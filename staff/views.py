from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny, IsAuthenticated
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
    SuperuserProfileSerializer,
    SuperuserProfileResponseSerializer,
    SuperuserPasswordChangeSerializer,
    SuperuserPasswordChangeResponseSerializer,
)


def build_staff_tokens(user, staff):
    refresh = RefreshToken.for_user(user)
    created_at = staff.created_at
    refresh['email'] = user.email
    refresh['username'] = user.username
    refresh['staff'] = {
        'id': staff.id,
        'full_name': staff.full_name,
        'email': user.email,
        'username': user.username,
        'phone_number': staff.phone_number,
        'created_at': created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at),
    }
    return refresh, str(refresh.access_token), str(refresh)


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
        refresh, access_token, refresh_token = build_staff_tokens(user, staff)
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
        refresh, access_token, refresh_token = build_staff_tokens(user, staff)
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


@extend_schema(
    responses=SuperuserDetailSerializer,
    description="Get the logged-in superuser profile.",
)
class SuperuserProfileView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get_superuser(self):
        user = self.request.user
        if not user.is_superuser:
            return None
        return user

    def get(self, request, *args, **kwargs):
        user = self.get_superuser()
        if user is None:
            return Response({'detail': 'User is not a superuser.'}, status=status.HTTP_403_FORBIDDEN)
        response_data = {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
            'date_joined': user.date_joined,
        }
        return Response(response_data, status=status.HTTP_200_OK)

    @extend_schema(
        request=SuperuserProfileSerializer,
        responses=SuperuserProfileResponseSerializer,
        description="Update the logged-in superuser profile information.",
    )
    def put(self, request, *args, **kwargs):
        user = self.get_superuser()
        if user is None:
            return Response({'detail': 'User is not a superuser.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = SuperuserProfileSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'email' in data:
            user.email = data['email']
            user.username = data['email']

        user.save(update_fields=['first_name', 'last_name', 'email', 'username'])

        response_data = {
            'superuser': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'is_superuser': user.is_superuser,
                'is_staff': user.is_staff,
                'date_joined': user.date_joined,
            },
            'message': 'Profile updated successfully',
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def patch(self, request, *args, **kwargs):
        return self.put(request, *args, **kwargs)


@extend_schema(
    request=SuperuserPasswordChangeSerializer,
    responses=SuperuserPasswordChangeResponseSerializer,
    description="Change the logged-in superuser password.",
)
class SuperuserPasswordChangeView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        if not user.is_superuser:
            return Response({'detail': 'User is not a superuser.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = SuperuserPasswordChangeSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])

        return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)
