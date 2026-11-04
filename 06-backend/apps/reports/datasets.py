# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 0 · P0.4 (the dataset registry + the metadata
#           endpoint) · P0.16 (the dimension model).  Screens: none in Phase 0;
#           2·1 and 2·2 inherit this in Phase 2.
# Rules:    CLAUDE.md hard rule 2 (money 4 dp stored / 6 for percentages / both
#           DISPLAY 2 — every money column here declares its basis and its
#           scale) · hard rule 3 (consumption always with an explicit unit,
#           never assumed — a quantity column without a unit is REFUSED at
#           import time by `_validate`) · hard rule 1 (a dataset is a REVIEWED
#           query precisely so a clerk-authored report cannot reach across a
#           tenant boundary) · brief §7.1 (datasets are code, definitions are
#           data) · §7.2 / §7.2.1 / §7.2.2 (the dimension model and additivity)
# Tests:    06-backend/tests/test_rep_p0_schema_spine.py
# Impacts:  apps/reports/models.py (`ReportDefinition.dataset` names one of
#           these codes) · apps/reports/runner.py (binds and validates against
#           this) · apps/reports/api.py (`GET /reports/datasets`)
# ───────────────────────────────────────────────────────
"""THE NINE DATASETS, AND THE DIMENSION MODEL THAT MAKES A WRONG TOTAL A REFUSAL.

A dataset is a registered, reviewed query against ONE module's read model.
There are nine, they are written by us, and they change by a pull request. A
definition is a row. That split is the brief's §7.1 and it is what lets a
utility author a report at all: everything a clerk can express has already
been reviewed for tenant isolation, for money precision and for cost.

⚠ **THIS IS METADATA, NOT A FEATURE.** It is a data structure beside each of
the nine queries and it ships no screen. What it buys is two things a comment
could never buy:

  1. *"Do not sum a balance across time"* stops being a sentence somebody reads
     and becomes `assert_summable()` raising, at build time, naming the
     measure. Brief §7.2.2: **nothing stops you today.**
  2. A report INHERITS every dimension its dataset declares — thirteen on the
     ageing report — instead of two being hand-picked. The PO raised this
     looking at AR Ageing: two slicers where the fact has about a dozen.

WHICH NINE, AND THE ONE PLACE THE SOURCE DOCUMENT COUNTS ITSELF WRONG
─────────────────────────────────────────────────────────────────────
The brief says **nine datasets, nine owners** (§05 p75) four separate times.
Its own *Every other module* table on p77 lists **eleven** module rows, of which
`portal` owns no dataset (it is a host) and `tenancy` owns `jobs` — and §05's
own note says `report_runs` is deliberately not created because *"the job record
IS the run record"*, which makes `jobs` the export pipeline's table rather than
a report dataset. That leaves ten, not nine, and `identity` is the tenth: its
row does not claim a dataset, it names two ATTRIBUTES Reports needs
(*"last-sign-in and who-added-whom"*), and §05's `notifications` row says
`audit_log` is read *"for R35 and R36"* — R36 Access Review BY NAME. So
identity is a set of attributes ON the audit dataset, not a dataset.

`metering` then owns TWO, because §7.2's own rule is that a dataset states ONE
grain and metering's row owns *"meter reads · assets"* — two grains, one row per
read and one row per meter. R28 Read Completeness is dated by read date; R31
Meter Fleet is `As at`. Folding them together would give a dataset with two
grains, which is the one thing P0.16 forbids.

**Nine, each with one grain and one owner.** The discrepancy is filed as
`DEF-REP-6797` against the document rather than resolved silently, and the
reasoning is in `12-governance/02-decision-log.md` dated 2026-09-26.

THE THREE THAT DID NOT PAGE, AND WHY THAT IS NAMED HERE
───────────────────────────────────────────────────────────
⚠ **ALL THREE PAGE SINCE 2026-09-27. COUNT THE `paginates` FIELDS; NEVER
TRUST THIS PARAGRAPH, INCLUDING THIS SENTENCE.** It has now been wrong in the
same direction THREE TIMES — it is prose about three things edited by three
different lanes, which is why the FACT is a field a test reads and this is
only the story around it.

⚠ **`journal_lines` PAGES SINCE 2026-09-26 (lane DS-LEDGER).**
`apps/ledger/journal_lines_dataset.py` is the query, and it applies
`limit`/`offset`/`sort` in SQL with no ceiling on the export branch.

⚠ **AND `payments` PAGES SINCE 2026-09-27 (lane DS-PAYMENTS).**
`apps/payments/payments_dataset.py` is the query. Its grain is ONE PAYMENT and
not *"one payment allocation"*, which is `DEF-REP-6853` — see the comment on
`PAYMENTS` below, and the measurement: 400 of 2,066 payments at a perf tenant
carry no allocation at all.

⚠ **AND `invoices` PAGES SINCE 2026-09-26 (lane DS-INVOICES).**
`apps/billing/reporting.py::invoices_dataset` applies every criterion as a
`WHERE`, the order as an `ORDER BY` and the page as a `LIMIT`/`OFFSET`, with
the totals a SQL aggregate over the whole filtered set, and
`invoices_dataset_stream` serves a FILE from a generator rather than a page.
**One left, and this paragraph has now been wrong in the same direction twice
in one day** — it is a sentence about three things that is edited by three
different lanes, which is why the COUNT below is a field and this is prose.

⚠ **AND THE FLAG WAS TRUE OF A QUERY THAT DID NOT EXIST**, which is worth more
than the fix. `journal_lines` read `paginates=False` with `DEF-PAY-4221` and
`ledger/reporting.py` beside it — a precise, sourced, checkable statement about
a read model that had never been written. `reporting.py` holds NINE aggregates
over journal lines and not one of them returns a LINE, so there was nothing
there to page. A field that records a limitation of something absent is
indistinguishable from one recording a limitation of something present, and
`P2.12` went green on it either way.

⚠ **THE BRIEF SAYS THOSE THREE FEED "32 OF THE 46" AND I COUNT 28.** Measured
against `0003_seed_catalogue.py`: `invoices` 8 + `payments` 10 +
`journal_lines` 10 = **28** definitions whose PRIMARY dataset is one of the
three; counting every definition whose DRAWN source expression touches one of
them — `R24`'s *accounts + invoices + payments*, `R39`'s *journal lines +
accounts + reads* and the like — gives **29**. Neither is 32, and the
difference is not worth a third defect against this document: the figure
appears only in prose, nothing is built from it, and `P2.12` asserts paging on
the NINE DATASETS rather than on a count of definitions. It is recorded here so
the next reader meets the discrepancy in the code instead of re-deriving it.
Each of the three declares `paginates` as a FIELD a test can read rather than
a paragraph somebody remembers, which is what `P2.12` asserts. Reporting one as
paginated without its query would be a check that cannot fail — which is
exactly why `invoices`, `journal_lines` and now `payments` each moved to `True`
in the SAME commit as their query, and not before it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# ── Column types ────────────────────────────────────────────────────────────
#: A value with no arithmetic — a name, a code, a status word.
TYPE_TEXT = "text"
#: A date or datetime. Its dimension is `time`, and see `TIME_HIERARCHIES`.
TYPE_DATE = "date"
#: Money. CLAUDE.md hard rule 2: stored to 4 decimals, DISPLAYED to 2, in a
#: `CHAR(3)` currency, never a float and never cents. A money column MUST also
#: declare its `money_basis` — BR-REP-001, a money report names its date basis.
TYPE_MONEY = "money"
#: A percentage. Hard rule 2: stored to 6 decimals, DISPLAYED to 2.
TYPE_PERCENT = "percent"
#: A measured quantity — consumption, demand, a duration. Hard rule 3: it
#: carries an explicit unit and `_validate` refuses one that does not.
TYPE_QUANTITY = "quantity"
#: A whole-number tally of rows.
TYPE_COUNT = "count"

COLUMN_TYPES: tuple[str, ...] = (
    TYPE_TEXT,
    TYPE_DATE,
    TYPE_MONEY,
    TYPE_PERCENT,
    TYPE_QUANTITY,
    TYPE_COUNT,
)

#: BR-REP-001's two labels, the same two `apps/reports/catalog.py` already uses.
BASIS_POSTING = "posting"
BASIS_CLEARING = "clearing"
#: A dated fact that is neither — a read date, an event date, an effective date.
BASIS_EVENT = "event"
MONEY_BASES: tuple[str, ...] = (BASIS_POSTING, BASIS_CLEARING, BASIS_EVENT)

# ── Aggregation and additivity (brief §7.2.2) ───────────────────────────────
AGG_SUM = "sum"
AGG_COUNT = "count"
AGG_AVERAGE = "average"
#: A measure that must be RECOMPUTED from its components and never aggregated.
AGG_RECOMPUTE = "recompute"
AGGREGATIONS: tuple[str, ...] = (AGG_SUM, AGG_COUNT, AGG_AVERAGE, AGG_RECOMPUTE)

#: Sum freely, in any direction. Invoiced amount · payment amount · tax.
ADD_FULL = "full"
#: Sums ACROSS ACCOUNTS, never ACROSS TIME. An AR balance, deposits held,
#: accounts active. ⚠ Group the ageing report by month, total the column, and
#: the number means nothing — and nothing stops you today.
ADD_SEMI = "semi"
#: Must be recomputed from its components, never averaged. DSO · collection
#: rate · % share · average days overdue. ⚠ The average of four route DSOs is
#: NOT the utility's DSO.
ADD_NON = "non"
#: Additive WITHIN ONE SERVICE and across nothing else. Gallons plus
#: kilowatt-hours is not a number — hard rule 3 already forbids it, and this is
#: the same rule stated as metadata so a machine can enforce it.
ADD_WITHIN_SERVICE = "within_service"
ADDITIVITIES: tuple[str, ...] = (ADD_FULL, ADD_SEMI, ADD_NON, ADD_WITHIN_SERVICE)

#: The dimension a semi-additive measure may NOT be summed across. Named as a
#: constant because the refusal message quotes it and a test asserts on it.
DIM_TIME = "time"
DIM_SERVICE = "service"

# ── The two time hierarchies, and they do not nest (brief §7.2.3) ───────────
#: *"A billing cycle does not sit inside a calendar month. It straddles two."*
#: So a report states WHICH hierarchy it is rolling up, and one that mixes them
#: is wrong in a way no total will reveal.
TIME_HIERARCHIES: dict[str, tuple[str, ...]] = {
    "calendar": ("year", "quarter", "accounting_period", "day"),
    "billing": ("year", "cycle", "day"),
}


@dataclass(frozen=True)
class Column:
    """One column a dataset produces. Every one carries a type; a quantity
    carries its unit and money carries its basis, or `_validate` refuses it."""

    name: str
    type: str
    #: Required when `type` is `quantity` — CLAUDE.md hard rule 3. A read of
    #: `684` is not a number anybody can bill or compare; `684 kWh` is.
    #: ⚠ `None` with `unit_from` set means the unit is a SIBLING COLUMN, which
    #: is how a multi-service row carries `26.24 kgal` and `684 kWh` at once.
    unit: str | None = None
    unit_from: str | None = None
    #: Required when `type` is `money` — BR-REP-001.
    money_basis: str | None = None
    #: Stored scale, for the avoidance of the doubt hard rule 2 exists to
    #: remove. 4 for money, 6 for a percentage, and DISPLAY is 2 for both.
    scale: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "unit": self.unit,
            "unit_from": self.unit_from,
            "money_basis": self.money_basis,
            "scale": self.scale,
        }


@dataclass(frozen=True)
class Measure:
    """A column a row COUNTS, with how it totals and whether that total is
    lawful. `additivity` is the half that did not exist before P0.16."""

    name: str
    aggregation: str
    additivity: str
    #: The dimensions this measure may NOT be aggregated across. Derived from
    #: `additivity` at construction so the two can never disagree.
    forbidden_across: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "aggregation": self.aggregation,
            "additivity": self.additivity,
            "forbidden_across": list(self.forbidden_across),
        }


def measure(name: str, aggregation: str, additivity: str) -> Measure:
    """A measure with its forbidden directions derived, never hand-typed.

    Hand-typing them is how a measure comes to say `semi` and carry an empty
    forbidden list — a declaration that reads correct and enforces nothing,
    which is hard-won law 1 in a dataclass.
    """
    if additivity == ADD_SEMI:
        forbidden: tuple[str, ...] = (DIM_TIME,)
    elif additivity == ADD_WITHIN_SERVICE:
        forbidden = (DIM_SERVICE,)
    elif additivity == ADD_NON:
        #: Non-additive means no direction is safe. The empty tuple would read
        #: as "sum freely", so the refusal below keys on `additivity` for this
        #: case and this list stays the SPECIFIC dimensions a reader can name.
        forbidden = ()
    else:
        forbidden = ()
    return Measure(name=name, aggregation=aggregation, additivity=additivity, forbidden_across=forbidden)


@dataclass(frozen=True)
class Dimension:
    """Something a report may slice, group or filter by — declared ONCE on the
    dataset, inherited by every definition built on it.

    `conformed` marks a dimension that must mean the same thing, carry the same
    label and offer the same values in EVERY dataset that has it. *Service*
    with eleven values in one report and *Utility* with three in another is two
    reports a clerk cannot compare, and `P0.17` is the test that refuses it.
    """

    name: str
    attributes: tuple[str, ...] = ()
    #: Coarse → fine, e.g. `("area", "route", "premises")`. `None` for a flat
    #: dimension. Group-to-three-levels reads this.
    hierarchy: tuple[str, ...] | None = None
    conformed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "attributes": list(self.attributes),
            "hierarchy": None if self.hierarchy is None else list(self.hierarchy),
            "conformed": self.conformed,
        }


@dataclass(frozen=True)
class Dataset:
    """One reviewed query against one module's read model."""

    code: str
    owner_module: str
    #: What ONE ROW IS, in words a clerk reads under the report title. Brief
    #: §7.2.1B: *"every report says what one row is"*.
    grain: str
    columns: tuple[Column, ...]
    measures: tuple[Measure, ...]
    dimensions: tuple[Dimension, ...]
    #: The parameter names this dataset accepts. A definition's `filters` keys
    #: are validated against this before anything reaches a query.
    filters: tuple[str, ...]
    #: Which of the two time hierarchies this dataset rolls up by default.
    time_hierarchy: str = "calendar"
    #: ⚠ FALSE on the three that do not accept limit/offset/sort in their
    #: owning module today. `DEF-PAY-4221` · `P2.12`.
    paginates: bool = True

    def column(self, name: str) -> Column | None:
        for col in self.columns:
            if col.name == name:
                return col
        return None

    def measure(self, name: str) -> Measure | None:
        for meas in self.measures:
            if meas.name == name:
                return meas
        return None

    def dimension_names(self) -> tuple[str, ...]:
        return tuple(dim.name for dim in self.dimensions)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "owner_module": self.owner_module,
            "grain": self.grain,
            "columns": [col.as_dict() for col in self.columns],
            "measures": [meas.as_dict() for meas in self.measures],
            "dimensions": [dim.as_dict() for dim in self.dimensions],
            "filters": list(self.filters),
            "time_hierarchy": self.time_hierarchy,
            "paginates": self.paginates,
        }


