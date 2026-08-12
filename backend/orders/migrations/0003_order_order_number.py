import secrets
import string

from django.db import migrations, models

import orders.models


ALPHABET = string.ascii_uppercase + string.digits


def populate_order_numbers(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    used = set(Order.objects.exclude(order_number__isnull=True).values_list(
        'order_number',
        flat=True,
    ))
    for order in Order.objects.filter(order_number__isnull=True).iterator():
        while True:
            value = ''.join(secrets.choice(ALPHABET) for _ in range(10))
            if value not in used:
                break
        order.order_number = value
        order.save(update_fields=('order_number',))
        used.add(value)


class Migration(migrations.Migration):
    dependencies = [('orders', '0002_coupon_order_address_order_billing_email_and_more')]

    operations = [
        migrations.AddField(
            model_name='order',
            name='order_number',
            field=models.CharField(
                editable=False,
                max_length=10,
                null=True,
            ),
        ),
        migrations.RunPython(populate_order_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='order_number',
            field=models.CharField(
                default=orders.models.generate_order_number,
                editable=False,
                max_length=10,
                unique=True,
            ),
        ),
    ]
