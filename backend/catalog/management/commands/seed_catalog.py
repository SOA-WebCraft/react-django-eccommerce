from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from catalog.models import Category, Product, ProductImage
from catalog.management.commands.smartphone_descriptions import (
    SMARTPHONE_DESCRIPTIONS,
)


CATALOG = {
    'Smartphones': (
        'Apple iPhone 16 Pro',
        'Samsung Galaxy S25 Ultra',
        'Google Pixel 9 Pro',
        'OnePlus 13',
        'Xiaomi 15 Pro',
        'Nothing Phone (3)',
        'Motorola Edge 60 Pro',
        'OPPO Find X8 Pro',
        'vivo X200 Pro',
        'ASUS ROG Phone 9',
    ),
    'Laptops': (
        'Apple MacBook Air M4',
        'Dell XPS 13',
        'HP Spectre x360',
        'Lenovo ThinkPad X1 Carbon',
        'ASUS Zenbook 14 OLED',
        'Acer Swift Go 14',
        'Microsoft Surface Laptop 7',
        'MSI Stealth 16 AI',
        'Razer Blade 16',
        'Samsung Galaxy Book5 Pro',
    ),
    'Tablets': (
        'Apple iPad Pro 13-inch',
        'Apple iPad Air 11-inch',
        'Samsung Galaxy Tab S10 Ultra',
        'Lenovo Tab P12 Pro',
        'Xiaomi Pad 7 Pro',
        'OnePlus Pad 2',
        'Microsoft Surface Pro 11',
        'Amazon Fire Max 11',
        'HONOR MagicPad 2',
        'Huawei MatePad Pro',
    ),
    'Smartwatches': (
        'Apple Watch Series 10',
        'Samsung Galaxy Watch Ultra',
        'Google Pixel Watch 3',
        'Garmin Fenix 8',
        'Huawei Watch GT 5 Pro',
        'Amazfit Balance',
        'Fitbit Sense 2',
        'OnePlus Watch 3',
        'Xiaomi Watch S4',
        'Suunto Race S',
    ),
    'Accessories': (
        'Anker 20,000mAh Power Bank',
        'Apple AirPods Pro (2nd Gen)',
        'Samsung Galaxy Buds3 Pro',
        'Belkin 65W USB-C Fast Charger',
        'Logitech MX Master 3S Wireless Mouse',
        'SanDisk Extreme Portable SSD 1TB',
        'UGREEN USB-C Hub 7-in-1',
        'Spigen Rugged Armor Phone Case',
        'JBL Flip 7 Bluetooth Speaker',
        'Baseus MagSafe Wireless Charger',
    ),
}

DESCRIPTIONS = {
    'Smartphones': 'A smartphone available in our catalog.',
    'Laptops': 'A laptop available in our catalog.',
    'Tablets': 'A tablet available in our catalog.',
    'Smartwatches': 'A smartwatch available in our catalog.',
    'Accessories': 'An accessory available in our catalog.',
}

DEFAULT_PRICES = {
    'Smartphones': Decimal('999.00'),
    'Laptops': Decimal('1299.00'),
    'Tablets': Decimal('599.00'),
    'Smartwatches': Decimal('399.00'),
    'Accessories': Decimal('79.00'),
}

PRODUCT_DESCRIPTIONS = {
    'Apple iPhone 16 Pro': (
        'A premium Apple smartphone with a refined titanium design, powerful '
        'everyday performance, an advanced camera experience, and seamless '
        'integration with the Apple ecosystem.'
    ),
    'Samsung Galaxy S25 Ultra': (
        'A flagship Samsung smartphone built for productivity and creativity, '
        'with a large immersive display, versatile cameras, and a premium '
        'design suited to demanding users.'
    ),
    'Google Pixel 9 Pro': (
        'A polished Google smartphone combining a clean Android experience, '
        'helpful AI-powered features, and an intelligent camera system for '
        'effortless everyday photography.'
    ),
    'OnePlus 13': (
        'A fast, refined flagship smartphone with a smooth display, responsive '
        'performance, capable cameras, and a premium design for work, play, '
        'and everyday use.'
    ),
    'Xiaomi 15 Pro': (
        'A premium Xiaomi smartphone offering flagship performance, a vivid '
        'display, versatile photography features, and an elegant design for '
        'users who want a powerful all-round device.'
    ),
    'Nothing Phone (3)': (
        'A distinctive smartphone with Nothing’s transparent-inspired design '
        'language, a clean and intuitive software experience, and smooth '
        'performance for modern everyday use.'
    ),
    'Motorola Edge 60 Pro': (
        'A stylish Motorola smartphone with an immersive edge-to-edge display, '
        'balanced performance, and versatile cameras in a comfortable premium '
        'design.'
    ),
    'OPPO Find X8 Pro': (
        'A sophisticated OPPO flagship with a premium finish, smooth '
        'performance, a vibrant display, and a versatile camera experience '
        'for photos, video, and daily use.'
    ),
    'vivo X200 Pro': (
        'A camera-focused vivo flagship combining premium performance, an '
        'immersive display, and versatile imaging features in a sleek, '
        'modern design.'
    ),
    'ASUS ROG Phone 9': (
        'A high-performance gaming smartphone designed for responsive play, '
        'with an immersive display, bold ROG styling, and the power needed '
        'for demanding mobile games and entertainment.'
    ),
}

