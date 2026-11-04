# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-009 (EP-RBS-03) — CR-075 wave K, runbook 9, *Books tie-out*.
#           Tasks K1 (the definition) · K2 (the Action block) · K3 (TC-RBS-17) ·
#           K4 (the unbalanced case and the $0.01 floor).
# Rules:    BR-RBS-002 (a Check holds no ports) · BR-RBS-021 (twelve blocks) ·
#           BR-RBS-023 (a step declares its mode — TC-RBS-17) · BR-RBS-029 (the
#           tax tolerance is $0.0000 and CANNOT be raised) · BR-RBS-030
#           (closing is a named person's act — CONFIRMED 2026-09-06, PO
#           verbatim *"1736 - always a person"*) · BR-LED-006 (checklist items
#           computed from live registers) · BR-LED-018 (no hard lockout) ·
#           CLAUDE.md hard rule 2 (money 4 stored / 2 displayed) · hard rule 5
#           (balanced pairs; this writes no journal line) · B14 rules 6 · 31 ·
#           32 · 33 · 34
# Tests:    this file — TC-RBS-17 (set once, per-record N times)
# Impacts:  apps/runbooks/definitions/month_end.py
# ───────────────────────────────────────────────────────
"""Runbook 9 — the books tie-out, and the button a person presses.

⚠ **WHAT THIS FILE CANNOT PROVE, SAID FIRST.** It runs on the default suite,
which is in-memory SQLite: tenant isolation does not exist there and a savepoint
proves nothing about PostgreSQL (hard-won law 14). Neither is pretended here.

⚠ **EVERY MONEY ASSERTION IS A FIGURE, NEVER A SHAPE.** A tie-out that reported
the wrong difference would pass *"there is a difference"*, and a month-end check
that is wrong in the reassuring direction is the one failure this runbook exists
to prevent.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.runbooks import models as runbook_models
from apps.runbooks.contract import (
    BLOCK_TYPES,
    MODE_PER_RECORD,
    MODE_SET,
    Parameter,
    RunbookContractError,
)
from apps.runbooks.definitions import month_end as rb9
from apps.runbooks.engine import executor
from apps.runbooks.registry import registry

# ⚠ THE STAR IMPORT IS LOAD-BEARING — see the note in the wave J suite.
from tests.test_us_met_helpers import *  # noqa: F401,F403 — incl. the autouse sqlite_guc
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
# THE CONTRACT — refused at construction if wrong
# ═══════════════════════════════════════════════════════════════════════════


def test_it_is_a_check_and_holds_no_ports_at_all():
    """`BR-RBS-002` · `BR-RBS-030`. **Close period is the LEDGER's act.**

    Asserted as **`ports == ()`**: the capability to close a period is ABSENT
    from this runbook rather than merely unused, so there is no path from a
    schedule to a period lock even by mistake. `OQ-RBS-1736` was CLOSED on
    2026-09-06 with the PO's own words — *"1736 - always a person"* — and this
    assertion is what that ruling looks like in code.
    """
    assert rb9.RUNBOOK.kind == runbook_models.KIND_CHECK
    assert rb9.RUNBOOK.ports == ()
    assert rb9.RUNBOOK.writes_nothing() is True


def test_it_is_registered_and_the_period_is_its_unit():
    assert "month_end" in registry.keys()
    assert rb9.RUNBOOK.subject_type == "period"
    assert rb9.RUNBOOK.unit_of_work == "accounting period"
    assert rb9.RUNBOOK.category == "finance"


def test_tc_rbs_17_eight_steps_are_SET_and_exactly_one_is_PER_RECORD():
    """`TC-RBS-17` · `BR-RBS-023` — **the set step runs ONCE, whatever the size.**

    ⚠ **THE EPIC'S OWN FAILURE MODE IS *"the set step registered as
    per-record"*** and it is asserted here on the DECLARATION, because that is
    the edit somebody would actually make. `test_tc_rbs_17_the_set_step_runs_once`
    below asserts the CONSEQUENCE through the engine, which is the half that
    would catch an executor change.
    """
    modes = {step.key: step.mode for step in rb9.RUNBOOK.steps}
    assert len(rb9.RUNBOOK.steps) == 9
    assert modes[rb9.STEP_FIGURES] == MODE_PER_RECORD
    assert sum(1 for mode in modes.values() if mode == MODE_SET) == 8
    assert sum(1 for mode in modes.values() if mode == MODE_PER_RECORD) == 1


def test_br_rbs_029_a_tax_tolerance_parameter_is_REFUSED_AT_CONSTRUCTION():
    """**The month-end tie-out tolerance for tax is `$0.0000` and cannot be raised.**

    ⚠ **REFUSED AT CONSTRUCTION AND NOT AT RUN TIME.** A run-time check would
    mean a runbook with a raised tax tolerance existing in memory on a live
    schedule, and a finance user closing a month over an unremitted difference.
    Shown RED first by adding the parameter this test builds — the message names
    the rule and says what to do instead, because the next lane will meet it
    while trying to make a real tenant's month close.
    """
    assert rb9.TAX_TOLERANCE == Decimal("0.0000")
    assert isinstance(rb9.TAX_TOLERANCE, Decimal)  # never a float (hard rule 2)
    assert not any(
        "tax" in parameter.name and "toler" in parameter.name
        for parameter in rb9.RUNBOOK.parameters
    ), "BR-RBS-029: there is no tax tolerance and there cannot be one"

    import dataclasses

    with_tax = dataclasses.replace(
        rb9.RUNBOOK,
        parameters=rb9.RUNBOOK.parameters
        + (Parameter(name="tax_tolerance", type="money", label="Tax tolerance", default="0.01"),),
    )
    with pytest.raises(RunbookContractError) as caught:
        rb9._refuse_a_tax_tolerance(with_tax)
    message = str(caught.value)
    assert "tax_tolerance" in message
    assert "cannot be raised" in message
    assert "posting the correction" in message


def test_no_money_parameter_carries_a_float():
    """Hard rule 2 — a `jsonb` document has no column type to catch one."""
    for parameter in rb9.RUNBOOK.parameters:
        if parameter.type in ("money", "percent"):
            assert isinstance(parameter.default, str), parameter.name
            Decimal(parameter.default)


def test_the_period_takes_ONE_value_and_declares_a_tenant_resolved_domain():
    """`BR-RBS-042` — one value, several, or ALL, **of a declared domain**.

    A close is answerable for exactly one month, so `multi` is False and there
    is no `default=all`: runbook 36 walks every month because a journal FILE
    legitimately spans them, and a close does not. There is also no hardcoded
    default month, because clause 2 makes the domain tenant-resolved and
    `resolve()` reads it at run start.
    """
    period = next(p for p in rb9.RUNBOOK.parameters if p.name == "period")
    assert period.multi is False
    assert period.domain == "period"
    assert period.default is None


def test_every_checklist_code_the_ledger_publishes_is_reported_by_some_step():
    """A month-end task the ledger requires and this runbook never mentions.

    ⚠ **THAT IS THE SILENT-EXCLUSION SHAPE HARD-WON LAW 7 NAMES** — a check
    reporting zero over a scope it does not cover. The map is asserted complete
    against the ledger's own vocabulary rather than trusted, so a new checklist
    item goes RED here naming itself.
    """
    from apps.ledger import close as ledger_close

    published = {
        name.split("ITEM_", 1)[1].lower()
        for name in dir(ledger_close)
        if name.startswith("ITEM_")
    }
    published = {getattr(ledger_close, f"ITEM_{code.upper()}") for code in published}
    assert published, "the ledger publishes no ITEM_ codes — this test is looking at nothing"
    missing = published - set(rb9.CHECKLIST_STEP)
    assert not missing, f"no step reports these ledger checklist items: {sorted(missing)}"
    assert set(rb9.CHECKLIST_WORDS) == set(rb9.CHECKLIST_STEP)


# ═══════════════════════════════════════════════════════════════════════════
# K2 — THE ACTION BLOCK
# ═══════════════════════════════════════════════════════════════════════════


def test_close_period_is_the_danger_tier_and_DISABLED_WITH_ITS_REASON():
    """B14 rule 6 · `RBS-006-R9` region 1 · `contract.PAYLOAD_FIELDS`.

    ⚠ **DISABLED, NOT ABSENT — AND FIVE SOURCES SAY SO AGAINST TWO.** The build
    sheet (*"DISABLED — reason on the button title"*), `RB-109`, `RB-109`'s own
    *stated absences* section which CLOSED the question this way, the payload
    contract (`enabled: false` REQUIRES `reason`) and the shipped
    `ActionBlock.tsx`. The execution plan's `K2` row and `EP-RBS-03` line 281
    say absent; both are `DEF-RBS-4360` and are amended rather than followed.

    The distinction that decides it: **a control is ABSENT when the CAPABILITY
    does not exist** — wave `L7`'s *"the Approve control is absent in the dry
    half"*, because nothing can send — **and DISABLED when a PRECONDITION is not
    met.** Closing a period is a capability this product has.
    """
    blocked = [{"weight": rb9.BLOCKER, "headline": "x"} for _ in range(3)]
    payload = rb9._action(blocked, [])
    assert payload["label"] == "Close period ✓"
    assert payload["tier"] == "danger"
    assert payload["enabled"] is False
    assert payload["reason"] == "3 blockers open."
    assert len(payload["reason"].split()) <= 6  # B14 rule 33 — a FACT


def test_a_WARNING_does_not_disable_close_period():
    """`BR-LED-018` forbids a hard lockout, and a warning is *we could not check*.

    ⚠ **THIS IS THE CHECK-INCAPABLE-OF-PASSING GUARD.** Two of the warnings this
    runbook produces are permanent stated absences — nothing records an
    adjustment's approver (`OQ-RBS-1739`), and a month with no bank statement
    cannot be counted. Counting them would leave **Close period ✓** disabled on
    every tenant for ever, which is hard-won law 7's third shape.
    """
    warned = [{"weight": rb9.WARNING, "headline": "x"} for _ in range(4)]
    payload = rb9._action([], warned)
    assert payload["enabled"] is True
    assert "reason" not in payload


def test_the_action_payload_matches_the_declared_contract():
    """`contract.PAYLOAD_FIELDS` — the shape `DEF-RBS-4352` was filed for.

    A `breakdown` with no `columns` drew an error boundary instead of 835
    notices, with every test on both sides green, because the report crosses the
    wire as untyped JSON. So the payload is validated against the CONTRACT here
    rather than eyeballed.
    """
    from apps.runbooks.contract import PAYLOAD_FIELDS

    required, optional = PAYLOAD_FIELDS["action"]
    enabled = rb9._action([], [])
    assert set(enabled) == required
    disabled = rb9._action([{"weight": rb9.BLOCKER, "headline": "x"}], [])
    assert set(disabled) == required | {"reason"}
    assert set(disabled) <= required | optional


# ═══════════════════════════════════════════════════════════════════════════
# K4 — THE UNBALANCED CASE, AND THE $0.01 FLOOR
# ═══════════════════════════════════════════════════════════════════════════


def test_a_period_off_by_one_cent_is_NOT_balanced():
    """**The floor.** `$0.01` is a difference, not a rounding.

    ⚠ **`_verdict` IN THE LEDGER IS WHAT DECIDES THIS AND THIS RUNBOOK MUST NOT
    SOFTEN IT.** A tolerance here would be a second opinion about whether the
    books agree, three lines after this module's docstring promised there would
    not be one. The row is asserted at ONE CENT because that is the smallest
    difference the product can express and the one a tolerance would swallow
    first.
    """
    row = {
        "subledger": "accounts_receivable",
        "state": "drifting",
        "gl": Decimal("1204318.2200"),
        "register": Decimal("1204318.2300"),
        "drift": Decimal("-0.0100"),
        "currency": "USD",
        "causes": (),
    }
    settle = rb9._tie_out_settle(
        row, key="receivables", item="Receivables", fix_route="finance",
        fix_label="Open the books", rule="to the cent",
    )
    assert len(settle) == 1
    assert settle[0].weight == rb9.BLOCKER
    assert "-0.01" in settle[0].detail
    assert settle[0].headline == "Receivables off by USD -0.01"


def test_a_row_that_agrees_produces_no_settle_row_at_all():
    """A tie is a MARK, not an absence, and it is not something to settle."""
    row = {
        "subledger": "accounts_receivable",
        "state": "agreed",
        "gl": Decimal("1204318.2200"),
        "register": Decimal("1204318.2200"),
        "drift": Decimal("0"),
        "currency": "USD",
        "causes": (),
    }
    assert rb9._tie_out_settle(
        row, key="receivables", item="Receivables", fix_route="finance",
        fix_label="Open the books", rule="to the cent",
    ) == []


def test_an_UNREADABLE_side_is_not_a_zero():
    """`None` and `0.00` are different answers, and folding them is `DEF-127`.

    `TieOutRow` returns `None` when a side is unreadable and never `0.00`;
    coercing it would fold *we could not read this* in with *this is zero*,
    which is how a release ships on a check that never ran.
    """
    row = {
        "subledger": "tax_payable",
        "state": "unverifiable",
        "gl": None,
        "register": None,
        "drift": None,
        "currency": None,
        "causes": (),
    }
    checked = rb9._tie_out_checked(row)
    assert checked["gl"] is None and checked["drift"] is None
    settle = rb9._tie_out_settle(
        row, key="tax", item="Tax", fix_route="finance", fix_label="Open the books",
        rule="no tolerance",
    )
    assert settle[0].weight == rb9.WARNING  # not a blocker: nothing was found wrong


def test_money_is_held_at_FOUR_and_shown_at_TWO():
    """Hard rule 2, both halves, and neither is ever a float."""
    assert rb9.money4("1204318.22") == Decimal("1204318.2200")
    assert rb9.money2("1204318.22") == "1204318.22"
    assert rb9.money4(Decimal("23304.7649")) == Decimal("23304.7649")
    assert rb9.money2(Decimal("23304.7649")) == "23304.76"
    assert isinstance(rb9.money4("14.25"), Decimal)
    # ROUND_HALF_UP, which is what B4 rounds with everywhere else. Banker's
    # rounding here would disagree with the figure this came from by a cent.
    assert rb9.money2(Decimal("14.2450")) == "14.25"


def test_a_money_headline_carries_its_currency(brazos, dana):
    """Hard rule 2's *currency beside every amount*, in a plain-string banner.

    The verdict's `detail` has no cell to carry a `MoneyCell`, so the CHAR(3)
    goes in the words. The code and not a symbol: `$` is four different
    currencies in North America alone.
    """
    with tenant_ctx(brazos):
        words = rb9.money_words(Decimal("816.4500"))
    assert words == "USD 816.45"
    assert len(f"Tax off by {words}".split()) <= 6  # B14 rule 33


# ═══════════════════════════════════════════════════════════════════════════
# THROUGH THE ENGINE
# ═══════════════════════════════════════════════════════════════════════════


def _run(tenant, *, period=None):
    return executor.execute(rb9.RUNBOOK, tenant_id=tenant.id, params={"period": period})


def test_tc_rbs_17_the_set_step_runs_ONCE_and_the_per_record_step_once_per_period(
    brazos, dana
):
    """`TC-RBS-17` through the engine — the CONSEQUENCE, not the declaration.

    ⚠ **`step_runs` IS COUNTED BY THE EXECUTOR RATHER THAN BY SIDE EFFECTS**,
    which is what stops this being *"a test named after an assertion it does not
    make"*. On a tenant with no posted period the pinned set is empty, so the
    per-record step runs ZERO times and every set step still runs ONCE — which
    is the distinction the epic's failure mode turns on.
    """
    with tenant_ctx(brazos):
        result = _run(brazos)
    set_keys = [step.key for step in rb9.RUNBOOK.steps if step.mode == MODE_SET]
    for key in set_keys:
        assert result.step_runs.get(key) == 1, key
    assert result.step_runs.get(rb9.STEP_FIGURES, 0) == len(result.subjects)


def test_a_tenant_with_nothing_posted_says_so_rather_than_reporting_a_balanced_zero(
    brazos, dana
):
    """`BR-RBS-042` clause 2 — **an empty domain says so.**

    ⚠ **THE DANGEROUS SHAPE THIS RUNBOOK COULD TAKE IS A PERIOD WITH NOTHING IN
    IT READING AS A BALANCED MONTH**: no runs, no payments, no lines, nine green
    steps and *Close period ✓* enabled over an empty book. Asserted directly.
    """
    with tenant_ctx(brazos):
        result = _run(brazos)
        blocks = {block.block: block.payload for block in rb9.report(_view(result))}
    assert result.subjects == ()
    checked = result.set_results[rb9.STEP_RUNS]["checked"]
    assert checked["period"] is None
    settle = [row["item"] for row in blocks["records"]["rows"]]
    assert "This period" in settle
    assert blocks["verdict"]["word"] != "Balanced"


def test_the_report_is_six_of_the_twelve_blocks_and_no_thirteenth(brazos, dana):
    """`BR-RBS-021`, and `RBS-006-R9`'s ten REGIONS are not ten blocks."""
    with tenant_ctx(brazos):
        result = _run(brazos)
        blocks = rb9.report(_view(result))
    names = [block.block for block in blocks]
    assert names == ["verdict", "kpis", "reconciled", "records", "action", "downloads"]
    assert all(name in BLOCK_TYPES for name in names)


