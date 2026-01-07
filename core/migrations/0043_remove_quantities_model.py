from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_add_costing_operator_fields'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Quantities',
        ),
    ]
