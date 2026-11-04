# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-001 (S9 Plans tab — capability row "Export: CSV (IS-9)") ·
#           US-RAT-008 (S9 Charge codes tab — same row) · US-RAT-009 (S9
#           Taxes & fees tab — same row) · US-RAT-010 (S9 History view over the
#           append-only rate-change log — same row) · US-RAT-004 (S9 Rate
#           schedules tab — DEF-441: r10 line 764 draws a nine-column TABLE, so
#           the tab gains the table capabilities it was excused from, export
#           included)   Screens: S9
# Rules:    BR-SHL-016 (server-side export under the caller's tenant context;
#           50,000-row cap; **money-table exports write `audit_log`** — all five
#           of these lists are money-bearing) · BR-SHL-029 (the cap constant) ·
#           BR-SHL-011 (the export mirrors the list's own q/sort/dir/f.‹name›
#           state) · BR-RAT-027 (plan base charges are DERIVED Σ) ·
#           BR-RAT-037 (the change log is append-only — read and export only) ·
#           BR-RAT-041/036 (a charge's / a tax's amount FORM decides which
#           field carries the number)
# Tests:    06-backend/tests/test_be_list_export.py
# Impacts:  apps.tenancy export registry (POST /exports) — registered from
#           RatingConfig.ready()
# ───────────────────────────────────────────────────────
"""The five Plans & Rates lists that declare Download, as export resources.

**Rate schedules is the fifth, added 2026-08-21 (DEF-441).** It had no export
because EP-RAT-02's capability row called the tab a card grid and excused it
from the table capabilities; r10 line 764 draws a nine-column table and the
matrix was simply wrong. The export follows the layout.

All five are MONEY-BEARING, so each accepted export writes its own `audit_log`
row (BR-SHL-016). That is the whole reason the registry carries a `money` flag
rather than the endpoint guessing from a column name — and rate schedules is
why that matters: its nine columns hold no amount at all, and a copy of a
tenant's whole pricing structure is exactly the event an audit trail wants.

**No money arithmetic happens here.** Every amount is the server's own
NUMERIC(18,6) STRING, handed to the IS-9 writer, which renders it at plain 2dp
for display (CLAUDE.md rule 2: round at finalization or display). Nothing in
this file adds, scales or compares a money value, and the 6-dp storage strings
are never re-derived — the export prints what the row holds.

**One display cell, two units → two CSV columns.** The Amount cell on the
charge-codes tab reads "1.5% or $5 min" — a percent, or money, or both, chosen
by `amount_rule` (BR-RAT-041). The Rate cell on the taxes tab does the same
across `kind` (percent / flat-per-bill / per-unit, BR-RAT-036). IS-9 gives a
money column one meaning: plain 2dp, no symbol. A single "amount" column would
therefore have to render a fraction as if it were dollars. So each of those
cells exports as its RULE plus the fields that rule uses, each in its own
column with its own kind — the file says which number is which, and a
spreadsheet can total the money columns without totalling percentages into
them.

**A percent is not money.** `charges.percent` and `taxes.rate` are stored
FRACTIONS (0.015 = 1.5%); they export as the stored string, unrounded and
unscaled. Rounding them to 2dp would turn 0.015 into 0.02 — a 33% rate change
performed by a CSV writer.
"""

import json
from collections.abc import Mapping
from typing import Any

from apps.rating import selectors
from apps.tenancy import exports as export_kernel
from apps.tenancy.exports import ExportColumn, ExportResource

# The five selectors below take BE-05's ListParams directly, so they need no
# adapter: the export hands each one the list endpoint's own parsed object.


def _json_cell(key: str):
    """A stored JSON payload, written as canonical JSON.

    The History screen renders before/after as a diff drawer; a CSV cannot, and
    a Python repr would not round-trip. Sorted keys make the cell stable across
    runs, which is what a compliance file needs (BR-RAT-037 / 7-year
    reproducibility per BR-RAT-017).
    """

    def read(row: Mapping[str, Any]) -> Any:
        value = row.get(key)
        return None if value is None else json.dumps(value, sort_keys=True, default=str)

    return read


