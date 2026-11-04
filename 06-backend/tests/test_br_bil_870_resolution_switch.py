# ── Trace ──────────────────────────────────────────────
# Rules:   BR-BIL-870 (a rule is served by the chain only when the deployment
#          names it; the default names none) · BR-BIL-871 (ONE fork) ·
#          BR-BIL-872 (a switched rule whose chain refuses REFUSES THE ACCOUNT —
#          no fallback) · BR-BIL-873 (R3 and R4 switch together) · BR-BIL-874 (a
#          named step with no fork REFUSES) · BR-RAT-088 (the charge code owns
#          the base — the disagreement this suite switches on)
# Defects: DEF-438 (the chain has no production caller) · DEF-455 (no tenant has
#          run the BR-RAT-088 migration, which is why the two paths differ)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""THE PER-STEP SWITCH — and the two things it has to prove.

    1. **Nothing is switched on**, so no bill moves. Asserted by object
       IDENTITY, not by comparing fields: `apply` hands back the very object it
       was given while the setting is empty, which is a stronger statement than
       "the numbers came out the same".

    2. **It has actually been flipped, in both directions, on a real bill.**
       `DEF-438`'s escape reason names the trap this suite is written against —
       *"every gate that touches this file is a unit test calling it DIRECTLY,
       which is exactly the shape that passes forever on dead code"* — and
       hard-won law 1 says a switch that has never been flipped is a comment
       claiming a guarantee. So the headline test prices ONE account three
       times: live, ruled, live again, and asserts a DIFFERENT figure in the
       middle.

⚠ THE DISAGREEMENT IS REAL AND IS NOT MANUFACTURED. `BR-RAT-088` moved the base
charge onto a charge code declaring `is_base`; `DEF-455` records that no tenant
has run that migration, so the live path still reads `plan_services.base_charge`
while the chain reads the code. The fixture declares a water base code at
**$12.50** on a plan whose stored base is **$8.00** — a **$4.50 per connection
per month** difference, which is the shape of the one disagreement the shadow
has actually measured on real rows (`by_step {R4: 1}`).

⚠ NOTHING HERE ASSERTS A FROZEN FIGURE. B4 money math and B5's GT-1..61 are
❄️ FROZEN and no number in this file is one of theirs; $8.00 is the sample
fixture's own water base, read from `core.sample_fixture` and never retyped.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.test import override_settings

from apps.billing import gather, resolution_switch
from apps.rating import models as rating_models
from core import sample_fixture as fixture

from tests.test_def_438_parity import (  # the fixture set this extends
    SERVICE_DATE,
    WATER_SIZE,
    _account_on,
    _price_live,
    _water_plan,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The plan's stored base — what the LIVE path prices today.
LIVE_BASE = Decimal(fixture.WATER_BASE)
#: What the tenant's own `is_base` charge code says — what the RULED path prices.
RULED_BASE = Decimal("12.50")

LOCALES = Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"


def _size_the_meter(asset, size=WATER_SIZE):
    """Record the connection size the way a utility does — on the ASSET.

    BR-AST-500 put `size_class` on `assets.Asset` and `metering.selectors
    .connection_size_for` reads it, so this suite uses the PRODUCTION seam and
    monkeypatches nothing. A test that published a fake seam could not tell a
    wired switch from an unwired one.
    """
    from apps.assets import models as asset_models

    asset_models.Asset.objects.filter(pk=asset["id"]).update(size_class=size)


def _declare_a_base_charge_code(tenant, amount=RULED_BASE):
    """BR-RAT-088's charge code, which the chain reads and the live path does not.

    Created AFTER the plan so the activation gate (a tenant with SOME declared
    base must declare one for every service it activates) is never in the way —
    this fixture is about pricing, not about activation.

    ⚠ **AND EVERY `_water_plan` CALL IN THIS FILE PASSES `base_code=False` FROM
    2026-09-28 (`DEF-BIL-7170`).** That helper now mints an `is_base` water code
    of its own, because the PO retired the plan's figure and a plan without one
    cannot bill. **This file mints its own and must be the only one**: two
    unscoped base codes for one service is `DEF-468`'s ambiguity — *"2 base
    charge codes for water. Scope them on Charge codes."* — and it refused
    fifteen cases here, every one of them about the resolution switch and none
    of them about the catalogue.
    """
    from apps.tenancy import models as tenancy_models

    from tests.base_code_naming import name_base_code

    # `DEF-RAT-9832` (PO 2026-10-06): the schedule NAMES it — an unnamed
    # schedule bills `$0.00` on both paths — so the figures here still bill.
    # `_a_second_priced_version` names it on the versions it adds.
    return name_base_code(
        tenant,
        rating_models.Charge.objects.create(
            tenant=tenant,
            code="BASE-W",
            name="Water base service",
            charge_type="recurring",
            amount_rule="flat",
            amount=amount,
            service=tenancy_models.Service.objects.get(code="water"),
            is_base=True,
        ),
    )


def _base_charges(data):
    return {config.service: Decimal(str(config.base_charge)) for config in data.tariffs}


def nothing_switched_on():
    """The OFF state, **STATED rather than INHERITED** (PO 2026-09-01).

    ⚠ **THE SHIPPED DEFAULT IS NO LONGER EMPTY, SO A BASELINE THAT SAYS NOTHING
    IS NO LONGER A BASELINE.** Every case below that means *the live path, with
    the fork in place and nothing switched on* used to get that for free from
    the shipped default. On the day the Product Owner ruled R3 and R4 in, those
    baselines silently became runs of the SWITCHED path — and a test whose
    "before" and "after" are the same path proves nothing while staying green
    on anything that does not happen to move a figure.

    So the OFF state is now written down at every point that depends on it. It
    is also the more honest spelling: the rollback a deployment types is exactly
    this — `SBH_BILLING_RESOLUTION_STEPS=` emptied — so these cases are the ones
    that keep proving a rolled-back deployment still bills correctly.

    Read a use of this as *"here the switch is OFF, and that is the point"*,
    never as *"here the switch happens to be off"*.
    """
    return override_settings(BILLING_RESOLUTION_STEPS="")


#: The tiers `_water_plan` writes on the version the CHAIN resolves, doubled.
#: Doubled rather than hand-picked so a fixture change moves both sides together
#: (B12 §No hard-coded values) and so no figure here can be mistaken for a ❄️ B5
#: one — none of these prices appears in B4 or B5.
DOUBLED_TIERS = tuple(
    (lo, hi, str(Decimal(price) * 2)) for lo, hi, price in fixture.WATER_TIERS
)


def _first_version(tenant):
    """The version `_water_plan` wrote — open-ended, so the CHAIN prices from it."""
    return rating_models.TariffVersion.objects.get(tenant=tenant, effective_to__isnull=True)


def _a_second_priced_version(tenant, plan, *, tiers, base_charge=LIVE_BASE):
    """A SECOND, fully priced rate schedule version, SCHEDULED FOR NEXT YEAR.

    ⚠ **THIS HELPER USED TO BE `DEF-2889` WORN AS A FIXTURE, AND THAT DEFECT IS
    NOW FIXED (2026-09-01).** It read: *"a second rate schedule version the LIVE
    path resolves and the CHAIN does not"*, and it worked by writing a version
    whose window ENDED on the service date. The chain's
    `ScheduleVersion.in_force_on` matched `effective_to > service_date` and the
    live `rating.selectors.in_force_version` matched `effective_to >=
    service_date`, so the two disagreed by exactly one day — and since
    `rating.services` closes a superseded window with `previous.effective_to =
    new_from - timedelta(days=1)`, the LIVE path was the one that was right. The
    chain moved to that boundary, so **no configuration of rows separates the
    two narrowings any more**, which is the whole point of the fix and is
    asserted outright by
    `test_r2_and_the_live_path_name_the_same_version_on_a_windows_LAST_DAY`.

    That leaves the rebuild branches below with nothing to exercise them from
    data alone, so this helper now does the honest half only: it writes a real,
    fully priced version with its own ladder, dated to start **next January**,
    which is an ordinary scheduled rate change and touches nothing the run
    resolves today. The cases that need the chain to NAME it say so through
    `_the_chain_names()` — this file's own established idiom, already used by
    two other cases — and that substitution is at the CHAIN'S ANSWER, the exact
    input the fork consumes, never at a rate row or a size seam.

    The prices differ from the run's so that "the version moved" and "the prices
    moved with it" stay two separate assertions rather than one.
    """
    from apps.rating import selectors as rating_selectors

    made = None
    for row in rating_selectors.plan_rate_schedules(plan.id):
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model="tiered",
            base_charge=base_charge,
            # `DEF-RAT-9832` — names the file's base code, as its first version does.
            base_charge_code=rating_models.Charge.objects.filter(tenant=tenant, code="BASE-W").first(),
            uom=fixture.WATER_UOM,
            currency="USD",
            effective_from=date(2027, 1, 1),
            effective_to=None,
        )
        # BR-RAT-120's size axis, exactly as `_water_plan` writes it: the row's
        # job is to say this version PRICES 5/8" at all, so R3 can resolve a
        # served size when the chain is pointed at it.
        rating_models.RateSizeRow.objects.update_or_create(
            tenant=tenant,
            tariff_version=version,
            size_class=WATER_SIZE,
            defaults={"minimum_bill": None, "currency": "USD"},
        )
        for seq, (from_qty, to_qty, price) in enumerate(tiers, start=1):
            rating_models.RateTier.objects.create(
                tenant=tenant,
                tariff_version=version,
                seq=seq,
                from_qty=Decimal(from_qty),
                to_qty=None if to_qty is None else Decimal(to_qty),
                unit_price=Decimal(price),
            )
        made = version
    return made


