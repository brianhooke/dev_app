from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0070_add_writeoff_fields_to_snap_allocation'),
    ]

    operations = [
        migrations.AddField(
            model_name='stocktakesnap',
            name='xero_journals',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