def _jurisdiction(field: str):
    def read(row: Mapping[str, Any]) -> Any:
        block = row.get("jurisdiction") or {}
        return block.get(field)

    return read


def _schedule_names(row: Mapping[str, Any]) -> list[str]:
    return [entry.get("tariff_name") or "" for entry in (row.get("rate_schedules") or [])]


def _absent(_row: Mapping[str, Any]) -> None:
    """A capability column with no field behind it. Present and EMPTY — hiding
    it would hide the gap (the same disposition the S9 History screen already
    renders for "Published by")."""
    return None


PLANS = ExportResource(
    name="plans",
    slug="plans",
    module="rating",
    select=selectors.plan_list,
    serialize=None,  # plan_list already serves the row dicts
    money=True,
    columns=(
        # EP-RAT-01 S9 Plans row: Plan · Services included · Rate schedules ·
        # Base charges · Accounts · Status.
        ExportColumn("plan", "name"),
        ExportColumn("services", "services", export_kernel.LIST),
        ExportColumn("rate_schedules", _schedule_names, export_kernel.LIST),
        # BR-RAT-027: the DERIVED Σ of the plan's per-service base charges.
        ExportColumn("base_charges", "base_charges", export_kernel.MONEY),
        ExportColumn("accounts", "accounts", export_kernel.NUMBER),
        ExportColumn("status", "status"),
    ),
)

CHARGES = ExportResource(
    name="charges",
    slug="charge-codes",
    module="rating",
    select=selectors.charge_list,
    serialize=None,
    money=True,
    columns=(
        # EP-RAT-03 S9 Charge codes row: Code · Description · Type · Service ·
        # Amount · GL account — with Amount split by its rule (see the docstring).
        ExportColumn("code", "code"),
        ExportColumn("description", "name"),
        ExportColumn("type", "charge_type"),
        ExportColumn("service", "service"),
        ExportColumn("amount_rule", "amount_rule"),
        ExportColumn("amount", "amount", export_kernel.MONEY),
        # ⚠ **STAYS `NUMBER`, AND I TRIED TO CHANGE IT AND WAS WRONG — OQ-621.**
        # DEF-1123 said IS-9 had no PERCENT kind and that a percentage therefore
        # exported against hard rule 2's display-two. That reasoning does not
        # survive contact with this column: `charges.percent` stores a
        # **FRACTION** (`0.015000` = one and a half percent), not percentage
        # POINTS, and `test_be_list_export.py` says so in the assertion itself —
        # *"A percent is a stored FRACTION, not money: 2dp would make 0.015 →
        # 0.02"*. Quantizing it to two places does not round it, it DESTROYS it.
        #
        # ⚠ **AND THE REAL GAP IS BIGGER AND IS NOT OURS TO CLOSE.** The SCREEN
        # renders this same field through `selectors._display_percent`, which
        # multiplies by a hundred: a clerk reads **`1.50%`** where this file
        # writes `0.015000`. So the file and the screen disagree about the
        # UNIT, not merely the precision — and OQ-620(b) ruled on precision
        # (*"two decimals, like the screen"*), which does not authorise
        # rescaling a column by 100 in a file somebody's spreadsheet already
        # parses. Asked as **OQ-621** rather than taken here.
        ExportColumn("percent", "percent", export_kernel.NUMBER),
        ExportColumn("min_amount", "min_amount", export_kernel.MONEY),
        ExportColumn("gl_account_id", "gl_account_id"),
    ),
)

