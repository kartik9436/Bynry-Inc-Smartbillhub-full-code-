# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-019 (S7 — the landing screen)   Screens: S7
# Change:   CR-015 (PO 2026-08-19 — *"we will ahve to allow period filter on
#           dashbaord - so user can select the filter ; default filter can be
#           last cycle or last 30 days and let user to change the peiod"*)
# Defect:   DEF-299 (`as_of` was the PERIOD END, so the screen labelled itself
#           as of a moment eleven days in the future) · DEF-298 (a calendar
#           month is the wrong window for cycle-shaped work)
# Rules:    BR-REP-035 (the period vocabulary and its default) · BR-REP-036
#           (`as_of` is the READ moment clamped into the selected period) ·
#           BR-TEN-022 (an accounting period is COMPUTED, never stored) ·
#           BR-TEN-043 (a window is an ARGUMENT, never a clock) · BR-SHL-011
#           (an unknown or impossible parameter falls back, never errors) ·
#           BR-REP-027 (the cycle facts are SET-07's, read through the seam)
# Tests:    06-backend/tests/test_cr015_dashboard_period.py
# Impacts:  apps/reports/dashboard.py (its only caller) · apps/reports/api.py
#           (the `period` query parameter) · 07-frontend DashboardPage (the
#           control and the on-screen statement)
# ───────────────────────────────────────────────────────
"""S7's period vocabulary — WHICH window the landing screen reports over.

════════════════════════════════════════════════════════════════════════════
WHY A CALENDAR MONTH WAS THE WRONG WINDOW (CR-015, and it is not about a fixture)
════════════════════════════════════════════════════════════════════════════
DEF-298 was first diagnosed as a SEED problem — the demo bills July and the
dashboard shows the current month, so the demo looks dead. The PO corrected it,
and the case that shows the correction uses no demo data at all:

    A real utility, on the **3rd of any month**. Bills went out on the 25th.
    The dashboard shows the calendar month, so it shows almost nothing — for
    the first week of every month, forever. Revenue near zero, service mix
    nearly empty. Nothing is broken and the operator cannot tell why the
    screen looks dead.

The seed did not cause that; the seed EXPOSED it. Billing is **lumpy by cycle,
not daily** (the forecast analysis of 2026-08-18, applied to the sub-line and
not to the period underneath it). So the window becomes something the operator
chooses, and it defaults to the utility's own unit of work.

════════════════════════════════════════════════════════════════════════════
⚠ THE "LAST COMPLETED CYCLE" WINDOW IS REMOVED — CR-029 D8①, PO 2026-08-23
════════════════════════════════════════════════════════════════════════════
Asked what makes a cycle *"completed"*, the Product Owner ruled, verbatim:
**"dont build it"**.

What stood here until that ruling was a definition this lane had DERIVED and
flagged as a judgment: *a cycle is complete when its bill date has passed, and
its window runs `window_start` … `bill_date`*. It was raised as **OQ-268** on
2026-08-19 and never ruled — and the answer, when it came, was that the concept
is not to be built at all.

So the option is gone, the function that computed it is gone, and **nothing is
substituted**. A second definition — the last window that has ELAPSED, say —
would be the same invention wearing different words, and B17 §7 W2-T3 is
explicit: *"the dashboard stops claiming it rather than keep guessing. Removing
a claim is the deliverable here; do not invent a definition."*

**WHAT THIS COSTS, STATED RATHER THAN GLOSSED.** CR-015's own ruling offered
*"last cycle or last 30 days"* and this lane chose the first as the default. The
default is now the rolling thirty days — a window that agrees with nothing else
in the product, which is exactly why it was the fallback rather than the choice.
The screen still STATES the dates it is reporting over, so no figure wears a
label it does not fit, and `GAP_CYCLE_WINDOW_NOT_OFFERED` says on the payload
that a cycle window is not among the choices. If the PO later wants a
cycle-shaped window back, what they are being asked is *what makes a cycle
completed* — the question D8① answered, and the one nobody may answer here.

════════════════════════════════════════════════════════════════════════════
NO CLOCK LIVES HERE
════════════════════════════════════════════════════════════════════════════
Every function takes `as_of` as an ARGUMENT (BR-TEN-043). Nothing in this file
calls `date.today()`, and nothing touches the database: the cycle rows and the
accounting periods are handed in by `dashboard.py` from the seams that own
them. That is what makes the whole vocabulary testable against a signed figure
without a fixture.
"""

from datetime import date, timedelta
from typing import Any

#: The option ids. They are STABLE MACHINE TOKENS the screen keys its own
#: translated label on (TD-16/B8 — the server sends keys, the UI renders
#: language), and they are the `f.period` URL value (BR-SHL-011), so a period a
#: person is looking at can be pasted into a message and opened by somebody else.
OPTION_LAST_CYCLE = "last_cycle"
OPTION_LAST_30_DAYS = "last_30_days"
OPTION_THIS_PERIOD = "this_period"
OPTION_LAST_PERIOD = "last_period"