class UnlawfulTotal(ValueError):
    """Raised when a report asks for a total its measure cannot bear.

    A `ValueError` and not an API refusal on purpose: P0.16's outcome is that
    the sum is refused **at build time, naming the measure** — when a definition
    is saved or a registry is imported, not when a clerk is looking at a number
    that is already wrong.
    """


class DatasetError(ValueError):
    """A dataset declaration that breaks one of the hard rules."""


# ── The thirteen dimensions, declared once (brief §7.2.1) ───────────────────
#: Named separately from the datasets so *Service* is literally the same object
#: everywhere it appears — which is conformance enforced by identity rather
#: than by a test noticing two copies have drifted apart.
D_TIME = Dimension(
    name=DIM_TIME,
    attributes=("date", "year", "quarter", "accounting_period", "cycle", "day"),
    hierarchy=("year", "accounting_period", "day"),
    conformed=True,
)
D_SERVICE = Dimension(
    name=DIM_SERVICE,
    attributes=("service_code", "service_name"),
    conformed=True,
)
D_CONSUMER_CLASS = Dimension(
    name="consumer_class", attributes=("class_code", "class_name"), conformed=True
)
D_ACCOUNT_STATUS = Dimension(name="account_status", attributes=("status",), conformed=True)
D_CUSTOMER_TYPE = Dimension(
    name="customer_type", attributes=("customer_type",), conformed=True
)
#: ⚠ CLAUDE.md hard rule 8 — an address is stored on `premises` and NOWHERE
#: else, so the locality on every one of these datasets is WALKED to premises
#: and no dataset declares an address column of its own.
D_PREMISES = Dimension(
    name="premises",
    attributes=("premises_no", "locality", "lat", "lng"),
    hierarchy=("area", "route", "premises"),
    conformed=True,
)
#: A unit refines a premises by LABEL, not by address (`BR-MET-1161`) — and may
#: carry its own lat/lng where a cabin or a pad is somewhere its site office is
#: not (`BR-MET-1162`).
D_UNIT = Dimension(name="unit", attributes=("unit_label", "lat", "lng"), conformed=True)
D_ROUTE_CYCLE = Dimension(
    name="route_cycle",
    attributes=("route_code", "cycle_code"),
    hierarchy=("cycle", "route"),
    conformed=True,
)
D_AREA = Dimension(name="area", attributes=("area_code", "area_name"), conformed=True)
D_RATE_SCHEDULE = Dimension(
    name="rate_schedule", attributes=("plan_code", "schedule_code"), conformed=True
)
D_PAYMENT_PLAN = Dimension(name="payment_plan", attributes=("on_plan", "plan_kind"))
D_COLLECTIONS = Dimension(name="collections_state", attributes=("stage", "hold_reason"))
#: Derived — the five bands are a RECEIVABLES rule and the ageing report renders
#: whatever Payments defines (brief §05: *"Not a reports setting"*). Duplicating
#: the bands here is how two screens come to disagree.
D_AGE_BUCKET = Dimension(name="age_bucket", attributes=("bucket",))

