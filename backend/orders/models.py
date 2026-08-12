import uuid
import secrets
import string
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from catalog.models import Category, Product


ORDER_NUMBER_ALPHABET = string.ascii_uppercase + string.digits


def generate_order_number():
    return ''.join(secrets.choice(ORDER_NUMBER_ALPHABET) for _ in range(10))


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        SHIPPED = 'shipped', 'Shipped'
        COMPLETED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

    order_number = models.CharField(
        max_length=10,
        unique=True,
        editable=False,
        default=generate_order_number,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
        validators=(MinValueValidator(0),),
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    promotion_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    coupon_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gift_card_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    promotion_snapshot = models.JSONField(default=list, blank=True)
    gift_card_masked = models.CharField(max_length=24, blank=True)
    shipping = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='USD')
    payment_status = models.CharField(max_length=20, default='unpaid')
    payment_method = models.CharField(max_length=80, blank=True)
    stripe_payment_intent = models.CharField(
        max_length=255,
        blank=True,
        unique=True,
        null=True,
    )
    coupon_code = models.CharField(max_length=40, blank=True)
    billing_name = models.CharField(max_length=200, blank=True)
    billing_email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmation_email_sent_at = models.DateTimeField(null=True, blank=True)
    tracking_number = models.CharField(max_length=120, blank=True)
    courier = models.CharField(max_length=120, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(total__gte=0),
                name='order_total_nonnegative',
            ),
        )

    def __str__(self):
        return f'Order {self.pk} for {self.user}'


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        related_name='order_items',
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=(MinValueValidator(0),),
    )
    quantity = models.PositiveIntegerField(
        validators=(MinValueValidator(1),),
    )
    line_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=(MinValueValidator(0),),
    )

    class Meta:
        ordering = ('id',)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name='order_item_unit_price_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name='order_item_quantity_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(line_total__gte=0),
                name='order_item_line_total_nonnegative',
            ),
        )

    def __str__(self):
        return f'{self.quantity} × {self.product_name}'


class OrderTimelineEvent(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='timeline_events',
    )
    event_type = models.CharField(max_length=40)
    description = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_timeline_events',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')


class ReturnRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        RECEIVED = 'received', 'Received'

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='return_request',
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.REQUESTED,
        db_index=True,
    )
    staff_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_return_requests',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)


class RefundRequest(models.Model):
    class Status(models.TextChoices):
        PROCESSING = 'processing', 'Processing'
        APPROVED = 'approved', 'Approved'
        FAILED = 'failed', 'Failed'

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='refund_request',
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PROCESSING,
        db_index=True,
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    stripe_refund_id = models.CharField(max_length=255, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='requested_refunds',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        FIXED = 'fixed', 'Fixed amount'
        PERCENTAGE = 'percentage', 'Percentage'

    code = models.CharField(max_length=40, unique=True)
    discount_type = models.CharField(
        max_length=12,
        choices=DiscountType.choices,
    )
    value = models.DecimalField(
        max_digits=12, decimal_places=2, validators=(MinValueValidator(Decimal('0.01')),),
    )
    minimum_subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    reserved_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = (
            models.CheckConstraint(condition=models.Q(value__gt=0), name='coupon_value_positive'),
            models.CheckConstraint(condition=models.Q(minimum_subtotal__gte=0), name='coupon_minimum_nonnegative'),
        )

    def clean(self):
        if (
            self.discount_type == self.DiscountType.PERCENTAGE
            and Decimal(str(self.value)) > 100
        ):
            raise ValidationError({'value': 'Percentage discounts cannot exceed 100.'})
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'Expiry must be after the start date.'})

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class Promotion(models.Model):
    class Scope(models.TextChoices):
        STORE = 'store', 'Entire store'
        CATEGORIES = 'categories', 'Selected categories'
        PRODUCTS = 'products', 'Selected products'

    name = models.CharField(max_length=160)
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=(MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('100'))),
    )
    scope = models.CharField(max_length=16, choices=Scope.choices)
    categories = models.ManyToManyField(Category, blank=True, related_name='promotions')
    products = models.ManyToManyField(Product, blank=True, related_name='promotions')
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-starts_at', 'name')
        constraints = (
            models.CheckConstraint(condition=models.Q(percentage__gt=0, percentage__lte=100), name='promotion_percentage_range'),
            models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='promotion_dates_ordered'),
        )

    def clean(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({'ends_at': 'Expiry must be after the start date.'})


class GiftCard(models.Model):
    code_hash = models.CharField(max_length=64, unique=True, editable=False)
    masked_code = models.CharField(max_length=24, editable=False)
    initial_balance = models.DecimalField(max_digits=14, decimal_places=2, validators=(MinValueValidator(Decimal('0.01')),))
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, validators=(MinValueValidator(0),))
    reserved_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=(MinValueValidator(0),))
    currency = models.CharField(max_length=3, default='GHS', editable=False)
    recipient_email = models.EmailField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='issued_gift_cards')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = (
            models.CheckConstraint(condition=models.Q(initial_balance__gt=0), name='gift_card_initial_positive'),
            models.CheckConstraint(condition=models.Q(current_balance__gte=0), name='gift_card_balance_nonnegative'),
            models.CheckConstraint(condition=models.Q(reserved_balance__gte=0), name='gift_card_reserved_nonnegative'),
        )


