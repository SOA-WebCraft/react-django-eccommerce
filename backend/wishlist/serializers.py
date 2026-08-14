from django.db import IntegrityError, transaction
from rest_framework import serializers

from catalog.models import Product
from catalog.serializers import ProductSerializer

from .models import WishlistItem


class WishlistItemSerializer(serializers.ModelSerializer):
    product_detail = ProductSerializer(source='product', read_only=True)

    class Meta:
        model = WishlistItem
        fields = ('id', 'product', 'product_detail', 'created_at')
        read_only_fields = ('id', 'product_detail', 'created_at')

    def validate_product(self, product):
        if not product.is_active:
            raise serializers.ValidationError(
                'Only active products may be added to a wishlist.'
            )
        return product

    def create(self, validated_data):
        try:
            with transaction.atomic():
                item, created = WishlistItem.objects.get_or_create(
                    user=self.context['request'].user,
                    product=validated_data['product'],
                )
        except IntegrityError:
            item = WishlistItem.objects.get(
                user=self.context['request'].user,
                product=validated_data['product'],
            )
            created = False
        self.was_created = created
        return item
