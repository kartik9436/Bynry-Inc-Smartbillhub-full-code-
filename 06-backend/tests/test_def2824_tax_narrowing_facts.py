# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2824 (2026-08-31) — `resolution_catalogue.tax_facts` called
#          `rating.selectors.plan_tax_rules` POSITIONALLY, with no customer
#          class, no premises and no service list. All three restrictions FAIL
#          CLOSED, so every class-scoped, premises-scoped or service-scoped tax
#          was silently absent from every ruled bill on every tenant — under a
#          comment asserting the narrowing had ALREADY happened.
#          Measured on the seeded utility, 47 accounts: the live path attached
#          `Texas State` (6.25 %, commercial + industrial only) on both
#          commercial accounts and the ruled chain attached only `Local`.
# Rules:   DEF-273 / PO 2026-08-18 (r10's three applicability conditions, ALL
#          fail-closed) · DEF-383 (the exemption CERTIFICATE, which fails OPEN)
#          · DEF-465 (`applies_to_services` also narrows the BASE) ·
#          BR-BIL-069 / OQ-116 (a tax names its authority) · BR-RAT-113 ·
#          CLAUDE.md hard rule 1 (tenant scoping) · hard-won law 1 (a comment
#          claiming a guarantee is not the guarantee) · law 7 (prove a guard RED)
# Tests:   this file
# Impacts: apps/rating/resolution_catalogue.py 🔒 (`tax_facts`,
#          `build_catalogue`, `_plan_services`, `_premises_scope_facts`) ·
#          apps/rating/resolution.py 🔒 (`AccountFacts.account_id`,
#          `PremisesFacts.city` / `.state`) ·
#          apps/billing/resolution_shadow.py 🔒 (`adapt`, `_premises_facts`) ·
#          apps/billing/resolution_switch.py 🔒 ·
#          10-scripts/cr052_r1r7_shadow_measure.py
# ───────────────────────────────────────────────────────
"""R7's candidate set is narrowed by facts, and the facts now REACH it.

⚠ **WHY THIS FILE ASSERTS AUTHORITIES BY NAME AND NEVER "SOME TAX ATTACHED".**
R7 publishes no refusal class and never will — a failed applicability condition
means NO LINE, never an error (DEF-273) — so its only possible output is
silence, and a test asserting "the chain resolved" passes just as happily over
an empty tax set as over the right one. That is precisely how this defect hid
for the whole life of the file. **Every case below names the authorities on both
sides AND asserts the set is non-empty**, so a comparison that stops comparing
fails instead of passing.

── THE RED PROOF, QUOTED, AND WHAT IT DOES *NOT* COVER (hard-won law 7) ─────

The defect was re-introduced as the one line it was — `plan_tax_rules(plan_id,
service_date)`, positional, nothing else changed, the file restored afterwards
and verified byte-identical by sha256 — and this suite ran against it:

    6 failed, 7 passed

**SIX go red, and they are the six that assert a tax the utility charges is
present:** TC1 (customer class), TC4 (premises state), TC5 (premises city),
TC6 (services), TC8 (the exemption certificate) and TC10 (the catalogue itself).

    E  AssertionError: ('Testland County',)
       assert ('Testland County',) == ('Testland County', 'Testland State')

**TC8 fails the OTHER way, and that is the finding worth reading twice:**

    E  AssertionError: ('Testland County', 'Testland State')
       assert ('Testland County', 'Testland State') == ('Testland County',)

— the broken code CHARGED the state tax to an account holding a live exemption
certificate, because `account_id` never reached the selector and that one gate
fails OPEN. Under-charging five ways and over-charging a sixth, from one line.

⚠ **THE OTHER SEVEN CANNOT GO RED ON THIS DEFECT AND ARE NOT CLAIMED TO.**
TC2, TC3 and TC7 assert a restricted tax is ABSENT — which the broken code also
does, for the wrong reason — so they are the anti-fail-open guards: they exist so
that the tempting "fix" (treat a missing restriction as no restriction) fails
here instead of on a customer's bill. TC9, TC11, TC12 and TC13 are structural:
on the pre-fix tree they fail at the signature (`TypeError: build_catalogue() got
an unexpected keyword argument 'account'`), which proves nothing about narrowing.
Saying which cases bite and which do not is the point — a suite reported as
"13 red first" would be a check that cannot fail wearing better manners.

On real rows, same day, same posture: the seeded tenant's two commercial accounts
moved from `('Local',)` back to `('Local', 'Texas State')`, restoring **$20.76**
and **$14.91** of `Texas State` tax the ruled chain had dropped.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.rating import models as rating_models
from apps.rating import resolution, resolution_catalogue

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, tenant_ctx

pytestmark = pytest.mark.django_db

SERVICE_DATE = date(2026, 7, 31)

#: The two authorities this file uses, **as `plan_tax_rules` reports them**: a
#: jurisdiction-bound percent rule's `code` is the JURISDICTION's name, which is
#: what a remittance report groups by (BR-BIL-069) and what the shadow's R7
#: comparison prints (`('Local', 'Texas State')` on the seeded utility).
#:
#: NOT the platform-seeded "Texas State" / "Local" rows: provisioning plants
#: r10's five ruled TX rates (DEF-254/273), and `_authority_tax` resolves a
#: jurisdiction's OWN row, so reusing a seeded jurisdiction would make every
#: assertion here measure the seed instead of the feature.
#: `test_br_rat_113_attach_taxes` records the same reasoning.
STATE = "Testland State"
COUNTY = "Testland County"


def a_tax(tenant, jurisdiction_name, **fields):
    jurisdiction, _ = rating_models.TaxJurisdiction.objects.get_or_create(
        tenant=tenant, name=jurisdiction_name
    )
    return (
        rating_models.Tax.objects.create(tenant=tenant, jurisdiction=jurisdiction, **fields),
        jurisdiction,
    )


def bind(tenant, plan, jurisdiction):
    rating_models.PlanTaxRule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, jurisdiction=jurisdiction
    )


def county_rate(tenant, plan):
    """2.00 %, UNCONDITIONAL — the control. It attaches in every case below, so
    an empty result can never be mistaken for "the restriction worked"."""
    tax, jurisdiction = a_tax(
        tenant,
        COUNTY,
        name="Local · Testland County",
        kind="percent",
        rate=Decimal("0.020000"),
    )
    bind(tenant, plan, jurisdiction)
    return tax


def state_rate(tenant, plan, **restriction):
    """6.25 %, carrying whatever restriction the case is about."""
    tax, jurisdiction = a_tax(
        tenant,
        STATE,
        name="TX State Utility Tax",
        kind="percent",
        rate=Decimal("0.062500"),
        **restriction,
    )
    bind(tenant, plan, jurisdiction)
    return tax


def facts(*, customer_class=None, account_id=None):
    return resolution.AccountFacts(
        account_no="AC-0001",
        unit_id="unit-1",
        customer_class=customer_class,
        account_id=account_id,
    )


def codes(plan, account, premises, *, services=("electric",)):
    """The authorities the WHOLE ruled path attaches: catalogue THEN R7.

    Both halves, always — the defect lived in the seam between them, and a test
    that exercised either alone would have passed on the broken tree.
    """
    catalogue = resolution_catalogue.build_catalogue(
        plan_id=plan.id,
        service_date=SERVICE_DATE,
        account=account,
        premises=premises,
    )
    return tuple(
        sorted(
            rule.code
            for rule in resolution.resolve_taxes(catalogue, account, premises, tuple(services))
        )
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · CUSTOMER CLASS — the axis the measurement caught
# ══════════════════════════════════════════════════════════════════════════


def test_tc1__a_commercial_account_attaches_the_class_restricted_tax(brazos):
    """THE DEFECT. r10: *"Comm, Industrial only · Residential exempt"*.

    Before the fix this returned `('Testland County',)` — the state tax
    was dropped by `plan_tax_rules` for want of a customer class it was never
    given, and `resolve_taxes` was handed nothing to narrow.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-2824 Class")
        county_rate(brazos, plan)
        state_rate(brazos, plan, applies_to_customer_classes=["commercial", "industrial"])

        names = codes(plan, facts(customer_class="commercial"), resolution.PremisesFacts())

    assert names == (COUNTY, STATE), names
    assert len(names) == 2, "the comparison compared nothing — see the module docstring"


