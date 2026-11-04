# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-019 (S7 — the landing screen; every tile carries the owner's
#           figure or reports that it cannot answer)   Screens: S7
# Rules:    BR-REP-024 (a dashboard tile never computes a figure) · BR-REP-002
#           (read-models only) · BR-REP-001 (every money figure labels its date
#           basis) · BR-REP-012 (Active connections = Active + Marked
#           disconnect + Vacation hold) · BR-TEN-022 (the period is COMPUTED
#           from fiscal settings, never stored) · BR-TEN-043 (a window is an
#           argument, never a clock) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 2 (NUMERIC(18,6) + CHAR(3), never a float)
# Tests:    06-backend/tests/test_us_rep_019_dashboard.py
# Impacts:  apps/reports/api.py (the only caller) · apps/reports/dashboard_seams.py
#           (every fact arrives through it) · 06-backend/openapi/schema.json
# ───────────────────────────────────────────────────────
"""`GET /dashboard/summary` — S7's read model, which owns no fact of its own.

A11 puts this route on S7 (*"S7 | dashboard | GET /dashboard/summary | period |
KPIs, activity"*) and 11b §1 amends it to carry a **basis label on every money
KPI** (BR-REP-001). This module answers it, and the shape of the answer is the
whole design:

    every KPI is a VALUE or a NULL, and every NULL has a matching entry in
    `unavailable` naming a stable `code`, the rule it comes from, and — where a
    neighbouring module would have to publish a read — that read BY NAME.

**No figure here is computed.** There is no `+` on a money value in this file,
no ratio, no comparison of two amounts. `still_owed` is the ledger's; `bills` is
billing's; `returned_mail` is payments'. What this module does is ASK the owners
(through `dashboard_seams`, resolved by name at call time) and assemble the
answers, keeping every absence an absence.

════════════════════════════════════════════════════════════════════════════
WHY A DASHBOARD IS THE WORST PLACE IN THE PRODUCT TO COMPUTE A NUMBER
════════════════════════════════════════════════════════════════════════════
DEF-104: four surfaces disagreed about one customer's balance — the account
screen said **$0.00** while the ledger held an issued, unpaid **$108.88**. Each
surface had derived the figure for itself and each was internally consistent.

DEF-075: a seam that could not answer returned `False`, the caller read it as
"there is nothing", and a tenant holding issued bill BL-2606-000001 (**108.88
USD**) re-denominated its books at HTTP 200.

S7 is the first screen after every sign-in and shows a dozen such claims at
once. If it derived any one of them it would become a fifth opinion on the busiest
surface in the app. So BR-REP-024 forbids it, and this file is where that is
enforced: the only transformation applied to an owner's figure is
`wire.money()`, which turns a `Decimal` into its exact decimal string.

════════════════════════════════════════════════════════════════════════════
WHAT ANSWERS AND WHAT REFUSES, TODAY — and why each refusal is not a zero
════════════════════════════════════════════════════════════════════════════
ANSWERS (owner → figure):
  ledger.reporting.revenue_and_ar  → `ar_outstanding` (= `kpis.still_owed`, the
      AR-control total S36 shows and the tie-out figure) · `period_revenue`
      (= `kpis.billed`) · `service_mix` (= `revenue_by_service`). ONE call, so
      the strip and the panel cannot straddle a posting and disagree. It also
      publishes the `currency` its figures ARE (DEF-081), which is what labels
      them — never the tenant's declared code over a book denominated in
      something else.
  billing.selectors.invoices_rollup → `bills` · `unresolved_from_last_run`.
  payments.summary.summary          → `returned_mail` · `autopay_scheduled`.
  customers.selectors.accounts_rollup → `accounts_on_file` — under its OWN name,
      never under Active connections.

REFUSES (and the reason each is a refusal rather than a zero):
  `unbilled_reads`      metering publishes no unbilled-read count. Counting from
                        here means querying metering's tables (B1 forbids it,
                        G6 greps for it) and creates a second counter of
                        metering's own fact.
  `active_connections`  BR-REP-012 wants Active + Marked disconnect + Vacation
                        hold. `accounts_rollup()["accounts"]` is right there and
                        counts Pending activation and Closed too, so under this
                        label it is a WRONG number, not a rounded one.
  `failed_payments`     `summary().failed` is sliced `[:50]` for S32's panel. A
                        tenant with 80 failures would be told **50** on the
                        first screen after sign-in.
  `aging`               the ledger's own null: a journal line carries no due
                        date. Passed through with its reason, and QUANTIFIED by
                        `ar_outstanding` — the total the missing bands would
                        have to add up to (the posture S60 already ships). An
                        empty four-band table reads as "nothing is overdue".
  `activity`            no module publishes an event read-model at all, so there
                        is no owner to name. Reported against US-REP-016 §1.

════════════════════════════════════════════════════════════════════════════
THE WINDOW IS CHOSEN, STATED, AND NEVER GUESSED (CR-015, 2026-08-19)
════════════════════════════════════════════════════════════════════════════
⚠ **THIS SECTION IS A REVERSAL AND THE OLD TEXT IS KEPT, because the next agent
will otherwise "correct" the build back to it.** It used to read:

    *"The window is the tenant's own `current_period` … When a tenant has no
    fiscal calendar configured, every money figure is served null with
    `fiscal_period_not_configured` and none is computed over a substituted
    calendar month: a KPI headed 'this period' that is not the tenant's period
    is a wrong number wearing a right label."*

The reasoning in that last clause is still exactly right, and CR-015 removes its
PREMISE rather than contradicting it. The failure was never the substitution; it
was that the screen could not SAY which window it was showing. So:

  · the operator CHOOSES the window from a published vocabulary
    (`dashboard_period`) — last 30 days · this period ·  ⚠ **THIS LINE LISTED A
    FOURTH, `last completed cycle`, UNTIL 2026-09-26** (`CR-142-BRC07` `P0.15`);
    `CR-029` `D8①` withdrew it on 2026-08-23 and `OPTION_ORDER` has offered
    three ever since —
    last period — defaulting to the utility's own unit of work;
  · the screen STATES the chosen window, in dates, above the figures, which is
    the PO's own condition for allowing the choice at all (CR-015: *"the
    selected period is stated prominently, not buried in a filter control"*),
    because a dashboard that differs from Finance is only a bug when a person
    cannot see that the two are looking at different weeks;
  · a tenant with NO fiscal calendar is no longer a page of nulls. It loses two
    of the four OPTIONS and keeps its figures, correctly labelled with the dates
    they cover. `fiscal_period_not_configured` moved to
    `dashboard_period.GAP_NO_ACCOUNTING_PERIOD` and now says that.

BR-TEN-022 is untouched: every accounting window on the menu is still COMPUTED
from the tenant's fiscal settings and never stored, and it is still the same
read S36, S59 and S60 head their pages with.
"""

