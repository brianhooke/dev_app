"""
Backfill division sentinels on Labour and Internal categories.

Historically several Category-creation paths (template-copy, rates page,
dashboard, hc_variations, csv upload) hard-coded division=0 even when the
name was 'Labour' or 'Internal'. That left some projects with mis-set
divisions, which made the v241 C2C export silently skip the Labour /
Margin slices for those projects.

The diagnostic run on production at v242 confirmed there are no
false-positives in either direction (no non-Labour rows holding -5 and
no non-Internal rows holding -10), so a blanket name-based update is
safe and fully deterministic.

This migration is idempotent — re-running it is a no-op.
"""
from django.db import migrations


def normalise_division(apps, schema_editor):
    Categories = apps.get_model('core', 'Categories')
    Categories.objects.filter(category__iexact='Labour').exclude(division=-5).update(division=-5)
    Categories.objects.filter(category__iexact='Internal').exclude(division=-10).update(division=-10)


def reverse_noop(apps, schema_editor):
    # Reversing this migration is intentionally a no-op: there's no safe
    # way to reconstruct the previous (incorrect) division values, and
    # the new save() guard on Categories would re-correct them anyway.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0071_stocktakesnap_xero_journals'),
    ]

    operations = [
        migrations.RunPython(normalise_division, reverse_noop),
    ]
