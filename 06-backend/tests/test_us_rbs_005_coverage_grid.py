# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-005 (EP-RBS-02) — CR-075 wave G task G4. Runbook 24, the
#           Coverage grid. Screens: RBS-004-R24 · RBS-006-R24.
# Rules:    BR-RBS-002 (a Check is CONSTRUCTED with no ports) · BR-RBS-009 (the
#           scope is resolved ONCE and pinned) · BR-RBS-011 (a refusal names its
#           fix route) · BR-RBS-014 (a sample record is never picked) ·
#           BR-RBS-021 (the grid is the Records block's DISPLAY MODE, not a
#           thirteenth block) · BR-RBS-023 · B14 rule 31 (no database id on
#           screen) · rule 32 (no rule id or internal code in clerk copy) ·
#           hard-won law 7 (a check that cannot cover its whole subject prints
#           what it skipped)
# Tests:    this file
# Impacts:  apps/runbooks/definitions/coverage_grid.py
# ───────────────────────────────────────────────────────
"""Runbook 24 on the default suite — the three cases `US-RBS-005` names.

`TC-RBS-005.2` (two runs, the same 25, the same order) · `TC-RBS-005.3` (no
sample account is ever picked) · `TC-RBS-005.5` (**the pick states what it left
out** rather than applying a silent `LIMIT 25`).

⚠ **EACH OF THE THREE CARRIES ITS *MUST FIRST FAIL ON* AS A CASE OF ITS OWN**,
because hard-won law 7 asks what would make a check pass wrongly and a check
nobody has watched fail is a claim rather than a guard. The three wrong builds
`US-RBS-005`'s own table names are:

  * a random or `ORDER BY`-less pick — proved red by feeding the planner the
    same estate in a different order and asserting the answer does not move;
  * the sample guard omitted from the pick rather than from the act — proved red
    by running the same planner with an empty sample set and watching the demo
    account arrive;
  * a silent `LIMIT 25` — proved red by asserting the SENTENCE carries the two
    numbers, over a run where they differ.

⚠ **WHAT IS DELIBERATELY NOT HERE, WITH ITS REASON.** `TC-RBS-005.1` and
`TC-RBS-005.4` are the **21 · 2 · 2** figure and the *fix the rate and it moves
to 23* movement. Both need a whole seeded utility — twenty-five plan and cycle
combinations, two estimated reads, a rate ladder that stops at 20,000 gallons —
and both are proved in a real browser against real PostgreSQL by
`10-scripts/render-checks/rbs-g-coverage-grid.mjs` and its seed. Asserting them
on a hand-built SQLite fixture would prove the fixture.
"""

from __future__ import annotations

import re

import pytest

from apps.runbooks import models, services
from apps.runbooks.contract import (
    MODE_PER_RECORD,
    MODE_SET,
    scope_fingerprint,
    validate_report,
)
from apps.runbooks.definitions import coverage_grid as rb24
from apps.runbooks.engine import executor
from apps.runbooks.registry import registry

from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


#: What a clerk must never be shown — the same three patterns runbook 23's suite
#: and the browser walkthrough use, so a string that passes here passes there.
FORBIDDEN_IN_CLERK_COPY = (
    re.compile(r"\bBR-[A-Z]{3}-\d{3,5}\b"),
    re.compile(r"\b(?:OQ|DEF|TC|US|EP|GT|RB)-(?:[A-Z]{3}-)?\d{2,5}\b"),
    re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"),
)

PERIOD = {"start": PERIOD_START.isoformat(), "end": PERIOD_END.isoformat()}


def _estate(brazos, dana, *, plans=2):
    """`plans` plan-and-cycle combinations, one billable account in each.

    Each combination is a DIFFERENT plan on a DIFFERENT cycle, which is what
    makes them separate cells rather than one cell with several members.
    """
    made = []
    for index in range(plans):
        cycle = a_cycle(brazos, code=f"24-{index}")
        plan = a_priced_plan(brazos, name=f"Runbook 24 Plan {index}")
        unit = a_billed_unit(
            dana,
            brazos,
            cycle,
            plan,
            asset_no=f"M-2400{index}",
            label=f"24-{index}",
            consumption="412.000000",
        )
        made.append(an_account(brazos, unit["id"], f"A-2400{index}"))
    return made


def _ctx(brazos, *, cells=25, run_id=None):
    definition = rb24.RUNBOOK
    params = {p.name: p.default for p in definition.parameters if p.default is not None}
    params.update({"accounts": cells, "period": PERIOD})
    return executor.build_context(
        definition, tenant_id=brazos.id, run_id=run_id, params=params
    )


def _add(brazos, key):
    return services.add_template(brazos.id, key)


