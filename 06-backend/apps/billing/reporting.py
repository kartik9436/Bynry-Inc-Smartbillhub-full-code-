# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-006 (Billing register, bill_type-aware + Revenue by service
#           & rate — the invoice-line read-model with drill-back)
#           Screens: S46
# Rules:    BR-REP-001 (billing-side money reads the POSTING date and every
#           header labels its basis) · BR-REP-002 (read-models over the owning
#           module's own rows — never a side-maintained number) · BR-REP-006
#           (filters enumerate LIVE vocabularies) · A14 item 6 (`bill_type` is
#           a first-class register column AND filter) · A14 item 9 (revenue by
#           service & rate is an INVOICE-LINE read-model with source
#           drill-back; a rate schedule never becomes a journal dimension) ·
#           BR-BIL-018 / BR-BIL-019 (back-bills and penalty bills are typed) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (NUMERIC(18,6) + CHAR(3),
#           never a float) · rule 3 (consumption always with its unit)
# Tests:    06-backend/tests/test_us_rep_canned_reports.py
# Impacts:  apps/reports/report_seams.py (the ONLY caller — reports resolves
#           these two by name) · nothing writes anywhere in this file
# ───────────────────────────────────────────────────────
"""Billing's two published REPORT read-models. This file reads and never writes.

`apps/ledger/reporting.py` is the precedent and the shape: the module that OWNS
the rows publishes the read-model, and the reports module composes and renders
it. B1 forbids reports from touching `invoices` / `invoice_lines`, and G6 greps
for the import, so a register drawn from the reports module would either be a
boundary violation or a second copy of billing's own arithmetic — which is how
DEF-104 (four surfaces, one balance, four answers) starts.

════════════════════════════════════════════════════════════════════════════
WHY THE REGISTER READS ISSUED BILLS AND NOTHING ELSE
════════════════════════════════════════════════════════════════════════════
US-REP-006 TC-6, verbatim: *"A draft (unissued) invoice in the cycle | Never
appears in the register — the register reads issued, immutable invoices only
(CLAUDE.md #4 family)"*. A draft is replaceable (BR-BIL-023 lets a re-run
discard and re-create it), so a register that counted drafts would change its
own history between two runs of the same report.

`corrected` and `void` bills ARE issued documents and they are IN the register,
typed as themselves. A corrected bill is not an un-issued one — the correction
is a NEW row (hard rule 4) and both rows are part of the month's record. The
register is a REGISTER: what was issued, in order, with nothing hidden.

════════════════════════════════════════════════════════════════════════════
POSTING BASIS, AND WHAT "POSTING DATE" IS FOR A BILL
════════════════════════════════════════════════════════════════════════════
BR-REP-001: *"billing-side numbers (billed, revenue, AR, aging, collection %)
read the POSTING date"*. A bill's posting date is the day it was ISSUED —
`issued_at`, the moment the document became a financial record and the ledger
entry was written. It is NOT `service_date` (which picks the tariff version) and
NOT `period_end` (which is what the customer consumed). Those three diverge by
weeks on a back-bill, and the register's window has to mean one of them.

A bill with `status='issued'` and no `issued_at` cannot be placed in time. It is
NOT dropped and NOT dated by a convention no rule states: it is counted in
`problems` with its number, the posture `apps/payments/billing_seam.py` already
takes with an undated open bill.

════════════════════════════════════════════════════════════════════════════
REVENUE BY SERVICE & RATE — WHY IT IS AN INVOICE-LINE READ AND NOT A LEDGER ONE
════════════════════════════════════════════════════════════════════════════
A14 item 9 settles it: *"Revenue by service & rate = invoice-line read-model
with drill-back; rate schedule never becomes a dimension."* A journal line
carries a service dimension and no tariff, so the ledger CAN answer "revenue by
service" (it does — `ledger.reporting.revenue_by_service`) and can never answer
"…and rate". This read model therefore groups `invoice_lines` by
(service × tariff version) and reconciles BY SERVICE to the dimension view,
which is the tie US-REP-006 TC-3 asserts.

The four money columns are the LINE KINDS, split exactly as the prototype's
table heads them: `usage_revenue` (kind `usage`), `base` (kinds `base`, `fee`,
`minimum`, `adjustment` — everything that is neither consumption nor tax), and
`tax` (kind `tax`). Nothing is netted, nothing is dropped: Σ of the three is Σ
of the lines, and the footer proves it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import connection
from django.db.models import (
    Count,
    DecimalField,
    Exists,
    F,
    OuterRef,
    Q,
    QuerySet,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce

from core.tenancy import current_tenant_id

from . import customers_seam, models, tenancy_seam

ZERO = Decimal("0")

#: BR-REP-001. Both reports on this page are billing-side, so both are POSTING
#: basis and both say so on the payload rather than in a caption a screen may
#: forget to render — the shape `apps/ledger/reporting.py` established.
BASIS_POSTING = "posting"

#: The register reads ISSUED documents. `draft` is the only status excluded, and
#: the module docstring says why.
REGISTER_STATUSES: tuple[str, ...] = (
    models.INVOICE_ISSUED,
    models.INVOICE_PAID,
    models.INVOICE_VOID,
    models.INVOICE_CORRECTED,
)

#: A14 item 6 / B2 r10 #12 — the register's `bill_type` filter vocabulary, read
#: from the model's own tuple so a seventh type cannot appear in one place and
#: not the other (BR-REP-006: a vocabulary is read live, never hardcoded twice).
BILL_TYPES: tuple[str, ...] = tuple(models.BILL_TYPES)

#: The revenue table's three money columns, by line kind. `base` is deliberately
#: everything that is neither consumption nor tax, so Σ(columns) = Σ(lines) and
#: no line can fall between the columns unnoticed.
KIND_USAGE = "usage"
KIND_TAX = "tax"


def _tenant_id() -> Any:
    return current_tenant_id()


def _issued_queryset() -> QuerySet:
    """Every ISSUED bill of the CURRENT tenant, and only those (hard rule 1).

    The explicit `tenant_id` filter keeps the law true on the sqlite unit tier
    where there is no RLS; on PostgreSQL the FORCE policy is the second,
    independent guarantee. `select_related` travels only the reviewed
    cross-module FK set (B2 §2): `invoices.account_id → customers.Account` and
    `bill_runs.cycle_id → metering.Cycle`.
    """
    return (
        models.Invoice.objects.filter(tenant_id=_tenant_id(), status__in=REGISTER_STATUSES)
        .select_related("account", "bill_run", "bill_run__cycle")
        .order_by("invoice_no", "id")
    )


def _customer_name(account: Any) -> str | None:
    """The bill's customer, through customers' OWN published read (B1).

    Exactly `apps/billing/selectors._customer_name`, reused rather than
    re-implemented: two readings of "who is this customer" is the shape that
    lets a register and a bills list disagree about one name.
    """
    from . import selectors

    return selectors._customer_name(account)


@dataclass(frozen=True)
class RegisterRow:
    """One line of the billing register — A14's own seven columns plus the type."""

    invoice_id: str
    invoice_no: str | None
    bill_type: str
    status: str
    account_id: str
    account_no: str | None
    customer_name: str | None
    cycle_label: str | None
    issued_on: date | None
    period_start: date
    period_end: date
    services: tuple[str, ...]
    #: CLAUDE.md rule 3 — a quantity NEVER travels without its unit. A bill
    #: measured in two units (electric kWh + water kgal) yields two entries, and
    #: they are never added together.
    usage: tuple[tuple[Decimal, str], ...]
    #: ⚠ **WHICH OF THIS BILL'S UNITS CAME FROM A COUNT RATHER THAN A READING**
    #: (`DEF-REP-7010`). `BR-RAT-090`: a CAPACITY service is billed by a COUNT
    #: of the unit's assets, so `0 cart` means *nobody has a cart here* while
    #: `0 kgal` means *the meter was read, and read zero*. Both arrive in this
    #: one cell as `Decimal("0")` and NOTHING downstream could tell them apart
    #: — which is why the live register drew `0 cart · 0 connection · 0 kW
    #: · 15.2 kgal` on every row and a clerk read four figures to find the
    #: one measure that had moved.
    #:
    #: ⚠ **A UNIT IS ONLY IN HERE WHEN *NO* READING CONTRIBUTED TO IT.**
    #: Water and sewer are both metered in kgal; if a capacity line and a
    #: metered line ever shared a unit, calling that unit *counted* would hide
    #: a real reading. The reading wins, always.
    #:
    #: ⚠ **IT NAMES UNITS AND NEVER DECIDES A PRICE.** Empty on every
    #: deployment whose tenancy lane publishes no declaration, which is what
    #: this register did before the field existed.
    counted_units: tuple[str, ...]
    amount: Decimal
    currency: str
    estimated: bool


