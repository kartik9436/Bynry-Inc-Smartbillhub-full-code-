# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-001 (S14 Premises list — capability row "Export: CSV (IS-9)") ·
#           US-MET-002 (S15 Units list — same row) · US-MET-005 (S26 Routes ·
#           S27 Cycles — the two read-only ops views, both declaring CSV)
#           Screens: S14, S15, S26, S27
# Rules:    BR-SHL-016 (server-side export under the caller's tenant context;
#           50,000-row cap; money exports write audit_log — none of these four
#           lists is money-bearing) · BR-SHL-010 (the capability row IS the
#           column set) · BR-SHL-011 (the export mirrors the list's own
#           q/sort/dir/f.‹name› state) · BR-MET-036 (occupancy is DERIVED — the
#           file writes what the screen derives, never a stored flag) ·
#           BR-MET-011 (collected/last completion/progress derive from committed
#           reads; NULL is unknown, never 0) · BR-MET-033 (route meter counts
#           come from membership)
# Tests:    06-backend/tests/test_be_list_export.py
# Impacts:  apps.tenancy export registry (POST /exports) — registered from
#           MeteringConfig.ready()
# ───────────────────────────────────────────────────────
"""The four metering lists that declare Download, registered as export resources.

BR-TEN-031's posture, applied to exports: the platform owns the endpoint, the
job and the CSV writer; the OWNING module owns what its list contains. Every
`select` below is the SAME selector call the list endpoint makes (minus
pagination) and every `serialize` is the SAME row serializer it serves, so a
file can only ever contain what the screen shows for the same request state.

Column sets are the capability rows of EP-MET-01 / EP-MET-02, in the matrix's
order. Two deliberate departures, both the S61 export's own precedent:

- A capability column that is ONE cell over TWO stored fields is split into two
  CSV columns ("Occupant/Account" → `occupant` + `account_no`; "Read window" →
  `window_start` + `window_end`; the Route cell's code + name; the Type cell's
  route type + feeder ref). A CSV consumer needs the parts in their own
  columns; a screen can afford to run them together, a spreadsheet cannot.
- A column whose ratified name has no API field behind it uses the API field
  name, noted here: "Address" → `address_line`, "Type" (premises) →
  `premises_type_name`, "Premise" (units) → `premise_no`, "Cycle" (routes) →
  `cycle_code`.

Nothing here formats money: none of these four lists carries a money column, so
none of them writes an audit row (BR-SHL-016's clause is for money tables).
That absence is stated so it is not read as an omission.
"""

from typing import Any
from collections.abc import Callable, Mapping

from apps.metering import selectors
from apps.tenancy import exports as export_kernel
from apps.tenancy.exports import ExportColumn, ExportResource
from core.pagination import ListParams

# US-MET-005 §5: a route with NO assignee is the AMI auto-pull path — the null
# is meaningful. The file writes the same machine token the S61 export writes
# for a null actor rather than the screen's translated "System (auto-pull)"
# copy, because copy belongs to IS-8 and a CSV must stay parseable.
SYSTEM_ASSIGNEE = "system"


def _premises_select(params: ListParams) -> Any:
    return selectors.premises_list(
        q=params.q, filters=params.filters, sort=params.sort, direction=params.dir
    )


def _units_select(params: ListParams) -> Any:
    return selectors.units_list(
        q=params.q, filters=params.filters, sort=params.sort, direction=params.dir
    )


def _routes_select(params: ListParams) -> Any:
    # S26 has no server sort vocabulary yet (GET /routes takes q + filters only
    # and answers a plain array — reported by the frontend lane); the export
    # therefore inherits the selector's own `code, id` order, exactly what the
    # screen shows.
    return selectors.routes_list(q=params.q, filters=params.filters)


def _cycles_select(params: ListParams) -> Any:
    return selectors.cycles_list(q=params.q, filters=params.filters)


