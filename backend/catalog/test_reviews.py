from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from orders.models import Order, OrderItem

from .models import Category, Product, ProductReview


User = get_user_model()


class ProductReviewApiTests(APITestCase):
    def setUp(self):
        self.buyer = User.objects.create_user(
            username='review-buyer', password='secret',
        )
        self.other = User.objects.create_user(
            username='review-other', password='secret',
        )
        self.staff = User.objects.create_user(
            username='review-staff', password='secret', is_staff=True,
        )
        category = Category.objects.create(name='Phones', slug='phones')
        self.product = Product.objects.create(
            category=category,
            name='Review Phone',
            slug='review-phone',
            price=Decimal('200.00'),
            stock_quantity=5,
        )
        order = Order.objects.create(
            user=self.buyer,
            total=Decimal('200.00'),
            payment_status='paid',
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal('200.00'),
            quantity=1,
            line_total=Decimal('200.00'),
        )
        self.list_url = reverse(
            'product-review-list-create',
            kwargs={'product_slug': self.product.slug},
        )

    def create_review(self):
        self.client.force_authenticate(self.buyer)
        return self.client.post(self.list_url, {
            'rating': 5,
            'title': 'Excellent phone',
            'comment': 'Fast, polished, and reliable.',
        }, format='json')

    def test_public_can_list_reviews_and_product_contains_aggregate(self):
        created = self.create_review()
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.client.force_authenticate(user=None)

        reviews = self.client.get(self.list_url)
        product = self.client.get(reverse(
            'product-detail', kwargs={'slug': self.product.slug},
        ))

        self.assertEqual(reviews.status_code, status.HTTP_200_OK)
        self.assertEqual(reviews.data['count'], 1)
        self.assertEqual(reviews.data['results'][0]['rating'], 5)
        self.assertEqual(
            reviews.data['results'][0]['customer'],
            {'id': self.buyer.pk, 'name': self.buyer.username},
        )
        self.assertTrue(reviews.data['results'][0]['verified_purchase'])
        self.assertEqual(product.data['rating_average'], '5.00')
        self.assertEqual(product.data['review_count'], 1)

    def test_review_requires_authentication_and_paid_purchase(self):
        payload = {'rating': 4, 'title': 'Good', 'comment': 'A good phone.'}
        self.assertEqual(
            self.client.post(self.list_url, payload, format='json').status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.client.force_authenticate(self.other)
        response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('paid purchase', response.data['detail'][0])

    def test_duplicate_and_invalid_reviews_are_rejected(self):
        self.assertEqual(self.create_review().status_code, status.HTTP_201_CREATED)
        duplicate = self.client.post(self.list_url, {
            'rating': 4, 'title': 'Again', 'comment': 'Second review.',
        }, format='json')
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

        ProductReview.objects.all().delete()
        invalid = self.client.post(self.list_url, {
            'rating': 6, 'title': '', 'comment': '',
        }, format='json')
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('rating', invalid.data)
        self.assertIn('title', invalid.data)
        self.assertIn('comment', invalid.data)

    def test_owner_can_patch_and_delete_but_another_customer_cannot(self):
        review_id = self.create_review().data['id']
        detail_url = reverse('product-review-detail', kwargs={
            'product_slug': self.product.slug,
            'pk': review_id,
        })

        updated = self.client.patch(
            detail_url, {'rating': 4, 'title': 'Updated'}, format='json',
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        self.assertEqual(updated.data['rating'], 4)

        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.patch(
                detail_url, {'rating': 1}, format='json',
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(self.buyer)
        self.assertEqual(
            self.client.delete(detail_url).status_code,
            status.HTTP_204_NO_CONTENT,
        )

    def test_staff_can_remove_review_and_inactive_product_is_hidden(self):
        review_id = self.create_review().data['id']
        detail_url = reverse('product-review-detail', kwargs={
            'product_slug': self.product.slug,
            'pk': review_id,
        })
        self.client.force_authenticate(self.staff)
        self.assertEqual(
            self.client.delete(detail_url).status_code,
            status.HTTP_204_NO_CONTENT,
        )
        self.product.is_active = False
        self.product.save(update_fields=('is_active',))
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get(self.list_url).status_code,
            status.HTTP_404_NOT_FOUND,
        )
