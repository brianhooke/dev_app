# Session Handoff — Mason / dev_app

**Last updated:** 26 May 2026 (v256 — staged for deploy: C2C export drops working_budget col + super-rate cache fixes 504 on execution export)
**Read this first** if you are picking up the audit cleanup work in a new chat.

---

## Deploy state

- **Live env**: `dev-app` / `dev-app-prod` in **us-east-1**. CNAME `app.mason.build` → `dev-app-prod.eba-pypetq2i.us-east-1.elasticbeanstalk.com`. Account `629256540295`.
- **Live RDS**: `dev-app-db.crnrbbuoh4sd.us-east-1.rds.amazonaws.com` (PostgreSQL, db `postgres`, user `dbadmin`). Security group `sg-0f70c48a43acf8dce` allows port 5432 only from EB security groups — no CIDR ingress by default.
- **Live version (currently serving)**: `v252-stocktake-2step-and-uli` (deployed 25 May 2026 — Stocktake two-step approval + ULI category seed). v253 was packaged but superseded by v254 before deploy.
- **Local code-state version**: `v256` — staged for next deploy. v253 + v254 + v255 + v256 changes folded into one zip:
  - **v256** (no migration): C2C export schema match + 504 fix. (1) `export_projects_c2c` no longer emits `working_budget`; CSV is now `project_name, revenue_receivable, c2c_incl_margin_and_labour, c2c_margin, c2c_labour` to match the downstream consumer's expected schema. `_compute_project_export_totals` still computes `working_budget` (free side-product) but it's silently dropped at write time. (2) `get_employee_super_rate` is now wrapped in a Django cache (default LocMemCache, 5-min TTL keyed by `(xero_instance_id, employee_id)`). This was the root cause of the **504 Gateway Timeout** the user hit when exporting execution-mode projects: `compute_staff_hours_allocation_amount` called the Xero Payroll API per StaffHoursAllocations row with a 15s per-call timeout. With ~hundreds of execution allocations across ~30 projects this blew straight past ALB's 60s idle timeout. After caching, each `(xero_instance, employee)` is fetched at most once per 5 min per gunicorn worker. None values + non-200 + empty payloads are also memoised (via a sentinel) so failed lookups don't spam Xero. Exceptions are deliberately NOT cached so a transient outage doesn't poison the cache. Audit IDs A.M-H-04 / B.V-H-03 partially closed.
  - **v253** (no migration): Stocktake snap dropdown is now a universal project selector with ULI fallback. Allocations dropdown on each snap item lists every active execution project; entries that don't have a costing matching the snap item's name are rendered red and route to that project's "Unexpected Line Items" line. Contract budget ULI Committed/Billed dropdowns and the costing-rollup totals (`compute_project_committed_billed`) all use the new `resolve_snap_allocation_costing_pk` helper. Side-effect fix: pre-A.M-C-13 the rollup gated snap allocations by FK only, which silently skipped every allocation in production (snap_item.item is the project=None master) — totals at the top of the contract budget were chronically lower than the sum of dropdown rows.
  - **v254** (no migration): Tender-mode staff hours + bills, with both kinds of allocation cloned at fix_contract_budget time. See "Tender-mode staff hours + bills (v254)" section below for the full design + manual verification path.
  - **v255** (migration `0083_projects_tender_substatus`): New `Projects.tender_substatus` IntegerField (1=Tendering default, 2=Quoted) + projects.html UI. Every existing project auto-backfills to `Tendering=1` at migration time. New projects default to `Tendering`. Each project card now carries `data-tender-substatus`, shows a coloured pill in the footer when `project_status=1`, and the dropdown form has a Tender Substatus select that calls `update_project` with `tender_substatus=1|2`. The toolbar gained `#projectTenderSubstatusFilter` — a second dropdown that becomes visible only when the main status filter is set to `Tender`, defaulting to `Tendering` with `Quoted` and `All` selectable. `applyProjectStatusFilter` chains the two filters together; the `MutationObserver` on `#projectsGrid` also reacts to `data-tender-substatus` changes so any future code path that mutates the attribute triggers a re-filter automatically. Server endpoints: `create_project` writes the default explicitly via `Projects.TENDER_SUBSTATUS_TENDERING`, `get_projects` returns the field in the JSON payload, `update_project` accepts and validates it (rejects anything outside the choices set with HTTP 400). No tests added — the change is a single nullable-style integer field plus pure UI; no rollup or allocation logic touches it.
- **Verification**: `curl -I https://app.mason.build/` returns `302 → /accounts/login/?next=/` with `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and `strict-transport-security: max-age=86400`. EB env: `Status=Ready`, `Health=Green`.

### How to run management commands on the live instance

The live RDS is private (no public IP) and the EB instance has no SSH key configured. The supported path is **SSM Run Command** against the EB EC2 instance:

```bash
INSTANCE_ID=$(aws --profile default --region us-east-1 \
  elasticbeanstalk describe-environment-resources \
  --environment-name dev-app-prod \
  --query 'EnvironmentResources.Instances[0].Id' --output text)

