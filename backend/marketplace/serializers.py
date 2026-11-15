from farmers.services import get_farmer_badges
from rest_framework import serializers
from trustscore.models import TrustScore

from marketplace.models import Listing, Transaction


class ListingSerializer(serializers.ModelSerializer):
    farmer_name = serializers.SerializerMethodField()
    farmer_village = serializers.CharField(source="farmer.village", read_only=True)
    crop_name = serializers.CharField(source="crop.crop_name", read_only=True)
    farmer_trust_score = serializers.SerializerMethodField()
    farmer_trust_category = serializers.SerializerMethodField()
    farmer_badges = serializers.SerializerMethodField()
    is_verified_farmer = serializers.BooleanField(
        source="farmer.verification_status", read_only=True
    )

    class Meta:
        model = Listing
        fields = (
            "id",
            "farmer",
            "farmer_name",
            "farmer_village",
            "crop",
            "crop_name",
            "quantity",
            "price_per_unit",
            "description",
            "status",
            "created_at",
            "farmer_trust_score",
            "farmer_trust_category",
            "farmer_badges",
            "is_verified_farmer",
        )
        read_only_fields = ("id", "farmer", "created_at")

    def get_farmer_name(self, obj):
        u = obj.farmer.user
        return f"{u.first_name} {u.last_name}".strip()

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    def validate_price_per_unit(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    def get_farmer_trust_score(self, obj):
        ts = TrustScore.objects.filter(farmer=obj.farmer).first()
        return ts.total_score if ts else 0

    def get_farmer_trust_category(self, obj):
        ts = TrustScore.objects.filter(farmer=obj.farmer).first()
        return ts.category if ts else "Average"

    def get_farmer_badges(self, obj):
        return get_farmer_badges(obj.farmer)[:4]


class TransactionSerializer(serializers.ModelSerializer):
    listing_crop = serializers.CharField(
        source="listing.crop.crop_name", read_only=True
    )
    buyer_email = serializers.EmailField(source="buyer.user.email", read_only=True)
    farmer_email = serializers.EmailField(
        source="listing.farmer.user.email", read_only=True
    )

    class Meta:
        model = Transaction
        fields = (
            "id",
            "listing",
            "listing_crop",
            "buyer",
            "buyer_email",
            "farmer_email",
            "quantity",
            "total_amount",
            "status",
            "transaction_date",
        )
        read_only_fields = ("id", "buyer", "total_amount", "transaction_date")

    def validate(self, attrs):
        listing = attrs.get("listing") or self.instance.listing
        quantity = attrs.get("quantity", self.instance.quantity if self.instance else None)
        status = attrs.get("status", self.instance.status if self.instance else "pending")
        if quantity is not None and quantity <= 0:
            raise serializers.ValidationError(
                {"quantity": "Quantity must be greater than zero."}
            )
        if self.instance is None and status != "pending":
            raise serializers.ValidationError(
                {"status": "New transactions must start as pending."}
            )
        if self.instance is not None:
            changes = set(attrs) - {"status"}
            if changes:
                raise serializers.ValidationError(
                    {"detail": "Only transaction status can be updated."}
                )
            if status != self.instance.status and self.instance.status != "pending":
                raise serializers.ValidationError(
                    {"status": "Only pending transactions can change status."}
                )
        if self.instance is None and listing.status != "active":
            raise serializers.ValidationError(
                {"listing": "This listing is no longer available."}
            )
        if self.instance is None and quantity > listing.quantity:
            raise serializers.ValidationError(
                {"quantity": "Quantity exceeds available listing quantity."}
            )
        return attrs

    def create(self, validated_data):
        listing = validated_data["listing"]
        quantity = validated_data["quantity"]
        validated_data["total_amount"] = quantity * listing.price_per_unit
        return super().create(validated_data)
