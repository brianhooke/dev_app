# Generated by Django 5.0.6 on 2024-06-22 13:12

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0021_build_categories_hc_claims_build_costing_claims_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='build_costing',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.build_categories'),
        ),
        migrations.AlterField(
            model_name='claim_allocations',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.build_costing'),
        ),
        migrations.AlterField(
            model_name='committed_allocations',
            name='item',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.build_costing'),
        ),
    ]
