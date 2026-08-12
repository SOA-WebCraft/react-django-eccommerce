import json
from pathlib import Path
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import TransactionTestCase

from catalog.models import Category, Product


User = get_user_model()


class ProductionDataMigrationTests(TransactionTestCase):
    reset_sequences = True

    def test_export_and_import_preserve_records_and_password_hashes(self):
        user = User.objects.create_user(
            username='migration-user', email='migration@example.com',
            password='safe-password-123',
        )
        password_hash = user.password
        category = Category.objects.create(name='Migration', slug='migration')
        Product.objects.create(
            category=category, name='Migration Product',
            slug='migration-product', price='25.00', stock_quantity=3,
        )
        fixture = settings.BASE_DIR / '.test_tmp' / f'production-{uuid4().hex}.json'
        try:
            call_command('export_production_data', fixture, confirm=True, verbosity=0)
            manifest = json.loads(
                fixture.with_suffix('.manifest.json').read_text(encoding='utf-8')
            )
            self.assertEqual(manifest['counts']['auth.User'], 1)
            call_command('flush', interactive=False, verbosity=0)
            call_command(
                'import_production_data', fixture,
                confirm_empty=True, verbosity=0,
            )
        finally:
            fixture.unlink(missing_ok=True)
            fixture.with_suffix('.manifest.json').unlink(missing_ok=True)
        restored = User.objects.get(username='migration-user')
        self.assertEqual(restored.password, password_hash)
        self.assertTrue(restored.check_password('safe-password-123'))
        self.assertTrue(Product.objects.filter(slug='migration-product').exists())

    def test_export_requires_confirmation(self):
        fixture = settings.BASE_DIR / '.test_tmp' / f'production-{uuid4().hex}.json'
        try:
            with self.assertRaises(CommandError):
                call_command('export_production_data', fixture)
        finally:
            fixture.unlink(missing_ok=True)
