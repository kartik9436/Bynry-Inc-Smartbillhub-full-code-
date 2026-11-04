# ── Trace ──────────────────────────────────────────────
# Change:   P4.1 (Finance blueprint p017) — "seven reports become export
#           resources", so each of 6·2's four groupings downloads and the five
#           refused download buttons in Finance become five working ones.
#           P4.10 — the kernel is tenancy's; Finance REGISTERS against it and
#           invents no second export mechanism.
# Rules:    BR-TEN-031 (the OWNING module supplies the column set, the selector
#           call and the vocabulary) · BR-REP-018 (IS-11: CSV always, strict
#           contract, context in the filename) · BR-REP-001 (every money file
#           LABELS its date basis) · BR-SHL-016 / BR-SHL-029 (server-side,
#           streamed under RLS, capped, money exports write `audit_log`) ·
#           BR-SHL-011 (the export mirrors the screen's OWN request state) ·
#           BR-LED-004 (the dimension extracts) · CLAUDE.md rule 2 (money 4dp
#           stored, 2dp displayed) · rule 3 (a quantity carries its unit) ·
#           rule 7 (every money action writes `audit_log`)
# Tests:    06-backend/tests/test_p4_1_finance_exports.py
# Impacts:  apps/ledger/apps.py registers these at startup ·
#           apps/tenancy/exports.py (the kernel that writes the bytes) ·
#           07-frontend reportsShared.tsx / RemittancePage / GeneralLedgerPage
#           (P4.5 turns their disabled buttons on)
# ───────────────────────────────────────────────────────
"""The seven Finance downloads, registered against the ONE export kernel.

`apps/reports/exports.py` did this for the report viewers on 2026-08-16 and its
argument is quoted rather than restated, because it is the whole design:

    So this module registers the four reports as EXPORT RESOURCES rather than
    writing a second CSV writer — hard-won law 5, generalised: one generated
    artifact, one implementation. A second export path would be a second
    filename grammar, a second cap check and a second audit row, and the three
    would drift within a week.

Seven here, and **every one of them is a read this product already serves**.
Nothing in this file derives a figure. A resource supplies four things and only
four: the filename's `{report}` segment, BR-REP-001's `{basis}`, the SAME read
the screen renders, and the stable snake_case header.

════════════════════════════════════════════════════════════════════════════
WHY SEVEN, AND WHICH SCREEN EACH ONE TURNS ON
════════════════════════════════════════════════════════════════════════════
Five of them are the **five refused downloads** the Finance blueprint counts —
controls that render disabled today with a reason that was true until now:

    trial_balance        6·1/3·1 General ledger    GeneralLedgerPage.tsx:971
    remittance           4·1 By authority          RemittancePage.tsx:484
    account_ledger       S59                       reportsShared ReportDownloads
    by_premises          S60                       reportsShared ReportDownloads
    customer_statement   the statement viewer      reportsShared ReportDownloads

The other two exist so that **each of 6·2's four groupings downloads** (p070
row 3: *"Group by Account · Service · Premises · Tax authority — replaces the
three extract buttons"*):

    export_preview       Group by ACCOUNT       — the trial-balance-shaped
                         preview the send gate reads, GET /finance/export/preview
    revenue_by_service   Group by SERVICE       — GET /finance/export/extracts/service

and `by_premises` + `remittance` above serve the other two groupings, which is
why the count is seven rather than nine: **one resource can back two surfaces
and two resources must not back one.**

⚠ `revenue_by_service` IS NOT `revenue_by_service_rate`. The reports module
registers the latter (its own S46 viewer, grouped by service AND rate schedule,
with an accounts count and a tax column). This one is `apps/ledger`'s dimension
extract — LE-2's usage / base-and-fees / total split off the posted journal.
Two real reports about the same subject, and naming them alike is how a
bookkeeper ends up reconciling one against the other.

════════════════════════════════════════════════════════════════════════════
WHY THE BASIS SEGMENT IS NOT DECORATION — BR-REP-001, quoted by example
════════════════════════════════════════════════════════════════════════════
Every one of these seven is a MONEY file, so every one names its basis and
every one writes `audit_log`. Six are `posting` — they are read off posted
journal lines. **`remittance` is the one that is not**: BR-LED-013 gives each
authority its own remitting basis, which the TENANT chooses per authority, so a
single file can carry a State row on `collected` beside a County row on
`billed`. Labelling the FILE with either one would be false about half of it,
so its `{basis}` segment is `per-authority` and the row itself carries
`remitting_basis` as a column. That is the rule honoured rather than a rule
quietly skipped.

════════════════════════════════════════════════════════════════════════════
A REPORT THAT NEEDS AN ID REFUSES RATHER THAN EXPORTING EVERYTHING
════════════════════════════════════════════════════════════════════════════
`account_ledger` is one account's ledger and `customer_statement` is one
customer's statement. Asked for without `account_id` / `customer_id` they raise
VAL-001 with the field named — they do **not** fall back to "every account",
which would be a download nobody asked for containing every customer's money,
under a filename that says it is one person's statement. BR-SHL-011's *"fall
back, never 4xx"* is about a sort or filter term the list does not honour; it
is not a licence to widen the SUBJECT of a report.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from apps.tenancy import exports as export_kernel
from core import errors
from core.pagination import ListParams

from . import exports as ledger_exports
from . import reporting

#: IS-11's `{report}` segment for each resource. Hyphenated, because a filename
#: is a DISPLAY artifact and the API key is a CONTRACT — `DEF-131` is what
#: happens when one constant serves both purposes.
SLUG_TRIAL_BALANCE = "trial-balance"
SLUG_REMITTANCE = "remittance-by-authority"
SLUG_ACCOUNT_LEDGER = "account-ledger"
SLUG_BY_PREMISES = "by-premises"
SLUG_CUSTOMER_STATEMENT = "customer-statement"
SLUG_EXPORT_PREVIEW = "export-preview"
SLUG_REVENUE_BY_SERVICE = "revenue-by-service"

#: BR-LED-013 — see the module docstring. A file whose rows may each remit on a
#: different basis names neither of them.
BASIS_PER_AUTHORITY = "per-authority"


# ═══════════════════════════════════════════════════════════════════════════
# THE WINDOW — one reading of `from`/`to`, for all seven
# ═══════════════════════════════════════════════════════════════════════════
def _window(params: ListParams) -> tuple[date, date]:
    """`from`/`to` off the caller's own filter state, or THIS MONTH.

    ⚠ **THE DEFAULT IS A MONTH AND NOT "EVERYTHING", AND THAT IS DELIBERATE.**
    Every one of these reads walks posted journal lines; an undated request
    would walk the whole book, which at `T5` is the largest tenant `B6` models
    and is a file nobody meant to ask for. Each screen always sends its dates
    (the parameter bar has no empty state), so this default is reached only by
    a hand-written request — and answering *this month* is both the cheapest
    and the least surprising thing to do with one.

    The dates are parsed with `date.fromisoformat`, which REFUSES rather than
    guessing: `2026-13-01` is a ValueError here and a VAL-002 to the caller,
    not a silent slide into January.
    """
    today = date.today()
    start_raw = (params.filters or {}).get("from")
    end_raw = (params.filters or {}).get("to")
    try:
        start = date.fromisoformat(start_raw) if start_raw else today.replace(day=1)
    except (TypeError, ValueError) as bad:
        raise _field_invalid("from") from bad
    try:
        end = date.fromisoformat(end_raw) if end_raw else _month_end(today)
    except (TypeError, ValueError) as bad:
        raise _field_invalid("to") from bad
    return start, end


def _month_end(day: date) -> date:
    first_next = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    return first_next - timedelta(days=1)


def _field_invalid(field: str) -> errors.ValidationError:
    return errors.ValidationError(
        errors.VAL_FORMAT,
        message_key="ledger.export.window_invalid",
        params={"field": field},
        field_errors=[{"field": field, "code": errors.VAL_FORMAT}],
    )


def _required(params: ListParams, field: str) -> str:
    value = str((params.filters or {}).get(field) or "").strip()
    if not value:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="ledger.export.subject_required",
            params={"field": field},
            field_errors=[{"field": field, "code": errors.VAL_REQUIRED}],
        )
    return value


def _checks(*, window: bool = True, subject: str | None = None):
    """The `validate` hook for one resource (DEF-TEN-9160): the SAME `_window`
    and `_required` its selector calls, run at the door and reading no row, so
    the refusal a clerk meets is the one the selector would have raised."""

    def validate(params: ListParams) -> None:
        if window:
            _window(params)
        if subject:
            _required(params, subject)

    return validate


# ═══════════════════════════════════════════════════════════════════════════
# THE SEVEN SELECTORS — each one call into a read this product already serves
# ═══════════════════════════════════════════════════════════════════════════
def _trial_balance_rows(params: ListParams) -> list[dict[str, Any]]:
    """S38's own table. `reporting.trial_balance` already serves plain dicts."""
    start, end = _window(params)
    result = reporting.trial_balance(start=start, end=end)
    return list(result["rows"])


