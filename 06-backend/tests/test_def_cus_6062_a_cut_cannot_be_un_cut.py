# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-6062 — A CUT CASE CAN BE UN-CUT. `commit_cut` refuses a
#          second cut BY NAME (`already_cut`) and gives the reason; `schedule_cut`
#          never mentioned `STATE_CUT` at all, so the refusal was reachable AROUND
#          in two moves: schedule the cut case (accepted, state goes back to
#          `scheduled`), then commit (the guard no longer fires). The second move
#          raised a SECOND $75.00 reconnection-fee invoice and a SECOND balanced
#          ledger pair against the same household, and re-dated the enforcement.
# Rules:   BR-CUS-039 · BR-CUS-104 (the fee lands at the cut) · `DSC-02.4` ·
#          B18 §5.8.4 (the way back is reconnection, not a re-schedule) ·
#          CLAUDE.md hard rule 4 (financial immutability — corrections are new
#          rows, so a second fee cannot be deleted afterwards), rule 5, rule 7
# Tests:   this file
# ───────────────────────────────────────────────────────
"""**A CUT IS RECORDED ONCE**, and the record is not re-openable by a second verb.

════════════════════════════════════════════════════════════════════════════
WHAT HAPPENED, ON REAL DATA, BEFORE THIS GUARD
════════════════════════════════════════════════════════════════════════════
`A-11340` was cut on 2026-09-20 at 19:03 and charged `BL-2609-000081`, $75.00.
Three `disconnect.cut.scheduled` rows then landed on the same case at 19:50 and
19:58 — a case whose state was `cut` — and a second `disconnect.cut.committed`
at 22:18 raised `BL-2609-000083`, **a second $75.00 invoice and a second
balanced ledger pair against the same household**, and moved `cut_on` from
20 September back to the 14th. Hard rule 4 makes both invoices permanent: a
correction is a new row, so the walk-around cannot be tidied away afterwards.

════════════════════════════════════════════════════════════════════════════
WHY THE GUARD IS ON THE CASE AND NOT ON THE MONEY
════════════════════════════════════════════════════════════════════════════
The second fee is the loudest consequence and it is not the only one: the same
two moves re-date `cut_on`, overwrite `outstanding_at_cut` and
`reconnection_fee_amount`, and re-open a window billing has already closed. A
guard that only refused the second CHARGE would allow every one of those, and
`commit_cut`'s own refusal names re-dating in the same breath as re-quoting.

⚠ **AND A LEGITIMATE RE-CUT IS NOT REFUSED, WHICH IS THE OTHER HALF.** A
household can be cut, reconnected and cut again — and it does not come back
down this road: `restore_service` writes `STATE_RESTORED`, which is in
`CLOSED_CASE_STATES`, so the case leaves the tab and the next enforcement opens
a NEW case at tier 1 with its own notices, its own certified proof and its own
fee. `test_a_household_cut_reconnected_and_cut_again_is_charged_once_per_case`
walks exactly that and proves the second fee is raised, legitimately, against a
second case.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE COUNTS, AND WHY IT COUNTS ROWS RATHER THAN CODES
════════════════════════════════════════════════════════════════════════════
A test that asserts an error code proves the message, not the money. Every case
below takes a full before/after census — invoices, invoice lines, journal
entries, journal lines and `audit_log` rows — across the whole two-move
sequence, the way `10-scripts/po20260921_disconnect_walk_readback.py` does
against the running product.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.billing import models as billing_models
from apps.customers import disconnect_record
from apps.customers import disconnects
from apps.customers import models as customers_models
from apps.ledger import models as ledger_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    erin,
    lonestar,
    marcus,
    tenant_ctx,
)
from tests.test_cr052_w0_the_23_23_case import (
    ARREARS,
    CUT_ON,
    RECONNECT_FEE,
    _a11488,
)
from tests.test_us_ten_helpers import api_call
from tests.test_w7_disconnects import _at_tier, _owes, _prove_tier_3_service

pytestmark = pytest.mark.django_db

#: The date the walk-around would cut on the second time. LATER than `CUT_ON`,
#: so `cut_before_the_scheduled_date` cannot be the thing that refuses it — the
#: second move has to be refused for being a second CUT, not for being early.
SECOND_CUT_ON = date(2026, 8, 26)

#: The day the reconnection is recorded and the day the supply comes back —
#: after the cut, which is the whole situation.
RECONNECT_ON = date(2026, 9, 1)
RESTORE_ON = date(2026, 9, 3)
#: The second, LAWFUL cut: a new debt, a new ladder, a new case.
SECOND_LADDER_DAY = date(2026, 9, 10)
SECOND_SERVED_ON = date(2026, 9, 12)
LAWFUL_SECOND_CUT_ON = date(2026, 9, 20)


def _census(account_id, trail):
    """Every row a cut can write, counted. The money first.

    ⚠ **THE LEDGER IS COUNTED TENANT-WIDE ON PURPOSE.** A journal line carries
    no account of its own that a customers test may read. Each test runs in its
    own rolled-back transaction, so a tenant total IS this test's total — and a
    total is the number that moves when a second cut posts a second balanced
    pair.

    ⚠ **THE AUDIT TRAIL IS COUNTED FROM THE CAPTURE SINK AND NOT FROM
    `audit_log`, AND THE FIRST DRAFT OF THIS FILE GOT THAT WRONG.**
    `tests/test_us_met_helpers.audit_rows` is an `autouse` fixture that points
    `core.audit`'s sink at a Python LIST, so in this suite NOTHING is ever
    inserted into the table. A census reading `AuditLog.objects` therefore
    answered **0 before and 0 after** — `after == before` passed, over a number
    that could not move. It was caught only because the assertion that the
    census is NON-EMPTY was written beside the comparison (CLAUDE.md law 7:
    ask what would make this check pass wrongly).
    """
    invoices = billing_models.Invoice.objects.filter(account_id=account_id)
    return {
        "invoices": invoices.count(),
        "fee_invoices": invoices.filter(bill_type="fee").count(),
        "invoice_lines": billing_models.InvoiceLine.objects.filter(
            invoice__account_id=account_id
        ).count(),
        "journal_entries": ledger_models.JournalEntry.objects.count(),
        "journal_lines": ledger_models.JournalLine.objects.count(),
        "audit_rows": sum(
            1 for row in trail if str(row.get("entity_id")) == str(account_id)
        ),
    }


def _fee_invoices(account_id):
    return list(
        billing_models.Invoice.objects.filter(account_id=account_id, bill_type="fee").order_by(
            "created_at"
        )
    )


# ════════════════════════════════════════════════════════════════════════════
# THE DEFECT. THE TWO MOVES, IN ORDER, AGAINST A REAL CUT.
# ════════════════════════════════════════════════════════════════════════════
def test_the_two_move_walk_around_raises_no_second_fee_and_no_second_ledger_pair(
    brazos, marcus, monkeypatch, audit_rows
):
    """**Move 1 is refused, and nothing downstream of it can run.**

    This is `DEF-CUS-6062` exactly as it was performed against the running
    product: schedule the cut case, then commit it. Both moves are attempted
    here — the second one so that a future lane that weakens move 1's guard
    still fails on the money rather than on a code.
    """
    with tenant_ctx(brazos):
        account, _unit = _a11488(marcus, brazos, monkeypatch)
        first = disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)
        before = _census(account.id, audit_rows)

        # ── MOVE 1 · schedule the case that is already cut ──────────────────
        with pytest.raises(disconnects.DisconnectRuleError) as rescheduled:
            disconnects.schedule_cut(
                marcus,
                account.id,
                cut_on=SECOND_CUT_ON,
                as_of=SECOND_CUT_ON,
                reason=disconnects.CUT_REASON_NON_PAYMENT,
                services={"electric": disconnects.TREATMENT_FULL},
            )

        # ── MOVE 2 · commit it anyway ───────────────────────────────────────
        with pytest.raises(disconnects.DisconnectRuleError) as recommitted:
            disconnects.commit_cut(
                marcus, account.id, cut_on=SECOND_CUT_ON, as_of=SECOND_CUT_ON
            )

        after = _census(account.id, audit_rows)
        case = disconnects.DisconnectCase.objects.get(account_id=account.id)
        fees = _fee_invoices(account.id)

    # ── the refusals ────────────────────────────────────────────────────────
    assert rescheduled.value.code == "already_cut"
    assert "already cut" in str(rescheduled.value)
    assert recommitted.value.code == "already_cut"

    # ── THE MONEY. Not one row moved. ───────────────────────────────────────
    # ⚠ **THE CENSUS IS PROVED NON-EMPTY FIRST.** `after == before` is also true
    # of two censuses that counted nothing — a filter that matches no row, or a
    # read the tenant context is not open for — so the numbers the first cut
    # wrote are asserted before they are compared. A check whose pass and fail
    # look the same to a reader is worse than no check (CLAUDE.md law 7).
    assert before["fee_invoices"] == 1, before
    assert before["journal_entries"] >= 1 and before["journal_lines"] >= 2, before
    assert before["audit_rows"] >= 1, before
    assert after == before
    assert len(fees) == 1
    assert fees[0].total == D("75.000000")
    assert str(first["fee_invoice"]["id"]) == str(fees[0].pk)

    # ── THE RECORD. The date the household was cut on is still that date. ───
    assert case.state == disconnects.STATE_CUT
    assert case.cut_on == CUT_ON
    assert case.cut_scheduled_for == CUT_ON
    assert case.reconnection_fee_amount == RECONNECT_FEE
    assert case.outstanding_at_cut == ARREARS


# ════════════════════════════════════════════════════════════════════════════
# THE ROW THE WALK-AROUND ALREADY LEFT BEHIND: `scheduled` WITH A `cut_on`
# ════════════════════════════════════════════════════════════════════════════
def test_a_case_that_already_carries_a_cut_date_is_not_ordinary_however_it_reads(
    brazos, marcus, monkeypatch, audit_rows
):
    """**A record asserting two incompatible facts is refused by BOTH verbs.**

    `DSC-26-0001` spent three hours reading `state='scheduled'` with `cut_on`
    still set — created by the walk-around above, so it exists in data that a
    guard on `state` alone would wave straight through. The fact is `cut_on`:
    only `commit_cut` writes it and nothing ever clears it, so an OPEN case that
    carries one has already been cut, whatever its state column says.

    The state is moved here with a queryset UPDATE, which is what a test may do
    to `disconnect_cases` (it is not one of hard rule 4's financial tables) and
    is the only way to reconstruct a row the fixed product can no longer make.
    """
    with tenant_ctx(brazos):
        account, _unit = _a11488(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)
        case = disconnects.DisconnectCase.objects.get(account_id=account.id)
        # The damaged row, exactly as the two moves left it on the real case.
        disconnects.DisconnectCase.objects.filter(pk=case.pk).update(
            state=disconnects.STATE_SCHEDULED, cut_scheduled_for=SECOND_CUT_ON
        )
        before = _census(account.id, audit_rows)

        with pytest.raises(disconnects.DisconnectRuleError) as refused:
            disconnects.commit_cut(
                marcus, account.id, cut_on=SECOND_CUT_ON, as_of=SECOND_CUT_ON
            )

        damaged = disconnects.DisconnectCase.objects.get(pk=case.pk)
        readiness = disconnect_record.cut_readiness(
            damaged,
            customers_models.Account.objects.get(pk=account.id),
            as_of=SECOND_CUT_ON,
        )
        after = _census(account.id, audit_rows)

    assert refused.value.code == "already_cut"
    assert before["fee_invoices"] == 1, before
    assert before["journal_lines"] >= 2, before
    assert after == before
    # The screen says the same thing the writer would have said, and offers no
    # button that would always be refused (B14's posture, BR-SHL-025).
    assert readiness["ready"] is False
    assert readiness["refusal"]["code"] == "already_cut"


# ════════════════════════════════════════════════════════════════════════════
# THE MIRROR — A GUARD THAT REFUSES EVERYTHING IS NOT A GUARD
# ════════════════════════════════════════════════════════════════════════════
def test_a_cut_that_has_not_happened_yet_can_still_be_rescheduled(
    brazos, marcus, monkeypatch
):
    """**Re-scheduling a case that has NOT been cut still works, unchanged.**

    `schedule_cut` was written to be safely repeatable on a running case — a
    date moves, a service election changes, a clerk corrects themselves — and
    the fix must not take that away. This is law 7's *what would make this check
    pass wrongly*: a guard keyed on the state name alone, or one that refused
    every second schedule, would pass the case above and break this one.
    """
    with tenant_ctx(brazos):
        account, _unit = _a11488(marcus, brazos, monkeypatch)
        moved = disconnects.schedule_cut(
            marcus,
            account.id,
            cut_on=SECOND_CUT_ON,
            as_of=CUT_ON,
            reason=disconnects.CUT_REASON_NON_PAYMENT,
            services={"electric": disconnects.TREATMENT_FULL},
        )
        case = disconnects.DisconnectCase.objects.get(account_id=account.id)

    assert moved["state"] == disconnects.STATE_SCHEDULED
    assert case.cut_scheduled_for == SECOND_CUT_ON
    assert case.cut_on is None


# ════════════════════════════════════════════════════════════════════════════
# THE LEGITIMATE SEQUENCE — CUT, RECONNECTED, CUT AGAIN
# ════════════════════════════════════════════════════════════════════════════
def test_a_household_cut_reconnected_and_cut_again_is_charged_once_per_case(
    brazos, marcus, monkeypatch
):
    """**Two lawful cuts, two fees, two cases — and the guard refuses neither.**

    §5.8.4's way back: *"payment confirmed → visit scheduled → restored"*. The
    restoration closes the case, so the second enforcement climbs a new ladder,
    serves new notices, records a new certified proof and schedules on a case
    whose `cut_on` is NULL. The $75.00 is charged twice here and both charges
    are correct — which is precisely why the guard is on the CASE and not on
    the second fee.
    """
    with tenant_ctx(brazos):
        account, _unit = _a11488(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)
        first_case = disconnects.DisconnectCase.objects.get(account_id=account.id)

        # ── they pay: the books read zero, so the reconnection is admissible ─
        _owes(monkeypatch, D("0"))
        disconnects.mark_reconnecting(marcus, account.id, on_date=RECONNECT_ON)
        disconnects.restore_service(marcus, account.id, on_date=RESTORE_ON)
        assert disconnects.open_case_for(account.id) is None

        # ── months later they fall behind again ─────────────────────────────
        _owes(monkeypatch, ARREARS)
        _at_tier(marcus, account.id, disconnects.TIER_3)
        _prove_tier_3_service(marcus, account.id, served_on=SECOND_SERVED_ON)
        second_case = disconnects.open_case_for(account.id)
        disconnects.schedule_cut(
            marcus,
            account.id,
            cut_on=LAWFUL_SECOND_CUT_ON,
            as_of=SECOND_LADDER_DAY,
            reason=disconnects.CUT_REASON_NON_PAYMENT,
            services={"electric": disconnects.TREATMENT_FULL},
        )
        second = disconnects.commit_cut(
            marcus, account.id, cut_on=LAWFUL_SECOND_CUT_ON, as_of=LAWFUL_SECOND_CUT_ON
        )
        fees = _fee_invoices(account.id)
        reopened = disconnects.DisconnectCase.objects.get(pk=first_case.pk)

    # The second cut is a different CASE, and it happened.
    assert second_case.id != first_case.id
    assert second["state"] == disconnects.STATE_CUT
    assert second["cut_on"] == str(LAWFUL_SECOND_CUT_ON)
    # Two lawful fees, one per cut, each its own invoice.
    assert len(fees) == 2
    assert [f.total for f in fees] == [D("75.000000"), D("75.000000")]
    # And the first cut's record is exactly as it was recorded on the day.
    assert (reopened.state, reopened.cut_on) == (disconnects.STATE_RESTORED, CUT_ON)


# ════════════════════════════════════════════════════════════════════════════
# THROUGH THE DOOR THE PROBE ACTUALLY USED
# ════════════════════════════════════════════════════════════════════════════
def test_the_route_refuses_the_walk_around_as_a_sentence_and_not_a_500(
    brazos, marcus, monkeypatch, audit_rows
):
    """**`POST /disconnects/schedule`, on a case that is already cut.**

    `DEF-CUS-6062` was not found by a screen and could not be: the record page
    greys `Mark as cut` on a cut case and always has. It was found by a probe
    posting to the wizard's one address, which is where the second cut was
    performed on `A-11340` — so this is the reproduction, at the door it came
    through.

    A ladder refusal reaches the wire as a 422 catalogue refusal carrying the
    rule and the service's own sentence (`DEF-2030`'s claim 3). Asserting a
    raised exception here would assert a shape no clerk ever meets.
    """
    from apps.customers import transfer_disconnect_api as doors
    from core import errors

    with tenant_ctx(brazos):
        account, _unit = _a11488(marcus, brazos, monkeypatch)
        disconnects.commit_cut(marcus, account.id, cut_on=CUT_ON, as_of=CUT_ON)
        before = _census(account.id, audit_rows)

    refused = api_call(
        doors.schedule_cut,
        "post",
        user=marcus.user,
        role="billing_clerk",
        tenant=brazos,
        data={
            "account_id": str(account.id),
            "cut_on": str(SECOND_CUT_ON),
            "services": {"electric": disconnects.TREATMENT_FULL},
        },
    )

    with tenant_ctx(brazos):
        after = _census(account.id, audit_rows)
        case = disconnects.DisconnectCase.objects.get(account_id=account.id)

    assert refused.status_code == 422, refused.data
    assert refused.data["code"] == errors.BIZ_COMPLETENESS
    assert refused.data["params"]["code"] == "already_cut"
    assert "already cut" in refused.data["params"]["detail"].lower()
    # The door moved nothing: not the record, and not one row of money.
    assert case.state == disconnects.STATE_CUT
    assert case.cut_on == CUT_ON
    assert before["fee_invoices"] == 1, before
    assert after == before
