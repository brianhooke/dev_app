# Generated by Django 5.0.6 on 2024-06-08 05:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0019_contacts_contact_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='po_orders',
            name='po_sent',
            field=models.BooleanField(default=False),
        ),
    ]
