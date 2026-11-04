# ── Trace ──────────────────────────────────────────────
# Change:   CR-184-BRC10 R3 + R4 — *Receivables over 90 days by service*, a
#           library report inside the reporting framework (no page of its own)
# Rules:    decision log 2026-10-14 (C1 → a — the sharing rule) · BR-REP-001
#           (a money report states its basis: POSTING) · BR-REP-008 /
#           BR-LED-007 (it foots to the AR control or says so) · CLAUDE.md
#           hard rule 2 (money 4 dp on the wire, 6 for a percentage)
# Tests:    06-backend/tests/test_cr184_receivables_by_service.py
# Impacts:  apps/reports/runner.py (`_OWNING_MODULES`) · apps/reports/exports.py
#           (`RECEIVABLES_OVER_90`) · reports/0011 (the platform row)
# ───────────────────────────────────────────────────────
"""RECEIVABLES OVER 90 DAYS BY SERVICE — one row per service, as at a date.

The PO tried to build exactly this in the custom builder on 2026-10-14 and
found nothing to build it on. The `receivables` dataset now exists for the
builder (`datasets.RECEIVABLES`); this is the same figure as a library card,
because *"how much is over ninety days, on which service"* is a question a
finance office asks every month-end and should not have to assemble.

ONE ROW PER SERVICE, AND PER CLASS ROW
──────────────────────────────────────
A row is a service the tenant bills (*Water*, *Fire* — whatever the bills name)
or a class row for lines that name no service (*Taxes*, *Fees*, *Other
charges*): the ruling says such a line is *"reported on its own row, never
guessed onto a service"*. Columns: debtors over 90 days on that row · the amount
over 90 days · that amount's share of the whole over-90 figure · the row's
whole receivable.

WHAT FOOTS, AND WHAT IS NOT A SUM
─────────────────────────────────
* Σ `total` over the rows is the WHOLE receivable at the as-of date, exactly —
  every row of every open bill is counted. That is the figure struck against
  the ledger's AR control (R4); a difference is stated and never adjusted.
* Σ `d90_plus` is the over-90 total; `share_pct` is each row's part of it.
* The DEBTORS total is DISTINCT accounts, not the column's sum: a customer over
  ninety days on water AND sewer is one debtor. Summing the column would count
  them twice, so the footer carries the distinct count instead.

The rows are bounded by the tenant's services plus at most five class rows, so
the report does not page — the same posture as Revenue by Service (`NFR-3`
pages what grows with the tenant; this does not).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from core import errors

from . import queries
from . import report_seams as seams

KEY = "receivables_over_90_by_service"
BASIS = "posting"

COLUMNS: tuple[str, ...] = ("service", "charge_class", "debtors", "d90_plus", "share_pct", "total")

FOUR_PLACES = Decimal("0.0001")
SIX_PLACES = Decimal("0.000001")
HUNDRED = Decimal("100")
ZERO = Decimal("0")


def _share(part: Decimal, whole: Decimal) -> str | None:
    """A row's part of the over-90 total at 6 dp (hard rule 2). None when there
    is nothing over 90 days — a share of zero is undefined, not 0%."""
    if whole == ZERO:
        return None
    return str((part / whole * HUNDRED).quantize(SIX_PLACES))


def receivables_over_90_by_service(params: Any) -> dict[str, Any]:
    """`GET /reports/receivables_over_90_by_service` — the rows, totals and foot."""
    as_of = queries.receivables_as_of(params)
    view = seams.receivables_over_90_by_service(as_of=as_of)
    if view is None:  # pragma: no cover — payments publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.dataset.unavailable")
    over_90: Decimal = view["over_90"]
    rows = [
        {
            "service": row.service_name,
            "service_code": row.service_code,
            "charge_class": row.charge_class,
            "debtors": row.debtors,
            "d90_plus": queries._money(row.over_90),
            "share_pct": _share(row.over_90, over_90),
            "total": queries._money(row.total),
        }
        for row in view["rows"]
    ]
    tie_out, foot = queries.receivables_foot(as_of, view["population"])
    currency = view["currency"]
    empty = not rows
    reason = (
        None
        if currency
        else ("nothing_owed_at_this_date" if empty else "receivable_holds_more_than_one_currency")
    )
    return queries._report(
        KEY,
        basis=view["basis"],
        window={"as_of": as_of.isoformat()},
        currency=currency,
        columns=COLUMNS,
        rows=rows,
        kpis=[
            queries._kpi("d90_plus", queries._money(over_90) if currency else None, reason_code=reason),
            queries._kpi("debtors", view["debtors_over_90"], kind="count"),
            queries._kpi(
                "total_ar", queries._money(view["total"]) if currency else None, reason_code=reason
            ),
        ],
        totals={
            "debtors": view["debtors_over_90"],
            "d90_plus": queries._money(over_90),
            "share_pct": _share(over_90, over_90),
            "total": queries._money(view["total"]),
            "ar_control": queries._money(tie_out) if tie_out is not None else None,
            "population_total": queries._money(view["population"]),
            "population_accounts": view["population_accounts"],
        },
        unavailable=list(view["problems"]) + foot,
        grain="service",
        column_meta={
            "d90_plus": {"type": "money", "unit": None, "unit_from": None,
                         "money_basis": BASIS, "scale": 4},
            "total": {"type": "money", "unit": None, "unit_from": None,
                      "money_basis": BASIS, "scale": 4},
            "share_pct": {"type": "percent", "unit": None, "unit_from": None,
                          "money_basis": None, "scale": 6},
            "debtors": {"type": "count", "unit": None, "unit_from": None,
                        "money_basis": None, "scale": None},
        },
        column_choices=COLUMNS,
    )


def export_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """The served rows, for a file — the screen's own answer."""
    return [row for row in payload.get("rows") or () if isinstance(row, dict)]


#: KEY -> every column this viewer can serve (`runner.served_columns`).
MODULE_COLUMNS: dict[str, tuple[str, ...]] = {KEY: COLUMNS}

#: KEY -> viewer, owned by THIS module (`runner.queries_for` asks first).
MODULE_VIEWERS: dict[str, Any] = {KEY: receivables_over_90_by_service}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-184-BRC10 (12-governance/change-requests/CR-184-BRC10-receivables-by-service.md)
# screens: the standard report viewer at /reports/receivables_over_90_by_service (no page of its own)
# generated: 2026-10-14 by lane ARSVC
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — see 06-backend/tests/test_cr184_receivables_by_service.py's module docstring
# exceptions: (1) not paged — bounded by the tenant's services plus at most five class rows · (2) the debtors footer is a DISTINCT count, not the column's sum
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
