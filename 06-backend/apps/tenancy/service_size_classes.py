# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-010 (EP-TEN-07 — reference data; this file is the CONTENT
#           half of one list)   Screens: S8 → Reference data → "Utility service
#           size classes" (r10 SET-04.sizes)
# Change:   CR-062 group A (A1–A6) — 2026-09-02. Solar, battery and storm water
#           are sized by a SUMMABLE CAPACITY rather than by a band, so every row
#           now carries a number and its unit as well as a label.
#           CR-063 tasks A4/A5 — 2026-09-02. FIRE joins as the ELEVENTH service
#           with seven BANDS and a price list, and it is the one list on this
#           table the Product Owner has never seen (`OQ-1360`, OPEN).
#           CR-080 — 2026-09-07. THERMAL/HEAT stops being a metered service
#           and becomes a CAPACITY one billed on CONNECTED TONNAGE. PO:
#           *"connected tonnage - it is capacity not metering; i will ahve 100
#           tonne or 200 tonne etc"*. The three `TH-CW-*` RANGES are withdrawn
#           — a range has no single value a capacity could be — and replaced
#           by eight connected-tonnage capacities in `ton`. 59 rows -> 64.
#           CR-063 AMENDED — 2026-09-03. PO: *"remove private hydrants from
#           list"*. `HYD` "Private hydrant" at `$25.0000` is WITHDRAWN and fire
#           goes 7 BANDS -> 6. It supersedes a worked figure signed the day
#           before: the warehouse with a 6" line and two hydrants was `$110.00`
#           and is now `$60.00`, `−$50.00` a month. The six diameters and their
#           prices do NOT move.
# Rules:    BR-TEN-170 (the list is the UTILITY SERVICE size class, not the
#           meter size class — PO 2026-08-27) · BR-TEN-171 (the ratified
#           classes, the dimensions that carry none, and — since CR-062 — which
#           of them are capacities rather than bands) · BR-TEN-071
#           (insert-if-absent; never UPDATE, never DELETE) · BR-TEN-072 (renames
#           forbidden in seed data — add the new code, deactivate the old) ·
#           BR-TEN-078 (this list is NOT service-scoped; the row names its
#           service in its own display name) · BR-RAT-015 (sewer is a share of
#           the water usage charge, which is why sewer carries no size class) ·
#           CLAUDE.md hard rule 3 (a quantity always carries an explicit unit)
# Tests:    06-backend/tests/test_cr039_e20_size_class_bands.py
#           06-backend/tests/test_cr039_e21_service_size_classes.py
#           06-backend/tests/test_cr062_a_capacity_size_classes.py
#           06-backend/tests/test_cr063_fire_service.py
# Impacts:  apps/tenancy/fixtures/lookup_defaults.json (`service_size_classes`
#           mirrors `seed_entries()` and a test refuses drift) ·
#           apps/tenancy/services.ServiceSizeClassLookupHandler ·
#           apps/rating/resolution.py (base charge resolves service → account
#           type → size class, so these codes are a rating input)
# ───────────────────────────────────────────────────────
"""BR-TEN-171 — the ratified utility-service size classes, as law rather than
as data.

WHY THIS FILE EXISTS AT ALL, WHEN THE FIXTURE ALREADY CARRIES THE ROWS
----------------------------------------------------------------------
The platform fixture is a DELIVERY MECHANISM: a version, a digest and a list of
`{code, name}` pairs that `_seed_reference_data` copies into a tenant. It cannot
say WHICH SERVICE a row belongs to, WHICH SERVICES DELIBERATELY HAVE NO ROWS,
WHY, or — since CR-062 — **WHETHER THE ROW IS A BAND OR A CAPACITY**. Those
facts are the ruling, and they are the whole point of the list:

  * **sewer has none BY RULING** — it is priced as a share of the water usage
    charge (BR-RAT-015) and reads no register, so there is nothing to size;
  * **thermal steam has none BY ABSENCE OF A RULING** — the PO was shown a
    DIMENSION and no boundaries (OQ-560). ⚠ **`CR-080` DID NOT CLOSE THIS.**
    It moved the whole service from metered to capacity and gave the CHILLED-
    WATER half a tonnage catalogue; steam's boundaries were never put to
    anybody and `steam_size_classes()` still raises.

In the fixture those two are indistinguishable: each is simply a service with no
rows. Here they are two different statements, and only one of them is a gap.
That distinction is what stops the next lane "finishing the list".

════════════════════════════════════════════════════════════════════════════
A SIZE CLASS IS ONE OF TWO DIFFERENT THINGS, AND THE DIFFERENCE IS ARITHMETIC
════════════════════════════════════════════════════════════════════════════
**This is the CR-062 change and it is the reason the row grew two fields.**

A **BAND** is a LABEL that picks a rate. Water's `W-2` is a pipe diameter,
electric's `E-1P-200` is a service entrance rating, gas's `G-630` is a meter's
cubic-feet-per-hour capacity. (Thermal's `TH-CW-25` was a RANGE and is exactly
why it could not survive `CR-080`.) A customer sits
in exactly one band and the band chooses which flat price applies. **You cannot
add two bands together** — the question has no meaning.

A **CAPACITY** is a NUMBER WITH A UNIT that is INSTALLED, possibly several times
on one unit, and the billable quantity is the SUM. The Product Owner put it in
their own words on 2026-09-02:

    "In solar youa re still not doing it correctly - For example We have 10
     Types of Solar panel with various capaity 1 Kw, 2Kw 3Kw 4Kw so and SO
     forth ; on given Unit we have installed 3 panels with 2Kw, 4Kw and 8 Kw ,
     it means the totla capacity will be 14 Kw ; rate will be for 1 Kw = 14 $
     per KW then bill should be 14 X 14 = 156 $"

Three panels of 2 kW, 4 kW and 8 kW are **14 kW**. Under the old structure — a
code and a display name and nothing else — the only quantity this product could
produce for that array was **3**, which prices a 14 kW system exactly like three
1 kW ones. **A name is a label; you cannot add labels together.** That is the
whole of A6.

⚠ **THE ARITHMETIC IN THAT QUOTE IS OFF BY ONE PRODUCT AND THE CORRECT FIGURE
IS THE ONE THIS PRODUCT USES.** 14 kW at $14.00 per kW is **$196.00**, not $156.
The PO was told so in the same session and did not dispute it. `$156` is written
nowhere in this repo, deliberately: a wrong figure copied into a fixture becomes
a wrong figure asserted by a test, and then it is the product's answer.

**HOW THE STRUCTURE HOLDS BOTH KINDS WITHOUT PRETENDING.** Every row is a
`SizeClass`, and its `capacity` is `None` for a band and a `Decimal` for a
capacity:

    band      SizeClass("W-2",    'Water 2"',           None,        None)
    capacity  SizeClass("SOL-P4", "Solar panel 4 kW",   Decimal(4),  "kW")

**`None` and not `0`, and the difference is the point.** A zero would sum
silently into a wrong total; `None` refuses. `total_capacity()` raises
`NotACapacityService` rather than answering, so trash — whose seven rows are
three CARTS measured in gallons and four DUMPSTERS measured in cubic yards —
cannot be summed even by accident. **There is no unit in which "a 96-gallon cart
plus a 4 cu-yd dumpster" is a quantity**, and the PO's own ruling for trash is
the count anyway: *"Cart sizes will decide price X how many Cart"*.

So "capacity based" is not one billing shape but TWO — trash MULTIPLIES a rate
by a COUNT, solar multiplies a rate by a SUM — and `capacity_uom_for_service()`
is the one call that tells them apart.

**WHAT PRECISION A CAPACITY CARRIES, AND WHY IT IS A DELIBERATE ANSWER.**
CLAUDE.md hard rule 2 fixes money at 4 decimal places and percentages at 6. A
capacity is neither, so it needs its own decision rather than an inherited one:

  * it is a **`Decimal` built from an exact integer or string, NEVER a float** —
    a capacity is MULTIPLIED BY a money figure, so a float's error is not a
    display artefact, it is a money error one operation later;
  * it is quantised to **4 decimal places**, matching money's scale, so that
    `capacity × rate` introduces **no rounding step of its own** and B4's
    "round only at finalization" remains the only rounding in the chain;
  * 0.0001 kW is far below anything a utility installs or meters, so the scale
    costs nothing and buys the guarantee above.

**THREE INVARIANTS ARE CHECKED AT IMPORT**, so a bad edit fails loudly and
immediately instead of producing a plausible wrong total months later:

  1. a row carries a number and a unit or neither, never one of the two
     (hard rule 3 — a quantity never travels without its unit);
  2. within one service every row is a band or every row is a capacity, never
     a mixture — "a service is billed on a sum" is a fact about the SERVICE;
  3. within one service every capacity shares ONE unit — you cannot add kW to
     Mbps, and a total assembled from two units is a number with no meaning.

⚠ **A TRAP FOR THE LANE THAT PRICES THESE (CR-062 H4), NAMED HERE BECAUSE THIS
FILE IS WHERE IT LOOKS LIKE A GOOD IDEA.** A capacity service's rows are a
CATALOGUE OF EQUIPMENT, not a rate axis. Building a rate schedule with one row
per solar size class puts several different sizes on one connection, which
`metering.connection_size_for` refuses — *"one connection has one size; two
different recorded sizes is a data error"* — and `gather` then refuses the bill
with `connection_size_unresolved_for_sized_schedule`. The PO's own example, three
panels of 2, 4 and 8 kW on one unit, is exactly that disagreement. Under the sum
model the size class is not the pricing axis for solar at all: the schedule
prices per kW flat and the refusal never arms. **Ask
`capacity_uom_for_service()` before treating any of these rows as a rate axis.**

THE SIGNATURE COVERS ONLY WHAT WAS SHOWN (PO 2026-08-11)
---------------------------------------------------------
PO verbatim, 2026-08-27:

    "Water (has 4) Pipe diameter keep the four; add 1½" · 3" · 4" · 6" - you
    need 1 inch 2 inch also 5 inch also; rest all are correct in this -
    Question 1 — the bands; Question 2 — is it a meter size class, or a service
    size class? it is utility service size class"

*"rest all are correct in this"* ratifies THE TABLE THAT WAS PUT TO THEM. Steam
carried a unit and no boundary — *"steam by thousand pounds per hour"* — so it
is NOT ratified and `steam_size_classes()` raises. **A band boundary decides
which base charge a customer pays; inventing one is inventing money.**

WHY THE ROW NAMES ITS OWN SERVICE INSTEAD OF CARRYING A COLUMN
--------------------------------------------------------------
BR-TEN-078 leaves `uoms` the only service-scoped reference list, and CR-004's
argument for that default is asymmetry, not caution: switching a list ON later
is a one-line registry change, switching it OFF after tenants have entered
scoped data is a migration. So `SERVICE` below is structure IN THIS FILE and a
display-name prefix on the row.

⚠ **STORM WATER'S FIVE ROWS ARE THE ONE DELIBERATE EXCEPTION TO THAT PREFIX,
AND IT IS RECORDED RATHER THAN QUIETLY TAKEN.** The PO approved those five names
as they read below — *"Single-family home"*, *"Apartment building"* — because
they name the PROPERTY a clerk is looking at, which is how storm water is
actually sized. That is what was shown and approved on 2026-09-02, so it is what
ships. **The cost is real and is stated here so nobody has to rediscover it:**
this list is unscoped, so on S8 those five rows sit among 53 and do not say
which service they belong to, which is exactly what BR-TEN-078's prefix
convention exists to prevent. Reversing it is a one-line change per row (prefix
*"Storm water "*) and needs the PO, because the names are theirs.
"""

