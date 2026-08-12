from django.core.management.base import BaseCommand

from invoices.models import Invoice
from invoices.services import create_invoice, generate_invoice_pdf
from orders.models import Order


class Command(BaseCommand):
    help = 'Create draft PDF invoices for legacy orders without invoices.'

    def handle(self, *args, **options):
        created = 0
        existing = 0
        generated = 0
        unavailable = False
        for order in Order.objects.prefetch_related('items').iterator(
            chunk_size=200,
        ):
            if hasattr(order, 'invoice'):
                invoice = order.invoice
                existing += 1
            else:
                invoice = create_invoice(order, status=Invoice.Status.DRAFT)
                created += 1
            if invoice.pdf_file:
                continue
            try:
                generate_invoice_pdf(invoice)
            except (ImportError, OSError, RuntimeError):
                unavailable = True
            else:
                generated += 1
        if unavailable:
            self.stdout.write(self.style.WARNING(
                'Some PDFs were not generated because WeasyPrint native '
                'libraries are unavailable. Install Pango/MSYS2 and retry.'
            ))
        self.stdout.write(
            self.style.SUCCESS(
                f'Legacy invoices created: {created}; existing: {existing}; '
                f'PDFs generated: {generated}.'
            )
        )
