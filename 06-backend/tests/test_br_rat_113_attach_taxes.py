# ── Trace ──────────────────────────────────────────────
# Story:    CR-021 → BR-RAT-113 (staff pick and attach taxes & fees on the
#           plan; PLN-03 step 5 is no longer read-only)   Screens: PLN-03
#           step 5 (S10 wizard) · S31.2 (the tax lines it produces)
# Rules:    BR-RAT-113 (attach is ADD-ONLY; a mandated tax stays on the bill
#           whether or not anyone ticked it; detach-of-mandated NOT ruled) ·
#           BR-RAT-094 (a plan attaches prices, never sets one — no
#           rate_override) · BR-RAT-096 (plan binds; jurisdiction still gates)
#           · BR-RAT-037 (published-plan content change needs reason+version) ·
#           BR-BIL-069 (a tax line names its authority)
# Golden:   NONE MOVES. B4/B5 ❄️ FROZEN — this change grows WHICH taxes attach,
#           never any arithmetic. GT-1's 8.25 % pair is re-asserted below as
#           6.25 + 2.00 on a $100.00 base = $8.25, one path derived and one
#           attached, and the derived-only figure is byte-identical to before.
# Tests:    this file
# Impacts:  apps/rating/models.PlanTaxRule · apps/rating/services (plan tax
#           block, attach/detach) 🔒 · apps/rating/selectors.plan_tax_rules 🔒 ·
#           apps/rating/api (plans/{id}/taxes)
# ───────────────────────────────────────────────────────
"""BR-RAT-113 — explicit tax/fee attachments on a plan, ADD-ONLY.

PO verbatim (2026-08-21, closing CR-021): *"staff need to pick up and attach
taxes and fees on the plan."* And the boundary: a plan may attach taxes BEYOND
what its jurisdiction brings; *"a jurisdiction-mandated tax stays on the bill
whether or not anyone ticked it"*; whether staff may DETACH a mandated tax is
explicitly NOT ruled, so no test here exercises such a door — the test asserts
the door does not exist.

Every money assertion is a worked dollar figure on a $100.00 taxable base,
priced by the real engine through the same adaptation `apps/billing/gather.py`
performs (`rating_seam.price_period`) — the pattern
`tests/test_def_273_tax_conditions.py` established and this file reuses.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.rating import models as rating_models
from apps.rating import selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db

USD = "USD"
TAXED = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)

#: A bill whose taxable base is EXACTLY $100.00 (test_def_273's own fixture):
#: every tax figure below reads as its own percentage.
HUNDRED = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("100.00"),
    unit_price=Decimal("0"),
)
NO_USAGE = rating_seam.Quantity(amount=Decimal("0"), unit="kWh")


# ── plumbing (mirrors test_def_273_tax_conditions.py) ───────────────────────
def a_tax(tenant, jurisdiction_name, **fields):
    jurisdiction, _ = rating_models.TaxJurisdiction.objects.get_or_create(
        tenant=tenant, name=jurisdiction_name
    )
    return (
        rating_models.Tax.objects.create(tenant=tenant, jurisdiction=jurisdiction, **fields),
        jurisdiction,
    )


def bind(tenant, plan, jurisdiction):
    """Shape 1 — a BR-RAT-096 jurisdiction binding row."""
    rating_models.PlanTaxRule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, jurisdiction=jurisdiction
    )


def bill(rules):
    """Price a $100.00 taxable bill under exactly these resolved rules."""
    return rating_seam.price_period(
        tariff=HUNDRED,
        consumption=NO_USAGE,
        period=FULL_MONTH,
        account=TAXED,
        taxes=tuple(
            rating_seam.TaxRule(
                code=rule["code"],
                rate=None if rule.get("rate") is None else Decimal(str(rule["rate"])),
                tax_id=rule.get("tax_id"),
                flat_amount=(
                    None if rule.get("flat_amount") is None else Decimal(str(rule["flat_amount"]))
                ),
            )
            for rule in rules
        ),
    )


def state_tax(tenant):
    """A 6.25 % state utility tax — the PO's ruled STATE figure on an authority
    of this file's own. NOT the seeded "Texas State": provisioning plants the
    five ruled TX rows (DEF-254/273) and the seeded state tax is CONDITIONAL
    (commercial+industrial only), so reusing its jurisdiction would make
    `_authority_tax` resolve the seed's row instead of this one and every
    class-less assertion here would measure the seed, not the feature."""
    return a_tax(
        tenant,
        "Testland State",
        name="TX State Utility Tax",
        kind="percent",
        rate=Decimal("0.062500"),
    )


def county_tax(tenant):
    """A 2.00 % county rate (the PO's ruled COUNTY figure), unconditional, on
    an authority the platform seed does not use — same reason as above."""
    return a_tax(
        tenant,
        "Testland County",
        name="Local · Testland County",
        kind="percent",
        rate=Decimal("0.020000"),
    )


# ── 1 · AN ATTACHMENT REACHES A PRICED BILL ─────────────────────────────────
def test_tc1__an_attached_tax_prices_the_bill_exactly_like_a_derived_one(brazos, dana):
    """The capability itself: a plan binding NO jurisdiction attaches the 2.00 %
    county rate and a $100.00 bill carries **$2.00** of tax — through the same
    resolver, the same gates and the same engine as a jurisdiction binding."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Attach Only")
        county, _j = county_tax(brazos)
        services.attach_tax_to_plan(
            dana, plan.id, {"tax": str(county.id), "reason": "BR-RAT-113 TC-1"}
        )
        rules = selectors.plan_tax_rules(plan.id, services=("electric",))

    assert [rule["code"] for rule in rules] == ["Local · Testland County"]
    # BR-BIL-069 — an attachment ALWAYS names its tax row, so the line can be
    # stamped with the authority's liability account at issue.
    assert rules[0]["tax_id"] == str(county.id)
    priced = bill(rules)
    assert priced.tax_total == Decimal("2.00")
    assert priced.total == Decimal("102.00")


