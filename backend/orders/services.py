import base64
import hashlib
import hmac
import json
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import stripe
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from cart.models import Cart
from catalog.models import Product

from .models import (
    CheckoutAttempt,
    CheckoutItem,
    Coupon,
    GiftCard,
    GiftCardTransaction,
    Order,
    OrderItem,
    PaymentTransaction,
    StoreConfiguration,
)
from .promotion_pricing import active_promotion_lookup, best_promotion_for_product


logger = logging.getLogger(__name__)


CENT = Decimal('0.01')


def _money(value):
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _cart_items(user):
    try:
        cart = Cart.objects.prefetch_related('items__product').get(user=user)
    except Cart.DoesNotExist as exc:
        raise ValidationError(
            {'cart': 'An order cannot be created from an empty cart.'}
        ) from exc
    items = list(cart.items.select_related('product').order_by('product_id'))
    if not items:
        raise ValidationError(
            {'cart': 'An order cannot be created from an empty cart.'}
        )
    for item in items:
        if not item.product.is_active:
            raise ValidationError({'cart': 'A product is no longer available.'})
        if item.quantity > item.product.stock_quantity:
            raise ValidationError(
                {'cart': 'Quantity exceeds available stock.'}
            )
    return cart, items


def _valid_coupon(code, subtotal, lock=False):
    if not code:
        return None
    queryset = Coupon.objects
    if lock:
        queryset = queryset.select_for_update()
    try:
        coupon = queryset.get(code__iexact=code.strip())
    except Coupon.DoesNotExist as exc:
        raise ValidationError({'coupon_code': 'Coupon is invalid.'}) from exc
    now = timezone.now()
    if not coupon.is_active:
        raise ValidationError({'coupon_code': 'Coupon is inactive.'})
    if coupon.starts_at and coupon.starts_at > now:
        raise ValidationError({'coupon_code': 'Coupon is not active yet.'})
    if coupon.ends_at and coupon.ends_at <= now:
        raise ValidationError({'coupon_code': 'Coupon has expired.'})
    if subtotal < coupon.minimum_subtotal:
        raise ValidationError(
            {'coupon_code': 'Cart does not meet the coupon minimum.'}
        )
    if (
        coupon.usage_limit is not None
        and coupon.used_count + coupon.reserved_count >= coupon.usage_limit
    ):
        raise ValidationError({'coupon_code': 'Coupon usage limit reached.'})
    return coupon


def gift_card_hash(code):
    normalized = code.strip().upper()
    return hmac.new(
        settings.SECRET_KEY.encode(), normalized.encode(), hashlib.sha256,
    ).hexdigest()


def _valid_gift_card(code, lock=False):
    if not code:
        return None
    queryset = GiftCard.objects
    if lock:
        queryset = queryset.select_for_update()
    try:
        card = queryset.get(code_hash=gift_card_hash(code))
    except GiftCard.DoesNotExist as exc:
        raise ValidationError({'gift_card_code': 'Gift card is invalid.'}) from exc
    if not card.is_active:
        raise ValidationError({'gift_card_code': 'Gift card is inactive.'})
    if card.expires_at and card.expires_at <= timezone.now():
        raise ValidationError({'gift_card_code': 'Gift card has expired.'})
    if card.currency != settings.STORE_CURRENCY:
        raise ValidationError({'gift_card_code': 'Gift card currency is not supported.'})
    if card.current_balance - card.reserved_balance <= 0:
        raise ValidationError({'gift_card_code': 'Gift card has no available balance.'})
    return card


def _promotion_discounts(items):
    lookup = active_promotion_lookup()
    snapshots = []
    total = Decimal('0.00')
    for item in items:
        best = best_promotion_for_product(item.product, lookup)
        if best is None:
            continue
        amount = _money(item.product.price * item.quantity * best.percentage / Decimal('100'))
        total += amount
        snapshots.append({
            'promotion_id': best.pk, 'name': best.name,
            'percentage': str(best.percentage), 'product_id': item.product_id,
            'amount': str(amount),
        })
    return _money(total), snapshots


