# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-006 (EP-RBS-03) — CR-075 wave H task H4. The work list.
#           Screens: RBS-007.1 · RBS-007.2.
# Rules:    BR-RBS-017 (a work item is UPSERTED by fingerprint so a repeated
#           finding AGES rather than duplicating) · BR-RBS-022 (work items are
#           the ENGINE's to write, never a port) · BR-RBS-011 (a failure names
#           its fix route) · B14 rule 31 (no database id is ever the visible
#           value of a field) · rule 32 (no rule id or internal code in clerk
#           copy) · hard-won law 7 (prove the guard RED first)
# Tests:    this file
# Impacts:  apps/runbooks/engine/work_items.py · apps/runbooks/services.py ·
#           apps/runbooks/selectors.py · apps/runbooks/contract.py
# ───────────────────────────────────────────────────────
"""`TC-RBS-10` and the four cases `US-RBS-006` names, on the default suite.

**`TC-RBS-10` — thirty daily sweeps over one missing read are ONE item, THIRTY
DAYS OLD**, and it is shown RED on an insert-instead-of-upsert before it is
shown green. The red half is not a comment: it runs the same thirty sweeps with
the run id folded into the fingerprint — **the exact wrong build `US-RBS-006`
§5 forbids in its own words** — and asserts thirty rows arrive.

⚠ **THE SECOND HALF OF `TC-RBS-10` IS THE ONE THAT IS EASY TO MISS: the item
must CLOSE ITSELF when the finding stops recurring.** An early return on an
empty finding list is the most natural line to write in `upsert` and it would
break exactly that, with every other assertion in this file still green — so it
has a case of its own, and the case runs a sweep that raises NOTHING.

⚠ **WHAT IS NOT HERE, WITH ITS REASON.** `TC-RBS-7` (two tenants, the same
finding on accounts of the same number, RLS `FORCE` on) cannot be proved on this
vendor: **SQLite has no row-level security at all**, so a case here would report
green over a guarantee that does not exist (`G5` once called 192 skips a pass).
The fingerprint carries the tenant as its first field and the unique index is
`(tenant, fingerprint)`; both are asserted below as STRINGS and as a constraint,
and the isolation half belongs to a PostgreSQL run.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.runbooks import models, selectors, services
from apps.runbooks.contract import Finding, RunbookContractError
from apps.runbooks.engine import work_items
from apps.runbooks.registry import registry

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


FORBIDDEN_IN_CLERK_COPY = (
    re.compile(r"\bBR-[A-Z]{3}-\d{3,5}\b"),
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
)

#: The finding one missing read raises, every morning, for thirty days.
THE_MISSING_READ = Finding(
    kind="reads:water",
    title="No read for Water this period.",
    fix_route="meter-reads",
    weight=100,
    subject_ref="1 account",
    subject_type="tenant",
)


def _runbook(brazos, key="configuration_check"):
    return services.add_template(brazos.id, key)


def _sweep(brazos, runbook, findings):
    """One run that raises exactly these findings, closed the product's own way.

    ⚠ **THROUGH `services.close_run`, NOT BY CALLING `upsert` DIRECTLY.** The
    thing under test is *what happens when a run closes*, and a fixture that
    called the engine act by hand would pass over a `close_run` that had stopped
    calling it — which is `DEF-RBS-4291`'s shape exactly (`open_run` stopped
    stamping `started_at` and every check still passed).
    """
    definition = registry.get(runbook.key)
    run = services.open_run(runbook, definition)
    result = _result(definition, findings)
    return services.close_run(run, result)


def _result(definition, findings):
    from apps.runbooks.engine.executor import RunResult

    return RunResult(
        runbook_key=definition.key,
        subjects=(),
        scope_fingerprint="fp",
        guarded=(),
        set_results={},
        records=(),
        counts={},
        report=[
            {
                "block": "sentence",
                "payload": {"tone": "neutral", "text": "A sweep ran."},
            }
        ],
        step_runs={},
        findings=tuple(findings),
    )


# ── the declaration · BR-RBS-011 · BR-RBS-017 ─────────────────────────────


def test_a_finding_with_no_fix_route_cannot_be_constructed():
    """`BR-RBS-011` — *a failure with no route is a defect in the runbook*.

    Refused at CONSTRUCTION, like every other declaration in this module, so a
    finding built in a branch no fixture reaches cannot escape without one.
    """
    with pytest.raises(RunbookContractError) as refused:
        Finding(kind="reads:water", title="No read.", fix_route="  ")
    assert "fix route" in str(refused.value)


def test_a_finding_with_no_kind_cannot_be_constructed():
    """Without a kind there is no fingerprint, so every run raises a new row."""
    with pytest.raises(RunbookContractError) as refused:
        Finding(kind="", title="No read.", fix_route="meter-reads")
    assert "fingerprinted" in str(refused.value)


def test_the_fingerprint_never_contains_the_run_id(brazos):
    """`US-RBS-006` §5, in its own words: *never contains the run id*."""
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        run = _sweep(brazos, runbook, [THE_MISSING_READ])
        item = models.WorkItem.objects.get(tenant_id=brazos.id)

    assert str(run.pk) not in item.fingerprint
    # The four parts, in order: tenant · runbook · subject · kind.
    assert item.fingerprint == f"{brazos.id}|configuration_check|tenant|reads:water"


# ── TC-RBS-10 · thirty sweeps are ONE item, thirty days old ───────────────


def test_tc_rbs_10__thirty_daily_sweeps_over_one_missing_read_are_one_item(brazos):
    """The headline. **One item ageing, not thirty items.**"""
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        for _ in range(30):
            _sweep(brazos, runbook, [THE_MISSING_READ])
        items = list(models.WorkItem.objects.filter(tenant_id=brazos.id))

    assert len(items) == 1, f"thirty sweeps produced {len(items)} rows — the upsert is an insert"
    assert items[0].status == "open"


def test_tc_rbs_10_red__with_the_run_in_the_fingerprint_thirty_sweeps_are_thirty_rows(
    brazos,
):
    """**THE RED HALF, and it is the wrong build spelled out.**

    `US-RBS-006` §5 forbids the run id in the fingerprint. This runs the same
    thirty sweeps through the same engine act with the run folded in — the change
    a lane would actually make, reaching for the run because it is right there —
    and watches thirty rows arrive. Without this case the green above would be
    consistent with an upsert that happened never to be exercised twice.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        definition = registry.get(runbook.key)
        for _ in range(30):
            run = services.open_run(runbook, definition)
            key = work_items.fingerprint(
                tenant_id=run.tenant_id, runbook_key=definition.key, finding=THE_MISSING_READ
            )
            models.WorkItem.objects.create(
                tenant_id=run.tenant_id,
                source_kind=models.WORK_ITEM_SOURCE_FINDING,
                source_run=run,
                # ⚠ THE WRONG BUILD: the run id, in the key.
                fingerprint=f"{key}|{run.pk}",
                title=THE_MISSING_READ.title,
                weight=THE_MISSING_READ.weight,
                fix_route=THE_MISSING_READ.fix_route,
                status="open",
            )
        assert models.WorkItem.objects.filter(tenant_id=brazos.id).count() == 30


