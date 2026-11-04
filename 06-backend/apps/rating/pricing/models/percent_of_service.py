# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — usage pricing) · EP-RAT-02
#           (US-RAT-007 configures the percent, its basis service, the BASIS
#           ITSELF — since CR-130-BRC07 — and sewer's own rate, since CR-081)
#           Screens: — (the line renders in S31.2 and on the bill; the percent
#           is configured on S11 step 3's "% of another service" card)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Change:   CR-130-BRC07 — a percentage of another service can be a percentage
#           of its MONEY or of its METER, and the meter basis may be priced
#           through a LADDER. PO ruling 2026-09-22.
# Rules:    BR-RAT-1030 (NEW — the two bases, and which fields each requires)
#           · BR-RAT-015 ❄️ SUPERSEDED 2026-09-08 by CR-081 (was: sewer = % of
#           WATER USAGE-CHARGE DOLLARS; then: % of the water QUANTITY, priced on
#           sewer's own schedule) · BR-RAT-010 reopened 2026-09-07 and answered
#           the VOLUME way · BR-RAT-003 (a plugin never rounds) · BR-RAT-044
#           (one price(...) interface) · BR-RAT-026/032 (every unit bills
#           through a tier; only the last block is open-ended) · B4.2 as
#           re-signed 2026-08-11 (a printed document must foot against itself)
# Golden:   GT-17 (= WE-1) — B5 ❄️ RE-SIGNED 2026-09-08 (HUMAN-GUIDE §6, PO as
#           finance authority): water 8 kgal, sewer 90% x 8 = 7.2 kgal at
#           $5.0000/kgal = **$36.00** (the 4120 posting). It was 40% x $39.50 =
#           $15.80 until that date. Also GT-20 (WE-4, sewer $54.00 on 12 kgal),
#           GT-25 (WE-9, $27.00 on 6 kgal) and GT-26 (WE-10, $27.00 per half).
#           ⚠ ALL FOUR ARE ON THE `usage` BASIS AND NONE OF THEM MOVES HERE.
# Tests:    06-backend/tests/test_us_rat_012_percent_of_service.py ·
#           06-backend/tests/test_cr081_sewer_volume_basis.py ·
#           06-backend/tests/test_cr130_percent_basis.py
# Impacts:  apps/rating/engine.py 🔒 (its second pass supplies the basis
#           quantity, its unit AND — since CR-130-BRC07 — the basis dollars)
# ───────────────────────────────────────────────────────
"""`percent_of_service`: a percentage of another service's METER, or of its MONEY.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

Serves US-RAT-012 TC-6 and US-RAT-007 §7. This is the commonest submetering
arrangement there is — a utility that meters water and bills sewer as a share of
it — and until 2026-08-16 no plugin was registered for it, so a plan carrying a
sewer schedule refused at the registry.

THE TWO BASES, AND WHY THERE ARE TWO
=====================================
`config.percent_basis` (`tariff_versions.percent_basis`, `CR-130-BRC07`, PO
ruling 2026-09-22) says WHAT the percentage is taken of. The PO asked for both
in one sentence — *"we also need to create 2 option 5age of charges or % of
usage"* — and gave a worked figure for each:

    'usage'   "if Water usage will be 100 gallan %age is 80% then sewer uage
               will be 80 gallan = sewer charge will be 80 X { flat rate or
               tiered rate}"

              -> 80 gallons, priced through THIS schedule's own rate: one
                 unbounded block (flat), or a ladder, walked block by block.

    'charge'  "if water charge is $100, and %age is 80% then sewer cahrge
               will be $80"

              -> $80.00. No rate of this schedule's own is read, and one is
                 REFUSED BY NAME if the tariff states one.

**THERE IS NO DEFAULT AND NO FALLBACK BETWEEN THEM.** A tariff that names no
basis refuses; a tariff that names `charge` and reaches the engine with no
amount refuses; a tariff that names `usage` and reaches it with no quantity
refuses. Reading one basis's number when the other's is missing would price 90%
of money at a factor meant for 90% of gallons and produce a well-formed bill
for a number nobody configured.

⚠ **WHAT THIS FILE SAID UNTIL 2026-09-08, QUOTED RATHER THAN DELETED (law 1)**
-------------------------------------------------------------------------------
It said *"sewer as a percentage of water"* and meant a percentage of MONEY, and
it argued the point at length under the heading *"BR-RAT-015 IS THREE
EXCLUSIONS"*:

    * **Not the consumption.** 40% of 8 kgal is 3.2 kgal, and sewer has no price
      per kgal to apply it to. OQ-008/OQ-010's closure chose the DOLLAR basis,
      and BR-RAT-010 is CLOSED as answered by it.

**Every clause of that was false from 2026-09-08, and the first one is why:**
sewer HAS a price per kgal from `CR-081`. The Product Owner reopened
`BR-RAT-010` on 2026-09-07 (*"we ahve to apply this method — Way 2 … a
percentage of the gallons"*) and re-signed the six frozen figures on 2026-09-08
under HUMAN-GUIDE §6, verbatim:

    "C — factor 90%, rate $5.00 → $36.00, which is what a real sewer customer
     actually pays"

⚠ **AND WHAT THIS FILE SAID FROM 2026-09-08 UNTIL 2026-09-22 WAS TOO NARROW IN
EXACTLY ONE WORD — *ONLY*.** It read *"a percentage of water's VOLUME"* and
argued the volume basis as the only basis there is, under the heading *"THE RATE
IS SEWER'S OWN"*. The volume basis is untouched and is still what every stored
schedule carries; what changed is that it stopped being the only one.
`CR-130-BRC07` puts the DOLLAR basis back BESIDE it as a choice a clerk makes on
S11 — **not in front of it**:

    ❄️ GT-17 = $36.00 · GT-20 = $54.00 · GT-25 = $27.00 · GT-26 = $27.00

are all on the `usage` basis, all re-signed 2026-09-08, and none of them moves.
Every row that existed before the column did is written `'usage'` BY NAME by
`rating/0043_cr130_percent_basis.py`, never left to a default — because a
schedule that silently changed basis moves real money on a real customer.

⚠ **THE SUPERSESSION CHAIN, IN ORDER, BECAUSE TWO OF ITS THREE LINKS REVERSE
EACH OTHER AND A READER WHO JOINS AT THE WRONG ONE BUILDS THE WRONG THING:**

    BR-RAT-015  CONFIRMED     2026-08-16  % of the basis service's MONEY
    BR-RAT-015  ❄️ SUPERSEDED  2026-09-08  % of its VOLUME          (CR-081)
    BR-RAT-1030 CONFIRMED     2026-09-22  BOTH, per schedule  (CR-130-BRC07)

`BR-RAT-1030` does not un-supersede `BR-RAT-015`: the 2026-09-08 ruling stands
as the default and as the law for every schedule in force. What `BR-RAT-1030`
adds is a stored answer to a question `BR-RAT-015` never had to ask.

THE FROZEN FIGURE THIS REPRODUCES, RE-SIGNED 2026-09-08
--------------------------------------------------------
B5 GT-17 (= WE-1, the reference bill, recomputed from raw inputs by
`10-scripts/03-golden-verify.py`):

    water usage   8 kgal metered                 <- the BASIS QUANTITY
    sewer qty     90% x 8 kgal   = 7.2 kgal      <- return-to-sewer factor
    sewer         7.2 x $5.0000  = 36.00         <- the 4120 posting

⚠ **THE 90% IS NOT THE OLD 40% MOVED UP. IT IS A DIFFERENT KIND OF NUMBER.**
The 40% was a PRICE RATIO — what sewer costs relative to water. The 90% is a
**RETURN-TO-SEWER FACTOR**: the fraction of metered water that physically
reaches the sewer. It is sourced at 79–95% across North American municipal
utilities and clusters on 90%.

⚠ **AND THAT DISTINCTION IS NOW LOAD-BEARING RATHER THAN HISTORICAL**, because
both kinds of number are configurable again: a tenant on `percent_basis='charge'`
is typing a PRICE RATIO, and a tenant on `'usage'` is typing a RETURN-TO-SEWER
FACTOR. They are not interchangeable, and the same digits mean different things
on the two bases — which is exactly why the basis is a stored column and never
an inference.

⚠ **AND THE IRRIGATION ALLOWANCE IS NOT MADE BY LOWERING THE FACTOR — THAT IS
THE ROAD NOT TAKEN, RECORDED SO NOBODY LATER "FIXES" IT DOWN.** A garden hose
is metered water that never reaches the sewer, and the industry's answer to it
is **winter-quarter averaging** — bill sewer on the customer's cold-months water
average, when nothing is being watered — which several utilities use and **this
product does not do** (B4's own note has said *"winter-averaging v1.1"* since it
was written). Dropping 90% to, say, 60% to "allow for gardens" would silently
under-bill every apartment and every commercial account that never waters
anything. If irrigation needs allowing for, the answer is winter averaging or a
separate irrigation meter, not this factor.

WHICH QUANTITY, EXACTLY: THE BILLED ONE  (the `usage` basis)
-------------------------------------------------------------
The basis is the BASIS service's `billed_quantity` — post-multiplier, in the
unit that service is metered in (`apps.metering.quantities` applies the meter
multiplier one module upstream; see `stages/normalize.py`). Not a rounded
figure and not a re-derivation: it is the same number that produced the water
line the customer is reading.

**THE UNIT TRAVELS WITH IT AND IS NOT ASSUMED (hard rule 3).** A utility
metering water in `ccf` bills sewer in `ccf`, and sewer's own rate is per that
unit. The plugin refuses a basis quantity that arrives without one rather than
labelling gallons as anything.

WHICH DOLLARS, EXACTLY: THE PRINTED ONES  (the `charge` basis)
---------------------------------------------------------------
`engine._usage_dollars` is the Σ of the basis service's FINALIZED usage lines —
rounded half-up to 2dp, which is what the customer reads. The base charge, the
tax and any fee are excluded by LINE KIND, which is `BR-RAT-015`'s own three
exclusions restored together with the arithmetic they belonged to.

`OQ-232` asks which dollars — printed or unrounded — and is **OPEN,
non-blocking**, with the printed reading already recorded in the register along
with its reasoning: `10-scripts/03-golden-verify.py` computes GT-17's old basis
from the ROUNDED tier lines, and B4.2's re-sign of 2026-08-11 settled the
identical question for the tax base, because *"a customer who adds up the four
printed lines and applies the rate"* must reach the printed figure. The PO's
worked figure ($100.00 at 80% → $80.00) is exact at both readings and does not
distinguish them.

⚠ **THIS FILE'S LIFECYCLE BLOCK CALLED `OQ-232` *CLOSED BY SUPERSESSION* FROM
2026-09-08, AND THE REGISTER NEVER AGREED — ITS STATUS COLUMN READ OPEN
THROUGHOUT (`DEF-RAT-6142`).** CLAUDE.md's rule is that the status column
decides and a body contradicting it is stale, so the question was live even
while this file called it closed. Restoring the charge basis makes it live in
substance too, and the block below now says so.

PERCENT POINTS, NOT A FRACTION
------------------------------
`tariff_versions.percent` stores what the tenant typed on S11 — 90 for 90% —
because `services._validate_structure` refuses values <= 0 and asks for
confirmation above 100 (US-RAT-007 TC-6, "Sewer percent entered as 140%"). The
division by 100 happens here, once, and nowhere else. It is the same column and
the same scale on BOTH bases.

THE RATE IS THIS SCHEDULE'S OWN, AND IT IS A REFUSAL WHEN ABSENT — ON `usage`
-------------------------------------------------------------------------------
`config.unit_price` is `rating.rate_tiers`' single 0→∞ block on this version,
and `config.tiers` is that same table with more than one row in it — the
representation `flat` and `tiered` already use (BR-RAT-032), so no new column
and no second way to say "one price". **Flat versus tiered is how many blocks
there are**, which is why `CR-130-BRC07` adds no `rate_shape` flag and no second
column for the rate. A percent-of-service tariff on the usage basis that states
no rate REFUSES: a factor with no price is not a $0.00 sewer line, it is a
tariff nobody finished configuring.

**ON `charge` THE SAME FIELDS ARE REFUSED, FOR THE OPPOSITE REASON.** A
percentage of money needs no price per gallon, and a rate that reached this
plugin on that basis would be a stated number the engine silently drops — the
same class of fault as the `tiers[0]` discard this change also fixes. It is
refused BY NAME, never ignored.

THE LADDER, AND THE DISCARD IT REPLACES
----------------------------------------
On the usage basis the derived quantity is priced through THIS schedule's own
blocks, and `tiered.price` does that walk — imported rather than re-implemented,
so `BR-RAT-026`'s *"every unit bills through a tier"* refusal, `BR-RAT-002`'s
threshold proration and the block wording exist once in the product. Only the
DESCRIPTION is rewritten afterwards, because a customer looking at 7.2 kgal of
sewer beside 8 kgal of water and no sewer meter has no other way to see where
the quantity came from.

⚠ **`selectors.pricing_inputs` READ `tiers[0].unit_price` AND SILENTLY
DISCARDED THE REST UNTIL 2026-09-22.** It was correct while nothing could create
a second block, and it would have become a silent wrong-money bug the moment the
ladder existed — a five-block sewer ladder billing every gallon at block one's
price, with no error anywhere and a bill that foots. It is fixed in the same
change that opens the door, which is the only order in which that fix is worth
anything.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from apps.rating.pricing.percent_basis import PERCENT_BASES, PERCENT_BASIS_CHARGE
from apps.rating.pricing import errors, wording
from apps.rating.pricing.contracts import (
    KIND_USAGE,
    LineCandidate,
    MeasuredUsage,
    ModelConfig,
    PeriodShape,
    SubscriptionContext,
)
from apps.rating.pricing.models import tiered

MODEL = "percent_of_service"

#: `tariff_versions.percent` is in percent POINTS (90 = 90%). Named rather than
#: inlined so the one place the scale is decided is greppable.
PERCENT_POINTS = Decimal("100")


def price(
    subscription: SubscriptionContext,
    usage: MeasuredUsage,
    config: ModelConfig,
    period: PeriodShape | None = None,
) -> tuple[LineCandidate, ...]:
    """A percentage of the basis service's METER, or of its MONEY.

    UNROUNDED on both bases (BR-RAT-003) — `stages/finalize.py` rounds each line
    once, exactly as it does every other line in the product.

    `usage` is ignored ON PURPOSE and the argument stays for the BR-RAT-044
    interface: a percent-of-service tariff meters no consumption of its own.
    Sewer is billed off the WATER meter, and a sewer service point often has no
    meter at all — which neither `CR-081` nor `CR-130-BRC07` changes.

    `period` is new with `CR-130-BRC07` and is read only on the usage basis,
    where a LADDER's thresholds scale with a partial period (BR-RAT-002) exactly
    as the `tiered` model's do. `stages/price_usage._accepts_period` is what
    passes it, by inspecting this signature rather than by knowing which model
    it is talking to — so adding the argument here taught that stage nothing
    about percent-of-service.
    """
    service = subscription.service
    if config.percent is None:
        raise errors.TariffConfigError(
            f"service {service!r} is priced as a percent of another service and the "
            "tariff states no percent (BR-RAT-1030). A percentage that is not "
            "configured is a refusal, never 0%."
        )
    if not config.basis_service:
        raise errors.TariffConfigError(
            f"service {service!r} is priced as a percent of another service and the "
            "tariff names no basis service (BR-RAT-1030). Without the name there is "
            "nothing to take a percentage of."
        )
    if config.percent_basis is None:
        # CR-130-BRC07. `rating/0043` writes one of the two onto EVERY stored
        # row by name, so a None here is not an old schedule — it is a CALLER
        # that dropped the column somewhere between `pricing_inputs` and this
        # plugin. Defaulting to `usage` would hide that hop, and would be
        # indistinguishable from a tenant who chose it.
        raise errors.TariffConfigError(
            f"service {service!r} bills a percentage of {config.basis_service!r} and the "
            "configuration does not say a percentage OF WHAT (BR-RAT-1030: 'usage' takes "
            "the percentage of the metered quantity, 'charge' of the usage-charge "
            "dollars). Every stored schedule names one of the two, so this is a seam "
            "that dropped it — and the answer is never assumed."
        )
    if config.percent_basis not in PERCENT_BASES:
        raise errors.TariffConfigError(
            f"service {service!r} names percent basis {config.percent_basis!r}, which is "
            f"not one of {PERCENT_BASES} (BR-RAT-1030). There is no third basis and no "
            "silent fallback: a basis guessed on a money path is a wrong bill that "
            "looks right."
        )

    factor = config.percent / PERCENT_POINTS
    if config.percent_basis == PERCENT_BASIS_CHARGE:
        return _of_the_charge(subscription, config, factor)
    return _of_the_usage(subscription, config, factor, period)


def _of_the_charge(
    subscription: SubscriptionContext,
    config: ModelConfig,
    factor: Decimal,
) -> tuple[LineCandidate, ...]:
    """The PO's first figure: water $100.00 at 80% bills sewer **$80.00**.

    One line, and it carries NO quantity and NO unit — the absence is
    deliberate. This line prices DOLLARS, not a metered volume, so inventing a
    quantity here (0.8 x 8 kgal = 6.4) would print a consumption the customer
    never used and nobody ever metered. That sentence is this file's own, from
    the comment `CR-081` deleted when the volume basis arrived; it was right
    about THIS basis then and it is right about it now.
    """
    service = subscription.service
    if config.unit_price is not None or config.tiers:
        # ⚠ REFUSED BY NAME, NEVER IGNORED (CR-130-BRC07 §3). `services
        # ._validate_structure` refuses this at CONFIGURATION time; this is the
        # pricing-time half, for a row written by a script, a fixture or an
        # older client. A rate that reached here would be a stated number the
        # engine drops on the floor — the same class of fault as the `tiers[0]`
        # discard this change fixes, and invisible for the same reason: the
        # bill it produces is well-formed.
        raise errors.TariffConfigError(
            f"service {service!r} bills {config.percent}% of {config.basis_service!r}'s "
            "usage CHARGE (BR-RAT-1030, percent_basis='charge') and its tariff also "
            "states a rate per unit. A percentage of money has no price per unit behind "
            "it; the rate is REFUSED rather than silently dropped, because a dropped "
            "rate is a configuration the tenant can see and the engine cannot."
        )
    if config.basis_amount is None:
        # THE SEAM REFUSAL, charge half. The basis lives on another service's
        # priced lines, which exist only inside a whole-bill pass. When that
        # service is not on this bill — not on the plan, outside the run's
        # service scope, carrying no usage line, or held base-only — the answer
        # is UNAVAILABLE, and 80% of an unavailable number is not $0.00.
        # CLAUDE.md's seam rule, verbatim: an unwired seam REPORTS that it
        # cannot answer, never answers 0.
        raise errors.BasisUnavailable(
            f"service {service!r} bills {config.percent}% of {config.basis_service!r}'s "
            f"usage charge (BR-RAT-1030) and this bill carries no usage charge for "
            f"{config.basis_service!r}. The line is REFUSED and the account goes to the "
            "run's exception list (BR-BIL-015) — a sewer charge priced at 0.00 is a bill "
            "that silently forgives it."
        )
    return (
        LineCandidate(
            kind=KIND_USAGE,
            # ⚠ IT SAYS *usage charges* WHERE THE USAGE BASIS SAYS *volume*, AND
            # THAT IS THE WHOLE POINT OF THE SENTENCE. A customer on the charge
            # basis is reading a share of another line's MONEY; a customer on
            # the usage basis is reading a share of another METER. One wording
            # for both would leave the document unable to say which it is —
            # which is `DEF-RAT-6145` exactly, where five catalogue sentences
            # went on describing arithmetic the engine had stopped doing.
            #
            # `wording.percent_text` pads to exactly two decimals — `80.00%`,
            # not `80%` — for DEF-968: `tariff_versions.percent` is
            # `NUMERIC(18,6)` and an f-string prints a Decimal at its storage
            # scale, which put *"40.000000% of water usage charges"* on a live
            # deployment. Hard rule 2: percentages are STORED to six and
            # DISPLAYED to two. `factor` still divides the untouched stored
            # value — the ARITHMETIC is the six-place number and only the
            # SENTENCE rounds.
            description=(
                f"{service} usage — {wording.percent_text(config.percent)}% "
                f"of {config.basis_service} usage charges"
            ),
            amount=config.basis_amount * factor,
            taxable=True,  # B4.2: usage is in the tax base
        ),
    )


def _of_the_usage(
    subscription: SubscriptionContext,
    config: ModelConfig,
    factor: Decimal,
    period: PeriodShape | None,
) -> tuple[LineCandidate, ...]:
    """The PO's second figure: water 100 gallons at 80% bills **80 gallons**,
    priced through this schedule's own flat rate or its own ladder.

    ❄️ GT-17's $36.00 is this path with ONE unbounded block: 90% x 8 kgal =
    7.2 kgal at $5.0000.
    """
    service = subscription.service
    if config.unit_price is None and not config.tiers:
        # CR-081. On the DOLLAR basis this refusal cannot exist — the price
        # comes from the basis service's own schedule. On the VOLUME basis this
        # schedule prices its own quantity, so a tariff with a factor and no
        # rate is HALF configured, and half a tariff bills nothing at all.
        raise errors.TariffConfigError(
            f"service {service!r} bills {config.percent}% of {config.basis_service!r}'s "
            "metered VOLUME (BR-RAT-1030, percent_basis='usage'; CR-081, PO re-sign "
            "2026-09-08) and its tariff states no rate per unit and no tier. A "
            "return-to-sewer factor with no price behind it is a refusal, never a $0.00 "
            "sewer line (hard-won law 3)."
        )
    if config.basis_quantity is None:
        # THE SEAM REFUSAL, volume half — the rule it shares with the charge
        # half is written out in `_of_the_charge` above. 90% of an unavailable
        # number is not $0.00.
        raise errors.BasisUnavailable(
            f"service {service!r} bills {config.percent}% of {config.basis_service!r}'s "
            f"metered volume (BR-RAT-1030) and this bill carries no billed quantity for "
            f"{config.basis_service!r}. The line is REFUSED and the account goes to the "
            "run's exception list (BR-BIL-015) — a sewer charge priced at 0.00 is a bill "
            "that silently forgives it."
        )
    if not config.basis_unit:
        # Hard rule 3, and it is not theoretical here: this line's quantity is
        # BORROWED from another service, so the one thing that cannot be
        # inferred from anything on this tariff is what it is measured in.
        raise errors.TariffConfigError(
            f"service {service!r} takes its quantity from {config.basis_service!r} "
            "(BR-RAT-1030) and that quantity arrived with no unit. Consumption is always "
            "carried with an explicit unit and never assumed (CLAUDE.md hard rule 3)."
        )

    quantity: Decimal = config.basis_quantity * factor
    #: Where the quantity came from, in the customer's words. Built once and
    #: appended to every line this basis emits, so a flat sewer line and each
    #: rung of a sewer ladder say the same thing about their provenance.
    source = f"{wording.percent_text(config.percent)}% of {config.basis_service} volume"

    if config.tiers:
        # ── THE LADDER, WALKED BY THE ONE IMPLEMENTATION THERE IS ───────────
        # `tiered.price` owns BR-RAT-026's *"every unit bills through a tier"*
        # refusal, BR-RAT-002's threshold proration and the block wording. It is
        # CALLED rather than copied so a sewer ladder and a water ladder cannot
        # disagree about which block a gallon landed in, and so that a fix to
        # one is a fix to both.
        #
        # The derived quantity is handed over as a MeasuredUsage in the BASIS
        # service's unit, because that is what the quantity IS (hard rule 3).
        # `raw_quantity` repeats it and `multiplier` is 1 because the METER
        # multiplier was applied to the BASIS service one module upstream and
        # must not be applied a second time here (B4.4, and the PO ruling of
        # 2026-08-11 that moved it into `apps.metering.quantities`).
        derived = MeasuredUsage(
            billed_quantity=quantity,
            unit=config.basis_unit,
            raw_quantity=quantity,
            multiplier=Decimal("1"),
        )
        return tuple(
            # ⚠ ONLY THE SENTENCE IS REWRITTEN. The amount, the quantity, the
            # unit and the unit price come back from `tiered.price` untouched,
            # because a customer must be able to add the blocks up and reach
            # the total. What the tiered wording cannot say is where the
            # quantity came from — and a customer looking at 7.2 kgal of sewer
            # beside 8 kgal of water, with no sewer meter anywhere, has no
            # other way to see it.
            dataclasses.replace(line, description=f"{line.description} — {source}")
            for line in tiered.price(subscription, derived, config, period=period)
        )

    return (
        LineCandidate(
            kind=KIND_USAGE,
            description=f"{service} usage — {source}",
            amount=quantity * config.unit_price,
            taxable=True,  # B4.2: usage is in the tax base
            # ⚠ THIS LINE CARRIES A QUANTITY AND A UNIT, AND UNTIL 2026-09-08 IT
            # DELIBERATELY DID NOT. The comment that stood here said, verbatim:
            # *"No quantity and no unit: this line prices DOLLARS, not a metered
            # volume. Inventing a quantity here (0.4 x 8 kgal = 3.2) would print
            # a consumption the customer never used and nobody ever metered."*
            # On THIS basis the quantity is not invented — it IS the bill's
            # basis, the number the price is applied to — and printing it is the
            # only way the customer can check the line. On the CHARGE basis that
            # old sentence is still exactly right, and `_of_the_charge` above
            # emits no quantity for precisely the reason it gives.
            quantity=quantity,
            unit=config.basis_unit,
            unit_price=config.unit_price,
        ),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md)
# generated: 2026-08-16 by the pricing-engines lane (EP-RAT-05 US-RAT-012 TC-6 · EP-RAT-02 US-RAT-007 §7)
#            · AMENDED 2026-09-08 by the CR-081 lane: the basis is the water VOLUME, not the water money; the line carries a quantity, a unit and sewer's own rate; BR-RAT-015 ❄️ SUPERSEDED and BR-RAT-010 reopened and answered the other way, both under the PO's HUMAN-GUIDE §6 re-sign of six frozen figures.
#            · AMENDED 2026-09-22 by the CR-130-BRC07 wave A lane: the VOLUME basis is JOINED by the CHARGE basis rather than replaced by it (BR-RAT-1030, PO ruling 2026-09-22 — *"we also need to create 2 option 5age of charges or % of usage"*); `percent_basis` decides which, refuses when absent and never defaults; the volume basis may now be priced through a LADDER, walked by `tiered.price` rather than by a second implementation; a rate stated on the CHARGE basis is refused BY NAME. ❄️ GT-17/20/25/26 are all on the volume basis and none of them moves.
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half; the CONFIG half is S11 step 3's %-of-service card, CR-130-BRC07 wave B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_rat_012_percent_of_service.py✔ · pytest tests/test_cr081_sewer_volume_basis.py✔ · pytest tests/test_cr130_percent_basis.py✔ · pytest tests/golden✔
# exceptions: OQ-232 is OPEN — non-blocking — AND IT IS LIVE AGAIN. It asks whether "usage-charge dollars" means the rounded printed amounts or the unrounded intermediates; from 2026-09-08 to 2026-09-22 this block said it was CLOSED BY SUPERSESSION while the register's status column read OPEN the whole time (DEF-RAT-6142). There are basis dollars again, so the question has a subject again; the PRINTED reading ships, which is the disposition the register itself already records. · OQ-RAT-12347 is unchanged and unmoved: WE-6/GT-22 carries a SEVENTH sewer figure the 2026-09-08 re-sign did not cover, and the downstream PE-*/LE-* workbooks consume WE-1's total. · The CHARGE basis has no ❄️ frozen golden test behind it and one is owed: the review-ledger row for this change puts its worked figure — water $100.00, 80% → sewer $80.00 — to the PO in plain English.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
