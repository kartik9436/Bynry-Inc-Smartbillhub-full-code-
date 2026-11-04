# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — usage pricing) · EP-RAT-02
#           (US-RAT-006 configures the windows this prices)
#           Screens: — (the per-window lines render in S31.2 and on the bill;
#           the windows are configured on S11 step 2's Time-of-use card)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-021 (TOU v1 = Option B: <=3 windows, 2 seasons with their own
#           prices, weekday/weekend/holiday day-types, holidays bill off-peak,
#           READS ARRIVE PRE-SPLIT PER WINDOW) · BR-RAT-033 (the config
#           validation that guarantees one price per hour) · BR-RAT-003 (a
#           plugin never rounds) · BR-RAT-038 (UoM gate) · BR-RAT-044 (one
#           price(...) interface)
# Golden:   GT-17 (= WE-1, the reference bill, machine-verified by
#           10-scripts/03-golden-verify.py) — B5 ❄️ FROZEN 2026-08-08:
#           120 kWh x 0.22 + 200 x 0.14 + 380 x 0.09 = 26.40 + 28.00 + 34.20
#           = 88.60, the 4100 electric-usage posting of that bill.
#           Also GT-22 (WE-6), GT-27 (WE-11), GT-28 (WE-12) — same arithmetic.
# Tests:    06-backend/tests/test_us_rat_012_tou.py
# Impacts:  apps/rating/pricing/stages/price_usage.py (resolves this by name)
# ───────────────────────────────────────────────────────
"""`time_of_use` pricing model: one line per window, quantity x window price.

HUMAN-OWNED · HUMAN-REVIEW-PENDING (amended 2026-10-01 — the BR-RAT-034 season
split; row "OQ-234 BUILT" in the human-review ledger) — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

Serves US-RAT-012 TC-5 and US-RAT-015 TC-1. Before 2026-08-16 no plugin was
registered for this model, so a utility on time-of-use rates — which is what the
demo tenant's own Residential Standard plan uses for electricity — could not
produce an electric bill at all. The run refused, correctly and loudly, at
`registry.resolve("time_of_use")`.

THE FROZEN FIGURE THIS REPRODUCES
---------------------------------
B5 GT-17 is WE-1, the reference bill, and its electric usage is a TOU bill:
120 kWh on-peak, 200 mid-peak, 380 off-peak at the Residential Standard summer
prices $0.22 / $0.14 / $0.09.

    120 x 0.22 = 26.40
    200 x 0.14 = 28.00
    380 x 0.09 = 34.20
                 -----
                 88.60   <- the 4100 posting in GT-17's own journal

That total is inside the frozen taxable base of 221.90 and is recomputed from
raw inputs by `10-scripts/03-golden-verify.py`, which is why this plugin has a
signed number to be wrong against rather than a rule with no example.

WHAT THIS PLUGIN DOES NOT DO, AND WHY EACH IS A BOUNDARY RATHER THAN A GAP
--------------------------------------------------------------------------
* **It does not split a total across windows.** BR-RAT-021 is explicit that
  reads arrive PRE-SPLIT; metering measures a register per window (`channel` =
  tou_on | tou_mid | tou_off, B2 r8 / BR-MET-059). A window with no measurement
  is a REFUSAL naming that window (`errors.MissingWindowQuantity`) — because
  "used nothing on-peak" and "nobody read the on-peak register" are different
  facts and only one of them is worth $0.00.
* **It does not work out which window reads which register, and as of
  2026-08-16 neither does anything else.** The utility states it on S11 and it
  is stored on the window row (`time_of_use_windows.channel`, BR-RAT-067; PO
  verbatim: *"make the rate wizard say which register is which"*, OQ-236
  CLOSED). This plugin was written against a `channel` that rating RESOLVED BY
  PRICE RANK (BR-RAT-064, now superseded and deleted); the field it consumes is
  unchanged, and what changed is that a human answers it. The refusal in
  `_priced_windows` therefore now means *nobody said*, where it used to mean
  *the prices did not rank* — a better sentence for a clerk and the same
  arithmetic for a bill.
* **It does not decide which hour belongs to which window**, does not read a
  clock and does not consult the holiday calendar. Those decide WHICH REGISTER a
  kWh landed in, upstream. Implementing them here would be a second, disagreeing
  copy of a split that has already happened.
* **It does not prorate.** A per-unit price times a metered quantity is already
  proportional to the days that produced it — the same reasoning `flat.py`
  states. B4.3 prorates the BASE charge and scales TIER thresholds; neither is
  in play here, and B5 freezes no prorated-TOU figure.
* **It does not COUNT the days of a season-crossing period — and since
  2026-10-01 it DOES split one.** ⚠ This bullet read *"It does not span two
  seasons … The caller resolves ONE season for the period … Raised as
  **OQ-234**"* until 2026-10-01. `OQ-234` was CLOSED by the PO on 2026-09-07
  (*"please split  swithch it on"*) and the split was not built for three
  weeks, so every season-crossing TOU bill went on pricing at one season's
  rates. It is built now: the CALLER counts the calendar days in each season
  (`rating.selectors._season_days_between`, beside the one-season lookup it
  extends) and hands them across as `ModelConfig.season_days`; this plugin
  only divides each register pro-rata (`season_split`) and prices each share
  at its own season. WE-18 / GT-34 is engine-verified at usage **$82.72**,
  total **$103.67** (`tests/golden/test_gt34_season_crossing_period.py`). A
  period inside one season is unchanged.
* **It does not resolve day-types.** Option B allows different prices for
  weekday / weekend / holiday, but a monthly on-peak REGISTER carries one
  number for the whole month — there is no weekday-only on-peak quantity to
  price at a weekday-only rate. Where the configured prices for a window agree
  across day-types (which is every configuration in the signed corpus, including
  the demo tenant's) this is invisible; where they DISAGREE the plugin refuses
  rather than silently choosing one. Raised as **OQ-233**.
"""

