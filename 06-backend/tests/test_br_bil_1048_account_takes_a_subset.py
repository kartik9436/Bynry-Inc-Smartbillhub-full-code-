# ── Trace ──────────────────────────────────────────────
# Rule:    BR-BIL-1048 (billing) — a bill charges for the services the ACCOUNT
#          HOLDS, never for every service its unit is connected for.
# Ruling:  PO 2026-09-25 (`BR-CUS-1101`), their own scenario: a premises offers
#          SIX services, the unit has SIX service points, FIVE carry a meter or
#          an asset, **and the account takes only THREE**.
# Defect:  DEF-BIL-6823 — the account held three and the bill charged six.
# Rules:   BR-CUS-1101 (the account's half) · BR-BIL-300 (the unit says which
#          services EXIST) · BR-BIL-301 (a plan service with NO CONNECTION is a
#          `$0.00` line and must stay one) · OQ-670 (the mirror gap, a
#          different sentence) · CLAUDE.md hard rule 2
# Tests:   this file
# Impacts: apps/billing/gather._services_taken_by_account ·
#          gather._plan_services_not_taken · gather._tariffs_for_plan ·
#          gather._unpriced_unit_service_lines(taken_services=) ·
#          apps/customers/selectors.billed_service_codes_for
# ───────────────────────────────────────────────────────
"""**AN ACCOUNT THAT TOOK THREE OF ITS UNIT'S SIX SERVICES.**

── RED BEFORE THE FIX (r11 step 2d, law 7), MEASURED ───────────────────────
Reproduced on real PostgreSQL 16 before a line was written, on a seeded
six-service tenant (`10-scripts/br_bil_1048_account_subset_measure.py`).
Account `AC-2026-00003` was narrowed to **electric, gas, fire** — three of its
unit's six — and its September bill came back **byte-identical**:

    before  $475.68   electric $230.50 · gas $46.25 · fire $0.00
                      water $98.10 · sewer $76.50 · trash $15.00 · tax $9.33
    after   $475.68   the same fifteen lines

**$189.60 of water, sewer and trash the account never bought.**

⚠ **THE FALSE PASS THIS FILE IS WRITTEN AGAINST, NAMED.** The obvious wrong
test uses a TWO-service fixture and asserts that the one taken service is
billed. It passes on the broken code the moment the account happens to take the
first service, and *narrow to the account* and *take them all* are
indistinguishable in it. **This fixture offers SIX and takes THREE**, and the
three taken are deliberately NOT a prefix of the six.

⚠ **THE SECOND FALSE PASS IS THE EXPENSIVE ONE AND `tc2` IS THE ONLY GUARD ON
IT.** A narrowing that simply drops every plan service with no agreement also
drops the ones `BR-BIL-301` rules must be billed at `$0.00` and *said so* — a
service with no connection cannot have an agreement, so it arrives at the same
test. That would reverse a PO ruling of the previous day in silence, and every
other assertion here would still pass.

⚠ **AND THE THIRD IS QUIETEST OF ALL — `tc6`.** Narrowing removes a service
from `tariffs`, and `_unpriced_unit_service_lines` emits `OQ-670`'s `$0.00`
*(not priced on this plan)* line for exactly *a unit service that is not
priced*. So without `taken_services=` the defect comes straight back wearing a
different sentence: the customer reads a bill listing the services they
refused.

⚠ **THE FIXTURE PATCHES `resolution_shadow._seam` AS WELL AS `gather._resolve`**
for the reason `test_br_bil_301_not_connected_zero_line.py` gives: the shipped
`R3,R4` chain reaches metering through `resolution_shadow._seam`, which calls
`import_module` directly and cannot see a patch of `gather._resolve`.
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

#: The PO's own scenario, held as constants so a reader can count them.
SIX = ("electric", "water", "gas", "sewer", "trash", "fire")
#: Three, and DELIBERATELY NOT the first three of `SIX` — a narrowing that
#: simply truncates would pass a prefix.
THREE = ("electric", "gas", "fire")

NOT_CONNECTED = "(not connected)"
NOT_PRICED = "(not priced on this plan)"


@pytest.fixture(autouse=True)
def _rolled_back_resolution_chain(settings):
    """`SBH_BILLING_RESOLUTION_STEPS` EMPTY, and why — a STATED limit.

    The shipped default is `R3,R4` (`CR-057`), whose rating catalogue reads
    `app.tenant_id` and raises `AuthError: AUTH-003` outside a tenant context;
    a fixture of plain namespaces cannot supply one, so with the chain on every
    case here would die before its own assertion. That is exactly how
    `test_def_1060_the_unit_decides_which_services_bill.py` came to have 7 of
    its 10 cases red at the tip (`DEF-BIL-6773`).

    **WHY IT COSTS THIS PROOF NOTHING:** `BR-BIL-1048` acts inside
    `_tariffs_for_plan` and `gather_account`, BEFORE `resolution_switch.apply`
    is called, and the switch substitutes prices on tariffs that this narrowing
    has already removed — it cannot re-add one.

    **AND THE SHIPPED CHAIN IS COVERED ELSEWHERE, ON REAL POSTGRESQL:**
    `10-scripts/br_bil_1048_account_subset_measure.py` narrows a real account on
    a seeded six-service tenant and bills it with the default `R3,R4` in force,
    before and after.
    """
    settings.BILLING_RESOLUTION_STEPS = ""


def an_account(**overrides):
    values = dict(
        id="acct-subset",
        account_no="AC-2026-00003",
        unit_id="unit-six",
        status=SimpleNamespace(behavior_class="billable"),
        tax_exempt=False,
        opened_at=None,
        closed_at=None,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _pricing_inputs(tariff, _service_date, *_size, **_kw):
    service = getattr(tariff, "service", None)
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
        "version_id": f"v-{service}",
        "model": "flat",
        "billed_unit": "kgal",
        "base_charge": "8.00",
        "minimum_bill": None,
        "currency": "USD",
        "unit_price": "3.00",
        "tiers": [],
    }


def _world(*, plan_services, unit_services, taken):
    """Three lists held apart, because the defect is that two of them were one.

    `plan_services` — what the tariff prices · `unit_services` — what the
    PROPERTY is connected for (`BR-BIL-300`) · `taken` — what the ACCOUNT
    bought (`BR-CUS-1101`). `taken=None` is *nobody can tell*.
    """
    sized = {code: "FL-6" for code in unit_services}
    return {
        "customers.billed_service_codes_for": (
            None if taken is None else (lambda _a, **_k: tuple(taken))
        ),
        "metering.connection_size_for": lambda _unit, code: sized.get(code),
        "metering.billing_multiplier_for": lambda _unit, _code: Decimal("1"),
        "metering.billable_size_groups": (
            lambda _unit, code, _as_of: (
                {"FL-6": 1} if code == "fire" and code in unit_services else None
            )
        ),
        "metering.unit_row": lambda _id: SimpleNamespace(
            id="unit-six", label="Unit 1", rate_plan_id="plan-res", premises=None
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
            {"service_code": code, "tariff": SimpleNamespace(id=f"t-{code}", service=code)}
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
        "rating.plan_tax_rules": lambda *_a, **_k: [],
        "tenancy.regional_settings": lambda: {"currency": "USD"},
    }


def _install(monkeypatch, published):
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


def _reads(*codes):
    """5 kgal for every METERED service. Fire carries no read and must not:
    it is a counting capacity service (`CR-063`) whose quantity is what is
    installed, and a `kgal` read against a `connection` tariff is refused by
    name (`BR-RAT-038`)."""
    return tuple(
        ServiceReading(
            service_code=code, consumption=Quantity(amount=Decimal("5"), unit="kgal")
        )
        for code in codes
        if code != "fire"
    )


def _services(data):
    return sorted(getattr(config, "service", "") for config in data.tariffs)


def _fee_services(data):
    return sorted(line.service for line in data.fees)


def _price(data):
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
                    # The config's OWN billed unit, never a literal `kgal`:
                    # fire is priced per `connection` and the engine refuses a
                    # quantity in the wrong unit by name (`BR-RAT-038`), which
                    # is CLAUDE.md rule 3 doing its job on a fixture.
                    Quantity(amount=Decimal("0"), unit=config.billed_unit),
                ),
            )
            for config in data.tariffs
        ),
        period=rating_seam.BillingPeriod(
            start=PERIOD_START, end=PERIOD_END, cycle_days=30, service_days=30
        ),
        account=rating_seam.AccountContext(currency="USD", tax_exempt=False),
        taxes=data.taxes,
        fees=data.fees,
    )


# ══════════════════════════════════════════════════════════════════════════
# (1) THE DELIVERABLE — six offered, six connected, THREE taken, three billed
# ══════════════════════════════════════════════════════════════════════════
def test_br_bil_1048_tc1__three_of_six_are_billed_and_the_other_three_vanish(
    monkeypatch,
):
    """**The PO's own scenario, and BOTH sides are asserted.**

    RED BEFORE THE FIX: `tariffs` held all six and the bill charged for all
    six — the assertion below read
    `['electric', 'fire', 'gas', 'sewer', 'trash', 'water'] != ['electric',
    'fire', 'gas']`.

    ⚠ **THE SECOND HALF IS THE HALF THAT MATTERS.** *No line of any kind* — not
    a tariff, not a `$0.00` fee, not a note. A service the account refused must
    be ABSENT from the document, because a zero line naming it is a bill listing
    what they said no to.
    """
    _install(monkeypatch, _world(plan_services=SIX, unit_services=SIX, taken=THREE))

    data = _gather(readings=_reads(*SIX))

    # (1) exactly the three taken, priced as tariffs
    assert _services(data) == sorted(THREE)
    # (2) the other three reach the document NOWHERE — no fee line either
    for code in set(SIX) - set(THREE):
        assert code not in _fee_services(data), (code, _fee_services(data))
        assert not [
            line for line in data.fees if code in (line.description or "")
        ], (code, [line.description for line in data.fees])


def test_br_bil_1048_tc2__a_plan_service_with_no_connection_still_bills_zero(
    monkeypatch,
):
    """⚠ **`BR-BIL-301` IS NOT REVERSED BY THIS, AND THIS IS THE GUARD.**

    ⚠⚠ **AMENDED 2026-09-30 — THE GUARD MOVED FROM THE DOCUMENT TO THE REVIEW
    LIST.** PO: *"sane no line - and use 0"*: a service not in service prints
    NO line, so *we cannot supply it* and *they did not buy it* now look the
    same on the bill. What still separates them — and what this asserts now —
    is that the unconnected one is carried as `unconnected_services` (the
    clerk's list) and the refused ones are not. RED against the ruling's code
    before this edit: `assert 0 == 1` (the `$0.00` line it counted is gone).

    A service the property has **no connection** for cannot have an agreement,
    so a narrowing written naively drops it — and PO ruling 2026-09-25, option
    (b), says it is billed `$0.00` and *says so*. The two cases are opposite:
    *we cannot supply it* against *they did not buy it*.

    Here the plan prices six, the unit is connected for five (no fire line),
    and the account holds those five. Fire must still reach the document at
    `$0.00`, marked *not connected*, and must still carry NO tariff — a tariff
    would bill the standing charge for a connection that does not exist
    (`BR-RAT-080`).
    """
    connected = tuple(c for c in SIX if c != "fire")
    _install(
        monkeypatch,
        _world(plan_services=SIX, unit_services=connected, taken=connected),
    )

    data = _gather(readings=_reads(*connected))

    assert "fire" not in _services(data)
    assert [line for line in data.fees if line.service == "fire"] == []
    assert data.unconnected_services == ("fire",)


def test_br_bil_1048_tc3__taking_every_service_is_byte_for_byte_what_it_was(
    monkeypatch,
):
    """**THE UNCHANGED DEFAULT, which is every bill this product has issued.**

    `BR-CUS-1101`: *"`services` absent means all of them"*. An account whose
    agreements cover everything its plan prices must price exactly as before —
    six tariffs, no extra line, not one cent moved. Without this case the
    narrowing could be over-eager and nothing here would say so.
    """
    _install(monkeypatch, _world(plan_services=SIX, unit_services=SIX, taken=SIX))

    data = _gather(readings=_reads(*SIX))

    assert _services(data) == sorted(SIX)
    assert [line.description for line in data.fees] == []


def test_br_bil_1048_tc4__nobody_can_tell_narrows_nothing(monkeypatch):
    """**`None` IS *NOBODY CAN TELL*, AND IT MUST NARROW NOTHING.**

    Customers has not published the read, or the account holds no overlapping
    agreement at all — an import that never wrote agreements, a row with no
    dates. Narrowing to nothing there would zero a real customer's bill on an
    ABSENCE, which is a worse defect than the one this rule fixes, so the
    three-valued answer is the rule and not a convenience.
    """
    _install(monkeypatch, _world(plan_services=SIX, unit_services=SIX, taken=None))

    data = _gather(readings=_reads(*SIX))

    assert _services(data) == sorted(SIX)


def test_br_bil_1048_tc5__oq_670s_zero_line_survives_for_a_service_taken(
    monkeypatch,
):
    """**A unit service the plan prices NOWHERE, that the account DID take.**

    `OQ-670` (PO 2026-08-27, option (b)) rules that at `$0.00` with its own
    sentence. Narrowing must not touch it: the account bought the service, the
    plan prices it nowhere, and the gap belongs on the document.
    """
    _install(
        monkeypatch,
        _world(
            plan_services=("electric", "gas"),
            unit_services=SIX,
            taken=("electric", "gas", "trash"),
        ),
    )

    data = _gather(readings=_reads("electric", "gas"))

    trash = [line for line in data.fees if line.service == "trash"]
    assert len(trash) == 1, [(f.service, f.description) for f in data.fees]
    assert trash[0].amount == Decimal("0.0000")
    assert trash[0].description == f"trash {NOT_PRICED}"


def test_br_bil_1048_tc6__the_defect_does_not_return_wearing_oq_670s_sentence(
    monkeypatch,
):
    """⚠⚠ **THE QUIETEST FALSE PASS, AND THE ONLY CASE THAT CATCHES IT.**

    Narrowing removes a service from `tariffs`. `_unpriced_unit_service_lines`
    emits `OQ-670`'s `$0.00` *(not priced on this plan)* line for precisely *a
    service the unit takes that is not priced*. So a fix that stops at
    `_tariffs_for_plan` gives the customer a bill that still names water, sewer
    and trash — at zero, with a sentence blaming the plan — when the truth is
    that they never bought them.

    Here the plan prices all six, the unit is connected for all six, the
    account took three, and the other three must produce **no line at all**,
    neither priced nor zero.
    """
    _install(monkeypatch, _world(plan_services=SIX, unit_services=SIX, taken=THREE))

    data = _gather(readings=_reads(*SIX))

    for code in set(SIX) - set(THREE):
        assert not [
            line
            for line in data.fees
            if line.service == code or NOT_PRICED in (line.description or "")
        ], [(f.service, f.description) for f in data.fees]


def test_br_bil_1048_tc7__narrowing_only_ever_subtracts(monkeypatch):
    """**IT CAN NEVER EMPTY A BILL, AND THAT IS ASSERTED AT THE JOINT.**

    `_plan_services_not_taken` answers `()` for `taken=None`, so a bill can
    never be narrowed to nothing by an absence. Asserted directly on the
    function as well as through `tc4`, because this is the property that keeps
    a mistake in the READ from becoming a zeroed invoice.
    """
    _install(monkeypatch, _world(plan_services=SIX, unit_services=SIX, taken=None))

    assert (
        gather._plan_services_not_taken(
            "unit-six",
            "plan-res",
            taken=None,
            scope_services=None,
            unconnected=(),
        )
        == ()
    )


def test_br_bil_1048_tc8__the_money_moves_by_exactly_the_three_refused(
    monkeypatch,
):
    """**THE FIGURE, PRICED THROUGH THE ENGINE AND NOT ASSERTED ON A LIST.**

    Each metered service is 5 kgal × `$3.00` + `$8.00` base = **`$23.00`**.
    Fire carries no read, so its FL-6 line is `$0.00` and it bills its `$9.00`
    base alone. Taking all six is `$23.00 × 5 + $9.00 = ` **`$124.00`**; taking
    electric, gas and fire is `$23.00 × 2 + $9.00 = ` **`$55.00`**.

    **The difference is `$69.00`, which is water, sewer and trash at `$23.00`
    each — exactly the three refused, and nothing else.** That last clause is
    the assertion that matters: a narrowing that also disturbed a per-service
    figure would move the total by some other number, and a frozen B4/B5 amount
    would be moving with it.
    """
    _install(monkeypatch, _world(plan_services=SIX, unit_services=SIX, taken=SIX))
    everything = _price(_gather(readings=_reads(*SIX))).total

    _install(monkeypatch, _world(plan_services=SIX, unit_services=SIX, taken=THREE))
    three = _price(_gather(readings=_reads(*SIX))).total

    assert everything == Decimal("124.0000"), everything
    assert three == Decimal("55.0000"), three
    assert everything - three == Decimal("69.0000")
