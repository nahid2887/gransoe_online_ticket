from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema_field
from .models import Customer
from datetime import date


class CustomerDetailSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = ('id', 'full_name', 'email', 'username', 'phone_number', 'gender', 'date_of_birth', 'created_at')

    @extend_schema_field(serializers.CharField())
    def get_email(self, obj):
        return obj.user.email

    @extend_schema_field(serializers.CharField())
    def get_username(self, obj):
        return obj.user.username


class CustomerRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, help_text="Email address for login")
    password = serializers.CharField(write_only=True, min_length=8, required=True, help_text="Password minimum 8 characters")
    confirm_password = serializers.CharField(write_only=True, min_length=8, required=True, help_text="Confirm password")
    full_name = serializers.CharField(max_length=255, required=True, help_text="Customer full name")
    phone_number = serializers.CharField(max_length=20, required=True, help_text="Phone number")
    gender = serializers.ChoiceField(choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')], required=True, help_text="Gender (M/F/O)")
    date_of_birth = serializers.DateField(required=True, help_text="Date of birth (YYYY-MM-DD)")

    def validate(self, data):
        """Validate password and confirm_password match"""
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        
        # Check if email already exists
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({'email': 'Email already registered.'})
        
        return data

    def create(self, validated_data):
        """Create user and customer instance"""
        validated_data.pop('confirm_password')
        email = validated_data['email']
        password = validated_data['password']
        
        # Create User
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password
        )
        
        return user


class CustomerLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True, help_text="Email address")
    password = serializers.CharField(write_only=True, required=True, help_text="Password")

    def validate(self, data):
        """Validate email and password"""
        email = data.get('email')
        password = data.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({'email': 'Email not found.'})

        if not user.check_password(password):
            raise serializers.ValidationError({'password': 'Invalid password.'})

        data['user'] = user
        return data


class AuthResponseSerializer(serializers.Serializer):
    """Response serializer for authentication endpoints"""
    customer = CustomerDetailSerializer()
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    message = serializers.CharField()
