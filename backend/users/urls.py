from django.urls import path

from .views import (
    AccountDataExportView,
    ChangePasswordView,
    CurrentUserView,
    LoginView,
    LogoutView,
    QuickFarmerRegisterView,
    RefreshTokenView,
    RegisterView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("quick-register/", QuickFarmerRegisterView.as_view(), name="quick_register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshTokenView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", CurrentUserView.as_view(), name="current_user"),
    path("me/export/", AccountDataExportView.as_view(), name="account_data_export"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
]
