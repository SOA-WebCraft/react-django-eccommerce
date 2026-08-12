from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cart.models import Cart, CartItem
from catalog.models import Category, Product

from .models import Coupon, GiftCard, GiftCardTransaction, Promotion
from .services import calculate_checkout_totals, create_checkout_session, fulfill_checkout


class DiscountApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user('discountstaff', password='safe-password', is_staff=True)
        self.user = User.objects.create_user('discountbuyer', password='safe-password')
        self.category = Category.objects.create(name='Phones', slug='phones-discounts')
        self.product = Product.objects.create(
            name='Discount Phone', slug='discount-phone', description='',
            price='100.00', stock_quantity=10, category=self.category,
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=1)

    def test_best_promotion_then_coupon_then_gift_card(self):
        now = timezone.now()
        Promotion.objects.create(name='Store ten', percentage='10', scope='store', starts_at=now - timedelta(hours=1), ends_at=now + timedelta(days=1))
        best = Promotion.objects.create(name='Phone twenty', percentage='20', scope='products', starts_at=now - timedelta(hours=1), ends_at=now + timedelta(days=1))
        best.products.add(self.product)
        Coupon.objects.create(code='save10', discount_type='percentage', value='10')
        card = GiftCard.objects.create(code_hash='hash', masked_code='**** ABCD', initial_balance='20', current_balance='20', created_by=self.staff)
        with patch('orders.services.gift_card_hash', return_value='hash'):
            totals = calculate_checkout_totals(self.user, 'SAVE10', 'secret')
        self.assertEqual(totals['promotion_discount'], Decimal('20.00'))
        self.assertEqual(totals['coupon_discount'], Decimal('8.00'))
        self.assertEqual(totals['gift_card_discount'], Decimal('20.00'))
        self.assertEqual(len(totals['applied_promotions']), 1)
        self.assertEqual(totals['gift_card'], card)

    def test_gift_card_code_is_returned_once_and_never_stored(self):
        self.client.force_login(self.staff)
        created = self.client.post(reverse('staff-gift-card-list'), {
            'initial_balance': '100.00', 'recipient_email': 'recipient@example.com',
        }, content_type='application/json')
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.data['code'].startswith('ECCO-'))
        card = GiftCard.objects.get()
        self.assertNotEqual(card.code_hash, created.data['code'])
        detail = self.client.get(reverse('staff-gift-card-detail', args=(card.pk,)))
        self.assertIsNone(detail.data['code'])

    @override_settings(STRIPE_SECRET_KEY='sk_test', STORE_SHIPPING_FEE='0', STORE_TAX_RATE='0')
    @patch('orders.services.stripe.checkout.Session.create')
    def test_card_balance_is_reserved_and_redeemed_once(self, stripe_create):
        stripe_create.return_value = SimpleNamespace(id='cs_gift', url='https://example.test')
        card = GiftCard.objects.create(code_hash='hash', masked_code='**** ABCD', initial_balance='60', current_balance='60', created_by=self.staff)
        data = {'billing_name': 'Buyer', 'billing_email': 'buyer@example.com', 'address': '1 Road', 'city': 'Accra', 'postal_code': 'GA1', 'country': 'Ghana', 'gift_card_code': 'secret'}
        with patch('orders.services.gift_card_hash', return_value='hash'):
            attempt, _ = create_checkout_session(self.user, data)
        card.refresh_from_db()
        self.assertEqual(card.reserved_balance, Decimal('60.00'))
        fulfill_checkout(attempt.pk, 'pi_gift')
        fulfill_checkout(attempt.pk, 'pi_gift')
        card.refresh_from_db()
        self.assertEqual(card.current_balance, Decimal('0.00'))
        self.assertEqual(card.reserved_balance, Decimal('0.00'))
        self.assertEqual(GiftCardTransaction.objects.filter(kind='redeemed').count(), 1)

    def test_discount_management_requires_staff(self):
        self.client.force_login(self.user)
        for name in ('staff-coupon-list', 'staff-promotion-list', 'staff-gift-card-list'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
