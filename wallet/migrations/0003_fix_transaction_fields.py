import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0002_remove_wallet_authorization_code_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Fix created_by: OneToOneField → ForeignKey (critical bug fix)
        migrations.RemoveField(
            model_name='transaction',
            name='created_by',
        ),
        migrations.AddField(
            model_name='transaction',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='initiated_transactions',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Add defaults for fields that had none (prevents crash on create)
        migrations.AlterField(
            model_name='transaction',
            name='withdrawable_amount',
            field=models.DecimalField(decimal_places=6, default=0, max_digits=14),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='service_fee',
            field=models.DecimalField(decimal_places=6, default=0, max_digits=14),
        ),
        # Admin topup tracking fields
        migrations.AddField(
            model_name='transaction',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='transaction',
            name='initiated_by_admin',
            field=models.BooleanField(default=False),
        ),
    ]
