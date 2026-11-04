# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 4 `P4.11` (the screen's
#          data) and `P4.13` (the panel→report handoff, *"which must carry the
#          period across"*). Drawing p36–p38, screen `3·1`, read as IMAGES per
#          B14 rule 42.
# Rules:   BR-REP-024 (a figure that cannot be computed is null WITH a reason,
#          never 0) · BR-REP-001 (a basis label on every report) · CLAUDE.md
#          hard rule 2 (money stored 4, displayed 2 — this file passes decimal
#          STRINGS through and rounds nothing) · hard rule 3 (a quantity
#          carries its unit) · hard-won law 2's mirror (a live screen behind a
#          dead control)
# Tests:   06-backend/tests/test_rep_p4_dashboard_tab.py
# Impacts: apps/reports/dashboard_tab_api.py (the route) · 07-frontend
#          ReportsDashboardPage.tsx and its five panel components
# ───────────────────────────────────────────────────────
"""Screen `3·1` — the Reports **Dashboard** tab. Four KPIs and five panels.

⚠ **THIS IS A NEW SCREEN AND IT DOES NOT TOUCH THE ONE WE ALREADY HAVE.**
PO ruling quoted on p36, verbatim: *"no i dont want to update existing dashboard
… you can create a tab - dont replace existing one"*. The shell's dashboard at
`/{tenant}/dashboard` — rail item 1, the screen after every sign-in — is
untouched by every task in this plan, and `apps/reports/dashboard.py` is not
imported here. Two dashboards is the right number because they answer different
questions to different people: one is a clerk's morning glance, *what needs me
today*; this is an owner's monthly read, *how are we doing*.

════════════════════════════════════════════════════════════════════════════
NOTHING ON THIS SCREEN COMPUTES ANYTHING — p38, AND IT IS THE WHOLE DESIGN
════════════════════════════════════════════════════════════════════════════
    *"Every figure here comes from a definition in the catalogue. ⚠ Nothing on
     this screen computes anything. The moment a panel does its own arithmetic,
     the dashboard and the report start disagreeing, and the utility stops
     trusting both."*

So every figure below is lifted from a report the catalogue already serves,
through the same functions `GET /reports/{key}` runs — `queries.VIEWERS` — and
never from a seam of its own. A panel is *a saved report rendered small*
(p37 DATASETS), which is what makes a panel and the report behind it incapable
of disagreeing.

⚠ **TWO REGROUPINGS ARE PERFORMED AND BOTH ARE NAMED HERE RATHER THAN HIDDEN.**
The `Service mix` panel SUMS the Revenue Analysis rows that share a service, and
the `Where the money sits` panel takes the SHARE each ageing band is of the
receivable. Neither derives money: the first adds published totals at a coarser
grain of the SAME report (one row is a service-and-rate pairing, and the drawing
wants the service), and the second divides two published totals. What is
forbidden is a second SOURCE of a figure, and there is none. A panel that priced
anything, or read a seam directly, would be the defect p38 describes.

════════════════════════════════════════════════════════════════════════════
A PANEL WHOSE REPORT CANNOT BE PRODUCED IS NOT DRAWN AS A PANEL
════════════════════════════════════════════════════════════════════════════
⚠ **hard-won law 2's mirror — a live screen behind a dead control.** Twenty-five
of the catalogue's forty-six definitions refuse today, each by name, and a panel
pointing at one of those would be a card with a link that opens onto a reason.
So every panel asks `queries.definition_refusal()` — **the same function the
catalogue card asks** — before it is built, and a refused panel carries
`available: false` with the reason code beside it and **no link**. One function,
three call sites (the card, the viewer and this), because two derivations of one
fact is how they came to disagree.

⚠ **AND A PANEL WHOSE REPORT IS PRODUCIBLE BUT WHOSE *SHAPE* IS NOT PUBLISHED
IS THE SAME REFUSAL FOR A DIFFERENT REASON, AND `Biggest movers` IS ONE.**
p37 ⑧ wants *top 3 by change, one service at a time*. `usage_and_ranking` is
producible and serves READ rows; nothing in this product publishes a per-account
usage comparison between two periods. Computing one here is precisely the
forbidden arithmetic, so the panel states the absence with its reason. Its LINK
stays live, because the report itself opens and is real — what is missing is the
ranking, not the report.

════════════════════════════════════════════════════════════════════════════
`P4.13` — THE PERIOD CROSSES INTO THE REPORT, OR THE PANEL IS WORSE THAN A LINK
════════════════════════════════════════════════════════════════════════════
p38 ⓸, verbatim: *"opening a panel opens that report **already set to this
period**. A dashboard that drops you into a report on a different window is
worse than one with no links, because the numbers change under you and nothing
says why."* Every panel therefore carries `report_params` — the `f.from` /
`f.to` pair the viewer reads — built from the SELECTED period and never from the
tenant's today.

════════════════════════════════════════════════════════════════════════════
ONE REPORT IS RUN ONCE PER WINDOW, AND THE CACHE IS NOT AN OPTIMISATION
════════════════════════════════════════════════════════════════════════════
The four KPIs, their four comparisons and the five panels between them name the
same report over the same window repeatedly — Revenue Analysis over the selected
period is the `billed` tile, the `Service mix` panel and the newest bar of
`Revenue, 12 months`. `_Runs` memoises by `(key, window)` so each is executed
once. ⚠ **That is correctness before it is speed:** two executions of one report
over one window are two chances for the screen to show two numbers for one fact,
which is the failure this whole file is arranged to make impossible.

⚠ **THE COST IS STATED RATHER THAN GLOSSED.** A first load of this screen runs
**at most 16 reports**: 12 revenue windows for the bars (one of which is the
selected period, already counted), the comparison's revenue window, two
payments windows, two ageing dates and one close pack. A web worker is given
sixty seconds (`docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`). This has NOT
been measured on PostgreSQL at 40,000 accounts by this lane and is REPORTED:
`DEF-REP-6935`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from . import catalog
from . import dashboard_tab_period as period_vocabulary
from . import queries
from . import report_seams as seams
from . import runner as reports_runner

#: The four KPI tiles, in the drawing's order (p36 region ④, p37 ④):
#: **billed · collected · outstanding · days to collect**.
#:
#: ⚠ **FOUR, NOT FIVE — p37 ④ says so in its own heading.** The shell dashboard
#: has five and they are different tiles; a fifth here would be the merge p36
#: rules out.
KPI_BILLED = "billed"
KPI_COLLECTED = "collected"
KPI_OUTSTANDING = "outstanding"
KPI_DAYS_TO_COLLECT = "days_to_collect"
KPI_ORDER = (KPI_BILLED, KPI_COLLECTED, KPI_OUTSTANDING, KPI_DAYS_TO_COLLECT)

#: The five panels, in the drawing's order (p36 regions ⑤–⑨).
PANEL_REVENUE_12 = "revenue_12_months"
PANEL_WHERE_MONEY_SITS = "where_the_money_sits"
PANEL_SERVICE_MIX = "service_mix"
PANEL_BIGGEST_MOVERS = "biggest_movers"
PANEL_MONTH_CLOSED = "month_closed"

#: How many bars `Revenue, 12 months` draws. p37 ⑤: *"bars, current period
#: accented"*.
REVENUE_BARS = 12

#: The five signed ageing bands, in the order `ar_aging` publishes them. Spelled
#: from the report's own `totals` keys so a band cannot be renamed here and
#: silently disagree with the report behind the panel.
AGEING_BANDS = (
    ("current", "current"),
    ("1-30", "d1_30"),
    ("31-60", "d31_60"),
    ("61-90", "d61_90"),
    ("90+", "d90_plus"),
)

#: The report ran, was not refused, and published no figure for this window.
#: Distinct from `report_cannot_be_produced` (this deployment cannot serve the
#: report at all) and from `report_did_not_answer` (it broke): those two are
#: facts about the software and this is a fact about the period.
REASON_NO_FIGURE_PUBLISHED = "no_figure_published_for_this_period"

#: Why the `days to collect` tile has no figure. p37 ④: *"A tile whose owner
#: publishes no count reads Not counted yet with its reason."*
#:
#: ⚠ **THE TILE IS DRAWN AND NOT DROPPED, WHICH IS THE RULE THE SHELL DASHBOARD
#: ALREADY OBEYS (BR-REP-024).** Days-sales-outstanding is a ratio of the
#: receivable to a period's billing, and NO definition in the catalogue
#: publishes it. Computing it here would be the one thing p38 forbids, and
#: dropping the tile would leave the drawing's four-tile band silently three.
GAP_DAYS_TO_COLLECT = {
    "code": "days_to_collect_is_not_published",
    "br_ref": "BR-REP-024 · CR-142-BRC07 P4.11",
    "detail": (
        "Days to collect is not published by any report in the catalogue. This tile shows "
        "the figure its owner publishes and computes nothing of its own; when a definition "
        "publishes a collection-days measure, the tile fills with it."
    ),
    "wanted_reads": ("a collection-days measure on a catalogue definition",),
}

#: Why `Biggest movers` shows no rows. See the file docstring.
GAP_MOVERS = {
    "code": "usage_movers_are_not_published",
    "br_ref": "BR-REP-024 · CR-142-BRC07 P4.11",
    "detail": (
        "A ranking of the accounts whose usage moved most between two periods is not "
        "published by any report. Usage & Ranking serves the reads themselves; the "
        "comparison between periods is not among the figures it publishes, and this panel "
        "renders a published figure rather than deriving one."
    ),
    "wanted_reads": ("a period-over-period usage comparison per account",),
}


def _decimal(value: Any) -> Decimal | None:
    """A decimal STRING off a report payload, back as a Decimal, or None.

    The reports serve money as exact decimal strings (`queries._money`) and this
    file compares and sums them. Never a float: hard rule 2 forbids a binary
    fraction anywhere near money, and `Decimal(str)` is exact.
    """
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):  # pragma: no cover — defensive
        return None


def _money(value: Decimal | None) -> str | None:
    """A Decimal back to its EXACT decimal string. Rounds NOTHING (hard rule 2):
    money is stored to 4 and DISPLAYED to 2, and display is the screen's job."""
    return None if value is None else f"{value:f}"