#: The thirteen the ageing report inherits, in §7.2.1's own order.
AR_AGEING_DIMENSIONS: tuple[Dimension, ...] = (
    D_TIME,
    D_CONSUMER_CLASS,
    D_SERVICE,
    D_ACCOUNT_STATUS,
    D_CUSTOMER_TYPE,
    D_PREMISES,
    D_UNIT,
    D_ROUTE_CYCLE,
    D_AREA,
    D_RATE_SCHEDULE,
    D_PAYMENT_PLAN,
    D_COLLECTIONS,
    D_AGE_BUCKET,
)


def _money(name: str, basis: str) -> Column:
    return Column(name=name, type=TYPE_MONEY, money_basis=basis, scale=4)


def _pct(name: str) -> Column:
    return Column(name=name, type=TYPE_PERCENT, scale=6)


def _text(name: str) -> Column:
    return Column(name=name, type=TYPE_TEXT)


def _date(name: str) -> Column:
    return Column(name=name, type=TYPE_DATE)


def _count(name: str) -> Column:
    return Column(name=name, type=TYPE_COUNT)


# ════════════════════════════════════════════════════════════════════════════
# THE NINE
# ════════════════════════════════════════════════════════════════════════════
INVOICES = Dataset(
    code="invoices",
    owner_module="billing",
    # ⚠ **THIS READ "one invoice line" UNTIL 2026-09-26 (`DEF-REP-6834`) AND
    # ITS OWN COLUMNS SAID OTHERWISE.** `services` is a SET, `usage` carries a
    # unit from a sibling column because *"a bill measured in two units yields
    # 684 kWh|26.24 kgal"*, and `base`/`usage_revenue`/`tax`/`amount` are one
    # bill's money split by LINE KIND. Every one of those is a roll-up of lines
    # onto one bill. R5's drawing (p50, read as an image per B14 rule 42)
    # settles it from the other side: one row per `BL-…` number, `Water ·
    # Sewer` in one cell, `4,100 gal` in one cell, `247.87` in one cell — and
    # `apps/billing/reporting.py` has served exactly that shape since the
    # register was built.
    #
    # Nothing in this repository read the string except the line a clerk reads
    # under the report title, which is why it could be wrong for as long as it
    # was: a grain is a CLAIM about a query, and the query is what decides.
    grain="one bill",
    columns=(
        _text("invoice_no"),
        _text("account_no"),
        _text("customer_name"),
        _text("bill_type"),
        # The bill's own status word. `draft` never appears — the register
        # reads ISSUED documents — so this is `issued`, `paid`, `void` or
        # `corrected`, and a corrected bill is IN the register as itself
        # because the correction is a new row (hard rule 4).
        _text("status"),
        # R5's drawing carries this as a warning in its own words: *"The one
        # report where cycle must be a parameter, not a date range."* It is
        # both a column and a filter here.
        _text("cycle"),
        _text("services"),
        _date("issued_on"),
        # ⚠ THE SAME DATE AS `issued_on`, AND THAT IS NOT A DUPLICATE. A bill's
        # POSTING date is the day it was issued — the moment the document
        # became a financial record and the ledger entry was written
        # (`apps/billing/reporting.py`'s own docstring). Both names are
        # declared because a definition may say either; serving one of them
        # from `service_date` or `period_end` would invent a second date a bill
        # does not have, and those three diverge by weeks on a back-bill.
        _date("posted_on"),
        _date("due_date"),
        # ⚠ A bill measured in two units yields `684 kWh|26.24 kgal`, so the
        # unit rides in its OWN column per row rather than being a property of
        # this one. Hard rule 3 with a multi-service account in mind.
        Column(name="usage", type=TYPE_QUANTITY, unit_from="usage_unit"),
        _text("usage_unit"),
        _money("base", BASIS_POSTING),
        _money("usage_revenue", BASIS_POSTING),
        _money("tax", BASIS_POSTING),
        _money("amount", BASIS_POSTING),
        _text("flag"),
    ),
    measures=(
        measure("amount", AGG_SUM, ADD_FULL),
        measure("base", AGG_SUM, ADD_FULL),
        measure("usage_revenue", AGG_SUM, ADD_FULL),
        measure("tax", AGG_SUM, ADD_FULL),
        measure("usage", AGG_SUM, ADD_WITHIN_SERVICE),
        measure("bills", AGG_COUNT, ADD_FULL),
    ),
    dimensions=(
        D_TIME,
        D_SERVICE,
        D_CONSUMER_CLASS,
        D_ACCOUNT_STATUS,
        D_CUSTOMER_TYPE,
        D_PREMISES,
        D_UNIT,
        D_ROUTE_CYCLE,
        D_AREA,
        D_RATE_SCHEDULE,
    ),
    filters=(
        "from",
        "to",
        "bill_type",
        "service",
        "class",
        "cycle",
        "status",
        "period",
    ),
    time_hierarchy="billing",
    # ⚠ **TRUE SINCE 2026-09-26.** This read `False` with the comment
    # *"DEF-PAY-4221 · billing/reporting.py · P2.12"*, and it was accurate:
    # nothing in billing accepted `limit`/`offset`/`sort` for this dataset.
    # `apps/billing/reporting.py::invoices_dataset` now applies every criterion
    # as a `WHERE`, the order as an `ORDER BY` and the page as a
    # `LIMIT`/`OFFSET`, with the totals a SQL aggregate over the whole filtered
    # set — and `invoices_dataset_stream` serves a file from a generator
    # instead of a page. `P2.12` asserts this field, so flipping it without the
    # query would be a declaration that reads correct and enforces nothing.
    paginates=True,
)

