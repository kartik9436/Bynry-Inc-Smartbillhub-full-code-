# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-6063 — a cut whose final bill billing REFUSED could never be
#          finished. `commit_cut` writes BR-CUS-107's status only when the days
#          before the cut are billed (`CUT_BILL_BLOCKED_SO_STATUS_HELD`), and
#          nothing anywhere could try again: `commit_cut` refuses `already_cut`
#          by name, `_write_disconnected_status` had one caller, and no run, job
#          or screen revisited the case.
#          DEF-CUS-6064 — and the record screen never said so: `cut_bill` and
#          `account_status_held` travelled on the cut's payload and no file in
#          `07-frontend` and no line of `disconnect_record.py` read either.
#          DEF-CUS-6086 — the $75.00 reconnection fee the refused cut raised
#          moved the account's first unbilled day PAST the cut, so a retry would
#          have answered `already_billed_through_the_cut_day` with `billed=True`
#          over days nobody had billed.
# Rules:   BR-CUS-107 · BR-CUS-103 · PO ruling 2026-08-30 (the disconnect is the
#          WHOLE event) · `DSC-02.4` (a cut is not a close-out) · BR-BIL-004 ·
#          CLAUDE.md rule 7 (every money action writes `audit_log`)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""The way OUT of a held cut, and the three things it must not do.

════════════════════════════════════════════════════════════════════════════
THE INVARIANT, WHICH IS `test_cr052_w0_disconnected_at_the_cut.py`'s WITH ITS
SECOND BRANCH FINISHED
════════════════════════════════════════════════════════════════════════════
That file states it in one line — **the days before a cut are never billed by
nobody** — and proves both branches of it AT THE CUT. This file proves what
happens to the second branch AFTERWARDS, which until 2026-09-20 was: nothing,
ever.

    * the bill is refused → the status is HELD, and **that is still correct**;
    * a human fixes what billing named → **the cut can now be finished**, the
      bill is raised and the status is written;
    * billing still refuses → **nothing is written**, and the engine's own
      sentence comes back so the person who can fix it is told what to fix.

════════════════════════════════════════════════════════════════════════════
THE SEAM IS STUBBED AT THE MODULE BOUNDARY, AND THAT IS THE POINT
════════════════════════════════════════════════════════════════════════════
`_fee_seam_answers` in the sibling file states the reason and it holds here:
raising a bill is BILLING's (BR-CUS-037, CLAUDE.md rule 5), so a customers test
that reached into invoice rows would be asserting another module's contract.
What this file owns is the DECISION — when the status is written, when it is
not, what is recorded and what is refused — and that decision reads exactly one
thing off billing's answer: `CutBill.billed`.

`tests/test_cr052_w0_the_23_23_case.py` runs the money end to end through the
real engine; nothing here duplicates it.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.billing import cut_bill as billing_cut_bill
from apps.customers import disconnect_record
from apps.customers import disconnects
from apps.customers import models as customers_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    erin,
    lonestar,
    marcus,
    tenant_ctx,
)
from tests.test_w7_cut_reconnect import CUT_ON, TODAY, _scheduled
from tests.test_w7_disconnects import _owes

pytestmark = pytest.mark.django_db

#: The day the clerk stands on when they finish the cut — after the cut, which
#: is the whole situation. It is NOT the bill's date: the window comes from
#: `cut_on` (BR-TEN-043 / G6, no clock on a money path).
FINISH_ON = date(2026, 8, 30)

#: The engine's own words on the two cuts this product has performed, quoted so
#: a reader of this file knows what the clerk is meant to see and act on.
#:
#: ⚠ **RE-QUOTED 2026-09-24 (`DEF-CUS-6550`).** This is a FIXTURE — nothing here
#: asks the engine for it — so it would have gone on quoting a sentence the
#: engine had stopped producing, which is hard-won law 1 inside a test
#: constant. The 63-word original read *"service electric: base charge code
#: BASE-E-COM prices per connection size and states no amount for size None. An
#: unpriced size is REFUSED and never substituted (PO ruling 2026-08-28) —
#: charging this connection another size's rate is not charging it for the
#: connection it has. Price that size on the charge code, or record the
#: connection's size."* It reached a CLERK on ACC-06 step 3, where B14 rule 33
#: caps a refusal at six words a sentence.
#: `test_def_cus_6550_base_refusals_are_short.py` builds every one of these
#: from the engine and holds the length; this file only needs A sentence.
ENGINE_SENTENCE = "This connection's size is not recorded. Record the connection's size."


