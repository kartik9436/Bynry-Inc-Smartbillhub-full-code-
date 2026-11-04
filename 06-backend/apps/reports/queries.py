# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-002 (S46 report viewer — live-vocabulary parameter bar, run,
#           basis-labeled render) · US-REP-005 (AR aging + the DSO ratio) ·
#           US-REP-006 (Billing register + Revenue by service & rate) ·
#           US-REP-007 (Payments by method)   Screens: S44 · S46
# Rules:    BR-REP-001 (EVERY money KPI/report header labels its date basis —
#           an unlabeled money render is a defect by contract) · BR-REP-002
#           (read-models only) · BR-REP-006 (live vocabularies) · BR-REP-008
#           (the ageing foots to the AR tie-out) · BR-REP-011 (DSO = (AR ÷
#           billed last 12 months) × 365, rolling, posting basis) · BR-REP-014
#           (collection framings count BILL-purpose payments only) · BR-REP-024
#           (never a 0 where a figure could not be computed) · CLAUDE.md rule 2
#           (money is a decimal string beside its CHAR(3)) · rule 3 (a quantity
#           always carries its unit)
# Tests:    06-backend/tests/test_us_rep_catalog_and_viewer.py ·
#           06-backend/tests/test_us_rep_005_007_ar_and_cash.py ·
#           06-backend/tests/test_us_rep_006_billing_reports.py
# Impacts:  apps/reports/api.py (the ONLY caller) · apps/reports/exports.py
#           (the IS-11 CSV rides the same rows) · 06-backend/openapi/schema.json
# ───────────────────────────────────────────────────────
"""Read-model composition for the S46 viewer: params in, a rendered report out.

This module owns NO tables and reads no neighbour's ORM (B1). Every figure
arrives through `report_seams`, from the module that owns the rows.

════════════════════════════════════════════════════════════════════════════
THE ONE INVARIANT EVERY REPORT ON THIS PAGE OBEYS — BR-REP-001
════════════════════════════════════════════════════════════════════════════
*"every KPI/report header labels its basis — no unlabeled money number
anywhere"*. So `basis` is not an optional field a renderer may forget: it is
built by `_report()` for every report and asserted by the suite. Billing-side
figures (billed, revenue, AR, ageing) read the POSTING date; cash-side figures
(deposits, bank rec) read the CLEARING date — and Payments by method moved to
the POSTING date on 2026-10-21 (PO ruling, `DEF-PAY-10321`).

════════════════════════════════════════════════════════════════════════════
A FIGURE WITH NO BASIS IS NOT A FIGURE, AND NEITHER IS A ZERO
════════════════════════════════════════════════════════════════════════════
DEF-129's lane wrote BR-REP-024 for the dashboard and the rule is the same here:
a total that cannot be computed carries `null` **and a reason**, never `0` and
never the string `null`. A production defect on 2026-08-16 rendered the literal
text `null USD` on a tile, which is what happens when a money value and its
currency code are formatted independently — so `_money()` returns None for an
absent amount and the currency travels on the report, ONCE, beside the figures
it belongs to.

════════════════════════════════════════════════════════════════════════════
WHAT A "RUN" IS, AND WHY RUNNING ONE WRITES NOTHING
════════════════════════════════════════════════════════════════════════════
`GET /reports/{key}` is a READ. It touches no table, records no row and has no
side effect — a report a clerk opens twice must be the same document twice.

The generation RECORD BR-REP-018 asks for is written when a FILE is produced,
by the export pipeline (`apps/tenancy/services.request_list_export` writes the
`audit_log` row for a money-bearing export, cap-checked first). `apps/reports/
exports.py` registers these reports with that pipeline, so an exported report is
audited by the same code path as every other export in the product and there is
no second implementation of "who exported what".
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from core import errors
from core.pagination import clamp_page_size

from . import catalog, report_seams as seams

#: US-REP-002's date-range presets, A14 §Viewer verbatim. `custom` is the caller
#: supplying `from`/`to` directly; the four named ones are RESOLVED AGAINST THE
#: TENANT'S OWN accounting calendar (BR-TEN-022), never against a calendar month
#: this module invented — that is the whole reason `current_period` is a seam.
RANGE_THIS_PERIOD = "this_period"
RANGE_CUSTOM = "custom"


def _money(value: Any) -> str | None:
    """A Decimal as its EXACT decimal string, or None.

    Never a float and never a rounded value: B4 rounds at finalization and
    display, and this is neither. None in ⇒ None out, so an absent figure stays
    absent all the way to the screen instead of becoming `"0.00"` on the way.
    """
    if value is None:
        return None
    if not isinstance(value, Decimal):  # pragma: no cover — defensive, hard rule 2
        raise TypeError(
            "money leaves a read model as a Decimal — NUMERIC(18,6), never a binary "
            f"fraction and never cents (CLAUDE.md rule 2); got {type(value).__name__}"
        )
    return f"{value:f}"


def _iso(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _trimmed(amount: Decimal) -> str:
    """A CONSUMPTION quantity, without the trailing zeros of its storage width.

    `684.000000` and `26.240000` are what NUMERIC(18,6) holds; A14 and the
    prototype both read *"684 kWh"* and *"26.24 kgal"*, and trailing zeros on a
    consumption figure carry no information — 684.000000 kWh is 684 kWh in every
    reading. Trimmed HERE, once, so the screen and the CSV say the same thing
    rather than each formatting the fact its own way.

    **THIS IS NOT APPLIED TO MONEY AND MUST NOT BE.** Money leaves through
    `_money()` at full precision, because B4 decides where a money figure rounds
    and a display helper is not that place (`10.50` and `10.5` are the same
    number and only one of them is a currency amount).
    """
    text = format(amount, "f")
    if "." not in text:
        return text
    return text.rstrip("0").rstrip(".") or "0"


def _quantity(pairs: Any, counted: Any = ()) -> list[dict[str, Any]]:
    """CLAUDE.md rule 3 — a quantity NEVER travels without its unit.

    A list of `{quantity, unit}` and not a single number, because a bill that
    consumed 684 kWh and 26.24 kgal has TWO usages and adding them is
    meaningless. The screen renders "684 kWh · 26.24 kgal"; it is never handed a
    bare 710.24.

    ⚠ **`measured` SAYS WHETHER THIS FIGURE IS A READING OR A COUNT**
    (`DEF-REP-7010`). `BR-RAT-090`: a CAPACITY service is billed by a COUNT of
    the unit's assets. So `0 cart` means *nobody has a cart here* and `0 kgal`
    means *the meter was read, and read zero* — two different facts that
    arrive in this one cell as the same `"0"`, and the register drew all of
    them on every row of a live tenant. The SCREEN decides what to do with it;
    this only says which is which, because only the read model knows.

    ⚠ **`counted` DEFAULTS TO EMPTY, SO EVERY EXISTING CALLER IS UNCHANGED.**
    An absent declaration means *every quantity is a reading*, which is what
    every report in this product served before the flag existed — and what a
    deployment whose tenancy lane publishes no capacity basis goes on serving.
    """
    units = frozenset(str(unit) for unit in (counted or ()))
    return [
        {"quantity": _trimmed(amount), "unit": unit, "measured": unit not in units}
        for amount, unit in pairs
    ]


def _window(params: Any, *, tenant_period: dict[str, Any] | None) -> tuple[date, date]:
    """The report window: the caller's explicit range, or the tenant's period.

    A16/BR-TEN-022: an accounting period is COMPUTED from the tenant's fiscal
    settings and never stored, and it is the SAME window S7, S36, S59 and S60
    head their pages with. A viewer that defaulted to `date.today()`'s calendar
    month would be the one screen in this product disagreeing with the other
    four about which month a figure belongs to.
    """
    raw_from = params.get("from")
    raw_to = params.get("to")
    if raw_from or raw_to:
        return _explicit_day(raw_from, "from"), _explicit_day(raw_to, "to")
    if tenant_period is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="reports.viewer.no_fiscal_period",
            field_errors=[{"field": "from", "code": errors.VAL_REQUIRED}],
        )
    return (
        _explicit_day(tenant_period.get("start"), "from"),
        _explicit_day(tenant_period.get("end"), "to"),
    )


def _explicit_day(raw: Any, field: str) -> date:
    if raw is None or str(raw).strip() == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="reports.viewer.param_required",
            field_errors=[{"field": field, "code": errors.VAL_REQUIRED}],
        )
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw))
    except (TypeError, ValueError) as problem:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="reports.viewer.date_invalid",
            field_errors=[{"field": field, "code": errors.VAL_FORMAT}],
        ) from problem


def _checked_window(params: Any) -> tuple[date, date]:
    """The window, with US-REP-002 TC-6's inverted-range refusal applied."""
    period = seams.current_period()
    start, end = _window(params, tenant_period=period)
    if start > end:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="reports.viewer.range_inverted",
            params={"from": start.isoformat(), "to": end.isoformat()},
            field_errors=[
                {"field": "from", "code": errors.VAL_RANGE},
                {"field": "to", "code": errors.VAL_RANGE},
            ],
        )
    return start, end


