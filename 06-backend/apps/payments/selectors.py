# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-004 (the S33 Record-payments ledger — its IS-5 capability
#           row, its "Applied to" column and its filter totals) · US-PAY-001
#           (the shape `POST /accounts/{id}/payments` answers with)
#           Screens: S33 · S22 · S35 · S21 (the Payments tab is this same list
#           scoped by `f.account_id`)
# Rules:    BR-PAY-002 (this surface WRITES NOTHING — every action routes to
#           its owning story) · BR-PAY-012 (purpose is a column and a filter) ·
#           BR-PAY-021 (posting date AND clearing date are both first-class
#           columns and both filterable) · BR-PAY-024 (the receipt number this
#           list cannot serve, and why) · BR-PAY-025 (the deposit batch, same) ·
#           BR-PAY-026 (method is a tenant LOOKUP — the vocabulary is LIVE) ·
#           BR-PAY-027 (S33 = the full IS-5 capability row) · BR-REP-006
#           (filters enumerate live vocabularies, never hardcoded) ·
#           BR-SHL-011 (q/sort/dir/page/per/f.<name>) · BR-TEN-042 (one
#           currency per tenant — why a filter total can be summed at all) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money is a decimal
#           string beside its CHAR(3), never a number on the wire)
# Tests:    06-backend/tests/test_us_pay_004_payments_api.py
# Impacts:  apps/payments/api.py (its only caller) · apps/payments/billing_seam
#           (the invoice NUMBERS the "Applied to" column prints) ·
#           07-frontend/src/api/endpoints.ts (`PaymentRow` is this row, field
#           for field — a rename on either side is a broken screen)
# ───────────────────────────────────────────────────────
"""The payments READ layer — the S33 ledger, and the shape a record answers with.

This module reads and never writes. BR-PAY-002 is explicit that the list mutates
nothing and that every row action routes to its owning story (reverse →
US-PAY-010, reapply → US-PAY-008, receipt → US-PAY-025, refund → US-PAY-011),
and none of those stories exists — so this surface serves rows and no verb.

════════════════════════════════════════════════════════════════════════════
WHAT THE ROW CANNOT SAY, SERVED NULL UNDER ITS OWN NAME
════════════════════════════════════════════════════════════════════════════
Two of the IS-5 "available columns" have no source in this deployment. Both are
served as `null` rather than dropped from the payload or filled with something
plausible, so the SCREEN can say why the cell is empty instead of a clerk
wondering whether the row failed to load:

  * `receipt_no` — BR-PAY-024 auto-queues a receipt on every cleared payment
    (RCT- series). That queue write is US-PAY-025 / EP-PAY-07 and does not
    exist; a number here would name a receipt nobody ever sent.
  * `deposit_batch_id` — `deposit_batches` is EP-PAY-06's table and is not
    built. `payments.deposit_batch_id` exists as a deferred-FK column (B11 F-3)
    and nothing writes it, so it is always null and that is the truth.

`customer_name` is read through customers' OWN published function (B1) and is
null only when no contact has been recorded. If customers publishes nothing the
read REFUSES rather than answering null — "no name recorded" and "the name could
not be read" are different statements and the second one must not degrade into
the first (hard-won law 2, and billing's `_customer_name` takes the same line).

════════════════════════════════════════════════════════════════════════════
THE "APPLIED TO" COLUMN IS THIS MODULE'S OWN TABLE, JOINED TO BILLING'S NUMBERS
════════════════════════════════════════════════════════════════════════════
The prototype's S33 row prints `BL-2607-018204` under "Applied to", and
US-PAY-004 §5 maps it to *"read-model over `allocations` → invoice numbers;
multi-allocation rows list all"*. The rows are payments' own; the NUMBERS are
billing's, and they are read through `billing_seam` by name rather than by
walking the cross-module FK into billing's ORM (B1). When billing publishes no
read the entry still carries its `invoice_id` and its amount, with
`invoice_number: null` — the money it met is never hidden because its label
could not be resolved.

════════════════════════════════════════════════════════════════════════════
THE FILTER TOTAL, AND THE ONE CASE IT REFUSES TO STATE
════════════════════════════════════════════════════════════════════════════
US-PAY-004 TC-1 asks for a *"totals row per current filter"*. Σ of stored
NUMERIC(18,6) values is EXACT — a comparison and an addition of already-finalized
figures — so no rounding event is introduced here (B4 rounds at finalization and
at display, and this is neither).

It is refused in two cases rather than guessed:

  * NO ROWS — the count is 0 and the money member is null. "$0.00 received"
    and "nothing matched this filter" are different statements about a day's
    takings, and only the second is true.
  * MORE THAN ONE CURRENCY in the filtered set. BR-TEN-042 locks a tenant to
    one currency once a financial record exists, so this cannot happen; if it
    ever does, adding a CAD row to a USD total is inventing money, and the
    total says it could not be stated instead.

⚠ **THE PARAGRAPH THAT STOOD HERE UNTIL 2026-09-02 SAID A CREDIT ROW "CANNOT
ARISE TODAY", AND IT HAD STOPPED BEING TRUE (`DEF-3207`, hard-won law 1).** It
read: *"The write path writes `payment` rows only, so the question cannot arise
today; if a signed row ever appears, the total refuses on the same principle and
names it."* **`CR-059` task 22 shipped the writer on 2026-09-02**, so the branch
went live the same day — and the refusal it describes turned out to be worse than
the question it was avoiding: **one $25.00 credit blanked the day's takings for
the whole filtered list.**

**WHAT IS TRUE NOW: the money member is the day's CASH and it EXCLUDES credits
and adjustments** (`CR-059` CS-35: *"the day's cash total must EXCLUDE credits and
adjustments, or it will not tie to the drawer"*). The O-4 residue is untouched and
still unresolved — whether a credit's sign lives on `amount` is nobody's to decide
here — but **excluding a row is correct under either reading of its sign, where
summing it is correct under only one.** So the excluded rows are COUNTED and never
summed, and `excluded_count` lets the screen state the absence instead of leaving
a clerk to assume the figure covered everything.

Three cases still refuse a money figure and each names itself: no rows at all, more
than one currency, and a filter in which every row is a credit or an adjustment —
where `$0.00` would read as *"we took nothing"* rather than *"nothing here was
cash"*.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any

from django.db.models import F, Q, QuerySet, Sum

from core import errors
from core import tenancy as core_tenancy
from core.pagination import ListParams, parse_list_params

from apps.payments import bankrec_models as bankrec
from apps.payments import balance_rule, billing_seam, metering_seam, models, settings_seam

SIX_PLACES = Decimal("0.000001")  # DB-3 storage precision — NOT money rounding

# ── The US-PAY-004 capability row (BR-PAY-027), as the parser reads it ──────
#: The sortable set from EP-PAY-01's capability matrix, verbatim: "posted_at,
#: cleared_at, amount, account, status". `account` is the screen's word; the
#: column is `account__account_no`, and the mapping lives once, in `_ORDER_BY`.
PAYMENT_SORTS: tuple[str, ...] = ("posted_at", "cleared_at", "amount", "account", "status")
PAYMENT_DEFAULT_SORT = "posted_at"
#: "Default sort: posted_at desc" (capability matrix). BE-05 defaults an absent
#: `dir` to asc, which on a growing ledger puts the OLDEST payment on page 1 —
#: so the screen's own default is applied here, in one place, rather than being
#: left to whichever caller remembers to send `dir=desc`.
PAYMENT_DEFAULT_DIRECTION = "desc"

#: The capability row's filters — "type, method, status, purpose, posted/cleared
#: date range" — plus 11b §2.6's account scope (the S21 Payments tab is this
#: same list with `f.account_id`). BE-05 ignores anything outside this set.
PAYMENT_FILTERS: tuple[str, ...] = (
    "type",
    "method",
    "status",
    "purpose",
    "account_id",
    "posted_from",
    "posted_to",
    "cleared_from",
    "cleared_to",
    # ── The blueprint's §03 2·1 Source filter (`DEF-PAY-6212`) ──────────────
    # ⚠ **THE FILTER TAKES THE STORED WORD, NOT THE DRAWN ONE.** The drawing
    # offers `Digital | Counter | Post`; the column holds `webhook | entry |
    # import`, and `models.PAYMENT_ORIGINS` records the PO's 2026-09-22 ruling
    # that the stored words do not move. So the chip's LABEL is the catalogue's
    # and its VALUE is the column's — the same split `method` already makes
    # (the code, never the row's uuid).
    "origin",
    # ── The blueprint's §03 2·1 Batch filter, note ③ (`CR-136-BRC07` `P2.8`) ─
    # *"Batch filter · one batch at a time"*, and the page's own header badge
    # reads **GAINS 2 COLUMNS · 2 FILTERS · 1 BUTTON** — the Source filter
    # landed with the columns and this is the second (`DEF-PAY-6227`).
    #
    # ⚠ **IT TAKES THE CODE A CLERK READS, WHICH IS WHAT THE CELL SHOWS.** A
    # deposit batch's `DEP-` code or an import run's number — never either
    # table's uuid (B14 rule 31), and never the drawn `CTR-260921-DW`, which is
    # an illustration (B14 rule 37).
    "batch",
    # ── `DEF-PAY-10732` · L2-11 (PO 2026-10-30, *"Rest we will fix"*) ───────
    # The counter screen (3·2) sends `f.counter=<till code>` and, until this
    # line, BE-05 dropped the undeclared name in silence — so a till opened a
    # minute ago listed EVERY payment the utility had ever taken. It takes the
    # CODE the page header shows (`CTR-261021-BS-4`), never the session uuid
    # (B14 rule 31), and resolves it to `counters.session_payments_q`, the one
    # definition every drawer figure already reads.
    "counter",
)

#: screen sort key -> (column, is_nullable). Nullable columns get an explicit
#: NULLS placement so the order is identical on PostgreSQL and on the sqlite
#: test tier — the two vendors disagree, and a page-1 order that changes with
#: the database is a defect and not a detail (IS-2).
_ORDER_BY: dict[str, tuple[str, bool]] = {
    "posted_at": ("posted_at", False),
    "cleared_at": ("cleared_at", True),
    "amount": ("amount", False),
    "account": ("account__account_no", True),
    "status": ("status", False),
}


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — no query is built without `app.tenant_id`.

    Refuses rather than defaulting: on PostgreSQL RLS would block the read, and
    on the SQLite developer tier it would list whatever tenant happened to be
    next, and "whichever database you happen to be running" is not a security
    model.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """A neighbour's published callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _decimal_str(value: Decimal | None) -> str | None:
    """The NUMERIC(18,6) value as its exact decimal STRING ("292.870000").

    CLAUDE.md rule 2: money never travels as a number and never as cents — it
    travels as the stored decimal beside its CHAR(3) code, and the frontend
    renders it without parsing or re-rounding it (`MoneyCell`). The quantize is
    the COLUMN's six places (DB-3), not money rounding — that is B4's, at
    finalization and display.
    """
    if value is None:
        return None
    return str(Decimal(value).quantize(SIX_PLACES, rounding=ROUND_HALF_UP))


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _day_bounds(raw: Any) -> datetime | None:
    """A `YYYY-MM-DD` filter bound as midnight in the UTILITY's own zone.

    **DEF-094's sweep, and this one is a FILTER rather than a stored value —
    which is why it was left in UTC and why leaving it there stopped being
    defensible.** The docstring used to say *"UTC, not the tenant's clock — a
    filter bound, from which no stored value and no money figure derives"*. True
    as far as it went, and beside the point once the WRITE half moved: US-PAY-005
    §1 requires every summary figure to tie to the list a clerk can open, so a
    tile bucketed in the tenant's day beside a list filtered in UTC's day is two
    screens disagreeing about the same money — the exact shape BR-PAY-027 calls
    *"counts tie to lists EXACTLY"*.

    **Worked, on a Houston utility:** a payment recorded at **22 Aug 20:00
    Central** is `2026-08-23T01:00Z`. The S32 tile now counts it on the 22nd;
    a UTC filter bound would have hidden it from the 22 August list the tile
    links to, and the clerk would be looking for money the screen insists exists.

    A malformed bound is still IGNORED rather than an error (BR-SHL-011: a list
    URL never 4xxs over its params). An unreadable SEAM is not a malformed param
    and is not swallowed here — see `settings_seam.tenant_timezone`.
    """
    if raw in (None, ""):
        return None
    try:
        parsed = date.fromisoformat(str(raw))
    except (TypeError, ValueError):
        return None
    return datetime.combine(parsed, time.min, tzinfo=settings_seam.tenant_timezone())


def _customer_name(account: Any) -> str | None:
    """The payer's name, through customers' OWN published read (B1).

    REFUSES when customers has published nothing, rather than answering None:
    the screen renders a null as "no customer name recorded", which is a
    different statement from "the name could not be read" and is false whenever
    a contact exists.
    """
    read = _resolve("customers", "primary_contact_name")
    if read is None:  # pragma: no cover - customers publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="payments.customer_name_unavailable")
    return read(account)


def _account_ids_by_customer_name(term: str) -> list[Any]:
    """IS-3's third search leg — the accounts whose CUSTOMER name matches.

    Customers' published `account_list` search is deliberately WIDER than this
    one (BR-CUS-053 also matches service address and meter #), so its rows are
    narrowed to the ones whose `name` actually contains the term: a payment on
    an account that merely shares an address with the search term is not a hit
    on "customer", and returning it would silently redefine the capability row
    the screen shows.
    """
    read = _resolve("customers", "account_list")
    if read is None:  # pragma: no cover - customers publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="payments.customer_name_unavailable")
    needle = term.lower()
    return [
        row["id"] for row in read(ListParams(q=term)) if needle in (row.get("name") or "").lower()
    ]


# ── The list ────────────────────────────────────────────────────────────────


def list_params(query_params: Any) -> ListParams:
    """BR-SHL-011's params for S33, with the capability row's own defaults.

    Wrapped here rather than in `api.py` so the vocabulary AND the ratified
    default direction live in one place. BE-05 has no notion of a default
    direction — an absent `dir` means asc — and this screen's default is posting
    date DESC, so an absent `dir` takes the screen's and an explicit one is
    honoured verbatim.
    """
    params = parse_list_params(
        query_params,
        allowed_sorts=PAYMENT_SORTS,
        default_sort=PAYMENT_DEFAULT_SORT,
        allowed_filters=PAYMENT_FILTERS,
    )
    if "dir" in query_params:
        return params
    return ListParams(
        q=params.q,
        sort=params.sort,
        dir=PAYMENT_DEFAULT_DIRECTION,
        page=params.page,
        per=params.per,
        filters=params.filters,
    )


