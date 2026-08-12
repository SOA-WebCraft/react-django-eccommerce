from django.contrib import admin

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


@admin.register(StoreConfiguration)
class StoreConfigurationAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Store', {'fields': ('store_name', 'logo', 'address', 'phone', 'email')}),
        ('Tax', {'fields': ('tax_label', 'tax_rate')}),
        ('Notifications', {'fields': ('send_order_emails', 'send_invoice_emails')}),
    )

    def has_add_permission(self, request):
        return not StoreConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        'product',
        'product_name',
        'unit_price',
        'quantity',
        'line_total',
    )

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number',
        'user',
        'status',
        'payment_status',
        'total',
        'created_at',
        'confirmation_email_sent_at',
        'shipped_at',
        'delivered_at',
        'cancelled_at',
    )
    list_filter = ('status', 'payment_status')
    readonly_fields = (
        'order_number',
        'user',
        'total',
        'subtotal',
        'discount',
        'promotion_discount',
        'coupon_discount',
        'gift_card_discount',
        'promotion_snapshot',
        'gift_card_masked',
        'shipping',
        'tax',
        'currency',
        'payment_status',
        'payment_method',
        'stripe_payment_intent',
        'coupon_code',
        'billing_name',
        'billing_email',
        'address',
        'city',
        'postal_code',
        'country',
        'created_at',
        'updated_at',
        'confirmation_email_sent_at',
    )
    inlines = (OrderItemInline,)

    def has_module_permission(self, request):
        return bool(request.user.is_active and request.user.is_staff)

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff)

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_active and request.user.is_staff)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_name', 'quantity', 'line_total')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'discount_type',
        'value',
        'used_count',
        'reserved_count',
        'is_active',
    )
    search_fields = ('code',)
    list_filter = ('discount_type', 'is_active')


@admin.register(CheckoutAttempt)
class CheckoutAttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total', 'created_at')
    readonly_fields = ('stripe_session_id', 'stripe_payment_intent')


@admin.register(OrderTimelineEvent)
class OrderTimelineEventAdmin(admin.ModelAdmin):
    list_display = ('order', 'event_type', 'description', 'created_by', 'created_at')
    readonly_fields = ('order', 'event_type', 'description', 'created_by', 'created_at')


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'created_at', 'resolved_by')
    list_filter = ('status',)
    readonly_fields = ('order', 'reason', 'created_at', 'updated_at')


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'amount', 'requested_by', 'created_at')
    list_filter = ('status',)
    readonly_fields = (
        'order', 'status', 'amount', 'stripe_refund_id', 'error_message',
        'requested_by', 'created_at', 'updated_at',
    )


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'public_id', 'provider', 'method', 'status', 'store_amount',
        'store_currency', 'order', 'created_at',
    )
    list_filter = ('provider', 'method', 'status', 'store_currency')
    search_fields = ('public_id', 'provider_reference', 'order__order_number')
    readonly_fields = tuple(field.name for field in PaymentTransaction._meta.fields)


admin.site.register(ShippingMethod)
admin.site.register(ShippingZone)
admin.site.register(ShippingRate)
admin.site.register(Promotion)


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    list_display = ('masked_code', 'current_balance', 'reserved_balance', 'currency', 'is_active', 'expires_at')
    list_filter = ('is_active', 'currency')
    readonly_fields = ('code_hash', 'masked_code', 'current_balance', 'reserved_balance', 'currency', 'created_by', 'created_at', 'updated_at')


@admin.register(GiftCardTransaction)
class GiftCardTransactionAdmin(admin.ModelAdmin):
    list_display = ('gift_card', 'kind', 'amount', 'checkout', 'order', 'created_at')
    readonly_fields = tuple(field.name for field in GiftCardTransaction._meta.fields)