class GiftCardTransaction(models.Model):
    class Kind(models.TextChoices):
        RESERVED = 'reserved', 'Reserved'
        RELEASED = 'released', 'Released'
        REDEEMED = 'redeemed', 'Redeemed'
        RESTORED = 'restored', 'Restored after refund'

    gift_card = models.ForeignKey(GiftCard, on_delete=models.PROTECT, related_name='transactions')
    checkout = models.ForeignKey('CheckoutAttempt', on_delete=models.PROTECT, related_name='gift_card_transactions')
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name='gift_card_transactions')
    kind = models.CharField(max_length=12, choices=Kind.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=(MinValueValidator(Decimal('0.01')),))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = (
            models.UniqueConstraint(fields=('checkout', 'kind'), name='unique_gift_card_checkout_kind'),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='gift_card_transaction_positive'),
        )


class CheckoutAttempt(models.Model):
    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        PAID = 'paid', 'Paid'
        FULFILLED = 'fulfilled', 'Fulfilled'
        EXPIRED = 'expired', 'Expired'
        REFUND_PENDING = 'refund_pending', 'Refund pending'
        REFUNDED = 'refunded', 'Refunded'
        REFUND_FAILED = 'refund_failed', 'Refund failed'
        FAILED = 'failed', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='checkout_attempts',
    )
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.CREATED,
        db_index=True,
    )
    stripe_session_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
    )
    stripe_payment_intent = models.CharField(max_length=255, blank=True)
    order = models.OneToOneField(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checkout_attempt',
    )
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    coupon_code = models.CharField(max_length=40, blank=True)
    coupon_reserved = models.BooleanField(default=False)
    subtotal = models.DecimalField(max_digits=14, decimal_places=2)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    promotion_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    coupon_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    gift_card_discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    promotion_snapshot = models.JSONField(default=list, blank=True)
    gift_card = models.ForeignKey(GiftCard, on_delete=models.SET_NULL, null=True, blank=True, related_name='checkout_attempts')
    gift_card_masked = models.CharField(max_length=24, blank=True)
    gift_card_reserved = models.BooleanField(default=False)
    shipping = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    billing_name = models.CharField(max_length=200)
    billing_email = models.EmailField()
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=120)
    postal_code = models.CharField(max_length=40)
    country = models.CharField(max_length=120)
    payment_method = models.CharField(max_length=80, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PaymentTransaction(models.Model):
    class Provider(models.TextChoices):
        STRIPE = 'stripe', 'Stripe'
        PAYSTACK = 'paystack', 'Paystack'
        PAYPAL = 'paypal', 'PayPal'
        STORE_CREDIT = 'store_credit', 'Store credit'

    class Method(models.TextChoices):
        CARD = 'card', 'Card'
        PAYPAL = 'paypal', 'PayPal'
        MOBILE_MONEY = 'mobile_money', 'Mobile money'
        BANK_TRANSFER = 'bank_transfer', 'Bank transfer'
        GIFT_CARD = 'gift_card', 'Gift card'

    class Status(models.TextChoices):
        INITIALIZED = 'initialized', 'Initialized'
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    checkout = models.OneToOneField(
        CheckoutAttempt,
        on_delete=models.PROTECT,
        related_name='transaction',
    )
    order = models.OneToOneField(
        Order,
        on_delete=models.SET_NULL,
        related_name='payment_transaction',
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=16, choices=Provider.choices)
    method = models.CharField(max_length=24, choices=Method.choices)
    provider_reference = models.CharField(max_length=255, blank=True, db_index=True)
    card_brand = models.CharField(max_length=40, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.INITIALIZED,
        db_index=True,
    )
    store_amount = models.DecimalField(max_digits=14, decimal_places=2)
    store_currency = models.CharField(max_length=3)
    provider_amount = models.DecimalField(max_digits=14, decimal_places=2)
    provider_currency = models.CharField(max_length=3)
    exchange_rate = models.DecimalField(
        max_digits=18,
        decimal_places=8,
        default=1,
    )
    refunded_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    provider_refund_id = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(store_amount__gte=0),
                name='payment_store_amount_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(provider_amount__gte=0),
                name='payment_provider_amount_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(exchange_rate__gt=0),
                name='payment_exchange_rate_positive',
            ),
        )


