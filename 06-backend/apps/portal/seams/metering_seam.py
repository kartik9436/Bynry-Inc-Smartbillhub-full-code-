# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-009 (EP-CWP-03) — the tracked timeline · US-CWP-010 — Track
#           anything · US-CWP-007 — *"someone has already reported this street"*
# Change:   CR-072 (2026-09-04) — the RP- lookup (`by_reference`, `progress_view`)
#           is DELETED; `progress_of` and `street_words` replace it
# Rules:    BR-CWP-012 (the portal reads through the OWNING module's published
#           seam and adds no second copy — the interruption belongs to
#           `metering`, B2 §2) · BR-CWP-024 (a public lookup returns PROGRESS
#           AND NEVER DATA) · BR-CWP-005 (the tenant in context is the tenant on
#           the path — asserted, never assumed)
# Tests:    06-backend/tests/test_us_cwp_010_track.py
# Impacts:  apps/portal/selectors.py (`track`) · apps/metering/interruptions.py
#           ⊕ 2026-09-04, CR-068 wave C: US-CWP-012 — the ADDRESS LOOKUP
#           behind `CWP-008`. Two halves in one seam because both are what
#           the portal reads from `metering`, and neither writes.
# ───────────────────────────────────────────────────────
"""What the portal reads from `metering`: a street, a confirmed interruption's
two facts, and the address lookup.

⚠ **NOTHING HERE WRITES, AND SINCE `CR-072` NOTHING IN THE PORTAL WRITES
`metering` AT ALL.** The guest report used to raise an `interruptions` row
through `apps/portal/services.py`; it raises a service request now, and a CLERK
opens the interruption from the staff app. So this file is the read half of a
seam whose write half no longer exists, which is the narrowest it has ever been.
G81 refuses an ORM write in it.
"""

from __future__ import annotations

import re
from typing import Any

from apps.metering import interruption_service
from apps.metering import models as metering_models
from apps.metering import interruptions as interruption_models
from apps.metering import monthly_usage_reads
from apps.metering import portal_reads
from core.tenancy import current_tenant_id


def _assert_in_context(tenant_id: Any) -> None:
    """BR-CWP-005: a caller asking for one tenant while another is in context is
    a wiring fault, refused here rather than answered with another utility's
    burst main."""
    current = current_tenant_id()
    if current is None or str(current) != str(tenant_id):
        raise RuntimeError(
            f"portal seam asked for tenant {tenant_id} while {current!r} is in context — "
            "BR-CWP-005: the tenant is resolved from the path before anything is read"
        )


# ⚠ **`by_reference` AND `progress_view` WERE DELETED HERE ON 2026-09-04
# (`CR-072`), AND THE DELETION IS THE POINT.** They looked an `RP-` reference up
# on an UNAUTHENTICATED endpoint and turned an interruption into a guest's
# progress card. `CR-072` §4 stops the `RP-` series being customer-facing —
# nothing hands one to a stranger any more — so both were doors with nobody on
# the other side, which is hard-won law 2 read in the mirror: surface that
# nothing reaches is not harmless, it is an unauthenticated read of another
# module's table waiting for a caller. What replaced them is `progress_of`
# below, which takes an ID the request already holds and answers TWO fields.


def progress_of(tenant_id: Any, interruption_id: Any) -> dict[str, Any] | None:
    """The confirmed interruption a report is attached to, as **two facts**, or
    None.

    ⚠ **TWO KEYS, AND THE NARROWNESS IS THE RULE (`BR-CWP-024`).** `status` is
    what a crew moved and `expected_back_on` is when supply is due back — the
    only two things about the utility's operational record a stranger holding a
    report reference has any business reading. The location they get is their
    OWN words off their own request, not the clerk's tidied version, and the
    `RP-` number is not here at all: `BR-CWP-024` gives them ONE reference and
    it is the `SR-`.

    None is a normal answer, not an error: most reports are not attached to
    anything, because most reports are not an outage.
    """
    _assert_in_context(tenant_id)
    if not interruption_id:
        return None
    row = (
        interruption_models.Interruption.objects.filter(
            tenant_id=tenant_id, id=interruption_id
        )
        .only("status", "expected_back_on")
        .first()
    )
    if row is None:
        return None
    return {
        "status": row.status,
        "expected_back_on": row.expected_back_on.isoformat() if row.expected_back_on else None,
    }


