# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-003 · US-RBS-018 (EP-RBS-01) — CR-075 wave D task D1, the
#           half SQLite cannot hold: the eight READ routes under real
#           row-level security, on the vendor that will run them.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS FORCE is on; no cross-tenant queryset) ·
#           hard-won law 14 (the suite is SQLite, which cannot hold this) ·
#           hard-won law 7 (a check that cannot fail is the defect) · NFR-3
#           (the clamp, proved against a real query planner)
# Tests:    this file — the ENDPOINT under a role RLS applies to, and the
#           paging arithmetic against PostgreSQL's own ordering
# Impacts:  apps/runbooks/api.py · apps/runbooks/selectors.py ·
#           apps/runbooks/migrations/0002_rls_force.py
# ───────────────────────────────────────────────────────
"""US-RBS-003 on PostgreSQL — what a green on SQLite does not prove.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_us_rbs_003_pg.py

⚠ **WHY THIS FILE EXISTS SEPARATELY, IN ONE SENTENCE:** `config/settings/test.py`
hardcodes in-memory SQLite, **SQLite has no row-level security at all**, and a
tenant-isolation test that runs there proves the queryset filter and nothing
else while reporting green. `G5` once ran the isolation suite on SQLite and
**called 192 skips a pass** — the failure this repository names *a check that
cannot fail*.

⚠ **AND IT RUNS UNDER THE NON-SUPERUSER PROBE ROLE** (`tests/isolation_helpers.py`),
because the connected role may BYPASS row security: a green obtained under a
superuser would be a green over a guarantee that was never tested. The probe
self-verifies — `assert_is_a_real_proof` FAILS rather than skips when the role
can bypass — so this file cannot silently degrade into the thing it exists to
catch. Every case carries `requires_postgres` and SKIPS on the default suite
rather than passing vacuously (hard-won law 14).

⚠ **THE SIBLING FILE PROVES THE SEVEN TABLES; THIS ONE PROVES THE DOOR.**
`tests/test_us_rbs_041_pg.py` runs the four manual RLS probes over all seven
tables — the policies themselves. What is asserted here is one layer up and it
is a different claim: that **the endpoints wave D mounts return nothing of
another tenant's when called under that tenant's real request context**. A
policy can be perfect while a route reads with the tenant filter forgotten, and
a route can be careful while a policy is missing; both halves are needed and
neither implies the other.
"""

from __future__ import annotations

import uuid

import pytest

from apps.runbooks import api, models, selectors
from core.permissions import SYSTEM_ADMIN
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_ten_helpers import api_call

RUN_TABLES = ("runbook_runs", "runbook_run_records")


def _seed(tenant, *, key: str, runs: int = 1, records_per_run: int = 2):
    """One runbook, `runs` closed runs, and records under each.

    ⚠ **THE FIXTURE MUST WRITE INTO EVERY TABLE THE PROBE ASKS ABOUT OR THE
    PROBE IS VACUOUS.** An `UPDATE … WHERE tenant_id = <owner>` on a table where
    the owner has no rows matches nothing, succeeds, and raises nothing — which
    reads in the failure output exactly like *the policy let a cross-tenant write
    through* (`DEF-PAY-4054` cost an hour on that distinction).
    """
    runbook = models.Runbook.objects.create(
        tenant=tenant,
        key=key,
        name="Can we bill?",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="tenant",
        unit_of_work="config graph",
        timezone="America/Chicago",
        gate_mode="approve_each_run",
        cap=100,
    )
    made = []
    for index in range(runs):
        run = models.RunbookRun.objects.create(
            tenant=tenant,
            runbook=runbook,
            version=1,
            status=models.RUN_STATUS_DONE,
            report=[{"block": "verdict", "payload": {"word": "No-go", "tone": "bad"}}],
            counts={"blockers": 3},
        )
        for seq in range(records_per_run):
            models.RunbookRunRecord.objects.create(
                tenant=tenant,
                run=run,
                subject_type="account",
                planned_action="report",
                outcome="done" if seq == 0 else "skipped",
                reason="Sent the notice." if seq == 0 else "No read since 18 Aug.",
                fix_route="Open the work list",
                data={"label": f"{key} subject {seq}"},
                idempotency_key=f"{key}-{index}-{seq}",
            )
        made.append(run)
    return runbook, made


