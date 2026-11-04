# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-004 (subledger tie-out views + drift red flag on S36 —
#           RELEASE BLOCKER; TC-1 the LE-1 greens, TC-2 the LE-7 fault, TC-3
#           the basis labels, TC-5 no dismiss path, TC-6 isolation)
#           Screens: S36
# Rules:    BR-LED-007 (deposit-liability GL = Σ deposits held · AR GL = Σ
#           account balances · tax payable = remittance outstanding; ANY drift
#           = red flag + release blocker) · BR-REP-001 (every money number
#           labels its date basis) · BR-REP-002 (a read-model over journal-line
#           dimensions, never a side-maintained number) · BR-LED-015 (the
#           inspection audits) · BR-TEN-013 (a cross-module read resolves the
#           owner's published callable) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 2 (money NUMERIC(18,6) + CHAR(3), never float)
# Golden:   LE-1 (AR 152.32 = 135.90 + 16.42 · deposit 0.00 = 0.00 · tax 47.38)
#           · LE-7 (the fault: deposit register 153.50 vs GL 150.00 = −3.50)
# Tests:    06-backend/tests/test_us_led_004_tie_out.py
# Impacts:  apps/ledger/finance_api.tie_outs (GET /finance/tie-outs) ·
#           07-frontend/src/features/ledger/RevenueArPage.tsx (the S36 panel)
# ───────────────────────────────────────────────────────
"""S36's three control-vs-register tie-outs, and the drift that blocks a release.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-08-16 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`. This module writes nothing and
decides no money; what it decides is whether a utility is told its books agree
with its bills, which is the one claim on S36 that must never be wrong in the
reassuring direction.

════════════════════════════════════════════════════════════════════════════
WHAT A TIE-OUT IS, IN THIS PRODUCT, IN ONE SENTENCE EACH
════════════════════════════════════════════════════════════════════════════
BR-LED-007 (CONFIRMED — PO LF-7, 2026-08-08), verbatim:

    "Tie-outs on S36: deposit-liability GL = Σ deposits held · AR GL = Σ account
     balances · tax payable = remittance outstanding; ANY drift = red flag +
     release blocker."

A CONTROL account in the general ledger holds one lump — *the utility is owed
152.32*. A SUBLEDGER holds the same money broken out per customer, per deposit,
per authority. They are two records of one fact, written by different paths, and
accounting's oldest check is that they must agree to the cent. When they do not,
something wrote money down one path and not the other — which in this product
can only mean a bypass of the ledger posting service (US-LED-004 §1), an
un-dimensioned line, or a register nobody maintains.

**The panel is computed live and never cached** (BR-REP-002). There is no
`tie_out_results` table and there must not be one: a stored tie-out is a
side-maintained number, and a side-maintained number that disagrees with the
books is the exact bug this check exists to catch.

════════════════════════════════════════════════════════════════════════════
⚠ WHAT "Σ ACCOUNT BALANCES" HAD TO MEAN, AND WHY IT IS NOT `accounts.balance`
════════════════════════════════════════════════════════════════════════════
The obvious reading of BR-LED-007's AR row is *compare 1200 against Σ
`accounts.balance`*. **That would report drift on every healthy tenant in the
product**, and the reason is DEF-127: `accounts.balance` is a CACHE (BR-CUS-015)
that **nothing in this product has ever written**, so the Σ is 0.00 for every
tenant and the panel would go red the moment a first bill issued. A release
blocker that fires on a correct book is worse than no check at all — it is the
check everybody learns to ignore.

So the AR register is the one a clerk can actually open: the per-account AR
positions `reporting.ar_positions` derives, restricted to accounts that exist in
customers' own published register. That makes the comparison a real one with a
real failure mode, stated so a reviewer can rule on it:

    CONTROL   Σ every posted line on the AR designation      (`ar_control`)
    REGISTER  Σ the same lines, per account, for accounts customers still holds

They differ by **exactly the AR money no customer account claims** — a line
posted with no `account_id`, or one naming an account the register has lost.
On LE-1 both are **152.32** and the row is green. `apps/customers/selectors.
accounts_rollup` names this comparison in its own docstring and defers it here:
*"the S36 tie-out panel (US-LED-004) is the thing that compares them; a screen
must never do that subtraction itself."*

════════════════════════════════════════════════════════════════════════════
⚠ THE DEPOSIT REGISTER IS UNMAINTAINED, AND THAT IS REPORTED, NOT SMOOTHED
════════════════════════════════════════════════════════════════════════════
US-LED-004 §5 signs the deposit register as *"accounts.deposit_on_file +
interest"*. **No code path in this product writes `accounts.deposit_on_file`**
— it is `default=0`, it is a `REFUSED_FIELD` on the account edit path
(`apps/customers/services.REFUSED_FIELDS`: *"a LOOKUP from the plan deposit
schedule"*), and the lookup that would fill it is US-CUS-007's and is unbuilt.
Meanwhile `apps/payments/ledger_seam.py` DOES credit the 2300 deposit-liability
GL every time a deposit-purpose payment clears.

So the two sides are written by one path and not the other, and the first
tenant to take a $150.00 deposit gets a red panel. **That is a true finding**
— the register really is not being kept — and it is reported as DEF-177 rather
than hidden by comparing the GL against itself. The row therefore carries BOTH
figures and the cause code `deposit_register_is_never_written`, so a finance
officer reads *"the books say 150.00, the customer register says 0.00, and the
register is not being maintained"* rather than *"your books are wrong"*.

Implementing the signed rule and REPORTING that its register is unmaintained is
the honest shape. Substituting Σ deposit-purpose payments — a register that IS
maintained — would make the row green and would compare the ledger against the
ledger, which is not a tie-out at all.

════════════════════════════════════════════════════════════════════════════
THREE STATES, NOT TWO — "CANNOT TELL" IS NEVER "AGREES"
════════════════════════════════════════════════════════════════════════════
US-LED-004's acceptance is *"three green equalities, or a named red flag"*, and
a real deployment has a third case: a side that cannot be computed at all (the
tenant has designated no AR account; customers publishes no register read). A
two-state model has to fold that into one of the others, and both foldings are
defects — `agreed` is a lie, `drifting` invents a delta out of an absence.

    AGREED        both figures known and equal
    DRIFTING      both figures known and different  → release blocker
    UNVERIFIABLE  a side could not be read          → release blocker, no delta

Both non-green states block, because BR-LED-007's blocker is about a book that
has not been PROVED to agree. Neither ever shows a zero for a figure it does not
have (`None` + the reason), and a drift always shows **both** figures with their
currency — never a bare "failed", which tells a finance officer nothing they can
act on.

**AND THERE IS NO DISMISS PATH** (US-LED-004 TC-5). Nothing here accepts an
acknowledgement, stores one, or takes a parameter that suppresses a row. Drift
clears when the explaining entry posts through the service, and by no other
means. That is why this module has no writes: an acknowledgement would need one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

from apps.ledger import chart, models, reporting
from core import errors
from core import tenancy as core_tenancy

ZERO = Decimal("0")

#: BR-REP-001 — the panel's basis, on the result rather than in a caption a
#: screen may forget to render. Both sides are POSTING basis: the registers are
#: derived from the same posted lines, and US-LED-004 TC-3 requires the label.
BASIS = reporting.BASIS_POSTING

#: The three subledgers BR-LED-007 names, as codes. Codes and not prose: the
#: frontend translates them (G18), the audit trail groups on them, and a rule
#: quoted into a UI string is a rule that drifts from the one it quotes.
SUBLEDGER_AR = "accounts_receivable"
SUBLEDGER_DEPOSITS = "deposit_liability"
SUBLEDGER_TAX = "tax_payable"
#: ⚠ **THE FOURTH, ADDED 2026-09-02 — CR-060 T6d.** BR-LED-007 names three
#: because when it was signed the cost side reached the books by no path at all.
#: `CR-060` T6 gave it one — entering a paid-on date posts DR cost / CR cash —
#: and the moment a figure exists on both sides it can disagree on both sides.
#: The T6 lane named this row as an inheritance rather than building it
#: (`cost_capture.SETTLEMENT_INHERITS_T6D`) and said in as many words that until
#: it existed a divergence *"surfaces nowhere"*.
SUBLEDGER_COST = "cost_of_service"
SUBLEDGERS: tuple[str, ...] = (
    SUBLEDGER_AR,
    SUBLEDGER_DEPOSITS,
    SUBLEDGER_TAX,
    SUBLEDGER_COST,
)

#: The three states — see the module docstring. `UNVERIFIABLE` exists so that
#: "nobody could read the register" never renders as "the register agrees".
STATE_AGREED = "agreed"
STATE_DRIFTING = "drifting"
STATE_UNVERIFIABLE = "unverifiable"

#: Customers' published tenant-scoped account register, named once so the
#: boundary is greppable from both sides (BR-TEN-013). Published today — this
#: is not a parked contract.
CUSTOMERS_MODULE = "customers"
ACCOUNT_QUERYSET_READ = "account_queryset"

# ── the causes a row can carry (never a bare "failed") ──────────────────────

CAUSE_NO_AR_DESIGNATION = {
    "code": "no_account_carries_the_accounts_receivable_designation",
    "br_ref": "BR-LED-007 · OQ-106",
    "detail": "this tenant has designated no AR account, so there is no control total to "
    "compare a register against. One chart edit on S56 fixes it; nothing here picks an "
    "account by number. The row is UNVERIFIABLE rather than green — a tie-out nobody could "
    "compute has not been passed.",
}

CAUSE_NO_DEPOSIT_DESIGNATION = {
    "code": "no_account_carries_the_deposit_liability_designation",
    "br_ref": "BR-LED-007 · OQ-110",
    "detail": "this tenant has designated no deposit-liability account, so deposits taken "
    "have nowhere to be held in the books and there is no control total to tie out.",
}

CAUSE_CUSTOMER_REGISTER_UNREADABLE = {
    "code": "customer_register_could_not_be_read",
    "br_ref": "BR-LED-007 · BR-TEN-013",
    "detail": "customers publishes no `account_queryset`, so the subledger side of this "
    "tie-out cannot be summed at all. Reported as UNVERIFIABLE and never as 0.00: a register "
    "nobody could read and a register holding nothing are opposite facts, and treating the "
    "first as the second would report the whole control balance as drift.",
}

CAUSE_DEPOSIT_REGISTER_UNWRITTEN = {
    "code": "deposit_register_is_never_written",
    "br_ref": "BR-LED-007 · US-LED-004 §5 · BR-CUS-023 · DEF-177",
    "detail": "US-LED-004 §5 signs this register as `accounts.deposit_on_file + interest`, "
    "and NO code path in this product writes that column — it is default 0, it is a refused "
    "field on the account edit path, and the plan-schedule lookup that would fill it "
    "(US-CUS-007) is unbuilt. Payments meanwhile credits the deposit-liability GL on every "
    "cleared deposit. So a drift here means the customer register is not being maintained, "
    "not that the books are wrong — DEF-177. Both figures are shown so the difference is "
    "readable rather than accusatory.",
}

CAUSE_SETTLED_COST_DIVERGED = {
    "code": "the_settled_register_and_the_cost_books_disagree",
    "br_ref": "BR-LED-007 · BR-LED-028 · OQ-1350",
    "detail": "the supplier register says one thing about what has been settled and the "
    "books say another. Both figures are shown, and neither is accused: a settlement posts "
    "DR cost / CR cash inside the same transaction that writes the paid-on date, so the two "
    "cannot separate through the ordinary path — `cost_capture._refuse_if_settled` refuses "
    "an edit to any of the four facts the entry copied and raises OQ-1350, which is minted "
    "and unanswered. A drift here therefore means a write went round the service, or that "
    "OQ-1350 has since been answered in a way that moves one side and not the other. The "
    "difference is what to look at; the direction says which side is behind.",
}

CAUSE_TAX_COLLECTED_BASIS_ABSENT = {
    "code": "tax_outstanding_is_the_billed_basis_only",
    "br_ref": "BR-LED-002 · BR-LED-007",
    "detail": "the remittance report's outstanding column is computed on the BILLED basis "
    "(billed − remitted). The COLLECTED basis needs tax-inside-a-payment, which the books do "
    "not hold (`apps/ledger/reporting.py` gap 3), so an authority the tenant remits on the "
    "collected basis is compared on the billed one. The comparison is still exact against "
    "the control account; what it cannot do is tell a collected-basis authority that it owes "
    "less than it has billed.",
}


@dataclass(frozen=True)
class TieOutRow:
    """One control-vs-register comparison, with both figures and its verdict.

    `gl` and `register` are `None` when unreadable and NEVER 0.00 — the whole
    module docstring turns on that distinction. `drift` is `gl − register` and
    is `None` whenever either side is, because a delta computed against an
    absence is a fabricated number wearing a precise one's clothes.
    """

    subledger: str
    state: str
    gl: Decimal | None
    register: Decimal | None
    drift: Decimal | None
    currency: str | None
    basis: str
    causes: tuple[dict[str, Any], ...] = ()

    @property
    def blocks_release(self) -> bool:
        """BR-LED-007: *ANY drift = red flag + release blocker.*

        `UNVERIFIABLE` blocks too. The rule is about a book PROVED to agree, and
        a row nobody could compute has proved nothing — folding it in with the
        greens is how a release ships on a check that never ran.
        """
        return self.state != STATE_AGREED


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owner's callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover — defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _verdict(gl: Decimal | None, register: Decimal | None) -> tuple[str, Decimal | None]:
    """(state, drift) from the two figures — the ONLY place the rule is applied.

    One implementation so that the API, the screen and the audit row cannot
    disagree about whether a book is drifting, which would be this check
    developing the very fault it exists to detect.
    """
    if gl is None or register is None:
        return STATE_UNVERIFIABLE, None
    drift = gl - register
    return (STATE_AGREED if drift == ZERO else STATE_DRIFTING), drift


def _control_total(designation: str, *, as_of: date | None) -> tuple[Decimal | None, str | None]:
    """(net balance of the designated control account, its derived currency).

    Signed by the account's own natural side: AR is an asset and carries a net
    DEBIT, deposit liability and tax payable are liabilities and carry net
    CREDITS. Comparing a liability's net debit against a positive register would
    make every healthy deposit book look like it drifted by twice the balance.
    """
    account_id = reporting._designated_account_id(designation)  # noqa: SLF001 — same module family
    if account_id is None:
        return None, None
    rows = reporting._posted_lines(end=as_of).filter(  # noqa: SLF001
        ledger_account_id=account_id
    )
    currency = reporting._one_currency(rows, figure=f"the {designation} control account")  # noqa: SLF001
    total = ZERO
    for side, amount in rows.values_list("side", "amount"):
        total += amount if side == models.SIDE_DEBIT else -amount
    return (total if designation == chart.AR else -total), currency


def _register_account_ids() -> set[str] | None:
    """The account ids customers still holds, or None when it publishes nothing."""
    read = _resolve(CUSTOMERS_MODULE, ACCOUNT_QUERYSET_READ)
    if read is None:
        return None
    return {str(value) for value in read().values_list("pk", flat=True)}


def _ar_row(*, as_of: date | None) -> TieOutRow:
    """AR GL vs Σ what each customer account owes (BR-LED-007's first row)."""
    gl, currency = _control_total(chart.AR, as_of=as_of)
    if gl is None:
        return TieOutRow(
            subledger=SUBLEDGER_AR,
            state=STATE_UNVERIFIABLE,
            gl=None,
            register=None,
            drift=None,
            currency=None,
            basis=BASIS,
            causes=(CAUSE_NO_AR_DESIGNATION,),
        )
    ids = _register_account_ids()
    if ids is None:
        return TieOutRow(
            subledger=SUBLEDGER_AR,
            state=STATE_UNVERIFIABLE,
            gl=gl,
            register=None,
            drift=None,
            currency=currency,
            basis=BASIS,
            causes=(CAUSE_CUSTOMER_REGISTER_UNREADABLE,),
        )
    positions = reporting.ar_positions(as_of=as_of)
    register = sum(
        (amount for key, amount in positions["positions"].items() if key in ids), ZERO
    )
    state, drift = _verdict(gl, register)
    return TieOutRow(
        subledger=SUBLEDGER_AR,
        state=state,
        gl=gl,
        register=register,
        drift=drift,
        currency=currency or positions["currency"],
        basis=BASIS,
    )


def _deposit_row() -> TieOutRow:
    """Deposit-liability GL vs Σ deposits held per account — BOTH as of NOW.

    ⚠ **THIS ROW TAKES NO `as_of`, AND THAT IS THE DEFECT DEF-2250 (2026-08-28).**
    It used to window the control account at `period_end` and compare the result
    against `accounts.deposit_on_file`, **which is an undated live column**. The
    two sides therefore answered different questions, and the row reported drift
    equal to every deposit taken after the period — on a perfectly correct book.

    It was invisible for as long as the GL side was empty (DEF-177: nothing
    posted, so the windowed total was 0.00 whatever the window). The moment
    deposits started reaching the books it surfaced immediately: the seeded
    estate's cutover is **2026-08-27** and the fixture's last period ends
    **2026-08-14**, so the panel read *GL 0.00 / register 750.00* over a book
    that held exactly 750.00 — the same $750.00 figure as the defect it had
    just stopped being.

    The AR row above is NOT affected and must keep its `as_of`: both of its
    sides are derived from the same posted lines, so the window cancels. Here
    only one side has a window to cancel, which is why the fix is to remove it
    rather than to add one — `accounts.deposit_on_file` cannot answer *"what
    was held on 14 August"* and inventing a date for it would be worse than the
    bug. That is the same lesson as DEF-1064: a tie-out that compares two
    figures answering different questions reports the difference as a fault.

    Carries `CAUSE_DEPOSIT_REGISTER_UNWRITTEN` **whenever it drifts** — the
    register and the liability are written by different paths (BR-CUS-670 /
    BR-CUS-671), so a drift here names WHICH side is behind rather than
    implying the books are wrong.
    """
    gl, currency = _control_total(chart.DEPOSIT_LIABILITY, as_of=None)
    if gl is None:
        return TieOutRow(
            subledger=SUBLEDGER_DEPOSITS,
            state=STATE_UNVERIFIABLE,
            gl=None,
            register=None,
            drift=None,
            currency=None,
            basis=BASIS,
            causes=(CAUSE_NO_DEPOSIT_DESIGNATION,),
        )
    read = _resolve(CUSTOMERS_MODULE, ACCOUNT_QUERYSET_READ)
    if read is None:
        return TieOutRow(
            subledger=SUBLEDGER_DEPOSITS,
            state=STATE_UNVERIFIABLE,
            gl=gl,
            register=None,
            drift=None,
            currency=currency,
            basis=BASIS,
            causes=(CAUSE_CUSTOMER_REGISTER_UNREADABLE,),
        )
    register = ZERO
    for held in read().values_list("deposit_on_file", flat=True):
        register += held if held is not None else ZERO
    state, drift = _verdict(gl, register)
    return TieOutRow(
        subledger=SUBLEDGER_DEPOSITS,
        state=state,
        gl=gl,
        register=register,
        drift=drift,
        currency=currency,
        basis=BASIS,
        causes=() if state == STATE_AGREED else (CAUSE_DEPOSIT_REGISTER_UNWRITTEN,),
    )


def _tax_row(*, period_start: date, period_end: date) -> TieOutRow:
    """Tax-payable GL vs the remittance report's outstanding column.

    The register is `remittance_by_authority`'s own `outstanding_billed` total
    — the SAME rows the S41 screen prints, so the panel and the remittance
    report cannot state different numbers about the same authorities.
    """
    remittance = reporting.remittance_by_authority(start=period_start, end=period_end)
    # A tenant with NO tax-authority account gets the remittance report's own
    # short shape, which carries neither key. Both sides are then genuinely
    # 0.00 — there is no tax liability and nothing outstanding — so this is an
    # AGREED row and not an unverifiable one: nothing was unreadable, there was
    # simply nothing to read. `.get` with an explicit ZERO rather than a
    # `KeyError`, because a utility that bills no tax is a lawful utility.
    gl = remittance.get("tie_out", {}).get("tax_payable_gl", ZERO)
    register = remittance["totals"].get("outstanding_billed", ZERO)
    state, drift = _verdict(gl, register)
    return TieOutRow(
        subledger=SUBLEDGER_TAX,
        state=state,
        gl=gl,
        register=register,
        drift=drift,
        currency=remittance["currency"],
        basis=BASIS,
        causes=() if state == STATE_AGREED else (CAUSE_TAX_COLLECTED_BASIS_ABSENT,),
    )


def _cost_row() -> TieOutRow:
    """Settled supplier cost in the BOOKS vs settled supplier cost in the
    REGISTER — CR-060 T6d, the fourth pair BR-LED-007 could not name in August.

    **CONTROL** — Σ the DEBIT lines every settlement posted, identified by the
    settlement's own `source_type`. Not "Σ the cost accounts": an accrual, a
    manual journal entry or a correction may lawfully touch 5110 without a
    supplier invoice behind it, and comparing those against the purchase
    register would report drift on a correct book — the same trap `_ar_row`
    avoids by not summing `accounts.balance`.

    **REGISTER** — Σ `amount` over captured supplier invoices carrying a
    `paid_on`. `paid_on` is what makes a row postable (CR-060 C1), so it is the
    one column that defines the same population on both sides.

    **UNDATED, LIKE THE DEPOSIT ROW AND FOR THE SAME REASON (DEF-2250).** The
    register side has no book date at all — an invoice is settled or it is not
    — so windowing the control total would compare two answers to different
    questions. And it would fire on the ordinary case rather than a rare one: a
    July purchase paid on 4 August books into AUGUST, so a July-windowed control
    would read 0.00 against a register holding the whole amount, on a book that
    is exactly right.

    **BOTH SIDES ZERO IS AGREED, NEVER UNVERIFIABLE.** A utility that has
    settled nothing has nothing unreadable — the same distinction `_tax_row`
    already draws for a utility that bills no tax.

    ⚠ **AND IT STILL NAMES A CURRENCY IN THAT CASE.** `_one_currency` answers
    `None` over an empty set, which is honest about the LINES and wrong about
    the ROW: US-LED-004 TC-3 requires every row to label its basis AND its
    currency, and a panel showing `0.00` with no code beside it is the ambiguity
    BR-REP-001 exists to remove. So an empty book falls back to the tenant's
    declared book currency, exactly as `exports._currency` does and for the same
    stated reason — a CAD tenant's panel must not read USD.
    """
    from apps.ledger import cost_capture, exports  # local: avoids an import cycle

    lines = reporting._posted_lines().filter(  # noqa: SLF001 — same module family
        journal_entry__source_type=cost_capture.SETTLEMENT_SOURCE_TYPE,
        side=models.SIDE_DEBIT,
    )
    currency = reporting._one_currency(lines, figure="settled supplier cost")  # noqa: SLF001
    gl = ZERO
    for amount in lines.values_list("amount", flat=True):
        gl += amount
    if currency is None:
        currency = exports._currency()  # noqa: SLF001 — the tenant's declared book currency

    register = ZERO
    settled = cost_capture.models.SupplierInvoice.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        status=models.SUPPLIER_INVOICE_CAPTURED,
        paid_on__isnull=False,
    )
    for amount in settled.values_list("amount", flat=True):
        register += amount

    state, drift = _verdict(gl, register)
    return TieOutRow(
        subledger=SUBLEDGER_COST,
        state=state,
        gl=gl,
        register=register,
        drift=drift,
        currency=currency,
        basis=BASIS,
        causes=() if state == STATE_AGREED else (CAUSE_SETTLED_COST_DIVERGED,),
    )


