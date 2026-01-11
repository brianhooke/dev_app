# Generated migration for ProjectTypes model
from django.db import migrations, models
import django.db.models.deletion


def populate_project_types(apps, schema_editor):
    """
    Populate ProjectTypes table with the existing 5 project types.
    """
    ProjectTypes = apps.get_model('core', 'ProjectTypes')
    
    project_types = [
        'general',
        'development',
        'construction',
        'precast',
        'pods',
    ]
    
    for pt in project_types:
        ProjectTypes.objects.get_or_create(project_type=pt)


def reverse_populate(apps, schema_editor):
    """
    Reverse migration - delete all project types.
    """
    ProjectTypes = apps.get_model('core', 'ProjectTypes')
    ProjectTypes.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0047_remove_invoices_associated_hc_claim_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectTypes',
            fields=[
                ('project_type_pk', models.AutoField(primary_key=True, serialize=False)),
                ('project_type', models.CharField(max_length=50, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True)),
                ('xero_instance', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='project_types',
                    to='core.xeroinstances'
                )),
            ],
            options={
                'verbose_name': 'Project Type',
                'verbose_name_plural': 'Project Types',
                'db_table': 'project_types',
            },
        ),
        # Populate with existing project types
        migrations.RunPython(populate_project_types, reverse_populate),
    ]