def test_tc2__a_residential_account_still_does_not(brazos):
    """The other direction, and it is the one a fail-OPEN "fix" would break.

    Passing the facts must not become *"no restriction"*: a residential customer
    r10 exempts is not charged the state tax, and the unconditional county rate
    is still there to prove the query ran at all.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-2824 Class Res")
        county_rate(brazos, plan)
        state_rate(brazos, plan, applies_to_customer_classes=["commercial", "industrial"])

        names = codes(plan, facts(customer_class="residential"), resolution.PremisesFacts())

    assert names == (COUNTY,), names
    assert names, "the unconditional control tax is missing — this test measured nothing"


def test_tc3__an_account_with_no_class_recorded_fails_closed(brazos):
    """DEF-273's fail-safe, preserved: under-charging is recoverable, charging a
    customer who is exempt is a refund and a support cycle."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-2824 Class None")
        county_rate(brazos, plan)
        state_rate(brazos, plan, applies_to_customer_classes=["commercial"])

        names = codes(plan, facts(customer_class=None), resolution.PremisesFacts())

    assert names == (COUNTY,), names


# ══════════════════════════════════════════════════════════════════════════
# 2 · PREMISES — the axis `resolve_taxes` CANNOT express at all
# ══════════════════════════════════════════════════════════════════════════