from __future__ import annotations


from dataclasses import replace

from apps.rating.pricing import errors, season_split
from core.units import same_unit
from apps.rating.pricing.contracts import (
    KIND_USAGE,
    LineCandidate,
    MeasuredUsage,
    ModelConfig,
    SubscriptionContext,
    TouWindowSpec,
    WindowUsage,
)

MODEL = "time_of_use"


def _windows_in_force(config: ModelConfig, service: str) -> tuple[TouWindowSpec, ...]:
    """The window prices that apply to the season the caller resolved.

    A window row with no season belongs to a schedule that defines none, and
    applies always. When the caller states a season, only that season's rows (and
    the season-less ones) are eligible — a summer bill must never reach a winter
    price, which is the whole content of BR-RAT-021's "per-season prices".
    """
    if not config.windows:
        raise errors.TariffConfigError(
            f"time-of-use tariff for service {service!r} defines no windows "
            "(BR-RAT-021/033). A TOU schedule with no priced window cannot price a "
            "kWh; that is a refusal, never a zero-dollar bill."
        )
    if config.season is None:
        eligible = tuple(window for window in config.windows if window.season is None)
        if not eligible:
            # Every window is seasonal and the caller resolved no season. Picking
            # one would price a July bill at whichever season happened to sort
            # first — a plausible bill at the wrong price.
            raise errors.TariffConfigError(
                f"service {service!r}: every time-of-use window is scoped to a season "
                f"({', '.join(sorted({w.season or '' for w in config.windows}))}) and no "
                "season was resolved for this period. BR-RAT-021 prices per season; the "
                "season is resolved on the service date by the caller, exactly as the "
                "tariff version is (BR-RAT-007). Refused rather than priced at an "
                "arbitrary season's rates."
            )
        return eligible
    eligible = tuple(window for window in config.windows if window.season in (None, config.season))
    if not eligible:
        raise errors.TariffConfigError(
            f"service {service!r}: no time-of-use window is priced for season "
            f"{config.season!r}; the tariff prices "
            f"{', '.join(sorted({w.season or '(no season)' for w in config.windows}))}. "
            "BR-RAT-033 requires the seasons to cover the year without a gap — this "
            "period fell in the gap, and a gap is a refusal, not a free month."
        )
    return eligible


