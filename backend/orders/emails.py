import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import Order, StoreConfiguration


logger = logging.getLogger(__name__)


def send_order_confirmation(order_id):
    email_settings = StoreConfiguration.load()
    if not (
        email_settings.send_order_emails
        or email_settings.send_invoice_emails
    ):
        return False
    with transaction.atomic():
        order = (
            Order.objects.select_for_update()
            .select_related('user')
            .prefetch_related('items')
            .get(pk=order_id)
        )
        if order.confirmation_email_sent_at:
            return False
        recipient = order.billing_email or order.user.email
        if not recipient:
            logger.info(
                'Order %s has no email address for purchase confirmation.',
                order.order_number,
            )
            return False
        item_lines = '\n'.join(
            f'- {item.product_name} x {item.quantity}: '
            f'{order.currency} {item.line_total}'
            for item in order.items.all()
        )
        order_url = f'{settings.FRONTEND_BASE_URL}/account/orders/{order.pk}'
        message = (
            f'Hello {order.billing_name or order.user.get_username()},\n\n'
            f'Thank you for your purchase. Your payment for order '
            f'{order.order_number} was successful.\n\n'
            f'{item_lines}\n\n'
            f'Total: {order.currency} {order.total}\n'
            f'Status: {order.get_status_display()}\n\n'
            f'View your order and invoice: {order_url}\n\n'
            'Thank you for shopping with ECCO.'
        )
        try:
            send_mail(
                f'ECCO order {order.order_number} confirmed',
                message,
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )
        except Exception:
            logger.exception(
                'Purchase confirmation delivery failed for order %s.',
                order.order_number,
            )
            return False
        order.confirmation_email_sent_at = timezone.now()
        order.save(update_fields=('confirmation_email_sent_at',))
        return True


def send_order_status_email(order_id):
    if not StoreConfiguration.load().send_order_emails:
        return False
    order = Order.objects.select_related('user').get(pk=order_id)
    recipient = order.billing_email or order.user.email
    if not recipient:
        return False
    tracking = (
        f'\nTracking number: {order.tracking_number}'
        if order.tracking_number else ''
    )
    order_url = f'{settings.FRONTEND_BASE_URL}/account/orders/{order.pk}'
    try:
        send_mail(
            f'ECCO order {order.order_number}: {order.get_status_display()}',
            (
                f'Hello {order.billing_name or order.user.get_username()},\n\n'
                f'Your order {order.order_number} is now '
                f'{order.get_status_display().lower()}.{tracking}\n\n'
                f'View your order: {order_url}\n'
            ),
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            'Status email delivery failed for order %s.', order.order_number,
        )
        return False
    return True
