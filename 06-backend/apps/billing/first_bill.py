# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-010 (First bill: prorated from move-in day + the one-time
#           lines)   Screens: S31 (single-account mode) · S30
# Rules:    BR-BIL-012 (first bill: prorated from move-in day; carries the
#           DEPOSIT — non-taxable, deposit-liability, never revenue — and the
#           CONNECTION charge) · BR-BIL-062 (a first bill with NO PRIOR READ
#           prices at the plan's minimum for the category, prorated, with no
#           usage line — and is NOT a missing-read exception) · BR-CUS-056
#           (billing boundaries at moves: same-day is no-gap-no-double) ·
#           BR-PAY-012 (a deposit-purpose payment satisfies the deposit line) ·
#           BR-RAT-020/023 (the deposit figure is plan × account_type reference
#           data) · BR-BIL-007 (a fee is a tenant charge code, never a literal) ·
#           B4.3 / B4.4 ❄️ (calendar-day proration; tier spans scale with it) ·
#           B4.2 (fees and deposits are never taxed) · CLAUDE.md rule 1
#           (tenant scoping) · rule 2 (money) · rule 3 (units)
# Golden:   GT-3 ❄️ (proration) · GT-15 (capacity, prorated like base) ·
#           WE-6 (ACC-1350, move-in 12 Jul, 20/31 → total 287.23) · WE-16
#           (a capacity rider from 22 Jul → 10/31 × 40.00 = 12.90)
# Tests:    06-backend/tests/test_us_bil_010_first_bill.py
# Journeys: J07 (first-bill life) · J2 step 8
# Impacts:  apps/billing/single.gather_single (the gather this narrows) ·
#           apps/billing/runs.calculate_account (stages 1–6, `bill_type=first`) ·
#           apps/billing/payments_seam.deposit_paid_for_account ·
#           apps/rating/selectors.deposit_rule_for + charge_by_code
# ───────────────────────────────────────────────────────
"""The FIRST bill — the one bill an account will never get again.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this decides the DEPOSIT figure that lands
on a customer's first bill and whether it is charged at all (CLAUDE.md 🔒 money
rounding / rating math adjacency + rule 4, because the line freezes at issue).
AI-authored 2026-08-15 under the PO ruling of 2026-08-09; it needs a row in
12-governance/09-human-review-ledger.md.

⚠ CORRECTED 2026-09-01 (DEF-2791) — THE PARAGRAPH BELOW IS HISTORY, NOT THE
CURRENT STATE. `human_owned.txt` carries `06-backend/apps/billing/first_bill.py`
today ("First-bill proration and one-time lines — deposits, connection charges
and a part-month base"), measured 2026-09-01, so **G7 DOES read the markers
above**. The list does not date this line, so no ruling is dated here either —
inventing one would be worse than the gap. The ask below was answered; it is
kept because why a money path went unguarded is worth knowing.

⚠ **NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE**, so G7
does not read the markers above. Reported for the PO batch rather than
self-granted — editing that guard list is itself a process event.

────────────────────────────────────────────────────────────────────────────
WHAT MAKES IT DIFFERENT, AND ALL OF IT IS BR-BIL-012
────────────────────────────────────────────────────────────────────────────
A first bill is *"prorated from move-in day (B4.3) and carries the one-time
lines — deposit (non-taxable → deposit liability, never revenue) + connection
charge"*. Worked, WE-6 verbatim: ACC-1350 moves in **12 July**, so the period is
**20 of 31 days**; the bases prorate to **7.74 / 5.16 / 11.61**, the water
tier-1 span scales to **3.225806 kgal**, taxable comes to **102.53** and tax to
**9.70**, and then the two one-time lines land — deposit **150.00** and CONN
**25.00**, neither taxed — for a total of **287.23**.

**THE PRORATION ITSELF IS NOT COMPUTED HERE.** B4.3/B4.4 are ❄️ finance-signed
and live in the rating engine; this module's whole contribution to that half is
handing stage 1 the right WINDOW — `service_days` counted from the move-in day
inclusive, against the CYCLE's length as the denominator. Getting the
denominator wrong is the whole failure mode: 20/20 charges a full month's base
for twenty days and every figure downstream is quietly right about the wrong
thing.

**`bill_type=first` IS DERIVED, NEVER SUPPLIED** (US-BIL-010 TC-6). It follows
from the move-in date falling inside the period, and a caller that asked for a
first bill on an account that did not move in this period is refused by name. A
bill type that a caller could set is a bill type that will eventually be set
wrong, and this one changes which lines exist.

────────────────────────────────────────────────────────────────────────────
THE DEPOSIT LINE, AND THE $150.00 THAT MUST NOT BE TAKEN TWICE
────────────────────────────────────────────────────────────────────────────
Three reads decide this line and each answers a different question:

  1. **Does this plan ask a deposit of this category?** `rating.selectors.
     deposit_rule_for` (BR-RAT-020/023). `None` means *no deposit is asked* and
     NO LINE IS EMITTED — never a $0.00 one, because a zero line on a first bill
     states that a deposit was assessed and waived.
  2. **Has the customer already paid one?** `payments_seam.
     deposit_paid_for_account` (BR-PAY-012). Money paid with purpose `deposit`
     SATISFIES the line, so a customer who paid at the counter is not billed
     again.
  3. **Could we ask at all?** If the payments seam is unreachable the read
     answers **None**, and this module REFUSES the deposit line rather than
     treating None as zero. That distinction is the entire safety of the
     paragraph: zero means *they have paid nothing* and would bill $150.00;
     None means *nobody asked*, and billing $150.00 on that basis takes it a
     second time from somebody who is already moving house — onto a bill that
     is immutable the moment it issues (hard rule 4).

**IT IS NEVER TAXABLE AND NEVER REVENUE.** B4.2 keeps a fee-class line out of
the tax base structurally, and BR-BIL-012 sends the deposit to the
deposit-liability DESIGNATION — the utility is holding the customer's money, not
earning it. The GL side is `issue._gl_account_for`'s and is not re-decided here.

────────────────────────────────────────────────────────────────────────────
THE CONNECTION CHARGE IS A CODE, NEVER A NUMBER
────────────────────────────────────────────────────────────────────────────
BR-BIL-007/019/020: *"lines come ONLY from rules and charge codes — free-typed
amounts never exist on any bill."* So the caller names a CODE (`"CONN"` in the
fixtures, and the tenant's own in the product) and the amount comes from
`rating.selectors.charge_by_code`. An unknown or deactivated code is REFUSED by
name; a percent-shaped rule is refused too, because a percentage needs a basis
nobody has stated and its `amount` column is not a flat price.

────────────────────────────────────────────────────────────────────────────
BR-BIL-062 — THE NO-PRIOR-READ CASE, AND WHY IT REFUSES TODAY
────────────────────────────────────────────────────────────────────────────
The rule is CONFIRMED and is not in question: a first bill with no prior read
prices at *"the plan's minimum for the account's consumer category, prorated on
calendar days, with NO usage line"*, and it is explicitly **not** a missing-read
exception — the account is never listed under Missing reads and no estimated
read is created.

**What is missing is the INPUT, not the decision.** The minimum-bill amount
lives on `plans.minimum_bill_amount` / `plan_services.minimum_amount`, and
neither can travel on the rating seam's `TariffConfig` today — the rating lane
names that hole in its own words (`apps/rating/pricing/stages/apply_charges.py`:
*"there is no input to apply. Emitting the line would require inventing the
threshold"*), and GT-13 is PROPOSED rather than frozen. So `refuse_without_a_
minimum` states the rule, names the missing input and REFUSES; it does not raise
`NotImplementedError` on an OQ, because nothing is open — this is an
unimplemented upstream input and pretending otherwise would file a question
somebody already answered. **REPORTED, in `FIRST_BILL_UNAVAILABLE`.**
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from apps.billing import gather, models, payments_seam, rating_seam, runs, single
from apps.billing.contracts import AccountBillingData
from apps.billing.exceptions import BillingRuleError

ZERO = Decimal("0")

#: BR-BIL-012's own two lines, named so a caller cannot mistype one into
#: existence and so the descriptions on a customer's bill come from one place.
DEPOSIT_DESCRIPTION = "Security deposit"
DEFAULT_CONNECTION_CHARGE_CODE = "CONN"

FIRST_BILL_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "no_prior_read_minimum_has_no_input",
        "br_ref": "BR-BIL-062 · BR-RAT-028 · B4 §minimum bill",
        "detail": "BR-BIL-062 is CONFIRMED and is not in question: a first bill with no "
        "prior read prices at the plan's minimum for the category, prorated, with no usage "
        "line. The minimum AMOUNT cannot reach the engine — neither "
        "`plans.minimum_bill_amount` nor `plan_services.minimum_amount` travels on the "
        "rating seam's TariffConfig, which the rating lane records as a named hole in "
        "`pricing/stages/apply_charges.py`, and GT-13 is PROPOSED rather than frozen. So "
        "the case REFUSES by name instead of inventing a floor. It is NOT stubbed on an "
        "open question: nothing is open.",
    },
    {
        "code": "deposit_interest_is_not_a_first_bill_line",
        "br_ref": "BR-CUS-057 · BR-BIL-013",
        "detail": "interest accrues on a deposit from receipt and is applied at CLOSURE "
        "(BR-BIL-013, and OQ-179's *'we dont have to give depoiste back in between'*). "
        "Nothing here computes or credits it — the first bill charges the deposit, the "
        "final bill settles it with its interest.",
    },
)


@dataclass(frozen=True)
class OneTimeLines:
    """BR-BIL-012's two lines, and what could not be answered about them.

    They travel as `rating_seam.RatedLine`s of kind `fee` because that is what
    B4.2 makes them structurally: the tax base is computed by KIND, so a
    fee-class line cannot reach the tax pass even if somebody flags it. The
    deposit's DESTINATION (the deposit-liability designation rather than a
    revenue account) is BR-BIL-010's stamp at issue and is not decided here.
    """

    lines: tuple[rating_seam.RatedLine, ...] = ()
    deposit_asked: Decimal | None = None
    deposit_already_paid: Decimal | None = None
    problems: tuple[dict[str, Any], ...] = ()

    @property
    def total(self) -> Decimal:
        return sum((line.amount for line in self.lines), ZERO)


def _rating_read(name: str) -> Any:
    """Rating's published read, by NAME at call time (B1, the house idiom)."""
    return gather._resolve("rating", name)