def street_words(location_text: Any) -> str | None:
    """`"1408 Elm St, Austin TX 78702"` → `"Elm St"`, or None — `metering`'s own
    small rule, exposed rather than reimplemented.

    ⚠ **IT STAYED IN `metering` WHEN THE REPORT MOVED TO `customers`
    (`CR-072`).** It parses a free-text ADDRESS, and an address is metering's
    (`BR-MET-1161`). Its own docstring states its limits and its one job; the
    portal is now a second caller of the same rule, not a second copy of it.
    """
    return interruption_service.street_words(location_text)


def open_interruption_on_street(tenant_id: Any, location_text: str) -> Any:
    """An interruption still open on this street, or None.

    Half of *"somebody has already reported this street"* (`US-CWP-007` TC-7);
    the other half is `customers_seam.open_report_on_street`, because since
    `CR-072` a report is a service request and MOST streets somebody has told us
    about have no interruption at all.
    """
    _assert_in_context(tenant_id)
    return interruption_service.open_on_street(tenant_id, location_text)


def affected_set(tenant_id: Any, interruption_id: Any) -> dict[str, Any]:
    """The premises an interruption touches — the staff screen's read, served
    through the seam so there is only one implementation of the rule."""
    _assert_in_context(tenant_id)
    return interruption_service.affected_set(interruption_id)


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave C — THE ADDRESS LOOKUP behind CWP-008 (US-CWP-012)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **NOTHING HERE WRITES, AND NOTHING HERE RETURNS A PERSON.** `BR-CWP-021`
# is the reason the return shapes below carry a premises, its units and a list
# of service codes and nothing else: a seam that returned the occupier would
# put the rule one careless serialiser away from being broken.
#
# THE MATCH IS DELIBERATELY FORGIVING AND DELIBERATELY NOT CLEVER.
# `US-CWP-012` §5 says *"Fuzzy; a miss is not a refusal"*, and a miss costs
# nothing — it routes to *a person will look at it*. So the lookup normalises
# case, punctuation and the common street abbreviations, matches on the
# leading part of the address line, and stops. It is not a geocoder and must
# not become one: an address resolver that is confident and wrong sends an
# applicant to the wrong premises' prices.


#: Street words a person shortens without thinking. Normalising them is the
#: whole of the "fuzzy" in US-CWP-012 §5 — nothing here guesses a NUMBER.
_ABBREVIATIONS = {
    "street": "st",
    "court": "ct",
    "road": "rd",
    "avenue": "ave",
    "drive": "dr",
    "lane": "ln",
    "boulevard": "blvd",
    "place": "pl",
    "terrace": "ter",
    "apartment": "apt",
    "unit": "",
    "north": "n",
    "south": "s",
    "east": "e",
    "west": "w",
}


def normalise_address(value: Any) -> str:
    """Lower-cased, punctuation stripped, abbreviations folded, spaces collapsed.

    `31 Palm Ct, Austin TX 78702`, `31 palm court austin tx 78702` and
    `31  PALM  CT.` all normalise to the same string, which is what makes a
    typed address match a stored one without a geocoder.
    """
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [_ABBREVIATIONS.get(word, word) for word in text.split()]
    return " ".join(word for word in words if word)


def _premises_key(row: Any) -> str:
    parts = [row.address_line, row.city, row.state, row.postal_code]
    return normalise_address(" ".join(str(part) for part in parts if part))


def find_premises(tenant_id: Any, address: Any) -> dict[str, Any] | None:
    """The premises this typed address means, or None.

    ⚠ **NONE IS AN ANSWER AND NOT AN ERROR** (`US-CWP-012` TC-2). The caller
    turns it into *a person will look at it*; nothing above this raises.

    Matching is by NORMALISED PREFIX in both directions: the typed address may
    be shorter than the stored one (`31 Palm Ct` against
    `31 Palm Ct, Austin TX 78702`) or longer (somebody pastes an apartment
    number onto the end). A single stored premises that survives both tests is
    the answer; **two survivors are no answer at all** — a lookup that picks one
    of two addresses is exactly the confident-and-wrong resolver the module
    docstring refuses.
    """
    _assert_in_context(tenant_id)
    typed = normalise_address(address)
    if len(typed) < 4:  # nobody's address is three characters; do not scan the tenant
        return None
    rows = list(
        metering_models.Premises.objects.filter(tenant_id=tenant_id).only(
            "id", "address_line", "city", "state", "postal_code", "services_available"
        )
    )
    hits = []
    for row in rows:
        key = _premises_key(row)
        if key and (key.startswith(typed) or typed.startswith(key)):
            hits.append(row)
    if len(hits) != 1:
        return None
    hit = hits[0]
    return {
        "id": str(hit.id),
        "address_line": hit.address_line,
        "city": hit.city,
        "state": hit.state,
        "postal_code": hit.postal_code,
        "services_available": list(hit.services_available or []),
    }


