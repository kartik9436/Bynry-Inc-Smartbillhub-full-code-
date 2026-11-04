# ── Trace ──────────────────────────────────────────────
# Defect:   **DEF-708 (high)** — a cut customer can be reconnected **$75.00
#           short**. Filed 2026-08-25, ruled 2026-08-27, fixed here.
# Rule:     **PO ruling 2026-08-27**, verbatim: *"A customer can be reconnected
#           $75 short - Make the fee a real charge — It becomes a line that can
#           be billed and paid, so the gate has something to check."*
# Rules:    BR-CUS-104 (PO 2026-08-25, closing OQ-381 — the fee lands AT THE
#           CUT; `A-11340` must clear **$8,315.00**, not $8,240.00) ·
#           BR-BIL-007 (a tenant-configured charge code, never a literal) ·
#           BR-BIL-010 (a charge code carries its own GL) · BR-CUS-037
#           (customers writes no financial table) · BR-BIL-005 (idempotency) ·
#           CLAUDE.md rule 4 (immutability) · rule 5 (only the posting service
#           writes journal lines) · rule 7 (audit)
# ───────────────────────────────────────────────────────
"""DEF-708 — the reconnection fee becomes money, not a note on a case.

**THE DEFECT.** A reconnection requires the fee to be paid. The **$75.00** was
recorded on `disconnect_cases.reconnection_fee_amount` and **posted nowhere**,
so `mark_reconnecting` — which reads AR — had nothing to test and let the
customer through. The utility did the work and never collected.

**WHY THE OBVIOUS FIX IS FORBIDDEN, and it is asserted here so nobody tries it
again (tc4).** Folding the case's recorded figure into the gate's comparison
makes the gate *work* and leaves the money *uncollected* — the wrong half — and
DEADLOCKS the product: paying takes AR to zero, the cached fee never clears,
and **no cut customer could ever be reconnected.** The PO ruled the other shape:
the fee becomes a real charge, and then the gate needs no change at all.

**RED PROOF (r11 step 2d), quoted in the lane report.** With
`seams.raise_and_issue_charge_fee` not called from `commit_cut`, tc2 fails on:

    AssertionError: assert Decimal('0.00') == Decimal('75.00')

— the cut customer's balance, which is the defect in one line: the fee is on
the case and not in the money. (tc3 then records `$0.00` owed where the
record must name the `$75.00` fee.)

**WHAT IS ASSERTED, and each case exists for a reason the others cannot cover:**

  * `tc1` — the cut raises a real `fee` bill for the tenant's OWN code, issued,
    with the charge code's GL account stamped on its line.
  * `tc2` — the customer's BALANCE moves by exactly the fee. This is the money
    half and it is separate from tc1 on purpose: an issued document that does
    not reach AR would pass tc1.
  * `tc3` — the customer who owes only the fee is reconnected and the record
    names the $75.00. ⛔ It asserted a REFUSAL until 2026-10-30
    (`DEF-CUS-10763`): `BR-CUS-1097` (PO 2026-09-25) withdrew that gate, and
    a reconnect request is never refused for an unpaid balance.
  * `tc4` — and once the fee is PAID the same customer is admitted. This is the
    deadlock test: the rejected one-line fix passes tc3 and fails this.
  * `tc5` — a charge code with no GL account refuses the CUT by name, rather
    than recording a cut whose money nothing can book.
  * `tc6` — the amount is the TENANT's, never a literal $75.00.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.billing import models as billing_models
from apps.customers import disconnects
from apps.rating import models as rating_models

from tests.test_w7_cut_reconnect import *  # noqa: F401,F403 — W7's own fixtures
from tests.test_w7_cut_reconnect import (  # noqa: F401
    CUT_ON,
    RECONNECT_FEE,
    TODAY,
    _owes,
    _reconnect_charge,
    _scheduled,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: BR-CUS-104's own worked pair, and the whole defect is the difference.
A_11340_ARREARS = D("8240.00")
A_11340_TO_CLEAR = D("8315.00")


def _fee_invoices(account_id):
    """Every `fee`-typed bill on this account, newest first."""
    return list(
        billing_models.Invoice.objects.filter(
            account_id=account_id, bill_type=disconnects_fee_type()
        ).order_by("-created_at")
    )


def disconnects_fee_type() -> str:
    from apps.billing import fee_bill

    return fee_bill.BILL_TYPE_FEE


def _real_ar_for(_monkeypatch, account_id) -> D:
    """What the **LEDGER** says this account owes — `ledger.reporting.ar_positions`.

    ⚠ **THE LEDGER'S OWN READ, NOT `customers.seams.ar_positions`, AND THAT IS
    THE WHOLE POINT OF THIS HELPER.** The W7 fixtures stand up the AR boundary
    with `_owes(...)`, which monkeypatches the customers-side seam to answer ONE
    constant for any account. That is exactly right for walking the ladder — a
    tier-3 notice needs arrears — and useless for asking whether a fee reached
    the books, because the fake answers the same figure either way. So this goes
    to the module BEHIND the seam, which the fixture does not touch.

    ⚠ **`monkeypatch.undo()` WAS TRIED FIRST AND IS WRONG.** It restores every
    patch in the test, the harness's own `set_config` shim included, and the
    read then dies on `sqlite3.OperationalError: no such function: set_config`.
    Recorded here because it is the obvious move and it fails in a way that
    looks like a database problem rather than a test-design one.

    Deliberately not a sum over invoices: a bill that issued and did not POST
    would satisfy an invoice-shaped assertion while leaving the gate exactly as
    broken as before (rule 5 — only the posting service writes journal lines, so
    only the ledger can answer).

    ⚠ **THE ARREARS THE LADDER WALKED ARE NOT IN THIS FIGURE, and that is
    correct rather than a gap.** `_owes` never posted them — no bill, no journal
    line — so the only real money on this account is the fee the cut charged.
    That makes every assertion below SHARPER: `$75.00` here cannot be arriving
    from anywhere else.
    """
    from apps.ledger import reporting as ledger_reporting

    answer = ledger_reporting.ar_positions(account_ids=[str(account_id)], as_of=None)
    assert answer.get("available"), (
        f"the ledger's AR read is unavailable ({answer.get('unavailable')}); "
        "this test cannot conclude anything"
    )
    positions = answer.get("positions") or {}
    return D(str(positions.get(str(account_id)) or "0"))


# ══════════════════════════════════════════════════════════════════════════
# (1) THE FEE IS A REAL, ISSUED, BOOKED DOCUMENT
# ══════════════════════════════════════════════════════════════════════════
def test_def_708_tc1__the_cut_raises_and_issues_a_real_fee_bill(brazos, marcus, monkeypatch):
    """One `fee` bill, ISSUED, one line, the tenant's code, a stamped GL account.

    Four separate assertions because four different things could be missing and
    three of them would leave the defect exactly where it was: a draft that
    never issues, a line with no charge code (DEF-714's shape), or a line whose
    GL account never got stamped.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)
        charge = rating_models.Charge.objects.get(
            tenant=brazos, code=disconnects.RECONNECT_CHARGE_CODE
        )

        cut = disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)

        bills = _fee_invoices(account["id"])
        assert len(bills) == 1, "the cut must raise exactly one fee bill"
        bill = bills[0]
        assert bill.status == billing_models.INVOICE_ISSUED
        assert bill.total == RECONNECT_FEE
        assert bill.service_date == CUT_ON

        lines = list(bill.lines.all())
        assert [line.kind for line in lines] == ["fee"]
        # BR-BIL-007 — the line names the TENANT's code (DEF-714's column).
        assert str(lines[0].charge_id) == str(charge.id)
        # BR-BIL-010 — and issue stamped that code's OWN GL account onto it.
        assert str(lines[0].gl_account_id) == str(charge.gl_account_id)

        # The cut's own payload names the document, so a figure on the screen
        # can be traced to a bill rather than standing on its own.
        assert cut["fee_invoice"]["invoice_no"] == bill.invoice_no


