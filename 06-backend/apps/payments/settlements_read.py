# ── Trace ──────────────────────────────────────────────
# Change:   CR-139-BRC07 — the payments blueprint's phase 5, the READ half of
#           `P5.7`. Drawing: `05-prototype/06 Payments Page Blueprint.pdf`
#           p069–p072 (§03 tab 5), read AS IMAGES at scale 2.0 (B14 rule 42).
#           ⚠ **THE DRAWING'S OWN *To build* ROW NAMES `GET /settlements` AND
#           NO `CR-139-BRC07` §4 TASK ROW OWNED IT** — `DEF-PAY-6286`. The
#           board has a writer (`P5.1`–`P5.3`), a schema (`P5.4`–`P5.6`) and
#           two screens (`P5.7`), and the read between them belonged to
#           nobody. Built here so the screens are WIRED rather than dead UI.
# Story:    no story — 5·1 Settlements and 5·2 Settlement are `S-NEW · PAY-P`.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping; every queryset starts from
#           `tenant_id`) · hard rule 2 (money is a DECIMAL STRING, four places,
#           beside its `CHAR(3)` code) · `NFR-3` (server pagination on every
#           list — no slice is materialised here) · `NFR-5` (no caps) ·
#           BR-SHL-011 (the list URL grammar) · BR-TEN-043 (nothing under
#           `apps/payments/` reads a wall clock — the CALLER names the day) ·
#           BR-TEN-042 (one currency per tenant) · B14 rule 31 (a payout is
#           named by the provider's own reference, never by its uuid)
# Tests:    06-backend/tests/test_cr139_p5_7_settlements_read.py
# Impacts:  apps/payments/settlements_api.py (the three doors) ·
#           apps/payments/settlement_models.py (the two tables) ·
#           apps/payments/settlements.awaiting_settlement_filter (COMPOSED
#           here, never re-derived)
# ───────────────────────────────────────────────────────
"""The two Settlements screens' whole read — **a payout, and what is inside it.**

    GET /settlements                    5·1  the list, one row per payout
    GET /settlements/{code}             5·2  one payout and its four figures
    GET /settlements/{code}/members     5·2  the payments inside it, paged

⚠ **NOTHING HERE WRITES.** p072's step 3 is titled *"What you can do to it —
Nothing, and that is the design"*, verbatim: *"It is a statement of fact from a
provider. There is nothing to approve, nothing to edit and nothing to cancel —
if a payout is wrong, the provider issues another one."* So this module has no
`create`, no `update` and no audit row: **hard rule 7 is about a money ACTION,
and a read is not one.**

⚠ **A PAYOUT IS RESOLVED BY THE PROVIDER'S OWN REFERENCE (`code`).** p071 draws
the address as `/:tenant/payments/settlements/STL-260921-CARD`, and B14 rule 31
puts no database id in the most visible field a screen has. `settlement_models`
already records why `code` is the provider's string and not a number we mint —
it is half the idempotency key and it is what the clerk is reading off the
processor's statement.

════════════════════════════════════════════════════════════════════════════
⚠ *AWAITING SETTLEMENT* IS A FACT ABOUT THE **TENDER**, AND THAT DECISION IS
THIS LANE'S — DECISION LOG 2026-09-23
════════════════════════════════════════════════════════════════════════════
`settlements.awaiting_settlement_filter()` answers *"this payment is in no
payout"* and its own docstring hands the rest of the question to the screen,
verbatim: *"A counter payment, a lockbox row and a posted cheque are awaiting
settlement **forever**, because nobody pays those out to us — which is why the
screen that draws this state draws THREE (in a payout · awaiting one · never
will be) and not two, and why the third one is a fact about the TENDER."*

**So the tile needs a narrowing and the repo did not have one.** It is decided
here rather than asked (CLAUDE.md hard-won law 13: *a judgment call recorded in
the decision log with its reasoning is the deliverable; a question is the
failure to make one*), and it is decided as narrowly as it can be:

  **A payment is AWAITING SETTLEMENT when a provider is the one who will pay it
  out — `card`, `ach`, `tap_pay` — and it is in no payout yet.**

Everything else is **never settled**, not *awaiting*: cash, a cheque and a money
order are physical and reach the bank in a deposit batch; a wire and a lockbox
row are credited by the BANK and there is no processor in the middle.

**The worked figure put in the decision log:** a utility that took `$1,204.80`
on cards across 31 payments yesterday and `$9,860.00` in cash and cheques at the
counter reads **`$1,204.80 · 31 payments`** on this tile. Counting the drawer
money too would read `$11,064.80` and would never fall, because nobody is ever
going to pay the utility out for its own till.

⚠ **`tap_pay` IS IN THAT LIST AND IT IS NOT A NEW TENDER.** `CR-139-BRC07`
`P5.11`, PO ruling 2026-09-23: *"user will manually use it and add reference #
and Tap & pay options in system"* — **a tap is a card** taken on somebody
else's terminal, so the processor pays it out exactly like any other card.

════════════════════════════════════════════════════════════════════════════
⚠ THE TWO DAY-SHAPED TILES ANSWER **null** WITHOUT AN `as_of`
════════════════════════════════════════════════════════════════════════════
`BR-TEN-043` and gate `G6` forbid a wall clock anywhere under `apps/payments/`,
because a server clock decides a business day in the SERVER's timezone. *Paid
out today* and *Fees this month* are claims about a DAY, so a caller that does
not say which day it means gets a stated absence and `totals_unavailable`
beside it — the shape `counter_list_totals` already ships, and `DEF-127` is
what `?? 0` costs: *"a figure nobody filled rendering as a figure somebody
counted."*
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Count, DecimalField, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from apps.payments import models, settlements
from apps.payments.exceptions import PaymentRuleError
from apps.payments.settlement_models import (
    SETTLEMENT_MATCHED,
    SETTLEMENT_RECEIVED,
    Settlement,
    SettlementMember,
)
from core.pagination import ListParams
from core.tenancy import current_tenant_id

FOUR_PLACES = Decimal("0.0001")
ZERO = Decimal("0")

#: BR-SHL-011's `sort` vocabulary for 5·1. Every one is a COLUMN the drawing
#: draws a ⇅ on (p070: SETTLEMENT · PROVIDER · PAID OUT · GROSS · NET · BANK),
#: plus the member count the PAYMENTS column shows.
SETTLEMENT_SORTS: tuple[str, ...] = (
    "paid_out_at",
    "code",
    "provider",
    "gross",
    "net",
    "payments",
    "status",
)
DEFAULT_SETTLEMENT_SORT = "paid_out_at"

#: The two the drawing evidences, and no third. p070's ② is the PROVIDER
#: column (*"one, two or three per utility"*) and its fourth tile is
#: **UNMATCHED**, which is the `status`/`bank_line` pair the BANK column shows.
#: A filter the drawing does not draw is a control B14 rule 41 did not ask for.
SETTLEMENT_FILTERS: tuple[str, ...] = ("state", "provider")

#: 5·2's member list. p071 draws ⇅ on PAYMENT # · TAKEN · GROSS.
MEMBER_SORTS: tuple[str, ...] = ("payment_no", "taken", "gross", "fee")
DEFAULT_MEMBER_SORT = "taken"
MEMBER_FILTERS: tuple[str, ...] = ()

#: ⚠ **THE TENDERS A PROVIDER PAYS OUT.** See the module docstring — this is
#: the narrowing `awaiting_settlement_filter()` deliberately does not make, and
#: it is a tender classification rather than a rule about time.
PROVIDER_SETTLED_TENDERS: tuple[str, ...] = ("card", "ach", "tap_pay")

_SORT_COLUMNS: dict[str, str] = {
    "paid_out_at": "paid_out_at",
    "code": "code",
    "provider": "provider",
    "gross": "gross",
    "net": "net",
    "payments": "member_count",
    "status": "status",
}

_MEMBER_SORT_COLUMNS: dict[str, str] = {
    "payment_no": "payment__payment_no",
    "taken": "payment__posted_at",
    "gross": "gross",
    "fee": "fee",
}


def _tenant_id() -> Any:
    """Hard rule 1 — every queryset in this module starts from this value."""
    return current_tenant_id()


def _money(value: Any) -> str:
    """A `NUMERIC(18,4)` column as its exact decimal STRING.

    Hard rule 2: money never travels as a JSON number and never as cents. The
    quantize is the COLUMN's four places, not a rounding decision — B4 owns
    those, at finalisation and display.
    """
    return str(Decimal(value or 0).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP))


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _tenant_currency() -> str:
    """BR-TEN-042 — one currency per tenant, and it REFUSES rather than
    defaulting to `USD`: a figure stated in a currency nobody configured is
    half a money fact. `counters._tenant_currency` takes the same line."""
    from apps.payments import settings_seam

    return settings_seam.tenant_currency()


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    """Midnight-to-midnight for `day` in the UTILITY's own zone (`OQ-153`)."""
    from apps.payments import settings_seam

    zone = settings_seam.tenant_timezone()
    start = datetime.combine(day, time.min, tzinfo=zone)
    end = datetime.combine(date.fromordinal(day.toordinal() + 1), time.min, tzinfo=zone)
    return start, end


