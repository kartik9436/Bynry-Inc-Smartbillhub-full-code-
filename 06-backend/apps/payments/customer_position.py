# ── Trace ──────────────────────────────────────────────
# Story:    CR-059 CS-12 (task 49) — *"plus a customer roll-up read over CS-4's
#           open-bill position"*
#           Screens: S22 · S35 · P5 "Pay by customer" (CR-059 task 50 — ANOTHER
#           LANE; nothing here draws anything)
# Rules:    BR-PAY-1126 (one tender may settle several accounts of ONE customer)
#           · BR-CUS-054 (the customer entity and its N:M account link) ·
#           BR-PAY-001 (the staff allocation choices this list is aimed at) ·
#           BR-TEN-042 (one currency per utility) · BR-TEN-080 (storage 6 dp ·
#           API 4 dp · display 2 dp) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 2 (a decimal string beside its CHAR(3), never a float)
# Tests:    06-backend/tests/test_cr059_cs12_multi_account_tender.py
# Impacts:  apps/payments/tenders_api.customer_open_bills (its only caller) ·
#           apps/payments/open_bills.open_bill_position (the per-account read
#           this rolls up, and does not re-implement) · apps/payments/
#           tenders.record_multi_account_payment (what a clerk does with it)
# ───────────────────────────────────────────────────────
"""ONE CUSTOMER, EVERY PROPERTY THEY HOLD, AND WHAT EACH ONE OWES.

╔══════════════════════════════════════════════════════════════════════════╗
║  THIS IS THE LIST A CLERK AIMS ONE CHEQUE AT. Without it, "a customer    ║
║  with three properties hands over one cheque" is three separate searches ║
║  and a split done on paper.                                             ║
╚══════════════════════════════════════════════════════════════════════════╝

**NOTHING HERE COMPUTES MONEY.** `open_bills.open_bill_position` already answers
*what does this ACCOUNT still owe, bill by bill* — over `billing_seam.
open_invoices_for_account`, which did the whole subtraction — and this file calls
it once per account and adds the answers up. The allocator is untouched and no
frozen figure moves (CS-4: *"No money logic moves"*).

**THE ACCOUNT SET IS BR-CUS-054's LINK AND NOTHING WIDENS IT.** The customer is
named by the caller and `customer_account_ids` is the complete answer for that
customer. A shared surname or a shared address counts for nothing — the same
posture `transfer.py` takes for a credit transfer, and for the same reason:
money aimed at the wrong Patel is a wrong allocation nobody can see is wrong.

**A JOINTLY-HELD ACCOUNT APPEARS AT FULL VALUE**, exactly as it does on
`customers.selectors.customer_statement`, and this read does not apportion. Two
people holding one account each owe the whole of it.

────────────────────────────────────────────────────────────────────────────
WHAT IS SERVED, AND WHAT IS DELIBERATELY NOT
────────────────────────────────────────────────────────────────────────────
Per account: its number, its open bills (each with `total`, `amount_due`,
`allocated` and `open_balance` — CS-4's own four figures), and its `total_open`.
Across the customer: `total_open` summed over exactly the accounts listed below
it, so the header and the list can never disagree.

**THE RUNNING REMAINDER IS NOT HERE.** It is the cheque total minus what the
clerk has typed so far — a fact about a FORM, not about this customer — so it
belongs to the screen, exactly as CS-4 ruled for the single-account picker.

**AND NEITHER IS A SUGGESTED SPLIT.** CS-12 says the automatic version needs a
ruling — *whose property goes short when the cheque does not cover everything* —
and that manual entry against three visible bills sidesteps the question, which
is why it is the right version one. Serving a pre-filled split would be that
ruling made quietly by a read.

**MONEY IS SERVED AT 4 DECIMAL PLACES** — BR-TEN-080's middle boundary and hard
rule 2 as re-signed 2026-08-22 — as a decimal STRING beside its CHAR(3), never
as a float and never as cents.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.payments import open_bills
from apps.payments.exceptions import PaymentRuleError

FOUR_DP = Decimal("0.0001")
ZERO = Decimal("0")

CUSTOMER_EXISTS_READ = "customer_exists"
CUSTOMER_ACCOUNT_IDS_READ = "customer_account_ids"
CUSTOMER_DETAIL_READ = "customer_detail"


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(Decimal(value).quantize(FOUR_DP, rounding=ROUND_HALF_UP))


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    from apps.payments.billing_seam import _resolve as seam_resolve

    return seam_resolve(module, attribute, kind)


def customer_open_bill_position(*, customer_id: Any) -> dict[str, Any]:
    """Every account of one customer, and every open bill on each.

    The body `GET /customers/{id}/open-bills` serves. Nothing is written, no
    clock is read and no money is computed here.

    **A customer with nothing open answers `accounts: []`-shaped rows with
    `total_open` 0.0000**, which is a real measured fact and not an absence:
    this read looked, and nothing is owed. That matters because the money the
    clerk is holding will then carry as credit and the screen has to say so.

    ⚠ **AN ACCOUNT WITH NO OPEN BILL IS STILL LISTED**, unlike a settled BILL,
    which the seam drops. The two absences are different: a bill that owes
    nothing is a control that can only produce a refusal, while an account that
    owes nothing is a property the customer still holds and may still want money
    parked against — and hiding it would make the roll-up disagree with the
    customer's own statement.
    """
    exists = _resolve("customers", CUSTOMER_EXISTS_READ)
    accounts_of = _resolve("customers", CUSTOMER_ACCOUNT_IDS_READ, "service_request_service")
    detail = _resolve("customers", CUSTOMER_DETAIL_READ)
    if exists is None or accounts_of is None:  # pragma: no cover - customers publishes both
        raise PaymentRuleError(
            f"`apps.customers.selectors.{CUSTOMER_EXISTS_READ}` or "
            f"`apps.customers.service_request_service.{CUSTOMER_ACCOUNT_IDS_READ}` is not "
            "published on this deployment, so this module cannot tell which accounts a "
            "customer holds. Payments may not read customers' ORM directly (B1).",
            br_ref="BR-CUS-054",
        )
    if not exists(customer_id):
        # The same sentence and the same rule the RECORD call refuses by, so a
        # clerk cannot be shown a list for a customer the payment then bounces
        # off — `open_bills._account` keeps the same discipline one level down.
        raise PaymentRuleError(
            f"customer {customer_id!r} is not a customer of this tenant, so they hold no "
            "accounts to show (CLAUDE.md rule 1).",
            br_ref="BR-CUS-054",
        )

    rows: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    total_open = ZERO
    currencies: set[str] = set()
    for account_id in sorted(accounts_of(customer_id)):
        position = open_bills.open_bill_position(account_id=account_id)
        # The per-account read already reports its own gaps by code; they are
        # carried up rather than re-worded, so one problem code means one fact
        # however deep in the stack it was found.
        problems.extend(position.get("problems") or ())
        if position.get("currency"):
            currencies.add(str(position["currency"]))
        total_open += Decimal(position.get("total_open") or "0")
        rows.append(position)

    if len(currencies) > 1:
        # Hard rule 2's other half: the sum only means something when the parts
        # share a code. BR-TEN-042 locks a utility to ONE currency, so this is a
        # data fact somebody must see — never a conversion this read may make.
        problems.append(
            {
                "code": "customer_accounts_in_several_currencies",
                "br_ref": "BR-TEN-042",
                "detail": f"this customer's accounts carry {sorted(currencies)}. BR-TEN-042 "
                "locks a utility to one currency once a financial record exists, so the "
                "roll-up total is not stated: adding them would invent a rate. Each account "
                "is listed with its OWN code.",
            }
        )

    customer = detail(customer_id) if callable(detail) else None
    return {
        "customer": {
            # B14 rule 31 — the id is served because the record call names it,
            # and the SCREEN shows `customer_no` and `display_name`.
            "id": str(customer_id),
            "customer_no": (customer or {}).get("customer_no"),
            "display_name": (customer or {}).get("display_name"),
        },
        "accounts": rows,
        "account_count": len(rows),
        # Summed over exactly the accounts above, so the header a clerk reads
        # and the rows they type into cannot disagree. `None` rather than a
        # figure when the codes differ — see the problem above.
        "total_open": _money(total_open) if len(currencies) <= 1 else None,
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "problems": problems,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 CS-12 (12-governance/11-change-requests.md §8 CS-12 · §10 P5 · §11 task 49 · CS-4's open-bill read it rolls up)
# generated: 2026-09-03 by the CR-059 W9 multi-account/master-tender lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no UI — CR-059 task 50 owns P5) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · the cross-tenant refusal and the per-account roll-up were driven RED before being trusted green (hard-won law 7)
# exceptions: (1) NO SCREEN. CR-059 task 50 owns P5 "Pay by customer" and another
#         lane holds `07-frontend/src/features/payments/`. REPORTED (law 2).
#         (2) NO SUGGESTED SPLIT AND NO RUNNING REMAINDER. The first would be
#         CS-12's unruled shortfall order decided by a read; the second is a fact
#         about a form.
#         (3) AN ACCOUNT OWING NOTHING IS LISTED, while a bill owing nothing is
#         not — the two absences mean different things and the docstring says so.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
