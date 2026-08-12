from django.conf import settings
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class SessionSecuritySettingsTests(TestCase):
    def test_session_and_csrf_cookie_security_settings(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(settings.SESSION_COOKIE_AGE, 60 * 60 * 8)
        self.assertFalse(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertFalse(settings.SESSION_COOKIE_SECURE)
        self.assertFalse(settings.CSRF_COOKIE_SECURE)
        self.assertIn(
            'http://localhost:5173',
            settings.CSRF_TRUSTED_ORIGINS,
        )
        self.assertIn(
            'http://127.0.0.1:5173',
            settings.CSRF_TRUSTED_ORIGINS,
        )


class StaffAdminTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='A-long-safe-password-482!',
        )
    def test_default_admin_accepts_staff_password_login(self):
        self.assertIsInstance(admin.site._wrapped, AdminSite)
        response = self.client.post(
            reverse('admin:login'),
            {
                'username': 'admin',
                'password': 'A-long-safe-password-482!',
                'next': reverse('admin:index'),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self.client.session['_auth_user_id'],
            str(self.staff.pk),
        )
