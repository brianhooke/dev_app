# Minimal migration for XeroTrackingCategories only

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_add_unit_qty_to_units'),
    ]

    operations = [
        migrations.CreateModel(
            name='XeroTrackingCategories',
            fields=[
                ('tracking_category_pk', models.AutoField(primary_key=True, serialize=False)),
                ('tracking_category_id', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255)),
                ('status', models.CharField(blank=True, max_length=50, null=True)),
                ('option_id', models.CharField(blank=True, max_length=255, null=True)),
                ('option_name', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
                ('xero_instance', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='xero_tracking_categories', to='core.xeroinstances')),
            ],
            options={
                'verbose_name': 'Xero Tracking Category',
                'verbose_name_plural': 'Xero Tracking Categories',
                'db_table': 'xero_tracking_categories',
            },
        ),
        migrations.AlterUniqueTogether(
            name='xerotrackingcategories',
            unique_together={('xero_instance', 'tracking_category_id', 'option_id')},
        ),
    ]