from datetime import date, timedelta
from collections.abc import Callable
from typing import Any

from core.tenancy import current_tenant_id

from apps.ledger import wire

from . import dashboard_format as fmt
from . import dashboard_period as period_vocab
from . import dashboard_regions as regions
from . import dashboard_seams as seams

#: BR-REP-001. Everything this screen shows in money is billing-side — AR,
#: revenue, the service slice — and therefore POSTING basis. The label rides on
#: the payload rather than in a caption a screen may forget, exactly as
#: `apps/ledger/reporting.py` publishes it.
BASIS_POSTING = "posting"

# ── The gap catalogue ───────────────────────────────────────────────────────
# Each entry is the shape `apps/billing/posting_seam.py` established and
# `apps/ledger/reporting.py` reuses: a stable machine `code` the SCREEN keys its
# own translated sentence on (TD-16/B8 — the server sends keys, the UI renders
# language), the `br_ref` it comes from, `detail` in prose for the next agent,
# and `wanted_reads` naming the read that closes it BY NAME so the day it exists
# the gap closes with no edit on either side.

GAP_UNBILLED_READS = {
    "code": "unbilled_read_count_is_not_published_by_metering",
    "br_ref": "BR-REP-002 · BR-REP-024",
    "detail": (
        "The prototype's dashboard shows an unbilled-reads count and a pending-routes "
        "count. Metering owns `meter_reads` and publishes a paginated LIST for S25; it "
        "publishes no count of committed-but-unbilled reads. Counting them here would "
        "mean the reports module querying metering's tables, which B1 forbids, and would "
        "create a second counter of metering's own fact — DEF-104's shape."
    ),
    "wanted_reads": ("apps.metering.selectors.unbilled_read_rollup",),
}

GAP_ACTIVE_CONNECTIONS = {
    "code": "active_connection_classes_are_not_published_by_customers",
    "br_ref": "BR-REP-012",
    "detail": (
        "BR-REP-012 defines Active connections as Active + Marked disconnect + Vacation "
        "hold, with Pending activation and Closed excluded. Customers publishes a total "
        "account count and no per-status-class breakdown. The total is NOT substituted: "
        "it includes the two classes the rule excludes, so under this label it would be a "
        "wrong figure rather than an approximate one."
    ),
    "wanted_reads": ("apps.customers.selectors.account_status_class_counts",),
}

GAP_FAILED_PAYMENTS = {
    "code": "failed_payment_count_is_not_published_by_payments",
    "br_ref": "BR-REP-002 · BR-REP-024",
    "detail": (
        "Payments publishes the fifty most recent failed payments as a LIST for the S32 "
        "panel (`summary().failed` is sliced [:50]). Its length is a count of rows chosen "
        "for a screen, not of failed payments: a tenant with eighty failures would read "
        "50 on the first screen after sign-in, which is a false number rather than a "
        "smaller true one."
    ),
    "wanted_reads": ("apps.payments.summary.failed_payment_count",),
}