def test_tc2__attach_adds_BEYOND_the_jurisdiction_set(brazos, dana):
    """GT-1's own pair, assembled the new way: 6.25 % DERIVED from the bound
    state + 2.00 % ATTACHED from the catalogue = **$8.25** on $100.00. The
    derived half alone is $6.25 — byte-identical to pre-BR-RAT-113 pricing."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        _state, texas = state_tax(brazos)
        county, _j = county_tax(brazos)
        bind(brazos, plan, texas)

        derived_only = selectors.plan_tax_rules(plan.id, services=("electric",))
        services.attach_tax_to_plan(
            dana, plan.id, {"tax": str(county.id), "reason": "BR-RAT-113 TC-2"}
        )
        both = selectors.plan_tax_rules(plan.id, services=("electric",))

    assert bill(derived_only).tax_total == Decimal("6.25")  # unchanged by the feature
    assert bill(both).tax_total == Decimal("8.25")
    assert bill(both).total == Decimal("108.25")


# ── 2 · DE-DUPLICATION — the same tax via both paths bills ONCE ─────────────
def test_tc3__a_tax_reached_by_both_paths_bills_once(brazos, dana):
    """Bind Texas AND attach the state tax row itself: **$6.25**, never $12.50.
    The jurisdiction path wins (it is the mandated one); the attachment then
    adds nothing, which is what "beyond what its jurisdiction brings" means
    for a tax the jurisdiction already brings."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Redundant Attach")
        state, texas = state_tax(brazos)
        bind(brazos, plan, texas)
        services.attach_tax_to_plan(
            dana, plan.id, {"tax": str(state.id), "reason": "BR-RAT-113 TC-3"}
        )
        rules = selectors.plan_tax_rules(plan.id, services=("electric",))

    assert len(rules) == 1
    assert rules[0]["tax_id"] == str(state.id)
    assert bill(rules).tax_total == Decimal("6.25")