def payment_queryset() -> QuerySet:
    """Every payment of the CURRENT tenant, and only those (hard rule 1).

    The tenant filter is written explicitly and RLS FORCE is the second,
    independent guarantee — neither is trusted to be the only one (the app half
    is what protects the SQLite developer tier, which has no policies at all).

    `select_related` + `prefetch_related` are not decoration: the row prints the
    account number, the customer's name, the method's name and every allocation,
    and a 50-row page would otherwise be 200 queries.
    """
    return (
        models.Payment.objects.filter(tenant_id=_tenant_id())
        # CR-059 CS-32 (task 40): the move marks read the ORIGINAL payment and
        # its account through `moved_from_payment`, and the destination leg
        # through the same column backwards. Both are joined here for the reason
        # the docstring above already gives — a 50-row page would otherwise ask
        # the database twice per row for two strings.
        .select_related("account", "method", "moved_from_payment", "moved_from_payment__account")
        .prefetch_related("allocations", "moved_to", "moved_to__account")
    )


def _account_ids_at_address(term: str) -> Any:
    """`CR-089` `PUJ-52` — the accounts AT an address, as a LAZY queryset.

    ⚠ **THE ADDRESS IS NOT A PAYMENTS COLUMN AND MUST NOT BECOME ONE.** Hard
    rule 8 keeps an address on `premises` and nowhere else; a payment reaches
    one by walking *payment → account → property*, and `g85_one_address_home.py`
    fails a fourth home. So this asks customers, which owns the account, and
    customers asks metering, which owns the property.

    ⚠ **LAZY, AND THAT IS THE DIFFERENCE FROM THE LEG ABOVE.**
    `_account_ids_by_customer_name` builds customers' whole `account_list` —
    every matching row, with its ledger, ageing and premise reads — and then
    filters it in PYTHON. This hands `Q(account_id__in=…)` an unevaluated
    queryset, which Django renders as a nested subquery: the address leg adds
    **no round trip at all** and the page is still cut in SQL (`NFR-3`).

    REFUSES if the read is unpublished, for the same reason the name leg does:
    skipping it returns FEWER payments with a 200, and a clerk who searches a
    street and sees nothing concludes no money was taken there.
    """
    read = _resolve("customers", "account_ids_at_matching_address")
    if read is None:  # pragma: no cover - customers publishes it
        raise errors.SysError(errors.SYS_INTERNAL, message_key="payments.address_search_unavailable")
    return read(term)


def _apply_search(qs: QuerySet, term: str) -> QuerySet:
    """IS-3 / the capability row: account #, customer, confirmation #, address.

    Server-side, because the list is paginated in the database: a client-side
    filter over page 1 would search 50 of 7,000 payments and report that as the
    answer.

    ⚠ **THE FOURTH LEG IS THE ADDRESS AND IT ARRIVED WITH `CR-089` `PUJ-52`.**
    The PO's sentence is *"you will ahve changes when Premises, Units, Assets,
    Accounts, Bills, Payments are search by address"*. Before it, typing *301
    Mill Pond Ln* into this box returned NOTHING while nine payments had been
    taken against the six accounts standing there — and the request had already
    paid for the join, because the customer-name leg builds customers' address-
    aware `account_list` and throws its address matches away.
    """
    if term == "":
        return qs
    from django.db.models import Q

    # ⚠ **THE PAYMENT'S OWN NUMBER AND ITS MEMO ARE LEGS TOO** (`DEF-PAY-10732`
    # L2-11, `DEF-PAY-10734` L2-03, PO 2026-10-30). A clerk reads
    # `PY-261021-1325` off a receipt and typed it here to find nothing; an
    # agency's or landlord's note lives in the memo and found nothing either.
    matches = (
        Q(account__account_no__icontains=term)
        | Q(confirmation__icontains=term)
        | Q(payment_no__icontains=term)
        | Q(memo__icontains=term)
    )
    by_name = _account_ids_by_customer_name(term)
    if by_name:
        matches = matches | Q(account_id__in=by_name)
    matches = matches | Q(account_id__in=_account_ids_at_address(term))
    return qs.filter(matches)


def _filter_by_batch(qs: QuerySet, code: Any) -> QuerySet:
    """§03 2·1 note ③ — *"Batch filter · one batch at a time"*.

    Takes the CODE the BATCH cell shows, which is one of two things, so this
    asks both populations and unions them:

      · a deposit batch's own `DEP-` code — this module's table, no seam;
      · an import run's NUMBER — metering's table, through the seam.

    ⚠ **IT REPEATS `payment_batch_labels`'s PRECEDENCE, AND THAT IS THE WHOLE
    CARE IN THIS FUNCTION.** An imported cheque that has since been BANKED has
    a run AND a deposit batch, and the cell shows the deposit — *"the later,
    more specific fact"*. A filter that ignored that would answer a run number
    with rows whose own cells say `DEP-26-0041`, and a list that contradicts
    its own column is worse than a list that finds nothing. So the import leg
    excludes anything already banked.

    ⚠ **AN UNKNOWN CODE MATCHES NOTHING AND DOES NOT RAISE** — BR-SHL-011, a
    list URL never 4xxs over its params, the same posture `origin` takes above.
    `Q(pk__in=[])` is the empty answer and needs no branch of its own.

    ⚠ **BOTH LEGS ARE ONE `IN` EACH, RESOLVED BEFORE THE PAGE** (`NFR-3`). The
    deposit leg is bounded by *one batch*, and the import leg by `BR-MET-038`'s
    10,000-row file cap.
    """
    wanted = str(code or "").strip()
    if not wanted:
        return qs
    banked = list(
        bankrec.DepositBatch.objects.filter(
            tenant_id=_tenant_id(), code=wanted
        ).values_list("pk", flat=True)
    )
    imported = metering_seam.payments_created_by_run_no(wanted)
    matches = Q(deposit_batch_id__in=banked) if banked else Q(pk__in=[])
    if imported:
        matches = matches | Q(pk__in=imported, deposit_batch_id__isnull=True)
    return qs.filter(matches)


def _filter_by_counter(qs: QuerySet, code: Any) -> QuerySet:
    """`DEF-PAY-10732` · L2-11 — only the payments THIS till took, by its code.

    ⚠ **AN UNKNOWN CODE MATCHES NOTHING** (BR-SHL-011, the `batch` posture). A
    new till with no payments must list NONE, and an unknown code answering
    with the unfiltered list is exactly the defect this closes.

    ⚠ **IT REUSES `session_payments_q` RATHER THAN RESTATING IT.** A payment
    belongs to a till when it names the till OR banks in one of its batches —
    two records of one fact — and the drawer totals already read that clause.
    A second definition here could disagree with the till's own figures.
    Imported lazily: `counters` is a sibling with its own import graph.
    """
    from apps.payments import counter_session_models as tills
    from apps.payments.counters import session_payments_q

    wanted = str(code or "").strip()
    if not wanted:
        return qs
    session = tills.CounterSession.objects.filter(tenant_id=_tenant_id(), code=wanted).first()
    if session is None:
        return qs.none()
    return qs.filter(session_payments_q(session))


def _apply_filters(qs: QuerySet, filters: dict[str, str]) -> QuerySet:
    """The declared filter set. An undeclared name never reaches here (BE-05)."""
    if "type" in filters:
        qs = qs.filter(type=filters["type"])
    if "status" in filters:
        qs = qs.filter(status=filters["status"])
    if "purpose" in filters:
        qs = qs.filter(purpose=filters["purpose"])
    if "method" in filters:
        # BR-PAY-026: the CODE, because that is what the tenant's lookup row is
        # named by and what the Record form submits — never the row's uuid.
        qs = qs.filter(method__code=filters["method"])
    if "origin" in filters:
        # ⚠ **AN UNKNOWN WORD MATCHES NOTHING AND DOES NOT RAISE** (BR-SHL-011:
        # a list URL never 4xxs over its params). It is filtered against the
        # column directly rather than validated against `PAYMENT_ORIGINS`
        # first, because the two answers are identical — an origin outside the
        # tuple cannot be stored, `ck_payments_origin` refuses it by name — and
        # a second copy of the vocabulary here is a second place for it to rot.
        qs = qs.filter(origin=filters["origin"])
    if "batch" in filters:
        qs = _filter_by_batch(qs, filters["batch"])
    if "counter" in filters:
        qs = _filter_by_counter(qs, filters["counter"])
    account_id = filters.get("account_id")
    if account_id:
        # The S21 Payments tab. A malformed id matches nothing rather than
        # raising: BR-SHL-011 says a list URL never errors over its params.
        try:
            qs = qs.filter(account_id=account_id)
        except (ValueError, TypeError):  # pragma: no cover - defensive
            return qs.none()
    posted_from = _day_bounds(filters.get("posted_from"))
    if posted_from is not None:
        qs = qs.filter(posted_at__gte=posted_from)
    posted_to = _day_bounds(filters.get("posted_to"))
    if posted_to is not None:
        # INCLUSIVE of the named day — a chip reading "to Aug 22" that dropped
        # every payment posted during Aug 22 would be read as a data gap.
        qs = qs.filter(posted_at__lt=_next_day(posted_to))
    cleared_from = _day_bounds(filters.get("cleared_from"))
    if cleared_from is not None:
        # A payment that has NOT cleared is excluded by the NULL, and that is
        # the right answer: "not cleared yet" is not "cleared outside the
        # window", and BR-PAY-021 makes the two different facts.
        qs = qs.filter(cleared_at__gte=cleared_from)
    cleared_to = _day_bounds(filters.get("cleared_to"))
    if cleared_to is not None:
        qs = qs.filter(cleared_at__lt=_next_day(cleared_to))
    return qs


def _next_day(moment: datetime) -> datetime:
    from datetime import timedelta

    return moment + timedelta(days=1)


def _apply_order(qs: QuerySet, params: ListParams) -> QuerySet:
    column, nullable = _ORDER_BY[params.sort if params.sort in _ORDER_BY else PAYMENT_DEFAULT_SORT]
    descending = params.dir == "desc"
    expression = F(column)
    if descending:
        ordered = expression.desc(nulls_last=True) if nullable else expression.desc()
    else:
        ordered = expression.asc(nulls_last=True) if nullable else expression.asc()
    return qs.order_by(ordered, "-id")  # `id` is the stable tiebreak (IS-2)


def payment_list_queryset(params: ListParams) -> QuerySet:
    """The S33 list, searched/filtered/ordered — paginated by the caller.

    Returns a QUERYSET rather than rows so BE-05 pages in the DATABASE: only the
    rows on screen are serialized, and a tenant with 7,000 payments does not
    build 7,000 dicts to show 50.
    """
    qs = _apply_search(payment_queryset(), (params.q or "").strip())
    qs = _apply_filters(qs, params.filters)
    return _apply_order(qs, params)


def allocation_entries(payment: models.Payment) -> list[dict[str, Any]]:
    """The prototype's "Applied to" cell — every bill this payment met.

    ALL of them, in the order they were written: a payment that settled two
    bills shows two, because showing the first would understate what the money
    did. The NUMBER comes from billing through the seam; when billing publishes
    no read the entry keeps its id and its amount and states a null number,
    rather than the money disappearing because its label could not be resolved.
    """
    rows = list(payment.allocations.all())
    numbers = billing_seam.invoice_numbers([row.invoice_id for row in rows])
    return [
        {
            "invoice_id": str(row.invoice_id),
            "invoice_number": numbers.get(row.invoice_id),
            "amount": _decimal_str(row.amount),
        }
        for row in sorted(rows, key=lambda row: (row.created_at, str(row.pk)))
    ]


# ══ THE BLUEPRINT'S §03 2·1 BATCH COLUMN ════════════════════════════════════
#
# The drawing gives every payment a batch and draws three shapes of one —
# `CTR-260921-DW` for a counter till, `IMP-260921-LBX` for a posted file and
# `STL-2609-CARD` for a card settlement. **Those three strings are drawn
# figures and B14 rule 37 makes a drawn figure an ILLUSTRATION**, so what is
# served is the code the product actually mints, not the one on the page.
#
# ⚠ **TWO OF THE THREE EXIST TODAY AND THE THIRD DOES NOT, AND THAT IS STATED
# RATHER THAN FAKED.** A banked payment carries `deposit_batch_id`, written
# once by `reconciliation.cut_deposit_batches`, and the batch's own `code` is
# `DEP-260922-0001`. An imported payment is named by the run that made it
# (`DEF-PAY-6213`). **A card taken but not yet settled has no batch at all**:
# the drawing's own gap note ⑦ says so — *"'every payment carries a batch id'
# and 'the digital batch id arrives at settlement' cannot both be true at the
# moment a card is taken"* — and there is no settlement run in the product.
# That row reads as a stated absence, and the words for it are the catalogue's.
#
#: What a batch label IS, so the screen can word the absence differently from
#: the value. `deposit` is a banked till or cut; `import` is a run.
BATCH_KIND_DEPOSIT = "deposit"
BATCH_KIND_IMPORT = "import"


def payment_batch_labels(payments: Any) -> dict[str, dict[str, Any]]:
    """`payment id` → `{"batch_ref", "batch_kind"}`, in TWO queries for a page.

    ⚠ **BULK, BECAUSE THE CALLER IS A PAGED LIST** (`NFR-3`). `payment_row`
    accepts this map rather than looking a row up itself: a per-row lookup on a
    50-row page is 100 queries, and a list that pages in SQL so that one page
    costs one page would have spent the saving here.

    ⚠ **A PAYMENT IN BOTH POPULATIONS READS AS ITS DEPOSIT BATCH.** An imported
    cheque that has since been banked has a run AND a deposit batch, and the
    deposit is the later, more specific fact — it is the one a bookkeeper is
    holding a bank statement against. The run is still reachable; it is simply
    not what this cell says.
    """
    rows = list(payments or [])
    if not rows:
        return {}
    labels: dict[str, dict[str, Any]] = {}

    # The run that made it — metering's own published read, through the seam.
    runs = metering_seam.runs_that_created([row.pk for row in rows])
    for payment_id, run in runs.items():
        run_no = run.get("run_no")
        if run_no:
            labels[payment_id] = {"batch_ref": str(run_no), "batch_kind": BATCH_KIND_IMPORT}

    # The deposit batch it was banked in — this module's own table, so no seam.
    batch_ids = {row.deposit_batch_id for row in rows if row.deposit_batch_id is not None}
    if batch_ids:
        codes = dict(
            bankrec.DepositBatch.objects.filter(
                tenant_id=_tenant_id(), pk__in=batch_ids
            ).values_list("pk", "code")
        )
        for row in rows:
            code = codes.get(row.deposit_batch_id)
            if code:
                # `batch_id` — record links (PO 2026-10-19): the screen opens
                # the batch by its id, the address the deposit pages already
                # use. It builds an href only and is never shown (B14 rule 31).
                labels[str(row.pk)] = {
                    "batch_ref": code,
                    "batch_kind": BATCH_KIND_DEPOSIT,
                    "batch_id": str(row.deposit_batch_id),
                }
    return labels


def payment_rows(payments: Any) -> list[dict[str, Any]]:
    """A PAGE of S33 rows — the form every list caller should use.

    It exists so the batch lookup happens ONCE per page rather than once per
    row. `payment_row` still serves a single payment for the callers that have
    one (the portal's own timeline builds its rows one at a time).
    """
    rows = list(payments or [])
    labels = payment_batch_labels(rows)
    return [payment_row(row, batch_labels=labels) for row in rows]