@pytest.fixture(autouse=True)
def _fee_seam_answers(monkeypatch):
    """The reconnection fee, stubbed at the customers/billing boundary."""
    monkeypatch.setattr(
        disconnects.seams,
        "raise_and_issue_charge_fee",
        lambda *_a, **_k: {"invoice_id": None, "stubbed_at": "the customers/billing seam"},
    )


def _blocked(detail=ENGINE_SENTENCE):
    return billing_cut_bill.CutBill(
        outcome=billing_cut_bill.CUT_BILL_BLOCKED,
        period_start=date(2026, 8, 1),
        period_end=CUT_ON,
        reason="cut_bill_refused",
        detail=detail,
    )


def _raised():
    return billing_cut_bill.CutBill(
        outcome=billing_cut_bill.CUT_BILL_RAISED,
        period_start=date(2026, 8, 1),
        period_end=CUT_ON,
        cycle_days=31,
        service_days=24,
        invoice_id="01a0c0de-0000-7000-8000-000000000001",
        invoice_no="BL-2608-000999",
        total=D("23.2300"),
        currency="USD",
    )


def _answer_with(monkeypatch, *answers):
    """Make billing's seam answer `answers` in order, then repeat the last."""
    queue = list(answers)

    def _seam(*_a, **_k):
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(disconnects.seams, "raise_and_issue_cut_bill", _seam)


def _held_cut(actor, tenant, monkeypatch):
    """A REALLY cut account whose final bill billing refused.

    The whole W7 ladder is walked and `commit_cut` is the thing that cuts it —
    a case put into `cut` with an UPDATE proves only that a column can hold a
    string, which is `_scheduled`'s own stated reason for walking the ladder.
    """
    account = _scheduled(actor, tenant, monkeypatch)
    _answer_with(monkeypatch, _blocked())
    cut = disconnects.commit_cut(actor, account["id"], cut_on=CUT_ON, as_of=TODAY)
    assert cut["cut_bill"]["billed"] is False, cut["cut_bill"]
    assert cut["account_status_written"] is None
    return account


def _row(account_id):
    return customers_models.Account.objects.get(id=account_id)


def _plain_account(actor, tenant, *, label):
    """One ordinary account, with no case and no ladder — the window cases only
    need an account id and the two dates the read looks at."""
    from tests.test_w7_disconnects import _account

    return _account(actor, tenant, label=label)



def _status_of(account_id):
    row = _row(account_id)
    return getattr(row.status, "code", None)


# ════════════════════════════════════════════════════════════════════════════
# TC-1 · THE STATE IS READABLE — which is what DEF-CUS-6064 was
# ════════════════════════════════════════════════════════════════════════════
def test_tc1_a_held_cut_reports_itself_unfinished(marcus, brazos, monkeypatch):
    """`cut_is_unfinished` is TRUE, and it is ONE read for three consumers.

    RED-FIRST (r11 step 2d): before this change there was no such function and
    the record payload had no key to carry it — `grep cut_bill 07-frontend`
    returned nothing and `grep account_status_held apps/customers/
    disconnect_record.py` returned nothing. The state existed and nothing could
    see it.
    """
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        case = disconnects.open_case_for(account["id"])
        assert disconnects.cut_is_unfinished(case, _row(account["id"])) is True


