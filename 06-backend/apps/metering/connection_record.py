# ── Trace ──────────────────────────────────────────────
# Change:   CR-126-BRC07 · lane NCD-1 — ONE DOOR THAT SERVES THE WHOLE BUILD
#           RECORD. Blueprint `02 Accounts Menu Blueprint.pdf` pages 98-107,
#           RENDERED AS IMAGES and read that way (`B14` rule 42), never from
#           the text layer — which prints every digit on those pages as `&`.
# Screens:  the property's **Build tab**, as SECTIONS. `OQ-MET-12520` CLOSED
#           2026-09-21 on the PO's option C: *"The drawing isn't asking for a
#           duplicate; it's asking for completeness we don't have."* There is
#           NO separate build screen and this read does not enable one — see
#           §0 below, which is the first thing to read in this file.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — a cross-tenant read is a
#           404, never a 403) · hard rule 2 (money stored 4 dp, served as a
#           STRING, displayed 2) · hard rule 8 (an address lives on `premises`
#           and NOWHERE else — the nine-row premise block is WALKED) ·
#           `NFR-3` (every list is server-paginated; no unpaginated list, no
#           per-tenant cap) · `B14` rule 31 (no database id is the visible
#           value of a field) · `B1` (a neighbour's fact through a neighbour's
#           published selector, never its tables)
# Rulings:  PO 2026-09-21 (1) the request is PROVENANCE, never a dependency ·
#           (2) asset numbers at commit, install on WORK ORDER COMPLETION ·
#           (3) say `activate`, never `energise` · (4) one destination
# Tests:    06-backend/tests/test_cr126_build_record.py
# ───────────────────────────────────────────────────────
"""Everything the build record draws, in one call, keyed by the build.

════════════════════════════════════════════════════════════════════════════
0 · WHERE THIS IS CONSUMED, AND THE ONE THING IT MUST NOT BECOME
════════════════════════════════════════════════════════════════════════════
**THERE IS NO BUILD RECORD PAGE AND THIS READ DOES NOT CREATE ONE.** A New
Connect detail screen existed for about three weeks and was deleted under the
PO's ruling of 2026-09-04 — *"you are duplicating this; there is nothing called
as connections; Connection = Account only — you cannot have two different
screen"*. `ConnectionDetailPage.tsx` is gone and `/connections/:id` REDIRECTS
(`App.tsx`'s `BuildRedirect`). `OQ-MET-12520`, closed 2026-09-21, re-confirmed
that ruling and added what the blueprint was actually asking for: **the
property's Build tab gains what the six drawn tabs carry, AS SECTIONS.** Pages
100-107 stay the CONTENT contract; only their address and their tab strip are
superseded.

So this is an API read and not a page's data source in the old sense. It is
keyed by the BUILD because the build is the subject — a property can carry more
than one, and `CON-26-0129` at 500 Main St is a live example — and the Build tab
already holds each build's id from the list beside it. **`B14` rule 31 is
untouched by that**: what a clerk SEES is `CX-26-0007`, served here as
`connection_no`; the uuid never leaves the wire.

════════════════════════════════════════════════════════════════════════════
1 · ONE CALL FILLS THE WHOLE TAB, AND EVERY LIST IN IT IS STILL PAGINATED
════════════════════════════════════════════════════════════════════════════
The point of the ruling is that a clerk stops hopping between three places, so
**three round trips to fill one tab would be that problem wearing a different
hat.** One call therefore returns the header, the five tiles, all six section
BLOCKS, and **the first page of every list**.

`NFR-3` says every list is server-paginated and none may be unbounded, and a
build is not small: a 500-unit block on three services is 1,500 service rows
before a single work order. So each list carries its own `count`/`page`/`per`
and `?section=` + `?page=`/`?per=` pages ONE of them deeper without disturbing
the others.

⚠ **PAGING ONE SECTION RECOMPUTES THE WHOLE ENVELOPE, AND THAT IS ACCEPTED
RATHER THAN OVERLOOKED.** The cost is bounded by the BUILD and never by the
tenant, which is the property `NFR-5` and B6's design rule actually care about.
A per-section endpoint would have been cheaper on page 4 of the audit log and
would have re-created the three-round-trip problem on page 1 of everything.

⚠ **AND THE `connection_services` ROWS ARE READ TWICE, WHICH IS SAID HERE
RATHER THAN LEFT TO BE FOUND.** `connection_detail` reads them for its own
blocks and this function reads them again for the two tile figures that need
the ROWS and not the summary — *units activated* and *service points live*.
It is one extra query on a set bounded by the build, and it is the price of
REUSING that read instead of re-deriving its blocks here, which would be the
second derivation `DEF-127` is about. A claim of *one pass* would have been
hard-won law 1 in this file's own docstring.

════════════════════════════════════════════════════════════════════════════
2 · WHAT WAS ALREADY SERVED, AND WHAT THIS FILE ADDS
════════════════════════════════════════════════════════════════════════════
`connection_reads.connection_detail()` is a finished 26-block read with **zero
callers** — built for the screen that was then deleted. It is REUSED here
rather than re-implemented, for `DEF-127`'s reason: a second derivation of the
same figure agrees on the day it is written.

What it already answers and this file simply forwards: the connection number,
the request number, the applicant, the derived state, the mode, `waiting_on`,
the target date, the unit count, the order progress, the per-service blocks,
the unit rows, the assets, the quote total, the outstanding-work items, the
audit trail and the owner account number.

What is NEW here, and every one of them is DERIVED rather than stored:

  * **the header** — the owner's name, the four chips, the address line and the
    service tags, each walked to the record that owns it;
  * **the five tiles** — units · activated `3 of 7` · work orders (and how many
    done) · quoted · outstanding, with `8 of 20 service points live` as the
    activated tile's own sub-figure;
  * **`OWNER AND SCOPE · STEP 1`** — three columns new on `connections`
    (`metering/0058`) and two WALKED to the payer's customer record;
  * **`THE PREMISE · STEP 2`** — nine rows, every one of them walked to
    `premises`. **Not one is a column on the build** (hard rule 8);
  * **`WHERE IT CAME FROM`** — the request, WHO APPROVED IT (walked to
    `service_requests.decided_by`) and when, the created stamp, and the fee
    still outstanding ON THE REQUEST, which is a different figure from the
    build's own outstanding and is drawn in a different block;
  * **the money block and the charge table** — read off the bill the build
    actually raised, through `quote_invoice_id`.

════════════════════════════════════════════════════════════════════════════
3 · FIVE THINGS REPORTED AS HAVING NO SOURCE THAT TURNED OUT TO HAVE ONE
════════════════════════════════════════════════════════════════════════════
Measured against the code before any column was proposed, because the cheapest
column is the one nobody adds:

  * **the customer-class chip** (`Apartment block`) is `premises.premises_type`,
    and the drawing proves it — `THE PREMISE · STEP 2`'s first row is *Premise
    type · Apartment block*, the same two words as the chip;
  * **`Approved by`** is `service_requests.decided_by`, stamped by
    `service_request_service.approve` beside `decided_at`. It belongs to the
    provenance block and is legitimately absent on a build nobody approved;
  * **`Activated at`** is `connections.activated_at`, a column since W6, written
    by `refresh_connection_state()` the moment a build reaches `activated`;
  * **`Owner or developer`** is the payer account's customer name — p106 rules
    it there: *"the name belongs to the account that pays"*;
  * **`External system reference`** is that same customer's legacy id.

════════════════════════════════════════════════════════════════════════════
4 · THE PO's FOUR RULINGS OF 2026-09-21, AND WHERE EACH ONE LANDS HERE
════════════════════════════════════════════════════════════════════════════
**(1) THE REQUEST IS PROVENANCE, NEVER A DEPENDENCY.** *"this request is new
work and recognized seperately from applcaition and hence we should not make it
dependent on applciation #"*. Everything drawn under `WHERE IT CAME FROM` is
null on a build raised directly, and that is a complete answer rather than a
gap. **Nothing else on this payload reads the request at all** — the money
block hangs off `connections.quote_invoice_id`, which is the column
`metering/0058` adds precisely so a build can name its own bill without one.

⚠ **AND THE PRICING HALF OF THAT RULING IS NOT BUILT, WHICH THIS FILE REPORTS
AND DOES NOT FIX.** `_post_connection_quote`'s first test is still *does this
build have a service request*, and it answers a stated absence —
`no_quote_on_this_build` — for every build raised directly. So *"the build
prices ITSELF"* is a ruling the commit path does not yet obey. It is a WRITE
path and a money path; a read lane may not quietly change one, so the absence
travels on `unavailable` with the ruling named.

**(2) ASSET NUMBERS AT COMMIT; `install_date` ON WORK ORDER COMPLETION.** Read
only: the unit rows report each meter as the assets module holds it. The defect
is `DEF-AST-5443`, already OPEN, and this ruling ANSWERS its Fix column.

**(3) SAY `activate`.** No English is written on this payload at all — every
label is the front end's, in its eleven catalogues (`B14` rule 35), so the word
cannot be wrong here. The one place the server could have leaked it is a
`state` token, and those were already `activated`.

**(4) ONE DESTINATION.** §0.

════════════════════════════════════════════════════════════════════════════
5 · WHAT IS NULL ON PURPOSE, AND WHY NONE OF IT IS A ZERO
════════════════════════════════════════════════════════════════════════════
Every absence on this payload carries a CODE and the question or defect it
tracks, and none of them degrades to `0`, `"—"` or a guessed word. That is
`DEF-127`'s whole lesson and it bites hardest on the money block: an
`OUTSTANDING` tile that printed `$0.00` because nobody could be asked would tell
a clerk a debt had been settled.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from apps.metering import connection_messages as messages
from apps.metering import connection_reads as reads
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import selectors as metering_selectors
from apps.metering import seams
from core.pagination import DEFAULT_PAGE_SIZE, clamp_page_size

#: The sections the Build tab renders, in the order the blueprint draws its
#: tabs. `overview` is not among them because it is not a list: it is the
#: blocks every response carries.
#:
#: ⚠ **A NAME NOBODY RECOGNISES IS IGNORED, NEVER REFUSED** (`BR-SHL-011`:
#: a list URL can never 4xx over its own params). An unknown `section` pages
#: nothing deeper and every list comes back on page one, which is exactly what
#: the caller would have got by omitting it.
SECTIONS: tuple[str, ...] = (
    "units",
    "charges",
    "work_orders",
    "communication",
    "audit",
    "outstanding",
)

#: Why a drawn figure is null. CODES, never sentences — `B14` rule 32 keeps our
#: vocabulary off a clerk's screen and the front end renders each through its
#: own catalogues (rule 35).
ABSENCE_NO_BILL = "this_build_has_raised_no_bill"
ABSENCE_BILLING_UNPUBLISHED = "billing_publishes_no_invoice_read"
ABSENCE_SETTLEMENT_UNPUBLISHED = "payments_publishes_no_allocation_read"
ABSENCE_TENDER_NOT_PUBLISHED = "the_tender_and_clearing_date_are_not_published_here"
ABSENCE_DIRECT_BUILD_PRICES_NOTHING = "a_build_raised_directly_is_priced_by_nobody"
ABSENCE_NO_MESSAGE_CAN_BE_FILED = "the_platform_cannot_file_a_connection_message_yet"


def _page_of(
    rows: list[Any], *, page: Any, per: Any, paged: bool
) -> dict[str, Any]:
    """One list, server-sliced, in the four keys every list in this product uses.

    ⚠ **THE SLICE HAPPENS HERE AND NOT IN SQL, AND THAT IS A DELIBERATE
    NARROWING RATHER THAN AN OVERSIGHT.** Each row on these lists costs a
    derivation through `connections.py` or a neighbour's selector, so the rows
    are built for the build and then sliced — the same posture
    `connection_reads.list_connections` takes and states, one screen over. What
    makes it safe HERE is the bound: the set is one BUILD's rows, never the
    tenant's, so there is no unpaginated tenant-wide list anywhere on this
    payload and no per-tenant ceiling to remove when T4 arrives (`NFR-5`, B6).

    `page` and `per` come back as the values that were USED after clamping, so
    a caller that asked for `page=99&per=75` is told it got page 3 of 50-row
    pages rather than having to work it out (`BR-SHL-011`: clamp, never error).

    ⚠ **FOUR KEYS, AND THEY ARE DELIBERATELY NEITHER OF THIS PRODUCT'S TWO LIST
    CONVENTIONS — SAID OUT LOUD BECAUSE A THIRD SHAPE IS NORMALLY A DEFECT.**
    A list ENDPOINT answers `{count, next, previous, results}` (work, metering,
    rating, assets) or `{rows, page, per, total, pages}` (customers' four
    worklists), and `G114` exists because eleven hand copies of the first one
    drifted. **These are neither, because they are not endpoints.** They are
    SECTIONS of one document, and `next`/`previous` are ABSOLUTE URLS of a
    resource — a section has none. The caller re-asks the SAME door with
    `?section=<name>&page=<n>`, which it can build from the key it is already
    holding, so a URL here would be a second address for a page that has one.
    `count` and `results` are the DRF names and `page`/`per` are the two the
    caller passed back, which is the smallest honest set.

    ⚠ **`rows` IS NOT USED, AND THAT IS ON PURPOSE:** `G114` treats a `rows` +
    `per` pair in a front-end declaration as the signature of the defect it was
    written for, so naming this `rows` would put a real trip-wire in NCD-2's way
    for a shape that is not that defect.
    """
    size = clamp_page_size(per) if paged else DEFAULT_PAGE_SIZE
    total = len(rows)
    last = max(1, -(-total // size))
    try:
        wanted = int(str(page)) if paged else 1
    except (TypeError, ValueError):
        wanted = 1
    number = min(max(wanted, 1), last)
    start = (number - 1) * size
    return {
        "count": total,
        "page": number,
        "per": size,
        "results": rows[start : start + size],
    }


def _customer_of_account(account_id: Any) -> dict[str, Any] | None:
    """The payer's CUSTOMER record — the owner's name and their legacy id.

    ⚠ **TWO OF THE FIVE `OWNER AND SCOPE` ROWS ARE HERE AND NOT ON THE BUILD,
    AND THE DRAWING IS WHAT DECIDES THAT.** p106's *"changed on the screen that
    owns it"* table puts `Owner or developer` at *Account A-10088* with the
    reason *"the name belongs to the account that pays"*, and the external
    reference is the same party's legacy id (`customers.external_ref`,
    `BR-CUS-054`). A copy of either on `connections` would be a second name for
    one company, drifting from the day somebody corrects the account.

    `None` where the build names no payer — which is the state ALL nine builds
    in the demo tenant are in today, because the master-account door requires an
    identifier the wizard's owner block does not carry (`DEF-MET-5093`). The
    caller states the absence; it does not fall back to the applicant, because
    *who applied* and *who pays* are two different questions and answering one
    with the other is how a bill reaches the wrong company.
    """
    if account_id is None:
        return None
    fn = seams.resolve("customers", "customer_for_account", kind="selectors")
    if fn is None:
        return None
    found = fn(account_id)
    return dict(found) if found else None


def _owner_account_role(account_id: Any) -> str | None:
    """⊕ `CR-164-BRC10` wave 4 — what the build's single-family owner's
    account IS: `"lives_there"` (it holds the home once approved) or
    `"billing_only"` (PO 2026-10-03: *"a landlord or builder doesn't"* — it pays
    the build's charges and holds no unit). `None` for a master account or no
    account, where the question does not arise. A read of the row, the way
    `connections._account_or_404` reads it (B2 §2 reviewed interface)."""
    if account_id is None:
        return None
    from apps.customers import models as customers_models

    row = (
        customers_models.Account.objects.filter(pk=account_id)
        .values("kind", "billing_only")
        .first()
    )
    if row is None or row["kind"] != "regular":
        return None
    return "billing_only" if row["billing_only"] else "lives_there"


def _approved_by(request: Any) -> dict[str, Any]:
    """`WHERE IT CAME FROM`'s *Approved by* and the date beside the request.

    ⚠ **REPORTED AS HAVING NO SOURCE AND IT HAS ONE.** `service_requests`
    carries `decided_by` (an `identity.User` FK) and `decided_at`, both written
    by `service_request_service.approve` in the same save as the outcome. The
    drawing's own eyebrow — `CONNECTION CX-26-0007 · FROM SR-26-0001` — and its
    `Request · SR-26-0001 · approved 05/04/2026` are the two halves of that one
    row.

    ⚠ **ALL OF IT IS NULL ON A BUILD RAISED DIRECTLY, AND THAT IS PO RULING 1
    RATHER THAN A GAP.** Nobody approves a build a developer starts; there is no
    approval to name and inventing a stand-in — the creator, say — would put a
    person's name against a decision they did not take.

    `full_name or email` is this module's own convention for naming a person
    (`route_sheet.py:160`): an invited user's name is `""` until they accept,
    and a blank beside a date reads as a broken row.
    """
    if request is None:
        return {"by": None, "at": None}
    user = getattr(request, "decided_by", None)
    at = getattr(request, "decided_at", None)
    return {
        "by": ((user.full_name or user.email) if user is not None else None),
        "at": at.isoformat() if at is not None else None,
    }


def _request_fee_outstanding(request: Any) -> dict[str, str | None]:
    """`Fee outstanding on the request` — and it is NOT the build's outstanding.

    ⚠ **TWO FIGURES, TWO BLOCKS, AND THE DRAWING SEPARATES THEM ON PURPOSE.**
    The `OUTSTANDING` tile and the money block's `Outstanding` are what is still
    owed on the BUILD's own quote; this row is what is still owed on the
    APPLICATION FEE, which is the request's money and sits under `WHERE IT CAME
    FROM` with the rest of the provenance. Collapsing them would put an
    application fee into a construction quote.

    `customers.service_request_service.fee_total_to_collect` is the one function
    that answers it — *quoted − settled − collected* — and the drawing's own
    `$105.00` is that function's own worked figure, line for line
    (`$130.00` quoted, `$25.00` taken at the counter, receipt `RCP-26-4471`).
    Asked of customers by name, never computed here (B1).

    ⚠ **IT IS SIGNED AND IS NOT CLAMPED AT ZERO**, which is that function's own
    ruling: a counter that took more than the quote is finance's to reconcile,
    and hiding the overpayment would be the same silence in the other
    direction. `{None, None}` — never a zero — where there is no request at all.
    """
    request_id = getattr(request, "id", None)
    if request_id is None:
        return {"stored": None, "display": None}
    fn = seams.resolve("customers", "fee_total_to_collect", kind="service_request_service")
    if fn is None:
        return {"stored": None, "display": None}
    return reads._pair(fn(request_id).get("outstanding"))


def _premise_block(premises: Any) -> dict[str, Any] | None:
    """`THE PREMISE · STEP 2` — nine rows, every one WALKED. Hard rule 8.

    ⚠ **`None` WHERE THE BUILD HAS NO ADDRESS YET — `DEF-CUS-6109`.** A DRAFT
    raised by approving an application whose address had not resolved carries
    `premises = None` until the wizard's last button writes one (`BR-MET-112`).
    The whole block is withheld rather than nine nulls served inside it: *there
    is no address yet* is ONE fact, and nine empty rows read as a property whose
    details nobody filled in.

    *"we are having addresses at one place now - Premises and Units -> then they
    flow to {Meters, Sub meter, assets} + {accounts} -> from there it flows to
    Routes and Cycles"* (`BR-MET-1161`, PO 2026-09-04). **The build declares no
    address column of its own and this block adds none** — it is
    `selectors.premises_detail_dict` and `selectors.premises_routes`, the same
    two reads the property's own header uses, so an envelope and the Build tab
    cannot disagree about where this build is.

    The drawing says so itself, under the ninth row: *"This is where the address
    came from. Every meter, account, route, bill and work order on this build
    reaches it by walking back to this record."*

    ⚠ **`Unit, flat or suite` IS DELIBERATELY EMPTY AND THE DRAWING AGREES** —
    it reads *"— units are named on the next tab"*. A build spans a whole
    property; the one thing that would go in this row is a single unit's label,
    and a build has many. Served as `None` with the units section beside it.

    ⚠ **ROUTE IS A LIST AND NOT A STRING.** `premises_routes`' own reasoning:
    route membership is per unit, and a building whose units genuinely sit on
    different routes must show every one rather than have one picked. The
    drawing's `Route 4 · North` is the one-route case, which is the ordinary
    one; the header composes the sentence from these parts (`B14` rule 35).
    """
    if premises is None:
        return None
    detail = metering_selectors.premises_detail_dict(premises, with_owner_account=False)
    routes = metering_selectors.premises_routes(premises)
    return {
        "premise_type": detail["premises_type_name"],
        "premise_type_code": detail["premises_type"],
        "address_line": detail["address_line"],
        # Drawn, and drawn EMPTY — see the docstring.
        "unit_label": None,
        "city": detail["city"],
        "state": detail["state"],
        "postal_code": detail["postal_code"],
        # ⚠ **TWO KEYS, TWO FACTS, NEITHER SUBSTITUTED FOR THE OTHER**
        # (`BR-MET-1173`): `gis_parcel_id` is what the CITY calls this lot and
        # `external_ref` is what the utility's PREVIOUS SOFTWARE called it. The
        # drawing's one row says *Parcel or GIS reference*, so the parcel key
        # leads and the import key travels beside it rather than under it.
        "parcel_or_gis_ref": detail["gis_parcel_id"],
        "external_ref": detail["external_ref"],
        "routes": [
            {"code": row["code"], "name": row["name"], "area": detail["area_path"]}
            for row in routes
        ],
        # `B14` rule 31 — the NUMBER a clerk quotes, never the row id.
        "premise_no": detail["premise_no"],
    }


def _service_point_progress(service_rows: list[Any]) -> dict[str, int]:
    """The activated tile's sub-figure — `8 of 20 service points live`.

    One `connection_services` row IS one service point on this build: one
    service, at one unit (or at the premises, for a main tap). `live` counts the
    rows the product itself calls activated, through `connections.SVC_ACTIVATED`
    rather than a literal, so the day that token moves this figure moves with
    it.

    ⚠ **CANCELLED IS NOT SUBTRACTED HERE AND IS ON THE ORDER COUNT, WHICH IS
    NOT AN INCONSISTENCY.** `order_progress` drops a cancelled order from BOTH
    halves because *"4 of 4 and 4 of 5 with one cancelled are the same build"*.
    A service has no cancelled state at all (`SERVICE_STATES`), so there is
    nothing to drop.
    """
    return {
        "done": sum(1 for row in service_rows if row.state == work_tables.SVC_ACTIVATED),
        "total": len(service_rows),
    }


def _units_activated(unit_rows: list[dict[str, Any]], service_rows: list[Any]) -> dict[str, int]:
    """The `ACTIVATED` tile — `3 of 7`, counted in UNITS and not in services.

    ⚠ **A UNIT IS ACTIVATED WHEN EVERY SERVICE THIS BUILD MAPPED TO IT IS**, and
    that is the only reading that matches the tile beside it. The drawing pairs
    `3 of 7` with `8 of 20 service points live`: if a unit counted as activated
    on its first live service, a build with 8 of 20 points live could show 7 of
    7 units done, which is the opposite of what the screen is for.

    Units with NO service on this build are not counted as activated — an empty
    set is not a satisfied one, and `all([])` is the classic way to report a
    building finished because nothing was asked of it.

    ⚠ **`{done, total}`, THE SAME TWO KEYS AS THE OTHER TWO COUNTED PAIRS, AND
    THAT IS DELIBERATE RATHER THAN LAZY.** Units activated, service points live
    and work orders done are all drawn as `N of M` and all mean the same kind of
    thing, so they carry the same shape — and the front end has ALREADY declared
    it, as `BuildCount` in `07-frontend/src/features/work/buildRecord/
    buildRecordSource.ts`. Matching a published declaration costs nothing here
    and removes a mapping step that is one of the places a wired screen goes
    wrong (hard-won law 2). Naming this one `activated` and that one `live`
    would have read better in isolation and forced three special cases on the
    other side of the wire.
    """
    by_unit: dict[str, list[str]] = {}
    for row in service_rows:
        if row.unit_id is None:
            continue
        by_unit.setdefault(str(row.unit_id), []).append(row.state)
    done = sum(
        1
        for states in by_unit.values()
        if states and all(state == work_tables.SVC_ACTIVATED for state in states)
    )
    return {"done": done, "total": len(unit_rows)}


def _money(connection: Any) -> dict[str, Any]:
    """The `MONEY` block and the `CHARGES · STEP 6` table — `Quoted`, `Taken`,
    `Outstanding`, and the lines behind the total.

    ════════════════════════════════════════════════════════════════════════
    NOTHING HERE IS STORED AND NOTHING HERE IS ADDED UP TWICE
    ════════════════════════════════════════════════════════════════════════
    `connections.quote_invoice_id` names the bill; billing serves its total and
    its lines; payments serves what has been allocated against it. **The only
    arithmetic in this function is one subtraction**, and it is done in
    `Decimal` on figures both modules serve at stored scale (hard rule 2 — never
    a float, never cents, and the 2-dp rounding happens once, in `_pair`).

    ⚠ **`quote_total` ON THE ROW IS NOT USED AS THE QUOTED FIGURE WHEN A BILL
    EXISTS.** It is the figure the commit wrote down; the BILL is what the
    customer was actually asked for, and `invoices.total` is immutable once
    issued (hard rule 4). Where the two disagree the bill wins and the row's
    copy is served beside it as `quote_total_recorded`, so a reader can SEE the
    disagreement rather than have this function pick a winner. Picking one would
    be `DEF-127` with the evidence thrown away.

    ⚠ **EACH PAYMENT IS SERVED UNDER `payments` SINCE `CR-163-BRC10` (item
    20), AND THE TOP-LEVEL `tender` / `reference` / `clearing_date` STAY
    NULL.** This paragraph read *"`Taken`'s TENDER, REFERENCE AND CLEARING DATE
    ARE NOT SERVED … payments publishes an allocated SUM and no per-bill
    payment list"* until 2026-10-02. Payments now publishes
    `selectors.payments_for_bills`, so the drawing's *"$1,500.00 · cheque CHQ
    118420"* is a ROW per payment rather than one tender for the whole build — a
    build can be paid twice by two tenders, and one top-level field would have
    to pick. `ABSENCE_TENDER_NOT_PUBLISHED` is stated only where that read is
    unpublished.

    ⚠ **SEVERAL BILLS, SUMMED (`CR-163-BRC10` item 2).** A fee added after
    submission is its own issued bill, recorded in `connection_fee_bills`;
    `Quoted` and `Taken` are sums over every bill `_bill_ids` names, and each
    line carries the bill it is on.

    ⚠ **A BUILD WITH NO BILL IS NOT A BUILD THAT OWES NOTHING.** Every figure is
    `{None, None}` with `this_build_has_raised_no_bill`, because `$0.00` on this
    tile reads as *settled* and the truth is *never priced*.
    """
    absences: list[dict[str, Any]] = []
    recorded = reads._pair(connection.quote_total)
    empty = {"stored": None, "display": None}

    bill_ids = _bill_ids(connection)
    if not bill_ids:
        absences.append(
            {
                "field": "money",
                "code": ABSENCE_NO_BILL,
                "tracks": "CR-126-BRC07",
            }
        )
        if connection.service_request_id is None:
            # ⚠ **THIS COMMENT SAID *"PO ruling 1 of 2026-09-21 says the build
            # prices itself; the commit path does not yet"* UNTIL 2026-09-28
            # AND BOTH HALVES ARE NOW FALSE.** `build_quote_lines` landed with
            # `BR-MET-1178` on 2026-09-21 — the commit path prices a direct
            # build — and under `BR-MET-1187` a build whose charges could not
            # be posted is **not created at all**. So reaching this branch no
            # longer means *"nobody priced it"*; it means **this build named no
            # charge**, which is the one case the ruling exempts by name.
            #
            # ⛔ **THE CODE STRING IS THEREFORE WRONG AND IS NOT RENAMED HERE —
            # `DEF-MET-7643`.** `a_build_raised_directly_is_priced_by_nobody`
            # is a screen-facing absence code; renaming it moves eleven locale
            # catalogues and a case in `test_cr126_build_record.py`, which is a
            # shared-file fan-out this lane does not own mid-flight (law 11).
            # **Nothing renders it yet** — grepped across `07-frontend/src`,
            # zero hits — so the row exists before the Charges tab starts
            # reading `unavailable` and repeats the sentence to a clerk.
            absences.append(
                {
                    "field": "money",
                    "code": ABSENCE_DIRECT_BUILD_PRICES_NOTHING,
                    "tracks": "PO-2026-09-21-1",
                }
            )
        return {
            "invoice_no": None,
            "invoice_id": None,
            "billed_to": None,
            "billed_to_id": None,
            "quoted": empty,
            "quote_total_recorded": recorded,
            "taken": empty,
            "outstanding": empty,
            "clearing_date": None,
            "tender": None,
            "reference": None,
            "lines": [],
            "bills": [],
            "payments": [],
            "unavailable": absences,
        }

    # ── `CR-163-BRC10` · EVERY BILL THIS BUILD RAISED, NOT ONLY THE FIRST ──
    # The quote is the first; a fee a clerk ADDS after submission is a NEW
    # issued bill (hard rule 4 — an issued line is never edited), recorded in
    # `connection_fee_bills`. Quoted, Taken and Outstanding are the sums over
    # all of them, and every line says which bill it is on.
    bills: list[dict[str, Any]] = []
    for invoice_id in bill_ids:
        one = seams.quote_bill(invoice_id)
        if one is None:
            absences.append(
                {
                    "field": "money",
                    "code": ABSENCE_BILLING_UNPUBLISHED,
                    "tracks": "B1",
                }
            )
            return {
                "invoice_no": None,
                "invoice_id": None,
                "billed_to": None,
                "billed_to_id": None,
                "quoted": empty,
                "quote_total_recorded": recorded,
                "taken": empty,
                "outstanding": empty,
                "clearing_date": None,
                "tender": None,
                "reference": None,
                "lines": [],
                "bills": [],
                "payments": None,
                "unavailable": absences,
            }
        bills.append({**one, "_id": str(invoice_id)})
    bill = bills[0]

    totals = [Decimal(str(one["total"])) for one in bills if one.get("total") is not None]
    quoted = sum(totals, Decimal("0")) if len(totals) == len(bills) else None
    settled = seams.settled_against_bills(bill_ids)
    if settled is None:
        absences.append(
            {
                "field": "taken",
                "code": ABSENCE_SETTLEMENT_UNPUBLISHED,
                "tracks": "B1",
            }
        )
        taken = None
    else:
        # ABSENT from the map is *nothing allocated*, which is a true answer
        # over payments' append-only table — see the seam's own docstring.
        taken = sum(
            (Decimal(str(settled.get(str(invoice_id), "0"))) for invoice_id in bill_ids),
            Decimal("0"),
        )

    outstanding = None if (quoted is None or taken is None) else quoted - taken
    # ── `CR-163-BRC10` item 20 · EACH PAYMENT, FROM PAYMENTS' OWN ROWS ──────
    # This block used to state `ABSENCE_TENDER_NOT_PUBLISHED` on every build,
    # because payments published an allocated SUM and no per-payment list. It
    # publishes one now, so the absence is stated ONLY when that read is
    # unpublished — a stated absence that outlives its cause is hard-won law 1.
    paid_rows = seams.payments_for_bills(
        bill_ids, entry_reference=f"{w6.PAYMENT_KEY_PREFIX}{connection.id}"
    )
    if paid_rows is None:
        absences.append(
            {
                "field": "tender",
                "code": ABSENCE_TENDER_NOT_PUBLISHED,
                "tracks": "B1",
            }
        )
    return {
        # `B14` rule 31 — the bill NUMBER is what a clerk reads; the id travels
        # only so a screen can build the bill's ADDRESS (`CR-163-BRC10` item 22).
        "invoice_no": bill.get("invoice_no"),
        "invoice_id": str(bill.get("id") or bill["_id"]),
        "billed_to": bill.get("account_no"),
        # Served so the screen stops DERIVING the payer's id through another
        # read (`GET /premises/{id}/build`), which answers the NEWEST build at
        # an address and so opened nothing on a re-built one (item 21).
        "billed_to_id": (
            str(bill["account_id"]) if bill.get("account_id") is not None else None
        ),
        "quoted": reads._pair(quoted),
        "quote_total_recorded": recorded,
        "taken": reads._pair(taken),
        "outstanding": reads._pair(outstanding),
        "clearing_date": None,
        "tender": None,
        "reference": None,
        "bills": [
            {
                "invoice_no": one.get("invoice_no"),
                "invoice_id": str(one.get("id") or one["_id"]),
                "total": reads._pair(one.get("total")),
                # `False` on the quote the build was created with, `True` on
                # every fee added after submission (`CR-163-BRC10` item 2).
                "added": str(one["_id"]) != str(connection.quote_invoice_id),
            }
            for one in bills
        ],
        "lines": [
            {
                "charge_code": line.get("charge_code"),
                "description": line.get("description"),
                "quantity": line.get("quantity"),
                "unit_price": line.get("unit_price"),
                "amount": line.get("amount"),
                # ⚠ **THE TWO FIGURES THE SCREEN PRINTS, ROUNDED ONCE, HERE**
                # (`CR-163-BRC10` item 18). The Charges tab read *"Priced on
                # the bill"* on every line because no display pair travelled
                # and rounding in the browser is the second path hard rule 2
                # forbids. `_pair` is that one rounding.
                "each": reads._pair(line.get("unit_price")),
                "line_total": reads._pair(line.get("amount")),
                "invoice_no": one.get("invoice_no"),
                "invoice_id": str(one.get("id") or one["_id"]),
                "currency": one.get("currency"),
            }
            for one in bills
            for line in (one.get("lines") or [])
        ],
        "payments": (
            None
            if paid_rows is None
            else [
                {
                    **{key: value for key, value in row.items() if key != "amount"},
                    "amount": reads._pair(row.get("amount")),
                }
                for row in paid_rows
            ]
        ),
        "unavailable": absences,
    }


def _bill_ids(connection: Any) -> list[Any]:
    """The build's bills, the quote FIRST and then each added fee in the order
    it was raised (`CR-163-BRC10` item 2). Ids this module wrote down itself —
    nothing is searched for in billing's tables."""
    from apps.metering.connection_fees import ConnectionFeeBill

    ids: list[Any] = [] if connection.quote_invoice_id is None else [connection.quote_invoice_id]
    ids.extend(
        ConnectionFeeBill.objects.filter(
            tenant_id=connection.tenant_id, connection_id=connection.id
        )
        .order_by("created_at", "id")
        .values_list("invoice_id", flat=True)
    )
    return ids


def _communication_rows(connection: Any) -> list[dict[str, Any]]:
    """`WHAT THIS BUILD QUEUED · STEP 7` — `WHAT WENT OUT · CHANNEL · TEMPLATE ·
    STATE`, read from the queue (`CR-163-BRC10`).

    The rows are `connection_messages.OCCASIONS`, which is the PO's own list in
    the PO's own order, plus the one the drawing shows and this step does NOT
    own — *Unit energised*, whose `WHEN` is *as each unit activates* and which
    `BR-MET-115` moved to the work-order screen. It is listed with its moment
    rather than dropped, because recording it as absent would quietly reverse a
    ruling by bookkeeping.

    ⚠ **THIS PARAGRAPH READ *"NO MESSAGE HAS EVER BEEN FILED FOR A CONNECTION
    … `OQ-NOT-12521`, OPEN"* UNTIL 2026-10-02.** That question closed on
    2026-09-21 (option A, a `connection` kind) and was built by `CR-163-BRC10`,
    so a letter CAN be filed — by *Send now* on the Messages tab, and on
    approval (`Q8`, `messages.fire_on_approval`). A row is `queued` once the
    queue holds a copy for it and `sent` only when a provider stamped
    `sent_at`, which no channel can do yet (`BR-NOT-013`): the drawing's red
    line, *"Queued is not sent"*, is now exactly true, and the payload still
    carries `nothing_is_sent()` so no screen can claim otherwise.

    **NO ENGLISH TRAVELS.** What goes on the wire is the occasion CODE, the
    channel and the template class; the words a clerk reads are the front end's
    eleven catalogues (`B14` rule 35).
    """
    # ── `CR-163-BRC10` items 26–27 · THE QUEUE IS ASKED, NOT ASSUMED ─────────
    # Every row read `not_sent` from a constant until 2026-10-02, so a letter a
    # clerk had sent could never show as sent and `When` was empty for ever
    # (`DEF-CUS-9188`). Each occasion files under its own source id
    # (`messages.occasion_source_id`), and what the queue holds for it now
    # decides the state, the moment and the copies.
    delivered = messages.deliveries_by_occasion(connection)
    available = _templates_available()
    utility_language = seams.tenant_default_language()

    def _sent_language(pinned: Any) -> str | None:
        code = str(pinned or "").strip()
        if code and code != "default":
            return code
        return utility_language

    def _live(code: str, fallback_state: str, fallback_reason: Any) -> dict[str, Any]:
        rows_for = delivered.get(code)
        if not rows_for:
            return {
                "state": fallback_state,
                "reason": fallback_reason,
                "sent_at": None,
                "deliveries": [] if rows_for is not None else None,
            }
        moments = [row.get("sent_at") or row.get("queued_at") for row in rows_for]
        moments = [moment for moment in moments if moment]
        return {
            "state": (
                messages.STATE_SENT
                if any(row.get("sent_at") for row in rows_for)
                else messages.STATE_QUEUED
            ),
            "reason": None,
            "sent_at": max(moments) if moments else None,
            "deliveries": [
                {
                    "id": row.get("id"),
                    "channel": row.get("channel"),
                    "copy_no": row.get("copy_no"),
                    "status": row.get("status"),
                    "queued_at": row.get("queued_at"),
                    "sent_at": row.get("sent_at"),
                    # ⊕ `DEF-CUS-9195` — the language this copy WENT in: the
                    # language its pinned wording is in, and the utility's
                    # own where it pinned the `default` wording.
                    "language": _sent_language(row.get("template_language")),
                }
                for row in rows_for
            ],
        }

    rows = [
        {
            "code": one.code,
            "channels": list(one.channels),
            "template_code": one.template_code,
            # Item 27 — `False` draws *"No template — add one in Settings →
            # Templates"* and greys Send. `None` = notifications could not say.
            "template_available": (
                None if available is None else one.template_code in available
            ),
            "sendable": True,
            "when": one.when,
            # ⊕ `DEF-MET-9229` — a letter with no template is NOT going on
            # approval, so it must not say it is; it reads *Not sent*.
            **_live(
                one.code,
                messages.STATE_NOT_SENT,
                (
                    messages.REASON_NO_TEMPLATE
                    if available is not None and one.template_code not in available
                    else messages.REASON_SENT_ON_APPROVAL
                ),
            ),
        }
        for one in messages.OCCASIONS
    ]
    rows.extend(
        {
            "code": one["code"],
            "channels": [],
            "template_code": None,
            "template_available": False,
            # No occasion and no template class: nothing a clerk could send.
            "sendable": False,
            "when": one.get("moved_to"),
            **_live(one["code"], messages.STATE_NOT_ASKED, one["because"]),
        }
        for one in messages.NOT_AT_CREATION
    )
    return rows


def _templates_available() -> set[str] | None:
    """The template classes this tenant has a PICKABLE (published) variant of,
    or `None` when notifications could not be asked."""
    rows = seams.connection_templates()
    if rows is None:
        return None
    return {str(row.get("code")) for row in rows if row.get("pickable")}


def build_record(
    connection_id: Any,
    *,
    section: str | None = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """`GET /connections/{id}/record` — the whole build record, in one call.

    Returns the header, the five tiles, the six `Overview` blocks and the first
    page of every list. `section` names the ONE list `page`/`per` apply to; an
    unrecognised name pages nothing and is not an error (`BR-SHL-011`).

    Tenant scoping is `connection_detail`'s — `_connection_or_404` filters on
    the resolved tenant and a cross-tenant id is an indistinguishable 404, never
    a 403 (hard rule 1, HR-1/G4).
    """
    tenant_id: UUID = reads._tenant_id()
    connection = reads._connection_or_404(tenant_id, connection_id)
    detail = reads.connection_detail(connection.id)

    service_rows = list(
        work_tables.ConnectionService.objects.filter(
            tenant_id=tenant_id, connection_id=connection.id
        ).select_related("service")
    )
    unit_rows = detail["unit_rows"]
    done, total_orders = detail["orders"]["done"], detail["orders"]["total"]
    premises = connection.premises
    request = connection.service_request
    customer = _customer_of_account(connection.owner_account_id)
    money = _money(connection)
    activated = _units_activated(unit_rows, service_rows)
    points = _service_point_progress(service_rows)
    wanted = section if section in SECTIONS else None

    def paged(name: str, rows: list[Any]) -> dict[str, Any]:
        return _page_of(rows, page=page, per=per, paged=(name == wanted))

    return {
        "id": str(connection.id),
        # `B14` rule 31 — what a clerk sees and says out loud.
        "connection_no": detail["connection_no"],
        "header": {
            # ⚠ **THE TITLE IS THE OWNER, NOT THE PROPERTY** — the PO confirmed
            # that on 2026-09-21 and the drawing shows `Balcones Development
            # LLC` over `212 Balcones Drive`. Null where the build names no
            # payer, with the applicant served separately rather than
            # substituted: *who applied* and *who pays* are two questions.
            "owner_name": (customer or {}).get("display_name"),
            "applicant": detail["applicant"],
            "request_no": detail["request_no"],
            "state": detail["state"],
            "waiting_on": detail["waiting_on"],
            # ⚠ **THE CUSTOMER-CLASS CHIP IS NOT A KEY HERE, ON PURPOSE.** It
            # is `premises.premises_type`, served ONCE under `premise` and read
            # from there — the drawing itself proves they are one fact, because
            # `THE PREMISE · STEP 2`'s first row and the chip carry the same two
            # words. A second copy on this block is hard-won law 5's shape for a
            # response: one source, views derived. A `null` placeholder would
            # have been worse than either — a key nothing may read is the dead
            # prop law 2 is about.
            "target_activation": detail["target_activation"],
            # The service tags under the address line, in the build's own order.
            "services": sorted({row.service.code for row in service_rows}),
        },
        "tiles": {
            "units": detail["units"],
            "activated": activated,
            "service_points": points,
            "work_orders": {"done": done, "total": total_orders},
            "quoted": money["quoted"],
            "outstanding": money["outstanding"],
        },
        "live_state": {
            "state": detail["state"],
            "waiting_on": detail["waiting_on"],
            "units_activated": activated,
            "service_points_live": points,
            "target_activation": detail["target_activation"],
            # Reported as having no source and it is a column since W6 — §3.
            "activated_at": (
                connection.activated_at.isoformat() if connection.activated_at else None
            ),
        },
        "owner_and_scope": {
            # THREE NEW COLUMNS (`metering/0058`) — collected by step 1 and
            # discarded until today.
            "owner_type": connection.owner_type,
            "units_prefix": connection.units_prefix,
            "scope": connection.scope,
            # TWO WALKED to the payer's customer record — p106 puts them there.
            "owner_or_developer": (customer or {}).get("display_name"),
            "external_system_reference": (customer or {}).get("external_ref"),
            # Step 1's `How the work is done`. The DERIVED reading — what the
            # ORDERS say — beside the build's own stamp, because
            # `connection_mode` is `"mixed"` on the ordinary build that does its
            # own water and contracts out gas (§8.3).
            "mode": detail["mode"],
            "mode_recorded": connection.mode,
            # ⊕ `CR-164-BRC10` wave 4 — the owner's account: lives there, or
            # billing only. `None` for a master account or none.
            "owner_account_role": _owner_account_role(connection.owner_account_id),
        },
        "premise": _premise_block(premises),
        "where_it_came_from": {
            "request_no": detail["request_no"],
            "approved": _approved_by(request),
            "created_at": connection.created_at.isoformat() if connection.created_at else None,
            "started_at": detail["started_at"],
            "fee_outstanding": _request_fee_outstanding(request),
        },
        "plan": {
            "services": detail["services"],
            "assets": detail["assets"],
            "sub_meter_links": detail["sub_meter_links"],
        },
        "money": money,
        "sections": {
            "units": paged("units", unit_rows),
            "charges": paged("charges", money["lines"]),
            "work_orders": paged("work_orders", detail["work_orders"]),
            "communication": paged("communication", _communication_rows(connection)),
            "audit": paged("audit", detail["history"]),
            "outstanding": paged("outstanding", detail["outstanding"]),
        },
        "messages_are_never_sent": messages.nothing_is_sent(),
        # `CR-163-BRC10` item 26 — who a clerk may send a letter to: the owner
        # account, and the request's co-applicant where it names one.
        "message_recipients": messages.recipients_for(connection),
        # Every absence the read model already states, plus this file's own.
        "unavailable": [
            *_forwarded_absences(connection, detail["unavailable"]),
            *money["unavailable"],
        ],
    }


