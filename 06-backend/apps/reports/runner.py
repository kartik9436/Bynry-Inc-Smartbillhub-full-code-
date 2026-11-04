# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 0 · P0.5 (the runner — ONE path from a
#           definition to rows).  Screens: none in Phase 0.
# Rules:    BR-REP-002 (every card opens a READ-MODEL) · BR-REP-001 (a money
#           report names its date basis) · CLAUDE.md hard rule 1 (a dataset is
#           a REVIEWED query; a definition names columns, never SQL) ·
#           hard rule 3 (a quantity carries its unit) · NFR-3 (universal server
#           pagination — and the three datasets that do not accept it yet say
#           so in a field rather than in a paragraph)
# Tests:    06-backend/tests/test_rep_p0_schema_spine.py
# Impacts:  apps/reports/exports.py (its `_rows_for` now calls `rows_for`) ·
#           apps/reports/api.py (the viewer calls `run`) · apps/reports/queries.py
# ───────────────────────────────────────────────────────
"""ONE PATH from a definition to rows: resolve → bind → execute → shape.

WHAT WAS WRONG, MEASURED
────────────────────────
The viewer and the export reach the same numbers by two different routes
today. `apps/reports/api.py` calls `queries.VIEWERS[key](request.query_params)`;
`apps/reports/exports.py:94` calls `queries.VIEWERS[key](filters)` with its own
`per="all"` and its own defaults. Two call sites, two sets of defaults, and the
only thing keeping the file and the screen in agreement is that somebody
remembered. `P0.5`'s outcome is the test that stops relying on memory: **a
report rendered on screen and the same report exported produce byte-identical
rows.**

⚠ AND THE EXPORT RUNS THE REPORT TWICE, WHICH THIS FILE DOES NOT FIX
─────────────────────────────────────────────────────────────────────
`apps/tenancy/services.py:6259` calls `resource.select(params)` to COUNT the
selection, refuses over `EXPORT_ROW_CAP`, and then the job body builds the same
selection again to write it. On a 40,000-row ageing report at T5 that is the
whole cost, doubled, for a number the clerk does not need before the file
exists.

**The second execution exists only to enforce the cap, so it goes when the cap
goes — and the cap goes in `P2.4`**, which is a one-line deletion rather than a
rewrite because the writer at `exports.py:546` already streams row by row from
a generator. `NFR-5` forbids reinstating it anywhere, including on a Settings
screen. Putting a cache in here instead would be a second mechanism for a
problem with a scheduled deletion, and a cache spanning a count in one process
and a job body in another would be a cache that is wrong rather than fast.
**Named here so the next reader does not "fix" it twice.**

WHAT RESOLVES, TODAY AND AFTER PHASE 1
──────────────────────────────────────
`resolve()` reads `report_definitions` — the tenant's own row first, then the
platform row it was copied from. There is no fallback to a Python literal and
deliberately none: `reports/0003` seeds all forty-six platform rows, and every
key this runner serves is among them, so a fallback would be code nothing can
reach. In Phase 0 the table holds those 46 and **nothing is switched over to
serve them as a CATALOGUE** — `GET /reports`
still renders `apps/reports/catalog.py`'s tuple, and `P1.1` owns the switch
together with the catalogue screen that labels the result. What DOES read the
table today is this runner, on every one of the four reports the product can
actually produce.

WHAT "EXECUTE" MEANS WHILE FIVE OF THE NINE DATASETS HAVE NO QUERY
─────────────────────────────────────────────────────────────────
**EIGHT** reports are built (`queries.VIEWERS`) — the four US-REP ones and the
four the `journal_lines` dataset turned on when its query was written
(2026-09-26, lane DS-LEDGER: trial balance, journal export, tax remittance,
close pack). ⚠ **THIS SENTENCE READ "Four … the other forty-two" AND WAS A
COUNT NOTHING RE-CHECKED**, which is this repository's most-filed rot. Count
`queries.VIEWERS`; never trust a number in a paragraph, including this one.
The rest are definitions whose dataset query is still to come.

A definition whose dataset cannot be executed
gets a NAMED refusal carrying the dataset code — never an empty result, which
is the hardest bug in this product to see, and never a 501, because a viewer
that opens onto a reason is a screen pretending to be a report (the posture
`apps/reports/catalog.py` already ships).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.reports import additivity, datasets, slicers


class DefinitionNotFound(LookupError):
    """No definition, platform or tenant, answers this key."""


class DatasetNotExecutable(NotImplementedError):
    """The definition resolves and its dataset has no query yet.

    Carries the dataset code so the refusal NAMES what is missing. A bare
    `NotImplementedError` would tell a reader that something is unbuilt and
    nothing about which of the nine it is.
    """

    def __init__(self, key: str, dataset_code: str) -> None:
        super().__init__(
            f"report {key!r} reads dataset {dataset_code!r}, which has no query yet "
            "(CR-142-BRC07 phase 2)"
        )
        self.key = key
        self.dataset_code = dataset_code


class UnknownParameter(ValueError):
    """A filter the dataset does not accept.

    ⚠ This is the wall the whole framework leans on, and it is why a clerk can
    be trusted with a report builder at all: a definition is USER INPUT and it
    names columns, never SQL. Everything that reaches a query has been checked
    against a declaration a pull request reviewed for tenant isolation, for
    money precision and for cost.
    """


@dataclass(frozen=True)
class ResolvedDefinition:
    """One definition, from the table or from the built-in set, in one shape."""

    key: str
    name: str
    dataset: str
    group_code: str
    sub_group_code: str | None
    columns: tuple[str, ...]
    filters: dict[str, Any]
    group_by: tuple[str, ...]
    sort: tuple[str, ...]
    service_codes: tuple[str, ...]
    #: True when this came out of `report_definitions`, False when it came from
    #: the built-in set. A caller never needs to care; a TEST does, because
    #: "is the table being read" is the whole of Phase 0's DONE WHEN.
    from_table: bool

    @property
    def basis(self) -> str | None:
        value = self.filters.get("basis")
        return value if isinstance(value, str) else None


def _from_row(row: Any) -> ResolvedDefinition:
    filters = dict(row.filters or {})
    return ResolvedDefinition(
        key=row.key,
        name=row.name,
        dataset=row.dataset,
        group_code=row.group_code,
        sub_group_code=row.sub_group_code,
        columns=tuple(row.columns or ()),
        filters=filters,
        group_by=tuple(row.group_by or ()),
        sort=tuple(row.sort or ()),
        service_codes=tuple(row.service_codes or ()),
        from_table=True,
    )


def canonical_key(key: str) -> str:
    """The key as STORED, for a key that may arrive in the viewer's spelling.

    ⚠ **`DEF-REP-10146` — TWO SPELLINGS OF ONE KEY.** A report a utility saves
    is keyed from its name with HYPHENS (`definitions._unique_key`:
    `overdue-60`), and the viewer maps every hyphen of its URL segment to an
    UNDERSCORE (`keyForSegment`, DEF-131's fix for our own keys). So a saved
    multi-word report asked for itself as `overdue_60` and was told it did not
    exist — every custom report a clerk named in more than one word.

    The exact key wins whenever ANY definition holds it, so every platform key
    and every key that already matched is answered exactly as before; only a
    miss is tried hyphenated. ⚠ **IT RUNS BEFORE THE ROLE GATE AND THE PRIVACY
    CHECK, NOT INSIDE `resolve`**, because both of those look the key up by
    its own spelling — a fallback buried in `resolve` would hand back a
    colleague's PRIVATE report through the underscore spelling while
    `resolve_for` found no row to refuse it on (BR-REP-019).
    """
    if "_" not in key:
        return key
    from django.db.models import Q

    from apps.reports.models import ReportDefinition
    from core import tenancy as core_tenancy

    # Named tenant as well as RLS — hard rule 1, and `resolve`'s own reason.
    visible = ReportDefinition.objects.filter(
        Q(tenant_id=core_tenancy.current_tenant_id()) | Q(tenant_id=None)
    )
    if visible.filter(key=key).exists():
        return key
    hyphenated = key.replace("_", "-")
    if visible.filter(key=hyphenated).exists():
        return hyphenated
    return key


def resolve(key: str) -> ResolvedDefinition:
    """The definition this key names — the tenant's own first, then platform.

    The ordering is copy-on-write made visible: a tenant that has copied a
    shipped report gets ITS row, and a tenant that has not gets ours. Both are
    visible to the session under `reports/0002`'s policy, so this is an
    ordering question and never a permission one.

    ⚠ THE `Q(tenant_id=...) | Q(tenant_id=None)` IS WRITTEN OUT EVEN THOUGH RLS
    ALREADY ENFORCES IT. CLAUDE.md hard rule 1 says never touch a tenant table
    without `app.tenant_id` set, and every other module in this product names
    its tenant in the queryset as well as relying on the policy. Leaning on RLS
    alone would also make this queryset return every tenant's rows on SQLite,
    where the policy does not exist — which is the test database, and which is
    hard-won law 14's exact shape: the broken version passes the whole suite,
    green, on every machine.
    """
    from django.db.models import Q

    from apps.reports.models import ReportDefinition
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    rows = list(
        ReportDefinition.objects.filter(
            Q(tenant_id=tenant_id) | Q(tenant_id=None), key=key
        )[:2]
    )
    if rows:
        # A tenant row (tenant_id set) outranks the platform row it copied.
        rows.sort(key=lambda row: row.tenant_id is None)
        return _from_row(rows[0])
    raise DefinitionNotFound(key)


def resolve_for(key: str, user_id: Any) -> ResolvedDefinition:
    """`resolve`, plus `BR-REP-019` — somebody else's PRIVATE report is absent.

    ⚠ **CLOSING THE LIST IS NOT CLOSING THE DOOR (`DEF-REP-6864`).** The
    catalogue stopped showing a colleague's private report on 2026-09-27; this
    is the other half, because a report has an ADDRESS and a link pasted into a
    chat is a way in that no list controls. A screen that hides a row and serves
    it at its URL has not implemented privacy, it has implemented tidiness.

    ⚠ **IT IS `DefinitionNotFound` AND NOT A REFUSAL, WHICH IS HR-1's POSTURE
    ONE BOUNDARY IN.** *"There is no report called this"* and *"there is one and
    it is not yours"* are different sentences, and only the first one is safe to
    say: the second confirms that a colleague has a report named *Board arrears
    pack*, which is the existence leak 404 exists to prevent.
    """
    definition = resolve(key)
    if not definition.from_table:
        return definition
    from apps.reports.models import ReportDefinition

    row = ReportDefinition.objects.filter(key=key).exclude(tenant_id=None).first()
    if row is None:
        return definition
    if row.visibility == "private" and str(row.owner_user_id or "") != str(user_id or ""):
        raise DefinitionNotFound(key)
    return definition


def _as_mapping(params: Any) -> dict[str, Any]:
    """A plain `{name: value}` from whatever the caller had.

    ⚠ **`dict(QueryDict)` DOES NOT DO THIS AND THE DIFFERENCE IS SILENT.** A
    Django `QueryDict` is multi-valued, so `dict(qd)` yields `{"from": ["2026-09-01"]}`
    — a LIST where every read model expects a string. `qd.get("from")` returns
    the last value, which is what `apps/reports/api.py` relied on before this
    runner existed by passing the `QueryDict` straight through. Losing that in
    the move to one path would have handed every date filter a one-element list
    and broken all four built reports, with `tsc`, the gates and this file's own
    structural assertions all still green.
    """
    if params is None:
        return {}
    flatten = getattr(params, "dict", None)
    if callable(flatten):  # QueryDict / MultiValueDict — last value per key
        return dict(flatten())
    return dict(params)


def bind(definition: ResolvedDefinition, params: Any) -> dict[str, Any]:
    """The definition's stored filters, overlaid with this run's parameters.

    ⚠ **A NAME THE DATASET DOES NOT DECLARE IS DROPPED HERE AND REFUSED IN
    `validate()`, AND THE SPLIT IS THE DOCUMENT'S, NOT A SOFTENING OF IT.**
    The brief puts the wall at SAVE: *"a definition is user input and names
    columns, never SQL — `P5.2` validates every name against the dataset's
    declaration"* (2·2's drawing, p32). At RUN it would be a different rule
    with a different victim: a clerk following a stale bookmark with one extra
    query parameter on it would get an error page instead of their report, and
    today's viewer simply ignores what it does not read. Raising here would be
    a user-visible behaviour change in a phase whose own brief says a clerk can
    newly do **nothing**.

    So `bind` drops, `validate` raises, and `dropped()` names what went — which
    is the part that matters, because a filter silently ignored with nothing
    recording it is a report answering a question nobody asked over a wider set
    than the clerk believes they are looking at.
    """
    dataset = datasets.BY_CODE.get(definition.dataset)
    if dataset is None:
        raise DatasetNotExecutable(definition.key, definition.dataset)

    bound: dict[str, Any] = {}
    inputs = declared_inputs(definition.key)
    # The stored filters are OURS and carry bookkeeping the dataset never sees
    # — the register number, the basis label, how the definition renders.
    for name, value in definition.filters.items():
        if name in dataset.filters or name in inputs:
            bound[name] = value
    for name, value in _as_mapping(params).items():
        if _passes(name, dataset, inputs):
            bound[name] = value
    return bound


#: The modules under `apps/reports` that OWN a report outright — each holds
#: its viewer and names it in its own `MODULE_VIEWERS` (and, where it has
#: them, `MODULE_STREAMS`, `MODULE_COLUMNS` and `MODULE_INPUTS`). One tuple
#: rather than one hand-written `or` per registry, so a report joining the
#: framework this way is one line here and every lookup below hears of it.
_OWNING_MODULES: tuple[str, ...] = ("statement", "rate_impact", "receivables_by_service", "owner_summary")


def _owned(registry: str) -> dict[str, Any]:
    """The union of one registry across the owning modules, first one wins."""
    from importlib import import_module

    merged: dict[str, Any] = {}
    for name in _OWNING_MODULES:
        module = import_module(f"apps.reports.{name}")
        for key, value in (getattr(module, registry, None) or {}).items():
            merged.setdefault(key, value)
    return merged


def owned_viewer(key: str) -> Any:
    """The MODULE viewer that owns this key, or None — `queries_for`'s first
    lookup, published so the catalogue's refusal check asks the same thing."""
    return _owned("MODULE_VIEWERS").get(key)


def declared_inputs(key: str) -> tuple[str, ...]:
    """The run parameters a viewer DECLARES for this key, or `()` — `CR-179-BRC10`.

    ⚠ **A FRAMEWORK MECHANISM AND NOT A RATE-IMPACT SPECIAL CASE.** A report
    whose question is not a dataset filter — a typed proposed rate, a table of
    rows, a choice of months — has nowhere to put it: `bind` passes only what
    the DATASET declares or what `_RUN_CONTROLS` names, and adding a report's
    own words to either would tell every OTHER report it honours them (the
    reasoning `_RUN_CONTROLS`' own comment gives for `subject`). So a viewer
    declares its inputs in `MODULE_INPUTS`, keyed by the report, and they pass
    `bind` FOR THAT REPORT ONLY. The viewer publishes the same names, drawn, as
    `controls.inputs`, and the screen renders whatever it is given.

    ⚠ **VALUES ARE PASSED AS GIVEN** — a JSON-encoded table stays one string
    through `bind`, an export's `dict[str, str]` filters and the run history,
    and the VIEWER validates every value it reads. It is not a hole in §8.1:
    the names are a reviewed declaration in this repository, and a name no
    declaration offers is still dropped.
    """
    return tuple(_owned("MODULE_INPUTS").get(key) or ())


#: ⚠ **THE `f.` PREFIX IS A LIVE WIRE AND DROPPING IT WOULD HAVE WIDENED A
#: SHIPPED SCREEN IN SILENCE.** The AR ageing screen sends its filters dotted —
#: `f.class`, `f.band`, `f.service`, `f.premises`, `f.purpose`, `f.bill_type`,
#: `f.period` — and `apps/reports/queries.py` reads BOTH spellings
#: (`params.get("class") or params.get("f.class")`). A runner that passed only
#: the bare names would have handed the query a request with every filter
#: missing: the report would render, the page would look right, and it would be
#: reporting the WHOLE receivable under a filter chip saying *Residential*.
#: Nothing on the screen and no test in this repo would have shown it.
#:
#: So the prefix is stripped before the name is checked against the dataset,
#: and the ORIGINAL key is what gets passed on — the queries read the dotted
#: form and this file does not get to rename anybody's wire.
_FILTER_PREFIX = "f."


def _passes(name: str, dataset: datasets.Dataset, inputs: tuple[str, ...] = ()) -> bool:
    if name in _RUN_CONTROLS or name in dataset.filters or name in inputs:
        return True
    if name.startswith(_FILTER_PREFIX):
        bare = name[len(_FILTER_PREFIX) :]
        return bare in dataset.filters or bare in inputs
    return False


def dropped(definition: ResolvedDefinition, params: Any) -> tuple[str, ...]:
    """The run parameters `bind` did not pass on, in the order given.

    Exists so *"which of my filters did this report ignore"* is a question with
    an answer rather than an inference from a row count.
    """
    dataset = datasets.BY_CODE.get(definition.dataset)
    if dataset is None:
        return tuple(_as_mapping(params))
    inputs = declared_inputs(definition.key)
    return tuple(name for name in _as_mapping(params) if not _passes(name, dataset, inputs))


def validate(definition: ResolvedDefinition) -> None:
    """Refuse a definition that names something its dataset does not produce.

    This is what `P5.2` calls when a clerk presses **Save as**, and it is the
    wall the whole framework leans on: everything a clerk can express has
    already been reviewed for tenant isolation, for money precision and for
    cost, because the only things they CAN express are names on a declaration a
    pull request approved. *"You cannot invent a column the dataset does not
    produce. That is the architecture, not an oversight."*

    It also refuses an UNLAWFUL TOTAL, which is `P0.16`'s own outcome: a
    definition that groups by month and totals a balance is refused here, at
    build time, naming the measure — rather than rendering a number that means
    nothing.
    """
    dataset = datasets.BY_CODE.get(definition.dataset)
    if dataset is None:
        raise DatasetNotExecutable(definition.key, definition.dataset)

    # ⚠ **`DEF-REP-7072` — A MODULE VIEWER'S OWN COLUMNS ARE NOT THE DATASET'S.**
    # Additive and nothing else: `viewer_only` is EMPTY for every report served
    # by a dataset query, so all forty-five of those are refused exactly as they
    # were, measures included. A report `MODULE_VIEWERS` owns serves names no
    # dataset declares, and refusing them here would make the editor's own
    # column list unsaveable — the offer and the honour coming from two lists
    # again, one function later.
    viewer_only = set(viewer_columns(definition.key))
    for name in definition.columns:
        if dataset.column(name) is None and name not in viewer_only:
            raise UnknownParameter(
                f"{definition.key}: {dataset.code} produces no column {name!r}"
            )
    # `CR-179-BRC10` — a viewer's DECLARED inputs are this report's own
    # vocabulary, so a saved copy may store them (`declared_inputs`).
    inputs = declared_inputs(definition.key)
    for name in definition.filters:
        if name in _DEFINITION_BOOKKEEPING or name in dataset.filters or name in inputs:
            continue
        raise UnknownParameter(
            f"{definition.key}: {dataset.code} does not accept {name!r} — it "
            f"accepts {', '.join(dataset.filters)}"
        )
    for name in definition.group_by:
        # ⚠ **A LEVEL COUNTS, NOT ONLY A DIMENSION NAME (`P2.17`).** This read
        # `name not in dataset.dimension_names()` until 2026-09-27, so *group
        # by cycle* — a level of `time` on the billing hierarchy, and the
        # thing `P2.25`'s own outcome row asks to be refused for a DIFFERENT
        # reason — was rejected here as an unknown dimension before the
        # calendar check could speak. `slicers` owns the question now, and it
        # answers for a dimension and for any level of one.
        if not slicers.is_group_level(dataset.code, name):
            raise UnknownParameter(
                f"{definition.key}: {dataset.code} declares no dimension {name!r} — "
                f"it declares {', '.join(dataset.dimension_names())}"
            )
    # ── P0.16 · the totals this definition actually asks for ───────────────
    # ⚠ **ONLY WHEN IT GROUPS, AND ONLY OVER THE COLUMNS IT NAMES.** The first
    # draft of this checked every column of the dataset whenever `columns` was
    # empty, and it refused all forty-six seeded rows — because a NON-additive
    # measure is unlawful to aggregate in any direction, and `dso_days` sits on
    # the `payments` dataset whether or not a given report totals it.
    #
    # That was the wrong question. A flat listing with no grouping aggregates
    # NOTHING: `AR Ageing` showing one row per account and no subtotal is not
    # summing a balance across anything. What P0.16 refuses is a definition
    # that GROUPS — *"group AR Ageing by month, total the column, and the
    # number means nothing"* — so the check fires on `group_by`, over the
    # columns the definition names.
    #
    # A definition with no `columns` means *"every column the dataset
    # declares"*, and when it also groups, every declared MEASURE is in scope:
    # the footer will total what the renderer is given.
    # ── P2.17 · P2.25 — the grouping itself, before anything is totalled ──
    # Three levels at most, every level a dimension or a level of one, and ONE
    # time hierarchy: *"a billing cycle does not sit inside a calendar month"*.
    # Refused HERE, at save, naming both sides — never at render, which would
    # be an error page over a report that is otherwise fine.
    slicers.validate_grouping(
        dataset.code, definition.group_by, tuple(definition.filters)
    )

    # ⚠ **THE LEVELS ARE MAPPED TO THEIR DIMENSIONS BEFORE ANYTHING IS ASKED,
    # AND THIS LINE READ `across = tuple(definition.group_by)` UNTIL 2026-09-27
    # (`DEF-REP-6862`).** `assert_summable` compares against DIMENSION names;
    # `P2.17` taught the check above that a group target may be a LEVEL of one —
    # `accounting_period`, `cycle`, `day` — and did not change this line. So
    # *group by `time`* was refused and *group by `accounting_period`*, which is
    # the only way a clerk would ever express **by month**, was not. `P0.16`'s
    # stated outcome is *"refused at BUILD time, naming the measure"* and it was
    # not true of any real grouping.
    #
    # It is `footer_across` and not a mapping written here, deliberately: that
    # is the function the RENDER path already uses (`_shaped`), so the answer a
    # save gets and the answer a footer gets now come from one place. Two
    # mappings is how they came to disagree in the first place — the footer
    # refused the total correctly while the save that produced it did not.
    across = slicers.footer_across(dataset.code, tuple(definition.group_by), dict(definition.filters))
    if definition.group_by:
        totalled = definition.columns or tuple(meas.name for meas in dataset.measures)
        for name in totalled:
            datasets.assert_summable(dataset.code, name, across)


#: Keys a definition's `filters` may carry that are OURS rather than the
#: dataset's — the register number it was drawn as, the label a clerk reads
#: beside the basis, whether it renders as a card or as a tab, and the subject
#: a four-grain report opens on.
_DEFINITION_BOOKKEEPING: frozenset[str] = frozenset(
    {"register", "basis", "basis_label", "renders_as", "subject", "subjects"}
)


#: Paging and ordering are the RUNNER's vocabulary, not a dataset's, so they
#: pass through `bind` without being declared nine times. `NFR-3` — and three
#: of the nine do not honour them in their owning module yet (`DEF-PAY-4221`,
#: `P2.12`), which each dataset declares as `paginates=False`.
_RUN_CONTROLS: frozenset[str] = frozenset(
    # `group_by` joined them with `P2.17`: three levels are a control a clerk
    # turns on 2·2, not a filter a dataset declares, so it passes through here
    # for the same reason paging and sorting do.
    #
    # ⚠ **`columns` JOINED THEM WITH `P5.3`, AND IT IS THE WHOLE OF THAT TASK'S
    # OUTCOME.** *"Adding a column shows it in the rows below without a save."*
    # The 2·2 panel is a PANEL and not a wizard precisely so a clerk can see the
    # rows change before committing (PO ruling 2026-09-26), and that is
    # impossible while the only column list the runner reads is the one already
    # stored. So the ticked set travels as a run control, exactly as `group_by`
    # does, and wins over the definition for THIS run only.
    #
    # ⚠ **IT IS NOT A HOLE IN §8.1.** Every name in it is checked against the
    # dataset's own declaration by `_requested_columns` below before anything is
    # shaped, and an unknown one is DROPPED rather than passed on — the
    # definition still *chooses from what a dataset offers*, which is the
    # property the whole architecture rests on. A clerk cannot name a column
    # here that they could not name at save.
    #
    # ⚠ **`subject` AND `subject_id` JOINED THEM FOR `BR-REP-038` (`DEF-REP-6908`),
    # AND WITHOUT THEM `P2.14`'s WHOLE VOCABULARY REACHED NO QUERY.** Measured on
    # real PostgreSQL before the fix:
    #
    #     runner.bind(account_ledger, {subject: premises, subject_id: abc, account: x})
    #       -> {'basis': 'posting'}
    #     runner.dropped(...)  -> ('subject', 'subject_id', 'account')
    #
    # `subject` and `subjects` are in `_DEFINITION_BOOKKEEPING`, which only lets
    # `validate()` ACCEPT them as STORED filters; `bind` passes a name on only
    # when the DATASET declares it or it is here. So the seeded subject survived
    # validation and was dropped on every run — a stored string nothing honours,
    # which is what `apps/reports/subject.py`'s own docstring warns about, one
    # layer further down than it was looking.
    #
    # They belong HERE rather than in a dataset's `filters` for the same reason
    # `page` and `sort` do: a subject is the RUNNER's vocabulary. It is declared
    # on the DEFINITION, it spans two definitions sitting on two different
    # datasets, and adding `subject` to `journal_lines.filters` would tell the
    # dataset query it honours something it does not — hard-won law 2's mirror
    # in a data structure, which that tuple's own comment was written about.
    {
        "page",
        "per",
        "limit",
        "offset",
        "sort",
        "dir",
        "q",
        "group_by",
        "columns",
        "subject",
        "subject_id",
    }
)


@dataclass(frozen=True)
class RunResult:
    """What one run produced. The SAME object the viewer renders and the export
    writes, which is the whole of `P0.5`."""

    key: str
    dataset: str
    grain: str
    basis: str | None
    payload: dict[str, Any]

    @property
    def rows(self) -> list[dict[str, Any]]:
        return list(self.payload.get("rows") or ())

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(self.payload.get("columns") or ())


def run(key: str, params: Any = None, *, whole: bool = False, as_user: Any = None) -> RunResult:
    """THE one path. Resolve → bind → execute → shape.

    `whole=True` is a FILE: the whole filtered set rather than one page. It is
    the only difference between what the screen shows and what the download
    holds, and it is a parameter of this one function rather than a second
    route into the query — which is what made the two disagree before.
    """
    # ⚠ `as_user` IS OPTIONAL AND ABSENT MEANS *no reader*, which resolves the
    # ordinary way. Every caller that is answering a PERSON passes it; the
    # export worker and the scheduler do not, because a job runs as the
    # definition's own owner and has already been authorised at the point it
    # was queued. Making it required would have moved nine call sites to fix
    # one, and `DEF-REP-6864`'s own lesson is that the read is what matters.
    definition = resolve_for(key, as_user) if as_user is not None else resolve(key)
    bound = bind(definition, params)
    if whole:
        # A file is the whole filtered set; a screen is one page of it.
        bound["per"] = "all"

    dataset = datasets.BY_CODE[definition.dataset]
    query = queries_for(definition.key, definition.dataset)
    if query is None:
        raise DatasetNotExecutable(definition.key, definition.dataset)
    # ⚠ **THE GROUPING IS RESOLVED BEFORE THE QUERY RUNS, AND THAT IS THE WHOLE
    # OF `DEF-REP-6855`.** `group_by` was bound, validated, additivity-checked
    # and echoed back into the payload, and **no query ever saw it** — measured
    # on real PostgreSQL 16 on 2026-09-27: 20 groupings over five reports, 20
    # returning rows byte-identical to the ungrouped run, zero group rows, and
    # `payload["group_by"]` claiming a grouping every time. A control that passes
    # every check and does nothing is hard-won law 2's mirror.
    #
    # A dataset query cuts the groups in SQL over the whole filtered set, so it
    # has to be TOLD, and it has to be told the same levels `_shaped` will then
    # shape — one resolution, here, rather than two that can disagree.
    grouping = _requested_grouping(definition, bound)
    if grouping:
        bound["group_by"] = list(grouping)
    payload = query(bound)
    if isinstance(payload, dict):
        payload = _shaped(payload, definition, dataset, bound)
        # ── `P5.3` · which DATASET this report is built on ─────────────────
        # ⚠ **THE PANEL CANNOT ASK A SCREEN WHAT IT IS EDITING.** 2·2 offers
        # the columns, measures, dimensions and filters the dataset declares,
        # and until this line the viewer had no way to know which of the nine
        # it was looking at — the answer carried the report's own columns and
        # nothing about where they came from. A screen that guessed the dataset
        # from the report key would be the seventh hand-typed map `P0.7`
        # deleted six of.
        if "dataset" not in payload:
            payload = dict(payload)
            payload["dataset"] = definition.dataset
        # ── `DEF-REP-7072` · WHAT THE EDITOR MAY ASK THIS REPORT FOR ───────
        # ⚠ **PUBLISHED ONLY WHERE IT DIFFERS FROM THE DATASET'S**, so the
        # forty-five dataset-backed reports carry no new key and the panel goes
        # on reading `GET /reports/datasets` for every one of them — byte for
        # byte what it served yesterday.
        #
        # ⚠ **AND IT IS THE SAME FUNCTION THE RUNNER HONOURS.** The editor
        # offered the DATASET's attributes and the runner honoured the DATASET's
        # attributes, and on a module viewer those are not this report's
        # columns: the statement's seven and `journal_lines`' five intersect in
        # `reference` alone, so ticking what the panel drew cut the table to one
        # column. Two lists, each correct about itself. `served_columns` is now
        # one list, and the offer cannot outrun the honour again.
        owned_columns = viewer_columns(definition.key)
        if owned_columns and "column_choices" not in payload:
            payload = dict(payload)
            payload["column_choices"] = list(owned_columns)
        # ── `DEF-REP-6867` · THE NAME A PERSON READS ──────────────────────
        # ⚠ **B14 RULE 31, AND THE VIEWER HAD NO OTHER ANSWER.** The page head
        # translated `reports.card.<key>.name` with the KEY as its default, so
        # a report a utility wrote was titled `overdue-60` — a slug on screen,
        # which is exactly what rule 31 forbids, and the only place the real
        # name lived was the row. A shipped report's name is still the
        # catalogue's, because ours are translated and a tenant's is not
        # (`DEF-REP-6817`); this is the row's own words for the rest.
        if "name" not in payload:
            payload = dict(payload)
            payload["name"] = definition.name
        # ── `DEF-REP-6863` (second occurrence) · WHERE IT LIVES ────────────
        # ⚠ **THE ROW KNOWS ITS OWN GROUP AND THE CATALOGUE READ DOES NOT
        # ALWAYS CARRY IT.** 2·2 seeded *Where it lives* from the catalogue
        # card, and `GET /reports` answers ONE sub-tab — Standard by default —
        # so a report a utility wrote had no card in hand and the panel opened
        # with an empty Group. The dialog then drew its first option while its
        # value was empty and refused the save, which is `DEF-REP-6863` exactly,
        # a second time, in the one case the first fix could not reach.
        #
        # Serving it here ends the class: the panel asks the REPORT where it
        # lives rather than hunting for it in a list that may not contain it.
        if "group" not in payload:
            payload = dict(payload)
            payload["group"] = definition.group_code
            payload["sub_group"] = definition.sub_group_code
    return RunResult(
        key=definition.key,
        dataset=definition.dataset,
        grain=dataset.grain,
        basis=payload.get("basis") if isinstance(payload, dict) else definition.basis,
        payload=payload if isinstance(payload, dict) else {},
    )


def _requested_grouping(
    definition: ResolvedDefinition, bound: dict[str, Any]
) -> tuple[str, ...]:
    """The levels THIS run groups by — the clerk's choice, else the stored one.

    A run parameter wins because `2·2`'s three group slots are a control the
    clerk turns; the definition's own `group_by` is the report as saved.
    """
    raw = bound.get("group_by")
    if isinstance(raw, str):
        chosen = tuple(part.strip() for part in raw.split(",") if part.strip())
    elif isinstance(raw, (list, tuple)):
        chosen = tuple(str(part) for part in raw)
    else:
        chosen = tuple(definition.group_by)
    return chosen[: slicers.MAX_GROUP_LEVELS]


def viewer_columns(key: str) -> tuple[str, ...]:
    """The columns a MODULE VIEWER declares for this key, or `()` — `DEF-REP-7072`.

    `()` for the forty-five reports a dataset query serves, which is what keeps
    every change built on this one additive: a caller asking *does a viewer own
    this report's column vocabulary* gets a falsy answer and the dataset's own
    rules apply untouched.
    """
    return tuple(_owned("MODULE_COLUMNS").get(key) or ())


def served_columns(key: str, dataset: datasets.Dataset | None) -> tuple[str, ...]:
    """Every column name THIS report may be asked for — `DEF-REP-7072`.

    ⚠ **A CONTROL AND A READ THAT SHARE ONE WORD OUT OF SEVEN.** Until this
    function existed, `_requested_columns` checked a run's ticked columns
    against the DATASET's declaration and nothing else. That is right for the
    nine dataset-backed reports and says nothing at all about a report served
    by a viewer of its own: the statement serves seven names, the
    `journal_lines` dataset declares five, and the two lists intersect in
    `reference` and in nothing else. Opening the editor — the only thing that
    sends a `columns` control — therefore cut a seven-column statement to ONE,
    measured on real PostgreSQL 16:

        runner.run("statement", {...})                  -> 7 columns
        runner.run("statement", {..., "columns": <7>})  -> ['reference']

    **Neither half was wrong about its own vocabulary, which is why nothing
    caught it.** The editor offered the dataset's attributes because that is
    what a definition chooses from; the runner honoured the dataset's
    attributes because that is what a definition may name. A viewer that owns
    a report owns its column vocabulary too, and this is the one place that
    says so — read by the render narrowing, by `validate()` at save, and
    published to the editor as `column_choices`, so the offer and the honour
    can no longer come from two lists.

    ⚠ **IT IS NOT A HOLE IN §8.1.** A module viewer is reviewed code in this
    repository exactly as a dataset is; the property the architecture rests on
    is *a clerk cannot name a column no reviewed declaration offers*, and this
    is a reviewed declaration. What a clerk still cannot do is invent one.
    """
    owned = viewer_columns(key)
    if owned:
        return owned
    if dataset is None:
        return ()
    names = [column.name for column in dataset.columns]
    names.extend(measure.name for measure in dataset.measures)
    return tuple(dict.fromkeys(names))


def _requested_columns(
    definition: ResolvedDefinition, dataset: datasets.Dataset, bound: dict[str, Any]
) -> tuple[str, ...]:
    """The columns THIS run draws — the clerk's ticks, else the stored ones.

    `P5.3`. The shape is `_requested_grouping`'s, deliberately: a run parameter
    wins because 2·2's tick list is a control the clerk turns, and the
    definition's own `columns` is the report as saved.

    ⚠ **AN UNKNOWN NAME IS DROPPED AND NEVER RAISED.** At SAVE an unknown column
    is refused with the column named (`P5.2`) — that is where a clerk finds out
    they mistyped. At RENDER the caller may be following a stale bookmark to a
    report whose dataset has since lost a column, and `bind`'s own docstring
    already settled that case for every other control: dropping is the shipped
    behaviour and raising would turn a stale link into an error page.
    """
    raw = bound.get("columns")
    if isinstance(raw, str):
        chosen = tuple(part.strip() for part in raw.split(",") if part.strip())
    elif isinstance(raw, (list, tuple)):
        chosen = tuple(str(part) for part in raw)
    else:
        return tuple(definition.columns)
    # `DEF-REP-7072` — the vocabulary is the REPORT's, not always the dataset's.
    # A module viewer declares its own; see `served_columns`.
    known = set(served_columns(definition.key, dataset))
    return tuple(name for name in chosen if name in known)


def _shaped(
    payload: dict[str, Any],
    definition: ResolvedDefinition,
    dataset: datasets.Dataset,
    bound: dict[str, Any],
) -> dict[str, Any]:
    """`P2.17`'s group rows and `P2.22`'s footer, applied to every report at once.

    ⚠ **THIS IS THE WIRING, AND IT IS HERE RATHER THAN IN `queries.py` FOR TWO
    REASONS.** `run()` is the ONE path the viewer and the export both take
    (`P0.5`), so a refusal added here reaches the screen and the file together
    and cannot be added to one and forgotten on the other — which is the exact
    fault `P0.5` was written to remove. And `queries.py` builds NINE separate
    `totals=` maps: wiring each of them would be nine chances to miss one, and
    the ninth would be a report quietly still showing a wrong number.

    ⚠ **A REPORT THAT GROUPS BY NOTHING AND SPANS NOTHING IS UNCHANGED, BYTE
    FOR BYTE.** `footer()` replaces a key only when `refusal_for` returns
    something, so the ageing as it ships today — one row per debtor, as at a
    date, no grouping — serves exactly the totals it served yesterday. That is
    the half that makes this safe to put on the shared path.

    ⚠ **AN UNSERVABLE GROUPING IS DROPPED, NOT RAISED.** `validate()` refuses
    it at save. At render a clerk may be following a stale bookmark, and
    `bind`'s own docstring already settled that case: dropping is the shipped
    behaviour and raising would be a user-visible change in a phase whose
    brief says a clerk can newly do nothing. What went is recorded in
    `unavailable` so a dropped grouping is never silent.
    """
    grouping = _requested_grouping(definition, bound)
    unavailable = list(payload.get("unavailable") or ())

    # ── `P5.3` · the columns the clerk has ticked, applied to THIS run ─────
    # ⚠ **THE ROWS ARE LEFT WHOLE AND ONLY `columns` IS NARROWED.** The table
    # draws `report.columns`, so narrowing that list is what the clerk sees
    # change; projecting every row dict as well would cost a pass over the page
    # and buy nothing, and it would break the footer, which is keyed by measure
    # name and not by what is on screen.
    requested = _requested_columns(definition, dataset, bound)
    if requested and bound.get("columns") is not None:
        served = payload.get("columns")
        # ⚠ **`list` ALONE WAS WRONG AND IT FAILED SILENTLY.** Six of the nine
        # queries publish `columns` as a TUPLE, so an `isinstance(served, list)`
        # guard skipped the narrowing entirely and the panel's ticks reached the
        # server, were validated, and changed nothing — the request was right,
        # the response was right, and the table did not move. Found by walking
        # it in a browser; `tsc`, the DOM suite and the backend suite were all
        # green over it, because none of them runs a real query.
        if isinstance(served, (list, tuple)):
            # Only columns the QUERY actually produced — a dataset may declare a
            # column this report's query does not select, and offering it as a
            # header over empty cells is worse than not offering it.
            narrowed = [name for name in requested if name in served]
            if narrowed:
                payload = dict(payload)
                payload["columns"] = narrowed
    if grouping:
        try:
            slicers.validate_grouping(dataset.code, grouping, tuple(bound))
        except slicers.GroupingRefused as exc:
            unavailable.append(
                {"field": "group_by", "code": "grouping_not_served", "detail": str(exc)}
            )
            grouping = ()

    if grouping:
        rows = payload.get("rows")
        # ⚠ **THE PAGE DECIDES WHETHER A PYTHON Σ IS EVEN ARITHMETICALLY LEGAL.**
        # A query that publishes SQL group cells is authoritative. One that does
        # not may still be rolled up in Python — but ONLY when the rows in hand
        # are the whole filtered set, which is what `page` states. Otherwise the
        # subtotals would cover a page under a footer covering the report:
        # `$14,185.80` under `$30,750.07`, measured (`DEF-REP-6875`).
        page = payload.get("page")
        whole_set = True
        if isinstance(page, dict):
            total = page.get("total")
            served = len(rows) if isinstance(rows, list) else 0
            whole_set = total is None or int(total) <= served
        if isinstance(rows, list) or isinstance(rows, tuple):
            try:
                shaped_rows = slicers.group_rows(
                    dataset.code,
                    list(rows),
                    grouping,
                    groups=payload.get("groups") or None,
                    whole_set=whole_set,
                )
            except slicers.GroupingRefused as exc:
                unavailable.append(
                    {
                        "field": "group_by",
                        "code": "grouping_needs_a_grouped_query",
                        "detail": str(exc),
                    }
                )
                grouping = ()
            else:
                grouped = any(
                    isinstance(row, dict) and row.get("__kind__") == "group"
                    for row in shaped_rows
                )
                payload = dict(payload)
                payload["rows"] = shaped_rows
                if grouped:
                    payload["group_by"] = list(grouping)
                    # ⚠ A grouped answer from SQL cells is COLLAPSED — every
                    # group's Σ covers the filtered set and the fact rows are one
                    # page of it, so they are not interleaved. `P2.24` opens a
                    # group through its `path`.
                    payload["collapsed"] = bool(payload.get("groups"))
                else:
                    # ⚠ **NEVER ECHO A GROUPING NOTHING APPLIED.** This is the
                    # `DEF-REP-6855` fault exactly: the payload said
                    # `group_by: ["accounting_period"]` over ungrouped rows, so
                    # every check downstream — and every reader — was told the
                    # report was grouped. An absence with a reason beside it is
                    # the only honest answer.
                    grouping = ()
                    unavailable.append(
                        {
                            "field": "group_by",
                            "code": "grouping_not_served",
                            "detail": (
                                f"{dataset.code}: nothing in the served rows or in this "
                                f"query's GROUP BY carries "
                                f"{', '.join(_requested_grouping(definition, bound))}, so the "
                                "report is not grouped."
                            ),
                        }
                    )
    for level in payload.get("groups_not_served") or ():
        unavailable.append(
            {
                "field": "group_by",
                "code": "level_has_no_group_by",
                "detail": (
                    f"{dataset.code}: this query cuts no GROUP BY for {level!r}, so it is "
                    "not grouped. A page-scoped Σ would not foot to the footer."
                ),
            }
        )

    totals = payload.get("totals")
    if isinstance(totals, dict):
        payload = dict(payload)
        payload["totals"] = additivity.footer(
            dataset.code,
            totals,
            # `DEF-REP-9150` — the window the report SERVED, so an as-at
            # report asked with `from`/`to` is not refused as a range.
            slicers.footer_across(dataset.code, grouping, bound, payload.get("window")),
        )
    # ── `DEF-REP-6902` / `DEF-REP-6903` · WHAT KIND OF THING EACH COLUMN IS ──
    #
    # ⚠ **THE SCREEN WAS PRINTING STORAGE PRECISION AT CLERKS ON EVERY REPORT
    # THIS DATASET FALLBACK SERVES.** Photographed at 1440 on 2026-09-27:
    # `15816.000000` in the trend pack's footer directly under a tile reading
    # `$15,816.00` for the same figure, and `247.300000` down the account
    # census's BALANCE column. CLAUDE.md hard rule 2 says money is STORED to
    # four places, a percentage to six, and **both DISPLAY two** — and the
    # viewer had no way to know which columns those were, because the only
    # thing on the wire was a list of NAMES. It carried a hand-typed
    # `MONEY_COLUMNS` map naming five reports out of forty-six, so the other
    # forty-one rendered every figure with `String(...)`.
    #
    # ⚠ **THIS IS THE ONE PLACE THAT KNOWS.** The DATASET declares each
    # column's `type`, its `unit` and its stored `scale`; `_shaped` already
    # holds the dataset and the served column list, and it is on `run()`, the
    # one path the viewer and the export both take (`P0.5`). Publishing it
    # anywhere else would be a second derivation of one fact, which is the
    # fault `DEF-REP-6866` records two files over.
    #
    # ⚠ **NOTHING IS ROUNDED HERE AND NOTHING MAY BE.** CLAUDE.md: *round only
    # at finalization/display*. The wire keeps every stored digit — a report
    # that rounded before it was displayed could not be reconciled against the
    # figure it came from, and a ❄️ FROZEN B4/B5 figure is safe only while the
    # query returns what is stored. This says what a figure IS; the screen
    # decides how many digits a person reads.
    # ⚠ RENAMED FROM `served_columns` WITH `DEF-REP-7072`: that is now a
    # module-level function of this file, and a local of the same name inside
    # `_shaped` would shadow it for any later reader who reached for it here.
    typed_columns = payload.get("columns")
    if isinstance(typed_columns, (list, tuple)):
        declared = {column.name: column for column in dataset.columns}
        meta: dict[str, Any] = {}
        for name in typed_columns:
            column = declared.get(str(name))
            # ⚠ **A COLUMN THE DATASET DOES NOT DECLARE IS OMITTED, NOT
            # GUESSED.** Several queries select a derived column the dataset
            # never declared; inventing a type for one would make the screen
            # confident about a figure nobody typed. An absent entry means
            # *render it as text*, which is exactly what the screen did before.
            if column is not None:
                meta[str(name)] = column.as_dict()
        # ⚠ **A QUERY'S OWN DECLARATION WINS, AND IT IS A MERGE RATHER THAN A
        # REPLACEMENT.** Two reports derive money columns their dataset has
        # never heard of — the close pack's tie-out figures and the tax
        # remittance's outstanding pair — and say so in `_report(column_meta=)`.
        # Overwriting here would have silently deleted that, which is the shape
        # of every defect this wave is about: the code was right and something
        # downstream threw the answer away.
        published = payload.get("column_meta")
        if isinstance(published, dict):
            meta.update({str(k): v for k, v in published.items()})
        if meta:
            payload = dict(payload)
            payload["column_meta"] = meta

    if unavailable != list(payload.get("unavailable") or ()):
        payload = dict(payload)
        payload["unavailable"] = unavailable
    return payload


def queries_for(key: str, dataset: str | None = None) -> Any:
    """The built query for a key, or None.

    Imported lazily and looked up by KEY rather than held as a module-level
    map, so this file adds no seventh hand-typed dispatch table to the six
    `P0.7` is deleting.

    ⚠ **TWO LOOKUPS, AND THE ORDER IS THE WHOLE POINT OF A DATASET.** A
    per-REPORT viewer wins when one exists — there are four, they are shipped
    and measured, and moving one onto a new path is a behaviour change wearing
    a refactor's clothes. Otherwise the DATASET's own query serves it, which is
    the brief's arithmetic made mechanical: *"46 reports sit on 9 datasets"*,
    so a dataset landing turns on every definition built upon it rather than
    one card at a time.

    A dataset query may still decline one definition — `queries.DatasetCannotServe`
    — and that is not the same thing as the dataset having no query at all. The
    two refusals need opposite work: one waits for a dataset lane, the other for
    a ruling about which dataset a definition belongs on.
    """
    from apps.reports import queries

    # ⚠ **A MODULE THAT OWNS A REPORT OWNS ITS REGISTRATION.** `statement.py`
    # holds R24's viewer and names it in `MODULE_VIEWERS`; this is the SAME
    # lookup as `queries.VIEWERS` and not a second rule — a per-REPORT viewer
    # wins, then the DATASET's own query, exactly as below. It is one more
    # dict read rather than a seventh hand-typed dispatch table, and it keeps
    # `queries.py` from being the one file every report lane edits at once.
    # `_OWNING_MODULES` (CR-179-BRC10) — `statement` and `rate_impact` both.
    found = owned_viewer(key) or queries.VIEWERS.get(key)
    if found is not None:
        return found
    if dataset is None:
        return None
    dataset_query = queries.DATASET_QUERIES.get(dataset)
    if dataset_query is None:
        return None
    return lambda params, _key=key, _query=dataset_query: _query(params, key=_key)


def stream_for(key: str, dataset: str | None = None) -> Any:
    """The STREAMING read for a key, or None — a generator over every row.

    §8.2 (p91): *"the left path never fetches more than a page; the right path
    never holds one."* It is a separate lookup from `queries_for` and returns a
    different kind of object on purpose, so an export cannot reach a paging
    function and inherit a screen's page size — the defect caught on the
    billing register on 2026-09-26, where a 38,000-row file would have been
    written as a valid-looking fifty rows.
    """
    from apps.reports import queries

    # The export half of the module-owned registration above. Same order, same
    # reasoning: a per-REPORT stream wins, then the dataset's.
    # ⚠ **`queries.KEY_STREAMS` JOINS THIS LOOKUP AND IS NOT A SECOND RULE
    # (`P6.11`).** It is the same `or` chain `queries_for` uses one function
    # up — a per-REPORT read wins, then the DATASET's — so there is one answer
    # to *which read serves this key* on both paths. Without it the three
    # joining reads' generators would be unreachable: `stream_for` would fall
    # through to the DATASET's stream and hand R36's export the AUDIT TRAIL's
    # rows under R36's name, which is a valid-looking file of the wrong
    # report. Hard-won law 2, on the path nobody looks at.
    owned = _owned("MODULE_STREAMS").get(key) or queries.KEY_STREAMS.get(key)
    if owned is not None:
        return owned
    if dataset is None:
        return None
    dataset_stream = queries.DATASET_STREAMS.get(dataset)
    if dataset_stream is None:
        return None
    return lambda params, _key=key, _stream=dataset_stream: _stream(params, key=_key)


def rows_for(key: str, params: Any = None, *, whole: bool = False) -> list[dict[str, Any]]:
    """The rows, for an export writer. `apps/reports/exports.py` calls this.

    It exists so the export and the viewer share `run()` rather than sharing a
    convention. Byte-identical rows is then a property of there being one
    function, not of two call sites agreeing.
    """
    return run(key, params, whole=whole).rows


# ⚠ `built_in_fallback()` WAS DRAFTED HERE AND DELETED BEFORE IT WAS COMMITTED.
# It would have read `apps/reports/catalog.py`'s tuple when the table held no
# row — and nothing would have called it, because `reports/0003` seeds all
# forty-six and every key the runner serves is among them. That is precisely
# the furniture `P0.7` is deleting two files away (`VIEWER_KEYS`, `card_for()`):
# a plausible unused export that the next lane reads, assumes is the interface,
# and wires to. Recorded rather than silently dropped so the idea is not had
# twice.

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 0 · P0.5 (05-prototype/09 Reports Build Brief.pdf p7 read as an image per B14 rule 42 · §7.5 p87)
# screens: none — Phase 0 ships no screen
# generated: 2026-09-26 by lane REP-P0A; amended 2026-09-27 by lane REP-UNBLOCK (DEF-REP-6855 — the grouping is resolved BEFORE the query runs so a dataset query can cut it in SQL, and a grouping nothing applied is no longer echoed back as though it had been); amended 2026-09-28 by lane REP-STMT-SCREEN (`DEF-REP-7072` — `served_columns()`/`viewer_columns()`: a report served by a MODULE VIEWER declares its own column vocabulary, and the editor's offer, the render narrowing and `validate()` at save now read that one declaration. Measured before: seven statement columns and the `journal_lines` dataset's five attributes share `reference` and nothing else, so opening the editor cut the table to ONE column)
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the byte-identity test failed with `AttributeError: module 'apps.reports.runner' has no attribute 'rows_for'` before this file existed
# exceptions: (1) the export's DOUBLE execution is NOT fixed here — the second run exists only to enforce `EXPORT_ROW_CAP`, and `P2.4` deletes the cap · (2) six of the nine datasets have no query yet and a definition on one raises `DatasetNotExecutable` NAMING the dataset, never an empty result
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