def calculate_checkout_totals(user, coupon_code='', gift_card_code=''):
    _, items = _cart_items(user)
    subtotal = _money(sum(
        (item.product.price * item.quantity for item in items),
        Decimal('0.00'),
    ))
    promotion_discount, promotion_snapshot = _promotion_discounts(items)
    merchandise_after_promotion = max(Decimal('0.00'), subtotal - promotion_discount)
    coupon = _valid_coupon(coupon_code, merchandise_after_promotion)
    coupon_discount = Decimal('0.00')
    if coupon:
        if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
            coupon_discount = merchandise_after_promotion * coupon.value / Decimal('100')
        else:
            coupon_discount = coupon.value
        coupon_discount = _money(min(coupon_discount, merchandise_after_promotion))
    threshold = Decimal(settings.STORE_FREE_SHIPPING_THRESHOLD)
    shipping = (
        Decimal('0.00')
        if subtotal >= threshold
        else Decimal(settings.STORE_SHIPPING_FEE)
    )
    taxable = subtotal - promotion_discount - coupon_discount + shipping
    tax = _money(taxable * StoreConfiguration.load().tax_rate)
    before_gift_card = _money(taxable + tax)
    gift_card = _valid_gift_card(gift_card_code)
    gift_card_discount = Decimal('0.00')
    if gift_card:
        available = gift_card.current_balance - gift_card.reserved_balance
        gift_card_discount = _money(min(available, before_gift_card))
    total = _money(max(Decimal('0.00'), before_gift_card - gift_card_discount))
    return {
        'subtotal': subtotal,
        'promotion_discount': promotion_discount,
        'coupon_discount': coupon_discount,
        'gift_card_discount': gift_card_discount,
        'discount': _money(promotion_discount + coupon_discount + gift_card_discount),
        'applied_promotions': promotion_snapshot,
        'shipping': _money(shipping),
        'tax': tax,
        'total': total,
        'currency': settings.STORE_CURRENCY,
        'coupon': coupon,
        'gift_card': gift_card,
    }


def _minor_units(value):
    return int((value * 100).quantize(Decimal('1')))


def _stripe_amount(total, currency):
    if currency == 'GHS':
        try:
            rate = Decimal(settings.STRIPE_GHS_TO_USD_RATE)
        except InvalidOperation as exc:
            raise ValidationError({
                'payment': 'Stripe currency conversion is not configured correctly.'
            }) from exc
        if rate <= 0:
            raise ValidationError({
                'payment': 'Stripe currency conversion is not configured correctly.'
            })
        return _money(total * rate), 'USD', rate
    return total, currency, Decimal('1')


