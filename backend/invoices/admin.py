from django.contrib import admin

from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer', 'status', 'total', 'issued_at')
    search_fields = ('invoice_number', 'customer__username')
    list_filter = ('status', 'issued_at')
