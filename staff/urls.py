from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StaffRegistrationView,
    StaffLoginView,
    StaffViewSet,
    SuperuserLoginView,
    SuperuserProfileView,
    SuperuserPasswordChangeView,
)

router = DefaultRouter()
router.register(r'staffs', StaffViewSet, basename='staff')

app_name = 'staff'

urlpatterns = [
    path('register/', StaffRegistrationView.as_view(), name='staff-register'),
    path('login/', StaffLoginView.as_view(), name='staff-login'),
    path('super/login/', SuperuserLoginView.as_view(), name='super-login'),
    path('super/profile/', SuperuserProfileView.as_view(), name='super-profile'),
    path('super/change-password/', SuperuserPasswordChangeView.as_view(), name='super-change-password'),
    path('', include(router.urls)),
]