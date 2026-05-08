from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema
from rest_framework.generics import GenericAPIView
from django.contrib.auth.models import User

from .models import Staff
from .serializers import (
    StaffRegistrationSerializer,
    StaffLoginSerializer,
    StaffDetailSerializer,
    StaffAuthResponseSerializer,
    SuperuserLoginSerializer,
    SuperuserAuthResponseSerializer,
    SuperuserDetailSerializer,
)


@extend_schema(
    request=StaffRegistrationSerializer,
    responses=StaffAuthResponseSerializer,
    description="Register a new staff member with required details.",
)
class StaffRegistrationView(GenericAPIView):
    serializer_class = StaffRegistrationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        full_name = request.data.get('full_name', '')
        phone_number = request.data.get('phone_number', '')
        staff = Staff.objects.create(
            user=user,
            full_name=full_name,
            phone_number=phone_number
        )
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        staff_data = StaffDetailSerializer(staff).data
        response_data = {
            'staff': staff_data,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Staff registered successfully'
        }
        response = Response(response_data, status=status.HTTP_201_CREATED)
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            max_age=86400,
            secure=False,
            httponly=True,
            samesite='Lax'
        )
        return response


@extend_schema(
    request=StaffLoginSerializer,
    responses=StaffAuthResponseSerializer,
    description="Staff login. Returns staff details and tokens.",
)
class StaffLoginView(GenericAPIView):
    serializer_class = StaffLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        try:
            staff = Staff.objects.get(user=user)
        except Staff.DoesNotExist:
            return Response({'error': 'Staff profile not found'}, status=status.HTTP_404_NOT_FOUND)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        staff_data = StaffDetailSerializer(staff).data
        response_data = {
            'staff': staff_data,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Login successful'
        }
        response = Response(response_data, status=status.HTTP_200_OK)
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            max_age=86400,
            secure=False,
            httponly=True,
            samesite='Lax'
        )
        return response


class StaffViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Staff.objects.all()
    serializer_class = StaffDetailSerializer


@extend_schema(
    request=SuperuserLoginSerializer,
    responses=SuperuserAuthResponseSerializer,
    description="Superuser login using email and password. Returns user details and tokens.",
)
class SuperuserLoginView(GenericAPIView):
    serializer_class = SuperuserLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # Prepare superuser detail data
        super_data = {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'date_joined': user.date_joined,
        }

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        response_data = {
            'superuser': super_data,
            'access_token': access_token,
            'refresh_token': refresh_token,
            'message': 'Superuser login successful'
        }

        response = Response(response_data, status=status.HTTP_200_OK)
        response.set_cookie(
            key='refresh_token',
            value=refresh_token,
            max_age=86400,
            secure=False,
            httponly=True,
            samesite='Lax'
        )
        return response
    permission_classes = [AllowAny]
    lookup_field = 'user__id'