def _premises_view(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "address_line": row.address_line,
        "city": row.city,
        "state": row.state,
        "postal_code": row.postal_code,
        "services_available": list(row.services_available or []),
    }


def find_premises_by_parts(
    tenant_id: Any, street: Any, *, city: Any = None, postal_code: Any = None
) -> dict[str, Any] | None:
    """The premises a STREET + TOWN + ZIP means, or None — `DEF-CWP-9817`.

    ⚠ **THE SAME MATCHER THE STAFF SIDE USES, NOT A THIRD ONE.** The Approve
    window asks `metering.address_match.premises_matching_address` whether a
    request's address — street, town and ZIP as given (`BR-CUS-1091`) — is
    already in Premises. The public door now asks the SAME function the SAME
    question, so a clerk and an applicant cannot get two answers about one
    address. It narrows in SQL (the ZIP's five digits, or the street's first
    word) rather than scanning the tenant in Python as `find_premises` does.

    ⚠ **ONLY ONE EXACT ROW IS AN ANSWER.** `near` (`highland pk` against
    `Highland Park`) is a question a CLERK is asked, never a decision a
    stranger's typing makes; two exact rows are no answer at all, for the
    reason `find_premises` gives. Both read as *a person will look at it*
    (`US-CWP-012` TC-2). ⊕ Offering the nearest matches to the applicant —
    the blueprint's *ADDRESS NOT RECOGNISED* state — is built BEFORE this is
    asked, as suggestions while typing (`address_suggestions` below,
    `CR-200-BRC10`); it read *"is not built here"* until then.

    A street with NO town and NO ZIP is a draft written before step 1 asked
    for them, and is matched the way it always was (`find_premises`).
    """
    _assert_in_context(tenant_id)
    town = str(city or "").strip()
    zip_code = str(postal_code or "").strip()
    if not town and not zip_code:
        return find_premises(tenant_id, street)
    from apps.metering.address_match import MATCH_EXACT, premises_matching_address

    answer = premises_matching_address(street, city=town or None, postal_code=zip_code or None)
    if answer["match"] != MATCH_EXACT or len(answer["candidates"]) != 1:
        return None
    return premises_by_id(tenant_id, answer["candidates"][0]["id"])


def premises_by_id(tenant_id: Any, premises_id: Any) -> dict[str, Any] | None:
    """One live premises' address parts, or None — what a matched draft SHOWS
    (`BR-CUS-1091`: once a premises is matched, the premises is the address)."""
    _assert_in_context(tenant_id)
    if not premises_id:
        return None
    row = (
        metering_models.Premises.objects.filter(
            tenant_id=tenant_id, pk=premises_id, deleted_at__isnull=True
        )
        .only("id", "address_line", "city", "state", "postal_code", "services_available")
        .first()
    )
    return _premises_view(row) if row is not None else None


def address_suggestions(tenant_id: Any, typed: Any) -> list[dict[str, Any]]:
    """`CR-200-BRC10` S7 — at most five held addresses for what was typed,
    street + town + state + ZIP and nothing else. **Metering's matcher, not a
    portal copy** (`address_match.address_suggestions`): the staff Approve
    window and this door read one function."""
    _assert_in_context(tenant_id)
    from apps.metering.address_match import address_suggestions as suggest

    return suggest(typed)


def unit_labels_to_choose(tenant_id: Any, premises_id: Any) -> list[str]:
    """`CR-200-BRC10` S8 — the LABELS of the units an applicant may pick at a
    building, and nothing else: no id (B14 rule 31), no occupancy
    (`BR-CWP-021`)."""
    _assert_in_context(tenant_id)
    from apps.metering.address_match import units_to_choose

    return [unit["label"] for unit in units_to_choose(premises_id)]


def unit_matching_label(tenant_id: Any, premises_id: Any, typed: Any) -> dict[str, Any] | None:
    """`CR-200-BRC10` S8 — the one live unit at this premises whose label is
    what the applicant picked or typed, `{id, label}`, or None. The id stays
    on the server."""
    _assert_in_context(tenant_id)
    from apps.metering.address_match import unit_matching_label as match_label

    return match_label(premises_id, typed)