def tie_outs(*, period_start: date, period_end: date) -> dict[str, Any]:
    """The three rows S36 renders side by side, and whether they block a release.

    Worked, against the signed month, so the figures are concrete rather than
    described (US-LED-004 §7, LE-1/LE-7 verbatim):

        AR                GL 152.32   register 152.32   drift 0.00   AGREED
                          (135.90 held on the master account + 16.42 unpaid)
        Deposit liability GL   0.00   register   0.00   drift 0.00   AGREED
                          (150.00 taken + 3.50 interest − 153.50 applied)
        Tax payable       GL  47.38   register  47.38   drift 0.00   AGREED

    …and LE-7's fault, which is the case the whole panel exists for: a deposit
    register of **153.50** against a GL of **150.00** renders **DRIFTING**, with
    both figures, their currency, the delta **−3.50** and the subledger named.

    `period_start` / `period_end` scope the TAX row only, and that is not an
    inconsistency: AR and deposits are CUMULATIVE control balances (what is owed
    and what is held, as of now), while a remittance is answered for a filing
    period. Comparing a cumulative tax balance against one period's outstanding
    would report drift equal to every earlier period's tax, on a correct book.

    ⚠ **AND THAT PARAGRAPH WAS TRUE OF THE DEPOSIT ROW ONLY IN PROSE UNTIL
    2026-08-28 (DEF-2250).** It said *"as of now"* while the code passed
    `period_end` — hard-won law 1, in the file's own docstring. The AR row
    genuinely is cumulative-as-of-`period_end` on BOTH sides, so its window
    cancels; the deposit row's register side has no date at all, so its window
    did not. It now takes none.
    """
    if core_tenancy.current_tenant_id() is None:
        # CLAUDE.md rule 1 — refuses rather than defaulting. A tie-out computed
        # with no tenant context would compare one utility's control account
        # against another's register, which is the one wrong answer this panel
        # could give that a reader would believe.
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    rows = (
        _ar_row(as_of=period_end),
        # ⚠ NO `as_of` — DEF-2250, and `_deposit_row`'s own docstring carries
        # the reasoning. The register side is an undated live column, so a
        # windowed control total compares two answers to different questions.
        _deposit_row(),
        _tax_row(period_start=period_start, period_end=period_end),
        # ⚠ NO WINDOW — CR-060 T6d, and `_cost_row`'s own docstring carries the
        # reasoning. A July purchase paid in August books into August, so a
        # windowed control total would read 0.00 against a full register on a
        # book that is exactly right: DEF-2250's mistake, in the ordinary case
        # rather than a rare one.
        _cost_row(),
    )
    drifting = tuple(row.subledger for row in rows if row.state == STATE_DRIFTING)
    unverifiable = tuple(row.subledger for row in rows if row.state == STATE_UNVERIFIABLE)
    return {
        "basis": BASIS,
        "period": {"start": period_start, "end": period_end},
        "rows": rows,
        "drifting": drifting,
        "unverifiable": unverifiable,
        # BR-LED-007's own words. Published as a FIELD rather than left for a
        # screen to derive from the rows: a screen that computed it could render
        # three red rows and no blocker, and US-LED-004 calls this a release
        # blocker rather than a warning.
        "release_blocked": bool(drifting or unverifiable),
        # US-LED-004 TC-5 — there is no dismiss path, and the absence is stated
        # on the wire so a client cannot look for one and quietly not find it.
        "dismissible": False,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-004@7eb889f (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-01-posting-consumption.md — US-LED-004 §1/§3/§4/§5/§6/§7 — · 04-docs/05-modules/09-ledger/02-business-rules.md — BR-LED-007 —; co-cited LE-1/LE-7 of 08-worked-examples.md, BR-REP-001/002, B2 Addendum r13 #6)
# generated: 2026-08-16 by story-coder (US-LED-004 release-blocker lane)
# checklist: A✔ B✔ C✔ D✔(GET /finance/tie-outs — apps/ledger/finance_api.py) E✔(the S36 panel in RevenueArPage.tsx) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN — a 5.00 drift tolerance in `_verdict` swallowed LE-7's -3.50 ("assert 'agreed' == 'drifting'"); dropping the liability sign flip in `_control_total` reported the deposit control as -150.00 ("assert Decimal('-150.000000') == Decimal('150.00')"); folding an unreadable AR side into the greens served a plausible 0.00 = 0.00 ("assert 'agreed' == 'unverifiable'"). All three verbatim in the human-review ledger row
# exceptions: (1) the AR register is Σ per-account AR positions restricted to customers' published register, NOT Σ `accounts.balance` — that column is a cache nothing writes (DEF-127) and comparing against it would make the blocker fire on every healthy tenant; argued in the module docstring and put to the PO with its figure · (2) the DEPOSIT register IS `accounts.deposit_on_file` as signed, and nothing writes that column either — reported as DEF-177 and carried as a named cause on the row rather than smoothed away · (3) this module writes nothing, including no audit row: the drift audit (US-LED-004 §5 `tieout.drift_detected`) belongs to the endpoint, which is where an actor exists · (4) the tax row's outstanding is the BILLED basis only (reporting.py gap 3), named on the row
#         (5) AMENDED 2026-08-28 (DEF-2250) — `_deposit_row` TAKES NO `as_of`. It
#         windowed the 2300 control account at `period_end` and compared the result
#         against `accounts.deposit_on_file`, an UNDATED live column, so it reported
#         drift equal to every deposit taken after the period — on a correct book.
#         Invisible while nothing wrote 2300 (DEF-177); it surfaced the day deposits
#         reached the books, reading GL 0.00 / register 750.00 over a book holding
#         exactly 750.00. The AR row KEEPS its `as_of` — both of its sides come from
#         the same posted lines, so its window cancels. Proved RED by restoring the
#         window: `GL 0 vs register 750.000000 (drift -750.000000)`.
#         (6) THE DEPOSIT REGISTER IS NOW WRITTEN (BR-CUS-670 / BR-CUS-671), so
#         `CAUSE_DEPOSIT_REGISTER_UNWRITTEN`'s detail is history rather than a live
#         finding — it is KEPT because a drift here still means one of the two paths
#         is behind, and the row must say WHICH rather than accuse the books.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
