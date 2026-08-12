from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings

from .environment import allowed_hosts, database_configuration
from .storage import PrivateCloudinaryStorage, PublicCloudinaryStorage


class ProductionDatabaseSettingsTests(SimpleTestCase):
    def test_render_hostname_is_added_to_allowed_hosts(self):
        self.assertEqual(
            allowed_hosts(
                'localhost,api.example.com',
                'react-django-eccommerce.onrender.com',
            ),
            [
                'localhost',
                'api.example.com',
                'react-django-eccommerce.onrender.com',
            ],
        )

    def test_duplicate_platform_hostname_is_not_added(self):
        self.assertEqual(
            allowed_hosts('api.example.com', 'api.example.com'),
            ['api.example.com'],
        )

    def test_csrf_origin_hostname_is_allowed_for_same_origin_proxy(self):
        self.assertEqual(
            allowed_hosts(
                'api.example.com',
                trusted_origins='https://ecco-storefront.vercel.app',
            ),
            ['api.example.com', 'ecco-storefront.vercel.app'],
        )

    def test_production_frontend_hostname_is_allowed(self):
        self.assertIn(
            'ecco-storefront.vercel.app',
            allowed_hosts(
                'api.example.com',
                trusted_origins='https://ecco-storefront.vercel.app',
            ),
        )

    def test_empty_database_url_preserves_sqlite_fallback(self):
        self.assertIsNone(database_configuration('', debug=True))

    def test_postgres_url_enables_health_checks_and_ssl(self):
        value = database_configuration(
            'postgresql://store:secret@database.example/ecco', debug=False,
        )
        self.assertEqual(value['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(value['CONN_MAX_AGE'], 600)
        self.assertTrue(value['CONN_HEALTH_CHECKS'])
        self.assertEqual(value['OPTIONS']['sslmode'], 'require')


@override_settings(CLOUDINARY_URL='cloudinary://key:secret@example')
class CloudinaryStorageTests(SimpleTestCase):
    @patch('config.storage.cloudinary.config')
    @patch('config.storage.cloudinary.uploader.upload')
    def test_public_upload_returns_cloudinary_reference(self, upload, config):
        upload.return_value = {'public_id': 'product_images/phone-abc', 'format': 'webp'}
        storage = PublicCloudinaryStorage()
        name = storage._save('product_images/phone.webp', ContentFile(b'image'))
        self.assertEqual(name, 'product_images/phone-abc.webp')
        self.assertEqual(upload.call_args.kwargs['type'], 'upload')
        self.assertNotIn('secret', str(upload.call_args))

    @patch('config.storage.cloudinary.config')
    @patch('config.storage.cloudinary.uploader.upload')
    def test_invoice_upload_is_authenticated(self, upload, config):
        upload.return_value = {'public_id': 'invoices/2026/invoice-abc.pdf'}
        storage = PrivateCloudinaryStorage()
        name = storage._save('2026/invoice.pdf', ContentFile(b'%PDF'))
        self.assertEqual(name, 'invoices/2026/invoice-abc.pdf')
        self.assertEqual(upload.call_args.kwargs['resource_type'], 'raw')
        self.assertEqual(upload.call_args.kwargs['type'], 'authenticated')

    @patch('config.storage.cloudinary.config')
    @patch('config.storage.cloudinary.utils.private_download_url')
    def test_invoice_url_is_signed_and_short_lived(self, private_url, config):
        private_url.return_value = 'https://cloudinary.example/private'
        storage = PrivateCloudinaryStorage()
        with patch('config.storage.time.time', return_value=1000):
            self.assertEqual(
                storage.private_url('invoices/invoice.pdf'),
                'https://cloudinary.example/private',
            )
        self.assertEqual(private_url.call_args.kwargs['expires_at'], 1300)
        self.assertEqual(private_url.call_args.kwargs['type'], 'authenticated')
