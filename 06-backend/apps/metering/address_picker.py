# ── Trace ──────────────────────────────────────────────
# Change:  CR-094 capture wave, lane E — PO ruling 2026-09-15, *"if we have
#          unit or street address then we should take it from premises/Unit -
#          it means its a search and if not foudn them alow user to add them"*
#          Screens: REQ-03.3 capture step 3 (blueprint entry 06, p077)
# Rules:   CLAUDE.md hard rule 8 (an address is stored on `premises` and
#          NOWHERE else) · hard rule 1 (tenant scoping, RLS FORCE) ·
#          B14 rule 31 (no database id is ever a visible value) ·
#          NFR-3 (every list server-paginated) · NFR-5 (no hard caps)
# Tests:   06-backend/tests/test_cr094_lane_e_address_is_picked.py
# Impacts: apps/metering/api.py (`GET /premises/picker`) ·
#          apps/customers/service_request_service.py (the pick lands there)
# ───────────────────────────────────────────────────────
"""THE PREMISES REGISTER'S OWN SEARCH, FOR ANY SCREEN THAT PICKS AN ADDRESS.

WHY THIS IS A NEW READ AND NOT ONE OF THE TWO PICKERS WE ALREADY HAD
--------------------------------------------------------------------
Both were measured against what this step needs before a line was written
(`12-governance/02-decision-log.md`, 2026-09-15, lane E's build row):

  * **`GET /premises` — the S14 list.** Server-paginated, and it searches the
    address, the premise number and the city, which is most of the job. It
    **carries no units at all**, and this step picks a unit where there is one,
    so it cannot answer half the question. It also runs the S14 roll-up and two
    per-row counts that a type-ahead at a counter has no use for.
  * **`GET /routes/premises-picker`.** It *does* carry each premises' units —
    and it answers with a **plain list, never a page**. That is correct for
    building a route over 79 properties and it is `NFR-3` at a T5 tenant's
    40,000. Worse for this screen, every row carries the **meter count and the
    route badge**, and the same 2026-09-15 ruling says the meters and assets on
    a unit are the MOVE-IN request's, never this wizard's.

So neither was reused, and serving either would have broken a rule rather than
saved work.

WHAT IT SERVES, AND WHAT IT DELIBERATELY DOES NOT
--------------------------------------------------
Six fields of a premises and three of a unit. **No meter, no service point, no
asset, no account, anywhere in this payload** — PO 2026-09-15, verbatim: *"if
unit is found then it is gi=oing to be mobve in mostly and all asset - which we
will take acre in move in request"*. A clerk who needs to know what is on the
unit is raising a move-in, and that request is where those facts belong. **A
later lane adding them here is undoing a ruling, not filling a gap.**

`premise_no` and `unit_no` travel as the VISIBLE values (B14 rule 31); the
`id`s travel too, because a pick has to name a row, and they are never rendered.

PAGINATION IS IN SQL, NOT IN PYTHON
------------------------------------
`search()` returns a **QuerySet**, unevaluated, so `StandardPagination` slices
it with `LIMIT`/`OFFSET` and `count()` is one `COUNT(*)`. Metering's own
`_page` helper does `list(rows)` before paginating, which materialises every
row of the tenant — fine at 79 properties and 13× short of the top of T5, which
is what `DEF-PAY-4221` is about elsewhere in this repo. This read does not use
it. **The units are fetched for the PAGE only**, in one query keyed by the
premises on it, so the cost does not grow with the register.

`NFR-5`: there is no cap here, no `[:N]` slice and no maximum page. A caller
asking for page 400 of 40,000 gets page 400.
"""

from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from apps.metering import models
from apps.metering.selectors import _tenant_id, premises_word_match

#: The minimum a search term has to be before it narrows anything (IS-3, and
#: the same two characters `premises_list` and `units_list` already use). A
#: shorter term is ignored rather than refused — BR-SHL-011, a list URL never
#: 4xxs over its own params.
MIN_TERM = 2