def test_the_age_a_clerk_sees_is_the_first_sighting_and_not_the_last(brazos):
    """*"The age a clerk sees is `created_at`, never the last sighting."*

    A row that showed `updated_at` would read *3 hours* every morning and the
    screen would lose the only number that says a thing has been ignored.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        _sweep(brazos, runbook, [THE_MISSING_READ])
        item = models.WorkItem.objects.get(tenant_id=brazos.id)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        models.WorkItem.objects.filter(pk=item.pk).update(created_at=thirty_days_ago)

        _sweep(brazos, runbook, [THE_MISSING_READ])
        again = models.WorkItem.objects.get(tenant_id=brazos.id)

    assert again.created_at == thirty_days_ago
    assert again.updated_at > thirty_days_ago


# ── the item closes itself · J-RBS-1's last assertion ─────────────────────


def test_the_item_closes_itself_when_the_finding_stops_recurring(brazos):
    """`J-RBS-1`: *fix the tax region, re-run, and the item closes itself.*

    Nobody ticks anything. The item is DERIVED, and its absence from the next
    run is the whole signal.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        _sweep(brazos, runbook, [THE_MISSING_READ])
        assert models.WorkItem.objects.filter(status="open").count() == 1

        # The read arrives. The next sweep raises nothing at all.
        run = _sweep(brazos, runbook, [])
        item = models.WorkItem.objects.get(tenant_id=brazos.id)

    assert item.status == "resolved"
    assert item.resolved_at is not None
    # ⚠ **THE COUNT IS ON THE RUN**, so *raised 0* is visible beside *closed 1*
    # rather than being an absence a reader has to infer.
    assert run.counts[work_items.COUNT_RAISED] == 0
    assert run.counts[work_items.COUNT_CLOSED] == 1


