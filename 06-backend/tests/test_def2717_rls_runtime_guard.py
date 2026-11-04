# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2717 (2026-08-31) — every published CR-051 figure was measured on
#           a connection that bypassed RLS, because the benchmark's role had been
#           made SUPERUSER to create a database. DEF-2760 — the repo does not
#           record which role a deployment connects as.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE) · hard-won law 1
#           (a comment claiming a guarantee is not the guarantee) · law 2 (built
#           is not wired) · law 3 (defaults fail closed) · law 14 (the suite runs
#           on SQLite, so anything asserted about RLS must be proved on Postgres)
# Guards:   06-backend/core/rls_guard.py · config/wsgi.py · docker-entrypoint.sh
#           · apps/tenancy/apps.py · 10-scripts/gates/g56_rls_runtime_guard.py
# ───────────────────────────────────────────────────────
"""DEF-2717 — is the RUNNING application actually subject to row-level security?

WHAT THIS FILE IS FOR, AND WHY IT IS NOT PART OF THE G5 ISOLATION SUITE
------------------------------------------------------------------------
The G5 suite proves the POLICIES EXIST and are correct. It does so under a
dedicated `sbh_rls_probe` role (NOLOGIN NOSUPERUSER NOBYPASSRLS) precisely
because the app's own role may be a superuser — `tests/isolation_helpers.py`
argues that at length and is right to.

⚠ **That leaves exactly one question unasked, and it is the one DEF-2717
answered the hard way: is the connection the APPLICATION serves on subject to
those policies?** A superuser bypasses row-level security unconditionally,
FORCE included. Nothing observable changes — `relrowsecurity` and
`relforcerowsecurity` both still read `t`, the policies still exist, every query
still returns plausible rows — and one tenant reads another's data in silence.
Before `core/rls_guard.py`, `rolsuper`/`rolbypassrls` appeared ZERO times in
`apps/`, `config/` and `core/`.

⚠ **LAW 14 GOVERNS HOW THIS FILE IS WRITTEN.** `config/settings/test.py`
hardcodes in-memory SQLite, and **SQLite has no row-level security at all**, so
an RLS assertion made in the default suite cannot fail and must never be written
as though it could. This file is therefore in two halves:

  * **Vendor-independent** (runs everywhere, including the SQLite suite): the
    verdict's four states and, critically, that the two "we could not tell"
    states are never rendered as a pass. That conflation IS the defect, one
    layer up, so it is asserted where every run will see it.
  * **`@requires_postgres`** (skipped on SQLite, and a skip is NOT a pass): the
    verdict read from a real `pg_roles` agrees with `pg_roles`.

The live three-role proof — NOSUPERUSER sees 2 rows, SUPERUSER sees 3, BYPASSRLS
sees 3, same table, same policy, same `app.tenant_id`, on PostgreSQL 16.13 — is
recorded in `core/rls_guard.py`'s docstring and in the decision log. It needs
three roles and a CREATE ROLE grant, so it is not reproduced as a unit test; what
IS reproduced here is that the guard reports each of those roles correctly.
"""

import subprocess
from pathlib import Path

import pytest
from django.db import connection

from core import rls_guard
from core.rls_guard import RlsRuntimeStatus, read_runtime_verdict

from tests.isolation_helpers import requires_postgres  # noqa: F401

BACKEND = Path(__file__).resolve().parent.parent
REPO = BACKEND.parent


# ── shims: the four states, without needing four real databases ─────────────
class _FakeConn:
    """Django's connection surface, reduced to what the guard actually touches."""

    def __init__(self, vendor, row=None, raises=None):
        self.vendor = vendor
        self._row = row
        self._raises = raises

    def cursor(self):
        if self._raises is not None:
            raise self._raises
        return _FakeCursor(self._row)


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *a, **kw):
        return None

    def fetchone(self):
        return self._row


def _pg(rolname="sbh_app", rolsuper=False, rolbypassrls=False, memberships=()):
    return _FakeConn("postgresql", row=(rolname, rolsuper, rolbypassrls, list(memberships)))


# ── the states ──────────────────────────────────────────────────────────────
def test_def2717_tc1__a_plain_role_is_reported_enforced():
    v = read_runtime_verdict(_pg())
    assert v.status is RlsRuntimeStatus.ENFORCED
    assert v.bypasses is False
    assert "sbh_app" in v.one_line()


def test_def2717_tc2__a_superuser_is_reported_bypassed():
    """rolsuper alone bypasses. This is DEF-2717's exact shape."""
    v = read_runtime_verdict(_pg(rolname="smartbillhub", rolsuper=True))
    assert v.status is RlsRuntimeStatus.BYPASSED
    assert v.bypasses is True
    assert "rolsuper=t" in v.one_line()


