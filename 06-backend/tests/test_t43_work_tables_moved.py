# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 T-43 — the six Work tables move from
#           `apps/metering/connections.py` to `apps/work/connection_models.py`
#           (`04-docs/05-modules/16-work/03-field-map.md` §4).
# Rules:    BR-WRK-001/002 · CLAUDE.md hard rule 1 (no policy moved) · hard-won
#           law 7 (all five cases were run RED on the pre-move branch tip —
#           5 failed — before they were trusted green)
# Impacts:  apps/work/migrations/0046_t43_take_the_six_work_tables.py ·
#           apps/metering/migrations/0078_t43_release_the_six_work_tables.py
# ───────────────────────────────────────────────────────
"""The move is a MODEL-STATE move: the classes and the migration state changed
owner, and nothing reached the database.

What these cases pin, so a later edit cannot quietly undo it:

  * the six models are registered under `work`, with the table names they
    always had, and `metering` declares none of them;
  * both T-43 migrations are `SeparateDatabaseAndState` with an EMPTY
    `database_operations` — a plain `DeleteModel` in metering would DROP six
    tables with every row and policy;
  * the order is create-in-work THEN delete-from-metering;
  * `apps/metering/connections.py` declares no model class any more, and the
    one name it re-exports for migration history (`DISPATCH_STATES`, read by
    `metering/0050`) still resolves.

The PostgreSQL half — rows, `pg_class` identity, RLS flags and policies
identical before and after `migrate` — was measured by the T-43 lane on
PostgreSQL 16 and is recorded in `03-field-map.md` §4; it is not repeated
here because it needs a populated database from BEFORE the move.
"""

from __future__ import annotations

import ast
from importlib import import_module
from pathlib import Path

from django.apps import apps
from django.db import migrations

SIX = {
    "Connection": "connections",
    "ConnectionService": "connection_services",
    "WorkOrder": "work_orders",
    "WorkOrderTemplate": "work_order_templates",
    "ServiceCharacteristic": "service_characteristics",
    "ConnectionTodo": "connection_todos",
}
BACKEND = Path(__file__).resolve().parents[1]
WORK_MIGRATION = "apps.work.migrations.0046_t43_take_the_six_work_tables"
METERING_MIGRATION = "apps.metering.migrations.0078_t43_release_the_six_work_tables"


def test_t43_the_six_are_work_models_on_their_old_tables():
    for name, table in SIX.items():
        model = apps.get_model("work", name)
        assert model._meta.app_label == "work"
        assert model._meta.db_table == table, f"{name} must keep the table {table}"
        assert model.__module__ == "apps.work.connection_models"
    metering_names = {m.__name__ for m in apps.get_app_config("metering").get_models()}
    assert not (metering_names & set(SIX)), f"metering still declares {metering_names & set(SIX)}"


def test_t43_every_foreign_key_into_the_six_points_at_work():
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if field.is_relation and field.concrete and field.related_model is not None:
                if field.related_model.__name__ in SIX:
                    assert field.related_model._meta.app_label == "work", (
                        f"{model._meta.label}.{field.name} points at {field.related_model._meta.label}"
                    )


def _only_operation(module_path: str) -> migrations.SeparateDatabaseAndState:
    migration = import_module(module_path).Migration
    assert len(migration.operations) == 1
    op = migration.operations[0]
    assert isinstance(op, migrations.SeparateDatabaseAndState)
    return op


def test_t43_both_migrations_touch_no_table():
    work = _only_operation(WORK_MIGRATION)
    metering = _only_operation(METERING_MIGRATION)
    assert work.database_operations == []
    assert metering.database_operations == []
    created = {op.name for op in work.state_operations if isinstance(op, migrations.CreateModel)}
    assert created == set(SIX)
    for op in work.state_operations:
        if isinstance(op, migrations.CreateModel):
            assert op.options["db_table"] == SIX[op.name]
    deleted = {op.name for op in metering.state_operations if isinstance(op, migrations.DeleteModel)}
    assert deleted == set(SIX)


def test_t43_create_in_work_comes_before_delete_from_metering():
    deps = import_module(METERING_MIGRATION).Migration.dependencies
    assert ("work", "0046_t43_take_the_six_work_tables") in deps
    work_deps = import_module(WORK_MIGRATION).Migration.dependencies
    assert not any(app == "metering" and name.startswith("0078") for app, name in work_deps)


def test_t43_connections_py_declares_no_model_and_keeps_the_migration_name():
    source = (BACKEND / "apps/metering/connections.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes = [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and any("Model" in ast.unparse(b) for b in node.bases)
    ]
    assert classes == [], f"connections.py declares model classes again: {classes}"
    from apps.metering.connections import DISPATCH_STATES  # what metering/0050 imports
    from apps.work.connection_models import DISPATCH_STATES as home

    assert DISPATCH_STATES is home