def payment_row(
    payment: models.Payment, *, batch_labels: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    """One S33 row. Every key is `PaymentRow` in the frontend's endpoints.ts.

    `batch_labels` is the page's precomputed map (`payment_batch_labels`).
    **An absent map means this row's batch is looked up on its own**, which is
    correct and costs two queries — never silently null, because a null here
    would tell a clerk this payment belongs to no batch when it may belong to
    one.
    """
    entries = allocation_entries(payment)
    applied = sum((row.amount for row in payment.allocations.all()), Decimal("0"))
    labels = batch_labels if batch_labels is not None else payment_batch_labels([payment])
    batch = labels.get(str(payment.pk)) or {}
    return {
        "id": str(payment.pk),
        # BR-TEN-035: minted at record. Nullable in the schema because a future
        # import path that cannot reach the series must fail loudly rather than
        # collide, so the screen still renders a stated absence for a null.
        "payment_no": payment.payment_no,
        "account_id": str(payment.account_id),
        "account_no": payment.account.account_no,
        "customer_name": _customer_name(payment.account),
        "type": payment.type,
        # BR-PAY-026: the tenant lookup's CODE and its NAME. Null when the row
        # carries no instrument — a credit or an adjustment has none, and B2
        # leaves the column nullable for exactly that.
        "method": payment.method.code if payment.method_id else None,
        "method_name": payment.method.name if payment.method_id else None,
        "confirmation": payment.confirmation,
        "memo": payment.memo,
        # LBX-04 (PO 2026-10-30) — on a REVERSING row its memo IS the bank's
        # own words (*"Bank memo: NSF"*); null on every other row, so a
        # payment's own memo is never relabelled as the bank's.
        "bank_memo": payment.memo if payment.reverses_payment_id else None,
        "amount": _decimal_str(payment.amount),
        "currency": payment.currency,
        "status": payment.status,
        "purpose": payment.purpose,
        # BR-PAY-021 — BOTH, always. A null `cleared_at` is `processing`: the
        # money has not arrived, which is a state and not a missing value.
        "posted_at": _iso(payment.posted_at),
        "cleared_at": _iso(payment.cleared_at),
        "applied_to": entries,
        "applied_total": _decimal_str(applied),
        # ── §03 2·1 ④ SOURCE and ⑤ BATCH — `DEF-PAY-6212` and `DEF-PAY-6213` ─
        #
        # ⛔ **BOTH FACTS WERE IN THE DATABASE AND NEITHER REACHED A SCREEN.**
        # `payments/0030` landed `origin` with its CHECK on 2026-09-22 and no
        # reader followed it; the run link has been on `import_run_rows` since
        # the eighth import target landed. Hard-won law 2 in its plainest form,
        # twice on one row.
        #
        # ⚠ **THE STORED WORD TRAVELS, NOT THE DRAWN ONE.** `entry · webhook ·
        # import` are what the column holds and what `ck_payments_origin`
        # enforces; `Counter · Digital · Post` are LABELS and live in the
        # eleven catalogues with every other label. `models.PAYMENT_ORIGINS`
        # records the PO's 2026-09-22 ruling and the reason the words did not
        # move — `entry` is written for both legs of an internal transfer and
        # for a bounce, neither of which is money handed over at a counter.
        #
        # A null `origin` is a row written before `payments/0029` whose source
        # could not be observed. It is served as null and the screen states it,
        # rather than being guessed into one of the three.
        "origin": payment.origin,
        # PO 2026-10-30 Q6 — the store network a payments file named
        # (`Hy-Vee`), so the Source cell reads *Store · Hy-Vee*. Null on
        # every other payment, which keeps its origin's word.
        "store_network": getattr(payment, "store_network", None),
        # The batch a clerk reads — a deposit code or an import run number —
        # and WHICH of the two it is, so the screen can word an absence without
        # guessing. Both null on a payment in neither population.
        "batch_ref": batch.get("batch_ref"),
        "batch_kind": batch.get("batch_kind"),
        # Record links (PO 2026-10-19): the deposit batch's id, so the `DEP-`
        # code can open its page. Null for an import run or no batch.
        "batch_id": batch.get("batch_id"),
        # ⚠ **`deposit_batch_id` STAYS NULL HERE AND THE REASON IS NO LONGER
        # THE ONE THIS COMMENT USED TO GIVE — `DEF-PAY-6216`.** It read *"always
        # null: nothing writes the column"*, and that has been false since
        # `reconciliation.cut_deposit_batches` shipped: the cut writes
        # `deposit_batch_id` on every member payment, write-once. What replaces
        # the false claim is a RULE rather than a fix in passing: B14 rule 31
        # says no database id is ever the visible value of a field, and this one
        # is a bare uuid with no screen behind it. The fact a clerk needs — the
        # batch's own `DEP-` code — now travels as `batch_ref` above. The id is
        # filed for whoever contracts a deposit-batch route to link to.
        "deposit_batch_id": None,
        # Served null under its contracted name — see the module docstring.
        "receipt_no": None,
        # ── CR-059 CS-30 (task 57) — A CHEQUE'S OWN STATE, ON THE WIRE ───────
        # `payments/0017` landed the three columns on 2026-09-03 and NOTHING
        # served them, so `GET /cheques` answered three lists of rows in which
        # no cheque fact appeared: P7 could name a cheque's date, its drawer
        # bank and its hold and read none of them back. Hard-won law 2 at the
        # selector layer — the column exists, the list exists, and the fact a
        # bookkeeper opens the screen for was not in the payload.
        #
        # All three are NULL on every payment that is not a structured cheque,
        # which is a STATE and not a missing value: the screen renders a stated
        # absence, exactly as `cleared_at` does for `processing`.
        "cheque_date": _date_str(payment.cheque_date),
        "drawer_bank": payment.drawer_bank,
        "bankable_from": _date_str(payment.bankable_from),
        # ── CR-059 CS-32 (task 40) — THE MOVE, FROM BOTH ENDS ───────────────
        # CS-32's screen note asks that **both** accounts' Payments tabs show
        # the move AS A MOVE — *"moved to 2608-0155"*, *"moved from 2608-0141"*
        # — *"rather than as an unexplained reversal on one screen and an
        # unexplained payment on the other."* The link exists as
        # `payments.moved_from_payment_id` and was served by nothing, so both
        # halves of that sentence were unreachable from a screen.
        #
        # ⚠ **NUMBERS, NEVER IDS** (B14 rule 31). The row carries the other
        # account's `account_no` and the other payment's `PMT-` number; a link
        # whose label could not be read states that rather than printing a
        # database id.
        **_move_marks(payment),
    }


def _date_str(value: Any) -> str | None:
    """A `DateField` on the wire — ISO, or a stated absence.

    `date.isoformat()` and never `str()`: the two agree for a `date` and differ
    for `None`, and `"None"` on a screen is the shape hard-won law 1 warns about
    — a value that looks like data.
    """
    return None if value is None else value.isoformat()


def _move_marks(payment: models.Payment) -> dict[str, Any]:
    """*"moved to 2608-0155"* and *"moved from 2608-0141"* — CR-059 CS-32.

    Two directions off ONE column. `moved_from_payment` is the destination
    leg's own FK, pointing at the ORIGINAL payment; `moved_to` is that same
    column read backwards, so the SOURCE row learns where its money went
    without a second column and without a second write.

    ⚠ **THE `moved_to` READ IS A REVERSE RELATION AND COSTS A QUERY PER ROW
    UNLESS IT IS PREFETCHED.** `payment_queryset` and `cheques.py`'s three
    reads prefetch it; a caller that does not still gets the right answer,
    slowly, which is the trade B2 §2 already makes for `allocations`.

    Every value is a NUMBER a clerk reads (B14 rule 31). A leg whose account
    number or payment number is null is served as null and the screen states
    the absence — a move is a fact about a customer's money, so the mark is
    shown even when one of its labels cannot be.
    """
    origin = payment.moved_from_payment
    destination = next(iter(payment.moved_to.all()), None)
    return {
        "moved_from_payment_no": None if origin is None else origin.payment_no,
        "moved_from_account_no": None if origin is None else origin.account.account_no,
        "moved_to_payment_no": None if destination is None else destination.payment_no,
        "moved_to_account_no": None if destination is None else destination.account.account_no,
    }


def payments_totals(qs: QuerySet) -> dict[str, Any]:
    """US-PAY-004 TC-1's "totals row per current filter".

    The COUNT is always answerable. The MONEY is **the day's CASH**, which is a
    narrower and more useful claim than "the sum of these rows" — see below.
    `amount_unavailable` carries the reason as a code the screen groups on,
    never as prose it would have to parse.

    ⚠ **THE CASH TOTAL EXCLUDES CREDITS AND ADJUSTMENTS, AND UNTIL 2026-09-02
    THIS FUNCTION REFUSED TO STATE ANYTHING AT ALL WHEN IT MET ONE (`DEF-3207`,
    `CR-059` CS-35 task 23).** The refusal was right when it was written and
    could not fire: `record_payment` wrote `payment` rows only, so a signed row
    could not exist. **`CR-059` task 22 shipped the writer on 2026-09-02 and the
    branch went live the same day** — from that moment, recording one **$25.00**
    credit answered `amount: null` for the WHOLE filtered set, so a clerk who
    granted one concession lost the day's takings figure entirely.

    **EXCLUDING IS SAFE WHERE SUMMING IS NOT, AND THAT IS THE WHOLE ARGUMENT.**
    The reason the old refusal existed is that whether a credit's sign lives on
    `amount` is B2's own O-4 residue and no signed document closes it — so a
    total that MIXED one in could be wrong by twice the row. **Leaving it out is
    correct under either reading of the sign**, so this needs no ruling and
    invents nothing. It is also what CS-35 asks for in as many words: *"the day's
    cash total must EXCLUDE credits and adjustments, or it will not tie to the
    drawer"*.

    **A day of $100.00 cash and a $25.00 credit reports `amount` 100.00 with
    `excluded_count` 1** — the drawer holds $100.00 and the figure ties to it.
    The excluded rows are COUNTED and never summed, for the same O-4 reason: the
    screen can say one row was left out without either of us claiming to know
    what it is worth.
    """
    from django.db.models import Sum

    rows = qs.values_list("currency", "type").distinct()
    currencies = {currency for currency, _type in rows}
    count = qs.count()
    if count == 0:
        # Zero rows: a "$0.00" here reads as "we took nothing today", which is a
        # claim about the day's takings that this filter did not make.
        return {
            "count": 0,
            "amount": None,
            "currency": None,
            "amount_unavailable": "no_rows",
            "excluded_count": 0,
        }
    if len(currencies) > 1:
        return {
            "count": count,
            "amount": None,
            "currency": None,
            "amount_unavailable": "mixed_currencies",
            "excluded_count": 0,
        }
    cash = qs.filter(type=models.PAYMENT_TYPE_PAYMENT)
    cash_count = cash.count()
    excluded = count - cash_count
    if cash_count == 0:
        # Every row in the filter is a credit or an adjustment. There is no cash
        # to state, and "$0.00" would read as "we took nothing" rather than as
        # "nothing here was cash" — the same distinction `no_rows` draws above.
        return {
            "count": count,
            "amount": None,
            "currency": None,
            "amount_unavailable": "no_cash_rows",
            "excluded_count": excluded,
        }
    # ⚠ SUMMED OVER `cash`, NOT OVER `qs`. That one word is the fix: `qs` is
    # every row the filter matched, credits included, and summing it is the
    # thing the O-4 residue makes unsafe.
    total = cash.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    return {
        "count": count,
        "amount": _decimal_str(total),
        "currency": next(iter(currencies)),
        "amount_unavailable": None,
        # How many rows the cash figure LEFT OUT. Counted, never summed — the
        # screen states the absence rather than implying the total covers them.
        "excluded_count": excluded,
    }


def selection_total(payment_ids: list[str]) -> dict[str, Any]:
    """CR-059 CS-43 — total a SELECTION on the server, not in the browser.

    The acceptance line, verbatim from the change register: *"four rows selected
    on page one and two on page two show `6 selected · 3,918.44` — not a
    blank."*

    ⚠ **THIS EXISTS BECAUSE A BROWSER CANNOT DO IT AND THE FAILURE IS SILENT.**
    The Payments list is paginated IN THE DATABASE (11b G5, 50 rows a page), so a
    tick on page two is a tick on a row page one never held. A selection bar that
    adds up what it can see reports the wrong figure, or nothing at all, at
    exactly the moment a clerk is about to refund six payments. CS-43 is a
    PREREQUISITE for CS-41's toolbar and the order is not optional.

    **IT IS `payments_totals`' RULES, APPLIED TO IDS INSTEAD OF A FILTER**, and
    deliberately so — two ways of totalling payments would be two answers to one
    question on one screen (hard-won law 5, in code):

      * the COUNT is always answerable and counts every selected row;
      * the MONEY is the day's CASH and **excludes credits and adjustments**,
        which is CS-35's own sentence — *"the day's cash total must EXCLUDE
        credits and adjustments, or it will not tie to the drawer"* — and is
        safe under either reading of B2's O-4 residue about where a credit's
        sign lives;
      * `excluded_count` says how many rows the figure left out, so the screen
        can state the absence instead of implying the total covers them;
      * mixed currencies state NO figure. `CHAR(3)` is half of hard rule 2 and
        adding 100.00 USD to 100.00 CAD is not 200.00 of anything.

    **THE IDS THAT ARE NOT THIS TENANT'S SIMPLY DO NOT MATCH** — `payment_queryset`
    filters on `app.tenant_id` and RLS FORCE is the second guarantee — and the
    count says so rather than the request failing: `requested` and `count` differ
    by exactly the rows this tenant does not have. A selection that has gone
    stale (a row filtered away, a payment from another session) is a normal thing
    for a screen to hold, and refusing the whole total over one id would leave the
    bar blank, which is the outcome CS-43 exists to remove.

    Two money members, and BOTH are strings (CLAUDE.md rule 2):

        amount           the exact stored decimal, `3918.440000`
        amount_display   the same figure at TWO places, `3918.44`

    The display companion is served BESIDE the stored value and never instead of
    it, for the reason `rating.selectors._display_money` records: if the client
    may not format money — and it may not, because that is server-owned
    arithmetic — then the server must, or a customer reads `3918.440000`
    (DEF-364).
    """
    from django.db.models import Sum

    ids = [str(one) for one in (payment_ids or [])]
    requested = len(ids)
    if requested == 0:
        return {
            "requested": 0,
            "count": 0,
            "amount": None,
            "amount_display": None,
            "currency": None,
            "amount_unavailable": "no_rows",
            "excluded_count": 0,
        }
    qs = payment_queryset().filter(pk__in=ids)
    count = qs.count()
    if count == 0:
        return {
            "requested": requested,
            "count": 0,
            "amount": None,
            "amount_display": None,
            "currency": None,
            "amount_unavailable": "no_rows",
            "excluded_count": 0,
        }
    currencies = {currency for currency, in qs.values_list("currency").distinct()}
    if len(currencies) > 1:
        return {
            "requested": requested,
            "count": count,
            "amount": None,
            "amount_display": None,
            "currency": None,
            "amount_unavailable": "mixed_currencies",
            "excluded_count": 0,
        }
    cash = qs.filter(type=models.PAYMENT_TYPE_PAYMENT)
    cash_count = cash.count()
    excluded = count - cash_count
    if cash_count == 0:
        return {
            "requested": requested,
            "count": count,
            "amount": None,
            "amount_display": None,
            "currency": None,
            "amount_unavailable": "no_cash_rows",
            "excluded_count": excluded,
        }
    total = cash.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    return {
        "requested": requested,
        "count": count,
        "amount": _decimal_str(total),
        "amount_display": _display_money(total),
        "currency": next(iter(currencies)),
        "amount_unavailable": None,
        "excluded_count": excluded,
    }


def _display_money(value: Decimal | None) -> str | None:
    """The DISPLAY half of CLAUDE.md rule 2 — *"display both 2 decimal"*.

    Served BESIDE the stored six-place value, never instead of it. **This is not
    money rounding**: `money.finalize` is what rounds a figure at issue; this is
    a presentation string and the stored value it sits next to is untouched,
    which is what keeps ❄️ FROZEN B4 out of it entirely.

    The same function `apps/rating/selectors._display_money` is, and a second
    definition rather than an import for the reason that module's own note gives:
    payments and rating share no import edge, and four lines of `quantize` is not
    a contract worth minting one for.
    """
    if value is None:
        return None
    return str(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def active_payment_methods() -> list[dict[str, Any]]:
    """The tenant's LIVE method list (BR-PAY-026) — the S33 filter's vocabulary
    and the S22 Record form's picker, from ONE source.

    BR-REP-006: a filter enumerates the live vocabulary and never a hardcoded
    list, and US-PAY-001 TC-3 is a tenant adding "Bill-pay portal" and using it
    immediately. Two lists would be two places for the six BR-PAY-026 seeds to
    drift, and the form could then offer a method the ledger has retired.

    DEACTIVATED rows are excluded: IS-1 deactivates rather than deletes, and
    `services._method` refuses an inactive code — offering one would be a
    control that always fails.

    `payment_methods` is hosted in tenancy and CONTENT-OWNED by payments
    (BR-TEN-031; the model's own docstring says so and names the re-homing
    path), so this is this module reading its own list, resolved by name in the
    same idiom `services._method` already uses.

    ⚠ **`id` RIDES BESIDE `code` AND `name` FOR ONE REASON: `DEF-3206`.**
    `POST /payments/{id}/correct-reference` resolves its `tender_id` as this
    row's PRIMARY KEY (`amendments._tender`), and until today this read served
    the code and the name and nothing else — so the tender third of the PO's
    2026-09-02 ruling had a door and no way for a screen to knock on it. The
    filter and the Record form still key on `code` and neither has changed.
    **The id is a `<select>` VALUE and is never a value a clerk reads** (B14
    rule 31 governs what a field SHOWS; the option's label is the method name).
    """
    lookup = _resolve("tenancy", "PaymentMethod", "models")
    if lookup is None:  # pragma: no cover - defensive
        return []
    rows = lookup.objects.filter(tenant_id=_tenant_id(), active=True).order_by("name", "code")
    return [{"id": str(row.pk), "code": row.code, "name": row.name} for row in rows]


# ── The record result (US-PAY-001) ──────────────────────────────────────────


def recorded_payment_dict(result: Any) -> dict[str, Any]:
    """`services.RecordedPayment` on the wire — what the S22 modal renders.

    A clerk who has just taken $292.87 is shown WHAT IT PAID, not an id: the
    allocator computed the per-bill split inside the same transaction and it
    would be perverse to throw it away and make the screen ask again.

    `payment_id` becomes `id` here — ONE name for the payment's identity across
    this API, because two names for one value is DEF-014's exact shape.

    `problems[]` travels verbatim. Every entry is a CODE plus its BR-ID plus a
    sentence; the screen groups on the code and shows the sentence, and the
    absences it names (no receipt queued, the account-balance cache not
    updated) are facts about this deployment rather than about this payment.
    """
    return {
        "id": result.payment_id,
        "payment_no": result.payment_no,
        "created": result.created,
        "status": result.status,
        "amount": _decimal_str(result.amount),
        "currency": result.currency,
        "applied": _decimal_str(result.applied),
        "credit_carried": _decimal_str(result.credit_carried),
        "allocations": [
            {
                "invoice_id": row.get("invoice_id"),
                "invoice_number": row.get("invoice_number"),
                "amount": _decimal_str(row["amount"]),
                # BR-PAY-038's four classes, as the allocator reported them.
                # Already strings (they ride the audit payload as strings, and
                # they have no column to live in — OQ-129). `{}` when the bill
                # stated no composition, which is B5 GT-7's own legal shape and
                # is NOT the same as "every class was zero".
                "by_class": row.get("by_class", {}),
            }
            for row in result.allocations
        ],
        "journal_entry_id": result.journal_entry_id,
        "posting_key": result.posting_key,
        "posted_to_ledger": result.posted_to_ledger,
        "problems": [dict(problem) for problem in result.problems],
    }


# ── The credit position, and the reversal link (US-PAY-009 · US-PAY-011) ────


def account_credit_position(account_id: Any) -> Decimal:
    """What the utility holds FOR this account — and it may be BELOW ZERO.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  A NEGATIVE CREDIT IS A REAL DEBT. NOTHING HERE FLOORS IT AT ZERO.   ║
    ╚══════════════════════════════════════════════════════════════════════╝
    Product Owner ruling, 2026-08-11, closing OQ-132 — verbatim: **"Yes, it's a
    real debt"**. Worked, on J15's own chain:

        pay $350.00 against $292.87 open   ->  credit   57.13   (PE-4)
        refund cheque $57.13 issued        ->  credit    0.00   (PE-9)
        the $350.00 cheque bounces         ->  credit  −57.13

    That **−57.13** is a genuine receivable the utility pursues. The ruling
    states the consequence for every consumer of this figure: *"any code, screen
    or report that assumes a customer credit is non-negative is wrong — the
    balance may be below zero and must render and age as a debt"*.

    So this returns a SIGNED Decimal and there is deliberately no `max(0, …)`
    anywhere in it. A floor here would be the exact defect the ruling names: the
    screen would show $0.00, the utility would never chase the $57.13, and the
    books — where `customer_credit_balance` (2400) carries a real debit balance
    for this account — would disagree with the product by that amount.

    THE ARITHMETIC, and why every term is a row this module owns:

        Σ payments.amount        every POSTED or CLEARED receipt EXCEPT a
                                 deposit (US-PAY-002 TC-1: a deposit is HELD,
                                 never credit; CR-186-BRC10: never cancelled,
                                 failed or processing — `balance_rule`), and
                                 INCLUDING the negative reversing rows (a bounce
                                 nets itself out)
      − Σ allocations.amount     what met bills, INCLUDING the negative
                                 reversing rows (a bounce re-opens them)
      − Σ refunds.amount         issued and cleared refunds; a VOID refund is
                                 excluded because its reversing entry has
                                 already restored the credit
      = the credit position

    `refunds` in `requested` or `approved` state are NOT subtracted: no money
    has left, and subtracting them would let an unapproved request make a real
    credit look spent — which would then block the refund that spends it.

    Nothing is read from another module. Billing's invoice totals do not appear
    here at all: this is what the utility holds ON ACCOUNT, not what the account
    owes, and mixing the two is how a credit balance comes to be reported as a
    reduced bill.
    """
    from django.db.models import Sum

    zero = Decimal("0")
    tenant_id = _tenant_id()
    received = (
        models.Payment.objects.filter(tenant_id=tenant_id, account_id=account_id)
        # ── CR-186-BRC10 · `DEF-PAY-10340` ─────────────────────────────────
        # posted, cleared and reversing rows ONLY. This read
        # `.exclude(status=processing)` until 2026-10-21, so a failed cheque
        # and a lone cancelled row were counted as money received. The set is
        # `balance_rule`'s and is stated nowhere else.
        .filter(status__in=balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES)
        # ── DEPOSITS ARE NOT CREDIT (US-PAY-002 TC-1, added 2026-08-15) ──────
        # BR-PAY-012 holds a deposit-purpose payment against the account's
        # DEPOSIT POSITION and US-PAY-002 TC-1 is explicit: *"account credit NOT
        # created — the money is held against the deposit line"*. It posts to
        # the deposit LIABILITY (2000), not to customer credit (2400), so
        # counting it here would put this figure out against the books by the
        # deposit — and worse, `credit.apply_credit_at_issue` would spend it on
        # the next bill, which is money the utility is holding FOR the customer
        # and owes back at move-out (BR-CUS-050 / US-BIL-011).
        .exclude(purpose=models.PURPOSE_DEPOSIT)
        .aggregate(total=Sum("amount"))["total"]
    )
    applied = models.Allocation.objects.filter(
        tenant_id=tenant_id, payment__account_id=account_id
    ).aggregate(total=Sum("amount"))["total"]
    # ⚠ **`account_id`, NOT `payment__account_id` (CR-059 CS-7, 2026-09-03).**
    # This clause used to JOIN THROUGH THE PAYMENT, which was correct while
    # `refunds.payment_id` was NOT NULL and became silently wrong the moment it
    # stopped being: a refund raised against a credit built from several
    # payments has NO payment, so an INNER JOIN drops the row and the refund is
    # **never subtracted**. Measured on the PO's own case — $40.00 + $17.13
    # refunded as one $57.13 cheque — the account went on reading **57.13** in
    # credit after the money had left the building, and the same 57.13 could
    # have been refunded again. Found by `test_cs7__two_overpayments_one_refund`
    # asserting the position AFTER issue; nothing else would have.
    refunded = models.Refund.objects.filter(
        tenant_id=tenant_id,
        account_id=account_id,
        status__in=(models.REFUND_ISSUED, models.REFUND_CLEARED),
    ).aggregate(total=Sum("amount"))["total"]
    # ⚖️ **A RELEASED DEPOSIT IS CREDIT** (CR-171-BRC10 lane RULINGS, 2026-10-05,
    # `OQ-CUS-12790` (a)). PO verbatim: *"Release the deposit and refund the full
    # $175.00 as one refund, approved by Finance as usual."* The deposit payment
    # stays excluded above — it is HELD (US-PAY-002 TC-1) — and the ACT that ends
    # the holding is a `deposit_releases` row, written with its DR 2300 / CR 2400
    # entry by `deposit_release.release_to_credit` alone. Nilesh: $25.00 prepay
    # + $150.00 released = **$175.00**, one refund.
    from apps.payments.deposit_release_models import DepositRelease

    released = DepositRelease.objects.filter(tenant_id=tenant_id, account_id=account_id).aggregate(
        total=Sum("amount")
    )["total"]
    return (
        (received or zero) + (released or zero) - (applied or zero) - (refunded or zero)
    )


def reversal_of(payment_id: Any) -> Any:
    """The reversing row that bounced this payment, or None.

    **"Has this payment been reversed?" is a question about the EXISTENCE of a
    row, never about a flag on the original.** Hard rule 4 and the trigger in
    `migrations/0002` both refuse to change a cleared payment, so the original's
    status stays `cleared` forever — which is also the truth: it DID clear, and
    then it came back. EP-PAY-03 §5's phrase *"status reversed on the pair"* can
    only mean the reversing row, and this is the read that answers it.
    """
    return models.Payment.objects.filter(
        tenant_id=_tenant_id(), reverses_payment_id=payment_id
    ).first()


def reversed_payment_dict(result: Any) -> dict[str, Any]:
    """`reversal.ReversedPayment` on the wire — what the S35 Reverse modal shows.

    ADDED 2026-09-01 (CR-059 CS-5, task 15). The service has produced this
    dataclass since 2026-08-11 and no route had ever answered with it.

    Every figure is the SERVICE's, restated nowhere: `allocations_reversed` is
    the Σ the reversing rows actually wrote, `credit_position_after` is the
    signed position `account_credit_position` computed inside the same
    transaction, and neither is recomputed here. **`_decimal_str` is the same
    exact-decimal serialisation `recorded_payment_dict` uses** — money never
    travels as a number and is never re-rounded on the way out (CLAUDE.md rule
    2, `BR-TEN-080`), and every amount travels beside its `CHAR(3)` code.

    `reversal_id` becomes `id` here, matching `recorded_payment_dict`'s
    `payment_id` → `id`: **one name for the payment's identity across this
    API**, because two names for one value is `DEF-014`'s exact shape.

    ⚠ **`amount` IS NEGATIVE AND STAYS NEGATIVE.** `PE-7`'s reversing row is
    **−292.87** and a screen that renders it unsigned would tell a clerk a
    second payment of 292.87 had arrived. `credit_position_after` may be
    negative too, and that is a real debt the utility pursues (PO 2026-08-11,
    `OQ-132`: *"Yes, it's a real debt"*) — nothing here floors either at zero.

    ⚠ **`nsf_count` AND `cash_only_no_autopay` MAY BE `null`, WHICH IS NOT
    ZERO AND NOT FALSE.** The service returns `None` when the customers seam did
    not run — a replay does not re-count a bounce, and a bounce is not an NSF
    unless its reason says so. *"We did not count"* and *"the count is zero"*
    are different facts and only one of them is safe to render, so the null
    travels as a null and the screen states the absence.

    `problems[]` travels verbatim. On this path it carries what the bounce could
    NOT do (the customer's NSF charge code, the notice-history row, the account
    balance cache) AND what it DID (whether the collection ladder was restarted
    or left paused, whether the returned-payment letter was queued) — a caller
    must not have to infer either one.
    """
    return {
        "id": result.reversal_id,
        "payment_no": result.reversal_no,
        "original_payment_id": result.original_payment_id,
        "created": result.created,
        "amount": _decimal_str(result.amount),
        "currency": result.currency,
        "reason": result.reason,
        "allocations_reversed": _decimal_str(result.allocations_reversed),
        # The bills that re-opened, each with the POSITIVE amount put back on
        # it — the reversing allocation row itself is the negative of this.
        # `amount` is serialised through `_decimal_str` like every other money
        # figure here: the service hands it back as a `Decimal` and letting the
        # renderer decide would be the one place in this payload where a money
        # value travels as something other than its exact decimal string.
        "reopened": [{**row, "amount": _decimal_str(row["amount"])} for row in result.reopened],
        "credit_reversed": _decimal_str(result.credit_reversed),
        "credit_position_after": _decimal_str(result.credit_position_after),
        "journal_entry_id": result.journal_entry_id,
        "posting_key": result.posting_key,
        "bank_fee": _decimal_str(result.bank_fee),
        "bank_fee_entry_id": result.bank_fee_entry_id,
        "nsf_count": result.nsf_count,
        "cash_only_no_autopay": result.cash_only_no_autopay,
        "privilege_flag_tripped": result.privilege_flag_tripped,
        # ── CR-059 CS-33 ──────────────────────────────────────────────────
        # ⚠ **`still_stands` IS SERVED SO A SCREEN NEVER SUBTRACTS TWO
        # FIGURES ITSELF.** The S35 modal's amount field defaults to the full
        # amount and shows *"what will still stand afterwards"*; a client
        # computing that from the payment and this reversal would eventually
        # disagree with the service that refuses the NEXT request — and the
        # figure a clerk is looking at when they decide is the one that has to
        # be right. It is `0` on a full reversal.
        "is_partial": result.is_partial,
        "still_stands": _decimal_str(result.still_stands),
        # ── DEF-PAY-10698 · the NSF penalty this bounce charged (PO 2026-10-30)
        # `nsf_fee_amount` is null unless a fee bill was raised — "no fee" is
        # never 0.00; `nsf_fee_status` names why (`nsf_fee_not_set_on_plan`).
        "nsf_fee_status": result.nsf_fee_status,
        "nsf_fee_code": result.nsf_fee_code,
        "nsf_fee_amount": _decimal_str(result.nsf_fee_amount),
        "nsf_fee_invoice_no": result.nsf_fee_invoice_no,
        "nsf_fee_waived_reason": result.nsf_fee_waived_reason,
        # LBX-04 — the bank's own words, as saved on the reversing row.
        "bank_memo": result.bank_memo,
        "problems": [dict(problem) for problem in result.problems],
    }


def transferred_money_dict(result: Any) -> dict[str, Any]:
    """One cross-account movement on the wire (CR-059 CS-8 · CS-32).

    ONE shape for both a credit transfer and a payment move, with `kind` telling
    them apart, because a screen that renders the two differently is a screen
    with two ways to be wrong about one fact. What differs is which optional
    members carry anything: a MOVE names the payment the customer holds a
    receipt for and lists what re-opened on the source; a TRANSFER re-opens
    nothing, because credit met no bill on the way out.

    ⚠ **`source_credit_after` AND `destination_credit_after` MAY BE BELOW ZERO**
    and nothing here floors them — PO 2026-08-11, `OQ-132`, *"Yes, it's a real
    debt"*. A screen that rendered a negative credit as `0.00` would tell a clerk
    the utility is owed nothing by an account it is owed money by.

    ⚠ **`amount` IS THE POSITIVE SIZE OF THE MOVEMENT**, not either row's signed
    amount. The two legs are `−amount` and `+amount` and both are readable on
    `GET /payments` under their own numbers; a payload that made the caller work
    out which sign belonged to which account would be inviting the mistake.

    Every money figure goes through `_decimal_str` — CLAUDE.md rule 2: the exact
    stored decimal beside its CHAR(3) code, never a number, never cents.
    """
    return {
        "kind": result.kind,
        "created": result.created,
        "source_account_id": result.source_account_id,
        "destination_account_id": result.destination_account_id,
        "source_payment_id": result.source_payment_id,
        "source_payment_no": result.source_payment_no,
        "destination_payment_id": result.destination_payment_id,
        "destination_payment_no": result.destination_payment_no,
        # CS-32 only: the number the customer was actually given. NULL on a
        # credit transfer, where no payment moved and there is no such number.
        "moved_payment_id": result.moved_payment_id,
        "moved_payment_no": result.moved_payment_no,
        "amount": _decimal_str(result.amount),
        "currency": result.currency,
        "applied": _decimal_str(result.applied),
        "credit_carried": _decimal_str(result.credit_carried),
        # ── CR-059 CS-22 · the deposit carry-forward's three figures ─────────
        # ⚠ **`held` IS WHAT MAKES A CARRIED DEPOSIT LEGIBLE ON A SCREEN, AND
        # WITHOUT IT THE PAYLOAD IS ACTIVELY MISLEADING.** A carry reports
        # `applied 0.00` and `credit_carried 0.00` — both true — so a screen
        # reading only those two would render a movement of $150.00 that met
        # nothing and credited nothing, which looks like money that vanished.
        # `held` is where it went: security the utility still owes back.
        "held": _decimal_str(result.held),
        # The customer deposit REGISTER on both accounts afterwards — the
        # customers-side figure BR-LED-007 ties against the 2300 liability.
        # Zero on a credit transfer and on a move, where no deposit moved.
        "source_deposit_after": _decimal_str(result.source_deposit_after),
        "destination_deposit_after": _decimal_str(result.destination_deposit_after),
        "allocations": [
            {**row, "amount": _decimal_str(row["amount"])} for row in result.allocations
        ],
        "reopened": [{**row, "amount": _decimal_str(row["amount"])} for row in result.reopened],
        "source_credit_after": _decimal_str(result.source_credit_after),
        "destination_credit_after": _decimal_str(result.destination_credit_after),
        "journal_entry_id": result.journal_entry_id,
        "posting_key": result.posting_key,
        "problems": [dict(problem) for problem in result.problems],
    }


def voided_cheque_dict(result: Any) -> dict[str, Any]:
    """One cheque voided at the counter (CR-059 CS-30, S33 · S35).

    ⚠ **`is_a_bank_event` IS `false` AND IT IS ON THE WIRE ON PURPOSE.** A void
    and a reversal look alike on a screen — a payment that was there and is not
    any more — and they are different facts about a customer: a reversal means
    the bank sent the money back, a void means the cheque never left the office.
    A screen that rendered them the same way would tell a customer their cheque
    bounced when nothing of the sort happened, and if the tender were a cheque
    that is a sentence with an NSF count behind it.

    `status` is `failed`, which is the lawful transition a `processing` payment
    may make (`payments/0002`). There is no `voided_at`: hard rule 4's trigger
    lets a processing row change its STATUS and nothing else, so the void's own
    who/when/why is the `audit_log` row — and `problems[]` says so, because that
    row is pruned on a retention schedule (`OQ-1340`, OPEN).
    """
    return {
        "payment_id": result.payment_id,
        "payment_no": result.payment_no,
        "account_id": result.account_id,
        "amount": _decimal_str(result.amount),
        "currency": result.currency,
        "status": result.status,
        "reason": result.reason,
        "is_a_bank_event": False,
        "posted_to_ledger": False,
        "problems": [dict(problem) for problem in result.problems],
    }


def reapplied_dict(result: Any) -> dict[str, Any]:
    """One reapply on the wire (CR-059 CS-11, S33 · S35).

    ⚠ **`posted_to_ledger` IS `false` AND IT IS A STATED FACT, NOT A SILENCE.**
    A reapply moves money between one account's own bills and posts NOTHING —
    the cash total has not changed, only which bill it met, and the books carry
    no invoice dimension for an entry to make more true. Every OTHER write path
    in this module posts, so the next reader's instinct is that a posting is
    missing; the member and the matching `problems[]` row are what answer that
    without anyone having to read the service.

    Every bill is named by its NUMBER as well as its id (B14 rule 31 — *"no
    database id is ever the visible value of a field"*). A bill whose number
    could not be read carries `null` rather than being dropped: the money moved
    and that is a fact about a customer's account, so the row shows the amount
    and states that the label is missing.

    Every money figure goes through `_decimal_str` — CLAUDE.md rule 2.
    """
    return {
        "payment_id": result.payment_id,
        "payment_no": result.payment_no,
        "account_id": result.account_id,
        "amount": _decimal_str(result.amount),
        "currency": result.currency,
        # The bills the money came OFF, each with the POSITIVE figure taken
        # back; the mirror allocation rows themselves are negative.
        "released": [
            {**row, "amount": _decimal_str(row["amount"])} for row in result.released
        ],
        "applied_to": [
            {**row, "amount": _decimal_str(row["amount"])} for row in result.applied_to
        ],
        "released_total": _decimal_str(result.released_total),
        "applied_total": _decimal_str(result.applied_total),
        # What no bill absorbed and is now sitting as account credit. Signed and
        # never floored (PO 2026-08-11, `OQ-132`).
        "credit_carried": _decimal_str(result.credit_carried),
        "posted_to_ledger": False,
        "problems": [dict(problem) for problem in result.problems],
    }


def refund_row(refund: Any) -> dict[str, Any]:
    """One `refunds` row on the wire (S58).

    Both approval acts are rendered SEPARATELY and neither is folded into a
    boolean: BR-PAY-037 lets one user initiate and approve in v1 *"as long as
    both acts are recorded separately"*, so a screen that showed only "approved"
    would erase the control the rule leans on.
    """
    return {
        "id": str(refund.pk),
        # ⚠ **`null` WHENEVER THE CREDIT CAME FROM MORE THAN ONE PAYMENT** —
        # CR-059 CS-7, the PO's ruling of 2026-09-01 (`OQ-195`). Every consumer
        # of this member must survive its absence; `account_id` below is the one
        # that is always there, and it is what a screen groups and filters on.
        "payment_id": None if refund.payment_id is None else str(refund.payment_id),
        # The refund's address (`payments/0018`). NOT NULL in the schema and
        # never null here — a refund with no account is a cheque with no
        # addressee, and the migration's `SET NOT NULL` is what guarantees it.
        "account_id": str(refund.account_id),
        "amount": _decimal_str(refund.amount),
        "currency": refund.currency,
        "status": refund.status,
        "method": refund.method,
        "reference": refund.reference,
        "reason": refund.reason,
        "requested_by": None if refund.requested_by_id is None else str(refund.requested_by_id),
        "requested_at": _iso(refund.requested_at),
        "approved_by": None if refund.approved_by_id is None else str(refund.approved_by_id),
        "approved_at": _iso(refund.approved_at),
        "issued_at": _iso(refund.issued_at),
        "cleared_at": _iso(refund.cleared_at),
        "voided_at": _iso(refund.voided_at),
        "void_reason": refund.void_reason,
        "journal_entry_id": (
            None if refund.journal_entry_id is None else str(refund.journal_entry_id)
        ),
        "void_journal_entry_id": (
            None if refund.void_journal_entry_id is None else str(refund.void_journal_entry_id)
        ),
    }


def payment_account_id(payment_id: Any) -> Any:
    """Which account a payment belongs to — this tenant's, or None.

    ADDED 2026-09-01 (CR-059 CS-6, task 17) so `POST /accounts/{id}/refunds` can
    prove its own path segment: a `payment_id` naming ANOTHER account's payment
    is refused there rather than accepted with the URL treated as a label.

    Tenant-scoped, so a cross-tenant payment id resolves to `None` and the
    caller's refusal is the ordinary one — never somebody else's row, and never
    a 403 that confirms the row exists (CLAUDE.md rule 1, HR-1).

    `None` means *"this tenant has no such payment"* and is deliberately NOT the
    caller's refusal: `refunds._source_payment` already refuses a missing
    payment with the sentence a clerk can act on, and two different messages for
    one fact is how two screens come to disagree.
    """
    try:
        return (
            models.Payment.objects.filter(tenant_id=_tenant_id(), pk=payment_id)
            .values_list("account_id", flat=True)
            .first()
        )
    except (ValueError, TypeError):  # a malformed id is a caller mistake
        return None


def refund_step_dict(result: Any) -> dict[str, Any]:
    """One refund STEP on the wire — the row, plus what only the result knows.

    ADDED 2026-09-01 (CR-059 CS-6, task 17). `refund_row` stays the shape of a
    refund everywhere and this adds nothing to it — a second serialisation of
    the same row is `DEF-014`'s exact shape. What it adds is the two facts the
    ROW cannot carry:

      * **`credit_position_after`** — the SIGNED credit the account holds once
        this step landed, computed by the service inside the same transaction.
        ⚠ CS-6's own *"watch for"*: the screen must **not cache the credit
        figure between request and issue**, because *"a credit real on Tuesday
        can be gone by Thursday, and the money moves on Thursday."* Serving the
        live figure on every step is what lets a screen obey that without
        asking a second endpoint and hoping the two agree. It may be BELOW ZERO
        and is not floored (PO 2026-08-11, `OQ-132`).
      * **`problems[]`** — verbatim, code + `br_ref` + sentence, as every money
        path in this module carries it. On issue it is where the refund receipt
        reports whether it was queued.

    `created` rides along because `request_refund` is idempotent on the submit
    token: a double-clicked Record answers `false` with the FIRST refund.
    """
    row = refund_detail(result.refund_id)
    row["created"] = result.created
    row["credit_position_after"] = _decimal_str(result.credit_position_after)
    row["problems"] = [dict(problem) for problem in result.problems]
    return row


def account_credit_sources(account_id: Any) -> dict[str, Any]:
    """S58's *"listing the payments behind it"* — CR-059 CS-7.

    The body `GET /accounts/{id}/credit-sources` serves: what this account holds
    on account, and WHICH payments built it. Nothing is written and no clock is
    read.

    ⚠ **`refundable` IS THE POSITION AND NOT THE SUM OF THE ROWS, AND THE
    DIFFERENCE IS THE HONEST PART.** `account_credit_position` subtracts issued
    and cleared refunds; `contributing_payments` cannot attribute a past refund
    back to the payments it drew on, because **nothing in this product records
    which ones it drew on** — the ruling of 2026-09-01 is precisely that a
    refund names the ACCOUNT and not a payment. So the two agree until the first
    refund is issued and then diverge, on purpose, and the payload says which is
    which rather than making a screen add up rows and get a number the refund
    path will refuse.

    Worked, on the PO's own case: **$40.00 in June + $17.13 in July** against
    bills that took nothing → `refundable` **57.13** with two rows behind it.

    `refundable` is SIGNED and may be below zero (PO 2026-08-11, `OQ-132` —
    *"Yes, it's a real debt"*); nothing floors it, and a screen rendering it as
    0.00 would tell a clerk there is nothing to chase.
    """
    from apps.payments import credit

    position = account_credit_position(account_id)
    rows = credit.contributing_payments(account_id)
    return {
        "account_id": str(account_id),
        "refundable": _decimal_str(position),
        "refundable_display": _display_money(position),
        "sources": [dict(row) for row in rows],
        "source_count": len(rows),
        "problems": [
            {
                "code": "sources_are_evidence_not_a_link",
                "br_ref": "BR-PAY-014",
                "detail": "these are the payments that built the credit, listed so a clerk can "
                "see where it came from. A refund raised from this screen names the ACCOUNT and "
                "none of them (PO ruling 2026-09-01), and once a refund has been issued the "
                "rows no longer sum to the refundable figure — nothing records which payments a "
                "past refund drew on, and this list does not invent an attribution.",
            }
        ],
    }


def refund_detail(refund_id: Any) -> dict[str, Any]:
    """ONE refund row, read back after an act on it.

    `refunds.RefundResult` is a step summary — `refund_id`, `status`, `amount`,
    `credit_position_after` — and it deliberately carries neither approval
    column. `BR-PAY-037` rests on `requested_by` and `approved_by` being visible
    as SEPARATE facts, so a door that answered with the result dataclass would
    hide the very thing the rule leans on. This reads the row back through the
    same `refund_row` the queue uses, so one act and one list cannot disagree
    about what a refund looks like.

    404-never-403 for a refund of another tenant: the filter is the tenant id
    and a miss is a miss (HR-1).
    """
    row = models.Refund.objects.filter(tenant_id=_tenant_id(), pk=refund_id).first()
    if row is None:
        raise errors.NotFoundError()
    return refund_row(row)


def refund_pending_count() -> int:
    """**THE WHOLE-POPULATION COUNT OF WHAT IS WAITING — Finance blueprint
    `P2.19`.**

    `writeoffs.write_off_pending_count`'s twin, and the reasoning is that
    function's: the badge in the Revenue & AR view label must state the TRUE
    total so a filtered or paged queue can no longer hide anything, which means
    it ignores every filter and can never be `len(rows)`. A count derived from
    the rows on screen IS the lie the badge exists to end.
    """
    return models.Refund.objects.filter(tenant_id=_tenant_id(), status="requested").count()


def refund_queue(
    *,
    status: str | None = None,
    q: str | None = None,
    method: str | None = None,
    requested_from: date | None = None,
    requested_to: date | None = None,
    offset: int = 0,
    limit: int | None = None,
) -> dict[str, Any]:
    """DEF-2032 — the refunds a second person approves. The read that was missing.

    The status is `BR-PAY-014`'s Admin half — *"what is awaiting approval?"* —
    and `status=None` serves every refund this tenant has, which is the
    reported history.

    ⚠ **IT TOOK ONE ARGUMENT UNTIL 2026-09-24 AND THE SCREEN DECLARED FOUR
    (`P2.19`).** Blueprint p041's criteria table marks **State** SERVED and
    **Method · Requested (a date range) · Search** NOT SERVED — *"only the state
    filter is supported today"* — over a toolbar the drawing puts on the screen.
    Four controls that narrow nothing is worse than four controls that are
    absent: a clerk who filters and sees the same rows concludes the DATA is
    wrong rather than the filter.

    ⚠ **`q` MATCHES THE CHEQUE / CONFIRMATION REFERENCE, AND NOT THE ACCOUNT.**
    p041 says *"Search · `q` · refund number, account or cheque"*. `reference`
    IS the cheque number and is what the screen prints as the row's
    human-facing reference. The ACCOUNT half is `account_id`, a uuid, and is
    **deliberately not searched**: matching a database id against text a clerk
    typed makes rule 31's invisible value findable, which is that rule's
    defect from the other end. The account NUMBER belongs to `customers` and
    this read does not join it — **stated here rather than quietly
    half-implemented**, because a search box that silently covers two of the
    three things its placeholder promises is `G32`'s shape: truthful about
    everything it can see, over a scope it excludes without saying so.

    ⚠ **AND IT PAGES, WHICH IS `P1.3` ARRIVING ALONGSIDE `P2.19` (`DEF-PAY-6555`
    · `NFR-3`, 2026-09-24).** This read was unpaginated and its own argument for
    that is worth quoting because it is a good one: *"a page of an approval
    queue is a queue that lies about what is pending."* The objection is real
    and the ceiling under it is not — the product serves utilities to 40,000
    accounts since 2026-09-06, and `/outstandings` is the same sentence,
    measured this week at **61.5 seconds against a 60-second worker timeout**.

    **It is ANSWERED rather than overruled, and the two lanes answered it the
    same way from opposite ends**, which is why both numbers are here and
    neither is redundant:

      * `total` — the count over the **FILTERED** set, which is what the PAGER
        states: *1–50 of 120*. Without it a page genuinely does lie.
      * `refund_pending_count()` — the count over the **WHOLE** population,
        ignoring every filter, which is what the BADGE in the view label
        states. A filtered queue must not be able to shrink it.

    Asking one number to be both is how a badge starts lying: narrow to
    `method=ach` and *"what is waiting"* would drop, over refunds that are still
    waiting. The decision and the options declined are in
    `12-governance/02-decision-log.md` under 2026-09-24.

    `limit=None` serves everything, for the callers that are not a screen.

    ⚠ **`statuses` AND `methods` ARE `P1.5`.** `RefundsPage.tsx` held the state
    chips as a literal array and `REFUND_METHODS` as a second copy of
    `models.REFUND_METHODS`, so a sixth status added here would be served,
    filterable and invisible (`DEF-PAY-6557`). The VALUES are the enums; the
    LABEL is a catalogue key the browser resolves, because a server does not
    speak a clerk's language (BR-SHL-023).

    **THIS READ IS WHY `approve_refund` AND `void_refund` COULD NOT BE MOUNTED
    BEFORE.** It is `DEF-100`'s shape exactly one table over, and that defect
    already recorded the mechanism in its own words: *"the only write-off id a
    browser could hold was the one the requester's own screen had just minted, so
    the Approve control had nowhere to live except beside the request."* A refund
    id had nowhere at all — no route in this product listed one — so the two
    Admin-gated acts on it were unreachable by construction, not by oversight.

    `apps/payments/models.Refund`'s own docstring records the requirement
    verbatim: *"J15 steps 2–3 require the row to be VISIBLE in an approval queue
    between the request and the execution."* This is that queue, built over the
    existing `refund_row` and adding no second serialisation of a money row.

    ⚠ **BOTH APPROVAL ACTS STAY SEPARATE.** `refund_row` renders `requested_by`
    and `approved_by` as distinct fields and folds neither into a boolean,
    because `BR-PAY-037` lets one user initiate AND approve in v1 *"as long as
    both acts are recorded separately"* — a queue showing only "approved" would
    erase the control the rule leans on.

    ⚠ **EVERY AMOUNT TRAVELS WITH ITS CHAR(3) CODE** (CLAUDE.md rule 2), and the
    code is the ROW's own `currency`, never a tenant default: a bare number in an
    approval queue for money leaving the building is half a fact.

    ⚠ **THIS READ WAS UNPAGINATED AND ITS OWN ARGUMENT FOR THAT IS QUOTED HERE
    BECAUSE IT IS A GOOD ONE (`DEF-PAY-6555` · `NFR-3` · `P1.3`, 2026-09-24).**
    Verbatim: *"Unpaginated, deliberately, for the reason `write_off_queue` and
    `/outstandings` are: a utility under 3,000 connections has a queue a person
    reads in one screen, and **a page of an approval queue is a queue that lies
    about what is pending.**"*

    **The objection is real and the ceiling is not.** The product serves
    utilities to 40,000 accounts since the PO's ruling of 2026-09-06, and
    `NFR-3` carves out no exception; `/outstandings` is the same sentence,
    measured this week at **61.5 seconds against a 60-second worker timeout** —
    at the top of the range it was not slow, it was killed before it answered.

    **And the objection is ANSWERED rather than overruled, which is the whole of
    this change.** `total` is the count over the FILTERED set and rides on every
    page, so *"what is pending"* is a number the screen always has — the Finance
    blueprint's own settlement, p040: *"The answer to 'a page lies about what is
    pending' is the count in the view label: `Refunds · 1` states the true total
    on every page, so paging can no longer hide anything."* A caller that pages
    without rendering that total re-opens the defect, which is why `total` is
    not optional on this body. The judgment is in `12-governance/02-decision-log.md`
    under 2026-09-24.

    `limit=None` serves everything, for the callers that are not a screen.

    ⚠ **`statuses` AND `methods` ARE `P1.5`.** `RefundsPage.tsx` held the state
    chips as a literal array and `REFUND_METHODS` as a second copy of
    `models.REFUND_METHODS`, so a sixth status added here would be served,
    filterable and invisible (`DEF-PAY-6557`). The VALUES are the enums; the
    LABEL is a catalogue key the browser resolves, because a server does not
    speak a clerk's language (BR-SHL-023).

    Ordered newest request first — an approval queue is worked from the top.
    """
    rows = models.Refund.objects.filter(tenant_id=_tenant_id())
    if status is not None:
        if status not in models.REFUND_STATUSES:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="payments.refund.status_unknown",
                params={"status": status, "supported": list(models.REFUND_STATUSES)},
            )
        rows = rows.filter(status=status)
    if method:
        # ⚠ **REFUSED BY NAME, LIKE THE STATUS ABOVE.** An unknown method
        # silently answering an empty queue is indistinguishable on screen from
        # *nothing is waiting* — this function's own sentence, applied to the
        # second filter it gained.
        if method not in models.REFUND_METHODS:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="payments.refund.method_unknown",
                params={"method": method, "supported": list(models.REFUND_METHODS)},
            )
        rows = rows.filter(method=method)
    if requested_from is not None:
        rows = rows.filter(requested_at__date__gte=requested_from)
    if requested_to is not None:
        # INCLUSIVE, because a clerk who types one date in both boxes means
        # *that day*, and `requested_at` is a MOMENT — an exclusive bound on a
        # timestamp column drops everything after midnight on the end date,
        # which is the whole day they asked for.
        rows = rows.filter(requested_at__date__lte=requested_to)
    if q:
        needle = q.strip()
        if needle:
            rows = rows.filter(reference__icontains=needle)
    # ⚠ THE TIEBREAK IS PART OF THE PAGE. `requested_at` is nullable and two
    # refunds raised in one minute compare equal; without `id` at the end a row
    # can swap between page 1 and page 2 and an approver sees one twice and
    # another never (`core.pagination.order_terms`' own warning).
    rows = rows.order_by("-requested_at", "-created_at", "-id")
    total = rows.count()
    page = rows[offset : offset + limit] if limit is not None else rows
    return {
        "rows": tuple(refund_row(row) for row in page),
        "total": total,
        "statuses": [
            {"value": value, "label_key": f"payments.refunds.status.{value}"}
            for value in models.REFUND_STATUSES
        ],
        "methods": [
            {"value": value, "label_key": f"payments.refunds.method.{value}"}
            for value in models.REFUND_METHODS
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE MONTH-CLOSE SEAM — BR-LED-006's two payments checklist items
# ═══════════════════════════════════════════════════════════════════════════
# `apps/ledger/close.py` has named these two callables, by exact signature, in
# its `WANTED_READS` table since it was written, and reported the two items
# `unknown` because nothing answered them. Two of BR-LED-006's five checklist
# lines — *batches reconciled* and *bank rec current* — read registers the
# ledger may not touch: B1 / BR-TEN-013 forbid a cross-module ORM query, which
# is exactly why the seam is a NAME resolved at call time and not an import.
#
# ── WHY A COUNT AND NOT A BOOLEAN ──────────────────────────────────────────
# The close screen tells a clerk what is left to do, and *"3 outstanding"* is
# actionable where *"not ready"* is a dead end. `close._seam_item` renders the
# integer straight into the item detail.
#
# ── `None` IS NOT ZERO, AND THAT IS THE WHOLE CONTRACT ─────────────────────
# These return `int | None`, widening the `-> int` the ledger first asked for,
# because there are THREE answers and not two:
#
#   * an integer — the register was read. `0` means nothing is outstanding and
#     the item ticks. This is what the change is FOR: before it, a utility
#     closed EVERY month over an explanation it had to type.
#   * `None` — the register cannot answer for this window. The ledger renders
#     this as `unknown`, which counts as INCOMPLETE, so the close still happens
#     (BR-LED-018 forbids a hard lockout) and still demands a reason.
#   * a raised error — the caller asked something malformed, or no tenant is in
#     scope. Never softened into either of the above.
#
# This is BR-LED-041's ratified shape, one module over and for the same reason:
# `account_references` answers *"we cannot tell what points at this"* rather
# than *"0 references"*, and it cites **DEF-127 — a zero that means "I don't
# know"**. `bankrec_read._decimal_str` keeps the same line for money: *"None in,
# None out … `bank_total` is NULL for a batch the bank has not shown, and
# turning that into `"0.00"` is the DEF-127 defect."*
#
# ── WHAT IS NOT COUNTED HERE, NAMED SO SILENCE IS NOT READ AS "DONE" ───────
# **Cleared money that never reached a batch at all.** `bankrec_read.
# cuttable_days()` already finds it — drawer days holding cleared, positive,
# unbatched payments — and a month with uncut days can still report zero
# unreconciled BATCHES, because there are none. It is deliberately NOT folded
# into `unreconciled_batch_count`: this module's own ratified reasoning in
# `bankrec_read.batch_kpis` is that *"in-transit money is its own tile and is
# never folded into 'deposited' … adding them would produce one confident
# figure out of two different facts"*, and a count named for batches that also
# counted days would be exactly that. It wants its own checklist item and its
# own rule; BR-LED-006 fixes the five and does not include it, so it is
# REPORTED here rather than invented.


def _close_window(start: Any, end: Any, *, read: str) -> tuple[date, date]:
    """Validate a close window — two DATES, in order — or refuse.

    An empty count and an unanswerable one look identical on a screen, so a
    malformed window is never allowed to become `0`: it would tick a close
    checklist item green on arithmetic nobody asked for. Same posture as
    `bankrec_read.batch_queryset`, which refuses an unrecognised status rather
    than filtering to nothing.

    `datetime` is rejected as well as non-dates: BR-TEN-043 makes a period
    boundary a DATE the caller names, and a `datetime` compared against a
    `DateField` would silently drop its time and answer for a different day.
    """
    for label, value in (("start", start), ("end", end)):
        if not isinstance(value, date) or isinstance(value, datetime):
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="payments.close_seam.window_not_a_date",
                params={"field": label, "read": read, "got": type(value).__name__},
            )
    if end < start:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="payments.close_seam.window_backwards",
            params={"read": read, "start": start.isoformat(), "end": end.isoformat()},
        )
    return start, end


