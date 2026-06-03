from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomerRegistrationView,
    CustomerLoginView,
    CustomerViewSet,
    UpcomingEventListView,
    UpcomingEventDetailView,
    PurchaseView,
    MyTicketsView,
    MyTicketDetailView,
    StripeWebhookView,
    LogoutView,
    OrderListView,
    OrderDetailView,
)

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')

app_name = 'customer'

urlpatterns = [
    path('register/', CustomerRegistrationView.as_view(), name='customer-register'),
    path('login/', CustomerLoginView.as_view(), name='customer-login'),
    path('logout/', LogoutView.as_view(), name='customer-logout'),
    path('events/upcoming/', UpcomingEventListView.as_view(), name='upcoming-events'),
    path('events/upcoming/<int:pk>/', UpcomingEventDetailView.as_view(), name='upcoming-event-detail'),
    path('purchase/', PurchaseView.as_view(), name='purchase'),
    path('my-tickets/', MyTicketsView.as_view(), name='my-tickets'),
    path('my-tickets/<int:pk>/', MyTicketDetailView.as_view(), name='my-ticket-detail'),
    path('webhook/stripe', StripeWebhookView.as_view(), name='stripe-webhook-no-slash'),
    path('webhook/stripe/', StripeWebhookView.as_view(), name='stripe-webhook'),
    path('orders/', OrderListView.as_view(), name='order-list'),
    path('orders/<int:pk>/', OrderDetailView.as_view(), name='order-detail'),
    path('', include(router.urls)),
]
