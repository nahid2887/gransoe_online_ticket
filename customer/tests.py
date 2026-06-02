from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken


class LogoutTests(APITestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(username="testuser@example.com", email="testuser@example.com", password="testpassword")
        self.logout_url = reverse('customer:customer-logout')

    def test_logout_single_session_via_body(self):
        # Generate tokens
        refresh = RefreshToken.for_user(self.user)
        refresh_str = str(refresh)
        
        # Ensure outstanding token exists in the db
        self.assertTrue(OutstandingToken.objects.filter(token=refresh_str).exists())
        self.assertEqual(BlacklistedToken.objects.count(), 0)

        # Call logout with refresh token in body
        response = self.client.post(self.logout_url, {"refresh_token": refresh_str})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Logout successful")
        
        # Cookie should be deleted
        self.assertIn("refresh_token", response.cookies)
        self.assertEqual(response.cookies["refresh_token"].value, "")

        # Verify token is blacklisted
        self.assertEqual(BlacklistedToken.objects.count(), 1)
        self.assertTrue(BlacklistedToken.objects.filter(token__token=refresh_str).exists())

    def test_logout_single_session_via_cookie(self):
        # Generate tokens
        refresh = RefreshToken.for_user(self.user)
        refresh_str = str(refresh)
        
        # Set refresh token cookie
        self.client.cookies['refresh_token'] = refresh_str

        # Call logout with empty body
        response = self.client.post(self.logout_url, {})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Logout successful")
        
        # Cookie should be deleted
        self.assertEqual(response.cookies["refresh_token"].value, "")

        # Verify token is blacklisted
        self.assertTrue(BlacklistedToken.objects.filter(token__token=refresh_str).exists())

    def test_logout_all_devices_requires_auth(self):
        # Unauthenticated request for all devices logout should fail
        response = self.client.post(self.logout_url, {"all_devices": True})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_all_devices_authenticated(self):
        # Create multiple tokens for the user simulating multiple logins
        refresh1 = RefreshToken.for_user(self.user)
        refresh2 = RefreshToken.for_user(self.user)
        
        refresh1_str = str(refresh1)
        refresh2_str = str(refresh2)

        # Ensure outstanding tokens are created
        self.assertTrue(OutstandingToken.objects.filter(token=refresh1_str).exists())
        self.assertTrue(OutstandingToken.objects.filter(token=refresh2_str).exists())
        self.assertEqual(BlacklistedToken.objects.count(), 0)

        # Authenticate client using the access token
        access_token = str(refresh1.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')

        # Call logout with all_devices=True
        response = self.client.post(self.logout_url, {"all_devices": True})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Logged out from all devices successfully.")

        # Both tokens should be blacklisted
        self.assertEqual(BlacklistedToken.objects.count(), 2)
        self.assertTrue(BlacklistedToken.objects.filter(token__token=refresh1_str).exists())
        self.assertTrue(BlacklistedToken.objects.filter(token__token=refresh2_str).exists())

    def test_logout_invalid_refresh_token_does_not_fail(self):
        # An invalid refresh token should not return 400 or 500, but rather return 200 OK (idempotent)
        response = self.client.post(self.logout_url, {"refresh_token": "invalid_token"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Logout successful")
        self.assertEqual(response.cookies["refresh_token"].value, "")