#: ⚠ **SUPERSEDED BY CR-012, 2026-08-18 — and kept as a CORRECTED record rather
#: than deleted, because hard-won law 1 is about exactly this: a note claiming a
#: guarantee (or, here, an absence) is not the thing itself.**
#:
#: It used to read *"No module in this product publishes an event read-model, so
#: there is no owner to ask — this is not an unwired seam, it is an unbuilt read
#: model"*. **That was true of the OPERATIONAL modules and was never true of
#: `apps.audit`**, which has published `audit_queryset` and `audit_page` since
#: the S61 viewer shipped. The panel now reads them (BR-REP-031).
#:
#: The half that is STILL true moved to `dashboard_regions.GAP_ACTIVITY_AMOUNT`:
#: `audit_log` carries no money column, so every activity row renders an em-dash
#: rather than an amount derived from a stored before/after diff.
#: ⚠ **SUPERSEDED BY CR-012, 2026-08-18 — and kept as a CORRECTED record rather
#: than deleted, because hard-won law 1 is about exactly this: a note claiming a
#: guarantee (or, here, an absence) is not the thing itself.**
#:
#: It used to read *"No module in this product publishes an event read-model, so
#: there is no owner to ask — this is not an unwired seam, it is an unbuilt read
#: model"*. **That was true of the OPERATIONAL modules and was never true of
#: `apps.audit`**, which has published `audit_queryset` and `audit_page` since
#: the S61 viewer shipped. The panel now reads them (BR-REP-031).
#:
#: The half that is STILL true moved to `dashboard_regions.GAP_ACTIVITY_AMOUNT`:
#: `audit_log` carries no money column, so every activity row renders an em-dash
#: rather than an amount derived from a stored before/after diff.
GAP_ACTIVITY = {
    "code": "activity_feed_has_no_event_read_model",
    "br_ref": "US-REP-016 §1 · SUPERSEDED by BR-REP-031 (CR-012, 2026-08-18)",
    "detail": (
        "SUPERSEDED. The Recent-activity panel is built and reads the audit log "
        "(BR-REP-031). This entry is emitted by nothing; the code is retained so a "
        "client still keying a sentence on it does not go blank."
    ),
    "wanted_reads": (),
}

#: ⚠ **SUPERSEDED BY CR-015, 2026-08-19 — and kept as a CORRECTED record rather
#: than deleted (hard-won law 1).**
#:
#: It used to be emitted whenever the tenant had no fiscal calendar, and it meant
#: *"every money figure on this screen is null"*. That was right while the screen
#: could report over exactly one window and could not say which: a KPI headed
#: *"this period"* over a substituted calendar month is a wrong number wearing a
#: right label.
#:
#: CR-015 removed the premise. The screen now STATES the window it is reporting
#: over, in dates, above the figures — so a tenant with no fiscal calendar is
#: shown its last completed cycle or its last thirty days, correctly labelled,
#: instead of a page of nulls. The code MOVED to
#: `dashboard_period.GAP_NO_ACCOUNTING_PERIOD`, where it now means *"two of the
#: four period options cannot be offered"*, which is the fact that is still true.
GAP_NO_PERIOD = dict(period_vocab.GAP_NO_ACCOUNTING_PERIOD)

GAP_LEDGER_UNWIRED = {
    "code": "ledger_read_model_is_not_published",
    "br_ref": "BR-REP-002",
    "detail": (
        "`apps.ledger.reporting.revenue_and_ar` does not resolve on this deployment, so "
        "no money figure on this screen has an owner to come from. Nothing falls back to "
        "`accounts.balance` — that cached column is exactly where DEF-104's $0.00 came "
        "from while the ledger held an issued, unpaid $108.88."
    ),
    "wanted_reads": ("apps.ledger.reporting.revenue_and_ar",),
}


def _day(value: Any) -> date | None:
    """One ISO calendar day as a `date`. `current_period` serves ISO STRINGS.

    Parsed rather than passed through, because a string reaching
    `revenue_and_ar` would be compared against `journal_entries.book_date` by
    the database's own coercion rules instead of Python's — the class of
    silent, environment-dependent difference that has no business inside a
    money window.
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _window(period: dict[str, Any] | None) -> tuple[date, date] | None:
    """`current_period`'s two days, or None when the tenant has no calendar."""
    if not period:
        return None
    start = _day(period.get("start"))
    end = _day(period.get("end"))
    if start is None or end is None:
        return None
    return start, end


