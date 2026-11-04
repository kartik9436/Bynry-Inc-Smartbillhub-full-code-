# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) TC-RBS-7 — CR-075 wave A task A7: the tenant
#           isolation fixture, on real PostgreSQL.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS FORCE is on; no cross-tenant queryset) ·
#           hard rule 6 (idempotency by a UNIQUE index) · hard-won law 14 (the
#           suite is SQLite, which cannot hold these guarantees) · hard-won law
#           7 (a check that cannot fail is the defect)
# Tests:    this file — the four manual RLS probes over all seven tables, and
#           the idempotency index proved on the vendor that will run it
# Impacts:  apps/runbooks/migrations/0002_rls_force.py · 0001_initial.py
# ───────────────────────────────────────────────────────
"""US-RBS-041 on PostgreSQL — the guarantees SQLite cannot hold, and does not.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_us_rbs_041_pg.py

⚠ **WHY THIS FILE EXISTS SEPARATELY, IN ONE SENTENCE:** `config/settings/test.py`
hardcodes in-memory SQLite, **SQLite has no row-level security at all**, and a
tenant-isolation test that runs there proves exactly nothing while reporting
green. `G5` once ran the isolation suite on SQLite and **called 192 skips a
pass** — the failure this repository names *a check that cannot fail*. Every
case here carries `requires_postgres` and SKIPS on the default suite rather than
passing vacuously (hard-won law 14).

⚠ **AND IT RUNS UNDER THE NON-SUPERUSER PROBE ROLE**
(`tests/isolation_helpers.py`), because the connected role may BYPASS row
security: a green obtained under a superuser would be a green over a guarantee
that was never tested. The probe self-verifies — `assert_is_a_real_proof` fails
rather than skips when the role can bypass — so this file cannot silently
degrade into the thing it exists to catch.

WHAT IT WOULD HAVE PROVED ON SQLITE: nothing. Every case below either skips
there, or (the idempotency one, which is in the sibling file) tests a constraint
rather than a policy. The difference is the point.
"""

import pytest
from django.db import DatabaseError, connection, transaction

from apps.runbooks import models
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

SEVEN = models.TENANT_TABLES


