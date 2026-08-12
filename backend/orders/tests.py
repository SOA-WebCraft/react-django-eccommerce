import re
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from cart.models import Cart, CartItem
from catalog.models import Category, Product
from invoices.models import Invoice

from .models import CheckoutAttempt, Coupon, Order, OrderItem, PaymentTransaction
from .emails import send_order_confirmation
from .services import fulfill_checkout


User = get_user_model()


class CheckoutApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='secret')
        self.other = User.objects.create_user(username='bob', password='secret')
        category = Category.objects.create(name='Books', slug='books')
        self.product = Product.objects.create(
            category=category,
            name='Django Book',
            slug='django-book',
            price=Decimal('50.00'),
            stock_quantity=5,
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2,
        )
        self.client.force_authenticate(self.user)

    def test_models_are_registered_with_admin(self):
        for model in (Order, OrderItem, Coupon, CheckoutAttempt):
            self.assertIn(model, admin.site._registry)

    def test_orders_receive_unique_ten_character_order_numbers(self):
        first = Order.objects.create(user=self.user, total=Decimal('1.00'))
        second = Order.objects.create(user=self.other, total=Decimal('2.00'))
        self.assertRegex(first.order_number, re.compile(r'^[A-Z0-9]{10}$'))
        self.assertRegex(second.order_number, re.compile(r'^[A-Z0-9]{10}$'))
        self.assertNotEqual(first.order_number, second.order_number)

    def test_quote_uses_server_decimal_totals_and_coupon(self):
        Coupon.objects.create(
            code='SAVE10',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            value=Decimal('10.00'),
        )
        response = self.client.post(
            reverse('checkout-quote'),
            {'coupon_code': 'save10'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subtotal'], Decimal('100.00'))
        self.assertEqual(response.data['discount'], Decimal('10.00'))
        self.assertEqual(response.data['shipping'], Decimal('0.00'))
        self.assertEqual(response.data['tax'], Decimal('6.75'))
        self.assertEqual(response.data['total'], Decimal('96.75'))

    @patch('orders.services.stripe.checkout.Session.create')
    def test_session_snapshots_cart_and_reserves_coupon(self, stripe_create):
        stripe_create.return_value = SimpleNamespace(
            id='cs_test_123',
            url='https://checkout.stripe.test/session',
        )
        coupon = Coupon.objects.create(
            code='FIVE',
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal('5.00'),
            usage_limit=1,
        )
        with self.settings(
            STRIPE_SECRET_KEY='sk_test',
            STORE_CURRENCY='GHS',
            STRIPE_GHS_TO_USD_RATE='0.10',
        ):
            response = self.client.post(
                reverse('checkout-session'),
                {
                    'billing_name': 'Alice Example',
                    'billing_email': 'alice@example.com',
                    'address': '1 Main Street',
                    'city': 'Accra',
                    'postal_code': '10000',
                    'country': 'Ghana',
                    'coupon_code': 'FIVE',
                },
                format='json',
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        attempt = CheckoutAttempt.objects.get()
        self.assertEqual(attempt.items.get().product_name, 'Django Book')
        coupon.refresh_from_db()
        self.assertEqual(coupon.reserved_count, 1)
        self.assertEqual(response.data['checkout_url'], stripe_create.return_value.url)
        price_data = stripe_create.call_args.kwargs['line_items'][0]['price_data']
        self.assertEqual(price_data['currency'], 'usd')
        self.assertEqual(price_data['unit_amount'], 1021)
        payment = PaymentTransaction.objects.get()
        self.assertEqual(payment.store_currency, 'GHS')
        self.assertEqual(payment.provider_currency, 'USD')
        self.assertEqual(payment.exchange_rate, Decimal('0.10'))

    def test_session_rejects_blank_stripe_configuration(self):
        with self.settings(STRIPE_SECRET_KEY=''):
            response = self.client.post(
                reverse('checkout-session'),
                {
                    'billing_name': 'Alice Example',
                    'billing_email': 'alice@example.com',
                    'address': '1 Main Street',
                    'city': 'Accra',
                    'postal_code': '10000',
                    'country': 'Ghana',
                },
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['payment'],
            'Stripe is not configured on the server.',
        )
        self.assertFalse(CheckoutAttempt.objects.exists())

    def test_fulfillment_is_atomic_idempotent_and_clears_cart(self):
        attempt = CheckoutAttempt.objects.create(
            user=self.user,
            subtotal=Decimal('100.00'),
            tax=Decimal('7.50'),
            total=Decimal('107.50'),
            billing_name='Alice',
        )
        attempt.items.create(
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=2,
            line_total=Decimal('100.00'),
        )
        first, refund_needed = fulfill_checkout(attempt.pk, 'pi_test')
        second, duplicate_refund = fulfill_checkout(attempt.pk, 'pi_test')
        self.assertFalse(refund_needed)
        self.assertFalse(duplicate_refund)
        self.assertEqual(first.order_id, second.order_id)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(first.order.status, Order.Status.PROCESSING)
        self.assertEqual(first.order.payment_status, 'paid')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)
        self.assertFalse(self.cart.items.exists())

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        FRONTEND_BASE_URL='http://127.0.0.1:5173',
    )
    def test_purchase_confirmation_email_is_sent_once(self):
        order = Order.objects.create(
            user=self.user,
            status=Order.Status.PROCESSING,
            total=Decimal('50.00'),
            currency='USD',
            payment_status='paid',
            billing_name='Alice Example',
            billing_email='alice@example.com',
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal('50.00'),
            quantity=1,
            line_total=Decimal('50.00'),
        )
        self.assertTrue(send_order_confirmation(order.pk))
        self.assertFalse(send_order_confirmation(order.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['alice@example.com'])
        self.assertIn(order.order_number, mail.outbox[0].subject)
        self.assertIn('Django Book x 1', mail.outbox[0].body)
        self.assertIn('USD 50.00', mail.outbox[0].body)
        self.assertIn(
            f'/account/orders/{order.pk}',
            mail.outbox[0].body,
        )
        order.refresh_from_db()
        self.assertIsNotNone(order.confirmation_email_sent_at)

    @patch('orders.emails.send_mail', side_effect=RuntimeError('SMTP failed'))
    def test_email_failure_does_not_change_order_or_mark_it_sent(self, send_mail):
        order = Order.objects.create(
            user=self.user,
            total=Decimal('50.00'),
            billing_email='alice@example.com',
        )
        with self.assertLogs('orders.emails', level='ERROR'):
            self.assertFalse(send_order_confirmation(order.pk))
        order.refresh_from_db()
        self.assertIsNone(order.confirmation_email_sent_at)
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        send_mail.assert_called_once()

    def test_unavailable_stock_requests_refund_and_preserves_cart(self):
        attempt = CheckoutAttempt.objects.create(
            user=self.user,
            subtotal=Decimal('100.00'),
            total=Decimal('100.00'),
        )
        attempt.items.create(
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=6,
            line_total=Decimal('300.00'),
        )
        attempt, refund_needed = fulfill_checkout(attempt.pk, 'pi_test')
        self.assertTrue(refund_needed)
        self.assertEqual(attempt.status, CheckoutAttempt.Status.REFUND_PENDING)
        self.assertEqual(Order.objects.count(), 0)
        self.assertTrue(self.cart.items.exists())

    def test_order_reads_and_checkout_status_are_owner_scoped(self):
        own = Order.objects.create(user=self.user, total=Decimal('1.00'))
        other = Order.objects.create(user=self.other, total=Decimal('2.00'))
        attempt = CheckoutAttempt.objects.create(
            user=self.other,
            subtotal=Decimal('0.00'),
            discount=Decimal('0.00'),
            shipping=Decimal('0.00'),
            tax=Decimal('0.00'),
            total=Decimal('0.00'),
        )
        listing = self.client.get(reverse('order-list'))
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data['results'][0]['id'], own.pk)
        self.assertEqual(
            listing.data['results'][0]['order_number'],
            own.order_number,
        )
        self.assertNotIn('customer', listing.data['results'][0])
        self.assertEqual(
            self.client.get(reverse('order-detail', args=(other.pk,))).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(reverse('checkout-status', args=(attempt.pk,))).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_staff_can_list_filter_and_retrieve_all_orders(self):
        staff = User.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='secret',
            is_staff=True,
        )
        self.user.email = 'alice@example.com'
        self.user.save(update_fields=('email',))
        own = Order.objects.create(
            user=self.user,
            status=Order.Status.PROCESSING,
            total=Decimal('1.00'),
        )
        other = Order.objects.create(
            user=self.other,
            status=Order.Status.COMPLETED,
            total=Decimal('2.00'),
        )
        self.client.force_authenticate(staff)

        listing = self.client.get(reverse('order-list'))
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data['count'], 2)
        self.assertEqual(
            {item['id'] for item in listing.data['results']},
            {own.pk, other.pk},
        )
        own_result = next(
            item for item in listing.data['results'] if item['id'] == own.pk
        )
        self.assertEqual(own_result['customer'], {
            'id': self.user.pk,
            'username': 'alice',
            'email': 'alice@example.com',
        })

        filtered = self.client.get(
            reverse('order-list'),
            {'status': Order.Status.COMPLETED},
        )
        self.assertEqual(filtered.data['count'], 1)
        self.assertEqual(filtered.data['results'][0]['id'], other.pk)

        detail = self.client.get(reverse('order-detail', args=(own.pk,)))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['customer']['id'], self.user.pk)

    def test_staff_can_advance_order_status_through_api(self):
        staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        order = Order.objects.create(user=self.other, total=Decimal('2.00'))
        self.client.force_authenticate(staff)

        processing = self.client.patch(
            reverse('order-detail', args=(order.pk,)),
            {'status': Order.Status.PROCESSING},
            format='json',
        )
        self.assertEqual(processing.status_code, status.HTTP_200_OK)
        self.assertEqual(processing.data['status'], Order.Status.PROCESSING)
        self.assertEqual(processing.data['customer']['id'], self.other.pk)

        shipped = self.client.patch(
            reverse('order-detail', args=(order.pk,)),
            {
                'status': Order.Status.SHIPPED,
                'tracking_number': 'TRACK123',
            },
            format='json',
        )
        self.assertEqual(shipped.status_code, status.HTTP_200_OK)
        completed = self.client.patch(
            reverse('order-detail', args=(order.pk,)),
            {'status': Order.Status.COMPLETED},
            format='json',
        )
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

    def test_staff_status_update_is_forward_only_and_idempotent(self):
        staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        order = Order.objects.create(user=self.other, total=Decimal('2.00'))
        self.client.force_authenticate(staff)
        url = reverse('order-detail', args=(order.pk,))

        skipped = self.client.patch(
            url,
            {'status': Order.Status.COMPLETED},
            format='json',
        )
        self.assertEqual(skipped.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('status', skipped.data)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

        order.status = Order.Status.PROCESSING
        order.save(update_fields=('status', 'updated_at'))
        same = self.client.patch(
            url,
            {'status': Order.Status.PROCESSING},
            format='json',
        )
        self.assertEqual(same.status_code, status.HTTP_200_OK)

        self.client.patch(
            url,
            {
                'status': Order.Status.SHIPPED,
                'tracking_number': 'TRACK123',
            },
            format='json',
        )
        self.client.patch(
            url,
            {'status': Order.Status.COMPLETED},
            format='json',
        )
        reversed_status = self.client.patch(
            url,
            {'status': Order.Status.PROCESSING},
            format='json',
        )
        self.assertEqual(
            reversed_status.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

    def test_order_status_patch_rejects_nonstaff_and_protected_fields(self):
        order = Order.objects.create(user=self.other, total=Decimal('2.00'))
        url = reverse('order-detail', args=(order.pk,))

        customer = self.client.patch(
            url,
            {'status': Order.Status.PROCESSING},
            format='json',
        )
        self.assertEqual(customer.status_code, status.HTTP_403_FORBIDDEN)

        staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        self.client.force_authenticate(staff)
        protected = self.client.patch(
            url,
            {'status': Order.Status.PROCESSING, 'total': '0.00'},
            format='json',
        )
        self.assertEqual(protected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('total', protected.data)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.total, Decimal('2.00'))

        missing = self.client.patch(
            reverse('order-detail', args=(999999,)),
            {'status': Order.Status.PROCESSING},
            format='json',
        )
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.put(url, {'status': 'processing'}, format='json').status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_order_status_patch_requires_authentication(self):
        order = Order.objects.create(user=self.other, total=Decimal('2.00'))
        self.client.force_authenticate(user=None)
        response = self.client.patch(
            reverse('order-detail', args=(order.pk,)),
            {'status': Order.Status.PROCESSING},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_order_list_remains_paginated(self):
        staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        Order.objects.bulk_create([
            Order(user=self.user, total=Decimal('1.00'))
            for _ in range(21)
        ])
        self.client.force_authenticate(staff)
        response = self.client.get(reverse('order-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 21)
        self.assertEqual(len(response.data['results']), 20)
        self.assertIsNotNone(response.data['next'])

    def test_staff_cannot_access_another_users_checkout_attempt(self):
        staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        attempt = CheckoutAttempt.objects.create(
            user=self.other,
            subtotal=Decimal('0.00'),
            total=Decimal('0.00'),
        )
        self.client.force_authenticate(staff)
        response = self.client.get(
            reverse('checkout-status', args=(attempt.pk,)),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_can_change_only_order_status_in_admin(self):
        staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        order = Order.objects.create(user=self.other, total=Decimal('2.00'))
        self.client.force_authenticate(user=None)
        self.client.force_login(staff)

        changelist = self.client.get(reverse('admin:orders_order_changelist'))
        detail = self.client.get(
            reverse('admin:orders_order_change', args=(order.pk,)),
        )
        self.assertEqual(changelist.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        model_admin = admin.site._registry[Order]
        self.assertTrue(model_admin.has_change_permission(detail.wsgi_request))
        self.assertFalse(model_admin.has_delete_permission(detail.wsgi_request))
        self.assertContains(detail, 'name="status"')
        self.assertNotContains(detail, 'name="total"')

        response = self.client.post(
            reverse('admin:orders_order_change', args=(order.pk,)),
            {
                'status': Order.Status.COMPLETED,
                'items-TOTAL_FORMS': '0',
                'items-INITIAL_FORMS': '0',
                'items-MIN_NUM_FORMS': '0',
                'items-MAX_NUM_FORMS': '1000',
                '_save': 'Save',
            },
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(order.total, Decimal('2.00'))

    @patch('orders.views.generate_invoice_pdf')
    @patch('orders.views.stripe.checkout.Session.retrieve')
    def test_checkout_status_reconciles_paid_stripe_session(
        self,
        retrieve_session,
        generate_invoice_pdf,
    ):
        attempt = CheckoutAttempt.objects.create(
            user=self.user,
            stripe_session_id='cs_test_paid',
            subtotal=Decimal('100.00'),
            tax=Decimal('7.50'),
            total=Decimal('107.50'),
        )
        attempt.items.create(
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=2,
            line_total=Decimal('100.00'),
        )
        retrieve_session.return_value = {
            'payment_status': 'paid',
            'payment_intent': 'pi_status_reconcile',
        }

        with self.settings(STRIPE_SECRET_KEY='sk_test'):
            response = self.client.get(
                reverse('checkout-status', args=(attempt.pk,)),
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], CheckoutAttempt.Status.FULFILLED)
        self.assertIsNotNone(response.data['order_id'])
        self.assertIsNotNone(response.data['invoice'])
        order = Order.objects.get()
        self.assertEqual(order.status, Order.Status.PROCESSING)
        self.assertEqual(order.payment_status, 'paid')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)
        self.assertFalse(self.cart.items.exists())
        generate_invoice_pdf.assert_called_once()

    def test_direct_order_creation_is_retired(self):
        response = self.client.post(reverse('order-list'), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch('orders.views.generate_invoice_pdf')
    @patch('orders.views.stripe.Webhook.construct_event')
    def test_verified_webhook_fulfills_once(
        self,
        construct_event,
        generate_invoice_pdf,
    ):
        attempt = CheckoutAttempt.objects.create(
            user=self.user,
            subtotal=Decimal('100.00'),
            tax=Decimal('7.50'),
            total=Decimal('107.50'),
        )
        attempt.items.create(
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=2,
            line_total=Decimal('100.00'),
        )
        construct_event.return_value = {
            'type': 'checkout.session.completed',
            'data': {'object': {
                'metadata': {'checkout_id': str(attempt.pk)},
                'payment_status': 'paid',
                'payment_intent': 'pi_test',
            }},
        }
        self.client.force_authenticate(user=None)
        for _ in range(2):
            response = self.client.post(
                reverse('stripe-webhook'),
                b'{}',
                content_type='application/json',
                HTTP_STRIPE_SIGNATURE='valid',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(generate_invoice_pdf.call_count, 2)

    @patch('orders.views.stripe.Webhook.construct_event')
    def test_invalid_webhook_signature_is_rejected(self, construct_event):
        construct_event.side_effect = ValueError
        self.client.force_authenticate(user=None)
        response = self.client.post(
            reverse('stripe-webhook'),
            b'{}',
            content_type='application/json',
            HTTP_STRIPE_SIGNATURE='invalid',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_checkout_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(reverse('checkout-quote'), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.get(reverse('order-list')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class StaffAnalyticsApiTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='analyst', password='secret', is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='customer', password='secret',
        )
        self.other_customer = User.objects.create_user(
            username='customer-two', password='secret',
        )
        category = Category.objects.create(name='Phones', slug='phones')
        self.low_stock_product = Product.objects.create(
            category=category,
            name='Low Stock Phone',
            slug='low-stock-phone',
            price=Decimal('100.00'),
            stock_quantity=3,
        )
        self.other_product = Product.objects.create(
            category=category,
            name='Popular Phone',
            slug='popular-phone',
            price=Decimal('50.00'),
            stock_quantity=20,
        )
        paid = Order.objects.create(
            user=self.customer,
            status=Order.Status.PROCESSING,
            total=Decimal('200.00'),
            payment_status='paid',
        )
        OrderItem.objects.create(
            order=paid,
            product=self.other_product,
            product_name=self.other_product.name,
            unit_price=Decimal('50.00'),
            quantity=4,
            line_total=Decimal('200.00'),
        )
        Order.objects.create(
            user=self.other_customer,
            status=Order.Status.PENDING,
            total=Decimal('75.00'),
            payment_status='unpaid',
        )

    def test_staff_receives_complete_analytics(self):
        self.client.force_authenticate(self.staff)
        response = self.client.get(reverse('staff-analytics'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['total_revenue'], Decimal('200.00'))
        self.assertEqual(response.data['summary']['paid_orders'], 1)
        self.assertEqual(response.data['summary']['total_orders'], 2)
        self.assertEqual(response.data['summary']['customers'], 2)
        self.assertEqual(
            {row['status']: row['count'] for row in response.data['orders_by_status']},
            {
                'pending': 1,
                'processing': 1,
                'shipped': 0,
                'delivered': 0,
                'cancelled': 0,
            },
        )
        self.assertEqual(len(response.data['daily_sales']), 30)
        self.assertEqual(response.data['daily_sales'][-1]['revenue'], Decimal('200.00'))
        self.assertEqual(response.data['top_products'][0]['quantity_sold'], 4)
        self.assertEqual(response.data['top_products'][0]['product_name'], 'Popular Phone')
        self.assertEqual(response.data['low_stock_products'][0]['name'], 'Low Stock Phone')

    def test_analytics_excludes_unpaid_revenue_and_requires_staff(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(
            self.client.get(reverse('staff-analytics')).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(reverse('staff-analytics')).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )


class OrderLifecycleApiTests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='fulfillment', password='secret', is_staff=True,
        )
        self.customer = User.objects.create_user(
            username='buyer', email='buyer@example.com', password='secret',
        )
        self.order = Order.objects.create(
            user=self.customer,
            status=Order.Status.PROCESSING,
            total=Decimal('125.00'),
            payment_status='paid',
            stripe_payment_intent='pi_lifecycle',
            billing_email='buyer@example.com',
        )

    def test_shipping_requires_tracking_and_lifecycle_is_strict(self):
        self.client.force_authenticate(self.staff)
        url = reverse('order-detail', args=(self.order.pk,))
        missing = self.client.patch(
            url, {'status': Order.Status.SHIPPED}, format='json',
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        shipped = self.client.patch(
            url,
            {'status': Order.Status.SHIPPED, 'tracking_number': 'TRACK-100'},
            format='json',
        )
        self.assertEqual(shipped.status_code, status.HTTP_200_OK)
        self.assertEqual(shipped.data['tracking_number'], 'TRACK-100')
        delivered = self.client.patch(
            url, {'status': Order.Status.COMPLETED}, format='json',
        )
        self.assertEqual(delivered.status_code, status.HTTP_200_OK)
        self.assertEqual(len(delivered.data['timeline']), 2)
        cancelled = self.client.patch(
            url, {'status': Order.Status.CANCELLED}, format='json',
        )
        self.assertEqual(cancelled.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_can_request_return_after_delivery_and_staff_can_approve(self):
        self.order.status = Order.Status.COMPLETED
        self.order.save(update_fields=('status',))
        self.client.force_authenticate(self.customer)
        created = self.client.post(
            reverse('customer-return-request', args=(self.order.pk,)),
            {'reason': 'The product arrived damaged.'},
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        duplicate = self.client.post(
            reverse('customer-return-request', args=(self.order.pk,)),
            {'reason': 'I am requesting this return again.'},
            format='json',
        )
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.client.force_authenticate(self.staff)
        approved = self.client.patch(
            reverse('staff-return-detail', args=(created.data['id'],)),
            {'status': 'approved', 'staff_note': 'Return authorized.'},
            format='json',
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        self.assertEqual(approved.data['status'], 'approved')

    @patch('orders.services.stripe.Refund.create')
    def test_staff_full_refund_updates_payment_once(self, stripe_refund):
        stripe_refund.return_value = SimpleNamespace(id='re_test_123')
        self.client.force_authenticate(self.staff)
        with self.settings(STRIPE_SECRET_KEY='sk_test'):
            first = self.client.post(
                reverse('staff-order-refund', args=(self.order.pk,)),
                {},
                format='json',
            )
            second = self.client.post(
                reverse('staff-order-refund', args=(self.order.pk,)),
                {},
                format='json',
            )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data['status'], 'approved')
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'refunded')
        stripe_refund.assert_called_once()

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        DEFAULT_FROM_EMAIL='store@example.com',
    )
    def test_staff_can_send_status_email(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            reverse('staff-order-email', args=(self.order.pk,)),
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.order.order_number, mail.outbox[0].subject)
