from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from .models import Invoice, InvoiceSequence


def _next_invoice_number():
    year = timezone.now().year
    sequence, _ = InvoiceSequence.objects.select_for_update().get_or_create(
        year=year,
        defaults={'next_value': 1},
    )
    value = sequence.next_value
    sequence.next_value += 1
    sequence.save(update_fields=('next_value',))
    return f'INV-{year}-{value:06d}'


@transaction.atomic
def create_invoice(order, status=Invoice.Status.PAID):
    existing = Invoice.objects.filter(order=order).first()
    if existing:
        return existing
    address = ', '.join(
        value for value in (
            order.address,
            order.city,
            order.postal_code,
            order.country,
        ) if value
    )
    return Invoice.objects.create(
        order=order,
        customer=order.user,
        invoice_number=_next_invoice_number(),
        status=status,
        subtotal=order.subtotal or order.total,
        tax=order.tax,
        shipping=order.shipping,
        discount=order.discount,
        total=order.total,
        currency=order.currency,
        billing_name=order.billing_name or order.user.get_full_name(),
        billing_email=order.billing_email or order.user.email,
        billing_address=address,
        payment_method=order.payment_method,
    )


def generate_invoice_pdf(invoice):
    from weasyprint import HTML

    html = render_to_string(
        'invoices/invoice.html',
        {
            'invoice': invoice,
            'company_name': settings.INVOICE_COMPANY_NAME,
            'company_address': settings.INVOICE_COMPANY_ADDRESS,
            'support_email': settings.INVOICE_SUPPORT_EMAIL,
            'tax_id': settings.INVOICE_TAX_ID,
        },
    )
    pdf = HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
    filename = f'{invoice.invoice_number}.pdf'
    invoice.pdf_file.save(filename, ContentFile(pdf), save=False)
    invoice.pdf_generated_at = timezone.now()
    invoice.save(update_fields=('pdf_file', 'pdf_generated_at'))
    return invoice.pdf_file