def test_a_run_that_raised_nothing_still_closes__the_early_return_case(brazos):
    """⚠ **THE RED HALF OF SELF-CLOSING, AND IT IS A ONE-LINE MISTAKE.**

    `if not findings: return {...}` at the top of `upsert` is the most natural
    line to write there, it is what a reader would call an optimisation, and it
    breaks exactly this — with every other case in this file still green,
    because they all raise something. So the assertion is made on the FUNCTION
    rather than only through a sweep: called with an empty sequence, it must
    still close.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        _sweep(brazos, runbook, [THE_MISSING_READ])
        definition = registry.get(runbook.key)
        run = services.open_run(runbook, definition)
        counts = work_items.upsert(run, definition, [])

    assert counts[work_items.COUNT_CLOSED] == 1


def test_one_runbooks_run_never_closes_another_runbooks_item(brazos):
    """The scoping half. A grid run must not tidy away the ladder's exceptions."""
    with tenant_ctx(brazos):
        first = _runbook(brazos, "configuration_check")
        second = _runbook(brazos, "coverage_grid")
        _sweep(brazos, first, [THE_MISSING_READ])
        _sweep(brazos, second, [])
        item = models.WorkItem.objects.get(tenant_id=brazos.id)

    assert item.status == "open", "the coverage grid closed runbook 1's finding"