def test_tc1b_a_case_that_was_never_cut_is_not_unfinished(
    marcus, brazos, monkeypatch
):
    """The read must not fire on a case that is merely SCHEDULED.

    A `scheduled` case has no `cut_on` and its account is legitimately on a
    billable status. Reporting it unfinished would offer a clerk a button that
    bills an account whose supply is still on.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        case = disconnects.open_case_for(account["id"])
        assert disconnects.cut_is_unfinished(case, _row(account["id"])) is False


def test_tc2_the_record_states_it_and_offers_the_door(
    marcus, brazos, monkeypatch
):
    """The screen's two halves — DEF-CUS-6064's whole subject.

    `what_a_cut_would_do` promises *"Status becomes Disconnected"* on every
    case. On a case where that did not happen the panel now carries
    `cut_unfinished`, and `actions.available` carries the fourth door.
    """
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        case = disconnects.open_case_for(account["id"])
        record = disconnect_record.record_detail(case.case_no, as_of=FINISH_ON)
        assert record["what_a_cut_would_do"]["cut_unfinished"] is not None
        assert (
            record["what_a_cut_would_do"]["cut_unfinished"]["code"]
            == "cut_bill_was_refused_so_the_status_was_held"
        )
        assert "finish_cut" in record["actions"]["available"]
        # ⚠ **AND IT DISPLACES NOTHING.** `available_actions` became
        # state-dependent on 2026-09-20 — a `cut` case offers the two doors and
        # `mark_reconnecting`, because `Mark as cut` on a case cut last Tuesday
        # can never become pressable again. This adds a fourth entry to that
        # ONE state and takes none away, which is what the PO's *"keep critical
        # ones"* allows and a replacement would not.
        assert record["actions"]["available"] == [
            "hold",
            "open_account",
            "finish_cut",
            "mark_reconnecting",
        ]


def test_tc2b_a_finished_cut_offers_no_fourth_door(
    marcus, brazos, monkeypatch
):
    """The mirror, and it is the one that keeps the screen honest.

    `DEF-CWP-3925`'s lesson is a control that goes on refusing over a screen
    that has landed; this is its opposite — a control that goes on OFFERING an
    act that has already happened. On a cut whose status was written the panel
    states nothing and the door is ABSENT, not greyed.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        _answer_with(monkeypatch, _raised())
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert _status_of(account["id"]) == disconnects.CUT_STATUS_CODE
        case = disconnects.open_case_for(account["id"])
        record = disconnect_record.record_detail(case.case_no, as_of=FINISH_ON)
        assert record["what_a_cut_would_do"]["cut_unfinished"] is None
        assert "finish_cut" not in record["actions"]["available"]


# ════════════════════════════════════════════════════════════════════════════
# TC-3 · FINISHING IT — the act, and the one rule that governs the status
# ════════════════════════════════════════════════════════════════════════════
def test_tc3_finishing_raises_the_bill_and_writes_the_status(
    marcus, brazos, monkeypatch
):
    """The whole of `DEF-CUS-6063`, in the order `commit_cut` uses."""
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        before = _status_of(account["id"])
        assert before != disconnects.CUT_STATUS_CODE

        _answer_with(monkeypatch, _raised())
        answer = disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON)

        assert answer["finished"] is True
        assert answer["cut_bill"]["billed"] is True
        assert answer["cut_bill"]["invoice_no"] == "BL-2608-000999"
        assert answer["account_status_written"] == disconnects.CUT_STATUS_CODE
        # The code to RESTORE to, recorded on the case — `restore_service`
        # cannot derive it afterwards.
        assert answer["account_status_before_cut"] == before
        assert _status_of(account["id"]) == disconnects.CUT_STATUS_CODE
        case = disconnects.open_case_for(account["id"])
        assert case.status_before_cut == before
        # The window came from the CASE's recorded cut date and not from today.
        assert answer["cut_on"] == str(CUT_ON)
        assert answer["finished_on"] == str(FINISH_ON)


def test_tc3b_the_cut_itself_is_not_re_recorded(marcus, brazos, monkeypatch):
    """⛔ **A CUT IS RECORDED ONCE** — `commit_cut`'s own refusal, and the
    regulator's record behind it. Finishing must not re-date the enforcement or
    re-quote the fee."""
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        case = disconnects.open_case_for(account["id"])
        was = (case.state, case.cut_on, case.reconnection_fee_amount, case.reconnection_fee_code)

        _answer_with(monkeypatch, _raised())
        disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON)

        case.refresh_from_db()
        assert (
            case.state,
            case.cut_on,
            case.reconnection_fee_amount,
            case.reconnection_fee_code,
        ) == was


def test_tc3c_it_is_not_a_close_out(marcus, brazos, monkeypatch):
    """`DSC-02.4`, untouched: no close, no deposit, nothing written off."""
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        _answer_with(monkeypatch, _raised())
        answer = disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON)

        row = _row(account["id"])
        assert row.closed_at is None
        assert answer["settlement"]["written_off"] is None
        assert answer["settlement"]["account_closed"] is False
        assert answer["settlement"]["deposit_settled"] is False


