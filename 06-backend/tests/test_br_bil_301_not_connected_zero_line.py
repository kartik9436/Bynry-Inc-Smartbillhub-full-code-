# ── Trace ──────────────────────────────────────────────
# Ruling:  PO 2026-09-25, option (b) of three, verbatim: *"Question · When a
#          plan includes a service the property has no connection for, what
#          should happen? b · Bill it at $0.00, and say so"*.
# Rule:    BR-BIL-301 (billing) — the ruled `$0.00` line, marked NOT CONNECTED.
#          Settles the PRICE that `BR-BIL-300` edge 2 left open.
# Defect:  DEF-BIL-6759 — the whole bill stopped, blaming a missing SIZE.
# Rules:   BR-BIL-300 edge 2 · BR-RAT-080 (a base is charged because a
#          CONNECTION exists) · BR-MET-108 (the ruled zero, a DIFFERENT fact) ·
#          OQ-670 (the mirror gap, a different sentence) · B14 rules 32 + 33 ·
#          CLAUDE.md hard rule 2 (money 4 decimals, display 2)
# Tests:   this file
# Impacts: apps/billing/gather._unconnected_plan_services ·
#          _unconnected_plan_service_lines · _tariffs_for_plan(skip_services=)
# ───────────────────────────────────────────────────────
"""**A PLAN THAT SELLS A SERVICE THE PROPERTY IS NOT CONNECTED FOR.**

⚠⚠ **AMENDED 2026-09-30 — THE `$0.00` LINE IS GONE; THE REVIEW LIST STAYS.**
PO ruling of that date, verbatim: *"sane no line - and use 0"* — a service
that is not in service prints NO line on the bill and counts as `$0`. It
supersedes the *on the document* half of the 2026-09-25 option (b) this file
was written for. **The rest of option (b) was not withdrawn and is still
asserted here:** the bill EXISTS (the defect was that it did not), there is
still NO fire tariff and therefore no fire base (`tc1`), nothing else moves
by a cent (`tc2`), a CONNECTED unit is untouched (`tc3`), and the account
still lands on the clerk's review list (`tc8`). `tc1`, `tc2`, `tc6` and `tc7`
changed their expectations for this ruling and each says so; each was RED
against the ruling's code before its edit (`assert 0 == 1`, `assert 4 == (4 +
1)`, `KeyError: 'fire'`, `IndexError`) — the old line simply is not there.

Before this, the account was REFUSED — and the refusal blamed a missing size.
**Measured on a seeded water + sewer + fire tenant on real PostgreSQL 16,
gathering all 75 accounts through `gather_account` + `price_account`
(`10-scripts/def_bil_6759_zero_line_measure.py`):**

    21 refused  connection_size_unresolved_for_sized_schedule
    20 of them  over a unit with NO fire service point
     0 of the 35 that PRICED had a plan service with no service point

A customer's plan sold fire, the unit had no fire line, and **the whole bill
stopped — their water with it.**

── RED BEFORE THE FIX (r11 step 2d, law 7) ─────────────────────────────────
Every case below was run against the pristine tip `90deb63b5` first. tc1 read:

    apps.billing.gather.GatherProblem: service fire: this rate schedule prices
    FL-10, FL-12, FL-2, FL-4, FL-6, FL-8 differently from every other size, and
    this connection's size is not recorded.

which is the defect exactly: a SIZE refusal over a connection that does not
exist to have a size.

⚠ **THE FALSE PASS THIS FILE IS WRITTEN AGAINST, NAMED.** The obvious wrong
test asserts *"a fire line reads `$0.00`"* on a unit that **does** have a fire
connection — which passes on the broken code too, because an empty fire
connection has ALWAYS billed `BR-MET-108`'s ruled zero. `tc3` is the
discriminator: a CONNECTED unit must still price fire as a tariff and must
carry **no** *not connected* line at all. Without tc3 every assertion here is
satisfiable by doing nothing.

⚠ **AND THE SECOND FALSE PASS IS QUIETER: A ZERO THAT COSTS MONEY.** Routing
this case into `_per_size_configs`' empty-map arm — the one-line seam change
`DEF-BIL-6759`'s own prevention note proposed — produces a `$0.00` usage line
**and the plan's BASE CHARGE with it**, because that arm passes `plan_base`.
The bill would then exist, a fire line would read `$0.00`, and the customer
would be charged a standing charge for a connection they have not got
(`BR-RAT-080`). `tc1` asserts there is **no fire tariff at all**, which is the
only assertion that can tell those two apart.

⚠ **THE FIXTURE PATCHES `resolution_shadow._seam` AS WELL AS `gather._resolve`,
AND THAT IS NOT DECORATION.** `resolution_switch` is on by default (`R3,R4`
since `CR-057`) and reaches metering through `resolution_shadow._seam`, which
calls `import_module` directly and **cannot see a patch of `gather._resolve`**.
Its sibling `test_def_1060_the_unit_decides_which_services_bill.py` patches only
the latter, and **7 of its 10 cases are red at the tip for exactly this reason**
— filed as `DEF-BIL-6773`, not caused here and not fixed here.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import gather, rating_seam, resolution_shadow
from apps.billing.contracts import ServiceReading
from apps.billing.rating_seam import Quantity

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)
SERVICE_DATE = date(2026, 6, 30)

#: The sentence a customer reads. Held as a constant so a lane that changes the
#: wording has to change it HERE, where B14 rule 33's count is argued.
NOT_CONNECTED = "(not connected)"
#: `OQ-670`'s sentence, for the SAME shape of gap in the opposite direction.
#: Asserted as DIFFERENT, never reused — see tc6.
NOT_PRICED = "(not priced on this plan)"


@pytest.fixture(autouse=True)
def _rolled_back_resolution_chain(settings):
    """Run these cases with `SBH_BILLING_RESOLUTION_STEPS` EMPTY, and say why.

    ⚠ **THIS IS A STATED LIMIT OF THIS FILE, NOT A CONVENIENCE, AND IT IS
    WRITTEN HERE SO THAT NOBODY READS THESE SEVEN GREENS AS COVERING MORE THAN
    THEY DO.** The shipped default is `R3,R4` (`CR-057`), and that chain builds
    a rating CATALOGUE — `resolution_catalogue.plan_version_facts` — which
    reads `app.tenant_id` and raises `AuthError: AUTH-003` outside a tenant
    context. A fixture of plain namespaces cannot supply one, so with the chain
    on, **every case here dies before reaching the assertion it was written
    for**. That is exactly how its sibling
    `test_def_1060_the_unit_decides_which_services_bill.py` came to have 7 of
    its 10 cases red at the tip (`DEF-BIL-6773`).

    **WHY ROLLING IT BACK COSTS THIS PROOF NOTHING, ARGUED RATHER THAN
    ASSERTED:** `BR-BIL-301` acts entirely inside `_tariffs_for_plan` and
    `gather_account`, **before** `resolution_switch.apply` is called, and it
    writes to `data.fees`, which the switch does not read or rewrite — it
    substitutes prices on `data.tariffs`. So the two cannot interact here.

    **AND THE SHIPPED CHAIN IS COVERED, ELSEWHERE AND ON REAL POSTGRESQL:**
    `10-scripts/def_bil_6759_zero_line_measure.py` gathers and prices all 75
    accounts of a seeded water + sewer + fire tenant with the default `R3,R4`
    in force, before and after. That measurement is this file's other half and
    neither is sufficient alone.
    """
    settings.BILLING_RESOLUTION_STEPS = ""


def an_account(**overrides):
    values = dict(
        id="acct-ruth",
        account_no="AC-2026-00056",
        unit_id="unit-ruth",
        status=SimpleNamespace(behavior_class="billable"),
        tax_exempt=False,
        opened_at=None,
        closed_at=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _pricing_inputs(tariff, _service_date, *_size, **_kw):
    """Rating's ENGINE shape. Water is TIERED, fire is the SIZED schedule.

    ⚠ **FIRE'S `size_groups` IS NON-EMPTY AND THAT IS THE WHOLE POINT.** It is
    what arms `DEF-484`'s size gate — the gate that refused the account — so a
    fixture without it would prove nothing about the defect.
    """
    service = getattr(tariff, "service", None)
    if service == "water":
        return {
            "version_id": "v-water",
            "model": "tiered",
            "billed_unit": "kgal",
            "base_charge": "8.00",
            "minimum_bill": None,
            "currency": "USD",
            "unit_price": None,
            "tiers": [
                {"upper": "3", "unit_price": "3.10"},
                {"upper": None, "unit_price": "4.20"},
            ],
        }
    if service == "fire":
        return {
            "version_id": "v-fire",
            "model": "flat",
            "billed_unit": "connection",
            "base_charge": "9.00",
            "minimum_bill": None,
            "currency": "USD",
            "unit_price": "60.00",
            "size_groups": ["FL-2", "FL-4", "FL-6", "FL-8", "FL-10", "FL-12"],
            "tiers": [],
        }
    return {
        "version_id": "v-1",
        "model": "flat",
        "billed_unit": "kgal",
        "base_charge": "8.00",
        "minimum_bill": None,
        "currency": "USD",
        "unit_price": "3.10",
        "tiers": [],
    }


def _world(*, plan_services, unit_services):
    """The two lists held apart so a case can disagree them.

    ⚠ **`connection_size_for` ANSWERS ONLY FOR A SERVICE THE UNIT IS CONNECTED
    FOR, AND THE FIRST DRAFT OF THIS FIXTURE DID NOT.** In the product a size
    lives on the ASSET standing on the connection (`BR-AST-500`), so a unit
    with no service point has no size and a unit WITH one does. A fixture that
    answered `None` for both made `tc3` — the case that proves a connected unit
    is untouched — fail on the size gate for a reason that has nothing to do
    with this ruling, which would have made its red worthless as evidence.
    """
    sized = {code: "FL-6" for code in unit_services}
    return {
        "metering.connection_size_for": lambda _unit, code: sized.get(code),
        # ⚠ **THE SHIPPED `R3,R4` CHAIN REFUSES AN ABSENT MULTIPLIER BY NAME**
        # (`resolution.MeterMultiplierUnstated`: *"a ×10 register whose
        # multiplier nobody recorded bills a tenth of the customer's
        # consumption"*). Published here as `1` so the cases below fail on
        # THEIR OWN subject; leaving it out makes every one of them red on a
        # metering fact that has nothing to do with this ruling.
        "metering.billing_multiplier_for": lambda _unit, _code: Decimal("1"),
        # ⚠ **FIRE IS A COUNTING CAPACITY SERVICE AND THE FIXTURE MUST SAY SO,**
        # or it is not fire. A real connected fire unit answers a per-size map
        # here, which makes `_per_size_configs` stamp `per_size_line=True` and
        # makes the shipped `R3,R4` chain SKIP the service by name (the live
        # answer stands, `CR-063`). Without this the ruled path tries to
        # resolve fire's ladder itself and every case dies on a rating read.
        # `None` where the unit has no fire connection — which is the seam's
        # own answer today and is deliberately NOT changed by this ruling (see
        # `metering.selectors.billable_size_groups`).
        "metering.billable_size_groups": (
            lambda _unit, code, _as_of: (
                {"FL-6": 1} if code == "fire" and code in unit_services else None
            )
        ),
        "metering.unit_row": lambda _id: SimpleNamespace(
            id="unit-ruth", label="Unit 1", rate_plan_id="plan-res", premises=None
        ),
        "metering.service_points_for": lambda _id: [
            {"id": f"sp-{code}", "service": code, "route_id": None}
            for code in unit_services
        ],
        "rating.plan_ref": lambda _id: {
            "id": "plan-res",
            "name": "Residential",
            "version": 3,
        },
        "rating.plan_rate_schedules": lambda _id: [
            {
                "service_code": code,
                "tariff": SimpleNamespace(id=f"t-{code}", service=code),
            }
            for code in plan_services
        ],
        "rating.pricing_inputs": _pricing_inputs,
        # ⚠ **ADDED 2026-09-30 — THIS FILE WAS RED AT THE TIP SINCE 2026-09-28.**
        # `DEF-BIL-7170` (PO: *"we will never take default value from plan $8.0
        # - that is retired"*) made the base come ONLY from the charge code, so
        # a world publishing no charge-code read refused every case here with
        # *"No base charge for water. Declare one on Charge codes."* — before
        # any assertion ran (dated with `git log -S`, commit `1c4644a4b`). The
        # figures are the SAME ones `pricing_inputs` below states, now served
        # by the object that owns them, so no asserted amount moves.
        "rating.base_charge_from_charge_code": lambda service_code, **_kw: {
            "amount": _pricing_inputs(
                __import__("types").SimpleNamespace(service=service_code), None
            )["base_charge"],
            "code": f"BASE-{service_code.upper()}",
            "refusal": None,
        },
        "rating.plan_tax_rules": lambda *_a, **_k: [
            {"code": "STATE+LOCAL", "rate": "0.0825", "tax_id": "TAX-TX"}
        ],
        "tenancy.regional_settings": lambda: {"currency": "USD"},
    }


def _install(monkeypatch, published):
    """Patch BOTH resolution paths — see the module docstring.

    A fixture that patched only `gather._resolve` would send the shipped
    `R3,R4` chain at the real `metering.selectors.unit_row` with a fake id, and
    every case here would die on `NotFoundError` before reaching the assertion
    it was written for. That is not a weaker proof; it is no proof at all.
    """

    def resolve(module, attribute, kind="selectors"):
        return published.get(f"{module}.{attribute}")

    monkeypatch.setattr(gather, "_resolve", resolve)
    monkeypatch.setattr(resolution_shadow, "_seam", resolve)


def _gather(readings=()):
    return gather.gather_account(
        account=an_account(),
        service_date=SERVICE_DATE,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=30,
        readings=readings,
    )


def _price(data, fees):
    return rating_seam.price_bill(
        services=tuple(
            (
                config,
                next(
                    (
                        r.consumption
                        for r in data.readings
                        if r.service_code == config.service
                    ),
                    Quantity(amount=Decimal("0"), unit="kgal"),
                ),
            )
            for config in data.tariffs
        ),
        period=rating_seam.BillingPeriod(
            start=PERIOD_START, end=PERIOD_END, cycle_days=30, service_days=30
        ),
        account=rating_seam.AccountContext(currency="USD", tax_exempt=False),
        taxes=data.taxes,
        fees=fees,
    )


WATER_READ = (
    ServiceReading(
        service_code="water", consumption=Quantity(amount=Decimal("5"), unit="kgal")
    ),
)


# ══════════════════════════════════════════════════════════════════════════
# (1) THE DELIVERABLE — the bill EXISTS, the line reads $0.00, and it SAYS SO
# ══════════════════════════════════════════════════════════════════════════
def test_br_bil_301_tc1__an_unconnected_plan_service_bills_zero_and_says_so(
    monkeypatch,
):
    """**PO 2026-09-25, option (b):** *"Bill it at $0.00, and say so"*.

    RED BEFORE THE FIX: `GatherProblem` — *"service fire: this rate schedule
    prices FL-10, FL-12, FL-2, FL-4, FL-6, FL-8 differently from every other
    size, and this connection's size is not recorded."* The account produced no
    bill at all, so there was nothing to assert an amount on.

    ⚠ **THE THIRD ASSERTION IS THE ONE THAT DISTINGUISHES THE RULING FROM THE
    CHEAPER FIX.** There must be **no fire tariff**: a tariff carries the plan's
    BASE CHARGE, and a standing charge over a connection that does not exist is
    money the customer does not owe (`BR-RAT-080`). `$0.00` means `$0.00`.
    """
    _install(monkeypatch, _world(plan_services=["water", "fire"], unit_services=["water"]))

    data = _gather(readings=WATER_READ)

    # (1) The bill exists at all — the defect was that it did not.
    assert data is not None
    # (2) ⚠ AMENDED 2026-09-30 (*"sane no line - and use 0"*): fire prints NO
    # line on any channel; it is carried as data for the review list instead.
    # This asserted one `fire (not connected)` fee line at `0.0000` until then.
    assert [line for line in data.fees if line.service == "fire"] == []
    assert data.unconnected_services == ("fire",)
    # (3) ⚠ NO FIRE TARIFF — and therefore no fire BASE CHARGE. This is what
    # separates the ruling from the empty-map arm, which would have billed
    # `$9.00` a month for a connection that does not exist.
    assert [config.service for config in data.tariffs] == ["water"]


# ══════════════════════════════════════════════════════════════════════════
# (2) THE MONEY — nothing else on the bill moves, to the cent
# ══════════════════════════════════════════════════════════════════════════
def test_br_bil_301_tc2__every_other_line_is_unchanged_to_the_cent(monkeypatch):
    """**The same account, priced with its fee channel and without it.**

    ⚠ **AMENDED 2026-09-30.** This compared *one more line, the same money*
    while BR-BIL-301 printed a `$0.00` line. Under *"sane no line - and use
    0"* the fee channel carries nothing for fire, so the two pricings must be
    IDENTICAL — the same number of lines and the same money, tax included. A
    regression that put the zero line back would make `with_fees` one line
    longer and fail here.
    """
    _install(monkeypatch, _world(plan_services=["water", "fire"], unit_services=["water"]))
    data = _gather(readings=WATER_READ)

    without = _price(data, ())
    with_zero = _price(data, data.fees)

    assert len(with_zero.lines) == len(without.lines)
    assert with_zero.total == without.total
    # And the water lines themselves are byte-identical, line for line.
    water_before = [
        (line.kind, line.description, line.amount)
        for line in without.lines
        if line.service == "water"
    ]
    water_after = [
        (line.kind, line.description, line.amount)
        for line in with_zero.lines
        if line.service == "water"
    ]
    assert water_before == water_after, "a moved cent on a working service is a regression"


# ══════════════════════════════════════════════════════════════════════════
# (3) ⚠ THE FALSE-PASS GUARD — a CONNECTED unit is untouched
# ══════════════════════════════════════════════════════════════════════════
def test_br_bil_301_tc3__a_connected_unit_still_prices_its_tariff(monkeypatch):
    """**The discriminator. Without this case every other assertion here is
    satisfiable by a product that does nothing.**

    A unit that DOES have a fire service point prices fire as a TARIFF, and
    carries **no** *not connected* line. An empty fire connection billing
    `BR-MET-108`'s ruled `$0.00` has always looked like the ruling's outcome
    from the outside; the difference is whether there is a connection, and that
    is what this asserts.
    """
    _install(
        monkeypatch, _world(plan_services=["water", "fire"], unit_services=["water", "fire"])
    )
    data = _gather(readings=WATER_READ)

    assert [config.service for config in data.tariffs] == ["water", "fire"]
    assert [line for line in data.fees if NOT_CONNECTED in line.description] == []


# ══════════════════════════════════════════════════════════════════════════
# (4) THE DEGRADE — nobody can tell, so nothing changes
# ══════════════════════════════════════════════════════════════════════════
def test_br_bil_301_tc4__an_unpublished_seam_behaves_exactly_as_the_tip_did(
    monkeypatch,
):
    """A deployment whose metering lane has not published `service_points_for`
    cannot tell what this unit takes, and **must not start zeroing services**.

    Inventing the reconciliation from a seam that is not there would zero a
    customer's whole bill on a fact nobody supplied — the same reasoning
    `_unpriced_unit_service_lines` states for the mirror gap.

    ⚠ **AND *EXACTLY AS THE TIP DID* MEANS THE REFUSAL, NOT A BILL, WHICH IS
    WORTH STATING PLAINLY RATHER THAN DRESSING UP.** Without the seam this is
    `DEF-BIL-6759` unchanged: fire is still priced from the plan, its size
    still cannot be resolved, and the account is still refused by name. The
    degrade is SAFE because it moves no money, **not** because it is good —
    the fix arrives with the seam, and a deployment without it keeps the
    defect. Asserting a happy bill here would have been a check that cannot
    fail, reporting a fix over a deployment that has not got one.
    """
    published = _world(plan_services=["water", "fire"], unit_services=["water"])
    published.pop("metering.service_points_for")
    _install(monkeypatch, published)

    with pytest.raises(gather.GatherProblem) as raised:
        _gather(readings=WATER_READ)

    assert raised.value.reason == gather.GATHER_SIZE_UNRESOLVED


# ══════════════════════════════════════════════════════════════════════════
# (5) ⚠ A UNIT CONNECTED FOR NOTHING IS STILL A CONFIGURATION PROBLEM
# ══════════════════════════════════════════════════════════════════════════
def test_br_bil_301_tc5__a_unit_with_no_points_at_all_still_refuses(monkeypatch):
    """**The ruling prices a MISSING service at zero; it does not turn a unit
    nobody has connected into a `$0.00` bill.**

    Every service drops out, `_tariffs_for_plan` ends with no configs, and its
    existing refusal fires with the sentence it already carried: *"A bill with
    no services is not a $0.00 bill — it is a configuration problem a human
    must see."* That guard is left exactly where it was, and this case is why
    it must not be relaxed.
    """
    _install(monkeypatch, _world(plan_services=["water", "fire"], unit_services=[]))

    with pytest.raises(gather.GatherProblem) as raised:
        _gather(readings=WATER_READ)

    assert raised.value.reason == gather.GATHER_NO_TARIFF


# ══════════════════════════════════════════════════════════════════════════
# (6) ⚠ TWO DIFFERENT GAPS, TWO DIFFERENT SENTENCES, ON ONE BILL
# ══════════════════════════════════════════════════════════════════════════
def test_br_bil_301_tc6__not_connected_and_not_priced_are_told_apart(monkeypatch):
    """**They are opposite gaps and a clerk who confuses them fixes the wrong
    thing.**

    *not priced on this plan* (`OQ-670`) is a gap in the TARIFF over a real
    connection — fixed on Plans & Rates. *not connected* (`BR-BIL-301`) is a gap
    in the ESTATE over a real tariff — fixed by connecting the property. One
    bill can carry both, and this case builds exactly that bill.
    """
    _install(
        monkeypatch,
        _world(plan_services=["water", "fire"], unit_services=["water", "sewer"]),
    )
    data = _gather(readings=WATER_READ)

    sentences = {line.service: line.description for line in data.fees}
    # ⚠ AMENDED 2026-09-30 — the two gaps are still told apart, now by WHERE
    # each is said: *not priced* (OQ-670, untouched) is still a `$0.00` line
    # on the document; *not connected* prints no line (*"sane no line - and
    # use 0"*) and is said only on the clerk's review list.
    assert "fire" not in sentences
    assert data.unconnected_services == ("fire",)
    assert sentences["sewer"] == f"sewer {NOT_PRICED}"


# ══════════════════════════════════════════════════════════════════════════
# (7) B14 RULES 32 AND 33 — WHAT A CLERK READS, COUNTED
# ══════════════════════════════════════════════════════════════════════════
def test_br_bil_301_tc7__no_line_anywhere_carries_the_retired_sentence(monkeypatch):
    """⚠ **REPURPOSED 2026-09-30.** This case counted the words of the
    `fire (not connected)` sentence against B14 rules 32 and 33. PO: *"sane no
    line - and use 0"* — the sentence no longer exists, so there is nothing to
    count. What is asserted instead is that it cannot come back on EITHER
    channel: no fee line and no priced line carries *not connected*, which is
    the regression a revert of the ruling would produce.
    """
    _install(monkeypatch, _world(plan_services=["water", "fire"], unit_services=["water"]))
    data = _gather(readings=WATER_READ)

    assert [f for f in data.fees if NOT_CONNECTED in (f.description or "")] == []
    priced = _price(data, data.fees)
    assert [ln for ln in priced.lines if NOT_CONNECTED in (ln.description or "")] == []


# ══════════════════════════════════════════════════════════════════════════
# (8) THE OTHER HALF OF OPTION (b) — THE LIST A CLERK WORKS THROUGH
# ══════════════════════════════════════════════════════════════════════════
def test_br_bil_301_tc8__the_account_lands_on_the_clerks_decision_list(monkeypatch):
    """**Option (b) is two things, and a mark nobody collects is decoration.**

    The PO's words as the option was put to them: *"The same bill, plus the
    zero line is marked not connected, and the account appears on a list of
    accounts billing zero for a service they are sold."* `tc1` proves the mark;
    this proves the list.

    ⚠ **A DECISION AND NOT A BLOCK, WHICH IS THE WHOLE POINT.** `blocked`
    means *a human must act before this bills*; `decisions` means *this WILL
    bill and somebody should look*. Filing it as a block would stop the bill
    the PO has expressly ruled must be produced — option (c), which they
    declined. `_decisions_for`'s own docstring already draws that line.
    """
    from apps.billing import models as billing_models
    from apps.billing import runs

    # `_continuity_decisions` is a NEIGHBOURING case that reads the invoice
    # table for this tenant (`last_issued_invoice_period_end`). It has nothing
    # to do with this ruling and this fast fixture has no tenant context, so it
    # is stubbed rather than worked around — leaving it in makes the case die
    # on `AuthError` before reaching the assertion it exists for.
    monkeypatch.setattr(runs, "_continuity_decisions", lambda *_a, **_k: [])

    _install(monkeypatch, _world(plan_services=["water", "fire"], unit_services=["water"]))
    data = _gather(readings=WATER_READ)

    rows = runs._decisions_for(data, ())

    fire = [row for row in rows if row.service_code == "fire"]
    assert len(fire) == 1, [(r.reason, r.service_code) for r in rows]
    assert fire[0].reason == "service_not_connected"
    assert fire[0].account_no == "AC-2026-00056"
    # The case must be STORABLE, or the decision a clerk takes cannot be
    # recorded against it and the row is a dead end (`G124`'s subject).
    assert "service_not_connected" in billing_models.DECISION_CASES
    # ⚠ AND A CONNECTED ACCOUNT RAISES NOTHING — the same false-pass guard tc3
    # makes for the document, made again for the list.
    _install(
        monkeypatch, _world(plan_services=["water", "fire"], unit_services=["water", "fire"])
    )
    assert [
        row
        for row in runs._decisions_for(_gather(readings=WATER_READ), ())
        if row.reason == "service_not_connected"
    ] == []