def _seed(tenant, *, key: str) -> dict:
    """One row in every one of the seven tables, for one tenant.

    ⚠ **THE FIXTURE MUST WRITE INTO ALL SEVEN OR THE PROBE IS VACUOUS.** An
    `UPDATE … WHERE tenant_id = <owner>` on a table where the owner has no rows
    matches nothing, succeeds, and raises nothing — which reads in the failure
    output exactly like *the policy let a cross-tenant write through*
    (`DEF-PAY-4054`'s triage cost an hour on that distinction). The helpers
    check the row count first; this function is what makes that check pass for
    the right reason.
    """
    runbook = models.Runbook.objects.create(
        tenant=tenant,
        key=key,
        name="Can we bill?",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="tenant",
        unit_of_work="tenant",
        timezone="America/Chicago",
        gate_mode="approve_each_run",
    )
    version = models.RunbookVersion.objects.create(
        tenant=tenant, runbook=runbook, version=1, definition={"steps": []}
    )
    run = models.RunbookRun.objects.create(
        tenant=tenant, runbook=runbook, version=1, status=models.RUN_STATUS_DONE
    )
    record = models.RunbookRunRecord.objects.create(
        tenant=tenant,
        run=run,
        subject_type="account",
        planned_action="report",
        idempotency_key=f"{key}-record-1",
    )
    item = models.WorkItem.objects.create(
        tenant=tenant,
        source_kind=models.WORK_ITEM_SOURCE_FINDING,
        source_run=run,
        fingerprint=f"{key}-no-read-since-18-aug",
        title="No read since 18 Aug",
        status="open",
    )
    plan = models.CutoverPlan.objects.create(tenant=tenant, name=f"{key} go-live", status="open")
    plan_item = models.CutoverPlanItem.objects.create(
        tenant=tenant, plan=plan, seq=1, title="Load the trial balance", status="open"
    )
    return {
        "runbooks": runbook,
        "runbook_versions": version,
        "runbook_runs": run,
        "runbook_run_records": record,
        "work_items": item,
        "cutover_plans": plan,
        "cutover_plan_items": plan_item,
    }


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_041_tc_rbs_7_with_no_tenant_in_context_all_seven_are_empty(rls, brazos, dana):
    """Probe 1 — deny by default. `app.tenant_id` unset means NOTHING is visible.

    `NULLIF(current_setting('app.tenant_id', true), '')::uuid` is NULL when the
    setting is unset or empty, the policy predicate is NULL, and no row of any
    of the seven is readable or writable. That is the whole of hard rule 1 for
    this module, and it is asserted under a role RLS applies to.
    """
    with live_tenant_context(brazos.id):
        _seed(brazos, key="brazos-can-we-bill")
    assert_denied_without_context(rls, *SEVEN)


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_041_tc_rbs_7_one_tenants_rows_vanish_under_another(
    rls, brazos, lonestar, dana, erin
):
    """Probe 2 — Brazos Bend's seven rows are invisible to Lone Star Ridge.

    Asserted table by table THROUGH THE DATABASE, with the app-layer filter
    deliberately out of the path: what is being tested is the policy, not the
    queryset.
    """
    with live_tenant_context(brazos.id):
        _seed(brazos, key="brazos-can-we-bill")
    with live_tenant_context(lonestar.id):
        _seed(lonestar, key="lonestar-can-we-bill")
    for table in SEVEN:
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar, min_owner_rows=1)


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_041_tc_rbs_7_no_foreign_row_is_reachable_from_either_side(
    rls, brazos, lonestar, dana, erin
):
    """Probe 3 — under one tenant's context, not one row of the other exists.

    The mirror of probe 2, and it runs BOTH ways: a policy that scopes reads in
    one direction and not the other is a leak that a one-sided test reports as
    healthy.
    """
    with live_tenant_context(brazos.id):
        _seed(brazos, key="brazos-can-we-bill")
    with live_tenant_context(lonestar.id):
        _seed(lonestar, key="lonestar-can-we-bill")
    assert_no_foreign_rows_anywhere(rls, brazos, SEVEN)
    assert_no_foreign_rows_anywhere(rls, lonestar, SEVEN)


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_041_tc_rbs_7_a_write_stamped_for_another_tenant_is_refused(
    rls, brazos, lonestar, dana, erin
):
    """Probe 4 — the policy's WITH CHECK refuses a row stamped for someone else.

    Re-stamping one of Brazos Bend's own visible rows with Lone Star Ridge's
    `tenant_id` is the table-agnostic form of *"INSERT carrying another tenant's
    id"*: USING lets the UPDATE find the row and WITH CHECK rejects the result.
    The refusal must come from row-level security and not from some other
    constraint, and the helper asserts that in the message.

    ⚠ **SIX OF THE SEVEN. `runbook_versions` IS REFUSED BY SOMETHING STRICTER
    THAT FIRES FIRST, AND THAT IS ASSERTED RATHER THAN SKIPPED (`CR-075` wave E,
    `migrations/0003`).** A version row is APPEND-ONLY: `BR-RBS-038` says a run
    pins the version that produced it and its stored plan and report never
    change, so a `BEFORE UPDATE` trigger refuses **every** UPDATE — including
    this one, and before PostgreSQL ever evaluates the policy's `WITH CHECK`.
    The isolation guarantee is not weakened by that; it is reached one layer
    earlier and by a rule that admits no exceptions at all.

    **So the table keeps an assertion instead of losing one.** Dropping it from
    the loop and saying nothing would leave a lane reading *six tables* and
    wondering which one was quietly excused — a declared blind spot with no
    number beside it, which is the shape `G32` reported 0 unresolved keys over
    21 live refusals with. What is asserted here is that the cross-tenant write
    is REFUSED and that the sentence names the rule that refused it.
    """
    append_only = "runbook_versions"
    with live_tenant_context(brazos.id):
        _seed(brazos, key="brazos-can-we-bill")
    checked = 0
    for table in SEVEN:
        if table == append_only:
            continue
        message = assert_write_into_other_tenant_refused(
            rls, table, owner=brazos, intruder=lonestar
        )
        assert "row-level security" in message
        checked += 1
    assert checked == len(SEVEN) - 1 == 6, "six by policy, one by the append-only trigger"

    # The seventh, refused one layer earlier and by name.
    with live_tenant_context(brazos.id):
        message = rls.refused(
            f"UPDATE {append_only} SET tenant_id = %s WHERE tenant_id = %s",
            [str(lonestar.id), str(brazos.id)],
        )
    assert "BR-RBS-038" in message, (
        f"{append_only}: the cross-tenant write was refused, but not by the "
        f"append-only rule — {message}"
    )


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_041_force_is_on_not_merely_enable(brazos):
    """`FORCE`, not just `ENABLE` — the half a table owner would otherwise skip.

    `ENABLE ROW LEVEL SECURITY` does not apply to the table's OWNER, and the
    application's migration role frequently is the owner. `relforcerowsecurity`
    is the column that says the guarantee holds for everyone, and it is read
    here rather than assumed because a comment claiming a guarantee is not the
    guarantee (hard-won law 1).
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = ANY(%s)",
            [list(SEVEN)],
        )
        rows = {name: (enabled, forced) for name, enabled, forced in cursor.fetchall()}
    assert set(rows) == set(SEVEN), f"missing from pg_class: {set(SEVEN) - set(rows)}"
    for table, (enabled, forced) in sorted(rows.items()):
        assert enabled, f"{table}: row level security is not ENABLED"
        assert forced, f"{table}: RLS is enabled but not FORCED — the table owner bypasses it"


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_041_the_idempotency_index_is_a_real_index_on_postgres(brazos, dana):
    """Hard rule 6 — the refusal comes from the DATABASE, concurrently safe.

    ⚠ It asserts the INDEX and says nothing about how the key is COMPOSED. That
    contradicts itself across our own documents (`DEF-RBS-4246`) and is
    `OQ-RBS-1737`, open: `BR-RBS-008` says *runbook + run + record + action
    kind* and three other statements — including `TC-RBS-4`'s **248 notices, not
    496** — need the run out of it. **The index is correct under every candidate
    answer**, which is why it is laid in wave A and the composition is not.
    """
    with live_tenant_context(brazos.id):
        seeded = _seed(brazos, key="brazos-can-we-bill")
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                models.RunbookRunRecord.objects.create(
                    tenant=brazos,
                    run=seeded["runbook_runs"],
                    subject_type="account",
                    planned_action="report",
                    idempotency_key="brazos-can-we-bill-record-1",
                )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-041 (EP-RBS-01; CR-075 wave A task A7, TC-RBS-7)
# generated: 2026-09-06 by the CR-075 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H✔(proves migrations/0002_rls_force)
# gates: pytest tests/test_us_rbs_041_pg.py on PostgreSQL 16 under the
#        non-superuser probe role · SKIPS on the default SQLite suite, and that
#        skip is the honest answer rather than a pass
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
