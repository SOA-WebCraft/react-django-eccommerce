from django.conf import settings
from django.core.files.storage import FileSystemStorage

from config.storage import PrivateCloudinaryStorage


def private_invoice_storage():
    if settings.CLOUDINARY_URL:
        return PrivateCloudinaryStorage()
    return FileSystemStorage(
        location=settings.PRIVATE_MEDIA_ROOT / 'invoices',
        base_url=None,
    )
