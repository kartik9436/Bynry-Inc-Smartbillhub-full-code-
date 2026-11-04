# ── Trace ──────────────────────────────────────────────
# Rule:     **BR-CUS-1083** — PO ruling 2026-09-20, verbatim: *"The register
#           reflects reality. Today a failed visit is invisible and the case
#           looks untouched."* and *"each must move the case somewhere, not
#           merely annotate it"*. Closes `OQ-383`, open since 2026-08-25.
# Rules:    BR-CUS-039 (the ladder and its three stop reasons) · BR-CUS-037
#           (customers writes no financial table) · BR-PAY-036 (a payment never
#           auto-changes a status; the ladder stops ITSELF) · CLAUDE.md hard
#           rule 1 (tenant scoping) · rule 7 (the act writes `audit_log`)
# Impacts:  apps/customers/disconnect_visits.py ·
#           apps/customers/disconnect_record.py (`actions.visit`) ·
#           apps/customers/transfer_disconnect_api.py (`record_visit`) ·
#           apps/customers/migrations/0062_br_cus_1083_disconnect_visits.py
# ───────────────────────────────────────────────────────
"""The crew attended and did not cut — what is recorded, and where the case goes.

⚠ **EVERY CASE HERE WAS SHOWN RED FIRST, IN PYTEST**, which is the harness that
will run it — not by executing a file, which exercises `__main__` and a path
`run_gates`/`pytest` never use (hard-won law 7's 2026-09-04 clause). The break
used for each one is named in its own docstring so the next reader can repeat it
in a single edit.

⚠ **THE WHOLE FILE WAS RED BEFORE THE FEATURE EXISTED**, for the most direct
reason possible: `apps.customers.disconnect_visits` did not exist and the import
at the top of this file raised `ModuleNotFoundError`. That is the proof that
matters for a capability that was previously absent rather than wrong.
"""
from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnect_record, disconnect_visits, disconnects

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    audit_rows,
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_w7_cut_reconnect import CUT_ON, TODAY, _scheduled

pytestmark = pytest.mark.django_db

VISITED_ON = date(2026, 8, 24)


def _case(account_id):
    return disconnects.open_case_for(account_id)


def _any_case(account_id):
    """The case whatever state it is in.

    ⚠ **`open_case_for` EXCLUDES THE THREE CLOSED STATES**, so a case this file
    has just STOPPED reads as no case at all through it. That is the product
    behaving correctly (`CLOSED_CASE_STATES` is what lets a fresh case be opened
    later) and it is a trap for a test that wants to look at what it just did.
    """
    return (
        disconnects.DisconnectCase.objects.filter(account_id=account_id)
        .order_by("-created_at")
        .first()
    )


# ════════════════════════════════════════════════════════════════════════════
# THE VOCABULARY — the PO's four, and a fifth refused BY NAME
# ════════════════════════════════════════════════════════════════════════════
def test_the_four_outcomes_are_the_pos_own_and_the_set_is_closed():
    """RED first by asserting the tuple before the module existed.

    The four words are the PO's, in their ruling of 2026-09-20. A fifth is a
    decision, not a string — `STOP_REASONS`' reasoning, one table over.
    """
    assert disconnect_visits.VISIT_OUTCOMES == (
        "locked_gate",
        "access_refused",
        "paid_at_door",
        "disputed",
    )


