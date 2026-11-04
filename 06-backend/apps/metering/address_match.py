# ── Trace ──────────────────────────────────────────────
# Change:   DEF-CUS-6350 — Approve checks the property and the unit before it is
#           pressed. PO ruling 2026-09-23 (decision log, *"RULED: A NEW
#           CONNECTION ONLY WHERE THE ADDRESS IS NOT IN PREMISES — IN ANY
#           STATUS"*, `OQ-CUS-12615` CLOSED), verbatim: *"this si correct
#           understanding"* and *"we dont allow these status - dont create new
#           request even if property is in draft, pending or inactive"*.
# Rules:    CLAUDE.md hard rule 8 (an address lives on `premises` and nowhere
#           else — this READS it and writes nothing) · hard rule 1 (tenant
#           scoping) · NFR-5 (no cap: nothing here slices a result) · B14 rule
#           31 (the `id` travels so a caller can act; `premise_no` and the
#           address are what a screen shows)
# Tests:    06-backend/tests/test_def_cus_6350_approve_checks.py
# Impacts:  apps/customers/seams.py (`premises_matching_address`,
#           `open_builds_for_requests`) · apps/customers/service_request_reads.py
# ───────────────────────────────────────────────────────
"""**IS THIS ADDRESS ALREADY IN PREMISES?** — metering's answer, for a caller
that is about to let somebody create one.

WHY THIS LIVES IN METERING AND NOT WHERE IT IS FIRST CALLED
-----------------------------------------------------------
The first caller is the Approve window on a service request, which is a
customers screen. But **the premises a new connection would create is
metering's write** — the New connect wizard's last button (`BR-MET-112`) — so
the question *"does this address already exist?"* is metering's to answer, once,
and customers asks it through its seam (`apps/customers/seams.py`). A second
matcher written inside customers would be a second opinion about metering's own
table, free to disagree with the first the day either changes.

THE THREE ANSWERS — the owner match's shape, on purpose
-------------------------------------------------------
`premises_owners.resolve_owner_name` already answers *"is this party on file?"*
with `exact` / `near` / `none`, and the PO's decision 3 behind it is *"offer the
match, clerk decides"*. This is the same shape for an ADDRESS:

  * ``exact`` — the tidied address line is identical to one on file, and the
    postcode does not contradict it. **It is in Premises.** No choice is offered;
    under the ruling a new connection is refused there, whatever the property's
    status says.
  * ``near`` — close, not identical: `highland pk` against `Highland Park`.
    **Offered; the clerk decides** whether it is the same place.
  * ``none`` — nothing close. The build may create the address.

HOW TWO SPELLINGS ARE COMPARED — and what was chosen, stated
------------------------------------------------------------
**THE TIDY IS NOT WRITTEN HERE.** `apps.integrations.gis_layer.normalise_street`
already reduces a street line to what two spellings of it share — case,
punctuation, spacing, and the street-type and direction words (`St`/`Street`,
`Ave`/`Avenue`, `N`/`North` …) — and `normalise_postcode` compares the first
five digits of a ZIP as TEXT, so `07001` keeps its zero and `48104-1234` equals
`48104`. They are pure functions with no database and no network, and a third
tidy beside them and the portal's would be exactly the drift B14 rule 43 names.

Then:
  * **exact** = the two tidied lines are equal;
  * **near** = equal once spaces are removed (`highlandpark`), or
    `difflib.SequenceMatcher` ratio **≥ 0.85** on the tidied lines. Worked:
    `highland pk` / `highland park` → 22/24 = **0.917**, near. `12 main street`
    / `21 main street` → 0.857, near — which is why the house NUMBER is also
    required to agree for a near match (a different number is a different
    house, however similar the letters).
  * a **postcode on both sides that differs** rules a row out. A city on both
    sides that differs rules it out when neither side has a postcode.

⚠ **A MISS IS THE SAFE DIRECTION ONLY FOR THE OFFER.** A pair the tidy does not
know simply fails to match, and the clerk is not asked. That is why the answer
carries `compared` — how many rows were actually looked at — so a caller and a
test can tell *nothing close* from *nothing searched* (hard-won law 7, the check
that reports zero over a scope it silently excludes).

WHAT IT SEARCHES — in SQL first, never the whole table in Python
----------------------------------------------------------------
Rows sharing the postcode's five digits, **or** whose address line starts with
the typed line's first word. At a 40,000-account tenant that is a few hundred
rows, not forty thousand. **No `[:N]` slice and no cap** (`NFR-5`): every row the
SQL narrows to is compared. Soft-deleted premises are not in Premises and are
not compared; **every STATUS is** — `active`, `draft`, `pending`, `inactive` —
because the ruling names all four and nothing here reads `premises.status`.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from django.db.models import Q

from apps.integrations.gis_layer import normalise_postcode, normalise_street
from apps.metering import models
from apps.metering.selectors import _tenant_id

MATCH_EXACT = "exact"
MATCH_NEAR = "near"
MATCH_NONE = "none"

#: `SequenceMatcher.ratio()` at or above this is a NEAR match. Chosen from the
#: worked pair in the module docstring and recorded there; moving it moves what
#: a clerk is asked about, so it is one named number rather than a literal.
NEAR_RATIO = 0.85


def tidy_line(raw: Any) -> str:
    """The comparison key for an address line — never stored (see module)."""
    return normalise_street(raw)


def tidy_postcode(raw: Any) -> str:
    return normalise_postcode(raw)


def _house_number(tidied: str) -> str:
    first = tidied.split(" ", 1)[0] if tidied else ""
    return first if any(ch.isdigit() for ch in first) else ""


def same_place(
    line_a: Any,
    line_b: Any,
    *,
    postcode_a: Any = None,
    postcode_b: Any = None,
    city_a: Any = None,
    city_b: Any = None,
) -> str:
    """`exact` · `near` · `none` for ONE pair — the rule every caller shares.

    Public because two lanes need the same verdict about two addresses that are
    NOT both premises: the Approve window also asks whether two open
    applications name the same new address, and a second comparison written
    there would be free to disagree with this one.
    """
    a, b = tidy_line(line_a), tidy_line(line_b)
    if not a or not b:
        return MATCH_NONE
    zip_a, zip_b = tidy_postcode(postcode_a), tidy_postcode(postcode_b)
    if zip_a and zip_b and zip_a != zip_b:
        return MATCH_NONE
    if not (zip_a and zip_b):
        town_a, town_b = tidy_line(city_a), tidy_line(city_b)
        if town_a and town_b and town_a != town_b:
            return MATCH_NONE
    if a == b:
        return MATCH_EXACT
    if _house_number(a) != _house_number(b):
        return MATCH_NONE
    if a.replace(" ", "") == b.replace(" ", ""):
        return MATCH_NEAR
    if SequenceMatcher(None, a, b).ratio() >= NEAR_RATIO:
        return MATCH_NEAR
    return MATCH_NONE


def _candidate(row: models.Premises) -> dict[str, Any]:
    return {
        # B14 rule 31 — the id is for ACTING on the row (a pick), never shown.
        "id": str(row.id),
        "premise_no": row.premise_no,
        # What a clerk calls the place: its name where it has one, else the
        # address line. `highland park` in the PO's own list is both.
        "label": (row.name or "").strip() or row.address_line,
        "address_line": row.address_line,
        "city": row.city,
        "state": row.state,
        "postal_code": row.postal_code,
    }


def premises_matching_address(
    address_line: Any, *, city: Any = None, postal_code: Any = None
) -> dict[str, Any]:
    """`{match, candidates, compared}` — see the module docstring.

    `candidates` is every matching row, closest first: all the `exact` ones when
    there are any (and then `match` is `exact`), otherwise the `near` ones.
    Read-only; takes no actor.
    """
    tidied = tidy_line(address_line)
    if len(tidied) < 3:
        return {"match": MATCH_NONE, "candidates": [], "compared": 0}
    first_word = str(address_line or "").strip().split()[0] if str(address_line or "").strip() else ""
    zip5 = tidy_postcode(postal_code)
    narrowing = Q(address_line__istartswith=first_word)
    if zip5:
        narrowing |= Q(postal_code__startswith=zip5)
    rows = list(
        models.Premises.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
        .filter(narrowing)
        .only("id", "premise_no", "name", "address_line", "city", "state", "postal_code")
        .order_by("premise_no", "id")
    )
    exact: list[dict[str, Any]] = []
    near: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        verdict = same_place(
            address_line,
            row.address_line,
            postcode_a=postal_code,
            postcode_b=row.postal_code,
            city_a=city,
            city_b=row.city,
        )
        if verdict == MATCH_EXACT:
            exact.append(_candidate(row))
        elif verdict == MATCH_NEAR:
            ratio = SequenceMatcher(None, tidied, tidy_line(row.address_line)).ratio()
            near.append((ratio, _candidate(row)))
    if exact:
        return {"match": MATCH_EXACT, "candidates": exact, "compared": len(rows)}
    if near:
        near.sort(key=lambda pair: -pair[0])
        return {
            "match": MATCH_NEAR,
            "candidates": [candidate for _ratio, candidate in near],
            "compared": len(rows),
        }
    return {"match": MATCH_NONE, "candidates": [], "compared": len(rows)}


# ═══════════════════════════════════════════════════════════════════════════
# `CR-177-BRC10` task 1 · `BR-MET-1190` — THE SAME ADDRESS, EXACTLY
# ═══════════════════════════════════════════════════════════════════════════
#
# PO 2026-10-09, verbatim: *"when address is added, we need to check for
# uniquness, exact same address if existing in system then you should promp user
# that eact same address is available"* — and the approved plan's words for
# EXACT: same street, city, state and ZIP, **ignoring capitals, spaces and
# punctuation**.
#
# ⚠ **THIS IS NOT `same_place` ABOVE, AND THE DIFFERENCE IS DELIBERATE.**
# `same_place` also folds street-type and direction words (`Rd` = `Road`,
# `N` = `North`) and compares ZIPs by their first five digits, because the
# Approve window is looking for the SAME PLACE spelled differently. The PO asked
# here for the EXACT address, so `Rd` and `Road` are two addresses to this
# check; folding them would prompt a clerk about a match the PO never asked to
# be prompted about. One key, written once, read by the screen's check AND by
# the save (`metering.services.create_premises`), so the two cannot disagree.
#
# Worked: `101 silver creek rd.` · `Silver Creek` · `TX` · `78611` and
# `101 Silver Creek Rd` · `silver  creek` · `tx` · `78611` → the same key,
# `101 silver creek rd|silver creek|tx|78611`.

_NOT_WORD = re.compile(r"[^0-9a-z]+")


def exact_address_part(raw: Any) -> str:
    """One part, lower-cased, every run of punctuation or spacing → one space."""
    return _NOT_WORD.sub(" ", str(raw or "").lower()).strip()


def exact_address_key(street: Any, city: Any, state: Any, postal_code: Any) -> str:
    """The four parts as ONE comparison key — never stored, never shown."""
    return "|".join(exact_address_part(part) for part in (street, city, state, postal_code))


def premises_with_same_address(
    street: Any,
    city: Any,
    state: Any,
    postal_code: Any,
    *,
    except_id: Any = None,
) -> dict[str, Any] | None:
    """The live premises of THIS tenant whose address is exactly this one, or None.

    RLS and `_tenant_id()` scope it (hard rule 1). Soft-deleted premises are not
    in Premises and are not compared; every STATUS is. ⚠ **NARROWED IN SQL,
    COMPARED IN PYTHON, NO CAP (NFR-5):** the SQL keeps rows whose street starts
    with the same first word (`101`), which at a 40,000-account utility is a
    handful, and every one of those is compared.

    Returns `{id, premise_no, address_line, city, state, postal_code, units,
    status}`. ⚠ **`id` IS FOR THE SCREEN'S *Open it* LINK ONLY (B14 rule 31)** —
    the premise NUMBER and the address are what a clerk reads.
    """
    first = exact_address_part(street).split(" ", 1)[0]
    if not first:
        return None
    wanted = exact_address_key(street, city, state, postal_code)
    rows = (
        models.Premises.objects.filter(
            tenant_id=_tenant_id(), deleted_at__isnull=True, address_line__istartswith=first
        )
        .only("id", "premise_no", "address_line", "city", "state", "postal_code", "status")
        .order_by("premise_no", "id")
    )
    if except_id:
        rows = rows.exclude(pk=except_id)
    for row in rows:
        if exact_address_key(row.address_line, row.city, row.state, row.postal_code) == wanted:
            return {
                "id": str(row.id),
                "premise_no": row.premise_no,
                "address_line": row.address_line,
                "city": row.city,
                "state": row.state,
                "postal_code": row.postal_code,
                "units": units_at_premises_count(row.id),
                "status": row.status,
            }
    return None


def premises_label(premises_id: Any) -> dict[str, Any] | None:
    """The one premises a request resolved to, as the Approve window names it —
    or `None` when the id is not a live premises of this tenant."""
    if not premises_id:
        return None
    row = (
        models.Premises.objects.filter(
            tenant_id=_tenant_id(), pk=premises_id, deleted_at__isnull=True
        )
        .only("id", "premise_no", "name", "address_line", "city", "state", "postal_code")
        .first()
    )
    return _candidate(row) if row is not None else None


#: A build that has not finished — neither `activated` nor `cancelled`.
def _open_states() -> tuple[str, ...]:
    from apps.work import connection_models as work_tables

    return (
        work_tables.DRAFT,
        work_tables.REQUESTED,
        work_tables.IN_PROGRESS,
        work_tables.PARTLY_ACTIVATED,
        work_tables.ON_HOLD,
    )


def builds_for_requests(request_ids: Any, *, open_only: bool = False) -> dict[str, dict[str, Any]]:
    """`{service_request_id: {id, connection_no, state}}` — the build raised
    from each of these applications (the first, where there were several).

    `open_only` keeps the builds that have NOT finished. The Approve window's
    *Open request* row asks for those: two applications for the same NEW
    address would both create that premises at their builds' last button, so
    the second is refused while the first's build is still open. Once the first
    build commits, the premises exists and the address check refuses instead;
    once it is cancelled, nothing is open and nothing refuses.

    Without `open_only` it is the request page's *Approved → build* link, which
    names the build by its NUMBER (B14 rule 31) and carries the id only to act.
    """
    from apps.work import connection_models as work_tables

    ids = [str(value) for value in (request_ids or []) if value]
    if not ids:
        return {}
    rows = work_tables.Connection.objects.filter(
        tenant_id=_tenant_id(), service_request_id__in=ids
    )
    if open_only:
        rows = rows.filter(state__in=_open_states())
    out: dict[str, dict[str, Any]] = {}
    for row in rows.only("id", "service_request_id", "connection_no", "state").order_by(
        "created_at", "id"
    ):
        out.setdefault(
            str(row.service_request_id),
            {"id": str(row.id), "connection_no": row.connection_no, "state": row.state},
        )
    return out


def open_builds_for_requests(request_ids: Any) -> dict[str, dict[str, Any]]:
    """`builds_for_requests(…, open_only=True)` — see there."""
    return builds_for_requests(request_ids, open_only=True)


def units_at_premises_count(premises_id: Any) -> int:
    """How many LIVE units a premises holds — the move-in's *a unit is chosen
    where the premises has units* asks it. Soft-deleted units are not counted:
    an account cannot open on one (`BR-CUS-020`)."""
    if not premises_id:
        return 0
    return models.Unit.objects.filter(
        tenant_id=_tenant_id(), premises_id=premises_id, deleted_at__isnull=True
    ).count()


# ═══════════════════════════════════════════════════════════════════════════
# `CR-200-BRC10` S7–S8 — SUGGESTIONS WHILE TYPING, AND THE APARTMENT
# ═══════════════════════════════════════════════════════════════════════════
#
# PO 2026-10-29, verbatim: *"Question 1 … -A · Question 2 … -A"* — (1A) after
# 4 typed characters, at most 5 suggestions, **street + town + ZIP only, never a
# name or whether anyone lives there**; picking one fills the three boxes and
# runs the check. (2A) after a building with several units the applicant picks
# from that building's unit LABELS (no occupancy), plus *"Mine isn't listed"*,
# and move-in against new connection is judged for THAT unit.
#
# ⚠ **WHY IT IS HERE AND NOT IN `apps/portal`.** The code plan the PO approved
# (*"this is ok"*, same day) keeps ONE address matcher for the portal's Start
# service and the staff Approve window, so the suggestion read and the unit
# read sit beside `premises_matching_address` and both sides change together.
#
# ⚠ **WORD BY WORD, THROUGH THE STAFF SIDE'S ONE MATCHER.** Lane A of the same
# CR built `core.search.matches_every_word`; the suggestion read uses it over
# street, town and ZIP (every word must match one of them), adding only each
# street word's other spellings as an extra way for that word to match.
#
# Worked: `2155 Hem` → words `2155`, `hem` → `2155 Hemlock Dr, Ann Arbor, MI
# 48108`. `hemlock ann` finds it too (street + town). `Hemlock Drive` finds a
# street stored as `Hemlock Dr`, because a typed street word is also tried in
# its other spellings (`STREET_WORDS`, the tidy `same_place` already uses).

#: Below this many typed characters nothing is looked up (PO 1A: *"after 4"*).
SUGGEST_MIN_CHARS = 4
#: At most this many suggestions (PO 1A: *"at most 5"*). A typeahead's display
#: cap — what one drop-down shows — never a cap on what a tenant may hold
#: (`NFR-5`): the applicant narrows by typing another letter.
SUGGESTION_LIMIT = 5

_WORD_SPLIT = re.compile(r"[\s,]+")


def _spellings(word: str) -> set[str]:
    """`drive` → {`drive`, `dr`}: every spelling `STREET_WORDS` folds together."""
    from apps.integrations.gis_layer import STREET_WORDS

    folded = STREET_WORDS.get(word)
    if folded is None:
        return {word}
    return {spelling for spelling, meaning in STREET_WORDS.items() if meaning == folded} | {word}


def suggestion_words(typed: Any) -> list[str]:
    """The typed text as the words each suggestion must match — lower-cased,
    split on spaces and commas, punctuation other than `-` dropped."""
    words = []
    for raw in _WORD_SPLIT.split(str(typed or "").strip().lower()):
        word = "".join(ch for ch in raw if ch.isalnum() or ch == "-")
        if word:
            words.append(word)
    return words


def address_suggestions(typed: Any, *, limit: int = SUGGESTION_LIMIT) -> list[dict[str, Any]]:
    """At most `limit` held addresses matching what was typed, word by word.

    Each row is `{street, city, state, postal_code}` — **and nothing else**:
    no id (B14 rule 31; the guest surface carries none), no premises number,
    no name, no unit, no occupancy (`BR-CWP-021`). A pick is re-resolved by the
    check that follows it, never by an id the browser held. The state travels
    because the ruled example prints it (*"2155 Hemlock Dr, Ann Arbor, MI
    48108"*); it says nothing about who lives there.

    Live premises of THIS tenant (RLS + `_tenant_id()`, hard rule 1), every
    status — the set the check matches, so a suggestion is never an address
    the check would then fail to recognise. Two premises at one address are
    one suggestion (and the check then answers *a person will look at it*).
    """
    if len(str(typed or "").strip()) < SUGGEST_MIN_CHARS:
        return []
    words = suggestion_words(typed)
    if not words:
        return []
    from core.search import matches_any, matches_every_word

    fields = ("address_line", "city", "postal_code")

    def other_spellings(word: str) -> Q:
        either = Q(pk__in=[])  # matches nothing on its own
        for spelling in _spellings(word) - {word}:
            either |= matches_any(spelling, fields)
        return either

    # The staff side's ONE word-by-word matcher (`core.search`, lane A), with
    # the street-word spellings as each word's extra way to match.
    condition = matches_every_word(" ".join(words), fields, also=other_spellings)
    rows = (
        models.Premises.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True)
        .filter(condition)
        .values("address_line", "city", "state", "postal_code")
        .distinct()
        .order_by("address_line", "city", "postal_code", "state")[: max(int(limit), 0)]
    )
    return [
        {
            "street": row["address_line"],
            "city": row["city"],
            "state": row["state"],
            "postal_code": row["postal_code"],
        }
        for row in rows
    ]


def unit_key(label: Any) -> str:
    """`Apt 2B`, `apt. 2-b`, `#2B` and `2b` → `2b` — the comparison key for a
    unit LABEL (`gis_layer.normalise_unit`, the tidy the GIS match already
    uses). Never stored."""
    from apps.integrations.gis_layer import normalise_unit

    return normalise_unit(label)


def units_to_choose(premises_id: Any) -> list[dict[str, Any]]:
    """The units an applicant may pick at a building: LIVE, not a common area,
    in label order. `{id, label}` — the id is for the SERVER to act on and is
    dropped before anything reaches a guest (B14 rule 31). Nothing about who
    lives in any of them (`BR-CWP-021`)."""
    if not premises_id:
        return []
    rows = (
        models.Unit.objects.filter(
            tenant_id=_tenant_id(),
            premises_id=premises_id,
            deleted_at__isnull=True,
            is_common_area=False,
        )
        .only("id", "label")
        .order_by("label", "id")
    )
    return [{"id": str(row.id), "label": row.label} for row in rows]


def unit_matching_label(premises_id: Any, typed: Any) -> dict[str, Any] | None:
    """The ONE live unit at this premises whose label means what was typed
    (`unit_key` on both sides), or None. Two units that tidy to one key are no
    answer — a person decides, as `find_premises` does for two addresses."""
    wanted = unit_key(typed)
    if not wanted:
        return None
    hits = [unit for unit in units_to_choose(premises_id) if unit_key(unit["label"]) == wanted]
    return hits[0] if len(hits) == 1 else None