def _report(
    key: str,
    *,
    basis: str,
    window: dict[str, Any],
    currency: str | None,
    columns: tuple[str, ...],
    rows: list[dict[str, Any]],
    kpis: list[dict[str, Any]],
    totals: dict[str, Any],
    unavailable: Any = (),
    page: dict[str, Any] | None = None,
    grain: str | None = None,
    controls: dict[str, Any] | None = None,
    column_meta: dict[str, dict[str, Any]] | None = None,
    head: dict[str, Any] | None = None,
    column_choices: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """The ONE wire shape every report on S46 renders through.

    Built here rather than per report so BR-REP-001 cannot be forgotten by one
    of them: `basis` is a required argument of this function, so a report
    without one does not compile into an answer.

    `kpis` is a LIST of `{key, value, kind, currency?, detail?}` rather than a
    dict, because the strip is ORDERED (A14 draws Total AR first) and because
    every tile must be able to carry its own null-with-a-reason without the
    caller inventing a parallel structure.
    """
    return {
        "key": key,
        "basis": basis,
        "window": window,
        "currency": currency,
        "columns": columns,
        # ── `DEF-REP-6902` · A COLUMN THIS QUERY INVENTED ────────────────────
        # ⚠ **`runner._shaped` PUBLISHES WHAT THE DATASET DECLARES, AND A
        # DERIVED COLUMN IS DECLARED BY NOBODY.** The close pack's `value_a`
        # and the tax remittance's `outstanding_billed` are money computed
        # here, on the `journal_lines` dataset, which has never heard of
        # either — so both printed storage width (`23766.560000`,
        # `531.140000`) after every declared money column on every other
        # report had been fixed. A query that invents a money column is the
        # only place that knows it is money, so it says so here. Omitted
        # entirely by a query that invents none, which is all but two of them.
        **({"column_meta": column_meta} if column_meta else {}),
        "rows": rows,
        "kpis": kpis,
        "totals": totals,
        "unavailable": [dict(entry) for entry in unavailable],
        # ⚠ **`NFR-3`.** Present on a report that PAGES and absent on one that
        # is bounded by something other than tenant size (at most eleven
        # services, at most three subledgers). A reader must be able to tell
        # *"this is all of it"* from *"this is page one"*, and an absent key
        # says the first without claiming the second.
        **({"page": page} if page is not None else {}),
        # ⚠ **`P2.23` — WHAT ONE ROW IS, AS A CODE AND NEVER AS A SENTENCE.**
        # The screen states it under the title (*"One row per account"*), and
        # the sentence is the catalogues' in eleven languages. Absent means this
        # report does not state its grain, and the screen then says NOTHING
        # rather than guessing — a report whose grain line is wrong is worse
        # than one that has none, because a reader trusts it.
        #
        # ⚠ IT IS THE DEFINITION'S AND NOT THE DATASET'S. `datasets.py` gives
        # AR ageing's dataset the grain *"one payment allocation"*, which is
        # true of the dataset and FALSE of this report: the ageing is one row
        # per debtor. Serving `Dataset.grain` here would have printed a
        # confident wrong fact on the screen the brief is fixing.
        **({"grain": grain} if grain is not None else {}),
        # ⚠ **`P2.5` / `P2.2` / `P2.3` — WHAT THE TABLE MAY OFFER, DECLARED.**
        # `{"sorts": [...], "sort": ..., "dir": ..., "searchable": bool}`.
        #
        # The screen draws a sort caret ONLY on a column named here, because a
        # caret over a column the query ignores is hard-won law 2's mirror — a
        # live screen behind a dead control. `ar_aging` sorts by `total` and
        # `days_late` and by nothing else; the account ledger declines sort
        # entirely and is right to, because ordering a running balance by
        # amount destroys the column.
        #
        # Absent = this report offers neither sort nor search, which is what
        # `revenue_by_service_rate` and `payments_by_method` are: bounded by the
        # service list and the tender list, not by tenant size.
        **({"controls": controls} if controls is not None else {}),
        # ⚠ **`DEF-REP-7052` — WHICH RECORD THIS PAGE OF MONEY BELONGS TO.**
        # `{"subject": "account", "fields": [{"field": ..., "value": ...}]}`,
        # composed from the SUBJECT's own `head_from` by
        # `apps/reports/subject_head.py`. Absent on the forty-five reports that
        # are about no particular record, and the screen then draws nothing —
        # never an empty separator and never a placeholder.
        #
        # ⚠ **VALUES ONLY, AND EVERY ONE OF THEM A WORD A CLERK ALREADY READS**
        # (B14 rule 31): an account NUMBER, a person's name, a premises address,
        # a unit label. The id that selected the record travels in the URL and
        # is never among these.
        **({"head": head} if head is not None else {}),
        # ⚠ **`DEF-REP-7072` — WHAT THE EDITOR MAY OFFER ON *THIS RUN*.**
        # Published by a report whose columns are its own rather than its
        # dataset's, and absent on the forty-five that read the dataset.
        #
        # ⚠ **IT IS THE RUN'S SET AND NOT THE REPORT'S WHOLE VOCABULARY, AND
        # THE TWO ARE DELIBERATELY DIFFERENT.** `runner.served_columns` is what
        # a run may be ASKED for and is the union across subjects, so a
        # bookmarked `columns` is not refused the moment a clerk switches
        # grain. This is what the panel DRAWS, and on an account statement the
        # unit subject's `occupant` and `account` are not among them — a tick
        # box for a column this run cannot serve is a control over nothing
        # (hard-won law 2's mirror), and it measured `7 of 9` in a browser
        # before this line existed.
        **({"column_choices": list(column_choices)} if column_choices is not None else {}),
    }


def _kpi(
    key: str,
    value: Any,
    *,
    kind: str = "money",
    detail: str | None = None,
    detail_kind: str | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    """One KPI tile. A null value ALWAYS carries `reason_code` (BR-REP-024).

    ⚠ **`detail` IS A FIGURE A CLERK READS, NEVER AN INTERNAL CODE**
    (`CR-142-BRC07` `P2.13`). Until 2026-09-26 the AR-total tile passed
    `detail="currency_not_derivable"` beside its reason, and the screen printed
    that snake_case string under the tile on every book with no single
    currency. That is B14 rule 31's shape, and the brief walked it on
    2026-09-23: *"one printed the internal code `currency_not_derivable`
    beneath it"*. `reason_code` already carries WHY, in a key the eleven
    catalogues turn into a sentence; `detail` carries a NUMBER.

    `detail_kind` says what that number is, so the screen renders its unit
    instead of sniffing the string: `"share"` is a percentage of this report's
    own total and renders `42%`. Absent = a plain string, which is what every
    other tile passes, so nothing else moves.
    """
    return {
        "key": key,
        "value": value,
        "kind": kind,
        "detail": detail,
        "detail_kind": detail_kind,
        "reason_code": reason_code,
    }


def _no_currency_reason(currency: Any, population: Any, mixed_code: str) -> str | None:
    """WHY a money figure is absent, and it is not always the same reason.

    ⚠ **`CR-142-BRC07` `P2.13` — THE FALSE SENTENCE THIS REPLACES SHIPPED.**
    A read model publishes the currency its figures ARE, derived from the
    entries it summed, and it publishes NONE in two different worlds: a window
    holding more than one currency, and a window holding nothing at all. Every
    caller treated the second as the first, so an EMPTY book — the state every
    new tenant is in on its first day — printed *"More than one currency was
    billed, so there is no single total"* over a book that had been billed in
    no currency whatsoever. The brief walked it on 2026-09-23 and counted it:
    *"three of the four printed a false multi-currency sentence"*.

    `population` is the report's own row/account count over the WHOLE filtered
    set, which is the only thing that can tell the two apart from here.
    """
    if currency:
        return None
    return "nothing_in_this_range" if not population else mixed_code


# ── AR aging summary + the DSO ratio (US-REP-005) ───────────────────────────
def _page_number(raw: Any) -> int:
    """`page`, clamped to 1 and never an error (`BR-SHL-011`).

    The seam clamps the UPPER end against the row count it has just computed;
    this only refuses a value that is not a page number at all. A saved link
    carrying `page=frog` opens on page one rather than on an error screen.
    """
    try:
        return max(1, int(str(raw)))
    except (TypeError, ValueError):
        return 1


#: p035's `f.band` values — the five bands, spelled as `apps/payments` spells
#: them. An unknown value FALLS BACK to no filter rather than erroring
#: (`BR-SHL-011`: *"invalid values fall back or clamp, NEVER error"*), because a
#: saved link with a stale chip must still open the report.
_AGING_BANDS: tuple[str, ...] = ("current", "1-30", "31-60", "61-90", "90+")

#: What this report may be ordered by. ⚠ `account_no` and `customer_name` are
#: NOT here and the screen offers no caret on them — they live on customers'
#: table, which the ageing statement does not join (`B1`/`BR-TEN-013`), and
#: sorting a page that was already cut is the defect `P2.21` exists to fix.
#: `DEF-REP-6660` sizes the join.
_AGING_SORTS: tuple[str, ...] = ("total", "days_late")


def ar_aging(params: Any) -> dict[str, Any]:
    """A14's AR ageing table, its KPI strip, and the tie-out it must foot to.

    ONE parameter decides the figures and it is `as_of`, not a range: a
    receivable is a POSITION at a date, not a flow over a window. Absent, it is
    the tenant's period END — the same day S36's tie-out is struck, which is
    what makes the two figures comparable at all.

    ⚠ **IT PAGES AND IT FILTERS SINCE `P2.21` (`DEF-REP-6607`), AND THE
    TIE-OUT IS DELIBERATELY NOT COMPUTED OVER WHAT YOU CAN SEE.** p035 names
    five criteria — `as_of`, band, service, property, search — and one row per
    debtor, so the list grows with the tenant and at 40,000 accounts it cannot
    load whole. The trap the previous lane measured and refused to ship around:
    **`totals` narrows with the filter, and comparing a narrowed total against
    the ledger's AR control makes this report accuse the books of not footing
    on every filtered page.** So there are two figures and they answer two
    questions — `totals`, a SQL aggregate over the whole FILTERED set which the
    KPI tiles show and which foots to the rows whatever page is cut, and
    `population_total`, the same aggregate with every criterion removed, which
    is the only figure `BR-REP-008`'s comparison may be struck against.
    """
    _, as_of = _checked_window(params)
    account_class = params.get("class") or params.get("f.class") or None
    band = params.get("f.band") or None
    if band not in _AGING_BANDS:
        band = None
    service = params.get("f.service") or params.get("service") or None
    premises = params.get("f.premises") or None
    search = (params.get("q") or "").strip() or None
    sort = params.get("sort") or "total"
    if sort not in _AGING_SORTS:
        sort = "total"
    direction = "asc" if str(params.get("dir") or "desc").lower() == "asc" else "desc"
    page_no = _page_number(params.get("page"))
    # ⚠ **`per=all` IS THE EXPORT'S DOOR AND IT IS NOT A CAP BEING LIFTED.**
    # A downloaded file is the whole filtered set by definition — `P4.13`, PO
    # verbatim *"all selected columns will go in downloaded file"* — and a
    # report that started paging would otherwise have silently truncated every
    # AR ageing export to fifty rows, with the file looking perfectly valid.
    # `NFR-5`: there is no ceiling on this branch and there must never be one.
    whole = str(params.get("per") or "").lower() == "all"
    per = None if whole else clamp_page_size(params.get("per"))

    view = seams.ar_aging(
        as_of=as_of,
        account_class=account_class,
        band=band,
        service_code=service,
        premises_id=premises,
        search=search,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
    )
    if view is None:  # pragma: no cover — payments publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.ar_aging.unavailable")

    currency = view["currency"]
    totals = view["totals"]
    rows = [
        {
            "account_id": row.account_id,
            "account_no": row.account_no,
            "customer_name": row.customer_name,
            "account_class": row.account_class,
            "account_class_code": row.account_class_code,
            "current": _money(row.buckets["current"]),
            "d1_30": _money(row.buckets["1-30"]),
            "d31_60": _money(row.buckets["31-60"]),
            "d61_90": _money(row.buckets["61-90"]),
            "d90_plus": _money(row.buckets["90+"]),
            "total": _money(row.total),
            "days_late": row.days_late,
        }
        for row in view["rows"]
    ]

    # BR-REP-008 / US-REP-005 TC-3 — the ageing must foot to the AR tie-out, and
    # any drift is US-LED-004's red flag rather than a report-side adjustment.
    # Stated ON the report so nobody has to perform the comparison by eye across
    # two screens.
    #
    # ⚠ **IT IS STRUCK AGAINST THE POPULATION AND NEVER AGAINST THE FILTERED
    # TOTAL.** The books hold the whole receivable; a filtered total is a
    # subset BY DESIGN, so comparing the two would report a discrepancy on
    # every chip and every search — the report calling the general ledger
    # broken because a clerk typed a name. `population_total` does not move
    # when a criterion is added, which is what makes this line a fact about the
    # BOOKS.
    tie_out = seams.ar_control(as_of=as_of)
    population_total = view["population_total"]
    unavailable = list(view["problems"])
    if tie_out is None:
        unavailable.append(
            {
                "code": "ar_control_total_not_published",
                "br_ref": "BR-REP-008",
                "detail": (
                    "The ledger's AR control total could not be read, so this ageing cannot "
                    "state whether it foots. The bands are served; the tie-out line is absent "
                    "with this reason rather than showing a tick nobody checked."
                ),
            }
        )
    elif tie_out != population_total:
        unavailable.append(
            {
                "code": "aging_does_not_foot_to_the_ar_control_total",
                "br_ref": "BR-REP-008 · BR-LED-007",
                "detail": (
                    f"Σ of this tenant's whole receivable is {population_total:f} and the "
                    f"ledger's AR control total is {tie_out:f}. BR-REP-008 requires them to "
                    "agree; a difference is the US-LED-004 red flag and is NEVER closed by "
                    "adjusting this report. The commonest cause on this deployment is "
                    "imported opening balances, which are in the books and not yet in any "
                    "bill (see the gap above). This comparison is struck over every debtor "
                    "in the tenant and is not narrowed by a filter or a page."
                ),
            }
        )

    aged_total = totals["total"]

    def _share(amount: Decimal) -> str | None:
        """A band's share of the receivable. None when there is nothing to
        divide by — a percentage of zero is not 0%, it is undefined."""
        if currency is None or aged_total is None or aged_total == Decimal("0"):
            return None
        return f"{(amount / aged_total * 100):.1f}"

    # ⚠ **THE REASON HAS TO BE THE TRUE ONE (`P2.13`).** `currency` is None in
    # TWO different worlds — a receivable holding more than one currency, and a
    # receivable holding nothing at all — and until 2026-09-26 both printed
    # *"More than one currency is owed"*. The brief walked it: *"three of the
    # four printed a false multi-currency sentence"* (2026-09-23, p027). An
    # empty book is the commonest state a new tenant is ever in, so the false
    # sentence was the one most clerks would have met first.
    empty = not totals["accounts"]
    ar_absent = (
        None
        if currency
        else "nothing_owed_at_this_date"
        if empty
        else "receivable_holds_more_than_one_currency"
    )
    kpis = [
        _kpi("total_ar", _money(aged_total) if currency else None, reason_code=ar_absent),
        _kpi("current", _money(totals["current"]), detail=_share(totals["current"]), detail_kind="share"),
        _kpi("d1_30", _money(totals["1-30"]), detail=_share(totals["1-30"]), detail_kind="share"),
        _kpi("d31_60", _money(totals["31-60"]), detail=_share(totals["31-60"]), detail_kind="share"),
        _kpi("d61_90", _money(totals["61-90"]), detail=_share(totals["61-90"]), detail_kind="share"),
        _kpi("d90_plus", _money(totals["90+"]), detail=_share(totals["90+"]), detail_kind="share"),
        _kpi("accounts", totals["accounts"], kind="count"),
    ]
    served = view["page"]
    return _report(
        catalog.KEY_AR_AGING,
        basis=view["basis"],
        window={"as_of": _iso(as_of)},
        currency=currency,
        columns=(
            "account_no",
            "customer_name",
            "account_class",
            "current",
            "d1_30",
            "d31_60",
            "d61_90",
            "d90_plus",
            "total",
        ),
        rows=rows,
        kpis=kpis,
        totals={
            "current": _money(totals["current"]),
            "d1_30": _money(totals["1-30"]),
            "d31_60": _money(totals["31-60"]),
            "d61_90": _money(totals["61-90"]),
            "d90_plus": _money(totals["90+"]),
            "total": _money(aged_total),
            "accounts": totals["accounts"],
            "ar_control": _money(tie_out) if tie_out is not None else None,
            # The receivable the tie-out line is about, served beside it so a
            # reader can see WHICH two numbers were compared (B14 rule 33 keeps
            # the sentence short; the figures carry the rest).
            "population_total": _money(population_total),
            "population_accounts": view["population_accounts"],
            "filtered": view["filtered"],
        },
        unavailable=unavailable,
        # `P2.23` — one row is one DEBTOR. Four words on screen.
        grain="account",
        controls={
            "sorts": list(_AGING_SORTS),
            "sort": sort,
            "dir": direction,
            "searchable": True,
        },
        page=None
        if whole
        else {
            "page": served,
            "per": per,
            "total": totals["accounts"],
            "pages": max(1, -(-int(totals["accounts"] or 0) // per)),
        },
    )


# ── Billing register (US-REP-006 ①) ─────────────────────────────────────────
#: What the register may be ordered by — billing's OWN tuple, read through the
#: seam at call time rather than copied here, so a sort this module offers and
#: the read model declines cannot exist (`BR-REP-006`, and hard-won law 2's
#: mirror: a caret the server silently ignores is a live control over a dead
#: one). The fallback is billing's own default and never a wider set.
def _register_sorts() -> tuple[str, ...]:
    found = seams.resolve_constant("billing", "REGISTER_SORTS", kind="reporting")
    return tuple(found) if found else (_register_default_sort(),)


def _register_default_sort() -> str:
    found = seams.resolve_constant("billing", "REGISTER_DEFAULT_SORT", kind="reporting")
    return str(found) if found else "invoice_no"


def _register_default_direction() -> str:
    found = seams.resolve_constant("billing", "REGISTER_DEFAULT_DIRECTION", kind="reporting")
    return str(found) if found else "asc"


def billing_register(params: Any) -> dict[str, Any]:
    """Every bill ISSUED in the window, typed, with its usage in its own units.

    ⚠ **IT PAGES, SORTS AND SEARCHES IN SQL SINCE `P2.12`/`P2.1`–`P2.3`
    (`CR-142-BRC07`).** Before that the read model materialised the tenant's
    whole ISSUED book and this function rendered every row of it — 38,412 rows
    at the top of the ICP, against a 60-second worker timeout. The KPI tiles
    are a SQL aggregate over the whole FILTERED set, so they foot to the report
    whether a page is cut or not; `rows` is the page.

    `per=all` is the EXPORT's door and is not a cap being lifted — the same
    branch `ar_aging` takes, for the same reason: a file is the whole filtered
    set by definition, and a register export that silently became fifty rows
    would look perfectly valid.
    """
    start, end = _checked_window(params)
    bill_type = params.get("bill_type") or params.get("f.bill_type") or None
    if bill_type is not None and bill_type not in catalog_bill_types():
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="reports.register.unknown_bill_type",
            params={"bill_type": bill_type, "values": list(catalog_bill_types())},
            field_errors=[{"field": "bill_type", "code": errors.VAL_UNKNOWN_LOOKUP}],
        )
    service = params.get("service") or params.get("f.service") or None
    search = (params.get("q") or params.get("search") or "").strip() or None
    sorts = _register_sorts()
    sort = params.get("sort") or _register_default_sort()
    if sort not in sorts:
        # `BR-SHL-011` — invalid values fall back or clamp, NEVER error. A
        # saved link carrying a sort this report retired still opens.
        sort = _register_default_sort()
    # ⚠ **THE DEFAULT DIRECTION IS BILLING'S, NOT THIS MODULE'S `desc`.** A
    # register is a numbered sequence and has always been served in
    # `invoice_no` ASC; defaulting to `desc` here would have reversed every
    # unsorted register on the day paging landed — a behaviour change wearing
    # a performance fix's clothes.
    raw_direction = params.get("dir")
    direction = (
        _register_default_direction()
        if raw_direction in (None, "")
        else ("asc" if str(raw_direction).lower() == "asc" else "desc")
    )
    page_no = _page_number(params.get("page"))
    whole = str(params.get("per") or "").lower() == "all"
    per = None if whole else clamp_page_size(params.get("per"))

    view = seams.billing_register(
        start=start,
        end=end,
        bill_type=bill_type,
        service_code=service,
        search=search,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
    )
    if view is None:  # pragma: no cover — billing publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.register.unavailable")

    currency = view["currency"]
    kpi = view["kpis"]
    rows = [
        {
            "invoice_id": row.invoice_id,
            "invoice_no": row.invoice_no,
            "bill_type": row.bill_type,
            "status": row.status,
            "account_id": row.account_id,
            "account_no": row.account_no,
            "customer_name": row.customer_name,
            "cycle_label": row.cycle_label,
            "issued_on": _iso(row.issued_on),
            "services": list(row.services),
            "usage": _quantity(row.usage, row.counted_units),
            "amount": _money(row.amount),
            "flag": "estimated" if row.estimated else None,
        }
        for row in view["rows"]
    ]
    return _report(
        catalog.KEY_BILLING_REGISTER,
        basis=view["basis"],
        window={"start": _iso(start), "end": _iso(end)},
        currency=currency,
        columns=(
            "invoice_no",
            "account_no",
            "customer_name",
            "bill_type",
            "services",
            "usage",
            "amount",
            "flag",
        ),
        rows=rows,
        kpis=[
            # ⚠ **THE SUB-LINE IS MONEY AND IT USED TO RENDER AS
            # `15734.170000`** — storage precision, six decimals, no currency,
            # on screen (CLAUDE.md hard rule 2: money DISPLAYS 2). `detail_kind`
            # tells the tile what the figure is so it goes through the one money
            # formatting path (BR-SHL-023) instead of `String(...)`.
            _kpi(
                "bills",
                kpi["bills"],
                kind="count",
                detail=_money(kpi["billed"]),
                detail_kind="money",
            ),
            _kpi(
                "average_bill",
                _money(kpi["average_bill"]),
                reason_code=None if kpi["average_bill"] is not None else "no_bills_in_window",
            ),
            _kpi("estimated", kpi["estimated"], kind="count"),
            # A14's fourth tile. NULL with its reason, never 0 — see
            # apps/billing/reporting.py: exceptions are keyed to a RUN and this
            # window may span several, so there is no single count to state.
            _kpi(
                "exceptions",
                None,
                kind="count",
                reason_code="exception_count_is_per_run_not_per_window",
            ),
        ],
        totals={"bills": kpi["bills"], "billed": _money(kpi["billed"])},
        unavailable=view["problems"],
        # `P2.23` — one row is one BILL.
        grain="bill",
        controls={
            "sorts": list(sorts),
            "sort": sort,
            "dir": direction,
            "searchable": True,
        },
        page=None
        if whole
        else {
            "page": view["page"],
            "per": per,
            "total": view["total"],
            "pages": max(1, -(-int(view["total"] or 0) // per)),
        },
    )


def catalog_bill_types() -> tuple[str, ...]:
    """A14 item 6's vocabulary, read from billing's own tuple at call time.

    Resolved through the seam rather than copied, so a seventh bill type cannot
    exist in billing and not in this filter (BR-REP-006).

    ⚠ **"THROUGH THE SEAM" BECAME TRUE ON 2026-09-26 AND WAS A CLAIM BEFORE
    THAT** (`CR-142-BRC07` `P0.13`, hard-won law 1). This docstring said the
    read went through the seam while the line below it said
    `import_module("apps.billing.reporting")`. It does now.
    """
    return seams.bill_types()


# ── Revenue by service & rate (US-REP-006 ②) ────────────────────────────────
def revenue_by_service_rate(params: Any) -> dict[str, Any]:
    """A14 item 9's invoice-line read-model, with a drill-back id on every row."""
    start, end = _checked_window(params)
    view = seams.revenue_by_service_and_rate(start=start, end=end)
    if view is None:  # pragma: no cover — billing publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.revenue.unavailable")

    currency = view["currency"]
    totals = view["totals"]
    rows = [
        {
            "service_id": row.service_id,
            "service_code": row.service_code,
            "service_name": row.service_name,
            # A14 item 9: the rate schedule is NOT a journal dimension. It is
            # here because this is an INVOICE-LINE read, and the id is what the
            # drill-back opens.
            "tariff_id": row.tariff_id,
            "tariff_name": row.tariff_name,
            "accounts": row.accounts,
            "usage_revenue": _money(row.usage_revenue),
            "base": _money(row.base),
            "tax": _money(row.tax),
            "total": _money(row.total),
        }
        for row in view["rows"]
    ]
    return _report(
        catalog.KEY_REVENUE_BY_SERVICE,
        basis=view["basis"],
        window={"start": _iso(start), "end": _iso(end)},
        currency=currency,
        columns=(
            "service_name",
            "tariff_name",
            "accounts",
            "usage_revenue",
            "base",
            "tax",
            "total",
        ),
        rows=rows,
        kpis=[
            # `P2.13` — the reason that is ACTUALLY true. An empty window and a
            # two-currency window both leave `currency` None, and only one of
            # them is a currency problem.
            _kpi("total_revenue", _money(totals["total"]) if currency else None,
                 reason_code=_no_currency_reason(
                     currency, totals["accounts"], "revenue_window_holds_more_than_one_currency"
                 )),
            _kpi("usage_revenue", _money(totals["usage_revenue"]) if currency else None,
                 reason_code=_no_currency_reason(
                     currency, totals["accounts"], "revenue_window_holds_more_than_one_currency"
                 )),
            _kpi("base_and_fees", _money(totals["base"]) if currency else None,
                 reason_code=_no_currency_reason(
                     currency, totals["accounts"], "revenue_window_holds_more_than_one_currency"
                 )),
            _kpi("tax", _money(totals["tax"]) if currency else None,
                 reason_code=_no_currency_reason(
                     currency, totals["accounts"], "revenue_window_holds_more_than_one_currency"
                 )),
        ],
        totals={
            "accounts": totals["accounts"],
            "usage_revenue": _money(totals["usage_revenue"]),
            "base": _money(totals["base"]),
            "tax": _money(totals["tax"]),
            "total": _money(totals["total"]),
        },
        unavailable=view["problems"],
        # `P2.23` — one row is one service-and-rate pairing.
        grain="service_rate",
    )


# ── Payments by method (US-REP-007) ─────────────────────────────────────────
def payments_by_method(params: Any) -> dict[str, Any]:
    """The cash mix on the POSTING basis (PO 2026-10-21), purposes on their own lines."""
    start, end = _checked_window(params)
    purpose = params.get("purpose") or params.get("f.purpose") or None
    view = seams.payments_by_method(start=start, end=end, purpose=purpose)
    if view is None:  # pragma: no cover — payments publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.cash.unavailable")

    currency = view["currency"]
    totals = view["totals"]
    grand = totals["amount"]

    def _share(amount: Decimal) -> str | None:
        if grand is None or grand == Decimal("0"):
            return None
        return f"{(amount / grand * 100):.1f}"

    rows = [
        {
            "method_id": row.method_id,
            "method_code": row.method_code,
            "method_name": row.method_name,
            "count": row.count,
            "amount": _money(row.amount),
            "share_pct": _share(row.amount),
        }
        for row in view["rows"]
    ]
    details = [
        {
            "payment_id": row.payment_id,
            "payment_no": row.payment_no,
            "account_id": row.account_id,
            "account_no": row.account_no,
            "customer_name": row.customer_name,
            "method_name": row.method_name,
            # BR-PAY-012 — first-class, and BR-REP-014's whole point: a deposit
            # is visible AS a deposit and never inside a collection figure.
            "purpose": row.purpose,
            "confirmation": row.confirmation,
            # BR-PAY-021 — BOTH dates, always. The divergence a clerk needs to
            # see is exactly the one a single-date row hides.
            "posted_on": _iso(row.posted_on),
            "cleared_on": _iso(row.cleared_on),
            "amount": _money(row.amount),
        }
        for row in view["details"]
    ]
    report = _report(
        catalog.KEY_PAYMENTS_BY_METHOD,
        basis=view["basis"],
        window={"start": _iso(start), "end": _iso(end)},
        currency=currency,
        columns=("method_name", "count", "amount", "share_pct"),
        rows=rows,
        kpis=[
            _kpi(
                "total_received",
                _money(grand),
                reason_code=_no_currency_reason(
                    None if grand is None else "x",
                    totals["count"],
                    "cash_window_holds_more_than_one_currency",
                ),
            ),
            _kpi("payments", totals["count"], kind="count"),
            # BR-REP-014, made structural: the ONLY figure a collection
            # percentage may divide, published under its own name so a deposit
            # can never be folded into one by accident.
            _kpi("bill_purpose_received", _money(totals["bill_purpose_amount"])),
        ],
        totals={
            "count": totals["count"],
            "amount": _money(grand),
            "bill_purpose_amount": _money(totals["bill_purpose_amount"]),
        },
        unavailable=view["problems"],
        # `P2.23` — one row is one tender.
        grain="method",
    )
    report["details"] = details
    report["detail_columns"] = (
        "posted_on",
        "cleared_on",
        "account_no",
        "customer_name",
        "method_name",
        "purpose",
        "amount",
    )
    report["purposes"] = [
        {
            "purpose": entry["purpose"],
            "count": entry["count"],
            "amount": _money(entry["amount"]),
        }
        for entry in view["purposes"]
    ]
    return report


# ═══════════════════════════════════════════════════════════════════════════
# THE `journal_lines` DATASET'S REPORTS (2026-09-26, lane DS-LEDGER)
# ═══════════════════════════════════════════════════════════════════════════
# Four viewers over ONE dataset — `apps.ledger.journal_lines_dataset` and the
# ledger aggregates beside it. Each drawing was read AS AN IMAGE (B14 rule 42):
# R15 p055 · R16 p056 · R18 p057 · R21 p058.
#
# ⚠ **NOT ONE FIGURE IS COMPUTED HERE.** Every number is ledger's, read through
# `report_seams`, for BR-REP-002's reason and DEF-104's: four surfaces once
# disagreed about one balance because four of them worked it out.

#: R15's `Level` control (p055). `detail` is one row per GL account — what a
#: trial balance IS. `summary` rolls those rows up by ACCOUNT TYPE, which is the
#: same figures grouped, never a second derivation.
_TB_LEVELS: tuple[str, ...] = ("detail", "summary")


def trial_balance(params: Any) -> dict[str, Any]:
    """R15 — the period's trial balance, and whether the books FOOT.

    ⚠ **THE WARNING ON p055 IS THE WHOLE REPORT**, verbatim: *"Balanced pairs
    are a database guarantee, not a report's opinion. A difference other than
    zero here means the posting service has a defect, not that the report needs
    tuning."* So `difference` is published on every answer, it is Σ debits − Σ
    credits exactly as ledger struck it, and nothing here rounds, plugs or
    suppresses it. If it is not zero, `US-LED-004`'s red flag is the finding.

    ⚠ **`balanced` IS `None` — NEVER `False` — ON A NARROWED TABLE.** Balance is
    a property of an ENTRY; an account RANGE keeps some of each entry's lines,
    so its residue is not expected to foot and a `False` would accuse the
    posting service of a defect it does not have. `CR-060` C24 settled this one
    level up and this follows it rather than re-arguing it.

    ⚠ **IT DOES NOT PAGE AND THAT IS NOT AN `NFR-3` BREACH.** The grain is one
    GL ACCOUNT, so the row count is the tenant's chart of accounts — bounded by
    configuration and not by how many customers they have. `_report` omits the
    `page` key for exactly this case, which is how a reader tells *"this is all
    of it"* from *"this is page one"*. The `journal_lines` dataset underneath it
    pages; this aggregate over it has nothing to page.
    """
    start, end = _checked_window(params)
    account_from = params.get("account_from") or params.get("f.account_from") or None
    account_to = params.get("account_to") or params.get("f.account_to") or None
    level = str(params.get("level") or params.get("f.level") or "detail").lower()
    if level not in _TB_LEVELS:
        # `BR-SHL-011` — an invalid value falls back, never errors.
        level = "detail"

    view = seams.trial_balance(start=start, end=end)
    if view is None:  # pragma: no cover — ledger publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.trial_balance.unavailable")

    rows = list(view["rows"])
    narrowed = bool(account_from or account_to)
    if account_from:
        rows = [row for row in rows if (row["code"] or "") >= str(account_from)]
    if account_to:
        rows = [row for row in rows if (row["code"] or "") <= str(account_to)]

    unavailable = list(view.get("unavailable") or ())
    if narrowed:
        unavailable.append(
            {
                "code": "a_narrowed_trial_balance_cannot_state_whether_the_books_foot",
                "br_ref": "BR-LED-007 · CR-060 C24",
                "detail": (
                    "An account range keeps part of each entry, so the residue is not expected "
                    "to foot. The difference is published because it is a real figure about the "
                    "rows in front of you; it is not evidence about the posting service. Clear "
                    "the range to get the verdict BR-LED-007 is about."
                ),
            }
        )

    # ⚠ **THE FOOTER IS Σ OF THE ROWS ON THE REPORT, ALWAYS.** When no range is
    # set these are ledger's own totals, unchanged. When one IS set they are the
    # sum of the presented rows, because a footer describing rows a filter
    # excluded is the trap `ar_aging` names and `P2.19` refuses.
    if narrowed:
        debits = sum((row["debit"] for row in rows), Decimal("0"))
        credits = sum((row["credit"] for row in rows), Decimal("0"))
        opening = sum((row["opening"] for row in rows), Decimal("0"))
        closing = sum((row["closing"] for row in rows), Decimal("0"))
        balanced = None
    else:
        debits = view["total_debit"]
        credits = view["total_credit"]
        opening = view["total_opening"]
        closing = view["total_closing"]
        balanced = view["balanced"]
    difference = debits - credits

    if level == "summary":
        rows = _rolled_up_by_type(rows)

    presented = [
        {
            "account_id": row["account_id"],
            # B14 rule 31 — the CODE is a chart-of-accounts code a finance
            # officer types and reads, not a database id. The id travels for a
            # drill-back and is never the visible value.
            "code": row["code"],
            "name": row["name"],
            "type": row["type"],
            "opening": _money(row["opening"]),
            "debit": _money(row["debit"]),
            "credit": _money(row["credit"]),
            "closing": _money(row["closing"]),
        }
        for row in rows
    ]
    return _report(
        catalog.KEY_TRIAL_BALANCE,
        basis=view["basis"],
        window={"start": _iso(start), "end": _iso(end)},
        currency=view["currency"],
        columns=("code", "name", "opening", "debit", "credit", "closing"),
        # `DEF-REP-6902` — four money columns this query derives. `debit` and
        # `credit` ARE declared by `journal_lines` and read correctly; `opening`
        # and `closing` are this query's own and printed `-171.160000` beside
        # them, so one row carried two precisions for the same kind of figure.
        column_meta={
            name: {"type": "money", "unit": None, "unit_from": None,
                   "money_basis": view["basis"], "scale": 4}
            for name in ("opening", "debit", "credit", "closing")
        },
        rows=presented,
        kpis=[
            _kpi("debits", _money(debits)),
            _kpi("credits", _money(credits)),
            _kpi(
                "difference",
                _money(difference),
                # p055's tile reads `$0.00` with *"Balanced"* under it. The word
                # is the VERDICT and it is absent on a narrowed table rather
                # than guessed — BR-REP-024, and B14 rule 33 keeps it to one.
                detail=None if balanced is None else ("balanced" if balanced else "out_of_balance"),
                reason_code=(
                    None if balanced is not None else "range_filter_makes_footing_unverifiable"
                ),
            ),
        ],
        totals={
            "opening": _money(opening),
            "debit": _money(debits),
            "credit": _money(credits),
            "closing": _money(closing),
            "difference": _money(difference),
            "balanced": balanced,
            "level": level,
            "filtered": narrowed,
        },
        unavailable=unavailable,
    )


def _rolled_up_by_type(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """p055's `Level: Summary` — the SAME rows grouped by account type.

    A roll-up and not a second query: every figure is the detail row's, added.
    Debits, credits, opening and closing are all fully additive across accounts
    (brief §7.2.2), so this addition is lawful in the one direction it happens
    in. Nothing is summed across TIME here and nothing may be.
    """
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["type"] or "unclassified"
        bucket = buckets.setdefault(
            key,
            {
                "account_id": None,
                "code": key,
                "name": key,
                "type": key,
                "opening": Decimal("0"),
                "debit": Decimal("0"),
                "credit": Decimal("0"),
                "closing": Decimal("0"),
            },
        )
        for column in ("opening", "debit", "credit", "closing"):
            bucket[column] += row[column]
    return [buckets[key] for key in sorted(buckets)]


#: R16's sort vocabulary — the dataset's own, read from the owning module at
#: call time rather than copied, so a caret this report offers and the query
#: declines cannot exist (hard-won law 2's mirror).
def _line_sorts() -> tuple[str, ...]:
    found = seams.resolve_constant("ledger", "LINE_SORTS", kind="journal_lines_dataset")
    return tuple(found) if found else ("posted_on",)


def _line_default_sort() -> str:
    found = seams.resolve_constant("ledger", "LINE_DEFAULT_SORT", kind="journal_lines_dataset")
    return str(found) if found else "posted_on"


def journal_export(params: Any) -> dict[str, Any]:
    """R16 — every posted journal LINE in the period, and the batches sent out.

    ⚠ **THIS IS THE DATASET ITSELF, AT ITS OWN GRAIN.** R15 above and R18 below
    are aggregates over these rows; this one serves the rows. It is why the
    `journal_lines` dataset had to exist at all — an aggregate cannot be
    un-aggregated, and p056 draws a line-level export.

    ⚠ **IT PAGES, SORTS AND FILTERS IN SQL** (`NFR-3`, brief §7.5), and
    `per=all` is the EXPORT's door — the whole filtered set, no ceiling, for the
    reason `NFR-5` gives and `ar_aging` and `billing_register` already take.

    ⚠ **THE BATCH TABLE IS NOT PAGED AND SAYS SO BY OMISSION.** p056 draws the
    export history under the KPI strip; a batch is one period × one target, so
    the list is bounded by how long the utility has been live and not by how
    many customers it has. `_report` omits the `page` key for that case. The
    LINES are the unbounded half and they page.

    ⚠ **Idempotent by batch** (p056's own warning): re-exporting a batch
    produces the same file and does not double-post. That is
    `apps.ledger.exports`' guarantee — `uq_export_batches_period_target` and the
    content hash — and this READ has no way to violate it, because it writes
    nothing. Stated here so the next reader does not go looking for it.
    """
    start, end = _checked_window(params)
    target = params.get("target") or params.get("f.target") or None
    source_type = params.get("source_type") or params.get("f.source_type") or None
    search = (params.get("q") or params.get("search") or "").strip() or None
    account_from = params.get("account_from") or params.get("f.account_from") or None
    account_to = params.get("account_to") or params.get("f.account_to") or None
    service = params.get("service") or params.get("f.service") or None
    sorts = _line_sorts()
    sort = params.get("sort") or _line_default_sort()
    if sort not in sorts:
        sort = _line_default_sort()
    direction = "asc" if str(params.get("dir") or "desc").lower() == "asc" else "desc"
    page_no = _page_number(params.get("page"))
    whole = str(params.get("per") or "").lower() == "all"
    per = None if whole else clamp_page_size(params.get("per"))

    view = seams.journal_lines(
        start=start,
        end=end,
        account_from=account_from,
        account_to=account_to,
        service_code=service,
        source_type=source_type,
        search=search,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
    )
    if view is None:  # pragma: no cover — ledger publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.journal_export.unavailable")

    totals = view["totals"]
    rows = [
        {
            "line_id": row.line_id,
            "posted_on": _iso(row.posted_on),
            "entry_id": row.entry_id,
            "reference": row.reference,
            "account_code": row.account_code,
            "account_name": row.account_name,
            "narrative": row.narrative,
            "debit": _money(row.debit),
            "credit": _money(row.credit),
            # ⚠ Served NULL on every row, deliberately. The dataset declares a
            # `balance` column and the grain cannot carry it — see
            # `journal_lines_dataset.GAP_BALANCE_IS_NOT_A_LINE_FACT`, which
            # travels in `unavailable` so the absence has a reason attached
            # rather than being a blank a reader has to interpret.
            "balance": None,
            "service": row.service_label,
            "account_no": row.customer_account_label,
            "source_type": row.source_type,
        }
        for row in view["rows"]
    ]

    batches = seams.export_history(target=target) or ()
    batch_rows = [
        {
            "batch_id": batch["batch_id"],
            "batch_no": batch["batch_no"],
            "period": batch["period"],
            "target": batch["target"],
            "entries": batch["entries"],
            "debits": _money(batch["total_debits"]),
            "credits": _money(batch["total_credits"]),
            "exported_at": batch["created_at"].isoformat() if batch["created_at"] else None,
            "ack_state": batch["ack_state"],
        }
        for batch in batches
    ]

    report = _report(
        catalog.KEY_JOURNAL_EXPORT,
        basis=view["basis"],
        window={"start": _iso(start), "end": _iso(end)},
        currency=view["currency"],
        columns=(
            "posted_on",
            "reference",
            "account_code",
            "account_name",
            "narrative",
            "debit",
            "credit",
        ),
        rows=rows,
        kpis=[
            # p056's strip: ENTRIES · LINES · VALUE · LAST EXPORT. `entries` is
            # the count of distinct entries behind the lines and is served as a
            # null-with-a-reason rather than as the line count wearing another
            # label, which would be a tile that is simply wrong.
            _kpi("lines", totals["lines"], kind="count"),
            _kpi("value", _money(totals["debit"])),
            _kpi(
                "difference",
                _money(totals["difference"]),
                detail=(
                    None
                    if view["balanced"] is None
                    else ("balanced" if view["balanced"] else "out_of_balance")
                ),
                reason_code=(
                    None if view["balanced"] is not None else "filter_makes_footing_unverifiable"
                ),
            ),
            _kpi(
                "last_export",
                batch_rows[0]["exported_at"] if batch_rows else None,
                kind="date",
                reason_code=None if batch_rows else "nothing_has_been_exported_yet",
            ),
        ],
        totals={
            "debit": _money(totals["debit"]),
            "credit": _money(totals["credit"]),
            "difference": _money(totals["difference"]),
            "lines": totals["lines"],
            "balanced": view["balanced"],
            "filtered": view["filtered"],
        },
        unavailable=view["problems"],
        page=(
            None
            if whole
            else {
                "page": view["page"],
                "per": per,
                "total": view["total"],
                "pages": view["pages"],
            }
        ),
    )
    report["batches"] = batch_rows
    report["batch_columns"] = (
        "batch_no",
        "period",
        "entries",
        "debits",
        "credits",
        "exported_at",
        "ack_state",
    )
    return report


def tax_remittance(params: Any) -> dict[str, Any]:
    """R18 — what each authority was charged, what was sent, what is still due.

    ⚠ **TWO BASES IN ONE REPORT, LABELLED PER ROW** — p057's warning verbatim:
    *"Franchise fees read the clearing date and the others read posting — a
    dual-basis report is correct and unlabelled money is a contract failure."*

    So BR-REP-001 is met TWICE here and the two labels are different things.
    `basis` on the report is the BILLED column's — posting — because that is the
    definition's seeded basis and the dominant one on the table. `totals.bases`
    carries both (`billed: posting`, `collected: clearing`), and every ROW
    carries `basis`: the one that authority actually files on, read from the
    stored per-authority setting. **A row whose basis nobody has chosen is NULL
    and is named in `unavailable`, never defaulted** — a default would file a
    utility's return on the wrong basis in its first month, and ledger already
    reports those authorities BY NAME rather than letting a first save hide
    them.

    ⚠ **THE OUTSTANDING COLUMN IS PER BASIS AND IS NEVER ONE NUMBER.** LE-3's
    whole point is that State remits on collected while County remits on
    billed; a single `outstanding` would have to pick one and be wrong for the
    other. Two columns, as ledger publishes them.

    ⚠ **NOT ONE FIGURE IS ADDED HERE.** `totals` is ledger's own — including
    its `None` where any authority's figure is absent, which is BR-REP-024
    doing its job: a partial sum under a heading a tax return is filed from
    reads as the whole and is not.

    ⚠ **THE RATE IS SIX DECIMALS AND IS NOT TRIMMED** (hard rule 2, and p067's
    sibling warning: *"Rates show four decimals and percentages six, displayed
    at the precision the rule stores"*). This table serves no rate column of its
    own — the drawing's RATE is rating's stored percentage and reaches the
    screen at its stored precision; nothing here rounds it to two.
    """
    start, end = _checked_window(params)
    authority = params.get("authority") or params.get("f.authority") or None

    view = seams.remittance_by_authority(start=start, end=end)
    if view is None:  # pragma: no cover — ledger publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.tax_remittance.unavailable")

    source = list(view["rows"])
    narrowed = False
    if authority:
        # ⚠ BY THE ACCOUNT CODE A CLERK READS, never by the database id —
        # B14 rule 31. `2200-01` is what the tenant typed and what p057's
        # Authority control offers.
        narrowed = True
        source = [row for row in source if str(row.code) == str(authority)]

    rows = [
        {
            "authority_id": row.account_id,
            "account_code": row.code,
            # The authority as RATING knows it where billing could answer, and
            # the ACCOUNT's own name otherwise. Both are published because
            # ledger publishes both and a disagreement between them is a chart
            # fault a picked name would hide.
            "authority": row.authority_name or row.name,
            "account_name": row.name,
            # ⚠ PER ROW. The report's `basis` is the dominant one; this is the
            # basis this authority files on, and p057 draws it as a column
            # precisely because the two disagree.
            "basis": row.remitting_basis,
            "billed": _money(row.billed),
            "collected": _money(row.collected),
            "remitted": _money(row.remitted),
            "outstanding_billed": _money(row.outstanding_billed),
            "outstanding_collected": _money(row.outstanding_collected),
            "billed_from_bills": _money(row.billed_from_bills),
            "problems": list(row.problems),
        }
        for row in source
    ]

    totals = view["totals"]
    bases = view["basis"]
    # ⚠ **`.get()` AND NOT `[...]`, AND THE SUITE IS WHY.** `remittance_by_authority`
    # has TWO return shapes: the full table, and a short one for a tenant with no
    # tax-payable account at all, whose `totals` carries four keys and not six.
    # Indexing `outstanding_billed` unconditionally raised `KeyError` — a 500 on
    # R18 for every utility that charges no tax, which is a real and ordinary
    # tenant. Found by `test_tax_remittance_labels_a_basis_on_every_row_and_carries_both`
    # before this shipped; the absent figures are served as null beside their
    # reason, which is what BR-REP-024 asks for anyway.
    outstanding_billed = totals.get("outstanding_billed")
    outstanding_collected = totals.get("outstanding_collected")
    # The two shapes also name their gap list differently — `problems` on the
    # full path, `unavailable` on the short one. Both are read.
    unavailable = list(view.get("problems") or view.get("unavailable") or ())
    unbased = [row["authority"] for row in rows if not row["basis"]]
    if unbased:
        unavailable.append(
            {
                "code": "an_authority_has_no_remitting_basis_chosen",
                "br_ref": "BR-LED-002 · PO ruling 2026-08-12",
                "detail": (
                    "Both bases are lawful and the choice is the utility's, so these "
                    f"authorities are served with a null basis rather than a default: "
                    f"{', '.join(str(name) for name in unbased)}. The choice is made on the "
                    "Finance controls page, keyed by the authority's own 2200-nn account code."
                ),
            }
        )

    return _report(
        catalog.KEY_TAX_REMITTANCE,
        basis=bases["billed"],
        window={"start": _iso(start), "end": _iso(end)},
        currency=view["currency"],
        columns=(
            "authority",
            "basis",
            "billed",
            "collected",
            "remitted",
            "outstanding_billed",
            "outstanding_collected",
        ),
        # `DEF-REP-6902` — five money columns this query derives; the
        # `journal_lines` dataset declares none of them.
        column_meta={
            name: {"type": "money", "unit": None, "unit_from": None,
                   "money_basis": bases["billed"], "scale": 4}
            for name in (
                "billed",
                "collected",
                "remitted",
                "outstanding_billed",
                "outstanding_collected",
            )
        },
        rows=rows,
        kpis=[
            _kpi(
                "collected",
                _money(totals["collected"]),
                reason_code=(
                    None
                    if totals["collected"] is not None
                    else "an_authority_collected_figure_is_not_derivable"
                ),
            ),
            _kpi("billed", _money(totals["billed"])),
            _kpi("remitted", _money(totals["remitted"])),
            _kpi(
                "due_billed",
                _money(outstanding_billed),
                reason_code=(
                    None if outstanding_billed is not None else "this_tenant_charges_no_tax"
                ),
            ),
            _kpi(
                "due_collected",
                _money(outstanding_collected),
                reason_code=(
                    None
                    if outstanding_collected is not None
                    else "an_authority_collected_figure_is_not_derivable"
                ),
            ),
        ],
        totals={
            "billed": _money(totals["billed"]),
            "collected": _money(totals["collected"]),
            "remitted": _money(totals["remitted"]),
            "outstanding_billed": _money(outstanding_billed),
            "outstanding_collected": _money(outstanding_collected),
            "authorities": len(rows),
            # BR-REP-001, both halves, on the wire rather than in a comment.
            "bases": dict(bases),
            "filtered": narrowed,
        },
        unavailable=unavailable,
    )


def close_pack(params: Any) -> dict[str, Any]:
    """R21 — the period's tie-outs, and whether a drift blocks the release.

    ⚠ **p058's warning is a RELEASE RULE and not a report finding**: *"A drift
    here is a release blocker, not a report finding."* That is BR-LED-007, which
    `apps.ledger.tie_out` already implements and publishes as a field rather
    than leaving a screen to derive — a screen that computed it could render
    three red rows and no blocker. This viewer RENDERS that field; it does not
    re-decide it.

    ⚠ **A ROW NOBODY COULD COMPUTE BLOCKS TOO, AND IS NOT A GREEN.**
    `TieOutRow.blocks_release` is `state != agreed`, so `unverifiable` counts —
    folding it in with the agreements is how a release ships on a check that
    never ran. `difference` is `None` there rather than `0.00`, because a delta
    struck against an absence is a fabricated number wearing a precise one's
    clothes.
    """
    start, end = _checked_window(params)
    view = seams.tie_outs(period_start=start, period_end=end)
    if view is None:  # pragma: no cover — ledger publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.close_pack.unavailable")

    rows = [
        {
            "check": row.subledger,
            # p058 draws SOURCE A / SOURCE B as words a finance officer reads.
            # They are the two records of one fact BR-LED-007 compares.
            "source_a": "ledger control",
            "value_a": _money(row.gl),
            "source_b": "subledger register",
            "value_b": _money(row.register),
            "difference": _money(row.drift),
            "result": row.state,
            "basis": row.basis,
            "causes": [dict(cause) for cause in row.causes],
        }
        for row in view["rows"]
    ]
    currencies = {row.currency for row in view["rows"] if row.currency}
    return _report(
        catalog.KEY_CLOSE_PACK,
        basis=view["basis"],
        window={"start": _iso(start), "end": _iso(end)},
        # DEF-081 — one currency or no label. Two codes across the tie-outs is
        # not a book this report can head with a single CHAR(3).
        currency=next(iter(currencies)) if len(currencies) == 1 else None,
        columns=(
            "check",
            "source_a",
            "value_a",
            "source_b",
            "value_b",
            "difference",
            "result",
        ),
        # `DEF-REP-6902` — the three tie-out figures are money this query
        # derives; the `journal_lines` dataset declares none of them.
        column_meta={
            name: {"type": "money", "unit": None, "unit_from": None,
                   "money_basis": view["basis"], "scale": 4}
            for name in ("value_a", "value_b", "difference")
        },
        rows=rows,
        kpis=[
            _kpi("checks", len(rows), kind="count"),
            _kpi("drifting", len(view["drifting"]), kind="count"),
            _kpi("unverifiable", len(view["unverifiable"]), kind="count"),
        ],
        totals={
            "checks": len(rows),
            "drifting": list(view["drifting"]),
            "unverifiable": list(view["unverifiable"]),
            # BR-LED-007's own words, served as a FIELD. US-LED-004 TC-5: there
            # is no dismiss path, and the absence is on the wire so a client
            # cannot look for one and quietly not find it.
            "release_blocked": view["release_blocked"],
            "dismissible": view["dismissible"],
        },
        unavailable=(),
    )


#: key → the function that answers it. A dict rather than a chain of `if`s so
#: `apps/reports/api.py`'s refusal can enumerate the vocabulary from the same
#: object that dispatches it — a served key and an advertised key cannot diverge.
# ════════════════════════════════════════════════════════════════════════════
# THE `invoices` DATASET QUERY — one reviewed read, every definition built on it
# ════════════════════════════════════════════════════════════════════════════
#
# The four functions above are PER-REPORT viewers: one function, one card. This
# is the other shape the brief asks for and the one the whole framework leans
# on — *"46 reports sit on 9 datasets"* (§05) and *"every arrow into the
# database passes through a reviewed dataset"* (§08 p90, read as an image per
# B14 rule 42). A definition names columns; this executes the dataset behind
# them.
#
# ⚠ **IT REFUSES SEVEN OF THE EIGHT `invoices` DEFINITIONS BY NAME, AND THAT
#   IS THE DELIVERABLE RATHER THAN A SHORTFALL.**
# ──────────────────────────────────────────────────────────────────────────
# `reports/0003` seeds eight definitions onto the `invoices` dataset. Read
# against their OWN DRAWINGS (p49–p73, as images), only one of them is a
# report about bills:
#
#   R5  Billing Register       bills & lines          ← this dataset, exactly
#   R4  Bill Run Readiness     bills + READS          one row per ACCOUNT IN A
#                                                     CYCLE, with a route, a
#                                                     check and a hold reason
#   R6  Bill Adjustments       bills & lines          one row per ADJUSTMENT —
#                                                     `adjustments`, with a
#                                                     reason, a raiser and an
#                                                     approver
#   R7  Bill Print File        bills & lines          one row per PRINT BATCH,
#                                                     with pages and a file
#   R13 Write-Offs & Late Fees bills & lines          write-offs are PAYMENTS'
#                                                     `write_offs` table; late
#                                                     fees are invoice lines
#   R24 Statement              accounts + invoices    a running balance mixing
#                              + PAYMENTS             charges and credits
#   R38 Adjustment Register    invoices + JOURNAL     the R6 rows again, with a
#                              LINES                  reference and a threshold
#   R44 My Bills & Payments    invoices + PAYMENTS    R24 for one customer
#
# **Six of the seven name a source this dataset does not own, and all seven
# state a grain that is not one bill.** §7.2 is explicit that a dataset states
# ONE grain, so serving them from here would mean rendering a bill register
# under the title *Bill Print File* — rows that are real, totals that foot, and
# an answer to a question nobody asked. That is worse than a refusal, because a
# refusal is visible and a wrong report is not.
#
# So each of the seven gets a refusal that NAMES what it draws and what this
# dataset produces. `DEF-REP-6835` is the register row, and the reasoning is in
# `12-governance/02-decision-log.md` dated 2026-09-26.
#
# ⚠ **`billing_register` KEEPS ITS OWN VIEWER AND IS NOT MOVED ONTO THIS.**
# It was rebuilt on 2026-09-26 by another lane, it is measured, and its payload
# is asserted by `tests/test_cr142_p2_read_path.py`. Moving a shipped, measured
# read onto a new path on the same day is a behaviour change wearing a
# refactor's clothes. What DOES prove the two agree is a test that runs the
# same parameters through both and compares the rows — the same discipline
# `P0.5` applied to the viewer and the export.

#: What each `invoices` definition DRAWS, for the refusal that names it. Data
#: rather than an `if` chain, because the next dataset lane needs the same
#: table and a chain is not a thing a test can read.
#:
#: Transcribed from the drawings on p49–p73 read as IMAGES (B14 rule 42): the
#: text layer loses column order and alignment entirely. A sibling lane
#: (REP-REGISTER) owns the written register of all 46; this is the eight this
#: dataset is asked for, held here because a refusal must carry its reason.
INVOICES_DEFINITIONS_NOT_SERVED: dict[str, str] = {
    "bill_run_readiness": (
        "Bill Run Readiness draws one row per ACCOUNT IN A CYCLE — route, check, "
        "detail and usage for the accounts a clerk fixes BEFORE the run — and its "
        "four tiles count accounts, not bills. The invoices dataset produces one "
        "row per bill, and a bill does not exist yet for a held account."
    ),
    "bill_adjustments": (
        "Bill Adjustments draws one row per ADJUSTMENT — date, bill number, reason, "
        "who raised it and who approved it — from `adjustments`. The invoices "
        "dataset produces one row per bill and carries no reason, raiser or "
        "approver. An adjustment is a NEW ROW and never an edit (hard rule 4), "
        "which is why the report exists and why it cannot be a bill listing."
    ),
    "bill_print_file": (
        "Bill Print File draws one row per PRINT BATCH — batch, cycle, bills, pages, "
        "built, status and the file — and states its 137 suppressed eBill enrolments "
        "rather than letting them go missing. The invoices dataset produces one row "
        "per bill and has no batch, no page count and no file."
    ),
    "write_offs_and_late_fees": (
        "Write-Offs & Late Fees draws write-offs from payments' own `write_offs` "
        "table beside late fees from invoice lines, and its warning is that the two "
        "must stay separate — write-offs are excluded from the collection rate "
        "because folding them in would flatter the figure. Half its rows are not "
        "billing's, so half of this report cannot come from the invoices dataset."
    ),
    "statement": (
        "Statement draws a running balance — opening, charges, credits, closing — "
        "over accounts, invoices AND payments, at whichever of four subjects the "
        "`subject` parameter names. The invoices dataset produces charges only, so "
        "serving it here would show every bill and no payment and still print a "
        "closing balance."
    ),
    "my_bills_and_payments": (
        "My Bills & Payments is Statement for one signed-in customer and draws bills "
        "AND payments in one list. The invoices dataset produces bills only — a "
        "customer would open their statement, see every charge, see none of what "
        "they had paid, and read a balance that agreed with neither."
    ),
    "adjustment_register": (
        "Adjustment Register draws the same adjustment rows as R6 with a reference, "
        "an approval threshold and the journal line behind each one. Its grain is an "
        "adjustment and its second source is journal lines, which another dataset "
        "owns. The invoices dataset produces one row per bill."
    ),
}


class DatasetCannotServe(NotImplementedError):
    """This definition's dataset is executable and this DEFINITION is not.

    Distinct from `runner.DatasetNotExecutable`, which means *no query exists
    for this dataset at all*, because the two need opposite work: one waits for
    a dataset lane and the other waits for a ruling about which dataset the
    definition belongs on. A single refusal covering both would send the next
    reader to build a query that already exists.
    """

    def __init__(self, key: str, reason: str) -> None:
        super().__init__(f"{key}: {reason}")
        self.key = key
        self.reason = reason


def _dataset_sorts() -> tuple[str, ...]:
    """Billing's OWN sort tuple, read through the seam at call time.

    So a caret this module offers and the read model declines cannot exist
    (`BR-REP-006`, and hard-won law 2's mirror). The fallback is the read
    model's own default and never a wider set.
    """
    found = seams.invoices_dataset_constant("DATASET_SORTS")
    return tuple(found) if found else (_dataset_default_sort(),)


def _dataset_default_sort() -> str:
    found = seams.invoices_dataset_constant("DATASET_DEFAULT_SORT")
    return str(found) if found else "invoice_no"


def _dataset_default_direction() -> str:
    found = seams.invoices_dataset_constant("DATASET_DEFAULT_DIRECTION")
    return str(found) if found else "asc"


#: The `invoices` dataset's declared columns, in the order R5's drawing heads
#: them. A definition with an empty `columns` list means *every column the
#: dataset declares*, and this is that list in a reader's order rather than a
#: declaration's.
INVOICES_COLUMNS: tuple[str, ...] = (
    "invoice_no",
    "account_no",
    "customer_name",
    "bill_type",
    "status",
    "cycle",
    "services",
    "issued_on",
    "posted_on",
    "due_date",
    "usage",
    "base",
    "usage_revenue",
    "tax",
    "amount",
    "flag",
)


def _dataset_row(row: Any) -> dict[str, Any]:
    """One `DatasetRow` on the wire, at hard rule 2's precision.

    Money leaves as its EXACT decimal string through `_money` — B4 rounds at
    finalization and display and this is neither. Usage leaves as `{quantity,
    unit}` pairs through `_quantity`, never a bare number, because a bill of
    684 kWh and 26.24 kgal has two usages and adding them is meaningless
    (hard rule 3).
    """
    return {
        "invoice_id": row.invoice_id,
        "invoice_no": row.invoice_no,
        "account_id": row.account_id,
        "account_no": row.account_no,
        "customer_name": row.customer_name,
        "bill_type": row.bill_type,
        "status": row.status,
        "cycle": row.cycle_code,
        "services": list(row.services),
        "issued_on": _iso(row.issued_on),
        "posted_on": _iso(row.posted_on),
        "due_date": _iso(row.due_date),
        "usage": _quantity(row.usage, row.counted_units),
        "base": _money(row.base),
        "usage_revenue": _money(row.usage_revenue),
        "tax": _money(row.tax),
        "amount": _money(row.amount),
        "flag": "estimated" if row.estimated else None,
    }


def _dataset_arguments(params: Any) -> dict[str, Any]:
    """The bound parameters as the read model's arguments.

    ⚠ **BOTH SPELLINGS OF EVERY FILTER.** The shipped screens send their
    filters DOTTED — `f.class`, `f.service`, `f.bill_type` — and the runner
    passes the ORIGINAL key through on purpose (*"this file does not get to
    rename anybody's wire"*). A query reading only the bare names would be
    handed a request with every filter missing: the report would render, the
    page would look right, and it would report the WHOLE book under a chip
    saying *Residential*.
    """

    def pick(name: str) -> Any:
        return params.get(name) or params.get(f"f.{name}") or None

    return {
        "bill_type": pick("bill_type"),
        "service_code": pick("service"),
        "cycle": pick("cycle"),
        "status": pick("status"),
        "consumer_class": pick("class"),
        "search": (params.get("q") or params.get("search") or "").strip() or None,
    }


def invoices_dataset(params: Any, *, key: str | None = None) -> dict[str, Any]:
    """The `invoices` dataset, one PAGE, shaped for the S46 viewer.

    The brief's left read path (§8.2 p91): *"page 1 only · never the whole
    result"*, with `LIMIT`, `OFFSET` and `ORDER BY` applied in SQL and never in
    Python. The totals are SQL aggregates over the whole FILTERED set, so the
    footer foots to the report whether a page is cut or not — CLAUDE.md's own
    resolution of `DEF-PAY-4221`, quoted.

    ⚠ **`per=all` IS THE EXPORT'S DOOR AND IT IS NOT HOW A FILE IS BUILT.** It
    exists so a caller can ask for the whole filtered set in one shape for
    comparison; the FILE comes from `invoices_dataset_stream`, a generator that
    takes no page size at all. That separation is the defect caught on the
    register the day it started paging, when the export silently inherited the
    screen's fifty rows.
    """
    resolved = key or catalog.KEY_BILLING_REGISTER
    refusal = INVOICES_DEFINITIONS_NOT_SERVED.get(resolved)
    if refusal is not None:
        raise DatasetCannotServe(resolved, refusal)

    start, end = _checked_window(params)
    arguments = _dataset_arguments(params)
    if arguments["bill_type"] is not None and arguments["bill_type"] not in catalog_bill_types():
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="reports.register.unknown_bill_type",
            params={"bill_type": arguments["bill_type"], "values": list(catalog_bill_types())},
            field_errors=[{"field": "bill_type", "code": errors.VAL_UNKNOWN_LOOKUP}],
        )

    sorts = _dataset_sorts()
    sort = params.get("sort") or _dataset_default_sort()
    if sort not in sorts:
        # `BR-SHL-011` — invalid values fall back or clamp, NEVER error. A saved
        # link carrying a sort this dataset retired still opens.
        sort = _dataset_default_sort()
    raw_direction = params.get("dir")
    direction = (
        _dataset_default_direction()
        if raw_direction in (None, "")
        else ("asc" if str(raw_direction).lower() == "asc" else "desc")
    )
    page_no = _page_number(params.get("page"))
    whole = str(params.get("per") or "").lower() == "all"
    per = None if whole else clamp_page_size(params.get("per"))

    view = seams.invoices_dataset(
        start=start,
        end=end,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
        **arguments,
    )
    if view is None:  # pragma: no cover — billing publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    currency = view["currency"]
    return _report(
        resolved,
        basis=view["basis"],
        window={"start": _iso(start), "end": _iso(end)},
        currency=currency,
        columns=INVOICES_COLUMNS,
        rows=[_dataset_row(row) for row in view["rows"]],
        kpis=[
            _kpi("bills", totals["bills"], kind="count", detail=_money(totals["billed"])),
            _kpi(
                "average_bill",
                _money(totals["average_bill"]),
                reason_code=None if totals["average_bill"] is not None else "no_bills_in_window",
            ),
            _kpi("estimated", totals["estimated"], kind="count"),
            # A14's fourth tile. NULL with its reason, never 0 — exceptions are
            # keyed to a RUN and this window may span several, so there is no
            # single count to state.
            _kpi(
                "exceptions",
                None,
                kind="count",
                reason_code="exception_count_is_per_run_not_per_window",
            ),
        ],
        totals={
            "bills": totals["bills"],
            "billed": _money(totals["billed"]),
            "base": _money(totals["base"]),
            "usage_revenue": _money(totals["usage_revenue"]),
            "tax": _money(totals["tax"]),
            # ⚠ NO `usage` TOTAL, AND THE ABSENCE IS THE RULE BEING OBEYED.
            # `usage` is declared WITHIN-SERVICE additive (§7.2.2): gallons plus
            # kilowatt-hours is not a number. The footer that renders this shows
            # an em-dash and the reason for a measure it may not sum, and a
            # number here would defeat that refusal before it was reached.
        },
        unavailable=view["problems"],
        page=None
        if whole
        else {
            "page": view["page"],
            "per": per,
            "total": view["total"],
            "pages": max(1, -(-int(view["total"] or 0) // per)),
        },
    )


def invoices_dataset_rows(params: Any, *, key: str | None = None) -> Any:
    """EVERY ROW of the `invoices` dataset, from a generator — the right path.

    §8.2 p91: *"every row · never in memory · never blocks the screen"*. It
    takes no `page` and no `per`, so an export cannot inherit a screen's fifty
    rows by passing the wrong argument — there is no argument to pass.
    """
    resolved = key or catalog.KEY_BILLING_REGISTER
    refusal = INVOICES_DEFINITIONS_NOT_SERVED.get(resolved)
    if refusal is not None:
        raise DatasetCannotServe(resolved, refusal)

    start, end = _checked_window(params)
    arguments = _dataset_arguments(params)
    sorts = _dataset_sorts()
    sort = params.get("sort") or _dataset_default_sort()
    if sort not in sorts:
        sort = _dataset_default_sort()
    raw_direction = params.get("dir")
    direction = (
        _dataset_default_direction()
        if raw_direction in (None, "")
        else ("asc" if str(raw_direction).lower() == "asc" else "desc")
    )

    stream = seams.invoices_dataset_stream(
        start=start, end=end, sort=sort, direction=direction, **arguments
    )
    if stream is None:  # pragma: no cover — billing publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield _dataset_row(row)


# ═══ THE `journal_lines` DATASET, ON THE DATASET PATH ══════════════════════
#
# ⚠ **THE QUERY HAS EXISTED SINCE 2026-09-26 AND NOTHING COULD REACH IT THROUGH
# A DEFINITION (`DEF-REP-6876`).** `apps/ledger/journal_lines_dataset.py` landed
# with lane DS-LEDGER, `report_seams.journal_lines` was wired to it, four
# per-KEY viewers were built on it — and `DATASET_QUERIES` held one entry,
# `invoices`. So `runner.queries_for` found no dataset fallback and the OTHER
# five definitions on this dataset raised `DatasetNotExecutable` naming a dataset
# that was, in fact, executable. The refusal was true of the registry and false
# of the product, which is the hardest kind of refusal to act on: it sends the
# next reader to build a query that already exists.

#: The `journal_lines` dataset's declared columns, in R15's reading order.
JOURNAL_LINES_COLUMNS: tuple[str, ...] = (
    "posted_on",
    "account_code",
    "account_name",
    "reference",
    "narrative",
    "debit",
    "credit",
    "balance",
)

#: Definitions on this dataset that it may NOT serve, each with the reason a
#: reader can act on. Same posture as `INVOICES_DEFINITIONS_NOT_SERVED`: a NAMED
#: refusal, never a plausible report over the wrong rows.
#:
#: ⚠ **THE FOUR PER-KEY VIEWERS ARE ABSENT FROM THIS TABLE ON PURPOSE.**
#: `runner.queries_for` checks `VIEWERS` first, so trial balance, journal export,
#: tax remittance and close pack never reach this function at all.
JOURNAL_LINES_DEFINITIONS_NOT_SERVED: dict[str, str] = {
    "account_ledger": (
        "Ledger (R25) draws ONE subject's running balance — account, customer, premises "
        "or unit, whichever the `subject` parameter names — with a carry-forward that "
        "survives a page. Two things stop the dataset serving it, and both are "
        "structural. The dataset declares no `subject` and no `account` filter, so "
        "`runner.bind` would DROP them and this report would serve every account's "
        "lines under one account's heading. And `balance` is null on every row of this "
        "grain: a running balance is a property of an ordered sequence, not of a line. "
        "`apps.ledger.reporting.account_ledger` computes both and is what S59 serves "
        "today; it is not replaced by registering this dataset."
    ),
    "regulatory_filing": (
        "Regulatory Filing (R39) is dated on the EVENT basis and this dataset is dated "
        "on the POSTING basis — its own `BASIS` constant says `posting` and every figure "
        "comes off `journal_entries.entry_date`, the book date. Serving it here would "
        "answer a filing with a period the regulator did not ask about, and BR-REP-001 "
        "exists so a money report cannot state the wrong one. The basis has to be "
        "settled before the rows are."
    ),
    "external_reconciliation": (
        "External Reconciliation (R40) matches our journal against what the other "
        "system says, so half of every row is the OTHER system's figure. The dataset "
        "produces our lines and has no external side at all — served here it would show "
        "one column of a two-column check and a difference computed against nothing."
    ),
    "operational_dashboard": (
        "Operational Dashboard (R42) renders as tiles rather than a table — its own "
        "definition carries `renders_as` — and every tile is an aggregate across several "
        "datasets. The journal-lines dataset produces one row per posted line; a "
        "dashboard built from it would be one dataset's slice of a picture that is "
        "supposed to span the product."
    ),
    # ⚠ **ADDED 2026-09-27 OVER A LIVE DEFECT (`DEF-REP-6937`), AND IT IS A
    # STATEMENT ABOUT THIS DATASET RATHER THAN A HOLD ON THE REPORT.** R43 and
    # R42 are neighbours in Finance › Performance, on this dataset, with the
    # same by-period shape. R42 was refused here and **R43 was not**, so
    # `runner.run("trend_pack")` fell through to the dataset query and served a
    # clerk one row per JOURNAL LINE — posting date, account code, debit,
    # credit — **under the title *Trend Pack***. A key MISSING from a
    # hand-kept refusal map is indistinguishable from a deliberately absent
    # one: every gate passed, the viewer drew real rows, and the footer footed.
    # That is hard-won law 7's *looking at the wrong thing*.
    #
    # ⚠ **IT STAYS WHEN R43's OWN READ MODEL LANDS**, exactly as
    # `work_orders_dataset.GAP_R34_IS_A_DIFFERENT_GRAIN` stays under
    # `BR-REP-039`. `runner.queries_for` and `definition_refusal` both check
    # `VIEWERS` FIRST, so a per-KEY viewer bypasses this entry without deleting
    # it — and a refusal deleted the day its read model lands is a refusal
    # nobody can read when the wiring rots.
    "trend_pack": (
        "Trend Pack (R43) draws one row per FISCAL PERIOD — twelve of them — carrying "
        "four aggregates over that period: revenue from the ledger, collected from "
        "payments, accounts on the books at the period end, and rebills issued. This "
        "dataset produces one row per posted journal LINE, which is neither the grain "
        "nor the arithmetic: served from here the report answers with thirty-six ledger "
        "lines under a title that promises a twelve-month trend, and its RATE and DSO "
        "columns are ratios of figures no single line carries. Its own read model is "
        "`apps.ledger.trend_pack`."
    ),
}


def _journal_lines_arguments(params: Any) -> dict[str, Any]:
    """The bound parameters as the read model's arguments.

    ⚠ **BOTH SPELLINGS OF EVERY FILTER**, for the reason `_dataset_arguments`
    records: the shipped screens send them dotted and the runner passes the
    original key through, so a query reading only the bare names would be handed
    a request with every filter missing and would report the WHOLE book under a
    chip that said otherwise.
    """

    def pick(name: str) -> Any:
        return params.get(name) or params.get(f"f.{name}") or None

    return {
        "account_from": pick("account_from"),
        "account_to": pick("account_to"),
        "service_code": pick("service"),
        "source_type": pick("source_type"),
        "search": (params.get("q") or params.get("search") or "").strip() or None,
    }


def _requested_levels(params: Any) -> tuple[str, ...]:
    """The group levels this run asks for, however the wire spelled them.

    `runner.run` normalises `group_by` to a list before the query is called, and
    a comma string is still accepted because a saved link may carry one. Capped
    at `slicers.MAX_GROUP_LEVELS` here as well as there — a query that trusted
    the caller's count would be a query with no ceiling of its own.
    """
    from apps.reports import slicers

    raw = params.get("group_by")
    if isinstance(raw, str):
        levels = tuple(part.strip() for part in raw.split(",") if part.strip())
    elif isinstance(raw, (list, tuple)):
        levels = tuple(str(part) for part in raw if str(part).strip())
    else:
        levels = ()
    return levels[: slicers.MAX_GROUP_LEVELS]


def _dataset_page(params: Any) -> tuple[int, int | None, bool]:
    """`(page, per, whole)` — the page this run asks for. `per=None` is the lot."""
    page_no = _page_number(params.get("page"))
    whole = str(params.get("per") or "").lower() == "all"
    return page_no, None if whole else clamp_page_size(params.get("per")), whole


def journal_lines_dataset(params: Any, *, key: str | None = None) -> dict[str, Any]:
    """The `journal_lines` dataset, ONE PAGE, shaped for the S46 viewer.

    Paged, sorted, filtered and — since 2026-09-27 — GROUPED in SQL. The totals
    are aggregates over the whole filtered set, so the footer foots to the report
    whether a page is cut or not, and the group subtotals are aggregates over the
    same set, so they foot to the footer.
    """
    resolved = key or catalog.KEY_TRIAL_BALANCE
    refusal = JOURNAL_LINES_DEFINITIONS_NOT_SERVED.get(resolved)
    if refusal is not None:
        raise DatasetCannotServe(resolved, refusal)

    start, end = _checked_window(params)
    arguments = _journal_lines_arguments(params)

    sorts = _line_sorts()
    sort = params.get("sort") or _line_default_sort()
    if sort not in sorts:
        # `BR-SHL-011` — invalid values fall back or clamp, NEVER error.
        sort = _line_default_sort()
    raw_direction = params.get("dir")
    direction = "asc" if str(raw_direction or "desc").lower() == "asc" else "desc"
    page_no, per, whole = _dataset_page(params)

    view = seams.journal_lines(
        start=start,
        end=end,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
        group_by=_requested_levels(params),
        **arguments,
    )
    if view is None:  # pragma: no cover — ledger publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    report = _report(
        resolved,
        basis=view["basis"],
        window={"start": _iso(start), "end": _iso(end)},
        currency=view["currency"],
        columns=JOURNAL_LINES_COLUMNS,
        rows=[dict(row) for row in _journal_line_rows(view["rows"])],
        kpis=[
            _kpi("debit", _money(totals["debit"])),
            _kpi("credit", _money(totals["credit"])),
            _kpi("difference", _money(totals["difference"])),
            _kpi("lines", totals["lines"], kind="count"),
        ],
        totals={
            "debit": _money(totals["debit"]),
            "credit": _money(totals["credit"]),
            "difference": _money(totals["difference"]),
            "lines": totals["lines"],
            # Read off the wire, never re-derived. `None` on a narrowed set is a
            # statement that no verdict is available — not that the books fail.
            "balanced": view["balanced"],
        },
        unavailable=view["problems"],
        grain="one journal line",
        controls={
            "sorts": list(sorts),
            "sort": sort,
            "dir": direction,
            "searchable": True,
        },
        page=None
        if whole
        else {
            "page": view["page"],
            "per": per,
            "total": view["total"],
            "pages": view["pages"],
        },
    )
    return _with_groups(report, view)


def _journal_line_rows(rows: Any) -> list[dict[str, Any]]:
    """One `JournalLineRow` on the wire, at hard rule 2's precision.

    Money leaves as its EXACT decimal string through `_money` — B4 rounds at
    finalization and display and this is neither. `balance` leaves NULL, because
    it is not a property of one line; the reason travels in `problems`.
    """
    return [
        {
            "line_id": row.line_id,
            "posted_on": _iso(row.posted_on),
            "entry_id": row.entry_id,
            "reference": row.entry_number or row.reference,
            "account_code": row.account_code,
            "account_name": row.account_name,
            "narrative": row.narrative,
            "debit": _money(row.debit),
            "credit": _money(row.credit),
            "balance": None,
            "service": row.service_label,
            "account_no": row.customer_account_label,
            "premises": row.premises_label,
            "source_type": row.source_type,
        }
        for row in rows
    ]


# ═══ THE `payments` DATASET, ON THE DATASET PATH ═══════════════════════════
#
# ⚠ **SAME SHAPE, SAME OMISSION, ONE DAY LATER (`DEF-REP-6876`).**
# `apps/payments/payments_dataset.py` landed 2026-09-27 with lane DS-PAYMENTS and
# `DATASET_QUERIES` was not touched, so eight of the ten definitions on this
# dataset raised `DatasetNotExecutable` over a query that exists and is measured.

#: The `payments` dataset's declared columns for THIS grain — one payment.
#:
#: ⚠ **THE AGEING COLUMNS ARE DELIBERATELY ABSENT.** `datasets.PAYMENTS` declares
#: `current`, `d1_30`…`d90_plus`, `total`, `deposits_held`, `days_late` and
#: `dso_days` because R9's live viewer names them, and its own comment records
#: that they are ONE ACCOUNT's position as at a date — a different grain this
#: query serves no column for. Listing them here would head a table with seven
#: columns that are empty on every row, and a footer would then total them.
PAYMENTS_COLUMNS: tuple[str, ...] = (
    "posted_on",
    "cleared_on",
    "account_no",
    "customer_name",
    "method_name",
    "purpose",
    "status",
    "teller",
    "amount",
)

#: Definitions on this dataset that it may NOT serve. Six of the eight, and every
#: one of them for the same measured reason: the `payments` dataset's grain is ONE
#: PAYMENT and these draw one ACCOUNT, one BATCH or one COLLECTIONS ACTION.
PAYMENTS_DEFINITIONS_NOT_SERVED: dict[str, str] = {
    "debtor_list": (
        "Debtor List (R10) draws one row per DEBTOR — the balance they owe, its age and "
        "how late it is, as at a date. The payments dataset produces one row per PAYMENT, "
        "which is what they have already paid. Served here the report would list "
        "receipts under a heading that promises arrears, and an account that owes money "
        "and has paid nothing would not appear at all."
    ),
    "cut_off_list": (
        "Cut-Off List (R11) draws the accounts eligible for disconnection — one row per "
        "ACCOUNT, with a balance, an age and a notice state. The payments dataset "
        "produces one row per payment and carries no balance and no notice; a cut-off "
        "list built from it would name the accounts that have PAID."
    ),
    "collections_activity": (
        "Collections Activity (R12) draws one row per collections ACTION — the notice "
        "sent, the stage reached, who acted. Those live on payments' collections tables "
        "and not on `payments`; a payment is the outcome of the activity, not the "
        "activity, and a report of outcomes cannot state what was attempted."
    ),
    "closed_account_balances": (
        "Closed Account Balances (R14) draws one row per CLOSED ACCOUNT and its residual "
        "— a credit to refund or a debt to write off. It is an account position on the "
        "POSTING basis; this dataset is one payment, dated by when it was posted. "
        "Two different grains."
    ),
    "deposits": (
        "Deposits (R20) draws one row per account's SECURITY-DEPOSIT position — held, "
        "applied, refundable. `datasets.PAYMENTS`'s own comment records where that lives: "
        "`customers.accounts`, not `payments`. A deposit PAYMENT is one event in that "
        "position's history and is not the position."
    ),
    "deposit_batches": (
        "Deposit Batches (R2) draws one row per BANKING BATCH — a day and a tender, with "
        "its count, its total and whether it has been reconciled. The grain is the batch "
        "and this dataset's is the payment inside it. Grouping payments by day and tender "
        "would produce the right arithmetic and none of the batch's own facts: no batch "
        "number, no banked date, no reconciliation state."
    ),
}


def _payments_arguments(params: Any) -> dict[str, Any]:
    """The bound parameters as the read model's arguments — both spellings."""

    def pick(name: str) -> Any:
        return params.get(name) or params.get(f"f.{name}") or None

    return {
        "purpose": pick("purpose"),
        "method_id": pick("method"),
        "teller_id": pick("teller"),
        "status": pick("status"),
    }


def _payment_sorts() -> tuple[str, ...]:
    """Payments' OWN sort tuple, read through the seam at call time, so a caret
    this module offers and the read model declines cannot exist."""
    found = seams.payments_dataset_constant("PAYMENT_SORTS")
    return tuple(found) if found else ("posted_on",)


def payments_dataset(params: Any, *, key: str | None = None) -> dict[str, Any]:
    """The `payments` dataset, ONE PAGE, shaped for the S46 viewer.

    POSTING basis (PO 2026-10-21). Paged, sorted, filtered and GROUPED in SQL,
    with the totals and the group subtotals both aggregates over the whole
    filtered set.
    """
    resolved = key or catalog.KEY_PAYMENTS_BY_METHOD
    refusal = PAYMENTS_DEFINITIONS_NOT_SERVED.get(resolved)
    if refusal is not None:
        raise DatasetCannotServe(resolved, refusal)

    start, end = _checked_window(params)
    arguments = _payments_arguments(params)

    sorts = _payment_sorts()
    sort = params.get("sort") or sorts[0]
    if sort not in sorts:
        sort = sorts[0]
    raw_direction = params.get("dir")
    direction = "asc" if str(raw_direction or "desc").lower() == "asc" else "desc"
    page_no, per, whole = _dataset_page(params)

    view = seams.payments_dataset(
        start=start,
        end=end,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
        group_by=_requested_levels(params),
        **arguments,
    )
    if view is None:  # pragma: no cover — payments publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    report = _report(
        resolved,
        basis=view["basis"],
        window={"start": _iso(start), "end": _iso(end)},
        currency=view["currency"],
        columns=PAYMENTS_COLUMNS,
        rows=[dict(row) for row in _payment_rows(view["rows"])],
        kpis=[
            _kpi("amount", _money(totals["amount"])),
            _kpi("payments", totals["payments"], kind="count"),
            _kpi(
                "bill_purpose_amount",
                _money(totals["bill_purpose_amount"]),
                detail=None,
            ),
            _kpi(
                "bill_purpose_payments", totals["bill_purpose_payments"], kind="count"
            ),
        ],
        totals={
            "amount": _money(totals["amount"]),
            # BR-REP-014 — a collection percentage reaches for THIS and cannot
            # reach a total with deposits folded into it.
            "bill_purpose_amount": _money(totals["bill_purpose_amount"]),
            "payments": totals["payments"],
            "bill_purpose_payments": totals["bill_purpose_payments"],
        },
        unavailable=view["problems"],
        grain="one payment",
        controls={
            "sorts": list(sorts),
            "sort": sort,
            "dir": direction,
            "searchable": False,
        },
        page=None
        if whole
        else {
            "page": view["page"],
            "per": per,
            "total": view["total"],
            "pages": view["pages"],
        },
    )
    return _with_groups(report, view)


def _payment_rows(rows: Any) -> list[dict[str, Any]]:
    """One `PaymentFactRow` on the wire, at hard rule 2's precision."""
    return [
        {
            "payment_id": row.payment_id,
            "posted_on": _iso(row.posted_on),
            "cleared_on": _iso(row.cleared_on),
            "account_id": row.account_id,
            "account_no": row.account_no,
            "customer_name": row.customer_name,
            "method_id": row.method_id,
            "method_name": row.method_name,
            "purpose": row.purpose,
            "status": row.status,
            "teller": row.teller,
            "confirmation": row.confirmation,
            "memo": row.memo,
            "amount": _money(row.amount),
        }
        for row in rows
    ]


def payments_dataset_rows(params: Any, *, key: str | None = None) -> Any:
    """EVERY ROW of the `payments` dataset, from a generator — the right path.

    §8.2 p91: *"every row · never in memory · never blocks the screen"*. It takes
    no `page` and no `per`, so an export cannot inherit a screen's page by passing
    the wrong argument — there is no argument to pass.
    """
    resolved = key or catalog.KEY_PAYMENTS_BY_METHOD
    refusal = PAYMENTS_DEFINITIONS_NOT_SERVED.get(resolved)
    if refusal is not None:
        raise DatasetCannotServe(resolved, refusal)

    start, end = _checked_window(params)
    arguments = _payments_arguments(params)
    sorts = _payment_sorts()
    sort = params.get("sort") or sorts[0]
    if sort not in sorts:
        sort = sorts[0]
    raw_direction = params.get("dir")
    direction = "asc" if str(raw_direction or "desc").lower() == "asc" else "desc"

    stream = seams.payments_dataset_stream(
        start=start, end=end, sort=sort, direction=direction, **arguments
    )
    if stream is None:  # pragma: no cover — payments publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _payment_rows([row])


def _with_groups(report: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
    """Carry the read model's SQL `GROUP BY` cells onto the wire shape.

    ⚠ **THREE KEYS, AND ALL THREE ARE ABSENT WHEN NOTHING WAS ASKED FOR.** An
    ungrouped answer must be byte-for-byte what it was before grouping existed —
    that is what makes this safe to put on the shared path, and there is a test
    that compares the two payloads rather than asserting it in a comment.

    `groups` is what `apps/reports/slicers.py` turns into group rows;
    `groups_not_served` is every level the query could cut no `GROUP BY` for, so
    a dropped level is NAMED rather than silently absent (hard-won law 2's
    mirror); `group_measures` is what a group row may carry, read from the read
    model rather than guessed here.
    """
    if not (view.get("groups") or view.get("groups_not_served")):
        return report
    report = dict(report)
    report["groups"] = [dict(cell) for cell in view.get("groups") or ()]
    report["groups_not_served"] = list(view.get("groups_not_served") or ())
    report["group_measures"] = list(view.get("group_measures") or ())
    return report


# ════════════════════════════════════════════════════════════════════════════
# THE SIX REMAINING DATASETS, ON THE DATASET PATH (2026-09-27, lane REP-WIRE)
# ════════════════════════════════════════════════════════════════════════════
#
# ⚠ **ALL SIX QUERIES EXISTED, WERE MEASURED ON REAL POSTGRESQL AND WERE
# TESTED, AND NOT ONE WAS REACHABLE FROM A SCREEN (`DEF-REP-6894`).**
# `DATASET_QUERIES` held three entries, `report_seams.py` named none of the six
# owning modules, and `runner.queries_for` therefore found no fallback: EIGHTEEN
# of the forty-six seeded definitions raised `DatasetNotExecutable` naming a
# dataset that was, in fact, executable. Hard-won law 2 — built is not wired —
# and the hardest refusal to act on, because it sends the next reader to build a
# query that already exists.
#
# ⚠ **ELEVEN OF THOSE EIGHTEEN MUST REFUSE, AND THE REFUSAL IS THE POINT OF
# THIS BLOCK RATHER THAN A CAVEAT ON IT.** A dataset fallback serves EVERY
# definition seeded onto its dataset, so registering `accounts` without refusing
# R23, R26, R27 and R41 would answer four reports AT THE WRONG GRAIN: rows that
# foot, tiles that add up, and an answer to a question nobody asked. That is
# invisible to `tsc`, to every gate and to the clerk.
#
# ⚠ **EVERY REFUSAL SENTENCE IS IMPORTED AND NOT ONE IS RETYPED.** The lane that
# knows why a report is refused is the lane that wrote the query, and a second
# spelling of a refusal is how two readers come to believe two different things
# (hard-won law 5). The maps are read through the seam at CALL TIME:
# `METER_READS_DEFINITIONS_NOT_SERVED`, `UNSERVABLE_HERE` on `accounts` and
# `audit_log` (whose own `refuse()` composes the sentence), and the
# `GAP_R34_IS_A_DIFFERENT_GRAIN` / `GAP_R37_IS_A_DIFFERENT_GRAIN` constants.
#
# ⚠ **NOTHING IS ADDED TO `VIEWERS`, DELIBERATELY.** `api._VIEWERS` splats
# `queries.VIEWERS` AFTER its own two hardcoded keys, so a `VIEWERS` entry named
# `account_ledger` or `by_premises` would silently replace a LIVE screen's
# handler. The dataset fallback reaches every one of these keys without that
# hazard, and `GET /reports/{key}` already falls through to `runner.run` for a
# key `_VIEWERS` does not hold (`DEF-REP-6867`).


#: `BR-REP-001`'s third label. The two the module already names are POSTING and
#: CLEARING; `0003_seed_catalogue.py` dates R28-R32, R35, R37, R45, R46 and the
#: customers reports on the EVENT basis, with the drawing's own words — *As at*,
#: *Read date*, *Effective date* — kept in the row's `basis_label`.
#:
#: ⚠ **IT IS ASSERTED AND NOT CLAIMED.** A constant here restating a seed is
#: hard-won law 1's shape, so `tests/test_rep_wire_catalogue_reachable.py`
#: compares every served report's `basis` against the seeded row's rather than
#: leaving this comment to be believed.
BASIS_EVENT = "event"

#: `BR-REP-001`'s posting basis, for the reports whose money comes off
#: `journal_entries.entry_date` — the BOOK date. Named here because R43's
#: `column_meta` has to state the basis of every money column it declares.
BASIS_POSTING = "posting"

#: The word the `assets` and `accounts` read models publish for *as at a date*,
#: used only when the read model itself does not state one.
BASIS_AS_AT = "as_at"


def _as_of(params: Any) -> date | None:
    """The `as_of` this run asks for, or None for *no membership window*.

    `BR-SHL-011` — an unparseable value FALLS BACK rather than erroring, so a
    saved link carrying `as_of=frog` still opens the report. None is not a
    default date: for `accounts` it means every account regardless of when it
    opened, and for `assets` the read model substitutes the TENANT's today
    (never this process's), which is BR-TEN-043.
    """
    raw = params.get("as_of") or params.get("f.as_of")
    if raw in (None, ""):
        return None
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def _mixed_units_code() -> str:
    """Metering's own reason code for a consumption total that spans units.

    Read through the seam rather than spelled here: hard rule 3's refusal is
    metering's to word, and a second spelling is how two readers come to believe
    two different things (hard-won law 5).
    """
    gap = seams.meter_reads_dataset_constant("GAP_MIXED_UNITS") or {}
    return str(gap.get("code") or "consumption_spans_more_than_one_unit")


def _fact_value(value: Any) -> Any:
    """One field of a read model's frozen row, on the wire.

    A `Decimal` leaves as its EXACT decimal string for the reason `_money` gives
    — hard rule 2 rounds at display and this is not display, and a rate at scale
    4 or a percentage at scale 6 must not be trimmed on the way out. A date or a
    datetime leaves ISO. Everything else is already a wire value.

    ⚠ **`_money` IS NOT USED HERE AND THAT IS ON PURPOSE.** It raises on a
    non-`Decimal` by design, which is right for a money column named one at a
    time and wrong for a generic walk over twenty-eight fields of which two are
    money, three are counts and one is a tuple of service codes.
    """
    from datetime import datetime

    if isinstance(value, Decimal):
        return f"{value:f}"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (tuple, set, frozenset)):
        return list(value)
    return value


def _fact_rows(rows: Any) -> list[dict[str, Any]]:
    """The read model's frozen rows as wire dicts, field for field.

    ⚠ **THE FIELD LIST COMES FROM THE DATACLASS AND IS NEVER TYPED HERE.** Six
    read models publish between twelve and twenty-eight fields; a hand-typed
    projection per dataset would be six more of the hand-typed maps `P0.7`
    deleted, and the failure mode is silent — a field added to a read model and
    not to the projection is a column that renders empty forever.
    """
    from dataclasses import fields as dataclass_fields

    shaped: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            shaped.append({name: _fact_value(value) for name, value in row.items()})
            continue
        shaped.append(
            {field.name: _fact_value(getattr(row, field.name)) for field in dataclass_fields(row)}
        )
    return shaped


def _declared_columns(dataset_code: str) -> tuple[str, ...]:
    """The columns `apps/reports/datasets.py` declares for this dataset.

    Read rather than retyped, because `runner.validate()` checks a definition's
    columns against that same declaration: a second list here could offer a
    clerk a column the validator would then refuse to save.
    """
    from apps.reports import datasets

    found = datasets.BY_CODE.get(dataset_code)
    return () if found is None else tuple(column.name for column in found.columns)


def _bound(params: Any, names: dict[str, str]) -> dict[str, Any]:
    """`{argument: value}` for a read model, reading BOTH spellings of a filter.

    The shipped screens send their filters DOTTED — `f.service`, `f.status` —
    and `runner.bind` passes the ORIGINAL key through on purpose (*"this file
    does not get to rename anybody's wire"*). A query reading only the bare
    names would be handed a request with every filter missing: the report would
    render, the page would look right, and it would report the WHOLE fleet under
    a chip saying *Water*.
    """
    out: dict[str, Any] = {}
    for wire, argument in names.items():
        value = params.get(wire)
        if value in (None, ""):
            value = params.get(f"f.{wire}")
        out[argument] = None if value == "" else value
    return out


def _sort_and_direction(
    params: Any, sorts: tuple[str, ...], default: str, default_direction: str
) -> tuple[str, str]:
    """`BR-SHL-011` — an invalid value FALLS BACK, never errors, so a saved link
    carrying a sort the dataset has since retired still opens."""
    sort = params.get("sort") or default
    if sort not in sorts:
        sort = default
    raw = params.get("dir")
    if raw in (None, ""):
        direction = default_direction
    else:
        direction = "asc" if str(raw).lower() == "asc" else "desc"
    return sort, direction


def _page_of(view: dict[str, Any], per: int | None, whole: bool) -> dict[str, Any] | None:
    """`NFR-3`'s page block, absent when the whole filtered set was asked for.

    A reader must be able to tell *"this is all of it"* from *"this is page
    one"*, and an absent key says the first without claiming the second.
    """
    if whole or per is None:
        return None
    total = int(view.get("total") or 0)
    return {
        "page": view.get("page") or 1,
        "per": per,
        "total": total,
        "pages": view.get("pages") or max(1, -(-total // per)),
    }


def _count_kpis(totals: dict[str, Any], names: tuple[str, ...]) -> list[dict[str, Any]]:
    """The tiles, as counts, in the order the drawing reads them.

    ⚠ A figure the read model could not compute arrives as `None` and is served
    as `None` WITH its reason rather than as 0 — `BR-REP-024`, and the whole of
    why an on-time percentage over nothing promised is not `0.0%`.
    """
    tiles: list[dict[str, Any]] = []
    for name in names:
        value = totals.get(name)
        tiles.append(
            _kpi(
                name,
                _fact_value(value),
                kind="count",
                reason_code=None if value is not None else f"{name}_is_not_computable",
            )
        )
    return tiles


def _dataset_refusal(key: str, reason: str | None) -> None:
    """Raise `DatasetCannotServe` when the query publishes a reason for this key."""
    if reason:
        raise DatasetCannotServe(key, reason)


def _refuse_from_map(key: str, constant: Any) -> None:
    """A `GAP_*` constant refusing exactly one definition, by its own `code`."""
    if constant is None:
        return
    _dataset_refusal(key, str(constant.get("detail") or "") or None)


def _refuse_through(module_refuse: Any, key: str, table: Any) -> None:
    """Refuse through the OWNING module's own `refuse()`, so the sentence a
    reader sees is the one the lane that measured the grain wrote.

    ⚠ It catches the module's `UnservableFromThisDataset` and re-raises
    `DatasetCannotServe`. The two are different facts to different readers: the
    module's says *this dataset does not state that grain*; the runner's says
    *this DEFINITION cannot be served and the dataset is fine*, which is what
    stops the next reader building a query that already exists.
    """
    if table is None or module_refuse is None or key not in table:
        return
    try:
        module_refuse(key)
    except Exception as exc:  # the module's own UnservableFromThisDataset
        raise DatasetCannotServe(key, str(exc)) from exc


# ── `meter_reads` — six definitions, three served ───────────────────────────
#: The wire filter name -> the read model's argument. `route` and `cycle` are
#: the dataset's declared filter names and `route_id`/`cycle_id` are metering's
#: argument names; naming both here is what stops a chip that filters nothing.
_METER_READS_ARGUMENTS = {
    "service": "service",
    "route": "route_id",
    "cycle": "cycle_id",
    "channel": "channel",
    "read_basis": "read_basis",
    "flag": "flag",
}


def _meter_reads_refusal(key: str) -> None:
    table = seams.meter_reads_dataset_constant("METER_READS_DEFINITIONS_NOT_SERVED")
    _dataset_refusal(key, (table or {}).get(key))


def meter_reads_dataset(params: Any, *, key: str | None = None) -> dict[str, Any]:
    """The `meter_reads` dataset, ONE PAGE, shaped for the S46 viewer.

    ⚠ **EVENT basis — the READ DATE**, which is `0003_seed_catalogue.py`'s word
    for all six definitions on this dataset and is asserted rather than claimed:
    `test_rep_wire_catalogue_reachable.py` compares every served report's basis
    against the seeded row.

    ⚠ **HARD RULE 3 IS THE READ MODEL'S AND IS PASSED THROUGH UNTOUCHED.** Every
    quantity on a row carries its unit in its own column (`unit`), and there is
    no consumption TOTAL tile, because 684 kWh plus 26.24 kgal is not a number.
    `totals.consumption` is the read model's own per-unit breakdown.
    """
    resolved = key or "usage_and_ranking"
    _meter_reads_refusal(resolved)

    start, end = _checked_window(params)
    arguments = _bound(params, _METER_READS_ARGUMENTS)
    sorts = tuple(seams.meter_reads_dataset_constant("READ_SORTS") or ("read_on",))
    default = str(seams.meter_reads_dataset_constant("READ_DEFAULT_SORT") or "read_on")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    page_no, per, whole = _dataset_page(params)

    view = seams.meter_reads_dataset(
        start=start,
        end=end,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
        **arguments,
    )
    if view is None:  # pragma: no cover — metering publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    consumption = totals.get("consumption") or {}
    return _report(
        resolved,
        basis=BASIS_EVENT,
        window={"start": _iso(start), "end": _iso(end)},
        currency=None,
        columns=_declared_columns("meter_reads"),
        rows=_fact_rows(view["rows"]),
        kpis=[
            _kpi("reads", totals.get("reads"), kind="count"),
            # ⚠ NO SINGLE CONSUMPTION TILE. Hard rule 3: the read model returns
            # a quantity PER UNIT and the strip renders them side by side. A
            # summed number here would be the one figure this dataset may never
            # produce.
            _kpi(
                "consumption",
                _fact_value(consumption.get("total")),
                kind="quantity",
                detail=str(consumption.get("unit") or "") or None,
                reason_code=None if consumption.get("total") is not None else _mixed_units_code(),
            ),
        ],
        totals={"reads": totals.get("reads"), "consumption": _fact_value(consumption)},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )


def meter_reads_dataset_rows(params: Any, *, key: str | None = None) -> Any:
    """EVERY ROW of the `meter_reads` dataset, from a generator.

    §8.2 p91: *"every row · never in memory · never blocks the screen"*. It
    takes no `page` and no `per`, so an export cannot inherit a screen's fifty
    rows — and at T5 a year of read history is ~480,000 of them.
    """
    resolved = key or "usage_and_ranking"
    _meter_reads_refusal(resolved)
    start, end = _checked_window(params)
    arguments = _bound(params, _METER_READS_ARGUMENTS)
    sorts = tuple(seams.meter_reads_dataset_constant("READ_SORTS") or ("read_on",))
    default = str(seams.meter_reads_dataset_constant("READ_DEFAULT_SORT") or "read_on")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    stream = seams.meter_reads_dataset_stream(
        start=start, end=end, sort=sort, direction=direction, **arguments
    )
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


# ── `assets` — one definition, one served ───────────────────────────────────
_ASSETS_ARGUMENTS = {
    "service": "service",
    "asset_type": "asset_type",
    "status": "status",
    "route": "route",
    "area": "area",
}


def assets_dataset(params: Any, *, key: str | None = None) -> dict[str, Any]:
    """The `assets` dataset, ONE PAGE — R31 Meter Fleet.

    AS-AT basis: the fleet as at a date, narrowed by INSTALL and RETIRE dates.
    ⚠ The lifecycle STAGE is today's even when `as_of` is not, and the read
    model says so in `problems` rather than inferring a past stage from two
    dates — which would be a guess with a date on it.
    """
    resolved = key or "meter_fleet"
    as_of = _as_of(params)
    arguments = _bound(params, _ASSETS_ARGUMENTS)
    sorts = tuple(seams.assets_dataset_constant("ASSET_SORTS") or ("asset_no",))
    default = str(seams.assets_dataset_constant("ASSET_DEFAULT_SORT") or "asset_no")
    sort, direction = _sort_and_direction(params, sorts, default, "asc")
    page_no, per, whole = _dataset_page(params)

    view = seams.assets_dataset(
        as_of=as_of, page=page_no, per=per, sort=sort, direction=direction, **arguments
    )
    if view is None:  # pragma: no cover — assets publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    return _report(
        resolved,
        basis=str(view.get("basis") or BASIS_AS_AT),
        window={"as_of": _iso(view.get("as_of"))},
        currency=None,
        columns=_declared_columns("assets"),
        rows=_fact_rows(view["rows"]),
        kpis=_count_kpis(totals, ("assets", "in_service", "spare", "due_for_change")),
        totals={name: _fact_value(value) for name, value in totals.items()},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )


def assets_dataset_rows(params: Any, *, key: str | None = None) -> Any:
    """EVERY ROW of the `assets` dataset, from a generator."""
    as_of = _as_of(params)
    arguments = _bound(params, _ASSETS_ARGUMENTS)
    sorts = tuple(seams.assets_dataset_constant("ASSET_SORTS") or ("asset_no",))
    default = str(seams.assets_dataset_constant("ASSET_DEFAULT_SORT") or "asset_no")
    sort, direction = _sort_and_direction(params, sorts, default, "asc")
    stream = seams.assets_dataset_stream(as_of=as_of, sort=sort, direction=direction, **arguments)
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


# ── `accounts` — five definitions, ONE served and FOUR refused ──────────────
_ACCOUNTS_ARGUMENTS = {
    "class": "account_class",
    "status": "status",
    "customer_type": "customer_type",
    "service": "service",
}


def _accounts_refusal(key: str) -> None:
    _refuse_through(
        seams.accounts_dataset_constant("refuse"),
        key,
        seams.accounts_dataset_constant("UNSERVABLE_HERE"),
    )


def accounts_dataset(params: Any, *, key: str | None = None) -> dict[str, Any]:
    """The `accounts` dataset, ONE PAGE — R22 Account Census.

    ⚠ **FOUR OF THE FIVE DEFINITIONS SEEDED ONTO THIS DATASET ARE REFUSED BY
    NAME** — R23 Account Activity, R26 Data Quality, R27 Plans & Discounts and
    R41 Migration Assurance. Each states a grain this dataset does not: an
    EVENT, a CHECK, an ENROLMENT and a RECONCILIATION respectively. Served here
    they would foot, tile and read correctly and answer a different question.
    """
    resolved = key or "account_census"
    _accounts_refusal(resolved)

    as_of = _as_of(params)
    arguments = _bound(params, _ACCOUNTS_ARGUMENTS)
    sorts = tuple(seams.accounts_dataset_constant("ACCOUNT_SORTS") or ("account_no",))
    default = str(seams.accounts_dataset_constant("ACCOUNT_DEFAULT_SORT") or "account_no")
    sort, direction = _sort_and_direction(params, sorts, default, "asc")
    page_no, per, whole = _dataset_page(params)

    view = seams.accounts_dataset(
        as_of=as_of, page=page_no, per=per, sort=sort, direction=direction, **arguments
    )
    if view is None:  # pragma: no cover — customers publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    return _report(
        resolved,
        basis=str(view.get("basis") or BASIS_AS_AT),
        window={"as_of": _iso(view.get("as_of"))},
        # ⚠ ONE CURRENCY OR NONE. The read model serves `balance` as None with a
        # problem beside it when the filtered set spans two currencies, because
        # adding dollars to anything else is hard rule 2's floor.
        currency=view.get("currency"),
        columns=_declared_columns("accounts"),
        rows=_fact_rows(view["rows"]),
        kpis=[
            *_count_kpis(totals, ("accounts", "active", "closed", "with_balance")),
            _kpi("balance", _fact_value(totals.get("balance"))),
        ],
        totals={name: _fact_value(value) for name, value in totals.items()},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )


def accounts_dataset_rows(params: Any, *, key: str | None = None) -> Any:
    """EVERY ROW of the `accounts` dataset, from a generator."""
    resolved = key or "account_census"
    _accounts_refusal(resolved)
    as_of = _as_of(params)
    arguments = _bound(params, _ACCOUNTS_ARGUMENTS)
    sorts = tuple(seams.accounts_dataset_constant("ACCOUNT_SORTS") or ("account_no",))
    default = str(seams.accounts_dataset_constant("ACCOUNT_DEFAULT_SORT") or "account_no")
    sort, direction = _sort_and_direction(params, sorts, default, "asc")
    stream = seams.accounts_dataset_stream(as_of=as_of, sort=sort, direction=direction, **arguments)
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


# ── `rate_schedules` — ONE definition, and it is REFUSED ────────────────────
_RATE_SCHEDULES_ARGUMENTS = {"service": "service", "plan": "plan"}


def _rate_schedules_refusal(key: str) -> None:
    gap = seams.rate_schedules_dataset_constant("GAP_R37_IS_A_DIFFERENT_GRAIN")
    if gap is not None and key == "rate_change_history":
        _refuse_from_map(key, gap)


def rate_schedules_dataset(params: Any, *, key: str | None = None) -> dict[str, Any]:
    """The `rate_schedules` dataset, ONE PAGE.

    ⚠ **ITS ONLY SEEDED DEFINITION IS REFUSED, AND REGISTERING IT IS STILL THE
    RIGHT MOVE.** R37 Rate Change History draws one COMPONENT of a schedule per
    row and this dataset states one VERSION — a four-tier schedule whose tiers
    all move on one date is four drawn rows and one row here. Registered, the
    refusal reaches a clerk as R37's own sentence; unregistered, it reached them
    as `DatasetNotExecutable` naming a dataset that is built, measured and
    tested, which sends the next reader to write it again.

    ⚠ **THIS REPORT MUST NOT ROUND.** Hard rule 2 stores money to 4 and
    percentages to 6 and R37 displays what the rule STORES; `_fact_value` emits
    a `Decimal` as its exact string and the read model publishes both scales in
    `precision`, which travels on the wire beside the rows.
    """
    resolved = key or "rate_change_history"
    _rate_schedules_refusal(resolved)

    start, end = _checked_window(params)
    arguments = _bound(params, _RATE_SCHEDULES_ARGUMENTS)
    sorts = tuple(
        seams.rate_schedules_dataset_constant("RATE_SCHEDULE_SORTS") or ("effective_from",)
    )
    default = str(
        seams.rate_schedules_dataset_constant("RATE_SCHEDULE_DEFAULT_SORT") or "effective_from"
    )
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    page_no, per, whole = _dataset_page(params)

    view = seams.rate_schedules_dataset(
        start=start,
        end=end,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
        **arguments,
    )
    if view is None:  # pragma: no cover — rating publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    report = _report(
        resolved,
        basis=str(view.get("basis") or BASIS_EVENT),
        window={"start": _iso(start), "end": _iso(end)},
        currency=None,
        columns=_declared_columns("rate_schedules"),
        rows=_fact_rows(view["rows"]),
        kpis=_count_kpis(totals, ("versions", "in_effect", "future_dated", "corrections")),
        totals={name: _fact_value(value) for name, value in totals.items()},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )
    report["precision"] = dict(view.get("precision") or {})
    return report


def rate_schedules_dataset_rows(params: Any, *, key: str | None = None) -> Any:
    """EVERY ROW of the `rate_schedules` dataset, from a generator."""
    resolved = key or "rate_change_history"
    _rate_schedules_refusal(resolved)
    start, end = _checked_window(params)
    arguments = _bound(params, _RATE_SCHEDULES_ARGUMENTS)
    sorts = tuple(
        seams.rate_schedules_dataset_constant("RATE_SCHEDULE_SORTS") or ("effective_from",)
    )
    default = str(
        seams.rate_schedules_dataset_constant("RATE_SCHEDULE_DEFAULT_SORT") or "effective_from"
    )
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    stream = seams.rate_schedules_dataset_stream(
        start=start, end=end, sort=sort, direction=direction, **arguments
    )
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


# ── `audit_log` — three definitions, ONE served and TWO refused ─────────────
_AUDIT_LOG_ARGUMENTS = {"actor": "actor_id", "action": "action", "entity": "entity_type"}


def _audit_log_refusal(key: str) -> None:
    _refuse_through(
        seams.audit_log_dataset_constant("refuse"),
        key,
        seams.audit_log_dataset_constant("UNSERVABLE_HERE"),
    )


def audit_log_dataset(params: Any, *, key: str | None = None) -> dict[str, Any]:
    """The `audit_log` dataset, ONE PAGE — R35 Audit Trail.

    ⚠ **TWO OF THE THREE ARE REFUSED.** R36 Access Review states one USER, and
    a user who has never signed in has written no audit event at all — so the
    drawn NEVER SIGNED IN tile would read 0 over a real dormant login, which on
    a security report reads as nothing to look at. R8 Bill Delivery states one
    OUTBOUND MESSAGE: a bounce is a provider's answer about a message, not an
    act anybody performed, and no audit row is written when an email bounces.

    ⚠ `channel` AND `status` ARE REFUSED AS FILTERS BY THE READ MODEL rather
    than accepted and ignored, because a chip reading *Email* over the whole
    trail is a live screen behind a broken control.
    """
    resolved = key or "audit_trail"
    _audit_log_refusal(resolved)

    start, end = _checked_window(params)
    arguments = _bound(params, _AUDIT_LOG_ARGUMENTS)
    sorts = tuple(seams.audit_log_dataset_constant("AUDIT_SORTS") or ("when",))
    default = str(seams.audit_log_dataset_constant("AUDIT_DEFAULT_SORT") or "when")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    page_no, per, whole = _dataset_page(params)

    view = seams.audit_log_dataset(
        start=start,
        end=end,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
        **arguments,
    )
    if view is None:  # pragma: no cover — audit publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    report = _report(
        resolved,
        basis=str(view.get("basis") or BASIS_EVENT),
        window={"start": _iso(start), "end": _iso(end)},
        currency=None,
        columns=_declared_columns("audit_log"),
        rows=_fact_rows(view["rows"]),
        kpis=_count_kpis(totals, ("events", "actors", "money_events")),
        totals={name: _fact_value(value) for name, value in totals.items()},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )
    # ⚠ **THE FLOOR TRAVELS WITH THE ROWS OR IT IS NOT A FACT.** Every audit
    # read is bounded by a time floor — the two-year hot window, or the
    # retention horizon when `archive` is asked for — and a trail that does not
    # say where it stops reads as a complete history of a pruned table.
    report["retention"] = _fact_value(view.get("retention"))
    report["window_floor"] = _fact_value(view.get("window_floor"))
    return report


def audit_log_dataset_rows(params: Any, *, key: str | None = None) -> Any:
    """EVERY ROW of the `audit_log` dataset, from a generator."""
    resolved = key or "audit_trail"
    _audit_log_refusal(resolved)
    start, end = _checked_window(params)
    arguments = _bound(params, _AUDIT_LOG_ARGUMENTS)
    sorts = tuple(seams.audit_log_dataset_constant("AUDIT_SORTS") or ("when",))
    default = str(seams.audit_log_dataset_constant("AUDIT_DEFAULT_SORT") or "when")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    stream = seams.audit_log_dataset_stream(
        start=start, end=end, sort=sort, direction=direction, **arguments
    )
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


# ── `work_orders` — two definitions, ONE served and ONE refused ─────────────
_WORK_ORDERS_ARGUMENTS = {
    "order_type": "order_type",
    "status": "status",
    "priority": "priority",
    "crew": "crew_id",
    "service": "service",
}


def _work_orders_refusal(key: str) -> None:
    gap = seams.work_orders_dataset_constant("GAP_R34_IS_A_DIFFERENT_GRAIN")
    if gap is not None and key == "disconnect_reconnect":
        _refuse_from_map(key, gap)


def work_orders_dataset(params: Any, *, key: str | None = None) -> dict[str, Any]:
    """The `work_orders` dataset, ONE PAGE — R33 Service Order Activity.

    ⚠ **R34 DISCONNECT & RECONNECT IS REFUSED.** Its every drawn row is an
    ACCOUNT carrying a whole sequence — balance, notice, disconnected,
    paid, reconnected — and an account cut and restored inside the window has
    TWO orders, so it would appear twice and the balance column would
    double-count the debt.

    ⚠ **DURATION CARRIES ITS UNIT** (hard rule 3): `duration_unit` is `hours`
    and travels on every row and on the totals. Orders that recorded no time on
    site are counted in `duration_missing` and are NOT folded in as zero, which
    would read as a job that took no time and drag every average down silently.
    """
    resolved = key or "service_order_activity"
    _work_orders_refusal(resolved)

    start, end = _checked_window(params)
    arguments = _bound(params, _WORK_ORDERS_ARGUMENTS)
    sorts = tuple(seams.work_orders_dataset_constant("WORK_ORDER_SORTS") or ("raised_on",))
    default = str(seams.work_orders_dataset_constant("WORK_ORDER_DEFAULT_SORT") or "raised_on")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    page_no, per, whole = _dataset_page(params)

    view = seams.work_orders_dataset(
        start=start,
        end=end,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
        **arguments,
    )
    if view is None:  # pragma: no cover — work publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    return _report(
        resolved,
        basis=str(view.get("basis") or BASIS_EVENT),
        window={"start": _iso(start), "end": _iso(end)},
        currency=None,
        columns=_declared_columns("work_orders"),
        rows=_fact_rows(view["rows"]),
        kpis=[
            *_count_kpis(totals, ("orders", "completed", "open")),
            # ⚠ NULL WITH ITS REASON, NEVER 0.0 — an order raised with no
            # priority carries no promise, so it is neither on time nor late and
            # is excluded from BOTH sides of the percentage (BR-REP-024).
            _kpi(
                "on_time_pct",
                _fact_value(totals.get("on_time_pct")),
                kind="percent",
                reason_code=(
                    None
                    if totals.get("on_time_pct") is not None
                    else "nothing_in_this_window_carried_a_promise"
                ),
            ),
        ],
        totals={name: _fact_value(value) for name, value in totals.items()},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )


def work_orders_dataset_rows(params: Any, *, key: str | None = None) -> Any:
    """EVERY ROW of the `work_orders` dataset, from a generator."""
    resolved = key or "service_order_activity"
    _work_orders_refusal(resolved)
    start, end = _checked_window(params)
    arguments = _bound(params, _WORK_ORDERS_ARGUMENTS)
    sorts = tuple(seams.work_orders_dataset_constant("WORK_ORDER_SORTS") or ("raised_on",))
    default = str(seams.work_orders_dataset_constant("WORK_ORDER_DEFAULT_SORT") or "raised_on")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    stream = seams.work_orders_dataset_stream(
        start=start, end=end, sort=sort, direction=direction, **arguments
    )
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


# ════════════════════════════════════════════════════════════════════════════
# THE JOINING READS (`P6.11`) — three reports whose grain NO dataset holds
# ════════════════════════════════════════════════════════════════════════════
# ⚠ **EACH IS A PER-KEY VIEWER, AND THAT IS WHAT MAKES IT REACH THE SCREEN.**
# `runner.queries_for` checks `VIEWERS` first and the DATASET query second, so
# a key registered below never reaches the dataset it is seeded on — which is
# the only way a report can be served at a grain its own dataset refuses. The
# three dataset refusal maps that name these keys STAY as they are: they are
# what a reader sees if a viewer is ever removed, and `definition_refusal()`
# already asks `VIEWERS` first for exactly this reason.
#
# ⚠ **THE JOIN IS NOT IN THIS FILE.** Each viewer below calls ONE seam, and the
# join lives in the module that owns the spine — identity, metering, customers.
# `apps/reports/` imports no other module's models (`CR-142-BRC07` §3), and a
# union composed here would be a cross-module query wearing a query file's name.


_ACCESS_REVIEW_ARGUMENTS = {"role": "role", "status": "status"}


def access_review(params: Any) -> dict[str, Any]:
    """R36 Access Review — one row per USER OF THIS TENANT, as at a date.

    ⚠ **IT PAGES AT NINE ROWS ON PURPOSE.** p066, verbatim: *"Ten staff is the
    whole ICP, so this is nine rows and not a paginated list — and it is still
    served paginated, because `NFR-3` admits no exceptions and the four places
    that claimed one are the defect `DEF-PAY-4221` exists to close."*

    ⚠ **THE `LAST SIGN-IN` COLUMN IS SERVED AS `last_active_at`** and the
    substitution travels in `unavailable` rather than being hidden — see
    `apps/identity/access_review.py` for why `sessions` cannot answer it.
    """
    as_of = _as_of(params)
    arguments = _bound(params, _ACCESS_REVIEW_ARGUMENTS)
    sorts = tuple(seams.access_review_constant("ACCESS_SORTS") or ("user",))
    default = str(seams.access_review_constant("ACCESS_DEFAULT_SORT") or "user")
    sort, direction = _sort_and_direction(params, sorts, default, "asc")
    page_no, per, whole = _dataset_page(params)

    view = seams.access_review(
        as_of=as_of, page=page_no, per=per, sort=sort, direction=direction, **arguments
    )
    if view is None:  # pragma: no cover — identity publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    return _report(
        "access_review",
        basis=str(view.get("basis") or BASIS_AS_AT),
        window={"as_of": _iso(view.get("as_of"))},
        currency=None,
        columns=ACCESS_REVIEW_COLUMNS,
        rows=_fact_rows(view["rows"]),
        kpis=_count_kpis(totals, ("users", "active", "never_signed_in", "can_approve_money")),
        totals={name: _fact_value(value) for name, value in totals.items()},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )


def access_review_rows(params: Any) -> Any:
    """EVERY ROW of R36, from a generator."""
    as_of = _as_of(params)
    arguments = _bound(params, _ACCESS_REVIEW_ARGUMENTS)
    sorts = tuple(seams.access_review_constant("ACCESS_SORTS") or ("user",))
    default = str(seams.access_review_constant("ACCESS_DEFAULT_SORT") or "user")
    sort, direction = _sort_and_direction(params, sorts, default, "asc")
    stream = seams.access_review_stream(
        as_of=as_of, sort=sort, direction=direction, **arguments
    )
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


#: R36's columns, in the drawing's own order (p066). ⚠ **THEY ARE NOT
#: `_declared_columns("audit_log")`** — this report is seeded on that dataset and
#: does not produce its columns, so offering `action` or `entity` as headers over
#: empty cells would be worse than not offering them (`_shaped`'s own rule, one
#: step earlier).
ACCESS_REVIEW_COLUMNS: tuple[str, ...] = (
    "user_name",
    "user_email",
    "role_name",
    "added_on",
    "added_by",
    "last_active_at",
    "can_approve_money",
    "status",
)


_IMPORT_LOG_ARGUMENTS = {
    "source": "source",
    "result": "result",
    "status": "status",
    "cycle": "cycle",
    "route": "route",
}


def read_import_log(params: Any) -> dict[str, Any]:
    """R32 Read Import Log — one row per READ-IMPORT BATCH, over an import window.

    ⚠ **ROWS / ACCEPTED / REJECTED ARE AGGREGATED FROM THE ROWS**, never read
    from the batch's denormalised `counts` blob, whose own column comment calls
    it a cache that must reconcile. A disagreement is REPORTED with both
    numbers rather than silently preferred one way (coordinator ruling,
    2026-09-27).
    """
    start, end = _checked_window(params)
    arguments = _bound(params, _IMPORT_LOG_ARGUMENTS)
    sorts = tuple(seams.read_import_log_constant("IMPORT_LOG_SORTS") or ("imported_at",))
    default = str(seams.read_import_log_constant("IMPORT_LOG_DEFAULT_SORT") or "imported_at")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    page_no, per, whole = _dataset_page(params)

    view = seams.read_import_log(
        start=start,
        end=end,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
        **arguments,
    )
    if view is None:  # pragma: no cover — metering publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    return _report(
        "read_import_log",
        basis=str(view.get("basis") or BASIS_EVENT),
        window={"start": _iso(start), "end": _iso(end)},
        currency=None,
        columns=IMPORT_LOG_COLUMNS,
        rows=_fact_rows(view["rows"]),
        kpis=[
            *_count_kpis(totals, ("imports", "rows", "accepted", "rejected")),
            # ⚠ NULL WITH ITS REASON, NEVER 0.0% — a share over a filtered set
            # with no file rows in it is undefined, and `no import had any rows`
            # and `every row was rejected` are opposite facts (BR-REP-024).
            _kpi(
                "accepted_pct",
                _fact_value(totals.get("accepted_pct")),
                kind="percent",
                reason_code=(
                    None
                    if totals.get("accepted_pct") is not None
                    else "no_file_rows_in_this_window"
                ),
            ),
        ],
        totals={name: _fact_value(value) for name, value in totals.items()},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )


