from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Category, Product

from .models import WishlistItem


User = get_user_model()


class WishlistApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='wishlist-user', password='secret',
        )
        self.other = User.objects.create_user(
            username='wishlist-other', password='secret',
        )
        category = Category.objects.create(name='Phones', slug='phones')
        self.product = Product.objects.create(
            category=category,
            name='Saved Phone',
            slug='saved-phone',
            price=Decimal('300.00'),
            stock_quantity=4,
        )
        self.list_url = reverse('wishlist-list')

    def test_wishlist_requires_authentication(self):
        self.assertEqual(
            self.client.get(self.list_url).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.post(
                self.list_url, {'product': self.product.pk}, format='json',
            ).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_add_is_idempotent_and_list_returns_product(self):
        self.client.force_authenticate(self.user)
        first = self.client.post(
            self.list_url, {'product': self.product.pk}, format='json',
        )
        second = self.client.post(
            self.list_url, {'product': self.product.pk}, format='json',
        )
        listed = self.client.get(self.list_url)

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(WishlistItem.objects.count(), 1)
        self.assertEqual(len(listed.data), 1)
        self.assertEqual(
            listed.data[0]['product_detail']['slug'],
            self.product.slug,
        )

    def test_inactive_product_is_rejected(self):
        self.product.is_active = False
        self.product.save(update_fields=('is_active',))
        self.client.force_authenticate(self.user)
        response = self.client.post(
            self.list_url, {'product': self.product.pk}, format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('active products', response.data['product'][0])

    def test_user_can_delete_only_their_own_item(self):
        item = WishlistItem.objects.create(
            user=self.user, product=self.product,
        )
        url = reverse('wishlist-item-delete', args=(item.pk,))
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.delete(url).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertTrue(WishlistItem.objects.filter(pk=item.pk).exists())

        self.client.force_authenticate(self.user)
        self.assertEqual(
            self.client.delete(url).status_code,
            status.HTTP_204_NO_CONTENT,
        )

    def test_wishlist_model_is_registered_with_admin(self):
        self.assertIn(WishlistItem, admin.site._registry)
