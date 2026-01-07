from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0038_add_amount_to_hc_variation'),
    ]

    operations = [
        # Add project_type to Categories
        migrations.AddField(
            model_name='categories',
            name='project_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('general', 'General'),
                    ('development', 'Development'),
                    ('construction', 'Construction'),
                    ('precast', 'Precast'),
                    ('pods', 'Pods'),
                ],
                max_length=20,
                null=True,
            ),
        ),
        # Add project_type to Costing
        migrations.AddField(
            model_name='costing',
            name='project_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('general', 'General'),
                    ('development', 'Development'),
                    ('construction', 'Construction'),
                    ('precast', 'Precast'),
                    ('pods', 'Pods'),
                ],
                max_length=20,
                null=True,
            ),
        ),
        # Add project_type to Units
        migrations.AddField(
            model_name='units',
            name='project_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('general', 'General'),
                    ('development', 'Development'),
                    ('construction', 'Construction'),
                    ('precast', 'Precast'),
                    ('pods', 'Pods'),
                ],
                max_length=20,
                null=True,
            ),
        ),
        # Create Quantities model
        migrations.CreateModel(
            name='Quantities',
            fields=[
                ('quantity_pk', models.AutoField(primary_key=True, serialize=False)),
                ('quantity', models.CharField(max_length=50)),
                ('order_in_list', models.IntegerField()),
                ('project_type', models.CharField(
                    blank=True,
                    choices=[
                        ('general', 'General'),
                        ('development', 'Development'),
                        ('construction', 'Construction'),
                        ('precast', 'Precast'),
                        ('pods', 'Pods'),
                    ],
                    max_length=20,
                    null=True,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
            ],
            options={
                'verbose_name_plural': 'Quantities',
                'ordering': ['order_in_list'],
            },
        ),
    ]