# ── 3 · A MANDATED TAX CANNOT BE DETACHED — REFUSED BY NAME ─────────────────
def test_tc4__detaching_the_LAST_tax_refuses_on_br_rat_115s_floor(brazos, dana):
    """⚠ **THIS CASE WAS TC-4's ABSOLUTE REFUSAL, INVERTED BY A PO RULING.**
    BR-RAT-115 (2026-08-22, verbatim: *"we ask madetory atleast 1 tax shuld
    be there"*) superseded the BR-RAT-094 refusal: a mandated tax MAY leave —
    the floor is that at least one tax stays. Here the 6.25 % state tax is
    the plan's ONLY tax, so the detach hits the floor, refuses BY NAME, and
    the $6.25 stays on the bill."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Floor Holds")
        state, texas = state_tax(brazos)
        bind(brazos, plan, texas)

        with pytest.raises(errors.BizError) as refused:
            services.detach_tax_from_plan(
                dana, plan.id, str(state.id), {"reason": "trying anyway"}
            )
        rules = selectors.plan_tax_rules(plan.id, services=("electric",))

    assert refused.value.br_ref == "BR-RAT-115"
    assert refused.value.message_key == "rating.plans.last_tax_not_detachable"
    assert refused.value.params["tax"] == "TX State Utility Tax"
    assert bill(rules).tax_total == Decimal("6.25")


def test_tc4b__a_mandated_tax_DETACHES_when_another_tax_stands(brazos, dana):
    """BR-RAT-115's grant, on its own worked figure: the plan binds Texas
    (6.25 %) AND attaches the 2.00 % county rate — $8.25 on $100.00. Detaching
    the MANDATED state tax is allowed with a reason; the bill drops to the
    county's **$2.00**, and the county survives as an explicit attachment."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Mandated May Go")
        state, texas = state_tax(brazos)
        county, _j = county_tax(brazos)
        bind(brazos, plan, texas)
        services.attach_tax_to_plan(dana, plan.id, {"tax": str(county.id), "reason": "BR-RAT-115 walkthrough"})
        assert bill(
            selectors.plan_tax_rules(plan.id, services=("electric",))
        ).tax_total == Decimal("8.25")

        services.detach_tax_from_plan(
            dana, plan.id, str(state.id), {"reason": "BR-RAT-115 walkthrough"}
        )
        rules = selectors.plan_tax_rules(plan.id, services=("electric",))
        rows = list(rating_models.PlanTaxRule.objects.filter(rate_plan=plan))

    assert bill(rules).tax_total == Decimal("2.00")
    # The Texas BINDING is gone — the plan no longer follows the authority
    # wholesale, which is what detaching a mandated tax MEANS — and what
    # remains is the county attachment alone.
    assert [str(r.tax_id) for r in rows if r.tax_id is not None] == [str(county.id)]
    assert all(r.jurisdiction_id is None or r.tax_id is not None for r in rows)