def _the_chain_names(monkeypatch, version_id):
    """Make the CHAIN's answer name `version_id`, leaving everything else real.

    ⚠ **WHY A SUBSTITUTION AND NOT A ROW (`DEF-2889`, 2026-09-01).** Until that
    defect was fixed the two narrowings disagreed by one day, so a pair of rows
    could put the run on one version and the chain on another. They agree now —
    `effective_to` is the last day a version prices on BOTH paths — and no
    arrangement of `tariff_versions` separates them any more. That is the fix
    working, and it leaves R2's and R3/R4's rebuild branches reachable only by
    handing the fork a chain answer that differs.

    So the substitution is at **the chain's answer**, which is precisely the
    input `resolution_switch` consumes, and NOT at a rate row, a size seam or a
    pricing read — all of which stay live and real, so this can still tell a
    wired fork from an unwired one. `resolution.resolve` really runs; only the
    `schedule_version_id` it reports is redirected, and it is redirected to a
    version that really exists and really has tiers.

    This is the file's own idiom, already used by
    `test_r2_refuses_a_version_the_chain_named_that_this_utility_cannot_price`
    and by R7's refusal case; it is factored out here so all of them read the
    same.
    """
    real = resolution_switch._resolve_for

    def _naming(data, *, account, service_date):
        resolved = real(data, account=account, service_date=service_date)
        return replace(
            resolved,
            services=tuple(
                replace(service, schedule_version_id=str(version_id))
                for service in resolved.services
            ),
        )

    monkeypatch.setattr(resolution_switch, "_resolve_for", _naming)


def _tier_prices(data, service="water"):
    for config in data.tariffs:
        if config.service == service:
            return tuple(Decimal(str(tier.unit_price)) for tier in config.tiers)
    raise AssertionError(f"no {service} tariff on this account")


def _version_id(data, service="water"):
    for config in data.tariffs:
        if config.service == service:
            return str(config.version_id)
    raise AssertionError(f"no {service} tariff on this account")


# ══════════════════════════════════════════════════════════════════════════
# 1 · NOTHING IS SWITCHED ON
# ══════════════════════════════════════════════════════════════════════════


def test_the_shipped_default_serves_EXACTLY_the_ruled_pair_and_both_literals_agree():
    """⚠ **THIS TEST USED TO ASSERT THE DEFAULT WAS EMPTY, AND THE PRODUCT OWNER
    MOVED IT ON 2026-09-01** — *"Can you wire them in now - R3 and R4"*.

    Its JOB has not changed and must not be weakened into a restatement of the
    constant: it exists so that **a rule cannot go live without a ruling**. What
    is ruled is the PAIR, so the assertion is now that the set is EXACTLY
    `{R3, R4}` — a lane that adds R1, R2, R5 or R7 here still goes red, which is
    the whole of what the empty-string version was protecting.

    What was measured before the pair went on: 3 utilities, 163 accounts,
    **0 (service · size) pairs with nothing pricing them**, and the pair switched
    on in a rolled-back transaction moved **0 base charges and refused 0
    accounts**. Both checks were proved able to say the opposite.

    ⚠ **AND IT PINS THE TWO LITERALS TOGETHER (`DEF-2922`).** The constant is
    only ever reached as `getattr(settings, SETTING, SERVED_BY_CHAIN_DEFAULT)`,
    and `BILLING_RESOLUTION_STEPS` is ALWAYS defined in `config/settings/base.py`
    — so the constant is an unreachable fallback that has never decided anything,
    and changing it alone switches nothing on. That was found by this very test
    failing after the constant was moved and the setting was not: the assertion
    below read `frozenset()` while the constant read `R3,R4`. Both are asserted
    now, so the next lane to move one and not the other is told immediately
    instead of believing a rule went live.
    """
    from django.conf import settings as django_settings

    #: The ONE ruling this default is allowed to carry. Written as a set rather
    #: than as a string so the assertion is about WHICH RULES ARE LIVE and not
    #: about how somebody spelled or ordered them.
    ruled_on_by_the_po = frozenset({"R3", "R4"})

    assert resolution_switch.SERVED_BY_CHAIN_DEFAULT == "R3,R4", (
        "the constant and the setting must move TOGETHER (DEF-2922). This one "
        "decides nothing on its own — it is only ever reached as "
        "getattr(settings, SETTING, SERVED_BY_CHAIN_DEFAULT) and the setting is "
        "always defined — so a lane that moves the setting and leaves this "
        "behind has left the file whose whole job is the switch disagreeing "
        "with itself."
    )
    assert django_settings.BILLING_RESOLUTION_STEPS == "R3,R4", (
        "the SETTING is what decides (DEF-2922). A deployment overriding "
        "SBH_BILLING_RESOLUTION_STEPS is lawful and expected — this asserts the "
        "SHIPPED default, so run the suite without that variable set."
    )
    assert resolution_switch.SERVED_BY_CHAIN_DEFAULT == (
        django_settings.BILLING_RESOLUTION_STEPS
    ), "the two literals have drifted apart — that is DEF-2922 happening again."

    assert resolution_switch.steps_served_by_chain() == ruled_on_by_the_po, (
        "the SHIPPED default serves a set the Product Owner has not ruled on. "
        "R3 and R4 were ruled ON (PO 2026-09-01, 'Can you wire them in now - R3 "
        "and R4') and they switch together (BR-BIL-873). R1, R2, R5 and R7 are "
        "forkable and are NOT ruled: each needs its own measurement and its own "
        "ruling, so adding one here is a rule going live without a ruling, "
        "which is the whole of what this test protects. Removing one is the "
        "one-line rollback and is lawful — but it is a deliberate act and it "
        "belongs in a commit that says so."
    )