# Inside the running web container is `current-web-1`.
aws --profile default --region us-east-1 ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters 'commands=["docker exec current-web-1 python manage.py <subcommand>"]'

# To pipe a longer Django shell script:
B64=$(base64 -i your_script.py | tr -d '\n')
aws --profile default --region us-east-1 ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters "commands=[\"echo $B64 | base64 -d > /tmp/x.py\",\"docker cp /tmp/x.py current-web-1:/tmp/x.py\",\"docker exec -i current-web-1 sh -c 'python manage.py shell < /tmp/x.py' 2>&1\"]"
```

The IAM user `dev-app-deployer` was granted `AmazonSSMFullAccess` in this session to enable the above. The EC2 instance role (`aws-elasticbeanstalk-ec2-role`) already has `AdministratorAccess`, so the SSM agent on the instance can register and execute commands.

### Canonical deploy procedure (from `DEPLOYMENT.txt`)

The live env is **not** managed by `eb deploy`. Use raw AWS CLI:

```bash
# 1. Bump version markers
#    core/templates/core/components/reusable_navbar.html  ("vNNN")
#    core/templates/core/dashboard.html                   (header docstring)
# 2. Commit + push to GitHub main
# 3. Zip the working tree
zip -r deploy.zip . \
  -x "*.git*" "*__pycache__*" "*.pyc" ".venv/*" "*.sqlite3" \
     ".DS_Store" "*.log" "csv/*" "pdfs/*" \
     ".elasticbeanstalk/*" "venv/*" "media/*"
# 4. Upload to the EB S3 bucket
aws s3 cp deploy.zip \
  s3://elasticbeanstalk-us-east-1-629256540295/dev-app/deploy-vNNN-description.zip \
  --profile default --region us-east-1
# 5. Create the application version
aws elasticbeanstalk create-application-version \
  --application-name dev-app \
  --version-label vNNN-description \
  --source-bundle S3Bucket=elasticbeanstalk-us-east-1-629256540295,S3Key=dev-app/deploy-vNNN-description.zip \
  --profile default --region us-east-1
# 6. Roll the env to that version
aws elasticbeanstalk update-environment \
  --application-name dev-app \
  --environment-name dev-app-prod \
  --version-label vNNN-description \
  --profile default --region us-east-1
