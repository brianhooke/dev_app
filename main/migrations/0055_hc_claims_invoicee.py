# Generated by Django 5.0.6 on 2025-02-02 06:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0054_alter_contacts_checked'),
    ]

    operations = [
        migrations.AddField(
            model_name='hc_claims',
            name='invoicee',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
