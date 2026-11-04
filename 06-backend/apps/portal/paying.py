# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-050 (EP-CWP-09) — collecting a connection fee.
#           Screen: CWP-050 (blueprint `P36`) at `/{tenant}/portal/fees`
# Rules:    BR-CWP-058 (the consequence is shown before the commit) ·
#           BR-CWP-056 (the Pay control appears disabled until rails) ·
#           BR-CUS-090 (the quote, what was taken, and the difference) ·
#           BR-CWP-010 (tenant AND the login's own facts, in the query) ·
#           BR-CWP-012 (read through the owning module; no second copy) ·
#           BR-CWP-093 (nothing empty ever appears) · B14 rule 31 (no database
#           id on screen) · rule 33 (a refusal is five or six words) ·
#           rule 35 (the catalogue writes the words) ·
#           CLAUDE.md hard rule 2 (4 stored, 2 displayed)
# Ruling:   PO 2026-09-05 (`OQ-CWP-1600`), verbatim: *"we have reconnect fees in
#           charge code, plan will tell you how much to charge, plan is attached
#           to unit and unit is attached to account"*
# Tests:    06-backend/tests/test_us_cwp_050_fees.py
# Impacts:  apps/portal/api.py (`GET portal/fees`) ·
#           07-frontend/src/portal/payments/Fees.tsx
# ───────────────────────────────────────────────────────
"""WHAT STARTING SERVICE WILL COST — and every figure on it is READ.

⚠ **A HARDCODED FEE OR DEPOSIT ANYWHERE IS NOW A DEFECT** (PO ruling
2026-09-05, `OQ-CWP-1600`). `US-CWP-050` §4 quotes `$185.00`, `$150.00`,
`$150.00` and `$25.00`, and it would be trivial and wrong to satisfy the story
with four constants. So:

  * the *before we start* lines are `service_request_fees` rows — a quote a
    clerk raised from the tenant's own charge catalogue, kept with its
    `charge_code` snapshotted beside it so a retired code still prints;
  * the DEPOSIT is `rating.PlanDepositRule.amount`, reached by walking
    **request → resolved unit → plan**, through `rating_seam.deposit` — the
    same function `CWP-008` quotes from before anybody applies, which is what
    `§7`'s *"must equal the figure quoted on `CWP-008`"* asks for.

⚠ **AND A DEPOSIT NOBODY HAS PRICED IS AN ABSENCE, NEVER `$0.00`.** That is
`selectors.DEPOSIT_NOT_PRICED`'s posture one screen along on `CWP-057`, and the
reason is the same: a `$0.00` tells an applicant a deposit costs nothing, passes
every check in this repo, and is discovered to be wrong at the counter.

WHAT IS NOT HERE, NAMED RATHER THAN IMPLIED
--------------------------------------------
* **NO WAY FOR A CUSTOMER TO PAY A FEE.** ⚠ This said *"there is no payment
  gateway"* until `apps/payments/gateway.py` landed hours later and the hold's
  own expiry test went red. A gateway exists; a FEE PATH does not — the quote
  never posts to the ledger, `collect_fee` is Admin or Billing Clerk at a
  counter, and `write_points.WRITE_POINTS`'s `payment` row still carries
  `function=None`. The control is visible, disabled and carries THAT reason
  (`BR-CWP-056` / R3), and the expiry test now watches the write point.
* **NO PART AMOUNT IS EXPRESSIBLE** (`US-CWP-050` TC-6 — *"fees are collected in
  full before work starts"*). The payload carries ONE figure and no minimum, no
  instalment and nothing a screen could turn into an amount box, so a partial
  payment is refused by there being nothing to say it with.
* **NO CARD FEE IS COMPUTED** (`OQ-1394`, CLOSED 2026-09-04 — the payer is a
  per-tenant switch `card_fee_payer` on the finance-controls family). Closing
  that question settled the utility's INTENTION and not the arithmetic: there is
  no processor, therefore no fee schedule, and `settings_families.py` records
  that `apps/payments` refuses to price a surcharge by name rather than
  inventing a percentage. This screen shows no fee line at all and says why.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.portal import money
from apps.portal.seams import customers_seam, rating_seam

#: `BR-CWP-056` / `CR-068` R3 — the *Pay $335.00* control is visible, disabled
#: and carries its reason. Never hidden, never live-but-inert.
#:
#: ⚠ **IT READ `no_rails` FOR ONE AFTERNOON AND THAT WORDING IS NOW FALSE.**
#: `apps/payments/gateway.py` landed the same day (lane B, `US-CWP-045`), this
#: story's own hold-expiry test went RED naming this control, and the refusal
#: turned out to be true for a DIFFERENT reason: a fee is a `service_request_
#: fees` QUOTE that never posts to the ledger, `collect_fee` is a counter action
#: gated to Admin or Billing Clerk, and `portal/write_points.py`'s `payment` row
#: still carries `function=None` — the product's own statement that the portal
#: writes no payment at all. So the control stays held and the reason is the one
#: that is true.
HELD_NO_FEE_PAYMENT_PATH = "no_fee_payment_path"

#: When each line falls due. The FEE lines take the request's own
#: `fee_timing` (`collect_now | collect_later`), which is where *"collect-now-or-
#: later is a property of the request"* already lives; the DEPOSIT is always the
#: first bill, which is `availability.py`'s `on_first_bill` for the same figure.
WHEN_BEFORE_WE_START = "before_we_start"
WHEN_LATER = "later"
WHEN_FIRST_BILL = "on_your_first_bill"
WHEN_NOT_RECORDED = "not_recorded"

#: The gaps this read NAMES rather than filling in.
DEPOSIT_NOT_PRICED = "deposit_not_priced"
FEE_TIMING_NOT_RECORDED = "fee_timing_not_recorded"
NO_CARD_FEE_IN_A_SANDBOX = "no_card_fee_computed"

#: ⚠ **FEES ARE QUOTED AFTER APPROVAL** (`US-CWP-050` TC-8, `B19` §12.3 —
#: *"Approving creates real service and real charges, so the decision is made
#: deliberately"*). A submitted request with three priced lines on it is not a
#: page this customer may open, and the SERVER is what decides that rather than
#: a screen choosing not to draw one.
QUOTABLE_STATES = ("approved", "in_fulfilment", "completed")

#: `collect_now` / `collect_later`, as `customers.ServiceRequest` writes them.
COLLECT_NOW = "collect_now"
COLLECT_LATER = "collect_later"


def _fee_when(request: Any) -> str:
    timing = getattr(request, "fee_timing", None)
    if timing == COLLECT_NOW:
        return WHEN_BEFORE_WE_START
    if timing == COLLECT_LATER:
        return WHEN_LATER
    #: ⚠ **NOT GUESSED.** The money is owed either way; only WHEN is unknown, and
    #: a screen saying *before we start* over a request nobody set a timing on
    #: would be inventing a deadline.
    return WHEN_NOT_RECORDED


def _quotable(request: Any) -> bool:
    return str(getattr(request, "state", "")) in QUOTABLE_STATES


def _deposit_for(tenant_id: Any, request: Any) -> Decimal | None:
    """The plan's deposit for this class of customer — **the PO's own walk**.

    PO 2026-09-05, verbatim: *"plan will tell you how much to charge, plan is
    attached to unit and unit is attached to account"*. An applicant has no
    account yet, so the walk starts one link earlier at the request's RESOLVED
    UNIT, and the class is the residential one — the same judgment
    `availability.py` records for a visitor who has not said what kind of
    customer they are.

    `None` at any link is `None` here: no resolved unit, no plan in force, or a
    plan that prices no deposit for this class. **Never `Decimal("0")`** — a
    zero states that a deposit was assessed and set to nothing, which is a
    different fact from never having been assessed (`deposit_rule_for`'s own
    docstring makes the same distinction for billing).
    """
    unit_id = getattr(request, "resolved_unit_id", None)
    if not unit_id:
        return None
    plan_id = rating_seam.current_plan_id(tenant_id, unit_id)
    if not plan_id:
        return None
    return rating_seam.deposit(tenant_id, plan_id, customers_seam.home_account_type_id())


def _line(*, what: str, when: str, amount: Decimal, waived: bool, settled: bool) -> dict[str, Any]:
    cell = money.amount(amount)
    return {
        "what": what,
        "when": when,
        #: Both precisions travel — four stored, two displayed — for the reason
        #: `apps/portal/money.py` gives: a payload carrying only one of them
        #: cannot be checked against hard rule 2 at all.
        "amount": cell["amount"],
        "display": cell["display"],
        "currency": cell["currency"],
        #: ⚠ **A WAIVED FEE STAYS ON THE LIST, STRUCK THROUGH** (`US-CWP-050`
        #: TC-3). The record keeps a waiver rather than deleting the line, which
        #: is what lets a customer see they were LET OFF rather than wonder
        #: whether they were quoted correctly. The REASON is the clerk's own
        #: note and is not on the wire (`BR-CWP-051`'s posture on a write-off).
        "waived": waived,
        "settled": settled,
    }


def fees_position(tenant_id: Any, *, phones: list[str]) -> dict[str, Any]:
    """`CWP-050` whole, for the request this login raised, or an absence.

    ⚠ **THE REQUEST IS FOUND THE WAY `/requests` FINDS IT** — through
    `customers_seam.my_requests`, which matches on the tenant AND the login's own
    contact facts (`BR-CWP-010`). Nothing here takes a reference from a caller,
    so a stranger cannot ask what `SR-26-0061` costs.

    ⚠ **THE REFERENCE IS THE IDENTITY AND THERE IS NO ID ON THE WIRE** (B14 rule
    31): `SR-26-0061` is what the applicant would read out on the telephone.

    Worked, `US-CWP-050` §4: `SR-26-0061`, approved, with `CONN $185.00` and
    `CC-METERT $150.00` before we start, `CC-REQFEE $25.00` **waived**, and the
    plan's `$150.00` deposit on the first bill →
    **`to_pay_now` `$335.00`**, `on_first_bill` `$150.00`, four rows on screen.
    """
    empty = {
        "any": False,
        "reference": None,
        "lines": [],
        "to_pay_now": None,
        "on_first_bill": None,
        "available": False,
        "held_reason": HELD_NO_FEE_PAYMENT_PATH,
        "problems": [],
    }
    if not phones:
        return empty

    request = (
        customers_seam.my_requests(tenant_id, phones=list(phones))
        .filter(state__in=QUOTABLE_STATES)
        .order_by("-created_at")
        .first()
    )
    if request is None or not _quotable(request):
        return empty

    from apps.customers import models as customers_models
    from apps.customers import service_request_service

    rows = list(
        customers_models.ServiceRequestFee.objects.filter(
            tenant_id=tenant_id, request_id=request.id
        ).order_by("line_no")
    )
    totals = service_request_service.fee_total_to_collect(request.id)

    when = _fee_when(request)
    problems: list[dict[str, Any]] = []
    if when == WHEN_NOT_RECORDED:
        problems.append(
            {
                "code": FEE_TIMING_NOT_RECORDED,
                "br_ref": "BR-CUS-090",
                "detail": "this request records no collect-now-or-later, so the fees are "
                "listed without a when. The money is owed either way; only the moment is "
                "unrecorded, and it is not guessed.",
            }
        )
    problems.append(
        {
            "code": NO_CARD_FEE_IN_A_SANDBOX,
            "br_ref": "OQ-1394",
            "detail": "who pays the card fee is a per-tenant switch (card_fee_payer), and "
            "closing that question settled the utility's intention rather than the "
            "arithmetic. There is no processor and therefore no fee schedule, so no fee "
            "line is drawn and none is computed.",
        }
    )

    lines = [
        _line(
            what=row.description or row.charge_code,
            when=when,
            amount=Decimal(row.amount),
            waived=bool(row.waived),
            settled=row.settled_at is not None,
        )
        for row in rows
    ]

    deposit = _deposit_for(tenant_id, request)
    if deposit is None:
        problems.append(
            {
                "code": DEPOSIT_NOT_PRICED,
                "br_ref": "OQ-CWP-1600",
                "detail": "this address's plan prices no deposit for a residential customer, "
                "so no deposit line is drawn. A zero would state that a deposit was assessed "
                "and set to nothing, which is a different fact.",
            }
        )
    else:
        lines.append(
            _line(
                what="Security deposit",
                when=WHEN_FIRST_BILL,
                amount=deposit,
                waived=False,
                settled=False,
            )
        )

    return {
        "any": True,
        #: `SR-26-0061` — a human reference, never a row id (B14 rule 31).
        "reference": request.request_no,
        "lines": lines,
        #: ⚠ **WHAT IS LEFT TO PAY, NOT WHAT WAS QUOTED.** `fee_total_to_collect`
        #: is `BR-CUS-090`'s own arithmetic — quoted, less what an invoice
        #: settled, less what the counter took — so `US-CWP-050` TC-4's *"the
        #: request moves out of fees due"* falls out of it rather than being a
        #: second sum here. On a request nothing has been taken against, it is
        #: the story's `$335.00`.
        "to_pay_now": money.amount(totals["outstanding"]),
        #: ⚠ **AND THE DEPOSIT IS NOT IN IT** (TC-4). It is not a fee line, it is
        #: not in `fee_total_to_collect`, and collecting the fees leaves it
        #: exactly where it was.
        "on_first_bill": None if deposit is None else money.amount(deposit),
        "available": False,
        "held_reason": HELD_NO_FEE_PAYMENT_PATH,
        "problems": problems,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-050 (04-docs/05-modules/15-portal/06-epics/EP-CWP-09-paying.md) + 08-screen-layouts.md CWP-050 + 12-governance/02-decision-log.md 2026-09-05 §3 (OQ-CWP-1600) + 01-open-questions.md OQ-1394
# screens: CWP-050
# generated: 2026-09-05 by the CR-068 phase 5 lane D (autopay · refunds · fees)
# checklist: A✔ B✔ C✔(tests/test_us_cwp_050_fees.py — RED first: ImportError, no such module) D✔ E✔ F✔ G✔ H=n/a(no money is written, no rate resolved, no RLS policy, no idempotency key — this reads)
# gates: ruff✔ black✔
# exceptions: (1) NO CUSTOMER-FACING FEE PAYMENT PATH — a gateway exists (lane B, US-CWP-045) and a FEE path does not; the hold carries its own expiry test, which watches write_points.WRITE_POINTS's `payment` row rather than the gateway module
#         (2) NO CARD FEE IS COMPUTED (OQ-1394 closed the payer, not the arithmetic)
#         (3) A DEPOSIT NOBODY HAS PRICED IS AN ABSENCE, never $0.00 (CWP-057's posture)
#         (4) THE FEE LINES' `when` IS THE REQUEST'S, and an unrecorded timing is
#         reported rather than assumed to be *before we start*
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