def create_checkout_session(user, validated_data):
    coupon_code = validated_data.get('coupon_code', '')
    gift_card_code = validated_data.get('gift_card_code', '')
    with transaction.atomic():
        cart, items = _cart_items(user)
        totals = calculate_checkout_totals(user, coupon_code, gift_card_code)
        coupon = None
        if totals['coupon']:
            coupon = _valid_coupon(
                coupon_code,
                totals['subtotal'] - totals['promotion_discount'],
                lock=True,
            )
            coupon.reserved_count = F('reserved_count') + 1
            coupon.save(update_fields=('reserved_count',))
        gift_card = None
        if totals['gift_card']:
            gift_card = _valid_gift_card(gift_card_code, lock=True)
            available = gift_card.current_balance - gift_card.reserved_balance
            if totals['gift_card_discount'] > available:
                raise ValidationError({'gift_card_code': 'Gift card balance is already reserved.'})
            gift_card.reserved_balance += totals['gift_card_discount']
            gift_card.save(update_fields=('reserved_balance', 'updated_at'))
        attempt = CheckoutAttempt.objects.create(
            user=user,
            coupon=coupon,
            coupon_code=coupon.code if coupon else '',
            coupon_reserved=bool(coupon),
            subtotal=totals['subtotal'],
            discount=totals['discount'],
            promotion_discount=totals['promotion_discount'],
            coupon_discount=totals['coupon_discount'],
            gift_card_discount=totals['gift_card_discount'],
            promotion_snapshot=totals['applied_promotions'],
            gift_card=gift_card,
            gift_card_masked=gift_card.masked_code if gift_card else '',
            gift_card_reserved=bool(gift_card),
            shipping=totals['shipping'],
            tax=totals['tax'],
            total=totals['total'],
            currency=totals['currency'],
            billing_name=validated_data['billing_name'],
            billing_email=validated_data['billing_email'],
            address=validated_data['address'],
            city=validated_data['city'],
            postal_code=validated_data['postal_code'],
            country=validated_data['country'],
        )
        CheckoutItem.objects.bulk_create([
            CheckoutItem(
                checkout=attempt,
                product=item.product,
                product_name=item.product.name,
                unit_price=item.product.price,
                quantity=item.quantity,
                line_total=_money(item.product.price * item.quantity),
            )
            for item in items
        ])
        if gift_card:
            GiftCardTransaction.objects.create(
                gift_card=gift_card, checkout=attempt,
                kind=GiftCardTransaction.Kind.RESERVED,
                amount=totals['gift_card_discount'],
            )
    if attempt.total == 0:
        PaymentTransaction.objects.create(
            checkout=attempt, provider=PaymentTransaction.Provider.STORE_CREDIT,
            method=PaymentTransaction.Method.GIFT_CARD,
            provider_reference=str(attempt.pk), status=PaymentTransaction.Status.PENDING,
            store_amount=attempt.total, store_currency=attempt.currency,
            provider_amount=attempt.total, provider_currency=attempt.currency,
        )
        fulfill_checkout(attempt.pk, str(attempt.pk), 'store_credit', 'gift_card')
        return attempt, settings.PAYMENT_SUCCESS_URL.format(checkout_id=attempt.pk)
    if not settings.STRIPE_SECRET_KEY:
        release_checkout_coupon(attempt)
        if not attempt.gift_card_id:
            attempt.delete()
        else:
            attempt.status = CheckoutAttempt.Status.FAILED
            attempt.error_message = 'Stripe is not configured on the server.'
            attempt.save(update_fields=('status', 'error_message', 'updated_at'))
        raise ValidationError(
            {'payment': 'Stripe is not configured on the server.'}
        )
    provider_amount, provider_currency, exchange_rate = _stripe_amount(
        attempt.total, attempt.currency,
    )
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        session = stripe.checkout.Session.create(
            mode='payment',
            client_reference_id=str(attempt.pk),
            customer_email=attempt.billing_email,
            line_items=[{
                'price_data': {
                    'currency': provider_currency.lower(),
                    'product_data': {
                        'name': f'ECCO order {attempt.pk}',
                    },
                    'unit_amount': _minor_units(provider_amount),
                },
                'quantity': 1,
            }],
            success_url=settings.STRIPE_SUCCESS_URL.format(
                checkout_id=attempt.pk,
            ),
            cancel_url=settings.STRIPE_CANCEL_URL,
            expires_at=int(timezone.now().timestamp()) + 1800,
            metadata={'checkout_id': str(attempt.pk)},
            payment_intent_data={
                'metadata': {'checkout_id': str(attempt.pk)},
            },
        )
    except stripe.StripeError as exc:
        logger.warning(
            'Stripe Checkout initialization failed (%s).',
            getattr(exc, 'code', None) or type(exc).__name__,
        )
        release_checkout_coupon(attempt)
        attempt.status = CheckoutAttempt.Status.FAILED
        attempt.error_message = 'Unable to initialize payment.'
        attempt.save(update_fields=('status', 'error_message', 'updated_at'))
        raise ValidationError(
            {'payment': 'Unable to initialize payment.'}
        ) from exc
    attempt.stripe_session_id = session.id
    attempt.save(update_fields=('stripe_session_id', 'updated_at'))
    PaymentTransaction.objects.create(
        checkout=attempt,
        provider=PaymentTransaction.Provider.STRIPE,
        method=PaymentTransaction.Method.CARD,
        provider_reference=session.id,
        status=PaymentTransaction.Status.PENDING,
        store_amount=attempt.total,
        store_currency=attempt.currency,
        provider_amount=provider_amount,
        provider_currency=provider_currency,
        exchange_rate=exchange_rate,
    )
    return attempt, session.url


