# ── Trace ──────────────────────────────────────────────
# Story:    DEF-894 (every quantity rendered six decimal places on screen and
#           in print)   Screens: S25 · S29 · RDS-01 · RDS-04
# Rules:    BR-MET-144 (PO 2026-08-27 — a quantity DISPLAYS at most two
#           decimals, trailing zeros trimmed; storage stays at six) ·
#           BR-MET-019 (storage precision) · CLAUDE.md hard rule 3 (a
#           consumption always carries its unit) · CLAUDE.md hard rule 2 (the
#           same shape, for money: stored 4, displayed 2)
# Tests:    06-backend/tests/test_def_894_quantity_display.py
# Impacts:  apps/metering/selectors (every `usage_display`) ·
#           apps/metering/services · the route sheet renderer
# ───────────────────────────────────────────────────────
"""How a QUANTITY is written for a person to read — one function, one rule.

WHY THIS FILE EXISTS, AND WHY IT DID NOT UNTIL TODAY
------------------------------------------------------
CLAUDE.md hard rule 2 fixes display at **2 decimals** for MONEY and for
PERCENTAGES, and says nothing at all about CONSUMPTION. So every quantity in
the product reached the screen at its STORAGE precision — `NUMERIC(18,6)`,
BR-MET-019's own — and printed as `8.000000 kgal`.

`readsShared.tsx` had already noticed and written the reason down, verbatim:
*"decimal details print VERBATIM at the precision the engine stored … rounding
for display is a decision no signed document makes for these figures"*. That
was **true**, and it is exactly why nothing was done and no gate could object:
there was no figure to check against, so six places was not wrong, it was
merely unruled.

**The Product Owner ruled it on 2026-08-27**, after finding it on the live app:

    "decimal places and any other issues you observe"
    → "2 decimals max, trailing zeros trimmed - this is correct"

which is what `05-prototype/r10` had been drawing the whole time — `684 kWh`,
`3.72 kgal`, `26.24 kgal`. Hard-won law 6: the answer was on screen in the
reference and nothing in this repo reads rendered output.

THE RULE, STATED ONCE
----------------------
* **At most two decimals.** More than two rounds, half-up, the same direction
  B4 rounds money.
* **Trailing zeros are trimmed**, and a whole number keeps no point at all:
  `8.000000` → `8`, never `8.00`. This is where a quantity DIFFERS from money —
  `$8.00` is right and `8.00 kgal` is noise, because a quantity's precision is
  what the meter measured and money's is what the currency is denominated in.
* **Storage does not move.** Six places is what BR-MET-019 stores and what the
  engine computes with. This function is the last step before a person reads
  it, and nothing round-trips through it.

⚠ **AND IT IS NEVER USED ON MONEY.** Money has its own rule, its own 2dp, and
its own cell (`MoneyCell`, DEF-088). A quantity trimmed to `8` and a price
trimmed to `8` look identical and mean different things; keeping the two
functions apart is what stops one being reached for in the other's place.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

#: Two, and it is the PO's figure rather than this file's.
DISPLAY_PLACES = Decimal("0.01")


def quantity_text(value: Any) -> str | None:
    """`8.000000` → `"8"` · `3.720000` → `"3.72"` · `8.126` → `"8.13"`.

    `None` in, `None` out — an absent quantity is absent, and a caller that
    wants a dash renders one. Returning `"0"` for a missing reading would state
    that a meter measured nothing, which is a different and false fact
    (BR-MET-106's *an unread month is ABSENT, never a zero*).

    A value this cannot parse comes back as its own string rather than raising:
    this runs on the last step before a screen, and a display helper that
    breaks a page over an odd value has made a rendering problem into an outage.
    """
    if value is None:
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)
    rounded = number.quantize(DISPLAY_PLACES, rounding=ROUND_HALF_UP)
    # `normalize()` alone would give `8E+1` for 80 — correct and unreadable —
    # so the exponent is expanded back out. This is the documented idiom and
    # the reason it is written here once instead of at six call sites.
    trimmed = rounded.normalize()
    if trimmed == trimmed.to_integral_value():
        trimmed = trimmed.quantize(Decimal(1))
    return f"{trimmed:f}"


def quantity_with_unit(value: Any, unit: Any) -> str | None:
    """The rendered pair — `"8 kgal"` — or `None` when there is no quantity.

    ⚠ **THE UNIT IS NOT OPTIONAL AND THAT IS CLAUDE.md HARD RULE 3.** A
    quantity with no unit is refused a rendering here rather than printed bare,
    because a bare number in a column headed *Usage* is read as the tenant's
    own unit by whoever is looking at it. A caller holding a quantity and no
    unit has a data problem, and the screens already have a sentence for it.
    """
    text = quantity_text(value)
    if text is None:
        return None
    if unit is None or str(unit).strip() == "":
        return None
    return f"{text} {unit}"