def test_tc4__a_state_scoped_tax_needs_the_premises_state(brazos):
    """`inside_city_only` / `outside_city_only` cannot say "in Texas".

    So this axis can only ever be decided by `selectors.premises_in_scope`, and
    only if the state reaches it. It did not: `PremisesFacts` carried the
    city-limits flag alone until this defect.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-2824 State Scope")
        county_rate(brazos, plan)
        state_rate(brazos, plan, premises_scope_kind="state", premises_scope_value="TX")

        in_texas = codes(
            plan, facts(customer_class="residential"), resolution.PremisesFacts(state="TX")
        )
        elsewhere = codes(
            plan, facts(customer_class="residential"), resolution.PremisesFacts(state="NM")
        )
        unrecorded = codes(plan, facts(customer_class="residential"), resolution.PremisesFacts())

    assert in_texas == (COUNTY, STATE), in_texas
    assert elsewhere == (COUNTY,), elsewhere
    # An unrecorded state is not "everywhere": a scope nobody can answer reaches
    # nobody (DEF-273's direction), and the control tax proves the query ran.
    assert unrecorded == (COUNTY,), unrecorded


def test_tc5__a_city_limits_scope_falls_back_to_the_recorded_city(brazos):
    """r10's *"Inside city limits"*, on a tenant that has not drawn its boundary.

    `premises_in_scope` answers by the FLAG where one exists and by the recorded
    CITY NAME where it does not — a fallback that was unreachable from the chain,
    because the chain carried no city.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-2824 City Scope")
        county_rate(brazos, plan)
        state_rate(
            brazos,
            plan,
            premises_scope_kind="city_limits",
            premises_scope_value="San Antonio",
        )

        inside = codes(
            plan,
            facts(customer_class="residential"),
            resolution.PremisesFacts(city="San Antonio"),
        )
        outside = codes(
            plan, facts(customer_class="residential"), resolution.PremisesFacts(city="Helotes")
        )
        # The FLAG wins over the name when it is recorded — a utility that has
        # drawn its boundary is not second-guessed by a spelling.
        flagged_out = codes(
            plan,
            facts(customer_class="residential"),
            resolution.PremisesFacts(inside_city_limits=False, city="San Antonio"),
        )

    assert inside == (COUNTY, STATE), inside
    assert outside == (COUNTY,), outside
    assert flagged_out == (COUNTY,), flagged_out


# ══════════════════════════════════════════════════════════════════════════
# 3 · SERVICES — narrowed TWICE, and the composition is the claim under test
# ══════════════════════════════════════════════════════════════════════════


def test_tc6__a_service_scoped_tax_attaches_only_where_that_service_bills(brazos):
    """`build_catalogue` passes the PLAN's service set so a candidate is not
    pre-dropped; `resolve_taxes` then narrows to the services that RESOLVED.

    Both halves are asserted, because the safety of passing the wider set rests
    entirely on the second one still running.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-2824 Services", services=("electric", "water"))
        county_rate(brazos, plan)
        state_rate(brazos, plan, applies_to_services=["electric"])

        residential = facts(customer_class="residential")
        whole_plan = codes(
            plan, residential, resolution.PremisesFacts(), services=("electric", "water")
        )
        # THE SECOND NARROWING. The catalogue admitted the electric-scoped tax —
        # electric is on the plan — and R7 drops it because this bill resolved
        # water alone.
        water_only = codes(plan, residential, resolution.PremisesFacts(), services=("water",))

    assert whole_plan == (COUNTY, STATE), whole_plan
    assert water_only == (COUNTY,), water_only


def test_tc7__a_tax_scoped_to_a_service_the_plan_does_not_sell_never_appears(brazos):
    """And the FIRST narrowing, from the other end: a gas-only tax on a plan
    that sells no gas is refused by the selector before a candidate exists."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-2824 No Gas", services=("electric",))
        county_rate(brazos, plan)
        state_rate(brazos, plan, applies_to_services=["gas"])

        names = codes(plan, facts(customer_class="residential"), resolution.PremisesFacts())

    assert names == (COUNTY,), names


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE EXEMPTION CERTIFICATE — the one gate whose absence OVER-charges
# ══════════════════════════════════════════════════════════════════════════


