from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from crops.models import CropRecord
from farmers.models import Farmer
from schemes.models import GovernmentScheme
from schemes.services import recommend_schemes_for_farmer
from trustscore.models import TrustScore


class SchemeDiscoveryTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            email="farmer@example.test", username="farmer", password="test-only"
        )
        self.farmer = Farmer.objects.create(user=user)
        CropRecord.objects.create(
            farmer=self.farmer,
            crop_name="Wheat",
            season="rabi",
            area_used="1.00",
            yield_amount="2.00",
            harvest_date=date(2026, 4, 1),
        )

    def create_scheme(self, *, name, criteria, active=True):
        return GovernmentScheme.objects.create(
            name=name,
            description="Public scheme information",
            eligibility_criteria=criteria,
            benefit_amount="1000.00",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=active,
        )

    def test_recommendations_use_crop_text_and_disclose_the_basis(self):
        wheat = self.create_scheme(name="Seasonal support", criteria="For Wheat growers")
        self.create_scheme(name="Other crop", criteria="For cotton growers")
        self.create_scheme(name="Inactive wheat", criteria="Wheat", active=False)
        TrustScore.objects.filter(farmer=self.farmer).update(total_score=100)

        results = recommend_schemes_for_farmer(self.farmer)

        self.assertEqual([item["scheme_id"] for item in results], [wheat.id])
        self.assertEqual(results[0]["reasons"], ["Scheme text mentions your crop: Wheat."])
        self.assertNotIn("match_score", results[0])

    def test_trust_score_alone_never_creates_scheme_suggestions(self):
        self.farmer.crops.all().delete()
        self.create_scheme(name="General farmer scheme", criteria="Check local office rules")
        TrustScore.objects.filter(farmer=self.farmer).update(total_score=100)

        self.assertEqual(recommend_schemes_for_farmer(self.farmer), [])