from __future__ import annotations

from decimal import Decimal
from collections.abc import Mapping
from typing import NamedTuple

#: The scale every capacity is quantised to — 4 decimal places, money's scale.
#: See the docstring: a capacity is multiplied BY a money figure, so matching
#: scales keeps `capacity × rate` free of any rounding step of its own.
CAPACITY_EXPONENT = Decimal("0.0001")


class SizeClass(NamedTuple):
    """One ratified size class: a code, the name a person reads, and — for a
    CAPACITY service only — how much of the thing is installed, with its unit.

    `capacity` and `capacity_uom` are BOTH `None` for a band and BOTH set for a
    capacity; `_validate_ratified_rows()` refuses any other combination at
    import time. A band's capacity is `None` rather than `0` deliberately: a
    zero sums silently into a wrong answer, and `None` refuses.
    """

    code: str
    name: str
    capacity: Decimal | None
    capacity_uom: str | None

    @property
    def is_capacity(self) -> bool:
        """True when this row is a number that can be added to another one."""
        return self.capacity is not None

    @property
    def is_band(self) -> bool:
        """True when this row is a LABEL that picks a rate and sums with nothing."""
        return self.capacity is None


def _band(code: str, name: str) -> SizeClass:
    """A size class that PICKS A RATE and carries no summable quantity."""
    return SizeClass(code, name, None, None)


def _capacity(code: str, name: str, qty: int | str, uom: str) -> SizeClass:
    """A size class that IS a quantity — a number with its unit, summable.

    `qty` is an int or a string and NEVER a float: `Decimal(0.1)` is not 0.1,
    and this number gets multiplied by a price.
    """
    return SizeClass(code, name, Decimal(qty).quantize(CAPACITY_EXPONENT), uom)


#: The platform catalog's ELEVEN service CODES — `tenancy/migrations/0001_initial.py`
#: `SERVICE_SEED` for the first ten and `0033_cr063_fire_service` for `fire`,
#: `SERVICE_SEED` order (BR-RAT-024) — which is also the order rows appear on the
#: S8 card.
#:
#: ⚠ **THE CODES ARE THE MIGRATION'S, NOT CLAUDE.md's PROSE — and thermal is why.**
#: CLAUDE.md calls the ninth service *Thermal/Heat*; the column stores
#: **`thermal_heat`**. This file first wrote `thermal`, a code no service has, so
#: `size_classes_for_service("thermal_heat")` raised `KeyError` and the three
#: ratified chilled-water classes were unreachable by their own service's name.
#: Every other case in the suite still passed, because they all ask this module
#: about itself and a wrong key is self-consistently wrong. TC-12 now pins this
#: tuple against `SERVICE_SEED`, so a display name can never stand in for a code.
#:
#: Named here rather than imported so this file states the whole of what it
#: claims to cover: a service missing from this tuple would silently seed nothing
#: and nobody would be told.
SERVICE_ORDER: tuple[str, ...] = (
    "electric",
    "water",
    "gas",
    "sewer",
    "trash",
    "storm_water",
    "solar",
    "broadband",
    "thermal_heat",
    "battery",
    # CR-063 — the ELEVENTH service, APPENDED at position 11 (BR-RAT-024,
    # CONFIRMED-AS-AMENDED 2026-09-02). Nothing above it is renumbered.
    "fire",
)

