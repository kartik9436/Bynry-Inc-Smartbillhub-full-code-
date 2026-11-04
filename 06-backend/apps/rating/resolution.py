# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-15 (the resolution engine — CR-013 design §A2, B2)
#           Screens: — (pure narrowing; its refusals surface on S31.3, its
#           answers price into S31.2)
#           No US-ID is cited in this header ON PURPOSE: G10 reads a Trace-header
#           US-ID as "this file ships that story's TCs" and EP-RAT-15's stories
#           are not authored yet. The precedent is apps/billing/rating_seam.py.
# Rules:    BR-RAT-730 (WHICH charge codes ride an ordinary periodic bill —
#           `recurring` AND `auto_apply`, or `is_base`) · BR-RAT-731 (R4 states
#           ONE amount or refuses by the name of the RULE in the way) ·
#           BR-RAT-117 (the PO ruling BR-RAT-730 executes) · BR-RAT-088 (the
#           charge code owns the base) · BR-RAT-041 (`formula` is reserved,
#           visible-but-disabled) ·
#           BR-RAT-007 (the version IN FORCE at the service date) · BR-RAT-012 /
#           BR-RAT-027 (the base charge is the plan's, per service) ·
#           BR-RAT-001 (the METER multiplier is applied to the QUANTITY, before
#           tiers) · BR-MET-056 (a read stores the multiplier USED) ·
#           BR-RAT-005 / B4.2 (the tax base is usage + base) · CR-013 part 1
#           (*"Blank base = size not served"*) · CR-013 header (taxes are never
#           selectable per plan)
# Rulings:  PO 2026-08-19 — a plan CANNOT override a price; the fire line is a
#           charge code, not a schedule; the meter multiplier and the
#           inside/outside-city factor are TWO DIFFERENT FACTORS on opposite
#           sides of the pricing step (decision log, "SIX RULINGS AND ONE
#           CORRECTION OF MINE")
# Golden:   the four §A4 scenarios — tests/test_cr013_a4_scenarios.py
# Tests:    06-backend/tests/test_cr013_resolution_chain.py ·
#           06-backend/tests/test_def_498_def_493_charge_code_recurrence.py
# Impacts:  apps/rating/engine.py 🔒 · apps/billing/gather.py (the DB-backed
#           half of R1/R2/R7 lives there today and is NOT duplicated here)
# ───────────────────────────────────────────────────────
"""R1–R7 — the deterministic narrowing that decides WHICH of many configured
prices applies to ONE customer.

HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING — rating math is a CLAUDE.md sensitive
path, AI-authored under the PO ruling of 2026-08-09 ("AI will do it; we will
review it later as human"). Row in 12-governance/09-human-review-ledger.md; not
RATIFIED without a recorded human sign-off. This file implements signed law and
never invents it.

WHY THIS MODULE EXISTS
----------------------
The PO put the problem exactly: *"we are setting all these rates, but in real
only one rate will be applicable or two or 3 based on how many services; billing
logic has to pic up dynamically which rate to apply out of these many that are
set"*. Silver Creek's catalogue holds 31 priced objects and a single bill uses a
handful. **The product's core job is the narrowing, and the narrowing is what has
to be provably correct** (CR-013 design §A1).

So this is a CHAIN, not a search. Each step returns **exactly one answer or
refuses** — ⚠ with ONE ruled exception since 2026-10-01: R2 answers the newest
of several versions of one schedule in force on one date, by the same rule as
the nightly run (`in_force_precedence`, `BR-RAT-1055`, PO ruling on
`DEF-RAT-8004`), and the bill-run Check names the overlap. There is no best match, no fallback, and no default anywhere in this
file — ambiguity is a defect the plan's own activation gates prevent, never
something a bill run resolves by picking. Every refusal below names the step, the
service and the fact that was missing, because a utility told *"this size is not
priced"* fixes it in a minute and a utility silently billed $0.00 finds out in an
audit.

THE CHAIN, AS RULED (design §A2, CORRECTED by the PO on 2026-08-19)
-------------------------------------------------------------------
    R1   account -> unit -> PLAN VERSION in force on the service-period end date
    R2   plan version -> exactly one RATE SCHEDULE VERSION per service
    R3   meter connection size -> IS IT SERVED by each bound schedule
                                                        (membership, NOT money)
    R3b  METER MULTIPLIER -> billable QUANTITY          (quantity, BEFORE pricing)
    R4   plan -> CHARGE CODES matching service, class and size
                                     -> THE BASE AMOUNT (money, BR-RAT-088)
    R5   PREMISES jurisdiction -> factor on base charges AND rates
                                                        (money, AFTER pricing)
    R6   account ENROLMENTS -> discounts, before taxes
    R7   taxes matching jurisdiction, services and class

⚠ R3b AND R5 ARE TWO DIFFERENT FACTORS AND THEY ARE NOT ADJACENT. The design
originally had one step — *"premises jurisdiction -> outside-city multiplier"* —
which folded together two unrelated facts. The PO corrected it, verbatim:
*"R5 · multiplier from the premises - multiple will come form meter; insight city
outside city will come from premises and you will ahve to add rate cahnges in
base charges and rates"*.

  * The **meter multiplier** is a METERING fact (a CT/PT ratio, a x10 register).
    It scales the QUANTITY and it must be applied **before the tier boundaries
    are walked**: a x10 register reading 62 is **620 kWh**, which lands in tier
    2, whereas 62 never leaves tier 1. Applying it as a money factor afterwards
    would price 62 kWh at tier-1 rates and then multiply the money by ten — a
    different, wrong number that looks entirely plausible.
  * The **outside-city factor** is a PRICING fact carried by the PREMISES. It
    scales the MONEY, after pricing, and it touches **both base charges and
    rates** — r10 draws it (*"Premises outside city limits multiply base and
    variable by 1.5"*) and the PO's correction makes it explicit so no
    implementation applies it to one and not the other.

WHAT THIS MODULE IS NOT
-----------------------
It holds NO database access, NO clock and NO money arithmetic. It NARROWS: given
facts that have already been read, it says which objects apply and refuses when
the answer is not exactly one. The arithmetic belongs to `apps.rating.engine`
(B4/B5, frozen) and the reads belong to `apps.rating.selectors` and
`apps.billing.gather`. That split is why this file can be tested exhaustively
without a stack, and why the four §A4 scenarios can be pinned to the cent.

WHAT IS DELIBERATELY UNBUILT, NAMED RATHER THAN FAKED
-----------------------------------------------------
**R6 has nothing to read, AS OF 2026-08-19.** There was no discounts table in
this product on the day this file was written — not "none seeded": the table did
not exist, and the CR-010 lane counted **zero discounts** on the live tenant.
CR-013 part 3 (EP-RAT-12, about nine stories) owns the discount object, the
enrolment table, verification, recertification and budget exhaustion.

So R6 resolves to a result that SAYS it is unmodelled
(`DiscountResolution.modelled is False`) rather than to an empty tuple, because
*"this product cannot express discounts yet"* and *"this customer has none"* are
different facts and a bill built on the second when the first is true is wrong
by a discount. A caller that needs the answer calls `require_discounts()` and
gets a refusal naming the epic.

⚠ **WIRED 2026-08-20 (DEF-361). THE PARAGRAPH BELOW IS KEPT AS THE RECORD OF
WHY THE CONTRACT HAS THE SHAPE IT DOES, AND ITS "when the table lands" IS NOW
"when the table landed"** — migration `0009_cr013_discounts` built six tables and
`resolve_discounts` went on refusing for a day with a reason that had become
false. It failed CLOSED, so nothing billed wrongly and no test failed; the only
signal was a human reading the message. `modelled` is now always True.

⚠ **EP-RAT-12 WAS BEING BUILT IN A PARALLEL LANE AT THE MOMENT THIS LANDED**
(`apps/rating/discounts.py`, `discount_services.py`, `discount_pricing.py`,
migration `0009_cr013_discounts`, all uncommitted in the shared tree when this
file was committed). **The CONTRACT is what survives that**, and it is why R6 is
a result object and not an empty tuple: when the table lands,
`resolve_discounts` reads it and returns `modelled=True` with the enrolments it
found — including `applied=()` for an account enrolled in nothing, which is then
a TRUE statement rather than a stand-in for one. Nothing else in the chain
changes, and no caller has to learn a new shape. **Whoever wires it: the ORDER
is the rule** — discounts apply BEFORE taxes, so a discount reduces the taxable
base, and §A4 S1 is the worked case (removing the $1.00 PAPERLESS discount moves
Bexar County from $3.78 to $3.80, which is why "reachable" is $196.37 and not
$194.60).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import replace as _dc_replace
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, TypeVar

# ── Refusals ────────────────────────────────────────────────────────────────
#
# Every one fails CLOSED and every one names its step. They are plain value
# errors for the reason `apps/rating/pricing/errors.py` gives for the engine's:
# this is a pure function with no request context, and the caller maps a refusal
# onto its own S31.3 exception row (BR-BIL-040). Mapping it here would give the
# narrowing knowledge of a screen it must not have.


class ResolutionError(Exception):
    """The chain could not narrow to exactly one answer. Never raised directly.

    ══════════════════════════════════════════════════════════════════════════
    TWO AUDIENCES, TWO SENTENCES — `DEF-RAT-7991`, 2026-09-29
    ══════════════════════════════════════════════════════════════════════════
    `str(exc)` is the ENGINEER's sentence and it is unchanged: it names the
    step, the rule and the row ids, and it goes to a log line, an audit row and
    the shadow report. **Nine of this module's raise sites interpolate a
    database uuid into it**, and on 2026-09-29 a clerk on the One-time bill
    screen read four of them at once:

        R2: 4 versions of schedule '01a0b366-61fa-7f50-8cc4-25fa070287cc' are
        in force for 'sewer' on 2026-10-29 (01a0b366-…, 01a0b388-…, …).

    B14 rule 31 — PO verbatim, *"no Databse ID on screen - that is a rule"*.
    The sentence reached the screen because `apps/billing/one_time.py` puts
    `str(refusal)` into a **200-response body** at six places, and
    `BR-SHL-020 r2`'s stripper (`client.ts` `delete rest.detail`) only ever saw
    an **ApiError's params**. The guard existed and could not see this shape.

    ⚠ **THE SENTENCE IS NOT REMOVED — `DEF-CUS-6464` added it on purpose,
    because a bare reason code breaks rule 32.** What changes is WHOSE words a
    clerk reads. A site that can carry a uuid now also states:

      * `message_key` — the catalogue key, resolved in the clerk's own
        language; the vehicle `DEF-BIL-5339` built for `GapNotes`, reused
        rather than a second one invented;
      * `message_params` — the FACTS the sentence interpolates, and every one
        of them is a thing a person can act on: a service, a date, a count, a
        connection size. **Never an id.** `G139` re-runs this module and fails
        on a uuid in either field;
      * `clerk_detail` — the id-free English mirror of that catalogue sentence,
        for a caller with no catalogue. `CLERK_REFUSALS` below holds the
        template and `G139` ties it to `en.json` — the same tie
        `test_def_bil_5339_clerk_facing_copy.py` holds over `budget_api`'s gap
        list, made by the gate here because the gate can RAISE the refusal and
        a pytest on this repo's default harness cannot reach PostgreSQL.

    A refusal that states none of the three is unchanged in every respect —
    twenty-seven of this module's thirty-six sites name no id and keep their
    one sentence.
    """

    step: str = "R?"
    #: The catalogue key a clerk's sentence resolves through, or None when this
    #: site never carried an id and has no second sentence to serve.
    message_key: str | None = None
    #: The id-free English mirror of that catalogue sentence, interpolated.
    clerk_detail: str | None = None

    def __init__(
        self,
        message: str,
        *,
        message_key: str | None = None,
        clerk_detail: str | None = None,
        message_params: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message_key = message_key
        self.clerk_detail = clerk_detail
        self.message_params: dict[str, object] = dict(message_params or {})


#: ── THE CLERK'S SENTENCES, IN ENGLISH, ONE PER `message_key` ───────────────
#:
#: ⚠ **THIS IS A MIRROR OF `en.json` AND NOT A SECOND SOURCE.** The words a
#: clerk reads come from the catalogue entry for the key and from nothing else
#: (the 2026-08-19 ruling, `DEF-322`); these templates exist so a caller with no
#: catalogue — a log, a CSV export, an API consumer — still gets the id-free
#: sentence instead of the engineer's one. `G139` re-raises every one of these
#: refusals and fails the moment the two drift apart — the same tie
#: `test_def_bil_5339_clerk_facing_copy.py` holds over `budget_api`.
#:
#: ⚠ **EVERY SENTENCE IS SIX WORDS OR FEWER AND THERE ARE AT MOST TWO** (B14
#: rule 33, PO 2026-08-30 — *"this shuld be 6 words only"*). G33 counts the
#: `en.json` side. And **rule 33's other half is why none of them explains
#: itself**: the reason a chain refuses rather than picking is RATIONALE, which
#: is zero words on screen. It is in this file's docstring, where it belongs.
#:
#: ⚠ **`{service}` IS A PLATFORM CODE HERE AND A LOCALISED LABEL ON SCREEN.**
#: The server states `sewer`; `GapNotes` resolves it through
#: `rating.service.sewer` before interpolating, so the catalogue value carries
#: no dotted identifier (rule 32) and the clerk reads *Sewer*. The English
#: mirror below title-cases it the one way English can.
#:
#: ⚠ **NO PARAMETER IS CALLED `count`, DELIBERATELY.** i18next reads `count`
#: as the PLURAL selector and looks for `<key>_one` / `<key>_other` first; a
#: key family that does not exist is a resolution that depends on a fallback,
#: which is the shape `DEF-323` records one gate over. `{plans}` and
#: `{schedules}` are ordinary interpolations and resolve the same way in all
#: eleven catalogues.
CLERK_REFUSALS: dict[str, str] = {
    "rating.refusal.plansAmbiguous": "{plans} plans apply on {date}. Ask an administrator to retire one.",
    "rating.refusal.noScheduleBound": "No rate schedule prices {service}. Ask an administrator to bind one.",
    "rating.refusal.noScheduleInForce": "No {service} rate applied on {date}. Ask an administrator to check dates.",
    "rating.refusal.overrideScheduleMissing": "A discount names a missing schedule. Ask an administrator to correct it.",
    "rating.refusal.overrideWrongService": "A discount schedule prices another service. Ask an administrator to correct it.",
    "rating.refusal.overrideNotInForce": "A discount schedule was retired. Ask an administrator to correct it.",
    # ⚠ `schedulesAmbiguous` and `overrideAmbiguous` were here until
    # 2026-10-01 and are RETIRED with their raise sites (`BR-RAT-1055`, PO
    # ruling on `DEF-RAT-8004`, option A): two versions of one schedule in
    # force on one date no longer refuse — the newest prices and the bill-run
    # Check names the overlap (`billing.run.warn.scheduleVersionsOverlap`).
    "rating.refusal.sizeBlankBase": "This {service} size has no price. Ask an administrator to price it.",
    # ⚠ **R7's ONLY REFUSAL, AND IT IS NOT RAISED FROM THIS FILE** —
    # `DEF-RAT-8051`, 2026-09-29. `selectors._authority_tax` raises
    # `AmbiguousAuthorityTax` when two of one authority's taxes of one form are
    # in force on the service date. The sentence lives HERE, with the other
    # nine, because `clerk_refusal()` is the one reader every serialiser calls
    # and a second registry beside it would be the third shape this module
    # already refuses to grow. The class is NOT a `ResolutionError`: R7
    # publishes no refusal class by design (a failed applicability means no
    # line, never an error — `DEF-273`), `test_cr052_task20_shadow_measure`
    # asserts that in those words, and `clerk_refusal()` reads the three fields
    # off ANY exception with `getattr`, so the mechanism is reused without the
    # hierarchy being widened.
    "rating.refusal.taxesAmbiguous": "{taxes} {authority} taxes apply on {date}. Ask an administrator to retire one.",
}


def clerk_date(when: date) -> str:
    """A date a clerk reads, never an ISO key. `2026-10-29` -> `29 Oct 2026`.

    ⚠ **ENGLISH MONTH ABBREVIATIONS, AND THAT IS A STATED LIMITATION RATHER
    THAN AN OVERSIGHT.** The eleven catalogues localise the SENTENCE; this one
    parameter arrives already rendered, because the server holds no locale and
    `Intl` lives in the browser. A clerk in `pt-BR` reads a Portuguese sentence
    with `29 Oct 2026` inside it. Recorded in `DEF-RAT-7991`'s row rather than
    left for a reader to discover.
    """
    return f"{when.day} {when.strftime('%b')} {when.year}"


def _titled(service: str) -> str:
    """`storm_water` -> `Storm water`. THE ENGLISH MIRROR ONLY.

    A screen never sees this: `GapNotes` resolves the raw code through
    `rating.service.<code>` in the clerk's own language. This is what the
    `clerk_detail` string carries for a caller that has no catalogue, and it is
    the one way English can title a platform code without a lookup table that
    would then have to be kept in step with the eleven services.
    """
    return service.replace("_", " ").capitalize()


def clerk_sentence(key: str, **params: object) -> str:
    """The id-free English mirror of `key`, interpolated. Refuses an unknown key."""
    try:
        template = CLERK_REFUSALS[key]
    except KeyError:  # pragma: no cover — a typo, caught by the tie test
        raise KeyError(f"{key!r} has no clerk sentence in CLERK_REFUSALS") from None
    return template.format(**params)


def clerk_refusal(exc: BaseException) -> dict[str, object] | None:
    """What a SCREEN may be given about `exc`, or None when it states nothing.

    THE ONE PLACE A REFUSAL BECOMES CLERK-FACING TEXT. Every serialiser that
    puts a resolution refusal into a response body calls this rather than
    `str(exc)` — `apps/billing/one_time.py`'s six `detail` sites and
    `apps/billing/shadow_report.py`'s account row today. A seventh caller that
    reaches for `str(exc)` re-opens `DEF-RAT-7991`, and `G139` is what notices.

    None means *this refusal carries no clerk sentence*, and the caller then
    falls back to `str(exc)` exactly as it always did — which is right for the
    twenty-seven sites that never named an id, and is the reason this change
    could land without rewriting prose nobody complained about.
    """
    key = getattr(exc, "message_key", None)
    if not key:
        return None
    return {
        "message_key": key,
        "detail": getattr(exc, "clerk_detail", None) or clerk_sentence(key),
        "message_params": dict(getattr(exc, "message_params", {}) or {}),
    }


class NoPlanInForce(ResolutionError):
    """R1 — no plan version covers the service-period end date.

    Not "the newest plan": BR-RAT-007's whole content is that a June bill prices
    on June's terms whether the run happens in July or in 2031, so a chain that
    fell back to today's plan would silently re-price history.
    """

    step = "R1"


class NoScheduleForService(ResolutionError):
    """R2 — the plan covers this service and binds no schedule version to it."""

    step = "R2"


class AmbiguousSchedule(ResolutionError):
    """R1's gate — two PLAN versions claim one account on one date.

    ⚠ **IT NO LONGER FIRES AT R2 (`BR-RAT-1055`, 2026-10-01).** Two versions
    of one rate schedule in force on one date are answered by
    `pick_in_force` — the newest — exactly as the nightly run answers them;
    the class name is kept because R1 still raises it and renaming a raised
    class moves every `except` that names it.

    Originally: two schedule versions claim one service on one date.

    The plan's own activation validation is supposed to make this unreachable.
    It refuses here anyway: a gate that exists only upstream is a gate that is
    absent the first time someone writes a row another way.
    """

    step = "R2"


class SizeNotServed(ResolutionError):
    """R3 — the meter's connection size has no row on the bound schedule, or the
    row it has states a BLANK base.

    CR-013 part 1, verbatim: *"Blank base = size not served"* (DEF-277). A
    blank is data. Billing $0.00 for a size the utility refuses to serve is a
    silent wrong answer, not a partial one.

    ⚠ A STORED `0.00` IS A DIFFERENT FACT and does NOT reach here — PO ruling
    2026-08-19, verbatim *"print $0.00"*, for the rows already in the database
    that cannot be disambiguated. Zero is a price; blank is the absence of one.
    """

    step = "R3"


class RateOverrideUnusable(ResolutionError):
    """R2 — a `rate_override` discount names a schedule this bill cannot be
    priced from (CR-052 W5 task 17).

    ⛔ **UNREACHABLE SINCE `BR-RAT-961` (PO ruling 2026-08-31).** A subsidy is
    the standard schedule plus a discount line, so no production path reaches
    `resolve_schedule_with_override` and none of these branches can fire. The
    class is KEPT with its function for the reason stated there (cutting a
    discount type is its own change — `BR-RAT-094`'s precedent), and this note is
    here so a reader does not take a live-looking refusal for a live one.

    CR-013 part 3 named both refusals in its own words — the product must refuse
    *"rate overrides pointing at retired or mismatched-service schedules"* — and
    they are the two branches below. They REFUSE rather than falling back to the
    plan's ordinary schedule, because a subsidy the utility granted and the bill
    silently did not apply is the failure part 3's *"subsidy granted is
    reportable"* clause exists to prevent, and the customer is the one who finds
    out. **That clause is now met a different way**: the discount line is on the
    bill, so a subsidy that was granted is visible by construction rather than by
    a refusal watching for its absence.
    """

    step = "R2"


class UsageAllowanceUnusable(ResolutionError):
    """R3b — a `usage_allowance` discount whose quantity cannot be subtracted
    from this service's billable quantity (CR-052 W5 task 17).

    ⚖️ **THE FIRST BRANCH MOVED ONE FACT ALONG ON 2026-08-31 (`BR-RAT-960`) AND
    IS WORTH READING TWICE.** It used to fire when the DISCOUNT stated no unit,
    which was every discount, because no column held one. The PO ruled the unit
    comes from the SERVICE — *"a) Take the unit from the service it's attached
    to"* — so the discount no longer needs to state one and that refusal is gone.
    **What replaces it is narrower and still hard rule 3**: it fires when the
    SERVICE states no unit. The ruling gave the unit a SOURCE, not a DEFAULT, and
    four of the ten catalog services carry no stated unit, so this is a branch a
    real tenant can reach.

    Three branches, and the first two are CLAUDE.md hard rule 3: a service with
    no stated unit, an allowance asserted in a unit that is not what the meter
    measured, and a negative allowance (which is a surcharge nobody authorised).
    Two free kgal cannot be taken off 620 kWh, and this chain holds no conversion
    factor and performs none (BR-RAT-038, *"no silent conversion"*).
    """

    step = "R3b"


class MeterMultiplierUnstated(ResolutionError):
    """R3b — the meter states no multiplier, so the billable quantity is unknown.

    BR-MET-056: a read stores the factor USED. A missing factor is not 1: a x10
    register whose multiplier nobody recorded bills a tenth of the customer's
    consumption, and the bill looks entirely normal.
    """

    step = "R3b"


class AssetCountUnavailable(ResolutionError):
    """R3b — the service is UNMETERED and nobody can say how many things it has.

    BR-RAT-090's own words: *"it REFUSES rather than defaults exactly as the
    metered branch does — a unit whose cart count cannot be determined stops the
    bill, because 'no carts recorded' and 'zero carts' are different facts and
    only one of them is billable."*

    This is the unmetered twin of `MeterMultiplierUnstated`, and for the same
    reason: the plausible default is the dangerous one. Reading an unknown count
    as zero bills a three-cart household `$0.00` for trash on a document that
    looks entirely normal.
    """

    step = "R3b"


class ChargeCodeAmountMissing(ResolutionError):
    """R4 — a charge code applies to this account and the chain cannot state
    ONE amount for it. Design §A2: *"no amount => REFUSE"*.

    ⚠ **THE CLASS IS UNCHANGED; THE SENTENCE IT CARRIES WAS WRONG FOUR TIMES
    OUT OF FIVE (`DEF-498`, 2026-08-28).** `ChargeCode` used to carry a flat
    amount and a per-size table and nothing else, while `charges.amount_rule`
    has stored four rules since r6.6. So a `percent` code, a
    `percent_with_minimum` code, a `formula` code and a code with no rule
    stated all arrived here identically — `flat_amount=None`, `amounts={}` —
    and every one of them was refused with the same sentence, blaming the
    CONNECTION SIZE:

        R4: charge code 'LATE' applies to this account and states no amount
        for connection size None on service None

    LATE is `percent_with_minimum` 1.5% with a $5.00 floor. Nothing about it
    has anything to do with a connection size, and an account-level code
    (`service is None`) can never match one anyway. **A refusal that names the
    wrong fact is worse than a long one**: it sends a utility to look at a
    meter for a problem that is on a price list. Each rule now says what is
    actually true of it.
    """

    step = "R4"


class BaseChargeNotBound(ChargeCodeAmountMissing):
    """R4 — the rate schedule NAMED a base code and that code cannot answer for
    this account (`BR-RAT-1025`, `DEF-RAT-6918`).

    ⚠ **RAISED BY `resolve_base_charge` AND CAUGHT BY `resolve`, NEVER BY A
    CALLER (PO ruling 2026-09-30).** Until that day it was the refusal itself.
    The PO ruled *"if user did not define and bind base charges in rate
    schedule - then as a default you take 0 and complete the bill"*, and a
    schedule whose named code cannot price this account is exactly *no base
    bound for it* — so `resolve` turns it into a `$0` base with
    `base_source="not_set"`. It is a subclass rather than a return value so a
    caller of `resolve_base_charge` alone (the shadow, the tests) still sees
    the refusal it always saw, with its sentence intact.

    **It never falls back to the service's inferred code or to the retired
    schedule column** — the reason the refusal existed (a bill figure the
    schedule's own screen does not show) is still true, and `$0.00` with a
    warning is the ruled answer instead of a different code's figure.
    """


class ChargeCodeRecurrenceConflict(ResolutionError):
    """R4 — this code's two recurrence columns contradict each other.

    `BR-RAT-730`. `charges.charge_type` says WHEN a code fires and
    `charges.auto_apply` says whether it fires by itself. A code marked
    `one_time` (or `penalty`, or `refundable`) AND `auto_apply` has been told
    both *"fire on an event"* and *"fire on every bill"*, and the two readings
    are a `$250.00` tamper fee on one bill or on twelve.

    **The chain does not pick one.** A contradiction is not a missing fact with
    a safe direction — both columns were filled in deliberately by a person, so
    reading either as authoritative discards the other person's answer. This is
    the chain's standing posture (*"no fallback, no default"*) applied to a
    disagreement rather than to a gap.

    ⚠ It cannot fire on any tenant provisioned today: every one of the 23
    seeded charge codes carries `auto_apply=False`, so nothing contradicts
    anything. It exists for the tenant who ticks the box on the wrong card.
    """

    step = "R4"


class JurisdictionUnstated(ResolutionError):
    """R5 — the premises records no jurisdiction and the plan prices by one.

    The fail direction is deliberate and it is the OPPOSITE of DEF-273's. There,
    an unknown premises must NOT be charged an inside-city fee, because
    over-charging a customer is not recoverable. Here the tenant has configured
    a factor that changes every line of the bill, so an unknown premises means
    the bill cannot be produced at all rather than produced at the inside-city
    price by default.
    """

    step = "R5"


class DiscountsNotModelled(ResolutionError):
    """R6 — raised by `require_discounts()` for a caller that cannot proceed
    without an answer.

    ⚠ **`resolve_discounts` NO LONGER PRODUCES THIS** (DEF-361, 2026-08-20): the
    six discount tables exist, so R6 always resolves. The class is kept because
    it is part of the contract callers were written against, and because
    `DiscountResolution.modelled` remains the honest place to say *the product
    cannot express this* if a future object ever needs it. A refusal nobody
    raises is cheap; a caller that has forgotten how to handle one is not.
    """

    step = "R6"


def refusal_steps() -> dict[str, str]:
    """Every refusal class this chain can raise -> the §A2 step it refuses at,
    derived from each class's own `step` attribute.

    ⚠ **PUBLISHED BECAUSE A SECOND COPY OF THIS MAP ALREADY EXISTS AND CANNOT
    SEE A NEW CLASS (`DEF-2341`).** `apps/billing/resolution_shadow.py` holds a
    hand-written `REFUSAL_STEPS` dict keyed on class NAME and reads it with
    `.get(name)`, so a refusal class added here comes back `None` and its
    account silently vanishes from the shadow report's `by_step` count — the
    one figure `DEF-1811`'s fix reported (`by_step {} -> {R4: 1}`). Nothing
    fails; a count is just quietly smaller. Hard-won law 5: one source,
    derived on demand, never a committed copy. This function is that source.

    Owned by another lane today, so it is offered rather than wired. The
    adoption is one line: `REFUSAL_STEPS = resolution.refusal_steps()`.
    """
    return {
        cls.__name__: cls.step
        for cls in _iter_refusals(ResolutionError)
        if getattr(cls, "step", None)
    }


def _iter_refusals(root: type) -> list[type]:
    """Every subclass of `root`, depth-first, each named once."""
    seen: list[type] = []
    for cls in root.__subclasses__():
        if cls not in seen:
            seen.append(cls)
        for deeper in _iter_refusals(cls):
            if deeper not in seen:
                seen.append(deeper)
    return seen


# ── The facts the chain narrows over ────────────────────────────────────────
#
# Read structurally where they come from other modules, by the same rule the
# pricing contracts follow: rating is called by billing and must not import it.


@dataclass(frozen=True)
class AccountFacts:
    """R1's starting point and R4/R6/R7's customer-class selector.

    `customer_class` is the PLATFORM code (`residential` | `commercial` |
    `industrial` | `government`), never a tenant's display label — r10's State
    Utility Tax is *"Comm, Industrial only · Residential exempt"* and that rule
    is written against the code. None means the account carries no type, which
    a class-restricted object treats as NOT matching (DEF-273's fail-safe).
    """

    account_no: str
    unit_id: str
    customer_class: str | None = None
    #: The discount codes the account is enrolled in. Carried so the shape is
    #: right when EP-RAT-12 lands; see `resolve_discounts` for why stating them
    #: does not make them apply.
    enrolments: tuple[str, ...] = ()
    #: ⚠ **WHOSE BILL THIS IS — R7's EXEMPTION-CERTIFICATE KEY (DEF-383), ADDED
    #: 2026-08-31 BY `DEF-2824`.** Not the same fact as `account_no`, which is
    #: the customer-facing number and keys nothing: `taxes`' part-4 exemption
    #: object hangs off `tax_exemption_certificates.account_id`.
    #:
    #: **THIS ONE FACT RUNS THE OPPOSITE WAY TO EVERY OTHER FACT ON THIS
    #: DATACLASS, AND THAT IS WHY IT IS NAMED HERE RATHER THAN LEFT TO A
    #: CALLER.** The three applicability RESTRICTIONS a tax states fail CLOSED
    #: when the caller cannot evaluate them (DEF-273: under-charging is
    #: recoverable). An EXEMPTION is a claim the CUSTOMER made, so an absent
    #: `account_id` reads as *"no certificate"* and the tax APPLIES
    #: (`selectors.tax_applies_to` states both directions and why). So omitting
    #: it does not drop a tax — it CHARGES one to a customer who is exempt,
    #: which is the unrecoverable direction. None is legitimate only for a
    #: caller asking about a plan rather than about a bill.
    account_id: str | None = None


@dataclass(frozen=True)
class PremisesFacts:
    """R5's selector. Selector 6 lives on the PREMISES and selector 5 on the
    ACCOUNT — different objects, and a naive implementation puts both in one
    place (design §A1). r10 says it plainly: *"the premise's jurisdiction flag
    (inside / outside city) and the account's customer class select which rows
    fire."*

    `inside_city_limits` is None when nobody recorded it.

    ── ⚠ `city` AND `state` ARE R7's, NOT R5's, AND THEY ARRIVED WITH `DEF-2824`
    A tax states its geography as `premises_scope_kind` + `premises_scope_value`
    over FIVE mechanisms (CR-013 part 4, TAX-02 step 1), of which
    `selectors.premises_in_scope` can answer two: `city_limits` — by the FLAG
    where one is recorded and **by the recorded city NAME where it is not** —
    and `state`. Until 2026-08-31 this dataclass carried the flag alone, so a
    tenant that had scoped a tax by state, or by a city name without having
    drawn its boundary flag, had that tax silently dropped from every ruled
    bill: the scope predicate reads the two keys BY NAME and an absent key
    fails closed.

    They are carried as the premises' own recorded values and nothing is
    derived from them here. `county` is still unanswerable everywhere (no
    column, no district table, no premise set — `premises_in_scope` returns
    False for those three mechanisms and says so), and it stays on this
    dataclass rather than being deleted because it is the fact the day a column
    holds it.
    """

    inside_city_limits: bool | None = None
    county: str | None = None
    city: str | None = None
    state: str | None = None


@dataclass(frozen=True)
class MeterFacts:
    """R3's connection size and R3b's multiplier, for ONE service point.

    `multiplier` is None when the meter states none — refused rather than
    defaulted to 1 (see `MeterMultiplierUnstated`).
    """

    service: str
    connection_size: str
    multiplier: Decimal | None = Decimal("1")


@dataclass(frozen=True)
class AssetCountFacts:
    """R3b's UNMETERED input — how many billable things this unit has.

    BR-RAT-090 (PO ruling 2026-08-20, option A, closes OQ-283): *"an unmetered
    service's quantity is a COUNT OF ITS ASSETS ON THE UNIT"*, and the count is
    **OBSERVED, never typed** — metering owns assets (B2 r4), so three carts on
    a unit bill three carts and adding one in the field changes the next bill by
    itself. **Worked, ratified:** 3 carts x `$15.00` = `$45.00`; remove one and
    the next bill is `$30.00`.

    ⚠ **`count=None` AND `count=0` ARE DIFFERENT FACTS AND ONLY ONE OF THEM
    BILLS.** `0` says the utility looked and this unit has no carts — a real
    answer, and it bills nothing for carts while the base still applies. `None`
    says nobody can tell, and BR-RAT-090 refuses on it exactly as the metered
    branch refuses an unstated multiplier. A `None` silently read as `0` is a
    customer with three carts billed for none.

    `size_class` is the asset's own class where the assets state one (A1 §S76
    lists **carts** among `service_size_classes`), so a per-size trash schedule
    can price a 96-gallon cart differently from a 35-gallon one. None means the
    assets state no class, which a flat schedule does not need.
    """

    service: str
    count: int | None = None
    size_class: str | None = None


@dataclass(frozen=True)
class PlanVersion:
    """R1's answer. `services` is the plan's service set — R2's domain."""

    plan_id: str
    version: int
    services: tuple[str, ...]
    effective_from: date | None = None
    effective_to: date | None = None
    #: service -> the RATE SCHEDULE the plan binds to it (`plan_rate_schedules`).
    #: The plan binds a SCHEDULE and the date picks the VERSION — those are two
    #: different narrowings and R2 does them in that order, which is why a
    #: catalogue may hold six electric schedules without any of them being
    #: ambiguous. A service listed in `services` with no entry here is a plan
    #: that covers a service and prices nothing for it: R2's first refusal.
    schedules: dict[str, str] = field(default_factory=dict)

    def in_force_on(self, service_date: date) -> bool:
        """⚠ **`effective_to` IS THE LAST DAY THIS VERSION PRICES — INCLUSIVE
        (`DEF-2889`, 2026-09-01).**

        This read `effective_to > service_date` until 2026-09-01 and was wrong
        by exactly one day, in the direction that stops a bill. `rating.services`
        closes a superseded window with `previous.effective_to = new_from -
        timedelta(days=1)`, so a version replaced on 1 October carries
        `effective_to = 30 September` and **30 September is a day it prices**.
        `rating.selectors.in_force_version` — the LIVE bill run — has always
        matched `effective_to__gte=service_date` and has always billed it.

        With the exclusive form, a service date equal to `effective_to` found
        the old version out of force and the new one not yet started, and the
        chain REFUSED the account. `BR-BIL-872` makes a switched rule's refusal
        FINAL — there is no fallback to the live answer — so switching R2 on
        would have stopped one day of billing per schedule change, per account.

        **The live path's boundary is the one that is right and the chain moved
        to it**, not the other way round: moving the bill run to the exclusive
        form would have taken a day off every rate window ever written and
        re-priced money already invoiced (hard rule 4).
        """
        if self.effective_from is None or self.effective_from > service_date:
            return False
        return self.effective_to is None or self.effective_to >= service_date


@dataclass(frozen=True)
class ScheduleVersion:
    """R2's answer for one service, carrying R3's size AXIS.

    ⚠ **`size_rows` IS A MEMBERSHIP MAP AND ITS VALUE NO LONGER PRICES A BILL
    (`DEF-2823`, 2026-08-31).** `BR-RAT-088` in its own words: *"R3's refusal
    semantics are unchanged — a size absent from the schedule still means NOT
    SERVED — but the base itself now resolves through R4; `ScheduleVersion
    .size_rows` stops carrying money."*

    So the KEYS are the whole of R3: a size on this mapping is a size this
    schedule serves, and a size absent from it refuses at R3 by name and is
    never substituted (PO 2026-08-28). The VALUE is the version's retired
    scalar `tariff_versions.base_charge`, kept for ONE purpose and read at ONE
    place — `resolve` uses it as R4's LEGACY fallback for a tenant that has
    declared no `is_base` charge code yet, and never as a gate.

    **Why that distinction is a defect fix and not a refactor.** While the
    value WAS the gate, `resolve_size_row` refused every size of every tenant
    that had done what `BR-RAT-088` told it to do: `RateScheduleWizard.tsx`
    dropped the base-charge input in the same ruling (*"CARRIED, NEVER EDITED
    … no control, no editing, no loss"*) and `decimalOut("")` omits the key, so
    **every schedule version a real utility creates through this product today
    stores NULL there, unavoidably.** Measured on the shipped fixture: 47 of 47
    accounts refused at R3 while the live path billed all 47 correctly from the
    charge code's `$8.00`.
    """

    version_id: str
    service: str
    #: ── `CR-120-BRC06` · `BR-RAT-1025` — THE BASE CHARGE CODE THIS VERSION
    #: NAMES, as a CODE STRING, or None (PO ruling 2026-09-19).
    #:
    #: PO verbatim: *"no this is not correct ; So: plan → rate schedule ->
    #: charge code → base charges - this is correct"*.
    #:
    #: ⚠ **A CODE STRING AND NOT AN ID, BECAUSE R4 SPEAKS IN CODES.**
    #: `ChargeCode.code` is what `resolve_base_charge` matches on and what every
    #: refusal in this module names; the catalogue holds the id and resolves it
    #: once, here, so the hot path never carries a uuid it would have to look
    #: up. That is `ChargeCodeAmount.customer_class`'s recorded reasoning
    #: applied — *"the resolver decides"* — rather than a second key invented.
    #:
    #: **None IS THE COMMON CASE AND IT IS THE FALLBACK.** Every version that
    #: exists on the day this field ships carries None, so R4 answers from the
    #: `is_base` lookup exactly as it does today and no bill moves. It carries a
    #: code only for a version somebody explicitly bound on step 1 of `RAT-03`.
    #:
    #: ⚠ **IT IS A POINTER AND `size_rows`' VALUE IS A RETIRED FIGURE.** Do not
    #: read one for the other: `size_rows` carries `tariff_versions.base_charge`,
    #: which `BR-RAT-088` RETIRED, and this carries the code that owns the base
    #: now. They are two fields about the base on one object and exactly one of
    #: them has a future.
    base_charge_code: str | None = None
    #: The SCHEDULE this is a version of (`tariffs.id`). Versions of one
    #: schedule succeed one another in time; two schedules for one service is
    #: an ordinary catalogue, not an ambiguity.
    tariff_id: str = ""
    effective_from: date | None = None
    effective_to: date | None = None
    #: ── `BR-RAT-1055` · `DEF-RAT-8004` — WHEN THE ROW WAS WRITTEN (PO ruling
    #: 2026-10-01, option A). R2's tie-break: two LEGACY versions of one
    #: schedule in force on one date (written before `rating/0047`) are
    #: separated by `effective_from` and then by THIS, newest wins — exactly
    #: as `selectors.in_force_version` separates them, through the same
    #: function (`in_force_precedence`). `None` on a fact built by hand, which
    #: sorts before any written row and is never the reason a bill moves.
    created_at: datetime | None = None
    size_rows: dict[str, Decimal | None] = field(default_factory=dict)
    #: WHICH OBJECT STATED THE KEYS OF `size_rows` — `"charge_code"` or
    #: `"schedule"` (PO ruling 2026-09-01, *"rate schedule will not provdie the
    #: size, charge code will provide"*).
    #:
    #: It carries NO money and gates NOTHING. It exists so that R3's refusal can
    #: name the object a person has to go and edit: telling a clerk a size *"has
    #: no row on rate schedule version 8f2c…"* when the axis was read off the
    #: base charge code sends them to the wrong screen, and `BR-RAT-120`'s whole
    #: point is that the refusal must be curable. `"schedule"` is the default so
    #: a fact built by any older caller keeps the sentence it has always had.
    size_axis_source: str = "schedule"
    #: ── `DEF-RAT-8822` · `BR-RAT-120` NARROWED (PO 2026-10-01, option A) ──
    #: DOES THE BASE PRICE DEPEND ON THE SIZE? `False` only where the base
    #: charge code is one *All sizes* price (`resolution_catalogue.
    #: base_is_one_price_for_all_sizes`); then a meter with no recorded size
    #: passes R3, because no size's base can be the wrong one. **`True` is the
    #: default and holds exactly as before** — a fact built by any older caller,
    #: a size-priced base, or no base code at all.
    base_priced_by_size: bool = True
    #: DEF-360 · the schedule's own per-size money, which is NOT the base.
    #:
    #: r10's rate matrix is `size · base · min · t1 · t2 · t3` and THREE columns
    #: vary by size. The base is the charge code's (BR-RAT-088). These two are
    #: the schedule's, and neither had a size dimension before CR-013 P1.
    #:
    #: An ABSENT key falls back to the version's scalar `minimum_bill`, and a
    #: present key holding None means this size has no minimum at all — r10
    #: draws an em-dash for every electric size. Absent is not zero, here as
    #: everywhere in this CR.
    minimum_bill_by_size: dict[str, Decimal | None] = field(default_factory=dict)
    #: The version's scalar minimum, used for any size the mapping does not
    #: name. Every schedule written before P1 has only this, so it prices
    #: exactly as it always did.
    minimum_bill: Decimal | None = None
    #: Per-size tier prices, `size_class -> tiers`. An absent size uses the
    #: schedule's ordinary tier set, which is why r10 states 2" and says nothing
    #: about the other four: a schedule states the EXCEPTION, not the rule.
    tiers_by_size: dict[str, tuple[Decimal, ...]] = field(default_factory=dict)

    def in_force_on(self, service_date: date) -> bool:
        """⚠ **`effective_to` IS THE LAST DAY THIS VERSION PRICES — INCLUSIVE
        (`DEF-2889`, 2026-09-01).**

        This read `effective_to > service_date` until 2026-09-01 and was wrong
        by exactly one day, in the direction that stops a bill. `rating.services`
        closes a superseded window with `previous.effective_to = new_from -
        timedelta(days=1)`, so a version replaced on 1 October carries
        `effective_to = 30 September` and **30 September is a day it prices**.
        `rating.selectors.in_force_version` — the LIVE bill run — has always
        matched `effective_to__gte=service_date` and has always billed it.

        With the exclusive form, a service date equal to `effective_to` found
        the old version out of force and the new one not yet started, and the
        chain REFUSED the account. `BR-BIL-872` makes a switched rule's refusal
        FINAL — there is no fallback to the live answer — so switching R2 on
        would have stopped one day of billing per schedule change, per account.

        **The live path's boundary is the one that is right and the chain moved
        to it**, not the other way round: moving the bill run to the exclusive
        form would have taken a day off every rate window ever written and
        re-priced money already invoiced (hard rule 4).
        """
        if self.effective_from is None or self.effective_from > service_date:
            return False
        return self.effective_to is None or self.effective_to >= service_date


@dataclass(frozen=True)
class ChargeCode:
    """R4's candidate. `service is None` is the spec's *"Any"* — CR-013 part 2:
    *"Svc is `—` for account-level codes (late fee, NSF)"*.

    `amounts` is the per-size table; `flat_amount` is the code that does not vary
    by size. Exactly one of the two is stated — a code stating both is a
    configuration the wizard's own gate refuses, and this chain refuses it too
    rather than choosing which one wins.
    """

    code: str
    service: str | None = None
    customer_classes: tuple[str, ...] = ()
    #: BR-RAT-088 · this code is its service's BASE charge, declared on the code
    #: itself. Never inferred from the code string — a tenant may name theirs
    #: anything, and matching `BASE-<service>` fails silently by producing a
    #: bill with no base rather than an error.
    is_base: bool = False
    #: ── WHEN THIS CODE FIRES (BR-RAT-730 · `charges.charge_type`) ──────────
    #: The tenant's own classification, from the S12 card the charge-code
    #: wizard writes: `recurring` | `one_time` | `refundable` | `penalty` |
    #: `adjustment`. **`None` is a real state and is not `recurring`** — a code
    #: whose type nobody stated is a fact about the configuration, and this
    #: chain never reads an absence as a value (`DEF-493`).
    charge_type: str | None = None
    #: ── AND WHETHER IT FIRES BY ITSELF (BR-RAT-730 · `charges.auto_apply`) ──
    #: `BR-RAT-117` (PO 2026-08-22, *"ruccuring and Autom apply land on bill"*):
    #: the gate for an ordinary periodic bill is BOTH flags together. Defaults
    #: False, which is the SAFE direction and is a declaration rather than a
    #: gap — see `resolve_charge_codes` and BR-RAT-730 for the worked figure.
    auto_apply: bool = False
    #: ── HOW ITS AMOUNT IS EXPRESSED (`charges.amount_rule`, r6.6) ──────────
    #: `flat` | `percent` | `percent_with_minimum` | `formula` (reserved and
    #: DISABLED, BR-RAT-041), or `None` where the tenant has stated no rule.
    #:
    #: ⚠ **THESE FOUR FIELDS DO NOT MAKE R4 PRICE A PERCENTAGE.** They let it
    #: SAY SO. Before they existed (`DEF-498`) a percent code and a per-case
    #: code both arrived as `flat_amount=None` with an empty `amounts` table,
    #: and R4 refused them by blaming the CONNECTION SIZE — *"states no amount
    #: for connection size None on service None"* — which is not what is wrong
    #: with either of them and sends a utility to look at a meter.
    amount_rule: str | None = None
    percent: Decimal | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    flat_amount: Decimal | None = None
    amounts: dict[str, Decimal | None] = field(default_factory=dict)
    outside_city_applies: bool = True


@dataclass(frozen=True)
class TaxRule:
    """R7's candidate. Attached, never chosen (CR-013 header: taxes are *"never
    selectable per plan"*), and the PO's ruling of 2026-08-19 — *"no plan cannot
    override prices"* — closes the only fork that could have changed that.

    A rule states EITHER `rate` or `flat_amount` (BR-RAT-036 gives a tax one
    form). `services` empty means every service on the bill; stated, it both
    RESTRICTS APPLICABILITY and NARROWS THE BASE — a city electric franchise fee
    is 1.5% of the electric lines, not 1.5% of the water bill.
    """

    code: str
    tax_id: str | None = None
    rate: Decimal | None = None
    flat_amount: Decimal | None = None
    services: tuple[str, ...] = ()
    customer_classes: tuple[str, ...] = ()
    inside_city_only: bool = False
    outside_city_only: bool = False


@dataclass(frozen=True)
class DiscountRule:
    """R6's candidate — what the CATALOGUE offers, before enrolment narrows it.

    Deliberately smaller than `discount_pricing.DiscountRule`, and the reason is
    the module boundary: `discount_pricing` imports `apps.rating.discounts`
    (Django models), and this module is PURE — it takes facts and returns
    facts, which is what lets the whole chain be tested without a database. So
    R6 carries only what SELECTING needs: which discount, at what configured
    value, in what order.

    **R6 selects; it does not price.** The money is computed by
    `discount_pricing`, which needs a subtotal R6 does not have — a percentage
    of a bill cannot be known before the bill's lines exist. `value` is the
    discount's CONFIGURED figure (`Decimal("0.15")` for −15%, `Decimal("25.00")`
    for a fixed monthly credit), never an amount taken off a bill.
    """

    code: str
    value: Decimal
    #: CR-013 part 3: *"stacking precedence, explicit because percentage-of-usage
    #: after a usage allowance gives a different number than the reverse."* Lower
    #: sorts first. Order is DATA, not the order rows happen to arrive in.
    precedence: int = 0


@dataclass(frozen=True)
class Catalogue:
    """Everything configured, before the narrowing. §A1's *"31 priced objects"*.

    Passed in whole rather than queried, so the chain is a pure function of what
    was configured and the four §A4 scenarios can run the SAME catalogue through
    it and prove that only the selectors moved the answer.
    """

    plan_versions: tuple[PlanVersion, ...] = ()
    schedule_versions: tuple[ScheduleVersion, ...] = ()
    charge_codes: tuple[ChargeCode, ...] = ()
    taxes: tuple[TaxRule, ...] = ()
    #: BR-RAT-081: the services this tenant sells WITHOUT a meter, read from
    #: `tenant_services.metered`. Empty is the correct default — every service
    #: this product has billed to date is metered, so an empty tuple preserves
    #: today's behaviour exactly.
    unmetered_services: tuple[str, ...] = ()
    #: R6's catalogue half. EMPTY means the tenant configured no discounts;
    #: it does NOT mean the product cannot express them — that distinction is
    #: `DiscountResolution.modelled` and since 2026-08-20 it is always True.
    discounts: tuple[DiscountRule, ...] = ()
    #: R5's factor, as the tenant configured it. `Decimal("1.5")` is r10's.
    outside_city_factor: Decimal = Decimal("1")
    #: The services R5's factor does NOT touch. §A4 S2: *"BASE-S $8.00 (flat
    #: everywhere — the multiplier does NOT touch sewer)"*.
    outside_city_exempt_services: tuple[str, ...] = ()


# ── The resolved answer ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class ServiceResolution:
    """What one service on one bill resolved to."""

    service: str
    schedule_version_id: str
    connection_size: str
    base_charge: Decimal
    billable_quantity: Decimal | None
    meter_multiplier: Decimal
    money_factor: Decimal
    #: BR-RAT-088 — WHICH OBJECT SUPPLIED `base_charge`. Recorded rather than
    #: inferred, because during the cutover both objects can answer and a bill
    #: that cannot say which one priced it is a bill nobody can audit.
    #:
    #:   "named_charge_code"
    #:                  `CR-120-BRC06` · `BR-RAT-1025` — the RATE SCHEDULE NAMED
    #:                  this code and R4 took it. The EXPLICIT route, and the
    #:                  only value that says a person chose rather than the
    #:                  product inferred
    #:   "charge_code"  R4 resolved a code declaring `is_base` for this service
    #:                  — the INFERRED route, and still what every schedule that
    #:                  exists today produces
    #:   "schedule"     no such code exists for this tenant yet, so R3's size
    #:                  row still answers — the pre-BR-RAT-088 path, kept so a
    #:                  tenant that has not declared one still bills correctly
    #:   "not_set"      nobody defined AND bound a base for this account and
    #:                  there is no retired figure either — `base_charge` is
    #:                  `0`. PO ruling 2026-09-30: *"as a default you take 0 and
    #:                  complete the bill instead of refusing"*. It used to be
    #:                  `ChargeCodeAmountMissing`; billing warns on it by name.
    #:
    #: ⚠ **THE FIRST TWO ARE TWO ROUTES TO ONE FIGURE AND THEY ARE RECORDED
    #: APART ON PURPOSE.** On a schedule whose binding names the same code the
    #: lookup would have found, the amount is identical — which is exactly the
    #: state every schedule is in on the day `BR-RAT-1025` ships, and exactly
    #: why a bill that cannot say WHICH route answered is a bill nobody can
    #: audit through the cutover. It is the same argument `base_source` was
    #: written for in the first place, one ruling on.
    base_source: str = "schedule"
    #: BR-RAT-090 — WHERE `billable_quantity` CAME FROM, recorded for the same
    #: reason as `base_source`: a bill that cannot say how its quantity was
    #: arrived at is a bill nobody can audit, and the two paths produce numbers
    #: that look identical on the document.
    #:
    #:   "read"         a register difference x the meter multiplier (metered)
    #:   "asset_count"  a count of the service's ACTIVE assets on the unit
    #:                  (unmetered — three carts is a quantity of 3)
    quantity_source: str = "read"


@dataclass(frozen=True)
class DiscountResolution:
    """R6's answer, and it is deliberately not a list.

    `modelled is False` says the PRODUCT cannot express discounts. An empty
    `applied` beside `modelled=True` says this CUSTOMER is enrolled in nothing.
    They are different facts and a bill built on the second while the first is
    true is wrong by a discount, so the chain refuses to let a caller read one
    as the other.

    ⚠ **Since 2026-08-20 the first case no longer occurs** (DEF-361) — the tables
    exist and `resolve_discounts` always returns `modelled=True`. The field
    stays: removing it would change every caller's contract, and it is still the
    right place to record *the product cannot express this* should that ever be
    true again. **`applied` carries the discount's CONFIGURED value, not an
    amount off a bill** — R6 selects, `discount_pricing` prices.
    """

    modelled: bool
    applied: tuple[tuple[str, Decimal], ...] = ()
    unmodelled_reason: str = ""

    def total(self) -> Decimal:
        if not self.modelled:
            raise DiscountsNotModelled(self.unmodelled_reason)
        return sum((amount for _code, amount in self.applied), Decimal("0"))


@dataclass(frozen=True)
class Resolution:
    """The whole narrowing, for ONE account for ONE service period."""

    plan: PlanVersion
    services: tuple[ServiceResolution, ...]
    charge_codes: tuple[tuple[ChargeCode, Decimal], ...]
    discounts: DiscountResolution
    taxes: tuple[TaxRule, ...]

    def service(self, code: str) -> ServiceResolution:
        for resolved in self.services:
            if resolved.service == code:
                return resolved
        raise KeyError(f"{code!r} is not on this bill")


# ── R1 ──────────────────────────────────────────────────────────────────────


def resolve_plan(catalogue: Catalogue, account: AccountFacts, service_date: date) -> PlanVersion:
    """R1 — the plan version in force on the SERVICE-PERIOD END DATE.

    The account derives its plan from the unit (design §A1 selector 1), so the
    caller supplies the candidates for THIS unit; this step chooses among them
    by date and refuses when that is not exactly one.
    """
    in_force = [plan for plan in catalogue.plan_versions if plan.in_force_on(service_date)]
    if not in_force:
        raise NoPlanInForce(
            f"R1: account {account.account_no} has no plan version in force on "
            f"{service_date.isoformat()}. BR-RAT-007 prices a period on the terms in "
            "force AT THE SERVICE DATE; there is no fallback to today's plan, because "
            "that would silently re-price history."
        )
    if len(in_force) > 1:
        raise AmbiguousSchedule(
            f"R1: account {account.account_no} has {len(in_force)} plan versions in "
            f"force on {service_date.isoformat()} "
            f"({', '.join(sorted(p.plan_id + '@' + str(p.version) for p in in_force))}). "
            "A bill prices on one set of terms; this chain never picks.",
            message_key="rating.refusal.plansAmbiguous",
            message_params={"plans": len(in_force), "date": clerk_date(service_date)},
            clerk_detail=clerk_sentence(
                "rating.refusal.plansAmbiguous",
                plans=len(in_force),
                date=clerk_date(service_date),
            ),
        )
    return in_force[0]


# ── R2 ──────────────────────────────────────────────────────────────────────

_Version = TypeVar("_Version")


def in_force_precedence(version: Any) -> tuple[Any, ...]:
    """🔒 HUMAN-REVIEW-PENDING · `BR-RAT-1055` — **THE ONE ORDER IN WHICH
    VERSIONS OF ONE RATE SCHEDULE, ALL IN FORCE ON ONE SERVICE DATE, WIN.**

    PO ruling 2026-10-01 (`DEF-RAT-8004`, option A), verbatim: *"two rate
    versions in force on the same day - how come that will happen - we have to
    return only 1 row; A · Use the newest everywhere, and flag it on Check"*.

    Highest key wins: the newest `effective_from`, then the newest
    `created_at`, then the highest id. The caller has ALREADY narrowed to the
    candidates — activated (a dated `effective_from`), not superseded by a
    correction, window containing the service date — so this decides only
    *which* of several live rows prices, never *whether* a row may.

    **ONE FUNCTION, TWO READERS.** `selectors.in_force_version` (the nightly
    run, and every path built on `pricing_inputs`) and `resolve_schedule`
    below (the R1-R7 chain: the one-time bill, the move-out final bill,
    corrections) both pick through `pick_in_force`, so the two cannot drift
    apart again the way `DEF-RAT-8004` found them: the run billing **$21.60**
    while the move-out bill for the same household on the same date refused.

    Works on a rating `TariffVersion` row (id = `pk`) and on a `ScheduleVersion`
    (id = `version_id`); this module holds no model and imports none.

    ⚠ **A NEW OVERLAP CANNOT BE WRITTEN** — `ex_tariff_versions_no_overlap`
    (`rating/0047`) refuses it at COMMIT and every save locks the schedule
    (`CR-157-BRC10`). This rule exists for the overlaps written BEFORE that,
    which `rating/0046` deliberately did not resolve. The bill-run Check names
    them (`schedule_versions_overlap`) and `rat_resolve_schedule_overlap` is how
    a person removes one.
    """
    created = getattr(version, "created_at", None)
    ident = version.version_id if isinstance(version, ScheduleVersion) else version.pk
    return (
        version.effective_from,
        created.timestamp() if created is not None else float("-inf"),
        str(ident or ""),
    )


def ordered_in_force(candidates: Iterable[_Version]) -> list[_Version]:
    """`candidates`, the winner FIRST, by `in_force_precedence` — so a caller
    that must also NAME the losers (the Check's overlap warning) reads them in
    the order they lost."""
    return sorted(candidates, key=in_force_precedence, reverse=True)


def pick_in_force(candidates: Iterable[_Version]) -> _Version | None:
    """The ONE version that prices, or None when there is no candidate."""
    ordered = ordered_in_force(candidates)
    return ordered[0] if ordered else None


def resolve_schedule(
    catalogue: Catalogue, plan: PlanVersion, service: str, service_date: date
) -> ScheduleVersion:
    """R2 — exactly ONE rate schedule version per service. The gate is the point.

    CR-013 part 1: *"one service per schedule"*, and the plan binds one schedule
    per service. Two claiming one service is a configuration error the plan's
    activation gate is supposed to prevent; it refuses here too, because a gate
    that exists only upstream is absent the first time a row is written another
    way.
    """
    tariff_id = plan.schedules.get(service)
    if tariff_id is None:
        raise NoScheduleForService(
            f"R2: the plan {plan.plan_id}@{plan.version} covers {service!r} and binds no "
            "rate schedule to it. The service is not dropped quietly — a bill missing a "
            "service the customer pays for is a configuration problem a human must see.",
            message_key="rating.refusal.noScheduleBound",
            message_params={"service": service},
            clerk_detail=clerk_sentence("rating.refusal.noScheduleBound", service=_titled(service)),
        )
    bound = [
        version
        for version in catalogue.schedule_versions
        if version.tariff_id == tariff_id and version.in_force_on(service_date)
    ]
    if not bound:
        raise NoScheduleForService(
            f"R2: the plan {plan.plan_id}@{plan.version} binds schedule {tariff_id!r} to "
            f"{service!r} and no version of it is in force on "
            f"{service_date.isoformat()}. BR-RAT-007 prices on the version in force AT "
            "THE SERVICE DATE and there is no fallback to the newest one.",
            message_key="rating.refusal.noScheduleInForce",
            message_params={"service": service, "date": clerk_date(service_date)},
            clerk_detail=clerk_sentence(
                "rating.refusal.noScheduleInForce",
                service=_titled(service),
                date=clerk_date(service_date),
            ),
        )
    # ── `BR-RAT-1055` · `DEF-RAT-8004` — MORE THAN ONE IS NO LONGER A REFUSAL
    # (PO ruling 2026-10-01, option A: *"we have to return only 1 row; A · Use
    # the newest everywhere, and flag it on Check"*). Until that ruling this
    # raised `AmbiguousSchedule` while the nightly run billed the newest, so a
    # move-out final bill refused for a household the run had just charged
    # $21.60. It now answers through the SAME function the run's
    # `selectors.in_force_version` does, and the overlap is named on the
    # bill-run Check instead of stopping one door of the product.
    return pick_in_force(bound)


def resolve_schedule_with_override(
    catalogue: Catalogue,
    plan: PlanVersion,
    service: str,
    service_date: date,
    override_tariff_id: str | None = None,
) -> ScheduleVersion:
    """R2 WITH A `rate_override` DISCOUNT — the SCHEDULE SWAP (CR-052 W5 task 17).

    HUMAN-OWNED · HUMAN-REVIEW-PENDING (🔒 rating math — it decides WHICH price
    applies).

    ⛔ **THIS IS NOT THE SUBSIDY MECHANISM ANY MORE, AND NOTHING REACHES IT —
    `BR-RAT-961`, PO ruling 2026-08-31, `OQ-292` CLOSED.** Verbatim: *"we will
    apply standard rate and also provdie discount - thats how it should be
    handled; sicne there is subsidy we dont change rate schedule"*. **A subsidy
    is the STANDARD schedule plus an ordinary discount line**, so the one live
    use this function was built for is gone: `rate_override_target` — the read
    that would supply `override_tariff_id` — refuses by naming that ruling, and
    `DISCOUNT_TYPES_PRICEABLE` still excludes the type. The function is KEPT
    rather than deleted because cutting a discount type is its own change with
    its own blast radius (`BR-RAT-094`'s precedent for a closed column). **Do not
    wire it to a subsidy; a subsidy that arrives here is a configuration error.**

    ⚠ **THE PARAGRAPH BELOW IS THE SUPERSEDED READING, KEPT SO THE REASONING
    STAYS LEGIBLE (the shape `BR-RAT-094` used for its two amended tests).**
    CR-052 task 17 says these are fixed *in the chain's own terms* —
    *"`rate_override` needs a schedule swap in R2"* — and CR-013 part 3 gave the
    live use, *"Rate override is the mechanism behind 'Res Electric · Tiered
    (subsidy)'"*, **which is the sentence the PO superseded**. The argument was
    that a subsidy cannot be money taken off afterwards because the customer is
    billed from a DIFFERENT SCHEDULE, so every tier boundary, every block price
    and the minimum move together. **The PO's answer removes the premise rather
    than the arithmetic**: the customer is NOT billed from a different schedule,
    so there is nothing for the tiers to move with. `BR-RAT-068` — *a discount is
    an overlay, never a rate* — had said so since 2026-08-19, and this function
    contradicted it in silence because nothing could ever call it.

    **WORKED, on r10's own subsidy shape.** Standard residential water prices
    `18.72 kgal` through `0–5 @ 3.20 / 5–15 @ 4.80 / 15+ @ 7.20` = `16.00 +
    48.00 + 26.78 = 90.78`. The subsidy schedule prices the same meter through
    `0–5 @ 1.60 / 5–15 @ 2.40 / 15+ @ 3.60` = `8.00 + 24.00 + 13.39 = 45.39`.
    The override is worth **`$45.39`** on that bill — and it is worth a different
    figure on every other bill, which is precisely why it cannot be stored as an
    amount.

    ⚠ **`override_tariff_id` IS AN ARGUMENT AND NOT A LOOKUP, AND UNDER
    `BR-RAT-961` IT NEVER BECOMES ONE.** `discount_versions` has `discount_type =
    'rate_override'` and **no FK to a tariff**. That was `OQ-292`, and the
    question is now CLOSED **without the column being added** — the PO ruled the
    mechanism out rather than deciding where to record it, so the missing column
    is a settled absence and not a pending one. `rate_override_target` says so in
    the refusal it raises. ⚠ **A LANE THAT ADDS `override_tariff_id` IS
    REVERSING A RULING**, not completing this function.

    ⚠ **AND NOTHING CALLS THIS ON A BILL — TWO REASONS NOW, AND ONE OF THEM
    CHANGED TODAY (`BR-RAT-962`).** `DEF-438`: the chain has no production
    caller, and CR-051's second hard rule forbids switching an R-step outside the
    ruled cutover. And `discounts.DISCOUNT_TYPES_PRICEABLE` is UNCHANGED, so
    activation still refuses the type — but the REASON it is refused is no longer
    *"the target has nowhere to be stored"*; it is *"there is nothing left for
    this type to do"*. A discount that activated and reached the LIVE path would
    still hit `discount_pricing`'s `DiscountTypeNotPriceable` and break the bill.
    **The arithmetic here is ready for a mechanism the product has ruled it does
    not use**, which is the honest description of dead-but-kept code.

    `None` is no override, which is every account in the product, and the answer
    is then byte-identical to `resolve_schedule`.
    """
    ordinary = resolve_schedule(catalogue, plan, service, service_date)
    if override_tariff_id is None:
        return ordinary
    if override_tariff_id == plan.schedules.get(service):
        # An override naming the schedule the plan already binds is not an
        # override. Returned rather than refused: it is a configuration that
        # says nothing, not one that says something impossible.
        return ordinary
    candidates = [
        version
        for version in catalogue.schedule_versions
        if version.tariff_id == override_tariff_id
    ]
    if not candidates:
        raise RateOverrideUnusable(
            # CR-013 part 3, *"subsidy granted is reportable"* — the id stays in
            # this comment and out of the clerk's sentence (G28 / CR-016).
            f"R2: a rate-override discount on {service!r} names a rate schedule "
            f"({override_tariff_id!r}) that this utility does not have. The bill stops "
            "rather than quietly charging the ordinary rate: a subsidy that was granted "
            "and not applied is one the customer finds out about, not the utility.",
            message_key="rating.refusal.overrideScheduleMissing",
            clerk_detail=clerk_sentence("rating.refusal.overrideScheduleMissing"),
        )
    # CR-013 part 3's FIRST named refusal — a MISMATCHED SERVICE. Checked before
    # the date, because a schedule for the wrong service is wrong on every date
    # and the clearer sentence is the one a utility can act on.
    wrong_service = [version for version in candidates if version.service != service]
    if wrong_service:
        raise RateOverrideUnusable(
            # CR-013 part 3's first named refusal (mismatched service).
            f"R2: a rate-override discount on {service!r} names a rate schedule "
            f"({override_tariff_id!r}) that prices {wrong_service[0].service!r} "
            "instead. A subsidised electricity schedule cannot price a water meter. "
            "Point the discount at a schedule for this service.",
            message_key="rating.refusal.overrideWrongService",
            clerk_detail=clerk_sentence("rating.refusal.overrideWrongService"),
        )
    # CR-013 part 3's SECOND — RETIRED, which here means *no version in force on
    # the service date*. BR-RAT-007 prices a period on the terms in force AT THE
    # SERVICE DATE and there is no fallback to the newest version, exactly as
    # `resolve_schedule` states for an ordinary binding.
    in_force = [version for version in candidates if version.in_force_on(service_date)]
    if not in_force:
        raise RateOverrideUnusable(
            # CR-013 part 3's second named refusal (retired), and BR-RAT-007 is
            # why the newest version is not substituted.
            f"R2: a rate-override discount on {service!r} names a rate schedule "
            f"({override_tariff_id!r}) that was not in force on "
            f"{service_date.isoformat()}. A period is priced on the terms that applied "
            "at the time, so a schedule that has been retired cannot price it and a "
            "newer one is not put in its place.",
            message_key="rating.refusal.overrideNotInForce",
            clerk_detail=clerk_sentence("rating.refusal.overrideNotInForce"),
        )
    # `BR-RAT-1055` — the same one rule as `resolve_schedule`, whether the
    # schedule arrived through the plan or through a discount.
    return pick_in_force(in_force)


def rate_override_target(discount_code: str) -> str:
    """WHICH schedule a `rate_override` discount swaps to — **NOTHING NEEDS THIS.**

    ⚖️ **BR-RAT-961 · PO RULING 2026-08-31, `OQ-292` CLOSED — AND CLOSED BY
    DISSOLUTION, NOT BY AN ANSWER.** Verbatim: *"we will apply standard rate and
    also provdie discount - thats how it should be handled; sicne there is
    subsidy we dont change rate schedule"*.

    **THIS FUNCTION USED TO BE THE PRIME DIRECTIVE'S STUB FOR AN OPEN QUESTION.
    IT IS NOT ONE ANY MORE**, and the distinction matters to the next reader: an
    `OQ-###` stub means *a person still has to decide this*. A person decided.
    What is left is a door onto a mechanism the product does not use, and it
    stays shut for a stated reason rather than a pending one.

    **THE RULING IS NONE OF THE THREE OPTIONS `OQ-292` OFFERED.** We asked which
    of an `override_tariff_id` FK, a plan variant, or cutting the type; the PO
    answered the business question underneath instead. `Res Electric · Tiered
    (subsidy)` is **the standard tiered schedule plus a discount line**, so the
    pointer this function would read is not missing — it is not wanted.

    **WORKED END TO END, on the seeded estate, and the three figures are the
    rule.** A `620 kWh` customer on `Res Electric · Tiered`
    (`0–500 @ 0.11 / 500–1,000 @ 0.14 / 1,000+ @ 0.19`) is charged the STANDARD
    schedule — `500 × 0.11 + 120 × 0.14 =` **`$71.80`**; the seeded `CAP /
    low-income credit` programme takes off **`$25.00`**; the customer pays
    **`$46.80`**, with both numbers printed. Through the swap this function was
    written for, a half-price subsidy schedule would have printed ONE line of
    **`$35.90`** and nothing on the bill would say a subsidy had been granted.

    ⚠ **AND THE RULING RESTORES A RULE WE ALREADY HAD.** `BR-RAT-068` (CONFIRMED
    2026-08-19) is that *a discount is an overlay, never a rate ... it therefore
    owns no tier, no schedule and no connection-size row*, and that *the bill
    shows the full tariff amount and the reduction as its own line, so subsidy
    granted is reportable*. **`rate_override` contradicted that CONFIRMED rule
    from the day it was stored**, and nothing noticed because the type was never
    priceable — a rule and a stored enum disagreeing in silence.

    `resolve_schedule_with_override` and `RateOverrideUnusable` are KEPT and are
    now unreachable from any production path. Cutting the type is its own change
    with its own blast radius and is deliberately not taken here; the precedent
    is `BR-RAT-094`, which kept a closed column and said so: *"dropping it is a
    separate change and needs its own CR."*
    """
    raise NotImplementedError(
        "BR-RAT-961 (PO ruling 2026-08-31) — a subsidy is priced on the STANDARD rate "
        "schedule with an ordinary discount line on top, so nothing swaps a schedule "
        f"and there is no override target to read ({discount_code!r}). This is not an "
        "open question waiting on a column: the mechanism was ruled out, and "
        "BR-RAT-068 already said a discount is an overlay that owns no schedule. If a "
        "caller reaches this, it wants a discount line, not a different rate table."
    )


# ── R3 ──────────────────────────────────────────────────────────────────────


def resolve_minimum_bill(schedule: ScheduleVersion, meter: MeterFacts) -> Decimal | None:
    """DEF-360 — the minimum bill for THIS connection size, or None.

    Three outcomes, and the middle one is the reason this is a function rather
    than a dictionary lookup:

        size named, value stated  -> that minimum
        size named, value None    -> NO minimum for this size (r10's em-dash)
        size not named            -> the version's scalar minimum (or None)

    The fallback is what makes the column additive: every schedule written
    before CR-013 P1 names no size and therefore prices exactly as it did.
    """
    if meter.connection_size in schedule.minimum_bill_by_size:
        return schedule.minimum_bill_by_size[meter.connection_size]
    return schedule.minimum_bill


def resolve_tiers(
    schedule: ScheduleVersion, meter: MeterFacts, default: tuple[Decimal, ...]
) -> tuple[Decimal, ...]:
    """DEF-360 — the tier prices for THIS size, falling back to the schedule's.

    r10's Residential Water prices 5/8", 3/4", 1" and 1.5" identically at
    `3.20 / 4.80 / 7.20` and prices 2" at `3.45 / 5.10 / 7.70`. A per-size tier
    cannot be derived from a base, a multiplier or the size itself — it can only
    come from a row on the schedule, which is the whole reason the schedule
    needs a size axis independently of who owns the base.
    """
    return schedule.tiers_by_size.get(meter.connection_size, default)


#: **THIS SERVICE HAS NO SIZE**, as a value R3 and R4 both understand.
#:
#: It has always been the unmetered branch's answer — `_size_key` returns it for
#: an unmetered service whose assets state no class, and `resolve_charge_codes`
#: narrows on it so a code with no size rows matches, which is exactly right for
#: a flat per-cart price. `DEF-2851` gave it a second, ruled meaning: a METERED
#: service the Product Owner ruled to have no size class at all (`BR-RAT-015` —
#: sewer is a share of the water usage charge).
#:
#: ⚠ **IT IS NEVER "nobody recorded a size".** That is `DEF-514`, it is a data
#: gap a human fixes, and `_assert_service_is_ruled_sizeless` is what keeps the
#: two apart — an empty string reaching R3 for a service that HAS a ladder
#: refuses by name. Collapsing them would price a water connection whose ladder
#: is merely unconfigured.
NO_SIZE = ""


def resolve_served_size(schedule: ScheduleVersion, meter: MeterFacts) -> str:
    """**R3 — DOES THIS SCHEDULE SERVE THIS SIZE?** Membership, and nothing else.

    ⚠ **THIS IS `DEF-2823`'s FIX AND IT IS `BR-RAT-088` EXECUTED LITERALLY.**
    The ruling's own consequence clause: *"R3's refusal semantics are unchanged
    — a size absent from the schedule still means not served — but the base
    itself now resolves through R4; `ScheduleVersion.size_rows` stops carrying
    money."* R3 answers WHICH SIZE; R4 answers WHAT IT COSTS. One function
    answering both is what made the gate read a column the product retired.

    Two outcomes, and NEITHER of them is money:

        size on the schedule's axis  -> that size, for R4 to price
        size absent from the axis    -> REFUSE (this size is not served)

    **The refusal is unchanged in word and in force** — the same
    `SizeNotServed`, the same step, the same sentence — because the PO ruled it
    correct twice: `BR-RAT-120` (*"Read the second way, the system refuses
    bills that price perfectly well today"*) and again on 2026-08-28, an
    unpriced size is REFUSED and never substituted. Nothing here changes
    WHETHER a size refuses; it changes only WHERE the price comes from.

    ⚠ **AND THE BLANK-VALUE REFUSAL IS NOT DELETED — IT MOVED TO THE STEP THAT
    OWNS IT.** `resolve_size_row` below still refuses a blank, and the chain's
    equivalent now fires at R4: `charge_code_amount` refuses a size the code
    does not price (*"states no amount for connection size …"*), and `resolve`
    refuses by name when NEITHER the charge code NOR the legacy scalar states a
    base. A blank still stops a bill; it stops it where the money lives.
    """
    if meter.connection_size == NO_SIZE:
        # ── A SERVICE RULED TO HAVE NO SIZE AXIS AT ALL (DEF-2851) ────────
        # ⚠ THIS IS NOT A MISSING VALUE AND MUST NEVER BECOME ONE. `""` is the
        # same "this service has no size" the UNMETERED branch has always used
        # (`_size_key`: *"a code with no size rows matches, which is exactly
        # right for a flat per-cart price"*). What is new is that a METERED
        # service can be ruled sizeless too: `BR-RAT-015` prices SEWER as a
        # share of the water usage charge, so a sewer connection has no size
        # class and never will.
        #
        # **Confirmed against the ratified register, never assumed from an
        # empty `size_rows`.** An empty size map has TWO readings — *ruled to
        # have none* and *nobody has configured the ladder yet* — and
        # `service_size_classes` is the module that keeps them apart on
        # purpose: an empty tuple for sewer, a RAISE for a service whose bands
        # the PO never saw. Reading the schedule alone would collapse them and
        # bill a water connection whose ladder is merely unconfigured.
        #
        # DEF-2851: without this branch the shadow could not evaluate ONE
        # account of ANY utility that bills sewer — 116 of 163 accounts across
        # three utilities, every one of them `service 'sewer' has no connection
        # size` — and R3 refused a size that correctly does not exist.
        #
        # ── `DEF-RAT-8822` · AND A METER NOBODY SIZED, WHERE THE BASE IS ONE
        # PRICE FOR EVERY SIZE (PO 2026-10-01, option A) ──────────────────
        # *"Hold back only where the price depends on the size."* A banded
        # service whose base code prices *All sizes* only passes with no size
        # — billed with no minimum, and the bill-run Check says *Meter size not
        # recorded*. A size-priced base still refuses below (`BR-RAT-120`,
        # NARROWED to size-priced bases, not superseded).
        _assert_service_is_ruled_sizeless(
            schedule.service, base_priced_by_size=schedule.base_priced_by_size
        )
        return NO_SIZE
    if meter.connection_size not in schedule.size_rows:
        # ⚠ **THE SENTENCE NAMES THE OBJECT THE AXIS CAME FROM (PO ruling
        # 2026-09-01).** Until that ruling there was only one possible answer
        # and the sentence hardcoded it. The charge code can now be the axis,
        # and a refusal that names the rate schedule then sends the clerk to a
        # screen where the fix is not — which makes a curable refusal
        # uncurable, the one thing `BR-RAT-120` weighed its cost against.
        where = (
            f"the base charge code pricing {schedule.service!r}"
            if schedule.size_axis_source == "charge_code"
            else f"the rate schedule version {schedule.version_id} pricing {schedule.service!r}"
        )
        raise SizeNotServed(
            f"R3: connection size {meter.connection_size!r} has no row on {where}. The "
            "bill refuses rather than charging $0.00 for a size the utility has never "
            "priced."
        )
    return meter.connection_size


def service_prices_by_size_class(service: str) -> bool:
    """**DOES THIS SERVICE'S PRICE VARY BY SIZE CLASS?** — the question R3 means.

    ⚠ **THIS IS `DEF-3098`, AND IT IS A DIFFERENT QUESTION FROM THE ONE THE CHAIN
    USED TO ASK.** Three places in this product needed to know whether a service
    is priced BY BAND, and all three asked *"does this service have any size
    class rows?"* instead. Those two questions had the same answer for as long as
    only banded services had rows, so the proxy was sound and nothing recorded
    that it was a proxy.

    `CR-062` group A (2026-09-02) broke it deliberately. Solar, battery, storm
    water and broadband gained a **CATALOGUE OF INSTALLABLE EQUIPMENT** — ten
    panel types, six battery blocks, five property sizes, three broadband tiers
    — and a catalogue is not a rate axis. Such a service HAS rows and is NOT
    banded: its price is one flat figure per kW (or per ERU, per Mbps) and the
    billable quantity is the SUM of what is installed. Three panels of 2 kW,
    4 kW and 8 kW are ONE 14 kW array on ONE connection, not three connections
    of three different sizes.

    **WHAT IT COST TO KEEP ASKING THE OLD QUESTION.** A battery or solar
    schedule stating no per-size rows flipped from one ladder at the blank size
    to no size priced at all, measured on a bare schedule beside the identical
    sewer one:

        assert battery.size_rows == sewer.size_rows
        AssertionError: assert {} == {'': Decimal('8.000000')}

    An empty axis refuses every meter by name, so **no battery or solar customer
    on such a schedule could be billed** — which is `DEF-2408`'s five-day outage
    arriving from the opposite direction one week later.

    **THE ANSWER IS EXACT AND IT IS TENANCY'S, NOT AN INFERENCE OF OURS.**
    `capacity_uom_for_service` returns the unit a service SUMS in and `None`
    when it does not sum, and that module's own docstring calls it *"the one
    call that tells the two billing shapes apart"*. A `None` therefore means
    *this service does not sum* — either because its rows are BANDS (water's
    pipe diameters, trash's carts and dumpsters) or because it was ruled to have
    no rows at all (sewer). Only the first of those prices by band, so the rows
    are consulted as well.

    ⚠ **TRASH IS THE CASE THAT PROVES THIS IS NOT "capacity services get a
    pass".** Trash is *capacity based* in the PO's own words and is BANDED here:
    the SIZE picks the rate and the COUNT multiplies it (*"Cart sizes will
    decide price X how many Cart"*), and its three carts are GALLONS while its
    four dumpsters are CUBIC YARDS, so no total exists in any unit. It answers
    `True` and keeps the banded axis it has always had.

    Raises exactly what `size_classes_for_service` raises — `SizeClassNotRuled`
    for a dimension nobody has ruled (thermal steam, OQ-560) and `KeyError` for
    a service this product does not recognise. Neither is answered here: the
    prime directive forbids resolving an unruled boundary by choosing a value.

    Imported inside the function on purpose: this module is otherwise pure
    stdlib and `service_size_classes` holds no model and issues no query, which
    is the same local-import precedent `apps/rating/sample_data.py` sets.
    """
    from apps.tenancy import service_size_classes

    if service_size_classes.capacity_uom_for_service(service) is not None:
        return False  # a CAPACITY service — it sums, it does not band
    return bool(service_size_classes.size_classes_for_service(service))


def _assert_service_is_ruled_sizeless(service: str, *, base_priced_by_size: bool = True) -> None:
    """REFUSE unless a blank size is a FACT about this service rather than a gap.

    Two services legitimately reach R3 with no connection size, and they get
    there by different routes:

        ruled to have none    sewer (BR-RAT-015) — a share of the water usage
                              charge, reading no register of its own.
        priced by capacity    solar, battery, storm water, broadband — nothing
                              meters a solar panel's "connection size", and the
                              price does not vary by band anyway (DEF-3098).

    A BANDED service is the case this still refuses: it HAS a rate axis, so an
    empty size is a fact nobody recorded — DEF-514, a data gap a human fixes on
    a screen — and pricing it would pick a tier ladder, which is money, on the
    strength of nothing.

    ⚠ **THE NAME IS NOW NARROWER THAN WHAT IT CHECKS, AND THAT IS DELIBERATE
    RATHER THAN OVERLOOKED.** *"ruled sizeless"* is what the ONE ruled-empty
    service is, and the question underneath is `service_prices_by_size_class` —
    read that docstring before changing this one. The name is kept because
    `resolve_served_size`'s own comment cites it and DEF-2851's trace is written
    against it.

    ⚠ **`base_priced_by_size=False` IS THE ONE WAY A BANDED SERVICE PASSES
    (`DEF-RAT-8822`, PO 2026-10-01, option A).** Where the base charge code is
    one *All sizes* price, an unsized meter cannot be billed the wrong size's
    base, so it is billed — `$8.00 + 1 kgal × $4.4096 = $12.41`, no minimum,
    the Check warning *Meter size not recorded*. The two refusals above it
    (bands never ruled, a service this product does not know) still fire: they
    are about not knowing the service, not about the base.
    """
    from apps.tenancy import service_size_classes

    try:
        prices_by_size = service_prices_by_size_class(service)
    except service_size_classes.SizeClassNotRuled as unruled:
        raise SizeNotServed(
            f"R3: {service!r} has no connection size on this meter and its size bands "
            f"have never been ruled, so there is nothing to check the absence against "
            f"({unruled}). The bill refuses rather than pricing a service whose size "
            "dimension the utility has not been asked about."
        ) from unruled
    except KeyError as unknown:
        raise SizeNotServed(
            f"R3: {service!r} is not one of the ten utility services, so whether it "
            "carries a connection size is not a question this product can answer "
            f"({unknown})."
        ) from unknown
    if prices_by_size and base_priced_by_size:
        ratified = service_size_classes.size_classes_for_service(service)
        raise SizeNotServed(
            f"R3: no connection size was resolved for {service!r}, and {service!r} DOES "
            f"have a ratified size ladder ({', '.join(code for code, _ in ratified)}). "
            "An empty size here is a fact nobody has recorded (DEF-514), not a service "
            "ruled to have none — and a size chosen for it would choose a tier ladder, "
            "which is money, on the strength of nothing."
        )


def _legacy_schedule_base(schedule: ScheduleVersion, meter: MeterFacts) -> Decimal | None:
    """The version's RETIRED scalar for a size R3 has already served. Never a gate.

    `BR-RAT-088` retired `tariff_versions.base_charge` and `RateScheduleWizard`
    removed its control, so this answers `None` for every schedule version a
    utility creates through this product today. It answers a figure for a
    tenant provisioned BEFORE the ruling, and that is the only reason it
    exists: `resolve` uses it as R4's fallback so such a tenant keeps billing
    the base it has always billed, with `base_source="schedule"` recorded on
    the line so the migration is observable rather than assumed.

    ⚠ **IT RAISES NOTHING.** The size has already passed R3; a blank here is
    *the charge code owns this now*, not *this size is not served*, and
    refusing on it is precisely `DEF-2823`.

    ── A STORED `0.00` HERE MEANS **NOT STATED** (`DEF-2830`, settled 2026-08-31)
    The live path and this one read the same stored column and used to read it
    DIFFERENTLY, which is worth **`$8.00` a month per connection** on every
    tenant configured before `BR-RAT-088`:

        `gather._base_charge_for` treated a schedule `0.00` as *nobody filled
        this in* — its `schedule_amount != 0` carve-out — and billed the plan's
        `$8.00`. ⚠ **PAST TENSE FROM 2026-09-28 (`DEF-BIL-7170`): it reads
        neither column now** and the carve-out is deleted with them. The
        judgment recorded below is unaffected — it is about what THIS
        function returns for a stored zero — and the two paths can no longer
        disagree about a column neither of them reads.
        This function used to hand back `Decimal("0")`, so `resolve` read it as
        *the charge is nothing* and billed `$0.00`.

    **Both readings are defensible and only one can be right, and the judgment
    is recorded rather than asked** (`12-governance/02-decision-log.md`,
    2026-08-31 — hard-won law 13: a judgment that preserves current behaviour
    needs no ruling). **NOT STATED wins.** The opposite reading would give the
    standing charge away because somebody left a box alone rather than because
    they decided anything, and a genuinely free connection is a thing a utility
    should have to state. The PO ruling of 2026-08-19 (*"print $0.00"*) is not
    contradicted: it is about a stored zero on a bill that is already priced,
    not about which of three objects sourced the base.

    **THIS MOVES NO BILL.** `resolution_switch.SERVED_BY_CHAIN_DEFAULT` is empty,
    so nothing in this product prices from the chain today; the live path's
    reading is unchanged and remains the one every bill is produced from.

    **WHAT IT DOES CHANGE IS WHAT THE CHAIN DOES INSTEAD**, and that is stated
    plainly rather than left to be discovered: with no `is_base` charge code and
    a schedule zero, R4 now REFUSES by name — *nobody has stated this service's
    base* — where the live path bills the plan's figure. That is a divergence
    the switch reports as a refusal instead of billing `$0.00` silently, and it
    is a **migration precondition, not a bug**: `BR-RAT-088` says such a tenant
    must declare a base charge code, and the chain is the ruled path.
    """
    stated = schedule.size_rows.get(meter.connection_size)
    if stated is not None and stated == 0:
        return None
    return stated


def resolve_size_row(schedule: ScheduleVersion, meter: MeterFacts) -> Decimal:
    """THE PRE-`BR-RAT-088` R3: the size's membership AND its price, together.

    ⚠ **THE CHAIN NO LONGER PRICES FROM THIS, AND THAT IS `DEF-2823`.** It is
    kept because its two refusals are two DIFFERENT rulings and only one of
    them moved: the membership half is `BR-RAT-120`, still live and now owned
    by `resolve_served_size` above — which this function CALLS, so there is one
    implementation of the ruling and not two that can drift. The blank half is
    `CR-013 part 1` / `DEF-277` read against a column `BR-RAT-088` retired.

    Three outcomes and only one of them is a price:

        size absent from the table   -> REFUSE (this size is not served)
        size present, base is BLANK  -> REFUSE (CR-013 part 1's own words)
        size present, base is 0.00   -> 0.00, a price (PO 2026-08-19)

    A caller that wants *"what does the SCHEDULE's own column say"* — the
    migration reader, and the tests that pin the pre-ruling behaviour — asks
    this. A caller pricing a bill asks `resolve_served_size` and then R4.
    """
    size = resolve_served_size(schedule, meter)
    base = schedule.size_rows[size]
    if base is None:
        raise SizeNotServed(
            f"R3: connection size {meter.connection_size!r} is on the rate schedule "
            f"version {schedule.version_id} for {schedule.service!r} with a BLANK base "
            "charge. CR-013 part 1: a blank base means THIS SIZE IS NOT SERVED "
            "(DEF-277). A stored 0.00 would be a price and would bill $0.00; a blank "
            "is the absence of one and refuses.",
            message_key="rating.refusal.sizeBlankBase",
            message_params={"service": schedule.service},
            clerk_detail=clerk_sentence(
                "rating.refusal.sizeBlankBase", service=_titled(schedule.service)
            ),
        )
    return base


# ── R3b ─────────────────────────────────────────────────────────────────────


def billable_quantity(meter: MeterFacts, register_quantity: Decimal | None) -> Decimal | None:
    """R3b — register difference x meter multiplier, BEFORE any price is applied.

    ⚠ THE ORDER IS THE WHOLE RULE (BR-RAT-001, and the PO's correction of
    2026-08-19). A x10 register reading **62** is **620 kWh**, which lands in
    tier 2; **62** never leaves tier 1. Applying the multiplier to the MONEY
    afterwards would price 62 kWh at tier-1 rates and then multiply by ten — a
    different number, and one that looks entirely plausible on the document.

    `None` in, `None` out: a service with no read has no billable quantity, and
    a zero would state that the meter was read and showed nothing.

    ⚠ **AND THE TWO CHECKS BELOW ARE IN THIS ORDER ON PURPOSE (`DEF-2875`,
    2026-09-01) — THEY USED TO BE THE OTHER WAY ROUND.** The multiplier refusal
    ran FIRST, so a service with NOTHING TO MULTIPLY was refused for the missing
    factor of a meter it does not have. `BR-RAT-015` prices sewer as a share of
    the water usage charge: no meter, no register, no factor. Measured over
    three seeded utilities on 2026-09-01, that refusal was the whole reason
    **116 of 163 accounts could not be evaluated at any step at all**, while the
    live path billed their sewer base charge without difficulty.

    **The guard is not weakened and the money it protects is untouched.** Its
    danger — *"a x10 register whose multiplier nobody recorded bills a tenth of
    the customer's consumption"* — needs a register difference to exist before
    it can be understated. Where `register_quantity` is None nothing is priced
    from a quantity on either path, so there is nothing to get wrong; where
    there IS a difference and no factor, the refusal below fires exactly as it
    always did. That case is asserted in
    `06-backend/tests/test_def2875_meterless_service.py` and was proved RED.
    """
    if register_quantity is None:
        return None
    if meter.multiplier is None:
        raise MeterMultiplierUnstated(
            f"R3b: the meter on {meter.service!r} states no multiplier, so the register "
            "difference cannot become a billable quantity. BR-MET-056 stores the factor "
            "USED; an absent factor is not 1 — a x10 register whose multiplier nobody "
            "recorded bills a tenth of the customer's consumption, on a document that "
            "looks entirely normal."
        )
    return register_quantity * meter.multiplier


def allowance_deducted_quantity(
    service: str,
    billable: Decimal | None,
    billed_unit: str,
    allowance: Decimal | None = None,
    allowance_unit: str | None = None,
) -> Decimal | None:
    """R3b WITH A `usage_allowance` DISCOUNT — the QUANTITY DEDUCTION (task 17).

    HUMAN-OWNED · HUMAN-REVIEW-PENDING (🔒 rating math — it decides how much of a
    customer's consumption is priced at all).

    **THE CR STATES THIS IN THE CHAIN'S OWN TERMS AND THE PLACE IS THE WHOLE
    RULE:** *"`usage_allowance` [needs] a quantity deduction before the tier
    walk"*. It happens HERE, beside the meter multiplier, and not at R6, because
    R6 subtracts MONEY and this subtracts UNITS — and on a tiered schedule the
    two are different numbers.

    **WORKED, and this is the figure that makes the placement visible.** Water
    priced `0–5 @ 3.20 / 5–15 @ 4.80 / 15+ @ 7.20`, meter reads `18.72 kgal`,
    the programme allows `2 kgal` free:

        no allowance   5 x 3.20 + 10 x 4.80 + 3.72 x 7.20 = 16.00 + 48.00 + 26.78
                       = **90.78**
        deducted here  16.72 kgal -> 5 x 3.20 + 10 x 4.80 + 1.72 x 7.20
                       = 16.00 + 48.00 + 12.38 = **76.38**

    The allowance is worth **`$14.40`** — the two kilogallons come off the TOP
    block, at `7.20`, because that is what "deduct before the tier walk" means.
    Applied at R6 as a money credit at the average price (`90.78 / 18.72 =
    4.85/kgal`) it would be **`$9.70`**, and the customer would be `$4.70` worse
    off on one bill for a discount the utility believes it granted.

    ⚠ **THE UNIT COMES FROM THE SERVICE — `BR-RAT-960`, PO ruling 2026-08-31,
    `OQ-291` CLOSED.** Verbatim: *"a) Take the unit from the service it's
    attached to"*. `allowance_unit` is therefore **an override, not the source**:
    left `None` — which is what every caller under the ruling passes, because no
    column stores one — the unit is RESOLVED from `billed_unit` through
    `usage_allowance_units`, and a service that states none REFUSES rather than
    being given a default (CLAUDE.md hard rule 3 has no "assume kWh" branch).

    **A CALLER MAY STILL STATE ONE, AND THE MISMATCH REFUSAL BELOW IS WHY THAT
    IS WORTH KEEPING.** A stated unit is an ASSERTION about the service, and
    `BR-RAT-038`'s *"no silent conversion"* is what catches an assertion that is
    wrong: two free kgal cannot be taken off `620 kWh`, and this chain holds no
    conversion factor and performs none. Under the ruling the two agree by
    construction on every production path, so the branch is defence in depth
    against a caller that resolves the unit itself and resolves it from the
    WRONG service — which is exactly the failure `OQ-291` described.

    ⚠ **NOTHING CALLS THIS ON A BILL, AND THE REASON CHANGED IDENTITY TODAY —
    `BR-RAT-962`.** `OQ-291` is CLOSED, so it is no longer the blocker; what
    remains is `DEF-438` (the R1–R7 chain has no production caller) and the fact
    that `DISCOUNT_TYPES_PRICEABLE` gates `discount_pricing._raw_reduction`,
    which is **R6, a subtraction of MONEY**. Adding `usage_allowance` to that set
    would price this `2 kgal` allowance as **`$2.00` off** instead of the
    **`$14.40`** worked above — a `$12.40` error on one bill, in the customer's
    disfavour. The set stays as it is; widening it is the ruled cutover's step 5,
    gated on its step 4.

    `None` allowance is no allowance and the answer is the quantity unchanged,
    which is every account in the product. `None` billable stays `None`: a
    service with no read has no billable quantity and an allowance cannot invent
    one.
    """
    if billable is None or allowance is None:
        return billable
    if not allowance_unit:
        # BR-RAT-960 — THE RULED DERIVATION, and the one place it happens. This
        # used to be a refusal ("no unit of measure is recorded with it"); the
        # PO ruled on 2026-08-31 that the unit comes from the service, so the
        # absent-unit case now RESOLVES. `usage_allowance_units` still refuses
        # when the SERVICE states no unit — the refusal moved one fact along, it
        # did not disappear.
        allowance_unit = usage_allowance_units(service, billed_unit)
    if allowance_unit != billed_unit:
        raise UsageAllowanceUnusable(
            # BR-RAT-038 — no silent conversion.
            f"R3b: a usage-allowance discount on {service!r} allows {allowance} "
            f"{allowance_unit!r} and this service is billed in {billed_unit!r}. The two "
            "cannot be subtracted and nothing here converts between them. State the "
            "allowance in the unit the meter is billed in."
        )
    if allowance < 0:
        raise UsageAllowanceUnusable(
            f"R3b: a usage-allowance discount on {service!r} states a NEGATIVE allowance "
            f"({allowance}). An allowance adds units to a customer's bill in that "
            "direction, which is a surcharge nobody authorised."
        )
    remaining = billable - allowance
    # An allowance larger than the consumption bills NOTHING, never a negative
    # quantity: a negative would walk the tiers backwards and price as a credit
    # the programme never granted. The BASE charge is untouched — it is not a
    # usage line and BR-BIL-028's own distinction applies (a customer who used
    # less than their allowance still pays to be connected).
    return remaining if remaining > 0 else Decimal("0")


def usage_allowance_units(service: str, service_billed_unit: str | None) -> str:
    """WHAT UNIT a `usage_allowance` is measured in — **the SERVICE's own unit**.

    ⚖️ **BR-RAT-960 · PO RULING 2026-08-31, `OQ-291` CLOSED.** Verbatim:
    *"a) Take the unit from the service it's attached to"*.

    **THE FAILURE THIS REMOVES, in the ruling's own worked terms.** A water
    programme allowing `2` free kgal and an electric one allowing `2` free kWh
    are the SAME STORED ROW — `discount_versions.value = 2`, and no column
    anywhere carries a unit. Resolved against the service, that one row is worth
    **`$14.40`** on water (`18.72 kgal` at `0–5 @ 3.20 / 5–15 @ 4.80 /
    15+ @ 7.20`: `90.78 → 76.38`) and **`$0.28`** on electric (`620 kWh` on
    `Res Electric · Tiered`: `71.80 → 71.52`). Fifty-one times the money, decided
    entirely by which service the discount is attached to — which is why the
    answer had to come from somewhere and not from the discount row.

    ⚠ **WE RECOMMENDED A COLUMN AND WERE OVERRULED, AND THE ARGUMENT IS KEPT
    HERE BECAUSE IT STILL CONSTRAINS THIS FUNCTION.** `OQ-291` recommended
    option (B), a `value_uom` column, on CLAUDE.md hard rule 3 — *"consumption:
    always with an explicit unit; never assume"* — because deriving a unit is an
    INFERENCE and hard rule 3 asks for a stated fact. The PO chose the narrower,
    cheaper answer, and it is theirs.

    **SO HARD RULE 3 SURVIVES IN THE ONE WAY IT STILL CAN, AND BOTH HALVES ARE
    IN THIS FUNCTION:**

      1. **A service that states NO unit still REFUSES.** The ruling supplies a
         SOURCE for the unit, not a DEFAULT for it. There is no "assume kWh"
         branch here and there must never be one — that is precisely the assumed
         unit hard rule 3 forbids, and four of the ten catalog services (sewer,
         solar, thermal/heat, battery) carry no stated default at all, so this
         branch is reachable on a real tenant rather than theoretical.
      2. **The inference is SHOWN, never silent.** The unit this returns is
         printed beside the figure wherever the allowance is displayed
         (`selectors.discount_value_display` serves `2.00 kgal`, not a bare
         `2.00`) and is named in every refusal below. An inference a reader can
         see is a different thing from an assumption they cannot.

    ⚠ **AND THE RULING DECIDES A SECOND THING BY IMPLICATION — `BR-RAT-960`'s
    second half, written down rather than re-asked (law 13).** Taking the unit
    from the service means a discount attached to the **WHOLE BILL** has no
    service to take one from. **A usage allowance is a ONE-SERVICE discount**,
    and the refusal for any other scope belongs at SET-UP — it is in
    `discount_services._validate_version`, on the `applies_to` field, where a
    clerk is typing. It is deliberately NOT here: a refusal met while
    configuring is a correction, and the same refusal met during a bill run is
    an outage.

    `service_billed_unit` is the tenant's own billed unit for the service
    (`seams.billed_uom`'s `billed_uom`, falling back to `primary_uom` — a NULL
    `billed_uom` MEANS *the register's own unit is what is billed* and does not
    mean unconfigured; `apps.tenancy.selectors.service_billed_uoms` states that
    in as many words). It is passed IN rather than looked up because this module
    is a pure narrowing with no database access, which is what lets the whole
    chain be exercised on fixtures.
    """
    if not service_billed_unit:
        raise UsageAllowanceUnusable(
            # BR-RAT-960 clause 1 — the ruling gives the unit a SOURCE, never a
            # DEFAULT. CLAUDE.md hard rule 3 is why there is no fallback here.
            f"R3b: a usage-allowance discount is attached to {service!r}, and this "
            "utility has not stated what unit that service is measured in. The "
            "allowance takes its unit from the service, so until the service states "
            "one there is nothing to take — and a free allowance has to say what it is "
            "free OF before it can be given. Set the unit on the service in Settings."
        )
    return service_billed_unit


def _size_key(facts: "MeterFacts | AssetCountFacts") -> str:
    """The size a service narrows by — a meter's connection size, or an
    unmetered service's asset size class.

    `""` means THIS SERVICE HAS NO SIZE, which is a real answer for an unmetered
    service whose assets state no class. It is not a missing value dressed as a
    string: `resolve_charge_codes` narrows on it and a code with no size rows
    matches, which is exactly right for a flat per-cart price.
    """
    if isinstance(facts, AssetCountFacts):
        return facts.size_class or NO_SIZE
    return facts.connection_size


def counted_quantity(assets: AssetCountFacts) -> Decimal:
    """R3b, UNMETERED — the billable quantity IS the count of assets.

    BR-RAT-090 (PO ruling 2026-08-20, option A). **Worked, ratified:** three
    carts is a billable quantity of `3`, which a `$15.00` per-cart schedule
    prices at `$45.00`; remove one and the next bill is `$30.00`.

    ⚠ **NO MULTIPLIER IS APPLIED, AND THAT IS NOT AN OMISSION.** R3b's metered
    half exists because a register reading is a SCALED number — `62` on a x10
    register is `620 kWh`. A cart count is not scaled by anything: three carts
    are three carts. Multiplying here would be inventing a factor the ruling
    does not mention, and the absence is asserted by a test rather than left to
    a reader's assumption.

    ⚠ **A COUNT OF `0` IS AN ANSWER AND BILLS; A COUNT OF `None` REFUSES.** The
    two are different facts (see `AssetCountFacts`), and this is the one place
    a lane could quietly merge them.
    """
    if assets.count is None:
        raise AssetCountUnavailable(
            f"R3b: {assets.service!r} is declared UNMETERED (BR-RAT-081), so its billable "
            "quantity is a COUNT of its assets on the unit (BR-RAT-090) — and no count "
            "could be determined. The bill refuses rather than billing zero: 'no carts "
            "recorded' and 'zero carts' are different facts, and a household with three "
            "carts billed for none is a document that looks entirely normal."
        )
    if assets.count < 0:
        raise AssetCountUnavailable(
            f"R3b: {assets.service!r} reports a NEGATIVE asset count ({assets.count}). A "
            "count is a number of physical things and cannot be below zero; a negative "
            "would price as a credit against a customer nobody authorised."
        )
    return Decimal(assets.count)


# ── R4 ──────────────────────────────────────────────────────────────────────


#: `charges.charge_type` — the ONE value that means *"this code belongs on an
#: ordinary periodic bill"* (BR-RAT-117, PO 2026-08-22). Named once so the
#: narrowing below and any future reader cannot drift apart, and spelled as the
#: column stores it (`apps.rating.services.CHARGE_TYPES`).
CHARGE_TYPE_RECURRING = "recurring"

#: `charges.amount_rule` — the rules this chain can turn into ONE amount, and
#: the two it deliberately cannot. `percent` and `percent_with_minimum` price a
#: fraction of a BALANCE (BR-BIL-001's *max($5, 1.5% × overdue)*), and a balance
#: is a BILLING fact that R1–R7 is never handed; `formula` is BR-RAT-041's
#: reserved value, *visible-but-disabled*, which no version of this product
#: evaluates.
AMOUNT_RULE_FLAT = "flat"
AMOUNT_RULES_ON_A_BALANCE = ("percent", "percent_with_minimum")
AMOUNT_RULE_FORMULA = "formula"
#: DEF-RAT-8753 — the amount is entered per case when the fee is used (CR-010 A2).
AMOUNT_RULE_PER_CASE = "per_case"


def rides_a_periodic_bill(code: ChargeCode) -> bool:
    """`BR-RAT-730` — does this charge code belong on an ORDINARY periodic bill?

    **This is the fourth narrowing condition, and its absence was `DEF-493`.**
    R4 narrowed by service, customer class and connection size and by nothing
    else, so a one-off `$45.00` connection fee and a recurring `$2.00`
    paper-bill fee were the same object to it — both service-`NULL`,
    class-unrestricted, both carrying a flat amount, both resolving. Measured
    on a provisioned tenant: **18 priced codes totalling `$829.95`, every one
    of them landing on a monthly bill whose base is `$8.00`.**

    ⚠ **THAT TOTAL READ `$799.95` UNTIL 2026-09-27 AND WAS A MEASUREMENT
    THAT HAD GONE STALE, NOT AN ERROR (`DEF-RAT-6980`).** `OQ-CUS-12518`,
    CLOSED 2026-09-21 on the PO's words *"reconnection fee is $75 - fix the
    code and seed"*, took the seeded `RECON` code from `$45.00` to `$75.00` —
    `$30.00`, which is the whole of the difference. The COUNT is 18 on both
    sides; no code was added or removed. The figure is pinned against the seed
    fixture itself in `tests/test_def_438_parity.py`, never re-typed.

    TWO WAYS IN, AND THEY ARE NOT THE SAME RULE
    -------------------------------------------
    * **`is_base` — the base charge, and it is NOT gated by the flags.**
      `BR-RAT-088` (PO 2026-08-20) made the charge code the one source of a
      service's base, and `resolve_base_charge` reads THIS function's output.
      `BR-RAT-117` says it in terms: *"⚠ THIS DOES NOT MOVE THE BASE. `is_base`
      still owns the base charge (BR-RAT-088)"*. Gating it would take the
      seeded tenant's `$8.00` residential water, `$15.00` commercial water and
      `$18.00` trash bases to **`$0.00`** — `DEF-154`'s exact shape, the base
      read from the wrong column, *"invisible because the arithmetic over it
      was right and the SOURCING was wrong"*.
    * **`recurring` AND `auto_apply` — every other code.** `BR-RAT-117`, PO
      verbatim: *"ruccuring and Autom apply land on bill"*. **Both flags, and
      the conjunction is the rule**: a code that is recurring but not
      auto-apply, or auto-apply but one-time, waits for its own trigger.

    NOT RIDING IS NOT AN ERROR
    --------------------------
    A `one_time` connection fee returns False and the bill proceeds. It is a
    code with a DIFFERENT trigger, not a missing fact — refusing it would stop
    every bill on every tenant, since 18 of the 23 codes a tenant is
    provisioned with are exactly that.

    ⚠ **`auto_apply=False` IS READ AS A DECLARATION, NOT AS A GAP** — the
    judgment is recorded in the decision log with its figure, and it is the
    safe direction: under-billing a `$2.00` fee is fixed by ticking a box next
    cycle, while over-billing `$829.95` on an `$8.00` bill is a credit note per
    customer under hard rule 4 (an issued invoice is immutable). Nothing is
    backfilled and nothing is guessed.
    """
    if code.is_base:
        # ⚠ CHECKED FIRST, SO A BASE CODE NEVER REACHES THE CONFLICT BELOW, and
        # that is a judgment rather than an accident: `BR-RAT-088` makes
        # `is_base` DECISIVE for the base, so the two recurrence flags are not
        # a second opinion about it — they are simply not the question being
        # asked. A tenant who also ticks auto-apply on their base code has said
        # nothing contradictory; they have said the same thing twice.
        return True
    if code.auto_apply and code.charge_type != CHARGE_TYPE_RECURRING:
        # ⚠ NOT `False`, and not `True` either. Both columns were filled in by
        # a person and they disagree; the chain says so (BR-RAT-730).
        raise ChargeCodeRecurrenceConflict(
            f"R4: charge code {code.code!r} is marked auto-apply and its charge type is "
            f"{code.charge_type!r}. Auto-apply means every bill; that type means an "
            "event. The chain refuses rather than choosing which of the two the "
            "customer is billed on."
        )
    return code.auto_apply and code.charge_type == CHARGE_TYPE_RECURRING


def charge_code_amount(code: ChargeCode, size: str | None) -> Decimal:
    """The ONE amount this code resolves to at this connection size, or REFUSE.

    Design §A2: *"no amount => REFUSE"*. **Every refusal here names the rule
    that is actually in the way** — see `ChargeCodeAmountMissing` for the four
    that used to share one sentence about connection sizes (`DEF-498`).
    """
    if code.flat_amount is not None and code.amounts:
        raise ChargeCodeAmountMissing(
            f"R4: charge code {code.code!r} states BOTH a flat amount and a per-size "
            "table. CR-013 part 2 gives a code one basis; this chain refuses rather "
            "than choosing which figure the customer is billed."
        )
    # ── The two rules that price off a BALANCE this chain is never handed ────
    # BR-BIL-001's late fee is `max($5, 1.5% × overdue)`. The overdue amount is
    # a BILLING fact — it depends on what has been issued and what has been
    # paid — and R1–R7 takes frozen RATING facts only. Naming a basis here
    # would be inventing one, and the plausible candidates (this bill's total?
    # the account balance?) differ by real money on every account.
    if code.amount_rule in AMOUNT_RULES_ON_A_BALANCE:
        raise ChargeCodeAmountMissing(
            f"R4: charge code {code.code!r} is priced as {code.amount_rule!r} "
            f"({code.percent} of a balance, minimum {code.min_amount}). R1-R7 resolves "
            "rating facts and is handed no balance, so it cannot state one amount for "
            "this code. A percentage code is billed by the rule that knows the balance "
            "(BR-BIL-001 for the late fee), never by this chain."
        )
    if code.amount_rule == AMOUNT_RULE_FORMULA:
        raise ChargeCodeAmountMissing(
            f"R4: charge code {code.code!r} is priced by {AMOUNT_RULE_FORMULA!r}, which "
            "BR-RAT-041 reserves as visible-but-disabled. No version of this product "
            "evaluates a formula, so there is no amount to state."
        )
    if code.amount_rule == AMOUNT_RULE_PER_CASE:
        # DEF-RAT-8753 / DEF-2340 — the code now SAYS it is priced per case
        # (CR-010 A2), so the refusal names that reading alone: a clerk enters
        # the amount when the fee is used (`billing.fee_bill`), and a periodic
        # bill has no clerk to enter it.
        raise ChargeCodeAmountMissing(
            f"R4: charge code {code.code!r} is priced per case — its amount is entered "
            "by a clerk when the fee is used (CR-010 A2) — so this chain has no amount "
            "to state for it."
        )
    if code.flat_amount is not None:
        return code.flat_amount
    if not code.amounts:
        # `DEF-2340`, CLOSED 2026-10-01 (2.436.7): TAP, IMPACT, DAMAGE and
        # BULK-WATER are now stored `per_case` (seed + `rating/0055`) and are
        # refused by the branch above, naming that reading. A NULL rule with no
        # amount is now a code nobody priced — or one of the four on a tenant
        # where `rating/0055` found it priced or deleted. The sentence below
        # still states both readings because a hand-edited row can reach here
        # either way; it is true of both and claims neither.
        raise ChargeCodeAmountMissing(
            f"R4: charge code {code.code!r} states no amount rule and no amount. Either "
            "it is priced per case by a clerk at the time it is used (CR-010 A2), or "
            "nobody has priced it — the product does not record which. Neither is an "
            "amount this chain may state, and billing $0.00 would be a silent wrong "
            "answer for both."
        )
    if size is None or size not in code.amounts or code.amounts[size] is None:
        raise ChargeCodeAmountMissing(
            f"R4: charge code {code.code!r} applies to this account and states no "
            f"amount for connection size {size!r} on service {code.service!r}. "
            "Design §A2: no amount refuses. Billing $0.00 for a code the utility "
            "has not priced is a silent wrong answer."
        )
    return code.amounts[size]


def resolve_charge_codes(
    catalogue: Catalogue,
    account: AccountFacts,
    services: tuple[str, ...],
    sizes: dict[str, str],
    named_base: dict[str, str] | None = None,
) -> tuple[tuple[ChargeCode, Decimal], ...]:
    """R4 — the charge codes that apply, each resolved to ONE amount.

    ── `DEF-RAT-9335` · A BASE CODE THE SCHEDULE DID NOT NAME IS NOT PRICED ──
    PO ruling 2026-10-03, verbatim: *"(a) Fix it: use the base the schedule
    names. Bills refused today start going out; bills already issued don't
    change."* `named_base` maps a service to the code its rate schedule NAMES
    (`tariff_versions.base_charge_code`, `BR-RAT-1025`). For such a service
    every OTHER `is_base` code of it is skipped before it is priced, because
    `resolve_base_charge`'s named arm would never charge it — so an un-named
    code that does not price this customer's size can no longer stop the
    bill. Worked (CR-167 §7.1): a residential 5/8" water account whose
    schedule names `BASE-W1` ($10.00) was refused by `BASE-W-FIRE` (priced
    only for 1" and 2"); it now bills September at $146.50 + $10.00 =
    **$156.50**. **Nothing that billed before moves**: the skipped codes were
    read by nothing but `resolve_base_charge`, whose named arm ignores them,
    and `Resolution.charge_codes` prices no line of its own. A service whose
    schedule names nothing is narrowed exactly as before (`DEF-468` still
    refuses two inferred base codes).

    **FOUR conjunctive conditions since `BR-RAT-730` (2026-08-28), not three.**
    In the design's own order plus the one it never had: the code's service
    matches (or it is account-level), its customer classes include the
    account's, **it rides an ordinary periodic bill at all**, and it resolves to
    an amount at that service's connection size. **No amount => REFUSE.**

    ⚠ **THE ORDER OF THE THIRD AND FOURTH IS LOAD-BEARING.** The recurrence
    test comes BEFORE the amount, so a `one_time` code that states no amount —
    which is TAP, IMPACT, DAMAGE and BULK-WATER on every tenant this product
    provisions — is simply not selected, rather than refusing a bill it was
    never going to appear on. Reversing the two puts `DEF-498`'s refusal back
    in front of `DEF-493`'s narrowing, which is precisely the state where
    *fixing either alone turns a refusal into an overcharge* (decision log,
    2026-08-27).

    Since the PO's ruling of 2026-08-19 — *"no plan cannot override prices"* —
    there is no per-plan amount override to consult, so the amount here is the
    code's own and the lookup is total.
    """
    resolved: list[tuple[ChargeCode, Decimal]] = []
    for code in catalogue.charge_codes:
        if code.service is not None and code.service not in services:
            continue
        if code.customer_classes and account.customer_class not in code.customer_classes:
            continue
        if not rides_a_periodic_bill(code):
            continue
        if (
            code.is_base
            and named_base
            and code.service in named_base
            and named_base[code.service] != code.code
        ):
            # `DEF-RAT-9335` — the schedule named another code; see above.
            continue
        if code.is_base and _states_no_amount_at_all(code):
            # ── PO ruling 2026-09-30, case (d) — A BASE CODE WITH NO AMOUNT ──
            # *"if user did not define and bind base charges in rate schedule
            # - then as a default you take 0 and complete the bill instead of
            # refusing"*. A base code that states neither a flat figure nor a
            # per-size table has not DEFINED a base, so it is not selected and
            # `resolve` bills `$0` with `base_source="not_set"`. Only this ONE
            # shape is skipped: a code with BOTH bases, a percent or formula
            # rule, or a per-size table missing THIS size is a definition that
            # contradicts itself, and `charge_code_amount` still refuses it.
            continue
        resolved.append((code, charge_code_amount(code, sizes.get(code.service or ""))))
    return tuple(resolved)


def _states_no_amount_at_all(code: ChargeCode) -> bool:
    """True exactly where `charge_code_amount` would refuse with *"states no
    amount rule and no amount"* — no flat figure, no per-size table, and no
    rule that prices off something else. Written as the same three tests in
    the same order so the two cannot drift apart."""
    return (
        code.flat_amount is None
        and not code.amounts
        and code.amount_rule not in AMOUNT_RULES_ON_A_BALANCE
        and code.amount_rule != AMOUNT_RULE_FORMULA
    )


# ── R5 ──────────────────────────────────────────────────────────────────────


def money_factor(catalogue: Catalogue, premises: PremisesFacts, service: str) -> Decimal:
    """R5 — the premises' jurisdiction factor on the MONEY, per service.

    It scales BOTH the base charge and the usage, which is the second half of the
    PO's correction: *"you will have to add rate changes in base charges and
    rates"*. A service the tenant listed as exempt is untouched — §A4 S2's sewer
    base is *"flat everywhere"* and stays $8.00 while every other line moves 50%.

    A tenant with no factor configured gets `Decimal("1")` and no jurisdiction is
    ever consulted, so this step cannot refuse a bill for a tenant who does not
    price by jurisdiction at all.
    """
    if catalogue.outside_city_factor == Decimal("1"):
        return Decimal("1")
    if premises.inside_city_limits is None:
        raise JurisdictionUnstated(
            "R5: this tenant prices by jurisdiction "
            f"(outside-city factor {catalogue.outside_city_factor}) and the premises "
            "records no inside/outside-city flag. The bill refuses rather than being "
            "produced at the inside-city price by default: the factor changes every "
            "line, so a guess here is a wrong bill and not a partial one."
        )
    if premises.inside_city_limits:
        return Decimal("1")
    if service in catalogue.outside_city_exempt_services:
        return Decimal("1")
    return catalogue.outside_city_factor


# ── R6 ──────────────────────────────────────────────────────────────────────


def resolve_base_charge(
    resolved_codes: tuple[tuple[ChargeCode, Decimal], ...],
    service: str,
    named_code: str | None = None,
) -> Decimal | None:
    """BR-RAT-088 — the base for ONE service, taken from the CHARGE CODE the
    rate schedule NAMES, or failing that from the code that declares itself the
    base. Returns None when neither exists.

    ── `CR-120-BRC06` · `BR-RAT-1025` — TWO ARMS, AND THE ORDER IS THE RULE ────
    PO ruling 2026-09-19: *"we are not bindng base charges in rate schedule -
    you were taking it default; now we are making it explicit it is a same rule
    - change is default -> expliciate"*.

      1. `named_code` is set  -> **THAT** code is this service's base. Stated by
         a person on step 1 of `RAT-03`.
      2. `named_code` is None -> today's lookup, BYTE FOR BYTE: the code whose
         `is_base` is set for this service, refusing on ambiguity (`DEF-468`).

    **EVERY SCHEDULE THAT EXISTS PASSES None, SO ARM 2 ANSWERS AND NO BILL
    MOVES.** That is not a hope: `tariff_versions.base_charge_code` is added
    NULL by `rating/0037` and backfilled by nothing, and all 47 ready accounts
    of the shipped fixture are asserted to resolve the same base, from the same
    code, at the same amount, before and after
    (`tests/test_cr120_schedule_names_base_charge_code.py`).

    The shape is `PlanWizard.lateFeeSourceCharge`'s, deliberately — *"Two places
    a plan can name it, and the order matters"* (`BR-RAT-1011` / `CR-078`). One
    pattern for two bindings beats two that happen to agree.

    ⚠ **THIS IS THE READ PATH FOR A RULING THAT REVERSED TWO CONFIRMED RULES**
    (PO 2026-08-20, closing B1 and OQ-238). `BR-RAT-012` and `BR-RAT-027` both
    said the base is *"defined per service within a plan"*; `tariff_versions
    .base_charge` is what the product actually read until 2026-08-16; and §A3
    ruled the charge code owns it. All three could hold a figure, and §A3 priced
    the collision: a 5/8" water account with `$12.00` in two of them is billed
    **`$24.00`** — `$23,069.50` a month across 1,247 connections — *"and no test
    catches it, because both rows are individually correct."*

    **It reads the already-resolved R4 output rather than the catalogue**, which
    matters: R4 has already applied service, customer class and the meter's size
    row, so the amount here is the one that will actually bill. Resolving the
    base separately from the catalogue would be a second narrowing that could
    disagree with the first — the same shape of bug one layer up.

    ── THE TRAVERSAL, AND THE PRECEDENCE, STATED ONCE ─────────────────────────
    ⚠ **THIS SECTION QUOTED THE PO'S SENTENCE OF 2026-08-31 AND DREW THE CHAIN
    WITH THE RATE SCHEDULE MISSING FROM IT. THE PO CORRECTED THE ORDER ON
    2026-09-19 (`CR-120-BRC06`, `BR-RAT-1025`).** Both sentences are kept,
    because the older one is quoted elsewhere in this repo and a reader tracing
    that quotation needs the middle link.

    **SUPERSEDED, PO 2026-08-31:** *"We already agreed that it will be in charge
    code, per utility services , you ahve to take it from there, and plan will
    bind it , so plan -> charges code -> base scharges"*.

    **CURRENT, PO 2026-09-19:** *"no this is not correct ; So: plan → rate
    schedule -> charge code → base charges - this is correct"*.

    And, in the same breath, why that reverses nothing: *"we are not bindng base
    charges in rate schedule - you were taking it default; now we are making it
    explicit it is a same rule - change is default -> expliciate"*. **The SOURCE
    and the ARITHMETIC do not move. The ROUTE gains a step, and that step was
    always there — it was inferred rather than stated.** The PO had already said
    so on 2026-09-10 (*"Charge Code -> base charge -> rate schedule -> plans -
    that is the path"*), and the decision log of that day reads *"THE MIDDLE
    STEP IS THE RATE SCHEDULE, AND IT IS A ROUTE RATHER THAN A STORE"*.

        the ACCOUNT resolves to a PLAN                    (R1)
        the PLAN lists its SERVICES and, per service, the RATE SCHEDULE it
        attaches                                          (R1/R2)
        the SCHEDULE VERSION may NAME the charge code that owns this service's
        base — `tariff_versions.base_charge_code`         (`BR-RAT-1025`)
        where it names none, that service's base is the CHARGE CODE that
        declares ITSELF the base — `charges.is_base`, narrowed by the account's
        customer class and its connection size            (R4, this function)
        the AMOUNT is the code's, from `charge_code_amounts` at that size or
        from its *All sizes* row (CR-156-BRC10 — `charges.amount` is retired),
        in force on the service date              (`charge_prices`, the one lookup)

    ⚠ **THE SCHEDULE NAMES; IT NEVER PRICES.** *"base will come from base"* —
    the PO, the same day. `tariff_versions.base_charge`, the retired decimal,
    is untouched by all of this and is still read at exactly one place
    (`_legacy_schedule_base`). The schedule is *"never a second place to type a
    figure"* (decision log, 2026-09-10) and this ruling does not make it one.

    **THREE OBJECTS CAN HOLD A BASE-SHAPED FIGURE AND EXACTLY ONE OF THEM IS
    THE SOURCE.** Written down here because the next lane meets all three and
    no file states the order:

      1. `charges` + `charge_code_amounts` — **THE SOURCE** (BR-RAT-088).
      2. `plan_services.base_charge` — the plan DISPLAYS it. BR-RAT-012 and
         BR-RAT-027 are both **SUPERSEDED** by BR-RAT-088; a figure here is a
         migration artefact once a base code exists.
      3. `tariff_versions.base_charge` — **RETIRED** by the same ruling, with
         no control on S11 since. Read only as the legacy fallback in
         `resolve`, for a tenant that has declared no base code at all.

    ⚠ **AND SINCE `CR-120-BRC06` THERE IS A FOURTH OBJECT IN THIS PICTURE AND IT
    IS NOT A FOURTH SOURCE — IT IS A POINTER.** `tariff_versions
    .base_charge_code` is a FK to `charges`. It says WHICH of item 1's codes
    owns this service's base; it holds no money and it can hold none. So the
    count of objects that can hold a base-shaped FIGURE is still THREE and
    exactly one of them is the source. **It sits in the same table as item 3
    and is its opposite** — a lane that reaches for `base_charge` when it means
    `base_charge_code` has repurposed a retired column on a money path.

    ⚠ **AND `plan_charge_rules` IS NOT A FOURTH.** It is the plan's binding for
    every OTHER charge code and the repo says so in its own words:
    `selectors.billable_charge_codes` excludes `is_base` rows by name — *"the
    base charge already reaches the bill as the service's base through R4 …
    the base has its own route"* — and `PlanWizard.servicesMissingBaseCharge`
    finds a service's base code by `is_base` + `service`, never through a
    binding row. **Measured on the shipped fixture on 2026-08-31: 9
    `plan_charge_rules` rows and 0 of them `is_base`**, while all 47 ready
    accounts resolve a base. Narrowing the base to bound codes would take every
    one of them to *no base at all*.

    ⚠ **AND `plan_charge_rules.amount_override` IS NOT CONSULTED, WHICH IS A
    SIGNED RULING AND NOT AN OMISSION.** PO 2026-08-19 ruling 1, verbatim: *"no
    plan cannot override prices"* — *"no per-plan amount override, no per-plan
    waive, no per-plan rate override"*, in the ruling's own words. The column
    survives only so no stored figure is destroyed. A plan BINDS; it never
    prices (CR-013 part 5: *"a plan composes; it does not price"*).

    Returning None is not an error and not zero. A plan whose service declares no
    base charge code is a configuration a human must see; §A3 makes that an
    ACTIVATION gate (*"refused, naming the service"*), not a billing-time guess.

    ⚠ **AND IT REFUSES ON AMBIGUITY RATHER THAN TAKING THE FIRST MATCH
    (DEF-468, PO 2026-08-21).** This used to `return` on the first code whose
    `is_base` was set for the service — so two matching base codes meant the
    customer was billed by CATALOGUE ORDER, which is arbitrary and silent.

    The PO put the case that surfaced it: *"based on Asset and Account type you
    will have select 1 base charge out of so many charges … then you need to
    derive which base rate to select."* Selecting one of several is exactly
    where a first-match wins by accident. Nothing in the schema prevents two —
    `charges.is_base` is a bare boolean with no uniqueness constraint — so the
    chain is the only place this can be caught, and a refusal here is the same
    posture R3, R4 and R5 already take: a wrong bill is worse than no bill.
    """
    if named_code is not None:
        # ── `CR-120-BRC06` · `BR-RAT-1025` — THE EXPLICIT ARM, AND IT IS FIRST.
        # The schedule NAMED this code, so no narrowing by `is_base` happens
        # here: a person said which code owns this service's base and R4 takes
        # them at their word. `_guard_bound_base_charge_code` is what makes that
        # safe — it refuses at ACTIVATION any binding R4 could not have selected
        # anyway, so by the time a bill runs, the named code is `is_base`, is on
        # this service (or is account-level) and reaches this account's class.
        #
        # ⚠ **THE AMBIGUITY REFUSAL BELOW CANNOT FIRE ON THIS ARM AND MUST NOT.**
        # `DEF-468` exists because TWO codes declaring themselves the base meant
        # the customer was billed by catalogue order. Naming one is the CURE for
        # that, not another instance of it: the whole value of the explicit route
        # is that a utility with two base codes can say which one this schedule
        # means.
        named = [
            (code, amount) for code, amount in resolved_codes if code.code == named_code
        ]
        if named:
            return named[0][1]
        # The named code did not survive R4's narrowing for THIS account.
        # Falling through to the `is_base` lookup would bill a figure the
        # schedule's own screen does not show, which is the exact disagreement
        # `BR-RAT-1025` exists to prevent, so it REFUSES instead.
        #
        # ⚠ **THE SENTENCE NAMES THE TWO CAUSES THAT CAN ACTUALLY OCCUR AND NOT
        # A THIRD THAT CANNOT.** A first draft of this refusal also offered
        # *"is not carried on an ordinary periodic bill"*, which is impossible
        # for a base code and would have sent a utility to look at the wrong
        # flags: `rides_a_periodic_bill` returns True for `is_base` **before**
        # it reads `charge_type` or `auto_apply` at all (`BR-RAT-117`,
        # `BR-RAT-088` — *"this does not move the base"*), so a base code can
        # never fail that test. That is `DEF-498`'s lesson on this very
        # exception class — *"a refusal that names the wrong fact is worse than
        # a long one: it sends a utility to look at a meter for a problem that
        # is on a price list."*
        #
        # ⚠ **AND `charge_code_amount` RAISES RATHER THAN FILTERING**, so a
        # code with no amount at this size has already refused by its own name
        # further up and cannot arrive here either. What is left is the SERVICE
        # and the CUSTOMER CLASS, plus the code having been retired or
        # un-ticked since the binding was made — which is what condition 2 of
        # `services._guard_bound_base_charge_code` refuses at activation, and
        # this is the same fact reaching billing because somebody changed the
        # code afterwards.
        raise BaseChargeNotBound(
            f"R4: rate schedule for {service!r} names charge code {named_code!r} as its "
            "base (BR-RAT-1025), and that code does not cover this account — it prices "
            "another service, it is scoped to other customer classes, or it has been "
            "retired or is no longer marked as a base charge since the rate schedule "
            "named it. The chain refuses rather than falling back to whichever other "
            "code declares itself the base: the rate schedule shows this account's base "
            f"coming from {named_code!r}, and billing a different one would make the "
            "screen and the bill disagree without either being visibly wrong. Either "
            f"widen {named_code!r} to cover this account, or clear the base charge code "
            "on the rate schedule's first step and let the service's declared base "
            "answer."
        )
    matches = [
        (code, amount)
        for code, amount in resolved_codes
        if code.is_base and code.service == service
    ]
    if matches:
        # ── `DEF-RAT-9832` · ARM 2 IS RETIRED (PO 2026-10-06) ─────────────────
        # PO, verbatim: *"You will take the code from plan -> rate schedule ->
        # base charges - in that case if it is provided then you will take it
        # if it is not provided then you will take it zeo ; but you cannot take
        # W-COM because it is availabel in charge coede"*. Until that day this
        # arm took the one `is_base` code surviving R4's class narrowing (and
        # refused on two, `DEF-468`) — a code taken from the charge-code list
        # by class, which the ruling forbids. The schedule named none, so no
        # base is BOUND for this account: `resolve` catches this exactly as it
        # catches an unusable named code and bills `$0` with
        # `base_source="not_set"`. The same answer as
        # `selectors._no_base_code_named` on the live path, so the shadow agrees.
        raise BaseChargeNotBound(
            f"R4: the rate schedule for {service!r} names no base charge code "
            f"({', '.join(sorted(code.code for code, _a in matches))} exist but none "
            "is bound), so the base is $0.00 — nothing is taken from the charge-code "
            "list by customer class (PO 2026-10-06). Name the base code on the rate "
            "schedule."
        )
    return None


def resolve_discounts(catalogue: Catalogue, account: AccountFacts) -> DiscountResolution:
    """R6 — the account's enrolments, narrowed against the catalogue, in
    precedence order. Selects; does not price.

    ⚠ **THIS FUNCTION USED TO RETURN `modelled=False` AND SAY THE TABLE DID NOT
    EXIST. IT DOES (DEF-361).** Migration `0009_cr013_discounts` landed six tables
    — `discounts`, `discount_versions`, `plan_discount_rules`,
    `discount_enrolments`, `discount_enrolment_documents`, `discount_grants` —
    and this stub went on refusing with a reason that had become false. It failed
    CLOSED, so no bill was wrong and no test failed, which is exactly why nothing
    caught it: a refusal is indistinguishable from the correct old behaviour.
    Hard-won law 1, where the comment was also the return value.

    **`modelled` is now always True and the field survives on purpose.** Removing
    it would change the contract every caller was written against, and the
    distinction it encodes is still the one that matters — an empty `applied`
    now means *this customer is enrolled in nothing*, which is a TRUE statement
    about the account rather than a stand-in for one about the product.

    **THE ORDER IS THE RULE** (CR-013 part 3, and the module docstring):
    discounts apply BEFORE taxes, so a discount reduces the taxable base. §A4 S1
    is the worked case — removing the $1.00 PAPERLESS discount moves Bexar County
    from $3.78 to $3.80, which is why "reachable" is $196.37 and not $194.60.

    **A discount the account is enrolled in but the catalogue does not offer is
    dropped, not guessed.** That is a plan/enrolment mismatch — CR-013 part 3's
    *"plan attachment makes a discount available, not granted"* read from the
    other end — and inventing a value for it would reduce a bill by a figure no
    configured object states.
    """
    offered = {rule.code: rule for rule in catalogue.discounts}
    enrolled = tuple(offered[code] for code in account.enrolments if code in offered)
    # Precedence is DATA (part 3). `sorted` is stable, so equal precedence keeps
    # the enrolment order rather than reordering it arbitrarily.
    ordered = sorted(enrolled, key=lambda rule: rule.precedence)
    return DiscountResolution(
        modelled=True,
        applied=tuple((rule.code, rule.value) for rule in ordered),
    )


def require_discounts(resolution: DiscountResolution) -> tuple[tuple[str, Decimal], ...]:
    """For a caller that cannot proceed without R6's answer. Refuses by name."""
    if not resolution.modelled:
        raise DiscountsNotModelled(resolution.unmodelled_reason)
    return resolution.applied


# ── R7 ──────────────────────────────────────────────────────────────────────


def resolve_taxes(
    catalogue: Catalogue,
    account: AccountFacts,
    premises: PremisesFacts,
    services: tuple[str, ...],
) -> tuple[TaxRule, ...]:
    """R7 — the taxes that ATTACH. Never chosen, and never per plan.

    Four conjunctive conditions, all of which decide APPLICABILITY and none of
    which decides an amount: the jurisdiction matches the premises, the rule's
    services include at least one on this bill, its customer classes include the
    account's, and — for a rule stating a city-limit condition — the premises
    flag agrees.

    THE OUTCOME OF A FAILED CONDITION IS NO LINE AT ALL, never a zero-valued one
    (DEF-273). A $0.00 tax line is a claim that the authority charges nothing.

    An account whose class was never recorded does not match a class-restricted
    rule (DEF-273's fail-safe): under-charging is recoverable and over-charging a
    customer who is exempt is not.

    ── ⚠ WHICH LAYER ACTUALLY DECIDES EACH AXIS (`DEF-2824`, 2026-08-31) ──────
    **THIS FUNCTION NARROWS WHAT IT IS GIVEN. IT CANNOT WIDEN.** `catalogue.taxes`
    is a candidate set somebody else built, and for a year the builder and this
    function each assumed the other had done the narrowing — so no layer did it,
    and every class-restricted, premises-restricted or service-restricted tax was
    dropped from every ruled bill on every tenant. Nothing could see it: R7 raises
    no refusal by design, so its only possible output was silence.

    The division of labour is now stated once, here, and enforced by the
    catalogue builder's own signature (`resolution_catalogue.tax_facts` takes the
    bill's facts as REQUIRED keyword arguments, so no caller can starve it):

      * **services** — decided HERE, and correctly. `TaxRule.services` is the
        tax's own `applies_to_services`, and the same field also NARROWS THE BASE
        (DEF-465), so it has to travel whatever else happens. The builder passes
        the PLAN's service set to the selector so a candidate is not pre-dropped;
        this line then narrows to the services that actually resolved.
      * **customer class** — decided by `selectors.tax_applies_to` before the
        candidate is built. `TaxRule.customer_classes` is left EMPTY by the
        builder, deliberately and with its reason stated there.
      * **premises** — decided by `selectors.premises_in_scope`, which is the
        only layer that can: a tax states its geography over FIVE mechanisms and
        these two booleans can express one of them. A tax scoped by STATE, or by
        a city NAME where no boundary flag is recorded, is invisible to
        `inside_city_only` / `outside_city_only` and would be attached by this
        function if the selector had not already refused it.
      * **the exemption certificate** (DEF-383) — the selector's, and it is the
        one gate that fails OPEN, so it is the one an absent fact OVER-charges on.

    Both remaining conditions are therefore a second, identical narrowing rather
    than the only one. They are kept because a narrowing that cannot widen costs
    nothing and because a caller building a `Catalogue` by hand may legitimately
    state them.
    """
    attached: list[TaxRule] = []
    for rule in catalogue.taxes:
        if rule.services and not set(rule.services) & set(services):
            continue
        if rule.customer_classes and account.customer_class not in rule.customer_classes:
            continue
        if rule.inside_city_only and premises.inside_city_limits is not True:
            continue
        if rule.outside_city_only and premises.inside_city_limits is not False:
            continue
        attached.append(rule)
    return tuple(attached)


# ── The chain ───────────────────────────────────────────────────────────────


def resolve(
    *,
    catalogue: Catalogue,
    account: AccountFacts,
    premises: PremisesFacts,
    meters: tuple[MeterFacts, ...],
    quantities: dict[str, Decimal | None] | None = None,
    #: BR-RAT-090 — the UNMETERED half of R3b. One row per unmetered service on
    #: the plan, carrying the OBSERVED count of that service's active assets on
    #: the unit. A service declared unmetered with no row here refuses; see
    #: `AssetCountUnavailable` for why an absent count is not a zero.
    asset_counts: tuple[AssetCountFacts, ...] | None = None,
    service_date: date,
) -> Resolution:
    """R1 -> R7, in order, once. Exactly one answer or a named refusal.

    `quantities` are REGISTER differences, pre-multiplier — R3b turns them into
    billable quantities and the engine prices those. A service absent from the
    mapping has no read, which is not a zero (`apps.billing.contracts
    .ServiceReading` states the reason: a zero claims the meter was read).

    The ORDER of the steps is the content of §A2 and it is not decorative: R3b
    must run before anything walks a tier boundary and R5 must run after
    everything has been priced, which is why they are two steps with three other
    steps between them.
    """
    quantities = quantities or {}
    counts_by_service = {row.service: row for row in (asset_counts or ())}
    plan = resolve_plan(catalogue, account, service_date)

    meters_by_service = {meter.service: meter for meter in meters}
    resolved_services: list[ServiceResolution] = []
    #: Per-service facts gathered by R1-R3b, held until R4 has run — because the
    #: base now comes from R4 and a ServiceResolution is frozen once built.
    #: `MeterFacts` for a metered service, `AssetCountFacts` for an unmetered
    #: one, and the fourth item is the version's RETIRED scalar base — R4's
    #: legacy fallback for a tenant that has declared no `is_base` code, `None`
    #: for every tenant configured since BR-RAT-088 and never a gate (DEF-2823).
    pending: list[tuple[str, ScheduleVersion, MeterFacts | AssetCountFacts, Decimal | None]] = []
    for service in plan.services:
        schedule = resolve_schedule(catalogue, plan, service, service_date)
        if service in catalogue.unmetered_services:
            # ── BR-RAT-081 + BR-RAT-090 · the UNMETERED branch ───────────────
            # PO ruling 2026-08-20: *"yes we have to say service is meter or
            # unmetered"* (the declaration, BR-RAT-081), then *"an unmetered
            # service's quantity is a COUNT OF ITS ASSETS ON THE UNIT"* (the
            # quantity, BR-RAT-090, option A — closes OQ-283). The run reads the
            # declaration instead of demanding a meter, which is DEF-161's fix
            # and is GENERAL: every unmetered service in the ten-service seed
            # comes through here, not just Trash.
            #
            # ⚠ THE COUNT IS OBSERVED, NEVER TYPED. Metering owns assets (B2 r4),
            # so three carts on a unit bill three carts and adding a cart in the
            # field changes the next bill by itself. Option B — a `quantity`
            # column on the plan's service line — was shown and REJECTED because
            # a typed number can disagree silently with the carts in the street.
            assets = counts_by_service.get(service)
            if assets is None:
                raise AssetCountUnavailable(
                    f"R3b: {service!r} is declared UNMETERED (BR-RAT-081) and this bill "
                    "carries no asset count for it, so BR-RAT-090's quantity cannot be "
                    "resolved. The caller must supply an `AssetCountFacts` row for every "
                    "unmetered service on the plan — an absent row is 'nobody looked', "
                    "which is not the same fact as 'this unit has none'."
                )
            # ⚠ R3 STILL RUNS WHERE IT CAN. An unmetered service has no
            # connection size, but it may have an asset SIZE CLASS — A1 §S76
            # lists **carts** among `service_size_classes`, so a 96-gallon cart
            # can be priced differently from a 35-gallon one. Where the assets
            # state a class, the schedule is asked for that row and refuses on
            # exactly the same two grounds as a meter's size (DEF-277). Where
            # they state none, R3 has nothing to look up and the base must come
            # from R4 — which is where BR-RAT-088 put it anyway.
            # ⚠ **R3's MEMBERSHIP GATE RUNS ON THIS BRANCH TOO, AND FORGETTING
            # IT WAS A REGRESSION THIS TEST CAUGHT** (`test_br_rat_090_tc10`).
            # A cart size the schedule does not price must refuse EXACTLY as a
            # meter size does — DEF-277 reached from the unmetered side — and
            # `_legacy_schedule_base` deliberately raises nothing, so calling it
            # alone silently priced a 64-gallon cart at whatever R4 said for the
            # service. Membership first, then the legacy figure.
            legacy_base = None
            if assets.size_class is not None:
                asset_size = MeterFacts(service, assets.size_class)
                resolve_served_size(schedule, asset_size)
                legacy_base = _legacy_schedule_base(schedule, asset_size)
            pending.append((service, schedule, assets, legacy_base))
            continue
        meter = meters_by_service.get(service)
        if meter is None:
            raise SizeNotServed(
                f"R3: the plan covers {service!r} and the unit has no meter for it, so "
                "there is no connection size to resolve a size row against. A service "
                "with no service point is a configuration problem a human must see. "
                "If this service is sold WITHOUT a meter, that is not a fault — declare "
                "it on `tenant_services.metered` (BR-RAT-081) and the run stops asking."
            )
        # ⚠ R3 STILL RUNS AND STILL REFUSES — the flip moved the PRICE, not the
        # gate. A size absent from the schedule still means *this size is not
        # served* and still stops the bill (BR-RAT-120; PO 2026-08-28, an
        # unpriced size is REFUSED and never substituted). What changed on
        # 2026-08-31 (`DEF-2823`) is that R3 no longer reads the RETIRED column
        # `tariff_versions.base_charge` to decide it — that column has had no
        # control on S11 since BR-RAT-088 and is NULL on every schedule a real
        # utility creates, so the gate refused every size of every tenant that
        # had adopted the ruling. The two refusals stay distinct, exactly as §A2
        # orders them: R3 asks "does this schedule serve this size", R4 asks "is
        # there an amount for it".
        resolve_served_size(schedule, meter)
        legacy_base = _legacy_schedule_base(schedule, meter)
        pending.append((service, schedule, meter, legacy_base))

    # R4 BEFORE the base, because the base now COMES from R4. `resolve_charge_codes`
    # narrows by service, customer class and the meter's size row, so the amount it
    # returns is the one that will actually bill. Reading the catalogue a second
    # time here would be a second narrowing that could disagree with the first.
    services = tuple(service for service, _s, _f, _b in pending)
    # An unmetered service narrows by its ASSET size class where it has one
    # (BR-RAT-090 — a 96-gallon cart may be priced differently from a 35-gallon
    # one) and by nothing where it does not. `_size_key` states that in one
    # place so the narrowing and R3's own lookup cannot drift apart.
    sizes = {service: _size_key(facts) for service, _s, facts, _b in pending}
    # `DEF-RAT-9335` — the base code each schedule NAMES, so R4 never prices
    # (and so never refuses on) a base code the bill would not charge.
    named_base = {
        service: schedule.base_charge_code
        for service, schedule, _f, _b in pending
        if schedule.base_charge_code is not None
    }
    charge_codes = resolve_charge_codes(catalogue, account, services, sizes, named_base)

    for service, schedule, facts, legacy_base in pending:
        unmetered = isinstance(facts, AssetCountFacts)
        # BR-RAT-088 (PO ruling 2026-08-20, closing B1/OQ-238): the CHARGE CODE
        # owns the base. §A3 priced the alternative — a plan, a schedule and a
        # code all holding $12.00 bills $24.00 when two of them are charged,
        # $23,069.50 a month across 1,247 connections, *"and no test catches it,
        # because both rows are individually correct."*
        #
        # ⚠ THE FALLBACK IS DELIBERATE AND IT IS NOT A HEDGE. `Charge.is_base`
        # defaults False, so a tenant that has not declared its base code has no
        # charge-code answer to give. Refusing there would stop every bill for
        # every existing tenant the day this shipped; silently billing no base
        # would be worse. So the schedule answers until the tenant moves, the
        # source is RECORDED on the line, and the migration becomes observable
        # rather than assumed.
        # `CR-120-BRC06` · `BR-RAT-1025` — the schedule's NAMED code first. It
        # is None on every version that exists today, so this is the identical
        # call it has always been until a person binds one on step 1.
        # ── PO ruling 2026-09-30 · A BASE NOBODY DEFINED AND BOUND IS `$0` ──
        # *"if user did not define and bind base charges in rate schedule -
        # then as a default you take 0 and complete the bill instead of
        # refusing"*. Two ways to arrive: the schedule NAMED a code that cannot
        # answer here (`BaseChargeNotBound`), or no code and no retired figure
        # answers at all (the `DEF-2823` refusal below, which is now a `$0`
        # base rather than a raise). A named-but-unusable binding never falls
        # back to the retired column, for the reason `BaseChargeNotBound`
        # gives.
        not_bound = False
        try:
            code_base = resolve_base_charge(charge_codes, service, schedule.base_charge_code)
        except BaseChargeNotBound:
            code_base, not_bound = None, True
        base_not_set = code_base is None and (legacy_base is None or not_bound)
        # ⚠ **THE `DEF-2823` BLANK-BASE REFUSAL THAT STOOD HERE IS REMOVED BY
        # THAT RULING, NOT MOVED.** It raised `ChargeCodeAmountMissing` when no
        # `is_base` code covered this account and the retired schedule column
        # was blank too, arguing that `$0.00` was *"the silent wrong answer
        # DEF-154 produced on every bill for days"*. The PO has now chosen
        # `$0.00` explicitly, and it is no longer SILENT: `base_source` says
        # `not_set` and billing puts a named warning on the preview, the draft
        # and the run (`billing.oneTime.warn.baseNotSet`).
        resolved_services.append(
            ServiceResolution(
                service=service,
                schedule_version_id=schedule.version_id,
                connection_size=_size_key(facts),
                base_charge=(
                    Decimal("0")
                    if base_not_set
                    else (legacy_base if code_base is None else code_base)
                ),
                # ⚠ THREE VALUES SINCE `CR-120-BRC06`, and the new one is the
                # EXPLICIT route. A schedule that names its code and a schedule
                # that infers it produce the SAME amount today — which is
                # exactly why the line has to say which one answered, for the
                # reason `base_source` was written in the first place: during a
                # cutover both objects can answer and a bill that cannot say
                # which one priced it is a bill nobody can audit.
                base_source=(
                    "not_set"
                    if base_not_set
                    else "schedule"
                    if code_base is None
                    else ("named_charge_code" if schedule.base_charge_code else "charge_code")
                ),
                # ── R3b, both halves ────────────────────────────────────────
                # Metered: a register difference SCALED by the meter multiplier
                # (BR-RAT-001 — 62 on a x10 register is 620 kWh, and the order
                # decides which tier it lands in). Unmetered: the count itself,
                # scaled by nothing, because three carts are three carts
                # (BR-RAT-090).
                billable_quantity=(
                    counted_quantity(facts)
                    if unmetered
                    else billable_quantity(facts, quantities.get(service))
                ),
                # `1` on the unmetered line is the ABSENCE of a register, not a
                # factor anybody recorded — `quantity_source` is what tells the
                # two apart on the bill.
                meter_multiplier=Decimal("1") if unmetered else (facts.multiplier or Decimal("1")),
                quantity_source="asset_count" if unmetered else "read",
                money_factor=money_factor(catalogue, premises, service),
            )
        )

    return Resolution(
        plan=plan,
        services=tuple(resolved_services),
        charge_codes=charge_codes,
        discounts=resolve_discounts(catalogue, account),
        taxes=resolve_taxes(catalogue, account, premises, services),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 §A2 as CORRECTED by the PO 2026-08-19 (decision log) + CR-013
#         parts 1/2/4/5 verbatim (12-governance/11-change-requests.md) +
#         BR-RAT-001/007/012/027, BR-MET-056, B4.2
# generated: 2026-08-19 by the CR-013 phase-1 lane (EP-RAT-15 — the resolution engine)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr013_resolution_chain.py → 23 PASS✔ · pytest tests/test_cr013_a4_scenarios.py → 5 PASS✔ · pytest tests -m golden → 23 PASS / 1 xfail, unchanged✔ · 10-scripts/03-golden-verify.py 33 PASS / 0 FAIL✔
# exceptions: R6 is an EXPLICIT NAMED GAP, not an implementation — no discounts table exists in this product (CR-013 part 3 / EP-RAT-12). R3's size rows and R4's per-size charge-code amounts are STATED ON THIS CONTRACT and not yet stored: `charge_code_amounts` and the per-size base grid are EP-RAT-10/11 schema. So this module is the narrowing LAW with its refusals proved; the DB-backed adapter that feeds it is the next slice, and until it lands `apps/billing/gather.py` remains the shipped R1/R2/R7 path.
# status: VERIFIED-UNRATIFIED
#
# ── 2026-08-28 · R4 gains its fourth narrowing axis and its amount rules ──
# packet: BR-RAT-117 (PO 2026-08-22, verbatim) + decision log 2026-08-27 §3 +
#         BR-RAT-088 + BR-RAT-041 + CR-010 A2 (PO 2026-08-17) + DEF-498/DEF-493
# generated: 2026-08-28 by the DEF-498/DEF-493 lane (BR-RAT-730, BR-RAT-731)
# checklist: A✔ B✔ C✔ D=n/a(pure module, no API half) E=n/a(no frontend half —
#         the two columns already have their controls on ChargeCodeWizard step 1
#         and the type is a column on ChargeCodesTab, which is WHY this is a
#         reading job and not a new field) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: golden-verify 33 PASS / 0 FAIL before and after (no ❄️ figure moves;
#         `charge_type` and `auto_apply` are not money columns) ·
#         run_gates 41 PASS / 12 FAIL, unchanged ·
#         tests/test_def_498_def_493_charge_code_recurrence.py 18 PASS, of which
#         16 FAIL on the untouched tree · six guards proved RED first
# exceptions: (1) **NOTHING IS SWITCHED ON.** R4 still has no production caller;
#         this changes what R4 WOULD do at step 5 of the cutover, not what any
#         bill says today. (2) A percentage is still NOT PRICED here and must
#         not be — the balance it is a fraction of is a billing fact this chain
#         is never handed (BR-RAT-731). (3) `DEF-2340`: a per-case code and an
#         unpriced code are the same stored row, so one refusal has to state
#         both readings. (4) `DEF-2341`: `resolution_shadow.py` keeps a
#         hand-written copy of the refusal→step map and cannot see the tenth
#         class; `refusal_steps()` is published for it, and the adoption belongs
#         to that file's owner.
# ──────────────────────────────────────────────────────────


#: Re-exported so callers and tests can build a VARIANT of a frozen facts
#: object without importing dataclasses themselves — every value type in this
#: module is frozen, which is what makes the chain safe to hand around.
replace = _dc_replace
#
# ── 2026-09-02 · DEF-3098 · "has size rows" was standing in for "prices by size" ──
# packet: DEF-3098 (12-governance/10-defect-log.csv) + CR-062 group A's handover
#         (12-governance/11-change-requests.md) + BR-TEN-171 as amended by
#         CR-062 + BR-RAT-120 (PO 2026-08-28) + the capacity-multiplier ruling
#         of 2026-08-27, verbatim: "multiplier replaces bands for capacity
#         services (solar, battery, thermal); bands stay for pipe/amp/CFH -
#         this si corect"
# generated: 2026-09-02 by the CR-062 fixture-and-DEF-3098 handover lane
# checklist: A=n/a(no packet story — a defect fix inside a signed rule) B=n/a
#         (no rule changes; the code now asks the rule it already had) C✔
#         (no query added — service_size_classes holds no model and issues no
#         query, so B1's ban on rating reading tenancy's TABLES is untouched;
#         no money column, nothing append-only written) D=n/a(no API half —
#         no endpoint, no error code, no money figure) E=n/a(no frontend half)
#         F✔ (see gates) G✔ (defect row closed with its escape reason, decision
#         log row with the worked figure, review-ledger row in plain English,
#         CR-062's own handover section marked done) H=deferred(PO 2026-08-09 —
#         AI authors 🔒, human reviews later; row in 09-human-review-ledger.md)
# gates: ruff✔ black✔ (the four black hunks in resolution_shadow.py are
#         PRE-EXISTING and outside this change — proved by running black on the
#         file's HEAD copy and getting the same four) ·
#         golden-verify 33 PASS / 0 FAIL before and after · G64 engine-verified
#         14 of 61 GTs, unmoved · run_gates run and every FAIL enumerated MECHANICALLY against this lane's files — none names one (see the lane report) ·
#         the affected-suite run and its counts are in the commit that follows this block ·
#         PostgreSQL 16.13 proof: the DEF-3098 suite and the BR-RAT-120 refusal suite run green on a real database (law 14)
# exceptions: (1) **NO PRICE MOVES.** This changes which SIZE a schedule serves
#         for four services whose price never varied by size; GT-15's $40.00
#         solar and $24.00 battery are untouched and no ❄️ FROZEN B4/B5 figure
#         moved. (2) The fix is a QUESTION, not a special case — nothing in any
#         of the three files names a service, which is why it is already right
#         for Fire. (3) **AND THAT WAS TESTED, NOT ASSUMED.** `CR-063` landed
#         Fire mid-lane with SEVEN BANDS — *"exactly like trash"* in the PO's own
#         words, so the size PICKS the price and the COUNT multiplies it — and
#         `service_prices_by_size_class("fire")` answered `True` on the first run
#         with no edit here at all. A case now asserts that every ratified
#         service sits on exactly one side of the question, so a TWELFTH cannot
#         arrive untested. That case is the durable half: two hand-written tuples
#         of service names would have skipped Fire in silence, every test still
#         passing — hard-won law 2's shape, in a test file. (4) Trash keeps its
#         banded axis and its refusal to be summed; a BANDED service whose
#         schedule configures no size still serves none and still refuses by
#         name (BR-RAT-120, the cost the PO accepted).
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING 🔒 — rating math, a
#         CLAUDE.md sensitive path; row in 12-governance/09-human-review-ledger.md.
#         Not RATIFIED without a recorded human sign-off.
# ──────────────────────────────────────────────────────────