def test_tc4c__THE_WIDER_FLOOR__an_ATTACHED_last_tax_cannot_leave_either(brazos, dana):
    """⚠ **THE PO'S SECOND PASS ON BR-RAT-115** — verbatim: *"yes lets go with
    B"*. The first build guarded only the MANDATED path; this is the worked
    case that was put to the PO and changed it. The plan binds NO authority
    and carries ONE hand-attached tax — the 2.00 % county rate, **$2.00** on a
    $100.00 bill. Detaching it would leave the plan taxing NOTHING, so the
    floor refuses it exactly as it refuses the last mandated one, and the
    $2.00 stays on the bill. The gate is on the OUTCOME, never on the route
    the departing tax arrived by."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Attached Floor")
        county, _j = county_tax(brazos)
        services.attach_tax_to_plan(dana, plan.id, {"tax": str(county.id), "reason": "the only one"})
        assert bill(
            selectors.plan_tax_rules(plan.id, services=("electric",))
        ).tax_total == Decimal("2.00")

        with pytest.raises(errors.BizError) as refused:
            services.detach_tax_from_plan(dana, plan.id, str(county.id), {"reason": "try"})
        rules = selectors.plan_tax_rules(plan.id, services=("electric",))

    assert refused.value.br_ref == "BR-RAT-115"
    assert refused.value.message_key == "rating.plans.last_tax_not_detachable"
    assert refused.value.params["tax"] == "Local · Testland County"
    assert bill(rules).tax_total == Decimal("2.00")  # nothing left the bill


def test_tc5__detaching_a_never_attached_non_mandated_tax_refuses_as_not_attached(brazos, dana):
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Nothing To Detach")
        county, _j = county_tax(brazos)  # exists in the catalogue, not on the plan
        with pytest.raises(errors.ValidationError) as refused:
            services.detach_tax_from_plan(dana, plan.id, str(county.id))
    assert refused.value.message_key == "rating.plans.tax_not_attached"


# ── 4 · DETACHING AN EXPLICIT ATTACHMENT IS FINE — IT REVERSES NOTHING ──────
def test_tc6__attach_then_detach_round_trips_and_a_redundant_detach_changes_no_money(
    brazos, dana
):
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Round Trip")
        state, texas = state_tax(brazos)
        county, _j = county_tax(brazos)
        bind(brazos, plan, texas)

        # A plain attachment round-trips.
        detail = services.attach_tax_to_plan(
            dana, plan.id, {"tax": str(county.id), "reason": "attach"}
        )
        assert [row["tax_id"] for row in detail["tax_attachments"]] == [str(county.id)]
        detail = services.detach_tax_from_plan(dana, plan.id, str(county.id), {"reason": "detach"})
        assert detail["tax_attachments"] == []

        # A REDUNDANT attachment (tax also mandated) detaches too — and the
        # bill is unchanged either side of it, because the derived path still
        # prices the state tax at $6.25. That is why this detach is allowed:
        # it reverses nothing.
        services.attach_tax_to_plan(dana, plan.id, {"tax": str(state.id), "reason": "redundant"})
        before = bill(selectors.plan_tax_rules(plan.id, services=("electric",))).tax_total
        services.detach_tax_from_plan(dana, plan.id, str(state.id), {"reason": "tidy up"})
        after = bill(selectors.plan_tax_rules(plan.id, services=("electric",))).tax_total

    assert before == Decimal("6.25")
    assert after == Decimal("6.25")


# ── 5 · BR-RAT-094 HOLDS ON THE NEW ROW SHAPE ───────────────────────────────
def test_tc7__an_attachment_row_carrying_a_rate_override_is_refused(brazos, dana):
    """A plan chooses WHETHER a tax applies, never at WHAT rate — the refusal
    BR-RAT-094 built for jurisdiction rows covers attachment rows too."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="No Pricing Door")
        county, _j = county_tax(brazos)
        with pytest.raises(errors.ValidationError):
            services.update_plan(
                dana,
                plan.id,
                {
                    "tax_rules": [{"tax": str(county.id), "rate_override": "0.00"}],
                    "reason": "BR-RAT-094 probe",
                },
            )


def test_tc8__a_row_stating_both_sources_or_a_duplicate_attachment_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="One Source Per Row")
        county, bexar = county_tax(brazos)
        with pytest.raises(errors.ValidationError):
            services.update_plan(
                dana,
                plan.id,
                {
                    "tax_rules": [{"tax": str(county.id), "jurisdiction": str(bexar.id)}],
                    "reason": "two sources",
                },
            )
        with pytest.raises(errors.ValidationError):
            services.update_plan(
                dana,
                plan.id,
                {
                    "tax_rules": [{"tax": str(county.id)}, {"tax": str(county.id)}],
                    "reason": "twice",
                },
            )


# ── 6 · TENANT ISOLATION + BR-RAT-037 DISCIPLINE ────────────────────────────
def test_tc9__another_tenants_tax_cannot_be_attached(brazos, lonestar, dana):
    with tenant_ctx(lonestar):
        foreign, _j = county_tax(lonestar)
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Isolation")
        with pytest.raises(errors.ValidationError) as refused:
            services.attach_tax_to_plan(
                dana, plan.id, {"tax": str(foreign.id), "reason": "cross-tenant probe"}
            )
    assert refused.value.field_errors[0]["message_key"] == "rating.plans.unknown_tax"