def read_import_log_rows(params: Any) -> Any:
    """EVERY ROW of R32, from a generator."""
    start, end = _checked_window(params)
    arguments = _bound(params, _IMPORT_LOG_ARGUMENTS)
    sorts = tuple(seams.read_import_log_constant("IMPORT_LOG_SORTS") or ("imported_at",))
    default = str(seams.read_import_log_constant("IMPORT_LOG_DEFAULT_SORT") or "imported_at")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    stream = seams.read_import_log_stream(
        start=start, end=end, sort=sort, direction=direction, **arguments
    )
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


#: R32's columns, in the drawing's own order (p064). The last is the DETAIL
#: drill-through — the drawing's *View 14 rows* — and it is `rejected` plus the
#: batch id the row already carries, never a separate query from here.
IMPORT_LOG_COLUMNS: tuple[str, ...] = (
    "imported_at",
    "file_name",
    "source_kind",
    "source_detail",
    "rows",
    "accepted",
    "rejected",
    "imported_by",
    "status",
)


_ACTIVITY_ARGUMENTS = {"event": "event", "account": "account"}


def account_activity(params: Any) -> dict[str, Any]:
    """R23 Account Activity — one row per ACCOUNT-LIFECYCLE EVENT.

    ⚠ **TWO DATE COLUMNS BECAUSE TWO DATES EXIST** (p060). The window is struck
    on `occurred_at` — when the clerk did it — and `effective_on` travels beside
    it, so a move-in dated 1 October is in September's activity and October's
    census and both are right.

    ⚠ **`net` IS DERIVED AND DECLARED NON-ADDITIVE.** It is `opened − closed`;
    a renderer summing a column of group subtotals would be right by accident.
    """
    start, end = _checked_window(params)
    arguments = _bound(params, _ACTIVITY_ARGUMENTS)
    sorts = tuple(seams.account_activity_constant("ACTIVITY_SORTS") or ("occurred_at",))
    default = str(seams.account_activity_constant("ACTIVITY_DEFAULT_SORT") or "occurred_at")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    page_no, per, whole = _dataset_page(params)

    view = seams.account_activity(
        start=start,
        end=end,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
        **arguments,
    )
    if view is None:  # pragma: no cover — customers publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    return _report(
        "account_activity",
        basis=str(view.get("basis") or BASIS_EVENT),
        window={"start": _iso(start), "end": _iso(end)},
        currency=None,
        columns=ACTIVITY_COLUMNS,
        rows=_fact_rows(view["rows"]),
        kpis=[
            *_count_kpis(totals, ("opened", "closed", "transferred")),
            # `net` is a signed COUNT and never money — `kind="count"` so the
            # screen does not print a currency symbol over a difference.
            _kpi("net", _fact_value(totals.get("net")), kind="count"),
        ],
        totals={name: _fact_value(value) for name, value in totals.items()},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )


def account_activity_rows(params: Any) -> Any:
    """EVERY ROW of R23, from a generator."""
    start, end = _checked_window(params)
    arguments = _bound(params, _ACTIVITY_ARGUMENTS)
    sorts = tuple(seams.account_activity_constant("ACTIVITY_SORTS") or ("occurred_at",))
    default = str(seams.account_activity_constant("ACTIVITY_DEFAULT_SORT") or "occurred_at")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    stream = seams.account_activity_stream(
        start=start, end=end, sort=sort, direction=direction, **arguments
    )
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


#: R23's columns, in the drawing's own order (p060). BOTH dates are here, and
#: that is the drawn warning built rather than described.
ACTIVITY_COLUMNS: tuple[str, ...] = (
    "occurred_at",
    "account_no",
    "customer_name",
    "event",
    "premises_address",
    "actor",
    "effective_on",
)


# ════════════════════════════════════════════════════════════════════════════
# THE JOINING READS, WAVE 2 (`P6.11`, lane REP-P6-W2) — the four RULED reports
# ════════════════════════════════════════════════════════════════════════════
# `BR-REP-039`–`042` were ruled by the PO on 2026-09-27, all option (a), and
# each moved a report from *needs a ruling* to *buildable*. The same shape as
# wave 1 applies throughout: a per-KEY viewer that `runner.queries_for` checks
# BEFORE the dataset, one seam call each, and the join itself living in the
# module that owns the spine.


