"""
Management command: import the "Onyx Factory (Subbie)" tender budget.

Source CSV: ``Concrete Quantities - 56 Cedar Mill (1).csv`` (delivered by
the user 24 May 2026). The CSV is reproduced inside this file as Python
literals so the command is self-contained, deterministic, and reproducible.

Mapping decisions (validated with the user before writing any rows):

- **Project metadata**: name = ``Onyx Factory (Subbie)`` · type = ``general`` ·
  Xero instance = ``Mason Build`` · sales account = ``4110`` · manager =
  Brian Hooke · contracts admin = dylan.bridge@mason.build · revenue
  project = True · status = tender (``project_status=1``).
- **Phase categories** (11): Preliminaries, Civil, Stormwater, Foundations,
  Internal Slab, Carpark + Kerbs, Crossover, Tilt Up, Pods, Mezz, External
  Works.
- **Internal items** (special, division=-10): one item per phase that has
  a non-zero Margin column value, named after the phase, with
  ``uncommitted_amount`` = Margin column. (User chose ``per_phase`` over
  the single rolled-up ``Margin`` item the bootstrap normally creates.)
- **Labour items** (special, division=-5): one item per phase that has
  a non-zero Staff column value (External Works is **negative** in the
  CSV — kept as-is per the source data), named after the phase, with
  ``uncommitted_amount`` = Staff column. ``costing_rollups`` recomputes
  the *actual* committed for Labour from ``StaffHoursAllocations``;
  ``uncommitted_amount`` is the budgeted figure for the tender stage.
- **Concrete / Steel**: one item per phase that has a non-zero column
  value, named ``Concrete`` / ``Steel``, sitting inside that phase's
  Category.
- **Other**: per the breakdown rows in the CSV. Stormwater ($86,016.53)
  and Tilt Up ($73,436.10) had no breakdown — user chose to store them
  as a single ``Other`` line each.
- **Items**: ``tender_or_execution=1`` (matches project_status=1=tender),
  ``order_in_list`` is sequential per category, ``xero_account_code=''``
  (no per-line account codes given). Budgeted amount goes into
  ``uncommitted_amount`` (tender convention — matches Onyx Factory
  (Builder) pk=19 on production); ``contract_budget`` stays at 0 until
  the project graduates to execution. ``fixed_on_site/sc_invoiced/sc_paid``
  all initialise to 0.

Usage::

    # Dry-run (default) — does every insert inside a transaction and
    # ROLLS BACK at the end. Prints a plan summary + final budget total.
    python manage.py import_onyx_subbie

    # Real run — commits.
    python manage.py import_onyx_subbie --commit

    # Skip the "name already exists" guard (only after manual cleanup).
    python manage.py import_onyx_subbie --commit --force

Designed to be run on the EB instance because production RDS rejects
direct connections from outside the EB security group::

    eb ssh --profile default
    docker exec -it $(docker ps -q --filter ancestor=...) \\
        python manage.py import_onyx_subbie

The command is idempotent w.r.t. failed runs: every write is wrapped in
``transaction.atomic`` so a partial run rolls back. The dry-run mode
exercises the same code path as the real run, then forces a rollback at
the end via a sentinel exception — so what you see in dry-run is
exactly what you'll get on commit.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import (
    Categories, Costing, Projects, ProjectTypes, XeroInstances,
)


# ----------------------------------------------------------------------
# Source data — verbatim from the CSV.
# ----------------------------------------------------------------------

PROJECT_NAME = "Onyx Factory (Subbie)"
PROJECT_TYPE = "general"
PROJECT_STATUS_TENDER = 1
TENDER_OR_EXECUTION_TENDER = 1
XERO_NAME = "Mason Build"
SALES_ACCOUNT_CODE = "4110"
MANAGER = "Brian Hooke"
MANAGER_EMAIL = "brian.hooke@mason.build"
CONTRACTS_ADMIN_EMAILS = "dylan.bridge@mason.build"
IS_REVENUE_PROJECT = True

# Phase categories in the order they appear in the CSV.
PHASE_CATEGORIES = [
    "Preliminaries",
    "Civil",
    "Stormwater",
    "Foundations",
    "Internal Slab",
    "Carpark + Kerbs",
    "Crossover",
    "Tilt Up",
    "Pods",
    "Mezz",
    "External Works",
]

# Budget matrix from the CSV. ``None`` means an empty cell.
# Order of columns matches the CSV header: Staff, Margin, Concrete, Steel, Other.
MATRIX: dict[str, dict[str, Optional[Decimal]]] = {
    "Preliminaries":   {"Staff": None,                   "Margin": None,                  "Concrete": None,                  "Steel": None,                 "Other": Decimal("146250.00")},
    "Civil":           {"Staff": Decimal("28000.00"),    "Margin": Decimal("56000.00"),    "Concrete": None,                  "Steel": None,                 "Other": Decimal("224833.84")},
    "Stormwater":      {"Staff": Decimal("16000.00"),    "Margin": Decimal("15983.47"),    "Concrete": None,                  "Steel": None,                 "Other": Decimal("86016.53")},
    "Foundations":     {"Staff": Decimal("22834.29"),    "Margin": Decimal("15222.86"),    "Concrete": Decimal("27155.57"),   "Steel": Decimal("59510.76"),  "Other": Decimal("14857.14")},
    "Internal Slab":   {"Staff": Decimal("48000.00"),    "Margin": Decimal("63823.25"),    "Concrete": Decimal("209564.53"),  "Steel": Decimal("81825.54"),  "Other": Decimal("27601.92")},
    "Carpark + Kerbs": {"Staff": Decimal("39000.00"),    "Margin": Decimal("74430.00"),    "Concrete": Decimal("157427.59"),  "Steel": Decimal("28500.70"),  "Other": Decimal("31008.76")},
    "Crossover":       {"Staff": Decimal("4000.00"),     "Margin": Decimal("10000.00"),    "Concrete": Decimal("6000.00"),    "Steel": Decimal("2500.00"),   "Other": Decimal("4500.00")},
    "Tilt Up":         {"Staff": Decimal("18445.10"),    "Margin": Decimal("50000.00"),    "Concrete": Decimal("67386.92"),   "Steel": Decimal("62390.00"),  "Other": Decimal("73436.10")},
    "Pods":            {"Staff": Decimal("2320.00"),     "Margin": Decimal("17680.00"),    "Concrete": None,                  "Steel": None,                 "Other": Decimal("50720.00")},
    "Mezz":            {"Staff": Decimal("27509.16"),    "Margin": Decimal("47422.37"),    "Concrete": None,                  "Steel": None,                 "Other": Decimal("180068.46")},
    "External Works":  {"Staff": Decimal("-2500.00"),    "Margin": Decimal("10000.00"),    "Concrete": None,                  "Steel": None,                 "Other": Decimal("81000.00")},
}

# Other-column breakdown. Keys are phase names; values are list of
# (item_name, amount). Missing breakdowns (Stormwater, Tilt Up) fall
# through to a single ``Other`` line carrying the matrix amount.
OTHER_BREAKDOWN: dict[str, list[tuple[str, Decimal]]] = {
    "Preliminaries": [
        ("Construction Insurance", Decimal("26250.00")),
        ("Charterpac Monthly Fee", Decimal("90000.00")),
        ("Misc - office, power, rubbish etc", Decimal("30000.00")),
    ],
    "Civil": [
        ("Direct Materials - sub base", Decimal("119487.76")),
        ("Misc - Other", Decimal("23346.08")),
        ("Machine Hire", Decimal("42000.00")),
        ("Fill export / import", Decimal("40000.00")),
    ],
    "Foundations": [
        ("Drill Rig", Decimal("14857.14")),
    ],
    "Internal Slab": [
        ("Plastic + misc other", Decimal("27601.92")),
    ],
    "Carpark + Kerbs": [
        ("Pit lids, grates, misc", Decimal("31008.76")),
    ],
    "Crossover": [
        ("Traffic Mgmt + Misc", Decimal("4500.00")),
    ],
    "Pods": [
        ("Materials + Install", Decimal("50720.00")),
    ],
    "Mezz": [
        ("Flooring Materials", Decimal("16071.84")),
        ("LG Framing Materials", Decimal("9871.62")),
        ("Rondo System S/I", Decimal("21826.00")),
        ("Gyprock S/I", Decimal("49379.40")),
        ("Painting S/I", Decimal("32919.60")),
        ("Tibor", Decimal("5000.00")),
        ("Floor prep", Decimal("5000.00")),
        ("Kitchens", Decimal("15000.00")),
        ("Cupboard", Decimal("5000.00")),
        ("Doors(?)", Decimal("5000.00")),
        ("Skirtings/Architr", Decimal("5000.00")),
        ("Anything else", Decimal("10000.00")),
    ],
    "External Works": [
        ("Gates, Fencing", Decimal("55000.00")),
        ("Line painting", Decimal("7000.00")),
        ("Fire Extinguishers", Decimal("4000.00")),
        ("Landscaping", Decimal("15000.00")),
    ],
    # Stormwater and Tilt Up: no breakdown — handled inline below.
}

EXPECTED_GRAND_TOTAL = Decimal("2186724.86")


class _DryRun(Exception):
    """Sentinel raised at the end of dry-run to force a rollback."""


class Command(BaseCommand):
    help = (
        "Import the 'Onyx Factory (Subbie)' tender budget from the "
        "matrix + breakdown literals embedded in this file. Default is "
        "dry-run (rolls back at the end). Pass --commit to write."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Actually write rows. Default is a dry-run that rolls back.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Skip the 'project name already exists' guard. Only use "
                "after you have deleted/renamed the existing row."
            ),
        )

    # ------------------------------------------------------------------
    # Helpers — small wrappers so the body of handle() stays readable.
    # ------------------------------------------------------------------

    def _line(self, msg: str = "") -> None:
        self.stdout.write(msg)

    def _section(self, msg: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING(msg))

    def _ok(self, msg: str) -> None:
        self.stdout.write(self.style.SUCCESS(msg))

    def _warn(self, msg: str) -> None:
        self.stdout.write(self.style.WARNING(msg))

    # ------------------------------------------------------------------

    def handle(self, *args, **opts):
        commit: bool = bool(opts.get("commit"))
        force: bool = bool(opts.get("force"))

        # Pre-flight: project type + Xero instance must already exist.
        pt = ProjectTypes.objects.filter(project_type__iexact=PROJECT_TYPE).first()
        if not pt:
            existing = list(ProjectTypes.objects.values_list("project_type", flat=True))
            raise CommandError(
                f"project_type '{PROJECT_TYPE}' not found on this DB. "
                f"Existing types: {existing}"
            )

        xero = XeroInstances.objects.filter(xero_name__iexact=XERO_NAME).first()
        if not xero:
            existing = list(XeroInstances.objects.values_list("xero_name", flat=True))
            raise CommandError(
                f"XeroInstances '{XERO_NAME}' not found. Existing: {existing}"
            )

        existing_proj = Projects.objects.filter(project=PROJECT_NAME).first()
        if existing_proj and not force:
            raise CommandError(
                f"A project named {PROJECT_NAME!r} already exists "
                f"(pk={existing_proj.projects_pk}). Pass --force to skip "
                f"this guard ONLY after deleting/renaming the existing row."
            )

        self._section("=== Pre-flight ===")
        self._line(f"  project_type pk={pt.project_type_pk} ('{pt.project_type}')")
        self._line(f"  xero pk={xero.xero_instance_pk} ('{xero.xero_name}')")
        if existing_proj:
            self._warn(
                f"  WARN: project {PROJECT_NAME!r} already exists "
                f"(pk={existing_proj.projects_pk}); --force is set so "
                f"this run will create a duplicate."
            )
        else:
            self._line(f"  no existing project named {PROJECT_NAME!r}")

        self._line("")
        if commit:
            self._section(f"=== COMMIT MODE ===")
        else:
            self._section(f"=== DRY-RUN MODE (default) ===")
            self._line("  Will create everything inside a transaction and roll back at the end.")
            self._line("  Pass --commit to actually write.")

        rows: dict[str, int] = {"Projects": 0, "Categories": 0, "Costing": 0}
        grand_total = Decimal("0")
        committed_pk: Optional[int] = None

        try:
            with transaction.atomic():
                project = Projects.objects.create(
                    project=PROJECT_NAME,
                    project_type=pt,
                    xero_instance=xero,
                    xero_sales_account=SALES_ACCOUNT_CODE,
                    manager=MANAGER,
                    manager_email=MANAGER_EMAIL,
                    contracts_admin_emails=CONTRACTS_ADMIN_EMAILS,
                    project_status=PROJECT_STATUS_TENDER,
                    is_revenue_project=IS_REVENUE_PROJECT,
                )
                rows["Projects"] += 1
                self._line("")
                self._ok(f"[create] Project pk={project.projects_pk} name={project.project!r}")

                # 1. Phase categories.
                phase_cats: dict[str, Categories] = {}
                self._line("")
                self._section("--- Phase categories ---")
                for i, name in enumerate(PHASE_CATEGORIES, start=1):
                    cat = Categories.objects.create(
                        project=project,
                        project_type=None,
                        division=0,
                        category=name,
                        invoice_category=name,
                        order_in_list=i,
                    )
                    rows["Categories"] += 1
                    phase_cats[name] = cat
                    self._line(f"  {i:2d}. {name!r}  (pk={cat.categories_pk})")

                # 2. Internal special category.
                internal = Categories.objects.create(
                    project=project,
                    project_type=None,
                    division=-10,
                    category="Internal",
                    invoice_category="Internal",
                    order_in_list=-2,
                )
                rows["Categories"] += 1
                self._line(f"  Internal  (pk={internal.categories_pk}, division=-10)")

                # 3. Labour special category.
                labour = Categories.objects.create(
                    project=project,
                    project_type=None,
                    division=-5,
                    category="Labour",
                    invoice_category="Labour",
                    order_in_list=-1,
                )
                rows["Categories"] += 1
                self._line(f"  Labour    (pk={labour.categories_pk}, division=-5)")

                # 4. Items. For tender-stage projects (project_status=1)
                # the budgeted figures live in ``uncommitted_amount`` and
                # ``contract_budget`` stays at 0 until the project is
                # graduated to execution. Verified against pk=19 'Onyx
                # Factory (Builder)' on production RDS (24 May 2026).
                def _mk_item(category, item_name, amount, order_in_list):
                    row = Costing.objects.create(
                        project=project,
                        project_type=None,
                        category=category,
                        item=item_name,
                        order_in_list=order_in_list,
                        xero_account_code="",
                        contract_budget=Decimal("0"),
                        uncommitted_amount=amount,
                        fixed_on_site=Decimal("0"),
                        sc_invoiced=Decimal("0"),
                        sc_paid=Decimal("0"),
                        tender_or_execution=TENDER_OR_EXECUTION_TENDER,
                    )
                    rows["Costing"] += 1
                    return row

                # Internal items (Margin per phase).
                self._line("")
                self._section("--- Internal items (Margin per phase) ---")
                internal_total = Decimal("0")
                for i, phase in enumerate(PHASE_CATEGORIES, start=1):
                    margin = MATRIX[phase]["Margin"]
                    if margin is None or margin == 0:
                        continue
                    _mk_item(internal, phase, margin, i)
                    internal_total += margin
                    self._line(f"  {phase:18s}  {margin:>14,.2f}")
                self._line(f"  {'subtotal':18s}  {internal_total:>14,.2f}")
                grand_total += internal_total

                # Labour items (Staff per phase).
                self._line("")
                self._section("--- Labour items (Staff per phase) ---")
                labour_total = Decimal("0")
                for i, phase in enumerate(PHASE_CATEGORIES, start=1):
                    staff = MATRIX[phase]["Staff"]
                    if staff is None or staff == 0:
                        continue
                    _mk_item(labour, phase, staff, i)
                    labour_total += staff
                    self._line(f"  {phase:18s}  {staff:>14,.2f}")
                self._line(f"  {'subtotal':18s}  {labour_total:>14,.2f}")
                grand_total += labour_total

                # Per-phase items: Concrete, Steel, Other-breakdown.
                self._line("")
                self._section("--- Per-phase items (Concrete, Steel, Other-breakdown) ---")
                phase_total = Decimal("0")
                for phase in PHASE_CATEGORIES:
                    cat = phase_cats[phase]
                    row = MATRIX[phase]
                    local_total = Decimal("0")
                    order = 1

                    concrete = row["Concrete"]
                    if concrete is not None and concrete != 0:
                        _mk_item(cat, "Concrete", concrete, order)
                        local_total += concrete
                        order += 1

                    steel = row["Steel"]
                    if steel is not None and steel != 0:
                        _mk_item(cat, "Steel", steel, order)
                        local_total += steel
                        order += 1

                    other = row["Other"]
                    if other is not None and other != 0:
                        breakdown = OTHER_BREAKDOWN.get(phase)
                        if breakdown:
                            bd_sum = sum((amt for _, amt in breakdown), Decimal("0"))
                            if abs(bd_sum - other) > Decimal("0.01"):
                                raise CommandError(
                                    f"{phase}: Other breakdown sums to {bd_sum} "
                                    f"but matrix has {other} (tolerance 0.01). "
                                    f"Aborting (transaction will roll back)."
                                )
                            for name, amt in breakdown:
                                _mk_item(cat, name, amt, order)
                                local_total += amt
                                order += 1
                        else:
                            # Stormwater + Tilt Up — single Other line.
                            _mk_item(cat, "Other", other, order)
                            local_total += other
                            order += 1

                    if local_total != 0:
                        self._line(f"  {phase:18s}  {local_total:>14,.2f}")
                        phase_total += local_total
                self._line(f"  {'subtotal':18s}  {phase_total:>14,.2f}")
                grand_total += phase_total

                # Summary + sanity check.
                self._line("")
                self._section("=== Summary ===")
                for k, v in rows.items():
                    self._line(f"  {k:12s}  {v:3d} rows")
                self._line(f"  {'GRAND TOTAL':12s}  ${grand_total:>14,.2f}")

                if abs(grand_total - EXPECTED_GRAND_TOTAL) > Decimal("0.05"):
                    raise CommandError(
                        f"Grand total {grand_total} does not match expected "
                        f"{EXPECTED_GRAND_TOTAL} (tolerance 0.05). "
                        f"Aborting (transaction will roll back)."
                    )
                self._line(
                    f"  matches expected ${EXPECTED_GRAND_TOTAL:,.2f} within tolerance"
                )

                if not commit:
                    self._line("")
                    self._warn("[dry-run] Forcing rollback. Pass --commit to write.")
                    raise _DryRun()

                committed_pk = project.projects_pk

        except _DryRun:
            # Transaction has rolled back; nothing was written.
            self._ok("[dry-run] OK — rollback complete, nothing written.")
            return

        # Reach here only on a successful commit.
        self._line("")
        self._ok(f"[committed] Project pk={committed_pk} written to RDS.")