def _once(read: Callable[[], Any]) -> Callable[[], Any]:
    """Call an owner's read AT MOST ONCE and replay its outcome — value OR error.

    Both halves matter. Replaying the VALUE is what stops the KPI strip and the
    service-mix panel from making two queries that could straddle a posting and
    disagree. Replaying the ERROR is what lets `regions.guard` contain a failing
    owner to its own panel (BR-REP-028) while the page body, which asked first,
    carried on with an absence.
    """
    box: dict[str, Any] = {}

    def call() -> Any:
        if not box:
            try:
                box["value"] = read()
            except Exception as exc:  # noqa: BLE001 — replayed, never swallowed
                box["error"] = exc
        if "error" in box:
            raise box["error"]
        return box["value"]

    return call


def _quiet(call: Callable[[], Any]) -> Any:
    """One memoised read for the PAGE BODY, where a failure is an absence.

    The body's job is the legacy top-level members and the KPI figures, and each
    of those already has a null-with-a-reason shape for "the owner cannot
    answer". A raise here would blank the whole screen, which is the acceptance
    criterion inverted — so it is turned into the absence the body already knows
    how to render, and the REGION that needs the same read still reports the
    real failure through `guard`.
    """
    try:
        return call()
    except Exception:  # noqa: BLE001 — the region reports it; see the docstring
        return None


