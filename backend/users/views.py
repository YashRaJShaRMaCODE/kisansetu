from django.db.models import FileField
from django.forms.models import model_to_dict
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import (
    ChangePasswordSerializer,
    QuickFarmerRegisterSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .tokens import CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_register"

    @extend_schema(tags=["Authentication"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class QuickFarmerRegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_quick_register"

    @extend_schema(tags=["Authentication"])
    def post(self, request):
        serializer = QuickFarmerRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                "message": "Welcome to UNNATI! Your profile is 20% complete.",
                "user": UserSerializer(user).data,
                "login_hint": f"Login with email: {user.email}",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    @extend_schema(tags=["Authentication"])
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            data = response.data
            response.data = {
                "access": data["access"],
                "refresh": data["refresh"],
                "message": "Login successful.",
            }
        return response


class RefreshTokenView(TokenRefreshView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Authentication"])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Authentication"])
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response(
                {"detail": "Invalid or expired refresh token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"message": "Logout successful."}, status=status.HTTP_200_OK)


class CurrentUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Authentication"])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(tags=["Authentication"])
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    def get_object(self):
        return self.request.user


class AccountDataExportView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(tags=["Authentication"], responses={200: dict})
    def get(self, request):
        from complaints.models import Complaint
        from crops.models import CropRecord
        from farmers.models import Buyer, Farmer
        from lands.models import LandRecord
        from loans.models import LoanPrediction
        from marketplace.models import Listing, Transaction
        from notifications.models import Notification
        from schemes.models import SchemeApplication
        from trustscore.models import TrustScore

        def record_data(instance, exclude=()):
            data = model_to_dict(instance, exclude=exclude)
            for field in instance._meta.concrete_fields:
                if isinstance(field, FileField):
                    data[field.name] = getattr(instance, field.name).name or None
            return data

        def export_records(queryset, exclude=()):
            return [
                record_data(item, exclude=exclude)
                for item in queryset.order_by("pk")
            ]

        user = request.user
        export = {
            "exported_at": timezone.now(),
            "account": {
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": user.phone_number,
                "role": user.role,
                "created_at": user.created_at,
            },
            "notifications": export_records(Notification.objects.filter(user=user)),
        }

        farmer = Farmer.objects.filter(user=user).first()
        if farmer:
            export["farmer_profile"] = record_data(farmer, exclude=["user"])
            export["land_records"] = export_records(
                LandRecord.objects.filter(farmer=farmer)
            )
            export["crop_records"] = export_records(
                CropRecord.objects.filter(farmer=farmer)
            )
            export["market_listings"] = export_records(
                Listing.objects.filter(farmer=farmer)
            )
            export["transactions"] = export_records(
                Transaction.objects.filter(listing__farmer=farmer), exclude=["buyer"]
            )
            export["complaints"] = export_records(
                Complaint.objects.filter(farmer=farmer)
            )
            export["scheme_applications"] = export_records(
                SchemeApplication.objects.filter(farmer=farmer)
            )
            score = TrustScore.objects.filter(farmer=farmer).first()
            export["trust_score"] = record_data(score) if score else None
            export["loan_predictions"] = export_records(
                LoanPrediction.objects.filter(farmer=farmer)
            )

        buyer = Buyer.objects.filter(user=user).first()
        if buyer:
            export["buyer_profile"] = record_data(buyer, exclude=["user"])
            export["transactions"] = export_records(
                Transaction.objects.filter(buyer=buyer), exclude=["listing"]
            )

        response = Response(export)
        response["Content-Disposition"] = (
            f'attachment; filename="unnati-data-export-{user.pk}-'
            f'{timezone.localdate().isoformat()}.json"'
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Authentication"])
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"old_password": "Incorrect password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        return Response({"message": "Password updated successfully."})
