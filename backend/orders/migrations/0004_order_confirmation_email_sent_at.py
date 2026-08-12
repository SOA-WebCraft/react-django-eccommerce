from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('orders', '0003_order_order_number')]
    operations = [
        migrations.AddField(
            model_name='order',
            name='confirmation_email_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
