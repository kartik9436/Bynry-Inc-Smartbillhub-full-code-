# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — usage pricing) · EP-RAT-02
#           (US-RAT-007 configures the seasons this prices)
#           Screens: — (the lines render in S31.2 and on the bill; the seasons
#           are configured on the rate schedule wizard, Structure = Seasonal)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-034 (CONFIRMED, PO R5-7: rate_seasons cover the year, each
#           season its own price set, season boundaries split the bill period
#           pro-rata by calendar days) · BR-RAT-002 (tier thresholds scale with
#           the period) · BR-RAT-003 (a plugin never rounds) · BR-RAT-044 (one
#           price(...) interface)
# Golden:   GT-34 (= WE-18) is the split's frozen figure (on the TOU shape);
#           this plugin applies the same split to a seasonal ladder.
# Tests:    06-backend/tests/test_oq234_season_split.py
# Impacts:  apps/rating/pricing/models/__init__.py (registers it)
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human sign-off.

`seasonal` pricing model: each season prices on ITS OWN ladder.

WHY IT EXISTS NOW (DEF-RAT-8832, 2026-10-01)
--------------------------------------------
The rate schedule wizard has offered Structure = Seasonal since RAT-03, a
seasonal schedule saved and read *In force*, and **every bill on it was
refused** — *"No tariff model plugin registered for seasonal"*, 11 of 11
services walked. The model was left unregistered ON PURPOSE while `OQ-234`
stood, because pricing a whole period at one season's rates is a wrong bill
that foots. The PO closed `OQ-234` on 2026-09-07 — *"please split  swithch it
on"* — which registers this model. It went unbuilt for three weeks after that.