def unapplied_cash(start: date, end: date) -> dict[str, Any]:
    """Money this utility is HOLDING that no bill has claimed — `RB-109` step 3.

    Every payment posted into the window, less this module's own allocation rows
    against it. What is left is unapplied cash: real money in the bank that the
    receivables sub-ledger cannot point at a bill for.

    ⚠ **THE SUBTRACTION IS THE ONE `credit.credit_position` ALREADY DOES, DONE IN
    BULK.** That function answers it for ONE account, with a row lock, because a
    clerk is about to allocate. This answers it for the whole tenant, in two
    queries, because month-end reads every account and one query per account is
    how a close screen becomes a timeout (`NFR-3`: a T5 utility has 40,000 of
    them). The arithmetic is identical and it is deliberately not re-derived —
    two answers to *"what is unapplied"* is exactly the fault a tie-out exists
    to catch, and having them inside one module would be no better than having
    them in two.

    ⚠ **DEPOSITS ARE EXCLUDED AND THAT IS NOT A ROUNDING OF THE QUESTION.** A
    `deposit` payment is money held on purpose — it sits in the deposit-liability
    account and has its own tie-out row (`BR-LED-007`). Counting it as *unapplied*
    would report every healthy utility as holding hundreds of dollars nobody
    allocated, on a correct book, and the month-end runbook would refuse to close
    for ever. `PURPOSE_PREPAY` and `PURPOSE_PLAN_DOWN` are NOT excluded: both are
    bill money that has not met a bill yet, which is precisely what this is.

    ⚠ **ONLY CLEARED MONEY.** A `processing` payment has not settled and a
    `failed` or `reversed` one is not money at all. `PAYMENT_FROZEN_STATUSES` is
    this module's own existing set for *the money is real*, so the set is read
    from there rather than re-listed here.

    ⚠ **AND `cancelled` IS EXCLUDED BY NAME, BECAUSE THAT SET IS DERIVED AND
    GREW UNDER THIS QUERY WITHOUT ANYONE DECIDING (`DEF-PAY-6454`,
    `CR-137-BRC07` `P3.5`).** `PAYMENT_FROZEN_STATUSES` is
    *every status but `processing`*, so `payments/0036` adding a sixth status
    added it to this month-end tie-out too — on a line nobody edited, in a file
    nobody had to open. A cancelled payment is money that was **taken by
    mistake and undone**: it has an `amount`, a `posted_at` and a `bill`
    purpose, it will never carry an allocation, and it would therefore have sat
    in *unapplied cash* for ever, **overstating the figure a month-end refuses
    to close against**. Nothing has reached it yet — no `cancelled` row exists
    in any database — which is why this is a line of code rather than an
    incident.

    ⚠ **THE PARAGRAPH ABOVE AND THE SET IT READS DISAGREE ABOUT `failed` AND
    `reversed`, AND THAT IS NOT TOUCHED HERE.** *"A `failed` or `reversed` one
    is not money at all"* is this docstring's own sentence, and both are in
    `PAYMENT_FROZEN_STATUSES` and are counted today. Narrowing them would move
    a signed tie-out figure and is a finance decision, not a lane's; it is
    filed as `DEF-PAY-6454` with this fix rather than fixed quietly alongside
    it. **This change moves no existing number** — it only keeps a status that
    does not exist yet from joining one.


    The window is `posted_at`, the date the money entered the books — never
    `cleared_at`, which is when the bank agreed, and never `created_at`, which is
    when somebody typed it. A month-end tie-out compares against what was POSTED
    in the month, so the two sides have to be windowed on the same instant.
    """
    from django.db.models import Sum

    zero = Decimal("0")
    tenant_id = _tenant_id()
    payments = list(
        models.Payment.objects.filter(
            tenant_id=tenant_id,
            posted_at__date__gte=start,
            posted_at__date__lte=end,
            # CR-186-BRC10 (`DEF-PAY-10340`): the balance's counted set. This
            # read FROZEN-minus-cancelled until 2026-10-21, which counted a
            # `failed` cheque as unapplied cash that never reached the books.
            status__in=balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES,
        )
        .exclude(purpose=models.PURPOSE_DEPOSIT)
        .values("id", "account_id", "payment_no", "amount", "currency", "posted_at")
    )
    if not payments:
        return {"total": zero, "payment_count": 0, "currency": None, "payments": ()}

    allocated = {
        row["payment_id"]: row["total"] or zero
        for row in models.Allocation.objects.filter(
            tenant_id=tenant_id, payment_id__in=[one["id"] for one in payments]
        )
        .values("payment_id")
        .annotate(total=Sum("amount"))
    }

    rows: list[dict[str, Any]] = []
    total = zero
    currencies = set()
    for payment in payments:
        left = (payment["amount"] or zero) - allocated.get(payment["id"], zero)
        if left <= zero:
            continue
        total += left
        currencies.add(payment["currency"])
        rows.append(
            {
                "payment_no": payment["payment_no"],
                "account_id": str(payment["account_id"]),
                "amount": payment["amount"],
                "unapplied": left,
                "currency": payment["currency"],
                "posted_on": payment["posted_at"].date(),
            }
        )
    return {
        "total": total,
        "payment_count": len(rows),
        # Hard rule 2 — the CHAR(3) travels WITH the amount. `None` when the
        # rows disagree, because a sum across two currencies is not a number
        # (DEF-081), and the caller must say it cannot answer rather than print
        # a total with somebody's symbol in front of it.
        "currency": currencies.pop() if len(currencies) == 1 else None,
        "payments": tuple(rows),
    }