PAYMENTS = Dataset(
    code="payments",
    owner_module="payments",
    # ⚠ **THIS READ `"one payment allocation"` UNTIL 2026-09-27, AND IT WAS
    # WRONG IN A WAY THAT DROPS MONEY (`DEF-REP-6853`, lane DS-PAYMENTS).**
    # An allocation is the payment→invoice row in `allocations`, and
    # `apps/payments/services.py` writes NONE of them for a payment whose
    # purpose does not allocate — `_allocate_and_post` branches on
    # `if not linkage.allocates:` and a **deposit**, a **prepay** and a
    # **plan-down** all take that branch. So an allocation-grain query serves
    # only BILL payments, and R1's own tiles — *Taken today*, *Payments* —
    # count and sum PAYMENTS. Measured on real PostgreSQL 16 at a perf tenant:
    # **400 of 2,066 payments are deposits**, so that grain would have served
    # 1,666 rows and a smaller day. A smaller day does not read as wrong.
    #
    # ⚠ **AND THE COLUMNS BELOW STILL SPAN THREE GRAINS, WHICH IS STATED
    # RATHER THAN SILENTLY TIDIED.** `current`, `d1_30`, `d31_60`, `d61_90`,
    # `d90_plus`, `total`, `days_late` and `dso_days` are one ACCOUNT's
    # position AS AT a date (R9/R10/R11's grain, served by
    # `apps/payments/reporting.ar_aging` and `apps/payments/outstandings`);
    # `deposits_held` is one account's SECURITY-DEPOSIT position, which lives
    # on `customers.accounts` (R20's grain). They are left declared because
    # R9's viewer names them and removing a column a live report reads would
    # break it; `payments_dataset` serves NONE of them and says so by name in
    # its `problems`, rather than serving a plausible zero that a footer would
    # then total. The split is the lane report's finding, not a silent edit.
    grain="one payment",
    columns=(
        _date("posted_on"),
        _date("cleared_on"),
        _text("account_no"),
        _text("customer_name"),
        _text("method_name"),
        _text("purpose"),
        _text("teller"),
        # The POSTING date since 2026-10-21 (DEF-PAY-10321, PO ruling) — it was
        # the clearing date while cleared meant the money arrived.
        _money("amount", BASIS_POSTING),
        _money("current", BASIS_POSTING),
        _money("d1_30", BASIS_POSTING),
        _money("d31_60", BASIS_POSTING),
        _money("d61_90", BASIS_POSTING),
        _money("d90_plus", BASIS_POSTING),
        _money("total", BASIS_POSTING),
        _money("deposits_held", BASIS_CLEARING),
        _pct("share_pct"),
        _pct("collection_rate"),
        _count("days_late"),
        _count("dso_days"),
    ),
    measures=(
        measure("amount", AGG_SUM, ADD_FULL),
        # ⚠ THE FIRST TRAP. An AR balance sums across ACCOUNTS and never across
        # TIME. Group the ageing report by month, total the column, and the
        # number means nothing — and nothing stopped you before this line.
        measure("total", AGG_SUM, ADD_SEMI),
        measure("current", AGG_SUM, ADD_SEMI),
        measure("d1_30", AGG_SUM, ADD_SEMI),
        measure("d31_60", AGG_SUM, ADD_SEMI),
        measure("d61_90", AGG_SUM, ADD_SEMI),
        measure("d90_plus", AGG_SUM, ADD_SEMI),
        measure("deposits_held", AGG_SUM, ADD_SEMI),
        measure("accounts_active", AGG_COUNT, ADD_SEMI),
        # ⚠ THE SECOND TRAP. These are recomputed from their components, never
        # averaged: the average of four route DSOs is not the utility's DSO.
        measure("dso_days", AGG_RECOMPUTE, ADD_NON),
        measure("collection_rate", AGG_RECOMPUTE, ADD_NON),
        measure("share_pct", AGG_RECOMPUTE, ADD_NON),
        measure("days_late", AGG_RECOMPUTE, ADD_NON),
        measure("payments", AGG_COUNT, ADD_FULL),
    ),
    dimensions=AR_AGEING_DIMENSIONS,
    filters=(
        "from",
        "to",
        "as_of",
        "purpose",
        "method",
        "teller",
        "class",
        "service",
        "status",
        "bucket",
        # ⚠ `band` and `premises` are the AR ageing screen's own live filter
        # names (`apps/reports/queries.py` reads `f.band` and `f.premises`).
        # They are declared here rather than special-cased in the runner,
        # because a filter the dataset does not declare is one the runner drops
        # — and a dropped filter on the ageing report shows the WHOLE
        # receivable under a chip that says otherwise.
        "band",
        "premises",
        "collections_stage",
        "on_plan",
        "route",
        "period",
    ),
    # ⚠ **TRUE SINCE 2026-09-27.** This read `False` with the comment
    # *"DEF-PAY-4221 · payments/reporting.py · P2.12"*, and it was accurate:
    # nothing in payments accepted `limit`/`offset`/`sort` for this dataset.
    # `apps/payments/payments_dataset.py::payments_dataset` now applies every
    # criterion as a `WHERE`, the order as an `ORDER BY` and the page as a
    # `LIMIT`/`OFFSET`, with the totals a SQL aggregate over the whole filtered
    # set — and `payments_dataset_stream` serves a file from a generator that
    # takes no `page` and no `per`, so an export has no argument through which
    # to inherit a screen's page. `P2.12` asserts this field, so flipping it
    # without the query would be a declaration that reads correct and enforces
    # nothing — which this registry has shipped once already.
    #
    # ⚠ **`DEF-PAY-4221` IS NOT CLOSED BY THIS.** That defect names
    # `GET /outstandings`, `GET /cheques` and the bank-rec batch list, which
    # are OTHER reads in the same module; this flag is about the DATASET
    # query, and those three are untouched here.
    paginates=True,
)

