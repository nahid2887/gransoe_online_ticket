from rest_framework.permissions import BasePermission


class IsCustomer(BasePermission):
    """Allow access only to authenticated users who have a Customer profile."""

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        return hasattr(user, 'customer')
