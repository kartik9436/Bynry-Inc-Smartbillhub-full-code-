# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-041 (EP-INT-11) — the partner surface reads bills.
#           CR-069 §11: one seam file per module integrations reads from.
#           **CR-110-BRC04 phase 2 wave 3** — the NESTED bill: one record per
#           bill carrying one row per LINE, each with the GL account that line
#           posted to. PO 2026-09-16, verbatim: *"we save bills as a multiple
#           line items with gl code map so for bill we will need nasted json
#           with multiple records with gl code mapped"*.
# Rules:    BR-INT-054 (land and hand over; do not interpret) · CLAUDE.md hard
#           rule 1 (no tenant argument) · hard rule 2 (4 stored, 2 displayed) ·
#           hard rule 3 (consumption never travels without its unit) ·
#           hard rule 4 (a DRAFT is not a financial record and is never served;
#           a correction is a NEW ROW, so both documents go)
# Tests:    06-backend/tests/test_us_int_041_partner_surface.py
#           06-backend/tests/test_cr110_phase2_bills_and_payments.py
# Impacts:  apps/integrations/partner_api.py
# ───────────────────────────────────────────────────────
"""integrations → billing: the bills a partner may collect, as we hold them.

⚠ **A DRAFT IS NEVER HANDED OVER, AND THAT IS HARD RULE 4 RATHER THAN A
FILTER.** A draft invoice is discardable — its numbers move, and it may never
become anything. An issued invoice is an immutable financial record. A finance
system that collected drafts would post entries for bills that later changed or
vanished, and it would have no way to know: nothing in the payload distinguishes
them, because nothing that is not issued reaches the payload at all.

⚠ **AND BOTH DOCUMENTS OF A CORRECTION GO — THE ORIGINAL AND ITS REBILL.** A
bill is never UPDATED: `INVOICE_LOCKED_STATUSES` covers `issued`, `paid`, `void`
and `corrected`, and billing's own model says why — *"`corrected` and `void` are
terminal readings of a bill that WAS issued, so they are locked too — a
correction is a new row."* Sending only the newer one would leave a partner's
books permanently wrong: they have already posted the original, and the
correction is the thing that reverses it. `status`, `billType` and `replaces`
are what let them pair the two without guessing (PO 2026-09-16: *"here you will
ahve to consiede what is the latestbill - we might have latest copy as
corrected bill - or udpated bill so decide which one to take"* — there is no
latest copy, so both go).

THE NESTED SHAPE (CR-110-BRC04 phase 2 wave 3)
-----------------------------------------------
Until this wave `as_record` returned FOUR fields and said so deliberately:
*"the four fields that are ours to hand over."* The PO's ruling replaced the
supplied document's FLAT sample, which carries one `accountString` per bill and
can only be right when every line of a bill posts to one account. On this
product's own demo tenant a single bill hits `4100`, `4105`, `4110`, `4115` and
`2200-01` — five accounts on one document — so a flat payload would force us to
pick one and lose the other four.

⚠ **`accountString` IS `ledger_accounts.code` AND IT IS NOT COMPUTED HERE.**
PO 2026-09-16: *"this is already done using setting and plans and rates - bills
are generated with gl code only - you can check this out"*. It checks out:
`rating.charges.gl_account_id`, `rating.taxes.liability_gl_account_id` and
tenancy's defaults all flow onto `invoice_lines.gl_account_id` AT ISSUE
(BR-BIL-010) and are frozen there. This seam resolves that stamped id to the
code the chart calls it, through `ledger.selectors.account_labels` — the
batched read billing's own Charges tab already uses, published for DEF-937 for
exactly this reason. Nothing here re-decides which account a line posted to.

⚠ **A LINE WITH NO STAMPED ACCOUNT SERVES `accountString: null` — NEVER A
GUESS AND NEVER A DEFAULT.** A default would post a real amount to an account
nobody chose, which is worse than a null a partner's job can stop on.

**MEASURED ON THE DEMO TENANT, 2026-09-16, AND THE NUMBER IS ZERO — WHICH IS
WHY IT IS WRITTEN DOWN RATHER THAN LEFT AS A REASSURANCE.** Seven of Brazos
Bend's 647 invoice lines carry no `gl_account_id`, and **all seven are on the
one DRAFT invoice**, which never leaves (hard rule 4). Of the 640 lines on the
81 bills a partner can collect, **640 carry a code**. So the null path is real,
is tested, and fires on nothing today — a fact that will stop being true the
first time a tenant prices a charge with no account behind it.

⚠ **`id` IS THE BILL NUMBER AND NEVER THE DATABASE KEY.** The PO's document
draws a numeric id; ours is `BL-2607-000041`. That divergence is recorded
rather than followed — a partner keyed on our uuid is coupled to our storage
forever, and the number is what a clerk and a customer already say out loud.

THE THREE BALANCE CLOCKS, WHICH ARE THREE DIFFERENT MOMENTS
------------------------------------------------------------
None of the three is stored on the row, and the next reader will assume they
are the same figure. They are not:

  * `before_pay_outstanding` — **AS AT THE BILL DATE.** It is read from the
    bill's OWN stamped `balance_forward` block (BR-BIL-035, written at issue
    into `bill_payload` and immutable ever after), so it is the very figure
    printed on the document the customer holds. It never moves again.
  * `after_pay_outstanding` — **THIS DOCUMENT, TODAY.** `before` + this bill −
    what payments has since allocated against this invoice. It moves every time
    a payment lands on this bill and stops moving when the bill is settled.
  * `amount` — **THE ACCOUNT, NOW.** Everything the account owes at the moment
    of the call, across every bill, through `billing.open_balance`. It moves
    when any bill issues and when any payment lands.

⚠ **SO `amount` MEANS SOMETHING DIFFERENT HERE THAN IT DID ON THE RETIRED FLAT
ROUTE**, where it was the bill's own total. That is the single strongest reason
the phase-1 pair had to retire rather than be upgraded in place: one key, two
meanings, and a finance system cannot see the difference. The bill's own total
is `bill_amount` on this payload and has its own name for the same reason.

⚠ **AN UNREACHABLE FIGURE IS NULL, NEVER ZERO** — the posture `_stamp_balance_
forward` already takes. `0.00` told to a partner about a customer in arrears
says they are square.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from core.tenancy import current_tenant_id

#: Issued, and everything an issued bill can become. A draft is absent by
#: design (see the docstring); a void bill IS served, because a finance system
#: that posted the original needs to know it was voided.
COLLECTABLE_STATUSES = ("issued", "paid", "void", "corrected")


#: `CR-111-BRC04` · what `projectType` says on every bill this product issues.
#:
#: ⚠ **A LITERAL, BY PO RULING 2026-09-17, AND THE QUESTION IT ANSWERS IS THE
#: HARD ONE.** Asked what `projectType` should say when ONE bill covers several
#: services — electric and water and trash on one document, which is the
#: ordinary case in this product — the PO answered: *"a) always \"Utility
#: Billing\""*. So it is **a fixed category on their side, not a description of
#: our bill**, and it is the same six characters on a single-service bill and on
#: an eleven-service one.
#:
#: ⚠ **WHICH MEANS IT IS DELIBERATELY NOT DERIVED, AND A LATER LANE MUST NOT
#: "IMPROVE" IT.** Reading the bill's services and composing *"Electric, Water"*
#: is the obvious next move and it is the thing that was ruled against: a
#: partner branching on this value would get one answer for a house on one
#: service and another for the house next door on two, from the same utility, on
#: the same run. The ruling makes it a constant precisely so that it cannot.
#:
#: ⚠ **IT IS NOT TRANSLATED.** B14 rule 35 governs what a CLERK reads on a
#: screen in their own language; this is a category on a partner's record, in the
#: partner's agreed spelling, and a localised `projectType` would be a different
#: value per catalogue for one fact.
PROJECT_TYPE = "Utility Billing"


def _model() -> Any:
    from apps.billing import models as billing_models

    return billing_models.Invoice


def display_amount(value: Any) -> str:
    """Four stored decimals → two displayed, half-up (hard rule 2, B4)."""
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _maybe_amount(value: Any) -> str | None:
    """`display_amount` for a figure that is allowed to be ABSENT.

    An unreachable seam stamps nulls rather than zeros (BR-BIL-035), and a
    partner reading `0.00` where we meant *we could not tell you* would post
    that a customer in arrears is square."""
    if value is None or value == "":
        return None
    return display_amount(value)


def collectable(*, since: date | None = None, until: date | None = None) -> Any:
    """The queryset a partner's page is cut from. No tenant ARGUMENT — the
    tenant is on the session (hard rule 1).

    ⚠ **THE WINDOW IS APPLIED BEFORE THE PAGE AND THE ORDER ENDS IN A UNIQUE
    COLUMN, AND BOTH HALVES ARE THE PAGING TRAP** (`CR-110-BRC04` phase 2).
    Page numbers over a moving table SKIP rows: pull page 1 of *newest first*,
    let three bills issue, and three fall off the end unseen — and a missed
    bill is a missed GL posting that nothing on either side raises. Bounding by
    `since`/`until` first makes the set a partner is paging through a set that
    has stopped changing, and ending the sort on `id` means no two rows can
    swap places between two calls.

    ⚠ **THE `tenant_id` FILTER IS BELT AND BRACES AND IT IS THE THIRD PLACE
    THIS WAVE NEEDED IT.** RLS `FORCE` scopes this on PostgreSQL, so it is
    redundant in production. **The suite runs on SQLite, which has no RLS**
    (`config/settings/test.py` hardcodes it), and the first draft relied on RLS
    alone: `test_tc7…` asked Lone Star Ridge for its seven payments and got
    ELEVEN — its own seven and Brazos Bend's four. Written the other way round,
    a partner reading another utility's money would have passed the entire
    suite, because the one mechanism that stops it does not exist on the vendor
    the suite runs on (CLAUDE.md law 7, *structurally incapable of failing*).
    So the tenant is stated twice, and the isolation case can go red on either
    vendor. `runners/serve.py` and `subprocessors.py` carry the same paragraph.

    """
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return _model().objects.none()
    query = (
        _model()
        .objects.filter(tenant_id=tenant_id, status__in=COLLECTABLE_STATUSES)
        .exclude(issued_at=None)
    )
    if since is not None:
        query = query.filter(issued_at__date__gte=since)
    if until is not None:
        query = query.filter(issued_at__date__lte=until)
    return query.order_by("issued_at", "id")


# ═══════════════════════════════════════════════════════════════════════════
# THE PAGE'S SHARED READS — asked ONCE for the whole page, never per row
# ═══════════════════════════════════════════════════════════════════════════


class PageContext:
    """Everything a page of bills needs that is not on the invoice row itself.

    ⚠ **IT EXISTS SO A THOUSAND-ROW PAGE IS NOT A THOUSAND ROUND TRIPS.** The
    PO set the page at 1,000 (*"make this as 1000 per page"*); the account
    name, the account's balance, what payments has allocated and the chart's
    code for each stamped GL account are four reads for the WHOLE page here and
    four reads PER BILL if `as_record` is left to resolve them itself. That is
    DEF-2723's shape — nine statements per row behind a 562 ms list — on a
    surface a partner pulls a month of at a time.

    `as_record` still works with no context at all: it builds one for the
    single bill it was handed. One composer, two callers, no second answer.
    """

    __slots__ = ("names", "balances", "allocated", "gl_codes")

    def __init__(
        self,
        *,
        names: dict[str, str | None],
        balances: dict[str, Any],
        allocated: dict[str, Decimal] | None,
        gl_codes: dict[str, str],
    ) -> None:
        self.names = names
        self.balances = balances
        self.allocated = allocated
        self.gl_codes = gl_codes


def _account_names(account_ids: list[str]) -> dict[str, str | None]:
    """The ACCOUNT's name, which is the primary contact's (PO 2026-09-16:
    *"Customers = accounts"* — `customer_name` is the ACCOUNT name).

    ⚠ **THE PUBLISHED BATCHED SELECTOR, NOT A SECOND DERIVATION.**
    `customers.selectors.primary_contact_names_for` is the one the accounts
    list's own Name column reads, ordering `-is_primary, created_at, id` — and
    its docstring records why that order is load-bearing: a batched read that
    sorted differently would quietly rename customers on one screen and not
    another. A private copy here would be free to disagree the first time
    either moved.

    ⚠ **NOT the customer ENTITY.** `customer_accounts` is N:M — a jointly-held
    account has more than one holder — so the entity answers *whose account is
    this* and not *what is this account called*. The PO asked for the account's
    name.
    """
    from apps.customers import selectors as customers_selectors

    if not account_ids:
        return {}
    return customers_selectors.primary_contact_names_for(account_ids)


def _balances(account_ids: list[str]) -> dict[str, Any]:
    """`amount` — what each account owes NOW, for the whole page at once."""
    from apps.billing import open_balance

    if not account_ids:
        return {}
    return open_balance.open_balances_for_accounts(account_ids)


def _allocated(invoice_ids: list[str]) -> dict[str, Decimal] | None:
    """What payments has allocated against each of these bills.

    `None` — not `{}` — when payments cannot be asked. Billing's own seam
    returns that, and the two answers are different facts: an empty map means
    *nothing has been paid*, and `None` means *we could not ask*. Collapsing
    them would publish `after_pay_outstanding` figures that silently ignore
    every payment ever made.
    """
    from apps.billing import payments_seam

    if not invoice_ids:
        return {}
    return payments_seam.allocated_for_invoices(invoice_ids)


def _gl_codes(account_ids: Any) -> dict[str, str]:
    """`{gl_account_id: code}` for every account these lines point at.

    `ledger.selectors.account_labels` is the published batched read — it
    includes DEACTIVATED accounts on purpose, because a bill posted last month
    to an account retired since still has to say where it went.
    """
    from apps.ledger import selectors as ledger_selectors

    wanted = [str(one) for one in account_ids if one]
    if not wanted:
        return {}
    return {
        key: str(value.get("code") or "")
        for key, value in ledger_selectors.account_labels(wanted).items()
        if value.get("code")
    }


def page_context(invoices: list[Any]) -> PageContext:
    """The four shared reads for ONE page of bills."""
    account_ids = sorted({str(one.account_id) for one in invoices})
    invoice_ids = [str(one.id) for one in invoices]
    gl_ids: set[str] = set()
    for invoice in invoices:
        for line in invoice.lines.all():
            if line.gl_account_id:
                gl_ids.add(str(line.gl_account_id))
    return PageContext(
        names=_account_names(account_ids),
        balances=_balances(account_ids),
        allocated=_allocated(invoice_ids),
        gl_codes=_gl_codes(gl_ids),
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE RECORD
# ═══════════════════════════════════════════════════════════════════════════


def _coded(code: Any, labels: dict[str, str]) -> dict[str, str] | None:
    """A coded field as `{code, label}`, which is how EVERY coded value leaves
    this surface (PO 2026-09-16: *"you ahve to extend the defination of codes
    so that partner can resolve all codes at there end"*).

    The words are `reference.py`'s own — the same map the reference endpoint
    publishes — so a partner that cached the document and a partner that reads
    the label off the payload can never be told two different things.
    """
    from apps.integrations import reference

    if code in (None, ""):
        return None
    return {"code": str(code), "label": labels.get(str(code)) or reference.derived_label(code)}


def _line_record(line: Any, context: PageContext) -> dict[str, Any]:
    """One line of a bill, with the account it posted to.

    ⚠ **`unit` TRAVELS WITH `quantity`, AND THE SUPPLIED DOCUMENT HAS NO SUCH
    FIELD.** CLAUDE.md hard rule 3 — *consumption is always stated with an
    explicit unit; never assume*. `4.000000` of something is not a consumption,
    and a partner's system that assumed gallons where we meant hundreds of
    cubic feet would be wrong by a factor of 748. The divergence from the
    document is deliberate and is recorded on the CR.
    """
    from apps.integrations import reference

    service = line.service
    return {
        "kind": _coded(line.kind, reference.LINE_KIND_LABELS),
        "service": (
            {"code": str(service.code), "label": str(service.name or service.code)}
            if service is not None
            else None
        ),
        "description": line.description,
        "quantity": None if line.quantity is None else str(line.quantity),
        "unit": line.unit,
        "amount": display_amount(line.amount),
        "accountString": context.gl_codes.get(str(line.gl_account_id)) if line.gl_account_id else None,
    }


def _stamped_balance_forward(invoice: Any) -> Decimal | None:
    """`before_pay_outstanding` — the account's balance AS AT THE BILL DATE.

    Read from the bill's own stamped block rather than recomputed, and that is
    the whole of the first clock: `balance_forward` is written at issue
    (BR-BIL-035) into `bill_payload`, which the immutability trigger freezes,
    so this is the figure PRINTED ON THE DOCUMENT the customer holds. A
    recomputation would drift away from it the moment anything else moved, and
    the partner and the customer would then be holding two different bills.

    `total_due − current_charges` rather than `previous_balance −
    payments_credits`: the same number by BR-BIL-035's own arithmetic, taken
    from the pair that FOOTS. `None` when the block is absent or its figures
    are (an unreachable seam stamps nulls), never `0.00`.
    """
    payload = invoice.bill_payload or {}
    block = payload.get("balance_forward") or {}
    total_due = block.get("total_due")
    current_charges = block.get("current_charges")
    if total_due in (None, "") or current_charges in (None, ""):
        return None
    try:
        return Decimal(str(total_due)) - Decimal(str(current_charges))
    except (ArithmeticError, ValueError):
        return None


def as_record(invoice: Any, context: PageContext | None = None) -> dict[str, Any]:
    """ONE bill, nested, with one row per line.

    `context` is the page's shared reads (`page_context`). Handed one, this
    composes; handed none, it builds one for this bill alone — so a caller with
    a single invoice and a caller with a thousand get the SAME record out of
    the SAME code, which is what stops a partner's month-end page and a
    one-bill spot check disagreeing.
    """
    from apps.integrations import reference

    if context is None:
        context = page_context([invoice])

    account = invoice.account
    account_key = str(invoice.account_id)
    lines = list(invoice.lines.all())

    before = _stamped_balance_forward(invoice)
    bill_amount = Decimal(str(invoice.total))
    allocated = context.allocated
    after: Decimal | None
    if before is None or allocated is None:
        # ⚠ NOT ZERO AND NOT `before + bill`. Either operand missing makes the
        # answer unknown, and a partner told a bill is fully outstanding when
        # it has been paid posts a receivable that is not there.
        after = None
    else:
        after = before + bill_amount - Decimal(str(allocated.get(str(invoice.id), 0)))

    position = context.balances.get(account_key)
    now = getattr(position, "open_balance", None) if position is not None else None

    replaced = invoice.corrects_invoice
    return {
        "id": invoice.invoice_no,
        "billDate": invoice.issued_at.date().isoformat() if invoice.issued_at else None,
        "consumer_no": account.account_no,
        "customer_name": context.names.get(account_key),
        "billType": _coded(invoice.bill_type, reference.BILL_TYPE_LABELS),
        # `CR-111-BRC04` · PO 2026-09-17: *"a) always \"Utility Billing\""*. See
        # `PROJECT_TYPE` — a fixed category on their side, never derived from
        # this bill's services, and the same on a one-service bill as on an
        # eleven-service one.
        #
        # ⚠ **THE SEAM AND NOT A SHAPE, BECAUSE IT IS A FACT AND NOT A NAME.**
        # `invoiceNo` is their spelling of `id` and is a SHAPE rename
        # (`shapes.INVOICE_CLOUD`); this is a value that was not in the record
        # before, and a shape may move a value and may never go and find one.
        "projectType": PROJECT_TYPE,
        "status": _coded(invoice.status, reference.INVOICE_STATUS_LABELS),
        # ⚠ **ALWAYS PRESENT, `null` WHEN THIS BILL REPLACES NOTHING — AND THE
        # PO'S DOCUMENT ANNOTATES IT *present only on a bill that replaces
        # one*.** The divergence is deliberate and is recorded on the CR: a
        # finance system pairing a correction cannot tell a key we OMITTED from
        # a bill that replaces nothing, and that is the same *missing versus
        # empty* confusion this surface answers `501` rather than `[]` to
        # avoid. The link is the REPLACEMENT's own column (`corrects_invoice`,
        # PO 2026-08-12 closing OQ-120) — an issued bill is immutable, so the
        # original cannot gain a pointer after the fact and the rebill learns
        # what it replaces at INSERT.
        "replaces": replaced.invoice_no if replaced is not None else None,
        "bill_amount": display_amount(bill_amount),
        "before_pay_outstanding": _maybe_amount(before),
        "after_pay_outstanding": _maybe_amount(after),
        "amount": _maybe_amount(now),
        "currency": invoice.currency,
        "lines": [_line_record(line, context) for line in lines],
    }


def records_for(invoices: list[Any]) -> list[dict[str, Any]]:
    """A whole page, with the four shared reads made once."""
    rows = list(invoices)
    if not rows:
        return []
    context = page_context(rows)
    return [as_record(one, context) for one in rows]


def page_queryset(*, since: date | None = None, until: date | None = None) -> Any:
    """`collectable` with the joins a nested record needs, so a page of 1,000
    bills is not 1,000 extra statements for the account, the replaced bill and
    each line's service."""
    return collectable(since=since, until=until).select_related(
        "account", "corrects_invoice"
    ).prefetch_related("lines__service")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-041@wave-S (EP-INT-11) · CR-110-BRC04 phase 2 wave 3
# generated: 2026-09-06 by the CR-069 wave S build lane (integrations half)
#            2026-09-16 extended to the nested bill by the CR-110 phase 2 lane C
# checklist: A✔ B=n/a(no screen — this is a partner payload) C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_041_partner_surface.py
#        pytest tests/test_cr110_phase2_bills_and_payments.py
# exceptions: no write path exists here by design (B2 §2) · reads customers,
#   ledger and billing's own payments seam by their PUBLISHED batched selectors
#   rather than through four one-function seam files — `reference.py` already
#   takes that posture for the same lookups, and lane B and lane D hold
#   `seams/customers.py` and `seams/ledger.py` open this hour (law 11)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
