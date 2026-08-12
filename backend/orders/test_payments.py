from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CheckoutAttempt, PaymentTransaction


class StaffPaymentApiTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username='paymentstaff', password='safe-password', is_staff=True,
        )
        self.customer = get_user_model().objects.create_user(
            username='buyer', password='safe-password',
        )
        self.attempt = CheckoutAttempt.objects.create(
            user=self.customer, subtotal='90.00', discount='0.00',
            shipping='5.00', tax='5.00', total='100.00', currency='GHS',
            billing_name='Buyer', billing_email='buyer@example.com',
            address='1 Main Street', city='Accra', postal_code='GA1',
            country='Ghana',
        )
        self.payment = PaymentTransaction.objects.create(
            checkout=self.attempt, provider='paystack', method='mobile_money',
            provider_reference='provider-reference', status='paid',
            store_amount='100.00', store_currency='GHS',
            provider_amount='100.00', provider_currency='GHS',
            paid_at='2026-08-12T00:00:00Z',
        )

    def test_staff_lists_transactions_and_reports_by_currency(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('staff-payment-transactions'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['provider'], 'paystack')
        report = self.client.get(reverse('staff-payment-reports'))
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.data['currencies'][0]['currency'], 'GHS')
        self.assertEqual(report.data['currencies'][0]['gross_revenue'], Decimal('100.00'))

    def test_payment_admin_endpoints_require_staff(self):
        self.client.force_login(self.customer)
        for name in ('staff-payment-transactions', 'staff-payment-methods', 'staff-payment-reports'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    @override_settings(
        STRIPE_SECRET_KEY='', PAYSTACK_SECRET_KEY='paystack-test',
        PAYPAL_CLIENT_ID='', PAYPAL_CLIENT_SECRET='',
    )
    def test_public_method_discovery_returns_enabled_methods_without_secrets(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('payment-methods'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 4)
        self.assertEqual(
            {item['provider'] for item in response.data['results']},
            {'paystack', 'store_credit'},
        )
        self.assertNotIn('paystack-test', str(response.data))