#: ⚠ **`connection_detail` STILL PUBLISHES A SENTENCE THAT STOPPED BEING TRUE
#: ON 2026-09-16, AND THIS PAYLOAD IS THE FIRST THING THAT WOULD SHOW IT TO A
#: CLERK.** `quote_recorded_not_posted` reads *"The charges for this build are
#: held as a single quoted total. The lines behind it were never raised as
#: bills, so there is nothing to list here."* `_post_connection_quote` landed
#: that day and raises a real receivable, so on any build that HAS a bill the
#: sentence is false — and it would be drawn on the `CHARGES · STEP 6` table,
#: beside the bill's own lines, contradicting them. That is hard-won law 1's
#: exact shape on a money screen: a stated absence outliving its cause. The
#: New Connect conformance measurement predicted it in as many words — *"the
#: day somebody builds the drawn Plan & charges tab, it draws a false absence
#: on a money screen"*.
#:
#: ⚠ **IT IS FILTERED HERE AND NOT DELETED AT SOURCE, AND THE REASON IS WORTH
#: STATING.** `tests/test_w6_connection_detail.py` PINS that sentence both ways
#: — the null and the words — deliberately, so that a later lane filling the
#: field with a zero goes red. Deleting it from `DETAIL_ABSENCES` moves that
#: contract and a neighbouring lane's test, so it is FILED — `DEF-MET-6059` —
#: rather than taken here on a read lane's own authority. What this payload
#: owes meanwhile is that it does not itself tell the lie.
STALE_QUOTE_ABSENCE = "quote_recorded_not_posted"


