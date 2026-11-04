# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — usage pricing)
#           Screens: — (pure code; the split lines render in S31.2 and on the bill)
#           No US-ID is cited in this header ON PURPOSE — see errors.py.
# Rules:    BR-RAT-034 (CONFIRMED, PO R5-7: "season boundaries split the bill
#           period pro-rata by calendar days") · BR-RAT-021 (per-season prices) ·
#           BR-RAT-033 (seasons cover the year — a gap is a refusal) ·
#           BR-RAT-003 (a plugin never rounds MONEY)
# Golden:   GT-34 (= WE-18) — 15 Sep – 14 Oct, season flips 1 Oct, 16/30 + 14/30:
#           on-peak 120 kWh → 64 × 0.22 = 14.08 + 56 × 0.18 = 10.08; usage 82.72,
#           total 103.67. tests/golden/test_gt34_season_crossing_period.py
# Tests:    06-backend/tests/test_oq234_season_split.py
# Impacts:  apps/rating/pricing/models/tou.py · apps/rating/pricing/models/seasonal.py
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED (CLAUDE.md 🔒 "rating math (B4)"). HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human sign-off.

The season-crossing split — ARITHMETIC ONLY, over day counts the caller supplied.

WHY THIS FILE EXISTS (built 2026-10-01; ruled 2026-09-07)
---------------------------------------------------------
PO, 2026-09-07, verbatim: *"please split  swithch it on"* — decision log *"TWO
RULINGS IN ONE BREATH: THE SEASON-CROSSING BILL PERIOD IS SPLIT, WHICH CLOSES
OQ-234"*. The rule it switched on had been CONFIRMED since it was written —
BR-RAT-034, *"season boundaries split the bill period pro-rata by calendar
days"* — and for three further weeks nothing built it: the engine went on
pricing a whole period at the season in force on its service date. On WE-18
that billed on-peak `120 × 0.18 = $21.60` where the rule says
`64 × 0.22 + 56 × 0.18 = $24.16`.

THE DESIGN CONSTRAINT, FROM OQ-234's OWN ROW, AND IT IS WHY THIS IS SMALL
--------------------------------------------------------------------------
*"The day weights are a calendar fact and the pricing engine is pure — it holds
no calendar."* So nothing here reads a date. `rating.selectors` counts the
calendar days of the period in each season — in the same place it already
resolved ONE season on the service date — and hands them across as
`ModelConfig.season_days`. This module only answers two questions about those
counts: **does this period cross a boundary at all**, and **how much of a
measured quantity belongs to each season**.

THE ONE JUDGMENT BEYOND THE RULING, STATED SO A REVIEWER CAN REVERSE IT
-----------------------------------------------------------------------
A share of a measured quantity is QUANTIZED TO 6 DECIMALS (B2's quantity
scale, `NUMERIC(18,6)`), and the LAST season takes the remainder, so the
shares always add back to exactly what the meter measured. WE-18 itself writes
the mid-peak share as `106.666667`, which is this rule; and the money is
unaffected at the cent on every WE-18 line. Without it, `200 × 16/30` is a
non-terminating decimal and the stored shares would round independently —
two rounded halves of a reading that no longer add up to the reading. This is
QUANTITY, never money: BR-RAT-003 (a plugin never rounds an AMOUNT) is untouched,
and every amount is still `share × price`, unrounded, finalized once downstream.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from apps.rating.pricing import errors
from apps.rating.pricing.contracts import ModelConfig, SeasonMeasured, SeasonShare

#: B2's quantity scale. A share of a reading is stored at this precision.
QUANTITY_STEP = Decimal("0.000001")


def crossing(config: ModelConfig) -> tuple[SeasonShare, ...]:
    """The shares when this period CROSSES a season boundary, else `()`.

    `()` means *price exactly as before this module existed*: no shares at all
    (a schedule with no seasons, a caller that counted none) or ONE share (a
    period inside one season). That is the guarantee the ruling needs — a
    period inside one season prices byte-identically to yesterday.
    """
    shares = tuple(config.season_days or ())
    if len(shares) < 2:
        return ()
    if any(share.days <= 0 for share in shares):
        raise errors.TariffConfigError(
            "a season share of this bill period counts no days "
            f"({', '.join(f'{s.season}={s.days}' for s in shares)}). The caller "
            "counts calendar days per season (BR-RAT-034) and a share of zero days "
            "is not a share; refused rather than dividing by it."
        )
    return shares


def refuse_uncovered(shares: tuple[SeasonShare, ...], service: str, priced: str) -> None:
    """BR-RAT-033 — a day no season covers is a GAP, and a gap is a refusal."""
    if any(share.season is None for share in shares):
        days = sum(share.days for share in shares if share.season is None)
        raise errors.TariffConfigError(
            f"service {service!r}: {days} day(s) of this bill period fall in no season "
            f"the rate schedule defines (it prices {priced}). BR-RAT-033 requires the "
            "seasons to cover the year without a gap; a gap is a refusal, not free days."
        )


