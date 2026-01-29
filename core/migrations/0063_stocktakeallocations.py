from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0062_projecttypes_stocktake_costing_stocktake'),
    ]

    operations = [
        migrations.CreateModel(
            name='StocktakeAllocations',
            fields=[
                ('allocation_pk', models.AutoField(primary_key=True, serialize=False)),
                ('project_type', models.CharField(blank=True, max_length=50, null=True)),
                ('unit', models.CharField(blank=True, max_length=50, null=True)),
                ('qty', models.DecimalField(blank=True, decimal_places=5, max_digits=15, null=True)),
                ('rate', models.DecimalField(blank=True, decimal_places=5, max_digits=15, null=True)),
                ('amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('gst_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('notes', models.CharField(blank=True, max_length=1000, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
                ('bill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stocktake_allocations', to='core.bills')),
                ('item', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='stocktake_allocations', to='core.costing')),
            ],
            options={
                'db_table': 'stocktake_allocations',
            },
        ),
        migrations.AddIndex(
            model_name='stocktakeallocations',
            index=models.Index(fields=['bill'], name='stocktake_a_bill_id_a1b2c3_idx'),
        ),
        migrations.AddIndex(
            model_name='stocktakeallocations',
            index=models.Index(fields=['item'], name='stocktake_a_item_id_d4e5f6_idx'),
        ),
    ]
