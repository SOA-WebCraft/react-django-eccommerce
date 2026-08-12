import hashlib
import json
from io import StringIO
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command


EXPORT_LABELS = (
    'auth.Group',
    'auth.User',
    'users.Profile',
    'catalog.Category',
    'catalog.Product',
    'catalog.ProductImage',
    'catalog.Supplier',
    'catalog.PurchaseOrder',
    'catalog.PurchaseOrderItem',
    'catalog.StockMovement',
    'cart.Cart',
    'cart.CartItem',
    'orders.Order',
    'orders.OrderItem',
    'orders.OrderTimelineEvent',
    'orders.ReturnRequest',
    'orders.RefundRequest',
    'orders.Coupon',
    'orders.Promotion',
    'orders.GiftCard',
    'orders.CheckoutAttempt',
    'orders.CheckoutItem',
    'orders.PaymentTransaction',
    'orders.GiftCardTransaction',
    'orders.ShippingMethod',
    'orders.ShippingZone',
    'orders.ShippingRate',
    'orders.StoreConfiguration',
    'invoices.InvoiceSequence',
    'invoices.Invoice',
)


class Command(BaseCommand):
    help = 'Export approved application data from local SQLite for production.'

    def add_arguments(self, parser):
        parser.add_argument('output', type=Path)
        parser.add_argument('--confirm', action='store_true')

    def handle(self, *args, **options):
        if not options['confirm']:
            raise CommandError('Pass --confirm after reviewing the export path.')
        if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('This command exports only from the local SQLite database.')
        output = options['output'].resolve()
        if output.suffix.lower() != '.json':
            raise CommandError('The output path must end in .json.')
        output.parent.mkdir(parents=True, exist_ok=True)
        stream = StringIO()
        call_command(
            'dumpdata', *EXPORT_LABELS, format='json', indent=2,
            use_natural_foreign_keys=True, stdout=stream,
        )
        payload = stream.getvalue()
        temporary = output.with_suffix('.json.tmp')
        temporary.write_text(payload, encoding='utf-8')
        temporary.replace(output)
        fixture_bytes = output.read_bytes()
        counts = {
            label: apps.get_model(label).objects.count()
            for label in EXPORT_LABELS
        }
        manifest = {
            'fixture': output.name,
            'sha256': hashlib.sha256(fixture_bytes).hexdigest(),
            'counts': counts,
        }
        manifest_path = output.with_suffix('.manifest.json')
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(
            f'Exported {sum(counts.values())} records to {output}. '
            f'Manifest: {manifest_path}'
        ))