def unreconciled_batch_count(start: date, end: date) -> int | None:
    """BR-LED-006 *"batches reconciled"* — deposit batches of this window that
    are not yet reconciled. Published for `apps.ledger.close`.

    A batch is DONE at exactly one status. B2's `batch_status` has four and the
    other three are all outstanding work at close:

      * `in_transit` — cut, and the bank has not shown it yet;
      * `unmatched`  — a statement is in and this batch is not tied to a line;
      * `matched`    — a line is linked, and the difference is not yet worked
                       (BR-PAY-019 wants reason + GL before it may reconcile);
      * `reconciled` — LOCKED (BR-PAY-004), and the only one that is finished.

    So this counts `NOT reconciled` rather than listing the three, and a fifth
    status added later is outstanding by default — which is the fail-closed
    direction for a checklist that gates a month close.

    **The window is the batch's `deposited_on`** — BR-PAY-025 / the PO's RQ-5
    ruling make that the POSTING day (the physical drawer day), never the
    clearing day, and it is the same column S37 sorts on. Both boundary days
    are INSIDE the window; a close that dropped the 1st or the 31st would
    under-report the month by two drawer days.

    **This read ALWAYS answers**, and never `None`. The deposit register is
    wholly this module's: we cut every batch and we move every status, so
    "there are no batches in July" is a fact we hold rather than a gap in what
    someone else told us. Contrast `unmatched_bank_line_count` below, whose
    register only exists once a bank has sent us something — that one has a
    real unknown, and this one would be inventing doubt to imitate it.
    """
    tenant_id = _tenant_id()  # CLAUDE.md rule 1 — refuses when no tenant is set
    start, end = _close_window(start, end, read="unreconciled_batch_count")
    return (
        bankrec.DepositBatch.objects.filter(
            tenant_id=tenant_id,
            deposited_on__gte=start,
            deposited_on__lte=end,
        )
        .exclude(status=bankrec.BATCH_RECONCILED)
        .count()
    )