def _authority_row(row: Any) -> dict[str, Any]:
    """`AuthorityRemittanceRow` is a DATACLASS and the kernel reads Mappings."""
    return {
        "code": row.code,
        "name": row.name,
        "remitting_basis": row.remitting_basis,
        "billed": row.billed,
        "collected": row.collected,
        "remitted": row.remitted,
        "outstanding_billed": row.outstanding_billed,
        "outstanding_collected": row.outstanding_collected,
    }


def _remittance_rows(params: ListParams) -> list[dict[str, Any]]:
    """4·1 By authority — BR-LED-013's billed · collected · remitted · owed.

    ⚠ **`collected` AND `outstanding_collected` CAN BE `None`, AND A `None`
    MUST NOT BECOME `0.00` IN THE FILE.** `apps/ledger/reporting` states why at
    length: payments publishes no allocation breakdown for some windows, and a
    zero there reads as *"nothing was collected"* about money that was. The
    kernel's `format_value` writes an empty cell for a None, which is the
    honest shape — and it is the same answer the screen gives.
    """
    start, end = _window(params)
    result = reporting.remittance_by_authority(start=start, end=end)
    return list(result["rows"])


def _account_ledger_rows(params: ListParams) -> list[dict[str, Any]]:
    """S59 — ONE account's ledger. `account_id` is required; see the module
    docstring for why this does not widen to every account."""
    start, end = _window(params)
    account_id = _required(params, "account_id")
    result = reporting.account_ledger(account_id, start=start, end=end)
    return list(result["rows"])