_DISCONNECT_ARGUMENTS = {"reason": "reason", "account": "account"}


def disconnect_reconnect(params: Any) -> dict[str, Any]:
    """R34 Disconnect & Reconnect — one row per ACCOUNT, showing its LATEST case.

    ⚠ **`BR-REP-039`, AND THE GRAIN IS THE RULING.** One row per CASE would
    show Alia twice — cut for `$210` in June and `$185` in September — and total
    `$395`, money she never owed at once. One row per account, the latest case,
    earlier cases COUNTED and never served as siblings.

    ⚠ **TWO DRAWN FIGURES ARE NULL WITH THEIR REASONS** (`BR-REP-024`):
    `ELIGIBLE` names a tenant rule nothing in this product evaluates, and
    `PAID` is payments' money and not a case column — `BR-REP-039` says so
    itself. Both travel in `unavailable` rather than as a zero.
    """
    start, end = _checked_window(params)
    arguments = _bound(params, _DISCONNECT_ARGUMENTS)
    sorts = tuple(seams.disconnect_reconnect_constant("DISCONNECT_SORTS") or ("notice_on",))
    default = str(seams.disconnect_reconnect_constant("DISCONNECT_DEFAULT_SORT") or "notice_on")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    page_no, per, whole = _dataset_page(params)

    view = seams.disconnect_reconnect(
        start=start,
        end=end,
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
        **arguments,
    )
    if view is None:  # pragma: no cover — customers publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    return _report(
        "disconnect_reconnect",
        basis=str(view.get("basis") or BASIS_EVENT),
        window={"start": _iso(start), "end": _iso(end)},
        currency=view.get("currency"),
        columns=DISCONNECT_COLUMNS,
        # `DEF-REP-6902` — `balance` and `paid` are money this query takes from
        # the customers seam; the dataset behind R34 declares neither, so both
        # printed at storage width (`318.6000`, `2410.0000`).
        column_meta={
            name: {"type": "money", "unit": None, "unit_from": None,
                   "money_basis": str(view.get("basis") or BASIS_EVENT), "scale": 4}
            for name in ("balance", "paid")
        },
        rows=_fact_rows(view["rows"]),
        kpis=[
            # ⚠ **ELIGIBLE IS NULL WITH ITS REASON AND NEVER 0** — an eligible
            # account is one with NO case, so a count over the case table would
            # report the opposite population.
            _kpi(
                "eligible",
                None,
                kind="count",
                reason_code="no_rule_in_this_product_selects_an_eligible_account",
            ),
            *_count_kpis(totals, ("notices_sent", "disconnected", "reconnected")),
            # The money tile that CAN be struck: what the shown cases were owed
            # when they opened. It foots to the BALANCE column beneath it.
            _kpi("owed", _fact_value(totals.get("owed")), kind="money"),
            # ⚠ **COLLECTED IS NULL WITH ITS REASON** — see the read model.
            _kpi(
                "collected",
                None,
                kind="money",
                reason_code="the_case_records_what_was_owed_never_what_was_received",
            ),
        ],
        totals={name: _fact_value(value) for name, value in totals.items()},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )


