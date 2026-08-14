from django.http import FileResponse, Http404
from rest_framework import generics, permissions
from rest_framework.exceptions import APIException
from rest_framework.views import APIView

from .models import Invoice
from .serializers import InvoiceSerializer
from .services import generate_invoice_pdf


class InvoiceGenerationUnavailable(APIException):
    status_code = 503
    default_detail = 'Invoice PDF is being prepared. Please try again later.'


class InvoiceDetailView(generics.RetrieveAPIView):
    serializer_class = InvoiceSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_queryset(self):
        return Invoice.objects.filter(customer=self.request.user)


class InvoiceDownloadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk):
        try:
            invoice = Invoice.objects.get(pk=pk, customer=request.user)
        except Invoice.DoesNotExist as exc:
            raise Http404('Invoice not found.') from exc
        if not invoice.pdf_file:
            try:
                generate_invoice_pdf(invoice)
            except (ImportError, OSError, RuntimeError) as exc:
                raise InvoiceGenerationUnavailable() from exc
        response = FileResponse(
            invoice.pdf_file.open('rb'),
            as_attachment=True,
            filename=f'{invoice.invoice_number}.pdf',
            content_type='application/pdf',
        )
        return response
