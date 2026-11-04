# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.12`
#          (*"the period-and-comparison service"*). Drawing p36–p38, screen
#          `3·1`, read as IMAGES per B14 rule 42.
# Rules:   BR-TEN-022 (an accounting period is COMPUTED, never stored) ·
#          BR-TEN-043 (a window is an ARGUMENT, never a clock) · BR-SHL-011
#          (an unknown or impossible parameter falls back, never errors) ·
#          BR-REP-024 (a figure that cannot be computed is null WITH a reason,
#          never 0)
# Tests:   06-backend/tests/test_rep_p4_dashboard_tab.py
# Impacts: apps/reports/dashboard_tab.py (its only caller) ·
#          apps/reports/dashboard_tab_api.py (the `period` / `compare` query
#          parameters) · 07-frontend ReportsDashboardPage (the two controls)
# ───────────────────────────────────────────────────────
"""Screen `3·1`'s two controls — WHICH period, and WHAT it is compared against.

⚠ **NOTHING IN `apps/reports/dashboard_period.py` IS REUSED AND THAT IS THE
BRIEF'S OWN INSTRUCTION, NOT TIDINESS.** p37 REPO row, verbatim: *"Nothing.
⚠ And nothing in `apps/reports/dashboard.py` is reused — that file serves the
shell's screen and is not touched."* `dashboard_period.py` is that screen's
vocabulary and it answers a DIFFERENT question: it offers a **rolling thirty
days** by default, and p37 ② is explicit that a rolling window is the one thing
this screen may not have —

    *"a real period, not a rolling window. This is the difference from the
     shell dashboard: a manager reads September, and a rolling thirty days
     straddles two cycles and answers nobody's question."*

Two dashboards, two questions (p36): the shell's is a clerk's morning glance,
*what needs me today*; this is an owner's monthly read, *how are we doing*. A
shared period vocabulary would have forced one of them to answer the other's.

⚠ **THE OPTION ID IS THE PERIOD'S START DATE AND NOT A ROW ID** (B14 rule 31,
and BR-TEN-022: there is no row — a period is computed). It rides in the URL as
`?period=2026-09-01`, so a link pasted into a board pack opens on the same
month for the person who receives it, which p38 names as the whole reason the
period is in the URL at all.

⚠ **NO CLOCK LIVES HERE.** Every function takes `as_of` as an argument
(BR-TEN-043) and nothing calls `date.today()`. The accounting periods are
handed in by the caller from the seam that owns them, which is what makes the
whole vocabulary testable against a signed figure without a fixture.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

#: How many periods back the menu offers. TWELVE, because the `Revenue, 12
#: months` panel draws twelve bars and a menu shorter than the chart would let a
#: reader see a bar for a period they cannot then select.
#:
#: ⚠ **THIS IS A MENU LENGTH AND NOT A CAP ON ANYTHING** (`NFR-5`). An older
#: period is still reachable by typing its start date into the URL, and
#: `resolve()` honours it: what is bounded is the number of options DRAWN, not
#: the set of periods this screen can report over.
PERIODS_OFFERED = 12

#: The comparison tokens. STABLE MACHINE TOKENS the screen keys its translated
#: label on (TD-16/B8 — the server sends keys, the UI renders language), and the
#: `?compare=` URL value.
COMPARE_SAME_PERIOD_LAST_YEAR = "same_period_last_year"
COMPARE_PREVIOUS_PERIOD = "previous_period"
COMPARE_BUDGET = "budget"

#: The order they are OFFERED in, which is the order the screen draws them. The
#: drawing's own order (p36 control ③): *same month last year · previous month ·
#: budget*.
COMPARE_ORDER = (COMPARE_SAME_PERIOD_LAST_YEAR, COMPARE_PREVIOUS_PERIOD)

#: The default. p36 draws the control reading *vs. same month last year*, and
#: p37 ③ says why a comparison exists at all: *"a number with nothing beside it
#: is not a performance report"*.
COMPARE_DEFAULT = COMPARE_SAME_PERIOD_LAST_YEAR

#: ⚠ **THE DRAWING NAMES THE PERIODS *month* AND THESE TOKENS SAY *period*, AND
#: THE DIFFERENCE IS DELIBERATE — DIVERGENCE FROM p36, REPORTED.** A tenant's
#: `close_cadence` may be `quarterly` (`apps/tenancy/selectors.current_period`),
#: in which case its accounting period is three months long and a token spelled
#: `same_month_last_year` would be a name that lies on every quarterly utility.
#: B14 rule 37 settles which half of the drawing binds: a figure drawn in a
#: wireframe is an ILLUSTRATION. The WORDS on screen still read *September 2026*
#: and *vs. same month last year* for a monthly tenant, because the label is
#: composed from the period the server served rather than from this token.

#: Why `budget` is not on the menu. p36 draws three comparison choices and this
#: deployment can honour two: **nothing in this product publishes a budget.**
#:
#: ⚠ **`apps/reports/report_seams.monthly_revenue_target()` IS NOT ONE AND
#: SUBSTITUTING IT WOULD BE THE WORST AVAILABLE ANSWER.** It is a single typed
#: REVENUE target that the shell dashboard's `mtd-revenue` tile renders
#: (BR-REP-034). This screen has FOUR KPIs; a *budget* comparison built on it
#: would show a real comparison on one tile and an invented one on three, which
#: is a screen that is wrong in a way a reader cannot see.
#:
#: The sentence carries NO provenance — no rule id, no module path (G28: *"keep
#: the honesty, drop the provenance"*). The provenance is this comment.
GAP_BUDGET_NOT_OFFERED = {
    "code": "budget_comparison_is_not_offered",
    "br_ref": "BR-REP-024 · CR-142-BRC07 P4.12",
    "detail": (
        "Comparing against budget is not offered. No report in the catalogue publishes a "
        "budget for billed, collected, outstanding or days to collect, and a comparison "
        "built from a single revenue target would be a real figure on one tile and an "
        "invented one on the other three. The two comparisons that ARE offered are struck "
        "against periods this product computes."
    ),
    "wanted_reads": (),
}

#: Why there is no menu at all. BR-TEN-022 — a period is COMPUTED from the
#: tenant's fiscal settings, and a tenant that has configured none has no
#: periods to offer. This screen does NOT substitute a calendar month: p37 ②
#: exists because a window that answers nobody's question is worse than a
#: missing one.
GAP_NO_ACCOUNTING_PERIOD = {
    "code": "fiscal_period_not_configured",
    "br_ref": "BR-TEN-022 · BR-REP-035",
    "detail": (
        "An accounting period is computed from the tenant's fiscal settings and never "
        "stored. This tenant has none configured, so this screen has no period to report "
        "over and offers none. A calendar month is not substituted: it would head every "
        "figure on this screen with a window the utility does not close its books on."
    ),
    "wanted_reads": (),
}


def _day(value: Any) -> date | None:
    """One ISO calendar day as a `date`, or None. The seam serves ISO STRINGS.

    Parsed rather than passed through: a string compared against a date is
    compared by the database's coercion rules instead of Python's, which is a
    silent environment-dependent difference with no business inside a money
    window.
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _option(period: dict[str, Any] | None) -> dict[str, Any] | None:
    """One computed accounting period as a menu option, or None."""
    if not period:
        return None
    start = _day(period.get("start"))
    end = _day(period.get("end"))
    if start is None or end is None:
        return None
    return {
        "id": start.isoformat(),
        "start": start,
        "end": end,
        "fy_label": period.get("fy_label"),
        "period_no": period.get("period"),
    }


