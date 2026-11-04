# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-032 TC-5 (tenant isolation on the order's own copies) ·
#           US-WRK-033 TC-6. The 🔒 file under review is
#           `apps/work/migrations/0013_rls_force_order_copies.py`
#           (review-ledger row, CR-070 wave H task H4)
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE is on) · B2 §3 (ENABLE + FORCE
#           with USING/WITH CHECK on `tenant_id`) · BR-WRK-008 · hard-won
#           law 14 (the suite runs on SQLite, which has NO row-level security)
#           · law 7 (proved RED first)
# Tests:    this file — skipped on SQLite BY DESIGN, and the skip is the point
# ───────────────────────────────────────────────────────
"""The order's six copy tables under real row-level security, on PostgreSQL.

WHY A SEPARATE FILE, AND WHY THE GATE IS NOT THE PROOF
------------------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite. **SQLite has no
row-level security of any kind**, so an isolation assertion in the ordinary
suite is green whether the policies exist or not — hard-won law 14's shape one
rule along.

⚠ **AND THE TENANT-ISOLATION GATE IS NOT THE PROOF EITHER, WHICH IS NEW TODAY.**
`DEF-GOV-4024` (2026-09-05) records that the gate runs the isolation suite
WITHOUT pointing it at PostgreSQL, so it inherits the same SQLite: **46 of 238
proofs run, 192 skip, and it exits 0.** A lane reading that green as evidence
its tables are isolated would be reading the absence of a database as a pass.
So this file is run DIRECTLY against real PostgreSQL and its result is quoted
in the review-ledger row rather than the gate's.

    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/sbh_dev"
    pytest tests/test_us_wrk_032_copies_pg.py

AND WHY IT ASSERTS UNDER A PROBE ROLE
--------------------------------------
PostgreSQL exempts SUPERUSER and BYPASSRLS roles from row-level security
**unconditionally, `FORCE` included**, and the development role is a superuser
(`DEF-2717`). So the reads run inside `SET ROLE sbh_rls_probe` and
`assert_is_a_real_proof()` FAILS — never skips — if that role could bypass.

WHAT THESE SIX TABLES HOLD, WHICH IS WHY THE POLICY IS NOT ROUTINE
-------------------------------------------------------------------
`work_order_details` holds a GATE CODE and access notes for one address.
`work_order_safety` and `work_order_tasks` say who was at that address and at
what minute they ticked each step. `work_order_readings` holds the meter
serials and the numbers taken off them. Read across a tenant boundary that is
another utility's customers' entry codes and a schedule of when their houses
were visited.

⚠ **AND A WRITE ACROSS THE BOUNDARY IS WORSE THAN A READ, FOR A REASON
`BR-WRK-008` CREATES.** Deleting another tenant's `work_order_safety` row
removes a safety step from a job in progress, and **nothing downstream
re-checks it against the template** — because not re-checking it IS the rule.
The copy is the only record. Nothing about the resulting job looks wrong.
"""

from __future__ import annotations

import pytest

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

#: The six tables `work/0012` creates and `work/0013` protects — the order's
#: own copy of its template (`BR-WRK-008`).
COPY_TABLES = (
    "work_order_details",
    "work_order_safety",
    "work_order_tasks",
    "work_order_materials",
    "work_order_readings",
    "work_order_help",
)


@requires_postgres
def test_work_0013_every_copy_table_is_enabled_AND_forced(brazos):
    """`ENABLE` is half the guarantee; `FORCE` is the half that binds the owner.

    Read out of `pg_class` rather than out of the migration file, because what
    is asserted is the state of the DATABASE — a migration that ran, a policy
    somebody dropped by hand and a policy that was never written all look
    identical in the source tree (hard-won law 1).
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(%s) ORDER BY c.relname",
            [list(COPY_TABLES)],
        )
        found = {name: (enabled, forced) for name, enabled, forced in cursor.fetchall()}
    assert set(found) == set(COPY_TABLES), f"missing tables: {set(COPY_TABLES) - set(found)}"
    wrong = {name: flags for name, flags in found.items() if flags != (True, True)}
    assert wrong == {}, (
        "CLAUDE.md hard rule 1 / B2 §3: every order-copy table needs ENABLE *and* "
        f"FORCE ROW LEVEL SECURITY — {wrong}"
    )


@requires_postgres
def test_work_0013_with_no_tenant_context_all_six_return_nothing(brazos, rls):
    """Deny by default, stated as the behaviour a person can check.

    `NULLIF(current_setting('app.tenant_id', true), '')::uuid` is NULL when
    nothing set it, `tenant_id = NULL` is NULL, and NULL is not TRUE — so no
    row is visible and none may be written, without the error the older
    `::uuid` form raised (`DEF-639`).
    """
    assert_denied_without_context(rls, *COPY_TABLES)


@requires_postgres
def test_work_0013_one_tenants_checklist_is_invisible_to_the_other(brazos, lonestar, dana, rls):
    """`US-WRK-032` TC-5 — the DATABASE's own refusal, not the handler's.

    `checklist()`'s `filter(tenant_id=…)` is deliberately not in this path, so
    what passes here is the policy rather than the application layer agreeing
    with itself.
    """
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        _raise(dana, brazos, tid)
    for table in COPY_TABLES:
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)


@requires_postgres
def test_work_0013_a_write_stamped_for_another_tenant_is_refused(brazos, lonestar, dana, rls):
    """The `WITH CHECK` half — and on these six it is the half that matters.

    A row INSERTED under another utility's order changes what a technician is
    shown to do on a live job: a safety step added, a reading removed. Because
    `BR-WRK-008` says the copy is the record, nothing anywhere re-derives it
    from the template, so nothing would ever notice.

    ⚠ **THE ORDER IS RAISED FIRST, AND THAT IS NOT SETUP TIDINESS
    (2026-09-05).** This case used to assert straight into
    `assert_write_into_other_tenant_refused` with all six tables EMPTY. That
    helper re-stamps one of the owner's own rows with the intruder's
    `tenant_id`; with no rows the UPDATE matches nothing, raises nothing, and
    the assertion reported `DID NOT RAISE DatabaseError` — which is
    indistinguishable in the output from *the policy let a cross-tenant write
    through*. One reads as a vacuous fixture and the other as a
    production-severity leak. The helper now proves the owner HAS a row before
    concluding anything, so the six tables are given the rows a real order
    leaves in them.
    """
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        _raise(dana, brazos, tid)
    for table in COPY_TABLES:
        assert_write_into_other_tenant_refused(rls, table, owner=brazos, intruder=lonestar)