def disconnect_reconnect_rows(params: Any) -> Any:
    """EVERY ROW of R34, from a generator."""
    start, end = _checked_window(params)
    arguments = _bound(params, _DISCONNECT_ARGUMENTS)
    sorts = tuple(seams.disconnect_reconnect_constant("DISCONNECT_SORTS") or ("notice_on",))
    default = str(seams.disconnect_reconnect_constant("DISCONNECT_DEFAULT_SORT") or "notice_on")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    stream = seams.disconnect_reconnect_stream(
        start=start, end=end, sort=sort, direction=direction, **arguments
    )
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


#: R34's columns, in the drawing's own order (p065). ⚠ **`paid` IS HERE
#: ALTHOUGH IT IS ALWAYS NULL.** The drawing draws the column; serving it as an
#: em-dash with a named reason in `unavailable` tells a supervisor the product
#: does not know, where dropping the column silently would tell them nothing at
#: all and would make the drawn table and the shipped table disagree with no
#: record of why.
DISCONNECT_COLUMNS: tuple[str, ...] = (
    "account_no",
    "customer_name",
    "balance",
    "notice_on",
    "cut_on",
    "paid",
    "reconnected_on",
    "status",
)


# ── `P6.11` wave 3 · R43 TREND PACK ─────────────────────────────────────────
#
# ⚠ **THIS VIEWER IS THE FIX FOR `DEF-REP-6937`, AND THE REFUSAL ABOVE STAYS.**
# `runner.queries_for` and `definition_refusal` both check `VIEWERS` FIRST, so
# registering this key bypasses `JOURNAL_LINES_DEFINITIONS_NOT_SERVED["trend_pack"]`
# without deleting a sentence that is still true of that DATASET. `BR-REP-039`
# set the precedent with `work_orders`: a refusal deleted the day its read model
# lands is a refusal nobody can read when the wiring rots.

