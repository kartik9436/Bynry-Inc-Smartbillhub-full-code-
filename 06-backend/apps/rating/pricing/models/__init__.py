# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — the pricing-model registry)
#           Screens: — (pure code)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-044 (a tariff_model is a module + a registry row, never an
#           engine edit; the registry is closed at import) · BR-RAT-019
#           (`capacity` joined the enum after v1 scoping — the precedent)
# Golden:   GT-1 (flat) · GT-2 · GT-5 (tiered) — B5 ❄️ FROZEN 2026-08-08
# Tests:    06-backend/tests/test_us_rat_015_plugins.py
# Impacts:  apps/rating/pricing/stages/price_usage.py · apps/rating/engine.py 🔒
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human sign-off.

Pricing-model plugins, and the registry rows that publish them.

ADDING A RATE SHAPE — the whole procedure, and nothing else changes
------------------------------------------------------------------
1. Write `apps/rating/pricing/models/<name>.py` with one function::

       def price(subscription, usage, config, period=None) -> tuple[LineCandidate, ...]

   It returns UNROUNDED amounts (BR-RAT-003: a plugin never rounds).
2. Add one line to `_register()` below.
3. If the shape needs configuration the seam cannot express yet (TOU windows,
   demand rates, seasons, capacity units, a percent-of-service basis), add those
   fields to `apps.billing.rating_seam.TariffConfig` and project them onto
   `ModelConfig` in `stages/normalize.py`. That is a CONTRACT change and is
   reviewed as one.

No stage is edited, no `if model == ...` ladder exists to extend, and no
surrounding rule moves — which is the property BR-RAT-019 already demonstrated
once when `capacity` was added to the model enum after v1 scoping.

WHAT IS REGISTERED TODAY, AND WHY NOT MORE
------------------------------------------
`flat` · `tiered` · `time_of_use` · `percent_of_service` · `capacity` · `demand`
· `seasonal` (2026-10-01).

The last four landed on **2026-08-16**, and the note that used to sit here is
worth keeping in view because it was true when it was written and stopped being
true: it said their configuration *"cannot travel on the seam's TariffConfig
today, and B5 freezes no figure for any of them"*, and concluded that
registering them would be dead code claiming a capability. Both halves were then
fixed rather than argued with:

* **The configuration now travels.** `TariffConfig` carries windows, a resolved
  season, a capacity unit+rate, the two demand rates and the percent+basis;
  `stages/normalize.py` projects them onto `ModelConfig`. That was a CONTRACT
  change and is reviewed as one (step 3 below).
* **The frozen figures were there all along, in the GT-17..61 range.** B5's own
  allocation table maps the billing workbook onto GT numbers, and the reference
  bill GT-17 (= WE-1) is a TOU + %-of-water + capacity bill whose electric
  usage $88.60, sewer $15.80 and solar $40.00 are all inside its
  machine-verified taxable base of $221.90. Demand is GT-20/GT-21
  ($134.90 · $4,097.00 + $2,002.00); capacity proration is GT-31 ($12.90),
  check #21 of the frozen harness. The earlier note looked only at GT-1..16.

`seasonal` IS REGISTERED AS OF 2026-10-01 — the seventh shape. ⚠ This paragraph
read *"`seasonal` is still NOT registered … neither the day weights nor a
machine-verified figure for it exist on this contract. It stays a module-shaped
hole and refuses loudly"* until that date, and it had been false as a reason
since **2026-09-07**, when the PO closed `OQ-234` in the words *"please split
swithch it on"* (decision log, *"TWO RULINGS IN ONE BREATH"*). Nothing built it
for three weeks, so a Seasonal schedule saved and read *In force* and every bill
on it was refused (`DEF-RAT-8832`). Both missing halves now exist: the day
weights are counted by the CALLER (`rating.selectors._season_days_between`) and
travel as `ModelConfig.season_days`, and WE-18 is engine-verified as GT-34
(`tests/golden/test_gt34_season_crossing_period.py`). `models/seasonal.py`
prices each season on its own ladder and splits a season-crossing period pro-rata
by calendar days (`season_split`), and `time_of_use` splits the same way.

THE PROPERTY THAT MADE THIS A FILE-SHAPED CHANGE
------------------------------------------------
Four rate shapes were added and `stages/price_usage.py` was not touched. It
still names no model; US-RAT-015 TC-4 greps it for exactly that, so a lane that
reached for an `if model == ...` ladder would fail a test rather than merely
offend a convention.
"""

from apps.rating.pricing import registry
from apps.rating.pricing.models import (
    capacity,
    demand,
    flat,
    percent_of_service,
    seasonal,
    tiered,
    tou,
)


def _register() -> None:
    """Import-time registration. Called once, by the package __init__."""
    registry.PRICING_MODELS.register(flat.MODEL, flat.price)
    registry.PRICING_MODELS.register(tiered.MODEL, tiered.price)
    registry.PRICING_MODELS.register(tou.MODEL, tou.price)
    registry.PRICING_MODELS.register(percent_of_service.MODEL, percent_of_service.price)
    registry.PRICING_MODELS.register(capacity.MODEL, capacity.price)
    registry.PRICING_MODELS.register(demand.MODEL, demand.price)
    # OQ-234 CLOSED 2026-09-07 ("please split  swithch it on") — built 2026-10-01.
    registry.PRICING_MODELS.register(seasonal.MODEL, seasonal.price)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-015@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05) · AMENDED 2026-08-16 by the pricing-engines lane: `time_of_use`, `percent_of_service`, `capacity` and `demand` REGISTERED — four rate shapes a utility could configure on S11 and the engine could not price
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔
# exceptions: ⚠ READ "`seasonal` remains UNREGISTERED and refuses loudly …" UNTIL 2026-10-01 — OQ-234 was CLOSED 2026-09-07 and `seasonal` is now REGISTERED (DEF-RAT-8832), with the caller-counted calendar-day split (BR-RAT-034) and GT-34 engine-verified. No module-shaped hole remains in the model enum.
# amended: 2026-10-01 by the season-split lane — `seasonal` registered, HUMAN-REVIEW-PENDING
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