def _by_premises_rows(params: ListParams) -> list[dict[str, Any]]:
    """S60 / 6·2's Premises grouping — `PremisesRow` dataclasses, not dicts, so
    the resource declares a `serialize`."""
    start, end = _window(params)
    result = reporting.by_premises_summary(start=start, end=end)
    return list(result["rows"])


def _customer_statement_rows(params: ListParams) -> list[dict[str, Any]]:
    """One customer's accounts and each balance (`CR-060` C16).

    The read lives in `apps/customers` and is reached through its published
    selector rather than by touching a customers table — B2 §2. Imported HERE
    rather than at module scope because `apps.ledger.apps.ready()` imports this
    file, and a top-level customers import at app-registry time is the circular
    import that `apps/reports/exports.py` avoids the same way.
    """
    from apps.customers import selectors as customer_selectors

    customer_id = _required(params, "customer_id")
    result = customer_selectors.customer_statement(customer_id)
    if result is None:
        # HR-1: another tenant's customer and a customer that never existed are
        # the same answer. An empty file would be a third, softer answer to a
        # question that has exactly two.
        raise errors.NotFoundError()
    return list(result["rows"])


def _export_preview_rows(params: ListParams) -> list[dict[str, Any]]:
    """6·2's ACCOUNT grouping — the very table the send gate reads.

    `SummaryRow` dataclasses. The target decides which ref column carries a
    value, so it rides on the caller's filter state like every other term;
    `csv` is the default because it is the one target that addresses accounts
    by code+name and therefore never refuses for a missing ref.
    """
    start, end = _window(params)
    target = str((params.filters or {}).get("target") or "csv").strip() or "csv"
    granularity = str((params.filters or {}).get("granularity") or "").strip() or None
    kwargs: dict[str, Any] = {
        "period_start": start,
        "period_end": end,
        "target": target,
    }
    if granularity:
        kwargs["granularity"] = granularity
    try:
        preview = ledger_exports.export_preview(**kwargs)
    except ledger_exports.ExportError as refusal:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="ledger.export.preview_refused",
            params={"detail": str(refusal)},
            field_errors=[{"field": "target", "code": errors.VAL_UNKNOWN_LOOKUP}],
        ) from refusal
    return list(preview["rows"])


def _revenue_by_service_rows(params: ListParams) -> list[dict[str, Any]]:
    """6·2's SERVICE grouping — LE-2's slice, `ServiceRevenueRow` dataclasses."""
    start, end = _window(params)
    return list(reporting.revenue_by_service(start=start, end=end))


# ═══════════════════════════════════════════════════════════════════════════
# SERIALIZERS — for the three reads that answer with dataclasses
# ═══════════════════════════════════════════════════════════════════════════
def _premises_row(row: Any) -> dict[str, Any]:
    return {
        "premises_id": row.premises_id,
        "premises_name": row.name,
        "billed": row.billed,
        "collected": row.collected,
        "owed": row.owed,
    }