#: R43's columns, in the drawing's own order (p059).
TREND_PACK_COLUMNS: tuple[str, ...] = (
    "period",
    "revenue",
    "target",
    "collected",
    "rate",
    "dso",
    "accounts",
    "rebills",
)

#: ⚠ **WHAT KIND EACH COLUMN IS, DECLARED BY THE ONLY PLACE THAT KNOWS**
#: (`DEF-REP-6902` / `DEF-REP-6903` / `DEF-REP-6963`). `runner._shaped`
#: publishes types for the columns the DATASET declares, and `journal_lines`
#: declares none of these — it has never heard of `rate`, `dso` or `rebills`.
#: Without this map every money figure on R43 would render at storage width
#: (`118402.100000`) under a tile reading `$118,402.10`, and the percentages
#: would print six places. That fault has now shipped TWICE on reports this
#: framework serves, both times found in a browser and never by a test, so it
#: is declared HERE rather than added to the viewer's hand-typed
#: `MONEY_COLUMNS` — a query that invents a column is the only place that knows
#: what it is.
#:
#: `period` and the two counts are deliberately ABSENT: an entry means *render
#: it as this kind*, and a column with no entry renders as text, which is what
#: `P10` and `1,947` want.
TREND_PACK_COLUMN_META: dict[str, dict[str, Any]] = {
    **{
        name: {"type": "money", "unit": None, "unit_from": None,
               "money_basis": BASIS_POSTING, "scale": 4}
        for name in ("revenue", "target", "collected")
    },
    # A percentage is STORED to six places and DISPLAYED at two (hard rule 2).
    "rate": {"type": "percent", "unit": None, "unit_from": None, "scale": 6},
    # ⚠ **`dso` IS A NUMBER OF DAYS AND IS NOT A PERCENTAGE.** p059 draws
    # `14.1 days`. Typing it `percent` would print `14.10%` at a finance
    # officer, which is the `DEF-REP-6903` fault with the sign of the error
    # reversed — a plausible figure in the wrong unit.
    "dso": {"type": "quantity", "unit": "days", "unit_from": "BR-REP-011", "scale": 6},
}


def trend_pack(params: Any) -> dict[str, Any]:
    """R43 Trend Pack — one row per FISCAL PERIOD, twelve of them.

    ⚠ **IT SERVED ONE ROW PER JOURNAL LINE UNTIL THIS FUNCTION EXISTED**
    (`DEF-REP-6937`) — thirty-six rows of `posted_on / account_code / debit /
    credit` under this report's own title, because a hand-kept refusal map was
    missing one key while its neighbour R42 was in it.

    ⚠ **NO `page` BLOCK, AND THAT IS `NFR-3` SATISFIED RATHER THAN DODGED.**
    The row count is p059's **Periods** control — twelve — not the tenant's
    size, so there is nothing to page. `_report` publishes `page` only for a
    report bounded by tenant size, and its absence says *this is all of it*.

    ⚠ **NO `totals`, BECAUSE p059 DRAWS NO TOTAL ROW AND IS RIGHT.** RATE and
    DSO are ratios, ACCOUNTS is as-of (the same account appears in all twelve
    rows) and TARGET is per period. Three of the eight columns cannot lawfully
    be summed, and a footer carrying the other three under a table of eight is
    worse than none.
    """
    view = seams.trend_pack(
        as_of=_as_of(params),
        periods=_trend_periods(params),
    )
    if view is None:  # pragma: no cover — the ledger publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    tiles = view["tiles"]
    return _report(
        "trend_pack",
        basis=str(view.get("basis") or BASIS_POSTING),
        window={"start": _iso(view["window"]["start"]), "end": _iso(view["window"]["end"])},
        currency=view.get("currency"),
        columns=TREND_PACK_COLUMNS,
        column_meta=TREND_PACK_COLUMN_META,
        rows=_fact_rows(view["rows"]),
        kpis=[
            # ⚠ **`BR-REP-034`'s RULED DEGRADE, AND IT IS THE DEFAULT STATE.**
            # The PO ruled on 2026-08-18 that with no target typed the tile
            # shows *the figure alone, no sub-line*. Every tenant on this
            # deployment is there, so the percentage is NULL with its reason
            # and `detail` carries the REVENUE — a figure, never a code
            # (`P2.13`).
            _kpi(
                "revenue_vs_target",
                _fact_value(tiles.get("revenue_vs_target")),
                kind="percent",
                detail=_fact_value(tiles.get("revenue_latest")),
                reason_code=tiles.get("revenue_vs_target_absence"),
            ),
            _kpi(
                "collection_rate",
                _fact_value(tiles.get("collection_rate")),
                kind="percent",
                reason_code=tiles.get("collection_rate_absence"),
            ),
            # `BR-REP-022` — the target is a tenant setting seeded at 15 days,
            # and it is the tile's sub-line rather than a second tile.
            _kpi(
                "dso",
                _fact_value(tiles.get("dso")),
                kind="quantity",
                detail=_fact_value(view.get("dso_target_days")),
                reason_code=tiles.get("dso_absence"),
            ),
            _kpi(
                "accounts_change",
                _fact_value(tiles.get("accounts_change")),
                kind="percent",
                detail=tiles.get("periods"),
                reason_code=tiles.get("accounts_change_absence"),
            ),
        ],
        totals={},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        # ⚠ **NEITHER SORTABLE NOR SEARCHABLE, DECLARED RATHER THAN OMITTED.**
        # A trend is read in period order and in no other: sorting it by
        # revenue destroys the only thing it is for. A caret over a column this
        # query will not reorder is hard-won law 2's mirror — a live control
        # over a dead one — so `sorts` is empty and the screen draws none.
        controls={"sorts": [], "sort": "period", "dir": "asc", "searchable": False},
    )


def trend_pack_rows(params: Any) -> Any:
    """EVERY ROW of R43, from a generator.

    ⚠ **REGISTERED IN `KEY_STREAMS` AND THE REGISTRATION IS THE POINT.** Without
    it `runner.stream_for` falls through to the `journal_lines` DATASET stream
    and the download button writes the ledger's own lines into a file headed
    *Trend Pack* — `DEF-REP-6937` surviving on the path nobody looks at.
    """
    stream = seams.trend_pack_stream(as_of=_as_of(params), periods=_trend_periods(params))
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


def _trend_periods(params: Any) -> int:
    """p059's **Periods** control, clamped rather than refused (`BR-SHL-011`).

    ⚠ **THE CLAMP IS ON THE CONTROL AND NOT ON THE TENANT**, so `NFR-5` is
    untouched: it bounds how many times one request may walk the fiscal calendar
    backwards, which no utility's growth ever reaches. The read model owns the
    ceiling and this reads it rather than typing a second one.
    """
    default = int(seams.trend_pack_constant("DEFAULT_PERIODS") or 12)
    ceiling = int(seams.trend_pack_constant("MAX_PERIODS") or 120)
    raw = params.get("periods") or params.get("f.periods")
    if raw in (None, ""):
        return default
    try:
        asked = int(str(raw))
    except (TypeError, ValueError):
        return default
    return max(1, min(asked, ceiling))


#: DATASET code -> a callable that RAISES `DatasetCannotServe` for a definition
#: that dataset may not serve, and returns None otherwise.
#:
#: ⚠ **IT EXISTS SO THE CATALOGUE AND THE VIEWER CANNOT DISAGREE, WHICH THEY
#: DID FOR ONE RUN OF THIS LANE'S OWN TESTS.** `catalogue_read` decided a card
#: was available by asking `runner.queries_for` — correct while a dataset with a
#: query served every definition on it. The moment six datasets were registered
#: that made **every one of the 46 cards claim to be producible**, twenty-eight
#: of which refuse on grain the instant they are clicked: *a viewer that opens
#: onto a reason is a screen pretending to be a report*, which is the exact
#: posture `apps/reports/catalog.py` ships. `test_rep_p1_catalogue.py` caught it
#: with *"every card available would mean the check cannot fail"*.
#:
#: The values are the SAME functions the adapters call, so there is one reading
#: of *may this dataset serve this report* and not two (hard-won law 5).
_DEFINITION_REFUSALS: dict[str, Any] = {
    "invoices": lambda key: _dataset_refusal(key, INVOICES_DEFINITIONS_NOT_SERVED.get(key)),
    "journal_lines": lambda key: _dataset_refusal(
        key, JOURNAL_LINES_DEFINITIONS_NOT_SERVED.get(key)
    ),
    "payments": lambda key: _dataset_refusal(key, PAYMENTS_DEFINITIONS_NOT_SERVED.get(key)),
    "meter_reads": _meter_reads_refusal,
    "accounts": _accounts_refusal,
    "audit_log": _audit_log_refusal,
    "rate_schedules": _rate_schedules_refusal,
    "work_orders": _work_orders_refusal,
    # `assets` holds one definition and serves it; it refuses none.
}


def definition_refusal(key: str, dataset: str | None) -> str | None:
    """The sentence this dataset publishes for refusing THIS definition, or None.

    Answered WITHOUT running the query, so a caller that only needs to know
    whether a report can be produced — the catalogue — pays nothing and cannot
    reach a different answer from the viewer, which calls the same functions.

    ⚠ **A PER-REPORT VIEWER WINS, EXACTLY AS IN `runner.queries_for`.** Four
    keys on `journal_lines` are served by their own viewers and never reach the
    dataset query, so a refusal table entry could not apply to them; asking the
    table first would mark a shipped, measured report unavailable.
    """
    if VIEWERS.get(key) is not None:
        return None
    # `CR-179-BRC10` — a MODULE-owned viewer (`runner._OWNING_MODULES`) wins the
    # same way, for the same reason: `queries_for` asks it first, so the
    # dataset's refusal table can never apply to the key it serves.
    from apps.reports import runner

    if runner.owned_viewer(key) is not None:
        return None
    check = _DEFINITION_REFUSALS.get(dataset or "")
    if check is None:
        return None
    try:
        check(key)
    except DatasetCannotServe as refusal:
        return refusal.reason
    return None


# ── `receivables` — THE TENTH DATASET (`CR-184-BRC10`, 2026-10-14) ───────────
#: The columns a definition on this dataset shows by default, in drawn order.
RECEIVABLES_COLUMNS: tuple[str, ...] = (
    "account_no",
    "customer_name",
    "service",
    "charge_class",
    "current",
    "d1_30",
    "d31_60",
    "d61_90",
    "d90_plus",
    "total",
)

#: this report's column → payments' band name (the ageing's own five, BR-REP-030).
_RECEIVABLES_BANDS: tuple[tuple[str, str], ...] = (
    ("current", "current"),
    ("d1_30", "1-30"),
    ("d31_60", "31-60"),
    ("d61_90", "61-90"),
    ("d90_plus", "90+"),
)


def receivables_as_of(params: Any) -> date:
    """The POSITION date — `as_of`, else the As-of box's `to`, else the tenant's
    period END (the day the AR tie-out is struck, as for the ageing)."""
    found = _as_of(params)
    if found is not None:
        return found
    raw = params.get("to") or params.get("f.to")
    if raw not in (None, ""):
        return _explicit_day(raw, "to")
    period = seams.current_period()
    if period is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="reports.viewer.no_fiscal_period",
            field_errors=[{"field": "as_of", "code": errors.VAL_REQUIRED}],
        )
    return _explicit_day(period.get("end"), "to")


def receivables_foot(as_of: date, population: Decimal) -> tuple[Decimal | None, list]:
    """R4 — the rows' whole receivable against the ledger's AR control.

    ⚠ **STRUCK AGAINST THE POPULATION — EVERY OPEN BILL, NO SERVICE FILTER —
    AND NEVER ADJUSTED.** A difference is stated with both figures (BR-REP-008 ·
    BR-LED-007, the ageing's own pattern); nothing here moves a row to close it.
    """
    tie_out = seams.ar_control(as_of=as_of)
    if tie_out is None:
        return None, [
            {
                "code": "ar_control_total_not_published",
                "br_ref": "BR-REP-008",
                "detail": "The ledger's AR control total could not be read, so this report "
                "cannot state whether it foots.",
            }
        ]
    if tie_out != population:
        return tie_out, [
            {
                "code": "receivables_by_service_does_not_foot_to_the_ar_control_total",
                "br_ref": "BR-REP-008 · BR-LED-007",
                "detail": (
                    f"Σ of every service row is {population:f} and the ledger's AR control "
                    f"total is {tie_out:f}, a difference of {(tie_out - population):f}. The "
                    "rows are NOT adjusted to close it. The commonest cause on this "
                    "deployment is imported opening balances, which are in the books and in "
                    "no bill."
                ),
            }
        ]
    return tie_out, []


def _receivables_rows(rows: Any) -> list[dict[str, Any]]:
    """One `ReceivableRow` on the wire, money at 4 dp (hard rule 2)."""
    return [
        {
            "account_id": row.account_id,
            "account_no": row.account_no,
            "customer_name": row.customer_name,
            "service": row.service_name,
            "service_code": row.service_code,
            "charge_class": row.charge_class,
            **{column: _money(row.bands[band]) for column, band in _RECEIVABLES_BANDS},
            "total": _money(row.total),
        }
        for row in rows
    ]


def _receivables_sort(params: Any) -> tuple[str, str]:
    """Payments' OWN sort tuple, read through the seam, so a caret this module
    offers and the read model declines cannot exist."""
    sorts = tuple(seams.receivables_constant("DATASET_SORTS") or ("total",))
    sort = params.get("sort") or sorts[0]
    if sort not in sorts:
        sort = sorts[0]
    direction = "asc" if str(params.get("dir") or "desc").lower() == "asc" else "desc"
    return sort, direction


def receivables_dataset(params: Any, *, key: str | None = None) -> dict[str, Any]:
    """The `receivables` dataset, ONE PAGE — what each account owes per service.

    POSTING basis, as at one date. Paged AFTER the whole filtered set is
    totalled (`NFR-3`), so the footer is the debt and not the page; the foot
    check is struck against the UNFILTERED population (R4).
    """
    as_of = receivables_as_of(params)
    service = params.get("service") or params.get("f.service") or None
    sort, direction = _receivables_sort(params)
    page_no, per, whole = _dataset_page(params)
    view = seams.receivables_dataset(
        as_of=as_of, service=service, page=page_no, per=per, sort=sort, direction=direction
    )
    if view is None:  # pragma: no cover — payments publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    totals = view["totals"]
    tie_out, foot = receivables_foot(as_of, view["population"])
    currency = view["currency"]
    empty = not totals["rows"]
    return _report(
        key or "receivables",
        basis=view["basis"],
        window={"as_of": _iso(as_of)},
        currency=currency,
        columns=RECEIVABLES_COLUMNS,
        rows=_receivables_rows(view["rows"]),
        kpis=[
            _kpi(
                "total_ar",
                _money(totals["total"]) if currency else None,
                reason_code=None
                if currency
                else ("nothing_owed_at_this_date" if empty else "receivable_holds_more_than_one_currency"),
            ),
            _kpi("d90_plus", _money(totals["90+"])),
            _kpi("accounts", totals["accounts"], kind="count"),
        ],
        totals={
            **{column: _money(totals[band]) for column, band in _RECEIVABLES_BANDS},
            "total": _money(totals["total"]),
            "accounts": totals["accounts"],
            "ar_control": _money(tie_out) if tie_out is not None else None,
            "population_total": _money(view["population"]),
            "population_accounts": view["population_accounts"],
            "filtered": view["filtered"],
        },
        unavailable=list(view["problems"]) + foot,
        grain="account_service",
        controls={
            "sorts": list(view["sorts"]),
            "sort": sort,
            "dir": direction,
            "searchable": False,
        },
        page=None
        if whole
        else {"page": view["page"], "per": per, "total": view["total"], "pages": view["pages"]},
    )


def receivables_dataset_rows(params: Any, *, key: str | None = None) -> Any:
    """EVERY ROW of the `receivables` dataset, from a generator — the right path."""
    as_of = receivables_as_of(params)
    service = params.get("service") or params.get("f.service") or None
    sort, direction = _receivables_sort(params)
    stream = seams.receivables_dataset_stream(
        as_of=as_of, service=service, sort=sort, direction=direction
    )
    if stream is None:  # pragma: no cover — payments publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _receivables_rows([row])


#: DATASET code -> the query behind it. `runner.queries_for` falls back to this
#: when a key has no per-report viewer, which is what makes a dataset turn on
#: every definition built upon it instead of one card at a time. Four datasets
#: had a per-KEY viewer before this and none had a dataset query; `invoices` is
#: the first.
DATASET_QUERIES = {
    "invoices": invoices_dataset,
    # ⚠ **REGISTERED 2026-09-27 (`DEF-REP-6876`, lane REP-UNBLOCK).** Both
    # queries existed, both were measured on real PostgreSQL, both were reachable
    # through `report_seams` — and neither was in this dict, so `queries_for`
    # found no fallback and thirteen definitions refused with
    # `DatasetNotExecutable` over datasets that were executable.
    "journal_lines": journal_lines_dataset,
    "payments": payments_dataset,
    # ⚠ **THE SIX REMAINING, REGISTERED 2026-09-27 (`DEF-REP-6894`, lane
    # REP-WIRE).** All six queries were built, measured on real PostgreSQL and
    # tested by four sibling lanes, and `apps/reports` had a seam to none of
    # them: eighteen definitions refused with `DatasetNotExecutable` over
    # datasets that were executable. Registering one turns on EVERY definition
    # seeded onto it, which is why eleven of the eighteen refuse BY NAME inside
    # the adapters above rather than answering at the wrong grain.
    "meter_reads": meter_reads_dataset,
    "assets": assets_dataset,
    "accounts": accounts_dataset,
    "rate_schedules": rate_schedules_dataset,
    "audit_log": audit_log_dataset,
    "work_orders": work_orders_dataset,
    # `CR-184-BRC10` — what is still owed, per account and service.
    "receivables": receivables_dataset,
    # ⚠ **`notifications` IS ABSENT AND CANNOT BE ADDED HERE (`DEF-REP-6895`).**
    # `apps/notifications/notifications_dataset.py` is built, measured and
    # tested — a TENTH dataset, written for R8 Bill Delivery rather than bending
    # R8 onto the audit trail — but `datasets.py` declares NINE and
    # `reports/0003` seeds R8 on `audit_log`. `runner.bind` looks the
    # definition's dataset up in `datasets.BY_CODE` and raises
    # `DatasetNotExecutable` BEFORE this map is consulted, so an entry here would
    # answer no call that can happen. Registering it needs a `NOTIFICATIONS`
    # dataset (with its slicer, drill-through, calendar and additivity rows) and
    # a MIGRATION moving R8's seeded `dataset` column — a catalogue change with a
    # ruling behind it, not a line in this dict.
}

# ── R27 PLANS & DISCOUNTS (`P6.11` wave 4, lane REP-P6-W4) ──────────────────

#: R27's columns, in the drawing's own order (p061).
PLANS_COLUMNS: tuple[str, ...] = (
    "programme",
    "account",
    "since",
    "terms_months",
    "terms_percent",
    "instalment",
    "remaining",
    "status",
)

#: ⚠ **`terms` IS DRAWN AS ONE COLUMN AND SERVED AS TWO, ON PURPOSE.** p061
#: draws `12 months`, `6 instalments` and `Low-income · 20%` in one cell —
#: three different KINDS of term. A server composing that sentence would decide
#: eleven catalogues' wording in English (B14 rule 35), so the MONTHS and the
#: PERCENT travel separately and the screen writes its own language around them.
#: ⚠ **AND THE PERCENT IS A PERCENT AND THE MONTHS ARE A COUNT** — typing both
#: the same way is `DEF-REP-6903`, a plausible figure in the wrong unit.
PLANS_COLUMN_META: dict[str, dict[str, Any]] = {
    "instalment": {"type": "money", "unit": None, "unit_from": None,
                   "money_basis": BASIS_AS_AT, "scale": 4},
    "remaining": {"type": "money", "unit": None, "unit_from": None,
                  "money_basis": BASIS_AS_AT, "scale": 4},
    "terms_percent": {"type": "percent", "unit": None, "unit_from": None, "scale": 6},
    "terms_months": {"type": "quantity", "unit": "months", "unit_from": "p061", "scale": 0},
}

