# Generated by Django 5.0.6 on 2024-07-10 09:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0034_alter_invoices_invoice_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='contacts',
            name='xero_contact_id',
            field=models.CharField(default=1, max_length=255),
            preserve_default=False,
        ),
    ]