#: BR-TEN-171 — service → the ratified rows, in the order the PO was shown them.
#: A service present with an EMPTY tuple has been RULED to have no size class; a
#: service absent from this map has not been ruled at all and must appear in
#: `UNBANDED_SERVICE_DIMENSIONS` instead.
RATIFIED_SERVICE_SIZE_CLASSES: dict[str, tuple[SizeClass, ...]] = {
    # ── ELECTRIC · six BANDS, ratified as put ────────────────────────────
    # ⚠ `E-3P` "Electric 3φ" IS NOT HERE AND THAT IS DELIBERATE (BR-TEN-171).
    # It was seeded from CR-004 until 2026-08-27; the ratified list names 3φ
    # 200A and 3φ 400A, and a bare 3φ with no amperage is neither. Dropping it
    # from the platform fixture means no NEW tenant receives it. BR-TEN-071
    # means nothing DELETES it from a tenant that already has it — the row
    # stays, deactivatable on S8 and never resurrected by a later sweep, which
    # is the only mechanism seed data has and is BR-TEN-072's posture reached
    # the long way round.
    #
    # An amperage is a SERVICE ENTRANCE RATING: a customer has one, it picks
    # which flat rate applies, and two of them do not add up to anything.
    "electric": (
        _band("E-1P-100", "Electric 1φ 100A"),
        _band("E-1P-200", "Electric 1φ 200A"),
        _band("E-1P-400", "Electric 1φ 400A"),
        _band("E-3P-200", "Electric 3φ 200A"),
        _band("E-3P-400", "Electric 3φ 400A"),
        _band("E-CT", "Electric CT-metered"),
    ),
    # ── WATER · nine BANDS, and this is the row the PO CORRECTED ─────────
    # *"Pipe diameter keep the four; add 1½" · 3" · 4" · 6" - you need 1 inch
    # 2 inch also 5 inch also"*. W-1 and W-2 were already seeded and are kept
    # (their codes and names are untouched — BR-TEN-072). **W-5 is the PO's own
    # addition and was NOT in the proposal**: it is the single figure on this
    # whole table that came from them rather than from the AWWA-convention list
    # a lane assembled, and it is called out here so a later reader does not
    # "tidy" the sequence back to a convention that never had it.
    "water": (
        _band("W-58", 'Water 5/8"'),
        _band("W-34", 'Water 3/4"'),
        _band("W-1", 'Water 1"'),
        _band("W-112", 'Water 1½"'),
        _band("W-2", 'Water 2"'),
        _band("W-3", 'Water 3"'),
        _band("W-4", 'Water 4"'),
        _band("W-5", 'Water 5"'),
        _band("W-6", 'Water 6"'),
    ),
    # ── GAS · four BANDS, by meter capacity in cubic feet per hour ───────
    # `G-250` keeps its EXISTING name, "(residential)" included. The ratified
    # table reads "250 · 425 · 630 · 1,000+ CFH" and tightening the seeded name
    # to match would be a rename, which BR-TEN-072 forbids in seed data and
    # BR-TEN-071 makes pointless anyway (a changed name reaches nobody).
    #
    # ⚠ A CFH figure is a METER'S THROUGHPUT RATING and not an installed
    # quantity: one connection has one meter, and `G-1000` is a range ("1,000+")
    # with no single value at all. It stays a band, and the PO's 2026-08-27
    # ruling says so in as many words — *"bands stay for pipe/amp/CFH"*.
    "gas": (
        _band("G-250", "Gas 250 CFH (residential)"),
        _band("G-425", "Gas 425 CFH"),
        _band("G-630", "Gas 630 CFH"),
        _band("G-1000", "Gas 1,000+ CFH"),
    ),
    # ── SEWER · NONE, BY RULING — not a gap ──────────────────────────────
    # Sewer is priced as a share of the WATER usage charge (BR-RAT-015, PO Q&A
    # R1 closing OQ-008) and reads no register of its own, so there is nothing
    # for a size class to size. Where a utility has a REAL sewer meter it
    # mirrors water's classes onto sewer by hand on S8 — which is why this is
    # an empty tuple (ruled: none by default) and not an absence.
    "sewer": (),
    # ── TRASH · seven BANDS — three carts and four dumpsters ─────────────
    # `CART-96` keeps its existing code and name.
    #
    # ⚠ **TRASH IS THE REASON `capacity` IS `None` AND NOT A NUMBER, AND IT IS
    # THE CASE THAT KEEPS THE TWO BILLING SHAPES APART (CR-062 D2).** PO
    # verbatim, statement (3), 2026-09-02: *"Trash - it is capacity based and
    # Cart sizes will decide price X how many Cart"*. The SIZE picks the rate
    # and the COUNT multiplies it — so what trash bills on is how MANY carts,
    # never how much they add up to.
    #
    # It is also arithmetically impossible to sum these: three of the seven are
    # CARTS measured in GALLONS and four are DUMPSTERS measured in CUBIC YARDS.
    # There is no unit in which "a 96-gallon cart plus a 4 cu-yd dumpster" is a
    # quantity. Giving these rows a number would invent one.
    "trash": (
        _band("CART-35", "Trash 35-gallon cart"),
        _band("CART-64", "Trash 64-gallon cart"),
        _band("CART-96", "Trash 96-gallon cart"),
        _band("DUMP-2", "Trash 2 cu-yd dumpster"),
        _band("DUMP-4", "Trash 4 cu-yd dumpster"),
        _band("DUMP-6", "Trash 6 cu-yd dumpster"),
        _band("DUMP-8", "Trash 8 cu-yd dumpster"),
    ),
    # ── STORM WATER · five CAPACITIES, in Equivalent Residential Units ───
    # ⚠ **THIS REPLACES A RATIFIED LIST AND IS A REVERSAL, NOT A TIDY-UP
    # (CR-062 A3, judgment 1).** `SW-1ERU` · `SW-2-5` · `SW-6-20` · `SW-20P`
    # were signed on 2026-08-27 and were **NOT** covered by the capacity-
    # multiplier ruling of that same day, which named only solar, battery and
    # thermal. Withdrawing them is therefore a genuine reversal of a signed
    # list. **The PO was shown the change explicitly on 2026-09-02, told they
    # could decline it, and said to execute** — statement (5): *"for panels you
    # will need various capacityes similarly the capacities we have created for
    # Trash cart - you need to do it for Solar, Battery and Strom water also"*,
    # and statement (3): *"Storm water - it is capacity based not unmetered ,
    # capaicyt is decided based on sizes of propoerty"*.
    #
    # Bands PICK a rate; capacities MULTIPLY one. A property assessed at 6 ERU
    # now bills 6 × the per-ERU rate instead of landing in a "6–20" bucket that
    # charges a 6 ERU school the same as a 20 ERU mall.
    #
    # ⚠ The names deliberately carry no "Storm water" prefix — see the module
    # docstring, where the BR-TEN-078 cost of that is stated in full.
    "storm_water": (
        _capacity("SW-SF", "Single-family home", 1, "ERU"),
        _capacity("SW-DUP", "Two-unit home", 2, "ERU"),
        # ⊕ PO ruling 2026-10-03 (decision log, option A), verbatim: *"A Keep
        # charging per unit, and add a size for a single flat, e.g. "Flat" = 2
        # ERU"*. Storm water is charged PER UNIT, and until this row a clerk
        # sizing one flat of a block could only pick *Apartment building* — the
        # whole building's 6 ERU on every flat (3 flats × 6 × $4.50 = $81.00
        # where 3 × 2 × $4.50 = $27.00). A SEEDED DEFAULT a utility edits on
        # Settings, like every row here — not signed law. Existing tenants whose
        # storm-water list is still untouched receive it from
        # `tenancy/0058`; the sweep does not deliver this list (discretionary).
        _capacity("SW-FLAT", "Flat", 2, "ERU"),
        _capacity("SW-APT", "Apartment building", 6, "ERU"),
        _capacity("SW-COM-S", "Small commercial", 4, "ERU"),
        _capacity("SW-COM-L", "Large commercial", 10, "ERU"),
    ),
    # ── SOLAR · ten CAPACITIES, one panel type per kilowatt ──────────────
    # ⚠ **THE FOUR INVERTER BANDS ARE WITHDRAWN HERE AND THIS PAYS A DEBT THE
    # FILE ITSELF RECORDED (CR-062 A4).** `SOL-5` · `SOL-5-10` · `SOL-10-25` ·
    # `SOL-25P` were ratified on 2026-08-27 and **superseded by a ruling the PO
    # made the same day**, and they were never removed. This file said so in its
    # own words — *"the supersession stands and is owed"* — because withdrawing
    # them is a reversal of signed figures with a fixture bump behind it, which
    # was a piece of work in its own right rather than a side effect of the
    # battery fix that noticed it. **CR-062 is that piece of work.**
    #
    # PO verbatim, 2026-08-27: *"(a) multiplier replaces bands for capacity
    # services (solar, battery, thermal); bands stay for pipe/amp/CFH - this si
    # corect"*. Statement (6) of 2026-09-02 is the same ruling said a second
    # time with a worked example, and it is what fixes the count at ten:
    # *"We have 10 Types of Solar panel with various capaity 1 Kw, 2Kw 3Kw 4Kw
    # so and SO forth"*.
    #
    # ⚠ `panel` IS NOT A UNIT OF THIS SERVICE. The PO approved counting panels
    # on 2026-09-02 (statement 4) and CORRECTED IT in statement (6) of the same
    # conversation: panels come in different sizes, so counting them loses the
    # thing being sold. Solar's unit is `kW` and `panel` is never added to the
    # UoM catalogue.
    "solar": (
        _capacity("SOL-P1", "Solar panel 1 kW", 1, "kW"),
        _capacity("SOL-P2", "Solar panel 2 kW", 2, "kW"),
        _capacity("SOL-P3", "Solar panel 3 kW", 3, "kW"),
        _capacity("SOL-P4", "Solar panel 4 kW", 4, "kW"),
        _capacity("SOL-P5", "Solar panel 5 kW", 5, "kW"),
        _capacity("SOL-P6", "Solar panel 6 kW", 6, "kW"),
        _capacity("SOL-P7", "Solar panel 7 kW", 7, "kW"),
        _capacity("SOL-P8", "Solar panel 8 kW", 8, "kW"),
        _capacity("SOL-P9", "Solar panel 9 kW", 9, "kW"),
        _capacity("SOL-P10", "Solar panel 10 kW", 10, "kW"),
    ),
    # ── BROADBAND · three CAPACITIES, by the tier bought ─────────────────
    # ⚠ **THE CODES, NAMES AND COUNT ARE UNCHANGED — ONLY THE NUMBER IS NEW,
    # AND IT IS TRANSCRIBED RATHER THAN CHOSEN.** These three rows have always
    # STATED their capacity inside their own display names ("Broadband 100
    # Mbps"), so writing `100` beside the label invents no figure and reverses
    # no signed one; it makes a number the product could only read as English
    # into one it can add up. CR-062 D1 lists broadband among the services
    # billed on the SUM of installed capacity, so leaving it label-only would
    # have left that task unable to do its arithmetic — built, and not wired.
    "broadband": (
        _capacity("BB-100", "Broadband 100 Mbps", 100, "Mbps"),
        _capacity("BB-500", "Broadband 500 Mbps", 500, "Mbps"),
        _capacity("BB-1000", "Broadband 1,000 Mbps", 1000, "Mbps"),
    ),
    # ── THERMAL / HEAT · eight CAPACITIES IN CONNECTED TONS — CR-080 ────
    # ⚠ **THE THREE `TH-CW-*` BANDS ARE WITHDRAWN HERE AND THIS PAYS THE LAST
    # OF THE 2026-08-27 DEBT.** `TH-CW-25` *"≤25 tons"* · `TH-CW-25-100`
    # *"25–100 tons"* · `TH-CW-100P` *"100+ tons"* were ratified on 2026-08-27
    # and **superseded by a ruling the PO made the same day**, and this file
    # recorded the omission in its own words for six days — *"the debt solar
    # just paid, thermal still owes"*. `CR-080` is the piece of work that pays
    # it. PO verbatim, 2026-08-27: *"(a) multiplier replaces bands for capacity
    # services (solar, battery, thermal); bands stay for pipe/amp/CFH - this si
    # corect"*, and again on 2026-09-07: *"connected tonnage - it is capacity
    # not metering; i will ahve 100 tonne or 200 tonne etc"*.
    #
    # ⚠ **THE TWO REASONS THIS FILE GAVE FOR NOT WITHDRAWING THEM ARE BOTH
    # ANSWERED, AND ONE OF THEM WAS ALWAYS THE ARGUMENT FOR WITHDRAWING.**
    # (1) *"CR-062 bills thermal as a METERED service, so it is not priced on
    # installed capacity"* — the 2026-09-07 ruling reverses exactly that, and
    # `SERVICE_DEFAULT_UOMS["thermal_heat"]` is `capacity` in `ton` now.
    # (2) *"each of these three rows is a RANGE — ≤25 tons, 25–100 — which has
    # no single value a capacity could be"* — true, and it is the reason a
    # range CANNOT survive the ruling rather than a reason to keep it. A
    # capacity is a number you multiply; *"25–100"* is not one.
    #
    # ⚠ **IT SUMS, LIKE SOLAR AND BATTERY — IT DOES NOT COUNT LIKE TRASH AND
    # FIRE.** *"Multiplier replaces bands"* is the summing shape, and connected
    # tonnage adds up in a way a pipe diameter does not: a building with a
    # 100-ton connection and a 25-ton connection has **125 tons** of connected
    # capacity, and 125 × the per-ton rate is what it owes. The mechanical
    # test, which a later reader should trust over this comment:
    # `capacity_uom_for_service("thermal_heat")` answers `"ton"`. If it ever
    # answers `None`, thermal has been turned back into bands and the CR-080
    # suite goes red — which is the conversation that should happen first.
    #
    # ⚠ **`ton` IS THE REFRIGERATION TON (12,000 BTU/hr), NOT THE METRIC
    # TONNE, AND THE READING IS RECORDED SO THE PO CAN CORRECT IT IN A WORD.**
    # The PO wrote *"tonne"*. The three withdrawn rows above already said
    # *"tons"*, and a North American chilled-water utility measures in
    # refrigeration tons — the City of Mesa's district-cooling rate book
    # defines a Ton-Hour as 12,000 BTU and bills a monthly charge on a
    # *"Rated-Ton"*. If the PO meant 1,000 kg of anything, this ladder and the
    # seeded price both move and nothing else does.
    #
    # ⚠ **THE EIGHT VALUES ARE THIS LANE'S PROPOSAL, NOT A RATIFIED LADDER, AND
    # THE PO HAS SEEN NEITHER THEM NOR THE PRICE BESIDE THEM.** They are what
    # the PO's own *"100 tonne or 200 tonne etc"* invites — the two figures
    # they named are here by name, and the *"etc"* is filled in as a doubling
    # ladder from a small commercial bay (5 tons) to a hospital plant
    # (800 tons), which is how equipment catalogues are actually shaped.
    # **25 and 100 are deliberately kept**: they were the boundaries of the
    # three withdrawn ranges, so a tenant reading its own list sees the numbers
    # it already had, now as capacities it can multiply.
    #
    # **They are seeded DEFAULTS a tenant edits on Settings → Service sizes**,
    # which is what a seed is for — the same posture as fire's six (`OQ-1360`).
    # No screen, document or report may present them as anybody's tariff.
    #
    # ⚠ **THE DISPLAY NAMES SAY "chilled water" AND THAT IS NOT DECORATION.**
    # Thermal was put to the PO as TWO dimensions; only chilled water was ever
    # banded. **Steam is still `OQ-560` and `steam_size_classes()` still
    # raises** — a row reading *"Thermal 100 tons"* would imply this list
    # covers thermal, and it covers half of it. `CR-080` moved the BASIS of the
    # whole service and settled nothing about steam's boundaries.
    "thermal_heat": (
        _capacity("TH-T5", "Thermal chilled water 5 tons", 5, "ton"),
        _capacity("TH-T10", "Thermal chilled water 10 tons", 10, "ton"),
        _capacity("TH-T25", "Thermal chilled water 25 tons", 25, "ton"),
        _capacity("TH-T50", "Thermal chilled water 50 tons", 50, "ton"),
        _capacity("TH-T100", "Thermal chilled water 100 tons", 100, "ton"),
        _capacity("TH-T200", "Thermal chilled water 200 tons", 200, "ton"),
        _capacity("TH-T400", "Thermal chilled water 400 tons", 400, "ton"),
        _capacity("TH-T800", "Thermal chilled water 800 tons", 800, "ton"),
        # ⚠ `TH-CW-25` · `TH-CW-25-100` · `TH-CW-100P` WERE HERE AND ARE
        # WITHDRAWN (`CR-080`, 2026-09-07). Named in this absence for the
        # reason `HYD` is named in fire's: eight capacities read as a complete
        # ladder, so nothing in the code would tell the next lane that three
        # rows were taken out, and all three are still cited across the
        # register. `BR-TEN-071` deletes them from NOBODY — a tenant that
        # already holds them keeps them and may deactivate them on S8; the
        # withdrawal means no NEW tenant receives them, exactly as `E-3P`,
        # solar's four inverter bands and storm water's four ERU bands.
    ),
    # ── BATTERY · six CAPACITIES — and this is NOT a set of bands ────────
    # ⚠ **READ THIS BEFORE CONCLUDING THAT A DISSOLVED QUESTION WAS REOPENED.**
    # Battery answered `()` — *"ruled to have none"* — from 2026-09-01 until
    # CR-062, because the PO **DISSOLVED** `OQ-561` on 2026-08-27 rather than
    # answering it: *"there are no kW boundaries to state, because battery is
    # not banded at all"*. PO verbatim: *"(a) multiplier replaces bands for
    # capacity services (solar, battery, thermal); bands stay for pipe/amp/CFH
    # - this si corect"*.
    #
    # **THAT RULING IS STILL TRUE AND THESE SIX ROWS DO NOT CONTRADICT IT.**
    # `OQ-561` asked WHERE ONE BAND ENDS — which is a question about price
    # boundaries, and none of these six states one. Nobody is being asked where
    # one price stops and the next begins; every battery is billed at the same
    # per-kW rate and these rows say only what capacities a utility can install.
    # **They are a CATALOGUE OF EQUIPMENT, which is what the PO asked for on
    # 2026-09-02** — *"the capacities we have created for Trash cart - you need
    # to do it for Solar, Battery and Strom water also"* — and it is the same
    # ruling read forward, not reversed.
    #
    # The mechanical test, and it is the one a later reader should trust over
    # any comment: `capacity_uom_for_service("battery")` answers `"kW"`. A BAND
    # service answers `None`, because it does not sum. If these six ever become
    # bands again that call flips and the CR-062 suite goes red, which is the
    # conversation that should happen before it ships.
    #
    # ⚠ `DEF-2408` is the five days when the dissolution had reached the
    # register and not this file, and a battery account could not be billed AT
    # ALL — `gather_account` raised `SizeClassNotRuled("OQ-561")` on the first
    # account of every battery run. Kept in view because the failure mode is
    # general: nothing in this repo re-reads a CLOSED open question against the
    # code that still cites it.
    "battery": (
        _capacity("BAT-5", "Battery 5 kW", 5, "kW"),
        _capacity("BAT-10", "Battery 10 kW", 10, "kW"),
        _capacity("BAT-15", "Battery 15 kW", 15, "kW"),
        _capacity("BAT-20", "Battery 20 kW", 20, "kW"),
        _capacity("BAT-25", "Battery 25 kW", 25, "kW"),
        _capacity("BAT-30", "Battery 30 kW", 30, "kW"),
    ),
    # ── FIRE · six BANDS — six line diameters, and NO hydrant ────────────
    # ⚠ **A PRIVATE HYDRANT WAS THE SEVENTH ROW UNTIL 2026-09-03 AND THE PO
    # TOOK IT OUT. DO NOT PUT IT BACK.** PO verbatim, 2026-09-03: *"remove
    # private hydrants from list"*, answering the narrow question put to them
    # after their earlier ruling *"we rnable fire line right now , hydrants are
    # assets not utility service as of now"*. `HYD` "Private hydrant", priced
    # `$25.0000`, is withdrawn; fire's list goes **7 → 6**.
    #
    # ⚠ **IT SUPERSEDES A WORKED FIGURE THAT WAS SIGNED THE DAY BEFORE**, which
    # is why the supersession is stated here rather than left to be inferred.
    # `CR-063` was approved on 2026-09-02 with the example *"a warehouse with a
    # 6-inch line and two private hydrants is charged `$60.00` for the line plus
    # `$25.00` for each hydrant — `$110.00` in total, printed as two separate
    # lines"*. **That warehouse now bills `$60.00`** — `−$50.00` a month on that
    # customer. Nothing was wrong with the arithmetic: the PO decided a hydrant
    # is not a thing this product bills as a utility service.
    #
    # **A HYDRANT DOES NOT DISAPPEAR — IT MOVES SURFACE.** The PO's framing is
    # *"assets not utility service"*, so a private hydrant is equipment recorded
    # against a premises. `OQ-1361` is HALF answered — the hydrant half is
    # ruled, the fire-LINE half stands — and it stays OPEN for that half. A
    # utility that wants to charge for hydrants is not blocked: `BR-TEN-036`
    # lets a tenant add its own charge code, and the seeded `HYDRANT` charge
    # code (hydrant meter rental, GL `4630`) is a DIFFERENT thing and is
    # untouched. What is removed is the PLATFORM's claim that a hydrant is a
    # fire-service size.
    #
    # ⚠ **NOTHING ALREADY ISSUED IS REWRITTEN** (CLAUDE.md hard rule 4), and
    # `BR-TEN-071` deletes nothing: a tenant that already holds `HYD` keeps it
    # and can deactivate it on S8. The withdrawal means no NEW tenant receives
    # it — the same posture `E-3P` and `CR-062`'s eight withdrawn rows carry.
    #
    # ⚠ **THESE SIX ARE STILL THE ONLY ROWS ON THIS TABLE THE PRODUCT OWNER HAS
    # NEVER SEEN AS A PRICE LIST, AND NOTHING ELSE IN THIS FILE IS LIKE THEM.
    # READ THAT BEFORE CITING ONE.** Every other list here was put to the PO and
    # ruled; these were AUTHORED BY THE `CR-063` LANE as a plausible AWWA-shaped
    # ladder. **The going-live customer's real sizes are a fact only they hold —
    # `OQ-1360`, OPEN.** The 2026-09-03 ruling does NOT close it: the PO removed
    # a row, they did not ratify the six that remain or the amounts beside them.
    #
    # **THE BUILD DOES NOT WAIT ON THAT AND MUST NOT.** A seeded default a
    # tenant edits on Settings -> Service sizes is exactly what a seed is FOR,
    # and blocking the eleventh service on the customer's own list would block
    # the customer on themselves. What the openness FORBIDS is presenting these
    # six as anybody's tariff: no screen, document or report may do so until
    # `OQ-1360` is answered.
    #
    # ⚠ **BANDS, NOT CAPACITIES — THIS IS THE WHOLE OF *"EXACTLY LIKE TRASH"*
    # AND GETTING IT WRONG PRICES FIRE WRONGLY WITH NOTHING GOING RED.** PO
    # verbatim, 2026-09-02: *"We will need Fire as utility Service - Capacity
    # based - this will behave exactly like trash"*. Since `CR-062` this file
    # holds two different arithmetics under the one word *capacity*: trash
    # COUNTS what is installed and solar SUMS it. Fire COUNTS. So the size class
    # PICKS the price and the count MULTIPLIES it, `BR-RAT-090` unchanged:
    #
    #     one 2" line                     ->  1 x $12.00              = $12.00
    #     one 6" line + two 2" lines      ->  $60.00 + 2 x $12.00     = $84.00
    #
    # ⚠ **THE SECOND EXAMPLE USED TO BE THE HYDRANT WAREHOUSE AND IS NOW TWO
    # DIAMETERS**, because the per-size arithmetic is what it illustrates and
    # that mechanism is untouched by the 2026-09-03 ruling: a property with more
    # than one size still bills ONE LINE PER SIZE. The hydrant warehouse itself
    # is now a single 6" line at `$60.00`.
    #
    # It is also arithmetically forced, for trash's own reason: **there is no
    # unit in which "a 6-inch fire line plus a 2-inch fire line" is a
    # quantity** — 8 inches is not a thing anybody sells.
    # Giving these rows a number would invent one. The mechanical test, which a
    # later reader should trust over this comment:
    # `capacity_uom_for_service("fire")` answers `None`, and
    # `total_capacity("fire", ...)` RAISES `NotACapacityService`.
    #
    # A diameter is a SERVICE CONNECTION RATING: a customer's line has one, it
    # picks which flat monthly price applies, and two of them do not add up to
    # anything — the same argument electric's amperages and water's pipe
    # diameters carry a few hundred lines above.
    "fire": (
        _band("FL-2", 'Fire line 2"'),
        _band("FL-4", 'Fire line 4"'),
        _band("FL-6", 'Fire line 6"'),
        _band("FL-8", 'Fire line 8"'),
        _band("FL-10", 'Fire line 10"'),
        _band("FL-12", 'Fire line 12"'),
        # ⚠ `HYD` "Private hydrant" WAS HERE AND WAS REMOVED BY PO RULING ON
        # 2026-09-03 — *"remove private hydrants from list"*. It is named in
        # this absence deliberately: fire's six read as a complete diameter
        # ladder, so nothing in the code would tell the next lane a row was
        # taken out, and the seventh is still cited across the register.
    ),
}

