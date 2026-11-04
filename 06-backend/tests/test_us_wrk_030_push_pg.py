# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-030 TC-5 (two tenants' pushes; neither dedupes the other).
#           The 🔒 file under review is
#           `apps/work/migrations/0015_rls_force_mobile.py`
#           (review-ledger row, CR-070 wave J task J6)
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE is on) · B2 §3 (ENABLE + FORCE
#           with USING/WITH CHECK on `tenant_id`) · BR-WRK-034 · hard-won
#           law 14 (the suite runs on SQLite, which has NO row-level security)
# Tests:    this file — skipped on SQLite BY DESIGN, and the skip is the point
# ───────────────────────────────────────────────────────
"""`technician_devices` under real row-level security, on PostgreSQL.

WHAT THIS TABLE HOLDS, WHICH IS WHY THE POLICY IS NOT ROUTINE
--------------------------------------------------------------
One row is **a live bearer credential that addresses a physical handset in a
named person's pocket.** Read across a tenant boundary, it is another utility's
technician's push token. **Written across one, it is worse:** it makes a
stranger's phone a delivery address for somebody else's jobs — a handset ringing
with another utility's customer's name, street and **gate code** — and nothing
anywhere would notice, because a push is fire-and-forget by design (there is no
delivery receipt in this schema, deliberately: `apps/work/push.py`).

So the `WITH CHECK` half is the half that matters here, and it is asserted
separately from the `USING` half rather than assumed to follow from it.

WHY A SEPARATE FILE, AND WHY THE GATE IS NOT THE PROOF
------------------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite. **SQLite has no row-level
security of any kind**, so an isolation assertion in the ordinary suite is green
whether the policy exists or not — hard-won law 14's shape, one rule along.

⚠ **AND THE TENANT-ISOLATION GATE IS NOT THE PROOF EITHER.** `DEF-GOV-4024`
(2026-09-05) records that it ran the isolation suite without pointing it at
PostgreSQL and therefore inherited SQLite — 46 of 238 proofs ran, 192 skipped,
exit 0. **On the machine this wave was built on it SKIPs for a second reason and
names it: the local `smartbillhub` role holds SUPERUSER, and PostgreSQL exempts
a superuser from row security unconditionally, `FORCE` included (`DEF-2717`).**
So this file was run BY HAND against real PostgreSQL 16 and its result is what
the review-ledger row quotes:

    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/sbh_wavej?sslmode=disable"
    pytest tests/test_us_wrk_030_push_pg.py

`rls_probe_role` enters `SET ROLE sbh_rls_probe` — NOLOGIN NOSUPERUSER
NOBYPASSRLS — and `assert_is_a_real_proof()` FAILS rather than skips if that
role could bypass. A green assertion made on the superuser connection would
prove nothing at all.
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

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

#: The one table `work/0014` creates and `work/0015` protects.
DEVICE_TABLES = ("technician_devices",)


def _a_device(tenant, email="ortiz@example.test", token="fxtr-ortiz-01"):
    """A technician of this tenant, with one registered handset."""
    from apps.identity import models as identity_models
    from apps.work import models as work_models

    user = identity_models.User.objects.create(
        tenant_id=tenant.id, email=email, full_name="D. Ortiz"
    )
    technician = work_models.Technician.objects.create(tenant_id=tenant.id, user=user)
    return work_models.TechnicianDevice.objects.create(
        tenant_id=tenant.id, technician=technician, token=token, platform="web"
    )


@requires_postgres
def test_work_0015_technician_devices_is_enabled_AND_forced(brazos):
    """`ENABLE` is half the guarantee; `FORCE` is the half that binds the OWNER.

    `ENABLE` alone exempts the table's owner, and the application's migration
    role owns every table in this schema — so without `FORCE` the policy is
    real and never consulted.

    Read out of `pg_class`, not out of the migration file: a migration that ran,
    a policy somebody dropped by hand and a policy that was never written all
    look identical in the source tree (hard-won law 1).
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(%s) ORDER BY c.relname",
            [list(DEVICE_TABLES)],
        )
        found = {name: (enabled, forced) for name, enabled, forced in cursor.fetchall()}
    assert set(found) == set(DEVICE_TABLES), f"missing: {set(DEVICE_TABLES) - set(found)}"
    wrong = {name: flags for name, flags in found.items() if flags != (True, True)}
    assert wrong == {}, (
        "CLAUDE.md hard rule 1 / B2 §3: `technician_devices` needs ENABLE *and* "
        f"FORCE ROW LEVEL SECURITY — {wrong}"
    )


@requires_postgres
def test_work_0015_with_no_tenant_context_nothing_is_visible(brazos, rls):
    """Deny by default, and without erroring on an unset GUC (`DEF-639`).

    `NULLIF(current_setting('app.tenant_id', true), '')::uuid` is NULL when
    nothing set it; `tenant_id = NULL` is NULL; NULL is not TRUE. So no row is
    visible and none may be written — which is also what keeps a fresh database
    buildable (`OQ-354`/`DEF-622`).
    """
    assert_denied_without_context(rls, *DEVICE_TABLES)


@requires_postgres
def test_work_0015_one_utilitys_phone_is_invisible_to_the_other(brazos, lonestar, rls):
    """**The sentence the review-ledger row puts to a person, proved.**

    *A phone's push token belongs to one technician of one utility; Lone Star
    Ridge cannot see or push to a Brazos Bend phone.*

    The application layer's own `filter(tenant_id=…)` is deliberately not in
    this path — `_active_devices` in `apps/work/push.py` is not called here — so
    what passes is the POLICY, not the application agreeing with itself.
    """
    with tenant_ctx(brazos):
        _a_device(brazos)
    for table in DEVICE_TABLES:
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)


@requires_postgres
def test_work_0015_a_device_stamped_for_another_tenant_is_refused(brazos, lonestar, rls):
    """The `WITH CHECK` half — **and on this table it is the half that matters.**

    A row INSERTED under another utility's tenant id makes a handset that
    utility does not own a delivery address for its jobs. The push path reads
    *this technician's active devices* and would address it; the audit line
    would read *pushed to phone* and be true. There is no delivery receipt to
    contradict it and nothing downstream re-checks who a token belongs to.

    ⚠ **THE DEVICE IS SEEDED HERE AND THE FIRST DRAFT DID NOT SEED IT**, which
    is worth the sentence because the failure is the one that looks most like a
    catastrophe. `assert_write_into_other_tenant_refused` re-stamps one of the
    owner's OWN rows with the intruder's `tenant_id`: `USING` lets the UPDATE
    find the row and `WITH CHECK` rejects the result. With no row to find, the
    UPDATE matches nothing, succeeds, and raises nothing — and the report reads
    **DID NOT RAISE DatabaseError**, which is indistinguishable from *the policy
    let a cross-tenant write through*. One is an empty fixture and the other is
    a production-severity leak. The helper's own docstring records an hour spent
    telling those apart on `work_order_details` on 2026-09-05 (`DEF-PAY-4054`
    triage), and it now asserts the owner has a row first — so this seeds one and
    the assertion means what it says.
    """
    with tenant_ctx(brazos):
        _a_device(brazos, email="ortiz-wc@example.test", token="fxtr-with-check-01")
    for table in DEVICE_TABLES:
        assert_write_into_other_tenant_refused(rls, table, owner=brazos, intruder=lonestar)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-030 (EP-WRK-05) · BR-WRK-034 · 10-execution-plan.md wave J task J6
# generated: 2026-09-05 by the CR-070 wave J build lane
# gates: run BY HAND on PostgreSQL 16 — see the module docstring for the exact command and why the isolation gate is not the proof on this machine
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
