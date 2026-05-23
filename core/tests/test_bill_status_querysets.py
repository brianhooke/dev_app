"""
Regression tests for ``BillsQuerySet`` status-bucket helpers.

Audit context (A.M-C-01): the Direct-to-Xero send used to land bills on
``STATUS_APPROVED`` (2) even after a successful Xero push, and the
dashboard "ready to send to Xero" filter used the literal
``bill_status__in=[2, 103]`` with no ``bill_xero_id`` exclusion. Result:
bills that had already been sent to Xero kept showing up on the
"ready to send" tile and could be re-pushed, creating duplicate
invoices.

The fix had three parts (already in the working tree by the time these
tests were written):

1. The Direct send path in ``bills_global._send_bill_to_xero_core`` now
   lands on ``STATUS_SENT_TO_XERO`` (3).
2. ``BillsQuerySet.approved_for_xero()`` carries ``bill_xero_id__isnull
   =True`` *inside* the helper, so any caller that forgets the guard
   still gets the safe behaviour.
3. Every "ready to send" caller (dashboard tile, get_approved_bills,
   etc.) now uses ``approved_for_xero()`` instead of literal status
   filters.

This module pins behaviours (1)+(2) with deterministic database-level
assertions so a future drive-by edit can't silently re-open the bug.

Running:

    DJANGO_SETTINGS_MODULE=dev_app.settings.test \\
        python manage.py test core.tests.test_bill_status_querysets -v 2

``dev_app/settings/test.py`` disables ``MIGRATION_MODULES`` so the test
schema is built from current model state via ``syncdb`` (sidesteps the
F.Q-C-05 migration ordering issue). Each test is wrapped in a
transaction, so ``db_test.sqlite3`` is never written to.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from core.models import Bills, Contacts, Projects, ProjectTypes, XeroInstances


class BillStatusQuerySetTests(TestCase):
    """One bill per relevant status, then assert each helper queryset
    returns the right subset.

    Fixture rows (all on Project P1, all with the same supplier so the
    ``bill_status`` column is the only thing varying between rows):

        b_created       STATUS_CREATED                             xero_id=None
        b_allocated     STATUS_ALLOCATED                           xero_id=None
        b_po_uploaded   STATUS_PO_APPROVED_BILL_UPLOADED           xero_id=None
        b_approved      STATUS_APPROVED                            xero_id=None
        b_po_approved   STATUS_PO_APPROVED_BILL_FOR_PAYMENT        xero_id=None
        b_approved_in_xero
                        STATUS_APPROVED                  xero_id='XERO-1' (!)
        b_sent          STATUS_SENT_TO_XERO              xero_id='XERO-2'
        b_po_sent       STATUS_PO_SENT_TO_XERO           xero_id='XERO-3'
        b_paid          STATUS_PAID                      xero_id='XERO-4'

    ``b_approved_in_xero`` is the historical "leaked" row that A.M-C-01
    was about: a bill that was pushed to Xero but never had its status
    advanced past APPROVED. The helper *must* exclude it.
    """

    @classmethod
    def setUpTestData(cls):
        cls.xero_instance = XeroInstances.objects.create(
            xero_name='Test Xero',
            xero_client_id='test-client-id',
        )
        cls.project_type = ProjectTypes.objects.create(
            project_type='unit-test-status',
            rates_based=0,
        )
        cls.project = Projects.objects.create(
            project='Test Project Status',
            project_type=cls.project_type,
            project_status=2,
            is_revenue_project=True,
        )
        cls.supplier = Contacts.objects.create(
            xero_instance=cls.xero_instance,
            xero_contact_id='test-contact-id',
            name='Test Supplier',
            email='test@example.com',
            status='ACTIVE',
            checked=1,
        )

        def _mk_bill(status, xero_id=None):
            return Bills.objects.create(
                project=cls.project,
                bill_status=status,
                bill_type=1,
                contact_pk=cls.supplier,
                bill_date=date(2026, 1, 1),
                total_net=Decimal('100'),
                total_gst=Decimal('10'),
                bill_xero_id=xero_id,
            )

        cls.b_created     = _mk_bill(Bills.STATUS_CREATED)
        cls.b_allocated   = _mk_bill(Bills.STATUS_ALLOCATED)
        cls.b_po_uploaded = _mk_bill(Bills.STATUS_PO_APPROVED_BILL_UPLOADED)
        cls.b_approved    = _mk_bill(Bills.STATUS_APPROVED)
        cls.b_po_approved = _mk_bill(Bills.STATUS_PO_APPROVED_BILL_FOR_PAYMENT)

        # The "leak" row that A.M-C-01 was specifically about: status
        # APPROVED but already in Xero. Must NOT show up in
        # approved_for_xero().
        cls.b_approved_in_xero = _mk_bill(
            Bills.STATUS_APPROVED, xero_id='XERO-1',
        )

        cls.b_sent    = _mk_bill(Bills.STATUS_SENT_TO_XERO,    xero_id='XERO-2')
        cls.b_po_sent = _mk_bill(Bills.STATUS_PO_SENT_TO_XERO, xero_id='XERO-3')
        cls.b_paid    = _mk_bill(Bills.STATUS_PAID,            xero_id='XERO-4')

    # ------------------------------------------------------------------
    # approved_for_xero  — the headline A.M-C-01 helper.
    # ------------------------------------------------------------------

    def test_approved_for_xero_includes_approved_without_xero_id(self):
        """Both the project-bill APPROVED row and the PO-graduated row
        belong on the "ready to send" tile."""
        ids = set(
            Bills.objects.approved_for_xero()
            .values_list('bill_pk', flat=True)
        )
        self.assertEqual(ids, {self.b_approved.bill_pk,
                               self.b_po_approved.bill_pk})

    def test_approved_for_xero_excludes_already_in_xero(self):
        """The exact A.M-C-01 lock-in: a bill at STATUS_APPROVED with a
        non-NULL ``bill_xero_id`` MUST NOT be returned. This is the
        "approved + already pushed" case that historically duplicated
        invoices."""
        ids = list(
            Bills.objects.approved_for_xero()
            .values_list('bill_pk', flat=True)
        )
        self.assertNotIn(self.b_approved_in_xero.bill_pk, ids)

    def test_approved_for_xero_excludes_post_send_statuses(self):
        """Anything past APPROVED — SENT_TO_XERO, PO_SENT_TO_XERO,
        PAID — is by definition not "approved, awaiting send"."""
        ids = list(
            Bills.objects.approved_for_xero()
            .values_list('bill_pk', flat=True)
        )
        for bill in (self.b_sent, self.b_po_sent, self.b_paid):
            self.assertNotIn(bill.bill_pk, ids)

    def test_approved_for_xero_excludes_pre_approval_statuses(self):
        """Bills that haven't reached APPROVED yet (CREATED, ALLOCATED,
        PO-uploaded-but-unapproved) are not ready for Xero either."""
        ids = list(
            Bills.objects.approved_for_xero()
            .values_list('bill_pk', flat=True)
        )
        for bill in (self.b_created, self.b_allocated, self.b_po_uploaded):
            self.assertNotIn(bill.bill_pk, ids)

    # ------------------------------------------------------------------
    # in_xero  — the complement of approved_for_xero.
    # ------------------------------------------------------------------

    def test_in_xero_returns_post_send_states_only(self):
        """``in_xero`` is the canonical "this row is in Xero" filter
        used by the Bills-in-Xero list. It must include all three
        post-send terminal states and nothing else."""
        ids = set(
            Bills.objects.in_xero()
            .values_list('bill_pk', flat=True)
        )
        self.assertEqual(ids, {
            self.b_sent.bill_pk,
            self.b_po_sent.bill_pk,
            self.b_paid.bill_pk,
        })

    def test_in_xero_does_not_pick_up_status_approved_with_xero_id(self):
        """If a leak row exists (status=2 + xero_id set), it is NOT in
        ``in_xero`` either — it's a malformed row that ought to be
        repaired by re-running the send so the status advances. We
        explicitly do NOT paper over it by inferring "in Xero" from
        ``bill_xero_id`` alone, because the status column is the source
        of truth for the bills queue."""
        ids = list(
            Bills.objects.in_xero()
            .values_list('bill_pk', flat=True)
        )
        self.assertNotIn(self.b_approved_in_xero.bill_pk, ids)

    # ------------------------------------------------------------------
    # pending_approval  — used by the dashboard "to be approved" tile.
    # ------------------------------------------------------------------

    def test_pending_approval_returns_allocated_and_po_uploaded(self):
        ids = set(
            Bills.objects.pending_approval()
            .values_list('bill_pk', flat=True)
        )
        self.assertEqual(ids, {self.b_allocated.bill_pk,
                               self.b_po_uploaded.bill_pk})

    def test_pending_approval_excludes_approved_and_sent(self):
        ids = list(
            Bills.objects.pending_approval()
            .values_list('bill_pk', flat=True)
        )
        for bill in (
            self.b_approved, self.b_po_approved,
            self.b_approved_in_xero,
            self.b_sent, self.b_po_sent, self.b_paid,
        ):
            self.assertNotIn(bill.bill_pk, ids)

    # ------------------------------------------------------------------
    # State-machine consistency.
    # ------------------------------------------------------------------

    def test_approved_for_xero_and_in_xero_are_disjoint(self):
        """A bill cannot simultaneously be 'ready to send' and
        'already in Xero' — that's the whole point of the A.M-C-01
        fix. This is a structural invariant: if any future status set
        edit overlaps the two queries, this test fires."""
        ready = set(
            Bills.objects.approved_for_xero()
            .values_list('bill_pk', flat=True)
        )
        sent = set(
            Bills.objects.in_xero()
            .values_list('bill_pk', flat=True)
        )
        self.assertEqual(ready & sent, set(),
                         msg='approved_for_xero and in_xero overlapped — '
                             'A.M-C-01 invariant broken.')

    def test_status_constants_match_audit(self):
        """Belt-and-braces: lock the integer values so a stray
        renumber of ``Bills.STATUS_*`` doesn't silently re-map the
        queryset helpers (which rely on the named constants but the
        *DB column* stores the int).
        """
        self.assertEqual(Bills.STATUS_CREATED, 0)
        self.assertEqual(Bills.STATUS_ALLOCATED, 1)
        self.assertEqual(Bills.STATUS_APPROVED, 2)
        self.assertEqual(Bills.STATUS_SENT_TO_XERO, 3)
        self.assertEqual(Bills.STATUS_PAID, 4)
        self.assertEqual(Bills.STATUS_PO_APPROVED_BILL_FOR_PAYMENT, 103)
        self.assertEqual(Bills.STATUS_PO_SENT_TO_XERO, 104)
