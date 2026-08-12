from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from PIL import Image

from .models import Category, Product, ProductImage
from .management.commands.seed_catalog import SMARTPHONE_IMAGES


class SeedCatalogCommandTests(TestCase):
    def run_command(self, **options):
        output = StringIO()
        call_command('seed_catalog', stdout=output, **options)
        return output.getvalue()

    def test_command_creates_complete_catalog_with_defaults(self):
        output = self.run_command()

        self.assertEqual(Category.objects.count(), 5)
        self.assertEqual(Product.objects.count(), 50)
        self.assertIn('5 categories created', output)
        self.assertIn('50 products created', output)

        iphone = Product.objects.get(slug='apple-iphone-16-pro')
        self.assertEqual(iphone.name, 'Apple iPhone 16 Pro')
        self.assertEqual(iphone.category.slug, 'smartphones')
        self.assertIn('Overview\n', iphone.description)
        self.assertIn('Display and design\n', iphone.description)
        self.assertIn('Performance and storage\n', iphone.description)
        self.assertIn('Cameras\n', iphone.description)
        self.assertIn('Battery and connectivity\n', iphone.description)
        self.assertIn('A18 Pro', iphone.description)
        self.assertEqual(iphone.price, Decimal('999.00'))
        self.assertEqual(iphone.stock_quantity, 10)
        self.assertTrue(iphone.is_active)
        self.assertEqual(
            iphone.image.name,
            'product_images/generated/apple-iphone-16-pro.png',
        )
        self.assertEqual(iphone.gallery_images.count(), 3)
        self.assertIn('30 gallery images created', output)

        charger = Product.objects.get(
            slug='belkin-65w-usb-c-fast-charger'
        )
        self.assertEqual(charger.category.slug, 'accessories')
        self.assertEqual(
            charger.description,
            'An accessory available in our catalog.',
        )

    def test_command_is_idempotent(self):
        self.run_command()
        output = self.run_command()

        self.assertEqual(Category.objects.count(), 5)
        self.assertEqual(Product.objects.count(), 50)
        self.assertIn('0 categories created', output)
        self.assertIn('5 categories existing', output)
        self.assertIn('0 products created', output)
        self.assertIn('50 products existing', output)
        self.assertIn('0 prices initialized', output)
        self.assertIn('0 gallery images created', output)
        self.assertIn('30 gallery images existing', output)
        self.assertEqual(ProductImage.objects.count(), 30)

    def test_command_does_not_overwrite_staff_edits(self):
        self.run_command()
        product = Product.objects.get(slug='apple-iphone-16-pro')
        product.price = Decimal('999.99')
        product.stock_quantity = 2
        product.description = 'Staff-authored description.'
        product.is_active = False
        product.save()

        self.run_command()
        product.refresh_from_db()

        self.assertEqual(product.price, Decimal('999.99'))
        self.assertEqual(product.stock_quantity, 2)
        self.assertEqual(product.description, 'Staff-authored description.')
        self.assertFalse(product.is_active)

    def test_command_preserves_staff_images(self):
        self.run_command()
        product = Product.objects.get(slug='apple-iphone-16-pro')
        product.image = 'product_images/staff-primary.png'
        product.save(update_fields=('image', 'updated_at'))
        staff_gallery = ProductImage.objects.create(
            product=product,
            image='product_images/gallery/staff-gallery.png',
        )

        self.run_command()
        product.refresh_from_db()

        self.assertEqual(product.image.name, 'product_images/staff-primary.png')
        self.assertTrue(
            ProductImage.objects.filter(pk=staff_gallery.pk).exists()
        )
        self.assertEqual(product.gallery_images.count(), 4)

    def test_seeded_smartphone_images_exist_and_are_valid_pngs(self):
        self.run_command()

        for slug, manifest in SMARTPHONE_IMAGES.items():
            product = Product.objects.get(slug=slug)
            self.assertEqual(product.image.name, manifest['primary'])
            self.assertEqual(
                list(
                    product.gallery_images.values_list('image', flat=True)
                ),
                list(manifest['gallery']),
            )
            for product_image in product.gallery_images.all():
                with Image.open(product_image.image.path) as image:
                    self.assertEqual(image.format, 'PNG')
                    self.assertEqual(image.size, (1254, 1254))

    def test_refresh_only_updates_curated_descriptions(self):
        self.run_command()
        product = Product.objects.get(slug='apple-iphone-16-pro')
        category = product.category
        product.price = Decimal('999.99')
        product.stock_quantity = 2
        product.description = 'Staff-authored description.'
        product.is_active = False
        product.save()

        output = self.run_command(refresh_descriptions=True)
        product.refresh_from_db()

        self.assertIn('1 descriptions refreshed', output)
        self.assertIn('A18 Pro', product.description)
        self.assertEqual(product.category, category)
        self.assertEqual(product.price, Decimal('999.99'))
        self.assertEqual(product.stock_quantity, 2)
        self.assertFalse(product.is_active)

    def test_refresh_updates_all_smartphone_descriptions(self):
        self.run_command()
        Product.objects.filter(category__slug='smartphones').update(
            description='Outdated description.'
        )

        output = self.run_command(refresh_descriptions=True)
        smartphones = Product.objects.filter(category__slug='smartphones')

        self.assertIn('10 descriptions refreshed', output)
        self.assertEqual(smartphones.count(), 10)
        for product in smartphones:
            self.assertIn('Overview\n', product.description)
            self.assertIn('Cameras\n', product.description)
            self.assertIn('Battery and connectivity\n', product.description)
