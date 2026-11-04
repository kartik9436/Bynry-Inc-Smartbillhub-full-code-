# ── Trace ──────────────────────────────────────────────
# Story:   CR-112 §E — address search: ONE implementation, three callers.
# Rules:   BR-INT-048 (`C16` — the list is OFFERED and nothing is written until
#          a person picks) · BR-INT-075 (the ranking is OURS and is labelled as
#          ours; the list is grouped by building and capped) · B14 rule 31 (no
#          database id is a visible value) · rule 33 (a fact ≤ 6 words) ·
#          PO rulings 2026-09-17 nos. 3 and 5
# Tests:   06-backend/tests/test_cr112_gis_search.py
# Impacts: apps/integrations/gis.py (the inline search) ·
#          apps/integrations/gis_parcels.py (the match step reads the same rules)
# ───────────────────────────────────────────────────────
"""Address search — ranked by us, grouped by building, and honest about both.

WHY THIS IS ITS OWN FILE: THREE CALLERS, ONE IMPLEMENTATION
-------------------------------------------------------------
The premises create form, the unit create form and the reconciliation match step
all ask the City the same question. Ruling 3 of 2026-09-17 makes that question
load-bearing — it is how BOTH keys arrive:

    *"We will need to use 2 · Address search … at first time to map pacle ID and
    Point ID during first run or when we create the premsies and Unit first time
    - that the answer to find out mathcing keys"*

Three copies of a ranking rule is three rankings, and they diverge the first
time one is tuned. The ordering, the grouping and the cap live here once.

⚠ **THE RANKING IS OURS AND THE SCREEN SAYS SO — WHEN IT IS OURS.** An ArcGIS
layer publishes no relevance score for a `like` query, so there is nothing to
sort by but our own judgment: exact street beats partial · postcode match ·
exact street number · then alphabetical, each a tie-break on the one before, and
`RANKING_NOTE_KEY` is the catalogue key the screen renders beside that list. ⚠ A
GEOCODER — the other shape `adapters/gis_city.candidate_from` accepts — DOES
publish one, and then **theirs wins and the note is not shown**: their index
knows things four tie-breaks over a street name cannot, and putting *"Ordered by
us, not the city."* over the city's own order would be the claim this file
exists to avoid making. `rank_candidates` is where that fork lives.

⚠ **GROUPED BY BUILDING, NOT A FLAT LIST.** A four-flat returns five rows — the
building and four units — and a flat list of five near-identical addresses is
the thing a clerk misreads. One parcel, with its units beneath it.

⚠ **CAPPED, AND THE CAP SAYS WHAT TO DO ABOUT IT.** Twenty buildings, with
*keep typing to narrow this* when there are more. A list nobody can finish
reading is a list nobody reads; a truncated list with no notice is worse,
because the row somebody wanted is missing and nothing says so.

⚠ **NOTHING IS WRITTEN HERE AND NOTHING IS AUTO-SELECTED — NOT EVEN AT ONE
RESULT** (`C16`). One result is the most tempting case and the most dangerous:
a single close-but-wrong match, selected for the clerk, is a wrong parcel key
that nobody chose and that everything downstream then trusts. **A person picks.**

⚠ **NOTHING FOUND IS AN ANSWER, NOT AN ERROR** (ruling 5's neighbour). A utility
may serve addresses outside the City's layer — a township on the edge of the
service area is ordinary — so an empty result says so plainly and the clerk
carries on typing. The City being UNREACHABLE is the different case and is
ruling 5: *"b) let them type it, mark unverified, the sync fixes it later"*.
`gis.py` already builds that branch; this file only ranks what came back.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping, Sequence

from apps.integrations.gis_layer import ParcelRow, normalise_postcode, normalise_street

#: ⚠ **TWENTY BUILDINGS, NOT TWENTY ROWS.** A cap counted in rows would show
#: three buildings when one of them is a large block, which is the opposite of
#: what a cap is for.
#:
#: ⚠⚠ **AND IT IS NOT THE CAP THE LIVE SEARCH ENFORCES — SAY SO RATHER THAN
#: LETTING TWO NUMBERS STAND FOR ONE FACT (`DEF-INT-5603`, re-measured
#: 2026-09-17).** `adapters/gis_city.CANDIDATE_CAP` is **8**, it is applied to
#: ROWS before anything reaches this module, and the City is only ever asked for
#: nine. So twenty can never bite on `gis.py::search`: this number governs
#: `group_by_building`, and `group_by_building` is not on that path. The honest
#: statement is that the product enforces 8 rows and this module documents 20
#: buildings, and the two become one number the day the search is grouped —
#: which needs the City's `Unit` on the wire and is not this module's to add.
BUILDING_CAP = 20

#: The sentence a screen shows when the cap bit. **A KEY, NEVER A SENTENCE BUILT
#: IN PYTHON** — `core.errors` asserts the key resolves, and the eleven
#: catalogues are what make it reach a clerk in their own language. Six words
#: (B14 rule 33, an instruction): *"Keep typing to narrow this."*
MORE_RESULTS_KEY = "integrations.gis.keep_typing"
#: *"No matching address found."* — plainly, and the clerk continues.
NOTHING_FOUND_KEY = "integrations.gis.nothing_found"
#: *"Ordered by us, not the city."* — the ranking labelled as ours.
RANKING_NOTE_KEY = "integrations.gis.our_ranking"


@dataclass(frozen=True)
class Building:
    """One parcel, with its units beneath it — what a clerk actually picks from.

    ⚠ **`parcel` IS A KEY AND NOT A DATABASE ID, WHICH IS WHY IT MAY BE SHOWN.**
    B14 rule 31 forbids a database id as a visible value; this is the CITY's own
    reference for a lot, which a clerk can read off a tax bill. `point_id` on a
    unit is the same kind of fact.
    """

    parcel: str
    address_line: str
    city: str | None
    state: str | None
    postal_code: str | None
    status: str | None
    #: The building's own point, when the City published one (ruling 6). `None`
    #: means the parcel has only unit points — the pin stays blank rather than
    #: borrowing one.
    lat: Any = None
    lng: Any = None
    units: tuple[Mapping[str, Any], ...] = ()

    @property
    def unit_count(self) -> int:
        return len(self.units)


def _street_number(address: str) -> str:
    """The leading number of an address line, or `""`."""
    head = normalise_street(address).split(" ", 1)[0] if address else ""
    return head if head.isdigit() else ""


def rank_key(row: ParcelRow, typed: str, postcode: str = "") -> tuple:
    """Our ordering, as a sort key. **Lower sorts first.**

    Four tie-breaks, in the order the brief sets them and each only breaking
    ties in the one above:

      1. **exact street beats partial** — the whole normalised street matching
         what was typed comes before a street that merely contains it;
      2. **postcode match** — when the clerk gave one;
      3. **exact street number** — `1408` before `14080`, which a substring
         match on `1408` otherwise ranks together;
      4. **alphabetical** — so the order is stable and two runs agree. Without
         this a set with equal scores comes out in dictionary order, which is
         insertion order, which is the City's paging order.
    """
    wanted = normalise_street(typed)
    theirs = row.street_key
    exact_street = 0 if theirs == wanted else 1
    postcode_hit = (
        0 if (postcode and row.postcode_key == normalise_postcode(postcode)) else 1
    )
    wanted_number = _street_number(typed)
    number_hit = 0 if (wanted_number and _street_number(row.address_line) == wanted_number) else 1
    return (exact_street, postcode_hit, number_hit, theirs, row.parcel_id)


def group_by_building(
    rows: Iterable[ParcelRow], *, typed: str = "", postcode: str = "", cap: int = BUILDING_CAP
) -> dict[str, Any]:
    """Their rows → buildings with units beneath, ranked by us and capped.

    Returns `{buildings, more, total_buildings, ranking_note_key,
    message_key}`. **Nothing here writes anything**, and nothing is marked as
    chosen — `C16`, the disposition is `offer`.
    """
    by_parcel: dict[str, list[ParcelRow]] = {}
    for row in rows:
        if not row.parcel_id:
            # No parcel key means nothing to store if it were picked — the whole
            # value of picking over typing is that the premises carries the
            # City's key. `adapters/gis_city.candidate_from` drops these for the
            # same reason, and this is the second door.
            continue
        by_parcel.setdefault(row.parcel_id, []).append(row)

    buildings: list[Building] = []
    for parcel, group in by_parcel.items():
        head = next((one for one in group if one.is_building_point), None)
        # The representative row for the ADDRESS is the building point when
        # there is one and any unit's otherwise — a unit's address line is its
        # building's, so this loses nothing.
        shown = head or group[0]
        units = tuple(
            {
                "label": one.unit_label,
                # The City's own reference for this address point, which is a
                # key a clerk can read, not a database id (B14 rule 31).
                "point_id": one.point_id,
                "lat": one.lat,
                "lng": one.lng,
                "status": one.status,
            }
            for one in sorted(group, key=lambda r: (r.unit_key, r.point_id))
            if not one.is_building_point
        )
        buildings.append(
            Building(
                parcel=parcel,
                address_line=shown.address_line,
                city=shown.city,
                state=shown.state,
                postal_code=shown.postal_code,
                status=shown.status,
                # ⚠ Ruling 6 — the BUILDING's own point or nothing at all.
                # Never a unit's, never an average of the units'.
                lat=head.lat if head else None,
                lng=head.lng if head else None,
                units=units,
            )
        )

    ordered = sorted(
        buildings,
        key=lambda b: rank_key(
            next(one for one in by_parcel[b.parcel] if one.parcel_id == b.parcel),
            typed,
            postcode,
        ),
    )
    shown_list = ordered[:cap]
    return {
        "buildings": shown_list,
        "total_buildings": len(ordered),
        # ⚠ **THE CAP SAYS WHAT TO DO ABOUT ITSELF.** A truncated list with no
        # notice is worse than a long one: the row somebody wanted is missing
        # and nothing says so.
        "more": len(ordered) > cap,
        "message_key": (
            MORE_RESULTS_KEY
            if len(ordered) > cap
            else (NOTHING_FOUND_KEY if not ordered else None)
        ),
        # The ranking is OURS and the screen says so. The City publishes none
        # for a `like` query, so presenting this order as theirs would be a
        # claim we cannot support.
        "ranking_note_key": RANKING_NOTE_KEY if ordered else None,
        # ⚠ **NO ROW IS MARKED CHOSEN, NOT EVEN WHEN THERE IS EXACTLY ONE.**
        # One close-but-wrong match auto-selected is a wrong parcel key nobody
        # picked and everything downstream then trusts (`C16`).
        "selected": None,
    }


def rank_candidates(
    candidates: Sequence[Mapping[str, Any]], typed: str, *, postcode: str = ""
) -> dict[str, Any]:
    """The live search's FLAT list, put in OUR order. Returns `{candidates,
    ranking_note_key}`.

    ── 2026-09-17 · `DEF-INT-5601` ─────────────────────────────────────────────
    ⚠ **THIS IS THE DOOR ONTO THIS MODULE, AND IT IS DELIBERATELY NARROWER THAN
    THE MODULE.** `gis.py::search` served the City's rows in the CITY's order —
    a FeatureServer answers in the layer's own order, which is essentially
    insertion order — and then cut them to eight. So *"8 matches from the City's
    records"* was eight arbitrary rows, and typing `100 N Maple` could show
    eight addresses with `100 N Maple` not among them. This puts `rank_key` on
    that path: exact street first, then postcode, then exact street number, then
    alphabetically, which is one ordering for every caller instead of none.

    ⚠ **IT RANKS AND IT DOES NOT GROUP, AND THE REASON IS A MISSING FIELD RATHER
    THAN A SHORTAGE OF TIME.** `group_by_building` needs to know which of a
    parcel's rows is the BUILDING and which are its units, and the only witness
    to that is the City's `Unit` column. `adapters/gis_city.candidate_from` does
    not put it on the wire, so every row arrives here looking like a building
    point. Grouping on that would collapse a four-flat's five address points
    into ONE row and take four `FULLPIN`s off the screen with them — which is
    the exact key `DEF-INT-5600` exists to deliver. **A worse screen is not a
    smaller gap.** The bridge below already reads `unit`, so the day that field
    is on the wire this becomes `group_by_building` and nothing else moves.
    ⚠ **2026-10-07 (`DEF-INT-9845`): THE FIELD IS ON THE WIRE NOW.** What is
    left is the screen — `FindTheAddress.tsx` reads a flat list, and grouping
    changes the shape it reads — so it is not switched here.

    ⚠ **THE RANKING CANNOT RECOVER A ROW THE CITY WAS NEVER ASKED FOR.** The
    adapter requests nine rows and the City chooses which nine. Ordering nine
    arbitrary rows well is better than ordering them not at all, and it is not
    the same thing as showing the best nine.

    ⚠⚠ **AND WHERE THE CITY DID PUBLISH A RELEVANCE, THEIRS WINS AND THE NOTE
    IS NOT SHOWN.** This module's premise is that *"the City publishes no
    relevance score for a `like` query — there is nothing to sort by but our own
    judgment"*. That is true of an ArcGIS layer and FALSE of a geocoder, which
    is the other shape `candidate_from` accepts: it returns a `score`, and it
    knows things about its own index that four tie-breaks over a street name
    cannot. Overriding it would make the answer WORSE, and saying *"Ordered by
    us, not the city."* over their order would be the claim this module exists
    to avoid making. So the note is a KEY OR `None` and never a decoration: it
    appears exactly when we did the ordering.

    ⚠ **ALL OR NOTHING, NEVER ROW BY ROW.** A scored row and an unscored one
    cannot be compared — there is no number to put the second one at — so one
    candidate without a score puts the whole list in our order. Mixed lists
    become ordinary the day `CR-115` §7.5 rule 2 merges several lookup URLs, and
    at that point the SCALES must be normalised before a merged score means
    anything; `match_word` already does that arithmetic and this reads the same
    `score_scale` for the same reason.
    """
    scores = [_relevance(one) for one in candidates]
    if candidates and all(one is not None for one in scores):
        # Their order. Descending relevance, and the City's own sequence breaks
        # a tie so two runs of the same search agree.
        order = sorted(range(len(candidates)), key=lambda i: (-scores[i], i))
        note = None
    else:
        rows = candidates_to_rows(candidates)
        order = sorted(range(len(rows)), key=lambda i: rank_key(rows[i], typed, postcode))
        note = RANKING_NOTE_KEY if candidates else None
    return {"candidates": [dict(candidates[i]) for i in order], "ranking_note_key": note}


def _relevance(candidate: Mapping[str, Any]) -> Decimal | None:
    """The City's own score as a 0–1 number, or `None` when they gave none.

    Normalised through the same `score_scale` reading `gis.match_word` uses: a
    city publishing 0–100 and one publishing 0–1 must produce one ordering, not
    two. **The number is never returned to a caller and never reaches a screen**
    — `US-INT-042` §1, and `gis.presented` drops it for the same reason.
    """
    raw = candidate.get("score")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None
    text = str(candidate.get("score_scale") or "").strip()
    upper = Decimal("100") if text.endswith("100") else Decimal("1")
    return value / upper if upper else None


#: A field name a `where` may name. The name is TENANT CONFIGURATION
#: (`field_mapping`, `BR-INT-037`) and it is spliced into the clause as an
#: identifier, so it is checked rather than trusted — a quote in it would be the
#: injection `where_clause` escapes everywhere else.
_FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
#: The escape character for a LIKE wildcard the clerk TYPED.
_LIKE_ESCAPE = "\\"


def where_clause(typed: str, field_name: str = "Street") -> str:
    """The `where` a search sends. **The input is escaped, not interpolated.**

    ── 2026-10-07 · `DEF-INT-9843` — IT HAS A CALLER NOW ─────────────────────
    The spelling is the one the PO checked BY HAND against the live Ann Arbor
    layer, which answered *"2670 Sequoia Pkwy, Ann Arbor"*:

        UPPER(Street) LIKE UPPER('%2670 SEQUOIA%')

    ⚠ **`UPPER` ON BOTH SIDES, BECAUSE CASE IS THE STORE'S CHOICE.** A
    FeatureServer's `LIKE` is case-sensitive on many back ends, so a clerk
    typing `2670 sequoia` against a layer holding `2670 Sequoia Pkwy` would get
    *no match* from a perfectly good City.

    ⚠ **A SINGLE QUOTE IN AN ADDRESS IS ORDINARY** — `O'Brien Court` — and
    unescaped it ends the literal and makes the rest of the clause somebody
    else's SQL. ArcGIS `where` is evaluated by the service against its own
    store, so this is their injection rather than ours, which makes it no less
    ours to prevent. Doubling the quote is the SQL-standard escape.

    ⚠ **A `%` OR `_` THE CLERK TYPED IS A CHARACTER, NOT A WILDCARD.** Unescaped,
    `1_2` matches `102`. They are escaped with a backslash and the clause then
    names its escape character — **only when one is present**, so the ordinary
    query is byte-for-byte the one the PO proved against the live service, and a
    back end that is fussy about `ESCAPE` meets it only on the rare address that
    needs it.
    """
    name = str(field_name or "").strip()
    if not _FIELD_NAME.match(name):
        raise ValueError(f"not a field name a where clause may name: {name!r}")
    cleaned = str(typed or "").strip()
    escaped = any(ch in cleaned for ch in "%_\\")
    if escaped:
        cleaned = (
            cleaned.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
    cleaned = cleaned.replace("'", "''")
    clause = f"UPPER({name}) LIKE UPPER('%{cleaned}%')"
    return f"{clause} ESCAPE '{_LIKE_ESCAPE}'" if escaped else clause


def presented(result: Mapping[str, Any]) -> dict[str, Any]:
    """The grouped result, as a screen may see it — dataclasses flattened."""
    return {
        **{key: value for key, value in result.items() if key != "buildings"},
        "buildings": [
            {
                "parcel": one.parcel,
                "address_line": one.address_line,
                "city": one.city,
                "state": one.state,
                "postal_code": one.postal_code,
                "status": one.status,
                "lat": str(one.lat) if one.lat is not None else None,
                "lng": str(one.lng) if one.lng is not None else None,
                "unit_count": one.unit_count,
                "units": [dict(unit) for unit in one.units],
            }
            for one in result.get("buildings", ())
        ],
    }


def candidates_to_rows(candidates: Sequence[Mapping[str, Any]]) -> list[ParcelRow]:
    """The existing inline search's shape → the shape this file ranks.

    ⚠ **A BRIDGE, KEPT DELIBERATELY SMALL AND NAMED AS ONE.** `gis.py`'s
    `search` predates this wave and answers a flat candidate list; the
    reconciliation match reads `ParcelRow`s from a `Snapshot`. One ranking has
    to serve both, so the older shape is converted rather than the ranking being
    written twice.
    """
    return [
        ParcelRow(
            parcel_id=str(one.get("parcel") or ""),
            # ⚠ `point` is what `candidate_from` PRODUCES; `point_id` is read
            # too for a caller that built its own row. Reading only `point_id`
            # put the PARCEL on every unit as its point (`DEF-INT-9845`).
            point_id=str(one.get("point") or one.get("point_id") or one.get("parcel") or ""),
            address_line=str(one.get("address_line") or ""),
            city=one.get("city"),
            state=one.get("state"),
            postal_code=one.get("postal_code"),
            unit_label=one.get("unit"),
            status=one.get("status"),
            lat=one.get("lat"),
            lng=one.get("lng"),
        )
        for one in candidates
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-112 §E (the ten PO rulings of 2026-09-17, decision log of that date)
# generated: 2026-09-17 by the CR-112 GIS build lane
# checklist: A✔ B=PARTIAL(FindTheAddress.tsx still renders a FLAT list — see the report) C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr112_gis_search.py
# exceptions: `candidates_to_rows` bridges the pre-existing inline-search shape rather than rewriting it — named above so it is not mistaken for a second model
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