def test_def2717_tc3__a_bypassrls_role_is_reported_bypassed():
    """BYPASSRLS without superuser bypasses just as completely, and a check that
    looked only for `rolsuper` would report this role healthy."""
    v = read_runtime_verdict(_pg(rolbypassrls=True))
    assert v.status is RlsRuntimeStatus.BYPASSED
    assert v.bypasses is True
    assert "rolbypassrls=t" in v.one_line()


def test_def2717_tc4__sqlite_is_not_applicable_and_is_not_a_pass():
    """⚠ THE ASSERTION THIS WHOLE FILE EXISTS FOR (law 14).

    The default suite runs on SQLite, which has no RLS. The guard must say so BY
    NAME and must not report `bypasses=False` as though it had proved something —
    "we could not tell" rendered as "it is fine" is DEF-2717's mechanism repeated.
    """
    v = read_runtime_verdict(_FakeConn("sqlite"))
    assert v.status is RlsRuntimeStatus.NOT_APPLICABLE
    assert v.status is not RlsRuntimeStatus.ENFORCED
    assert "not a pass" in v.one_line().lower()


def test_def2717_tc5__an_unreachable_database_is_unknown_and_is_not_a_pass():
    v = read_runtime_verdict(_FakeConn("postgresql", raises=RuntimeError("Connection refused")))
    assert v.status is RlsRuntimeStatus.UNREACHABLE
    assert v.status is not RlsRuntimeStatus.ENFORCED
    assert "not a pass" in v.one_line().lower()


def test_def2717_tc6__a_missing_pg_roles_row_is_unknown_not_healthy():
    """CURRENT_USER with no pg_roles row should be impossible. The impossible is
    reported as unknown, never as enforced."""
    v = read_runtime_verdict(_FakeConn("postgresql", row=None))
    assert v.status is RlsRuntimeStatus.UNREACHABLE


def test_def2717_tc7__membership_in_a_bypassing_role_is_warned_not_refused():
    """One `SET ROLE` from a bypass — worth saying, not worth refusing on. The
    RDS master user the runbook blesses (09-infra/02 §8.0) is this shape."""
    v = read_runtime_verdict(_pg(memberships=("rds_superuser",)))
    assert v.status is RlsRuntimeStatus.ENFORCED
    assert v.bypassing_memberships == ("rds_superuser",)
    assert "SET ROLE" in v.one_line()


# ── the escape hatch: law 3, the unsafe option is the one you type ──────────
def test_def2717_tc8__bypass_is_not_tolerated_by_default(settings, monkeypatch):
    monkeypatch.delenv(rls_guard.BYPASS_ESCAPE_HATCH_ENV, raising=False)
    settings.RLS_ALLOW_BYPASSING_ROLE = False
    tolerated, who = rls_guard.bypass_is_tolerated()
    assert tolerated is False, "a bypassing role must not be tolerated by default"
    assert who == ""


def test_def2717_tc9__the_env_escape_hatch_must_be_typed(monkeypatch):
    monkeypatch.setenv(rls_guard.BYPASS_ESCAPE_HATCH_ENV, "1")
    tolerated, who = rls_guard.bypass_is_tolerated()
    assert tolerated is True
    assert rls_guard.BYPASS_ESCAPE_HATCH_ENV in who


def test_def2717_tc10__the_settings_escape_hatch_names_itself(settings, monkeypatch):
    monkeypatch.delenv(rls_guard.BYPASS_ESCAPE_HATCH_ENV, raising=False)
    settings.RLS_ALLOW_BYPASSING_ROLE = True
    tolerated, who = rls_guard.bypass_is_tolerated()
    assert tolerated is True
    assert "RLS_ALLOW_BYPASSING_ROLE" in who


def test_def2717_tc11__base_settings_fail_closed():
    """base.py must leave the allow-flag False so EVERY settings module refuses by
    inheritance — the same two-key shape as FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS."""
    text = (BACKEND / "config" / "settings" / "base.py").read_text(encoding="utf-8")
    assert "RLS_ALLOW_BYPASSING_ROLE = False" in text, (
        "base.py no longer fails closed on a bypassing role (hard-won law 3)"
    )
    prod = (BACKEND / "config" / "settings" / "production.py").read_text(encoding="utf-8")
    assert "RLS_ALLOW_BYPASSING_ROLE = True" not in prod, (
        "production.py tolerates a bypassing role — hard rule 1 would be unenforced"
    )


# ── the refusal ─────────────────────────────────────────────────────────────
def test_def2717_tc12__a_bypassing_role_refuses_to_start(settings, monkeypatch):
    from django.core.exceptions import ImproperlyConfigured

    monkeypatch.delenv(rls_guard.BYPASS_ESCAPE_HATCH_ENV, raising=False)
    settings.RLS_ALLOW_BYPASSING_ROLE = False
    with pytest.raises(ImproperlyConfigured) as exc:
        rls_guard.enforce_at_startup(_pg(rolsuper=True))
    message = str(exc.value)
    assert rls_guard.REFUSAL_HEADLINE in message
    # The refusal must be actionable by somebody who has never read the module.
    assert "NOSUPERUSER NOBYPASSRLS" in message
    assert rls_guard.BYPASS_ESCAPE_HATCH_ENV in message