TAXES = ExportResource(
    name="taxes",
    slug="taxes",
    module="rating",
    select=selectors.tax_list,
    serialize=None,
    money=True,
    columns=(
        # EP-RAT-03 S9 Taxes & fees row: Jurisdiction · Applies to · Rate ·
        # Remittance · GL account. "Jurisdiction" is the identity column on the
        # screen and renders the tax's own name over its jurisdiction, so both
        # travel, plus the authority and level the cell shows beneath them.
        ExportColumn("name", "name"),
        ExportColumn("jurisdiction", _jurisdiction("name")),
        ExportColumn("authority", _jurisdiction("authority")),
        ExportColumn("level", _jurisdiction("level")),
        ExportColumn("applies_to_services", "applies_to_services", export_kernel.LIST),
        ExportColumn("rate_kind", "kind"),
        # ⚠ **STAYS `NUMBER` ON PURPOSE — THIS IS THE COLUMN OQ-620(b)'s OPEN
        # HALF IS ABOUT, AND IT IS NOT GUESSED HERE.** A tax `rate` is a RATE,
        # and OQ-620(a) ruled a rate displays FOUR decimals with its zeros KEPT
        # (`0.1420`). OQ-620(b) then ruled a CSV shows *"two decimals, like the
        # screen"* — but after (a) the screen shows three precisions, so that
        # sentence no longer names one number for this cell. The recorded
        # reading is that each kind follows its own screen rule in the file
        # too, which would make this `0.1420`; it is with the PO for one line
        # of confirmation. Writing `0.14` here would export a rate that cannot
        # reproduce the line it priced — the exact hazard (a) exists to
        # prevent — so this column is left AS SERVED, visibly, until the answer
        # comes back. See `apps/tenancy/exports.py`'s kind table for the whole
        # argument and for the composer to delegate to when it does.
        ExportColumn("rate", "rate", export_kernel.NUMBER),
        ExportColumn("flat_amount", "flat_amount", export_kernel.MONEY),
        ExportColumn("per_unit_amount", "per_unit_amount", export_kernel.MONEY),
        ExportColumn("per_unit_uom", "per_unit_uom"),
        ExportColumn("remittance", "filing_frequency"),
        ExportColumn("gl_account_id", "liability_gl_account_id"),
    ),
)

RATE_SCHEDULES = ExportResource(
    name="rate-schedules",
    slug="rate-schedules",
    module="rating",
    select=selectors.schedule_list,
    serialize=None,  # schedule_list already serves the row dicts
    # A rate schedule IS the pricing, so this is the most money-bearing list of
    # the five even though not one of its COLUMNS is an amount — the amounts
    # live in the versions underneath. BR-SHL-016's audit row is about who took
    # a copy of the tenant's pricing, not about whether a `$` was printed.
    money=True,
    columns=(
        # r10 line 764's own nine headers, in its own order (DEF-441). The tab
        # was excused from an export because EP-RAT-02's matrix called it a card
        # grid; the matrix was wrong about the layout, and the export went with
        # the layout.
        ExportColumn("schedule", "name"),
        ExportColumn("service", "service"),
        ExportColumn("structure", "structure"),
        # Counts, not money: written as served (IS-9 NUMBER).
        ExportColumn("sizes", "size_count", export_kernel.NUMBER),
        # The season LABELS, not their count — a CSV reader can count a list and
        # cannot recover "Summer | Winter" from the number 2.
        ExportColumn("seasons", "season_labels", export_kernel.LIST),
        ExportColumn("plans", "used_by_plans", export_kernel.NUMBER),
        ExportColumn("accounts", "applied_to_accounts", export_kernel.NUMBER),
        # IS-11 keeps every exported date ISO-8601 whatever the tenant's screen
        # format is — so this column reads 2026-01-01 where the screen reads
        # what BR-SHL-023 formats.
        ExportColumn("effective", "effective_from", export_kernel.DATE),
        ExportColumn("status", "status"),
    ),
)

RATE_CHANGES = ExportResource(
    name="rate-changes",
    slug="rate-change-history",
    module="rating",
    select=selectors.history_list,
    serialize=None,
    money=True,
    default_dir="desc",  # the capability matrix: changed_at DESC, newest first
    # An append-only event log, like S61's trail — the filename says so instead
    # of naming a money date basis the log does not have (BR-REP-001).
    basis="event-time",
    period="full-log",
    columns=(
        # EP-RAT-04 S9 History row: When · Entity · Change (before → after) ·
        # Reason · Actor · Published by · Batch.
        ExportColumn("changed_at", "changed_at", export_kernel.TIMESTAMP),
        ExportColumn("entity_type", "entity_type"),
        ExportColumn("entity_id", "entity_id"),
        ExportColumn("entity_name", "entity_name"),
        ExportColumn("change_before", _json_cell("before")),
        ExportColumn("change_after", _json_cell("after")),
        ExportColumn("reason", "reason"),
        ExportColumn("actor_user_id", "actor_user_id"),
        # GAP: the matrix names a "Published by" column, but `rate_change_log`
        # stores ONE actor and no separate publisher (r5 #14). Present-and-empty
        # is what the S9 screen already renders; repeating the actor under a
        # second heading would read as two people having touched the change.
        ExportColumn("published_by", _absent),
        ExportColumn("batch_id", "batch_id"),
    ),
)


