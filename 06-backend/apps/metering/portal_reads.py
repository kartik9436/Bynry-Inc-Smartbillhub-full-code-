# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-041 (EP-CWP-08) — *Every reading, how it was taken, and why
#           one was corrected*. Screen: CWP-034 (blueprint `P20`)
#           US-CWP-043 — *Meters and equipment at the property*. Screen: CWP-037
#           US-CWP-040 — *Usage* (CWP-033) reads `monthly_usage_reads` and needs
#           only the read WINDOW from here
# Change:   CR-068 wave H (2026-09-04) · PO ruling of the same day: *"all the
#           services that are required for Consumer portal - you will find it
#           same set of services, endpoints are already available for Accounts -
#           account details view"* (04-docs/05-modules/15-portal/12-reuse-map.md)
# Rules:    BR-CWP-071 (how a reading was taken is shown as prominently as the
#           number, estimation included) · BR-CWP-072 (why a read was corrected,
#           and by how much) · BR-CWP-069 (a superseded read must not leave the
#           customer charged twice) · BR-CWP-073 (equipment is what an
#           unmeasured service is billed on) · BR-MET-016/053 (lineage HEADS
#           only; a correction is a new row and the old one is not demoted) ·
#           BR-MET-028 (an estimate carries consumption, not a dial figure) ·
#           BR-MET-144 (a quantity displays at most two decimals) ·
#           CLAUDE.md hard rule 3 (a consumption ALWAYS carries its unit) ·
#           BR-TEN-043 (the event date is an argument, never a clock read here)
# Tests:    06-backend/tests/test_us_cwp_041_readings.py ·
#           06-backend/tests/test_us_cwp_043_equipment.py
# Impacts:  apps/portal/seams/metering_seam.py → apps/portal/selectors.py →
#           apps/portal/api.py (`GET portal/accounts/{id}/readings` ·
#           `/equipment` · `/usage`)
# ───────────────────────────────────────────────────────
"""What a CUSTOMER is shown of their own meter readings and equipment.

READ-ONLY, and a separate module from `selectors.py` for the reason
`monthly_usage_reads.py` and `connection_reads.py` are separate from it: one
audience, one file, and two lanes can work beside each other without sharing
5,000 lines.

════════════════════════════════════════════════════════════════════════════
EVERY DERIVATION HERE IS ONE THE STAFF SURFACES ALREADY USE
════════════════════════════════════════════════════════════════════════════
The portal is the third surface on these reads, not a fourth implementation of
them (`12-reuse-map.md`). Nothing below computes a consumption, a threshold or
an estimate:

  * *is this head an estimate* → `selectors.read_is_estimated`, the ONE
    derivation billing and the reads list already share;
  * *how was it collected* → `selectors._read_method_of`, which reports
    `recorded` / `derived` / `not_stated` so a screen can never show a guess as
    a record;
  * *what did it use* → the STORED `consumption`, rendered by
    `quantity_display.quantity_with_unit` — the same pair `read_dict` serves;
  * *which meters are here* → `seams.equipment_on_unit` onto the ONE asset
    registry (`BR-AST-028`), never a second idea of what a meter is.

⚠ **`assets.selectors.asset_reads` WAS THE OBVIOUS CANDIDATE AND IT IS NOT
ENOUGH — CHECKED, NOT ASSUMED.** That read backs the staff Meters tab's nested
read log and folds BR-AST-029's typed records per date; it serves `reading`,
`consumption`, `unit`, `source` and `status`. **It carries none of the three
facts `US-CWP-041` exists for**: the METHOD in words (`read_method` +
its origin), the CORRECTION pair with its size, and the bill the reading fed.
So this module composes those from the same rows through the same published
derivations rather than widening a fold five staff callers depend on.

════════════════════════════════════════════════════════════════════════════
WHAT THIS MODULE DELIBERATELY DOES NOT ANSWER
════════════════════════════════════════════════════════════════════════════
⚠ **WHICH BILL A READING FED IS NOT HERE, AND IT CANNOT BE.** `meter_reads`
carries no invoice reference — `ReadCorrection.invoice_id` is the module's only
metering→billing reference and it exists for a CORRECTION, not for a routine
read. The portal matches the reading's date against the ISSUED bill whose
period covers it (`apps/portal/selectors.py`), which is a billing read through
billing's own seam. Metering serves the DATE and stops; a read with no such
bill shows an EMPTY cell, never a guess (`US-CWP-041` TC-4).

⚠ **`awaiting_review` IS NOT SERVED, AND ITS ABSENCE IS SCHEMA RATHER THAN
SCOPE.** `meter_read.review_state` and `meter_read.source = 'portal'` are
declared as **GAP** columns in `US-CWP-042` §5 and that story is wave 3. No row
in this product can hold either value today, so a field here would be a state
nothing sets and a screen rendering it would be dead UI (hard-won law 2).
Decision log 2026-09-04.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.db.models import Case, CharField, F, Q, Value, When
from django.db.models.functions import Cast, Coalesce, TruncDate

from apps.metering import high_consumption, models, quantity_display, seams, selectors

# ═══════════════════════════════════════════════════════════════════════════
# 1 · HOW A READING WAS TAKEN — `BR-CWP-071`
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THESE ARE CODES AND NOT SENTENCES, AND THAT IS B14 RULE 35.** *Read by a
# meter reader* is written by eleven catalogues in eleven languages; a server
# that shipped the English would make ten of them impossible. The code is what
# a screen keys on and what a test asserts.
#
# ⚠ **AND THE ORDER OF THE TESTS BELOW IS THE RULE.** A corrected estimate is
# the one a customer rings up about, so it beats every other reading of the
# same row: `BR-CWP-071` says the estimation must be visible *including that
# the next real reading corrects it*, and a row that showed only *Read by a
# meter reader* would hide exactly that.

#: The head is an estimate that a later real read has NOT yet replaced.
HOW_ESTIMATED = "estimated"
#: The head is a real read that REPLACED an estimate — `US-CWP-041` TC-2.
HOW_ESTIMATED_CORRECTED = "estimated_corrected"
#: The customer sent it in themselves (`self_read`, `BR-MET-142`'s method).
HOW_SELF_READ = "self_read"
#: A person went and looked — walk-by, drive-by, mobile, manual, field visit.
HOW_READER = "reader"
#: The meter told us — AMI or AMR.
HOW_AUTOMATIC = "automatic"
#: Nothing on file says how it was collected, and the product refuses to invent
#: it (`BR-MET-123`: `source='import'` is a TRANSPORT and lands here).
HOW_NOT_STATED = "not_stated"

#: `read_methods` codes that mean *a person went and looked*. The tenant's own
#: list is the authority (`BR-AST-043`); these are the seeded codes and an
#: unknown method falls through to `not_stated` rather than being guessed at.
_READER_METHODS = frozenset({"walk_by", "drive_by", "mobile", "manual", "field_visit"})
_AUTOMATIC_METHODS = frozenset({"ami", "amr"})
_SELF_READ_METHODS = frozenset({"self_read"})


def _how_taken(read: Any, *, method: str | None, estimated: bool, corrected: bool) -> str:
    """One of the six codes above, in the order `BR-CWP-071` implies."""
    if corrected:
        return HOW_ESTIMATED_CORRECTED
    if estimated:
        return HOW_ESTIMATED
    detail = getattr(read, "source_detail", None)
    if method in _SELF_READ_METHODS or detail == "self_read":
        return HOW_SELF_READ
    if method in _AUTOMATIC_METHODS or getattr(read, "source", None) == "ami":
        return HOW_AUTOMATIC
    if method in _READER_METHODS or getattr(read, "source", None) == "manual":
        return HOW_READER
    return HOW_NOT_STATED


def _superseded_rows(tenant_id: Any, head_ids: list[Any]) -> dict[str, list[Any]]:
    """The rows each of these heads REPLACED, keyed by head id — ONE query.

    ⚠ **NOT `_read_heads()`.** A superseded row is by definition not a head;
    reading it is the only way to say *what the estimate said before it was
    corrected*, which is the whole of `BR-CWP-072`. It is read and never
    written (hard rule 4 — a correction is a new row and this one stays put).
    """
    if not head_ids:
        return {}
    rows = models.MeterRead.objects.filter(
        tenant_id=tenant_id, superseded_by_id__in=list(head_ids)
    ).order_by("read_at", "id")
    out: dict[str, list[Any]] = {}
    for row in rows:
        out.setdefault(str(row.superseded_by_id), []).append(row)
    return out


def _correction_view(head: Any, replaced: list[Any]) -> dict[str, Any] | None:
    """`BR-CWP-072` — why a read was corrected **and by how much**, or None.

    The size is the pair of figures, never a sentence: *estimated 144,600,
    corrected to 144,130 when the meter was read on 3 July*. Eleven catalogues
    write that sentence from these five keys.

    ⚠ **`estimated_reading` IS OFTEN `None`, AND THAT IS `BR-MET-028` RATHER
    THAN A GAP.** An estimate produced by the estimation engine carries a
    CONSUMPTION and no dial figure at all, because nobody read a dial. When the
    figure is absent the catalogue writes the shorter sentence — *we estimated
    your usage and the reading on 3 July corrected it* — and never a `0`.
    """
    estimate = next(
        (row for row in replaced if selectors.read_is_estimated(row.status, row.disposition)),
        None,
    )
    if estimate is None:
        return None
    return {
        "estimated_reading": (
            str(estimate.current_value) if estimate.current_value is not None else None
        ),
        "estimated_reading_display": quantity_display.quantity_text(estimate.current_value),
        "estimated_used": quantity_display.quantity_with_unit(estimate.consumption, estimate.unit),
        "corrected_to": str(head.current_value) if head.current_value is not None else None,
        "corrected_to_display": quantity_display.quantity_text(head.current_value),
        #: ⚠ **THE DAY THE METER WAS ACTUALLY READ, NOT THE PERIOD THE READING
        #: BELONGS TO.** Both rows carry `read_at = 30 June` — that is the
        #: period's own date and it is the same on the estimate and on its
        #: replacement — while the estimate's `superseded_at` is **3 July**,
        #: the day somebody went and looked. The story's sentence says *"when
        #: the meter was read on 3 July"*, so it is the supersede stamp that is
        #: wanted; `read_at` is the fallback for a correction that recorded no
        #: stamp, and it is never wrong, only vaguer.
        "corrected_on": (
            estimate.superseded_at.date().isoformat()
            if estimate.superseded_at
            else (head.read_at.date().isoformat() if head.read_at else None)
        ),
        #: ⚠ **THE REASON IS ON THE ROW THAT WAS SUPERSEDED, NOT ON ITS
        #: REPLACEMENT.** `superseded_by_id`, `superseded_at` and
        #: `supersede_reason` are the three columns B2 r8 permits UPDATEing on a
        #: committed read, and all three are written on the OLD row: it is the
        #: one pointing forward. A first draft read them off the head and got
        #: `None` every time — the correction had no reason and nothing said so.
        "reason": estimate.supersede_reason,
    }


def readings_for_account(
    account_id: Any, *, limit: int | None = None, channel: str | None = None
) -> list[dict[str, Any]]:
    """`CWP-034` — every committed reading on this account's meters, NEWEST FIRST.

    ⚠ **HEADS ONLY** (`BR-MET-016`/`053`): a corrected reading is represented by
    its correction, and the estimate it replaced appears as that row's
    `correction` block rather than as a second line a customer would count
    twice. That is `BR-CWP-069` held at the display layer — *the customer is
    never charged twice for the same water*, and the list must not imply they
    were.

    ⚠ **`used_since` IS THE STORED `consumption`, RENDERED — NEVER RECOMPUTED**
    (`US-CWP-041` TC-8). A meter that passed its maximum has its rollover
    handled by metering's own validation at commit; a screen or a seam
    subtracting two dial figures would produce a NEGATIVE for exactly the
    customer whose meter rolled over. Nothing here subtracts anything.

    ⚠ **EVERY QUANTITY CARRIES ITS UNIT AND NONE IS SERVED BARE** (hard rule 3,
    TC-9). `quantity_with_unit` returns `None` rather than a bare number when
    the unit is missing, and the screen dashes the cell.

    `channel` defaults to the flat meter's single register (`total`), because a
    customer's question is *what did my meter say* and a TOU window or an
    export register is a different quantity of the same unit (`read_type_of`'s
    own reasoning). Pass `None` explicitly for every channel.

    ⚠ **PREFER `readings_page` (`DEF-CWP-5747`, 2026-09-19).** This function
    answers EVERY reading, and on an AMI deployment — an interval reading per
    meter per hour — that is unbounded in the one place it bites. It stays
    because `limit=N` is a legitimate question (the home page asks for the last
    few) and because three callers ask it; `GET portal/accounts/{id}/readings`
    no longer does.
    """
    rows = _reading_head_queryset(account_id, channel=channel)
    if limit is not None:
        rows = rows[: max(0, int(limit))]
    heads = list(rows)
    return _reading_rows(heads)



def _reading_rows(heads: list[Any]) -> list[dict[str, Any]]:
    """THE reading row, built once — `readings_for_account` and `readings_page`
    both compose it and neither has a second idea of what a reading looks like.

    ⚠ **EXTRACTED RATHER THAN COPIED (`DEF-CWP-5747`, 2026-09-19), AND THE
    REASON IS HARD-WON LAW 5.** Two spellings of one row, one page apart, is
    how a list and a card start disagreeing about what a meter said; the
    paging path needed the same eleven derivations and would otherwise have
    grown its own.

    ⚠ **THE TWO BULK READS RIDE WITH IT.** `_superseded_rows` answers the
    correction block for the whole set in ONE query and
    `service_codes_for_points` answers the service for the whole set in two —
    both are `DEF-1549`'s shape and both are per PAGE now rather than per
    tenant-history.
    """
    tenant_id = selectors._tenant_id()
    replaced_by_head = _superseded_rows(tenant_id, [head.id for head in heads])
    #: ⚠ **WHICH METER — AND THE SERVICE IS HALF OF THAT ANSWER
    #: (`DEF-CWP-3990`, 2026-09-05).** The serial identifies the box on the
    #: wall; the SERVICE is what a customer calls it. Until this commit the row
    #: carried neither to a screen, so an account with two meters listed the
    #: electric read and the water read on the same date with nothing on either
    #: row saying which was which.
    #:
    #: **ONE BULK READ, NOT ONE PER ROW** — `service_codes_for_points` answers
    #: the whole set in two queries and exists because `service_point_ref` cost
    #: two round trips EACH (`DEF-1549`). Twenty-six readings would otherwise be
    #: fifty-two lookups for one column.
    #:
    #: The CODE travels and nothing here writes the service's name: the tenant's
    #: own name for it is `tenancy.Service.name`, which `apps/portal/selectors`
    #: joins on, and an English word shipped from here would make ten of the
    #: eleven catalogues impossible (B14 rule 35).
    service_by_point = selectors.service_codes_for_points(
        {head.asset.service_point_id for head in heads if head.asset.service_point_id}
    )

    out: list[dict[str, Any]] = []
    for head in heads:
        replaced = replaced_by_head.get(str(head.id), [])
        correction = _correction_view(head, replaced)
        estimated = selectors.read_is_estimated(head.status, head.disposition)
        method = selectors._read_method_of(head)
        out.append(
            {
                #: ⚠ **NO `read_id` AND NO `asset_id`** (B14 rule 31). The row is
                #: identified on screen by its DATE and the meter's SERIAL, both
                #: of which a customer can check against the box on the wall.
                "taken_on": head.read_at.date().isoformat() if head.read_at else None,
                #: The meter this reading is of, by its serial and then by the
                #: utility's own number — never by a database id.
                "meter_serial": getattr(head.asset, "serial_no", None),
                "meter_no": getattr(head.asset, "asset_no", None),
                #: …and WHICH SERVICE that meter stands on, as a code. `None` is
                #: an ordinary answer (a device on no service point) and the
                #: screen then names the meter by its serial alone.
                "meter_service": (
                    service_by_point.get(str(head.asset.service_point_id))
                    if getattr(head.asset, "service_point_id", None)
                    else None
                ),
                #: The dial figure. `None` on an estimate (`BR-MET-028`), which
                #: the screen dashes rather than filling with a zero.
                "reading": str(head.current_value) if head.current_value is not None else None,
                "reading_display": quantity_display.quantity_text(head.current_value),
                #: Used since the reading before — STORED, with its unit.
                "used_since": (
                    str(head.consumption) if head.consumption is not None else None
                ),
                "used_since_display": quantity_display.quantity_with_unit(
                    head.consumption, head.unit
                ),
                "unit": head.unit,
                #: `BR-CWP-071` — a CODE the catalogue turns into words.
                "how": _how_taken(head, method=method["read_method"], estimated=estimated,
                                  corrected=correction is not None),
                #: …and the record behind it, so a screen can be precise without
                #: this module writing English. `read_method_origin` is
                #: `recorded` · `derived` · `not_stated` (`BR-MET-123`).
                "read_method": method["read_method"],
                "read_method_origin": method["read_method_origin"],
                "estimated": estimated,
                #: `CR-182-BRC10` (PO A3) — BR-MET-020/120 flagged this reading
                #: HIGH. The screen tags the row *High consumption alert*; the
                #: flag is the reading's own stored outcome, so staff and
                #: customer see the same set (`high_consumption.is_flagged_high`).
                "high_consumption": high_consumption.is_flagged_high(head.rule_outcomes),
                #: `BR-CWP-072` — the reason AND the size, or None.
                "correction": correction,
                "channel": head.channel,
                #: ⚠ **`on_bill` IS PRESENT ONLY WHERE THE QUERY ANNOTATED IT**
                #: (`DEF-CWP-5747`). `readings_page` resolves the covering bill in
                #: SQL, for the PAGE and for the sort; `readings_for_account` does
                #: not, and `apps/portal/selectors` fills the key for that path as
                #: it always has. A key that is sometimes absent would be two
                #: shapes of one row, so it is written on every row and is `None`
                #: where nothing annotated it.
                "on_bill": getattr(head, "on_bill", None) or None,
            }
        )
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 1b · ONE PAGE OF READINGS — `DEF-CWP-5747` (`NFR-3`)
#
# ⚠ **THIS EXISTS BECAUSE `CWP-034` IS THE ONE PORTAL LIST THAT IS GENUINELY
# UNBOUNDED.** A customer has a dozen bills and three meters; an AMI
# deployment writes an interval reading per meter per HOUR, so a two-year
# account is ~17,000 rows and `GET accounts/{id}/readings` served every one of
# them so a browser could search, sort and slice them. `NFR-3` asks for
# universal SERVER pagination and `NFR-5` forbids answering it with a cap.
#
# ⚠ **SEARCH AND SORT COME WITH THE PAGE OR THE FIX IS A DEFECT.** The whole
# reason `DEF-CWP-5747` was filed rather than half-fixed on 2026-09-18 is
# written into its own row: *"asking the server for one page while search, sort
# and chips stay in the browser makes every one of them silently search one
# page of N"*. So every predicate the screen owned moves into the query below,
# and the SERVICE TABS move with them — those are built from the whole set too,
# and a tab list built from one page would lose a service.
# ═══════════════════════════════════════════════════════════════════════════

#: The service tab a reading with no service point belongs to. It is a KEY the
#: catalogue words, never a word this module wrote (B14 rule 35), and it exists
#: because a reading a customer cannot reach is worse than an oddly-named tab.
UNASSIGNED_SERVICE = "unassigned"

#: What `?sort=` may name, and the COLUMNS each one orders by. Every one of them
#: is real SQL: `meter` is the serial falling back to the utility's own number
#: (which is what the screen sorted on), `bill` is the annotation below.
#: ⚠ **`how` IS ABSENT ON PURPOSE** — the screen does not offer it, and a sort
#: the UI cannot ask for is surface with no caller (hard-won law 2).
READING_SORTS: dict[str, tuple[str, ...]] = {
    "taken": ("read_at",),
    "meter": ("meter_ref",),
    "reading": ("current_value",),
    "used": ("consumption",),
    "bill": ("on_bill",),
}
#: Newest first, which is the order the screen opens on and the order a
#: customer expects before they touch anything (B14 rule 13's *clear* step).
READING_DEFAULT_SORT = "taken"
READING_DEFAULT_DIR = "desc"


def _reading_head_queryset(account_id: Any, *, channel: str | None = None) -> Any:
    """Every committed head on this account's meters, newest first, LAZY.

    ⚠ **LAZY IS THE WHOLE POINT (`NFR-3`).** This is the query
    `readings_for_account` has always built; it is named so `readings_page`
    can put a `LIMIT` on it instead of building every row and throwing all but
    fifty away.
    """
    rows = (
        selectors._read_heads()
        .filter(account_id=account_id)
        .select_related("asset")
        .order_by("-read_at", "-id")
    )
    if channel is not None:
        rows = rows.filter(channel=channel)
    return rows


def _covering_bill_case(windows: Any) -> Any:
    """The ISSUED bill whose service period covers each reading, as ONE
    annotation — so the cell, the search and the sort are one derivation.

    ⚠ **THE WINDOWS ARE HANDED IN AS PLAIN DATES AND A NUMBER, AND THAT IS THE
    MODULE BOUNDARY DOING ITS JOB.** `meter_reads` carries no invoice
    reference (`billing_seam.bill_number_covering` says so in its own words),
    so the correspondence is a period match — and metering may not query
    `billing`. `apps/portal/selectors` asks `billing_seam` for the account's
    issued periods in ONE query and passes them here as data.

    ⚠ **THIS REPLACES AN N+1 OVER DISTINCT DATES.** `apps/portal/selectors.
    account_readings` called `bill_number_covering` once per distinct
    `taken_on` in the payload; on an AMI account that is one statement per DAY.
    The `CASE` costs none.

    ⚠ **FIRST MATCH WINS, IN THE ORDER THE CALLER GAVE**, which is the same
    `-issued_at, -service_date` precedence `bill_number_covering` applied when
    two issued periods overlap.
    """
    branches = [
        When(
            read_at__date__gte=window["from"],
            read_at__date__lte=window["to"],
            then=Value(window["number"]),
        )
        for window in windows
        if window.get("number") and window.get("from") and window.get("to")
    ]
    if not branches:
        return Value(None, output_field=CharField())
    return Case(*branches, default=Value(None), output_field=CharField())


def _reading_search(needle: str, windows: Any) -> Any:
    """What a typed string looks at — **the fields a customer can SEE**.

    The screen's own predicate, moved into SQL unchanged in what it matches:
    the date, the meter's serial, the utility's meter number, the tenant's own
    name for the service, and the bill number the reading fed.

    ⚠ **THE DATE IS MATCHED AS THE TEXT THE SCREEN PRINTS.** `taken_on` is an
    ISO day, so `2026-08` and `08-14` both find rows exactly as the browser's
    `includes` did. `TruncDate` then `Cast` spells `YYYY-MM-DD` on both
    PostgreSQL and SQLite — checked on both, because `config/settings/test.py`
    is SQLite and hard-won law 14 is what happens when a backend difference is
    assumed rather than run.

    ⚠ **THE BILL NUMBER IS MATCHED THROUGH ITS PERIOD, NOT THROUGH A JOIN**
    (there is no join to make). A needle matching an issued bill's number
    widens the predicate by that bill's own date window, which is exactly the
    set of readings whose cell prints it.

    ⚠ **THE SERVICE IS MATCHED ON THE TENANT'S OWN WORD** — `tenancy.Service.
    name`, which is what the screen draws. Matching the CODE instead would mean
    a customer typing what they can read finds nothing (`DEF-CWP-3969`'s shape).
    """
    condition = (
        Q(asset__serial_no__icontains=needle)
        | Q(asset__asset_no__icontains=needle)
        | Q(asset__service_point__service__name__icontains=needle)
        | Q(taken_text__icontains=needle)
    )
    lowered = needle.lower()
    for window in windows:
        number = window.get("number") or ""
        if lowered in number.lower() and window.get("from") and window.get("to"):
            condition |= Q(read_at__date__gte=window["from"], read_at__date__lte=window["to"])
    return condition


def reading_services(account_id: Any, *, channel: str | None = None) -> list[dict[str, Any]]:
    """The drawing's meter tabs — **over the WHOLE account, never over a page**.

    ⚠ **THIS IS THE HALF OF `DEF-CWP-5747` THAT IS NOT SEARCH, SORT OR
    PAGING.** `Readings.tsx` built its tab list from the payload it held, and
    the payload was every reading the account had ever taken. Serve it one page
    and the tabs become *the services that happen to appear in the newest
    fifty rows* — an electric meter read once a quarter would simply lose its
    tab, silently, with every test green. So the set question is answered by
    its own query.

    Two facts per service and both are cheap: the tenant's own NAME for it, and
    how many distinct meters answered on it (the screen brings the meter column
    back when that is not one).
    """
    rows = (
        _reading_head_queryset(account_id, channel=channel)
        .annotate(meter_ref=Coalesce("asset__serial_no", "asset__asset_no"))
        .values_list(
            "asset__service_point__service__code",
            "asset__service_point__service__name",
            "meter_ref",
        )
        .distinct()
    )
    order: list[str] = []
    named: dict[str, str | None] = {}
    meters: dict[str, set[str]] = {}
    for code, name, reference in rows:
        key = code or UNASSIGNED_SERVICE
        if key not in named:
            order.append(key)
            named[key] = name
            meters[key] = set()
        if reference:
            meters[key].add(reference)
    return [
        {"code": key, "name": named.get(key), "meters": sorted(meters.get(key) or ())}
        for key in order
    ]


def readings_page(
    account_id: Any,
    *,
    page: int = 1,
    per: int = 50,
    q: str = "",
    sort: str | None = None,
    dir: str = READING_DEFAULT_DIR,
    service: str | None = None,
    bill_windows: Any = (),
    channel: str | None = None,
) -> dict[str, Any]:
    """ONE PAGE of readings, searched, filtered and sorted **in the database**.

    Returns `{"readings": [...one page...], "count": <the whole set>}`.

    ⚠ **`count` IS A `COUNT(*)` OVER THE SEARCHED SET**, so the footer under a
    search says how many readings match rather than how many are on screen —
    which is the figure `DEF-NOT-5746` records a queue tab losing when it
    counted its own page.

    ⚠ **NO CAP OF ANY KIND (`NFR-5`).** `per` is the caller's, clamped by the
    edge to the IS-2 page-size vocabulary, and `page` beyond the end returns an
    empty page rather than refusing — `BR-SHL-011`'s *clamp, never error* is
    applied by the edge, which is the layer that knows the count.

    ⚠ **THE ORDER ALWAYS ENDS IN `-id`** (IS-2): two readings taken on one day
    on one meter would otherwise be free to swap between page 1 and page 2, and
    a customer would see one row twice and another not at all.
    """
    per = max(1, int(per))
    page = max(1, int(page))
    windows = list(bill_windows or ())
    rows = (
        _reading_head_queryset(account_id, channel=channel)
        .annotate(meter_ref=Coalesce("asset__serial_no", "asset__asset_no"))
        .annotate(on_bill=_covering_bill_case(windows))
        .annotate(taken_text=Cast(TruncDate("read_at"), CharField()))
    )
    if service:
        rows = (
            rows.filter(asset__service_point__isnull=True)
            if service == UNASSIGNED_SERVICE
            else rows.filter(asset__service_point__service__code=service)
        )
    needle = (q or "").strip()
    if needle:
        rows = rows.filter(_reading_search(needle, windows))
    total = rows.count()
    columns = READING_SORTS.get(sort or "", READING_SORTS[READING_DEFAULT_SORT])
    prefix = "-" if (dir or READING_DEFAULT_DIR) == "desc" else ""
    # ⚠ **NULLS LAST IN BOTH DIRECTIONS, WHICH IS THE BROWSER'S OWN RULE
    # MOVED RATHER THAN CHANGED.** `compareValues` in
    # `portal/components/listTable.tsx` sorts `null` LAST both ways and says
    # why: *"a missing date is not 'earliest', it is unknown, and burying it
    # under a descending sort would hide the row"*. An unbilled reading has no
    # bill number and an estimate has no dial figure, so this is the ordinary
    # case on two of the five columns rather than an edge.
    ordering = [
        F(column).desc(nulls_last=True) if prefix else F(column).asc(nulls_last=True)
        for column in columns
    ]
    heads = list(rows.order_by(*ordering, "-id")[(page - 1) * per : (page - 1) * per + per])
    return {"readings": _reading_rows(heads), "count": total}


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE EQUIPMENT AT THE PROPERTY — `US-CWP-043`, `BR-CWP-073`
# ═══════════════════════════════════════════════════════════════════════════


def equipment_for_unit(unit_id: Any, *, today: date | None = None) -> list[dict[str, Any]]:
    """`CWP-037` — every asset on this unit, with the date it was last read.

    Two published reads joined and nothing else: `seams.equipment_on_unit`
    (assets owns the registry — B2 r4) and `selectors.latest_read_for_asset`
    (metering owns `meter_reads`). The join is here because metering is the
    module that may hold both.

    ⚠ **A CART HAS NO LAST READ AND THE CELL IS EMPTY, NOT ZERO**
    (`US-CWP-043` TC-2). `latest_read_for_asset` answers `None` for an asset
    nobody ever read, and `None` travels the whole way to the screen — a `0`
    would tell a customer their cart measured nothing.

    ⚠ **NO `asset_id` LEAVES THIS FUNCTION** (B14 rule 31). It is used to ask
    for the read and dropped; the visible identifier is the serial.
    """
    rows = seams.equipment_on_unit(unit_id, today=today)
    out: list[dict[str, Any]] = []
    for row in rows:
        asset_id = row.get("asset_id")
        last = selectors.latest_read_for_asset(asset_id) if asset_id else None
        item = {key: value for key, value in row.items() if key != "asset_id"}
        item["last_read_on"] = (last or {}).get("read_at")
        out.append(item)
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 3 · WHEN THE NEXT READING IS DUE — `CWP-033`'s third tile
# ═══════════════════════════════════════════════════════════════════════════


def scheduled_read_window(
    *,
    frequency: str | None,
    start_day: Any,
    days_to_complete: Any,
    first_run: date | None,
    today: date,
) -> dict[str, Any] | None:
    """The next read window from the CYCLE'S SCHEDULE — `DEF-MET-4684`'s fix.

    ⚠ **`open_read_window_for_unit` COULD NEVER ANSWER AND THAT IS WHY THIS
    EXISTS.** It filters `read_on IS NULL`, and the only
    `ReadWindow.objects.create` in the whole product is inside
    `read_windows.close_read_window()`, which sets `read_on` at creation.
    An OPEN window is therefore unreachable **by construction**;
    `close_read_window` has no callers at all, so the table is empty on every
    tenant including both demos. `CWP-033`'s *NEXT READING DUE* tile has never
    rendered for anybody.

    **Nothing caught it, and the reason generalises:** `None` is ALSO the right
    answer on a day with no window open, so a dead lookup and a quiet day are
    the same output — exactly `DEF-CWP-4510`'s shape one layer down.

    ⚠ **THE SCHEDULE IS A DERIVATION, NOT A TABLE, SO IT CANNOT GO EMPTY.**
    `period_engine.upcoming_windows` is the same published walk the run wizard
    proposes from; a route belongs to a cycle and a cycle carries `frequency`,
    `start_day`, `days_to_complete` and `first_run_date`. Nothing is stored and
    nothing is guessed: a cycle with no schedule answers `None`, which is an
    absence to STATE rather than a date to invent.

    ⚠ **`today` IS AN ARGUMENT** (`BR-TEN-043`).
    """
    if not frequency or first_run is None:
        return None
    from apps.metering import period_engine

    windows = period_engine.upcoming_windows(
        frequency=frequency,
        start_day=start_day,
        days_to_complete=days_to_complete,
        first_run=first_run,
        as_of=today,
        count=1,
    )
    if not windows:
        return None
    window = windows[0]
    return {
        "from": window.period_start.isoformat(),
        "to": window.period_end.isoformat(),
        #: True while today is INSIDE it — the difference between *your reading
        #: is due between 2 and 6 September* and *your next reading window opens
        #: on 2 September*, which are two different sentences.
        "open_now": window.period_start <= today <= window.period_end,
    }


def describe_read_window(
    window: dict[str, Any] | None, *, today: date
) -> dict[str, Any] | None:
    """A read window with the COUNT OF DAYS until it opens — `CPB-09`.

    The blueprint asks the Readings screen to read *"Next read: Sep 30 · in 22
    days"*, and names the gap in its own words: *"The readings data carries no
    next-read date. The usage data does."*

    ⚠ **THE SERVER SHIPS A NUMBER AND THE CATALOGUE WRITES *in 22 days***
    (B14 rule 35). Eleven languages count differently — Hindi and Japanese put
    the number in another place in the sentence — and a server that shipped the
    English would make ten of the catalogues impossible.

    ⚠ **`today` IS AN ARGUMENT** (`BR-TEN-043`). A countdown computed from a
    clock read inside a read model is a figure no test can pin and no clerk can
    reproduce on a screen opened a minute later.

    ⚠ **IT NEVER GOES NEGATIVE.** A crew already walking the route is not *"in
    −3 days"*; `open_now` is the fact that sentence turns on, and the count is
    clamped at zero so a screen that ignores `open_now` still cannot print
    nonsense.

    ⚠ **ONE DERIVATION, TWO SCREENS.** `CWP-033`'s tile and `CWP-034`'s line both
    read this, so the Usage screen and the Readings screen cannot come to
    disagree about the same date — which is the shape `DEF-CWP-3655` records
    (`TwoCol` and `Panel` drifting because one decision had two homes).
    """
    if window is None:
        return None
    opens = window.get("from")
    if not opens:
        return None
    days = (date.fromisoformat(opens) - today).days
    return {**window, "days_until": max(days, 0)}


def open_read_window_for_unit(unit_id: Any, *, today: date) -> dict[str, Any] | None:
    """The OPEN read window covering or ahead of `today` for this unit's route.

    ⚠ **`billing_seam.reading_window_open` SAID THIS COULD NOT BE PUBLISHED,
    AND IT WAS READING THE WRONG THING.** Its docstring names
    `services._cycle_window_for` — a private service function — and concludes
    the portal may not have the fact. `ReadWindow` is a first-class metering
    TABLE with `period_start`, `period_end` and a `read_on` that is NULL while
    the window is open (`SET-06D`), and this is a read of that table by the
    module that owns it. Corrected 2026-09-04, `CR-068` wave H.

    ⚠ **OPEN MEANS `read_on IS NULL`.** A window whose crew has walked it is
    history and a customer being told a reading is *due* on it would be told to
    do something already done.

    `None` is an ordinary answer — most days have no window open — and the tile
    closes up rather than showing a dash (`BR-CWP-093`).
    """
    tenant_id = selectors._tenant_id()
    route_ids = list(
        models.ServicePoint.objects.filter(
            tenant_id=tenant_id, unit_id=unit_id, deleted_at__isnull=True, route_id__isnull=False
        ).values_list("route_id", flat=True)
    )
    if not route_ids:
        return None
    row = (
        models.ReadWindow.objects.filter(
            tenant_id=tenant_id,
            route_id__in=route_ids,
            read_on__isnull=True,
            period_end__gte=today,
        )
        .order_by("period_start", "id")
        .first()
    )
    if row is not None:
        return {
            "from": row.period_start.isoformat(),
            "to": row.period_end.isoformat(),
            #: True while today is inside it — the difference between *your
            #: reading is due between 2 and 6 September* and *your next reading
            #: window opens on 2 September*, which are two different sentences.
            "open_now": row.period_start <= today <= row.period_end,
        }
    #: ⚠ **AND WHEN NOTHING IS STORED, THE SCHEDULE ANSWERS** (`DEF-MET-4684`).
    #: The branch above has NEVER been reached by anybody: an open window cannot
    #: exist in this product, because the one writer sets `read_on` at creation.
    #: It is kept rather than deleted because it is the RIGHT answer the day a
    #: window is genuinely opened — a crew's own dates beat a calendar — and
    #: removing it would make that future feature silently wrong.
    cycle = (
        models.Cycle.objects.filter(
            tenant_id=tenant_id,
            route__id__in=route_ids,
            deleted_at__isnull=True,
        )
        .order_by("code", "id")
        .first()
    )
    if cycle is None:
        return None
    return scheduled_read_window(
        frequency=cycle.frequency,
        start_day=cycle.start_day,
        days_to_complete=cycle.days_to_complete,
        first_run=cycle.first_run_date,
        today=today,
    )


def billing_frequency_for_unit(unit_id: Any) -> str | None:
    """*Billed* — **how often**, as one of `schedule.FREQUENCIES`, or None.

    `CWP-022`'s **YOUR SERVICE** panel reads *Address / Plan / Billed /
    Paperless* (`08-screen-layouts.md`), and *Billed* is the cadence: a customer
    checking their own service wants to know a bill lands monthly, not what the
    rate plan is called — the plan is the row above.

    ⚠ **IT IS PUBLISHED HERE BECAUSE THE WALK CROSSES THREE METERING TABLES.**
    unit → `service_points.route` → `routes.cycle` → `cycles.frequency`. The
    portal may not walk another module's tables itself (`BR-CWP-012`), and a
    fourth spelling of *which cycle is this unit on* is how two screens come to
    disagree about a customer's billing day.

    ⚠ **A DRAFT CYCLE IS INVISIBLE** (`BR-MET-076`): it stamps no service point
    and no bill run sees it, so a customer told *Monthly* off a draft would be
    told something that is not happening yet.

    ⚠ **`None` IS ORDINARY AND THE ROW IS THEN ABSENT** (`BR-CWP-093`). A unit
    with no route, a route with no cycle and a cycle with no frequency are all
    real configurations, and *Billed —* would be a dash where a customer expects
    a fact.

    ⚠ **THE ANSWER IS A BUSINESS WORD RUN THROUGH `schedule.business_frequency`,
    NOT THE STORED STRING.** CR-006's three lowercase values are still accepted
    on write and mapped on read, so an unmigrated row answers `Monthly` rather
    than `monthly` and the screen has one value to key its catalogue on.
    """
    from apps.metering import schedule

    tenant_id = selectors._tenant_id()
    route_ids = list(
        models.ServicePoint.objects.filter(
            tenant_id=tenant_id, unit_id=unit_id, deleted_at__isnull=True, route_id__isnull=False
        ).values_list("route_id", flat=True)
    )
    if not route_ids:
        return None
    frequency = (
        models.Route.objects.filter(
            tenant_id=tenant_id, pk__in=route_ids, cycle__isnull=False
        )
        .exclude(cycle__status="draft")
        .values_list("cycle__frequency", flat=True)
        .first()
    )
    return schedule.business_frequency(frequency)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-041@this-commit · US-CWP-043@this-commit (EP-CWP-08 stories + BR-CWP-069/071/072/073 verbatim) · 12-reuse-map.md@4fd54fa6
# generated: 2026-09-04 by the CR-068 wave H build lane
# checklist: A✔ B=n/a(no frontend half in this module) C✔ D=n/a(apps/portal/api.py serves it) E=n/a F✔ G✔ H=n/a(no money read; consumption only)
# gates: pytest tests/test_us_cwp_041_readings.py tests/test_us_cwp_043_equipment.py · G81 (the portal seam that calls this performs no ORM write and imports no `services`)
# exceptions: (1) which bill a reading fed is composed in apps/portal/selectors.py, because meter_reads carries no invoice reference and metering may not read billing's tables. (2) `awaiting_review` is not served — US-CWP-042's GAP columns do not exist yet; decision log 2026-09-04.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
