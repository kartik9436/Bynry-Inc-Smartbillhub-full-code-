# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-019 (S7 / DSH-01)   Screens: S7   Change: CR-012
# Rules:    BR-REP-024 (a tile never computes a figure) · BR-REP-025 (the
#           TENANT's OWN services, all of them, in the platform's seed order —
#           amended by PO ruling 2026-08-19 d.1 from a hard-coded five) ·
#           BR-REP-026 (bars are a share of the LARGEST) ·
#           BR-REP-027 (the cycle status line) · BR-REP-028 (regions load,
#           empty and FAIL independently) · BR-REP-029 (pre-formatted) ·
#           BR-REP-030 (five aging buckets; the arrangement rule) · BR-REP-031
#           (activity: 24h, max 6, the audit log — and the panel STATES the
#           window, PO 2026-08-19 d.6) · BR-REP-032 (to do: max 4,
#           owner-generated; a row nobody could count shows NO NUMBER, PO
#           2026-08-19 d.3) · BR-REP-033 (role-gated actions; nothing mutates)
#           · BR-REP-034 (the typed revenue target) · BR-TEN-043 (a window is
#           an argument, never a clock) · CLAUDE.md rule 1 · rule 2
# Tests:    06-backend/tests/test_cr012_dashboard_dsh01.py
# Impacts:  apps/reports/dashboard.py (the only caller)
# ───────────────────────────────────────────────────────
"""DSH-01's six regions, each of which loads, empties and FAILS on its own.

The PO's acceptance criterion, verbatim: *"Per-section loading/empty/error
states; one section failing must not blank the page."* That sentence is the
reason this module exists as something other than more code inside
`dashboard.py`: a region is a unit of FAILURE here, not just a unit of layout.

    guard("service_mix", …) → {"state": "ok"|"empty"|"error", "data", "error"}

Every region goes through `guard`. A region whose owner raises reports its own
error with a stable code and the other five still answer, so the worst outcome
this screen can produce is five sixths of a dashboard — never a blank page, and
never a page of zeroes, which is the failure mode that looks like success.

════════════════════════════════════════════════════════════════════════════
WHAT THIS MODULE COMPUTES, AND WHAT IT REFUSES TO
════════════════════════════════════════════════════════════════════════════
BR-REP-024 still holds: **no money figure here is derived from another money
figure.** What CR-012 adds is presentation arithmetic, and the line between the
two is worth stating because it is the line a later agent will blur:

  ALLOWED, and done here      a bar width (a ratio of two of the OWNER's own
                              amounts, rendered as a percentage of the largest)
                              · a display string · a whole-number percentage
                              against a target a HUMAN typed
  NOT ALLOWED, and not here   summing bands to a total · re-bucketing an
                              account · deriving a share the owner already
                              published · turning an absence into a zero

The aging panel is the sharpest case. `payments.outstandings` publishes each
band's amount, its account count AND its share; this module renders all three
and recomputes none of them. That is not fastidiousness — it is the only reason
the panel can obey *"a KPI must agree with its owning module for the same as-of
moment"*.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable

from apps.ledger import wire

from . import dashboard_format as fmt

# ── BR-REP-025 · the tenant's OWN services, in the platform's seed order ────
#
# ⚠ **AMENDED BY THE PO, 2026-08-19 — and the amendment is a REVERSAL, so the
# thing it reversed is written down rather than quietly deleted.** This constant
# used to be `FIXED_SERVICE_CODES = ("electric","water","sewer","trash","gas")`
# — the requirement of 2026-08-18 named exactly five and gave the reason, *"so
# row order is stable month to month"*. What the PO saw on 2026-08-19 is what
# that costs a utility that does not sell those five: **a broadband-and-water
# utility met five rows, three of them permanently empty, and its actual revenue
# in the remainder footnote.**
#
# The PO's answer, verbatim: *"I agree - My proposal, which keeps your reason
# intact: draw the tenant's own configured services — always all of them"*.
#
# **The stability reason survives intact** and that is why the ruling is safe: a
# tenant's service list changes when they ADD A SERVICE, not month to month, so
# a person reading this screen every morning still sees the same rows in the
# same order. Silver Creek, which sells the original five, sees exactly what it
# saw before.
#
# ORDER IS THE PLATFORM'S SEED ORDER (BR-RAT-024 / `apps/tenancy/migrations/
# 0001_initial.SERVICE_SEED`), which is `Service.sort` and is what
# `tenancy.selectors.enabled_service_codes()` already orders by. It is mirrored
# here — not imported — because reports reading tenancy's module constants is a
# cross-module read (B1); the mirror's job is to ORDER an answer tenancy gave,
# never to produce one, and a code tenancy names that this tuple has never heard
# of is still drawn (last, by code) rather than dropped.
PLATFORM_SERVICE_ORDER: tuple[str, ...] = (
    "electric",
    "water",
    "gas",
    "sewer",
    "trash",
    "storm_water",
    "solar",
    "broadband",
    "thermal_heat",
    "battery",
    # CR-063 — the ELEVENTH service, APPENDED (BR-RAT-024, amended 2026-09-02).
    # Its own migration is `0033_cr063_fire_service.py`; `0001_initial` has run
    # on every database that exists and can never gain a row.
    #
    # ⚠ A code missing from this tuple is NOT dropped — the note above says so
    # and it is true — but it is drawn LAST, BY CODE, which is a different place
    # from where the platform puts it. So a fire utility's service-mix panel
    # would have ordered correctly by accident (fire IS last) and any TWELFTH
    # service would not. Ordering by accident is not ordering.
    "fire",
)

GAP_CONFIGURED_SERVICES = {
    "code": "configured_services_are_not_published_by_tenancy",
    "br_ref": "BR-REP-025 · BR-REP-002",
    "detail": (
        "Which services this utility sells is tenancy's fact and it could not be read, "
        "so this panel lists the services that actually billed in the period instead of "
        "the ones the utility has configured. Nothing is invented and nothing is "
        "dropped: a service that billed money is drawn, and a configured service that "
        "billed nothing cannot be shown as an empty row because there is nothing to say "
        "it exists. The five-row list this panel used to hard-code is NOT substituted — "
        "it is the wrong list for most utilities, which is why the PO removed it."
    ),
    "wanted_reads": ("apps.tenancy.selectors.enabled_service_codes",),
}


def panel_service_codes(
    configured: tuple[str, ...] | None, billed: tuple[str, ...] = ()
) -> tuple[str, ...]:
    """The rows this panel draws, in the platform's fixed seed order.

    `configured` is tenancy's own answer to *"which services does this utility
    sell"*. Every one of them draws a row **whether or not it billed anything**,
    which is the half of BR-REP-025 the ruling did not change: a configured
    service that billed nothing is an em-dash and a zero-width bar, never
    `$0.00`.

    **A `None` here is not an empty list.** Tenancy could not answer, so the
    panel falls back to the services that BILLED — every figure still appears,
    the panel still foots, and the region reports `GAP_CONFIGURED_SERVICES` so
    the screen says which list it is showing. The old hard-coded five are not
    used as a fallback: they are the wrong list for most utilities, which is
    the whole reason they were removed.

    A code the platform order has never heard of sorts last, by code. Dropping
    it would hide a row tenancy told us to draw, and inventing a position for it
    would put it somewhere the seed order does not agree with.
    """
    source = tuple(billed) if configured is None else tuple(configured)
    seen: list[str] = []
    for code in source:
        if code and code not in seen:
            seen.append(code)
    ranked = sorted(
        seen,
        key=lambda code: (
            (
                PLATFORM_SERVICE_ORDER.index(code)
                if code in PLATFORM_SERVICE_ORDER
                else len(PLATFORM_SERVICE_ORDER)
            ),
            code,
        ),
    )
    return tuple(ranked)


# ── BR-REP-030 · the five aging bands ──────────────────────────────────────
#
# `apps.payments.outstandings.AGEING_BUCKETS`, mirrored rather than imported —
# reports importing a neighbour's constant is a cross-module read (B1). The
# names are ASSERTED against the served buckets at render time (see
# `aging_data`), so a divergence goes red here instead of drawing a band under
# the wrong label.
AGING_BUCKETS: tuple[str, ...] = ("current", "1-30", "31-60", "61-90", "90+")

#: r10's `.aging-tbl` puts its danger emphasis on the OLDEST bucket alone —
#: `.tot` appears on the 90+ amount and on nothing else.
DANGER_BUCKET = "90+"

# ── BR-REP-031 · what counts as operator work ──────────────────────────────
#
# The PO named six classes: *"bill runs, payments, read imports, adjustments,
# dunning, new accounts"*. Each maps to the audit action prefixes this codebase
# actually writes (grepped from `apps/**`, not guessed), and each prefix carries
# the MODULE that owns it so the role gate below has something to ask about.
#
# What is deliberately NOT here: `settings.*`, `auth.*`, `user.*` and
# `security.*`. They are in the trail, they belong on S61, and on a busy morning
# they would bury the bill run under the sign-in that reached it.
OPERATOR_ACTIONS: dict[str, str] = {
    "bill_run.": "billing",  # bill runs
    "invoice.": "billing",
    "correction.": "billing",  # adjustments
    "payment.": "payments",
    "refund.": "payments",
    "collection.": "payments",  # dunning
    "notice.": "notifications",  # dunning
    "read_batch.": "metering",  # read imports
    "account.": "customers",  # new accounts
}

#: Prefixes that are NOT operator-relevant today but ARE module-owned, kept so
#: the role gate is a real gate rather than a formality: if a later lane
#: allowlists a finance action above, a Billing Clerk still never sees it.
MODULE_OF_ACTION: dict[str, str] = dict(OPERATOR_ACTIONS) | {
    "journal.": "finance",
    "write_off.": "finance",
}

# A4's addendum (04-docs/01-spec/04-roles-permissions.md), the three predefined
# tenant roles, transcribed: *"Billing Clerk — full on Premises/Accounts/Reads/
# Billing/Payments; … no settings/users"* with **Finance/reconcile/export = —**;
# *"Executive — view across operational modules; full on Finance + Reports"*.
ROLE_MODULES: dict[str, frozenset[str]] = {
    "system_admin": frozenset(
        {"billing", "payments", "metering", "customers", "notifications", "finance"}
    ),
    "executive": frozenset(
        {"billing", "payments", "metering", "customers", "notifications", "finance"}
    ),
    "billing_clerk": frozenset({"billing", "payments", "metering", "customers", "notifications"}),
}

#: BR-REP-033: *"Both hidden for read-only roles."* A4's addendum makes the
#: Executive **View** on *Reads & Billing runs*, so the Executive is the
#: read-only role for these two actions. Stated as a set of roles that MAY act,
#: because "who is allowed" fails closed and "who is forbidden" does not: an
#: unknown role gets nothing rather than everything (hard-won law 3).
ROLES_MAY_RUN_WORK: frozenset[str] = frozenset({"system_admin", "billing_clerk"})

#: BR-REP-031 / BR-REP-032: the two caps the PO stated, spelled once.
ACTIVITY_MAX_ROWS = 6
TODO_MAX_ROWS = 4

#: BR-REP-031's window. *"last 24h"*, measured back from the as-of DAY, because
#: every other figure on this screen is bucketed by day in the utility's own
#: zone (DEF-094) and a feed measured to the second beside figures measured to
#: the day is two clocks on one screen.
ACTIVITY_WINDOW_DAYS = 1

#: The same window in the unit a person reads it in, published to the screen.
#:
#: **PO, 2026-08-19: *"yes it shoudl state the window"*.** The panel's empty
#: state says *"nothing has happened here yet"*, and that sentence means
#: something very different at 24 hours than at forever — on a utility's first
#: Monday the difference is the whole message. So the window is a SERVED FIGURE
#: rather than a sentence hard-coded in eleven catalogues: change
#: `ACTIVITY_WINDOW_DAYS` and every catalogue's wording follows, instead of ten
#: translations quietly continuing to claim 24 hours.
ACTIVITY_WINDOW_HOURS = ACTIVITY_WINDOW_DAYS * 24


# ═══════════════════════════════════════════════════════════════════════════
# THE REGION BOUNDARY — BR-REP-028
# ═══════════════════════════════════════════════════════════════════════════
GAP_REGION_FAILED = {
    "code": "region_read_failed",
    "br_ref": "BR-REP-028 · BR-SHL-020",
    "detail": (
        "This region's own read raised. The other regions on this screen are unaffected "
        "and render their figures — the PO's acceptance criterion is that one section "
        "failing must not blank the page. The exception text is NOT carried to the "
        "client: a billing clerk reads a sentence keyed on this code, never a stack "
        "trace or a database error (BR-SHL-020)."
    ),
    "wanted_reads": (),
}


def guard(name: str, build: Callable[[], dict[str, Any] | None]) -> dict[str, Any]:
    """Run one region's build and contain its failure to that region.

    ⚠ **A BARE `except Exception` IS ALMOST ALWAYS WRONG AND IS RIGHT HERE**, so
    the reason is written down rather than left to be "cleaned up" later. This
    screen is a READ, it writes nothing (BR-REP-033), and it is the first thing
    a user sees after every sign-in. A read model that cannot answer must say so
    in its own square inch; the alternative — which is what shipped before this
    CR — is that a single owner's failure returns 500 and the user meets a blank
    page with no figures at all, including the five that were fine.

    The exception is deliberately NOT re-raised and NOT serialised. It is
    LOGGED, once, with the region name, so the failure is diagnosable from the
    server side where a stack trace belongs.
    """
    try:
        data = build()
    except Exception:  # noqa: BLE001 — contained on purpose; see the docstring
        import logging

        logging.getLogger("smartbillhub.reports").exception("DSH-01 region %s failed", name)
        return {
            "state": "error",
            "data": None,
            "error": dict(GAP_REGION_FAILED, region=name),
            "unavailable": [],
        }
    if data is None:
        return {"state": "empty", "data": None, "error": None, "unavailable": []}
    gaps = list(data.pop("unavailable", ()) or ())
    return {
        "state": data.pop("state", "ok"),
        "data": data,
        "error": None,
        "unavailable": [wire.gap(entry) for entry in gaps],
    }


# ═══════════════════════════════════════════════════════════════════════════
# REGION 4 · SERVICE MIX — BR-REP-025 / BR-REP-026
# ═══════════════════════════════════════════════════════════════════════════
def mix_rows(
    totals: dict[str, Any],
    *,
    codes: tuple[str, ...],
    currency: str | None,
    number_format: str | None,
) -> list[dict[str, Any]]:
    """One row per service this tenant sells, with the bar each one draws.

    `totals` is `{service_code: amount}` taken straight from the ledger's
    `revenue_by_service`. A code absent from it billed nothing; so did a code
    present with `0`. **Both render the em-dash**, because the PO's worked
    examples rule that `$0.00` is never printed in this column: *"a printed zero
    and an absent service look identical to a reader and mean different
    things"*. The DIFFERENCE that matters is between an absent ROW (which would
    say "this utility does not sell trash") and an em-dash row (which says
    "trash billed nothing this month"), and the row is always there.

    **The bar is a share of the LARGEST, not of the total** (BR-REP-026). r10's
    own file hardcodes 70/22/8, which is 238/342, 76/342 and 28/342 — a share of
    the TOTAL. That is not what ships and this docstring exists so the next agent
    who decodes the reference does not "fix" a correct build back.

    One rounded percentage drives BOTH the number and the width, so the two can
    never disagree, and a non-zero service floors at 1% so a real charge never
    renders as nothing.
    """
    amounts: dict[str, Decimal | None] = {}
    for code in codes:
        raw = totals.get(code)
        amounts[code] = None if raw is None else Decimal(str(raw))

    positive = [value for value in amounts.values() if value is not None and value > 0]
    largest = max(positive) if positive else None

    rows: list[dict[str, Any]] = []
    for code in codes:
        amount = amounts[code]
        billed = amount is not None and amount != 0
        percent = (
            fmt.whole_percent(amount, largest, floor_visible=True) if billed and largest else None
        )
        rows.append(
            {
                "service_code": code,
                # The exact figure still travels (CLAUDE.md rule 2) even where
                # the label is an em-dash, so nothing downstream has to read
                # money out of an abbreviation.
                "amount": wire.money(amount),
                "display": (
                    fmt.money_display_short(amount, currency=currency, number_format=number_format)
                    if billed
                    else fmt.EM_DASH
                ),
                "bar_pct": percent or 0,
                "share": percent,
                "share_display": fmt.percent_display(percent),
            }
        )
    return rows


def service_mix_data(
    revenue_rows: Any,
    *,
    configured_services: tuple[str, ...] | None,
    currency: str | None,
    number_format: str | None,
) -> dict[str, Any]:
    """The panel: this tenant's own service rows, plus whatever they cannot hold.

    ⚠ **THE REMAINDER SURVIVES THE 2026-08-19 RULING AND IS STILL NOT OPTIONAL,
    and the reason is worth restating because "draw all the tenant's services"
    reads like it removes the need for it.** It does not. `revenue_by_service`
    keeps rows whose `service_code` is `None` AT ALL — **a late fee is charged
    to an ACCOUNT, not to a service** — and rows for a service the tenant has
    since switched off but billed earlier in the period. Neither has a row to
    live in however complete the row list is. Folding either into a service row
    would be a wrong figure; dropping it would make the panel foot to LESS than
    the period's revenue, which is the silent shortfall BR-REP-002 exists to
    forbid. So it is reported, under its own name, with a count of how many
    services it covers.
    """
    totals: dict[str, Decimal] = {}
    for row in revenue_rows or ():
        code = getattr(row, "service_code", None)
        amount = Decimal(str(getattr(row, "total_billed", 0) or 0))
        key = str(code) if code else ""
        totals[key] = totals.get(key, Decimal("0")) + amount

    billed_codes = tuple(code for code in totals if code)
    codes = panel_service_codes(configured_services, billed_codes)

    # Everything the drawn rows cannot hold, by subtraction rather than by a
    # second pass — so a row can never be counted both in a service and in the
    # remainder, which is the arithmetic that would make the panel foot twice.
    drawn = set(codes)
    remainder = Decimal("0")
    remainder_services = 0
    for key, amount in totals.items():
        if key in drawn:
            continue
        remainder += amount
        remainder_services += 1

    rows = mix_rows(totals, codes=codes, currency=currency, number_format=number_format)
    # ⚠ **"EMPTY" NOW MEANS "NO ROWS TO DRAW", NOT "NOTHING WAS BILLED" — and
    # that is a CONSEQUENCE of the 2026-08-19 ruling rather than a second
    # ruling.** It used to read `"ok" if billed_anything or remainder else
    # "empty"`, so a month in which nothing had been billed yet replaced the
    # whole panel with a sentence. That was defensible while the rows were a
    # hard-coded five that told the reader nothing about their own utility. It
    # is not defensible now: the PO's word is *"always all of them"*, and a
    # broadband-and-water utility opening the product on the first of the month
    # would meet the sentence and never see that the panel knows what it sells.
    #
    # Nothing else changes. Each unbilled row is still the em-dash and the
    # zero-width bar the requirement asks for — *"unsold services show an empty
    # bar and `—`"* — which says "nothing here yet" per service, in the place a
    # reader is already looking. **`$0.00` still never appears.** The empty
    # STATE is reserved for the one case where there is genuinely nothing to
    # render: a tenant with no configured service and no revenue at all.
    return {
        "state": "ok" if rows or remainder else "empty",
        "rows": rows,
        "remainder": (
            None
            if remainder_services == 0
            else {
                "amount": wire.money(remainder),
                "display": fmt.money_display(
                    remainder, currency=currency, number_format=number_format
                ),
                "services": remainder_services,
            }
        ),
        "unavailable": ((dict(GAP_CONFIGURED_SERVICES),) if configured_services is None else ()),
    }


# ═══════════════════════════════════════════════════════════════════════════
# REGION 1 · CYCLE STATUS — BR-REP-027
# ═══════════════════════════════════════════════════════════════════════════
#: ⚠ **`CYCLE_CLOSE_FIELD` IS GONE — CR-029 D8②, PO 2026-08-23.** It held
#: `"read_day_to"`, DERIVED from the requirement's own four states because
#: nothing stated which date *"closes in 4 days"* counts to (OQ-221 carries that
#: derivation, and its own words were *"if the PO meant the BILL date, one
#: constant moves"*). The PO has now stated it, and the answer is neither of the
#: day-of-month candidates: verbatim, *"② which date 'closes in 4 days' counts
#: to - Next cycle date"*.
#:
#: So the countdown reads `next_cycle_date` off the cycle payload — the next
#: occurrence the period engine derives from start day · frequency ·
#: days-to-complete (`apps/metering/period_engine.py`) — and the constant that
#: named a column does not move, it goes. A cycle that cannot say when it next
#: comes round (an unruled month-end anchor, OQ-339) publishes no date and is
#: SKIPPED rather than counted down to a date this file chose for it.
CYCLE_RUN_FIELD = "bill_day"

CYCLE_STATE_CLOSES_IN = "closes_in"
CYCLE_STATE_TODAY = "closes_today"
CYCLE_STATE_PENDING_RUN = "closed_pending_run"
CYCLE_STATE_NONE = "not_configured"

#: ⚠ **REMOVED BY THE PO, 2026-08-19 — decision 5, verbatim: *"no provide any
#: link - also consider what if status are set in settings - check that out"*.**
#:
#: This used to be `ROUTES_AND_CYCLES_TARGET = "settings/routes-cycles"`, served
#: on the `not_configured` state so the line could offer a set-up link. The
#: second half of the PO's sentence was a question and it was CHECKED: cycle
#: configuration does live in Settings → Routes & Cycles, which is CR-006's own
#: surface and reachable from the sidebar on every screen.
#:
#: So the line **reflects the configured state rather than prompting a set-up**.
#: The constant is gone rather than left unread, because a served target nothing
#: renders is hard-won law 2 — dead payload that reads as a feature.
_CYCLE_SETTINGS_LINK_REMOVED = "PO 2026-08-19 · decision 5"

GAP_CYCLE_RUN_NOT_PUBLISHED = {
    "code": "whether_the_bill_run_has_happened_is_not_published_by_billing",
    "br_ref": "BR-REP-027 · BR-REP-024",
    "detail": (
        "The 'closed — bill run pending' state is derived from the cycle's OWN "
        "day-of-month defaults — the read window has shut and the cycle's bill day has "
        "not arrived. Whether a run ACTUALLY happened is billing's fact and billing "
        "publishes no per-cycle run read, so a run taken early is not reflected. The "
        "line states the schedule, which is what a cycle definition holds; it does not "
        "claim a run did or did not occur."
    ),
    "wanted_reads": ("apps.billing.selectors.last_run_for_cycle",),
}


# ⚠ **`_day_in_month` AND `_next_month` ARE GONE — W5-T2.** They landed a
# day-of-month default on a real calendar month for the transitional fallback
# above, clamping because *"read_day_to may be 31 and February is not"*. The
# column is dropped and the fallback with it, so both helpers had no caller.
# Deleted rather than kept for later: a month-end clamp sitting unused in a
# reports module is exactly the kind of thing a lane reaches for to answer
# OQ-339 (which reading a repeating month-end schedule takes), and that question
# is the PO's, not a helper's. `apps.metering.schedule.derive_read_window` owns
# the clamp that IS ruled, and states at its own docstring why rendering a
# chosen month is a different question from generating occurrences.


def _cycle_date(value: Any) -> date | None:
    """`next_cycle_date` as a `date` — the seam serves ISO strings."""
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _candidate(cycle: dict[str, Any], as_of: date) -> tuple[date, str] | None:
    """One cycle's next date and the state it is in, or None if it cannot say.

    ── CR-029 D8② — THE RULED TARGET ────────────────────────────────────────
    PO, verbatim 2026-08-23: *"② which date 'closes in 4 days' counts to - Next
    cycle date"*. `next_cycle_date` is metering's own derivation (the period
    engine over start day · frequency · days-to-complete · first run), so the
    countdown and SET-07D's schedule card cannot disagree about one cycle.

    Worked, and it is the sentence the requirement draws: a cycle whose next
    date is **1 Sep**, read on **28 Aug**, is *"closes in 4 days"*; on 1 Sep it
    is *"closes today"*.

    ⚠ **THE TRANSITIONAL DAY-OF-MONTH FALLBACK IS GONE — RC-W5-T2.** RC-W2 left
    one here and said out loud what would end it: *"while the deprecated
    day-of-month columns still exist (RC-W5 drops them) a cycle that cannot say
    when it next comes round falls back to them, unchanged. When they go, a
    cycle with no first run publishes nothing and is skipped."* metering 0021
    dropped `read_day_to`, so that is now what happens.

    **WHAT THAT COSTS, STATED RATHER THAN GLOSSED.** Two things go with it.

      1. A cycle carrying no `first_run_date` is SKIPPED instead of counted
         down to. The fallback existed so a tenant with six such cycles would
         not read *"no cycle configured"* — and the fix for that tenant is now a
         first-run date on the cycle, which is a field the wizard asks for,
         rather than a date this file derives from a column nobody chose.
      2. `closed_pending_run` becomes UNREACHABLE. It was the only state derived
         entirely from the day-of-month defaults — *"the read window has shut and
         the cycle's bill day has not arrived"* — and its own gap note
         (`GAP_CYCLE_RUN_NOT_PUBLISHED`) already recorded that it could not say
         whether a run had actually happened, because billing publishes no
         per-cycle run read. The constant and the gap row are KEPT, unrendered,
         because the state is real and the read that would restore it is named:
         when `apps.billing.selectors.last_run_for_cycle` exists, this is where
         it lands. That is a named absence, not dead code — hard-won law 2 asks
         for the name, not for the silence.
    """
    ruled = _cycle_date(cycle.get("next_cycle_date"))
    if ruled is None:
        return None
    # `next_cycle_date` is by construction on or after the moment metering was
    # asked. It can still be in the past here, because the header counts from
    # `read_on` and the cycles were read at the tenant's today (they differ only
    # across a midnight). Zero-or-less reads as TODAY rather than as a negative
    # countdown a clerk cannot act on.
    return ruled, (CYCLE_STATE_CLOSES_IN if as_of < ruled else CYCLE_STATE_TODAY)


def cycle_status_data(cycles: Any, *, as_of: date) -> dict[str, Any]:
    """r10's second line, from SET-07's own definitions (BR-REP-027).

    *"Named cycle is the next-closing active cycle from SET-07 (tie broken by
    account count)"* — the PO, verbatim. Three things fall out of that sentence
    and each is a filter here rather than a judgement:

      ACTIVE      a draft cycle stamps no service point (BR-MET-076) and would
                  count down to a run that cannot happen; an inactive one is
                  retired. Neither is named.
      NEXT        ordered by the candidate's own close DATE ascending. A cycle
                  in the pending-run window has a close date in the PAST, so it
                  sorts ahead of every future close by construction — which is
                  right: the work it is waiting for is the most urgent thing on
                  the screen.
      TIE         more accounts wins. A one-person utility saying "the cycle"
                  means the big one.

    A cycle with no `next_cycle_date` — one whose schedule the period engine
    cannot resolve, most often because it carries no first-run date to anchor
    from — cannot say when it closes and is skipped rather than given a default
    (W5-T2; this said `read_day_to` while the fallback existed). If nothing is
    left, the line is the fourth state and **says so without offering a link**
    (PO 2026-08-19, decision 5): cycle configuration lives in Settings → Routes
    & Cycles, which is CR-006's surface and is in the sidebar on every screen,
    so the dashboard states the fact rather than prompting the errand.
    """
    ranked: list[tuple[date, int, str, dict[str, Any], str]] = []
    for cycle in cycles or ():
        if str(cycle.get("lifecycle_status") or "active") != "active":
            continue
        candidate = _candidate(cycle, as_of)
        if candidate is None:
            continue
        close, state = candidate
        ranked.append(
            (close, -int(cycle.get("accounts") or 0), str(cycle.get("code") or ""), cycle, state)
        )

    if not ranked:
        return {
            "state": CYCLE_STATE_NONE,
            "cycle_code": None,
            "cycle_name": None,
            "days": None,
            "close_date": None,
            "accounts": None,
        }

    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    close, negative_accounts, _code, cycle, state = ranked[0]
    return {
        "state": state,
        "cycle_code": cycle.get("code"),
        "cycle_name": cycle.get("name"),
        "days": None if state == CYCLE_STATE_PENDING_RUN else (close - as_of).days,
        "close_date": close.isoformat(),
        "accounts": -negative_accounts,
        "unavailable": (
            (dict(GAP_CYCLE_RUN_NOT_PUBLISHED),) if state == CYCLE_STATE_PENDING_RUN else ()
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════
# REGION 2 · THE MTD-REVENUE SUB-LINE — BR-REP-034
# ═══════════════════════════════════════════════════════════════════════════
def revenue_target_sub(
    billed: Any, *, target: Any, currency: str | None, number_format: str | None
) -> dict[str, Any] | None:
    """`86% of $400,000 target`, or **nothing at all**.

    The PO ruled option "B" on 2026-08-18 against a worked fixture: MTD billed
    **$342,700.00** against a typed **$400,000** target is 85.675%, which reads
    **86%** — half-up to a whole number, the same rounding the bars use, so no
    two numbers on this screen round differently.

    **`None` is the important return value.** With no target typed the tile
    degrades to the figure alone: no sub-line, no percentage, no bar, no delta.
    That is the state every tenant on this deployment is in and it is not a stub
    — a new tenant on day one must see nothing rather than a wrong denominator.
    A target of ZERO is not a target either and no division is performed on it.

    ⚠ **NOTHING HERE IS PRO-RATED BY DAYS.** The PO declined options (c) and (d)
    for exactly that reason and the arithmetic is worth keeping: if cycle 1 (842
    accounts) issues Aug 5 and cycle 2 (405) issues Aug 20, then on Aug 18
    straight-line assumes 58% of the month is billed while the real billed share
    is 842/1,247 = 68%. Billing is lumpy by cycle, not daily.
    """
    if billed is None or target is None:
        return None
    goal = Decimal(str(target))
    if goal <= 0:
        return None
    percent = fmt.whole_percent(billed, goal)
    if percent is None:
        return None
    return {
        "percent": percent,
        "percent_display": fmt.percent_display(percent),
        "target": wire.money(goal),
        "target_display": fmt.money_display(goal, currency=currency, number_format=number_format),
    }


# ═══════════════════════════════════════════════════════════════════════════
# REGION 5a · AR AGING — BR-REP-030
# ═══════════════════════════════════════════════════════════════════════════
def aging_data(view: Any, *, currency: str | None, number_format: str | None) -> dict[str, Any]:
    """Five bands, straight from `payments.outstandings`, recomputed nowhere.

    ⚠ **THE ARRANGEMENT RULE IS SATISFIED BY WHAT THIS FUNCTION DOES NOT DO.**
    The PO: *"Accounts on an active payment arrangement count in their TRUE
    bucket, not Current."* `payments.outstandings` buckets on the age of an
    account's OLDEST UNPAID BILL and carries `plan_status` as a column it never
    ages by, so an account 45 days late on an active plan is already in `31-60`
    there. The naive implementation moves it to Current; this one has no branch
    that could.

    **Shares are the owner's, not ours**, rounded here to whole numbers for the
    screen — and they are ALLOWED not to sum to 100 (PO verbatim: *"rounded,
    need not total 100%"*). There is no balancing row and there must not be one:
    a fudge row would make the column add up by describing money that is not
    owed. A share of an empty book is `None`, never `0%`.
    """
    served = {str(row["bucket"]): row for row in view.ageing()}
    unknown = set(served) - set(AGING_BUCKETS)
    if unknown:  # pragma: no cover — a divergence must go red, not render wrong
        raise ValueError(
            f"payments published aging buckets this panel has no row for: {sorted(unknown)}"
        )

    rows = []
    for bucket in AGING_BUCKETS:
        row = served.get(bucket) or {}
        amount = row.get("amount")
        share = row.get("share")
        # `share` arrives as the owner's 1-dp string; it is ROUNDED for display
        # and never RE-DERIVED from the amounts, which would make this a second
        # opinion on the same ratio.
        # Half-UP, explicitly. Python's default is ROUND_HALF_EVEN, which turns
        # the owner's 18.5% into 18% and 4.5% into 4% — two rows quietly a point
        # light beside a screen whose every other number rounds half-up (B4.4 ❄️).
        whole = (
            None
            if share in (None, "")
            else int(Decimal(str(share)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        )
        rows.append(
            {
                "bucket": bucket,
                "accounts": row.get("accounts"),
                "accounts_display": fmt.count_display(
                    row.get("accounts"), number_format=number_format
                ),
                "amount": amount,
                "amount_display": fmt.money_display(
                    amount, currency=currency, number_format=number_format
                ),
                "share": whole,
                "share_display": fmt.percent_display(whole),
                "emphasis": "danger" if bucket == DANGER_BUCKET else None,
            }
        )
    total = getattr(view, "total_owed", None)
    return {
        "state": "ok" if any(row["accounts"] for row in rows) else "empty",
        "rows": rows,
        "total": wire.money(total),
        "total_display": fmt.money_display(total, currency=currency, number_format=number_format),
    }


# ═══════════════════════════════════════════════════════════════════════════
# REGION 3 · RECENT ACTIVITY — BR-REP-031
# ═══════════════════════════════════════════════════════════════════════════
def is_operator_relevant(action: Any) -> bool:
    """One of the six classes the PO named, and nothing else."""
    return any(str(action or "").startswith(prefix) for prefix in OPERATOR_ACTIONS)


def role_may_see(action: Any, role: Any) -> bool:
    """*"events the role can't see in their own module are excluded"* (PO).

    Fails closed twice over. An action whose module this map does not know is
    refused, and a role this map does not know is granted nothing — so a new
    role or a new action class is invisible until somebody states where it
    belongs, rather than appearing on every clerk's landing page by default.
    """
    module = next(
        (
            owner
            for prefix, owner in MODULE_OF_ACTION.items()
            if str(action or "").startswith(prefix)
        ),
        None,
    )
    if module is None:
        return False
    return module in ROLE_MODULES.get(str(role or ""), frozenset())


def activity_window(as_of: date) -> tuple[date, date]:
    """BR-REP-031's 24 hours, as an ARGUMENT and never a clock (BR-TEN-043)."""
    return as_of - timedelta(days=ACTIVITY_WINDOW_DAYS), as_of


GAP_ACTIVITY_AMOUNT = {
    "code": "activity_rows_carry_no_amount",
    "br_ref": "BR-REP-031 · BR-REP-024",
    "detail": (
        "r10 draws an amount on some activity rows. `audit_log` has no money column "
        "(apps/audit/models.py: action, entity_type, entity_id, before, after) and "
        "reading a figure out of a stored before/after diff would make this screen a "
        "second opinion on money — DEF-104's shape. Every row renders an em-dash, which "
        "the requirement already provides for ('— where none')."
    ),
    "wanted_reads": ("apps.audit.selectors.audit_row → an `amount` + `currency` pair",),
}


def activity_rows(
    trail: Any, *, currency: str | None, number_format: str | None, role: Any = None
) -> list[dict[str, Any]]:
    """The last day's operator work, newest first, capped at six.

    The filters run in this order and the order is load-bearing: relevance
    first (so the cap is spent on work rather than on sign-ins), then the role
    gate, then the cap. Filtering after the cap would show a clerk four rows on
    a morning that had twenty.
    """
    kept: list[dict[str, Any]] = []
    for row in trail or ():
        action = row.get("action")
        if not is_operator_relevant(action):
            continue
        if role is not None and not role_may_see(action, role):
            continue
        kept.append(
            {
                "at": row.get("created_at"),
                "action": action,
                "entity_type": row.get("entity_type"),
                "entity_id": row.get("entity_id"),
                "actor": (row.get("actor") or {}).get("name") if row.get("actor") else None,
                # BR-REP-024: there is no amount to render and none is derived.
                "amount": None,
                "amount_display": fmt.EM_DASH,
            }
        )
        if len(kept) >= ACTIVITY_MAX_ROWS:
            break
    return kept


# ═══════════════════════════════════════════════════════════════════════════
# REGION 5b · TO DO — BR-REP-032
# ═══════════════════════════════════════════════════════════════════════════
def todo_rows(
    *,
    billing_exceptions: Any,
    onboarding: Any,
    rate_approvals: Any,
    disconnect_eligible: Any,
    finance_close: Any,
    number_format: str | None,
) -> list[dict[str, Any]]:
    """At most four items, every one generated by the module that owns the work.

    **An owner with nothing to say adds no row.** A to-do reading *"0 billing
    exceptions"* is a task that does not exist, so an owner that answers ZERO
    contributes nothing and an owner that answers nothing at all contributes
    nothing either.

    ⚠ **BUT A ROW THAT EXISTS AND CANNOT BE SIZED SHOWS NO NUMBER — PO ruling
    2026-08-19, decision 3, verbatim: *"I will start with - Show 'Review billing
    exceptions' with no number"*.** What the PO was shown: *"Review 3 billing
    exceptions"*, where the 3 is billing's, and **if billing cannot answer, a
    `0` tells the operator "nothing needs my attention", which is false.** So
    `count=None` on an emitted row is a real state and it carries
    `count_display=None` with it — the label alone, never a zero and never a
    dash standing in for a digit. It is the KPI rule (BR-REP-024) applied to
    this panel, and it covers all six emittable codes: `billing_exceptions`,
    `disconnect_eligible`, `finance_close`, `rate_approvals`, `import_reads`,
    `run_billing`.

    **`finance_close` is the live case, and it was a latent crash (DEF-304).**
    `seams.open_finance_close()` is documented to publish a DICT naming the
    period a close is outstanding for — not an int — and this function used to
    call `int()` on whatever it was handed. The seam is dark today, so the day
    the ledger lands that read the To-do region would have failed into its own
    error state on `TypeError: int() argument must be...`. A finance close is
    inherently a countless task: the row now renders the label alone.

    **Nothing here is stored.** There is no to-do table, no done flag and no
    dismiss control: every count is recomputed from its owner on each read, so
    an item disappears because the WORK disappeared. That is the PO's clearing
    rule — *"completing the work in the owning module clears the item on next
    refresh"* — satisfied by construction rather than by a job that could fail.

    Order is the PO's own listing order: `action` before `review` before
    `draft`, with the new-tenant onboarding steps last because they are the only
    items that are not operational work.
    """
    rows: list[dict[str, Any]] = []

    def add(kind: str, code: str, count: Any, module: str, target: str) -> None:
        """One row. `count=None` means THE WORK EXISTS AND ITS SIZE IS UNKNOWN.

        The two absences are kept apart on purpose. A count of `0` means the
        owner counted and found nothing, so there is no row; `None` means the
        owner could not count, so there IS a row and it carries no number. The
        `count_display` is `None` in lockstep — a served display string with a
        null count is exactly how a `0` gets back onto the screen.
        """
        sized: int | None = None
        if count is not None:
            try:
                sized = int(count)
            except (TypeError, ValueError):
                # The owner published something that is not a number — a dict
                # naming a period, say. That is "there is work here" without a
                # size, which is precisely the ruled state. DEF-304.
                sized = None
            else:
                if sized <= 0:
                    return
        rows.append(
            {
                "kind": kind,
                "code": code,
                "count": sized,
                "count_display": (
                    None if sized is None else fmt.count_display(sized, number_format=number_format)
                ),
                "module": module,
                "target": target,
            }
        )

    if billing_exceptions is not None:
        add("action", "billing_exceptions", billing_exceptions, "billing", "billing")
    if rate_approvals is not None:
        add("review", "rate_approvals", rate_approvals, "rating", "plans-rates")
    if disconnect_eligible is not None:
        add("review", "disconnect_eligible", disconnect_eligible, "customers", "accounts")
    if finance_close is not None:
        add("draft", "finance_close", finance_close, "ledger", "finance")

    for item in onboarding or ():
        if len(rows) >= TODO_MAX_ROWS:
            break
        rows.append(
            {
                "kind": "onboarding",
                "code": item.get("item"),
                "count": None,
                "count_display": None,
                "module": "tenancy",
                "target": item.get("target"),
            }
        )
    return rows[:TODO_MAX_ROWS]


def page_actions(role: Any) -> dict[str, bool]:
    """BR-REP-033 — *"Both hidden for read-only roles."*

    Decided on the SERVER. A control hidden only by the client is a suggestion,
    not a permission; this says what the role may DO and the screen renders
    accordingly. It fails closed: a role this product does not know gets
    neither action.
    """
    may = str(role or "") in ROLES_MAY_RUN_WORK
    return {"import_reads": may, "run_billing": may}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-012 (12-governance/11-change-requests.md §CR-012 — the PO's build spec and the FULL DSH-01 requirements verbatim, plus §"THE BAR RULE, WORKED") · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-024..034 · 04-docs/05-modules/12-reports/06-epics/EP-REP-05-dashboards.md §US-REP-019 AMENDMENT · 12-governance/02-decision-log.md 2026-08-18 (both rulings) · 04-docs/01-spec/04-roles-permissions.md (A4 addendum — the three predefined roles)
# screens: S7
# generated: 2026-08-18 by story-coder (CR-012 DSH-01 lane) · AMENDED 2026-08-19 by story-coder (CR-012 closing lane — the five PO rulings from the design review, decision log 2026-08-19)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_cr012_dashboard_dsh01.py could not import this module before it existed ("ImportError: cannot import name 'dashboard_regions' from 'apps.reports'"), and each behaviour's own first failure is quoted in the section header of the case that closed it.
# exceptions: AMENDED 2026-08-19 for the five PO rulings — (0) the service-mix ROW SET is now tenancy's `enabled_service_codes()` rather than a constant in this file; when tenancy cannot answer the panel draws what BILLED and reports `configured_services_are_not_published_by_tenancy` BY NAME, and the old five are NOT used as a fallback because they are the wrong list for most utilities · (0b) the `not_configured` cycle state serves no `settings_target` any more (PO d.5, *"no provide any link"*) · (0c) `todo_rows` emits `count=None` with `count_display=None` for a row whose owner published something unsizeable, which is DEF-304's latent `int(dict)` crash turned into the ruled state · (1) `guard` catches a bare Exception ON PURPOSE and the reason is in its docstring — a read model that cannot answer must say so in its own square inch rather than 500 the landing page · (2) ⚠ AMENDED 2026-08-23 (CR-029 W5-T2): the 'closed — bill run pending' state is now UNREACHABLE — it was derived entirely from the day-of-month defaults metering 0021 dropped. The constant and `GAP_CYCLE_RUN_NOT_PUBLISHED` are KEPT unrendered because the state is real and the read that would restore it is named (`apps.billing.selectors.last_run_for_cycle`); that is a named absence, not dead code · (3) ⚠ AMENDED 2026-08-23 (CR-029 D8②, COMPLETED BY W5-T2): `CYCLE_CLOSE_FIELD` is GONE. OQ-221's derivation guessed `read_day_to`; the PO stated *"Next cycle date"*, so the countdown reads metering's derived `next_cycle_date` — and the transitional day-of-month branch that survived alongside it is gone too, with `_day_in_month` and `_next_month`. A cycle that cannot say when it next comes round is SKIPPED · (4) three to-do owners (rating approvals, disconnect eligibility, finance close) publish nothing, so they contribute no row rather than a zero — each names the read that would close it in dashboard_seams.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
