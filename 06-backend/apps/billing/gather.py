# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-002 (S31.2 — "Check what we found": the run assembles every
#           input per account and shows it BEFORE anything commits)
#           Screens: S31.2 · S31.3
# Rules:    **BR-CUS-103** (PO 2026-08-25, closing OQ-380 — base charges STOP at
#           the cut, and the boundary is the CUT date: `_service_days` subtracts
#           the dark days and B4.3's frozen factor prices it) ·
#           BR-BIL-039 (stages 1–5 are PURE — so everything they need is
#           gathered first, here) · BR-BIL-015 (a missing input is an
#           EXCEPTION, never a silent skip) · BR-CUS-055 (status behaviour
#           classes) · BR-CUS-014 (the account derives its plan from the unit)
#           · BR-RAT-007/017 (reprice on the SERVICE DATE — 7-year
#           reproducibility) · BR-RAT-030 (published plans only) · B4.2 (tax
#           exemption is account-level) · BR-RAT-101 (the inside/outside-city
#           flag is the PREMISES', resolved Account → Unit → Premises; `None` is
#           a THIRD STATE) · BR-RAT-102 (the PLAN states the outside-city factor
#           and its per-service exemptions; a factor over a `None` premises
#           STOPS THE BILL) · BR-RAT-032 as amended by DEF-433 (NULL is "every
#           size"; a size_class group is the exception) · CLAUDE.md rule 2 (the
#           tenant's currency) · rule 3 (a quantity carries its unit)
#           · BR-CUS-068 / BR-MET-101 (a MASTER account is one row covering
#           several common areas, so one bill prices EVERY covered unit —
#           1408 Elm: hallway $41.20 + shared irrigation $28.40 = $69.60)
# Defects:  DEF-484 / DEF-514 (the connection size) · DEF-466 / DEF-515 /
#           DEF-517 (the outside-city factor and the two columns nothing writes)
#           · DEF-502 (discounts priced by nothing — `_discounts_for` +
#           `_discount_treatments` are the close's gather half, 2026-08-22)
#           · DEF-571 (a master bill priced the ANCHOR unit only)
# OQs:      OQ-334 (two covered areas on ONE service — base per connection or
#           per bill?) · OQ-335 (covered areas on DIFFERENT plans — whose
#           taxes, fees, discounts, snapshot?). Both REFUSE by name here.
# Tests:    **06-backend/tests/test_br_cus_105_static_balance.py (BR-CUS-103 — a
#           cut account's base charge, on REAL priced bills)** ·
#           06-backend/tests/test_us_bil_002_gather.py ·
#           06-backend/tests/test_def_484_size_and_jurisdiction.py
# Impacts:  **apps.customers.selectors.service_off_windows (resolved BY NAME —
#           BR-CUS-103's dark days; billing writes nothing to customers)** ·
#           apps/billing/stages/** (everything they consume comes from here) ·
#           the S31.2 preview, which renders exactly this
# ───────────────────────────────────────────────────────
"""The one impure pass: read everything the run needs, before the run starts.

HUMAN-REVIEW-PENDING — 🔒 rating/billing math. The 2026-08-22 master-account
amendment (BR-CUS-068 coverage) is AI-authored under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md. It implements the
signed rules of 2026-08-21/22 and invents no figure: the two places those rules
run out are OQ-334 and OQ-335, and both REFUSE rather than choose.

HUMAN-OWNED — added 2026-08-31 when the PO's ruling put this file on
10-scripts/gates/human_owned.txt ("groups one, two, three and four ... That is
56 files"). The guard list requires both markers; this file carried only
HUMAN-REVIEW-PENDING, which is exactly why G53 could not see it (DEF-2790).

BR-BIL-039 makes stages 1–5 pure — no writes, no external calls, no clock.
Read that literally and this module is what it implies: a stage that cannot
call anything cannot go and fetch what it needs, so something must fetch it
first. This is that something, and it is the ONLY part of the run that reads
the database.

That is not a tidiness argument. It is what makes three separate things true:

  * **The preview and the real run are the same code.** BR-BIL-039: "the S31.2
    preview is stages 1–5 with stage 6 not run." Two implementations that
    agree until they don't is the classic way a preview lies.
  * **The PO's prepare screen works.** *"we build the data first for billing
    show all that data on screen for user … in case any data should be
    changed, he is able to do it."* What is gathered is what is shown, what is
    edited, and what is then billed — one object, so "what I approved" and
    "what got billed" cannot be different things.
  * **A re-rate is trivial.** Replay stages 2–6 over the same gathered data;
    nothing to undo, because nothing before stage 6 wrote anything.

CROSS-MODULE READS GO THROUGH SEAMS, NEVER IMPORTS (B1). Billing does not
import customers' or metering's or rating's models. Every read below resolves
the owning module's own selector by name, and a module that has not published
one yields None — which becomes a NAMED EXCEPTION on the account rather than a
crash or, worse, a plausible default.

────────────────────────────────────────────────────────────────────────────
THE SERVICE DATE IS THE PIVOT, and it is easy to get wrong
────────────────────────────────────────────────────────────────────────────
BR-RAT-007/017 promise seven-year reproducibility: a bill for June prices on
the tariff version in force on the SERVICE DATE, not the version in force when
the run happens. A run executed in July for a June period, or a re-run in
2031, must both reach the same version. So every tariff resolved here is
resolved AT `service_date`, and the version id travels onto the bill line so a
reprint can prove which prices were used.

Getting this wrong produces bills that are individually plausible and
collectively impossible to defend — the failure mode you discover in an audit.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from importlib import import_module
from inspect import signature
from typing import Any

from apps.billing import bill_warnings, rating_seam, resolution_switch, seam_batch
from apps.billing.contracts import WARN_NO_AGREEMENTS, AccountBillingData, ServiceReading
from apps.billing.exceptions import BillingRuleError

# CLAUDE.md hard rule 2 — money is stored to FOUR decimals and DISPLAYED to
# two. A refusal sentence a clerk reads is a display, so the one figure that
# reaches one goes through `finalize` rather than a local `quantize`: the
# rounding constants are HUMAN-OWNED (`core/money.py`'s own header) and this
# file may apply them, never restate them. `billing/selectors._display_money`
# is the same call one file over.
from core import batch_reads
from core import money  # noqa: F401 — unused at the tip too; not this lane's to remove

#: Why an account could not be gathered. These are VALUES because the run
#: groups its exception screen on them (BR-BIL-015) and free text cannot be
#: grouped. Each names the thing a human must fix.
GATHER_NO_UNIT = "account_has_no_unit"
GATHER_NO_PLAN = "unit_has_no_plan"
GATHER_PLAN_UNPUBLISHED = "plan_not_published"
GATHER_NO_TARIFF = "plan_has_no_tariff_for_service"
GATHER_NO_VERSION = "tariff_has_no_version_in_force_at_service_date"
GATHER_NO_CURRENCY = "tenant_currency_unresolved"
#: `DEF-2381` (PO 2026-09-02) — base charges EXIST for this service and none of
#: them names this account's customer type.
#:
#: ⚠ **THIS IS NOT `GATHER_NO_TARIFF`, AND THE DISTINCTION IS THE DEFECT.**
#: `charges.applies_to_customer_classes` is an INCLUSION list (`BR-RAT-108`),
#: so a type nobody listed matches nothing — and until this constant existed
#: the account fell through to the plan's figure, or, with the R3/R4 chain
#: served, to `tariff_versions.base_charge`, the column `BR-RAT-088` RETIRED.
#: Measured on PostgreSQL 16 under `DEF-3282`: a seeded municipal building with
#: a plan, an active account, three service points, a meter and four committed
#: reads sat in the run's scope and issued **0 invoices** while unit 0 issued 2,
#: with nothing failing and nothing logged.
#:
#: **A SERVICE WITH NO `is_base` CODE AT ALL IS A DIFFERENT FACT AND IS
#: UNCHANGED.** That tenant has not adopted `BR-RAT-088` and still bills from
#: the plan; turning it into a refusal would stop every bill for every tenant
#: provisioned before the ruling. Rating draws the line, not this module —
#: `base_charge_from_charge_code` returns `refusal_reason: "customer_class"`
#: only when the codes exist and the narrowing emptied them.
GATHER_NO_BASE_FOR_CUSTOMER_TYPE = "no_charge_applies_to_this_customer_type"
#: DEF-484 / DEF-514 — the rate schedule prices some sizes differently and this
#: connection's size cannot be stated, so which ladder applies is unknown.
GATHER_SIZE_UNRESOLVED = "connection_size_unresolved_for_sized_schedule"
#: BR-RAT-101 / BR-RAT-102 — the plan surcharges outside the city and nobody has
#: recorded which side of the line this premises is on.
GATHER_JURISDICTION_UNSTATED = "premises_jurisdiction_unstated"
#: BR-CUS-068 — this account covers SEVERAL units (a master account) and
#: customers has not published the read that says WHICH. Never degraded to the
#: anchor: that silent under-bill is DEF-571 itself.
GATHER_COVERAGE_UNRESOLVED = "master_coverage_unresolved"
#: OQ-335 — the covered units sit on DIFFERENT plans and no signed rule says
#: whose taxes, fees, discounts or plan snapshot govern the one bill.
GATHER_COVERAGE_MULTI_PLAN = "master_coverage_spans_two_plans"
#: OQ-334 — two covered units take the SAME service and no signed rule says
#: whether the base charge is per connection or per bill.
GATHER_COVERAGE_SERVICE_TWICE = "master_coverage_repeats_a_service"
#: BR-CUS-103 (PO 2026-08-25, closing OQ-380) — SOME of this account's services
#: were cut and some were not, and B4.3 prorates ONE factor for the whole
#: account. There is no per-service `service_days` anywhere in the engine, so
#: stopping base for the cut half would stop it for the live half too and
#: leaving it running would bill a dead connection. Neither is rounded to; the
#: account goes to the exception screen with the two service lists named.
GATHER_PARTIAL_CUT = "cut_covers_some_services_and_not_others"
#: BR-BIL-870/872 — a rule of the R1–R7 chain is SWITCHED ON for this
#: deployment and the ruled path has no answer for this account: either the
#: chain refused by name, or the adapter could not assemble a fact it needs.
#:
#: ⚠ **THERE IS NO FALLBACK TO THE OLD IMPLEMENTATION HERE, AND THERE MUST
#: NEVER BE ONE.** Quietly re-serving this account from the code the deployment
#: just switched away from would produce a bill nobody could attribute to
#: either path, and it would erase the disagreement the cutover exists to
#: measure (decision log 2026-08-27). The account goes to the exception screen
#: carrying the chain's OWN sentence, which names its step and the missing fact.
#: ⚠ **CORRECTED 2026-09-01 — IT FIRES.** This line read *"Fires on NOTHING
#: today: no deployment names a step … this reason cannot be raised"* and it
#: stopped being true the hour `CR-057` shipped: `resolution_switch
#: .SERVED_BY_CHAIN_DEFAULT` and `config/settings/base.py` both name **R3,R4**,
#: so the chain prices every account's base charge and a chain refusal reaches
#: this constant on a real bill run. A comment claiming a guarantee is not the
#: guarantee (hard-won law 1), and this one would have told a lane the exception
#: path was dead code. It is raised only on a deployment that has NOT rolled the
#: pair back (`SBH_BILLING_RESOLUTION_STEPS=`), and `DEF-2923` is what it looked
#: like the first time: a tenant with no `is_base` charge code declared for a
#: service had every account of that service refused by name.
GATHER_RULED_PATH_REFUSED = "ruled_path_refused"


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one.

    ⚠ **CR-051 task 22 · THE ONE PLACE A SEAM NAME BECOMES A CALLABLE.** When a
    prepare pass is open (`runs.prepare_run` holds one), `seam_batch.wrap`
    returns a memoised form of the seam for the run- and plan-scoped reads on
    its named list — the SAME callable, the SAME arguments, the SAME answer,
    asked once for a thousand accounts instead of a thousand times.

    It is wired HERE and not at the call sites deliberately (hard-won law 2): a
    seam reached around this would be a seam nobody batched, and there would be
    no way to tell which. Outside a pass, and for every seam not on that list,
    this returns exactly what it always returned.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    if not callable(found):
        return None
    return seam_batch.wrap(module, attribute, found)


class GatherProblem(BillingRuleError):
    """This account cannot be gathered, and here is the reason code.

    A subclass rather than a flag so the orchestrator can catch exactly this
    and record the account as an exception, while a genuine bug still
    propagates. `reason` is one of the GATHER_* values above — the exception
    ⚠ **`message` IS FOR THE RECORD AND `clerk_detail` IS FOR THE SCREEN —
    `DEF-RAT-7991`, 2026-09-29.** Nine of the rating chain's raise sites put a
    database uuid in `message`, and `one_time.py` serves it in a 200-response
    body that no `detail` stripper is anywhere near. These three fields are
    rating's own clerk sentence, carried through untouched; they are None on
    every problem this module raises itself, and a serialiser that finds them
    empty falls back to `message` exactly as it always did.
    """

    def __init__(
        self,
        reason: str,
        message: str,
        *,
        service_code: str | None = None,
        message_key: str | None = None,
        clerk_detail: str | None = None,
        message_params: dict[str, object] | None = None,
    ):
        super().__init__(message)
        self.reason = reason
        self.service_code = service_code
        self.message_key = message_key
        self.clerk_detail = clerk_detail
        self.message_params: dict[str, object] = dict(message_params or {})


def _base_charge_for(
    service_code: str,
    *,
    code_base: Any,
) -> Decimal:
    """🔒 HUMAN-REVIEW-PENDING — see `12-governance/09-human-review-ledger.md`.

    WHAT THIS BILL CHARGES FOR STANDING SERVICE: the CHARGE CODE's figure, and
    nothing else (`DEF-BIL-7170`).

    ── 2026-09-28 · THE PLAN'S BASE IS RETIRED, AND RETIRED MEANS UNREADABLE ──
    PO ruling, verbatim: *"we ahve to take ot from Charge code - whya re you
    confuse about it - charge code binded in plan - unitl it is part of plan we
    cannot take amount from charge code - we will never take default value from
    plan $8.0 - that is retired"*. Two statements, both load-bearing:

      1. the amount comes from the CHARGE CODE, and only where that code is
         BOUND TO THE PLAN — the account resolves to a plan, the plan attaches a
         RATE SCHEDULE per service, and the schedule names (or the catalogue
         infers) the code that owns that service's base (`BR-RAT-1025`). An
         unbound `is_base` code prices nothing.
      2. the plan's own base figure is **never a source and never a fallback**,
         **not even when the charge code is silent**.

    **SO THERE IS ONE INPUT AND TWO OUTCOMES:**

        the charge code states an amount  -> THAT is the base. Full stop.
        it states none                    -> `$0.00`, and a named warning.

    ⚠ **THE SECOND LINE READ *"REFUSE, by name"* UNTIL 2026-09-30, AND THE PO
    REVERSED IT THAT DAY.** Verbatim: *"here we need to builf flexibility - if
    user did not define and bind base charges in rate schedule - then as a
    default you take 0 and complete the bill instead of refusing - if you want
    to show the warning you can display it dueing the process"*. The refusal
    was our implementation choice; the ruling of 2026-09-28 said only where the
    base comes FROM, and **it stands: the default is `$0.00` and never the
    retired plan figure.** The warning is `billing.oneTime.warn.baseNotSet`
    with `{service}`, collected per `gather_account` call (`_BASE_NOT_SET`)
    and carried on `AccountBillingData.warnings`.

    ⚠ **WHAT WAS DELETED HERE, AND WHY DELETED RATHER THAN LEFT UNREAD.** This
    function took `plan_base` and `schedule_base` and read BOTH: it preferred
    the charge code, then compared the other two against it and raised *"Two
    base charges for {service}. Clear {amount} on the {plan|rate schedule}"*
    when either DIFFERED. That is `DEF-BIL-7170`, critical: a tenant whose
    migration left a stale figure had **every bill for that service stopped**,
    told to go and clear a number on an object the product itself says does not
    define it. The two parameters are GONE rather than accepted and ignored,
    for the reason this module already gave when it dropped `code_label=`: *"a
    parameter nothing reads is hard-won law 1 in miniature"*. A retired source
    still sitting in the signature is an invitation to read it again.

    ⚠ **AND `code_base` IS KEYWORD-ONLY SO THE DELETION CANNOT BE SILENT.** The
    old call was `_base_charge_for(service, plan_base, schedule_base,
    code_amount)`. Had the new one simply taken two positionals, that stale
    call would have passed **the plan's figure as the charge code's** and billed
    the retired column under the ruling that retired it — a well-formed bill
    nobody could see was wrong, which is `DEF-154`'s shape exactly. Keyword-only
    turns every such call into a `TypeError` at the first line that runs it.

    ⚠ **WHY THE MEASUREMENT THAT MADE THE OLD BEHAVIOUR LOOK SAFE IS THE REASON
    IT WAS NOT.** `BR-RAT-088`'s entry recorded the 2026-08-31 switch as proved:
    *"all 47 ready accounts on the seeded tenant state the SAME figure on both
    objects, so no bill moved"*. True — and it means the refusal branch **was
    never exercised by a real account**. It was unreachable on the data it was
    measured against: law 7's *incapable of failing*, one step removed. The
    mismatched configuration is built deliberately now, on real PostgreSQL, by
    `10-scripts/def_bil_7170_plan_base_retired_proof.py`, and asserted by
    `tests/test_def_bil_7170_plan_base_is_retired.py`.

    ── `$0.00`, AND WHAT IT IS NOT (2026-09-30) ───────────────────────────
    **`code_base is None` REACHES HERE FOR THE FOUR CASES THE RULING NAMES**
    (decision log 2026-09-30): (a) no base code for the service at all, (b) the
    schedule named a code that cannot price this account — none is BOUND for
    it, (c) no base code reaches this customer type, (d) the base code states
    no amount. Rating marks (b)–(d) `not_set` and `_base_charge_code_for` lets
    them through. **The CONFLICTS still refuse, by rating's own sentence,
    before this function is called**: two codes survive the narrowing, a code
    states both a flat amount and a per-size table, a size the code does not
    price (`CR-013`: blank = not served), and a connection whose size is not
    recorded. Choosing between two things the utility DID define is a guess
    about money; a base nobody defined is not.

    ⚠ **A STORED `0.00` IS NOT SILENCE AND STILL BILLS `$0.00`** — PO ruling
    2026-08-19, verbatim *"print $0.00"*. What refuses is a base nobody stated.
    `CR-013` part 1's *blank = this size is not served* is the same fact from
    the other end and is refused by rating before it gets here.

    ⚠ **THE REPAIR NAMES CHARGE CODES AND NO LONGER NAMES THE PLAN.** It used
    to read *"No base charge for {service}. Type it on the plan's services."*,
    which under this ruling sends a clerk to type a figure into the one column
    the product has stopped reading — the bill would refuse again on the next
    run and nothing on screen would say why. B14 rule 32 (no rule id in
    clerk-facing copy) and rule 33 (a label ≤ 3 words, a fact ≤ 6, RATIONALE at
    ZERO words) are why it is two six-word sentences and why the whole of the
    *why* is in this docstring.

    ⚠ **THIS IS NOT THE LAST WORD ON THE PLAN'S COLUMN, DELIBERATELY.** The PO
    ruled on what may be READ. Whether that column stops being WRITTEN and
    SHOWN is a separate question and is named as NOT RULED in the decision-log
    entry of 2026-09-28. Do not delete the column, its API field or its display
    on the strength of this function.
    """
    code_amount = _decimal_or_none(code_base)
    if code_amount is None:
        # ── PO ruling 2026-09-30 · NOT DEFINED AND BOUND -> `$0.00` + A WARNING ─
        # See the docstring's last section. The retired plan figure is NOT a
        # source here either: the default is zero, never `$8.00`.
        _record_base_not_set(service_code)
        return BASE_NOT_SET_AMOUNT
    return code_amount


#: PO ruling 2026-09-30 — the base a service bills when nobody DEFINED AND
#: BOUND one: *"as a default you take 0"*. Four decimals, hard rule 2.
BASE_NOT_SET_AMOUNT = Decimal("0.0000")

#: The services whose base answered *not set* during the `gather_account` call
#: in progress. A context variable rather than a return value because the
#: answer is found three calls deep inside `_tariff_config_for`, which has four
#: callers and returns a `rating_seam.TariffConfig` (🔒 HUMAN-OWNED — a new
#: field there would widen a signed contract for a warning). `None` outside a
#: gather, where nothing collects and nothing is recorded.
_BASE_NOT_SET: ContextVar[list[str] | None] = ContextVar("billing_base_not_set", default=None)


def _record_base_not_set(service_code: str) -> None:
    collected = _BASE_NOT_SET.get()
    if collected is not None and service_code not in collected:
        collected.append(service_code)


#: PO ruling 2026-10-01 — the `(service, base code, size)` triples whose base
#: had no price for that size and billed `$0.00`, during the `gather_account`
#: call in progress. Same posture as `_BASE_NOT_SET` and for the same reason.
_SIZE_NOT_PRICED: ContextVar[list[tuple[str, str, str]] | None] = ContextVar(
    "billing_size_not_priced", default=None
)

#: PO ruling 2026-10-01, part 3 — *"i want tracbility -> billing -> account ->
#: unit -> plan -> rate schedule -> base charge -> size and amount"*. Per
#: SERVICE, what its base and price were found from, collected while the
#: tariffs are built and attached to `AccountBillingData.pricing_trace`;
#: `stages/assemble_document` writes it, as VALUES, onto every line of that
#: service (`invoice_lines.pricing_trace`, `billing/0039`).
_PRICING_TRACE: ContextVar[dict[str, dict[str, Any]] | None] = ContextVar(
    "billing_pricing_trace", default=None
)


#: PO ruling 2026-10-01 on `DEF-RAT-8004` (option A) — the services whose
#: schedule had MORE THAN ONE version in force on the service date during the
#: `gather_account` call in progress, each as rating published it
#: (`versions_in_force`, values, winner first). The newest priced
#: (`BR-RAT-1055`); this is how the Check names it. Same posture as
#: `_SIZE_NOT_PRICED`.
_VERSIONS_OVERLAP: ContextVar[list[tuple[str, date, dict[str, Any]]] | None] = ContextVar(
    "billing_versions_overlap", default=None
)

#: PO ruling 2026-10-01 (*"A METER WITH NO RECORDED SIZE GETS NO MINIMUM"*,
#: option A) — services priced with no connection size on a version that
#: states per-size minimums (rating's `minimum_needs_size`), then the meters
#: on that connection with no size, `(service, meter number)`.
_MINIMUM_NEEDS_SIZE: ContextVar[list[str] | None] = ContextVar(
    "billing_minimum_needs_size", default=None
)

#: 🔒 BR-RAT-034 · THE DAYS A SEASON-CROSSING SPLIT IS COUNTED OVER — the
#: account's SERVED span of the bill period, `(first day, last day)`, set by
#: `_gather_account` for the call in progress (`OQ-234` CLOSED 2026-09-07, PO
#: *"please split  swithch it on"*; built 2026-10-01, `DEF-RAT-8832`).
#:
#: ⚠ **A CONTEXT VARIABLE BECAUSE EVERY TARIFF IN A GATHER IS BUILT THROUGH
#: `_tariff_config_for`, FROM FOUR CALL SITES, THREE CALLS DEEP** — the same
#: reason `_BASE_NOT_SET` gives. Threading a parameter through every one of
#: them is a hop a fifth caller could forget, and a forgotten hop here is not a
#: crash: it is a season-crossing bill priced whole at one season's rates,
#: which foots perfectly (law 2's shape). Set in ONE place, read in ONE place.
#: `None` outside a gather — the impact analysis, a fixture — where no period
#: exists and the one-season answer is the right one.
_SEASON_SPAN: ContextVar[tuple[date, date] | None] = ContextVar(
    "billing_season_span", default=None
)
_METER_SIZE_NOT_RECORDED: ContextVar[list[tuple[str, str]] | None] = ContextVar(
    "billing_meter_size_not_recorded", default=None
)


def _record_versions_overlap(service_code: str, on_date: date, facts: dict[str, Any]) -> None:
    collected = _VERSIONS_OVERLAP.get()
    if collected is not None and all(entry[0] != service_code for entry in collected):
        collected.append((service_code, on_date, facts))


def _record_minimum_needs_size(service_code: str) -> None:
    collected = _MINIMUM_NEEDS_SIZE.get()
    if collected is not None and service_code not in collected:
        collected.append(service_code)


def _flag_unsized_meters(unit_id: Any, service_code: str) -> None:
    """After a config priced with NO connection size: if rating said that
    version states per-size minimums, name each meter on the connection with
    no recorded size. Sewer following its basis has no meter and is never
    named — metering answers `[]`."""
    if str(service_code) not in (_MINIMUM_NEEDS_SIZE.get() or ()):
        return
    collected = _METER_SIZE_NOT_RECORDED.get()
    if collected is None:
        return
    resolver = _resolve("metering", "unsized_meters_for")
    for meter in (resolver(unit_id, service_code) if resolver is not None else ()):
        entry = (str(service_code), str(meter))
        if meter and entry not in collected:
            collected.append(entry)


def _record_size_not_priced(service_code: str, code: str, size_class: str) -> None:
    collected = _SIZE_NOT_PRICED.get()
    entry = (service_code, code, size_class)
    if collected is not None and entry not in collected:
        collected.append(entry)


def _size_was_unpriced(service_code: str, size_class: str | None) -> bool:
    """Did this gather already bill `size_class`'s base at `$0.00` for want
    of a price? Read off the warning collector, the one record of it."""
    return any(
        service == service_code and size == (size_class or "")
        for service, _code, size in (_SIZE_NOT_PRICED.get() or ())
    )


def _is_capacity_service(service_code: str) -> bool:
    """BR-TEN-1180 — is this service billed on CAPACITY (a size and a count)?

    Read through billing's tenancy seam, which degrades to the EMPTY set: an
    unpublished answer refuses an unpriced size as before, never zeroes it.
    """
    from apps.billing import tenancy_seam

    return service_code in tenancy_seam.capacity_service_codes()


def _trace(service_code: str) -> dict[str, Any] | None:
    """This service's trace entry in the collector, created on first use, or
    `None` outside a gather (where nothing is recorded)."""
    collected = _PRICING_TRACE.get()
    if collected is None:
        return None
    return collected.setdefault(str(service_code), {"service": str(service_code)})


def _money_text(value: Any) -> str | None:
    """A money figure as TEXT at four places (hard rule 2), or None. A trace
    stores VALUES, never references to rows that will change — the size rows
    of a charge code are deleted and re-created on every edit."""
    amount = _decimal_or_none(value)
    return None if amount is None else str(amount.quantize(Decimal("0.0001")))


def _usage_price_of(config: Any) -> str | None:
    """The one usage price a per-size config charges per item — its flat unit
    price, or the price of a single open-ended tier. `None` where there is no
    single price (a ladder), so the trace never states an average."""
    if getattr(config, "unit_price", None) is not None:
        return _money_text(config.unit_price)
    tiers = tuple(getattr(config, "tiers", ()) or ())
    if len(tiers) == 1:
        return _money_text(tiers[0].unit_price)
    return None


def _base_charge_code_for(
    service_code: str,
    *,
    customer_class: str | None,
    size_class: str | None,
    named_code: str | None = None,
    on_date: date | None = None,
) -> tuple[Decimal | None, str | None]:
    """`BR-RAT-088` across the seam — what the CHARGE CODE says the base is.

    Returns `(amount, code)`. **`(None, None)` means the tenant has declared no
    base charge code for this service**, which is not an error and not a zero:
    the caller then takes DEF-154's pre-ruling answer and bills exactly what it
    billed yesterday. That fallback is what lets a tenant provisioned before
    the ruling go on producing bills, and `base_source` on the ruled chain's
    line is where the migration becomes observable rather than assumed.

    ⚠ **AN UNPUBLISHED SEAM DEGRADES TO THE PRE-RULING BEHAVIOUR AND NEVER TO
    A GUESS.** Rating owns this narrowing (B1: billing does not read rating's
    storage) and the read is resolved by name, like every other seam in this
    file, so a deployment whose rating lane has not landed prices exactly as it
    does today rather than raising mid-run.

    A refusal rating returns — two base codes surviving the narrowing, a code
    stating both a flat amount and a per-size table, a size the code does not
    price, a code stating no amount at all — becomes a `GatherProblem` carrying
    rating's own sentence WHOLE. It stops ONE account and lets the rest of the
    run bill (BR-BIL-055); it is never softened into a figure.

    ── `named_code` · WHAT THE RATE SCHEDULE SAID (`BR-RAT-1025`) ────────────
    ⚠ **THIS PARAMETER IS `DEF-RAT-5782`, AND THE DEFECT WAS THAT IT DID NOT
    EXIST.** The PO ruled on 2026-09-19 that a rate schedule NAMES the charge
    code that owns its service's base — *"plan → rate schedule -> charge code
    → base charges"*. Rating's read took the binding from that day; the ruled
    R1–R7 chain honoured it from that day; **this function, which is what
    actually bills, called the seam with three arguments and never passed a
    fourth.** A utility with three codes ticked as water's base had every bill
    refuse — *"3 base charge codes for water"* — while its own rate schedule
    screen showed the one it had chosen.

    **`None` MEANS THE SCHEDULE NAMED NOTHING**, which is every version this
    product has ever written (`rating/0037` adds the column NULL), and it is
    byte-identical to the call this function made yesterday.
    ⚠ **SINCE 2026-10-06 (`DEF-RAT-9832`, PO ruling) rating answers it
    `not_set`** — no code is taken from the pool by class — so it arrives here
    as `(None, None)` and `_base_charge_for` bills `$0.00` with the existing
    `baseNotSet` warning. No code in this module changed for that.

    ⚠ **A NAMED CODE THAT CANNOT ANSWER IS A REFUSAL AND NEVER A FALLBACK.**
    Rating decides that, and it decides it the way the chain and the
    activation gate already do; billing carries the sentence, as it does for
    every other refusal above. What must NOT be added here is a retry without
    the binding — it would bill the INFERRED code under a schedule naming
    another, which is the whole defect running backwards.
    """
    answer = _base_answer(
        service_code,
        customer_class=customer_class,
        size_class=size_class,
        named_code=named_code,
        on_date=on_date,
    )
    if answer is None:
        return None, None
    return _interpret_base_answer(service_code, answer)


def _base_answer(
    service_code: str,
    *,
    customer_class: str | None,
    size_class: str | None,
    named_code: str | None,
    on_date: date | None = None,
) -> dict[str, Any] | None:
    """Rating's raw answer for one service at one size, or `None` while the
    seam is unpublished. Split out of `_base_charge_code_for` on 2026-10-01 so
    the per-size base of a SUMMING capacity service (`_size_base`) reads the
    same seam, through the same interpretation, once per size."""
    seam = _resolve("rating", "base_charge_from_charge_code")
    if seam is None:
        return None
    # ⚠ **`named_code` IS PASSED UNCONDITIONALLY AND IS NOT DEGRADED
    # (`DEF-RAT-5782`).** Every other optional hop in this file degrades to
    # the previous behaviour when rating's half has not landed, and that is
    # right for a hop that can only DROP something. This one cannot: dropping
    # the binding bills the INFERRED code under a schedule whose first step
    # names another, which is a well-formed bill nobody can see is wrong —
    # the exact failure the binding was ruled into existence to end. `None`
    # is byte-identical to not passing it, so this moves nothing on a tenant
    # that has bound nothing, and a rating half with no such parameter raises
    # rather than quietly pricing from the wrong code.
    # ── CR-156-BRC10 · THE PRICE IN FORCE ON THE DAY BEING BILLED ─────────
    # PO 2026-10-01, option A: *"A past bill reads the row in force on its
    # dates."* `on_date` is the service date `_tariff_config_for` prices (a
    # split segment's own first day). Passed only when known, so a rating half
    # that predates the dated rows is called exactly as before.
    if on_date is not None:
        return seam(
            service_code,
            customer_class=customer_class,
            size_class=size_class,
            named_code=named_code,
            on_date=on_date,
        )
    return seam(
        service_code,
        customer_class=customer_class,
        size_class=size_class,
        named_code=named_code,
    )


#: Rating's tag for *"this per-size base code has no price for this size"*
#: (`base_charge_from_charge_code`, 2026-10-01).
SIZE_NOT_PRICED = "size_not_priced"


def _interpret_base_answer(
    service_code: str, answer: dict[str, Any]
) -> tuple[Decimal | None, str | None]:
    """`(amount, code)` from rating's answer, or a `GatherProblem`.

    🔒 HUMAN-REVIEW-PENDING — the 2026-10-01 branch is money (a base becomes
    `$0.00`); row in `12-governance/09-human-review-ledger.md`
    (*"2026-10-01 · CAPACITY BASE BY SIZE"*).

    ── 2026-10-01 · A CAPACITY SIZE WITH NO PRICE BILLS `$0.00` ─────────────
    PO verbatim: *"in case of all capacity based base rates … based rates
    should be search based on sizes dueing billing; if rate is not found then
    you assum it zero and calculate instead of refusing the bill"*. Worked:
    two 96-gallon carts, BASE-T with no CART-96 row, cart $15.00 — base
    `$0.00`, line `$30.00`, the bill completes and carries the warning
    *"BASE-T has no price for CART-96 · billed $0.00"*. **Capacity services
    ONLY** (`tenancy_seam.capacity_service_codes`, BR-TEN-1180's `capacity`
    basis): the ruling names them, so a METERED service with an unpriced size
    still refuses exactly as before. A degraded (empty) basis answer is the
    safe direction — it refuses, as yesterday. An asset with NO size is not
    tagged by rating and keeps its named stop.
    """
    refusal = answer.get("refusal")
    if (
        refusal
        and answer.get("refusal_reason") == SIZE_NOT_PRICED
        and _is_capacity_service(service_code)
    ):
        _record_size_not_priced(
            service_code, str(answer.get("code") or ""), str(answer.get("size_class") or "")
        )
        return BASE_NOT_SET_AMOUNT, answer.get("code")
    if refusal and answer.get("not_set"):
        # ── PO ruling 2026-09-30 · NOT DEFINED AND BOUND IS NOT A REFUSAL ────
        # Rating keeps its sentence (its own configuration screens still show
        # it) and flags the three cases the ruling covers — a named code that
        # cannot answer here, no code for this customer type, a code with no
        # amount. Billing answers `(None, code)`, and `_base_charge_for` turns
        # that into `$0.00` and a named warning. The conflicts carry no flag
        # and fall through to the refusal below exactly as before.
        return None, answer.get("code")
    if refusal:
        # ── `DEF-2381` · WHICH KIND OF REFUSAL THIS IS ──────────────────────
        # Four of rating's five refusals are TARIFF faults — two base codes,
        # two bases on one code, an unpriced size, no amount at all — and they
        # keep the reason they have always had. The fifth is a SCOPING fault:
        # the codes are fine and none of them claims this account's customer
        # type. It is repaired in a different place (the code's customer-type
        # list) and it is reported under its own name, because a reason code
        # is the grouping key the S31.2 findings tabs are built on and burying
        # it in `plan_has_no_tariff_for_service` would tell a clerk to go and
        # look at prices that are not wrong.
        #
        # `.get` and not `[...]`: a deployment whose rating half predates this
        # change publishes no discriminator and degrades to the generic reason,
        # which is exactly what it raised yesterday.
        reason = (
            GATHER_NO_BASE_FOR_CUSTOMER_TYPE
            if answer.get("refusal_reason") == "customer_class"
            else GATHER_NO_TARIFF
        )
        if answer.get("per_size") and not answer.get("refusal_reason"):
            # ── `DEF-BIL-9024` · NO SIZE RECORDED, BY ITS OWN NAME ───────────
            # Rating tags an unpriced SIZE (`size_not_priced`) and leaves the
            # one remaining per-size refusal untagged on purpose: the asset has
            # NO size, a named stop. Filed under the tariff reason it sent a
            # clerk to the prices; it is the connection that needs fixing, and
            # `GATHER_SIZE_UNRESOLVED` is its reason, clerk line and Check tag.
            reason = GATHER_SIZE_UNRESOLVED
        raise GatherProblem(reason, refusal, service_code=service_code)
    return _decimal_or_none(answer.get("amount")), answer.get("code")


def version_fields_from(inputs: Any) -> dict[str, Any]:
    """The `TariffConfig` fields that come from the RATE SCHEDULE VERSION — and
    ONLY those.

    ⚠ **EXTRACTED 2026-08-31 SO THERE IS EXACTLY ONE OF IT (CR-052 task 22).**
    Every line below was inside `_tariff_config_for`'s constructor call and is
    unchanged; what is new is that a SECOND caller now needs the same mapping.
    `apps/billing/resolution_switch.py`'s R2 fork prices a bill from the rate
    schedule version the R1–R7 chain resolved rather than the one the bill run
    resolved, so it holds a different `pricing_inputs` dict and must turn it
    into the same fields.

    **A COPY WOULD BE THE `DEF-434` DEFECT ONE LAYER UP.** Rating split
    `pricing_inputs_for_version` out for exactly this reason and said why in its
    own words: *"a copy of it would drift on the first shape that gained a
    column — silently, because both copies would still produce a well-formed
    bill."* The same is true here: the day rating publishes a sixth rate shape,
    one copy would read it and the other would price without it, and both bills
    would look entirely ordinary.

    **WHAT IS DELIBERATELY NOT HERE, because it is not the version's:**
    `base_charge` (a THREE-way precedence over the charge code, the plan and
    this column — `_base_charge_for`, and two of its three inputs are not on a
    `TariffConfig` at all), `size_class`, `jurisdiction_factor`, `base_only`
    and the two `BR-RAT-028` minimums. Those are the account's, the premises'
    and the plan's facts, and a caller substituting a version must keep them.
    """
    capacity = inputs.get("capacity")
    return {
        "model": inputs["model"],
        "billed_unit": inputs["billed_unit"] or "",
        "unit_price": _decimal_or_none(inputs["unit_price"]),
        "tiers": tuple(
            rating_seam.Tier(
                upper=_decimal_or_none(tier["upper"]),
                unit_price=_decimal(tier["unit_price"]),
            )
            for tier in inputs["tiers"]
        ),
        # NO multiplier. PO ruling 2026-08-11: metering applies the meter
        # multiplier and the engine refuses one. Consumption arrives here
        # already post-multiplier.
        #
        # ── The other four rate shapes (2026-08-16) ─────────────────────────
        # `.get` rather than `[...]` for every one of them, and that is the same
        # late-binding posture every other cross-module read in this file uses:
        # a deployment where rating's selector has not yet been updated must
        # degrade to a tariff with no windows — which the engine REFUSES by name
        # — rather than to a KeyError in the middle of a 500-account run.
        "windows": tuple(
            rating_seam.TouWindow(
                label=window["label"],
                unit_price=_decimal(window["unit_price"]),
                # THE UTILITY states which metered register this window is read
                # from, on the S11 rate wizard (BR-RAT-067; PO ruling
                # 2026-08-16 closing OQ-236, verbatim: *"make the rate wizard
                # say which register is which"*). Rating serves the stored
                # answer and billing carries it — neither derives one, and the
                # price-rank resolution this comment used to describe is
                # superseded and deleted. A None here is a window whose register
                # was never stated, and the engine refuses on it BY NAME rather
                # than pricing by position or at 0.00.
                channel=window.get("channel"),
                season=window.get("season"),
                day_type=window.get("day_type") or "weekday",
            )
            for window in inputs.get("windows") or ()
        ),
        "season": inputs.get("season"),
        # 🔒 BR-RAT-034 — the calendar days of the period in each season, as
        # RATING counted them (`selectors._season_days_between`), and every
        # season's own ladder for a `seasonal` schedule. `.get` for the same
        # late-binding reason as every field here: a rating that predates them
        # serves neither, the period prices on ONE season exactly as it did,
        # and a seasonal schedule refuses by name rather than raising mid-run.
        "season_days": tuple(
            rating_seam.SeasonDays(season=share.get("season"), days=int(share["days"]))
            for share in inputs.get("season_days") or ()
        ),
        "season_tiers": tuple(
            rating_seam.SeasonTiers(
                season=ladder["season"],
                tiers=tuple(
                    rating_seam.Tier(
                        upper=_decimal_or_none(tier["upper"]),
                        unit_price=_decimal(tier["unit_price"]),
                    )
                    for tier in ladder["tiers"]
                ),
            )
            for ladder in inputs.get("season_tiers") or ()
        ),
        "capacity": (
            None
            if not capacity
            else rating_seam.CapacityRate(
                unit_label=capacity["unit_label"],
                rate_per_unit=_decimal(capacity["rate_per_unit"]),
            )
        ),
        "energy_rate_per_kwh": _decimal_or_none(inputs.get("energy_rate_per_kwh")),
        "demand_rate_per_kw": _decimal_or_none(inputs.get("demand_rate_per_kw")),
        "ratchet_enabled": bool(inputs.get("ratchet_enabled")),
        "pf_penalty_enabled": bool(inputs.get("pf_penalty_enabled")),
        "percent": _decimal_or_none(inputs.get("percent")),
        "basis_service": inputs.get("basis_service"),
        # CR-130-BRC07 — A PERCENTAGE OF WHAT: 'usage' or 'charge'. `.get` for
        # the same late-binding reason as every other read here, and the plugin
        # refuses a None rather than assuming one, so a rating deployment older
        # than this column degrades to a NAMED refusal on the exception list
        # instead of a silently mis-based sewer line.
        "percent_basis": inputs.get("percent_basis"),
        # DEF-276 — WHICH VERSION PRICED THIS. `pricing_inputs` has served this
        # id since it was written, with the comment *"travels onto the bill line
        # — provable prices"*, and until 2026-08-19 nothing picked it up: the
        # column on `invoice_lines` was NULL on every line ever issued. `.get`
        # for the same late-binding reason as every other read here.
        "version_id": inputs.get("version_id"),
    }


def _tariff_config_for(
    tariff_row: Any,
    service_code: str,
    service_date: date,
    *,
    size_class: str | None = None,
    customer_class: str | None = None,
    jurisdiction_factor: Decimal = Decimal("1"),
    base_only: bool = False,
    carries_service_minimum: bool = True,
    plan_minimum_bill_amount: Any = None,
    size_axis_required: bool = True,
    base_size_counts: "dict[str, int] | None" = None,
) -> Any:
    """The priced-stage input, from RATING's own pricing shape.

    ── `base_size_counts` — THE BASE BY SIZE (PO 2026-10-01) ─────────────────
    For a capacity service whose sizes SUM (solar, battery, storm water,
    broadband, thermal), `{size: count}` of its in-service assets. When the
    base code prices by size, the base is `Σ base(size) × count`
    (`_size_base`) and the usage — priced on the summed capacity — is NOT
    touched. `None` (every other caller) is byte-identical to yesterday.

    Billing does NOT read rating's storage. An earlier cut of this called
    `version_structure`, which is the S9 card's display preview — it returns
    `from_qty`/`to_qty` where the engine wants an upper bound, omits the billed
    unit and base charge (they live on the version row), and does not contain a
    flat rate's price at all, because BR-RAT-032 stores flat as one 0→∞ tier.
    It could never have worked, and only an end-to-end test found it: the
    gather's own tests publish a fake seam, so both halves agreed only in my
    head.

    `pricing_inputs` is rating's answer to "what does the engine need", and it
    is rating's to keep correct. That is the boundary — storage is not an
    interface.

    ── `size_class` — WHICH TIER LADDER (DEF-484, added 2026-08-21) ───────────
    A rate schedule may now carry more than one tier ladder: the NULL group is
    *"every size"* and a `size_class` group is the override r10's 2" water row
    needs (BR-RAT-032 as amended by DEF-433). This hands rating the connection's
    size so it can select one; `None` selects the NULL group, which for every
    version written before DEF-433 is the whole set and therefore today's exact
    answer on every bill this product has issued.

    ⚠ **AND IT IS `None` ON EVERY BILL, BECAUSE NOTHING RECORDS A CONNECTION'S
    SIZE — DEF-514.** The hop is wired so that the day a size exists it travels;
    what does not exist is the fact. So the second half of DEF-484's prevention
    is what does the work today: when the version in force NAMES sizes and no
    size could be resolved, this REFUSES BY NAME rather than billing the base
    ladder to a connection that might be a 2". A refused account is one row on
    the exception screen; a silent fallback is $12/month missing on a document
    that looks entirely ordinary.

    ── `base_only` — THIS CONNECTION'S BASE AND NO USAGE (DEF-990) ───────────
    Set for a tariff that must charge its base charge and price no consumption,
    while OTHER tariffs on the same bill price usage normally. BR-CUS-170 (PO
    2026-08-27) is the case: a master's bill carries the base charge of every
    unit on its premises nobody occupies, beside the common areas it prices in
    full — `$69.60 + $12.00` = **`$81.60`** on BR-MET-101's building.

    ⚠ **IT CHANGES NOTHING ABOUT THE PRICES THIS FUNCTION READS.** The version
    in force, the size ladder, the jurisdiction factor and the base charge are
    resolved by exactly the code above, from exactly the same rows; the flag
    only tells `stages/measure_consumption` not to go looking for a reading on
    this tariff's behalf (it would find another connection's, matched by service
    code, and bill that usage twice — DEF-990's second named obstacle).

    ── `jurisdiction_factor` — R5's surcharge (BR-RAT-102, added 2026-08-21) ──
    Per SERVICE, because §A4 S2 needs it to be: an outside-city electric base of
    $18.50 bills $27.75 while the sewer base beside it stays $8.00. The two-gate
    decision (does the PLAN state a factor · is the PREMISES outside) is taken
    in `_jurisdiction_factor_for` and arrives here as one number, so this
    function still holds no rule — it projects.
    """
    pricing = _resolve("rating", "pricing_inputs")
    if pricing is None:
        raise GatherProblem(
            GATHER_NO_VERSION,
            "rating has not published pricing_inputs, so no tariff can be "
            "resolved at a service date. Nothing is guessed.",
            service_code=service_code,
        )
    span = _SEASON_SPAN.get()
    inputs = _call_pricing_inputs(pricing, tariff_row, service_date, size_class, span=span)
    if inputs is None:
        raise GatherProblem(
            GATHER_NO_VERSION,
            f"service {service_code}: no tariff version is in force on "
            f"{service_date.isoformat()}. BR-RAT-007: a bill prices on the "
            "version in force at the SERVICE date; there is no fallback to "
            "today's prices, because that would silently re-price history.",
            service_code=service_code,
        )
    # ── PO 2026-10-01 · TWO FACTS RATING PUBLISHES ONLY WHEN THEY ARE TRUE ──
    # `versions_in_force`: a legacy overlap, the newest priced (`BR-RAT-1055`,
    # `DEF-RAT-8004` option A) — named on the Check, never a refusal.
    # `minimum_needs_size`: no size was handed in and the version states
    # per-size minimums — no minimum applies (option A of the same day's
    # meter-size ruling); the caller names the unsized meter.
    overlap = inputs.get("versions_in_force") if isinstance(inputs, dict) else None
    if overlap:
        _record_versions_overlap(service_code, service_date, dict(overlap))
    if isinstance(inputs, dict) and inputs.get("minimum_needs_size"):
        _record_minimum_needs_size(service_code)
    # DEF-484 — THE FALLBACK IS A FALLBACK, NOT AN ANSWER.
    #
    # `size_groups` is `[]` for every version in the database today, so this
    # refusal fires on nothing and no bill moves. It fires the moment a utility
    # types a per-size ladder, which is the moment the old behaviour would have
    # started being wrong — and being wrong by exactly the amount the utility
    # typed, on every bill on that schedule, for ever.
    #
    # `.get` and not `[...]`, for the reason every other read in this function
    # gives: a deployment whose rating lane has not landed degrades to today's
    # behaviour rather than raising mid-run.
    # ⚠ **`CR-063` — A CONNECTION WITH NOTHING ON IT HAS NO SIZE TO RESOLVE,
    # AND DEMANDING ONE WOULD TURN THE RULED ZERO INTO AN EXCEPTION ROW.** The
    # refusal below asks *"which of these ladders prices this connection?"*, and
    # for a service billed by a COUNT PER SIZE that question only exists once
    # something is installed: the size belongs to the ITEM (decision log
    # 2026-09-02), the count is 0, and `0 × any price` is `BR-MET-108`'s ruled
    # `$0.00`. `_per_size_configs` passes `size_axis_required=False` for exactly
    # that one case and for nothing else — an item whose size nobody RECORDED is
    # refused there, by name, before this function is reached.
    sized_groups = tuple(inputs.get("size_groups") or ())
    if sized_groups and not size_class and size_axis_required:
        # ── THE SENTENCE A CLERK READS — `DEF-BIL-6760`, 2026-09-25 ─────────
        # ⚠ **IT USED TO BE 72 WORDS, IT CITED A DEFECT CLOSED A MONTH
        # EARLIER, AND IT SENT THE PRODUCT OWNER TO THE WRONG SCREEN.** It
        # read *"this connection's size could not be resolved — nothing in
        # this product records one yet (DEF-514)"*, followed by forty words
        # arguing why refusing beats the every-size ladder. Three faults, all
        # of them on a clerk's screen, because `final_bill.preview_final_bill`
        # puts this string on `priced_unavailable.detail` and the move-out
        # wizard renders it verbatim:
        #
        #   1. **IT WAS FALSE.** `DEF-514` is `status: fixed`, closed
        #      2026-08-27 at `2.79.5` — `assets.Asset.size_class`, its two
        #      publications and `metering.connection_size_for` all landed, and
        #      `DEF-1900` added the screen control and the import column at
        #      `2.79.7`. The product records a connection size and has done
        #      for a month. Hard-won law 1: a sentence describing an absence
        #      outlives the absence exactly as easily as one describing a
        #      guarantee. **Measured cost:** the PO read it, opened the asset,
        #      found `W-58` recorded on it, and reported the product broken in
        #      a way it is not.
        #   2. **B14 rule 32** — no rule id or internal code in clerk-facing
        #      copy. `final_bill`'s own neighbours on that endpoint already
        #      say so in terms: *"THE RULE ID AND THE MODULE PATH GO IN
        #      `br_ref`, NEVER IN `detail`"*.
        #   3. **B14 rule 33** — RATIONALE IS ZERO WORDS ON SCREEN. Why a
        #      refusal beats a guessed ladder belongs in the code, which is
        #      where it now is: the paragraph above this one.
        #
        # What replaces it is the FACT, the sizes (which the person fixing it
        # needs, and which is why the list survived), and the WAY OUT. The
        # `reason` code and `service_code` are UNCHANGED, because the screen
        # and `resolution_switch` key on those and this is a copy fix.
        #
        # ⚠ **IT SAYS *no size for this connection* RATHER THAN NAMING WHICH
        # OF TWO STATES THIS IS, AND THAT IS DELIBERATE.** `_connection_size_
        # for` answers `None` both for a connection that exists with no size
        # recorded and for a unit with **no service point for this service at
        # all** — and the second is the state the PO's account is actually in
        # (`DEF-BIL-6759`, where 19 of 75 accounts on a seeded fire tenant
        # refuse and every one of them has no fire connection). Telling those
        # two apart needs a second read and a decision about what the no-
        # connection case should COST, which is rating math and is not ruled.
        # Writing a sentence that picks one of them would be the same defect
        # this comment is about, one month newer.
        raise GatherProblem(
            GATHER_SIZE_UNRESOLVED,
            f"service {service_code}: no size for this connection. "
            f"The schedule prices each size: {', '.join(sized_groups)}. "
            "Check the connection on this unit.",
            service_code=service_code,
        )
    # ── BR-RAT-088 · WHAT THE CHARGE CODE SAYS THIS SERVICE'S BASE IS ───────
    # `DEF-2823`. Read HERE and not in `_base_charge_for` because this is where
    # the three narrowing facts already are — the service, the connection size
    # and the account's customer class — and a second place that re-derives any
    # of them is a second narrowing that can disagree with this one.
    #
    # A refusal travels back as a SENTENCE and becomes one account's exception
    # (BR-BIL-055); an unpublished seam degrades to *the charge code says
    # nothing*, which is the pre-ruling behaviour exactly.
    # ⚠ **THE CODE'S NAME IS NO LONGER CARRIED INTO THE REFUSAL — `DEF-CUS-6550`.**
    # `_base_charge_for` took a `code_label=` for one purpose: to print *"charge
    # code BASE-E-COM says 120.0000"* inside a 100-word sentence on a clerk's
    # screen. B14 rule 33 cut that sentence to the state and the repair, which
    # left the parameter reading nothing, and a parameter nothing reads is
    # hard-won law 1 in miniature — so it is GONE rather than kept "in case".
    # A clerk sees which code owns the base on Charge codes, one click from the
    # repair. The seam still ANSWERS the code and this caller ignores it.
    # ── `BR-RAT-1025` · THE SCHEDULE'S OWN BINDING, CARRIED (`DEF-RAT-5782`) ─
    # `inputs` is rating's projection of the version `BR-RAT-007` resolved for
    # this service and date, so the binding arrives with the rates it belongs
    # to and billing never has to look a version up for itself. `.get` and not
    # `[...]`: a deployment whose rating half predates the key publishes none,
    # and `None` is exactly *this schedule names nothing* — today's behaviour
    # on every tenant, because every version written before `rating/0037`
    # stores NULL.
    # ── PO 2026-10-01 · A SUMMING CAPACITY SERVICE'S BASE, LOOKED UP BY SIZE ─
    # `None` from `_size_base` means the base code does not price by size (a
    # flat code, or none at all), and the ONE lookup below answers exactly as
    # it did yesterday — a flat solar base is not multiplied by panel count.
    sized_base = (
        _size_base(
            service_code,
            base_size_counts,
            customer_class=customer_class,
            named_code=inputs.get("base_charge_code"),
            on_date=service_date,
        )
        if base_size_counts
        else None
    )
    if sized_base is not None:
        base_charge, code_label = sized_base
    else:
        code_amount, code_label = _base_charge_code_for(
            service_code,
            customer_class=customer_class,
            size_class=size_class,
            named_code=inputs.get("base_charge_code"),
            on_date=service_date,
        )
        base_charge = _base_charge_for(service_code, code_base=code_amount)
    entry = _trace(service_code)
    if entry is not None:
        # VALUES at gather, written onto the line at stage 6. The first config
        # of a service states the code and version; per-size configs agree.
        entry.setdefault("base_code", code_label)
        entry.setdefault("rate_schedule_version_id", inputs.get("version_id"))
        entry.setdefault("customer_type", customer_class)
    return rating_seam.TariffConfig(
        service=service_code,
        # ── `DEF-BIL-7170` · ONE SOURCE, AND THE OTHER TWO ARE NOT PASSED ──
        # PO 2026-09-28: *"we will never take default value from plan $8.0 -
        # that is retired"*. This call used to hand `_base_charge_for` three
        # figures — the plan's `plan_base`, the rate schedule version's
        # `inputs["base_charge"]` and the charge code's — and the function
        # refused the bill when the code disagreed with either of the other
        # two. Both of those columns are RETIRED, so a figure on them is a
        # migration artefact and may not stop a bill.
        #
        # ⚠ **THE OTHER TWO ARE NOT MERELY UNUSED HERE, THEY ARE GONE FROM THE
        # SIGNATURE**, and `code_base` is KEYWORD-ONLY so that a stale
        # positional call fails loudly rather than passing the plan's figure
        # where the charge code's belongs.
        #
        # ⚠ **AND `_tariff_config_for`'s OWN `plan_base=` WENT WITH IT.** Its
        # only reader was this call, so keeping it would have left four call
        # sites threading the retired column into a function that does nothing
        # with it — a parameter nothing reads, which is what this file already
        # deleted `code_label=` for. The plan's column is still WRITTEN, still
        # served and still SHOWN; it is simply no longer carried down the path
        # that decides money.
        base_charge=base_charge,
        # `DEF-BIL-8316` — the code's NAME, carried for the screen beside the
        # figure it produced. A label only: nothing prices from it.
        base_charge_code=code_label,
        # ── WHICH LADDER PRICED THIS, RECORDED (DEF-2823) ──────────────────
        # R3's own answer, carried so the pricing shadow can compare R3 and R4
        # SEPARATELY. While the base was one fused figure neither step could
        # ever satisfy the cutover's rule that a step switches only when its own
        # class is at zero — 47 accounts read `cannot evaluate` at both.
        size_class=size_class,
        # ⚠ DEF-466 — R5 REACHES A BILL. Until 2026-08-21 this field was left at
        # its `Decimal("1")` default on every TariffConfig this function has ever
        # built, so `price_usage` multiplied every base line and every usage line
        # by the identity and the whole of R5 was dead code executing on every
        # line of every bill. It is resolved per SERVICE (§A4 S2: the sewer base
        # is flat everywhere while electric moves) by `_jurisdiction_factor_for`,
        # which is where BR-RAT-102's two gates live.
        jurisdiction_factor=jurisdiction_factor,
        # DEF-990 — see the parameter's own paragraph above. False on every
        # tariff every other caller builds, so every bill this product has
        # issued and every ❄️ B5 figure prices byte for byte.
        base_only=base_only,
        # ── BR-RAT-028 · A PROJECTION AND NOT A DECISION ───────────────────
        # Both figures are carried across UNCHANGED. There is no precedence to
        # apply and none is invented here: unlike `base_charge`, which exists on
        # three rows and therefore needed `_base_charge_for` to say which one
        # wins, each of these has exactly ONE stored home.
        #
        # ⚠ **MODE A'S HOME MOVED ON 2026-09-10 — PO ruling, migrations
        # `rating/0030` + `0031`.** Verbatim: *"set it in rates and use it in
        # plans - thats it - this is rule"*. It was `plan_services
        # .minimum_amount`, the plan's own column, published by
        # `plan_rate_schedules`. It is now the RATE SCHEDULE VERSION's
        # `tariff_versions.minimum_bill`, which arrives on `inputs` from
        # `rating.selectors.pricing_inputs` — the figure this comment used to
        # say was *"REPORTED as a defect and left unread"* (`DEF-2446`, whose
        # objection was that *"nothing signed says what a schedule that ALSO
        # carries one means"*). **The ruling above is that missing signature,
        # and it removes the ambiguity rather than resolving it:** there is no
        # longer a plan column to disagree with, so no precedence exists to get
        # wrong. `DEF-2446` is closed by it. ⚠ **AND IT MOVED AGAIN ON
        # 2026-10-01: the version's scalar is no longer billed; the figure is
        # the `rate_size_rows` minimum for the connection's size** (below).
        #
        # ⚠ **THE ARITHMETIC DID NOT MOVE AND MUST NOT.** `BR-RAT-028` mode (A)
        # still applies before the plan floor of mode (B); `GT-13` and `GT-19`
        # state that arithmetic and neither names a source, which is why the PO
        # ruled this an AMENDMENT to the rule rather than a finance re-sign.
        # A lane that "simplifies" this to one minimum has deleted mode (A).
        #
        # ⚠ **IT IS A VERSION FACT NOW, SO IT IS RESOLVED AT THE SERVICE DATE.**
        # The plan's column applied to every version; this one belongs to the
        # version `BR-RAT-007` resolved. `rating/0030` therefore wrote the moved
        # figure onto EVERY version of the attached tariff, so a back-dated
        # re-bill prices exactly what it priced before.
        # ⚠ **`carries_service_minimum` IS NOT A TIDY-UP OF THE OLD PARAMETER —
        # IT IS THE HALF THAT KEEPS A PER-SIZE BILL FROM BEING TOPPED UP ONCE
        # PER LINE.** The plan's column was read by the CALLER, which passed it
        # only on the first size group (`_tariff_configs_for_sizes`: *"the
        # standing charge and the minimum ride on a group whose size is
        # known"*). The version's column is read HERE, and `inputs` is built per
        # size group — so reading it unconditionally would put a floor on every
        # group and a warehouse with a 6" and two 2" fire lines would be topped
        # up three times. The caller says WHETHER this config may carry it; the
        # figure itself comes from the version. Renamed rather than kept, so a
        # caller still passing `minimum_amount=` fails loudly instead of having
        # its figure silently ignored.
        #
        # ⚠ **THE FIGURE IS THE SIZE'S SINCE 2026-10-01 (`DEF-RAT-8737`, PO
        # option A: *"A · Minimum per size - this is correct"*).** This
        # paragraph read *"THE PER-SIZE FLOORS ON `size_rows` ARE STILL NOT
        # READ, AND THAT IS TODAY'S BEHAVIOUR EXACTLY. `pricing_inputs`
        # publishes the version's SCALAR `minimum_bill`"* until that ruling.
        # `pricing_inputs` now publishes, under the SAME key, the
        # `rate_size_rows` minimum for the `size_class` this call already hands
        # it (`rating.selectors._size_minimum`) — so every path that prices
        # through here (the bulk run, every one-time kind, mid-period, the
        # corrections) gets it from the one version lookup it already made.
        # The version's own `minimum_bill` is no longer billed anywhere.
        # Worked: Water — Residential at 1 kgal, 5/8" `$12.41` → **$15.00**
        # under a 5/8" minimum of `$15.00`; 2" `$32.41` → **$40.00** under
        # `$40.00`; a size stating *No minimum* stays `$12.41`.
        #
        # ⚠ **ON A CAPACITY UNIT WITH SEVERAL SIZES, THE FLOOR IS THE FIRST
        # GROUP'S SIZE'S** — the group `carries_service_minimum` already picks
        # (`_tariff_configs_for_sizes`, sorted, unsized last). A judgment
        # recorded in the decision log of 2026-10-01; no seeded capacity
        # schedule states a minimum today, so no bill moves on it.
        minimum_amount=(
            _decimal_or_none(inputs.get("minimum_bill")) if carries_service_minimum else None
        ),
        plan_minimum_bill_amount=_decimal_or_none(plan_minimum_bill_amount),
        # ── THE VERSION'S OWN FIELDS, THROUGH THE ONE MAPPING ──────────────
        # `version_fields_from` is shared with `resolution_switch`'s R2 fork,
        # which prices from the version the R1–R7 chain resolved. A second
        # copy of this projection is `DEF-434`'s defect one layer up: it
        # would drift on the first rate shape that gained a column, silently,
        # because both copies would still build a well-formed tariff.
        **version_fields_from(inputs),
        # 🔒 BR-RAT-034 — the days rating counted `season_days` over, carried
        # as IDENTITY so the R2 fork can ask for the same days against the
        # version it swaps in. Nothing prices from it.
        season_span=span,
    )


def _size_base(
    service_code: str,
    counts: "dict[str, int]",
    *,
    customer_class: str | None,
    named_code: str | None,
    on_date: date | None = None,
) -> "tuple[Decimal, str | None] | None":
    """🔒 rating math · HUMAN-REVIEW-PENDING (*"2026-10-01 · CAPACITY BASE BY
    SIZE"* in `12-governance/09-human-review-ledger.md`).

    **`Σ base(size) × count` for a SUMMING capacity service, or `None` when its
    base code does not price by size.** PO 2026-10-01, verbatim: *"in case of
    all capacity based base rates for example ofr base charges for Trash, Fire,
    Battery, Solar - all capacity based - based rates should be search based on
    sizes dueing billing"*.

    Worked: a unit with 2 panels of size A and 1 of size B, the base code
    pricing A at `$2.00` and B at `$3.00` → `2 × 2.00 + 1 × 3.00 = $7.00`. The
    kW usage line is priced on the summed capacity exactly as before — this
    function moves the BASE only.

    A size the code does not price bills `$0.00` for that size with the named
    warning (`_interpret_base_answer`), and the rest still bill. A conflict on
    the code (an amount AND sizes) is not `per_size` and falls through to the
    one-lookup path, which refuses it as it always did.

    **A FLAT CODE ANSWERS `None` HERE, DELIBERATELY** — a lane judgment,
    recorded in the decision log: the ruling is about rates *"search[ed] based
    on sizes"*; a flat solar base names no size, and multiplying it by the
    panel count would move every summing-service bill a tenant already sends
    with nothing in the ruling asking for it. Trash and fire are unchanged:
    their base was ruled per ASSET on 2026-09-30 (option B).
    """
    components: list[dict[str, Any]] = []
    total = Decimal("0")
    code: str | None = None
    for size in sorted(counts):
        answer = _base_answer(
            service_code,
            customer_class=customer_class,
            size_class=size,
            named_code=named_code,
            on_date=on_date,
        )
        if answer is None or not answer.get("per_size"):
            return None
        amount, code_here = _interpret_base_answer(service_code, answer)
        each = _base_charge_for(service_code, code_base=amount)
        count = int(counts[size] or 0)
        total += each * count
        code = code or code_here
        components.append(
            {
                "size": size,
                "size_label": _size_label_for(service_code, size),
                "count": count,
                "base_each": _money_text(each),
                "base_total": _money_text(each * count),
                "base_priced": answer.get("refusal_reason") != SIZE_NOT_PRICED,
                "price_each": None,
            }
        )
    entry = _trace(service_code)
    if entry is not None:
        entry["sizes"] = components
        entry["base_by_size"] = True
    return total, code


def _base_size_counts_for(unit_id: Any, service_code: str, service_date: date) -> Any:
    """`{size: count}` for a SUMMING capacity service's in-service assets, or
    `None` — metering's answer (`billable_base_size_counts`), never decided
    here. `None` also while the seam is unpublished: the base is then looked
    up once, exactly as before."""
    resolver = _resolve("metering", "billable_base_size_counts")
    if resolver is None:
        return None
    counts = resolver(unit_id, service_code, service_date)
    return dict(counts) if counts else None


def _call_pricing_inputs(
    resolver: Any,
    tariff_row: Any,
    service_date: date,
    size_class: str | None,
    *,
    span: tuple[date, date] | None = None,
) -> Any:
    """Call rating's projection WITH the connection size, and without it if the
    deployment's rating half is older (DEF-484).

    The same shape and the same reason as `_call_plan_taxes` below: the seam's
    signature is another module's contract, `size_class` arrived on it with
    DEF-433 on 2026-08-21, and a deployment where that lane has not landed must
    degrade to the previous behaviour rather than raise a `TypeError` in the
    middle of a 500-account run.

    ⚠ **AND THE `None` CASE IS THE TWO-ARGUMENT CALL, DELIBERATELY.** A size of
    `None` and no size at all select the same ladder, so passing `None`
    positionally would buy nothing and would make a call on a bill with no size
    depend on a signature that only landed that week. Byte-identical is the
    point.

    ⚠ **THIS PARAGRAPH SAID *"every call — every bill, because `DEF-514` means
    the size is always `None`"* UNTIL 2026-09-25, AND IT HAD BEEN FALSE FOR A
    MONTH (`DEF-BIL-6760`, the same claim `_connection_size_for` below carried
    and the same repair).** `DEF-514` was CLOSED on 2026-08-27 at `2.79.5`:
    `assets.Asset.size_class` is a real column, `metering.connection_size_for`
    answers from it, and `DEF-1900` added the screen control and the import
    column at `2.79.7`. **Measured by lane FIRESIZE on a seeded water + sewer + fire
    tenant on PostgreSQL 16, 2026-09-25, and recorded in
    `_connection_size_for`'s docstring below: of 51 fire service points a real
    ratified size comes back — `FL-4`, `FL-6`, `FL-8` — on every one that has a
    fire line on it. The count is that lane's; what is re-checked here is the
    part this paragraph turns on — `DEF-514` reads `status: fixed` in the
    register, `assets.Asset.size_class` is a declared column and
    `metering.selectors.connection_size_for` is a defined, published seam.** So the three-argument call below is the ORDINARY path today and the
    two-argument one is the exception, which is the reverse of what this
    docstring described. **What it cost:** the sibling copy of this claim sent
    a lane and then the Product Owner to the wrong screen over a size the
    product had recorded all along — hard-won law 1, which is why the sentence
    is corrected with its date rather than quietly deleted.

    ⚠ **AND IT ASKS THE SIGNATURE RATHER THAN CATCHING `TypeError`, WHICH IS
    WHERE THIS DEPARTS FROM `_call_plan_taxes`.** That function retries on a
    `TypeError` — fine for a tax it can only ever DROP, and wrong here. A
    `TypeError` raised *inside* rating while it resolved a version would be
    indistinguishable from an arity mismatch, and the retry would then pick the
    every-size ladder and bill it: the silent wrong ladder this whole commit
    exists to stop, reintroduced by the compatibility shim. So the arity is
    ASKED, once, and a genuine `TypeError` propagates.
    """
    # ⚠ **THE PROBE BELOW IS A FALLBACK AND NO LONGER THE DECISION
    # (`DEF-2387`).** It used to be the whole of it, and a wrapper with a
    # `(*args, **kwargs)` signature — which is what `seam_batch.wrap` returned
    # inside every prepare pass — answered *"rating cannot take a size"* and the
    # size was dropped from every priced bill in a run. Passing the size and
    # catching the `TypeError` asks the CALLABLE rather than a description of
    # it, so a wrapper cannot answer on rating's behalf. The probe is kept as
    # the first gate only because a `TypeError` raised INSIDE rating would
    # otherwise be mistaken for a signature mismatch.
    # 🔒 BR-RAT-034 (built 2026-10-01) — the served span, as keywords, ONLY to
    # a rating that NAMES them. Asked by name rather than by count, because a
    # fake seam with a `size_class` third parameter is not a rating that can
    # count season days. A rating without them prices the period on ONE
    # season — yesterday's answer — never a `TypeError` mid-run.
    extra: dict[str, Any] = {}
    if span is not None:
        try:
            names = signature(resolver).parameters
        except (TypeError, ValueError):  # pragma: no cover — unintrospectable callable
            names = {}
        if "period_start" in names and "period_end" in names:
            extra = {"period_start": span[0], "period_end": span[1]}
    if size_class is None:
        return resolver(tariff_row, service_date, **extra)
    try:
        accepts_size = len(signature(resolver).parameters) >= 3
    except (TypeError, ValueError):  # pragma: no cover — unintrospectable callable
        accepts_size = True  # assume the current contract; a real mismatch raises
    if not accepts_size:  # pragma: no cover — pre-DEF-433 rating only
        return resolver(tariff_row, service_date, **extra)
    try:
        return resolver(tariff_row, service_date, size_class, **extra)
    except TypeError:  # pragma: no cover — a signature this probe misread
        # The size could not be passed. Falling back is today's behaviour and
        # is the SAFE direction only because the caller REFUSES by name when the
        # version names sizes and none was resolved — so a bill is never quietly
        # priced on the every-size ladder for a size the schedule does name.
        return resolver(tariff_row, service_date, **extra)


def _connection_size_for(unit_id: Any, service_code: str) -> str | None:
    """This connection's `meter_size_classes.code`, or None while nothing
    records one.

    ⚠⚠ **THE FOUR PARAGRAPHS THIS DOCSTRING CARRIED HERE UNTIL 2026-09-25 SAID
    THE SIZE DOES NOT EXIST, AND THEY HAD BEEN WRONG FOR A MONTH —
    `DEF-BIL-6760`.** They read *"IT IS `None` FOR EVERY ACCOUNT OF EVERY
    TENANT … `assets.Asset` carries no size column … this is wired to a seam
    that does not exist yet"*. **`DEF-514` was CLOSED on 2026-08-27 at
    `2.79.5`**: `assets.Asset.size_class` is a real column (`assets/0010`,
    `BR-AST-500`), `assets.selectors.assets_on_unit` publishes it,
    `metering.selectors.connection_size_for` answers from it, and `DEF-1900`
    added the screen control and the meters-import column at `2.79.7`.
    **Measured on a seeded water+sewer+fire tenant on PostgreSQL 16, 2026-09-25:
    of 51 fire service points, this call answers a real ratified size — `FL-4`,
    `FL-6`, `FL-8` — on every one that has a fire line on it.** It is not
    `None` for every account of every tenant and has not been since August.

    ⚠ **IT COST A ROUND TRIP THE DAY IT WAS READ.** A lane tracing a fire
    refusal took this paragraph at its word, concluded that the `W-58` a clerk
    could see on the asset screen *"comes from somewhere else"* and that a
    screen showing a size billing cannot read was its own defect. It is the
    same column. Hard-won law 1: a sentence describing an absence outlives the
    absence exactly as easily as one describing a guarantee, and a docstring is
    where the next reader looks first.

    **WHAT IS STILL TRUE, AND IT IS THE PART WORTH KEEPING.** `None` is a real
    answer and is never a guess. It means *"no size is recorded for this
    connection"* — which since `DEF-514` closed is a DATA state a human can
    fix. `_resolve` still returns `None` for an unpublished seam, so a
    deployment whose metering lane has not landed degrades to today's
    behaviour rather than raising mid-run.

    ⚠ **AND `None` HAS A SECOND MEANING THE CALLER CANNOT TELL APART:
    `metering.connection_size_for` ALSO ANSWERS `None` WHEN THE UNIT HAS NO
    SERVICE POINT FOR THIS SERVICE AT ALL** — there is no connection here, so
    there is no size to record. On a schedule that names sizes the refusal
    below fires on both, and on the same sentence. That is `DEF-BIL-6759`,
    where a plan pricing fire on a unit with no fire connection refuses the
    WHOLE account: 19 of 75 accounts on the seeded fire tenant, and every one
    of the 19 has no fire connection while all 36 that have one price cleanly.
    **What a service billed by a COUNT should charge where there is no
    connection at all is NOT RULED** — its three neighbours (`OQ-670`,
    `BR-MET-108`, `BR-BIL-300` edge 3) all answer `$0.00` and none of them
    names this case — so nothing is chosen here.

    **The HOP is proved and the SOURCE now exists:**
    `tests/test_def_484_size_and_jurisdiction.py` publishes the seam and
    asserts a 2" ladder reaches the priced bill.

    BY UNIT AND SERVICE, because a house on water + electric has two connections
    and they need not be the same size — a per-account answer could only ever be
    one of them, and the per-size ladder is per SCHEDULE, which is per service.
    """
    resolver = _resolve("metering", "connection_size_for")
    if resolver is None:
        return None
    size = resolver(unit_id, service_code)
    return (str(size).strip() or None) if size else None


def _size_groups_for(unit_id: Any, service_code: str, service_date: date) -> Any:
    """The per-size bill lines this connection owes, or `None` for *do not
    group* — `CR-063` C3/C5, decision log 2026-09-02.

    ⚠ **THE SEAM ANSWERS THE MODEL QUESTION, NOT THIS FILE.**
    `metering.selectors.billable_size_groups` returns a map only for a service
    the tenant has declared unmetered whose sizes do NOT sum and which has a
    ratified ladder — trash and fire today — and `None` for everything else.
    Deciding it here would put a second, drifting copy of `BR-TEN-171`'s
    arithmetic in billing, and the wrong answer costs money in both directions:
    grouping a METERED service would price ONE water reading on two size lines
    and double the bill, and grouping a SUMMING one would bill three solar
    panels separately instead of as one 14 kW array.

    An unpublished seam answers `None`, which is today's behaviour on every
    bill — the same late-binding posture `_connection_size_for` and
    `_premises_geography` take, and the safe direction here: a service that
    would have been grouped is billed exactly as it is billed now.
    """
    resolver = _resolve("metering", "billable_size_groups")
    if resolver is None:
        return None
    groups = resolver(unit_id, service_code, service_date)
    return None if groups is None else dict(groups)


def _size_label_for(service_code: str, size_class: str | None) -> str | None:
    """`BR-TEN-171`'s ratified NAME for a size class, for the line a customer
    reads — `CR-063` C5.

    Two fire lines on one document must be tellable apart: without a name both
    read *"fire usage"* and nothing distinguishes the `$60.00` 6" line from the
    `$50.00` pair of hydrants. It changes a DESCRIPTION and never an amount.
    """
    if not size_class:
        return None
    resolver = _resolve("metering", "service_size_class_labels")
    if resolver is None:
        return None
    return (resolver(service_code) or {}).get(size_class)


def _per_size_configs(
    row: Any,
    service_code: str,
    service_date: date,
    size_groups: "dict[str | None, int]",
    *,
    customer_class: str | None,
    jurisdiction: dict[str, Any],
    premises: dict[str, Any],
) -> "list[Any]":
    """ONE `TariffConfig` per size present on this connection — `CR-063` C5.
    🔒 rating math. HUMAN-REVIEW-PENDING.

    **Worked, on a fire property with a 6" line and two 2" lines:**
    `{"FL-6": 1, "FL-2": 2}` becomes two configs, priced from the same schedule
    at the tier group each size names — `1 × $60.00` and `2 × $12.00`,
    **`$84.00` on two lines**. (It was `CR-063`'s warehouse at `$110.00` until
    the PO withdrew the private hydrant on 2026-09-03; that warehouse is now one
    `FL-6` and one line.) The counts
    themselves never travel on a tariff; `measure_consumption` pairs each config
    with its own count off the reading, where the tariff's billed unit is in
    hand (rule 3).

    ⚠ **THE BASE CHARGE IS PER ASSET — PO ruling 2026-09-30, option B,
    verbatim: *"B. Base per cart: 2 × ($15.00 + $3.00) = $36.00"*** (was
    `$33.00`: 2 × $15.00 + ONE $3.00). Every asset is its own connection, as
    the same day's metered ruling made every meter one. **SUPERSEDES** this
    docstring's 2026-09-02 judgment that *"the base charge rides on the first
    group only"* because *"the warehouse has ONE fire connection"*.

    **HOW, AND WHY THIS WAY — the smallest change that is exact.** Each size
    group's config carries `base_charge × count` (the group's own size base,
    times the assets of that size). The alternative — a base QUANTITY on the
    config that `rating/pricing/stages/price_usage._base_lines` multiplies —
    touches the 🔒 engine's base stage, which every ❄️ golden figure runs
    through, for the same arithmetic: proration and the jurisdiction factor are
    both multiplications, so `(base × n) × factor × jf` is exactly `n × (base ×
    factor × jf)` before the ONE rounding at finalization (BR-RAT-003). What it
    costs: the document prints ONE base line PER SERVICE — PO 2026-09-30,
    *"per service"*: every group's `base × count` is summed onto the first
    group — at the service total (`trash base charge 6.00`), not `2 × 3.00`.
    ⚠ This read *"The count and sizes are NOT yet written into that line's
    quantity or wording"* until 2026-09-30. They are now: after the engine,
    `counted_service_line` (called by `runs.price_account`) joins these configs'
    usage lines and this base into ONE line per service whose quantity is the
    count and whose wording names the sizes (`DEF-BIL-8151`) — 2 carts = one
    `$36.00` line. This function still emits one config per size; the join is
    layout and moves no figure. **Fire's `$84.00`
    worked figure (`CR-063`) does NOT move**: build plan R4 (merged) found
    fire's base seeded at `$0.00`, and `n × $0.00` is `$0.00`. It would move
    only for a tenant that sets a non-zero fire base — by that base once per
    fire line — which is exactly the ruling.

    ⚠ **AN EMPTY MAP IS NOW NOT IN SERVICE — NO CONFIG, NO LINE, NO BASE.** PO
    2026-09-30: *no asset = not in service*. It answered one config with no
    size and the service's base until this ruling (`BR-MET-108`'s ruled zero,
    which put a `$0.00` line AND the standing charge on the document); the
    caller now records the service as not in service instead.

    ⚠ **AN UNRECORDED SIZE IS ITS OWN GROUP, LAST, AND `_tariff_config_for`
    DECIDES WHETHER THAT REFUSES.** The `None` key is an item somebody installed
    and nobody typed a size for. The ruling says *"A size nobody recorded is
    still a refusal, not a zero"* — and the refusal that enforces it already
    exists and asks the only question that matters: **does this schedule price
    sizes differently?** (`sized_groups and not size_class`, `DEF-484`).

      * **Fire's schedule names six bands** (seven until the PO withdrew the
        private hydrant on 2026-09-03), so the unsized group refuses the
        account by name. Pricing the rest and skipping it would bill a 6" line
        at nothing on a document that foots and prints.
      * **Trash's schedule prices every size at one rate** (`$15.00` per cart),
        so nothing refuses and the unsized carts bill at that rate. Refusing
        there would stop a bill for want of a fact that cannot change a single
        figure on it — a widening of refusals with no money behind it, on the
        one capacity service a real utility is already running.

    Writing a second refusal here would have made that distinction invisible and
    would have refused trash. It is deliberately NOT written.

    ⚠ **AND THE UNSIZED GROUP SORTS LAST**, so the standing charge and the
    minimum ride on a group whose size is known whenever one exists.

    ⚠ **AN EMPTY MAP PRODUCES NO CONFIG (2026-09-30, see above) — AND STILL
    NEVER A REFUSAL.** This paragraph read *"AN EMPTY MAP STILL PRODUCES ONE
    CONFIG"* (`BR-MET-108`'s ruled `$0.00` line) until the PO ruled that no
    asset is not in service. What it guarded is unchanged: an empty capacity
    unit must not become an exception row, and it does not — it becomes a
    service the clerk's review list names.
    """
    configs = []
    ordered = sorted(size_groups, key=lambda code: (code is None, code or ""))
    for index, size_class in enumerate(ordered):
        config = _tariff_config_for(
            row["tariff"],
            service_code,
            service_date,
            size_class=size_class,
            customer_class=customer_class,
            jurisdiction_factor=_jurisdiction_factor_for(
                service_code, jurisdiction=jurisdiction, premises=premises
            ),
            carries_service_minimum=index == 0,
            plan_minimum_bill_amount=row.get("plan_minimum_bill_amount"),
        )
        # ── PO 2026-10-01 · THE TRACE: this size, its count, its base each ──
        # Recorded BEFORE the base is multiplied and folded onto the first
        # group below, because after that the per-size figure no longer exists
        # anywhere. VALUES, never a reference to a `charge_code_amounts` row.
        count = int(size_groups[size_class] or 0)
        entry = _trace(service_code)
        if entry is not None:
            entry.setdefault("sizes", []).append(
                {
                    "size": size_class,
                    "size_label": _size_label_for(service_code, size_class),
                    "count": count,
                    "base_each": _money_text(config.base_charge),
                    "base_total": _money_text(
                        None if config.base_charge is None else config.base_charge * count
                    ),
                    "base_priced": not _size_was_unpriced(service_code, size_class),
                    "price_each": _usage_price_of(config),
                }
            )
        if config.base_charge is not None:
            # 2026-09-30, option B — the base is per ASSET: this size's base
            # times the assets of this size. `None` stays `None` (no base).
            config = replace(
                config, base_charge=config.base_charge * int(size_groups[size_class] or 0)
            )
        # PO 2026-09-30 (*"SIX ANSWERS"*, (5)): ONE base line PER SERVICE. So
        # every group's base is summed onto the FIRST group and the later
        # groups state none — the amount is unchanged, the layout is one line.
        if configs and config.base_charge is not None:
            first = configs[0]
            configs[0] = replace(
                first,
                base_charge=(first.base_charge or Decimal("0")) + config.base_charge,
            )
            config = replace(config, base_charge=None)
        configs.append(
            replace(
                config,
                size_label=_size_label_for(service_code, size_class),
                per_size_line=True,
            )
        )
    return configs


def _plan_jurisdiction(plan_id: Any) -> dict[str, Any]:
    """BR-RAT-102's two stored facts for THIS plan, or "this plan does not
    surcharge" while rating has not published them.

    An unpublished seam yields *no factor*, which is today's behaviour on every
    bill and is the SAFE direction here — the opposite of `_taxes_for`'s, and it
    is worth saying why. Losing this fact removes a surcharge, so the customer
    is charged the un-uplifted price the utility could always have charged;
    inventing one would ADD money to a bill on a fact nobody supplied.
    Under-charging is a support call; over-charging is a refund and a regulator
    (the same asymmetry DEF-273 is decided on).
    """
    resolver = _resolve("rating", "plan_jurisdiction_pricing")
    if resolver is None:
        return {}
    return resolver(plan_id) or {}


def _jurisdiction_factor_for(
    service_code: str,
    *,
    jurisdiction: dict[str, Any],
    premises: dict[str, Any],
) -> Decimal:
    """BR-RAT-102's TWO GATES: the plan states the factor, the premises states
    which side of the line it is on. R5, for one service.

    PO verbatim (2026-08-21, closing `OQ-308`): *"We can have it on plan itself -
    Plan will decide whether to apply and then how much"*, over BR-RAT-101's
    *"On premises we will add this flag and during billing we will consider
    Account -> Unit -> Premises to consider it"*. A line is surcharged only when
    **both** gates open.

        plan states no factor    -> 1, and the premises is never consulted
        premises inside the city -> 1
        service exempt           -> 1   (§A4 S2: sewer is "flat everywhere")
        premises outside         -> the plan's factor

    ⚠ **AND THE FOURTH CASE STOPS THE BILL.** `premises.inside_city_limits` is
    THREE-STATE: `True` inside, `False` outside, `None` **nobody recorded it**.
    A plan that states a factor over a premises whose flag is `None` refuses
    here, by name, naming the premises and what to fix — because the factor
    multiplies EVERY base and EVERY usage line, so a guess is a wrong bill and
    not a partial one, and either default is a silent pricing decision taken on
    data nobody entered. Assuming *inside* under-charges a customer the utility
    may be entitled to surcharge; assuming *outside* over-charges one who never
    agreed to it. `rating.resolution.money_factor` refuses on exactly this, in
    the same words, and BR-RAT-102 carries the refusal into the rule.

    **It refuses ONE ACCOUNT, never the run.** `GatherProblem` is caught per
    account in `runs.prepare_run`, which records it in `blocked` and moves on to
    the next account (BR-BIL-055: a break never blocks the run), so the clerk
    sees one named row on the S31.2 exception tab beside every other unbillable
    account and the other 499 bills are drafted.

    ⚠ **THIS PARAGRAPH SAID "EVERY SEEDED PREMISES IS `None` TODAY AND NOT ONE
    BILL IS REFUSED" UNTIL 2026-08-27** (CR-039 wave C tasks 10/11, closing the
    write halves of `DEF-517` and `DEF-515`). Both gates are now open on a
    seeded tenant: the sample Residential plan states r10's `1.5`, all 44
    seeded premises state a side, and **two of them are outside the city**.
    Nothing is refused, because *stated* is what the refusal is missing — a
    seeded estate with 42 unstated addresses under a surcharging plan would be
    42 exception rows, which is exactly why the seed states all of them.
    **The promise underneath is unchanged and is still what protects a real
    utility:** a plan stating NO factor never consults the premises at all
    (BR-RAT-102), which is why the sample COMMERCIAL plan deliberately states
    none and its two suites bill byte-identically to before.

    This is the SECOND implementation of R5 in the repo — `rating.resolution
    .money_factor` is the first — and that is deliberate rather than an
    oversight. Billing may not import rating's modules (B1), the chain has no
    production caller (DEF-438), and `tests/test_def_438_parity.py` exists
    precisely to price both paths and name any step where they disagree. R5 is
    compared there, on a plan that states a factor.
    """
    factor = jurisdiction.get("outside_city_factor")
    if factor is None:
        # BR-RAT-102: absent or `1` is *this plan does not surcharge*, and the
        # premises is not consulted. `plan_jurisdiction_pricing` has already
        # folded a stored `1` into None, so there is ONE shape to test here.
        return Decimal("1")
    inside = premises.get("inside_city_limits")
    if inside is None:
        where = premises.get("address_line") or premises.get("premises_id") or "this premises"
        raise GatherProblem(
            GATHER_JURISDICTION_UNSTATED,
            f"service {service_code}: this account's plan surcharges outside the "
            f"city by ×{factor} (BR-RAT-102) and nobody has recorded whether "
            f"{where} is inside or outside the city limits. The bill refuses "
            "rather than being produced at the inside-city price by default: the "
            "factor changes every base line and every usage line, so a guess "
            "here is a wrong bill and not a partial one. To clear it, set the "
            "inside/outside-city flag on this premises (BR-RAT-101).",
            service_code=service_code,
        )
    if inside:
        return Decimal("1")
    if service_code in tuple(jurisdiction.get("exempt_services") or ()):
        # §A4 S2, verbatim: *"BASE-S $8.00 (flat everywhere — the multiplier does
        # NOT touch sewer)"*. The plan lists its own services, so the plan's own
        # service line is where the exemption lives (BR-RAT-102).
        return Decimal("1")
    return _decimal(factor)


#: BR-CUS-068's own value for `accounts.kind`. Billing reads a customers CODE
#: here — in exactly ONE place, and deliberately — because the safe degrade
#: when customers' coverage read is absent depends on whether this account
#: covers one unit or several, and nothing else on the account can say. A
#: string and not an import: B1 forbids billing importing customers' modules.
ACCOUNT_KIND_MASTER = "master"


def covered_units(account: Any) -> tuple[str, ...]:
    """EVERY unit this account's ONE bill prices, anchor first (BR-CUS-068).

    An ordinary account answers `(unit_id,)` — the single id this module has
    always billed — so every non-master bill prices byte-identically and the
    ❄️ B5 goldens cannot move. A MASTER account answers the anchor plus every
    other common area it covers through an open service agreement, which is
    the difference between the owner's $41.20 and the owner's **$69.60**
    (BR-MET-101; DEF-571).

    ⚠ **AN UNPUBLISHED SEAM DEGRADES ONE WAY FOR AN ORDINARY ACCOUNT AND
    REFUSES FOR A MASTER, AND THE ASYMMETRY IS THE WHOLE POINT.** Every other
    cross-module read in this file degrades to today's behaviour when its
    owner has not published the name (`_discounts_for`, `_plan_jurisdiction`,
    `_taxes_for`). Today's behaviour for a master account IS the defect —
    a bill for $41.20 of a $69.60 obligation, correct-looking on the document
    and short by an entire common area — so the master branch refuses BY NAME
    instead. The refusal is one row on the S31.2 exception tab (BR-BIL-055),
    never a crash and never a run.
    """
    anchor = getattr(account, "unit_id", None)
    fallback = (str(anchor),) if anchor is not None else ()
    covered = _resolve("customers", "covered_unit_ids")
    if covered is None:
        if str(getattr(account, "kind", "") or "") == ACCOUNT_KIND_MASTER:
            raise GatherProblem(
                GATHER_COVERAGE_UNRESOLVED,
                f"account {getattr(account, 'account_no', '?')} is a MASTER account "
                "(BR-CUS-068) and customers has not published covered_unit_ids, so "
                "WHICH common areas this one bill covers cannot be read. The bill "
                "refuses rather than being produced from the anchor unit alone — "
                "that answer is a plausible document short by every other common "
                "area (DEF-571), and nothing on it would say so.",
            )
        return fallback
    unit_ids = tuple(str(unit_id) for unit_id in covered(account) or ())
    if str(getattr(account, "kind", "") or "") == ACCOUNT_KIND_MASTER:
        unit_ids = _without_unplanned_common_areas(unit_ids)
    return unit_ids or fallback


def _without_unplanned_common_areas(unit_ids: tuple[str, ...]) -> tuple[str, ...]:
    """🔒 HUMAN-REVIEW-PENDING (money path) — `DEF-BIL-9252`.

    A master's covered COMMON AREA that carries no plan contributes NOTHING to
    the owner's bill, and does not block it. PO 2026-09-21, verbatim: *"common
    area dont need rate plan as of now; make this optional"* (decision log
    2026-09-21, ruling 1; carried from `DEF-CUS-5496`, 2026-09-16, *"common
    area dont need plan"*).

    Until this filter the unplanned common area was the anchor of the master's
    coverage, so `_gather_account` read ITS plan — None — and refused the whole
    owner's bill with `unit_has_no_plan`: every New Connection build with a
    common area (the wizard's own default shape) could never take its first
    bill, and the empty homes' base charges (`BR-CUS-170`) went with it.

    ⚠ **THE RULING'S PRECONDITION STILL HOLDS, AND THIS IS HOW.** The decision
    log made the ruling safe on *"an unplanned unit can exist and can never be
    billed"*. Dropping the unit from the coverage keeps exactly that: no tariff,
    no reading and no line of the unplanned common area is priced on any bill.
    What changes is that it no longer takes the dwellings' money down with it —
    with no planned common area left, the master falls through to the
    `DEF-CUS-9050` path (PO 2026-10-02, option A) and borrows its first PLANNED
    empty home as the anchor for the bill-level facts. A master with nothing
    planned at all still refuses (`GATHER_NO_UNIT` / `GATHER_NO_PLAN`).

    ⛔ **A DWELLING IS NEVER DROPPED** — only a unit flagged `is_common_area`,
    and only while customers' `COMMON_AREA_REQUIRES_A_PLAN` is False. A
    missing seam on either side fails CLOSED: the unit is kept and the bill
    refuses exactly as it did before.
    """
    requires = _resolve("customers", "common_area_requires_a_plan")
    unit_row = _resolve("metering", "unit_row")
    if requires is None or unit_row is None or requires():
        return unit_ids
    kept: list[str] = []
    for unit_id in unit_ids:
        row = unit_row(unit_id)
        if bool(getattr(row, "is_common_area", False)) and getattr(row, "rate_plan_id", None) is None:
            continue
        kept.append(unit_id)
    return tuple(kept)


#: BR-CUS-170 — this master's premises holds units NOBODY OCCUPIES, whose base
#: charges belong on the owner's bill.
#:
#: ⚠ **RETIRED 2026-08-27 — THE BILL NO LONGER REFUSES, IT PRICES THEM.** This
#: reason was raised while `TariffConfig` had no per-tariff base-only flag, so
#: one bill could not hold two base charges for one service and the owner's
#: document would have footed at `$69.60` while `$81.60` was owed (DEF-990).
#: `_unbilled_unit_tariffs` builds those base charges now. The string is KEPT
#: rather than deleted because exception rows already written on a running
#: deployment carry it and the S31.2 screen groups on the value — a code that
#: vanishes turns those rows into blanks. Nothing raises it any more.
GATHER_UNBILLED_UNITS_UNPRICEABLE = "master_unbilled_units_unpriceable"

#: OQ-601 edge 1 / DEF-1060 — the UNIT takes a service and the plan prices it
#: NOWHERE: no rate schedule, therefore no base charge and no billed unit.
#:
#: ⚠ **RETIRED AS A REFUSAL THE DAY IT WAS WRITTEN — `OQ-670` IS RULED AND THE
#: BILL CARRIES A `$0.00` LINE INSTEAD.** PO verbatim, 2026-08-27: *"Ana's trash
#: — what does a service cost when the plan prices it nowhere? 🔒 - (b) Bill
#: $0.00"*. This lane recommended (a), refuse by name; the PO overruled it with
#: the trade in front of them — that (b) is *"a trash line at zero on the
#: document. The run never stops — and 48 trash accounts are told they owe
#: nothing for trash. That is the same silence you caught, wearing a line
#: item."* The string is KEPT because it is the marker
#: `_unpriced_unit_service_lines` stamps on the zero line's provenance, and
#: because an exception row already written on a running deployment carries it.
#: Nothing raises it any more.
GATHER_UNIT_SERVICE_UNPRICED = "unit_service_priced_nowhere"


def base_charge_only_units(
    account: Any, *, period_start: date | None = None, period_end: date | None = None
) -> tuple[dict[str, Any], ...]:
    """BR-CUS-170 — the units on a master's premises that nobody else pays for.

    PO ruling 2026-08-27 (closing OQ-531), verbatim: *"when bill is generated
    for A - we should consider common areas and U6 to U10 base charges ; U1 to
    U5 bill be send to Accounts assocaited with U1 to U5"*. So a master's one
    bill is its common areas (which `covered_units` above already answers) PLUS
    the BASE CHARGES of every unit on that premises with **no occupying
    account** — and an occupied unit is excluded by the PRESENCE OF ITS OWN
    ACCOUNT, never by a flag somebody has to maintain.

    `()` for every ordinary account and for every master whose premises is
    fully let, so no ordinary bill issues an extra query and no ❄️ B5 figure
    can move. An unpublished customers seam also answers `()` — the degrade
    that cannot invent a charge; what it CANNOT do is quietly under-bill,
    because `gather_account` refuses on the non-empty case rather than pricing
    a subset (see `_unbilled_unit_tariffs`).
    """
    if str(getattr(account, "kind", "") or "") != ACCOUNT_KIND_MASTER:
        return ()
    coverage = _resolve("customers", "base_charge_only_coverage")
    if coverage is None:
        return ()
    if period_start is not None and period_end is not None:
        # 🔒 `DEF-CUS-9050` (PO 2026-10-02) — the BILL asks for its period, so a
        # unit let for part of it comes back with its `vacant_days`, and the
        # owner pays the base only for those days.
        return tuple(
            dict(entry)
            for entry in coverage(account, period_start=period_start, period_end=period_end)
            or ()
        )
    return tuple(dict(entry) for entry in coverage(account) or ())


#: DEF-990 — a master's empty unit whose IN-SERVICE state cannot be read,
#: because the assets module has not published the read that says whether a
#: service point carries anything at all.
GATHER_UNBILLED_UNIT_UNREADABLE = "unbilled_unit_service_state_unreadable"


def _point_has_asset(service_point_id: Any, service_code: Any = None) -> bool | None:
    """Does anything stand on this service point? `None` = nobody can tell.

    PO ruling 2026-08-27, closing OQ-601's last edge, verbatim: *"C — derive
    it: a service point with no asset and no account means not in service"*.
    A unit awaiting installation gets no new status value and no new column —
    it is recognised by the two facts already true of it, and this read is the
    first of them.

    ⚠ **THE THREE-VALUED ANSWER IS THE POINT.** `False` is *the utility looked
    and this point carries nothing*; `None` is *nobody looked*, which is what an
    unpublished seam means and is a different fact entirely. Collapsing them
    would turn a deployment whose assets lane has not landed into a premises
    where every unit is "awaiting installation", and every empty unit's base
    charge would silently leave the owner's bill — DEF-1060's shape, on the
    money BR-CUS-170 exists to collect. The caller REFUSES on `None`.

    ⚠ **A SERVICE WHOSE CAPACITY IS RECORDED ON THE UNIT ANSWERS `True`
    (`DEF-BIL-8725`, decision log 2026-10-01).** Storm water's ERU and
    thermal/heat's tons live on the unit by PO ruling (2026-09-02, 2026-09-07:
    *"take it from Unit"*), and no asset type exists for either — so asking
    whether an asset stands on their point is asking a question the product
    rules can never answer yes to. The 2026-09-30 ruling (*no asset = not in
    service*) excepted sewer for exactly that reason (*"sewer is exception
    because it is % of service"*); these two are the same case. Read before
    this, every storm-water and thermal line left every bill, on every tenant.
    Asked through metering's published `capacity_is_recorded_on_unit`; absent
    seam = not such a service, so nothing else moves.
    """
    if service_code:
        on_unit = _resolve("metering", "capacity_is_recorded_on_unit")
        if on_unit is not None and on_unit(str(service_code)):
            return True
    ids_for = _resolve("assets", "asset_ids_for_service_point")
    if ids_for is None:
        return None
    return bool(ids_for(service_point_id) or ())


def nothing_to_bill(account: Any) -> bool:
    """`BR-BIL-1025` — is there anything at this account's address to charge for?

    ⚠ **THE ANSWER IS READ FROM THE SAME TWO SEAMS THE BILL ITSELF WOULD ASK,
    AND NEVER FROM THE ACCOUNT'S KIND.** A master account's bill is exactly two
    things: the units it COVERS (`covered_units`, its common areas) and the
    unoccupied units `BR-CUS-170` puts on it (`base_charge_only_units`). Both
    empty means the bill would have no lines — and *"it is a master account"*
    would not, because a master with a hallway and a master with six empty flats
    are the same kind and only one of them is silent.

    **WHY IT EXISTS AT ALL, AND WHY IT IS NOT THE DOCUMENT DECISION.** The PO
    ruled on 2026-08-31 that *every address gets its owner a Master Account*, so
    an owner-occupier holds one — covering nothing, because he occupies the only
    unit — and `gather_account` refuses it by name (`GATHER_NO_UNIT`: no unit, no
    plan, no service points). That refusal is CORRECT for an account that ought
    to have had something and is a FALSE ALARM for this one, and consequence 1 of
    the same ruling is explicit about the cost: *"Leave it firing and every
    owner-occupier in the book is a false alarm every month."*

    So this answers one question — *is this account silent?* — and the run uses
    it to sort a refusal into `silent` instead of `blocked`. **The DOCUMENT
    decision is not here and must not be**: it is `BR-BIL-1024`, taken in
    `stages/assemble_document.py` after pricing, where the lines are known. Two
    exclusion paths is how a run starts disagreeing with itself about who was
    billed; this is one classifier feeding one list.

    ⚠ **A COVERAGE READ THAT REFUSES IS NOT A COVERAGE READ THAT IS EMPTY.**
    `covered_units` raises `GatherProblem` for a master when customers has not
    published the coverage read, deliberately — today's behaviour for a master
    would be a plausible document short by an entire common area (DEF-571). That
    refusal is caught here and answered **False**: an unreadable master goes on
    blocking the run and reaching the exceptions screen exactly as it does now.
    Silence is only ever claimed on a positive reading of BOTH seams.

    **False for every ordinary account**, which is every account in this product
    that is not a master: an ordinary account answers `(unit_id,)` from the row
    already in hand, so the first test short-circuits with no query at all and no
    ❄️ B5 figure can reach this function.
    """
    if str(getattr(account, "kind", "") or "") != ACCOUNT_KIND_MASTER:
        return False
    try:
        if covered_units(account):
            return False
    except GatherProblem:
        # The seam could not answer. "Nobody looked" is not "there is nothing" —
        # DEF-990's three-valued lesson, one module along.
        return False
    return not base_charge_only_units(account)


def _unbilled_unit_tariffs(
    account: Any,
    coverage: tuple[dict[str, Any], ...],
    *,
    service_date: date,
    scope_services: tuple[str, ...] | None,
    premises: dict[str, Any] | None,
) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """BR-CUS-170's OTHER half, PRICED — the base charge of every empty unit.

    Returns `(tariffs, zero_lines)`: the base-only TARIFFS for the empty units'
    services their plan prices, and the `$0.00` LINES for the ones it prices
    nowhere (OQ-670 — see the paragraph on the schedule-less case below).

    🔒 HUMAN-REVIEW-PENDING (money path) — row in
    `12-governance/09-human-review-ledger.md`.

    PO ruling 2026-08-27 (closing OQ-531), verbatim: *"when bill is generated
    for A - we should consider common areas and U6 to U10 base charges ; U1 to
    U5 bill be send to Accounts assocaited with U1 to U5"*. `covered_units`
    answers the common areas; this answers the empty units, as one **base-only**
    tariff per service each of them takes.

    ❄️ **WORKED, ON BR-MET-101's OWN BUILDING.** 1408 Elm: hallway electric
    `$41.20` + shared irrigation water `$28.40` = **`$69.60`**, and with Unit C
    empty, planned and taking electric its **`$12.00`** base joins them —
    **`$81.60`**. Before this function the bill REFUSED (DEF-990) rather than
    issue a document that foots at `$69.60` and is short by `$12.00` with
    nothing on it saying so.

    ── WHY THIS IS NOW BUILDABLE AND WAS NOT (DEF-990's three obstacles) ─────
    Every one of them was a routing gap and none was arithmetic — the engine
    has always been able to price a base with no usage line
    (`price_bill(base_only_services=…)`):

    * **one bill could not hold two base charges for one service.** It can now:
      `TariffConfig.base_only` is a per-TARIFF fact, so the hallway's electric
      prices usage on the same bill where Unit C's electric prices only its
      base. Nothing keys a bill's tariffs by service code.
    * **a second electric tariff would pick up the first one's read**, because
      `measure_consumption._reading_for` matches by service code alone. A
      base-only tariff never reaches that lookup — the stage branches on the
      flag first — so no usage is billed twice.
    * **`runs.readings_for_account` walks `covered_units`**, so widening that
      tuple would have read the empty unit's meter and charged USAGE the ruling
      did not ask for. It is deliberately NOT widened: these units arrive here
      instead, base-only, and their meters are never read.

    ── THE EMPTY UNIT'S BASE COMES FROM THE EMPTY UNIT'S OWN PLAN ────────────
    BR-CUS-014 (PO 2026-08-11): *the account derives its plan from the unit*.
    BR-RAT-012/027 (CONFIRMED): the base charge *"is defined per service within
    a plan"*. So the price of Unit C's electric connection is a fact about Unit
    C's plan, resolved through exactly the same `_tariff_config_for` every other
    line on this bill goes through — the version in force at the SERVICE date
    (BR-RAT-007), the size ladder, the jurisdiction factor. What stays the
    ANCHOR's, because BR-CUS-068 already settles it for the covered areas, is
    everything the BILL carries once rather than per service: the taxes, the
    fees, the discounts and the plan snapshot.

    ── NOT IN SERVICE (PO ruling 2026-08-27, OQ-601's last edge) ────────────
    *"a service point with no asset and no account means not in service"*.
    Every unit in this coverage already satisfies the second half by
    construction — `base_charge_only_coverage` includes a unit exactly when no
    account occupies it — so the test that remains is the first: a point with
    nothing standing on it is a connection awaiting installation and is billed
    **nothing at all**. A unit whose every point is empty therefore contributes
    no tariff and no charge, which is what makes a newly created premises cost
    its owner nothing until the installer arrives.

    `()` for every ordinary account and for every master whose premises is
    fully let, so no ordinary bill issues an extra query and no ❄️ B5 figure
    can move.
    """
    if not coverage:
        return (), ()
    unit_row = _resolve("metering", "unit_row")
    points_for = _resolve("metering", "service_points_for")
    plan_schedules = _resolve("rating", "plan_rate_schedules")
    if unit_row is None or points_for is None or plan_schedules is None:
        raise GatherProblem(
            GATHER_COVERAGE_UNRESOLVED,
            f"account {getattr(account, 'account_no', '?')} is a MASTER account whose "
            f"premises holds {len(coverage)} unit(s) with no occupying account, and the "
            "reads that price their base charges (metering's unit_row / "
            "service_points_for, rating's plan_rate_schedules) are not all published. "
            "BR-CUS-170 puts those base charges on this bill and nothing here assumes "
            "what they are.",
        )
    configs: list[Any] = []
    zero_lines: list[Any] = []
    for entry in coverage:
        unit_id = entry.get("unit_id")
        label = str(entry.get("label") or unit_id)
        if not entry.get("has_plan"):
            # BR-MET-040 wants a plan on every unit, but an unplanned EMPTY unit
            # has no base charge to omit and nobody to send one to. It is left
            # exactly where BR-CUS-068's signed $69.60 case leaves it — out of
            # the bill entirely — rather than stopping the owner's document for
            # a connection that does not exist yet.
            continue
        row = unit_row(unit_id)
        unit_plan = getattr(row, "rate_plan_id", None)
        if unit_plan is None:  # pragma: no cover — has_plan said otherwise
            continue
        schedules = {
            schedule.get("service_code"): schedule for schedule in plan_schedules(unit_plan)
        }
        jurisdiction = _plan_jurisdiction(unit_plan)
        for point in points_for(unit_id) or ():
            service_code = point.get("service")
            if not service_code:
                continue
            if scope_services is not None and service_code not in scope_services:
                # US-BIL-001 §5 — an unchecked service is an EXPLICIT recorded
                # choice, and it is the same choice for an empty unit's base as
                # for an occupied one's usage.
                continue
            occupied = _point_has_asset(point.get("id"), service_code)
            if occupied is None:
                raise GatherProblem(
                    GATHER_UNBILLED_UNIT_UNREADABLE,
                    f"account {getattr(account, 'account_no', '?')}: {label} has no "
                    f"occupying account and takes {service_code}, so BR-CUS-170 puts its "
                    "base charge on this owner's bill — and assets has not published "
                    "asset_ids_for_service_point, so whether that connection is INSTALLED "
                    "or still awaiting installation cannot be read. The PO's rule (2026-08-27) "
                    "is that a service point with no asset AND no account is NOT IN SERVICE "
                    "and bills nothing; an unreadable seam is not the same fact as an empty "
                    "point, and answering 'nothing' to both would quietly drop a base charge "
                    "off every owner's bill. The run continues for every other account.",
                    service_code=service_code,
                )
            if not occupied:
                # NOT IN SERVICE — no asset and no account. Bills nothing.
                continue
            schedule = schedules.get(service_code)
            if schedule is None:
                # ── THE EMPTY UNIT TAKES A SERVICE ITS OWN PLAN PRICES NOWHERE
                # It is OQ-670's case exactly, one unit along: no rate schedule,
                # therefore no base charge and no billed unit, and BR-CUS-170
                # still says the charge is this owner's. **PO 2026-08-27: bill
                # `$0.00`** — the same ruling and for the same stated reason, so
                # the gap is on the owner's document rather than dropped from it.
                #
                # ⚠ IT IS THE RULED CASE AND NOT A WIDENING, and the reading is
                # written down rather than smuggled: the ruling names *a service
                # the UNIT derives that the plan prices nowhere at all*, and a
                # master's empty unit is a unit this one bill derives services
                # from (BR-CUS-170) whose plan is its own (BR-CUS-014). Refusing
                # here instead would contradict the half of the ruling that says
                # the run never stops.
                zero_lines.append(
                    rating_seam.RatedLine(
                        kind="base",
                        description=f"{label} — {service_code} (not priced on this plan)",
                        amount=Decimal("0.0000"),
                        taxable=True,
                        service=service_code,
                    )
                )
                continue
            # 🔒 HUMAN-REVIEW-PENDING — `DEF-BIL-9251`. A COUNTING capacity
            # service (trash, fire) is priced the way the unit-level path prices
            # it (`_tariff_configs` → `_per_size_configs`, `CR-063`): one config
            # per size, the base per ASSET (PO 2026-09-30 option B) and summed
            # onto ONE base line per service (*"per service"*). Until this branch
            # the empty home asked `_connection_size_for` for ONE size, and a fire
            # connection carrying a 6" line and two 2" lines has three — so the
            # owner's whole first bill refused `connection_size_unresolved` while
            # every line had its size. Base ONLY (BR-CUS-170): the per-size
            # USAGE ($60.00 + 2 × $12.00 = $84.00 on an occupied unit) is not the
            # owner's for an empty home, exactly as an empty home's meter is
            # never read. Worked: base $5.00 a line → Unit 1 3 × $5.00 = $15.00,
            # the figure the unit-level path puts inside its $99.00 fire line.
            size_groups = _size_groups_for(unit_id, service_code, service_date)
            if size_groups is not None:
                configs.extend(
                    replace(
                        config,
                        base_only=True,
                        covers_unit_id=str(unit_id),
                        covers_unit_label=label,
                        occupancy_factor=_vacancy_factor(entry),
                    )
                    for config in _per_size_configs(
                        schedule,
                        service_code,
                        service_date,
                        size_groups,
                        customer_class=_customer_class(account),
                        jurisdiction=jurisdiction,
                        premises=premises or {},
                    )
                )
                continue
            # `DEF-BIL-8724` — the config NAMES its empty unit, so the ruled
            # path can leave this one base exactly as priced here (it belongs to
            # another unit's plan) rather than refuse the owner's whole bill as
            # "more than one tariff for electric".
            configs.append(
                replace(
                    _tariff_config_for(
                        schedule["tariff"],
                        service_code,
                        service_date,
                        size_class=_connection_size_for(unit_id, service_code),
                        # BR-RAT-108 — the empty unit's base is still THIS bill's
                        # base and it is still narrowed by the OWNER's class
                        # (DEF-2823). `account` is the owner, which is the account
                        # BR-CUS-170 puts the charge on.
                        customer_class=_customer_class(account),
                        jurisdiction_factor=_jurisdiction_factor_for(
                            service_code, jurisdiction=jurisdiction, premises=premises or {}
                        ),
                        # THE WHOLE POINT: the base charge and NOT the usage. This
                        # unit's meter is never read (`runs.readings_for_account`
                        # walks `covered_units`, which does not contain it), and
                        # `measure_consumption` never asks for a reading on this
                        # tariff's behalf — so a second electric tariff cannot pick
                        # up the hallway's kWh, which is DEF-990's own warning.
                        base_only=True,
                        # BR-RAT-028 — mode (A) is the SCHEDULE's figure since the
                        # PO ruling of 2026-09-10, so it is read inside
                        # `_tariff_config_for` from the resolved version and this
                        # caller only says that the config may carry it. Mode (B),
                        # the plan floor, is still the plan's and still travels, and
                        # `.get` for the same late-binding reason as `base_charge`
                        # beside it. OQ-1166 asks the PO whether a base-only unit
                        # should be topped to a minimum at all; the rule as signed
                        # states no exception, so the figures travel and the
                        # question is filed rather than answered here.
                        carries_service_minimum=True,
                        plan_minimum_bill_amount=schedule.get("plan_minimum_bill_amount"),
                    ),
                    covers_unit_id=str(unit_id),
                    # 🔒 `DEF-CUS-9050` (PO 2026-10-02) — the line NAMES its
                    # unit (*"Unit 4 · water base charge"*), and is the owner's
                    # only for the days nobody occupied the unit: 15 vacant
                    # days of 30 → 15/30 × $8.00 = $4.00. `None` (the whole
                    # period) multiplies by nothing, so every earlier figure,
                    # 1408 Elm's $81.60 among them, is unmoved.
                    covers_unit_label=label,
                    occupancy_factor=_vacancy_factor(entry),
                )
            )
    return tuple(configs), tuple(zero_lines)


def _vacancy_factor(entry: dict[str, Any]) -> Decimal | None:
    """🔒 HUMAN-REVIEW-PENDING (money path) — `DEF-CUS-9050`.

    `vacant_days / period_days` for a unit let for PART of the period, else
    `None`. UNROUNDED (hard rule 2: round only at finalization, B4) — the engine
    multiplies the base by it and rounds once, at the line."""
    vacant = entry.get("vacant_days")
    days = entry.get("period_days")
    if vacant is None or not days or int(vacant) >= int(days):
        return None
    return Decimal(int(vacant)) / Decimal(int(days))


def _coverage_facts(
    unit_ids: tuple[str, ...], *, plan_id: Any, account_no: str
) -> tuple[dict[str, str], tuple[tuple[str, str | None], ...]]:
    """WHICH covered unit serves each service, and what each is called.

    Returns `({service_code: unit_id}, ((unit_id, label), …))`. A single-unit
    account returns `({}, ())` WITHOUT asking metering anything — every service
    resolves to the anchor, so the empty map is the identity and an ordinary
    account issues not one extra query.

    ── THE TWO REFUSALS, AND WHY NEITHER IS A CHOICE ────────────────────────
    **OQ-335 — the covered units sit on DIFFERENT plans.** Every bill-level
    input the pipeline carries is resolved from ONE plan id: the taxes (PO
    2026-08-11, *"Tax rates are for bill not for service"*), the charge codes
    (BR-RAT-117), the discounts (BR-RAT-069/110) and the locked-at-issue plan
    snapshot (BR-CUS-013). Adopting the ANCHOR's plan for all of them would be
    the same silent-anchor answer DEF-571 was filed for, one layer up.

    **OQ-334 — two covered units take the SAME service.** BR-MET-101's worked
    case does not reach it (hallway electric, irrigation water), and nothing
    signed says whether a second electric connection brings a second base
    charge or whether BR-RAT-002's tiers pool across the bill. On a $12.00
    base and two 100 kWh connections the two readings are **$64.00** and
    **$52.00**, and the ladder question moves it again.

    ⚠ **BOTH REFUSE AS A `GatherProblem`, NOT AS `NotImplementedError`** — the
    same departure `_base_charge_for` takes for OQ-238 and for the same reason:
    a raise here would take down a 500-account run on its first account, where
    a named break stops ONE account and lets the rest bill (BR-BIL-055). The
    OQ id travels in the message, so the exception screen names the question.
    """
    if len(unit_ids) < 2:
        return {}, ()
    unit_row = _resolve("metering", "unit_row")
    points_for = _resolve("metering", "service_points_for")
    if unit_row is None or points_for is None:
        raise GatherProblem(
            GATHER_COVERAGE_UNRESOLVED,
            f"account {account_no} covers {len(unit_ids)} units (BR-CUS-068) and "
            "metering has not published unit_row/service_points_for, so the other "
            "covered units cannot be resolved. Nothing is assumed about them.",
        )
    serves: dict[str, str] = {}
    labels: list[tuple[str, str | None]] = []
    for position, unit_id in enumerate(unit_ids):
        row = unit_row(unit_id)
        labels.append((unit_id, getattr(row, "label", None)))
        if position:  # the anchor's own plan is the one the caller resolved
            covered_plan = getattr(row, "rate_plan_id", None)
            if covered_plan is None:
                raise GatherProblem(
                    GATHER_NO_PLAN,
                    f"covered common area {getattr(row, 'label', None) or unit_id} has "
                    "no plan. BR-MET-040: a plan is REQUIRED, and this account's bill "
                    "prices that area beside the anchor's — so the whole bill waits "
                    "for a human rather than quietly omitting one shared space.",
                )
            if str(covered_plan) != str(plan_id):
                raise GatherProblem(
                    GATHER_COVERAGE_MULTI_PLAN,
                    f"account {account_no} covers common areas on TWO DIFFERENT plans "
                    f"({plan_id} and {covered_plan}), and no signed rule says whose "
                    "taxes, fees, discounts or plan snapshot govern the one bill "
                    "BR-CUS-068 gives the owner — every one of those is resolved from "
                    "a single plan id. OQ-335 carries the question to the Product "
                    "Owner; the bill refuses rather than adopting the anchor's plan "
                    "for figures the other area never agreed to. To clear it, put the "
                    "covered common areas on one plan (S16); the run continues for "
                    "every other account.",
                )
        for point in points_for(unit_id) or ():
            service_code = point.get("service")
            if not service_code:
                continue
            held_by = serves.get(service_code)
            if held_by is not None and held_by != unit_id:
                raise GatherProblem(
                    GATHER_COVERAGE_SERVICE_TWICE,
                    f"account {account_no} covers TWO common areas that both take "
                    f"{service_code} (BR-CUS-068), and no signed rule says whether "
                    "the second connection brings its own base charge or whether "
                    "BR-RAT-002's tiers pool across the one bill — on a $12.00 base "
                    "and two 100 kWh connections that is $64.00 or $52.00. OQ-334 "
                    "carries the question to the Product Owner; the bill refuses "
                    "rather than being produced on whichever reading the code "
                    "reached first. BR-MET-101's worked case (one electric area, one "
                    "water area) is unaffected and bills.",
                    service_code=service_code,
                )
            serves[service_code] = unit_id
    return serves, tuple(labels)


def gather_account(**kwargs: Any) -> AccountBillingData:
    """`_gather_account`, with the base-not-set collector open around it.

    PO ruling 2026-09-30 — a base nobody defined and bound bills `$0.00` with a
    named warning. The collector is opened HERE, around the whole call, so the
    warning is attached to the very `AccountBillingData` whose tariffs carry
    the zero, and it is reset in `finally` so a refused account cannot leak its
    services into the next account's warnings. A split segment and a
    back-bill group each call this function, so each carries its own.
    """
    token = _BASE_NOT_SET.set([])
    # PO 2026-10-01 — the unpriced sizes and the per-service trace, opened and
    # reset with the base-not-set collector for the same reason.
    size_token = _SIZE_NOT_PRICED.set([])
    trace_token = _PRICING_TRACE.set({})
    # PO 2026-10-01 — overlapping versions and unsized meters, the same way.
    overlap_token = _VERSIONS_OVERLAP.set([])
    needs_size_token = _MINIMUM_NEEDS_SIZE.set([])
    unsized_token = _METER_SIZE_NOT_RECORDED.set([])
    # 🔒 BR-RAT-034 — the served span the season split is counted over, opened
    # and reset with the rest for the same reason: one account's days must not
    # leak into the next account's prices.
    span_token = _SEASON_SPAN.set(
        _served_span(kwargs.get("account"), kwargs.get("period_start"), kwargs.get("period_end"))
    )
    # 🔒 `BR-RAT-1066` (`CR-167-BRC10`) — every plan binding read during this
    # gather sees the plan VERSION in force on the period end (R1's own rule,
    # *"the plan version in force on the service-period end date"*); a period
    # crossing a version start is cut there by `midperiod.split_plan`, so each
    # segment is gathered on its own version. A plan with one version reads
    # exactly what it read before (`plan_versioning`'s fallback to the head).
    pricing_day = _resolve("rating", "pricing_day", "plan_versioning")
    # 🔒 `CR-180-BRC10` B4 — a CORRECTION that names the plan VERSION the bill
    # should have used (PO 2026-10-12: *"you ahve to allow user to select the
    # plan and plan version"*) reads the plan's bindings as of THAT version's
    # first day instead of the period end. `None` — every caller but
    # `correction_items` — keeps R1's rule above byte for byte.
    binding_day = kwargs.pop("binding_day", None)
    day_scope = (
        pricing_day(binding_day or kwargs.get("period_end")) if pricing_day is not None else None
    )
    if day_scope is not None:
        day_scope.__enter__()
    try:
        return _gather_account(**kwargs)
    finally:
        if day_scope is not None:
            day_scope.__exit__(None, None, None)
        _SEASON_SPAN.reset(span_token)
        _METER_SIZE_NOT_RECORDED.reset(unsized_token)
        _MINIMUM_NEEDS_SIZE.reset(needs_size_token)
        _VERSIONS_OVERLAP.reset(overlap_token)
        _PRICING_TRACE.reset(trace_token)
        _SIZE_NOT_PRICED.reset(size_token)
        _BASE_NOT_SET.reset(token)


def _gather_account(
    *,
    account: Any,
    service_date: date,
    period_start: date,
    period_end: date,
    cycle_days: int,
    readings: tuple[ServiceReading, ...] = (),
    scope_services: tuple[str, ...] | None = None,
    rate_plan_id: Any = None,
) -> AccountBillingData:
    """Everything the pipeline needs about ONE account, read once.

    `rate_plan_id` (BR-RAT-114, 2026-08-22) is the plan in force during THIS
    window when it is not the unit's current one — resolved by the mid-period
    split from `unit_plan_assignments` (DEF-504: a customer who moved plans on
    the 15th is gathered once per stretch, each on ITS plan). None — every
    call that predates the split, and every unsplit account — keeps the only
    behaviour this function ever had: the unit's current plan.

    `account` is customers' own row, passed in by the orchestrator — billing
    does not query for it, because WHICH accounts a run covers is the run's
    decision (scope, cycle, behaviour class) and not this function's.

    `readings` are supplied rather than fetched for the same reason stage 2
    does not fetch them: the S31.3 exception step may REPLACE a reading with an
    estimate a human chose, and that decision has to be able to reach the
    gather without this module knowing anything about decisions.

    Raises `GatherProblem` — reason-coded — for every condition that makes the
    account unbillable. The orchestrator turns those into exception rows. None
    of them is a crash and none of them is a default.
    """
    unit_id = getattr(account, "unit_id", None)
    if unit_id is None:
        # ⚠ **`CR-056` W1 / `BR-CUS-1010` — A MASTER ACCOUNT NAMES NO UNIT, AND
        # THE UNIT THIS FUNCTION WANTS IS THE FIRST ONE IT COVERS.**
        #
        # `unit_id` is read here for three things — the PLAN (`BR-CUS-014`: the
        # account derives its plan from the unit), the PREMISES geography
        # (`BR-RAT-101`), and the tariff resolution — and until 2026-09-01 the
        # answer for a master was its ANCHOR, which was the premises' first
        # common area. `covered_unit_ids` returns exactly that unit first, in
        # exactly the same (label, id) order the anchor was chosen by, so on
        # `1408 Elm Street` this resolves to the hallway either way and the bill
        # is byte-identical: **$41.20 + $28.40 = $69.60.**
        #
        # It is read from the coverage rather than from the premises on purpose:
        # the premises' first unit is not necessarily one this account covers,
        # and pricing a bill off a unit the account does not hold an agreement on
        # would be inventing a plan for it.
        first_covered = covered_units(account)
        unit_id = first_covered[0] if first_covered else None
    # 🔒 HUMAN-REVIEW-PENDING — `DEF-CUS-9050` (PO 2026-10-02, option A). A
    # master with NO common area covers no unit, and until today that refused
    # here — so Oak Court's owner (four homes, no hallway) was never billed the
    # $8.00 base of the empty Unit 4. When the owner's bill has nothing of its
    # own but DOES carry empty homes for this period, the bill borrows the first
    # PLANNED empty home as its anchor for the bill-level facts only (plan
    # snapshot, taxes, fees, geography) and prices NO tariff of that home in
    # full: `borrowed_anchor` empties the own-tariff set below, so the only
    # lines are the empty homes' base charges (`_unbilled_unit_tariffs`).
    borrowed_anchor = False
    if unit_id is None and str(getattr(account, "kind", "") or "") == ACCOUNT_KIND_MASTER:
        empty_homes = base_charge_only_units(
            account, period_start=period_start, period_end=period_end
        )
        planned = [entry for entry in empty_homes if entry.get("has_plan")]
        if planned:
            unit_id = planned[0].get("unit_id")
            borrowed_anchor = True
    if unit_id is None:
        raise GatherProblem(
            GATHER_NO_UNIT,
            f"account {getattr(account, 'account_no', '?')} has no unit and covers "
            "none, so it has no plan and no service points. An ordinary account is "
            "bound to exactly one unit (BR-CUS-017); a master account that names a "
            "premises (BR-CUS-1010) is priced from the units it covers, and this "
            "one covers nothing.",
        )

    unit_row = _resolve("metering", "unit_row")
    if unit_row is None:
        raise GatherProblem(
            GATHER_NO_UNIT, "metering has not published unit_row; nothing is assumed."
        )
    unit = unit_row(unit_id)

    # BR-CUS-014 / PO ruling 2026-08-11 — the account DERIVES its plan from the
    # unit. There is deliberately no account-side plan record to consult.
    # BR-RAT-114: unless the SPLIT already resolved which plan covered these
    # days from the dated assignment history — see the parameter docstring.
    plan_id = rate_plan_id if rate_plan_id is not None else getattr(unit, "rate_plan_id", None)
    if plan_id is None:
        raise GatherProblem(
            GATHER_NO_PLAN,
            f"unit {unit_id} has no plan. BR-MET-040: a plan is REQUIRED — a "
            "unit without one blocks. The account belongs in the run's "
            "exception list, not in a bill.",
        )

    plan_ref = _resolve("rating", "plan_ref")
    plan = plan_ref(plan_id) if plan_ref else None
    if plan is None:
        # `plan_ref` filters to PUBLISHED (BR-RAT-030), so this is either a
        # draft/archived plan or a missing one. Both are "you cannot bill this",
        # and separating them here would leak which plan ids exist.
        raise GatherProblem(
            GATHER_PLAN_UNPUBLISHED,
            f"unit {unit_id}'s plan is not published. BR-RAT-030: a draft plan "
            "has no prices a bill could be produced from.",
        )

    # BR-CUS-068 (DEF-571) — EVERY unit this ONE bill covers, not just the
    # anchor. `({}, ())` for an ordinary account, which is every account that
    # is not a master: the maps below then resolve every service to `unit_id`
    # and this function prices exactly what it always priced.
    covered = covered_units(account)
    serving_units, covered_labels = _coverage_facts(
        covered, plan_id=plan_id, account_no=account.account_no
    )

    # BR-RAT-101 — resolved ONCE, along the path the run already walks for
    # everything else (`accounts.unit_id → units.premises_id`), and read here
    # rather than twice: R5's jurisdiction gate below and DEF-273's tax scope
    # further down are two questions asked of ONE set of premises facts, and two
    # reads could answer them differently.
    #
    # The ANCHOR's premises, and for a master account that is every covered
    # area's premises too: BR-CUS-068 attaches only common areas OF THIS
    # PREMISES and refuses a unit of another by name, so there is one geography
    # and one jurisdiction answer for the whole bill.
    premises_facts = _premises_geography(unit)

    # ── BR-BIL-300/301 · THE SERVICES THIS UNIT IS NOT IN SERVICE FOR ──────
    # Resolved BEFORE the tariffs so that no tariff — and therefore no base
    # charge — is built for a connection that does not exist (BR-RAT-080).
    # PO 2026-09-30: *no asset = not in service, even if the account took the
    # service* (a point with no asset counts as no point) and *"sane no line -
    # and use 0"* — so these print NO line; they reach the review list only.
    # `()` on every account whose unit carries an asset for everything its
    # plan prices.
    # ── 2026-09-30 · A %-OF-SERVICE HAS NO POINT OF ITS OWN (B1) ─────────
    # PO: *"for % of service there will not be any service point"*, and
    # sewer *"is taken whenever its basis service (water) is on the bill"*.
    # Read ONCE, here, so both narrowings below follow the SAME basis map.
    percent_bases = _percent_of_service_bases(plan_id, service_date, scope_services)
    unconnected_services = _unconnected_plan_services(
        unit_id,
        plan_id,
        scope_services=scope_services,
        serving_units=serving_units,
        percent_bases=percent_bases,
        # DEF-BIL-9793 — a %-of-service follows its basis only at an address
        # that OFFERS it (BR-MET-119). See the function's docstring.
        offered=_services_the_address_offers(unit),
    )

    # ── BR-BIL-1048 · THE SERVICES THIS ACCOUNT DID NOT BUY ────────────────
    # `BR-CUS-1101` (PO 2026-09-25) lets an account take a SUBSET of its
    # unit's services; until this landed the bill charged for every one of
    # them. Resolved AFTER `unconnected_services` and given it, so that a
    # service the property is not in service for stays on BR-BIL-301's review
    # list instead of being filed as *not bought* — the two cases are opposite
    # and are argued in `_plan_services_not_taken`'s docstring.
    #
    # `None` from the read means nobody can tell, `()` comes back, and the
    # bill is byte-for-byte what it was — which is every account whose
    # agreements cover everything its plan prices.
    services_taken = _services_taken_by_account(
        account, period_start=period_start, period_end=period_end
    )
    services_not_taken = _plan_services_not_taken(
        unit_id,
        plan_id,
        taken=services_taken,
        scope_services=scope_services,
        unconnected=unconnected_services,
        percent_bases=percent_bases,
    )

    # ── 2026-09-30 · NO AGREEMENTS ON FILE — BILL ALL AND WARN (B8) ────────
    # PO, option C: *"The bill still goes out, and the clerk sees the gap and
    # can fix the account."* `services_taken is None` already narrows nothing;
    # what is new is the warning. ⚠ **ONLY WHEN THE READ IS PUBLISHED.** An
    # unpublished customers seam is *nobody looked*, and a warning saying the
    # account holds no agreements would be a claim nobody checked.
    warnings: list[dict[str, Any]] = []
    if services_taken is None and _resolve("customers", "billed_service_codes_for"):
        warnings.append(
            {"key": WARN_NO_AGREEMENTS, "params": {"account_no": account.account_no}}
        )

    # ── 2026-09-30 · TWO METERS ON ONE METERED SERVICE (B5) ───────────────
    # Metering publishes one reading per meter, each naming its `asset_id`,
    # only where a metered point carries two or more in-service meters. The
    # tariffs follow the READINGS rather than a second read of the estate, so
    # the number of configs and the number of readings cannot disagree.
    meters_by_service = _meters_by_service(readings)
    # 🔒 PO 2026-10-01 (*"B · Price each meter separately"*, BR-BIL-1062) — a
    # meter SWAPPED inside the period arrives as one reading per meter part
    # (`runs._meter_swap`), so it is split per meter exactly like two in-service
    # meters; these are the services where that split is a swap.
    swapped_services = _swapped_services(readings)
    counted_empty: list[str] = []

    if borrowed_anchor:
        # `DEF-CUS-9050` — the anchor is an EMPTY home lent for bill-level facts;
        # none of its services is this owner's in full, so none is reviewed or
        # priced here. Its base arrives below, base-only, like every other.
        unconnected_services = ()
        services_not_taken = ()
    tariffs = () if borrowed_anchor else _tariffs_for_plan(
        plan_id,
        unit_id,
        service_date,
        scope_services,
        premises=premises_facts,
        serving_units=serving_units,
        skip_services=unconnected_services + services_not_taken,
        # BR-RAT-108 — the base charge code may be scoped by customer class
        # (DEF-2823). Resolved ONCE for the whole bill, from the same helper
        # the fee narrowing already uses, so the base and the fees cannot
        # disagree about what class this account is.
        customer_class=_customer_class(account),
        meters_by_service=meters_by_service,
        swapped_services=swapped_services,
        counted_empty=counted_empty,
    )
    # B2 — a COUNTED service whose point carries assets and none of them in
    # service on the period's end date is not in service either: no line, no
    # base, and the clerk's review list names it with the rest.
    unconnected_services = unconnected_services + tuple(
        code for code in counted_empty if code not in unconnected_services
    )

    # BR-CUS-170 (PO 2026-08-27, OQ-531) — and for a master account it is the
    # OTHER half of what this one bill owes: the BASE CHARGES of every unit on
    # the premises with no occupying account, each as its own base-only tariff
    # beside the common areas priced in full ($69.60 + $12.00 = $81.60 on
    # BR-MET-101's building, DEF-990). `()` for every ordinary account, so
    # nothing below this line changed for any bill this product has issued.
    unbilled_tariffs, unbilled_zero_lines = _unbilled_unit_tariffs(
        account,
        base_charge_only_units(account, period_start=period_start, period_end=period_end),
        service_date=service_date,
        scope_services=scope_services,
        premises=premises_facts,
    )
    tariffs = tariffs + unbilled_tariffs
    if borrowed_anchor and not tariffs and not unbilled_zero_lines:
        # `DEF-BIL-9252` — an owner's bill with an anchor BORROWED from an empty
        # home and nothing in service on any home has nothing to price. Until
        # this refusal it went on to the ruled chain, which asked metering for
        # the row of a unit the master does not cover and crashed `not found`
        # (red since 2.444.0 in `test_br_met_040_common_area`). Refused BY NAME,
        # as it was before the borrowed anchor existed: no unit in service.
        raise GatherProblem(
            GATHER_NO_UNIT,
            f"account {getattr(account, 'account_no', '?')} covers no common area "
            "with a plan, and none of its empty homes has a connection in service, "
            "so this owner's bill has nothing to price.",
        )

    # 🔒 DEF-RAT-8849 (PO 2026-10-01, *"yes build the season-change day
    # reading"*) — a reading dated on a season-change day inside the period
    # cuts the usage there. AFTER `tariffs`, because the season days are
    # rating's answer on each tariff; the readings come back unchanged
    # wherever no such reading exists, which is every bill before this rule.
    readings = _cut_at_season_change_reads(readings, tariffs)

    currency = _tenant_currency()
    if not currency:
        raise GatherProblem(
            GATHER_NO_CURRENCY,
            "the tenant's currency could not be resolved. CLAUDE.md rule 2: "
            "money travels with its CHAR(3) partner and the currency is the "
            "TENANT's — never client input, never a default.",
        )

    # BR-CUS-103 (DEF-707) — AFTER `tariffs`, because the partial-cut refusal
    # needs to know which services THIS bill charges for. A cut that covers
    # every one of them subtracts its dark days; one that covers some of them
    # refuses by name.
    service_days = _service_days(
        account,
        period_start,
        period_end,
        cycle_days,
        _service_off_windows(
            account,
            period_start=period_start,
            period_end=period_end,
            billed_services=tuple(getattr(config, "service", "") for config in tariffs),
            account_no=account.account_no,
        ),
    )

    discounts = _discounts_for(account, plan["id"], service_date)
    # BR-RAT-117 (PO 2026-08-22) — the recurring/auto-apply codes and the
    # plan's own named ones, as ONE deduped set of fee lines. `fees` has
    # defaulted to `()` here since this function was written (`DEF-561`), so
    # every configured charge code was silently absent from every bill.
    charge_fees = _charge_fees_for(
        plan["id"],
        service_date,
        _customer_class(account),
        tuple(getattr(config, "service", "") for config in tariffs),
    )

    # DEF-1060 / OQ-670 (PO 2026-08-27, overruling this lane's recommendation) —
    # the OTHER direction of the reconciliation: a service the UNIT takes that
    # the plan prices NOWHERE bills a **$0.00 line**, so the gap is on the
    # document rather than invisible in a silence. `()` for every account whose
    # unit takes only services its plan prices, which is every account this
    # product has ever billed — so no ❄️ B5 figure can move and Ana Alvarez's
    # six-line $64.57 becomes a SEVEN-line $64.57.
    #
    # It joins `fees` and not `tariffs` because there is no schedule to build a
    # tariff from: no model, no rate, no billed unit, and rule 3 forbids
    # inventing the last of those. See `_unpriced_unit_service_lines`.
    charge_fees = (
        charge_fees
        + unbilled_zero_lines
        # ⚠ BR-BIL-301's `$0.00 (not connected)` line WAS here. PO ruling
        # 2026-09-30: *"sane no line - and use 0"* — a service that is not in
        # service prints NO line and contributes `$0`. It is still carried as
        # `unconnected_services` below, which feeds the clerk's review list
        # (`runs._decisions_for`) and the one-time bill's Services table.
        + _unpriced_unit_service_lines(
            covered,
            priced_services=tuple(getattr(config, "service", "") for config in tariffs),
            scope_services=scope_services,
            plan_id=plan["id"],
            account_no=account.account_no,
            # BR-BIL-1048 — without this the narrowing feeds THIS function: a
            # service the account did not buy is no longer priced, so it would
            # arrive here as *the plan prices this nowhere* and reach the
            # document as a `$0.00` line. A customer would read a bill naming
            # the services they refused, which is the defect wearing a
            # different sentence.
            taken_services=services_taken,
            # 2026-09-30 — a service NOT IN SERVICE is not "priced nowhere";
            # it is absent, and PO ruled it prints no line of any kind.
            not_in_service=unconnected_services,
        )
    )

    data = AccountBillingData(
        account_id=str(account.id),
        account_no=account.account_no,
        # ⊕ `CR-183-BRC10` T5 — the class FOR THIS PERIOD, not only today's.
        behavior_class=_behavior_class_for_period(account, period_start, period_end),
        currency=currency,
        tax_exempt=_tax_exempt_on(account, service_date),  # B4.2 + CR-013 part 4
        period_start=period_start,
        period_end=period_end,
        cycle_days=cycle_days,
        service_days=service_days,
        rate_plan_id=plan["id"],
        rate_plan_name=plan["name"],
        rate_plan_version=plan["version"],  # SNAPSHOT — BR-CUS-013
        tariffs=tariffs,
        readings=readings,
        # DEF-273 (PO ruling 2026-08-18) — a tax rate is not a tax RULE. r10's
        # own table scopes three of its five Texas rates by customer class,
        # premises geography and service, so the resolver is handed the three
        # facts that answer them. They are read HERE because this is the step
        # that already holds the account, the unit and the premises; the engine
        # never learns them, and a tax that does not apply produces no rule and
        # therefore no line.
        taxes=_taxes_for(
            plan_id,
            service_date,
            customer_class=_customer_class(account),
            premises=premises_facts,
            services=tuple(getattr(config, "service", "") for config in tariffs),
            # DEF-383 — WHOSE bill this is, so rating can find an exemption
            # CERTIFICATE against one authority's tax. Not the same fact as
            # `tax_exempt` above: that flag is BLANKET (one boolean, one expiry,
            # every authority at once), where part 4's exemption object is per
            # tax and per category. A church exempt from the 6.25% state tax
            # still pays the city's 1.50% franchise fee.
            account_id=getattr(account, "id", None),
        ),
        # DEF-502 — the account's GRANTED discounts: open enrolment ∩ the
        # plan's binding, resolved at the SERVICE DATE like every tariff
        # version (BR-RAT-007). Read HERE because stages 1–6 are pure and an
        # enrolment is a database fact; applied ONCE at bill level by the
        # engine's apply-discounts stage (BR-RAT-071: before taxes, each tax
        # then picking its own base per BR-RAT-106).
        discounts=discounts,
        fees=charge_fees,
        # BR-BIL-301 — carried rather than re-derived, so the document's zero
        # lines and the clerk's review list are the SAME fact read once (see
        # the field's own note on `AccountBillingData`).
        unconnected_services=unconnected_services,
        # B8 (and the base-not-set warning another lane adds) — named
        # warnings that ride with the bill and never stop it.
        warnings=tuple(warnings),
        snapshot=_snapshot_for(
            account, unit, plan, covered=covered_labels, premises=premises_facts
        ),
    )

    # ── PO ruling 2026-09-30 · THE `$0.00` BASES, NAMED ────────────────────
    # Attached BEFORE the fork below, because a switched-on R3/R4 restates the
    # base per service and `resolution_switch` re-derives these warnings from
    # the chain's own answer. Appended rather than assigned, so a warning some
    # other step put on `data` is kept.
    base_not_set = tuple(_BASE_NOT_SET.get() or ())
    if base_not_set:
        data = replace(
            data,
            warnings=bill_warnings.with_base_not_set(data.warnings, base_not_set),
        )

    # ── PO ruling 2026-10-01 · A SIZE WITH NO BASE PRICE, NAMED ───────────
    # *"BASE-T has no price for CART-96 · billed $0.00"* — a warning, never a
    # refusal (and no sign-off tick: PO 2026-10-01, option A). And the chain
    # each service was priced from, as values, for stage 6 to write onto the
    # lines (`invoice_lines.pricing_trace`).
    unpriced_sizes = tuple(_SIZE_NOT_PRICED.get() or ())
    if unpriced_sizes:
        data = replace(
            data,
            warnings=bill_warnings.with_size_not_priced(data.warnings, unpriced_sizes),
        )
    # ── PO rulings 2026-10-01 · TWO MORE WARNINGS, NEVER REFUSALS ─────────
    # A legacy overlap of rate-schedule versions (the newest priced,
    # `BR-RAT-1055`) and a meter with no recorded size on a schedule with
    # per-size minimums (no minimum applied). Each names what a person fixes:
    # the schedule and its versions; the meter.
    overlaps = tuple(_VERSIONS_OVERLAP.get() or ())
    unsized = tuple(_METER_SIZE_NOT_RECORDED.get() or ())
    if overlaps or unsized:
        data = replace(
            data,
            warnings=bill_warnings.merged(
                data.warnings,
                tuple(
                    bill_warnings.schedule_versions_overlap(
                        service, str(facts.get("schedule") or ""), on_date, facts.get("versions") or ()
                    )
                    for service, on_date, facts in overlaps
                ),
                tuple(bill_warnings.meter_size_not_recorded(service, meter) for service, meter in unsized),
            ),
        )
    trace = _PRICING_TRACE.get()
    if trace:
        data = replace(data, pricing_trace={k: dict(v) for k, v in trace.items()})

    # ── STEP 5 OF THE R1–R7 CUTOVER · THE ONE FORK ───────────────────────
    # BR-BIL-870/871. `apply` returns `data` ITSELF — the same object, not a
    # copy — on every deployment that has not named a step, which is all of
    # them. So this line moves no figure on any bill and cannot: the ruled path
    # is not run at all while the setting is empty.
    #
    # It is here, at the END, and it is the ONLY place a rule crosses over.
    # Two forks for one decision is how two implementations come to disagree,
    # which is the defect this whole cutover exists to close — and this
    # module's own header says it about the preview: *"two implementations that
    # agree until they don't is the classic way a preview lies."*
    #
    # ⚠ A REFUSAL FROM A SWITCHED-ON RULE REFUSES THIS ACCOUNT, NEVER THE RUN
    # (BR-BIL-055, and JUDGMENT B of the 2026-08-21 cutover entry made the same
    # call for the jurisdiction refusal). One named row on the S31.2 exception
    # tab and the other 499 accounts still draft.
    try:
        return resolution_switch.apply(data, account=account, service_date=service_date)
    except resolution_switch.RuledPathRefused as refusal:
        raise GatherProblem(
            # Changes row 44 — a missing multiplier inside a Check pass is the
            # clerk's decision (`runs.METER_HAS_NO_MULTIPLIER`), not a block.
            getattr(refusal, "reason", None) or GATHER_RULED_PATH_REFUSED,
            refusal.sentence,
            service_code=refusal.service or None,
            # `DEF-RAT-7991` — the chain's CLERK sentence, carried the last hop
            # so `one_time._clerk_gap` never has to reach for `str(refusal)`.
            message_key=getattr(refusal, "message_key", None),
            clerk_detail=getattr(refusal, "clerk_detail", None),
            message_params=getattr(refusal, "message_params", None),
        ) from refusal


#: `BR-BIL-301` — a service the PLAN prices over a unit that has NO service
#: point for it. The `$0.00` line on the document carries this, so the reads
#: that collect the review list group on one constant rather than on prose.
UNCONNECTED_PLAN_SERVICE = "plan_service_not_connected"


def _services_taken_by_account(
    account: Any,
    *,
    period_start: date,
    period_end: date,
) -> tuple[str, ...] | None:
    """The services THIS ACCOUNT HOLDS during this period — `BR-BIL-1048`.

    🔒 rating math. HUMAN-REVIEW-PENDING (money path) — row in
    `12-governance/09-human-review-ledger.md`.

    **`BR-CUS-1101` (PO ruling 2026-09-25) made an account take a SUBSET of its
    unit's services, and said in its own text that billing did not yet narrow
    to it.** This is that narrowing's one read. `None` means nobody can tell —
    customers has not published the selector, or the account holds no
    overlapping agreement at all — and billing then narrows nothing and prices
    exactly what it priced before.

    ⚠ **IT IS THE ACCOUNT'S AGREEMENTS AND NOT THE UNIT'S POINTS, WHICH IS THE
    WHOLE DISTINCTION.** `BR-BIL-300` asks the UNIT which services exist; this
    asks the ACCOUNT which of them it bought. A unit can be connected for six
    and sell three.
    """
    read = _resolve("customers", "billed_service_codes_for")
    if read is None or account is None:
        return None
    codes = read(account, period_start=period_start, period_end=period_end)
    if codes is None:
        return None
    taken = tuple(sorted({str(code) for code in codes if code}))
    return taken or None


def _plan_services_not_taken(
    unit_id: Any,
    plan_id: Any,
    *,
    taken: tuple[str, ...] | None,
    scope_services: tuple[str, ...] | None,
    unconnected: tuple[str, ...],
    percent_bases: dict[str, str] | None = None,
) -> tuple[str, ...]:
    """The plan's services this unit IS connected for and the ACCOUNT DID NOT BUY.

    ⚠ **2026-09-30 — A %-OF-SERVICE (SEWER) IS TAKEN IFF ITS BASIS IS TAKEN
    (PO, option B: *"Sewer is taken whenever its basis service (water) is on
    the bill"*).** Sewer has no service point, so it can have no agreement of
    its own; asking the account for one would drop sewer from every bill.
    `percent_bases` (`{sewer: water}`) makes it follow its basis instead: the
    account holds water → sewer is taken; it does not → sewer is not taken
    either, with no line of any kind.

    ⚠ **THE TWO CASES BELOW WERE ARGUED WHEN A NOT-CONNECTED SERVICE PRINTED A
    `$0.00` LINE (BR-BIL-301, 2026-09-25). PO 2026-09-30 took that line away
    (*"sane no line - and use 0"*), so on the DOCUMENT the two cases now look
    the same — no line — and what still separates them is the clerk's REVIEW
    LIST: a service the property lacks is listed, one the customer declined
    is not.** The argument below is kept for that half.

    🔒 rating math. HUMAN-REVIEW-PENDING (money path).

    ⚠⚠ **THE TWO CASES THIS FUNCTION EXISTS TO KEEP APART, AND CONFUSING THEM
    IS THE WHOLE RISK OF `BR-BIL-1048`:**

      * **the property has NO CONNECTION for a plan service** — `BR-BIL-301`
        (PO 2026-09-25, option (b)): **a line at `$0.00`, marked *not
        connected*, on the document**. *We cannot supply it.*
      * **the account DID NOT TAKE a service the unit IS connected for** —
        `BR-BIL-1048`: **no line of any kind.** *They did not buy it.*

    Turn the second into a `$0.00` line and a customer reads a bill listing
    services they refused; turn the first into no line and yesterday's ruling
    is reversed in silence. So `unconnected` is EXCLUDED here by hand rather
    than left to fall out of the arithmetic — a service with no point cannot
    have an agreement, so every unconnected service would otherwise arrive here
    as *not taken* and be dropped.

    ⚠ **IT ONLY EVER SUBTRACTS FROM A NON-EMPTY SET.** `taken is None` answers
    `()` — narrow nothing. `customers.billed_service_codes_for` never answers
    an empty tuple for the same reason (see its docstring): an account narrowed
    to nothing is a bill refused on `GATHER_NO_TARIFF`, and an ABSENCE of rows
    is not a clerk's decision to buy nothing.
    """
    if taken is None:
        return ()
    schedules = _resolve("rating", "plan_rate_schedules")
    if schedules is None or plan_id is None:
        return ()
    held = set(taken)
    skipped = set(unconnected)
    bases = percent_bases or {}
    missing: list[str] = []
    for row in schedules(plan_id) or ():
        service_code = row.get("service_code")
        if not service_code:
            continue
        service_code = str(service_code)
        if scope_services is not None and service_code not in scope_services:
            continue
        if service_code in skipped:
            continue
        if service_code in bases:
            # B1 — taken iff the basis is, never by an agreement of its own.
            if bases[service_code] in held:
                continue
        elif service_code in held:
            continue
        if service_code not in missing:
            missing.append(service_code)
    return tuple(missing)


def _unconnected_plan_services(
    unit_id: Any,
    plan_id: Any,
    *,
    scope_services: tuple[str, ...] | None,
    serving_units: dict[str, str] | None,
    percent_bases: dict[str, str] | None = None,
    offered: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """The plan's services THIS UNIT IS NOT IN SERVICE FOR — `BR-BIL-300/301`.

    ── DEF-BIL-9793 (2026-10-06) · A `%`-OF-SERVICE NEEDS AN ADDRESS THAT
    OFFERS IT ─────────────────────────────────────────────────────────────
    🔒 rating math. HUMAN-REVIEW-PENDING (money path) — row in
    `12-governance/09-human-review-ledger.md`.

    Option B (below) took sewer's SERVICE POINT out of the question; it did not
    take the ADDRESS out. A premises declares which services it offers
    (`BR-MET-119`), and every other service is already bounded by it — a meter
    for a service the address does not offer is refused at the door, so no
    point, so no line. Sewer has no door, so it is asked here instead.
    **Measured (CR-171 §28.1, M6):** Foundry Works at 5 Foundry Way, an address
    offering electric, gas, water and solar, was billed **`$38.25` of sewer
    usage and a `$9.00` sewer base, and taxed on both**, because its plan prices
    sewer and it took water. `offered` is the anchor's
    `premises.services_available`: a list without the service → not in service,
    on the clerk's review list like any plan service the property lacks.
    ⚠ **`None` IS *NOBODY WAS ASKED*, NOT *OFFERS NOTHING*** (`DEF-762`), and
    narrows nothing — sewer then follows water exactly as before. A master
    account's covered units stand on the same premises (`BR-CUS-068`), so the
    anchor's list answers for all of them.

    ── AMENDED 2026-09-30 BY THREE PO RULINGS (decision log, that date) ──────
      * **No asset = not in service, even if the account took the service.**
        PO: *"if unit has 6 utility services and user only add 1 or 3 assets
        to it - it means you will consider only 3 service point exist"*, and
        *"this is correct sewer is exception becuase it is % of servcie"*. So
        a point counts only when `assets.asset_ids_for_service_point` names
        something on it (`_point_has_asset`); a gas point with no meter no
        longer reaches the run as a `no_meter` missing read that refuses the
        whole account. **`None` from that read is *nobody can tell* and counts
        the point as in service** — the three-valued rule below, one seam on.
      * **A `%`-of-service has no service point at all** (*"for % of service
        there will not be any service point"*). `percent_bases` maps it to its
        basis (`{sewer: water}`); its own points are never asked, and it is
        not in service exactly when its basis is not — or when the plan prices
        no basis at all, since then there is nothing for it to be a percentage
        of. Measured before the fix on the BR-BIL-1048 account: **$76.50 a
        month** of sewer was billed `$0.00 (not connected)`.
      * **Not in service prints NO line** (*"sane no line - and use 0"*). The
        answer here no longer reaches the document at all; it feeds
        `AccountBillingData.unconnected_services`, which is the clerk's review
        list (`runs._decisions_for`) and the one-time bill's Services table.

    🔒 rating math. HUMAN-REVIEW-PENDING (money path) — row in
    `12-governance/09-human-review-ledger.md`.

    **PO ruling 2026-09-25, verbatim, option (b) of three:** *"Question · When
    a plan includes a service the property has no connection for, what should
    happen? b · Bill it at $0.00, and say so"*. Option (a) — bill it silently —
    and option (c) — keep stopping the bill — were both declined.

    ── THE DEFECT, MEASURED (`DEF-BIL-6759`) ────────────────────────────────
    A counting capacity service whose schedule names sizes REFUSED THE WHOLE
    ACCOUNT when the unit had no service point for it, and the refusal blamed a
    missing SIZE. Measured on a seeded water + sewer + fire tenant on real
    PostgreSQL 16, gathering all **75** accounts directly:
    **21 refused on `connection_size_unresolved_for_sized_schedule`, 20 of them
    over a unit with no fire service point, and 0 of the 35 accounts that
    priced had a plan service with no point.** The whole bill stopped — the
    customer's water with it.

    ⚠ **THIS SETTLES THE PRICE `BR-BIL-300` EDGE 2 LEFT OPEN, AND THE
    SUPERSESSION IS STATED RATHER THAN ASSUMED (CLAUDE.md law 13).** Edge 2
    reads *"Plan has a schedule, unit has no service point - this will also not
    happen pratcially; - we have to bill it"* (PO 2026-08-27). **The
    measurement contradicts its *"will not happen practically"*: it happens on
    20 of 75 accounts of one seeded utility.** *"We have to bill it"* stands —
    the service still reaches the document — and what it COSTS is now ruled at
    `$0.00`.

    ⚠ **WHY THIS IS NOT THE `{}` THE DEFECT ROW PROPOSED, AND IT IS A MONEY
    ARGUMENT RATHER THAN A TIDINESS ONE.** Answering `{}` from
    `metering.selectors.billable_asset_size_counts` would route this into
    `_per_size_configs`' empty-map arm — **which builds a config carrying this
    service's base charge**. A base charge is charged because A CONNECTION
    EXISTS (`BR-RAT-080`, stated in `_per_size_configs`' own docstring), so
    that arm would bill the STANDING CHARGE for a connection that does not
    exist. ⚠ **THIS SENTENCE SAID *"which passes `plan_base`"* UNTIL
    2026-09-28** — that parameter is gone (`DEF-BIL-7170`) and the base now
    comes from the service's CHARGE CODE, which is per service and answers for
    an empty unit exactly as readily. **The argument is unchanged and its
    mechanism is not**, which is why it is restated rather than left to be
    inferred from a name that no longer exists. That is not the ruled
    `$0.00`; it is a different and more expensive ruling. It also could not
    *say so*: the empty-map arm produces an engine-priced config whose
    description comes from the schedule. **So `{}` keeps the one meaning its
    docstring gives it — *the utility looked at this connection and there is
    nothing on it* — and *there is no connection here* is named separately.**

    ── THREE-VALUED, LIKE EVERY OTHER ABSENCE ON THIS PATH ──────────────────
    An unpublished `service_points_for`, or a call with no unit, means **nobody
    can tell**, and this answers `()` — every service is priced exactly as it
    is priced today. Inventing a reconciliation from a seam that is not there
    would zero a customer's whole bill on a fact nobody supplied, which is the
    same reasoning `_unpriced_unit_service_lines` states for the mirror case.

    ⚠ **A UNIT WITH NO POINTS AT ALL IS NOT SPECIAL-CASED HERE AND DOES NOT
    NEED TO BE.** Every service drops out, `_tariffs_for_plan` ends with no
    configs, and its existing `GATHER_NO_TARIFF` refusal fires with the
    sentence it already carries: *"A bill with no services is not a $0.00 bill
    — it is a configuration problem a human must see."* That guard is the right
    one and it is left exactly where it is.

    `serving_units` is honoured for the same reason `_tariffs_for_plan` honours
    it: on a master account the hallway's water and the irrigation's water are
    different connections on different units, so the question *is there a point
    for this service* is asked of the unit that actually serves it.
    """
    points_for = _resolve("metering", "service_points_for")
    if points_for is None or plan_id is None:
        return ()
    schedules = _resolve("rating", "plan_rate_schedules")
    if schedules is None:
        return ()
    bases = percent_bases or {}
    taken: dict[Any, set[str]] = {}

    def _codes(target: Any) -> set[str] | None:
        """The services this unit has a point IN SERVICE for.

        B2 — a point with nothing on it is no point. `_point_has_asset`
        answering `None` (assets unpublished) keeps the point: nobody looked.
        """
        if target is None:
            return None
        if target not in taken:
            taken[target] = {
                str(point.get("service"))
                for point in points_for(target) or ()
                if point.get("service")
                and _point_has_asset(point.get("id"), point.get("service")) is not False
            }
        return taken[target]

    plan_codes: list[str] = []
    missing: list[str] = []
    for row in schedules(plan_id) or ():
        service_code = row.get("service_code")
        if not service_code:
            continue
        service_code = str(service_code)
        if scope_services is not None and service_code not in scope_services:
            continue
        plan_codes.append(service_code)
        if service_code in bases:
            continue  # B1 — decided from its basis below, never from a point
        codes = _codes((serving_units or {}).get(service_code, unit_id))
        if codes is None:
            continue
        if service_code not in codes and service_code not in missing:
            missing.append(service_code)
    # B1 — a %-of-service follows its basis. Its basis not in service, or not
    # priced by this plan at all, leaves it nothing to be a percentage of.
    for service_code in plan_codes:
        if service_code not in bases or service_code in missing:
            continue
        basis = bases[service_code]
        if basis in missing or basis not in plan_codes:
            missing.append(service_code)
        elif offered is not None and service_code not in offered:
            # DEF-BIL-9793 — the address does not offer it (BR-MET-119).
            missing.append(service_code)
    return tuple(missing)


def _services_the_address_offers(unit: Any) -> tuple[str, ...] | None:
    """The anchor premises' `services_available`, or None when nobody was asked.

    🔒 rating math. HUMAN-REVIEW-PENDING (money path) — `DEF-BIL-9793`.
    Read off the same `unit.premises` `_premises_geography` reads, with the
    same `getattr` posture: an absent premises or column is *nobody can tell*
    and narrows nothing. `[]` is a clerk saying *offers nothing* and is kept.
    """
    premises = getattr(unit, "premises", None)
    if premises is None:
        return None
    offered = getattr(premises, "services_available", None)
    if offered is None:
        return None
    return tuple(str(code) for code in offered if code)


def _percent_of_service_bases(
    plan_id: Any,
    service_date: date,
    scope_services: tuple[str, ...] | None,
) -> dict[str, str]:
    """`{service: basis service}` for every `%`-of-service the plan prices.

    🔒 rating math. HUMAN-REVIEW-PENDING (money path) — row in
    `12-governance/09-human-review-ledger.md`.

    PO 2026-09-30, option B: sewer has NO service point and is billed whenever
    its basis (water) is. Which services are `%`-of-service, and of what, is
    the RATE SCHEDULE VERSION's fact (`model`, `basis_service`), so it is read
    from rating's own `pricing_inputs` at the SERVICE DATE — never from a
    service code, because `sewer` is a percentage of water only on a tenant
    that priced it that way.

    ⚠ **THREE-VALUED LIKE EVERY SEAM ON THIS PATH.** An unpublished rating
    read, or no version in force, answers *not a percentage* for that service,
    which is today's behaviour: its point decides, and `_tariff_config_for`
    then refuses a missing version by name exactly as it always did.
    """
    schedules = _resolve("rating", "plan_rate_schedules")
    pricing = _resolve("rating", "pricing_inputs")
    if schedules is None or pricing is None or plan_id is None:
        return {}
    bases: dict[str, str] = {}
    for row in schedules(plan_id) or ():
        service_code = row.get("service_code")
        if not service_code or row.get("tariff") is None:
            continue
        if scope_services is not None and service_code not in scope_services:
            continue
        inputs = _call_pricing_inputs(pricing, row["tariff"], service_date, None)
        if not inputs or inputs.get("model") != "percent_of_service":
            continue
        basis = inputs.get("basis_service")
        if basis:
            bases[str(service_code)] = str(basis)
    return bases


def _meters_by_service(readings: tuple[ServiceReading, ...]) -> dict[str, tuple[str, ...]]:
    """`{service: (meter, meter, …)}` for every service metering SPLIT per meter.

    PO 2026-09-30: *"both meter should be build in metered case also - as a
    speearte line"*. Metering names a reading's `asset_id` only where a METERED
    point carries two or more in-service meters, so this is empty on every
    account with one meter per service — every bill before the ruling — and
    `_tariffs_for_plan` then builds exactly the one config it always built.
    Order is the readings' own (metering orders by asset number), so a
    re-run lists the meters the same way.
    """
    meters: dict[str, list[str]] = {}
    for reading in readings or ():
        asset_id = getattr(reading, "asset_id", None)
        if not asset_id:
            continue
        seen = meters.setdefault(str(reading.service_code), [])
        if str(asset_id) not in seen:
            seen.append(str(asset_id))
    return {code: tuple(ids) for code, ids in meters.items()}


def _swapped_services(readings: tuple[ServiceReading, ...]) -> frozenset[str]:
    """🔒 The services whose per-meter readings are the two PARTS of one meter
    swapped inside the period (each reading carries its own `meter_parts`
    entry, `runs._meter_swap`). PO 2026-10-01, *"B · Price each meter
    separately"* (BR-BIL-1062): each part climbs the tiers from the bottom on
    its own config, and — one connection over one period — the base charge
    and the service minimum ride on the FIRST part (the old meter) only. Empty
    on every bill without a swap, so nothing else moves."""
    return frozenset(
        str(reading.service_code)
        for reading in readings or ()
        if getattr(reading, "meter_parts", ()) and getattr(reading, "asset_id", None)
    )


def _tariffs_for_plan(
    plan_id: Any,
    unit_id: Any,
    service_date: date,
    scope_services: tuple[str, ...] | None,
    *,
    premises: dict[str, Any] | None = None,
    serving_units: dict[str, str] | None = None,
    customer_class: str | None = None,
    skip_services: tuple[str, ...] = (),
    meters_by_service: dict[str, tuple[str, ...]] | None = None,
    swapped_services: frozenset[str] = frozenset(),
    counted_empty: list[str] | None = None,
) -> tuple[Any, ...]:
    """One tariff config per service the ACCOUNT'S UNIT takes, priced by the plan.

    ── 2026-09-30 · ONE CONFIG PER METER (B5) ────────────────────────────────
    PO: *"both meter should be build in metered case also - as a speearte
    line"* — option A as put: each meter's usage on its OWN tier ladder with
    its OWN base, on its own lines. Worked: two water meters at 6.1 kgal each
    (tiers $3.25 to 5 kgal, $4.50 above; base $8.00) bill **2 × ($21.20 +
    $8.00) = $58.40**, where the tip billed **$29.20** and the second meter was
    never charged. `meters_by_service` (from the readings, see
    `_meters_by_service`) names the meters; each config is the service's
    ordinary config with `asset_id` stamped, so `measure_consumption` pairs it
    with ITS meter's reading and the engine stamps the meter on its lines. The
    service's MINIMUM applies to EACH meter, on its own line — PO ruling
    2026-09-30 (decision log *"SIX ANSWERS"*, (4)): *"consider them 2 lines anc
    charge"*. Worked: minimum $10.00, meter A usage $6.00 → $10.00, meter B
    $14.00 → $14.00, bill **$24.00** (not $20.00). (Until that ruling this lane
    had put the minimum on the first meter only.) Empty on every account with
    one meter per service: byte-identical.

    `counted_empty` collects a COUNTED service whose point has assets and none
    in service on the period end (`_per_size_configs` answers no config for
    it); `gather_account` adds it to the not-in-service list (B2).

    ⚠ **`skip_services` CARRIES TWO DIFFERENT FACTS AND THEY REACH THE SAME
    PLACE ONLY BECAUSE NEITHER PRODUCES A TARIFF.** `BR-BIL-301`'s services —
    the property is not in service for it — go on to the clerk's review list
    (they printed a `$0.00` line until PO 2026-09-30, *"sane no line - and use
    0"*); `BR-BIL-1048`'s — the ACCOUNT did not buy it — go nowhere at all.
    Both are computed by `gather_account` and passed in, never derived here,
    and `_plan_services_not_taken` argues why they must not be merged earlier.

    ⚠ **`skip_services` IS `BR-BIL-301`'S HALF AND IT IS PASSED IN, NEVER
    DERIVED HERE.** `_unconnected_plan_services` answers which of the plan's
    services this unit is not in service for, and `gather_account` carries
    them to the review list. This function drops them so that no
    tariff, **and therefore no base charge**, is built for a connection that
    does not exist (`BR-RAT-080`). `()` on every caller that predates the
    ruling and on every account whose unit takes everything its plan prices —
    which is every bill this product has issued — so nothing below is reached
    on the ordinary path."

    A plan is a BUNDLE (PO ruling 2026-08-11): a house on electric + water +
    trash is on one plan that resolves to a schedule per service. The run's
    service scope narrows it — and an unchecked service is an EXPLICIT recorded
    choice (US-BIL-001 §5), never a silent skip, which is why the scope is a
    filter here rather than an absence upstream.

    ── THE TWO FACTS ADDED 2026-08-21 ARE BOTH PER-SERVICE ───────────────────
    The connection SIZE (DEF-484) is per service because a house's water meter
    and its electric service are different connections, and the per-size ladder
    hangs off the SCHEDULE, which is per service. The jurisdiction FACTOR
    (BR-RAT-102) is per service because §A4 S2 needs it to be: *"BASE-S $8.00
    (flat everywhere — the multiplier does NOT touch sewer)"* while the electric
    base beside it moves. So both are resolved inside this loop, once per
    service, rather than once per account.

    The plan's jurisdiction pricing is read ONCE for the whole plan (it is a
    property of the plan, not of the service) and the exempt-service list is
    applied per service. `premises` is the caller's — this function is given the
    facts, because `_premises_geography` is the one place billing reads a
    premises and a second read here would be a second seam.

    ── `serving_units` — WHOSE CONNECTION, ON A MASTER ACCOUNT (BR-CUS-068) ───
    A master account's one bill covers several common areas, and the connection
    SIZE is a fact about a CONNECTION: the hallway's electric service and the
    irrigation's water service are different physical things on different
    units. So the size for each service is resolved against the covered unit
    that actually SERVES it, and only the size — the plan, the premises, the
    jurisdiction and the tariff versions are the same for the whole bill
    (`_coverage_facts` refuses a coverage where they would not be, OQ-334/335).
    Empty or absent means "every service is the anchor's", which is every
    ordinary account and therefore every bill this product has issued.

    ── WHICH SERVICES, FROM THE UNIT (DEF-1060) — AND WHERE THAT LIVES ──────
    **PO ruling 2026-08-27, closing OQ-601 on mechanism, verbatim:** *"how do
    you decide how many services to be billed on that account? You look at
    account, then you look at unit asscoaited with that account, how many meters
    and how many services are atatched to it and decide how you bill the
    services on account. - your logic need to fix here"*.

    **The services a bill charges are the services attached to the UNIT the
    account occupies; the plan supplies the PRICE for each and no longer
    supplies the LIST.** Until this argument existed, this function iterated
    `rating.plan_rate_schedules(plan_id)` and read the unit only to resolve the
    connection SIZE — so Ana Alvarez's badges read WATER · SEWER · TRASH and her
    June bill charged **`$64.57`** for water and sewer with no trash line, no run
    exception and no note (DEF-1060).

    ⚠ **THE UNIT ADDS SERVICES AND NEVER REMOVES THEM, AND THAT IS A SECOND PO
    RULING AND NOT AN IMPLEMENTATION CHOICE.** OQ-601's edge 2, verbatim: *"2
    Plan has a schedule, unit has no service point - this will also not happen
    pratcially; - we have to bill it"*. So the plan's schedules are still priced
    in full, exactly as before, and the reconciliation below is purely
    ADDITIVE — which is also why every bill this product has issued is
    byte-identical and no ❄️ B5 figure can move: a unit whose service points are
    a subset of its plan's services reaches not one new line.

    ⚠ **THE RECONCILIATION IS NOT IN THIS FUNCTION AND THAT IS DELIBERATE.**
    Under `OQ-670` (PO 2026-08-27) a unit service the plan prices nowhere bills
    a **`$0.00` LINE**, not a tariff — there is no schedule, so there is no
    model, no rate and no billed unit to build one from, and inventing any of
    them is what CLAUDE.md rule 3 forbids. So `_unpriced_unit_service_lines`
    builds a `RatedLine` and `gather_account` carries it, and this function goes
    on doing exactly one job: turning the plan's schedules into tariffs.
    """
    plan_schedules = _resolve("rating", "plan_rate_schedules")
    if plan_schedules is None:
        # Rating has not published the per-service resolver. Reported as a
        # problem on the account rather than silently billing no services,
        # which would produce a base-charge-only bill that looks deliberate.
        raise GatherProblem(
            GATHER_NO_TARIFF,
            "rating has not published plan_rate_schedules, so a plan cannot be "
            "resolved to its per-service tariffs. No service is dropped quietly.",
        )
    jurisdiction = _plan_jurisdiction(plan_id)
    configs = []
    for row in plan_schedules(plan_id):
        service_code = row.get("service_code")
        if scope_services is not None and service_code not in scope_services:
            continue
        # ── NOT A TARIFF, FOR ONE OF TWO REASONS (see the docstring) ───────
        # BR-BIL-301 (PO 2026-09-25, (b)) — there is no CONNECTION here, so not
        # a tariff and therefore not a base either: a standing charge is
        # charged because a connection exists (BR-RAT-080). Since 2026-09-30
        # no line says so on the bill; the review list does.
        # BR-BIL-1048 — the ACCOUNT did not take this service. No tariff, no
        # base, and no line anywhere: it is not theirs.
        if service_code in skip_services:
            continue
        serving_unit = (serving_units or {}).get(service_code, unit_id)
        # ── CR-063 · ONE TARIFF PER SIZE FOR A COUNTING CAPACITY SERVICE ────
        # Decision log 2026-09-02: *"For a capacity service billed by a COUNT —
        # today trash and fire — the one-size-per-connection rule does not
        # apply. The bill carries ONE LINE PER SIZE, and the quantity on each
        # line is the count of items of that size."* `None` from this seam is
        # *do not group*, which is every metered service and every capacity
        # service that SUMS — so nothing but trash and fire changes shape.
        size_groups = _size_groups_for(serving_unit, service_code, service_date)
        if size_groups is not None:
            per_size = _per_size_configs(
                row,
                service_code,
                service_date,
                size_groups,
                customer_class=customer_class,
                jurisdiction=jurisdiction,
                premises=premises or {},
            )
            if not per_size and counted_empty is not None:
                counted_empty.append(str(service_code))
            configs.extend(per_size)
            continue
        meters = (meters_by_service or {}).get(str(service_code), ())
        configs_before = len(configs)
        connection_size = _connection_size_for(serving_unit, service_code)
        configs.append(
            # ⚠ **THE PLAN'S OWN BASE CHARGE IS NO LONGER HANDED DOWN HERE —
            # `DEF-BIL-7170`, PO 2026-09-28.** This call passed
            # `row.get("base_charge")` as a fourth positional, and that figure
            # is the RETIRED column: *"we will never take default value from
            # plan $8.0 - that is retired"*. It is still on `row`, because the
            # plan still stores it and still shows it; nothing on the money
            # path reads it.
            _tariff_config_for(
                row["tariff"],
                service_code,
                service_date,
                size_class=connection_size,
                # BR-RAT-088 · BR-RAT-108 — a base charge code may be scoped to
                # a customer class (`BASE-W` residential $8.00 beside
                # `BASE-W-COM` commercial $15.00 on this very tenant), so the
                # class is a narrowing fact for the BASE and not only for fees.
                customer_class=customer_class,
                jurisdiction_factor=_jurisdiction_factor_for(
                    service_code,
                    jurisdiction=jurisdiction,
                    premises=premises or {},
                ),
                # BR-RAT-028 — mode (A) moved onto the rate schedule version on
                # 2026-09-10 (PO ruling; `rating/0030`+`0031`) and is read from
                # `pricing_inputs` inside `_tariff_config_for`; this caller only
                # says the config may carry it. Mode (B), the plan floor, is
                # still the plan's, and `.get` for the same reason the base
                # charge above uses one: a deployment whose rating lane has not
                # landed states no floor and prices exactly as it does today,
                # rather than raising a KeyError mid-run.
                carries_service_minimum=True,
                plan_minimum_bill_amount=row.get("plan_minimum_bill_amount"),
                # PO 2026-10-01 — a SUMMING capacity service's base, by size ×
                # count. `None` for every other service (metering decides).
                base_size_counts=_base_size_counts_for(serving_unit, service_code, service_date),
            )
        )
        if connection_size is None:
            # PO 2026-10-01 — no recorded size, no minimum; name the meter.
            _flag_unsized_meters(serving_unit, service_code)
        entry = _trace(str(service_code))
        if entry is not None and "sizes" not in entry:
            # One base for the service: the connection's size (or none), no
            # count — a metered or flat-based service's whole trace.
            entry["sizes"] = [
                {
                    "size": connection_size,
                    "size_label": _size_label_for(str(service_code), connection_size),
                    "count": None,
                    "base_each": _money_text(configs[-1].base_charge),
                    "base_total": _money_text(configs[-1].base_charge),
                    "base_priced": not _size_was_unpriced(str(service_code), connection_size),
                    "price_each": None,
                }
            ]
        if meters:
            # B5 — the one config just built, once per meter. Same version,
            # same ladder, same base, same minimum (each meter its own floor,
            # PO 2026-09-30); only the meter differs.
            shared = configs.pop()
            assert len(configs) == configs_before
            swapped = str(service_code) in swapped_services
            for index, meter in enumerate(meters):
                if swapped and index > 0:
                    # 🔒 PO 2026-10-01 (BR-BIL-1062) — a SWAP is one connection
                    # over one period: the new meter's part is priced on its
                    # own ladder from the bottom, with no second base and no
                    # second minimum (judgment, decision log 2026-10-01).
                    configs.append(
                        replace(shared, asset_id=meter, base_charge=None, minimum_amount=None)
                    )
                    continue
                configs.append(replace(shared, asset_id=meter))
    if not configs:
        raise GatherProblem(
            GATHER_NO_TARIFF,
            f"plan {plan_id} resolves to no tariff for any service in this "
            "run's scope. A bill with no services is not a $0.00 bill — it is "
            "a configuration problem a human must see.",
        )
    return tuple(configs)


def _unpriced_unit_service_lines(
    unit_ids: tuple[str, ...],
    *,
    priced_services: tuple[str, ...],
    scope_services: tuple[str, ...] | None,
    plan_id: Any,
    account_no: str,
    taken_services: tuple[str, ...] | None = None,
    not_in_service: tuple[str, ...] = (),
) -> tuple[Any, ...]:
    """DEF-1060 — a service the UNIT takes and the PLAN prices nowhere, at `$0.00`.

    ⚠ **2026-09-30 — ONLY OVER A POINT THAT IS IN SERVICE.** PO: *no asset =
    not in service*, and not in service prints no line (*"sane no line - and
    use 0"*). A point with nothing on it (`_point_has_asset` is False), or a
    service in `not_in_service`, is skipped: without this, every plan service
    the ruling takes out of service would come straight back as a `$0.00`
    *(not priced on this plan)* line — the removed line wearing another
    sentence. `None` from the assets read (nobody can tell) keeps the point.

    🔒 HUMAN-REVIEW-PENDING (money path) — row in
    `12-governance/09-human-review-ledger.md`.

    ── THE DEFECT, MEASURED ─────────────────────────────────────────────────
    Two independent sources describe *this account's services* and nothing
    reconciled them. The BADGES come from ACTIVE SERVICE AGREEMENTS
    (`customers.selectors.service_codes_for` → metering's service points,
    BR-CUS-015); the BILL came from the PLAN's rate schedules. **A service in
    the first and not the second produced no line, no run exception and no note
    on the document.** Ana Alvarez `AC-2026-00001` is the Product Owner's own
    case: badges WATER · SEWER · TRASH, June bill `BL-2607-000001` at **`$64.57`**
    over six lines, none of them trash. This function is the reconciliation, and
    after it a service cannot leave an account's bill in silence.

    ── WHAT IT COSTS: `$0.00`, AND THAT IS A RULING, NOT A DEFAULT (OQ-670) ──
    **PO verbatim, 2026-08-27:** *"Ana's trash — what does a service cost when
    the plan prices it nowhere? 🔒 - (b) Bill $0.00"*.

    ⚠ **THIS OVERRULES THE RECOMMENDATION THIS LANE MADE, AND THE CODE SAYS SO
    RATHER THAN READING AS AGREEMENT.** The lane built (a) *refuse by name* and
    put the collision back; the PO chose (b) with the trade stated — that a zero
    line is *"the same silence you caught, wearing a line item"* — and with the
    figure in front of them: **`$15.00` a cart across Silver Creek's 48 trash
    accounts is `$720.00` a month**, uncollected since the demo was seeded.

    ⚠ **THE `$720.00` IS NOT WRITTEN OFF AND THAT IS THE POINT OF THE ZERO.**
    The moment a clerk adds trash to the plan (S9 base charge, S11 rate) it
    prices normally and every later bill collects it. **What the zero line buys
    is VISIBILITY: the gap is on the document, where a customer and a clerk both
    read it, instead of being invisible in a silence.** A refusal would have made
    it visible too and stopped 48 bills to do it; the PO weighed those and chose
    the line.

    ⚠⚠ **THE SUPERSESSION IS NARROW AND MUST NOT BE WIDENED.** CR-013 part 1
    (PO 2026-08-19) — *"Blank base = size not served"*, on which
    `_base_charge_for` REFUSES by name (DEF-277) — **still stands everywhere it
    already applied.** It is superseded ONLY for the case the ruling names: a
    service the UNIT derives that the plan prices **nowhere at all** — no rate
    schedule and therefore no base row. A blank base on a size the plan DOES
    serve still refuses, unchanged, and it refuses in `_base_charge_for`, which
    this function never reaches: there is no schedule here to read a base from,
    so the two paths cannot be confused by a later reader.

    ── WHY THE LINE RIDES `fees` AND CARRIES NO UNIT, NO RATE, NO QUANTITY ───
    A `RatedLine` and not a `TariffConfig`, deliberately. A synthetic tariff
    would have to state a pricing MODEL, a `unit_price` and a `billed_unit`
    before the engine would touch it — `normalize` refuses a quantity with no
    unit (CLAUDE.md rule 3) and the flat plugin refuses a `None` price — and
    **every one of those three would be invented**, because a plan that prices
    the service nowhere states none of them. The seam's fee channel is the
    sanctioned way to hand an ALREADY-PRICED line to the engine: its own
    `fee_candidates` carries `kind` and `service` faithfully and says in its own
    words that it *"does not only carry fees — a multi-pass bill hands
    already-priced usage/base lines through it"*. So the line is `kind="base"`,
    names its service, and leaves `quantity`, `unit` and `unit_price` at `None`,
    which is the truth: nobody measured anything and nobody quoted a rate.

    `taxable=True` because a base line IS in the tax base (B4.2) and the
    classification should not lie; at `0.0000` it moves no tax base by any
    arithmetic. **`$0.0000` — money is stored to 4 decimals and displayed at 2
    (hard rule 2), so the document reads `$0.00`.**

    ── WHAT STAYS SILENT ────────────────────────────────────────────────────
    * **Every account whose unit takes only services its plan prices** — which
      is every account this product has ever billed, ❄️ GT-17's five-service
      reference bill included. No extra line, no extra query.
    * **A service the run's scope UNCHECKED** (US-BIL-001 §5) — that is an
      EXPLICIT recorded choice by the clerk who set the scope, not a silence.
    * **A deployment where metering has not published `service_points_for`** —
      nobody can tell what the unit takes, and inventing a reconciliation from a
      seam that is not there would be a guess about a customer's subscription.

    ⚠ **ONE CONSEQUENCE, STATED RATHER THAN DISCOVERED.** The zero line NAMES a
    service, so BR-BIL-010 resolves its revenue account from that service at
    issue — and a tenant that has never mapped trash to a revenue account will
    have the bill refused there by name (US-BIL-007 TC-5, the ratified
    behaviour). That is not new machinery and not a silent failure, but it is a
    second place this ruling can be felt, and it belongs in writing.
    """
    points_for = _resolve("metering", "service_points_for")
    if points_for is None:
        return ()
    priced = set(priced_services)
    held = set(taken_services) if taken_services is not None else None
    missing: list[str] = []
    for unit_id in unit_ids:
        for point in points_for(unit_id) or ():
            service_code = point.get("service")
            if not service_code or service_code in priced:
                continue
            if scope_services is not None and service_code not in scope_services:
                continue
            # ── BR-BIL-1048 · THE ACCOUNT DID NOT BUY THIS ─────────────────
            # `None` is *nobody can tell* and changes nothing, which is every
            # bill issued before `BR-CUS-1101`. A non-empty set is the
            # account's own agreements: a connection on the unit that this
            # account never took is not its gap to state, and a `$0.00` line
            # for it would put a service the customer refused on their bill.
            if held is not None and service_code not in held:
                continue
            if (
                service_code in not_in_service
                or _point_has_asset(point.get("id"), service_code) is False
            ):
                continue
            if service_code not in missing:
                missing.append(service_code)
    return tuple(
        rating_seam.RatedLine(
            kind="base",
            # WHAT A CUSTOMER READS. The gap is stated on the document rather
            # than dressed as a free service: "no charge" would read as a
            # decision to give it away, and the utility has not decided that —
            # nobody has priced it. Wording is a stated absence against the
            # ruling, which settled the FIGURE and not the sentence.
            description=f"{service_code} (not priced on this plan)",
            amount=Decimal("0.0000"),
            taxable=True,
            service=service_code,
        )
        for service_code in missing
    )


def _charge_fees_for(
    plan_id: Any,
    service_date: date,
    customer_class: str | None,
    services: tuple[str, ...],
) -> tuple[rating_seam.RatedLine, ...]:
    """`BR-RAT-117` — the charge codes that belong on this ordinary bill.

    PO ruling 2026-08-22: *"ruccuring and Autom apply land on bill"*. Rating
    owns the whole answer (`billable_charge_codes` applies the flag gate, the
    plan's own `plan_charge_rules` binding, R4's service/class narrowing and
    BR-RAT-088's base exclusion); this function only projects its dicts onto
    the seam's shape, `.get` on every field like every other cross-module
    read in this file.

    ⚠ **`taxable` COMES FROM THE CODE, NOT FROM A CONSTANT, and the two rules
    that meet here are worth stating.** B4.2 says a fee is never in the tax
    base; BR-RAT-116 (PO 2026-08-22) says a tax is levied on *"Utility
    service charge + base fees"*. They are reconciled by `charges.
    taxable_default`, which is the tenant's own declaration per code and
    defaults FALSE — so B4.2's posture is what an unconfigured code gets, and
    a tenant that has declared a base fee taxable gets BR-RAT-116's reading.
    Neither rule is bent by this file, and the judgment is in the decision log.

    ⚠ **AN UNPUBLISHED SEAM YIELDS NO CHARGE LINES**, the same degrade
    `_discounts_for` takes and for the same reason — it is the UNDERCHARGE
    direction on a mixed deployment, visible because the resolver is asked
    for BY NAME here rather than by nothing.
    """
    resolver = _resolve("rating", "billable_charge_codes")
    if resolver is None:
        return ()
    rows = (
        resolver(
            plan_id,
            service_date,
            customer_class=customer_class,
            services=services,
        )
        or ()
    )
    return tuple(
        rating_seam.RatedLine(
            kind="fee",
            description=row.get("name") or row["code"],
            amount=Decimal(str(row["amount"] or "0")),
            taxable=bool(row.get("taxable")),
            service=row.get("service"),
            # ⚠ **WHICH CODE THIS LINE IS** (DEF-714, 2026-08-25) — the fact
            # that lets the line be ISSUED. BR-BIL-010 gives every charge code
            # its own GL account and issue resolves it from this id; without it
            # the line reached issue anonymous, was refused, and the bill died
            # with it. So a tenant that configured any recurring or auto-apply
            # code — the very thing BR-RAT-117 asks for — could issue no bill
            # at all, while the DRAFT looked perfectly correct.
            #
            # `.get`, like every other field here: rating's row shape is
            # another module's contract, and a deployment whose rating half
            # predates DEF-714 degrades to an unattributed fee line that issue
            # refuses BY NAME, never to a KeyError mid-run.
            charge_id=row.get("id"),
        )
        for row in rows
    )


def _discounts_for(
    account: Any, plan_id: Any, service_date: date
) -> tuple[rating_seam.DiscountRule, ...]:
    """The account's GRANTED discounts, as the seam's `DiscountRule`s (DEF-502).

    Rating owns the whole answer — `billable_discount_rules` applies BOTH gates
    (the open enrolment, BR-RAT-069; the plan's binding, BR-RAT-110) and
    resolves everything time-dependent at the service date, so this function
    only projects its dicts onto the seam's shape, `.get` on every field for
    the reason every other cross-module read in this file gives.

    ⚠ AN UNPUBLISHED SEAM YIELDS NO DISCOUNTS — which is the pre-DEF-502
    behaviour on every bill, and the stated trade is worth reading: it is the
    OVERCHARGE direction (an enrolled customer pays full price), the very
    defect this hop closes, chosen over refusing every bill of a deployment
    whose rating half has not landed. Both halves land in one commit, so the
    degrade is a posture for mixed deployments, not a state this repo ships —
    and unlike DEF-502 itself the absence is now VISIBLE: the resolver is
    asked for BY NAME here, not by nothing.
    """
    resolver = _resolve("rating", "billable_discount_rules")
    if resolver is None:
        return ()
    rows = resolver(getattr(account, "id", None), plan_id, service_date) or ()
    return tuple(
        rating_seam.DiscountRule(
            code=row["code"],
            name=row.get("name") or row["code"],
            discount_type=row.get("discount_type") or "",
            value=_decimal(row.get("value") or 0),
            currency=row.get("currency") or "",
            applies_to=row.get("applies_to") or "whole_bill",
            verified=bool(row.get("verified", True)),
            proof_before_first_reduction=bool(row.get("proof_before_first_reduction", True)),
            applies_to_service=row.get("applies_to_service"),
            applies_to_charge_codes=tuple(row.get("applies_to_charge_codes") or ()),
            cap_per_bill=_decimal_or_none(row.get("cap_per_bill")),
            cap_year_remaining=_decimal_or_none(row.get("cap_year_remaining")),
            cap_lifetime_remaining=_decimal_or_none(row.get("cap_lifetime_remaining")),
            budget_remaining=_decimal_or_none(row.get("budget_remaining")),
            exhaustion_behaviour=row.get("exhaustion_behaviour") or "suspend",
            bill_floor_amount=_decimal(row.get("bill_floor_amount") or 0),
            stacking_precedence=int(row.get("stacking_precedence") or 100),
            stacks_with_others=bool(row.get("stacks_with_others", True)),
            exclusivity_group=row.get("exclusivity_group"),
        )
        for row in rows
    )


def _taxes_for(
    plan_id: Any,
    service_date: date,
    *,
    customer_class: str | None = None,
    premises: dict[str, Any] | None = None,
    services: tuple[str, ...] | None = None,
    account_id: Any = None,
) -> tuple[Any, ...]:
    """The plan's tax rules (PO ruling 2026-08-11: tax is a BILL-level concept
    and the PLAN carries the rate — *"Tax rates are for bill not for service"*).

    An absent resolver yields NO taxes rather than a guessed rate: a bill
    missing its tax is visibly wrong on the preview, where a bill carrying an
    invented rate is not.

    `tax_id` travels with the rate (BR-BIL-069, PO ruling 2026-08-11 closing
    OQ-116) — WHICH authority's tax this is, so the line it produces can name
    the 2200-series account that authority is owed into. `.get` rather than
    `[...]`: rating's row shape is another module's contract, and a deployment
    where that lane has not landed must degrade to an untaggable line that
    BR-BIL-010 refuses AT ISSUE, by name, rather than to a KeyError in the
    middle of a 500-account run.
    """
    plan_taxes = _resolve("rating", "plan_tax_rules")
    if plan_taxes is None:
        return ()
    rows = tuple(
        _call_plan_taxes(
            plan_taxes,
            plan_id,
            service_date,
            customer_class=customer_class,
            premises=premises,
            services=services,
            account_id=account_id,
        )
    )
    # BR-RAT-106 (DEF-502) — each authority's statutory before/after answer,
    # batched in ONE read per account. An unpublished seam (or an id with no
    # row) yields None, which the engine reads as `before` — the column's own
    # default, inert on any bill without a discount.
    treatments = _discount_treatments(tuple(rule.get("tax_id") for rule in rows))
    return tuple(
        rating_seam.TaxRule(
            code=rule["code"],
            # DEF-RAT-9307 — the tax's Bill label, carried for the line's
            # WORDING only. `.get`: an older rating row states none and the
            # line reads as it always has.
            bill_label=rule.get("bill_label"),
            # `.get` + None-tolerant: a FLAT rule states no percent rate and a
            # PERCENT rule states no flat amount (BR-RAT-036 gives a tax one
            # form). `_decimal_or_none` keeps the absent one absent instead of
            # turning it into a 0 the engine would then price with.
            rate=_decimal_or_none(rule.get("rate")),
            tax_id=rule.get("tax_id"),
            flat_amount=_decimal_or_none(rule.get("flat_amount")),
            # ⚠ DEF-465 — WHAT THE PERCENT IS A PERCENT *OF*.
            #
            # `TaxRule.applies_to_services` has existed on the seam since it was
            # written and `compute_tax._base_for` has always read it; the only
            # missing hop was this one. Its default is `()` and the engine reads
            # `()` as "no restriction", so a tax scoped to [electric, gas] was
            # charged on the WHOLE bill: Silver Creek's City Franchise Fee at
            # 1.50% is $1.82 on design §A4 S1 and production computed $2.83.
            #
            # It looked correct because the tax ATTACHED correctly — rating's
            # `tax_applies_to` reads the same field as an applicability gate, so
            # the right accounts got the right taxes with the wrong base.
            #
            # `.get` with a `()` fallback, like every field above it and for the
            # reason the docstring gives: rating's row shape is another module's
            # contract, and a deployment where that lane has not landed must
            # degrade to today's behaviour rather than raise mid-run.
            applies_to_services=tuple(rule.get("applies_to_services") or ()),
            # BR-RAT-106 — see `_discount_treatments` above. Keyed on the
            # authority's tax id because the treatment is the TAX ROW's fact.
            discount_treatment=treatments.get(str(rule.get("tax_id") or "")),
            # ── BR-RAT-036's PER-UNIT FORM (CR-052 W5 task 16) ─────────────
            # A PROJECTION and nothing else: three figures rating already
            # stores, carried across the seam with no precedence taken and none
            # invented — the same shape `_tariff_config_for` takes for
            # BR-RAT-028's two minimum thresholds. WHICH tax applies is still
            # decided in `rating.selectors.plan_tax_rules` before a rule is
            # built (DEF-273), and HOW MANY UNITS are taxed is decided in the
            # engine's compute-tax stage from BR-RAT-042. Billing decides
            # neither and carries both.
            #
            # `.get` + None-tolerant like every field above it: a deployment
            # where rating has not published these keys degrades to a rule with
            # no per-unit form, which is exactly today's behaviour.
            per_unit_amount=_decimal_or_none(rule.get("per_unit_amount")),
            per_unit_uom=rule.get("per_unit_uom"),
            applies_above_units=_decimal_or_none(rule.get("applies_above_units")),
            # BR-RAT-036's per-METER form (`DEF-RAT-9278`, CR-165-BRC10 round
            # 2). A projection like the three above: rating states the amount,
            # the engine counts the meters. Absent key -> None -> today's bill.
            per_meter_amount=_decimal_or_none(rule.get("per_meter_amount")),
        )
        for rule in rows
    )


def _discount_treatments(tax_ids: tuple[Any, ...]) -> dict[str, str]:
    """`taxes.discount_treatment` per tax id, through rating's batched read.

    A separate seam from `plan_tax_rules` DELIBERATELY: that selector's block
    is another lane's working area this session, and the treatment is a fact
    about the TAX ROW that `discount_treatments_for_taxes` can serve without
    either lane touching the other's function. Absent seam → empty dict →
    every treatment None → `before` (the stored default) — today's behaviour
    on every bill, and inert wherever no discount applied.
    """
    resolver = _resolve("rating", "discount_treatments_for_taxes")
    if resolver is None:
        return {}
    wanted = tuple(tax_id for tax_id in tax_ids if tax_id)
    if not wanted:
        return {}
    return resolver(wanted) or {}


def _call_plan_taxes(resolver: Any, plan_id: Any, service_date: date, **facts: Any) -> Any:
    """Call rating's resolver with `account_id`, and WITHOUT it if it is older.

    The seam's contract is another module's, and this module has been burned by
    assuming a shape it could not see (`_taxes_for`'s own `.get` calls, three of
    them, say so). `account_id` arrived with DEF-383 on 2026-08-21; a deployment
    where the rating half has not landed yet must degrade to the previous
    behaviour — every tax applies, nobody is exempt — rather than raise a
    `TypeError` in the middle of a 500-account run.

    The fallback is the SAFE direction here and it is worth saying why, because
    it points the opposite way to DEF-273's fail-safe two functions down: this
    argument would only ever REMOVE a tax line, so losing it means the customer
    is charged the tax the utility believes they owe. Losing a class or a
    premises restriction would ADD one. Under-serving an exemption is a support
    call and a credit; over-charging is a refund and a regulator.
    """
    try:
        return resolver(plan_id, service_date, **facts)
    except TypeError:  # pragma: no cover — pre-DEF-383 rating only
        facts.pop("account_id", None)
        return resolver(plan_id, service_date, **facts)


def _tax_exempt_on(account: Any, service_date: date) -> bool:
    """Is this account exempt ON THE SERVICE DATE — certificate expiry included?

    ── THE RULE, AND IT IS DELIBERATELY UNLIKE THE REST OF THIS FILE ─────────
    CR-013 part 4 (PO, 2026-08-18, `TAXES-FEES-BUSINESS-SPEC.md` shared rules),
    verbatim: *"Expired exemption certificates reinstate the tax on the next run
    with no exception raised — it's expected behaviour."*

    Every other missing or stale input in this module becomes a `GatherProblem`
    a human must clear (BR-BIL-015). This one does NOT, and the PO said so in as
    many words, so it is written here rather than left to be "fixed" into an
    exception by a later reading. The account simply starts paying tax again.

    ── WHAT IT FIXES, MEASURED ──────────────────────────────────────────────
    `accounts.tax_exempt_expires` has existed since the customers slice (r9 #5 /
    BR-CUS-050 neighbourhood) and NOTHING read it. The account-level exemption
    was a boolean, so a certificate that expired in 2024 still zeroed the tax on
    every bill for ever — a silent UNDER-tax, which is the same class of failure
    as the over-tax DEF-273 was filed for and points the other way: the utility
    owes an authority money it never collected. `compute_tax`'s own trailer has
    named this gap since 2026-08-10 (*"the exemption EXPIRY branch (US-RAT-013
    TC-8, BR-CUS-063) needs an expiry date the seam's AccountContext does not
    carry — REPORTED"*). It is carried here instead, because the engine is pure
    and holds no clock: the SERVICE DATE is the bill's own date and it already
    travels.

    An exemption with NO expiry never expires — a blank date is "open-ended",
    not "expired yesterday".
    """
    if not bool(getattr(account, "tax_exempt", False)):
        return False
    expires = getattr(account, "tax_exempt_expires", None)
    if expires is None:
        return True
    return service_date <= expires


def _customer_class(account: Any) -> str | None:
    """The account's PLATFORM consumer category — `residential`, `commercial`,
    `industrial`, `government` (customers `account_types.code`, r5 #12 / D5).

    r10's State Utility Tax is *"Comm, Industrial only · Residential exempt"*,
    and this is the fact that answers it. Read through the row, never guessed
    from a NAME: a tenant may rename the label on their own screen while the
    platform CODE is the one the rule is written against — the same distinction
    `_behavior_class` draws just below for account status.

    None when the account carries no type, and `plan_tax_rules` then treats a
    class-restricted tax as NOT applying (DEF-273's fail-safe): under-charging
    is recoverable, over-charging a customer who is exempt is not.
    """
    account_type = getattr(account, "account_type", None)
    code = getattr(account_type, "code", None)
    return str(code).strip() or None if code else None


def _premises_geography(unit: Any) -> dict[str, Any]:
    """The premises facts a tax scope can be evaluated against.

    r10 states the mechanism on its own tax detail drawer — *"Inside Bexar
    County · Premise flag selects it at billing time"* — and **the flag now
    EXISTS**: `premises.inside_city_limits`, added 2026-08-21 under BR-RAT-101
    (PO: *"On premises we will add this flag and during billing we will consider
    Account -> Unit -> Premises to consider it"*). This docstring said *"there
    is no `inside_city_limits` flag on `premises` yet"* until that landed, and
    a sentence describing an absence outlives the absence exactly as easily as
    one describing a guarantee (hard-won law 1; DEF-445 is the same shape one
    module over).

    So the scope resolves against the flag where it is recorded and against the
    geography the record already carries where it is not. FOUR keys now — the
    three matching `taxes.premises_scope_field`'s bounded set, plus the flag.

    ⚠ **AND TWO IDENTITY KEYS BESIDE THEM, ADDED 2026-08-21 — WHICH PREMISES.**
    `premises_id` and `address_line` are not scope facts and rating's
    `premises_in_scope` never reads them (it asks for `inside_city_limits`,
    `city` and `state` by name and ignores the rest, so they are inert on the
    tax path). They are here because R5's refusal has to be ACTIONABLE: BR-RAT-102
    stops a bill when the plan surcharges and the flag is `None`, and a message
    that says *"a premises has no city-limits flag"* tells a clerk nothing they
    can act on. `rating.selectors.premises_geography_rows` carries the same two
    for the same reason — *"plus enough to name one on screen"*.

    They live on THIS seam rather than a second one, deliberately: billing reads
    a premises in exactly one place, and a second reader is how two answers to
    one question start.

    An absent premises or a blank column yields nothing, and the tax then does
    NOT apply. That is the ruled direction (DEF-273, PO 2026-08-18): a premises
    whose city nobody recorded must not be charged an inside-city-only fee on a
    guess.
    """
    premises = getattr(unit, "premises", None)
    if premises is None:
        return {}
    facts = {
        "city": getattr(premises, "city", None),
        "state": getattr(premises, "state", None),
        "postal_code": getattr(premises, "postal_code", None),
        # Identity, not scope — see the docstring. `str(...) or None` so a
        # missing id travels as an absence rather than as the string "None" in a
        # refusal a clerk has to act on.
        "premises_id": str(getattr(premises, "id", "") or "") or None,
        "address_line": getattr(premises, "address_line", None),
    }
    # CR-013 part 4 downstream, verbatim: *"premise city-limit flags drive
    # attachment and are audit-logged on the premise"*.
    #
    # ⚠ THE COLUMN LANDED 2026-08-21 (BR-RAT-101) AND THIS LINE DID NOT HAVE TO
    # CHANGE — which is the point worth keeping. It was written with `getattr`
    # so the flag would travel the day metering added it, and it does.
    #
    # `getattr` STAYS rather than becoming an attribute read: `unit.premises` is
    # a cross-module object reached through a seam, and a deployment where the
    # metering migration has not run must degrade to the recorded city name
    # rather than raise inside a 500-account run.
    #
    # ⚠ AND THE `is not None` TEST IS LOAD-BEARING. `None` means NOBODY RECORDED
    # IT, which is a third state — not False. A premises whose flag nobody set
    # travels WITHOUT the key, and the tax then does not apply, which is
    # DEF-273's ruled direction: never charge an inside-city-only fee on a
    # guess. `bool(flag)` would turn None into False and start charging.
    flag = getattr(premises, "inside_city_limits", None)
    if flag is not None:
        facts["inside_city_limits"] = bool(flag)
    return facts


def _behavior_class(account: Any) -> str:
    """BR-CUS-055's class, read through the status row — never guessed from a
    status NAME, because a tenant may add statuses and the name is theirs while
    the class is the rule."""
    status = getattr(account, "status", None)
    return getattr(status, "behavior_class", "") or ""


#: BR-CUS-055's two classes a temporary stop moves between (`stages.resolve_subscription`).
_CLASS_BILLABLE = "billable"
_CLASS_BASE_ONLY = "billable_base_only"


def _behavior_class_for_period(account: Any, period_start: date, period_end: date) -> str:
    """BR-CUS-055's class for THIS PERIOD when a TEMPORARY STOP touched it.

    `CR-183-BRC10` B1 (PO 2026-10-14): *"during the hold the account bills its
    base (standing) charge only, no usage"*. The account's status is
    `vacation_hold` exactly while the hold runs, and `_behavior_class` reads the
    status on the day the run GATHERS — so a period only PARTLY on hold was
    priced by whichever side of the hold the run happened to fall on:

      * **run while the hold is on** → the whole period base-only, and the
        usage the meter recorded on the ACTIVE days before the stop was billed
        by nobody: the next bill opens on this period's closing read. Measured
        (T5 test): a June period, hold from 21 Jun, 412 kWh read on 28 Jun —
        the draft was **$18.50** and the 412 kWh × $0.12 = **$49.44** was lost.
      * **run after the restart** → billable, which is right.

    **So the class follows the DAYS** (B1 says *by the day*): a hold that covers
    every day of the period is `billable_base_only`; a hold that covers only
    some of them leaves the period `billable`, and the meter's own reading
    prices the usage — the hold days add none, because the supply was off or
    nobody was home. The base charge is untouched either way: it runs on hold
    days and active days alike (B1), so `service_days` is not reduced.

    ⚠ **NOTHING CHANGES WITHOUT A `temporary_stops` ROW.** An account a clerk
    put on `vacation_hold` by hand answers `()` and keeps the status's class
    exactly as before; the seam absent answers the status's class too.
    """
    status_class = _behavior_class(account)
    if status_class not in (_CLASS_BILLABLE, _CLASS_BASE_ONLY):
        return status_class
    reader = _resolve("customers", "temporary_stop_windows")
    if reader is None:
        return status_class
    windows = tuple(reader(account.id, period_start, period_end) or ())
    if not windows:
        return status_class
    held = sum((last - first).days + 1 for first, last in windows)
    days = (period_end - period_start).days + 1
    return _CLASS_BASE_ONLY if held >= days else _CLASS_BILLABLE


def _tenant_currency() -> str:
    regional = _resolve("tenancy", "regional_settings")
    settings = regional() if regional else None
    return (settings or {}).get("currency") or ""


def _service_days(
    account: Any,
    period_start: date,
    period_end: date,
    cycle_days: int,
    off_windows: tuple[tuple[date, date], ...] = (),
) -> int:
    """Days of the period this account actually held the service (B4.3).

    A mid-period move-in owns fewer days than the cycle has. Both numbers
    travel so the proration factor is derived ONCE downstream — computing it
    here as well would give two places for it to be wrong differently.

    ── BR-CUS-103, AND WHY IT NEEDED NO NEW MONEY MATH (DEF-707) ────────────
    **PO ruling 2026-08-25 closing OQ-380** — asked *"when a service is cut,
    does the base charge keep running?"* with `A-11488`, cut 2026-08-18 owing
    **$612.75**, the PO answered **"no"**. A cut service is a service the
    customer does not have, and `service_days` is already the count of days
    they DID have it. So a cut subtracts days here and B4.3's frozen
    `service_days / cycle_days` factor prices it — nothing about the money rule
    changes, and nothing new computes a base charge.

    `off_windows` are INCLUSIVE `(first_dark_day, last_dark_day)` pairs from
    `apps.customers.selectors.service_off_windows`, which is where the boundary
    lives: BR-CUS-103 bills base *"right up to the moment it is cut, because
    until then it was available"*, so the first dark day is `cut_on + 1` and
    customers applies that offset — this function only counts.

    ⚠ **SUBTRACTED, NOT TRUNCATED, and that is the whole reason this takes a
    LIST.** A period holding a cut AND a later restoration is dark in the
    middle and served at both ends; truncating the span at the cut would
    also throw away the days after the service came back. Counting is the only
    shape that is right for one window, two, or none — and B4.3 asks for a
    COUNT of days, not a range, so this needs no segment machinery.

    ⚠ **THE WINDOWS ARE INTERSECTED WITH THE SERVED SPAN FIRST.** A dark day
    that falls before a move-in or after a move-out was never billed, so
    subtracting it would take the day off twice and under-bill the customer.
    """
    opened = getattr(account, "opened_at", None)
    closed = getattr(account, "closed_at", None)
    start = max(period_start, opened) if opened else period_start
    end = min(period_end, closed) if closed else period_end
    if end < start:
        return 0
    days = (end - start).days + 1
    for dark_from, dark_through in _merged(off_windows):
        low = max(start, dark_from)
        high = min(end, dark_through)
        if high >= low:
            days -= (high - low).days + 1
    # Never negative: overlapping windows cannot subtract a day twice (they are
    # merged above), and a fully dark period is 0 days served, which is exactly
    # what B4.3's factor of zero means.
    return max(0, min(cycle_days, days))


def _cut_at_season_change_reads(
    readings: tuple[ServiceReading, ...], tariffs: Any
) -> tuple[ServiceReading, ...]:
    """🔒 `DEF-RAT-8849` · A METER READ ON THE SEASON-CHANGE DAY REPLACES THE
    DAY SPLIT. HUMAN-REVIEW-PENDING (rating math).

    PO, 2026-10-01, verbatim: *"yes build the season-change day reading"*
    (decision log *"A METER READ TAKEN ON THE SEASON-CHANGE DAY REPLACES THE DAY
    SPLIT"*; WE-18's own sentence, *"an ACTUAL read dated Oct 1 would replace
    the split"*). 120 kWh over 15 Sep – 14 Oct with the season changing 1 Oct:
    with an actual reading dated 1 Oct showing 80 used before it and 40 after,
    the bill prices **80 at summer and 40 at winter**; without one it stays
    the calendar-day split, **64 / 56** (BR-RAT-034, built 2.437.1).

    ⚠ **THE ENGINE STAYS CALENDAR-FREE, SO THE CUT IS MADE HERE.** Rating
    counted the days per season over the served span (`TariffConfig.season_days`
    / `season_span`), which places each season-change day; metering published
    every register reading of the period on the reading (`period_registers`,
    no extra query). This function matches the two and hands the engine
    QUANTITIES per season (`Quantity.season_parts`), never a date.

    THE FOUR JUDGMENTS, recorded in the decision log and the review-ledger row:

    1. **"On the season-change day" is the reading dated the FIRST DAY OF THE
       NEW SEASON** (1 Oct for a winter starting 1 Oct). Metering stamps
       `read_at` at 00:00 of the read date and a billing period opens on the
       date of its opening reading, so a reading dated 1 Oct is the register
       at the instant winter begins. It is also the day WE-18 and the PO's
       example name.
    2. **Only an ACTUAL reading cuts** (WE-18's word). An estimate carries no
       dial value (BR-MET-028) and is a model of the usage, not a measurement
       of where it stood on the day; an estimate on the boundary leaves the
       day split. Several actual readings that day → the LAST one.
    3. **The cut is taken from the REGISTERS, relative to what this bill
       measured.** Every later season is `(next register − this register) ×`
       the factor the closing reading USED (BR-MET-500, never defaulted to 1);
       the first season is the REMAINDER of the bill's own quantity, so the
       parts add back to it exactly and no unit is invented or dropped.
    4. **Anything that makes the subtraction a fiction leaves the day split**:
       no factor, an estimated closing reading, a reading on another meter (an
       exchange), a part below zero, or a TOU window the day's reading did not
       cover (the engine then splits every window by days — all or none).
    """
    if not any(getattr(reading, "period_registers", ()) for reading in readings or ()):
        return readings
    return tuple(_season_cut(reading, tariffs) for reading in readings)


def _season_cut(reading: ServiceReading, tariffs: Any) -> ServiceReading:
    """One reading cut at its season-change readings, or returned unchanged."""
    quantity = reading.consumption
    registers = tuple(getattr(reading, "period_registers", ()) or ())
    if quantity is None or not registers:
        return reading
    config = next(
        (
            one
            for one in tariffs or ()
            if getattr(one, "service", None) == reading.service_code
            and getattr(one, "asset_id", None) in (None, getattr(reading, "asset_id", None))
            and len(getattr(one, "season_days", ()) or ()) >= 2
            and getattr(one, "season_span", None) is not None
        ),
        None,
    )
    if config is None:
        return reading
    changes: list[date] = []
    day = config.season_span[0]
    for share in tuple(config.season_days)[:-1]:
        day = day + timedelta(days=int(share.days))
        changes.append(day)
    main_channel = next(
        (r.get("channel") for r in registers if str(r.get("read_id")) == str(reading.read_id)),
        None,
    )
    parts: list[rating_seam.SeasonParts] = []
    if main_channel is not None:
        cut = _cut_register(quantity.amount, registers, main_channel, changes)
        if cut is not None:
            parts.append(rating_seam.SeasonParts(channel=None, quantities=cut))
    for window in quantity.windows or ():
        cut = _cut_register(window.quantity.amount, registers, window.channel, changes)
        if cut is not None:
            parts.append(rating_seam.SeasonParts(channel=window.channel, quantities=cut))
    if not parts:
        return reading
    return replace(reading, consumption=replace(quantity, season_parts=tuple(parts)))


def _cut_register(
    measured: Decimal, registers: tuple[dict, ...], channel: str, changes: list[date]
) -> tuple[Decimal, ...] | None:
    """`measured` per season of ONE register, cut at the actual readings dated
    on each season-change day — or `None`, which leaves the day split.

    `registers` are newest first (metering's order), so the closing reading is
    the first billable one on the channel and "the last one that day" is the
    first match. See `_cut_at_season_change_reads` for the four judgments.
    """
    on_channel = [r for r in registers if r.get("channel") == channel and r.get("billable", True)]
    if not on_channel:
        return None
    closing = on_channel[0]
    if closing.get("current_value") is None or closing.get("multiplier") is None:
        return None
    asset = closing.get("asset_id")
    cuts: list[Decimal] = []
    for change in changes:
        on_the_day = next(
            (
                r
                for r in on_channel
                if r.get("day") == change.isoformat()
                and r.get("asset_id") == asset
                and not r.get("estimated")
                and r.get("current_value") is not None
            ),
            None,
        )
        if on_the_day is None:
            return None
        cuts.append(Decimal(str(on_the_day["current_value"])))
    factor = Decimal(str(closing["multiplier"]))
    dials = cuts + [Decimal(str(closing["current_value"]))]
    later = tuple((dials[i + 1] - dials[i]) * factor for i in range(len(cuts)))
    parts = (Decimal(measured) - sum(later, Decimal(0)),) + later
    if any(part < 0 for part in parts):
        return None
    return parts


def _served_span(account: Any, period_start: Any, period_end: Any) -> tuple[date, date] | None:
    """🔒 BR-RAT-034 — the days of the period this account HELD the service:
    `(max(period start, opened), min(period end, closed))`, the same clipping
    `_service_days` applies, or `None` when there is no such span.

    It is what rating counts season days over (`OQ-234` CLOSED 2026-09-07,
    built 2026-10-01). The served span and not the bare period, because a
    customer who moved in on 5 October of a 15 Sep – 14 Oct period consumed
    nothing in September, and splitting their reading 16/30 into summer would
    price winter kWh at summer rates. ⚠ Service CUTS inside the span are NOT
    subtracted (BR-CUS-103's dark days): a lane judgment, recorded in the
    review-ledger row, because no signed figure covers a cut that straddles a
    season boundary and the read for the period is still one register delta.
    """
    if not isinstance(period_start, date) or not isinstance(period_end, date):
        return None
    opened = getattr(account, "opened_at", None)
    closed = getattr(account, "closed_at", None)
    start = max(period_start, opened) if isinstance(opened, date) else period_start
    end = min(period_end, closed) if isinstance(closed, date) else period_end
    if end < start:
        return None
    return (start, end)


def _merged(windows: tuple[tuple[date, date], ...]) -> tuple[tuple[date, date], ...]:
    """Overlapping dark windows collapsed into disjoint ones, in date order.

    Two cases cannot overlap today — `uq_one_open_disconnect_case_per_account`
    allows one open case at a time — but a subtraction that double-counts a day
    would REDUCE somebody's bill silently, and a merge costs one sort. Written
    because "cannot happen" is not a guarantee about data (hard-won law 1).
    """
    if not windows:
        return ()
    ordered = sorted(windows)
    merged: list[list[date]] = [list(ordered[0])]
    for dark_from, dark_through in ordered[1:]:
        if dark_from <= merged[-1][1] + timedelta(days=1):
            merged[-1][1] = max(merged[-1][1], dark_through)
        else:
            merged.append([dark_from, dark_through])
    return tuple((row[0], row[1]) for row in merged)


def _service_off_windows(
    account: Any,
    *,
    period_start: date,
    period_end: date,
    billed_services: tuple[str, ...],
    account_no: str,
) -> tuple[tuple[date, date], ...]:
    """BR-CUS-103's dark days for THIS bill — or a refusal when the cut is partial.

    Asked of `apps.customers.selectors.service_off_windows` BY NAME, the seam
    idiom every other cross-module read in this file uses. Customers owns the
    cut, owns the boundary (`cut_on + 1`), and writes nothing new for this:
    `commit_cut` still never touches `accounts`, which is `DSC-02.4`'s first
    prohibition and the reason DEF-707 had no wrong line of code in it.

    ⚠ **AN UNPUBLISHED SEAM YIELDS NO WINDOWS — the OVERCHARGE direction, and
    it is stated rather than silent.** That is today's behaviour (DEF-707
    itself) and it is the wrong one; refusing every bill of a deployment whose
    customers half has not landed would be worse. The resolver is asked for BY
    NAME here, so the absence is visible, which is the trade `_discounts_for`
    and `_charge_fees_for` both take one screen up.

    ⛔ **A PARTIAL CUT REFUSES, IT IS NOT AVERAGED.** `DSC-02.1` is *"One
    decision per service, not all or nothing"*, and B4.3 has exactly one
    `service_days / cycle_days` factor for the whole account — there is no
    per-service proration anywhere in the engine. So a bill charging electric
    and water where only water was cut has two right answers and no way to
    express either: stopping base stops the electric standing charge the
    customer still owes, and leaving it running bills a dead water connection.
    The account becomes a named exception the run reports (BR-BIL-015), with
    both service lists in the message, rather than a plausible wrong bill.
    """
    read = _resolve("customers", "service_off_windows")
    if read is None:
        return ()
    rows = read(getattr(account, "id", None)) or ()
    windows: list[tuple[date, date]] = []
    for row in rows:
        dark_from = row.get("off_from")
        dark_through = row.get("off_through") or period_end
        if dark_from is None or dark_from > period_end or dark_through < period_start:
            continue
        cut_services = {str(code) for code in (row.get("services") or ())}
        still_live = tuple(
            sorted(code for code in billed_services if code and code not in cut_services)
        )
        if still_live:
            # ⚠ THE IDS STAY IN THIS COMMENT AND OUT OF THE SENTENCE (CR-016 /
            # DEF-322): the rule is BR-CUS-103, the ruling is OQ-380, the
            # proration is B4.3 ❄️, the one-decision-per-service table is
            # `DSC-02.1`, the exception-row contract is BR-BIL-015, and
            # `disconnects.RESTRICTOR_UNBUILDABLE` already spells out what a
            # per-service treatment row would take to build. None of that helps
            # the clerk reading the exception screen; the two service lists do.
            raise GatherProblem(
                GATHER_PARTIAL_CUT,
                f"account {account_no} had its service cut on {row.get('cut_on')} for "
                f"{sorted(cut_services) or ['(no service named)']}, and this bill also charges "
                f"{list(still_live)}, which was not cut. A cut service is charged no standing "
                "charge and a live one is, and this bill can only prorate the account as a "
                "whole — so it cannot do both. Nothing is guessed either way: bill the cut "
                "services separately from the live ones, or restore service first.",
            )
        windows.append((dark_from, dark_through))
    return tuple(windows)


def _service_address(premises: dict[str, Any] | None) -> str | None:
    """`DEF-2865` — the premises' street, as one line a customer reads.

    Composed from the facts `_premises_geography` already returns, so this adds
    no read: the premises is looked at ONCE per account and a second reader is
    how two answers to one question start (that seam's own words).

    **A MISSING PART IS DROPPED, NEVER FILLED.** A premises with a street and no
    city prints the street; a premises with nothing prints nothing and the
    document names the absence. A partial address that reads as complete is
    worse than a dash, because nobody goes looking for it.
    """
    facts = premises or {}

    def text(key: str) -> str | None:
        value = facts.get(key)
        return str(value).strip() or None if isinstance(value, str) and value.strip() else None

    region = " ".join(part for part in (text("state"), text("postal_code")) if part)
    parts = [part for part in (text("address_line"), text("city"), region or None) if part]
    return ", ".join(parts) or None


def _snapshot_for(
    account: Any,
    unit: Any,
    plan: dict,
    covered: tuple[tuple[str, str | None], ...] = (),
    *,
    premises: dict[str, Any] | None = None,
) -> dict:
    """What the document will print, captured NOW — at gather, from what the
    clerk is about to see. BR-BIL-030 / the PO's "keep lock data for that bill".

    Captured here rather than at issue on purpose: at issue it would re-join
    whatever the customer record says by then, and a name changed between the
    run and the release would print on a bill for a period billed under the
    old one.

    `covered_units` appears ONLY on a bill that covers more than one unit
    (BR-CUS-068), and its absence on every other bill is deliberate: an
    ordinary account's snapshot stays byte-identical to every one already
    locked into an issued invoice. On a master bill it is the answer to the
    question the document otherwise cannot answer — *which shared spaces is
    the owner being charged for* — and `unit_label` alone names the anchor,
    which on a two-area building is half the bill.
    """
    contact_name = _resolve("customers", "primary_contact_name")
    snapshot = {
        "account_no": account.account_no,
        "customer_name": contact_name(account) if contact_name else None,
        "unit_id": str(getattr(unit, "id", "")) or None,
        "unit_label": getattr(unit, "label", None),
        # ── DEF-2865 · WHERE THE SERVICE IS ──────────────────────────────────
        # A19 §1.2 prints a service address and the snapshot stamped `unit_label`
        # alone, so every bill this product issued said *Unit A* and never which
        # building. Captured HERE with the customer's name and for the identical
        # reason (BR-BIL-030): a premises re-addressed between the run and the
        # release must not print over a period billed at the old address.
        "service_address": _service_address(premises),
        "plan": {"id": plan["id"], "name": plan["name"], "version": plan["version"]},
    }
    if len(covered) > 1:
        snapshot["covered_units"] = [
            {"unit_id": unit_id, "unit_label": label} for unit_id, label in covered
        ]
    notice = _plan_extended_notice(account)
    if notice is not None:
        # Absent on every other bill, so an ordinary snapshot stays
        # byte-identical to the ones already locked into issued invoices.
        snapshot["payment_plan"] = notice
    return snapshot


def _plan_extended_notice(account: Any) -> dict[str, Any] | None:
    """🔒 DEF-BIL-8248 · PO ruling 2026-09-30, fixed-charge case 5 — *"the next
    bill says the plan now ends a month later"*.

    True of THIS bill when the account's LAST ISSUED bill came from a run in
    which a clerk chose *Skip this month* for a payment-plan instalment
    (`plan_instalment_due` / `skip` — billing's own decision trail; issue then
    extended the plan through payments, `payments_seam.
    extend_plans_for_skips`). The end date is PAYMENTS' — its live plan's last
    instalment (`apps.payments.plans.plan_ends_on`, resolved by name) — never
    recomputed here. Only the next bill: the one after it looks back at a run
    with no skip and says nothing. Any unanswerable read says nothing too — a
    notice is information, never a reason to refuse a bill."""
    from django.db import transaction

    from apps.billing import models as billing_models

    try:
        # ⚠ A SAVEPOINT, NOT A TIDY-UP (hard-won law 14): this catches and
        # carries on, and on PostgreSQL a failed statement would otherwise
        # abort the gather's whole transaction. Proved in
        # `tests/test_bbr_plan_extended_notice.py` (PostgreSQL case).
        with transaction.atomic():
            answer = _plan_extended_answer(account, billing_models)
    except Exception:  # noqa: BLE001 — a notice never refuses a bill
        return None
    if not answer or not answer.get("ends_on"):
        return None
    return {"extended_one_month": True, **answer}


@batch_reads.memoised
def _skipped_instalment_last_run(tenant_id: Any, account_id: Any) -> bool:
    """Did the run that issued this account's LAST bill SKIP its plan
    instalment? `_plan_extended_notice`'s two reads; memoised for a bulk Check
    batch and primed for the whole batch by `batch_seams` (B27)."""
    from django.db.models import F

    from apps.billing import models as billing_models

    last = (
        billing_models.Invoice.objects.filter(
            tenant_id=tenant_id,
            account_id=account_id,
            status__in=billing_models.INVOICE_LOCKED_STATUSES,
            bill_run__isnull=False,
        )
        .order_by(F("issued_at").desc(nulls_last=True), "-period_end", "-created_at")
        .values_list("bill_run_id", flat=True)
        .first()
    )
    if last is None:
        return False
    return billing_models.BillRunDecision.objects.filter(
        tenant_id=tenant_id,
        bill_run_id=last,
        account_id=account_id,
        case="plan_instalment_due",
        choice="skip",
        superseded_by__isnull=True,
    ).exists()


def _plan_extended_answer(account: Any, billing_models: Any) -> dict[str, Any] | None:
    """`_plan_extended_notice`'s reads, inside its savepoint."""
    if not _skipped_instalment_last_run(getattr(account, "tenant_id", None), account.id):
        return None
    ends = _resolve("payments", "plan_ends_on", "plans")
    return ends(account.id) if ends is not None else None


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _decimal_or_none(value: Any) -> Decimal | None:
    return None if value is None else _decimal(value)


def with_readings(
    data: AccountBillingData, readings: tuple[ServiceReading, ...]
) -> AccountBillingData:
    """The same account, with different readings — how a re-rate is expressed.

    The S31.3 exception step may replace a missing read with an estimate a
    human chose. Rather than re-gathering (which would re-read the customer
    record and could pick up a name changed since), the run swaps the readings
    on the data it already has and replays stages 2–6. Everything else the bill
    prints stays exactly as the clerk saw it.
    """
    return replace(data, readings=readings)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane) · AMENDED 2026-08-16 by the pricing-engines lane (`_tariff_config_for` projects rating's windows/season/capacity/demand/percent onto the seam, each read with `.get` so a rating deployment that has not been updated degrades to a NAMED refusal rather than a KeyError mid-run) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: `_taxes_for` carries rating's `tax_id` onto the seam's TaxRule) · AMENDED 2026-08-21 by the DEF-438 cutover step-5 lane (`gather` now hands rating the two facts the engine has always been able to use and never received: the CONNECTION SIZE — `size_class`, which tier ladder, DEF-484 — and the per-service JURISDICTION FACTOR — `TariffConfig.jurisdiction_factor`, R5's outside-city surcharge, DEF-466. Neither moves a figure on any real tenant, and in both cases what is missing is the SOURCE rather than the hop: `_connection_size_for` resolves an unpublished metering seam because NO ROW IN THIS PRODUCT RECORDS A CONNECTION'S SIZE (DEF-514) [⚠ CORRECTED 2026-09-25, DEF-BIL-6760 — THAT CLAUSE WAS TRUE WHEN THIS LINE WAS WRITTEN AND STOPPED BEING TRUE SIX DAYS LATER. DEF-514 closed 2026-08-27 at 2.79.5: `assets.Asset.size_class` is a real column, `metering.connection_size_for` answers from it, and DEF-1900 added the screen control and the meters-import column at 2.79.7. Measured 2026-09-25 on a seeded water+sewer+fire tenant on PostgreSQL 16, the seam answers a real ratified size — FL-4, FL-6, FL-8 — on every one of 51 fire service points that has a fire line on it. The clause is kept with this stamp rather than deleted because it is a dated record of what that lane did; it is not a description of today], and `_plan_jurisdiction` reads two columns NOTHING WRITES AT ANY LAYER (DEF-515, plus DEF-517 for the premises flag it is gated on)) · AMENDED 2026-08-22 by the W9a DEF-502 lane (`_discounts_for` reads rating's `billable_discount_rules` — the account's open ENROLMENTS narrowed by the plan's BINDING, both gates per BR-RAT-069/110, at the SERVICE DATE — and `_taxes_for` carries each authority's `taxes.discount_treatment` onto the seam's TaxRule through the batched `discount_treatments_for_taxes` read, so BR-RAT-106's per-tax before/after answer reaches compute-tax; an unpublished seam degrades to NO discounts, which is the pre-DEF-502 behaviour, stated with its trade in `_discounts_for`'s docstring) · AMENDED 2026-08-22 by the master-account BILL-ASSEMBLY lane (🔒 HUMAN-REVIEW-PENDING — BR-CUS-068: `covered_units` + `_coverage_facts` price EVERY common area one master account covers onto ONE document, so BR-MET-101's 1408 Elm bills $41.20 + $28.40 = **$69.60** where it billed the anchor's services alone (DEF-571). An ordinary account answers `(unit_id,)` and issues no extra query, which is why every ❄️ B5 figure is untouched. The two places the rules run out REFUSE by name: OQ-334 (two covered areas on one service) and OQ-335 (covered areas on two plans))
# checklist: A✔ B✔ C✔ D=deferred(no-API-half yet) E=deferred(no-frontend-half yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_002_gather.py ·
#         tests/test_us_rat_002_plan_seams.py::tc10 (real selectors) ·
#         tests/test_us_bil_001_prepare.py (four modules, real rows)
# exceptions: (1) CLOSED 2026-08-11 — the three rating selectors this calls
#         (`plan_rate_schedules`, `plan_tax_rules`, `pricing_inputs`) are all
#         published and proved end to end. The refusals stated when they were
#         missing still stand and are still the behaviour: an absent
#         `plan_rate_schedules` raises a reason-coded GatherProblem (a plan
#         with no resolvable services must be VISIBLE, not a base-charge-only
#         bill that looks deliberate) and an absent `plan_tax_rules` yields NO
#         taxes, because a bill missing its tax is visibly wrong on the preview
#         while a bill carrying an invented rate is not.
#         (2) `readings` are an ARGUMENT, not fetched — the exception step
#         replaces a missing read with a human's estimate, and that decision
#         must reach the gather without this module knowing about decisions.
#         (3) the SERVICE DATE resolves every tariff version (BR-RAT-007) —
#         there is deliberately no fallback to today's prices, because a
#         fallback would silently re-price history and the bills would each
#         look plausible
#         (4) ⚠ **HALF OF THIS NOTE EXPIRED ON 2026-08-27 (CR-039 wave C
#         task 11).** It read *"THE TWO REFUSALS ADDED 2026-08-21 FIRE ON
#         NOTHING TODAY … no plan in any tenant states a factor, so the
#         premises flag is never consulted."* **The sample RESIDENTIAL plan
#         now states `1.5`**, so on a seeded tenant the flag IS consulted on
#         every bill and `GATHER_JURISDICTION_UNSTATED` is reachable — which
#         is why the seed states a side on all 44 sample premises rather than
#         leaving 42 of them to become exception rows. The SIZE half stands:
#         no version in any tenant names a size, so `GATHER_SIZE_UNRESOLVED`
#         still cannot be reached. Both remain asserted rather than assumed
#         (tests/test_def_484_size_and_jurisdiction.py for the arithmetic,
#         tests/test_cr039_c11_seeded_surcharge.py for what the seed holds).
#         (5) R5 IS NOW IMPLEMENTED TWICE — here and in
#         `rating.resolution.money_factor` — deliberately, because billing
#         may not import rating's modules (B1) and the chain has no
#         production caller (DEF-438). `tests/test_def_438_parity.py`
#         compares the two at R5 rather than trusting them to agree.
#         (6) `_call_pricing_inputs` ASKS THE SIGNATURE rather than catching
#         a `TypeError` the way `_call_plan_taxes` does, and the departure is
#         deliberate: a `TypeError` raised INSIDE rating would be
#         indistinguishable from an arity mismatch, and the retry would then
#         bill the every-size ladder — the silent wrong ladder this commit
#         exists to stop, reintroduced by its own compatibility shim.
#         (7) THE COVERAGE READ IS THE ONE CROSS-MODULE SEAM HERE THAT DOES
#         NOT DEGRADE TO TODAY'S BEHAVIOUR, and the asymmetry is stated in
#         `covered_units`' docstring: today's behaviour for a MASTER account
#         is DEF-571 — a bill short by an entire common area that foots and
#         prints — so an unpublished `customers.covered_unit_ids` refuses a
#         master account by name while an ordinary account is unaffected.
#         (8) `_coverage_facts` RETURNS EMPTY FOR A SINGLE-UNIT ACCOUNT
#         WITHOUT ASKING METERING ANYTHING, so an ordinary bill issues not
#         one extra query and prices byte-identically — which is what keeps
#         every ❄️ B5 figure frozen (golden 33/33 before and after).
# revised: 2026-08-25 (lane CUTMONEY, closing DEF-707) — **BR-CUS-103: BASE CHARGES
#         STOP AT THE CUT** (PO 2026-08-25, closing OQ-380; asked *"when a service
#         is cut, does the base charge keep running?"* with `A-11488`, cut
#         2026-08-18 owing **$612.75** — the PO answered **"no"**).
#         ⚠ **THERE WAS NO WRONG LINE OF CODE TO FIX.** `commit_cut` correctly never
#         writes `accounts` (`DSC-02.4`'s three prohibitions), so base ran on because
#         NOTHING WAS WRITTEN TO STOP IT — an omission, never a decision, which is why
#         no test asserted it either way and why it had to be put to the PO.
#         **WHAT CHANGED, AND WHY IT NEEDED NO NEW MONEY MATH:** `service_days` is
#         already the count of days the customer HAD the service, and B4.3 ❄️ already
#         prorates base by `service_days / cycle_days`. So the cut subtracts days and
#         the frozen factor prices it. `_service_days` gained an `off_windows`
#         argument; `_merged` collapses overlaps so a day cannot be subtracted twice;
#         `_service_off_windows` asks `apps.customers.selectors.service_off_windows`
#         BY NAME — customers still writes nothing new, billing ASKS.
#         **The boundary lives in customers, not here** (BR-CUS-103: *"a service is
#         billed base right up to the moment it is cut, because until then it was
#         available"*), so the first dark day is `cut_on + 1` and this file only counts.
#         **SUBTRACTED, NOT TRUNCATED** — a period holding a cut AND a later
#         restoration is dark in the middle and served at both ends.
#         WORKED, MEASURED on `tests/test_br_cus_105_static_balance.py`: base $18.50/mo,
#         cut 15 June → June bills **15/30 → $9.25**, July bills **0/31 → $0.00** and the
#         whole bill totals **$0.00** (it carried $18.50 every month before this).
#         RED PROOFS EXECUTED IN A SCRATCHPAD `cp -a` COPY, never the shared tree (step
#         2d as amended 2026-08-25), each quoted in the lane report: subtraction removed
#         → `assert 31 == 0`; boundary moved to `cut_on` → `assert (14, 30) == (15, 30)`;
#         partial-cut refusal removed → *"a partially cut account must not be priced at
#         all"*; windows forced on every account → the never-cut control `assert 0 == 30`.
#         (9) **A PARTIAL CUT REFUSES — `GATHER_PARTIAL_CUT`.** `DSC-02.1` is *"One
#         decision per service, not all or nothing"* and B4.3 has exactly ONE factor for
#         the whole account; there is no per-service `service_days` anywhere in the
#         engine. Stopping base would stop it for the services the customer still has and
#         leaving it running would bill a dead connection, so the account becomes a named
#         exception row (BR-BIL-015) with BOTH service lists in the message. Building the
#         per-service half is a schema change this lane does not own.
#         (10) **AN UNPUBLISHED SEAM YIELDS NO WINDOWS — the OVERCHARGE direction**, and
#         it is exactly DEF-707's behaviour. Stated rather than silent, and asked for BY
#         NAME so the absence is visible: the trade `_discounts_for` and
#         `_charge_fees_for` both take, for the same reason.
#         (11) ✅ **BR-CUS-104's HALF IS BUILT — DEF-708, 2026-08-27 — AND STILL NOT
#         HERE.** This note read *"the reconnection fee is owed AT THE CUT and posts
#         nowhere, so `A-11340` clears a reconnection at $8,240.00 where $8,315.00 is
#         owed"*. The fee is now a real receivable raised by `commit_cut` through
#         `apps/billing/fee_bill.py` on its OWN `fee` bill, so `$8,315.00` is what
#         clears. Nothing in THIS file changed and nothing here should: a cycle bill
#         prices a service period, and the fee is not one.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