def _reads_select(params: ListParams) -> Any:
    # ⚠ **THE ARCHIVE OPT-IN IS DELIBERATELY NOT HERE (BR-MET-055).**
    # US-MET-012 TC-10 in as many words: a client requesting *"an export of all
    # history"* gets queries *"scoped to the 2-yr hot window"* — and the
    # ratified POST /exports body carries q/sort/dir/filters only, no top-level
    # `archive` param to mirror. So the file is the DEFAULT view of the screen:
    # the hot window, the caller's own filters, the same selector call.
    #
    # `CR-192-BRC10` task 13 — the list's `answer[<key>]=<value>` filters
    # travel in the export body's `filters` under the SAME spelling the list's
    # URL uses, are read by the SAME parser the list endpoint uses, and narrow
    # by the SAME subquery (BR-SHL-011: the file is the list the clerk sees).
    # The selection is then streamed in chunks with each chunk's answers read
    # in one query (`read_answers_office.AnswerEnrichedSelection`).
    from apps.metering import read_answers_office, read_formats

    filters = dict(params.filters or {})
    answers = read_formats.answer_filters(filters)
    plain = {k: v for k, v in filters.items() if not str(k).startswith("answer[")}
    return read_answers_office.AnswerEnrichedSelection(
        selectors.read_result_set(
            q=params.q,
            filters=plain,
            sort=params.sort,
            direction=params.dir,
            include_archive=False,
            answer_filters=answers,
        )
    )


def _reads_serialize(row: Any) -> Mapping[str, Any]:
    """`read_dict` plus the chunk's answer cells (export plumbing only)."""
    from apps.metering import read_answers_office

    served = dict(selectors.read_dict(row))
    served[read_answers_office.ANSWER_CELLS] = getattr(row, read_answers_office.ANSWER_CELLS, {})
    return served


def _reads_answer_columns(params: ListParams, selection: Any) -> tuple[ExportColumn, ...]:
    """One column per read-format question the exported rows carry."""
    from apps.metering import read_answers_office

    return read_answers_office.export_answer_columns(getattr(selection, "queryset", selection))


def _meters_cell(row: Mapping[str, Any]) -> str:
    """The S15 Meters cell: each meter number with its (sub)/(master)
    qualifier, exactly as the screen qualifies them (US-MET-002 §5)."""
    parts = []
    for meter in row.get("meters") or []:
        number = meter.get("asset_no") or ""
        qualifier = meter.get("qualifier")
        parts.append(f"{number} ({qualifier})" if qualifier else str(number))
    return export_kernel.MULTI_VALUE_SEPARATOR.join(parts)


def _assignee(row: Mapping[str, Any]) -> Any:
    return row.get("assigned_to") or SYSTEM_ASSIGNEE


def _recorded(field: str) -> Callable[[Mapping[str, Any]], bool]:
    """DEF-762 — has anyone answered the services question for this address?

    `None` is SQL NULL passed straight through by the metering selectors: the
    question was never put. Any list, empty included, is an answer somebody
    gave. Built as a factory over the FIELD NAME because two resources need the
    same derivation from two differently-named keys — premises rows carry
    `services_available`, unit rows carry `services` (their premises', per
    DEF-755) — and one derivation cannot disagree with itself the way two copies
    could.
    """

    def read(row: Mapping[str, Any]) -> bool:
        return row.get(field) is not None

    return read


_services_recorded = _recorded("services_available")


PREMISES = ExportResource(
    name="premises",
    slug="premises",
    module="metering",
    select=_premises_select,
    # DEF-650 — the export runs over EVERY premises, so it does not expand each
    # owner's account (one account read + one ledger derivation each). No export
    # column reads it; the owner's NAME and the free text are both already here.
    serialize=lambda row: selectors.premises_detail_dict(row, with_owner_account=False),
    columns=(
        # EP-MET-01 S14 row: Premise ID · Address · Type · Units ·
        # Services available · Owner/manager · Status.
        ExportColumn("premise_no", "premise_no"),
        ExportColumn("address_line", "address_line"),
        ExportColumn("premises_type_name", "premises_type_name"),
        ExportColumn("units", "units", export_kernel.NUMBER),
        ExportColumn("services_available", "services_available", export_kernel.LIST),
        # ⚠ **DEF-762 — THE CSV NEEDS A SECOND CELL AND THE API DOES NOT.**
        # `services_available` is nullable on purpose (CR-036 (h): NULL means
        # *never asked*, `[]` means *offers nothing*), and the API serves the
        # difference directly. A CSV cannot: `format_list` writes an EMPTY CELL
        # for both, which is exactly the collapse the fix removes — so the file
        # would have gone on lying after the screens stopped.
        #
        # It is DERIVED from the same one field, in this one place, so it can
        # never disagree with the cell beside it (an `asked` column stored
        # alongside the list COULD). `false` = nobody has been asked about this
        # address; `true` with an empty cell = this address offers nothing.
        ExportColumn("services_recorded", _services_recorded, export_kernel.BOOLEAN),
        ExportColumn("owner_manager", "owner_manager"),
        ExportColumn("status", "status"),
        # `DEF-MET-10164` (PO 2026-10-17: *"Both go in the export"*) — the
        # stamp the list's Created column draws, in the tenant's zone WITH its
        # offset (IS-9's timestamp form). Age is NOT a column: it is a
        # subtraction from the day the file is opened, and a file keeps no
        # today. The importer reads this exact form back
        # (`import_runs._parse_created`), so an exported file round-trips.
        ExportColumn("created_at", "created_at", export_kernel.TIMESTAMP),
    ),
)

