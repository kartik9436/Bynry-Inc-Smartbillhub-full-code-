# ── Trace ──────────────────────────────────────────────
# Story:    CR-059 CS-27 (task 51) — *"A premises-scoped read: the units of a
#           premises, their occupying accounts and what each owes. An authority
#           resolver walking unit → premises → owner → master."*
#           Screens: S22 · S35 · S21 · P6 "Pay by premises" (CR-059 task 52 —
#           ANOTHER LANE; nothing here draws anything)
# Rules:    BR-PAY-1129 (a master may pay a bill on a unit of its own premises,
#           and the authority is recorded) · BR-PAY-1130 (the leftover is the
#           MASTER's credit, never a tenant's) · BR-CUS-068 (a master account
#           and its common-area coverage) · BR-CUS-171 (a master's children,
#           DERIVED from the premises and never stored) · BR-CUS-055 (occupancy
#           keys off the status BEHAVIOUR CLASS, never its label) ·
#           BR-TEN-042 (one currency per utility) · BR-TEN-080 (API 4 dp) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (a decimal string beside
#           its CHAR(3))
# Ruling:   PO 2026-09-01 — a master **may always** pay a unit's bill (*"anyone
#           may pay any bill; the tenant's agreement is not required"*), and
#           paying it **does** give the master sight of that bill including its
#           usage. So `may_pay` is a RELATIONSHIP answer, not a consent answer.
# Tests:    06-backend/tests/test_cr059_cs27_master_pays_units.py
# Impacts:  apps/payments/tenders_api.premises_payment_position (its only
#           caller) · apps/customers/selectors.premises_scope_for_account (the
#           published seam it reads — payments touches no customers table) ·
#           apps/payments/open_bills.open_bill_position (what each owes) ·
#           apps/payments/tenders.record_multi_account_payment (what a clerk
#           does with it, and the authority check it shares)
# ───────────────────────────────────────────────────────
"""ONE BUILDING, ITS UNITS, WHO OCCUPIES EACH, AND WHAT EACH OWES.

╔══════════════════════════════════════════════════════════════════════════╗
║  SUB-METERED BUILDINGS ARE THIS PRODUCT'S CORE MARKET AND A LANDLORD     ║
║  PAYING ONE CHEQUE FOR A BLOCK IS THE ORDINARY CASE THERE. Today it is   ║
║  *"four hand-typed payments on four strangers' accounts"* with nothing   ║
║  tying them together except the cheque number typed four times.          ║
╚══════════════════════════════════════════════════════════════════════════╝

**THIS IS NOT THE CUSTOMER ROLL-UP WITH A DIFFERENT ARGUMENT.** CS-27 is
explicit: *"CS-12 groups by CUSTOMER, and the customer link does not join a
landlord to their tenants. This groups by PREMISES — unit → premises → owner →
master — which is a different key and a different authority question."* The
landlord and the tenants are **different customers**, so no query in
`customer_position.py` can ever return this list.

────────────────────────────────────────────────────────────────────────────
THE THREE SHAPES PEOPLE MEAN BY "THE MASTER PAYS", AND WHICH ONE THIS IS
────────────────────────────────────────────────────────────────────────────
**A · the master's own bill** — the owner is billed for the hallway light and
the car-park meter. **This WORKS already** and always did: a master account is
an ordinary account marked `kind=master` holding service agreements over the
building's common-area units. *It is not a parent of the others.* Nothing here
changes it, and the master's own hallway bill appears in this read exactly as
any other account's does.

**B · the owner holds every unit account** — several accounts, several bills,
one cheque. **That is CS-12's problem and CS-12 covers it** — use
`customer_position.py` and the customer-scoped tender.

**C · the master pays its TENANTS' bills** — several accounts held by different
people, one cheque from a fourth. **This had NO CONCEPT AT ALL**, and it is what
this file and `tenders.py`'s premises scope build. ⚠ *Be careful: C looks like B
and behaves quite differently, because the landlord and the tenants are not the
same customer, so nothing joins their accounts, and the money is being paid by
somebody who does not hold them.*

────────────────────────────────────────────────────────────────────────────
`may_pay` IS A RELATIONSHIP ANSWER — PO RULING 2026-09-01, NOT A SIMPLIFICATION
────────────────────────────────────────────────────────────────────────────
CS-27 first drew a consent check. The PO ruled that a master **may always** pay
a unit's bill — *"anyone may pay any bill; the tenant's agreement is not
required"* — and that paying it **does** give the master sight of that bill,
including its usage. **So the authority check became: is this unit on this
master's premises?** That is simpler than first drawn, and it is a ruling rather
than a corner cut.

⚠ **AND IT IS OWED TO A PERSON.** A tenant's consumption becomes visible to
their landlord. CS-27: *"Tell the tenant it happens — at sign-up or on the bill
— so it is a policy rather than a discovery."* No screen in this lane; the fact
rides on `problems` so the surface that renders this list cannot silently drop
it, and it rides again on every tender recorded through this path.

────────────────────────────────────────────────────────────────────────────
WHERE THE MONEY LANDS IS NOT A MATTER OF TASTE — THREE SIGNED RULES FORCE IT
────────────────────────────────────────────────────────────────────────────
**Model 1 is correct** and it is what `tenders.py` writes: a real payment entry
on **each unit account**, allocated against that unit's bill and **annotated
with the payer**; the **master carries the TENDER record and NO payment entry**,
except for money deliberately parked as its own credit. CS-27 gives all three
reasons and they are repeated here because the next lane will otherwise
"simplify" the payment onto the master:

  (i) a payment row carries exactly **one mandatory account** and money meets a
      bill only through an **allocation against that bill's invoice**, so
      settling a unit's bill **requires** a payment row on the unit's account;
  (ii) a cleared payment credits accounts receivable and **the receivable being
      reduced is the UNIT's** — put the payment on the master and you credit a
      debt the master never had **while four bills stay open**;
  (iii) the master **genuinely does not owe this money** — no consolidated bill
      exists, so a payment there would **create a credit balance beside four
      unpaid bills.**

**Model 2** — bill the master and recharge the units — becomes right only if a
utility wants the landlord invoiced for the whole building. *That is
consolidated billing, a much larger change*: billing, delivery, taxes and the
plan snapshot all assume one bill per account. **Paying once and billing once
are separate builds, and only the first is cheap.**

**What each place then shows.** *The tenant's account* — a real payment entry
against their bill, annotated with who paid it, balance 0.00. *The master's
account* — the tender: the cheque, the date, the total and the list of what it
settled; **no payment entry and no balance change**. *The master, exception* —
one payment entry only for money deliberately left over, carried as the master's
own credit, because a leftover has to live somewhere and **the only lawful home
is the payer's account. It must never settle on a tenant's** (BR-PAY-1130).
*The deposit batch* — **nothing new**; the parts join the day's batch by tender
exactly as they do today.

**AND IF THE CHEQUE BOUNCES, THE TENANT IS CHASED — PO RULING 2026-09-01,
verbatim: *"If acocunt is will Utility , utility will chase it and apply
penalty"*.** The tenant's bill is simply unpaid again, the tenant's own account
walks the ladder, and the returned-cheque penalty applies to it. Nothing new is
built for that: a reversal already re-opens the bills at their ORIGINAL due
date. ⚠ **What that ruling does NOT settle is whether the master ALSO carries a
consequence** — it speaks to the tenant side only, and nothing here assumes an
answer.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from apps.payments import open_bills
from apps.payments.exceptions import PaymentRuleError

FOUR_DP = Decimal("0.0001")
ZERO = Decimal("0")

PREMISES_SCOPE_READ = "premises_scope_for_account"


def _money(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(Decimal(value).quantize(FOUR_DP, rounding=ROUND_HALF_UP))


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    from apps.payments.billing_seam import _resolve as seam_resolve

    return seam_resolve(module, attribute, kind)


def premises_payment_position(*, payer_account_id: Any) -> dict[str, Any]:
    """The building this master may pay for, unit by unit, with what each owes.

    The body `GET /accounts/{id}/premises-position` serves. Nothing is written,
    no clock is read and no money is computed here — `open_bills.
    open_bill_position` did the whole subtraction, once per account.

    **A unit with no occupying account is listed with `accounts: []`.** That is a
    real measured fact and CS-27's own case B: an empty flat is on the OWNER's
    own bill (BR-CUS-170), not on nobody's, so hiding it would make the building
    look smaller than it is.

    **The master's own position is served beside the units**, because its hallway
    bill is an ordinary bill the same cheque may settle — CS-27's fixture has
    `ACC-9001` holding **69.60** (41.20 + 28.40) of its own — and a screen that
    could not show it would send the clerk to a second search for shape A.

    **`may_pay` is `true` for every listed unit account and for the master
    itself**, and it is served as a FIELD rather than left implicit because
    CS-27's S22/S35 asks for a *"may pay?"* column by name and because a control
    a clerk cannot use has to state WHY (BR-SHL-025). An account that may not be
    paid for is simply not in this list — the read is the authority.
    """
    read = _resolve("customers", PREMISES_SCOPE_READ)
    if read is None:  # pragma: no cover - customers publishes it
        raise PaymentRuleError(
            f"`apps.customers.selectors.{PREMISES_SCOPE_READ}` is not published on this "
            "deployment, so this module cannot tell which units belong to this master's "
            "premises. Payments may not read customers' or metering's tables directly (B1), "
            "and a payer who may not be checked is a payer who is refused.",
            br_ref="BR-PAY-1129",
        )
    scope = read(payer_account_id)
    if scope is None:
        # The SAME sentence and the same rule the RECORD call refuses by, on
        # purpose: the list a clerk aims at and the payment it produces must
        # agree on what a master is, or they get a building whose cheque bounces.
        raise PaymentRuleError(
            f"account {payer_account_id!r} is not a master account of this tenant, so it has "
            "no premises to pay for. An ordinary account pays its own bills; a landlord "
            "paying a block is a MASTER account holding the building's common areas "
            "(BR-CUS-068).",
            br_ref="BR-PAY-1129",
        )

    problems: list[dict[str, Any]] = [
        {
            "code": "master_can_see_the_units_bills",
            "br_ref": "BR-PAY-1129",
            "detail": "paying a unit's bill gives this master sight of that bill, including "
            "its usage (PO ruling 2026-09-01). CS-27 asks that the tenant be TOLD this "
            "happens — at sign-up or on the bill — so it is a policy rather than something "
            "they discover.",
        }
    ]

    positions: dict[str, dict[str, Any]] = {}
    currencies: set[str] = set()
    total_open = ZERO

    def position_for(account_id: str) -> dict[str, Any]:
        if account_id not in positions:
            positions[account_id] = open_bills.open_bill_position(account_id=account_id)
        return positions[account_id]

    units: list[dict[str, Any]] = []
    for unit in scope.get("units") or ():
        occupants = []
        for account in unit.get("accounts") or ():
            position = position_for(account["account_id"])
            problems.extend(position.get("problems") or ())
            if position.get("currency"):
                currencies.add(str(position["currency"]))
            total_open += Decimal(position.get("total_open") or "0")
            occupants.append(
                {
                    **account,
                    # PO ruling 2026-09-01 — a RELATIONSHIP answer. Everything in
                    # this list is on the master's premises, so everything in it
                    # may be paid for; the field exists because the screen draws
                    # the column and BR-SHL-025 forbids a silent control.
                    "may_pay": True,
                    "bills": position.get("bills") or [],
                    "total_open": position.get("total_open"),
                    "currency": position.get("currency"),
                }
            )
        units.append(
            {
                "unit_id": unit.get("unit_id"),
                "label": unit.get("label"),
                "premises_id": unit.get("premises_id"),
                "is_common_area": unit.get("is_common_area"),
                "accounts": occupants,
            }
        )

    # Shape A, beside shapes B and C — the master's OWN bill, which the same
    # cheque may lawfully settle and which is the one payment entry that belongs
    # on the master by right rather than by exception.
    payer_position = position_for(str(scope["payer_account_id"]))
    problems.extend(payer_position.get("problems") or ())
    if payer_position.get("currency"):
        currencies.add(str(payer_position["currency"]))

    if len(currencies) > 1:
        problems.append(
            {
                "code": "premises_accounts_in_several_currencies",
                "br_ref": "BR-TEN-042",
                "detail": f"the accounts on this premises carry {sorted(currencies)}. "
                "BR-TEN-042 locks a utility to one currency once a financial record exists, "
                "so the building total is not stated: adding them would invent a rate.",
            }
        )
    if not (scope.get("premises_ids") or ()):
        problems.append(
            {
                "code": "premises_names_no_owner",
                "br_ref": "BR-PAY-1129",
                "detail": "this master account is tied to no premises, so there is nobody it "
                "is authorised to pay for and every part of a premises cheque would be "
                "refused. The owner link is nullable and an unowned premises has nobody to "
                "authorise; declaring the owner on the premises is the fix.",
            }
        )

    return {
        "payer": {
            # B14 rule 31 — the id is served because the record call names it;
            # the SCREEN shows `account_no` and the payer's name.
            "id": str(scope["payer_account_id"]),
            "account_no": scope.get("payer_account_no"),
            "name": scope.get("payer_name"),
            # Shape A: what the landlord owes on their OWN account. Never summed
            # into the units' total below — the two are different people's money.
            "own_total_open": payer_position.get("total_open"),
            "own_bills": payer_position.get("bills") or [],
            "may_pay": True,
        },
        "premises_ids": scope.get("premises_ids") or [],
        "units": units,
        "unit_count": len(units),
        # Summed over exactly the UNIT accounts listed above and over nothing
        # else. The master's own 69.60 is deliberately NOT in it: it is the
        # landlord's own debt, and adding it would tell a clerk the tenants owe
        # more than they do.
        "units_total_open": _money(total_open) if len(currencies) <= 1 else None,
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "problems": problems,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 CS-27 (12-governance/11-change-requests.md §8 CS-27 · §10 P6 · §11 task 51 · decision log 2026-09-01 "a bounced landlord cheque is chased on the tenant's own account" · BR-CUS-068/170/171)
# generated: 2026-09-03 by the CR-059 W9 multi-account/master-tender lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no UI — CR-059 task 52 owns P6, S21's two sides, S33 grouping and S17 find-by-building) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · the not-a-master refusal, the unowned-premises problem and the units-vs-master total separation were each driven RED before being trusted green (hard-won law 7)
# exceptions: (1) NO SCREEN. CR-059 task 52 owns every CS-27 surface and another
#         lane holds `07-frontend/src/features/payments/`. REPORTED (law 2).
#         (2) `S17 · find the master BY BUILDING` IS NOT BUILT and is not this
#         file: it is a filter on the accounts LIST, which customers owns, and
#         CS-27 puts it in the same task 52 as the screens. REPORTED, not done.
#         (3) NO CONSOLIDATED BILL AND NO RECHARGE. That is CS-27's Model 2 and
#         its own sentence calls it *"a much larger change"* — billing, delivery,
#         taxes and the plan snapshot all assume one bill per account.
#         (4) WHETHER THE MASTER ALSO CARRIES A COLLECTION CONSEQUENCE WHEN ITS
#         CHEQUE BOUNCES IS NOT ANSWERED HERE. The PO ruled the TENANT side on
#         2026-09-01 and that ruling speaks to the tenant only; nothing in this
#         file assumes the other half.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