def _clerk_strings(blocks) -> list[str]:
    """Every string a report puts in front of a person (`meta` excluded)."""
    found: list[str] = []

    def walk(node, *, inside_meta=False):
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, inside_meta=inside_meta or key == "meta")
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value, inside_meta=inside_meta)
        elif isinstance(node, str) and not inside_meta:
            found.append(node)

    walk(blocks)
    return found


# ── the declaration · BR-RBS-002 · BR-RBS-023 ─────────────────────────────


def test_runbook_24_holds_no_port_at_all():
    """A Check is CONSTRUCTED without action ports — the capability is gone.

    Twenty-five child runs of runbook 23 do not change that: a child run is a
    row in THIS module's own table, written by this module's own service, and
    not a write to another module through a port.
    """
    assert rb24.RUNBOOK.kind == models.KIND_CHECK
    assert rb24.RUNBOOK.ports == ()
    assert rb24.RUNBOOK.writes_nothing() is True


def test_the_three_steps_are_the_build_sheets_own_three():
    """`RBS-004-R24` region 3 draws three rows with this copy, in this order."""
    assert [s.key for s in rb24.RUNBOOK.steps] == ["pick", "price", "group"]
    assert [s.label for s in rb24.RUNBOOK.steps] == [
        "Pick one account per plan, service mix and cycle",
        "Price each one through the real engine",
        "Group by outcome",
    ]
    assert [s.mode for s in rb24.RUNBOOK.steps] == [MODE_SET, MODE_PER_RECORD, MODE_SET]
    assert all(step.writes is False for step in rb24.RUNBOOK.steps)


def test_pricing_is_per_record_so_one_bad_cell_cannot_take_the_grid():
    """⚠ **THE MODE IS THE SAVEPOINT** — hard-won law 14, stated as an assertion.

    `executor._run_one_record` wraps a per-record step in a nested
    `transaction.atomic()`, which on PostgreSQL is a real `SAVEPOINT`. Registered
    as `set`, all twenty-five cells would share one transaction and the first
    refused statement would abort the run at COMMIT — **and the whole suite
    would still be green, because `config/settings/test.py` is in-memory SQLite,
    which has no aborted-transaction state at all.** Nothing else in this file
    can see that, so the mode is asserted by name.
    """
    price = next(step for step in rb24.RUNBOOK.steps if step.key == rb24.STEP_PRICE)
    assert price.mode == MODE_PER_RECORD


# ── TC-RBS-005.2 · two runs, the same accounts, the same order ────────────


def test_tc_rbs_005_2__two_runs_over_an_unchanged_estate_pick_the_same_set(brazos, dana):
    """*"If the 25 are re-picked at random, 'the grid moved from 21 to 23' is
    not a measurement."* Same accounts, same order, same fingerprint."""
    with tenant_ctx(brazos):
        _add(brazos, "test_bill")
        _estate(brazos, dana, plans=2)

        first = list(rb24.resolve(_ctx(brazos)))
        second = list(rb24.resolve(_ctx(brazos)))

    assert [s.subject_id for s in first] == [s.subject_id for s in second]
    assert len(first) == 2
    assert scope_fingerprint(first) == scope_fingerprint(second)


def test_tc_rbs_005_2_red__the_order_does_not_come_from_the_input(brazos, dana):
    """The RED half: *a random or `ORDER BY`-less pick*.

    The planner is handed the SAME estate with its accounts reversed. A pick
    that merely took them in arrival order would answer differently; this one
    sorts by the plan's NAME, the service mix and the cycle, so it does not
    move. Feeding the reversed list is the change a broken build would survive.
    """
    with tenant_ctx(brazos):
        _add(brazos, "test_bill")
        _estate(brazos, dana, plans=2)
        estate = rb24._estate(_ctx(brazos))

    forwards = rb24._plan(estate, cells=25)
    backwards = rb24._plan({**estate, "accounts": list(reversed(estate["accounts"]))}, cells=25)

    assert [c["account_id"] for c in forwards["cells"]] == [
        c["account_id"] for c in backwards["cells"]
    ]
    assert [c["plan_name"] for c in forwards["cells"]] == sorted(
        c["plan_name"] for c in forwards["cells"]
    )


# ── TC-RBS-005.3 · a sample account is never picked · BR-RBS-014 ──────────


