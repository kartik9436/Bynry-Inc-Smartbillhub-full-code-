# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-6440 — `charge_code_amounts` holds ZERO rows on every tenant
#          this product has ever seeded, so the base charge does not vary by
#          connection size anywhere. `BR-RAT-088` works its own example on a
#          base that DOES vary — a 5/8" water base at $8.00 and a 2" at $34.00
#          — and `BR-RAT-690` built the writer for it on 2026-08-28. Neither
#          reached the seed: the shipped fixture states ONE flat amount per
#          charge code, so a utility opening CHG-02 step 2 sees an empty table
#          and learns nothing about what the size axis is for.
# Rules:   BR-RAT-088 (the CHARGE CODE owns the base amount) · BR-RAT-108 (the
#          base narrows by service -> customer class -> METER SIZE, and its own
#          worked example is this file's water anchor) · BR-RAT-690 (the write
#          path, and the size must be one the tenant configured) · BR-RAT-092 /
#          BR-RAT-089 (money stored to 4 decimals, displayed to 2 —
#          CLAUDE.md hard rule 2) · CR-013 part 1 / DEF-277 (a blank base means
#          THIS SIZE IS NOT SERVED and stops the bill; a stored 0 is a PRICE)
# Golden:  none. ⚠ **NO ❄️ FROZEN FIGURE IS REACHABLE FROM THIS FILE** — see the
#          `GT-10` paragraph in the module docstring, which states the evidence
#          rather than the claim (hard-won law 1).
# Impacts: apps/rating/sample_data.py (`seed_sample_base_charge_codes`) ·
#          `charge_code_amounts` rows on every newly seeded tenant
# ───────────────────────────────────────────────────────
"""🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — see `12-governance/09-human-review-ledger.md`.

**THE BASE CHARGE'S SIZE LADDER — what a bigger connection pays for its base.**

A base charge is not paid for water, gas or kilowatt-hours; it is paid because
a CONNECTION EXISTS (`BR-RAT-080`), and what a connection costs a utility is
the CAPACITY it reserves whether or not anybody opens a tap. That is why every
North American schedule steps the base by meter size, and it is why a 6" water
meter is not twice a 5/8" one but roughly twenty-five times it.

⚠ **THIS FILE STATES MULTIPLIERS, NEVER MONEY, AND THAT IS THE WHOLE DESIGN.**
The AMOUNT for a size is `the charge code's own anchor amount x the ladder`.
The anchor is the figure the code already states — `$8.00` for `BASE-W`,
`$15.00` for `BASE-W-COM`, `$12.00`/`$48.00`/`$180.00` for the three electric
codes — so:

  * **the smallest size keeps EXACTLY the figure that code charges today**, and
    every seeded bill is byte for byte what it was (measured, not assumed —
    `10-scripts/def2799_live_base_charges.py` diffs empty across this change);
  * a utility that prices its residential and commercial customers differently
    gets ONE ladder and two price levels, which is `BR-RAT-108`'s own shape;
  * there is exactly one statement of how the base grows with size, so the two
    cannot drift apart the way `DEF-2823`'s plan and charge code did.

⚠ **AND THE ANCHOR SIZE IS LOAD-BEARING FOR A REASON THAT IS NOT AESTHETIC.**
⚠ **THIS PARAGRAPH SAID THE ANCHOR STOPS A BILL, AND THAT STOPPED BEING TRUE
ON 2026-09-28 (`DEF-BIL-7170`).** It read: *"`gather._base_charge_for` REFUSES
a bill, by name, when the charge code and the plan state DIFFERENT bases …
a ladder whose anchor size did not reproduce it would not merely move a bill:
it would STOP one"*. The PO retired the plan's figure — *"we will never take
default value from plan $8.0 - that is retired"* — so nothing a plan states can
stop a bill. **The anchor is still load-bearing and the reason is now a
DISPLAY reason:** `plan_services.base_charge` still states the flat figure and
a clerk still reads it on the plan, so a ladder whose anchor size did not
reproduce it would put a number on the screen that no bill charges. Agreeing to
the cent by construction is still `DEF-455`'s requirement; what it buys is an
honest screen rather than a bill that runs.

── WHERE THE NUMBERS COME FROM, SERVICE BY SERVICE ─────────────────────────
The shape is the one every utility fixed charge actually has: **half of the
smallest size's base is a CUSTOMER component every connection pays whatever its
size — meter reading, billing, the account itself — and half is a CAPACITY
component that scales with what the connection can take.** So

    multiplier(size) = 0.5 + 0.5 x (capacity(size) / capacity(smallest size))

and the smallest size is always `1.0000` by construction.

⚠ **THAT FORMULA IS NOT INVENTED HERE — IT IS READ OFF TWO FIGURES THE REPO HAS
ALREADY RATIFIED, WHICH IS WHY IT IS USED RATHER THAN SOMETHING TIDIER.**
`BR-RAT-108` (CONFIRMED, PO 2026-08-21) publishes a water ladder in its own
words: *"`BASE-W` residential can state `5/8" $8.00 - 1" $14.00 - 2" $34.00`"*.
At AWWA capacity ratios of 1 and 2.5 the formula gives `1.0000` and `1.7500`,
i.e. **$8.00 and $14.00 — both published figures exactly**. Independently,
fire's six ratified prices (`FIRE_DEFAULT_PRICES`, PO 2026-09-02/09-03) run
`$12 / $30 / $60 / $100 / $160 / $230`, which against diameter-squared capacity
is `1.00 / 2.50 / 5.00 / 8.33 / 13.33 / 19.17` where this formula gives
`1.00 / 2.50 / 5.00 / 8.50 / 13.00 / 18.50`. Two independent ratified ladders,
one shape. This file is therefore recording the house method rather than
choosing a new one.

⚠ **ONE PINNED EXCEPTION, STATED RATHER THAN SMOOTHED (water 2").** At an AWWA
ratio of 8 the formula gives `4.5000`, i.e. `$36.00`, and `BR-RAT-108` publishes
**`$34.00`**. The published figure WINS and the ladder carries `4.2500`, because
that number is quoted in three separate rules (`BR-RAT-088`, `BR-RAT-108`,
`BR-RAT-690`) and a seed that contradicted the register would teach a reader the
register is wrong. The `$2.00` divergence is recorded here rather than left for
somebody to rediscover as a defect.

⚠ **`GT-10` CANNOT MOVE, AND HERE IS THE EVIDENCE RATHER THAN THE ASSURANCE.**
`06-backend/tests/golden/conftest.py` builds `GT10_TARIFF` as a literal
`rating_seam.TariffConfig(service="electric", model="flat",
base_charge=Decimal("18.50"), unit_price=Decimal("0.12"))` and hands it straight
to `rating_seam.price_period`. It reads **no tenant, no charge code, no size
class and no database at all** — so GT-10's bill has no meter and therefore no
size class for this ladder to price. `$18.50` is an input constant in a test
file, not a seeded amount, and the same is true of every other ❄️ B5 figure:
B5 hands the base to the engine directly. The golden suite is run either side of
this change and reported, because *"a comment claiming a guarantee is not the
guarantee"* (hard-won law 1).

── WHAT THIS FILE DELIBERATELY DOES NOT PRICE ──────────────────────────────
**Only a service whose base charge is a SIGNED, NON-ZERO figure gets a ladder**
— water, electric and gas, whose amounts come from the billing workbook
`[W] §1`. The other eight services state a base of `$0.00`, and multiplying zero
by any ladder is still zero, so a table for them would be 44 rows of `$0.00`:
the flattest possible table, which is exactly the thing that makes a size class
stop meaning anything.

Their zeros are NOT this file's to overwrite, and the two reasons are different:

  * **trash is a PO RULING** — `OQ-317` option A retired the trash base to zero
    because trash bills per CART (`$15.00` each, `BR-RAT-090`). Giving it a
    standing charge reverses a decision the Product Owner made.
  * **sewer, storm water, solar, broadband, thermal, battery and fire are
    UNSIGNED** — `core/sample_fixture.CAPACITY_BASE` states the fixture's own
    standing law for them: *"a base nobody signed is a base this fixture does
    not invent"*, and the billing workbook names a base for electric, water and
    gas and for nothing else.

⚠ **AND RAISING ONE IS A TWO-FILE CHANGE, WHICH IS WHY IT IS NOT SMUGGLED IN
HERE.** The charge code's amount and `plan_services.base_charge` must agree to
the cent or the bill REFUSES (above), and the plan's figure comes from
`core/sample_fixture.CAPACITY_BASE` — a file this module does not own and that
metering and assets also read. Moving it changes money on every seeded tenant of
eight services at once. It is reported with its worked figures instead.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.tenancy import service_size_classes

#: `BR-RAT-092` / `BR-RAT-089` — an AMOUNT is stored to FOUR decimals and
#: displayed to two (CLAUDE.md hard rule 2). `charge_code_amounts.amount` is
#: `core.money_fields.money_field()`, i.e. `NUMERIC(18,4)`, so this is the
#: quantum every figure this module produces is snapped to.
MONEY_EXPONENT = Decimal("0.0001")


class LadderIncomplete(KeyError):
    """A service has a ratified size class this ladder does not price.

    ⚠ **RAISED BY NAME RATHER THAN LET THROUGH AS A `KeyError`, and the
    precedent is `DEF-3087` one module over.** These two lists grow
    independently: a size class is ratified in
    `apps/tenancy/service_size_classes.RATIFIED_SERVICE_SIZE_CLASSES` and its
    multiplier is typed HERE. On 2026-09-02 `fire` joined one and not the other
    and a bare subscript raised `KeyError: 'fire'` out of the middle of
    `seed_sample_records`, taking down fourteen of the seventeen seeding blocks
    and leaving the tenant with no bills at all.

    **A missing multiplier is not a cosmetic gap.** `resolve_charge_codes`
    refuses a bill for a size a per-size code does not price — PO ruling
    2026-08-28, *"an unpriced size is REFUSED and never substituted"* — so a
    size class added upstream without a rung here would stop every bill on a
    connection of that size. The message says what to add and where.
    """


#: **HOW MUCH CAPACITY EACH SIZE CLASS RESERVES, RELATIVE TO THE SMALLEST.**
#:
#: Not the multiplier — the RATIO the multiplier is derived from. It is kept
#: separate so the basis can be checked against a physical fact rather than
#: taken on trust, and so the formula appears once instead of nine times.
#:
#: ⚠ **EVERY ENTRY CITES A MEASURE, NOT A PREFERENCE.** A number here that
#: cannot be traced to a rated capacity is a number somebody liked the look of,
#: and this is a 🔒 money path.
CAPACITY_RATIOS: dict[str, dict[str, Decimal]] = {
    #: AWWA M1 safe-maximum-operating-capacity ratios, the North American
    #: standard for meter equivalence and the basis every water utility's
    #: fixed-charge schedule is built on. 5" is not an AWWA size; it is taken as
    #: the midpoint of 4" (25) and 6" (50), and it is priced rather than omitted
    #: because an ABSENT size REFUSES a bill (`DEF-277`) where a stated one
    #: merely charges.
    "water": {
        "W-58": Decimal("1"),  # 5/8"
        "W-34": Decimal("1.5"),  # 3/4"
        "W-1": Decimal("2.5"),  # 1"
        "W-112": Decimal("5"),  # 1.5"
        "W-2": Decimal("8"),  # 2"
        "W-3": Decimal("16"),  # 3"
        "W-4": Decimal("25"),  # 4"
        "W-5": Decimal("37.5"),  # 5" — midpoint of 4" and 6", see above
        "W-6": Decimal("50"),  # 6"
    },
    #: Rated apparent power in kVA, relative to a 1-phase 100 A service.
    #: 1-phase at 240 V: `A x 240 / 1000`. 3-phase at 208 V:
    #: `A x 208 x sqrt(3) / 1000`. So 1P-100 is 24 kVA and is the unit here;
    #: 3P-200 is 72 kVA, which is why it sits BETWEEN 1P-200 and 1P-400 rather
    #: than beside 1P-200 — the ladder is ordered by capacity, not by ampere
    #: number, and that is the point of stating the basis.
    #: `E-CT` is the CT-metered class, which begins where direct metering stops;
    #: taken as a 1,200 A 3-phase service, 432 kVA, ratio 18.
    "electric": {
        "E-1P-100": Decimal("1"),  # 24 kVA
        "E-1P-200": Decimal("2"),  # 48 kVA
        "E-3P-200": Decimal("3"),  # 72 kVA
        "E-1P-400": Decimal("4"),  # 96 kVA
        "E-3P-400": Decimal("6"),  # 144 kVA
        "E-CT": Decimal("18"),  # 432 kVA
    },
    #: Rated capacity in cubic feet per hour, relative to the 250 CFH
    #: residential diaphragm meter — the size class's own name states it.
    "gas": {
        "G-250": Decimal("1"),
        "G-425": Decimal("1.7"),
        "G-630": Decimal("2.52"),
        "G-1000": Decimal("4"),
    },
}

#: **WHICH SERVICES GET A LADDER AT ALL.** The module docstring's last section
#: is the reasoning; this is the list it produces. A service absent from here
#: keeps the FLAT amount its charge code already states.
LADDERED_SERVICES: tuple[str, ...] = ("water", "electric", "gas")

#: `BR-RAT-108`'s published water figure at 2", as a MULTIPLIER of the 5/8"
#: base. The formula gives `4.5000`; the register publishes `$34.00` on an
#: `$8.00` base, i.e. `4.2500`, in three separate rules. The register wins and
#: the divergence is named — see the module docstring.
_PINNED: dict[tuple[str, str], Decimal] = {
    ("water", "W-2"): Decimal("4.25"),
}


def multiplier(service_code: str, size_class_code: str) -> Decimal:
    """This size's base as a multiple of the smallest size's base.

    `0.5 + 0.5 x capacity ratio`, except where the register publishes a figure
    (`_PINNED`). Always `1` for the smallest size, by construction.
    """
    pinned = _PINNED.get((service_code, size_class_code))
    if pinned is not None:
        return pinned
    ratios = CAPACITY_RATIOS.get(service_code)
    if ratios is None or size_class_code not in ratios:
        raise LadderIncomplete(
            f"{size_class_code!r} is a ratified size class of {service_code!r} "
            "with no rung on the base-charge ladder in "
            "apps/rating/base_size_amounts.CAPACITY_RATIOS. A per-size base "
            "charge REFUSES a bill for a size it does not price (PO ruling "
            "2026-08-28: an unpriced size is never substituted), so every "
            "connection of this size would stop billing rather than fall back "
            "to another size's rate. Add the size's RATED CAPACITY relative to "
            f"the smallest {service_code} size — not a multiplier, and not a "
            "figure chosen for its shape."
        )
    return Decimal("0.5") + Decimal("0.5") * ratios[size_class_code]


def has_ladder(service_code: str) -> bool:
    """True where this service's base charge varies by connection size."""
    return service_code in LADDERED_SERVICES