```

Key facts:
- Application name on AWS is `dev-app` (hyphen). The repo directory and Django project module are `dev_app` (underscore).
- Region is `us-east-1`, **not** `ap-southeast-2`.
- `start.sh` runs `migrate --noinput` and `collectstatic` on container start.
- `.elasticbeanstalk/config.yml` now points at `dev-app` / `dev-app-prod` / `us-east-1` so any opportunistic `eb status` / `eb logs` / `eb open` use targets the right env. Avoid `eb deploy` — it bypasses the S3-zip flow.

### Wrong-env deploys to clean up later

A separate sandbox env exists in **ap-southeast-2** (`dev_app` / `dev-app-docker` on RDS `dev-app-db.crda6mduzc63.ap-southeast-2.rds.amazonaws.com`, sg `sg-0205bb6f6e3d2f7fd`). The previous session's `eb deploy` calls and the v251/v252/v253 version labels all landed there, NOT on the live env. Treat that env and its RDS as orphaned — do not `eb deploy` to it again, and ignore claims in earlier session transcripts that v250+ was "live".

The Onyx Factory (Subbie) project pk=2 written during the previous session is in the **wrong** RDS (the ap-southeast-2 one). It is **not** there for users — those rows are orphaned. The re-import was redone this session against the correct RDS — see **Onyx Factory (Subbie) import (live)** below.

### Onyx Factory (Subbie) import (live)

Re-run on 24 May 2026 against the production RDS via SSM Run Command (the live RDS rejected direct connections from outside the EB SG, and the previous session's RDS-SG-open trick was useless because RDS is in a private subnet anyway).

Mapping vs. the original CSV intent:

- **project_type**: live DB has no `general` type. Used `General - MDG` (pk=1) — closest to the user's chosen `General` and matches the only other Onyx project that uses this type (pk=17 `Onyx Factory (Developer)`).
- **xero_instance**: `Mason Development Group` (pk=4), again matching the (Developer) sibling. The CSV said "Mason Build" but pairing General-MDG with Mason Build would have been semantically wrong.
- All other fields per CSV: `xero_sales_account=4110`, `manager='Brian Hooke'`, `manager_email='brian.hooke@mason.build'`, `contracts_admin_emails='dylan.bridge@mason.build'`, `project_status=1` (tender), `is_revenue_project=True`.

Result on live RDS:

- **Project pk=34** `Onyx Factory (Subbie)` (the 31st project on the system, after pks 1-32 + a transient pk=33 burned by the dry-run rollback).
- 13 categories (11 phase categories pk=299..pk=309 + Internal pk=310 + Labour pk=311).
- 60 costing items totalling **$2,186,724.86** — matches the source CSV grand total.

The override mechanism (so the deployed `import_onyx_subbie` can target the live names without redeploying) was monkey-patching at runtime:

```python
import core.management.commands.import_onyx_subbie as onyx
onyx.PROJECT_TYPE = "General - MDG"
onyx.XERO_NAME = "Mason Development Group"
from django.core.management import call_command
call_command("import_onyx_subbie", commit=True)
```

### Remaining deploy hygiene to-dos

- `start.sh` still does `dumpdata core --natural-foreign --natural-primary` as a "pre-migration backup" but this raises `CommandError: Unable to serialize database: cursor "..." does not exist` on every start (the script swallows it). Either fix the serialiser bug or replace this with a scheduled RDS snapshot job.
- `health_endpoint` (`core/views/main.py`) is a 200-OK Django view that doesn't actually check the DB. EB Health stays `Grey` because of this. Consider making it `SELECT 1;` against the DB so EB can detect crash loops automatically.
- Decide whether to terminate the orphan ap-southeast-2 env + RDS to stop accruing cost and to avoid future confusion.
- Lambda + Django still hold the email-pipeline secret under different env-var names (`API_SECRET_KEY` on Lambda vs `EMAIL_API_SECRET_KEY` on Django). Tracked as a deferred unification step in `docs/SECRET_ROTATION_RUNBOOK.md` Step 2 → "Future: rename Lambda env var".

### Email pipeline incident #2 (28 May 2026) — Lambda timeout + stale code

Two days after the secret-rotation fix, users reported bills weren't appearing
again. **NOT the same bug.** Keys were still in sync (Lambda
`API_SECRET_KEY` and Django `EMAIL_API_SECRET_KEY` both `…7cf6ed0e`); every
invocation that *reached* Django returned 200. Two genuinely new failure modes
had emerged:

**Bug A — 60s Lambda timeout on a 30 MB email (27 May 01:53 UTC).** A user
forwarded `for onyx subbie` with **15 PDFs** totalling 30 MB. The Lambda was
configured at `Timeout=60s, Memory=256MB` and ran out of both time and memory
just walking the multipart payload (max RAM observed post-fix: 336 MB). S3
async-invocation auto-retried 3× — all 3 hit the wall. After the 3rd retry
S3 stops trying. That email sat dead in `s3://dev-app-emails/inbox/`.

