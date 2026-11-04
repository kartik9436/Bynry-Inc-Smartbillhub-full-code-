# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.17 (slicers derived from the dataset's
#           declared dimensions; group by up to three levels with subtotals) ·
#           P2.25 (ONE calendar per report; mixing refused) · P2.26 (four
#           visible slicers, the rest behind `+ Filter`).
#           Screens: 2·1 slicer bar · 2·1 group rows · 2·2 group slots.
# Rules:    brief §7.2.1 / §7.2.1B / §7.2.3, read as images from p83, p84 and
#           p85 per B14 rule 42 · CLAUDE.md hard rule 2 (money 4 dp, DISPLAY 2)
#           · hard rule 3 (a quantity carries its unit) · NFR-3 · NFR-5 (no
#           hard caps — the THREE-LEVEL limit is a drawn control, not a cap on
#           data, see below)
# Tests:    06-backend/tests/test_rep_p2_17_slicers.py
#           06-backend/tests/test_rep_p2_25_calendar.py
# Impacts:  apps/reports/additivity.py (a subtotal asks it the same question a
#           footer does) · apps/reports/runner.py (`validate`) ·
#           apps/reports/api.py · 07-frontend 2·1 slicer bar
# ───────────────────────────────────────────────────────
"""SLICERS AND GROUP LEVELS, DERIVED FROM THE MODEL RATHER THAN HAND-PICKED.

THE FINDING THIS ANSWERS, IN THE PO's OWN TERMS
───────────────────────────────────────────────
AR Ageing shows **two** slicers. Its fact has **thirteen** dimensions —
measured, not quoted: `len(datasets.AR_AGEING_DIMENSIONS)` is 13 and they are
time, consumer class, service, account status, customer type, premises, unit,
route/cycle, area, rate schedule, payment plan, collections state and age
bucket. Eleven of those are things the server already reads and no control was
ever drawn for. Multiply two-of-thirteen by 45 reports (p84) and the
hand-picking IS the problem.

So a slicer is not a thing a report declares any more. It is a thing a DATASET
declares, and every definition built on that dataset inherits all of them the
moment the dimension is added — *"adding a dimension to a dataset makes it
available on every report built on it, with no report edited"* (p12).

⚠ **FOUR ARE VISIBLE AND THE REST ARE ONE CLICK AWAY (`P2.26`).** p12: *"⚠
Thirteen chips on screen is a worse screen, not a better one."* Inheriting
thirteen dimensions and rendering thirteen chips would answer the PO's finding
by making the screen unusable, which is not answering it. The definition names
the four; `visible_slicers()` falls back to the first four DECLARED when it
names none, so a dataset gains a dimension without a screen gaining a chip.

THREE LEVELS, AND WHY THAT IS NOT AN `NFR-5` HARD CAP
─────────────────────────────────────────────────────
`MAX_GROUP_LEVELS = 3` is p12 and p84's *"group by up to three levels with
subtotals"* — a count of DRAWN CONTROLS (*"Group by becomes three slots"*), not
a ceiling on rows, accounts or tenants. `NFR-5` forbids a per-tenant cap, an
account maximum or an unpaginated list; it does not forbid a screen having
three dropdowns. The distinction matters because the T4 flexibility rule is
negative — nobody may add a cap that would have to be REMOVED when T4 arrives —
and a fourth group slot would be a screen change, never a migration.

⚠ **WHERE A SUBTOTAL'S ADDITIVITY QUESTION DIFFERS FROM A FOOTER'S, AND IT IS
THE THING THAT MAKES THIS MODULE CORRECT RATHER THAN CAUTIOUS.**
Group AR Ageing by month. There are two sums on that screen and only ONE of
them is unlawful:

  · **Each month's subtotal** holds `time` FIXED. It is the receivable within
    one month, summed across accounts, which is exactly what a balance is for.
    **Lawful, and it must render as a number** — a module that refused it would
    make grouping useless and would satisfy every refusal test in the suite.
  · **The grand total in the footer** spans every month. It sums a balance
    ACROSS TIME, and §7.2.2 says the number means nothing.

So `across` — the thing `additivity.refusal_for` asks about — is *what this sum
SPANS*, and a group level that is FIXED is not spanned. `subtotal_across()` and
`footer_across()` are two functions for that reason and a single shared one
would be wrong for one of them whichever way it was written.

WHY THE TIME LEVELS DO NOT COME FROM THE TIME DIMENSION (`DEF-REP-6846`)
───────────────────────────────────────────────────────────────────────
The obvious implementation reads `Dimension.hierarchy` for every dimension
including `time`. **Measured, that is wrong on all nine datasets.** `D_TIME` is
ONE shared frozen object and its hierarchy is hardcoded
`("year", "accounting_period", "day")`, while `TIME_HIERARCHIES` declares
calendar as `("year", "quarter", "accounting_period", "day")` and billing as
`("year", "cycle", "day")`. It agrees with neither, on any of them — and on
`invoices`, which declares `time_hierarchy="billing"`, it offers
`accounting_period`, a CALENDAR level. That is §7.2.3's *"a report that mixes
them is wrong in a way no total will reveal"* shipped in the declaration
itself, invisible because nothing read the field until this module.

**So the time levels come from `dataset.time_hierarchy` through
`TIME_HIERARCHIES`, and never from `D_TIME.hierarchy`**, and
`test_rep_p2_25_calendar.py` asserts the two agree for every dataset so the
next person to add a hierarchy cannot add it on one side only.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Iterable, Mapping, Sequence

from apps.reports import additivity, datasets

#: p12 · p84 — *"Group by becomes three slots"*. A drawn control count, NOT an
#: `NFR-5` cap. See the docstring.
MAX_GROUP_LEVELS = 3

#: `P2.26` — *"Four visible slicers, named by the definition, and `+ Filter`
#: opens the rest."*
VISIBLE_SLICERS = 4

#: Levels that belong to ONE calendar only. Derived from `TIME_HIERARCHIES`
#: rather than typed, so a third hierarchy cannot be added without these
#: moving with it.
_CALENDAR = frozenset(datasets.TIME_HIERARCHIES["calendar"])
_BILLING = frozenset(datasets.TIME_HIERARCHIES["billing"])
#: `year` and `day` mean the same thing in both and discriminate nothing.
NEUTRAL_LEVELS: frozenset[str] = _CALENDAR & _BILLING
CALENDAR_ONLY_LEVELS: frozenset[str] = _CALENDAR - _BILLING
BILLING_ONLY_LEVELS: frozenset[str] = _BILLING - _CALENDAR

#: A dataset FILTER name → the calendar it commits the report to. `from`, `to`
#: and `as_of` are plain dates and commit it to neither.
_FILTER_CALENDAR: dict[str, str] = {
    "period": "calendar",
    "accounting_period": "calendar",
    "quarter": "calendar",
    "cycle": "billing",
}


#: ⚠ **THE DIMENSION → FILTER MAP, AND WHY IT IS A TABLE AND NOT AN INFERENCE
#: (`DEF-REP-6847`).**
#:
#: `P0.16` declares dimensions with attribute names (`consumer_class` →
#: `class_code`, `class_name`) and each dataset separately declares the filters
#: it accepts (`class`) and the columns it produces (`account_class`).
#: **Nothing compared the two until this module.** Measured across the nine:
#: **71 dimensions declared, 14 whose name or one of whose attributes is among
#: that dataset's own columns, 57 not** — and on `payments`, which serves AR
#: Ageing, it is **0 of 13**.
#:
#: So *"AR Ageing goes from 2 slicers to the 13 its fact actually has, free"*
#: is **not free**. Deriving thirteen controls from the declaration alone would
#: render thirteen chips that filter nothing and group nothing: hard-won law 2,
#: dead UI, multiplied by 45 reports.
#:
#: This table is the honest bridge. A dimension is SERVABLE as a slicer when
#: the dataset accepts a filter for it, and GROUPABLE when a served row carries
#: a column for it. The two are different questions with different answers and
#: a dimension may be one, both or neither. An entry that is not here is not
#: offered — which is a shorter slicer bar than the brief draws, and correct,
#: rather than a longer one that does nothing.
_DIMENSION_FILTER: dict[str, tuple[str, ...]] = {
    datasets.DIM_TIME: ("from", "to", "as_of", "period"),
    "consumer_class": ("class",),
    "service": ("service",),
    "account_status": ("status",),
    "customer_type": ("customer_type",),
    "premises": ("premises",),
    "route_cycle": ("route", "cycle"),
    "area": ("area",),
    "rate_schedule": ("plan",),
    "payment_plan": ("on_plan",),
    "collections_state": ("collections_stage",),
    "age_bucket": ("bucket", "band"),
}

#: The row column a dimension's VALUE arrives in, where one exists. Same
#: reasoning: measured against what each dataset says it produces, never
#: inferred from the dimension's own attribute names.
_DIMENSION_COLUMN: dict[str, tuple[str, ...]] = {
    "consumer_class": ("account_class", "class", "class_code"),
    "service": ("service", "service_code", "service_name"),
    "account_status": ("status",),
    "customer_type": ("customer_type",),
    "premises": ("premises_no", "premises"),
    "unit": ("unit_label", "unit"),
    "route_cycle": ("route_code", "route", "cycle_code", "cycle"),
    "area": ("area_code", "area"),
    "rate_schedule": ("plan_code", "schedule_code", "plan"),
    "payment_plan": ("on_plan",),
    "collections_state": ("stage",),
    "age_bucket": ("bucket",),
}


def filter_for(dataset_code: str, dimension_name: str) -> str | None:
    """The filter name this dataset accepts for this dimension, or None."""
    dataset = datasets.BY_CODE.get(dataset_code)
    if dataset is None:
        return None
    for candidate in _DIMENSION_FILTER.get(dimension_name, ()):
        if candidate in dataset.filters:
            return candidate
    return None


def column_for(dataset_code: str, dimension_name: str) -> str | None:
    """The served column carrying this dimension's value, or None.

    Checked against the dataset's DECLARED columns — which is the half
    `DEF-REP-6847` records nobody had checked.
    """
    dataset = datasets.BY_CODE.get(dataset_code)
    if dataset is None:
        return None
    names = {col.name for col in dataset.columns}
    for candidate in (dimension_name, *_DIMENSION_COLUMN.get(dimension_name, ())):
        if candidate in names:
            return candidate
    return None


class GroupingRefused(ValueError):
    """A grouping this dataset will not serve. Raised at SAVE, never at render.

    Render-time this would be an error page over a report that is mostly fine;
    save-time it is a refusal a clerk can act on before any harm — the same
    split `P0.16` already made for an unlawful total.
    """


class CalendarMixed(GroupingRefused):
    """`P2.25` — one report, two time hierarchies.

    *"A billing cycle does not sit inside a calendar month. It straddles two."*
    The message NAMES BOTH sides, because *"mixed calendars"* tells a clerk
    nothing they can change and *"filtering by accounting period and grouping
    by cycle"* tells them exactly which of the two to drop.
    """


# ── The calendar (P2.25) ────────────────────────────────────────────────────
def time_levels(dataset_code: str) -> tuple[str, ...]:
    """The time levels THIS dataset may be grouped by.

    From `dataset.time_hierarchy`, never from `D_TIME.hierarchy` — see the
    module docstring and `DEF-REP-6846`.
    """
    dataset = datasets.BY_CODE.get(dataset_code)
    if dataset is None:
        return ()
    return tuple(datasets.TIME_HIERARCHIES[dataset.time_hierarchy])


def calendar_of(level: str) -> str | None:
    """Which hierarchy a level commits a report to, or `None` for neutral."""
    if level in NEUTRAL_LEVELS:
        return None
    if level in CALENDAR_ONLY_LEVELS:
        return "calendar"
    if level in BILLING_ONLY_LEVELS:
        return "billing"
    return None


def calendar_of_filter(name: str) -> str | None:
    """Which hierarchy a FILTER commits a report to, or `None`.

    The `f.` prefix the ageing screen sends is stripped first — `runner`'s own
    comment records that dropping it would have widened a shipped screen in
    silence, and a calendar check that could not see `f.cycle` would be a check
    that cannot fail on the one screen that sends it.
    """
    bare = name[2:] if name.startswith("f.") else name
    return _FILTER_CALENDAR.get(bare)


def assert_one_calendar(
    dataset_code: str, group_by: Sequence[str] = (), filters: Iterable[str] = ()
) -> None:
    """`P2.25`'s outcome: *"filtering by accounting period AND grouping by
    cycle is refused at save, naming both."*"""
    committed: dict[str, list[str]] = {"calendar": [], "billing": []}
    for level in group_by:
        which = calendar_of(level)
        if which:
            committed[which].append(f"grouping by {level}")
    for name in filters:
        which = calendar_of_filter(name)
        if which:
            committed[which].append(f"filtering by {name}")
    if committed["calendar"] and committed["billing"]:
        raise CalendarMixed(
            f"{dataset_code}: a report rolls up ONE calendar. "
            f"{committed['calendar'][0]} is the calendar hierarchy and "
            f"{committed['billing'][0]} is the billing hierarchy — a billing "
            "cycle straddles two months, so the two do not nest. Drop one."
        )