def size_amounts(service_code: str, anchor_amount: Any) -> list[dict[str, Any]]:
    """The `size_amounts` payload `rating.services.create_charge` takes.

    `anchor_amount` is what the charge code charges the SMALLEST size — the
    flat figure it states today — so the first rung reproduces it exactly and
    no seeded bill moves.

    Returns `[]` for a service with no ladder and for a zero or absent anchor,
    which is what keeps the caller from writing a table of zeros. **An empty
    list is not an empty table**: the caller then leaves the code's flat amount
    in place, which is the behaviour every tenant has today.

    ⚠ **THE ROWS ARE BUILT FROM THE RATIFIED SIZE LIST AND NEVER FROM THIS
    MODULE'S OWN KEYS.** `service_size_classes` is the one place a size class
    exists (`BR-TEN-031`/`170`), and `_validate_size_amounts` refuses a code the
    tenant has not configured — so iterating `CAPACITY_RATIOS` instead would let
    a stale key here become a row nothing ever looks up, which is exactly the
    silent `W58`-for-`W-58` failure `BR-RAT-690` was written to prevent.
    """
    if not has_ladder(service_code):
        return []
    anchor = Decimal(str(anchor_amount)) if anchor_amount is not None else Decimal("0")
    if anchor <= 0:
        # A ladder on a zero anchor is a table of zeros — see the module
        # docstring. The caller keeps the flat amount and nothing is written.
        return []
    rows: list[dict[str, Any]] = []
    for code, _name in service_size_classes.size_classes_for_service(service_code):
        amount = (anchor * multiplier(service_code, code)).quantize(MONEY_EXPONENT)
        rows.append({"size_class": code, "amount": str(amount)})
    return rows


def ladder_table(service_code: str, anchor_amount: Any) -> list[tuple[str, str, Decimal]]:
    """`(size code, size name, amount)` for REPORTING — the table a person reads.

    Separate from `size_amounts` above because that one produces a write payload
    and this one produces evidence, and a reporting helper that reshaped the
    write payload would be a second derivation of a money figure.
    """
    return [
        (code, name, Decimal(row["amount"]))
        for (code, name), row in zip(
            service_size_classes.size_classes_for_service(service_code),
            size_amounts(service_code, anchor_amount),
            strict=True,
        )
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-6440 · BR-RAT-088 / BR-RAT-108 / BR-RAT-690
# generated: 2026-09-07 by the rating-pricing lane (claude)
# gates: ruff · black · pytest tests/test_def_rat_4492_base_size_ladder.py
# status: VERIFIED-UNRATIFIED — 🔒 money path, HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
