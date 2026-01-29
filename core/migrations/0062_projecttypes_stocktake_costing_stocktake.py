from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0061_bills_is_stocktake'),
    ]

    operations = [
        migrations.AddField(
            model_name='projecttypes',
            name='stocktake',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='costing',
            name='stocktake',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