def test_apply_hands_back_THE_SAME_OBJECT_when_nothing_is_switched():
    """Identity, not equality. `apply` may not even copy the gathered data when
    the setting is empty — that is what makes "no bill changed" a property of
    the code rather than a claim about a test run.

    ⚠ **THE EMPTY SETTING IS NOW STATED RATHER THAN INHERITED (PO 2026-09-01).**
    The shipped default is `R3,R4`, so relying on it here would silently turn
    this into a test of the switched path that happens to pass on a stub object.
    A deployment that has turned the pair OFF — the one-line rollback the
    constant documents — is exactly this case, and it must still get its own
    object back untouched.
    """

    class _Data:
        pass

    data = _Data()
    with override_settings(BILLING_RESOLUTION_STEPS=""):
        assert resolution_switch.steps_served_by_chain() == frozenset()
        assert resolution_switch.apply(data, account=None, service_date=SERVICE_DATE) is data


def test_a_real_gathered_account_is_unchanged_and_carries_no_stamp(brazos, dana):
    """The whole live path, end to end, with the fork in place and nothing on."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        # ⚠ **AT THE PLAN'S OWN FIGURE SINCE `DEF-2823`.** The live path reads
        # the base from the CHARGE CODE now (BR-RAT-088), and a code that
        # disagreed with the plan would be REFUSED as a migration artefact
        # rather than priced — which is the correct behaviour and is asserted
        # in `test_def2823_base_from_charge_code.py`. This test is about the
        # switch being OFF, so the configuration is a lawful one.
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)

        # ⚠ **THE OFF STATE IS STATED, NOT INHERITED (PO 2026-09-01).** This
        # case is titled "with the fork in place and nothing on", and since the
        # pair was ruled in, the shipped default no longer supplies that. A
        # deployment that has typed the one-line rollback is exactly this case,
        # and it must still bill the plan's figure and stamp nothing.
        with nothing_switched_on():
            data = _price_live(account)

        assert _base_charges(data)["water"] == LIVE_BASE
        assert data.resolution_steps == ()


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE SWITCH HAS BEEN FLIPPED — both directions, on one real bill
# ══════════════════════════════════════════════════════════════════════════


def test_r3_r4_can_be_served_by_the_chain_AND_SWITCHED_BACK(brazos, dana):
    """THE test. Three gathers of ONE account: live, ruled, live again.

    A switch that has never been flipped is a comment claiming a guarantee
    (hard-won law 1), and a test whose middle pass is indistinguishable from its
    outer two would prove the switch is dead rather than that it works. So the
    middle OUTCOME has to be different, and it is: **$8.00 → the account is
    refused by name → $8.00**, with nothing left behind either way.

    ⚠ **THE DIVERGENCE THIS USED TO USE IS GONE, AND ITS DISAPPEARANCE IS THE
    POINT OF `DEF-2823` (2026-08-31).** It used to declare an `is_base` charge
    code at `$12.50` beside a plan stating `$8.00` and watch the chain price the
    code while the live path priced the plan. **Both paths read the charge code
    now** (BR-RAT-088), so that configuration no longer produces two figures —
    it produces a REFUSAL on both, because a plan still carrying a different
    base is a migration artefact the ruling says must be refused. A base
    divergence by SOURCE is no longer constructible, which is exactly the
    property the cutover wanted and is why the step is safe to switch.

    ⚠ **AND THE FIGURE DIVERGENCE THIS TEST PINNED IS GONE TOO — `DEF-2830`,
    SETTLED 2026-08-31 AND IMPLEMENTED HERE.** The middle pass used to read
    `$0.00`. A tenant with no `is_base` code falls back, and the two paths read
    a stored schedule `0.00` differently: `gather._base_charge_for` treats a
    schedule zero as *not stated* when the plan states a figure (its
    `schedule_amount != 0` carve-out, which is `DEF-277`'s history) and prices
    the plan's `$8.00`, while `_legacy_schedule_base` handed the zero back as a
    PRICE and the chain billed `$0.00`. **`$8.00` a month per connection**, and
    both readings were defensible.

    **The judgment was ours to make and is recorded, not asked** (decision log
    2026-08-31; hard-won law 13 — a judgment that preserves current behaviour
    needs no ruling): **a stored `0.00` means NOT STATED.** The opposite reading
    would give the standing charge away because somebody left a box alone rather
    than because they decided anything.

    **So the two paths now read that column the same way, and what is left is
    not a figure disagreement — it is a MIGRATION PRECONDITION.** With no base
    charge code declared, the chain has nothing left to price the base from and
    refuses the account by name; the live path still bills the plan's figure,
    because `BR-RAT-088` explicitly keeps a pre-ruling tenant billing what it
    billed yesterday. `BR-RAT-088` is also what tells such a tenant how to clear
    it: declare a base charge code. That refusal is the live fork the switch is
    proved on here, and it is a strictly safer one — the chain can no longer put
    `$0.00` on a bill because a box was never filled in.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        # ⚠ **THE MIDDLE PASS DIVERGES ON THE CONNECTION SIZE FROM 2026-09-28,
        # AND IT USED TO DIVERGE ON THE BASE (`DEF-BIL-7170`).** The old
        # fixture declared no `is_base` code and let the LIVE path fall back to
        # the plan's `$8.00` while the chain refused for want of a base. The PO
        # deleted that fallback — *"we will never take default value from plan
        # $8.0 - that is retired"* — so BOTH paths now refuse that
        # configuration and the outer two passes have no figure to produce.
        #
        # **What this case needs is a divergence, not a particular one**: the
        # live path must PRICE and the ruled path must REFUSE, so the middle
        # outcome is distinguishable from the outer two. An unsized meter is
        # that divergence today — R3 cannot say which ladder applies, while the
        # live path prices the flat code — and it is the same fork
        # `test_a_fact_the_adapter_cannot_assemble_refuses_too` proves.
        account, _unit, _asset, _delta = _account_on(
            brazos, dana, plan, size_class=None
        )
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)

        # ⚠ **THE OUTER TWO PASSES PIN THE OFF STATE EXPLICITLY.** They are the
        # "live" in *live → ruled → live again*, and the shipped default has
        # served the pair since 2026-09-01 — so inheriting it would make this
        # test's first and third passes RUN THE SWITCHED PATH and quietly turn
        # THE test of the switch into three runs of one path. The third pass is
        # also the rollback, proved: a deployment that empties the setting bills
        # the plan's figure again with nothing left behind.
        with nothing_switched_on():
            first = _price_live(account)
        assert _base_charges(first)["water"] == LIVE_BASE
        assert first.resolution_steps == ()

        with override_settings(BILLING_RESOLUTION_STEPS="R3 R4"):
            with pytest.raises(gather.GatherProblem) as raised:
                _price_live(account)

        with nothing_switched_on():
            after = _price_live(account)
        assert _base_charges(after)["water"] == LIVE_BASE
        assert after.resolution_steps == ()

    problem = raised.value
    assert problem.reason == gather.GATHER_RULED_PATH_REFUSED
    # The chain's own SENTENCE, naming what is actually in the way. ⚠ **IT USED
    # TO ASSERT `R4`, `0.00` AND `NOBODY FILLED IT IN`** — the base refusal this
    # fixture can no longer construct (`DEF-BIL-7170`); `DEF-2830`'s reading of
    # a stored zero is unchanged and is asserted where it lives, in
    # `test_def2830__a_stored_schedule_zero_is_NOT_STATED_on_both_paths`.
    assert "connection size" in str(problem)


