# ── Trace ──────────────────────────────────────────────
# Change:  Settings → Security redesign, APPROVED by the PO 2026-09-29 — the
#          Audit log card's tenant isolation, PROVED ON POSTGRESQL.
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id`; RLS FORCE is on) · BR-AUD-007 (every audit read
#          tenant-scoped) · hard-won law 14 (the unit suite hardcodes
#          in-memory SQLite) · law 7 (a probe over a row that was never
#          written prints the same PASS)
# Tests:   this file — SKIPPED on SQLite BY DESIGN, and the skip is the point.
# ───────────────────────────────────────────────────────
"""THE CARD CANNOT SHOW ANOTHER UTILITY'S HISTORY, ON A REAL DATABASE.

Run it against real PostgreSQL — the whole line, because a header that omits
`JOBS_EAGER=false` costs an hour (`DEF-567`):

    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/smartbillhub?sslmode=disable"
    pytest tests/test_security_redesign_audit_card_pg.py

⚠ **WHY THE APP-TIER CASE IS NOT ENOUGH.** `test_security_redesign_audit_card
.py` proves the QUERYSET filters by tenant, on SQLite, where row-level
security does not exist. That is the convenience half. The law is RLS, and
the only place it can be shown is here.

⚠ **AND THE PROBE MUST RUN AS A ROLE RLS APPLIES TO.** PostgreSQL exempts
SUPERUSER and BYPASSRLS roles unconditionally, `FORCE` included, and the
development role on this container IS a superuser (`rolsuper = t`) — so a
case written the obvious way passes by FINDING the other utility's row
through a bypass and calling that a pass. The `rls` fixture reads `rolsuper`
and `rolbypassrls` out of `pg_roles` and FAILS rather than skips if the probe
could bypass anything; `assert_rls_scoped` then asserts through the database
with the app-layer filter deliberately out of the path.

⚠ **BOTH ROWS ARE PLANTED AND EACH IS PROVED VISIBLE FROM ITS OWN SEAT
FIRST.** A probe reporting *cannot see it* over a row that was never written
prints exactly the same PASS as a probe reporting a policy that works.
`min_owner_rows` is passed explicitly for that reason, and the seats are
SWAPPED so the pair is proved in both directions rather than in one lucky
one.
"""

from __future__ import annotations

import pytest

from apps.audit import services as audit_services
from apps.identity import selectors
from apps.identity.seams import audit_seam
from core import audit as core_audit
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_idn_helpers import idn  # noqa: F401 (fixture import)

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

TABLE = "audit_log"


@pytest.fixture()
def card_env(idn):
    """`idn`, with the audit trail actually written to the database."""
    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    try:
        yield idn
    finally:
        core_audit.set_audit_sink(previous)


def _write_change(tenant, *, before, after):
    """One `settings.security_updated` row, through the sanctioned writer.

    ⚠ `write_row` is used rather than `save_security_policy` because what is
    being probed is the TRAIL, not the save: the row has to exist under a
    known tenant with a known pair, and the service's role gate and
    self-lockout guard are somebody else's test.
    """
    with live_tenant_context(tenant.id):
        core_audit.write_row(
            action=audit_seam.SECURITY_POLICY_ACTION,
            entity_type="security_policy",
            entity_id=None,
            actor_user_id=None,
            before=before,
            after=after,
        )


@requires_postgres
def test_audit_log_is_enabled_AND_forced(card_env):
    """`ENABLE` is half the guarantee; `FORCE` is the half that binds the
    OWNER — and the deployment's migrating role owns these tables.

    Read out of `pg_class`, because a migration that ran, a policy somebody
    dropped by hand and a policy that was never written all look identical in
    the source tree.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [TABLE],
        )
        row = cursor.fetchone()

    assert row is not None, f"{TABLE} does not exist"
    enabled, forced = row
    assert enabled, f"{TABLE}: row-level security is not ENABLED"
    assert forced, f"{TABLE}: FORCE is off, so the table owner bypasses the policy"


@requires_postgres
def test_with_no_tenant_context_the_trail_answers_nothing(card_env, rls):
    """Cleared context must deny EVERYTHING, never expose everything."""
    assert_denied_without_context(rls, TABLE)


@requires_postgres
def test_one_utilitys_security_history_is_invisible_to_another(card_env, rls):
    _write_change(
        card_env.silvercreek, before={"lockout_minutes": 15}, after={"lockout_minutes": 30}
    )
    _write_change(card_env.bluemesa, before={"lockout_minutes": 15}, after={"lockout_minutes": 45})

    assert_rls_scoped(
        rls, TABLE, owner=card_env.silvercreek, intruder=card_env.bluemesa, min_owner_rows=1
    )
    assert_rls_scoped(
        rls, TABLE, owner=card_env.bluemesa, intruder=card_env.silvercreek, min_owner_rows=1
    )


@requires_postgres
def test_the_card_itself_draws_only_its_own_utilitys_changes(card_env):
    """The seam and the renderer, end to end, under each utility's own GUC —
    the same question one layer up from the probe above."""
    _write_change(
        card_env.silvercreek, before={"lockout_minutes": 15}, after={"lockout_minutes": 30}
    )
    _write_change(card_env.bluemesa, before={"lockout_minutes": 15}, after={"lockout_minutes": 45})

    with live_tenant_context(card_env.silvercreek.id):
        silver = selectors.security_policy_audit_card(card_env.silvercreek.id)
    with live_tenant_context(card_env.bluemesa.id):
        mesa = selectors.security_policy_audit_card(card_env.bluemesa.id)

    assert [row["after"] for row in silver["rows"]] == [30]
    assert [row["after"] for row in mesa["rows"]] == [45]


@requires_postgres
def test_the_card_read_survives_the_monthly_partitioning(card_env):
    """`audit_log` is `PARTITION BY RANGE (created_at)` on PostgreSQL and a
    plain table on SQLite, so *"the read works"* is a different claim on each.
    A row written now lands in the current month's partition and the card
    must find it there."""
    _write_change(
        card_env.silvercreek,
        before={"session_timeout_minutes": 480},
        after={"session_timeout_minutes": 60},
    )
    with live_tenant_context(card_env.silvercreek.id):
        card = selectors.security_policy_audit_card(card_env.silvercreek.id)

    assert len(card["rows"]) == 1
    assert card["rows"][0]["actor"]["name"] == "Product upgrade"
    assert card["rows"][0]["before"] == 480