def _priced_windows(windows: tuple[TouWindowSpec, ...], service: str) -> dict[str, TouWindowSpec]:
    """metering channel -> the ONE window spec priced on it.

    THREE REFUSALS LIVE HERE, and none of them is a preference.

    **A window whose register the utility never stated (BR-RAT-067).** PO ruling
    2026-08-16, verbatim: *"make the rate wizard say which register is which"*
    (OQ-236 CLOSED). The mapping is a stored column the utility fills in on S11,
    and `selectors.pricing_inputs` READS it — nothing infers it any more. A
    window configured before that column existed arrives with `channel=None`,
    and this refuses BY NAME. It does not fall back to the old price-rank match
    (that code is deleted) and it does not price the window at 0.00: **a window
    priced at $0.00 is a charge the bill forgives every month until somebody
    notices.**

    **Two windows on one register (BR-RAT-067 clause 2).** The write path
    already rejects this per season, so reaching it means the rows predate the
    rule or were written outside the service. Keeping one and dropping the other
    would bill that register once and lose the second window's money with no
    mark on the bill, so it refuses.

    **Day-types that disagree (OQ-233).** Option B lets a tenant price on-peak
    differently on a weekday and a weekend (B2 r5 #17 `day_type`). A monthly
    on-peak REGISTER holds one number, so there is no weekend-only quantity to
    apply a weekend-only price to. Where the day-types agree the question never
    arises — which is every configuration in the signed corpus, including the
    demo tenant's. Where they disagree, this says so instead of choosing.
    """
    priced: dict[str, TouWindowSpec] = {}
    for window in windows:
        if not window.channel:
            raise errors.TariffConfigError(
                f"service {service!r}: time-of-use window {window.label!r} does not say "
                "which meter register it is measured on, so nothing can price it. A "
                "window is a LABEL this utility typed and a measurement is a REGISTER "
                "(tou_on | tou_mid | tou_off, B2 r8) — the utility states the pairing on "
                "the rate schedule's Time-of-use card (S11), and this schedule was "
                "configured before that field existed (BR-RAT-067, PO ruling 2026-08-16 "
                "closing OQ-236). Open the schedule and say which register "
                f"{window.label!r} reads. Refused rather than guessing from the prices: "
                "on the reference bill the right pairing is 88.60 and the wrong one is "
                "122.40, and neither document looks unusual."
            )
        seen = priced.get(window.channel)
        if seen is None:
            priced[window.channel] = window
        elif seen.label != window.label:
            raise errors.TariffConfigError(
                f"service {service!r}: windows {seen.label!r} and {window.label!r} both "
                f"read register {window.channel}, and one register holds ONE number for "
                "the period. Pricing it once would silently drop the other window's "
                "money; splitting it would invent a quantity nobody measured. Give each "
                "window its own register on the rate schedule (S11) — BR-RAT-067."
            )
        elif seen.unit_price != window.unit_price:
            raise errors.TariffConfigError(
                f"service {service!r}: window {window.label!r} is priced at "
                f"{seen.unit_price} on day-type {seen.day_type!r} and {window.unit_price} "
                f"on {window.day_type!r}. Metering supplies ONE pre-split quantity per "
                "register for the whole period (BR-RAT-021), so there is no per-day-type "
                "quantity to apply per-day-type prices to. Refused rather than billing "
                "one of the two rates for the whole month — OQ-233."
            )
    return priced


def price(
    subscription: SubscriptionContext,
    usage: MeasuredUsage,
    config: ModelConfig,
) -> tuple[LineCandidate, ...]:
    """One usage line per configured window — per SEASON when the period
    crosses a boundary. UNROUNDED (BR-RAT-003).

    ── BR-RAT-034 · THE SEASON-CROSSING SPLIT (built 2026-10-01) ─────────────
    When the caller hands two or more `season_days` shares, every window's
    pre-split register quantity is divided pro-rata by calendar days
    (`season_split.split_quantity`) and each share is priced at ITS season's
    window price. WE-18 / GT-34: on-peak 120 kWh over 16 summer + 14 winter
    days of 30 is `64 × 0.22 = 14.08` plus `56 × 0.18 = 10.08`, and the whole
    bill's usage is **$82.72** where one season's prices gave on-peak alone
    `120 × 0.18 = $21.60`. Lines come out season by season, chronologically,
    each season in the tariff's own window order, and each names its season and
    its days so the customer can see why one window has two lines.

    **A period inside one season prices EXACTLY as before** — `crossing`
    answers `()` and this is the old body, on the season the caller resolved.
    """
    shares = season_split.crossing(config)
    if not shares:
        return _price_one_season(subscription, usage, config)
    service = subscription.service
    season_split.refuse_uncovered(
        shares,
        service,
        ", ".join(sorted({w.season or "(no season)" for w in config.windows})),
    )
    # 🔒 DEF-RAT-8849 (PO 2026-10-01, *"yes build the season-change day
    # reading"*) — where the caller cut EVERY window at a read on the
    # season-change day, each register's seasons are what it MEASURED (80 / 40)
    # rather than its calendar days (64 / 56). All windows or none: a meter
    # whose on-peak was read on the day and whose off-peak was not is not one
    # reading, and half a bill cut at a read is priced on two different rules.
    measured = (
        usage.season_measured
        if all(
            any(m.channel == window.channel for m in usage.season_measured)
            for window in usage.windows
        )
        else ()
    )
    per_channel = {
        window.channel: season_split.measured_or_split(
            window.quantity, shares, measured, window.channel
        )
        for window in usage.windows
    }
    lines: list[LineCandidate] = []
    for index, share in enumerate(shares):
        season_usage = replace(
            usage,
            windows=tuple(
                WindowUsage(
                    channel=window.channel,
                    quantity=per_channel[window.channel][index],
                    unit=window.unit,
                )
                for window in usage.windows
            ),
        )
        lines.extend(
            _price_one_season(
                subscription,
                season_usage,
                replace(config, season=share.season, season_days=()),
                note=season_split.wording(share, shares),
            )
        )
    return tuple(lines)