JOURNAL_LINES = Dataset(
    code="journal_lines",
    owner_module="ledger",
    grain="one journal line",
    columns=(
        _date("posted_on"),
        _text("account_code"),
        _text("account_name"),
        _text("reference"),
        _text("narrative"),
        _money("debit", BASIS_POSTING),
        _money("credit", BASIS_POSTING),
        _money("balance", BASIS_POSTING),
    ),
    measures=(
        measure("debit", AGG_SUM, ADD_FULL),
        measure("credit", AGG_SUM, ADD_FULL),
        # A running balance is a position, not a flow — semi-additive for the
        # same reason an AR balance is.
        measure("balance", AGG_SUM, ADD_SEMI),
        measure("lines", AGG_COUNT, ADD_FULL),
    ),
    dimensions=(
        D_TIME,
        D_SERVICE,
        D_CONSUMER_CLASS,
        D_ACCOUNT_STATUS,
        D_CUSTOMER_TYPE,
        D_PREMISES,
        D_UNIT,
        D_AREA,
    ),
    # ⚠ **`source_type` AND `target` WERE ADDED WITH THE QUERY (2026-09-26, lane
    # DS-LEDGER) BECAUSE THE QUERY HONOURS THEM.** `runner.bind` DROPS any
    # parameter a dataset does not declare, so a filter the query applies and
    # this tuple omits would be silently discarded on the way in — a control
    # that looks live, changes nothing, and reports no error. That is hard-won
    # law 2's mirror in a data structure, and `runner.dropped()` exists so the
    # question has an answer rather than being inferred from a row count.
    filters=(
        "from",
        "to",
        "account_from",
        "account_to",
        "service",
        "basis",
        "source_type",
        "target",
        # ⚠ **`level` AND `authority` ARE HERE BECAUSE THE VIEWERS READ THEM.**
        # R15's `Level` (Detail / Summary, p055) and R18's `Authority` (p057)
        # are drawn controls; `bind` drops any name this tuple omits, so
        # leaving them out would have shipped two selects that change the URL
        # and nothing else — and `runner.dropped()` would have been the only
        # place in the product that knew.
        "level",
        "authority",
    ),
    # ⚠ **PAGED SINCE 2026-09-26 — `apps/ledger/journal_lines_dataset.py`.** It
    # read `False` with `DEF-PAY-4221` beside it while NOTHING implemented this
    # dataset at all, so the flag was true of a query that did not exist. The
    # query now applies `limit`/`offset`/`sort` in SQL (brief §7.5) with no cap
    # on the export branch (`NFR-5`), and `P2.12` asserts this field rather than
    # reading a paragraph.
    paginates=True,
)