def period_options(
    *, as_of: date, current_period: Callable[[date], dict[str, Any] | None]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The periods this tenant may be shown, newest first, and why any is missing.

    `current_period` is the tenant seam, passed in rather than imported, so this
    module keeps its promise of touching no database and holding no clock.

    ⚠ **THE MENU IS BUILT BY WALKING BACK FROM EACH PERIOD'S OWN START, NEVER BY
    SUBTRACTING A MONTH.** A period's length is the tenant's — one month or
    three — and the seam is the only thing that knows which. Asking it for the
    period containing *the day before this period started* gets the previous
    period whatever its cadence, and gets it right across a fiscal year
    boundary, which arithmetic on month numbers does not.
    """
    options: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = [dict(GAP_BUDGET_NOT_OFFERED)]

    cursor: date | None = as_of
    seen: set[str] = set()
    while cursor is not None and len(options) < PERIODS_OFFERED:
        option = _option(current_period(cursor))
        if option is None or option["id"] in seen:
            # None ⇒ no fiscal calendar (or a period the seam could not compute).
            # A repeat ⇒ the seam clamped rather than stepping back, and walking
            # on would loop for ever.
            break
        seen.add(option["id"])
        options.append(option)
        # The day before this period began is, by construction, in the one
        # before it. `option["start"]` is a real date, so `.toordinal()` − 1 is
        # a real date too, with no month arithmetic anywhere.
        cursor = date.fromordinal(option["start"].toordinal() - 1)

    if not options:
        unavailable.append(dict(GAP_NO_ACCOUNTING_PERIOD))
    return options, unavailable


def resolve(
    options: list[dict[str, Any]],
    requested: str | None,
    *,
    current_period: Callable[[date], dict[str, Any] | None],
) -> dict[str, Any] | None:
    """The period to report over — the requested one, or the newest.

    BR-SHL-011: an unknown, misspelled or no-longer-offered value FALLS BACK
    rather than refusing. A dashboard that 500s on a stale link is a locked
    door, and `?period=` is exactly the part of the URL a person edits by hand.

    ⚠ **A PERIOD OLDER THAN THE MENU IS HONOURED RATHER THAN FALLING BACK**
    (`NFR-5`). `PERIODS_OFFERED` bounds what is DRAWN; a link to
    `?period=2024-03-01` still opens on March 2024, because a menu length is not
    a cap on what the product can report. The seam is asked for the period
    containing that day, so a start date a period does not actually begin on
    resolves to the period it falls in rather than to a window this product
    never closes its books on.
    """
    if not options:
        return None
    wanted = _day(requested)
    if wanted is not None:
        for option in options:
            if option["id"] == wanted.isoformat():
                return option
        older = _option(current_period(wanted))
        if older is not None:
            return older
    return options[0]


def comparison_options() -> list[dict[str, Any]]:
    """The comparisons offered, in the drawing's order. Two of p36's three."""
    return [{"id": token} for token in COMPARE_ORDER]


def resolve_comparison(requested: str | None) -> str:
    """The comparison to strike — the requested one, or the default.

    BR-SHL-011 again, and `budget` falls back here like any other unknown value:
    it is NOT a special case, because `GAP_BUDGET_NOT_OFFERED` already says on
    the payload why it is absent, and a second refusal path would be a second
    sentence to keep in step with the first.
    """
    return requested if requested in COMPARE_ORDER else COMPARE_DEFAULT


def comparison_window(
    period: dict[str, Any],
    comparison: str,
    *,
    current_period: Callable[[date], dict[str, Any] | None],
) -> dict[str, Any] | None:
    """The window `comparison` names, relative to `period`, or None.

    None is a real answer and not a failure: a tenant in its first period has no
    previous one, and a tenant live for six months has no same-period-last-year.
    Every KPI then renders its figure with **nothing beside it**, which is
    honest, rather than a comparison struck against a window that does not
    exist.
    """
    start = period["start"]
    if comparison == COMPARE_PREVIOUS_PERIOD:
        return _option(current_period(date.fromordinal(start.toordinal() - 1)))
    if comparison == COMPARE_SAME_PERIOD_LAST_YEAR:
        # The same DAY one year earlier, handed to the seam — never
        # `start.replace(year=...)` arithmetic on the window itself. A fiscal
        # year that moved, or a 29 February start, is the seam's problem and it
        # already solves it (`_safe_date` clamps the day into the month).
        try:
            anchor = start.replace(year=start.year - 1)
        except ValueError:  # 29 Feb → 28 Feb
            anchor = start.replace(year=start.year - 1, day=28)
        return _option(current_period(anchor))
    return None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P4.12 (05-prototype/09 Reports Build Brief.pdf pp36-38, read as IMAGES per B14 rule 42) · 04-docs/05-modules/01-tenancy/02-business-rules.md BR-TEN-022/043 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-024
# screens: 3·1
# generated: 2026-09-27 by lane REP-P4-DASH
# checklist: A✔ B=n/a(the screen is P4.11's file) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case in tests/test_rep_p4_dashboard_tab.py failed before this module existed (ModuleNotFoundError: apps.reports.dashboard_tab_period).
# exceptions: (1) the comparison tokens say `period` where p36's copy says `month` — a quarterly tenant's period is three months and a token spelled `month` would lie on it. B14 rule 37 (a drawn figure is an illustration). DIVERGENCE FROM p36, REPORTED · (2) `budget`, the third comparison p36 draws, is NOT offered: nothing in this product publishes a budget for any of the four KPIs. Named on the payload rather than silently dropped · (3) `PERIODS_OFFERED` bounds the MENU and caps nothing — an older period typed into the URL is still served (NFR-5)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