def _month_bounds(day: date) -> tuple[datetime, datetime]:
    """The calendar month `day` falls in, in the utility's own zone."""
    from apps.payments import settings_seam

    zone = settings_seam.tenant_timezone()
    first = day.replace(day=1)
    following = (
        date(first.year + 1, 1, 1) if first.month == 12 else date(first.year, first.month + 1, 1)
    )
    return (
        datetime.combine(first, time.min, tzinfo=zone),
        datetime.combine(following, time.min, tzinfo=zone),
    )


def _sum(queryset: QuerySet, column: str) -> Decimal:
    """`SUM(column)` in SQL, never `sum()` over materialised rows (`NFR-5`)."""
    total = queryset.aggregate(
        total=Coalesce(
            Sum(column), ZERO, output_field=DecimalField(max_digits=18, decimal_places=4)
        )
    )["total"]
    return Decimal(total or 0)


# ═══════════════════════════════════════════════════════════════════════════
# 5·1 · THE LIST
# ═══════════════════════════════════════════════════════════════════════════
def settlement_list_queryset(params: ListParams) -> QuerySet:
    """`GET /settlements` — *"The bank shows one credit. Which payments is it?"*

    ⚠ **PAGED AND SORTED IN SQL.** The caller hands this straight to
    `StandardPagination`, which adds `LIMIT`/`OFFSET`; nothing is sliced here.
    Four lists in this module sort in Python and name a 3,000-connection
    utility as their excuse (`DEF-PAY-4221`) — correct at T7 and 13× short of
    T5. This is not a fifth.

    `q` matches the PAYOUT'S REFERENCE and the PROVIDER, which are the two
    things a clerk can read — off our screen or off the processor's own
    statement. It deliberately matches no id (B14 rule 31: an id is not
    something anybody could have read in order to search for it).
    """
    queryset = (
        Settlement.objects.filter(tenant_id=_tenant_id())
        .select_related("bank_line")
        .annotate(member_count=Count("members"))
    )

    state = (params.filters.get("state") or "").strip().lower()
    if state == SETTLEMENT_MATCHED:
        queryset = queryset.filter(status=SETTLEMENT_MATCHED)
    elif state == SETTLEMENT_RECEIVED:
        queryset = queryset.filter(status=SETTLEMENT_RECEIVED)

    provider = (params.filters.get("provider") or "").strip()
    if provider:
        queryset = queryset.filter(provider=provider)

    if params.q:
        queryset = queryset.filter(Q(code__icontains=params.q) | Q(provider__icontains=params.q))

    column = _SORT_COLUMNS.get(params.sort or DEFAULT_SETTLEMENT_SORT, "paid_out_at")
    order = column if params.dir == "asc" else f"-{column}"
    # A stable tie-break, so page 2 of two payouts stamped the same second is
    # not a different two rows each time it is asked for.
    return queryset.order_by(order, "-created_at", "id")