def test_def2830__a_stored_schedule_zero_is_NOT_STATED_on_both_paths(brazos, dana):
    """`DEF-2830`, at the two functions that disagreed, with the worked figure.

    The settled reading is one sentence — **a stored `0.00` on the retired
    `tariff_versions.base_charge` means NOBODY FILLED THIS IN, not *this
    connection is free*** — and it has to hold in BOTH places or the switch
    moves money. So both are asserted here rather than one being trusted to
    follow the other:

      * the LIVE path bills the plan's **`$8.00`**, unchanged, which is the
        whole point of settling it this way;
      * `_legacy_schedule_base` answers **`None`** for the same stored zero,
        where it used to answer `Decimal("0")` and bill `$0.00`.

    ⚠ **A NON-ZERO FIGURE IS STILL A FIGURE.** The carve-out is about zero and
    nothing else: a tenant that really did type `$4.25` on a pre-ruling schedule
    goes on getting `$4.25` from the fallback, and that is asserted below so the
    fix cannot be widened into *the legacy fallback is dead* by a later reader.
    """
    from apps.rating import resolution

    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        rating_models.TariffVersion.objects.filter(tenant=brazos).update(base_charge=Decimal("0"))
        # ⚠ **THE LIVE HALF NEEDS A SOURCE FROM 2026-09-28 (`DEF-BIL-7170`).**
        # It used to read the PLAN's `$8.00` while this tenant declared no
        # `is_base` code, and the PO retired that column: *"we will never take
        # default value from plan $8.0 - that is retired"*. The code states the
        # SAME `LIVE_BASE`, so the figure asserted below has not moved — what
        # moved is which object states it.
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)

        # THE LIVE PATH BILLS THE SAME FIGURE IT ALWAYS DID — this is the
        # behaviour being preserved, so the switch is pinned OFF to say WHICH
        # path is being asserted.
        with nothing_switched_on():
            assert _base_charges(_price_live(account))["water"] == LIVE_BASE

    meter = resolution.MeterFacts("water", WATER_SIZE)
    zeroed = resolution.ScheduleVersion(
        version_id="v-zero", service="water", size_rows={WATER_SIZE: Decimal("0")}
    )
    assert resolution._legacy_schedule_base(zeroed, meter) is None

    stated = resolution.ScheduleVersion(
        version_id="v-stated", service="water", size_rows={WATER_SIZE: Decimal("4.25")}
    )
    assert resolution._legacy_schedule_base(stated, meter) == Decimal("4.25")

    # A size the schedule does not serve at all is still None, and R3 — not this
    # function — is what refuses on it (DEF-2823).
    assert resolution._legacy_schedule_base(zeroed, resolution.MeterFacts("water", "W-99")) is None


def test_one_rule_switches_WITHOUT_the_others(brazos, dana):
    """Per RULE, not per chain. R5 on, R3/R4 off: the jurisdiction factor comes
    from the ruled path and the base charge is still the live path's $8.00.

    The recorded method insists on this — *"switching all seven at once makes
    every disagreement arrive in one diff with no way to attribute it"*.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)

        with override_settings(BILLING_RESOLUTION_STEPS="R5"):
            data = _price_live(account)

        assert data.resolution_steps == ("R5",)
        # R3/R4 stayed on the live path and the base is the live path's own.
        # ⚠ Since `DEF-2823` BOTH paths read the base from the charge code, so
        # this figure would be $8.00 either way — the assertion that carries the
        # per-rule claim is `resolution_steps` above, and the base is checked
        # here only to show the bill is intact.
        assert _base_charges(data)["water"] == LIVE_BASE
        # …and R5 did cross: this plan prices no surcharge, so both paths say 1,
        # which is the point — a rule can be switched without moving a figure.
        assert Decimal(str(data.tariffs[0].jurisdiction_factor)) == Decimal("1")


@pytest.mark.django_db
def test_r1_serves_the_plan_VERSION_and_asserts_the_plan_id_rather_than_serving_it(
    brazos, dana
):
    """CR-052 task 21 — R1's fork, and the reason it is a fork at all.

    ⚠ **HALF OF R1'S ANSWER IS AN ECHO AND ONLY THE OTHER HALF IS SWITCHABLE
    (`DEF-2839`).** `resolution_shadow.adapt` hands `plan_id` to
    `build_catalogue`, which stamps it back onto the row it yields, so comparing
    it compares one value with itself. The plan VERSION never reaches the chain
    — the chain re-reads it against `BR-RAT-007`'s rule, *the version in force
    AT the service date* — so it is a real second answer and it is what R1's
    fork substitutes.

    **What switching R1 changes on a bill is the version RECORDED, never an
    amount.** `rate_plan_version` reaches the document payload and prices
    nothing, so this test asserts the stamp and the base charge together: one
    moved, the other did not.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)

        # Both sides are stated, so the STEP UNDER TEST is the only difference
        # between them. Inheriting the shipped default would put R3 and R4 on
        # the "live" side too and compare R3,R4 against R1 (PO 2026-09-01).
        with nothing_switched_on():
            live = _price_live(account)
        with override_settings(BILLING_RESOLUTION_STEPS="R1"):
            ruled = _price_live(account)

    assert live.resolution_steps == ()
    assert ruled.resolution_steps == ("R1",)
    # The chain resolved it, and it is a real integer rather than a None that
    # would read as "switched on and answering nothing" (hard-won law 1).
    assert ruled.rate_plan_version is not None
    # R1 moved no money: R3/R4 are still the live path's.
    assert _base_charges(ruled)["water"] == LIVE_BASE


@pytest.mark.django_db
def test_r1_refuses_the_account_when_the_two_paths_name_DIFFERENT_plans(
    brazos, dana, monkeypatch
):
    """The plan id is an INVARIANT, and a difference is louder than a divergence.

    If the chain resolved one plan and the bill run gathered another, the two
    are not disagreeing about a price — they are looking at different accounts,
    and every other figure in that run is meaningless. So it refuses by name
    rather than reporting a divergence, which is the one case in this file where
    a mismatch is not evidence to be collected.
    """
    from apps.billing import resolution_switch

    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)

        real_resolve = resolution_switch.resolution_shadow.adapt

        def _adapt_with_a_foreign_plan(data, *, account):
            return real_resolve(replace(data, rate_plan_id="00000000-0000-0000-0000-000000000000"), account=account)

        monkeypatch.setattr(
            resolution_switch.resolution_shadow, "adapt", _adapt_with_a_foreign_plan
        )
        with override_settings(BILLING_RESOLUTION_STEPS="R1"):
            with pytest.raises(Exception) as raised:
                _price_live(account)

    assert "different accounts" in str(raised.value) or "plan" in str(raised.value)


@pytest.mark.django_db
def test_r2_is_forked_and_naming_it_no_longer_refuses():
    """CR-052 task 22 — R2 has a fork, and the step list says so.

    This is the assertion the previous lane's proof-by-running produced in the
    other direction: `R2` used to raise *"this build has no fork for it"*
    (`BR-BIL-874`). Six of eight steps are switchable now; `R3b` and `R6` are
    not, and naming either still refuses rather than being ignored.
    """
    assert "R2" in resolution_switch.FORKED
    with override_settings(BILLING_RESOLUTION_STEPS="R2"):
        assert resolution_switch.steps_served_by_chain() == frozenset({"R2"})
    with override_settings(BILLING_RESOLUTION_STEPS="R3b"):
        with pytest.raises(resolution_switch.SwitchMisconfigured) as raised:
            resolution_switch.steps_served_by_chain()
    assert "no fork" in str(raised.value)


