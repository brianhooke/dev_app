"""
Regression tests for ``core.services.costing_rollups``.

Background (audit P-5 / A.M-R-02): Contract Budget and HC Claims used to
implement their committed/billed/invoiced loops *inline* in their view
modules. The two implementations drifted (different snap-match logic,
different progress-claim filter behaviour, different quote scope) and a
third "global" version lived in ``core/formulas.Committed`` and was
never called. This module is the canonical home for the rollup logic;
these tests pin the numbers so a future refactor can't change them
silently.

Numbers in this file are hand-checked. Each assertion comments how the
expected value is built up so that if a value changes, the diff makes
it obvious whether the change is intentional (new business rule) or a
regression.

Running:

    DJANGO_SETTINGS_MODULE=dev_app.settings.test \\
        python manage.py test core.tests.test_costing_rollups -v 2

``dev_app/settings/test.py`` disables ``MIGRATION_MODULES`` for every
app so the schema is built directly from current model state via
``syncdb`` — the historical migration set has the F.Q-C-05 ordering
issue and can't replay onto a fresh DB until the squash + db_table
cleanup lands. Each test method runs inside a transaction that's
rolled back on completion, so ``db_test.sqlite3`` is never written to.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from core.models import (
    Bills,
    Bill_allocations,
    Categories,
    Costing,
    Contacts,
    HC_claims,
    Projects,
    ProjectTypes,
    Quotes,
    Quote_allocations,
    StocktakeSnap,
    StocktakeSnapAllocation,
    StocktakeSnapItem,
    XeroInstances,
)
from core.services import costing_rollups as svc


class CostingRollupsTests(TestCase):
    """
    Build a single deterministic dataset and exercise every rollup function
    against it. Each test asserts a specific number with the maths in the
    docstring, so a regression jumps out in the failure message.

    Fixture (all on Project P1, tender_or_execution = execution = 2):

        Costings
            C1  Materials       contract_budget = 1000
            C2  Internal        contract_budget =  500
            C3  Labour          contract_budget =  200

        Quote Q1 (execution mode), allocations:
            -> C1: amount = 300, qty = 3, rate = 100
            -> C1: amount = 700, qty = 7, rate = 100   (same rate so no
                                                         "multiple_rates")

        Bill B1 (direct cost, bill_type = 1, bill_status = APPROVED):
            -> C1: amount = 400

        Bill B2 (progress claim, bill_type = 2, bill_status = APPROVED):
            -> C1: amount = 100, allocation_type = 1   ("direct cost in PC")
            -> C1: amount = 200, allocation_type = 0   ("as per bill_type")

        Stocktake snap S1 (status = FINALISED):
            snap_item -> C1
            snap_alloc -> P1, qty = 1, rate = 150, amount = 150
    """

    @classmethod
    def setUpTestData(cls):
        # ---------- supporting metadata ----------
        cls.xero_instance = XeroInstances.objects.create(
            xero_name='Test Xero',
            xero_client_id='test-client-id',
        )
        cls.project_type = ProjectTypes.objects.create(
            project_type='unit-test-rollup',
            rates_based=0,  # non-construction => committed_dict values are floats
        )

        # Categories. The Categories.save() override forces division=-10 for
        # 'Internal' and division=-5 for 'Labour' regardless of caller, so
        # we don't need to set those explicitly.
        cls.cat_materials = Categories.objects.create(
            category='Materials',
            division=1,
            invoice_category='Materials',
            order_in_list=1,
        )
        cls.cat_internal = Categories.objects.create(
            category='Internal',
            invoice_category='Internal',
            order_in_list=2,
        )
        cls.cat_labour = Categories.objects.create(
            category='Labour',
            invoice_category='Labour',
            order_in_list=3,
        )

        # ---------- project + costings ----------
        cls.project = Projects.objects.create(
            project='Test Project P1',
            project_type=cls.project_type,
            project_status=2,  # execution
            is_revenue_project=True,
        )

        def _mk_costing(item, category, contract_budget):
            return Costing.objects.create(
                project=cls.project,
                category=category,
                item=item,
                xero_account_code='100',
                contract_budget=Decimal(str(contract_budget)),
                uncommitted_amount=Decimal('0'),
                fixed_on_site=Decimal('0'),
                sc_invoiced=Decimal('0'),
                sc_paid=Decimal('0'),
                tender_or_execution=2,  # execution
            )

        cls.c1 = _mk_costing('Concrete', cls.cat_materials, 1000)
        cls.c2 = _mk_costing('Margin', cls.cat_internal, 500)
        cls.c3 = _mk_costing('Site Labour', cls.cat_labour, 200)

        # ---------- supplier contact ----------
        cls.supplier = Contacts.objects.create(
            xero_instance=cls.xero_instance,
            xero_contact_id='test-contact-id',
            name='Test Supplier',
            email='test@example.com',
            status='ACTIVE',
            checked=1,  # supplier
        )

        # ---------- quote + allocations ----------
        cls.quote = Quotes.objects.create(
            supplier_quote_number='Q1',
            total_cost=Decimal('1000'),
            contact_pk=cls.supplier,
            project=cls.project,
            tender_or_execution=2,
        )
        Quote_allocations.objects.create(
            quotes_pk=cls.quote, item=cls.c1,
            qty=Decimal('3'), rate=Decimal('100'), amount=Decimal('300'),
        )
        Quote_allocations.objects.create(
            quotes_pk=cls.quote, item=cls.c1,
            qty=Decimal('7'), rate=Decimal('100'), amount=Decimal('700'),
        )

        # ---------- direct-cost bill (counts in committed AND billed) ----------
        cls.bill_direct = Bills.objects.create(
            project=cls.project,
            bill_status=Bills.STATUS_APPROVED,
            bill_type=1,                       # direct cost
            contact_pk=cls.supplier,
            bill_date=date(2026, 1, 1),
            total_net=Decimal('400'),
            total_gst=Decimal('40'),
        )
        Bill_allocations.objects.create(
            bill=cls.bill_direct, item=cls.c1,
            amount=Decimal('400'), qty=Decimal('1'), rate=Decimal('400'),
            gst_amount=Decimal('40'), allocation_type=0,
        )

        # ---------- progress-claim bill (only allocation_type=1 lines count
        # toward HC invoiced; *all* lines count toward Billed). Both lines
        # are excluded from Contract-Budget Committed because that loop
        # restricts to bill_type__in=[0,1]. ----------
        cls.bill_pc = Bills.objects.create(
            project=cls.project,
            bill_status=Bills.STATUS_APPROVED,
            bill_type=2,                       # progress claim
            contact_pk=cls.supplier,
            bill_date=date(2026, 2, 1),
            total_net=Decimal('300'),
            total_gst=Decimal('30'),
        )
        Bill_allocations.objects.create(
            bill=cls.bill_pc, item=cls.c1,
            amount=Decimal('100'), qty=Decimal('1'), rate=Decimal('100'),
            gst_amount=Decimal('10'), allocation_type=1,
        )
        Bill_allocations.objects.create(
            bill=cls.bill_pc, item=cls.c1,
            amount=Decimal('200'), qty=Decimal('2'), rate=Decimal('100'),
            gst_amount=Decimal('20'), allocation_type=0,
        )

        # ---------- finalised stocktake snap ----------
        cls.snap = StocktakeSnap.objects.create(
            date=date(2026, 3, 1),
            costing_method='AVG',
            status=StocktakeSnap.STATUS_FINALISED,
        )
        cls.snap_item = StocktakeSnapItem.objects.create(
            snap=cls.snap,
            item=cls.c1,
            book_qty=Decimal('5'),
            counted_qty=Decimal('4'),  # variance = -1 -> consumed
        )
        # ``StocktakeSnapAllocation.save()`` recomputes amount = qty * rate,
        # so we don't need to set it explicitly — set it anyway so the
        # fixture is self-documenting.
        cls.snap_alloc = StocktakeSnapAllocation.objects.create(
            snap_item=cls.snap_item,
            project=cls.project,
            qty=Decimal('1'),
            rate=Decimal('150'),
            amount=Decimal('150'),
        )

    # ------------------------------------------------------------------
    # Per-item primitives.
    # ------------------------------------------------------------------

    def test_committed_for_item(self):
        """Quotes ($300+$700) + bills.committed() (B1 $400 + B2 $100+$200) = $1700.

        ``BillAllocationsQuerySet.committed()`` filters bill_status in
        [STATUS_ALLOCATED, STATUS_PO_PROGRESS_REJECTED), which is 1..98
        — so STATUS_APPROVED (2) is included. The committed() filter does
        NOT apply the progress-claim allocation_type filter, so both B2
        allocations count.
        """
        self.assertEqual(svc.committed_for_item(self.c1.pk), Decimal('1700'))

    def test_settled_for_item_uses_settled_set(self):
        """Settled = bills with status in ``STATUSES_SETTLED_FOR_HC_CLAIM``.

        Both B1 and B2 are STATUS_APPROVED (which is in the historical
        settled set), so all three allocations count: 400 + 100 + 200 = 700.
        """
        self.assertEqual(svc.settled_for_item(self.c1.pk), Decimal('700'))

    # ------------------------------------------------------------------
    # Per-project simple rollups.
    # ------------------------------------------------------------------

    def test_committed_by_costing_for_project(self):
        """Project-scoped variant of ``committed_for_item``.

        Only C1 has any allocations against it. Numbers match
        test_committed_for_item.
        """
        result = svc.committed_by_costing_for_project(self.project.pk)
        self.assertEqual(result, {self.c1.pk: Decimal('1700')})

    def test_invoiced_amounts_for_project_applies_progress_filter(self):
        """Settled set + canonical bill_type filter.

        - B1 (bill_type=1, status=APPROVED): all allocations pass -> $400.
        - B2 (bill_type=2, status=APPROVED): only allocation_type=1
          passes the canonical filter -> $100. The $200 allocation_type=0
          line is excluded (otherwise it would double-count alongside its
          direct-cost siblings — audit A.M-C-12).

        Total for C1 = $500.
        """
        result = svc.invoiced_amounts_for_project(self.project.pk)
        self.assertEqual(result, {self.c1.pk: Decimal('500')})

    def test_invoiced_amounts_without_progress_filter_keeps_all_allocations(self):
        """include_progress_claim_only=False keeps the $200 PC allocation.

        Without the canonical filter, all settled-bill allocations count
        regardless of allocation_type: 400 + 100 + 200 = 700.
        """
        result = svc.invoiced_amounts_for_project(
            self.project.pk, include_progress_claim_only=False
        )
        self.assertEqual(result, {self.c1.pk: Decimal('700')})

    def test_project_committed_total_matches_per_item_sum(self):
        self.assertEqual(svc.project_committed_total(self.project.pk), Decimal('1700'))

    # ------------------------------------------------------------------
    # Contract Budget rollup (full {qty, rate, amount} dict shape).
    # ------------------------------------------------------------------

    def test_compute_project_committed_billed_non_construction(self):
        """Pin every cell of the committed_dict and billed_dict.

        Contract Budget commits include:
          quotes ($300+$700) + Internal contract_budget for C2 ($500)
          + Labour wages for C3 ($0, no staff hours fixture)
          + finalised snap ($150 to C1)
          + direct-cost bills (B1 only — B2 excluded by bill_type filter): $400 to C1
        => committed_dict = {C1: 1550, C2: 500, C3: 0}

        Billed includes ALL bill allocations (every bill_type) + snap +
        staff hours wages:
          B1 ($400) + B2 ($100+$200) + snap ($150) = $850 to C1
        => billed_dict = {C1: 850}
        """
        committed, billed, is_construction = svc.compute_project_committed_billed(
            self.project, tender_or_execution=2
        )

        self.assertFalse(is_construction)

        self.assertEqual(committed[self.c1.pk], 1550.0)   # quotes 1000 + snap 150 + direct bill 400
        self.assertEqual(committed[self.c2.pk], 500.0)    # Internal contract_budget
        self.assertEqual(committed[self.c3.pk], 0.0)      # Labour, no allocations

        self.assertEqual(billed, {self.c1.pk: 850.0})     # 400 + 100 + 200 + 150

    def test_compute_project_committed_billed_other_scope_documents_quirk(self):
        """tender_or_execution=1 — pin the slightly-surprising scoping rules.

        The function scopes most loops by tender_or_execution but NOT bills:

          * Quotes: scoped (Q1 is execution, so excluded) -> 0
          * Internal contract_budget: scoped (C2 is execution) -> 0
          * Labour wages: scoped (C3 is execution) -> 0
          * Stocktake snaps: gated by project_costing_pks, which is built
            from scoped costings -> empty set -> snap excluded
          * Direct-cost bills: NOT scoped by tender_or_execution (Bills
            and Bill_allocations don't carry that concept). B1's $400
            allocation to C1 still lands in committed_dict.

        Result: committed = {C1: 400} (just B1).

        Billed mirrors:
          * All bill allocations: NOT scoped -> B1 ($400) + B2 ($100+$200)
          * Snap: gated by project_costing_pks (empty) -> excluded
          * Staff hours: scoped (costing__tender_or_execution=1) -> 0
        Result: billed = {C1: 700}.

        Documenting this here because the asymmetry (snap rolls up into
        billed for in-scope costings only, but bills roll up regardless)
        is easy to miss when reading the function and is exactly the
        kind of behaviour that drifts. If a future change tightens
        bill scoping or loosens snap scoping, this test will fail and
        force the change to be conscious.
        """
        committed, billed, is_construction = svc.compute_project_committed_billed(
            self.project, tender_or_execution=1
        )
        self.assertFalse(is_construction)
        self.assertEqual(committed, {self.c1.pk: 400.0})
        self.assertEqual(billed,    {self.c1.pk: 700.0})

    # ------------------------------------------------------------------
    # HC Claims rollups (deliberately narrower scope than Contract Budget).
    # ------------------------------------------------------------------

    def test_hc_committed_amounts_excludes_internal_labour_and_bills(self):
        """HC committed = quotes + finalised snaps. Nothing else.

        Internal contract_budget (C2 = $500) and Labour wages (C3) are
        intentionally NOT folded in — those are Contract Budget concepts.
        Direct-cost bills are also excluded (they live on the invoiced
        side of the HC claim, not the committed side).

        => result = {C1: 1000 (quotes) + 150 (snap) = 1150}
        """
        result = svc.hc_committed_amounts(self.project.pk)
        self.assertEqual(result, {self.c1.pk: 1150.0})

    def test_hc_invoiced_amounts_no_claim(self):
        """No claim attached; in_claim should be 0 for every line.

        Canonical filter applied:
          B1 (direct cost, status=APPROVED): $400  -> invoiced += 400, paid += 400
          B2 (PC, status=APPROVED): only allocation_type=1 passes
                                                   -> invoiced += 100, paid += 100
        => {C1: {invoiced: 500, paid: 500, in_claim: 0}}
        """
        result = svc.hc_invoiced_amounts(self.project.pk, claim=None)
        self.assertEqual(result, {self.c1.pk: {'invoiced': 500.0, 'paid': 500.0, 'in_claim': 0}})

    def test_hc_invoiced_amounts_with_claim(self):
        """Tag B1 to a claim; in_claim should pick up its $400 only."""
        claim = HC_claims.objects.create(
            project=self.project, date=date(2026, 4, 1), status=0,
        )
        Bills.objects.filter(pk=self.bill_direct.pk).update(associated_hc_claim=claim)

        result = svc.hc_invoiced_amounts(self.project.pk, claim=claim)

        bucket = result[self.c1.pk]
        self.assertEqual(bucket['invoiced'], 500.0)
        self.assertEqual(bucket['paid'],     500.0)
        self.assertEqual(bucket['in_claim'], 400.0)  # only B1, not the PC

    # ------------------------------------------------------------------
    # Direct queryset-helper coverage (audit A.M-R-03 / A.M-H-02).
    #
    # The rollup tests above already exercise these indirectly, but we
    # also assert the helpers in isolation so that a future caller
    # wiring up the queryset directly can rely on the published
    # contract.
    # ------------------------------------------------------------------

    def test_direct_cost_lines_excludes_progress_claim_bills(self):
        """``direct_cost_lines`` keeps bill_type 0/1, drops bill_type=2.

        Fixture has B1 (direct cost, 1 allocation) and B2 (progress
        claim, 2 allocations). direct_cost_lines should return B1 only.
        """
        from core.models import Bill_allocations

        rows = list(
            Bill_allocations.objects.direct_cost_lines()
            .filter(bill__project=self.project)
            .values_list('bill__bill_type', 'amount')
        )
        self.assertEqual(rows, [(1, Decimal('400'))])

    def test_counts_toward_hc_invoiced_canonical_filter(self):
        """The progress-claim wrap-up line ($200, allocation_type=0) is excluded.

        Total expected = B1 ($400) + B2's allocation_type=1 line ($100).
        The B2 allocation_type=0 line is dropped — that's the whole
        point of the canonical filter.
        """
        from core.models import Bill_allocations
        from django.db.models import Sum

        total = (
            Bill_allocations.objects.counts_toward_hc_invoiced()
            .filter(bill__project=self.project)
            .aggregate(t=Sum('amount'))['t']
        )
        self.assertEqual(total, Decimal('500'))

    def test_committed_queryset_includes_full_active_status_band(self):
        """``committed`` keeps bills in [STATUS_ALLOCATED, STATUS_PO_PROGRESS_REJECTED).

        Both fixture bills are STATUS_APPROVED — comfortably inside the
        band — so all three allocations land. Add a STATUS_CREATED bill
        and verify it's excluded; add a STATUS_PO_PROGRESS_REJECTED bill
        and verify the upper bound is exclusive.
        """
        from core.models import Bill_allocations
        from django.db.models import Sum

        baseline = (
            Bill_allocations.objects.committed()
            .filter(bill__project=self.project)
            .aggregate(t=Sum('amount'))['t']
        )
        self.assertEqual(baseline, Decimal('700'))  # 400 + 100 + 200

        unsettled = Bills.objects.create(
            project=self.project,
            bill_status=Bills.STATUS_CREATED,           # below the floor
            bill_type=1,
            contact_pk=self.supplier,
            bill_date=date(2026, 6, 1),
            total_net=Decimal('99'),
            total_gst=Decimal('9'),
        )
        Bill_allocations.objects.create(
            bill=unsettled, item=self.c1,
            amount=Decimal('99'), gst_amount=Decimal('9'),
        )
        rejected = Bills.objects.create(
            project=self.project,
            bill_status=Bills.STATUS_PO_PROGRESS_REJECTED,  # above the ceiling
            bill_type=1,
            contact_pk=self.supplier,
            bill_date=date(2026, 6, 2),
            total_net=Decimal('11'),
            total_gst=Decimal('1'),
        )
        Bill_allocations.objects.create(
            bill=rejected, item=self.c1,
            amount=Decimal('11'), gst_amount=Decimal('1'),
        )

        after = (
            Bill_allocations.objects.committed()
            .filter(bill__project=self.project)
            .aggregate(t=Sum('amount'))['t']
        )
        self.assertEqual(after, Decimal('700'))  # neither $99 nor $11 included

    def test_bills_direct_cost_helper_matches_allocation_helper(self):
        """``Bills.objects.direct_cost`` and
        ``Bill_allocations.objects.direct_cost_lines`` should agree on what
        counts as a direct-cost bill — they're two views of the same rule.
        """
        from core.models import Bill_allocations

        bills_via_bill_qs = set(
            Bills.objects.direct_cost()
            .filter(project=self.project)
            .values_list('bill_pk', flat=True)
        )
        bills_via_alloc_qs = set(
            Bill_allocations.objects.direct_cost_lines()
            .filter(bill__project=self.project)
            .values_list('bill_id', flat=True)
        )
        self.assertEqual(bills_via_bill_qs, bills_via_alloc_qs)

    def test_hc_invoiced_amounts_drops_unsettled_bills_from_paid(self):
        """A bill in STATUS_CREATED still contributes to invoiced but NOT paid.

        Adds a 4th allocation on a fresh STATUS_CREATED direct-cost bill.
        Note: STATUS_CREATED (0) is below the committed() floor too,
        so this bill won't appear in any rollup that uses committed().
        It SHOULD appear in invoiced (which uses the canonical Q-filter,
        not committed()) but should NOT be marked paid.
        """
        unsettled = Bills.objects.create(
            project=self.project,
            bill_status=Bills.STATUS_CREATED,
            bill_type=1,
            contact_pk=self.supplier,
            bill_date=date(2026, 5, 1),
            total_net=Decimal('50'),
            total_gst=Decimal('5'),
        )
        Bill_allocations.objects.create(
            bill=unsettled, item=self.c1,
            amount=Decimal('50'), qty=Decimal('1'), rate=Decimal('50'),
            gst_amount=Decimal('5'), allocation_type=0,
        )

        # ``invoiced_amounts_for_project`` filters by
        # STATUSES_SETTLED_FOR_HC_CLAIM, so it excludes STATUS_CREATED — this
        # is a property of the project-scoped variant. Confirm it still
        # returns the original $500.
        self.assertEqual(
            svc.invoiced_amounts_for_project(self.project.pk),
            {self.c1.pk: Decimal('500')},
        )

        # ``hc_invoiced_amounts`` (the per-item HC claim helper) does NOT
        # apply the settled filter to the queryset itself — it instead
        # tags each allocation as paid/not based on the bill's status.
        # So a STATUS_CREATED bill *should* appear in invoiced, with
        # paid = 0. That's the contract; pin it.
        result = svc.hc_invoiced_amounts(self.project.pk, claim=None)
        bucket = result[self.c1.pk]
        self.assertEqual(bucket['invoiced'], 550.0)  # 500 + 50
        self.assertEqual(bucket['paid'],     500.0)  # unchanged — unsettled bill not "paid"
        self.assertEqual(bucket['in_claim'], 0)