def test_a_fifth_outcome_is_refused_by_name(brazos, marcus, monkeypatch):
    """RED by removing the membership check — then any string is recordable.

    A refusal that names the four is the difference between a guard and a
    `TypeError` at the database layer.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        with pytest.raises(disconnects.DisconnectRuleError) as refused:
            disconnect_visits.record_outcome(
                marcus, account["id"], on_date=VISITED_ON, outcome="dog_loose"
            )
        assert refused.value.code == "visit_outcome_unknown"
        assert "locked_gate" in str(refused.value)


def test_the_database_refuses_a_fifth_outcome_too(brazos, marcus, monkeypatch):
    """RED by dropping `ck_disconnect_visit_outcome` from the migration.

    ⚠ **THE SERVICE GUARD IS NOT THE ONLY GUARD, AND THAT IS THE POINT.** An
    import or a fixture writes rows without going through `record_outcome`, and
    a vocabulary held only in Python is a vocabulary a CSV can extend.

    ⛔ **POSTGRES ONLY.** SQLite does not enforce a CHECK added by Django's
    `constraints`, so this case SKIPS on the default suite rather than passing
    there and lying (law 7's *incapable of failing* shape).
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip("CHECK constraints are only enforced on the PostgreSQL tier")
    from django.db import IntegrityError, transaction

    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        case = _case(account["id"])
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                disconnect_visits.DisconnectVisit.objects.create(
                    tenant_id=case.tenant_id,
                    case=case,
                    visited_on=VISITED_ON,
                    outcome="dog_loose",
                )


# ════════════════════════════════════════════════════════════════════════════
# THE MOVE — the half the PO ruled on: *"each must move the case somewhere"*
# ════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "outcome",
    [
        disconnect_visits.OUTCOME_LOCKED_GATE,
        disconnect_visits.OUTCOME_ACCESS_REFUSED,
        disconnect_visits.OUTCOME_PAID_AT_DOOR,
    ],
)
def test_a_recorded_visit_moves_the_case_and_the_row_is_the_evidence(
    brazos, marcus, monkeypatch, outcome
):
    """THE CASE THIS FILE EXISTS FOR, and the one a "simplification" breaks.

    RED first in the most complete way: before this feature, recording anything
    was impossible and the case sat `scheduled` with `cut_scheduled_for` set to
    a date in the past — which is exactly what the assertions below deny.

    ⚠ **IT ASSERTS BOTH HALVES BECAUSE BOTH ARE THE RULING.** The ROW is the
    evidence (a crew attended on a day and found a padlock) and the CASE'S MOVE
    is *"not merely annotate it"*. A lane deriving the state from the latest
    visit instead of writing it would still pass the row half and fail here.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        before = _case(account["id"])
        assert before.state == disconnects.STATE_SCHEDULED
        assert before.cut_scheduled_for == CUT_ON

        result = disconnect_visits.record_outcome(
            marcus,
            account["id"],
            on_date=VISITED_ON,
            outcome=outcome,
            note="Nobody on site; padlock on the meter box.",
        )

        # ── the evidence ────────────────────────────────────────────────────
        assert result["visit"]["outcome"] == outcome
        assert result["visit"]["visited_on"] == str(VISITED_ON)
        assert result["visit"]["clears_the_cut_date"] is True
        rows = disconnect_visits.visits_for(before)
        assert len(rows) == 1
        assert rows[0]["note"] == "Nobody on site; padlock on the meter box."

        # ── the move ────────────────────────────────────────────────────────
        after = _case(account["id"])
        assert after.state == disconnects.STATE_NOTICE_SENT
        assert after.cut_scheduled_for is None
        # ⚠ THE TIER IS UNTOUCHED — a re-schedule RESUMES rather than restarts,
        # and a lane that "reset" the ladder here would be re-serving notices
        # the customer has already had.
        assert after.tier == disconnects.TIER_3


def test_a_doorstep_dispute_stops_the_ladder_with_the_reason_that_already_exists(
    brazos, marcus, monkeypatch
):
    """RED by routing `disputed` through the clear-the-date branch.

    ⚠ **IT REUSES `STOP_REASONS` RATHER THAN MINTING A FOURTH.** Blueprint p137
    draws *Disputed · The customer is contesting the bill* as one of the three
    reasons a ladder is stopped by hand, and a doorstep dispute is that dispute.
    Minting a fourth stop reason is *"a fourth way to stop chasing a real debt"*
    and needs a ruling.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        result = disconnect_visits.record_outcome(
            marcus,
            account["id"],
            on_date=VISITED_ON,
            outcome=disconnect_visits.OUTCOME_DISPUTED,
            note="Says the meter was read wrong.",
        )
        assert result["visit"]["clears_the_cut_date"] is False
        # ⚠ `_any_case`, not `_case`: `stopped` is a CLOSED state and
        # `open_case_for` deliberately cannot see it.
        after = _any_case(account["id"])
        assert after.state == disconnects.STATE_STOPPED
        assert after.stopped_reason == disconnects.STOP_DISPUTE
        assert after.stopped_on == VISITED_ON
        # The crew's sentence lands in the drawn `What happened` column.
        assert after.stopped_note == "Says the meter was read wrong."


