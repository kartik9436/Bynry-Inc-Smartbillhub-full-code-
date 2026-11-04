# ── Trace ──────────────────────────────────────────────
# Defects: DEF-438 (the R1–R7 chain has no production caller — this file is the
#          caller, in SHADOW) · DEF-494 (the two paths mean opposite things by
#          "a plan in force") · DEF-498 (R4 refuses every bill five times over)
#          · DEF-493 (R4 narrows by three things and would put the whole price
#          list on every bill) · DEF-514 (no connection size is stored anywhere)
#          · DEF-1810..DEF-1816 (the disagreements this file MEASURED)
# Rules:   BR-RAT-007 (the version in force at the SERVICE date) · BR-RAT-030
#          (published plans only) · BR-RAT-081 (a service is declared metered or
#          unmetered) · BR-RAT-088 (the charge code owns the base) · BR-MET-056
#          (a read stores the multiplier USED) · BR-BIL-039 (the preview and the
#          real run are the SAME code) · BR-RAT-120 (PO 2026-08-28 — the sizes a
#          schedule serves are the SCHEDULE's, so this file no longer hands the
#          catalogue the account's own sizes; DEF-1810 CLOSED)
# Tests:   06-backend/tests/test_def_1810_resolution_shadow.py
#          06-backend/tests/test_br_rat_120_size_refusal.py
# Impacts: apps/billing/gather.py (the path this shadows — UNCHANGED by this
#          file) · apps/rating/resolution.py · apps/rating/resolution_catalogue.py
# ───────────────────────────────────────────────────────
"""SHADOW MODE: price one account BOTH ways and name every step that differs.

HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING — this file feeds rating math, a CLAUDE.md
sensitive path, AI-authored under the PO ruling of 2026-08-09 ("AI will do it;
we will review it later as human"). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a recorded human
sign-off. It implements signed law and never invents it.

WHAT THIS IS, IN ONE SENTENCE
-----------------------------
Steps **1 (adapter)** and **2 (shadow)** of the six-step cutover recorded in
`12-governance/02-decision-log.md`, 2026-08-27, *"HOW R1–R7 GETS WIRED INTO
BILLING — run both, compare, rule, then switch. Never swap and hope."*

⚠ **IT CHANGES NOTHING ON ANY BILL, AND THAT IS A PROPERTY, NOT A LIMITATION.**
The decision log's table has one column headed *"what changes on a bill"* and
steps 1, 2, 3 and 4 all read **nothing**. `shadow_account` is called for its
REPORT; its return value has never priced an invoice line and must not, until
each class of disagreement has been RULED (step 4) and its step switched
individually (step 5). A caller that prices from a `ShadowOutcome` has done the
one thing that decision forbids.

WHY THIS IS CHEAP — the three facts the method rests on, re-verified here
------------------------------------------------------------------------
1. `resolution.resolve()` is PURE — frozen facts in, a `Resolution` out. No DB,
   no I/O. Running it beside the live path costs CPU and nothing else.
2. `gather_account()` has ALREADY loaded every fact the chain needs. This is a
   MAPPING job, not a data job — no new queries for the facts it carries.
3. The run already has a stage that shows every input before anything commits
   (S31.2, *"Check what we found"*), and BR-BIL-039 makes the preview and the
   real run the same code. That is where a disagreement belongs.

⚠ THE ONE RULE THIS FILE MUST NOT BREAK
---------------------------------------
**It may not make a disagreement go away.** Every divergence below is REPORTED
with both figures and neither is chosen. The decision log says it plainly: *"A
lane that makes the disagreements go away has destroyed the evidence this job
exists to produce, and has done it inside the one system where a wrong answer is
irreversible (hard rule 4)."* So there is no fallback, no default and no
`or Decimal("1")` anywhere in the adapter. Where a fact is missing, the adapter
says which fact and stops — see `MISSING_*` below.

⚠ AND IT MAY NOT DEFAULT A MULTIPLIER — the trap the harness names
------------------------------------------------------------------
`resolution.billable_quantity` multiplies the REGISTER DIFFERENCE by the meter
multiplier (BR-RAT-001: a ×10 register reading 62 is 620 kWh, which lands in
tier 2). `apps.metering.selectors.billing_reads_for_unit` publishes
`consumption` **already post-multiplier** (its own docstring: *"it is ALREADY
POST-MULTIPLIER"*). **Feeding the chain that figure would bill 100× on a ×10
register** — a plausible-looking document and a customer's ruin.

So `_quantities_from` feeds the chain `current_read − prior_read`, the RAW
register difference, and never `consumption`. The multiplier is then a fact the
adapter must obtain separately, and **billing's read seam does not publish one**
(`billing_reads_for_unit` returns no `multiplier` key). It is therefore read
through a late-bound metering seam that does not exist yet, and while it does
not exist the adapter reports `MISSING_MULTIPLIER` rather than passing 1.

**Passing 1 would be the worst available outcome**: it would make R3b's
comparison report PARITY on every account by construction, because ×1 of the
register difference equals metering's stored figure exactly when — and only
when — the multiplier really is 1. The parity would be an artefact of the
adapter, not a fact about the product. `resolution.MeterMultiplierUnstated`
exists for precisely this reason and its own message says so: *"an absent factor
is not 1"*.

WHY THE LATE BINDING, and why it is not the dead wiring law 2 forbids
---------------------------------------------------------------------
Billing must not import rating or metering at module scope — `rating_seam.py`
sets that rule and `_refusal_types` there explains it. Every cross-module read
here goes through `_seam`, which returns None while the owner has not published
the name. `gather.py` takes the identical posture for `connection_size_for` and
defends it in terms: *"What is missing is the SOURCE, and it has a defect row;
what is proved is the HOP."* The hop is proved the same way here — the tests
PUBLISH each seam and assert the fact reaches the chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

from apps.billing.contracts import AccountBillingData, ServiceReading

__all__ = [
    "Divergence",
    "ShadowOutcome",
    "MISSING_MULTIPLIER",
    "MISSING_CONNECTION_SIZE",
    "MISSING_ASSET_COUNT",
    "MISSING_PLAN",
    "STATUS_AGREED",
    "STATUS_DISAGREED",
    "STATUS_CHAIN_REFUSED",
    "STATUS_NOT_ATTEMPTED",
    "REFUSAL_STEPS",
    "UNREAD_FACTOR_NOT_NEEDED",
    "UNREAD_FACTOR_REFUSE",
    "adapt",
    "shadow_account",
    "summarise",
]


# ══════════════════════════════════════════════════════════════════════════
# The vocabulary — what a shadow run can SAY
# ══════════════════════════════════════════════════════════════════════════

#: A fact the chain requires that the live path does not carry. Each is a
#: MEASUREMENT, not an error: the adapter reports which fact and which service,
#: and the chain is not run rather than run on an invented value.
MISSING_MULTIPLIER = "meter_multiplier_not_published_to_billing"
MISSING_CONNECTION_SIZE = "connection_size_unresolved"
MISSING_ASSET_COUNT = "unmetered_asset_count_not_published_to_billing"
MISSING_PLAN = "account_has_no_plan"

STATUS_AGREED = "agreed"
STATUS_DISAGREED = "disagreed"
#: The highest-value row in the exercise (decision log, 2026-08-27): the chain
#: REFUSED where the live path produced a number — a bill that would have gone
#: out on a guess.
STATUS_CHAIN_REFUSED = "chain_refused"
#: The adapter could not assemble the chain's inputs, so nothing was compared.
#: ⚠ It is NOT parity. A shadow report that counted these as agreement would be
#: the comfortable lie the parity harness warns about.
STATUS_NOT_ATTEMPTED = "not_attempted"

#: Exception class name -> the design §A2 step it refuses at. The chain's NINE
#: typed refusals are its SIGNATURE (decision log, 2026-08-27, *"HOW THE SCREEN
#: PROVES R1–R7 IS WIRED"*): the live path refuses the same situation in
#: different words (`GATHER_SIZE_UNRESOLVED`) or does not refuse at all, so
#: **both sentences cannot be on the screen at once** and the screen is a probe
#: for which path ran.
REFUSAL_STEPS = {
    "NoPlanInForce": "R1",
    "NoScheduleForService": "R2",
    "AmbiguousSchedule": "R2",
    "SizeNotServed": "R3",
    "MeterMultiplierUnstated": "R3b",
    "AssetCountUnavailable": "R3b",
    "ChargeCodeAmountMissing": "R4",
    "JurisdictionUnstated": "R5",
    "DiscountsNotModelled": "R6",
}


@dataclass(frozen=True)
class Divergence:
    """One step where the two paths disagree.

    `live` and `chain` are the two values VERBATIM — never a boolean, never a
    summary. "Billing and rating disagree" is not actionable; *"R2 water: live
    resolved version 7, the chain resolved version 9"* is. The figures ARE the
    finding, which is why they are carried rather than compared away.
    """

    step: str
    service: str
    live: Any
    chain: Any
    note: str = ""

    def sentence(self) -> str:
        """One line a clerk can act on (BR-SHL-020 — a sentence, not a code)."""
        where = f"{self.step} {self.service}" if self.service else self.step
        tail = f" — {self.note}" if self.note else ""
        return f"{where}: the live path says {self.live!r}, the ruled path says {self.chain!r}{tail}"


@dataclass(frozen=True)
class ShadowOutcome:
    """What running BOTH paths on one account produced.

    `refusal_sentence` is the chain's OWN message, unedited. It names its step
    and the missing fact — *"R3: connection size … has no row on the rate
    schedule version …"* — and rendering the exception CLASS NAME instead is
    called out in the decision log as *"the lazy way to make the first test
    pass"*. The sentence is the product of this whole exercise; it is carried
    whole.
    """

    account_id: str
    account_no: str
    status: str
    divergences: tuple[Divergence, ...] = ()
    refusal_step: str | None = None
    refusal_type: str | None = None
    refusal_sentence: str | None = None
    #: ── `DEF-RAT-7991`, 2026-09-29 — `refusal_sentence` IS NOT SCREEN TEXT ──
    #: Nine of the chain's raise sites interpolate a database uuid into it, and
    #: `billRunShared.tsx` printed it RAW on the bill-run screen. B14 rule 31.
    #: These two are rating's own clerk sentence, carried whole and unedited in
    #: exactly the way `refusal_sentence` is: `refusal_message_key` resolves in
    #: the clerk's own catalogue and `refusal_clerk_detail` is its id-free
    #: English mirror. Both are None where the chain states none, and the
    #: screen then shows nothing rather than the engineer's sentence.
    refusal_message_key: str | None = None
    refusal_clerk_detail: str | None = None
    refusal_message_params: dict | None = None
    #: Which fact the adapter could not assemble, when `status` is
    #: `not_attempted`. One of the `MISSING_*` constants above.
    blocked_reason: str | None = None
    blocked_detail: str | None = None

    @property
    def disagreed(self) -> bool:
        return self.status in (STATUS_DISAGREED, STATUS_CHAIN_REFUSED)


# ══════════════════════════════════════════════════════════════════════════
# Late binding — billing may not import rating or metering at module scope
# ══════════════════════════════════════════════════════════════════════════


def _seam(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while its lane has not landed."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _rating() -> tuple[Any, Any] | tuple[None, None]:
    """`resolution` and `resolution_catalogue`, or a pair of Nones."""
    try:
        return (
            import_module("apps.rating.resolution"),
            import_module("apps.rating.resolution_catalogue"),
        )
    except ImportError:  # pragma: no cover - defensive
        return (None, None)


def _refusal_base() -> type[BaseException] | None:
    """Rating's `ResolutionError`, resolved by name like its callables.

    Only the chain's OWN refusals are caught. An `AttributeError` inside
    `resolve()` is a bug in the chain and must NOT be reported to a clerk as a
    disagreement — the same distinction `rating_seam._refusal_types` draws.
    """
    resolution, _ = _rating()
    if resolution is None:  # pragma: no cover - defensive
        return None
    base = getattr(resolution, "ResolutionError", None)
    return base if isinstance(base, type) and issubclass(base, BaseException) else None


# ══════════════════════════════════════════════════════════════════════════
# STEP 1 · THE ADAPTER — gather's facts, in the chain's shapes
# ══════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ChainInputs:
    """Everything `resolution.resolve()` needs, or the reason it cannot run.

    `blocked_reason` is set when a REQUIRED fact is absent. The adapter never
    fills one in: an absent fact is the finding.
    """

    account: Any = None
    premises: Any = None
    meters: tuple[Any, ...] = ()
    asset_counts: tuple[Any, ...] = ()
    quantities: dict[str, Decimal | None] | None = None
    unmetered_services: tuple[str, ...] = ()
    #: The connection sizes this account's meters actually are, de-duplicated.
    #:
    #: ⚠ **THIS NO LONGER REACHES `build_catalogue`, AND THAT IS BR-RAT-120**
    #: (PO 2026-08-28, verbatim: *"we need to charge account based on connection
    #: size they have"*). It used to be handed to the catalogue as the sizes the
    #: schedule serves, which made R3's *"this size is not served"* refusal
    #: unreachable: the size R3 looked up was by construction one the catalogue
    #: had just been told to serve, so a 3-inch connection resolved the 5/8
    #: rate — **$8.00 both ways on the same tenant and the same plan**
    #: (`DEF-1810`). The sizes a schedule serves are now read from the schedule.
    #:
    #: It is KEPT because it is still the ACCOUNT's fact and the shadow report
    #: needs it: these are the sizes carried on `MeterFacts`, which is what R3
    #: looks UP. Reporting what was asked for is not the same as deciding what
    #: is served.
    served_sizes: tuple[str, ...] = ()
    plan_id: Any = None
    blocked_reason: str | None = None
    blocked_detail: str | None = None
    #: WHICH service the missing fact belongs to (`DEF-BIL-8218`) — so the bulk
    #: run's Check can offer the fix on the row (a connection size is set on
    #: THAT service's meters). None where the fact is the account's.
    blocked_service: str | None = None


def _register_difference(reading: ServiceReading) -> Decimal | None:
    """R3b's input: `current − prior`, PRE-multiplier.

    ⚠ **NOT `reading.consumption`.** That figure is metering's stored
    `(current − prior) × multiplier` and handing it to `billable_quantity`
    applies the multiplier a second time (see the module docstring). This is the
    single most dangerous line in the file and it is one subtraction long.

    None when either register is absent — a service with no read has no billable
    quantity, and a zero would state that the meter WAS read and showed nothing
    (`contracts.ServiceReading` makes exactly this distinction).
    """
    if reading.prior_read is None or reading.current_read is None:
        return None
    return Decimal(str(reading.current_read)) - Decimal(str(reading.prior_read))


def _unmetered_from(readings: tuple[ServiceReading, ...]) -> tuple[str, ...]:
    """BR-RAT-081's declaration, as it already reaches billing.

    `build_catalogue` says `unmetered_services` is the CALLER's to supply
    because the declaration lives on `tenancy.TenantService.metered` and rating
    may not query tenancy's tables (B1). Billing may not either — but it does
    not have to: metering already read the declaration and published the result
    as `absent_reason == "service_not_metered"` on the reading row (DEF-161).

    So this derives the declaration from data the live path ALREADY carries,
    which is the mapping-not-a-data-job property the whole shadow rests on.
    """
    not_metered = _metering_constant("READ_ABSENT_SERVICE_NOT_METERED")
    if not_metered is None:  # pragma: no cover - defensive
        return ()
    # ⚠ `DEF-BIL-8851` — AND THE SAME DECLARATION WHEN NOBODY CAN COUNT.
    # Metering REWRITES `service_not_metered` to `asset_count_unavailable` when
    # the count cannot be read (`_stamp_asset_count`): it is still a counted
    # service, never a register. Left out of this tuple, the row fell through to
    # the multiplier guard below and a cart was stopped as *"the meter states no
    # multiplier — Hold, or Bill with multiplier 1"*, offering a clerk an answer
    # that bills a counted service with no count. Included, it reaches the
    # asset-count loop, which stops it as what it is (`MISSING_ASSET_COUNT`).
    count_unavailable = _metering_constant("READ_ABSENT_ASSET_COUNT_UNAVAILABLE")
    reasons = {not_metered} | ({count_unavailable} if count_unavailable else set())
    return tuple(
        reading.service_code
        for reading in readings
        if reading.absent_reason in reasons
    )


def _has_no_meter_at_all(reading: Any) -> bool:
    """Does metering say this service point holds NO ASSET? (`DEF-2875`)

    ⚠ **THREE `absent_reason`s AND ONLY ONE OF THEM IS THIS ONE.** Metering
    already tells the difference and publishes it on the reading row; nothing in
    this adapter read it until 2026-09-01:

      * `no_meter`             — the service point holds no asset. There is no
                                 register, so there is no factor and no register
                                 difference. **This one.**
      * `service_not_metered`  — DECLARED unmetered (BR-RAT-081). Handled well
                                 above by `_unmetered_from`, which routes it to
                                 BR-RAT-090's asset count instead.
      * `no_read`              — there IS a meter and nobody read it. A data gap
                                 a human fixes, and it must go on blocking: the
                                 factor is knowable and absent, which is exactly
                                 what `MeterMultiplierUnstated` exists for.

    Returns False for anything it cannot establish — an unpublished constant, a
    row without the field — so this helper can only ever make the adapter block
    MORE, never less. Same safe direction as `_service_is_ruled_sizeless`, and
    for the same reason: the account is reported unevaluable rather than priced
    on an assumption.
    """
    no_meter = _metering_constant("READ_ABSENT_NO_METER")
    if no_meter is None:  # pragma: no cover - defensive
        return False
    return getattr(reading, "absent_reason", None) == no_meter


def _metering_constant(name: str) -> Any:
    try:
        return getattr(import_module("apps.metering.selectors"), name, None)
    except ImportError:  # pragma: no cover - defensive
        return None


def _base_is_one_price_for_all_sizes(service: str) -> bool:
    """Rating's answer to *is this service's base one price for every size?*
    (`DEF-RAT-8822`), asked through the same catalogue module R3's facts are
    built from, so the adapter and R3 cannot disagree. False when rating has
    not published it — which holds the account exactly as before."""
    _, catalogue = _rating()
    ask = getattr(catalogue, "base_is_one_price_for_all_sizes", None) if catalogue else None
    return bool(ask(service)) if callable(ask) else False


def _service_is_ruled_sizeless(service: str) -> bool:
    """Is a BLANK connection size a FACT about this service rather than a gap?

    Two services reach R3 with no size and are right to, by different routes:

        ruled to have none    sewer (`BR-RAT-015`) — a share of the water usage
                              charge, reading no register of its own.
        priced by capacity    solar, battery, storm water, broadband — nothing
                              meters a solar panel's "connection size", and the
                              price does not vary by band anyway.

    **False for every other answer**, and deliberately so: a service with a
    ratified rate axis whose size nobody recorded is `DEF-514`, a data gap a
    human fixes on a screen, and a service whose bands were never put to the PO
    raises inside `service_size_classes`. The adapter must not flatten those —
    a guessed size selects a tier ladder, which is money.

    ⚠ **THE SECOND ROUTE IS `DEF-3098` AND THIS FUNCTION HAD THE DEFECT TOO
    (2026-09-02).** It read `size_classes_for_service(service) == ()`, which
    asks *"does this service have size rows"* — a proxy for *"is it banded"*
    that was sound only while banded services were the only ones with rows.
    `CR-062` gave four capacity services a CATALOGUE OF INSTALLABLE EQUIPMENT,
    so from that commit this answered False for every solar and battery account
    and the adapter reported each of them unevaluable with
    `MISSING_CONNECTION_SIZE`. It is the shape of `DEF-2851`'s sewer outage —
    116 of 163 accounts NOT ATTEMPTED — one service family further on.
    `resolution.service_prices_by_size_class` is the question asked properly and
    its docstring is the authority.

    Any refusal or unknown service still answers False, so this helper can only
    ever make the adapter block MORE, never less. That is the safe direction:
    the account is reported as unevaluable rather than priced on an assumption.
    """
    try:
        resolution, _ = _rating()
        if resolution is None:  # pragma: no cover - defensive
            return False
        return not resolution.service_prices_by_size_class(service)
    except Exception:
        return False


#: `unread_factor` — what the adapter does about a service whose meter states
#: NO multiplier and whose usage this bill prices (changes row 44, PO
#: 2026-09-30: *"no multiplier → Hold (default) / Bill with multiplier 1"*):
#:   REFUSE       always refuse (`MISSING_MULTIPLIER`). The default, and the
#:                shadow's: a factor is never 1 by default (BR-MET-056).
#:   NOT_NEEDED   refuse only where there IS a register difference to scale.
#:                With none (a meter never read), nothing on this bill is
#:                priced from a quantity on either path — the chain's own
#:                `billable_quantity` answers None for None (`DEF-2875`), and
#:                the ruled path substitutes no quantity — so the refusal
#:                guarded no figure. The live path's caller outside a Check.
#: A clerk's recorded *Bill with multiplier 1* (`multiplier_one`) puts a 1 in
#: under either policy, and it is the ONLY thing that ever does.
UNREAD_FACTOR_REFUSE = "refuse"
UNREAD_FACTOR_NOT_NEEDED = "not_needed"


def adapt(
    data: AccountBillingData,
    *,
    account: Any,
    unread_factor: str = UNREAD_FACTOR_REFUSE,
    multiplier_one: Any = None,
) -> ChainInputs:
    """`AccountBillingData` -> the chain's frozen facts. THE only new code.

    The decision log's step 1 in one function: *"map `gather_account`'s facts
    into the chain's dataclasses. The only genuinely new code."*

    ⚠ **EVERY MISSING FACT STOPS THE ADAPTER AND NAMES ITSELF.** There is no
    default in this function. The four `MISSING_*` reasons are the four facts
    the chain requires that the live path does not carry today, and each one is
    a filed defect rather than a value to choose.

    `multiplier_one(service) -> bool` (changes row 44, 2026-10-01): True only
    where a CLERK recorded *Bill with multiplier 1* for this account and
    service on the bulk run's Check. `unread_factor`: see the constants above.
    Both default to the behaviour this function always had.
    """
    resolution, _ = _rating()
    if resolution is None:  # pragma: no cover - defensive
        return ChainInputs(blocked_reason="rating_resolution_not_published")

    if data.rate_plan_id is None:
        return ChainInputs(
            blocked_reason=MISSING_PLAN,
            blocked_detail=(
                f"account {data.account_no} carries no rate plan, so R1 has nothing to "
                "resolve. The live path refuses this too (`GATHER_NO_PLAN`); the two "
                "agree that it is unbillable and this is not a disagreement."
            ),
        )

    # ── 2026-09-30 · ONLY THE SERVICES THIS BILL PRICES ───────────────────
    # PO rulings of that date: a service with no asset is NOT IN SERVICE (no
    # tariff, no line), and a `%`-of-service (sewer) has NO service point and
    # follows its basis. The live path decides both in `gather` and hands the
    # chain `data.tariffs`; the readings still carry metering's row for every
    # POINT, so an adapter reading them raw would demand a size and a factor
    # for a meter the ruling says is not there, and a sewer with no point would
    # reach R3 with no meter at all. Measured on PostgreSQL 16 before this
    # clause: an account whose electric point had its meter detached refused
    # with *"service 'electric' has no connection size RECORDED"*, and one whose
    # sewer point was removed refused with *"R3: the plan covers 'sewer' and the
    # unit has no meter for it"* — both bills the live path priced.
    #
    # So: readings for a service the bill does not price are skipped, a second
    # meter of one service (two meters = two lines, excluded from substitution
    # in `resolution_switch._substituted`) contributes no second fact, and a
    # `%`-of-service with no reading is given the row metering published for
    # sewer before the ruling — `no_meter` — which `_has_no_meter_at_all` and
    # `_service_is_ruled_sizeless` already handle. `billed` empty (a hand-built
    # fixture with no tariffs) narrows nothing.
    billed = {getattr(config, "service", "") for config in data.tariffs}
    readings = [r for r in data.readings if not billed or r.service_code in billed]
    no_meter = _metering_constant("READ_ABSENT_NO_METER")
    read_codes = {r.service_code for r in readings}
    for config in data.tariffs:
        service = getattr(config, "service", "")
        if (
            getattr(config, "model", None) == "percent_of_service"
            and service not in read_codes
            and no_meter is not None
        ):
            readings.append(ServiceReading(service_code=service, absent_reason=no_meter))
            read_codes.add(service)
    unmetered = _unmetered_from(tuple(readings))

    # ── R3 · the connection size, per service ────────────────────────────
    # `MeterFacts.connection_size` is typed `str` and `resolve_size_row` refuses
    # on a size the schedule does not carry. Reported, never invented — a
    # guessed size prices a bill.
    #
    # ⚠ **CORRECTED 2026-09-01 (`DEF-2414`, hard-won law 1). THIS PARAGRAPH SAID
    # THERE WAS NO SIZE STORED ANYWHERE IN THE PRODUCT AND HAD NOT BEEN TRUE FOR
    # FIVE DAYS.** `DEF-514` closed on 2026-08-27: `assets.Asset.size_class`
    # exists with its migration, `assets.selectors.assets_on_unit` publishes it,
    # `metering.selectors.connection_size_for` answers from it, and `DEF-1900`
    # gave it both human doors — a column in the meters import (`BR-MET-530`)
    # and a control on the asset screens (`BR-AST-530`). `connection_size_for`'s
    # own docstring has said so since that commit: a `None` here is *"a data
    # state a human can fix rather than a product that cannot hold the fact"*.
    # **The rotted sentence cost a whole investigation its first day** — it sent
    # the `DEF-2414` trace looking for a missing COLUMN when what was missing
    # was a seeded VALUE and, underneath that, `BR-RAT-081`'s declaration.
    size_for = _seam("metering", "connection_size_for")
    # ── `DEF-BIL-8470` · WHOSE CONNECTION, ON A MASTER ACCOUNT ───────────────
    # A master account carries NO unit of its own (customers 0036, PO
    # 2026-08-31), so asking the anchor `account.unit_id` asked `None` and the
    # ruled path refused every master bill *"no connection size recorded"* —
    # while the 1408 Elm meters record `E-1P-100` and `W-58` on their own
    # common-area units. The live path resolves each service against the
    # COVERED UNIT that serves it (`gather._coverage_facts` → `serving_units`);
    # the adapter now asks the same function the same question, so both paths
    # read one connection per service. An ordinary account answers `{}` without
    # a query and every service still resolves to its own unit.
    serving = _serving_units(account, data)
    # 🔒 `DEF-CUS-9050` (PO 2026-10-02) — a master with NO common area is priced
    # from the empty homes alone; the live path borrows the first of them as its
    # anchor (`gather._gather_account`, `borrowed_anchor`), and the ruled path
    # reads the same unit: the first base-only tariff's `covers_unit_id`.
    anchor = _anchor_unit(account) or next(
        (
            config.covers_unit_id
            for config in getattr(data, "tariffs", ()) or ()
            if getattr(config, "covers_unit_id", None)
        ),
        None,
    )

    def unit_for(service: str) -> Any:
        return serving.get(service) or anchor

    # `DEF-BIL-8247` — the services whose USAGE this bill does not price.
    # `DEF-BIL-8724` — NOT an empty unit's base on an owner's bill
    # (`covers_unit_id`): that tariff sits BESIDE a common area's full tariff
    # for the same service, whose usage IS priced, and reading it as "this
    # service is base-only" dropped the hallway's quantity and relaxed the
    # multiplier guard for the hallway's meter.
    base_only_services = {
        getattr(config, "service", "")
        for config in data.tariffs
        if getattr(config, "base_only", False) and not getattr(config, "covers_unit_id", None)
    }
    whole_account_base_only = getattr(data, "behavior_class", None) == "billable_base_only"
    meters: list[Any] = []
    sizes: list[str] = []
    quantities: dict[str, Decimal | None] = {}
    for reading in readings:
        service = reading.service_code
        if service in unmetered:
            continue
        if service in quantities:
            continue  # 2026-09-30 — a split service's second meter; see above
        quantities[service] = _register_difference(reading)
        size = size_for(unit_for(service), service) if size_for else None
        size = (str(size).strip() or None) if size else None
        if size is None and _service_is_ruled_sizeless(service):
            # ── RULED TO HAVE NO SIZE, WHICH IS NOT A MISSING SIZE (DEF-2851) ──
            # `BR-RAT-015` prices SEWER as a share of the water usage charge, so
            # a sewer connection carries no size class and never will;
            # `tenancy.service_size_classes` returns an EMPTY TUPLE for it and
            # RAISES for a service whose bands were never ruled, keeping the two
            # apart on purpose. This branch asks that register rather than
            # treating every `None` as the same fact.
            #
            # **What it cost to not ask.** Measured 2026-08-31 over three
            # utilities: 116 of 163 accounts NOT ATTEMPTED, every one of them
            # `service 'sewer' has no connection size`. The shadow could not
            # evaluate a single account of any utility that bills sewer, and the
            # `47 agree / 0 disagree` the cutover ruling was taken on came from
            # the one seeded utility that bills water only — the population
            # where this case cannot arise.
            size = resolution.NO_SIZE
        elif size is None and _base_is_one_price_for_all_sizes(service):
            # ── `DEF-RAT-8822` · AN UNSIZED METER ON AN *ALL SIZES* BASE IS
            # BILLED (PO 2026-10-01, option A, verbatim: *"Hold back only where
            # the price depends on the size. If the base is one price for all
            # sizes, the bill goes out at $12.41 with the warning"*). The size
            # is still NOT RECORDED — it is handed to R3 as the blank it is,
            # R3 lets it through only on the same question
            # (`ScheduleVersion.base_priced_by_size`), no minimum applies, and
            # the Check names the meter. A size-priced base falls to the
            # refusal below, word for word as before (`BR-RAT-120`, narrowed).
            size = resolution.NO_SIZE
        elif size is None:
            return ChainInputs(
                blocked_service=service,
                blocked_reason=MISSING_CONNECTION_SIZE,
                blocked_detail=(
                    f"service {service!r} has no connection size RECORDED on this "
                    "connection. R3 cannot be resolved and a size may not be guessed — "
                    "`resolve_size_row` refuses a size the schedule does not price "
                    "rather than charging $0.00 for it. This is a DATA state a human "
                    "can fix, not a product that cannot hold the fact (DEF-514 closed "
                    "2026-08-27): record it on the asset standing on this connection, "
                    "on the meters import or the asset screen. If the service is "
                    "priced without a register at all — trash by cart count, say — the "
                    "fix is the other one: declare it unmetered on Settings > Services "
                    "(BR-RAT-081), and no size is asked for."
                ),
            )
        usage_billed = not whole_account_base_only and service not in base_only_services
        multiplier = _multiplier_for(account, service, unit_id=unit_for(service))
        if multiplier is None and getattr(reading, "provisional", False):
            # ── `DEF-CUS-5931` · A KEYED READ HAS NO COMMITTED HEAD TO ASK ───
            # `_multiplier_for` resolves the factor through
            # `metering.billing_multiplier_for`, which answers from the latest
            # BILLABLE HEAD — and the move-out wizard's step-2 capture has none
            # by design (p111: the reads commit with the close). The factor is
            # not unknown, though: metering put it on the row it overlaid,
            # straight off the meter, which is the same `asset.multiplier` the
            # commit itself stamps. So the row answers where the seam cannot.
            #
            # ⚠ **THE ROW IS PREFERRED HERE AND ONLY HERE, DELIBERATELY.**
            # `billing_reads_for_unit`'s own docstring says the row's key is
            # the authoritative answer *"and this function is the one for a
            # caller that has no row in hand"* — which this caller is not — so
            # preferring it on EVERY row is the better rule. It is not taken in
            # this commit because it would move the factor on live bills
            # wherever the seam's latest head differs from the period's read,
            # which is money. Filed as `DEF-CUS-5935`.
            multiplier = _dec(getattr(reading, "multiplier", None))
        # ── `DEF-BIL-8247` · NO USAGE BILLED, SO NO FACTOR IS NEEDED ─────
        # A standing-charges-only account (BR-CUS-055 vacation hold,
        # `billable_base_only`) and a service a clerk billed *without its
        # reading* (PO 2026-09-30, fixed-charge case 1 — `TariffConfig.
        # base_only`) price NO usage on either path. With no reading this
        # period, metering has no head to answer a multiplier from, and the
        # refusal below blocked the account for the factor of a quantity
        # nobody was going to bill. The factor's danger — a ×10 register
        # billed at a tenth — needs a usage line to exist, so the guard is
        # kept exactly where it bites: any service whose usage IS billed. The
        # quantity is dropped too, so the chain cannot price a usage line the
        # live path does not.
        if not usage_billed:
            quantities[service] = None
        if (
            multiplier is None
            and not _has_no_meter_at_all(reading)
            and usage_billed
            and multiplier_one is not None
            and multiplier_one(service)
        ):
            # ── changes row 44 · THE CLERK CHOSE ×1 (PO 2026-09-30) ──────────
            # *"no multiplier → Hold (default) / Bill with multiplier 1"*. The 1
            # is a recorded answer with a name and a time on it
            # (`bill_run_decisions`), never a default.
            multiplier = Decimal("1")
        if (
            multiplier is None
            and not _has_no_meter_at_all(reading)
            and usage_billed
            and unread_factor == UNREAD_FACTOR_NOT_NEEDED
            and quantities.get(service) is None
        ):
            # No register difference: nothing to scale, nothing to understate.
            # `None` travels, as for a meterless service below (`DEF-2875`).
            usage_billed = False
        if multiplier is None and not _has_no_meter_at_all(reading) and usage_billed:
            return ChainInputs(
                blocked_service=service,
                blocked_reason=MISSING_MULTIPLIER,
                blocked_detail=(
                    f"service {service!r}: billing's read seam publishes no meter "
                    "multiplier, and BR-MET-056 stores the factor USED. An absent "
                    "factor is NOT 1 (`resolution.MeterMultiplierUnstated`): a ×10 "
                    "register whose multiplier nobody recorded bills a tenth of the "
                    "customer's consumption on a document that looks entirely normal."
                ),
            )
        # ── NO METER AT ALL, WHICH IS NOT A MISSING MULTIPLIER (`DEF-2875`) ──
        # `DEF-2851` taught the branch above this one to ask the ratified size
        # register before demanding a size, and stopped at the size. THIS
        # statement demanded a multiplier from the very same service three lines
        # later, and metering answers None for the very same reason: sewer has
        # no meter (`BR-RAT-015` — it is a share of the water usage charge). So
        # the 116 accounts DEF-2851 unblocked stayed blocked and merely changed
        # their sentence, which read as a fresh finding.
        #
        # **The fact is metering's and it is already published**, on the same
        # reading row every other fact here comes from: `absent_reason ==
        # 'no_meter'` means this service point holds no asset, as against
        # `'service_not_metered'` (declared unmetered, handled by
        # `_unmetered_from` above) and `'no_read'` (a meter that was not read,
        # which is a data gap and still blocks).
        #
        # `None` travels rather than `Decimal("1")`, deliberately and for the
        # reason `_multiplier_for`'s own docstring gives: a defaulted 1 makes
        # R3b report parity by construction. The chain decides — and it decides
        # correctly, because a service with no meter has no register difference
        # to scale (`resolution.billable_quantity`).
        sizes.append(size)
        meters.append(
            resolution.MeterFacts(
                service=service, connection_size=size, multiplier=multiplier
            )
        )

    # ── R3b · the UNMETERED half (BR-RAT-090) ────────────────────────────
    # The count is OBSERVED, never typed. `count=None` and `count=0` are
    # different facts and only one of them bills, so an unpublished seam blocks
    # rather than counting zero carts for a unit that has three.
    counts: list[Any] = []
    #: DEF-1813 — the count now crosses billing's read seam on the reading row
    #: itself (`ServiceReading.asset_count`, published by
    #: `metering.billing_reads_for_unit` at the SERVICE-PERIOD END DATE per
    #: BR-RAT-090). Preferring the row over a fresh seam call is the same
    #: choice `_register_difference` makes and the same one BR-MET-500 records
    #: for the multiplier: **the row cannot name a different unit or a
    #: different date from the one being priced**, and reading it costs no
    #: query — which is the mapping-not-a-data-job property this whole shadow
    #: rests on. The by-name seam stays as the fallback for a `ServiceReading`
    #: built by a caller that predates the key.
    counted_on_row = {
        reading.service_code: reading.asset_count
        for reading in readings
        if getattr(reading, "asset_count", None) is not None
    }
    count_for = _seam("metering", "billable_asset_count")
    for service in unmetered:
        count = counted_on_row.get(service)
        if count is None and count_for is not None:
            count = count_for(unit_for(service), service, data.period_end)
        if count is None:
            return ChainInputs(
                blocked_service=service,
                blocked_reason=MISSING_ASSET_COUNT,
                blocked_detail=(
                    f"service {service!r} is declared UNMETERED (BR-RAT-081) and no "
                    "asset count could be determined, so BR-RAT-090's quantity cannot "
                    "be resolved. An absent count is 'nobody looked', which is not the "
                    "same fact as 'this unit has none' — and only the second one bills. "
                    "There is no fallback and no `or 0` here: a defaulted zero would "
                    "make the chain and the live path AGREE by construction on every "
                    "unmetered service, which reads as the best possible news while "
                    "measuring nothing."
                ),
            )
        counts.append(resolution.AssetCountFacts(service=service, count=int(count)))

    return ChainInputs(
        account=resolution.AccountFacts(
            account_no=data.account_no,
            # DEF-BIL-8470 — the unit gather priced from (a master: its first
            # covered unit), never the literal "None" of a master's own unit.
            unit_id=str(anchor or ""),
            # The PLATFORM code, never a tenant's display label — r10's State
            # Utility Tax is "Comm, Industrial only · Residential exempt" and
            # that rule is written against the code.
            customer_class=getattr(getattr(account, "account_type", None), "code", None),
            enrolments=tuple(
                code for code in (getattr(rule, "code", None) for rule in data.discounts) if code
            ),
            # ⚠ DEF-2824 — WHOSE bill this is, so R7 can find an exemption
            # CERTIFICATE (DEF-383). It is the ONE tax fact whose absence
            # OVER-charges: the three restrictions fail closed, an exemption
            # fails open, so a chain that could not name the account charged a
            # customer holding a live certificate. Taken from the gathered row
            # rather than re-queried, like every other fact in this adapter.
            account_id=str(data.account_id) if data.account_id is not None else None,
        ),
        premises=_premises_facts(account, unit_id=anchor),
        meters=tuple(meters),
        asset_counts=tuple(counts),
        quantities=quantities,
        unmetered_services=unmetered,
        served_sizes=tuple(dict.fromkeys(sizes)),
        plan_id=data.rate_plan_id,
    )


def _multiplier_for(account: Any, service: str, *, unit_id: Any = None) -> Decimal | None:
    """BR-MET-056's stored factor, or None while metering publishes none.

    `unit_id` is the unit that SERVES this service (`DEF-BIL-8470` — a master
    account's service is served by a covered unit, never by its own, which it
    does not have); None falls back to the account's own unit.

    ⚠ **NEVER `Decimal("1")` ON THE None BRANCH.** See the module docstring: a
    defaulted 1 makes R3b's comparison report parity by construction.
    """
    seam = _seam("metering", "billing_multiplier_for")
    if seam is None:
        return None
    value = seam(unit_id if unit_id is not None else getattr(account, "unit_id", None), service)
    return None if value is None else Decimal(str(value))


def _serving_units(account: Any, data: AccountBillingData) -> dict[str, str]:
    """`{service_code: unit_id}` — the covered unit that serves each service,
    by the live path's OWN function (`gather._coverage_facts`), so the two
    paths cannot map a service to different connections (`DEF-BIL-8470`).

    `{}` for an ordinary account (one covered unit — gather asks metering
    nothing either). A coverage the live path REFUSES (OQ-334 two units on one
    service, OQ-335 two plans) answers `{}` too: the live path has already
    broken that account by name, and the adapter falls back to the unit it
    always asked rather than inventing a second answer."""
    from apps.billing import gather

    try:
        covered = gather.covered_units(account)
        serving, _labels = gather._coverage_facts(
            covered, plan_id=data.rate_plan_id, account_no=data.account_no
        )
    except gather.GatherProblem:
        return {}
    return {str(service): str(unit) for service, unit in (serving or {}).items()}


def _anchor_unit(account: Any) -> Any:
    """The unit the live path prices this account from (`DEF-BIL-8470`):
    its own, or — for a MASTER account, which names none — the first unit it
    covers, exactly as `gather._gather_account` chooses it (CR-056 W1,
    BR-CUS-1010). None when it has neither; the chain then refuses by name."""
    own = getattr(account, "unit_id", None)
    if own is not None:
        return own
    from apps.billing import gather

    try:
        covered = gather.covered_units(account)
    except gather.GatherProblem:
        return None
    return covered[0] if covered else None


def _premises_facts(account: Any, *, unit_id: Any = None) -> Any:
    """R5's jurisdiction flag AND R7's tax geography, off ONE premises read.

    ⚠ **THIS USED TO BE `_inside_city_limits` AND RETURNED THE FLAG ALONE
    (`DEF-2824`, 2026-08-31).** R5 asks the premises one question — is this
    inside the city — and that is all this function ever carried. R7 asks it a
    different one: a tax states its geography over five mechanisms, and
    `rating.selectors.premises_in_scope` answers two of them off keys it reads
    BY NAME — `inside_city_limits`, then `city` and `state` as the recorded
    geography it falls back to where no boundary flag was ever drawn. Passing
    only the flag meant a tax scoped by STATE, or by a city name on a premises
    with no flag, was dropped from every ruled bill.

    **ONE read for both, deliberately.** `gather._premises_geography` makes the
    same choice and states the reason: *"billing reads a premises in exactly one
    place, and a second reader is how two answers to one question start."* This
    is the shadow's copy of that read, over the same objects, and it must not
    grow into a second one.

    None on any field is a real answer and every consumer treats it as one:
    `money_factor` refuses with `JurisdictionUnstated` only when the plan
    actually SURCHARGES, so an unrecorded flag costs nothing on a plan that does
    not; and a stated scope this premises cannot answer means the tax reaches
    nobody rather than everybody (DEF-273's direction).
    """
    resolution, _ = _rating()
    if resolution is None:  # pragma: no cover - defensive
        return None
    seam = _seam("metering", "unit_row")
    if seam is None:  # pragma: no cover - defensive
        return resolution.PremisesFacts()
    unit = seam(unit_id if unit_id is not None else getattr(account, "unit_id", None))
    premises = getattr(unit, "premises", None)
    return resolution.PremisesFacts(
        inside_city_limits=getattr(premises, "inside_city_limits", None),
        city=getattr(premises, "city", None),
        state=getattr(premises, "state", None),
    )


# ══════════════════════════════════════════════════════════════════════════
# STEP 2 · THE SHADOW RUN — both paths, one account, every difference named
# ══════════════════════════════════════════════════════════════════════════


def shadow_account(data: AccountBillingData, *, account: Any, service_date: date) -> ShadowOutcome:
    """Run the ruled path beside the live one. Report; never price.

    `data` is the LIVE path's own output — this function does not re-gather and
    does not re-query for anything gather already holds, so the two sides are
    guaranteed to be looking at the same account at the same instant. A shadow
    that re-read the database could differ from the live path for no reason but
    the clock.
    """
    inputs = adapt(data, account=account)
    if inputs.blocked_reason is not None:
        return ShadowOutcome(
            account_id=data.account_id,
            account_no=data.account_no,
            status=STATUS_NOT_ATTEMPTED,
            blocked_reason=inputs.blocked_reason,
            blocked_detail=inputs.blocked_detail,
        )

    resolution, catalogue_module = _rating()
    base = _refusal_base()
    if base is None:  # pragma: no cover - defensive
        # An empty `except` is a legal one that catches nothing; while rating's
        # error base is absent its refusals propagate UNWRAPPED rather than
        # being swallowed by a bare `except Exception` — the same reasoning
        # `rating_seam._refusal_types` records.
        base = ()  # type: ignore[assignment]
    # ⚠ **`served_sizes` IS DELIBERATELY NOT PASSED (BR-RAT-120).** The keyword
    # was removed from `build_catalogue` on 2026-08-28, so this is a `TypeError`
    # if anyone puts it back rather than a quietly widened catalogue. The sizes
    # this account's meters are still travel on `inputs.meters`, where R3 LOOKS
    # THEM UP; what a schedule SERVES is the schedule's to say.
    # ⚠ **`account` AND `premises` ARE PASSED AND ARE REQUIRED (`DEF-2824`).**
    # They reach exactly one thing — R7's candidate query — and without them
    # `rating.selectors.plan_tax_rules` fails closed on every restriction a tax
    # states and returns only the UNRESTRICTED taxes. That dropped `Texas State`
    # (6.25%, commercial and industrial only) from both commercial accounts of
    # this repo's own 47-account measurement while the live path charged it.
    catalogue = catalogue_module.build_catalogue(
        plan_id=inputs.plan_id,
        service_date=service_date,
        account=inputs.account,
        premises=inputs.premises,
        unmetered_services=inputs.unmetered_services,
    )
    try:
        resolved = resolution.resolve(
            catalogue=catalogue,
            account=inputs.account,
            premises=inputs.premises,
            meters=inputs.meters,
            quantities=inputs.quantities,
            asset_counts=inputs.asset_counts,
            service_date=service_date,
        )
    except base as refusal:  # type: ignore[misc]
        # ⚠ THE HIGHEST-VALUE ROW IN THE EXERCISE. The chain refused where the
        # live path produced a number — a bill that would have gone out on a
        # guess. The chain's own sentence is carried WHOLE and unedited.
        name = type(refusal).__name__
        # `DEF-RAT-7991` — rating's OWN reader, for the reason `refusal_steps()`
        # is published one file over: a hand-written copy here cannot see a
        # field added there (DEF-2341).
        clerk = resolution.clerk_refusal(refusal) or {}
        return ShadowOutcome(
            account_id=data.account_id,
            account_no=data.account_no,
            status=STATUS_CHAIN_REFUSED,
            refusal_step=REFUSAL_STEPS.get(name),
            refusal_type=name,
            refusal_sentence=str(refusal),
            refusal_message_key=clerk.get("message_key"),
            refusal_clerk_detail=clerk.get("detail"),
            refusal_message_params=clerk.get("message_params") or None,
        )

    divergences = compare(data, resolved)
    return ShadowOutcome(
        account_id=data.account_id,
        account_no=data.account_no,
        status=STATUS_DISAGREED if divergences else STATUS_AGREED,
        divergences=tuple(divergences),
    )


def compare(data: AccountBillingData, resolved: Any) -> list[Divergence]:
    """Every step, both figures. The function the whole exercise exists for.

    ⚠ **AN EMPTY COMPARISON IS A FAILURE, NOT A PASS.** A parity checker that
    compares nothing returns no divergences and reads as green — the single way
    this file could tell a comfortable lie. `tests/test_def_438_parity.py`
    very nearly shipped exactly that (a fixture wrote no `plan_services` row, so
    the per-service loop never ran once and PARITY was reported over zero
    services). It is asserted here, in the shared function, so that no future
    caller can be written without the guard.

    Inputs are compared, never totals: comparing totals would hide two errors
    that cancel.

    ── DEF-2798 · THE FOUR STEPS THIS FUNCTION COMPARED NOTHING AT ─────────────

    ── DEF-2823 · R3 AND R4 ARE TWO COMPARISONS NOW, NOT ONE FUSED ONE ────────

    The base used to be compared as a single `R3/R4` figure, because
    `ServiceResolution` carries one `base_charge` and `base_source` merely named
    which object supplied it. A joint agreement satisfies the cutover's rule —
    *"a step switches only when its own class is at zero"* — for NEITHER half,
    so **R3 and R4 both read `47 could not evaluate` on a run where the base
    agreed on all 47 accounts.**

    `BR-RAT-088` says where the seam is: *"R3's refusal semantics are unchanged
    — a size absent from the schedule still means not served — but the base
    itself now resolves through R4."* **R3 chooses the SIZE; R4 resolves the
    AMOUNT for it**, and each is compared against the live path's own answer to
    that same question. `TariffConfig.size_class` was added for the R3 half —
    the live path already resolved a size and simply did not carry it.

    ⚠ **AND THE R3 HALF OF THAT SENTENCE WAS WRONG (`DEF-2878`, 2026-09-01).**
    *"The live path's own answer to that same question"* was the live path
    handing back the answer `metering.connection_size_for` gave it, and the
    chain handing back the answer this adapter gave IT. **R3 is asserted as an
    INVARIANT below and is no longer compared at all**; only R4's half of the
    separation survives as a comparison, and it survives because its two sides
    really are two narrowings over one table. The four hops and the measurement
    that proved it are in the R3 block itself.

    Until 2026-08-31 this function put a figure beside the live path's at **R1**,
    **R2** and the fused **R3/R4** base — and at **nothing else**. R3b, R5, R6
    and R7 were never compared, so their `by_step` count was zero on every run
    that had ever been taken, and a zero nobody measured reads exactly like a
    zero that was earned. Under the cutover's own rule — *"one at a time, each
    only when its own class is at zero"* — those four could never qualify,
    because nothing could ever produce a non-zero. **Proved rather than argued:
    a thousandfold error was put on one account's live meter multiplier and NOT
    ONE COLUMN MOVED**, with the chain fully resolving.

    All four are compared now, off objects both paths ALREADY hold — no new
    query, no new fact, which is the mapping-not-a-data-job property this whole
    shadow rests on.

    ⚠ **R3b IS COMPARED ON THE QUANTITY AND NOT ON THE MULTIPLIER, AND
    `DEF-2798`'s OWN SUGGESTION TO USE `TariffConfig.multiplier` IS WRONG.**
    That field is a TRIP-WIRE, not the live path's meter multiplier:
    `apps/rating/pricing/stages/normalize.py` REFUSES BY NAME any tariff
    reaching the engine with a multiplier that is not 1 (*"which does NOT apply
    meter multipliers (PO ruling 2026-08-11)"*), and `gather` therefore sets
    none at all — *"consumption arrives here already post-multiplier"*. So
    comparing the chain's real meter multiplier against it would report a
    DISAGREEMENT on every meter that is not ×1 and agreement by construction on
    every meter that is, which is a false-disagreement generator wearing a
    comparison's coat.
    **The multiplier's whole effect is inside the quantity** — the chain
    multiplies the register difference by the factor metering's seam publishes,
    metering multiplied the same registers by the factor it stored — so the two
    quantities are two independent derivations of one number and a multiplier
    that differs makes them differ. **One blind spot, stated rather than
    discovered later: a register difference of ZERO hides a multiplier error,
    because nothing times anything is nothing.**

    ⚠ **R6 IS PARTLY CIRCULAR AND CAN ONLY EVER FIND ONE DIRECTION OF ERROR.**
    `adapt` builds `AccountFacts.enrolments` FROM `data.discounts` — the live
    path's own answer — so the chain can DROP a code the live path granted (the
    plan-binding gate disagreeing, BR-RAT-110) and can never ADD one. That is a
    real finding and a real refusal to overclaim: the row it produces is
    evidence about the catalogue's narrowing, not about which discounts an
    account should have.

    ⚠ **R7 HAS NO REFUSAL CLASS AT ALL, BY DESIGN, WHICH IS WHY COMPARING IT IS
    THE ONLY THING THAT CAN EVER EVALUATE IT.** `resolve_taxes`'s four
    conditions decide APPLICABILITY, and the outcome of a failed one is *no line
    at all*, never an error and never a zero-valued line (DEF-273). So R7 cannot
    refuse, and before this change it could not be compared either: it was
    invisible end to end. The two sides are genuinely independent — the live set
    is narrowed by `rating.selectors.plan_tax_rules` before a `TaxRule` is even
    built, the ruled set by `resolve_taxes` over the catalogue — so this row can
    and does disagree.
    """
    if not getattr(resolved, "services", ()):
        raise AssertionError(
            "the chain resolved ZERO services, so this comparison compared nothing. "
            "A shadow run that measures nothing reports parity — fix the inputs, "
            "never the assertion."
        )
    if not data.tariffs:
        raise AssertionError(
            "the live path resolved ZERO tariffs, so this comparison compared nothing."
        )

    found: list[Divergence] = []

    # ── R1 · WHICH PLAN VERSION PRICED THIS ACCOUNT (`DEF-2839`) ─────────
    # ⚠ **THE PLAN ID IS AN INPUT, SO COMPARING IT IS A CHECK THAT CANNOT
    # FAIL.** `adapt` hands `data.rate_plan_id` to `build_catalogue` and
    # `resolution_catalogue.plan_version_facts` filters `pk=plan_id` and then
    # stamps `plan_id=str(plan.id)` back onto the row it yields — both sides
    # are one value by construction. Until 2026-08-31 that WAS R1's comparison,
    # so its `47 agree` was 47 restatements of a single id, and `figures_differ`
    # was unreachable: across a clean run and a `--sabotage R1` run, 94 account
    # evaluations produced it NOT ONCE. The sabotage looked like it worked only
    # because it moved the row through the REFUSAL path.
    #
    # It is asserted as an INVARIANT rather than counted as agreement. If these
    # two ever differ, the shadow is comparing two different accounts and every
    # other figure in the run is meaningless — a louder thing than a pricing
    # divergence, and the posture this function already takes for a run that
    # compared nothing at all.
    if str(data.rate_plan_id) != str(resolved.plan.plan_id):
        raise AssertionError(
            "the chain resolved a DIFFERENT plan from the one the live path was "
            f"asked about (live {data.rate_plan_id}, ruled {resolved.plan.plan_id}). "
            "The adapter hands the chain the live plan id, so these cannot differ: "
            "the shadow's own plumbing is broken and no figure in this run means "
            "anything. Fix the inputs, never the assertion."
        )
    # **THE COMPARABLE HALF: the VERSION.** It never reaches the chain —
    # `ChainInputs` carries `plan_id` and nothing else about the plan — so
    # `plan_version_facts` re-reads `rate_plans.version` for itself while the
    # live path reads it through `rating.selectors.plan_ref`. Two derivations of
    # one answer, which is what a comparison needs.
    #
    # ⚠ **AND ITS LIMIT, STATED RATHER THAN LEFT TO BE DISCOVERED** — the same
    # posture R6 takes about its own circularity (R3 used to be named here too,
    # and `DEF-2878` found that STATING a circularity is not the same as
    # measuring it: R3's was total, not partial, and the statement sat beside a
    # column counting 47 agreements). Both sides
    # read the same column of the same row under the same `status='published'`
    # filter, so this row bites where the two paths TREAT that column
    # differently (`plan_version_facts` coerces `int(plan.version or 1)`;
    # `plan_ref` does not) and on the chain's in-force narrowing, which
    # `plan_ref` does not apply at all and which surfaces as `NoPlanInForce`
    # rather than as a figure. Strictly stronger than comparing an input to
    # itself; weaker than R7, whose two sides are narrowed by different code.
    if str(data.rate_plan_version) != str(getattr(resolved.plan, "version", None)):
        found.append(
            Divergence(
                "R1",
                "",
                data.rate_plan_version,
                getattr(resolved.plan, "version", None),
                "the plan VERSION each path stamped on the bill (BR-CUS-013 — the "
                "bill SNAPSHOTS it, so two versions are two sets of terms)",
            )
        )

    live_quantities = _live_quantities(data)
    live_by_service = {config.service: config for config in data.tariffs}
    for service_resolution in resolved.services:
        service = service_resolution.service
        config = live_by_service.get(service)
        if config is None:
            found.append(
                Divergence(
                    "R2",
                    service,
                    None,
                    service_resolution.schedule_version_id,
                    "the live path resolved no tariff for this service",
                )
            )
            continue
        # ── R2 · the schedule VERSION in force at the service date ───────
        if str(config.version_id) != str(service_resolution.schedule_version_id):
            found.append(
                Divergence("R2", service, config.version_id, service_resolution.schedule_version_id)
            )
        # ── R3 · THE CONNECTION SIZE IS AN INVARIANT, NOT A COMPARISON ───
        # ⚠ **`DEF-2878` (2026-09-01) — THIS WAS A CHECK THAT COULD NOT FAIL,
        # AND IT IS `DEF-2839`'s FAULT ONE STEP OVER.** R1's plan id was an
        # input the adapter handed the catalogue, so comparing it compared a
        # value with itself; R3's size is the same shape and the fix for R1 did
        # not look next door. The size makes FOUR hops and starts and ends in
        # one place:
        #
        #     gather._connection_size_for  -> metering.connection_size_for
        #     resolution_shadow.adapt      -> metering.connection_size_for (same)
        #     adapt puts that value on `MeterFacts.connection_size`
        #     resolution.resolve_served_size ends `return meter.connection_size`
        #     this comparison then tests the first against the last
        #
        # **MEASURED, not argued** (`10-scripts/cr052_r1r7_shadow_measure.py
        # --sabotage R3-seam`): with the shared seam patched for the whole pass
        # to answer `'W-2'` where it should answer `'W-58'` — a 2-inch ladder
        # pricing a 5/8-inch connection on every account, in BOTH
        # implementations — the per-step table read **47 agree / 0 disagree / 0
        # cannot evaluate at R3, unmoved**, and `by_step` was empty. The old
        # `--sabotage R3` moved it only because it rewrote ONE side after the
        # run was prepared.
        #
        # So every additional account added one more agreement of X with X, and
        # the PO's release condition for R3 — *"run the comparison over more
        # than one seeded utility"* — could never have been met by a wider
        # population. **R3's `agree` column is retired rather than grown**: the
        # harness's `comparator_coverage()` no longer lists R3 among the steps
        # `compare()` covers, so it reports `cannot evaluate` with this reason
        # instead of counting a zero nobody earned.
        #
        # ⚠ **WHAT IS STILL GENUINELY INDEPENDENT AT R3, AND IT IS THE REFUSAL.**
        # `resolve_served_size` raises `SizeNotServed` for a size absent from the
        # schedule's own axis where the live path prices from the every-size
        # ladder anyway. That is not circular — the axis is the SCHEDULE's fact
        # and the size is the CONNECTION's — it is money, and it is enumerable
        # without any population at all (`tests/test_def2878_r3_refusal.py`).
        # The harness already counts a chain refusal at R3 as an R3 disagreement,
        # so that half of the row is unchanged by this edit.
        #
        # **WHY A RAISE AND NOT A DIVERGENCE, which is `DEF-2839`'s own posture.**
        # These two cannot differ for a reason the shadow controls, so if they
        # ever do, the adapter mapped a DIFFERENT CONNECTION from the one the
        # live path priced and no figure on this account means anything — the
        # base amount, the quantity and the tax are all about someone else's
        # meter. The known way to reach it is a MASTER account (BR-CUS-068):
        # `gather` resolves each service against the COVERED UNIT that serves it
        # (`serving_units`), this adapter resolves every service against the
        # anchor's `unit_id`, and a hallway's 2" irrigation connection is not the
        # anchor's 5/8". That account is then reported `not_attempted` by
        # `shadow_report` with this sentence, which is the truth about it, rather
        # than as a pricing disagreement between two implementations.
        live_size = getattr(config, "size_class", None)
        if (live_size or None) != (service_resolution.connection_size or None):
            raise AssertionError(
                f"R3: the two paths resolved DIFFERENT connection sizes for {service!r} "
                f"(live {live_size!r}, ruled {service_resolution.connection_size!r}). "
                "Both read `metering.connection_size_for` and the chain returns the "
                "adapter's own value unchanged, so these cannot differ for a pricing "
                "reason: the adapter mapped a different CONNECTION from the one the "
                "live path priced — a master account resolves each service against the "
                "covered unit that serves it (BR-CUS-068) and this adapter asks the "
                "anchor. No other figure on this account is about the same meter. "
                "Fix the inputs, never the assertion."
            )
        # ── R4 · THE BASE AMOUNT, AND WHO SUPPLIED IT (BR-RAT-088) ───────
        # ⚠ **THE TWO SIDES ARE TWO INDEPENDENT NARROWINGS OVER ONE TABLE, AND
        # THAT IS DELIBERATE.** Since `DEF-2823` both paths read the base from
        # the `is_base` CHARGE CODE — but the live path reaches it through
        # `rating.selectors.base_charge_from_charge_code` and the chain through
        # `resolution_catalogue.charge_code_facts` → `resolve_charge_codes` →
        # `resolve_base_charge`, which additionally applies the recurrence gate
        # and the whole-catalogue candidate set. Wiring the live path to CALL
        # the chain would have made this row agreement by construction: a check
        # that cannot fail, which is worse than no check (`DEF-182`). This is
        # the posture `R7` already takes, and R7 is the only step that has ever
        # disagreed.
        #
        # `base_source` rides on the note so a disagreement says WHICH OBJECT
        # priced the chain's side — a bill that cannot name where its base came
        # from is a bill nobody can audit.
        if _dec(config.base_charge) != _dec(service_resolution.base_charge):
            found.append(
                Divergence(
                    "R4",
                    service,
                    config.base_charge,
                    service_resolution.base_charge,
                    f"base_source={getattr(service_resolution, 'base_source', '?')}",
                )
            )
        # ── R3b · the BILLABLE QUANTITY (DEF-2798) ───────────────────────
        # The figure that decides which tier a customer's usage lands in, and
        # the one a x1000 multiplier error moves. See the docstring for why this
        # is the quantity and NOT `TariffConfig.multiplier`.
        #
        # ⚠ A `None` ON EITHER SIDE IS COMPARED, NEVER SKIPPED. *"No usable
        # read"* against *"a quantity of 620 kWh"* is the most expensive
        # disagreement on this list, and skipping the pair because one half is
        # absent would report it as agreement.
        live_quantity = live_quantities.get(service, _ABSENT)
        chain_quantity = _dec(service_resolution.billable_quantity)
        if live_quantity is _ABSENT:
            found.append(
                Divergence(
                    "R3b",
                    service,
                    None,
                    service_resolution.billable_quantity,
                    "the live path carries no reading row for this service at all",
                )
            )
        elif live_quantity != chain_quantity:
            found.append(
                Divergence(
                    "R3b",
                    service,
                    live_quantity,
                    service_resolution.billable_quantity,
                    "billable quantity — the live path's post-multiplier consumption "
                    "against the chain's register-difference x multiplier "
                    f"(x{service_resolution.meter_multiplier}, "
                    f"source={getattr(service_resolution, 'quantity_source', '?')})",
                )
            )
        # ── R5 · the jurisdiction factor on the MONEY (DEF-2798) ─────────
        # Both paths carry this fact per service and mean the same thing by it:
        # `TariffConfig.jurisdiction_factor` is *"a PRICING fact carried by the
        # PREMISES: it scales the MONEY, after the tiers have been walked"*, and
        # `ServiceResolution.money_factor` is R5's answer to the same question.
        if _dec(config.jurisdiction_factor) != _dec(service_resolution.money_factor):
            found.append(
                Divergence(
                    "R5",
                    service,
                    config.jurisdiction_factor,
                    service_resolution.money_factor,
                    "jurisdiction factor on the money (BR-RAT-102)",
                )
            )

    # ── R2 · a service the LIVE path priced and the chain never saw ──────
    chain_services = {row.service for row in resolved.services}
    for service, config in live_by_service.items():
        if service not in chain_services:
            found.append(
                Divergence(
                    "R2",
                    service,
                    config.version_id,
                    None,
                    "the ruled path resolved no schedule for a service the live path priced",
                )
            )

    # ── R6 · the DISCOUNT SET, one per bill (DEF-2798) ───────────────────
    # `DiscountResolution.applied` is *"the discount's CONFIGURED value, not an
    # amount off a bill"* — R6 SELECTS and `discount_pricing` prices — and
    # `AccountBillingData.discounts` is the same selection made by the live
    # path's own `billable_discount_rules`. Codes AND values, because a
    # programme both paths agree to apply at two different percentages is a
    # disagreement the code set alone would report as parity.
    live_discounts = tuple(
        sorted((str(rule.code), _dec(rule.value)) for rule in data.discounts)
    )
    chain_discounts = tuple(
        sorted((str(code), _dec(value)) for code, value in resolved.discounts.applied)
    )
    if live_discounts != chain_discounts:
        found.append(
            Divergence(
                "R6",
                "",
                live_discounts,
                chain_discounts,
                "the granted discount set (code, configured value) — the chain drops a "
                "code the catalogue does not offer (BR-RAT-110) and can never add one, "
                "because `adapt` takes the enrolments FROM the live path's own answer",
            )
        )

    # ── R7 · the TAX SET, one per bill (DEF-2798) ────────────────────────
    # THE ONLY THING THAT CAN EVER EVALUATE R7 — it publishes no refusal class
    # and never will, because a failed condition means NO LINE rather than an
    # error (DEF-273). The two narrowings are genuinely independent:
    # `rating.selectors.plan_tax_rules` evaluates r10's conditions BEFORE a live
    # `TaxRule` is built, `resolve_taxes` evaluates its own four over the
    # catalogue. CODES only, and that is a limit worth naming: the live rule
    # carries a `rate` where the chain's carries the configured one, and this
    # comparison asks WHICH AUTHORITIES ATTACH, which is the question R7 is.
    live_taxes = tuple(sorted(str(rule.code) for rule in data.taxes))
    chain_taxes = tuple(sorted(str(rule.code) for rule in resolved.taxes))
    if live_taxes != chain_taxes:
        found.append(
            Divergence(
                "R7",
                "",
                live_taxes,
                chain_taxes,
                "the tax rules that ATTACH to this bill (R7 decides applicability, "
                "never an amount)",
            )
        )
    return found


#: R3b's live half when the account carries no reading row for a service at all.
#: A sentinel and not `None`, because `None` is a REAL answer there — *"there is
#: no usable read"* — and collapsing the two would let *"nobody published a row"*
#: read as *"the meter was read and there is no quantity"*.
_ABSENT = object()


def _live_quantities(data: AccountBillingData) -> dict[str, Any]:
    """R3b's live half: the quantity the LIVE path will price, per service.

    `ServiceReading.consumption` is metering's stored `(current − prior) ×
    multiplier` — already post-multiplier by the PO's ruling of 2026-08-11 — so
    it is the same figure `ServiceResolution.billable_quantity` states, arrived
    at by different code from different reads of the same registers.

    ⚠ **`consumption=None` IS KEPT AS `None` AND NEVER TURNED INTO A ZERO.**
    `contracts.ServiceReading` draws that distinction in its own words and the
    whole shadow depends on it: a zero would state that the meter was read and
    showed nothing, which is a different and sometimes very expensive claim.
    """
    quantities: dict[str, Any] = {}
    for reading in data.readings:
        consumption = reading.consumption
        quantities[reading.service_code] = (
            None if consumption is None else _dec(getattr(consumption, "amount", None))
        )
    return quantities


def _dec(value: Any) -> Decimal | None:
    return None if value is None else Decimal(str(value))


# ══════════════════════════════════════════════════════════════════════════
# STEP 3 · THE REPORT the pre-commit screen renders
# ══════════════════════════════════════════════════════════════════════════


def summarise(outcomes: tuple[ShadowOutcome, ...]) -> dict[str, Any]:
    """The counts S31.2 shows: *"the ruled path and the live path disagree on 14
    of 1,247 accounts."*

    ⚠ **A COUNT THAT IS ALWAYS ZERO MEANS THE CHAIN IS NOT RUNNING**, and
    nothing else would say so (decision log, 2026-08-27). `attempted` is
    published beside `disagreed` for exactly that reason: zero disagreements out
    of zero attempts is not parity, and a screen that showed only the
    disagreement count could not tell the two apart.
    """
    attempted = tuple(o for o in outcomes if o.status != STATUS_NOT_ATTEMPTED)
    by_step: dict[str, int] = {}
    for outcome in outcomes:
        for divergence in outcome.divergences:
            by_step[divergence.step] = by_step.get(divergence.step, 0) + 1
        if outcome.refusal_step:
            by_step[outcome.refusal_step] = by_step.get(outcome.refusal_step, 0) + 1
    blocked: dict[str, int] = {}
    for outcome in outcomes:
        if outcome.blocked_reason:
            blocked[outcome.blocked_reason] = blocked.get(outcome.blocked_reason, 0) + 1
    return {
        "accounts": len(outcomes),
        "attempted": len(attempted),
        "agreed": sum(1 for o in attempted if o.status == STATUS_AGREED),
        "disagreed": sum(1 for o in attempted if o.disagreed),
        "chain_refused": sum(1 for o in attempted if o.status == STATUS_CHAIN_REFUSED),
        "not_attempted": len(outcomes) - len(attempted),
        "by_step": by_step,
        "blocked_by_reason": blocked,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-438 (root) · DEF-1810 · DEF-1811 · DEF-1812 · DEF-1813 · decision
#         log 2026-08-27 *"HOW R1–R7 GETS WIRED INTO BILLING — run both, compare,
#         rule, then switch"* and *"R1–R7 STEP 3, DELIVERED"* · step 1 of
#         12-governance/19-execution-sequence.md · BR-RAT-001 · BR-RAT-007 ·
#         BR-RAT-030 · BR-RAT-081 · BR-RAT-088 · BR-RAT-090 · BR-MET-056 ·
#         BR-BIL-039 · BR-SHL-020
# generated: 2026-08-27 by the R1–R7 wiring lane (claude)
# checklist: A✔ (backend) B✔ — ⚠ **AMENDED 2026-08-28. THE S31.2 PANEL IS
#         BUILT.** This line read "NOT BUILT ON PURPOSE … withheld while the
#         chain can be run on NO account (DEF-1811)", on the recorded warning
#         that *"a count that is always zero means the chain is not running"*.
#         **That judgment's own stated condition was met the next day**: DEF-1813
#         closed the last of the four missing facts and the shadow now attempts
#         a real account (attempted 1 · disagreed 1 · by_step {R1: 1}). The panel
#         is `apps/billing/shadow_report.py` and `GET /billing/runs/{id}/
#         pricing-shadow`, drawn on S31.2. C✔ (tests + data) D✔ (proved)
# gates: golden-verify 33 PASS / 0 FAIL before and after — no ❄️ B4/B5 figure is
#         asserted or moved here · tests/test_def_1810_resolution_shadow.py (8) ·
#         tests/test_def_1810_disagreements.py (5) ·
#         tests/test_def_438_parity.py (17, unchanged) · run_gates unchanged by
#         this file. THREE GUARDS PROVED RED FIRST (hard-won law 7): a defaulted
#         multiplier, metering's stored consumption in place of the register
#         difference, and the exception class name in place of the refusal
#         sentence — each failure quoted in the lane report.
# exceptions: (1) ⚠ **AMENDED 2026-08-28 — THIS MODULE NOW HAS EXACTLY ONE
#         PRODUCTION CALLER, AND IT IS THE ONE THE RECORDED METHOD ALLOWS.**
#         `apps/billing/shadow_report.py`, serving `GET /billing/runs/{id}/
#         pricing-shadow` on S31.2 — step 3 of the cutover, whose "what changes
#         on a bill" column reads **nothing**. The caller PRICES NOTHING: it
#         reads `shadow_account` for its REPORT, and `runs.py` does not import
#         it, so a fault there cannot reach `prepare_run`, `calculate_account`
#         or issue. **The prohibition this line used to carry is UNCHANGED for
#         every other caller**: a lane that calls `shadow_account` from the bill
#         run has started step 5 without step 4, which is the one thing the
#         method forbids. **And the importer gate no longer needs an exemption
#         keyed to DEF-1811** — when it lands it should find this file CALLED.
#         ⚠ **A SECOND IMPORTER EXISTS AND IT IS NOT A `shadow_account` CALLER
#         (`DEF-2550`, filed by the lane that wrote it):**
#         `apps/billing/resolution_switch.py` — step 5's per-step door — imports
#         `adapt` and nothing else, and runs the chain only for a step the
#         DEPLOYMENT names. No deployment names one, so it is inert today. The
#         two importers are the two the method allows and no third is.
#         (2) **FOUR FACTS ARE MISSING AND NONE IS DEFAULTED.** The connection
#         size (DEF-1811/DEF-514), the meter multiplier (DEF-1812), the unmetered
#         asset count (DEF-1813) and the plan each block the adapter by name.
#         ⚠ **THREE OF THE FOUR ARE SOURCED AS OF 2026-08-28 AND `MISSING_PLAN`
#         IS THE ONLY ONE LEFT — the size and the multiplier landed with
#         BR-AST-500/BR-MET-500, and the UNMETERED ASSET COUNT with BR-MET-710
#         (`DEF-1813` CLOSED).** The count now travels on the READING ROW
#         (`ServiceReading.asset_count`), which `adapt` prefers over a fresh
#         seam call for the reason BR-MET-500 records for the multiplier: the
#         row cannot name a different unit or a different date from the one
#         being priced, and reading it costs no query. `MISSING_ASSET_COUNT`
#         still fires — on an account whose carts nobody has counted, which is
#         a REAL refusal and not a wiring gap. `MISSING_PLAN` is a customer
#         configuration and was never metering's to source.
#         Defaulting the multiplier to 1 would make R3b report PARITY BY
#         CONSTRUCTION on every account, which is why there is no fallback here.
#         (3) The metering seams `connection_size_for`, `billing_multiplier_for`
#         and `billable_asset_count` are LATE-BOUND and two of the three do not
#         exist. This is `gather.py`'s documented posture, not dead wiring: the
#         tests publish each seam and assert the fact reaches the chain.
#         (4) ⚠ **R1's COMPARISON WAS A CHECK THAT COULD NOT FAIL UNTIL
#         2026-08-31 (`DEF-2839`).** It tested `data.rate_plan_id` against a
#         `plan_id` the catalogue had been HANDED FROM THAT SAME FIELD, so both
#         sides were one value by construction: over 94 account evaluations
#         (a clean run and a `--sabotage R1` run) `figures_differ` was produced
#         NOT ONCE, and the sabotage only appeared to work because it moved its
#         row through the REFUSAL path. The plan id is now an INVARIANT that
#         RAISES and the VERSION — which never reaches the chain — is the
#         compared figure. **The residual limit is stated in `compare()`'s own
#         comment and must travel with any decision taken from R1's agree
#         column:** both sides read one column of one row, so the row bites on
#         the two paths' different TREATMENT of it and on the chain's in-force
#         narrowing, which surfaces as a refusal. Stronger than comparing an
#         input to itself; weaker than R7.
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING 🔒 — rating math / money, a
#         CLAUDE.md sensitive path; row in 12-governance/09-human-review-ledger.md.
#         Not RATIFIED without a recorded human sign-off.
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