def _forwarded_absences(connection: Any, absences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`connection_detail`'s absences, minus any this record has disproved.

    Only one qualifies today and only on one condition: a build that HAS a bill
    cannot also be a build whose lines *"were never raised as bills"*. Where
    there is no bill the sentence is still true OF THAT BUILD and travels
    untouched — what is stale is the code's reasoning, and suppressing a true
    sentence to hide a stale code would be the worse of the two.
    """
    if connection.quote_invoice_id is None:
        return list(absences)
    return [entry for entry in absences if entry.get("code") != STALE_QUOTE_ABSENCE]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-126-BRC07 lane NCD-1 · blueprint p98-p107 read AS IMAGES (B14
#         rule 42) · 12-governance/28-new-connect-measured-2026-09-21.md ·
#         OQ-MET-12520 (CLOSED 2026-09-21, option C) · PO rulings 2026-09-21
# generated: 2026-09-21 by lane NCD-1 (the backend half of the build record)
# checklist: A✔ B✔ C✔ D✔ E=deferred(front end is lane NCD-2's — the property's
#         Build tab gains these as SECTIONS, per OQ-MET-12520) F✔ G✔ H=deferred(PO)
# exceptions:
#   (1) the header carries NO customer-class chip key; it is
#       `premise.premise_type`, served once and read from there — one fact,
#       one home on the payload (hard-won law 5's shape for a response);
#   (2) `money.tender` / `.reference` / `.clearing_date` are null with
#       `the_tender_and_clearing_date_are_not_published_here`. Payments serves
#       an allocated SUM and no per-bill payment list; a read carrying the
#       drawn three is REPORTED as owed and is PAYMENTS' to publish (B1);
#   (3) `_customer_of_account` and `_request_fee_outstanding` resolve
#       `customers.selectors.customer_for_account` and
#       `customers.service_request_service.fee_total_to_collect`, both of which
#       exist today. Where a resolve comes back None the rows are null rather
#       than guessed;
#   (4) the commit path does not yet obey PO ruling 1's pricing half
#       (`_post_connection_quote` still refuses a build with no request). It is
#       a WRITE on a money path and is not changed from a read lane; the
#       absence travels on the payload naming the ruling;
#   (5) no story owns this screen (hard-won law 8) — S88 never had one and the
#       Build tab's sections have none either. REPORTED, not invented.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