def settlement_rows(page: Any) -> list[dict[str, Any]]:
    """p070's eight columns, and nothing a clerk cannot read.

    ⚠ **NO `id` ON ANY ROW** — B14 rule 31. The row's identity is `code`, which
    is also the address segment 5·2 opens at, so a screen cannot accidentally
    render the key it would otherwise have had to carry.
    """
    return [
        {
            "code": row.code,
            "provider": row.provider,
            "paid_out_at": _iso(row.paid_out_at),
            "payments": getattr(row, "member_count", 0),
            "gross": _money(row.gross),
            "fees": _money(row.fees),
            "net": _money(row.net),
            "currency": row.currency,
            "status": row.status,
            # ⚠ THE BANK CREDIT'S OWN REFERENCE, NEVER `bank_line_id`. `null`
            # is the honest value while the payout is `received`, and the CHECK
            # constraint `ck_settlements_matched_has_line` means the two can
            # never disagree.
            "bank_reference": _bank_reference(row.bank_line),
        }
        for row in page
    ]


def _bank_reference(line: Any) -> str | None:
    """What a person would call this bank line — `BRM-2609-0044` on p071.

    ⚠ **`bank_lines.reference` IS NULLABLE AND A NULL STAYS A NULL.** B14 rule
    31: where no human-facing reference exists the field says so in words on
    the screen, and the primary key is not a second-best answer to put there.
    """
    if line is None:
        return None
    return str(line.reference) if line.reference else None