def is_first_bill(*, moved_in_on: date | None, period_start: date, period_end: date) -> bool:
    """US-BIL-010 TC-6 — the type is DERIVED from the move-in date. Pure.

    A first bill is the bill of a period the customer moved into. Nothing else
    makes one, and in particular a caller's opinion does not: `bill_type` decides
    whether a deposit and a connection charge exist on somebody's bill, and a
    field a caller could set is a field that will eventually be set wrong.
    """
    if moved_in_on is None:
        return False
    return period_start <= moved_in_on <= period_end


def deposit_line_for(
    data: AccountBillingData,
    *,
    account_type_id: Any,
    description: str = DEPOSIT_DESCRIPTION,
) -> OneTimeLines:
    """BR-BIL-012's deposit line — or no line, or a refusal. Never a guess.

    Worked, WE-6: Residential on the Residential Standard plan asks **150.00**,
    the customer has paid nothing, so the line is **150.00** and the first bill
    totals **287.23**. Worked the other way (BR-PAY-012): the same customer paid
    **150.00** at the counter last week, so the line is **not emitted** and the
    bill is **137.23** — the utility does not hold the money twice.

    THREE ANSWERS AND THEY ARE DIFFERENT FACTS:
      * no rule ⇒ **no line**. This plan asks this category for no deposit. A
        $0.00 line would say one was assessed and waived.
      * paid in full ⇒ **no line**, and `deposit_already_paid` carries the
        figure so the screen can say why it is not there.
      * paid in PART ⇒ the REMAINDER is billed. 150.00 asked, 50.00 paid → a
        **100.00** line.
      * the payments seam unreachable ⇒ **REFUSED**, naming the read. See the
        module docstring: None is not zero, and the difference is $150.00 of
        somebody else's money on an immutable bill.
    """
    read_rule = _rating_read("deposit_rule_for")
    if read_rule is None:
        raise BillingRuleError(
            "apps.rating.selectors.deposit_rule_for is not published, so the deposit a "
            "first bill must carry (BR-BIL-012) cannot be resolved. The figure is "
            "reference data on `plan_deposit_rules` (BR-RAT-020/023) and nothing here "
            "invents one — a deposit is the customer's money and the amount is the "
            "tenant's to state.",
            br_ref="BR-BIL-012",
        )
    if data.rate_plan_id is None:
        raise BillingRuleError(
            f"account {data.account_no} has no plan, so no deposit rule can be resolved "
            "for its first bill (BR-BIL-012 / BR-RAT-020). Stage 1 refuses an account "
            "with no plan for the same reason.",
            br_ref="BR-BIL-012",
        )
    if account_type_id is None:
        # ⚠ `DEF-BIL-5318` (2026-09-15) — THIS REFUSAL FIRED ON EVERY ACCOUNT
        # FROM 2026-08-16 TO 2026-09-15 AND THE FAULT WAS NOT THE ACCOUNT'S.
        # `one_time._account_type_id` read `account_type_id` off customers'
        # `account_detail` seam, which did not publish that key, and `.get()`
        # turned the absent KEY into an absent CATEGORY. The first kind had
        # never produced a bill. Fixed on both sides: customers publishes the
        # key, and billing's read now ASSERTS it instead of shrugging — so
        # reaching this line again really does mean the account has no
        # category. Nothing about this refusal changed; only what can reach it.
        raise BillingRuleError(
            f"account {data.account_no} names no consumer category, so the deposit rule "
            "for its first bill cannot be resolved — `plan_deposit_rules` is keyed on "
            "rate_plan × account_type (BR-RAT-020/023) and a category is not something "
            "this module may pick.",
            br_ref="BR-BIL-012",
        )

    # `OQ-RAT-12786` (CLOSED 2026-10-03, PO verbatim *"(a) Class or size: the
    # deposit table gets a size column, like charge codes have."*) — the
    # account is passed so a deposit code priced by METER SIZE is asked at
    # this account's connection size; a class-priced code ignores it.
    rule = read_rule(data.rate_plan_id, account_type_id, account_id=data.account_id)
    if rule is None:
        # A real and common configuration, not a gap: this plan asks this
        # category for nothing.
        return OneTimeLines()
    if rule.get("amount") is None:
        # A deposit priced by size that cannot be priced for THIS connection —
        # no size recorded, or a size the code does not price. Refused by name,
        # never billed as no deposit: `None` above is "the plan asks nothing",
        # and this plan DOES ask; the amount is the utility's to state.
        raise BillingRuleError(
            f"the plan's deposit code {rule.get('code')!r} is priced by meter size and "
            f"states no amount for account {data.account_no}'s connection size "
            f"{rule.get('size_class')!r} ({rule.get('refusal')}). The first bill is "
            "refused rather than issued without the deposit the plan asks "
            "(BR-BIL-012 / BR-RAT-020 as superseded in part 2026-10-03).",
            br_ref="BR-BIL-012",
        )

    asked = rule["amount"]
    if _deposit_waived(data.account_id):
        # ── `DEF-BIL-9709` · A WAIVED DEPOSIT IS NOT OWED ─────────────────────
        # BR-CUS-1050 (PO 2026-09-24, *"clark and sysem admin can do it"*): a
        # deposit the plan asked and a clerk WAIVED is kept on the account
        # (`deposit_waived_*`, DEF-CUS-6370) and is not owed. Until 2026-10-05
        # nothing here read it, so Rosa's $150.00 waived for Hardship came back
        # as a $150.00 line. No line — the same answer as paid in full —
        # and `deposit_asked` still says what the plan asked.
        return OneTimeLines(deposit_asked=asked)
    currency = rule.get("currency") or data.currency
    if currency != data.currency:
        # Hard rule 2 — money is never summed across currencies. A deposit rule
        # denominated in something other than the bill's is a configuration
        # error, and netting the two would put a number with no name on a bill.
        raise BillingRuleError(
            f"the deposit rule for account {data.account_no} is denominated in {currency} "
            f"and this bill is in {data.currency}. There is no lawful addition: "
            f"{data.currency} plus {currency} is a number with no name (CLAUDE.md rule 2). "
            "A human re-denominates the rule.",
            br_ref="BR-BIL-012",
        )

    already_paid = payments_seam.deposit_paid_for_account(data.account_id)
    if already_paid is None:
        raise BillingRuleError(
            f"the deposit already paid by account {data.account_no} could not be read "
            f"(apps.payments.credit.deposit_payments_for_account is not published), so its "
            f"first bill cannot say whether the {asked} {currency} deposit is still owed "
            "(BR-BIL-012 / BR-PAY-012). It is REFUSED rather than billed: an unreachable "
            "read answers 'we could not ask', never 'they have paid nothing', and charging "
            "a deposit that was already paid takes the money a second time onto a bill "
            "that is immutable the moment it issues (hard rule 4).",
            br_ref="BR-PAY-012",
        )

    outstanding = asked - already_paid
    if outstanding <= ZERO:
        return OneTimeLines(deposit_asked=asked, deposit_already_paid=already_paid)

    return OneTimeLines(
        lines=(
            rating_seam.RatedLine(
                # ⚠ **THIS WAS `"fee"` UNTIL 2026-08-16 AND IT COST EVERY FIRST
                # BILL CARRYING A DEPOSIT (DEF-181).** B4.2 was the whole reason
                # — a fee-class line is structurally outside the tax base — and
                # `deposit` is outside it in exactly the same way (it is absent
                # from `rating.pricing.contracts.TAX_BASE_KINDS`), so nothing
                # about the tax guarantee changes.
                #
                # What the shared kind DID break is the GL stamp. BR-BIL-010
                # sends a FEE to its charge code's account and a deposit line
                # has no charge code, so `issue._gl_account_for` refused the
                # whole bill — with a message about a missing charge code, on a
                # line that is not a charge at all. US-LED-001's contract table
                # sends this line to the **deposit-liability** designation
                # (*"never revenue"*), and it needs its own kind to be told
                # apart from a fee at the moment the stamp is resolved.
                kind="deposit",
                description=description,
                amount=outstanding,
                taxable=False,  # BR-BIL-012, and the KIND already guarantees it
            ),
        ),
        deposit_asked=asked,
        deposit_already_paid=already_paid,
    )


