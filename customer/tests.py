# Empty tests file for the customer app
from django.test import TestCase
from django.contrib.auth.models import User
from .models import Customer


class CustomerRegistrationTestCase(TestCase):
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'password': 'testpass123',
            'confirm_password': 'testpass123',
            'full_name': 'Test User',
            'phone_number': '1234567890',
            'gender': 'M',
            'date_of_birth': '1990-01-01',
        }

    def test_customer_registration(self):
        """Test customer registration"""
        pass
