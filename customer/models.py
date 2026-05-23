from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    event = models.ForeignKey('staff.Event', on_delete=models.CASCADE, related_name='orders')
    quantity = models.PositiveIntegerField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reservation_expires_at = models.DateTimeField(null=True, blank=True)
    stripe_payment_intent = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order {self.id} - {self.user.email} - {self.event.title} ({self.status})"


class Ticket(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='tickets')
    event = models.ForeignKey('staff.Event', on_delete=models.CASCADE, related_name='tickets')
    code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    tracking_number = models.CharField(max_length=64, unique=True, blank=True)
    qr_data = models.TextField(blank=True)  # base64 PNG or raw data for client (legacy)
    qr_image = models.CharField(max_length=512, blank=True)  # path/URL to generated QR image
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_tickets')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket {self.code} for {self.event.title}"


class Customer(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer')
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} - {self.user.email}"

    class Meta:
        ordering = ['-created_at']