**Bug B — `application/octet-stream` PDF rejected (27 May 23:58 UTC).** A
Bunnings forwarded email had its PDF declared as `application/octet-stream`.
The deployed Lambda (last modified 25 May 06:18) didn't have the
`xero_attachment_types::resolve_attachment_content_type` filename-fallback —
the local repo did, but it had never been deployed. Symptom in logs:
`Skipping attachment application/octet-stream - not a valid invoice type`
(an error string that doesn't even exist in the local repo anymore).

**Fix applied 28 May 2026.**

1. **Bumped Lambda config**: `Timeout 60s → 300s`, `Memory 256MB → 1024MB`.
   ```bash
   aws lambda update-function-configuration \
     --function-name email-processor --region us-east-1 \
     --timeout 300 --memory-size 1024
   ```
   Memory bump matters: Lambda CPU/network scale linearly with memory, so
   1024 MB ≈ 4× the throughput of 256 MB.

2. **Re-deployed the Lambda code** (zipped `lambda_function.py` + `xero_attachment_types.py` plus `requests`/`urllib3`/`certifi`/`charset_normalizer`/`idna` from a clean
   `pip install --platform manylinux2014_x86_64 --target ... --only-binary=:all: requests`). New code includes the octet-stream→filename mimetype fallback.
   ```bash
   aws lambda update-function-code \
     --function-name email-processor --region us-east-1 \
     --zip-file fileb://lambda_email_processor.zip
   ```

3. **Re-invoked the Lambda** manually for the two stranded S3 keys (the
   30 MB onyx-subbie one and the Bunnings one). Both processed cleanly —
   onyx-subbie in 4.4 s peak 336 MB, Bunnings in 0.3 s. **27 new Bills rows
   landed** (`bill_pk=786..812`).

**Verification path for future sessions.** If users report a similar gap:

1. Check key sync first (`API_SECRET_KEY` last 8 vs `EMAIL_API_SECRET_KEY` last 8) — if it's auth, this'll show it instantly.
2. Check Lambda CloudWatch metrics: `Invocations` vs `Errors` and `Duration` (per-day). If errors > 0 or duration is at the timeout ceiling, it's a Lambda-side issue, not a Django one.
3. Look at the most recent S3 object timestamps in `dev-app-emails/inbox/` and check whether each one has a `Successfully sent to Django: 200` log line. The Lambda log group is `/aws/lambda/email-processor`.
4. If a specific email is stranded, re-invoke with the canonical event shape:
   ```bash
   echo '{"Records":[{"eventVersion":"2.1","eventSource":"aws:s3","awsRegion":"us-east-1","s3":{"bucket":{"name":"dev-app-emails"},"object":{"key":"inbox/<KEY>"}}}]}' \
     | base64 \
     | xargs -I {} aws lambda invoke --function-name email-processor --region us-east-1 \
         --payload {} /tmp/r.json
   cat /tmp/r.json
   ```

### Email pipeline recovery (25 May 2026)

**Symptom.** Users reported emails sent to `bills@mail.mason.build` weren't appearing in the Bills Inbox.

**Root cause.** P-1 secret rotation (commit `894ff43`) updated Django's `EMAIL_API_SECRET_KEY` on EB but did **not** update Lambda's matching env var. Worse, the runbook had a wrong instruction (told you to set `EMAIL_API_SECRET_KEY` on Lambda, but the deployed Lambda code at `lambda_function.py:26` reads `API_SECRET_KEY`). So whatever you set under `EMAIL_API_SECRET_KEY` on Lambda was ignored, the Lambda kept signing with its old `API_SECRET_KEY`, and Django returned 401 on every email POST.

CloudWatch evidence (`/aws/lambda/email-processor`):

```
Error sending to Django API: 401 Client Error: Unauthorized for url: https://app.mason.build/core/api/receive_email/
```

8 emails were stuck in `s3://dev-app-emails/inbox/` between 24 May 23:12 UTC and 25 May 06:02 UTC.

**Fix applied.**

1. Synced Lambda's `API_SECRET_KEY` to Django's `EMAIL_API_SECRET_KEY` (they're now both the same 64-char hex value):

   ```bash
   DJANGO_KEY=$(aws elasticbeanstalk describe-configuration-settings \
     --application-name dev-app --environment-name dev-app-prod --region us-east-1 \
     --query "ConfigurationSettings[0].OptionSettings[?OptionName=='EMAIL_API_SECRET_KEY'].Value" --output text)
   aws lambda update-function-configuration \
     --function-name email-processor --region us-east-1 \
     --environment "Variables={API_SECRET_KEY=$DJANGO_KEY,DJANGO_API_URL=https://app.mason.build/core/api/receive_email/}"
   ```

2. Replayed all 8 stuck S3 objects through Lambda manually (`aws lambda invoke` with synthetic S3 events). Lambda's idempotency check on `ReceivedEmail.message_id` would have skipped duplicates; none were duplicates, all 8 created `ReceivedEmail` (pks 576–583) + 8 `Bills` rows at `bill_status=-2`.

3. Rewrote `docs/SECRET_ROTATION_RUNBOOK.md` Step 2 to:
   - Keep the Lambda env-var name as `API_SECRET_KEY` (matching deployed code); only the value rotates.
   - Add a verify step at the end (`MATCH` / `MISMATCH` echo).
   - Note the asymmetric env-var names explicitly so future rotations don't go off-script.
   - Carve out the rename-Lambda-env-var work as a separate deferred task.

**Recovery snippet for the future** if Lambda → Django ever 401s again:

```bash
# 1. Find the failed S3 keys from CloudWatch
aws logs filter-log-events --log-group-name /aws/lambda/email-processor \
  --region us-east-1 \
  --start-time $(($(date -u +%s) * 1000 - 7*86400*1000)) \
  --filter-pattern '"401 Client Error"' \
  --query 'events[].message' --output text | grep -oE 'inbox/[a-z0-9]+' | sort -u > failed_keys.txt

# 2. After fixing the auth, replay each one (idempotent on Django side via message_id)
while IFS= read -r KEY; do
  PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'Records':[{'eventSource':'aws:s3','s3':{'bucket':{'name':'dev-app-emails'},'object':{'key':sys.argv[1]}}}]}))" "$KEY")
  echo "$PAYLOAD" > /tmp/event.json
  aws lambda invoke --function-name email-processor --region us-east-1 \
    --cli-binary-format raw-in-base64-out --payload file:///tmp/event.json /tmp/resp.json
done < failed_keys.txt
```

---

## Stocktake two-step approval / shelf-lock (25 May 2026, v252)

Triggered by the 50MPa retroactive-allocation forensic earlier in the same session — 16 stocktake allocations were entered after 6 Feb with `bill_date <= 6 Feb`, retroactively inflating the historical balance. The 6 Feb snap was also entered weeks late, so it locked in an already-inflated `book_qty`.

To stop that class of bug recurring, every stocktake bill in the Allocations tab now has two new fields and the Approve workflow refuses to accept it without them:

- **`Bills.pm_approved`** (Boolean, default False) — the PM checkbox in the main row of the Allocations tab. Server-side approve guard rejects the bill unless this is True.
- **`Bills.stock_on_shelf_date`** (DateField, nullable) — the date stock physically landed. Must be **strictly after** the most recent finalised `StocktakeSnap.date`. Once a snap is taken, the shelf is locked for any prior date — bills after the snap must claim a date `≥ snap_date + 1`.

UX flow:

1. User opens Allocations tab → sees PM Approve checkbox + Stock Date input alongside the existing Approve button.
2. Ticking PM Approve auto-fills today's date if the field is empty (`update_stocktake_bill_meta` does this server-side).
3. The Approve button only enables when **all four** gates hold: fully allocated, every row has an item, PM Approved, stock-on-shelf set & after latest snap. Tooltip names whichever gate is failing.
4. `approve_stocktake_bill` re-runs the same gates server-side so a stale tab or direct API call can't bypass them.

JS reads the snap floor (`/core/stocktake/latest_finalised_snap/`) on every Allocations tab refresh, so the date inputs render with the correct `min` attribute.

**Phase 2 follow-up** (NOT done in v252): the stock ledger / snap consumption logic still uses `Bills.bill_date` rather than `stock_on_shelf_date`. The two are equal for newly-approved bills but diverge for legacy bills (which have NULL `stock_on_shelf_date`). Migrating the ledger to use `COALESCE(stock_on_shelf_date, bill_date)` is the natural next step — it lets future snaps consume the right cohort even when a bill was approved with a back-dated `bill_date`. Track as a separate audit item.

---

## Unexpected Line Items category (25 May 2026, v252)

A new universal contingency category auto-seeded on every project. Mirrors the existing pattern of Internal (`-10`) and Labour (`-5`) special divisions:

- **`Categories.DIVISION_ULI = -15`**, name `"Unexpected Line Items"`. Single same-named costing.
- **`Categories.PROTECTED_DIVISIONS = (-10, -5, -15)`** — used by the new server-side guards (Categories.SPECIAL_CATEGORY_NAMES exists too for the `save()`-time normalisation that already enforces division by name).
- Auto-seeded on project creation in `core.views.projects.create_project` after the Internal / Labour blocks.
- Migration `0082_seed_uli_for_existing_projects` runs an **additive backfill** for every existing project — creates the ULI category + tender costing if missing, and the execution costing if missing for any `project_status==2` project. Idempotent. **Never** touches non-ULI rows. Local backfill ran cleanly: 35 ULI categories created, 35 tender costings, 7 execution costings (matches 7 execution-mode projects).

Server-side guards added in v252:

| Endpoint | File | Guard |
|----------|------|-------|
| `delete_category` | `core/views/projects.py` | `division == DIVISION_ULI` → 400 |
| `delete_item` | `core/views/projects.py` | `category.division == DIVISION_ULI` → 400 |
| `delete_category_or_item` | `core/views/rates.py` | Both branches: same as above |
| `update_category_name` | `core/views/rates.py` | Existing ULI cannot be renamed; non-ULI cannot be renamed *to* ULI |
| `update_item_name` | `core/views/rates.py` | ULI costing cannot be renamed |
| `create_new_category_costing_unit_quantity` | `core/views/rates.py` | Block "category" with name ULI; block "item" under ULI category |
| `dashboard.create_category` | `core/views/dashboard.py` | Block name == ULI |
| `dashboard.create_item` | `core/views/dashboard.py` | Block adding under ULI category |

Special integrations:

- **Staff hours**: `get_costings_for_project` returns ULI costings alongside Labour for execution-mode projects. Wages allocated against ULI flow into both:
  - the ULI row's **committed** total in `_compute_project_committed_billed` (added a `wages_carrying_items` queryset that handles ULI by *adding* wages to existing quote/snap committed, vs Labour which *replaces*).
  - the ULI Committed dropdown in `contract_budget.html`, via the `is_uli_costing` branch in `get_item_quote_allocations` that aggregates wages exactly the way `get_item_bill_allocations` does for the Billed dropdown.
- **Stocktake snaps**: `get_snap` now unions all execution projects into `valid_projects` whenever a snap item's name is `"Unexpected Line Items"` — the snap can dump variance against ULI on any project, even if for some reason the project lacks the costing (defensive).
- **Frontend (rates_table.html)**: `.uli-category` / `.uli-item` CSS classes added (teal palette). Drag handles, item drag, and bulk-delete checkboxes are hidden for ULI. The flag is sourced from the new `division` field in `get_rates_data` and `get_project_categories` payloads.
- **Contract budget rendering**: ULI rows fall through the existing non-Internal / non-Labour code path (its name doesn't match either), so the Committed cell is clickable and shows the dropdown of bills + snaps + wages.

Notes for whoever picks this up next:

- The audit's recurring `-5` / `-10` literals scattered across `contract_budget.py` / `costing_rollups.py` / `staff_hours.py` are still mostly inline integers (audit `A.M-H-11`). The v252 ULI batch added the constants in `Categories.DIVISION_ULI` / `PROTECTED_DIVISIONS` and uses them in new code, but did **not** sweep existing `-5`/`-10` literals — that's a separate cleanup pass.
- The C2C export slices in `contract_budget.export_projects_c2c_csv` (Margin/Labour columns) currently treat ULI as a normal cost line (folded into `c2c_incl_margin_and_labour` and `cost_to_complete`). If ULI should get its own export column, that's a separate ask.
- `fix_contract_budget` (tender → execution clone) duplicates ULI like every other costing — no special handling required there.

---

## Stocktake snap → ULI orphan routing (26 May 2026, v253)

**User-visible behaviour change.** When a user opens a stocktake snap and picks a project from the per-item Allocations dropdown:

- Every active execution project is selectable (previously only projects whose costings included an item matching the snap item's name).
- Projects without a costing matching the snap item's name are rendered in **red** (foreground colour `#c0392b`) with a tooltip explaining "allocation will land in Unexpected Line Items".
- The closed `<select>` itself paints red whenever the currently-selected project routes to ULI, so the user can see the routing without having to open the dropdown.
- Auto-create / new-row defaults prefer a project with the named costing (`pickDefaultProject` helper); falls back to a "red" project only when no execution project carries the named costing.

**Backend state-of-the-world.**

- `StocktakeSnapItem.item` is FK to a `Costing` row. In production every `Costing` flagged `stocktake=1` is a global "stockroom" row with `project=None` (probe `core/views/stocktake.py:create_snap` iterates `Costing.objects.filter(stocktake=1)` once globally, not per project). So `snap_item.item.project_id is None` for every snap item in production.
- This means the rollup gate at `core/services/costing_rollups.py` (pre-v253: `if costing_pk not in project_costing_pks: continue`) silently skipped 100% of snap allocations on production — totals at the top of contract-budget rows undercounted snap-driven movements while the dropdowns (which match by name) showed them. v253 closes that gap as a side-effect of the routing helper.

**The new routing helper** (single source of truth for "given a snap allocation on project P, which costing on P should receive it?"):

```python
core/services/costing_rollups.py
def resolve_snap_allocation_costing_pk(
    snap_item_costing_pk,
    snap_item_name,
    project_costing_pks,
    project_costings_by_name,
    project_uli_costing_pk,
):
    # 1) FK direct: snap_item.item is itself one of the project's costings.
    # 2) Name match: project has a costing with the same item name.
    # 3) ULI fallback: route to project's "Unexpected Line Items" line.
    # 4) None: skip silently — no plausible target on this project.
```

Used by:

- `compute_project_committed_billed` — both the committed loop and the billed loop. Replaces the old FK-only gate.
- `get_item_quote_allocations` (Committed dropdown) — for ULI costings, after the existing logic, additionally pulls in snap allocations to this project where `snap_item.item.item` is *not* a costing name on this project (orphan-routed). Each appears with notes `Routed to ULI from "<original snap item name>"` and contact `Stocktake <date> (<original name>)` so the user can tell at a glance which physical-stock item produced the entry.
- `get_item_bill_allocations` (Billed dropdown) — same orphan extension as above, on the ULI costing only.

**`get_snap` payload change.** Each entry in `snap_item.valid_projects` now carries `has_named_costing: bool`. For the ULI snap item (`item_name == 'Unexpected Line Items'`) every project gets `True` since every project carries ULI. Sort order: named-match projects first, alphabetical within each group.

**Frontend changes** (`core/templates/core/stocktake.html`, all in `createAllocationRow`):

- `<option>` colour + `title` set per-project from `has_named_costing`.
- New helper `applyRoutingStyleToSelect()` mirrors the colour onto the `<select>` itself based on the currently-selected option.
- New `pickDefaultProject(validProjects)` used by `autoCreateFirstAllocation` and `createNewAllocation` to bias toward named-match projects.

**No schema changes; no data migration.** Routing is derived from existing data. Dropdown UX, contract-budget dropdowns and rollup totals all converge on the same answer via the same helper.

**Verification path post-deploy:**

1. Open any active execution project's contract budget → expand Committed for "Unexpected Line Items" → confirm orphan-snap rows appear with `Routed to ULI from "<snap item name>"` notes (only if any snap allocations exist on that project against orphan-named items — for the active 4 exec projects, this should produce visible rows since the production probe found 21 cross-project allocs).
2. Open the most-recent stocktake snap → for any non-ULI snap item, confirm the project dropdown lists every active exec project, with red font on those without the costing name.
3. Confirm row totals at the top of the contract budget for "50MPa" / "SL102 (6m x 2.4m)" / etc. now include snap-driven amounts (previously chronically lower than the dropdown sum).

**Known follow-ups deferred:**

- The HC Claims rollup (`hc_committed_amounts`) still uses FK-only matching. Same helper would apply, but no user complaint yet — defer until needed.
- v252's `_compute_project_committed_billed` test fixture (`core/tests/test_costing_rollups.py`) uses `snap_item.item = C1` (a project costing) so the FK-direct path covers it. The new name + ULI fallback paths aren't covered by tests yet — add when the F.Q-C-05 SQLite blocker is resolved or when the next test pass adds prod-shape fixtures.

---

## Tender substatus (26 May 2026, v255)

### What changed for users

- Each project that is in tender mode now carries a substatus: **Tendering** (default) or **Quoted**. Execution-mode projects still have the column populated but the UI ignores it.
- On the projects grid, every tender-mode card shows a small coloured pill next to the "Tender" link in the card footer — orange "Tendering" or blue "Quoted".
- Each project card's expand-out dropdown form has a new "Tender Substatus" select, visible only for tender-mode projects. Click Update → flip → Save to persist.
- The toolbar gained a second dropdown next to the main status filter. It is hidden whenever the main filter is anything other than **Tender**. When the user toggles the main filter to Tender, the substatus filter appears with **Tendering** preselected (and **Quoted** + **All** selectable). The grid then narrows to that subset.
- Default landing state: main filter = **Execution** (unchanged); switching to Tender lands on **Tendering** because that's where new opportunities live.

### Backfill

- Migration `0083_projects_tender_substatus` adds the field with `default=1`, which auto-fills every existing row at apply time. Verified against the local sqlite snapshot: 35/35 projects → `tender_substatus=1`. Production should land the same way (every existing project picks up Tendering on migrate; nothing else changes).

### Server endpoints touched

- `core/views/projects.py::create_project` — explicitly sets `tender_substatus=Projects.TENDER_SUBSTATUS_TENDERING` and returns it in the response.
- `core/views/projects.py::get_projects` — adds `tender_substatus` to each project dict in the JSON payload.
- `core/views/projects.py::update_project` — accepts a `tender_substatus` POST parameter, parses to int, validates against `Projects.TENDER_SUBSTATUS_CHOICES` (rejects any other value with HTTP 400), and persists. Returns the updated value back to the client so the card can re-render its pill from authoritative state.

### UI details

- `core/templates/core/projects.html`:
  - Card root carries `data-tender-substatus="1|2"`.
  - Footer pill markup is built only when `project_status === 1`; for execution-mode cards the pill is omitted entirely.
  - Dropdown form has a "Tender Substatus" `<select>` with the row hidden via inline `style="display:none;"` for execution-mode cards (cheaper than two separate templates and keeps the DOM consistent).
  - Cancel rolls back to `card.data('original-tender-substatus')`; Save re-syncs from `response.project.tender_substatus`.
  - `applyProjectStatusFilter()` now chains the two dropdowns: when the main filter is set to `1` (Tender) the substatus filter is shown and applied; otherwise it's hidden.
  - The pre-existing `MutationObserver` was extended to react to `data-tender-substatus` changes so any future flow that mutates the attribute (e.g. an inline action elsewhere) automatically triggers a re-filter.

### Manual verification path (post-deploy)

1. Hard refresh `https://app.mason.build/projects/`.
2. Confirm v255 appears in the navbar bottom-left.
3. Toggle the main filter to **Tender** — the second dropdown should appear, default Tendering, and the grid should show only tender-mode projects.
4. Open one tender card → Update → flip Tender Substatus to **Quoted** → Save. Pill in the footer should refresh to "Quoted" without a full page reload.
5. Switch the substatus filter to **Quoted** — only the project just flipped should remain visible.
6. Switch the main filter back to **Execution** — the substatus dropdown should hide; execution cards should appear normally.

### Skipped / explicit non-goals

- `fix_contract_budget` does **not** read or mutate `tender_substatus`. The substatus is a tender-pipeline marker only; once a project transitions to execution the value is preserved as-is for historical record but is irrelevant downstream.
- No tests were added. The change is a nullable-style int + UI; no rollup, allocation, or reporting logic depends on it.

---

## Tender-mode staff hours + bills (26 May 2026, v254)

### What changed for users

- **Staff hours** can now be allocated to a project while it's still in tender mode. The Allocations tab's project picker behaves identically to execution mode; the Costings dropdown lists the project's tender Labour + ULI costings.
- **Bills** can now be allocated to tender-mode projects. The tender-side nav now exposes a Bills button group that mirrors the execution view (Unallocated / POs sub-buttons). The same `bills_project.html` template renders for both modes; it switches `tender_or_execution` based on which of `currentTenderProject` / `currentConstructionProject` is active.
- **At fix_contract_budget** (the "Fix it" / Tender → Execution transition), every tender `StaffHoursAllocations` row + every tender `Bill_allocations` row that points at a tender Costing is duplicated. The clone uses the existing `costing_pk_mapping` to point at the matching execution Costing. The original tender row is preserved so reviewing a project in tender mode after transition still shows the historical commit picture.

### What does NOT get cloned

- `StaffHours` (the per-employee per-day timesheet parent) — `unique_together = ('employee', 'date')`, so we'd violate the constraint. The clone happens at the per-project breakdown level (`StaffHoursAllocations`) only.
- `Bills` (the supplier invoice itself) — there's still one `bill.project` FK and one supplier ledger row per invoice. Only the per-line `Bill_allocations` are duplicated. The same Bill therefore carries both tender and execution allocations after transition (each pointing at its respective Costing).

### Server-side TE guards

- `staff_hours.save_allocation`: project-typed allocations now reject costings whose `tender_or_execution` doesn't match the project's current `project_status`. Stops a stale frontend (or a post-transition client) from saving in the wrong scope.
- `bills.create_unallocated_invoice_allocation` / `update_unallocated_invoice_allocation`: same guard via the new `_validate_bill_allocation_costing_te` helper.
- `bills.get_project_bills`: `tender_or_execution` query param defaults to project status, and a mismatched explicit value is rejected (400) rather than silently coerced. The costing picker in `bills_project.html` therefore can never load the wrong scope.

### Rollup TE-isolation tightened

`costing_rollups.compute_project_committed_billed` previously left bills unscoped (the assumption was that Bill_allocations didn't carry TE because the parent `Bills` table didn't). After v254 cloning that's no longer safe — a bill carries both tender and execution allocations for the same dollar. Two queries were tightened with explicit `item__tender_or_execution=tender_or_execution` filters:

- `bill_allocations_direct` (committed-side, direct-cost bills)
- `all_bill_allocations` (billed-side, all bill types)

Same-amount sibling rows on the same Bill no longer leak across the boundary. The previous quirk — bills counted in committed regardless of TE — is now flagged in `test_compute_project_committed_billed_other_scope_documents_quirk` as the intentional new behaviour (every loop is now uniformly TE-isolated).

`bills_global.get_bills_list` filters out the cloned-sibling project allocations from the response (only the row matching the bill project's current TE survives) so the global Bills inbox doesn't show duplicate project rows on bills that survived a transition.

`get_staff_hours_report` (the project × employee pivot at `/core/staff_hours_report/`) gates allocation rows by `(project_status, costing__tender_or_execution)` — a tender project shows tender allocations, an execution project shows execution allocations. Without this gate the pivot would double-count hours for any allocation cloned through `fix_contract_budget`.

### Tests

`core/tests/test_fix_contract_budget.py` (new, 5 tests, all passing under the `dev_app.settings.test` shim):

- `FixContractBudgetCloningTests.test_fixture_starts_in_tender_with_known_counts`
- `FixContractBudgetCloningTests.test_fix_contract_budget_clones_staff_hours_and_bills` — asserts the tender rows are preserved, the same Bill ends up with two allocation rows, and clone counts come out as 2N for both Hours and Bills.
- `FixContractBudgetCloningTests.test_fix_contract_budget_uli_costing_cloned_no_special_casing` — pins that ULI rides through the same `costing_pk_mapping` loop as everything else.
- `TenderExecutionRollupIsolationTests.test_committed_billed_te_2_excludes_tender_bill_allocations`
- `TenderExecutionRollupIsolationTests.test_committed_billed_te_1_excludes_execution_bill_allocations`

`core/tests/test_costing_rollups.py` was updated: `test_compute_project_committed_billed_other_scope_documents_quirk` now expects empty dicts for the tender-side rollup of an execution-only fixture. Was previously asserting `committed = {C1: 400}` (the bill-leakage quirk). The full file (16 tests) still passes.

### Manual verification path post-deploy

1. Pick a tender project. Confirm the BoM nav now shows a Bills group between Quotes and Contract Budget.
2. Allocate a few staff hours against tender Labour + ULI costings via Staff Hours → Allocations. Confirm they appear on the tender contract budget Committed dropdown for those costings.
3. Attach a bill to the tender project, allocate it across one or two tender costings. Confirm the tender contract budget Billed dropdown shows the bill.
4. Run "Fix Contract Budget" on that project (Contract Budget → Fix It). Verify on the live RDS via SSM:
   - Tender `StaffHoursAllocations` + `Bill_allocations` rows still point at the tender Costing PKs.
   - New execution copies exist for the same allocations, pointing at the new execution Costing PKs.
   - The execution contract budget shows those hours + bills via the cloned execution allocations.
   - Re-opening the tender view (Review Tender) still shows the historical tender allocations.
5. Edit one execution-side allocation post-transition. Confirm the tender allocation is unchanged.

### Things explicitly NOT in v254

- HC Claims rollup (`hc_committed_amounts`) — still FK-only for snaps; deferred (carried over from v253).
- Reverse transition (execution → tender) — still not implemented.
- Schema additions: `StaffHoursAllocations` and `Bill_allocations` do **not** have a `tender_or_execution` column. TE is derived from the linked Costing, which is the canonical TE-bearing model.
- `StaffHours` parent rows are unchanged.

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
