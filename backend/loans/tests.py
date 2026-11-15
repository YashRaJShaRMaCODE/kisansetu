from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from farmers.models import Farmer
from rest_framework.test import APIRequestFactory, force_authenticate
from trustscore.models import TrustScore

from loans.models import LoanPrediction
from loans.serializers import LoanPredictionSerializer
from loans.services import calculate_loan_eligibility
from loans.views import LoanPredictionViewSet

User = get_user_model()


class LoanEligibilityTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="loan@test.com",
            username="loanuser",
            password="SecurePass123!",
            role="farmer",
        )
        self.farmer = Farmer.objects.create(
            user=self.user,
            aadhaar_number="111122223333",
            address="Farm Road",
            verification_status=True,
        )
        self.bank_user = User.objects.create_user(
            email="bank@test.com",
            username="bankuser",
            password="SecurePass123!",
            role="bank",
        )
        TrustScore.objects.update_or_create(
            farmer=self.farmer,
            defaults={
                "verification_score": 20,
                "transaction_score": 30,
                "buyer_rating_score": 20,
                "government_score": 15,
                "complaint_score": 15,
                "total_score": 100,
                "category": "Excellent",
            },
        )

    def test_calculate_loan_eligibility(self):
        prediction = calculate_loan_eligibility(self.farmer)
        self.assertGreater(prediction.eligible_amount, Decimal(0))
        self.assertIn(
            prediction.risk_category,
            ["low", "medium", "high"],
        )
        self.assertTrue(prediction.recommendation)
        self.assertIn("Demo estimate only", prediction.recommendation)
        self.assertNotIn("favorable interest rates", prediction.recommendation)

    def test_prediction_api_text_never_trusts_legacy_recommendation_copy(self):
        prediction = LoanPrediction.objects.create(
            farmer=self.farmer,
            trust_score=100,
            land_size=Decimal(1),
            revenue=Decimal(0),
            transaction_count=0,
            eligible_amount=Decimal(50000),
            risk_category="low",
            recommendation="Eligible for priority loan processing with favorable interest rates.",
        )

        text = LoanPredictionSerializer(prediction).data["recommendation"]

        self.assertIn("not a lender's credit assessment", text)
        self.assertNotIn("favorable interest rates", text)

    def test_bank_role_cannot_read_or_calculate_farmer_estimates_without_consent(self):
        factory = APIRequestFactory()
        list_view = LoanPredictionViewSet.as_view({"get": "list"})
        list_request = factory.get("/api/loans/")
        force_authenticate(list_request, user=self.bank_user)
        list_response = list_view(list_request)

        calculate_view = LoanPredictionViewSet.as_view({"post": "calculate"})
        calculate_request = factory.post(
            "/api/loans/calculate/",
            {"farmer_id": self.farmer.pk},
            format="json",
        )
        force_authenticate(calculate_request, user=self.bank_user)
        calculate_response = calculate_view(calculate_request)

        self.assertEqual(list_response.status_code, 403)
        self.assertEqual(calculate_response.status_code, 403)
        self.assertEqual(LoanPrediction.objects.count(), 0)

    def test_farmer_and_admin_roles_keep_loan_access(self):
        factory = APIRequestFactory()
        list_view = LoanPredictionViewSet.as_view({"get": "list"})
        farmer_request = factory.get("/api/loans/")
        force_authenticate(farmer_request, user=self.user)
        self.assertEqual(list_view(farmer_request).status_code, 200)

        admin = User.objects.create_superuser(
            email="admin@test.com",
            username="adminuser",
            password="SecurePass123!",
        )
        admin_request = factory.get("/api/loans/")
        force_authenticate(admin_request, user=admin)
        self.assertEqual(list_view(admin_request).status_code, 200)