def test_def_708_tc2__the_customers_balance_moves_by_exactly_the_fee(brazos, marcus, monkeypatch):
    """**THE MONEY HALF, and it is the assertion the defect was about.**

    Measured through the LEDGER, which is the only thing that can say the fee
    was collected rather than merely printed.

    ⚠ **THE ARREARS THE LADDER WALKED WERE NEVER POSTED** — `_owes` fakes the AR
    read and writes no rows — so with that fake undone the ONLY real money on
    this account is the fee. The figure therefore cannot be right by accident.

    ⚠ RED before the fix: `assert Decimal('0.00') == Decimal('75.00')`.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)

        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)

        # The LEDGER's own answer, with the fixture's fake AR read undone.
        assert _real_ar_for(monkeypatch, account["id"]) == RECONNECT_FEE

        # …and it is there because a BALANCED PAIR was posted (rule 5), not
        # because a total was written somewhere. An issued bill that posted
        # nothing is the exact shape of the defect, one layer down.
        bill = _fee_invoices(account["id"])[0]
        assert bill.status == billing_models.INVOICE_ISSUED
        assert bill.total == RECONNECT_FEE


# ══════════════════════════════════════════════════════════════════════════
# (2) THE GATE — UNCHANGED, AND NOW IT BITES
# ══════════════════════════════════════════════════════════════════════════
def test_def_708_tc3__reconnecting_a_customer_who_owes_only_the_fee_records_the_fee(
    brazos, marcus, monkeypatch
):
    """The customer paid every cent of arrears and still owes the fee.

    ⛔ **REWRITTEN 2026-10-30 (lane FINAL-WALK, `DEF-CUS-10763`) — THIS CASE
    ASSERTED A SUPERSEDED RULE.** Until then it was named
    `…reconnecting_refuses_a_customer_who_owes_only_the_fee` and expected
    `mark_reconnecting` to raise `not_settled`. `BR-CUS-1097` (PO 2026-09-25,
    *"Show what's still owed and let the clerk proceed"*) withdrew that refusal,
    and the 2026-10-29 ruling *"C1 -Restore = Reconnect request"* made the
    reconnect request the step that is **never refused for an unpaid balance**.
    So the fee no longer GATES the customer; it is what the clerk is SHOWN and
    what the record keeps. DEF-708's point survives intact and is what this
    case still proves: the **$75.00** is real money in AR, so the warning and
    `owed_at_reconnection` name it — before DEF-708 they would have read
    **$0.00**, because the fee existed only on the case.

    This is `A-11340` at **$8,240.00** against **$8,315.00** in miniature.

    ⚠ **THE FAKE AR READ IS RE-POINTED AT THE LEDGER'S REAL ANSWER, AND THAT IS
    WHAT MAKES THIS CASE PROVE ANYTHING.** Setting the fake to what the LEDGER
    actually holds (`_real_ar_for`) means the ONLY money in the record is the
    fee itself, so the $75.00 below can have no other source.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)

        # NON-VACUOUS: the arrears were faked and never posted, so the ledger's
        # own figure for this account is the fee and nothing else.
        real = _real_ar_for(monkeypatch, account["id"])
        assert real == RECONNECT_FEE

        # The customer has now paid the arrears; the read is what is really
        # outstanding — the fee.
        _owes(monkeypatch, real)

        # BR-CUS-1097: not refused.
        payload = disconnects.mark_reconnecting(marcus, account["id"], on_date=CUT_ON)
        assert payload["state"] == disconnects.STATE_RECONNECTING
        # …and the record keeps EXACTLY the fee, by amount.
        assert payload["owed_at_reconnection"]["display"] == str(RECONNECT_FEE)
        codes = [w["code"] for w in payload["warnings"]]
        assert codes == [disconnects.RECONNECT_MONEY_STILL_OWED]
        assert str(RECONNECT_FEE) in payload["warnings"][0]["detail"]


