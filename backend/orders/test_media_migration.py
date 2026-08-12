from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from catalog.models import Category, Product
from invoices.models import Invoice
from orders.management.commands.migrate_media_to_cloudinary import Command
from orders.models import Order


class MediaMigrationEntryTests(TestCase):
    def test_invoice_is_not_marked_as_an_image(self):
        user = get_user_model().objects.create_user(username='media-user')
        order = Order.objects.create(user=user, total='0.00')
        Invoice.objects.create(
            order=order,
            customer=user,
            invoice_number='INV-MEDIA-0001',
            subtotal='0.00',
            total='0.00',
            pdf_file='2026/08/invoice.pdf',
        )
        category = Category.objects.create(name='Media', slug='media')
        Product.objects.create(
            category=category,
            name='Media Product',
            slug='media-product',
            price='0.00',
            stock_quantity=1,
            image='product_images/product.png',
        )

        entries = Command._entries(Path('public-media'), Path('private-media'))

        image_entry = next(entry for entry in entries if entry[0] is Product)
        invoice_entry = next(entry for entry in entries if entry[0] is Invoice)
        self.assertTrue(image_entry[4])
        self.assertFalse(invoice_entry[4])
        self.assertEqual(invoice_entry[3], 'pdf_file')
