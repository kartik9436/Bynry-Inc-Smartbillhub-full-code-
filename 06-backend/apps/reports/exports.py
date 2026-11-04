# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-003 (IS-11 downloads: CSV always, filename contract, the
#           50k guard and the money-export audit row)   Screens: S46
# Rules:    BR-REP-018 (every report download follows IS-11: CSV always + PDF
#           where layout matters; NO XLSX v1; strict CSV contract — snake_case
#           headers, plain 2dp money, ISO dates, no metadata rows, context in
#           the filename; generated files retained 3 days) · BR-REP-001 (the
#           basis rides in the `{basis}` filename segment) · BR-SHL-016 /
#           BR-SHL-029 (server-side, streamed under RLS, >50,000 rows refused,
#           money exports write `audit_log`) · CLAUDE.md rule 7
# Tests:    06-backend/tests/test_us_rep_003_downloads.py
# Impacts:  apps/reports/apps.py registers these at startup ·
#           apps/tenancy/exports.py (the kernel that writes the bytes) ·
#           apps/tenancy/services.request_list_export (cap + audit + enqueue)
# ───────────────────────────────────────────────────────
"""IS-11 downloads for the four report viewers — ONE pipeline, not a second one.

US-REP-003 asks for CSV on every report, under the guards BR-SHL-016 names: a
server-side stream under the caller's RLS, a hard refusal over 50,000 rows with
no partial file, and an `audit_log` row for a money-bearing export.

**Every one of those already exists**, in `apps/tenancy/exports.py` and
`apps/tenancy/services.request_list_export`, serving nine lists and the S61
audit export. So this module registers the four reports as EXPORT RESOURCES
rather than writing a second CSV writer — hard-won law 5, generalised: one
generated artifact, one implementation. A second export path would be a second
filename grammar, a second cap check and a second audit row, and the three would
drift within a week.

What a resource has to supply is small and is all this file does:

    slug     the `{report}` filename segment          (`ar-aging`)
    basis    BR-REP-001's `{basis}` segment           (`posting` / `clearing`)
    select   the caller's params → the report's ROWS  (the same read model S46
             renders, so the file and the screen cannot disagree)
    columns  the stable snake_case header, documented HERE and nowhere else

════════════════════════════════════════════════════════════════════════════
THE FILENAME, AND WHY THE BASIS SEGMENT IS NOT DECORATION
════════════════════════════════════════════════════════════════════════════
IS-11: `{tenant}_{report}_{period}_{basis}_{generated}.csv`, e.g.
`brazos-bend_ar-aging_2026-07_posting_20260805T1014.csv`. US-REP-003 TC-3 makes
a money file missing its basis segment a FAILURE, and the reason is the whole of
BR-REP-001: two files of the same month, one on the posting basis and one on the
clearing basis, hold different money and are both correct. A bookkeeper holding
them side by side has nothing but the filename to tell them apart.

════════════════════════════════════════════════════════════════════════════
WHAT IS NOT HERE — AND IS NOT STUBBED, BECAUSE A STUB IS A PROMISE
════════════════════════════════════════════════════════════════════════════
  · **PDF.** BR-REP-018 asks for a PDF skeleton (letterhead, filters echoed,
    basis label, generated-by, page X/Y, totals footer) *where layout matters*.
    This deployment has no PDF renderer of any kind — no library is declared in
    `pyproject.toml` and nothing anywhere emits one. `DownloadButton` therefore
    offers CSV only (its `pdf` prop is not passed), which is the control
    behaving correctly rather than a format hidden: IS-11 says CSV ALWAYS and
    PDF where layout matters, and one of those two is true today.
  · **XLSX.** Does not exist and must not: IS-11 corrects A14's "Excel" mention,
    and `DownloadButton` has no prop that could ask for one.
  · **A stored run row.** `report_runs` has no B2 anchoring (pack report R-1,
    DDL 🔒), so S45's history is not built. The job record IS the run record
    today — `GET /jobs/{id}` carries who asked, what for and the artifact — and
    the 3-day retention IS the kernel's `ARTIFACT_RETENTION_DAYS`.
"""

from __future__ import annotations

from typing import Any

from apps.tenancy import exports as export_kernel

from . import additivity, catalog, runner

#: `P6.11`'s three keys. They are spelled from `reports/0003_seed_catalogue.py`
#: rather than added to `catalog.py`, which names only the handful of reports
#: that predate the definitions table.
KEY_ACCESS_REVIEW = "access_review"
KEY_READ_IMPORT_LOG = "read_import_log"
KEY_ACCOUNT_ACTIVITY = "account_activity"
#: `P6.11` wave 2 (lane REP-P6-W2).
KEY_DISCONNECT_RECONNECT = "disconnect_reconnect"
#: `P6.11` wave 3 (lane REP-P6-W3) — `DEF-REP-6937`.
KEY_TREND_PACK = "trend_pack"
#: `P6.11` wave 4 (lane REP-P6-W4).
KEY_BILL_RUN_READINESS = "bill_run_readiness"
KEY_PLANS_AND_DISCOUNTS = "plans_and_discounts"
#: `DEF-REP-7053` — R24, the account's running record. Spelled from
#: `reports/0003_seed_catalogue.py` and `apps/reports/statement.py`, never a
#: second literal.
KEY_STATEMENT = "statement"
#: `CR-179-BRC10` — Rate Impact. Spelled from `apps/reports/rate_impact.py`.
KEY_RATE_IMPACT = "rate_impact"
#: `CR-184-BRC10` — Receivables over 90 days by service. Spelled from
#: `apps/reports/receivables_by_service.py`.
KEY_RECEIVABLES_OVER_90 = "receivables_over_90_by_service"
#: `CR-185-BRC10` — the Owner summary. Spelled from `apps/reports/owner_summary.py`.
KEY_OWNER_SUMMARY = "owner_summary"

