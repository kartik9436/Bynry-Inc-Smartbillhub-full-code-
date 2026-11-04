# ── Trace ──────────────────────────────────────────────
# Change:   CR-044 §4 — "reading open balance", the one piece of work four
#           surfaces need (04-docs/05-modules/07-billing/10-cr044-workflow-design.md)
#           Defect:   DEF-1081 (the bill run's step 2 cannot show what a
#           customer already owes, because nothing gathers it)
#           Screens:  S31 step 2 · S30 One-time bill · S30 Budget Bills ·
#                     S30 Fix a bill
# Rules:    BR-BIL-035 (previous balance − payments received + this period =
#           total due) · BR-BIL-160 (a migrated opening balance is part of the
#           previous balance, and so is what has been paid against it) ·
#           BR-PAY-041 (a negative credit position is a real DEBT) ·
#           BR-CUS-015 (`accounts.balance` is a CACHE — nothing here reads it) ·
#           B1 (no module computes another's half) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 2 (money, never float) · rule 4 (this WRITES NOTHING)
# Tests:    06-backend/tests/test_cr044_open_balance_reader.py
# Impacts:  apps/billing/runs.py (step 2 — DEF-1081) · apps/billing/one_time.py
#           (the preview) · apps/billing/budget_api.py (eligibility) ·
#           apps/billing/corrections_api.py (`the_customers_balance`)
# ───────────────────────────────────────────────────────
"""What an ACCOUNT already owes — the same figure the bill prints, asked earlier.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this reads a customer's money position and
four money surfaces will render it. AI-authored 2026-08-27 under the PO ruling
of 2026-08-09; its row is in `12-governance/09-human-review-ledger.md`.

════════════════════════════════════════════════════════════════════════════
THIS IS A READER, NOT A GATHER, AND THE DIFFERENCE IS THE WHOLE DESIGN
════════════════════════════════════════════════════════════════════════════
`payments_seam.prior_position_for_account` already computes this position and
already FOOTS by construction:

    previous_balance − payments_credits == open_balance

so `open_balance + this bill's current charges` is the total due however the
split is drawn, and a page can print all three with the arithmetic adding up.

**It had exactly ONE caller — `issue._stamp_balance_forward` — and it answers
about an INVOICE.** Its `totals_by_invoice_id` argument comes from
`_prior_bill_totals(invoice)`, which needs an invoice to exclude itself from.
Every surface that wants this figure has no invoice to ask about:

  * the bill run's **step 2** is a pre-flight over a cohort BEFORE any draft is
    reviewed — `DEF-1081`, whose own on-screen sentence reads *"What each
    customer already owes, and the late fees that would follow, are not gathered
    by the run yet — so nothing here would be a figure we could stand behind."*
  * the **One-time bill** preview prices nothing and writes nothing;
  * **budget-billing eligibility** is a question about an account;
  * a correction's **`the_customers_balance`** section is about the customer.

So this module changes the QUESTION and delegates the ARITHMETIC untouched. It
computes no money rule of its own, takes no rounding decision (B4 is ❄️ FROZEN
and a reader is not where one of its decisions is taken), and writes nothing at
all — there is no mutation entry point in this file.

════════════════════════════════════════════════════════════════════════════
WHY IT LIVES IN BILLING (B1, and it is not a preference)
════════════════════════════════════════════════════════════════════════════
Three modules own the three operands and none of them computes another's half:

    billing    Σ of the account's LOCKED bills at the totals they were issued
               with — billing's own immutable column, read from billing's own
               table. That is the half that crosses no boundary.
    payments   Σ of what has been allocated against those same bills, plus the
               account's credit position. `allocations` is payments' row and
               payments' arithmetic; asked for BY NAME through the seam.
    customers  the MIGRATED opening balance and how much of it is settled.
               Billing owns no opening bucket and computes none.

The four callers are billing's, the seam that already asks the other two is
billing's, so the reader is billing's.

⚠ **AND IT IS NOT `payments.outstandings`.** That module answers a different
question — *who owes, worst first, with ageing buckets* — over INVOICES only,
for S34's collections list. An account that arrived with a migrated balance and
has never been invoiced does not appear in it at all, and telling a clerk about
to bill that customer they are square is the defect BR-BIL-160 exists to stop.

════════════════════════════════════════════════════════════════════════════
`None` IS NOT `Decimal("0")`, ON EVERY FIELD, EVERY TIME
════════════════════════════════════════════════════════════════════════════
Zero means *this customer owes nothing from before*. None means *nobody could
ask*. Every one of the four surfaces renders `—` for the second and never
`0.00`, and the reason travels in `problems` so a screen never has to invent a
sentence for an absence it cannot explain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from core import errors, tenancy as core_tenancy

from apps.billing import customers_seam, models, payments_seam

#: WHICH WINDOW the two middle figures were read over — a VALUE and not a
#: comment, and deliberately the SAME constants `issue.py` stamps onto the
#: immutable bill. OQ-217 moved the definition on 2026-10-01; a figure on a
#: screen that cannot say which definition produced it is one nobody can
#: reconcile against the bill beside it.
#:
#: ⚠ **AMENDED 2026-10-01 — `OQ-217` CLOSED (PO, option A, BR-BIL-1065): the
#: WHOLE ACCOUNT SINCE THE LAST BILL**, the same as `issue.py`; the old window
#: is named only where payments cannot answer (`BALANCE_FORWARD_BASIS_FALLBACK`).
BALANCE_FORWARD_BASIS = "whole_account_since_last_bill"
BALANCE_FORWARD_BASIS_FALLBACK = "open_prior_bills_and_migrated_opening_at_issue"
BALANCE_FORWARD_BASIS_OQ = "OQ-217"


@dataclass(frozen=True)
class AccountOpenBalance:
    """What one account already owes, or why nobody could say.

    The four money fields are `Decimal | None` and the distinction is load
    bearing on every one of them — see the module docstring. `basis` says which
    window `previous_balance` and `payments_credits` were read over, because
    the definition has moved before (OQ-217, ruled 2026-10-01) and a later
    reader must be able to tell without dating the code.
    """

    account_id: str
    #: CLAUDE.md rule 2 — a money figure NEVER travels without its CHAR(3), so
    #: the currency comes with the amount rather than being looked up beside it.
    #: It is `None` only when neither owner has recorded one, which is an account
    #: with no locked bill and no migration — an account that owes nothing, where
    #: there is no figure to print a currency for. Nothing here invents one: a
    #: guessed currency on an arrears figure is a guess about what a customer
    #: pays in.
    currency: str | None = None
    previous_balance: Decimal | None = None
    payments_credits: Decimal | None = None
    open_balance: Decimal | None = None
    #: How many still-open earlier BILLS stand behind the figure. Not a money
    #: field: 0 with a non-zero `open_balance` is a real and readable state — a
    #: migrated account that has never been invoiced.
    bills: int = 0
    #: BR-BIL-160 — the MIGRATED half, carried separately so a reader can see
    #: how much of a balance came from a bill and how much the account arrived
    #: with. Both are already INSIDE the two figures above; they are not a fifth
    #: and sixth thing to add on.
    opening_balance: Decimal | None = None
    opening_settled: Decimal | None = None
    opening_buckets: int = 0
    basis: str = BALANCE_FORWARD_BASIS
    basis_oq: str = BALANCE_FORWARD_BASIS_OQ
    problems: tuple[dict[str, Any], ...] = field(default_factory=tuple)


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set.

    Refuse loudly rather than run an unscoped query and leave RLS as the only
    thing between one tenant's debts and another's. Same guard and same error as
    `apps/billing/selectors.py` and `apps/billing/issue.py`.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def locked_bill_totals_for_accounts(account_ids: Any) -> dict[str, dict[str, Decimal]]:
    """Billing's own half: every LOCKED bill of these accounts, at its issued total.

    `invoices.total` is immutable once issued (hard rule 4), so this is a fact
    rather than a recomputation — the same read `issue._prior_bill_totals` makes,
    widened from one account to a cohort and with no invoice to exclude.

    ⚠ **THE SET IS THE LOCKED STATUSES, WHICH IS WHY A DRAFT CANNOT COUNT.**
    Step 2 runs while this cycle's drafts already exist; if a draft were in the
    set, every account in the run would be overstated by exactly the bill it is
    about to be sent. Filtering by status is stronger than excluding by id and
    it cannot rot — it stays true when a caller forgets to pass an exclusion,
    which is the failure mode an id filter has and this does not.

    One query for the whole cohort. Returned as `{account_id: {invoice_id:
    total}}` because that is the shape the seam takes, per account.

    `DEF-BIL-8696` — `account_ids` may be a queryset of account ids, read as a
    subquery (a bill run's 40,000 accounts are never 40,000 bound parameters).
    """
    keys = [str(account_id) for account_id in account_ids]
    by_account: dict[str, dict[str, Decimal]] = {key: {} for key in keys}
    if not keys:
        return by_account
    rows = models.Invoice.objects.filter(
        tenant_id=_tenant_id(),
        account_id__in=account_ids if hasattr(account_ids, "query") else keys,
        status__in=models.INVOICE_LOCKED_STATUSES,
    ).values_list("account_id", "pk", "total")
    for account_id, invoice_id, total in rows:
        by_account.setdefault(str(account_id), {})[str(invoice_id)] = total
    return by_account


def plan_not_yet_due(
    split: dict[str, Any] | None, *, skipped: bool, stands: Decimal
) -> dict[str, Decimal] | None:
    """🔒 HUMAN-REVIEW-PENDING · BR-BIL-1061 (PO 2026-10-01), verbatim: *"A · Ask
    for new charges + this month's instalment: $62 + $45 = $107, with the rest of
    the plan shown as not yet due"* — the arithmetic over payments' split, pure.

    `split` is payments' `{"due_now", "not_yet_due"}` for an ACTIVE plan (None:
    no plan). A clerk's *Skip this month* (`skipped`) leaves this month's
    instalment not yet due too. Capped at what the account owes from before
    this bill (`stands`), so a plan can never turn a bill into a credit. None
    when nothing is held back. Worked: $270 at $45 × 6, the bill due before the
    second instalment, $62 of new charges → not yet due $225.00, due now
    $45.00, the bill asks $107.00.

    `DEF-BIL-8720` — Sign off reads this for every bill of a run, so its
    *Amount due* asks what the bills will ask. ⚠ It is the same six lines as
    `issue._plan_not_yet_due`'s tail, which still computes them itself: the Send
    lane holds `issue.py` today, so that function moves onto this one in a later
    change (`DEF-BIL-8720`'s close names it), and `tests/
    test_d8696_signoff_batched.py` asserts the two agree on a plan account."""
    if not split:
        return None
    later = Decimal(str(split.get("not_yet_due") or 0))
    now = Decimal(str(split.get("due_now") or 0))
    if skipped:
        later, now = later + now, Decimal("0")
    owed = stands if stands > 0 else Decimal("0")
    later = later if later < owed else owed
    if later <= 0:
        return None
    return {"not_yet_due": later, "due_now": now}


def _billed_currencies(account_ids: Any) -> dict[str, str]:
    """The CHAR(3) each account's locked bills were written in — billing's own column.

    Read separately from the totals because it is a different question with a
    different absence: an account may have no bill at all and still owe a
    migrated balance, and that figure's currency is CUSTOMERS' (it is on the
    opening bucket). Neither is guessed and neither falls back to the other's.
    """
    keys = [str(account_id) for account_id in account_ids]
    if not keys:
        return {}
    rows = (
        models.Invoice.objects.filter(
            tenant_id=_tenant_id(),
            account_id__in=keys,
            status__in=models.INVOICE_LOCKED_STATUSES,
        )
        .values_list("account_id", "currency")
        .distinct()
    )
    found: dict[str, str] = {}
    for account_id, currency in rows:
        if currency:
            # First one wins and a second is not merged. A single monthly figure
            # cannot be stated across two currencies (the same refusal
            # `budget_api.budget_eligibility` raises on a mixed-currency
            # history), and picking one would be this module choosing which of a
            # customer's currencies they owe in.
            found.setdefault(str(account_id), str(currency))
    return found


def payments_since(account_id: Any, *, exclude_invoice_id: Any = None) -> Any:
    """🔒 HUMAN-REVIEW-PENDING · OQ-217 (PO 2026-10-01) — the moment the account's
    LAST locked bill stopped counting payments: its stamped `payments_through`
    day (an *Apply next bill* bill, `DEF-BIL-8412`) or else the moment it was
    issued. None when the account has no locked bill — everything received
    counts. Billing's own rows; no clock is read (G6)."""
    from datetime import datetime

    from django.utils import timezone as dj_timezone

    rows = models.Invoice.objects.filter(
        tenant_id=_tenant_id(),
        account_id=account_id,
        status__in=models.INVOICE_LOCKED_STATUSES,
        issued_at__isnull=False,
    )
    if exclude_invoice_id is not None:
        rows = rows.exclude(pk=exclude_invoice_id)
    last = (
        rows.order_by("-issued_at", "-created_at").values_list("issued_at", "bill_payload").first()
    )
    if last is None:
        return None
    issued_at, payload = last
    through = ((payload or {}).get("balance_forward") or {}).get("payments_through")
    if not through:
        return issued_at
    try:
        day = datetime.fromisoformat(str(through)).date()
    except ValueError:
        return issued_at
    return dj_timezone.make_aware(datetime.combine(day, datetime.max.time()))


def payments_since_for_accounts(account_ids: Any, *, exclude_bill_run: Any = None) -> dict[str, Any]:
    """`payments_since` for MANY accounts — the same moment for each, in ONE
    query per 900 accounts whatever the run's size (`DEF-BIL-8682`, NFR-3).
    Every account asked about is a key; None where it has no locked bill.

    Each account's newest locked bill by a window (`ROW_NUMBER() OVER
    (PARTITION BY account ORDER BY issued_at DESC, created_at DESC)`), exactly
    the singular's `ORDER BY -issued_at, -created_at`, and of it only the
    `payments_through` stamp (one key of the payload, never all of it). `exclude_bill_run` is the
    singular's `exclude_invoice_id` for a whole run (one bill per account in
    a run): a run's own bill never counts as its "last bill", issued or not.

    🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8696` — `account_ids` may be a QUERYSET
    of account ids, read as a subquery in ONE pass: 40,000 ids bound as
    parameters cost seconds of Python before PostgreSQL sees the statement."""
    from datetime import datetime

    from django.db.models import F, Window
    from django.db.models.functions import RowNumber
    from django.utils import timezone as dj_timezone

    if hasattr(account_ids, "query"):
        keys = [str(account_id) for account_id in account_ids]
        chunks: list[Any] = [account_ids]
    else:
        keys = [str(account_id) for account_id in account_ids]
        chunks = [keys[start : start + 900] for start in range(0, len(keys), 900)]
    out: dict[str, Any] = {key: None for key in keys}
    tenant_id = _tenant_id()
    for chunk in chunks:
        locked = models.Invoice.objects.filter(
            tenant_id=tenant_id,
            account_id__in=chunk,
            status__in=models.INVOICE_LOCKED_STATUSES,
            issued_at__isnull=False,
        )
        if exclude_bill_run is not None:
            locked = locked.exclude(bill_run=exclude_bill_run)
        # Each account's newest locked bill — the singular's
        # `ORDER BY -issued_at, -created_at` LIMIT 1, per account, in ONE
        # statement (`DEF-BIL-8696`). It was a Max() and then an
        # `issued_at IN (…)` of every account's newest moment, which at a
        # second 40,000-bill month is 40,000 bound timestamps.
        newest = locked.annotate(
            _newest=Window(
                RowNumber(),
                partition_by=[F("account_id")],
                order_by=[F("issued_at").desc(), F("created_at").desc()],
            )
        ).filter(_newest=1)
        for account_id, issued_at, through in newest.values_list(
            "account_id", "issued_at", "bill_payload__balance_forward__payments_through"
        ):
            key = str(account_id)
            if key not in out:
                continue
            moment = issued_at
            if through:
                try:
                    day = datetime.fromisoformat(str(through)).date()
                    moment = dj_timezone.make_aware(datetime.combine(day, datetime.max.time()))
                except ValueError:
                    moment = issued_at
            out[key] = moment
    return out


#: `whole_account`'s "not handed in" — distinct from None, which is a real
#: answer (payments could not say).
_ASK = object()


def whole_account(
    account_id: Any,
    position: Any,
    *,
    since: Any,
    through_date: Any = None,
    credit: Any = _ASK,
    received: Any = _ASK,
    beyond: Any = _ASK,
) -> dict[str, Any] | None:
    """🔒 HUMAN-REVIEW-PENDING · **`OQ-217` CLOSED — THE WHOLE ACCOUNT SINCE THE
    LAST BILL** (PO 2026-10-01, option A; BR-BIL-1065). Verbatim: *"A · Show the
    whole account: last bill $34.00 − paid $120.00 + new charges $37.25 = $48.75
    credit, nothing to pay"*. ONE definition, read by the bill (`issue.py`) and
    by every screen that shows the figure the bill will print (this module).

      * **where the account stands** = what is still open (open earlier bills +
        unsettled migrated opening, `prior_position_for_account`) **minus** what
        the utility holds on account beyond what settled that opening (payments'
        SIGNED credit position — a negative one is a debt, BR-PAY-041, and adds);
      * **payments & credits** = everything received after `since` (and on or
        before `through_date`), refunds netted, allocated to a bill or not;
      * **previous balance** = where the account stands + what was received.

    `previous − payments + current = total due` is BR-BIL-035's arithmetic
    UNCHANGED; ❄️ WE-1 (one unpaid 45.00 bill, nothing received, no credit)
    still reads 45.00 − 0.00 + 247.87 = 292.87. Worked on the ruling: a $34.00
    bill, $120.00 paid → stands at −86.00; previous 34.00, payments 120.00; with
    $37.25 of new charges the total due is **−48.75 — a $48.75 credit**.

    With `through_date` (*Apply next bill*, `DEF-BIL-8412`), money posted after
    it is left out of the payments line AND added back to where the account
    stands, so this bill does not count it and the next one does.

    None when payments cannot answer any read — the caller keeps the old window
    and names it (`BALANCE_FORWARD_BASIS_FALLBACK`), never a guess.

    `DEF-BIL-8682` — `credit`, `received` and `beyond` (what was received after
    `through_date`) may be HANDED IN from payments' batched reads, so Sign off
    can read a whole run without a statement per account. The arithmetic below
    is the one statement of the rule either way.
    """
    if position.open_balance is None:
        return None
    if credit is _ASK:
        credit = payments_seam.credit_position_for_account(account_id)
    if credit is None:
        return None
    settled = position.opening_settled or Decimal("0")
    stands = position.open_balance - (credit - settled)
    if received is _ASK:
        received = payments_seam.payments_received_for_account(
            account_id, after=since, through_date=through_date
        )
    if received is None:
        return None
    if through_date is not None:
        if beyond is _ASK:
            everything = payments_seam.payments_received_for_account(account_id, after=since)
            beyond = None if everything is None else everything - received
        if beyond is None:
            return None
        stands = stands + beyond
    return {
        "previous_balance": stands + received,
        "payments_credits": received,
        "open_balance": stands,
        "payments_through": through_date.isoformat() if through_date is not None else None,
    }


def _position_from(
    account_id: Any, totals: dict[str, Decimal], billed_currency: str | None = None
) -> AccountOpenBalance:
    """The seam call, with the two figures billing does not own asked for by name."""
    key = str(account_id)
    # BR-BIL-160 — customers' figure, asked of customers. Handed IN rather than
    # resolved inside the payments seam so each seam keeps asking only the
    # module it names (the posture `issue.py` takes for the same call).
    opening = customers_seam.opening_position_for_account(account_id)
    position = payments_seam.prior_position_for_account(
        account_id,
        totals_by_invoice_id=totals,
        opening=opening,
    )
    # OQ-217 CLOSED (PO 2026-10-01) — the same whole-account window the bill
    # stamps, so a screen and the bill it previews cannot disagree.
    whole = whole_account(account_id, position, since=payments_since(account_id))
    return AccountOpenBalance(
        account_id=key,
        # The bill's currency first, because that is what the customer has been
        # ASKED in; the migrated bucket's second, for the account that has no
        # bill yet. Never a tenant default — see the field's own note.
        currency=billed_currency or opening.currency,
        previous_balance=whole["previous_balance"] if whole else position.previous_balance,
        payments_credits=whole["payments_credits"] if whole else position.payments_credits,
        open_balance=whole["open_balance"] if whole else position.open_balance,
        basis=BALANCE_FORWARD_BASIS if whole else BALANCE_FORWARD_BASIS_FALLBACK,
        bills=position.bills,
        opening_balance=position.opening_balance,
        opening_settled=position.opening_settled,
        opening_buckets=position.opening_buckets,
        problems=tuple(dict(entry) for entry in position.problems),
    )


def open_balance_for_account(account_id: Any) -> AccountOpenBalance:
    """What this ONE account already owes, before any bill of this cycle.

    ❄️ Worked on WE-1, the frozen example: one unpaid **45.00** prior bill with
    nothing paid against it gives **45.00 − 0.00 = 45.00**, so the bill that
    follows reads **45.00 − 0.00 + 247.87 = 292.87**. ❄️ Worked on GT-16's
    migrated `A-12103`: four bands **84.20 / 62.10 / 0.00 / 121.00** with no
    invoice anywhere give **267.30**, where an invoice-only read gives nothing.

    **The figure is identical to the one the bill will print**, because it is
    computed by the same seam from the same three operands. That is the point:
    a step-2 preview and the customer's own bill disagreeing about a debt is
    worse than step 2 showing nothing, which is the state DEF-1081 records.
    """
    key = str(account_id)
    totals = locked_bill_totals_for_accounts([key])
    return _position_from(account_id, totals.get(key, {}), _billed_currencies([key]).get(key))


def open_balances_for_accounts(account_ids: Any) -> dict[str, AccountOpenBalance]:
    """The same answer for a COHORT — DEF-1081's own shape.

    Step 2 is the pre-flight before 47 customers are billed, so the batch form is
    the one the run actually needs. Billing's half is ONE query for the whole
    cohort; the seam is then asked per account, because payments' and customers'
    reads are theirs and this module does not reach past them to batch what they
    have not published as a batch (B1 — a read that skipped the seam would be
    faster and would be billing computing payments' half).

    ⚠ **AN ACCOUNT WITH NOTHING OPEN IS ANSWERED, NOT OMITTED.** Every id asked
    about is a key in the answer. A caller that has to guess whether a missing
    key means *owes nothing* or *was not asked* will guess, and those two are the
    exact pair this module exists to keep apart.
    """
    keys = [str(account_id) for account_id in account_ids]
    totals = locked_bill_totals_for_accounts(keys)
    currencies = _billed_currencies(keys)
    return {
        key: _position_from(key, totals.get(key, {}), currencies.get(key)) for key in keys
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-044 §4 (04-docs/05-modules/07-billing/10-cr044-workflow-design.md) ·
#         DEF-1081 · BR-BIL-035 · BR-BIL-160 · BR-PAY-041 · B1 · ❄️ WE-1 · ❄️ GT-16
# generated: 2026-08-27 by the CR-044 lane (the three-workflow design pass)
# gates: RED PROVED FIRST — all six cases in tests/test_cr044_open_balance_reader.py
#        were run against a tree with no `apps/billing/open_balance.py` and errored
#        on the import; verbatim in the lane report
# exceptions: (1) THIS FILE WRITES NOTHING and has no mutation entry point — the
#             posture `apps/payments/outstandings.py` takes for the same reason
#             (2) it computes NO money rule: the arithmetic is delegated to
#             `payments_seam.prior_position_for_account` unchanged, so the figure
#             on a screen and the figure on the bill cannot diverge
#             (3) `BALANCE_FORWARD_BASIS` is RESTATED rather than imported from
#             `issue.py`: issue is a write path inside a transaction and importing
#             it into a read module to borrow two strings would couple a preview to
#             the issuing pipeline. The constants are asserted equal in the tests
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