def test_tc10__attaching_on_a_published_plan_needs_a_reason_and_bumps_the_version(brazos, dana):
    """An attached tax changes money, so it IS a BR-RAT-037 content change:
    refused without a reason, versioned with one — the same discipline every
    other plan edit takes, because attach/detach delegate to `update_plan`."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Versioned")  # make_plan publishes
        county, _j = county_tax(brazos)
        version_before = plan.version

        with pytest.raises(errors.ValidationError) as refused:
            services.attach_tax_to_plan(dana, plan.id, {"tax": str(county.id)})
        assert refused.value.message_key == "rating.reason_required"

        detail = services.attach_tax_to_plan(
            dana, plan.id, {"tax": str(county.id), "reason": "county rate adopted"}
        )
    assert detail["version"] == version_before + 1


# ── 7 · AN ATTACHMENT IS NEVER A SIDE DOOR — IT IS THE SAME FOUR GATES ──────
def test_tc11__a_per_unit_attachment_resolves_exactly_like_the_derived_path(brazos, dana):
    """BR-RAT-113 TC-11, RE-POINTED TO THE WORLD THAT NOW EXISTS (DEF-2828).

    ⚠ **THIS CASE ASSERTED AN ABSENCE AND SOMEBODY BUILT THE THING.** It read
    *"a per-unit attachment prices nothing exactly like the derived path"* and
    asserted `rules == []`, which was true while `BR-RAT-036`'s per-unit form
    was unbuilt. **CR-052 W5 task 16 built it on 2026-08-31**, and
    `selectors.plan_tax_rules` now admits a per-unit attachment through the
    SAME four gates as percent and flat-per-bill (kind · window · applicability
    · already-emitted). The CODE is right; the case stated the old world.

    What TC-11 is actually for survives the rewrite unchanged: **an attachment
    must reach the bill the way a jurisdiction binding does — the SET grows,
    the MECHANISM does not.** So the assertion is now that the attached
    surcharge resolves with its own figures intact, and per-METER — still
    unpriced anywhere — is the form that proves the door is not open to
    everything.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Per Unit Attaches Like Any Other")
        surcharge, _j = a_tax(
            brazos,
            "Conservation District",
            name="Water Conservation Surcharge",
            kind="per_unit",
            per_unit_amount=Decimal("0.25"),
            per_unit_uom="kgal",
        )
        services.attach_tax_to_plan(
            dana, plan.id, {"tax": str(surcharge.id), "reason": "BR-RAT-113 TC-11"}
        )
        rules = selectors.plan_tax_rules(plan.id, services=("electric", "water"))
    assert [row["tax_id"] for row in rules] == [str(surcharge.id)]
    only = rules[0]
    # The per-unit figures travel with the rule; nothing is approximated onto a
    # percent rate or a flat amount, which is what "the same form" means.
    assert only["per_unit_amount"] == Decimal("0.25")
    assert only["per_unit_uom"] == "kgal"
    assert only["rate"] is None
    assert only["flat_amount"] is None


def test_tc11b__a_per_meter_attachment_now_prices(brazos, dana):
    """⚠ THIS CASE WENT RED THE DAY PER-METER WAS BUILT, EXACTLY AS IT SAID IT
    WOULD (`DEF-RAT-9278`, CR-165-BRC10 round 2, 2026-10-03). It asserted the
    absence; it now asserts the attached per-meter levy reaches the bill with
    its amount. The original paragraph, kept for the record:

    The half of TC-11 that is STILL an absence, kept as one (DEF-2828).

    `BR-RAT-036` names four forms and only three are built. PER-METER is not
    priced anywhere — not through a jurisdiction binding and not through an
    attachment — and `plan_tax_rules` skips it by kind. Kept as its own case so
    that the day somebody builds it, this is the row that goes red and names
    the sentence to re-read, instead of the absence quietly ceasing to be true
    inside a case about something else (hard-won law 1, second form).
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Per Meter Stays Unpriced")
        per_meter, _j = a_tax(
            brazos,
            "Conservation District",
            name="Per Meter Levy",
            kind="per_meter",
            per_meter_amount=Decimal("1.50"),
        )
        services.attach_tax_to_plan(
            dana, plan.id, {"tax": str(per_meter.id), "reason": "BR-RAT-113 TC-11b"}
        )
        rules = selectors.plan_tax_rules(plan.id, services=("electric", "water"))
    assert [rule["tax_id"] for rule in rules] == [str(per_meter.id)]
    assert Decimal(str(rules[0]["per_meter_amount"])) == Decimal("1.50")
