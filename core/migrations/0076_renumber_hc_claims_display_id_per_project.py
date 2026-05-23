"""Renumber HC_claims.display_id so it counts per-project.

Pre-fix display_id was a global counter shared across every project,
so a project's claim sequence appeared as e.g. {1, 2, 4} whenever
claim #3 was created for some other project. This migration walks
each project's claims in chronological order (date asc, then
created_at asc, then hc_claim_pk asc) and renumbers them 1..N.

Orphan claims with project IS NULL keep their existing display_id —
they shouldn't exist post-0074 backfill, but this avoids touching
unexpected rows.
"""
from collections import defaultdict
from django.db import migrations


def renumber_per_project(apps, schema_editor):
    HC_claims = apps.get_model('core', 'HC_claims')

    by_project = defaultdict(list)
    for claim in HC_claims.objects.exclude(project__isnull=True).order_by('date', 'created_at', 'hc_claim_pk'):
        by_project[claim.project_id].append(claim)

    # Two-phase update to avoid colliding with any existing
    # (hypothetical) UNIQUE constraint or interim duplicates: first
    # push every renumbered claim into a high range, then assign final
    # values. Without a uniqueness constraint this is just paranoia,
    # but it keeps the migration safe to re-run after partial failures.
    HIGH_RANGE = 10_000_000
    next_high = HIGH_RANGE
    for claims in by_project.values():
        for claim in claims:
            claim.display_id = next_high
            claim.save(update_fields=['display_id'])
            next_high += 1

    for project_id, claims in by_project.items():
        for idx, claim in enumerate(claims, start=1):
            claim.display_id = idx
            claim.save(update_fields=['display_id'])


def reverse_noop(apps, schema_editor):
    # We can't reconstruct the prior global numbering — and even if we
    # could, the global counter was a bug. Leave the per-project
    # numbering in place on rollback.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0075_stocktakesnap_associated_hc_claim'),
    ]

    operations = [
        migrations.RunPython(renumber_per_project, reverse_noop),
    ]
