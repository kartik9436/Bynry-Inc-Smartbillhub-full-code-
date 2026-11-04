# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-TEN-9794 — the boot guard checked only the role's own flags,
#          never the LIVE tables, and honoured its escape hatches under the
#          production settings module (DEF-RAT-9791's production half).
# Rules:   CLAUDE.md hard rule 1 · hard-won laws 3 (fail closed) and 7
# ───────────────────────────────────────────────────────
"""What a production boot now refuses, proved both ways.

1. Under `config.settings.production` neither escape hatch is honoured: a
   bypassing role refuses to start even with SBH_ALLOW_RLS_BYPASSING_ROLE=1 or
   RLS_ALLOW_BYPASSING_ROLE=True, and the refusal says the hatch was ignored.
2. A tenant table without ENABLE, FORCE or its tenant policy refuses a
   production boot, naming the table; elsewhere it is one warning line.
3. On a real PostgreSQL 16 the migrated schema has NO unprotected tenant table
   (so a healthy production boots), and a table stripped of FORCE is named.
"""

import io

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

from core import rls_guard
from tests.isolation_helpers import requires_postgres


class _Cursor:
    def __init__(self, one=None, many=None):
        self._one, self._many = one, many

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *a, **kw):
        return None

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _Conn:
    vendor = "postgresql"

    def __init__(self, role_row, table_rows):
        self._role_row, self._table_rows = role_row, table_rows

    def cursor(self):
        # The guard asks the role first (fetchone), then the tables (fetchall).
        return _Cursor(one=self._role_row, many=self._table_rows)


HEALTHY_TABLES = [("charges", True, True, True), ("tenants", False, False, False)]
STRIPPED_TABLES = [("charges", True, False, True), ("taxes", False, False, False)]
ENFORCED_ROLE = ("sbh_app", False, False, [])
BYPASS_ROLE = ("sbh_app", False, True, [])


@pytest.fixture()
def production(settings, monkeypatch):
    # Both: a second `settings.X = …` override starts a fresh holder whose
    # SETTINGS_MODULE is None, and the guard then falls back to the environment.
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", rls_guard.PRODUCTION_SETTINGS_MODULE)
    settings.SETTINGS_MODULE = rls_guard.PRODUCTION_SETTINGS_MODULE
    return settings


def test_tc1__under_production_neither_hatch_is_honoured(production, monkeypatch):
    monkeypatch.setenv(rls_guard.BYPASS_ESCAPE_HATCH_ENV, "1")
    production.RLS_ALLOW_BYPASSING_ROLE = True
    assert rls_guard.bypass_is_tolerated() == (False, "")


def test_tc2__a_bypassing_role_refuses_a_production_boot_even_with_the_hatch_typed(
    production, monkeypatch
):
    monkeypatch.setenv(rls_guard.BYPASS_ESCAPE_HATCH_ENV, "1")
    with pytest.raises(ImproperlyConfigured) as refused:
        rls_guard.enforce_at_startup(_Conn(BYPASS_ROLE, HEALTHY_TABLES), stream=io.StringIO())
    text = str(refused.value)
    assert rls_guard.REFUSAL_HEADLINE in text
    assert "NOT honoured" in text and "IGNORED" in text


def test_tc3__outside_production_the_hatch_still_works(settings, monkeypatch):
    settings.SETTINGS_MODULE = "config.settings.local"
    monkeypatch.setenv(rls_guard.BYPASS_ESCAPE_HATCH_ENV, "1")
    out = io.StringIO()
    rls_guard.enforce_at_startup(_Conn(BYPASS_ROLE, HEALTHY_TABLES), stream=out)
    assert "TOLERATED" in out.getvalue()


def test_tc4__an_unprotected_tenant_table_refuses_a_production_boot_naming_it(production):
    with pytest.raises(ImproperlyConfigured) as refused:
        rls_guard.enforce_at_startup(_Conn(ENFORCED_ROLE, STRIPPED_TABLES), stream=io.StringIO())
    text = str(refused.value)
    assert rls_guard.TABLE_REFUSAL_HEADLINE in text
    assert "charges (no FORCE)" in text
    assert "taxes (no ENABLE, no FORCE, no tenant policy)" in text


def test_tc5__outside_production_an_unprotected_table_is_one_warning_line(settings):
    settings.SETTINGS_MODULE = "config.settings.local"
    out = io.StringIO()
    rls_guard.enforce_at_startup(_Conn(ENFORCED_ROLE, STRIPPED_TABLES), stream=out)
    assert "⚠ 2 of 2 tenant table(s) are NOT protected" in out.getvalue()


def test_tc6__a_healthy_production_boot_prints_both_lines_and_starts(production):
    out = io.StringIO()
    rls_guard.enforce_at_startup(_Conn(ENFORCED_ROLE, HEALTHY_TABLES), stream=out)
    lines = out.getvalue()
    assert "RLS is enforced on this connection" in lines
    assert "1 tenant table(s) carry ENABLE + FORCE" in lines
    assert "tenants" in lines  # the exemption is named, not silent


@requires_postgres
@pytest.mark.django_db
def test_tc7__the_migrated_schema_has_no_unprotected_tenant_table_and_a_stripped_one_is_named():
    verdict = rls_guard.read_table_verdict(connection)
    assert verdict.checked and verdict.checked > 100, verdict
    assert verdict.unprotected == (), verdict.one_line()
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE charges NO FORCE ROW LEVEL SECURITY")
    stripped = rls_guard.read_table_verdict(connection)
    assert stripped.unprotected == ("charges (no FORCE)",), stripped.one_line()