#: IS-11's `{report}` segment for each key. Hyphenated, because a filename is a
#: DISPLAY artifact and the API key is a CONTRACT — DEF-131 is what happens when
#: one constant serves both purposes (the hyphenated spelling silently became
#: the API key and every request 422'd for a day).
SLUGS: dict[str, str] = {
    catalog.KEY_AR_AGING: "ar-aging",
    catalog.KEY_BILLING_REGISTER: "billing-register",
    catalog.KEY_REVENUE_BY_SERVICE: "revenue-by-service-rate",
    catalog.KEY_PAYMENTS_BY_METHOD: "payments-by-method",
    # ── `P6.11` · the three joining reads ──────────────────────────────────
    # ⚠ **THEY ARE REGISTERED BECAUSE THE DOWNLOAD BUTTON WAS ALREADY THERE.**
    # `ReportViewerPage` enables the export icon whenever a report renders, so
    # the moment R36, R32 and R23 stopped refusing, three live controls started
    # posting a `resource` this module did not hold and the server answered
    # **404**. Measured through the signed-in browser, not inferred: an
    # unauthenticated `curl` answers 404 for every resource including a
    # registered one, and a probe that cannot tell those apart proves nothing.
    # That is hard-won law 2's mirror — a live screen behind a dead control —
    # and it is closed in the same commit that could have created it.
    KEY_ACCESS_REVIEW: "access-review",
    KEY_READ_IMPORT_LOG: "read-import-log",
    KEY_ACCOUNT_ACTIVITY: "account-activity",
    # ── `P6.11` wave 2 · the same live-Download-button reasoning ───────────
    KEY_DISCONNECT_RECONNECT: "disconnect-reconnect",
    # ── `P6.11` wave 3 · and a THIRD time, because it has now been the cost
    # of turning a report on twice running. `ReportViewerPage` enables the
    # export icon the moment a report RENDERS, so the commit that stops R43
    # refusing is the commit that puts a live Download button over a 404
    # unless this line lands with it.
    KEY_TREND_PACK: "trend-pack",
    # ── `P6.11` wave 4 · and a FOURTH time. `ReportViewerPage` enables the
    # export icon the moment a report RENDERS, so the commit that stops R4
    # refusing is the commit that puts a live Download button over a 404
    # unless this line lands with it.
    KEY_BILL_RUN_READINESS: "bill-run-readiness",
    KEY_PLANS_AND_DISCOUNTS: "plans-and-discounts",
    # ── `DEF-REP-7053` · THE EXPORT WAS BUILT AND NOT WIRED ────────────────
    # `statement_stream` has been in `MODULE_STREAMS` since `P2.8`, measured
    # yielding every row of the window, and no clerk could reach it: the
    # viewer draws Download only where `exportable` is true, `exportable` asks
    # the export registry, and the registry had never heard of this report. So
    # the whole right-hand path of §8.2 existed and no door opened onto it —
    # hard-won law 2 in its original direction, on the one report that is
    # printed and posted more than any other.
    KEY_STATEMENT: "statement",
    # ── `CR-179-BRC10` · registered WITH the report, for the reason the four
    # blocks above give: the viewer enables Download the moment it renders.
    KEY_RATE_IMPACT: "rate-impact",
    # `CR-184-BRC10` — registered WITH the report, for the same reason.
    KEY_RECEIVABLES_OVER_90: "receivables-over-90-by-service",
    # ── `CR-185-BRC10` · registered WITH the report, for the same reason.
    KEY_OWNER_SUMMARY: "owner-summary",
}


def _rows_for(key: str, params: Any, *, whole: bool = False) -> list[dict[str, Any]]:
    """The report's own rows, from the SAME read model S46 renders.

    A `ListParams` arrives (the kernel's contract) and its `filters` mapping
    carries `from`/`to`/`bill_type`/`purpose`/`class` exactly as the viewer's
    query string does — so an exported file is the screen's own report, not an
    approximation of it re-derived under different defaults.

    ⚠ **IT GOES THROUGH `apps/reports/runner.run()` AND SO DOES THE VIEWER
    (`P0.5`).** Until 2026-09-26 this function reached into the queries dispatch
    table itself and `apps/reports/api.py` reached into it separately, with its own
    defaults — two routes to the same numbers, kept in agreement by somebody
    remembering. One function is what makes "the file is the screen's own
    report" a property of the code rather than a promise in a docstring.
    """
    return runner.rows_for(key, dict(params.filters), whole=whole)


def _detail_rows(params: Any) -> list[dict[str, Any]]:
    """Payments by method exports the DETAIL rows, not the four summary lines.

    A four-row file is not a download anybody needs: the summary is on screen
    and fits in a glance. US-REP-007's own capability row spells the detail
    columns out — Date · Account · Method · Purpose · Amount — and BR-PAY-021
    adds the second date, because a clearing-basis file whose reader cannot see
    the posting date cannot be reconciled against a bank statement.

    ⚠ **IT GOES THROUGH THE RUNNER TOO (`P0.5`).** It reaches for a different
    KEY of the same payload — `details` rather than `rows` — which is a second
    QUESTION and must not become a second ROUTE. Calling
    `queries.payments_by_method` directly here would leave one call site with
    its own defaults beside the one the screen uses, which is the exact fault
    this task exists to remove, one key along.
    """
    return list(runner.run(catalog.KEY_PAYMENTS_BY_METHOD, dict(params.filters))
                .payload.get("details", ()))


