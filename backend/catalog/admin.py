from django.contrib import admin

from .models import (
    Category,
    Product,
    ProductImage,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'category',
        'image',
        'price',
        'stock_quantity',
        'is_active',
    )
    list_filter = ('is_active', 'category')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    inlines = (ProductImageInline,)


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'image', 'created_at')
    search_fields = ('product__name',)
    list_select_related = ('product',)
    readonly_fields = ('created_at',)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email')
    search_fields = ('name', 'phone', 'email')
    filter_horizontal = ('products',)


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'supplier', 'status', 'created_by', 'created_at')
    list_filter = ('status',)
    list_select_related = ('supplier', 'created_by')
    inlines = (PurchaseOrderItemInline,)
    readonly_fields = ('created_at', 'received_at')


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'movement_type', 'quantity_change', 'previous_stock',
        'resulting_stock', 'created_by', 'created_at',
    )
    list_filter = ('movement_type',)
    search_fields = ('product__name', 'note')
    list_select_related = ('product', 'created_by')
    readonly_fields = (
        'product', 'movement_type', 'quantity_change', 'previous_stock',
        'resulting_stock', 'note', 'purchase_order', 'created_by',
        'created_at',
    )
