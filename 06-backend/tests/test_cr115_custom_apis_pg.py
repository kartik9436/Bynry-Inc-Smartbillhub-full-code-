# ── Trace ──────────────────────────────────────────────
# Story:   CR-115-BRC05 §7.6 — *"The rows are PER UTILITY … Two utilities on
#          the same connector configure it independently"*.
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id`; RLS FORCE is on) · B2 §3 (the signed policy
#          template) · hard-won law 14 (SQLite cannot hold this guarantee, so
#          these SKIP there rather than passing vacuously) · law 7 (`G5` ran
#          the isolation suite on sqlite and called 192 skips a pass).
# ───────────────────────────────────────────────────────
"""`integration_api` under RLS — the half SQLite cannot prove, on PostgreSQL.

⚠ **THE SQLITE SUITE PROVES THE APPLICATION FILTER AND CALLS IT ISOLATION, AND
IT IS NOT.** `tests/test_cr115_custom_apis.py` asserts that one utility's rows
do not reach another's screen, which is true and is a statement about a
`WHERE` clause a lane could delete. The guarantee hard rule 1 actually makes is
the DATABASE's: with no `app.tenant_id` set, no row of this table is readable or
writable by anyone, the owner included (`FORCE`). That is only testable where
RLS exists.

⚠ **IT RUNS UNDER A PROBE ROLE, NOT AS THE OWNER, AND THAT DISTINCTION HAS
ALREADY COST THIS REPO THREE WEEKS** (hard-won law 7's *incapable of passing*):
the isolation fixture once demanded `ALTER ROLE … NOSUPERUSER`, which only a
superuser may issue — and a superuser bypasses the very policies the suite
exists to test. `tests/isolation_helpers.py` owns that arrangement now and this
file uses it rather than rebuilding one.

RUN IT (it SKIPS under the pinned test settings, which hardcode in-memory
SQLite and ignore `DATABASE_URL` — CLAUDE.md law 14):

    DATABASE_URL="postgres://…/<db>?sslmode=disable" \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    pytest tests/test_cr115_custom_apis_pg.py
"""

from __future__ import annotations

import pytest

from apps.integrations import custom_apis, gis, models
from apps.integrations import services as integration_services
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin

TABLE = "integration_api"
LAYER = "https://gis.brazosbend.example/addr"


def _connected(actor, tenant, url=LAYER):
    with live_tenant_context(tenant.id):
        return integration_services.connect(
            actor=actor,
            tenant_id=tenant.id,
            provider_key=gis.PROVIDER_KEY,
            environment=models.ENVIRONMENT_PRODUCTION,
            config={"base_url": url},
            cadence=models.CADENCE_NIGHTLY,
        )


@requires_postgres
@pytest.mark.django_db
def test_the_table_is_named_in_tenant_tables_so_the_probe_walks_it():
    """⚠ **A TABLE NOTHING WALKS IS A TABLE NOTHING PROVES.**

    `models.TENANT_TABLES` is what the isolation probe, the gates and the RLS
    migration all read, and its own comment says a table added without being
    named there *"is a table nothing proves"*. This case exists so that the
    seventh cannot quietly be the first one nobody checks.
    """
    assert TABLE in models.TENANT_TABLES


@requires_postgres
@pytest.mark.django_db
def test_with_no_tenant_context_not_one_row_is_reachable(rls, brazos, dana):
    """Deny by default — hard rule 1, measured rather than asserted in prose.

    With `app.tenant_id` unset, `NULLIF(…, '')::uuid` is NULL, the policy
    predicate is NULL, and the row is invisible and unwritable to every role
    including the owner.
    """
    connection = _connected(dana, brazos)
    with live_tenant_context(brazos.id):
        custom_apis.add(
            actor=dana, connection=connection,
            kind=custom_apis.KIND_ADDRESS_LOOKUP,
            name="Address points", url="https://points.brazosbend.example/addr",
        )
    assert_denied_without_context(rls, TABLE)


@requires_postgres
@pytest.mark.django_db
def test_one_utilitys_rows_vanish_under_another_utilitys_context(
    rls, brazos, lonestar, dana, erin
):
    """§7.6 — *"Two utilities on the same connector configure it
    independently"*, proved BELOW the application.

    Both tenants connect the SAME connector, which is the case that matters:
    an application filter keyed on `provider_key` would pass a test where the
    two used different connectors and leak on this one.
    """
    ours = _connected(dana, brazos)
    _connected(erin, lonestar)
    with live_tenant_context(brazos.id):
        row = custom_apis.add(
            actor=dana, connection=ours,
            kind=custom_apis.KIND_ADDRESS_LOOKUP,
            name="Ours only", url="https://points.brazosbend.example/addr",
        )
    assert_rls_scoped(rls, TABLE, owner=brazos, intruder=lonestar, owner_ids={str(row.id)})
    assert_no_foreign_rows_anywhere(rls, lonestar, [TABLE])


@requires_postgres
@pytest.mark.django_db
def test_a_write_into_another_utilitys_rows_is_refused_by_the_policy(
    rls, brazos, lonestar, dana
):
    """The WITH CHECK half. A policy that only filters reads lets a caller
    write a row it can then never see — which reads as success."""
    connection = _connected(dana, brazos)
    with live_tenant_context(brazos.id):
        custom_apis.add(
            actor=dana, connection=connection,
            kind=custom_apis.KIND_ADDRESS_LOOKUP,
            name="Ours only", url="https://points.brazosbend.example/addr",
        )
    assert_write_into_other_tenant_refused(rls, TABLE, owner=brazos, intruder=lonestar)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-115-BRC05 §7.6 + CLAUDE.md hard rule 1 + B2 §3
# generated: 2026-09-17 by the CR-115-BRC05 per-API lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=deferred(🔒 migration row in 09-human-review-ledger.md)
# gates: pytest tests/test_cr115_custom_apis_pg.py on PostgreSQL 16 (SKIPS on the pinned SQLite settings — law 14)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
