from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Product, PurchaseOrder, StockMovement


@transaction.atomic
def adjust_stock(user, validated_data):
    product = Product.objects.select_for_update().get(
        pk=validated_data['product'].pk
    )
    previous = product.stock_quantity
    quantity = validated_data['quantity']
    operation = validated_data['operation']
    if operation == 'add':
        resulting = previous + quantity
        movement_type = StockMovement.MovementType.ADDED
    elif operation == 'remove':
        if quantity > previous:
            raise ValidationError({
                'quantity': 'Cannot remove more than the current stock.'
            })
        resulting = previous - quantity
        movement_type = StockMovement.MovementType.REMOVED
    else:
        resulting = quantity
        movement_type = StockMovement.MovementType.ADJUSTMENT
    product.stock_quantity = resulting
    product.save(update_fields=('stock_quantity', 'updated_at'))
    return StockMovement.objects.create(
        product=product,
        movement_type=movement_type,
        quantity_change=resulting - previous,
        previous_stock=previous,
        resulting_stock=resulting,
        note=validated_data.get('note', ''),
        created_by=user,
    )


@transaction.atomic
def receive_purchase_order(user, purchase_order_id):
    order = (
        PurchaseOrder.objects.select_for_update()
        .prefetch_related('items__product')
        .get(pk=purchase_order_id)
    )
    if order.status != PurchaseOrder.Status.ORDERED:
        raise ValidationError({
            'status': 'Only an ordered purchase order can be received.'
        })
    products = {
        product.pk: product
        for product in Product.objects.select_for_update().filter(
            pk__in=[item.product_id for item in order.items.all()]
        )
    }
    for item in order.items.all():
        product = products[item.product_id]
        previous = product.stock_quantity
        product.stock_quantity = previous + item.quantity
        product.save(update_fields=('stock_quantity', 'updated_at'))
        StockMovement.objects.create(
            product=product,
            movement_type=StockMovement.MovementType.PURCHASE_RECEIVED,
            quantity_change=item.quantity,
            previous_stock=previous,
            resulting_stock=product.stock_quantity,
            note=f'Purchase order {order.pk} received.',
            purchase_order=order,
            created_by=user,
        )
    order.status = PurchaseOrder.Status.RECEIVED
    order.received_at = timezone.now()
    order.save(update_fields=('status', 'received_at'))
    return order
