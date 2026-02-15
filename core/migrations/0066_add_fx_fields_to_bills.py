# Generated manually for FX (Foreign Currency) fields
# See FX_IMPLEMENTATION_PLAN.md for full spec

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0065_add_stocktake_to_xeroinstances'),
    ]

    operations = [
        # Add currency field - ISO 4217 code, default AUD
        migrations.AddField(
            model_name='bills',
            name='currency',
            field=models.CharField(default='AUD', max_length=3),
        ),
        # Add foreign_amount - Net amount in foreign currency
        migrations.AddField(
            model_name='bills',
            name='foreign_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        # Add foreign_gst - GST in foreign currency
        migrations.AddField(
            model_name='bills',
            name='foreign_gst',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        # Add exchange_rate - 1 foreign unit = X AUD
        migrations.AddField(
            model_name='bills',
            name='exchange_rate',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=10, null=True),
        ),
        # Add is_fx_fixed - False for unfixed FX bills, True once payment confirmed or AUD bill
        migrations.AddField(
            model_name='bills',
            name='is_fx_fixed',
            field=models.BooleanField(default=True),
        ),
        # Add fx_fixed_at - When FX was fixed (payment confirmed)
        migrations.AddField(
            model_name='bills',
            name='fx_fixed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Add xero_paid_aud - Actual AUD amount from Xero payment
        migrations.AddField(
            model_name='bills',
            name='xero_paid_aud',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        # Add index for FX queries (find unfixed FX bills)
        migrations.AddIndex(
            model_name='bills',
            index=models.Index(fields=['currency', 'is_fx_fixed'], name='core_invoic_currenc_fx_idx'),
        ),
    ]
