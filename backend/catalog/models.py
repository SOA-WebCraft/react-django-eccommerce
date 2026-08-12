from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='product_images/',
        blank=True,
        null=True,
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=(MinValueValidator(0),),
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    minimum_stock_quantity = models.PositiveIntegerField(default=5)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        constraints = (
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name='product_price_nonnegative',
            ),
            models.CheckConstraint(
                condition=models.Q(stock_quantity__gte=0),
                name='product_stock_nonnegative',
            ),
        )

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='gallery_images',
    )
    image = models.ImageField(upload_to='product_images/gallery/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')

    def __str__(self):
        return f'Gallery image {self.pk} for {self.product}'


class Supplier(models.Model):
    name = models.CharField(max_length=200, unique=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    products = models.ManyToManyField(Product, related_name='suppliers', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        ORDERED = 'ordered', 'Ordered'
        RECEIVED = 'received', 'Received'
        CANCELLED = 'cancelled', 'Cancelled'

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='purchase_orders',
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ORDERED,
        db_index=True,
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_purchase_orders',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'Purchase order {self.pk} from {self.supplier}'


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='purchase_order_items',
    )
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ('id',)
        constraints = (
            models.UniqueConstraint(
                fields=('purchase_order', 'product'),
                name='unique_product_per_purchase_order',
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name='purchase_order_item_quantity_positive',
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name='purchase_order_item_cost_nonnegative',
            ),
        )

    def __str__(self):
        return f'{self.quantity} × {self.product}'


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        ADDED = 'added', 'Stock added'
        REMOVED = 'removed', 'Stock removed'
        ADJUSTMENT = 'adjustment', 'Stock adjustment'
        PURCHASE_RECEIVED = 'purchase_received', 'Purchase order received'

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='stock_movements',
    )
    movement_type = models.CharField(max_length=24, choices=MovementType.choices)
    quantity_change = models.IntegerField()
    previous_stock = models.PositiveIntegerField()
    resulting_stock = models.PositiveIntegerField()
    note = models.CharField(max_length=255, blank=True)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        related_name='stock_movements',
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='stock_movements',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')

    def __str__(self):
        return f'{self.product}: {self.quantity_change:+d}'