def available_payment_methods():
    return [
        {
            'provider': 'stripe', 'method': 'card', 'label': 'Stripe',
            'description': 'Secure card checkout.',
            'enabled': bool(settings.STRIPE_SECRET_KEY),
        },
        {
            'provider': 'paystack', 'method': 'card', 'label': 'Paystack',
            'description': 'Pay securely with card, Mobile Money, or bank transfer.',
            'enabled': bool(settings.PAYSTACK_SECRET_KEY),
        },
    ]


def _request_json(url, *, method='GET', data=None, headers=None):
    body = json.dumps(data).encode() if data is not None else None
    request = Request(url, data=body, method=method, headers={
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'ECCO-Store-Backend/1.0',
        **(headers or {}),
    })
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode())
    except HTTPError as exc:
        provider_message = ''
        try:
            provider_payload = json.loads(exc.read().decode())
            provider_message = str(provider_payload.get('message', ''))[:300]
        except (ValueError, UnicodeDecodeError):
            pass
        logger.warning(
            'Payment provider request failed: host=%s status=%s message=%s',
            url.split('/', 3)[2],
            exc.code,
            provider_message or 'No provider message returned.',
        )
        raise ValidationError({
            'payment': provider_message
            or 'The payment provider rejected the checkout request.'
        }) from exc
    except (URLError, ValueError) as exc:
        logger.warning(
            'Payment provider request could not be completed: host=%s error=%s',
            url.split('/', 3)[2],
            exc.reason if isinstance(exc, URLError) else type(exc).__name__,
        )
        raise ValidationError({'payment': 'The payment provider could not initialize checkout.'}) from exc


def _create_payment_attempt(user, validated_data):
    coupon_code = validated_data.get('coupon_code', '')
    gift_card_code = validated_data.get('gift_card_code', '')
    with transaction.atomic():
        _, items = _cart_items(user)
        totals = calculate_checkout_totals(user, coupon_code, gift_card_code)
        coupon = None
        if totals['coupon']:
            coupon = _valid_coupon(
                coupon_code,
                totals['subtotal'] - totals['promotion_discount'],
                lock=True,
            )
            coupon.reserved_count = F('reserved_count') + 1
            coupon.save(update_fields=('reserved_count',))
        gift_card = None
        if totals['gift_card']:
            gift_card = _valid_gift_card(gift_card_code, lock=True)
            available = gift_card.current_balance - gift_card.reserved_balance
            if totals['gift_card_discount'] > available:
                raise ValidationError({'gift_card_code': 'Gift card balance is already reserved.'})
            gift_card.reserved_balance += totals['gift_card_discount']
            gift_card.save(update_fields=('reserved_balance', 'updated_at'))
        attempt = CheckoutAttempt.objects.create(
            user=user, coupon=coupon, coupon_code=coupon.code if coupon else '',
            coupon_reserved=bool(coupon), subtotal=totals['subtotal'],
            discount=totals['discount'], promotion_discount=totals['promotion_discount'],
            coupon_discount=totals['coupon_discount'], gift_card_discount=totals['gift_card_discount'],
            promotion_snapshot=totals['applied_promotions'], gift_card=gift_card,
            gift_card_masked=gift_card.masked_code if gift_card else '',
            gift_card_reserved=bool(gift_card), shipping=totals['shipping'], tax=totals['tax'],
            total=totals['total'], currency=totals['currency'],
            billing_name=validated_data['billing_name'],
            billing_email=validated_data['billing_email'], address=validated_data['address'],
            city=validated_data['city'], postal_code=validated_data['postal_code'],
            country=validated_data['country'],
        )
        CheckoutItem.objects.bulk_create([
            CheckoutItem(
                checkout=attempt, product=item.product, product_name=item.product.name,
                unit_price=item.product.price, quantity=item.quantity,
                line_total=_money(item.product.price * item.quantity),
            ) for item in items
        ])
        if gift_card:
            GiftCardTransaction.objects.create(
                gift_card=gift_card, checkout=attempt,
                kind=GiftCardTransaction.Kind.RESERVED,
                amount=totals['gift_card_discount'],
            )
    return attempt


