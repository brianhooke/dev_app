# Session Handoff — Mason / dev_app

**Last updated:** 23 May 2026 (v252 — P-5 / A.M-R-02 + A.M-R-03 + B.V-H-02 + A.M-C-01 + dead-code cleanup)
**Read this first** if you are picking up the audit cleanup work in a new chat.

---

## Deploy state (resolved)

- **Live on EB**: `v252` (deployed 23 May 2026 13:32 UTC, commit `f0078ee`). Costing-rollup migration + bill-allocation queryset helpers + bill-status filter sweep + A.M-C-01 lock-in + A.M-H-16 dead-Xero-endpoint deletion + A.M-H-01 dead-formulas-cleanup all in front of users. Status: `Ready`. Health: `Grey` (cosmetic — the `/health/` endpoint doesn't actually probe the DB; see "Remaining deploy hygiene to-dos" below).
- **GitHub `main`**: at `f0078ee` (v252).
- **RDS state**: All 80 core migrations applied. v252 is a code-only deploy (no new migrations).
- **Predecessor**: v251 (`13718ed`) was the surgical RDS-migration-state reconciliation that recovered the v250 deploy crash; that history is preserved in the "Recovery story" section below.
- Verification: `curl http://dev-app-docker.eba-mkynfeyv.ap-southeast-2.elasticbeanstalk.com/` returns `302 → /accounts/login/?next=/` with `X-Frame-Options: SAMEORIGIN` and `X-Content-Type-Options: nosniff`. Login-required middleware and clickjacking protection both confirmed active post-v252.

### Recovery story (what happened and why it now works)

The v250 deploy initially crashed because production RDS was 5 months behind on migrations (last applied `0046` from Jan 14 2026), but the Feb 7 `start.sh` had `migrate --noinput || echo "Migrations failed, continuing..."` — migrations were silently failing on every container start and the app was running on a half-applied schema. The audit pass made `migrate` fatal (correctly), which surfaced the issue.

To fix:

1. **Snapshot taken**: `dev-app-db-pre-v250-fix-20260523-221139` (still in RDS, available).
2. **Schema drift mapped**: `core_invoices` had bill_* columns from migration 0037's column rename, but Django's `Bills` model state had never been recorded. Tables `project_types` / column `core_categories.division` / column `core_invoices.contact_pk_id` and similar already existed because someone had applied the schema parts manually outside Django's tracking.
3. **Surgical migration sequence**:
   - **Faked** 0047 (CreateModel(Bills) where the table already existed with matching columns).
   - **Faked** 0048 (CreateModel(ProjectTypes) where the table already existed).
   - **Faked** 0049 (project_type FK migration where `project_type_id` already existed).
   - **Manually dropped** the orphan `core_categories.division` column (0 rows), then ran 0050 normally to re-add it cleanly along with `project_types.archived`.
   - **Manually added** `core_costing.xero_tracking_category` (because faked 0047 said it was added but didn't actually run).
   - **Real-applied** 0051..0067 (project types updates, public holiday tables, employee/staff hours, stocktake tables, bills.is_stocktake, FX fields, etc.).
   - **Real-applied** 0068 onward (drops the tracking_category trio + `xero_tracking_categories` table; data migrations were no-ops since all tables had 0 rows).
4. **v250 redeployed**: clean migrate, gunicorn responding.

The diagnostic and migration scripts that did this work are in `scripts/`:

- `scripts/inspect_rds_state.py` — read-only RDS inspector. Pulls EB env vars via boto3, connects, prints migration state and key columns.
- `scripts/inspect_rds_state2.py` — round-2 (lists all public tables, not just `core_*`).
- `scripts/preflight_migrations.py` — symbolically scans pending migrations vs the actual schema and predicts conflicts before you run `migrate`.

If you ever need to redo this kind of reconciliation: snapshot first, run preflight, then apply with selective `--fake`s as needed.

### Important production-data note

**RDS has 0 rows in every business table.** `core_projects`, `core_costing`, `core_invoices`, `core_po_orders`, `core_hc_claims`, `core_quotes`, etc., are all empty. Only `auth_user` has 2 rows. The user has confirmed the data isn't on this instance — possibly local docker, possibly somewhere I don't have visibility into. The other RDS instance (`pod-app-aws-db`) is in `inaccessible-encryption-credentials` state (KMS key was deleted) and is effectively dead.

If you need to know where the user actually keeps production data, **ask before assuming**.

### Remaining deploy hygiene to-dos

- `start.sh` still does `dumpdata core --natural-foreign --natural-primary` as a "pre-migration backup" but this raises `CommandError: Unable to serialize database: cursor "..." does not exist` on every start (the script swallows it). Either fix the serialiser bug (probably an FK ordering issue post-rename) or replace this with a scheduled RDS snapshot job.
- `health_endpoint` (`core/views/main.py`) is a 200-OK Django view that doesn't actually check the DB. EB Health stays Grey because of this. Consider making it `SELECT 1;` against the DB so EB can detect crash loops automatically next time.
- The deploy that succeeded was triggered with `eb deploy --version <label>` (re-deploying v250 by version label rather than by archive). Direct `eb deploy` from the working tree also works once RDS is at 0080.

---

## Where we are right now

We are mid-way through executing `BEST_PRACTICE_AUDIT.md`. Three big phases are done:

1. **The "if you only do 12 things" priority queue (P-1 … P-12)** — done in a previous session.
   - Includes secret rotation (`SECRET_KEY`, `EMAIL_API_SECRET_KEY` / Lambda `API_SECRET_KEY`, `RDS_PASSWORD`).
   - **`XERO_ENCRYPTION_KEY` was deliberately *not* rotated** — that's destructive and needs its own scheduled outage. See `docs/SECRET_ROTATION_RUNBOOK.md`.
2. **Section 3 critical findings** — done in the previous session.
   - 14 critical items closed; 2 explicitly deferred (`G.X-C-06`, `F.Q-C-05`).
3. **Costing-rollup migration (P-5 / A.M-R-02) + Bill-allocation queryset helpers (A.M-R-03 / A.M-H-02) + Bill-status filter sweep (B.V-H-02) + A.M-C-01 lock-in + A.M-H-16 dead Xero endpoints + A.M-H-01 dead-code cleanup** — done in this session.
   - ~370 lines of inline rollup logic moved from `core/views/contract_budget.py` and `core/views/hc_claims.py` into `core/services/costing_rollups.py`. Both views now keep one-line legacy aliases at the top so any external imports keep working.
   - Canonical bill-allocation filters promoted to queryset methods on `BillAllocationsQuerySet`: `direct_cost_lines()` and `counts_toward_hc_invoiced()`, plus a matching `BillsQuerySet.direct_cost()` shorthand. The Q-literal `bill_type IN (0,1) OR (bill_type=2 AND allocation_type=1)` now lives in **exactly one place** (the queryset class). All callers migrated.
   - **Bill-status filter sweep (B.V-H-02)**: every `bill_status__in=[...]` literal in active code paths has been replaced with the matching `BillsQuerySet` method (`pending_approval`, `approved_for_xero`, `in_xero`). Magic numbers like `bill.bill_status = 0` swapped for named constants. The dashboard's "ready for Xero" count uses `approved_for_xero()` which folds in `bill_xero_id IS NULL`.
   - **A.M-C-01 closed**: the live Direct-send path in `bills_global._send_bill_to_xero_core` already lands on `STATUS_SENT_TO_XERO` (3) — verified by reading the workflow branch around line 819. Combined with the B.V-H-02 sweep that puts every "ready to send" caller behind `approved_for_xero()` (which carries `bill_xero_id__isnull=True` *inside* the helper), the bug is structurally closed. Locked with 10 deterministic regression tests in `core/tests/test_bill_status_querysets.py` covering every status bucket plus the structural invariant `approved_for_xero ∩ in_xero = ∅`.
   - **A.M-H-16 closed**: the two pre-OAuth2 legacy Xero endpoints `post_bill` and `test_xero_bill` are deleted. Both were already gated by `raise NotImplementedError`, had no UI callers, and still carried the historical `bill_status = STATUS_APPROVED` write after a Xero send. URL routes `/post_bill/` and `/test_xero_bill/` removed from `core/urls.py`. The `core/views/__init__` re-exports + the legacy section of the bills.py header docstring + the now-unused `requests` and `urljoin` imports are all gone.
   - Dead code `formulas.Committed()` and its 4 stale imports deleted (A.M-H-01).
   - Latent `NameError` / `AttributeError` in CB's billed-side snap loop fixed (A.M-C-13's cleanup missed the second use of `item_name_to_costing` plus the loop was iterating a `.values()` queryset using object access — would have crashed on the first finalised snap).
   - `core/tests/test_costing_rollups.py` pins the rollup numbers (16 tests). `core/tests/test_bill_status_querysets.py` pins the bill-status guards (10 tests). All 26 pass. Tests run via `python manage.py test core.tests.test_costing_rollups core.tests.test_bill_status_querysets` thanks to the `MIGRATION_MODULES = _DisableMigrations()` shim in `dev_app/settings/test.py` (sidesteps F.Q-C-05 by using `syncdb` from current model state instead of replaying migrations).

A full status dashboard with per-item outcomes lives at the **top** of `BEST_PRACTICE_AUDIT.md` in section `## 0. Status`. Read that before doing anything else.

## Where to start

1. Open `BEST_PRACTICE_AUDIT.md` and read **§0 Status** end-to-end.
2. Read the table headed **"Still deferred — needs dedicated work"** in §0. Those items are the next sensible chunks of work.
3. Ask the user which deferred item to tackle, or let them tell you. **Don't pick on your own** — some of these (e.g. the migration squash) need the user's call on tradeoffs.

## What to **not** redo

The following are **already complete**; don't re-fix them:

- Secret rotation (except `XERO_ENCRYPTION_KEY`).
- Static-asset cleanup (`background.png` 37 MB, `mason_steampunk.mp4`, etc.) — already deleted.
- Repo hygiene: `.venv/`, vendored `certifi/`/`charset_normalizer/`/`idna/`/`requests/`/`urllib3/`, `db.sqlite3`, `get-pip.py`, `eb_logs.txt`, `Procfile`, `Aptfile`, `runtime.txt`, `dev_app/settings/production.py`, `core/tests.py`, three `DEPRECATED_bills_global_*.html` files — all removed.
- `core/views/_helpers.py` exists with `json_ok`, `json_err`, `@api_login_required`, `@api_public`. P-3 migrated `projects.py`, `pos.py`, `email_receiver.py` as the pattern. Other modules still bare `@csrf_exempt` — opportunistic migration as you touch them.
- `core/static/core/js/utils.js`: debug code stripped (1632 → 1019 lines). `Money.formatAUD` is the canonical money pipeline (in `core/static/core/js/money.js`).
- Bootstrap 4-vs-5 modal mismatch: a compatibility shim was added at the top of `core/templates/core/dashboard_master.html` (the `(function(){ ... })()` block right after `bootstrap.min.js`). Don't remove it until the codebase is moved to BS5.
- `Bills.STATUSES_SETTLED_FOR_HC_CLAIM` is **deliberately unchanged**. The audit (`A.M-C-02`) flagged that calling merely-approved bills "paid" suppresses claimable amounts, but changing the constant moves money on every HC claim and needs Mason's business owner to confirm. The model docstring carries the audit note.

## Suggested next moves (ranked by leverage)

These all come straight from §0's deferred list:

1. **Full `@csrf_exempt` sweep** — clean drop-in mechanical work. Open each `core/views/*.py` and `construction/views/*.py` not yet migrated, replace `@csrf_exempt` with `@api_login_required` (staff-facing) or `@api_public` (genuinely public, signed). Run the matching JS through the dashboard to verify.
2. **Lower-impact `transaction.atomic` wraps** — `dashboard.create_category`, `dashboard.create_item`, `dashboard.send_po_email`'s pre-PDF block, `email_receiver.receive_email`, `main.upload_categories`, `main.upload_letterhead`, `staff_hours.create_holiday_calendar` / `update_holiday_calendar` / `save_allocation`. Mechanical wrap, ~20 minutes total. None of these are silent-money-bug paths.
3. **Bill-status state machine centralisation (A.M-R-01)** — the audit's other large named refactor. The Bills `STATUS_*` constants exist on the model and a few queryset helpers (`pending_approval`, `approved_for_xero`, `in_xero`, `settled_for_hc_claim`) cover some transitions, but views still call `bill.bill_status = N; bill.save()` ad-hoc. Codify the legal transitions in a `BillWorkflow` service and have views call events instead. Higher payoff than 4 below — these are real correctness paths (e.g. A.M-C-09 "approve_bill_direct skips allocated state").
4. **G.X-C-06 invoice→bill rename completion** — only do this in a dedicated PR. ~100 surfaces. The model class is `Bills`, fields are `bill_*`, but URL paths still say `/invoice/...`, JS still posts `invoice_id`. Cosmetic only — no live correctness bug.
5. **F.Q-C-05 migration squash** — also dedicated PR. Tests don't run on a fresh DB because migration `0037` did `RENAME COLUMN` against the existing `core_invoices` table; a fresh schema build can't resolve the FK. Decide between (a) rename tables to `core_bills`/`core_bill_allocations` with another `RENAME TABLE` migration, or (b) commit to `db_table='core_invoices'` and document. **Note:** the new test suite (`core/tests/test_costing_rollups.py`) sidesteps this by using `MIGRATION_MODULES = _DisableMigrations()` in `dev_app/settings/test.py` — that workaround is fine until the squash lands but should be removed in the same PR that fixes F.Q-C-05.
6. **Per-section JS extraction (P-9 / C.T-R-11)** — large but high payoff for reviewer. Priority order: `stocktake.html`, `staff_hours.html`, `bills_global.html`, `rates_table.html`, `hc_claims.html`, `contract_budget.html`.

## Operational notes

- **Deploys go to AWS Elastic Beanstalk** (Docker-based). Use `eb deploy --profile default` from the repo root. The `eb-cli` profile referenced in `.elasticbeanstalk/config.yml` does *not* exist; pass `--profile default` explicitly.
- **Region**: `ap-southeast-2`.
- **Live env name**: check with `eb list --profile default`.
- **Health endpoint**: `/health/` (currently a Django view; not yet a real systems check).
- **Migrations**: run on each deploy via `start.sh`. Watch the EB logs for `migrate` failures.

## Files the next session should be aware of

| Path | Why it matters |
|---|---|
| `BEST_PRACTICE_AUDIT.md` (§0 Status, then §3 Critical) | The single source of truth on what's done and what's left. |
| `docs/SECRET_ROTATION_RUNBOOK.md` | Procedures for rotating each secret, including what to do about `XERO_ENCRYPTION_KEY`. |
| `core/views/_helpers.py` | Decorators + JSON envelope helpers introduced in P-3. |
| `core/services/costing_rollups.py` | Canonical rollup primitives. The HC/Contract Budget views still don't use them — that migration is the next big lever. |
| `core/static/core/js/money.js` | `window.Money.formatAUD` is the canonical money pipeline. |
| `core/static/core/js/utils.js` | Trimmed; only `Utils.api()`-style helpers and a small kit of formatters/dropdown helpers remain. |
| `dev_app/settings/base.py` and `production_aws.py` | `SecurityMiddleware` + `XFrameOptionsMiddleware` are re-enabled. Production now fails fast on missing required env vars. |
| `core/templates/core/dashboard_master.html` | BS4-vs-BS5 compatibility shim. Keep it until BS5 migration. |
| `core/models.py` | Look at `Bills.STATUSES_SETTLED_FOR_HC_CLAIM` and the docstring above it for the deferred A.M-C-02 business decision. |

## How to confirm the env is healthy before starting

```bash
# All Python compiles cleanly.
python3 -c "
import compileall, sys
ok = (compileall.compile_dir('core', quiet=1) and
      compileall.compile_dir('construction', quiet=1) and
      compileall.compile_dir('dev_app', quiet=1))
sys.exit(0 if ok else 1)
"

# Django boots.
DJANGO_SETTINGS_MODULE=dev_app.settings.local python3 -c "
import django; django.setup()
from django.urls import get_resolver
get_resolver().url_patterns
print('OK')
"

# JS parses.
node -e "new Function(require('fs').readFileSync('core/static/core/js/utils.js','utf8'))" && echo "JS OK"
```

If any of these fail, **stop and show the user** before touching anything.