def test_tc8__a_live_certificate_removes_that_authoritys_tax_and_no_others(brazos):
    """DEF-383, reached from the chain for the first time.

    The three restrictions fail CLOSED, so forgetting them under-charges. An
    exemption fails OPEN, so forgetting `account_id` CHARGES a customer holding
    a live certificate — the direction that is a refund rather than a catch-up.

    A church exempt from the state tax still pays the county's: the certificate
    is per TAX and per CATEGORY, never blanket.
    """
    account_uuid = "01a0549c-0000-7000-8000-00000000d824"
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-2824 Exemption")
        county_rate(brazos, plan)
        state = state_rate(brazos, plan)

        category = rating_models.TaxExemptionCategory.objects.create(
            tenant=brazos, tax=state, code="religious", name="Religious"
        )
        rating_models.TaxExemptionCertificate.objects.create(
            tenant=brazos,
            category=category,
            account_id=account_uuid,
            expires_on=SERVICE_DATE + timedelta(days=365),
        )

        holder = codes(
            plan,
            facts(customer_class="commercial", account_id=account_uuid),
            resolution.PremisesFacts(),
        )
        neighbour = codes(
            plan,
            facts(
                customer_class="commercial",
                account_id="01a0549c-0000-7000-8000-00000000ffff",
            ),
            resolution.PremisesFacts(),
        )

    assert holder == (COUNTY,), holder
    assert neighbour == (COUNTY, STATE), neighbour


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE STARVATION GUARD — the half that stops this recurring
# ══════════════════════════════════════════════════════════════════════════


def test_tc9__the_catalogue_cannot_be_built_without_r7s_facts(brazos):
    """⚠ **THE DURABLE FIX, AND IT IS A SIGNATURE RATHER THAN A COMMENT.**

    A default on any of these would restore the exact arrangement the defect
    names — each layer believing the other narrowed — and it would fail closed
    and silently, on money, in the one step of the chain that publishes no
    refusal. So a caller that cannot name the bill's facts gets a `TypeError`
    at the call site instead of a customer under-charged.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-2824 Required")

        with pytest.raises(TypeError):
            resolution_catalogue.build_catalogue(  # type: ignore[call-arg]
                plan_id=plan.id, service_date=SERVICE_DATE
            )
        with pytest.raises(TypeError):
            resolution_catalogue.build_catalogue(  # type: ignore[call-arg]
                plan_id=plan.id,
                service_date=SERVICE_DATE,
                account=facts(customer_class="commercial"),
            )
        with pytest.raises(TypeError):
            resolution_catalogue.build_catalogue(  # type: ignore[call-arg]
                plan_id=plan.id,
                service_date=SERVICE_DATE,
                premises=resolution.PremisesFacts(),
            )
        # And the function underneath it, one fact at a time — because
        # `build_catalogue` is not the only way to reach `tax_facts`.
        every = {
            "customer_class": "commercial",
            "premises": {},
            "services": ("electric",),
            "account_id": None,
        }
        for omitted in sorted(every):
            with pytest.raises(TypeError):
                resolution_catalogue.tax_facts(  # type: ignore[call-arg]
                    plan.id,
                    SERVICE_DATE,
                    **{key: value for key, value in every.items() if key != omitted},
                )


def test_tc10__the_catalogue_passes_the_facts_rather_than_holding_them(brazos):
    """`Catalogue.taxes` is the only thing the account facts reach.

    R1–R6 stay a pure function of what the tenant CONFIGURED — the same
    catalogue, built for a commercial and a residential account, differs in its
    taxes and in nothing else. If that ever stops being true, an account fact
    has leaked into a configuration answer.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-2824 Isolation")
        county_rate(brazos, plan)
        state_rate(brazos, plan, applies_to_customer_classes=["commercial"])

        common = {
            "plan_id": plan.id,
            "service_date": SERVICE_DATE,
            "premises": resolution.PremisesFacts(),
        }
        commercial = resolution_catalogue.build_catalogue(
            account=facts(customer_class="commercial"), **common
        )
        residential = resolution_catalogue.build_catalogue(
            account=facts(customer_class="residential"), **common
        )

    assert sorted(rule.code for rule in commercial.taxes) == [
        COUNTY,
        STATE,
    ]
    assert sorted(rule.code for rule in residential.taxes) == [COUNTY]
    assert commercial.plan_versions == residential.plan_versions
    assert commercial.schedule_versions == residential.schedule_versions
    assert commercial.charge_codes == residential.charge_codes
    assert commercial.discounts == residential.discounts
    assert commercial.outside_city_factor == residential.outside_city_factor


