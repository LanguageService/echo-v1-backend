import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payment', '0003_kpaywebhookevent'),
    ]

    operations = [
        # Rename the table (KPayWebhookEvent → PaymentWebhookEvent)
        migrations.RenameModel(
            old_name='KPayWebhookEvent',
            new_name='PaymentWebhookEvent',
        ),
        # Link to Payment
        migrations.AddField(
            model_name='paymentwebhookevent',
            name='payment',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='webhook_events',
                to='payment.payment',
            ),
        ),
        # Source field so we know which gateway sent the event
        migrations.AddField(
            model_name='paymentwebhookevent',
            name='source',
            field=models.CharField(default='paystack', help_text='Gateway that sent this event (paystack, kpay, etc.)', max_length=20),
        ),
        # Make status_desc optional (was TextField with no default)
        migrations.AlterField(
            model_name='paymentwebhookevent',
            name='status_desc',
            field=models.TextField(blank=True, default=''),
        ),
    ]