METER_READS = Dataset(
    code="meter_reads",
    owner_module="metering",
    grain="one meter read",
    columns=(
        _date("read_on"),
        _text("account_no"),
        _text("meter_no"),
        _text("channel"),
        # ⚠ Hard rule 3, and the reason there is no Total usage tile on a
        # multi-service account: every quantity carries its unit in its OWN
        # column (R30's drawing says so in as many words).
        Column(name="reading", type=TYPE_QUANTITY, unit_from="unit"),
        Column(name="consumption", type=TYPE_QUANTITY, unit_from="unit"),
        _text("unit"),
        # ⚠ R45 cannot state a basis and R28 cannot separate a read gap from a
        # scheduling gap without this column (§05, metering's row).
        _text("read_basis"),
        _text("flag"),
    ),
    measures=(
        measure("consumption", AGG_SUM, ADD_WITHIN_SERVICE),
        measure("reads", AGG_COUNT, ADD_FULL),
        measure("completeness_pct", AGG_RECOMPUTE, ADD_NON),
    ),
    dimensions=(
        D_TIME,
        D_SERVICE,
        D_CONSUMER_CLASS,
        D_PREMISES,
        D_UNIT,
        D_ROUTE_CYCLE,
        D_AREA,
        D_RATE_SCHEDULE,
    ),
    # ⚠ **`source`, `result` AND `status` ARE HERE BECAUSE R32'S VIEWER READS
    # THEM (`P6.11`)** — the drawn `Source` and `Result` selects on p064, plus
    # the batch status. `result` is a HAVING over the row counts rather than a
    # stored column, which is why it must be declared here AND honoured there:
    # a filter this tuple omits is dropped by `runner.bind` before any query
    # sees it, and the report would then show every import under a chip saying
    # `AMI batch`.
    filters=(
        "from",
        "to",
        "service",
        "route",
        "cycle",
        "channel",
        "read_basis",
        "flag",
        "source",
        "result",
        "status",
    ),
)

ASSETS = Dataset(
    code="assets",
    owner_module="metering",
    grain="one asset",
    columns=(
        _text("asset_no"),
        _text("asset_type"),
        _text("make_model"),
        _text("status"),
        _date("installed_on"),
        _date("last_read_on"),
        _text("premises_no"),
        _text("unit_label"),
        Column(name="size", type=TYPE_QUANTITY, unit_from="size_unit"),
        _text("size_unit"),
    ),
    measures=(measure("assets", AGG_COUNT, ADD_SEMI),),
    dimensions=(D_TIME, D_SERVICE, D_PREMISES, D_UNIT, D_ROUTE_CYCLE, D_AREA),
    filters=("as_of", "service", "asset_type", "status", "route", "area"),
)

ACCOUNTS = Dataset(
    code="accounts",
    owner_module="customers",
    grain="one account",
    columns=(
        _text("account_no"),
        _text("customer_name"),
        _text("customer_type"),
        _text("account_class"),
        _text("status"),
        _date("opened_on"),
        _date("closed_on"),
        _text("premises_no"),
        _text("unit_label"),
        # ⚠ Hard rule 8 — walked to `premises`, never a column of its own here.
        _text("locality"),
        _money("balance", BASIS_POSTING),
    ),
    measures=(
        measure("accounts", AGG_COUNT, ADD_SEMI),
        measure("balance", AGG_SUM, ADD_SEMI),
    ),
    dimensions=(
        D_TIME,
        D_SERVICE,
        D_CONSUMER_CLASS,
        D_ACCOUNT_STATUS,
        D_CUSTOMER_TYPE,
        D_PREMISES,
        D_UNIT,
        D_ROUTE_CYCLE,
        D_AREA,
        D_RATE_SCHEDULE,
        D_PAYMENT_PLAN,
        D_COLLECTIONS,
    ),
    # ⚠ **`event` AND `account` ARE HERE BECAUSE R23'S VIEWER READS THEM
    # (`P6.11`)** — p060's third control, `Event`, and the account a
    # drill-through arrives with. `from`/`to` were already declared and R23
    # strikes them on `occurred_at`, which is its own basis and not R22's.
    filters=(
        "as_of",
        "from",
        "to",
        "class",
        "status",
        "customer_type",
        "service",
        "route",
        "event",
        "account",
    ),
)