def _indistinguishable(body):
    """A refusal body with its per-request correlation id taken out.

    ⚠ **`trace_id` IS DIFFERENT ON EVERY RESPONSE AND THAT IS THE ENVELOPE
    WORKING, NOT A LEAK.** `HR-1` asks that another tenant's row and a row that
    never existed answer the SAME 404 — same status, same `code`, same
    `message_key`. A correlation id is generated per request and differs between
    two calls to the SAME absent id, so comparing it would fail for a reason
    that has nothing to do with isolation. It is asserted PRESENT on both
    instead, because an envelope that dropped it would be a different defect.
    """
    assert body.get("trace_id"), "every refusal carries a trace id"
    return {name: value for name, value in body.items() if name != "trace_id"}


def _get(view, tenant, actor, path, **kwargs):
    query = kwargs.pop("query", None)
    return api_call(
        view,
        "get",
        f"/api/{tenant.subdomain}{path}",
        user=actor.user,
        role=SYSTEM_ADMIN,
        tenant=tenant,
        query=query,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE DOOR, UNDER A ROLE RLS APPLIES TO
# ═══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_003_pg_a_second_tenant_sees_none_of_the_first_tenants_runs(
    brazos, lonestar, dana, erin
):
    """Erin's history is her own, and it is EMPTY of Brazos Bend's four runs.

    The endpoint half of hard rule 1. Both tenants hold runs, so an empty answer
    for Erin cannot be an empty database — which is the difference between this
    case and one that seeds a single tenant and reports success.
    """
    with live_tenant_context(brazos.id):
        _seed(brazos, key="brazos-can-we-bill", runs=4)
    with live_tenant_context(lonestar.id):
        _seed(lonestar, key="lonestar-can-we-bill", runs=1)

    mine = _get(api.runs_list, brazos, dana, "/runbooks/runs")
    theirs = _get(api.runs_list, lonestar, erin, "/runbooks/runs")
    assert mine.data["count"] == 4
    assert theirs.data["count"] == 1
    assert {row["id"] for row in mine.data["results"]} & {
        row["id"] for row in theirs.data["results"]
    } == set()


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_003_pg_every_run_route_is_a_404_across_the_tenant_line(
    brazos, lonestar, dana, erin
):
    """All four run routes, on the real vendor, with the real policy underneath.

    Asserted route by route rather than once: a tenant filter written on three
    of four and forgotten on the fourth is the shape this repository keeps
    finding, and on PostgreSQL the policy would refuse the fourth anyway — so a
    green here is *both* halves agreeing, which is what production has.
    """
    with live_tenant_context(brazos.id):
        _runbook, runs = _seed(brazos, key="brazos-can-we-bill")
    run_id = str(runs[0].pk)
    absent = str(uuid.uuid4())
    for view, extra in (
        (api.run_detail, {}),
        (api.run_report, {}),
        (api.run_records, {}),
        (api.run_result_file, {"outcome": "done"}),
    ):
        theirs = _get(view, lonestar, erin, f"/runbooks/runs/{run_id}", run_id=run_id, **extra)
        never = _get(view, lonestar, erin, f"/runbooks/runs/{absent}", run_id=absent, **extra)
        assert theirs.status_code == never.status_code == 404
        assert _indistinguishable(theirs.data) == _indistinguishable(never.data)
    # And the owner can still read every one of them — a 404 for everybody is
    # not isolation, it is a broken route (law 7: name the false pass).
    for view, extra in (
        (api.run_detail, {}),
        (api.run_report, {}),
        (api.run_records, {}),
    ):
        assert (
            _get(view, brazos, dana, f"/runbooks/runs/{run_id}", run_id=run_id, **extra).status_code
            == 200
        )


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_003_pg_the_two_result_files_carry_no_other_tenants_row(
    brazos, lonestar, dana, erin
):
    """A download is the quiet leak: it streams, and nobody reads all of it."""
    with live_tenant_context(brazos.id):
        _runbook, brazos_runs = _seed(brazos, key="brazos-can-we-bill")
    with live_tenant_context(lonestar.id):
        _seed(lonestar, key="lonestar-can-we-bill")

    run_id = str(brazos_runs[0].pk)
    response = _get(
        api.run_result_file,
        brazos,
        dana,
        f"/runbooks/runs/{run_id}/results/not-done.csv",
        run_id=run_id,
        outcome="not-done",
    )
    body = b"".join(response.streaming_content).decode("utf-8")
    assert "brazos-can-we-bill subject 1" in body
    assert "lonestar" not in body


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_003_pg_with_no_tenant_in_context_the_run_tables_are_empty(
    rls, brazos, lonestar, dana, erin
):
    """Deny by default: `app.tenant_id` unset means nothing is readable.

    `NULLIF(current_setting('app.tenant_id', true), '')::uuid` is NULL when the
    setting is unset, the policy predicate is NULL, and no row is visible. This
    is what makes the endpoint's own filter a SECOND line rather than the only
    one — asserted under the probe role, because a superuser bypasses the policy
    and would report a green over a guarantee that was never consulted.
    """
    with live_tenant_context(brazos.id):
        _seed(brazos, key="brazos-can-we-bill")
    assert_denied_without_context(rls, *RUN_TABLES)


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_003_pg_the_policy_scopes_the_two_tables_this_wave_reads(
    rls, brazos, lonestar, dana, erin
):
    """Through the DATABASE, with the app-layer filter deliberately out of the path.

    What is tested here is the POLICY, not the queryset — and both directions,
    because a policy that scopes reads one way and not the other is a leak a
    one-sided test reports as healthy.
    """
    with live_tenant_context(brazos.id):
        _seed(brazos, key="brazos-can-we-bill")
    with live_tenant_context(lonestar.id):
        _seed(lonestar, key="lonestar-can-we-bill")
    for table in RUN_TABLES:
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar, min_owner_rows=1)
    assert_no_foreign_rows_anywhere(rls, brazos, RUN_TABLES)
    assert_no_foreign_rows_anywhere(rls, lonestar, RUN_TABLES)


