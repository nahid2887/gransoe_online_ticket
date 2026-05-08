from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerRegistrationView, CustomerLoginView, CustomerViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')

app_name = 'customer'

urlpatterns = [
    path('register/', CustomerRegistrationView.as_view(), name='customer-register'),
    path('login/', CustomerLoginView.as_view(), name='customer-login'),
    path('', include(router.urls)),
]
