# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-021 (EP-RBS-05) — CR-075 wave S, runbook 6.
# Rules:    BR-RBS-002 · BR-RBS-009 · BR-RBS-010 · BR-RBS-011 · BR-RBS-019 ·
#           BR-RBS-020 · BR-RBS-021 · BR-RBS-023 · BR-RBS-027 · BR-BIL-037 /
#           BR-BIL-040 (the pipeline's stages) · B14 rules 31, 32, 33
# Tests:    this file. The PostgreSQL half is tests/test_rbs_check_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/why_not_billed.py
# ───────────────────────────────────────────────────────
"""Runbook 6, against the rules rather than against itself.

⚠ **THE CASE THAT MATTERS MOST IS THE ONE ABOUT WORDS.** A break carries
billing's own reason code and a `detail` that quotes rule ids by name — the
seeded one reads *"BR-BIL-015 makes that a choice"* — and both would reach a
clerk if this runbook drew them. B14 rule 32 forbids it, nothing mechanical
checks it, and the first build title-cased the code into *"Missing read
undecided at calculate."* before the real database showed it up.
"""

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import why_not_billed as wnb
from apps.runbooks.engine import executor

pytestmark = pytest.mark.django_db

RUN = "run-1"


def _break(account_id="a1", stage="measure-consumption", reason="missing_read_undecided_at_calculate"):
    return {
        "id": "brk-1",
        "account_id": account_id,
        "account_no": "AC-2026-00012",
        "stage": stage,
        "reason": reason,
        "detail": (
            "account AC-2026-00012: water still has no usable read and no decision. "
            "BR-BIL-015 makes that a choice — estimate it, hold the account, or bill "
            "without the service."
        ),
        "retryable": True,
        "resolution": None,
        "job_id": None,
        "raised_at": "2026-07-31",
        "updated_at": "2026-07-31",
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the five reads runbook 6 makes."""
    state = {
        "outcome": {
            "run_id": RUN,
            "run_no": "RUN-0002",
            "status": "draft",
            "bill_type": "cycle",
            "cycle_id": "c1",
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "breaks": [_break()],
            "breaks_by_stage": {"measure-consumption": ["AC-2026-00012"]},
            "exclusions": [],
            "billed_account_ids": ["a2", "a3"],
        },
        "facts": {"account_no": "AC-2026-00012", "label": "Luca Lindqvist", "unit_id": "u1"},
        "dispute": False,
        "bills": [
            {
                "bill_id": "b1",
                "period_end": "2026-06-30",
                "total": "96.4000",
                "currency": "USD",
                "lines": [],
            }
        ],
        "refusal": {"reason": "missing_read_undecided_at_calculate", "service_code": "water"},
    }
    monkeypatch.setattr(
        wnb.billing_seam, "bill_run_outcome", lambda run_id: dict(state["outcome"]) if state["outcome"] else None
    )
    monkeypatch.setattr(
        wnb.billing_seam,
        "issued_bills_for_account",
        lambda account_id, limit=14: list(state["bills"]),
    )
    monkeypatch.setattr(
        wnb.billing_seam,
        "price_account_as_the_run_would",
        lambda **kwargs: {"priced": None, "refusal": state["refusal"]}
        if state["refusal"]
        else {"priced": {"total": 1}, "refusal": None},
    )
    monkeypatch.setattr(wnb.customers_seam, "account_facts", lambda account_id: state["facts"])
    monkeypatch.setattr(
        wnb.metering_seam, "unit_has_dispute_hold", lambda unit_id: state["dispute"]
    )
    return state


def _run(params=None):
    definition = wnb.RUNBOOK
    ctx = executor.build_context(
        definition, tenant_id="t", params={"bill_run": RUN, **(params or {})}
    )
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


# ── the declaration ───────────────────────────────────────────────────────


def test_it_is_a_check_and_holds_no_ports(seams):
    assert wnb.RUNBOOK.is_check
    assert wnb.RUNBOOK.ports == ()


def test_it_triggers_manually_and_on_a_completed_bill_run(seams):
    """The card's own trigger row. Unlike the two landed-batch events, this one
    is already in `models.EVENT_KINDS`."""
    assert "manual" in wnb.RUNBOOK.triggers
    assert "bill_run.completed" in wnb.RUNBOOK.triggers


# ── the stop ──────────────────────────────────────────────────────────────


def test_no_run_stops_the_runbook_with_a_sentence(seams):
    seams["outcome"] = None
    result = _run()
    stop = result.set_results[wnb.STEP_SCOPE]["stop"]
    assert stop["headline"] == "No bill run to explain."
    blocks = _blocks(result)
    assert set(blocks) == {"verdict", "sentence", "records"}
    assert "failed" not in str(result.report).lower()


# ── the scope: one account, or the break list ─────────────────────────────


def test_the_break_list_variant_pins_every_broken_account(seams):
    seams["outcome"]["breaks"] = [_break("a1"), _break("a9", reason="unit_has_no_plan", stage="resolve-subscription")]
    result = _run()
    assert {one.subject_id for one in result.subjects} == {"a1", "a9"}
    assert len(result.records) == 2


def test_an_excluded_account_is_pinned_too_and_reads_as_held(seams):
    """A deliberate exclusion is not a fault and must not read as one."""
    seams["outcome"]["breaks"] = []
    seams["outcome"]["exclusions"] = [
        {"account_id": "a5", "reason_code": "storm_hold", "detail": None, "resolved_by_a_later_run": False}
    ]
    result = _run()
    assert [one.subject_id for one in result.subjects] == ["a5"]
    assert result.records[0].outcome == wnb.OUTCOME_HELD
    assert "Held on purpose" in result.records[0].reason


def test_one_account_can_be_asked_about_on_its_own(seams):
    result = _run({"account": "a1"})
    assert [one.subject_id for one in result.subjects] == ["a1"]


def test_an_account_that_billed_says_so(seams):
    """A clerk who picked the wrong account must be told, not shown green cells."""
    result = _run({"account": "a2"})
    assert result.records[0].outcome == wnb.OUTCOME_BILLED
    assert _blocks(result)["sentence"]["text"] == "This account billed on this run."


# ── the answer ────────────────────────────────────────────────────────────


def test_the_stage_decides_the_step_and_the_chain_draws_seven_cells(seams):
    result = _run()
    cells = _blocks(result)["chain"]["cells"]
    assert len(cells) == 7
    assert [one["state"] for one in cells] == [
        "ok",
        "ok",
        "ok",
        "bad",
        "notReached",
        "notReached",
        "ok",
    ]
    assert cells[4]["note"] == "Never reached"


def test_a_plan_break_stops_at_step_three_instead(seams):
    seams["outcome"]["breaks"] = [_break(reason="unit_has_no_plan", stage="resolve-subscription")]
    result = _run()
    assert result.records[0].data["position"] == 3
    assert result.records[0].reason == "No plan is assigned to this unit."
    assert result.records[0].fix_route == "plans-rates/plans"


def test_the_sentence_names_the_step_the_service_and_the_window(seams):
    """`RB-106`'s own deliverable: *"Stopped at step 4 — no Sewer read between
    18 Aug and 17 Sep. Last billed 20 Aug."*"""
    text = _blocks(_run())["sentence"]["text"]
    assert text.startswith("Stopped at step 4 —")
    assert "No water read between 1 Jul and 31 Jul" in text
    assert "Last billed 30 Jun." in text


def test_no_reason_code_and_no_rule_id_reaches_a_drawn_cell(seams):
    """⚠ **THE FIRST BUILD TITLE-CASED THE CODE.** *"Missing read undecided at
    calculate."* is the pipeline's word on a clerk's screen (B14 rule 32), and
    the break's own `detail` quotes `BR-BIL-015` by name."""
    result = _run()
    drawn = [_blocks(result)["sentence"]["text"], _blocks(result)["verdict"]["count"]]
    for row in _blocks(result)["records"]["rows"]:
        drawn.extend(str(cell.get("text") or cell.get("label") or "") for cell in row["cells"].values())
    for cell in _blocks(result)["chain"]["cells"]:
        drawn.append(str(cell.get("note") or ""))
    for text in drawn:
        assert "BR-BIL" not in text
        assert "undecided at calculate" not in text
        assert "measure-consumption" not in text


def test_the_reason_code_and_the_detail_travel_in_meta_where_nothing_draws_them(seams):
    row = _blocks(_run())["records"]["rows"][0]
    assert row["meta"]["reason_code"] == "missing_read_undecided_at_calculate"
    assert "BR-BIL-015" in row["meta"]["detail"]
    assert "BR-BIL-015" not in str(row["cells"])


def test_a_reason_this_runbook_has_no_words_for_is_named_and_counted(seams):
    """Hard-won law 7 — an unmapped reason must be visible, not silently generic."""
    seams["outcome"]["breaks"] = [_break(reason="a_reason_nobody_has_written_words_for")]
    result = _run()
    assert _checked(result, wnb.STEP_READ)["reasons_this_runbook_has_no_words_for"] == [
        "a_reason_nobody_has_written_words_for"
    ]
    assert result.records[0].reason == wnb.REASON_UNKNOWN


def test_a_chain_note_is_short_enough_to_read(seams):
    """B14 rule 33 — a refusal caps at five or six words, and `Chain.tsx` says so
    at the `note` field itself."""
    for cell in _blocks(_run())["chain"]["cells"]:
        assert len(str(cell["note"]).split()) <= 6


# ── re-price to confirm ───────────────────────────────────────────────────


def test_re_pricing_says_when_the_fix_has_landed(seams):
    """The run's break explains the past; the re-price answers *is it still
    broken*, and the two disagreeing is a finding rather than a bug."""
    seams["refusal"] = None
    result = _run()
    assert _checked(result, wnb.STEP_PRICING)["prices_cleanly_now"] == 1
    assert result.records[0].data["prices_now"] is True
    assert "prices cleanly now" in _blocks(result)["sentence"]["text"]


def test_re_pricing_can_be_switched_off_and_then_nothing_is_claimed(seams):
    """⚠ `None` means NOT ASKED and `False` means STILL REFUSED — collapsing the
    two would tell a clerk an account is broken when nobody looked."""
    result = _run({"re_price_to_confirm": False})
    assert _checked(result, wnb.STEP_PRICING)["re_price_to_confirm"] is False
    assert result.records[0].data["prices_now"] is None


def test_the_engine_supplies_the_service_the_sentence_names(seams):
    seams["refusal"] = {"reason": "missing_read_undecided_at_calculate", "service_code": "sewer"}
    assert "No sewer read" in _blocks(_run())["sentence"]["text"]


def test_with_no_service_the_sentence_still_reads(seams):
    seams["refusal"] = {"reason": "missing_read_undecided_at_calculate", "service_code": None}
    assert "No one service read" in _blocks(_run())["sentence"]["text"]


# ── step 6 · the one this product cannot answer ───────────────────────────


def test_an_account_with_no_bill_and_no_break_is_named_not_guessed(seams):
    """Nothing records a refused write, so this reports the state it CAN see."""
    seams["outcome"]["breaks"] = []
    seams["outcome"]["exclusions"] = []
    result = _run({"account": "a7"})
    assert result.records[0].outcome == wnb.OUTCOME_UNEXPLAINED
    assert result.records[0].reason == "No bill and nothing recorded either way."
    checked = _checked(result, wnb.STEP_WRITE)
    assert checked["refused_writes_recorded"] == 0
    assert checked["nothing_records_a_refused_write"] is True


# ── holds ─────────────────────────────────────────────────────────────────


def test_a_disputed_reading_is_a_hold_and_not_a_missing_read(seams):
    seams["dispute"] = True
    seams["outcome"]["breaks"] = []
    result = _run({"account": "a1"})
    assert result.records[0].outcome == wnb.OUTCOME_HELD
    assert "disputed" in result.records[0].reason
    assert _checked(result, wnb.STEP_HELD)["held_by_a_dispute"] == 1


# ── the report ────────────────────────────────────────────────────────────


def test_every_block_name_is_one_of_the_twelve(seams):
    assert {block["block"] for block in _run().report} <= set(BLOCK_TYPES)


def test_the_break_list_draws_no_chain_and_the_single_account_does(seams):
    """A chain is one account's story; seven cells over fourteen accounts would
    be seven cells about nobody."""
    assert "chain" in _blocks(_run({"account": "a1"}))
    seams["outcome"]["breaks"] = [_break("a1"), _break("a9")]
    assert "chain" not in _blocks(_run())


def test_the_chips_count_accounts_by_the_step_that_stopped_them(seams):
    seams["outcome"]["breaks"] = [
        _break("a1"),
        _break("a9", reason="unit_has_no_plan", stage="resolve-subscription"),
    ]
    chips = {one["label"]: one["count"] for one in _blocks(_run())["records"]["chips"]}
    assert chips["Plan in force"] == 1
    assert chips["A read for every service"] == 1


def test_the_sentence_tone_is_one_the_renderer_has(seams):
    """`OutcomeTone` is `success | danger | muted` — NOT the verdict's three. A
    fourth word draws the card with no rail and no tint, silently."""
    assert _blocks(_run())["sentence"]["tone"] in {"success", "danger", "muted"}
    assert _blocks(_run())["verdict"]["tone"] in {"success", "warning", "danger"}


def test_every_chain_state_is_one_the_renderer_has(seams):
    for cell in _blocks(_run())["chain"]["cells"]:
        assert cell["state"] in {"ok", "bad", "notReached", "pending"}


def test_an_account_that_never_billed_reads_pending_not_bad(seams):
    """It did not fail — nobody has established it yet."""
    seams["bills"] = []
    cells = _blocks(_run({"account": "a1"}))["chain"]["cells"]
    assert cells[-1]["state"] == "pending"
    assert cells[-1]["note"] == "Never billed"


def test_every_row_names_a_fix_route(seams):
    for row in _blocks(_run())["records"]["rows"]:
        assert row["cells"]["fix"]["to"]
        assert row["cells"]["fix"]["label"].endswith("→")