_PLANS_ARGUMENTS = {"programme": "programme", "status": "status"}


def plans_and_discounts(params: Any) -> dict[str, Any]:
    """R27 Plans & Discounts — one row per ENROLMENT, across three programmes.

    ⚠ **`BR-REP-040`, AND THE GRAIN IS THE RULING.** p061's tiles are the
    evidence: `184 + 84 + 50 = 318`, which only adds up at enrolment grain,
    because one account can be on all three programmes at once. At account grain
    the three tiles stop summing to the first and the SINCE, TERMS, INSTALMENT
    and REMAINING columns have no single value.

    ⚠ **THE LAST PAGE IS SLOWER THAN THE FIRST AND IT IS RULED.** A k-way merge
    fetches `offset + per` from each of three streams. `NFR-3` and `NFR-5` are
    untouched — every fetch is SQL-sorted and SQL-limited, no Python slice of an
    unbounded read, no cap. The measured cost is published in `BR-REP-040`.

    ⚠ **THE `ENROLLED` TILE IS TWO FIGURES BECAUSE IT MIXES UNITS** — 318 is
    enrolments and 16.3% is a share of ACCOUNTS. `BR-REP-040` says to label each
    for what it is, so they are served under two names and the percentage is the
    tile's `detail` rather than a second tile.
    """
    arguments = _bound(params, _PLANS_ARGUMENTS)
    sorts = tuple(seams.plans_and_discounts_constant("PLANS_SORTS") or ("since",))
    default = str(seams.plans_and_discounts_constant("PLANS_DEFAULT_SORT") or "since")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    page_no, per, whole = _dataset_page(params)

    view = seams.plans_and_discounts(
        as_of=_as_of(params),
        page=page_no,
        per=per,
        sort=sort,
        direction=direction,
        **arguments,
    )
    if view is None:  # pragma: no cover — reports publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    absences = view.get("absences") or {}
    return _report(
        "plans_and_discounts",
        basis=str(view.get("basis") or BASIS_AS_AT),
        window={"start": _iso(view["window"]["start"]), "end": _iso(view["window"]["end"])},
        currency=view.get("currency"),
        columns=PLANS_COLUMNS,
        column_meta=PLANS_COLUMN_META,
        rows=_fact_rows(view["rows"]),
        kpis=[
            _kpi(
                "enrolled",
                _fact_value(totals.get("enrolled")),
                kind="count",
                # The percentage, as this tile's SUB-LINE — never as the tile's
                # own value, which is what mixing the two units would produce.
                detail=_fact_value(totals.get("enrolled_share")),
                reason_code=absences.get("enrolled_share"),
            ),
            *_count_kpis(totals, ("level_pay",)),
            _kpi(
                "payment_plan",
                _fact_value(totals.get("payment_plan")),
                kind="count",
                # p061's `$14,204.00 remaining` sub-line, which is the SUM of
                # the REMAINING column beneath it — one figure computed once.
                detail=_fact_value(totals.get("plan_remaining")),
            ),
            *_count_kpis(totals, ("assistance",)),
        ],
        totals={name: _fact_value(value) for name, value in totals.items()},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        # p061 draws As of · Programme · Status and no search box.
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )


def plans_and_discounts_rows(params: Any) -> Any:
    """EVERY ROW of R27, from a generator.

    ⚠ **REGISTERED IN `KEY_STREAMS`. WITHOUT IT `stream_for` FALLS THROUGH TO
    THE `accounts` DATASET STREAM** and the Download button writes an ACCOUNT
    LIST into a file headed *Plans & Discounts* — one row per account under the
    title of a report whose grain is one enrolment, which is the exact confusion
    `accounts_dataset`'s refusal exists to prevent.
    """
    arguments = _bound(params, _PLANS_ARGUMENTS)
    sorts = tuple(seams.plans_and_discounts_constant("PLANS_SORTS") or ("since",))
    default = str(seams.plans_and_discounts_constant("PLANS_DEFAULT_SORT") or "since")
    sort, direction = _sort_and_direction(params, sorts, default, "desc")
    stream = seams.plans_and_discounts_stream(
        as_of=_as_of(params), sort=sort, direction=direction, **arguments
    )
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


# ── R4 BILL RUN READINESS (`P6.11` wave 4, lane REP-P6-W4) ──────────────────

#: R4's columns, in the drawing's own order (p049).
#:
#: ⚠ **`route` AND `usage` ARE HERE AND ARE NULL ON EVERY ROW** (`BR-REP-060`).
#: They are DRAWN by p049, and `BR-REP-024` keeps a drawn figure and states its
#: absence rather than deleting the column — the posture R34 gives `paid` and
#: R43 gives `target`. The Route FILTER is a different matter and is NOT
#: offered: see `_READINESS_ARGUMENTS` below.
READINESS_COLUMNS: tuple[str, ...] = (
    "account",
    "customer",
    "route",
    "check",
    "detail",
    "usage",
)

#: ⚠ **WHAT KIND EACH COLUMN IS, DECLARED BY THE ONLY PLACE THAT KNOWS.**
#: `runner._shaped` publishes types for the columns the DATASET declares, and
#: `invoices` declares none of these — it has never heard of `check` or
#: `retryable`. R4 carries NO MONEY COLUMN AT ALL, which is why this map is
#: short rather than missing: `usage` is a QUANTITY and would otherwise be
#: right-aligned as an untyped string the day `OQ-REP-12768` fills it, and
#: `DEF-REP-6903` is a plausible figure in the wrong unit reaching a clerk.
READINESS_COLUMN_META: dict[str, dict[str, Any]] = {
    "usage": {"type": "quantity", "unit": None, "unit_from": "BR-REP-060", "scale": 6},
}

#: ⚠ **`route` IS DELIBERATELY ABSENT FROM THIS MAP AND p049 DRAWS THE CHIP.**
#: `BR-REP-060`: a filter over a column that is NULL on every row is a live
#: control that cannot work — hard-won law 2's mirror, on a brand-new screen.
#: The column states its absence honestly; a chip offering to act on that
#: absence would tell a clerk the product can answer a question it cannot.
#: **Do not "finish" this by adding `route` here — read `OQ-REP-12768` first.**
_READINESS_ARGUMENTS = {"cycle": "cycle", "check": "check"}


def bill_run_readiness(params: Any) -> dict[str, Any]:
    """R4 Bill Run Readiness — one row per HELD ACCOUNT of the latest prepared run.

    ⚠ **`BR-REP-041`, AND THE SPINE IS THE RULING.** The report is opened for a
    CYCLE and readiness belongs to a RUN, so it shows the LATEST PREPARED run for
    that cycle. Where none exists the absence is STATED and nothing is
    substituted — an empty table reads as a clean result, and this screen's whole
    purpose is the accounts that are not clean.

    ⚠ **TWO DRAWN COLUMNS ARE NULL WITH ONE SHARED REASON** (`BR-REP-060`): an
    account has no single ROUTE and no single USAGE figure, because a route
    belongs to one service and a quantity may not be summed across services
    (hard rule 3). That is `OQ-REP-12768` — a missing DECISION rather than a
    missing read — and the Route FILTER is not offered.

    ⚠ **THE ROWS ARE THE HELD ACCOUNTS AND NOT THE CYCLE.** p049's footnote is
    the spec: *"The 49 held accounts are the whole point of the screen."* A
    listing of all 1,247 would bury the 49 that need a person before the run.
    """
    arguments = _bound(params, _READINESS_ARGUMENTS)
    sorts = tuple(seams.bill_run_readiness_constant("READINESS_SORTS") or ("account",))
    default = str(seams.bill_run_readiness_constant("READINESS_DEFAULT_SORT") or "account")
    sort, direction = _sort_and_direction(params, sorts, default, "asc")
    page_no, per, whole = _dataset_page(params)

    view = seams.bill_run_readiness(
        page=page_no, per=per, sort=sort, direction=direction, **arguments
    )
    if view is None:  # pragma: no cover — billing publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")

    totals = view["totals"]
    absences = view.get("absences") or {}
    return _report(
        "bill_run_readiness",
        basis=str(view.get("basis") or BASIS_POSTING),
        window={"start": _iso(view["window"]["start"]), "end": _iso(view["window"]["end"])},
        currency=view.get("currency"),
        columns=READINESS_COLUMNS,
        column_meta=READINESS_COLUMN_META,
        rows=_fact_rows(view["rows"]),
        kpis=[
            # ⚠ **THE TOP TWO TILES DEGRADE AND THE BOTTOM TWO DO NOT**
            # (`BR-REP-061`). ACCOUNTS IN CYCLE and READY TO BILL are
            # `bill_runs.findings_summary`, which only the background findings
            # job writes — a run calculated inline carries none, and a `0` there
            # would say the cycle is empty when the truth is that nobody counted.
            _kpi(
                "accounts_in_cycle",
                _fact_value(totals.get("accounts_in_cycle")),
                kind="count",
                reason_code=absences.get("accounts_in_cycle"),
            ),
            # p049 draws `96%` as the SUB-LINE of READY TO BILL rather than as a
            # fifth tile, so it travels as this tile's `detail`.
            _kpi(
                "ready_to_bill",
                _fact_value(totals.get("ready_to_bill")),
                kind="count",
                detail=_fact_value(totals.get("ready_pct")),
                reason_code=absences.get("ready_to_bill"),
            ),
            # HELD is the row count of this report and is always produced: it is
            # a count over `bill_run_breaks`, which is persisted.
            _kpi(
                "held",
                _fact_value(totals.get("held")),
                kind="count",
                reason_code=absences.get("held"),
            ),
            _kpi(
                "no_read",
                _fact_value(totals.get("no_read")),
                kind="count",
                reason_code=absences.get("no_read"),
            ),
        ],
        totals={name: _fact_value(value) for name, value in totals.items()},
        unavailable=view.get("problems") or (),
        grain=view.get("grain"),
        # ⚠ **NOT SEARCHABLE, DECLARED RATHER THAN OMITTED.** p049 draws three
        # parameters and no search box, and the read honours no `q`. A search
        # field over a query that ignores it is the same dead control the Route
        # chip would be.
        controls={"sorts": list(sorts), "sort": sort, "dir": direction, "searchable": False},
        page=_page_of(view, per, whole),
    )


def bill_run_readiness_rows(params: Any) -> Any:
    """EVERY ROW of R4, from a generator.

    ⚠ **REGISTERED IN `KEY_STREAMS`, AND WITHOUT IT `stream_for` FALLS THROUGH TO
    THE `invoices` DATASET STREAM** — the download button would write a BILL
    REGISTER into a file headed *Bill Run Readiness*: the accounts that DID bill,
    under the title of the ones that did not. `DEF-REP-6937` on the export path.
    """
    arguments = _bound(params, _READINESS_ARGUMENTS)
    sorts = tuple(seams.bill_run_readiness_constant("READINESS_SORTS") or ("account",))
    default = str(seams.bill_run_readiness_constant("READINESS_DEFAULT_SORT") or "account")
    sort, direction = _sort_and_direction(params, sorts, default, "asc")
    stream = seams.bill_run_readiness_stream(sort=sort, direction=direction, **arguments)
    if stream is None:  # pragma: no cover
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    for row in stream:
        yield from _fact_rows([row])


#: REPORT KEY -> its streaming read, for a FILE. ⚠ **IT EXISTS BECAUSE
#: `VIEWERS` DOES.** `runner.stream_for` looked up by DATASET alone, so the
#: three joining reads below — each a per-KEY viewer, each seeded on a dataset
#: whose query refuses it — had no stream a caller could reach, and their
#: export would have fallen back to `run(whole=True)`: correct rows, and the
#: whole filtered set materialised in memory instead of streamed. At a
#: top-of-ICP tenant R23 is years of moves.
#:
#: ⚠ **AND THREE GENERATORS NOTHING CAN CALL ARE DEAD CODE** — hard-won law 2,
#: which is the reason this map is added in the same commit as the viewers
#: rather than left for a later lane to notice. `stream_for` checks this map
#: FIRST and the dataset map second, mirroring `queries_for` exactly, so there
#: is one rule for *which read serves this key* and not two.
KEY_STREAMS = {
    "access_review": access_review_rows,
    "read_import_log": read_import_log_rows,
    "account_activity": account_activity_rows,
    # ── wave 2 (lane REP-P6-W2) ─────────────────────────────────────────────
    "disconnect_reconnect": disconnect_reconnect_rows,
    # ── wave 3 (lane REP-P6-W3) ─────────────────────────────────────────────
    # ⚠ **BOUNDED AND STILL REGISTERED.** Twelve rows do not need a generator;
    # what they need is for `stream_for` NOT to fall through to the
    # `journal_lines` dataset stream and write the ledger's own lines into a
    # file headed *Trend Pack* — `DEF-REP-6937` on the export path.
    "trend_pack": trend_pack_rows,
    # ── wave 4 (lane REP-P6-W4) ─────────────────────────────────────────────
    # ⚠ **WITHOUT THIS LINE `stream_for` FALLS THROUGH TO THE `invoices`
    # DATASET STREAM** and the Download button writes a BILL REGISTER into a
    # file headed *Bill Run Readiness* — the accounts that DID bill, under the
    # title of the ones that did not.
    "bill_run_readiness": bill_run_readiness_rows,
    "plans_and_discounts": plans_and_discounts_rows,
}


#: DATASET code -> its streaming read, for a FILE. Separate map for the reason
#: the two seams are separate: a generator and a page must not be reachable
#: through one name.
DATASET_STREAMS = {
    "invoices": invoices_dataset_rows,
    # ⚠ **`journal_lines` IS ABSENT AND THE ABSENCE IS THE FACT.**
    # `apps/ledger/journal_lines_dataset.py` publishes a PAGE and no generator, so
    # there is nothing to register; an entry here pointing at the paging function
    # is exactly how the billing register's export shipped a valid-looking file of
    # fifty rows from a 38,000-row report. `apps/reports/runner.stream_for`
    # returns None and the export falls back to `run(whole=True)`.
    "payments": payments_dataset_rows,
    # ⚠ **SIX GENERATORS, AND EACH IS A SEPARATE LOOKUP FROM THE PAGE ABOVE.**
    # §8.2 p91: *"the left path never fetches more than a page; the right path
    # never holds one."* None of these takes a `page` or a `per`, so an export
    # has no argument through which to inherit a screen's fifty rows — the
    # defect caught on the billing register on 2026-09-26, where a 38,000-row
    # file would have been written as a valid-looking fifty.
    "meter_reads": meter_reads_dataset_rows,
    "assets": assets_dataset_rows,
    "accounts": accounts_dataset_rows,
    "rate_schedules": rate_schedules_dataset_rows,
    "audit_log": audit_log_dataset_rows,
    "work_orders": work_orders_dataset_rows,
    "receivables": receivables_dataset_rows,
}


VIEWERS = {
    catalog.KEY_AR_AGING: ar_aging,
    catalog.KEY_BILLING_REGISTER: billing_register,
    catalog.KEY_REVENUE_BY_SERVICE: revenue_by_service_rate,
    catalog.KEY_PAYMENTS_BY_METHOD: payments_by_method,
    # The `journal_lines` dataset's four (lane DS-LEDGER, 2026-09-26).
    catalog.KEY_TRIAL_BALANCE: trial_balance,
    catalog.KEY_JOURNAL_EXPORT: journal_export,
    catalog.KEY_TAX_REMITTANCE: tax_remittance,
    catalog.KEY_CLOSE_PACK: close_pack,
    # ── THE JOINING READS (`P6.11`, lane REP-P6-JOIN, 2026-09-27) ──────────
    # ⚠ **A PER-KEY VIEWER IS THE ONLY WAY A REPORT CAN BE SERVED AT A GRAIN
    # ITS OWN DATASET REFUSES.** Each of these three is seeded on a dataset
    # whose query refuses it BY NAME — `audit_log` cannot see a user who never
    # signed in, `meter_reads` never holds a rejected row, `accounts` states one
    # account and not one event — and each refusal is CORRECT and stays where it
    # is. `queries_for` checks this map first, so the dataset never sees the
    # call; `definition_refusal()` asks this map first for the same reason, so
    # the catalogue card and the viewer cannot disagree about whether a report
    # can be produced.
    #
    # The keys are spelled from `reports/0003_seed_catalogue.py`'s own tuple
    # rather than from `catalog.py`, because `catalog` names only the handful of
    # reports that predate the definitions table.
    "access_review": access_review,
    "read_import_log": read_import_log,
    "account_activity": account_activity,
    # ── WAVE 2 — the reports `BR-REP-039`–`042` moved into buildable ────────
    # ⚠ **EACH IS SEEDED ON A DATASET WHOSE QUERY REFUSES IT BY NAME AND EVERY
    # ONE OF THOSE REFUSALS STAYS.** `work_orders` is right that an account cut
    # and restored twice appears twice in a list of field jobs; `BR-REP-039`
    # answers that by moving the SPINE, not by widening the dataset.
    "disconnect_reconnect": disconnect_reconnect,
    # ── WAVE 3 · `DEF-REP-6937` ─────────────────────────────────────────────
    # ⚠ **R43 WAS THE ONE KEY ON `journal_lines` THAT NOBODY REFUSED AND
    # NOBODY SERVED.** Its neighbour R42 was in the refusal map and it was not,
    # so the dataset query answered it at one-row-per-LINE under its own title.
    # The refusal is there now AND this viewer wins over it, which is the same
    # arrangement `disconnect_reconnect` has one line up and for the same
    # reason: the sentence stays true of the dataset either way.
    "trend_pack": trend_pack,
    # ── WAVE 4 · R4, R27, R46 (lane REP-P6-W4) ─────────────────────────────
    # ⚠ **R4 IS SEEDED ON `invoices` AND THAT DATASET REFUSES IT BY NAME,
    # CORRECTLY AND PERMANENTLY** — *"a bill does not exist yet for a held
    # account"*. The refusal STAYS; this viewer wins over it, which is the
    # same arrangement `trend_pack` and `disconnect_reconnect` have, and for
    # the same reason: the sentence goes on being true of the dataset.
    "bill_run_readiness": bill_run_readiness,
    # ⚠ **R27 IS SEEDED ON `accounts` AND THAT DATASET REFUSES IT BY NAME,
    # CORRECTLY AND PERMANENTLY** — its grain is one ENROLMENT and accounts
    # produces one ACCOUNT, so SINCE, TERMS, INSTALMENT and REMAINING have no
    # account-level value. The refusal STAYS and this viewer wins over it.
    "plans_and_discounts": plans_and_discounts,
}


def parameter_vocabularies() -> dict[str, Any]:
    """BR-REP-006's LIVE vocabularies for the S46 parameter bar.

    *"Filters enumerate LIVE vocabularies (tenant services, 4 consumer classes
    incl. Government, 5 statuses + behavior classes, bill_type, payment purpose,
    read channel) — never hardcoded."*

    Services come from the tenant's ENABLED set — a tenant with two services
    lists two, and the prototype's hardcoded Electric/Water/Sewer trio appears
    nowhere. The ACCOUNT-CLASS list is deliberately absent from this payload and
    is read by the screen from `GET /lookups/account_types`, which is the read
    S18's customer-type select already uses; see `report_seams` for why a second
    read of one vocabulary is the drift BR-REP-006 exists to prevent.
    """
    services = seams.services_overview() or []
    period = seams.current_period()
    regional = seams.regional_settings() or {}
    return {
        # `services_overview()` names the code `service` and flags the tenant's
        # own enablement — only the ENABLED ones are offered, which is the whole
        # of BR-REP-006 for this filter (US-REP-002 TC-1: a tenant with two
        # services lists two).
        "services": [
            {"code": row.get("service"), "name": row.get("name")}
            for row in services
            if row.get("enabled")
        ],
        "bill_types": list(catalog_bill_types()),
        "purposes": list(_payment_purposes()),
        "current_period": (
            None
            if period is None
            else {
                "start": period.get("start"),
                "end": period.get("end"),
                "fy_label": period.get("fy_label"),
                "period": period.get("period"),
            }
        ),
        "currency": regional.get("currency"),
        # BR-TEN-022 — a viewer with no fiscal calendar has no default window,
        # and says so rather than substituting a calendar month.
        "period_unavailable_reason": None if period is not None else "fiscal_period_not_configured",
    }


def _payment_purposes() -> tuple[str, ...]:
    """BR-PAY-012's four values — through the SEAM (`CR-142-BRC07` `P0.13`).

    ⚠ **THIS FUNCTION USED TO CALL `import_module("apps.payments.models")`
    HERE.** It read a constant and touched no ORM, so no figure was ever wrong;
    what was wrong is that a cross-module read lived in a query file instead of
    in `report_seams.py`, where `G20` and the next reader both look for the
    list of what this module needs from its neighbours. A boundary crossing
    nobody has written down is one nobody can audit.
    """
    return seams.payment_purposes()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-REP-002@c6c35b2 (co-packets US-REP-005/006/007; 04-docs/05-modules/12-reports/06-epics/EP-REP-01-report-center.md §US-REP-002 · EP-REP-02-canned-reports.md §US-REP-005/006/007 · 12-reports/02-business-rules.md BR-REP-001/002/006/008/011/014/024 · 04-docs/01-spec/14-reports-and-exports.md · 05-prototype/UtilityBilling.html lines 4145-4232)
# screens: S44 · S46
# generated: 2026-08-16 by story-coder (reports lane — the module had 939 backend lines against 125,419 across the rest of the product); amended 2026-09-27 by lane REP-UNBLOCK (DEF-REP-6876 — `journal_lines` and `payments` registered in DATASET_QUERIES, `payments` in DATASET_STREAMS, with a NAMED refusal per definition the dataset may not serve); amended 2026-09-27 by lane REP-WIRE (DEF-REP-6894 — the SIX remaining dataset queries registered in both maps through new seams, with eleven further definitions refused BY NAME on grain; `notifications` reported unregisterable as DEF-REP-6895)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the three test modules named above could not import this file before it existed, and `GET /reports/ar_aging` answered VAL-005 enumerating only the two ledger keys. ruff✔ black✔ pytest✔ run_gates✔
# exceptions: (0) `queries.BASIS_EVENT` restates `reports/0003_seed_catalogue.py`'s third basis code and is ASSERTED against it by `tests/test_rep_wire_catalogue_reachable.py`, never left as a comment to be believed (hard-won law 1) · (1) BR-REP-001 is enforced STRUCTURALLY — `basis` is a required argument of `_report()`, so a report without one cannot be built · (2) a figure that cannot be computed is null WITH a `reason_code` and never 0 (BR-REP-024); a percentage over a zero total is undefined and served null rather than 0.0% · (3) running a report WRITES NOTHING — the BR-REP-018 generation record is written by the export pipeline when a FILE is produced, so there is one implementation of "who exported what" and it is `apps/tenancy/services.request_list_export` · (4) the account-class vocabulary is NOT served in `parameter_vocabularies()`: `GET /lookups/account_types` already serves it and a second read would be a second vocabulary
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