UNITS = ExportResource(
    name="units",
    slug="units",
    module="metering",
    select=_units_select,
    serialize=selectors.unit_list_dict,
    columns=(
        # EP-MET-01 S15 row: Unit ID · Premise · Unit · Type · Services ·
        # Meters · Occupant/Account · Status. `occupancy` rides with them
        # because the screen renders it as its own column (BR-MET-036 derived);
        # a file that dropped it would not match the list.
        ExportColumn("unit_no", "unit_no"),
        ExportColumn("premise_no", "premise_no"),
        ExportColumn("label", "label"),
        ExportColumn("unit_type", "unit_type"),
        # ⚠ **`services` CHANGED MEANING ON 2026-08-26 AND `metered_services`
        # IS THE OLD ONE, RENAMED (DEF-755).** `services` is the unit's
        # PREMISES' list — the rule in force is that a unit's services ARE its
        # premises' (PO, after CR-037 was withdrawn). What this column used to
        # hold is *what is metered here*, which is a different and still useful
        # fact, so it keeps its data and gets its own name rather than being
        # deleted or left sharing a word. A file that carried only the new
        # meaning would silently answer a question its header did not ask.
        ExportColumn("services", "services", export_kernel.LIST),
        # DEF-762's problem again, one level down: `format_list` writes an empty
        # cell for a NULL premises list and for an empty one alike, so the
        # derived flag rides along here too. `false` = nobody was ever asked
        # about this unit's address.
        ExportColumn("services_recorded", _recorded("services"), export_kernel.BOOLEAN),
        ExportColumn("metered_services", "metered_services", export_kernel.LIST),
        ExportColumn("meters", _meters_cell),
        ExportColumn("occupancy", "occupancy"),
        ExportColumn("occupant", "occupant"),
        ExportColumn("account_no", "account_no"),
        ExportColumn("status", "status"),
        # `DEF-MET-10164` — the UNIT's own stamp; see the premises column.
        ExportColumn("created_at", "created_at", export_kernel.TIMESTAMP),
    ),
)

ROUTES = ExportResource(
    name="routes",
    slug="routes",
    module="metering",
    select=_routes_select,
    serialize=None,  # routes_list already serves the row dicts
    columns=(
        # EP-MET-02 S26 row: Route · Type · Assigned to · Cycle · Meters ·
        # Collected · Last completion · Status.
        ExportColumn("code", "code"),
        ExportColumn("name", "name"),
        ExportColumn("route_type", "route_type"),
        ExportColumn("feeder_ref", "feeder_ref"),
        ExportColumn("assigned_to", _assignee),
        ExportColumn("cycle_code", "cycle_code"),
        ExportColumn("meters", "meters", export_kernel.NUMBER),
        # BR-MET-011: NULL is "not collected yet", and empty is how a CSV says
        # unknown. A 0 here would be a different, false claim.
        ExportColumn("collected", "collected", export_kernel.NUMBER),
        ExportColumn("last_completion", "last_completion", export_kernel.TIMESTAMP),
        ExportColumn("status", "status"),
    ),
)