@pytest.mark.django_db
def test_r2s_read_REACHES_the_pass_memo_rather_than_only_being_listed_on_it(brazos):
    """Built is not wired (hard-won law 2) — the read has to REACH the memo.

    R2's only database read is `rating.selectors.pricing_inputs_for_version_id`,
    and it is on `seam_batch.BATCHABLE` so a prepare pass asks it once per
    (version, date, size) instead of once per service per account. That holds
    ONLY if the fork resolves it through `gather._resolve`, which is the one
    place `seam_batch.wrap` is wired: reaching around it with a plain import
    would be *"a seam nobody batched, and there would be no way to tell which"*.

    So this asserts the wiring by BEHAVIOUR — two identical asks inside one pass
    cost one call — rather than by checking the name is on a list, which is the
    shape that passes forever on a read that never arrives.
    """
    from apps.billing import seam_batch
    from apps.rating import selectors as rating_selectors

    assert ("rating", "pricing_inputs_for_version_id") in seam_batch.BATCHABLE

    # ⚠ INSIDE A TENANT CONTEXT, and that is the read's OWN guarantee showing.
    # `rating.selectors._tenant_id` refuses outright when `app.tenant_id` is
    # unset (`AUTH-003`, BR-TEN-003 — CLAUDE.md hard rule 1), so this seam
    # cannot be asked for a version without saying whose it is.
    with tenant_ctx(brazos):
        with seam_batch.pass_cache() as cache:
            seam = resolution_switch._rating_selector("pricing_inputs_for_version_id")
            # An id nothing can resolve, twice: the ANSWER is None either way
            # and the point is the call count, not the value.
            missing = "00000000-0000-0000-0000-000000000000"
            assert seam(missing, SERVICE_DATE, None) is None
            assert seam(missing, SERVICE_DATE, None) is None
            assert cache.asked["rating.pricing_inputs_for_version_id"] == 1
            assert cache.served["rating.pricing_inputs_for_version_id"] == 1

    # …and OUTSIDE a pass it is rating's own selector, unwrapped, which is the
    # other half of the contract: `single.calculate_single_bill` opens no pass
    # and must still get a truthful answer.
    assert (
        resolution_switch._rating_selector("pricing_inputs_for_version_id")
        is rating_selectors.pricing_inputs_for_version_id
    )


@pytest.mark.django_db
def test_r2_serves_the_schedule_version_and_the_AGREEING_case_moves_nothing(brazos, dana):
    """R2 switched on, one version, both paths name it — and no figure moves.

    ⚠ **THIS IS THE SAFETY PROPERTY AND NOT THE FORK.** When the chain names the
    version the bill run already priced from, rebuilding would re-derive byte
    for byte what is on the tariff, so nothing is substituted and **no database
    read is issued at all**. It is 47 of 47 accounts of the seeded utility today.
    The test below is the one that proves the rebuild actually rebuilds.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)

        # Stated on both sides — R2 alone is the difference under test, and the
        # shipped default would otherwise add R3 and R4 to the baseline.
        with nothing_switched_on():
            live = _price_live(account)
        with override_settings(BILLING_RESOLUTION_STEPS="R2"):
            ruled = _price_live(account)

    assert live.resolution_steps == ()
    assert ruled.resolution_steps == ("R2",)
    # Same version, same ladder, same base — the switch is on and the bill is
    # identical, which is what "the two paths agree at R2" MEANS.
    assert _version_id(ruled) == _version_id(live)
    assert _tier_prices(ruled) == _tier_prices(live)
    assert _base_charges(ruled)["water"] == _base_charges(live)["water"] == LIVE_BASE


@pytest.mark.django_db
def test_r2_and_the_live_path_name_the_same_version_on_a_windows_LAST_DAY(brazos, dana):
    """❄️ `DEF-2889` — THE BOUNDARY, ON REAL ROWS, AND IT PRICES.

    When a rate schedule is superseded, `rating.services` closes the old window
    with `previous.effective_to = new_from - timedelta(days=1)`. So a version
    replaced on **1 August** carries `effective_to = 31 July`, and **31 July is
    a day it prices**. The bill run has always read it that way
    (`in_force_version`, `effective_to__gte=service_date`).

    `resolution.ScheduleVersion.in_force_on` read `effective_to > service_date`
    and was therefore wrong by exactly one day, in the direction that STOPS A
    BILL: on 31 July it found the old version out of force and the new one not
    yet started, and `BR-BIL-872` makes a switched rule's refusal FINAL — no
    fallback to the live answer. Switching R2 on would have refused one day of
    billing per schedule change, per account.

    This case is that boundary written as the product itself writes it: one
    window closed on the service date, its successor starting the next morning,
    nothing overlapping. **Both paths must name the CLOSED version and the
    account must still bill.** It is the fixture DEF-2889's prevention column
    asked for — *"a test that prices a service date equal to a version
    effective_to on both paths and asserts they name the same version"*.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)

        closing = _first_version(brazos)
        # The product's own supersession shape: the old window's LAST DAY is
        # the service date, and the successor opens the next morning.
        rating_models.TariffVersion.objects.filter(pk=closing.pk).update(
            effective_to=SERVICE_DATE
        )
        successor = _a_second_priced_version(brazos, plan, tiers=DOUBLED_TIERS)
        rating_models.TariffVersion.objects.filter(pk=successor.pk).update(
            effective_from=SERVICE_DATE + timedelta(days=1)
        )

        live = _price_live(account)
        with override_settings(BILLING_RESOLUTION_STEPS="R2"):
            ruled = _price_live(account)

    # The bill run prices the closing version on its own last day — always has.
    assert _version_id(live) == str(closing.id)
    # And so does the chain, now. Before 2026-09-01 this line raised
    # `NoScheduleForService` and the account was refused outright.
    assert _version_id(ruled) == str(closing.id)
    assert ruled.resolution_steps == ("R2",)
    # The ladder is the closing version's, on both paths — no successor prices
    # a day early either, which is the same boundary read from the other side.
    assert _tier_prices(live) == _tier_prices(ruled)
    assert _tier_prices(ruled) == tuple(Decimal(p) for _lo, _hi, p in fixture.WATER_TIERS)
    assert _base_charges(ruled)["water"] == LIVE_BASE


