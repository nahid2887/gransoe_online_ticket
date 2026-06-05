from django.db import models
from django.contrib.auth.models import User


class Staff(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff')
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    role = models.CharField(max_length=100, default='Check-in Staff')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} - {self.user.email}"

    class Meta:
        ordering = ['-created_at']


class Event(models.Model):
    TICKET_TYPE_CHOICES = [
        ('General Admission', 'General Admission'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    venue = models.CharField(max_length=255, blank=True)
    age = models.CharField(max_length=50, blank=True)
    image = models.ImageField(upload_to='events/', blank=True)
    date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)

    # Ticket fields (embedded on the Event model)
    ticket_type = models.CharField(max_length=50, choices=TICKET_TYPE_CHOICES, default='General Admission')
    available_tickets = models.PositiveIntegerField(default=0)
    max_per_order = models.PositiveIntegerField(default=1)
    price_per_ticket = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.date})"

    class Meta:
        ordering = ['-created_at']

class Banner(models.Model):
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to='banners/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return self.title




class Singer(models.Model):
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    bio = models.TextField()
    image = models.ImageField(upload_to='singers/')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class AboutUs(models.Model):
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"About Us - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"



class PrivecyPolicy(models.Model):
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Privacy Policy - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"



class TremsAndCondition(models.Model):
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Terms and Conditions - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

