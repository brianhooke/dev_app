"""Add Bills.pm_approved and Bills.stock_on_shelf_date for the stocktake
two-step approval + shelf-lock workflow introduced 2026-05-25.

`pm_approved` is the PM checkbox in the stocktake Allocations tab — an
additional gate on top of the existing fully-allocated check before
`approve_stocktake_bill` will accept the bill.

`stock_on_shelf_date` tracks the date stock physically landed and must
be > the most recent finalised StocktakeSnap.date. This locks the shelf
once a snap is taken so prior dates can't be back-filled and inflate
the historical balance (see HANDOFF.md "50MPa stocktake forensic,
25 May 2026" for the bug this prevents).

Both fields default to safe values (False / NULL) for non-stocktake
bills, which is the vast majority of rows on the existing table.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0080_po_orders_status_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='bills',
            name='pm_approved',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='bills',
            name='stock_on_shelf_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