WHAT IT DOES
------------
A seasonal schedule stores `rate_seasons` and season-scoped `rate_tiers`
(B2 r5 #2, r6.7): one 0→∞ block for a flat seasonal price, several for an
inclining one. The caller hands over every season's ladder
(`ModelConfig.season_tiers`), the season in force on the service date
(`season`) and — when the period CROSSES a boundary — the calendar days in each
season (`season_days`, counted by `rating.selectors`, never here).

* **Inside one season:** the whole measured quantity prices on that season's
  ladder, exactly as the `tiered` plugin prices a ladder — it IS the tiered
  plugin, handed that season's blocks.
* **Across a boundary (BR-RAT-034):** the quantity divides pro-rata by
  calendar days (`season_split.split_quantity`) and each share prices on its
  own season's ladder.

THE ONE JUDGMENT BEYOND THE RULING — TIER THRESHOLDS ON A SPLIT PERIOD
----------------------------------------------------------------------
A share of a period prices on its season's ladder with that ladder's block
bounds scaled by the share's fraction of the period (`days / Σ days`), on top
of any B4.3 proration factor already in force. That is BR-RAT-002 — *"tier
thresholds … scale with the prorated period"* — applied to each season's part
of the period, which is the only reading under which splitting a period cannot
move a customer into a dearer block: 16 days of a 0–10 kgal block is 0–5.33,
and 16/30 of the water lands in it. The signed corpus has no figure for a
tiered seasonal split (WE-18 is TOU, flat per window), so this is recorded in
the review ledger as a judgment for the PO, not as signed law. A flat seasonal
price (one open block) is unaffected by it.

WHAT IT REFUSES, BY NAME
------------------------
* a schedule with no season ladder at all;
* a season — the resolved one, or one of a split — with no ladder (BR-RAT-033's
  gap: *"a gap is a refusal, not a free month"*);
* any day of a split period no season covers.
"""

from __future__ import annotations

from dataclasses import replace

from apps.rating.pricing import errors, season_split
from apps.rating.pricing.contracts import (
    LineCandidate,
    MeasuredUsage,
    ModelConfig,
    PeriodShape,
    SubscriptionContext,
    TierSpec,
)
from apps.rating.pricing.models import tiered

MODEL = "seasonal"


def _ladders(config: ModelConfig, service: str) -> dict[str, tuple[TierSpec, ...]]:
    ladders = {ladder.season: tuple(ladder.tiers) for ladder in config.season_tiers or ()}
    if not ladders:
        raise errors.TariffConfigError(
            f"seasonal tariff for service {service!r} prices no season (BR-RAT-034: each "
            "season carries its own price set). A seasonal schedule with no season "
            "ladder cannot price a unit; that is a refusal, never a zero-dollar bill."
        )
    return ladders


def _ladder_for(
    ladders: dict[str, tuple[TierSpec, ...]], season: str | None, service: str
) -> tuple[TierSpec, ...]:
    if season is None or season not in ladders or not ladders[season]:
        raise errors.TariffConfigError(
            f"service {service!r}: no seasonal price is defined for "
            f"{'this period' if season is None else f'season {season!r}'}; the tariff "
            f"prices {', '.join(sorted(ladders))}. BR-RAT-033/034 require the seasons to "
            "cover the year without a gap — this period fell in the gap, and a gap is a "
            "refusal, not a free month."
        )
    return ladders[season]


def _scaled(period: PeriodShape | None, fraction) -> PeriodShape:
    """The period shape a SHARE of the period prices on (see the module note)."""
    base = period.factor if period is not None else 1
    cycle = period.cycle_days if period is not None else 0
    service_days = period.service_days if period is not None else 0
    return PeriodShape(cycle_days=cycle, service_days=service_days, factor=base * fraction)


def price(
    subscription: SubscriptionContext,
    usage: MeasuredUsage,
    config: ModelConfig,
    period: PeriodShape | None = None,
) -> tuple[LineCandidate, ...]:
    """Each season on its own ladder; split by calendar days across a boundary.

    UNROUNDED (BR-RAT-003) — every line is `tiered.price`'s own, so a block's
    amount is `quantity × unit price` exactly as on a tiered schedule.
    """
    service = subscription.service
    ladders = _ladders(config, service)
    shares = season_split.crossing(config)
    if not shares:
        ladder = _ladder_for(ladders, config.season, service)
        return tiered.price(
            subscription, usage, replace(config, tiers=ladder, season_tiers=()), period
        )

    season_split.refuse_uncovered(shares, service, ", ".join(sorted(ladders)))
    # 🔒 DEF-RAT-8849 (PO 2026-10-01) — a read on the season-change day hands
    # the measured parts (`channel=None`, the one billed quantity); without one
    # this is the calendar-day split exactly as before.
    quantities = season_split.measured_or_split(
        usage.billed_quantity, shares, usage.season_measured, None
    )
    lines: list[LineCandidate] = []
    for share, quantity in zip(shares, quantities, strict=True):
        ladder = _ladder_for(ladders, share.season, service)
        priced = tiered.price(
            subscription,
            replace(usage, billed_quantity=quantity, raw_quantity=quantity),
            replace(config, tiers=ladder, season=share.season, season_days=(), season_tiers=()),
            _scaled(period, season_split.fraction(share, shares)),
        )
        note = season_split.wording(share, shares)
        lines.extend(replace(line, description=f"{line.description} ({note})") for line in priced)
    return tuple(lines)


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-234 (CLOSED 2026-09-07) · DEF-RAT-8832 · BR-RAT-034 (CONFIRMED, PO R5-7) · BR-RAT-002 · decision log 2026-09-07 + 2026-10-01 "BUILT"
# generated: 2026-10-01 by the season-split lane (DEF-RAT-8832)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half; the wizard already offers Seasonal) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_oq234_season_split.py ✔ · pytest tests/golden ✔
# exceptions: tier THRESHOLDS on a split period scale by each season's day fraction (BR-RAT-002 applied per share) — a lane judgment with no signed figure behind it, recorded in the review ledger for the PO.
# amended: 2026-10-01 by the season-change-reading lane (DEF-RAT-8849) — a reading on the season-change day replaces the day split (PO "yes build the season-change day reading"); HUMAN-REVIEW-PENDING, review-ledger row "DEF-RAT-8849"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
