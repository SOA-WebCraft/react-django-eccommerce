from django.db import transaction
from rest_framework import serializers

from catalog.models import Product
from catalog.serializers import ProductSerializer

from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    product_detail = ProductSerializer(source='product', read_only=True)
    line_total = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = CartItem
        fields = ('id', 'product', 'product_detail', 'quantity', 'line_total')
        read_only_fields = ('id', 'product_detail', 'line_total')

    def validate_product(self, product):
        if self.instance and product != self.instance.product:
            raise serializers.ValidationError(
                'The product on a cart item cannot be changed.'
            )
        if not product.is_active:
            raise serializers.ValidationError(
                'Only active products may be added to a cart.'
            )
        return product

    def validate(self, attrs):
        product = attrs.get('product') or getattr(self.instance, 'product', None)
        quantity = attrs.get(
            'quantity',
            getattr(self.instance, 'quantity', None),
        )
        if product and not product.is_active:
            raise serializers.ValidationError(
                {'product': 'Only active products may be added to a cart.'}
            )
        if product and quantity and quantity > product.stock_quantity:
            raise serializers.ValidationError(
                {'quantity': 'Quantity exceeds available stock.'}
            )
        return attrs

    def create(self, validated_data):
        request = self.context['request']
        submitted_quantity = validated_data['quantity']
        product_id = validated_data['product'].pk

        with transaction.atomic():
            product = Product.objects.select_for_update().get(pk=product_id)
            if not product.is_active:
                raise serializers.ValidationError(
                    {'product': 'Only active products may be added to a cart.'}
                )

            cart, _ = Cart.objects.get_or_create(user=request.user)
            cart = Cart.objects.select_for_update().get(pk=cart.pk)
            item = (
                CartItem.objects.select_for_update()
                .filter(cart=cart, product=product)
                .first()
            )

            if item is None:
                self.was_created = True
                return CartItem.objects.create(
                    cart=cart,
                    product=product,
                    quantity=submitted_quantity,
                )

            combined_quantity = item.quantity + submitted_quantity
            if combined_quantity > product.stock_quantity:
                raise serializers.ValidationError(
                    {'quantity': 'Combined quantity exceeds available stock.'}
                )
            item.quantity = combined_quantity
            item.save(update_fields=('quantity',))
            self.was_created = False
            return item


class CartItemQuantityAdjustmentSerializer(serializers.Serializer):
    operation = serializers.ChoiceField(
        choices=('increment', 'decrement'),
    )

    def validate_operation(self, operation):
        item = self.context['item']
        if operation == 'increment':
            if not item.product.is_active:
                raise serializers.ValidationError(
                    'Only active products may be incremented.'
                )
            if item.quantity >= item.product.stock_quantity:
                raise serializers.ValidationError(
                    'Quantity exceeds available stock.'
                )
        elif item.quantity <= 1:
            raise serializers.ValidationError(
                'Quantity cannot be less than one. Remove the item instead.'
            )
        return operation


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Cart
        fields = ('id', 'items', 'total', 'created_at', 'updated_at')
        read_only_fields = fields
