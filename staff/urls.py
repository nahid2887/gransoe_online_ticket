from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StaffRegistrationView,
    StaffLoginView,
    StaffViewSet,
    EventViewSet,
    StaffUpcomingEventViewSet,
    StaffVerifyTicketView,
    SuperuserLoginView,
    SuperuserProfileView,
    SuperuserPasswordChangeView,
    SuperuserDashboardView,
)

router = DefaultRouter()
router.register(r'staffs', StaffViewSet, basename='staff')
router.register(r'events', EventViewSet, basename='event')
router.register(r'upcoming-events', StaffUpcomingEventViewSet, basename='staff-upcoming-event')

app_name = 'staff'

urlpatterns = [
    path('register/', StaffRegistrationView.as_view(), name='staff-register'),
    path('login/', StaffLoginView.as_view(), name='staff-login'),
    path('verify-ticket/', StaffVerifyTicketView.as_view(), name='staff-verify-ticket'),
    path('super/login/', SuperuserLoginView.as_view(), name='super-login'),
    path('super/profile/', SuperuserProfileView.as_view(), name='super-profile'),
    path('super/change-password/', SuperuserPasswordChangeView.as_view(), name='super-change-password'),
    path('super/dashboard/', SuperuserDashboardView.as_view(), name='super-dashboard'),
    path('', include(router.urls)),
]