def dashboard_summary(
    *,
    as_of: date | None = None,
    period: str | None = None,
    role: str | None = None,
) -> dict[str, Any]:
    """Everything S7 renders — each figure the owner's, each null with a reason.

    ════════════════════════════════════════════════════════════════════════
    THE TWO ARGUMENTS, AND WHY THEY ARE DIFFERENT THINGS
    ════════════════════════════════════════════════════════════════════════
    `as_of`   the READ MOMENT — *when* the figures are being asked for. It is an
              argument rather than a clock (BR-TEN-043) for the same reason
              `payments.summary` takes one: a dashboard that cannot be asked for
              last month cannot be reconciled against last month's day-end, and
              a read model that reads a clock inside itself cannot be tested
              against a signed figure at all. Absent ⇒ the tenant's own today,
              resolved by tenancy in the UTILITY's timezone, read ONCE here and
              turned into a value immediately.
    `period`  WHICH WINDOW to report over — one of `dashboard_period`'s stable
              option ids. Absent, unknown or no longer available ⇒ the ruled
              default (BR-SHL-011: fall back, never refuse).

    ⚠ **THIS FUNCTION USED TO SAY "It does NOT accept a window"** — *"S7 is the
    landing screen and has no parameter bar … a period picker on the landing
    screen would be a control that changes a number nobody asked to change."*
    **CR-015 REVERSES THAT, and the reversal is the PO's** (2026-08-19):

        *"If we allow this then there is now way user can see previous values
        and they will be confuse what is dashbaord is saying - so we will ahve
        to allow period filter on dashbaord."*

    The old posture was not wrong about the risk; it was wrong about the cost.
    A fixed calendar-month window on a screen that reports **cycle-shaped work**
    shows a real utility almost nothing for the first week of every month,
    forever — bills go out on the 25th, the month rolls over, and revenue reads
    near zero with nothing broken. See `dashboard_period` for the full case.

    ════════════════════════════════════════════════════════════════════════
    `as_of` IS NOW THE READ MOMENT CLAMPED INTO THE PERIOD (DEF-299 · BR-REP-036)
    ════════════════════════════════════════════════════════════════════════
    It used to be the period END unconditionally, so on 19 Aug this payload said
    `as_of 2026-08-31` — eleven days in the future. Every internal check passed,
    because the value was carried correctly everywhere; what was wrong was what
    it MEANT, and the PO's consistency rule (*"a KPI must agree with its owning
    module for the same as-of moment"*) cannot be checked by a person comparing
    a dashboard label of the 31st against Finance's 19th.

    ⚠ **`read_on` AND `as_of` ARE BOTH PUBLISHED AND THEY ARE NOT THE SAME
    DATE.** `read_on` is the moment the figures were read; `as_of` is that
    moment clamped into the selected window. They are equal for a window that
    contains today — which is every default — and they diverge the moment a user
    selects a CLOSED period, where `as_of` becomes the period end and `read_on`
    stays today. The page BODY is as of `as_of`; the page HEADER's date line and
    its cycle countdown are as of `read_on`, because *"cycle 08-A closes in N
    days"* is a statement about the future from now and not from a window that
    ended last week.
    """
    unavailable: list[dict[str, Any]] = []

    regional = seams.regional_settings() or {}
    declared_currency = regional.get("currency")

    # THE ONE CLOCK READ IN THIS FILE, and only when the caller gave nothing.
    # Pass `as_of` and nothing below consults a clock at all — which is the
    # whole of BR-TEN-043 and is what every test in this module relies on.
    read_on = as_of if as_of is not None else _day(seams.tenant_today())

    accounting_period = None if read_on is None else seams.current_period(reference_date=read_on)
    previous_period = None
    if accounting_period is not None:
        this_start = _day(accounting_period.get("start"))
        if this_start is not None:
            # BR-TEN-022 again, one day earlier: the period CONTAINING the day
            # before this one starts IS the previous period, whatever the
            # tenant's cadence — monthly, quarterly, an off-calendar FY. Nothing
            # here subtracts a month, because a month is not what a period is.
            previous_period = seams.current_period(reference_date=this_start - timedelta(days=1))

    # ⚠ MEMOISED, and it was proved by a red test.
    #
    # MEMOISED because the cycle read is not free and the region below uses it.
    # It is a `_once` rather than a bare call because this is the PAGE BODY and
    # BR-REP-028 says one section failing must not blank the page: the first
    # version called `seams.cycles_list()` bare and `test_cr012_tc15` went red
    # with `RuntimeError: cycles_list is on fire` — a metering outage taking
    # down the whole landing screen. A failing metering seam now costs the
    # cycle-status region, which reports its own failure through `guard`, and
    # nothing else.
    #
    # ⚠ **THE PERIOD FILTER NO LONGER READS CYCLES AT ALL (CR-029 D8①).** It
    # read them to build the "last completed cycle" window; the PO ruled that
    # concept out — *"dont build it"* — so the option is gone and the parameter
    # with it, rather than being passed and ignored.
    cycles_once = _once(seams.cycles_list)
    options, period_gaps = (
        ([], [])
        if read_on is None
        else period_vocab.period_options(
            as_of=read_on,
            accounting_period=accounting_period,
            previous_accounting_period=previous_period,
        )
    )
    unavailable.extend(period_gaps)
    selected = period_vocab.resolve(options, period)
    window = None if selected is None else (selected["start"], selected["end"])
    effective_as_of = None if read_on is None else period_vocab.clamp_as_of(read_on, window)

    # ── The money, all of it from ONE ledger call ──────────────────────────
    #
    # ⚠ MEMOISED SINCE CR-012, and the memo is what makes BR-REP-028 possible
    # without breaking the older guarantee. TWO things have to be true at once:
    # the KPI strip and the service-mix panel must come from ONE call (or they
    # can straddle a posting and disagree — DEF-104's shape), AND a ledger that
    # raises must take down only the regions that need it, not the page. A
    # memoised callable does both: called from the page body and from the
    # service-mix region, it queries once and re-raises the same failure into
    # whichever region asked.
    book_once = _once(
        (lambda: None)
        if window is None
        else (lambda: seams.revenue_and_ar(start=window[0], end=window[1]))
    )
    book = _quiet(book_once)
    if window is not None and book is None:
        unavailable.append(dict(GAP_LEDGER_UNWIRED))

    if book is None:
        ar_outstanding = None
        period_revenue = None
        # The currency LABEL still comes from tenancy's declared code so a
        # screen with no figures can still say what it would have been in;
        # nothing is labelled that is not there.
        currency = declared_currency
    else:
        kpis = book["kpis"]
        ar_outstanding = wire.money(kpis["still_owed"])
        period_revenue = wire.money(kpis["billed"])
        # CR-012: `revenue_by_service` is no longer flattened here. It is handed
        # WHOLE to `regions.service_mix_data`, which owns BR-REP-025's five
        # fixed rows and BR-REP-026's bars — a shape this module used to decide
        # and deliberately no longer does.
        # DEF-081: the code the figures ARE, derived from the entries summed —
        # never the declared code over a book denominated in something else. A
        # window that posted nothing derives none, and the declared code is then
        # the honest label for a set of zeroes that really are zeroes.
        currency = book.get("currency") or declared_currency
        # The ledger's own refusals travel with its figures, unedited — the
        # aging null and its reason are the pair, and dropping either half is
        # what makes a screen look broken instead of honest.
        unavailable.extend(wire.gaps(book["unavailable"]))

    # ── The counts each owner publishes, and the three none of them do ─────
    rollup_once = _once(seams.invoices_rollup)
    rollup = _quiet(rollup_once) or {}
    accounts = seams.accounts_rollup() or {}

    chips: dict[str, Any] = {}
    if effective_as_of is not None:
        # DEF-299: the CLAMPED as-of, not the window END. On 19 Aug with the
        # current period selected these two were 12 days apart, so the chips
        # answered a question about the end of the month.
        payments_view = seams.payments_summary(as_of=effective_as_of)
        if payments_view is not None:
            chips = dict(payments_view.chips)

    unbilled = seams.unbilled_read_rollup()
    if unbilled is None:
        unavailable.append(dict(GAP_UNBILLED_READS))
    connections = seams.account_status_class_counts()
    if connections is None:
        unavailable.append(dict(GAP_ACTIVE_CONNECTIONS))
    failed = None
    if effective_as_of is not None:
        failed = seams.failed_payment_count(as_of=effective_as_of)
    if failed is None:
        unavailable.append(dict(GAP_FAILED_PAYMENTS))

    number_format = regional.get("number_format")

    return {
        "basis": BASIS_POSTING,
        "currency": currency,
        # CR-012: the moment every figure on this screen was read AT. The PO's
        # own consistency rule — *"a KPI must agree with its owning module for
        # the same as-of moment"* — is only checkable if the screen says which
        # moment that was, so it is published rather than implied.
        #
        # ⚠ CR-015 / DEF-299 / BR-REP-036 — it is the READ MOMENT CLAMPED INTO
        # THE SELECTED PERIOD, and it used to be the period END. On 2026-08-19
        # this key served **2026-08-31**, a moment eleven days in the future,
        # against a Finance page headed the 19th.
        "as_of": None if effective_as_of is None else effective_as_of.isoformat(),
        # The moment the figures were READ — today, whatever window is selected.
        # Separate from `as_of` on purpose: the page HEADER's date line and its
        # cycle countdown are statements about NOW, and a countdown computed
        # from a window that closed last week reads "closes in -11 days".
        "read_on": None if read_on is None else read_on.isoformat(),
        # BR-REP-033: what this ROLE may do, decided on the server. A control
        # hidden only by the client is a suggestion, not a permission.
        "page_actions": regions.page_actions(role),
        "period": wire.period(None if window is None else {"start": window[0], "end": window[1]}),
        # BR-REP-035 — the WHOLE vocabulary, not just the chosen one. The screen
        # draws the control from this, so an option nobody can compute is absent
        # from the menu rather than present and broken, and the DEFAULT is the
        # server's answer rather than a constant two codebases have to agree on.
        "period_filter": {
            "selected": None if selected is None else selected["id"],
            "default": period_vocab.default_option_id(options),
            "options": [_period_option(option) for option in options],
        },
        "regions": _regions(
            book_once=book_once,
            window=window,
            currency=currency,
            number_format=number_format,
            as_of=effective_as_of,
            read_on=read_on,
            cycles_once=cycles_once,
            role=role,
            rollup_once=rollup_once,
            kpis={
                "ar_outstanding": ar_outstanding,
                "period_revenue": period_revenue,
                "unbilled_reads": None if unbilled is None else unbilled.get("unbilled"),
                "failed_payments": failed,
                "active_connections": (
                    None if connections is None else connections.get("active_connections")
                ),
            },
        ),
        "kpis": {
            # Money — both POSTING basis, both labeled, both the ledger's own.
            "ar_outstanding": ar_outstanding,
            "period_revenue": period_revenue,
            # Counts — null wherever the owner publishes nothing.
            "unbilled_reads": None if unbilled is None else unbilled.get("unbilled"),
            "pending_routes": None if unbilled is None else unbilled.get("pending_routes"),
            "failed_payments": failed,
            "active_connections": (
                None if connections is None else connections.get("active_connections")
            ),
        },
        # Named separately from the KPI strip on purpose: this is HOW MANY
        # ACCOUNTS EXIST, which is not BR-REP-012's Active-connections figure and
        # must never be read as one.
        "accounts_on_file": accounts.get("accounts"),
        "bills": rollup.get("bills"),
        "unresolved_from_last_run": rollup.get("unresolved_from_last_run"),
        "returned_mail": chips.get("returned_mail"),
        "autopay_scheduled": chips.get("autopay_scheduled"),
        # ⚠ `service_mix`, `aging` and `activity` USED TO BE TOP-LEVEL MEMBERS
        # and are now `regions.service_mix` / `regions.aging` / `regions.activity`
        # (CR-012). They moved rather than being duplicated: they are exactly the
        # three regions whose CONTENT the requirement changed, and a second copy
        # on the old key would be a second source of truth for the same panel —
        # the shape hard-won law 5 is about. Nothing outside this repo consumed
        # them; `DashboardPage.tsx` is the only reader.
        "unavailable": [wire.gap(entry) for entry in unavailable],
    }


