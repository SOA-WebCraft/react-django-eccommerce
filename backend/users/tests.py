from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from .models import Profile, SocialIdentity
from .social_auth import login_or_create_social_user, profile_from_token
from catalog.roles import CATALOG_MANAGERS_GROUP
from orders.models import Order


User = get_user_model()


class UserApiTests(APITestCase):
    def test_social_provider_discovery_does_not_expose_credentials(self):
        response = self.client.get(reverse('user-social-providers'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {item['provider'] for item in response.data['results']},
            {'google', 'apple', 'facebook', 'linkedin'},
        )
        self.assertNotIn('client_secret', str(response.data))

    def test_unconfigured_social_provider_is_unavailable(self):
        response = self.client.get(
            reverse('user-social-login', kwargs={'provider': 'linkedin'})
        )
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_social_identity_creates_and_reuses_user_without_password(self):
        profile = {
            'sub': 'linkedin-member-42',
            'email': 'social@example.com',
            'email_verified': True,
            'given_name': 'Social',
            'family_name': 'Customer',
        }
        user = login_or_create_social_user('linkedin', profile)
        again = login_or_create_social_user('linkedin', profile)
        self.assertEqual(user, again)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.profile.first_name, 'Social')
        self.assertEqual(SocialIdentity.objects.count(), 1)

    def test_social_identity_requires_verified_email(self):
        from .social_auth import SocialAuthError
        with self.assertRaises(SocialAuthError):
            login_or_create_social_user('google', {
                'sub': 'google-42',
                'email': 'unverified@example.com',
                'email_verified': False,
            })

    def test_facebook_profile_is_normalized_for_account_creation(self):
        class FacebookResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    'id': 'facebook-member-42',
                    'email': 'facebook@example.com',
                    'first_name': 'Facebook',
                    'last_name': 'Customer',
                }

        class FacebookClient:
            def get(self, url, token):
                self.url = url
                self.token = token
                return FacebookResponse()

        client = FacebookClient()
        profile = profile_from_token(
            'facebook',
            client,
            {'access_token': 'provider-token'},
        )
        user = login_or_create_social_user('facebook', profile)

        self.assertEqual(profile['sub'], 'facebook-member-42')
        self.assertTrue(profile['email_verified'])
        self.assertEqual(user.email, 'facebook@example.com')
        self.assertEqual(user.profile.first_name, 'Facebook')
        self.assertEqual(user.profile.last_name, 'Customer')
        self.assertTrue(
            SocialIdentity.objects.filter(
                user=user,
                provider=SocialIdentity.Provider.FACEBOOK,
                subject='facebook-member-42',
            ).exists()
        )

    def test_profile_is_created_with_nullable_fields_and_registered_in_admin(self):
        user = User.objects.create_user(username='profile-user', password='safe-password')
        profile = user.profile
        self.assertIsNone(profile.first_name)
        self.assertIsNone(profile.last_name)
        self.assertIsNone(profile.phone)
        self.assertIsNone(profile.address)
        self.assertIn(Profile, admin.site._registry)

    def test_register_hashes_password_and_does_not_expose_it(self):
        response = self.client.post(
            reverse('user-register'),
            {
                'username': 'alice',
                'email': 'alice@example.com',
                'password': 'A-long-safe-password-482!',
                'confirm_password': 'A-long-safe-password-482!',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('password', response.data)
        user = User.objects.get(username='alice')
        self.assertTrue(user.check_password('A-long-safe-password-482!'))

    def test_register_rejects_weak_password(self):
        response = self.client.post(
            reverse('user-register'),
            {
                'username': 'alice',
                'email': 'alice@example.com',
                'password': '123',
                'confirm_password': '123',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)

    def test_register_rejects_duplicate_email_case_insensitively(self):
        User.objects.create_user(
            username='existing',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )
        response = self.client.post(
            reverse('user-register'),
            {
                'username': 'alice',
                'email': 'ALICE@example.com',
                'password': 'A-long-safe-password-482!',
                'confirm_password': 'A-long-safe-password-482!',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_register_validates_every_field_and_password_confirmation(self):
        missing = self.client.post(reverse('user-register'), {}, format='json')
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        for field in ('username', 'email', 'password', 'confirm_password'):
            self.assertIn(field, missing.data)

        mismatch = self.client.post(
            reverse('user-register'),
            {
                'username': 'alice',
                'email': 'alice@example.com',
                'password': 'A-long-safe-password-482!',
                'confirm_password': 'A-different-safe-password-731!',
            },
            format='json',
        )
        self.assertEqual(mismatch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_password', mismatch.data)
        self.assertFalse(User.objects.filter(username='alice').exists())

    def test_email_availability_is_validated_case_insensitively(self):
        User.objects.create_user(
            username='existing',
            email='existing@example.com',
            password='A-long-safe-password-482!',
        )
        existing = self.client.post(
            reverse('user-email-availability'),
            {'email': 'EXISTING@example.com'},
            format='json',
        )
        self.assertEqual(existing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', existing.data)

        available = self.client.post(
            reverse('user-email-availability'),
            {'email': 'available@example.com'},
            format='json',
        )
        self.assertEqual(available.status_code, status.HTTP_200_OK)
        self.assertEqual(available.data, {'available': True})

        invalid = self.client.post(
            reverse('user-email-availability'),
            {'email': 'not-an-email'},
            format='json',
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', invalid.data)

    def test_session_login_and_current_user(self):
        User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )
        csrf_response = self.client.get(reverse('user-csrf'))
        self.assertEqual(csrf_response.status_code, status.HTTP_200_OK)
        login_response = self.client.post(
            reverse('user-login'),
            {
                'email': 'ALICE@example.com',
                'password': 'A-long-safe-password-482!',
            },
            format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('sessionid', self.client.cookies)
        self.assertNotIn('password', login_response.data)
        response = self.client.get(reverse('user-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'alice')
        self.assertFalse(login_response.data['can_manage_orders'])
        self.assertFalse(login_response.data['can_manage_catalog'])
        self.assertFalse(response.data['can_manage_orders'])
        self.assertFalse(response.data['can_manage_catalog'])
        self.assertNotIn('password', response.data)

    def test_staff_login_and_current_user_expose_order_capability(self):
        staff = User.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='A-long-safe-password-482!',
            is_staff=True,
        )
        self.client.get(reverse('user-csrf'))
        login = self.client.post(
            reverse('user-login'),
            {
                'email': 'staff@example.com',
                'password': 'A-long-safe-password-482!',
            },
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertTrue(login.data['can_manage_orders'])
        self.assertFalse(login.data['can_manage_catalog'])
        me = self.client.get(reverse('user-me'))
        self.assertTrue(me.data['can_manage_orders'])
        Group.objects.get(name=CATALOG_MANAGERS_GROUP).user_set.add(staff)
        me = self.client.get(reverse('user-me'))
        self.assertTrue(me.data['can_manage_catalog'])

    def test_login_rotates_existing_session_identifier(self):
        User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )
        session = self.client.session
        session['pre_login_value'] = True
        session.save()
        previous_session_key = session.session_key
        self.client.get(reverse('user-csrf'))

        response = self.client.post(
            reverse('user-login'),
            {
                'email': 'alice@example.com',
                'password': 'A-long-safe-password-482!',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(
            self.client.session.session_key,
            previous_session_key,
        )

    def test_session_logout_invalidates_current_session(self):
        User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )
        self.client.get(reverse('user-csrf'))
        self.client.post(
            reverse('user-login'),
            {
                'email': 'alice@example.com',
                'password': 'A-long-safe-password-482!',
            },
            format='json',
        )
        response = self.client.post(reverse('user-logout'), format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        me_response = self.client.get(reverse('user-me'))
        self.assertEqual(
            me_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_session_login_rejects_invalid_credentials(self):
        User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )
        self.client.get(reverse('user-csrf'))
        response = self.client.post(
            reverse('user-login'),
            {'email': 'alice@example.com', 'password': 'incorrect'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'], 'Invalid email or password.')

    def test_session_login_returns_backend_field_validation_errors(self):
        missing = self.client.post(reverse('user-login'), {}, format='json')
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', missing.data)
        self.assertIn('password', missing.data)

        invalid_email = self.client.post(
            reverse('user-login'),
            {'email': 'not-an-email', 'password': 'secret'},
            format='json',
        )
        self.assertEqual(
            invalid_email.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn('email', invalid_email.data)

    def test_session_login_rejects_ambiguous_legacy_email(self):
        for username in ('alice', 'alice-legacy'):
            User.objects.create_user(
                username=username,
                email='alice@example.com',
                password='A-long-safe-password-482!',
            )
        response = self.client.post(
            reverse('user-login'),
            {
                'email': 'alice@example.com',
                'password': 'A-long-safe-password-482!',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data['detail'], 'Invalid email or password.')

    def test_current_user_requires_authentication(self):
        response = self.client.get(reverse('user-me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_patch_updates_only_supplied_fields_and_clears_blanks(self):
        user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )
        user.profile.first_name = 'Alice'
        user.profile.city = 'Accra'
        user.profile.save(update_fields=('first_name', 'city', 'updated_at'))
        self.client.force_authenticate(user)
        response = self.client.patch(
            reverse('user-me'),
            {'first_name': '', 'phone': '+233 20 000 0000'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.profile.refresh_from_db()
        self.assertIsNone(user.profile.first_name)
        self.assertEqual(user.profile.phone, '+233 20 000 0000')
        self.assertEqual(user.profile.city, 'Accra')
        self.assertIsNone(response.data['first_name'])
        self.assertEqual(response.data['city'], 'Accra')

    def test_email_change_requires_current_password(self):
        user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )
        self.client.force_authenticate(user)
        url = reverse('user-me')
        rejected = self.client.patch(
            url,
            {'email': 'new@example.com'},
            format='json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('current_password', rejected.data)
        user.refresh_from_db()
        self.assertEqual(user.email, 'alice@example.com')
        accepted = self.client.patch(
            url,
            {
                'email': 'new@example.com',
                'current_password': 'A-long-safe-password-482!',
            },
            format='json',
        )
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        self.assertEqual(accepted.data['email'], 'new@example.com')
        self.assertNotIn('current_password', accepted.data)

    def test_email_change_rejects_another_accounts_email(self):
        user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )
        User.objects.create_user(
            username='bob',
            email='bob@example.com',
            password='A-long-safe-password-482!',
        )
        self.client.force_authenticate(user)
        response = self.client.patch(
            reverse('user-me'),
            {
                'email': 'BOB@example.com',
                'current_password': 'A-long-safe-password-482!',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_profile_patch_rejects_protected_fields_and_put(self):
        user = User.objects.create_user(username='alice', password='secret')
        self.client.force_authenticate(user)
        url = reverse('user-me')
        response = self.client.patch(
            url,
            {'username': 'changed', 'is_staff': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)
        self.assertIn('is_staff', response.data)
        user.refresh_from_db()
        self.assertEqual(user.username, 'alice')
        self.assertFalse(user.is_staff)
        self.assertEqual(
            self.client.put(url, {'email': 'x@example.com'}, format='json').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_profile_patch_requires_authentication_and_csrf(self):
        self.assertEqual(
            self.client.patch(reverse('user-me'), {'city': 'Accra'}, format='json').status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        user = User.objects.create_user(username='alice', password='secret')
        csrf_client = APIClient(enforce_csrf_checks=True)
        csrf_client.login(username='alice', password='secret')
        self.assertEqual(
            csrf_client.patch(reverse('user-me'), {'city': 'Accra'}, format='json').status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_login_and_registration_require_csrf(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )

        login = csrf_client.post(
            reverse('user-login'),
            {
                'email': 'alice@example.com',
                'password': 'A-long-safe-password-482!',
            },
            format='json',
        )
        registration = csrf_client.post(
            reverse('user-register'),
            {
                'username': 'bob',
                'email': 'bob@example.com',
                'password': 'A-long-safe-password-482!',
                'confirm_password': 'A-long-safe-password-482!',
            },
            format='json',
        )
        availability = csrf_client.post(
            reverse('user-email-availability'),
            {'email': 'available@example.com'},
            format='json',
        )

        self.assertEqual(login.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            registration.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            availability.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_csrf_cookie_allows_login_and_protects_logout(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )
        csrf_client.get(reverse('user-csrf'))
        token = csrf_client.cookies['csrftoken'].value

        login = csrf_client.post(
            reverse('user-login'),
            {
                'email': 'alice@example.com',
                'password': 'A-long-safe-password-482!',
            },
            format='json',
            HTTP_X_CSRFTOKEN=token,
            HTTP_ORIGIN='http://localhost:5173',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

        missing_csrf = csrf_client.post(
            reverse('user-logout'),
            format='json',
        )
        self.assertEqual(
            missing_csrf.status_code,
            status.HTTP_403_FORBIDDEN,
        )
        rotated_token = csrf_client.cookies['csrftoken'].value
        logout_response = csrf_client.post(
            reverse('user-logout'),
            format='json',
            HTTP_X_CSRFTOKEN=rotated_token,
            HTTP_ORIGIN='http://localhost:5173',
        )
        self.assertEqual(
            logout_response.status_code,
            status.HTTP_204_NO_CONTENT,
        )

    def test_login_rejects_invalid_csrf_token(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )
        csrf_client.get(reverse('user-csrf'))

        response = csrf_client.post(
            reverse('user-login'),
            {
                'email': 'alice@example.com',
                'password': 'A-long-safe-password-482!',
            },
            format='json',
            HTTP_X_CSRFTOKEN='invalid',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    FRONTEND_BASE_URL='http://localhost:5173',
)
class PasswordResetApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='A-long-safe-password-482!',
        )

    def request_reset(self, email='alice@example.com'):
        return self.client.post(
            reverse('user-password-reset'),
            {'email': email},
            format='json',
        )

    def reset_credentials(self):
        return {
            'uid': urlsafe_base64_encode(force_bytes(self.user.pk)),
            'token': default_token_generator.make_token(self.user),
        }

    def test_known_email_receives_frontend_reset_link(self):
        response = self.request_reset()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            'http://localhost:5173/reset-password/',
            mail.outbox[0].body,
        )
        self.assertNotIn('token', response.data)
        self.assertNotIn('email', response.data)

    def test_unknown_inactive_and_unusable_accounts_are_indistinguishable(self):
        inactive = User.objects.create_user(
            username='inactive',
            email='inactive@example.com',
            password='A-long-safe-password-482!',
            is_active=False,
        )
        unusable = User.objects.create_user(
            username='unusable',
            email='unusable@example.com',
        )
        unusable.set_unusable_password()
        unusable.save(update_fields=('password',))
        responses = [
            self.request_reset('missing@example.com'),
            self.request_reset(inactive.email),
            self.request_reset(unusable.email),
        ]
        self.assertTrue(all(item.status_code == 200 for item in responses))
        self.assertEqual(len({item.data['detail'] for item in responses}), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_valid_token_resets_password_and_is_single_use(self):
        credentials = self.reset_credentials()
        payload = {
            **credentials,
            'new_password': 'Another-safe-password-593!',
            'confirm_password': 'Another-safe-password-593!',
        }
        response = self.client.post(
            reverse('user-password-reset-confirm'),
            payload,
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(payload['new_password']))
        reused = self.client.post(
            reverse('user-password-reset-confirm'),
            payload,
            format='json',
        )
        self.assertEqual(reused.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('token', reused.data)

    def test_confirmation_validates_token_match_and_password_strength(self):
        credentials = self.reset_credentials()
        mismatch = self.client.post(
            reverse('user-password-reset-confirm'),
            {
                **credentials,
                'new_password': 'Another-safe-password-593!',
                'confirm_password': 'different',
            },
            format='json',
        )
        self.assertEqual(mismatch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_password', mismatch.data)
        weak = self.client.post(
            reverse('user-password-reset-confirm'),
            {
                **credentials,
                'new_password': '123',
                'confirm_password': '123',
            },
            format='json',
        )
        self.assertEqual(weak.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', weak.data)
        invalid = self.client.post(
            reverse('user-password-reset-confirm'),
            {
                'uid': 'invalid',
                'token': 'invalid',
                'new_password': 'Another-safe-password-593!',
                'confirm_password': 'Another-safe-password-593!',
            },
            format='json',
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('token', invalid.data)

    def test_expired_token_is_rejected(self):
        old_time = datetime.now() - timedelta(hours=2)
        with patch.object(default_token_generator, '_now', return_value=old_time):
            token = default_token_generator.make_token(self.user)
        response = self.client.post(
            reverse('user-password-reset-confirm'),
            {
                'uid': urlsafe_base64_encode(force_bytes(self.user.pk)),
                'token': token,
                'new_password': 'Another-safe-password-593!',
                'confirm_password': 'Another-safe-password-593!',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('token', response.data)

    def test_reset_endpoints_require_csrf(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        request_response = csrf_client.post(
            reverse('user-password-reset'),
            {'email': self.user.email},
            format='json',
        )
        confirm_response = csrf_client.post(
            reverse('user-password-reset-confirm'),
            {
                **self.reset_credentials(),
                'new_password': 'Another-safe-password-593!',
                'confirm_password': 'Another-safe-password-593!',
            },
            format='json',
        )
        self.assertEqual(request_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(confirm_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reset_request_is_throttled(self):
        responses = [self.request_reset('missing@example.com') for _ in range(6)]
        self.assertTrue(all(item.status_code == 200 for item in responses[:5]))
        self.assertEqual(
            responses[-1].status_code,
            status.HTTP_429_TOO_MANY_REQUESTS,
        )


class StaffCustomerApiTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='staff', password='secret', is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='alice',
            email='alice@example.com',
            password='secret',
        )
        profile = self.customer.profile
        profile.first_name = 'Alice'
        profile.last_name = 'Example'
        profile.phone = '+233200000000'
        profile.address = '1 Main Street'
        profile.city = 'Accra'
        profile.country = 'Ghana'
        profile.save()
        Order.objects.create(
            user=self.customer,
            total=Decimal('125.50'),
            payment_status='paid',
        )
        Order.objects.create(
            user=self.customer,
            total=Decimal('40.00'),
            payment_status='unpaid',
        )

    def test_staff_can_list_search_and_retrieve_customer_summary(self):
        self.client.force_authenticate(self.staff)
        listing = self.client.get(
            reverse('staff-customer-list'),
            {'search': 'Alice'},
        )
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data['count'], 1)
        customer = listing.data['results'][0]
        self.assertEqual(customer['name'], 'Alice Example')
        self.assertEqual(customer['orders'], 2)
        self.assertEqual(customer['total_spent'], '125.50')
        self.assertNotIn('password', customer)

        detail = self.client.get(
            reverse('staff-customer-detail', args=(self.customer.pk,)),
        )
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(len(detail.data['order_history']), 2)
        self.assertEqual(detail.data['saved_addresses'][0]['city'], 'Accra')
        self.assertNotIn('is_staff', detail.data)

    def test_customer_endpoints_require_staff_and_exclude_staff_accounts(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(
            self.client.get(reverse('staff-customer-list')).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(reverse('staff-customer-list')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.client.force_authenticate(self.staff)
        listing = self.client.get(reverse('staff-customer-list'))
        self.assertEqual(listing.data['count'], 1)


class ProfileMigrationTests(TransactionTestCase):
    migrate_from = [('users', None)]
    migrate_to = [('users', '0001_initial')]

    def test_migration_backfills_existing_user_names(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state([
            ('auth', '0012_alter_user_first_name_max_length')
        ]).apps
        OldUser = old_apps.get_model('auth', 'User')
        user = OldUser.objects.create(
            username='existing-user',
            first_name='Existing',
            last_name='Customer',
        )
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        new_apps = executor.loader.project_state(self.migrate_to).apps
        Profile = new_apps.get_model('users', 'Profile')
        profile = Profile.objects.get(user_id=user.pk)
        self.assertEqual(profile.first_name, 'Existing')
        self.assertEqual(profile.last_name, 'Customer')
