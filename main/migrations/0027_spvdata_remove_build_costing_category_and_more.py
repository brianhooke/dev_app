# Generated by Django 5.0.6 on 2024-06-30 05:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0026_categories_division_contacts_division'),
    ]

    operations = [
        migrations.CreateModel(
            name='SPVData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', models.CharField(max_length=255)),
                ('lot_size', models.CharField(max_length=255)),
                ('legal_owner', models.CharField(max_length=255)),
                ('folio_identifier', models.CharField(max_length=255)),
                ('bill_to', models.CharField(max_length=255)),
                ('email', models.EmailField(max_length=254)),
                ('owner_address', models.CharField(max_length=255)),
                ('director_1', models.CharField(max_length=255)),
                ('director_2', models.CharField(max_length=255)),
                ('abn', models.CharField(max_length=255)),
                ('acn', models.CharField(max_length=255)),
            ],
        ),
        migrations.RemoveField(
            model_name='build_costing',
            name='category',
        ),
        migrations.RemoveField(
            model_name='build_po_order_detail',
            name='costing',
        ),
        migrations.RemoveField(
            model_name='committed_allocations',
            name='item',
        ),
        migrations.RemoveField(
            model_name='claim_allocations',
            name='item',
        ),
        migrations.RemoveField(
            model_name='build_po_order_detail',
            name='po_order_pk',
        ),
        migrations.RemoveField(
            model_name='build_po_order_detail',
            name='quote',
        ),
        migrations.RemoveField(
            model_name='build_po_orders',
            name='po_supplier',
        ),
        migrations.RemoveField(
            model_name='claim_allocations',
            name='claim',
        ),
        migrations.RemoveField(
            model_name='claims',
            name='supplier',
        ),
        migrations.RemoveField(
            model_name='committed_allocations',
            name='quote',
        ),
        migrations.RemoveField(
            model_name='committed_quotes',
            name='contact_pk',
        ),
        migrations.RemoveField(
            model_name='hc_claim_lines',
            name='hc_claim',
        ),
        migrations.DeleteModel(
            name='Build_categories',
        ),
        migrations.DeleteModel(
            name='Build_costing',
        ),
        migrations.DeleteModel(
            name='Build_po_order_detail',
        ),
        migrations.DeleteModel(
            name='Build_po_orders',
        ),
        migrations.DeleteModel(
            name='Claim_allocations',
        ),
        migrations.DeleteModel(
            name='Claims',
        ),
        migrations.DeleteModel(
            name='Committed_allocations',
        ),
        migrations.DeleteModel(
            name='Committed_quotes',
        ),
        migrations.DeleteModel(
            name='Hc_claim_lines',
        ),
        migrations.DeleteModel(
            name='Hc_claims',
        ),
    ]
