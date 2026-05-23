"""Add Po_orders.status and backfill it from the legacy po_sent boolean.

Pre-fix, the only state we tracked on a PO was the boolean ``po_sent``,
which couldn't represent "draft", "cancelled", "replaced", etc.
``status`` is the new authoritative state field — see B24 in the PO
audit notes. We backfill it from ``po_sent`` so existing PO rows keep
displaying as Sent in the admin.
"""

from django.db import migrations, models


def backfill_status_from_po_sent(apps, schema_editor):
    Po_orders = apps.get_model('core', 'Po_orders')
    Po_orders.objects.filter(po_sent=True).update(status=1)  # STATUS_SENT
    Po_orders.objects.filter(po_sent=False).update(status=0)  # STATUS_DRAFT


def reverse_noop(apps, schema_editor):
    # Forward backfill is idempotent and reversed implicitly when the
    # column is dropped.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0079_drop_po_globals'),
    ]

    operations = [
        migrations.AddField(
            model_name='po_orders',
            name='status',
            field=models.IntegerField(
                choices=[(0, 'Draft'), (1, 'Sent'), (2, 'Cancelled')],
                default=0,
            ),
        ),
        migrations.RunPython(backfill_status_from_po_sent, reverse_noop),
    ]
