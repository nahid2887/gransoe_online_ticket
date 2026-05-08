from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StaffRegistrationView, StaffLoginView, StaffViewSet

router = DefaultRouter()
router.register(r'staffs', StaffViewSet, basename='staff')

app_name = 'staff'

urlpatterns = [
    path('register/', StaffRegistrationView.as_view(), name='staff-register'),
    path('login/', StaffLoginView.as_view(), name='staff-login'),
    path('', include(router.urls)),
]