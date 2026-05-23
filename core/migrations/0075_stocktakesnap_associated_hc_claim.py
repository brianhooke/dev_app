"""Add StocktakeSnap.associated_hc_claim FK.

Mirrors Bills.associated_hc_claim. Pre-fix, create_hc_claim accepted
snap_pks but had nowhere to persist them — the field was effectively a
no-op (B7 in the review).

No backfill is performed: there is no historical signal that ties an
existing snap to a particular claim. The field stays nullable and
populates from this point forward.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0074_hc_claims_project_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='stocktakesnap',
            name='associated_hc_claim',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='associated_stocktake_snaps',
                to='core.hc_claims',
            ),
        ),
    ]
