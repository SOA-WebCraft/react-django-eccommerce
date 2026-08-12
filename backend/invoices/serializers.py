from rest_framework import serializers

from .models import Invoice


class InvoiceSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = (
            'id',
            'invoice_number',
            'status',
            'issued_at',
            'subtotal',
            'discount',
            'shipping',
            'tax',
            'total',
            'currency',
            'pdf_generated_at',
            'download_url',
        )
        read_only_fields = fields

    def get_download_url(self, invoice):
        return f'/api/invoices/{invoice.pk}/download/'