def _deposit_waived(account_id: Any) -> bool:
    """`DEF-BIL-9709` — did a clerk waive this account's deposit? Read from
    customers' published `account_detail` (`deposit_waiver`, null when nothing
    was waived). An unwired read answers False: the account then bills exactly
    as it did before this fix, never less."""
    detail = gather._resolve("customers", "account_detail")
    if detail is None:
        return False
    # Not caught: an account this tenant cannot read is refused by the
    # gather that ran before this, and a database error must not be swallowed
    # inside a bill's transaction (hard-won law 14).
    return bool((detail(account_id) or {}).get("deposit_waiver"))


def connection_charge_line_for(
    data: AccountBillingData, *, code: str = DEFAULT_CONNECTION_CHARGE_CODE
) -> OneTimeLines:
    """BR-BIL-012's connection charge, from the tenant's CHARGE CODE.

    Worked, WE-6: `CONN` is **25.00** on the Brazos Bend catalogue, so the line
    is 25.00 and is not taxed (B4.2 — a fee never is).

    **NEVER A LITERAL.** BR-BIL-007 and BR-BIL-020 both say it: a bill's lines
    come only from rules and charge codes, and a hand-typed amount does not
    exist on any bill in this product. An unknown code, a deactivated one
    (IS-1 — a retired charge is not chargeable) and a percent-shaped rule are
    each refused by name; the last because a percentage needs a basis nobody
    has stated, and its `amount` column is not a flat price. **A code with no GL
    account is refused too (B12, 2026-09-30)**, exactly as
    `fee_bill.charge_code_line` refuses it, with key
    `billing.oneTime.err.chargeCodeNoGl` and `{code}`.
    """
    read_charge = _rating_read("charge_by_code")
    if read_charge is None:
        raise BillingRuleError(
            "apps.rating.selectors.charge_by_code is not published, so a first bill's "
            "connection charge cannot be resolved (BR-BIL-012). The amount is a tenant "
            "charge code and never a constant (BR-BIL-007).",
            br_ref="BR-BIL-012",
        )
    charge = read_charge(code)
    if charge is None:
        raise BillingRuleError(
            f"charge code {code!r} is not a live charge code of this tenant, so the "
            f"connection charge cannot be placed on account {data.account_no}'s first "
            "bill (BR-BIL-012 / BR-BIL-007). A retired code is not chargeable and nothing "
            "here substitutes an amount.",
            br_ref="BR-BIL-007",
        )
    if charge["amount"] is None:
        raise BillingRuleError(
            f"charge code {code!r} carries a {charge['amount_rule']!r} amount rule, which "
            "needs a basis this bill has not stated, so no connection-charge amount can be "
            "computed (BR-RAT-041). Refused rather than reading its `amount` column, which "
            "is not a flat price for a rule that is not flat.",
            br_ref="BR-BIL-007",
        )
    if not charge.get("gl_account_id"):
        # ── B12 (2026-09-30) · NO GL ACCOUNT, REFUSED AT DRAFT ──────────────
        # `fee_bill.charge_code_line` has refused this since DEF-708, for the
        # reason it gives: BR-BIL-010 (*charge codes carry their own GL*) would
        # refuse the line at ISSUE anyway, and by then a bill number has been
        # spent on a draft that can never become a bill — and on a first bill
        # the whole document dies with it, deposit and usage included. The
        # connection charge is the same kind of line from the same catalogue,
        # so it is refused at the same moment, by name, with the code.
        raise BillingRuleError(
            f"charge code {code!r} has no GL account, so the connection charge on account "
            f"{data.account_no}'s first bill could never be issued (BR-BIL-010: charge "
            "codes carry their own GL). Refused at draft rather than at issue, so no bill "
            "number is spent on a draft that cannot become a bill.",
            br_ref="BR-BIL-010",
            message_key="billing.oneTime.err.chargeCodeNoGl",
            params={"code": code},
        )
    return OneTimeLines(
        lines=(
            rating_seam.RatedLine(
                kind="fee",
                description=charge["name"] or charge["code"],
                amount=charge["amount"],
                taxable=False,  # B4.2 — a fee is never taxed, whatever a flag says
                # WHICH CODE IT IS (DEF-714, 2026-08-25). `charge_by_code`
                # already returned the id and nothing carried it, so this
                # connection charge reached issue anonymous and BR-BIL-010
                # refused the whole first bill for want of it — the same
                # failure DEF-181 fixed for the deposit line beside it, in the
                # one case where the fee genuinely IS a charge code.
                charge_id=charge["id"],
            ),
        )
    )


