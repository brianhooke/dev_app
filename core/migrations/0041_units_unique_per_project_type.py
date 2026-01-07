from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0040_add_costing_rate'),
    ]

    operations = [
        # Remove old unique constraints
        migrations.AlterField(
            model_name='units',
            name='unit_name',
            field=models.CharField(max_length=50),
        ),
        migrations.AlterField(
            model_name='units',
            name='order_in_list',
            field=models.IntegerField(),
        ),
        # Add unique_together for project_type scoped uniqueness
        migrations.AlterUniqueTogether(
            name='units',
            unique_together={('unit_name', 'project_type'), ('order_in_list', 'project_type')},
        ),
    ]
