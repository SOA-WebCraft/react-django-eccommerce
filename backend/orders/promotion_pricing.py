from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from .models import Promotion


CENT = Decimal('0.01')


def active_promotion_lookup():
    promotions = Promotion.objects.filter(
        is_active=True,
        starts_at__lte=timezone.now(),
        ends_at__gt=timezone.now(),
    ).prefetch_related('categories', 'products')
    lookup = {'store': None, 'categories': {}, 'products': {}}
    for promotion in promotions:
        if promotion.scope == Promotion.Scope.STORE:
            lookup['store'] = _better(lookup['store'], promotion)
        elif promotion.scope == Promotion.Scope.CATEGORIES:
            for category in promotion.categories.all():
                lookup['categories'][category.pk] = _better(
                    lookup['categories'].get(category.pk), promotion,
                )
        else:
            for product in promotion.products.all():
                lookup['products'][product.pk] = _better(
                    lookup['products'].get(product.pk), promotion,
                )
    return lookup


def best_promotion_for_product(product, lookup):
    candidates = (
        lookup['store'],
        lookup['categories'].get(product.category_id),
        lookup['products'].get(product.pk),
    )
    return max(
        (promotion for promotion in candidates if promotion is not None),
        key=lambda promotion: promotion.percentage,
        default=None,
    )


def promotional_price(product, promotion):
    if promotion is None:
        return None
    multiplier = Decimal('1') - promotion.percentage / Decimal('100')
    return (product.price * multiplier).quantize(CENT, rounding=ROUND_HALF_UP)


def _better(current, candidate):
    if current is None or candidate.percentage > current.percentage:
        return candidate
    return current
