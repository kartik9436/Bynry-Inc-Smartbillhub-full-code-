# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-002 (S15 units) · CR-024 (the move itself) · CR-089 wave J
#           Screens: S15 / PRM-01U row action · PRM-03 header action
# Rules:    BR-MET-095 (a unit MAY move, and the move is a DATED EVENT) ·
#           BR-MET-1161 (an address is stored on `premises` and NOWHERE else,
#           and every other entity derives it by walking there) · BR-MET-1162
#           (a unit may carry its own point; where it does not it uses its
#           building's) · BR-MET-082 clause 2 (grouping a premises groups every
#           unit in it — which is why a route follows a move) · B1/B8 (metering
#           never touches another module's ORM)
# Tests:    06-backend/tests/test_cr089_j_move_preview.py
# Impacts:  apps/metering/api.py (`GET /units/{id}/move-preview`) ·
#           apps/metering/derivation.py (`routes_if_moved`) ·
#           apps/metering/seams.py (`issued_bill_count_for_unit`) ·
#           07-frontend/src/features/metering/MoveUnitModal.tsx
# ───────────────────────────────────────────────────────
"""`GET /units/{id}/move-preview` — what moving this unit will actually do.

**WHY THIS READ EXISTS.** The move screen asked four things well — where the
unit is, where it is going, when, and why — and then described the consequence
in two sentences, one of which was about the ledger. `CR-089` `PUJ-46` rules
that it **itemises** what the move does, because two of the consequences reach
much further than the screen ever said:

  * **every asset tagged to the unit changes address.** An address is stored on
    `premises` and nowhere else (hard rule 8 / `BR-MET-1161`); an asset derives
    its own by walking unit → premises (`assets.selectors` serves it as
    `assigned_address`). So moving the unit re-addresses every meter, sub-meter,
    cart and fire line on it, silently, at the moment of the press. **The old
    screen mentioned none of this.**
  * **the route and the cycle change** — who reads the meter and when it bills.
    A unit takes its route from its building (`BR-MET-082` clause 2, and
    `derivation._resolve_one` says so in its own comment: a sibling's live pick
    *"is what carries a unit that has just been MOVED to a routed premises onto
    that premises' route with no cascade on the move path"*).

**NOTHING HERE IS COMPUTED ON THE CLIENT AND NOTHING HERE IS GUESSED.** Every
figure is read: the asset count from the assets module's own selector, the
accounts from customers', the routes from this module's derivation, the bill
count from billing — or, where a module cannot answer, `null`, which the screen
renders as a stated absence rather than a zero.

⛔ **IT WRITES NOTHING.** The move is `services.move_unit`, and every refusal
that matters — a future date, a missing reason, the same premise, a colliding
label, an un-acknowledged unit that has had accounts — is still the service's.
This read cannot approve a move and must never be mistaken for a check: a
preview that says *0 accounts* and a service that refuses on 2 is the service
that is right.
"""

from __future__ import annotations

from typing import Any

from . import derivation, seams, selectors


def _premises_brief(premises: Any) -> dict[str, Any]:
    """The building, named the way a clerk names it.

    `BR-MET-1161`: the address lives HERE, so this is the one place either side
    of the move reads it from. The town line is composed from the same three
    columns the property page composes it from — never stored twice.
    """
    locality = ", ".join(
        part
        for part in [
            premises.city,
            " ".join(part for part in [premises.state, premises.postal_code] if part).strip(),
        ]
        if part
    )
    return {
        "premises_id": str(premises.pk),
        "premise_no": premises.premise_no,
        "address_line": premises.address_line,
        "locality": locality or None,
        "has_point": premises.lat is not None and premises.lng is not None,
    }


def _route_side(found: Any) -> dict[str, Any] | None:
    if found is None:
        return None
    return {
        "route_code": found.route_code,
        "cycle_code": found.cycle_code,
        "basis": found.basis,
    }


