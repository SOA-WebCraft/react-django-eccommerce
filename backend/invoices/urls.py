from django.urls import path

from .views import InvoiceDetailView, InvoiceDownloadView


urlpatterns = [
    path('invoices/<uuid:pk>/', InvoiceDetailView.as_view(), name='invoice-detail'),
    path(
        'invoices/<uuid:pk>/download/',
        InvoiceDownloadView.as_view(),
        name='invoice-download',
    ),
]