def test_tc_rbs_005_3__a_sample_account_is_never_picked(brazos, dana):
    """`BR-RBS-014` — *a sample record is never acted on, in any tenant, at any
    time*; here, never PICKED. It is excluded in the pick because this runbook
    has no act to exclude it from."""
    with tenant_ctx(brazos):
        _add(brazos, "test_bill")
        accounts = _estate(brazos, dana, plans=2)
        from apps.customers import models as customer_models

        customer_models.Account.objects.filter(pk=accounts[0].pk).update(is_sample=True)
        estate = rb24._estate(_ctx(brazos))

    picked = rb24._plan(estate, cells=25)
    assert str(accounts[0].id) not in [c["account_id"] for c in picked["cells"]]
    assert picked["excluded_sample"] == 1
    # ⚠ **AND THE COUNT IS PUBLISHED, NOT ONLY THE EXCLUSION.** A guard that
    # removes a row and says nothing is indistinguishable from an estate that
    # never had it (hard-won law 7's fifth shape).
    assert "1 sample" in rb24._coverage_sentence(picked)


def test_tc_rbs_005_3_red__without_the_guard_the_sample_account_is_picked(brazos, dana):
    """The RED half: *the sample guard omitted from the pick rather than from
    the act*. The same planner, the same estate, an empty sample set."""
    with tenant_ctx(brazos):
        _add(brazos, "test_bill")
        accounts = _estate(brazos, dana, plans=2)
        from apps.customers import models as customer_models

        customer_models.Account.objects.filter(pk=accounts[0].pk).update(is_sample=True)
        estate = rb24._estate(_ctx(brazos))

    unguarded = rb24._plan({**estate, "samples": frozenset()}, cells=25)
    assert str(accounts[0].id) in [c["account_id"] for c in unguarded["cells"]]
    assert unguarded["excluded_sample"] == 0


# ── TC-RBS-005.5 · it states what it left out ─────────────────────────────


def test_tc_rbs_005_5__the_pick_states_what_it_left_out(brazos, dana):
    """*The pick states what it left out rather than silently truncating.*

    Two combinations exist and the grid is asked for ONE. The sentence carries
    both numbers, which is the only thing that separates a grid over the whole
    estate from a grid over a slice of it.
    """
    with tenant_ctx(brazos):
        _add(brazos, "test_bill")
        _estate(brazos, dana, plans=2)
        estate = rb24._estate(_ctx(brazos, cells=1))

    picked = rb24._plan(estate, cells=1)
    assert picked["groups_found"] == 2
    assert picked["cells_drawn"] == 1
    assert picked["cells_left_out"] == 1

    sentence = rb24._coverage_sentence(picked)
    assert "1 of 2" in sentence
    assert "1 more would not fit" in sentence


def test_tc_rbs_005_5_red__a_silent_limit_would_say_the_same_thing_either_way(
    brazos, dana
):
    """The RED half: *a silent `LIMIT 25`*.

    A truncating build produces the SAME twenty-five rows and a sentence that
    cannot tell a covered estate from a sliced one. So the assertion is that the
    two sentences DIFFER — the full-coverage wording and the truncated wording
    are not the same string, which is exactly what a silent limit would break.
    """
    with tenant_ctx(brazos):
        _add(brazos, "test_bill")
        _estate(brazos, dana, plans=2)
        estate = rb24._estate(_ctx(brazos))

    whole = rb24._coverage_sentence(rb24._plan(estate, cells=25))
    sliced = rb24._coverage_sentence(rb24._plan(estate, cells=1))
    assert whole != sliced
    assert "All 2 plan and cycle combinations were priced." in whole
    assert "would not fit" not in whole


# ── the run, end to end: the grid is a DISPLAY MODE · BR-RBS-021 ──────────


def _run(brazos, dana, *, cells=25):
    runbook = _add(brazos, "coverage_grid")
    definition = registry.get("coverage_grid")
    run = services.open_run(runbook, definition)
    ctx = _ctx(brazos, cells=cells, run_id=run.pk)
    result = executor.execute(definition, ctx=ctx)
    return services.close_run(run, result), result


def test_the_grid_is_the_records_blocks_display_mode_and_not_a_thirteenth_block(
    brazos, dana
):
    """`BR-RBS-021` — twelve names, closed. The grid is `records` with
    `display: "grid"`, which `RecordsPayload` has declared since wave C."""
    with tenant_ctx(brazos):
        _add(brazos, "test_bill")
        _estate(brazos, dana, plans=2)
        run, result = _run(brazos, dana)

    names = [block["block"] for block in run.report]
    assert names == ["kpis", "records", "sentence"]
    records = next(b["payload"] for b in run.report if b["block"] == "records")
    assert records["display"] == "grid"
    assert set(records["grid"]) == {"labelKey", "stateByRowId", "linkKey", "reasonKey"}
    # `validate_report` already ran at close; asserting it again here is what
    # catches a payload that only the DATABASE round trip would break.
    validate_report(run.report, runbook_key="coverage_grid")