def search(*, q: str | None = None) -> QuerySet:
    """Every premises this tenant holds, narrowed by `q`, newest-first-free.

    The term matches the **street line, the premise number and the town** —
    the three things a clerk reads off an applicant's utility bill — and,
    since `CR-200-BRC10`, the ZIP, the premises name and a unit's label, WORD
    BY WORD (each typed word must match one of them). It does
    NOT match the owner's name, which `premises_list` does: a clerk at this
    step is looking for a place, and an owner match would put *212 Balcones
    Drive* in the answer because somebody called Balcones owns a shop.

    Ordered by `premise_no` then `address_line` then `id` — a total order, so
    page 2 cannot repeat a row from page 1. Two properties may share a street
    line (a block with no unit numbers yet), which is why `id` is the last key.
    """
    # ⚠ **THE JOIN IS `DEF-CUS-6116`'s AND IT IS NOT A TIDY-UP.** `row()` serves
    # the premises TYPE's code, and an FK read per row on a page of 50 is 50
    # queries at a counter. One JOIN, no extra query, and `NFR-3`'s page is
    # still the page.
    qs = models.Premises.objects.filter(tenant_id=_tenant_id()).select_related("premises_type")
    term = (q or "").strip()
    if len(term) >= MIN_TERM:
        # `CR-200-BRC10` — the shared word-by-word premises match (street,
        # town, ZIP, premises number and name, or a unit inside it), so
        # "12 Oak 2B" finds 12 Oak St. The owner is still NOT matched, for the
        # reason in this docstring.
        qs = qs.filter(premises_word_match(term))
    return qs.order_by("premise_no", "address_line", "id")


def units_for(premises_ids: Any) -> dict[str, list[dict[str, Any]]]:
    """`{premises_id: [unit, …]}` for a whole PAGE — **one query, not one per
    premises.**

    Deleted units are left out: a clerk cannot pick one, and a picker that
    offers a row the write path refuses is worse than a shorter list.

    The order is `label`, which is what a clerk reads — *Unit 100, Unit 200,
    Unit 205* — with `unit_no` second so two units sharing a label (which the
    schema permits across a soft-delete) cannot swap places between pages.
    """
    ids = [str(p) for p in (premises_ids or []) if p]
    if not ids:
        return {}
    out: dict[str, list[dict[str, Any]]] = {pid: [] for pid in ids}
    rows = (
        models.Unit.objects.filter(
            tenant_id=_tenant_id(), premises_id__in=ids, deleted_at__isnull=True
        )
        .values("id", "premises_id", "unit_no", "label", "is_common_area")
        .order_by("label", "unit_no")
    )
    for row in rows:
        out[str(row["premises_id"])].append(
            {
                "id": str(row["id"]),
                # B14 rule 31 — this is the visible value, and it may be null
                # on a tenant that keeps no unit series. The label is then what
                # shows, which is what the S15 list already does.
                "unit_no": row["unit_no"],
                "label": row["label"],
                # A common area is a real unit and it is offered, because a
                # request against a building's common supply is a real request.
                # The screen marks it; nothing here hides it.
                "is_common_area": bool(row["is_common_area"]),
            }
        )
    return out


#: ══════════════════════════════════════════════════════════════════════════
#: **WHAT TRAVELS WITH AN ADDRESS — DECLARED, SO IT CAN BE ASSERTED**
#: ══════════════════════════════════════════════════════════════════════════
#:
#: ⚠ **A PICKED ADDRESS CARRIED FOUR FACTS AND LEFT A FIFTH BEHIND, TWICE, AND
#: BOTH TIMES EVERY TEST PASSED (`DEF-CUS-6057`, then `DEF-CUS-6116`).** The
#: first was the SERVICE LIST: picking an address copied street, town, state and
#: ZIP and not what that address offers, so a clerk's step-4 ticks were a local
#: fiction and every meter was refused at the last press. The second was the
#: PREMISE TYPE: town, state and postcode came back filled and the type came
#: back EMPTY, so the wizard re-asked a question the register had already
#: answered — **and a clerk may answer it differently from the record, which
#: puts two answers in the product for one fact.**
#:
#: ⚠ **NEITHER SIDE WAS WRONG, WHICH IS WHY NOTHING CAUGHT EITHER.** This file
#: served honest fields and the wizard copied honest fields; **nothing compared
#: the set that travels against what a `premises` row actually holds.** That is
#: the same hole `SignupWizard.test.tsx` fills by asserting ELEVEN services
#: rather than the ones it happens to render, and it is filled the same way:
#: name the set, and let a test hold it against the MODEL.
#:
#: Every name here is a concrete field on `metering.Premises`
#: (`test_def_cus_6116_the_picked_address_carries_its_type.py` asserts exactly
#: that), so a column renamed on the model fails loudly instead of quietly
#: ceasing to travel.
TRAVELS_WITH_AN_ADDRESS: tuple[str, ...] = (
    "address_line",
    "city",
    "state",
    "postal_code",
    # `DEF-CUS-6057` — what the STREET offers, read by step 4 to decide meters.
    "services_available",
    # `DEF-CUS-6116` — WHAT KIND OF PROPERTY IT IS. Served as the type's CODE,
    # which is the value the wizard's picker holds (B14 rule 31 — the uuid is
    # never the visible value and is not on this payload at all).
    "premises_type",
)