def _footer_for(key: str) -> Any:
    """`P2.22` — the ONE row appended under the data, or `None`.

    ⚠ **`None` IS THE COMMON CASE AND THAT IS THE POINT.** A file whose totals
    are all lawful gets no footer and is byte-identical to the file it wrote
    yesterday, which is what keeps `IS-11`'s *"no metadata rows"* intact
    everywhere it is currently true. The only files that gain a row are the
    ones whose alternative is an auditor reading a figure that means nothing —
    and the tension between those two signed statements is `OQ-REP-12740`, put
    to the PO rather than decided here (hard-won law 13).

    ⚠ **IT RUNS THE REPORT THROUGH `runner.run`, THE SAME FUNCTION THE SCREEN
    USES** (`P0.5`). Rebuilding the totals here under this file's own defaults
    is exactly the fault `P0.5` was written to remove: the file would refuse a
    total the screen served, or serve one the screen refused, and both would
    look correct.
    """

    def build(params: Any, chosen: Any) -> Any:
        try:
            served = runner.run(key, dict(params.filters), whole=True).payload
        except Exception:  # pragma: no cover — a refusal is never a broken file
            return None
        totals = served.get("totals") or {}
        if not additivity.has_refusal(totals):
            return None
        return additivity.csv_footer_row(
            columns=tuple(column.name for column in chosen),
            totals=totals,
            label="Total",
        )

    return build


def _usage_cell(row: dict[str, Any]) -> str:
    """CLAUDE.md rule 3 in one CSV cell: every quantity WITH its unit.

    A bill measured in two units yields `684 kWh|26.24 kgal` — the kernel's own
    multi-value separator — and never a bare summed number, which would add kWh
    to kgal.
    """
    return export_kernel.MULTI_VALUE_SEPARATOR.join(
        f"{entry['quantity']} {entry['unit']}" for entry in row.get("usage") or ()
    )


AR_AGING = export_kernel.ExportResource(
    name=catalog.KEY_AR_AGING,
    footer=_footer_for(catalog.KEY_AR_AGING),
    slug=SLUGS[catalog.KEY_AR_AGING],
    module="reports",
    # ⚠ **`per="all"` — THE WHOLE FILTERED SET, NOT PAGE ONE (`P2.21`).** The
    # ageing began paging at fifty on 2026-09-24; without this the file would
    # have held fifty rows of a 40,000-row receivable and looked entirely
    # valid. The filters still come from the screen, so the file is the
    # screen's own report and not an approximation re-derived under other
    # defaults.
    select=lambda params: _rows_for(catalog.KEY_AR_AGING, params, whole=True),
    columns=(
        # US-REP-003 TC-1's documented set, verbatim.
        export_kernel.ExportColumn("account_no", "account_no"),
        export_kernel.ExportColumn("customer", "customer_name"),
        export_kernel.ExportColumn("class", "account_class"),
        export_kernel.ExportColumn("current", "current", export_kernel.MONEY),
        # `d1_30` is new with `P2.21` — `BR-REP-030`'s fifth band, which this
        # report folded into `current` until 2026-09-24 (`DEF-REP-6659`).
        export_kernel.ExportColumn("d1_30", "d1_30", export_kernel.MONEY),
        export_kernel.ExportColumn("d31_60", "d31_60", export_kernel.MONEY),
        export_kernel.ExportColumn("d61_90", "d61_90", export_kernel.MONEY),
        export_kernel.ExportColumn("d90_plus", "d90_plus", export_kernel.MONEY),
        export_kernel.ExportColumn("total", "total", export_kernel.MONEY),
        # BR-PAY-032. Empty when nothing is past due — a 0 would read as "due
        # today", which is a different and false statement.
        export_kernel.ExportColumn("days_late", "days_late", export_kernel.NUMBER),
    ),
    # `P2.22` — see `_footer_for`. `None` unless a total refused itself.
    money=True,
    basis="posting",
    period="as-of",
    filters=("from", "to", "class"),
)

BILLING_REGISTER = export_kernel.ExportResource(
    name=catalog.KEY_BILLING_REGISTER,
    footer=_footer_for(catalog.KEY_BILLING_REGISTER),
    slug=SLUGS[catalog.KEY_BILLING_REGISTER],
    module="reports",
    # ⚠ **`whole=True` IS LOAD-BEARING SINCE THE REGISTER STARTED PAGING**
    # (`P2.12`). Without it this resource would write the SCREEN's page —
    # fifty rows — into a file that looks perfectly valid, which is the
    # reason `AR_AGING` above carries it.
    select=lambda params: _rows_for(catalog.KEY_BILLING_REGISTER, params, whole=True),
    columns=(
        export_kernel.ExportColumn("bill_no", "invoice_no"),
        export_kernel.ExportColumn("bill_type", "bill_type"),
        export_kernel.ExportColumn("account_no", "account_no"),
        export_kernel.ExportColumn("customer", "customer_name"),
        export_kernel.ExportColumn("cycle", "cycle_label"),
        export_kernel.ExportColumn("issued_on", "issued_on", export_kernel.DATE),
        export_kernel.ExportColumn("services", "services", export_kernel.LIST),
        export_kernel.ExportColumn("usage", _usage_cell),
        export_kernel.ExportColumn("amount", "amount", export_kernel.MONEY),
        export_kernel.ExportColumn("flag", "flag"),
    ),
    # `P2.22` — see `_footer_for`. `None` unless a total refused itself.
    money=True,
    basis="posting",
    period="window",
    filters=("from", "to", "bill_type", "service"),
)