#: **THE SEEDED DEFAULT MONTHLY PRICE FOR EACH OF FIRE'S SIX SIZES — `CR-063`
#: step 5 as amended by the PO ruling of 2026-09-03, and `OQ-1360` is the
#: question it answers provisionally.**
#:
#: ⚠ **`HYD` "Private hydrant" AT `$25.0000` WAS THE SEVENTH ENTRY AND IS GONE
#: — PO 2026-09-03, *"remove private hydrants from list"*.** The list above
#: carries the ruling and its supersession chain; this table follows it, and
#: the two move together on purpose (see the next paragraph).
#:
#: ⚠ **THIS IS THE ONLY PRICE LIST IN THIS MODULE AND IT IS HERE ON PURPOSE.**
#: `service_size_classes.py` otherwise holds no money at all, and the reason it
#: holds this is that Fire's sizes and Fire's prices are ONE unratified
#: statement: the six rows above are meaningless to a utility without an
#: amount beside them, and splitting them across two files would let one move
#: without the other. They are seeded together and they are questioned
#: together — **and on 2026-09-03 they were WITHDRAWN together, which is the
#: first time that argument was tested and is why it is worth keeping.**
#:
#: ⚠ **NOT SIGNED, NOT FROZEN, NOT B4/B5 — AND NOT TO BE TREATED AS ANY OF
#: THOSE.** No finance signature covers a figure here. `GT-17`'s water `$39.50`
#: and sewer `$15.80` are untouched by every one of them, because Fire is new
#: money on new lines and changes no existing one.
#:
#: **Worked, and all three figures are asserted by `test_cr063_fire_service.py`
#: — RED on the code that preceded them:**
#:
#:     fire_charge({"FL-2": 1})               == Decimal("12.00")
#:     fire_charge({"FL-6": 1})               == Decimal("60.00")    # the warehouse
#:     fire_charge({"FL-6": 1, "FL-2": 2})    == Decimal("84.00")    # two sizes
#:
#: ⚠ **THE SECOND LINE USED TO READ `fire_charge({"FL-6": 1, "HYD": 2}) ==
#: Decimal("110.00")` AND IT IS THE FIGURE THE 2026-09-03 RULING MOVED.** Same
#: customer, same 6" line, `−$50.00` a month. It is kept in view here rather
#: than deleted quietly, because `$110.00` is quoted across the register and a
#: reader who meets it needs to know which side of the ruling they are on.
#:
#: Stored to 4 decimal places and DISPLAYED to 2 (CLAUDE.md hard rule 2); built
#: from strings and never floats, because these numbers get multiplied.
FIRE_DEFAULT_PRICES: dict[str, Decimal] = {
    "FL-2": Decimal("12.0000"),
    "FL-4": Decimal("30.0000"),
    "FL-6": Decimal("60.0000"),
    "FL-8": Decimal("100.0000"),
    "FL-10": Decimal("160.0000"),
    "FL-12": Decimal("230.0000"),
    # ⚠ `"HYD": Decimal("25.0000")` WAS HERE — withdrawn 2026-09-03 with the
    # size row it priced. A price with no size class is refused by
    # `fire_charge` anyway, so the two must never be separated.
}

