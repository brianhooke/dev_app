# Session Handoff — Mason / dev_app

**Last updated:** 23 May 2026 (v250 commit pushed; v250 deploy FAILED → rolled back to Feb 7 build)
**Read this first** if you are picking up the audit cleanup work in a new chat.

---

## ⚠ URGENT — Deploy state right now

- **Live on EB**: `app-ALL_IN_ONE_WORKING_VERSION-460-g513d-260207_222940776796` (commit `513d…`, Feb 7 2026). This was rolled back to manually after v250 crash-looped.
- **GitHub `main`**: at v250 (commit `894ff43`). Includes all priority-queue (P-1..P-12) and Section 3 critical fixes documented below.
- **The two are out of sync.** The next session **must** reconcile schema drift on RDS before re-deploying main.

### What happened

The v250 deploy uploaded fine and EB reported "Environment update completed successfully", but the gunicorn container crash-looped on `start.sh` migrate step:

```
psycopg2.errors.DuplicateTable: relation "core_invoices" already exists
django.db.utils.ProgrammingError: relation "core_invoices" already exists
```

The migration that hit this is whichever one Django decided to apply first against RDS. The error means RDS has the `core_invoices` table but `django_migrations` does not have the corresponding `core.<NNNN>` row marked applied.

**Important context:**

- There were **zero migration file changes between v249 and v250** (`git diff 8777b06..HEAD -- 'core/migrations/' 'construction/migrations/'` is empty), so v250 didn't add any migration that would explain this.
- The previously deployed EB version (`460-g513d`, Feb 7) ran the same `start.sh` against the same RDS without crashing. So either (a) Feb 7's container was crash-looping silently and the user never noticed because requests went somewhere stale, or (b) the RDS schema/migration state changed since Feb 7 (`migrate --fake` somewhere, restored backup, manual `RENAME TABLE`, partial run of `0037_rename_invoice_to_bill`, etc.).
- The user rotated `RDS_PASSWORD` earlier today via `docs/SECRET_ROTATION_RUNBOOK.md`. That should not have touched schema, but it's worth verifying the RDS instance ID is still the same one that holds production data.
- This is the same family of issue as `F.Q-C-05` in the audit (migration FK mismatch) but in production rather than tests.

### What the next session needs to do, in order

1. **Don't deploy v250 again until this is fixed** — it will crash-loop and the rollback target may not be the same next time.
2. **Connect to RDS read-only** (e.g. `psql` from a developer machine, or `python manage.py dbshell` against `production_aws`) and inspect:
   - `SELECT name FROM django_migrations WHERE app = 'core' ORDER BY name;` — what's the latest applied migration?
   - `\dt core_*` — what tables actually exist?
   - Specifically: does `core_invoices` exist, does `core_bills` exist, both, neither?
   - Does `django_migrations` have a row for `core.0037_rename_invoice_to_bill`?
3. **Compare against `core/migrations/`** in the v250 tree (which is what's on `main`). Find the gap.
4. The most likely fix is one of:
   - `python manage.py migrate core --fake <appropriate_migration>` to align state, then redeploy. Do this from a one-off `eb ssh` shell, **not** baked into start.sh, so the user controls the timing.
   - Apply the table rename migration manually (`ALTER TABLE core_invoices RENAME TO core_bills;` etc.) and then `--fake` `0037`.
5. After RDS state is sane, run `eb deploy` to land v250 again.
6. **Don't take a backup with `dumpdata core` in start.sh** — it raises `Unable to serialize database: cursor "..." does not exist` on every start, which suggests a serialiser bug (possibly tied to the same model-vs-table mismatch).

### Other deploy-related notes for the next session

- The previous deploy attempts at 09:43, 10:05, 10:12 today were **config changes** (env-var rotations), not code deploys. So v250 was the first new code in production since Feb 7.
- The custom domain the user actually hits is **not** the EB CNAME (`dev-app-docker.eba-mkynfeyv.ap-southeast-2.elasticbeanstalk.com` returns 400 on the bare hostname). Find the real hostname in EB env config or Route 53 before health-checking with curl.
- `health_endpoint` in `core/views/main.py` is currently a 200-OK Django view that doesn't actually check the DB. After this incident, consider giving it a real systems check (`SELECT 1;` on the DB) so EB can detect crash loops.

---

## Where we are right now

We are mid-way through executing `BEST_PRACTICE_AUDIT.md`. Two big phases are done:

1. **The "if you only do 12 things" priority queue (P-1 … P-12)** — done in a previous session.
   - Includes secret rotation (`SECRET_KEY`, `EMAIL_API_SECRET_KEY` / Lambda `API_SECRET_KEY`, `RDS_PASSWORD`).
   - **`XERO_ENCRYPTION_KEY` was deliberately *not* rotated** — that's destructive and needs its own scheduled outage. See `docs/SECRET_ROTATION_RUNBOOK.md`.
2. **Section 3 critical findings** — done in the most recent session.
   - 14 critical items closed; 2 explicitly deferred (`G.X-C-06`, `F.Q-C-05`).

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
2. **Costing-rollup migration (P-5 / A.M-R-02)** — `core/services/costing_rollups.py` already has the primitives. Rewrite the rollup blocks in `core/views/contract_budget.py` and `core/views/hc_claims.py` to call them. **Pin the numbers with a test before/after.**
3. **Lower-impact `transaction.atomic` wraps** — `dashboard.create_category`, `dashboard.create_item`, `dashboard.send_po_email`'s pre-PDF block, `email_receiver.receive_email`, `main.upload_categories`, `main.upload_letterhead`, `staff_hours.create_holiday_calendar` / `update_holiday_calendar` / `save_allocation`. Mechanical wrap, ~20 minutes total. None of these are silent-money-bug paths.
4. **G.X-C-06 invoice→bill rename completion** — only do this in a dedicated PR. ~100 surfaces. The model class is `Bills`, fields are `bill_*`, but URL paths still say `/invoice/...`, JS still posts `invoice_id`. Cosmetic only — no live correctness bug.
5. **F.Q-C-05 migration squash** — also dedicated PR. Tests don't run on a fresh DB because migration `0037` did `RENAME COLUMN` against the existing `core_invoices` table; a fresh schema build can't resolve the FK. Decide between (a) rename tables to `core_bills`/`core_bill_allocations` with another `RENAME TABLE` migration, or (b) commit to `db_table='core_invoices'` and document.
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