REVENUE_BY_SERVICE = export_kernel.ExportResource(
    name=catalog.KEY_REVENUE_BY_SERVICE,
    footer=_footer_for(catalog.KEY_REVENUE_BY_SERVICE),
    slug=SLUGS[catalog.KEY_REVENUE_BY_SERVICE],
    module="reports",
    select=lambda params: _rows_for(catalog.KEY_REVENUE_BY_SERVICE, params),
    columns=(
        export_kernel.ExportColumn("service", "service_name"),
        export_kernel.ExportColumn("rate_schedule", "tariff_name"),
        export_kernel.ExportColumn("accounts", "accounts", export_kernel.NUMBER),
        export_kernel.ExportColumn("usage_revenue", "usage_revenue", export_kernel.MONEY),
        export_kernel.ExportColumn("base", "base", export_kernel.MONEY),
        export_kernel.ExportColumn("tax", "tax", export_kernel.MONEY),
        export_kernel.ExportColumn("total", "total", export_kernel.MONEY),
    ),
    # `P2.22` — see `_footer_for`. `None` unless a total refused itself.
    money=True,
    basis="posting",
    period="window",
    filters=("from", "to"),
)

PAYMENTS_BY_METHOD = export_kernel.ExportResource(
    name=catalog.KEY_PAYMENTS_BY_METHOD,
    footer=_footer_for(catalog.KEY_PAYMENTS_BY_METHOD),
    slug=SLUGS[catalog.KEY_PAYMENTS_BY_METHOD],
    module="reports",
    select=_detail_rows,
    columns=(
        export_kernel.ExportColumn("posted_on", "posted_on", export_kernel.DATE),
        export_kernel.ExportColumn("cleared_on", "cleared_on", export_kernel.DATE),
        export_kernel.ExportColumn("payment_no", "payment_no"),
        export_kernel.ExportColumn("account_no", "account_no"),
        export_kernel.ExportColumn("customer", "customer_name"),
        export_kernel.ExportColumn("method", "method_name"),
        export_kernel.ExportColumn("purpose", "purpose"),
        export_kernel.ExportColumn("confirmation", "confirmation"),
        export_kernel.ExportColumn("amount", "amount", export_kernel.MONEY),
    ),
    # `P2.22` — see `_footer_for`. `None` unless a total refused itself.
    money=True,
    # BR-REP-001 — the file names its basis. It was `clearing` until the PO
    # ruling of 2026-10-21 moved Payments by method to the POSTING date
    # (`DEF-PAY-10321`): a payment counts the day it was taken and applied.
    basis="posting",
    period="window",
    filters=("from", "to", "purpose"),
)



# ── `P6.11` · THE THREE JOINING READS ───────────────────────────────────────
#
# ⚠ **`whole=True` ON ALL THREE, AND IT IS LOAD-BEARING.** `P2.12`'s own trap:
# `_rows_for`'s flag defaults to False, and the moment a report starts paging,
# an export without it writes the screen's fifty rows into a file that looks
# entirely valid — no error, no gate, no test. All three of these page from
# their first commit, so there is no version of them for which False is right.
#
# ⚠ **NO `money=True` ON ANY OF THEM.** None serves a money column: R36 is
# people, R32 is counts of file rows and R23 is dates and names. `money=True`
# would put a currency segment in the filename of a file with no money in it.

ACCESS_REVIEW = export_kernel.ExportResource(
    name=KEY_ACCESS_REVIEW,
    footer=_footer_for(KEY_ACCESS_REVIEW),
    slug=SLUGS[KEY_ACCESS_REVIEW],
    module="reports",
    select=lambda params: _rows_for(KEY_ACCESS_REVIEW, params, whole=True),
    columns=(
        export_kernel.ExportColumn("user", "user_name"),
        export_kernel.ExportColumn("email", "user_email"),
        export_kernel.ExportColumn("role", "role_name"),
        export_kernel.ExportColumn("added_on", "added_on", export_kernel.DATE),
        export_kernel.ExportColumn("added_by", "added_by"),
        # ⚠ **NAMED `last_active_at` IN THE FILE TOO.** The screen's header is
        # `Last active` because that is what the value is; a CSV column called
        # `last_sign_in` over the same value would put the wrong name on the
        # machine-readable copy, which outlives the screen.
        export_kernel.ExportColumn("last_active_at", "last_active_at", export_kernel.TIMESTAMP),
        # ⚠ **`BOOLEAN`, NOT THE SCREEN'S `Yes`/`No`.** The kernel's own comment
        # on this kind: *"true / false — machine-parseable, never Yes/No copy"*.
        # A file is read by a spreadsheet as well as a person.
        export_kernel.ExportColumn(
            "can_approve_money", "can_approve_money", export_kernel.BOOLEAN
        ),
        export_kernel.ExportColumn("status", "status"),
    ),
    sorts=("user", "role", "added_on", "last_active", "status"),
    default_sort="user",
    filters=("as_of", "role", "status"),
    basis="as-at",
    period="as-of",
)

