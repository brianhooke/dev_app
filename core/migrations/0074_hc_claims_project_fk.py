"""Add HC_claims.project FK and backfill it from existing relations.

Historically a claim's project was inferred from its allocations or its
attached bills (see core/views/hc_claims.py::get_hc_claims). That made
project-scoped behaviour brittle - notably the draft-claim guard, which
was effectively global because a brand-new draft has neither
allocations nor bills until the user does more work.

This migration introduces a direct nullable FK and backfills it for
every existing claim using the same precedence the views already use:

  1. Try HC_claim_allocations -> item.project_id
  2. Otherwise try Bills.associated_hc_claim -> bill.project_id
  3. Otherwise leave NULL (orphan claim with no relations)

Idempotent on re-run.
"""
import django.db.models.deletion
from django.db import migrations, models


def backfill_project(apps, schema_editor):
    HC_claims = apps.get_model('core', 'HC_claims')
    HC_claim_allocations = apps.get_model('core', 'HC_claim_allocations')
    Bills = apps.get_model('core', 'Bills')

    for claim in HC_claims.objects.filter(project__isnull=True):
        # 1. Try via allocations -> item.project
        alloc = (
            HC_claim_allocations.objects
            .filter(hc_claim_pk=claim)
            .select_related('item')
            .first()
        )
        if alloc and alloc.item and alloc.item.project_id:
            claim.project_id = alloc.item.project_id
            claim.save(update_fields=['project'])
            continue

        # 2. Fall back to attached bills
        bill = Bills.objects.filter(associated_hc_claim=claim).first()
        if bill and bill.project_id:
            claim.project_id = bill.project_id
            claim.save(update_fields=['project'])
            continue

        # 3. Orphan - leave NULL


def reverse_noop(apps, schema_editor):
    # The reverse of AddField drops the column; we don't need to clear
    # values manually. RunPython reverse is a noop because the original
    # state had no project FK to restore.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0073_projects_is_revenue_project'),
    ]

    operations = [
        migrations.AddField(
            model_name='hc_claims',
            name='project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='hc_claims',
                to='core.projects',
            ),
        ),
        migrations.RunPython(backfill_project, reverse_noop),
    ]