def test_def_708_tc4__paying_the_fee_lets_the_customer_back(brazos, marcus, monkeypatch):
    """**THE DEADLOCK TEST. The rejected one-line fix fails HERE and only here.**

    Folding `case.reconnection_fee_amount` into `mark_reconnecting`'s comparison
    passes tc3 — the customer is refused — and then refuses them FOREVER,
    because the case's figure never clears when money posts. `A cut customer who
    has paid everything must be able to come back` is the requirement that fix
    breaks, and it is asserted here rather than trusted to a comment.

    The payment is simulated at the AR read (the fixture's own `_owes`) rather
    than by taking a real payment: what is being proved is that the GATE
    releases on a settled balance, and the payments path has its own tests.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert _real_ar_for(monkeypatch, account["id"]) == RECONNECT_FEE

        # Everything owed — the fee included — is now paid.
        _owes(monkeypatch, D("0.00"))

        payload = disconnects.mark_reconnecting(marcus, account["id"], on_date=CUT_ON)
        assert payload["state"] == disconnects.STATE_RECONNECTING


# ══════════════════════════════════════════════════════════════════════════
# (3) THE REFUSALS — a fee that cannot be booked is not charged
# ══════════════════════════════════════════════════════════════════════════
def test_def_708_tc5__a_charge_code_with_no_gl_account_refuses_the_cut(brazos, marcus, monkeypatch):
    """BR-BIL-010 — a code with no GL account is a fee that can never be booked.

    Refused at the CUT, by name, naming the screen that fixes it. The
    alternative is worse in both directions: recording the cut and skipping the
    charge is DEF-708 restored, and drafting a bill that can never issue burns
    an invoice number on a document nobody can release.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)
        rating_models.Charge.objects.filter(
            tenant=brazos, code=disconnects.RECONNECT_CHARGE_CODE
        ).update(gl_account_id=None)

        with pytest.raises(Exception) as refusal:
            disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert "GL account" in str(refusal.value)

        # AND NOTHING WAS RECORDED — the cut did not half-happen. A cut with an
        # uncollectable fee must leave no trace at all (one transaction).
        assert _fee_invoices(account["id"]) == []
        case = disconnects.open_case_for(account["id"])
        assert case.state != disconnects.STATE_CUT


