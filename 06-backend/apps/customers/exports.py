# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-CUS-10180 (account age) · DEF-CUS-10181 (Aging reads bills)
# Ruling:   decision log 2026-10-17 — "ACCOUNT AGE ON THE ACCOUNTS LIST; AGING
#           STAYS MONEY AND IS FIXED TO READ BILLS": *"Column Account age …
#           sortable oldest ↔ newest by Opened; in the download"*.
# Screen:   ACC-01 / S17 (the Accounts list's Download control)
# Rules:    BR-SHL-016 (the export covers the list's CURRENT state) · IS-9
#           (CSV kinds) · CLAUDE.md hard rule 1 (the rows are the list's own,
#           tenant-scoped read) · hard rule 2 (money 2dp in the file)
# Tests:    06-backend/tests/test_def_cus_10165_10166_account_age_and_ageing.py
# ───────────────────────────────────────────────────────
"""The Accounts list's download, on the ONE export kernel.

`AccountsListPage.tsx` carried *"No `downloadSlot`: `/exports` registers no
`accounts` resource"* since the screen shipped. The PO's ruling of 2026-10-17
put Account age *"in the download"*, so the resource exists now and the file
is the list a clerk is looking at: the SAME `account_list` read, in the same
filters, search and sort (BR-SHL-016), never a re-derivation.

**THREE COLUMNS THE RULING NAMED, AND HOW EACH IS WRITTEN:**

  * `opened_at` / `closed_at` — ISO dates, as served.
  * `account_age` — an **ISO 8601 duration** (`P7Y7M`, `P4M`, `P12D`), built by
    the same three rules the screen's age cell uses: whole years and months,
    months only under a year, days only under a month; a closed account stops
    at its Closed date; an account never opened is blank. ⚠ **A DURATION AND
    NOT "7 yrs 7 mos"**, for the reason IS-9 writes `true`/`false` and never
    `Yes`/`No`: a file is read by a spreadsheet as well as a person, the
    screen's words are in eleven languages, and the CSV has one.
  * `ageing` — the band in the list filter's own spellings (`current`,
    `31-60`, `61-90`, `90+`), and `ageing_days_past_due` beside it. Blank when
    nothing owed ages — never `current`, which is a claim about money.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.tenancy import exports as export_kernel
from core.pagination import ListParams

from . import models, seams, selectors

SLUG = "accounts"

#: The band codes → the spellings `?ageing=` already accepts (`AGEING_SEGMENT_
#: ALIASES`), so a value read out of the file can be pasted back into a filter.
_BAND_LABEL: dict[str, str] = {
    models.AccountOpeningBucket.BUCKET_CURRENT: "current",
    models.AccountOpeningBucket.BUCKET_31_60: "31-60",
    models.AccountOpeningBucket.BUCKET_61_90: "61-90",
    models.AccountOpeningBucket.BUCKET_90_PLUS: "90+",
}


def account_age_parts(
    opened: date | None, closed: date | None, today: date
) -> tuple[int, int, int] | None:
    """`(years, months, days)` from Opened to Closed-or-today — calendar
    arithmetic in the tenant's own days, `None` for an account never opened.

    A month is counted when the day of the month is reached (03/14 → 10/13 is
    6 months, → 10/14 is 7); a Closed date stops the clock. Never negative: an
    Opened date after the end (a typo the import now refuses) reads as zero.
    """
    if opened is None:
        return None
    end = closed if closed is not None else today
    if end < opened:
        return (0, 0, 0)
    months = (end.year - opened.year) * 12 + (end.month - opened.month)
    if end.day < opened.day:
        months -= 1
    years, months = divmod(months, 12)
    anchor_month = opened.month + months + years * 12
    anchor_year = opened.year + (anchor_month - 1) // 12
    anchor_month = (anchor_month - 1) % 12 + 1
    day = min(opened.day, _days_in_month(anchor_year, anchor_month))
    days = (end - date(anchor_year, anchor_month, day)).days
    return (years, months, days)


def _days_in_month(year: int, month: int) -> int:
    nxt = date(year + (month // 12), month % 12 + 1, 1)
    return (nxt - date(year, month, 1)).days


def account_age_duration(row: dict[str, Any], today: date | None = None) -> str | None:
    """The `account_age` cell: `P7Y7M`, `P4M`, `P12D` — the screen's three rules.
    Blank for an account pending activation (rule 5), as on the screen."""
    if row.get("status") == selectors.ACCOUNT_AGE_NOT_OPENED_STATUS:
        return None
    opened = _date(row.get("opened_at"))
    parts = account_age_parts(opened, _date(row.get("closed_at")), today or seams.tenant_today())
    if parts is None:
        return None
    years, months, days = parts
    if years:
        return f"P{years}Y{months}M" if months else f"P{years}Y"
    if months:
        return f"P{months}M"
    return f"P{days}D"


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _rows(params: ListParams) -> list[dict[str, Any]]:
    """The list's own rows, from the SAME read the screen pages."""
    today = seams.tenant_today()
    rows = selectors.account_list(params)
    for row in rows:
        row["account_age"] = account_age_duration(row, today)
        row["ageing_band"] = _BAND_LABEL.get(row.get("ageing_segment") or "")
    return rows


ACCOUNTS = export_kernel.ExportResource(
    name="accounts",
    slug=SLUG,
    module="customers",
    select=_rows,
    columns=(
        # The column KEYS the table declares, so a ticked-columns request
        # (`P4.13`) names the same thing on both sides.
        export_kernel.ExportColumn("account_no", "account_no"),
        export_kernel.ExportColumn("name", "name"),
        export_kernel.ExportColumn("premise", "premise"),
        export_kernel.ExportColumn("balance", "balance", export_kernel.MONEY),
        export_kernel.ExportColumn("last_bill", "last_bill_at", export_kernel.DATE),
        export_kernel.ExportColumn("status", "status_name"),
        export_kernel.ExportColumn("ageing", "ageing_band"),
        export_kernel.ExportColumn(
            "ageing_days_past_due", "ageing_days_past_due", export_kernel.NUMBER
        ),
        export_kernel.ExportColumn("opened_at", "opened_at", export_kernel.DATE),
        export_kernel.ExportColumn("closed_at", "closed_at", export_kernel.DATE),
        export_kernel.ExportColumn("account_age", "account_age"),
    ),
    sorts=selectors.ACCOUNT_SORTS,
    default_sort=selectors.ACCOUNT_DEFAULT_SORT,
    default_dir=selectors.ACCOUNT_DEFAULT_DIR,
    filters=selectors.ACCOUNT_FILTERS,
    money=True,
    basis="current-state",
    period="full-list",
)

RESOURCES = (ACCOUNTS,)


def register() -> None:
    """Called once from `CustomersConfig.ready()`."""
    for resource in RESOURCES:
        export_kernel.register_export_resource(resource)