class ShippingMethod(models.Model):
    class Kind(models.TextChoices):
        STANDARD = 'standard', 'Standard'
        EXPRESS = 'express', 'Express'
        PICKUP = 'pickup', 'Pickup'

    name = models.CharField(max_length=120)
    code = models.SlugField(unique=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    estimated_days = models.PositiveSmallIntegerField(default=3)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class ShippingZone(models.Model):
    name = models.CharField(max_length=120, unique=True)
    countries = models.JSONField(default=list)
    regions = models.JSONField(default=list, blank=True)
    cities = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class ShippingRate(models.Model):
    method = models.ForeignKey(
        ShippingMethod, on_delete=models.CASCADE, related_name='rates',
    )
    zone = models.ForeignKey(
        ShippingZone, on_delete=models.CASCADE, related_name='rates',
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, validators=(MinValueValidator(0),),
    )
    free_shipping_threshold = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=(MinValueValidator(0),),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('zone__name', 'method__name')
        constraints = (
            models.UniqueConstraint(
                fields=('method', 'zone'), name='unique_shipping_rate',
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gte=0), name='shipping_rate_nonnegative',
            ),
        )


class StoreConfiguration(models.Model):
    class TaxLabel(models.TextChoices):
        VAT = 'vat', 'VAT'
        GST = 'gst', 'GST'
        SALES_TAX = 'sales_tax', 'Sales Tax'
        NONE = 'none', 'No Tax'

    store_name = models.CharField(max_length=160, default='ECCO Store')
    logo = models.ImageField(upload_to='store/', blank=True, null=True)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    tax_label = models.CharField(
        max_length=20, choices=TaxLabel.choices, default=TaxLabel.VAT,
    )
    tax_rate = models.DecimalField(
        max_digits=6, decimal_places=5, default=Decimal('0.075'),
        validators=(MinValueValidator(0), MaxValueValidator(1)),
    )
    send_order_emails = models.BooleanField(default=True)
    send_invoice_emails = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'store configuration'
        permissions = (
            ('manage_store_settings', 'Can manage store settings'),
        )

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        instance, _ = cls.objects.get_or_create(
            pk=1,
            defaults={'tax_rate': Decimal(settings.STORE_TAX_RATE)},
        )
        return instance

    def __str__(self):
        return self.store_name


class CheckoutItem(models.Model):
    checkout = models.ForeignKey(
        CheckoutAttempt,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ('id',)
