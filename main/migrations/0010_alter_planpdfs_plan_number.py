# Generated by Django 4.2.3 on 2024-05-18 10:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0009_alter_planpdfs_rev_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='planpdfs',
            name='plan_number',
            field=models.CharField(max_length=255),
        ),
    ]