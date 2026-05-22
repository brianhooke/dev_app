"""Add is_revenue_project flag to Projects.

True = client-billed revenue project (default — preserves existing
behaviour for every row already in the DB).

False = internal/expense-only project. The UI hides the HC Claims
button and relabels "HC Variations" -> "Scope Variations" for these
projects; the underlying Hc_variation model is unchanged.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0072_normalise_labour_internal_division'),
    ]

    operations = [
        migrations.AddField(
            model_name='projects',
            name='is_revenue_project',
            field=models.BooleanField(default=True),
        ),
    ]
