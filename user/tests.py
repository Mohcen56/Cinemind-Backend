from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

User = get_user_model()


class CookieAuthenticationSecurityTests(APITestCase):
    def setUp(self):
        # DRF's throttle counters live outside the test database transaction.
        # Clear them so one test's login attempts cannot throttle another test.
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            username="security-test",
            email="security@example.com",
            password="correct horse battery staple",
        )
        self.token = Token.objects.create(user=self.user)

    def issue_csrf_token(self):
        response = self.client.get(reverse("csrf_token"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(settings.CSRF_COOKIE_NAME, response.cookies)
        return response.data["csrfToken"]

    def test_cookie_authenticated_unsafe_request_requires_csrf(self):
        self.client.cookies[settings.AUTH_COOKIE_NAME] = self.token.key

        response = self.client.patch(
            reverse("update_profile"),
            {"username": "blocked-without-csrf"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "security-test")

    def test_cookie_authenticated_unsafe_request_accepts_csrf(self):
        csrf_token = self.issue_csrf_token()
        self.client.cookies[settings.AUTH_COOKIE_NAME] = self.token.key

        response = self.client.patch(
            reverse("update_profile"),
            {"username": "updated-with-csrf"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "updated-with-csrf")

    def test_authorization_header_does_not_require_csrf(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        response = self.client.patch(
            reverse("update_profile"),
            {"username": "header-client"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_requires_csrf_and_sets_secure_cookie(self):
        login_data = {
            "email": self.user.email,
            "password": "correct horse battery staple",
        }
        rejected = self.client.post(reverse("login"), login_data, format="json")
        self.assertEqual(rejected.status_code, status.HTTP_403_FORBIDDEN)

        csrf_token = self.issue_csrf_token()
        response = self.client.post(
            reverse("login"),
            login_data,
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        auth_cookie = response.cookies[settings.AUTH_COOKIE_NAME]
        self.assertTrue(auth_cookie["httponly"])
        self.assertEqual(auth_cookie["samesite"], settings.AUTH_COOKIE_SAMESITE)

    @override_settings(CSRF_TRUSTED_ORIGINS=["http://localhost:3000"])
    def test_login_accepts_csrf_from_trusted_frontend_origin(self):
        csrf_token = self.issue_csrf_token()

        response = self.client.post(
            reverse("login"),
            {
                "email": self.user.email,
                "password": "correct horse battery staple",
            },
            format="json",
            HTTP_ORIGIN="http://localhost:3000",
            HTTP_REFERER="http://localhost:3000/login",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_logout_revokes_token_and_clears_cookie(self):
        csrf_token = self.issue_csrf_token()
        self.client.cookies[settings.AUTH_COOKIE_NAME] = self.token.key

        response = self.client.post(
            reverse("logout"),
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())
        self.assertEqual(response.cookies[settings.AUTH_COOKIE_NAME]["max-age"], 0)

    def test_password_change_accepts_frontend_payload_contract(self):
        csrf_token = self.issue_csrf_token()
        self.client.cookies[settings.AUTH_COOKIE_NAME] = self.token.key

        response = self.client.post(
            reverse("change_password"),
            {
                "old_password": "correct horse battery staple",
                "new_password": "new correct horse battery staple",
            },
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new correct horse battery staple"))