#: `CR-171-BRC10` P1.14 — customers' published read of a move-in's recorded
#: fee lines (`apps.customers.move_fees.first_bill_fee_lines`).
MOVE_IN_FEES_READ = "first_bill_fee_lines"
MOVE_IN_FEES_KIND = "move_fees"


def move_in_fee_lines(data: AccountBillingData) -> OneTimeLines:
    """🔒 `CR-171-BRC10` P1.14 — the FEES the move-in that opened this account
    recorded on its Fees table (images 41, 43, 26), as first-bill lines.

    HUMAN-REVIEW-PENDING — AI-authored 2026-10-05 (lane MVI-MONEY); row in
    `12-governance/09-human-review-ledger.md` (*"CR-171 MOVE-IN MONEY"*).

    **WHY.** Decision log 2026-10-05 *"MOVE-IN REDESIGN P0"* J4/J5: every fee
    row a clerk quotes at the counter lands on the first bill as a one-time
    line, and money taken today is a PAYMENT the bill reads (a prepay credit,
    applied at issue by `payments_seam.apply_credit_at_issue`; a deposit-purpose
    payment satisfies the deposit line, BR-PAY-012). Worked: DEPOSIT $150.00 +
    CONNECT $25.00 + RUSH $40.00 = $215.00 of one-time lines; $100.00 paid
    today → $115.00 still to pay.

    **WHAT IT DOES NOT DO.**
      * **The deposit is not read from here.** `deposit_line_for` prices it
        from the plan minus what was paid, and a second source for one figure
        is `DEF-154`'s shape. Customers serves FEE lines only.
      * **No tax.** `OQ-BIL-12788` CLOSED (a), PO 2026-10-05: *"a (recommended)
        $25.00 (never taxed at move-in)"*. Each line is kind `fee` — outside
        `TAX_BASE_KINDS` structurally (B4.2) — and `taxable=False`.
      * **No price is re-read.** The amount is the one the move recorded,
        priced from its charge code ON THE DAY the customer was quoted it
        (BR-BIL-007). Re-pricing today would bill a figure nobody was shown.

    **WHY IT REPLACES THE DEFAULT CONNECTION CHARGE.** The Fees table IS the
    list of this move-in's fees: the plan's one-time codes are its locked rows,
    so a plan naming `CONN` already put it there. Adding the one-time tab's
    default `CONN` beside the table would bill the connection twice, or bill
    one the plan never named.

    **REFUSED BY NAME, NEVER GUESSED:** a line in another currency (hard rule
    2), and a line whose code has no GL account (BR-BIL-010 would refuse it at
    issue; refused at draft, like `connection_charge_line_for`). An unwired
    customers read answers no lines — the account then bills as every account
    did before the Fees table existed.
    """
    read = gather._resolve("customers", MOVE_IN_FEES_READ, kind=MOVE_IN_FEES_KIND)
    if read is None:
        return OneTimeLines()
    rows = read(data.account_id) or []
    gl_for = _rating_read("gl_account_id_for_charge")
    lines: list[rating_seam.RatedLine] = []
    for row in rows:
        currency = row.get("currency") or data.currency
        if currency != data.currency:
            raise BillingRuleError(
                f"the move-in fee {row.get('code')!r} on account {data.account_no} is in "
                f"{currency} and this bill is in {data.currency}. There is no lawful addition "
                "(CLAUDE.md rule 2).",
                br_ref="BR-BIL-012",
            )
        charge_id = row.get("charge_id")
        if not charge_id or gl_for is None or not gl_for(charge_id):
            raise BillingRuleError(
                f"charge code {row.get('code')!r} has no GL account, so the move-in fee on "
                f"account {data.account_no}'s first bill could never be issued (BR-BIL-010).",
                br_ref="BR-BIL-010",
                message_key="billing.oneTime.err.chargeCodeNoGl",
                params={"code": row.get("code")},
            )
        lines.append(
            rating_seam.RatedLine(
                kind="fee",
                description=row.get("description") or row.get("code"),
                amount=Decimal(str(row["amount"])),
                taxable=False,  # OQ-BIL-12788 (a) and B4.2 — and the KIND guarantees it
                charge_id=charge_id,
            )
        )
    return OneTimeLines(lines=tuple(lines))