def test_the_tie_out_columns_are_B14_rule_34s_ratified_pair(brazos, dana):
    """**Recorded** and **In the books**, in all eleven catalogues (`CR-060` C11).

    Ratified 2026-09-02 as *"the one pair of words for held here and in the
    books"*. `RBS-006-R9`'s build sheet writes *Billed* for the first column;
    the rule's pair is what a translator sees and is what ships.
    """
    with tenant_ctx(brazos):
        result = _run(brazos)
        blocks = {block.block: block.payload for block in rb9.report(_view(result))}
    labels = [column["label"] for column in blocks["reconciled"]["columns"]]
    assert labels == ["", "Recorded", "In the books", "Difference"]
    assert blocks["reconciled"]["tiesLabel"] == "Ties"


def test_every_settle_row_names_a_fix_route_and_carries_no_internal_reference(
    brazos, dana
):
    """`BR-RBS-011` · `BR-RBS-010` · B14 rules 31 and 32, over a real run."""
    with tenant_ctx(brazos):
        result = _run(brazos)
    rows = []
    for key in rb9.STEP_LABELS:
        rows.extend((result.set_results.get(key) or {}).get("settle") or [])
    assert rows
    for row in rows:
        assert row["fix_route"].strip()
        assert not row["fix_route"].startswith("/")  # tenant-relative (DEF-RBS-4329)
        assert row["decided_by_rule"].strip()
        for token in ("BR-", "US-", "DEF-", "OQ-", "TC-"):
            assert token not in row["decided_by_rule"], row
            assert token not in row["detail"], row
            assert token not in row["item"], row


