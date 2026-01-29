from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0060_alter_staffhoursallocations_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='bills',
            name='is_stocktake',
            field=models.BooleanField(default=False),
        ),
    ]
