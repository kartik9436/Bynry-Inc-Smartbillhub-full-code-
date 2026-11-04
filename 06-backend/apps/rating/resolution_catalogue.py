# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-15 (the resolution engine — CR-013 design §A2)
#           Screens: — (a pure read adapter; its refusals surface where its
#           caller's do)
#           No US-ID in this header ON PURPOSE, for the reason
#           `apps/rating/resolution.py` gives: G10 reads a Trace-header US-ID as
#           "this file ships that story's TCs" and EP-RAT-15's stories are not
#           authored yet.
# Rules:    BR-RAT-007 (the version IN FORCE at the service date) · BR-RAT-030
#           (published plans only) · BR-RAT-088 / BR-RAT-108 (the charge code
#           owns the base, narrowed by service, size and customer class) ·
#           BR-RAT-032 (contiguity per size group) · BR-RAT-102 (the
#           outside-city factor and its per-service exemptions) · BR-RAT-081
#           (a service is declared metered or unmetered) · BR-RAT-120 (PO
#           2026-08-28 — `served_sizes` is what the TENANT HAS CONFIGURED, so
#           R3's "this size is not served" refusal can actually fire) ·
#           BR-RAT-730 (the two columns that say WHICH codes ride a periodic
#           bill — carried through verbatim, never repaired here) ·
#           BR-RAT-731 (the amount RULE travels so R4 can name what is in the
#           way instead of blaming a connection size)
# Defects:  DEF-438 (the chain has no production caller — this file is the
#           missing half it names) · DEF-452 · DEF-455 · DEF-484 · DEF-1810
#           (CLOSED by BR-RAT-120 — the caller could widen the size axis, so a
#           3-inch connection priced at the 5/8 rate, $8.00 both ways) ·
#           DEF-2060 (a size configured with a MINIMUM row but no size-scoped
#           tiers published an empty tier tuple, pricing its usage at nothing) ·
#           DEF-498 / DEF-493 (CLOSED 2026-08-28 — six columns were on the table
#           and not on the contract) · DEF-2340 (a per-case code and an unpriced
#           code are the same stored row) · DEF-2824 (CLOSED 2026-08-31 —
#           `tax_facts` called `plan_tax_rules` with NO customer class, NO
#           premises and NO service list; all three restrictions FAIL CLOSED, so
#           every restricted tax was dropped from every ruled bill on every
#           tenant, under a comment asserting the narrowing had already happened)
# Tests:    06-backend/tests/test_def_438_parity.py
#           06-backend/tests/test_br_rat_120_size_refusal.py
#           06-backend/tests/test_def_498_def_493_charge_code_recurrence.py
#           06-backend/tests/test_def2824_tax_narrowing_facts.py
#           06-backend/tests/test_def_rat_8002_two_readers_agree.py
# Impacts:  apps/billing/gather.py (the path this is being cut over TO — not
#           yet called from there; see the module docstring)
# ───────────────────────────────────────────────────────
"""DB → `resolution.Catalogue`: the adapter DEF-438 says does not exist.

HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING — this file feeds rating math, a CLAUDE.md
sensitive path, AI-authored under the PO ruling of 2026-08-09 ("AI will do it;
we will review it later as human"). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a recorded human
sign-off. It implements signed law and never invents it.

WHY THIS FILE EXISTS
--------------------
`apps/rating/resolution.py` is ~1,150 lines implementing design §A2's R1–R7
narrowing, and it has **no production caller** (DEF-438). Its own lifecycle
trailer says why in one sentence:

    "this module is the narrowing LAW with its refusals proved; the DB-backed
    adapter that feeds it is the next slice, and until it lands
    `apps/billing/gather.py` remains the shipped R1/R2/R7 path."

This is that slice. It reads rating's OWN tables — rating owns them (B1) — and
returns the frozen, pure `Catalogue` the chain narrows. It holds no money
arithmetic, no clock and no cross-module read: the ACCOUNT's facts, the
PREMISES' facts and the METER's facts are the caller's to supply, because they
belong to customers, metering and assets and rating may not touch those tables.

WHAT IT IS DELIBERATELY NOT
---------------------------
**It is not wired into the bill run, and this commit does not wire it.** The
cutover from `apps/billing/gather.py` is being proved one step at a time by
`tests/test_def_438_parity.py`, which prices both paths and names the step and
both figures wherever they differ. A step is flipped only where parity is
already green. Building the adapter and flipping the caller in one commit is
exactly the big-bang this work exists to avoid — the parity harness is the
deliverable that makes each later flip provable, and it needs this file to run
at all.

⚠ WHAT THE DATABASE CANNOT YET SAY, NAMED RATHER THAN DEFAULTED
---------------------------------------------------------------
Three of the chain's inputs have storage that the shipped fixture leaves empty,
and each is an OPEN defect rather than an opinion. This adapter reports them by
returning what the tables actually hold; it never fills one in:

  * **R4 has nothing to narrow on.** No seeded plan carries an
    `account_type_id` (DEF-452) and the rating seeder writes no base charge
    codes at all (DEF-455), so `Catalogue.charge_codes` comes back EMPTY for
    the shipped tenant and `resolve_base_charge` returns None for every
    service. The chain's own fallback then reads R3's size row, which is the
    pre-BR-RAT-088 behaviour and is what the live path does today.
  * **R3 IS A MEMBERSHIP TEST AND `size_rows` NO LONGER PRICES ANYTHING
    (`DEF-2823`, 2026-08-31).** This note used to read *"R3's per-size base grid
    is `charge_code_amounts`, which is EMPTY; `size_rows` is therefore built
    from the version's scalar `base_charge`"* — an honest statement about the
    data that turned out to be a defect in the chain. `BR-RAT-088` RETIRED
    `tariff_versions.base_charge` and `RateScheduleWizard` removed its control
    in the same ruling, so **every schedule version a real utility creates
    stores NULL there** and R3 refused every size of every tenant that had
    adopted the ruling — 47 of 47 accounts on this fixture, while the live path
    billed all 47 correctly.
    **The KEYS of `size_rows` are now the whole of R3** (`resolve_served_size`:
    does this schedule serve this size), and the VALUE is read at ONE place —
    `resolve` uses it as R4's LEGACY fallback for a tenant that has declared no
    `is_base` charge code, never as a gate. The AMOUNT is the charge code's,
    per size from `charge_code_amounts` where the code prices per size.
    ⚠ **AND *"the tenant serves"* BECAME LITERAL ON 2026-08-28** — until then
    the sizes came from the CALLER and the phrase was aspirational
    (`DEF-1810`). See `configured_sizes_for`. A consequence the PO ruled on with
    its cost stated — *"Read the second way, the system refuses bills that price
    perfectly well today"* — is that a BANDED service whose schedule version
    configures no size at all serves NO size and refuses every meter by name.
    **Nothing is switched on by any of it: this chain still has no production
    caller and no bill changes.** The order is fixed by the same ruling — load
    the connection sizes first, switch the chain in after.
  * **R5's factor is stored (`rate_plans.outside_city_factor`) and no screen
    can set it** (DEF-466), so it is NULL on every row and `money_factor`
    resolves to `Decimal("1")` without ever consulting a jurisdiction.

Each of those is read from the column, so the day the column is filled the
adapter starts answering differently with no edit here — the late-binding
posture every seam in this repo takes, and the one that made `_premises_geography`
correct on the day BR-RAT-101 landed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Q

from apps.rating import charge_prices, models, plan_versioning, resolution
from apps.rating.constants import ALL_SIZES
from core import batch_reads


class AmbiguousDiscountVersion(RuntimeError):
    """Two `active` discount versions are in force on one service date.

    `DEF-RAT-8050`. Raised instead of picking one, for the reason
    `selectors.in_force_version` gives about its own object: *"That is not a
    tie-break, it is a coin toss on a money path."* The database refuses this
    shape from `rating/0049` onward; this exists because the test suite runs on
    SQLite, which has no exclusion constraints at all (hard-won law 14), and
    because a raise names BOTH rows where PostgreSQL names one key.
    """


__all__ = [
    "build_catalogue",
    "base_code_sizes_for",
    "configured_sizes_for",
    "plan_version_facts",
    "size_classes_for",
    "NO_SIZE_AXIS",
]

#: The `size_rows` key a service with NO SIZE AXIS AT ALL is priced under —
#: sewer, which BR-TEN-171 rules to have no size classes because BR-RAT-015
#: prices it as a share of the water usage charge and it reads no register of
#: its own.
#:
#: It is the EMPTY STRING because that is already what `resolution._size_key`
#: produces for a fact carrying no size, so a blank size RESOLVES here rather
#: than refusing. **A blank size on such a service is CORRECT and is not an
#: error** (BR-RAT-120, PO ruling 2026-08-28) — which is a different fact from a
#: banded service whose meter has no size recorded, and that one still refuses.
NO_SIZE_AXIS = ""


def _dec(value: Any) -> Decimal | None:
    """A stored NUMERIC as a Decimal, preserving NULL as None.

    NULL IS NOT ZERO anywhere in this module (DEF-277, CR-013 part 1: *"blank
    base = size not served"*). A stored `0.00` is a PRICE and travels as
    `Decimal("0")`; an absent figure travels as `None` and the chain refuses on
    it. Collapsing the two is the shape of DEF-154 and of DEF-277 both.
    """
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _tenant_id() -> Any:
    from apps.rating.selectors import _tenant_id as tenant_id  # local: RLS context

    return tenant_id()


# ── R1 · the plan versions this unit could be on ────────────────────────────


@batch_reads.memoised
def plan_version_facts(plan_id: Any) -> tuple[resolution.PlanVersion, ...]:
    """R1's candidates for ONE plan id.

    ⚠ **A PUBLISHED PLAN WITH NO `effective_from` IS NOT IN FORCE, AND THE LIVE
    PATH DISAGREES.** `resolution.PlanVersion.in_force_on` requires a stated
    start date; `apps.rating.selectors.plan_ref` — what the bill run reads
    today — filters on `status="published"` and consults no date at all. So a
    published plan whose dates nobody typed bills forever on the live path and
    refuses at R1 on this one.

    **That divergence is REPORTED, not resolved here** (see
    `tests/test_def_438_parity.py`, and the defect it cites). This function
    hands the chain what the column says; deciding what a dateless published
    plan MEANS is a rule question and CLAUDE.md's prime directive forbids a lane
    answering it by choosing a value.

    Only PUBLISHED plans are returned (BR-RAT-030) — the same filter
    `plan_ref` applies, so the two paths at least start from the same rows.
    """
    plan = (
        models.RatePlan.objects.filter(tenant_id=_tenant_id(), pk=plan_id, status="published")
        .prefetch_related()
        .first()
    )
    if plan is None:
        return ()
    # ── `BR-RAT-1066` · ONE CANDIDATE PER PRICEABLE PLAN VERSION ─────────────
    # A plan version has dates and owns its bindings (`OQ-324` CLOSED (B),
    # 2026-10-03), so R1's candidates are the plan's published, un-superseded
    # versions, each with ITS window and ITS services and schedules — and R1's
    # existing rule (*"the plan version in force on the service-period end
    # date"*, refusing two) picks one. A plan with ONE version yields one
    # candidate carrying the plan's own window, exactly as before; the
    # database lock (`ex_plan_versions_no_overlap`) is why two can never both
    # cover a date.
    versions = plan_versioning.priceable_versions(plan.id)
    if len(versions) <= 1:
        # ONE priceable version (every plan before `BR-RAT-1066` and every plan
        # never given a second): the PLAN's own window and its head's rows —
        # byte-identical to what this read returned before versions had dates.
        versions = [None]
    out = []
    for version in versions:
        vid = getattr(version, "pk", None) or plan.head_version_id
        services = list(
            models.PlanService.all_versions.filter(
                tenant_id=_tenant_id(), rate_plan_id=plan.id, plan_version_id=vid
            ).select_related("service")
        )
        bindings = list(
            models.PlanRateSchedule.all_versions.filter(
                tenant_id=_tenant_id(), rate_plan_id=plan.id, plan_version_id=vid
            ).select_related("service")
        )
        # ⚠ **THE UNION, NOT `plan_services` ALONE — AND THE DIFFERENCE IS A
        # LINE ON A CUSTOMER'S BILL.** A plan's service set lives in
        # `plan_services` and its schedule bindings in `plan_rate_schedules`,
        # and **nothing constrains the two to agree**. Taking only the first
        # would make a service that is BOUND TO A SCHEDULE but missing from
        # `plan_services` vanish from the bill in silence (R2 would never be
        # asked about it). The union makes the disagreement LOUD instead — R2's
        # own standard: *"a bill missing a service the customer pays for is a
        # configuration problem a human must see."* (`tests/test_us_met_helpers
        # .make_plan` writes the binding and no `plan_services` row at all.)
        declared = {row.service.code for row in services}
        bound = {row.service.code for row in bindings}
        out.append(
            resolution.PlanVersion(
                plan_id=str(plan.id),
                version=int(getattr(version, "version_no", None) or plan.version or 1),
                services=tuple(sorted(declared | bound)),
                effective_from=(
                    version.effective_from if version is not None else plan.effective_from
                ),
                effective_to=version.effective_to if version is not None else plan.effective_to,
                #: The plan binds a SCHEDULE; the DATE picks the version. Two
                #: narrowings, in that order — which is why a catalogue may hold
                #: six water schedules without any of them being ambiguous.
                schedules={row.service.code: str(row.tariff_id) for row in bindings},
            )
        )
    return tuple(out)


# ── R2 / R3 · the schedule versions and their size axis ─────────────────────


@batch_reads.memoised
def size_classes_for(tariff_version_id: Any) -> tuple[str, ...]:
    """Every size this version says something about — its own rows, plus the
    per-size tier groups DEF-433 added.

    The NULL tier group is *"every size"* and is deliberately NOT a size: it is
    the rule, and a `size_class` value is the EXCEPTION to it (BR-RAT-032 as
    amended). It therefore contributes no key here.
    """
    sizes = {
        row.size_class
        for row in models.RateSizeRow.objects.filter(
            tenant_id=_tenant_id(), tariff_version_id=tariff_version_id
        )
    }
    sizes |= {
        row.size_class
        for row in models.RateTier.objects.filter(
            tenant_id=_tenant_id(), tariff_version_id=tariff_version_id
        ).exclude(size_class__isnull=True)
    }
    return tuple(sorted(size for size in sizes if size))


@batch_reads.memoised
def base_code_sizes_for(service_code: str, on_date: date | None = None) -> tuple[str, ...]:
    """**THE SIZES THE SERVICE'S BASE CHARGE CODE STATES A ROW FOR** — R3's axis
    from 2026-09-01, and the empty tuple means *this code states no size axis*.

    ⚠ **PO RULING 2026-09-01, verbatim: *"rate schedule will not provdie the
    size, charge code will provide"*.** It completes `BR-RAT-088`, which moved
    the base AMOUNT onto the charge code on 2026-08-20 and left the MEMBERSHIP
    question — *is this size priced at all* — reading the rate schedule
    (`configured_sizes_for`, the version's `rate_size_rows` and tier groups). So
    the amount came from one object and *which sizes exist* came from another.
    `BR-RAT-690` had already given `charge_code_amounts` a writer, a screen and
    three ratified readings, which is why this is a re-pointing rather than a
    new mechanism.

    **UNION ACROSS THE SERVICE'S `is_base` CODES, AND THE UNION IS DELIBERATE.**
    `BR-RAT-108` scopes a code to customer classes, so one service can hold
    `BASE-W` (residential) and `BASE-W-COM` (commercial) with different size
    tables. R3 is asked per SERVICE and is handed no customer class — it answers
    WHICH SIZE, and WHICH CODE is R4's narrowing. A size priced for one class
    and not the other therefore passes R3 and refuses at **R4 by name**
    (`charge_code_amount`: *"states no amount for connection size …"*), which is
    the same division of labour `BR-RAT-088`'s consequence clause sets out.
    Narrowing here instead would refuse a commercial meter for a size its own
    code prices, naming the wrong step.

    **A CODE PRICING FLAT STATES NO AXIS, AND THAT IS NOT AN EMPTY AXIS.** A
    flat `is_base` code prices every size at one figure — `BR-RAT-690`:
    *"a per-size table IS the flat amount stated once per size"* — so it makes no
    statement about which sizes exist and contributes nothing here. The caller
    falls back to the schedule's configuration, which is what the shipped
    fixture does: `BASE-W` is seeded flat at `$8.00` on purpose (`BR-RAT-088`),
    so **no tenant on this database changes axis today** and the day one prices
    per size its axis becomes that table with no edit here.

    Nothing is invented: the rows are returned exactly as stored, and a row
    whose amount is NULL still COUNTS as a size the code states — `BR-RAT-690`'s
    middle reading (*the utility does not serve this size*) is a refusal about
    MONEY and fires at R4, not a size that fails to exist.
    """
    codes = models.Charge.objects.filter(
        tenant_id=_tenant_id(), deleted_at__isnull=True, is_base=True, service__code=service_code
    ).values_list("id", flat=True)
    if not codes:
        return ()
    # CR-156-BRC10 — through the one lookup, on the day asked. The *All sizes*
    # row is a FLAT code's amount and states no axis, exactly as the paragraph
    # above says of a flat code; `stated_sizes` leaves it out.
    return tuple(sorted(charge_prices.stated_sizes(list(codes), on_date)))


@batch_reads.memoised
def base_is_one_price_for_all_sizes(service_code: str, named_charge_id: Any = None) -> bool:
    """**IS THIS SERVICE'S BASE ONE PRICE FOR EVERY SIZE?** — the question an
    unsized meter is now asked (`DEF-RAT-8822`, PO 2026-10-01, option A).

    PO verbatim: *"Hold back only where the price depends on the size. If the
    base is one price for all sizes, the bill goes out at $12.41 with the
    warning. If the base differs by size, it's still held as today, so nobody
    is billed the wrong size's rate."*

    True only when the service's base charge code(s) — every `is_base` code of
    the service, plus the code the schedule version NAMES when it names one —
    carry an *All sizes* price and state NO per-size row. Then a meter with no
    recorded size cannot be charged the wrong size's base, because there is no
    other size's base to charge, and R3 lets it through (`BR-RAT-120` NARROWED
    to size-priced bases).

    **False in every other case, and False holds the account exactly as
    today:** a code with any sized row (`5/8" $8.00, 2" $34.00`), no base code
    at all (the 2026-09-30 `$0` base is not a price that is the same for every
    size, it is the absence of one), or a code with no row in force. The union
    is deliberate and conservative: a residential code priced flat beside a
    commercial code priced per size holds, because R3 is not handed the
    customer class.

    Undated, exactly as `base_code_sizes_for` is when R3's axis is read, so the
    adapter and the catalogue answer from the same rows.
    """
    codes = list(
        models.Charge.objects.filter(
            tenant_id=_tenant_id(), deleted_at__isnull=True, is_base=True, service__code=service_code
        ).values_list("id", flat=True)
    )
    if named_charge_id is not None and named_charge_id not in codes:
        codes.append(named_charge_id)
    if not codes:
        return False
    rows = [row for found in charge_prices.rows_in_force(codes).values() for row in found]
    if any(not row.is_flat and row.size_class for row in rows):
        return False
    return any(row.is_flat for row in rows)


def configured_sizes_for(tariff_version_id: Any, service_code: str) -> tuple[str, ...]:
    """BR-RAT-120 — the sizes the TENANT HAS CONFIGURED on this schedule version.

    **This function is the whole of the PO's ruling of 2026-08-28**, verbatim:
    *"we need to charge account based on connection size they have"*. Until that
    ruling `schedule_version_facts` built its size axis as
    ``served_sizes | size_classes_for(version)`` where `served_sizes` came from
    the CALLER — normally the size the account's meter actually is. So the size
    R3 looked up was, by construction, one the catalogue had just been told to
    serve, and R3's *"this size is not served"* refusal was dead code
    (`DEF-1810`). Worked on one tenant and one plan: ``served_sizes=('5/8',)``
    resolved **$8.00**, and ``served_sizes=('3-inch',)`` — a size the utility
    never priced — resolved **$8.00 as well**. Charging a 3-inch connection at
    the 5/8 rate is not charging based on the connection size the account has.

    The axis is now read from CONFIGURATION and the caller cannot widen it.

    THREE DIFFERENT FACTS, KEPT APART — the discipline is
    `apps/tenancy/service_size_classes.py`'s and its docstring is the authority:
    *"an empty tuple means 'ruled to have none' (sewer) and a raise means
    'nobody has said' (these two). The two readings must never collapse into
    each other, because one is a finished decision and the other is money nobody
    has priced."*

        the version states sizes      -> THOSE sizes, and no others.
                                         A size absent from them refuses at R3
                                         BY NAME and never falls back to another
                                         size's rate.
        no sizes, service RULED to
        have none (sewer)             -> `(NO_SIZE_AXIS,)` — one ladder, priced
                                         at a BLANK size, which is CORRECT here
                                         and is not an error.
        no sizes, service priced by
        CAPACITY (solar, battery,
        storm water, broadband)       -> `(NO_SIZE_AXIS,)` too, and by a
                                         DIFFERENT route: it HAS size rows and
                                         they are a catalogue of installable
                                         equipment, not a rate axis. Reading
                                         those rows as bands is `DEF-3098` and
                                         refused every bill on such a schedule.
        no sizes, service IS banded   -> `()` — this version prices no size at
                                         all, so every size refuses by name.
                                         **This is the reading the PO chose with
                                         its cost stated:** *"Read the second
                                         way, the system refuses bills that
                                         price perfectly well today."*
        no sizes, bands NEVER RULED
        (thermal steam OQ-560)        -> `SizeClassNotRuled` propagates. It stays
                                         *"nobody has priced this"* and never
                                         becomes *"no size"*.

    ⚠ **THE RATIFIED LAW IS READ THROUGH `resolution`, AND NO TENANCY TABLE IS
    QUERIED.** B1 forbids rating reading tenancy's TABLES;
    `apps.tenancy.service_size_classes` holds no model and issues no query — it
    is ratified law expressed as data, and its own Trace header already names
    `apps/rating/resolution.py` under `Impacts` with the reason: *"base charge
    resolves service -> account type -> size class, so these codes are a rating
    input"*. It is consulted for ONE question only — *does this service's price
    vary by size class* — and never to widen a version's axis, because the
    platform's ratified class list is the SEED for a tenant's reference data and
    not a statement about what any schedule prices.
    """
    # ── THE CHARGE CODE IS ASKED FIRST (PO ruling 2026-09-01) ─────────────
    # *"rate schedule will not provdie the size, charge code will provide"*.
    # `BR-RAT-088` moved the base AMOUNT here on 2026-08-20 and its own words
    # left the MEMBERSHIP question behind — *"a size absent from the SCHEDULE
    # still means not served"* — so the amount was read off the charge code and
    # *which sizes exist* off the rate schedule. **SUPERSEDED at that word
    # only:** where the service's `is_base` code states a per-size table, THAT
    # table is the axis and the schedule's configuration is not consulted.
    #
    # It NARROWS and never widens, which is `BR-RAT-120`'s standing constraint:
    # a size the code does not state refuses BY NAME at R3 and never falls back
    # to another size's rate. A code pricing FLAT states no axis at all (see
    # `base_code_sizes_for`) and the schedule answers, unchanged — which is
    # every tenant on this database today, so no bill and no fixture moves.
    from_code = base_code_sizes_for(service_code)
    if from_code:
        return from_code

    configured = size_classes_for(tariff_version_id)
    if configured:
        return configured
    # ── THE QUESTION IS "DOES THE PRICE VARY BY SIZE", NOT "ARE THERE ROWS"
    #    (DEF-3098, 2026-09-02) ────────────────────────────────────────────
    # This branch used to read `size_classes_for_service(service) == ()` and
    # treat "no rows" as "not banded". Those were the same fact for as long as
    # only banded services had rows; `CR-062` group A gave solar, battery, storm
    # water and broadband a CATALOGUE OF INSTALLABLE EQUIPMENT, and a catalogue
    # is not a rate axis. A capacity service HAS rows and does NOT band — its
    # price is one flat figure per kW (per ERU, per Mbps) times the SUM of what
    # is installed — so it flipped from one blank ladder to NO SIZE PRICED AT
    # ALL, which refuses every bill on such a schedule:
    #
    #     assert battery.size_rows == sewer.size_rows
    #     AssertionError: assert {} == {'': Decimal('8.000000')}
    #
    # `resolution.service_prices_by_size_class` is the question asked properly,
    # and its docstring is the authority. It is not a special case for battery:
    # nothing here names a service, TRASH still answers True (its size PICKS the
    # rate and the count multiplies it), and a BANDED service whose schedule
    # configures no size still serves none and still refuses by name — which is
    # `BR-RAT-120`'s ruling with the cost the PO accepted in as many words.
    #
    # Raises `SizeClassNotRuled` (a `NotImplementedError` carrying its OQ-ID) for
    # thermal steam, and `KeyError` for a code that is not one of the ten
    # platform services. Both propagate on purpose: the prime directive forbids
    # answering an unruled boundary by choosing a value, and a service nobody
    # recognises must stop a bill rather than be priced under a guess.
    if resolution.service_prices_by_size_class(service_code):
        return ()
    return (NO_SIZE_AXIS,)


@batch_reads.memoised
def _tier_prices(version_id: Any, size_class: str | None) -> tuple[Decimal, ...]:
    rows = models.RateTier.objects.filter(
        tenant_id=_tenant_id(), tariff_version_id=version_id, size_class=size_class
    ).order_by("seq")
    return tuple(_dec(row.unit_price) or Decimal("0") for row in rows)


@batch_reads.memoised
def schedule_version_facts(tariff_id: Any) -> tuple[resolution.ScheduleVersion, ...]:
    """R2's candidates for ONE bound schedule, each carrying R3's size axis.

    ⚠ **THE `served_sizes` KEYWORD IS GONE, AND ITS REMOVAL IS THE PO's RULING
    OF 2026-08-28** (`BR-RAT-120`, verbatim: *"we need to charge account based
    on connection size they have"*). It used to let the CALLER name the sizes
    this schedule serves, which meant the size R3 looked up was always one the
    catalogue had just been told to serve — see `configured_sizes_for` for the
    worked $8.00 / $8.00 pair. It is REMOVED rather than ignored: a caller that
    still passes it now gets a `TypeError` at the call site instead of a
    silently narrower catalogue.

    The size axis is `configured_sizes_for(version, service)` — what the TENANT
    has configured — and the caller cannot widen it.

    ⚠ **THE VALUE IN `size_rows` IS THE VERSION'S RETIRED SCALAR AND IT NO
    LONGER PRICES A BILL (`DEF-2823`, 2026-08-31).** This note used to say the
    scalar WAS the base, *"repeated per size"*, and that was an honest statement
    about the data while nothing else could answer. It is a defect now:
    `BR-RAT-088` retired `tariff_versions.base_charge` and `RateScheduleWizard`
    removed its control in the same ruling, so **every version a real utility
    creates stores NULL there** — and R3, reading it, refused 47 of 47 accounts
    of this very fixture while the live path billed all 47 at `$8.00`.

    **The KEYS are R3's whole answer** — the sizes this version serves, which
    `resolve_served_size` tests membership against. **The VALUE is read at ONE
    place**: `resolution.resolve` takes it as R4's LEGACY fallback for a tenant
    that has declared no `is_base` charge code, so such a tenant keeps billing
    what it has always billed, with `base_source="schedule"` recorded on the
    line. It is never a gate, and a `None` here is no longer a refusal — the
    refusal moved to R4, which is where the money is.

    Nothing is invented either way: the scalar is carried exactly as stored, and
    a version whose `base_charge` is NULL yields `None` for every size.
    """
    # ── `DEF-RAT-8002` · THE CORRECTED ROW IS EXCLUDED HERE TOO ─────────────
    # ⚠ **TWO READERS OF ONE TABLE DISAGREED, AND THAT IS HOW A MOVE-OUT FINAL
    # BILL REFUSES WHILE THE ORDINARY RUN BILLS.** This query had no
    # `superseded_by` filter at all. The live bill run's read —
    # `selectors.in_force_version` — has carried
    # `.filter(superseded_by__isnull=True)` since `DEF-RAT-5715`, and its own
    # comment says exactly why: a CORRECTION restates the SAME window
    # (BR-RAT-104 / BR-RAT-1016 verb 2), so for any date in that window there
    # are TWO rows whose window contains it, and *"the order-by decides which
    # one prices — by `effective_from`, which is IDENTICAL on both … That is
    # not a tie-break, it is a coin toss on a money path."*
    #
    # Without this line the resolution chain saw both rows, R2 counted two
    # versions in force and raised `AmbiguousSchedule` — so every path built on
    # the chain (the one-time bill, the move-out final bill) REFUSED on a
    # schedule the nightly run priced without complaint. The refusal was not
    # wrong about what it saw; it was seeing rows the pricing rule had already
    # removed.
    #
    # ⚠ **IT IS `superseded_by` AND NOT AN "ACTIVATED" FILTER.** Drafts are
    # dropped four lines below, by `effective_from is None`, which is
    # `activated_versions`' predicate written out — that is left where it is
    # because the comment there explains what a draft's absence means to a
    # refusal message. Both halves of `in_force_version` are now present, in
    # the same order.
    versions = models.TariffVersion.objects.filter(
        tenant_id=_tenant_id(), tariff_id=tariff_id, superseded_by__isnull=True
    ).select_related("tariff", "tariff__service", "base_charge_code")
    facts: list[resolution.ScheduleVersion] = []
    for version in versions:
        if version.effective_from is None:
            # NULL `effective_from` is the resumable DRAFT (BR-RAT-031), never a
            # priced version. `in_force_on` would refuse it anyway; dropping it
            # here keeps an AmbiguousSchedule refusal from naming a row no
            # customer could ever be billed from.
            continue
        version_id = str(version.id)
        scalar_base = _dec(version.base_charge)
        minimums = {
            row.size_class: _dec(row.minimum_bill)
            for row in models.RateSizeRow.objects.filter(
                tenant_id=_tenant_id(), tariff_version_id=version.id
            )
        }
        service_code = version.tariff.service.code
        sizes = configured_sizes_for(version.id, service_code)
        # Which object answered — carried so R3's refusal names the screen a
        # clerk has to open. Asked the same way `configured_sizes_for` asks it,
        # never inferred from whether `sizes` is empty: a service with NO base
        # code and no configured size is also empty, and the two send a person
        # to different places.
        axis_source = "charge_code" if base_code_sizes_for(service_code) else "schedule"
        facts.append(
            resolution.ScheduleVersion(
                version_id=version_id,
                service=service_code,
                # ── `CR-120-BRC06` · `BR-RAT-1025` — THE NAMED CODE, RESOLVED
                # TO ITS CODE STRING ONCE, HERE. R4 matches on `ChargeCode.code`
                # and every refusal in that module names a code, so carrying a
                # uuid onto the hot path would force a lookup inside the loop
                # that prices. `select_related` above makes it free.
                #
                # **None on every version that exists**, because `rating/0037`
                # adds the column NULL and backfills nothing — so R4 falls
                # through to the `is_base` lookup and prices exactly what it
                # priced yesterday.
                #
                # ⚠ **A SOFT-DELETED CODE IS STILL NAMED HERE, DELIBERATELY.**
                # This is a read of what the version SAYS, not a judgment about
                # whether it is still sound; judging that is
                # `services._guard_bound_base_charge_code`'s job at activation,
                # and R4's own refusal if it somehow reaches a bill. Silently
                # dropping the binding here would put the schedule back on the
                # inferred route with nothing on the line to say it happened —
                # a fallback nobody asked for, invisible to `base_source`.
                base_charge_code=(
                    version.base_charge_code.code if version.base_charge_code_id else None
                ),
                tariff_id=str(version.tariff_id),
                effective_from=version.effective_from,
                effective_to=version.effective_to,
                # `BR-RAT-1055` · `DEF-RAT-8004` — R2's tie-break, so a legacy
                # overlap is answered by the SAME rule the nightly run uses
                # (`resolution.in_force_precedence`): newest `effective_from`,
                # then newest `created_at`, then id. Before 2026-10-01 R2
                # refused here while the run billed the newest.
                created_at=version.created_at,
                size_rows={size: scalar_base for size in sizes},
                size_axis_source=axis_source,
                # `DEF-RAT-8822` · PO 2026-10-01 (A) — an unsized meter passes
                # R3 only where the base is one price for every size.
                base_priced_by_size=not base_is_one_price_for_all_sizes(
                    service_code, version.base_charge_code_id
                ),
                minimum_bill_by_size=minimums,
                minimum_bill=_dec(version.minimum_bill),
                # ⚠ **AN EMPTY TIER TUPLE IS EXCLUDED, AND THAT IS A FIX, NOT A
                # TIDY-UP (`DEF-2060`).** `resolve_tiers` documents an ABSENT size
                # as *"uses the schedule's default tiers"*; a size PRESENT with
                # `()` is a different statement — *this size has no tiers at
                # all* — and prices every unit of usage at nothing. Before
                # BR-RAT-120 the two could not be told apart in practice,
                # because `size_classes_for` was only ever consulted for a
                # version that already had size-scoped rows. Now that a size can
                # be configured by a `rate_size_rows` MINIMUM row while its
                # tiers live in the NULL "every size" group (BR-RAT-032), the
                # distinction bills money.
                tiers_by_size={
                    size: prices
                    for size in size_classes_for(version.id)
                    if (prices := _tier_prices(version.id, size))
                },
            )
        )
    return tuple(facts)


# ── R4 · the charge codes ───────────────────────────────────────────────────


@batch_reads.memoised
def charge_code_facts(
    customer_class: str | None = None, service_date: date | None = None
) -> tuple[resolution.ChargeCode, ...]:
    """R4's candidates — the tenant's whole charge-code catalogue.

    `customer_classes` is `charges.applies_to_customer_classes` (BR-RAT-108, PO
    2026-08-21), a JSON inclusion list of platform `account_types.code` values
    where **NULL or `[]` means EVERY CLASS**. The empty tuple carries that
    meaning unchanged into `resolve_charge_codes`, whose narrowing reads
    `if code.customer_classes and ...`.

    ⚠ **A CODE WITH PER-SIZE AMOUNTS AND A FLAT AMOUNT IS NOT REPAIRED HERE.**
    `resolve_charge_codes` refuses on exactly that combination, by name, because
    CR-013 part 2 gives a code ONE basis. Choosing one of the two in the adapter
    would move a refusal the chain exists to make into a silent preference.

    ⚠ **AND SIX COLUMNS THAT WERE ON THE TABLE AND NOT ON THE CONTRACT NOW
    TRAVEL (`DEF-493` + `DEF-498`, 2026-08-28).** `charge_type`, `auto_apply`,
    `amount_rule`, `percent`, `min_amount` and `max_amount` are read here and
    passed through **verbatim, with no repair and no default**:

    * `charge_type` is carried as stored, `None` included. It is NOT read as
      `recurring` when absent — `BR-RAT-730` says an unstated type is a fact
      about the configuration, not a licence to guess, and the chain narrows on
      it. Blanking it here would be that guess wearing an adapter's coat.
    * `auto_apply` is a `BooleanField(default=False)`, so it is never NULL and
      the `bool()` is a type coercion rather than a decision. **The reading of
      that `False` is `BR-RAT-730`'s** — a declaration, not a gap — and it is
      made in the chain where it can be read, never here.
    * the three money-shaped columns ride through `_dec`, which is this
      module's single Decimal boundary. `percent` stores a FRACTION (`0.015`
      for 1.5%, `models.Charge`'s own comment and US-RAT-008 TC-3), and nothing
      here scales it: R4 does not price a percentage, it REFUSES one by name,
      and a converted figure would be a number nobody asked for on a refusal
      path.
    """
    rows = list(
        models.Charge.objects.filter(tenant_id=_tenant_id(), deleted_at__isnull=True).select_related(
            "service"
        )
    )
    # ── CR-156-BRC10 · ONE QUERY, ON THE SERVICE DATE, THROUGH THE ONE LOOKUP ─
    # Rule 1 — a CLASS-SPECIFIC ROW BEATS THE EVERY-CLASS ROW, and a row for
    # ANOTHER class is not a candidate (CR-087 A1) — used to be this loop's own
    # sort order over `charge_code_amounts`. It is `charge_prices.resolve_for_
    # class` now, shared with `selectors.base_charge_from_charge_code`, so the
    # two live reads of the table cannot disagree. A killed row still prices
    # its own dates; the day is the bill's service date.
    tables = charge_prices.resolved_tables(rows, service_date, customer_class)
    codes: list[resolution.ChargeCode] = []
    for row in rows:
        table = dict(tables.get(row.id, {}))
        flat_row = table.pop(ALL_SIZES, None)
        amounts: dict[str, Any] = {size: _dec(price.amount) for size, price in table.items()}
        classes = row.applies_to_customer_classes or []
        codes.append(
            resolution.ChargeCode(
                code=row.code,
                service=row.service.code if row.service_id else None,
                customer_classes=tuple(str(code) for code in classes),
                is_base=bool(row.is_base),
                # ── BR-RAT-730 · WHEN this code fires, as the tenant declared
                # it on the S12 card. Neither column is repaired: `charge_type`
                # keeps its NULL and `auto_apply` keeps its False.
                charge_type=(row.charge_type or None),
                auto_apply=bool(row.auto_apply),
                # ── DEF-498 · HOW its amount is expressed. Carried so R4 can
                # SAY what is in the way; it still prices only `flat` and the
                # per-size table.
                amount_rule=(row.amount_rule or None),
                percent=_dec(row.percent),
                min_amount=_dec(row.min_amount),
                max_amount=_dec(row.max_amount),
                # A code carrying a per-size table states its amounts THERE.
                # `charges.amount` is the flat one, and passing both would trip
                # the chain's own refusal on a row the wizard considers valid.
                flat_amount=(
                    None if amounts or flat_row is None else _dec(flat_row.amount)
                ),
                amounts=amounts,
                # ⚠ `charges.outside_city_applies` HAS NO COLUMN (DEF-373 names
                # it among the eight things CR-013 part 2 requires of a charge
                # code and no column holds). `getattr` degrades to the chain's
                # own default of True the day it lands, with no edit here.
                outside_city_applies=bool(getattr(row, "outside_city_applies", True)),
            )
        )
    return tuple(codes)


# ── R7 · the taxes ──────────────────────────────────────────────────────────


def tax_facts(
    plan_id: Any,
    service_date: date,
    *,
    customer_class: str | None,
    premises: dict[str, Any] | None,
    services: tuple[str, ...],
    account_id: Any,
) -> tuple[resolution.TaxRule, ...]:
    """R7's candidates, read through rating's OWN published selector.

    ⚠ **THE FOUR FACTS ARE REQUIRED KEYWORD ARGUMENTS AND THAT IS THE FIX
    (`DEF-2824`, 2026-08-31).** This function used to call
    `plan_tax_rules(plan_id, service_date)` positionally, under a comment
    asserting that *"`plan_tax_rules` has ALREADY applied the customer-class
    narrowing (DEF-273) before it returns; the rows that reach here are the ones
    that survived it."*

    **It had not, and it could not.** That selector's own docstring states the
    opposite outcome in the same words the code implements: *"EVERY ONE OF THEM
    FAILS CLOSED … A restriction the caller gave no context to evaluate — no
    class, no premises, no service list — means the restricted tax DOES NOT
    APPLY."* So the rows reaching here were the UNRESTRICTED ones, `resolve_taxes`
    was handed nothing to narrow, and **every class-scoped, premises-scoped or
    service-scoped tax was silently absent from every ruled bill on every
    tenant** — measured on the seeded utility as `Texas State` (6.25%, *commercial
    and industrial only*) attaching on the live path and not on this one, on both
    commercial accounts of a 47-account run.

    Nothing could have caught it. R7 publishes no refusal class by design — a
    failed applicability condition means NO LINE, never an error (DEF-273) — so
    the step is not refusable, and until `DEF-2798` landed nothing compared it
    either. Its only possible output was silence. Hard-won law 1, in the one step
    of the chain where no other signal could contradict the comment.

    **They are REQUIRED rather than defaulted so the failure cannot recur.** A
    default would restore exactly the arrangement the defect names — each layer
    believing the other narrowed — and would fail closed and silently again. A
    caller that cannot name the bill's facts now gets a `TypeError` at the call,
    which is a stack trace instead of a customer under-charged.

    ── WHERE EACH FACT NARROWS, AND WHY IT IS THE SELECTOR THAT HOLDS THEM ────
      * `customer_class` — `taxes.applies_to_customer_classes` (r10: *"Comm,
        Industrial only · Residential exempt"*).
      * `premises` — `premises_scope_kind` / `premises_scope_value`, over FIVE
        mechanisms. **Only this layer can evaluate them**: `resolve_taxes` has
        two booleans (`inside_city_only` / `outside_city_only`) and a tax scoped
        by STATE, or by a city NAME where no boundary flag was ever drawn, is
        expressible in neither.
      * `services` — `taxes.applies_to_services`. The caller passes the PLAN's
        service set (R1's own union) so a candidate is not pre-dropped; the
        SAME field travels onto `TaxRule.services` below and `resolve_taxes`
        narrows again to the services that actually resolved. The two are the
        same predicate over the same field, so the composition is exact and can
        only narrow.
      * `account_id` — DEF-383's exemption CERTIFICATE, and it is the gate that
        runs the other way: absent, a tax APPLIES. Omitting it charged a
        customer holding a live certificate, which is the direction that is not
        recoverable in the next cycle.

    Every one of them is a fact the chain has already resolved: three are
    `AccountFacts` / `PremisesFacts` the caller supplied, and the service set is
    read off this plan's own `plan_version_facts` in `build_catalogue`.
    """
    from apps.rating import selectors

    rules: list[resolution.TaxRule] = []
    for row in selectors.plan_tax_rules(
        plan_id,
        service_date,
        customer_class=customer_class,
        premises=premises,
        services=services,
        account_id=account_id,
    ):
        rules.append(
            resolution.TaxRule(
                # `code` on this row is the JURISDICTION's name — the authority
                # a remittance report groups by (BR-BIL-069). It is carried
                # verbatim rather than re-derived, because the tax's identity
                # and its rate must name the same row.
                code=str(row.get("code") or row.get("tax_id") or ""),
                tax_id=row.get("tax_id"),
                rate=_dec(row.get("rate")),
                flat_amount=_dec(row.get("flat_amount")),
                # ⚠ NOT ONLY AN APPLICABILITY GATE — this field also NARROWS THE
                # BASE (DEF-465): a city franchise fee is 1.5% of the electric
                # lines, not 1.5% of the whole bill. So it travels whatever the
                # selector already decided with it.
                services=tuple(row.get("applies_to_services") or ()),
                # ⚠ EMPTY, AND THE REASON IS NOW A CALL YOU CAN READ TEN LINES
                # UP RATHER THAN A CLAIM (`DEF-2824`). `customer_class` is passed
                # to `plan_tax_rules` above, so a class-restricted tax that did
                # not survive is not in this loop at all. Re-stating the classes
                # here would narrow the same fact twice — and would do it with a
                # DIFFERENT comparison: the selector case-folds
                # (`str(code).strip().lower()`) where `resolve_taxes` matches
                # exactly, so a tax stating `["Commercial"]` would pass one gate
                # and fail the other. A second implementation of a money rule
                # that can disagree with the first is worse than no second one.
                customer_classes=(),
            )
        )
    return tuple(rules)


# ── The catalogue ───────────────────────────────────────────────────────────


def build_catalogue(
    *,
    plan_id: Any,
    service_date: date,
    account: resolution.AccountFacts,
    premises: resolution.PremisesFacts,
    unmetered_services: tuple[str, ...] = (),
) -> resolution.Catalogue:
    """Everything CONFIGURED that could price this plan's bill. §A1's catalogue.

    ⚠ **`account` AND `premises` ARE REQUIRED, AND THEY REACH EXACTLY ONE
    THING — R7 (`DEF-2824`, 2026-08-31).** Everything else here is configuration
    and stays configuration: the plan versions, the schedule versions, the charge
    codes, the discounts and R5's factor are read from the tenant's tables and
    narrowed by the CHAIN against these same facts, which is what keeps R1–R6 a
    pure function of what was configured.

    A TAX cannot be built that way, and the reason is in the data rather than in
    this file's taste: a tax states its own applicability — customer class,
    premises geography over five mechanisms, service list — and
    `rating.selectors.plan_tax_rules` evaluates every one of them **fail-closed**
    before it returns a row. Called with no facts it therefore returns only the
    UNRESTRICTED taxes, which is not a candidate set; it is a wrong answer that
    looks like a candidate set. `tax_facts` says what each fact narrows.

    **They are required rather than optional for the reason `tax_facts` gives:**
    a default here would silently re-create the bug, and it would fail closed, on
    money, in the one step that publishes no refusal.

    ⚠ **`served_sizes` WAS REMOVED FROM THIS SIGNATURE ON 2026-08-28** by the
    PO's ruling that a charge follows the account's actual connection size
    (`BR-RAT-120`, `DEF-1810`). The word CONFIGURED in the line above is now
    true of the size axis too: a caller states the account's facts, and the
    sizes a schedule serves are read from the schedule. See
    `configured_sizes_for`.

    `unmetered_services` is supplied by the CALLER and not read here, and that
    is a module boundary rather than an omission: the declaration lives on
    `tenancy.TenantService.metered` (BR-RAT-081) and rating may not query
    tenancy's tables (B1). It reaches the chain through whoever is already
    holding the tenant's service list.

    ⚠ **`tenant_services.metered` HAS NO READER IN THE PRODUCT AT ALL TODAY** —
    grep finds the column, its migration and two comments, and no query. So
    every caller currently passes `()` and every service is treated as metered,
    which is the pre-BR-RAT-081 behaviour. Reported rather than worked around.

    `discounts` come from the CATALOGUE (what the tenant offers); which of them
    an account is ENROLLED in is an `AccountFacts` field and therefore the
    caller's. R6 selects against both.
    """
    plan_versions = plan_version_facts(plan_id)
    return resolution.Catalogue(
        plan_versions=plan_versions,
        schedule_versions=_schedule_versions_for_plan(plan_id),
        charge_codes=charge_code_facts(account.customer_class, service_date),
        taxes=tax_facts(
            plan_id,
            service_date,
            customer_class=account.customer_class,
            premises=_premises_scope_facts(premises),
            services=_plan_services(plan_versions),
            account_id=account.account_id,
        ),
        unmetered_services=unmetered_services,
        discounts=_discount_facts(plan_id, service_date),
        outside_city_factor=_outside_city_factor(plan_id),
        outside_city_exempt_services=_outside_city_exempt_services(plan_id),
    )


def _plan_services(plan_versions: tuple[resolution.PlanVersion, ...]) -> tuple[str, ...]:
    """The service set R7's candidate query is narrowed by (`DEF-2824`).

    **R1's OWN ANSWER, not a second reading of the tables.** `plan_version_facts`
    has already taken the union of `plan_services` and `plan_rate_schedules` and
    said, in its own comment, why the union rather than either alone — *"a
    service that is BOUND TO A SCHEDULE but missing from `plan_services` would
    vanish from the bill in silence"*. Re-deriving it here would be a second
    implementation of that judgment.

    ⚠ **IT IS THE PLAN's SET AND NOT THE BILL's, AND THE DIFFERENCE IS SAFE FOR
    ONE STATED REASON.** `resolve()` builds R7's `services` from exactly this
    union too (every service on the plan either reaches `pending` or refuses the
    whole bill), so on the chain's own path the two are the same tuple. Where a
    caller's differs, this one can only be WIDER — and a wider service list can
    only ADMIT a candidate at `tax_applies_to`, never attach one, because
    `resolve_taxes` then re-applies the identical predicate over the identical
    field (`TaxRule.services`) against the services that actually resolved. The
    narrowing composes; it does not fail open.

    Every version is unioned rather than the in-force one picked: choosing among
    versions by date is R1's job and R1 refuses when it is not exactly one. A
    catalogue builder that quietly picked would answer a question R1 exists to
    refuse.
    """
    return tuple(sorted({service for version in plan_versions for service in version.services}))


def _premises_scope_facts(premises: resolution.PremisesFacts) -> dict[str, Any]:
    """`PremisesFacts` → the dict `selectors.premises_in_scope` reads (`DEF-2824`).

    Three keys and no more, because that predicate reads exactly three by name:
    `inside_city_limits` (the drawn boundary, BR-RAT-101), then `city` and
    `state` — the recorded geography it falls back to where no flag exists.
    `county` is NOT passed: `premises_in_scope` cannot answer a county scope at
    all (no column, no district table, no premise set) and returns False for it,
    and handing it a key it does not read would suggest otherwise.

    A None value is passed through as None rather than dropped. The predicate
    distinguishes *"the tenant stated no scope"* (the tax applies everywhere)
    from *"the tenant stated a scope and this premises cannot answer it"* (the
    tax reaches nobody), and only the second is what an absent fact means.
    """
    return {
        "inside_city_limits": premises.inside_city_limits,
        "city": premises.city,
        "state": premises.state,
    }


@batch_reads.memoised
def _schedule_versions_for_plan(
    plan_id: Any,
) -> tuple[resolution.ScheduleVersion, ...]:
    versions: list[resolution.ScheduleVersion] = []
    for binding in models.PlanRateSchedule.objects.filter(
        tenant_id=_tenant_id(), rate_plan_id=plan_id
    ).select_related("service"):
        versions.extend(schedule_version_facts(binding.tariff_id))
    return tuple(versions)


@batch_reads.memoised
def _outside_city_factor(plan_id: Any) -> Decimal:
    """BR-RAT-102's factor, or `Decimal("1")` when the plan does not price by
    jurisdiction.

    `Decimal("1")` is what `money_factor` short-circuits on, and the
    short-circuit is what stops R5 refusing a bill for a tenant who has no
    jurisdiction pricing at all. NULL on every row in the product today
    (DEF-466: nothing at any layer can set it), so this returns 1 everywhere and
    R5 is a no-op — which is also exactly what the live path does.
    """
    plan = models.RatePlan.objects.filter(tenant_id=_tenant_id(), pk=plan_id).first()
    # `BR-RAT-1066` — the factor of the plan version read on the day.
    factor = _dec(plan_versioning.terms_on(plan)["outside_city_factor"]) if plan else None
    return factor if factor is not None else Decimal("1")


@batch_reads.memoised
def _outside_city_exempt_services(plan_id: Any) -> tuple[str, ...]:
    """§A4 S2's *"BASE-S $8.00 (flat everywhere — the multiplier does NOT touch
    sewer)"*, read from `plan_services.outside_city_exempt`."""
    return tuple(
        sorted(
            row.service.code
            for row in models.PlanService.objects.filter(
                tenant_id=_tenant_id(), rate_plan_id=plan_id, outside_city_exempt=True
            ).select_related("service")
        )
    )


@batch_reads.memoised
def _discount_facts(plan_id: Any, service_date: date) -> tuple[resolution.DiscountRule, ...]:
    """R6's catalogue half — what this plan makes AVAILABLE (CR-013 part 3:
    *"plan attachment makes a discount available, not granted"*).

    ⚠ **`service_date` IS NEW AND IT CLOSES A REAL HOLE (`DEF-RAT-8050`).**
    This read filtered `status='active'` and then took `.order_by("-version_no")
    .first()` **with no date predicate at all**, so a discount's version
    history was read as *"the highest-numbered active row, whenever it starts
    or ends"*. Its sibling `discount_services.active_version` has always asked
    the window question (`effective_from <= day <= effective_to`), so the two
    readers of one table disagreed by construction. That is `DEF-483`'s tax
    defect and `DEF-RAT-8000`'s schedule defect, on the third priced object.

    ⚠ **AND `.first()` ON A MONEY PATH IS A COIN TOSS, NOT A TIE-BREAK** —
    `selectors.in_force_version`'s own words. Two `active` rows whose windows
    both contain `service_date` is an ambiguity nothing in this file may
    resolve, so it RAISES and names both rows. `rating/0049`'s
    `ex_discount_versions_no_overlap` is what makes that unreachable through
    the database; this is the same sentence one layer up, and it is the layer
    that still answers on SQLite, where no exclusion constraint exists at all
    (hard-won law 14).

    ⚠ **THE `getattr(discount_models, "VERSION_ACTIVE", "active")` FALLBACK IS
    GONE.** A default that resolves to a stale literal keeps a renamed constant
    working against the OLD spelling instead of failing — a silently wrong
    filter on a money read. The module is imported defensively above, which is
    the guard that was actually wanted; the constant itself is read directly,
    so a rename breaks loudly at the one place it must.

    Read late and defensively: `apps.rating.discounts` landed in a parallel lane
    (DEF-361) and a deployment whose migration has not run must degrade to "this
    tenant offers none" rather than raise inside a bill run. An empty tuple is
    the honest reading of an absent table here, because `DiscountResolution
    .modelled` — the field that distinguishes *the product cannot express this*
    from *this customer has none* — is the chain's to set and it sets True.
    """
    try:
        from apps.rating import discounts as discount_models
    except Exception:  # pragma: no cover - the table's own migration guard
        return ()
    rule_model = getattr(discount_models, "PlanDiscountRule", None)
    version_model = getattr(discount_models, "DiscountVersion", None)
    if rule_model is None or version_model is None:  # pragma: no cover
        return ()
    rules: list[resolution.DiscountRule] = []
    for row in rule_model.objects.filter(
        tenant_id=_tenant_id(), rate_plan_id=plan_id
    ).select_related("discount"):
        # ⚠ THE VALUE IS ON THE **VERSION**, NOT ON THE PLAN RULE. The plan
        # attachment says a discount is AVAILABLE (CR-013 part 3, verbatim:
        # *"plan attachment makes a discount available, not granted"*); the
        # figure and the stacking precedence are the discount's own, and they
        # are versioned so a rate change is reproducible (BR-RAT-037's shape,
        # one object over).
        in_force = list(
            version_model.objects.filter(
                tenant_id=_tenant_id(),
                discount_id=row.discount_id,
                status=discount_models.VERSION_ACTIVE,
                effective_from__isnull=False,
                effective_from__lte=service_date,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=service_date))
            .order_by("-effective_from", "-version_no")[:2]
        )
        if len(in_force) > 1:
            # NOT a tie-break — a coin toss on a money path. Two active
            # versions of one discount are both in force on `service_date`,
            # and picking by version number would reduce a bill by a figure
            # chosen because a row sorted first.
            raise AmbiguousDiscountVersion(
                f"discount {row.discount_id}: versions "
                f"{in_force[0].id} [{in_force[0].effective_from} → "
                f"{in_force[0].effective_to or 'open'}] and {in_force[1].id} "
                f"[{in_force[1].effective_from} → {in_force[1].effective_to or 'open'}] "
                f"are both active on {service_date}. A person must decide which one "
                "prices; this read may not."
            )
        version = in_force[0] if in_force else None
        value = _dec(getattr(version, "value", None)) if version is not None else None
        if value is None:
            # No ACTIVE version is not a zero discount. R6 selects and
            # `discount_pricing` prices; inventing a value here would reduce a
            # bill by a figure no configured object states.
            continue
        rules.append(
            resolution.DiscountRule(
                code=getattr(row.discount, "code", "") or "",
                value=value,
                # CR-013 part 3: *"stacking precedence, explicit because
                # percentage-of-usage after a usage allowance gives a different
                # number than the reverse."* Order is DATA.
                precedence=int(getattr(version, "stacking_precedence", 0) or 0),
            )
        )
    return tuple(rules)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-438 + CR-013 §A2 (as CORRECTED by the PO 2026-08-19) +
#         `apps/rating/resolution.py`'s own contract + B2 (rating owns these
#         tables) + BR-RAT-007/030/081/088/102/108
# generated: 2026-08-21 by the DEF-438 Wave A cutover lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a pure read adapter)
#         E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_def_438_parity.py
# exceptions: (1) NOT WIRED INTO THE BILL RUN BY THIS COMMIT, deliberately —
#         the cutover is proved step by step by the parity harness and a step
#         is flipped only where parity is already green. (1b) AMENDED 2026-08-28
#         for BR-RAT-120: `served_sizes` is removed from `build_catalogue` and
#         `schedule_version_facts`, and the size axis is read from the schedule
#         version. Still not wired; still no bill changes. (2) `size_rows` repeats
#         the version's SCALAR base across the sizes the caller asks for,
#         because `charge_code_amounts` — where BR-RAT-088 puts the per-size
#         base — is EMPTY on every tenant (DEF-455). Stated in the docstring
#         rather than hidden. (3) `unmetered_services` is the CALLER's to
#         supply: the declaration lives on `tenancy.TenantService.metered` and
#         rating may not read tenancy's tables (B1) — and nothing in the product
#         reads that column yet at all. (4) AMENDED 2026-08-28 for BR-RAT-730 /
#         BR-RAT-731 (DEF-493 + DEF-498): `charge_type`, `auto_apply`,
#         `amount_rule`, `percent`, `min_amount` and `max_amount` now travel on
#         `ChargeCode`, read straight off `charges` with NO repair and NO
#         default — a NULL `charge_type` stays NULL, because reading it as
#         `recurring` in the adapter is exactly the guess the rule forbids.
#         Still not wired; still no bill changes.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
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
