# Generated by Django 5.0.6 on 2024-10-06 04:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0044_hc_claims_invoices_associated_hc_claim'),
    ]

    operations = [
        migrations.AddField(
            model_name='hc_claims',
            name='display_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
