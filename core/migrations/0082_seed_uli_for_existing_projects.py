"""Backfill the Unexpected Line Items (ULI) category + costing for every
existing project.

ULI is a new special division (-15) introduced 2026-05-25. New projects
are seeded by `core.views.projects.create_project`, but existing
projects predate the change and need a one-shot backfill.

This migration is **strictly additive**:

  * For every Projects row that does NOT already have a category with
    division=-15, it creates a new ULI category and a single matching
    costing.
  * For every Projects row that already has the ULI category (e.g.
    because it was created after the new project-creation seed
    landed), it does nothing — no rename, no delete, no field rewrite.
  * It never touches any other Categories, Costing, or Projects rows.
  * If the project is in execution mode (project_status=2), it also
    creates the execution-mode (tender_or_execution=2) clone of the
    ULI costing, mirroring how `fix_contract_budget` clones the rest
    of the BOM. Tender-mode projects only get the tender costing — the
    execution clone will be added when fix_contract_budget runs.

Idempotent: rerunning the migration after manual ULI creation is a
no-op. Safe to run on local + production via the standard
`manage.py migrate` flow.
"""

from decimal import Decimal

from django.db import migrations


DIVISION_ULI = -15
ULI_CATEGORY_NAME = 'Unexpected Line Items'
ULI_COSTING_NAME = 'Unexpected Line Items'


def seed_uli_for_existing_projects(apps, schema_editor):
    Projects = apps.get_model('core', 'Projects')
    Categories = apps.get_model('core', 'Categories')
    Costing = apps.get_model('core', 'Costing')

    created_categories = 0
    created_tender_costings = 0
    created_execution_costings = 0

    for project in Projects.objects.all():
        # Find any existing ULI category for this project. Match by
        # division first (canonical), fall back to name-only in case a
        # legacy row was created with division=0 before save() picked
        # up the new sentinel name. Both cases are treated as "ULI
        # already present" — we don't rewrite division here.
        existing = Categories.objects.filter(
            project=project, division=DIVISION_ULI
        ).first()
        if existing is None:
            existing = Categories.objects.filter(
                project=project, category__iexact=ULI_CATEGORY_NAME
            ).first()

        if existing is None:
            existing = Categories.objects.create(
                project=project,
                division=DIVISION_ULI,
                category=ULI_CATEGORY_NAME,
                invoice_category=ULI_CATEGORY_NAME,
                order_in_list=Decimal('-3'),
            )
            created_categories += 1

        # Tender-mode costing — always create if missing.
        tender_costing = Costing.objects.filter(
            project=project,
            category=existing,
            tender_or_execution=1,
        ).first()
        if tender_costing is None:
            Costing.objects.create(
                project=project,
                category=existing,
                item=ULI_COSTING_NAME,
                order_in_list=Decimal('1'),
                xero_account_code='',
                contract_budget=Decimal('0'),
                uncommitted_amount=Decimal('0'),
                fixed_on_site=Decimal('0'),
                sc_invoiced=Decimal('0'),
                sc_paid=Decimal('0'),
                tender_or_execution=1,
            )
            created_tender_costings += 1

        # Execution-mode clone — only seed if the project is already in
        # execution mode (project_status=2). For tender projects, the
        # execution row will appear automatically when
        # fix_contract_budget runs at tender → execution transition.
        if getattr(project, 'project_status', 1) == 2:
            execution_costing = Costing.objects.filter(
                project=project,
                category=existing,
                tender_or_execution=2,
            ).first()
            if execution_costing is None:
                Costing.objects.create(
                    project=project,
                    category=existing,
                    item=ULI_COSTING_NAME,
                    order_in_list=Decimal('1'),
                    xero_account_code='',
                    contract_budget=Decimal('0'),
                    uncommitted_amount=Decimal('0'),
                    fixed_on_site=Decimal('0'),
                    sc_invoiced=Decimal('0'),
                    sc_paid=Decimal('0'),
                    tender_or_execution=2,
                )
                created_execution_costings += 1

    print(
        f"[ULI backfill] Created {created_categories} categories, "
        f"{created_tender_costings} tender costings, "
        f"{created_execution_costings} execution costings."
    )


def reverse_noop(apps, schema_editor):
    # Reversal would mean deleting ULI rows that downstream features
    # (staff_hours, stocktake snaps, contract_budget committed
    # dropdown) now reference. Leave them in place — the model itself
    # is unchanged on rollback.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0081_bills_pm_approved_stock_on_shelf_date'),
    ]

    operations = [
        migrations.RunPython(seed_uli_for_existing_projects, reverse_noop),
    ]
