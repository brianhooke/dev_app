"""One-shot RDS state inspector.

Pulls the live RDS credentials from the EB environment configuration via
boto3 (the AWS profile is `default` and region `ap-southeast-2`),
connects to PostgreSQL, and prints what the migration state looks like
versus the schema.

Run from the repo root:

    source .venv/bin/activate
    python scripts/inspect_rds_state.py

Outputs:
- last 15 applied migrations per app
- whether key tables exist (core_invoices vs core_bills, allocations, etc.)
- whether 0037_rename_invoice_to_bill is recorded as applied

This script is read-only. Nothing it does mutates RDS.
"""

from __future__ import annotations

import os
import sys

import boto3
import psycopg2


REGION = "ap-southeast-2"
PROFILE = "default"
APP = "dev_app"
ENV = "dev-app-docker"

INTERESTING_TABLES = (
    "core_invoices",
    "core_bills",
    "core_invoice_allocations",
    "core_bill_allocations",
    "django_migrations",
    "core_po_orders",
    "core_costing",
    "core_projects",
    "core_projecttypes",
    "core_publicholidaycalendar",
    "core_publicholiday",
    "core_employee",
    "core_employeepayrate",
    "core_staffhours",
    "core_staffhoursallocations",
    "core_stocktakeallocations",
    "core_stocktakeopeningbalance",
    "core_stocktakesnap",
    "core_stocktakesnapallocation",
    "core_po_globals",
    "core_xerotrackingcategories",
)


def _eb_env_vars() -> dict[str, str]:
    sess = boto3.Session(profile_name=PROFILE, region_name=REGION)
    eb = sess.client("elasticbeanstalk")
    cfg = eb.describe_configuration_settings(ApplicationName=APP, EnvironmentName=ENV)
    out: dict[str, str] = {}
    for opt in cfg["ConfigurationSettings"][0]["OptionSettings"]:
        if opt.get("Namespace") in (
            "aws:elasticbeanstalk:application:environment",
            "aws:elasticbeanstalk:environment:variables",
        ):
            out[opt["OptionName"]] = opt.get("Value", "")
    return out


def main() -> int:
    env = _eb_env_vars()
    host = env.get("RDS_HOSTNAME")
    port = env.get("RDS_PORT", "5432")
    db = env.get("RDS_DB_NAME")
    user = env.get("RDS_USERNAME")
    pw = env.get("RDS_PASSWORD")
    if not all([host, db, user, pw]):
        missing = [k for k, v in (
            ("RDS_HOSTNAME", host),
            ("RDS_DB_NAME", db),
            ("RDS_USERNAME", user),
            ("RDS_PASSWORD", pw),
        ) if not v]
        print(f"[FATAL] EB env missing: {missing}", file=sys.stderr)
        return 2

    print(f"[connect] host={host} port={port} db={db} user={user}")
    try:
        conn = psycopg2.connect(
            host=host, port=port, dbname=db, user=user, password=pw,
            connect_timeout=10, sslmode="require",
        )
    except psycopg2.OperationalError as exc:
        print(f"[FATAL] connect failed: {exc}", file=sys.stderr)
        return 3

    conn.set_session(readonly=True, autocommit=True)

    with conn.cursor() as cur:
        print("\n=== django_migrations: latest 25 across all apps ===")
        cur.execute(
            "SELECT app, name, applied FROM django_migrations "
            "ORDER BY applied DESC LIMIT 25"
        )
        for app, name, applied in cur.fetchall():
            print(f"  {applied}  {app:20s}  {name}")

        print("\n=== django_migrations: latest 5 per app ===")
        cur.execute(
            "SELECT app, name, applied FROM django_migrations ORDER BY app, applied"
        )
        rows = cur.fetchall()
        per_app: dict[str, list[tuple[str, object]]] = {}
        for app, name, applied in rows:
            per_app.setdefault(app, []).append((name, applied))
        for app, items in per_app.items():
            print(f"\n  {app}: {len(items)} migrations")
            for name, applied in items[-5:]:
                print(f"    {applied}  {name}")

        print("\n=== core migrations specifically (last 20) ===")
        cur.execute(
            "SELECT name, applied FROM django_migrations WHERE app='core' "
            "ORDER BY name DESC LIMIT 20"
        )
        for name, applied in cur.fetchall():
            print(f"  {applied}  {name}")

        print("\n=== Is 0037_rename_invoice_to_bill recorded? ===")
        cur.execute(
            "SELECT name, applied FROM django_migrations "
            "WHERE app='core' AND name LIKE '0037%'"
        )
        rows = cur.fetchall()
        if rows:
            for name, applied in rows:
                print(f"  YES — {name} applied at {applied}")
        else:
            print("  NO — 0037_rename_invoice_to_bill is NOT in django_migrations")

        print("\n=== Existence of interesting tables ===")
        for t in INTERESTING_TABLES:
            cur.execute(
                "SELECT EXISTS ( SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=%s )",
                (t,),
            )
            (exists,) = cur.fetchone()
            print(f"  {t:30s}  {'EXISTS' if exists else 'absent'}")

        print("\n=== Row counts on core_invoices vs core_bills (whichever exists) ===")
        for t in ("core_invoices", "core_bills"):
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{t}"')
                (n,) = cur.fetchone()
                print(f"  {t}: {n} rows")
            except psycopg2.errors.UndefinedTable:
                print(f"  {t}: missing")
            except Exception as e:
                print(f"  {t}: error -> {e}")

        print("\n=== Columns on whichever of {core_invoices, core_bills} exists ===")
        for t in ("core_invoices", "core_bills"):
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=%s "
                "ORDER BY ordinal_position",
                (t,),
            )
            cols = [r[0] for r in cur.fetchall()]
            if cols:
                print(f"  {t}: {len(cols)} columns")
                print("    " + ", ".join(cols))

        print("\n=== Allocations table columns ===")
        for t in ("core_invoice_allocations", "core_bill_allocations"):
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=%s "
                "ORDER BY ordinal_position",
                (t,),
            )
            cols = [r[0] for r in cur.fetchall()]
            if cols:
                print(f"  {t}: {cols}")

        print("\n=== Bills/core_invoices columns we expect from 0061/0066 ===")
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='core_invoices' "
            "ORDER BY ordinal_position"
        )
        cols = [r[0] for r in cur.fetchall()]
        print(f"  has 'is_stocktake' (0061): {'is_stocktake' in cols}")
        for fx_col in ("fx_currency", "fx_rate", "fx_total_net", "fx_total_gst",
                       "fx_xero_id", "fx_xero_status", "fx_xero_attempted_at"):
            print(f"  has '{fx_col}' (0066): {fx_col in cols}")

        print("\n=== Full core_invoices column list ===")
        for c in cols:
            print(f"  {c}")

        print("\n=== Total table count + sample of unknown tables ===")
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name LIKE 'core_%' "
            "ORDER BY table_name"
        )
        all_core_tables = [r[0] for r in cur.fetchall()]
        print(f"  total core_* tables: {len(all_core_tables)}")
        for t in all_core_tables:
            print(f"    {t}")

    conn.close()
    print("\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