def refuse_without_a_minimum(data: AccountBillingData) -> None:
    """BR-BIL-062 — the no-prior-read first bill, refused for want of its INPUT.

    The RULE is confirmed and is stated here so an implementer reads it where
    they need it: no prior read ⇒ the plan's minimum for the account's consumer
    category, prorated on calendar days, **no usage line**, and it is **not** a
    missing-read exception (the account is never listed under Missing reads and
    no estimated read is created for it).

    What refuses is the arithmetic, because the minimum cannot reach the engine
    — see `FIRST_BILL_UNAVAILABLE`. **This is not an open question and is
    deliberately not stubbed on one:** OQ-102 was CLOSED by the PO on
    2026-08-11 and BR-BIL-062 is its answer. Raising `NotImplementedError("OQ-…")`
    here would file a question that has been answered, which is worse than a
    refusal because it reads as *nobody has decided* when somebody has.

    **"NO PRIOR READ" MEANS NO MEASURED CONSUMPTION, not an empty list.** Stage
    1 emits a `ServiceReading` for every service on the plan and marks the ones
    it could not measure (`consumption=None`, `absent_reason`), so a new
    account's gather is FULL of readings that measure nothing. Testing
    `data.readings` for emptiness would let a move-in with no meter history
    price as an ordinary bill with zero usage — which is BR-BIL-062's case
    arriving as a $0.00 usage line instead of the plan minimum.
    """
    measured = [
        reading for reading in data.readings if getattr(reading, "consumption", None) is not None
    ]
    if measured:
        return
    raise BillingRuleError(
        f"account {data.account_no} has no prior read, so its first bill prices at the "
        "plan's MINIMUM for its consumer category, prorated on calendar days, with no "
        "usage line (BR-BIL-062, PO 2026-08-11 closing OQ-102). That minimum cannot be "
        "computed today: neither `plans.minimum_bill_amount` nor "
        "`plan_services.minimum_amount` travels on the rating seam, so there is no figure "
        "to prorate and inventing a floor would put a number on a customer's first bill "
        "that no rule produced. The rule is CONFIRMED and the INPUT is missing — this is "
        "not an open question and nothing here chooses a value.",
        br_ref="BR-BIL-062",
    )