CYCLES = ExportResource(
    name="cycles",
    slug="cycles",
    module="metering",
    select=_cycles_select,
    serialize=None,  # cycles_list already serves the row dicts
    columns=(
        # EP-MET-02 S27 row: Cycle · Routes · Read window · Bill date ·
        # Expected · Collected · Progress · Status.
        #
        # ⚠ **THE READ-WINDOW CELLS READ THE SAME KEYS AND THE SOURCE CHANGED
        # UNDERNEATH THEM (W5-T2).** `window_start`/`window_end` were columns on
        # `cycles`; metering 0021 dropped them and `cycle_dict` derives the pair
        # from `start_day` + `days_to_complete` for every cycle. This resource
        # serialises `cycles_list`'s row dicts (`serialize=None`), so the export
        # needed no edit to follow — which is exactly why the keys were kept.
        # It is noted rather than left silent: an export column named after a
        # column that no longer exists is the next lane's confusion.
        #
        # The three SCHEDULE fields are exported now too. A cycles export that
        # said WHEN the window ran but not what the cycle repeats on could not
        # be used to reconstruct the schedule it describes.
        ExportColumn("code", "code"),
        ExportColumn("routes", "routes", export_kernel.LIST),
        ExportColumn("frequency", "frequency"),
        ExportColumn("start_day", "start_day", export_kernel.NUMBER),
        ExportColumn("days_to_complete", "days_to_complete", export_kernel.NUMBER),
        ExportColumn("window_start", "window_start", export_kernel.DATE),
        ExportColumn("window_end", "window_end", export_kernel.DATE),
        # ⚠ `bill_date` IS STILL EXPORTED AND ITS SOURCE MOVED (RC-W6). The
        # stored column is gone (metering 0023, OQ-344); `cycle_dict` derives
        # the key from the bill DAY and the cycle's next period — *"the bill
        # day, in the month after the period ends"*. This export serialises
        # `cycles_list`'s row dicts, so the column follows with no edit; it is
        # noted rather than left silent, because an export column whose meaning
        # changed under it is the next lane's confusion.
        ExportColumn("bill_date", "bill_date", export_kernel.DATE),
        ExportColumn("expected", "expected", export_kernel.NUMBER),
        ExportColumn("collected", "collected", export_kernel.NUMBER),
        ExportColumn("progress", "progress", export_kernel.NUMBER),
        ExportColumn("status", "status"),
    ),
)


READS = ExportResource(
    name="reads",
    slug="reads",
    module="metering",
    select=_reads_select,
    serialize=_reads_serialize,
    # `CR-192-BRC10` task 13: *"exported"* — the utility's own questions,
    # one column each, after the capability row's columns.
    extra_columns=_reads_answer_columns,
    columns=(
        # CR-038 W5 — the S25 capability row (EP-MET-04): Meter · Cycle · Route
        # · Service · Premise · Previous · Current · Usage · Source · Status,
        # in the matrix's order, with this file's two standing precedents
        # applied:
        #   · a cell of TWO stored facts is split into two CSV columns — the
        #     Premise cell ("1408 Elm · A") into `premise` + `unit_label`, the
        #     Usage cell into `consumption` + `unit` (CLAUDE.md rule 3: the
        #     quantity never travels without its unit — in a CSV the unit is
        #     its own parseable cell), and the Source cell into `source` +
        #     `source_detail`;
        #   · the ratified column with no API field uses the API field name:
        #     Previous → `prior_value`, Current → `current_value`.
        # `read_at` rides second exactly as the screen draws it (the S25 lane's
        # reported deliberate divergence: the list is sorted by read date and a
        # reading without its date cannot be checked against a bill), and
        # `channel` rides because two same-day rows of a TOU meter are
        # indistinguishable without it (B2 r8's channel model).
        ExportColumn("meter", "meter"),
        ExportColumn("read_at", "read_at", export_kernel.TIMESTAMP),
        ExportColumn("cycle", "cycle"),
        ExportColumn("route", "route"),
        ExportColumn("service", "service"),
        ExportColumn("premise", "premise"),
        ExportColumn("unit_label", "unit_label"),
        # ── DEF-1123 · QUANTITY, NOT NUMBER ──────────────────────────────────
        # These three declared NUMBER — *written as served* — because IS-9 had
        # no QUANTITY kind, so the reads CSV wrote BR-MET-019's storage
        # precision: `1008.000000` in the cell the PO reported as
        # `1008.000000` on the screen. The PO ruled on 2026-08-27 (OQ-620(b))
        # that a downloaded CSV shows *"two decimals, like the screen"*, so
        # these follow BR-MET-144 exactly as their columns do: `1008` and
        # `26.24`. The UNIT rides in its own parseable cell below, which is
        # this file's standing precedent and hard rule 3 in a CSV.
        ExportColumn("prior_value", "prior_value", export_kernel.QUANTITY),
        ExportColumn("current_value", "current_value", export_kernel.QUANTITY),
        ExportColumn("consumption", "consumption", export_kernel.QUANTITY),
        ExportColumn("unit", "unit"),
        ExportColumn("channel", "channel"),
        ExportColumn("source", "source"),
        ExportColumn("source_detail", "source_detail"),
        ExportColumn("status", "status"),
    ),
)