def test_tc3d_every_finish_writes_an_audit_row(marcus, brazos, monkeypatch, audit_rows):
    """CLAUDE.md rule 7 — the act that billed a customer and moved their account
    out of the bill run is on the record.

    ⚠ **READ FROM THE BE-03 SINK, NOT FROM `audit_log`.** `audit_rows` is the
    suite's autouse capture sink and it REPLACES the table writer for the
    duration of a test, so a case querying the table finds zero rows and reads
    as *"rule 7 was not honoured"* when it was. That is a check looking at the
    wrong thing (hard-won law 7), and this file met it on its first run."""
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        _answer_with(monkeypatch, _raised())
        disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON)

        written = [
            row for row in audit_rows if row["action"] == disconnects.AUDIT_CUT_FINISHED
        ]
        assert len(written) == 1, audit_actions(audit_rows)
        after = written[0]["after"]
        assert after["account_status_written"] == disconnects.CUT_STATUS_CODE
        # Both figures, because one of them is superseded and a reader has to
        # be able to tell which.
        assert "outstanding_recorded_at_the_cut" in after["settlement"]


# ════════════════════════════════════════════════════════════════════════════
# TC-4 · STILL REFUSED — nothing is written, and the sentence comes back
# ════════════════════════════════════════════════════════════════════════════
def test_tc4_a_still_refused_bill_writes_nothing_and_names_what_to_fix(
    marcus, brazos, monkeypatch
):
    """**The safety rule, unchanged.** `Disconnected` is written only when the
    days up to the cut are billed. A clerk who presses the door before fixing
    the data gets the engine's sentence and an account that is exactly where it
    was."""
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        before = _status_of(account["id"])

        _answer_with(monkeypatch, _blocked())
        answer = disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON)

        assert answer["finished"] is False
        assert answer["account_status_written"] is None
        assert (
            answer["account_status_held"]["code"]
            == "cut_bill_still_blocked_status_not_written"
        )
        # The ENGINE's own words, not ours — the only thing in this product
        # that tells the clerk what to fix.
        # ⚠ **CAPITAL `R` SINCE 2026-09-24 (`DEF-CUS-6550`)** — the repair is
        # its own sentence now rather than a clause at the end of a 63-word
        # paragraph, which is B14 rule 33's *"two sentences of six beat one
        # sentence of twelve"*. The assertion is the same claim: the ENGINE's
        # words, not ours, are what tells the clerk what to fix.
        assert "Record the connection's size" in answer["cut_bill"]["detail"]
        assert _status_of(account["id"]) == before
        case = disconnects.open_case_for(account["id"])
        assert case.status_before_cut is None


# ════════════════════════════════════════════════════════════════════════════
# TC-5 · THE THREE ACTS IT REFUSES
# ════════════════════════════════════════════════════════════════════════════
def test_tc5_a_case_with_no_cut_cannot_be_finished(
    marcus, brazos, monkeypatch
):
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON)
        assert refusal.value.code == "no_cut_to_finish"


def test_tc5b_a_finished_cut_cannot_be_finished_twice(
    marcus, brazos, monkeypatch
):
    """Idempotent BY REFUSAL, not by replay: a second run would ask billing for
    a window it has already billed and re-state a settlement nobody changed."""
    with tenant_ctx(brazos):
        account = _held_cut(marcus, brazos, monkeypatch)
        _answer_with(monkeypatch, _raised())
        disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON)
        assert refusal.value.code == "cut_already_finished"


def test_tc5c_an_account_with_no_case_cannot_be_finished(
    marcus, brazos, monkeypatch
):
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("0.00"))
        from tests.test_w7_disconnects import _account

        account = _account(marcus, brazos, label="Unit Z")
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.finish_cut(marcus, account["id"], as_of=FINISH_ON)
        assert refusal.value.code == "no_open_case"


# ════════════════════════════════════════════════════════════════════════════
# TC-6 · THE WINDOW — `DEF-CUS-6086` and `DEF-BIL-6093`, the two dates that
#        decide how many days a cut customer is asked to pay for
# ════════════════════════════════════════════════════════════════════════════
def test_tc6_a_fee_bill_does_not_move_the_first_unbilled_day(brazos, marcus):
    """`DEF-CUS-6086` — a `fee` bill covers NO SERVICE PERIOD.

    `fee_bill` writes `period_start = period_end = the fee's date` because a
    row needs a date, not because a day of service was priced. Counting it
    would answer *"an issued bill already covers this account through the cut
    day"* — with `billed=True` — over days nobody has billed.
    """
    from apps.billing import models as billing_models
    from apps.billing import selectors as billing_selectors

    with tenant_ctx(brazos):
        account = _plain_account(marcus, brazos, label="Unit W6a")
        billing_models.Invoice.objects.create(
            tenant_id=brazos.id,
            account_id=account["id"],
            invoice_no="BL-TEST-FEE-1",
            bill_type="fee",
            status="issued",
            period_start=date(2026, 8, 24),
            period_end=date(2026, 8, 24),
            # NOT NULL — BR-RAT-007 prices on the service date, and a document
            # with none could not be re-priced by anybody.
            service_date=date(2026, 8, 24),
            currency="USD",
            total=D("75.0000"),
        )
        assert billing_selectors.last_issued_invoice_period_end(account["id"]) == date(2026, 8, 24)
        # …and the read the cut bill uses skips it.
        assert billing_selectors.last_issued_service_period_end(account["id"]) is None