def prepare_first_bill(
    *,
    account_id: Any,
    moved_in_on: date,
    period_end: date,
    cycle_days: int,
    period_start: date | None = None,
    scope_services: tuple[str, ...] | None = None,
    keyed_reads: Any = None,
    cycle_days_for: Any = None,
) -> AccountBillingData:
    """Gather the OCCUPIED window — from the move-in day. Writes nothing.

    **THE WINDOW IS THE WHOLE OF THIS FUNCTION'S CONTRIBUTION TO B4.3.** The
    period runs from the MOVE-IN DAY (the incoming customer pays it — BR-CUS-056
    gives the move day to the OUTGOING account and starts the incoming one the
    day after, from the same reading, so `moved_in_on` here is already that next
    day) to the period end, inclusive on both ends. `cycle_days` is the CYCLE's
    length and is required rather than defaulted, because defaulting it to the
    occupied window's length would make every proration factor 1 and charge a
    full month's base for twenty days — right-looking and wrong.

    Worked, WE-6: move-in **12 July**, period end **31 July**, cycle **31** days
    → **20/31**, which is the factor every figure in that fixture hangs off.

    `period_start` is accepted so a caller may record a different window start,
    and it DEFAULTS TO THE MOVE-IN DAY — which is what makes the proration work
    at all: `gather_account` derives `service_days` from the period it is given,
    so the occupied window IS the period and the cycle length is the separate
    denominator. WE-6 uses exactly that: period 12–31 July (20 days) against a
    31-day cycle. A caller passing the CYCLE's start here would get 31/31 and no
    proration, which is why the default is the move-in day and not the cycle's.
    """
    if moved_in_on > period_end:
        raise BillingRuleError(
            f"the move-in date {moved_in_on} is after the period end {period_end}, so "
            "there are no occupied days in this period to bill. A first bill covers the "
            "days the customer held the service.",
            br_ref="BR-BIL-012",
        )
    if cycle_days <= 0:
        raise BillingRuleError(
            f"the cycle length {cycle_days} is not a positive number of days, and every "
            "B4.3 proration divides by it. Refused rather than defaulted: a denominator "
            "guessed here charges a full month for a partial one.",
            br_ref="BR-BIL-012",
        )
    scope = single.billable_account(account_id)
    window_start = period_start or moved_in_on
    # `DEF-BIL-8563` — a reading dated exactly the move-in day is the START
    # reading, so the readings window opens the day after it. J74 case 3:
    # Unit C's move-in reads (W-10442C 479.8 on 09/12) were taken as the
    # CLOSING reading of a 09/12 first bill, which then priced nothing and
    # carried no deposit or connection charge. The move-in day is still billed.
    reads_from = first_reading_day(moved_in_on) if window_start == moved_in_on else None
    data = single.gather_single(
        scope,
        period_start=window_start,
        period_end=period_end,
        service_date=period_end,
        cycle_days=cycle_days,
        scope_services=scope_services,
        # `DEF-BIL-8300` — the preview's provisional step-2 values; None on the draft.
        keyed_reads=keyed_reads,
        reads_from=reads_from,
    )
    # ── `DEF-BIL-8749` (CR-156-BRC10) · A CHARGE-CODE PRICE CHANGE CUTS IT ───
    # Each part divides by `cycle_days_for(part_start, part_end)` — the One-time
    # tab passes the account's cycle on the part's last day (a stated figure
    # still wins); a caller passing none keeps `cycle_days` for every part. The
    # deposit and connection charge ride `fees`, which the split carries once.
    return single.with_price_split(
        data,
        scope,
        period_start=window_start,
        period_end=period_end,
        cycle_days=cycle_days,
        cycle_days_for=cycle_days_for or (lambda _start, _end: cycle_days),
        scope_services=scope_services,
        keyed_reads=keyed_reads,
        reads_from=reads_from,
    )