#: The dimensions the PO was shown WITHOUT boundaries. Absence from
#: `RATIFIED_SERVICE_SIZE_CLASSES` is what makes a lookup RAISE instead of
#: returning an empty tuple, and this register is why: an empty tuple means
#: "ruled to have none" (sewer) and a raise means "nobody has said" (steam).
#: The two readings must never collapse into each other, because one is a
#: finished decision and the other is money nobody has priced.
#:
#: ⚠ **BATTERY LEFT THIS REGISTER ON 2026-09-01 (`DEF-2408`) AND IS NOT COMING
#: BACK.** `OQ-561` was DISSOLVED, and CR-062 then gave battery a CATALOGUE OF
#: CAPACITIES rather than the bands the dissolved question was about — see the
#: long note on the `battery` entry above. It is named here because this
#: register's whole job is to keep *"nobody has said"* apart from *"ruled to
#: have none"*, and battery has now been all three things in six days.
UNBANDED_SERVICE_DIMENSIONS: dict[str, tuple[str, str]] = {
    "thermal_heat_steam": (
        "OQ-560",
        'the proposal said only "steam by thousand pounds per hour", which names '
        "the UNIT and no boundary. Thermal's OTHER dimension, chilled water, WAS "
        "banded (≤25 · 25–100 · 100+ tons) and is seeded — so thermal is half "
        "ruled, and this is the half that is not.",
    ),
}