def declared_calendar(dataset_code: str) -> str:
    """What the head says — *"Grouped by billing cycle"* (p84's Time hierarchy
    row). A report states which, always, because one that does not is one a
    reader assumes about."""
    dataset = datasets.BY_CODE.get(dataset_code)
    return "calendar" if dataset is None else dataset.time_hierarchy


# ── The slicers (P2.17 · P2.26) ─────────────────────────────────────────────
def levels_for(dataset_code: str, dimension_name: str) -> tuple[str, ...]:
    """The levels this dimension may be grouped at, coarse → fine.

    `time` is answered from the dataset's declared calendar; every other
    dimension from its own `hierarchy`, or itself when it is flat.
    """
    dataset = datasets.BY_CODE.get(dataset_code)
    if dataset is None:
        return ()
    if dimension_name == datasets.DIM_TIME:
        return time_levels(dataset_code)
    for dim in dataset.dimensions:
        if dim.name == dimension_name:
            return tuple(dim.hierarchy) if dim.hierarchy else (dim.name,)
    return ()


def slicers_for(
    dataset_code: str, definition_filters: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    """EVERY dimension the dataset declares, as a slicer. `P2.17`, entire.

    The list is the whole thirteen for AR Ageing; `visible` marks the four the
    bar shows and `+ Filter` opens the rest (`P2.26`). The definition names its
    four through `filters["slicers"]`; when it names none the first four
    DECLARED are visible, so a dataset gaining a dimension never silently
    gains a chip on 45 screens.
    """
    dataset = datasets.BY_CODE.get(dataset_code)
    if dataset is None:
        return []
    named = ()
    if isinstance(definition_filters, Mapping):
        raw = definition_filters.get("slicers")
        if isinstance(raw, (list, tuple)):
            named = tuple(
                name
                for name in raw
                if isinstance(name, str) and name in dataset.dimension_names()
            )
    # ⚠ **ONLY A SERVABLE DIMENSION MAY BE VISIBLE** (`DEF-REP-6847`). A chip
    # for a dimension this dataset accepts no filter for is a control that
    # filters nothing — hard-won law 2, and the reason this list is shorter
    # than the thirteen the brief draws on some datasets.
    servable = tuple(
        dim.name for dim in dataset.dimensions if filter_for(dataset_code, dim.name)
    )
    chosen = tuple(name for name in named if name in servable)
    visible = chosen[:VISIBLE_SLICERS] or servable[:VISIBLE_SLICERS]
    return [
        {
            "name": dim.name,
            "attributes": list(dim.attributes),
            "levels": list(levels_for(dataset_code, dim.name)),
            "conformed": dim.conformed,
            "filters_with": filter_for(dataset_code, dim.name),
            "groups_by": column_for(dataset_code, dim.name),
            # False = declared by the model and honoured by nothing on this
            # dataset. Served rather than hidden, so a screen can say *"not on
            # this report"* instead of a reader wondering where it went.
            "servable": dim.name in servable,
            "visible": dim.name in visible,
        }
        for dim in dataset.dimensions
    ]


def visible_slicers(
    dataset_code: str, definition_filters: Mapping[str, Any] | None = None
) -> tuple[str, ...]:
    """The four on the bar, **IN THE DEFINITION'S OWN ORDER**.

    ⚠ The order is the definition's and not the declaration's, because the four
    are a thing a clerk chose and a bar that silently re-sorted them would be
    the same fault as a table re-sorting a chosen caret — hard-won law 2's
    mirror, a live control something downstream overrules. `slicers_for` keeps
    DECLARATION order, because that list is the model and not a choice.
    """
    entries = slicers_for(dataset_code, definition_filters)
    visible = {entry["name"] for entry in entries if entry["visible"]}
    named: tuple[str, ...] = ()
    if isinstance(definition_filters, Mapping):
        raw = definition_filters.get("slicers")
        if isinstance(raw, (list, tuple)):
            named = tuple(n for n in raw if isinstance(n, str) and n in visible)
    if named:
        return named
    return tuple(entry["name"] for entry in entries if entry["visible"])


def validate_grouping(
    dataset_code: str,
    group_by: Sequence[str] = (),
    filters: Iterable[str] = (),
) -> None:
    """Refuse a grouping this dataset will not serve, at SAVE, naming it."""
    dataset = datasets.BY_CODE.get(dataset_code)
    if dataset is None:
        raise GroupingRefused(f"no dataset named {dataset_code!r}")
    if len(tuple(group_by)) > MAX_GROUP_LEVELS:
        raise GroupingRefused(
            f"{dataset_code}: a report groups to at most {MAX_GROUP_LEVELS} levels — "
            f"{len(tuple(group_by))} were given ({', '.join(group_by)})"
        )
    seen: set[str] = set()
    for level in group_by:
        if level in seen:
            raise GroupingRefused(
                f"{dataset_code}: {level!r} is grouped twice — the second level "
                "would hold one value and subtotal itself"
            )
        seen.add(level)
        if not _groupable(dataset, level):
            raise GroupingRefused(
                f"{dataset_code}: nothing to group by {level!r} — this dataset "
                f"declares {', '.join(dataset.dimension_names())}"
            )
    assert_one_calendar(dataset_code, group_by, filters)


def is_group_level(dataset_code: str, level: str) -> bool:
    """STRUCTURAL: is this a dimension of the dataset, or a level of one?

    ⚠ **NOT THE SAME QUESTION AS `groupable_on`, AND CONFUSING THE TWO COSTS A
    REFUSAL IN THE WRONG PLACE.** This one asks whether the NAME is part of the
    model — what `validate()` needs at save, with no rows in hand.
    `groupable_on` asks whether the ROWS SERVED carry a column for it, which is
    `DEF-REP-6847`'s question and can only be asked at render. A save-time
    check that used the data question would refuse `cycle` on `invoices` as an
    unknown dimension — which it is not — and the calendar refusal that should
    have spoken would never be reached.
    """
    dataset = datasets.BY_CODE.get(dataset_code)
    return False if dataset is None else _groupable(dataset, level)


def _groupable(dataset: datasets.Dataset, level: str) -> bool:
    """A level is groupable when it is a dimension, or a LEVEL of one."""
    if level in dataset.dimension_names():
        return True
    for dim in dataset.dimensions:
        if level in levels_for(dataset.code, dim.name):
            return True
    return False


def _dimension_of(dataset: datasets.Dataset, level: str) -> str:
    """The dimension a level belongs to — `accounting_period` → `time`."""
    if level in dataset.dimension_names():
        return level
    for dim in dataset.dimensions:
        if level in levels_for(dataset.code, dim.name):
            return dim.name
    return level


# ── What a sum SPANS (the additivity question) ──────────────────────────────
def subtotal_across(dataset_code: str, group_by: Sequence[str], level_index: int) -> tuple[str, ...]:
    """What a subtotal at `level_index` spans: the grouped dimensions BELOW it.

    A month's subtotal holds `time` fixed and spans everything grouped inside
    it. See the docstring — this is why grouping AR Ageing by month still
    shows each month's balance as a number while the footer refuses.
    """
    dataset = datasets.BY_CODE.get(dataset_code)
    if dataset is None:
        return ()
    return tuple(
        _dimension_of(dataset, level) for level in tuple(group_by)[level_index + 1 :]
    )


def footer_across(
    dataset_code: str,
    group_by: Sequence[str] = (),
    filters: Mapping[str, Any] | None = None,
    window: Mapping[str, Any] | None = None,
) -> tuple[str, ...]:
    """What the GRAND total spans — the thing `P2.22`'s footer asks about.

    Three sources, and each is a measured case rather than a precaution:

      1. **Every grouped dimension.** A report grouped by month has a footer
         that spans months, which is §7.2.2's first trap exactly.
      2. **`service`, unless a filter pins it to one.** An ungrouped meter-read
         listing across eleven services has a consumption footer adding gallons
         to kilowatt-hours — hard rule 3 — and no grouping is involved, so (1)
         alone would miss it. `invoices_dataset` already works around this by
         omitting its `usage` total entirely, with a comment saying the footer
         *"shows an em-dash and the reason for a measure it may not sum"*. This
         is that footer.
      3. **`time`, when the report covers a RANGE rather than an instant.** An
         as-at ageing (`as_of`) spans no time and its balance total is lawful —
         which is the ungrouped half of the pair the PO asked to see. A `from`/
         `to` report spans time and a balance total over it does not mean
         anything.

    ⚠ **(3) IS ASKED OF THE `window` THE REPORT SERVED, WHEN THE CALLER HAS
    ONE — NOT OF THE REQUEST (`DEF-REP-9150`, 2026-10-02).** This read only the
    request, and `ar_aging` reads only `to` and answers
    `window={"as_of": …}` whatever bounds it was given. The Finance Aging
    view, its CSV download and the report viewer after any filter all send
    `from`+`to`, so every band total and the grand total of a report that
    describes ONE date came back as *"Balances do not sum across time"* —
    `$340.20` over 8 accounts at `as_of=2026-10-31`, five em-dashes and a
    reason for the identical figures under `from=2026-10-01&to=2026-10-31`.
    **The served window is the fact; the request is only what was asked.** It
    can only take `time` AWAY — a served instant (`as_of`, or `start == end`)
    spans nothing — and never adds it, so a report that serves a real range
    over a balance (`journal_lines`' running `balance`) still refuses exactly
    as before. The save-time check (`runner.validate`) has no served window
    and still reads the request; see `_spans_time`.
    """
    dataset = datasets.BY_CODE.get(dataset_code)
    if dataset is None:
        return ()
    params = {str(k): v for k, v in (filters or {}).items()}
    bare = {k[2:] if k.startswith("f.") else k: v for k, v in params.items()}

    across = {_dimension_of(dataset, level) for level in group_by}
    if not _pinned(bare, "service"):
        across.add(datasets.DIM_SERVICE)
    if _spans_time(bare, window):
        across.add(datasets.DIM_TIME)
    return tuple(sorted(across))


def _pinned(filters: Mapping[str, Any], name: str) -> bool:
    """True when a filter names exactly ONE value of this dimension.

    A list of two services is not pinned — two services added together is the
    same wrong number as eleven.
    """
    value = filters.get(name)
    if value is None or value == "":
        return False
    if isinstance(value, (list, tuple, set)):
        return len(value) == 1
    return "," not in str(value)


def _spans_time(filters: Mapping[str, Any], window: Mapping[str, Any] | None = None) -> bool:
    """A range spans time; an `as_of` instant does not.

    `window` is what the report SERVED (`_report`'s `window` key) and, when it
    describes one date, it wins over the request — `DEF-REP-9150`. Two shapes
    are an instant: `{"as_of": …}` (ar_aging, accounts, assets, access_review)
    and `{"start": d, "end": d}` (plans_and_discounts serves its as-at date
    that way). A served RANGE defers to the request, so this can only ever
    REMOVE `time` from a footer's span, never add it.
    """
    if _served_instant(window):
        return False
    if filters.get("as_of"):
        return False
    return bool(filters.get("from") or filters.get("to") or filters.get("period"))


def _served_instant(window: Mapping[str, Any] | None) -> bool:
    """True when the served window describes ONE date rather than a span."""
    if not isinstance(window, Mapping):
        return False
    start, end = window.get("start"), window.get("end")
    if start is None and end is None:
        return "as_of" in window
    return start is not None and start == end


# ── The group rows (P2.17's subtotals · what P2.18 and P2.24 render) ────────
class GroupingNeedsSql(GroupingRefused):
    """This grouping cannot be served without a `GROUP BY`, so it is not served.

    ⚠ **THE ALTERNATIVE WAS MEASURED AND IT IS A WRONG NUMBER ON A SCREEN
    (`DEF-REP-6875`, 2026-09-27).** Adding the SERVED rows up in Python adds up
    **one page**. On this branch the billing register grouped by status served
    `$14,048.10 + $137.70 = $14,185.80` of subtotals under a footer of
    `$30,750.07` over 92 bills, with nothing anywhere saying the groups covered
    fifty of them. Two figures on one screen that do not foot, and no reader
    could tell which was wrong.

    So a page-scoped roll-up is refused BY NAME rather than served. A clerk sees
    the report with its grouping dropped and a reason; they never see a subtotal
    that means half of what it says.
    """


def group_rows(
    dataset_code: str,
    rows: Sequence[Mapping[str, Any]],
    group_by: Sequence[str],
    *,
    measures: Sequence[str] | None = None,
    groups: Sequence[Mapping[str, Any]] | None = None,
    whole_set: bool = True,
) -> list[dict[str, Any]]:
    """Fact rows with a SUBTOTAL row inserted at every level. Flat, in order.

    Flat rather than nested because the table renders rows and `P2.24` opens
    and closes a level IN PLACE — a nested payload would make "collapse" a
    different shape from "expand" and the screen would hold two.

    Every group row carries:

      `path`      the dimension/value pairs that identify it — which is
                  `P2.18`'s drill-through, pre-applied as filters. *"A $48,221.14
                  subtotal opens the 412 rows that make it."* The path IS the
                  filter set, so the rows behind a subtotal cannot be a
                  different query from the one that produced it.
      `rows`      how many facts it covers — the 412.
      `subtotals` its measures, each through `additivity` with the correct
                  `across` for a SUBTOTAL, so an unlawful one is an em-dash
                  here exactly as in the footer.
    """
    dataset = datasets.BY_CODE.get(dataset_code)
    levels = tuple(group_by)[:MAX_GROUP_LEVELS]
    if dataset is None or not levels:
        return [dict(row) for row in rows]

    # ── THE SQL PATH — a group row is a `GROUP BY` cell (`P2.17`) ────────────
    if groups:
        return _from_sql(dataset_code, groups, levels)

    # ⚠ **NO `GROUP BY` AND THE PAGE IS NOT THE WHOLE SET ⇒ REFUSED BY NAME.**
    # See `GroupingNeedsSql`. This is the ONLY condition under which the Python
    # roll-up below is arithmetically the same answer a database would give: the
    # rows in hand ARE the filtered set, so their Σ is the set's Σ.
    if not whole_set:
        raise GroupingNeedsSql(
            f"{dataset_code}: grouping by {', '.join(levels)} needs a GROUP BY and this "
            "query serves none. The rows in hand are one page, so a subtotal struck over "
            "them would cover the page and be read as covering the report — the footer and "
            "the subtotals would not foot and nothing would say why."
        )

    # ⚠ **A LEVEL NO ROW CARRIES IS NOT GROUPED, AND THIS IS A MONEY GUARD
    # RATHER THAN A TIDINESS ONE (`DEF-REP-6847`).** `row.get(level)` returns
    # `None` for every row when the column is absent, so the obvious
    # implementation puts ALL the rows in ONE group keyed `None` and gives it a
    # subtotal — a figure that equals the grand total, is labelled with a blank,
    # and looks exactly like a correct group. Measured, 57 of 71 declared
    # dimensions have no column on their own dataset, so that is the COMMON
    # case here and not an edge one.
    keys = tuple(_row_key(dataset_code, level, rows) for level in levels)
    if any(key is None for key in keys):
        return [dict(row) for row in rows]

    names = tuple(measures) if measures is not None else tuple(m.name for m in dataset.measures)
    out: list[dict[str, Any]] = []
    _emit(dataset_code, list(rows), levels, keys, names, 0, [], out)
    return out


def groupable_on(dataset_code: str, level: str, rows: Sequence[Mapping[str, Any]] = ()) -> bool:
    """Whether this level can actually be grouped on the rows served."""
    return _row_key(dataset_code, level, rows) is not None


def _row_key(
    dataset_code: str, level: str, rows: Sequence[Mapping[str, Any]] = ()
) -> str | None:
    """The key in a served row that holds this level's value, or None.

    Three sources, narrowest first: the level name itself, the reviewed
    dimension→column table, and — last — a key the ROWS actually carry, which
    covers a dataset query serving a column its declaration does not list.
    """
    if rows and level in rows[0]:
        return level
    mapped = column_for(dataset_code, _dimension_of_code(dataset_code, level))
    if mapped is not None and (not rows or mapped in rows[0]):
        return mapped
    if rows:
        for candidate in _DIMENSION_COLUMN.get(
            _dimension_of_code(dataset_code, level), ()
        ):
            if candidate in rows[0]:
                return candidate
    return None


#: The reason a group row carries no drill-through, keyed
#: `reports.drill.<code>` in all eleven catalogues. ONE key: the clerk needs to
#: know the control is absent, and WHY is rationale — B14 rule 33 puts that at
#: zero words on screen.
DRILL_UNAVAILABLE = "drill_through_filter_is_not_declared"


def drill_filters(
    dataset_code: str,
    path: Sequence[Mapping[str, Any]],
    member: Mapping[str, Any],
) -> dict[str, Any] | None:
    """The filters that reproduce EXACTLY this group's rows, or `None`.

    ⚠ **THIS EXISTS BECAUSE THE `path` IS NOT A FILTER SET, AND
    `group_rows()`'s OWN DOCSTRING SAID IT WAS (`DEF-REP-6869`, hard-won law
    1).** It claimed *"The path IS the filter set, so the rows behind a subtotal
    cannot be a different query from the one that produced it"*. Measured on
    real PostgreSQL 16 against the seeded demo tenant, it is wrong three
    separate ways and each is enough on its own:

      1. the path's `dimension` is `consumer_class`; the `payments` dataset
         declares the FILTER as `class`;
      2. the path's `value` is the DISPLAY label `Residential`; the filter's
         vocabulary is the CODE `residential`, which the row carries in a
         SIBLING column `account_class_code`;
      3. the path's `column` names the display column, not the code column.

    `runner.run("ar_aging", {"group_by": "consumer_class"})` groups 30 rows;
    replaying its path verbatim — `{"class": "Residential"}` — returns **0
    rows**, and `{"class": "residential"}` returns **30**. A subtotal opening
    onto nothing, under a chip naming the group, is precisely the failure
    `P2.18` exists to prevent: *"a number a clerk cannot check is one they will
    not defend to a customer."*

    ⚠ **`None` RATHER THAN A BEST GUESS, AND THAT IS THE LOAD-BEARING HALF.**
    A drill-through built on a filter this dataset does not declare is a
    control that runs and answers the wrong question — worse than an absent
    one, because the clerk cannot tell. `runner.bind` DROPS an undeclared
    parameter silently, so such a control would open the UNFILTERED report
    showing every row under a chip naming one group. When any level of the path
    cannot be expressed, the whole set is `None`, the screen draws no
    drill-through, and `DRILL_UNAVAILABLE` says so in six words.

    ⚠ **IT IS DERIVED, NEVER A SEVENTH HAND-TYPED MAP** (`P0.7`). The filter
    NAME comes from `dataset.filters` and the reviewed dimension→column table
    the grouping itself already uses; the VALUE comes from the member row's own
    code column. A per-report table of drill filters is the thing this module
    was written to stop existing.
    """
    dataset = datasets.BY_CODE.get(dataset_code)
    if dataset is None:
        return None
    declared = set(dataset.filters)
    out: dict[str, Any] = {}
    for step in path:
        dimension = str(step.get("dimension") or "")
        column = str(step.get("column") or "")
        name = _filter_name_for(dimension, column, declared)
        if name is None:
            return None
        value = _filter_value_for(column, member)
        if value is None:
            return None
        out[name] = value
    return out


def _filter_name_for(dimension: str, column: str, declared: set[str]) -> str | None:
    """The DECLARED filter that selects this dimension, narrowest first.

    The candidates are the dimension's own name, the column the grouping used,
    and the reviewed dimension→column aliases — the same list `_row_key` walks
    in the other direction, so the name a group is BUILT on and the name it is
    REPLAYED through come from one table and cannot drift apart.
    """
    for candidate in (dimension, column, *_DIMENSION_COLUMN.get(dimension, ())):
        if candidate and candidate in declared:
            return candidate
        # `class_code` declared as `class`, `service_code` as `service`.
        trimmed = candidate[: -len("_code")] if candidate.endswith("_code") else ""
        if trimmed and trimmed in declared:
            return trimmed
    return None


def _filter_value_for(column: str, member: Mapping[str, Any]) -> Any:
    """The value in the FILTER's vocabulary, read off a member row.

    ⚠ **A CODE WHERE THE ROW CARRIES ONE, AND THIS IS THE THIRD MISMATCH.** The
    ageing serves `account_class` (`Residential`, for reading) beside
    `account_class_code` (`residential`, for querying); the group is keyed on
    the first and the filter takes the second. A drill-through built on the
    display label matches nothing — measured, 0 rows of 30.

    A row carrying no `_code` sibling is one whose display value IS its code
    (`bucket`, `on_plan`, `status`), so the column itself is used. `None` is
    returned only when the member row has no such key at all, which makes the
    whole drill-through unavailable rather than wrong.
    """
    coded = f"{column}_code"
    if coded in member and member[coded] not in (None, ""):
        return member[coded]
    if column in member:
        return member[column]
    return None


def _dimension_of_code(dataset_code: str, level: str) -> str:
    dataset = datasets.BY_CODE.get(dataset_code)
    return level if dataset is None else _dimension_of(dataset, level)


def _from_sql(
    dataset_code: str,
    groups: Sequence[Mapping[str, Any]],
    levels: tuple[str, ...],
) -> list[dict[str, Any]]:
    """`GROUP BY` cells → group rows, in tree order, COLLAPSED.

    ⚠ **COLLAPSED, AND THAT IS THE HONEST SHAPE RATHER THAN A MISSING FEATURE.**
    Each cell's Σ and `rows` count cover the WHOLE filtered set; the fact rows the
    query also served are ONE PAGE of it. Interleaving them would put fifty facts
    under a group that says it holds 412, which is `DEF-REP-6875` in a nicer
    costume. So a grouped answer is the group rows, and each one carries the
    FILTERS that reopen exactly the rows its subtotal was struck over.

    ⚠ **`path` IS NOT THOSE FILTERS**, which `DEF-REP-6869` measured on the
    Python path the same day: `_emit`'s path carries the DIMENSION's name where
    the dataset declares a FILTER's, and the DISPLAY label where the filter's
    vocabulary is a code, so feeding it back returns zero rows. `drill_filters()`
    is that fix and this is its counterpart for a `GROUP BY` cell.

    ⚠ **A SEPARATE FUNCTION, AND NOT BECAUSE THE PROBLEM IS DIFFERENT.**
    `drill_filters()` reads the VALUE off a member row — the `_code` sibling
    column beside the display column — and a `GROUP BY` cell **has no member
    row**: the groups cover the whole filtered set and the facts in hand are one
    page of it, so the row a value would be read from may not have been fetched.
    `sql_drill_filters()` takes the value the DATABASE grouped on instead, which
    is already the code (`service__code`), and adds the one case the row-based
    derivation cannot do at all: a `Trunc` cell is a point in time and the filter
    that reproduces it is a `from`/`to` WINDOW, computed from the truncation
    rather than re-read off any row.

    **The filter NAME comes from `_filter_name_for`, which is `drill_filters`'s
    own helper**, so the name a group is built on and the name it is replayed
    through still come from one table. `None` — never `{}` — where a level cannot
    be expressed, for the reason that function already records.

    ⚠ **THE VALUE IS THE DATABASE's, NEVER RE-DERIVED.** A `Trunc` comes back as a
    `date`/`datetime`; it is stringified for the wire and NOT reformatted into a
    month name here, because a label is a screen's decision and two places
    formatting one value is how a group row and its drill-through come to disagree.

    Order is the cells' own — `_grouped` applies `ORDER BY` — for the reason
    `_emit` records: re-sorting here would overrule the clerk's caret.
    """
    children: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for cell in groups:
        values = tuple(cell.get("values") or ())
        if not values or len(values) > len(levels):
            continue
        children.setdefault(values[:-1], []).append(cell)

    out: list[dict[str, Any]] = []

    def walk(parent: tuple[Any, ...], path: list[dict[str, Any]]) -> None:
        for cell in children.get(parent, ()):
            values = tuple(cell.get("values") or ())
            index = len(values) - 1
            level = levels[index]
            value = values[-1]
            here = path + [
                {"dimension": level, "column": level, "value": _wire(value)}
            ]
            out.append(
                {
                    "__kind__": "group",
                    "level": index,
                    "dimension": level,
                    "value": _wire(value),
                    "path": [dict(step) for step in here],
                    # `P2.24`/`P2.18`'s door, and the thing `path` is not.
                    "filters": sql_drill_filters(dataset_code, here),
                    "rows": int(cell.get("rows") or 0),
                    "subtotals": additivity.footer(
                        dataset_code,
                        {
                            name: _wire(figure)
                            for name, figure in (cell.get("measures") or {}).items()
                        },
                        subtotal_across(dataset_code, levels, index),
                    ),
                }
            )
            walk(values, here)

    walk((), [])
    return out


#: How wide one time level is, as a number of MONTHS, so a group's window is
#: arithmetic on the truncation the database already returned rather than a second
#: interpretation of the clerk's date. `day` is its own case below.
_LEVEL_MONTHS: dict[str, int] = {"year": 12, "quarter": 3, "accounting_period": 1}


def sql_drill_filters(
    dataset_code: str, path: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    """The filters that reopen EXACTLY the rows a `GROUP BY` cell's subtotal covers.

    `None` — never `{}` — when any step of the path cannot be turned into a filter
    this dataset accepts. An empty dict applied as filters returns the WHOLE
    report under a chip naming one group, which is `DEF-REP-6869`'s measured
    failure with better manners; `None` is something a drill-through can refuse on.

    ⚠ **A TIME LEVEL BECOMES `from`/`to` AND NOT `period`.** The database returned
    the START of the truncated window, so the window is that date plus the level's
    own width, minus a day, and both ends are INCLUSIVE because that is what
    `from`/`to` mean everywhere else in this module. Deriving it from the clerk's
    original filter instead would be a second interpretation of the same fact, and
    the two would disagree on the month a report's window starts mid-month.

    ⚠ **THE NARROWEST TIME LEVEL WINS.** Grouped by `year`, then `quarter`, then
    `accounting_period`, the innermost group is one month inside one quarter inside
    one year; writing all three windows would be three pairs of `from`/`to` and the
    last would silently win anyway. Written once, from the last time step, so what
    the caller sends is what this function decided.
    """
    from datetime import date as _date

    from core.partitioning import add_months

    dataset = datasets.BY_CODE.get(dataset_code)
    if dataset is None:
        return None
    declared = set(dataset.filters)
    out: dict[str, Any] = {}
    for step in path:
        level = str(step.get("dimension"))
        value = step.get("value")
        if value is None:
            # A `GROUP BY` cell keyed NULL is *"no service on this line"*, and
            # there is no filter that expresses it — `service=` means unset.
            return None
        if level in _LEVEL_MONTHS or level == "day":
            if "from" not in dataset.filters or "to" not in dataset.filters:
                return None
            try:
                start = _date.fromisoformat(str(value))
            except ValueError:
                return None
            end = (
                start
                if level == "day"
                else add_months(start, _LEVEL_MONTHS[level]) - timedelta(days=1)
            )
            out["from"] = start.isoformat()
            out["to"] = end.isoformat()
            continue
        # ⚠ **`drill_filters`'s OWN RESOLVER, NOT A SECOND ONE.** A duplicate
        # here is how the name a group is BUILT on and the name it is REPLAYED
        # through come to disagree, which is `DEF-REP-6869` with two tables
        # instead of none.
        name = _filter_name_for(level, str(step.get("column") or level), declared)
        if name is None:
            return None
        out[name] = value
    return out or None


def _wire(value: Any) -> Any:
    """A database value in the shape the rest of this product puts on the wire.

    `Decimal` → its EXACT string, never a float and never rounded: hard rule 2
    stores money to 4 decimals and rounds at display, and this is neither place.
    A `date`/`datetime` → ISO, because a `Trunc` cell is a point in time and
    `str(datetime)` is not a wire format. Everything else travels as it came.
    """
    from datetime import date as _date, datetime as _datetime
    from decimal import Decimal as _Decimal

    if isinstance(value, _Decimal):
        return str(value)
    if isinstance(value, _datetime):
        return value.date().isoformat()
    if isinstance(value, _date):
        return value.isoformat()
    return value


def _emit(
    dataset_code: str,
    rows: list[Mapping[str, Any]],
    levels: tuple[str, ...],
    keys: tuple[Any, ...],
    names: tuple[str, ...],
    index: int,
    path: list[dict[str, Any]],
    out: list[dict[str, Any]],
) -> None:
    if index >= len(levels):
        out.extend(dict(row) for row in rows)
        return
    level = levels[index]
    key = keys[index]
    # ⚠ **ORDER IS THE ROWS' OWN, NOT `sorted()`.** The read path sorts in SQL
    # (`P2.2`) and re-sorting here would quietly overrule the clerk's caret —
    # hard-won law 2's mirror, a live control with something downstream
    # ignoring it. Groups appear in the order their first row does.
    buckets: dict[Any, list[Mapping[str, Any]]] = {}
    for row in rows:
        buckets.setdefault(row.get(key), []).append(row)
    for value, members in buckets.items():
        here = path + [{"dimension": level, "column": key, "value": value}]
        # ⚠ **THE FILTERS ARE DERIVED FROM A MEMBER ROW, NOT FROM THE PATH**
        # (`DEF-REP-6869`). See `drill_filters` — the path is the grouping key
        # and carries display values on display columns; the filter set is the
        # dataset's declared filter names carrying code values. `None` here
        # means the screen draws no drill-through at all, which is the only
        # safe answer: `runner.bind` drops an undeclared parameter silently, so
        # a guessed filter would open the WHOLE report under a chip naming one
        # group.
        drill = drill_filters(dataset_code, here, members[0]) if members else None
        out.append(
            {
                "__kind__": "group",
                "level": index,
                "dimension": level,
                "value": value,
                "path": [dict(step) for step in here],
                "filters": drill,
                "drill_unavailable": None if drill else DRILL_UNAVAILABLE,
                "rows": len(members),
                "subtotals": additivity.footer(
                    dataset_code,
                    _sum(members, names),
                    subtotal_across(dataset_code, levels, index),
                ),
            }
        )
        _emit(dataset_code, members, levels, keys, names, index + 1, here, out)


def _sum(rows: Sequence[Mapping[str, Any]], names: Sequence[str]) -> dict[str, Any]:
    """Add each named measure over these rows, in `Decimal`, never a float.

    CLAUDE.md hard rule 2: money is stored to 4 decimals and is NEVER a float.
    A subtotal built with `+` over `float(cell)` would be off in the fourth
    place on a few thousand rows and would tie out to nothing.
    """
    from decimal import Decimal, InvalidOperation

    served: dict[str, Any] = {}
    for name in names:
        running = Decimal("0")
        seen = False
        for row in rows:
            raw = row.get(name)
            if raw is None or raw == "":
                continue
            try:
                running += Decimal(str(raw))
            except (InvalidOperation, ValueError, TypeError):
                # A non-numeric cell under a measure name is a dataset bug, not
                # a rounding question; the subtotal says nothing rather than
                # guessing, and `unavailable` is where a reason belongs.
                seen = False
                break
            seen = True
        if seen:
            served[name] = str(running)
    return served


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.17 · P2.25 · P2.26 (05-prototype/09 Reports Build Brief.pdf p12, p13, p83, p84, p85 read as images per B14 rule 42)
# screens: 2·1 slicer bar · 2·1 group rows · 2·2 group slots
# generated: 2026-09-27 by lane REP-P2-MODEL; amended 2026-09-27 by lane REP-UNBLOCK (DEF-REP-6875 — a group row comes from a SQL GROUP BY, and a Python roll-up is refused BY NAME unless the page holds the whole filtered set; `filters` beside `path`, because `path` applied verbatim opens zero rows — DEF-REP-6869)
# checklist: A✔ B✔ C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_rep_p2_17_slicers.py and tests/test_rep_p2_25_calendar.py were shown red before this file existed. The 2026-09-27 amendment was proved red THROUGH PYTEST by turning `if not whole_set:` into `if False:`: tests/test_rep_unblock_grouping.py then reported `assert 'grouping_needs_a_grouped_query' in ['grouping_not_served']` and `DID NOT RAISE GroupingNeedsSql`, 2 failed 14 passed, and went 16 passed when restored
# exceptions: (1) time levels come from `dataset.time_hierarchy` and NOT from `D_TIME.hierarchy`, which disagrees with the declared calendar on all nine datasets — DEF-REP-6846 · (2) MAX_GROUP_LEVELS is a drawn control count and not an NFR-5 cap; reasoning in the docstring · (3) a SUBTOTAL and a FOOTER ask additivity different questions and have two functions for it
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING (money rounding — subtotals are Decimal, 🔒)
# ──────────────────────────────────────────────────────────