def _period_option(option: dict[str, Any]) -> dict[str, Any]:
    """One entry of the period menu, on the wire.

    The dates go out as ISO strings so the SCREEN can state the window in the
    reader's own locale (a date is language, and this product ships eleven
    catalogues — the same reason the weekday is formatted client-side). The
    `id` is a stable machine token the screen keys its label on, never a
    sentence: TD-16/B8, the server sends keys and the UI renders language.
    """
    return {
        "id": option["id"],
        "start": option["start"].isoformat(),
        "end": option["end"].isoformat(),
        # Present only on the option that HAS one. A cycle window is the only
        # one that can name itself, and naming it is most of why the default is
        # a cycle: "12 Aug - 19 Aug 2026 - Cycle 08-B" is a window an operator
        # recognises, where "12 Aug - 19 Aug" alone is an arbitrary week.
        "cycle_code": option.get("cycle_code"),
        "cycle_name": option.get("cycle_name"),
        "fy_label": option.get("fy_label"),
        "period_no": option.get("period_no"),
    }


def _regions(
    *,
    book_once: Callable[[], dict[str, Any] | None],
    window: tuple[date, date] | None,
    currency: str | None,
    number_format: str | None,
    as_of: date | None,
    read_on: date | None,
    cycles_once: Callable[[], list[dict[str, Any]] | None],
    role: str | None,
    rollup_once: Callable[[], dict[str, Any] | None],
    kpis: dict[str, Any],
) -> dict[str, Any]:
    """DSH-01's six regions, each built behind its own failure boundary.

    **Every one of these calls can raise and none of them can take the page
    down** (BR-REP-028, the PO's *"one section failing must not blank the
    page"*). `regions.guard` is the boundary; the lambdas below are what it
    guards, and they are written as separate builders precisely so that one
    owner's outage is contained to one panel.

    The KPI band is assembled from figures the caller already read — it does no
    fetching of its own — so a failing owner shows up as that TILE's stated
    absence rather than as a failed region.
    """
    return {
        # ⚠ THE ONE REGION THAT READS `read_on` AND NOT `as_of` (CR-015). It
        # answers *"which cycle closes next"* — a statement about the future
        # from NOW. Fed the clamped `as_of` of a closed window it would count
        # down from a date in the past and report a cycle as closing in a
        # negative number of days.
        "cycle_status": regions.guard(
            "cycle_status",
            lambda: (
                None
                if read_on is None
                else regions.cycle_status_data(cycles_once() or (), as_of=read_on)
            ),
        ),
        "kpi_band": regions.guard(
            "kpi_band",
            lambda: _kpi_band(kpis, currency=currency, number_format=number_format),
        ),
        "activity": regions.guard(
            "activity",
            lambda: _activity(
                as_of=as_of, currency=currency, number_format=number_format, role=role
            ),
        ),
        "service_mix": regions.guard(
            "service_mix",
            lambda: regions.service_mix_data(
                (book_once() or {}).get("revenue_by_service") or (),
                # PO 2026-08-19, decision 1: the ROW SET is the tenant's own
                # configured services, always all of them, in the platform's
                # seed order — not the five this panel used to hard-code. Read
                # here rather than inside the region so the region stays a pure
                # function of two owners' answers and remains testable without
                # a database.
                configured_services=seams.enabled_service_codes(),
                currency=currency,
                number_format=number_format,
            ),
        ),
        "aging": regions.guard(
            "aging", lambda: _aging(as_of=as_of, currency=currency, number_format=number_format)
        ),
        "todo": regions.guard(
            "todo", lambda: _todo(rollup_once=rollup_once, number_format=number_format)
        ),
    }


