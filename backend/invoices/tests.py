from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from orders.models import Order

from .models import Invoice
from .services import create_invoice


User = get_user_model()


@override_settings(PRIVATE_MEDIA_ROOT='test-private-media')
class InvoiceApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='secret')
        self.other = User.objects.create_user(username='bob', password='secret')
        self.order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('10.00'),
            total=Decimal('10.00'),
        )
        self.client.force_authenticate(self.user)

    def tearDown(self):
        for invoice in Invoice.objects.all():
            if invoice.pdf_file:
                invoice.pdf_file.delete(save=False)

    def test_invoice_number_sequence_and_idempotency(self):
        first = create_invoice(self.order)
        same = create_invoice(self.order)
        second_order = Order.objects.create(
            user=self.user,
            subtotal=Decimal('2.00'),
            total=Decimal('2.00'),
        )
        second = create_invoice(second_order)
        self.assertEqual(first.pk, same.pk)
        self.assertTrue(first.invoice_number.endswith('000001'))
        self.assertTrue(second.invoice_number.endswith('000002'))

    def test_invoice_metadata_and_download_are_owner_scoped(self):
        invoice = create_invoice(self.order)
        invoice.pdf_file.save(
            'invoice.pdf',
            ContentFile(b'%PDF-1.7\n%%EOF'),
        )
        detail = self.client.get(reverse('invoice-detail', args=(invoice.pk,)))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(detail.data['invoice_number'], invoice.invoice_number)
        self.client.force_authenticate(self.other)
        self.assertEqual(
            self.client.get(reverse('invoice-detail', args=(invoice.pk,))).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(reverse('invoice-download', args=(invoice.pk,))).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_staff_does_not_gain_access_to_another_users_invoice(self):
        invoice = create_invoice(self.order)
        staff = User.objects.create_user(
            username='staff',
            password='secret',
            is_staff=True,
        )
        self.client.force_authenticate(staff)
        self.assertEqual(
            self.client.get(reverse('invoice-detail', args=(invoice.pk,))).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(reverse('invoice-download', args=(invoice.pk,))).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    @patch('invoices.views.generate_invoice_pdf')
    def test_missing_pdf_is_regenerated_for_authorized_download(self, generate):
        invoice = create_invoice(self.order)

        def attach_pdf(target):
            target.pdf_file.save(
                'generated.pdf',
                ContentFile(b'%PDF-1.7\n%%EOF'),
            )

        generate.side_effect = attach_pdf
        response = self.client.get(
            reverse('invoice-download', args=(invoice.pk,))
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        response.close()
        generate.assert_called_once()
