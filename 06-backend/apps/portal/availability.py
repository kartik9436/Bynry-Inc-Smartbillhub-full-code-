# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-012 (EP-CWP-04) — can I get service here: availability, fees
#           and deposits, read publicly. Screens: CWP-008 (and CWP-009's
#           restatement of the same two figures)
# Rules:    BR-CWP-021 (⚠ availability names the SERVICES, never the current
#           occupier) · BR-CWP-026 (a public read may never change an account)
#           · US-CWP-012 TC-2 (an unknown address returns *a person will look
#           at it*, NEVER a refusal) · TC-4 (a service not carried reads NOT
#           HERE with no fee — not `$0.00`, which means free) · TC-6 (the
#           currently effective version) · CR-068 §2d (the portal computes no
#           money) · CLAUDE.md hard rule 2 (4 stored, 2 displayed)
#           · ⊕ PO 2026-10-30 ruling A (`DEF-CWP-10690`): an address — and
#           picked apartment — already in Premises is a MOVE-IN, occupied or
#           empty; new connection only where it is not in Premises (the
#           2026-09-23 / 2026-10-11 rulings the staff Approve window keeps)
# Tests:    06-backend/tests/test_us_cwp_012_availability.py TC-1..TC-6 ·
#           06-backend/tests/test_cr200_portal_address_suggestions.py T4
# Impacts:  apps/portal/guest_api.py (`availability`) ·
#           07-frontend/src/portal/guest/StartService.tsx
# ───────────────────────────────────────────────────────
"""`CWP-008`'s answer, assembled from four seam reads and NOTHING ELSE.

⚠ **THE ONE SENTENCE THIS FILE EXISTS TO PROTECT.** `US-CWP-012` TC-2:
*"An address matching no premises → **a person will look at it** and an *Apply*
route. ⚠ **Not a refusal and not an empty table**"*. So there is no error path
in here at all: an address nobody recognises answers `200` with `matched:
false`, and the screen offers to apply anyway. A refusal would lose the
applicant at the first box, and the epic says why in as many words — *"they may
never become a customer if we refuse them."*

⚠ **AND THE FIELDS THAT ARE NOT HERE.** Nothing in the returned body names a
person, an account, a customer or an id of any of them (`BR-CWP-021`, B14 rule
31). ⚠ **AND SINCE 2026-10-30 NOT EVEN OCCUPANCY.** `job` said `move_in`
against `new_connection` by whether a live account held the address; PO ruling
A (*"A, move-in"*, `DEF-CWP-10690`) made it PRESENCE in Premises instead — the
rule the staff Approve window already kept — so whether anybody lives there is
not read for a guest at all.

**Nor does the matched premises' id travel**, and that was a deliberate second
pass over this file: it is convenient to hand the browser the uuid so the
application step need not look it up again, and it would put a database id in
an anonymous stranger's network tab. The draft re-resolves the address
server-side instead (`applications.save_draft`), which costs one read and keeps
wave A's promise that *no id of any kind travels* true of the whole guest
surface rather than of one endpoint.

WHAT IT COSTS TO ASK (NFR-41). One scan of the tenant's premises for the
address, then the units at one premises, the service points at those units, the
plan's one-time charges and one deposit row: five reads, none of them growing
with how long the utility has been a customer of ours.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.portal import money, selectors
from apps.portal.seams import customers_seam, metering_seam, rating_seam, tenancy_seam

#: `US-CWP-012` TC-1's third bullet — *"about three working days"*. It is the
#: same number `US-CWP-013` TC-3 refuses a start date inside, and it lives here
#: once so the two can never drift apart.
WORKING_DAYS_TO_CONNECT = 3

#: Kept as the wire's other value: since ruling A (`DEF-CWP-10690`) the guest read never
#: answers it — an address not in Premises is `None`, *a person will look at it*.
JOB_NEW_CONNECTION = "new_connection"
JOB_MOVE_IN = "move_in"


def _service_rows(
    tenant_id: Any,
    *,
    carried: list[str],
    fees: dict[str, Decimal] | None,
    deposit_amount: Decimal | None,
) -> list[dict[str, Any]]:
    """One row per service THE UTILITY SELLS, in the order it lists them.

    Every enabled service appears, including the ones this address does not
    have: the wireframe's fourth row is *Electric · NOT HERE*, greyed, and an
    absent row would leave a visitor wondering whether we forgot to check.

    ⚠ **THE ORDER IS THE UTILITY'S OWN, NOT THE CATALOGUE'S**, and it is the
    same rule wave A settled for the front-page chips (decision log 2026-09-03,
    judgment 4): the wireframe draws *Water · Sewer · Trash · Electric*, which
    is neither the platform seed order nor alphabetical. It is the order the
    utility ticked its services in, stored in
    `portal_settings.front_page_service_ids`, and reading it here means one
    utility's pages agree with each other. Anything enabled but not on that list
    follows, in catalogue order, so nothing is lost by an unticked service.
    """
    rows: list[dict[str, Any]] = []
    for service in _in_the_utilitys_order(tenant_id):
        code = service["code"]
        available = code in carried
        if not available:
            # TC-4: not carried here → no fee and no deposit, and expressly NOT
            # `$0.00`, which is a utility saying it is free.
            to_connect: dict[str, Any] = money.nothing()
            deposit: dict[str, Any] = money.nothing()
        elif fees is None:
            # The plan is not effective today (TC-6) or the unit has none, so
            # there is no price to quote. A person looks at it.
            to_connect = money.nothing()
            deposit = money.nothing()
        else:
            fee = fees.get(code, fees.get("", None))
            to_connect = money.amount(fee) if fee is not None else money.included()
            deposit = (
                money.amount(deposit_amount)
                if deposit_amount is not None and code == _deposit_service(fees, carried)
                else money.nothing()
            )
        rows.append(
            {
                "service_code": code,
                "service_name": service["name"],
                "available": available,
                "to_connect": to_connect,
                "deposit": deposit,
            }
        )
    return rows


def _in_the_utilitys_order(tenant_id: Any) -> list[dict[str, Any]]:
    """The tenant's enabled services, ordered by its own front-page list."""
    services = tenancy_seam.enabled_services(tenant_id)
    listed = selectors.settings_view(tenant_id)["front_page_service_ids"] or []
    position = {str(one): index for index, one in enumerate(listed)}
    return sorted(services, key=lambda row: position.get(row["id"], len(position)))


