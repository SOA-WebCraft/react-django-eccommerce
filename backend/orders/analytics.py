from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from catalog.models import Product

from .models import Order, OrderItem


User = get_user_model()


def build_analytics_snapshot():
    today = timezone.localdate()
    start_date = today - timedelta(days=29)
    paid_orders = Order.objects.filter(payment_status='paid')
    paid_summary = paid_orders.aggregate(
        revenue=Sum('total', default=Decimal('0.00')),
        count=Count('id'),
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