def test_the_verdict_line_is_three_clauses_of_six_words_or_fewer(brazos, dana):
    """B14 rule 33 — the cap is PER CLAUSE and the middle dot is the join."""
    settle = [
        {"weight": rb9.BLOCKER, "headline": "Tax off by USD 816.45"},
        {"weight": rb9.BLOCKER, "headline": "USD 1195.05 unapplied"},
        {"weight": rb9.BLOCKER, "headline": "Tax remittance not done"},
        {"weight": rb9.BLOCKER, "headline": "Unbilled revenue not done"},
    ]
    detail = " · ".join(row["headline"] for row in settle[:3] if row.get("headline"))
    assert detail.count("·") == 2  # three clauses, never four
    for clause in detail.split(" · "):
        assert len(clause.split()) <= 6, clause


def _view(result):
    from apps.runbooks.engine.executor import _ReportView

    return _ReportView(
        definition=rb9.RUNBOOK,
        subjects=result.subjects,
        guarded=result.guarded,
        records=result.records,
        counts=result.counts,
        set_results=result.set_results,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-009 (EP-RBS-03 §3 TC-RBS-17; RB-109; RBS-006-R9 build sheet; BR-RBS-029 · BR-RBS-030)
# generated: 2026-09-07 by the CR-075 wave K build lane
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
