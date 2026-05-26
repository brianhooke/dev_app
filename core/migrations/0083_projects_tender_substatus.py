"""Add Projects.tender_substatus for the v255 tender substatus feature.

The new field captures whether a tender-mode project is still
``Tendering`` (1, the default) or has graduated to ``Quoted`` (2). It's
only meaningful when ``project_status == 1`` (tender), but the column
exists on every row regardless. Defaulting to TENDERING auto-backfills
every existing tender + execution project at migration time, which
matches the user requirement: every legacy project should land on
TENDERING by default.

Once a project transitions to execution via ``fix_contract_budget`` the
value is preserved as a historical marker but ignored by the UI.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0082_seed_uli_for_existing_projects'),
    ]

    operations = [
        migrations.AddField(
            model_name='projects',
            name='tender_substatus',
            field=models.IntegerField(
                default=1,
                choices=[(1, 'Tendering'), (2, 'Quoted')],
                help_text=(
                    'Tender phase substatus: 1=Tendering (default), '
                    '2=Quoted. Ignored when project_status=2.'
                ),
            ),
        ),
    ]