READ_IMPORT_LOG = export_kernel.ExportResource(
    name=KEY_READ_IMPORT_LOG,
    footer=_footer_for(KEY_READ_IMPORT_LOG),
    slug=SLUGS[KEY_READ_IMPORT_LOG],
    module="reports",
    select=lambda params: _rows_for(KEY_READ_IMPORT_LOG, params, whole=True),
    columns=(
        export_kernel.ExportColumn("imported_at", "imported_at", export_kernel.TIMESTAMP),
        export_kernel.ExportColumn("file", "file_name"),
        export_kernel.ExportColumn("source", "source_kind"),
        export_kernel.ExportColumn("method", "source_detail"),
        export_kernel.ExportColumn("rows", "rows", export_kernel.NUMBER),
        export_kernel.ExportColumn("accepted", "accepted", export_kernel.NUMBER),
        export_kernel.ExportColumn("rejected", "rejected", export_kernel.NUMBER),
        # ⚠ **`warnings` IS IN THE FILE AND NOT ON THE SCREEN.** A warning row
        # is ACCEPTED and carries a flag, so the drawn table folds it into
        # ACCEPTED; a file is where somebody reconciles, and the split has to
        # be recoverable there or the two numbers cannot be told apart again.
        export_kernel.ExportColumn("warnings", "warnings", export_kernel.NUMBER),
        export_kernel.ExportColumn("imported_by", "imported_by"),
        export_kernel.ExportColumn("status", "status"),
    ),
    sorts=("imported_at", "file_name", "source", "rows", "accepted", "rejected", "status"),
    default_sort="imported_at",
    default_dir="desc",
    filters=("from", "to", "source", "result", "status", "cycle", "route"),
    basis="event-time",
    period="range",
)

ACCOUNT_ACTIVITY = export_kernel.ExportResource(
    name=KEY_ACCOUNT_ACTIVITY,
    footer=_footer_for(KEY_ACCOUNT_ACTIVITY),
    slug=SLUGS[KEY_ACCOUNT_ACTIVITY],
    module="reports",
    select=lambda params: _rows_for(KEY_ACCOUNT_ACTIVITY, params, whole=True),
    columns=(
        # ⚠ **BOTH DATES ARE IN THE FILE**, for p060's own reason: a move-in
        # dated 1 October belongs to September's activity and October's census,
        # and a file carrying one of them cannot answer the other question.
        export_kernel.ExportColumn("occurred_at", "occurred_at", export_kernel.TIMESTAMP),
        export_kernel.ExportColumn("account_no", "account_no"),
        export_kernel.ExportColumn("customer", "customer_name"),
        export_kernel.ExportColumn("event", "event"),
        export_kernel.ExportColumn("premises", "premises_address"),
        export_kernel.ExportColumn("by", "actor"),
        export_kernel.ExportColumn("effective_on", "effective_on", export_kernel.DATE),
        export_kernel.ExportColumn("reference", "reference"),
    ),
    sorts=("occurred_at", "effective_on", "account_no", "event"),
    default_sort="occurred_at",
    default_dir="desc",
    filters=("from", "to", "event", "account"),
    basis="event-time",
    period="range",
)


DISCONNECT_RECONNECT = export_kernel.ExportResource(
    name=KEY_DISCONNECT_RECONNECT,
    footer=_footer_for(KEY_DISCONNECT_RECONNECT),
    slug=SLUGS[KEY_DISCONNECT_RECONNECT],
    module="reports",
    select=lambda params: _rows_for(KEY_DISCONNECT_RECONNECT, params, whole=True),
    columns=(
        export_kernel.ExportColumn("account_no", "account_no"),
        export_kernel.ExportColumn("customer", "customer_name"),
        export_kernel.ExportColumn("balance", "balance", export_kernel.MONEY),
        export_kernel.ExportColumn("notice_on", "notice_on", export_kernel.DATE),
        export_kernel.ExportColumn("cut_on", "cut_on", export_kernel.DATE),
        # ⚠ **`paid` IS IN THE FILE AND IS ALWAYS EMPTY.** Dropping it would
        # make the file disagree with the screen and with p065, and a reader
        # comparing two exports six months apart would read the column's
        # arrival as new data rather than as a gap that was always there.
        export_kernel.ExportColumn("paid", "paid", export_kernel.MONEY),
        export_kernel.ExportColumn("reconnected_on", "reconnected_on", export_kernel.DATE),
        export_kernel.ExportColumn("status", "status"),
        # Not drawn as a column; in the FILE because `BR-REP-039` puts the
        # earlier cases *underneath* and a file has no underneath.
        export_kernel.ExportColumn("earlier_cases", "earlier_cases"),
    ),
    sorts=("account_no", "balance", "notice_on", "cut_on", "reconnected_on", "status"),
    default_sort="notice_on",
    default_dir="desc",
    filters=("from", "to", "reason", "account"),
    basis="event-time",
    period="range",
    money=True,
)


