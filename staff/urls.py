from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StaffRegistrationView, StaffLoginView, StaffViewSet, SuperuserLoginView

router = DefaultRouter()
router.register(r'staffs', StaffViewSet, basename='staff')

app_name = 'staff'

urlpatterns = [
    path('register/', StaffRegistrationView.as_view(), name='staff-register'),
    path('login/', StaffLoginView.as_view(), name='staff-login'),
    path('super/login/', SuperuserLoginView.as_view(), name='super-login'),
    path('', include(router.urls)),
]