#: BR-REP-034's tile carries its target sub-line; the other four carry the sub
#: r10 draws only where a read exists for it. Every entry names the gap CODE the
#: screen keys its own sentence on, so a refusing tile still says what is
#: missing (TD-16/B8 — the server sends keys, the UI renders language).
KPI_ORDER: tuple[tuple[str, str, str, str | None], ...] = (
    ("ar-outstanding", "ar_outstanding", "money", None),
    ("unbilled-reads", "unbilled_reads", "count", GAP_UNBILLED_READS["code"]),
    ("failed-payments", "failed_payments", "count", GAP_FAILED_PAYMENTS["code"]),
    ("mtd-revenue", "period_revenue", "money", None),
    ("active-connections", "active_connections", "count", GAP_ACTIVE_CONNECTIONS["code"]),
)


def _kpi_band(
    kpis: dict[str, Any], *, currency: str | None, number_format: str | None
) -> dict[str, Any]:
    """The five tiles, in the PO's fixed order, each pre-formatted (BR-REP-029).

    **No tile carries a navigation target** — *"KPI cells do not navigate in
    v1"* (BR-REP-033) — and that is expressed by the payload simply not having
    somewhere to put one, which is stronger than a screen remembering not to
    render a link.
    """
    target = seams.monthly_revenue_target()
    tiles = []
    for tile_id, key, kind, gap_code in KPI_ORDER:
        value = kpis.get(key)
        display = (
            fmt.money_display(value, currency=currency, number_format=number_format)
            if kind == "money"
            else fmt.count_display(value, number_format=number_format)
        )
        sub = None
        if tile_id == "mtd-revenue":
            # BR-REP-034. `None` here is the RULED state, not a gap: with no
            # target typed the tile is the figure alone and says nothing false.
            sub = regions.revenue_target_sub(
                value, target=target, currency=currency, number_format=number_format
            )
        tiles.append(
            {
                "id": tile_id,
                "kind": kind,
                "value": value,
                "display": display,
                "basis": BASIS_POSTING if kind == "money" else None,
                "sub": sub,
                "unavailable_code": None if value is not None else gap_code,
            }
        )
    return {
        "state": "ok" if any(tile["value"] is not None for tile in tiles) else "empty",
        "tiles": tiles,
    }