def create_hosted_payment(user, validated_data):
    provider = validated_data.pop('provider')
    method = validated_data.pop('method')
    if provider == 'stripe':
        return (*create_checkout_session(user, validated_data), provider, method)
    enabled = any(
        item['provider'] == provider and item['method'] == method and item['enabled']
        for item in available_payment_methods()
    )
    if not enabled:
        raise ValidationError({'payment_method': 'This payment method is not configured.'})
    attempt = _create_payment_attempt(user, validated_data)
    if attempt.total == 0:
        PaymentTransaction.objects.create(
            checkout=attempt, provider=PaymentTransaction.Provider.STORE_CREDIT,
            method=PaymentTransaction.Method.GIFT_CARD,
            provider_reference=str(attempt.pk), status=PaymentTransaction.Status.PENDING,
            store_amount=attempt.total, store_currency=attempt.currency,
            provider_amount=attempt.total, provider_currency=attempt.currency,
        )
        fulfill_checkout(attempt.pk, str(attempt.pk), 'store_credit', 'gift_card')
        return attempt, settings.PAYMENT_SUCCESS_URL.format(checkout_id=attempt.pk), 'store_credit', 'gift_card'
    if provider == 'store_credit':
        release_checkout_coupon(attempt)
        raise ValidationError({'gift_card_code': 'Gift card balance does not cover the full total.'})
    try:
        if provider == 'paystack':
            response = _request_json(
                'https://api.paystack.co/transaction/initialize', method='POST',
                headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
                data={
                    'email': attempt.billing_email,
                    'amount': _minor_units(attempt.total),
                    'currency': 'GHS',
                    'reference': str(attempt.pk),
                    'callback_url': settings.PAYMENT_SUCCESS_URL.format(checkout_id=attempt.pk),
                    'channels': ['card', 'mobile_money', 'bank_transfer'],
                    'metadata': {'checkout_id': str(attempt.pk)},
                },
            )
            if response.get('status') is not True:
                raise ValidationError({
                    'payment': 'Paystack could not initialize checkout.'
                })
            provider_reference = response['data']['reference']
            checkout_url = response['data']['authorization_url']
            if not provider_reference or not checkout_url.startswith('https://'):
                raise ValidationError({
                    'payment': 'Paystack returned an invalid checkout response.'
                })
            provider_amount, provider_currency, rate = attempt.total, 'GHS', Decimal('1')
        else:
            rate = Decimal(settings.PAYPAL_GHS_TO_USD_RATE)
            provider_amount = _money(attempt.total * rate)
            provider_currency = 'USD'
            token = _paypal_access_token()
            response = _request_json(
                f'{settings.PAYPAL_API_BASE}/v2/checkout/orders', method='POST',
                headers={'Authorization': f'Bearer {token}', 'PayPal-Request-Id': str(attempt.pk)},
                data={
                    'intent': 'CAPTURE',
                    'purchase_units': [{
                        'reference_id': str(attempt.pk),
                        'custom_id': str(attempt.pk),
                        'amount': {'currency_code': 'USD', 'value': str(provider_amount)},
                    }],
                    'payment_source': {'paypal': {'experience_context': {
                        'return_url': settings.PAYMENT_SUCCESS_URL.format(checkout_id=attempt.pk),
                        'cancel_url': settings.PAYMENT_CANCEL_URL,
                    }}},
                },
            )
            provider_reference = response['id']
            checkout_url = next(link['href'] for link in response['links'] if link['rel'] == 'payer-action')
        PaymentTransaction.objects.create(
            checkout=attempt, provider=provider, method=method,
            provider_reference=provider_reference, status=PaymentTransaction.Status.PENDING,
            store_amount=attempt.total, store_currency=attempt.currency,
            provider_amount=provider_amount, provider_currency=provider_currency,
            exchange_rate=rate,
        )
        return attempt, checkout_url, provider, method
    except (KeyError, StopIteration, ValidationError):
        release_checkout_coupon(attempt)
        attempt.status = CheckoutAttempt.Status.FAILED
        attempt.error_message = 'Unable to initialize payment.'
        attempt.save(update_fields=('status', 'error_message', 'updated_at'))
        raise


