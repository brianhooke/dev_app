# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0044_units_project_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='units',
            name='unit_qty',
            field=models.DecimalField(blank=True, decimal_places=5, max_digits=15, null=True),
        ),
    ]