def first_reading_day(moved_in_on: date) -> date:
    """`DEF-BIL-8563` — the first day a first bill's CLOSING reading may fall on.

    The move-in day's own reading opens the window (it is the register the
    customer took the service on), so a closing reading is one dated after it.
    One definition, read by the engine and by the preview's reading rows."""
    return moved_in_on + timedelta(days=1)


def first_bill_data(
    data: AccountBillingData,
    *,
    moved_in_on: date,
    account_type_id: Any,
    connection_charge_code: str | None = DEFAULT_CONNECTION_CHARGE_CODE,
) -> AccountBillingData:
    """Everything `calculate_first_bill` does BEFORE pricing, and **no write**.

    ⚠ **EXTRACTED SO THAT A SECOND FIRST-BILL SHAPE CANNOT EXIST** (`CR-108`
    wave 1, the one-time tab's step 3). It is `runs.price_account`'s own reason,
    one layer up: the One-time tab has to show a clerk the LINES a first bill
    would carry before anything is drafted, and the deposit line and the
    connection charge are what make a first bill different from an interim one.
    A preview that rebuilt those two lines would be a second implementation of
    BR-BIL-012 sitting beside this one, and the first time they disagreed the
    customer would be shown a bill they did not get.

    So the split is exactly where `price_account`'s is: this function is the
    pure half — the TC-6 derivation, BR-BIL-062's minimum refusal and the two
    one-time lines — and `calculate_first_bill` is this plus stage 6. Preview
    calls `runs.price_account(first_bill_data(…))`; the draft calls
    `runs.calculate_account(first_bill_data(…))`. One set of lines, by
    construction rather than by assertion.

    **DO NOT INLINE IT BACK.**
    """
    if not is_first_bill(
        moved_in_on=moved_in_on, period_start=data.period_start, period_end=data.period_end
    ):
        raise BillingRuleError(
            f"account {data.account_no} did not move in during {data.period_start} → "
            f"{data.period_end} (move-in {moved_in_on}), so this is not a first bill. "
            "`bill_type` is DERIVED from the move-in date and is never supplied by a "
            "caller (US-BIL-010 TC-6): it decides whether a deposit and a connection "
            "charge exist on somebody's bill.",
            br_ref="BR-BIL-012",
        )
    refuse_without_a_minimum(data)

    one_timers: list[rating_seam.RatedLine] = []
    deposit = deposit_line_for(data, account_type_id=account_type_id)
    one_timers.extend(deposit.lines)
    # `CR-171-BRC10` P1.14 — THE FEES THE MOVE-IN RECORDED REPLACE THE DEFAULT
    # CONNECTION CHARGE. See `move_in_fee_lines`. An account no move-in fee
    # table opened (every account before that CR) reads none, and its first
    # bill is exactly what it always was.
    recorded = move_in_fee_lines(data)
    if recorded.lines:
        one_timers.extend(recorded.lines)
    elif connection_charge_code:
        one_timers.extend(connection_charge_line_for(data, code=connection_charge_code).lines)

    from dataclasses import replace

    return replace(data, fees=tuple(data.fees) + tuple(one_timers))