def test_a_visit_is_refused_on_a_case_nobody_scheduled(brazos, marcus, monkeypatch):
    """RED by dropping the state check — then a crew can attend a `cut` case.

    ⚠ **THE CASE IS `cut` AND NOT `stopped`, AND THE DIFFERENCE IS THE TEST.**
    A stopped case is CLOSED, so `open_case_for` cannot see it and the refusal
    is `no_open_case` — a true refusal about a different thing. A `cut` case is
    OPEN and still gets `visit_not_scheduled`, which is the guard this case
    exists for: the supply is already off, and an attendance afterwards is a
    different event this vocabulary does not describe.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=CUT_ON)
        with pytest.raises(disconnects.DisconnectRuleError) as refused:
            disconnect_visits.record_outcome(
                marcus,
                account["id"],
                on_date=VISITED_ON,
                outcome=disconnect_visits.OUTCOME_LOCKED_GATE,
            )
        assert refused.value.code == "visit_not_scheduled"


def test_two_visits_on_one_case_are_both_true(brazos, marcus, monkeypatch):
    """RED by adding a unique constraint on `(tenant, case)`.

    A padlock on Tuesday and a refusal on Thursday are two facts. Nothing here
    is idempotent on purpose — an act that happened twice is recorded twice.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        case = _case(account["id"])
        disconnect_visits.record_outcome(
            marcus,
            account["id"],
            on_date=date(2026, 8, 24),
            outcome=disconnect_visits.OUTCOME_LOCKED_GATE,
        )
        # The cut has to be put back on the calendar before a second crew goes.
        disconnects.schedule_cut(
            marcus, account["id"], cut_on=date(2026, 8, 26), as_of=TODAY
        )
        disconnect_visits.record_outcome(
            marcus,
            account["id"],
            on_date=date(2026, 8, 26),
            outcome=disconnect_visits.OUTCOME_ACCESS_REFUSED,
        )
        rows = disconnect_visits.visits_for(case)
        assert [row["outcome"] for row in rows] == ["access_refused", "locked_gate"]


# ════════════════════════════════════════════════════════════════════════════
# WHAT IT DOES NOT DO — the three absences, each asserted rather than assumed
# ════════════════════════════════════════════════════════════════════════════
def test_paid_at_the_door_takes_no_money_and_does_not_stop_the_ladder(
    brazos, marcus, monkeypatch
):
    """RED by making `paid_at_door` write `stopped`.

    ⚠ **A CREW HOLDING A CHEQUE IS NOT A POSTED PAYMENT.** `apps/customers`
    writes no financial table (`BR-CUS-037`), and a stop on an unposted payment
    closes a case on a crew's word. When the money posts, `halt_reason` answers
    `nothing_owed` by itself — `BR-PAY-036`'s design.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        result = disconnect_visits.record_outcome(
            marcus,
            account["id"],
            on_date=VISITED_ON,
            outcome=disconnect_visits.OUTCOME_PAID_AT_DOOR,
            note="Handed the driver a cheque for $200.",
        )
        after = _case(account["id"])
        assert after.state == disconnects.STATE_NOTICE_SENT
        assert after.stopped_reason is None
        assert result["money"]["code"] == "paid_at_door_records_no_amount"
        # No column anywhere on the visit holds an amount.
        assert not hasattr(disconnect_visits.DisconnectVisit(), "amount")


def test_a_visit_raises_no_work_order_and_notifies_nobody(brazos, marcus, monkeypatch):
    """RED by asserting the key before the constant existed.

    A new visit is a NEW CUT DATE, set by a clerk in the wizard — the act that
    serves the notice the date is counted from. `apps/work` owns dispatch and
    this module writes nothing there (`BR-WRK-002`).
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        result = disconnect_visits.record_outcome(
            marcus,
            account["id"],
            on_date=VISITED_ON,
            outcome=disconnect_visits.OUTCOME_LOCKED_GATE,
        )
        assert result["follow_up"]["code"] == "visit_outcome_raises_no_follow_up"