def _deposit_service(fees: dict[str, Decimal], carried: list[str]) -> str | None:
    """Which row the deposit is drawn against.

    `plan_deposit_rules` is one amount PER PLAN and per class — not per service
    — and the wireframe puts the single figure on the first row that has a
    connection charge of its own (Water `$150.00`; Sewer and Trash `—`).
    Spreading one deposit across three rows would read as three deposits, and
    repeating it on each would read as `$450.00`.
    """
    for code in carried:
        if fees.get(code) is not None:
            return code
    return carried[0] if carried else None


def availability(
    tenant_id: Any,
    address: Any,
    *,
    city: Any = None,
    postal_code: Any = None,
    unit: Any = None,
    today: date | None = None,
) -> dict[str, Any]:
    """`GET /portal/public/premises/availability?address=…&city=…&postal_code=…`.

    ⊕ `DEF-CWP-9817` — step 1 asks a street, a town and a ZIP as the blueprint
    draws them (p31), and all three are matched through the staff side's own
    matcher (`metering_seam.find_premises_by_parts`). `address` alone, with no
    town and no ZIP, is matched the way it always was.

    Two shapes, both `200`:

      * **matched** — the four rows, the job, and the *IF YOU APPLY* figures;
      * **not matched** — `matched: false` and nothing else, which the screen
        draws as *a person will look at it* with the *Apply* route still open.

    ⊕ **`CR-200-BRC10` S8 — THE APARTMENT (PO 2026-10-29, 2A).** At a building
    with MORE THAN ONE live unit the answer carries `units` — the LABELS an
    applicant picks from, nothing else (`BR-CWP-021`, B14 rule 31) — and
    `unit`, the label `unit` (as picked or typed) means, or None. The rows, the
    plan and the fees are then THAT unit's. *Mine isn't listed* is *a person
    will look at it*, never a refusal (`US-CWP-012` TC-2).

    ⊕ **THE JOB — PO 2026-10-30, RULING A (`DEF-CWP-10690`).** *"A, move-in"*:
    an address — and picked apartment — already in Premises is a **move-in,
    occupied or empty**; a new connection only where the address is not in
    Premises (2026-09-23 / 2026-10-11, the rule the staff Approve window
    keeps). So a matched single-unit premises and a picked apartment both read
    `move_in` — `1408 Elm St` · `B` empty and `31 Palm Ct` empty included —
    and the figures are the MOVE-IN's (`rating_seam.move_in_fees`, the read the
    staff move-in's Fees table uses). Until an apartment is picked at a
    building with several, the job is None: the apartment may be one we do not
    hold, which is *a person will look at it*. The 2026-10-29 reading
    (*"B empty reads new_connection"*) is SUPERSEDED. Occupancy is not read.
    """
    on = today or date.today()
    typed = str(address or "").strip()
    premises = (
        metering_seam.find_premises_by_parts(tenant_id, typed, city=city, postal_code=postal_code)
        if typed
        else None
    )
    # 🔒 DEF-CUS-9819 — the application fee does not depend on the address,
    # so both shapes carry it: a figure (`$0.00` included) or `nothing()` when
    # the utility has marked no code.
    fee = rating_seam.application_fee(tenant_id)
    application_fee = money.amount(fee) if fee is not None else money.nothing()
    # 🔒 CR-191-BRC10 (PO 2026-10-23) — a fee above $0.00 is paid by card on
    # the last step, so the screen must know BEFORE it draws the button whether
    # this utility can take a card at all (`BR-CWP-056`: held WITH its reason).
    from apps.portal.seams import payments_seam

    card_payment_available = bool(
        fee is not None and fee > 0 and payments_seam.card_payments_available(tenant_id)
    )
    if premises is None:
        return {
            "matched": False,
            "application_fee": application_fee,
            "card_payment_available": card_payment_available,
            "address": typed,
            "job": None,
            # CR-200-BRC10 S8 — no building, so no apartments to pick from.
            "units": [],
            "unit": None,
            "rows": [],
            "if_you_apply": None,
            # ⚠ **`DEF-CWP-4930` — THE APPLICANT TICKS WHAT THEY NEED.** An
            # address nobody holds has no service points to read, so until
            # 2026-10-02 the draft carried NO services and its submit was
            # refused on a step the applicant was never shown — every
            # application for an address we do not hold, for ever, on the one
            # journey `EP-CWP-04` §1 says must stay open. So the utility's own
            # services are OFFERED, in its own order, as NAMES to tick: no
            # fee, no deposit and no *available* verdict, because nobody has
            # looked at the address yet and TC-2's *a person will look at it*
            # is still the whole answer about it.
            "offered": [
                {"service_code": service["code"], "service_name": service["name"]}
                for service in _in_the_utilitys_order(tenant_id)
            ],
        }
    units = metering_seam.units_at(tenant_id, premises["id"])
    # ⊕ CR-200-BRC10 S8 — the apartment, at a building with several.
    labels = metering_seam.unit_labels_to_choose(tenant_id, premises["id"])
    several = len(labels) > 1
    picked = (
        metering_seam.unit_matching_label(tenant_id, premises["id"], unit)
        if several and str(unit or "").strip()
        else None
    )
    if picked is not None:
        # Service is per unit (the drawing's UNIT NEEDED state), so the rows,
        # the plan and the fees are THAT unit's.
        units = [one for one in units if one["id"] == picked["id"]]
    unit_ids = [one["id"] for one in units]
    carried = metering_seam.service_codes_at(tenant_id, unit_ids)
    priced_unit = next((unit for unit in units if unit["rate_plan_id"]), None)
    plan_id = priced_unit["rate_plan_id"] if priced_unit is not None else None
    # ⊕ DEF-CWP-10690 — a matched address is a move-in, so it is quoted what a
    # move-in charges: the plan's move-in fees for a HOME (the class the
    # deposit below is already quoted for), sized by what is recorded here.
    fees = rating_seam.move_in_fees(
        tenant_id,
        plan_id,
        on=on,
        customer_class=customers_seam.home_account_type_code(),
        services=carried,
        size_by_service=metering_seam.connection_sizes(
            tenant_id, priced_unit["id"] if priced_unit is not None else None, carried
        ),
    )
    deposit_amount = rating_seam.deposit(
        tenant_id, plan_id, customers_seam.home_account_type_id()
    )
    # ⊕ DEF-CWP-10690 (PO ruling A) — PRESENCE in Premises decides, never
    # occupancy. A building with several units waits for the apartment: one
    # we do not hold is *a person will look at it*, not a move-in.
    job: str | None = None if several and picked is None else JOB_MOVE_IN
    rows = _service_rows(
        tenant_id, carried=carried, fees=fees, deposit_amount=deposit_amount
    )
    before_we_start = sum(
        (Decimal(row["to_connect"]["amount"]) for row in rows if row["to_connect"]["amount"]),
        Decimal("0"),
    )
    on_first_bill = next(
        (Decimal(row["deposit"]["amount"]) for row in rows if row["deposit"]["amount"]), None
    )
    return {
        "matched": True,
        "application_fee": application_fee,
        "card_payment_available": card_payment_available,
        # A held address decides its own services — there is nothing to tick
        # (`DEF-CWP-4930`'s other half: the list is empty, never absent).
        "offered": [],
        # The address AS WE HOLD IT, so an applicant sees which one we matched
        # — in the one US form every later step uses (`DEF-CWP-9817`).
        "address": selectors.us_address_line(
            premises["address_line"],
            None,
            premises["city"],
            premises["state"],
            premises["postal_code"],
        ),
        # ⚠ ONE BOOLEAN'S WORTH OF OCCUPANCY, AND NO OCCUPIER (BR-CWP-021).
        "job": job,
        # ⊕ CR-200-BRC10 S8 — labels only, and only where there is a choice.
        "units": labels if several else [],
        "unit": picked["label"] if picked is not None else None,
        "rows": rows,
        "if_you_apply": {
            "before_we_start": money.amount(before_we_start),
            "on_first_bill": (
                money.amount(on_first_bill) if on_first_bill is not None else money.nothing()
            ),
            "working_days": WORKING_DAYS_TO_CONNECT,
        },
    }
