# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-001 (EP-AST-01 — the S49 registry list: the three type tabs,
#           BR-AST-041's column + filter set)   Screens: S49
# Rules:    BR-SHL-016 (server-side export under the caller's tenant context;
#           50,000-row cap; money exports write audit_log — the registry is not
#           money-bearing) · BR-SHL-011 (the export mirrors the list's own
#           q/sort/dir/f.‹name› state, tab included) · BR-AST-041 (the S49
#           column + filter row) · BR-AST-004 (the tab IS a filter — one
#           resource, three tabs) · BR-AST-026 (asset_no is the user-facing
#           identifier; the uuid never stands in for it) · BR-AST-043/044
#           (read method + meter type are first-class registry columns)
# Tests:    06-backend/tests/test_be_list_export.py
# Impacts:  apps.tenancy export registry (POST /exports) — registered from
#           AssetsConfig.ready()
# ───────────────────────────────────────────────────────
"""S49's registry export — one resource for all three tabs (BR-AST-004).

The tab is a FILTER on the server (`f.tab=meters|sub_meters|behind_meter`), so
an export of the Sub-meters tab is the same resource with the same filter the
list carried: one registration, never three drifting ones. `parent_asset_no` is
in the column set for every tab because it is the Sub-meters tab's own column
and it is empty everywhere else — the honest way for one file shape to serve
three views.

The columns are BR-AST-041's default set as S49 actually renders it: Meter # ·
Type (+ meter type + read method) · UoM · Mult. · Assigned to · Installed ·
Status. The checkbox and the Actions cells are NOT columns — a CSV has no
selection and no buttons, and writing the server's `actions` array into a file
would export UI affordances as if they were data.

**BR-AST-041 names a "Service" column that this export does not carry.** The
served registry row (selectors.asset_dict) has no service field — only
`service_point_id` — and S49 does not render one either; the service is reached
through the assignment. Inventing a column here would mean inventing a join the
list itself does not make. REPORTED, not faked.
"""

from datetime import date
from typing import Any

from apps.assets import seams, selectors
from apps.tenancy import exports as export_kernel
from apps.tenancy.exports import ExportColumn, ExportResource
from core.pagination import ListParams


def _assets_select(params: ListParams) -> Any:
    return selectors.asset_list(
        q=params.q, filters=params.filters, sort=params.sort, direction=params.dir
    )


def _assets_row(asset: Any) -> dict[str, Any]:
    """The registry row plus its AGE as numbers (`DEF-AST-10178`).

    A file has no screen to subtract with, so the download carries the age
    itself — whole years, months and days from `age_start` to the retire date
    or the tenant's today — beside the start date and which date it was. Numbers
    and a code rather than `8 yrs 3 mos`: an export is machine-parseable
    (`BOOLEAN`'s own rule — never copy), and the words belong to the eleven
    catalogues. `past_life` is the screen's red, as true/false.
    """
    row = selectors.asset_dict(asset)
    start = date.fromisoformat(row["age_start"])
    end = asset.retire_date or seams.tenant_today()
    years, months, days = selectors.age_parts(start, end)
    life = asset.expected_life_years
    row.update(
        age_from=row["age_start_source"],
        age_years=years,
        age_months=months,
        age_days=days,
        past_life=bool(life) and years >= life,
    )
    return row


ASSETS = ExportResource(
    name="assets",
    slug="assets",
    module="assets",
    select=_assets_select,
    serialize=_assets_row,
    columns=(
        # BR-AST-026: the user-facing number leads; the uuid is not a column.
        ExportColumn("asset_no", "asset_no"),
        ExportColumn("parent_asset_no", "parent_asset_no"),
        # Both classifications, side by side (BR-AST-044) — code AND name, so
        # the file is readable by a human and joinable by a machine.
        ExportColumn("type", "type"),
        ExportColumn("type_name", "type_name"),
        ExportColumn("meter_type", "meter_type"),
        ExportColumn("read_method", "read_method"),
        # CLAUDE.md rule 3: a quantity never travels without its unit.
        ExportColumn("unit", "unit"),
        ExportColumn("multiplier", "multiplier", export_kernel.NUMBER),
        ExportColumn("assigned_to", "assigned_to"),
        ExportColumn("assigned_address", "assigned_address"),
        ExportColumn("install_date", "install_date", export_kernel.DATE),
        ExportColumn("status", "status"),
        ExportColumn("status_name", "status_name"),
        # DEF-AST-10178 — the Age column, as numbers (see `_assets_row`).
        ExportColumn("age_start", "age_start", export_kernel.DATE),
        ExportColumn("age_from", "age_from"),
        ExportColumn("age_years", "age_years", export_kernel.NUMBER),
        ExportColumn("age_months", "age_months", export_kernel.NUMBER),
        ExportColumn("age_days", "age_days", export_kernel.NUMBER),
        ExportColumn("past_life", "past_life", export_kernel.BOOLEAN),
    ),
)


def register() -> None:
    """Called once from AssetsConfig.ready(). The sort/filter vocabulary is the
    LIST endpoint's own (apps/assets/api.py), so the export can never honor a
    filter S49 ignores — the tab included."""
    from dataclasses import replace

    from apps.assets.api import ASSET_FILTERS

    export_kernel.register_export_resource(
        replace(
            ASSETS,
            sorts=tuple(selectors.ASSET_SORTS),
            default_sort=selectors.ASSET_DEFAULT_SORT,
            filters=ASSET_FILTERS,
        )
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AST-001@566072b (EP-AST-01 registry story — hash = sha256/7 of the source epic)
# generated: 2026-08-10 by story-coder v1 (list-export lane — S49 was named in the PO's nine)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — registration only; the resource is POST /exports) E=deferred(the S49 Download button is the frontend half of this lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F on apps/core/config — the bar the baseline passes) black✔(this lane's 13 files; 32 pre-existing unformatted files are the repo baseline, untouched) py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped (unchanged) · migrate from empty✔ makemigrations --check --dry-run clean✔ (this lane adds NO migration) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) · frontend tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · mypy NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: **the EP-AST-01 capability row declares Export "— (not shown in design)" for all three S49 tabs**, yet the PO ruling of 2026-08-09 names S49 among the nine lists to build; built per the RULING and the divergence REPORTED rather than silently resolved either way · BR-AST-041's "Service" column has no field on the served registry row (only service_point_id) and S49 renders none — omitted and REPORTED, not invented · the ☑ selection cell and the Actions cell are not columns: a CSV has no selection and no buttons, and the server's `actions` array is a UI affordance, not data · the registry carries no money column, so this export writes no audit row (BR-SHL-016's clause is for money tables) — stated so the absence is not read as an omission
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
