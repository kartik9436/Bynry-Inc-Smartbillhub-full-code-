# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-IDN-9748 — identity/0009 moves every existing field technician
#          login from `both` to `mobile` (the phone only), per utility.
# Rules:   BR-WRK-043 / OQ-WRK-1494 (PO 2026-09-04) · CLAUDE.md hard rule 1
#          (never touch a tenant table without `app.tenant_id`; FORCE RLS) ·
#          hard-won laws 7 and 14 (a superuser and SQLite are the two places
#          the per-tenant bug cannot exist).
# ───────────────────────────────────────────────────────
"""identity/0009, called through its OWN function against the live registry.

The SQLite cases prove WHO is moved; the PostgreSQL case proves it as a role
row-level security applies to, with the production default (the nil UUID) in
`app.tenant_id` — the `DEF-RAT-5799` / `DEF-IDN-7504` trap, where one query
across every tenant finds nothing and prints a zero.

    DATABASE_URL=postgres://… pytest --ds=config.settings.pgtest tests/test_def_idn_9748_migration.py

WHAT WOULD MAKE THIS PASS WRONGLY: a filter that moves everyone — so office
logins and a deliberately web-only technician are in the fixture and must stay
put; and a count nobody reads — so the printed figure is asserted.
"""

from __future__ import annotations

import re
from importlib import import_module

import pytest
from django.apps import apps as live_apps
from django.db import connection

from apps.identity.models import User
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    requires_postgres,
    rls,
    rls_probe_role,
    writing_as_tenant,
)
from tests.test_us_idn_helpers import idn  # noqa: F401 (fixture import)

pytestmark = pytest.mark.django_db

MIGRATION = "apps.identity.migrations.0009_def_idn_9748_technicians_to_the_field_app"
NIL_TENANT = "00000000-0000-0000-0000-000000000000"


class _SchemaEditorStub:
    connection = connection


def _run(capsys) -> tuple[str, int]:
    import_module(MIGRATION).technicians_to_the_field_app(live_apps, _SchemaEditorStub())
    printed = capsys.readouterr().out
    match = re.search(r"DEF-IDN-9748 \(per tenant\): (\d+) field technician", printed)
    assert match, printed
    return printed, int(match.group(1))


def _scope(user) -> str:
    with writing_as_tenant(user.tenant):
        return User.objects.get(pk=user.pk).surface_scope


def _set_scope(user, scope):
    with writing_as_tenant(user.tenant):
        User.objects.filter(pk=user.pk).update(surface_scope=scope)


@pytest.fixture()
def world(idn):
    """Two utilities. In each: a technician on the default `both` (moved), and
    office logins (untouched). Silver Creek also holds a technician already on
    `mobile` and one somebody deliberately scoped `web` (both untouched)."""
    users = idn.seed_silvercreek()
    tech, _ = idn.make_user(
        idn.silvercreek,
        "tech@silvercreek.example",
        "Tess Line",
        password="Prairie2026grass",
        role="field_technician",
    )
    on_phone, _ = idn.make_user(
        idn.silvercreek,
        "phone@silvercreek.example",
        "Pat Phone",
        password="Prairie2026grass",
        role="field_technician",
    )
    web_tech, _ = idn.make_user(
        idn.silvercreek,
        "webtech@silvercreek.example",
        "Wes Web",
        password="Prairie2026grass",
        role="field_technician",
    )
    mesa_admin, _ = idn.seed_bluemesa_admin()
    mesa_tech, _ = idn.make_user(
        idn.bluemesa,
        "tech@bluemesa.example",
        "Mo Field",
        password="Prairie2026grass",
        role="field_technician",
    )
    _set_scope(on_phone, "mobile")
    _set_scope(web_tech, "web")
    for u in (tech, mesa_tech, users.alex, users.priya, mesa_admin):
        assert _scope(u) == "both"
    idn.rows.clear()
    return idn, users, tech, on_phone, web_tech, mesa_admin, mesa_tech


def test_moves_only_technicians_on_both_in_every_utility(world, capsys):
    idn, users, tech, on_phone, web_tech, mesa_admin, mesa_tech = world
    printed, moved = _run(capsys)

    assert _scope(tech) == "mobile"
    assert _scope(mesa_tech) == "mobile"
    assert _scope(on_phone) == "mobile"
    assert _scope(web_tech) == "web", "a deliberate web scope was overwritten"
    for office in (users.alex, users.priya, users.diana, mesa_admin):
        assert _scope(office) == "both", f"office login {office.email} was moved"
    assert moved == 2, printed

    rows = idn.rows_for("user.surface_scope_changed")
    assert sorted(str(r["entity_id"]) for r in rows) == sorted([str(tech.id), str(mesa_tech.id)])
    for row in rows:
        assert row["before"] == {"surface_scope": "both"}
        assert row["after"] == {"surface_scope": "mobile"}
        assert row["actor_user_id"] is None  # BR-AUD-003's unnamed system job


def test_running_it_twice_moves_nobody_the_second_time(world, capsys):
    _run(capsys)
    printed, moved = _run(capsys)
    assert moved == 0, printed


def test_reverse_is_a_noop_on_purpose():
    """Reversing would re-open the web door against the PO's ruling; `noop`
    keeps `migrate identity 0008` working without doing that."""
    from django.db import migrations

    (operation,) = import_module(MIGRATION).Migration.operations
    assert operation.reverse_code is migrations.RunPython.noop


@requires_postgres
@pytest.mark.isolation
def test_moves_technicians_as_a_role_rls_applies_to(world, rls, capsys):
    idn, users, tech, on_phone, web_tech, mesa_admin, mesa_tech = world
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [NIL_TENANT])
        cursor.execute(f'SET ROLE "{rls.role}"')
        cursor.execute(
            "SELECT current_user, (SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user)"
        )
        who, bypasses = cursor.fetchone()
    assert who == rls.role and not bypasses, (who, bypasses)
    try:
        # The trap this migration is written against: with the nil UUID in the
        # GUC, a role RLS binds sees NO technician at all from a global query.
        assert User.objects.filter(email="tech@silvercreek.example").count() == 0
        printed, moved = _run(capsys)
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            (left_behind,) = cursor.fetchone()
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")

    assert left_behind == NIL_TENANT, "the GUC was not restored to its arrival value"
    assert moved == 2, printed
    assert _scope(tech) == "mobile"
    assert _scope(mesa_tech) == "mobile"
    assert _scope(web_tech) == "web"
    assert _scope(users.priya) == "both"
    rows = idn.rows_for("user.surface_scope_changed")
    assert sorted(str(r["tenant_id"]) for r in rows) == sorted(
        [str(idn.silvercreek.id), str(idn.bluemesa.id)]
    )
