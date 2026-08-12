from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Category, Product

from .models import Cart, CartItem


User = get_user_model()


class CartApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='secret')
        self.other = User.objects.create_user(username='bob', password='secret')
        category = Category.objects.create(name='Books', slug='books')
        self.product = Product.objects.create(
            category=category,
            name='Django Book',
            slug='django-book',
            price=Decimal('12.50'),
            stock_quantity=3,
        )
        self.client.force_authenticate(self.user)

    def test_cart_models_are_registered_with_admin(self):
        self.assertIn(Cart, admin.site._registry)
        self.assertIn(CartItem, admin.site._registry)

    def test_cart_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse('cart-detail'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cart_item_operations_require_authentication(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=1,
        )
        self.client.force_authenticate(user=None)

        create_response = self.client.post(
            reverse('cart-item-create'),
            {'product': self.product.id, 'quantity': 1},
            format='json',
        )
        update_response = self.client.patch(
            reverse('cart-item-detail', args=(item.pk,)),
            {'operation': 'increment'},
            format='json',
        )
        delete_response = self.client.delete(
            reverse('cart-item-detail', args=(item.pk,))
        )

        self.assertEqual(
            create_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            update_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            delete_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)

    def test_add_and_read_cart_with_calculated_totals(self):
        create_response = self.client.post(
            reverse('cart-item-create'),
            {'product': self.product.id, 'quantity': 2},
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        response = self.client.get(reverse('cart-detail'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(Decimal(str(response.data['total'])), Decimal('25.00'))

    def test_quantity_must_be_positive_and_within_stock(self):
        zero = self.client.post(
            reverse('cart-item-create'),
            {'product': self.product.id, 'quantity': 0},
            format='json',
        )
        self.assertEqual(zero.status_code, status.HTTP_400_BAD_REQUEST)
        excessive = self.client.post(
            reverse('cart-item-create'),
            {'product': self.product.id, 'quantity': 4},
            format='json',
        )
        self.assertEqual(excessive.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantity', excessive.data)

    def test_inactive_product_is_rejected(self):
        self.product.is_active = False
        self.product.save(update_fields=('is_active',))
        inactive = self.client.post(
            reverse('cart-item-create'),
            {'product': self.product.id, 'quantity': 1},
            format='json',
        )
        self.assertEqual(inactive.status_code, status.HTTP_400_BAD_REQUEST)

    def test_existing_product_adds_to_quantity(self):
        created = self.client.post(
            reverse('cart-item-create'),
            {'product': self.product.id, 'quantity': 1},
            format='json',
        )
        updated = self.client.post(
            reverse('cart-item-create'),
            {'product': self.product.id, 'quantity': 2},
            format='json',
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data['quantity'], 3)
        self.assertEqual(
            CartItem.objects.filter(cart__user=self.user).count(),
            1,
        )

    def test_existing_product_rejects_combined_quantity_above_stock(self):
        self.client.post(
            reverse('cart-item-create'),
            {'product': self.product.id, 'quantity': 2},
            format='json',
        )
        response = self.client.post(
            reverse('cart-item-create'),
            {'product': self.product.id, 'quantity': 2},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('quantity', response.data)
        item = CartItem.objects.get(cart__user=self.user)
        self.assertEqual(item.quantity, 2)

    def test_user_cannot_change_another_users_cart_item(self):
        other_cart = Cart.objects.create(user=self.other)
        item = CartItem.objects.create(
            cart=other_cart,
            product=self.product,
            quantity=1,
        )
        response = self.client.patch(
            reverse('cart-item-detail', args=(item.pk,)),
            {'operation': 'increment'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_and_delete_own_item(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=1,
        )
        update = self.client.patch(
            reverse('cart-item-detail', args=(item.pk,)),
            {'operation': 'increment'},
            format='json',
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        self.assertEqual(
            Decimal(str(update.data['line_total'])),
            Decimal('25.00'),
        )
        cart_response = self.client.get(reverse('cart-detail'))
        self.assertEqual(
            Decimal(str(cart_response.data['total'])),
            Decimal('25.00'),
        )
        delete = self.client.delete(
            reverse('cart-item-detail', args=(item.pk,))
        )
        self.assertEqual(delete.status_code, status.HTTP_204_NO_CONTENT)

    def test_backend_decrements_quantity_and_recalculates_totals(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=3,
        )

        response = self.client.patch(
            reverse('cart-item-detail', args=(item.pk,)),
            {'operation': 'decrement'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['quantity'], 2)
        self.assertEqual(
            Decimal(str(response.data['line_total'])),
            Decimal('25.00'),
        )
        cart_response = self.client.get(reverse('cart-detail'))
        self.assertEqual(
            Decimal(str(cart_response.data['total'])),
            Decimal('25.00'),
        )

    def test_backend_rejects_invalid_quantity_adjustments(self):
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=1,
        )

        decrement = self.client.patch(
            reverse('cart-item-detail', args=(item.pk,)),
            {'operation': 'decrement'},
            format='json',
        )
        item.quantity = self.product.stock_quantity
        item.save(update_fields=('quantity',))
        increment = self.client.patch(
            reverse('cart-item-detail', args=(item.pk,)),
            {'operation': 'increment'},
            format='json',
        )

        self.assertEqual(
            decrement.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            increment.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