def calculate_first_bill(
    data: AccountBillingData,
    *,
    bill_run: models.BillRun,
    moved_in_on: date,
    account_type_id: Any,
    connection_charge_code: str | None = DEFAULT_CONNECTION_CHARGE_CODE,
    service_date: date | None = None,
) -> models.Invoice:
    """Stages 1 → 6 for the occupied window, typed `first`, with both one-timers.

    The SAME `runs.calculate_account` a cycle run uses — a first bill is priced
    by the same engine on the same signed rules, and the only things that make
    it first are the window and the two extra lines.

    THE TYPE IS DERIVED (TC-6): the move-in date must fall inside the period
    being billed, and a caller asking for a first bill on an account that did not
    move in is refused by name rather than getting one. That derivation and both
    one-time lines now live in `first_bill_data`, which the One-time tab's
    preview calls too — see its docstring for why the split is where it is.

    The one-time lines are appended to `data.fees`, which is where the engine
    takes bill-level charges from (the shape GT-10 is written in) — so they are
    added ONCE, after the services and after the tax pass, and B4.2 keeps them
    structurally out of the tax base.
    """
    with_one_timers = first_bill_data(
        data,
        moved_in_on=moved_in_on,
        account_type_id=account_type_id,
        connection_charge_code=connection_charge_code,
    )
    return runs.calculate_account(
        with_one_timers,
        bill_run=bill_run,
        service_date=service_date or with_one_timers.period_end,
        bill_type="first",
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-010@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md WE-6/WE-16)
# generated: 2026-08-15 by Eng-Lead (US-BIL-010 lane — the first bill and the
#         payments lane's third unwired call site, BR-PAY-012's deposit read)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S31 single-account mode is US-BIL-012's route) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_010_first_bill.py · three mutations
#         proved RED (the derived bill_type, the already-paid subtraction, and
#         the None-is-not-zero refusal on the deposit read)
# exceptions: (1) [CLOSED 2026-09-01, DEF-2791] "NO GLOB IN human_owned.txt
#         MATCHES THIS FILE — reported for the PO batch" was true when written
#         and is false now: the glob is there and G7 checks this file. Kept as
#         history, per the module docstring's dated correction.
#         (2) BR-BIL-062's no-prior-read minimum REFUSES for want
#         of an input the rating seam does not carry; the rule is CONFIRMED, the
#         question is CLOSED, and nothing is stubbed on an OQ. (3) Deposit
#         INTEREST is not a first-bill line (BR-CUS-057 accrues it from receipt
#         and BR-BIL-013 settles it at closure). Both are in
#         FIRST_BILL_UNAVAILABLE rather than in prose only.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