def _paypal_access_token():
    credentials = base64.b64encode(
        f'{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}'.encode()
    ).decode()
    request = Request(
        f'{settings.PAYPAL_API_BASE}/v1/oauth2/token',
        data=urlencode({'grant_type': 'client_credentials'}).encode(),
        method='POST',
        headers={
            'Authorization': f'Basic {credentials}',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode())['access_token']
    except (HTTPError, URLError, ValueError, KeyError) as exc:
        raise ValidationError({'payment': 'PayPal authentication failed.'}) from exc


@transaction.atomic
def release_checkout_coupon(attempt):
    attempt = CheckoutAttempt.objects.select_for_update().get(pk=attempt.pk)
    if attempt.coupon_id and attempt.coupon_reserved:
        coupon = Coupon.objects.select_for_update().get(pk=attempt.coupon_id)
        coupon.reserved_count = max(0, coupon.reserved_count - 1)
        coupon.save(update_fields=('reserved_count',))
        attempt.coupon_reserved = False
        attempt.save(update_fields=('coupon_reserved', 'updated_at'))
    if attempt.gift_card_id and attempt.gift_card_reserved:
        gift_card = GiftCard.objects.select_for_update().get(pk=attempt.gift_card_id)
        gift_card.reserved_balance = max(
            Decimal('0.00'), gift_card.reserved_balance - attempt.gift_card_discount,
        )
        gift_card.save(update_fields=('reserved_balance', 'updated_at'))
        GiftCardTransaction.objects.get_or_create(
            gift_card=gift_card, checkout=attempt,
            kind=GiftCardTransaction.Kind.RELEASED,
            defaults={'amount': attempt.gift_card_discount},
        )
        attempt.gift_card_reserved = False
        attempt.save(update_fields=('gift_card_reserved', 'updated_at'))


@transaction.atomic
def fulfill_checkout(
    attempt_id,
    payment_intent,
    provider='stripe',
    payment_method=None,
    card_brand='',
):
    attempt = (
        CheckoutAttempt.objects.select_for_update()
        .prefetch_related('items')
        .get(pk=attempt_id)
    )
    if attempt.order_id:
        return attempt, False
    if provider == 'stripe':
        attempt.stripe_payment_intent = payment_intent
    attempt.status = CheckoutAttempt.Status.PAID
    products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(
            pk__in=[item.product_id for item in attempt.items.all()]
        )
    }
    unavailable = any(
        item.product_id not in products
        or not products[item.product_id].is_active
        or item.quantity > products[item.product_id].stock_quantity
        for item in attempt.items.all()
    )
    unavailable = unavailable or bool(
        attempt.gift_card_discount and not attempt.gift_card_reserved
    )
    if unavailable:
        attempt.status = CheckoutAttempt.Status.REFUND_PENDING
        attempt.error_message = 'Stock became unavailable after payment.'
        attempt.save(update_fields=(
            'status',
            'stripe_payment_intent',
            'error_message',
            'updated_at',
        ))
        return attempt, True
    order = Order.objects.create(
        user=attempt.user,
        status=Order.Status.PROCESSING,
        subtotal=attempt.subtotal,
        discount=attempt.discount,
        promotion_discount=attempt.promotion_discount,
        coupon_discount=attempt.coupon_discount,
        gift_card_discount=attempt.gift_card_discount,
        promotion_snapshot=attempt.promotion_snapshot,
        gift_card_masked=attempt.gift_card_masked,
        shipping=attempt.shipping,
        tax=attempt.tax,
        total=attempt.total,
        currency=attempt.currency,
        payment_status='paid',
        payment_method=(payment_method or provider).replace('_', ' ').title(),
        stripe_payment_intent=(payment_intent if provider == 'stripe' else None),
        coupon_code=attempt.coupon_code,
        billing_name=attempt.billing_name,
        billing_email=attempt.billing_email,
        address=attempt.address,
        city=attempt.city,
        postal_code=attempt.postal_code,
        country=attempt.country,
    )
    OrderItem.objects.bulk_create([
        OrderItem(
            order=order,
            product_id=item.product_id,
            product_name=item.product_name,
            unit_price=item.unit_price,
            quantity=item.quantity,
            line_total=item.line_total,
        )
        for item in attempt.items.all()
    ])
    for item in attempt.items.all():
        product = products[item.product_id]
        product.stock_quantity -= item.quantity
        product.save(update_fields=('stock_quantity',))
    if attempt.coupon_id and attempt.coupon_reserved:
        coupon = Coupon.objects.select_for_update().get(pk=attempt.coupon_id)
        coupon.reserved_count = max(0, coupon.reserved_count - 1)
        coupon.used_count += 1
        coupon.save(update_fields=('reserved_count', 'used_count'))
        attempt.coupon_reserved = False
    if attempt.gift_card_id and attempt.gift_card_reserved:
        gift_card = GiftCard.objects.select_for_update().get(pk=attempt.gift_card_id)
        gift_card.reserved_balance = max(Decimal('0.00'), gift_card.reserved_balance - attempt.gift_card_discount)
        gift_card.current_balance -= attempt.gift_card_discount
        gift_card.save(update_fields=('reserved_balance', 'current_balance', 'updated_at'))
        GiftCardTransaction.objects.create(
            gift_card=gift_card, checkout=attempt, order=order,
            kind=GiftCardTransaction.Kind.REDEEMED,
            amount=attempt.gift_card_discount,
        )
        attempt.gift_card_reserved = False
    cart = Cart.objects.filter(user=attempt.user).first()
    if cart:
        cart.items.all().delete()
        cart.updated_at = timezone.now()
        cart.save(update_fields=('updated_at',))
    attempt.order = order
    attempt.status = CheckoutAttempt.Status.FULFILLED
    attempt.payment_method = (payment_method or provider).replace('_', ' ').title()
    attempt.save(update_fields=(
        'order',
        'status',
        'payment_method',
        'stripe_payment_intent',
        'coupon_reserved',
        'gift_card_reserved',
        'updated_at',
    ))
    payment = PaymentTransaction.objects.select_for_update().filter(
        checkout=attempt,
    ).first()
    if payment:
        payment.order = order
        payment.status = PaymentTransaction.Status.PAID
        payment.provider_reference = payment_intent or payment.provider_reference
        payment.card_brand = card_brand[:40]
        payment.paid_at = timezone.now()
        payment.save(update_fields=(
            'order', 'status', 'provider_reference', 'card_brand', 'paid_at',
            'updated_at',
        ))
    return attempt, False


