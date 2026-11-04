# ── Trace ──────────────────────────────────────────────
# Rules:    BR-RAT-092 (PO 2026-08-20: "all finance field need same decimal
#           rule - apply to every fiannce field") · BR-RAT-089 (store 4,
#           display 2) · OQ-286 CLOSED (PO 2026-08-20: "for perctnage you can
#           have 6 decimal places") · CR-013 part 1 (rates keep six) ·
#           B4 ❄️ · CLAUDE.md hard rule 2
# ───────────────────────────────────────────────────────
"""The decimal rule for money columns, declared ONCE.

B12 §No hard-coded values, applied to the schema: `decimal_places` appears on 56
columns today and the rule that decides it appeared nowhere. A number repeated 56
times is 56 chances to be wrong, and a wrong one is invisible — the column is
well-formed, the bill is produced, and the value is short in its fourth digit.

THE RULE HAS THREE KINDS AND TWO PRECISIONS
-------------------------------------------
The PO's *"all finance field need same decimal rule"* resolves to three kinds,
because "finance field" is not one thing:

    AMOUNT   money you can actually hold      NUMERIC(18,4)   BR-RAT-089/092
    PERCENT  a proportion                     NUMERIC(18,6)   OQ-286
    RATE     a price per unit of something    NUMERIC(18,6)   CR-013 part 1

**Why percent is not four.** A percent stored as a FRACTION needs two more places
than the percent it expresses. CR-013 part 4 requires a tax rate *"percent to 4
decimals"* — `6.2500%` — and `taxes.rate` stores `0.062500`, which is six. At four
it truncates to `0.0625`: two decimals of percent, lost silently. The PO ruled six
(OQ-286), which keeps every fraction column exactly as it is and needs no data
conversion at all.

**Why rate is not four.** `$0.118500` per kWh is a real per-unit price, and part 1
restates frozen B4 for exactly these: *"rates stored to 6 decimals."* A rate is
multiplied by a quantity before it becomes money, so its precision compounds —
truncating it moves the bill, where truncating an amount only moves itself.

**Why amount IS four.** The PO's reason, recorded: *"generally utilities user will
input 2 decimal places not more than that"* — so four is headroom for anything
derived, and six was never earning its extra two.

WHAT THIS MODULE DOES NOT DO
----------------------------
It does not migrate the 56 existing columns. Adopting it is one edit per column
plus one migration, and every column that adopts it stops being able to drift.
`charge_code_amounts` is the first adopter because it is **empty**, so narrowing
it costs nothing and proves the path.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import models

#: The one place these numbers exist.
MONEY_DIGITS = 18
AMOUNT_PLACES = 4  # BR-RAT-089/092
PERCENT_PLACES = 6  # OQ-286 — a fraction needs two more than its percent
RATE_PLACES = 6  # CR-013 part 1, restating ❄️ B4

#: What a caller rounds TO before storing an amount. Named so nobody writes
#: Decimal("0.0001") at a call site and quietly disagrees with the column.
AMOUNT_QUANTUM = Decimal(1).scaleb(-AMOUNT_PLACES)
PERCENT_QUANTUM = Decimal(1).scaleb(-PERCENT_PLACES)


def money_field(**kwargs: Any) -> models.DecimalField:
    """An AMOUNT — money a tenant can hold, invoice or remit. Four places."""
    return models.DecimalField(max_digits=MONEY_DIGITS, decimal_places=AMOUNT_PLACES, **kwargs)


def percent_field(**kwargs: Any) -> models.DecimalField:
    """A PERCENT, stored either as a fraction (`0.062500`) or as percent points
    (`40`) — the product uses both conventions and this covers each, because the
    place count is what differs from an amount, not the convention."""
    return models.DecimalField(max_digits=MONEY_DIGITS, decimal_places=PERCENT_PLACES, **kwargs)


def rate_field(**kwargs: Any) -> models.DecimalField:
    """A RATE — a price per unit, multiplied by a quantity before it is money."""
    return models.DecimalField(max_digits=MONEY_DIGITS, decimal_places=RATE_PLACES, **kwargs)