def split_quantity(quantity: Decimal, shares: tuple[SeasonShare, ...]) -> tuple[Decimal, ...]:
    """`quantity` pro-rata by calendar days, in the shares' order (BR-RAT-034).

    Every share but the last is `quantity × days / Σ days`, quantized to B2's
    6-decimal quantity scale; the last is the REMAINDER, so the parts always sum
    to the measured quantity exactly (see the module docstring's judgment).

    WE-18: 120 over 16/14 → (64, 56); 200 → (106.666667, 93.333333);
    380 → (202.666667, 177.333333).
    """
    total_days = sum(share.days for share in shares)
    parts: list[Decimal] = []
    allotted = Decimal(0)
    for share in shares[:-1]:
        part = (quantity * Decimal(share.days) / Decimal(total_days)).quantize(
            QUANTITY_STEP, rounding=ROUND_HALF_UP
        )
        parts.append(part)
        allotted += part
    parts.append(quantity - allotted)
    return tuple(parts)


def measured_or_split(
    quantity: Decimal,
    shares: tuple[SeasonShare, ...],
    measured: tuple[SeasonMeasured, ...],
    channel: str | None,
) -> tuple[Decimal, ...]:
    """`quantity` per season — AS MEASURED by a read on the season-change day
    where the caller handed one for this register, else by calendar days.

    `DEF-RAT-8849`, PO 2026-10-01 verbatim *"yes build the season-change day
    reading"*: WE-18's *"an ACTUAL read dated Oct 1 would replace the split"*.
    120 kWh over 15 Sep – 14 Oct with a read on 1 Oct showing 80 then 40 is
    `(80, 40)` — 80 at summer, 40 at winter — where the day split is
    `(64, 56)`. The caller found the read and subtracted the registers; this
    only checks the answer fits and hands it on (the engine holds no calendar).

    The measured parts are used ONLY when they are one per season AND add back
    to `quantity` exactly. A count that does not match the shares means they
    were cut against another season calendar (the R2 fork can swap the version
    under them); that falls back to the ruled default rather than pricing a
    reading against a calendar it was not cut for. A SUM that does not match is
    a caller fault and is REFUSED — two parts that do not add up to what the
    meter measured would bill usage nobody used, or drop usage somebody did.
    """
    found = next((m for m in measured or () if m.channel == channel), None)
    if found is None or len(found.quantities) != len(shares):
        return split_quantity(quantity, shares)
    parts = tuple(Decimal(part) for part in found.quantities)
    if sum(parts) != quantity or any(part < 0 for part in parts):
        raise errors.RatingInputError(
            f"the per-season quantities measured at the season-change read "
            f"({', '.join(str(p) for p in parts)}) do not add back to the "
            f"{quantity} the register measured, or one is negative. Refused "
            "rather than billing usage that was not measured (DEF-RAT-8849)."
        )
    return parts


def fraction(share: SeasonShare, shares: tuple[SeasonShare, ...]) -> Decimal:
    """`days / Σ days` — the share of the period, for scaling tier THRESHOLDS."""
    return Decimal(share.days) / Decimal(sum(s.days for s in shares))


def wording(share: SeasonShare, shares: tuple[SeasonShare, ...]) -> str:
    """What a split line says about its season: *"Summer, 16 of 30 days"*.

    It names a line and prices nothing. A customer billed one window twice must
    be able to see WHY there are two lines — WE-18's own presentation is
    *"16/30 summer + 14/30 winter"*.
    """
    total_days = sum(s.days for s in shares)
    return f"{share.season}, {share.days} of {total_days} days"


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-234 (CLOSED 2026-09-07) · BR-RAT-034 (CONFIRMED, PO R5-7) · WE-18/GT-34 (04-docs/05-modules/07-billing/08-worked-examples.md) · decision log 2026-09-07 "TWO RULINGS IN ONE BREATH" + 2026-10-01 "BUILT"
# generated: 2026-10-01 by the season-split lane (DEF-RAT-8832)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/golden (GT-34 engine-verified) ✔ · G64 ✔
# exceptions: the 6-decimal quantization of a quantity SHARE (remainder on the last season) is this lane's judgment, recorded in the review ledger row; it moves no cent on WE-18.
# amended: 2026-10-01 by the season-change-reading lane (DEF-RAT-8849) — a reading on the season-change day replaces the day split (PO "yes build the season-change day reading"); HUMAN-REVIEW-PENDING, review-ledger row "DEF-RAT-8849"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