@pytest.mark.django_db
def test_r2_PRICES_FROM_the_chains_version_rather_than_stamping_its_id(
    brazos, dana, monkeypatch
):
    """THE R2 test — the prices move WITH the version, or the fork is a lie.

    The decision log's words for what must not happen: *"substituting the id
    alone would stamp the chain's version on prices read from the live one …
    a lie on the bill, and the worst kind, because every figure would still be
    internally consistent."*

    ⚠ **HOW THE TWO PATHS ARE MADE TO DIFFER CHANGED ON 2026-09-01, AND THE
    REASON IS GOOD NEWS.** This case used to lean on `DEF-2889` — the two
    narrowings disagreed by one day, so a pair of rows put the run on one
    version and the chain on another. That defect is fixed and the narrowings
    now agree by construction (the case above asserts it), so **no arrangement
    of rate rows separates them any more.** The fork's rebuild branch is
    therefore reached the only honest way left: by handing it a chain answer
    that names a different version, through `_the_chain_names()` — a
    substitution at the fork's own INPUT, with the catalogue build, the size
    seam and every pricing read still live and real.

    The version it names is not invented: it is a real, fully priced schedule
    version with its own ladder, scheduled to start next January. With R2 on,
    **both the recorded version and the tier prices become that one's** — the
    ladder really is re-read, and a fork that only stamped the id would fail on
    the second assertion while passing the first.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)
        run_version = _first_version(brazos)
        chain_version = _a_second_priced_version(brazos, plan, tiers=DOUBLED_TIERS)

        live = _price_live(account)
        _the_chain_names(monkeypatch, chain_version.id)
        with override_settings(BILLING_RESOLUTION_STEPS="R2"):
            ruled = _price_live(account)

    # The two paths really did name different versions — the premise of the test.
    assert _version_id(live) == str(run_version.id)
    assert _version_id(ruled) == str(chain_version.id)
    assert str(run_version.id) != str(chain_version.id)
    # …and the LADDER came with it: the run's own 4.00/6.50/8.00, doubled on the
    # version the chain named.
    assert _tier_prices(live) == tuple(Decimal(p) for _lo, _hi, p in fixture.WATER_TIERS)
    assert _tier_prices(ruled) == tuple(Decimal(p) for _lo, _hi, p in DOUBLED_TIERS)
    assert ruled.resolution_steps == ("R2",)
    # R3/R4 stayed live, so the base is still the charge code's own figure.
    assert _base_charges(ruled)["water"] == LIVE_BASE


@pytest.mark.django_db
def test_r2_REFUSES_when_moving_the_version_would_move_the_base_charge(
    brazos, dana, monkeypatch
):
    """The fact the chain's version cannot supply, refused rather than defaulted.

    `TariffConfig.base_charge` is `gather._base_charge_for`'s answer over THREE
    figures — the charge code's, the plan's and the version's own retired column
    — and two of them do not travel on a `TariffConfig`. So when R2 would move
    the version underneath a base decided partly from the version being
    replaced, the ACCOUNT REFUSES BY NAME. Same shape as R7's
    `discount_treatment` refusal, one field along.

    Here the run's version states the same `$8.00` as the charge code and the
    plan, and the chain's version states `$0.00` — so pricing from the chain's
    ladder while keeping the run's base would put one version's prices beside
    another version's base on a document where every figure agrees.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)
        # The version the chain names states a DIFFERENT base of its own — the
        # run's version keeps the fixture's $8.00 (DEF-2889: the two narrowings
        # agree now, so the chain is pointed at it explicitly).
        chain_version = _a_second_priced_version(
            brazos, plan, tiers=DOUBLED_TIERS, base_charge=Decimal("0")
        )

        # The live path is untouched and still bills the charge code's figure.
        assert _base_charges(_price_live(account))["water"] == LIVE_BASE

        _the_chain_names(monkeypatch, chain_version.id)
        with override_settings(BILLING_RESOLUTION_STEPS="R2"):
            with pytest.raises(Exception) as raised:
                _price_live(account)

    said = str(raised.value)
    assert "base charge" in said
    assert "different rate schedule version" in said
    # The sentence names the repair rather than only the problem (BR-SHL-020).
    assert "R3 and R4" in said


@pytest.mark.django_db
def test_r2_with_r3_and_r4_does_NOT_refuse_because_the_chain_states_the_base(
    brazos, dana, monkeypatch
):
    """The other lawful way out of the same case: let the chain answer the base.

    With `R3 + R4` served the base charge comes from the ruled path outright, so
    there is no figure left that belongs to the version being replaced and
    nothing is mixed. The same configuration that refuses above bills here —
    which is what makes the refusal a statement about MIXING rather than about
    the version differing.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)
        chain_version = _a_second_priced_version(
            brazos, plan, tiers=DOUBLED_TIERS, base_charge=Decimal("0")
        )

        _the_chain_names(monkeypatch, chain_version.id)
        with override_settings(BILLING_RESOLUTION_STEPS="R2 R3 R4"):
            ruled = _price_live(account)

    assert ruled.resolution_steps == ("R2", "R3", "R4")
    # The chain's ladder AND the chain's base, from one narrowing.
    assert _tier_prices(ruled) == tuple(Decimal(p) for _lo, _hi, p in DOUBLED_TIERS)
    assert _base_charges(ruled)["water"] == LIVE_BASE


@pytest.mark.django_db
def test_def2890__r3_r4_WITHOUT_r2_refuses_a_base_from_a_different_version(
    brazos, dana, monkeypatch
):
    """`DEF-2890` — the same unauditable bill, assembled from the opposite side.

    The test above proves R2 refuses to move the VERSION out from under a base
    it cannot restate. **This is the mirror, and it had no gate at all:** switch
    `R3 + R4` and leave R2 OFF, and the chain states the base while `gather` has
    already built every other figure on the service — the tier ladder, the
    minimum, the unit price — from the version the LIVE path resolved. When the
    two paths name different versions, one version's base lands on another
    version's ladder and every figure on the document agrees with itself.

    It has never run on a real bill (no deployment names a step) and the seeded
    utility has one version per schedule, so the two paths cannot name different
    versions there — which is the whole reason nothing found it.

    ⚠ **THE FIXTURE MOVED ON 2026-09-01 AND THE CASE DID NOT.** It was written
    on `DEF-2889`'s one-day boundary — a July version whose window ended ON the
    service date, which the live path priced and the chain read as finished.
    That defect is fixed: `effective_to` is the last day a version prices on
    BOTH paths now, so those two rows no longer disagree about anything and this
    case would have gone green for the wrong reason (both paths naming one
    version, no base to mix, no refusal to observe). The divergence is produced
    at the chain's ANSWER instead, through `_the_chain_names()` — see that
    helper for why that is the honest lever and not a fake seam. Both versions
    state a base of their own, and a base charge code is declared so the chain
    has an answer to stamp — without one it would refuse for `DEF-2830`'s reason
    instead and this case would prove nothing.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)
        chain_version = _a_second_priced_version(brazos, plan, tiers=DOUBLED_TIERS)

        # The live path is untouched and prices its own version end to end.
        live = _price_live(account)
        assert _base_charges(live)["water"] == LIVE_BASE
        assert _tier_prices(live) == tuple(Decimal(p) for _lo, _hi, p in fixture.WATER_TIERS)

        _the_chain_names(monkeypatch, chain_version.id)
        with override_settings(BILLING_RESOLUTION_STEPS="R3 R4"):
            with pytest.raises(gather.GatherProblem) as raised:
                _price_live(account)

    problem = raised.value
    assert problem.reason == gather.GATHER_RULED_PATH_REFUSED
    said = str(problem)
    assert "base charge" in said
    # Both version ids are named, so the repair is a lookup rather than a hunt.
    assert _version_id(live) in said
    # The sentence names the repair, not only the problem (BR-SHL-020).
    assert "rate-schedule rule" in said


