# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (S22/S35 Record payment — the allocation choice a clerk
#           makes) · US-PAY-006 (allocation — the open bills a payment meets)
#           Screens: S22 · S35 (the bill picker and its running remainder) ·
#           S21 (Account detail, Bills tab)
# Change:   CR-059 CS-4, 2026-09-01 — *"Publish what each bill still owes"*.
#           Closing OQ-154, ruled by the PO on 2026-08-12 in the words
#           *"Build the open-balance read"*, option (a): `GET
#           /accounts/{id}/open-bills` on the payments surface.
# Rules:    BR-PAY-001 (the four staff allocation choices — `specific` and
#           `split` are the two this read exists to switch on) · BR-PAY-010
#           (oldest-invoice-first; the within-bill class order) · BR-PAY-038
#           (the fourth class, whose membership is tenant configuration) ·
#           BR-BIL-004 (an issued bill is immutable, so its total is a fact) ·
#           BR-TEN-042 (one currency per utility) · BR-TEN-080 (storage 6 dp ·
#           API 4 dp · display 2 dp) · BR-SHL-025 (a control a clerk cannot use
#           states WHY) · CLAUDE.md rule 1 (tenant scoping) · rule 2 (money is
#           a decimal string beside its CHAR(3), never a float and never cents)
# Tests:    06-backend/tests/test_cr059_cs4_open_bills.py
# Impacts:  apps/payments/api.account_open_bills (its only caller) ·
#           apps/payments/billing_seam.open_invoices_for_account (the read it
#           serves) · 07-frontend S22/S35 Record payment + S21 Bills tab
#           (CR-059 task 12 — the picker, the running remainder, and the
#           deletion of `payments.applyTo.pickerUnavailable`)
# ───────────────────────────────────────────────────────
"""WHAT EACH OPEN BILL OF ONE ACCOUNT STILL OWES.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE FIGURE THIS EXISTS FOR IS THE **OPEN** BALANCE, NOT THE ISSUED      ║
║  TOTAL. THEY ARE THE SAME NUMBER ONLY UNTIL SOMEBODY PAYS SOMETHING.    ║
╚══════════════════════════════════════════════════════════════════════════╝

Two of BR-PAY-001's four staff allocation choices — *"A specific bill"* and
*"Split across bills"* — have been CONFIRMED law, executed by
`apps/payments/allocation.py`, accepted by `POST /accounts/{id}/payments`, and
rendered DISABLED on both screens that offer them, since 2026-08-11. The engine
was never the gap. **The gap was that nothing served the list a clerk aims at.**

`GET /invoices?f.account_id=` could not stand in for it, and the repo's own
worked figure says why: **`BL-2608-018410` was issued at 247.87, a 200.00
payment left 47.87 outstanding (PE-2), and a picker built on the bill list would
have offered the clerk 247.87 as the figure to aim at.** Money aimed at 247.87
on a bill that owes 47.87 is a wrong allocation a clerk cannot see is wrong.

NOTHING HERE COMPUTES MONEY. `billing_seam.open_invoices_for_account` already
did the whole subtraction — billing owns what was BILLED, this module owns what
was ALLOCATED, and the seam is where the two meet (OQ-113). This file reshapes
that answer into a body and adds nothing to it. **The allocator is untouched and
no frozen figure moves** (CR-059 CS-4: *"No money logic moves"*).

────────────────────────────────────────────────────────────────────────────
WHAT IS SERVED, AND WHY EACH FIELD IS THERE RATHER THAN LEFT TO THE SCREEN
────────────────────────────────────────────────────────────────────────────
`total` · `allocated` · `open_balance` — all three, per bill. The picker reads
the third; **S21's Bills tab reads the first two beside it**, because *"issued
247.87 · still owes 47.87"* is the sentence that tab could not previously make
and CR-059 P1 asks for. Serving `allocated` means no screen subtracts money.

`total_open` and `bill_count` are the header P1 draws — *"owes 341.10 across 2
bills"* — summed over exactly the bills listed below them, so the header and the
list can never disagree. **The running remainder is NOT here**: it is what the
clerk has typed so far against what they are holding, which is a fact about a
form and not about this account.

`currency` rides on every amount and on the position (hard rule 2 — *"never
assumed"*). It is the BILL's own code, read along the same reviewed edge as the
total it belongs to, and the account's is served beside it. **A bill whose code
differs from the account's is REPORTED by name and never quietly summed**:
BR-TEN-042 locks a utility to one currency, so a mismatch is a fact somebody
must see, not a rounding decision this read may take.

`composition` is `null`, never `[]`. **Absence and "every class is settled" are
different facts** and only the first is true today — billing publishes no
kind→class map (OQ-128) and the tenant's fourth class lives unpublished in the
ledger (BR-PAY-038, OQ-129 for a part-paid bill). The seam says so on
`problems`; an empty list here would read as a breakdown that came back all
zeros, which is a claim about a customer's tax.

**MONEY IS SERVED AT 4 DECIMAL PLACES** — BR-TEN-080's middle boundary, and hard
rule 2 as re-signed 2026-08-22 (*"MOney 4 decimal, percentage 6 decimal, display
both 2 decimal"*). The column stores 6; `MoneyCell` displays 2; 4 is what
crosses the wire so no computed precision is lost in transit. Nothing here
rounds — `quantize` to 4 dp is the WIRE format, not B4's finalization, which
happened when the bill was issued.

────────────────────────────────────────────────────────────────────────────
⚠ THE FIGURE THIS READ USED TO GET WRONG — DEF-2416, FIXED 2026-09-01
────────────────────────────────────────────────────────────────────────────
Every balance below is **`amount_due − Σ allocations`**, and `amount_due` is what
the bill ASKS for. For an ordinary bill that is its total. For a BUDGET BILLING
bill it is the LEVEL: the PO ruled *"Level is due"* on 2026-08-11 (BR-BIL-072,
closing DEF-062) and billing publishes the answer as
`apps.billing.selectors.amount_due_for`, which the seam now calls per bill.

On the ❄️ WE-8 bill the two figures are **292.87** and **242.00**. This section
said *"NOT FIXED HERE"* until 2026-09-01, and until then a budget customer who
paid the 242.00 they were asked for was shown here as still owing **50.87** —
so the picker offered a clerk a bill nobody owed and the ladder chased them.

**BOTH FIGURES ARE SERVED, and that is not two answers to one question.** Each
row carries `total` (what the bill CHARGED, BR-BIL-004, the figure S21's Bills
tab shows), `amount_due` (what it ASKS for), `allocated` and `open_balance`, and
the arithmetic closes: `amount_due − allocated == open_balance`. They differ on
budget bills alone, they are equal everywhere else, and a screen that shows
"issued 292.87 · asks 242.00 · paid 242.00 · owes 0.00" is telling a customer
something true that it previously could not say at all.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any

from core import errors
from core import tenancy as core_tenancy

from apps.payments import billing_seam
from apps.payments.exceptions import PaymentRuleError

#: BR-TEN-080's API boundary: money crosses the wire at FOUR decimal places.
#: Storage stays at 6 (the column) and display is 2 (`MoneyCell`). This is a
#: WIRE format and not a rounding site — B4's finalization already happened when
#: the bill was issued (CLAUDE.md rule 2, PO re-sign 2026-08-22).
FOUR_DP = Decimal("0.0001")

ZERO = Decimal("0")

#: Customers' own published, tenant-scoped account read — resolved BY NAME at
#: call time (B1: cross-module reads via service functions only), the idiom
#: `services._account` and every seam in this module already use. Payments may
#: not touch customers' ORM.
CUSTOMERS_MODULE = "customers"
ACCOUNT_READ = "account_queryset"


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — no read is built without `app.tenant_id`.

    Refuses rather than defaulting, for `selectors._tenant_id`'s reason: on
    PostgreSQL RLS would block the read and on the SQLite developer tier it
    would answer for whichever tenant came first, and *"whichever database you
    happen to be running"* is not a security model.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _money(value: Decimal | None) -> str | None:
    """A stored amount as its 4 dp decimal STRING, or None.

    Money never travels as a number and never as cents (hard rule 2); it travels
    as a string beside its CHAR(3) code and the frontend renders it without
    parsing it back into a float.
    """
    if value is None:
        return None
    return str(Decimal(value).quantize(FOUR_DP, rounding=ROUND_HALF_UP))


def _account(account_id: Any) -> Any:
    """The account this position belongs to, through customers' own read.

    Tenant-scoped by customers' own code, so **an account id belonging to
    another tenant resolves to nothing and this read refuses without ever
    learning whether the id was real** (CLAUDE.md rule 1 / BR-TEN-003). On
    PostgreSQL RLS FORCE refuses it a second time, independently.

    It refuses by the SAME sentence and the same rule id that
    `POST /accounts/{id}/payments` refuses by, deliberately: the picker and the
    record call must agree on what an account is, or a clerk gets a list of
    bills for an account the payment then bounces off.

    **Its STATUS is never read** — BR-PAY-036: a payment is always accepted, so
    a closed account with an open bill still has an open bill.
    """
    if account_id is None:
        raise PaymentRuleError(
            "no account was named, so there is no bill position to read. Every open bill "
            "belongs to exactly one account (BR-PAY-022).",
            br_ref="BR-PAY-022",
        )
    try:
        target = import_module(f"apps.{CUSTOMERS_MODULE}.selectors")
    except ImportError:  # pragma: no cover - defensive
        target = None
    read = getattr(target, ACCOUNT_READ, None) if target is not None else None
    if not callable(read):  # pragma: no cover - customers publishes it
        raise PaymentRuleError(
            f"apps.{CUSTOMERS_MODULE}.selectors.{ACCOUNT_READ} is not published, so this "
            "bill position cannot be tied to an account. Payments may not read customers' "
            "ORM directly (B1).",
            br_ref="BR-PAY-022",
        )
    try:
        account = read().filter(pk=account_id).first()
    except (ValueError, TypeError):  # a malformed id is a caller mistake
        account = None
    if account is None:
        raise PaymentRuleError(
            f"account {account_id!r} is not an account of this tenant, so it has no open "
            "bills to show (CLAUDE.md rule 1).",
            br_ref="BR-PAY-022",
        )
    return account


def _bill_row(invoice: billing_seam.OpenInvoice) -> dict[str, Any]:
    """One row of the picker. Every key is a fact the seam already computed."""
    return {
        # B14 rule 31 — a database id is never the VISIBLE value of a field.
        # It is served because the `targets[]` the Record form posts back name
        # a bill, and the screen shows `number`.
        "invoice_id": str(invoice.invoice_id) if invoice.invoice_id is not None else None,
        "number": invoice.number,
        "issued_on": invoice.issued_on.isoformat() if invoice.issued_on is not None else None,
        # ⚠ **`DEF-PAY-6254`, 2026-09-23 — THE DAY IT WAS DUE.** Screen 7·2
        # draws a **DUE** column and an **AGE** beside it, and the debtor read
        # that feeds it could serve neither: `_rows_from_billing` has carried
        # `due_on` since `CR-059` CS-4 and `billing_seam.OpenInvoice` had no
        # field to copy it into, so it stopped at the seam.
        #
        # `null` is a MEASURED fact and NOT an absence — billing declares the
        # date nullable and `BR-PAY-032` refuses to age a bill nobody can place
        # in time. The screen draws a dash; it never draws a zero and it never
        # calls an undated bill *not due*.
        "due_on": invoice.due_on.isoformat() if invoice.due_on is not None else None,
        # BR-BIL-004 — what the bill CHARGED, immutable.
        "total": _money(invoice.total),
        # ⛔ DEF-2416 / BR-BIL-072 — what it ASKS for. Equal to `total` on every
        # bill that is not budget-billing; the LEVEL on one that is (WE-8:
        # 292.87 charged, 242.00 asked). `amount_due − allocated ==
        # open_balance`, so a screen showing all four never does arithmetic.
        "amount_due": _money(invoice.amount_due),
        "allocated": _money(invoice.allocated),
        "open_balance": _money(invoice.balance),
        "currency": invoice.currency,
        # null, never [] — see the module docstring. `problems` carries why.
        "composition": (
            [
                {"class": entry.line_class, "balance": _money(entry.balance)}
                for entry in invoice.composition
            ]
            if invoice.composition
            else None
        ),
    }


def open_bill_position(*, account_id: Any) -> dict[str, Any]:
    """Every bill of `account_id` that still owes money, oldest first.

    The body `GET /accounts/{id}/open-bills` serves. Nothing is written, no
    clock is read and no money is computed here.

    A settled bill is absent rather than listed at 0.00 — the seam drops it, for
    `allocation.py`'s own reason (*"a row means money moved"*), and a picker
    offering a bill that owes nothing is a control that can only produce a
    refusal.

    An account with nothing open answers `bills: []` with `total_open` **0.0000**
    and `bill_count` 0, which is a real measured fact and not an absence: this
    read looked, and there is nothing owed. That is the one place a zero is the
    honest answer, because the money the clerk is holding will carry as account
    credit and the screen has to say so.
    """
    _tenant_id()
    account = _account(account_id)
    account_currency = getattr(account, "currency", None) or None

    position = billing_seam.open_invoices_for_account(account.pk)
    problems: list[dict[str, Any]] = [dict(problem) for problem in position.problems]

    bills = [_bill_row(invoice) for invoice in position.invoices]
    total_open = sum((invoice.balance for invoice in position.invoices), ZERO)

    # Hard rule 2, the half that is easy to skip: the currency must be the SAME
    # one for the sum to mean anything. BR-TEN-042 locks a utility to one, so a
    # bill that disagrees is a fact somebody has to see rather than a rounding
    # decision this read may take on its own.
    mismatched = sorted(
        invoice.number
        for invoice in position.invoices
        if invoice.currency and account_currency and invoice.currency != account_currency
    )
    if mismatched:
        problems.append(
            {
                "code": "bill_currency_differs_from_account",
                "br_ref": "BR-TEN-042",
                "detail": f"bill(s) {mismatched} carry a currency the account does not hold "
                f"({account_currency!r}). BR-TEN-042 locks a utility to ONE currency once a "
                "financial record exists, so this is a data fact and not a conversion "
                "problem — every bill is listed with its OWN code and the total is stated in "
                "the account's, because payments converts nothing (CLAUDE.md rule 2).",
            }
        )
    unpriced = sorted(invoice.number for invoice in position.invoices if not invoice.currency)
    if unpriced:
        problems.append(
            {
                "code": "bill_states_no_currency",
                "br_ref": "BR-TEN-042",
                "detail": f"bill(s) {unpriced} state no CHAR(3) currency code, so their amounts "
                "are shown with the ACCOUNT's code and not with one of their own. Hard rule 2 "
                "requires a currency beside every amount; it is reported rather than filled in, "
                "because a code assumed here is exactly how a CAD balance is read as USD.",
            }
        )

    return {
        "account_id": str(account.pk),
        "account_no": getattr(account, "account_no", None),
        # BR-TEN-042: the account's own code, the same one `record_payment`
        # stamps on the payment the clerk is about to take — so the figures on
        # the picker and the payment it produces cannot be in two currencies.
        "currency": account_currency,
        "bills": bills,
        # CR-059 P1's header: "owes 341.10 across 2 bills". Summed over exactly
        # the rows above, so the header and the list can never disagree.
        "total_open": _money(total_open),
        "bill_count": len(bills),
        "problems": problems,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@08c9bfec · US-PAY-006@08c9bfec — CR-059 CS-4 (sha1[:8] of the four sources concatenated in order: 12-governance/11-change-requests.md §8 CS-4 + §10 P1 + §11 task 11 · 12-governance/01-open-questions.md OQ-154 (CLOSED, PO 2026-08-12) · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-001/010/012 · 04-docs/05-modules/08-payments/06-epics/EP-PAY-01-record-payments.md §3 TC-4 + §5)
# generated: 2026-09-01 by the CR-059 task 11 lane (CS-4 — the read OQ-154 ordered built)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_cr059_cs4_open_bills.py — the route-not-mounted case, the PE-2 open-vs-issued figure and the cross-tenant refusal were each driven RED before being trusted green (hard-won law 7)
# exceptions: (1) NO SCREEN IS BUILT HERE. CR-059 task 12 owns S22/S35's picker,
#         the running remainder and the deletion of the on-screen refusal text
#         (`payments.applyTo.pickerUnavailable`, rendered by
#         `paymentsShared.allocationChoiceReason` on BOTH PaymentsPage and
#         AccountActions). Until that lands the endpoint is live and the two
#         controls still render disabled — hard-won law 2 with the halves in
#         two lanes by design, and REPORTED so the second half is not lost.
#         (2) [AMENDED 2026-09-01] DEF-2416 is FIXED. This entry read *"every
#         balance served here is measured at `invoice.total` … Filed, not
#         fixed"*. Both seam reads now call billing's `selectors.amount_due_for`
#         (BR-BIL-072, *"Level is due"*), so a budget bill is measured at its
#         LEVEL — WE-8 asks 242.00 against a 292.87 total — and the row serves
#         BOTH figures: `total` is what the bill charged and `amount_due` is
#         what it asks for, with `amount_due − allocated == open_balance`. That
#         key is ADDITIVE and the route serves a plain body, so `openapi/schema
#         .json` describes no response properties and is unchanged by it.
#         (3) NO `composition` IS EVER SERVED TODAY and it is `null` rather than
#         `[]`, because absence and "all classes settled" are different facts
#         (OQ-128 · OQ-129 · BR-PAY-038). The seam's own problem code travels
#         with it.
#         (4) THE RUNNING REMAINDER IS NOT SERVED. It is the payment amount
#         minus what the clerk has typed so far — a fact about a form, not about
#         this account — so it belongs to the screen (CR-059 task 12).
#         (5) `06-backend/openapi/schema.json` IS REGENERATED AND CARRIES MORE
#         THAN THIS ROUTE — `tests/test_be11_openapi.py` TC-05 was ALREADY RED
#         at the pinned tip, because two `/customers` routes and two description
#         changes (`accounts/imports/template`, `transfers/commit`) were
#         committed without it. It was rebuilt in a CLEAN WORKTREE at the tip
#         with only this lane's three payments files copied in, so every entry
#         derives from COMMITTED code and no lane's in-flight work is published
#         (law 11 / DEF-168). TC-05 was red before and is green after.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
