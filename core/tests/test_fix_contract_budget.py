"""
Regression tests for ``core.views.contract_budget.fix_contract_budget``
focused on the v254 cloning behaviour: at the tender → execution
transition, both ``StaffHoursAllocations`` and ``Bill_allocations``
should be cloned from tender Costings to the new execution Costings via
``costing_pk_mapping``, with the original tender rows preserved as a
historical snapshot.

Running:

    DJANGO_SETTINGS_MODULE=dev_app.settings.test \\
        python manage.py test core.tests.test_fix_contract_budget -v 2

``dev_app/settings/test.py`` disables ``MIGRATION_MODULES`` so the
schema is built from current model state and the F.Q-C-05 historical
migration ordering issue is sidestepped.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase, RequestFactory

from core.models import (
    Bill_allocations,
    Bills,
    Categories,
    Contacts,
    Costing,
    Employee,
    EmployeePayRate,
    Projects,
    ProjectTypes,
    Quote_allocations,
    Quotes,
    StaffHours,
    StaffHoursAllocations,
    XeroInstances,
)
from core.services import costing_rollups as svc
from core.views.contract_budget import fix_contract_budget


class FixContractBudgetCloningTests(TestCase):
    """
    Build a tender-mode project with quotes, staff hours, and bill
    allocations, then run ``fix_contract_budget`` and assert that:

    1. Tender rows survive (historical snapshot).
    2. Execution clones exist with the same shape but pointing at the
       newly created execution Costings.
    3. ULI Costings are cloned just like everything else (no special-
       casing needed because they're already in the BoM).

    Fixture (tender-side):

        Costings (tender_or_execution=1)
            T_C1   Materials.Concrete    uncommitted_amount = 1000
            T_C2   Labour.Site Labour    uncommitted_amount =    0
            T_C3   ULI.Unexpected Line Items uncommitted_amount = 0

        Quote Q1 (tender), allocations:
            -> T_C1: amount=1000

        StaffHours (Alice, 2026-01-15, 8h)
            -> T_C2: 6h
            -> T_C3: 2h  (ULI)

        Bill B1 (direct cost, tender-allocated)
            -> T_C1: $400
            -> T_C3: $50  (ULI)
    """

    @classmethod
    def setUpTestData(cls):
        cls.xero = XeroInstances.objects.create(
            xero_name='Test Xero',
            xero_client_id='test-client-id',
        )
        cls.project_type = ProjectTypes.objects.create(
            project_type='unit-test-fcb',
            rates_based=0,  # non-construction so we don't need rate*qty maths
        )

        cls.cat_materials = Categories.objects.create(
            category='Materials', division=1, invoice_category='Materials',
            order_in_list=1,
        )
        # Categories.save() forces the canonical division for these
        # special names, so passing division here is harmless and keeps
        # the fixture self-documenting.
        cls.cat_labour = Categories.objects.create(
            category='Labour', invoice_category='Labour', order_in_list=2,
        )
        cls.cat_uli = Categories.objects.create(
            category='Unexpected Line Items', invoice_category='Unexpected Line Items',
            order_in_list=3,
        )

        cls.project = Projects.objects.create(
            project='Test FCB Project',
            project_type=cls.project_type,
            project_status=1,  # tender
            xero_instance=cls.xero,
        )

        def _mk_costing(item, category, uncommitted_amount):
            return Costing.objects.create(
                project=cls.project,
                category=category,
                item=item,
                xero_account_code='100',
                contract_budget=Decimal('0'),
                uncommitted_amount=Decimal(str(uncommitted_amount)),
                fixed_on_site=Decimal('0'),
                sc_invoiced=Decimal('0'),
                sc_paid=Decimal('0'),
                tender_or_execution=1,  # tender
            )

        cls.t_c1 = _mk_costing('Concrete', cls.cat_materials, 1000)
        cls.t_c2 = _mk_costing('Site Labour', cls.cat_labour, 0)
        cls.t_c3 = _mk_costing('Unexpected Line Items', cls.cat_uli, 0)

        cls.supplier = Contacts.objects.create(
            xero_instance=cls.xero,
            xero_contact_id='test-contact-id',
            name='Test Supplier',
            email='test@example.com',
            status='ACTIVE',
            checked=1,
        )

        cls.quote = Quotes.objects.create(
            supplier_quote_number='Q1',
            total_cost=Decimal('1000'),
            contact_pk=cls.supplier,
            project=cls.project,
            tender_or_execution=1,
        )
        Quote_allocations.objects.create(
            quotes_pk=cls.quote, item=cls.t_c1,
            qty=Decimal('1'), rate=Decimal('1000'), amount=Decimal('1000'),
        )

        cls.employee = Employee.objects.create(
            xero_instance=cls.xero,
            xero_employee_id='emp-1',
            name='Alice',
        )
        # Pay rate so wages > 0 (used in cost rollups, not strictly
        # necessary for the cloning assertions but keeps the fixture
        # honest end-to-end).
        EmployeePayRate.objects.create(
            employee=cls.employee,
            effective_date=date(2026, 1, 1),
            is_ordinary_rate=True,
            rate_per_unit=Decimal('50'),
        )

        cls.staff_day = StaffHours.objects.create(
            employee=cls.employee,
            date=date(2026, 1, 15),
            hours=Decimal('8'),
        )
        cls.alloc_labour = StaffHoursAllocations.objects.create(
            staff_hours=cls.staff_day,
            allocation_type=StaffHoursAllocations.ALLOCATION_TYPE_PROJECT,
            project=cls.project,
            costing=cls.t_c2,
            hours=Decimal('6'),
        )
        cls.alloc_uli = StaffHoursAllocations.objects.create(
            staff_hours=cls.staff_day,
            allocation_type=StaffHoursAllocations.ALLOCATION_TYPE_PROJECT,
            project=cls.project,
            costing=cls.t_c3,
            hours=Decimal('2'),
        )

        cls.bill = Bills.objects.create(
            project=cls.project,
            bill_status=Bills.STATUS_APPROVED,
            bill_type=1,
            contact_pk=cls.supplier,
            bill_date=date(2026, 1, 20),
            total_net=Decimal('450'),
            total_gst=Decimal('45'),
        )
        cls.bill_alloc_c1 = Bill_allocations.objects.create(
            bill=cls.bill, item=cls.t_c1,
            amount=Decimal('400'), qty=Decimal('1'), rate=Decimal('400'),
            gst_amount=Decimal('40'), allocation_type=0, notes='Concrete bill line',
        )
        cls.bill_alloc_uli = Bill_allocations.objects.create(
            bill=cls.bill, item=cls.t_c3,
            amount=Decimal('50'), qty=Decimal('1'), rate=Decimal('50'),
            gst_amount=Decimal('5'), allocation_type=0, notes='ULI bill line',
        )

    def setUp(self):
        # ``fix_contract_budget`` is decorated with @csrf_exempt and
        # @require_http_methods(["POST"]); we call it as a plain function
        # with a synthesised POST request to avoid wiring up the URLconf
        # or auth middleware in the test.
        self.factory = RequestFactory()

    def _run_fix(self):
        request = self.factory.post(f'/core/fix-contract-budget/{self.project.pk}/')
        return fix_contract_budget(request, self.project.pk)

    # ------------------------------------------------------------------
    # Pre-condition sanity.
    # ------------------------------------------------------------------

    def test_fixture_starts_in_tender_with_known_counts(self):
        self.assertEqual(self.project.project_status, 1)
        self.assertEqual(Costing.objects.filter(project=self.project).count(), 3)
        self.assertEqual(
            Costing.objects.filter(project=self.project, tender_or_execution=1).count(), 3
        )
        self.assertEqual(
            Costing.objects.filter(project=self.project, tender_or_execution=2).count(), 0
        )
        self.assertEqual(
            StaffHoursAllocations.objects.filter(project=self.project).count(), 2
        )
        self.assertEqual(
            Bill_allocations.objects.filter(bill__project=self.project).count(), 2
        )

    # ------------------------------------------------------------------
    # Cloning assertions (the v254 contract).
    # ------------------------------------------------------------------

    def test_fix_contract_budget_clones_staff_hours_and_bills(self):
        response = self._run_fix()
        self.assertEqual(response.status_code, 200)

        self.project.refresh_from_db()
        self.assertEqual(self.project.project_status, 2)

        # Costings: 3 tender + 3 execution clones = 6 total.
        all_costings = Costing.objects.filter(project=self.project)
        self.assertEqual(all_costings.count(), 6)
        self.assertEqual(all_costings.filter(tender_or_execution=1).count(), 3)
        self.assertEqual(all_costings.filter(tender_or_execution=2).count(), 3)

        # Build name -> {te: pk} index for downstream lookups.
        idx = {}
        for c in all_costings:
            idx.setdefault(c.item, {})[c.tender_or_execution] = c.costing_pk
        # Sanity: every tender costing has an execution sibling.
        for name, by_te in idx.items():
            self.assertIn(1, by_te, f'{name}: missing tender side')
            self.assertIn(2, by_te, f'{name}: missing execution clone')

        # ---- StaffHoursAllocations: 2 tender + 2 execution clones = 4 ----
        all_staff = StaffHoursAllocations.objects.filter(project=self.project)
        self.assertEqual(all_staff.count(), 4)
        tender_staff = all_staff.filter(costing__tender_or_execution=1)
        exec_staff = all_staff.filter(costing__tender_or_execution=2)
        self.assertEqual(tender_staff.count(), 2)
        self.assertEqual(exec_staff.count(), 2)

        # Tender rows untouched: the original alloc PKs still exist and
        # still point at the original tender Costings.
        self.assertTrue(tender_staff.filter(allocation_pk=self.alloc_labour.pk).exists())
        self.assertTrue(tender_staff.filter(allocation_pk=self.alloc_uli.pk).exists())

        # Execution clones: same hours + note + parent staff_hours,
        # different costing PK, pointing at the matching execution clone.
        for tender_alloc, expected_costing_name in (
            (self.alloc_labour, 'Site Labour'),
            (self.alloc_uli, 'Unexpected Line Items'),
        ):
            clone = exec_staff.get(
                staff_hours=tender_alloc.staff_hours,
                hours=tender_alloc.hours,
            )
            self.assertEqual(clone.costing.item, expected_costing_name)
            self.assertEqual(clone.costing.tender_or_execution, 2)
            self.assertNotEqual(clone.allocation_pk, tender_alloc.pk)
            self.assertEqual(clone.staff_hours_id, tender_alloc.staff_hours_id)
            self.assertEqual(clone.note, tender_alloc.note)

        # ---- Bill_allocations: 2 tender + 2 execution clones = 4 ----
        all_bill_allocs = Bill_allocations.objects.filter(bill__project=self.project)
        self.assertEqual(all_bill_allocs.count(), 4)
        self.assertEqual(
            all_bill_allocs.filter(item__tender_or_execution=1).count(), 2
        )
        self.assertEqual(
            all_bill_allocs.filter(item__tender_or_execution=2).count(), 2
        )

        # Tender rows untouched.
        self.assertTrue(
            all_bill_allocs.filter(bill_allocation_pk=self.bill_alloc_c1.pk).exists()
        )
        self.assertTrue(
            all_bill_allocs.filter(bill_allocation_pk=self.bill_alloc_uli.pk).exists()
        )

        # Same Bill record on both sides — only the per-line allocation
        # rows are duplicated.
        self.assertEqual(
            all_bill_allocs.values_list('bill_id', flat=True).distinct().count(),
            1,
        )

        # Execution clones: same dollar/qty/rate/notes, different
        # ``item`` FK pointing at the execution costing of the same name.
        for tender_alloc, expected_costing_name in (
            (self.bill_alloc_c1, 'Concrete'),
            (self.bill_alloc_uli, 'Unexpected Line Items'),
        ):
            clone = all_bill_allocs.exclude(
                bill_allocation_pk=tender_alloc.bill_allocation_pk
            ).get(
                item__tender_or_execution=2,
                item__item=expected_costing_name,
                amount=tender_alloc.amount,
            )
            self.assertEqual(clone.qty, tender_alloc.qty)
            self.assertEqual(clone.rate, tender_alloc.rate)
            self.assertEqual(clone.notes, tender_alloc.notes)
            self.assertEqual(clone.gst_amount, tender_alloc.gst_amount)
            self.assertEqual(clone.bill_id, tender_alloc.bill_id)

    def test_fix_contract_budget_uli_costing_cloned_no_special_casing(self):
        """The ULI category is just another Costing in the BoM at this point.

        The cloning loop iterates every tender costing for the project
        and remaps via ``costing_pk_mapping``, so ULI rides along
        without needing its own branch. Pin that explicitly: there
        should be a tender ULI Costing AND an execution ULI Costing
        after fix_contract_budget runs.
        """
        self._run_fix()

        uli_costings = Costing.objects.filter(
            project=self.project,
            category=self.cat_uli,
        )
        self.assertEqual(uli_costings.count(), 2)
        tes = sorted(uli_costings.values_list('tender_or_execution', flat=True))
        self.assertEqual(tes, [1, 2])

        # The execution ULI costing should have a staff-hour allocation
        # cloned from the tender side.
        exec_uli = uli_costings.get(tender_or_execution=2)
        self.assertTrue(
            StaffHoursAllocations.objects.filter(costing=exec_uli, hours=Decimal('2')).exists()
        )
        # And a Bill_allocation cloned too.
        self.assertTrue(
            Bill_allocations.objects.filter(item=exec_uli, amount=Decimal('50')).exists()
        )


class TenderExecutionRollupIsolationTests(TestCase):
    """
    With v254 cloning in place, ``compute_project_committed_billed`` must
    be uniformly TE-isolated — calling it with TE=1 must not leak any
    execution-side allocations and vice versa.

    Build a small fixture with one Costing on each side, both anchored
    via the same Bill (mimicking what ``fix_contract_budget`` produces),
    plus one StaffHours record split across the boundary.
    """

    @classmethod
    def setUpTestData(cls):
        cls.xero = XeroInstances.objects.create(
            xero_name='Test Xero TE', xero_client_id='te-client',
        )
        cls.project_type = ProjectTypes.objects.create(
            project_type='unit-test-te', rates_based=0,
        )
        cls.cat = Categories.objects.create(
            category='Materials', division=1, invoice_category='Materials',
            order_in_list=1,
        )
        cls.project = Projects.objects.create(
            project='TE Project', project_type=cls.project_type, project_status=2,
            xero_instance=cls.xero,
        )

        def _mk_costing(item, te):
            return Costing.objects.create(
                project=cls.project, category=cls.cat, item=item,
                xero_account_code='100',
                contract_budget=Decimal('0'),
                uncommitted_amount=Decimal('0'),
                fixed_on_site=Decimal('0'),
                sc_invoiced=Decimal('0'),
                sc_paid=Decimal('0'),
                tender_or_execution=te,
            )

        cls.tender_c = _mk_costing('Concrete', 1)
        cls.exec_c = _mk_costing('Concrete', 2)

        cls.supplier = Contacts.objects.create(
            xero_instance=cls.xero, xero_contact_id='te-contact',
            name='TE Supplier', email='te@example.com', status='ACTIVE', checked=1,
        )

        cls.bill = Bills.objects.create(
            project=cls.project,
            bill_status=Bills.STATUS_APPROVED,
            bill_type=1,
            contact_pk=cls.supplier,
            bill_date=date(2026, 1, 1),
            total_net=Decimal('100'),
            total_gst=Decimal('10'),
        )
        # Same bill carries BOTH tender and execution allocations,
        # mirroring what fix_contract_budget produces.
        Bill_allocations.objects.create(
            bill=cls.bill, item=cls.tender_c,
            amount=Decimal('100'), gst_amount=Decimal('10'),
            allocation_type=0,
        )
        Bill_allocations.objects.create(
            bill=cls.bill, item=cls.exec_c,
            amount=Decimal('100'), gst_amount=Decimal('10'),
            allocation_type=0,
        )

    def test_committed_billed_te_2_excludes_tender_bill_allocations(self):
        committed, billed, _ = svc.compute_project_committed_billed(
            self.project, tender_or_execution=2,
        )
        # Only the execution Costing PK should appear.
        self.assertIn(self.exec_c.pk, billed)
        self.assertNotIn(self.tender_c.pk, billed)
        self.assertEqual(billed[self.exec_c.pk], 100.0)
        self.assertIn(self.exec_c.pk, committed)
        self.assertNotIn(self.tender_c.pk, committed)
        self.assertEqual(committed[self.exec_c.pk], 100.0)

    def test_committed_billed_te_1_excludes_execution_bill_allocations(self):
        committed, billed, _ = svc.compute_project_committed_billed(
            self.project, tender_or_execution=1,
        )
        self.assertIn(self.tender_c.pk, billed)
        self.assertNotIn(self.exec_c.pk, billed)
        self.assertEqual(billed[self.tender_c.pk], 100.0)
        self.assertIn(self.tender_c.pk, committed)
        self.assertNotIn(self.exec_c.pk, committed)
        self.assertEqual(committed[self.tender_c.pk], 100.0)
