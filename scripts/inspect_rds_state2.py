"""Round 2 — list ALL public tables and check `core_projects` columns.

Read-only.
"""

from __future__ import annotations

import sys

import boto3
import psycopg2

REGION = "ap-southeast-2"
PROFILE = "default"
APP = "dev_app"
ENV = "dev-app-docker"


def _eb_env() -> dict[str, str]:
    sess = boto3.Session(profile_name=PROFILE, region_name=REGION)
    eb = sess.client("elasticbeanstalk")
    cfg = eb.describe_configuration_settings(ApplicationName=APP, EnvironmentName=ENV)
    out = {}
    for opt in cfg["ConfigurationSettings"][0]["OptionSettings"]:
        if opt.get("Namespace") in (
            "aws:elasticbeanstalk:application:environment",
            "aws:elasticbeanstalk:environment:variables",
        ):
            out[opt["OptionName"]] = opt.get("Value", "")
    return out


def main() -> int:
    env = _eb_env()
    conn = psycopg2.connect(
        host=env["RDS_HOSTNAME"], port=env["RDS_PORT"], dbname=env["RDS_DB_NAME"],
        user=env["RDS_USERNAME"], password=env["RDS_PASSWORD"],
        connect_timeout=10, sslmode="require",
    )
    conn.set_session(readonly=True, autocommit=True)

    with conn.cursor() as cur:
        print("=== ALL public tables (sorted) ===")
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE' "
            "ORDER BY table_name"
        )
        for (t,) in cur.fetchall():
            print(f"  {t}")

        print("\n=== core_projects columns ===")
        cur.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='core_projects' "
            "ORDER BY ordinal_position"
        )
        for c, dt, n in cur.fetchall():
            print(f"  {c:30s}  {dt:25s}  null={n}")

        print("\n=== row counts on key tables ===")
        for t in ("core_invoices", "core_invoice_allocations", "core_projects",
                  "core_costing", "core_categories", "core_contacts",
                  "core_po_orders", "core_hc_claims", "core_hc_variation",
                  "core_quotes", "core_quote_allocations",
                  "core_hc_claim_allocations", "core_po_globals",
                  "auth_user", "django_session"):
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{t}"')
                (n,) = cur.fetchone()
                print(f"  {t:35s}  {n}")
            except psycopg2.Error as e:
                print(f"  {t}: error -> {e}")
                conn.rollback()

    conn.close()
    print("[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