TREND_PACK = export_kernel.ExportResource(
    name=KEY_TREND_PACK,
    footer=_footer_for(KEY_TREND_PACK),
    slug=SLUGS[KEY_TREND_PACK],
    module="reports",
    select=lambda params: _rows_for(KEY_TREND_PACK, params, whole=True),
    columns=(
        export_kernel.ExportColumn("period", "period"),
        # ⚠ **THE FILE CARRIES THE TWO DATES AND THE SCREEN DRAWS ONE CELL.**
        # `P10` is a fiscal ordinal and means nothing beside another utility's
        # `P10`; a spreadsheet a finance officer sorts or charts needs the
        # window, and a file has no regional formatter to compose it from.
        export_kernel.ExportColumn("period_start", "period_start", export_kernel.DATE),
        export_kernel.ExportColumn("period_end", "period_end", export_kernel.DATE),
        export_kernel.ExportColumn("revenue", "revenue", export_kernel.MONEY),
        # ⚠ **`target` IS IN THE FILE AND IS EMPTY ON EVERY TENANT TODAY**
        # (`BR-REP-034`'s ruled degrade). Dropping it would make the file
        # disagree with p059 and with the screen, and a reader comparing two
        # exports a year apart would read the column's arrival as new data
        # rather than as a figure somebody finally typed.
        export_kernel.ExportColumn("target", "target", export_kernel.MONEY),
        export_kernel.ExportColumn("collected", "collected", export_kernel.MONEY),
        # ⚠ **`QUANTITY` AND NOT `NUMBER` FOR THE TWO RATIOS, AND THERE IS NO
        # `PERCENT` KIND BY DESIGN** — `apps/tenancy/exports.py` records why it
        # was added and taken back out (`OQ-621`): the only other percent column
        # in the product stores a FRACTION, so one kind could not serve both.
        # `NUMBER` is *written as served*, which would put `94.200000` and
        # `14.100000` in the file against hard rule 2's display rule.
        # `QUANTITY` rounds half-up to at most two places and trims, which is
        # p059's own `94.2%` and `14.1 days`.
        export_kernel.ExportColumn("rate", "rate", export_kernel.QUANTITY),
        export_kernel.ExportColumn("dso", "dso", export_kernel.QUANTITY),
        export_kernel.ExportColumn("accounts", "accounts", export_kernel.NUMBER),
        export_kernel.ExportColumn("rebills", "rebills", export_kernel.NUMBER),
    ),
    # ⚠ **NO SORTS, AND THE EMPTY TUPLE IS A STATEMENT.** A trend is read in
    # period order and in no other; offering a sort the read model will not
    # apply is a control over nothing (hard-won law 2's mirror).
    sorts=(),
    default_sort="period",
    default_dir="asc",
    filters=("as_of", "periods"),
    basis="posting",
    period="range",
    money=True,
)


BILL_RUN_READINESS = export_kernel.ExportResource(
    name=KEY_BILL_RUN_READINESS,
    footer=_footer_for(KEY_BILL_RUN_READINESS),
    slug=SLUGS[KEY_BILL_RUN_READINESS],
    module="reports",
    select=lambda params: _rows_for(KEY_BILL_RUN_READINESS, params, whole=True),
    columns=(
        export_kernel.ExportColumn("account", "account"),
        export_kernel.ExportColumn("customer", "customer"),
        # ⚠ **`route` AND `usage` ARE IN THE FILE AND ARE EMPTY ON EVERY ROW**
        # (`BR-REP-060`). Dropping them would make the file disagree with p049
        # and with the screen, and a reader comparing two exports six months
        # apart would read a column's arrival as new data rather than as a gap
        # that was always there — the reasoning R34's `paid` and R43's `target`
        # already carry, for the third time.
        export_kernel.ExportColumn("route", "route"),
        export_kernel.ExportColumn("check", "check"),
        export_kernel.ExportColumn("detail", "detail"),
        export_kernel.ExportColumn("usage", "usage", export_kernel.QUANTITY),
        # Not drawn as a column. In the FILE because *fix and retry now* is what
        # a clerk sorts the twenty minutes before the run by, and a file has no
        # button to grey out.
        export_kernel.ExportColumn("retryable", "retryable"),
    ),
    sorts=("account", "customer", "check", "detail"),
    default_sort="account",
    default_dir="asc",
    # ⚠ **`route` IS NOT A FILTER HERE EITHER, AND THE OMISSION IS THE RULE**
    # (`BR-REP-060`). p049 draws the chip; the column is NULL on every row, so
    # a filter would be a control that cannot work — on the export path, where
    # nobody would see it fail.
    filters=("cycle", "check"),
    basis="posting",
    period="range",
    # No money column at all — R4 lists the accounts that could NOT be drafted.
    money=False,
)


PLANS_AND_DISCOUNTS = export_kernel.ExportResource(
    name=KEY_PLANS_AND_DISCOUNTS,
    footer=_footer_for(KEY_PLANS_AND_DISCOUNTS),
    slug=SLUGS[KEY_PLANS_AND_DISCOUNTS],
    module="reports",
    select=lambda params: _rows_for(KEY_PLANS_AND_DISCOUNTS, params, whole=True),
    columns=(
        export_kernel.ExportColumn("programme", "programme"),
        export_kernel.ExportColumn("account", "account"),
        export_kernel.ExportColumn("since", "since", export_kernel.DATE),
        # ⚠ **TWO TERM COLUMNS IN THE FILE WHERE p061 DRAWS ONE CELL**, and the
        # file is right to split them: a spreadsheet a clerk sorts cannot sort
        # `12 months` against `20%`, and composing one string would put English
        # into a file eleven catalogues would otherwise each write themselves
        # (B14 rule 35).
        export_kernel.ExportColumn("terms_months", "terms_months", export_kernel.NUMBER),
        export_kernel.ExportColumn("terms_percent", "terms_percent", export_kernel.QUANTITY),
        export_kernel.ExportColumn("instalment", "instalment", export_kernel.MONEY),
        # Empty on the level-pay and assistance rows BY RIGHT, not as a gap —
        # p061 draws em-dashes there. In the file so it agrees with the screen.
        export_kernel.ExportColumn("remaining", "remaining", export_kernel.MONEY),
        export_kernel.ExportColumn("status", "status"),
    ),
    sorts=("since", "programme", "account"),
    default_sort="since",
    default_dir="desc",
    filters=("as_of", "programme", "status"),
    basis="as-at",
    period="as-at",
    money=True,
)


