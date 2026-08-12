import hashlib
import json
from pathlib import Path

from django.apps import apps
from django.core.management import BaseCommand, CommandError, call_command
from django.db import transaction

from .export_production_data import EXPORT_LABELS


class Command(BaseCommand):
    help = 'Import an approved production fixture into an empty migrated database.'

    def add_arguments(self, parser):
        parser.add_argument('fixture', type=Path)
        parser.add_argument('--confirm-empty', action='store_true')

    def handle(self, *args, **options):
        if not options['confirm_empty']:
            raise CommandError('Pass --confirm-empty after verifying the target database.')
        fixture = options['fixture'].resolve()
        manifest_path = fixture.with_suffix('.manifest.json')
        if not fixture.is_file() or not manifest_path.is_file():
            raise CommandError('Both fixture and matching .manifest.json are required.')
        payload = fixture.read_bytes()
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if hashlib.sha256(payload).hexdigest() != manifest.get('sha256'):
            raise CommandError('Fixture checksum does not match its manifest.')
        occupied = {
            label: apps.get_model(label).objects.count()
            for label in EXPORT_LABELS
            if label not in {'auth.Group', 'orders.StoreConfiguration'}
            if apps.get_model(label).objects.exists()
        }
        if occupied:
            raise CommandError(
                'Target application tables are not empty: '
                + ', '.join(f'{key}={value}' for key, value in occupied.items())
            )
        with transaction.atomic():
            apps.get_model('auth.Group').objects.all().delete()
            apps.get_model('orders.StoreConfiguration').objects.all().delete()
            call_command('loaddata', str(fixture), verbosity=0)
            actual = {
                label: apps.get_model(label).objects.count()
                for label in EXPORT_LABELS
            }
            expected = manifest['counts']
            mismatches = {
                label: (expected.get(label), actual[label])
                for label in EXPORT_LABELS
                if expected.get(label) != actual[label]
            }
            if mismatches:
                raise CommandError(f'Imported record counts do not match: {mismatches}')
        self.stdout.write(self.style.SUCCESS(
            f'Imported and verified {sum(actual.values())} records.'
        ))