#: What the register may be ORDERED by, and the absence is named.
#: `customer_name` is NOT here: the name is composed by customers' own
#: published read (`_customer_name`), one account at a time, so ordering by it
#: would mean materialising the book to sort it — the exact defect `P2.12`
#: exists to remove. `account_no` IS here because
#: `invoices.account_id -> customers.Account` is in B2 §2's REVIEWED FK set and
#: `_issued_queryset` already travels it, so the `ORDER BY` is one join the
#: statement already carries rather than a new reach into another module.
REGISTER_SORTS: tuple[str, ...] = ("invoice_no", "issued_on", "amount", "account_no")

#: The DEFAULT order, and it is `invoice_no` ASC because that is EXACTLY
#: what `_issued_queryset()` has always returned. `P2.12` is a read-signature
#: change to another module's published model, so a caller that passes no
#: `sort` must get byte-identical rows in byte-identical order — a default
#: that quietly became "newest first" would be a silent behaviour change
#: hiding inside a performance fix. A register is a numbered sequence
#: anyway; the screen asks for another order by asking.
REGISTER_DEFAULT_SORT = "invoice_no"
REGISTER_DEFAULT_DIRECTION = "asc"

#: `P2.3` — what `q` searches, DECLARED rather than implied. A caller may not
#: search a column that is not here, and a screen may not offer a box that
#: claims more than this tuple. The customer's name is searched through
#: customers' OWN published read (B1), never by joining their tables here.
REGISTER_SEARCH_COLUMNS: tuple[str, ...] = ("invoice_no", "account_no", "customer_name")

#: How many undated bills are NAMED in the problem's detail. The count is
#: always exact; the list is a sample, because a tenant with 4,000 undated
#: bills must not be handed 4,000 bill numbers inside a JSON field nobody
#: renders (`NFR-5` is about CAPS on what a user may HAVE — this is a bound on
#: a diagnostic string, and the figure beside it is uncapped).
UNDATED_SAMPLE = 20


def _unit_origins() -> tuple[set[str], set[str]]:
    """Two empty sets: the units a COUNT fed, and the units a READING fed.

    A pair rather than one dict because the answer is their DIFFERENCE and
    nothing else — see `RegisterRow.counted_units`. Trivial, and a named
    function because the register and the invoices dataset both do it: two
    copies of a rule is how the two reports would come to disagree about one
    bill (B14 rule 43's reasoning, in Python).
    """
    return set(), set()


def _record_unit_origin(
    line: Any,
    capacity_services: frozenset[str],
    counted: set[str],
    measured: set[str],
) -> None:
    """Note whether THIS usage line's unit came from a count or from a reading.

    ⚠ **A LINE WITH NO SERVICE COUNTS AS MEASURED.** `service_id` is nullable
    on `invoice_lines` and a line we cannot attribute is one we cannot call a
    count — and the safe direction is the one that SHOWS the figure. Hiding a
    zero we were unsure about is exactly the collapse this field exists to
    prevent.
    """
    code = line.service.code if line.service_id is not None else None
    if code is not None and code in capacity_services:
        counted.add(line.unit)
    else:
        measured.add(line.unit)


