import hashlib
import hmac
import json
from io import BytesIO
from decimal import Decimal
from unittest.mock import patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from cart.models import Cart, CartItem
from catalog.models import Category, Product
from .models import CheckoutAttempt, PaymentTransaction
from .services import _request_json


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


class PaystackCheckoutTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='paystack-buyer', email='buyer@example.com',
            password='safe-password',
        )
        category = Category.objects.create(name='Phones', slug='phones-paystack')
        self.product = Product.objects.create(
            category=category, name='Test Phone', slug='test-phone-paystack',
            price='100.00', stock_quantity=5,
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.client.force_login(self.user)
        self.payload = {
            'provider': 'paystack', 'method': 'mobile_money',
            'billing_name': 'Paystack Buyer',
            'billing_email': 'buyer@example.com',
            'address': '1 Main Street', 'city': 'Accra',
            'postal_code': 'GA1', 'country': 'Ghana',
        }

    @override_settings(PAYSTACK_SECRET_KEY='sk_test_paystack')
    @patch('orders.services._request_json')
    def test_checkout_initializes_paystack_on_server(self, request_json):
        request_json.return_value = {
            'status': True,
            'data': {
                'reference': 'paystack-reference-1',
                'authorization_url': 'https://checkout.paystack.com/access-code',
            },
        }
        response = self.client.post(
            reverse('hosted-payment'), json.dumps(self.payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['provider'], 'paystack')
        self.assertEqual(
            response.data['checkout_url'],
            'https://checkout.paystack.com/access-code',
        )
        transaction = PaymentTransaction.objects.get()
        self.assertEqual(transaction.provider_reference, 'paystack-reference-1')
        sent = request_json.call_args.kwargs
        self.assertEqual(sent['data']['currency'], 'GHS')
        self.assertEqual(sent['data']['channels'], ['mobile_money'])
        self.assertEqual(sent['data']['amount'], int(transaction.provider_amount * 100))
        self.assertNotIn('sk_test_paystack', str(response.data))

    @override_settings(PAYSTACK_SECRET_KEY='sk_test_paystack')
    @patch('orders.services._request_json')
    def test_invalid_paystack_initialization_does_not_create_transaction(self, request_json):
        request_json.return_value = {'status': False, 'message': 'Rejected'}
        response = self.client.post(
            reverse('hosted-payment'), json.dumps(self.payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PaymentTransaction.objects.exists())
        attempt = CheckoutAttempt.objects.get()
        self.assertEqual(attempt.status, CheckoutAttempt.Status.FAILED)

    @override_settings(PAYSTACK_SECRET_KEY='sk_test_paystack')
    @patch('orders.views.send_order_confirmation')
    @patch('orders.views.generate_invoice_pdf')
    def test_signed_success_webhook_fulfills_once(
        self, generate_invoice_pdf, send_order_confirmation,
    ):
        from orders.services import _create_payment_attempt
        attempt = _create_payment_attempt(self.user, {
            key: value for key, value in self.payload.items()
            if key not in {'provider', 'method'}
        })
        PaymentTransaction.objects.create(
            checkout=attempt, provider='paystack', method='mobile_money',
            provider_reference='paystack-reference-2', status='pending',
            store_amount=attempt.total, store_currency='GHS',
            provider_amount=attempt.total, provider_currency='GHS',
        )
        event = {
            'event': 'charge.success',
            'data': {
                'reference': 'paystack-reference-2', 'status': 'success',
                'amount': int(attempt.total * 100), 'currency': 'GHS',
                'metadata': {'checkout_id': str(attempt.pk)},
                'authorization': {'brand': 'visa'},
            },
        }
        body = json.dumps(event, separators=(',', ':')).encode()
        signature = hmac.new(
            b'sk_test_paystack', body, hashlib.sha512,
        ).hexdigest()
        self.client.logout()
        for _ in range(2):
            response = self.client.post(
                reverse('paystack-webhook'), body,
                content_type='application/json',
                HTTP_X_PAYSTACK_SIGNATURE=signature,
            )
            self.assertEqual(response.status_code, 200)
        attempt.refresh_from_db()
        self.product.refresh_from_db()
        transaction = PaymentTransaction.objects.get(checkout=attempt)
        self.assertEqual(attempt.status, CheckoutAttempt.Status.FULFILLED)
        self.assertEqual(transaction.status, PaymentTransaction.Status.PAID)
        self.assertEqual(transaction.card_brand, 'visa')
        self.assertEqual(self.product.stock_quantity, 4)
        self.assertEqual(attempt.user.orders.count(), 1)

    @override_settings(PAYSTACK_SECRET_KEY='sk_test_paystack')
    def test_webhook_rejects_invalid_signature(self):
        response = self.client.post(
            reverse('paystack-webhook'), b'{}',
            content_type='application/json',
            HTTP_X_PAYSTACK_SIGNATURE='invalid',
        )
        self.assertEqual(response.status_code, 400)

    @patch('orders.services.urlopen')
    def test_paystack_error_message_is_returned_without_secrets(self, urlopen):
        urlopen.side_effect = HTTPError(
            'https://api.paystack.co/transaction/initialize', 400,
            'Bad Request', {}, BytesIO(json.dumps({
                'status': False,
                'message': 'Currency not supported by integration.',
            }).encode()),
        )
        with self.assertRaisesMessage(
            Exception, 'Currency not supported by integration.'
        ):
            _request_json(
                'https://api.paystack.co/transaction/initialize',
                method='POST', data={'amount': 100},
            )