def test_every_cell_opens_that_accounts_own_test_bill(brazos, dana):
    """*"a red cell opens that account's test bill"* — a real run, not a string.

    ⚠ **`RecordGrid` CANNOT EXPRESS A CELL WITHOUT A DESTINATION**, which is why
    this asserts that the address names a run that EXISTS and whose runbook is
    the test bill — an href that merely looks right is the shape `DEF-CWP-3925`
    cost eight doors.
    """
    with tenant_ctx(brazos):
        _add(brazos, "test_bill")
        _estate(brazos, dana, plans=2)
        run, result = _run(brazos, dana)

        records = next(b["payload"] for b in run.report if b["block"] == "records")
        assert records["rows"], "a grid with no cells proves nothing"
        for row in records["rows"]:
            link = row["cells"]["open"]
            assert link["kind"] == "link"
            assert link["to"].startswith("runbooks/test_bill/runs/")
            child = models.RunbookRun.objects.filter(
                pk=link["to"].rsplit("/", 1)[-1]
            ).first()
            assert child is not None, f"cell links at {link['to']} and no such run exists"
            assert child.runbook.key == "test_bill"
            # The provenance column that makes a child run a child run.
            assert str(child.parent_run_id) == str(run.pk)


def test_the_counts_are_the_engines_own_and_the_strip_carries_its_denominator(
    brazos, dana
):
    """⚠ **WHAT WOULD MAKE THIS RUNBOOK PASS WRONGLY** — a grid over three
    accounts of four hundred reads *3 clean* and looks perfect. The fourth tile
    is the denominator that stops it."""
    with tenant_ctx(brazos):
        _add(brazos, "test_bill")
        _estate(brazos, dana, plans=2)
        run, result = _run(brazos, dana)

    tiles = next(b["payload"] for b in run.report if b["block"] == "kpis")["tiles"]
    assert [tile["label"] for tile in tiles] == ["Clean", "Estimated", "Refused", "Cells"]
    # ⚠ **THE VALUE IS A `ReportValue` OBJECT AND NOT A STRING — `DEF-RBS-4375`.**
    # `KpisPayload.tiles[].value` is the same tagged union every report cell
    # uses, and a bare `"3"` renders as NOTHING: the strip drew four labels over
    # four empty boxes and the browser check, which asserted only the label,
    # passed over it. This case asserts the SHAPE, because `PAYLOAD_FIELDS`
    # cannot — it validates top-level names and `tiles` is present either way.
    assert all(tile["value"] == {"kind": "text", "text": tile["value"]["text"]} for tile in tiles)
    assert all(isinstance(tile["id"], str) and tile["id"] for tile in tiles)
    assert sum(int(tile["value"]["text"]) for tile in tiles[:3]) == int(tiles[3]["value"]["text"])
    # The engine derived them from the record rows; the runbook did not re-count.
    assert sum(result.counts.values()) == len(result.records) == 2


def test_no_database_id_and_no_rule_id_reaches_a_clerk(brazos, dana):
    """B14 rules 31 and 32 over every string the report draws.

    The cell's `to` is an ADDRESS and addresses carry ids — that is what an
    address is — so the link's `to` is excluded by name here and asserted
    separately above. Everything a reader sees is checked.
    """
    with tenant_ctx(brazos):
        _add(brazos, "test_bill")
        _estate(brazos, dana, plans=2)
        run, result = _run(brazos, dana)

    drawn = []
    for block in run.report:
        payload = dict(block["payload"])
        if block["block"] == "records":
            payload = {
                **payload,
                "rows": [
                    {**row, "cells": {k: v for k, v in row["cells"].items() if k != "open"}}
                    for row in payload["rows"]
                ],
                # `id` and `stateByRowId` are KEYS, never rendered — RecordsBlock
                # says so in its own header and `RecordGrid` draws `label`.
                "grid": {"labelKey": payload["grid"]["labelKey"]},
            }
            payload["rows"] = [{"cells": row["cells"]} for row in payload["rows"]]
        drawn.append(payload)

    for text in _clerk_strings(drawn):
        for pattern in FORBIDDEN_IN_CLERK_COPY:
            assert not pattern.search(text), f"{pattern.pattern} matched {text!r}"


def test_without_the_test_bill_the_grid_resolves_nothing_and_says_why(brazos, dana):
    """`BR-RBS-042` clause 2 — *an empty domain says so*, with a route.

    Every cell IS a run of runbook 23, so a tenant that has not added it has
    nothing to price with. A grid that drew an empty rectangle over that would
    read as *your estate is fine*.
    """
    with tenant_ctx(brazos):
        _estate(brazos, dana, plans=2)
        assert list(rb24.resolve(_ctx(brazos))) == []
        run, result = _run(brazos, dana)

    assert result.subjects == ()
    sentence = next(b["payload"] for b in run.report if b["block"] == "sentence")
    assert "Add the Test bill" in sentence["text"]