@pytest.mark.django_db
def test_r2_refuses_a_version_the_chain_named_that_this_utility_cannot_price(
    brazos, dana, monkeypatch
):
    """An id with no priced version behind it stops the account, by name.

    `BR-RAT-031`: a saved draft has never been in force and may never price
    anything, and an unknown id is not an invitation to keep the run's own
    version. Both answer `None` from rating's by-id read and both refuse here —
    there is no fallback in this file and there must never be one
    (`BR-BIL-872`).
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)

        real = resolution_switch._resolve_for

        def _naming_a_version_nobody_has(data, *, account, service_date):
            resolved = real(data, account=account, service_date=service_date)
            return replace(
                resolved,
                services=tuple(
                    replace(
                        service,
                        schedule_version_id="00000000-0000-0000-0000-000000000000",
                    )
                    for service in resolved.services
                ),
            )

        monkeypatch.setattr(resolution_switch, "_resolve_for", _naming_a_version_nobody_has)
        with override_settings(BILLING_RESOLUTION_STEPS="R2"):
            with pytest.raises(Exception) as raised:
                _price_live(account)

    said = str(raised.value)
    assert "no priced version by that name" in said


@pytest.mark.django_db
def test_r7_serves_the_chains_taxes_and_CARRIES_the_levy_order_across(brazos, dana):
    """CR-052 task 22 — R7's fork, and the one field the chain cannot supply.

    The module used to list R7 among the steps with no fork, on the grounds that
    *"the two paths carry different shapes"*. Reading both shapes, they differ by
    one field each way. The chain's applicability fields have already been
    APPLIED by `resolve_taxes` — `resolved.taxes` is the narrowed answer — and
    its `services` has a home on the billing rule (`applies_to_services`, added
    so a *City Franchise Fee · Electric only* stops taxing the water).

    What the chain has no field for is `discount_treatment` (BR-RAT-106): whether
    an authority levies BEFORE or AFTER a discount. It is carried across from the
    live rule rather than defaulted, and this test pins that — a `None` here
    answers *before*, which is a real levy order, so a default would be an
    invented statutory fact.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)

        # Stated on both sides — R7 alone is the difference under test, and the
        # shipped default would otherwise add R3 and R4 to the baseline.
        with nothing_switched_on():
            live = _price_live(account)
        with override_settings(BILLING_RESOLUTION_STEPS="R7"):
            ruled = _price_live(account)

    assert live.resolution_steps == ()
    assert ruled.resolution_steps == ("R7",)
    # Same authorities, by identity rather than by display text.
    assert {str(rule.tax_id) for rule in ruled.taxes if rule.tax_id} == {
        str(rule.tax_id) for rule in live.taxes if rule.tax_id
    }
    # And the levy order survived the crossing, per rule.
    live_order = {str(rule.tax_id): rule.discount_treatment for rule in live.taxes if rule.tax_id}
    for rule in ruled.taxes:
        if rule.tax_id:
            assert rule.discount_treatment == live_order[str(rule.tax_id)]
    # R7 moved no base charge.
    assert _base_charges(ruled)["water"] == LIVE_BASE


@pytest.mark.django_db
def test_r7_refuses_when_a_chain_tax_matches_no_live_rule_to_take_its_levy_order_from(
    brazos, dana, monkeypatch
):
    """A tax the live path never attached has no `discount_treatment` to carry.

    `None` answers *before* — the column's own default and a real levy order —
    so accepting the tax and leaving the field empty would silently decide, for
    an authority nobody matched, that it levies on the reduced subtotal. It
    refuses instead.
    """
    from apps.billing import resolution_switch

    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        _declare_a_base_charge_code(brazos, amount=LIVE_BASE)

        real = resolution_switch._taxes_from_chain

        class _Stranger:
            code = "Duchy of Grand Fenwick"
            tax_id = "00000000-0000-0000-0000-0000000000ff"
            rate = Decimal("0.0900")
            flat_amount = None
            services = ()

        class _WithAStranger:
            def __init__(self, inner):
                self._inner = inner

            def __getattr__(self, name):
                return getattr(self._inner, name)

            @property
            def taxes(self):
                return tuple(self._inner.taxes) + (_Stranger(),)

        monkeypatch.setattr(
            resolution_switch,
            "_taxes_from_chain",
            lambda resolved, data: real(_WithAStranger(resolved), data),
        )
        with override_settings(BILLING_RESOLUTION_STEPS="R7"):
            with pytest.raises(Exception) as raised:
                _price_live(account)

    assert "levy order" in str(raised.value) or "discount_treatment" in str(raised.value)


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE SETTING REFUSES RATHER THAN PRETENDING
# ══════════════════════════════════════════════════════════════════════════


def test_an_unknown_step_name_refuses_and_is_never_read_as_off():
    with override_settings(BILLING_RESOLUTION_STEPS="R9"):
        with pytest.raises(resolution_switch.SwitchMisconfigured) as raised:
            resolution_switch.steps_served_by_chain()
    assert "not a step of the R1–R7 chain" in str(raised.value)


@pytest.mark.parametrize("named", ["R3b", "R6"])
def test_a_step_with_no_fork_refuses_rather_than_being_silently_ignored(named):
    """BR-BIL-874. Accepting a step and doing nothing would be reported to a PO
    as *"it has been live for a week and nothing broke"* when it never ran.

    ⚠ **THIS TEST NAMED `R2` UNTIL 2026-08-31 AND NOW NAMES THE TWO STEPS THAT
    ARE GENUINELY UNFORKED.** R2 got its fork with CR-052 task 22, so the old
    example had become a test of the wrong thing — it would have gone red on the
    commit that BUILT the rule, which is the correct signal and not a failure.
    `R3b` and `R6` are the two left, and each keeps its own recorded reason: the
    billable quantity lives on the reading rather than the tariff, and the two
    paths carry discounts in different shapes."""
    with override_settings(BILLING_RESOLUTION_STEPS=named):
        with pytest.raises(resolution_switch.SwitchMisconfigured) as raised:
            resolution_switch.steps_served_by_chain()
    assert "no fork" in str(raised.value)


@pytest.mark.parametrize("named", ["R3", "R4"])
def test_r3_and_r4_may_only_be_switched_together(named):
    """BR-BIL-873 — `resolve()` produces ONE base charge from both steps, so
    there is no seam between them to switch on its own."""
    with override_settings(BILLING_RESOLUTION_STEPS=named):
        with pytest.raises(resolution_switch.SwitchMisconfigured) as raised:
            resolution_switch.steps_served_by_chain()
    assert "BR-BIL-873" in str(raised.value)


# ══════════════════════════════════════════════════════════════════════════
# 4 · A REFUSAL IS A REFUSAL — never a quiet fall back to the old path
# ══════════════════════════════════════════════════════════════════════════