#: 30 days INCLUSIVE of the read day — `as_of - 29 … as_of` is thirty dates.
#: Spelled as a constant because the fence-post is exactly the sort of thing a
#: later edit gets wrong by one day in a window that labels itself "30 days".
LAST_30_DAYS_SPAN = 30

#: The order the options are OFFERED in, which is the order the screen draws
#: them: the rolling window first and the two accounting windows after, so a
#: finance officer reconciling against S36 knows to look for the period by name.
#:
#: ⚠ **`OPTION_LAST_CYCLE` IS DELIBERATELY ABSENT (CR-029 D8①).** The constant
#: itself is KEPT so that `f.period=last_cycle` — a link somebody shared while
#: the option existed — is still a value this module recognises as a token and
#: falls back on (BR-SHL-011), rather than a string nothing in the codebase
#: explains. It is never built and never offered.
OPTION_ORDER = (
    OPTION_LAST_30_DAYS,
    OPTION_THIS_PERIOD,
    OPTION_LAST_PERIOD,
)

#: Why `this_period` and `last_period` are not on the menu for a tenant with no
#: fiscal calendar. ⚠ **THIS IS WHERE `fiscal_period_not_configured` MOVED TO,
#: AND THE MOVE IS DELIBERATE** — see `dashboard.py`'s docstring. It used to
#: mean *"every money figure on this screen is null"*; it now means *"two of the
#: four windows cannot be offered"*, because the screen no longer has to guess
#: which window it is showing: it STATES it. A KPI headed "this period" over a
#: substituted calendar month is a wrong number wearing a right label; a KPI
#: headed "21 Jul – 19 Aug 2026 · Last 30 days" is a right number wearing its own.
GAP_NO_ACCOUNTING_PERIOD = {
    "code": "fiscal_period_not_configured",
    "br_ref": "BR-TEN-022 · BR-REP-035",
    "detail": (
        "An accounting period is COMPUTED from the tenant's fiscal settings and never "
        "stored. This tenant has none configured, so the two accounting windows — this "
        "period and last period — are not offered. The cycle and rolling windows do not "
        "depend on a fiscal calendar and are offered as usual, each labelled on screen "
        "with the exact dates it covers."
    ),
    "wanted_reads": (),
}

#: Why no cycle-shaped window is on the menu at all — CR-029 D8①, *"dont build
#: it"*. Served on every tenant, because the absence is a product decision and
#: not a state of this tenant's data: a utility with six perfectly healthy
#: cycles sees it too, and the sentence has to be true for that reader.
#:
#: ⚠ The customer sentence carries **no provenance** — no rule id, no
#: open-question id, no module path (G28: *"keep the honesty, drop the
#: provenance"*). The provenance is this comment: D8① answered OQ-268 by
#: withdrawing the concept.
GAP_CYCLE_WINDOW_NOT_OFFERED = {
    "code": "billing_cycle_window_is_not_offered",
    "br_ref": "BR-REP-035 · CR-029 D8①",
    "detail": (
        "Reporting over a whole billing cycle is not offered. It needs a definition of "
        "when a cycle is FINISHED, the one this lane derived was raised as OQ-268 and "
        "never ruled, and CR-029's D8 answered it by withdrawing the concept — PO, "
        "2026-08-23: 'what makes a cycle completed - dont build it'. Nothing is "
        "substituted: a second definition would be the same invention in other words. "
        "Every window that IS offered states the exact dates it covers, so no figure "
        "wears a label it does not fit."
    ),
    "wanted_reads": (),
}


def _day(value: Any) -> date | None:
    """One ISO calendar day as a `date`, or None. Seams serve ISO STRINGS.

    Parsed rather than passed through for the reason `dashboard._day` gives: a
    string compared against a date is compared by the database's coercion rules
    instead of Python's, which is a silent environment-dependent difference with
    no business inside a money window.
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def rolling_30_days(*, as_of: date) -> dict[str, Any]:
    """`as_of - 29 … as_of`. Always available — it needs nothing configured."""
    return {
        "id": OPTION_LAST_30_DAYS,
        "start": as_of - timedelta(days=LAST_30_DAYS_SPAN - 1),
        "end": as_of,
    }


def _accounting_option(option_id: str, period: dict[str, Any] | None) -> dict[str, Any] | None:
    """One of BR-TEN-022's computed windows, or None when there is no calendar."""
    if not period:
        return None
    start = _day(period.get("start"))
    end = _day(period.get("end"))
    if start is None or end is None:
        return None
    return {
        "id": option_id,
        "start": start,
        "end": end,
        "fy_label": period.get("fy_label"),
        "period_no": period.get("period"),
    }


