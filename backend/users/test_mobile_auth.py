from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient, APITestCase


User = get_user_model()
PASSWORD = 'A-long-safe-password-482!'
INVALID_CREDENTIALS = 'Invalid email or password.'


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MOBILE_APP_BASE_URL='https://mobile.ecco.example',
)
class MobileAuthenticationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password=PASSWORD,
        )

    def login(self, email='alice@example.com', password=PASSWORD):
        return self.client.post(
            reverse('mobile-token'),
            {'email': email, 'password': password},
            format='json',
        )

    def test_mobile_registration_requires_no_csrf_and_returns_no_tokens(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(
            reverse('mobile-register'),
            {
                'username': 'bob',
                'email': 'bob@example.com',
                'password': PASSWORD,
                'confirm_password': PASSWORD,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('password', response.data)
        self.assertNotIn('access', response.data)
        self.assertNotIn('refresh', response.data)
        self.assertTrue(User.objects.get(username='bob').check_password(PASSWORD))

    def test_mobile_registration_reuses_backend_validation(self):
        response = self.client.post(
            reverse('mobile-register'),
            {
                'username': 'bo',
                'email': 'ALICE@example.com',
                'password': 'short',
                'confirm_password': 'different',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
        self.assertIn('email', response.data)
        self.assertNotIn(PASSWORD, str(response.data))

    def test_mobile_login_returns_tokens_user_and_expiry_information(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['access_expires_in'], 900)
        self.assertEqual(response.data['refresh_expires_in'], 2592000)
        self.assertEqual(response.data['user']['email'], self.user.email)
        self.assertNotIn('password', str(response.data))

        authorized = APIClient()
        authorized.credentials(
            HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}'
        )
        me = authorized.get(reverse('user-me'))
        cart = authorized.get(reverse('cart-detail'))
        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual(me.data['id'], self.user.id)
        self.assertEqual(cart.status_code, status.HTTP_200_OK)

    def test_mobile_login_uses_generic_failure_for_invalid_and_inactive_users(self):
        invalid = self.login(password='incorrect')
        self.user.is_active = False
        self.user.save(update_fields=('is_active',))
        inactive = self.login()
        self.assertEqual(invalid.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(inactive.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(invalid.data, inactive.data)

    def test_mobile_login_is_throttled(self):
        responses = [
            self.login(email='missing@example.com', password='incorrect')
            for _ in range(11)
        ]
        self.assertEqual(
            responses[-1].status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    def test_refresh_rotates_and_blacklists_previous_refresh_token(self):
        original = self.login().data['refresh']
        refreshed = self.client.post(
            reverse('mobile-token-refresh'),
            {'refresh': original},
            format='json',
        )
        self.assertEqual(refreshed.status_code, status.HTTP_200_OK)
        self.assertIn('refresh', refreshed.data)
        self.assertNotEqual(original, refreshed.data['refresh'])
        replay = self.client.post(
            reverse('mobile-token-refresh'),
            {'refresh': original},
            format='json',
        )
        self.assertEqual(replay.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_is_idempotent_for_a_recognized_refresh_token(self):
        refresh = self.login().data['refresh']
        first = self.client.post(
            reverse('mobile-logout'), {'refresh': refresh}, format='json'
        )
        second = self.client.post(
            reverse('mobile-logout'), {'refresh': refresh}, format='json'
        )
        malformed = self.client.post(
            reverse('mobile-logout'), {'refresh': 'not-a-token'}, format='json'
        )
        self.assertEqual(first.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(second.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(malformed.status_code, status.HTTP_400_BAD_REQUEST)

    def test_staff_dashboard_rejects_jwt_but_accepts_staff_session(self):
        access = self.login().data['access']
        self.user.is_staff = True
        self.user.save(update_fields=('is_staff',))
        jwt_client = APIClient()
        jwt_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        denied = jwt_client.get(reverse('staff-customer-list'))
        self.assertEqual(denied.status_code, status.HTTP_401_UNAUTHORIZED)

        session_client = APIClient()
        session_client.force_login(self.user)
        allowed = session_client.get(reverse('staff-customer-list'))
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)

    def test_staff_accounts_cannot_obtain_mobile_tokens(self):
        self.user.is_staff = True
        self.user.save(update_fields=('is_staff',))
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'], INVALID_CREDENTIALS)

    def test_mobile_password_reset_is_generic_and_uses_mobile_link(self):
        known = self.client.post(
            reverse('mobile-password-reset'),
            {'email': self.user.email},
            format='json',
        )
        unknown = self.client.post(
            reverse('mobile-password-reset'),
            {'email': 'missing@example.com'},
            format='json',
        )
        self.assertEqual(known.status_code, status.HTTP_200_OK)
        self.assertEqual(known.data, unknown.data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            'https://mobile.ecco.example/reset-password/',
            mail.outbox[0].body,
        )

    def test_mobile_reset_changes_password_once_and_revokes_existing_jwt(self):
        access = self.login().data['access']
        credentials = {
            'uid': urlsafe_base64_encode(force_bytes(self.user.pk)),
            'token': default_token_generator.make_token(self.user),
            'new_password': 'Another-safe-password-593!',
            'confirm_password': 'Another-safe-password-593!',
        }
        response = self.client.post(
            reverse('mobile-password-reset-confirm'),
            credentials,
            format='json',
        )
        reused = self.client.post(
            reverse('mobile-password-reset-confirm'),
            credentials,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(reused.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(
            self.user.check_password('Another-safe-password-593!')
        )

        authorized = APIClient()
        authorized.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        self.assertEqual(
            authorized.get(reverse('user-me')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