def _account_ledger_row(row: Any) -> dict[str, Any]:
    """`AccountLedgerRow` is a dataclass, and `type` is the TENANT-FACING word.

    ⚠ `type_mapped=False` means BR-REP-008's vocabulary has no word for this
    line's source and the raw value is showing through. The file carries the
    raw value exactly as the screen does — *nothing invisible* is the rule, and
    a download that quietly substituted a familiar word for an unmapped one
    would hide the very thing the flag exists to surface."""
    return {
        "entry_date": row.entry_date,
        "type": row.type,
        "reference": row.reference,
        "description": row.description,
        "charge": row.charge,
        "payment": row.payment,
        "running_balance": row.running_balance,
    }


def _summary_row(row: Any) -> dict[str, Any]:
    """⚠ The fields are `window_start`/`window_end`, NOT `period_start`.

    BR-LED-017's weekly granularity slices one period into several windows, so
    a row's dates are ITS window's and the period's dates are the request's.
    Naming the columns `window_*` keeps that distinction visible in the file —
    a summary export at weekly granularity has five rows per account, and a
    column called `period_start` repeating the same date on all five would
    make them look like duplicates."""
    return {
        "code": row.code,
        "name": row.name,
        "target_ref": row.target_ref,
        "debit": row.debit,
        "credit": row.credit,
        "window_start": row.window_start,
        "window_end": row.window_end,
    }


