# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-012 (EP-CWP-04) — what it costs to get connected here.
#           Screens: CWP-008 · CWP-009
# Rules:    BR-CWP-012 (read through the owning module; no second copy — this
#           file COMPUTES NOTHING, it reads the rows rating already holds) ·
#           CR-068 §2d (the portal computes no money) · CLAUDE.md hard rule 2
#           (money is stored to four decimals and DISPLAYS two — this seam
#           returns the stored value and `money.py` does the display) ·
#           US-CWP-012 TC-6 (the CURRENTLY EFFECTIVE version, never next
#           quarter's price)
# Tests:    06-backend/tests/test_us_cwp_012_availability.py TC-1, TC-4, TC-6
# Impacts:  apps/rating/models.RatePlan · PlanChargeRule · Charge ·
#           PlanDepositRule
# ───────────────────────────────────────────────────────
"""What the portal reads from `rating`: a connection fee and a deposit.

⚠ **WHERE THESE FIGURES ACTUALLY LIVE, AGAINST WHAT THE STORY SAYS.**
`US-CWP-012` §5 maps *To connect* to *"connection fee on the effective tariff"*.
**There is no such column.** `TariffVersion` carries `base_charge`,
`minimum_bill`, `percent` and the tier rows — no connection fee anywhere — and
the product's connection fee is a CHARGE CODE (`seed_demo.py` seeds `CONN ·
Connection fee · one_time · $45.00`) attached to a rate plan through
`PlanChargeRule`, whose `amount_override` is the plan's own price for it. The
plan's §0 rule applies: the code wins and the task says so (`DEF-CWP-3703`; the
story's §5 row is stamped).

⚠ **AND EFFECTIVE DATING IS THE PLAN'S, NOT THE CHARGE'S** (`US-CWP-012`
TC-6). `Charge` and `PlanChargeRule` carry no dates at all; `RatePlan` carries
`effective_from` / `effective_to`. So *"the currently effective version"* is
implemented where the product actually keeps it: a plan whose window has not
opened, or has closed, is not quoted, and the caller reads that as *a person
will look at it* rather than as a price. A fee dated for next quarter therefore
cannot reach a visitor, which is what the test case is protecting.

**THE THREE PRESENTATIONS, AND WHY THEY ARE THREE.** The wireframe draws
`$185.00`, `Included` and `$0.00` in one column and they mean different things:

  * an amount — the plan attaches a one-time charge and it costs that;
  * `Included` — the plan attaches NO separate connection charge for that
    service, so nothing extra is payable to connect it;
  * `$0.00` — the plan attaches a charge the utility has priced at zero, which
    is a utility saying *"this one is free"* out loud.

`NOT HERE` is the fourth and is not this file's: it is the absence of a service
point, decided in `metering_seam`. `US-CWP-012` TC-4 is explicit that a service
the utility does not carry must NOT read `$0.00`, *"which means free"*.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.rating import charge_prices
from apps.rating import models as rating_models
from core.tenancy import current_tenant_id

#: What `charge_type` a connection fee carries. The seeded catalogue's `CONN`
#: is `one_time`; anything recurring is a bill line, not a cost to connect.
ONE_TIME = "one_time"

#: ⚠ **A DRAFT PLAN PRICES NOTHING (`BR-RAT-030`), SO IT QUOTES NOTHING.**
#: A public page reading a draft plan's charge rules would publish a price
#: nobody had approved — the wizard's half-finished work, on the utility's
#: own website. `publish_plan` is the moment a figure becomes the utility's
#: word, and it is the moment this seam starts quoting it.
PUBLISHED = "published"


def _assert_in_context(tenant_id: Any) -> None:
    current = current_tenant_id()
    if current is None or str(current) != str(tenant_id):
        raise RuntimeError(
            "portal seam asked for tenant "
            f"{tenant_id} while {current!r} is in context — BR-CWP-005: the tenant is "
            "resolved from the path before anything is read"
        )


def plan_is_quotable(plan: Any, on: date) -> bool:
    """`US-CWP-012` TC-6 — may this plan's prices be shown to a stranger TODAY?

    Two conditions and both are refusals a customer would rather have than a
    wrong number: the plan is PUBLISHED (a draft prices nothing), and its
    window is open.

    A NULL `effective_from` is a plan with no start date recorded, and the
    product treats that as effective (the seeded plans carry none). A future
    start or a past end is not effective, and the caller quotes nothing.
    """
    if plan.status != PUBLISHED:
        return False
    if plan.effective_from is not None and plan.effective_from > on:
        return False
    if plan.effective_to is not None and plan.effective_to < on:
        return False
    return True


def connection_fees(tenant_id: Any, rate_plan_id: Any, *, on: date) -> dict[str, Decimal] | None:
    """`{service_code: amount}` for every ONE-TIME charge the plan attaches.

    The value is **the CATALOGUE amount and never the plan's
    `amount_override`**, and that is a signed ruling rather than a shortcut. PO
    2026-08-19 ruling 1, verbatim: *"no plan cannot override prices"* — *"no
    per-plan amount override, no per-plan waive, no per-plan rate override"* —
    and `CR-013` part 5 puts it as *"a plan composes; it does not price."*
    `rating.resolution` says the same at its own call site: the column survives
    only so no stored figure is destroyed, and the engine does not consult it.
    A public price read that DID consult it would quote a number the bill would
    not charge, which is the worst kind of disagreement this surface can
    produce.

    A charge scoped to no service (`service_id` NULL) applies to the connection
    as a whole and is returned under the key `""`.

    **None means the plan quotes nothing today** — it is a draft, or its window
    has not opened — and never an empty dict, which would read as *"free for
    everything"*.
    """
    _assert_in_context(tenant_id)
    if not rate_plan_id:
        return None
    plan = (
        rating_models.RatePlan.objects.filter(tenant_id=tenant_id, pk=rate_plan_id)
        .only("id", "status", "effective_from", "effective_to")
        .first()
    )
    if plan is None or not plan_is_quotable(plan, on):
        return None
    rows = list(
        rating_models.PlanChargeRule.objects.filter(tenant_id=tenant_id, rate_plan_id=plan.id)
        .select_related("charge", "charge__service")
    )
    # CR-156-BRC10 — the catalogue amount is the code's *All sizes* row in force
    # on `on`, read through rating's one lookup (`charge_prices`); one query for
    # every rule. NEVER `row.amount_override` — see the docstring.
    flat = charge_prices.flat_amounts([row.charge_id for row in rows], on)
    fees: dict[str, Decimal] = {}
    for row in rows:
        charge = row.charge
        if charge.charge_type != ONE_TIME or charge.deleted_at is not None:
            continue
        if charge.amount_rule == "per_case":
            # DEF-RAT-9807 — an *entered when used* code's *All sizes* row is a
            # clerk's starting DEFAULT (`BR-RAT-1054` AMENDED 2026-10-06), not
            # a price; quoting it to a visitor would promise a figure the clerk
            # may change. Skipped, exactly as it was before it had a default.
            continue
        amount = flat.get(charge.id)
        if amount is None:
            continue
        key = charge.service.code if charge.service_id else ""
        fees[key] = Decimal(amount)
    return fees


def move_in_fees(
    tenant_id: Any,
    rate_plan_id: Any,
    *,
    on: date,
    customer_class: str | None,
    services: list[str],
    size_by_service: dict[str, str | None] | None = None,
) -> dict[str, Decimal] | None:
    """`{service_code: amount}` — what a MOVE-IN on this plan charges, `""` for
    an account-level code. PO 2026-10-30, ruling A (`DEF-CWP-10690`): an address
    already in Premises is a move-in, occupied or empty, so *IF YOU APPLY*
    quotes the move-in's figures.

    **Read through rating's ONE move-in price read** (`rating.move_in_fees.
    plan_move_in_charges`) — the read the staff move-in's Fees table (image 41,
    *From plan*) uses — so the portal and the counter cannot quote two figures:
    a one-time code on the plan's Charges table, for THIS customer class, for a
    service this unit has, priced by the catalogue (never the plan's override)
    and by the connection's recorded size where the code is priced by size.
    Nothing here sums across plans, rounds or taxes (`OQ-BIL-12788` (a): never
    taxed at move-in).

    A row rating cannot price (a `per_case` code a clerk types, a size nobody
    recorded, a percent with no basis) is NOT quoted — a public page never
    guesses a figure a clerk may change. Two codes for one service ADD: a
    move-in charges both.

    **None means the plan quotes nothing today** (`US-CWP-012` TC-6 — a draft,
    or a window that has not opened), exactly as `connection_fees` answers.
    """
    _assert_in_context(tenant_id)
    if not rate_plan_id:
        return None
    plan = (
        rating_models.RatePlan.objects.filter(tenant_id=tenant_id, pk=rate_plan_id)
        .only("id", "status", "effective_from", "effective_to")
        .first()
    )
    if plan is None or not plan_is_quotable(plan, on):
        return None
    from apps.rating import move_in_fees as rating_move_in_fees

    fees: dict[str, Decimal] = {}
    for row in rating_move_in_fees.plan_move_in_charges(
        plan.id,
        customer_class=customer_class,
        size_by_service=size_by_service or {},
        services=services,
        on_date=on,
    ):
        if row.get("amount") is None or row.get("refusal"):
            continue
        key = row.get("service") or ""
        fees[key] = fees.get(key, Decimal("0")) + Decimal(str(row["amount"]))
    return fees


def application_fee(tenant_id: Any) -> Decimal | None:
    """🔒 `DEF-CUS-9819` (PO 2026-10-06) — the price of the code the utility
    marked *Application fee*, read now, or None when no code is marked (or it
    cannot be priced flat today). `Decimal("0")` is a real answer: a utility
    that charges nothing (*"we wil ahve application fees as zero"*). It is the
    SAME read `customers` prices the request's line from, so *What you will
    pay* and the line the clerk sees cannot disagree."""
    _assert_in_context(tenant_id)
    from apps.rating import selectors as rating_selectors

    charge = rating_selectors.application_fee_charge()
    if not charge or charge.get("amount") is None:
        return None
    return Decimal(str(charge["amount"]))


def deposit(tenant_id: Any, rate_plan_id: Any, account_type_id: Any) -> Decimal | None:
    """The fixed deposit this plan asks of this class of customer, or None.

    ⚠ **A VISITOR HAS NOT SAID WHAT KIND OF CUSTOMER THEY ARE**, so the caller
    passes the residential class — somebody moving into a home — and the screen
    says *"deposit on your first bill"* rather than promising a final figure.
    The judgment is recorded in `12-governance/02-decision-log.md` (2026-09-04)
    rather than guessed at each call site.
    """
    _assert_in_context(tenant_id)
    if not rate_plan_id or not account_type_id:
        return None
    row = (
        rating_models.PlanDepositRule.objects.filter(
            tenant_id=tenant_id, rate_plan_id=rate_plan_id, account_type_id=account_type_id
        )
        .only("amount")
        .first()
    )
    return Decimal(row.amount) if row is not None else None


def current_plan_id(tenant_id: Any, unit_id: Any) -> Any | None:
    """The plan this unit is on TODAY, or None.

    ⚠ **`assigned_to IS NULL` IS WHAT *CURRENT* MEANS HERE, and it is the same
    test `plan_history` below uses.** `UnitPlanAssignment` is append-only, so a
    unit has one open row and a tail of closed ones; picking the newest
    `assigned_from` instead would return a FUTURE assignment on the day a clerk
    schedules a plan change, and quote next month's prices as today's.
    """
    _assert_in_context(tenant_id)
    if not unit_id:
        return None
    row = (
        rating_models.UnitPlanAssignment.objects.filter(
            tenant_id=tenant_id, unit_id=unit_id, assigned_to__isnull=True
        )
        .only("rate_plan_id")
        .first()
    )
    return row.rate_plan_id if row is not None else None


# ══ CR-068 · `CWP-052` — WHAT A STANDING CHARGE COSTS (US-CWP-062) ═════════
#
# ⚠ **THE BASE CHARGE HAS THREE POSSIBLE HOMES AND EXACTLY ONE SOURCE, AND
# THIS SEAM RESOLVES NONE OF THAT ITSELF.** `BR-RAT-088` (PO 2026-08-20:
# *"the CHARGE CODE owns the base amount; a plan displays it, never defines
# it"*) put the precedence in ONE function, and `DEF-154` is what it cost to
# have two: **every bill this product produced charged `$0.00` for base**
# because billing read a different column from the signed source. So the two
# figures a plan and a schedule hold are read here and handed STRAIGHT to
# `apps.rating.seams.base_charge_for`, which is the published door onto that
# one implementation.
#
# ⚠ **AND SINCE `DEF-RAT-6960` THE SCHEDULE'S THIRD FACT GOES WITH THEM.**
# `BR-RAT-1025` (PO 2026-09-19: *"plan -> rate schedule -> charge code -> base
# charges"*) lets the version NAME the code that owns its service's base, and
# `DEF-RAT-5782` made the BILL honour it. A door onto one implementation that
# asks a narrower question than the bill does is a second implementation with
# extra steps — the standing charge on `CWP-052` and the figure on the
# customer's bill are the same money, and they may not disagree.
#
# ⚠ **`size_class` IS `None` AND THAT IS THE PRODUCT'S OWN ANSWER, NOT A
# SHORTCUT.** `DEF-514` records that nothing in this product records a
# connection size, and `base_charge_for`'s own docstring says an unscoped call
# *"gets the same answer a tenant with one unscoped, flat base code would get
# — which is every tenant this product provisions today"*. The day sizes are
# recorded, this call gains the argument; until then passing one would be
# passing a guess.


#: What `standing_charge_monthly` says when the plan states no base at all.
#: ⚠ **NOT `$0.00`** (`US-CWP-062` TC-8). `rating_seam`'s own three
#: presentations already draw this line: an AMOUNT, `Included` (no charge
#: attached) and `$0.00` (a utility saying *this one is free* out loud). A
#: comparison built on a missing figure read as zero would tell a customer that
#: stopping for nineteen months costs nothing.
NO_STANDING_CHARGE = "no_standing_charge_on_this_plan"


def standing_charge_monthly(
    tenant_id: Any,
    *,
    rate_plan_id: Any,
    service_codes: list[str],
    customer_class: str | None,
    on: date,
) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING — see `12-governance/09-human-review-ledger.md`.

    ⚠ **THIS IS A MONEY FIGURE ON A CUSTOMER'S OWN SCREEN AND NO GLOB IN
    `human_owned.txt` MATCHES THIS FILE**, so `G7` reports CONFORM over it.
    Flagged rather than glob-added: changing that list is the PO's call, not a
    lane's, and the request is in the ledger row for `DEF-RAT-6960`.

    What this account pays a month before it uses anything.

    `{"amount": Decimal | None, "per_service": {code: Decimal}, "unavailable":
    str | None}` — and `amount` is `None` WITH a reason rather than a zero,
    every time it cannot be said.

    ⚠ **IT SUMS THE ACCOUNT'S OWN SERVICES AND NOT THE PLAN'S.** A plan may
    list five services; a customer who takes water and trash pays two bases.
    Summing the plan would quote a household the price of services it is not
    connected to, which on this screen decides whether they are told to close
    their account.

    ⚠ **ONE REFUSAL REFUSES THE WHOLE FIGURE.** If any service's base cannot be
    resolved, the monthly total is unknowable — and a partial total is worse
    than none, because it is a number the screen would compare against a
    connection fee and reach a verdict on.
    """
    _assert_in_context(tenant_id)
    if not rate_plan_id or not service_codes:
        return {"amount": None, "per_service": {}, "unavailable": NO_STANDING_CHARGE}

    from apps.rating import seams as rating_seams, selectors as rating_selectors

    # ⚠ **`plan_bases` WAS BUILT HERE AND IS DELETED (`DEF-BIL-7170`).** It
    # read `plan_services.base_charge` — the RETIRED column — for the one call
    # below, and that call stopped taking it on 2026-09-28. A query kept "in
    # case" is a reader of a retired source waiting to be wired up again.
    schedules = {
        row.service.code: row.tariff
        for row in rating_models.PlanRateSchedule.objects.filter(
            tenant_id=tenant_id, rate_plan_id=rate_plan_id
        ).select_related("service", "tariff")
    }

    per_service: dict[str, Decimal] = {}
    for code in service_codes:
        tariff = schedules.get(code)
        version = rating_selectors.in_force_version(tariff, on) if tariff is not None else None
        # ⚠ **THE SCHEDULE'S BINDING TRAVELS WITH THE FIGURE — `BR-RAT-1025`,
        # `DEF-RAT-6960`.** From `DEF-RAT-5782` the BILL charges the base code
        # the rate schedule NAMES, and this call did not pass it: a customer
        # whose utility has more than one `is_base` code for a service read
        # *we cannot work this out* on `CWP-052` while their bill carried the
        # named code's figure perfectly well, and a named code scoped to
        # another customer class showed them an INFERRED base the bill
        # refuses. One implementation of the precedence is worth nothing if
        # the two doors onto it are asked different questions.
        #
        # `named_base_charge_code` is rating's own narrowing rather than a
        # copy of it, for the reason its docstring gives.
        # ⚠ **THE PLAN'S AND THE VERSION'S RETIRED FIGURES ARE NO LONGER
        # PASSED — `DEF-BIL-7170` / `DEF-CWP-7001`, PO 2026-09-28.** This call
        # handed down `plan_bases.get(code)` and `version.base_charge`, and
        # the portal's own demo fixture is what proved why that was a hazard:
        # it wrote `8.0000` onto the plan for every service while the charge
        # codes said water 12.00, sewer 8.00 and trash 9.00, and the bill then
        # refused the disagreement by name — so `CWP-052` could show no
        # standing charge at all. The charge code is the only source now, and
        # there is no second figure for it to disagree with.
        answer = rating_seams.base_charge_for(
            code,
            customer_class=customer_class,
            size_class=None,
            named_code=rating_selectors.named_base_charge_code(version),
            # CR-156-BRC10 — the price row in force on the day quoted.
            on_date=on,
        )
        if answer["refusal"]:
            # Rating's or billing's own named refusal, carried as the reason
            # rather than swallowed — the posture `base_charge_for` itself takes.
            return {"amount": None, "per_service": {}, "unavailable": str(answer["refusal"])}
        if answer["amount"] is not None:
            per_service[code] = Decimal(answer["amount"])

    if not per_service:
        return {"amount": None, "per_service": {}, "unavailable": NO_STANDING_CHARGE}
    return {
        "amount": sum(per_service.values(), Decimal("0")),
        "per_service": per_service,
        "unavailable": None,
    }


def plan_history(tenant_id: Any, unit_id: Any) -> dict[str, Any]:
    """`CWP-065`'s *how you are billed* — the plan now, and what came before.

    ⚠ **THE ASSIGNMENT TABLE IS APPEND-ONLY, WHICH IS WHY THIS CAN BE ASKED AT
    ALL.** `UnitPlanAssignment` keeps every assignment with its own
    `assigned_from` / `assigned_to`, so *Residential Standard since 1 January
    2026, and before that Residential Basic* is a read rather than a
    reconstruction.

    ⚠ **`plan_version`, `source`, `actor` AND `reason` STAY INSIDE.** They are
    the utility's record of WHO changed a customer's plan and WHY — a bulk
    update, an import, a clerk's note — and none of it is the customer's
    business (`US-CWP-031` §5: *its version and the reason stay internal*). This
    returns a NAME and a DATE and nothing else.
    """
    _assert_in_context(tenant_id)
    rows = list(
        rating_models.UnitPlanAssignment.objects.filter(tenant_id=tenant_id, unit_id=unit_id)
        .select_related("rate_plan")
        .order_by("-assigned_from")
    )
    current = next((row for row in rows if row.assigned_to is None), None)
    previous = [row for row in rows if row.assigned_to is not None]
    return {
        "current": (
            {
                "name": current.rate_plan.name,
                "since": current.assigned_from.isoformat() if current.assigned_from else None,
            }
            if current is not None
            else None
        ),
        "before": [
            {
                "name": row.rate_plan.name,
                "from": row.assigned_from.isoformat() if row.assigned_from else None,
                "to": row.assigned_to.isoformat() if row.assigned_to else None,
            }
            for row in previous
        ],
    }
