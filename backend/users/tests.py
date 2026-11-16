from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from complaints.models import Complaint
from crops.models import CropRecord
from farmers.models import Buyer, Farmer
from lands.models import LandRecord
from marketplace.models import Listing, Transaction

User = get_user_model()


class AuthAPITestCase(APITestCase):
    def setUp(self):
        self.register_url = reverse("register")
        self.login_url = reverse("login")
        self.me_url = reverse("current_user")

    def test_register_farmer(self):
        payload = {
            "email": "farmer@test.com",
            "username": "farmer1",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "role": "farmer",
            "first_name": "Test",
            "last_name": "Farmer",
        }
        response = self.client.post(self.register_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        farmer = Farmer.objects.get(user__email="farmer@test.com")
        self.assertIsNone(farmer.aadhaar_number)

    def test_registration_cannot_assign_privileged_roles(self):
        for role in ("admin", "bank", "government"):
            with self.subTest(role=role):
                response = self.client.post(
                    self.register_url,
                    {
                        "email": f"{role}@test.com",
                        "username": role,
                        "password": "SecurePass123!",
                        "password_confirm": "SecurePass123!",
                        "role": role,
                        "first_name": "Test",
                        "last_name": "User",
                    },
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertFalse(User.objects.filter(email=f"{role}@test.com").exists())

    def test_user_cannot_change_own_role(self):
        user = User.objects.create_user(
            email="self-role@test.com", username="self-role", password="SecurePass123!"
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(self.me_url, {"role": "admin"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.role, "farmer")

    def test_register_buyer_creates_profile(self):
        response = self.client.post(
            self.register_url,
            {
                "email": "buyer@test.com",
                "username": "buyer",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "role": "buyer",
                "first_name": "Test",
                "last_name": "Buyer",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.get(email="buyer@test.com").buyer_profile)

    def test_login_and_me(self):
        user = User.objects.create_user(
            email="login@test.com",
            username="loginuser",
            password="SecurePass123!",
            role="farmer",
        )
        Farmer.objects.create(
            user=user,
            aadhaar_number="123456789012",
            address="Test Address",
        )
        login_response = self.client.post(
            self.login_url,
            {"email": "login@test.com", "password": "SecurePass123!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        access = login_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        me_response = self.client.get(self.me_url)
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["email"], "login@test.com")

    def test_account_export_contains_only_authenticated_users_records(self):
        owner = User.objects.create_user(
            email="export@test.com", username="export", password="SecurePass123!"
        )
        other = User.objects.create_user(
            email="other@test.com", username="other", password="SecurePass123!"
        )
        farmer = Farmer.objects.create(
            user=owner, aadhaar_number="123456789012", address="Private address"
        )
        other_farmer = Farmer.objects.create(user=other, aadhaar_number="987654321098")
        LandRecord.objects.create(
            farmer=farmer, survey_number="OWN-1", total_area="2.50", soil_type="black",
            irrigation_type="well", location="Own village",
        )
        LandRecord.objects.create(
            farmer=other_farmer, survey_number="OTHER-1", total_area="3.00",
            soil_type="red",
            irrigation_type="canal", location="Other village",
        )
        Complaint.objects.create(
            farmer=farmer, title="My complaint", description="My private note"
        )
        Complaint.objects.create(
            farmer=other_farmer, title="Other complaint", description="Do not include"
        )
        self.client.force_authenticate(user=owner)

        response = self.client.get(reverse("account_data_export"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(
            response.data["farmer_profile"]["aadhaar_number"], "123456789012"
        )
        self.assertEqual(
            [row["survey_number"] for row in response.data["land_records"]], ["OWN-1"]
        )
        self.assertEqual(
            [row["title"] for row in response.data["complaints"]], ["My complaint"]
        )
        self.assertNotIn("Do not include", str(response.data))
        self.assertNotIn("987654321098", str(response.data))

    def test_account_export_requires_auth_and_hides_farmer_details_from_buyer(self):
        response = self.client.get(reverse("account_data_export"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        buyer_user = User.objects.create_user(
            email="buyer-export@test.com", username="buyer-export",
            password="SecurePass123!", role="buyer",
        )
        farmer_user = User.objects.create_user(
            email="farmer-export@test.com", username="farmer-export",
            password="SecurePass123!",
        )
        buyer = Buyer.objects.create(user=buyer_user, company_name="Buyer Co")
        farmer = Farmer.objects.create(
            user=farmer_user, address="Farmer private address"
        )
        listing_crop = CropRecord.objects.create(
            farmer=farmer, crop_name="Wheat", season="rabi", area_used="1.00",
            yield_amount="2.00", harvest_date="2026-11-17",
        )
        listing = Listing.objects.create(
            farmer=farmer, crop=listing_crop, quantity="2.00", price_per_unit="20.00"
        )
        Transaction.objects.create(
            listing=listing, buyer=buyer, quantity="1.00", total_amount="20.00"
        )
        self.client.force_authenticate(user=buyer_user)

        response = self.client.get(reverse("account_data_export"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["transactions"]), 1)
        self.assertNotIn("farmer_profile", response.data)
        self.assertNotIn("Farmer private address", str(response.data))

    def test_login_throttle_blocks_repeated_attempts(self):
        cache.clear()
        responses = [
            self.client.post(
                self.login_url,
                {"email": "missing@test.com", "password": "wrong"},
                format="json",
            )
            for _ in range(11)
        ]
        cache.clear()
        self.assertTrue(
            all(
                response.status_code == status.HTTP_401_UNAUTHORIZED
                for response in responses[:10]
            )
        )
        self.assertEqual(responses[10].status_code, status.HTTP_429_TOO_MANY_REQUESTS)