def create_order_from_cart(user):
    raise ValidationError(
        {'payment': 'Orders must be created through verified checkout.'}
    )


def process_full_refund(order_id, user):
    import stripe
    from django.conf import settings

    from .models import OrderTimelineEvent, RefundRequest

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.payment_status != 'paid':
            raise ValidationError({'payment': 'Only paid orders can be refunded.'})
        payment = PaymentTransaction.objects.select_for_update().filter(order=order).first()
        provider = payment.provider if payment else 'stripe'
        payment_reference = (
            payment.provider_reference if payment else order.stripe_payment_intent
        )
        if not payment_reference:
            raise ValidationError({'payment': 'This order has no payment reference.'})
        refund, _ = RefundRequest.objects.get_or_create(
            order=order,
            defaults={'amount': order.total, 'requested_by': user},
        )
        if refund.status == RefundRequest.Status.APPROVED:
            return refund
        refund.status = RefundRequest.Status.PROCESSING
        refund.error_message = ''
        refund.requested_by = user
        refund.save(update_fields=(
            'status', 'error_message', 'requested_by', 'updated_at',
        ))
    provider_refund_id = ''
    refund_complete = True
    try:
        if provider == 'stripe':
            if not settings.STRIPE_SECRET_KEY:
                raise ValidationError({'payment': 'Stripe is not configured on the server.'})
            stripe.api_key = settings.STRIPE_SECRET_KEY
            result = stripe.Refund.create(
                payment_intent=payment_reference,
                reason='requested_by_customer',
                idempotency_key=f'staff-full-refund-{order_id}',
            )
            provider_refund_id = getattr(result, 'id', '')
        elif provider == 'paystack':
            result = _request_json(
                'https://api.paystack.co/refund', method='POST',
                headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
                data={'transaction': payment_reference},
            )
            provider_refund_id = str(result.get('data', {}).get('id', ''))
            refund_complete = result.get('data', {}).get('status') == 'processed'
        elif provider == 'paypal':
            result = _request_json(
                f'{settings.PAYPAL_API_BASE}/v2/payments/captures/{payment_reference}/refund',
                method='POST',
                headers={
                    'Authorization': f'Bearer {_paypal_access_token()}',
                    'PayPal-Request-Id': f'staff-full-refund-{order_id}',
                },
                data={},
            )
            provider_refund_id = result.get('id', '')
            refund_complete = result.get('status') == 'COMPLETED'
        else:
            provider_refund_id = f'gift-card-{order.order_number}'
    except (stripe.StripeError, ValidationError) as exc:
        RefundRequest.objects.filter(pk=refund.pk).update(
            status=RefundRequest.Status.FAILED,
            error_message='The payment provider could not complete the refund.',
        )
        raise ValidationError({
            'payment': 'The payment provider could not complete the refund.'
        }) from exc
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        refund = RefundRequest.objects.select_for_update().get(pk=refund.pk)
        refund.status = (
            RefundRequest.Status.APPROVED
            if refund_complete else RefundRequest.Status.PROCESSING
        )
        refund.stripe_refund_id = provider_refund_id
        refund.error_message = ''
        refund.save(update_fields=(
            'status', 'stripe_refund_id', 'error_message', 'updated_at',
        ))
        PaymentTransaction.objects.filter(order=order).update(
            provider_refund_id=provider_refund_id,
        )
        if refund_complete:
            order.payment_status = 'refunded'
            order.save(update_fields=('payment_status', 'updated_at'))
            CheckoutAttempt.objects.filter(order=order).update(
                status=CheckoutAttempt.Status.REFUNDED
            )
            PaymentTransaction.objects.filter(order=order).update(
                status=PaymentTransaction.Status.REFUNDED,
                refunded_amount=order.total,
            )
            attempt = CheckoutAttempt.objects.select_related('gift_card').filter(order=order).first()
            if attempt and attempt.gift_card_id and attempt.gift_card_discount:
                gift_card = GiftCard.objects.select_for_update().get(pk=attempt.gift_card_id)
                _, restored = GiftCardTransaction.objects.get_or_create(
                    gift_card=gift_card, checkout=attempt, order=order,
                    kind=GiftCardTransaction.Kind.RESTORED,
                    defaults={'amount': attempt.gift_card_discount},
                )
                if restored:
                    gift_card.current_balance += attempt.gift_card_discount
                    gift_card.save(update_fields=('current_balance', 'updated_at'))
        OrderTimelineEvent.objects.create(
            order=order,
            event_type='refund_approved',
            description=(
                f'Full refund of {order.currency} {order.total} '
                f'{"approved" if refund_complete else "submitted"}.'
            ),
            created_by=user,
        )
    return refund
