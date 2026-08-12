from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import Product


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Cart for {self.user}'

    @property
    def total(self):
        return sum((item.line_total for item in self.items.all()), start=0)


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items',
    )
    quantity = models.PositiveIntegerField(
        validators=(MinValueValidator(1),),
    )

    class Meta:
        ordering = ('id',)
        constraints = (
            models.UniqueConstraint(
                fields=('cart', 'product'),
                name='unique_product_per_cart',
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name='cart_item_quantity_positive',
            ),
        )

    def __str__(self):
        return f'{self.quantity} × {self.product}'

    @property
    def line_total(self):
        return self.product.price * self.quantity
