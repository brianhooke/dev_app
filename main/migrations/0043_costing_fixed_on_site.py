# Generated by Django 5.0.6 on 2024-10-05 12:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0042_contacts_checked'),
    ]

    operations = [
        migrations.AddField(
            model_name='costing',
            name='fixed_on_site',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
            preserve_default=False,
        ),
    ]