class _Runs:
    """Every report this screen needs, each executed at most once per window.

    ⚠ **A REPORT THAT RAISES IS CAUGHT AND BECOMES A REFUSAL, NEVER A 500.**
    This screen is an index of five panels; one unavailable report must cost its
    own panel and nothing else. The exception's own reason travels with it so
    the panel can say which of the two things happened — the report refused
    (`DatasetCannotServe`, a fact about this deployment) or the report broke.
    """

    def __init__(self, run: Callable[[str, dict[str, Any]], dict[str, Any]]):
        self._run = run
        self._cache: dict[tuple[str, tuple[tuple[str, str], ...]], Any] = {}

    def get(self, key: str, params: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        """`(payload, reason_code)`. Exactly one of the two is None."""
        signature = (key, tuple(sorted((k, str(v)) for k, v in params.items())))
        if signature not in self._cache:
            try:
                self._cache[signature] = (self._run(key, params), None)
            except queries.DatasetCannotServe:
                self._cache[signature] = (None, "report_cannot_be_produced")
            except Exception:  # noqa: BLE001 — see the docstring
                self._cache[signature] = (None, "report_did_not_answer")
        return self._cache[signature]


def _seam_value(seam: Callable[[], Any]) -> Any:
    """A neighbouring module's published read, or `None` if it cannot answer.

    ⚠ **AN OWNER THAT CANNOT ANSWER IS AN ABSENCE, NEVER A 500 ON THIS SCREEN**
    (BR-REP-024, and `dashboard_seams.py`'s whole argument). These two seams
    decide the service ORDER and the CURRENCY — presentation, not a figure — so
    a screen that lost five panels because the tenancy module was unreachable
    would be trading a cosmetic gap for a blank page.
    """
    try:
        return seam()
    except Exception:  # noqa: BLE001 — see the docstring
        return None


def _window_params(window: dict[str, Any]) -> dict[str, Any]:
    """The `from`/`to` pair a viewer reads. `queries._window` takes bare names."""
    return {"from": window["start"].isoformat(), "to": window["end"].isoformat()}


def _report_params(window: dict[str, Any], *, as_at: bool = False) -> dict[str, str]:
    """`P4.13` — the period, in the URL grammar the VIEWER reads (`f.<name>`).

    Served rather than composed by the client so the period a panel hands over
    and the period a panel was computed over are one value — p38 ⓸: *"opening a
    panel opens that report already set to this period"*.

    ⚠ **AN AS-AT REPORT GETS `f.as_of` AND A FLOW REPORT GETS `f.from`/`f.to`,
    AND HANDING THE WRONG ONE IS NOT A COSMETIC MISMATCH.** `ar_aging` is a
    POSITION at a date. Given a RANGE, `slicers.footer_across` adds `time` to
    what the footer spans and `additivity.footer` replaces every band total with
    an em-dash — so a panel showing `$48,221.14` would open a report showing
    five dashes, which is precisely the *"numbers change under you and nothing
    says why"* p38 names as worse than having no link at all. Measured on this
    deployment before this argument existed: `ar_aging?f.from=…&f.to=…` refuses
    `total`; `ar_aging?f.as_of=2026-09-30` serves `8372.060000`.
    """
    if as_at:
        return {"f.as_of": window["end"].isoformat()}
    return {"f.from": window["start"].isoformat(), "f.to": window["end"].isoformat()}


def _total(payload: dict[str, Any] | None, name: str) -> Decimal | None:
    if payload is None:
        return None
    return _decimal((payload.get("totals") or {}).get(name))


def _kpi(
    tile_id: str,
    *,
    value: Decimal | None,
    reason_code: str | None,
    comparison: Decimal | None,
    comparison_reason: str | None,
    kind: str = "money",
) -> dict[str, Any]:
    """One tile, with its comparison underneath (p37 ④).

    ⚠ **THE CHANGE IS SERVED AS A PERCENTAGE TO SIX DECIMALS AND DISPLAYED TO
    TWO** (hard rule 2). It is null — never 0 — when either side is absent or
    when the comparison is zero, because a change against nothing is undefined
    rather than infinite, and `+∞%` on a board pack is worse than a blank.
    """
    change = None
    if value is not None and comparison is not None and comparison != Decimal("0"):
        change = f"{((value - comparison) / comparison * 100):.6f}"
    # ⚠ **A REPORT THAT ANSWERED AND PUBLISHED NO FIGURE STILL OWES A REASON**
    # (BR-REP-024 — an absent figure is a null WITH a reason, never a bare
    # blank and never a 0). `payments_by_method` over a period with no
    # payments answers `{"count": 0, "amount": null}`: the report ran, it is
    # not refused, and it published nothing for this window. Measured on this
    # deployment: September 2026 returns exactly that. Without this the tile
    # would render an unexplained gap that reads identically to a broken seam.
    if value is None and reason_code is None:
        reason_code = REASON_NO_FIGURE_PUBLISHED
    if comparison is None and comparison_reason is None:
        comparison_reason = REASON_NO_FIGURE_PUBLISHED
    return {
        "id": tile_id,
        "kind": kind,
        "value": _money(value) if kind == "money" else value,
        "reason_code": reason_code,
        "comparison": {
            "value": _money(comparison) if kind == "money" else comparison,
            "change_pct": change,
            "reason_code": comparison_reason,
        },
    }


def _panel(
    panel_id: str,
    *,
    report_key: str,
    dataset: str | None,
    window: dict[str, Any],
    reason_code: str | None,
    as_at: bool = False,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One panel, with its door.

    ⚠ **THE DOOR IS DECIDED BY THE SAME FUNCTION THE CATALOGUE CARD ASKS.** A
    panel whose report the catalogue would refuse carries no `report_params` at
    all, so a screen cannot render a link by forgetting to check a flag — the
    destination is simply absent from the payload, which is stronger than a
    client remembering not to draw one (BR-REP-033's own mechanism).
    """
    refusal = queries.definition_refusal(report_key, dataset)
    opens = refusal is None
    return {
        "id": panel_id,
        "report_key": report_key,
        "opens": opens,
        # p37 ⑨ and hard-won law 2's mirror: a panel that cannot show figures
        # still says which report it is about; what it does not do is offer a
        # door onto a reason.
        "report_params": _report_params(window, as_at=as_at) if opens else None,
        "reason_code": ("report_cannot_be_produced" if not opens else reason_code),
        **(body or {}),
    }


def _share(amount: Decimal | None, total: Decimal | None) -> str | None:
    """A band's share of the receivable, to ONE decimal.

    ⚠ **NOT FORCED TO 100, AND p37 ⑥ SAYS WHY IN ITS OWN FIGURES**: the drawn
    bands read *58+25+9+4+4*, which is 100 by luck rather than by construction.
    A screen that redistributed a rounding remainder would be showing a share no
    band actually has. None when there is nothing to divide by: a percentage of
    zero is undefined, not 0%.
    """
    if amount is None or total is None or total == Decimal("0"):
        return None
    return f"{(amount / total * 100):.1f}"


def _revenue_bars(runs: _Runs, windows: list[dict[str, Any]], selected_id: str) -> dict[str, Any]:
    """p37 ⑤ — twelve bars, the current period accented.

    A window whose report did not answer contributes a bar with a NULL value and
    its reason, never a zero: a missing month drawn as a floor is a month that
    reads as *we billed nothing*, which is the one lie a revenue chart can tell.
    """
    bars = []
    for window in windows:
        payload, reason = runs.get(catalog.KEY_REVENUE_BY_SERVICE, _window_params(window))
        bars.append(
            {
                "period_id": window["id"],
                "start": window["start"].isoformat(),
                "end": window["end"].isoformat(),
                "value": _money(_total(payload, "total")),
                "reason_code": reason,
                "current": window["id"] == selected_id,
            }
        )
    # Oldest first: the drawing's axis runs *Oct 25 → Mar 26 → Sep 26*.
    bars.reverse()
    return {"bars": bars}


def _service_mix(
    payload: dict[str, Any] | None,
    reason: str | None,
    services_in_seed_order: tuple[str, ...] | list[str] | None,
) -> dict[str, Any]:
    """p37 ⑦ — every enabled service in seed order, plus the named remainder.

    ⚠ **THE ROWS ARE SUMMED BY SERVICE AND NOTHING IS PRICED.** Revenue Analysis
    publishes one row per service-and-rate pairing; the drawing wants the
    service. Adding a report's own published totals at a coarser grain of that
    same report is the regrouping named in the file docstring.

    ⚠ **A ROW WITH NO SERVICE IS THE NAMED REMAINDER AND IS KEPT.** The drawing
    calls it *Not attributable* and draws it at `0.00`. Dropping it would make
    the panel's rows fail to add up to the report's own total, silently.
    """
    if payload is None:
        return {"services": [], "reason_code": reason}
    by_code: dict[str | None, Decimal] = {}
    for row in payload.get("rows") or []:
        code = row.get("service_code") or None
        amount = _decimal(row.get("total")) or Decimal("0")
        by_code[code] = by_code.get(code, Decimal("0")) + amount
    # Seed order (CLAUDE.md: eleven services, `fire` appended at 11), taken from
    # the tenant's own enabled set rather than typed here — the eleventh service
    # failed silently twice by being typed out by hand.
    enabled = list(services_in_seed_order or ())
    ordered = [code for code in enabled if code in by_code]
    ordered += [code for code in by_code if code is not None and code not in enabled]
    services = [{"service_code": code, "value": _money(by_code[code])} for code in ordered]
    if None in by_code:
        # The remainder is LAST and carries a null code; the screen names it.
        services.append({"service_code": None, "value": _money(by_code[None])})
    return {"services": services, "reason_code": reason}


def _ageing_bands(payload: dict[str, Any] | None, reason: str | None) -> dict[str, Any]:
    """p37 ⑥ — the five signed bands with their shares."""
    if payload is None:
        return {"bands": [], "reason_code": reason}
    totals = payload.get("totals") or {}
    whole = _decimal(totals.get("total"))
    bands = []
    for band_id, total_key in AGEING_BANDS:
        amount = _decimal(totals.get(total_key))
        bands.append({"band": band_id, "value": _money(amount), "share_pct": _share(amount, whole)})
    return {"bands": bands, "reason_code": reason}


def _tie_outs(payload: dict[str, Any] | None, reason: str | None) -> dict[str, Any]:
    """p37 ⑨ — the Close Pack tie-outs, *the one panel that can be red*.

    ⚠ **THE VERDICT IS THE REPORT'S OWN FIELD AND IS NOT RE-DERIVED HERE.**
    `close_pack` publishes `result` per row and `release_blocked` over the set
    (BR-LED-007). A panel that decided *red* from a non-zero difference would be
    a second opinion about a release blocker, and `unverifiable` — a check that
    never ran — would come out green.
    """
    if payload is None:
        return {"checks": [], "blocked": None, "reason_code": reason}
    rows = [
        {
            "check": row.get("check"),
            "ours": row.get("value_a"),
            "theirs": row.get("value_b"),
            "difference": row.get("difference"),
            "result": row.get("result"),
        }
        for row in payload.get("rows") or []
    ]
    return {
        "checks": rows,
        "blocked": (payload.get("totals") or {}).get("release_blocked"),
        "reason_code": reason,
    }


def dashboard(
    *,
    as_of: date,
    period: str | None = None,
    compare: str | None = None,
    run: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
    current_period: Callable[[date], dict[str, Any] | None] | None = None,
    enabled_services: Callable[[], tuple[str, ...] | None] | None = None,
    regional: Callable[[], dict[str, Any] | None] | None = None,
) -> dict[str, Any]:
    """Screen `3·1`'s whole payload. Writes NOTHING (p36 ④, p38 ⓸).

    *"Nothing. No write of any kind, not even a remembered period."* There is no
    preference, no cookie and no row: the period rides in the URL, which is what
    makes a link pasted into a board pack open on the same month.

    `run` and `current_period` are injected so the assembly can be tested
    against signed figures without a database, and default to the real ones.
    """
    runner = _Runs(run or _default_run)
    seam_period = current_period or _default_current_period
    # ⚠ **ALL FOUR SEAMS ARE INJECTED, AND THE LAST TWO WERE ADDED BECAUSE THE
    # TESTS PROVED THEY HAD TO BE.** This module's whole promise is that it
    # holds no clock and reaches no database of its own, so the assembly can be
    # asserted against signed figures. Two calls broke that promise by going
    # straight to `report_seams` — `enabled_service_codes()` for the service
    # ORDER and `regional_settings()` for the currency — and both raise
    # `AuthError AUTH-003` outside a tenant context. Every case that built a
    # panel failed on it, in a traceback that named the SEAM and not the
    # missing fixture. Injected, they are four arguments with real defaults.
    seam_services = enabled_services or seams.enabled_service_codes
    seam_regional = regional or seams.regional_settings

    options, unavailable = period_vocabulary.period_options(as_of=as_of, current_period=seam_period)
    chosen = period_vocabulary.resolve(options, period, current_period=seam_period)
    comparison = period_vocabulary.resolve_comparison(compare)

    if chosen is None:
        # No fiscal calendar: there is no window, so there is nothing true to
        # put in a tile. Stated once, at the top, rather than repeated as a
        # reason on nine surfaces (B14 rule 32 — one stated absence).
        return {
            "period": None,
            "periods": [],
            "comparison": comparison,
            "comparisons": period_vocabulary.comparison_options(),
            "comparison_period": None,
            "currency": (_seam_value(seam_regional) or {}).get("currency"),
            "kpis": [],
            "panels": [],
            "unavailable": unavailable,
        }

    against = period_vocabulary.comparison_window(chosen, comparison, current_period=seam_period)
    # A comparison window that does not exist is an ABSENCE, not an error: a
    # tenant in its first period has no previous one.
    comparison_missing = None if against is not None else "comparison_period_does_not_exist"

    def _revenue(window: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
        if window is None:
            return None, comparison_missing
        return runner.get(catalog.KEY_REVENUE_BY_SERVICE, _window_params(window))

    def _cash(window: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
        if window is None:
            return None, comparison_missing
        return runner.get(catalog.KEY_PAYMENTS_BY_METHOD, _window_params(window))

    def _ageing(window: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
        if window is None:
            return None, comparison_missing
        # ⚠ **`as_of`, AND NEVER `from`/`to` — AND THIS IS NOT A TIDINESS
        # PREFERENCE, IT DECIDES WHETHER THE PANEL SHOWS FIGURES AT ALL.** A
        # receivable is a POSITION at a date, not a flow over a window, so
        # `datasets.PAYMENTS` declares every ageing band SEMI-ADDITIVE and
        # `slicers.footer_across` adds `time` to the footer's span for any
        # report given a RANGE. `additivity.footer` then replaces every band
        # total with an em-dash and `balance_does_not_sum_across_time`.
        #
        # Measured on this deployment's PostgreSQL before this line was
        # written: `ar_aging` over `from=2026-09-01&to=2026-09-30` returns
        # `current`, `d1_30`, `d31_60`, `d61_90`, `d90_plus` and `total` ALL
        # refused; the same report at `as_of=2026-09-30` returns
        # `total = 8372.060000` over 26 accounts. A first draft of this file
        # passed the window and would have shipped an Outstanding tile and a
        # `Where the money sits` panel that were five em-dashes and a reason,
        # on every tenant, for ever — with `tsc` and every test green, because
        # the refusal IS a valid payload.
        #
        # The position that belongs to a period is the one at its END, which is
        # also what makes the comparison meaningful: last period's receivable is
        # the receivable on last period's closing day.
        #
        # ⚠⚠ **AND THAT LAST SENTENCE IS NOT TRUE OF THIS DEPLOYMENT TODAY —
        # `DEF-PAY-6940`, FOUND BY THIS SCREEN AND NOT FIXED HERE.** `ar_aging`
        # takes `as_of` and uses it to decide which BAND each open bill falls
        # in, but the SET of bills it ages is whatever is outstanding NOW. So a
        # date a year earlier ages the same population. Measured on real
        # PostgreSQL at `2026-09-30`, `2025-09-30` and `2024-01-31`: `current 0
        # · 1-30 0 · 31-60 7678.460000 · 61-90 693.600000 · 90+ 0 · total
        # 8372.060000 · 26 accounts` — **identical, all three**.
        #
        # **The visible consequence is on this screen:** the `Outstanding` tile
        # reads *0.00% against the comparison* and will do so for ever, on every
        # tenant. That is a live comparison over a figure that cannot move —
        # hard-won law 2's mirror, one module out.
        #
        # ⚠ **IT IS REPORTED AND NOT PAPERED OVER.** Suppressing the comparison
        # here would hide another module's defect behind this screen's copy, and
        # the tile would then be silently different from the other three for a
        # reason no reader could find. This screen renders what the owner
        # publishes; the owner is `apps/payments/reporting.ar_aging` and the row
        # is `DEF-PAY-6940`.
        return runner.get(catalog.KEY_AR_AGING, {"as_of": window["end"].isoformat()})

    revenue, revenue_reason = _revenue(chosen)
    revenue_before, revenue_before_reason = _revenue(against)
    cash, cash_reason = _cash(chosen)
    cash_before, cash_before_reason = _cash(against)
    ageing, ageing_reason = _ageing(chosen)
    ageing_before, ageing_before_reason = _ageing(against)
    pack, pack_reason = runner.get(catalog.KEY_CLOSE_PACK, _window_params(chosen))

    kpis = [
        _kpi(
            KPI_BILLED,
            value=_total(revenue, "total"),
            reason_code=revenue_reason,
            comparison=_total(revenue_before, "total"),
            comparison_reason=revenue_before_reason,
        ),
        _kpi(
            KPI_COLLECTED,
            value=_total(cash, "amount"),
            reason_code=cash_reason,
            comparison=_total(cash_before, "amount"),
            comparison_reason=cash_before_reason,
        ),
        _kpi(
            KPI_OUTSTANDING,
            value=_total(ageing, "total"),
            reason_code=ageing_reason,
            comparison=_total(ageing_before, "total"),
            comparison_reason=ageing_before_reason,
        ),
        _kpi(
            KPI_DAYS_TO_COLLECT,
            value=None,
            reason_code=GAP_DAYS_TO_COLLECT["code"],
            comparison=None,
            comparison_reason=GAP_DAYS_TO_COLLECT["code"],
            kind="count",
        ),
    ]

    # The twelve windows the bar chart draws, newest first — the menu already
    # holds exactly this many, walked back period by period by the seam.
    bar_windows = options[:REVENUE_BARS]

    panels = [
        _panel(
            PANEL_REVENUE_12,
            report_key=catalog.KEY_REVENUE_BY_SERVICE,
            dataset="journal_lines",
            window=chosen,
            reason_code=None,
            body=_revenue_bars(runner, bar_windows, chosen["id"]),
        ),
        _panel(
            PANEL_WHERE_MONEY_SITS,
            report_key=catalog.KEY_AR_AGING,
            dataset="payments",
            window=chosen,
            reason_code=ageing_reason,
            as_at=True,
            body=_ageing_bands(ageing, ageing_reason),
        ),
        _panel(
            PANEL_SERVICE_MIX,
            report_key=catalog.KEY_REVENUE_BY_SERVICE,
            dataset="journal_lines",
            window=chosen,
            reason_code=revenue_reason,
            body=_service_mix(revenue, revenue_reason, _seam_value(seam_services)),
        ),
        _panel(
            PANEL_BIGGEST_MOVERS,
            report_key="usage_and_ranking",
            dataset="meter_reads",
            window=chosen,
            # See the file docstring: the REPORT opens, the RANKING is not
            # published, and those are two different sentences.
            reason_code=GAP_MOVERS["code"],
            body={"movers": []},
        ),
        _panel(
            PANEL_MONTH_CLOSED,
            report_key=catalog.KEY_CLOSE_PACK,
            dataset="journal_lines",
            window=chosen,
            reason_code=pack_reason,
            body=_tie_outs(pack, pack_reason),
        ),
    ]

    unavailable = list(unavailable) + [dict(GAP_DAYS_TO_COLLECT), dict(GAP_MOVERS)]

    return {
        "period": {
            "id": chosen["id"],
            "start": chosen["start"].isoformat(),
            "end": chosen["end"].isoformat(),
            "fy_label": chosen.get("fy_label"),
            "period_no": chosen.get("period_no"),
        },
        "periods": [
            {
                "id": option["id"],
                "start": option["start"].isoformat(),
                "end": option["end"].isoformat(),
            }
            for option in options
        ],
        "comparison": comparison,
        "comparisons": period_vocabulary.comparison_options(),
        "comparison_period": (
            None
            if against is None
            else {
                "id": against["id"],
                "start": against["start"].isoformat(),
                "end": against["end"].isoformat(),
            }
        ),
        # BR-REP-001 — the basis the figures are struck on, from the reports
        # themselves rather than asserted here.
        "basis": (revenue or {}).get("basis"),
        "currency": (revenue or ageing or cash or {}).get("currency")
        or (_seam_value(seam_regional) or {}).get("currency"),
        "kpis": kpis,
        "panels": panels,
        "unavailable": unavailable,
    }


def _default_run(key: str, params: dict[str, Any]) -> dict[str, Any]:
    """One catalogue report, through the SAME dispatch `GET /reports/{key}` uses.

    ⚠ **`runner.run` AND NOT `queries.VIEWERS[key]`, WHICH AN EARLIER DRAFT DID.**
    `VIEWERS` holds ELEVEN per-report viewers of the forty-six definitions, and
    `runner.queries_for` falls back to the DATASET's query for the rest — which
    is what turns a dataset landing into every definition built upon it. Reading
    the dict directly would `KeyError` on any panel later pointed at one of the
    other thirty-five, and it would bypass `runner`'s binding, grouping and
    `additivity.footer` — so this screen and the report behind it could disagree
    about the same figure, which is the one thing p38 forbids.
    """
    return reports_runner.run(key, params).payload


def _default_current_period(reference: date) -> dict[str, Any] | None:
    return seams.current_period(reference_date=reference)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P4.11 · P4.13 (05-prototype/09 Reports Build Brief.pdf pp36-38, read as IMAGES per B14 rule 42) · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-001/024/033 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-007
# screens: 3·1
# generated: 2026-09-27 by lane REP-P4-DASH
# checklist: A✔ B=n/a(the screen is its own file) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case in tests/test_rep_p4_dashboard_tab.py failed before this module existed (ModuleNotFoundError: apps.reports.dashboard_tab).
# exceptions: (1) `Biggest movers` publishes NO rows: a period-over-period usage ranking is not published by any definition and deriving one here is the arithmetic p38 forbids. The panel states the absence and its LINK stays live, because the report itself opens. REPORTED · (2) `days to collect` is a tile with no figure and its reason, for the same cause — BR-REP-024's rule rather than a gap in this lane · (3) two regroupings ARE performed (per-service sums, band shares) and both are named in the docstring: they are a coarser grain of one report's own published totals, never a second source · (4) the 16-report worst case has NOT been measured on PostgreSQL at 40,000 accounts against the 60s worker timeout — DEF-REP-6935
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
