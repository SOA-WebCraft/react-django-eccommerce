from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import (
    CharField,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from catalog.models import Product

from .models import CheckoutAttempt, Order, OrderItem, PaymentTransaction


User = get_user_model()


def percentage_change(current, previous):
    if not previous:
        return Decimal('0.0') if not current else None
    current = Decimal(current)
    previous = Decimal(previous)
    return ((current - previous) / previous * 100).quantize(Decimal('0.1'))


def build_analytics_snapshot():
    today = timezone.localdate()
    start_date = today - timedelta(days=29)
    previous_start_date = start_date - timedelta(days=30)
    paid_orders = Order.objects.filter(payment_status='paid')
    paid_summary = paid_orders.aggregate(
        revenue=Sum('total', default=Decimal('0.00')),
        count=Count('id'),
    )
    current_paid_orders = paid_orders.filter(created_at__date__gte=start_date)
    previous_paid_orders = paid_orders.filter(
        created_at__date__gte=previous_start_date,
        created_at__date__lt=start_date,
    )
    current_period = current_paid_orders.aggregate(
        revenue=Sum('total', default=Decimal('0.00')),
        orders=Count('id'),
        customers=Count('user_id', distinct=True),
    )
    previous_period = previous_paid_orders.aggregate(
        revenue=Sum('total', default=Decimal('0.00')),
        orders=Count('id'),
    )
    units_sold = OrderItem.objects.filter(
        order__payment_status='paid',
        order__created_at__date__gte=start_date,
    ).aggregate(total=Sum('quantity', default=0))['total']
    repeat_customers = (
        current_paid_orders.values('user_id')
        .annotate(order_count=Count('id'))
        .filter(order_count__gte=2)
        .count()
    )
    customer_count = current_period['customers']
    repeat_customer_rate = (
        Decimal(repeat_customers * 100) / Decimal(customer_count)
        if customer_count else Decimal('0.0')
    ).quantize(Decimal('0.1'))
    average_order_value = (
        current_period['revenue'] / current_period['orders']
        if current_period['orders'] else Decimal('0.00')
    ).quantize(Decimal('0.01'))
    financials = current_paid_orders.aggregate(
        gross_sales=Sum('subtotal', default=Decimal('0.00')),
        discounts=Sum('discount', default=Decimal('0.00')),
        shipping=Sum('shipping', default=Decimal('0.00')),
        tax=Sum('tax', default=Decimal('0.00')),
    )
    refunds = PaymentTransaction.objects.filter(
        refunded_amount__gt=0,
        updated_at__date__gte=start_date,
    ).aggregate(total=Sum('refunded_amount', default=Decimal('0.00')))[
        'total'
    ]
    financials['refunds'] = refunds
    financials['net_revenue'] = max(
        current_period['revenue'] - refunds,
        Decimal('0.00'),
    )
    checkout_attempts = CheckoutAttempt.objects.filter(
        created_at__date__gte=start_date,
    )
    checkout_counts = checkout_attempts.aggregate(
        started=Count('id'),
        completed=Count(
            'id',
            filter=Q(status__in=[
                CheckoutAttempt.Status.PAID,
                CheckoutAttempt.Status.FULFILLED,
                CheckoutAttempt.Status.REFUND_PENDING,
                CheckoutAttempt.Status.REFUNDED,
                CheckoutAttempt.Status.REFUND_FAILED,
            ]),
        ),
    )
    checkout_counts['abandoned_or_failed'] = (
        checkout_counts['started'] - checkout_counts['completed']
    )
    checkout_counts['completion_rate'] = (
        Decimal(checkout_counts['completed'] * 100)
        / Decimal(checkout_counts['started'])
        if checkout_counts['started'] else Decimal('0.0')
    ).quantize(Decimal('0.1'))
    sales_by_category = list(
        OrderItem.objects.filter(
            order__payment_status='paid',
            order__created_at__date__gte=start_date,
        )
        .annotate(category=Coalesce(
            'product__category__name',
            Value('Uncategorized'),
            output_field=CharField(),
        ))
        .values('category')
        .annotate(
            revenue=Sum('line_total', default=Decimal('0.00')),
            units=Sum('quantity', default=0),
        )
        .order_by('-revenue', 'category')[:6]
    )
    payment_methods = list(
        current_paid_orders.values('payment_method')
        .annotate(
            orders=Count('id'),
            revenue=Sum('total', default=Decimal('0.00')),
        )
        .order_by('-orders', 'payment_method')
    )
    for method in payment_methods:
        method['payment_method'] = method['payment_method'] or 'unknown'
    active_products = Product.objects.filter(is_active=True)
    inventory_value_expression = ExpressionWrapper(
        F('price') * F('stock_quantity'),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )
    inventory_health = active_products.aggregate(
        active_products=Count('id'),
        low_stock=Count('id', filter=Q(stock_quantity__lte=5)),
        out_of_stock=Count('id', filter=Q(stock_quantity=0)),
        units_available=Sum('stock_quantity', default=0),
        retail_value=Sum(
            inventory_value_expression,
            default=Decimal('0.00'),
        ),
    )
    status_counts = dict(
        Order.objects.values_list('status').annotate(count=Count('id'))
    )
    daily_rows = {
        row['day']: row
        for row in (
            paid_orders.filter(created_at__date__gte=start_date)
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(
                revenue=Sum('total', default=Decimal('0.00')),
                orders=Count('id'),
            )
            .order_by('day')
        )
    }
    daily_sales = []
    for offset in range(30):
        day = start_date + timedelta(days=offset)
        row = daily_rows.get(day, {})
        daily_sales.append({
            'date': day.isoformat(),
            'revenue': row.get('revenue', Decimal('0.00')),
            'orders': row.get('orders', 0),
        })
    top_products = list(
        OrderItem.objects.filter(order__payment_status='paid')
        .values('product_id', 'product_name')
        .annotate(
            quantity_sold=Sum('quantity'),
            revenue=Sum('line_total', default=Decimal('0.00')),
        )
        .order_by('-quantity_sold', '-revenue', 'product_name')[:5]
    )
    low_stock = list(
        Product.objects.filter(is_active=True, stock_quantity__lte=5)
        .select_related('category')
        .order_by('stock_quantity', 'name')
        .values(
            'id', 'name', 'slug', 'stock_quantity', 'category__name',
        )[:10]
    )
    return {
        'summary': {
            'total_revenue': paid_summary['revenue'],
            'paid_orders': paid_summary['count'],
            'total_orders': Order.objects.count(),
            'customers': User.objects.filter(is_staff=False).count(),
        },
        'statistics': {
            'period_days': 30,
            'revenue': current_period['revenue'],
            'revenue_change_percent': percentage_change(
                current_period['revenue'], previous_period['revenue'],
            ),
            'paid_orders': current_period['orders'],
            'paid_orders_change_percent': percentage_change(
                current_period['orders'], previous_period['orders'],
            ),
            'average_order_value': average_order_value,
            'units_sold': units_sold,
            'unique_customers': customer_count,
            'repeat_customer_rate': repeat_customer_rate,
            'new_customers': User.objects.filter(
                is_staff=False,
                date_joined__date__gte=start_date,
            ).count(),
        },
        'financials': financials,
        'checkout_performance': checkout_counts,
        'sales_by_category': sales_by_category,
        'sales_by_payment_method': payment_methods,
        'inventory_health': inventory_health,
        'orders_by_status': [
            {'status': value, 'count': status_counts.get(value, 0)}
            for value, _ in Order.Status.choices
        ],
        'daily_sales': daily_sales,
        'top_products': top_products,
        'low_stock_products': [
            {
                'id': product['id'],
                'name': product['name'],
                'slug': product['slug'],
                'stock_quantity': product['stock_quantity'],
                'category': product['category__name'],
            }
            for product in low_stock
        ],
    }