def test_a_visit_moves_no_money_and_writes_its_audit_row(
    brazos, marcus, monkeypatch, audit_rows
):
    """RED by moving `_audit` outside the `atomic()` and killing the insert.

    Hard rule 7 as this module widens it: a crew standing at somebody's meter is
    a service action against a named customer. **ONE transaction**, `commit_cut`'s
    shape — the row, the move and the audit are one act.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        before = _account_balance_rows(account["id"])
        disconnect_visits.record_outcome(
            marcus,
            account["id"],
            on_date=VISITED_ON,
            outcome=disconnect_visits.OUTCOME_LOCKED_GATE,
        )
        # ⚠ `audit_actions` is a HELPER over the `audit_rows` sink, never a
        # fixture — requesting it as one is an ERROR at setup, not a failure.
        assert disconnect_visits.AUDIT_VISIT_RECORDED in audit_actions(audit_rows)
        assert _account_balance_rows(account["id"]) == before


def _account_balance_rows(account_id):
    """Every money row a visit must not touch, counted."""
    from apps.billing import models as billing_models
    from apps.ledger import models as ledger_models

    return (
        billing_models.Invoice.objects.filter(account_id=account_id).count(),
        ledger_models.JournalLine.objects.count(),
    )


def test_a_disputed_visit_writes_two_audit_rows_because_two_acts_happened(
    brazos, marcus, monkeypatch, audit_rows
):
    """RED by calling `stop_by_hand` outside the transaction, or by suppressing
    its audit row. Two acts happened — a visit was recorded and a ladder was
    stopped — and a record that showed one would be short."""
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnect_visits.record_outcome(
            marcus,
            account["id"],
            on_date=VISITED_ON,
            outcome=disconnect_visits.OUTCOME_DISPUTED,
        )
        actions = audit_actions(audit_rows)
        assert disconnect_visits.AUDIT_VISIT_RECORDED in actions
        assert disconnects.AUDIT_STOPPED in actions


# ════════════════════════════════════════════════════════════════════════════
# THE DOOR — because a backend with no door is not a deliverable
# ════════════════════════════════════════════════════════════════════════════
def test_the_record_screen_offers_the_visit_only_on_a_scheduled_case(
    brazos, marcus, monkeypatch
):
    """RED by returning `can_record: True` unconditionally.

    `BR-SHL-025` — a refused control renders disabled WITH ITS REASON, and a
    control that will ALWAYS be refused is not offered at all.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        case = _case(account["id"])
        panel = disconnect_record.visit_panel(case)
        assert panel["can_record"] is True
        assert panel["refusal"] is None
        assert [row["move"] for row in panel["outcomes"]] == [
            "clears_the_cut_date",
            "clears_the_cut_date",
            "clears_the_cut_date",
            "stops_the_ladder",
        ]

        disconnect_visits.record_outcome(
            marcus,
            account["id"],
            on_date=VISITED_ON,
            outcome=disconnect_visits.OUTCOME_DISPUTED,
        )
        stopped = disconnect_record.visit_panel(_any_case(account["id"]))
        assert stopped["can_record"] is False
        assert stopped["refusal"]["code"] == "visit_not_scheduled"


def test_the_visit_action_appears_on_the_record_and_leaves_when_the_case_moves(
    brazos, marcus, monkeypatch
):
    """RED by leaving `available` as the flat three.

    Hard-won law 2 read from both ends: the door must EXIST on the case that can
    use it, and must NOT be offered on the case that cannot.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        case = _case(account["id"])
        assert disconnect_record.available_actions(case) == (
            "hold",
            "open_account",
            "record_visit",
            "mark_as_cut",
        )
        disconnect_visits.record_outcome(
            marcus,
            account["id"],
            on_date=VISITED_ON,
            outcome=disconnect_visits.OUTCOME_LOCKED_GATE,
        )
        assert disconnect_record.available_actions(_case(account["id"])) == (
            "hold",
            "open_account",
            "mark_as_cut",
        )


def test_another_tenants_case_cannot_have_a_visit_recorded_against_it(
    brazos, lonestar, marcus, erin, monkeypatch
):
    """RED by dropping the tenant scoping — CLAUDE.md hard rule 1.

    `open_case_for` is tenant-scoped, so a clerk of another utility simply
    finds no case rather than finding somebody else's.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
    with tenant_ctx(lonestar):
        with pytest.raises(disconnects.DisconnectRuleError) as refused:
            disconnect_visits.record_outcome(
                erin,
                account["id"],
                on_date=VISITED_ON,
                outcome=disconnect_visits.OUTCOME_LOCKED_GATE,
            )
        assert refused.value.code == "no_open_case"


# ════════════════════════════════════════════════════════════════════════════
# THE OTHER HALF OF THE JOB — the reconnection doors
# ════════════════════════════════════════════════════════════════════════════
def test_a_cut_case_offers_mark_reconnecting_and_never_a_dead_mark_as_cut(
    brazos, marcus, monkeypatch
):
    """RED by leaving `available` as the flat three.

    ⚠ **`Mark as cut` ON A CUT CASE CAN NEVER BECOME PRESSABLE AGAIN** —
    `cut_readiness` answers `already_cut` for ever — and a permanently dead
    control over a live screen is the mirror of hard-won law 2 that cost the
    customer portal six of its eight doors.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=CUT_ON)
        case = _case(account["id"])
        assert case.state == disconnects.STATE_CUT
        assert disconnect_record.available_actions(case) == (
            "hold",
            "open_account",
            "mark_reconnecting",
        )


def test_the_screen_quotes_the_servers_own_refusal_word_for_word(
    brazos, marcus, monkeypatch
):
    """RED by paraphrasing the refusal in `reconnection_readiness`.

    ⚠ **THIS IS THE ASSERTION THAT KEEPS THE TWO IN STEP.** A screen that
    restated a server refusal would be a second answer to a question the writer
    already answers, and it drifts the moment either side is edited. The
    sentences live in `reconnect_blockers` and `mark_reconnecting` RAISES them.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=CUT_ON)
        readiness = disconnects.reconnection_readiness(account["id"])
        assert readiness["step"] == "mark_reconnecting"
        assert readiness["ready"] is False
        assert readiness["refusal"]["code"] == "not_settled"
        with pytest.raises(disconnects.DisconnectRuleError) as raised:
            disconnects.mark_reconnecting(marcus, account["id"], on_date=CUT_ON)
        assert str(raised.value) == readiness["refusal"]["detail"]
        assert raised.value.code == readiness["refusal"]["code"]


