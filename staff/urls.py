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
    MyProfileView,
    SuperuserOdersView,
     LatestBannerListView,
    BannerCreateView,
    BannerUpdateDeleteView,
    SingerListView,
    SingerCreateView,
    SingerUpdateDeleteView,
    AboutUsListView,
    AboutUsCreateView,
    AboutUsUpdateDeleteView,
    PrivacyPolicyListView,
    PrivacyPolicyCreateView,
    PrivacyPolicyUpdateDeleteView,
    TremsAndConditionListView,
    TremsAndConditionCreateView,
    TremsAndConditionUpdateDeleteView,
    SendOTPView,
    VerifyOTPView,
    ResetPasswordView,

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
    path('superuser/orders/',SuperuserOdersView.as_view(),name='superuser-order-list'),
    path('banners/', LatestBannerListView.as_view(), name='latest-banners'),
    path('banners/create/', BannerCreateView.as_view(), name='banner-create'),
    path('banners/<int:pk>/', BannerUpdateDeleteView.as_view(), name='banner-update-delete'),
    path('singers/', SingerListView.as_view(), name='singer-list'),
    path('singers/create/', SingerCreateView.as_view(), name='singer-create'),
    path('singers/<int:pk>/', SingerUpdateDeleteView.as_view(), name='singer-update-delete'),
    path('about-us/', AboutUsListView.as_view(), name='aboutus-list'),
    path('about-us/create/', AboutUsCreateView.as_view(), name='aboutus-create'),
    path('about-us/<int:pk>/', AboutUsUpdateDeleteView.as_view(), name='aboutus-update-delete'),    
    path('privacy-policy/', PrivacyPolicyListView.as_view(), name='privacy-policy-list'),
    path('privacy-policy/create/', PrivacyPolicyCreateView.as_view(), name='privacy-policy-create'),
    path('privacy-policy/<int:pk>/', PrivacyPolicyUpdateDeleteView.as_view(), name='privacy-policy-update-delete'),
    path('terms-and-conditions/', TremsAndConditionListView.as_view(), name='terms-and-conditions-list'),
    path('terms-and-conditions/create/', TremsAndConditionCreateView.as_view(), name='terms-and-conditions-create'),
    path('terms-and-conditions/<int:pk>/', TremsAndConditionUpdateDeleteView.as_view(), name='terms-and-conditions-update-delete'),
    path('forgot-password/send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('forgot-password/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('forgot-password/reset/', ResetPasswordView.as_view(), name='reset-password'),

    path('me/', MyProfileView.as_view(), name='my-profile'),
    path('', include(router.urls)),
]