def _activity(
    *, as_of: date | None, currency: str | None, number_format: str | None, role: str | None
) -> dict[str, Any] | None:
    """BR-REP-031 — the last 24 hours of operator work, from the audit log."""
    if as_of is None:
        return None
    since, until = regions.activity_window(as_of)
    trail = seams.audit_recent(tenant_id=current_tenant_id(), since=since, until=until)
    if trail is None:
        return None
    rows = regions.activity_rows(trail, currency=currency, number_format=number_format, role=role)
    return {
        "state": "ok" if rows else "empty",
        "rows": rows,
        "window": {"from": since.isoformat(), "to": until.isoformat()},
        # PO 2026-08-19: *"yes it shoudl state the window"*. The panel says how
        # far back it looked, in hours, and the SCREEN renders that figure into
        # its own language — so the heading and the empty sentence cannot drift
        # from `ACTIVITY_WINDOW_DAYS`, and "nothing has happened here yet" can
        # never be read as "nothing has ever happened".
        "window_hours": regions.ACTIVITY_WINDOW_HOURS,
        "unavailable": (dict(regions.GAP_ACTIVITY_AMOUNT),) if rows else (),
    }


def _aging(*, as_of: date | None, currency: str | None, number_format: str | None):
    """BR-REP-030 — the five bands, from `payments.outstandings` (not A14's four)."""
    if as_of is None:
        return None
    view = seams.outstandings(as_of=as_of)
    if view is None:
        return None
    return regions.aging_data(view, currency=currency, number_format=number_format)


def _todo(
    *, rollup_once: Callable[[], dict[str, Any] | None], number_format: str | None
) -> dict[str, Any]:
    """BR-REP-032 — max four, every one generated by its owning module.

    The onboarding steps are the PO's new-tenant case: *"New tenants show `—`
    KPIs with 'No billing history yet' and remaining onboarding steps in To
    do."* They come from S62's checklist, which is COMPUTED from live data
    (BR-TEN-015), so a step leaves the dashboard the moment the work is done in
    Settings.
    """
    checklist = seams.onboarding_checklist() or {}
    outstanding = [
        {"item": item.get("item"), "target": item.get("target")}
        for item in (checklist.get("items") or ())
        if not item.get("done")
    ]
    rows = regions.todo_rows(
        billing_exceptions=(rollup_once() or {}).get("unresolved_from_last_run"),
        onboarding=outstanding,
        rate_approvals=seams.pending_rate_approvals(),
        disconnect_eligible=seams.disconnect_eligible_count(),
        finance_close=seams.open_finance_close(),
        number_format=number_format,
    )
    return {"state": "ok" if rows else "empty", "rows": rows}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-REP-019@f9ccd14 (story+rules snapshot — 04-docs/05-modules/12-reports/06-epics/EP-REP-05-dashboards.md §US-REP-019 · 12-reports/02-business-rules.md BR-REP-001/002/012/024 · 04-docs/01-spec/11-api-contracts.md S7 row · 04-docs/01-spec/11b-api-audit.md §1 GET /dashboard/summary · 05-prototype/UtilityBilling.html lines 653-711)
# screens: S7   (DEF-137's screen-id stamp — see 10-scripts/gates/g25_screen_coverage.py)
# generated: 2026-08-16 by story-coder (DEF-129 lane — the first screen after every sign-in did not exist) · AMENDED 2026-08-19 by story-coder (CR-012 closing lane — the service-mix row set follows the tenant, and Recent activity publishes the window it read)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_rep_019_dashboard.py failed to import this module before it existed. ruff✔ black✔ pytest✔ run_gates✔ · openapi schema regenerated
# exceptions: (1) FIVE of this screen's figures are served NULL with a named reason and NONE is substituted — unbilled reads, active connections, failed payments, AR aging and the activity feed. Three are unwired seams (parked in seam_known_gaps.txt), one is the ledger's own published refusal passed through, and one is an unbuilt read model belonging to US-REP-016. In every case a plausible substitute exists in the owning module and is deliberately not used · (2) `dashboard_summary()` takes NO arguments: the window is the tenant's computed `current_period` (BR-TEN-022), the same one S36/S59/S60 use, so four screens cannot disagree about which month a figure belongs to. A period picker on the landing screen would be a control that changes a number nobody asked to change · (3) the currency LABEL is the code the ledger derived from the entries it summed (DEF-081), falling back to the tenant's declared code only for a window that posted nothing · (4) this file contains no arithmetic on money of any kind — `wire.money` is the only transformation applied to an owner's figure
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