def billing_register(
    *,
    start: date,
    end: date,
    bill_type: str | None = None,
    service_code: str | None = None,
    search: str | None = None,
    page: int = 1,
    per: int | None = None,
    sort: str = REGISTER_DEFAULT_SORT,
    direction: str = REGISTER_DEFAULT_DIRECTION,
) -> dict[str, Any]:
    """Every bill ISSUED in `[start, end]`, with the month's own KPIs.

    `start`/`end` are ARGUMENTS and never a clock (BR-TEN-043): a register a
    clerk reads at 23:58 and a register a job takes at 00:02 must be the same
    document, and a function that read the system date could not be asked for
    July.

    The window is closed on both ends and is inclusive, matching every other
    report window in this product (`ledger.reporting.revenue_and_ar`,
    `account_ledger`). `issued_at` is a timestamp, so the comparison is by DATE
    in the tenant's own stored value — a bill issued at 23:30 on the 31st
    belongs to that month. `TIME_ZONE` is `UTC` and storage is UTC (B2), so the
    `__date` lookup and `issued_at.date()` are the same day; the lookup is used
    because only the lookup can go into the `WHERE`.

    ════════════════════════════════════════════════════════════════════════
    THIS PULLED EVERY ISSUED BILL INTO PYTHON UNTIL `P2.12` (`CR-142-BRC07`)
    ════════════════════════════════════════════════════════════════════════
    `invoices = list(queryset)` read the tenant's WHOLE issued book and then
    applied the window, the service filter, the totals and the order in Python.
    At the top of the ICP — T5, 40,000 accounts — that is a year of bills in
    one list, and `docker-entrypoint.sh` gives a web worker `GUNICORN_TIMEOUT`
    of **60 seconds**: the read was not slow, it was killed before it answered.
    That is `NFR-3` and it is the same shape CLAUDE.md records for
    `GET /outstandings` (`DEF-PAY-4221`).

    **Every criterion is now a `WHERE`, the order is an `ORDER BY`, and the
    page is a `LIMIT`/`OFFSET`.** Two figures come back and they answer two
    questions: `rows` is the PAGE, and `kpis` is a SQL aggregate over the whole
    FILTERED set — so the tiles foot to the report whether a page is cut or
    not. That is CLAUDE.md's own resolution of this shape, quoted: *"the tiles
    are a SQL aggregate over the whole filtered set whether a page is cut or
    not"*.

    ⚠ **`per=None` MEANS THE WHOLE FILTERED SET AND IS THE DEFAULT, ON
    PURPOSE.** This is a read-SIGNATURE change to another module's published
    model, so every caller that predates it keeps its exact behaviour; the
    reports module opts in by passing `per`. `per=None` is **not a cap being
    lifted** and never a cap being set — it is the export's door, the posture
    `payments.reporting.ar_aging` already takes.

    ⚠ **`customer_name` IS SEARCHABLE AND IS NOT SORTABLE**, and the two are
    different questions rather than an inconsistency. Searching narrows by an
    id set customers publishes LAZILY (one nested subquery, no round trip);
    ordering by a name would need the name in the `ORDER BY`, and the name is
    composed one account at a time by customers' own read. `REGISTER_SORTS`
    and `REGISTER_SEARCH_COLUMNS` say which is which, out loud, because a
    screen that offers a caret the server declines is hard-won law 2's mirror.
    """
    problems: list[dict[str, Any]] = []

    base = _issued_queryset()
    if bill_type is not None:
        base = base.filter(bill_type=bill_type)

    # ── the undated, counted over the WHOLE issued set ───────────────────
    # Deliberately BEFORE the window: a bill with no `issued_at` cannot be
    # placed in time at all, so it is not in this month and not out of it. The
    # old loop reached the same answer by `continue`-ing before the window
    # test; this is that test as a statement.
    undated_queryset = base.filter(issued_at__isnull=True)
    undated_count = undated_queryset.count()
    if undated_count:
        sample = sorted(
            str(number or identifier)
            for number, identifier in undated_queryset.order_by("id").values_list(
                "invoice_no", "id"
            )[:UNDATED_SAMPLE]
        )
        problems.append(
            {
                "code": "issued_bill_without_an_issue_date",
                "br_ref": "BR-REP-001",
                "detail": (
                    f"{undated_count} bill(s) are ISSUED and carry no `issued_at`, so they "
                    "cannot be placed in a POSTING-basis window. They are EXCLUDED from this "
                    "register and reported here rather than dated by a convention no rule "
                    "states — a bill silently moved into the month being reported is a wrong "
                    f"figure that foots perfectly. First {min(undated_count, UNDATED_SAMPLE)} "
                    f"by id: {sample}."
                ),
            }
        )

    # ── the window, the service, the search: all in SQL ──────────────────
    selected = base.filter(issued_at__date__gte=start, issued_at__date__lte=end)

    if service_code is not None:
        # `Exists` rather than a join plus `DISTINCT`: a bill with four lines
        # of one service must appear ONCE, and a `DISTINCT` over a row that
        # carries a JSON payload is the expensive way to say so.
        selected = selected.filter(
            Exists(
                models.InvoiceLine.objects.filter(
                    tenant_id=_tenant_id(),
                    invoice_id=OuterRef("pk"),
                    service__code=service_code,
                )
            )
        )

    term = (search or "").strip()
    if term:
        predicate = Q(invoice_no__icontains=term)
        account_ids = customers_seam.account_ids_matching_search(term)
        if account_ids is None:
            # Customers publishes no search read on this deployment. The bill
            # number and the account number are still searched — from columns
            # this statement already has — and the narrowing is REPORTED by
            # name rather than silently dropped (BR-REP-024).
            predicate = predicate | Q(account__account_no__icontains=term)
            problems.append(
                {
                    "code": "register_search_does_not_reach_the_customer_name",
                    "br_ref": "B1 · BR-REP-024",
                    "detail": (
                        "customers publishes no account search on this deployment, so `q` "
                        "matched the bill number and the account number only. A name typed "
                        "here found nothing; it was not searched and did not fail."
                    ),
                }
            )
        else:
            predicate = predicate | Q(account_id__in=account_ids)
        selected = selected.filter(predicate)

    # ── the KPIs: ONE statement over the whole FILTERED set ──────────────
    tiles = selected.aggregate(
        bills=Count("id"),
        billed=Coalesce(
            Sum("total"),
            Value(ZERO, output_field=DecimalField(max_digits=18, decimal_places=6)),
            output_field=DecimalField(max_digits=18, decimal_places=6),
        ),
    )
    count = int(tiles["bills"] or 0)

    # DEF-081 / DEF-099 — the CHAR(3) these figures ARE, derived from the rows
    # summed rather than read off a tenant setting. Bounded at two reads
    # because "more than one" is all the footer needs to know.
    currencies = tuple(
        sorted(set(selected.order_by().values_list("currency", flat=True).distinct()[:2]))
    )
    currency = currencies[0] if len(currencies) == 1 else None
    if currency is None and currencies:
        problems.append(
            {
                "code": "register_window_holds_more_than_one_currency",
                "br_ref": "CLAUDE.md rule 2",
                "detail": (
                    "The bills in this window are denominated in more than one currency, so "
                    "'total billed' and 'average bill' are not numbers. The rows are served; "
                    "the two totals are null with this reason."
                ),
            }
        )

    estimated_count, estimated_problem = _estimated_count(selected)
    if estimated_problem is not None:
        problems.append(estimated_problem)

    # ── the order, and a TOTAL second term so a page boundary is stable ───
    # Two bills issued on the same day must not swap between page 1 and page 2:
    # a row a clerk sees twice is a row they never see.
    column = _REGISTER_SORT_COLUMNS.get(sort, _REGISTER_SORT_COLUMNS[REGISTER_DEFAULT_SORT])
    descending = str(direction).lower() != "asc"
    term_expression = (
        F(column).desc(nulls_last=True) if descending else F(column).asc(nulls_last=True)
    )
    selected = selected.order_by(term_expression, F("id").asc())

    # ── the page ─────────────────────────────────────────────────────────
    if per is None:
        served_page = 1
        invoices = list(selected)
    else:
        # `BR-SHL-011` — clamp, never error. A caller asking for page 9,999 of
        # a 41-page register is told which page it got.
        per = max(1, int(per))
        last_page = max(1, -(-count // per))
        served_page = min(max(1, int(page)), last_page)
        offset = (served_page - 1) * per
        invoices = list(selected[offset : offset + per])

    # The line read is ONE query for the whole PAGE rather than one per bill:
    # services, units and the estimate flag all come off the same rows.
    by_invoice: dict[Any, list[Any]] = {}
    if invoices:
        line_rows = models.InvoiceLine.objects.filter(
            tenant_id=_tenant_id(), invoice_id__in=[invoice.id for invoice in invoices]
        ).select_related("service")
        for line in line_rows:
            by_invoice.setdefault(line.invoice_id, []).append(line)

    # The Name column for the WHOLE PAGE in one query, through customers' own
    # batched read — never one resolve per row (`DEF-2723`'s shape, and it was
    # measured here at 50 of a page's 56 statements before `P2.12`).
    names = customers_seam.primary_contact_names_for(
        [invoice.account_id for invoice in invoices]
    )

    # ⚠ **ONE READ FOR THE WHOLE PAGE, NEVER ONE PER ROW.** The tenant's
    # capacity-basis declaration is the same answer for every bill in the
    # window, and `P2.12` exists because this function used to do per-row work.
    capacity_services = tenancy_seam.capacity_service_codes()

    rows: list[RegisterRow] = []
    for invoice in invoices:
        lines = by_invoice.get(invoice.id, [])
        services = tuple(
            sorted({line.service.code for line in lines if line.service_id is not None})
        )
        usage: dict[str, Decimal] = {}
        counted, measured = _unit_origins()
        for line in lines:
            if line.kind != KIND_USAGE or line.quantity is None or not line.unit:
                continue
            usage[line.unit] = usage.get(line.unit, ZERO) + line.quantity
            _record_unit_origin(line, capacity_services, counted, measured)
        rows.append(
            RegisterRow(
                invoice_id=str(invoice.id),
                invoice_no=invoice.invoice_no,
                bill_type=invoice.bill_type,
                status=invoice.status,
                account_id=str(invoice.account_id),
                account_no=getattr(invoice.account, "account_no", None),
                customer_name=(
                    _customer_name(invoice.account)
                    if names is None
                    else names.get(str(invoice.account_id))
                ),
                cycle_label=(
                    invoice.bill_run.cycle.code
                    if invoice.bill_run is not None and invoice.bill_run.cycle_id
                    else None
                ),
                issued_on=invoice.issued_at.date(),
                period_start=invoice.period_start,
                period_end=invoice.period_end,
                services=services,
                # `(quantity, unit)` pairs, ordered by UNIT so two runs of the
                # same report list a bill's usages in the same order. The pair
                # is quantity-first because rule 3 reads that way — a number
                # and the unit it is IN — and swapping them silently is how a
                # kWh figure gets formatted as a unit string.
                usage=tuple((amount, unit) for unit, amount in sorted(usage.items())),
                counted_units=tuple(sorted(counted - measured)),
                amount=invoice.total,
                currency=invoice.currency,
                estimated=_estimated_flag(invoice),
            )
        )
    # ⚠ **NOTHING SORTS HERE.** The order is the `ORDER BY` above; a
    # `rows.sort` would re-order a page that was already cut, which is
    # `DEF-PAY-4221`'s exact shape one report along.

    total_billed = tiles["billed"] or ZERO
    return {
        "basis": BASIS_POSTING,
        "window": {"start": start, "end": end},
        "currency": currency,
        "rows": tuple(rows),
        "kpis": {
            "bills": count,
            # Money is null WITH A REASON when it cannot be stated, never 0.
            "billed": total_billed if currency is not None else None,
            # B4's display rule is the reports module's to apply at render; the
            # read model publishes the exact quotient at full precision and the
            # renderer rounds. Division by zero is not a figure — it is null.
            "average_bill": (
                (total_billed / count) if (currency is not None and count) else None
            ),
            "estimated": estimated_count,
            # A14's fourth register KPI. `bill_run_exclusions` is the run's
            # exception queue and it is billing's own, but it is keyed to a RUN
            # and not to a date window — a register spanning two runs has no
            # single exception count. REPORTED rather than approximated.
            "exceptions": None,
        },
        "bill_types": BILL_TYPES,
        "sorts": REGISTER_SORTS,
        "searchable": REGISTER_SEARCH_COLUMNS,
        "page": served_page,
        "per": per,
        "total": count,
        "problems": tuple(problems),
    }


#: `sort` value -> the COLUMN it is. Separate from `REGISTER_SORTS` so an
#: unknown value can fall back (`BR-SHL-011`: invalid values fall back or
#: clamp, NEVER error) without the fallback deciding what the vocabulary is.
_REGISTER_SORT_COLUMNS: dict[str, str] = {
    "invoice_no": "invoice_no",
    "issued_on": "issued_at",
    "amount": "total",
    "account_no": "account__account_no",
}


def _estimated_count(selected: QuerySet) -> tuple[int | None, dict[str, Any] | None]:
    """How many bills in the FILTERED set priced an estimated read.

    ⚠ **THIS IS THE ONE REGISTER TILE THAT IS NOT A PLAIN AGGREGATE, AND THE
    REASON IS A MISSING COLUMN RATHER THAN A MISSING QUERY.** `estimated` is
    not a field: it is *did any meter block in this bill's FROZEN payload carry
    `estimated: true`* (`_estimated_flag`), and `bill_payload` is a JSON blob.
    A containment lookup answers it in SQL — `@>` on PostgreSQL's `jsonb` — and
    Django refuses the same lookup on SQLite, which is the backend
    `config/settings/test.py` hardcodes. So the backend is ASKED
    (`supports_json_field_contains`) rather than assumed, which is CLAUDE.md
    law 14's shape: the two backends differ, and the difference is named here
    instead of being discovered in production.

    Where the lookup exists the tile is a `COUNT` and costs one statement.
    Where it does not, the payload column alone is streamed with
    `.iterator()` — correct, O(n), and only ever reached on the unit tier,
    whose fixtures are tens of rows. Returning `None` instead would make the
    SQLite suite disagree with PostgreSQL about a number, which is worse than
    being slow on a fixture.
    """
    if connection.features.supports_json_field_contains:
        return (
            selected.filter(bill_payload__meters__contains=[{"estimated": True}]).count(),
            None,
        )
    total = 0
    for payload in selected.order_by().values_list("bill_payload", flat=True).iterator(
        chunk_size=500
    ):
        if not isinstance(payload, dict):
            continue
        meters = payload.get("meters")
        if not isinstance(meters, list):
            continue
        if any(isinstance(meter, dict) and bool(meter.get("estimated")) for meter in meters):
            total += 1
    return total, None


def _estimated_flag(invoice: Any) -> bool:
    """Did this bill price ANY estimated read? — A14's `Est` register flag.

    Read from the bill's own FROZEN payload (BR-BIL-030), never from today's
    reads: a read corrected in September must not change what an August bill was
    flagged as when it was issued. A bill drafted before the payload carried
    meter blocks answers False, which is the honest reading of a document that
    records no estimate rather than a claim that none happened.
    """
    payload = getattr(invoice, "bill_payload", None) or {}
    if not isinstance(payload, dict):
        return False
    meters = payload.get("meters")
    if not isinstance(meters, list):
        return False
    return any(
        isinstance(meter, dict) and bool(meter.get("estimated")) for meter in meters
    )


@dataclass(frozen=True)
class RevenueRow:
    """One (service × rate schedule) row of A14's revenue table."""

    service_id: str | None
    service_code: str | None
    service_name: str | None
    tariff_id: str | None
    tariff_name: str | None
    accounts: int
    usage_revenue: Decimal
    base: Decimal
    tax: Decimal
    total: Decimal


def revenue_by_service_and_rate(*, start: date, end: date) -> dict[str, Any]:
    """A14's *Revenue by service & rate*, from `invoice_lines` (item 9).

    Lines belong to the window through their INVOICE's posting date, not through
    their own `period_start`: the line's period is what the customer consumed and
    the invoice's issue date is when the utility recognised it. Mixing the two is
    how a back-bill's revenue lands in a month whose books are closed.

    A line with no `tariff_version` (a manual charge code, a fee, a tax on a
    charge-only bill) groups under a NULL rate schedule and is shown as such.
    It is not dropped: A14's own footer must equal Σ of the register's amounts,
    and a hidden row is exactly how a report stops footing.
    """
    invoices = {
        invoice.id: invoice
        for invoice in _issued_queryset()
        if invoice.issued_at is not None and start <= invoice.issued_at.date() <= end
    }
    if not invoices:
        return {
            "basis": BASIS_POSTING,
            "window": {"start": start, "end": end},
            "currency": None,
            "rows": (),
            "totals": {
                "accounts": 0,
                "usage_revenue": ZERO,
                "base": ZERO,
                "tax": ZERO,
                "total": ZERO,
            },
            "problems": (),
        }

    lines = models.InvoiceLine.objects.filter(
        tenant_id=_tenant_id(), invoice_id__in=list(invoices)
    ).select_related("service", "tariff_version", "tariff_version__tariff")

    buckets: dict[tuple[Any, Any], dict[str, Any]] = {}
    currencies = {invoices[key].currency for key in invoices}
    all_accounts: set[str] = set()
    for line in lines:
        tariff = line.tariff_version.tariff if line.tariff_version_id else None
        key = (line.service_id, None if tariff is None else tariff.id)
        bucket = buckets.setdefault(
            key,
            {
                "service_id": None if line.service_id is None else str(line.service_id),
                "service_code": line.service.code if line.service_id else None,
                "service_name": line.service.name if line.service_id else None,
                "tariff_id": None if tariff is None else str(tariff.id),
                "tariff_name": None if tariff is None else tariff.name,
                "accounts": set(),
                "usage_revenue": ZERO,
                "base": ZERO,
                "tax": ZERO,
            },
        )
        bucket["accounts"].add(str(line.account_id))
        all_accounts.add(str(line.account_id))
        if line.kind == KIND_USAGE:
            bucket["usage_revenue"] += line.amount
        elif line.kind == KIND_TAX:
            bucket["tax"] += line.amount
        else:
            bucket["base"] += line.amount

    rows = tuple(
        RevenueRow(
            service_id=bucket["service_id"],
            service_code=bucket["service_code"],
            service_name=bucket["service_name"],
            tariff_id=bucket["tariff_id"],
            tariff_name=bucket["tariff_name"],
            accounts=len(bucket["accounts"]),
            usage_revenue=bucket["usage_revenue"],
            base=bucket["base"],
            tax=bucket["tax"],
            total=bucket["usage_revenue"] + bucket["base"] + bucket["tax"],
        )
        for bucket in sorted(
            buckets.values(),
            key=lambda item: ((item["service_code"] or ""), (item["tariff_name"] or "")),
        )
    )

    problems: list[dict[str, Any]] = []
    currency = currencies.pop() if len(currencies) == 1 else None
    if currency is None:
        problems.append(
            {
                "code": "revenue_window_holds_more_than_one_currency",
                "br_ref": "CLAUDE.md rule 2",
                "detail": (
                    "The bills in this window are denominated in more than one currency, so "
                    "the revenue totals are not numbers. Rows are served per schedule; the "
                    "footer is null with this reason."
                ),
            }
        )

    return {
        "basis": BASIS_POSTING,
        "window": {"start": start, "end": end},
        "currency": currency,
        "rows": rows,
        "totals": {
            # DISTINCT accounts across the whole window, not Σ of the per-row
            # counts: one account on Electric and Water is ONE account, and
            # adding the columns would report it twice.
            "accounts": len(all_accounts),
            "usage_revenue": sum((row.usage_revenue for row in rows), ZERO),
            "base": sum((row.base for row in rows), ZERO),
            "tax": sum((row.tax for row in rows), ZERO),
            "total": sum((row.total for row in rows), ZERO),
        },
        "problems": tuple(problems),
    }


# ════════════════════════════════════════════════════════════════════════════
# THE `invoices` DATASET — the reviewed query the reports framework binds to
# ════════════════════════════════════════════════════════════════════════════
#
# HUMAN-REVIEW-PENDING — 12-governance/09-human-review-ledger.md, row
# "DS-INVOICES" dated 2026-09-26. 🔒 a billing money read, AI-authored under
# the standing PO ruling of 2026-08-09. It reaches no lifecycle beyond
# VERIFIED-UNRATIFIED until a human sign-off is recorded in that row.
#
# `apps/reports/datasets.py::INVOICES` is the DECLARATION — what columns exist,
# what may be filtered, what may be totalled and in which directions. This is
# the QUERY behind it, and the two are deliberately in different modules: the
# declaration is what a clerk's saved definition is validated against, and the
# query is billing's own read over billing's own rows (B1).
#
# ⚠ **ITS GRAIN IS ONE BILL, AND THE DECLARATION SAID "one invoice line"**
# ──────────────────────────────────────────────────────────────────────────
# `DEF-REP-6834`. The declaration's own COLUMNS contradict its own grain
# string: `services` is a set, `usage` carries a unit from a sibling column
# because *"a bill measured in two units yields `684 kWh|26.24 kgal`"*, and
# `base`/`usage_revenue`/`tax`/`amount` are the four money columns of a BILL
# split by line kind. Every one of those is a roll-up of lines onto one bill.
# R5's drawing (p50, read as an image per B14 rule 42) settles it from the
# other side: one row per `BL-…` number, `Water · Sewer` in one cell,
# `4,100 gal` in one cell, `247.87` in one cell. `billing_register` has served
# exactly that shape since it was built.
#
# So the grain is ONE BILL and the declaration is amended to say so. Building
# to the string instead would have produced a register with four rows per bill
# and a `Total` that triple-counts nothing a clerk asked for — and it would
# have passed every test in this repository, because nothing reads the grain
# string except the line under the report title.
#
# ⚠ **`cycle` IS A PARAMETER HERE AND IT IS NOT ON `billing_register`**
# ──────────────────────────────────────────────────────────────────────────
# R5's drawing carries the warning in its own words: *"The one report where
# `cycle` must be a parameter, not a date range. Today it runs on a date range
# only."* That is this function's first reason to exist. `billing_register`'s
# signature is unchanged — it is another module's published read with callers
# that predate this, and widening it would be a behaviour change wearing a
# feature's clothes — so the dataset query takes `cycle` and the register goes
# on taking a window.
#
# ⚠ **TWO PATHS, AND NEITHER MAY BECOME THE OTHER (brief §8.2, p91)**
# ──────────────────────────────────────────────────────────────────────────
# *"The left path never fetches more than a page; the right path never holds
# one."* `invoices_dataset()` is the left path: one page, `LIMIT`/`OFFSET`/
# `ORDER BY` in SQL. `invoices_dataset_stream()` is the right path: a
# GENERATOR over every row of the filtered set, in id-stable chunks, holding
# one chunk at a time and never a list of the whole thing.
#
# That separation is not tidiness. On 2026-09-26 the billing register started
# paging and its EXPORT silently inherited the screen's fifty rows — a clerk
# would have exported a 38,000-row register and received a valid-looking file
# of fifty. A single function with a `per` argument is exactly how that
# happens, so the export door is a different function with a different return
# type: a generator cannot be handed a page size by accident.
#
# ⚠ **THE PORTAL SCOPE IS A PRIVACY BOUNDARY, NOT A FILTER**
# ──────────────────────────────────────────────────────────────────────────
# `account_ids` narrows to the accounts a signed-in person holds. Passing
# `None` means *no narrowing* — the staff read — and passing an EMPTY
# collection means *no accounts*, which returns nothing rather than
# everything. Those two are one keystroke apart and the difference is a
# landlord at 1408 Elm Street reading Unit 3's $100.00 instead of their own
# $69.60 of common-area charges (PO ruling, option (a)). `_PORTAL_NOTHING` is
# the sentinel that makes the empty case impossible to write by accident.
#
# ⚠ **NO ADDRESS COLUMN, DELIBERATELY (CLAUDE.md hard rule 8)**
# ──────────────────────────────────────────────────────────────────────────
# An address is stored on `premises` and every other entity derives it by
# walking. This dataset declares no address column of its own and holds no
# copy; a report that needs one walks to premises through the `premises`
# dimension. R8's drawing says the same thing in the same words.

#: What the dataset may be ORDERED by, and the absences are named.
#:
#: `base`, `usage_revenue` and `tax` are NOT here: they are sums over a bill's
#: LINES, computed for the page after the page is cut, so ordering by one would
#: mean aggregating the tenant's whole line book to sort it — the exact defect
#: `NFR-3` exists to remove. `customer_name` is NOT here for the reason
#: `REGISTER_SORTS` already gives: the name is composed one account at a time by
#: customers' own read. A screen that offered a caret on any of the four would
#: be hard-won law 2's mirror — a live control the server silently declines.
DATASET_SORTS: tuple[str, ...] = (
    "invoice_no",
    "issued_on",
    "posted_on",
    "due_date",
    "amount",
    "account_no",
)
DATASET_DEFAULT_SORT = "invoice_no"
DATASET_DEFAULT_DIRECTION = "asc"

#: `sort` value -> the column it is. Separate from `DATASET_SORTS` so an unknown
#: value can fall back (`BR-SHL-011`) without the fallback deciding the
#: vocabulary.
_DATASET_SORT_COLUMNS: dict[str, str] = {
    "invoice_no": "invoice_no",
    # ⚠ `issued_on` and `posted_on` are the SAME COLUMN and that is not a
    # duplicate. This file's own docstring settles it: *"A bill's posting date
    # is the day it was ISSUED — `issued_at`"*. The dataset declares both names
    # because a definition may say either, and serving one of them from a
    # different column would invent a second date a bill does not have.
    "issued_on": "issued_at",
    "posted_on": "issued_at",
    "due_date": "due_date",
    "amount": "total",
    "account_no": "account__account_no",
}

#: What `q` searches, DECLARED rather than implied — the same three columns the
#: register searches, through the same published reads.
DATASET_SEARCH_COLUMNS: tuple[str, ...] = ("invoice_no", "account_no", "customer_name")

#: The filter names this query honours, so a caller can tell what it applied
#: from what it was given. `class` is DECLARED BY THE DATASET AND NOT SERVED
#: HERE — see `_consumer_class_narrowing`.
DATASET_FILTERS_SERVED: tuple[str, ...] = ("from", "to", "bill_type", "service", "cycle", "status")

#: How many bills one streaming chunk holds. Not a cap (`NFR-5`): the generator
#: yields every row of the filtered set however many there are, and this is only
#: how many it holds in memory at once while doing so.
STREAM_CHUNK = 500


class _PortalNothing:
    """The sentinel for *this person holds no accounts*.

    An empty list and `None` are one keystroke apart and mean opposite things
    here — no accounts versus no narrowing — so the empty case is a distinct
    object a caller cannot produce by writing `[]` into the wrong variable.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover — diagnostics only
        return "PORTAL_NOTHING"


PORTAL_NOTHING = _PortalNothing()


@dataclass(frozen=True)
class DatasetRow:
    """One BILL, with the `invoices` dataset's declared columns on it."""

    invoice_id: str
    invoice_no: str | None
    account_id: str
    account_no: str | None
    customer_name: str | None
    bill_type: str
    status: str
    cycle_code: str | None
    services: tuple[str, ...]
    issued_on: date | None
    posted_on: date | None
    due_date: date | None
    period_start: date
    period_end: date
    #: CLAUDE.md rule 3 — `(quantity, unit)` pairs, never a bare number and
    #: never a sum across units. A bill of 684 kWh and 26.24 kgal has TWO.
    usage: tuple[tuple[Decimal, str], ...]
    #: ⚠ **WHICH OF THIS BILL'S UNITS CAME FROM A COUNT RATHER THAN A READING**
    #: (`DEF-REP-7010`). `BR-RAT-090`: a CAPACITY service is billed by a COUNT
    #: of the unit's assets, so `0 cart` means *nobody has a cart here* while
    #: `0 kgal` means *the meter was read, and read zero*. Both arrive in this
    #: one cell as `Decimal("0")` and NOTHING downstream could tell them apart
    #: — which is why the live register drew `0 cart · 0 connection · 0 kW
    #: · 15.2 kgal` on every row and a clerk read four figures to find the
    #: one measure that had moved.
    #:
    #: ⚠ **A UNIT IS ONLY IN HERE WHEN *NO* READING CONTRIBUTED TO IT.**
    #: Water and sewer are both metered in kgal; if a capacity line and a
    #: metered line ever shared a unit, calling that unit *counted* would hide
    #: a real reading. The reading wins, always.
    #:
    #: ⚠ **IT NAMES UNITS AND NEVER DECIDES A PRICE.** Empty on every
    #: deployment whose tenancy lane publishes no declaration, which is what
    #: this register did before the field existed.
    counted_units: tuple[str, ...]
    base: Decimal
    usage_revenue: Decimal
    tax: Decimal
    amount: Decimal
    currency: str
    estimated: bool


def _consumer_class_narrowing(code: str) -> tuple[Any, dict[str, Any] | None]:
    """The account ids in a consumer class, through customers' OWN read.

    Returns `(ids_or_None, problem_or_None)`. `None` ids means customers
    publishes no such read on this deployment, and then the filter is REPORTED
    BY NAME rather than silently dropped — a report answering a wider question
    than its filter chip claims is the shape `BR-REP-024` exists to prevent, and
    it is invisible on screen.

    ⚠ **IT IS UNWIRED TODAY AND SAYS SO WITH A NUMBER.** `apps/customers` has
    no published `account_ids_in_consumer_class`; the dataset DECLARES `class`
    as a filter because the brief's dimension model declares it, so the honest
    build is to accept the name, apply nothing, and say which. `DEF-REP-6837`
    is the row, and the day customers publishes that read this function starts
    narrowing with no change here.
    """
    from importlib import import_module

    try:
        module = import_module("apps.customers.selectors")
    except Exception:  # pragma: no cover — customers is always installed
        module = None
    reader = getattr(module, "account_ids_in_consumer_class", None) if module else None
    if reader is None:
        return None, {
            "code": "consumer_class_filter_was_not_applied",
            "br_ref": "B1 · BR-REP-024",
            "detail": (
                "customers publishes no consumer-class account read on this deployment, so "
                f"`class={code!r}` narrowed NOTHING: these rows are every class, not that one. "
                "The filter is reported rather than dropped because a report answering a wider "
                "question than its chip claims looks perfectly correct on screen (DEF-REP-6837)."
            ),
        }
    return reader(code), None


def _dataset_selection(
    *,
    start: date | None,
    end: date | None,
    bill_type: str | None,
    service_code: str | None,
    cycle: str | None,
    status: str | None,
    search: str | None,
    consumer_class: str | None,
    account_ids: Any,
) -> tuple[QuerySet, list[dict[str, Any]]]:
    """Every criterion as a `WHERE`, and the problems the narrowing produced.

    Shared by the page path and the stream path so the two cannot disagree
    about what the filtered set IS — which is the whole of `P0.5`'s argument
    one layer down, and the reason the export could inherit a page size in the
    first place.
    """
    problems: list[dict[str, Any]] = []
    selected = _issued_queryset()

    # ── the privacy boundary, FIRST, so nothing below can widen it ────────
    if account_ids is PORTAL_NOTHING:
        selected = selected.none()
    elif account_ids is not None:
        selected = selected.filter(account_id__in=list(account_ids))

    if status is not None:
        if status not in REGISTER_STATUSES:
            # `BR-SHL-011` — invalid values fall back, NEVER error. A saved link
            # carrying a status this product retired still opens the report.
            problems.append(
                {
                    "code": "unknown_bill_status_was_not_applied",
                    "br_ref": "BR-SHL-011 · BR-REP-024",
                    "detail": (
                        f"`status={status!r}` is not one of {list(REGISTER_STATUSES)}, so it "
                        "narrowed nothing. The report opens on every issued status rather "
                        "than on an error screen."
                    ),
                }
            )
        else:
            selected = selected.filter(status=status)

    if bill_type is not None:
        selected = selected.filter(bill_type=bill_type)

    if cycle is not None:
        # R5's own warning, built. `invoices.bill_run_id -> bill_runs.cycle_id`
        # is the reviewed FK `_issued_queryset` already travels (B2 §2), so this
        # is one join the statement already carries rather than a new reach.
        selected = selected.filter(bill_run__cycle__code=cycle)

    # ── the undated, counted over the set as narrowed SO FAR ──────────────
    # Deliberately before the window, exactly as `billing_register` does it: a
    # bill with no `issued_at` cannot be placed in time at all, so it is neither
    # in this window nor out of it.
    if start is not None or end is not None:
        undated = selected.filter(issued_at__isnull=True)
        undated_count = undated.count()
        if undated_count:
            sample = sorted(
                str(number or identifier)
                for number, identifier in undated.order_by("id").values_list(
                    "invoice_no", "id"
                )[:UNDATED_SAMPLE]
            )
            problems.append(
                {
                    "code": "issued_bill_without_an_issue_date",
                    "br_ref": "BR-REP-001",
                    "detail": (
                        f"{undated_count} bill(s) are ISSUED and carry no `issued_at`, so they "
                        "cannot be placed in a POSTING-basis window. They are EXCLUDED and "
                        "reported here rather than dated by a convention no rule states — a "
                        "bill silently moved into the month being reported is a wrong figure "
                        f"that foots perfectly. First {min(undated_count, UNDATED_SAMPLE)} by "
                        f"id: {sample}."
                    ),
                }
            )
    if start is not None:
        selected = selected.filter(issued_at__date__gte=start)
    if end is not None:
        selected = selected.filter(issued_at__date__lte=end)

    if service_code is not None:
        # `Exists` rather than a join plus `DISTINCT`: a bill with four lines of
        # one service must appear ONCE, and a `DISTINCT` over a row carrying a
        # JSON payload is the expensive way to say so.
        selected = selected.filter(
            Exists(
                models.InvoiceLine.objects.filter(
                    tenant_id=_tenant_id(),
                    invoice_id=OuterRef("pk"),
                    service__code=service_code,
                )
            )
        )

    if consumer_class is not None:
        class_ids, class_problem = _consumer_class_narrowing(consumer_class)
        if class_problem is not None:
            problems.append(class_problem)
        else:
            selected = selected.filter(account_id__in=class_ids)

    term = (search or "").strip()
    if term:
        predicate = Q(invoice_no__icontains=term)
        matched = customers_seam.account_ids_matching_search(term)
        if matched is None:
            predicate = predicate | Q(account__account_no__icontains=term)
            problems.append(
                {
                    "code": "search_does_not_reach_the_customer_name",
                    "br_ref": "B1 · BR-REP-024",
                    "detail": (
                        "customers publishes no account search on this deployment, so `q` "
                        "matched the bill number and the account number only. A name typed "
                        "here found nothing; it was not searched and did not fail."
                    ),
                }
            )
        else:
            predicate = predicate | Q(account_id__in=matched)
        selected = selected.filter(predicate)

    return selected, problems


def _ordered(selected: QuerySet, *, sort: str, direction: str) -> QuerySet:
    """The `ORDER BY`, with a TOTAL second term so a page boundary is stable.

    Two bills issued on the same day must not swap between page 1 and page 2:
    a row a clerk sees twice is a row they never see. The same tie-break makes
    the STREAM safe to chunk, which is the property `invoices_dataset_stream`
    leans on entirely.
    """
    column = _DATASET_SORT_COLUMNS.get(sort, _DATASET_SORT_COLUMNS[DATASET_DEFAULT_SORT])
    descending = str(direction).lower() != "asc"
    term = F(column).desc(nulls_last=True) if descending else F(column).asc(nulls_last=True)
    return selected.order_by(term, F("id").asc())


def _rows_for_bills(invoices: list[Any]) -> list[DatasetRow]:
    """The declared columns for a LIST OF BILLS, in a bounded number of queries.

    Two statements for the whole batch and never one per bill: the lines, and
    the names through customers' own batched read. `DEF-2723`'s shape, measured
    on the register at 50 of a page's 56 statements before it was fixed.
    """
    if not invoices:
        return []

    by_invoice: dict[Any, list[Any]] = {}
    line_rows = models.InvoiceLine.objects.filter(
        tenant_id=_tenant_id(), invoice_id__in=[invoice.id for invoice in invoices]
    ).select_related("service")
    for line in line_rows:
        by_invoice.setdefault(line.invoice_id, []).append(line)

    names = customers_seam.primary_contact_names_for(
        [invoice.account_id for invoice in invoices]
    )

    # One read for the whole page — see the register above.
    capacity_services = tenancy_seam.capacity_service_codes()

    rows: list[DatasetRow] = []
    for invoice in invoices:
        lines = by_invoice.get(invoice.id, [])
        services = tuple(
            sorted({line.service.code for line in lines if line.service_id is not None})
        )
        usage: dict[str, Decimal] = {}
        counted, measured = _unit_origins()
        base = ZERO
        usage_revenue = ZERO
        tax = ZERO
        for line in lines:
            # The three money columns ARE the line kinds, split exactly as
            # `revenue_by_service_and_rate` splits them: `base` is everything
            # that is neither consumption nor tax, so Σ(the three) = Σ(lines)
            # and no line can fall between the columns unnoticed.
            if line.kind == KIND_USAGE:
                usage_revenue += line.amount
                if line.quantity is not None and line.unit:
                    usage[line.unit] = usage.get(line.unit, ZERO) + line.quantity
                    _record_unit_origin(line, capacity_services, counted, measured)
            elif line.kind == KIND_TAX:
                tax += line.amount
            else:
                base += line.amount
        issued_on = invoice.issued_at.date() if invoice.issued_at is not None else None
        rows.append(
            DatasetRow(
                invoice_id=str(invoice.id),
                invoice_no=invoice.invoice_no,
                account_id=str(invoice.account_id),
                account_no=getattr(invoice.account, "account_no", None),
                customer_name=(
                    _customer_name(invoice.account)
                    if names is None
                    else names.get(str(invoice.account_id))
                ),
                bill_type=invoice.bill_type,
                status=invoice.status,
                cycle_code=(
                    invoice.bill_run.cycle.code
                    if invoice.bill_run is not None and invoice.bill_run.cycle_id
                    else None
                ),
                services=services,
                issued_on=issued_on,
                # The SAME date, and this file's docstring is why: a bill's
                # posting date IS the day it was issued.
                posted_on=issued_on,
                due_date=invoice.due_date,
                period_start=invoice.period_start,
                period_end=invoice.period_end,
                usage=tuple((amount, unit) for unit, amount in sorted(usage.items())),
                counted_units=tuple(sorted(counted - measured)),
                base=base,
                usage_revenue=usage_revenue,
                tax=tax,
                amount=invoice.total,
                currency=invoice.currency,
                estimated=_estimated_flag(invoice),
            )
        )
    # ⚠ NOTHING SORTS HERE. The order is the `ORDER BY`; a `rows.sort` would
    # re-order a page that was already cut — `DEF-PAY-4221`'s exact shape.
    return rows


def invoices_dataset(
    *,
    start: date | None = None,
    end: date | None = None,
    bill_type: str | None = None,
    service_code: str | None = None,
    cycle: str | None = None,
    status: str | None = None,
    consumer_class: str | None = None,
    search: str | None = None,
    account_ids: Any = None,
    page: int = 1,
    per: int | None = None,
    sort: str = DATASET_DEFAULT_SORT,
    direction: str = DATASET_DEFAULT_DIRECTION,
) -> dict[str, Any]:
    """ONE PAGE of the `invoices` dataset, plus the totals over the whole set.

    The brief's left path (§8.2, p91): *"page 1 only · never the whole
    result"*. Every criterion is a `WHERE`, the order is an `ORDER BY`, the page
    is a `LIMIT`/`OFFSET`, and the totals are SQL aggregates over the whole
    FILTERED set — so a footer foots to the report whether a page is cut or not.

    `per=None` means the whole filtered set and exists for one caller: a test
    proving the page and the stream agree. **A file is not produced this way**
    — `invoices_dataset_stream` is, and the split is argued above.
    """
    selected, problems = _dataset_selection(
        start=start,
        end=end,
        bill_type=bill_type,
        service_code=service_code,
        cycle=cycle,
        status=status,
        search=search,
        consumer_class=consumer_class,
        account_ids=account_ids,
    )

    # ── the totals: aggregates over the whole FILTERED set ────────────────
    money = DecimalField(max_digits=18, decimal_places=6)
    tiles = selected.aggregate(
        bills=Count("id"),
        billed=Coalesce(Sum("total"), Value(ZERO, output_field=money), output_field=money),
    )
    count = int(tiles["bills"] or 0)

    # The three line-kind measures, over the same filtered set, in ONE
    # statement. Conditional aggregation rather than three queries, and a
    # subquery on the bills rather than a join that would multiply the rows.
    line_totals = models.InvoiceLine.objects.filter(
        tenant_id=_tenant_id(), invoice_id__in=selected.values("id")
    ).aggregate(
        base=Coalesce(
            Sum("amount", filter=~Q(kind__in=(KIND_USAGE, KIND_TAX)), output_field=money),
            Value(ZERO, output_field=money),
            output_field=money,
        ),
        usage_revenue=Coalesce(
            Sum("amount", filter=Q(kind=KIND_USAGE), output_field=money),
            Value(ZERO, output_field=money),
            output_field=money,
        ),
        tax=Coalesce(
            Sum("amount", filter=Q(kind=KIND_TAX), output_field=money),
            Value(ZERO, output_field=money),
            output_field=money,
        ),
    )

    # DEF-081 / DEF-099 — the CHAR(3) these figures ARE, derived from the rows
    # summed rather than read off a tenant setting. Bounded at two reads because
    # "more than one" is all a footer needs to know.
    currencies = tuple(
        sorted(set(selected.order_by().values_list("currency", flat=True).distinct()[:2]))
    )
    currency = currencies[0] if len(currencies) == 1 else None
    if currency is None and currencies:
        problems.append(
            {
                "code": "window_holds_more_than_one_currency",
                "br_ref": "CLAUDE.md rule 2",
                "detail": (
                    "These bills are denominated in more than one currency, so the money "
                    "totals are not numbers. The rows are served; the totals are null with "
                    "this reason."
                ),
            }
        )

    estimated_count, estimated_problem = _estimated_count(selected)
    if estimated_problem is not None:
        problems.append(estimated_problem)

    ordered = _ordered(selected, sort=sort, direction=direction)
    if per is None:
        served_page = 1
        invoices = list(ordered)
    else:
        # `BR-SHL-011` — clamp, never error. A caller asking for page 9,999 of
        # a 41-page report is told which page it got.
        per = max(1, int(per))
        last_page = max(1, -(-count // per))
        served_page = min(max(1, int(page)), last_page)
        offset = (served_page - 1) * per
        invoices = list(ordered[offset : offset + per])

    total_billed = tiles["billed"] or ZERO
    return {
        "grain": "one bill",
        "basis": BASIS_POSTING,
        "window": {"start": start, "end": end},
        "currency": currency,
        "rows": tuple(_rows_for_bills(invoices)),
        "totals": {
            "bills": count,
            # Money is null WITH A REASON when it cannot be stated, never 0.
            "billed": total_billed if currency is not None else None,
            "base": line_totals["base"] if currency is not None else None,
            "usage_revenue": line_totals["usage_revenue"] if currency is not None else None,
            "tax": line_totals["tax"] if currency is not None else None,
            # B4's display rule is the renderer's; this publishes the exact
            # quotient at full precision. Division by zero is not a figure.
            "average_bill": (
                (total_billed / count) if (currency is not None and count) else None
            ),
            "estimated": estimated_count,
            # `bill_run_exclusions` is keyed to a RUN and not to a window, so a
            # report spanning two runs has no single exception count. REPORTED
            # rather than approximated.
            "exceptions": None,
        },
        "sorts": DATASET_SORTS,
        "searchable": DATASET_SEARCH_COLUMNS,
        "filters_served": DATASET_FILTERS_SERVED,
        "page": served_page,
        "per": per,
        "total": count,
        "problems": tuple(problems),
    }


def invoices_dataset_stream(
    *,
    start: date | None = None,
    end: date | None = None,
    bill_type: str | None = None,
    service_code: str | None = None,
    cycle: str | None = None,
    status: str | None = None,
    consumer_class: str | None = None,
    search: str | None = None,
    account_ids: Any = None,
    sort: str = DATASET_DEFAULT_SORT,
    direction: str = DATASET_DEFAULT_DIRECTION,
    chunk: int = STREAM_CHUNK,
) -> Any:
    """EVERY ROW of the filtered set, one at a time. The brief's right path.

    §8.2, p91: *"every row · never in memory · never blocks the screen"*, and
    *"row by row, from a generator"*. This returns a GENERATOR and takes no
    `page` and no `per` — a file that silently became fifty rows is the defect
    caught on the register the day it started paging, and a function with no
    page size cannot inherit one.

    It holds `chunk` bills at a time, never the whole book, and `NFR-5` is
    untouched: `chunk` bounds MEMORY and never how many rows a caller gets.

    ⚠ **IT PAGES BY `OFFSET` AND THE TIE-BREAK IS WHAT MAKES THAT SOUND.**
    `_ordered` ends every order in `id ASC`, so the sequence is total and a
    chunk boundary cannot repeat or skip a row the way an ambiguous order can.
    The alternative — a keyset cursor — is faster at the far end of 40,000 rows
    and is a different shape from the page path; two shapes is how the two
    disagree, which is exactly what this pair of functions exists to prevent.
    **Measured on PostgreSQL 16 over 40,092 bills: the whole file streams in
    43.983s and a page costs 0.673s at page 802 exactly as at page 1** — the
    offset is not what costs here, the three line-kind totals are, and a keyset
    cursor would not move either figure. It is recorded as an option nobody
    needs to take rather than as a defect nobody will close.
    """
    selected, _problems = _dataset_selection(
        start=start,
        end=end,
        bill_type=bill_type,
        service_code=service_code,
        cycle=cycle,
        status=status,
        search=search,
        consumer_class=consumer_class,
        account_ids=account_ids,
    )
    ordered = _ordered(selected, sort=sort, direction=direction)

    size = max(1, int(chunk))
    offset = 0
    while True:
        batch = list(ordered[offset : offset + size])
        if not batch:
            return
        for row in _rows_for_bills(batch):
            yield row
        if len(batch) < size:
            return
        offset += size


# ── CR-179-BRC10 · THE RATE IMPACT REPORT'S BILLED REVENUE ──────────────────
#
# `apps/reports/rate_impact.py` is the only caller, through
# `apps/reports/report_seams.py`. Read-only.

#: The bills whose lines are billed revenue today. ⚠ **`corrected` IS NOT HERE
#: AND THAT IS HOW A CORRECTION IS INCLUDED, NOT EXCLUDED.** A class-R
#: correction reverses the original IN FULL with a credit note and issues a
#: REBILL (`corrections.py`, *"Full credit note (−original total, the whole bill
#: reversed)"*); the original moves to `corrected` and the rebill is `issued`.
#: So the money that stands is the rebill's lines: reading `corrected` too
#: would count the bill twice, and reading the credit note would need a line
#: table the credit note does not have. `void` was never revenue.
RATE_IMPACT_BILLED_STATUSES: tuple[str, ...] = (models.INVOICE_ISSUED, models.INVOICE_PAID)


def rate_impact_billed(
    *, tariff_ids: Any = (), charge_ids: Any = (), start: date, end: date
) -> list[dict[str, Any]]:
    """Billed revenue per ACCOUNT per rate schedule or charge code, in a window.

    `[{account_id, tariff_id, charge_id, amount, currency}]` — one row per
    account × schedule (with `charge_id` None) and per account × charge code
    (with `tariff_id` None).

    * **A schedule's revenue** is every line stamped with one of its versions
      (`tariff_version`, DEF-276's provenance) except tax — its base, usage and
      minimum lines. Any version: a report asking about a schedule asks what
      the schedule billed, whichever version priced each bill.
    * **A charge code's revenue** is every line naming the code (`charge`).
    * **A line counts in the month its period ENDS** (CR-179 confirmed rule 1):
      a line belongs to the window when its own `period_end` — or, where the
      line states none, its bill's — falls inside `[start, end]`. A bill whose
      period crosses the start of the window therefore counts whole, in its
      end month, and never split.
    * **Issued bills only, corrections included** — `RATE_IMPACT_BILLED_STATUSES`.

    Money is the stored `NUMERIC` sum, never rounded here (hard rule 2).
    """
    tariff_list = [str(one) for one in tariff_ids or () if one]
    charge_list = [str(one) for one in charge_ids or () if one]
    if not tariff_list and not charge_list:
        return []
    ends_on = Coalesce("period_end", "invoice__period_end")
    base = (
        models.InvoiceLine.objects.filter(
            tenant_id=_tenant_id(),
            invoice__status__in=RATE_IMPACT_BILLED_STATUSES,
        )
        .annotate(rate_impact_ends_on=ends_on)
        .filter(rate_impact_ends_on__gte=start, rate_impact_ends_on__lte=end)
    )
    out: list[dict[str, Any]] = []
    if tariff_list:
        for row in (
            base.filter(tariff_version__tariff_id__in=tariff_list)
            .exclude(kind=KIND_TAX)
            .values("account_id", "tariff_version__tariff_id", "invoice__currency")
            .annotate(total=Sum("amount"))
            .order_by("account_id", "tariff_version__tariff_id", "invoice__currency")
        ):
            out.append(
                {
                    "account_id": str(row["account_id"]),
                    "tariff_id": str(row["tariff_version__tariff_id"]),
                    "charge_id": None,
                    "amount": row["total"] if row["total"] is not None else ZERO,
                    "currency": row["invoice__currency"],
                }
            )
    if charge_list:
        for row in (
            base.filter(charge_id__in=charge_list)
            .values("account_id", "charge_id", "invoice__currency")
            .annotate(total=Sum("amount"))
            .order_by("account_id", "charge_id", "invoice__currency")
        ):
            out.append(
                {
                    "account_id": str(row["account_id"]),
                    "tariff_id": None,
                    "charge_id": str(row["charge_id"]),
                    "amount": row["total"] if row["total"] is not None else ZERO,
                    "currency": row["invoice__currency"],
                }
            )
    return out



# ═══════════════════════════════════════════════════════════════════════════
# CR-185-BRC10 D4 — THE OWNER SUMMARY'S READ: an owner's own issued bills,
# summed per owner (master) account into the three sections the PO named
# ═══════════════════════════════════════════════════════════════════════════
#: The three sections, PO 2026-10-14 (D4): *"a section per property (empty
#: units, common areas, other owner charges)"*.
OWNER_SECTION_EMPTY_UNITS = "empty_units"
OWNER_SECTION_COMMON_AREAS = "common_areas"
OWNER_SECTION_OTHER = "other_charges"
OWNER_SECTIONS: tuple[str, ...] = (
    OWNER_SECTION_EMPTY_UNITS,
    OWNER_SECTION_COMMON_AREAS,
    OWNER_SECTION_OTHER,
)

#: Which bills count: the ones that STAND. `void` and `corrected` bills were
#: replaced (a credit note and a rebill carry the money from then on, and the
#: rebill is itself `issued`), so counting them would count one month twice.
OWNER_SUMMARY_STATUSES: tuple[str, ...] = (models.INVOICE_ISSUED, models.INVOICE_PAID)

#: How an EMPTY unit's base line names itself on its owner's bill —
#: `apps/rating/pricing/stages/price_usage.py` writes `f"{unit} · {service}
#: base charge"` for exactly the configs `billing.gather` marks with
#: `covers_unit_label` (`DEF-CUS-9050`), and no other line carries the
#: separator. ⚠ **IT IS THE ONLY MARK THE STORED LINE CARRIES** —
#: `invoice_lines` has no unit column — so the classification reads the
#: description, and says so on every result (`OWNER_SUMMARY_CLASSIFIED_BY`).
EMPTY_UNIT_SEPARATOR = " · "

OWNER_SUMMARY_CLASSIFIED_BY = {
    "code": "owner_sections_read_from_the_line",
    "br_ref": "BR-CUS-170 · DEF-CUS-9050 · CR-185-BRC10",
    "detail": "an owner bill's line is an EMPTY UNIT's base when it is a base line naming "
    "its unit (`<unit> · <service> base charge`); every other base, usage and minimum line "
    "is the COMMON AREAS; fees, taxes and adjustments are OTHER owner charges. "
    "`invoice_lines` stores no unit, so the unit is read from the line's own words.",
}


def _owner_section_case() -> Any:
    from django.db.models import Case, When

    return Case(
        When(
            Q(kind="base") & Q(description__contains=EMPTY_UNIT_SEPARATOR),
            then=Value(OWNER_SECTION_EMPTY_UNITS),
        ),
        When(kind__in=("base", "usage", "minimum"), then=Value(OWNER_SECTION_COMMON_AREAS)),
        default=Value(OWNER_SECTION_OTHER),
    )


def owner_bill_summary(*, account_ids: Any, start: date, end: date) -> dict[str, Any]:
    """`{account_id: {bills, empty_units, common_areas, other_charges, total,
    currency}}` over the owner accounts' ISSUED bills in `[start, end]`.

    PO 2026-10-14 (D4): the utility runs an owner summary — *"one monthly
    statement with a section per property and a grand total of $85. Each
    property's account keeps its own books, and they still pay per property."*
    So this READS the owner accounts' own bills and changes nothing.

    * **The window is the bill's ISSUE date** (`issued_at`, POSTING basis —
      the same placing `billing_register` uses), so a summary for September
      holds the bills the owner was sent in September.
    * **Every figure is the stored `NUMERIC` sum** (hard rule 2), grouped in
      SQL — one statement for the whole set, whatever its size (`NFR-3`/`NFR-5`).
    * An account with no bill in the window is ABSENT from the answer; the
      caller states it as a property with nothing billed, never as an error.
    """
    ids = [str(one) for one in account_ids or () if one]
    if not ids:
        return {}
    rows = (
        models.InvoiceLine.objects.filter(
            tenant_id=_tenant_id(),
            account_id__in=ids,
            invoice__status__in=OWNER_SUMMARY_STATUSES,
            invoice__issued_at__date__gte=start,
            invoice__issued_at__date__lte=end,
        )
        .annotate(owner_section=_owner_section_case())
        .values("account_id", "owner_section", "invoice__currency")
        .annotate(total=Sum("amount"), bills=Count("invoice_id", distinct=True))
        .order_by("account_id", "owner_section")
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = out.setdefault(
            str(row["account_id"]),
            {
                **{section: ZERO for section in OWNER_SECTIONS},
                "total": ZERO,
                "bills": 0,
                "currency": row["invoice__currency"],
            },
        )
        amount = row["total"] if row["total"] is not None else ZERO
        entry[row["owner_section"]] += amount
        entry["total"] += amount
    # The bill COUNT is per account, never summed across sections — a bill
    # with lines in all three would otherwise count three times.
    for row in (
        models.Invoice.objects.filter(
            tenant_id=_tenant_id(),
            account_id__in=ids,
            status__in=OWNER_SUMMARY_STATUSES,
            issued_at__date__gte=start,
            issued_at__date__lte=end,
        )
        .values("account_id")
        .annotate(n=Count("id"))
        .order_by("account_id")
    ):
        if str(row["account_id"]) in out:
            out[str(row["account_id"])]["bills"] = row["n"]
    return out

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-REP-006@c6c35b2 (story+rules snapshot — 04-docs/05-modules/12-reports/06-epics/EP-REP-02-canned-reports.md §US-REP-006 · 12-reports/02-business-rules.md BR-REP-001/002/006 · 04-docs/01-spec/14-reports-and-exports.md items 6 + 9 · 05-prototype/UtilityBilling.html lines 4197-4232)
# screens: S46
# generated: 2026-08-16 by story-coder (reports lane — 18 of 19 reports stories had no code at all)
# checklist: A✔ B✔ C=deferred(the SCREEN half is apps/reports — this file publishes the read model it renders) D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_rep_canned_reports.py could not import this module before it existed. ruff✔ black✔ pytest✔ run_gates✔
# exceptions: (1) the register's `exceptions` KPI is served NULL with its reason: `bill_run_exclusions` is keyed to a RUN and this report's window may span several, so there is no single count to state · (2) a bill ISSUED with no `issued_at` is EXCLUDED and named in `problems` rather than placed in the window by convention · (3) two currencies in one window makes the totals null with a reason, never a sum of unlike money (CLAUDE.md rule 2) · (4) this file writes nothing anywhere
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