def period_options(
    *,
    as_of: date,
    accounting_period: dict[str, Any] | None,
    previous_accounting_period: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Every window this tenant may be shown, and why any is missing.

    Returns `(options, unavailable)`. An option that cannot be built is ABSENT
    from the menu with a named reason beside it, never present-but-broken: a
    filter entry that selects a window nobody can compute is the same false
    affordance as a KPI showing zero because nothing answered.

    ⚠ **NO `cycles` PARAMETER ANY MORE (CR-029 D8①).** It existed only to build
    the completed-cycle window, and a parameter nothing reads is dead payload
    that reads as a feature (hard-won law 2). The caller still reads SET-07's
    cycles — the cycle-status region needs them — and no longer passes them
    here.
    """
    built: dict[str, dict[str, Any]] = {}
    unavailable: list[dict[str, Any]] = [dict(GAP_CYCLE_WINDOW_NOT_OFFERED)]

    built[OPTION_LAST_30_DAYS] = rolling_30_days(as_of=as_of)

    this_period = _accounting_option(OPTION_THIS_PERIOD, accounting_period)
    last_period = _accounting_option(OPTION_LAST_PERIOD, previous_accounting_period)
    if this_period is None and last_period is None:
        unavailable.append(dict(GAP_NO_ACCOUNTING_PERIOD))
    if this_period is not None:
        built[OPTION_THIS_PERIOD] = this_period
    if last_period is not None:
        built[OPTION_LAST_PERIOD] = last_period

    return [built[key] for key in OPTION_ORDER if key in built], unavailable


def default_option_id(options: list[dict[str, Any]]) -> str | None:
    """The default: the rolling thirty days.

    It was the completed-cycle window until CR-029 D8① withdrew the concept
    (*"dont build it"*), and the rolling window was already the ruled FALLBACK
    for a tenant with no such cycle — so the screen opens on a window CR-015's
    own ruling named, rather than on one invented to replace the removed one.

    ⚠ Read from the options that were actually BUILT, never asserted. A default
    naming a window the menu does not carry is a screen that opens on nothing.
    """
    ids = {option["id"] for option in options}
    if OPTION_LAST_30_DAYS in ids:
        return OPTION_LAST_30_DAYS
    return options[0]["id"] if options else None


def resolve(options: list[dict[str, Any]], requested: str | None) -> dict[str, Any] | None:
    """The window to report over — the requested one, or the default.

    BR-SHL-011: an unknown, misspelled or no-longer-available value FALLS BACK
    rather than refusing. A landing page that 500s on a stale bookmark is a
    locked front door, and `?f.period=last_cycle` on a tenant that has since
    retired its only cycle is exactly that bookmark.
    """
    chosen = default_option_id(options)
    for option in options:
        if requested is not None and option["id"] == requested:
            chosen = option["id"]
            break
    for option in options:
        if option["id"] == chosen:
            return option
    return None


def clamp_as_of(read_on: date, window: tuple[date, date] | None) -> date:
    """DEF-299 / BR-REP-036 — the READ moment, clamped into the selected period.

    The PO's ruling of 2026-08-19, option (a), verbatim: *"`as_of` is the moment
    the figures were read, clamped into the selected period — so mid-period it
    is today, and once a period closes it is the period end."*

    Before this the value was the period END unconditionally, so on 19 Aug the
    first screen after every sign-in labelled itself **as of 31 Aug** — a moment
    eleven days in the future. Nothing disagreed with anything else, which is
    why every internal consistency check passed; what was wrong was what it
    MEANT. The PO's own rule is that a KPI must agree with its owning module
    **for the same as-of moment**, and that rule cannot be checked by a person
    comparing labels when the dashboard says the 31st and Finance says the 19th.

    Both ends clamp. The lower clamp is not decoration: a window entirely in the
    past (last cycle, last period) takes its END, and a window entirely in the
    future — which no option builds today, and which a later one might — would
    take its START rather than claiming figures were read before it began.
    """
    if window is None:
        return read_on
    start, end = window
    if read_on < start:
        return start
    if read_on > end:
        return end
    return read_on


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-015 (12-governance/11-change-requests.md §CR-015 — the PO's request verbatim, the 3rd-of-the-month case, and the two things it drags with it) · 12-governance/02-decision-log.md 2026-08-19 §"FOUR RULINGS" 3 and 4 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-035/036 · 04-docs/05-modules/01-tenancy/02-business-rules.md BR-TEN-022/043
# screens: S7   (DEF-137's screen-id stamp — see 10-scripts/gates/g25_screen_coverage.py)
# generated: 2026-08-19 by story-coder (CR-015 lane — the dashboard could report over one window and nobody could change it)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case in tests/test_cr015_dashboard_period.py failed before this module existed (ModuleNotFoundError), and the as_of case was proved against the LIVE fixture reading `as_of 2026-08-31` on 2026-08-19. ruff✔ black✔ pytest✔
# exceptions: (1) "a cycle is COMPLETE when its bill date has passed, and its window runs window_start…bill_date" is a LANE JUDGMENT over SET-07's published fields, not a signed rule — recorded in the decision log with the worked cycle (08-B, reads 12–16 Aug, bills 19 Aug) rather than left in the code alone, and minted as OQ-268 · (2) `fiscal_period_not_configured` no longer blanks every money figure: it now withdraws two of four OPTIONS, because a window that STATES its own dates on screen is not a KPI wearing a wrong label · (3) no clock and no database in this file — every input is an argument, which is what makes the vocabulary testable against a signed figure
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