def _service_row(row: Any) -> dict[str, Any]:
    return {
        "service_code": row.service_code,
        "usage": row.usage,
        "base_and_fees": row.base_and_fees,
        "total_billed": row.total_billed,
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE SEVEN RESOURCES
# ═══════════════════════════════════════════════════════════════════════════
MONEY = export_kernel.MONEY
DATE = export_kernel.DATE
TEXT = export_kernel.TEXT
NUMBER = export_kernel.NUMBER
Column = export_kernel.ExportColumn

TRIAL_BALANCE = export_kernel.ExportResource(
    name="trial_balance",
    slug=SLUG_TRIAL_BALANCE,
    module="ledger",
    select=_trial_balance_rows,
    validate=_checks(),
    columns=(
        Column("gl_account", "code"),
        Column("name", "name"),
        Column("type", "type"),
        Column("opening", "opening", MONEY),
        Column("debit", "debit", MONEY),
        Column("credit", "credit", MONEY),
        Column("closing", "closing", MONEY),
    ),
    money=True,
    basis="posting",
    period="window",
    filters=("from", "to"),
)

REMITTANCE = export_kernel.ExportResource(
    name="remittance",
    slug=SLUG_REMITTANCE,
    module="ledger",
    select=_remittance_rows,
    validate=_checks(),
    serialize=_authority_row,
    columns=(
        Column("authority_code", "code"),
        Column("authority", "name"),
        Column("remitting_basis", "remitting_basis"),
        Column("billed", "billed", MONEY),
        Column("collected", "collected", MONEY),
        Column("remitted", "remitted", MONEY),
        Column("outstanding_billed", "outstanding_billed", MONEY),
        Column("outstanding_collected", "outstanding_collected", MONEY),
    ),
    money=True,
    # BR-LED-013 — see the module docstring. Two authorities in one file can
    # lawfully remit on two different bases, so the FILE names neither and the
    # ROW carries its own.
    basis=BASIS_PER_AUTHORITY,
    period="window",
    filters=("from", "to"),
)

ACCOUNT_LEDGER = export_kernel.ExportResource(
    name="account_ledger",
    slug=SLUG_ACCOUNT_LEDGER,
    module="ledger",
    select=_account_ledger_rows,
    validate=_checks(subject="account_id"),
    serialize=_account_ledger_row,
    columns=(
        Column("entry_date", "entry_date", DATE),
        Column("type", "type"),
        Column("reference", "reference"),
        Column("description", "description"),
        Column("charge", "charge", MONEY),
        Column("payment", "payment", MONEY),
        Column("running_balance", "running_balance", MONEY),
    ),
    money=True,
    basis="posting",
    period="window",
    filters=("from", "to", "account_id"),
)

BY_PREMISES = export_kernel.ExportResource(
    name="by_premises",
    slug=SLUG_BY_PREMISES,
    module="ledger",
    select=_by_premises_rows,
    validate=_checks(),
    serialize=_premises_row,
    columns=(
        Column("premises", "premises_name"),
        Column("billed", "billed", MONEY),
        Column("collected", "collected", MONEY),
        Column("owed", "owed", MONEY),
    ),
    money=True,
    basis="posting",
    period="window",
    filters=("from", "to"),
)

CUSTOMER_STATEMENT = export_kernel.ExportResource(
    name="customer_statement",
    slug=SLUG_CUSTOMER_STATEMENT,
    module="ledger",
    select=_customer_statement_rows,
    validate=_checks(window=False, subject="customer_id"),
    columns=(
        Column("account_no", "account_no"),
        Column("kind", "kind"),
        Column("status", "status_name"),
        Column("balance", "balance", MONEY),
        # `CR-060` C16 rule 3 — a weakly-linked account is SHOWN AND MARKED,
        # never silently merged into the total and never silently dropped. The
        # file carries the same mark the screen does, or a reader adding the
        # column up gets a different total from the one on their screen.
        Column("confident", "confident", export_kernel.BOOLEAN),
        Column("held_with", "held_with", export_kernel.LIST),
    ),
    money=True,
    basis="posting",
    period="as-of",
    filters=("customer_id",),
)

EXPORT_PREVIEW = export_kernel.ExportResource(
    name="export_preview",
    slug=SLUG_EXPORT_PREVIEW,
    module="ledger",
    select=_export_preview_rows,
    validate=_checks(),
    serialize=_summary_row,
    columns=(
        Column("gl_account", "code"),
        Column("name", "name"),
        Column("target_ref", "target_ref"),
        Column("debit", "debit", MONEY),
        Column("credit", "credit", MONEY),
        Column("window_start", "window_start", DATE),
        Column("window_end", "window_end", DATE),
    ),
    money=True,
    basis="posting",
    period="window",
    filters=("from", "to", "target", "granularity"),
)

REVENUE_BY_SERVICE = export_kernel.ExportResource(
    name="revenue_by_service",
    slug=SLUG_REVENUE_BY_SERVICE,
    module="ledger",
    select=_revenue_by_service_rows,
    validate=_checks(),
    serialize=_service_row,
    columns=(
        # ⚠ A row whose `service_code` is None is KEPT and written EMPTY, never
        # dropped and never labelled. `reporting.revenue_by_service` says why:
        # a late fee is charged to an account rather than to a service, and
        # dropping those rows makes the file foot to less than the period's
        # revenue — BR-REP-002's silent shortfall.
        Column("service", "service_code"),
        Column("usage_revenue", "usage", MONEY),
        Column("base_and_fees", "base_and_fees", MONEY),
        Column("total_billed", "total_billed", MONEY),
    ),
    money=True,
    basis="posting",
    period="window",
    filters=("from", "to"),
)

RESOURCES = (
    TRIAL_BALANCE,
    REMITTANCE,
    ACCOUNT_LEDGER,
    BY_PREMISES,
    CUSTOMER_STATEMENT,
    EXPORT_PREVIEW,
    REVENUE_BY_SERVICE,
)

#: The names, for a screen or a test asking *"which Finance downloads exist"*
#: without importing seven dataclasses.
RESOURCE_NAMES: tuple[str, ...] = tuple(resource.name for resource in RESOURCES)


def register() -> None:
    """Called once from `LedgerConfig.ready()` — registration only, no logic."""
    for resource in RESOURCES:
        export_kernel.register_export_resource(resource)


# ── Lifecycle ─────────────────────────────────────────────
# packet: P4.1 + P4.10 (05-prototype/07 Finance Blueprint.pdf p017 task rows, read AS IMAGES per B14 rule 42 · p070 rows 3 and 6 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-004/013 · apps/reports/exports.py, the precedent this copies)
# screens: 6·2 Export · 4·1 By authority · S38 · S59 · S60 · the statement viewer
# generated: 2026-09-24 by lane FIN-P4
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — these register against POST /exports, which already exists) E=deferred(the five buttons are P4.5, in this lane) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: (1) NO PDF — this deployment has no PDF renderer of any kind and `apps/reports/exports.py` records the same absence; IS-11 says CSV always and PDF where layout matters, and one of those two is true today · (2) `remittance`'s `{basis}` segment is `per-authority` rather than a BR-REP-001 label, because BR-LED-013 lets two authorities in one file remit on two different bases — the row carries `remitting_basis` instead · (3) `account_ledger` and `customer_statement` REFUSE without their subject id rather than widening to every account, which BR-SHL-011's fall-back does not cover · (4) `revenue_by_service` is registered beside reports' `revenue_by_service_rate` and they are deliberately different reports
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
