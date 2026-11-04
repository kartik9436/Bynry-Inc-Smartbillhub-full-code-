# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 4 · `P4.15` — *"a landlord sees their own
#           account only"*.  Screen: CWP-078 Property statement (390 · 1280).
# Change:   `CR-142-BRC07` `P4.15`, brief p016 (the task row) and p070–p071
#           (report `R24c` *Statement · by premises*), read as IMAGES, B14
#           rule 42.
# Rules:    **R24c LAW (ruled)**, verbatim: *"The master account is a row like
#           any other, marked, never merged. … This report crosses customers —
#           and that is now ruled. Staff see it as drawn. In the customer
#           portal a landlord sees **their own master account only**: the
#           $69.60, never Unit 3's $100.00 (`P4.15`)."* ·
#           BR-CWP-016 (PO 2026-09-04, *"(a) no"*) · BR-CWP-010 (the tenant AND
#           the account set, IN THE QUERY) · BR-CWP-041 (nothing above the
#           issued bill) · BR-CWP-047 (re-read, never cached) ·
#           BR-TEN-043 (no wall clock where a caller holds the date) ·
#           CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE) · hard rule 2
#           (4 dp stored, DISPLAY 2) · hard rule 8 (the address is WALKED to
#           `premises`; a unit refines it by LABEL) · NFR-3 (server pagination)
#           · NFR-5 (no hard caps) · B14 rule 31 (no database id on screen)
# Tests:    06-backend/tests/test_cr142_p4_15_premises_statement.py
#           10-scripts/rep_p4_15_landlord_rls_proof.py (real PostgreSQL 16)
# Impacts:  apps/portal/api.py
#           (`GET accounts/{id}/premises-statement`) ·
#           apps/portal/seams/ledger_seam.py (NEW — its only caller)
# ───────────────────────────────────────────────────────
"""THE PROPERTY STATEMENT, SCOPED TO WHAT THE SIGNED-IN PERSON HOLDS.

╔══════════════════════════════════════════════════════════════════════════╗
║  `R24c` AS STAFF SEE IT, from the brief's p070 — 1408 Elm Street:        ║
║                                                                          ║
║    100901  Unit 1   Okafor, D.    Regular   188.40  −188.40      0.00    ║
║    100902  Unit 2   Nwosu, A.     Regular   204.12     0.00    204.12    ║
║    100903  Unit 3   Baptiste, L.  Regular   196.00   −96.00    100.00    ║
║    100904  Unit 4   Alvarez, R.   Regular   212.40     0.00    212.40    ║
║    100900  Common   Elm St Hldgs  Master     69.60     0.00     69.60    ║
║                                  Total     870.52  −284.40    586.12    ║
║                                                                          ║
║  THE LANDLORD, IN THE PORTAL, SEES ONE ROW OF THAT FIVE: the `$69.60`.  ║
╚══════════════════════════════════════════════════════════════════════════╝

⚠ **THE SCOPING IS NOT A FILTER OVER THE STAFF REPORT, AND THAT DISTINCTION IS
THE WHOLE TASK.** The tempting build is *run `R24c`, then drop the rows that
are not yours*: five rows are fetched, four are discarded, and every figure the
landlord must never see has already been assembled in memory one serialiser
away from the wire. `BR-CWP-016` is not a display rule. So this module never
asks the question *what is at this premises* at all. It asks *which of MY
accounts are at this premises*, and the set it starts from is
`principal.account_ids` — the session's own, re-derived on this read
(`BR-CWP-047`). There is no widened query here for a screen state to reach.

⚠ **AND THE `COMMON AREAS` KPI IS THEIRS OR IT IS ABSENT.** On the staff
drawing that tile reads `$69.60` because the master account is in the report.
In the portal it reads `$69.60` when the signed-in person HOLDS the master, and
the tile is not drawn at all when they do not — never `$0.00`, which would be a
claim about the building's common charges and is a different sentence
(`BR-CWP-093`, *nothing empty ever appears*).

⚠ **`UNITS BILLED` IS NOT SERVED, DELIBERATELY.** p070's third KPI counts the
building's billed units — `4` — and it is the one figure on that drawing that
is a fact about OTHER customers rather than money belonging to them. A landlord
may well know how many flats they own; that is not the point. The point is that
this endpoint would be the product's only place a portal read counted rows it
had already been ruled out of seeing, and the next lane to add a second figure
beside it would have a precedent to cite. The absence is stated on the screen's
own docstring and in `CR-142-BRC07`, not left to be noticed.

⚠ **THE SUBJECT IS AN ACCOUNT THIS LOGIN HOLDS, NOT A PREMISES ID, AND THAT IS
WHAT KEEPS A UUID OUT OF THE BROWSER'S ADDRESS BAR.** `portalRoutes.tsx` reads
B14 rule 31 as reaching URLs — *"a database id in a URL is a database id on
screen"* — and a premises has no human reference a customer could quote the way
`BL-2608-0141` is printed on their bill. So the caller names an ACCOUNT, this
module walks it to its premises (hard rule 8), and the screen is served at
`/portal/property` with nothing in the path at all: the shell's switcher
already knows which account is being read, exactly as `CWP-065` does.

⚠ **AND IT CLOSES THE ENUMERATION HOLE FOR FREE, WHICH IS THE BETTER HALF.** A
premises-addressed route would take an id from the caller and have to prove
they hold something there. This one starts from an account the session's own
set already contains, so **there is no id a stranger could supply at all** — an
account not in the set is refused before any premises is resolved.

⚠ **AN ACCOUNT THIS LOGIN DOES NOT HOLD IS *NOT FOUND*, NEVER *FORBIDDEN*.**
`deny_as_not_found` is the portal's standing posture (`BR-CWP-010`): a 403 over
a real id and a 404 over an invented one are distinguishable, and the
difference is an oracle for *does this account exist on this utility*. Both
answer the same way here.

⚠ **THE CUSTOMER COLUMN OF THE DRAWING IS REPLACED BY `holding`, AND THAT IS A
JUDGMENT WITH A REASON.** p070 draws CUSTOMER because a staff reader is looking
across five customers. Every row here belongs to the signed-in person by
construction, so the column would repeat their own name down the page —
except for a DELEGATED account, where it would name the holder who invited
them. `source` (`holder` | `delegate`) is the fact that actually varies and the
one a helper needs, so the screen words that instead. Recorded in
`CR-142-BRC07` rather than inferred from the code.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Q

from core import errors

from apps.portal import paging
from apps.portal.seams import customers_seam, ledger_seam

ZERO = Decimal("0.0000")

#: `R24c` draws the master LAST, under the units it serves, and the drawing is
#: right: a common-area row read first invites the reading that it is the
#: building's total. `(is_master, unit_label)` sorts units by label and puts the
#: master after them, whatever it is called.
def _row_order(row: dict[str, Any]) -> tuple[int, str]:
    return (1 if row["is_master"] else 0, str(row.get("unit_label") or ""))


PREMISES_STATEMENT_SORTS: dict[str, Any] = {
    "unit": _row_order,
    "balance": lambda row: Decimal(row.get("closing") or ZERO),
}


def _premises_of(principal: Any, account_id: Any) -> Any:
    """Which premises an account this login HOLDS takes service at.

    ⚠ **THE ACCOUNT SET IS CHECKED HERE AND NOT BY THE CALLER**, so there is
    exactly one door. An account outside `principal.account_ids` never reaches
    the walk at all — it is refused as absent, which is the same answer an
    invented id gets.
    """
    from apps.customers import models as customers_models

    wanted = str(account_id)
    if wanted not in {str(one) for one in principal.account_ids}:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    row = (
        customers_models.Account.objects.filter(
            tenant_id=principal.tenant_id, pk=wanted
        )
        .select_related("unit")
        .only("id", "premises_id", "unit__premises_id")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found(br_ref="BR-CWP-010")
    premises_id = row.premises_id or getattr(row.unit, "premises_id", None)
    if premises_id is None:
        # An account with no address at all. Nothing to draw a property
        # statement about, and saying so as *absent* keeps the one refusal.
        raise errors.deny_as_not_found(br_ref="BR-MET-1161")
    return premises_id


def _accounts_here(principal: Any, premises_id: Any) -> list[Any]:
    """The signed-in person's OWN accounts at one premises — one query.

    ⚠ **BOTH HALVES ARE IN THE QUERY** (`BR-CWP-010`, `G96`): `tenant_id` and
    `pk__in=<the session's set>`. The suite runs on SQLite, which has no
    row-level security at all (hard-won law 14), so the database's guarantee is
    invisible to every test in this repo — the `pk__in` is what those tests can
    see, and `10-scripts/rep_p4_15_landlord_rls_proof.py` is what proves the
    other strand on real PostgreSQL.

    ⚠ **TWO SHAPES REACH ONE PREMISES** — an ordinary account hangs off a
    **unit**, and a master account over a building's common areas hangs off the
    **premises** itself (`customers_seam.account_premises_id` says so). Both are
    matched, because the master IS the landlord's row and missing it would
    answer the ruling's own worked example with nothing.
    """
    from apps.customers import models as customers_models

    held = [str(one) for one in principal.account_ids]
    if not held:
        return []
    return list(
        customers_models.Account.objects.filter(
            tenant_id=principal.tenant_id, pk__in=held
        )
        .filter(
            Q(premises_id=premises_id) | Q(unit__premises_id=premises_id)
        )
        .select_related("unit")
        .order_by("account_no")
    )


def _premises_address(tenant_id: Any, premises_id: Any) -> str | None:
    """`1408 Elm Street` — hard rule 8, walked, never stored on the account."""
    from apps.metering import models as metering_models

    row = (
        metering_models.Premises.objects.filter(tenant_id=tenant_id, pk=premises_id)
        .only("address_line")
        .first()
    )
    return getattr(row, "address_line", None)


def premises_statement(
    principal: Any, account_id: Any, *, start: date, end: date, params: Any = None
) -> tuple[dict[str, Any], int]:
    """`CWP-078` — one property, the window, and ONLY this login's accounts.

    `account_id` names an account the signed-in person HOLDS; the property is
    walked from it. See the module docstring for why the subject is an account
    rather than a premises.

    Answers `(body, count)` the way every other portal list does. `start` and
    `end` are PARAMETERS and never a clock read in here (`BR-TEN-043`).

    ⚠ **THE TOTALS ARE THE WHOLE SET'S AND NEVER THE PAGE'S**, which is
    `my_accounts_page`'s rule for the same reason (`BR-CWP-015`): a total that
    changed on page 2 is a figure a customer could reasonably believe and act
    on. The rows are a page; `totals` is every row they hold here.
    """
    if start > end:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="portal.statement.range_inverted",
            params={"from": str(start), "to": str(end)},
        )

    premises_id = _premises_of(principal, account_id)
    accounts = _accounts_here(principal, premises_id)
    if not accounts:  # pragma: no cover - the walk above guarantees one
        # Not 403. See the module docstring: a 403 over a real premises is an
        # oracle for whether that address exists on this utility.
        raise errors.deny_as_not_found(br_ref="BR-CWP-016")

    by_id = {str(account.pk): account for account in accounts}
    sources = {entry.account_id: entry.source for entry in principal.accounts}

    rows: list[dict[str, Any]] = []
    for account_id, account in by_id.items():
        figures = ledger_seam.window_totals(account_id, start=start, end=end)
        is_master = account.kind == customers_seam.ACCOUNT_KIND_MASTER
        rows.append(
            {
                #: B14 rule 31 — `id` is the ROUTE's value and never a visible
                #: field; `account_no` is what the screen prints.
                "id": account_id,
                "account_no": account.account_no,
                #: A unit refines a premises by LABEL (hard rule 8). A master
                #: has no unit, and the screen words that absence itself rather
                #: than the server shipping an English word for it (B14 r35).
                "unit_label": getattr(account.unit, "label", None),
                "is_master": is_master,
                "holding": sources.get(account_id, "holder"),
                "opening": str(figures["opening"]),
                "charges": str(figures["charges"]),
                "credits": str(figures["credits"]),
                "closing": str(figures["closing"]),
            }
        )

    rows.sort(key=_row_order)
    totals = {
        key: str(sum((Decimal(row[key]) for row in rows), ZERO))
        for key in ("charges", "credits", "closing")
    }
    #: THEIRS OR ABSENT — see the module docstring. `None` is *you hold no
    #: common-area account here*, which is not `$0.00`.
    common_areas = next(
        (row["closing"] for row in rows if row["is_master"]),
        None,
    )

    page, count = paging.on_the_server(
        rows, params, sorts=PREMISES_STATEMENT_SORTS
    ) if params is not None else (rows, len(rows))

    return (
        {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "address": _premises_address(principal.tenant_id, premises_id),
            "rows": page,
            "account_count": len(rows),
            "totals": totals,
            "common_areas": common_areas,
        },
        count,
    )


# gates: G81 (no write here) · G91 (no apps.identity) · G96 (both halves named)
# exceptions: `UNITS BILLED`, p070's third KPI, is NOT served — the module
#   docstring says why and CR-142-BRC07 records it. A stated absence, never a
#   silent one.
# status: VERIFIED-UNRATIFIED
