import io
import os
import shutil
import uuid
from datetime import timedelta
from decimal import Decimal

from PIL import Image
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Product, ProductImage
from orders.models import Promotion
from .roles import CATALOG_MANAGERS_GROUP


User = get_user_model()


def grant_catalog_manager(user):
    group = Group.objects.get(name=CATALOG_MANAGERS_GROUP)
    user.groups.add(group)


class CatalogApiTests(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Books', slug='books')
        self.active = Product.objects.create(
            category=self.category,
            name='Django Book',
            slug='django-book',
            price=Decimal('25.00'),
            stock_quantity=5,
        )
        self.inactive = Product.objects.create(
            category=self.category,
            name='Hidden Book',
            slug='hidden-book',
            price=Decimal('10.00'),
            stock_quantity=1,
            is_active=False,
        )

    def test_public_list_is_paginated_and_hides_inactive_products(self):
        response = self.client.get(reverse('product-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.active.id)

    def test_product_response_includes_active_promotional_price(self):
        now = timezone.now()
        Promotion.objects.create(
            name='Store sale',
            percentage=Decimal('20.00'),
            scope=Promotion.Scope.STORE,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )

        response = self.client.get(
            reverse('product-detail', args=(self.active.slug,))
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['price'], '25.00')
        self.assertEqual(response.data['promotional_price'], '20.00')
        self.assertEqual(response.data['promotion_percentage'], '20.00')
        self.assertEqual(response.data['promotion_name'], 'Store sale')

    def test_best_matching_promotion_is_displayed(self):
        now = timezone.now()
        store = Promotion.objects.create(
            name='Store sale', percentage=Decimal('10.00'),
            scope=Promotion.Scope.STORE,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
        product_sale = Promotion.objects.create(
            name='Book sale', percentage=Decimal('25.00'),
            scope=Promotion.Scope.PRODUCTS,
            starts_at=now - timedelta(hours=1),
            ends_at=now + timedelta(hours=1),
        )
        product_sale.products.add(self.active)

        response = self.client.get(reverse('product-list'))

        result = response.data['results'][0]
        self.assertEqual(result['promotional_price'], '18.75')
        self.assertEqual(result['promotion_name'], product_sale.name)
        self.assertNotEqual(result['promotion_name'], store.name)

    def test_inactive_or_expired_promotions_are_not_displayed(self):
        now = timezone.now()
        Promotion.objects.create(
            name='Expired sale', percentage=Decimal('50.00'),
            scope=Promotion.Scope.STORE,
            starts_at=now - timedelta(days=2),
            ends_at=now - timedelta(days=1),
        )

        response = self.client.get(
            reverse('product-detail', args=(self.active.slug,))
        )

        self.assertIsNone(response.data['promotional_price'])
        self.assertIsNone(response.data['promotion_percentage'])
        self.assertIsNone(response.data['promotion_name'])

    def test_public_cannot_mutate_catalog(self):
        response = self.client.post(
            reverse('category-list'),
            {'name': 'Games', 'slug': 'games'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_non_staff_cannot_mutate_catalog(self):
        user = User.objects.create_user(username='customer', password='secret')
        self.client.force_authenticate(user)
        response = self.client.delete(
            reverse('product-detail', args=(self.active.slug,))
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_without_catalog_permissions_cannot_mutate_catalog(self):
        staff = User.objects.create_user(
            username='staff-only',
            password='secret',
            is_staff=True,
        )
        self.client.force_authenticate(staff)

        response = self.client.delete(
            reverse('product-detail', args=(self.active.slug,))
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_catalog_managers_group_has_expected_permissions(self):
        group = Group.objects.get(name=CATALOG_MANAGERS_GROUP)
        self.assertEqual(
            group.permissions.filter(
                content_type__app_label='catalog'
            ).count(),
            9,
        )

    def test_staff_can_create_and_see_inactive_products(self):
        staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        grant_catalog_manager(staff)
        self.client.force_authenticate(staff)
        list_response = self.client.get(
            reverse('product-list'),
            {'is_active': 'false'},
        )
        self.assertEqual(list_response.data['count'], 1)
        self.assertEqual(list_response.data['results'][0]['id'], self.inactive.id)

        create_response = self.client.post(
            reverse('product-list'),
            {
                'category': self.category.id,
                'name': 'New Book',
                'slug': 'new-book',
                'price': '8.50',
                'stock_quantity': 3,
                'is_active': True,
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

    def test_filters_search_ordering_and_validation(self):
        Product.objects.create(
            category=self.category,
            name='Advanced Django',
            slug='advanced-django',
            price=Decimal('40.00'),
            stock_quantity=2,
        )
        response = self.client.get(
            reverse('product-list'),
            {
                'category': 'books',
                'min_price': '20',
                'max_price': '30',
                'search': 'Django',
                'ordering': '-price',
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.active.id)

        invalid = self.client.get(
            reverse('product-list'),
            {'min_price': 'not-a-price'},
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_price_and_stock_are_rejected(self):
        staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        grant_catalog_manager(staff)
        self.client.force_authenticate(staff)
        response = self.client.post(
            reverse('product-list'),
            {
                'category': self.category.id,
                'name': 'Invalid',
                'slug': 'invalid',
                'price': '-1.00',
                'stock_quantity': -1,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('price', response.data)
        self.assertIn('stock_quantity', response.data)

    def test_category_with_products_cannot_be_deleted(self):
        staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        grant_catalog_manager(staff)
        self.client.force_authenticate(staff)
        response = self.client.delete(
            reverse('category-detail', args=(self.category.pk,))
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())

    def test_staff_can_replace_catalog_resources_with_put(self):
        staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        grant_catalog_manager(staff)
        self.client.force_authenticate(staff)
        category_response = self.client.put(
            reverse('category-detail', args=(self.category.pk,)),
            {'name': 'Replacement', 'slug': 'replacement'},
            format='json',
        )
        self.assertEqual(category_response.status_code, status.HTTP_200_OK)

        product_response = self.client.put(
            reverse('product-detail', args=(self.active.slug,)),
            {
                'category': self.category.pk,
                'name': 'Replacement Product',
                'slug': 'replacement-product',
                'description': '',
                'price': '1.00',
                'stock_quantity': 1,
                'is_active': True,
            },
            format='json',
        )
        self.assertEqual(product_response.status_code, status.HTTP_200_OK)
        self.category.refresh_from_db()
        self.active.refresh_from_db()
        self.assertEqual(self.category.name, 'Replacement')
        self.assertEqual(self.active.name, 'Replacement Product')

    def test_non_staff_cannot_replace_catalog_resources_with_put(self):
        user = User.objects.create_user(username='customer', password='secret')
        self.client.force_authenticate(user)
        response = self.client.put(
            reverse('category-detail', args=(self.category.pk,)),
            {'name': 'Replacement', 'slug': 'replacement'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ProductImageApiTests(APITestCase):
    def setUp(self):
        self.media_directory = (
            settings.BASE_DIR / 'media' / f'test-{uuid.uuid4().hex}'
        )
        self.media_directory.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.media_directory, True)
        self.settings_override = override_settings(
            MEDIA_ROOT=self.media_directory
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.category = Category.objects.create(name='Books', slug='books')
        self.staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        grant_catalog_manager(self.staff)
        self.client.force_authenticate(self.staff)

    def image_upload(self, image_format='PNG', name=None):
        buffer = io.BytesIO()
        Image.new('RGB', (4, 4), color='blue').save(
            buffer,
            format=image_format,
        )
        extension = {
            'JPEG': 'jpg',
            'PNG': 'png',
            'WEBP': 'webp',
            'GIF': 'gif',
        }[image_format]
        content_type = {
            'JPEG': 'image/jpeg',
            'PNG': 'image/png',
            'WEBP': 'image/webp',
            'GIF': 'image/gif',
        }[image_format]
        return SimpleUploadedFile(
            name or f'product.{extension}',
            buffer.getvalue(),
            content_type=content_type,
        )

    def product_payload(self, slug, image=None):
        payload = {
            'category': str(self.category.pk),
            'name': slug.replace('-', ' ').title(),
            'slug': slug,
            'description': '',
            'price': '10.00',
            'stock_quantity': '3',
            'is_active': 'true',
        }
        if image is not None:
            payload['image'] = image
        return payload

    def test_product_image_is_optional_and_public_response_uses_null(self):
        product = Product.objects.create(
            category=self.category,
            name='No Image',
            slug='no-image',
            price=Decimal('10.00'),
        )
        self.client.force_authenticate(user=None)
        response = self.client.get(
            reverse('product-detail', args=(product.slug,))
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['image'])

    def test_staff_can_upload_supported_image_formats(self):
        for image_format in ('JPEG', 'PNG', 'WEBP'):
            with self.subTest(image_format=image_format):
                slug = f'product-{image_format.lower()}'
                response = self.client.post(
                    reverse('product-list'),
                    self.product_payload(
                        slug,
                        self.image_upload(image_format),
                    ),
                    format='multipart',
                )
                self.assertEqual(
                    response.status_code,
                    status.HTTP_201_CREATED,
                )
                self.assertIn('/media/product_images/', response.data['image'])
                product = Product.objects.get(slug=slug)
                self.assertTrue(os.path.exists(product.image.path))

    def test_invalid_unsupported_and_oversized_images_are_rejected(self):
        invalid = SimpleUploadedFile(
            'invalid.png',
            b'not an image',
            content_type='image/png',
        )
        invalid_response = self.client.post(
            reverse('product-list'),
            self.product_payload('invalid-image', invalid),
            format='multipart',
        )
        self.assertEqual(
            invalid_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn('image', invalid_response.data)

        gif_response = self.client.post(
            reverse('product-list'),
            self.product_payload('gif-image', self.image_upload('GIF')),
            format='multipart',
        )
        self.assertEqual(
            gif_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn('image', gif_response.data)

        oversized_image = self.image_upload('PNG', name='oversized.png')
        oversized = SimpleUploadedFile(
            oversized_image.name,
            oversized_image.read() + b'0' * (5 * 1024 * 1024),
            content_type='image/png',
        )
        oversized_response = self.client.post(
            reverse('product-list'),
            self.product_payload('oversized-image', oversized),
            format='multipart',
        )
        self.assertEqual(
            oversized_response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn('image', oversized_response.data)

    def test_replaced_cleared_and_deleted_images_are_removed_after_commit(self):
        product = Product.objects.create(
            category=self.category,
            name='Image Product',
            slug='image-product',
            price=Decimal('10.00'),
            image=self.image_upload('PNG', name='first.png'),
        )
        first_path = product.image.path
        self.assertTrue(os.path.exists(first_path))

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                reverse('product-detail', args=(product.slug,)),
                {'image': self.image_upload('JPEG', name='second.jpg')},
                format='multipart',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        product.refresh_from_db()
        second_path = product.image.path
        self.assertFalse(os.path.exists(first_path))
        self.assertTrue(os.path.exists(second_path))

        with self.captureOnCommitCallbacks(execute=True):
            clear_response = self.client.patch(
                reverse('product-detail', args=(product.slug,)),
                {'image': None},
                format='json',
            )
        self.assertEqual(clear_response.status_code, status.HTTP_200_OK)
        self.assertFalse(os.path.exists(second_path))

        product.image = self.image_upload('WEBP', name='third.webp')
        product.save()
        third_path = product.image.path
        with self.captureOnCommitCallbacks(execute=True):
            delete_response = self.client.delete(
                reverse('product-detail', args=(product.slug,))
            )
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(os.path.exists(third_path))

    def test_rolled_back_image_clear_does_not_delete_file(self):
        product = Product.objects.create(
            category=self.category,
            name='Rollback Product',
            slug='rollback-product',
            price=Decimal('10.00'),
            image=self.image_upload('PNG'),
        )
        image_path = product.image.path

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                product.image = None
                product.save(update_fields=('image',))
                raise RuntimeError('roll back')

        self.assertTrue(os.path.exists(image_path))
        product.refresh_from_db()
        self.assertTrue(product.image)


class ProductGalleryApiTests(ProductImageApiTests):
    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(
            category=self.category,
            name='Gallery Product',
            slug='gallery-product',
            price=Decimal('10.00'),
            stock_quantity=10,
        )

    def test_product_image_is_registered_with_admin(self):
        self.assertIn(ProductImage, admin.site._registry)

    def test_staff_can_batch_upload_and_public_can_read_in_upload_order(self):
        response = self.client.post(
            reverse(
                'product-image-list-create',
                args=(self.product.pk,),
            ),
            {
                'images': [
                    self.image_upload('PNG', name='first.png'),
                    self.image_upload('JPEG', name='second.jpg'),
                ]
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 2)
        self.assertLess(response.data[0]['id'], response.data[1]['id'])

        self.client.force_authenticate(user=None)
        gallery = self.client.get(
            reverse(
                'product-image-list-create',
                args=(self.product.pk,),
            )
        )
        detail = self.client.get(
            reverse('product-detail', args=(self.product.slug,))
        )
        self.assertEqual(gallery.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item['id'] for item in gallery.data],
            [item['id'] for item in detail.data['gallery_images']],
        )
        self.assertTrue(
            all('/media/product_images/gallery/' in item['image']
                for item in gallery.data)
        )

    def test_gallery_upload_requires_staff_and_inactive_is_hidden_publicly(self):
        customer = User.objects.create_user(
            username='customer',
            password='secret',
        )
        self.client.force_authenticate(customer)
        forbidden = self.client.post(
            reverse(
                'product-image-list-create',
                args=(self.product.pk,),
            ),
            {'images': [self.image_upload()]},
            format='multipart',
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

        self.product.is_active = False
        self.product.save(update_fields=('is_active',))
        self.client.force_authenticate(user=None)
        hidden = self.client.get(
            reverse(
                'product-image-list-create',
                args=(self.product.pk,),
            )
        )
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(self.staff)
        visible = self.client.get(
            reverse(
                'product-image-list-create',
                args=(self.product.pk,),
            )
        )
        self.assertEqual(visible.status_code, status.HTTP_200_OK)

    def test_empty_invalid_batch_and_gallery_limit_are_rejected_atomically(self):
        empty = self.client.post(
            reverse(
                'product-image-list-create',
                args=(self.product.pk,),
            ),
            {},
            format='multipart',
        )
        self.assertEqual(empty.status_code, status.HTTP_400_BAD_REQUEST)

        invalid_batch = self.client.post(
            reverse(
                'product-image-list-create',
                args=(self.product.pk,),
            ),
            {
                'images': [
                    self.image_upload('PNG'),
                    self.image_upload('GIF'),
                ]
            },
            format='multipart',
        )
        self.assertEqual(
            invalid_batch.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(self.product.gallery_images.count(), 0)

        for index in range(9):
            ProductImage.objects.create(
                product=self.product,
                image=self.image_upload(
                    'PNG',
                    name=f'existing-{index}.png',
                ),
            )
        over_limit = self.client.post(
            reverse(
                'product-image-list-create',
                args=(self.product.pk,),
            ),
            {
                'images': [
                    self.image_upload('PNG', name='tenth.png'),
                    self.image_upload('PNG', name='eleventh.png'),
                ]
            },
            format='multipart',
        )
        self.assertEqual(over_limit.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.product.gallery_images.count(), 9)

    def test_gallery_delete_is_product_scoped_and_removes_file_after_commit(self):
        image = ProductImage.objects.create(
            product=self.product,
            image=self.image_upload('PNG'),
        )
        image_path = image.image.path
        other = Product.objects.create(
            category=self.category,
            name='Other Product',
            slug='other-product',
            price=Decimal('1.00'),
        )
        wrong_product = self.client.delete(
            reverse(
                'product-image-delete',
                args=(other.pk, image.pk),
            )
        )
        self.assertEqual(wrong_product.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(os.path.exists(image_path))

        with self.captureOnCommitCallbacks(execute=True):
            deleted = self.client.delete(
                reverse(
                    'product-image-delete',
                    args=(self.product.pk, image.pk),
                )
            )
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(os.path.exists(image_path))

    def test_product_delete_cascades_and_cleans_gallery_files(self):
        first = ProductImage.objects.create(
            product=self.product,
            image=self.image_upload('PNG', name='first.png'),
        )
        second = ProductImage.objects.create(
            product=self.product,
            image=self.image_upload('WEBP', name='second.webp'),
        )
        paths = (first.image.path, second.image.path)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.delete(
                reverse('product-detail', args=(self.product.slug,))
            )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ProductImage.objects.count(), 0)
        self.assertTrue(all(not os.path.exists(path) for path in paths))

    def test_gallery_replacement_cleanup_and_rollback_safety(self):
        gallery_image = ProductImage.objects.create(
            product=self.product,
            image=self.image_upload('PNG', name='original.png'),
        )
        original_path = gallery_image.image.path

        with self.captureOnCommitCallbacks(execute=True):
            gallery_image.image = self.image_upload(
                'JPEG',
                name='replacement.jpg',
            )
            gallery_image.save(update_fields=('image',))
        replacement_path = gallery_image.image.path
        self.assertFalse(os.path.exists(original_path))
        self.assertTrue(os.path.exists(replacement_path))

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                gallery_image.image = self.image_upload(
                    'WEBP',
                    name='rolled-back.webp',
                )
                gallery_image.save(update_fields=('image',))
                raise RuntimeError('roll back')
        self.assertTrue(os.path.exists(replacement_path))
        gallery_image.refresh_from_db()
        self.assertEqual(gallery_image.image.path, replacement_path)
