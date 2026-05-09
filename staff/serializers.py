from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema_field
from .models import Staff


class StaffDetailSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()

    class Meta:
        model = Staff
        fields = ('id', 'full_name', 'email', 'username', 'phone_number', 'created_at')

    @extend_schema_field(serializers.CharField())
    def get_email(self, obj):
        return obj.user.email

    @extend_schema_field(serializers.CharField())
    def get_username(self, obj):
        return obj.user.username


class StaffRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, min_length=8, required=True)
    confirm_password = serializers.CharField(write_only=True, min_length=8, required=True)
    full_name = serializers.CharField(max_length=255, required=True)
    phone_number = serializers.CharField(max_length=20, required=True)
    # Registration now only requires the fields specified by the user.

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({'email': 'Email already registered.'})
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        email = validated_data['email']
        password = validated_data['password']
        user = User.objects.create_user(username=email, email=email, password=password)
        return user


class StaffLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        # Try finding user by email first, then by username for flexibility
        user = None
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            try:
                user = User.objects.get(username=email)
            except User.DoesNotExist:
                raise serializers.ValidationError({'email': 'Email not found.'})
        if not user.check_password(password):
            raise serializers.ValidationError({'password': 'Invalid password.'})
        data['user'] = user
        return data


class StaffAuthResponseSerializer(serializers.Serializer):
    staff = StaffDetailSerializer()
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    message = serializers.CharField()


class SuperuserDetailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    username = serializers.CharField()
    is_superuser = serializers.BooleanField()
    is_staff = serializers.BooleanField()
    date_joined = serializers.DateTimeField()


class SuperuserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({'email': 'Email not found.'})
        if not user.check_password(password):
            raise serializers.ValidationError({'password': 'Invalid password.'})
        if not user.is_superuser:
            raise serializers.ValidationError({'permission': 'User is not a superuser.'})
        data['user'] = user
        return data


class SuperuserAuthResponseSerializer(serializers.Serializer):
    superuser = SuperuserDetailSerializer()
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    message = serializers.CharField()


class SuperuserProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False)

    def validate(self, data):
        email = data.get('email')
        user = self.context['request'].user
        if email and User.objects.exclude(pk=user.pk).filter(email=email).exists():
            raise serializers.ValidationError({'email': 'Email already in use.'})
        return data


class SuperuserProfileResponseSerializer(serializers.Serializer):
    superuser = SuperuserDetailSerializer()
    message = serializers.CharField()


class SuperuserPasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, min_length=8, required=True)
    confirm_new_password = serializers.CharField(write_only=True, min_length=8, required=True)

    def validate(self, data):
        user = self.context['request'].user
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        confirm_new_password = data.get('confirm_new_password')

        if not user.check_password(current_password):
            raise serializers.ValidationError({'current_password': 'Current password is incorrect.'})
        if new_password != confirm_new_password:
            raise serializers.ValidationError({'confirm_new_password': 'Passwords do not match.'})
        return data


class SuperuserPasswordChangeResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
