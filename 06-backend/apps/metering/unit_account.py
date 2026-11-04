# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-002 (S15 unit detail — the Account tab) · CR-089 wave I
#           Screens: S15 (PRM-03, Account tab)
# Rules:    BR-MET-036 (occupancy DERIVED from the occupying account) ·
#           BR-MET-094 (a vacant unit IS billed — the base charges go to the
#           owner) · BR-CUS-068 (the master account is the owner's account) ·
#           BR-CUS-039 (a protection forbids disconnection) · B1/B8 (metering
#           never touches another module's ORM)
# Tests:    06-backend/tests/test_cr089_i_unit_account_facts.py
# Impacts:  apps/metering/api.py (`GET /units/{id}/account`) ·
#           apps/metering/seams.py (`account_facts_for`) ·
#           07-frontend/src/features/metering/UnitDetailPage.tsx
# ───────────────────────────────────────────────────────
"""`GET /units/{id}/account` — the S15 Account tab's ONE read.

**WHY IT IS A NEW ROUTE AND NOT ANOTHER `GET /accounts?f.unit_id=`.**
The tab used to build itself from the accounts LIST, filtered to the unit, and
render the five fields a list row happens to carry. That is why `DEF-CUS-4691`
was possible: a protection, a note, a payment plan and a budget enrolment are
not columns on a list row, so no amount of reading the list would ever surface
one. This route asks the question the tab actually has — *what does a clerk
standing on this unit need to know before promising anything?* — and the answer
is assembled by the module that owns the rows.

**NOTHING HERE COMPUTES.** Every figure is forwarded from `apps/customers` at
the scale it is stored (hard rule 2 — 4 decimals stored, 2 displayed, rounded
once at display by `MoneyCell`). This module adds exactly three facts of its
own: the unit's number, its label, and whether it is a **common area** — and
that last one changes what the screen may offer, because a common area is
always the owner's and there is no tenant to move out.
"""

from __future__ import annotations

from typing import Any

from . import seams, selectors

#: Why the tab has no account to draw. Three DIFFERENT sentences, and telling
#: them apart is the whole of `CR-089`'s vacant-unit rule — an empty table says
#: none of them.
NO_ACCOUNT_VACANT = "vacant"  # nobody occupies it; the owner is billed the base
NO_ACCOUNT_COMMON_AREA = "common_area"  # never has a tenant; always the owner's
CUSTOMERS_CANNOT_ANSWER = "customers_cannot_answer"  # the module is unwired


def unit_account(unit_id: Any) -> dict[str, Any]:
    """The Account tab for one unit.

    404s through `selectors.unit_row` FIRST, so an unknown or foreign unit is a
    refusal rather than a tab of absences that would read as *"this unit has no
    account and no protections and no notes"* — three claims, none of them made.

    ⚠ **`as_of` IS THE TENANT'S BUSINESS DATE, ASKED FOR ONCE AND PASSED DOWN**
    (`BR-TEN-043`, gate `G6`). Whether a medical certificate is in force today is
    a question about the utility's calendar, and a protection that expired
    yesterday in one time zone has not expired in another. `seams.tenant_today`
    is the only clock this module is allowed to read.

    ⚠ **WHEN CUSTOMERS CANNOT ANSWER THE TAB SAYS SO AND DRAWS NOTHING ELSE.**
    `facts_unavailable` is a code, never an empty payload: an unwired module and
    an account with nothing on it must not render the same, which is `DEF-127`
    one module over.
    """
    unit = selectors.unit_row(unit_id)
    common_area = bool(unit.is_common_area)
    block: dict[str, Any] = {
        "unit": {
            "id": str(unit.pk),
            "unit_no": unit.unit_no,
            "label": unit.label,
            # `CR-089`: a common area is always the owner's account and offers
            # no move-out. The screen keys off this, not off the unit TYPE
            # string, because `unit_type` may ALSO read `common_area` and two
            # spellings of one fact is how a screen ends up disagreeing with
            # itself (the column's own model comment says the same).
            "is_common_area": common_area,
        },
        "account": None,
        "facts": None,
        "owner_account": None,
        "no_account_reason": None,
        "facts_unavailable": None,
    }

    answer = seams.account_facts_for_unit(unit.pk, as_of=seams.tenant_today())
    if answer is None:
        block["facts_unavailable"] = CUSTOMERS_CANNOT_ANSWER
        return block

    block["account"] = answer.get("account")
    block["facts"] = answer.get("facts")
    block["owner_account"] = answer.get("owner_account")
    if block["account"] is None:
        # A common area is not *vacant* — nobody was ever going to live in the
        # laundry. Same absence, different sentence, and the screen must not
        # offer a move-out on one of them.
        block["no_account_reason"] = NO_ACCOUNT_COMMON_AREA if common_area else NO_ACCOUNT_VACANT
    return block


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-089 wave I (I1–I5) · DEF-CUS-4691 · PUJ-36..PUJ-40
# generated: 2026-09-08 by the CR-089 wave I build lane
# checklist: A✔ B=n/a C✔ D=n/a E✔(GET /units/{id}/account, read by UnitAccountTab) F✔ G✔ H=n/a
# gates: pytest 06-backend/tests/test_cr089_i_unit_account_facts.py · G6 (no wall clock — `seams.tenant_today`)
# exceptions: E3 this module computes NOTHING; every figure is customers' at the stored scale · E3 the occupying-account rule is customers' `occupying_accounts_for_unit` (status CLASS, BR-CUS-055) and not the front end's `closed_at IS NULL`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