def test_a_settled_cut_account_walks_back_through_both_doors(
    brazos, marcus, monkeypatch, audit_rows
):
    """The whole path: `cut` → `reconnecting` → `restored`, through the reads
    a screen uses.

    RED before `reconnection_readiness` existed — the call raised
    `AttributeError`, which is the honest shape of *there was no door*.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=CUT_ON)
        # They pay. `_owes` is the suite's ledger stub; nothing here posts money.
        from tests.test_w7_disconnects import _owes

        _owes(monkeypatch, D("0.00"))

        ready = disconnects.reconnection_readiness(account["id"])
        assert ready["ready"] is True
        assert ready["balance"] == {"stored": "0.0000", "display": "0.00"}

        disconnects.mark_reconnecting(marcus, account["id"], on_date=CUT_ON)
        assert _case(account["id"]).state == disconnects.STATE_RECONNECTING

        mid = disconnects.reconnection_readiness(account["id"])
        assert mid["step"] == "restore_service"
        assert mid["ready"] is True
        case = _case(account["id"])
        assert disconnect_record.available_actions(case) == (
            "hold",
            "open_account",
            "restore_service",
        )

        disconnects.restore_service(marcus, account["id"], on_date=CUT_ON)
        # `restored` is a CLOSED state, so the case leaves the tab — which is
        # the same fact as `open_case_for` no longer finding it.
        assert _case(account["id"]) is None
        actions = audit_actions(audit_rows)
        assert disconnects.AUDIT_RECONNECTING in actions
        assert disconnects.AUDIT_RESTORED in actions


def test_restoring_is_still_refused_around_the_middle_state(brazos, marcus, monkeypatch):
    """RED by widening `restore_blockers` to accept `cut`.

    Restoring an account that never settled states on the record that it paid.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=CUT_ON)
        with pytest.raises(disconnects.DisconnectRuleError) as refused:
            disconnects.restore_service(marcus, account["id"], on_date=CUT_ON)
        assert refused.value.code == "not_reconnecting"


def test_the_status_it_would_restore_to_is_active_whatever_was_held_before(
    brazos, marcus, monkeypatch
):
    """`DEF-CUS-10668` (PO 2026-10-29, *"2A"*): a restoration writes Active.

    This case asserted the OPPOSITE until that ruling — that a case with no
    recorded `status_before_cut` showed an absence instead of `active`. The
    pre-cut status is now history and decides nothing, so a case with nothing
    recorded is restored to Active exactly like any other, and the readiness
    read says so. The absence is left for the one thing that can still stop
    the write: no live `active` row on the tenant.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=CUT_ON)
        case = _case(account["id"])
        case.status_before_cut = None
        case.save(update_fields=["status_before_cut"])
        readiness = disconnects.reconnection_readiness(account["id"], case=case)
        assert readiness["status_before_cut"] is None
        assert readiness["status_restored_to"] == "active"
        assert readiness["status_absence"] is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: PO ruling 2026-09-20 · `OQ-383` (CLOSED) · `BR-CUS-1083` ·
#         B18 §5.8.3 / §5.8.4 · apps/customers/disconnect_visits.py ·
#         apps/customers/disconnects.py · 12-governance/02-decision-log.md
# generated: 2026-09-20 by lane DBLD-2
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 `test_the_database_refuses_a_fifth_outcome_too` SKIPS on sqlite and says
#      so — a CHECK is not enforced there, and a case that passed on the default
#      suite would be law 7's *incapable of failing* shape.
#   E2 the money assertions count rows rather than driving a real payment; the
#      ledger tie-out for the cut itself is `test_def_708_the_fee_is_a_real_charge`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
