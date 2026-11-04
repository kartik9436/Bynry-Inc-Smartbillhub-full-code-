# ── Trace ──────────────────────────────────────────────
# Change:   CR-138-BRC07 · P4.24 — "Regression: the write-off two-person
#           control." Blueprint p23 and screen **7·3b Write-offs**, whose own
#           annotations are *"① The two-person control — the requester asks
#           from, a different person decides here — EXISTS"* and *"② Asked by,
#           which is what makes the control visible — EXISTS"*.
# Rules:    ⚠ **BR-PAY-037 (CONFIRMED, PO SD-1 2026-08-08)** — *"the SAME user
#           holding the approver role MAY initiate AND approve in v1 — both
#           acts recorded distinctly; enforced separation-of-duties = v2"* ·
#           BR-PAY-020 (initiated in Payments, APPROVED in Finance) ·
#           BR-PAY-1120 (four states, three terminal) · BR-SHL-025 (the gate is
#           the server's, never a disabled button)
# ───────────────────────────────────────────────────────
"""**THE CONTROL THAT EXISTS IS A ROLE CONTROL, NOT AN IDENTITY CONTROL — AND
THE TASK LINE SAYS OTHERWISE.**

⚠ **THE BRIEF FOR THIS TASK READS *"A requester cannot approve their own"*, AND
AS WRITTEN THAT IS NOT THIS PRODUCT'S RULE.** It was checked before a line of
test was written, because a regression test asserting a rule the repo does not
hold would either be deleted by the next reader or — far worse — be "fixed" by
somebody adding the refusal, which would overturn a CONFIRMED rule without a
ruling (hard-won law 13, and the prime directive: *never resolve an open
question by choosing a value*).

**WHAT THE REGISTER ACTUALLY SAYS**, `04-docs/05-modules/08-payments/
02-business-rules.md`, `BR-PAY-037`, status **CONFIRMED**, verbatim:

    Approval chains (refund, write-off, adjustment, cross-period reversal):
    the SAME user holding the approver role MAY initiate AND approve in v1 —
    both acts recorded distinctly; enforced separation-of-duties = v2

`apps/payments/writeoffs.py` says the same in its own words and gives the
reason: *"Nothing here refuses a self-approval, because a CONFIRMED rule
permits it and an implementing lane does not overturn one."*

═══════════════════════════════════════════════════════════════════════════════
SO WHAT **IS** THE TWO-PERSON CONTROL? THREE THINGS, AND ALL THREE ARE REAL
═══════════════════════════════════════════════════════════════════════════════
  **1 · THE ROLE SPLIT.** Requesting is `AdminOrClerk`; approving is
      `@require_role(SYSTEM_ADMIN)` **in the service**, not on the route. So a
      **Billing Clerk who requests a write-off genuinely cannot approve it** —
      which is the brief's sentence, true for the role that raises nearly all
      of them, and false only for an Admin raising their own.
  **2 · THE TWO ACTS ARE SEPARATE COLUMNS.** `requested_by` and `approved_by`,
      never folded into a boolean. That is the half `BR-PAY-037` actually
      specifies — *"both acts recorded distinctly"* — and it is what makes the
      blueprint's *"Asked by"* column drawable at all.
  **3 · THE SCREEN SEPARATION.** `GET /write-offs?f.status=requested` is a
      listable queue, so the Approve control lives in Finance instead of beside
      the requester's own form. `DEF-100` is the defect where it did not exist:
      *"the only write-off id a browser could hold was the one the requester's
      own screen had just minted."*

**This file asserts all three, and asserts the fourth fact out loud:** that an
ADMIN may still approve their own request, with both acts recorded. If a later
lane makes that refuse, this file goes red and names `BR-PAY-037` — which is
the correct outcome, because that change is a v2 ruling and not a bug fix.

═══════════════════════════════════════════════════════════════════════════════
RED PROOF (hard-won law 7) — OBSERVED, NOT PREDICTED
═══════════════════════════════════════════════════════════════════════════════
  * **the role gate.** With `@permissions.require_role(permissions.SYSTEM_ADMIN,
    br_ref="BR-PAY-020")` deleted from `approve_write_off`, the clerk case
    fails `Failed: DID NOT RAISE <class 'core.errors.AuthError'>` and the
    write-off reaches `approved` with `requested_by == approved_by` on a
    BILLING CLERK. Restored, and the case is green.
  * **the separate columns.** With `approved_by_id` left unset in
    `approve_write_off`, the distinctness case fails
    `AssertionError: the approver was not recorded — BR-PAY-037 rests on this`.

═══════════════════════════════════════════════════════════════════════════════
WHAT WOULD MAKE THESE CHECKS PASS WRONGLY (law 7, habit 2)
═══════════════════════════════════════════════════════════════════════════════
* **A gate on the ROUTE rather than in the SERVICE would pass an HTTP test and
  fail a real one**, because a background job, a runbook or another module
  calls the service and never the route. So the clerk case calls
  `writeoffs.approve_write_off` DIRECTLY, with no view in the way.
* **`requested_by == approved_by` is `None == None` on an unattributed row**,
  which would pass a naive equality. So the distinctness case asserts both are
  NOT NULL before comparing them.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.payments import writeoffs
from apps.payments.collections_models import WriteOff
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill

pytestmark = pytest.mark.django_db

from tests.test_us_ten_helpers import api_call  # noqa: E402 — after the star import

#: US-PAY-012 TC-2's own figure, and the one the PO worked through.
OWED = Decimal("948.20")
BILLED_ON = date(2026, 4, 22)
REQUESTED_ON = date(2026, 8, 15)
APPROVED_ON = date(2026, 8, 16)
POSTED_AT = datetime(2026, 8, 16, 10, 0, tzinfo=timezone.utc)


def _an_account(brazos, marcus):
    """An account that actually OWES 948.20 — an issued, unpaid bill.

    ⚠ **NOT `an_overpaid_account`.** That helper builds an account in CREDIT,
    and `request_write_off` refuses on the spot: *"a write-off of 948.20 is
    more than the 0 this account actually owes … Writing off more than was
    billed would put revenue into bad debt that no customer was ever charged."*
    Which is the rule working, and a fixture that provoked it would have made
    every case here fail for a reason that has nothing to do with the
    two-person control.
    """
    with tenant_ctx(brazos):
        account = an_account_of(marcus, brazos)
        an_issued_bill(
            brazos,
            account,
            number=f"BL-2604-{uuid.uuid4().hex[:6]}",
            total=OWED,
            issued_on=BILLED_ON,
        )
    return account


def _requested_by(brazos, actor, account):
    """A write-off REQUEST, raised by `actor`. Moves no money (TC-1)."""
    with tenant_ctx(brazos):
        return writeoffs.request_write_off(
            actor,
            account_id=account.pk,
            amount=OWED,
            reason="uncollectible_120_days",
            note=f"regression {uuid.uuid4()}",
            requested_on=REQUESTED_ON,
        )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE ROLE SPLIT — the half of the brief's sentence that IS true
# ══════════════════════════════════════════════════════════════════════════


def test_a_billing_clerk_cannot_approve_the_write_off_they_requested(brazos, marcus):
    """**THE CONTROL, AS IT ACTUALLY EXISTS.** A clerk raises; a clerk cannot sign.

    ⚠ **CALLED AT THE SERVICE, NOT THROUGH THE ROUTE, DELIBERATELY.** The gate
    is `@require_role(SYSTEM_ADMIN)` on `approve_write_off` itself — not on a
    view — and that is the half that matters: a runbook, a job or another
    module reaches the service and never the route. A test that only pressed
    the HTTP door would pass over a gate that had moved onto it.
    """
    account = _an_account(brazos, marcus)
    requested = _requested_by(brazos, marcus, account)

    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError):
            writeoffs.approve_write_off(
                marcus,
                write_off_id=requested.write_off_id,
                approved_on=APPROVED_ON,
                posted_at=POSTED_AT,
            )

    # AND NOTHING MOVED. A refused approval must leave the request exactly as it
    # was — no posting, no plan closed, no status change.
    with tenant_ctx(brazos):
        row = WriteOff.objects.get(pk=requested.write_off_id)
    assert row.status == "requested"
    assert row.journal_entry_id is None, "a refused approval posted bad debt"
    assert row.approved_by_id is None and row.approved_on is None


def test_an_admin_signs_the_clerks_request_and_the_money_moves(brazos, marcus, dana):
    """The other side of the same control: a DIFFERENT person decides.

    `BR-PAY-020` — *"INITIATED in Payments, APPROVED in Finance"* — and 7·3b's
    own annotation, *"the requester asks from, a different person decides
    here"*.
    """
    account = _an_account(brazos, marcus)
    requested = _requested_by(brazos, marcus, account)

    with tenant_ctx(brazos):
        approved = writeoffs.approve_write_off(
            dana,
            write_off_id=requested.write_off_id,
            approved_on=APPROVED_ON,
            posted_at=POSTED_AT,
        )
        row = WriteOff.objects.get(pk=requested.write_off_id)

    assert approved.status == "approved"
    assert row.journal_entry_id is not None, "an approved write-off posts DR write-off / CR AR"
    assert str(row.requested_by_id) != str(row.approved_by_id)


# ══════════════════════════════════════════════════════════════════════════
# 2 · BOTH ACTS RECORDED DISTINCTLY — the half BR-PAY-037 actually specifies
# ══════════════════════════════════════════════════════════════════════════


def test_the_two_acts_are_two_columns_and_neither_is_a_boolean(brazos, marcus, dana):
    """`BR-PAY-037`: *"both acts recorded distinctly."*

    ⚠ **BOTH ARE ASSERTED NOT-NULL BEFORE THEY ARE COMPARED.** On an
    unattributed row `requested_by == approved_by` is `None == None`, which a
    naive inequality would read as *two different people* — a check that passes
    wrongly on precisely the row it exists to catch.
    """
    account = _an_account(brazos, marcus)
    requested = _requested_by(brazos, marcus, account)
    with tenant_ctx(brazos):
        writeoffs.approve_write_off(
            dana,
            write_off_id=requested.write_off_id,
            approved_on=APPROVED_ON,
            posted_at=POSTED_AT,
        )
        row = WriteOff.objects.get(pk=requested.write_off_id)

    assert row.requested_by_id is not None, "the requester was not recorded"
    assert (
        row.approved_by_id is not None
    ), "the approver was not recorded — BR-PAY-037 rests on this"
    assert row.requested_on == REQUESTED_ON
    assert row.approved_on == APPROVED_ON


def test_the_queue_renders_both_acts_separately_so_asked_by_is_drawable(brazos, marcus, dana):
    """7·3b's *"Asked by, which is what makes the control visible."*

    The queue row carries `requested_by` and `approved_by` as distinct members
    and folds neither into a boolean — a row showing only *approved* would
    erase the control the rule leans on, which is `refund_queue`'s own recorded
    reasoning one table over.
    """
    from apps.payments import api as payments_api

    account = _an_account(brazos, marcus)
    _requested_by(brazos, marcus, account)

    listed = api_call(
        payments_api.write_offs,
        "get",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        query={"f.status": "requested"},
    )
    assert listed.status_code == 200
    rows = listed.data["rows"] if "rows" in listed.data else listed.data["results"]
    row = next(r for r in rows if str(r["account_id"]) == str(account.pk))
    assert "requested_by" in row and "approved_by" in row
    assert row["requested_by"] is not None
    assert row["approved_by"] is None, "nothing is approved yet and the row must say so"
    # B14 rule 31 — a NAME is offered beside the id so a screen never draws one.
    assert "requested_by_name" in row


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE FACT THE BRIEF GETS WRONG, ASSERTED OUT LOUD
# ══════════════════════════════════════════════════════════════════════════


def test_an_ADMIN_may_still_approve_their_own_request_BR_PAY_037_permits_it(brazos, marcus, dana):
    """⚠ **THIS IS NOT A GAP. IT IS `BR-PAY-037`, CONFIRMED, AND IT IS v1.**

    *"the SAME user holding the approver role MAY initiate AND approve in v1 —
    both acts recorded distinctly; enforced separation-of-duties = v2."*

    The task line for `P4.24` reads *"A requester cannot approve their own"*,
    which is true of a **Billing Clerk** (the case above) and **false of an
    Admin** (this one). It is asserted rather than left unstated so that a lane
    meeting it cannot quietly "fix" the product into breaking a CONFIRMED rule.

    **If enforced separation of duties is ever ruled in, this test is what goes
    red, and it names the rule to supersede.** That is the correct failure: a
    ruling, not a bug fix.
    """
    account = _an_account(brazos, marcus)
    requested = _requested_by(brazos, dana, account)  # the ADMIN raises it

    with tenant_ctx(brazos):
        approved = writeoffs.approve_write_off(  # …and signs it
            dana,
            write_off_id=requested.write_off_id,
            approved_on=APPROVED_ON,
            posted_at=POSTED_AT,
        )
        row = WriteOff.objects.get(pk=requested.write_off_id)

    assert approved.status == "approved", (
        "a self-approval by an Admin was refused. That REVERSES BR-PAY-037, which is "
        "CONFIRMED and permits it in v1 — so if this is now intended, supersede the rule "
        "through HUMAN-GUIDE §6 and delete this test in the same commit. It is not a bug."
    )
    # …and BOTH acts are still recorded, which is the condition the rule attaches.
    assert row.requested_by_id is not None and row.approved_by_id is not None
    assert str(row.requested_by_id) == str(row.approved_by_id)


def test_the_debt_is_not_written_off_twice(brazos, marcus, dana):
    """A second approval is a reported no-op, never a second posting.

    `BR-PAY-002` — *"an approved write-off has already reduced receivables, and
    doing it twice would halve them."* Part of the same control: the second
    pair of eyes is worth nothing if the signature can be applied repeatedly.
    """
    account = _an_account(brazos, marcus)
    requested = _requested_by(brazos, marcus, account)
    with tenant_ctx(brazos):
        first = writeoffs.approve_write_off(
            dana,
            write_off_id=requested.write_off_id,
            approved_on=APPROVED_ON,
            posted_at=POSTED_AT,
        )
        second = writeoffs.approve_write_off(
            dana,
            write_off_id=requested.write_off_id,
            approved_on=APPROVED_ON,
            posted_at=POSTED_AT,
        )
        row = WriteOff.objects.get(pk=requested.write_off_id)

    # `str()` on both sides: `WriteOffResult.journal_entry_id` is a string and
    # the column is a `UUIDField`, so a bare `==` compares a str with a UUID and
    # is False for the SAME id — a check that could only fail, which is the
    # shape law 7 habit 2 asks about and this one had.
    assert str(first.journal_entry_id) == str(row.journal_entry_id)
    assert str(second.journal_entry_id) == str(row.journal_entry_id)
    assert "already_approved" in {problem["code"] for problem in second.problems}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-138-BRC07 §3 P4.24 · 05-prototype/06 Payments Page Blueprint.pdf
#         p23 + screen 7·3b (p87) · apps/payments/writeoffs.py · api.py
#         (`write_offs`) · BR-PAY-020 · BR-PAY-037 · BR-PAY-1120 · DEF-100
# generated: 2026-09-23 by the CR-138 lane P4-READS
# gates: RED PROVED FIRST — the two mutations are quoted in this file's own
#        docstring, each observed rather than predicted.
# exceptions:
#   (1) ⚠ **THE TASK LINE IS WRONG AND THE TEST SAYS SO.** "A requester cannot
#       approve their own" is true for a Billing Clerk and FALSE for an Admin;
#       BR-PAY-037 is CONFIRMED and permits the latter in v1. Reported rather
#       than built around, because adding the refusal would overturn a CONFIRMED
#       rule with no ruling (law 13, prime directive).
#   (2) THE CLERK CASE CALLS THE SERVICE, NOT THE ROUTE. The gate lives on
#       `approve_write_off` itself and a job or a runbook never touches a view.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