def unmatched_bank_line_count(start: date, end: date) -> int | None:
    """BR-LED-006 *"bank rec current"* — statement lines of this window tied to
    no deposit batch. Published for `apps.ledger.close`.

    An unmatched line is `bank_lines.deposit_batch_id IS NULL` — B2's own
    nullable link, and what "matched" means (`bankrec_models.BankLine`). It is
    either a line nobody has looked at or S38's fourth tile, *"Not in our
    system"*; both are outstanding reconciliation work and both count.

    **`None` WHEN NO STATEMENT COVERS THE WINDOW, AND THIS IS THE POINT OF THE
    WHOLE FILE.** Bank lines arrive only inside a `bank_statement_imports` row.
    If nobody has imported a statement overlapping these dates there are zero
    lines, and a plain `.count()` would answer `0` and tick *bank rec current*
    GREEN on a month the bank has never been asked about. That is DEF-127
    exactly — a zero that means "I don't know" — and it is the same refusal
    `bankrec_read._decimal_str` already makes for a batch the bank has not
    shown. So the register says it cannot answer, the ledger reports `unknown`,
    and the close still goes through with a reason (BR-LED-018).

    **Coverage is OVERLAP, not containment**, and that is deliberate. A
    statement is cut on the BANK's cycle — Jun 25 – Jul 24 is an ordinary file
    — and demanding a file that spans the whole fiscal month would make almost
    every real month `unknown` and buy nothing. One file touching the window is
    enough to make the window readable; how well it covers it is the clerk's
    judgement on S38, not an invented threshold here.

    Once a statement covers the window a `0` is a REAL zero: the bank has shown
    us these dates and every line is tied. That pair — the same integer meaning
    opposite things — is why the coverage test exists at all.
    """
    tenant_id = _tenant_id()  # CLAUDE.md rule 1 — refuses when no tenant is set
    start, end = _close_window(start, end, read="unmatched_bank_line_count")
    covered = bankrec.BankStatementImport.objects.filter(
        tenant_id=tenant_id,
        period_start__lte=end,
        period_end__gte=start,
    ).exists()
    if not covered:
        return None
    return bankrec.BankLine.objects.filter(
        tenant_id=tenant_id,
        deposit_batch__isnull=True,
        posted_on__gte=start,
        posted_on__lte=end,
    ).count()