def units_at(tenant_id: Any, premises_id: Any) -> list[dict[str, Any]]:
    """The premises' units — a label, a rate plan and nothing about who lives
    there (`BR-CWP-021`).

    ⊕ `CR-200-BRC10` — LIVE units only. A soft-deleted unit cannot take an
    account (`BR-CUS-020`), so it is not part of what an applicant asks
    about, and `units_to_choose` (the apartment list) already reads it so."""
    _assert_in_context(tenant_id)
    rows = (
        metering_models.Unit.objects.filter(
            tenant_id=tenant_id, premises_id=premises_id, deleted_at__isnull=True
        )
        .only("id", "label", "unit_no", "rate_plan_id", "is_common_area")
        .order_by("label")
    )
    return [
        {
            "id": str(row.id),
            "label": row.label,
            "rate_plan_id": str(row.rate_plan_id) if row.rate_plan_id else None,
        }
        for row in rows
        if not row.is_common_area
    ]


def connection_sizes(tenant_id: Any, unit_id: Any, services: list[str]) -> dict[str, str | None]:
    """`{service_code: size_class | None}` — each service's RECORDED connection
    size at this unit (metering's own `connection_size_for`, the read the staff
    move-in prices a size-priced fee by). None where nobody recorded one, which
    prices nothing — never a guess. `DEF-CWP-10690`."""
    _assert_in_context(tenant_id)
    if not unit_id:
        return {code: None for code in services}
    from apps.metering import selectors as metering_selectors

    return {code: metering_selectors.connection_size_for(unit_id, code) for code in services}


def service_codes_at(tenant_id: Any, unit_ids: list[str]) -> list[str]:
    """The service codes actually carried at these units — `service_points`,
    which is the fact that decides YES against NOT HERE (`US-CWP-012` TC-4).

    ⚠ **`premises.services_available` IS NOT THIS.** It is a list a clerk typed
    on the premises record; a service point is a metered service that exists.
    Quoting a fee against the first would price a connection nobody has.
    """
    _assert_in_context(tenant_id)
    if not unit_ids:
        return []
    rows = (
        metering_models.ServicePoint.objects.filter(
            tenant_id=tenant_id, unit_id__in=unit_ids, deleted_at__isnull=True
        )
        .select_related("service")
        .only("service__code")
    )
    seen: list[str] = []
    for row in rows:
        code = row.service.code
        if code not in seen:
            seen.append(code)
    return seen


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave H · the readings behind one bill (`CWP-028`, `BR-CWP-071`) and
# the month-against-the-same-month-last-year comparison (`CWP-030`).
#
# ⚠ **BOTH CALL METERING'S OWN PUBLISHED READS.** PO ruling 2026-09-04 —
# *"all the services that are required for Consumer portal … are already
# available for Accounts - account details view"* — and the portal reuse map
# names `monthly_usage_reads.usage_payload` for the usage half. It is the read
# a lane missed this morning while concluding metering published none.
# ═══════════════════════════════════════════════════════════════════════════


def reads_behind_bill(read_ids: list[Any]) -> list[dict[str, Any]]:
    """`BR-CWP-071` — the readings a bill was priced from, and HOW each was taken.

    ⚠ **`metering.selectors.read_dict` IS THE READ AND THIS ADDS NOTHING TO
    IT.** It already composes `prior_value_display` and `current_value_display`
    through `quantity_display.quantity_with_unit`, which REFUSES a bare number
    when the unit is missing (hard rule 3), and it already reports
    `read_method` beside `read_method_origin` so a screen can tell a RECORDED
    method from a DERIVED one from *nothing on file says*. Re-deriving any of
    that here would be a second answer to *"how was this read taken"*.

    ⚠ **THE PROJECTION DROPS EVERY ID** (B14 rule 31). The staff row carries
    `id`, `asset_id`, `cycle_id`, `route_id`, `premise_id`; a customer reads the
    METER's number and nothing else. `accountDetailTabs.tsx` records that even
    eight characters of a uuid is the same breach as all of it.

    ⚠ **`estimated` IS `selectors.read_is_estimated`, NOT A LOCAL TEST.** Two
    inputs decide it — `status="estimated"` and `disposition="estimate"` — and
    that derivation was extracted into one function precisely so two consumers
    could not start disagreeing about which reads are estimates. `US-CWP-033`
    TC-8 turns on it: *"Both taken by a reader. Neither was estimated."*

    An id naming a read that is no longer a lineage head (it was corrected and
    superseded) is simply absent from the answer rather than raising — the bill
    is still readable, and a missing row is a stated absence on the panel.
    """
    from apps.metering import high_consumption
    from apps.metering import models as reads_models
    from apps.metering import selectors as metering_selectors

    wanted = [one for one in read_ids if one]
    if not wanted:
        return []
    rows = (
        reads_models.MeterRead.objects.filter(id__in=wanted)
        .select_related("asset")
        .order_by("read_at")
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        full = metering_selectors.read_dict(row)
        out.append(
            {
                #: The METER's own number (`assets.asset_no`) — the label on the
                #: box in the yard, which is what a customer can go and check.
                "meter": full.get("meter"),
                #: `DEF-CWP-3967` — WHICH SERVICE this meter measures, as a
                #: CODE the catalogue words (`rating.service.*`, the keys the
                #: bill's own service headings already use). The panel read
                #: `W-5026` and `E-5026` — two serial numbers a decimal apart —
                #: where a customer needs to know which line is their water. It
                #: is the read's own linkage (`asset → service_point →
                #: service`), so it names the meter that was actually read
                #: rather than a service guessed from the number's first
                #: letter. `None` for a stock meter with no service point,
                #: which the screen draws as the number alone.
                "service": full.get("service"),
                "read_at": full.get("read_at"),
                "prior_value": full.get("prior_value_display"),
                "current_value": full.get("current_value_display"),
                "usage": full.get("usage_display"),
                "unit": full.get("unit"),
                #: `BR-MET-123`'s pair, both halves, because one without the
                #: other shows a guess as a record.
                "read_method": full.get("read_method"),
                "read_method_origin": full.get("read_method_origin"),
                "estimated": metering_selectors.read_is_estimated(
                    full.get("status"), full.get("disposition")
                ),
                #: `CR-182-BRC10` (PO A2) — BR-MET-020/120 flagged this reading
                #: high; the bill that priced it says *High usage*.
                "high_consumption": high_consumption.is_flagged_high(row.rule_outcomes),
            }
        )
    return out


def usage_same_month_last_year(
    account_id: Any, *, period_end: Any, months: int = 24
) -> list[dict[str, Any]]:
    """`CWP-030`'s **AGAINST LAST AUGUST** — this month beside the same month a
    year ago, per service, each point carrying its unit.

    ⚠ **TWENTY-FOUR MONTHS, NOT TWELVE, AND THE WINDOW IS THE WHOLE POINT.**
    August 2025 and August 2026 are THIRTEEN months apart, so the 12-month
    window `usage_payload` defaults to cannot hold both — it would answer `[]`
    and the panel would state an absence on every account that HAS the data.
    24 is one of the two windows that read model allows (`ALLOWED_WINDOWS`), so
    nothing is widened here and nothing is re-implemented.

    ⚠ **THIS IS `monthly_usage_reads.usage_payload`, THE READ THE REUSE MAP
    NAMES** — the account's stored twelve months (`BR-MET-106`), the same read
    behind the staff Usage tab and behind `CWP-033`. The PO said it in the same
    hour as the ruling above: *"We are mainiting last 12 month usage details on
    account - you canuse it"*. Two bills' usage lines would have been a second
    answer to *"how much water did you use in August"*.

    ⚠ **NOTHING IS SUBTRACTED HERE AND NOTHING IS SCORED.** The two points and
    their unit travel; the SCREEN says *`4,090 → 4,820 gal`*. A percentage
    computed here would be a fourth figure nobody signed.

    A service with no point in either month is omitted rather than shown as a
    zero — `BR-MET-106`'s *an unread month is ABSENT, never a zero*, carried
    through the projection instead of being flattened by it.
    """
    from apps.metering import monthly_usage_reads

    if period_end is None:
        return []
    payload = monthly_usage_reads.usage_payload(account_id, months=months)
    this_label = _month_label_of(period_end)
    last_label = _month_label_of(period_end.replace(year=period_end.year - 1))
    out: list[dict[str, Any]] = []
    for series in payload.get("series") or ():
        service = series.get("service") or {}
        #: `points`, keyed on `month` — that read model's OWN key names, read
        #: out of it rather than guessed. A second spelling here would match
        #: nothing and answer `[]` for every account, silently, which is the
        #: one failure shape no test written from this side would catch.
        points = {row.get("month"): row for row in series.get("points") or ()}
        now = points.get(this_label)
        then = points.get(last_label)
        if now is None or then is None:
            continue
        if now.get("quantity_display") is None or then.get("quantity_display") is None:
            continue
        #: ⚠ **HARD RULE 3, AND THE ABSENCE IS REAL RATHER THAN DEFENSIVE.**
        #: `usage_payload` sets the series `unit` to `None` when the months do
        #: not agree on one (`unit_absence: mixed_units_across_months`,
        #: `OQ-358`). `4,090 → 4,820` with no unit is two bare numbers, so the
        #: row is DROPPED and the panel states the absence — it is never shown
        #: with the unit quietly omitted.
        unit = series.get("unit")
        if not unit:
            continue
        out.append(
            {
                "service": service.get("code"),
                "service_name": service.get("name"),
                "unit": unit,
                "this_year": now.get("quantity_display"),
                "last_year": then.get("quantity_display"),
                "this_year_label": this_label,
                "last_year_label": last_label,
                #: Whether either point was an estimate, so the screen can say
                #: so rather than comparing a measured month against a guess.
                "this_year_estimated": bool(now.get("estimated")),
                "last_year_estimated": bool(then.get("estimated")),
            }
        )
    return out


def _month_label_of(value: Any) -> str:
    """`monthly_usage_reads`' own axis label for a date — `YYYY-MM`.

    Spelled from that module's `_month_label` shape rather than invented: the
    labels this matches on are the ones that read model emits, and a second
    format here would silently match nothing and answer `[]` for every account.
    """
    return f"{value.year:04d}-{value.month:02d}"



# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave H — USAGE, READINGS AND EQUIPMENT (US-CWP-040 · 041 · 043)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **EVERY READ BELOW ALREADY EXISTED, AND THE PORTAL IS THE THIRD SURFACE ON
# IT RATHER THAN A FOURTH IMPLEMENTATION** (PO ruling 2026-09-04: *"all the
# services that are required for Consumer portal - you will find it same set of
# services, endpoints are already available for Accounts - account details
# view"*; the map is `04-docs/05-modules/15-portal/12-reuse-map.md`).
#
# ⚠ **AND THE COST OF NOT LOOKING IS RECORDED ONE FILE OVER.**
# `billing_seam.py`'s usage paragraph concluded that `metering` published no
# per-account consumption read and built the home tile from BILL LINES. The
# read had existed since `CR-030` W3 under a name that lane did not grep for.
# **A second read of the same facts is a second ANSWER**, and the two surfaces
# are a clerk and a customer arguing on the phone.
#
# Nothing here computes. Each function names the published read it calls, and
# the whole of its own body is the tenant assertion plus that call.


def usage_for_account(
    tenant_id: Any, account_id: Any, *, months: int = 12, today: Any = None
) -> dict[str, Any]:
    """`CWP-033` — the stored monthly usage, one series per service.

    `apps.metering.monthly_usage_reads.usage_payload` — the SAME read the staff
    Account details Usage tab (`S21`) and the Overview's usage trend draw, and
    the read the Product Owner pointed at: *"We are mainiting last 12 month
    usage details on account - you canuse it"*.

    ⚠ **READ ITS DOCSTRING BEFORE READING THIS ONE.** `BR-MET-106` is what
    makes the screen possible and it is stated there: a month with no read is
    `quantity: null, absent: true` and **never `0`**, because *"zero usage and
    no read are different claims about a customer"*; a metric over no months is
    `null` with an `absent_reason` rather than an average of nothing; a
    year-on-year figure says `no_prior_reads` rather than `0.0%`.

    ⚠ **THERE IS NO SINGLE TOTAL AND THIS SEAM WILL NEVER ADD ONE.** Gallons
    and therms share a period and nothing else (hard rule 3); the payload
    carries one series per service, each with its own unit, and `CWP-033` draws
    them side by side exactly as the staff tab does.

    `months` is 12 or 24 — the read clamps anything else to its own default
    rather than refusing (`BR-SHL-011`). The portal opens on **12**, which is
    the Overview panel's window and the PO's own words.

    ⚠ **`today` IS PASSED THROUGH AND IT IS NOT OPTIONAL IN PRACTICE**
    (`BR-TEN-043` — the event date is an argument, never a clock read inside a
    read model). `usage_payload` falls back to `timezone.now()` when nobody
    tells it, which makes the axis depend on the machine's clock rather than on
    the request's; the portal edge already resolves `date.today()` once per
    request and hands it down, so every figure on one screen is measured from
    one moment.
    """
    _assert_in_context(tenant_id)
    return monthly_usage_reads.usage_payload(account_id, months=months, today=today)


def readings_for_account(
    tenant_id: Any, account_id: Any, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """`CWP-034` — every committed reading, how it was taken, and any correction.

    `apps.metering.portal_reads.readings_for_account`, which composes the SAME
    derivations the staff reads list uses — `read_is_estimated`,
    `_read_method_of`, `quantity_with_unit` — and invents none of them.

    ⚠ **WHICH BILL A READING FED IS NOT IN THIS ANSWER.** `meter_reads` carries
    no invoice reference at all, so `apps/portal/selectors.py` matches the
    reading's date against the ISSUED bill covering it through `billing_seam`,
    and a reading with no such bill shows an EMPTY cell rather than a guess
    (`US-CWP-041` TC-4).
    """
    _assert_in_context(tenant_id)
    return portal_reads.readings_for_account(account_id, limit=limit)


#: `CWP-034`'s sort vocabulary, RE-EXPORTED rather than retyped
#: (`DEF-CWP-5747`). `apps/portal/api` declares `allowed_sorts` from this, and
#: metering owns what a reading may be ordered by — a second list on the edge
#: would be two answers to one question (hard-won law 5).
READING_SORTS = portal_reads.READING_SORTS
READING_DEFAULT_SORT = portal_reads.READING_DEFAULT_SORT
READING_DEFAULT_DIR = portal_reads.READING_DEFAULT_DIR


def readings_page(
    tenant_id: Any,
    account_id: Any,
    *,
    page: int = 1,
    per: int = 50,
    q: str = "",
    sort: str | None = None,
    dir: str = "desc",
    service: str | None = None,
    bill_windows: Any = (),
) -> dict[str, Any]:
    """`CWP-034` — ONE PAGE of readings, searched and sorted IN THE DATABASE.

    `apps.metering.portal_reads.readings_page` (`DEF-CWP-5747`, `NFR-3`). The
    sibling above answers EVERY reading and is what this route used to call;
    on an AMI deployment that is an interval reading per meter per hour.

    ⚠ **`bill_windows` IS DATA, NOT A QUERY METERING MAY RUN.** Which bill a
    reading fed is a PERIOD match against `billing`'s issued invoices, and
    metering may not read that module. `apps/portal/selectors` asks
    `billing_seam.bill_windows_for` once and hands the periods over as plain
    dates, so the cell, the search and the sort are one derivation without a
    cross-module query.
    """
    _assert_in_context(tenant_id)
    return portal_reads.readings_page(
        account_id,
        page=page,
        per=per,
        q=q,
        sort=sort,
        dir=dir,
        service=service,
        bill_windows=bill_windows,
    )


def high_consumption_alerts(tenant_id: Any, account_ids: list[Any]) -> list[dict[str, Any]]:
    """`CR-182-BRC10` (PO A1) — the open high-consumption alerts on these
    accounts' meters: `[{"service": code, "taken_on": iso date}]`, newest first.

    `apps.metering.high_consumption.open_alerts_for_accounts` — an alert is open
    while its flagged reading is the meter's latest head and not yet billed.
    No id leaves it (B14 rule 31)."""
    from apps.metering import high_consumption

    _assert_in_context(tenant_id)
    return high_consumption.open_alerts_for_accounts(account_ids)


def flagged_high_read_ids(tenant_id: Any, read_ids: list[Any]) -> set[str]:
    """`CR-182-BRC10` (PO A2) — of the readings a bill PRICED, the ones
    BR-MET-020/120 flagged high. Ids in, ids out, and none reaches a screen."""
    from apps.metering import high_consumption

    _assert_in_context(tenant_id)
    return high_consumption.flagged_read_ids(read_ids)


def reading_services(tenant_id: Any, account_id: Any) -> list[dict[str, Any]]:
    """`CWP-034`'s meter tabs, over the WHOLE account (`DEF-CWP-5747`).

    `apps.metering.portal_reads.reading_services`. It is its own question
    because the screen built the tabs from the payload, and the payload is now
    one page — tabs built from a page would silently drop a service that is
    read quarterly.
    """
    _assert_in_context(tenant_id)
    return portal_reads.reading_services(account_id)


def equipment_for_unit(tenant_id: Any, unit_id: Any, *, today: Any = None) -> list[dict[str, Any]]:
    """`CWP-037` — the meters, carts and devices on this unit, by SERIAL.

    `apps.metering.portal_reads.equipment_for_unit`, which joins the ONE asset
    registry (`assets.equipment_reads`, `BR-AST-028`) to metering's own last
    read. The staff Meters tab reads the same registry and says why in its own
    words: *"one implementation of what a meter IS"*.

    ⚠ **A CART'S LAST-READ CELL IS EMPTY, NOT ZERO** (`US-CWP-043` TC-2), and
    **nothing on the row is a database id** (B14 rule 31) — not even eight
    characters of one, which `DEF-3158` records as the same breach as a whole
    uuid.
    """
    _assert_in_context(tenant_id)
    return portal_reads.equipment_for_unit(unit_id, today=today)


def self_read_meters(tenant_id: Any, unit_id: Any, *, today: Any) -> list[dict[str, Any]]:
    """`CWP-035` — the meters a customer at this unit may read, each register
    with its last reading and date (`US-CWP-042`, `DEF-CWP-10175`).

    `apps.metering.customer_reads.meters_for_unit`: the ONE asset registry's
    current assignments narrowed to read devices, joined to metering's own
    lineage heads. Named by SERIAL and addressed by meter number — no database
    id leaves (B14 rule 31). A READ; the write is `services.submit_meter_reading`.
    """
    from apps.metering import customer_reads

    _assert_in_context(tenant_id)
    return customer_reads.meters_for_unit(unit_id, today=today)


def read_window_for_unit(tenant_id: Any, unit_id: Any, *, today: Any) -> dict[str, Any] | None:
    """`CWP-033`'s third tile — *next reading due 2–6 Sep*, or None.

    `apps.metering.portal_reads.open_read_window_for_unit`. ⚠ **THIS IS THE
    READ `billing_seam.reading_window_open` SAID DID NOT EXIST**; that
    docstring named a private service function and stopped, and `ReadWindow` is
    a first-class metering table with the period on it. Corrected 2026-09-04.

    `None` is ordinary — most days have no window open — and the tile closes up
    rather than showing a dash (`BR-CWP-093`).
    """
    _assert_in_context(tenant_id)
    return portal_reads.describe_read_window(
        portal_reads.open_read_window_for_unit(unit_id, today=today), today=today
    )


def billing_frequency_for_unit(tenant_id: Any, unit_id: Any) -> str | None:
    """`CWP-022`'s **YOUR SERVICE** row *Billed* — `Monthly`, or None.

    `apps.metering.portal_reads.billing_frequency_for_unit`, which is the walk
    unit → service point → route → cycle. Nothing is composed here; `None` is
    ordinary and the row closes up (`BR-CWP-093`).
    """
    _assert_in_context(tenant_id)
    return portal_reads.billing_frequency_for_unit(unit_id)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-009@d6d31c46 · US-CWP-010@d6d31c46 (EP-CWP-03 stories) · US-CWP-012@46851178 (EP-CWP-04) · US-CWP-033@8bcd8b6a · US-CWP-035@8bcd8b6a (EP-CWP-07 stories + BR-CWP-071 verbatim + the portal reuse map 12-reuse-map.md)
# generated: 2026-09-04 by the CR-068 wave B build lane · AMENDED 2026-09-04 by the wave C lane (the address lookup) · AMENDED 2026-09-04 by the wave H lane (the readings behind a bill · the year-on-year usage comparison)
# checklist: A✔ B✔ C✔ D✔(guest_api.py · api.py bill_detail/bill_comparison) E✔(CWP-007 · CWP-012 · CWP-028 · CWP-030) F✔ G✔ H=n/a(read side)
# gates: pytest tests/test_us_cwp_010_track.py tests/test_us_cwp_012_availability.py tests/test_us_cwp_033_bill_detail.py tests/test_us_cwp_035_comparison.py · G81 (no ORM write, no foreign `services` import — `interruption_service` is not a `services` module by name and is the OWNING module's published door; `selectors` and `monthly_usage_reads` are published reads)
# exceptions: `usage_same_month_last_year` asks `usage_payload` for 24 months rather than its 12-month default — the two Augusts are 13 months apart, so 12 would answer `[]` on every account that has the data. 24 is one of that read model's OWN two allowed windows; nothing is widened.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