STATEMENT = export_kernel.ExportResource(
    name=KEY_STATEMENT,
    footer=_footer_for(KEY_STATEMENT),
    slug=SLUGS[KEY_STATEMENT],
    module="reports",
    # ⚠ **`whole=True`, AND ON THIS REPORT IT IS NOT A PRECAUTION.** The
    # statement has paged from its first commit (`NFR-3`), so there is no
    # version of this resource for which `False` would be right: without it a
    # clerk printing a year of an account's movements would receive the
    # screen's fifty rows in a file that looks entirely valid. `rows_for`
    # reaches `statement_stream` through `runner`, which is the generator §8.2
    # calls the right path — *"the right path never holds a page"*.
    select=lambda params: _rows_for(KEY_STATEMENT, params, whole=True),
    columns=(
        export_kernel.ExportColumn("entry_date", "entry_date", export_kernel.DATE),
        export_kernel.ExportColumn("type", "type"),
        export_kernel.ExportColumn("reference", "reference"),
        export_kernel.ExportColumn("description", "description"),
        # ⚠ **THE UNION OF BOTH SUBJECTS, AND THE TWO UNIT COLUMNS ARE EMPTY
        # ON AN ACCOUNT STATEMENT.** `BR-REP-043` gives the unit subject an
        # `occupant` and an `account` column and gives no other subject either
        # one — a unit outlives its tenants, an account does not. One resource
        # serves every subject because the report is one report; the
        # alternative is a second registration keyed by a run parameter, which
        # is a second filename grammar and a second audit row for one file.
        # R34's `paid`, R43's `target` and R4's `route` each carry the same
        # reasoning: a column that is empty is a column the reader can still
        # tell apart from one that was never offered.
        export_kernel.ExportColumn("occupant", "occupant"),
        export_kernel.ExportColumn("account", "account"),
        export_kernel.ExportColumn("charge", "charge", export_kernel.MONEY),
        export_kernel.ExportColumn("payment", "payment", export_kernel.MONEY),
        export_kernel.ExportColumn(
            "running_balance", "running_balance", export_kernel.MONEY
        ),
    ),
    # ⚠ **NO SORTS, AND THE EMPTY TUPLE IS THE STATEMENT ITSELF.**
    # `ACCOUNT_LEDGER_SORTS` is `()` for the reason a statement cannot be
    # re-ordered at all: the running balance is DEFINED by the row order, so
    # sorting that column does not re-sort it, it destroys it.
    sorts=(),
    default_sort="entry_date",
    default_dir="asc",
    # The run controls a statement is actually about. `subject_id` is what
    # makes the file one account's rather than a tenant's, and it travels in
    # `filters` exactly as it travels in the URL.
    filters=("from", "to", "subject", "subject_id"),
    # BR-REP-001 — the ledger strikes every figure on the BOOK date, and
    # `reports/0007` moved the definition's basis to match. A statement file and
    # a clearing-basis file of the same month hold different money and are both
    # correct; the filename is the only thing that tells a bookkeeper which.
    basis="posting",
    period="window",
    money=True,
)


def _rate_impact_rows(params: Any) -> list[dict[str, Any]]:
    """CR-179-BRC10 — the result's LINES, through `runner.run` like the screen.

    The run's four declared inputs arrive in `filters` exactly as the screen
    sent them — `rows` as ONE JSON string — so the file is the screen's own
    result. Group heads are dropped; each line names its schedule or code.
    """
    from . import rate_impact

    return rate_impact.export_rows(
        runner.run(KEY_RATE_IMPACT, dict(params.filters), whole=True).payload
    )


RATE_IMPACT = export_kernel.ExportResource(
    name=KEY_RATE_IMPACT,
    footer=None,
    slug=SLUGS[KEY_RATE_IMPACT],
    module="reports",
    select=_rate_impact_rows,
    columns=(
        export_kernel.ExportColumn("item", "item_label"),
        export_kernel.ExportColumn("capacity", "capacity"),
        export_kernel.ExportColumn("class", "class"),
        export_kernel.ExportColumn("accounts", "accounts", export_kernel.NUMBER),
        export_kernel.ExportColumn("usage", "usage"),
        export_kernel.ExportColumn("unit", "unit"),
        export_kernel.ExportColumn("items", "items", export_kernel.NUMBER),
        export_kernel.ExportColumn("revenue_now", "revenue_now", export_kernel.MONEY),
        export_kernel.ExportColumn("revenue_proposed", "revenue_proposed", export_kernel.MONEY),
        export_kernel.ExportColumn("change", "change", export_kernel.MONEY),
        export_kernel.ExportColumn("change_pct", "change_pct"),
    ),
    sorts=(),
    default_sort="item",
    default_dir="asc",
    # The viewer's DECLARED inputs (`rate_impact.INPUT_PARAMS`), every one a
    # string — the export's `dict[str, str]` filters carry them unchanged.
    filters=("services", "classes", "months", "rows"),
    basis="event",
    period="range",
    money=True,
)


