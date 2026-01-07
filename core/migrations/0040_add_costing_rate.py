from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_add_project_type_and_quantities'),
    ]

    operations = [
        migrations.AddField(
            model_name='costing',
            name='rate',
            field=models.DecimalField(blank=True, decimal_places=5, max_digits=15, null=True),
        ),
    ]
