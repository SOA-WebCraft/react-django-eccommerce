from pathlib import Path

from PIL import Image
from django.conf import settings
from django.core.files import File
from django.core.management import BaseCommand, CommandError

from catalog.models import Product, ProductImage
from invoices.models import Invoice
from orders.models import StoreConfiguration


class Command(BaseCommand):
    help = 'Upload existing public media and private invoices to Cloudinary.'

    def add_arguments(self, parser):
        parser.add_argument('--source-media', required=True, type=Path)
        parser.add_argument('--source-private-media', required=True, type=Path)
        parser.add_argument('--confirm', action='store_true')

    def handle(self, *args, **options):
        if not options['confirm']:
            raise CommandError('Pass --confirm after reviewing both source directories.')
        if not settings.CLOUDINARY_URL:
            raise CommandError('CLOUDINARY_URL must be configured.')
        public_root = options['source_media'].resolve()
        private_root = options['source_private_media'].resolve()
        if not public_root.is_dir() or not private_root.is_dir():
            raise CommandError('Both source media directories must exist.')
        entries = self._entries(public_root, private_root)
        missing = [str(path) for _, _, path, _ in entries if not path.is_file()]
        if missing:
            raise CommandError('Missing source files:\n' + '\n'.join(missing))
        for _, _, path, image in entries:
            if image:
                try:
                    with Image.open(path) as candidate:
                        candidate.verify()
                except Exception as exc:
                    raise CommandError(f'Invalid image: {path}') from exc
        uploaded = 0
        for model, pk, source, field_name in entries:
            instance = model.objects.get(pk=pk)
            field = getattr(instance, field_name)
            old_name = field.name
            with source.open('rb') as handle:
                new_name = field.storage.save(old_name, File(handle, name=source.name))
            model.objects.filter(pk=pk).update(**{field_name: new_name})
            if not field.storage.exists(new_name):
                raise CommandError(f'Cloudinary verification failed for {new_name}.')
            uploaded += 1
        self.stdout.write(self.style.SUCCESS(f'Uploaded and verified {uploaded} files.'))

    @staticmethod
    def _entries(public_root, private_root):
        entries = []
        for product in Product.objects.exclude(image='').exclude(image__isnull=True):
            entries.append((Product, product.pk, public_root / product.image.name, 'image'))
        for image in ProductImage.objects.exclude(image='').exclude(image__isnull=True):
            entries.append((ProductImage, image.pk, public_root / image.image.name, 'image'))
        for store in StoreConfiguration.objects.exclude(logo='').exclude(logo__isnull=True):
            entries.append((StoreConfiguration, store.pk, public_root / store.logo.name, 'logo'))
        for invoice in Invoice.objects.exclude(pdf_file='').exclude(pdf_file__isnull=True):
            entries.append((
                Invoice, invoice.pk,
                private_root / 'invoices' / invoice.pdf_file.name,
                'pdf_file',
            ))
        return entries
