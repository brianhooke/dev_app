"""Compare what 0048-0080 will try to ADD/CREATE vs what's already in RDS.

Scans each migration file's `operations` symbolically (via Django's
state framework) and emits a list of conflicts.

Read-only.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running from anywhere (script dir is .../scripts, repo root is parent).
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import django


def main() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dev_app.settings.local")
    django.setup()

    from django.db import connection
    from django.db.migrations.loader import MigrationLoader

    loader = MigrationLoader(connection)
    graph = loader.graph

    with connection.cursor() as cur:
        cur.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema='public'"
        )
        existing_cols = set()
        for tbl, col in cur.fetchall():
            existing_cols.add((tbl, col))
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE'"
        )
        existing_tables = {r[0] for r in cur.fetchall()}

    print(f"[info] {len(existing_tables)} tables, {len(existing_cols)} columns in RDS")

    project_state = loader.project_state(at_end=False)

    def model_table(app_label: str, model_name: str) -> str | None:
        try:
            ms = project_state.models[(app_label, model_name.lower())]
            return ms.options.get("db_table") or f"{app_label}_{model_name.lower()}"
        except KeyError:
            return None

    print("\n=== Conflicts predicted ===\n")

    for key in sorted(graph.leaf_nodes()):
        pass

    seen = set()
    plan = loader.graph.forwards_plan(("core", "0080_po_orders_status_field"))
    applied = loader.applied_migrations
    for app_name, mig_name in plan:
        if app_name != "core":
            continue
        if (app_name, mig_name) in applied:
            continue
        if (app_name, mig_name) in seen:
            continue
        seen.add((app_name, mig_name))
        mig = loader.graph.nodes[(app_name, mig_name)]
        for op in mig.operations:
            cls = op.__class__.__name__
            if cls == "AddField":
                tbl = model_table(app_name, op.model_name)
                if not tbl or tbl not in existing_tables:
                    continue
                col = op.field.db_column or op.name
                if op.field.is_relation and not op.field.db_column:
                    col = f"{op.name}_id"
                if (tbl, col) in existing_cols:
                    print(f"  CONFLICT  {mig_name}: AddField {op.model_name}.{op.name} -> {tbl}.{col} ALREADY EXISTS")
            elif cls == "CreateModel":
                ms_options = op.options or {}
                tbl = ms_options.get("db_table") or f"{app_name}_{op.name.lower()}"
                if tbl in existing_tables:
                    # Verify column-level shape vs the migration definition
                    expected_cols = []
                    for fname, fobj in op.fields:
                        col = fobj.db_column or fname
                        if fobj.is_relation and not fobj.db_column:
                            col = f"{fname}_id"
                        expected_cols.append(col)
                    actual = {c for (t, c) in existing_cols if t == tbl}
                    missing = set(expected_cols) - actual
                    extra = actual - set(expected_cols)
                    print(f"  CONFLICT  {mig_name}: CreateModel {op.name} -> table {tbl} ALREADY EXISTS")
                    print(f"            expected cols ({len(expected_cols)}): {expected_cols}")
                    print(f"            actual cols ({len(actual)}): {sorted(actual)}")
                    if missing:
                        print(f"            MISSING: {sorted(missing)}")
                    if extra:
                        print(f"            EXTRA: {sorted(extra)}")
            elif cls == "RemoveField":
                tbl = model_table(app_name, op.model_name)
                if not tbl:
                    continue
                col_candidates = [op.name, f"{op.name}_id"]
                hits = [c for c in col_candidates if (tbl, c) in existing_cols]
                if not hits and tbl in existing_tables:
                    print(f"  WARNING   {mig_name}: RemoveField {op.model_name}.{op.name} -> column NOT IN SCHEMA, will fail unless faked")
            elif cls == "DeleteModel":
                tbl = model_table(app_name, op.name)
                if tbl and tbl not in existing_tables:
                    print(f"  WARNING   {mig_name}: DeleteModel {op.name} -> table {tbl} NOT IN SCHEMA, will fail unless faked")
        # apply this migration's state changes to project_state for the next iteration
        for op in mig.operations:
            try:
                op.state_forwards(app_name, project_state)
            except Exception:
                pass

    print("\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
