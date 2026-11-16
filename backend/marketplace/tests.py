from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace
from unittest import skipUnless

from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from rest_framework.exceptions import ValidationError

from crops.models import CropRecord
from farmers.models import Buyer, Farmer
from marketplace.models import Listing, Transaction
from marketplace.serializers import ListingSerializer, TransactionSerializer
from marketplace.views import TransactionViewSet
from users.models import User


class MarketplaceSafetyTests(TestCase):
    def setUp(self):
        self.farmer_user = User.objects.create_user(
            username="sample-farmer",
            email="farmer@example.test",
            password="local-test-password",
            role="farmer",
        )
        self.farmer = Farmer.objects.create(user=self.farmer_user)
        self.crop = CropRecord.objects.create(
            farmer=self.farmer,
            crop_name="Wheat",
            season="rabi",
            area_used=Decimal("1.00"),
            yield_amount=Decimal("10.00"),
            harvest_date=date(2026, 3, 1),
        )
        buyer_user = User.objects.create_user(
            username="sample-buyer",
            email="buyer@example.test",
            password="local-test-password",
            role="buyer",
        )
        self.buyer = Buyer.objects.create(user=buyer_user)
        self.listing = Listing.objects.create(
            farmer=self.farmer,
            crop=self.crop,
            quantity=Decimal("5.00"),
            price_per_unit=Decimal("10.00"),
        )

    def test_marketplace_listing_does_not_expose_account_email(self):
        data = ListingSerializer(self.listing).data

        self.assertNotIn("farmer_email", data)
        self.assertEqual(data["farmer_name"], "")

    def test_listing_amounts_must_be_positive(self):
        serializer = ListingSerializer()

        with self.assertRaises(ValidationError):
            serializer.validate_quantity(Decimal(0))
        with self.assertRaises(ValidationError):
            serializer.validate_price_per_unit(Decimal(-1))

    def test_transaction_rejects_non_active_listing(self):
        self.listing.status = "closed"
        self.listing.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            TransactionSerializer().validate({
                "listing": self.listing,
                "quantity": Decimal("1.00"),
            })

    def test_new_transaction_cannot_choose_its_own_status(self):
        serializer = TransactionSerializer(data={
            "listing": self.listing.pk,
            "quantity": "1.00",
            "status": "completed",
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)

    def test_transaction_update_cannot_change_reserved_listing_or_quantity(self):
        transaction = Transaction.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            quantity=Decimal("2.00"),
            total_amount=Decimal("20.00"),
        )
        serializer = TransactionSerializer(
            transaction, data={"quantity": "4.00"}, partial=True
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("detail", serializer.errors)

    def test_cancelling_pending_transaction_restores_reserved_stock(self):
        self.listing.quantity = Decimal("0.00")
        self.listing.status = "sold"
        self.listing.save(update_fields=["quantity", "status"])
        transaction = Transaction.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            quantity=Decimal("5.00"),
            total_amount=Decimal("50.00"),
        )
        serializer = TransactionSerializer(
            transaction, data={"status": "cancelled"}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        TransactionViewSet().perform_update(serializer)

        transaction.refresh_from_db()
        self.listing.refresh_from_db()
        self.assertEqual(transaction.status, "cancelled")
        self.assertEqual(self.listing.quantity, Decimal("5.00"))
        self.assertEqual(self.listing.status, "active")

    def test_completed_transaction_cannot_be_cancelled(self):
        transaction = Transaction.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            quantity=Decimal("1.00"),
            total_amount=Decimal("10.00"),
            status="completed",
        )
        serializer = TransactionSerializer(
            transaction, data={"status": "cancelled"}, partial=True
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)

    def test_completing_a_transaction_remains_available_after_listing_sells_out(self):
        self.listing.status = "sold"
        self.listing.quantity = Decimal("0.00")
        self.listing.save(update_fields=["status", "quantity"])
        transaction = Transaction.objects.create(
            listing=self.listing,
            buyer=self.buyer,
            quantity=Decimal("5.00"),
            total_amount=Decimal("50.00"),
        )

        serializer = TransactionSerializer(
            transaction, data={"status": "completed"}, partial=True
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_checkout_rechecks_quantity_after_locking_current_listing(self):
        serializer = TransactionSerializer(data={
            "listing": self.listing.pk,
            "quantity": "4.00",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

        Listing.objects.filter(pk=self.listing.pk).update(quantity=Decimal("2.00"))
        view = TransactionViewSet()
        view.request = SimpleNamespace(user=self.buyer.user)

        with self.assertRaises(ValidationError):
            view.perform_create(serializer)

        self.assertEqual(Transaction.objects.count(), 0)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity, Decimal("2.00"))

    def test_checkout_reserves_quantity_and_calculates_total(self):
        serializer = TransactionSerializer(data={
            "listing": self.listing.pk,
            "quantity": "2.00",
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        view = TransactionViewSet()
        view.request = SimpleNamespace(user=self.buyer.user)

        view.perform_create(serializer)

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity, Decimal("3.00"))
        self.assertEqual(serializer.instance.status, "pending")
        self.assertEqual(serializer.instance.total_amount, Decimal("20.00"))


@skipUnless(connection.vendor == "postgresql", "row-lock concurrency requires PostgreSQL")
class MarketplacePostgresConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_checkouts_cannot_oversell_listing(self):
        seller_user = User.objects.create_user(
            username="locking-farmer", email="locking-farmer@example.test",
            password="local-test-password", role="farmer",
        )
        farmer = Farmer.objects.create(user=seller_user)
        crop = CropRecord.objects.create(
            farmer=farmer, crop_name="Wheat", season="rabi", area_used=Decimal("1.00"),
            yield_amount=Decimal("10.00"), harvest_date=date(2026, 3, 1),
        )
        buyer_user = User.objects.create_user(
            username="locking-buyer", email="locking-buyer@example.test",
            password="local-test-password", role="buyer",
        )
        Buyer.objects.create(user=buyer_user)
        listing = Listing.objects.create(
            farmer=farmer, crop=crop, quantity=Decimal("5.00"),
            price_per_unit=Decimal("10.00"),
        )
        start_together = Barrier(2)

        def checkout():
            connections.close_all()
            try:
                serializer = TransactionSerializer(data={
                    "listing": listing.pk,
                    "quantity": "4.00",
                })
                if not serializer.is_valid():
                    return "invalid"
                start_together.wait(timeout=10)
                view = TransactionViewSet()
                view.request = SimpleNamespace(user=User.objects.get(pk=buyer_user.pk))
                view.perform_create(serializer)
                return "created"
            except ValidationError:
                return "rejected"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [future.result(timeout=20) for future in (pool.submit(checkout), pool.submit(checkout))]

        listing.refresh_from_db()
        self.assertCountEqual(outcomes, ["created", "rejected"])
        self.assertEqual(listing.quantity, Decimal("1.00"))
        self.assertEqual(Transaction.objects.count(), 1)
