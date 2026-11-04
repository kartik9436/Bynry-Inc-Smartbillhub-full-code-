# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-025 (EP-CWP-06) — the home page's four tiles, the three
#           recent bills and the twelve-month chart. Screen: CWP-022
# Rules:    CLAUDE.md hard rule 3 (consumption ALWAYS carries its unit — never
#           a bare number) · hard rule 2 (4 dp stored, 2 dp displayed) ·
#           BR-CWP-041 (nothing above the issued bill reaches a customer) ·
#           BR-CWP-093 (nothing empty ever appears) · BR-CWP-010 (both halves
#           in the query — the caller has already intersected the account set)
# Tests:    06-backend/tests/test_us_cwp_025_home.py
# Impacts:  apps/portal/selectors.py `home`
# ───────────────────────────────────────────────────────
"""What the portal reads from `billing`. **NOTHING HERE WRITES** (G81).

⚠ **A DRAFT BILL IS NOT A BILL** (`BR-CWP-041`). Every read below filters on
`status = issued`: a draft is the utility's working copy, and a customer who
saw one would ring up about a figure that is going to change. The filter is in
the QUERY and not in the screen, for the same reason `BR-CWP-010` puts the
account set there.

⚠ **SUPERSEDED (PO ruling 2026-09-04 → `metering.monthly_usage_reads.usage_payload`).
KEPT BECAUSE THE MISTAKE IS THE LESSON, NOT BECAUSE THE CODE SURVIVED.**

The paragraph below was written on a premise that was **false when it was
written**, and it shipped: `metering` HAS published a per-account consumption
read since `CR-030` W3 — `monthly_usage_reads.usage_payload(account_id,
months=12|24)`, served at `GET /accounts/{id}/usage`, drawn by the staff
Account details Usage tab and by its Overview panel. An absence in one folder
was read as an absence in the product.

**What the mistake cost, in one line:** the home tile showed what the customer
was **BILLED** for, so usage since the last bill never appeared at all — and an
**unread month was indistinguishable from a month of no use**, because a bill
line simply has no row for a month nobody read, which is the exact claim
`BR-MET-106` exists to refuse (*"zero usage and no read are different claims
about a customer"*).

`usage_series` and `usage_latest` are **GONE from this file** — `selectors.home`
reads `metering_seam.usage_for_account` now, and a second read of the same
facts is a second ANSWER, which is a clerk and a customer arguing on the phone.
The paragraph stays; the code does not.

    [SUPERSEDED text, kept verbatim]

    ⚠ **AND THE USAGE CHART IS READ FROM BILLS RATHER THAN FROM METERS, WHICH
    IS A DECISION AND NOT A SHORTCUT.** `metering` publishes no per-account
    consumption read, and composing one here — account → unit → service points
    → meters → reads → a month's difference — would put billing arithmetic in
    the portal, which is the one place it must never be. **A bill line already
    holds the answer**: `kind='usage'` carries `quantity`, `unit` and the period
    it covers, signed off at issue. So the chart shows *what the customer was
    billed for*, which is also the number they will ring up about — and it
    carries its unit by construction, because the column does (hard rule 3).

    **What that costs, stated so nobody is surprised:** usage since the last
    bill does not appear, because it has not been billed yet. The tile is *this
    month* in the sense of *the last period billed*, and the screen words it
    that way.

⚠ **WHAT THIS FILE STILL OWNS, AND IT IS THE RIGHT HALF.** A BILL is billing's,
so `recent_bills`, `last_bill`, `bills_for` and `bill_number_covering` stay
here. The rule that came out of this is narrow and worth stating: **read the
figure from the module that MEASURES it and the money from the module that
CHARGES it.** `04-docs/05-modules/15-portal/12-reuse-map.md` is the map.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Sum

from apps.billing import models as billing_models
from apps.metering import quantity_display
from apps.rating.pricing import wording
from core import money
from core.tenancy import current_tenant_id

from core import tenancy as core_tenancy


def _tenant() -> Any:
    """The tenant this request is scoped to, for the QUERY (`BR-CWP-010`).

    ⚠ **RLS `FORCE` ALREADY ENFORCES THIS AND THAT IS NOT ENOUGH** (`G96`,
    `DEF-CWP-3775`). `BR-CWP-010` says *in the query*, not *enforced
    somewhere*, and the reason is hard-won law 14: `config/settings/test.py`
    hardcodes in-memory SQLite, **which has no row-level security at all**. So
    a portal read that omits the tenant passes every test in this repository,
    on every machine, forever — and the day one `.using()`, one raw query or
    one policy nobody wrote removes the database's guarantee, nothing above it
    was ever asked to agree. Naming it here costs one keyword and makes the two
    halves independent.
    """
    return core_tenancy.current_tenant_id()


#: `BR-CWP-041` — the only status a customer may be shown.
ISSUED = billing_models.INVOICE_ISSUED
#: `billing`'s own constant, re-exported so no portal file spells `"void"`
#: as a literal. A literal is a second spelling of a status the owning
#: module names, and the day billing renames it a literal goes quietly
#: wrong instead of failing to import.
VOID = billing_models.INVOICE_VOID

#: How many bills `CWP-022` is served. The number is the SCREEN's rather than
#: this seam's; it is named here so the test and the read agree on one constant.
#:
#: ⚠ **THREE UNTIL 2026-09-08, WHEN THE PRODUCT OWNER ASKED FOR SIX** —
#: verbatim: *"please give me drop down to select last 6 months - on this -
#: August bill · BL-2608-000077"*. The home page's bill panel now carries a
#: chooser over the months it holds, and a chooser of three cannot answer *how
#: does this month compare with the spring* — which is the commonest reason a
#: customer leaves the home page at all.
#:
#: ⚠ **IT IS A COUNT OF BILLS, NOT A WINDOW OF MONTHS.** A quarterly account
#: gets its last six bills, which is eighteen months; the chooser names each
#: one by its own month, so nothing on screen claims a period it does not hold.
RECENT_BILL_COUNT = 6
#: ⚠ **`CHART_MONTHS` WENT WITH `usage_series` (2026-09-04).** The window a
#: customer chooses is now `monthly_usage_reads.ALLOWED_WINDOWS` — 12 or 24,
#: r10's own filter vocabulary — and a second constant here would be a second
#: opinion about how long a year is.


def _money(value: Any) -> str:
    """Four decimals as a string. Never a float, never cents (hard rule 2)."""
    return str(Decimal(value or 0).quantize(Decimal("0.0001")))


def _bill_view(row: Any) -> dict[str, Any]:
    """One bill as a customer reads it. ⚠ **NO `bill_run_id`, NO `id`** — B14
    rule 31: the visible reference is `invoice_no`, the number on the paper."""
    return {
        "number": row.invoice_no,
        "issued_on": row.issued_at.date().isoformat() if row.issued_at else None,
        "due_on": row.due_date.isoformat() if row.due_date else None,
        "total": _money(row.total),
        "currency": row.currency,
        "period_start": row.period_start.isoformat() if row.period_start else None,
        "period_end": row.period_end.isoformat() if row.period_end else None,
    }


#: `invoice_lines.kind` for a line priced off a METER READING, as
#: `billing_models.InvoiceLine.kind`'s own comment names it — *usage | base |
#: fee | tax | adjustment | minimum*. Billing spells it in a private tuple
#: (`selectors._SERVICE_BEARING_KINDS`) and publishes no constant, so it is
#: named ONCE here rather than typed at each call site.
USAGE_LINE_KIND = "usage"

#: `DEF-CWP-3967` — the two shapes a tariff rate takes on a bill. A rate is
#: money PER A UNIT (`$5.2000 / kgal`) or it is a PROPORTION of something else
#: (`6.25%`), and a bare `5.2000` beside a water line tells a customer neither.
RATE_PER_UNIT = "per_unit"
RATE_PERCENT = "percent"


def _usage_by_invoice(invoice_ids: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """What each bill CHARGED FOR, per unit — one query for the whole list.

    ⚠ **THIS IS THE BILL'S OWN LINES, AND THAT IS THE RIGHT SOURCE HERE EVEN
    THOUGH IT IS THE WRONG ONE ON THE USAGE TILE.** `selectors.home`'s docstring
    records the 2026-09-04 correction: the *this month* tile used to sum
    `invoice_lines` and so showed what a customer was BILLED rather than what
    was READ, which made an unread month indistinguishable from a month of no
    use. A column headed *Usage* **on a bill row** is asking the opposite
    question — *what did this bill charge me for* — and the only truthful answer
    to that is the paper's own lines.

    ⚠ **GROUPED BY UNIT AND NEVER TOTALLED ACROSS UNITS** (hard rule 3). A bill
    carrying 4,820 gal of water and 31 therms of gas has two figures and no
    third one; adding them would invent a number in a unit that does not exist.

    ⚠ **A LINE WITH A QUANTITY AND NO UNIT IS DROPPED, NOT PRINTED** — the same
    refusal `_quantity_of` makes one screen along, and for the same reason: a
    bare `4,820` in a column headed *Usage* means whatever the reader assumes.
    """
    if not invoice_ids:
        return {}
    totals: dict[str, dict[str, Decimal]] = {}
    rows = (
        billing_models.InvoiceLine.objects.filter(
            tenant_id=_tenant(), invoice_id__in=invoice_ids, kind=USAGE_LINE_KIND
        )
        .values("invoice_id", "unit")
        .annotate(quantity=Sum("quantity"))
    )
    for row in rows:
        unit = (row.get("unit") or "").strip()
        quantity = row.get("quantity")
        if not unit or quantity is None:
            continue
        totals.setdefault(str(row["invoice_id"]), {}).setdefault(unit, Decimal("0"))
        totals[str(row["invoice_id"])][unit] += Decimal(quantity)
    return {
        invoice_id: [
            #: `BR-MET-144`'s own helper — two decimals, trailing zeros trimmed
            #: — because the stored figure is `NUMERIC(18,6)` and a screen
            #: printing it reads `4820.000000 gal` (`DEF-CWP-3770`).
            {"quantity_display": quantity_display.quantity_text(amount), "unit": unit}
            for unit, amount in sorted(units.items())
        ]
        for invoice_id, units in totals.items()
    }


#: The line kinds a CAPACITY service's standing charge is written as. `BR-RAT-090`
#: prices an unmetered service as a COUNT of its assets on the unit at the size
#: class's rate, and the bill writes that as a base/charge line rather than a
#: usage one.
CAPACITY_LINE_KINDS = ("base", "charge", "capacity")


def month_end(month: str | None) -> date | None:
    """The last day of a `YYYY-MM` month — `CPB-08`'s join key.

    ⚠ **THE LAST DAY AND NOT THE FIRST, AND IT IS NOT A DETAIL.** A usage month
    is complete on its last day. A bill issued mid-month covers the START of
    August and not its end, so joining on 1 August would attach a whole month's
    usage to a bill that stopped before most of it happened — and the customer
    reading *"800 kWh at $0.1150 = $92.00"* would be looking at a figure for a
    fortnight.

    `None` for anything malformed: the month key comes off a payload, and a read
    model that raised on one would take a whole screen down for one cell.
    """
    if not month:
        return None
    try:
        year, mon = (int(part) for part in month.split("-")[:2])
        first_next = date(year + (mon == 12), 1 if mon == 12 else mon + 1, 1)
    except (ValueError, TypeError):
        return None
    return first_next - timedelta(days=1)


def usage_cost_view(
    lines: list[dict[str, Any]], *, month: str, bill_number: str | None
) -> dict[str, Any] | None:
    """One usage month's cost, **entirely off the bill's own lines** — `CPB-08`.

    The specification's sentence is *"The Usage screen reads '800 kWh at $0.1150
    = $92.00' for August, and the figure is the bill's own line, not a
    re-calculation."*

    ⚠ **IT IS `lines`, PLURAL, AND THAT IS A CORRECTION MADE AGAINST LIVE DATA
    RATHER THAN A FIXTURE.** The blueprint draws ONE line, and the first version
    of this function served one. Ana's own July electric bill has **two**:
    `500 kWh at $0.1100 = $55.00` and `300 kWh at $0.1350 = $40.50` — a tiered
    tariff, which is what most utilities actually charge. Serving only the first
    would have shown a customer `$55.00` for a month that cost `$95.50` and
    called it an explanation. **The bill's shape decides the panel's shape.**

    ⚠ **NOTHING IS MULTIPLIED AND NOTHING IS ADDED THAT THE BILL DID NOT ADD.**
    `500 × 0.1100` is `55.00` here and stops being so the moment a minimum or a
    proration is involved. The TOTAL is a sum of the lines' own stored amounts —
    the same 2 dp figures the printed column foots to (`_display`, and
    `charges_by_service` sums the ROUNDED lines by B4's 2026-08-11 reading), so
    the panel foots against the paper by construction. **This is also what keeps
    the whole specification off B4's ❄️ FROZEN ground: nothing here prices
    anything.**

    ⚠ **A LINE WITH A QUANTITY AND NO UNIT IS DROPPED, NOT PRINTED** (hard rule
    3) — and the read one level up has already refused the pair, so this is the
    second guard on the rule this wave exists to keep.

    ⚠ **THE BILL'S NUMBER TRAVELS AND ITS ID DOES NOT** (B14 rule 31).
    """
    if not bill_number:
        return None
    shown: list[dict[str, Any]] = []
    total = Decimal("0")
    unit: str | None = None
    for line in lines:
        amount = line.get("amount_display")
        if amount is None:
            continue
        quantity = line.get("quantity")
        line_unit = line.get("unit")
        #: `_quantity_of` already serves the pair or NEITHER, so one being
        #: present without the other cannot happen — this states the invariant
        #: rather than trusting it, because a later lane may rewrite that read.
        if (quantity is None) != (line_unit is None):
            continue
        if line_unit is not None:
            unit = line_unit
        shown.append(
            {
                "description": line.get("description"),
                "quantity": quantity,
                "unit": line_unit,
                #: FOUR decimals — a rate is not money (`OQ-620`(a), PO
                #: 2026-08-27). Already rendered by `_line_view`.
                "rate": line.get("rate"),
                #: `per_unit` · `percent` — so a screen can put a `$` on one and
                #: a `%` on the other (`DEF-CWP-3967`).
                "rate_basis": line.get("rate_basis"),
                "rate_percent": line.get("rate_percent"),
                "amount_display": amount,
            }
        )
        total += Decimal(str(amount))
    if not shown:
        return None
    return {
        "month": month,
        "bill_number": bill_number,
        "lines": shown,
        "total_display": _display(total),
        #: The unit the month is measured in, when every line agrees on one.
        "unit": unit,
    }


def usage_cost_for_month(
    account_ids: list[Any], *, service_code: str, month: str, today: date
) -> dict[str, Any] | None:
    """What one service's usage cost in one month, from the bill that covers it.

    ⚠ **THE SAME PERIOD MATCH `CWP-034` ALREADY MAKES FOR A READING**
    (`bill_number_covering`), one level up: `invoice_lines` carries no month, and
    the correspondence a customer makes holding the paper is *this bill covers
    that stretch of time*. Nothing new is invented to join them.

    ⚠ **THE GROUP KEY IS `service`, AND THAT IS NOT A DETAIL — IT WAS A BUG
    HERE.** `_grouped_lines` serves `service`, `service_name`, `lines` and
    `subtotal_display`; the first draft of this function read `service_code`,
    which is not a key that shape has, so the loop matched nothing and every
    account in the product answered `None`. **Every unit test passed**, because
    they exercised `usage_cost_view` against a fixture this file invented rather
    than against a bill this product produces. It was found by running the join
    over live `pine-hill` data and watching it answer nothing where a bill
    plainly existed.

    ⚠ **`None` IS ORDINARY AND COMMON.** The current month is never billed yet;
    Ana's August is exactly that case. The screen states the absence rather than
    printing `$0.00`, which is a claim that the month was free.
    """
    closes = month_end(month)
    if closes is None:
        return None
    number = bill_number_covering(account_ids, closes)
    if not number:
        return None
    detail = bill_detail_for(account_ids, number=number, today=today)
    if detail is None:
        return None
    for group in detail.get("groups") or ():
        if (group.get("service") or "") != service_code:
            continue
        usage = [
            line
            for line in group.get("lines") or ()
            if (line.get("kind") or "") == USAGE_LINE_KIND
        ]
        return usage_cost_view(usage, month=month, bill_number=number)
    return None


def per_item_monthly(line: dict[str, Any] | None) -> str | None:
    """What ONE of these costs a month, from the bill's OWN rate.

    `CR-085` `CPB-10` — the drawing's `Monthly` column, *"Fire line · 2 inch
    sprinkler supply · $12.00"*.

    ⚠ **IT IS THE `unit_price`, NOT `amount ÷ quantity`, AND THE DIFFERENCE IS
    NOT PEDANTRY.** `BR-RAT-090` bills two carts as `2 × $12.00 = $24.00`, so
    both readings give `12.00` on that line — and they stop agreeing the moment a
    proration, a partial month or a rounding step touches the amount. Dividing
    here would be this screen doing arithmetic **the bill has already done**,
    which is exactly the second-answer-to-one-question shape `CPB-08` names in
    its own words: *"the figure is the bill's own line, not a re-calculation."*

    ⚠ **A LINE WITH NO RATE HAS NO ANSWER AND `None` IS SERVED.** Nothing is
    substituted. A customer told their meter costs `$12.00` a month because a
    screen divided two numbers has been told something no clerk can reproduce.

    ⚠ **DISPLAYED AT TWO PLACES** (CLAUDE.md hard rule 2). The stored rate is
    four; `$12.0000 a month` is not a sentence.
    """
    if not line:
        return None
    #: ⚠ **`rate`, WHICH IS WHAT `_line_view` SERVES** — the raw column is
    #: `unit_price` and the projection renames it, at FOUR decimals
    #: (`OQ-620`(a)). Reading the raw name here answered `None` on every bill in
    #: the product, and the unit test passed because it fed the raw shape.
    #: Both are accepted so a caller holding either is served, and neither is
    #: guessed.
    rate = line.get("rate")
    if rate is None:
        rate = line.get("unit_price")
    if rate is None:
        return None
    return _display(rate)


def standing_charge_line(
    account_ids: list[Any], *, service_code: str, today: date
) -> dict[str, Any] | None:
    """The LATEST issued bill's standing line for one service, or `None`.

    ⚠ **THE LATEST ISSUED BILL AND NOT A RATE TABLE.** A rate schedule says what
    a plan WOULD charge; this screen answers *what am I paying for it*, and the
    only honest source for that is the paper the customer has. A tenant mid-way
    through a rate change would otherwise be shown next month's price beside
    equipment they were billed for at last month's.

    ⚠ **`None` IS AN ORDINARY ANSWER** — a service never billed, a brand-new
    account, a bill that carried no standing line. The screen states the
    absence; it does not print `$0.00`, which is a claim that the item is free.
    """
    invoice = None
    for row in recent_bills(account_ids, limit=1, today=today):
        invoice = row
        break
    if invoice is None:
        return None
    number = invoice.get("number")
    if not number:
        return None
    detail = bill_detail_for(account_ids, number=number, today=today)
    if detail is None:
        return None
    #: ⚠ **`service`, NOT `service_code`** — `_grouped_lines` serves
    #: `service` / `service_name` / `lines` / `subtotal_display`, and the first
    #: draft of this file read a key that shape does not have. It matched
    #: nothing on every account in the product and every unit test passed,
    #: because they fed it a fixture this file invented. Found by running it
    #: over live `pine-hill` data.
    for group in detail.get("groups") or ():
        if (group.get("service") or "") != service_code:
            continue
        for line in group.get("lines") or ():
            if (line.get("kind") or "") in CAPACITY_LINE_KINDS:
                return {**line, "bill_number": number}
    return None


def recent_bills(
    account_ids: list[Any], *, limit: int = RECENT_BILL_COUNT, today: date | None = None
) -> list[dict[str, Any]]:
    """The last few ISSUED bills across this login's accounts, newest first.

    ⚠ **`today` IS WHAT ADDS THE `state` AND `usage` COLUMNS, AND IT IS
    OPTIONAL SO `last_bill` DOES NOT PAY FOR THEM** (`DEF-CWP-3965`). The home
    page's *RECENT BILLS* table is `Bill / Period / Usage / Amount / Status`
    (`08-screen-layouts.md` `CWP-022`), and the two right-hand columns need a
    day to compare a due date against and the bill's own lines. The lead tile
    needs neither.

    ⚠ **THE STATE IS `_bill_state`'S — NOT A SECOND ARITHMETIC.** `CWP-027`
    already paints a chip from that function and a home page computing its own
    would be two answers to *is this bill overdue* one screen apart. The owing
    figure it reads comes from `payments`, never from subtraction here, for the
    reason `bills_for` states in full.

    ⚠ **THE FILTER STAYS `status = issued` AND DOES NOT WIDEN TO `bills_for`'s
    PAIR.** `CWP-027` lists a CORRECTED bill too (`BR-CWP-042`) because that is
    the screen a customer reconciles a bank statement on; three rows of *recent*
    on a home page are the last three things that happened, and a corrected
    original beside its replacement would spend two of the three saying the same
    thing twice.
    """
    rows = list(
        billing_models.Invoice.objects.filter(
            tenant_id=_tenant(), account_id__in=list(account_ids), status=ISSUED
        )
        .order_by("-issued_at", "-service_date")[: max(0, int(limit))]
    )
    if today is None:
        return [_bill_view(row) for row in rows]

    from apps.portal.seams import payments_seam

    owing_by_number: dict[str, Decimal] = {}
    for account_id in [str(one) for one in account_ids]:
        for row in payments_seam.account_balance(account_id).get("bills") or ():
            number = row.get("number")
            if number:
                owing_by_number[number] = Decimal(row.get("open_balance") or "0")
    usage = _usage_by_invoice([row.pk for row in rows])
    out: list[dict[str, Any]] = []
    for row in rows:
        owed = owing_by_number.get(row.invoice_no or "", Decimal("0"))
        out.append(
            {
                **_bill_view(row),
                "owing": _money(owed),
                "state": _bill_state(
                    status=row.status,
                    amount=Decimal(row.total or 0),
                    owing=owed,
                    due_on=row.due_date,
                    today=today,
                ),
                "usage": usage.get(str(row.pk), []),
            }
        )
    return out


def last_bill(account_ids: list[Any]) -> dict[str, Any] | None:
    """The most recent issued bill, or None. ⚠ `None` is a NORMAL answer — a
    new customer has not been billed yet, and the tile closes up rather than
    showing a zero (`BR-CWP-093`)."""
    found = recent_bills(account_ids, limit=1)
    return found[0] if found else None


def last_bill_high_usage(account_ids: list[Any]) -> str | None:
    """`CR-182-BRC10` (PO A1) — the NUMBER of the most recent issued bill when
    it priced a reading BR-MET-020/120 flagged high, else None.

    The bill's own frozen read ids (`_readings_behind`'s source, `DEF-098`), so
    the answer is about what THAT bill charged for. One bill is asked about: a
    newer bill replaces the notice, which is what *your last bill* means — the
    same `-issued_at, -service_date` order `recent_bills` takes.
    """
    from apps.portal.seams import metering_seam

    invoice = (
        billing_models.Invoice.objects.filter(
            tenant_id=_tenant(),
            account_id__in=[str(one) for one in account_ids],
            status=ISSUED,
        )
        .order_by("-issued_at", "-service_date")
        .only("invoice_no", "bill_payload")
        .first()
    )
    if invoice is None or not invoice.invoice_no:
        return None
    read_ids = _priced_read_ids(invoice)
    if not read_ids:
        return None
    flagged = metering_seam.flagged_high_read_ids(_tenant(), read_ids)
    return invoice.invoice_no if flagged else None


def _priced_read_ids(invoice: Any) -> list[str]:
    """EVERY reading this bill charged for — each service's closing `read_id`
    and its `chain_read_ids` (`DEF-CWP-10153`).

    ⚠ **THE CLOSING READ ALONE IS NOT WHAT THE BILL PRICED.** Since
    `DEF-BIL-9016` a period with a reading partway through charges for each
    reading in its chain, and stage 6 stamps them all, the closing one first
    (`DEF-BIL-9075`). Asking only `read_id` missed a high reading taken on
    10/13 inside an October bill whose 10/31 closing read was low — the bill
    charged all 94 kgal and said nothing (combined walk, 2026-10-14). A payload
    from before the chain was stamped has `read_id` alone, which still answers.
    """
    payload = invoice.bill_payload or {}
    ids: list[str] = []
    for entry in payload.get("services") or ():
        for one in (entry.get("read_id"), *(entry.get("chain_read_ids") or ())):
            if one and str(one) not in ids:
                ids.append(str(one))
    return ids


def bill_number_covering(account_ids: list[Any], on: date) -> str | None:
    """`CWP-034`'s *on which bill* — the ISSUED bill whose period covers `on`.

    ⚠ **A PERIOD MATCH, BECAUSE THERE IS NO REFERENCE TO FOLLOW.**
    `meter_reads` carries no invoice id at all — `ReadCorrection.invoice_id` is
    metering's only billing reference and it exists for a CORRECTION, not for a
    routine read. So the bill a reading fed is the one whose service period
    contains the day it was taken, which is the same correspondence a customer
    makes holding the paper.

    ⚠ **`None` IS THE ANSWER FOR ANYTHING NOT YET BILLED, AND THE CELL STAYS
    EMPTY** (`US-CWP-041` TC-4). A reading taken after the last bill, or one a
    clerk has not cleared, belongs to no issued bill; naming the nearest one
    would tell a customer they were charged for a reading nobody has billed.

    ⚠ **A DRAFT IS NEVER MATCHED** (`BR-CWP-041`) — the filter is the same
    `status = issued` every read in this file carries, in the QUERY.
    """
    row = (
        billing_models.Invoice.objects.filter(
            tenant_id=_tenant(),
            account_id__in=[str(one) for one in account_ids],
            status=ISSUED,
            period_start__lte=on,
            period_end__gte=on,
        )
        .order_by("-issued_at", "-service_date")
        .values_list("invoice_no", flat=True)
        .first()
    )
    return row or None


def bill_windows_for(account_ids: list[Any]) -> list[dict[str, Any]]:
    """Every ISSUED bill's own service period, newest first — **ONE query.**

    ⚠ **THIS IS `bill_number_covering` ASKED FOR THE WHOLE ACCOUNT AT ONCE
    (`DEF-CWP-5747`, 2026-09-19).** That function answers ONE day, and
    `apps/portal/selectors.account_readings` called it once per distinct
    `taken_on` in its payload — on an AMI account, one statement per DAY of
    history, to fill one column. The set question costs one.

    ⚠ **THE ORDER IS THE PRECEDENCE, AND IT IS THE SAME ONE.**
    `bill_number_covering` takes `-issued_at, -service_date` and the FIRST row
    whose period contains the day; a caller walking this list must stop at its
    first match for the two answers to agree where two issued periods overlap.

    ⚠ **A DRAFT IS NEVER HERE** (`BR-CWP-041`) — `status = issued`, in the
    query, exactly as the singular has it. A corrected bill is not here either:
    `CUSTOMER_VISIBLE_STATUSES` is a wider set for the BILLS list, and the
    reading column has always named the bill a reading was CHARGED on.

    ⚠ **NOT ONE DATABASE ID LEAVES THIS FUNCTION** (B14 rule 31): the number
    printed on the paper, and two dates.
    """
    rows = (
        billing_models.Invoice.objects.filter(
            tenant_id=_tenant(),
            account_id__in=[str(one) for one in account_ids],
            status=ISSUED,
            period_start__isnull=False,
            period_end__isnull=False,
        )
        .order_by("-issued_at", "-service_date")
        .values_list("invoice_no", "period_start", "period_end")
    )
    return [
        {"number": number, "from": start, "to": end}
        for number, start, end in rows
        if number
    ]


def reading_window_open(account_ids: list[Any], *, today: date) -> bool:
    """⚠ **STILL FALSE, AND THE REASON CHANGED ON 2026-09-04 — READ THE NEW ONE.**

    ⚠ **THE OLD REASON WAS WRONG AND IS CORRECTED HERE RATHER THAN LEFT TO
    ROT** (hard-won law 1). It said a read window *"lives in `metering` and is
    computed by `services._cycle_window_for`, which is a SERVICE function and
    not a published read"*. `ReadWindow` is a first-class metering TABLE with
    `period_start`, `period_end` and a `read_on` that is NULL while the window
    is open (`SET-06D`), and `metering.portal_reads.open_read_window_for_unit`
    publishes it — `CWP-033`'s third tile draws *next reading due 2–6 Sep* from
    it today.

    **THE FACT IS AVAILABLE; THE ACTION IS NOT.** `US-CWP-025` TC-8 wants the
    attention panel to offer *Send a reading*, and sending one is `US-CWP-042`
    — wave 3, and the one portal switch that is OFF for a new tenant
    (`CR-068` R8). An attention item is *a thing the customer can act on now*,
    so offering one whose only control does not exist would be worse than the
    absence (`BR-CWP-093`), and this seam keeps saying no until the write
    lands. Wiring it is `US-CWP-025`'s to do, not this seam's to decide.
    """
    return False


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-025@this-commit (EP-CWP-06 story + BR-CWP-041/093 verbatim)
# generated: 2026-09-04 by the CR-068 wave F build lane
# checklist: A✔ B✔ C✔ D✔(api.py home) E✔(CWP-022) F✔ G✔ H=n/a(it reads issued figures, it computes no money)
# gates: G81 (a seam performs no ORM write) · pytest tests/test_us_cwp_025_home.py
# exceptions: the usage chart is read from BILL LINES rather than from meter reads — metering publishes no per-account consumption read, and composing one here would put billing arithmetic in the portal. Decision logged 2026-09-04.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave G · `CWP-027` — every bill, with OWING beside AMOUNT
# ═══════════════════════════════════════════════════════════════════════════

#: `BR-CWP-043`'s states. ⚠ **`part_paid` IS A THIRD STATE AND NOT A SHADE OF
#: THE OTHER TWO** — a bill with `$40.00` against `$142.18` is neither paid nor
#: unpaid, and a screen that had to choose would be wrong either way: showing
#: it PAID asks nobody for the `$102.18`, showing it DUE asks for `$142.18`
#: twice.
BILL_PAID = "paid"
BILL_PART_PAID = "part_paid"
BILL_DUE = "due"
BILL_OVERDUE = "overdue"
BILL_CORRECTED = "corrected"

#: The statuses a customer may see. ⚠ A DRAFT IS NOT HERE (`BR-CWP-041`), and
#: `corrected` IS — `BR-CWP-042` requires the corrected pair to be **both
#: present**, the original greyed and naming its replacement. A bill that
#: silently vanished when it was corrected is a customer who cannot reconcile
#: their own records.
CUSTOMER_VISIBLE_STATUSES = (ISSUED, billing_models.INVOICE_CORRECTED)


def _bill_state(*, status: str, amount: Decimal, owing: Decimal, due_on: date | None,
                today: date) -> str:
    if status == billing_models.INVOICE_CORRECTED:
        return BILL_CORRECTED
    if owing <= 0:
        return BILL_PAID
    if 0 < owing < amount:
        return BILL_PART_PAID
    if due_on is not None and due_on < today:
        return BILL_OVERDUE
    return BILL_DUE


def bills_for(account_ids: list[Any], *, today: date) -> list[dict[str, Any]]:
    """`CWP-027` — every bill this login may see, newest first.

    ⚠ **`amount` AND `owing` ARE TWO COLUMNS AND THE SCREEN NEVER SUBTRACTS**
    (`BR-CWP-043`). The bill CHARGED `$142.18` and still OWES `$102.18`; both
    are facts the server computed, and a screen doing the arithmetic is a
    screen that can disagree with the ledger.

    ⚠ **A CORRECTED BILL IS LISTED AND NAMES ITS REPLACEMENT** (`BR-CWP-042`).
    `BL-2606-0137` at `$154.90` stays in the list, greyed, reading *Replaced by
    `BL-2606-0147`*, and the replacement at `$129.02` sits beside it. Dropping
    the original would leave a customer with a bank statement they cannot
    reconcile against anything.

    ⚠ **THE OWING FIGURE COMES FROM `payments`, NEVER FROM SUBTRACTION HERE.**
    `open_bill_position` already knows what each bill still owes, allocations
    and credits included; recomputing it from `total` minus something would be
    a second implementation of the one number a customer argues about.
    """
    from apps.portal.seams import payments_seam

    ids = [str(one) for one in account_ids]
    owing_by_number: dict[str, Decimal] = {}
    for account_id in ids:
        for row in payments_seam.account_balance(account_id).get("bills") or ():
            number = row.get("number")
            if number:
                owing_by_number[number] = Decimal(row.get("open_balance") or "0")

    rows = list(
        billing_models.Invoice.objects.filter(
            tenant_id=_tenant(), account_id__in=ids, status__in=CUSTOMER_VISIBLE_STATUSES
        )
        .select_related("corrects_invoice")
        .prefetch_related("corrected_by")
        .order_by("-issued_at", "-service_date")
    )
    #: `DEF-CWP-3980` — **the same helper the home page's table already uses**,
    #: over the whole list in ONE query. `CWP-027`'s drawn columns are
    #: `Bill / Period / Issued / Due / Usage (with unit) / Amount / Owing /
    #: Status`, and *Usage* was the one of the eight this read could not answer.
    #: Reusing `_usage_by_invoice` rather than writing a second sum is law 5:
    #: two answers to *what did this bill charge me for*, one screen apart, is
    #: how they start disagreeing.
    usage = _usage_by_invoice([row.pk for row in rows])
    out: list[dict[str, Any]] = []
    for row in rows:
        amount = Decimal(row.total or 0)
        owing = owing_by_number.get(row.invoice_no or "", Decimal("0"))
        replacement = next(iter(row.corrected_by.all()), None)
        out.append(
            {
                **_bill_view(row),
                "owing": _money(owing),
                "state": _bill_state(
                    status=row.status, amount=amount, owing=owing,
                    due_on=row.due_date, today=today,
                ),
                #: `DEF-CWP-3980` — the chip counts DOWN (*Due in 12 days*), and
                #: the count is computed HERE against the same `today` the state
                #: word was computed against. A browser subtracting its own
                #: clock from a due date would paint *Due in 12 days* beside a
                #: chip the server had already called `overdue`, for every
                #: customer whose device is a day out or in another time zone.
                #: `None` when the bill carries no due date, which the screen
                #: draws as the plain state word.
                "due_in_days": (
                    (row.due_date - today).days if row.due_date is not None else None
                ),
                #: One entry per UNIT and never a sum across units (hard rule 3).
                #: `[]` for a base-only bill, which the screen draws as an empty
                #: cell — a bill for a fixed charge is not a bill for nothing.
                "usage": usage.get(str(row.pk), []),
                #: `BR-CWP-042` — the original NAMES the replacement, by the
                #: number on the paper and never by an id (B14 rule 31).
                "replaced_by": getattr(replacement, "invoice_no", None),
                #: …and the replacement names what it replaced, so a customer
                #: reading either row can find the other.
                "replaces": getattr(row.corrects_invoice, "invoice_no", None),
            }
        )
    return out


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave H · `CWP-028` · `CWP-029` · `CWP-030`
#
# ⚠ **NOTHING BELOW IS A SECOND READ OF A BILL.** PO ruling 2026-09-04,
# verbatim: *"all the services that are required for Consumer portal - you will
# find it same set of services, endpoints are already available for Accounts -
# account details view"*. The staff bill detail (`S30`) is served by
# `apps.billing.selectors.invoice_detail` and the bill AS PRINTED by
# `apps.billing.frozen_bill.reproduce`; those two are what these functions
# call. What the portal adds is (a) `BR-CWP-010`'s intersection, in the query,
# (b) the projection that drops every database id (B14 rule 31), and (c) the
# customer's grouping — WATER · SEWER · TRASH · TAXES AND FEES.
#
# **Every money figure is the server's own.** `charges_by_service` already
# takes B4's 2026-08-11 reading — Σ of the ROUNDED lines, so a customer adding
# the printed column down reaches the printed subtotal — and serves the 2dp
# `subtotal_display` beside the 4dp stored figure. Recomputing any of that here
# would be a second implementation of signed money law (hard-won law 5).
# ═══════════════════════════════════════════════════════════════════════════

#: The one group that is NOT a service. `charges_by_service` puts every line
#: with no `service_id` into one bucket for a ruled reason — *"Tax rates are
#: for bill not for service"* (PO 2026-08-11) — and the wireframe heads it
#: **TAXES AND FEES**. The code travels; the catalogue writes the word
#: (B14 rule 35).
BILL_LEVEL_GROUP = "taxes_and_fees"


def _display(value: Any) -> str:
    """The 2dp figure a customer reads (hard rule 2 — *display both 2 decimal*).

    `core.money.finalize` and never a local `quantize`: the rounding constants
    are HUMAN-OWNED and this file may APPLY them, never restate them. It is the
    same helper `billing.selectors._display_money` applies, so the portal and
    the staff screen round once, in one place, the same way.
    """
    return str(money.finalize(Decimal(value or 0)))


def _display_or_none(value: Any) -> str | None:
    """`None` in, `None` out — an unstamped figure is ABSENT, never `0.00`.

    `BR-BIL-035`'s stamp writes NULLS rather than zeros when the payments seam
    was unreachable, on purpose: *"0.00 would tell a customer in arrears that
    they are square"*. That distinction has to survive this projection.
    """
    return None if value is None else _display(value)


def bill_in_set(account_ids: list[Any], *, number: str) -> Any | None:
    """The ONE lookup every bill screen goes through — `BR-CWP-010` in the query.

    ⚠ **BOTH HALVES ARE SPELLED IN THE `filter()` AND NEITHER IS A CHECK
    AFTERWARDS** — `BR-CWP-010` says *in the query*, and this writes the tenant
    out rather than leaning on `app.tenant_id` alone. RLS `FORCE` is on in
    production and is the real guarantee; the reason the column is named here
    as well is CLAUDE.md law 14's setting in a second costume: **the suite runs
    on SQLite, which has NO RLS**, so a read that relied on the database for the
    tenant half would have no test that could ever see it go wrong. Naming it
    makes the rule true in the query TEXT and provable on the suite.

    A bill outside this login's accounts is therefore never fetched rather than
    fetched-then-refused; a read that loaded the row first would hold another
    customer's data in memory before deciding, which is a disclosure one
    exception handler away.

    ⚠ **BY `invoice_no`, NEVER BY ID** (B14 rule 31, PO 2026-08-30: *"no
    Databse ID on screen - that is a rule"*, and `accountDetailTabs.tsx`'s own
    finding that EIGHT CHARACTERS of a uuid is the same breach as all of it).
    The number is printed on the paper the customer is holding, so it is what
    the address bar carries.

    `None` for an unknown number, another login's bill and a DRAFT alike — one
    answer, so a customer cannot probe which bills exist (`BR-CWP-041`).
    """
    if not number:
        return None
    tenant_id = current_tenant_id()
    if tenant_id is None:
        # Hard rule 1 — never touch a tenant table without `app.tenant_id`.
        raise RuntimeError("bill_in_set called with no tenant in context (hard rule 1)")
    return (
        billing_models.Invoice.objects.filter(
            tenant_id=tenant_id,
            account_id__in=[str(one) for one in account_ids],
            invoice_no=number,
            status__in=CUSTOMER_VISIBLE_STATUSES,
        )
        .select_related("corrects_invoice")
        .prefetch_related("corrected_by")
        .first()
    )


#: What a GUEST holding a paper bill may be shown — wider than
#: `CUSTOMER_VISIBLE_STATUSES` by exactly two members, and each is a test case.
#:
#: ⚠ **`paid` AND `void` ARE HERE BECAUSE SILENCE WOULD BE THE WRONG ANSWER.**
#: `US-CWP-003` TC-4: a PAID bill *"Opens showing `$0.00` owing and no Pay
#: control — not a refusal, because the holder is entitled to know it is
#: paid"*. TC-5: a VOIDED bill *"Reads 'cancelled' and offers no payment"*.
#: Refusing either would answer identically to *no such bill*, which would send
#: somebody who has already paid to the office to ask why their bill has
#: vanished — the telephone call this whole screen exists to prevent.
#:
#: ⚠ **`draft` IS NOT HERE AND NEVER MAY BE.** A draft was never sent, so
#: nobody can be holding it; it is refused identically to a number that does
#: not exist, which is `US-CWP-003` TC-3.
GUEST_VISIBLE_STATUSES = (
    ISSUED,
    billing_models.INVOICE_PAID,
    billing_models.INVOICE_VOID,
    billing_models.INVOICE_CORRECTED,
)


def bill_by_number(tenant_id: Any, *, number: str) -> Any | None:
    """`CWP-002` — one bill by the number printed on it, for a stranger.

    ⚠ **THE ONE READ ON THIS SURFACE WITH NO ACCOUNT SET, AND THE SECOND FACT
    IS WHAT REPLACES IT.** Every other portal read filters on the session's
    accounts (`BR-CWP-010`); a guest has no session and no accounts, so the
    guard is `BR-CWP-025` — the caller must also match the postcode of the
    service address, which `selectors.bill_lookup` does before it discloses
    anything. **This function on its own is a bill-number oracle and must never
    be called from anywhere else.**

    ⚠ **THE TENANT IS IN THE QUERY** (`BR-CWP-010`, `G96`, `DEF-CWP-3775`) and
    is this function's own argument rather than `app.tenant_id` alone: the
    suite runs on SQLite, which has no row-level security, so a read that left
    the tenant to the database would have no test that could ever see it go
    wrong (law 14 in its second costume). `TC-6` — Pine Hill's number submitted
    on `/oak-ridge` — is what asserts it.

    `None` for an unknown number, another utility's number and a DRAFT alike.
    """
    typed = str(number or "").strip()
    if not typed:
        return None
    if tenant_id is None:
        # Hard rule 1 — never touch a tenant table without `app.tenant_id`.
        raise RuntimeError("bill_by_number called with no tenant (hard rule 1)")
    # ⚠ **TRIMMED AND UPPER-CASED (`DEF-CWP-10711`, audit L1-07, 2026-10-30).**
    # A customer copying `bl-2610-000079 ` off a phone screen was told the bill
    # does not exist. The number is matched as typed OR in capitals — never a
    # case-insensitive LIKE, which would stop the (tenant, number) index being
    # used — so a utility whose numbering carries a lower-case prefix still
    # matches exactly. Every miss is still one `None`: the postcode compare and
    # the single sentence at the edge are untouched (`BR-CWP-025`).
    return (
        billing_models.Invoice.objects.filter(
            tenant_id=tenant_id,
            invoice_no__in=sorted({typed, typed.upper()}),
            status__in=GUEST_VISIBLE_STATUSES,
        )
        .select_related("corrects_invoice")
        .prefetch_related("corrected_by")
        .first()
    )


def owing_on(invoice: Any) -> Any:
    """What this bill still owes — `payments`' figure, never a subtraction.

    The public face of `_owing_of`: `selectors.bill_lookup` needs the same
    number `CWP-027` and `CWP-028` already show, and a second implementation
    would be a second answer to the one figure a customer argues about.
    """
    return _owing_of(invoice)


def replacement_number(invoice: Any) -> str | None:
    """The number of the bill that REPLACED this one, or None (`BR-CWP-042`).

    `US-CWP-003` TC-7: a corrected bill *"Reads 'replaced by BL-2606-0147' and
    directs payment at the replacement"*. Dropping the original instead would
    leave somebody holding a piece of paper the product denies exists.
    """
    replacement = list(getattr(invoice, "corrected_by", None).all())[:1] if invoice else []
    return getattr(replacement[0], "invoice_no", None) if replacement else None


def _quantity_of(line: dict[str, Any]) -> dict[str, Any]:
    """A quantity and its unit, or NEITHER — hard rule 3, held in the read.

    ⚠ **A LINE WITH A QUANTITY AND NO UNIT SERVES `null`, NOT THE NUMBER.**
    `4,820` in a column headed *Quantity* is read as whatever unit the reader
    assumes; `4,820 gal` is the whole point of the column. Refusing it HERE
    rather than on the screen is deliberate: a screen can be rewritten by a
    lane that has not read this rule, and the wire then cannot hand it a bare
    number to render. Stage 6 already refuses to WRITE one, so this is the
    second guard on a rule the product must not break in public.

    `quantity_display.quantity_text` is `BR-MET-144`'s own helper — at most two
    decimals, trailing zeros trimmed — and not a fourth spelling of it.
    """
    quantity = line.get("quantity")
    unit = (line.get("unit") or "").strip()
    if quantity is None or not unit:
        return {"quantity": None, "unit": None}
    return {"quantity": quantity_display.quantity_text(quantity), "unit": unit}


def _rate_basis_of(line: dict[str, Any]) -> dict[str, Any]:
    """WHAT KIND of number the rate is — a price per unit, or a proportion.

    ⚠ **THE DISCRIMINATOR IS STRUCTURAL AND NOT A LIST OF `kind` VALUES.** A
    line priced off a meter carries a UNIT — that is `_quantity_of`'s rule one
    function up, and hard rule 3 makes it non-optional — so its `unit_price` is
    money PER that unit. A line with a rate and no unit is pricing a
    PROPORTION of something else: `percent_of_service` says so in its own
    words (*"No quantity and no unit: this line prices DOLLARS, not a metered
    volume"*) and `TaxRuleSpec.rate` is documented as a fraction (`0.0825`).
    Reading `kind` instead would need this function to be kept in step with
    every pricing model anybody adds.

    ⚠ **THE ×100 HAPPENS HERE, NOT ON THE SCREEN.** The stored figure is a
    FRACTION (`0.0625`) and a percentage is `6.25`. `wording.percent_text`
    takes POINTS and its docstring is emphatic about the two conventions —
    *"handing a fraction to this function serves `0.02%` for a two-percent
    rate, and handing points to a fraction formatter serves `4000.00%`. Both
    are well-formed strings."* Converting in a browser would put that trap on
    the one surface a customer reads.

    Hard rule 2: a percentage DISPLAYS at two places, padded — `6.25`, and
    `40.00` rather than `40`.
    """
    price = line.get("unit_price")
    if price is None:
        return {"rate_basis": None, "rate_percent": None}
    if (line.get("unit") or "").strip():
        return {"rate_basis": RATE_PER_UNIT, "rate_percent": None}
    points = Decimal(str(price)) * 100
    return {"rate_basis": RATE_PERCENT, "rate_percent": wording.percent_text(points)}


def _line_view(line: dict[str, Any]) -> dict[str, Any]:
    """One charge line as a customer reads it — no id, no GL, no tariff stamp.

    The staff row carries `id`, `gl_account_id`, `tariff_version_id`, `tax_id`
    and `charge_id`. Every one is a database id (B14 rule 31) and none is a
    fact a customer can act on, so the projection DROPS them rather than
    serving them and trusting a screen not to draw them.

    `amount_display` is the figure the customer ADDS UP, and it is the same 2dp
    rounding `charges_by_service` summed to reach the group subtotal — so the
    column foots against its own heading by construction rather than by luck
    (`US-CWP-033` TC-2).

    ⚠ **THE SIGN IS THE SERVER'S.** Nothing here takes an absolute value. A
    credit line is negative and prints negative; `accountDetailTabs.tsx`
    records what the other reading cost — a panel reading `272.30` where the
    customer owed `222.30`.
    """
    return {
        "description": line.get("description"),
        **_quantity_of(line),
        #: OQ-620(a) as narrowed 2026-10-02 — a unit PRICE shows up to FOUR
        #: decimals and at least two (PO: *"Show unit prices with up to 4
        #: decimals and keep every total at 2"*). It is NOT run through
        #: `_display`, which would round a rate to money's two.
        "rate": (
            wording.rate_text(line["unit_price"]) if line.get("unit_price") is not None else None
        ),
        #: `DEF-CWP-3967` — **WHAT KIND OF NUMBER THE RATE IS**, so the screen
        #: can put a currency and a unit on one and a `%` on the other. The
        #: figure alone was reaching customers bare: `4.2400` next to a water
        #: line, `0.0200` next to a local tax, and nothing on the page saying
        #: whether either was dollars, cents, or per what.
        **_rate_basis_of(line),
        #: `DEF-BIL-8744` — the days a line was cut down by (`{"days": 19,
        #: "of": 30}`), so *6 kW · $14.0000 · 19/30 days* foots to `$53.20`.
        #: Two counts, no id; null on every line that foots without it.
        "day_share": line.get("day_share"),
        "amount": line.get("amount"),
        "amount_display": _display(line.get("amount")),
        "kind": line.get("kind"),
    }


def _grouped_lines(detail: dict[str, Any]) -> list[dict[str, Any]]:
    """`WATER · SEWER · TRASH · TAXES AND FEES` — the catalogue's own order.

    ⚠ **THE ORDER IS `charges_by_service`'s AND IT IS `services.sort`**, the
    seeded catalogue order every other screen draws the eleven services in.
    Alphabetical would put sewer before water on the bill and after it
    everywhere else.

    ⚠ **UP TO ELEVEN GROUPS CAN APPEAR** (`BR-RAT-024`), which is why the
    grouping is structural rather than a fixed four-heading layout. Fire is
    among them and it COUNTS: one 6" line and two 2" lines is `$60.00` and
    `2 × $12.00` on **two lines** in one group, exactly as the rows were
    written — nothing here sums or collapses them.
    """
    block = detail.get("charges_by_service") or {}
    by_service: dict[Any, list[dict[str, Any]]] = {}
    for line in detail.get("lines") or ():
        by_service.setdefault(line.get("service"), []).append(line)

    groups: list[dict[str, Any]] = []
    for row in block.get("services") or ():
        code = row["service"]
        groups.append(
            {
                "service": code,
                #: The platform catalogue's name, so a tenant with no word for a
                #: service still gets one. The CATALOGUE writes the customer's
                #: word (B14 rule 35) and falls back to this.
                "service_name": row.get("service_name"),
                "subtotal_display": row.get("subtotal_display"),
                "lines": [_line_view(line) for line in by_service.get(code, ())],
            }
        )
    bill_level = block.get("bill_level") or {}
    unfiled = by_service.get(None) or []
    if unfiled:
        groups.append(
            {
                "service": BILL_LEVEL_GROUP,
                "service_name": None,
                "subtotal_display": bill_level.get("subtotal_display"),
                "lines": [_line_view(line) for line in unfiled],
            }
        )
    return groups


def _owing_of(invoice: Any) -> Decimal:
    """What this bill still owes — `payments`' figure, never a subtraction here.

    The same posture `bills_for` takes and for the same reason:
    `open_bill_position` already knows what each bill owes, allocations and
    credits included, and `total` minus something would be a second
    implementation of the one number a customer argues about.
    """
    from apps.portal.seams import payments_seam

    for row in payments_seam.account_balance(invoice.account_id).get("bills") or ():
        if row.get("number") == invoice.invoice_no:
            return Decimal(row.get("open_balance") or "0")
    return Decimal("0")


def _readings_behind(invoice: Any) -> list[dict[str, Any]]:
    """The reads that PRICED this bill, named by the bill's own frozen payload.

    ⚠ **THE IDENTITY IS FROZEN, NOT LOOKED UP** (`DEF-098`). Stage 6 stamps
    `bill_payload["services"][].read_id` — *"WHICH METER READING produced the
    quantity"* — precisely so a reprint years later can name the read it
    charged for. Asking metering *"what is the latest read on this unit"*
    instead would answer with a read taken AFTER the bill was sent, on a screen
    whose whole job is to explain the bill in the customer's hand.

    A service with no read (no meter, base-only, trash on a cart) contributes
    nothing rather than a placeholder, and a bill issued before the stamp
    existed answers `[]` — which the screen states (`BR-CWP-093`).
    """
    from apps.portal.seams import metering_seam

    payload = invoice.bill_payload or {}
    read_ids = [
        entry.get("read_id") for entry in (payload.get("services") or ()) if entry.get("read_id")
    ]
    return metering_seam.reads_behind_bill(read_ids)


def bill_detail_for(account_ids: list[Any], *, number: str, today: date) -> dict[str, Any] | None:
    """`CWP-028` — one bill, line by line, and the figures it must foot to.

    ⚠ **THIS CALLS THE STAFF READ AND ADDS NO ARITHMETIC TO IT** (PO
    2026-09-04). `billing.selectors.invoice_detail` is `S30`'s own read — the
    reuse map's row for this screen — and the portal serves the same facts in a
    customer's words. A portal read of `invoice_lines` would be a second answer
    to the one number a customer argues about, and the two would drift the
    first time a rounding reading moved.

    ⚠ **`subtotal_display + tax_display` EQUALS `total_display`, FROM THE
    DISPLAYED FIGURES** (`US-CWP-033` TC-2). All three are `money.finalize` of
    a stored figure, so the identity holds arithmetically rather than by
    assertion; the test asserts it anyway, because *"a penny of disagreement
    here is a support call"* and nothing else in this repo reads a rendered
    column.
    """
    from apps.billing import selectors as billing_selectors
    from apps.portal.seams import metering_seam

    invoice = bill_in_set(account_ids, number=number)
    if invoice is None:
        return None
    detail = billing_selectors.invoice_detail(invoice.pk)
    summary = detail.get("summary") or {}
    owing = _owing_of(invoice)
    readings = _readings_behind(invoice)
    return {
        **_bill_view(invoice),
        "owing": _money(owing),
        #: `CR-182-BRC10` (PO A2) — this bill priced a reading BR-MET-020/120
        #: flagged high, so the screen says *High usage* and nothing longer.
        #: Asked of EVERY read the bill priced, not only the ones listed
        #: (`DEF-CWP-10153`): a high reading partway through the period counts.
        "high_usage": bool(
            metering_seam.flagged_high_read_ids(_tenant(), _priced_read_ids(invoice))
        ),
        "state": _bill_state(
            status=invoice.status,
            amount=Decimal(invoice.total or 0),
            owing=owing,
            due_on=invoice.due_date,
            today=today,
        ),
        "replaced_by": getattr(next(iter(invoice.corrected_by.all()), None), "invoice_no", None),
        "replaces": getattr(invoice.corrects_invoice, "invoice_no", None),
        "groups": _grouped_lines(detail),
        #: The three figures the footer prints, each rounded ONCE by the server.
        "subtotal_display": _display(detail.get("subtotal")),
        "tax_display": _display(detail.get("tax_total")),
        "total_display": _display(detail.get("total")),
        #: The rail — **YOUR ACCOUNT**. `previous_balance` and
        #: `payments_credits` are `BR-BIL-035`'s stamp, written once at issue
        #: over the account's still-open earlier bills; they are read back,
        #: never re-added (`_summary_for`'s own rule).
        "account": {
            "brought_forward": _display_or_none(summary.get("previous_balance")),
            "paid_since": _display_or_none(summary.get("payments_credits")),
            "this_bill": _display(detail.get("total")),
            "owing": _display(owing),
        },
        #: `BR-CWP-071` — the readings behind the bill, WITH HOW EACH WAS TAKEN.
        "readings": readings,
    }


# ═══════════════════════════════════════════════════════════════════════════
# `CWP-029` — THE BILL AS IT WAS PRINTED (`US-CWP-034`, `BR-CWP-045`)
# ═══════════════════════════════════════════════════════════════════════════

#: `frozen_bill.PROVENANCE_ORIGINAL` — the kept artefact, byte for byte.
PRINTED_ORIGINAL = "original"
#: `frozen_bill.PROVENANCE_RE_RENDERED` — no copy was kept. ⚠ **THE PORTAL
#: REFUSES THIS RATHER THAN SERVING IT** — see `printed_bill_for`.
PRINTED_RE_RENDERED = "re_rendered_from_data_not_the_original"


def printed_bill_for(account_ids: list[Any], *, number: str) -> dict[str, Any] | None:
    """`CWP-029` — *the document you actually sent me*, or an honest refusal.

    ⚠ **THE STORED ARTEFACT EXISTS AND THIS IS IT** — the finding the coordinator
    asked for by name. `apps/tenancy/document_store` keeps the bill's HTML and
    its PDF, frozen at issue by `billing.frozen_bill.freeze_at_issue`
    (`BR-NOT-027`, `CR-049` task 4), and `frozen_bill.reproduce` answers WHICH
    document a caller may serve without rendering anything. That is the same
    function `apps/billing/documents_api.py` calls for the staff screen, and it
    is why this file renders NOTHING: `BR-CWP-045` — *"serves the issued file
    from its pinned template; never re-renders"* — is satisfied by calling the
    module that owns the bytes, not by owning a second renderer.

    ⚠ **A RE-RENDER IS REFUSED HERE, WHICH IS STRICTER THAN THE STAFF ROUTE,
    AND DELIBERATELY.** `documents_api` serves the rebuild to a CLERK with
    `X-Document-Provenance` saying so, because a clerk can read the caption and
    act on it. A customer cannot: this screen's promise is *"exactly as it was
    printed and posted on 30 August"*, and handing over a fresh render under
    that sentence is the one thing `US-CWP-034` exists to prevent — the
    figures would be right (`BR-BIL-030` freezes them) and the PAGE could
    differ from the one in their drawer. So a bill with no kept copy answers
    `available: false` with its reason, and `US-CWP-034` TC-4's *plain sentence
    and a route to ask* is what the screen draws.

    ⚠ **THE PIN IS REPORTED, INCLUDING ITS LANGUAGE VARIANT** (TC-6). It is the
    invoice's own `template_version`, stamped at issue — so `bill-v4` published
    on 1 September and a changed tenant logo both leave this untouched, because
    neither is read.

    Returns `None` only when the BILL is not this login's (`BR-CWP-010`); an
    unavailable DOCUMENT is a real answer about a real bill.
    """
    from apps.billing import frozen_bill
    from apps.portal.seams import notifications_seam
    from apps.tenancy import document_storage, document_store

    invoice = bill_in_set(account_ids, number=number)
    if invoice is None:
        return None
    reproduction = frozen_bill.reproduce(invoice)
    page = reproduction.pdf if reproduction.is_original else None
    #: ⚠ **`available` USED TO BE A CLAIM ABOUT A ROW AND THE SERVING PATH IS A
    #: CLAIM ABOUT BYTES, AND THEY DISAGREED (`CR-085` `CPB-19`,
    #: `DEF-CWP-4658`).** Measured on a live portal session: this read answered
    #: `available: true` for `BL-2607-000003` while
    #: `GET .../document.pdf?view=1` answered **409** for the same bill in the
    #: same second, because the row was there and the object was not. The
    #: screen believes this field — it draws the frame, the sentence *"Exactly
    #: as it was printed and posted on 2 July"* and a download link — so the
    #: customer met a broken frame and a link that fails, over a bill we had
    #: just told them we still had.
    #:
    #: ⚠ **SO IT ASKS THE SAME QUESTION THE SERVING PATH ASKS**, through the
    #: same `document_store.fetch`, and the two cannot disagree any more. It
    #: costs ONE extra object read per open of `CWP-029` — one document, for
    #: one customer, who is about to fetch the very same object to look at it —
    #: and the bytes are dropped on the floor here rather than carried up,
    #: because this read answers a question and the PDF route serves the file.
    #: ⚠ **THE LIST (`CWP-031`) DELIBERATELY DOES NOT DO THIS**: forty rows
    #: would be forty object reads to draw a table, so there the flag stays a
    #: statement about the ROW and the file route answers precisely. That
    #: asymmetry is written down rather than discovered.
    served: str = notifications_seam.DOCUMENT_NOT_KEPT
    if page is not None:
        served = notifications_seam.DOCUMENT_OK
        try:
            document_store.fetch(page.id)
        except document_storage.StoredObjectMissing:
            served = notifications_seam.DOCUMENT_NOT_KEPT
        except document_storage.ContentHashMismatch:
            served = notifications_seam.DOCUMENT_NOT_TRUSTED
    available = served == notifications_seam.DOCUMENT_OK
    return {
        "number": invoice.invoice_no,
        "issued_on": invoice.issued_at.date().isoformat() if invoice.issued_at else None,
        "provenance": reproduction.provenance,
        #: TRUE only for a kept original this deployment can actually hand over.
        #: A screen branches on this one field.
        "available": available,
        #: Why not, when not — `document_store`'s own word, so the sentence a
        #: customer reads and the reason an operator debugs are one fact.
        #: ⚠ **`document_bytes_do_not_match` IS ITS OWN REASON AND NOT A
        #: SPELLING OF `document_not_stored`** (`BR-NOT-027`): *missing* means
        #: we no longer have it and *tampered* means what we have is not what
        #: you received, and the screen says two different things.
        "unavailable_reason": (
            None
            if available
            else (
                "document_bytes_do_not_match"
                if served == notifications_seam.DOCUMENT_NOT_TRUSTED
                else (reproduction.unavailable_reason or "document_not_stored")
            )
        ),
        #: `BR-BIL-026`'s pin, reported so TC-2/TC-3/TC-6 have something to
        #: assert against. No id: the VERSION is a number on a template, not a
        #: row a customer can look up (B14 rule 31 is about ids, and this is
        #: not one — the `template_id` uuid is deliberately not served).
        "template_version": invoice.template_version,
        "byte_length": getattr(page, "byte_length", None),
        "content_type": getattr(page, "content_type", None),
    }


def printed_bill_bytes(account_ids: list[Any], *, number: str) -> tuple[bytes, str, str] | None:
    """The kept page itself — `(bytes, content_type, filename)` — or `None`.

    ⚠ **HASH-VERIFIED ON THE WAY OUT**, because `document_store.fetch` verifies
    and this file does not repeat the check with its own spelling. A copy whose
    bytes have moved raises rather than being served, which is `BR-NOT-027`'s
    posture: a tampered document refuses; it never degrades into a re-render.

    ⚠ **NOTHING IS RENDERED ON THIS PATH.** If the store has no original the
    answer is `None` and the caller states the absence. There is no fallback,
    for `printed_bill_for`'s reason.

    ── THERE ARE TWO WAYS TO HAVE NO ORIGINAL (DEF-CWP-4657) ────────────────
    The first is **no document row**, caught by `reproduction.pdf is None`
    below. The second is **a row whose bytes have gone from the store** — a
    redeploy onto a different volume, a restored database, a retention sweep —
    and until this catch existed it raised straight through and reached the
    customer as a raw **500**, on the one endpoint whose own docstring says
    *"NOT A 500 AND NOT A RE-RENDER"*. Both are the same fact to the person
    looking at the screen: we do not have the page we sent you. Both answer
    `None`, and `bill_document_pdf` states the absence with the wording it
    already had.

    ⚠ **A TAMPERED COPY IS NOT MERGED WITH A MISSING ONE, AND IT IS NO LONGER
    A 500 EITHER (`CR-085` `CPB-19`).** `BR-NOT-027`: a tampered document
    refuses and never degrades. Missing means *we no longer have it*; tampered
    means *what we have is not what you received*, and softening the second into
    "no copy kept" is the one outcome this path must never produce.
    `document_storage` draws that line — `StoredObjectMissing` against
    `ContentHashMismatch`, each with its own message — and before
    `DEF-CWP-4657` **nothing in the codebase caught either**. That defect caught
    the first. The second was left uncaught **on purpose**, to keep the
    distinction — and the cost of keeping it that way was a Django error page in
    front of a customer who pressed *view my bill*, measured on this route.
    `printed_bill_service` below answers the three cases apart; this function
    keeps its two-valued shape for the callers and tests that had it, and
    **`None` here still means one of the two refusals rather than a raise**.
    """
    from apps.portal.seams import notifications_seam

    verdict, payload, content_type, filename = printed_bill_service(
        account_ids, number=number
    )
    if verdict != notifications_seam.DOCUMENT_OK or payload is None:
        return None
    return (payload, content_type or "application/pdf", filename or f"{number}.pdf")


def printed_bill_service(
    account_ids: list[Any], *, number: str
) -> tuple[str, bytes | None, str | None, str | None]:
    """The kept page, or WHICH refusal — `(verdict, bytes, content_type, name)`.

    ⚠ **THE VERDICTS ARE `notifications_seam`'s AND NOT A SECOND SET.** A bill
    and a receipt refuse for the same three reasons and a customer reads the
    same three sentences; two vocabularies for one fact is how the two screens
    would eventually disagree (`CR-085` `CPB-14`/`CPB-19`).

    ⚠ **A BILL OUTSIDE THIS LOGIN'S SET IS `not_kept` HERE AND A 404 AT THE
    EDGE.** `BR-CWP-010` is answered by `bill_in_set` above this line, and the
    edge turns a `None` invoice into the not-found refusal before it ever reads
    this verdict — so the two are never confused.
    """
    from apps.billing import frozen_bill
    from apps.portal.seams import notifications_seam
    from apps.tenancy import document_storage, document_store

    invoice = bill_in_set(account_ids, number=number)
    if invoice is None:
        return (notifications_seam.DOCUMENT_NOT_KEPT, None, None, None)
    reproduction = frozen_bill.reproduce(invoice)
    if not reproduction.is_original or reproduction.pdf is None:
        return (notifications_seam.DOCUMENT_NOT_KEPT, None, None, None)
    page = reproduction.pdf
    name = f"{invoice.invoice_no or invoice.pk}.pdf"
    try:
        payload = document_store.fetch(page.id)
    except document_storage.StoredObjectMissing:
        return (notifications_seam.DOCUMENT_NOT_KEPT, None, None, name)
    except document_storage.ContentHashMismatch:
        return (notifications_seam.DOCUMENT_NOT_TRUSTED, None, None, name)
    return (notifications_seam.DOCUMENT_OK, payload, page.content_type, name)


# ═══════════════════════════════════════════════════════════════════════════
# `CWP-030` — WHY THIS BILL IS DIFFERENT (`US-CWP-035`, `BR-CWP-046`)
#
# ⚠ **THE DECOMPOSITION RULE IS PROPOSED, NOT SIGNED, AND A LANE MUST NOT
# RATIFY ITS OWN FORMULA.** `US-CWP-035` §7 says so in as many words: it is new
# arithmetic on a money path, B4/B5 are ❄️ FROZEN, and *"which components exist,
# and in what order they are attributed when two move at once"* is a FINANCE
# judgment. It is raised as `OQ-CWP-1563` with the worked figure and the
# derivation is stubbed on that id — the prime directive's *implement up to the
# boundary*.
#
# WHAT IS BUILT, BECAUSE ALL OF IT IS CONFIRMED:
#   · the DIFFERENCE — `142.18 − 138.44 = 3.74`, plain subtraction of two
#     stored totals, not a decomposition;
#   · the direction — *cost more* / *cost less*, signs never absolute (TC-4);
#   · the NO-COMPARISON case — a first bill offers none at all, and not one
#     against zero (TC-5);
#   · `BR-CWP-046`'s ADDITIVE INVARIANT, which is CONFIRMED and holds under
#     ANY signed decomposition: Σ components ≡ difference, with no tolerance.
# ═══════════════════════════════════════════════════════════════════════════

#: ⚠ **THE ONE SWITCH, AND ONLY FINANCE MAY MOVE IT.** `False` until the
#: decomposition rule is signed through HUMAN-GUIDE §6 (`OQ-CWP-1563`). Flipping
#: it calls `_components_for`, which raises until somebody writes the signed
#: rule into it — so a lane cannot enable the panel by accident, and the day the
#: ruling lands there is exactly one place to look.
#: ⚠ **TRUE SINCE 2026-09-05, WHEN THE PRODUCT OWNER RULED IT** — verbatim,
#: *"(a) list every reason with its share"* (`OQ-CWP-1563` / `OQ-CWP-1569`,
#: decision log of that day). It stood FALSE while the decomposition was a
#: finance judgment nobody had made; `DEF-CWP-3968` is the record that the
#: ruling reached the decision log and not this line, so the screen went on
#: saying it could not explain two totals it had every ingredient to explain.
COMPONENTS_SIGNED = True

#: `US-CWP-035` TC-4 — the two directions, and the words are the catalogue's.
MOVED_UP = "cost_more"
MOVED_DOWN = "cost_less"
MOVED_NOT_AT_ALL = "cost_the_same"


def _prior_bill(invoice: Any) -> Any | None:
    """The bill BEFORE this one on the same account — its comparison, or none.

    Ordered by `period_end` and not by `issued_at`: a backbill issued today for
    March is not last month's bill, and comparing August against it would
    explain a difference nobody experienced. `billing.selectors`' own module
    docstring makes the same argument about ordering by issue time.

    ⚠ **A CORRECTED BILL IS NOT A COMPARISON.** It was replaced; explaining
    this month against a figure the utility itself withdrew would compare
    against a number that is no longer owed.
    """
    return (
        billing_models.Invoice.objects.filter(
            tenant_id=_tenant(),
            account_id=invoice.account_id,
            status=ISSUED,
            period_end__lt=invoice.period_end,
        )
        .exclude(pk=invoice.pk)
        .order_by("-period_end", "-issued_at")
        .first()
    )


def _bucket_totals(invoice: Any) -> dict[tuple[Any, str], Decimal]:
    """One bill's charges added up per `(service, kind)` — its stored 4dp sums.

    ⚠ **EVERY LINE LANDS IN EXACTLY ONE BUCKET, AND THAT IS WHAT MAKES THE
    SHARES TIE OUT.** The buckets are a PARTITION of the bill's own lines, so
    the bucket sums add to the bill and the differences of the bucket sums add
    to the difference of the bills — by construction, not by a correction
    applied afterwards. `BR-CWP-046` allows no tolerance, and the way to satisfy
    a rule with no tolerance is to make the arithmetic exact rather than close.

    A bill-level line — a tax, a whole-bill discount — carries `service = None`
    and buckets under that, exactly as `_grouped_lines` files it under
    `taxes_and_fees` on the bill itself.
    """
    totals: dict[tuple[Any, str], Decimal] = {}
    rows = billing_models.InvoiceLine.objects.filter(
        tenant_id=_tenant(), invoice_id=invoice.pk
    ).values_list("service__code", "kind", "amount")
    for service, kind, amount in rows:
        key = (service, kind or "other")
        totals[key] = totals.get(key, Decimal("0")) + Decimal(amount or 0)
    return totals


def _components_for(invoice: Any, prior: Any) -> list[dict[str, Any]]:
    """The lines of *why* — **EVERY REASON, EACH WITH ITS SHARE.**

    ⚠ **THE PRODUCT OWNER RULED THIS AND THE RULING IS WHAT IS BUILT.** From
    the three options put to them (`OQ-CWP-1563`, duplicated as `OQ-CWP-1569`),
    verbatim: *"(a) list every reason with its share"*. So when two things move
    at once — more water AND a price rise — **the screen names both and
    attributes an amount to each**, rather than picking the larger and calling
    it the cause. The decision log of 2026-09-05 carries the ruling and its
    reasoning: *"It is more arithmetic than naming one, and it is the only
    version that survives a customer checking it."*

    ⚠ **THE GRANULARITY IS `(service, kind)`, AND IT IS THE RULING'S OWN WORKED
    EXAMPLE RATHER THAN A CHOICE MADE HERE.** The four lines put to the PO were
    *used more water* · *trash cart charge unchanged* · *a summer discount
    ended* · *lower tax on a smaller sewer share* — a usage bucket, a base
    bucket, a discount bucket and a tax bucket. Nothing in that example splits
    one service's usage into a VOLUME part and a PRICE part, and nothing here
    does either: a cross-term attribution (`Δqty × Δrate` credited to one side
    or the other) is a second finance judgment that was not put and has not been
    made. **`US-CWP-035` §8's other half — *"in what order they are attributed
    when two move at once"* — is answered by there being no order to choose: the
    buckets do not overlap.**

    ⚠ **THE SHARES SUM TO THE MOVEMENT EXACTLY, WITH NO RESIDUE ANYWHERE.** The
    ruling says so in the PO's own terms — *"no residue hidden in a rounding —
    the split is money arithmetic and hard rule 2 governs it like any other"* —
    and `components_tie_out` is the invariant that was built and tested before
    the ruling arrived, waiting for exactly this. The caller gates on it: a
    decomposition that does not tie is NOT SERVED, and the screen states the
    absence rather than showing four numbers that explain nothing.

    ⚠ **A BUCKET PRESENT ON ONLY ONE BILL IS A REASON, NOT AN OMISSION.** A
    summer discount that ended appears on the prior bill and not on this one;
    its share is the whole of what it used to take off. Dropping it would leave
    the column short by exactly the amount a customer is asking about.

    ⚠ **A BUCKET THAT DID NOT MOVE IS STILL LISTED**, at `$0.00`. *Trash cart
    charge unchanged* is one of the PO's four lines: a customer looking for what
    changed is also asking what did NOT, and a service silently absent from the
    list reads as a service that stopped being charged.

    The worked figure the ruling was put on: July `BL-2607-0139` `$138.44`,
    August `BL-2608-0141` `$142.18`, difference **`+$3.74`**.
    """
    now = _bucket_totals(invoice)
    was = _bucket_totals(prior)
    #: ⚠ **THE ORDER IS THIS BILL'S OWN, THEN WHATEVER ONLY THE OLD ONE HAD.**
    #: A customer reads the breakdown beside the bill it explains, so *Water*
    #: before *Sewer* here and there. `sorted` on the codes would put sewer
    #: first on this screen and second everywhere else.
    order: list[tuple[Any, str]] = []
    for key in now:
        order.append(key)
    for key in was:
        if key not in now:
            order.append(key)
    out: list[dict[str, Any]] = []
    for service, kind in order:
        share = now.get((service, kind), Decimal("0")) - was.get((service, kind), Decimal("0"))
        out.append(
            {
                #: A stable identifier for a test and a log, never shown: the
                #: screen words it from `service` and `kind` (B14 rule 35, and
                #: rule 32 — no internal code in customer-facing copy).
                "code": f"{service or 'bill'}_{kind}",
                #: The SERVICE, so the screen can use the word the catalogue
                #: already has for it. `None` is a bill-level charge.
                "service": service,
                "kind": kind,
                "amount": str(share.quantize(Decimal("0.0001"))),
                "amount_display": _display(share),
            }
        )
    return out


def components_tie_out(components: list[dict[str, Any]], *, difference: Any) -> bool:
    """`BR-CWP-046` — the component lines sum **EXACTLY** to the difference.

    ⚠ **NO TOLERANCE, AND THAT IS THE WHOLE STORY** (`US-CWP-035` TC-3, J38 step
    3: *"a tolerance here would defeat the whole story"*). A customer who adds
    the four lines and does not reach the headline has been shown four numbers
    that explain nothing.

    ⚠ **THE COMPARISON IS ON THE DISPLAYED FIGURES**, the ones on the page, and
    not on the 4dp stored ones. Four stored components can sum to the stored
    difference and still print a column that is a cent out — which is exactly
    the failure B4's 2026-08-11 ruling names for the tax base and
    `_charges_by_service` takes the same reading of.

    ⚠ **IT IS CONFIRMED LAW AND SURVIVES THE UNSIGNED DECOMPOSITION.** Whichever
    components finance signs (`OQ-CWP-1563`), this invariant is what they must
    satisfy — which is why it is built and tested now, on the story's own worked
    figures, rather than waiting for the ruling.
    """
    total = sum((money.finalize(Decimal(row["amount"])) for row in components), Decimal("0"))
    return total == money.finalize(Decimal(difference))


def _components_view(invoice: Any, prior: Any, *, difference: Any) -> dict[str, Any]:
    """The breakdown, **or an honest absence with the reason it could not be
    served** — never a set of shares that fails `BR-CWP-046`.

    ⚠ **THE FAILURE PATH IS NOT DEAD CODE AND MUST NOT BE DELETED AS SUCH.**
    It cannot fire on a bill whose stored total equals the sum of its own lines,
    which is every bill this engine writes — and that is precisely why it is
    here: the day it fires, something upstream has drifted, and the screen a
    customer is arguing with is the last place that should be the first to
    show it.
    """
    if not COMPONENTS_SIGNED:
        return {"components": [], "components_available": False,
                "components_blocked_by": "OQ-CWP-1563"}
    components = _components_for(invoice, prior)
    if not components_tie_out(components, difference=difference):
        return {"components": [], "components_available": False,
                "components_blocked_by": "BR-CWP-046"}
    return {"components": components, "components_available": True,
            "components_blocked_by": None}


def bill_comparison_for(
    account_ids: list[Any], *, number: str, months: int = 24
) -> dict[str, Any] | None:
    """`CWP-030` — *Why August cost `$3.74` more*, and what still cannot be said.

    ⚠ **IT IS A VIEW, NOT A SOURCE.** It reads two issued bills and the account's
    stored monthly usage; it writes nothing, caches nothing, and can never
    disagree with the bill it explains, because every figure on it is one of
    those bills' own stored totals.

    ⚠ **THE YEAR COMPARISON REUSES `metering.monthly_usage_reads.usage_payload`**
    — the read the portal reuse map names, the one `CR-030` W3 built and a lane
    missed this morning. *Water used `4,090 → 4,820 gal`* is two points on that
    series; composing it from bill lines here would be that same mistake with
    this file's name on it.

    ⚠ **`months` DEFAULTS TO 24 AND MUST NEVER GO BACK TO 12 (`DEF-CWP-4206`).**
    August 2025 and August 2026 are **thirteen** months apart, so a 12-month
    window cannot hold both ends of the comparison this panel exists to draw.
    `usage_same_month_last_year` says exactly that in its own docstring and
    defaults itself to 24 — and this function shipped declaring `months = 12`
    and passing it straight through, so **`against_last_year` was `[]` on every
    bill on every account** and the whole right-hand column of `CWP-030`'s
    drawing rendered as nothing at all. It was invisible in both directions:
    `LastYearPanel` returns `null` on an empty list, which is CORRECT under
    `BR-CWP-093` (nothing empty ever appears), and the one test that named
    `against_last_year` asserted `== []` on a first bill whose account had no
    usage seeded, so it was legitimately empty there and pinned nothing.
    **Measured on the live clone at the same account and the same bill: 1 row
    at 24 months, 0 rows at 12.** No caller passes this argument, so the
    default is the whole of the behaviour.

    ⚠ **A FIRST BILL OFFERS NO COMPARISON AT ALL** (TC-5) — `compared: false`,
    and NOT a comparison against zero. A `$142.18` bill described as *"$142.18
    more than last month"* is arithmetically true and, to somebody who has just
    moved in, a lie.
    """
    from apps.portal.seams import metering_seam

    invoice = bill_in_set(account_ids, number=number)
    if invoice is None:
        return None
    prior = _prior_bill(invoice)
    if prior is None:
        return {
            "number": invoice.invoice_no,
            "compared": False,
            "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
            "period_end": invoice.period_end.isoformat() if invoice.period_end else None,
            "total_display": _display(invoice.total),
            "against_last_year": [],
        }

    #: PLAIN SUBTRACTION OF TWO STORED TOTALS — not a decomposition, not a new
    #: formula, and not `finance_calc: proposed`. `142.18 − 138.44 = 3.74`.
    #: Rounded ONCE, at display, over the 4dp stored figures (B4).
    difference = Decimal(invoice.total or 0) - Decimal(prior.total or 0)
    #: ⚠ **THE SIGN IS THE ANSWER AND IS NEVER TAKEN AWAY.** TC-4's bill that
    #: went DOWN reads *cost less* with the signs reversed; an absolute value
    #: here would make a refund look like a charge.
    direction = MOVED_UP if difference > 0 else (MOVED_DOWN if difference < 0 else MOVED_NOT_AT_ALL)
    return {
        "number": invoice.invoice_no,
        "compared": True,
        "period_start": invoice.period_start.isoformat() if invoice.period_start else None,
        "period_end": invoice.period_end.isoformat() if invoice.period_end else None,
        "prior_number": prior.invoice_no,
        "prior_period_end": prior.period_end.isoformat() if prior.period_end else None,
        "total_display": _display(invoice.total),
        "prior_total_display": _display(prior.total),
        "difference": str(Decimal(difference).quantize(Decimal("0.0001"))),
        "difference_display": _display(difference),
        "direction": direction,
        #: ⚠ **EMPTY UNTIL FINANCE SIGNS THE DECOMPOSITION** (`OQ-CWP-1563`).
        #: `[]` here is not "the lines are all zero" — the screen reads
        #: `components_available` and states the absence in words (B14 rule 32).
        #: ⚠ **GATED ON THE TIE-OUT, AND THE GATE IS NOT BELT-AND-BRACES.**
        #: `BR-CWP-046` allows NO tolerance (`US-CWP-035` TC-3, J38 step 3:
        #: *"a tolerance here would defeat the whole story"*), and the PO's own
        #: ruling says the shares carry *"no residue hidden in a rounding"*. The
        #: buckets partition the lines so this holds by construction — but a
        #: bill whose stored total does not equal its own lines would break it,
        #: and the honest answer there is the stated absence rather than four
        #: numbers that do not add up to the headline the customer is reading.
        **_components_view(invoice, prior, difference=difference),
        #: AGAINST LAST AUGUST — the stored monthly usage, per service, with its
        #: unit on every point (hard rule 3, held by the read that owns it).
        "against_last_year": metering_seam.usage_same_month_last_year(
            invoice.account_id, period_end=invoice.period_end, months=months
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-031` — THE NUMBER ON THE PAPER, FOR A DOCUMENT ROW (US-CWP-036)
# ═══════════════════════════════════════════════════════════════════════════


def invoice_numbers(invoice_ids: list[Any]) -> dict[str, str]:
    """`{invoice id: BL-2608-0141}` for the ids that HAVE a number.

    ⚠ **AN ID WITH NO NUMBER IS SIMPLY ABSENT FROM THIS MAP, AND THE CALLER
    MUST SAY SO IN WORDS RATHER THAN FALLING BACK TO THE ID** (`DEF-3158`,
    B14 rule 31: *"no Databse ID on screen"*, and a TRUNCATION of one is the
    same breach — the staff bills list read `row.invoice_no ?? row.id.slice(0,
    8)` until 2026-09-02). Rule 31's own answer where no human-facing number
    exists is to say so in words.

    ⚠ **STATUS IS NOT FILTERED HERE, DELIBERATELY.** `bills_for` above filters
    on `BR-CWP-041` because it LISTS bills; this resolves a NAME for a document
    the utility has already sent, and a bill whose status later moved is still
    the bill that went in that envelope. Filtering would blank the reference on
    a corrected original — the one row `BR-CWP-042` insists stays readable.
    """
    ids = [str(one) for one in invoice_ids]
    if not ids:
        return {}
    rows = billing_models.Invoice.objects.filter(
        tenant_id=_tenant(), id__in=ids
    ).values_list("id", "invoice_no")
    return {str(key): number for key, number in rows if number}



def invoice_periods(invoice_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """`{invoice id: {"period_start": …, "period_end": …}}` — WHICH MONTH a
    bill covers, so `CWP-031` can name the document instead of its class.

    ⚠ **THIS EXISTS BECAUSE A LIST OF DOCUMENTS THAT ALL SHARE ONE NAME CANNOT
    BE USED TO FIND A DOCUMENT** (`DEF-CWP-3969`). Every row on the live screen
    read *A letter from us*, and the number underneath is the only thing that
    differed — which asks a customer to know their own bill numbers to find
    their August bill.

    ⚠ **NO STATUS FILTER, FOR `invoice_numbers`' OWN REASON.** This names a
    document the utility has already sent; a bill whose status later moved is
    still the bill that went in that envelope. An id whose bill carries no
    period is ABSENT from the map and the caller falls back to the kind word
    rather than composing a name around a blank.
    """
    ids = [str(one) for one in invoice_ids]
    if not ids:
        return {}
    rows = billing_models.Invoice.objects.filter(
        tenant_id=_tenant(), id__in=ids
    ).values_list("id", "period_start", "period_end")
    return {
        str(key): {"period_start": start.isoformat(), "period_end": end.isoformat()}
        for key, start, end in rows
        if start is not None and end is not None
    }

# CR-068 · `CWP-044` — LEVEL PAY (US-CWP-054)
#
# ⚠ **EVERY FIGURE BELOW IS THE STAFF READ'S, REACHED RATHER THAN REBUILT.**
# `GET budget-billing/{account}/eligibility` has answered exactly this question
# for a clerk since `US-BIL-018`, and the PO's ruling of 2026-09-04 is that the
# portal uses the same one: *"you will find it same set of services, endpoints
# are already available for Accounts"*. So this composes the identical three
# pieces that route composes — `selectors.budget_history_for`,
# `budget.compute_level` and the tenant's own `settings_seam.budget_billing()`
# — and adds no arithmetic of its own. A customer and a clerk reading the same
# account see one level, because there is one implementation of it.
# ═══════════════════════════════════════════════════════════════════════════


def level_pay_position(account_id: Any) -> dict[str, Any]:
    """`CWP-044` — the twelve months, the average, the level, and the month.

    ⚠ **THE ROUNDING IS THE TENANT'S AND THE PORTAL HAS NO RULE OF ITS OWN**
    (`US-CWP-054` TC-2). `$1,501.09 ÷ 12 = $125.0908…` and the level is
    `$125.00` because `level_rounding` says `whole_dollar`; a tenant that
    configured something else would get their own figure from the same call,
    and `compute_level` REFUSES an unknown mode rather than falling through to
    whole dollars.

    ⚠ **NO SETTING IS EVER DEFAULTED HERE.** `settings_seam.budget_billing()`
    refuses when the tenant's settings cannot be read, and that refusal is
    carried as a reason rather than replaced by twelve months and June: *"an
    unreachable `eligibility_months` is not twelve"*. The screen says it cannot
    say, which is `US-CWP-054` TC-3's shape one step earlier.

    ⚠ **`settle_up_month` IS NULL UNTIL A TENANT PICKS ONE**, because
    `settings_families` ratifies no month — *"rule names the parameter,
    ratifies no month"*. TC-6 asks the box to name the tenant's OWN month, and
    a screen hardcoding June would be right for one utility and wrong for the
    rest, silently. Null here means the box says the month is not set.

    ⚠ **AND AN ALREADY-ENROLLED ACCOUNT IS NOT OFFERED ENROLMENT AGAIN**
    (TC-4). `enrolled` carries the account's own copy of the settle-up month,
    which is deliberately a COPY taken at enrolment — a tenant who moves the
    month in September must not move it for an account already mid-year.
    """
    from apps.billing import budget as billing_budget
    from apps.billing import budget_service, selectors as billing_selectors
    from apps.billing import settings_seam as billing_settings
    from apps.billing.exceptions import BillingConfigError, BillingRuleError

    settings: dict[str, Any] = {}
    settings_absent: str | None = None
    try:
        settings = dict(billing_settings.budget_billing())
    except (BillingConfigError, BillingRuleError, KeyError) as unreadable:
        settings_absent = str(unreadable)

    required_months = settings.get("eligibility_months")
    history = billing_selectors.budget_history_for(
        account_id, months=int(required_months) if required_months else 12
    )

    level: str | None = None
    level_absent: str | None = None
    if settings_absent is not None:
        level_absent = settings_absent
    elif history["mixed_currency"]:
        # The staff route raises here. A customer screen does not get to 500,
        # so the same fact is carried as a reason and the offer is withheld.
        level_absent = (
            "this account has been billed in more than one currency, so one "
            "monthly level cannot be computed for it"
        )
    elif required_months is None:
        level_absent = "the tenant's budget-billing settings carry no averaging window"
    elif history["months_of_history"] < int(required_months):
        level_absent = (
            f"{history['months_of_history']}/{int(required_months)} months of billing "
            "history — averaging over a short history would set what the customer "
            "pays for a year off a season rather than a year"
        )
    else:
        try:
            level = str(
                billing_budget.compute_level(
                    trailing_actuals=tuple(Decimal(value) for value in history["actuals"]),
                    months=int(required_months),
                    rounding=str(settings["level_rounding"]),
                )
            )
        except (BillingRuleError, BillingConfigError, ValueError, KeyError) as refused:
            level_absent = str(refused)

    #: The RAW average, before the tenant's rounding — `US-CWP-054` TC-1 shows
    #: both, because *"$125.09 rounded to $125.00"* is the sentence that
    #: explains the level, and a screen given only the level cannot say it.
    #: ⚠ **THE DIVISOR IS THE TENANT'S WINDOW AND NOT `len(actuals)` — THE
    #: SAME TRAP `compute_level` WARNS ABOUT IN ITS OWN DOCSTRING**: *"the two
    #: differ the moment a tenant lowers the window to 9 and a caller hands
    #: over twelve bills anyway; dividing by the list length would quietly
    #: average a different period than the tenant configured."* Dividing by a
    #: different number here would put a `$125.09` on screen that does not
    #: round to the `$125.00` beside it — two figures in one sentence, silently
    #: disagreeing, which is the worst shape a money display can take.
    #:
    #: This is the ONE piece of arithmetic on this path that is not
    #: `apps.billing.budget`'s, and it exists only because that module
    #: publishes the ROUNDED level and not the average `US-CWP-054` TC-1 asks
    #: to show. Same Σ, same divisor, one extra quantize —
    #: `test_us_cwp_054_level_pay.py` asserts it rounds to the level, so a
    #: drift between the two figures goes RED rather than quiet.
    total = sum((Decimal(value) for value in history["actuals"]), Decimal("0"))
    months_counted = len(history["actuals"])
    divisor = int(required_months) if required_months else months_counted
    average = str((total / Decimal(divisor)).quantize(Decimal("0.0001"))) if divisor else None

    #: ⚠ **`CR-085` `CPB-18` — *WHICH* MONTH IS MISSING, NOT JUST HOW MANY.**
    #: The refusal above has always been able to say *8 of 12*, and `CWP-044`
    #: said exactly that. A customer reading it cannot tell whether they simply
    #: have not been with the utility for a year or whether one of their bills
    #: is missing, and can act on neither. The blueprint's done-when is *"offers
    #: a monthly amount … **or says precisely which month is missing**"*, and
    #: this is that half.
    #:
    #: ⚠ **THE LEVEL ITSELF IS NOT OFFERED ON A SHORT HISTORY, AND THAT IS A
    #: SIGNED RULE RATHER THAN A CHOICE MADE HERE.** `eligibility_months` is a
    #: TENANT SETTING (`BR-BIL-017`/`BR-BIL-021`); averaging nine months and
    #: calling it a year would put a figure in front of a customer that no
    #: staff screen and no bill can reproduce — the same argument the blueprint
    #: itself uses to keep `CPB-07` out of scope. See the decision log,
    #: 2026-09-08.
    #:
    #: ⚠ **TWO SHAPES, AND THEY ARE DIFFERENT ANSWERS.** A month before the
    #: account's FIRST bill is *you have not been with us that long*; a month
    #: after it is a genuine GAP in a history that otherwise runs. The screen
    #: says different things about them, so the split is published rather than
    #: left for a screen to work out from two lists.
    missing = [list(pair) for pair in history["missing_months"]]
    first_billed = history["first_billed_month"]
    gaps = (
        [pair for pair in missing if tuple(pair) > first_billed] if first_billed else []
    )
    before_start = (
        [pair for pair in missing if tuple(pair) < first_billed] if first_billed else []
    )

    enrolled = budget_service.status_for(account_id)
    return {
        "months_of_history": history["months_of_history"],
        "required_months": int(required_months) if required_months else None,
        #: Every month of the window with no issued bill, newest first, as
        #: `[year, month]`. Empty for an account that has never been billed —
        #: that account has no history rather than a hole in one.
        "missing_months": missing,
        #: The subset that falls INSIDE the billed history: a real gap.
        "missing_month_gaps": gaps,
        #: The subset that falls BEFORE the first bill: not long enough with us.
        "missing_months_before_first_bill": before_start,
        #: `[year, month]` of the first bill ever issued, or `None`.
        "first_billed_month": list(first_billed) if first_billed else None,
        "trailing_total": str(total.quantize(Decimal("0.0001"))) if months_counted else None,
        "months_counted": months_counted,
        "monthly_average": average,
        "level": level,
        "level_unavailable": level_absent,
        "currency": history["currency"],
        "rounding": settings.get("level_rounding"),
        #: 1–12, or `None` — never 6. See the docstring.
        "settle_up_month": settings.get("settle_up_month"),
        "relevel_cadence_months": settings.get("relevel_cadence_months"),
        "settings_unavailable": settings_absent,
        "enrolled": enrolled is not None,
        "enrolled_level": (
            str(budget_service.effective_level(enrolled)) if enrolled is not None else None
        ),
        "enrolled_settle_up_month": (
            enrolled.settle_up_month if enrolled is not None else None
        ),
        #: The bars `CWP-044`'s chart draws — what was BILLED, newest first out
        #: of the read and reversed here so a chart reads left to right.
        "billed": list(reversed(history["actuals"])),
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave L1 · `CWP-045` — credits on the account (US-CWP-056)
# ═══════════════════════════════════════════════════════════════════════════


def credits_for(account_id: Any) -> list[dict[str, Any]]:
    """`CWP-045`'s right half — every credit note on THIS account.

    ⚠ **THE READ IS `billing`'s OWN AND ALREADY EXISTS.**
    `selectors.account_credit_notes` is `GET /accounts/{id}/credit-notes`
    (`CR-059` CS-37), the same read `CWP-041`'s money list uses for its credit
    rows and the same one the staff Credits tab reads. `12-reuse-map.md`: *"a
    second read of the same facts is a second ANSWER, and the two surfaces are
    a clerk and a customer arguing with each other on the phone."*

    ⚠ **NOTHING IS CACHED HERE AND NOTHING MAY BE** (`BR-CWP-047`,
    `US-CWP-056` TC-3): *"a credit that was real on Tuesday can be spent by
    Thursday."* No memo, no module-level dict, and the edge sends `no-store`.

    ⚠ **THE AMOUNT ARRIVES NEGATIVE AND LEAVES NEGATIVE.**
    `credit_notes.amount <= 0` is a database CHECK added after two writers
    stored opposite signs (`DEF-085`), and `payments_seam._credit_rows` records
    the same. **Nothing here re-signs it and nothing takes an absolute value** —
    a panel that once read `272.30` where a customer owed `222.30` is what two
    writers disagreeing about a sign costs.

    ⚠ **`invoice_no` IS THE BILL IT WAS USED ON, AND `None` IS A HISTORIC ROW**
    rather than *"not used yet"*. `account_credit_notes` normalises a blank
    invoice number to null for exactly that reason — an empty cell reads as
    *there is nothing here* about a document that exists (B14 rule 31).
    """
    from apps.billing import selectors as billing_selectors

    answer = billing_selectors.account_credit_notes(account_id)
    return [
        {
            #: `US-CWP-056` §1 — *what, when, amount, and which bill they were
            #: used on*. `reason` is the WHAT: `BR-CWP-050` asks for it in
            #: plain English, and it is a COLUMN on this table.
            "reason": note.get("reason"),
            "credit_note_no": note.get("credit_note_no"),
            "issued_on": (note.get("issued_at") or "")[:10] or None,
            "amount": note["amount"],
            "currency": note.get("currency"),
            "used_on_bill": note.get("invoice_no"),
        }
        for note in answer.get("credit_notes") or ()
    ]


def bill_facts(account_ids: list[Any], *, number: str) -> dict[str, Any] | None:
    """The seven facts `CWP-055` quotes back at a customer querying a bill, or
    None — `bill_in_set`'s own answer for an unknown number, another login's
    bill and a draft alike (`US-CWP-065`).

    ⚠ **IT IS `_bill_view`, NOT A SECOND PROJECTION.** The number, the period
    and the total a query's sentence names are the ones the bills list already
    shows the same customer; a second read would let the clerk's worklist and
    the screen that raised it disagree about the amount being questioned.
    """
    row = bill_in_set(account_ids, number=number)
    return None if row is None else {**_bill_view(row), "account_id": str(row.account_id)}


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-032` — THE FINAL BILL, AND WHERE THE DEPOSIT COMES BACK
# (US-CWP-037)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **NOT ONE FIGURE ON THIS PATH IS COMPUTED HERE.**
# `apps.billing.final_bill.settle_final_bill` has settled a closing account
# since `US-BIL-011`: it applies the deposit AND its `BR-CUS-057` interest
# FIRST — the order is the rule, because the remainder is what picks the path —
# and then resolves exactly one of refund · collect · payment plan · transfer ·
# write-off. This seam calls it and serves what it answers.
#
# ⚠ **AND CALLING IT IS SAFE FROM A READ, WHICH IS WHY IT IS CALLED RATHER THAN
# COPIED.** `settle` is pure and writes nothing; `settle_account` READS the
# tenant's write-off threshold, the deposit and the landlord link. A second
# implementation on this screen is how the figure a customer reads comes to
# disagree with the figure their account is actually settled on — which
# `US-CWP-037` §7 names as *the defect this story exists to catch*.
#
# ⚠ **IT REFUSES RATHER THAN GUESSING, AND THE REFUSAL IS CARRIED.** A deposit
# whose accrued interest cannot be read stops the settlement BY NAME
# (`deposit_credit_for`: *"a principal-only credit of 150.00 instead of 153.50
# would keep $3.50 of the customer's money on a bill that foots and an account
# nobody will look at again"*). A customer screen does not get to 500, so the
# reason travels and the panel says it cannot say.

#: `bill_type` on the closing bill. One value, named once, so the read and the
#: engine's own `settle_final_bill` guard cannot be spelt differently.
BILL_TYPE_FINAL = "final"


def final_bill_for(account_ids: list[Any], *, today: date) -> dict[str, Any] | None:
    """`CWP-032` — the closing bill and how the deposit settled it, or None.

    `None` means this account has no final bill: it has not moved out, or the
    closing bill is still a draft. **Never an empty settlement**, which a screen
    would draw as *we owe you `$0.00`*.

    ⚠ **`service_charges` AND `charges` ARE TWO DIFFERENT FIGURES AND BOTH ARE
    SERVED.** `service_charges` is the closing bill's own total — *"service to
    17 September, `$63.40`"*, the line `US-CWP-037` §1 draws. `charges` is what
    the deposit is actually applied to, which by the PO's ruling of 2026-08-12
    (`OQ-158`, verbatim *"everything outstanding"*) is that total PLUS anything
    the account already owed. On `US-CWP-037`'s own account they are the same
    number because there are no arrears; on an account with them they are not,
    and a screen given only one of the two would either hide the arrears or
    misname the service charge.
    """
    from apps.billing import final_bill as billing_final_bill
    from apps.billing.exceptions import BillingRuleError

    ids = [str(one) for one in account_ids]
    if not ids:
        return None
    invoice = (
        billing_models.Invoice.objects.filter(
            tenant_id=_tenant(),
            account_id__in=ids,
            bill_type=BILL_TYPE_FINAL,
            status__in=CUSTOMER_VISIBLE_STATUSES,
        )
        .order_by("-service_date", "-issued_at")
        .first()
    )
    if invoice is None:
        return None

    view = _bill_view(invoice)
    try:
        settlement = billing_final_bill.settle_final_bill(invoice)
    except Exception as refused:  # the engine's own named refusal, carried
        return {
            **view,
            "account_id": str(invoice.account_id),
            "service_charges": _money(invoice.total),
            "settlement_unavailable": (
                str(refused) if isinstance(refused, BillingRuleError) else type(refused).__name__
            ),
            "deposit": None,
            "settled": False,
        }

    deposit = settlement.deposit
    return {
        **view,
        "account_id": str(invoice.account_id),
        "service_charges": _money(invoice.total),
        #: What the deposit was applied to — the bill plus anything outstanding.
        "charges": _money(settlement.charges),
        "settlement_unavailable": None,
        #: ⚠ **ABSENT, NOT ZERO, ON AN ACCOUNT WITH NO DEPOSIT** (`US-CWP-037`
        #: TC-6). `$0.00` held reads as *we took nothing from you*, which is a
        #: different sentence from *there is nothing here* — the same line
        #: `CWP-065`'s panel already draws.
        "deposit": (
            {
                "held": _money(deposit.principal),
                "interest": _money(deposit.interest),
                "total": _money(deposit.total),
                "taken_on": deposit.received_on.isoformat() if deposit.received_on else None,
                "currency": deposit.currency or None,
            }
            if deposit.exists
            else None
        ),
        #: ⚠ **SIGNED, AND THE SCREEN RENDERS THE SIGN THE SERVER SENT.**
        #: Negative is money owed BACK. The screen words it — *we owe you* — and
        #: takes no absolute value anywhere.
        "remainder": _money(settlement.remainder),
        #: `BR-CWP-048` — a negative final balance is a REFUND and never a
        #: carried credit, because there is no next bill to carry it to. The
        #: engine's own path, not this seam's reading of the sign.
        "path": settlement.path,
        "path_is_automatic": settlement.automatic,
        "settled": settlement.settled,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-066` — WHERE YOUR LEVEL PAY STANDS (US-CWP-055)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **`CWP-044` IS THE JOINING SCREEN AND THIS IS THE STANDING ONE, AND
# NEITHER MAY CARRY A SECOND ARITHMETIC.** `level_pay_position` above answers
# *what would I pay if I joined* — twelve months, the average, the rounded
# level. This answers *what am I paying and where do I stand*, and every figure
# in it is a column `apps.billing.budget_service` already maintains:
# `effective_level` (the override if there is one, else the computed level),
# `variance_balance` (the running total of the append-only events), and the
# account's own copy of the settle-up month.
#
# ⚠ **THE VARIANCE IS READ AND NOT RE-DERIVED, AND `recompute_balance` IS THE
# REASON THAT IS SAFE.** `AccountBudgetStatus.variance_balance` is a CACHE and
# `account_budget_events` is the truth — the model says so in its own words —
# but `budget_service.recompute_balance` exists precisely so the two can be
# asserted equal, and its own test does. A portal read that summed the events
# itself would be a third answer to a question that already has two agreeing
# ones.

#: `US-CWP-055` TC-7 — *ahead* and *behind* IN WORDS, never a bare signed
#: number. The DIRECTION travels as one of these and the catalogue writes the
#: sentence; `variance_balance` positive means the levels collected more than
#: the customer used, which is the model's own comment on the column.
AHEAD = "ahead"
BEHIND = "behind"
LEVEL = "level"


def level_pay_standing(account_id: Any) -> dict[str, Any] | None:
    """`CWP-066` — the level, the variance, the settle-up, and every re-levelling.

    `None` when the account is not enrolled — `US-CWP-055` TC-5 routes that
    customer to `CWP-044` rather than drawing an empty standing screen.

    ⚠ **`override` IS SHOWN AND ITS REASON IS NOT** (TC-4). `BR-BIL-017` keeps
    both columns because the ±30% bound is measured against the COMPUTED level,
    so losing it would make the next override unvalidatable — but
    `level_override_reason` is the utility's own note about a customer, in the
    utility's words, and `BR-CWP-052`'s posture is that the surest way to keep
    such a field off a customer's screen is for the code that builds the body
    never to select it. **It is not in this dict.**

    ⚠ **EACH RE-LEVELLING CARRIES WHAT ACTUALLY HAPPENED** (TC-3): the actual
    that year, the movement, and the balance after — the three columns the
    event row already stores, so a year-old row reproduces what the customer
    was shown without re-deriving it from a level that has since moved.
    """
    from apps.billing import budget as billing_budget
    from apps.billing import budget_service, models as billing_module_models

    status = budget_service.status_for(account_id)
    if status is None:
        return None

    level = budget_service.effective_level(status)
    balance = Decimal(status.variance_balance or 0)
    events = list(
        budget_service.event_queryset()
        .filter(budget_status=status)
        .exclude(event=billing_module_models.BUDGET_EVENT_BILLED)
        .order_by("-occurred_on", "-created_at")
    )
    return {
        "level": _money(level),
        #: ⚠ **THE COMPUTED LEVEL TRAVELS BESIDE THE EFFECTIVE ONE ONLY WHEN
        #: THEY DIFFER**, which is exactly when there is an override to state.
        #: Serving both always would put two figures on a screen that means one.
        "override": _money(status.level_override) if status.level_override is not None else None,
        "computed_level": (
            _money(status.level) if status.level_override is not None else None
        ),
        "currency": status.currency or None,
        #: The SIZE, always positive, with the direction beside it — TC-7's
        #: *ahead* and *behind* in words. The catalogue writes the sentence.
        "variance": _money(abs(balance)),
        "variance_direction": AHEAD if balance > 0 else (BEHIND if balance < 0 else LEVEL),
        #: 1–12, or `None`. The ACCOUNT's own copy, taken at enrolment — a
        #: tenant that moves its settle-up month in September must not move it
        #: for an account already mid-year (`BR-TEN-043`).
        "settle_up_month": status.settle_up_month,
        "enrolled_on": status.enrolled_on.isoformat() if status.enrolled_on else None,
        "last_leveled_at": (
            status.last_leveled_at.isoformat() if status.last_leveled_at else None
        ),
        "status": status.status,
        "off_budget": status.status == billing_budget.STATUS_OFF_BUDGET,
        #: ⚠ **NO ROW ID ON ANY EVENT** (B14 rule 31). A re-levelling is
        #: identified by the date it happened, which is what a customer would
        #: read out on the telephone.
        "changes": [
            {
                "event": row.event,
                "on": row.occurred_on.isoformat() if row.occurred_on else None,
                "level": _money(row.level) if row.level is not None else None,
                "actual": _money(row.actual) if row.actual is not None else None,
                "movement": _money(row.movement),
                "balance_after": _money(row.balance_after),
                "currency": row.currency or None,
            }
            for row in events
        ],
    }


def level_pay_months(account_id: Any) -> list[dict[str, Any]]:
    """What was PAID against what was USED, month by month — `CWP-066`'s chart
    and its CSV (`US-CWP-055` TC-8).

    ⚠ **ONE ROW PER BILLED MONTH, OUT OF THE EVENTS THE PROGRAMME ALREADY
    WRITES.** `budget_service` records a `billed` event per invoice carrying the
    LEVEL in force that month and the ACTUAL that was used — the two figures the
    chart draws — so nothing here re-reads invoices or re-derives a level that
    has since been re-levelled (`BR-TEN-043`: the level in force when each bill
    issued governs it).
    """
    from apps.billing import budget_service, models as billing_module_models

    status = budget_service.status_for(account_id)
    if status is None:
        return []
    rows = (
        budget_service.event_queryset()
        .filter(budget_status=status, event=billing_module_models.BUDGET_EVENT_BILLED)
        .order_by("occurred_on", "created_at")
    )
    return [
        {
            "month": row.occurred_on.isoformat()[:7] if row.occurred_on else None,
            "paid": _money(row.level) if row.level is not None else None,
            "used": _money(row.actual) if row.actual is not None else None,
            "currency": row.currency or None,
        }
        for row in rows
    ]


def closing_reading_for(readings: list[dict[str, Any]], *, moved_out_on: date | None) -> dict[str, Any] | None:
    """The reading the final bill was cut on, out of the readings list.

    ⚠ **CHOSEN FROM THE LIST THE CUSTOMER CAN ALREADY SEE, NEVER RE-QUERIED**
    (`CWP-034` serves the same rows). A second query could return a reading
    that is not on the readings screen, and then the closing figure on one
    screen would not appear on the other.

    ⚠ **ON OR BEFORE THE MOVE-OUT DAY, NEWEST FIRST** — `BR-CUS-056` bills
    THROUGH the move day, so a reading taken that day is the closing one and a
    reading taken after it belongs to whoever moved in.
    """
    if moved_out_on is None:
        return None
    for row in readings:
        taken = row.get("taken_on")
        if taken and date.fromisoformat(taken) <= moved_out_on:
            return row
    return None