RATE_SCHEDULES = Dataset(
    code="rate_schedules",
    owner_module="rating",
    grain="one rate-schedule version",
    columns=(
        _text("plan_code"),
        _text("plan_name"),
        _text("schedule_code"),
        _text("service_code"),
        _date("effective_from"),
        _date("effective_to"),
        # ⚠ R37 IS THE ONE REPORT THAT MUST NOT ROUND. Hard rule 2 stores money
        # to 4 and percentages to 6, and this report displays them at the
        # precision the rule STORES — trimming to two here would change what a
        # signed rate means.
        Column(name="unit_rate", type=TYPE_MONEY, money_basis=BASIS_EVENT, scale=4),
        _pct("percentage"),
        _text("changed_by"),
    ),
    measures=(measure("versions", AGG_COUNT, ADD_FULL),),
    dimensions=(D_TIME, D_SERVICE, D_CONSUMER_CLASS, D_RATE_SCHEDULE),
    filters=("as_of", "from", "to", "service", "plan"),
)

AUDIT_LOG = Dataset(
    code="audit_log",
    owner_module="notifications",
    grain="one audit event",
    columns=(
        _date("event_at"),
        _text("actor"),
        _text("actor_role"),
        _text("action"),
        _text("entity"),
        _text("entity_ref"),
        _text("channel"),
        _text("status"),
        _text("reason"),
        # The two facts §05's identity row names, as ATTRIBUTES on this dataset
        # rather than as a tenth dataset of their own.
        _date("last_sign_in_at"),
        _text("added_by"),
    ),
    measures=(measure("events", AGG_COUNT, ADD_FULL),),
    dimensions=(D_TIME, D_SERVICE, D_ACCOUNT_STATUS),
    # ⚠ **`as_of` AND `role` ARE HERE BECAUSE R36'S VIEWER READS THEM
    # (`P6.11`).** `runner.bind` DROPS any parameter a dataset does not declare,
    # so leaving them out would have shipped the drawn `As of` and `Role`
    # controls as two inputs that change the URL and nothing else — hard-won law
    # 2's mirror, and `runner.dropped()` would have been the only place in the
    # product that knew. They are honoured by `apps/identity/access_review.py`
    # and by nothing else on this dataset; R35's own query neither reads nor
    # needs them, which is the same posture `level` and `authority` already have
    # on `JOURNAL_LINES`.
    filters=("from", "to", "actor", "action", "entity", "channel", "status", "as_of", "role"),
)

WORK_ORDERS = Dataset(
    code="work_orders",
    owner_module="work",
    grain="one work order",
    columns=(
        _text("order_no"),
        _text("order_type"),
        _text("priority"),
        _text("status"),
        _text("crew"),
        _text("technician"),
        _date("raised_on"),
        _date("completed_on"),
        _text("account_no"),
        _text("premises_no"),
        Column(name="duration", type=TYPE_QUANTITY, unit="hours"),
    ),
    measures=(
        measure("orders", AGG_COUNT, ADD_FULL),
        measure("duration", AGG_SUM, ADD_FULL),
        measure("on_time_pct", AGG_RECOMPUTE, ADD_NON),
    ),
    dimensions=(D_TIME, D_SERVICE, D_PREMISES, D_UNIT, D_ROUTE_CYCLE, D_AREA, D_ACCOUNT_STATUS),
    filters=("from", "to", "order_type", "status", "priority", "crew", "service"),
)

#: The nine, in the order §05's own table names their owners.
#: ⚠ **THE TENTH DATASET — `CR-184-BRC10`, 2026-10-14.** The PO went to build
#: *"receivables over 90 days by service"* in the builder and found nothing to
#: build it on: none of the nine holds what is STILL OWED. This one does, and
#: its grain is not a bill and not a payment but a POSITION — what one account
#: owes on one service (or on one class row: *Taxes*, *Fees*, *Other charges*,
#: for lines that name no service) at the as-of date, aged per bill on its own
#: due date. The sharing rule is the PO's (decision log 2026-10-14, C1 → a)
#: and lives in `apps/payments/receivables_by_service.py`. Every money column
#: is a BALANCE, so every measure is semi-additive: it sums across accounts and
#: services, never across time.
RECEIVABLES = Dataset(
    code="receivables",
    owner_module="payments",
    grain="one account and service",
    columns=(
        _text("account_no"),
        _text("customer_name"),
        _text("service"),
        _text("service_code"),
        # The class row a line naming no service lands on — `taxes`, `fees`,
        # `usage_base`, `other` — and empty on a service row. A vocabulary
        # value, translated on screen (`reports.value.charge_class.*`).
        _text("charge_class"),
        _money("current", BASIS_POSTING),
        _money("d1_30", BASIS_POSTING),
        _money("d31_60", BASIS_POSTING),
        _money("d61_90", BASIS_POSTING),
        _money("d90_plus", BASIS_POSTING),
        _money("total", BASIS_POSTING),
    ),
    measures=(
        measure("current", AGG_SUM, ADD_SEMI),
        measure("d1_30", AGG_SUM, ADD_SEMI),
        measure("d31_60", AGG_SUM, ADD_SEMI),
        measure("d61_90", AGG_SUM, ADD_SEMI),
        measure("d90_plus", AGG_SUM, ADD_SEMI),
        measure("total", AGG_SUM, ADD_SEMI),
    ),
    dimensions=(D_TIME, D_SERVICE, D_AGE_BUCKET),
    # ⚠ `to` IS THE AS-OF BOX's OWN PARAMETER — the viewer's *As of* control
    # writes the date into `to`, exactly as it does for the ageing, and
    # `runner.bind` drops a name the dataset does not declare. Without it the
    # box showed the date typed while the report answered the period end
    # (found on the walk of 2026-10-14). `as_of` is the same date by name.
    filters=("as_of", "to", "service"),
    paginates=True,
)

