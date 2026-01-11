# Generated migration to convert Projects.project_type from CharField to FK
from django.db import migrations, models
import django.db.models.deletion


def migrate_project_type_to_fk(apps, schema_editor):
    """
    Migrate existing project_type string values to FK references.
    """
    Projects = apps.get_model('core', 'Projects')
    ProjectTypes = apps.get_model('core', 'ProjectTypes')
    
    for project in Projects.objects.all():
        if project.project_type:
            # Find the matching ProjectTypes record
            project_type_obj = ProjectTypes.objects.filter(project_type=project.project_type).first()
            if project_type_obj:
                project.project_type_fk = project_type_obj
                project.save()


def reverse_migrate(apps, schema_editor):
    """
    Reverse migration - copy FK values back to string field.
    """
    Projects = apps.get_model('core', 'Projects')
    
    for project in Projects.objects.all():
        if project.project_type_fk:
            project.project_type = project.project_type_fk.project_type
            project.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0048_projecttypes'),
    ]

    operations = [
        # Step 1: Add the new FK field (nullable initially)
        migrations.AddField(
            model_name='projects',
            name='project_type_fk',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='projects_by_type',
                to='core.projecttypes',
            ),
        ),
        # Step 2: Migrate existing data from string to FK
        migrations.RunPython(migrate_project_type_to_fk, reverse_migrate),
        # Step 3: Remove the old CharField
        migrations.RemoveField(
            model_name='projects',
            name='project_type',
        ),
        # Step 4: Rename the FK field to project_type
        migrations.RenameField(
            model_name='projects',
            old_name='project_type_fk',
            new_name='project_type',
        ),
    ]