class SizeClassNotRuled(NotImplementedError):
    """Raised when something asks for bands the Product Owner never saw.

    A `NotImplementedError` subclass on purpose: the prime directive asks for
    `NotImplementedError("OQ-###")` at an unruled boundary, G8 reads the OQ-ID
    out of the message, and a caller that wants to tell "not ruled yet" apart
    from "not built yet" can still catch this by type.
    """


class NotACapacityService(TypeError):
    """Raised when something asks a BANDED service for a summable total.

    A `TypeError` on purpose, and deliberately NOT a `SizeClassNotRuled`: this
    is not an unruled boundary that a later PO answer could fill in, it is an
    operation the data does not support and never will. Trash's carts are
    gallons and its dumpsters are cubic yards; water's rows are pipe diameters.
    Adding either set up produces a number with no meaning, so the only correct
    answer is to refuse.

    It is also not caught by the seam wrappers in `assets` and `metering`, which
    narrow their `except` to `SizeClassNotRuled` and `KeyError` — so a caller
    that reaches here has a bug and will hear about it.
    """


def _validate_ratified_rows() -> None:
    """The three import-time invariants named in the module docstring.

    Run at import so a bad edit fails LOUDLY AND IMMEDIATELY — every test in the
    process stops on the same message — instead of shipping a plausible wrong
    total that only shows up as money months later. A capacity is the one field
    here that gets multiplied by a price, so it is worth the microseconds.
    """
    for service, rows in RATIFIED_SERVICE_SIZE_CLASSES.items():
        if service not in SERVICE_ORDER:
            raise ValueError(
                f"{service!r} carries size classes but is not one of the eleven "
                f"utility services ({', '.join(SERVICE_ORDER)}) — see BR-RAT-024"
            )
        # 1 · a quantity never travels without its unit (CLAUDE.md hard rule 3),
        #     and a unit never travels without its quantity either. The second
        #     direction is the one a reader would not think to check.
        for row in rows:
            if (row.capacity is None) != (row.capacity_uom is None):
                raise ValueError(
                    f"{row.code} carries one half of a quantity — "
                    f"capacity={row.capacity!r} unit={row.capacity_uom!r}. "
                    "CLAUDE.md hard rule 3: a quantity always carries an "
                    "explicit unit, and a unit is meaningless without one."
                )
            if row.capacity is not None and row.capacity <= 0:
                raise ValueError(
                    f"{row.code} has a capacity of {row.capacity} — a size class "
                    "that is installed must be a positive quantity"
                )
        if not rows:
            continue
        # 2 · a service is billed on a SUM or on a BAND. Never on both: mixing
        #     them would mean one customer's size multiplies and another's
        #     picks, on the same service, with nothing recording which.
        kinds = {row.is_capacity for row in rows}
        if len(kinds) != 1:
            bands = sorted(r.code for r in rows if r.is_band)
            caps = sorted(r.code for r in rows if r.is_capacity)
            raise ValueError(
                f"{service} mixes bands {bands} with capacities {caps}. "
                "A service is sized by one or the other — a band picks a rate, "
                "a capacity multiplies one — and no row records which a given "
                "customer got."
            )
        # 3 · one service, one unit. You cannot add kW to Mbps, and a total
        #     assembled from two units is a number with no meaning at all.
        units = {row.capacity_uom for row in rows if row.is_capacity}
        if len(units) > 1:
            raise ValueError(
                f"{service} sums in more than one unit ({sorted(units)}). "
                "A total across two units is not a quantity."
            )


_validate_ratified_rows()


def size_class_records_for_service(service_code: str) -> tuple[SizeClass, ...]:
    """The FULL ratified rows for one utility service — capacity included.

    This is the whole record and it is what CR-062 added the fields for. Use it
    whenever the NUMBER matters; `size_classes_for_service` below is the
    narrower `(code, name)` view for callers that only ever needed the label.

    Answers exactly as `size_classes_for_service` does at the three boundaries:
    an EMPTY TUPLE for a service ruled to have no size class (sewer), a RAISE
    for a dimension whose bands were never put to the PO (thermal steam), and a
    `KeyError` for a code that is not one of the eleven services.
    """
    if service_code in RATIFIED_SERVICE_SIZE_CLASSES:
        return RATIFIED_SERVICE_SIZE_CLASSES[service_code]
    if service_code in UNBANDED_SERVICE_DIMENSIONS:
        oq, why = UNBANDED_SERVICE_DIMENSIONS[service_code]
        raise SizeClassNotRuled(f"{oq} — {service_code} size bands are not ruled: {why}")
    raise KeyError(
        f"{service_code!r} is not one of the eleven utility services "
        f"({', '.join(SERVICE_ORDER)}) — see CLAUDE.md and BR-RAT-024"
    )


def size_classes_for_service(service_code: str) -> tuple[tuple[str, str], ...]:
    """The ratified `(code, name)` rows for one utility service.

    Returns an EMPTY TUPLE for a service ruled to have no size class (sewer),
    and RAISES for a service whose bands were never put to the PO. Those two
    answers are different facts and this function keeps them different.

    ⚠ **THIS IS A DERIVED VIEW OF `size_class_records_for_service`, NOT A
    SECOND SOURCE** (hard-won law 5: one source, derive views on demand). It
    exists because most callers genuinely only want the label — a downloadable
    template's sample cell, a seeded demo row, the flat `{code, name}` fixture —
    and widening all of them to carry a number they never read would be noise.

    ⚠ **IT CANNOT TELL YOU WHETHER A ROW IS A BAND OR A CAPACITY, AND THAT
    MATTERS FOR PRICING.** Ask `capacity_uom_for_service()` before treating any
    of these rows as a rate axis — see the H4 note in the module docstring for
    what happens to a solar bill if you do not.
    """
    return tuple((row.code, row.name) for row in size_class_records_for_service(service_code))


