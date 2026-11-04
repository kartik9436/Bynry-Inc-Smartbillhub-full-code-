# ── Trace ──────────────────────────────────────────────
# Change:   CR-185-BRC10 D4 — the OWNER SUMMARY report (Customers · Statements).
#           PO 2026-10-14, verbatim: *"D4 … utility can produce thi using reort ;
#           landload cannot do it on there own today - Option 1 Summary document
#           only: one monthly statement with a section per property and a grand
#           total of $85. Each property's account keeps its own books, and they
#           still pay per property."*
# Rules:    BR-CUS-170 (the owner's bill = common areas + the base charges of
#           every unit nobody occupies) · BR-CUS-1010 (one master account per
#           address) · BR-REP-001 (a money report states its basis) ·
#           BR-REP-002 (a read model over the owner's rows) · NFR-3 (paged on the
#           server) · NFR-5 (no cap) · CLAUDE.md hard rules 1, 2 · B14 rule 31
# Tests:    06-backend/tests/test_cr185_owner_summary_report.py
# Impacts:  apps/reports/runner.py (`_OWNING_MODULES`) · apps/reports/exports.py
#           (`OWNER_SUMMARY`) · apps/reports/report_seams.py (the two reads) ·
#           apps/reports/migrations/0012_cr185_owner_summary.py (the card) ·
#           apps/billing/reporting.owner_bill_summary ·
#           apps/customers/selectors.owner_properties
# ───────────────────────────────────────────────────────
"""OWNER SUMMARY — one owner, a row per property, and a grand total.

WHAT IT IS
──────────
A statement the UTILITY runs (never a landlord self-serve page): the owner is
the customer who holds master accounts, a property is one of those accounts,
and each property's row is what the owner was BILLED on that account in the
period, split three ways — the base charges of its empty units, its common
areas, and its other owner charges (fees, taxes, adjustments). The grand total
is the sum across every property, not the page.

Worked, Maple Rentals LLC (the case the PO was shown): 12 Oak St — empty units
**$15.00**, common areas **$40.00**; 40 Elm Ave — common areas **$30.00** →
grand total **$85.00**.

WHAT IT DOES NOT DO
───────────────────
**Nothing in the ledger changes**, and nothing is billed: the figures are the
owner accounts' OWN issued bills, read through billing's published read. Each
property keeps its own books and is paid per property, exactly as before.

HOW IT IS OPENED
────────────────
`subject_id` names ANY of the owner's master accounts — the account finder,
narrowed to master accounts, is the one search box this product has for an
owner — and customers widens it to every master account the same customer
holds (`selectors.owner_properties`). Without one, no rows are read and the
report says what it needs (`controls.requires`), exactly as R24 does.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from core import errors

from apps.reports import datasets, queries
from apps.reports import report_seams as seams

KEY = "owner_summary"

#: The columns, in a reader's order: which property, then its three sections,
#: then what the property came to.
COLUMNS: tuple[str, ...] = (
    "property",
    "account",
    "bills",
    "empty_units",
    "common_areas",
    "other_charges",
    "moved_from_tenants",
    "total",
)
MONEY_COLUMNS: tuple[str, ...] = (
    "empty_units",
    "common_areas",
    "other_charges",
    "moved_from_tenants",
    "total",
)
#: The three BILLED sections (billing's read). `moved_from_tenants` is the
#: fourth part of a property's total and is not a bill — `DEF-REP-10158`.
SECTIONS: tuple[str, ...] = ("empty_units", "common_areas", "other_charges")
MOVED = "moved_from_tenants"

#: `P2.23` — one row is one property (a master account).
GRAIN = "property"

#: The page size when the caller names none. The viewer always names one; this
#: is the floor for a bare API call, so an unpaged read is never the default.
DEFAULT_PER = 50

ZERO = Decimal("0")

NO_OWNER = {
    "code": "an_owner_summary_names_one_owner",
    "br_ref": "CR-185-BRC10 · BR-CUS-1010",
    "detail": "An owner summary is about one owner, so it opens on one of their master "
    "accounts. None was named, so no rows were read.",
}
NOT_AN_OWNER_ACCOUNT = {
    "code": "the_account_is_not_an_owner_account",
    "br_ref": "CR-185-BRC10 · BR-CUS-068",
    "detail": "The account named is not a master account, so it belongs to no owner and "
    "there are no properties to summarise.",
}


def _subject_id_of(params: Any) -> str | None:
    for name in ("subject_id", "f.subject_id"):
        found = params.get(name)
        if found not in (None, ""):
            return str(found)
    return None


def _paging(params: Any) -> tuple[int, int | None]:
    raw = params.get("per")
    if raw == "all":
        per: int | None = None
    elif raw in (None, ""):
        per = DEFAULT_PER
    else:
        try:
            per = max(1, int(str(raw)))
        except (TypeError, ValueError):
            per = DEFAULT_PER
    return queries._page_number(params.get("page")), per


def owner_summary(params: Any) -> dict[str, Any]:
    """The run: the window, the owner, a page of their properties, the totals."""
    start, end = queries._checked_window(params)
    subject_id = _subject_id_of(params)
    page_no, per = _paging(params)
    if subject_id is None:
        return _shaped(start=start, end=end, owner=None, rows=[], totals=None,
                       page=None, unavailable=[NO_OWNER], currency=None)

    answer = seams.owner_properties(subject_id, page=page_no, per=per)
    if answer is None:
        # HR-1: another tenant's account and no account are the same answer.
        raise errors.deny_as_not_found("BR-TEN-003")
    if not answer.get("is_owner_account"):
        return _shaped(start=start, end=end, owner=None, rows=[], totals=None,
                       page=None, unavailable=[NOT_AN_OWNER_ACCOUNT], currency=None)

    properties = list(answer.get("properties") or ())
    all_ids = list(answer.get("all_account_ids") or ())
    billed = seams.owner_bill_summary(account_ids=all_ids, start=start, end=end)
    if billed is None:  # pragma: no cover — billing publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="reports.ownerSummary.unavailable")

    moved = _moved_from_tenants(all_ids, start=start, end=end)
    rows = [
        _row(prop, billed.get(prop["account_id"]), moved.get(str(prop["account_id"]), ZERO))
        for prop in properties
    ]
    totals = {section: ZERO for section in SECTIONS}
    totals[MOVED] = sum(moved.values(), ZERO)
    totals["total"] = totals[MOVED]
    bills = 0
    for entry in billed.values():
        for section in SECTIONS:
            totals[section] += entry[section]
        totals["total"] += entry["total"]
        bills += int(entry.get("bills") or 0)
    books, foot = _books(all_ids, end=end, grand=totals["total"])
    currencies = {entry.get("currency") for entry in billed.values() if entry.get("currency")}
    currency = next(iter(currencies)) if len(currencies) == 1 else (
        properties[0]["currency"] if properties else None
    )
    # ⚠ The classification note (`billing.reporting.OWNER_SUMMARY_CLASSIFIED_BY`)
    # is RATIONALE and is not put on the wire's `unavailable` channel, which
    # the viewer draws as sentences: B14 rule 33 puts rationale at zero words
    # on screen. It lives in billing's docstring and this one.
    return _shaped(
        start=start,
        end=end,
        owner=answer.get("owner"),
        rows=rows,
        totals={**totals, "bills": bills, "properties": int(answer.get("total") or 0)},
        page={"page": page_no, "per": per, "total": int(answer.get("total") or 0)},
        unavailable=foot,
        currency=currency,
        books=books,
    )


def _moved_from_tenants(account_ids: list[Any], *, start: Any, end: Any) -> dict[str, Decimal]:
    """`DEF-REP-10158` — per owner account, the balances moved onto it from
    departing tenants (CR-185 D5) with a BOOK date in the window.

    A move is a journal entry and not a bill, so billing's read never saw it:
    Mill Pond's summary read **$2.00** (one paper-fee bill) while the owner
    owed **$367.21**, $365.21 of it moved from AC-2026-00044 in the same
    period. It is now its own column, *Moved from tenants*, and part of each
    property's total. Read from the ledger's entry, never the tie-back promise.
    """
    found = seams.balance_to_owner_moves(start=start, end=end, account_ids=account_ids)
    out: dict[str, Decimal] = {}
    for move in found or ():
        key = str(move["to_account_id"])
        out[key] = out.get(key, ZERO) + move["amount"]
    return out


def _books(account_ids: list[Any], *, end: Any, grand: Decimal) -> tuple[Decimal | None, list]:
    """`DEF-REP-10158` — what the owner's accounts owe IN THE BOOKS at the
    window's end, struck against the grand total and never adjusted.

    The summary is the period's charges and moves; the books also hold what
    was owed before the period and every payment since. So the two agree only
    when nothing was owed before and nothing was paid — and when they do not,
    the report says so with both figures (BR-REP-008's posture), rather than
    letting a reader take the grand total for the balance.
    """
    found = seams.ar_positions(account_ids=account_ids, as_of=end)
    if not found or not found.get("available"):
        return None, [
            {
                "code": "owner_books_not_published",
                "br_ref": "DEF-REP-10158 · BR-REP-008",
                "detail": "What the owner's accounts owe in the books could not be read, so "
                "this summary cannot state whether it matches them.",
            }
        ]
    positions = found.get("positions") or {}
    books = sum((positions.get(str(account_id), ZERO) for account_id in account_ids), ZERO)
    if books == grand:
        return books, []
    return books, [
        {
            "code": "owner_summary_differs_from_the_books",
            "br_ref": "DEF-REP-10158 · BR-REP-008",
            "detail": f"The summary's grand total is {grand:f} and the owner's accounts owe "
            f"{books:f} in the books at the end of the period, a difference of "
            f"{(books - grand):f}: what was owed before the period, less what was paid. "
            "Nothing is adjusted to close it.",
        }
    ]


def _row(prop: dict[str, Any], billed: dict[str, Any] | None, moved: Decimal) -> dict[str, Any]:
    """One property. ⚠ `account_id` rides for the React key and is never a
    column (B14 rule 31); the visible reference is the ACCOUNT NUMBER.
    `total` = what was billed + what was moved onto it (`DEF-REP-10158`)."""
    figures = billed or {}
    return {
        "account_id": prop["account_id"],
        "property": prop.get("property"),
        "account": prop.get("account_no"),
        "bills": int(figures.get("bills") or 0),
        **{section: queries._money(figures.get(section, ZERO)) for section in SECTIONS},
        MOVED: queries._money(moved),
        "total": queries._money(figures.get("total", ZERO) + moved),
    }


def _shaped(
    *,
    start: Any,
    end: Any,
    owner: dict[str, Any] | None,
    rows: list[dict[str, Any]],
    totals: dict[str, Any] | None,
    page: dict[str, Any] | None,
    unavailable: list[dict[str, Any]],
    currency: str | None,
    books: Decimal | None = None,
) -> dict[str, Any]:
    reason = None if totals is not None else unavailable[0]["code"] if unavailable else None
    grand = None if totals is None else totals["total"]
    return queries._report(
        KEY,
        basis=datasets.BASIS_POSTING,
        window={"start": queries._iso(start), "end": queries._iso(end)},
        currency=currency,
        columns=COLUMNS,
        column_meta={
            name: {
                "type": datasets.TYPE_MONEY,
                "unit": None,
                "unit_from": None,
                "money_basis": datasets.BASIS_POSTING,
                "scale": 4,  # hard rule 2: stored to 4, DISPLAYED at 2.
            }
            for name in MONEY_COLUMNS
        },
        rows=rows,
        grain=GRAIN,
        controls={
            "sorts": [],
            "sort": "",
            "dir": "asc",
            "searchable": False,
            "requires": [{"param": "subject_id", "finds": "owner"}],
            # The report is a STATEMENT a utility hands to a landlord, so the
            # viewer offers Print beside Download (PO D4: *"Summary document"*).
            "printable": True,
        },
        kpis=[
            queries._kpi("grand_total", queries._money(grand), reason_code=reason),
            queries._kpi(
                "properties",
                None if totals is None else totals["properties"],
                kind="count",
                reason_code=reason,
            ),
            # DEF-REP-10158 — the owner's accounts in the books at the end of
            # the period, beside the grand total, so the two are read together.
            queries._kpi(
                "in_the_books",
                None if books is None else queries._money(books),
                reason_code=reason or (None if books is not None else "owner_books_not_published"),
            ),
        ],
        totals=(
            {}
            if totals is None
            else {
                **{section: queries._money(totals[section]) for section in SECTIONS},
                MOVED: queries._money(totals[MOVED]),
                "total": queries._money(totals["total"]),
                "bills": totals["bills"],
                "in_the_books": None if books is None else queries._money(books),
            }
        ),
        head=(
            None
            if not owner or not owner.get("name")
            else {"subject": "owner", "fields": [{"field": "owner", "value": owner["name"]}]}
        ),
        column_choices=COLUMNS,
        page=page,
        unavailable=unavailable,
    )


def owner_summary_stream(params: Any) -> Any:
    """EVERY property of the owner — the export path (never the screen's page)."""
    payload = owner_summary({**(dict(params) if params else {}), "per": "all"})
    for row in payload["rows"]:
        yield row


MODULE_COLUMNS: dict[str, tuple[str, ...]] = {KEY: COLUMNS}
MODULE_VIEWERS: dict[str, Any] = {KEY: owner_summary}
MODULE_STREAMS: dict[str, Any] = {KEY: owner_summary_stream}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-185-BRC10 · decision log 2026-10-14 "LANDLORD D2–D5" (D4) · BR-CUS-170 · BR-REP-001/002
# screens: 2·1 Report viewer at /reports/owner_summary
# generated: 2026-10-14 by lane OWNER-D4D5
# checklist: A✔ B=n/a C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: tests/test_cr185_owner_summary_report.py, SQLite and PostgreSQL 16
# exceptions: (1) the three sections are read from the stored line (`kind` and, for an empty unit's base, its own words `<unit> · <service> base charge`), because `invoice_lines` stores no unit — `billing.reporting.OWNER_SUMMARY_CLASSIFIED_BY` states it · (2) the window is the bill's ISSUE date (posting basis)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