def row(premises: models.Premises, units: list[dict[str, Any]]) -> dict[str, Any]:
    """One answer row: where it is, what it is called, what services it offers,
    and what units it has.

    ⚠ **THE SET IT SERVES IS `TRAVELS_WITH_AN_ADDRESS` AND IT IS DECLARED
    ABOVE, NOT INFERRED FROM THIS FUNCTION'S BODY.** A test holds that tuple
    against `metering.Premises` itself, so a fact the register holds cannot
    quietly stop travelling — which it has now done twice (`DEF-CUS-6057`,
    `DEF-CUS-6116`) with every test on both sides green.

    The locality travels **with** the premises rather than being fetched again
    by the caller, for the reason `DEF-CUS-3653` records: the account header
    composed `Austin, TX 78704` out of a `customers.addresses` row, that row's
    kind was retired, and the line returned null on every account forever with
    `tsc` and every test green. There is one home for this and it is here.

    ── `services_available` — ADDED 2026-09-21, `DEF-CUS-6057` ───────────────
    ⚠ **WITHOUT IT, PICKING AN ADDRESS ALREADY ON FILE SILENTLY DISCARDED WHAT
    THAT ADDRESS OFFERS.** New Connect step 2 copies street, town, state and
    ZIP out of this row and had nothing to copy the service list from, so the
    clerk's step-4 ticks became a local fiction and **every meter on the build
    was refused at the last press**, after eight steps.

    ⚠ **IT IS NOT A METER, A SERVICE POINT, AN ASSET OR AN ACCOUNT, SO THE
    2026-09-15 RULING THIS FILE IS BUILT ON IS UNTOUCHED.** That ruling —
    *"if unit is found then it is gi=oing to be mobve in mostly and all asset -
    which we will take acre in move in request"* — keeps the EQUIPMENT standing
    on a unit out of this payload. `services_available` is a column on
    `premises`: what the STREET offers, the same class of fact as the address
    itself, travelling for the same reason (hard rule 8).

    ⚠ **`None` IS NOT `[]`, AND THE COLUMN IS SERVED RAW (`DEF-762`).** SQL
    NULL means *nobody has ever been asked about this address*; `[]` means *it
    offers nothing*. Collapsing them here would destroy the only signal that an
    address was never asked, so the caller decides what to do with each — the
    wizard writes the clerk's list only where there is an ANSWER to write.
    """
    return {
        "id": str(premises.id),
        "premise_no": premises.premise_no,
        "address_line": premises.address_line,
        "city": premises.city,
        "state": premises.state,
        "postal_code": premises.postal_code,
        "services_available": premises.services_available,
        # ── `DEF-CUS-6116` · THE KIND OF PROPERTY, AS ITS CODE ───────────────
        # ⚠ **`None` WHERE THE REGISTER HAS NO OPINION, AND THE COLUMN IS
        # NULLABLE ON PURPOSE.** A premises whose type was never set answers
        # `None`, and the wizard then asks — which is the right question over a
        # record that has no answer. Collapsing it to a default here would
        # write a guess onto a building.
        "premises_type": (
            premises.premises_type.code if premises.premises_type_id is not None else None
        ),
        "units": units,
    }


def page_rows(premises_page: Any) -> list[dict[str, Any]]:
    """Shape one PAGE of premises — the units are read for these rows only."""
    rows = list(premises_page or [])
    units = units_for([r.id for r in rows])
    return [row(r, units.get(str(r.id), [])) for r in rows]