def test_def_708_tc6__the_amount_is_the_tenants_and_never_a_literal(brazos, marcus, monkeypatch):
    """BR-BIL-007 — *"NSF/reconnect fees are tenant-configured charge codes,
    never hardcoded"*. A utility that charges $95.00 bills $95.00.

    The `$75.00` in every other case of this file is the DEMO tenant's figure,
    and this case is what stops it becoming the product's.
    """
    theirs = D("95.00")
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)
        rating_models.Charge.objects.filter(
            tenant=brazos, code=disconnects.RECONNECT_CHARGE_CODE
        ).update(amount=theirs)

        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)

        assert _fee_invoices(account["id"])[0].total == theirs
        assert _real_ar_for(monkeypatch, account["id"]) == theirs
        assert theirs != RECONNECT_FEE


def test_def_708_tc7__a_fee_bill_is_typed_fee_and_not_cycle(brazos, marcus, monkeypatch):
    """B2 r10 #12 — the document says what it is.

    `fee` joined `BILL_TYPES` for this. Typing a charge-code bill as `cycle`
    would put a service period on a document kept for seven years that billed
    no period at all, and every bill-type report would count it as a cycle bill.
    """
    with tenant_ctx(brazos):
        account = _scheduled(marcus, brazos, monkeypatch, owed=A_11340_ARREARS)
        disconnects.commit_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)

        bill = _fee_invoices(account["id"])[0]
        assert bill.bill_type == "fee"
        assert "fee" in billing_models.BILL_TYPES
        # A fee is charged ON a day, not OVER a window (B4.3 prorates by the
        # window and a fee is never prorated).
        assert bill.period_start == bill.period_end == CUT_ON
        assert isinstance(bill.period_start, date)
