from rest_framework import permissions


class LandRecordPermission(permissions.BasePermission):
    """
    Farmer: CRUD on own land records.
    Government/Admin: full access including verification.
    Bank: no access until farmer-controlled sharing is available.
    Buyer: no access.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in ("farmer", "admin", "government") or request.user.is_superuser

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role in ("admin", "government") or user.is_superuser:
            return True
        if user.role == "farmer":
            return (
                hasattr(user, "farmer_profile")
                and obj.farmer_id == user.farmer_profile.id
            )
        return False
