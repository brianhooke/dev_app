# Generated manually - SQL already applied
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_rename_invoice_to_bill'),
    ]

    operations = [
        migrations.AddField(
            model_name='hc_variation',
            name='amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
    ]
