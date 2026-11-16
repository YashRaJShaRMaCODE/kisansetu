from rest_framework.exceptions import ValidationError

from crops.models import CropRecord
from schemes.models import GovernmentScheme, SchemeApplication


def validate_unique_application(farmer, scheme):
    if SchemeApplication.objects.filter(farmer=farmer, scheme=scheme).exists():
        raise ValidationError({"scheme": "You have already applied to this scheme."})


def recommend_schemes_for_farmer(farmer):
    crops = list(
        CropRecord.objects.filter(farmer=farmer).values_list("crop_name", flat=True)
    )
    applied_ids = SchemeApplication.objects.filter(farmer=farmer).values_list(
        "scheme_id", flat=True
    )
    schemes = GovernmentScheme.objects.filter(is_active=True).exclude(
        id__in=applied_ids
    )

    recommendations = []
    for scheme in schemes:
        searchable_text = (
            f"{scheme.name} {scheme.description} {scheme.eligibility_criteria}"
        ).casefold()
        matched_crops = [crop for crop in crops if crop.casefold() in searchable_text]
        if not matched_crops:
            continue
        recommendations.append(
            {
                "scheme_id": scheme.id,
                "name": scheme.name,
                "description": scheme.description[:200],
                "benefit_amount": float(scheme.benefit_amount),
                "reasons": [f"Scheme text mentions your crop: {crop}." for crop in matched_crops],
            }
        )

    recommendations.sort(key=lambda item: (-len(item["reasons"]), item["name"].casefold()))
    return recommendations[:8]
