from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema_field
from .models import Customer
from datetime import date
from staff.models import Event


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
        if User.objects.filter(email__iexact=data['email']).exists():
            raise serializers.ValidationError({'email': 'Email already registered.'})
        
        return data

    def create(self, validated_data):
        """Create user and customer instance"""
        validated_data.pop('confirm_password')
        email = validated_data['email']
        password = validated_data['password']
        
        try:
            return User.objects.create_user(
                username=email,
                email=email,
                password=password
            )
        except Exception:
            raise serializers.ValidationError({'email': 'Email already registered.'})


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


class UpcomingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = (
            'id', 'title', 'description', 'venue', 'age', 'image', 'date', 'time',
            'ticket_type', 'available_tickets', 'max_per_order', 'price_per_ticket',
            'platform_fee', 'created_at', 'updated_at',
        )


class PurchaseSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)


class TicketSerializer(serializers.ModelSerializer):
    qr_image = serializers.SerializerMethodField()
    is_verified = serializers.BooleanField(read_only=True)
    verified_at = serializers.DateTimeField(read_only=True)
    verified_by = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = getattr(__import__('customer.models', fromlist=['Ticket']), 'Ticket')
        fields = ('id', 'code', 'tracking_number', 'qr_data', 'qr_image', 'event', 'is_verified', 'verified_at', 'verified_by', 'created_at')

    def get_qr_image(self, obj):
        if not obj.qr_image:
            return ''

        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(obj.qr_image)

        return obj.qr_image

    @extend_schema_field(serializers.JSONField(allow_null=True))
    def get_verified_by(self, obj):
        if not obj.verified_by:
            return None
        return {'id': obj.verified_by.id, 'email': obj.verified_by.email}


class OrderSerializer(serializers.ModelSerializer):
    tickets = TicketSerializer(many=True, read_only=True)

    class Meta:
        model = getattr(__import__('customer.models', fromlist=['Order']), 'Order')
        fields = ('id', 'user', 'event', 'quantity', 'total_amount', 'platform_fee', 'status', 'reservation_expires_at', 'stripe_payment_intent', 'created_at', 'tickets')
        read_only_fields = ('user', 'total_amount', 'platform_fee', 'status', 'reservation_expires_at', 'stripe_payment_intent', 'created_at', 'tickets')
