from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_units_unique_per_project_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='costing',
            name='operator',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='costing',
            name='operator_value',
            field=models.DecimalField(blank=True, decimal_places=5, max_digits=15, null=True),
        ),
    ]