def test_def2717_tc13__a_tolerated_bypass_still_says_so_every_boot(settings, monkeypatch, capsys):
    """A tolerated bypass that goes SILENT is how DEF-2717 happened."""
    monkeypatch.setenv(rls_guard.BYPASS_ESCAPE_HATCH_ENV, "1")
    rls_guard.enforce_at_startup(_pg(rolsuper=True))
    printed = capsys.readouterr().err
    assert "RLS IS NOT ENFORCED" in printed
    assert "TOLERATED" in printed


def test_def2717_tc14__an_enforced_connection_also_prints_its_role(capsys):
    """The ENFORCED line beside a published figure is what tells a later reader
    which world the number came from — the half of DEF-2717 a refusal alone
    would not have fixed."""
    rls_guard.enforce_at_startup(_pg(rolname="sbh_app"))
    assert "sbh_app" in capsys.readouterr().err


# ── law 2: built is not wired ───────────────────────────────────────────────
def test_def2717_tc15__the_guard_is_wired_into_every_boot_path():
    """Four callers, checked as text because that is what a merge can see. The
    gate g56 asserts the same thing; this fails in the suite as well so a lane
    running only pytest still learns."""
    wsgi = (BACKEND / "config" / "wsgi.py").read_text(encoding="utf-8")
    assert "rls_guard.enforce_at_startup()" in wsgi, "gunicorn's own module no longer checks"

    entry = (BACKEND / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert "rls_guard" in entry, "the container entrypoint no longer checks"

    apps_py = (BACKEND / "apps" / "tenancy" / "apps.py").read_text(encoding="utf-8")
    assert "check_runtime_rls_enforcement" in apps_py, "the system check is no longer registered"


def test_def2717_tc16__the_system_check_is_registered_with_django():
    from django.core.checks.registry import registry

    names = {
        getattr(c, "__name__", "")
        for c in registry.get_checks(include_deployment_checks=True)
    }
    assert "check_runtime_rls_enforcement" in names, (
        "apps/tenancy/apps.py no longer registers the DEF-2717 system check — it is "
        "dead code, and `manage.py migrate` would stop asking (hard-won law 2)"
    )


def test_def2717_tc17__the_system_check_errors_on_a_bypassing_role(settings, monkeypatch):
    monkeypatch.delenv(rls_guard.BYPASS_ESCAPE_HATCH_ENV, raising=False)
    settings.RLS_ALLOW_BYPASSING_ROLE = False
    monkeypatch.setattr(rls_guard, "read_runtime_verdict", lambda *a, **k: read_runtime_verdict(_pg(rolsuper=True)))
    results = rls_guard.check_runtime_rls_enforcement()
    assert [r.id for r in results] == ["core.E001"]
    assert results[0].is_serious()


def test_def2717_tc18__the_system_check_is_silent_on_sqlite(monkeypatch):
    """It must not turn the whole SQLite suite red — there is nothing to assert."""
    monkeypatch.setattr(
        rls_guard, "read_runtime_verdict", lambda *a, **k: read_runtime_verdict(_FakeConn("sqlite"))
    )
    assert rls_guard.check_runtime_rls_enforcement() == []


# ── the live half — a skip here is NOT a pass ───────────────────────────────
@requires_postgres
@pytest.mark.django_db
def test_def2717_tc19__the_verdict_agrees_with_pg_roles():
    """Read the database, not the code (hard-won law 1). Whatever this role IS,
    the guard must report it correctly — the test asserts agreement, not a
    particular privilege, because dev boxes legitimately differ."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = CURRENT_USER"
        )
        rolname, rolsuper, rolbypassrls = cursor.fetchone()

    v = read_runtime_verdict(connection)
    assert v.role == rolname
    assert v.rolsuper is bool(rolsuper)
    assert v.rolbypassrls is bool(rolbypassrls)
    assert v.bypasses is (bool(rolsuper) or bool(rolbypassrls))
    assert v.status is (
        RlsRuntimeStatus.BYPASSED if v.bypasses else RlsRuntimeStatus.ENFORCED
    )


@requires_postgres
@pytest.mark.django_db
def test_def2717_tc20__the_shipped_entrypoint_block_is_syntactically_runnable():
    """The entrypoint's check is a heredoc, so nothing type-checks it. `sh -n`
    at least proves the script still parses with the block in it."""
    result = subprocess.run(
        ["sh", "-n", str(BACKEND / "docker-entrypoint.sh")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"docker-entrypoint.sh does not parse: {result.stderr}"