def awaiting_settlement_queryset() -> QuerySet:
    """The payments a provider still owes the utility — see the module docstring.

    ⚠ **IT COMPOSES `settlements.awaiting_settlement_filter()` RATHER THAN
    RE-DERIVING IT.** That `Q` is the published answer to *"is this payment in
    a payout?"*, and it reads `settlement_members` because that is now the
    ONLY record of the fact: `payments.settlement_id` was dropped by
    `payments/0044` on the PO's ruling of 2026-09-24 (`OQ-PAY-12608` option
    (b)) after it turned out that hard rule 4's trigger froze it in every
    status. **This function did not change when the column went** — it never
    read it. Writing the membership test again here would be the *two answers
    to one question* shape this phase keeps filing.
    """
    return models.Payment.objects.filter(tenant_id=_tenant_id()).filter(
        settlements.awaiting_settlement_filter(),
        method__code__in=PROVIDER_SETTLED_TENDERS,
    )


def settlement_list_totals(queryset: QuerySet, *, as_of: date | None) -> dict[str, Any]:
    """p069–p070's four tiles, folded over the WHOLE filtered set.

    **PAID OUT TODAY · AWAITING SETTLEMENT · FEES THIS MONTH · UNMATCHED.**

    ⚠ **NEVER OVER ONE PAGE.** A figure folded over fifty rows is a different
    figure wearing the same label, and this list is paginated by law.

    ⚠ **TWO OF THE FOUR ARE null WITHOUT `as_of`**, with
    `totals_unavailable: "as_of_missing"` beside them. See the module docstring
    — `BR-TEN-043`, and `DEF-127` is what a `?? 0` costs on a money tile.

    ⚠ **THE FIGURES p069 DRAWS ARE ILLUSTRATIONS** (B14 rule 37) — `$12,841.03`,
    `$1,204.80`, `$418.22`, `0` are a demo tenant's and nothing here is built
    to reach them.
    """
    currency = _tenant_currency()
    awaiting = awaiting_settlement_queryset()
    unmatched = queryset.filter(status=SETTLEMENT_RECEIVED)

    totals: dict[str, Any] = {
        "currency": currency,
        # The distinct providers in the filtered set — the PROVIDER filter's
        # options and the first tile's detail line both read it, so the screen
        # does not need a second call to populate a two-item dropdown.
        "providers": sorted(
            {value for value in queryset.values_list("provider", flat=True).distinct() if value}
        ),
        "awaiting_settlement": _money(_sum(awaiting, "amount")),
        "awaiting_settlement_payments": awaiting.count(),
        "unmatched": unmatched.count(),
        "paid_out_today": None,
        "paid_out_today_providers": None,
        "fees_this_month": None,
        # ⚠ A STRING, NOT A FLOAT. It is rendered and never arithmetic'd, and a
        # percentage is six decimals by hard rule 2 wherever it is stored.
        "fees_share_of_takings": None,
        "totals_unavailable": None,
    }
    if as_of is None:
        totals["totals_unavailable"] = "as_of_missing"
        return totals

    day_start, day_end = _day_bounds(as_of)
    today = queryset.filter(paid_out_at__gte=day_start, paid_out_at__lt=day_end)
    totals["paid_out_today"] = _money(_sum(today, "net"))
    totals["paid_out_today_providers"] = today.values("provider").distinct().count()

    month_start, month_end = _month_bounds(as_of)
    month = queryset.filter(paid_out_at__gte=month_start, paid_out_at__lt=month_end)
    fees = _sum(month, "fees")
    gross = _sum(month, "gross")
    totals["fees_this_month"] = _money(fees)
    # ⚠ **THE DENOMINATOR IS WHAT THE PROVIDERS COLLECTED, AND THE DRAWING'S
    # SUB-LINE SAYS *"of card takings"*.** The same drawing's own table lists an
    # ACH payout, so the two halves of ONE drawing describe one fact two ways —
    # exactly what B14 rule 37 is for. The SHAPE they agree on is a percentage
    # under FEES THIS MONTH; the screen's word for the denominator is
    # *provider takings*, because a share that included ACH and called itself
    # *card* would be a false sentence on a money tile.
    totals["fees_share_of_takings"] = (
        None
        if gross <= ZERO
        else str((fees / gross * Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
    )
    return totals


# ═══════════════════════════════════════════════════════════════════════════
# 5·2 · ONE PAYOUT
# ═══════════════════════════════════════════════════════════════════════════
def settlement_by_code(code: str) -> Settlement:
    """The payout a clerk named, resolved by the PROVIDER'S reference.

    ⚠ **REFUSES RATHER THAN ANSWERING THE FIRST OF SEVERAL.** `code` is unique
    per `(tenant, provider)`, so two processors can in principle issue the same
    reference. That is refused BY NAME with the instruction to open it from the
    list, which is `counters._session_by_ref`'s posture one noun along.

    ⚠ **AN UNKNOWN REFERENCE IS *ABSENT*, NEVER *FORBIDDEN*.** BR-TEN-003 /
    HR-1: a 403 would confirm that the row exists in somebody else's utility.
    """
    reference = (code or "").strip()
    if not reference:
        raise PaymentRuleError(
            "no payout reference was given, so there is nothing to open.",
            br_ref="BR-SHL-011",
        )
    found = list(Settlement.objects.filter(tenant_id=_tenant_id(), code=reference)[:2])
    if not found:
        raise PaymentRuleError(
            f"no payout is on file with the reference {reference!r}. Check it against the "
            "provider's own statement, or open it from the Settlements list.",
            br_ref="BR-SHL-020",
        )
    if len(found) > 1:
        raise PaymentRuleError(
            f"two providers have both used the reference {reference!r}. Open the one you "
            "meant from the Settlements list, where each row names its provider.",
            br_ref="BR-SHL-020",
        )
    return found[0]


def settlement_detail(code: str) -> dict[str, Any]:
    """5·2's head and its four figures — GROSS · FEES · NET · BANK.

    p071 ①: *"Fees — the difference between what a customer paid and what we
    banked"*. ②: *"One credit — which is the whole reason a batch number is
    needed"*.

    ⚠ **THE FOUR FIGURES ARE THE PROVIDER'S, CHECKED AND NOT RE-DERIVED.**
    `ck_settlements_net_ties` already refuses a row where `gross - fees != net`,
    so this read prints the stored three rather than computing a fourth that
    could never disagree with itself (`settlement_models` records why).

    ⚠ **THE FEE SHARE IS THIS PAYOUT'S OWN**, `fees / gross`, and it is the one
    percentage on the screen the drawing evidences — p071's `1.91%` under FEES.
    """
    payout = settlement_by_code(code)
    gross = Decimal(payout.gross or 0)
    fees = Decimal(payout.fees or 0)
    return {
        "code": payout.code,
        "provider": payout.provider,
        "paid_out_at": _iso(payout.paid_out_at),
        "payments": SettlementMember.objects.filter(
            tenant_id=_tenant_id(), settlement_id=payout.pk
        ).count(),
        "gross": _money(gross),
        "fees": _money(fees),
        "net": _money(payout.net),
        "currency": payout.currency,
        "status": payout.status,
        "bank_reference": _bank_reference(payout.bank_line),
        "fee_share": (
            None
            if gross <= ZERO
            else str(
                (fees / gross * Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            )
        ),
    }


def member_list_queryset(payout: Settlement, params: ListParams) -> QuerySet:
    """*"Which 46 payments made up this $8,047.30?"* — paged in SQL like the rest.

    `q` matches all three things p071's placeholder promises — *"Search
    account, customer or reference…"*.

    ⚠ **THE CUSTOMER LEG GOES THROUGH CUSTOMERS' OWN PUBLISHED SEARCH, NEVER
    THROUGH A JOIN.** A name lives in the customers module and payments reads
    one through `selectors._account_ids_by_customer_name`, which is the one
    place in this module that already goes looking for one (B2 §2 — a
    cross-module write is forbidden and a cross-module JOIN is not this
    module's to invent). Dropping the leg instead would leave a placeholder
    promising a search that silently matched nothing, which B14 rule 19's own
    amendment names as the thing no check can see.
    """
    queryset = SettlementMember.objects.filter(
        tenant_id=_tenant_id(), settlement_id=payout.pk
    ).select_related("payment", "payment__account")

    if params.q:
        from apps.payments.selectors import _account_ids_by_customer_name

        matches = (
            Q(payment__account__account_no__icontains=params.q)
            | Q(payment__confirmation__icontains=params.q)
            | Q(payment__payment_no__icontains=params.q)
        )
        by_name = _account_ids_by_customer_name(params.q)
        if by_name:
            matches = matches | Q(payment__account_id__in=by_name)
        queryset = queryset.filter(matches)

    column = _MEMBER_SORT_COLUMNS.get(params.sort or DEFAULT_MEMBER_SORT, "payment__posted_at")
    order = column if params.dir == "asc" else f"-{column}"
    return queryset.order_by(order, "id")


def member_rows(page: Any) -> list[dict[str, Any]]:
    """p071's seven columns — PAYMENT # · TAKEN · ACCOUNT · CUSTOMER ·
    REFERENCE · GROSS · FEE.

    ⚠ **`gross` IS THE PAYMENT'S OWN AMOUNT AND IT IS READ FROM THE MEMBER
    ROW**, which `ingest_payout` already refused to write unless the two agree.
    A $100.00 card payment with a $2.90 fee is a $100.00 payment and a $2.90
    expense — the money-correctness heart of this phase, stated on the column
    that would carry the error.
    """
    # ⚠ **THE PAYER'S NAME COMES THROUGH CUSTOMERS' OWN PUBLISHED READ (B1),
    # AND `selectors` IS WHERE PAYMENTS ALREADY KEEPS THAT CALL.** Reusing it
    # rather than resolving the seam a second time is the *two answers to one
    # question* risk this phase keeps naming — and its refusal behaviour is
    # part of the contract: it RAISES when customers has published nothing,
    # because a null renders as *"no customer name recorded"*, which is a
    # different and false statement.
    from apps.payments.selectors import _customer_name

    rows: list[dict[str, Any]] = []
    for member in page:
        payment = member.payment
        rows.append(
            {
                # B14 rule 31 — the PMT- series number a clerk reads out, and a
                # stated absence where a legacy import could not reach it.
                "payment_no": payment.payment_no,
                "taken_at": _iso(payment.posted_at),
                "account_no": payment.account.account_no,
                # Record links (PO 2026-10-19): the account number OPENS the
                # account, whose address is its id. Never a visible value.
                "account_id": str(payment.account_id),
                "customer_name": _customer_name(payment.account),
                # What a person read off a device or a statement — the cheque
                # or authorisation number. One of the exactly three columns
                # `POST /payments/{id}/correct-reference` may fix.
                "reference": payment.confirmation,
                "gross": _money(member.gross),
                "fee": _money(member.fee),
                "currency": payment.currency,
            }
        )
    return rows


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-139-BRC07 §4 row `P5.7` · blueprint `05-prototype/06 Payments Page Blueprint.pdf` p069–p072 read as IMAGES at 2.0 (B14 rule 42) · DEF-PAY-6286 (the read no task row owned) · decision log 2026-09-23 "AWAITING SETTLEMENT IS A FACT ABOUT THE TENDER"
# generated: 2026-09-23 by LANE P5-SCREENS
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_cr139_p5_7_settlements_read.py
# exceptions: (1) no payment row names its payout — `OQ-PAY-12608` CLOSED 2026-09-24 option (b) dropped `payments.settlement_id` (`payments/0044`) and the membership table is the record, exactly as `test_cr139_p5_6_the_third_state_is_answered_from_the_membership` asserts · (2) the member list's CUSTOMER search leg goes through customers' published `account_list` rather than a join, so it is one extra read per search and no cross-module join (B2 §2)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