def _receivables_over_90_rows(params: Any) -> list[dict[str, Any]]:
    """CR-184-BRC10 — the screen's own rows, through `runner.run`."""
    from . import receivables_by_service

    return receivables_by_service.export_rows(
        runner.run(KEY_RECEIVABLES_OVER_90, dict(params.filters), whole=True).payload
    )


RECEIVABLES_OVER_90 = export_kernel.ExportResource(
    name=KEY_RECEIVABLES_OVER_90,
    footer=None,
    slug=SLUGS[KEY_RECEIVABLES_OVER_90],
    module="reports",
    select=_receivables_over_90_rows,
    columns=(
        export_kernel.ExportColumn("service", "service"),
        export_kernel.ExportColumn("charge_class", "charge_class"),
        export_kernel.ExportColumn("debtors", "debtors", export_kernel.NUMBER),
        export_kernel.ExportColumn("d90_plus", "d90_plus", export_kernel.MONEY),
        export_kernel.ExportColumn("share_pct", "share_pct"),
        export_kernel.ExportColumn("total", "total", export_kernel.MONEY),
    ),
    sorts=(),
    default_sort="service",
    default_dir="asc",
    filters=("as_of", "to"),
    basis="posting",
    period="as-of",
    money=True,
)


OWNER_SUMMARY = export_kernel.ExportResource(
    name=KEY_OWNER_SUMMARY,
    footer=None,
    slug=SLUGS[KEY_OWNER_SUMMARY],
    module="reports",
    # `whole=True` — the file is EVERY property of the owner, never the screen's
    # page (`NFR-3`); `rows_for` reaches `owner_summary_stream` through `runner`.
    select=lambda params: _rows_for(KEY_OWNER_SUMMARY, params, whole=True),
    columns=(
        export_kernel.ExportColumn("property", "property"),
        export_kernel.ExportColumn("account", "account"),
        export_kernel.ExportColumn("bills", "bills", export_kernel.NUMBER),
        export_kernel.ExportColumn("empty_units", "empty_units", export_kernel.MONEY),
        export_kernel.ExportColumn("common_areas", "common_areas", export_kernel.MONEY),
        export_kernel.ExportColumn("other_charges", "other_charges", export_kernel.MONEY),
        export_kernel.ExportColumn("total", "total", export_kernel.MONEY),
    ),
    sorts=(),
    default_sort="property",
    default_dir="asc",
    # `subject_id` is what makes the file ONE owner's, and it travels in
    # `filters` exactly as it travels in the URL.
    filters=("from", "to", "period", "subject_id"),
    basis="posting",
    period="window",
    money=True,
)


RESOURCES = (
    AR_AGING,
    BILLING_REGISTER,
    REVENUE_BY_SERVICE,
    PAYMENTS_BY_METHOD,
    # `P6.11` — see the block above for why all three arrive with the download
    # button rather than after it.
    ACCESS_REVIEW,
    READ_IMPORT_LOG,
    ACCOUNT_ACTIVITY,
    # `P6.11` wave 2.
    DISCONNECT_RECONNECT,
    # `P6.11` wave 3 — `DEF-REP-6937`.
    TREND_PACK,
    # `P6.11` wave 4.
    BILL_RUN_READINESS,
    PLANS_AND_DISCOUNTS,
    # `DEF-REP-7053` — built since `P2.8`, reachable from today.
    STATEMENT,
    # `CR-179-BRC10` — Rate Impact, registered with the report itself.
    RATE_IMPACT,
    # `CR-184-BRC10` — Receivables over 90 days by service.
    RECEIVABLES_OVER_90,
    # `CR-185-BRC10` — the Owner summary, registered with the report itself.
    OWNER_SUMMARY,
)


def register() -> None:
    """Called once from `ReportsConfig.ready()`."""
    for resource in RESOURCES:
        export_kernel.register_export_resource(resource)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-REP-003@c6c35b2 (04-docs/05-modules/12-reports/06-epics/EP-REP-01-report-center.md §US-REP-003 · 12-reports/02-business-rules.md BR-REP-001/018 · IS-11 via B9 · apps/tenancy/exports.py, the kernel this rides)
# screens: S46
# generated: 2026-08-16 by story-coder (reports lane); amended 2026-09-28 by lane REP-STMT-SCREEN (`DEF-REP-7053` — the `statement` resource. `statement_stream` had been registered and unreachable since `P2.8`: the viewer draws Download only where `exportable` is true, and `exportable` asks this registry)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `POST /exports {"resource":"ar_aging"}` answered 404 (no such registered resource) before this module was registered. ruff✔ black✔ pytest✔ run_gates✔
# exceptions: (1) NO PDF. BR-REP-018 asks for a PDF skeleton where layout matters and this deployment has no PDF renderer of any kind — none is declared in pyproject.toml and nothing emits one. `DownloadButton` is used WITHOUT its `pdf` prop, so CSV is offered and PDF is not advertised; the gap is stated on screen · (2) NO XLSX, and no code path could produce one (IS-11 corrects A14's "Excel") · (3) NO STORED RUN ROW — `report_runs` has no B2 anchoring (pack report R-1, DDL 🔒), so the JOB record is the run record and the kernel's 3-day artifact retention is BR-REP-018's window · (4) payments-by-method exports the DETAIL rows rather than the four summary lines, per US-REP-007's own capability row
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
