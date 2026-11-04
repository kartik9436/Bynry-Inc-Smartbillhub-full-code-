# ── Trace ──────────────────────────────────────────────
# Component: W0 migration helpers (vendor guard + db/ SQL loader)
# Contract:  B2 §3 (RLS applied per table by migration; policies live as SQL in
#            06-backend/db/) · config/settings/test.py (tests run sqlite — RLS and
#            partition DDL are Postgres-only and honestly skipped there; the live
#            assertions belong to the G5 isolation suite)
# Rules:     none enforced here — the laws live in the SQL files and migrations
#            this module loads and guards
# Tests:     06-backend/tests/test_be10_partitioning.py (vendor-guard behavior)
# Impacts:   every RLS/partition/extension migration in apps/*/migrations/
# ───────────────────────────────────────────────────────
"""Two tiny helpers so every W0 migration handles the two-vendor reality the
same way (LAW 0: one boring pattern, repeated).

PostgresOnlySQL — RunSQL that executes only on Postgres. The sqlite test
database gets the plain Django-created tables (constraint tests run there);
RLS ENABLE+FORCE, partitioning, triggers, and extensions are Postgres DDL and
would be a lie on sqlite. Skipping is HONEST and recorded: sqlite cannot
exercise RLS — those assertions stay in the G5 isolation suite against live
Postgres, per the W0 lane instructions.

load_db_sql — reads a SQL file from 06-backend/db/ so the policy text lives in
ONE reviewable place (B2 §3 / CLAUDE.md 🔒: RLS policy SQL in 06-backend/db/,
applied by migration) instead of being pasted into migration bodies.
"""

from pathlib import Path

from django.db import migrations

DB_SQL_DIR = Path(__file__).resolve().parent.parent / "db"


class PostgresOnlySQL(migrations.RunSQL):
    """RunSQL that is a no-op on any vendor except postgresql."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):  # type: ignore[no-untyped-def]
        if schema_editor.connection.vendor == "postgresql":
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):  # type: ignore[no-untyped-def]
        if schema_editor.connection.vendor == "postgresql":
            super().database_backwards(app_label, schema_editor, from_state, to_state)


def load_db_sql(filename: str) -> str:
    """The contents of 06-backend/db/<filename> — fails loudly if absent."""
    path = DB_SQL_DIR / filename
    return path.read_text(encoding="utf-8")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-001@b2ae555 (story+rules snapshot hash — W0 migrations lane)
# generated: 2026-08-09 by story-coder v1 (R1 critical path, W0 migrations)
# checklist: A✔ B=deferred(plumbing — the guarded laws live in migrations/SQL) C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ py_compile✔ pytest✔ · run_gates✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: sqlite cannot exercise RLS/partition DDL — Postgres-only ops skip there by design; live assertions = G5 isolation suite
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
