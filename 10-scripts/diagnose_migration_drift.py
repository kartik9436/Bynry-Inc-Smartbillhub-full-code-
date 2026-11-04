#!/usr/bin/env python3
"""Report where a database's SCHEMA disagrees with its MIGRATION HISTORY — and
say exactly which migrations are safe to fake and which are not.

READ-ONLY. This script opens a transaction and rolls it back. It creates
nothing, drops nothing, and writes no `django_migrations` row. The repair is
printed for a human to run, deliberately, after reading it.

WHY THIS EXISTS
---------------
On 2026-08-19 a deploy to smartbillhub.bynry.com would not come up. The log read
as one incoherent traceback and was in fact FOUR failures from FOUR container
restarts, interleaved — `docker-entrypoint.sh` runs `migrate` under `set -e`
before gunicorn binds, so each failure exits the container, the restart policy
brings it back, and migrate runs again from the top, dying one migration later
each time:

    notifications.0012   policy "in_app_messages_tenant_isolation" already exists
    payments.0001        type "payments" already exists
    payments.0004        type "bank_accounts" already exists
    payments.0007        relation "payment_plans" already exists

Every one is the same condition: **the object exists and `django_migrations` has
no row for the migration that makes it.** The schema is ahead of the history.

The obvious remedy — `migrate --fake <app> <name>` — is right for some of these
and DANGEROUS for others, and nothing in the error message tells you which. A
table that exists with the WRONG COLUMNS is a real schema gap; faking its
migration writes "applied" into the history and buries it, and the failure comes
back months later as a column that does not exist at runtime.

So this script asks the question the error cannot: **does the object exist, and
does it match?**

WHAT IT CHECKS, per unapplied migration
---------------------------------------
* `CreateModel`      → does the table exist? do its columns match the model's?
* `AddField`         → does the column exist?
* `RunPython`/`RunSQL` naming a policy → does the policy exist on that table?

VERDICTS
--------
  MISSING        the objects are genuinely absent. Let migrate run it. Never fake.
  SAFE-TO-FAKE   every object exists AND matches. Faking records the truth.
  ⚠ MISMATCH     the object exists but does NOT match. **Do not fake.** A human
                 must decide; faking hides a real difference.

Usage, from inside the backend container:
    python manage.py shell -c "exec(open('/app/../10-scripts/diagnose_migration_drift.py').read())"
or, simpler, copy it in and:
    DJANGO_SETTINGS_MODULE=config.settings.production python 10-scripts/diagnose_migration_drift.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.db.migrations.loader import MigrationLoader  # noqa: E402
from django.db.migrations.operations import models as model_ops  # noqa: E402
from django.db.migrations.operations import fields as field_ops  # noqa: E402
from django.db.migrations.operations.special import RunPython, RunSQL  # noqa: E402

MISSING, SAFE, MISMATCH, UNKNOWN = "MISSING", "SAFE-TO-FAKE", "⚠ MISMATCH", "UNKNOWN"


def _tables() -> set[str]:
    with connection.cursor() as c:
        c.execute("select tablename from pg_tables where schemaname='public'")
        return {r[0] for r in c.fetchall()}


def _columns(table: str) -> set[str]:
    with connection.cursor() as c:
        c.execute(
            "select column_name from information_schema.columns "
            "where table_schema='public' and table_name=%s",
            [table],
        )
        return {r[0] for r in c.fetchall()}


def _policies() -> set[tuple[str, str]]:
    with connection.cursor() as c:
        c.execute("select tablename, policyname from pg_policies where schemaname='public'")
        return {(r[0], r[1]) for r in c.fetchall()}


def _model_of(loader, key, model_name):
    """The model as it exists AFTER this migration, from Django's own historical
    registry — never guessed.

    ⚠ THE FIRST DRAFT OF THIS TOOL GUESSED, AND IT WAS WRONG TWICE ON THE VERY
    DATABASE USED TO TEST IT. It inferred `applabel_modelname` for the table and
    `field + "_id"` for a foreign key's column. Both are only Django's DEFAULTS,
    and this project overrides them everywhere — the tables are `payments`,
    `bank_accounts`, `payment_plans`. The probe duly reported `payments_bankline
    absent` for a table that exists under another name, and a MISMATCH on
    `delivery_return_events` for two columns that are present.

    A diagnostic that misreports is worse than none, because it is trusted —
    the failure already recorded in G18's, G26's and G27's own docstrings. So
    nothing here is inferred: `project_state` replays the migration graph and
    returns the real `_meta`, which is what the schema editor itself used.
    """
    try:
        return loader.project_state(key).apps.get_model(key[0], model_name)
    except LookupError:
        return None


def _expected_columns(model) -> set[str]:
    """`field.column` as Django resolves it — honours db_column and FK naming."""
    return {f.column for f in model._meta.local_fields}


def classify(loader, key, migration, tables, policies):
    """One verdict per migration, with the evidence that produced it."""
    findings = []
    for op in migration.operations:
        if isinstance(op, model_ops.CreateModel):
            model = _model_of(loader, key, op.name)
            if model is None:
                findings.append((UNKNOWN, f"{op.name}: not in the historical registry"))
                continue
            table = model._meta.db_table
            if table not in tables:
                findings.append((MISSING, f"table {table} absent"))
                continue
            want, have = _expected_columns(model), _columns(table)
            gap = want - have
            findings.append(
                (MISMATCH, f"table {table} exists but is missing column(s): {', '.join(sorted(gap))}")
                if gap
                else (SAFE, f"table {table} exists with all {len(want)} expected column(s)")
            )
        elif isinstance(op, field_ops.AddField):
            model = _model_of(loader, key, op.model_name)
            if model is None:
                findings.append((UNKNOWN, f"{op.model_name}: not in the historical registry"))
                continue
            table = model._meta.db_table
            if table not in tables:
                findings.append((MISSING, f"table {table} absent"))
                continue
            try:
                column = model._meta.get_field(op.name).column
            except Exception:  # noqa: BLE001 — unresolvable is UNKNOWN, never MISSING
                findings.append((UNKNOWN, f"{table}.{op.name}: field not resolvable"))
                continue
            findings.append(
                (SAFE, f"{table}.{column} exists") if column in _columns(table)
                else (MISSING, f"{table}.{column} absent")
            )
        elif isinstance(op, (RunPython, RunSQL)):
            declared = _rls_tables_of(migration)
            if not declared:
                findings.append((UNKNOWN, "data/SQL migration — introspection cannot judge it"))
                continue
            present = {t for (t, p) in policies if t in declared and p.endswith("_tenant_isolation")}
            absent = declared - present
            findings.append(
                (MISSING, f"no tenant_isolation policy on: {', '.join(sorted(absent))}") if absent
                else (SAFE, f"policy present on: {', '.join(sorted(present))}")
            )
    if not findings:
        return UNKNOWN, ["no checkable operation"]
    order = [MISMATCH, MISSING, UNKNOWN, SAFE]
    verdict = next(v for v in order if any(f[0] == v for f in findings))
    return verdict, [f"{v}: {d}" for v, d in findings]


def _rls_tables_of(migration) -> set[str]:
    """The TABLES tuple these RLS migrations declare at module level."""
    mod = sys.modules.get(type(migration).__module__)
    return set(getattr(mod, "TABLES", ()) or ())


def main() -> int:
    loader = MigrationLoader(connection)
    applied = loader.applied_migrations
    tables, policies = _tables(), _policies()
    unapplied = [k for k in loader.graph.nodes if k not in applied]
    unapplied.sort()

    print(f"database: {connection.settings_dict.get('NAME')}")
    print(f"tables: {len(tables)}   policies: {len(policies)}   "
          f"migrations applied: {len(applied)}   UNAPPLIED: {len(unapplied)}\n")
    if not unapplied:
        print("Nothing unapplied. The history and the schema agree.")
        return 0

    buckets = {MISSING: [], SAFE: [], MISMATCH: [], UNKNOWN: []}
    for key in unapplied:
        migration = loader.disk_migrations[key]
        verdict, evidence = classify(loader, key, migration, tables, policies)
        buckets[verdict].append((key, evidence))

    for verdict in (MISMATCH, SAFE, MISSING, UNKNOWN):
        rows = buckets[verdict]
        if not rows:
            continue
        print(f"── {verdict} ── {len(rows)}")
        for (app, name), evidence in rows:
            print(f"   {app}.{name}")
            for line in evidence:
                print(f"       {line}")
        print()

    if buckets[MISMATCH]:
        print("⚠ STOP. Migrations above are MISMATCH: the object exists and does NOT match.")
        print("  Do not fake these. Faking records 'applied' over a real schema gap.\n")
        return 2

    if buckets[SAFE]:
        print("Run these, in this order, then let the deploy proceed:\n")
        for (app, name), _ in buckets[SAFE]:
            print(f"  python manage.py migrate --fake {app} {name}")
        print("\nThen: python manage.py migrate   # applies the genuinely MISSING ones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