def capacity_uom_for_service(service_code: str) -> str | None:
    """The unit a service's size classes SUM in, or `None` when they do not sum.

    **This is the one call that tells the two billing shapes apart**, and it is
    deliberately the cheapest thing in this module to ask:

        "solar"   -> "kW"    the billable quantity is the SUM of what is installed
        "trash"   -> None    the billable quantity is the COUNT of what is installed
        "water"   -> None    the band picks a rate; nothing is summed at all
        "sewer"   -> None    ruled to have no size class

    A `None` therefore means *"do not sum these"* and never *"sum them in some
    default unit"* — there is no default, by CLAUDE.md hard rule 3.
    """
    rows = size_class_records_for_service(service_code)
    for row in rows:
        if row.is_capacity:
            return row.capacity_uom
    return None


def capacity_of(
    service_code: str,
    size_class_code: str,
    capacities: "Mapping[str, Decimal] | None" = None,
) -> Decimal:
    """How much one size class IS, as a number, for a capacity service.

    Raises `NotACapacityService` for a banded service — see that class for why
    refusing is the only correct answer — and `KeyError` for a code this service
    does not have. The second one matters more than it looks: solar and battery
    both sum in `kW`, so a battery code slipped into a solar total would
    otherwise produce a plausible, silent, wrong number.

    ⊕ **`DEF-RAT-10220` (PO 2026-10-17) — THE TENANT'S OWN ROW IS THE TRUTH.**
    `capacities` is THIS tenant's size-class rows for THIS service, as
    `{code.casefold(): capacity}` (`tenancy.selectors.size_class_capacities`).
    A code found there answers from the row — built-in or tenant-added alike,
    because the built-in rows carry the ladder's figure in the same column
    (seeded by `ServiceSizeClassLookupHandler.seed`, back-filled by
    `tenancy/0064`). PO, verbatim: *"do not hard code anything … it should able
    to handle dyanmic capacities and calcualte based on logic"*.

    **The ladder below is the SEED SOURCE and answers only where the tenant
    holds NO row with a capacity for the code** — a tenant provisioned before
    the list carried the service, or a test that never seeded the list. A row
    always wins over it. A code in neither place still raises `KeyError`:
    never guess, never read a number out of a name.
    """
    if capacities:
        own = capacities.get(str(size_class_code).strip().casefold())
        if own is not None:
            if capacity_uom_for_service(service_code) is None:
                raise NotACapacityService(
                    f"{service_code} is sized by BANDS; a capacity on one of its "
                    "rows is not a quantity this service sums."
                )
            return Decimal(own).quantize(CAPACITY_EXPONENT)
    rows = size_class_records_for_service(service_code)
    uom = capacity_uom_for_service(service_code)
    if uom is None:
        raise NotACapacityService(
            f"{service_code} is sized by BANDS, which are labels rather than "
            "quantities, so no size class of it has a capacity to report. "
            "See `capacity_uom_for_service`."
        )
    for row in rows:
        if row.code == size_class_code:
            assert row.capacity is not None  # invariant 2, checked at import
            return row.capacity
    raise KeyError(
        f"{size_class_code!r} is not a ratified size class of {service_code!r} "
        f"({', '.join(row.code for row in rows)})"
    )


def total_capacity(
    service_code: str,
    size_class_codes,
    capacities: "Mapping[str, Decimal] | None" = None,
) -> Decimal:
    """**The sum of installed capacity — the quantity a capacity service bills.**

    The Product Owner's own example, 2026-09-02: three panels of 2 kW, 4 kW and
    8 kW on one unit are **14 kW**, so

        total_capacity("solar", ["SOL-P2", "SOL-P4", "SOL-P8"]) == Decimal("14")

    and at their rate of $14.00 per kW that bills **$196.00**. (Their message
    reads *"14 X 14 = 156 $"*; 14 × 14 is 196. They were told so in the same
    session and did not dispute it, and $156 appears nowhere in this repo.)

    ⚠ **THE PRICE IS NOT THIS FUNCTION'S BUSINESS AND IS DELIBERATELY ABSENT.**
    This returns a QUANTITY WITH NO MONEY IN IT — rating multiplies it by a rate
    it resolves for itself. Keeping the money out is what lets this live in
    tenancy beside the ratified law it reads, rather than becoming a second
    place where a bill is computed.

    Refuses rather than answers in two cases, both of which would otherwise
    produce a plausible wrong number:

      * a BANDED service (`NotACapacityService`) — trash counts its carts, it
        does not add them up, and its gallons and cubic yards cannot be summed
        in any unit at all;
      * a code belonging to some other service (`KeyError`) — solar and battery
        both sum in `kW`, so this one would be silent.

    An empty list sums to `Decimal("0.0000")`, which is a real answer and not a
    gap: a unit with no panels on it has no installed capacity, and BR-MET-108's
    ruled zero says that bills as `$0.00` rather than refusing.

    `capacities` — the tenant's own rows, which win (`capacity_of`,
    `DEF-RAT-10220`): 47.84 kW on a tenant-added size plus the built-in 10 kW
    is **57.84 kW**, and at $14.00 per kW that bills **$809.76**.
    """
    codes = list(size_class_codes)
    uom = capacity_uom_for_service(service_code)
    if uom is None:
        raise NotACapacityService(
            f"{service_code} is sized by BANDS, so its size classes cannot be "
            "added together. A band picks a rate; only a capacity multiplies "
            "one. If you meant how MANY were installed, that is a count and "
            "this is not the function for it."
        )
    total = Decimal(0)
    for code in codes:
        total += capacity_of(service_code, code, capacities)
    return total.quantize(CAPACITY_EXPONENT)


def fire_charge(counts, prices: "dict[str, Decimal] | None" = None) -> Decimal:
    """**What a unit's fire equipment costs a month — `CR-063`, `BR-RAT-090`.**

    `counts` maps a fire size-class code to HOW MANY of that size stand on the
    unit. The charge is the sum, over the sizes present, of `count x the price
    for that size` — which is trash's arithmetic and not solar's:

        fire_charge({"FL-2": 1})             == Decimal("12.00")
        fire_charge({"FL-6": 1})             == Decimal("60.00")   # the warehouse
        fire_charge({"FL-6": 1, "FL-2": 2})  == Decimal("84.00")   # 60 + 2 x 12

    ⚠ **`fire_charge({"FL-6": 1, "HYD": 2})` USED TO ANSWER `$110.00` AND NOW
    RAISES `KeyError`** — PO 2026-09-03, *"remove private hydrants from list"*.
    That is the refusal below doing its job, not a regression: `HYD` is no
    longer a fire size class, and a code this list does not hold is a typo. The
    warehouse the `$110.00` named bills `$60.00` for its 6" line, and its two
    hydrants are equipment on file rather than money on a bill.

    ⚠ **THIS IS THE PRICE-LIST ARITHMETIC AND IT IS NOT THE BILL RUN.** The
    engine prices a bill through `apps.rating.resolution`, which resolves ONE
    size per connection and multiplies the observed asset COUNT by the amount
    R4 returns for that size. This function is what the SEED and the SETTINGS
    screen are worth per month, stated once so the two ratified figures have a
    single home instead of being retyped into a test. Where the two must agree,
    a test asserts them against each other rather than trusting the comment.
    ⚠ And note what the engine does with the THIRD example: a 6" line and two
    2" lines on ONE connection are two different recorded sizes, which
    `metering.connection_size_for` answers `None` for BY DESIGN — *"one
    connection has one size"* — so that property bills as two priced groups and
    not as one line. **`DEF-3093` records it, filed before this function was
    written rather than after** (CLAUDE.md law W). **The 2026-09-03 hydrant
    ruling did not touch this**: the mixed-size property is now two DIAMETERS
    rather than a line and two hydrants, and the per-size grouping is the same
    mechanism on the same code path.

    ⚠ **`prices` DEFAULTS TO `FIRE_DEFAULT_PRICES`, WHICH ARE SEEDED DEFAULTS
    AND NOT ANYBODY'S TARIFF** (`OQ-1360`). A caller pricing a REAL tenant must
    pass that tenant's own amounts: the seed is what a utility STARTS with on
    Settings -> Service sizes, and the going-live customer types their own.

    Refuses rather than answers in two cases, both of which would otherwise
    produce a plausible wrong number:

      * a size code fire does not have (`KeyError`) — a typo'd `FL-3` silently
        skipped is a fire line billed at nothing;
      * a negative count (`ValueError`) — a number of physical things cannot be
        below zero, and it would price as a credit nobody authorised.

    An empty mapping is `Decimal("0.00")`, which is a real answer and not a gap:
    a unit with no fire equipment owes nothing for fire. It is `BR-RAT-090`'s
    own distinction — *"'no carts recorded' and 'zero carts' are different facts
    and only one of them is billable"* — and the ABSENT case is the caller's to
    refuse, exactly as `counted_quantity` refuses a `None` count.
    """
    table = FIRE_DEFAULT_PRICES if prices is None else prices
    ratified = {row.code for row in RATIFIED_SERVICE_SIZE_CLASSES["fire"]}
    total = Decimal(0)
    for code, count in dict(counts).items():
        if code not in ratified:
            raise KeyError(
                f"{code!r} is not a fire size class "
                f"({', '.join(row.code for row in RATIFIED_SERVICE_SIZE_CLASSES['fire'])}). "
                "A code this list does not hold is a typo, and skipping it would bill a "
                "fire line at nothing."
            )
        if code not in table:
            raise KeyError(
                f"{code!r} is a fire size class with no price in the table supplied. "
                "An unpriced size is REFUSED and never substituted (BR-RAT-120)."
            )
        if int(count) < 0:
            raise ValueError(
                f"{code!r} reports a count of {count}. A count is a number of physical "
                "things and cannot be below zero; a negative prices as a credit against "
                "a customer nobody authorised."
            )
        total += table[code] * Decimal(int(count))
    # Money is STORED to 4 decimals and DISPLAYED to 2 (CLAUDE.md hard rule 2).
    # This is a displayable charge, so it rounds here and B4's "round only at
    # finalization" is satisfied: nothing downstream re-rounds it.
    return total.quantize(Decimal("0.01"))