def register() -> None:
    """Called once from MeteringConfig.ready(). The BR-SHL-011 vocabularies are
    read from the LIST endpoints themselves (apps/metering/api.py), so an export
    can never honor a filter the list ignores — or ignore one it honors."""
    from apps.metering import api as metering_api

    export_kernel.register_export_resource(
        _with_vocabulary(
            PREMISES,
            sorts=tuple(selectors.PREMISES_SORTS),
            default_sort=selectors.PREMISES_DEFAULT_SORT,
            filters=metering_api.PREMISES_FILTERS,
        )
    )
    export_kernel.register_export_resource(
        _with_vocabulary(
            UNITS,
            sorts=tuple(selectors.UNIT_SORTS),
            default_sort=selectors.UNIT_DEFAULT_SORT,
            filters=metering_api.UNIT_FILTERS,
        )
    )
    export_kernel.register_export_resource(
        _with_vocabulary(ROUTES, sorts=(), default_sort=None, filters=metering_api.ROUTE_FILTERS)
    )
    export_kernel.register_export_resource(
        _with_vocabulary(CYCLES, sorts=(), default_sort=None, filters=metering_api.CYCLE_FILTERS)
    )
    # CR-038 W5 — the S25 list (US-MET-012's declared "Export: CSV (IS-9)").
    # `POST /exports {"resource": "reads"}` used to resolve NOTHING, the exact
    # DEF-034 shape one module over. The default is the capability row's own
    # `read_at desc`; the SORT KEY carries no minus because the kernel's
    # `params_from_payload` passes it back to `read_result_set(sort=…)`, whose
    # `_order` maps bare keys — direction travels separately as `default_dir`.
    export_kernel.register_export_resource(
        _with_vocabulary(
            READS,
            sorts=tuple(selectors.READ_SORTS),
            default_sort="read_at",
            filters=tuple(selectors.READ_FILTERS),
            default_dir="desc",
        )
    )


def _with_vocabulary(
    resource: ExportResource,
    *,
    sorts: tuple[str, ...],
    default_sort: str | None,
    filters: tuple[str, ...],
    default_dir: str | None = None,
) -> ExportResource:
    """The declared resource + the list endpoint's own param vocabulary."""
    from dataclasses import replace

    updated = replace(resource, sorts=sorts, default_sort=default_sort, filters=filters)
    if default_dir is not None:
        updated = replace(updated, default_dir=default_dir)
    return updated


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-001@947cf31 (EP-MET-01 lead story — hash = sha256/7 of the source epic; co-packets US-MET-002@947cf31 · US-MET-005@14f767b for S26/S27)
# generated: 2026-08-10 by story-coder v1 (list-export lane — the four metering capability rows that declared Download with no route)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — registration only; the resource is POST /exports) E=deferred(the four screens' Download buttons are the frontend half of this lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F on apps/core/config — the bar the baseline passes) black✔(this lane's 13 files; 32 pre-existing unformatted files are the repo baseline, untouched) py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped (unchanged) · migrate from empty✔ makemigrations --check --dry-run clean✔ (this lane adds NO migration) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) · frontend tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · mypy NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: S26/S27 have NO server sort vocabulary (GET /routes and GET /cycles take q + filters and answer plain unpaginated arrays — the pre-existing gap the frontend lane reported), so their exports inherit the selector's own order and declare no sorts — REPORTED, not invented · a capability cell that renders TWO stored fields is split into two CSV columns (Occupant/Account, Read window, Route code+name, Type+feeder ref) — the S61 export's own precedent for the Entity cell · four columns have no ratified name and use the API field name: address_line, premises_type_name, premise_no, cycle_code · a null route assignee is written as `system` (US-MET-005 §5's auto-pull path), the same token the S61 export writes for a null actor; the assignee is a user ID and is NOT resolved to a name — metering has no identity seam for it, REPORTED · collected / last_completion / progress export EMPTY while the W2 reads lane is unwired (BR-MET-011: unknown is not zero) · none of these four lists is money-bearing, so none writes an audit row — stated so the absence is not read as an omission
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