def test_tc6b_a_cycle_bill_still_moves_it(brazos, marcus):
    """The negative half — otherwise the fix above could be `return None`."""
    from apps.billing import models as billing_models
    from apps.billing import selectors as billing_selectors

    with tenant_ctx(brazos):
        account = _plain_account(marcus, brazos, label="Unit W6b")
        billing_models.Invoice.objects.create(
            tenant_id=brazos.id,
            account_id=account["id"],
            invoice_no="BL-TEST-CYCLE-1",
            bill_type="cycle",
            status="issued",
            period_start=date(2026, 7, 1),
            period_end=date(2026, 7, 31),
            service_date=date(2026, 7, 31),
            currency="USD",
            total=D("40.0000"),
        )
        assert billing_selectors.last_issued_service_period_end(account["id"]) == date(2026, 7, 31)
        assert billing_cut_bill.first_unbilled_day(account["id"]) == date(2026, 8, 1)


def test_tc6c_a_migrated_account_is_billed_from_the_cutover_not_the_move_in(
    brazos, marcus
):
    """`DEF-BIL-6093` — **the days before cutover belong to the old system.**

    An account brought over at cutover has no issued bill in this product, so
    the window used to open at `accounts.opened_at` — the day service began.
    On `A-11340` that is **2021-03-15** against a cut on 2026-09-20: five and a
    half years, every day of which is already on the books as an opening
    receivable of **$8,240.00** `as_of` 2026-09-20. Raising it would charge the
    customer twice.
    """
    from apps.customers import models as customers_models

    with tenant_ctx(brazos):
        account = _plain_account(marcus, brazos, label="Unit W6c")
        row = customers_models.Account.objects.get(id=account["id"])
        row.opened_at = date(2021, 3, 15)
        row.save(update_fields=["opened_at", "updated_at"])
        # Without a migration the move-in date still answers — unchanged.
        assert billing_cut_bill.first_unbilled_day(account["id"]) == date(2021, 3, 15)

        customers_models.AccountOpeningBucket.objects.create(
            tenant_id=brazos.id,
            account_id=row.id,
            as_of=date(2026, 8, 31),
            bucket=customers_models.AccountOpeningBucket.BUCKET_90_PLUS,
            amount=D("8240.0000"),
            currency="USD",
        )
        # …and with one, the cutover wins: the first day this product owns.
        assert billing_cut_bill.first_unbilled_day(account["id"]) == date(2026, 9, 1)


def test_tc6d_a_migrated_account_cut_before_its_first_bill_owes_nothing_new(
    brazos, marcus
):
    """And the sentence a support person reads is the RIGHT one.

    `nothing_to_bill` used to say *"an issued bill already covers this
    account"* whatever the reason, and on a cutover account that is false —
    there is no issued bill anywhere. Two facts, two sentences.
    """
    from apps.customers import models as customers_models

    with tenant_ctx(brazos):
        account = _plain_account(marcus, brazos, label="Unit W6d")
        row = customers_models.Account.objects.get(id=account["id"])
        row.opened_at = date(2021, 3, 15)
        row.save(update_fields=["opened_at", "updated_at"])
        customers_models.AccountOpeningBucket.objects.create(
            tenant_id=brazos.id,
            account_id=row.id,
            as_of=date(2026, 9, 20),
            bucket=customers_models.AccountOpeningBucket.BUCKET_90_PLUS,
            amount=D("8240.0000"),
            currency="USD",
        )
        answer = billing_cut_bill.raise_and_issue_cut_bill(
            marcus, account_id=row.id, cut_on=date(2026, 9, 20), due_days=0
        )
        assert answer.outcome == billing_cut_bill.CUT_BILL_NOTHING_TO_BILL
        assert answer.billed is True
        assert answer.reason == "covered_by_the_opening_balance_at_cutover"
        assert "charge the customer twice" in (answer.detail or "")