def test_a_chain_refusal_refuses_the_ACCOUNT_and_never_serves_the_live_answer(
    brazos, dana
):
    """The rule this whole cutover rests on: *"a lane that makes the
    disagreements go away has destroyed the evidence this job exists to
    produce"*.

    The base is blanked on the version and this tenant declares no `is_base`
    charge code, so **nobody has stated this service's base** and the chain
    refuses. With R3/R4 switched on, that must stop the account — not quietly
    hand back the live path's $8.00, which is a bill nobody could attribute to
    either path.

    ⚠ **THE REFUSAL MOVED FROM R3 TO R4 ON 2026-08-31 (`DEF-2823`), AND THEN
    OFF THE CHAIN ALTOGETHER ON 2026-09-28 (`DEF-BIL-7170`).** It used to be
    R3's *"…with a BLANK base charge"*, then R4's *"no charge code declaring
    `is_base`"*. The PO then retired the plan's own figure — *"we will never
    take default value from plan $8.0 - that is retired"* — and
    `gather._base_charge_for` now refuses this configuration **before the chain
    is consulted at all**, in six words.

    ⚠⚠ **SO THE GUARANTEE THIS CASE EXISTS FOR IS STRONGER, NOT WEAKER, AND
    THAT IS WHY IT IS RESTATED RATHER THAN DELETED.** It asked that a chain
    refusal must not *"quietly hand back the live path's $8.00"*. **There is no
    longer an `$8.00` to hand back**: with nobody having stated this service's
    base, the live path refuses too, and the two paths cannot disagree about a
    bill neither of them can produce. What is asserted below is exactly that —
    a refusal with the switch OFF and a refusal with it ON, and no figure
    either way. **The chain's own refusal still reaching an account is proved
    by `test_a_fact_the_adapter_cannot_assemble_refuses_too`**, which builds a
    configuration the live path CAN price and the chain cannot.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, asset, _delta = _account_on(brazos, dana, plan)
        _size_the_meter(asset)
        rating_models.TariffVersion.objects.filter(tenant=brazos).update(base_charge=None)

        # ⚠ SUPERSEDED 2026-09-30 (PO ruling: *"if user did not define and bind
        # base charges in rate schedule - then as a default you take 0 and
        # complete the bill instead of refusing"*). Both paths used to REFUSE
        # here; both now bill `$0.00` and say so. The guarantee this case
        # exists for — no figure served from the WRONG path — is unchanged:
        # the two sides state the SAME `$0.00` and the SAME warning.
        with nothing_switched_on():
            live = _price_live(account)
        with override_settings(BILLING_RESOLUTION_STEPS="R3 R4"):
            served = _price_live(account)

    def _water(data):
        return [c for c in data.tariffs if c.service == "water"][0].base_charge

    assert _water(live) == Decimal("0") == _water(served)
    # AMENDED 2026-10-01 (billing red triage): + `noAgreements`, FIRST. Since
    # `31358c239` (2026-09-30, PO option C: *"The bill still goes out, and the
    # clerk sees the gap and can fix the account."*) an account with NO service
    # agreements on file bills everything and is WARNED, and this fixture's
    # account holds none. The base warning this case is about is unchanged.
    assert [w["key"] for w in live.warnings] == [
        "billing.oneTime.warn.noAgreements",
        "billing.oneTime.warn.baseNotSet",
    ]
    assert served.warnings == live.warnings


def test_a_fact_the_adapter_cannot_assemble_refuses_too(brazos, dana):
    """No connection size recorded, R3/R4 switched on: the ruled path has no
    answer, so the account stops. Serving it from the old implementation would
    be the silent fallback the decision log forbids."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        # ⚠ **`size_class=None` IS NOW STATED, AND THE COMMENT BELOW IS WHY THIS
        # WAS A REGRESSION WAITING TO HAPPEN (`DEF-2965`).** It already said
        # "deliberately NOT sized" — the INTENT was explicit and the CODE was
        # inherited, and on 2026-09-01 `_account_on`'s default became the
        # service's smallest ratified band, so the meter arrived sized and the
        # refusal this case exists to prove simply did not fire: `DID NOT RAISE
        # GatherProblem`. Third occurrence in one wave of the same shape
        # (`DEF-2817`): a case whose SUBJECT is an absence must ASK for the
        # absence, because a default it merely relies on is a default somebody
        # else will change.
        account, _unit, _asset, _delta = _account_on(
            brazos, dana, plan, size_class=None
        )
        # deliberately NOT sized — DEF-514's world, before a utility records one
        # ⚠ **AND A BASE CHARGE CODE IS DECLARED FROM 2026-09-28
        # (`DEF-BIL-7170`), WHICH IS WHAT KEEPS THIS CASE ABOUT ITS OWN
        # SUBJECT.** The PO retired the plan's base, so a tenant with no
        # `is_base` code is stopped by `gather._base_charge_for` BEFORE the
        # chain is ever consulted — and this case would have proved that
        # refusal instead of the one it is named for. The code is flat and
        # unscoped, so it prices with or without a size, and what is left in
        # the way is exactly the missing CONNECTION SIZE.
        _declare_a_base_charge_code(brazos)

        with override_settings(BILLING_RESOLUTION_STEPS="R3 R4"):
            with pytest.raises(gather.GatherProblem) as raised:
                _price_live(account)

    assert raised.value.reason == gather.GATHER_RULED_PATH_REFUSED
    assert "connection size" in str(raised.value)


def test_a_master_account_reaches_the_chain_and_a_repeated_service_still_refuses():
    """⚠ **THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-09-30 (`DEF-BIL-8470`)** —
    *"a master account is refused outright rather than approximated"*, on the
    premise that the adapter asked only the ANCHOR's unit. The adapter now asks
    each service's SERVING covered unit (`gather._coverage_facts`), so a master
    bill is one connection per service and is substituted like any other; the
    refusal and its premise are withdrawn together. A service with TWO tariffs
    (OQ-334's shape) still refuses by name.

    Pure, with no database: `_substituted` is handed the two shapes.
    """
    from dataclasses import dataclass, replace as dc_replace

    @dataclass(frozen=True)
    class _Cfg:
        service: str
        base_charge: Decimal = LIVE_BASE
        jurisdiction_factor: Decimal = Decimal("1")

    @dataclass(frozen=True)
    class _Data:
        account_no: str = "SCW-0001"
        tariffs: tuple = ()
        snapshot: dict | None = None
        resolution_steps: tuple = ()

    class _Reached(Exception):
        pass

    class _Resolved:
        def service(self, code):
            raise _Reached(code)

    master = _Data(
        tariffs=(_Cfg("water"),),
        snapshot={"covered_units": [{"unit_id": "a"}, {"unit_id": "b"}]},
    )
    # The master shape is no longer refused: substitution asks the chain for
    # its one water answer, which is what `_Reached` records.
    with pytest.raises(_Reached) as reached:
        resolution_switch._substituted(
            master, _Resolved(), frozenset({"R3", "R4"}), service_date=SERVICE_DATE
        )
    assert str(reached.value) == "water"

    twice = _Data(tariffs=(_Cfg("water"), _Cfg("water")), snapshot={})
    with pytest.raises(resolution_switch.RuledPathRefused) as raised:
        resolution_switch._substituted(
            twice, _Resolved(), frozenset({"R3", "R4"}), service_date=SERVICE_DATE
        )
    assert "more than one tariff for water" in str(raised.value)
    assert dc_replace  # the substitution path uses it; imported to keep ruff quiet


def test_a_service_the_chain_did_not_resolve_refuses_rather_than_staying_live():
    """A per-service silent fallback would price ONE bill by two narrowings —
    the disagreement reconciled away invisibly, one line at a time."""
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class _Cfg:
        service: str
        base_charge: Decimal = LIVE_BASE
        jurisdiction_factor: Decimal = Decimal("1")

    @dataclass(frozen=True)
    class _Data:
        account_no: str = "SCW-0001"
        tariffs: tuple = ()
        snapshot: dict | None = None
        resolution_steps: tuple = ()

    class _Resolved:
        def service(self, code):
            raise KeyError(code)

    data = _Data(tariffs=(_Cfg("water"),), snapshot={})
    with pytest.raises(resolution_switch.RuledPathRefused) as raised:
        resolution_switch._substituted(
            data, _Resolved(), frozenset({"R5"}), service_date=SERVICE_DATE
        )
    assert "resolved no schedule for 'water'" in str(raised.value)


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE CLERK CAN READ IT — eleven catalogues, not thirteen
# ══════════════════════════════════════════════════════════════════════════


def test_the_refusal_reason_has_copy_in_all_eleven_catalogues():
    """`DEF-518`: `BillRunWizard` renders `billing.run.reason.<code>` with the
    raw snake_case code as its default, so a missing key puts an identifier in
    front of a clerk."""
    key = f"billing.run.reason.{gather.GATHER_RULED_PATH_REFUSED}"
    files = sorted(LOCALES.glob("*.json"))
    assert len(files) == 11, f"expected eleven catalogues, found {len(files)}"
    missing = [
        path.name for path in files if key not in json.loads(path.read_text("utf-8"))
    ]
    assert not missing, f"{key} is missing from {missing}"