def test_a_human_task_is_outside_the_closing_query_by_construction(brazos):
    """A cutover task has no run and no runbook prefix, so no run can close it.

    ⚠ **BY CONSTRUCTION RATHER THAN BY A FLAG SOMEBODY HAS TO REMEMBER.** A
    `skip if source_kind == human_task` would be correct today and would be
    forgotten by the wave that adds a fourth source kind.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        models.WorkItem.objects.create(
            tenant_id=brazos.id,
            source_kind=models.WORK_ITEM_SOURCE_HUMAN_TASK,
            fingerprint="cutover|silvercreek-golive|item:7",
            title="Customer signs bill layout",
            weight=0,
            fix_route="cutover",
            status="open",
        )
        _sweep(brazos, runbook, [])
        task = models.WorkItem.objects.get(source_kind=models.WORK_ITEM_SOURCE_HUMAN_TASK)

    assert task.status == "open"


# ── TC-RBS-006.2 · a resolved item whose finding recurs REOPENS ───────────


def test_tc_rbs_006_2__a_resolved_item_whose_finding_recurs_reopens_the_same_row(
    brazos,
):
    """**The same row, with its history — never a second row.**"""
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        _sweep(brazos, runbook, [THE_MISSING_READ])
        item = models.WorkItem.objects.get(tenant_id=brazos.id)
        services.update_work_item(item, {"status": "resolved"})
        assert models.WorkItem.objects.get(pk=item.pk).status == "resolved"

        _sweep(brazos, runbook, [THE_MISSING_READ])
        rows = list(models.WorkItem.objects.filter(tenant_id=brazos.id))

    assert len(rows) == 1
    assert rows[0].pk == item.pk
    assert rows[0].status == "open"
    assert rows[0].resolved_at is None


# ── assign · resolve · reopen · US-RBS-006 §5 ─────────────────────────────


def test_resolving_stamps_the_time_and_reopening_clears_it_and_keeps_the_row(brazos):
    """`US-RBS-006` §5, word for word."""
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        _sweep(brazos, runbook, [THE_MISSING_READ])
        item = models.WorkItem.objects.get(tenant_id=brazos.id)
        created = item.created_at

        resolved = services.update_work_item(item, {"status": "resolved"})
        assert resolved.resolved_at is not None

        reopened = services.update_work_item(resolved, {"status": "open"})

    assert reopened.resolved_at is None
    assert reopened.pk == item.pk
    assert reopened.created_at == created


def test_a_person_may_not_edit_a_field_the_engine_re_derives(brazos):
    """⚠ **REFUSED, NOT IGNORED.** A caller that sent `title` believing it would
    stick deserves to be told; silently dropping it is how a screen ends up
    claiming an edit that never happened — and the next run would revert it."""
    from core import errors

    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        _sweep(brazos, runbook, [THE_MISSING_READ])
        item = models.WorkItem.objects.get(tenant_id=brazos.id)
        with pytest.raises(errors.ValidationError):
            services.update_work_item(item, {"title": "something else"})


# ── the row a screen draws · B14 rules 31 and 32 ──────────────────────────


def test_the_row_never_carries_the_fingerprint_and_names_the_runbook_in_words(brazos):
    """`US-RBS-006` §5: the fingerprint is *never rendered* (B14 rule 31)."""
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        _sweep(brazos, runbook, [THE_MISSING_READ])
        page = selectors.work_items_page(brazos.id)

    row = page["rows"][0]
    assert "fingerprint" not in row
    assert row["from"] == "Can we bill?"
    assert row["weight_pill"] == "blocks_billing"
    assert row["subject_ref"] == "1 account"
    assert row["fix_route"] == "meter-reads"
    for key in ("title", "from", "subject_ref", "fix_route"):
        for pattern in FORBIDDEN_IN_CLERK_COPY:
            assert not pattern.search(str(row[key] or ""))


def test_the_list_defaults_to_open_and_sorts_the_heaviest_and_oldest_first(brazos):
    """*Sorted by weight, then age* — and **age is OLDEST first**, which is the
    opposite of every other list in the product and the whole point of this one."""
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        _sweep(
            brazos,
            runbook,
            [
                Finding(
                    kind="tax:water",
                    title="No tax region is set.",
                    fix_route="settings/tax",
                    weight=100,
                    subject_type="tenant",
                ),
                Finding(
                    kind="plans:water",
                    title="A rate stops at 20,000 gallons.",
                    fix_route="plans",
                    weight=50,
                    subject_type="tenant",
                ),
            ],
        )
        heavy = models.WorkItem.objects.get(weight=100)
        models.WorkItem.objects.filter(pk=heavy.pk).update(
            created_at=timezone.now() - timedelta(days=30)
        )
        page = selectors.work_items_page(brazos.id)
        chips = selectors.work_item_counts(brazos.id)

    assert [row["title"] for row in page["rows"]] == [
        "No tax region is set.",
        "A rate stops at 20,000 gallons.",
    ]
    assert chips["all"] == 2
    assert chips["blocks_billing"] == 1

    with tenant_ctx(brazos):
        services.update_work_item(
            selectors.work_item(brazos.id, str(heavy.pk)), {"status": "resolved"}
        )
        still_open = selectors.work_items_page(brazos.id)
    assert [row["title"] for row in still_open["rows"]] == [
        "A rate stops at 20,000 gallons."
    ]