def register() -> None:
    """Called once from RatingConfig.ready(). Each resource inherits the LIST
    endpoint's own BR-SHL-011 vocabulary, so a sort or filter the S9 tab honors
    is honored by its export and one it ignores is ignored here too."""
    from dataclasses import replace

    for resource, sorts, default_sort, filters in (
        (PLANS, selectors.PLAN_SORTS, selectors.PLAN_DEFAULT_SORT, selectors.PLAN_FILTERS),
        (
            RATE_SCHEDULES,
            selectors.SCHEDULE_SORTS,
            selectors.SCHEDULE_DEFAULT_SORT,
            selectors.SCHEDULE_FILTERS,
        ),
        (CHARGES, selectors.CHARGE_SORTS, selectors.CHARGE_DEFAULT_SORT, selectors.CHARGE_FILTERS),
        (TAXES, selectors.TAX_SORTS, selectors.TAX_DEFAULT_SORT, selectors.TAX_FILTERS),
        (
            RATE_CHANGES,
            selectors.HISTORY_SORTS,
            selectors.HISTORY_DEFAULT_SORT,
            selectors.HISTORY_FILTERS,
        ),
    ):
        export_kernel.register_export_resource(
            replace(resource, sorts=sorts, default_sort=default_sort, filters=filters)
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-001@6304a38 (EP-RAT-01 lead story — hash = sha256/7 of the source epic; co-packets US-RAT-008/009@7d1a8ef · US-RAT-010@f69a661)
# generated: 2026-08-10 by story-coder v1 (list-export lane — the four EP-RAT capability rows that declared CSV with no route, reported by the Plans & Rates lane as finding (d)) · AMENDED 2026-08-21 by the DEF-441 lane (a FIFTH resource, `rate-schedules`. It had no export because EP-RAT-02's capability row called the S9 tab a card grid and excused it from the table capabilities; r10 line 764 draws a nine-column table, so the export follows the layout. money=True — its nine columns hold no amount at all, and a copy of a tenant's whole pricing structure is exactly the event BR-SHL-016's audit row exists for)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — registration only; the resource is POST /exports) E=deferred(the four S9 Download buttons are the frontend half of this lane) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F on apps/core/config — the bar the baseline passes) black✔(this lane's 13 files; 32 pre-existing unformatted files are the repo baseline, untouched) py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped (unchanged) · migrate from empty✔ makemigrations --check --dry-run clean✔ (this lane adds NO migration) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) · frontend tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · mypy NOT INSTALLED in this environment (recorded, not skipped silently)
# exceptions: the Amount cell (charges, BR-RAT-041) and the Rate cell (taxes, BR-RAT-036) each render ONE column whose UNIT depends on a rule field; IS-9 gives a money column exactly one meaning, so each exports as its rule plus the fields that rule uses, one kind per column — REPORTED as a deliberate departure from a single ratified column name · percents (`charges.percent`, `taxes.rate`) are stored FRACTIONS and export unrounded and unscaled: 2dp rounding would turn 0.015 into 0.02 · before/after export as canonical sorted JSON — a CSV cannot render the S9 diff drawer, and a Python repr would not round-trip · "Published by" has no column in `rate_change_log` (one actor, no publisher — r5 #14): present-and-empty, the same disposition the S9 screen renders · all FIVE exports write an `audit_log` row (BR-SHL-016 money tables) · DEF-441: the rate-schedules `seasons` column exports the season LABELS as an IS-9 LIST rather than the count the screen may render, because a CSV reader can count a list and cannot recover "Summer | Winter" from the number 2; `effective` exports ISO-8601 per IS-11 whatever the tenant's screen format is · no money arithmetic occurs in this file — every amount is the server's own string, rendered at display precision by the shared IS-9 writer
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
