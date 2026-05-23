# Best-Practice Audit — Mason / dev_app

**Audit date:** 23 May 2026 · **Codebase version:** v249 · **Scope:** every Python module, template, static asset, migration, settings file, and deployment artifact in the repo.

This audit was prepared ahead of professional review. It is the union of seven parallel deep-dives across separate domains, deduplicated and re-ranked. Every finding includes a `path:line` reference so the reviewer can jump straight to the code.

---

## Table of contents

1. Executive summary
2. The "if you only do twelve things" priority queue
3. Critical findings (security, data integrity, broken)
4. High findings (significant duplication / drift / risk)
5. Medium findings (consistency / hygiene)
6. Low findings (polish)
7. Refactor opportunities, by area
8. Test-coverage gap map
9. Repo hygiene cleanup checklist

Per-domain detailed reports follow as appendices A–G.

---

## 0. Status (post-priority-queue + critical-clear)

The 12-thing priority queue (P-1…P-12) has been completed, including the
live secret rotation (`SECRET_KEY`, `EMAIL_API_SECRET_KEY` /
`API_SECRET_KEY` Lambda parity, and `RDS_PASSWORD`).

A second pass cleared the remaining Section-3 critical items:

| ID | Status |
|---|---|
| G.X-C-07 — public PO `is_admin` escalation | Fixed (`is_staff` gate in `core/views/pos.py`). |
| C.T-C-04 — phantom `xero_modals.html` include | Non-issue (was a stale comment, no live `{% include %}`). |
| A.M-C-10 / A.M-C-11 — HC claim draft & update project scoping | Both fixed in `construction/views/claims.py`; new claims stamp `project` FK and `update_hc_claim_data` derives project from costing items. |
| B.V-C-10 — global TLS verify off | Removed `ssl._create_default_https_context = ssl._create_unverified_context` from `construction/views/claims.py`. |
| B.V-C-11 — exception leakage to clients | Mechanical sweep across `core/views/*.py` and `construction/views/*.py`; `'message'/'error': str(e)` shapes replaced with action-only strings, full traces still logged. |
| A.M-C-09 — `approve_bill_direct` guard | Now accepts `STATUS_CREATED` *or* `STATUS_ALLOCATED` (P-4 had narrowed it incorrectly). |
| A.M-C-12 — HC `get_invoiced_amounts` allocation filter | Applies the canonical `bill_type IN (0,1) OR (bill_type=2 AND allocation_type=1)` filter. |
| A.M-C-02 — HC settled-for-claim semantics | Audit note baked into the model docstring; flagged as a deliberate business decision needed before changing the constant. |
| A.M-C-13 — Contract Budget snap matching by name | Aligned to HC's FK approach (`snap_item__item_id`) with project-scope guard. |
| D.F-C-06 — money formatter locale split | `formatNumber`/`formatMoney`/`formatCurrency` all on `en-AU`; `rates_table.html` switched from 10× `en-US` to `en-AU`. |
| B.V-C-09 — PO submit cross-project costing tampering | `Costing` lookup now scoped to the PO's project. |
| C.T-C-02 / D.F-C-01 — BS5 modal API on BS4 | Compatibility shim added in `dashboard_master.html`; promotes `data-bs-*` to `data-*` and provides `bootstrap.Modal` shape that wraps BS4's jQuery API. |
| B.V-C-12 — `transaction.atomic` in multi-table mutates | 7 highest-risk paths wrapped: `bills.upload_bill_allocations`, `quotes.commit_data`, `quotes.update_quote`, `bills_global.return_to_inbox`, `pos.approve_po_claim` (totals/status block), `hc_claims.create_hc_claim` / `delete_hc_claim` / `finalize_hc_claim`, `hc_variations.save_hc_variation`, `claims.post_direct_cost_data`. Lower-impact paths (`create_category`, `create_item`, `upload_categories`, `upload_letterhead`, `create_holiday_calendar`, `update_holiday_calendar`, `save_allocation`, `send_po_email`'s pre-PDF block) listed in the deferred bucket below. |
| D.F-C-05 — debug code in `utils.js` | `debugStickyHeader`, `verifyStickyHeader`, `debugFxBill`, `debugAllFxBills`, `debugFxOrange` removed; `[SearchableDropdown]` console.log removed; only legitimate `console.warn`s in `initSortableTable` remain. File shrank from 1632 → 1019 lines (-613). |

### Still deferred — needs dedicated work (do not bundle with anything else)

| ID | Why deferred | What it would take |
|---|---|---|
| **G.X-C-06** invoice→bill rename completion | Touches ~100+ URL kwargs, view function names, POST field names, JS variables, and template paths. Cosmetic, not a correctness bug — but high regression risk. | Scoped PR per surface (URLs, JS, templates, tests), with a single sweep of the user-facing endpoints behind a feature flag if needed. |
| **F.Q-C-05** migration FK mismatch | The 2026-02 invoice→bill rename used `RENAME COLUMN` over the existing `core_invoices`/`core_invoice_allocations` tables instead of `RenameModel`. Fresh test DBs build the schema from scratch and the FK on `core_invoice_allocations.bill_id → core_bills.bill_pk` doesn't resolve because the table is still called `core_invoices`. | Migration squash + `db_table` decision (either rename the underlying tables to `core_bills` / `core_bill_allocations` with another `RENAME TABLE` migration, or commit to keeping `db_table='core_invoices'` and document it). Either approach needs a full test-suite run on a fresh DB. |
| Lower-impact `transaction.atomic` paths (B.V-C-12 leftovers) | Listed above. None are silently producing wrong numbers; worst case is duplicate ordering on `Categories`/`Costing` after a partial create. | Mechanical wrap each of: `dashboard.create_category`, `dashboard.create_item`, `dashboard.send_po_email` (the pre-`transaction.atomic` block), `bills_global.bills.upload_bill` (now mostly fine), `email_receiver.receive_email`, `main.upload_categories`, `main.upload_letterhead`, `staff_hours.create_holiday_calendar` / `update_holiday_calendar` / `save_allocation`. |
| Full `@csrf_exempt` sweep | P-3 introduced `_helpers.py` decorators and migrated `projects.py`, `pos.py`, `email_receiver.py` as the pattern. ~180 endpoints still use bare `@csrf_exempt`. | Touch each file once, drop `@csrf_exempt` in favour of `@api_login_required`/`@api_public`, regression-test the matching JS calls. Best done while the file is open for some other reason. |
| Per-section JS extraction (P-9 / C.T-R-11) | The dashboard SPA still ships ~25k lines of inline JS via `{% include %}`. P-9 demonstrated the pattern in `dashboard.html` and trimmed the orphan static assets, but each section template still inlines its own scripts. | Per-section static `.js` extraction in priority order: `stocktake.html`, `staff_hours.html`, `bills_global.html`, `rates_table.html`, `hc_claims.html`, `contract_budget.html`. |
| Costing-rollup migration (P-5 / A.M-R-02) | `core/services/costing_rollups.py` exists with `committed`/`settled`/`invoiced` primitives. Contract Budget and HC Claims still implement their own loops. | Rewrite both views' rollup blocks to call the service, delete the duplicated Q-clauses, write tests pinning the numbers before and after. |

---

## 1. Executive summary

| Domain | Critical | High | Medium | Low | Refactor proposals |
|---|---:|---:|---:|---:|---:|
| A. Models, services, formulas | 13 | 16 | 22 | 10 | 10 |
| B. Views, URLs, auth, queries | 13 | 15 | 25 | 8 | 12 |
| C. Templates | 5 | 15 | 16 | 10 | 14 |
| D. JavaScript & CSS | 6 | 11 | 17 | 15 | 10 |
| E. Settings, security, deploy | 16 | 21 | 27 | 22 | 12 |
| F. Tests, dead code, migrations | 8 | 13 | 16 | 10 | 12 |
| G. Cross-cutting consistency | 7 | 12 | 17 | 10 | 12 |
| **Total** | **68** | **103** | **140** | **85** | **82** |

**Headline picture.** The app is feature-complete and shipping, but it has accumulated three categories of debt that a professional reviewer will flag immediately:

1. **Security & deploy hygiene is genuinely critical** — `SecurityMiddleware` is commented out, ~183 endpoints are `@csrf_exempt` with almost no `@login_required`, a public `wipe_database/` URL is wired in production, and committed scripts/docs leak the live RDS password and email API key. Rotating secrets and gating endpoints should happen before any further feature work.
2. **Business-logic duplication and formula drift** — at least three different "committed" calculations exist, "approved-bill" filters are copy-pasted as raw `Q(...)` clauses across views, GST is hard-coded as `* 0.1` in four templates/JS files, and the `Bills.STATUS_*` constants exist but are still used as magic numbers `[1,102]`/`[2,103]`/`[103,104]` everywhere except `pos.py`. Two of these (the bill status semantics and HC-claim "settled" set) are silently producing wrong numbers.
3. **Frontend monolith** — every dashboard hit ships ~25 000 lines of inline JS because all SPA sections are `{% include %}`'d up front. Three CSRF-token helpers, three money formatters, and two date formatters coexist; Bootstrap 4 is loaded but Bootstrap 5 modal APIs are called in three templates (silent failure).

**Numbers worth knowing.**

- 80 migrations on `core`; 0 on `construction`. `core/models.py` is 1 464 lines.
- 25 view modules in `core/views/`. Largest: `staff_hours.py` (2 787), `dashboard.py` (2 554), `stocktake.py` (2 331), `bills_global.py` (2 072).
- 29 templates under `core/templates/core/`. Largest: `stocktake.html` (3 485), `staff_hours.html` (3 270), `bills_global.html` (2 772). Three `DEPRECATED_*` templates totalling 2 340 lines are still present.
- ~900 `JsonResponse` call sites, ~200 of them inconsistent in error envelope shape; 9 `transaction.atomic` blocks in the entire codebase.
- 4 of the 5 `core/services/*.py` files are empty stubs.
- ~2 600 lines of dev/debug code in `utils.js` (sticky-header inspector, FX debug suite, ~135 `console.log` calls in static JS plus ~200 more in templates).
- Two missing templates referenced from live URLs: `bills_global_inbox.html`, `bills_global_direct.html`, `bills_global_approvals.html`, and `project_selector.html` (will 500 if hit).
- Two production-grade security holes: `core/views/database_wipe.py` is wired at `/core/wipe_database/` with no auth and `@csrf_exempt`; the same is true of `database_diagnostics.py`, `api_diagnostics.py`, `xero_diagnostics.py`.
- ~37 MB orphan static asset (`background.png`) shipped on every deploy with zero references.

---

## 2. The "if you only do twelve things" priority queue

These are the highest-leverage, cross-cutting actions. Each fixes findings from multiple domains at once, so the order is also the recommended sequence.

### P-1. Rotate the leaked secrets and stop committing them
- `set_eb_env_vars.sh:15` (`RDS_PASSWORD=DevApp2024SecurePass!`), `set_rds_env_vars.sh:18` (`RDS_PASSWORD=U1wPqDKuRZVZ6hwRrLkrpnNp`), `LOCAL_EMAIL_TESTING.md:28,61,91` (live `API_SECRET_KEY`).
- `dev_app/settings/base.py:25,28,31` and `dev_app/settings/production_aws.py:17` have insecure defaults for `SECRET_KEY`, `XERO_ENCRYPTION_KEY`, `EMAIL_API_SECRET_KEY` that production silently falls back to.
- Default superuser password `admin123` lives in `.ebextensions/04_docker_env.config:11-12` and `docker-compose.yml:27-29`.
- **Action:** rotate every credential listed above, remove the scripts from git history (`git filter-repo` or BFG), drop the in-code defaults, and require env vars at startup (fail fast). Move secret loading to `dev_app/aws_secrets.py` (already written, never wired). See E.S-C-01..09.

### P-2. Re-enable Django security middleware and gate the diagnostics endpoints
- `dev_app/settings/base.py:77,83` — `SecurityMiddleware` and `XFrameOptionsMiddleware` are commented out. HSTS / SSL redirect / clickjacking protection are all off.
- `core/views/database_wipe.py` is `@csrf_exempt`, has no auth, is wired at `core/urls.py:169`, and TRUNCATEs the database. `database_diagnostics.py`, `api_diagnostics.py`, `xero_diagnostics.py`, `staff_hours.py:2516-2519`, and `core/urls.py:88` (`update_fixed_on_site`) are all similarly exposed.
- **Action:** uncomment the middleware, move WhiteNoise to position 2, add `SECURE_HSTS_SECONDS` etc. in `production_aws.py`, move all diagnostics behind a `staff_member_required` decorator, and drop them from production `urlpatterns` entirely (load behind a `DEBUG`-or-`ENABLE_DIAGNOSTICS=1` flag). See E.S-H-01..03, B.V-C-01..04, E.S-C-10.

### P-3. Default-deny the JSON API
- ~183 `@csrf_exempt` views; ~50 use `@login_required` (almost all in `staff_hours.py` and `rates.py`); zero use `@staff_member_required` outside Django admin. Cookie-authenticated POSTs sit on top of disabled CSRF, which means a logged-in user clicking a malicious link can mutate finance data with no guard.
- Public PO endpoints in `dev_app/urls.py:14-18` are correctly gated by unique IDs but `submit_po_claim` accepts an arbitrary `pending_bill_pk` from POST.
- **Action:** introduce `core/views/_helpers.py` with `@api_login_required` (auth + CSRF-on, JSON-only) and `@api_public` (intentional, signed). Replace bare `@csrf_exempt` with one of those. Add a `LoginRequiredMiddleware` allowlist for the genuinely-public PO/email-webhook routes. See B.V-C-07..09, B.V-R-03.

### P-4. Make `Bills.STATUS_*` the single source of truth
- The constants exist (`core/models.py:793-805`) but ~90 % of usage is still raw `[1,102]`, `[2,103]`, `[103,104]`, etc. (`core/views/bills.py:533,651,895,1007`, `core/views/dashboard.py:386,420,2466,2492`, `core/views/bills_global.py:257,918,923,1174,1255`, plus templates).
- The dashboard docstring at `core/templates/core/dashboard.html:31,41` says archive is `bill_status=4`, but the backend archives to `-1` and `4` is `STATUS_PAID`. This is a live operator-facing wrong fact.
- `stocktake.html:911-915` defines a JS `BILL_STATUS = {PENDING:0, APPROVED:1, SENT:2}` that does not match the model.
- The Direct-to-Xero send sets `bill_status=2` even though sent-to-Xero is `STATUS_SENT_TO_XERO=3`; combined with `core/views/dashboard.py:2492`'s "ready to send" filter that does not exclude rows with `bill_xero_id`, the dashboard can advertise bills as ready-to-send that are already in Xero.
- **Action:** mechanical pass replacing every literal with `Bills.STATUS_*`; emit a JS constants file from Django; fix the Direct-Xero workflow to land on `STATUS_SENT_TO_XERO`; correct the dashboard docstring; add a regression test asserting the JS and Python sets match. See A.M-C-01, G.X-C-02..05, X-H-10.

### P-5. Unify the "committed" calculation
- Three incompatible implementations live in production: `core/formulas.py:5-47` (global, sums quote + filtered bill allocations), `core/views/contract_budget.py:230-546` (project-scoped, includes Internal `contract_budget` + Labour wages/super + direct bills + snaps), `core/views/hc_claims.py:709-818` (project-scoped, quotes + snaps only — no bills, no Internal, no Labour).
- The HC C2C formula then uses a "settled" set `{STATUS_APPROVED, STATUS_SENT_TO_XERO}` (`core/views/hc_claims.py:839-852`), which counts merely-approved bills as paid and suppresses HC claimable amounts.
- `formulas.Committed()` is imported in four modules and called by zero of them.
- **Action:** introduce `core/services/costing_rollups.py` with `committed(project, scope)`, `billed(project, scope)`, `working_budget(item)`. Migrate Contract Budget and HC Claims to it. Decide whether HC's "settled" set means approved+paid or paid+xero, codify as a constant, document the choice, write a test. See A.M-C-02, A.M-C-03, A.M-R-02, G.X-H-06.

### P-6. Centralise GST + money handling
- GST as `* 0.1` is hard-coded in `core/templates/core/stocktake.html:1430`, `bills_global.html:835,1769`, `core/static/core/js/allocations_layout.js:1765`, `core/static/core/js/project_type_config.js:404`. No Python helper exists.
- DecimalField columns are converted to `float()` before summing in `core/views/contract_budget.py:266-267`, `core/views/hc_claims.py:845`, `core/views/bills_global.py:1025-1033`, `core/views/pos.py:254-263`, `core/services/quotes.py:209-212`. Tolerances of `0.01` are used to compare floats — silent rounding-bug factory.
- Three different money formatters in JS (`Utils.formatNumber` is `en-US`, `Utils.formatMoney` is `en-AU`, `Utils.formatCurrency` mixes both); `core/templatetags/math_filters.py:16-18` mutates `locale.setlocale()` on every call (process-global state, race-prone, and the filter is never `{% load %}`'d anywhere).
- **Action:** add `core/formulas.gst_from_net()` and `core/formulas.gross_from_net()`; `core/utils/money.py` with `to_decimal`, `sum_decimals`; one `core/static/core/js/money.js` exporting `formatAUD`/`parseAUD`. Delete the locale-mutating filter and the duplicate JS formatters. See A.M-H-05..06, D.F-C-06, D.F-R-02, G.X-H-03.

### P-7. Fix the field-rename and import bombs
There are several places where a runtime error is one click away because old field/PK names survived a model rename:

- `core/views/bills.py:157-158`, `construction/views/claims.py:380-386,441` create `Bill_allocations(bill_pk=invoice, ...)` — the FK is `bill`, so this is a `TypeError` on first call. Same code path also exists in `construction/views/claims.py`.
- `core/views/bills.py:339,376`, `construction/views/claims.py:388` access `bill_allocations_pk`; the model PK is `bill_allocation_pk` — `AttributeError`.
- `core/services/quotes.py:67,206-207` filters/accesses `Contacts.contact_name`; the field is `name` (renamed in migration `0005`). `get_committed_quotes_list` will `FieldError` on call.
- `core/views/main.py:74` constructs `Contacts(contact_name=..., contact_email=...)` — those fields no longer exist.
- `core/views/bills.py:119-130` passes `invoice_division=invoice_division` to `Bills()`; the field was removed in favour of `project` FK.
- `core/tests/test_quote_service.py:50-66` creates `Contacts(contact_name=..., checked=True)` — fixtures are stale, tests do not run.
- **Action:** mechanical sweep with `rg "bill_pk\b|bill_allocations_pk|contact_name\b|contact_email\b|invoice_division\b"` and a regression smoke-test for each affected endpoint. See A.M-C-04..08, F.Q-C-04.

### P-8. Restore or remove the broken Bills/Project-Selector templates
- `core/views/bills_global.py:152,189,230` render `core/bills_global_inbox.html`, `core/bills_global_direct.html`, `core/bills_global_approvals.html`. Only `DEPRECATED_*` versions exist — these routes 500.
- `core/views/bills.py:850,853` falls back to `core/bills_global_approvals.html` — same.
- `core/views/project_type.py:129` renders `core/project_selector.html` — the file does not exist anywhere in the repo.
- The three `DEPRECATED_bills_global_*.html` files (≈ 2 340 lines combined) have zero `{% include %}` references.
- **Action:** decide route by route whether to redirect to the consolidated `bills_global.html`, restore a thin shim, or remove the URL entirely. Then delete the DEPRECATED files and the `bills_global_inbox/direct/approvals` URL entries at `core/urls.py:197-199`. See C.T-C-01, C.T-C-03, F.Q-C-01..02, F.Q-M-06.

### P-9. Slim the dashboard SPA bundle
- `core/templates/core/dashboard.html:521-545` `{% include %}`s 10+ section templates on every dashboard hit. Combined inline JS in those sections totals roughly 25 000 lines (`stocktake.html` ~2 586, `staff_hours.html` ~2 279, `rates_table.html` ~2 210, `bills_global.html` ~2 438, `hc_claims.html` ~1 893, `contract_budget.html` ~1 632, `documents.html` ~1 452 + 11 more). Combined inline CSS is similar.
- 1.2 MB `mason_logo.png`, 1.5 MB `mason_steampunk.mp4`, 37 MB `background.png` (orphan) ship via `collectstatic` every deploy.
- WhiteNoise serves raw, unminified, unhashed; `package.json` is Playwright-only; no build step.
- **Action:** lazy-load section HTML/JS on first nav click; extract per-section static JS files (top priority: stocktake, staff_hours, bills_global, rates_table); delete `core/static/core/media/background.png` and `mason_steampunk.mp4`; convert the logo to WebP/SVG; turn on `ManifestStaticFilesStorage`. See C.T-H-01, C.T-R-11, D.F-C-04, D.F-C-05, D.F-H-10, D.F-H-11.

### P-10. One HTTP client, one CSRF helper, one error envelope
- Five CSRF-token cookie parsers exist (`utils.js:28-41` is canonical, plus duplicates in `dashboard_master.html:39-51`, `rates.html:183`, `documents.html:1772`, `components/rates_table.html:942`).
- 148 `$.ajax` call sites vs 23 `fetch` call sites across templates — no shared wrapper. The closest thing, `staffHoursApi()` in `staff_hours.html:872-885`, has no `response.ok` check, no 401 redirect, and returns the JSON body even on HTTP error.
- Three JSON error envelope shapes coexist: `{status, message}` in `dashboard.py`, `{error}` in `hc_claims.py`, `{success, error}` in `construction/views/claims.py`. Frontend has to branch on all three (`staff_hours.html:863-868` checks both `message` and `error`).
- **Action:** add `core/static/core/js/api.js` (`Utils.api(url, opts)` with CSRF, JSON parse, 401 redirect, structured errors). Add `core/views/_helpers.py` with `json_ok()` / `json_err()` and `@api_view`. Mass-rename the duplicates. See B.V-H-01, D.F-C-02, D.F-H-01..03, D.F-R-01, G.X-H-07..08.

### P-11. Make the data layer enforce its own filters
- The "approved-bill committed" Q-clause `Q(bill__bill_type__in=[0,1]) | (Q(bill__bill_type=2) & Q(allocation_type=1))` is duplicated verbatim in `core/formulas.py:13-15` and in views.
- "Active project" is variously `archived=False`, `exclude(archived=1)`, or unfiltered (`core/views/dashboard.py:2434-2507`, `core/views/bills_global.py:1416`, `core/views/bills.py:532-533`).
- "Pending claim" / "PO with status >= 102" are repeated across views.
- N+1 patterns in `core/views/contract_budget.py:336-348` (`EmployeePayRate.objects.filter(...).first()` per row plus `get_employee_super_rate()` per row, hitting the live Xero Payroll API in a loop) and in `core/middleware.py:80-82` (`Projects.objects.all()` plus `.count()` on every request if the `ProjectTypeMiddleware` is ever enabled).
- **Action:** custom QuerySets/Managers — `Bills.objects.committed_lines()`, `Projects.objects.active()`, `Po_orders.objects.live()`. Replace the literal Q's. Batch the pay-rate / super-rate lookups. See A.M-H-02, B.V-H-02..03, B.V-R-02, B.V-R-12, G.X-H-05.

### P-12. Repo & deploy bundle hygiene
- `.venv/` is tracked (9 095 files). `certifi/`, `charset_normalizer/`, `idna/`, `requests/`, `urllib3/` and matching `*-dist-info/` directories are vendored at the repo root and confused with packages. `db.sqlite3` and `db_test.sqlite3` are tracked despite `.gitignore`. `lambda-*.zip`, `logs.zip`, `get-pip.py` (2.6 MB), `eb_logs.txt`, `xero_instances_export.json` (sensitive), `playwright-report/`, `test-results/` are committed or shipped.
- `DEPLOYMENT.txt:34` zip command does not exclude any of the above. They go to S3 every deploy.
- `Procfile`, `Aptfile`, `runtime.txt` are Heroku-era leftovers. `dev_app/settings/production.py` (S3 static) coexists with `production_aws.py` (local static) and `README.md:7` says Django 4.x while live is 5.0.6.
- **Action:** `git rm -r --cached` the junk; expand `.gitignore` and `.dockerignore`; update the deploy zip excludes; delete the orphan settings and Heroku files; consolidate ~25 root-level `.md`/`.txt` notes into a `docs/` tree. See E.S-C-12..16, E.S-M-19..23, E.S-R-06.

---

## 3. Critical findings (consolidated)

> Each row links back to the per-domain appendix where the finding has full description and recommendation. Rows are clustered by theme.

### Theme: secrets, keys, credentials in source

| ID | One-line | Where |
|---|---|---|
| E.S-C-01 | Hardcoded `SECRET_KEY` fallback | `dev_app/settings/base.py:25` |
| E.S-C-02 | Same insecure `SECRET_KEY` reachable in production | `dev_app/settings/production_aws.py:17` |
| E.S-C-03 | Hardcoded `XERO_ENCRYPTION_KEY` Fernet key | `dev_app/settings/base.py:28` |
| E.S-C-04 | Weak default `EMAIL_API_SECRET_KEY` (and Lambda uses different env name) | `dev_app/settings/base.py:31` |
| E.S-C-05 | Production RDS password committed | `set_eb_env_vars.sh:15` |
| E.S-C-06 | A second production RDS password committed | `set_rds_env_vars.sh:18` |
| E.S-C-07 | Live email API secret in committed docs | `LOCAL_EMAIL_TESTING.md:28,61,91` |
| E.S-C-08 | Default superuser password `admin123` baked into EB env file | `.ebextensions/04_docker_env.config:11-12` |
| E.S-C-09 | Default superuser password in Docker compose | `docker-compose.yml:27-29` |
| E.S-C-15 | `xero_instances_export.json` contains OAuth tokens; not in deploy-zip excludes | repo root |

### Theme: production endpoints with no auth

| ID | One-line | Where |
|---|---|---|
| B.V-C-01 / E.S-C-10 | `wipe_database` is `@csrf_exempt`, no auth, TRUNCATEs every business table | `core/views/database_wipe.py:17-120`, route at `core/urls.py:169` |
| B.V-C-02 | `database_diagnostics` exposes engine/host/user/version | `core/views/database_diagnostics.py:9-56` |
| B.V-C-03 | `api_diagnostics` exposes secret-key matching | `core/views/api_diagnostics.py:9-27` |
| B.V-C-04 | `xero_diagnostics` exposes Xero `client_id` + auth URL | `core/views/xero_diagnostics.py:9-50` |
| E.S-C-11 / B.V-C-08 | ~183 `@csrf_exempt` JSON endpoints with ~50 `@login_required` total; no `@staff_member_required` outside Django admin | repo-wide |
| B.V-C-09 | Public PO claim submit accepts arbitrary `pending_bill_pk` | `core/views/pos.py:599-662`, `dev_app/urls.py:16-17` |
| B.V-C-10 | TLS verification globally disabled in claims module | `construction/views/claims.py:60` |

### Theme: security headers / framework defenses disabled

| ID | One-line | Where |
|---|---|---|
| E.S-H-01 / B.V-C-05 | `SecurityMiddleware` commented out; HSTS, SSL redirect, headers all disabled | `dev_app/settings/base.py:77` |
| E.S-H-02 / B.V-C-13 | `XFrameOptionsMiddleware` commented out though `X_FRAME_OPTIONS = 'SAMEORIGIN'` is set | `dev_app/settings/base.py:83-87` |
| B.V-C-06 | Hardcoded `SECRET_KEY`/`XERO_ENCRYPTION_KEY`/`EMAIL_API_SECRET_KEY` defaults reachable in production | `dev_app/settings/base.py:25-31` |
| B.V-C-07 | Cookie-auth POSTs sit on top of `@csrf_exempt` repo-wide | repo-wide |

### Theme: data integrity / silent wrong numbers

| ID | One-line | Where |
|---|---|---|
| A.M-C-01 / G.X-C-02 | `Bills.STATUS_*` constants exist but are not used (~90% magic numbers) | `core/models.py:793-805` + many call sites |
| G.X-C-04 | Stocktake JS `BILL_STATUS` enum does not match model | `core/templates/core/stocktake.html:911-915` |
| G.X-C-05 | Dashboard docstring says archive=`bill_status=4`; backend archives to `-1`; `4` is `STATUS_PAID` | `core/templates/core/dashboard.html:31,41` vs `core/views/bills_global.py:1287-1310` |
| A.M-C-02 | HC "settled-for-claim" set includes merely-approved bills, suppressing claimable amounts | `core/models.py:806-812`, `core/views/hc_claims.py:839-852` |
| A.M-C-03 | Three incompatible "committed" implementations | `core/formulas.py:5-47`, `core/views/contract_budget.py:230-546`, `core/views/hc_claims.py:709-818` |
| A.M-C-09 | `approve_bill_direct` skips the allocated state and uses wrong guard | `core/views/bills_global.py:249-257` |
| A.M-C-12 | HC `get_invoiced_amounts` lacks the progress-claim allocation filter the formulas module uses | `core/views/hc_claims.py:835-855` |
| A.M-C-13 | Contract budget snap→costing matched by string name, HC claims by FK | `core/views/contract_budget.py:400-408` vs `core/views/hc_claims.py:734-741` |
| A.M-C-04 | `Bill_allocations` created with wrong FK kwarg `bill_pk=` (TypeError on first call) | `core/views/bills.py:157-158`, `construction/views/claims.py:380-386,441` |
| A.M-C-05 | `upload_bill` references removed field `invoice_division` | `core/views/bills.py:119-130` |
| A.M-C-06 | Quotes service references removed field `Contacts.contact_name` | `core/services/quotes.py:67,206-207` |
| A.M-C-07 | `main.create_contacts` constructs `Contacts(contact_name=..., contact_email=...)` (removed fields) | `core/views/main.py:74` |
| A.M-C-08 | Wrong PK attribute `bill_allocations_pk` (model is `bill_allocation_pk`) | `core/views/bills.py:339,376`, `construction/views/claims.py:388` |
| A.M-C-10 | HC claim draft creation in construction path omits `project` FK | `construction/views/claims.py:88-89` |
| A.M-C-11 | `update_hc_claim_data` resolves draft globally (race-prone across projects) | `construction/views/claims.py:122` |
| B.V-C-12 | Multi-table mutations without `transaction.atomic` (only 9 `atomic` blocks repo-wide) | `core/views/bills.py:157-167`, `construction/views/claims.py:88-90` |
| B.V-C-11 | Exception messages and tracebacks returned to clients | `core/views/pos.py:596`, `core/views/rates.py:143-147` |

### Theme: live URLs with broken templates

| ID | One-line | Where |
|---|---|---|
| C.T-C-01 / G.X-C-01 / F.Q-C-01 | Three Bills templates referenced from live views do not exist; only `DEPRECATED_*` versions remain | `core/views/bills_global.py:152,189,230`, `core/views/bills.py:850,853` |
| C.T-C-03 / F.Q-C-02 | `project_selector.html` rendered by `core/views/project_type.py:129` does not exist | repo-wide |
| C.T-C-02 / D.F-C-01 | Bootstrap 4 loaded but Bootstrap 5 modal API used in `bills_global.html`, `staff_hours.html`, `stocktake.html` (silent modal failures) | `core/templates/core/dashboard_master.html:10-25` vs `bills_global.html:1983-2041` |
| C.T-C-04 | Phantom include `{% include 'core/xero_modals.html' %}` — file does not exist | `core/templates/core/dashboard.html:24` |
| C.T-C-05 | `math_filters.numberformat` mutates `locale.setlocale()` per call (process-global, race-prone) and is unused | `core/templatetags/math_filters.py:16-18` |

### Theme: repo / deploy bundle hygiene

| ID | One-line | Where |
|---|---|---|
| E.S-C-12 / F.Q-C-06 | Production SQLite DB tracked in git despite `.gitignore` | `db.sqlite3` |
| E.S-C-13 | `.venv/` tracked (9 095 files) | `.venv/` |
| E.S-C-14 | Vendored `certifi/`, `charset_normalizer/`, `idna/`, `requests/`, `urllib3/` at repo root | repo root |
| E.S-C-16 | Deploy zip ships large lambda zips and `xero_instances_export.json` | repo root + `DEPLOYMENT.txt:34` |
| F.Q-C-05 | Fresh test DB migration fails (FK mismatch on `core_invoice_allocations` → `core_invoices`) | `core/migrations/0037_*`, `0047_*` |
| F.Q-C-07 | Dual `core/tests.py` + `core/tests/` package (the file is shadowed) | `core/tests.py` |
| F.Q-C-08 | `/wipe_database/` exposed (also S-C-10 / V-C-01) | `core/urls.py:169` |
| D.F-C-04 | 37 MB orphan static asset shipped on every deploy | `core/static/core/media/background.png` |

### Theme: production code quality

| ID | One-line | Where |
|---|---|---|
| D.F-C-02 | No unified HTTP client; ~150+ call sites hand-roll fetch/$.ajax with inconsistent error/401 handling | repo-wide |
| D.F-C-05 | ~2 600 lines of debug/dev code shipped in `utils.js` | `core/static/core/js/utils.js:824-1151,1214-1509` |
| D.F-C-06 | `Utils.formatNumber` uses `en-US`, `Utils.formatMoney` uses `en-AU`, `Utils.formatCurrency` mixes them | `core/static/core/js/utils.js:50-92` |
| G.X-C-06 | Invoice→Bill rename incomplete across URL kwargs, view names, POST fields, paths | repo-wide (~100+ `invoice` mentions) |
| G.X-C-07 | `is_admin` is set from `request.user.is_authenticated` on the public PO page (any logged-in user gets admin UI) | `core/views/pos.py:314`, `core/templates/core/po_public.html:718` |

---

## 4. High findings (top recurring patterns)

The full list is in the appendices; what follows are the patterns that appear in *several* domain audits independently. Treat these as the next tier of cleanup after the twelve-thing queue.

### 4.1 Duplication that should collapse to a helper

| Cluster | Where it appears | Proposed home |
|---|---|---|
| JSON response builder boilerplate (~900 sites, three envelope shapes) | every view module; local helpers duplicated in `dashboard.py:67-77` and `contacts.py:29-36` | `core/views/_helpers.py:json_ok/json_err` (B.V-H-01, G.X-H-07..08) |
| CSRF token cookie parser | `utils.js:28-41` canonical + 4 inline duplicates | only `Utils.getCSRFToken` (D.F-H-01) |
| GST `* 0.1` in client | 4 templates / static JS files | `core/formulas.gst_from_net` + `money.js` (A.M-H-06, G.X-H-03) |
| Money formatter | 3 JS variants + 6 inline `toFixed(2)` overrides + Django `floatformat:2` | `Utils.formatAUD` only (D.F-M-01) |
| Date formatter | 6 reimplementations of `formatDateDMY` | `Utils.formatDateDMY` (D.F-M-02) |
| Email send / PDF gen | 5+ modules each rebuild `EmailMultiAlternatives`/PDF pipelines | `core/services/email.py`, `core/services/pdf.py` (B.V-H-08, B.V-H-09) |
| Date-param parsing (`strptime '%Y-%m-%d'`) | 25+ sites | `parse_api_date()` helper (B.V-M-07, B.V-R-06) |
| CSV upload/parsing | `main.py`, `contract_budget.py`, `claims.py` | `core/services/csv_io.py` (B.V-M-20) |
| Approved-bill committed `Q(...)` | duplicated literally in `core/formulas.py:13-15` and twice within the same function, plus implicit duplication in views | `Bill_allocations` queryset manager (A.M-H-02, B.V-H-02) |
| Active-project filter | three different shapes across views | `Projects.objects.active()` (B.V-H-12, B.V-R-12) |
| Allocation row builders / "Still to allocate" sums | server validation in `bills.py:1255+` plus client recomputation in `allocations_layout.js:899+` | `core/allocations/totals.py` + JS bound to it (G.X-H-05) |
| Status-badge HTML | repeated in JS strings across `contacts.html`, `settings.html`, `bills_global.html`, `stocktake.html`, `po_public.html` | `_status_badge.html` partial / `Utils.renderBadge()` (C.T-R-03) |
| Modal markup | PDF confirm modal duplicated in 3+ files; folder-prompt modal duplicated in documents | `_pdf_confirm_modal.html`, `_prompt_modal.html` (C.T-R-02, C.T-R-10) |
| `bills_global` Inbox/Direct/Approvals JS | the same row builders, GST auto-calc, dropdowns, footers exist three times in `bills_global.html` | one config-driven `_bills_section.js` (C.T-H-02, C.T-R-01) |

### 4.2 Inconsistencies the reviewer will flag immediately

- **Naming.** `Po_orders`, `Bill_allocations`, `Quote_allocations`, `HC_claims` etc. mix Pascal_Snake with PEP 8 PascalCase neighbours (`Bills`, `Projects`, `Contacts`, `Costing`). `Po_orders` is the singular row model. (G.X-M-01)
- **`*_pk` field names.** `bill_pk`, `costing_pk`, `quote_pk`, `po_order_pk`, `contact_pk` are manually-named PKs/FKs where Django would have generated `*_id`. Document the convention or rename. (A.M-M-04..05)
- **`archived` is `IntegerField(0/1)` not `BooleanField`** on `Projects`, `ProjectTypes`, etc. (A.M-M-06)
- **JSON error envelope shape** is `{status, message}` vs `{error}` vs `{success, error}`. The frontend has to branch on all three. (G.X-H-07)
- **Hardcoded URL paths.** ~130+ `/core/...` strings in templates and JS where `{% url %}` should be used (`core/templates/core/hc_claims.html:857,895,1257`, `contract_budget.html:489-491`, `documents.html`, `xero.html`, etc.). (C.T-H-09)
- **URL kwarg naming.** `<int:project_pk>` vs `projects_pk` field lookups vs bare `pk` in some routes. (B.V-M-04)
- **`is_authenticated` ad-hoc checks** vs `@login_required` decorators. (B.V-H-13)
- **`@csrf_exempt + @login_required`** on the same view in `rates.py` (CSRF disabled even for cookie-authenticated browser sessions). (B.V-H-14)
- **`AllocationsManager` adopted unevenly** — some screens use `core/static/core/js/allocations_layout.js`, others reimplement allocation rendering inline. (C.T-H-04)
- **Logger setup**: most modules use `logger = logging.getLogger(__name__)`, but `core/views/pos.py:48` calls `logger.setLevel(logging.INFO)` at import time and `construction/views/claims.py:63` does the same — process-wide level mutation. (B.V-L-02, G.X-L-01)
- **Project-type rules** are duplicated as Python (`core/utils/project_type.py`, `ProjectTypes.rates_based`) and JS (`core/static/core/js/project_type_config.js:38-41` hardcodes `construction|pods|precast`). New project types created via Settings will silently get the JS default. (D.F-H-05, G.X-M-05)
- **`bills_project_buttons.html`** referenced in original scope does not exist; only `bills_global_buttons.html` (312 lines). (C.T-L-04)

### 4.3 Performance / N+1 hotspots

- `core/views/contract_budget.py:336-348` — inner loop calls `EmployeePayRate.objects.filter(...).first()` per allocation, plus `get_employee_super_rate()` per allocation (Xero Payroll API HTTPS call inside the loop). (A.M-H-04, B.V-H-03)
- `core/middleware.py:80-82` — `Projects.objects.all()` + `.count()` on every request when session lacks `project_pk` (only safe because the middleware is never registered, see below).
- Repeated `XeroInstances.objects.all()` in `dashboard.py:101`, `bills_global.py:1414,1654`, `staff_hours.py:39`, `xero.py:211,544` — no caching. (B.V-M-24)
- No pagination on big-table screens (bills, projects, staff hours, stocktake snaps) — all loaded full via AJAX. (G.X-H-12)
- Python-side aggregation that should be SQL — `core/formulas.py:37-45`, `core/views/contract_budget.py:460-463`. (B.V-H-15)

### 4.4 Dead / orphan code

- `ProjectTypeMiddleware` (`core/middleware.py:10-84`) and the matching context processors (`:87-134`) are defined but not registered in `dev_app/settings/base.py`. Pure dead code today. (B.V-H-04)
- `formulas.Committed()` is imported in `bills.py:86`, `main.py:55`, `documents.py:57`, `construction/views/claims.py:56` and **called by zero of them**. (A.M-H-01)
- 4 of the 5 `core/services/*.py` files are empty docstring stubs (`documents.py`, `order_book.py`, `suppliers.py`, `variations.py`). (A.M-H-14)
- `construction/models.py` is empty (3 lines); construction is a view/template namespace only. (A.M-H-15)
- `core/templatetags/json_filters.py`, `math_filters.py` — no template `{% load %}`s either. (F.Q-H-05)
- `get_template_for_project_type` is exported from `core/utils/__init__.py:10` but never imported. (F.Q-H-04)
- `debug_settings` view is defined but unwired. (B.V-M-12, F.Q-H-06)
- `alphanumeric_sort_key` re-exported from `core/views/__init__.py:60`, never called. (B.V-L-03, F.Q-H-07)
- Three `DEPRECATED_bills_global_*.html` files (~2 340 lines combined) — no `{% include %}` references. (C.T-H-03, F.Q-M-06)
- `components/data_table.html` (commented out in `dashboard.html:541`) and `components/reusable_form.html` (52-line CSS-only stub) — abandoned partial-abstractions. (C.T-H-14)
- Legacy `production.py` settings file still present; `Procfile`, `Aptfile`, `runtime.txt` are Heroku-era leftovers. (E.S-H-17, E.S-M-22)
- Top-level scratch: `db_test.py`, `check_imports.py`, `check_package_sizes.py`, `get-pip.py`, `lambda-*.zip`, `logs.zip`, `eb_logs.txt`. (F.Q-R-11, E.S-L-06..13)
- Commented-out URL routes in `core/urls.py:89,114-115,391-392`. (F.Q-M-11)

---

## 5. Medium / Low findings

The full list is in the appendices. The pattern at this tier is **lots of small, easy fixes that won't move the needle individually but together signal "this codebase has not had a tidy-up pass":**

- inline `<style>` blocks per template re-implementing `.reusable-table` rules (C.T-M-01, C.T-H-12, C.T-M-15);
- 200+ `console.log` calls in templates plus 135 in static JS (D.F-M-05);
- 50+ `alert()` for UX feedback (C.T-M-12);
- Z-index arms race up to `1050000` (D.F-H-07);
- `!important` flags scattered (`projects.html:47`, `staff_hours.html:17`) (D.F-H-09);
- print()s in `core/views/rates.py:449-484` (B.V-M-22, F.Q-M-08);
- `SECURE_PROXY_SSL_HEADER` set but no HSTS, `SESSION_COOKIE_SECURE` not always on (E.S-H-13);
- ~25 `.md`/`.txt` notes at the repo root, several contradicting each other (E.S-L-15..21, F.Q-L-08);
- README claims Django 4.x; live is 5.0.6 (F.Q-L-07);
- `LANGUAGE_CODE='en-us'`, `TIME_ZONE='UTC'`; AU app with hardcoded 1-Jul-25 FY in JS (G.X-H-11, G.X-M-16, A.M-M-13);
- `SUPERUSER_PASSWORD` overwrites admin password every deploy if env is set (E.S-H-10).

---

## 6. Refactor opportunities, by area

These are the named, scoped, achievable refactors the reviewer will most want to see executed.

### 6.1 Backend — models, services, formulas

| ID | Refactor | Lift |
|---|---|---|
| A.M-R-01 | Centralise the `Bills` status state machine into `core/services/bills.py:BillWorkflow.transition()`; views call events only | L |
| A.M-R-02 | Unified `core/services/costing_rollups.py` with `committed/billed/working_budget` consumed by Contract Budget *and* HC Claims | L |
| A.M-R-03 | `Bill_allocations.QuerySet.committed_lines()` etc. replacing literal `Q(...)` | S |
| A.M-R-04 | `core/formulas.gst_from_net()` + JS counterpart | S |
| A.M-R-05 | `core/utils/money.py` with `to_decimal`, `sum_decimals`, JSON-encoder helper | M |
| A.M-R-06 | `core/services/staff_cost.py` batching pay-rate / super-rate lookups | M |
| A.M-R-07 | Wire `core/validators.py` into `Contacts.clean()` and admin `ModelForm` | S |
| A.M-R-08 | Mechanical sweep fixing legacy field names (`bill_pk=`, `bill_allocations_pk`, `contact_name`, `contact_email`, `invoice_division`) | S |
| A.M-R-09 | HC claim project-scoping via `HC_claims.objects.draft_for_project(project)` | M |
| A.M-R-10 | Populate or delete the four empty `core/services/*` stubs | S each |

### 6.2 Backend — views, URLs, auth, queries

| ID | Refactor | Lift |
|---|---|---|
| B.V-R-01 | `core/views/_helpers.py:json_ok/json_err` + `@api_view` | M |
| B.V-R-02 | `BillQuerySet` workflow filters + `Bill_allocations.committed()` | M |
| B.V-R-03 | `@staff_api` decorator combining auth + CSRF + JSON | S |
| B.V-R-04 | `core/services/email.py` — shared mail builder | M |
| B.V-R-05 | `core/services/pdf.py` — shared HTML→PDF, merge, stamp | L |
| B.V-R-06 | `parse_api_date()` helper, ~25 strptime sites | S |
| B.V-R-07 | Wire-or-delete `ProjectTypeMiddleware` + matching context processor | S |
| B.V-R-08 | `core/urls_diagnostics.py` included only behind `DEBUG`/`ENABLE_DIAGNOSTICS=1` | S |
| B.V-R-09 | Wrap multi-table bill workflows in `transaction.atomic` service functions | M |
| B.V-R-10 | Slim `core/views/__init__.py` to URL-facing symbols only | S |
| B.V-R-11 | Consolidate public PO routes under `core/urls/public.py` | S |
| B.V-R-12 | `Projects.objects.active()` manager | S |

### 6.3 Templates

| ID | Refactor | Lift |
|---|---|---|
| C.T-R-01 | `_bills_section.js` config-driven Inbox/Direct/Approvals replacing the 2 400-line triplicate in `bills_global.html` | L |
| C.T-R-02 | `_pdf_confirm_modal.html` partial | S |
| C.T-R-03 | `_status_badge.html` + optional template tag | M |
| C.T-R-04 | `_mode_toggle.html` (Pending/Approved, Pending/Sent) | M |
| C.T-R-05 | `_money` filter + JS `Utils.formatAUD` parity | M |
| C.T-R-06 | `_contact_form_modal.html` — single source of truth for verify/add supplier | M |
| C.T-R-07 | `_document_list_section.html` — quotes/PO/variations/claims share one skeleton | L |
| C.T-R-08 | `_data_table_theme.css` with `[data-section=...]` scoping replacing per-template overrides | M |
| C.T-R-09 | `_project_workspace_shell.html` — tender/construction nav | M |
| C.T-R-10 | `_prompt_modal.html` — generic single-field modal | S |
| C.T-R-11 | Per-section static JS extraction, priority: stocktake → staff_hours → bills_global → rates_table → hc_claims → contract_budget | L |
| C.T-R-12 | `TableSelection.bind()` replacing 10+ ad-hoc click handlers | S |
| C.T-R-13 | `_api_urls.html` — Django→JS URL map; eliminate ~130 hardcoded paths | M |
| C.T-R-14 | Delete DEPRECATED + dead components after route fixup | S |

### 6.4 Frontend — JS / CSS

| ID | Refactor | Lift |
|---|---|---|
| D.F-R-01 | `Utils.api()` unified HTTP client | M |
| D.F-R-02 | `money.js` — one currency pipeline | S |
| D.F-R-03 | `dates.js` — one date pipeline | S |
| D.F-R-04 | Split `utils.js` into themed modules + strip debug | M |
| D.F-R-05 | Decompose `allocations_layout.js` into `state/data/dom/index` | L |
| D.F-R-06 | Server-driven project-type column config (eliminate JS duplication) | M |
| D.F-R-07 | CSS tokens `:root { --z-*, --space-*, --status-* }` | M |
| D.F-R-08 | Unify `.btn` system on `.rt-btn` | M |
| D.F-R-09 | Static asset hygiene + build pipeline (`ManifestStaticFilesStorage`) | M |
| D.F-R-10 | Bootstrap version alignment (4 → 5 or revert BS5 modal usage) | L |

### 6.5 Settings / security / deploy

| ID | Refactor | Lift |
|---|---|---|
| E.S-R-01 | Rotate every leaked secret + scrub git history | L |
| E.S-R-02 | Settings secrets pattern via `aws_secrets.py` / SSM with fail-fast on missing | M |
| E.S-R-03 | Re-enable `SecurityMiddleware` + `XFrameOptionsMiddleware` + HSTS | M |
| E.S-R-04 | Default-deny via `LoginRequiredMiddleware` + explicit allowlist | L |
| E.S-R-05 | Remove or staff-gate destructive/diagnostic endpoints | M |
| E.S-R-06 | Purge repo junk + fix `.gitignore` / `.dockerignore` / deploy zip excludes | M |
| E.S-R-07 | Harden EB/Docker boot: fail on migrate/collectstatic error, drop `admin123`, non-root user, real `/health/` route | M |
| E.S-R-08 | Unify Lambda email pipeline (single source, single env-var name) | M |
| E.S-R-09 | Delete `production.py` + Heroku files; document one `production_aws.py` path | S |
| E.S-R-10 | Split `requirements.txt` (prod) + `requirements-dev.txt` + multi-stage Docker | S |
| E.S-R-11 | Add Sentry / structured JSON logging | M |
| E.S-R-12 | Consolidate ~25 root docs into `docs/` | S |

### 6.6 Tests / dead code / migrations

| ID | Refactor | Lift |
|---|---|---|
| F.Q-R-01 | Restore or remove broken Bills templates (and the URLs that reach them) | M |
| F.Q-R-02 | Repair quotes service + tests | S |
| F.Q-R-03 | Consolidate test layout (`core/tests.py` + `construction/tests.py` removal) | S |
| F.Q-R-04 | Un-track `db.sqlite3` and `db_test.sqlite3` | S |
| F.Q-R-05 | Align Playwright docs and npm scripts with what actually exists | M |
| F.Q-R-06 | Migration squash + FK hygiene (`core_invoices` table-name drift) | L |
| F.Q-R-07 | Decide stub services: implement or delete (and update `MODEL_SERVICE_MAPPING.md`) | M |
| F.Q-R-08 | Harden/remove `wipe_database`, `send_test_email` | S |
| F.Q-R-09 | CI gate: migrate-test + Django test + Playwright | M |
| F.Q-R-10 | Documentation consolidation under `docs/` | M |
| F.Q-R-11 | Root scratch file cleanup | S |
| F.Q-R-12 | Remove debug `print()` from hot paths | S |

### 6.7 Cross-cutting centralisation proposals

| ID | Proposal | Lift |
|---|---|---|
| G.X-R-01 | Single source of truth for `Bills.bill_status` (Python + emitted JS enum) | M |
| G.X-R-02 | Namespaced status enums per model to prevent cross-domain integer collisions | M |
| G.X-R-03 | Single GST helper (Python + JS twin) | S |
| G.X-R-04 | Bill terminology completion (URL kwargs / functions / POST fields) | L |
| G.X-R-05 | JSON response envelope unification | M |
| G.X-R-06 | Shared `error_response` / context helpers, including `today` and `current_user` | S |
| G.X-R-07 | Project-type / rates-based config exposed as JSON from backend | M |
| G.X-R-08 | Financial-year helper module (replace hardcoded 2025-07-01) | S |
| G.X-R-09 | "Today" policy: `timezone.localdate()` server-side, passed in context | S |
| G.X-R-10 | Allocation-sum validation module shared by Python + JS | M |
| G.X-R-11 | Template inventory / deprecation cleanup (and the dashboard docstring) | S |
| G.X-R-12 | Forms / serializers for high-risk POST endpoints (contacts, bills, projects) | L |

---

## 7. Test-coverage gap map

Reproduced from F.Q section 5. The headline: nearly nothing is tested.

| Domain | Models tested? | Views tested? | E2E? | Notes |
|---|---|---|---|---|
| URL routing / namespaces | No | Partial (reverse/resolve only) | No | `core/tests/test_url_namespaces.py` (109 lines) |
| Quotes service | No | No | No | `test_quote_service.py` (400 lines) — fixtures stale |
| Quotes / PO / Bills views | No | No | Smoke nav only | Bills CRUD, allocation, Xero send — zero |
| HC Claims / Variations | No | No | No | `construction/views/claims.py` 1 000+ lines untested |
| Contract Budget / Rates | No | No | No | Largest templates |
| Staff Hours / Xero Payroll | No | No | No | Live API calls; no mocks |
| Stocktake / Snaps | No | No | No | 20+ endpoints |
| Xero OAuth / Contacts | No | No | No | |
| Documents / 3D / PDFs | No | No | No | |
| PO public supplier flow | No | No | No | Public PO routes untested |
| Settings / Project Types | No | No | No | |
| Email receiving (Lambda→Django) | No | No | No | Manual scripts only |
| E2E smoke (Playwright) | — | — | Minimal (6 tests) | `tests/smoke.spec.js` |
| construction app | No | No | No | Empty models |

---

## 8. Repo hygiene checklist

A single PR could land most of this. Items marked ⚠ hold real secrets — coordinate with whoever holds the AWS credentials before pushing the rotation.

```
git rm -r --cached \
  .venv/ \
  certifi/ certifi-*.dist-info/ \
  charset_normalizer/ charset_normalizer-*.dist-info/ \
  idna/ idna-*.dist-info/ \
  requests/ requests-*.dist-info/ \
  urllib3/ urllib3-*.dist-info/ \
  db.sqlite3 db_test.sqlite3 \
  lambda-complete.zip lambda-fix.zip lambda-update.zip logs.zip \
  get-pip.py eb_logs.txt
```

Add to `.gitignore`:

```
.venv/
*.zip
get-pip.py
eb_logs.txt
__pycache__/
certifi/
certifi-*.dist-info/
charset_normalizer/
charset_normalizer-*.dist-info/
idna/
idna-*.dist-info/
requests/
requests-*.dist-info/
urllib3/
urllib3-*.dist-info/
```

⚠ Rotate and remove:

- `set_eb_env_vars.sh` (live RDS password)
- `set_rds_env_vars.sh` (live RDS password)
- `LOCAL_EMAIL_TESTING.md` (live email API key)
- the `admin123` defaults in `.ebextensions/04_docker_env.config:11-12` and `docker-compose.yml:27-29`
- the in-code `SECRET_KEY` / `XERO_ENCRYPTION_KEY` / `EMAIL_API_SECRET_KEY` defaults

Delete (after confirming nothing depends on them):

- `Procfile`, `Aptfile`, `runtime.txt` (Heroku-era)
- `dev_app/settings/production.py` (legacy)
- `core/templates/core/DEPRECATED_bills_global_*.html` (after route cleanup)
- `core/templates/core/components/data_table.html`, `components/reusable_form.html`
- `core/static/core/media/background.png` (37 MB orphan)
- `core/static/core/media/mason_steampunk.mp4` (1.5 MB orphan)
- `core/static/core/images/logo.png` (likely dead, only `mason_logo.png` is referenced)
- top-level scratch: `db_test.py`, `check_imports.py`, `check_package_sizes.py`, `get-pip.py`
- one of the duplicate `lambda_email_processor.py` / `lambda_function.py` (they're identical)

Move to `docs/` with deduplication: `DEPLOYMENT.txt`, `DEPLOYMENT_CHECKLIST.md`, `DEPLOYMENT_GUIDE.md`, `AWS_DEPLOYMENT_GUIDE.md`, `EMAIL_QUICK_START.md`, `EMAIL_RECEIVING_SETUP.md`, `LOCAL_EMAIL_TESTING.md`, `URL_NAMESPACES.md`, `TEMPLATE_STATIC_NAMESPACES.md`, `MODEL_SERVICE_MAPPING.md`, `PROJECT_TYPE_RESOLVER.md`, `FX_IMPLEMENTATION_PLAN.md`, `ALLOCATIONS_MANAGER_MIGRATION.md`, `REPO_GUIDE.txt`, `SERVICES_ORDER.txt`, `development_notes.txt`, `dependency_tree.txt`, `end_user_documentation.txt`, `knowledge_base.txt`, `refactor.txt`, `table_head_scrolling_issue_fix.txt`. Delete `eb_logs.txt`.

Update `DEPLOYMENT.txt:34` zip command to exclude `*.zip`, `xero_instances_export.json`, `node_modules`, `playwright-report`, `test-results`, `db_test.sqlite3`, `eb_logs.txt`, `__pycache__`, the vendored `requests/`/`urllib3/`/etc. directories.

---

# Appendices — full per-domain audit reports

Each appendix is the verbatim deep-dive from the corresponding subagent. Use these for the granular detail (code excerpts, full finding lists) when working through a particular area.

- Appendix A — Models, services, formulas
- Appendix B — Views, URLs, auth, queries
- Appendix C — Templates
- Appendix D — JavaScript & CSS
- Appendix E — Settings, security, deployment
- Appendix F — Tests, dead code, migrations
- Appendix G — Cross-cutting consistency

---

## Appendix A — Models, services, formulas

### A.1 Critical (data integrity / silent wrong numbers)

- **[A.M-C-01] `bill_status=2` overloaded — approved vs sent-to-Xero** — `core/models.py:797-798`, `core/views/bills_global.py:916-918`, `core/views/dashboard.py:386`, `core/views/dashboard.py:2492`. Model defines `STATUS_APPROVED=2` and `STATUS_SENT_TO_XERO=3`, but the Direct Xero workflow sets status **2 after a successful send** with comment "sent to Xero". Bills already in Xero remain status 2 and are still counted in dashboard "ready to send" (`bill_status__in=[2,103]` with no `bill_xero_id` filter). Recommendation: Use a single status state machine; Direct send must land on `STATUS_SENT_TO_XERO` (3), and dashboard queries must exclude `bill_xero_id__isnull=False`.

- **[A.M-C-02] HC "paid/settled" treats approved (2) as settled** — `core/models.py:806-812`, `core/views/hc_claims.py:839-852`. `STATUSES_SETTLED_FOR_HC_CLAIM = {STATUS_APPROVED, STATUS_SENT_TO_XERO}` feeds `paid_invoices` in HC C2C (`c2c_hc = working_budget - paid_invoices - invoices_in_claim`). Any bill merely **approved** (not sent/paid) inflates "paid" and suppresses HC claimable amounts. Recommendation: Align settled set with business intent (likely `{3, 4}` or add explicit `STATUS_PAID`); document and test before changing.

- **[A.M-C-03] Three incompatible "committed" implementations** — `core/formulas.py:5-47`, `core/views/contract_budget.py:230-546`, `core/views/hc_claims.py:709-818`. Contract budget committed includes quotes + Internal `contract_budget` + Labour wages/super + direct bills (types 0/1) + snaps. HC claims committed includes quotes + snaps only (no bills, Internal, Labour). `formulas.Committed()` is global, sums quote + filtered bill allocations, returns `(costing_pk, amount)` list — different shape and scope again. HC claim working budget and C2C will disagree with Contract Budget UI. Recommendation: One project-scoped `CommittedService.committed_for_project(project, tender_or_execution)` consumed by both views.

- **[A.M-C-04] `Bill_allocations` created with wrong FK kwarg `bill_pk=`** — `core/views/bills.py:157-158`, `construction/views/claims.py:380-386`, `construction/views/claims.py:441`. Model FK is `bill`, not `bill_pk`. These create paths should raise `TypeError: Bill_allocations() got unexpected keyword argument 'bill_pk'` unless never exercised. Recommendation: Replace with `bill=invoice`; add integration test for allocation upload.

- **[A.M-C-05] `upload_bill` references removed `invoice_division` field** — `core/views/bills.py:119-130`, `core/models.py:815-816`. Model comment says `invoice_division` was replaced by `project` FK; view still passes `invoice_division=invoice_division` to `Bills()`. Recommendation: Remove field or map to `project`; fix upload path.

- **[A.M-C-06] Quotes service references renamed contact field `contact_name`** — `core/services/quotes.py:67`, `core/services/quotes.py:206-207`. `Contacts` field is `name` (renamed in `0005_rename_contact_email_contacts_email_and_more.py`). `get_committed_quotes_list` and `get_committed_items_for_costing` will fail at query/access time. Recommendation: Use `contact_pk__name` / `contact.name`.

- **[A.M-C-07] `main.create_contacts` uses pre-rename field names** — `core/views/main.py:74`. Creates `Contacts(contact_name=..., contact_email=...)` — fields no longer exist (`name`, `email`). Recommendation: Fix or delete dead endpoint.

- **[A.M-C-08] Wrong allocation PK attribute `bill_allocations_pk`** — `core/views/bills.py:339`, `core/views/bills.py:376`, `construction/views/claims.py:388`. Model PK is `bill_allocation_pk` (`core/models.py:884`). Attribute access raises `AttributeError`. Recommendation: Rename all references to `bill_allocation_pk`.

- **[A.M-C-09] `approve_bill_direct` skips allocated state and wrong guard** — `core/views/bills_global.py:249-257`. Validates `bill_status != 0` (not `STATUS_ALLOCATED=1`) and jumps straight to `2`. Allows approving bills that were never allocated; conflates with "ready for Xero" queue per dashboard semantics. Recommendation: Enforce `0 → 1 → 2 → 3` transitions via model helpers.

- **[A.M-C-10] HC claim draft creation without `project` FK (construction path)** — `construction/views/claims.py:88-89`, `core/models.py:1100-1103`. `HC_claims.objects.create(date=..., status=0)` omits `project`; `display_id` allocation and finalize guard (`hc_claims.py:965-969`) depend on project. Recommendation: Require `project_id` on create (mirror `core/views/hc_claims.py`).

- **[A.M-C-11] `update_hc_claim_data` resolves draft claim globally** — `construction/views/claims.py:122`. `HC_claims.objects.get(status=0)` — first draft across all projects; race-prone with multi-project drafts. Recommendation: Scope by `project_id` + `status=0`.

- **[A.M-C-12] `get_invoiced_amounts` lacks progress-claim allocation filter** — `core/views/hc_claims.py:835-855` vs `core/formulas.py:12-15`. Formulas exclude progress-claim lines except `allocation_type=1`; HC invoiced sums **all** `Bill_allocations.amount`. Progress-claim bills can overstate `invoiced` and distort QS formula (`c2c_qs = working_budget - invoiced`). Recommendation: Shared `Bill_allocations.objects.committed_for_costing()` / `invoiced_for_hc()` queryset helpers.

- **[A.M-C-13] Contract budget snap→costing match by item *name*, HC claims by FK** — `core/views/contract_budget.py:400-408`, `core/views/hc_claims.py:734-741`. Renaming a costing line breaks contract-budget snap roll-ups silently; HC claims fixed to use `snap_item__item_id`. Recommendation: Use FK consistently in `contract_budget.py`.

### A.2 High (significant duplication / formula drift)

- **[A.M-H-01] `formulas.Committed()` is dead code** — `core/formulas.py:5-47`; imported at `core/views/bills.py:86`, `core/views/main.py:55`, `core/views/documents.py:57`, `construction/views/claims.py:56` but **never called** (only definition matches grep). Recommendation: Delete or wire up; remove stale imports.

- **[A.M-H-02] Duplicate bill-allocation filter Q-literal** — `core/formulas.py:13-14`, `core/formulas.py:24-25`. Same `Q(bill__bill_type__in=[0,1]) | (Q(bill__bill_type=2) & Q(allocation_type=1))` duplicated twice in one function. Recommendation: `Bill_allocations.objects.filter(Bill_allocations.Q_COMMITTED)` on model/manager.

- **[A.M-H-03] Staff wages + super calculation triplicated** — `core/views/contract_budget.py:182-227`, `core/views/contract_budget.py:336-374` (inline loop), `core/views/staff_hours.py:2003-2005`, `core/views/staff_hours.py:2181-2186`. Hourly-from-salary, super `/100`, and float accumulation duplicated. Recommendation: Single `compute_staff_allocation_cost(alloc) -> Decimal` in `core/services/` (partial helper exists but loop reimplements it).

- **[A.M-H-04] `get_employee_super_rate` HTTP call inside allocation loops** — `core/views/contract_budget.py:364-367`, `core/views/staff_hours.py:1862-1902`. Called per staff allocation when computing Labour committed — N× Xero Payroll API latency and failure modes. Recommendation: Batch/cache super rates per `(xero_instance, employee)` per request.

- **[A.M-H-05] Widespread `float()` on money before sum/compare** — `core/views/contract_budget.py:266-267`, `core/views/hc_claims.py:845`, `core/views/bills_global.py:1025-1033`, `core/views/pos.py:254-263`, `core/services/quotes.py:209-212`. Decimal DB columns converted to float for arithmetic and 0.01 tolerance checks — classic rounding drift. Recommendation: Keep `Decimal` through aggregation; use `quantize(Decimal('0.01'))`.

- **[A.M-H-06] GST computed in JS only (10% default)** — `core/templates/core/stocktake.html:1430`, bill templates (`amount * 0.1`). No shared Python GST helper; server accepts client-supplied `gst_amount`. Recommendation: `core/formulas.gst_from_net(net, rate=Decimal('0.1'))` used by views + documented override rules.

- **[A.M-H-07] Progress-claim percentage math duplicated in `pos.py`** — `core/views/pos.py:261-263`, `core/views/pos.py:1142-1149`. Same `(amount / contract_sum * 100)` block in two view functions. Recommendation: Extract `progress_claim_percent(amount, contract_sum)`.

- **[A.M-H-08] Quote `amount = qty * rate` duplicated** — `core/views/quotes.py:203`, `core/views/quotes.py:697-700`. No model `save()` or shared validator ensuring stored `amount` matches qty×rate. Recommendation: Centralise in `Quote_allocations.clean()` or service layer.

- **[A.M-H-09] Magic `bill_status` literals despite new constants** — `core/views/bills_global.py:257`, `core/views/bills.py:533`, `core/views/dashboard.py:2466`, `core/views/pos.py:412`. Dozens of raw `-2, 0, 1, 2, 100, 102, 103, 104` instead of `Bills.STATUS_*`. Drift already visible in comments (`dashboard.py:2195` labels 2 "Sent for approval"). Recommendation: Mechanical replace with constants; add lint rule.

- **[A.M-H-10] Magic `bill_type` values 0/1/2 without model constants** — `core/models.py:829`, `core/views/contract_budget.py:445`, `core/views/email_receiver.py:147`. Default `bill_type=0` not in `choices=[(2,...),(1,...)]`; "0" meaning implicit. Recommendation: Add `BILL_TYPE_UNSET=0`, `BILL_TYPE_DIRECT=1`, `BILL_TYPE_PROGRESS=2`.

- **[A.M-H-11] Magic category division literals `-5`/`-10`** — `core/views/contract_budget.py:324`, `core/views/contract_budget.py:641-647`. Model defines `Categories.DIVISION_LABOUR` / `DIVISION_INTERNAL` (`core/models.py:616-617`) but views hard-code ints. Recommendation: Use model constants everywhere.

- **[A.M-H-12] Staff allocation type magic `1`** — `core/views/staff_hours.py:2040`, `core/views/staff_hours.py:2143`. Model has `ALLOCATION_TYPE_PROJECT=1` but views use raw `1`. Recommendation: Use named constants.

- **[A.M-H-13] `billed_dict` vs `committed_dict` bill_type rules asymmetric and undocumented in HC path** — `core/views/contract_budget.py:440-506`. Committed excludes `bill_type=2`; billed includes all types. HC claims don't replicate bill roll-ups at all. Recommendation: Document invariants in one module; test cross-view parity.

- **[A.M-H-14] Empty service stubs — logic remains in views** — `core/services/variations.py:1-6`, `core/services/order_book.py:1-6`, `core/services/suppliers.py:1-6`, `core/services/documents.py:1-6`. Only `quotes.py` has code; deleted `core/services/pos.py` (per git status) with logic in `core/views/pos.py`. Recommendation: Either populate services or drop the directory convention.

- **[A.M-H-15] `construction/models.py` empty — domain lives entirely in `core`** — `construction/models.py:1-3`. Construction app is a view/template namespace only; increases coupling and duplicate imports (`construction/views/claims.py:13-18`). Recommendation: Accept explicitly or migrate construction-specific logic/models.

- **[A.M-H-16] Legacy `post_bill` Xero path sets status 2 without OAuth** — `core/views/bills.py:177-233`. Deprecated direct API call; sets `bill_status=2` on success. Overlaps broken status semantics. Recommendation: Remove or gate behind feature flag.

### A.3 Medium (hygiene / consistency)

- **[A.M-M-01] `core/forms.py` essentially unused for domain validation** — `core/forms.py:1-5`. Only `CSVUploadForm`; all bill/quote/claim validation ad-hoc in views (`bills_global.py`, `hc_claims.py`). Recommendation: Introduce ModelForms for high-risk money endpoints or DRF serializers.
- **[A.M-M-02] `core/validators.py` wired only to contacts/dashboard** — `core/validators.py:11-121`, `core/views/contacts.py:23`, `core/views/dashboard.py:61`. Not used on `Contacts` model fields (`clean()` / `validators=`). Bank/ABN rules bypassed when saving via admin/API. Recommendation: Attach validators to model fields or forms.
- **[A.M-M-03] Non-PEP8 model naming (`Po_orders`, `Bill_allocations`, …)** — `core/models.py:734`, `core/models.py:883`, `core/models.py:1271`. Mixed with `Employee`, `StocktakeSnap`. Recommendation: Long-term rename via `db_table` preservation.
- **[A.M-M-04] Manual `*_pk` primary keys everywhere** — `core/models.py:24`, `core/models.py:814`, etc. Django would normally use `id`; consistent internally but verbose. Recommendation: Document convention; avoid adding new `foo_pk` FK field names (`contact_pk` on Quotes/Bills).
- **[A.M-M-05] `Quotes.contact_pk` / `Bills.contact_pk` FK naming** — `core/models.py:725`, `core/models.py:827`. Non-idiomatic `contact_pk` instead of `contact`. Recommendation: Keep for migration stability; don't extend pattern.
- **[A.M-M-06] `archived` as `IntegerField(0/1)` not Boolean** — `core/models.py:252`, `core/models.py:518`, `core/models.py:293`. Inconsistent with `is_stocktake`, `is_revenue_project`. Recommendation: Gradual migration to `BooleanField` with `db_column` if needed.
- **[A.M-M-07] Missing `class Meta` on several live models** — `core/models.py:14` (`XeroInstances`), `core/models.py:506` (`Projects`), `core/models.py:611` (`Categories`), `core/models.py:720` (`Quotes`), `core/models.py:1090` (`HC_claims`), `core/models.py:1152` (`HC_claim_allocations`), `core/models.py:1208` (`Contacts`), `core/models.py:1271` (`Po_orders`). No ordering/indexes where useful. Recommendation: Add Meta incrementally (HC_claims: index on `(project, status)`).
- **[A.M-M-08] Timestamp retrofit incomplete** — `core/migrations/0035_add_timestamps_to_all_models.py`; `EmployeePayRate` has `created_at` only (`core/models.py:399`), no `updated_at`. `ReceivedEmail` has no `created_at` (`core/models.py:1343-1345`). Recommendation: Align with migration 0035 intent.
- **[A.M-M-09] `StaffHoursAllocations.clean()` never enforced in views** — `core/models.py:494-503`. Views create allocations without `full_clean()`. Recommendation: Call `full_clean()` before save in staff_hours API.
- **[A.M-M-10] `HC_claims.status` lacks named constants** — `core/models.py:1105`. Magic `0/1/2/3` in views (`hc_claims.py:895`, `construction/views/claims.py:149-150`). Recommendation: Mirror `Bills.STATUS_*` pattern.
- **[A.M-M-11] `Po_orders.status` not in admin list_display** — `core/admin.py:271-274` vs `core/models.py:1293`, migration `0080_po_orders_status_field.py`. Admin still shows legacy `po_sent` only. Recommendation: Add `status`, deprecate `po_sent` in admin.
- **[A.M-M-12] `HC_claimsAdmin` missing `project` column** — `core/admin.py:320-321` vs `core/models.py:1100-1103`. Post-0074 FK invisible in admin. Recommendation: Add `project` to `list_display` / `list_filter`.
- **[A.M-M-13] `date.today()` vs timezone-aware dates** — `core/views/stocktake.py:645`, `core/views/bills_global.py:620`, `core/views/dashboard.py:329`, `core/views/staff_hours.py:318`. No `timezone.localdate()` despite Django timezone support. Recommendation: Standardise on `timezone.localdate()` for AU business dates.
- **[A.M-M-14] `XeroInstances._get_cipher()` generates ephemeral key** — `core/models.py:40-47`. Missing `XERO_ENCRYPTION_KEY` creates new Fernet key each call — undecryptable DB blobs on next read. Recommendation: Fail hard if key missing in any environment that writes secrets.
- **[A.M-M-15] `EmailAttachment.get_download_url` does S3/boto in model** — `core/models.py:1421-1464`. Side effects, network I/O, `print()` on error in model layer. Recommendation: Move to `core/services/documents.py` or storage utility.
- **[A.M-M-16] Destructive migration reverse** — `core/migrations/0048_projecttypes.py:24-29`. `reverse_populate` deletes all `ProjectTypes`. Recommendation: Document; prefer noop reverse for data migrations.
- **[A.M-M-17] Multiple RunPython migrations with noop reverse** — `0072`, `0074`, `0076`, `0080` (`reverse_noop`). Acceptable but squashing won't restore data. Recommendation: Note in ops runbook.
- **[A.M-M-18] `get_project_type` utility ignores ProjectTypes table** — `core/utils/project_type.py:44-46`. Validates against hardcoded `PROJECT_TYPE_CHOICES`, not DB `ProjectTypes`. Recommendation: Resolve from DB when dynamic types matter.
- **[A.M-M-19] `get_template_for_project_type` always returns core template** — `core/utils/project_type.py:86-89`. PROJECT_TYPE-specific templates never selected despite docstring. Recommendation: Implement existence check or remove dead branch.
- **[A.M-M-20] Legacy / dead model fields flagged in-model** — `core/models.py:1107-1111` (`HC_claims.invoicee`), `core/models.py:1215-1223` (`Contacts.contact_person`, `division`, `bank_details`). Recommendation: Schedule removal behind data audit.
- **[A.M-M-21] `Po_orders.po_sent` redundant with `status`** — `core/models.py:1292-1293`, `0080_po_orders_status_field.py:13-16`. Two sources of truth; backfill only at migration time. Recommendation: Property `po_sent -> status==SENT` and stop writing boolean.
- **[A.M-M-22] `bill_type` choices omit default value 0** — `core/models.py:829`. Integer default 0 not labelled in choices — admin/forms show blank meaning. Recommendation: Add `(0, 'Unset')` choice.

### A.4 Low (polish)

- **[A.M-L-01] `HC_claim_allocations.__str__` dumps entire row** — `core/models.py:1173-1174`. Unusable in admin dropdowns/logs. Recommendation: Short `f"{item} claim#{display_id}"`.
- **[A.M-L-02] `Quote_allocations.__str__` includes notes** — `core/models.py:752-753`. Recommendation: Truncate notes.
- **[A.M-L-03] `Categories` lacks Meta ordering** — `core/models.py:611-632`. Relies on view `.order_by('order_in_list')`. Recommendation: `ordering = ['order_in_list']`.
- **[A.M-L-04] `SPVData`, `PlanPdfs`, `Letterhead`, `Models_3d` minimal Meta/`__str__`** — `core/models.py:535-596`. Registered in admin but sparse metadata. Recommendation: Add `__str__` for admin usability.
- **[A.M-L-05] `construction/admin.py` / empty construction models** — no construction models registered. Recommendation: Remove empty admin or add comment.
- **[A.M-L-06] `CSVUploadForm` duplicated import pattern** — `core/views/main.py:103-127`, `construction/views/claims.py:11`. Only consumer is main CSV upload. Recommendation: Colocate form with view module.
- **[A.M-L-07] `quotes.get_committed_quotes_list` DEBUG/ prod same MEDIA_URL concat** — `core/services/quotes.py:73-77`. Both branches identical. Recommendation: Delete branch.
- **[A.M-L-08] `StaffHoursAllocations` help_text duplicates choices** — `core/models.py:462-465`. Recommendation: Rely on `choices=` only.
- **[A.M-L-09] No retention math anywhere in app code** — grep only hits vendor libs. Not a bug; document absence for HC/progress-claim scope.
- **[A.M-L-10] `send_hc_claim_to_xero` raises `NotImplementedError`** — `construction/views/claims.py:188-190`. Dead endpoint with unreachable code below. Recommendation: Remove or return 410.

### A.5 Refactor opportunities (named)

- **A.M-R-01 — Centralise bill status state machine (L)** — Where now: `core/models.py:793-805`; transitions in `core/views/bills_global.py:235-257`, `916-924`, `1209-1256`, `core/views/bills.py:1289-1423`, `core/views/dashboard.py:386`, `core/views/stocktake.py:489`, `core/views/pos.py:412-838`. Proposed: `core/services/bills.py` with `BillWorkflow.transition(bill, event)` and guards; views call events only.
- **A.M-R-02 — Unified committed/billed/C2C calculator (L)** — Where now: `core/formulas.py:5-47`, `core/views/contract_budget.py:230-546`, `core/views/hc_claims.py:709-818`, `571-572`. Proposed: `core/services/costing_rollups.py` with `committed(project, scope)`, `billed(project, scope)`, `working_budget(item)`; delete duplicate loops.
- **A.M-R-03 — Bill allocation queryset helpers (S)** — Where now: duplicated Q in `core/formulas.py:13-15`; implicit rules in `contract_budget.py:443-451`, `hc_claims.py:835`. Proposed: `Bill_allocations.QuerySet.direct_cost_lines()` and `.counts_toward_hc_invoiced()`.
- **A.M-R-04 — Centralise GST helper (S)** — Where now: JS `stocktake.html:1430`, bill templates; server accepts raw GST in `bills_global.py`, `stocktake.py`. Proposed: `core/formulas.py`: `gst_from_net()`, `gross_from_net()`; optional override flag.
- **A.M-R-05 — Decimal-safe money pipeline (M)** — Where now: float conversions across `contract_budget.py`, `hc_claims.py`, `bills_global.py`, `pos.py`, `quotes.py` service. Proposed: `core/utils/money.py` with `to_decimal`, `sum_decimals`, JSON encoding helper.
- **A.M-R-06 — Staff cost + super batch service (M)** — Where now: `contract_budget.py:182-227`, `336-374`, `staff_hours.py:1862-1912`. Proposed: `core/services/staff_cost.py` with cached super rates and single allocation cost function.
- **A.M-R-07 — Wire validators into Contacts model (S)** — Where now: `core/validators.py`; manual calls in `contacts.py`, `dashboard.py`. Proposed: `Contacts.clean()` invoking validators; admin uses `ModelForm`.
- **A.M-R-08 — Fix legacy field renames sweep (S)** — Where now: `bill_pk=`/`bill_allocations_pk`/`contact_name`/`invoice_division`/`contact_email` paths in M-C-04..08. Proposed: Single PR with grep-driven fixes + smoke tests.
- **A.M-R-09 — HC claim project scoping (M)** — Where now: `construction/views/claims.py:88`, `122`; `core/views/hc_claims.py` (correct patterns). Proposed: `HC_claims.objects.draft_for_project(project)` manager method; construction views delegate to core service.
- **A.M-R-10 — Populate or delete empty `core/services/*` stubs (S)** — Where now: empty `variations.py`, `order_book.py`, `suppliers.py`, `documents.py`. Proposed: Move `hc_variations.py` / `order_book` view logic into services incrementally, or delete stubs to avoid false layering.

**Summary stats (A):** 13 Critical, 16 High, 22 Medium, 10 Low, 10 named refactors. Highest-risk clusters: bill status semantics, committed/invoiced formula drift across Contract Budget vs HC Claims, and legacy field names causing runtime failures on several code paths.

---

## Appendix B — Views, URLs, auth, queries

### B.1 Critical (security / data integrity / outages)

- **[B.V-C-01] Unauthenticated database wipe endpoint in production URLs** — `core/views/database_wipe.py:17-120`, wired at `core/urls.py:169`. `wipe_database` is `@csrf_exempt`, has no `@login_required` / `@staff_member_required`, and TRUNCATEs every non-auth table on POST. Recommendation: Remove from production URLconf immediately; gate with staff + CSRF (or admin-only management command) and require explicit confirmation token.

- **[B.V-C-02] Unauthenticated database diagnostics exposes DB credentials metadata** — `core/views/database_diagnostics.py:9-56`, `core/urls.py:168`. Returns engine, host, port, user, version, and row counts with no auth and `@csrf_exempt`. Recommendation: Delete from production or restrict to `DEBUG` + staff; never expose connection metadata publicly.

- **[B.V-C-03] API diagnostics leaks secret-key validation logic** — `core/views/api_diagnostics.py:9-27`, `core/urls.py:192`. Compares configured vs request API keys and exposes lengths/previews; `@csrf_exempt`, no auth. Recommendation: Remove from production URLconf; use env/CloudWatch checks instead.

- **[B.V-C-04] Xero OAuth diagnostics exposes client_id and auth URL** — `core/views/xero_diagnostics.py:9-50`, `core/urls.py:165`. Returns full `client_id`, redirect URI, and constructed auth URL; no auth. Recommendation: Staff-only + feature-flag; redact client_id in responses.

- **[B.V-C-05] SecurityMiddleware commented out** — `dev_app/settings/base.py:77`. HSTS, SSL redirect, and other security headers from Django's security stack are disabled. Recommendation: Uncomment `SecurityMiddleware` as first middleware entry in all deployed settings.

- **[B.V-C-06] Hardcoded SECRET_KEY and encryption defaults in base settings** — `dev_app/settings/base.py:25-28,31`. `SECRET_KEY`, `XERO_ENCRYPTION_KEY`, and `EMAIL_API_SECRET_KEY` have insecure in-repo defaults; production settings inherit base without overriding them. Recommendation: Require env vars in production; fail startup if missing.

- **[B.V-C-07] Global CSRF bypass on mutating endpoints (~183 `@csrf_exempt` usages)** — widespread, e.g. `core/views/bills.py:110+`, `core/views/stocktake.py:13+`, `core/views/xero.py:220+`, `construction/views/claims.py:66+`. Nearly all JSON POST/PUT/DELETE handlers disable CSRF while most also lack login checks. Recommendation: Remove blanket `@csrf_exempt`; use `@ensure_csrf_cookie` + JS token for SPA, or token/API-key auth for webhooks only.

- **[B.V-C-08] No authentication on core business mutation APIs** — e.g. `core/views/bills.py:735` (`bills_view`), `core/views/bills.py:524` (`get_approved_bills`), `core/views/projects.py:17` (`create_project`), `construction/views/claims.py:66` (`associate_sc_claims_with_hc_claim`). Only ~50 views use `@login_required` (mostly `staff_hours.py`, `rates.py`); zero uses of `is_staff` / `permission_required` in views. Recommendation: Default-deny with `@login_required` on all non-public routes; add role checks for financial mutations.

- **[B.V-C-09] Public PO claim submission without auth** — `core/views/pos.py:599-662`, top-level routes `dev_app/urls.py:16-17`. `submit_po_claim` is `@csrf_exempt` POST; any holder of `unique_id` can create/update pending bills (`bill_status=100`) and allocations. Recommendation: Treat as intentional supplier flow but add signed tokens, rate limits, and supplier verification; never reuse for staff operations.

- **[B.V-C-10] SSL certificate verification disabled globally in claims module** — `construction/views/claims.py:60`. `ssl._create_default_https_context = ssl._create_unverified_context` disables TLS verification for all outbound HTTPS from that module. Recommendation: Remove; use proper CA bundle or per-request `verify=True`.

- **[B.V-C-11] Exception messages returned to clients** — e.g. `core/views/pos.py:596`, `core/views/rates.py:143-147` (includes traceback), `core/views/bills.py:174`. Broad `except Exception` returns `str(e)` or stack traces to callers. Recommendation: Log server-side; return generic error IDs to clients.

- **[B.V-C-12] Multi-table mutations without transactions** — e.g. `core/views/bills.py:157-167` (`allocate_bill`: creates allocations, updates costings, updates bill status), `construction/views/claims.py:88-90` (create HC claim + bulk bill update). Partial failure can corrupt committed amounts vs bill status. Recommendation: Wrap multi-row workflows in `transaction.atomic()`; only 9 `atomic()` blocks exist across all views.

- **[B.V-C-13] Clickjacking protection disabled** — `dev_app/settings/base.py:83`. `XFrameOptionsMiddleware` is commented out (only `X_FRAME_OPTIONS = 'SAMEORIGIN'` set, but middleware not active). Recommendation: Re-enable middleware or use CSP `frame-ancestors`.

### B.2 High (significant duplication / wrong abstraction / N+1)

- **[B.V-H-01] JSON response boilerplate duplicated ~900+ times** — `JsonResponse` appears ~900 times across views; explicit `{'status': 'success'}` ~44 times, `{'status': 'error'}` ~200+ times; `dashboard.py:67-77` and `contacts.py:29-36` each define local `error_response`/`success_response`; HC modules use `{'error': ...}` (~52 occurrences) instead. Recommendation: Add `core/views/_helpers.py` with `json_ok()`, `json_err()`, and `@api_view` wrapper enforcing shape + status codes.

- **[B.V-H-02] Approved-bill / committed-allocation filter not centralized** — canonical Q in `core/formulas.py:13-14`; partial duplicate `bill_type__in=[0,1]` at `core/views/contract_budget.py:445,879`; views still use raw `bill_status__in=[1,102]` / `[2,103]` at `core/views/bills.py:533,895,1007`, `core/views/dashboard.py:2466,2492` despite `Bills.STATUS_*` constants at `core/models.py:793-805` (only adopted in `pos.py`). Recommendation: Add `BillQuerySet.approved_for_payment()`, `BillQuerySet.pending_approval()`, and `Bill_allocations.committed()` manager methods; migrate literals.

- **[B.V-H-03] N+1 pay-rate lookups in contract budget labour committed calc** — `core/views/contract_budget.py:336-348`. Inner loop over allocations runs `EmployeePayRate.objects.filter(...).first()` per row plus `get_employee_super_rate()` per row. Recommendation: Prefetch latest pay rates per employee/date in one query or annotate in SQL.

- **[B.V-H-04] ProjectTypeMiddleware implemented but never registered** — `core/middleware.py:10-84` vs `dev_app/settings/base.py:75-85`. Middleware and context processors (`core/middleware.py:87-134`) are dead code; templates lack `request.project_type` from middleware. Recommendation: Either wire into `MIDDLEWARE` + `TEMPLATES['context_processors']` or delete; views currently rely on ad-hoc session reads.

- **[B.V-H-05] ProjectTypeMiddleware would N+1 on every request if enabled** — `core/middleware.py:80-82`. `Projects.objects.all()` + `.count()` on each request when session lacks `project_pk`. Recommendation: Replace with `exists()` / cached session value; never full-table scan per request.

- **[B.V-H-06] Duplicate fixed-on-site update endpoints** — `construction/views/claims.py:101-111` (`update_fixedonsite`) vs `core/views/contract_budget.py:164-179` (`update_fixed_on_site`); both `@csrf_exempt`, wired at `core/urls.py:88` and `construction/urls.py:18`. Recommendation: Keep one implementation; deprecate the other URL.

- **[B.V-H-07] Duplicate HC claims URL namespaces** — same claim ops registered under `core:` (`core/urls.py:119-136`) and `construction:` (`construction/urls.py:14-26`) via re-exports in `core/views/__init__.py:48-54`. Recommendation: Single namespace (`construction:`) with core importing for backward compat only; document canonical names.

- **[B.V-H-08] Email sending duplicated without shared helper** — `EmailMultiAlternatives` at `core/views/dashboard.py:1702`, `core/views/pos.py:578,781,920`; `send_mail` at `core/views/main.py:86`, `construction/views/claims.py:37`. Each rebuilds subject/body/attachments inline. Recommendation: `core/services/email.py` with templated PO/bill/claim senders.

- **[B.V-H-09] PDF generation duplicated across 5 modules** — xhtml2pdf+pypdf at `core/views/dashboard.py:53-57,1585,1803`; PyPDF2 at `core/views/documents.py:23-110`, `core/views/bills.py:63`, `core/views/main.py:25`, `construction/views/claims.py:30-43`; reportlab at `documents.py:33-36`, `claims.py:40-43`; PO PDF serving at `core/views/pos.py:957-997`. No shared PDF service. Recommendation: `core/services/pdf.py` wrapping HTML→PDF, merge, stamp.

- **[B.V-H-10] Broad exception swallowing (~250+ `except Exception` blocks in views)** — e.g. `construction/views/claims.py:96-98`, `core/views/stocktake.py` (28 blocks), `core/views/bills_global.py` (28). Many return 500 with raw exception text. Recommendation: Central `@handle_api_errors` decorator mapping `ValidationError`, `DoesNotExist`, Xero errors to typed responses.

- **[B.V-H-11] `get_approved_bills` logs per-row in hot path** — `core/views/bills.py:544-546`. `logger.info` inside `for invoice in invoices` on every poll. Recommendation: Remove loop logging; use debug level + single summary line.

- **[B.V-H-12] Active/archived project filter inconsistent** — `archived=False` at `core/views/bills_global.py:1416`; `exclude(project__archived=1)` at `core/views/dashboard.py:2434-2507`; many bill queries omit archived filter entirely (`core/views/bills.py:532-533`). Recommendation: `Projects.objects.active()` manager; apply consistently.

- **[B.V-H-13] Manual `is_authenticated` checks instead of decorators (inconsistent)** — `core/views/pos.py:332-336`, `core/views/email_receiver.py:190-191` vs `@login_required` elsewhere. Recommendation: Standardize on `@login_required` / `@login_required(login_url=...)`; remove ad-hoc 401 JSON branches.

- **[B.V-H-14] `rates.py` combines `@csrf_exempt` + `@login_required`** — e.g. `core/views/rates.py:150-152`. CSRF disabled even for authenticated browser sessions. Recommendation: Drop `csrf_exempt` where session auth is used; keep CSRF for cookie-based login.

- **[B.V-H-15] Python-side aggregation where SQL would suffice** — `core/formulas.py:37-45` merges two queryset dicts in Python; `core/views/contract_budget.py:460-463` sums allocation amounts per costing in loops after fetch. Recommendation: Push rollups to `annotate(Sum(...))` grouped queries.

### B.3 Medium (consistency / hygiene)

- **[B.V-M-01]** Top-level PO routes pierce namespace scheme — `dev_app/urls.py:5-18` imports `core.views.pos` directly; duplicates redirect at `core/urls.py:260`.
- **[B.V-M-02]** `dev_app/urls.py` couples root URLconf to internal view modules.
- **[B.V-M-03]** `dashboard` vs `dashboard_alt` duplicate homepage at `dev_app/urls.py:10-11`.
- **[B.V-M-04]** Inconsistent project PK URL param naming — `<int:project_pk>` vs `projects_pk` field lookups vs bare `pk`.
- **[B.V-M-05]** Inconsistent JSON error shapes — `{status,message}` vs `{error}` vs `{success,error}`.
- **[B.V-M-06]** HTTP status code discipline weak — almost no `422`; wrong methods often return `400` instead of `405`.
- **[B.V-M-07]** Date parsing duplicated ~25+ times as `datetime.strptime(..., '%Y-%m-%d')`.
- **[B.V-M-08]** Query param parsing ad hoc — `request.GET.get('project_pk')` strings passed to ORM without validation.
- **[B.V-M-09]** Hard-coded URL paths instead of `reverse()` — `core/views/xero_oauth.py:40,105`, `core/views/xero_diagnostics.py:18`, `core/views/staff_hours.py:48`.
- **[B.V-M-10]** REST naming inconsistency — mix of `get_*`, `create_*`, `save_*`, `finalize_*`, `fix_*`, `toggle_*`, `send_*`, `pull_*`.
- **[B.V-M-11]** `core/views/__init__.py` re-export fan-in adds fragility — re-exports ~70 symbols from 12 modules.
- **[B.V-M-12]** Orphan re-exports / dead imports — `generate_po_html`, `debug_settings`, `send_test_email` vs `send_test_email_view`.
- **[B.V-M-13]** Deprecated global bills routes still wired at `core/urls.py:197-199`.
- **[B.V-M-14]** Duplicate claims compatibility shim at `core/views/claims.py:1-22`.
- **[B.V-M-15]** WhiteNoise middleware ordering suboptimal — placed after auth/messages in `dev_app/settings/base.py:84-85`.
- **[B.V-M-16]** ELB health check bypasses host validation in `dev_app/middleware.py:34-37`.
- **[B.V-M-17]** Staff hours debug endpoint wired in production at `core/views/staff_hours.py:2516-2519`, `core/urls.py:388`.
- **[B.V-M-18]** Email list debug endpoint at `core/views/email_receiver.py:185-210`.
- **[B.V-M-19]** Mixed POST response shapes for same domain (JSON vs HTML redirect).
- **[B.V-M-20]** CSV upload/parsing duplicated across `core/views/main.py`, `contract_budget.py`, `claims.py`.
- **[B.V-M-21]** Logging: 4 view modules have no logger (diagnostics trio + `project_type.py`, `settings.py`).
- **[B.V-M-22]** `print()` debug left in `core/views/rates.py:449-484` (5 calls).
- **[B.V-M-23]** `rates.py` returns traceback to client on 500 at `core/views/rates.py:143-147`.
- **[B.V-M-24]** No caching of config-like reads — repeated `XeroInstances.objects.all()` across views.
- **[B.V-M-25]** `core/middleware.py` context processor duplicated as class and function (lines 87-134); neither wired.

### B.4 Low (polish)

- **[B.V-L-01]** Comment in base settings admits pre-production debt at `dev_app/settings/base.py:162`.
- **[B.V-L-02]** `logger.setLevel(logging.INFO)` in `construction/views/claims.py:63` — mutates global logging config per-module at import.
- **[B.V-L-03]** `alphanumeric_sort_key` exported from `core/views/__init__.py:60`; utility, not a view.
- **[B.V-L-04]** Deprecated xero token comments scattered.
- **[B.V-L-05]** Inconsistent `@require_http_methods` usage.
- **[B.V-L-06]** `update_contacts` URL missing trailing slash at `core/urls.py:116`.
- **[B.V-L-07]** Construction claims module imports unused heavy stack (reportlab, PyPDF2, ratelimit) for a subset of functions.
- **[B.V-L-08]** No async/threading concerns found.

### B.5 Refactor opportunities

- **B.V-R-01** `json_ok` / `json_err` helpers (M)
- **B.V-R-02** `BillQuerySet` workflow filters (M)
- **B.V-R-03** `@staff_api` decorator (S)
- **B.V-R-04** `core/services/email.py` (M)
- **B.V-R-05** `core/services/pdf.py` (L)
- **B.V-R-06** `parse_api_date()` helper (S)
- **B.V-R-07** Wire or delete `ProjectTypeMiddleware` (S)
- **B.V-R-08** Production diagnostics gate via `core/urls_diagnostics.py` (S)
- **B.V-R-09** Transaction wrapper for bill allocation workflows (M)
- **B.V-R-10** Slim `core/views/__init__.py` (S)
- **B.V-R-11** Consolidate public PO routes (S)
- **B.V-R-12** `Projects.objects.active()` manager (S)

**Summary counts (B):** `@csrf_exempt` ≈183 view decorators (27 modules + construction claims); `@login_required` ≈50 (staff_hours 32, rates 17, dashboard 1); ad-hoc `is_authenticated` checks: 2; `transaction.atomic()`: 9 blocks in 7 files; `JsonResponse`: ~900 usages; `print()`: 5 (all `rates.py`); view modules without logger: ~4 diagnostics/settings modules; caching in views: none; threads/async: none found.

---

## Appendix C — Templates

**Components already factored out:**

| File | Lines | Used by | Notes |
|---|---|---|---|
| `components/reusable_navbar.html` | 303 | `dashboard_master.html` only | Inline CSS (~200 lines) + collapse JS |
| `components/allocations_layout.html` | 442 | bills, quotes, PO, HC variations, stocktake, contract budget | Best abstraction in the codebase |
| `components/rates_table.html` | 3,145 | `rates.html`, `bom.html` | Entire screen lives in one include |
| `components/data_table.html` | 67 | **Nothing** (commented out in `dashboard.html:541`) | Dead component |
| `components/reusable_form.html` | 52 | **Nothing** | CSS-only stub, no markup |

**Architecture summary:** Only `dashboard.html` extends `dashboard_master.html`. Everything else is either (a) a hidden SPA fragment `{% include %}`'d from dashboard, (b) an AJAX HTML fragment (`bills_global.html`), or (c) a standalone public/project page (`po_public.html`, fragment views for contract budget / HC claims).

### C.1 Critical

- **[C.T-C-01] Broken template paths for deprecated Bills routes** — `core/views/bills_global.py:152,189,230`, `core/views/bills.py:850,853`. Views render `core/bills_global_inbox.html`, `core/bills_global_direct.html`, and `core/bills_global_approvals.html`, but on disk only `DEPRECATED_bills_global_*.html` exist. Hitting `/core/bills/inbox/` etc. will 500. Either restore/rename templates or delete routes and point all callers at `bills_global_view`.

- **[C.T-C-02] Bootstrap 4 vs Bootstrap 5 API mismatch** — `core/templates/core/bills_global.html:1983-2041`, `2397-2465`; `dashboard_master.html:10,25`. PDF confirm modals call `new bootstrap.Modal(...)` and use `data-bs-dismiss`, but the app loads Bootstrap **4.3.1**. `bootstrap.Modal` is undefined → Send-to-Xero confirmation modals likely fail silently. Same `data-bs-*` attrs on tabs in `staff_hours.html:408-420` and `stocktake.html:559-565` (partially mitigated by manual tab JS at `staff_hours.html:927-939`).

- **[C.T-C-03] Missing `project_selector.html`** — `core/views/project_type.py:129` renders `core/project_selector.html`, which does not exist in the repo.

- **[C.T-C-04] Phantom include documented but absent** — `core/templates/core/dashboard.html:24` references `{% include 'core/xero_modals.html' %}`, but no such file exists; Xero UI lives entirely in `xero.html`.

- **[C.T-C-05] `math_filters.numberformat` uses `locale.setlocale()`** — `core/templatetags/math_filters.py:16-18`. Mutates process-global locale on every filter call; unsafe under concurrent requests and unused in any template (zero `{% load math_filters %}` hits). Remove or replace before adopting server-side money formatting.

### C.2 High (massive duplication, big abstraction wins)

- **[C.T-H-01] Monolithic SPA shell loads ~25k lines of inline JS on every dashboard visit** — `dashboard.html:521-545` includes 10+ full section templates at once. Combined inline script: `stocktake.html` ~2,586; `staff_hours.html` ~2,279; `bills_global.html` ~2,438 (via AJAX but still huge); `components/rates_table.html` ~2,210; `hc_claims.html` ~1,893; `contract_budget.html` ~1,632; `documents.html` ~1,452; (11 more files). Recommendation: lazy-load section HTML/JS on first nav click; extract per-section static JS files.

- **[C.T-H-02] `bills_global.html` triplicates Inbox/Direct/Approvals logic** — `bills_global.html:418-1298` (Inbox JS), `:1300-2093` (Direct JS), `:2095-2393` (Approvals JS). ~2,400 lines where ~800-line DEPRECATED files were copy-pasted and merged. Row builders, GST auto-calc, searchable dropdowns, and allocation footers repeat 3× with section-id string swaps. Extract `_bills_section.js` driven by `{sectionId, statusFilter, columns}` config.

- **[C.T-H-03] DEPRECATED Bills files are dead weight but nearly identical to live code** — `DEPRECATED_bills_global_inbox.html` (708 lines), `_direct.html` (850), `_approvals.html` (782). Not `{% include %}`'d anywhere; overlap with consolidated `bills_global.html` is ~90%. Safe to delete after fixing T-C-01 and confirming no external bookmarks.

- **[C.T-H-04] Allocations list skeleton duplicated across 6+ screens** — Same pattern (main table + allocations table + PDF viewer + "Still to Allocate") implemented via `allocations_layout.html` markup but custom JS per screen: `quotes.html`, `hc_variations.html`, `bills_project.html`, `po.html`, `stocktake.html`, `contract_budget.html`. `AllocationsManager` in `allocations_layout.js` is adopted unevenly—bills global reimplements rather than configuring the manager. Unify on `AllocationsManager.init()` + shared row renderers.

- **[C.T-H-05] Quotes / PO / Variations / Claims share one list-table skeleton, four implementations** — `quotes.html:4-646`, `po.html:6-414`, `hc_variations.html:10-893`, `hc_claims.html:538-2478`. All use `.reusable-table`, row selection (`.selected-row`), and allocation footers, but each ships its own ~600–1,900 lines of JS. A `_document_list_section.html` + `_document_list.js` with `{entity: 'quote'|'po'|'variation'|'claim'}` would collapse 4 sites.

- **[C.T-H-06] Duplicate PDF confirmation modals** — `bills_global.html:1983-2012` vs `:2397-2426` (and mirrors in `DEPRECATED_bills_global_direct.html:736` and `_approvals.html:417`). Same header, iframe preview, confirm/cancel—only IDs differ. One `_pdf_confirm_modal.html` with `modal_id` param.

- **[C.T-H-07] Contact/supplier form duplication** — `contacts.html:47-170` (Verify + Add Supplier modals), `settings.html:515-517` (inline contact row with identical BSB/ABN placeholders), `contacts.html:573-575` (JS-built row). `validateContactFields()` at `contacts.html:170` is contacts-only; settings rebuilds the same fields. Extract `_contact_fields.html` + shared validation JS.

- **[C.T-H-08] Verified badge markup copy-pasted in JS strings** — `contacts.html:325-327,686` and `settings.html:470-472`. Identical Bootstrap badge HTML built in two places. Needs `_verified_badge.html` partial or `Utils.renderVerifiedBadge(status)` in `utils.js`.

- **[C.T-H-09] Hard-coded `/core/...` URLs dominate (~130+ occurrences vs ~30 `{% url %}`)** — Examples: `hc_claims.html:857,895,1257` (11 hardcoded); `contract_budget.html:489-491` (12); `documents.html` (12); `xero.html:140,419` (8); `settings.html` (11). Renaming URL patterns breaks silently. Standardize on `{% url 'core:…' %}` in templates; export URL map from Django into JS for dynamic fetches.

- **[C.T-H-10] Money/date formatting is inconsistent across 4 layers** — (1) Django `floatformat:2` only in `po_public.html:527-584`; (2) `math_filters.numberformat` unused; (3) `Utils.formatMoney` (en-AU), `formatNumber` (en-US), `formatCurrency` in `utils.js`; (4) local duplicates: `hc_claims.html:2465-2469`, inline `toFixed(2)` in 15+ files. Pick one server filter (`{% money value %}`) and one JS helper (`Utils.formatMoney`); deprecate `formatNumber` vs `formatMoney` split.

- **[C.T-H-11] `components/rates_table.html` is a 3,145-line mega-include** — Loaded for both Global Rates (`rates.html:2`) and per-project BOM (`bom.html:2`). Contains ~933 lines CSS + ~2,210 lines inline JS including its own `getCSRFToken()` at `:942`. Should be split into `rates_table.html` (markup), `rates_table.css`, `rates_table.js`.

- **[C.T-H-12] Duplicate `.reusable-table` hover/selected CSS per section** — Nearly identical blocks at `staff_hours.html:155-201`, `stocktake.html:106-152`, `bills_global_buttons.html:85-122`, `rates.html:25-102`, `hc_claims.html:9-139`. All override the same thead/tbody/hover/selected rules. Move section-specific overrides to `data_table_styles.css` using `[data-section="staff-hours"]` scoping.

- **[C.T-H-13] Pending/Approved toggle duplicated** — `bills_global.html:28-137` (`.approvals-toggle-*`) vs `stocktake.html:512-1799` (`.stocktake-toggle-*`) vs `DEPRECATED_bills_global_approvals.html:9-64`. Same HTML/CSS/JS pattern, different class prefixes. One `_mode_toggle.html` component.

- **[C.T-H-14] `reusable_form.html` and `data_table.html` are abandoned half-abstractions** — Created but never wired (`reusable_form` has zero includes; `data_table` commented out at `dashboard.html:541`). Either finish adoption or delete to avoid false expectations.

- **[C.T-H-15] `dashboard_master.html` vs `dashboard.html` naming confuses inheritance** — Master is the true base (DOCTYPE, navbar, global scripts); dashboard is the SPA body. New developers look for `base.html`. Only one child extends master (`dashboard.html:1`). Standalone views (`contract_budget.html`, `hc_claims.html`, etc.) ship no chrome—fine for AJAX fragments, confusing for direct browser hits.

### C.3 Medium

- **[C.T-M-01]** Inline `<style>` blocks repeat design tokens. Total inline CSS: `rates_table.html` ~933 lines; `projects.html` ~575; `stocktake.html` ~530; `dashboard.html` ~330; `hc_claims.html` ~481; `po_public.html` ~445.
- **[C.T-M-02]** Duplicate CSRF helpers redefined locally despite `utils.js:255-257`.
- **[C.T-M-03]** Duplicate date formatters — three implementations of dd-mmm-yy.
- **[C.T-M-04]** Row selection class names inconsistent — `.selected-row`, `.selected-bill-row`, `.selected`, etc.
- **[C.T-M-05]** Project navigation duplicated between Tender and Construction in `project_buttons_switching.html:1-987`.
- **[C.T-M-06]** Documents modals share form skeleton at `documents.html:48-96`.
- **[C.T-M-07]** Xero instance management is inline, not modular.
- **[C.T-M-08]** `templates/registration/login.html` is an orphan page with different stack (Bootstrap 5.1.3, no shared CSS).
- **[C.T-M-09]** Version string hard-coded in two places: `reusable_navbar.html:246` and `dashboard.html:99`.
- **[C.T-M-10]** Dangerous admin actions exposed in dashboard JS — `dashboard.html:1117,1155`.
- **[C.T-M-11]** `staff_hours.html:1950` calendar uses clickable `<div>` not `<button>`.
- **[C.T-M-12]** Alert-driven UX instead of inline feedback (50+ `alert()` calls).
- **[C.T-M-13]** Bill status labels are magic strings everywhere.
- **[C.T-M-14]** `po_public.html` reimplements entire table CSS at lines 94-263.
- **[C.T-M-15]** Sticky header CSS duplicated per screen (8+ files).
- **[C.T-M-16]** `projects.html` includes nested giants (BOM rates table + full documents module + 987 lines of nav switching).

### C.4 Low

- **[C.T-L-01]** `{% load humanize %}` imported but barely used.
- **[C.T-L-02]** Comment blocks are enormous (`dashboard.html:4-100`, etc.).
- **[C.T-L-03]** Placeholder strings "XXX-XXX" / "XX XXX XXX XXX".
- **[C.T-L-04]** `bills_project_buttons.html` does not exist.
- **[C.T-L-05]** Debug utilities shipped in production `utils.js`.
- **[C.T-L-06]** Navbar inline styles in component (`reusable_navbar.html:3-202`).
- **[C.T-L-07]** Mixed modal dismiss patterns (BS4 `data-dismiss` vs BS5 `data-bs-dismiss`).
- **[C.T-L-08]** `onclick` in template strings.
- **[C.T-L-09]** Empty `<table>` placeholder rows duplicated.
- **[C.T-L-10]** `login.html` lacks `{% load static %}` favicon.

### C.5 Component / include extraction proposals

Already enumerated in section 6.3 of the master document. T-R-01..T-R-14.

### Inline JS / CSS inventory (top files)

| File | Total lines | Inline `<script>` | Inline `<style>` |
|---|---|---|---|
| `stocktake.html` | 3,485 | ~2,586 | ~530 |
| `staff_hours.html` | 3,270 | ~2,279 | ~504 |
| `components/rates_table.html` | 3,145 | ~2,210 | ~933 |
| `bills_global.html` | 2,772 | ~2,438 | ~218 |
| `hc_claims.html` | 2,478 | ~1,893 | ~481 |
| `contract_budget.html` | 1,965 | ~1,632 | ~301 |
| `documents.html` | 1,806 | ~1,452 | ~253 |
| `po_public.html` | 1,627 | ~921 | ~445 |
| `projects.html` | 1,603 | ~902 | ~575 |
| `dashboard.html` | 1,181 | ~630 | ~330 |

### Accessibility snapshot

- `aria-*` / `role=`: ~80 occurrences total across all templates (mostly tabs/modals); vast majority of interactive UI has none.
- `<label for=`: ~13 occurrences (`login.html` is best at `:27-31`; most forms use unlabeled inputs in tables).
- Worst offenders: `staff_hours.html` calendar divs (`:1950`), `documents.html` folder tree (click-only rows), table-heavy screens with no `scope` on `<th>`, pervasive `alert()` for errors.

---

## Appendix D — JavaScript & CSS

### D.1 Critical

- **[D.F-C-01]** Bootstrap 4 loaded, Bootstrap 5 APIs used — `core/templates/core/dashboard_master.html:10-25`, `core/templates/core/bills_global.html:1983-2035`. Master loads Bootstrap 4.3.1; bills/stocktake/staff-hours use BS5 markup. `bootstrap.Modal` undefined → silent failure.
- **[D.F-C-02]** No unified HTTP client. Canonical CSRF helpers exist (`core/static/core/js/utils.js:255-283`) but no shared `fetch`/`$.ajax` wrapper. ~150+ call sites hand-roll.
- **[D.F-C-03]** Widespread `@csrf_exempt` on authenticated JSON endpoints removes CSRF as a defense layer for cookie-authenticated POSTs.
- **[D.F-C-04]** 37 MB orphaned static asset in repo — `core/static/core/media/background.png`, zero references, shipped via `collectstatic` every deploy.
- **[D.F-C-05]** Production debug/diagnostic code ships in `utils.js` — `core/static/core/js/utils.js:824-1151` (`verifyStickyHeader`, `debugStickyHeader`), `:1214-1509` (FX debug suite), `:1511` `console.log('[FX] Foreign Currency utilities loaded...')`. ~47% of file is console-oriented tooling.
- **[D.F-C-06]** Money formatting locale split inside `Utils` — `utils.js:50-57` `en-US`; `:88-92` `en-AU`; `:66-67` `formatCurrency` delegates to `formatNumber` (US) then prepends `$`. Same screen can show inconsistent separators.

### D.2 High

- **[D.F-H-01]** Duplicate CSRF cookie parsers (5+) — canonical `utils.js:28-41`; duplicated in `dashboard_master.html:39-52`, `rates.html:183-191`, `documents.html:1772-1780`, `components/rates_table.html:942-957`. `dashboard.html:1114` reads `[name=csrfmiddlewaretoken]` instead.
- **[D.F-H-02]** Mixed jQuery AJAX + vanilla `fetch` (~4:1 ratio in templates). `$.ajax(` ≈ 148, `fetch(` ≈ 23.
- **[D.F-H-03]** Best partial fetch wrapper not shared — `staff_hours.html:872-885` `staffHoursApi()` adds CSRF + JSON body but no `response.ok`, no 401 redirect.
- **[D.F-H-04]** Global mutable SPA state on `window.*` — bills (`window.billsInboxData`, `window.billsDirectData`, `window.currentBillData`); navigation (`window.hideAllSections`, `window.pendingProjectNavigation`); project context; rates BOM (`window.itemsItems`, `window.itemsCategories`).
- **[D.F-H-05]** `project_type_config.js` duplicates business rules that belong in DB/backend — `:38-41` hardcodes `isConstruction()` as `construction|pods|precast`. Backend source: `ProjectTypes.rates_based`.
- **[D.F-H-06]** Column layout rules duplicated Python ↔ JS — server passes `is_construction` + JSON column defs; client also encodes widths/headers in `project_type_config.js:46-536` and `allocations_layout.js` defaults.
- **[D.F-H-07]** Z-index arms race — values: 1, 2, 5, 10, 11, 100, 2000, 9999, 1050-1060, **1050000** (`styles.css:186` `#quoteModal`).
- **[D.F-H-08]** Three parallel CSS/table systems — `styles.css` (legacy), `data_table_styles.css` (modern), Bootstrap `.table` overrides in `global_styles.css:48-68`.
- **[D.F-H-09]** `!important` used to win specificity wars — static CSS: `global_styles.css` (7), `data_table_styles.css` (4), `styles.css` (3), `utils.js` injected (9). Templates: `staff_hours.html` 17, `projects.html` 47, `stocktake.html` 24.
- **[D.F-H-10]** No JS/CSS build, minification, or cache-busting — `package.json` is Playwright-only; settings use plain `STATIC_URL` without `ManifestStaticFilesStorage`.
- **[D.F-H-11]** 1.2 MB PNG logo in static tree — `core/static/core/images/mason_logo.png`.

### D.3 Medium

- **[D.F-M-01]** `formatMoney` / `formatCurrency` / `ProjectTypeConfig.formatCurrency` triplication; some sites double-prefix `'$' + Utils.formatMoney(x)`.
- **[D.F-M-02]** Date formatting duplicated 6+ ways.
- **[D.F-M-03]** `recalculateFooterTotals` defined twice with different signatures (`utils.js:224-246` vs `allocations_layout.js:559-585`).
- **[D.F-M-04]** `allocations_layout.js` doc references dead `getCsrfToken()` at `:66`.
- **[D.F-M-05]** Production `console.log` noise — static JS: ~135 (utils.js 100, allocations_layout.js 35); templates: ~200+.
- **[D.F-M-06]** Inline `<style>` blocks duplicate `data_table_styles.css` (25+ templates).
- **[D.F-M-07]** Hard-coded colors without tokens (~40+ literals).
- **[D.F-M-08]** No spacing scale — `padding: 2.5px`, `4px 6px`, `6px 12px`, inline `padding: 20px`.
- **[D.F-M-09]** Button styles fragmented despite `.rt-btn` system.
- **[D.F-M-10]** Event binding mostly delegated jQuery; rare inline `onclick` (6 hits).
- **[D.F-M-11]** `createSearchableDropdown` document listener leak at `utils.js:647-653`.
- **[D.F-M-12]** CSS injected from JavaScript — `utils.js:704-822` injects ~110 lines of dropdown CSS at runtime.
- **[D.F-M-13]** XSS escape inconsistent — `Utils.escapeHtml` exists but not always used.
- **[D.F-M-14]** `core/utils/project_type.py` is NOT the JS counterpart for column matrices.
- **[D.F-M-15]** 1.5 MB video with zero references — `core/static/core/media/mason_steampunk.mp4`.
- **[D.F-M-16]** jQuery 3.5.1 + Bootstrap 4.3.1 from CDN (EOL-adjacent) — no SRI, no vendored fallback.
- **[D.F-M-17]** `staff_hours.html` duplicates allocation type constants.

### D.4 Low

- **[D.F-L-01]** `formatNumber` vs `formatMoney` naming confusion.
- **[D.F-L-02]** `parseFloatSafe` underused (defined `utils.js:76-78`).
- **[D.F-L-03]** `#quoteModal { z-index: 1050000 }` likely dead.
- **[D.F-L-04]** Legacy hand-rolled overlays in `styles.css` (`#combinedModal`, `#pdfModal`).
- **[D.F-L-05]** Float-based layout remnants (`styles.css:97-105`).
- **[D.F-L-06]** `.delete-column` defined twice in `styles.css`.
- **[D.F-L-07]** `AllocationsManager` re-init guard is empty (`allocations_layout.js:125-126`).
- **[D.F-L-08]** Deep selectors in templates (5+ levels).
- **[D.F-L-09]** `projects.html` weak CSRF fallback.
- **[D.F-L-10]** `hc_claims.html` ternary CSRF fallback.
- **[D.F-L-11]** Background sync on every session start (`dashboard_master.html:28-91`).
- **[D.F-L-12]** `po_public.html` fetch without CSRF (intentional).
- **[D.F-L-13]** Humanize only on server for public PO — visible inconsistency.
- **[D.F-L-14]** `logo.png` vs `mason_logo.png` — only the latter is referenced.
- **[D.F-L-15]** Playwright `tests/global-setup.js:70` uses raw `fetch`.

### D.5 Refactor opportunities

Already enumerated in section 6.4 of the master document. F-R-01..F-R-10.

### Fetch/AJAX pattern summary

| Pattern | Where | CSRF | Error handling | 401 redirect |
|---|---|---|---|---|
| `Utils.getJSONHeaders()` + `fetch` | `contacts.html`, `xero.html` | Yes | Partial | Yes |
| `staffHoursApi()` | `staff_hours.html:872` | Yes | No | No |
| `stocktakeAjax()` | `stocktake.html:920` | Yes (POST) | Optional | No |
| Raw `$.ajax` + manual headers | `bills_global.html`, `contract_budget.html`, `settings.html`, `rates_table.html` | Yes | `alert()` / inline | Rare |
| Raw `fetch` + DOM csrf token | `dashboard.html:1117` | Yes | `alert()` | No |
| Raw `fetch` no CSRF | `po_public.html:1372` | No (public) | `alert()` | N/A |

### `window.*` global inventory (risk-ranked)

| Global | Risk |
|---|---|
| `billsInboxData`, `billsDirectData`, `billsApprovalsData` | High — stale data after partial updates |
| `currentBillData`, `currentSelectedBillPk` | High — selection state races |
| `xeroInstancesData` | Medium — shared across staff hours, settings |
| `AllocationsManager`, `Utils`, `ProjectTypeConfig` | Medium — intentional libs |
| `hideAllSections`, `pendingProjectNavigation` | Medium — SPA router coupling |
| `currentTenderProject`, `currentConstructionProject`, `currentQuotesProject` | Medium — overwritten on project switch |
| `itemsItems`, `itemsCategories`, `ratesTableUnits` | Medium — large arrays on window |
| `adjustAllocationsHeight` | Low — per-section functions |
| `debugStickyHeader`, `debugFxOrange`, FX globals | Low — debug pollution |

---

## Appendix E — Settings, security, deployment

### E.1 Critical (security risk, secret leakage, production-breaking)

- **[E.S-C-01]** Hardcoded `SECRET_KEY` in shared settings — `dev_app/settings/base.py:25`.
- **[E.S-C-02]** `SECRET_KEY` fallback duplicates insecure default in production — `dev_app/settings/production_aws.py:17`.
- **[E.S-C-03]** Hardcoded `XERO_ENCRYPTION_KEY` fallback — `dev_app/settings/base.py:28`.
- **[E.S-C-04]** Weak default `EMAIL_API_SECRET_KEY` — `dev_app/settings/base.py:31`. Lambda uses different env name (`API_SECRET_KEY`).
- **[E.S-C-05]** Production RDS password committed in EB setup script — `set_eb_env_vars.sh:15` `RDS_PASSWORD=DevApp2024SecurePass!`.
- **[E.S-C-06]** Production RDS password committed in RDS setup script — `set_rds_env_vars.sh:18` `RDS_PASSWORD=U1wPqDKuRZVZ6hwRrLkrpnNp`.
- **[E.S-C-07]** Live email API secret committed in documentation — `LOCAL_EMAIL_TESTING.md:28,61,91`.
- **[E.S-C-08]** Default production superuser password `admin123` in EB deploy — `.ebextensions/04_docker_env.config:11-12`.
- **[E.S-C-09]** Default superuser credentials in Docker Compose — `docker-compose.yml:27-29`.
- **[E.S-C-10]** Unauthenticated database wipe endpoint — `core/views/database_wipe.py:17-19`, `core/urls.py:169`.
- **[E.S-C-11]** Near-total lack of auth on JSON API surface — only `dashboard_view`, `rates.py`, `staff_hours.py` consistently require login.
- **[E.S-C-12]** Production SQLite database committed to git — `db.sqlite3` (~1.5 MB).
- **[E.S-C-13]** Entire `.venv` committed (9 095 files).
- **[E.S-C-14]** Vendored Python packages at repo root — `certifi/`, `charset_normalizer/`, `idna/`, `requests/`, `urllib3/`.
- **[E.S-C-15]** `xero_instances_export.json` contains OAuth secrets — included in `deploy.zip` because zip excludes don't cover it.
- **[E.S-C-16]** Deploy bundle includes large zip artifacts with potential secrets/logs — `lambda-*.zip`, `logs.zip`.

### E.2 High (significant hygiene / risk)

- **[E.S-H-01]** `SecurityMiddleware` disabled — `dev_app/settings/base.py:77`.
- **[E.S-H-02]** `XFrameOptionsMiddleware` disabled; conflicting `X_FRAME_OPTIONS` — `dev_app/settings/base.py:83-87`.
- **[E.S-H-03]** WhiteNoise placed last in middleware stack — should follow `SecurityMiddleware`.
- **[E.S-H-04]** Invalid / ineffective `ALLOWED_HOSTS` patterns — `'herokuapp.com'` doesn't match `*.herokuapp.com`.
- **[E.S-H-05]** Hardcoded CSRF trusted origins for dev ports in base.
- **[E.S-H-06]** Invalid CSRF origins in local settings — `http://127.0.0.1:*` is not valid Django syntax.
- **[E.S-H-07]** PostgreSQL credentials in `DATABASE_URL` default — `dev_app/settings/base.py:118`.
- **[E.S-H-08]** Public diagnostic endpoints expose infrastructure.
- **[E.S-H-09]** Startup script ignores migration/collectstatic failures — `start.sh:16,27` `|| echo "...continuing..."`.
- **[E.S-H-10]** `create_admin` resets superuser password every deploy if `DJANGO_SUPERUSER_PASSWORD` is set.
- **[E.S-H-11]** Lambda ↔ Django API secret env name mismatch.
- **[E.S-H-12]** EB deployment writes secrets to `.env` on instance disk.
- **[E.S-H-13]** No HSTS configuration.
- **[E.S-H-14]** ELB health check via spoofable User-Agent — `dev_app/middleware.py:35-37`.
- **[E.S-H-15]** AWS account ID and deploy bucket in docs — `DEPLOYMENT.txt:35,39`.
- **[E.S-H-16]** Conflicting AWS regions across tooling — `ap-southeast-2` vs `us-east-1`.
- **[E.S-H-17]** Legacy `production.py` (Heroku/S3-static) still present alongside `production_aws.py`.
- **[E.S-H-18]** `aws_secrets.py` helper never wired into settings.
- **[E.S-H-19]** No error tracking (Sentry/etc.).
- **[E.S-H-20]** Docker image runs as root, no healthcheck.
- **[E.S-H-21]** `.env.production.template:13` points to wrong settings module.

### E.3 Medium

- **[E.S-M-01]** `DEBUG` not defined in `base.py`; inherited inconsistently.
- **[E.S-M-02]** `debug` context processor enabled in all environments.
- **[E.S-M-03]** `test.py` prints banner on import — side effect on every load.
- **[E.S-M-04]** `wsgi.py` / `asgi.py` default to local settings.
- **[E.S-M-05]** `production_aws.py` RDS config missing `CONN_MAX_AGE`.
- **[E.S-M-06]** `ATOMIC_REQUESTS` not enabled.
- **[E.S-M-07]** `collectstatic` message contradicts config — `start.sh:15` says S3, `production_aws.py:73-75` serves locally.
- **[E.S-M-08]** File upload validation is extension-only in key paths — `core/views/pos.py:833-834`, `core/views/documents.py:504-559`.
- **[E.S-M-09]** `DATA_UPLOAD_MAX_MEMORY_SIZE = 10 MB` may be tight for multi-file document uploads.
- **[E.S-M-10]** `TIME_ZONE = 'UTC'` for an AU business app.
- **[E.S-M-11]** Password validators use Django defaults (min length 8); no breach checker.
- **[E.S-M-12]** No `django-cors-headers`.
- **[E.S-M-13]** `urllib3==1.26.19` (1.x line EOL).
- **[E.S-M-14]** Duplicate PDF libraries — `pypdf` + `PyPDF2`.
- **[E.S-M-15]** `oauth2==1.9.0.post1` appears unused.
- **[E.S-M-16]** `awsebcli` in production `requirements.txt` — bloats Docker image.
- **[E.S-M-17]** Duplicate Lambda sources — `lambda_email_processor.py` and `lambda_function.py` are identical.
- **[E.S-M-18]** Lambda zips in repo, no CI/tests.
- **[E.S-M-19]** `.dockerignore` excludes `set_eb_env_vars.sh` but not vendored root packages or zips.
- **[E.S-M-20]** `.gitignore` gaps — vendored packages, `*.zip`, `logs.zip`, `eb_logs.txt`.
- **[E.S-M-21]** Python version drift — `Dockerfile:2` `python:3.11-slim` vs `runtime.txt:1` `python-3.11.5`.
- **[E.S-M-22]** `Procfile`, `Aptfile`, `runtime.txt` are Heroku-era leftovers.
- **[E.S-M-23]** `start.sh` runs full `dumpdata` + S3 backup on every container start.
- **[E.S-M-24]** Registration/auth wiring minimal — only `templates/registration/login.html`.
- **[E.S-M-25]** `EMAIL_HOST_USER` default exposes real mailbox.
- **[E.S-M-26]** `production.py` duplicates `EMAIL_HOST_PASSWORD` assignment.
- **[E.S-M-27]** `base.py:162` unfinished "to be deleted pre production" comment.

### E.4 Low

- **[E.S-L-01]** `manage.py` is vanilla; defaults to `dev_app.settings.local`.
- **[E.S-L-02]** `dev_app/__init__.py` / `version.py` only expose semver; no runtime impact.
- **[E.S-L-03]** `CustomEmailBackend` is reasonable.
- **[E.S-L-04]** `MyS3Boto3Storage` sets inline PDF disposition.
- **[E.S-L-05]** `package.json` is Playwright E2E only.
- **[E.S-L-06]** `check_imports.py` is stale scratch.
- **[E.S-L-07]** `check_package_sizes.py` is dev utility.
- **[E.S-L-08]** `get-pip.py` (2.6 MB) should not be in repo.
- **[E.S-L-09]** `db_test.py` is local data-structure scratch.
- **[E.S-L-10]** `test_email_locally.py` / `test_email_sender.py` are dev helpers.
- **[E.S-L-11]** `xero_attachment_types.py` is live shared module — belongs in package.
- **[E.S-L-12]** `eb_logs.txt` is stale one-line failure artifact.
- **[E.S-L-13]** `dependency_tree.txt` dated Jul 2024.
- **[E.S-L-14]** No `/healthz` / `/health/` URL.
- **[E.S-L-15]** `README.md` stale — claims Django 4.x, references deleted dashboard app.
- **[E.S-L-16]** `URL_NAMESPACES.md` stale — says core prefix `/`; actual is `/core/`.
- **[E.S-L-17]** `MODEL_SERVICE_MAPPING.md` partially stale — references deleted `pos.py`.
- **[E.S-L-18]** `AWS_DEPLOYMENT_GUIDE.md` checklist outdated — steps 3-10 still pending despite live prod.
- **[E.S-L-19]** `development_notes.txt` (Nov 2025, v61) likely superseded.
- **[E.S-L-20]** `table_head_scrolling_issue_fix.txt` vs `knowledge_base.txt` — duplicate sticky-header docs.
- **[E.S-L-21]** `FX_IMPLEMENTATION_PLAN.md` (Feb 2026) — active but belongs under `docs/`.
- **[E.S-L-22]** `SECURE_PROXY_SSL_HEADER` set in base and production (correct for ALB).

### E.5 Cleanup plan

Already enumerated in section 6.5 of the master document. S-R-01..S-R-12.

### Repo top-level junk

| Path | Issue |
|---|---|
| `.venv/` | 9,095 tracked files |
| `certifi/`, `charset_normalizer/`, `idna/`, `requests/`, `urllib3/` + `*-dist-info/` | Vendored site-packages at root |
| `db.sqlite3` | Tracked despite `.gitignore` |
| `db_test.sqlite3` | Test DB on disk |
| `lambda-*.zip`, `logs.zip` | Tracked deployment/log bundles |
| `get-pip.py` | 2.6 MB bootstrap script |
| `playwright-report/`, `test-results/` | Present on disk; gitignored |
| `node_modules/` | Present on disk; gitignored |
| `__pycache__/` | At root; should be ignored everywhere |
| `eb_logs.txt` | Stale CLI output |
| `xero_instances_export.json` | Sensitive export; gitignored but not deploy-zip excluded |

### DEBUG / DB / static / email by env

| Module | DEBUG | Database | Static | Media | Email |
|---|---|---|---|---|---|
| `local.py` | True | SQLite or RDS via env | Local `/static/` | Local or S3 | SMTP via env |
| `production_aws.py` | False | RDS via `RDS_*` | Local + WhiteNoise | S3 | Office 365 |
| `production.py` | False | base `DATABASE_URL` | S3 | S3 | env |
| `test.py` | True (inherits local) | `db_test.sqlite3` | inherited | inherited | console |

---

## Appendix F — Tests, dead code, migrations

### F.1 Critical

- **[F.Q-C-01]** Missing templates break deprecated Bills routes and AJAX fallback — `core/views/bills_global.py:152,189,230`, `core/views/bills.py:850,853`. Only `DEPRECATED_*` versions exist; routes will 500.
- **[F.Q-C-02]** Missing `project_selector.html` — `core/views/project_type.py:129`.
- **[F.Q-C-03]** `core/services/quotes.py` references deleted field `contact_name` at `:67,206`. `Contacts` uses `name`.
- **[F.Q-C-04]** Unit tests use stale model API — `core/tests/test_quote_service.py:50-66` creates `Contacts(contact_name=..., checked=True)`.
- **[F.Q-C-05]** Fresh test DB migration fails (FK mismatch on `core_invoice_allocations` → `core_invoices`).
- **[F.Q-C-06]** `db.sqlite3` tracked in git despite `.gitignore`.
- **[F.Q-C-07]** Dual test module layout — `core/tests.py` + `core/tests/` package; package shadows the file.
- **[F.Q-C-08]** Production wipe endpoint exposed.

### F.2 High

- **[F.Q-H-01]** Near-zero automated test coverage — `core/tests/` only 2 files (509 lines): URL namespaces + quotes service.
- **[F.Q-H-02]** Playwright docs/scripts reference tests that do not exist — `tests/HOW_TO_RUN_TESTS.md:15`, `tests/README_TEST_DATABASE.md:79-80`, `tests/TEST_STATUS.md:60-66` claim 12 tests + `bills-inbox.spec.js` / `bills-direct.spec.js`. Repo only has `tests/smoke.spec.js` (6 tests). `npm run test:bills-inbox` will fail.
- **[F.Q-H-03]** Four empty service modules (scaffolding only) — `documents.py`, `order_book.py`, `suppliers.py`, `variations.py` (~6 lines each).
- **[F.Q-H-04]** `get_template_for_project_type` exported but never used.
- **[F.Q-H-05]** Custom templatetags are dead — no template uses `{% load json_filters %}` or `{% load math_filters %}`.
- **[F.Q-H-06]** `debug_settings` view is orphan (no URL).
- **[F.Q-H-07]** `alphanumeric_sort_key` re-exported but unused.
- **[F.Q-H-08]** `send_test_email` sends real mail in production — `core/views/main.py:80-94`, `core/urls.py:103`. Unauthenticated POST.
- **[F.Q-H-09]** Staff Hours views hit live Xero Payroll API; no mocking in tests.
- **[F.Q-H-10]** PO audit migrations look sane individually; batching is noisy (4 migrations on one day).
- **[F.Q-H-11]** No straggler imports of deleted `core/services/pos.py`. Codebase clean post-v249 deletion.
- **[F.Q-H-12]** `core/tests/` package missing `__init__.py`.
- **[F.Q-H-13]** Seed script duplication with divergent schemas — `seed_test_data.py` vs `seed_test_data_simple.py`.

### F.3 Medium

- **[F.Q-M-01]** 80 core migrations; `0035_add_timestamps_to_all_models.py` retrofits flagged.
- **[F.Q-M-02]** RunPython migrations with intentional noop reverses.
- **[F.Q-M-03]** Fragile invoice→bill rename path — Django models `Bills`, SQL says `core_invoices`.
- **[F.Q-M-04]** `makemigrations --check` passes — no model drift.
- **[F.Q-M-05]** `construction/migrations/` is empty shell; `construction/models.py` is empty.
- **[F.Q-M-06]** Deprecated Bills HTML files unreferenced — safe to delete after route cleanup.
- **[F.Q-M-07]** `core/views/claims.py` is a backward-compat shim re-exporting from construction.
- **[F.Q-M-08]** `print()` left in production paths (13 app occurrences) — worst: `core/views/rates.py:449-484`.
- **[F.Q-M-09]** TODO debt: 3 OAuth-related entries.
- **[F.Q-M-10]** No `import pdb` / `breakpoint()` in app code.
- **[F.Q-M-11]** Commented-out URL routes (~6 lines) at `core/urls.py:89,114-115,391-392`.
- **[F.Q-M-12]** All static assets in `core/static/core/` are referenced.
- **[F.Q-M-13]** All primary page templates are live (except missing ones in F.Q-C-01/02).
- **[F.Q-M-14]** `core/views/__init__.py` re-exports mostly wired.
- **[F.Q-M-15]** Playwright global setup kills port 8000 aggressively — `lsof -ti:8000 | xargs kill -9`.
- **[F.Q-M-16]** Test settings inherit full `local.py`.

### F.4 Low

- **[F.Q-L-01]** Empty Django test stubs at `core/tests.py:3` and `construction/tests.py:3`.
- **[F.Q-L-02]** No skipped/xfail tests in app code.
- **[F.Q-L-03]** Test naming convention OK in the two files.
- **[F.Q-L-04]** `npm test` correctly blocks accidental runs (`package.json:7`).
- **[F.Q-L-05]** `playwright.config.js` webServer block commented out.
- **[F.Q-L-06]** `Contacts.division` marked for deletion in model comment.
- **[F.Q-L-07]** `README.md` version drift — Django 4.x claim.
- **[F.Q-L-08]** Documentation proliferation / contradictions.
- **[F.Q-L-09]** No empty/no-op migration files.
- **[F.Q-L-10]** `0077` + `0078` could collapse (same day on `StaffHoursAllocations` / `ProjectTypes`).

### F.5 Cleanup proposals

Already enumerated in section 6.6 of the master document. Q-R-01..Q-R-12.

### Test inventory

`core/tests/` (package — 2 files, 509 lines): `test_url_namespaces.py` (109 lines) — `reverse()`/`resolve()` for core homepage/build/drawings/commit_data/upload_bill, namespace registration for development/construction/precast/pods/general. `test_quote_service.py` (400 lines) — 7 service functions in `core/services/quotes.py`.

`core/tests.py` — 3 lines, empty stub, **shadowed by package** (dead).
`construction/tests.py` — 3 lines, empty stub.

Top-level `tests/`: `smoke.spec.js` (72 lines, 6 tests), `seed_test_data_simple.py` (335 lines, active), `seed_test_data.py` (241 lines, legacy unused), `global-setup.js`, `global-teardown.js`, plus 5 README/status `.md` files (several stale).

`playwright.config.js` — testDir `./tests`, baseURL `127.0.0.1:8000`, global setup/teardown, Chromium only.

`dev_app/settings/test.py` — inherits `local.py`; separate `db_test.sqlite3`; MD5 hasher; console email; DEBUG toolbar off; WARNING log level; prints banner on import.

### Top-level scratch files — keep / archive / delete

| File | Verdict |
|---|---|
| `db_test.py` | Archive → `scripts/` |
| `db_test.sqlite3` | Delete from repo (gitignored test artifact) |
| `db.sqlite3` | Delete from repo tracking |
| `check_imports.py` | Archive → `scripts/` |
| `check_package_sizes.py` | Archive → `scripts/` |
| `test_email_locally.py` | Keep in `scripts/` |
| `test_email_sender.py` | Keep in `scripts/` |
| `xero_attachment_types.py` | Keep next to `lambda_function.py` |
| `get-pip.py` | Delete (2.6 MB vendored installer) |
| `lambda-*.zip` | Delete from repo (store in S3/releases) |
| `logs.zip` | Delete (ephemeral debug artifact) |
| `xero_instances_export.json` | Delete from repo (sensitive) |

---

## Appendix G — Cross-cutting consistency

### G.1 Critical

- **[G.X-C-01]** Missing bill template files — live URLs/views reference templates that do not exist (see C.T-C-01, F.Q-C-01).
- **[G.X-C-02]** `Bills` status constants defined but almost never used — magic numbers dominate at `core/views/bills.py:533,651,895,1007,1379`, `core/views/bills_global.py:257,918,923,1174,1211,1255`, `core/views/dashboard.py:386,420,2146,2195,2466,2492,2507`, `core/templates/core/bills_project.html:604`, `core/templates/core/bills_global.html:754,1717`. Only `core/views/pos.py:181,220,227,631` partially uses `Bills.STATUS_*`.
- **[G.X-C-03]** Same integer, different meaning across domains — `STATUS_APPROVED = 2` on `Bills` vs `STATUS_SENT_TO_XERO = 2` on `StocktakeSnap` vs `STATUS_CANCELLED = 2` on `Po_orders`. Any shared helper on bare `status=2` is ambiguous.
- **[G.X-C-04]** Stocktake JS `BILL_STATUS` enum does not match `Bills` model — `core/templates/core/stocktake.html:911-915` defines `{PENDING:0, APPROVED:1, SENT:2}` while model defines `-2…104`.
- **[G.X-C-05]** Dashboard template docstring contradicts implementation for archive status — `core/templates/core/dashboard.html:31,41` says Archive → status `4`; backend archives to `-1`. Status `4` is `STATUS_PAID`.
- **[G.X-C-06]** Invoice→Bill rename incomplete across URL/API/variable layers — URL kwarg `invoice_id` (`core/urls.py:133,187,203-204`), view functions `create_unallocated_invoice_allocation`, POST fields `invoice_total`/`invoice_pdf`, path `upload-invoice/`, endpoint `get_po_table_data_for_invoice`. ~100+ `invoice` mentions remain.
- **[G.X-C-07]** `is_admin` semantics wrong — `core/views/pos.py:314` sets `'is_admin': request.user.is_authenticated`; consumed at `core/templates/core/po_public.html:718`. Any logged-in user gets admin UI on public PO pages.

### G.2 High

- **[G.X-H-01]** `allocation_type` is two different enums under one name — Bill allocations: `0=as per bill_type`, `1=direct cost in progress claim`. Staff hours: `1=Project, 2=Unchargeable, 3=Other, 4=R&D`.
- **[G.X-H-02]** `bill_type=0` is a silent third type — model choices document only `1` and `2` but default is `0`.
- **[G.X-H-03]** GST computed via hardcoded `* 0.1` in multiple layers (no shared helper).
- **[G.X-H-04]** Decimal fields written with `float()` — `core/views/bills.py:869` assigns `invoice.total_gst = float(total_gst)` on `DecimalField`.
- **[G.X-H-05]** "Still to allocate" formula duplicated server-side validation + client display.
- **[G.X-H-06]** HC claim formulas duplicated in Python and JS — backend `core/views/hc_claims.py:563-572`; frontend `core/templates/core/hc_claims.html:2141-2149`.
- **[G.X-H-07]** JSON error envelope split across three conventions.
- **[G.X-H-08]** Duplicate `error_response` / `success_response` helpers in `dashboard.py:67-77` and `contacts.py:29-38`.
- **[G.X-H-09]** URL/view import style inconsistent.
- **[G.X-H-10]** `Po_orders` dual state: `po_sent` boolean + `status` enum.
- **[G.X-H-11]** Australian business context vs `en-us` / `UTC` settings.
- **[G.X-H-12]** No pagination on large data screens.

### G.3 Medium

- **[G.X-M-01]** Model class naming: PEP 8 vs `Pascal_Snake` / plural-row models.
- **[G.X-M-02]** URL name ↔ view ↔ template ↔ JS naming misaligned.
- **[G.X-M-03]** "Costing Item" vs "Item" vs "BOM line" vs "Line item" — same concept, four labels.
- **[G.X-M-04]** Template context conventions are ad hoc per view.
- **[G.X-M-05]** `project_type_config.js` vs backend `rates_based` drift.
- **[G.X-M-06]** Status comment drift on `bill_status=2` (three different labels in three files).
- **[G.X-M-07]** `Po_orders.status` constants unused outside one write.
- **[G.X-M-08]** Contact verified status documented but not centralized.
- **[G.X-M-09]** Project lifecycle status magic numbers (`1=tender, 2=execution`).
- **[G.X-M-10]** Forms layer effectively bypassed for user input.
- **[G.X-M-11]** `core/validators.py` wired to one endpoint only.
- **[G.X-M-12]** Deprecated views still registered; consolidated template doc outdated.
- **[G.X-M-13]** `core/services/order_book.py` is an empty stub.
- **[G.X-M-14]** `construction/views/claims.py` vs `core/views/claims.py` — re-export shim, redundant.
- **[G.X-M-15]** HC/domain language still says "Invoiced" for bills.
- **[G.X-M-16]** Hardcoded financial-period date only in Staff Hours JS — `2025-07-01` at `core/templates/core/staff_hours.html:1009`.
- **[G.X-M-17]** Auth decorator coverage uneven.

### G.4 Low

- **[G.X-L-01]** Logging mostly standardized; two outliers — `core/views/pos.py:48`, `core/views/rates.py:449-484` `print()`.
- **[G.X-L-02]** Currency display hardcoded to `$`.
- **[G.X-L-03]** i18n enabled but unused.
- **[G.X-L-04]** Legacy DB table name preserved — `Bills.Meta.db_table = 'core_invoices'`.
- **[G.X-L-05]** `main.py` duplicate unreachable error returns — `core/views/main.py:154-155`.
- **[G.X-L-06]** Seed/test scripts still say "Invoices" in print statements.
- **[G.X-L-07]** `StocktakeSnap` JS constants partially aligned.
- **[G.X-L-08]** `CSVUploadForm` duplicated import path.
- **[G.X-L-09]** Public PO URL path still says `upload-invoice` (name=`upload_bill_pdf`).
- **[G.X-L-10]** `core/views/dashboard.py` module docstring lists moved functions.

### G.5 Centralisation proposals

Already enumerated in section 6.7 of the master document. X-R-01..X-R-12.

### Status-code catalog

| Domain | Values | Defined | Mostly magic-used |
|---|---|---|---|
| `Bills.bill_status` | `-2,-1,0-4,99-104` | `core/models.py:793-805` | Views/templates |
| `Bills.bill_type` | `0,1,2` | choices `1,2` only `core/models.py:829` | `contract_budget.py`, `email_receiver.py` |
| `Bill_allocations.allocation_type` | `0,1` | `core/models.py:893-895` | construction claims, bills_global |
| `StaffHoursAllocations.allocation_type` | `1-4` | `core/models.py:446-456` | staff_hours |
| `Po_orders.status` | `0,1,2` | `core/models.py:1278-1280` | mostly `po_sent` instead |
| `StocktakeSnap.status` | `0,1,2` | `core/models.py:979-985` | uses constants ✓ |
| `Projects.project_status` | `1=tender,2=execution` | comment `core/models.py:519` | widespread literals |
| `Contacts.verified_status` | `0,1,2` | property `core/models.py:1235` | templates only |
| Stocktake JS `BILL_STATUS` | `0,1,2` (wrong) | `stocktake.html:911-915` | does not match model |

### Invoice legacy mentions (sample)

| Layer | Examples |
|---|---|
| URLs | `invoice_id` kwarg `core/urls.py:133,187`; `upload-invoice/` `dev_app/urls.py:18`; `get_po_table_data_for_invoice` `core/urls.py:210` |
| Views | Variable `invoice` throughout `bills.py`, `bills_global.py`, `pos.py`, `dashboard.py`; functions `create_unallocated_invoice_allocation` |
| POST fields | `invoice_pdf`, `invoice_total`, `invoice_id` `core/views/bills.py:101-116`, `core/views/pos.py:827` |
| Templates | `invoice_id=0` in URL reverse `core/templates/core/bills_global.html:2361`; PO copy "Upload Invoice" `core/views/pos.py:555` |
| Intentional keep | Xero API types (`InvoiceID`), upload field name `invoice_pdf` until form rename |

---

*End of audit.*

