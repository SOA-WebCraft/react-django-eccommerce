import secrets

from django.utils import timezone
from rest_framework import serializers

from invoices.models import Invoice
from invoices.serializers import InvoiceSerializer

from .models import (
    CheckoutAttempt,
    Coupon,
    GiftCard,
    GiftCardTransaction,
    Order,
    OrderItem,
    OrderTimelineEvent,
    PaymentTransaction,
    Promotion,
    RefundRequest,
    ReturnRequest,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
    StoreConfiguration,
)
from .services import calculate_checkout_totals, gift_card_hash


class StoreLogoField(serializers.ImageField):
    allowed_formats = {'JPEG', 'PNG', 'WEBP'}

    def to_internal_value(self, data):
        if data.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('Logo files must be 5 MB or smaller.')
        value = super().to_internal_value(data)
        if value.image.format not in self.allowed_formats:
            raise serializers.ValidationError('Upload a JPEG, PNG, or WebP image.')
        return value


class StoreConfigurationSerializer(serializers.ModelSerializer):
    logo = StoreLogoField(required=False, allow_null=True)

    class Meta:
        model = StoreConfiguration
        fields = (
            'store_name', 'logo', 'address', 'phone', 'email', 'tax_label',
            'tax_rate', 'send_order_emails', 'send_invoice_emails', 'updated_at',
        )
        read_only_fields = ('updated_at',)


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            'id',
            'product',
            'product_name',
            'unit_price',
            'quantity',
            'line_total',
        )
        read_only_fields = fields


class OrderTimelineEventSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(
        source='created_by.username',
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = OrderTimelineEvent
        fields = ('id', 'event_type', 'description', 'created_by', 'created_at')
        read_only_fields = fields


class ReturnRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReturnRequest
        fields = (
            'id', 'order', 'reason', 'status', 'staff_note',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'order', 'status', 'staff_note', 'created_at', 'updated_at',
        )

    def validate_reason(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError(
                'Explain the return reason using at least 10 characters.'
            )
        return value.strip()


class RefundRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundRequest
        fields = (
            'id', 'order', 'status', 'amount', 'stripe_refund_id',
            'error_message', 'created_at', 'updated_at',
        )
        read_only_fields = fields


class StaffReturnRequestSerializer(ReturnRequestSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer = serializers.CharField(source='order.user.username', read_only=True)
    order_total = serializers.DecimalField(
        source='order.total', max_digits=14, decimal_places=2, read_only=True,
    )

    class Meta(ReturnRequestSerializer.Meta):
        fields = ReturnRequestSerializer.Meta.fields + (
            'order_number', 'customer', 'order_total',
        )
        read_only_fields = fields


class StaffRefundRequestSerializer(RefundRequestSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer = serializers.CharField(source='order.user.username', read_only=True)

    class Meta(RefundRequestSerializer.Meta):
        fields = RefundRequestSerializer.Meta.fields + (
            'order_number', 'customer',
        )
        read_only_fields = fields


class PaymentTransactionSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(
        source='order.order_number', read_only=True, allow_null=True,
    )

    class Meta:
        model = PaymentTransaction
        fields = (
            'public_id', 'order', 'order_number', 'provider', 'method',
            'provider_reference', 'card_brand', 'status', 'store_amount',
            'store_currency', 'provider_amount', 'provider_currency',
            'exchange_rate', 'refunded_amount', 'provider_refund_id',
            'paid_at', 'created_at', 'updated_at',
        )
        read_only_fields = fields


class CouponManagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = ('id', 'code', 'discount_type', 'value', 'minimum_subtotal', 'starts_at', 'ends_at', 'usage_limit', 'used_count', 'reserved_count', 'is_active')
        read_only_fields = ('id', 'used_count', 'reserved_count')

    def validate(self, attrs):
        discount_type = attrs.get('discount_type', getattr(self.instance, 'discount_type', None))
        value = attrs.get('value', getattr(self.instance, 'value', None))
        starts_at = attrs.get('starts_at', getattr(self.instance, 'starts_at', None))
        ends_at = attrs.get('ends_at', getattr(self.instance, 'ends_at', None))
        if discount_type == Coupon.DiscountType.PERCENTAGE and value and value > 100:
            raise serializers.ValidationError({'value': 'Percentage discounts cannot exceed 100.'})
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({'ends_at': 'Expiry must be after the start date.'})
        return attrs


class PromotionSerializer(serializers.ModelSerializer):
    state = serializers.SerializerMethodField()

    class Meta:
        model = Promotion
        fields = ('id', 'name', 'percentage', 'scope', 'categories', 'products', 'starts_at', 'ends_at', 'is_active', 'state', 'created_at', 'updated_at')
        read_only_fields = ('id', 'state', 'created_at', 'updated_at')

    def validate(self, attrs):
        scope = attrs.get('scope', getattr(self.instance, 'scope', None))
        categories = attrs.get('categories')
        products = attrs.get('products')
        starts_at = attrs.get('starts_at', getattr(self.instance, 'starts_at', None))
        ends_at = attrs.get('ends_at', getattr(self.instance, 'ends_at', None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({'ends_at': 'Expiry must be after the start date.'})
        if scope == Promotion.Scope.CATEGORIES and self.instance is None and not categories:
            raise serializers.ValidationError({'categories': 'Select at least one category.'})
        if scope == Promotion.Scope.PRODUCTS and self.instance is None and not products:
            raise serializers.ValidationError({'products': 'Select at least one product.'})
        return attrs

    def get_state(self, promotion):
        now = timezone.now()
        if not promotion.is_active:
            return 'inactive'
        if promotion.starts_at > now:
            return 'upcoming'
        if promotion.ends_at <= now:
            return 'expired'
        return 'live'


class GiftCardSerializer(serializers.ModelSerializer):
    code = serializers.CharField(read_only=True)
    available_balance = serializers.SerializerMethodField()

    class Meta:
        model = GiftCard
        fields = ('id', 'code', 'masked_code', 'initial_balance', 'current_balance', 'reserved_balance', 'available_balance', 'currency', 'recipient_email', 'expires_at', 'is_active', 'created_by', 'created_at', 'updated_at')
        read_only_fields = ('id', 'code', 'masked_code', 'current_balance', 'reserved_balance', 'available_balance', 'currency', 'created_by', 'created_at', 'updated_at')

    def create(self, validated_data):
        raw_code = 'ECCO-' + secrets.token_urlsafe(15).replace('-', '').replace('_', '').upper()[:20]
        card = GiftCard.objects.create(
            code_hash=gift_card_hash(raw_code), masked_code=f'•••• {raw_code[-4:]}',
            current_balance=validated_data['initial_balance'],
            created_by=self.context['request'].user, **validated_data,
        )
        card._issued_code = raw_code
        return card

    def validate(self, attrs):
        if self.instance and 'initial_balance' in self.initial_data:
            raise serializers.ValidationError({'initial_balance': 'Initial balance cannot be changed.'})
        expires_at = attrs.get('expires_at')
        if not self.instance and expires_at and expires_at <= timezone.now():
            raise serializers.ValidationError({'expires_at': 'Expiry must be in the future.'})
        return attrs

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['code'] = getattr(instance, '_issued_code', None)
        return representation

    def get_available_balance(self, card):
        return card.current_balance - card.reserved_balance


class GiftCardTransactionSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True, allow_null=True)

    class Meta:
        model = GiftCardTransaction
        fields = ('id', 'checkout', 'order', 'order_number', 'kind', 'amount', 'created_at')
        read_only_fields = fields


class ShippingMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = ('id', 'name', 'code', 'kind', 'estimated_days', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


class ShippingZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingZone
        fields = ('id', 'name', 'countries', 'regions', 'cities', 'is_active', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate(self, attrs):
        for field in ('countries', 'regions', 'cities'):
            values = attrs.get(field)
            if values is not None and (not isinstance(values, list) or not all(isinstance(value, str) and value.strip() for value in values)):
                raise serializers.ValidationError({field: 'Use a list of nonblank names.'})
        return attrs


class ShippingRateSerializer(serializers.ModelSerializer):
    method_name = serializers.CharField(source='method.name', read_only=True)
    zone_name = serializers.CharField(source='zone.name', read_only=True)

    class Meta:
        model = ShippingRate
        fields = ('id', 'method', 'method_name', 'zone', 'zone_name', 'amount', 'free_shipping_threshold', 'is_active')
        read_only_fields = ('id', 'method_name', 'zone_name')


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    invoice = InvoiceSerializer(read_only=True)
    payment_provider = serializers.SerializerMethodField()
    timeline = OrderTimelineEventSerializer(
        source='timeline_events', many=True, read_only=True,
    )
    return_request = ReturnRequestSerializer(read_only=True)
    refund_request = RefundRequestSerializer(read_only=True)

    class Meta:
        model = Order
        fields = (
            'id',
            'order_number',
            'status',
            'subtotal',
            'discount',
            'promotion_discount',
            'coupon_discount',
            'gift_card_discount',
            'promotion_snapshot',
            'gift_card_masked',
            'shipping',
            'tax',
            'total',
            'currency',
            'payment_status',
            'payment_provider',
            'payment_method',
            'billing_name',
            'billing_email',
            'address',
            'city',
            'postal_code',
            'country',
            'tracking_number',
            'courier',
            'shipped_at',
            'delivered_at',
            'cancelled_at',
            'coupon_code',
            'items',
            'invoice',
            'timeline',
            'return_request',
            'refund_request',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_payment_provider(self, order):
        try:
            return order.payment_transaction.provider
        except PaymentTransaction.DoesNotExist:
            normalized_method = order.payment_method.strip().lower()
            if normalized_method in {
                PaymentTransaction.Provider.STRIPE,
                PaymentTransaction.Provider.PAYSTACK,
                PaymentTransaction.Provider.PAYPAL,
            }:
                return normalized_method
            if order.stripe_payment_intent:
                return PaymentTransaction.Provider.STRIPE
            return None


class OrderCustomerSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)


class StaffOrderSerializer(OrderSerializer):
    customer = OrderCustomerSerializer(source='user', read_only=True)

    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ('customer',)
        read_only_fields = fields


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=(
        Order.Status.PROCESSING,
        Order.Status.SHIPPED,
        Order.Status.COMPLETED,
        Order.Status.CANCELLED,
    ))
    tracking_number = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=120,
    )
    courier = serializers.CharField(required=False, allow_blank=True, max_length=120)

    class Meta:
        model = Order
        fields = ('status', 'tracking_number', 'courier')

    def validate(self, attrs):
        unexpected = set(self.initial_data) - {'status', 'tracking_number', 'courier'}
        if unexpected:
            raise serializers.ValidationError({
                field: 'This field cannot be updated.'
                for field in sorted(unexpected)
            })
        current = self.instance.status
        target = attrs.get('status', current)
        if target == current:
            return attrs
        allowed = {
            Order.Status.PENDING: Order.Status.PROCESSING,
            Order.Status.PROCESSING: Order.Status.SHIPPED,
            Order.Status.SHIPPED: Order.Status.COMPLETED,
        }
        if target == Order.Status.CANCELLED:
            if current not in {Order.Status.PENDING, Order.Status.PROCESSING}:
                raise serializers.ValidationError({
                    'status': 'Only pending or processing orders can be cancelled.'
                })
            return attrs
        if allowed.get(current) != target:
            raise serializers.ValidationError({
                'status': 'Order status must advance to the next status.'
            })
        if target == Order.Status.SHIPPED:
            tracking_number = attrs.get(
                'tracking_number', self.instance.tracking_number
            ).strip()
            if not tracking_number:
                raise serializers.ValidationError({
                    'tracking_number': 'Enter a tracking number before shipping.'
                })
            attrs['tracking_number'] = tracking_number
        return attrs

    def update(self, instance, validated_data):
        from django.utils import timezone

        target = validated_data['status']
        instance.status = target
        update_fields = ['status', 'updated_at']
        if 'tracking_number' in validated_data:
            instance.tracking_number = validated_data['tracking_number']
            update_fields.append('tracking_number')
        if 'courier' in validated_data:
            instance.courier = validated_data['courier']
            update_fields.append('courier')
        now = timezone.now()
        if target == Order.Status.SHIPPED:
            instance.shipped_at = now
            update_fields.append('shipped_at')
        elif target == Order.Status.COMPLETED:
            instance.delivered_at = now
            update_fields.append('delivered_at')
        elif target == Order.Status.CANCELLED:
            instance.cancelled_at = now
            update_fields.append('cancelled_at')
        instance.save(update_fields=update_fields)
        OrderTimelineEvent.objects.create(
            order=instance,
            event_type='status_changed',
            description=f'Order status changed to {instance.get_status_display()}.',
            created_by=self.context['request'].user,
        )
        instance._prefetched_objects_cache.pop('timeline_events', None)
        return instance


class StaffReturnUpdateSerializer(serializers.ModelSerializer):
    status = serializers.ChoiceField(choices=(
        ReturnRequest.Status.APPROVED,
        ReturnRequest.Status.REJECTED,
        ReturnRequest.Status.RECEIVED,
    ))

    class Meta:
        model = ReturnRequest
        fields = ('status', 'staff_note')

    def validate(self, attrs):
        current = self.instance.status
        target = attrs.get('status', current)
        allowed = {
            ReturnRequest.Status.REQUESTED: {
                ReturnRequest.Status.APPROVED,
                ReturnRequest.Status.REJECTED,
            },
            ReturnRequest.Status.APPROVED: {ReturnRequest.Status.RECEIVED},
        }
        if target != current and target not in allowed.get(current, set()):
            raise serializers.ValidationError({
                'status': 'This return transition is not allowed.'
            })
        return attrs


class QuoteSerializer(serializers.Serializer):
    coupon_code = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=40,
    )
    gift_card_code = serializers.CharField(required=False, allow_blank=True, max_length=64, write_only=True)

    def create(self, validated_data):
        return calculate_checkout_totals(
            self.context['request'].user,
            validated_data.get('coupon_code', ''),
            validated_data.get('gift_card_code', ''),
        )


class CheckoutSessionSerializer(serializers.Serializer):
    billing_name = serializers.CharField(max_length=200)
    billing_email = serializers.EmailField()
    address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=120)
    postal_code = serializers.CharField(max_length=40)
    country = serializers.CharField(max_length=120)
    coupon_code = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=40,
    )
    gift_card_code = serializers.CharField(required=False, allow_blank=True, max_length=64, write_only=True)


class HostedPaymentSerializer(CheckoutSessionSerializer):
    provider = serializers.ChoiceField(choices=('stripe', 'paystack'))
    method = serializers.ChoiceField(
        choices=('card',),
    )

    def validate(self, attrs):
        combinations = {
            'stripe': {'card'},
            'paystack': {'card'},
        }
        if attrs['method'] not in combinations[attrs['provider']]:
            raise serializers.ValidationError({
                'method': 'This method is not available for the selected provider.'
            })
        return attrs


class CheckoutStatusSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(read_only=True)
    invoice = serializers.SerializerMethodField()

    class Meta:
        model = CheckoutAttempt
        fields = (
            'id',
            'status',
            'subtotal',
            'discount',
            'promotion_discount',
            'coupon_discount',
            'gift_card_discount',
            'promotion_snapshot',
            'gift_card_masked',
            'shipping',
            'tax',
            'total',
            'currency',
            'order_id',
            'invoice',
            'error_message',
        )
        read_only_fields = fields

    def get_invoice(self, attempt):
        if not attempt.order_id:
            return None
        try:
            invoice = attempt.order.invoice
        except Invoice.DoesNotExist:
            return None
        return InvoiceSerializer(
            invoice,
            context=self.context,
        ).data
