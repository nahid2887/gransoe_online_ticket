from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from django.contrib.auth.models import User

from .models import Customer
from .serializers import (
    CustomerRegistrationSerializer,
    CustomerLoginSerializer,
    CustomerDetailSerializer,
    AuthResponseSerializer,
)


def build_customer_tokens(user, customer):
    refresh = RefreshToken.for_user(user)
    refresh['email'] = user.email
    refresh['username'] = user.username
    refresh['full_name'] = customer.full_name
    refresh['phone_number'] = customer.phone_number
    refresh['gender'] = customer.gender
    date_of_birth = customer.date_of_birth
    created_at = customer.created_at
    refresh['date_of_birth'] = date_of_birth.isoformat() if hasattr(date_of_birth, 'isoformat') else str(date_of_birth)
    refresh['customer'] = {
        'id': customer.id,
        'full_name': customer.full_name,
        'email': user.email,
        'username': user.username,
        'phone_number': customer.phone_number,
        'gender': customer.gender,
        'date_of_birth': refresh['date_of_birth'],
        'created_at': created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
    }
    return refresh, str(refresh.access_token), str(refresh)


@extend_schema(
    request=CustomerRegistrationSerializer,
    responses=AuthResponseSerializer,
    description="Register a new customer account with required details.",
)
class CustomerRegistrationView(GenericAPIView):
    serializer_class = CustomerRegistrationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Get customer details from request
        full_name = request.data.get('full_name', 'Not provided')
        phone_number = request.data.get('phone_number', '')
        gender = request.data.get('gender', 'O')
        date_of_birth = request.data.get('date_of_birth', None)

        # Create Customer profile
        customer = Customer.objects.create(
            user=user,
            full_name=full_name,
            phone_number=phone_number,
            gender=gender,
            date_of_birth=date_of_birth
        )

        # Generate tokens with customer details in the JWT claims
        refresh, access_token, refresh_token = build_customer_tokens(user, customer)

        # Prepare response
        customer_data = CustomerDetailSerializer(customer).data
        response_data = {
            'customer': customer_data,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Customer registered successfully'
        }

        response = Response(response_data, status=status.HTTP_201_CREATED)

        # Set refresh token in secure HTTP-only cookie
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            max_age=86400,  # 1 day
            secure=False,  # Set to True in production with HTTPS
            httponly=True,
            samesite='Lax'
        )

        return response


@extend_schema(
    request=CustomerLoginSerializer,
    responses=AuthResponseSerializer,
    description="Login with email and password. Returns customer details, access token, and refresh token in cookie.",
)
class CustomerLoginView(GenericAPIView):
    serializer_class = CustomerLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        try:
            customer = Customer.objects.get(user=user)
        except Customer.DoesNotExist:
            return Response({'error': 'Customer profile not found'}, status=status.HTTP_404_NOT_FOUND)

        # Generate tokens with customer details in the JWT claims
        refresh, access_token, refresh_token = build_customer_tokens(user, customer)

        # Prepare response
        customer_data = CustomerDetailSerializer(customer).data
        response_data = {
            'customer': customer_data,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Login successful'
        }

        response = Response(response_data, status=status.HTTP_200_OK)

        # Set refresh token in secure HTTP-only cookie
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            max_age=86400,  # 1 day
            secure=False,  # Set to True in production with HTTPS
            httponly=True,
            samesite='Lax'
        )

        return response


class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for retrieving customer details.
    Requires JWT authentication.
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'user__id'
