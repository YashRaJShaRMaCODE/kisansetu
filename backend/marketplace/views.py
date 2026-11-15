from django.db import transaction as db_transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.filters import OrderingFilter, SearchFilter

from marketplace.models import Listing, Transaction

from .filters import ListingFilter, TransactionFilter
from .permissions import ListingPermission, TransactionPermission
from .serializers import ListingSerializer, TransactionSerializer


class ListingViewSet(viewsets.ModelViewSet):
    queryset = Listing.objects.select_related(
        "farmer__user", "crop"
    ).all()
    serializer_class = ListingSerializer
    permission_classes = (ListingPermission,)
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_class = ListingFilter
    search_fields = (
        "crop__crop_name",
        "description",
        "farmer__user__first_name",
        "farmer__user__last_name",
    )
    ordering_fields = ("price_per_unit", "quantity", "created_at")
    ordering = ("-created_at",)

    def get_queryset(self):
        user = self.request.user
        if user.role == "farmer" and hasattr(user, "farmer_profile"):
            if self.action in ("list", "retrieve"):
                return self.queryset.filter(
                    Q(farmer=user.farmer_profile) | Q(status="active")
                )
            return self.queryset.filter(farmer=user.farmer_profile)
        return self.queryset

    def perform_create(self, serializer):
        serializer.save(farmer=self.request.user.farmer_profile)


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.select_related(
        "listing__crop",
        "listing__farmer__user",
        "buyer__user",
    ).all()
    serializer_class = TransactionSerializer
    permission_classes = (TransactionPermission,)
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_class = TransactionFilter
    search_fields = (
        "listing__crop__crop_name",
        "buyer__user__email",
        "listing__farmer__user__email",
    )
    ordering_fields = ("transaction_date", "total_amount", "status")
    ordering = ("-transaction_date",)

    def get_queryset(self):
        user = self.request.user
        if user.role == "buyer" and hasattr(user, "buyer_profile"):
            return self.queryset.filter(buyer=user.buyer_profile)
        if user.role == "farmer" and hasattr(user, "farmer_profile"):
            return self.queryset.filter(listing__farmer=user.farmer_profile)
        if user.role == "admin" or user.is_superuser:
            return self.queryset
        return Transaction.objects.none()

    @db_transaction.atomic
    def perform_create(self, serializer):
        requested_listing = serializer.validated_data["listing"]
        listing = get_object_or_404(
            Listing.objects.select_for_update(), pk=requested_listing.pk
        )
        quantity = serializer.validated_data["quantity"]
        if listing.status != "active":
            raise ValidationError({"listing": "This listing is no longer available."})
        if quantity <= 0 or quantity > listing.quantity:
            raise ValidationError(
                {"quantity": "Quantity exceeds the currently available amount."}
            )

        txn = serializer.save(buyer=self.request.user.buyer_profile, listing=listing)
        listing.quantity -= txn.quantity
        if listing.quantity <= 0:
            listing.quantity = 0
            listing.status = "sold"
        listing.save(update_fields=["quantity", "status"])

    @db_transaction.atomic
    def perform_update(self, serializer):
        current = Transaction.objects.select_for_update().get(
            pk=serializer.instance.pk
        )
        new_status = serializer.validated_data.get("status", current.status)
        if new_status != current.status and current.status != "pending":
            raise ValidationError(
                {"status": "Only pending transactions can change status."}
            )

        if new_status == "cancelled" and current.status == "pending":
            listing = Listing.objects.select_for_update().get(pk=current.listing_id)
            listing.quantity += current.quantity
            fields = ["quantity"]
            if listing.status == "sold":
                listing.status = "active"
                fields.append("status")
            listing.save(update_fields=fields)

        serializer.save()
        if new_status == "completed" and current.status != "completed":
            from trustscore.services import recalculate_farmer_trust_score

            listing = Listing.objects.select_related("farmer").get(pk=current.listing_id)
            recalculate_farmer_trust_score(listing.farmer)
