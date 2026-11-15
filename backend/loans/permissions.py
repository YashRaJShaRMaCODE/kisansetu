from rest_framework import permissions


class LoanPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser or request.user.role in ("farmer", "admin")

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == "admin" or user.is_superuser:
            return True
        if user.role == "farmer":
            return (
                hasattr(user, "farmer_profile")
                and obj.farmer_id == user.farmer_profile.id
            )
        return False
