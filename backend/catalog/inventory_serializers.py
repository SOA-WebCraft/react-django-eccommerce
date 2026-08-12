from rest_framework import serializers

from .models import (
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
)


class InventoryProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    reserved_stock = serializers.IntegerField(read_only=True)
    available_stock = serializers.SerializerMethodField()
    stock_state = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'slug', 'category_name', 'stock_quantity',
            'minimum_stock_quantity', 'reserved_stock', 'available_stock',
            'stock_state', 'is_active',
        )
        read_only_fields = fields

    def get_available_stock(self, product):
        return max(product.stock_quantity - product.reserved_stock, 0)

    def get_stock_state(self, product):
        available = self.get_available_stock(product)
        if available == 0:
            return 'out_of_stock'
        if available <= product.minimum_stock_quantity:
            return 'low_stock'
        return 'in_stock'


class StockAdjustmentSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    operation = serializers.ChoiceField(choices=('add', 'remove', 'set'))
    quantity = serializers.IntegerField(min_value=0)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        if attrs['operation'] in {'add', 'remove'} and attrs['quantity'] < 1:
            raise serializers.ValidationError({
                'quantity': 'Add and remove operations require at least one unit.'
            })
        return attrs


class StockMovementSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    created_by = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = StockMovement
        fields = (
            'id', 'product', 'product_name', 'movement_type',
            'quantity_change', 'previous_stock', 'resulting_stock', 'note',
            'purchase_order', 'created_by', 'created_at',
        )
        read_only_fields = fields


class SupplierSerializer(serializers.ModelSerializer):
    products = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        many=True,
        required=False,
    )
    product_names = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = (
            'id', 'name', 'phone', 'email', 'products', 'product_names',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'product_names', 'created_at', 'updated_at')

    def get_product_names(self, supplier):
        return [product.name for product in supplier.products.all()]


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = ('id', 'product', 'product_name', 'quantity', 'unit_cost')
        read_only_fields = ('id', 'product_name')


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    created_by = serializers.CharField(source='created_by.username', read_only=True)
    total_cost = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = (
            'id', 'supplier', 'supplier_name', 'status', 'notes', 'items',
            'total_cost', 'created_by', 'created_at', 'received_at',
        )
        read_only_fields = (
            'id', 'status', 'supplier_name', 'total_cost', 'created_by',
            'created_at', 'received_at',
        )

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError('Add at least one product.')
        product_ids = [item['product'].pk for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                'A product may appear only once in a purchase order.'
            )
        return items

    def create(self, validated_data):
        items = validated_data.pop('items')
        order = PurchaseOrder.objects.create(
            created_by=self.context['request'].user,
            **validated_data,
        )
        PurchaseOrderItem.objects.bulk_create([
            PurchaseOrderItem(purchase_order=order, **item)
            for item in items
        ])
        order.supplier.products.add(*(item['product'] for item in items))
        return order

    def get_total_cost(self, order):
        return sum(item.unit_cost * item.quantity for item in order.items.all())