def _routes_block(unit: Any, target: Any | None) -> list[dict[str, Any]]:
    """Every service this unit is read for, with the route on each side.

    ⚠ **A SERVICE APPEARS HERE EVEN WHEN ONE SIDE HAS NO ROUTE**, because *"it
    is on RT-012 today and on nothing at the destination"* is the consequence a
    clerk most needs to see and an entry that only listed matched pairs would
    drop it. `changes` is the honest comparison of the two sides, `null`
    included.
    """
    before = derivation.routes_for_unit(unit.pk)
    after = derivation.routes_if_moved(unit.pk, target.pk) if target is not None else {}
    rows: list[dict[str, Any]] = []
    for code in sorted(set(before) | set(after)):
        from_side = _route_side(before.get(code))
        to_side = _route_side(after.get(code))
        rows.append(
            {
                # ⛔ **THE CODE, AND NOT A NAME — `DEF-763`.** The front end owns
                # the ONE service-name catalogue (`rating.service.<code>`, with
                # the bare code as its default) and eleven catalogues carry it in
                # their own language. A `service_name` served from here would be
                # a twelfth answer in English, and it would cost
                # `seams.service_catalog()` — the S8 SCREEN read, 41 queries on
                # an empty tenant, whose own docstring asks callers not to.
                "service_code": code,
                "from": from_side,
                "to": to_side,
                # Compared on what a person READS — the route and cycle codes —
                # and not on the ids, so a route re-pointed at the same codes
                # does not report a change nobody can see.
                "changes": target is not None
                and (
                    (from_side or {}).get("route_code"),
                    (from_side or {}).get("cycle_code"),
                )
                != (
                    (to_side or {}).get("route_code"),
                    (to_side or {}).get("cycle_code"),
                ),
            }
        )
    return rows


def move_preview(unit_id: Any, premises_id: Any | None = None) -> dict[str, Any]:
    """The consequences of moving this unit, before anybody presses anything.

    404s through `selectors.unit_row` FIRST, and through `selectors.premises_row`
    for the destination, so an unknown or foreign id is a refusal rather than a
    preview full of absences that would read as *"this unit has no assets, no
    accounts and no route"* — three claims, none of them made.

    `premises_id` is OPTIONAL: without it the screen can still state what the
    move will carry (the assets, the accounts, the bills, the route it is on
    today), which is what it draws before a destination is chosen.

    ⚠ **A DESTINATION THAT IS THE UNIT'S CURRENT BUILDING IS NOT REFUSED HERE.**
    `services.move_unit` refuses it by name (`metering.unit.move_same_premises`)
    and that refusal is the guarantee; a read that raised as well would mean two
    places deciding one rule. The preview simply reports every side unchanged,
    which is the truth about that move.
    """
    unit = selectors.unit_row(unit_id)
    target = selectors.premises_row(premises_id) if premises_id else None

    assets = seams.assets_on_unit(unit.pk)
    occupying = seams.active_account_for_unit(unit.pk)
    point = selectors.unit_point(unit)

    return {
        "unit": {
            "id": str(unit.pk),
            "unit_no": unit.unit_no,
            "label": unit.label,
        },
        "from": _premises_brief(unit.premises),
        "to": _premises_brief(target) if target is not None else None,
        # BR-MET-1161's reach, and the one figure `PUJ-46` names in full: the
        # assets CURRENTLY tagged to this unit, each of which derives its address
        # from the building and therefore changes address with the unit.
        "assets": {"count": len(assets)},
        "routes": _routes_block(unit, target),
        "accounts": {
            # `account_reference_count` is EVERY account ever attached — the
            # figure `services.move_unit` refuses on — and the occupying account
            # is the one a clerk can name. Two different questions, both asked.
            "ever": seams.account_reference_count(unit.pk),
            "occupying": (
                {
                    "account_no": occupying.get("account_no"),
                    "customer_name": occupying.get("customer_name"),
                }
                if occupying
                else None
            ),
        },
        # ⚠ `null` IS *NOBODY COULD COUNT THEM*, NEVER *NONE* — `DEF-511`, and
        # the seam's own docstring carries the reason. The screen prints the
        # absence; it never prints a zero it was not given.
        "bills": {"count": seams.issued_bill_count_for_unit(unit.pk)},
        # BR-MET-1162: a unit with its OWN point keeps it and its pin does not
        # move; a unit reading its building's takes the destination's.
        "point": {
            "source": point.get("source"),
            "moves": point.get("source") != "unit",
        },
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-089 wave J (`PUJ-46`, `PUJ-47`, `PUJ-55`) · BR-MET-095 ·
#         BR-MET-1161 · BR-MET-1162 · BR-MET-082 clause 2 · DEF-511 ·
#         DEF-MET-4694
# generated: 2026-09-09 by the CR-089 wave J lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: E3 **THE BILL COUNT IS `null` UNTIL BILLING PUBLISHES ONE
#         FUNCTION** — `DEF-511` is still open and `apps/billing/selectors.py`
#         belongs to another lane this session. The seam is DECLARED and
#         resolves at call time, so the number appears the day that function
#         lands with no change here and none on the client; the test
#         `test_cr089_j_move_preview.py::test_bill_count_appears_the_day_billing_answers`
#         is the one that fires when it does.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
