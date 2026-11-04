# ── Trace ──────────────────────────────────────────────
# Defect:   **DEF-708 (high)** — a cut customer can be reconnected **$75.00
#           short**. The reconnection fee is recorded on the disconnect case
#           and POSTS NOWHERE, so the gate that requires it has nothing to
#           test: the utility does the work and never collects.
# Rule:     **PO ruling 2026-08-27**, verbatim: *"A customer can be reconnected
#           $75 short - Make the fee a real charge — It becomes a line that can
#           be billed and paid, so the gate has something to check."*
# Rules:    BR-CUS-104 (PO 2026-08-25, closing OQ-381 — the reconnection fee
#           lands AT THE CUT: `A-11340` must clear **$8,315.00**, not
#           $8,240.00) · BR-BIL-007 (*"NSF/reconnect fees are tenant-configured
#           charge codes, never hardcoded"*) · BR-BIL-010 (a charge code
#           carries its own GL account) · BR-BIL-005 (idempotency) ·
#           BR-BIL-063 (a draft is numbered when it is drafted) · BR-BIL-024
#           (the due date is derived at issue from the run's terms) ·
#           CLAUDE.md rule 2 (money 4dp) · rule 4 (immutability) · rule 5 (only
#           the posting service writes journal lines) · rule 7 (audit)
# Tests:    06-backend/tests/test_def_708_the_fee_is_a_real_charge.py
# Impacts:  apps/billing/models.BILL_TYPES (gains `fee`) ·
#           apps/billing/services (publishes `raise_charge_fee`) ·
#           apps/customers/disconnects.commit_cut (the first caller)
# ───────────────────────────────────────────────────────
"""A tenant charge code, billed as a real receivable. DEF-708's whole fix.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-08-27 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*). This is a
🔒 money path: it creates a receivable against a named customer. A row in
`12-governance/09-human-review-ledger.md` states in plain English what it does
and with which figure. Not RATIFIED without a recorded human sign-off.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS, AND WHY IT IS IN **BILLING** AND NOT IN **CUSTOMERS**
════════════════════════════════════════════════════════════════════════════
`apps/customers/disconnects.py` has carried this sentence since 2026-08-25:

    ⚠ NOTHING POSTS THE FEE TO THE BALANCE, AND THE RECORD SAYS SO. … Measured
    2026-08-25: `apps.billing.services.__all__` publishes `assess_late_fee` and
    **no ad-hoc charge service**, so there is no owning-module service to hand
    this to.

That is the gap, and it is billing's. Customers may not write a financial table
(BR-CUS-037) and only the ledger posting service writes journal lines
(CLAUDE.md rule 5), so the fee could be QUOTED and never CHARGED.

⚠ **AND THE OBVIOUS ONE-LINE FIX IN CUSTOMERS DEADLOCKS THE PRODUCT.** Folding
`disconnect_cases.reconnection_fee_amount` into `mark_reconnecting`'s balance
comparison makes the gate *work* and leaves the money *uncollected* — the wrong
half — and worse: paying takes AR to zero while the cached fee never clears, so
**no cut customer could ever be reconnected again.** The PO's ruling names the
lawful shape instead — *"It becomes a line that can be billed and paid, so the
gate has something to check"* — and once the fee is a real receivable
`mark_reconnecting` needs no change at all, because AR already contains it.

════════════════════════════════════════════════════════════════════════════
WHAT A FEE BILL IS, AND THE THREE THINGS IT IS NOT
════════════════════════════════════════════════════════════════════════════
A fee bill is an invoice whose entire content is charge-code lines. It carries
the new `fee` bill type (B2 r10 #12), so a document kept for seven years says
what it is rather than being mislabelled `cycle`.

**IT IS NOT PRICED, AND THAT IS DELIBERATE.** It never touches
`rating.engine.price_bill`, which refuses a bill with no services by name — *"A
plan that resolves to nothing priceable is an exception for a human
(BR-BIL-015), never a bill"* — and that refusal is a real protection over the
metered path that must not be weakened to let a fee through. A charge code is
not priced: the tenant's own row carries the amount (BR-BIL-007), there is no
tariff, no quantity and no proration, and **B4 contains no arithmetic that
applies to it**. So no ❄️ FROZEN figure is touched and golden-verify stays
33/33.

**IT IS TAXED WHEN ITS CHARGE CODE IS MARKED TAXABLE — ❄️ B4.2 RE-SIGNED
2026-09-30.** ⚠ This paragraph read *"IT IS NOT TAXED HERE"* until 2026-09-30:
`charges.taxable_default` was not read, because a fee bill never entered the
engine's single tax pass, and `OQ-812` asked whether it should. The PO ruled
option (b) and signed the frozen rule's extension in the same breath — asked
*"Re-sign the frozen tax rule so a Fee bill is taxed when its charge code is
marked taxable?"*, verbatim *"Yes, re-sign."*, shown **RECON $75.00 marked
taxable at 8.25% → $81.19** (decision log *"ONE-TIME BILL: SIX ANSWERS"* (1);
the ❄️ ADDENDUM of 2026-09-30 in `04-docs/02-decisions/04-money-math-rules.md`).

So `price_charge_fee` reads the flag off the tenant's row and, when it is set,
hands the line to `rating_seam.price_fee_bill` — the engine's OWN finalize →
compute-tax → assemble stages, run ONCE over the bill (BR-RAT-062 / GT-17 ❄️),
never a percent multiplied here. The taxes are the account's PLAN taxes,
resolved exactly as an ordinary bill resolves them but with NO service list,
so a tax scoped to a service (a franchise fee on *electric only*) fails closed
and does not reach a fee. Exemption is account-level and wins (BR-RAT-006).

⚠ **WHAT IT DOES NOT COVER, STATED:** (1) a non-taxable code is byte-identical
to every fee bill raised before the ruling — no engine call, no extra read;
(2) `charge_code_line`'s OTHER callers (`penalty`, `first_bill`, `backbill`, the
connection QUOTE via `price_quote_bill` / `price_quote_preview`) still get
`taxable=False`: the ruling was about a Fee bill, a fee RIDING an ordinary bill
is still kept out of the base by KIND (B4.2 unchanged), and New Connect is
halted by the PO — a quote bill's tax is taken up when that work resumes;
(3) only PERCENT taxes are priced on a fee bill (see the engine's
`price_fee_bill` for why a flat or per-unit rule is not).

**IT IS NOT A SECOND WRITER OF `invoice_lines`.** It builds the same
`RatedLine` shape the engine emits and hands it to `stages.assemble_document`,
which is the one function in this product that writes a bill. What it supplies
is a priced RESULT, not a second implementation of one.

════════════════════════════════════════════════════════════════════════════
IT DOES NOT ISSUE, AND THE CALLER MUST
════════════════════════════════════════════════════════════════════════════
`raise_charge_fee` returns a DRAFT. Issue is the act that stamps the GL
accounts, freezes the document and posts it (rule 5), and it is a separate call
so that a caller inside its own transaction — `commit_cut` is exactly that —
can decide whether the posting rides with it. `issue_charge_fee` is the pair,
and it is a thin forwarder to `issue.issue_invoice` rather than a second issue
path, for the reason this module refuses to be a second line writer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone as dt_timezone
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.billing import gather, issue, models, one_time, rating_seam
from apps.billing.contracts import MeasuredUsage, SubscriptionContext
from apps.billing.exceptions import BillingRuleError
from apps.billing.stages.assemble_document import assemble_document
from core import audit
from core import tenancy as core_tenancy
from core.money_fields import AMOUNT_QUANTUM

#: The `invoices.bill_type` this module writes. Named here so the caller never
#: types the string and `models.BILL_TYPES` stays the single vocabulary.
BILL_TYPE_FEE = "fee"
#: DEF-RAT-8753 — `rating.services.AMOUNT_RULE_PER_CASE`: a code whose amount is
#: entered when the fee is used (CR-010 A2). The only code a clerk's figure prices.
PER_CASE = "per_case"


@dataclass(frozen=True)
class _PricedFee:
    """A priced RESULT in the shape `assemble_document` reads structurally.

    `assemble_document` takes `priced` by `getattr` and never imports rating's
    class — *"the two modules must not depend on each other's classes"* — so
    this is the same duck the engine presents. For a fee on a code NOT marked
    taxable no tax pass runs, and `taxable_subtotal` is **zero, not the
    total**: that fee is not in the tax base, and a subtotal that claimed
    otherwise would be a taxable base on the document with no tax line against
    it. For a code marked taxable (❄️ B4.2 re-sign 2026-09-30) all three money
    fields are copied off the engine's `price_fee_bill` result, never computed
    here.
    """

    currency: str
    lines: tuple[rating_seam.RatedLine, ...]
    total: Decimal
    tax_total: Decimal = Decimal("0")
    taxable_subtotal: Decimal = Decimal("0")


#: **WHAT A COUNT IS A COUNT OF** — the drawing's BASIS column turned into the
#: noun that rides on the bill line beside the number (`CLAUDE.md` hard rule 3).
#:
#: `02 Accounts Menu Blueprint.pdf` p090 draws three bases and no others: *per
#: unit* · *per meter* · *per premise*. A quantity of `6` is meaningless on a
#: document; `6 units` is a figure the developer can check against the building
#: he is putting up, which is the whole of rule 3's reason.
#:
#: ⚠ **A MAP AND NOT A `.removeprefix("per ")`, DELIBERATELY.** Rule 3 is *"never
#: assume"*, and string surgery on a caller's text would mint a unit out of
#: whatever arrived — a typo becomes a unit nobody defined and it lands on an
#: immutable document (hard rule 4). An unknown basis REFUSES below.
BASIS_UNITS: dict[str, str] = {
    "per unit": "unit",
    "per meter": "meter",
    "per premise": "premise",
}


def charge_code_line(
    code: str,
    *,
    description: str | None = None,
    quantity: Decimal | None = None,
    unit: str | None = None,
    taxable_from_code: bool = False,
    entered_amount: Decimal | None = None,
    on_date: date | None = None,
    customer_class: str | None = None,
) -> rating_seam.RatedLine:
    """One `RatedLine` from the tenant's OWN charge code — or a refusal by name.

    ⚠ **`on_date` / `customer_class` ADDED 2026-10-01 (`DEF-RAT-8826`).** A
    charge code's price is DATED (`CR-156-BRC10`): `RE-READ` repriced $20.00 →
    $21.00 from 11/01 must bill $21.00 on a fee bill dated 11/15 and $20.00 on
    one dated 10/15 — *"a bill passes its own dates and never today"*
    (`charge_prices.price_on_date`). Without them `charge_by_code` answers the
    tenant's TODAY, which billed the 11/15 fee at $20.00. The class is the
    account's, so a code priced by customer class answers that class's row.
    `None` for both keeps every older caller's meaning (today, every class).

    ⚠ **`entered_amount` ADDED 2026-10-01 (`DEF-RAT-8753`) AND IT IS THE ONE
    PLACE A CLERK'S FIGURE REACHES A BILL — FOR ONE KIND OF CODE ONLY.** A code
    whose `amount_rule` is `per_case` states no price: CR-010 A2 (PO
    2026-08-17) priced TAP, IMPACT, DAMAGE and BULK-WATER at *"actual cost,
    entered per case"*, and the PO-approved charge-code mock-up draws it as
    *"Amount is entered when the fee is used"* (images 41, 64, 70). So for that
    code the amount IS the clerk's, typed when the fee is raised. **BR-BIL-020
    still holds for every other code, structurally:** an `entered_amount`
    beside a code that states its own price is REFUSED by name, and a
    `per_case` code with no `entered_amount` is refused rather than charged
    $0.00. The figure is money: Decimal, positive, at most four places (hard
    rule 2), carried as typed and never re-scaled.

    ⚠ **`taxable_from_code` ADDED 2026-09-30 (❄️ B4.2 re-sign, `OQ-812`).**
    `False` — the default, and every caller before that date — keeps the line
    `taxable=False` exactly as it always was. `True` carries the tenant's own
    `charges.taxable_default` onto the line, and ONLY `price_charge_fee` passes
    it, because the re-sign is about a FEE BILL: a penalty, a connection
    charge or a quote line built here rides a bill whose tax base is still
    usage + base by KIND (B4.2, unchanged), so flagging those would change no
    figure and would say something on the line that is not true of it.

    ⚠ **`quantity` ADDED 2026-09-16 (`CR-109` — the New Connect quote) AND IT
    IS NOT A WAY TO TYPE MONEY.** `None` is the historic behaviour and every
    existing caller keeps it: one line, the code's own amount, no quantity on
    the document. A COUNT given here multiplies the code's amount by it —
    `$325.0000 × 6 = $1,950.0000` — and the count is the only new input.

    **WHY THAT DOES NOT WEAKEN BR-BIL-020.** The rule's own words are *"lines
    come ONLY from rules and charge codes — free-typed amounts never exist on
    any bill"*. The UNIT PRICE is still the tenant's row and there is still no
    parameter anywhere in this module that a caller could put money in. What a
    count adds is *how many of them*, and the blueprint is explicit that a clerk
    does not type that either (`02 Accounts Menu Blueprint.pdf` p090, in red):
    *"Every quantity is counted from the services grid, not typed. Six units,
    twenty service points, one premise — change a tick on step 4 and these move
    with it."* So the count is DERIVED from the build and the price is the
    catalogue's; neither is anybody's opinion.

    **NO ❄️ FROZEN FIGURE MOVES.** B4 contains no arithmetic that applies to a
    charge code (see the module docstring), so `count × flat price` touches
    nothing B4/B5 signed. The shape is not novel either — CLAUDE.md rules fire
    service the same way: *"the size class picks the price and the COUNT
    multiplies it"*, one 6" line and two 2" lines being `$60.00 + 2 × $12.00`.

    **ROUNDED EXACTLY ONCE, HERE** (CLAUDE.md rule 2, and `DEF-088`, which
    removed a second rounding path once already). The product is quantised to
    four decimals at the moment it is formed and never again: the caller
    receives a finished figure, `assemble_document` stores it, and display
    rounds to two. A caller that multiplied first and handed in a product would
    be the second rounding path this comment exists to prevent, which is why
    there is no `amount` parameter for it to arrive through.

    **BR-BIL-007: the amount comes from the tenant's row, never from a literal.**
    `CC-RECON` is seeded at `$75.00` and a utility is entitled to charge $95.00;
    a constant here would bill every tenant the demo tenant's price.

    **FOUR STATES REFUSE, AND NONE OF THEM DEFAULTS**, because a fee charged at
    a guessed amount lands on an immutable document (rule 4):

      * rating publishes no `charge_by_code` — the seam is not there;
      * the tenant has no code by that name, retired it (IS-1 — a retired
        charge is not chargeable), or it is another tenant's (HR-1);
      * the code carries a `percent` or `percent_with_minimum` rule, so
        `charge_by_code` returns `amount=None` on purpose: such a rule needs a
        BASIS that a standalone fee has none of;
      * the code has no GL account, which would refuse at issue anyway — caught
        here so the refusal names the tenant's screen instead of burning an
        invoice number on a draft that can never be issued.

    `taxable` — see `taxable_from_code` above and the module docstring.
    """
    read_charge = gather._resolve("rating", "charge_by_code")
    if read_charge is None:
        raise BillingRuleError(
            "apps.rating.selectors.charge_by_code is not published, so a charge-code fee "
            "cannot be priced or booked (BR-BIL-007 / BR-BIL-010). Nothing here falls "
            "back to a literal amount: the fee a utility charges is theirs to set.",
            br_ref="BR-BIL-007",
        )
    charge = (
        read_charge(code, on_date, customer_class)
        if on_date is not None or customer_class is not None
        else read_charge(code)
    )
    if charge is None:
        raise BillingRuleError(
            f"charge code {code!r} is not a live charge code of this tenant, so no fee can "
            "be raised against it (BR-BIL-007). An unknown code, a deactivated one (IS-1) "
            "and another tenant's are one answer. A human creates or reactivates it on S13 "
            "(Taxes & fees -> charge codes).",
            br_ref="BR-BIL-007",
        )
    amount = charge.get("amount")
    # ── DEF-RAT-8753 · `per_case` — THE AMOUNT IS ENTERED WHEN THE FEE IS USED ──
    per_case = charge.get("amount_rule") == PER_CASE
    if entered_amount is not None and not per_case:
        raise BillingRuleError(
            f"charge code {code!r} states its own price, so no amount may be typed for it "
            "(BR-BIL-020 — free-typed amounts never exist on any bill). Only a code priced "
            "'entered when used' takes the clerk's figure.",
            br_ref="BR-BIL-020",
        )
    if per_case:
        if entered_amount is None:
            raise BillingRuleError(
                f"charge code {code!r} is priced 'entered when used' and no amount was "
                "entered, so nothing can be charged (CR-010 A2). Nothing here charges "
                "$0.00 in its place: the clerk enters the amount for this case.",
                br_ref="BR-BIL-007",
            )
        figure = Decimal(str(entered_amount))
        if figure <= 0 or -figure.as_tuple().exponent > 4:
            raise BillingRuleError(
                f"charge code {code!r} was entered as {figure}; an entered amount is a "
                "positive figure of at most four decimal places (CLAUDE.md hard rule 2). A "
                "credit is a credit note, never a fee.",
                br_ref="BR-BIL-007",
            )
        if quantity is not None:
            raise BillingRuleError(
                f"charge code {code!r} is priced 'entered when used'; a count cannot "
                "multiply a figure the clerk typed for the whole case.",
                br_ref="BR-BIL-020",
            )
        amount = figure
    if amount is None:
        raise BillingRuleError(
            f"charge code {code!r} is priced as {charge.get('amount_rule')!r}, which needs a "
            "BASIS to compute against, and a standalone fee has none. Only a FLAT charge "
            "code can be raised on its own; nothing here invents the basis. A human either "
            "gives the code a flat amount on S13 or the fee is charged on a bill that "
            "carries the basis.",
            br_ref="BR-BIL-007",
        )
    if not charge.get("gl_account_id"):
        raise BillingRuleError(
            f"charge code {code!r} has no GL account, so a fee raised on it could never be "
            "issued (BR-BIL-010: *charge codes carry their own GL*). Refused HERE rather "
            "than at issue, so the message names the screen that fixes it and no invoice "
            "number is spent on a draft that cannot become a bill. A human points the code "
            "at an account on S13 (Taxes & fees -> charge codes -> GL account).",
            br_ref="BR-BIL-010",
        )
    unit_price = Decimal(str(amount))
    taxable = bool(charge.get("taxable_default")) if taxable_from_code else False
    if per_case:
        # ⚠ The figure on a per_case line is what the clerk entered — never a
        # count of anything, so a quantity beside it is refused above.
        return rating_seam.RatedLine(
            kind="fee",
            description=description or charge.get("name") or code,
            amount=unit_price,
            taxable=taxable,
            charge_id=charge["id"],
        )
    if quantity is None:
        # The historic single line: the tenant's stored figure at 4dp, carried,
        # never re-scaled here (CLAUDE.md rule 2). `quantity`/`unit_price` stay
        # None so a one-off fee's document says nothing it does not mean — a
        # `1` in a quantity column is a claim that something was counted.
        return rating_seam.RatedLine(
            kind="fee",
            description=description or charge.get("name") or code,
            amount=unit_price,
            taxable=taxable,
            # BR-BIL-010 / DEF-714 — WHICH code this line came from. Without it
            # `issue._gl_account_for` refuses the line by name and the bill dies
            # at release, which is the shape DEF-714 was.
            charge_id=charge["id"],
        )
    count = Decimal(str(quantity))
    if not unit:
        # ⚠ **`DEF-BIL-5458` — THIS REFUSAL REPLACES ONE THAT FIRED TOO LATE.**
        # A counted line used to reach `assemble_document`, which correctly
        # refused it under CLAUDE.md rule 3 — *"a fee line carries a quantity
        # with no unit"* — by which point an invoice NUMBER had been spent on a
        # draft that could never be issued. Refused here for the same reason the
        # missing-GL check above is: the message names what to fix and no
        # document is burned. Every counted quote line the product could raise
        # died this way until 2026-09-16, so nothing about the count was ever
        # observed on a real invoice.
        raise BillingRuleError(
            f"charge code {code!r} was given a count of {count} and no unit to count in "
            "(CLAUDE.md rule 3 — a quantity always travels with its unit, and is never "
            f"assumed). A bill line reading {count} is a number the customer cannot "
            f"check; {count} units, meters or premises is a figure they can hold against "
            "the building. The quote's BASIS carries it — pass the noun from "
            "`BASIS_UNITS`.",
            br_ref="BR-BIL-020",
        )
    if count <= 0:
        raise BillingRuleError(
            f"charge code {code!r} was given a quantity of {count}, and a bill line for "
            "nothing — or for less than nothing — is not a line. A count of zero means "
            "the build has none of these, and the lawful answer is to leave the line off "
            "the quote rather than to raise it at $0.00: a line that quietly prices at "
            "nothing is a charge nobody notices was never made. A negative count would be "
            "a credit, and a credit is a credit note (hard rule 4), never a fee.",
            br_ref="BR-BIL-020",
        )
    return rating_seam.RatedLine(
        kind="fee",
        description=description or charge.get("name") or code,
        # ROUNDED ONCE — see the docstring. `AMOUNT_QUANTUM` is four decimals
        # (CLAUDE.md rule 2); display rounds to two and nothing here does.
        amount=(unit_price * count).quantize(AMOUNT_QUANTUM),
        taxable=taxable,
        # All three ride onto `invoice_lines`, so the customer's document shows
        # the arithmetic — `6 units × $325.00` — instead of a total they cannot
        # check. The blueprint draws QTY and UNIT as their own columns.
        quantity=count,
        unit=unit,
        unit_price=unit_price,
        charge_id=charge["id"],
    )


@dataclass(frozen=True)
class PricedFeeBill:
    """A fee bill priced and **not written** — what stage 6 would be handed.

    `account` rides along because a caller showing this to a clerk needs the
    account number and the currency, and re-reading them would be a second
    answer to *who is being charged*.
    """

    account: _AccountFacts
    priced: _PricedFee
    usage: MeasuredUsage

    @property
    def line(self) -> rating_seam.RatedLine:
        """The ONE charge-code line. A fee bill has exactly one by construction.

        Since the ❄️ B4.2 re-sign of 2026-09-30 a taxable code's bill ALSO
        carries one tax line per authority, after it — the engine's `assemble`
        puts the charged lines first — so this is `lines[0]` and never a tax.
        """
        return self.priced.lines[0]


@dataclass(frozen=True)
class QuotedCharge:
    """ONE line of a quote: WHICH code and HOW MANY. **There is no amount here.**

    ⚠ **THE ABSENT MEMBER IS THE ENFORCEMENT, EXACTLY AS IN `OneTimeRequest`.**
    BR-BIL-020 is *"free-typed amounts never exist on any bill"*, and the way
    this module keeps that is not a validation a refactor could delete — it is
    that a caller holding a figure has nowhere to put it. `charge_code` names
    the code and the tenant's own row carries the price (BR-BIL-007);
    `quantity` is a COUNT of things the build contains.

    ⚠ **A QUOTE'S OWN STORED PRICE IS DELIBERATELY NOT AN INPUT, AND THIS IS
    THE ONE JUDGMENT IN THIS FILE THAT COULD HAVE GONE THE OTHER WAY.**
    `service_request_fees` holds a `unit_amount` snapshot beside each line, and
    billing the snapshot would have been one line of code. It is refused
    because that column is a SNAPSHOT: since `DEF-CUS-6416` (2.350.4)
    `customers.service_request_service.add_fee_line` prices each line from the
    tenant's charge code AT THE MOMENT THE FEE IS ADDED and refuses any other
    figure, so `unit_amount` is the catalogue as it stood then — and a bill is
    priced from the catalogue as it stands at commit (BR-BIL-007). The quote's
    COUNT is a fact about the build; the quote's PRICE is an earlier reading of
    the price list. We take the count and re-read the price. (This paragraph
    called the column a caller-typed amount until 2026-09-24 — true when it was
    written, stale since `DEF-CUS-6416`; `DEF-CUS-6461` corrected the words.)

    **THE COST OF THAT IS STATED RATHER THAN HIDDEN, AND IT IS THE CALLER'S TO
    HANDLE:** if the catalogue moved between quoting and committing, the bill
    would differ from the number the customer was shown. Nothing here silently
    picks a side — `commit_connection` compares the two and refuses by name
    with both figures. Whether a quote HOLDS its price for a period is a
    promise only the utility can make, so it is `OQ-BIL-12376` and it is open.

    `basis` (*per unit* · *per meter* · *per premise*) is carried for the
    DESCRIPTION alone. It is not arithmetic: nothing here derives a count from
    it, because the count already arrived counted.

    ════════════════════════════════════════════════════════════════════════
    ⚠ WHAT THIS SHAPE WILL HAVE TO CARRY — TWO PO RULINGS OF 2026-09-16,
    RECORDED HERE AND **NOT BUILT**
    ════════════════════════════════════════════════════════════════════════
    Both landed after this class was written and before any of it was proved,
    and New Connect work was then halted. They are written down because the
    next lane reads the repo and not anybody's memory (hard-won law 10), and
    because the second one crosses a line the blueprint draws explicitly.

    PO, verbatim: *"you will select connection fees, deposites, work order
    fees, based on plan you will devicde how many charges to calculate for this
    premises - charges will be per unit - we will ahve to allow whether
    deposite will be given by owner or it should be charge to person who move
    in in to this units. if it is owner and we charge all, if it is occupant
    then we dont charge"*.

    **1 · THREE CATEGORIES, AND THE PLAN DECIDES HOW MANY.** Connection fees ·
    **deposits** · work order fees, **charged per unit**. `QuotedCharge` can
    already express a per-unit count, so the shape survives — what it does NOT
    have is any notion of a CATEGORY, or of a PLAN deciding the counts. Today
    the counts arrive from the service request's quote; under this ruling they
    would be derived from the premises' plan. That is a different source, not a
    different field.

    **2 · THE DEPOSIT PAYER CHOICE IS A NEW MONEY PATH, NOT A RENAME, AND IT
    MUST NOT BE BUILT AS ONE.** If the OWNER pays, every unit's deposit is
    charged now to the owner's account; if the OCCUPANT pays, **nothing is
    charged at build time** and it is taken at move-in.

    ⚠ **THAT DELIBERATELY CROSSES THE BLUEPRINT'S OWN LINE.** `02 Accounts Menu
    Blueprint.pdf` p090 says: *"A deposit against a quote is not a deposit
    against an account. This money settles one-time charges on a build; it is
    not the security deposit a tenant pays when they move in, and the two never
    meet."* The ruling is about the SECURITY deposit, so the owner option makes
    a BUILD charge a tenant deposit per unit up front — the two meeting, on
    purpose. **A deposit is also not revenue**: it is a liability at `2300`,
    taken and owed back, which is precisely why `chart.CHARGE_CODE_ACCOUNTS_
    NOT_MAPPED` refuses to map `DEPO-R`/`DEPO-C` to a `46xx` fee account, and
    why this class's flat-charge pricing is the WRONG engine for it —
    `BR-RAT-020`/`BR-RAT-023` put deposit amounts on the PLAN's deposit rules
    and supersede a flat deposit charge.
    **And the occupant option is the move-in wizard's EXISTING deposit step
    doing its existing job — it must not be duplicated.**
    """

    charge_code: str
    quantity: Decimal
    description: str | None = None
    basis: str | None = None


@dataclass(frozen=True)
class PricedQuoteBill:
    """A MULTI-LINE fee bill priced and **not written**. `PricedFeeBill`'s twin.

    Separate from `PricedFeeBill` rather than a widening of it, because that
    class promises *"a fee bill has exactly one by construction"* in its own
    `line` property and callers rely on it. Two shapes, two promises, neither
    lying about the other.
    """

    account: _AccountFacts
    priced: _PricedFee
    usage: MeasuredUsage

    @property
    def lines(self) -> tuple[rating_seam.RatedLine, ...]:
        return self.priced.lines

    @property
    def total(self) -> Decimal:
        return self.priced.total


def _unit_for_basis(item: "QuotedCharge") -> str | None:
    """The noun a quoted line's count is counted in, or a refusal by name.

    `None` where the line carries no count at all — an uncounted fee is one
    charge of one thing and says nothing about quantity, which is the historic
    behaviour `charge_code_line` keeps.

    ⚠ **AN UNRECOGNISED BASIS REFUSES AND IS NEVER PASSED THROUGH.** Hard rule 3
    is *"always with an explicit unit; never assume"*, and the cost of assuming
    lands on an immutable document (hard rule 4): a typo'd basis would become a
    unit of measure on an issued invoice, where no UPDATE can reach it. The
    three the blueprint draws are the three that exist, and a fourth is a
    conversation with the Product Owner rather than a string this function
    invents.
    """
    if item.quantity is None:
        return None
    basis = (item.basis or "").strip().lower()
    unit = BASIS_UNITS.get(basis)
    if unit is None:
        raise BillingRuleError(
            f"charge code {item.charge_code!r} is counted {item.quantity} times on a "
            f"basis of {item.basis!r}, which is not one this product counts in "
            f"({', '.join(sorted(BASIS_UNITS))}). CLAUDE.md rule 3 forbids assuming the "
            "unit, and an invented one would land on an issued invoice that no "
            "correction can reach (hard rule 4). A new basis is a ruling, not a string.",
            br_ref="BR-BIL-020",
        )
    return unit


def price_quote_bill(
    *,
    account_id: Any,
    charges: tuple[QuotedCharge, ...] | list[QuotedCharge],
    on_date: date,
    pending_new_connection_owner: bool = False,
) -> PricedQuoteBill:
    """Price a whole quote — N coded lines with counts — and write NOTHING.

    `price_charge_fee`'s reason, N lines wide: the screen shows a clerk the
    lines and the total BEFORE the button that writes, and the figure it shows
    has to be the figure the draft will carry. One reading of BR-BIL-007, not
    two that eventually disagree.

    **IT WRITES NOTHING AND SPENDS NO BILL NUMBER.** No run row, no
    `assemble_document`, no `core.numbering`. Every refusal
    `charge_code_line` has fires here exactly as it fires at draft, and it
    fires on the FIRST bad line rather than pricing around it: a quote with one
    unchargeable code is not a quote that should be three-quarters raised.

    **THE TOTAL IS Σ(already-rounded lines) AND IS NOT ROUNDED AGAIN.** Each
    line was quantised once when it was formed; summing four four-decimal
    figures cannot produce a fifth decimal, so a `quantize` here would be the
    second rounding path `DEF-088` removed. Stated because it looks like an
    omission.
    """
    if not charges:
        raise BillingRuleError(
            "a quote bill was asked for with no lines. An invoice with nothing on it is "
            "not a document a customer can be sent or a regulator can read, and a $0.00 "
            "total would say the build was free rather than that nothing was quoted. A "
            "build with no chargeable line raises no bill at all.",
            br_ref="BR-BIL-020",
        )
    lines = tuple(
        charge_code_line(
            item.charge_code,
            description=item.description,
            quantity=item.quantity,
            # `DEF-BIL-5458` — the BASIS is what the count is counted in, and it
            # is data rather than decoration. `_unit_for_basis` refuses an
            # unrecognised one rather than inventing a noun (hard rule 3).
            unit=_unit_for_basis(item),
        )
        for item in charges
    )
    account = _account_facts(
        account_id, on_date=on_date, pending_new_connection_owner=pending_new_connection_owner
    )
    return PricedQuoteBill(
        account=account,
        priced=_PricedFee(
            currency=account.currency,
            lines=lines,
            total=sum((line.amount for line in lines), Decimal("0")),
        ),
        usage=_fee_usage(account, on_date=on_date),
    )


@dataclass(frozen=True)
class PreviewedQuote:
    """A quote PRICED FOR A SCREEN — no account, no run, no document, no write.

    ⚠ **IT EXISTS BECAUSE A MONEY SCREEN WAS SHOWING NO MONEY (`DEF-CUS-6115`).**
    New Connect step 6 counted quantities correctly, listed the charge code a
    clerk picked, and printed no unit price, no line total and no total — so
    six build variations were committed in the acceptance walk **without the
    clerk ever seeing a figure**, and the commit then raised `7 x $45.00 =
    $315.00`. The engine could always answer; nobody asked it.

    ⚠ **WHY `price_quote_bill` COULD NOT BE CALLED INSTEAD, WHICH IS THE WHOLE
    REASON THIS CLASS EXISTS.** That function takes an `account_id` — it needs
    one for the CURRENCY and for `_fee_usage`'s billing period — and a DRAFT
    build has no account until step 8 writes one (`BR-MET-112`, *nothing is
    written until step 8*). `NewConnectChargesStep.tsx` recorded that as a
    missing DOOR rather than a missing screen and filed `DEF-BIL-5486`. This is
    that door: the same lines, priced the same way, with the two account-shaped
    facts removed.

    ⚠ **THE LINES ARE BUILT BY `charge_code_line`, THE FUNCTION THE COMMIT
    USES, AND THAT IS NOT AN IMPLEMENTATION DETAIL.** A preview that priced by
    a second route would be a screen showing a clerk a figure the commit will
    not raise — `DEF-MET-5428`'s shape on a money path. Every refusal fires
    here exactly as it fires there, on the FIRST bad line — so a code the
    catalogue cannot price is named where it was PICKED as well as where it is
    raised (`DEF-MET-6110` is the COMMIT half, another lane's, the same day).

    **THE TOTAL IS Σ(already-rounded lines) AND IS NOT ROUNDED AGAIN** — the
    identical sentence `price_quote_bill` carries, for the identical reason:
    each line was quantised once when it was formed, and a second `quantize`
    here would be the rounding path `DEF-088` removed.

    **`currency` MAY BE EMPTY AND IS NEVER INVENTED.** It is the TENANT's, read
    through `gather._tenant_currency`; a tenant whose regional settings cannot
    be read gets `""` and the screen says the figure is unlabelled rather than
    stamping a dollar sign on somebody else's money (CLAUDE.md rule 2: money
    travels with its `CHAR(3)` partner).
    """

    lines: tuple[rating_seam.RatedLine, ...]
    total: Decimal
    currency: str


def price_quote_preview(
    *,
    charges: tuple[QuotedCharge, ...] | list[QuotedCharge],
) -> PreviewedQuote:
    """Price N counted quote lines for a SCREEN. Writes nothing, needs no account.

    See `PreviewedQuote` for why this is not `price_quote_bill` with an
    argument removed.

    ⚠ **AN EMPTY LIST IS REFUSED HERE TOO**, and it is the same refusal
    `price_quote_bill` makes, in the same words, for the reason that function
    gives: *"a `$0.00` total would say the build was free rather than that
    nothing was quoted"*. The screen's answer to a build with no charge is a
    BLANK, never a zero — which is already the law on the build record's own
    money tiles — so the caller reports the absence and never calls this with
    nothing.
    """
    if not charges:
        raise BillingRuleError(
            "a quote preview was asked for with no lines. A build with no chargeable "
            "line is not a build that costs $0.00 — it is one that has not been priced, "
            "and a zero on a money screen reads as 'this was free'. The caller states "
            "the absence instead.",
            br_ref="BR-BIL-020",
        )
    lines = tuple(
        charge_code_line(
            item.charge_code,
            description=item.description,
            quantity=item.quantity,
            unit=_unit_for_basis(item),
        )
        for item in charges
    )
    return PreviewedQuote(
        lines=lines,
        total=sum((line.amount for line in lines), Decimal("0")),
        currency=gather._tenant_currency(),
    )


def raise_quote_bill(
    actor: Any,
    *,
    account_id: Any,
    charges: tuple[QuotedCharge, ...] | list[QuotedCharge],
    on_date: date,
    due_days: int,
    pending_new_connection_owner: bool = False,
) -> models.Invoice:
    """DRAFT one `fee` bill of N coded lines against ONE account.

    `pending_new_connection_owner` — `DEF-MET-9217`, 🔒 HUMAN-REVIEW-PENDING:
    ONLY `metering.connection_fees` passes it, so a fee added to a New
    Connection before approval may bill the build's owner account while it is
    held `pending_activation`; see `single._pending_new_connection_scope`.

    `raise_charge_fee` with a list where it has a code, and every sentence of
    that function's docstring applies unchanged: `on_date` is the business
    event's date and never a clock (BR-TEN-043, gate G6); `due_days` is
    REQUIRED and this module does not choose it (CR-029 D8③).

    ⚠⚠ **THE POSTING HALF OF THIS PATH IS NOT PROVEN, AS OF 2026-09-16, AND
    NOTHING MAY CITE IT AS WORKING.** `tests/test_cr109_connection_quote_posts_
    pg.py::test_the_quote_posts_a_balanced_pair` was run against real
    PostgreSQL and **FAILED**, and the run was not diagnosed before New Connect
    work was halted by the Product Owner (*"please dont start any tasks on new
    connection request - we are preparing the details once we have everything
    then we start the job"*). So the balanced pair this function is supposed to
    produce — `DR 1200` against the codes' own revenue accounts — **has never
    been observed.** The pricing half IS proven: `charge_code_line`'s existing
    behaviour is unchanged and `tests/test_cr108_w1_one_time_fee_lines_and_
    books.py` is green at 11 passed.

    **IT IS UNREACHABLE FROM THE PRODUCT, WHICH IS WHY IT IS SAFE TO LEAVE
    HERE.** `metering.connections._post_connection_quote` will not call this
    without `quote_due_days` in the commit payload, and **no caller in the
    product sends that field** — the wizard does not collect it. Every real
    commit therefore takes the *"payment terms not captured"* branch and posts
    nothing, exactly as before. **A lane resuming this work proves the pair
    FIRST** (hard-won law 7) and deletes this banner when it has.

    ⚠ **IDEMPOTENT ON (account, `fee`, on_date) — WHICH IS THE WHOLE BILL, NOT
    THE LINE.** `one_time.create_one_time_run` keys the run on exactly that
    (`idempotency.one_time_run_key`), so re-committing a build raises ONE quote
    bill and the second attempt comes back as `runs.DuplicateRun` naming the
    first, with who ran it and when (BR-BIL-005). That is the protection a
    double-clicked commit needs.

    ⚠ **AND IT IS ALSO A REAL LIMIT, NAMED RATHER THAN WORKED AROUND: ONE
    ACCOUNT CAN TAKE ONE `fee` BILL PER DAY.** A developer committing a SECOND
    build on the same day, against the same owner account, is refused by an
    idempotency key that cannot tell the two builds apart. The key's shape is
    signed and 🔒 (`core/idempotency.one_time_run_key`, HUMAN-REVIEW-PENDING),
    and widening it would move every one-time run in the product, so nothing
    here invents a suffix to dodge it. **`OQ-BIL-12377`** asks whether one
    account may carry two fee bills on one day; the refusal is loud, named and
    carries the first run, so no money is lost either way.
    """
    priced_bill = price_quote_bill(
        account_id=account_id,
        charges=charges,
        on_date=on_date,
        pending_new_connection_owner=pending_new_connection_owner,
    )
    account = priced_bill.account
    tenant_id = core_tenancy.current_tenant_id()

    with transaction.atomic():
        run = one_time.create_one_time_run(
            account_id=account_id,
            bill_type=BILL_TYPE_FEE,
            # A quote is charged ON a day, not OVER a window — `raise_charge_fee`
            # states the reason and it is the same one here.
            period_start=on_date,
            period_end=on_date,
            bill_date=on_date,
            due_days=due_days,
            run_by=actor,
            actor=actor,
            pending_new_connection_owner=pending_new_connection_owner,
        )
        invoice = assemble_document(
            usage=priced_bill.usage,
            priced=priced_bill.priced,
            tenant_id=tenant_id,
            account_id=account.account_id,
            bill_run=run,
            period_start=on_date,
            period_end=on_date,
            service_date=on_date,
            bill_type=BILL_TYPE_FEE,
        )
        # CLAUDE.md rule 7 — figures now exist against a named customer. Every
        # LINE is listed, not just the total: an audit row saying only
        # "$3,030.00" cannot answer which code was charged how many times, and
        # that is the question a dispute asks.
        audit.money_action(
            actor,
            "invoice.drafted",
            "invoice",
            str(invoice.pk),
            before=None,
            after={
                "bill_type": BILL_TYPE_FEE,
                "account_no": account.account_no,
                "currency": account.currency,
                "on_date": on_date.isoformat(),
                "bill_run_id": str(run.pk),
                "total": str(priced_bill.total),
                "lines": [
                    {
                        "charge_code": item.charge_code,
                        "quantity": str(line.quantity),
                        "unit_price": str(line.unit_price),
                        "amount": str(line.amount),
                    }
                    for item, line in zip(charges, priced_bill.lines)
                ],
            },
        )
    return invoice


def raise_and_issue_quote_bill(
    actor: Any,
    *,
    account_id: Any,
    charges: tuple[QuotedCharge, ...] | list[QuotedCharge],
    on_date: date,
    due_days: int,
    issued_at: datetime | None = None,
    pending_new_connection_owner: bool = False,
) -> models.Invoice:
    """Draft AND issue in one act — the door `metering` calls at a build's commit.

    ONE transaction, `raise_and_issue_charge_fee`'s reason word for word: a
    quote that drafted and failed to issue would sit as a draft nobody looks at,
    carrying an invoice number, while the build says the developer owes it. The
    commit either takes the quote to AR or does not happen.
    """
    with transaction.atomic():
        invoice = raise_quote_bill(
            actor,
            account_id=account_id,
            charges=charges,
            on_date=on_date,
            due_days=due_days,
            pending_new_connection_owner=pending_new_connection_owner,
        )
        # A DERIVATION FROM THE ARGUMENT, not a default value — BR-TEN-043 / G6.
        issue_charge_fee(actor, invoice, issued_at=issued_at or issue_moment(on_date))
    invoice.refresh_from_db()
    return invoice


def price_charge_fee(
    *,
    account_id: Any,
    charge_code: str,
    on_date: date,
    description: str | None = None,
    entered_amount: Decimal | None = None,
    pending_new_connection_owner: bool = False,
) -> PricedFeeBill:
    """Everything `raise_charge_fee` resolves BEFORE it writes anything.

    `entered_amount` — DEF-RAT-8753: the clerk's figure for a code priced
    *entered when used* (`per_case`); refused for every other code.

    ⚠ **EXTRACTED FOR THE ONE-TIME TAB'S STEP 3** (`CR-108` wave 1), and for
    `runs.price_account`'s reason rather than for convenience: screen 22.6 shows
    a clerk the line and its amount BEFORE the button that writes, and the
    figure it shows has to be the figure the draft will carry. A preview that
    re-read the charge code would be a second reading of BR-BIL-007 — and the
    two would eventually disagree about a retired code, a percent rule or a
    missing GL account, which are precisely the four states this module refuses
    on rather than defaults through.

    **IT WRITES NOTHING AND CONSUMES NO BILL NUMBER.** No run row is minted
    (`BR-BIL-005`'s idempotency key is untouched) and `assemble_document` — the
    only function in this product that writes a bill — is not called, so
    `core.numbering` spends nothing (`BR-BIL-063`). The four refusals fire here
    exactly as they fire at draft, which is the whole point: a fee that cannot
    be raised says so on the screen instead of at the button.
    """
    account = _account_facts(
        account_id, on_date=on_date, pending_new_connection_owner=pending_new_connection_owner
    )
    # DEF-RAT-8826 — the price in force on the BILL's date, for the account's class.
    line = charge_code_line(
        charge_code,
        description=description,
        taxable_from_code=True,
        entered_amount=entered_amount,
        on_date=on_date,
        customer_class=gather._customer_class(account.row),
    )
    if line.taxable:
        # ❄️ B4.2 RE-SIGNED 2026-09-30 — the tenant marked this code taxable,
        # so the bill runs the engine's one tax pass over it. See the module
        # docstring; the preview and the draft both come through here, so the
        # figure a clerk is shown is the figure the draft carries.
        priced = _taxed_fee(account, (line,), on_date=on_date)
    else:
        priced = _PricedFee(currency=account.currency, lines=(line,), total=line.amount)
    return PricedFeeBill(
        account=account,
        priced=priced,
        usage=_fee_usage(account, on_date=on_date),
    )


def _taxed_fee(
    account: "_AccountFacts", lines: tuple[rating_seam.RatedLine, ...], *, on_date: date
) -> _PricedFee:
    """The fee lines priced by the ENGINE, with the account's tax — ❄️ B4.2 as
    re-signed 2026-09-30.

    Nothing here is arithmetic. The lines, the taxable subtotal, the tax total
    and the total are all copied off `rating_seam.price_fee_bill`, which runs
    the engine's own finalize → compute-tax → assemble stages ONCE over the
    bill (BR-RAT-062 / GT-17 ❄️). Each line is finalized there — half-up 2dp,
    the one rounding event (B4.4 / CLAUDE.md rule 2) — and stored at 4dp by
    `assemble_document` as every other bill line is.
    """
    rated = rating_seam.price_fee_bill(
        account=rating_seam.AccountContext(
            currency=account.currency, tax_exempt=account.tax_exempt
        ),
        taxes=_fee_bill_taxes(account, on_date=on_date),
        fees=lines,
    )
    return _PricedFee(
        currency=account.currency,
        lines=tuple(rated.lines),
        total=rated.total,
        tax_total=rated.tax_total,
        taxable_subtotal=rated.taxable_subtotal,
    )


def _fee_bill_taxes(account: "_AccountFacts", *, on_date: date) -> tuple[Any, ...]:
    """The ACCOUNT's taxes, resolved the way an ordinary bill resolves them.

    Tax hangs off the PLAN (PO 2026-08-11: *"Tax rates are for bill not for
    service"*) and the account derives its plan from its UNIT (BR-CUS-014), so
    this walks account → unit → plan exactly as `gather._gather_account` does
    and asks `gather._taxes_for` — the SAME resolver — with the same class,
    premises and account facts. The one difference is deliberate:
    **`services=()`**. A fee bill charges no service, so a tax scoped to one
    fails closed in `rating.selectors.tax_applies_to` (DEF-273) and never
    reaches a fee. A master account with no unit of its own prices from the
    first unit it covers, as `gather` does (`BR-CUS-1010`).

    ⚠ **AN ACCOUNT WITH NO PLAN REFUSES — IT IS NEVER CHARGED UNTAXED.** The
    PO ruled that a taxable fee IS taxed; an account whose taxes cannot be
    found has no rule to tax it by, and quietly issuing the fee without its
    tax would be the filing error `OQ-812` named. The refusal names the fix.
    """
    row = account.row
    unit_id = getattr(row, "unit_id", None)
    if unit_id is None:
        covered = gather.covered_units(row)
        unit_id = covered[0] if covered else None
    unit_row = gather._resolve("metering", "unit_row")
    unit = unit_row(unit_id) if (unit_row is not None and unit_id is not None) else None
    plan_id = getattr(unit, "rate_plan_id", None) if unit is not None else None
    if plan_id is None:
        raise BillingRuleError(
            f"account {account.account_no} has no rate plan, and a taxable fee is taxed "
            "by the plan's own tax rules (B4.2 as re-signed 2026-09-30). Nothing here "
            "charges it untaxed. A human puts the account's unit on a plan, or marks "
            "the charge code not taxable on S13.",
            br_ref="BR-RAT-005",
        )
    return gather._taxes_for(
        plan_id,
        on_date,
        customer_class=gather._customer_class(row),
        premises=gather._premises_geography(unit),
        services=(),
        account_id=getattr(row, "id", None),
    )


def raise_charge_fee(
    actor: Any,
    *,
    account_id: Any,
    charge_code: str,
    on_date: date,
    due_days: int,
    description: str | None = None,
    entered_amount: Decimal | None = None,
    pending_new_connection_owner: bool = False,
    run_key_source: str | None = None,
) -> models.Invoice:
    """DRAFT one fee bill for one charge code against one account.

    `entered_amount` — DEF-RAT-8753, see `charge_code_line`.

    `run_key_source` — `DEF-PAY-10740`: the one event this fee answers to,
    appended to the idempotency key (`one_time.create_one_time_run`). The NSF
    fee passes `nsf:<bounced payment uuid>`, so it is keyed PER BOUNCED
    PAYMENT (PO 2026-10-30, *"Two bounces on the same day: A"*); every other
    caller passes nothing and stays keyed (account, `fee`, day) as below.

    **`on_date` is the business event's date and is an ARGUMENT, never a clock**
    (BR-TEN-043, gate G6). For a reconnection fee it is the CUT DATE, because
    BR-CUS-104 rules that the fee is owed the moment the service is cut.

    **`due_days` IS REQUIRED AND THIS MODULE DOES NOT CHOOSE IT.** A cycle-less
    bill has no cycle to take its terms from — CR-029 D8③, PO 2026-08-23: *"it
    will be capture at the time of bulk billing"* — and `issue` refuses a bill
    whose due date cannot be derived rather than guessing one. The caller knows
    what the charge is for; this module does not.

    **IDEMPOTENT ON (account, `fee`, on_date).** `one_time.create_one_time_run`
    keys the run on exactly that (`idempotency.one_time_run_key`), so a
    double-clicked cut raises ONE fee and the second attempt comes back as
    `runs.DuplicateRun` naming the first, with who ran it and when (BR-BIL-005).
    A second fee for the same customer on the same day is refused rather than
    charged twice — which is the right default for a fee nobody re-reads.

    Returns the DRAFT. See the module docstring for why it does not issue.
    """
    # Resolved BEFORE the transaction, so a code that cannot be charged refuses
    # without minting a run row and spending its idempotency key on a bill that
    # was never going to exist. The same call the preview makes — see
    # `price_charge_fee`.
    priced_bill = price_charge_fee(
        account_id=account_id,
        charge_code=charge_code,
        on_date=on_date,
        description=description,
        entered_amount=entered_amount,
        pending_new_connection_owner=pending_new_connection_owner,
    )
    line = priced_bill.line
    account = priced_bill.account
    tenant_id = core_tenancy.current_tenant_id()

    with transaction.atomic():
        run = one_time.create_one_time_run(
            account_id=account_id,
            bill_type=BILL_TYPE_FEE,
            # A fee is charged ON a day, not OVER a window. Both ends are the
            # event's own date rather than a manufactured month: B4.3's
            # proration divides by this window and a fee is not prorated, so a
            # wider window would state a service period this charge never had.
            period_start=on_date,
            period_end=on_date,
            # BR-BIL-070 — the date the bill is dated. On a cycle-less run this
            # is the ONLY source of one, and the caller's event date is it.
            bill_date=on_date,
            due_days=due_days,
            run_by=actor,
            actor=actor,
            pending_new_connection_owner=pending_new_connection_owner,
            run_key_source=run_key_source,
        )
        invoice = assemble_document(
            usage=priced_bill.usage,
            priced=priced_bill.priced,
            tenant_id=tenant_id,
            account_id=account.account_id,
            bill_run=run,
            period_start=on_date,
            period_end=on_date,
            service_date=on_date,
            bill_type=BILL_TYPE_FEE,
        )
        # CLAUDE.md rule 7 — a figure now exists against a named customer.
        audit.money_action(
            actor,
            "invoice.drafted",
            "invoice",
            str(invoice.pk),
            before=None,
            after={
                "bill_type": BILL_TYPE_FEE,
                "account_no": account.account_no,
                "charge_code": charge_code,
                "amount": str(line.amount),
                # DEF-RAT-8753 — say so when the figure is the clerk's.
                "entered_when_used": entered_amount is not None,
                # ❄️ B4.2 re-sign 2026-09-30 — a taxable fee carries tax, so
                # the row states the tax and the bill's total beside the fee.
                # On an untaxed fee these read 0 and the fee's own amount.
                "taxable": bool(line.taxable),
                "tax_total": str(priced_bill.priced.tax_total),
                "total": str(priced_bill.priced.total),
                "currency": account.currency,
                "on_date": on_date.isoformat(),
                "bill_run_id": str(run.pk),
            },
        )
    return invoice


def issue_charge_fee(actor: Any, invoice: models.Invoice, *, issued_at: datetime) -> Any:
    """Issue a drafted fee bill — the act that makes it a RECEIVABLE.

    A thin forwarder. Issue stamps every line's GL account from its charge code
    (BR-BIL-010), freezes the document (rule 4) and hands the posting to the
    ledger (rule 5); none of that is re-implemented here, for the same reason
    this module writes no invoice lines of its own.

    **`issued_at` IS THE CALLER'S** (BR-TEN-043, gate G6): no clock is read on a
    money path, so a replayed cut stamps the same moment rather than a new one.

    ⚠ **THE TEMPLATE PIN IS THE TENANT'S FALLBACK (BR-BIL-025), AND THE LIMIT IS
    STATED RATHER THAN HIDDEN.** BR-BIL-026 pins a template AT ISSUE and the
    columns freeze with the bill, so issue refuses without one. BR-BIL-025
    resolves per ACCOUNT — account override → category default → fallback — and
    **billing has no published read for an account's consumer category**, so
    this resolves `consumer_category=None`, exactly as `api._template_pin_for`
    does for a whole run and with the same consequence: a tenant who has set a
    different template for a category does not get it on a fee bill. Every
    tenant today has at most one bill template, so nothing is mis-pinned; the
    per-account resolution is owed in both places at once and is not invented
    here for one of them.
    """
    from apps.billing import templates_service

    template, version = templates_service.resolve_for(consumer_category=None)
    return issue.issue_invoice(
        invoice,
        issued_at=issued_at,
        template_id=template.pk,
        template_version=version.version_no,
        actor=actor,
    )


def issue_moment(on_date: date) -> datetime:
    """The business event's date as an instant — **derived, never a clock read.**

    BR-TEN-043 and gate G6: a money path reads no wall clock, so `issued_at`
    comes from the date the CALLER named for the event. The start of that day is
    the instant chosen because it is the only one the date itself determines: a
    replay, a resumed batch and a re-run all produce the same value, which is
    the whole property `issued_at` exists to have.

    UTC, deliberately: a tenant's own zone is a tenancy fact and would make this
    a second answer to "when did this happen" that could disagree with the date
    on the document. The DATE is what the customer and the regulator read.
    """
    return datetime.combine(on_date, time.min, tzinfo=dt_timezone.utc)


def raise_and_issue_charge_fee(
    actor: Any,
    *,
    account_id: Any,
    charge_code: str,
    on_date: date,
    due_days: int,
    description: str | None = None,
    issued_at: datetime | None = None,
    run_key_source: str | None = None,
) -> models.Invoice:
    """Draft AND issue in one act — the door `customers` calls at the cut.

    ONE transaction: a fee that drafted and failed to issue would sit as a draft
    nobody ever looks at, carrying an invoice number, while the case says the
    customer owes it. The cut either takes the fee to AR or does not happen.

    `run_key_source` — `DEF-PAY-10740`, forwarded to `raise_charge_fee`. The
    reconnection fee (`customers.disconnects` through `customers.seams`) does
    not pass it and stays keyed per account per day.
    """
    with transaction.atomic():
        invoice = raise_charge_fee(
            actor,
            account_id=account_id,
            charge_code=charge_code,
            on_date=on_date,
            due_days=due_days,
            description=description,
            run_key_source=run_key_source,
        )
        # `issued_at` defaults to the START OF THE EVENT'S OWN DAY and never to
        # a clock (BR-TEN-043 / G6). A caller that holds a more precise instant
        # — an API request time, say — passes it and this derivation stands
        # aside; it is a DERIVATION FROM THE ARGUMENT, not a default value.
        issue_charge_fee(actor, invoice, issued_at=issued_at or issue_moment(on_date))
    invoice.refresh_from_db()
    return invoice


# ── the two reads this module needs, and nothing more ──────────────────────


@dataclass(frozen=True)
class _AccountFacts:
    account_id: str
    account_no: str
    currency: str
    tax_exempt: bool
    #: customers' own account row, HELD rather than copied (as `SingleScope`
    #: holds it), so the taxable-fee path reads the unit, class and id it
    #: resolves taxes from without a second read of who is being charged.
    #: Excluded from equality and repr: it is a source, not a fact of the bill.
    row: Any = field(default=None, compare=False, repr=False)


def _account_facts(
    account_id: Any, *, on_date: date, pending_new_connection_owner: bool = False
) -> _AccountFacts:
    """WHO is being charged and in WHAT currency.

    Through `one_time`'s own billable-account read, so a fee bill verifies the
    account exactly as every other one-time bill does: an unknown id, a
    malformed id and another tenant's id are ONE answer (HR-1), because a
    foreign key alone would not stop a run being pointed at another tenant's
    account — PostgreSQL evaluates referential integrity OUTSIDE row-level
    security.
    """
    # `DEF-MET-9217` — only the New Connection fee door passes the flag.
    scope = one_time.single.billable_account(
        account_id, pending_new_connection_owner=pending_new_connection_owner
    )
    currency = gather._tenant_currency()
    if not currency:
        raise BillingRuleError(
            "the utility's currency is not set, so a fee cannot be charged in it "
            "(CLAUDE.md rule 2 — money never travels without its currency, and the "
            "currency is the TENANT's, never client input).",
            br_ref="BR-TEN-020",
        )
    return _AccountFacts(
        account_id=str(scope.account_id),
        account_no=str(scope.account_no),
        currency=currency,
        # B4.2 / BR-RAT-006 — exemption is account-level, and since the ❄️ B4.2
        # re-sign of 2026-09-30 it DECIDES something: a taxable fee on an
        # exempt account carries no tax. Read off customers' ROW through
        # `gather._tax_exempt_on`, the reader every ordinary bill uses, so a
        # certificate that expired before `on_date` reinstates the tax here too
        # (CR-013 part 4).
        #
        # ⚠ `DEF-BIL-8340` (filed with this change): this read was
        # `getattr(scope, "tax_exempt", False)` until 2026-09-30, and
        # `SingleScope` HAS no `tax_exempt` — the flag lives on `scope.account`
        # — so it answered False for every account, exempt or not. Harmless
        # while no tax pass ran over a fee bill (it reached only the snapshot);
        # the first day a fee bill is taxed it would have taxed an exempt
        # church. `tests/test_oq_812_fee_bill_tax.py::tc3` is the guard.
        tax_exempt=gather._tax_exempt_on(scope.account, on_date),
        row=scope.account,
    )


def _fee_usage(account: _AccountFacts, *, on_date: date) -> MeasuredUsage:
    """The `MeasuredUsage` a fee bill has: a subscription to NOTHING.

    `assemble_document` reads the account, the currency and the snapshot off
    this object, so a fee bill has to present one. **Every service field is
    empty and that is the truthful answer** — a fee is a fact about the ACCOUNT,
    not about a service (`_service_id_for` says the same of every fee line), so
    the document's `services` list is empty rather than carrying a fabricated
    row, and the plan is None rather than borrowing the account's.

    ⚠ It is built here rather than through `resolve_subscription`, which
    REFUSES an account with no `rate_plan_id` — correctly, for a metered bill.
    A fee bill genuinely has no plan, and relaxing that guard to let one
    through would remove the check that stops an unplanned account being billed
    for usage.

    `cycle_days=1, service_days=1` states a window of one day, which is what
    `period_start == period_end` above already says. Nothing prorates a fee, so
    the ratio is 1 and no B4.3 arithmetic reads it.
    """
    return MeasuredUsage(
        subscription=SubscriptionContext(
            account_id=account.account_id,
            account_no=account.account_no,
            currency=account.currency,
            tax_exempt=account.tax_exempt,
            period=rating_seam.BillingPeriod(
                cycle_days=1, service_days=1, start=on_date, end=on_date
            ),
            rate_plan_id=None,
            rate_plan_name=None,
            rate_plan_version=None,
            tariffs=(),
            taxes=(),
            fees=(),
            base_only=False,
            snapshot={},
        ),
        services=(),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-708 (decision log 2026-08-27 §3 · BR-CUS-104 · BR-BIL-007 ·
#         BR-BIL-010 · apps/customers/disconnects.FEE_POSTED (formerly FEE_NOT_POSTED))
# generated: 2026-08-27 by the billing-rulings lane (claude)
# checklist: A✔ B✔ C✔ D=deferred(no API half — the door is a service, called by
#         customers' own cut endpoint) E✔(the S90 cut modal states the posted
#         fee) F✔ G✔ H=deferred(PO 2026-08-09 — HUMAN-REVIEW-PENDING)
# gates: ruff✔ black✔ · tests/test_def_708_the_fee_is_a_real_charge.py
#         PROVED RED: with `raise_and_issue_charge_fee` not called from
#         `commit_cut`, tc2 fails on the gate admitting a customer at $0.00 who
#         owes $75.00 — the defect exactly.
# exceptions: (1) it constructs a `SubscriptionContext` DIRECTLY rather than
#         through `resolve_subscription`, because a fee bill has no rate plan
#         and that function refuses one — REPORTED rather than relaxing a guard
#         that protects the metered path. (2) it presents a priced RESULT
#         (`_PricedFee`) without running the pricing engine, because
#         `price_bill` refuses a serviceless bill by name and a charge code is
#         not priced at all. (3) ⚠ READ "`charges.taxable_default` is NOT read — see
#         `OQ-812`" UNTIL 2026-09-30. It is read now, by `price_charge_fee` only
#         (the ❄️ B4.2 re-sign, PO "Yes, re-sign.", RECON $75.00 at 8.25% →
#         $81.19), and a taxable fee is taxed by the engine's `price_fee_bill`
#         — tests/test_oq_812_fee_bill_tax.py, red first.
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