def _price_one_season(
    subscription: SubscriptionContext,
    usage: MeasuredUsage,
    config: ModelConfig,
    note: str | None = None,
) -> tuple[LineCandidate, ...]:
    """One usage line per configured window, at ONE season's prices.

    This was `price` itself until 2026-10-01 and its body is unchanged; `note`
    is the only addition — the season wording a SPLIT line carries
    (*"Summer, 16 of 30 days"*), `None` on every unsplit bill so no existing
    line's wording moves.

    Lines come out in the tariff's own window order, so an on/mid/off schedule
    prints on/mid/off — the order the tenant built and the customer reads.
    """
    service = subscription.service
    in_force = _windows_in_force(config, service)
    priced = _priced_windows(in_force, service)
    measured = {window.channel: window for window in usage.windows}

    if not usage.windows:
        raise errors.MissingWindowQuantity(
            f"service {service!r} prices on time of use "
            f"({', '.join(sorted(w.label for w in priced.values()))}) and NO per-window "
            "quantity arrived. BR-RAT-021: reads arrive pre-split per window. Nothing "
            "here divides a total across windows and nothing prices an unmeasured "
            "window as zero — the account is an exception for a human (BR-BIL-015), "
            "not a bill."
        )

    unpriced = sorted(set(measured) - set(priced))
    if unpriced:
        raise errors.TariffConfigError(
            f"service {service!r}: register(s) {', '.join(unpriced)} were measured and the "
            f"tariff prices only {', '.join(sorted(priced))}. Billing the measured "
            "quantity at another window's rate, or dropping it, are both wrong in ways "
            "nobody would see on the bill — so the run refuses."
        )

    lines: list[LineCandidate] = []
    for channel, spec in priced.items():
        window = measured.get(channel)
        if window is None:
            raise errors.MissingWindowQuantity(
                f"service {service!r}: the tariff prices window {spec.label!r} "
                f"(register {channel}) at {spec.unit_price} and nothing measured it. A "
                "window with no read is UNKNOWN, not zero (BR-RAT-021 — reads arrive "
                "pre-split); pricing it at 0.00 would tell the customer their meter was "
                "read and showed nothing."
            )
        if not same_unit(window.unit, config.billed_unit):  # DEF-RAT-10220 — `_gate_uom`'s rule
            raise errors.UomMismatch(
                f"service {service!r}: window {spec.label!r} was measured in "
                f"{window.unit!r} and the tariff bills in {config.billed_unit!r}. "
                "BR-RAT-038 (PO R6): convert at rating input with a defined per-service "
                "factor, or block the read — never convert silently."
            )
        lines.append(
            LineCandidate(
                kind=KIND_USAGE,
                description=(
                    f"{service} usage — {spec.label}"
                    if note is None
                    else f"{service} usage — {spec.label} ({note})"
                ),
                amount=window.quantity * spec.unit_price,
                taxable=True,  # B4.2: usage is in the tax base
                quantity=window.quantity,
                unit=window.unit,
                unit_price=spec.unit_price,
            )
        )
    return tuple(lines)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md)
# generated: 2026-08-16 by the pricing-engines lane (EP-RAT-05 US-RAT-012 TC-5 · EP-RAT-02 US-RAT-006 §7) · AMENDED 2026-08-16 by the register lane (BR-RAT-067: the unresolved-channel refusal now means *nobody said*, names the window and points at S11; a second refusal added for two windows on one register)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half; the CONFIG half is S11's Time-of-use card, already built) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_rat_012_tou.py✔ · pytest -m golden✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔
# exceptions: ONE named boundary. (1) OQ-233 — per-day-type prices cannot be resolved from a monthly per-window register; equal prices across day-types price normally, unequal ones REFUSE. ⚠ (2) WAS "OQ-234 — a period spanning a season boundary … the caller resolves ONE season" until 2026-10-01: OQ-234 was CLOSED 2026-09-07 and the split is BUILT (season_split; GT-34 engine-verified).
# amended: 2026-10-01 by the season-split lane (DEF-RAT-8832) — BR-RAT-034's pro-rata calendar-day split, HUMAN-REVIEW-PENDING
# amended: 2026-10-01 by the season-change-reading lane (DEF-RAT-8849) — a reading on the season-change day replaces the day split (PO "yes build the season-change day reading"); HUMAN-REVIEW-PENDING, review-ledger row "DEF-RAT-8849"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