# ═══════════════════════════════════════════════════════════════════════════
# CR-060 C19 / task T7d — WHICH CHARGE CLASSES A WINDOW'S PAYMENTS ACTUALLY MET
# ═══════════════════════════════════════════════════════════════════════════
#: Published for `apps.ledger.payments_seam`, which the dual-basis remittance
#: table (S41) reads. Named here as a constant so the contract is greppable from
#: BOTH sides of the boundary — the discipline every seam in this product uses.
COLLECTED_BY_CLASS_READ = "collected_by_class_for_invoices"


def collected_by_class_for_invoices(
    invoice_ids: tuple[Any, ...],
    *,
    line_class: str,
    start: date,
    end: date,
) -> dict[str, Any]:
    """How much of ONE charge class each named bill was PAID, in this window.

    `{"collected": {invoice_id: Decimal}, "allocated_without_breakdown":
      Decimal, "allocations_without_breakdown": int, "allocations_read": int}`

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THIS READS A RECORD. IT DOES NOT DECIDE HOW A PAYMENT MEETS A BILL. ║
    ╚══════════════════════════════════════════════════════════════════════╝
    The class order is BR-PAY-010's TENANT SETTING and `apps/payments/
    allocation.py` walked it at the moment the money moved; `allocation_classes`
    is what it wrote down (CR-060 C19, `payments/0015`). So a tenant filing on
    the *collected* basis gets what their own order produced, and the two signed
    rulings that disagree about a partial payment's tax (`OQ-174`'s *"tax
    first"* against BR-PAY-010's configurable order) do not have to be
    reconciled for this figure to exist — which is C19's stated disposition, in
    as many words: *"recording the breakdown makes the question moot"*.

    **THE WINDOW IS THE PAYMENT'S POSTING DATE**, never the allocation's
    creation timestamp and never the bill's. ⚠ **IT WAS THE CLEARING DATE UNTIL
    2026-10-21 (`DEF-PAY-10321`).** BR-LED-002's collected basis reads *"tax
    inside CLEARED payments via allocation"*, signed when *cleared* meant *the
    money arrived*; `CR-186-BRC10` redefined `cleared` as *its deposit batch was
    reconciled with the bank*, days later, and the PO ruled the same day
    (decision log *"Two CR-186 follow-up rulings"*, item 2) that the
    collected-tax basis moves to the posting date and counts `posted` +
    `cleared`. Shown: *"a card payment taken 14 Oct and reconciled 16 Oct"* —
    its tax is collected in the 14 Oct window, before and after the
    reconciliation. `apps/ledger/reporting` declares the basis on the response.

    **A REVERSAL SUBTRACTS ITSELF, AND THE FILTER HAS TO LET IT.** A bounced
    cheque writes a mirror allocation with a NEGATIVE breakdown
    (`apps/payments/reversal.py`) on a NEW payment row whose status is
    `reversed`, not `cleared` — so a filter reading `status == cleared` keeps the
    original's positive breakdown and drops the mirror, and the report claims tax
    collected on money that came back. That is why the status clause below is
    the balance's counted set (`posted`, `cleared`, `reversed`) and not the
    ruling's two words alone, and it was measured rather than reasoned: see TC-5.

    ⚠ **`allocated_without_breakdown` IS THE HONEST PART OF THIS ANSWER AND THE
    CALLER MUST REPORT IT.** Three kinds of allocation carry no class rows:

      * every allocation written BEFORE `payments/0015` landed on 2026-09-02 —
        the breakdown was computed and stored only in the audit payload, which
        is pruned, so it cannot be backfilled and never will be;
      * an application of an existing account CREDIT to a bill
        (`apps/payments/credit.py`), and a release of one
        (`apps/payments/allocation_release.py`). Neither runs through
        `allocate_payment`, so neither has a breakdown to record, and
        **computing one here would be a second implementation of the class walk
        living downstream of the first** — the shape CR-060 §13's third
        exclusion forbids and the reason `billing/posting_seam` refuses to
        re-resolve a GL account it was handed.

    So the figure this returns is a **FLOOR**: the collected tax we can prove.
    The unbreakdown'd total travels beside it so the report can say how much
    money it could not classify instead of quietly reporting a smaller number as
    though it were the whole month. A caller that drops it is publishing a tax
    figure with a silent gap in it.
    """
    tenant_id = _tenant_id()  # CLAUDE.md rule 1 — refuses when no tenant is set
    ids = tuple(invoice_ids)
    if not ids:
        return {
            "collected": {},
            "allocated_without_breakdown": Decimal("0"),
            "allocations_without_breakdown": 0,
            "allocations_read": 0,
        }
    # THE UTILITY'S OWN DAY, not UTC — `_day_bounds` is the one implementation
    # of that (DEF-094's sweep), and a window bucketed differently here from the
    # S33 list a clerk opens is two screens disagreeing about the same money.
    # `__lt next_day` rather than `__lte end` for the reason the list filter
    # states: a bound reading "to Aug 31" that dropped everything posted DURING
    # Aug 31 reads as a data gap, and this one would under-report a tax return.
    window_start = _day_bounds(start.isoformat())
    window_end = _next_day(_day_bounds(end.isoformat()))
    rows = (
        models.Allocation.objects.filter(
            tenant_id=tenant_id,
            invoice_id__in=ids,
            # DEF-PAY-10321 — the POSTING date (PO ruling 2026-10-21); this read
            # `payment__cleared_at` until then.
            payment__posted_at__gte=window_start,
            payment__posted_at__lt=window_end,
            payment__status__in=balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES,
        )
        # ⚠ **NOT `status == cleared`, AND THIS WAS PROVED RATHER THAN
        # REASONED.** The first draft filtered on `cleared` alone and a bounced
        # cheque then left its collected tax standing: a reversal writes a NEW
        # payment row at `status='reversed'` (`apps/payments/reversal.py`), so
        # its NEGATIVE breakdown was filtered out while the original's positive
        # one stayed, and the report read **20.97 collected on money that had
        # come back**. The test that found it is
        # `tests/test_cr060_t7d_allocation_classes.py` TC-5.
        #
        # **WHAT THE FILTER MEANS SINCE 2026-10-21: money taken and applied, in
        # this window, by posting date** — `posted`, `cleared` and the negative
        # `reversed` mirror, the balance's own counted set (`balance_rule`).
        # It was an exclude of `processing` and `failed` over a clearing-date
        # window until then; `cancelled` was outside it only because a
        # cancelled payment never cleared. On the posting date it would be
        # inside, so the set is now an ALLOW list and `cancelled` — the
        # original and its mirror both — is out by name.
        .prefetch_related("classes")
        .only("id", "invoice_id", "amount")
    )
    collected: dict[str, Decimal] = {}
    unclassified = Decimal("0")
    unclassified_rows = 0
    read = 0
    for row in rows:
        read += 1
        children = list(row.classes.all())
        if not children:
            unclassified += row.amount
            unclassified_rows += 1
            continue
        for child in children:
            if child.line_class != line_class:
                continue
            key = str(row.invoice_id)
            collected[key] = collected.get(key, Decimal("0")) + child.amount
    return {
        "collected": collected,
        "allocated_without_breakdown": unclassified,
        "allocations_without_breakdown": unclassified_rows,
        "allocations_read": read,
    }


