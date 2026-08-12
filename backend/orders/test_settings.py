from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from catalog.models import Category, Product
from .models import Order, StoreConfiguration
from .services import calculate_checkout_totals


User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class StaffSettingsApiTests(APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            'owner', 'owner@example.com', 'secret-pass',
        )
        self.staff = User.objects.create_user(
            'manager', 'manager@example.com', 'secret-pass', is_staff=True,
        )
        self.customer = User.objects.create_user('customer', password='secret-pass')

    def test_store_settings_are_singleton_and_superuser_can_update(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(
            reverse('staff-store-settings'),
            {'store_name': 'New Store', 'tax_label': 'vat', 'tax_rate': '0.15000'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(StoreConfiguration.objects.count(), 1)
        configuration = StoreConfiguration.load()
        self.assertEqual(configuration.store_name, 'New Store')
        self.assertEqual(configuration.tax_rate, Decimal('0.15000'))

    def test_store_logo_validation_rejects_non_image(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(
            reverse('staff-store-settings'),
            {'logo': SimpleUploadedFile('logo.txt', b'not an image', 'text/plain')},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('logo', response.data)

    @override_settings(STORE_SHIPPING_FEE='0', STORE_FREE_SHIPPING_THRESHOLD='0')
    def test_configured_tax_affects_new_quotes_not_existing_orders(self):
        category = Category.objects.create(name='Books', slug='settings-books')
        product = Product.objects.create(
            category=category, name='Book', slug='settings-book',
            price=Decimal('100.00'), stock_quantity=2,
        )
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        configuration = StoreConfiguration.load()
        configuration.tax_rate = Decimal('0.10000')
        configuration.save()
        existing = Order.objects.create(
            user=self.customer, subtotal=100, tax=5, total=105,
        )
        self.assertEqual(calculate_checkout_totals(self.customer)['tax'], Decimal('10.00'))
        configuration.tax_rate = Decimal('0.20000')
        configuration.save()
        existing.refresh_from_db()
        self.assertEqual(existing.tax, Decimal('5.00'))
        self.assertEqual(existing.total, Decimal('105.00'))

    def test_delegated_staff_can_manage_store_but_not_users(self):
        permission = Permission.objects.get(codename='manage_store_settings')
        self.staff.user_permissions.add(permission)
        self.client.force_authenticate(self.staff)
        self.assertEqual(
            self.client.get(reverse('staff-store-settings')).status_code,
            status.HTTP_200_OK,
        )
        self.assertEqual(
            self.client.get(reverse('staff-settings-user-list')).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_ordinary_staff_and_anonymous_users_are_denied(self):
        self.client.force_authenticate(self.staff)
        self.assertEqual(
            self.client.get(reverse('staff-store-settings')).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.get(reverse('staff-store-settings')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_system_settings_never_expose_secrets(self):
        self.client.force_authenticate(self.superuser)
        with self.settings(
            STRIPE_SECRET_KEY='sk_test_do_not_return',
            EMAIL_HOST_PASSWORD='smtp-secret',
        ):
            response = self.client.get(reverse('staff-system-settings'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rendered = str(response.data)
        self.assertNotIn('sk_test_do_not_return', rendered)
        self.assertNotIn('smtp-secret', rendered)
        self.assertTrue(response.data['can_manage_users'])

    def test_superuser_invites_staff_and_assigns_role(self):
        role = Group.objects.create(name='Catalog team')
        self.client.force_authenticate(self.superuser)
        response = self.client.post(
            reverse('staff-settings-user-list'),
            {
                'username': 'newstaff',
                'email': 'newstaff@example.com',
                'role_ids': [role.pk],
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        invited = User.objects.get(username='newstaff')
        self.assertTrue(invited.is_staff)
        self.assertTrue(invited.is_active)
        self.assertFalse(invited.has_usable_password())
        self.assertEqual(list(invited.groups.all()), [role])
        self.assertTrue(response.data['invitation_sent'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/reset-password/', mail.outbox[0].body)

    def test_role_permissions_are_allowlisted_and_used_roles_cannot_be_deleted(self):
        self.client.force_authenticate(self.superuser)
        allowed = Permission.objects.get(codename='manage_store_settings')
        forbidden = Permission.objects.get(codename='change_user')
        rejected = self.client.post(
            reverse('staff-settings-role-list'),
            {'name': 'Unsafe', 'permission_ids': [forbidden.pk]},
            format='json',
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        created = self.client.post(
            reverse('staff-settings-role-list'),
            {'name': 'Store managers', 'permission_ids': [allowed.pk]},
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        role = Group.objects.get(pk=created.data['id'])
        self.staff.groups.add(role)
        response = self.client.delete(
            reverse('staff-settings-role-detail', args=(role.pk,)),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_deactivate_or_reassign_self(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(
            reverse('staff-settings-user-detail', args=(self.superuser.pk,)),
            {'is_active': False},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.patch(
            reverse('staff-settings-user-detail', args=(self.superuser.pk,)),
            {'role_ids': []},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_capability_reports_store_settings_permission(self):
        permission = Permission.objects.get(codename='manage_store_settings')
        self.staff.user_permissions.add(permission)
        self.client.force_authenticate(self.staff)
        response = self.client.get(reverse('user-me'))
        self.assertTrue(response.data['can_manage_settings'])
        self.client.force_authenticate(self.customer)
        response = self.client.get(reverse('user-me'))
        self.assertFalse(response.data['can_manage_settings'])
