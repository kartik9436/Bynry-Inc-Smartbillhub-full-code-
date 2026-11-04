# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-025 (EP-RBS-05) — CR-075 wave S, runbook 13.
# Rules:    BR-RBS-002 · BR-RBS-009 · BR-RBS-010 · BR-RBS-019 · BR-RBS-020 ·
#           BR-RBS-021 · BR-RBS-023 · RBR-16 · CLAUDE.md hard rules 2 and 4 ·
#           B14 rules 31, 32, 33
# Tests:    this file. The PostgreSQL half is tests/test_rbs_check_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/payment_trace.py
# ───────────────────────────────────────────────────────
"""Runbook 13, against the rules rather than against itself.

⚠ **THE CASE THE CARD IS ABOUT IS THE MIS-KEYED ONE**: a payment applied to
Alvarez because both account numbers end 4471. The seeded utility can produce a
payment on another account, and it cannot produce two accounts whose numbers end
the same four digits — so the *same last four* sentence, the reversal and the
landed-file branch live here.
"""

import datetime as dt
from decimal import Decimal

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import payment_trace as pt
from apps.runbooks.engine import executor

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 9, 15)
MINE = "acc-okonkwo"
THEIRS = "acc-alvarez"


def _payment(
    payment_no="PY-260912-0088",
    account_id=THEIRS,
    account_no="AC-2026-04471",
    amount="182.400000",
    posted_on="2026-09-12",
    status="cleared",
    reverses=None,
):
    return {
        "payment_no": payment_no,
        "payment_id": "pay-1",
        "account_id": account_id,
        "account_no": account_no,
        "amount": amount,
        "currency": "USD",
        "status": status,
        "type": "cheque",
        "purpose": "bill",
        "confirmation": "88213",
        "memo": None,
        "posted_on": posted_on,
        "cleared_on": posted_on,
        "reverses_payment_id": reverses,
        "reversal_reason": None,
        "moved_from_payment_id": None,
        "deposit_batch_id": None,
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the five reads runbook 13 makes."""
    state = {
        "payments": [_payment()],
        "facts": {"account_no": "AC-2025-14471", "label": "Okonkwo, D.", "unit_id": "u1"},
        "credit": None,
        "batch": None,
    }

    def _matching(**kwargs):
        rows = list(state["payments"])
        account_ids = kwargs.get("account_ids")
        if account_ids:
            rows = [one for one in rows if one["account_id"] in [str(x) for x in account_ids]]
        return rows

    monkeypatch.setattr(pt.payments_seam, "payments_matching", _matching)
    monkeypatch.setattr(pt.payments_seam, "account_credit", lambda account_id: state["credit"])
    monkeypatch.setattr(pt.payments_seam, "import_batch", lambda batch_id: state["batch"])
    monkeypatch.setattr(pt.customers_seam, "account_facts", lambda account_id: state["facts"])
    monkeypatch.setattr(pt.tenancy_seam, "today", lambda: TODAY)
    return state


def _run(params=None):
    definition = pt.RUNBOOK
    ctx = executor.build_context(
        definition,
        tenant_id="t",
        params={
            "account": MINE,
            "amount": "182.40",
            "around": "2026-09-12",
            "within_days": 3,
            "look_back": 90,
            "amount_tolerance": "0.0100",
            "search_other_accounts": True,
            "include_reversed_and_returned": True,
            "include_todays_batch": True,
            **(params or {}),
        },
    )
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _cells(result):
    return {one["label"]: one for one in _blocks(result)["chain"]["cells"]}


# ── the declaration ───────────────────────────────────────────────────────


def test_it_is_a_check_and_moves_nothing(seams):
    """Hard rule 4 — a payment is append-only and moving one is payments' act."""
    assert pt.RUNBOOK.is_check
    assert pt.RUNBOOK.ports == ()
    assert pt.RUNBOOK.writes_nothing()


# ── the card's headline case ──────────────────────────────────────────────


def test_a_payment_on_another_account_ending_the_same_four_says_so(seams):
    """*"Found: $182.40 on 12 Sep, applied to account ending 4471 — Alvarez,
    not Okonkwo. Same last four."*"""
    result = _run()
    assert result.records[0].outcome == pt.FOUND_ELSEWHERE
    assert "same four digits" in result.records[0].reason
    facts = {one["label"]: one["value"] for one in _blocks(result)["facts"]["rows"]}
    assert facts["Applied to"]["text"] == "AC-2026-04471"
    assert facts["Likely cause"]["text"] == (
        "The remittance slip carried the wrong account number."
    )


def test_the_move_button_is_enabled_only_when_it_is_on_another_account(seams):
    assert _blocks(_run())["action"] == {
        "label": "Move payment",
        "tier": "primary",
        "enabled": True,
    }
    seams["payments"] = [_payment(account_id=MINE, account_no="AC-2025-14471")]
    action = _blocks(_run())["action"]
    assert action["enabled"] is False
    assert action["reason"] == "It is already on this account"
    # B14 rule 33 — a refusal caps at five or six words.
    assert len(action["reason"].split()) <= 6


def test_a_payment_on_a_different_account_with_different_digits_still_reads_plainly(seams):
    seams["payments"] = [_payment(account_no="AC-2026-00999")]
    result = _run()
    assert result.records[0].outcome == pt.FOUND_ELSEWHERE
    assert result.records[0].reason.endswith("It is on another account.")


# ── the chain ─────────────────────────────────────────────────────────────


def test_the_chain_stops_when_found_and_the_rest_read_not_needed(seams):
    """`RB-113`'s design note, and *Not needed* is not *Never reached*."""
    cells = _cells(_run())
    assert cells["This account"]["note"] == "Nothing"
    assert cells["Elsewhere"]["state"] == "bad"
    assert [cells[one]["note"] for one in ("Reversed", "Unapplied", "Today's batch")] == [
        "Not needed"
    ] * 3


def test_every_chain_state_is_one_the_renderer_has(seams):
    for cell in _blocks(_run())["chain"]["cells"]:
        assert cell["state"] in {"ok", "bad", "notReached", "pending"}


def test_a_search_with_no_account_says_the_first_step_was_not_checked(seams):
    """⚠ **A FIRST BUILD SEARCHED THE WHOLE TENANT IN STEP 1 AND THEN REPORTED
    THE HIT AS *"It is on this account"*** — a sentence about an account nobody
    had named. The card's second scope is a search by amount and date *"when the
    caller does not know which account it landed on"*."""
    result = _run({"account": None})
    cells = _cells(result)
    assert cells["This account"]["note"] == "Not checked"
    assert cells["Elsewhere"]["state"] == "bad"
    assert result.records[0].outcome == pt.FOUND_HERE


def test_searching_other_accounts_can_be_switched_off(seams):
    result = _run({"search_other_accounts": False})
    assert _cells(result)["Elsewhere"]["note"] == "Not needed"
    assert result.records[0].outcome == pt.NOT_FOUND


# ── the other three places a payment can be ───────────────────────────────


def test_a_reversed_payment_is_found_and_named(seams):
    """*"I paid"* is true of a cheque that bounced."""
    seams["payments"] = [_payment(account_id=MINE, account_no="AC-2025-14471", reverses="pay-0")]
    result = _run()
    assert result.records[0].outcome == pt.FOUND_HERE  # step 1 sees it first


def test_unapplied_cash_is_a_different_answer_from_not_found(seams):
    seams["payments"] = []
    seams["credit"] = "182.4000"
    result = _run()
    assert result.records[0].outcome == pt.FOUND_UNAPPLIED
    assert "has not placed it on a bill" in result.records[0].reason


def test_a_negative_credit_is_never_read_as_money_held(seams):
    """PO ruling 2026-08-11 (`OQ-132`) — a negative credit is a real debt."""
    seams["payments"] = []
    seams["credit"] = "-40.0000"
    result = _run()
    assert result.records[0].outcome == pt.NOT_FOUND


def test_a_landed_file_that_nobody_named_reads_not_checked(seams):
    """⚠ `payments` publishes no list of import batches (`S-15`), so *not
    checked* and *nothing found* are different answers and this says which."""
    seams["payments"] = []
    result = _run()
    checked = (result.set_results.get(pt.STEP_BATCH) or {}).get("checked") or {}
    assert checked["checked"] is False
    assert checked["batches_this_module_can_enumerate"] == 0
    assert _cells(result)["Today's batch"]["note"] == "Not checked"


def test_a_named_landed_file_is_searched(seams):
    seams["payments"] = []
    seams["batch"] = {
        "currency": "USD",
        "rows": [{"amount": "182.40", "account_no": "AC-2025-14471"}],
    }
    result = _run({"batch": "batch-1"})
    assert result.records[0].outcome == pt.FOUND_IN_BATCH
    assert "has not been applied yet" in result.records[0].reason


# ── the report ────────────────────────────────────────────────────────────


def test_every_block_name_is_one_of_the_twelve(seams):
    assert {block["block"] for block in _run().report} <= set(BLOCK_TYPES)


def test_money_reaches_the_report_at_four_decimals_and_the_sentence_at_two(seams):
    """⚠ `payments.amount` is a `NUMERIC(18,6)` container, so the seam hands
    over `182.400000`. Hard rule 2: four stored, two shown."""
    result = _run()
    facts = {one["label"]: one["value"] for one in _blocks(result)["facts"]["rows"]}
    assert facts["Amount"] == {"kind": "money", "amount": "182.4000", "currency": "USD"}
    assert "182.40 USD" in result.records[0].reason
    assert "182.400000" not in str(result.report)


def test_nothing_found_says_what_to_try_next(seams):
    seams["payments"] = []
    blocks = _blocks(_run())
    assert blocks["verdict"]["word"] == "Not found"
    assert blocks["verdict"]["detail"] == "Try a wider window, or search without the account."


def test_no_database_id_reaches_a_drawn_value(seams):
    result = _run()
    drawn = [one["value"] for one in _blocks(result)["facts"]["rows"]]
    assert all(THEIRS not in str(one) for one in drawn)
    assert all("pay-1" not in str(one) for one in drawn)


def test_the_sentence_tone_is_one_the_renderer_has(seams):
    assert _blocks(_run())["verdict"]["tone"] in {"success", "warning", "danger"}