# ── CR-059 CS-2 · the staged remittance import (S35 · S33) ──────────────────


def payment_import_batch_dict(batch_id: Any, *, with_rows: bool = False) -> dict[str, Any]:
    """One import batch as the S35 modal reads it — counts, then rows.

    ⚠ **THE COUNTS ARE RECOMPUTED FROM THE ROWS, NOT READ OFF THE BATCH.**
    `payment_import_batches.counts` is a cache for a list screen; this is the
    figure a clerk decides on, and a denormalised number that has drifted from
    its rows is the shape this repo has been bitten by more than once. The two
    are written together by `payment_import.validate_batch` and they should
    agree — but "should" is not what a preview is allowed to rest on.

    ⚠ **`total_matched` IS THE CLEAN ROWS ONLY**, and it is the number the
    commit will actually post. A total that included review rows would tell a
    clerk that $18,240.55 is about to be banked when $2,113.90 of it is still
    waiting for somebody to say whose it is.

    Money travels twice, both as STRINGS (CLAUDE.md rule 2): the stored six-place
    decimal and the two-place display figure beside it. The client renders
    neither — `rating.selectors._display_money` records why (DEF-364: a percent
    shipped as `0.015000` and a customer read `0.015000`).
    """
    batch = models.PaymentImportBatch.objects.filter(
        tenant_id=_tenant_id(), pk=batch_id
    ).first()
    if batch is None:
        # A 404 rather than a refusal, and the two are NOT interchangeable here:
        # a batch belonging to another tenant and a batch that never existed must
        # be indistinguishable (G4, hard rule 1), and a refusal naming the batch
        # would tell a caller that somebody else's file exists.
        raise errors.NotFoundError()
    rows = list(
        models.PaymentImportRow.objects.filter(
            tenant_id=batch.tenant_id, batch_id=batch.pk
        ).order_by("row_no")
    )
    counts = {state: 0 for state in models.ROW_STATES}
    committed = 0
    matched = Decimal("0")
    for row in rows:
        if row.match_state in counts:
            counts[row.match_state] += 1
        if row.payment_id is not None:
            committed += 1
        if row.match_state == models.ROW_CLEAN and row.amount is not None:
            matched += row.amount
    counts["committed"] = committed
    counts["rows"] = len(rows)

    served: dict[str, Any] = {
        "batch_id": str(batch.pk),
        "file_name": batch.file_name,
        # 🔒 The file's identity, served so a clerk can see the same file was
        # refused rather than being told "already imported" with no way to check.
        "file_hash": batch.file_hash,
        "tags": batch.tags,
        "source_kind": batch.source_kind,
        "status": batch.status,
        "counts": counts,
        "total_matched": _decimal_str(matched),
        "total_matched_display": _display_money(matched),
        "committed_at": _iso(batch.committed_at),
        "uploaded_at": _iso(batch.uploaded_at),
    }
    if with_rows:
        served["rows"] = [payment_import_row_dict(row) for row in rows]
    return served


def payment_import_row_dict(row: Any) -> dict[str, Any]:
    """One staged cheque, with what the file said BESIDE what we made of it.

    ⚠ **THE RAW VALUES ARE ON THE WIRE AND THAT IS THE POINT OF THE SCREEN.** A
    row a person has to work is one where our reading was not good enough, so
    the first thing they need is what the file actually said — not our
    interpretation, which is the thing under suspicion.

    ⚠ **`match_method` TRAVELS, so a screen can tell a SUGGESTION from a FACT.**
    A row matched on `name_amount` has an account filled in and must not be
    rendered the same way as one matched on `account_no`: the first is a guess
    this module refuses to post on (CS-2's second rule) and the second is the
    customer quoting our own number.
    """
    return {
        "row_id": str(row.pk),
        "row_no": row.row_no,
        "raw": {
            "account_ref": row.account_ref_raw,
            "invoice_ref": row.invoice_ref_raw,
            "payer_name": row.payer_name_raw,
            "amount": row.amount_raw,
            "paid_on": row.paid_on_raw,
            "reference": row.reference_raw,
        },
        "amount": _decimal_str(row.amount),
        "amount_display": _display_money(row.amount),
        "paid_on": row.paid_on.isoformat() if row.paid_on else None,
        "reference": row.reference,
        "account_id": str(row.account_id) if row.account_id else None,
        "invoice_id": str(row.invoice_id) if row.invoice_id else None,
        "match_method": row.match_method,
        "match_state": row.match_state,
        "match_detail": row.match_detail,
        "payment_id": str(row.payment_id) if row.payment_id else None,
        "commit_error": row.commit_error,
    }


# ═══════════════════════════════════════════════════════════════════════════
# P5.8 — THE PRINTED PAYMENT NUMBER, PUBLISHED FOR THE LEDGER TO ASK FOR
# ═══════════════════════════════════════════════════════════════════════════
def payment_numbers_for(ids: Any) -> dict[str, str]:
    """`{payment_id: payment_no}` for the payments this tenant can read.

    Finance blueprint p018 `P5.8`. `apps/ledger/reporting.account_ledger` shows
    a journal line's `source_id` in its **Reference** column because a UUID is
    the only thing the line carries; `apps/ledger` may not read this module's
    ORM (`BR-TEN-013`, gate `G6`), so payments publishes the read and the ledger
    resolves it by name through `apps/ledger/payments_seam.py`.

    ⚠ **A MISS IS AN ABSENT KEY AND NEVER THE UUID**, for the reason
    `apps/integrations/seams/ledger._document_numbers` already states about the
    wire: the whole task is *document number, not internal id*, so an id that
    resolves to nothing must not come back wearing the name of its answer.
    Another tenant's id, an unknown id and a payment with a NULL `payment_no`
    are one and the same absence here, which is `BR-TEN-003` — a cross-tenant
    read is an absence, and telling the three apart would be a membership
    oracle over somebody else's money.

    One query for the whole ask; `{}` for an empty one, and no query for it.
    """
    wanted = _payment_document_ids(ids)
    if not wanted:
        return {}
    rows = models.Payment.objects.filter(
        tenant_id=_tenant_id(), id__in=wanted
    ).values_list("id", "payment_no")
    return {str(row_id): str(number) for row_id, number in rows if number}


def _payment_document_ids(ids: Any) -> list[str]:
    """The ask, de-duplicated and SORTED, as strings.

    Sorted so two identical asks build one SQL string rather than two; empty
    ids dropped because a journal line with no `source_id` is an ordinary row
    and not a question for the database.
    """
    if not ids:
        return []
    return sorted({str(one) for one in ids if one})



# ── `CR-142-BRC07` `P6.11` wave 3 · R43's COLLECTED column ──────────────────
#
# ⚠ **THIS IS THE READ `apps/ledger/reporting.GAP_ALLOCATION_PERIOD` ASKS FOR,
# BY NAME.** That gap has said since 2026-08 that BR-REP-009's collection
# percentage *"is not derivable"* from the books and named its own remedy in
# its `wanted_reads`:
#
#     apps.payments.selectors.allocated_to_invoices_issued_between(
#         start: date, end: date) -> Decimal
#
# It is written here rather than in the ledger because the period attribution
# is PAYMENTS' fact: a journal entry credits AR in one lump with `source_id` =
# the payment, so the books record that cash reduced AR and never WHICH bill it
# met. `allocations` records exactly that, one row per (payment, invoice).
#
# ⚠ **THE LEDGER'S OWN `collection_pct` IS UNCHANGED AND STAYS `None`.** This
# read exists and that figure could now be computed — but `revenue_and_ar` is a
# shipped, signed read behind S36, and moving a KPI from *absent with a reason*
# to a number is a behaviour change that belongs to whoever owns that screen,
# not to a report lane passing through. `GAP_ALLOCATION_PERIOD` therefore stays
# where it is and stays true of THAT read.
def allocated_to_invoices_issued_between(*, start: date, end: date) -> Decimal:
    """Cash APPLIED to bills issued inside the window — BR-REP-009's numerator.

    *"Collection % = cash applied to bills in period ÷ billed in period"* (PO
    RQ-1, 2026-08-08). The denominator is the ledger's; this is the top half,
    and it is **not** *cash received in the window*: a payment landing on 2 July
    against a bill issued on 28 June belongs to JUNE's collection rate, and a
    figure summed over payment dates would put it in July's.

    ⚠ **THE INVOICE SIDE IS A SUBQUERY AND NEVER A MATERIALISED LIST OF IDS.**
    At the top of the ICP one period holds about forty thousand bills, so an
    `id__in=[...]` built in Python would be a forty-thousand-element IN clause
    per period and twelve of them per run. `billing_seam` hands back a
    QUERYSET — the same shape `OPEN_AMOUNTS_QUERYSET_READ` already uses — and
    the database resolves the whole thing in one statement.

    ⚠ **A REVERSING ROW IS INCLUDED AND MUST BE.** BR-PAY-031 makes a reapply
    *"reversing allocation rows + new rows, never edits"*, so the negative row
    is how a mistaken application is undone; excluding it would report money as
    collected that was taken back.

    Returns `Decimal("0")` for a window with no applications, which is a real
    answer. The UNANSWERABLE case — billing publishing no invoice queryset —
    raises, because a caller silently reading zero would print a 0% collection
    rate over a book that collected.
    """
    invoices = billing_seam.invoices_issued_between(start=start, end=end)
    if invoices is None:
        raise errors.SysError(
            errors.SYS_INTERNAL, message_key="payments.billing_read_unavailable"
        )
    total = models.Allocation.objects.filter(
        tenant_id=_tenant_id(), invoice_id__in=invoices.values("id")
    ).aggregate(total=Sum("amount"))["total"]
    return total if total is not None else Decimal("0")


def payments_for_bills(
    invoice_ids: Any, *, entry_reference: str | None = None
) -> list[dict[str, Any]]:
    """Every payment that MET these bills, or was TAKEN FOR them — one row each.

    ``CR-163-BRC10`` item 20 (PO 2026-10-02, the New Connection detail's
    *Paid so far*): *"table of each payment — date, method (e.g. Cheque #4471),
    type, amount, receipt no. — each row links to the payment record"*. Until
    this read existed the build record could state only an allocated SUM, and
    its own docstring said so (``connection_record._money``).

    **TWO WAYS A PAYMENT BELONGS TO A BUILD, AND BOTH ARE THIS MODULE'S OWN
    FACTS.** (1) it has an ``allocations`` row against one of ``invoice_ids``;
    (2) it was recorded through the build's own door, whose idempotency key is
    ``inbound_payment_key(source="entry", reference=entry_reference)`` — hard
    rule 6's one key. The second matters because a cheque handed over at the
    counter is ``processing`` until it clears (``BR-PAY-021``) and meets NO bill
    meanwhile: listing allocations alone would hide the cheque the clerk is
    looking at.

    ``amount`` is what met THESE bills where anything did (net of reversing
    rows, ``BR-PAY-031``) and the payment's own amount otherwise, and
    ``applied`` says which, so a screen never presents one as the other. Money
    is served as decimal STRINGS at stored scale (hard rule 2); the caller pairs
    them. ``payment_no`` is the receipt number and the record's address (B14
    rule 31) — ``id`` travels for an ``href`` only.

    Tenant-scoped BY NAME first and by RLS second (hard rule 1).
    """
    from apps.payments import idempotency

    tenant_id = _tenant_id()
    ids = [str(one) for one in (invoice_ids or []) if one]
    allocated: dict[str, Decimal] = {}
    if ids:
        for row in (
            models.Allocation.objects.filter(tenant_id=tenant_id, invoice_id__in=ids)
            .values("payment_id")
            .annotate(total=Sum("amount"))
        ):
            allocated[str(row["payment_id"])] = row["total"] or Decimal("0")
    wanted = Q(pk__in=list(allocated))
    if entry_reference:
        key = idempotency.inbound_payment_key(
            source=idempotency.SOURCE_ENTRY, reference=entry_reference
        )
        # ⊕ `DEF-MET-9224` — and every payment the request's own *Take
        # payment* recorded, whose staff-entry key is the build's reference
        # plus `:take:<token>`. A cheque taken there is `processing` and meets
        # no bill, so without this the clerk's own cheque vanished from *Paid
        # so far* — the exact case the paragraph above names.
        wanted |= Q(webhook_key=key) | Q(webhook_key__startswith=f"{key}:take:")
    rows = (
        models.Payment.objects.filter(tenant_id=tenant_id)
        .filter(wanted)
        .select_related("method")
        .order_by("posted_at", "payment_no")
    )
    out: list[dict[str, Any]] = []
    for payment in rows:
        met = allocated.get(str(payment.pk))
        out.append(
            {
                "id": str(payment.pk),
                "payment_no": payment.payment_no,
                "posted_at": payment.posted_at.isoformat() if payment.posted_at else None,
                "method_code": payment.method.code if payment.method_id else None,
                "method_name": payment.method.name if payment.method_id else None,
                "confirmation": payment.confirmation,
                "type": payment.type,
                "purpose": payment.purpose,
                "status": payment.status,
                "amount": str(met if met is not None else payment.amount),
                "applied": met is not None,
                "currency": payment.currency,
            }
        )
    return out


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-004@0f1a7c3 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-01-record-payments.md — US-PAY-001 + US-PAY-004 — · 04-docs/05-modules/08-payments/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §1 + §2.9 · 04-docs/01-spec/11-api-contracts.md Addendum r2; co-packet US-PAY-001, same four sources)
# generated: 2026-08-11 by story-coder (W4 payments API lane — the read layer the S33 ledger had never had)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_004_payments_api.py (RED-proved first — verbatim failures in the lane report) · pytest tests -m isolation✔ · pytest tests -m golden✔ · run_gates✔
# exceptions: (1) `receipt_no` and `deposit_batch_id` are NULL on every row — BR-PAY-024's receipt queue is US-PAY-025's and `deposit_batches` is EP-PAY-06's; both are served under their contracted names so the screen can state the absence · (2) the FILTER TOTAL refuses on zero rows, on mixed currencies and on any signed credit/adjustment row (B2 O-4 residue) rather than summing a figure that could be wrong by twice a row · (3) `f.cleared_from/to` EXCLUDE a payment that has not cleared — "not cleared yet" is not "cleared outside the window" (BR-PAY-021) · (4) the account-level BALANCE, the "days late" figure and the S32 KPI strip are NOT served here: the first is customers' cached column (B1/DB-16), the second is BR-PAY-032's `today − oldest unpaid due date` and needs a clock this path may not read (G6/BR-TEN-043), and the third is US-PAY-005's own story
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
