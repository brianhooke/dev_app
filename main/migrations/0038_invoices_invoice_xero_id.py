# Generated by Django 5.0.6 on 2024-07-13 02:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0037_invoices_invoice_date_invoices_invoice_due_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoices',
            name='invoice_xero_id',
            field=models.CharField(max_length=255, null=True),
        ),
    ]