DATASETS: tuple[Dataset, ...] = (
    INVOICES,
    PAYMENTS,
    JOURNAL_LINES,
    METER_READS,
    ASSETS,
    ACCOUNTS,
    RATE_SCHEDULES,
    AUDIT_LOG,
    WORK_ORDERS,
    RECEIVABLES,
)

BY_CODE: dict[str, Dataset] = {dataset.code: dataset for dataset in DATASETS}


# ── The rules this declaration must itself obey ─────────────────────────────
def _validate() -> None:
    """Refuse a declaration that breaks a hard rule, AT IMPORT.

    This is the module's own law 7: a registry that declares a quantity without
    a unit is precisely the thing hard rule 3 forbids, and a check that runs
    only when somebody remembers to call it is a check nothing reads. It runs
    when this module is imported, so a dataset added without a unit cannot
    start the server.
    """
    seen: set[str] = set()
    for dataset in DATASETS:
        if dataset.code in seen:
            raise DatasetError(f"dataset {dataset.code!r} is declared twice")
        seen.add(dataset.code)
        if dataset.time_hierarchy not in TIME_HIERARCHIES:
            raise DatasetError(
                f"dataset {dataset.code!r} rolls up by {dataset.time_hierarchy!r}, "
                f"which is not one of {tuple(TIME_HIERARCHIES)}"
            )
        for col in dataset.columns:
            if col.type not in COLUMN_TYPES:
                raise DatasetError(f"{dataset.code}.{col.name}: unknown type {col.type!r}")
            if col.type == TYPE_QUANTITY and not (col.unit or col.unit_from):
                raise DatasetError(
                    f"{dataset.code}.{col.name}: a quantity carries its unit "
                    "(CLAUDE.md hard rule 3) — set `unit` or `unit_from`"
                )
            if col.type == TYPE_MONEY:
                if col.money_basis not in MONEY_BASES:
                    raise DatasetError(
                        f"{dataset.code}.{col.name}: a money column names its date "
                        "basis (BR-REP-001)"
                    )
                if col.scale != 4:
                    raise DatasetError(
                        f"{dataset.code}.{col.name}: money is stored to 4 decimals "
                        "(CLAUDE.md hard rule 2)"
                    )
            if col.type == TYPE_PERCENT and col.scale != 6:
                raise DatasetError(
                    f"{dataset.code}.{col.name}: a percentage is stored to 6 decimals "
                    "(CLAUDE.md hard rule 2)"
                )
            if col.unit_from and dataset.column(col.unit_from) is None:
                raise DatasetError(
                    f"{dataset.code}.{col.name}: names {col.unit_from!r} as its unit "
                    "column and the dataset does not produce it"
                )
        for meas in dataset.measures:
            if meas.aggregation not in AGGREGATIONS:
                raise DatasetError(
                    f"{dataset.code}.{meas.name}: unknown aggregation {meas.aggregation!r}"
                )
            if meas.additivity not in ADDITIVITIES:
                raise DatasetError(
                    f"{dataset.code}.{meas.name}: unknown additivity {meas.additivity!r}"
                )
        for dim in dataset.dimensions:
            if dim.hierarchy is not None and len(dim.hierarchy) < 2:
                raise DatasetError(
                    f"{dataset.code}.{dim.name}: a hierarchy of one level is a flat "
                    "dimension — set `hierarchy=None`"
                )


_validate()


def assert_summable(dataset_code: str, measure_name: str, across: tuple[str, ...]) -> None:
    """P0.16's outcome, in one function: refuse an unlawful total BY NAME.

    `across` is the dimensions the total would cross — the definition's
    `group_by`, or the whole dimension set when a footer totals a column.

    The message names the MEASURE and the DIRECTION, because *"unlawful total"*
    tells a person nothing they can act on and *"`total` is a balance: it sums
    across accounts, never across time"* tells them exactly what to change.
    """
    dataset = BY_CODE.get(dataset_code)
    if dataset is None:
        raise UnlawfulTotal(f"no dataset named {dataset_code!r}")
    meas = dataset.measure(measure_name)
    if meas is None:
        # Not a measure at all — an attribute is never totalled, so there is
        # nothing to refuse and nothing to permit.
        return
    if meas.additivity == ADD_NON:
        raise UnlawfulTotal(
            f"{dataset_code}.{measure_name} is non-additive: it must be recomputed "
            f"from its components, never aggregated — the average of four routes' "
            f"{measure_name} is not the utility's {measure_name}."
        )
    crossed = tuple(dim for dim in meas.forbidden_across if dim in across)
    if crossed:
        raise UnlawfulTotal(
            f"{dataset_code}.{measure_name} is {meas.additivity}-additive and cannot "
            f"be summed across {', '.join(crossed)}."
        )


def registry_payload() -> dict[str, Any]:
    """`GET /reports/datasets` — P0.4's metadata endpoint.

    Serves the declaration rather than a summary of it: the edit panel says
    *"13 available"* and *"4 of 7 shown"* by counting what is here, so a screen
    and the engine can never be counting different things.
    """
    return {
        "datasets": [dataset.as_dict() for dataset in DATASETS],
        "count": len(DATASETS),
        "time_hierarchies": {name: list(levels) for name, levels in TIME_HIERARCHIES.items()},
        "additivity": list(ADDITIVITIES),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 0 · P0.4 · P0.16 (05-prototype/09 Reports Build Brief.pdf §05 p75-77, §7.2 p82-85, read as images per B14 rule 42)
# screens: none — Phase 0 ships no screen
# generated: 2026-09-26 by lane REP-P0A
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `_validate()` was shown to raise on a quantity column with no unit and on a money column with no basis before the declarations were completed
# exceptions: (1) the document says NINE datasets and its own §05 table lists TEN owners — resolved here with the reasoning in the docstring, filed as DEF-REP-6797, NOT resolved silently · (2) `identity` is attributes on `audit_log` rather than a dataset · (3) `metering` owns TWO because a dataset states ONE grain
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