def steam_size_classes() -> tuple[tuple[str, str], ...]:
    """Thermal STEAM's bands — OQ-560, never ruled.

    Separate from `size_classes_for_service("thermal_heat")` because thermal is the
    one service with TWO dimensions and only one of them is ratified. Asking
    for thermal returns the three chilled-water classes; asking for steam
    raises, and neither answer can be mistaken for the other.
    """
    oq, why = UNBANDED_SERVICE_DIMENSIONS["thermal_heat_steam"]
    raise SizeClassNotRuled(f"{oq} — thermal steam size bands are not ruled: {why}")


def seed_entries() -> list[dict[str, str]]:
    """Every ratified row, flattened into the `{code, name, service_code}` shape
    the platform fixture and `HostedFlatLookupHandler.seed` both speak, in
    SERVICE_ORDER.

    ⚠ **`service_code` IS CR-065 AND IT IS THE FIELD THIS FUNCTION USED TO
    DROP.** Every row here has ALWAYS known its service — the map above is keyed
    by it — and until 2026-09-02 this loop read that key for its rows and threw
    it away, so sixty `{code, name}` pairs reached the database with the one
    fact a picker needs missing. The Fire rate schedule therefore offered
    *Electric CT-metered*, which is `DEF-2385` and the PO's own screenshot. That
    is hard-won law 2 (*built is not wired*) on reference DATA rather than on a
    component: the knowledge was complete, correct, and never carried.

    This is the SOURCE the fixture's `service_size_classes` block mirrors;
    `test_cr039_e20_size_class_bands.py` asserts the two are identical, so a row
    edited in one place and not the other goes RED rather than shipping.

    ⚠ **CR-062 CHANGED WHAT THIS CARRIES AND NOT ITS SHAPE.** The delivery
    format is still a flat `{code, name}` list, so `_seed_reference_data` needs
    no change and no migration is owed: the capacity is ratified LAW that lives
    in this module, not a column on the hosted table. What moved is the content
    — 40 rows to 53 — and that needs a fixture version bump, which is
    BR-TEN-077's job and is the reviewable diff that says the new content was
    shipped deliberately.

    The unbanded dimension is skipped BY NAME — `UNBANDED_SERVICE_DIMENSIONS` is
    consulted, never a bare `except`. A swallowed exception here would look
    exactly like a ruled-empty service, which is the one confusion this module
    exists to prevent.
    """
    rows: list[dict[str, str]] = []
    for service in SERVICE_ORDER:
        if service in UNBANDED_SERVICE_DIMENSIONS:
            continue  # OQ-560 — not ruled, so not seeded
        for code, name in size_classes_for_service(service):
            # `service_code` is the SERVICE CODE the migration stores, never a
            # display name: `thermal_heat`, not "Thermal/Heat" (DEF-972 is the
            # same confusion one level up, where this module first wrote
            # `thermal` and the lookup raised KeyError on a key no service has).
            rows.append({"code": code, "name": name, "service_code": service})
    return rows


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-010@f9d0685 (EP-TEN-07 reference data — the CONTENT half of one list. The hex is the branch-base commit the packet was assembled from, the one carrying the 2026-08-27 ruling in 12-governance/02-decision-log.md; no verifier tool stamps this yet, so it is a checkable reference rather than a recomputed snapshot hash)
# generated: 2026-08-27 by the CR-039 wave E tasks 20–21 lane (BR-TEN-170 rename + BR-TEN-171 forty ratified classes; OQ-560/OQ-561 stubbed rather than guessed) · AMENDED the same day for DEF-972 — the thermal service CODE is `thermal_heat`, not the prose name `thermal`, and TC-12 now pins SERVICE_ORDER against tenancy/migrations/0001_initial.SERVICE_SEED · AMENDED 2026-09-01 by the DEF-2396/DEF-2408 lane — battery left UNBANDED_SERVICE_DIMENSIONS for `()`, *ruled to have none*, because the PO DISSOLVED OQ-561 · AMENDED 2026-09-02 by the CR-062 group A lane — a size class is now either a BAND (a label that picks a rate) or a CAPACITY (a number with its unit, summable), solar's four superseded inverter bands are WITHDRAWN and replaced by ten panel types, storm water's four ERU bands are REVERSED into five property sizes, and battery gains six capacities that are a catalogue rather than the bands OQ-561 dissolved. 40 rows becomes 53. · AMENDED 2026-09-07 by the CR-080 lane — THERMAL/HEAT moves metered -> capacity on the PO's ruling of that day, its three `TH-CW-*` RANGES are WITHDRAWN (a range has no single value a capacity could be) and replaced by EIGHT connected-tonnage capacities `TH-T5`..`TH-T800` in `ton`, the last of the 2026-08-27 supersession debt this file recorded against itself. 59 rows becomes 64. Steam is untouched and `OQ-560` stays OPEN.
# checklist: A✔ B✔ (BR-TEN-170/171 → code; 19 cases in test_cr039_e20_size_class_bands.py + test_cr039_e21_service_size_classes.py, 26 more in test_cr062_a_capacity_size_classes.py, every one of which was shown RED on the pre-CR-062 code before a line here changed) C✔ (no query at all — this module is pure ratified data, so there is no tenant scope to get wrong; no money column, BR-MET-067b still forbids one; nothing append-only is written; the one number added is a QUANTITY and the price that multiplies it stays in rating) D=deferred(no-API-half — the list is served by tenancy's EXISTING /lookups/{list}; this lane changed the list CONTENT and added no endpoint, no error code and no money figure) E=deferred(CR-062 group A is reference data only; the S8 card renders whatever the list serves and needed no change, and the e2e spec's expected code list moved with it) F✔ (see gates:) G✔ (the two supersessions are written to 12-governance/02-decision-log.md with the rulings quoted verbatim and dated, BR-TEN-171 is amended in 04-docs/05-modules/01-tenancy/02-business-rules.md in the same commit, and CR-062's own A1–A6 rows are marked done) H=deferred(PO 2026-08-09 — AI authors, human reviews later; the row is in 12-governance/09-human-review-ledger.md and names in plain English with figures the two ratified lists this CR reverses)
# exceptions: the hosted TABLE and `models.MeterSizeClass` deliberately keep the OLD name — BR-TEN-170 states where the rename stops and DEF-970 tracks the schema slice · `E-3P` "Electric 3φ" is dropped from the platform fixture and BR-TEN-071 deletes it from NOBODY · thermal STEAM seeds nothing and RAISES — it was put to the PO as a DIMENSION with no boundaries · ~~thermal chilled water's three bands are STILL superseded and STILL not withdrawn~~ **PAID 2026-09-07 by `CR-080`** — the ruling reversed the first of those two reasons and the second (each row is a RANGE) was always the argument FOR withdrawal rather than against it · **storm water's five names carry no "Storm water " prefix**, which diverges from BR-TEN-078's convention that an unscoped row names its own service; the names are the PO's own and were approved as they read, and the cost is stated in the module docstring · **the fixture mirror `apps/tenancy/fixtures/lookup_defaults.json` and its BR-TEN-077 version bump are NOT in this commit** — that file is held by the CR-062 group B lane and was messaged rather than edited, so `test_br_ten_171_tc7` is the drift guard that will hold until it lands
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