def test_tc11__the_service_set_is_r1s_own_union_and_not_a_second_reading(brazos):
    """`_plan_services` is R1's answer, re-used.

    `plan_version_facts` unions `plan_services` with `plan_rate_schedules` and
    says why (*"a service BOUND TO A SCHEDULE but missing from `plan_services`
    would vanish from the bill in silence"*). Deriving the tax query's service
    list any other way would be a second implementation of that judgment, and
    the two could disagree about which services a bill covers.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="DEF-2824 Union", services=("electric", "water"))
        versions = resolution_catalogue.plan_version_facts(plan.id)

        assert resolution_catalogue._plan_services(versions) == ("electric", "water")
        assert resolution_catalogue._plan_services(versions) == tuple(sorted(versions[0].services))


def test_tc12__the_premises_dict_carries_exactly_the_three_keys_that_are_read(brazos):
    """`premises_in_scope` reads `inside_city_limits`, `city` and `state` by name.

    `county` is deliberately NOT passed: that predicate cannot answer a county
    scope at all (no column, no district table, no premise set) and returns
    False for it, so handing it a key it never reads would suggest otherwise.
    """
    dictionary = resolution_catalogue._premises_scope_facts(
        resolution.PremisesFacts(
            inside_city_limits=True, city="San Antonio", state="TX", county="Bexar"
        )
    )
    assert dictionary == {
        "inside_city_limits": True,
        "city": "San Antonio",
        "state": "TX",
    }


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE ADAPTER — the facts have to be gathered as well as accepted
# ══════════════════════════════════════════════════════════════════════════


def test_tc13__the_shadow_adapter_reads_the_premises_geography_not_just_the_flag(brazos):
    """`resolution_shadow._premises_facts` — one premises read, both questions.

    It used to be `_inside_city_limits` and returned the flag alone, so even
    once `PremisesFacts` could carry a city and a state, nothing would have put
    them there. A signature that accepts a fact nobody supplies is the same
    defect one layer along (hard-won law 2 — built is not wired).
    """
    from apps.billing import resolution_shadow

    class _Premises:
        inside_city_limits = False
        city = "Helotes"
        state = "TX"

    class _Unit:
        premises = _Premises()

    class _Account:
        unit_id = "unit-1"

    seam = resolution_shadow._seam("metering", "unit_row")
    assert seam is not None, "metering publishes no `unit_row` seam — the adapter is blind"

    from apps.metering import selectors as metering_selectors

    original = metering_selectors.unit_row
    metering_selectors.unit_row = lambda _unit_id: _Unit()
    try:
        premises = resolution_shadow._premises_facts(_Account())
    finally:
        metering_selectors.unit_row = original

    assert premises.inside_city_limits is False
    assert premises.city == "Helotes"
    assert premises.state == "TX"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2824 + DEF-273 (PO 2026-08-18) + DEF-383 + DEF-465 + CR-052 task 20
# generated: 2026-08-31 by the DEF-2824 lane (claude)
# checklist: A✔ B✔ C✔ D=n/a(pure module, no API half) E=n/a(no frontend half —
#         the chain has no screen) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: every case proved RED against the pre-fix tree first and the failures
#         quoted in the module docstring · golden-verify 33 PASS / 0 FAIL before
#         and after (no ❄️ figure moves — R7 decides applicability, never an
#         amount) · the shadow measurement re-run on 47 real accounts under
#         `rolsuper=false, rolbypassrls=false`
# exceptions: NOTHING IS SWITCHED ON. `resolution_switch.SERVED_BY_CHAIN_DEFAULT`
#         is still empty, so no rule prices any real bill through the chain and
#         no customer's tax moves today. This changes what R7 WOULD attach at
#         step 5 of the cutover.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