PRODUCT_DESCRIPTIONS.update(SMARTPHONE_DESCRIPTIONS)

SMARTPHONE_IMAGES = {
    slugify(product_name): {
        'primary': f'product_images/generated/{slugify(product_name)}.png',
        'gallery': tuple(
            f'product_images/gallery/generated/{slugify(product_name)}-{view}.png'
            for view in ('front', 'rear', 'side')
        ),
    }
    for product_name in CATALOG['Smartphones']
}


class Command(BaseCommand):
    help = 'Populate the catalog with the standard electronics product set.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--refresh-descriptions',
            action='store_true',
            help='Restore curated descriptions without changing other fields.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        created_categories = 0
        existing_categories = 0
        created_products = 0
        existing_products = 0
        refreshed_descriptions = 0
        initialized_prices = 0
        created_gallery_images = 0
        existing_gallery_images = 0

        self._validate_seed_images()

        for category_name, product_names in CATALOG.items():
            category, category_created = Category.objects.get_or_create(
                slug=slugify(category_name),
                defaults={'name': category_name},
            )
            if category_created:
                created_categories += 1
            else:
                existing_categories += 1

            for product_name in product_names:
                product, product_created = Product.objects.get_or_create(
                    slug=slugify(product_name),
                    defaults={
                        'category': category,
                        'name': product_name,
                        'description': PRODUCT_DESCRIPTIONS.get(
                            product_name,
                            DESCRIPTIONS[category_name],
                        ),
                        'price': DEFAULT_PRICES[category_name],
                        'stock_quantity': 10,
                        'is_active': True,
                    },
                )
                if product_created:
                    created_products += 1
                else:
                    existing_products += 1
                    if product.price == Decimal('0.00'):
                        product.price = DEFAULT_PRICES[category_name]
                        product.save(update_fields=('price', 'updated_at'))
                        initialized_prices += 1
                    description = PRODUCT_DESCRIPTIONS.get(product_name)
                    if (
                        options['refresh_descriptions']
                        and description is not None
                        and product.description != description
                    ):
                        product.description = description
                        product.save(update_fields=('description', 'updated_at'))
                        refreshed_descriptions += 1

                image_manifest = SMARTPHONE_IMAGES.get(product.slug)
                if image_manifest is None:
                    continue

                if not product.image:
                    product.image = image_manifest['primary']
                    product.save(update_fields=('image', 'updated_at'))

                for image_path in image_manifest['gallery']:
                    if ProductImage.objects.filter(
                        product=product,
                        image=image_path,
                    ).exists():
                        existing_gallery_images += 1
                    else:
                        ProductImage.objects.create(
                            product=product,
                            image=image_path,
                        )
                        created_gallery_images += 1

        self.stdout.write(
            self.style.SUCCESS(
                'Catalog seed complete: '
                f'{created_categories} categories created, '
                f'{existing_categories} categories existing; '
                f'{created_products} products created, '
                f'{existing_products} products existing; '
                f'{initialized_prices} prices initialized; '
                f'{refreshed_descriptions} descriptions refreshed; '
                f'{created_gallery_images} gallery images created, '
                f'{existing_gallery_images} gallery images existing.'
            )
        )

    @staticmethod
    def _validate_seed_images():
        missing = []
        for manifest in SMARTPHONE_IMAGES.values():
            paths = (manifest['primary'], *manifest['gallery'])
            missing.extend(
                path
                for path in paths
                if not (Path(settings.MEDIA_ROOT) / path).is_file()
            )
        if missing:
            formatted = ', '.join(sorted(missing))
            raise FileNotFoundError(
                f'Catalog seed image files are missing: {formatted}'
            )
