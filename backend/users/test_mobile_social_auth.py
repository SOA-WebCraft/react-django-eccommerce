from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .mobile_views import exchange_code_hash
from .models import MobileSocialExchange, SocialIdentity


User = get_user_model()
REDIRECT_URI = 'eccostore://auth/social'
SOCIAL_SETTINGS = {
    'google': {'client_id': 'google-client', 'client_secret': 'google-secret'},
    'apple': {},
    'facebook': {},
    'linkedin': {},
}


@override_settings(
    SOCIAL_AUTH=SOCIAL_SETTINGS,
    MOBILE_SOCIAL_REDIRECT_URIS=(REDIRECT_URI,),
    MOBILE_SOCIAL_CALLBACK_BASE_URL='https://ecco-storefront.vercel.app',
)
class MobileSocialAuthenticationTests(APITestCase):
    def setUp(self):
        cache.clear()

    def _set_mobile_session(self):
        session = self.client.session
        session['mobile_social_redirect_uri'] = REDIRECT_URI
        session.save()

    def _complete_google_callback(self, profile=None):
        self._set_mobile_session()
        client = Mock()
        client.authorize_access_token.return_value = {'access_token': 'provider-token'}
        profile = profile or {
            'sub': 'google-customer-1',
            'email': 'customer@example.com',
            'email_verified': True,
            'given_name': 'Mobile',
            'family_name': 'Customer',
        }
        with (
            patch('users.mobile_views.oauth_client', return_value=client),
            patch('users.mobile_views.profile_from_token', return_value=profile),
        ):
            return self.client.get(reverse('mobile-social-google-callback'))

    def test_start_requires_allowlisted_redirect_and_uses_mobile_callback(self):
        rejected = self.client.get(
            reverse('mobile-social-google'),
            {'redirect_uri': 'https://attacker.example/callback'},
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('redirect_uri', rejected.data)

        client = Mock()
        client.authorize_redirect.return_value = HttpResponseRedirect(
            'https://accounts.google.com/o/oauth2/auth'
        )
        with patch('users.mobile_views.oauth_client', return_value=client):
            self.client.get(
                reverse('mobile-social-google'),
                {'redirect_uri': REDIRECT_URI},
            )
        client.authorize_redirect.assert_called_once()
        self.assertEqual(
            client.authorize_redirect.call_args.args[1],
            'https://ecco-storefront.vercel.app/api/mobile/auth/social/google/callback/',
        )
        self.assertEqual(
            self.client.session['mobile_social_redirect_uri'],
            REDIRECT_URI,
        )

    @override_settings(SOCIAL_AUTH={
        'google': {'client_id': '', 'client_secret': ''},
        'apple': {}, 'facebook': {}, 'linkedin': {},
    })
    def test_start_reports_unconfigured_google(self):
        response = self.client.get(
            reverse('mobile-social-google'),
            {'redirect_uri': REDIRECT_URI},
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_callback_returns_only_one_time_code_and_exchange_returns_jwt(self):
        callback = self._complete_google_callback()
        self.assertEqual(callback.status_code, status.HTTP_302_FOUND)
        query = parse_qs(urlparse(callback['Location']).query)
        self.assertEqual(callback['Location'].split('?')[0], REDIRECT_URI)
        self.assertIn('code', query)
        self.assertNotIn('access', query)
        self.assertNotIn('refresh', query)

        raw_code = query['code'][0]
        exchange_record = MobileSocialExchange.objects.get()
        self.assertNotEqual(exchange_record.code_hash, raw_code)
        self.assertEqual(exchange_record.code_hash, exchange_code_hash(raw_code))

        csrf_client = APIClient(enforce_csrf_checks=True)
        exchanged = csrf_client.post(
            reverse('mobile-social-exchange'),
            {'code': raw_code},
            format='json',
        )
        self.assertEqual(exchanged.status_code, status.HTTP_200_OK)
        self.assertIn('access', exchanged.data)
        self.assertIn('refresh', exchanged.data)
        self.assertEqual(exchanged.data['access_expires_in'], 900)
        self.assertEqual(exchanged.data['refresh_expires_in'], 2592000)
        self.assertEqual(exchanged.data['user']['email'], 'customer@example.com')
        self.assertNotIn(raw_code, str(exchanged.data))

        authorized = APIClient()
        authorized.credentials(
            HTTP_AUTHORIZATION=f'Bearer {exchanged.data["access"]}'
        )
        self.assertEqual(
            authorized.get(reverse('user-me')).status_code,
            status.HTTP_200_OK,
        )

    def test_exchange_code_is_single_use_and_expired_codes_are_rejected(self):
        callback = self._complete_google_callback()
        raw_code = parse_qs(urlparse(callback['Location']).query)['code'][0]
        first = self.client.post(
            reverse('mobile-social-exchange'), {'code': raw_code}, format='json'
        )
        replay = self.client.post(
            reverse('mobile-social-exchange'), {'code': raw_code}, format='json'
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(replay.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('code', replay.data)

        user = User.objects.get(email='customer@example.com')
        expired_code = 'expired-exchange-code'
        MobileSocialExchange.objects.create(
            user=user,
            provider=SocialIdentity.Provider.GOOGLE,
            code_hash=exchange_code_hash(expired_code),
            redirect_uri=REDIRECT_URI,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        expired = self.client.post(
            reverse('mobile-social-exchange'),
            {'code': expired_code},
            format='json',
        )
        self.assertEqual(expired.status_code, status.HTTP_400_BAD_REQUEST)

    def test_callback_rejects_staff_and_redirects_safe_errors(self):
        staff = User.objects.create_user(
            username='staff',
            email='staff@example.com',
            is_staff=True,
        )
        SocialIdentity.objects.create(
            user=staff,
            provider=SocialIdentity.Provider.GOOGLE,
            subject='staff-google-id',
            email=staff.email,
        )
        callback = self._complete_google_callback({
            'sub': 'staff-google-id',
            'email': staff.email,
            'email_verified': True,
        })
        query = parse_qs(urlparse(callback['Location']).query)
        self.assertEqual(query, {'error': ['account_unavailable']})
        self.assertFalse(MobileSocialExchange.objects.exists())

        self._set_mobile_session()
        denied = self.client.get(
            reverse('mobile-social-google-callback'),
            {'error': 'access_denied'},
        )
        self.assertEqual(
            parse_qs(urlparse(denied['Location']).query),
            {'error': ['access_denied']},
        )

    def test_callback_requires_a_valid_mobile_session(self):
        response = self.client.get(reverse('mobile-social-google-callback'))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_exchange_is_throttled(self):
        responses = [
            self.client.post(
                reverse('mobile-social-exchange'),
                {'code': f'invalid-{index}'},
                format='json',
            )
            for index in range(21)
        ]
        self.assertEqual(
            responses[-1].status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )
