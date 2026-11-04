# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · the `meter_reads` DATASET QUERY (brief §7.1 —
#           "datasets are code, definitions are data"; §7.5 — the read path;
#           §7.6 — scale; §08 — "every arrow into the database passes through a
#           reviewed dataset").
#           Drawings read as IMAGES (B14 rule 42), rendered at scale 4 by
#           `10-scripts/pdf/pdf_render.py`: p061 (R45 My Usage head + tiles),
#           p062 (R45 table + its warning, R46 Bill Projection, R28 Read
#           Completeness head), p063 (R28 table + its warning, R29 Consumption
#           Exceptions, R30 Usage & Ranking head), p064 (R30 warning, R31 Meter
#           Fleet, R32 Read Import Log), p065 (R32's savepoint warning),
#           p083–p086 (§7.2/§7.2.1/§7.2.1B/§7.2.2 the dimension model and
#           additivity), p087 (§7.5 read path, §7.6 scale, §7.7 tenancy).
# Rules:    CLAUDE.md **hard rule 3 — EVERY QUANTITY CARRIES AN EXPLICIT UNIT,
#           NEVER ASSUMED.** This dataset is where that bites hardest and it is
#           enforced STRUCTURALLY here, not remembered: see `_UNIT_REFUSAL` and
#           `consumption_total()` · hard rule 1 (tenant scoping — every
#           queryset carries `current_tenant_id()`, RLS FORCE behind it) ·
#           hard rule 2 (money 4 dp stored, percentages 6, both DISPLAY 2 —
#           this dataset publishes NO money column at all, which is itself the
#           R30 finding below) · **hard rule 4 — THIS FILE WRITES NOTHING** ·
#           hard rule 7 (a money ACTION writes `audit_log`; a READ is not an
#           action and writes none) · NFR-3 (universal server pagination —
#           `limit`/`offset`/`sort` applied IN SQL, never in Python) · NFR-5
#           (no hard caps anywhere) · BR-MET-016/053 (lineage HEADS only) ·
#           BR-MET-021 (one primary status) · BR-MET-028 (an estimate carries
#           consumption and is labelled) · BR-MET-059 (the channel model) ·
#           BR-REP-002 (read models only) · BR-REP-024 (never a 0 where a
#           figure could not be computed)
# Tests:    06-backend/tests/test_rep_meter_reads_dataset.py
#           10-scripts/ds_meter_reads_cost.py (the PostgreSQL measurement and
#           the RLS proof — hard-won law 14: the suite runs on in-memory
#           SQLite, where neither `jsonb` containment nor RLS exists)
# Impacts:  apps/reports/queries.py (`DATASET_QUERIES["meter_reads"]`,
#           `DATASET_STREAMS["meter_reads"]`) — NOT EDITED BY THIS LANE, it is
#           lane REP-UNBLOCK's file this session; the registration is REPORTED ·
#           apps/reports/datasets.py (`METER_READS.columns` is three columns
#           short of R29's drawing — REPORTED, not edited, for the same reason:
#           three lanes share that registry and law 11 is why)
# ───────────────────────────────────────────────────────
"""THE `meter_reads` DATASET — **one row per COMMITTED LINEAGE HEAD**, paged
and sorted in SQL.

═══════════════════════════════════════════════════════════════════════════════
THE BLOCK PREMISE BROKE AGAIN: SIX REPORTS ARE SEEDED HERE AND **THREE** STATE
THIS GRAIN
═══════════════════════════════════════════════════════════════════════════════
`reports/0003_seed_catalogue.py` puts six definitions on this dataset. §7.2
says a dataset states ONE GRAIN, and a report served from a dataset whose grain
it does not state produces real rows, a footing total and an answer to a
question nobody asked. Read as images (B14 rule 42), the six drawings say:

  R45 My Usage            p061-p062  one READ per period, per service  ✔ SERVED
  R29 Consumption Excs.   p063       one READ that tripped a rule      ✔ SERVED
  R30 Usage & Ranking     p063-p064  one ACCOUNT, ranked               ◑ PARTLY
  R28 Read Completeness   p062-p063  one ROUTE                         ✘ REFUSED
  R32 Read Import Log     p064       one IMPORT                        ✘ REFUSED
  R46 Bill Projection     p062       one PROJECTED CHARGE COMPONENT    ✘ REFUSED

Each refusal is argued from the drawing and from the code below, by name. This
is the fourth dataset lane in a row to find the seeded assignment wrong; the
pattern is that the seeder grouped by SUBJECT ("this is about reads") where
§7.2 groups by GRAIN ("one row is a read").

──────────────────────────────────────────────────────────────────────────────
R28 READ COMPLETENESS — REFUSED, AND THE DENOMINATOR IS WHY
──────────────────────────────────────────────────────────────────────────────
p063 heads ROUTE · READER · EXPECTED · ACTUAL · ESTIMATED · SKIPPED · MISSING ·
COMPLETE, one row per route. **EXPECTED is a count of reads that did not
happen**, and a read that did not happen has NO ROW IN THIS TABLE. No filter,
no group and no join over `meter_reads` can produce it: the fact is absent by
construction.

The arithmetic already exists and it is not here — `apps/metering/
completeness.py::cycle_coverage`, built for BR-MET-049/BR-MET-057. Its
denominator is `_expected_meters()` walking `assets → service_points.cycle_id`
through `PlanRegisterResolver`, which reads the unit's RATE PLAN to decide how
many channel records that meter owes. This dataset reads none of those tables.

⚠ **AND THE DRAWING'S WARNING IS A DESIGN RULE FOR THAT REPORT, WHICH I
CHECKED RATHER THAN ASSUMED.** p063, verbatim: *"Route R-03 has no reader and
still reads 100% complete — an unassigned route is a scheduling gap, not a read
gap, and the report must not conflate them. Complete counts actual plus
estimated because an estimated read bills; Missing is the column that blocks a
bill run."* It reads like a live defect and it is NOT one today: `cycle_coverage`
reports per CYCLE with no route breakdown and no reader column at all, so there
is no shipped surface that conflates the two. The fact the column needs exists
— `metering.models.Route.assigned_to`, whose own comment reads *"NULL = System
(auto-pull)"* — so an R28 lane has a reader to render and a NULL to render as
*Unassigned* rather than as a gap. Recorded here so the next lane does not
re-derive it.

`COMPLETE = (actual + estimated) / expected` also makes COMPLETE a **non-
additive** measure by §7.2.2's own table (*"% share · collection rate · DSO —
must be recomputed from its components, never averaged"*), which is why
`METER_READS` already declares `completeness_pct` as `ADD_NON`. That
declaration is correct and is the only part of R28 this dataset can honour.

──────────────────────────────────────────────────────────────────────────────
R32 READ IMPORT LOG — REFUSED, AND THE COORDINATOR'S FLAG IS CONFIRMED
──────────────────────────────────────────────────────────────────────────────
p064 heads DATE · FILE · SOURCE · ROWS · ACCEPTED · REJECTED · BY · DETAIL and
names its own source in the drawing's header line: *"Operations › Reads · jobs
+ meter reads · Import date"*. **One row is one IMPORT**, and its natural key
is `metering.models.ReadImportBatch`, not a read.

The decisive column is REJECTED. A rejected row **never became a meter read** —
`read_import_rows` holds it with its `rule_outcomes` and its `meter_read_id`
NULL. A dataset at read grain can count 80,918 accepted and is structurally
blind to the 286 rejected, which is precisely the invisible wrong answer §7.2
exists to prevent: the file would not look wrong, it would look like a clean
import.

⚠ **ITS WARNING IS ABOUT THE WRITE PATH, NOT THIS READ, AND I CHECKED THAT THE
WRITE PATH ALREADY OBEYS IT.** p065, verbatim: *"A rejected row is skipped
inside its own savepoint — hard-won law 14. Without the nested transaction the
first rejection aborts the whole import on PostgreSQL and every row is lost at
commit, while the test suite on SQLite passes. The 286 rejections are proof the
savepoint is real."* That is a rule for the IMPORTER. `_savepoint_audit()`
below is the standing measurement of it, so the claim in this docstring is a
command a reader can run rather than a sentence they must believe (CLAUDE.md:
*"where a rule restates what a tool does, name the tool"*).

──────────────────────────────────────────────────────────────────────────────
R46 BILL PROJECTION — REFUSED, AND IT IS NOT EVEN A FACT TABLE
──────────────────────────────────────────────────────────────────────────────
p062 heads COMPONENT · BASIS · QUANTITY · UNIT · RATE · PROJECTED, four rows —
*Water base · Water usage · Sewer base · Sewer usage* — and names its source as
*"meter reads + rating"*. **One row is one PROJECTED CHARGE COMPONENT**, which
is a rating output, not a read. Two of the four rows (`Water base`, `Sewer
base`, both `Monthly`, quantity `1 month`) have **no meter read behind them at
all** and would simply be absent from a read-grain query.

⚠ **AND IT CARRIES MONEY THIS DATASET DOES NOT PUBLISH.** RATE `0.0142` and
PROJECTED `59.64` are money; `METER_READS.columns` declares no money column and
should not gain one, because hard rule 2's basis and scale belong to whichever
dataset owns the charge. Its drawing's own warning — *"Usage is straight-lined
and base charges are not, and each row says which it is… the definition carries
the ± range beside the figure: a single number reads as a promise and generates
a complaint when the real bill differs"* — is a statement about a PREDICTION
with an error bar, which is not a stored fact of any kind.

What this dataset CAN lawfully give R46 is the input to the straight-lining:
the usage so far and the days elapsed, for one account and one window. That is
`portal_usage()` below, and an R46 lane should read it through a seam rather
than re-deriving it.

──────────────────────────────────────────────────────────────────────────────
R30 USAGE & RANKING — PARTLY SERVED, AND THE ONE COLUMN THAT IS NOT IS MONEY
──────────────────────────────────────────────────────────────────────────────
p063-p064 heads RANK · ACCOUNT · CUSTOMER · CLASS · USAGE · UNIT · SHARE ·
BILLED. Seven of the eight are a lawful GROUP over this fact and `account_usage
_ranking()` below builds them in SQL. **BILLED is money from `billing`** — a
second source — and it is served as `None` with a stated reason rather than as
`0`, per BR-REP-024 (*"never a 0 where a figure could not be computed"*). A
zero there would read as *"this account used 148,200 gal and was billed
nothing"*, which is a defect report, not a report.

⚠ **ITS WARNING IS ENFORCED STRUCTURALLY RATHER THAN DOCUMENTED.** p064,
verbatim: *"One service at a time, and the dropdown is not optional. A ranking
across water and electricity would sort gallons against kilowatt-hours, which
is the single most common way a usage report lies. The service parameter is
required, not defaulted."* `account_usage_ranking(service=…)` takes `service`
as a **keyword-only argument with no default**, so a caller that omits it gets
a `TypeError` at the call site rather than a ranking of gallons against
kilowatt-hours. A default of `None` meaning *all* would have had the bug the
warning names; a missing default cannot. That is the same reasoning as the
export's missing `per` below, applied to a unit rather than to a page.

═══════════════════════════════════════════════════════════════════════════════
HARD RULE 3 IS STRUCTURAL HERE, AND IT IS THE ONE THING THIS FILE MOST EXISTS
FOR
═══════════════════════════════════════════════════════════════════════════════
A sibling measured `26.24 kgal + 684.00 kWh = 710.24` — *a number with no unit,
which is not a quantity at all*. §7.2.2's table states the same rule as
metadata: consumption is **additive WITHIN ONE SERVICE**, and `METER_READS`
declares `measure("consumption", AGG_SUM, ADD_WITHIN_SERVICE)`.

So `consumption_total()` **counts the distinct units in the filtered set before
it sums anything**, and where there is more than one it returns a REFUSAL —
`total=None`, `unit=None`, and a `reason` the footer renders as an em-dash and
a sentence. It does not sum and label; it does not pick the commonest unit; it
does not convert. `kgal` and `kWh` have no conversion and `gal`→`kgal` has one
that nobody signed.

⚠ **THE REFUSAL IS COUNTED IN SQL, IN THE SAME AGGREGATE CALL AS THE SUM.** Two
round trips could see two different sets if a read committed between them, and
*"the total was struck over one unit and the unit count over two"* is not a
defect anybody would ever diagnose from a report that foots.

This is why there is no `Total usage` tile on a multi-service account, which
p062's warning says in as many words: *"Every quantity carries its unit, in its
own column — hard rule 3, and the reason there is no Total usage tile on a
multi-service account. The Basis column is why a customer's own figure and
their bill can differ without either being wrong."*

═══════════════════════════════════════════════════════════════════════════════
R45 IS THE CUSTOMER PORTAL, AND THIS QUERY IS WHERE THE LEAK WOULD BE
═══════════════════════════════════════════════════════════════════════════════
`portal_usage()` takes `account_ids` as a **required keyword argument** — the
signed-in principal's set, exactly as `apps/portal/selectors.py` already passes
it (`account_ids = list(principal.account_ids)`) — and applies it as a
`WHERE account_id IN (…)` in the same `_base()` every other path uses.

⚠ **AND THE FOOTER IS SCOPED IN THE SAME QUERYSET, WHICH IS THE HALF A WEAKER
TEST MISSES.** A total struck over the unscoped set leaks the figure without
leaking a row: the customer sees their four reads and a *This period* tile
holding their neighbour's gallons too. `test_rep_meter_reads_dataset.py` proves
it with **two accounts in the same window**, so a scope that did nothing would
return both and pass, and asserts the tile as well as the rows.

⚠ **THE `NEIGHBOURHOOD AVERAGE` TILE ON p061 IS A DELIBERATE CROSS-ACCOUNT
AGGREGATE AND IS NOT BUILT HERE.** It is drawn (`152 gal` beside the
customer's own `137 gal`) and it necessarily reads other customers' reads. It
is not served by `portal_usage()`.

⚠⚠ **RULED 2026-09-27 AND THIS PARAGRAPH SAID THE OPPOSITE UNTIL THEN.** It
read *"nobody has decided what the floor is"*. **A floor is decided.** PO
verbatim, option (a) of three: *"(a) with a floor of at least ten homes, and
the tile simply absent below that, saying nothing about why"* — written up as
`BR-REP-037` in `04-docs/05-modules/12-reports/02-business-rules.md` and in
the decision log of that date. **Show the tile only over at least TEN other
homes; below that it is ABSENT — not a dash, not a zero — and the screen says
NOTHING about why** (B14 rule 33 puts rationale at zero words on screen, and
*"too few homes nearby"* is itself a fact about the neighbourhood).

**It is still not built here**, and a lane adding it obeys that floor.

═══════════════════════════════════════════════════════════════════════════════
IT PAGES AND SORTS IN SQL, AND THE EXPORT IS A SEPARATE FUNCTION
═══════════════════════════════════════════════════════════════════════════════
Brief §7.5 (p087): *"Sync — viewing — page 1 — returns rows with limit/offset/
sort applied in SQL. Never the whole result."*

§7.6 (p087) makes this dataset the LARGEST in the product: at T5 the biggest
report is *"~480,000 rows — a year of read history"*. Nothing here sorts or
slices in Python.

⚠ **`meter_reads_dataset_stream()` TAKES NO `page` AND NO `per`.** An export
cannot inherit a screen's fifty rows because there is no argument through which
to pass them. When the billing register started paging, its export inherited
the page and shipped a valid-looking file of 50 rows from a 38,000-row report;
a flag would have had the same bug, a missing parameter cannot.

`NFR-5` — no cap on that branch and none anywhere in this file. `STREAM_CHUNK`
is a fetch buffer, not a ceiling: the loop runs until the cursor is exhausted.

**TOTALS ARE A SQL AGGREGATE OVER THE WHOLE FILTERED SET, NEVER OVER THE
PAGE**, so the tiles foot whether a page is cut or not.

═══════════════════════════════════════════════════════════════════════════════
LINEAGE HEADS ONLY, AND WHY THAT IS NOT A FILTER A CALLER MAY DROP
═══════════════════════════════════════════════════════════════════════════════
BR-MET-016/053: a correction is a NEW row and the old one gets
`superseded_by_id`. `_base()` applies `superseded_by_id__isnull=True`
UNCONDITIONALLY and takes no argument to switch it off, because a report that
counts a read and its correction counts one meter twice — and the count would
be *larger*, which reads as a busier month rather than as an error.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.apps import apps as django_apps
from django.db.models import Count, Q, Sum

from apps.metering import models, selectors
from core.pagination import order_terms
from core.tenancy import current_tenant_id

#: The fetch buffer for the streaming read. **NOT A CEILING** (`NFR-5`).
STREAM_CHUNK = 2_000

#: `sort` name → the order terms it means, each written ASCENDING. `order_terms`
#: flips every term for `desc`, so the two directions cannot drift apart.
#: ⚠ **EVERY TUPLE ENDS WITH `id`** — `core.pagination.order_terms`' own
#: docstring: *"a page is a window over an ORDER; if the order is not total, two
#: rows that compare equal may swap between page 1 and page 2 and a clerk sees
#: one row twice and another never."* At 480,000 rows over a year of history
#: (§7.6) a non-total order is not a theoretical hazard.
READ_SORT_COLUMNS: dict[str, tuple[Any, ...]] = {
    "read_on": ("read_at", "id"),
    "account_no": ("account__account_no", "id"),
    "meter_no": ("asset__asset_no", "id"),
    "channel": ("channel", "id"),
    "consumption": ("consumption", "id"),
    "reading": ("current_value", "id"),
    "unit": ("unit", "id"),
    "flag": ("status", "id"),
}
READ_DEFAULT_SORT = "read_on"

#: ⚠ **THE SORTS, THE FILTERS AND THE GROUP LEVELS THIS QUERY HONOURS, AS
#: DECLARED TUPLES THE VIEWER READS AT CALL TIME.**
#:
#: `apps/reports/report_seams.py` already resolves a dataset's own constants
#: this way (`payments_dataset_constant("PAYMENT_SORTS")`) and its docstring
#: gives the reason: *"a sort or a group level this module offered and the read
#: model declined would be a live control over a dead one."* That is hard-won
#: law 2's mirror, and it is the exact fault `DEF-PAY-6271` is still open on —
#: a screen declaring ten sorts, a search and four filters over a query that
#: honours three sorts and two filters. A viewer that builds its caret row from
#: these tuples cannot offer a control this file does not implement.
READ_SORTS: tuple[str, ...] = tuple(READ_SORT_COLUMNS)
READ_FILTERS: tuple[str, ...] = (
    "from",
    "to",
    "service",
    "route",
    "cycle",
    "channel",
    "read_basis",
    "flag",
)
#: R30 is the only drawn grouping and it groups by ACCOUNT. A second level is a
#: new argument here BEFORE it is a new chip on a screen.
READ_GROUPS: tuple[str, ...] = ("account",)

#: ⚠ **THE THREE DEFINITIONS THIS DATASET MAY NOT SERVE, REFUSED BY NAME.**
#:
#: `reports/0003_seed_catalogue.py` puts SIX definitions on `meter_reads` and
#: three of them state a different grain (§7.2). Serving one produces real rows,
#: a footing total and an answer to a question nobody asked — invisible to every
#: gate and to the clerk.
#:
#: The sentences live HERE rather than in `apps/reports/queries.py` so the lane
#: that knows why a report is refused is the lane that writes the refusal, and
#: so a fourth misfit cannot be added to that dict without this file agreeing.
#: `queries.py` imports this map through the seam; the shape is the one
#: `PAYMENTS_DEFINITIONS_NOT_SERVED` already uses.
METER_READS_DEFINITIONS_NOT_SERVED: dict[str, str] = {
    "read_completeness": (
        "Read Completeness (R28) draws one row per ROUTE, and its Expected column is a "
        "count of reads that DID NOT HAPPEN. A read that did not happen has no row in "
        "`meter_reads`, so no filter, group or join over this dataset can produce the "
        "denominator. The arithmetic exists in `apps/metering/completeness.py"
        "::cycle_coverage`, whose expected set walks assets to service points to each "
        "unit's rate plan. Served from here the report would show 100% complete for "
        "every route, always, because every read it can see was collected."
    ),
    "read_import_log": (
        "Read Import Log (R32) draws one row per IMPORT — its file, its row count, and "
        "how many rows were ACCEPTED and REJECTED. A rejected row never became a meter "
        "read: it sits in `read_import_rows` with `meter_read_id` NULL. This dataset is "
        "structurally blind to every rejection, so the report would not look wrong, it "
        "would look like a clean import. Its grain is `ReadImportBatch`, and the "
        "drawing names its own source as 'jobs + meter reads'."
    ),
    "bill_projection": (
        "Bill Projection (R46) draws one row per projected CHARGE COMPONENT and carries "
        "a rate and a projected amount. Two of its four drawn rows are base charges with "
        "no meter read behind them at all, so they would simply be absent; and the money "
        "columns belong to whichever dataset owns the charge, because hard rule 2's "
        "basis and scale travel with it. What this dataset can lawfully give R46 is the "
        "usage and the days elapsed that the straight-lining starts from — "
        "`portal_usage()`."
    ),
}

#: `read_basis` — the two words p062's BASIS column renders.
BASIS_ACTUAL = "actual"
BASIS_ESTIMATED = "estimated"

#: ⚠ **THE SQL HALF OF `selectors.read_is_estimated`, AND THE TEST ASSERTS THE
#: TWO AGREE ON EVERY COMBINATION.**
#:
#: That helper is the ONE derivation of *"this head is an estimate"* and its own
#: docstring says why it was extracted: *"a second spelling of one derivation is
#: how two consumers start disagreeing about which reads are estimates
#: (hard-won law 5)."* It takes two Python values, so it cannot be applied
#: inside a `WHERE` — and re-deriving it in SQL is exactly the second spelling
#: it warns about.
#:
#: So this `Q` is declared beside it and `test_basis_q_agrees_with_selector`
#: walks the full cross product of `READ_STATUSES` × `DISPOSITIONS` + `None`
#: asserting the two answers match. The day somebody adds a third way for a
#: read to be an estimate, that test goes red and names it. The alternative —
#: a comment saying *"keep these in step"* — is hard-won law 1.
ESTIMATED_Q = Q(status="estimated") | Q(disposition="estimate")

#: BR-REP-024 — the reason a figure is ABSENT rather than zero.
GAP_MIXED_UNITS = {
    "code": "consumption_spans_more_than_one_unit",
    "measure": "consumption",
    #: ⚠ B14 rule 33 caps ON-SCREEN text; this is a `reason` a screen renders
    #: through its own catalogue key, not a string this file puts on a screen.
    "message_key": "reports.meter_reads.total_spans_units",
}
GAP_BILLED_IS_NOT_A_READ_FACT = {
    "code": "billed_amount_is_not_a_meter_read_fact",
    "measure": "billed",
    "message_key": "reports.meter_reads.billed_unavailable",
}


def _tenant_id() -> Any:
    """Hard rule 1. RLS `FORCE` is the floor under this, never the ceiling —
    `10-scripts/ds_meter_reads_cost.py` proves the policy on real PostgreSQL,
    because `config/settings/test.py` hardcodes in-memory SQLite where the
    guarantee cannot exist at all (hard-won law 14, and law 7's *"G5 ran the
    tenant-isolation suite on sqlite and called 192 skips a pass"*)."""
    return current_tenant_id()


def _base(
    *,
    start: date | None = None,
    end: date | None = None,
    service: str | None = None,
    route_id: Any = None,
    cycle_id: Any = None,
    channel: str | None = None,
    read_basis: str | None = None,
    flag: str | None = None,
    account_ids: Sequence[Any] | None = None,
    flagged_only: bool = False,
) -> Any:
    """THE filtered set. Every criterion is a `WHERE`; nothing is filtered in
    Python anywhere in this file.

    ⚠ **`superseded_by_id__isnull=True` IS UNCONDITIONAL AND TAKES NO
    ARGUMENT** — see the module docstring. A caller cannot switch lineage
    heads off, because the wrong answer is a LARGER number and reads as a
    busier month rather than as an error.
    """
    rows = models.MeterRead.objects.filter(
        tenant_id=_tenant_id(),
        superseded_by_id__isnull=True,
    )
    if start is not None:
        rows = rows.filter(read_at__date__gte=start)
    if end is not None:
        rows = rows.filter(read_at__date__lte=end)
    if service is not None:
        # The read carries no service of its own; it walks
        # asset → service_point → service, which is the same walk
        # `completeness._expected_meters` makes. Hard rule 8's shape for a
        # non-address fact: derive it, never duplicate the column.
        rows = rows.filter(asset__service_point__service__code=service)
    if route_id is not None:
        # ⚠ **THE READ'S OWN ROUTE, NOT THE SERVICE POINT'S** (BR-MET-079).
        # `meter_reads.route_id` is an immutable provenance stamp taken at
        # collection; `service_points.route_id` is UNSTAMPED the moment a
        # membership moves, so filtering through it makes a route's own history
        # vanish when its premises are reassigned. That model comment records a
        # seeded route destroyed exactly that way.
        rows = rows.filter(route_id=route_id)
    if cycle_id is not None:
        rows = rows.filter(asset__service_point__cycle_id=cycle_id)
    if channel is not None:
        rows = rows.filter(channel=channel)
    if read_basis == BASIS_ESTIMATED:
        rows = rows.filter(ESTIMATED_Q)
    elif read_basis == BASIS_ACTUAL:
        rows = rows.exclude(ESTIMATED_Q)
    if flag is not None:
        rows = rows.filter(status=flag)
    if flagged_only:
        # R29's set: BR-MET-021 keeps ONE primary status, and `ok` is the
        # unflagged one. An ESTIMATE is not an exception — it is a labelled
        # read (BR-MET-028) — so `estimated` is excluded too, which is what
        # makes p063's tiles foot: READS CHECKED 1,916 against EXCEPTIONS 48.
        rows = rows.exclude(status__in=("ok", "estimated"))
    if account_ids is not None:
        # ⚠ **THE CUSTOMER-PORTAL SCOPE (R45).** An empty sequence is an empty
        # result and NOT "no filter" — `if account_ids:` would have made a
        # principal holding no accounts see the whole utility, which is the
        # falsy-empty bug in its most expensive form. `is not None` is the test.
        rows = rows.filter(account_id__in=list(account_ids))
    return rows


@dataclass(frozen=True)
class MeterReadFactRow:
    """One committed lineage head, shaped as the dataset's declared columns.

    ⚠ **`prior`, `change` AND `rule` ARE SERVED AND ARE NOT YET DECLARED IN
    `apps/reports/datasets.py`.** R29's drawing (p063) heads PRIOR · THIS READ ·
    CHANGE, and its warning says why they cannot be dropped: *"Prior and current
    sit side by side because the exception is a comparison, not a value."* All
    three are facts of this row (`prior_value`, `current_value` minus it, and
    `rule_outcomes`), so serving them is honest at this grain.

    The three-column gap in `METER_READS.columns` is **REPORTED, not edited**:
    `datasets.py` is the registry three dataset lanes share this session and a
    whole-file write to it is hard-won law 11's mechanism two. The lane report
    names the exact tuple to add.
    """

    read_on: date | None
    account_no: str | None
    meter_no: str | None
    channel: str
    reading: Decimal | None
    consumption: Decimal | None
    unit: str
    read_basis: str
    flag: str
    # R29's comparison columns — see the class docstring.
    prior: Decimal | None
    change: Decimal | None
    rule: str | None


def _rule_of(read: Any) -> str | None:
    """The WORST outcome's rule name — p063's RULE column.

    `rule_outcomes` is `jsonb`, a list of `{rule, severity, detail}`
    (`models.py`). It is read here in Python and NOT filtered on, deliberately:
    `jsonb` containment does not exist on SQLite, so a `WHERE` over it would be
    a predicate the whole suite is structurally unable to exercise (law 7's
    *"incapable of failing"*). The SET is cut by `status`, which is an ordinary
    text column BR-MET-021 keeps as the ONE primary status — so the filtering is
    in SQL and only the LABEL is resolved per row, over a page that is already
    cut.
    """
    outcomes = read.rule_outcomes or []
    ranked = [
        o
        for o in outcomes
        if isinstance(o, dict) and o.get("severity") in ("error", "warning")
    ]
    if not ranked:
        return None
    worst = max(ranked, key=lambda o: 1 if o.get("severity") == "warning" else 2)
    value = worst.get("rule")
    return None if value is None else str(value)


def _shape(
    read: Any,
    *,
    account_nos: dict[str, str | None],
    meter_nos: dict[str, str | None],
) -> MeterReadFactRow:
    """One row. **NO QUERY RUNS IN HERE** — the two label maps are resolved once
    per page by `_labels_for`, so a fifty-row page costs three bounded
    statements and never fifty-one."""
    estimated = selectors.read_is_estimated(read.status, read.disposition)
    prior = read.prior_value
    current = read.current_value
    return MeterReadFactRow(
        read_on=read.read_at.date() if read.read_at is not None else None,
        account_no=account_nos.get(str(read.account_id)),
        meter_no=meter_nos.get(str(read.asset_id)),
        channel=read.channel,
        reading=current,
        consumption=read.consumption,
        # Hard rule 3: `unit` is NOT NULL on the model and is stamped from the
        # asset's own UoM at insert — never inferred from service, and never
        # inferred here either.
        unit=read.unit,
        read_basis=BASIS_ESTIMATED if estimated else BASIS_ACTUAL,
        flag=read.status,
        prior=prior,
        # ⚠ **THE RAW DIFFERENCE, NOT A PERCENTAGE**, and p063's warning is the
        # whole reason: *"A reverse reading is negative usage and is shown as
        # the raw difference, not as a percentage — dividing by a larger number
        # to produce −0.1% would hide a meter swap."* A percentage is the
        # screen's to compute from these two, with the screen's own rule for a
        # zero prior; this dataset serves the comparison.
        change=(None if (prior is None or current is None) else current - prior),
        rule=_rule_of(read),
    )


def _labels_for(
    reads: list[Any],
) -> tuple[dict[str, str | None], dict[str, str | None]]:
    """A PAGE's account numbers and meter numbers — TWO bounded queries, never
    one per row and never a join.

    ⚠ **THIS WAS `select_related("account", "asset")` AND THAT COST 30× ON REAL
    PostgreSQL.** `meter_reads` is PARTITIONED MONTHLY on `read_at`
    (DB-7/NFR-24, BR-MET-055) and the clone carries 28 partitions. Measured on
    PostgreSQL 16 over 40,201 reads, page 1 of 50 with `ORDER BY read_at, id`:

        page, ORDER BY + select_related   0.345s
        page, ORDER BY, no select_related 0.011s
        page, no ORDER BY, no join        0.011s

    **The join defeats the `LIMIT` pushdown**: the planner joins the whole
    partitioned parent to `assets` and `accounts` before it cuts fifty rows, so
    the work is proportional to the tenant's whole read history rather than to
    the page. At T5 §7.6 puts that history at ~480,000 rows, which is twelve
    times the set measured here.

    Resolving the labels AFTER the page makes the second and third statements
    `IN (…)` over at most `per` distinct ids. **Bounded by the PAGE, not by the
    tenant** — the same shape, and the same reasoning, as
    `payments_dataset._teller_names`, whose own docstring records the one-query-
    per-row version it replaced.

    ⚠ **`accounts` IS CUSTOMERS' TABLE AND `assets` IS THE ASSET REGISTRY.**
    Both are already reachable from `meter_reads` by a reviewed cross-module FK
    (B2 §2's reviewed interface set — the model declares them), so reading the
    number off each is the same boundary `select_related` was crossing, not a
    wider one. Nothing is written (hard rule 4).
    """
    if not reads:
        return {}, {}
    account_ids = {read.account_id for read in reads if read.account_id is not None}
    asset_ids = {read.asset_id for read in reads if read.asset_id is not None}
    accounts: dict[str, str | None] = {}
    meters: dict[str, str | None] = {}
    if account_ids:
        customer_models = django_apps.get_model("customers", "Account")
        accounts = {
            str(one): number
            for one, number in customer_models.objects.filter(
                tenant_id=_tenant_id(), id__in=account_ids
            ).values_list("id", "account_no")
        }
    if asset_ids:
        asset_model = django_apps.get_model("assets", "Asset")
        meters = {
            str(one): number
            for one, number in asset_model.objects.filter(
                tenant_id=_tenant_id(), id__in=asset_ids
            ).values_list("id", "asset_no")
        }
    return accounts, meters


def _shape_all(reads: list[Any]) -> list[MeterReadFactRow]:
    """A whole page (or a stream chunk), with its labels resolved once."""
    account_nos, meter_nos = _labels_for(reads)
    return [
        _shape(read, account_nos=account_nos, meter_nos=meter_nos) for read in reads
    ]


def consumption_total(rows: Any) -> dict[str, Any]:
    """**HARD RULE 3, AS A REFUSAL RATHER THAN A SENTENCE.**

    Σ consumption over the filtered set, **and the count of DISTINCT UNITS in
    the same aggregate call**. Where the set spans more than one unit there is
    no lawful total, so this returns `total=None`, `unit=None` and a stated
    reason — never a number, never the commonest unit, never a conversion.

    §7.2.2 (p085), verbatim: *"Consumption — additive **within one service** —
    gallons plus kilowatt-hours is not a number, hard rule 3 already forbids it,
    and this is the same rule stated as metadata."* `METER_READS` declares
    `ADD_WITHIN_SERVICE` and this is that declaration made to bite.

    ⚠ **ONE ROUND TRIP, NOT TWO.** A separate `values("unit").distinct()` call
    could see a different set from the `Sum` if a read committed between them,
    and a total struck over one unit while the unit count saw two is a defect
    nobody would ever diagnose from a report that foots.

    ⚠ **A SUM OF NOTHING IS `None`, NOT `0` (BR-REP-024).** `Sum` over an empty
    set returns NULL and it is left NULL: *"never a 0 where a figure could not
    be computed"*. Zero gallons and no reads are different facts and a tile
    showing `0 gal` for the second one is wrong.
    """
    aggregated = rows.aggregate(
        consumption_sum=Sum("consumption"),
        unit_count=Count("unit", distinct=True),
        read_count=Count("id"),
    )
    units = int(aggregated["unit_count"] or 0)
    if units > 1:
        return {
            "total": None,
            "unit": None,
            "unit_count": units,
            "reads": int(aggregated["read_count"] or 0),
            "reason": dict(GAP_MIXED_UNITS),
        }
    # Exactly one unit (or none at all) — safe to name it. The extra statement
    # runs ONLY on the lawful branch and over a set already known to hold one
    # distinct value, so it is a single-row index probe rather than a scan.
    unit = None if units == 0 else rows.values_list("unit", flat=True).first()
    return {
        "total": aggregated["consumption_sum"],
        "unit": unit,
        "unit_count": units,
        "reads": int(aggregated["read_count"] or 0),
        "reason": None,
    }


def meter_reads_dataset(
    *,
    start: date | None = None,
    end: date | None = None,
    service: str | None = None,
    route_id: Any = None,
    cycle_id: Any = None,
    channel: str | None = None,
    read_basis: str | None = None,
    flag: str | None = None,
    flagged_only: bool = False,
    account_ids: Sequence[Any] | None = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = "desc",
) -> dict[str, Any]:
    """THE dataset query. One row per committed lineage head, paged and sorted
    in SQL.

    `per=None` is the whole filtered set. `per` is a page size the CALLER clamps
    (`core.pagination.clamp_page_size`); this function invents none, because a
    cap invented here is a cap nobody can see (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `meter_reads_dataset_stream()`** — it takes no
    `page` and no `per`, so an export has no argument through which to inherit a
    screen's fifty rows.

    `totals` is a SQL aggregate over the WHOLE filtered set and never over the
    page, so the tiles foot whether a page is cut or not.
    """
    rows = _base(
        start=start,
        end=end,
        service=service,
        route_id=route_id,
        cycle_id=cycle_id,
        channel=channel,
        read_basis=read_basis,
        flag=flag,
        flagged_only=flagged_only,
        account_ids=account_ids,
    )

    totals = consumption_total(rows)
    total_rows = totals["reads"]

    ordered = rows.order_by(
        *order_terms(
            sort, direction, columns=READ_SORT_COLUMNS, default=READ_DEFAULT_SORT
        )
    )

    if per is None:
        page_rows = list(ordered)
        page_number = 1
    else:
        page_number = max(1, int(page))
        offset = (page_number - 1) * int(per)
        # ONE `LIMIT`/`OFFSET`, in SQL. Slicing a QuerySet does not evaluate it.
        page_rows = list(ordered[offset : offset + int(per)])

    return {
        "grain": "one meter read",
        "rows": _shape_all(page_rows),
        "total": total_rows,
        "page": page_number,
        "per": per,
        "totals": {
            "consumption": totals,
            "reads": total_rows,
        },
        # BR-REP-024 — what this dataset cannot answer, said out loud beside the
        # figures rather than left to be inferred from an absent column.
        "problems": [dict(GAP_BILLED_IS_NOT_A_READ_FACT)],
    }


def meter_reads_dataset_stream(
    *,
    start: date | None = None,
    end: date | None = None,
    service: str | None = None,
    route_id: Any = None,
    cycle_id: Any = None,
    channel: str | None = None,
    read_basis: str | None = None,
    flag: str | None = None,
    flagged_only: bool = False,
    account_ids: Sequence[Any] | None = None,
    sort: str | None = None,
    direction: str = "desc",
) -> Iterator[MeterReadFactRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    ⚠ **THE ABSENCE OF THOSE TWO PARAMETERS IS THE WHOLE DESIGN**, and this
    dataset is the one where it costs most: §7.6 (p087) puts a year of read
    history at T5 at ~480,000 rows, so an export that silently inherited a
    screen's fifty would be short by four hundred and seventy-nine thousand and
    would still open cleanly in a spreadsheet.

    ⚠ **`NFR-5` — NO CAP ANYWHERE ON THIS PATH.** `STREAM_CHUNK` is a fetch
    buffer: the loop runs until the cursor is exhausted.

    The order is the same `order_terms` the page uses, applied in SQL, so the
    file and the screen sort identically.
    """
    rows = _base(
        start=start,
        end=end,
        service=service,
        route_id=route_id,
        cycle_id=cycle_id,
        channel=channel,
        read_basis=read_basis,
        flag=flag,
        flagged_only=flagged_only,
        account_ids=account_ids,
    ).order_by(
        *order_terms(
            sort, direction, columns=READ_SORT_COLUMNS, default=READ_DEFAULT_SORT
        )
    )
    # Labels are resolved PER CHUNK — bounded and batched, never one query per
    # row, and never a join (see `_labels_for`).
    buffer: list[Any] = []
    for read in rows.iterator(chunk_size=STREAM_CHUNK):
        buffer.append(read)
        if len(buffer) >= STREAM_CHUNK:
            yield from _shape_all(buffer)
            buffer = []
    if buffer:
        yield from _shape_all(buffer)


def account_usage_ranking(
    *,
    service: str,
    start: date | None = None,
    end: date | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """R30's drawn row — one ACCOUNT, ranked by usage — **grouped in SQL**.

    ⚠ **`service` IS KEYWORD-ONLY WITH NO DEFAULT, AND THAT IS THE DRAWING'S
    WARNING MADE STRUCTURAL.** p064, verbatim: *"One service at a time, and the
    dropdown is not optional. A ranking across water and electricity would sort
    gallons against kilowatt-hours, which is the single most common way a usage
    report lies. The service parameter is required, not defaulted."* A caller
    that omits it raises `TypeError` at the call site. A default of `None`
    meaning *all services* would have had exactly the bug the warning names.

    ⚠ **THIS IS NOT THIS DATASET'S GRAIN AND THE RETURN SAYS SO.** `grain` here
    reads *"one account"*, not *"one meter read"*. §7.2 lets a report GROUP a
    fact; it does not let a definition claim a grain its dataset does not state.

    `SHARE` is **non-additive** (§7.2.2: *"% share — must be recomputed from its
    components, never averaged"*), so it is recomputed per row from the group's
    own usage over the whole-set total and is never summed. `BILLED` is money
    from `billing` and is served `None` with its reason (BR-REP-024).

    `limit` is p064's *Top 25* and is a caller's choice, never a cap: `None` is
    every account and there is no maximum (`NFR-5`).
    """
    rows = _base(start=start, end=end, service=service)

    # Hard rule 3 again, one layer up: even inside ONE service a tenant could
    # hold two units of measure (a `gal` meter and a `kgal` meter on water), so
    # the same refusal applies to the ranking's TOTAL USAGE tile.
    overall = consumption_total(rows)

    grouped = (
        rows.values(
            "account_id",
            "account__account_no",
            "unit",
        )
        .annotate(
            usage=Sum("consumption"),
            reads=Count("id"),
        )
        .order_by("-usage", "account__account_no")
    )
    if limit is not None:
        grouped = grouped[: int(limit)]

    total = overall["total"]
    ranked: list[dict[str, Any]] = []
    for position, row in enumerate(grouped, start=1):
        usage = row["usage"]
        ranked.append(
            {
                "rank": position,
                "account_id": row["account_id"],
                "account_no": row["account__account_no"],
                "usage": usage,
                # Hard rule 3 — the unit rides in its OWN column, on every row.
                "unit": row["unit"],
                "reads": int(row["reads"]),
                # Recomputed from components, never averaged. `None` rather
                # than `0` where the denominator is absent or zero — a share of
                # nothing is undefined, not 0.0% (BR-REP-024).
                "share": (
                    None
                    if (total is None or not total or usage is None)
                    else (Decimal(usage) / Decimal(total))
                ),
                # R30's eighth column. Money from `billing` — a second source.
                "billed": None,
            }
        )

    return {
        "grain": "one account",
        "service": service,
        "rows": ranked,
        "totals": {"consumption": overall},
        "problems": [dict(GAP_BILLED_IS_NOT_A_READ_FACT)],
    }


def portal_usage(
    *,
    account_ids: Sequence[Any],
    service: str | None = None,
    start: date | None = None,
    end: date | None = None,
    channel: str | None = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = "desc",
) -> dict[str, Any]:
    """R45 My Usage — **the customer portal**, scoped to the signed-in person's
    accounts.

    `account_ids` is REQUIRED and keyword-only: the principal's set, as
    `apps/portal/selectors.py` already spells it (`account_ids =
    list(principal.account_ids)`). There is no default and no `None` branch,
    because a portal read whose scope is optional is a portal read that leaks
    the first time a caller forgets it.

    ⚠ **THE ROWS AND THE FOOTER ARE STRUCK OVER THE SAME SCOPED QUERYSET.** A
    total over the unscoped set leaks the figure without leaking a row: four of
    the customer's own reads under a *This period* tile carrying their
    neighbour's gallons. `meter_reads_dataset` builds both from one `_base()`
    call and that is what makes the tile foot to the scope.

    p062's table columns PERIOD, DAYS and PER DAY are DERIVED from consecutive
    reads and are the screen's to compute; this serves the fact — `read_on`,
    `reading`, `consumption`, `unit` and `read_basis`. The BASIS column is the
    one p062 singles out: *"The Basis column is why a customer's own figure and
    their bill can differ without either being wrong."*

    ⚠ **THE `NEIGHBOURHOOD AVERAGE` TILE IS NOT HERE.** It is RULED as of
    2026-09-27 (`BR-REP-037`: at least ten other homes, absent below that,
    nothing said on screen about the absence) and simply not built — see the
    module docstring.
    """
    return meter_reads_dataset(
        start=start,
        end=end,
        service=service,
        channel=channel,
        account_ids=account_ids,
        page=page,
        per=per,
        sort=sort,
        direction=direction,
    )