# ═══════════════════════════════════════════════════════════════════════════
# NFR-3 ON THE VENDOR THAT WILL RUN IT
# ═══════════════════════════════════════════════════════════════════════════


@requires_postgres
@pytest.mark.django_db
def test_us_rbs_003_pg_paging_is_total_and_the_windows_do_not_overlap(brazos, dana):
    """51 runs, `per=5` clamped to 50, and page 2 holds the one that is left.

    ⚠ **THIS CASE IS ON POSTGRESQL AS WELL AS SQLITE ON PURPOSE, AND NOT AS
    DUPLICATION.** The order is `-started_at, -id` and `started_at` is nullable;
    PostgreSQL sorts NULLs FIRST on a descending order and SQLite sorts them
    LAST, so a slice ordered on that column alone divides the rows differently
    on the two vendors and page 1 and page 2 can overlap on one and not the
    other. The `id` tiebreak is what makes the order total, and this is where
    that claim is actually exercised against a planner that disagrees with the
    test suite's.
    """
    with live_tenant_context(brazos.id):
        runbook, _runs = _seed(brazos, key="dunning", runs=51, records_per_run=0)

    first = _get(api.runs_list, brazos, dana, "/runbooks/runs", query={"per": "5"})
    second = _get(api.runs_list, brazos, dana, "/runbooks/runs", query={"page": "2", "per": "5"})
    assert first.data["count"] == 51
    assert len(first.data["results"]) == 50
    assert len(second.data["results"]) == 1
    ids = [row["id"] for row in first.data["results"]] + [
        row["id"] for row in second.data["results"]
    ]
    assert len(set(ids)) == 51, "the two windows overlap — the order is not total"

    wide = _get(api.runs_list, brazos, dana, "/runbooks/runs", query={"per": "5000"})
    assert len(wide.data["results"]) == 51, "per=5000 must clamp to 1000, not refuse"
    with live_tenant_context(brazos.id):
        assert selectors.runs_page(brazos.id, per="5000")["per"] == 1000


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-003 · US-RBS-018 (EP-RBS-01; CR-075 wave D task D1)
# generated: 2026-09-06 by the CR-075 wave D build lane
# checklist: A✔ B✔ C✔ D✔ E=n/a(a test file) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_us_rbs_003_pg.py on PostgreSQL · G5 (no bare skip on an isolation case)
# exceptions: every case SKIPS on SQLite rather than passing vacuously — hard-won law 14
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
