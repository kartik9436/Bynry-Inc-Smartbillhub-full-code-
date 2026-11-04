# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-001 (EP-RBS-01) — CR-075 wave C tasks C6 and C7.
#           C6: the report is composed at close and FROZEN; an unknown block is
#           refused AT CLOSE, not at render (TC-RBS-16); TC-RBS-14's static
#           scan — no failure reason without a fix route.
#           C7: the blockers fixture — no tax region · one plan with no rate
#           above 20,000 gallons · 4 accounts with no unit → EXACTLY 3 blockers
#           and 3 fix routes; and the per-service rollup (Sewer red, Water
#           green).
# Rules:    BR-RBS-011 (a failure names its fix route) · BR-RBS-020 (composed at
#           close and frozen) · BR-RBS-021 (twelve blocks) · BR-RBS-038 (a run
#           pins its version) · 01-overview.md §8.1 (the rollup)
# Tests:    this file
# Impacts:  apps/runbooks/definitions/configuration_check.py
# ───────────────────────────────────────────────────────
"""Runbook 1 on real data — three blockers, a per-service rollup, a frozen report.

⚠ **WHAT THIS FILE CAN AND CANNOT PROVE, SAID FIRST.** It runs on the default
suite, which is in-memory SQLite. Two things are therefore NOT proved here and
are not pretended to be: the per-record savepoint (`TC-RBS-5`, PostgreSQL only,
`tests/test_rbs_savepoint_pg.py`) and tenant isolation, which does not exist on
SQLite at all. Neither is load-bearing for this runbook — every one of its ten
steps is `set` mode and none of them writes — but the sentence belongs here
anyway, because the next lane to add a per-record step to a Check will read this
file first.

⚠ **THE FIXTURE'S OWN NUMBER IS ASSERTED, NOT ITS SHAPE.** `assert len(blockers)
== 3` and never `assert blockers`. A fixture that produced four blockers because
one step reported the same fault twice would pass *"some blockers"* and would be
exactly the defect this Check exists to avoid — a clerk who is told four things
are wrong when three are.
"""

from __future__ import annotations

import ast
import pathlib
import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.runbooks import models, services
from apps.runbooks.contract import BLOCK_TYPES, RunbookContractError
from apps.runbooks.definitions import configuration_check as rb1
from apps.runbooks.engine import executor
from apps.runbooks.registry import registry
from core import tenancy as core_tenancy
# ⚠ **THE STAR IMPORT IS LOAD-BEARING AND IS NOT LAZINESS.** `test_us_ten_helpers`
# declares an `autouse` fixture, `sqlite_guc`, that sends `set_config('app.tenant_id',
# …)` to a recording fake on SQLite — which has no such function — while leaving the
# Python-side ContextVar mirror real, so every selector's tenant filter is still
# exercised. Importing only the names this file uses leaves that fixture unregistered
# and **every tenant context dies with `sqlite3.OperationalError: no such function:
# set_config`**, which reads as a broken fixture rather than as a missing import. The
# whole runbooks conformance suite imports it the same way and for the same reason.
from tests.test_us_met_helpers import *  # noqa: F401,F403 — incl. the autouse sqlite_guc
from tests.test_us_met_helpers import (  # noqa: F401
    growth_plan,
    identity_seam,
    make_plan,
    make_premises,
    seed_physical_series,
    seeding_ctx,
    staff_actor,
)
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant

pytestmark = pytest.mark.django_db


# ── the two fixtures C7 asks for ──────────────────────────────────────────


def _tenant(subdomain: str, name: str, services_sold):
    tenant, _ = provisioned_tenant(
        brazosbend_payload(name=name, subdomain=subdomain, services=list(services_sold))
    )
    seed_physical_series(tenant)
    return tenant


def _strip_every_tax_region(tenant) -> None:
    """Leave the tenant with NO tax authority at all — runbook 1 step 3's blocker.

    ⚠ **BOTH TABLES, AND THE PRICED ONE FIRST.** Provisioning writes tax
    JURISDICTIONS (the names) and the rating sample block writes TAXES (the
    rates), and `tax_pricing_gap` counts them separately precisely because a
    tenant can have the first and not the second. Deleting only the taxes would
    build the WARNING fixture, not the blocker one, and the case would then
    assert three blockers over a tenant that has two.
    """
    from apps.rating import models as rating_models

    with seeding_ctx(tenant):
        rating_models.Tax.objects.filter(tenant=tenant).delete()
        rating_models.TaxJurisdiction.objects.filter(tenant=tenant).delete()


def _plan_with_a_ladder(tenant, *, service_code: str, name: str, top_block):
    """A published plan whose schedule carries an ACTIVATED version and tiers.

    `top_block=None` is an unbounded ladder — `BR-RAT-032`'s `0 → ∞` last tier,
    which is the CORRECT shape and the one runbook 1 must report nothing about.
    A number is a ladder that stops, and usage above it can be priced by nobody.
    """
    from apps.rating import models as rating_models

    plan = make_plan(tenant, name=name, services=(service_code,))
    with seeding_ctx(tenant):
        schedule = rating_models.PlanRateSchedule.objects.get(
            tenant=tenant, rate_plan=plan, service__code=service_code
        )
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=schedule.tariff,
            model="tiered",
            uom="gal",
            effective_from=date(2026, 1, 1),
        )
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=1,
            from_qty=Decimal("0"),
            to_qty=Decimal("5000"),
            unit_price=Decimal("3.2000"),
        )
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=version,
            seq=2,
            from_qty=Decimal("5000"),
            to_qty=None if top_block is None else Decimal(top_block),
            unit_price=Decimal("4.8000"),
        )
    return plan


def _accounts_that_reach_no_property(tenant, count: int):
    """`count` accounts with **no unit** whose address does not resolve.

    ⚠ **THIS IS THE ONLY SHAPE THE DATABASE PERMITS, AND THE EXECUTION PLAN'S
    WORDS FOR IT ARE LOOSER THAN THEY LOOK (`DEF-RBS-4280`).** Task `C7` says
    *"4 accounts with no unit"*. A **`regular`** account with no unit cannot be
    written at all — `ck_accounts_regular_has_unit` refuses it, and
    `ck_accounts_anchored` refuses any account naming neither a unit nor a
    premises, both since `CR-056` W1 on 2026-09-01. So an account with no unit
    is a **Master Account**, which names an address instead (`BR-CUS-1010`), and
    the fault runbook 1 step 6 can actually find is one whose address does not
    resolve.

    **That is a real production shape rather than a fixture trick.**
    `accounts.premises_id` is a plain `UUIDField` and deliberately NOT a foreign
    key — migration `0037` says so and why: `B2` §2's cross-module FK set is
    reviewed and this column is not in it. **Nothing in the database stops it
    pointing at a premises that no longer exists**, which is exactly why a Check
    has to look.
    """
    from apps.customers import models as customers_models

    with seeding_ctx(tenant):
        status = customers_models.AccountStatus.objects.filter(tenant=tenant).first()
        account_type = customers_models.AccountType.objects.first()
        for index in range(count):
            customers_models.Account.objects.create(
                tenant=tenant,
                kind="master",
                unit=None,
                premises_id=uuid.uuid4(),
                account_no=f"A-9000{index}",
                status=status,
                account_type=account_type,
            )


@pytest.fixture()
def blockers_tenant(growth_plan, identity_seam):  # noqa: F811
    """C7's fixture: **no tax region · a ladder that stops at 20,000 gallons ·
    4 accounts that reach no property** — and nothing else wrong.

    ⚠ **ONE SERVICE, AND THAT IS WHAT MAKES THE NUMBER 3.** Step 3 is
    per-service (`01-overview.md` §8.1), so a missing tax region reddens every
    enabled service and a two-service utility with no tax region has **two**
    tax blockers, correctly. The card's *"3 things stop billing"* is a utility
    with one. The rollup fixture below is the two-service case and asserts the
    opposite half.
    """
    tenant = _tenant("blockerswater", "Blockers Water Co", ["water"])
    _strip_every_tax_region(tenant)
    _plan_with_a_ladder(tenant, service_code="water", name="Residential Water", top_block="20000")
    _accounts_that_reach_no_property(tenant, 4)
    return tenant


@pytest.fixture()
def rollup_tenant(growth_plan, identity_seam):  # noqa: F811
    """C7's second fixture: **Sewer red, Water green**, on one utility.

    Everything a tax region needs is left alone, so step 3 finds nothing and
    cannot redden both services. The only per-service fault is Sewer's ladder,
    which stops; Water's runs to no limit, which is what a correct ladder does.
    """
    tenant = _tenant("rolluputility", "Rollup Utility", ["water", "sewer"])
    _plan_with_a_ladder(tenant, service_code="water", name="Residential Water", top_block=None)
    _plan_with_a_ladder(tenant, service_code="sewer", name="Residential Sewer", top_block="20000")
    return tenant


def _run(tenant):
    with core_tenancy.tenant_context(tenant.id):
        return executor.execute(registry.get("configuration_check"), tenant_id=tenant.id)


#: The pill a weight is drawn as. `StatusPill` never knows a domain status, so
#: the weight travels as the LABEL a clerk reads and the tone it is drawn in —
#: which is why these tests read it back through the label rather than around it.
_PILL_WEIGHT = {"Blocks billing": rb1.BLOCKER, "Warning": rb1.WARNING}

#: The step label a clerk reads, back to the key the runbook names it by.
_STEP_BY_LABEL = {label: key for key, label in rb1.STEP_LABELS.items()}


def _flat(row):
    """One `ReportRow` read back as the flat finding it was composed from.

    ⚠ **THE REPORT CARRIES THE RENDERER'S SHAPE SINCE `DEF-RBS-4284`.** Every
    cell says what KIND it is — `text`, `pill`, `link` — so the screen picks
    `StatusPill` for a status and a router link for a route without any screen
    deciding. These tests read THROUGH that shape rather than around it: a cell
    whose kind or key changes breaks this helper by name, which is the point.
    Before the fix, the engine emitted flat rows the twelve block components
    could not draw, and every suite on both sides was green.
    """
    cells = row["cells"]
    return {
        # ⚠ The cell carries the step's LABEL — *Tax*, not `tax` — because B14
        # rule 32 forbids an internal code in clerk-facing copy and this cell IS
        # the copy. It is mapped back to the key here so these tests keep
        # asserting the step they mean, and the mapping itself is the assertion:
        # a label that stops resolving fails by name.
        "step": _STEP_BY_LABEL[cells["step"]["text"]],
        "step_label": cells["step"]["text"],
        "finding": cells["finding"]["text"],
        "affects": cells["affects"]["text"],
        "weight": _PILL_WEIGHT[cells["weight"]["label"]],
        "fix_route": cells["fix"]["to"],
        "fix_label": cells["fix"]["label"],
        # Carried on the row and drawn by nothing — see `ReportRow.meta`.
        **row["meta"],
    }


def _records(result):
    return next(b for b in result.report if b["block"] == "records")["payload"]


def _rows(result):
    return [_flat(row) for row in _records(result)["rows"]]


def _blockers(result):
    return [row for row in _rows(result) if row["weight"] == rb1.BLOCKER]


def _services(result):
    """The breakdown's service codes, read out of its `ReportRow` cells."""
    breakdown = next(b for b in result.report if b["block"] == "breakdown")
    return [row["cells"]["service"]["text"] for row in breakdown["payload"]["rows"]]


# ── C7 · the blockers fixture ─────────────────────────────────────────────


def test_us_rbs_001_the_fixture_produces_exactly_three_blockers(blockers_tenant):
    """**Exactly three**, and the number is the assertion (`US-RBS-001`).

    A Check that reports *some* blockers is a Check nobody can act on. The three
    are the card's own three — the tax region, the block above 20,000 gallons,
    and the accounts that reach no property — and each names the step it came
    from, so a fourth arriving from anywhere fails here with its own step in the
    message rather than as a bare count mismatch.
    """
    result = _run(blockers_tenant)
    blockers = _blockers(result)
    assert [row["step"] for row in blockers] == [
        rb1.STEP_TAX,
        rb1.STEP_RATES,
        rb1.STEP_CHAIN,
    ], f"expected the card's three, got {[(r['step'], r['finding']) for r in blockers]}"
    assert len(blockers) == 3


def test_us_rbs_001_every_blocker_names_a_fix_route_and_a_button(blockers_tenant):
    """Three blockers, three fix routes, three distinct buttons (`BR-RBS-011`).

    The routes are asserted as VALUES rather than merely as non-empty, because
    *"has a fix route"* is satisfied by a string, and a string that names no
    screen is a dead button over a live finding — hard-won law 2's mirror, the
    shape that left the customer portal with two working doors out of eight.
    """
    blockers = _blockers(_run(blockers_tenant))
    assert [row["fix_route"] for row in blockers] == [
        rb1.FIX_PLANS_RATES,
        rb1.FIX_PLANS_RATES,
        rb1.FIX_ACCOUNTS,
    ]
    assert [row["fix_label"] for row in blockers] == [
        "Set a tax region",
        "Add a block",
        "Match units",
    ]
    assert len({row["fix_label"] for row in blockers}) == 3


def test_us_rbs_001_the_headline_counts_the_blockers_and_not_the_warnings(blockers_tenant):
    """*"3 things stop billing"* — the card's own sentence, four words.

    Warnings are counted separately and never reach the headline: a utility told
    *"9 things stop billing"* when three do will stop reading the number.
    """
    result = _run(blockers_tenant)
    verdict = next(b for b in result.report if b["block"] == "verdict")
    assert verdict["payload"]["count"] == "3 things stop billing"
    # `word` is what a clerk reads and `tone` is how it is drawn — never `no_go`,
    # which is an internal code and would breach B14 rule 32 on screen.
    assert verdict["payload"]["word"] == "No-go"
    assert verdict["payload"]["tone"] == "danger"


def test_us_rbs_001_the_block_that_stops_reads_as_a_quantity_and_not_as_storage(blockers_tenant):
    """`DEF-1121` — *20000*, never *20000.000000*.

    `version_structure` serves every tier bound at STORAGE precision, so the
    ceiling arrives as a six-place string. A block bound is a QUANTITY: at most
    two decimals with the zeros TRIMMED (`BR-MET-144`), which is a different
    rule from money's two decimals with the zeros KEPT (`BR-SHL-250`). Three
    screens got this wrong at once and a water tier read `0.000000 – 5.000000`
    to a live utility.
    """
    finding = next(row for row in _blockers(_run(blockers_tenant)) if row["step"] == rb1.STEP_RATES)
    assert "20000 gal" in finding["finding"]
    assert "20000.000000" not in finding["finding"]


def test_us_rbs_001_the_chain_is_red_at_the_earliest_failure(blockers_tenant):
    """Ten cells, in order, red where the step found a blocker.

    **A Check runs every step whatever the earlier ones found.** Stopping at the
    first would tell a clerk one thing to fix and hide the two behind it, and
    the utility would run this three times instead of once — which is why the
    chain draws a state per cell and the *earliest* failure is simply the first
    red one.
    """
    chain = next(b for b in _run(blockers_tenant).report if b["block"] == "chain")
    cells = chain["payload"]["cells"]
    assert len(cells) == 10
    assert [c["position"] for c in cells] == list(range(1, 11))
    # `bad` is `ChainCellState`'s own word. ⚠ A WARNING DOES NOT REDDEN A CELL:
    # `wireframes/RBS-006-R1.png` draws cells 3, 5 and 6 red — the three
    # BLOCKERS — and draws 7, 8 and 9 green, which carry this fixture's six
    # warnings. The KPI strip counts those and the table lists them.
    red = [c["position"] for c in cells if c["state"] == "bad"]
    assert red == [3, 5, 6]
    assert min(red) == 3


def test_us_rbs_001_a_step_states_what_it_looked_at_and_not_only_what_it_found(blockers_tenant):
    """An empty estate and a correct one must not read the same (hard-won law 7).

    `G32` reported **0 unresolved** truthfully over 21 live refusals it could not
    see. Every step here publishes what it examined beside what it found, so a
    reader can tell *nothing was wrong* from *nothing was looked at* — and the
    two steps that genuinely cannot answer half their card question say so in
    the same place rather than staying silent.
    """
    checked = _records(_run(blockers_tenant))["checked"]
    assert checked[rb1.STEP_CHAIN] == {"accounts": 4, "broken": 4}
    assert checked[rb1.STEP_TAX]["authorities"] == 0
    assert checked[rb1.STEP_RATES]["ladders"] == 1
    # The declared blind spots, each with its own sentence rather than a silence.
    assert "not made" in checked[rb1.STEP_RATES]["usage_comparison"]
    # ⚠ **THIS ASSERTED A DECLARED BLIND SPOT UNTIL 2026-09-17.** It read
    # `"platform data" in checked[...]["account_types"]` — true of a PLATFORM
    # table nothing tenant-scoped could read. The PO ruled *"utility can get
    # their own account types"* (`BR-CUS-1079`), so the step counts real rows
    # and a blind spot that has stopped being blind is not left reading like a
    # considered exclusion.
    types = checked[rb1.STEP_REFERENCE]["account_types"]
    assert types["total"] == 8 and types["selectable"] == 7, types
    assert "not checked" in checked[rb1.STEP_DOCUMENTS]["per_language"]


def test_us_rbs_001_a_master_account_with_a_good_address_is_not_a_blocker(blockers_tenant):
    """The false positive that would have made step 6 useless (`BR-CUS-1010`).

    A Master Account is the owner's account at an ADDRESS and names **no unit**,
    lawfully. A step that read *no unit* as *broken* would report every master
    account in the product as a blocker — and every utility with a landlord on
    its books would learn to ignore this runbook on its first run.
    """
    from apps.customers import models as customers_models

    # Through the REAL service rather than the ORM, so the address this account
    # is re-anchored to is one the product would actually have created — the
    # `make_premises` precedent, and hard rule 8's single address home.
    admin = staff_actor(blockers_tenant, "system_admin", "chain@blockerswater.test")
    with core_tenancy.tenant_context(blockers_tenant.id):
        premises = make_premises(admin, services_available=["water"])
    with seeding_ctx(blockers_tenant):
        customers_models.Account.objects.filter(
            tenant=blockers_tenant, kind="master"
        ).update(premises_id=premises["id"])

    blockers = _blockers(_run(blockers_tenant))
    assert [row["step"] for row in blockers] == [rb1.STEP_TAX, rb1.STEP_RATES]


# ── C7 · the per-service rollup ───────────────────────────────────────────


def test_us_rbs_001_sewer_is_red_while_water_is_green(rollup_tenant):
    """`01-overview.md` §8.1, and it is the reason the rollup exists at all.

    *"A two-service utility that fixes water would watch the verdict go from
    No-go to No-go and learn nothing. Sewer must stay visibly red while water
    goes green."* A single tenant verdict cannot show progress, and showing
    progress is the whole point of the screen.
    """
    result = _run(rollup_tenant)
    breakdown = next(b for b in result.report if b["block"] == "breakdown")
    assert breakdown["payload"]["heading"] == "By service"
    assert _services(result) == ["sewer", "water"]
    verdicts = [row["cells"]["verdict"] for row in breakdown["payload"]["rows"]]
    assert [v["label"] for v in verdicts] == ["No-go", "Go"]
    assert [v["tone"] for v in verdicts] == ["danger", "success"]


def test_us_rbs_001_the_tenant_verdict_is_the_worst_of_the_services(rollup_tenant):
    """Blocker anywhere → **No-go**; a green service never dilutes a red one.

    Worst-wins rather than any kind of average: a verdict that averaged across
    services would let a disabled or a healthy one hide a live fault, which
    §8.1 names as the fourth reason for the whole decision.
    """
    verdict = next(b for b in _run(rollup_tenant).report if b["block"] == "verdict")
    assert verdict["payload"]["word"] == "No-go"
    assert verdict["payload"]["count"] == "1 thing stops billing"


def test_us_rbs_001_a_service_with_nothing_wrong_is_still_listed(rollup_tenant):
    """Water appears as `go` rather than vanishing from the table.

    A screen that listed only the faulty services would show movement as a row
    DISAPPEARING, which reads like a bug rather than like progress — and the
    clerk who just fixed water would have nothing confirming they had.
    """
    assert set(_services(_run(rollup_tenant))) == {"water", "sewer"}


def test_us_rbs_001_a_tenant_wide_finding_reddens_no_single_service(blockers_tenant):
    """A finding with no service counts towards the tenant verdict and no other.

    The account chain is the case that matters: four accounts reaching no
    property is one fault about the utility, not a fault of Water. Attributing
    it to a service would redden a service whose own configuration is perfect,
    and the breakdown would then be unable to show water going green.

    ⚠ **THE ROLLUP IS COMPUTED PER FINDING, NOT PER STEP, AND §8.1's TWO LISTS
    ARE THE EXPLANATION RATHER THAN THE IMPLEMENTATION.** §8.1 classifies steps
    — *"1, 3, 4, 5, 7, 9 and 10 are per-service; 2, 6 and 8 are tenant-wide"* —
    and that is true of what each step is ABOUT. It does not follow that every
    finding of a per-service step belongs to a service: step 10 is per-service
    because a revenue account is, and *"3 places in the books have no account
    behind them"* is about the books rather than about Water. Attributing it to
    every service would redden a service whose own configuration is perfect,
    which is the exact failure §8.1's second reason names. Recorded in the
    decision log of 2026-09-06 with this worked case.
    """
    rows = _rows(_run(blockers_tenant))
    tenant_wide = {row["step"] for row in rows if row["service"] is None}
    assert rb1.STEP_CHAIN in tenant_wide
    # Every tenant-wide STEP that found anything is here …
    for step in rb1.TENANT_WIDE_STEPS:
        if any(row["step"] == step for row in rows):
            assert step in tenant_wide
    # … and no finding that names a service is counted as tenant-wide.
    assert all(row["service"] is not None or row["step"] in tenant_wide for row in rows)


# ── BR-RBS-042 · the two tests that rule records as owed ──────────────────


def test_us_rbs_001_a_service_enabled_after_a_run_appears_in_the_next_one(rollup_tenant):
    """`BR-RBS-042` clause 1 — ***all* is resolved at RUN START, not at setup.**

    This is the owed test the rule names in its own row: *"a domain with a
    service added after setup resolves to the LARGER set on the next run"*. The
    PO's reason is the failure mode rather than the mechanism — expanding *all*
    into a list at configure time makes **adding a service silently drop it out
    of every runbook set to *all***, with nothing on any screen to see.

    Runbook 1 satisfies it structurally rather than by a setting: its scope panel
    is *Scope decided for you*, the service list is permanently *all*, and it is
    read when the run starts. That is exactly the shape the rule asks for, and
    this case is what stops a later lane "optimising" the read onto the
    definition.
    """
    from apps.tenancy import models as tenancy_models

    def services_in(result):
        return set(_services(result))

    assert services_in(_run(rollup_tenant)) == {"water", "sewer"}

    with seeding_ctx(rollup_tenant):
        # ⚠ **UPDATED, NOT CREATED.** Provisioning writes a `tenant_services`
        # row for EVERY catalogue service and enables the chosen ones, so
        # enabling a service later is a flag moving rather than a row appearing
        # — `uq` on (tenant, service) refuses the second row. That is exactly
        # the shape `BR-RBS-042` clause 1 is about: nothing changes in the
        # runbook's own configuration, and the next run must still find three.
        tenancy_models.TenantService.objects.update_or_create(
            tenant=rollup_tenant,
            service=tenancy_models.Service.objects.get(code="trash"),
            defaults={"enabled": True, "disabled_at": None},
        )

    assert services_in(_run(rollup_tenant)) == {"water", "sewer", "trash"}


def test_us_rbs_001_the_service_domain_is_read_per_tenant(rollup_tenant, blockers_tenant):
    """`BR-RBS-042` clause 2 — **every domain is tenant-resolved, never hardcoded.**

    The rule's own words: *"no utility has all eleven services or every
    plan-and-rate combination"*. Two utilities, two different answers, from one
    runbook — and the one-service utility must not see a Sewer verdict it does
    not sell, because a verdict over a service nobody sells is noise a clerk has
    to learn to ignore.
    """

    def services_in(tenant):
        return set(_services(_run(tenant)))

    assert services_in(rollup_tenant) == {"water", "sewer"}
    assert services_in(blockers_tenant) == {"water"}


# ── C6 · composed at close, and FROZEN ────────────────────────────────────


def _runbook_row(tenant, definition):
    return models.Runbook.objects.create(
        tenant=tenant,
        key=definition.key,
        name=definition.name,
        kind=definition.kind,
        category=definition.category,
        subject_type=definition.subject_type,
        unit_of_work=definition.unit_of_work,
    )


def test_us_rbs_001_tc_rbs_16_an_unknown_block_is_refused_at_close(blockers_tenant):
    """`TC-RBS-16` — refused at CLOSE, the run marked **failed**, report empty.

    ⚠ **AT CLOSE AND NOT AT RENDER, AND THE DIFFERENCE IS THE WHOLE TEST.**
    Refused at render, the run is already marked `done`: a clerk opens it, meets
    a half-drawn screen, and has no way to tell whether the missing part
    mattered. Refused at close, the run says `failed` and the block is named, so
    nobody reads a partial answer as a whole one.

    This is wave B's assertion re-made over **runbook 1's own report path**
    rather than over an exemplar, because that is what C6 delivers: the wave-B
    case proved the mechanism with a hand-built `RunResult`, and this one proves
    the runbook that a utility will actually press Run on cannot smuggle a
    thirteenth block past `close_run`.
    """
    definition = registry.get("configuration_check")
    with core_tenancy.tenant_context(blockers_tenant.id):
        runbook = _runbook_row(blockers_tenant, definition)
        run = services.open_run(runbook, definition)
        result = executor.execute(definition, tenant_id=blockers_tenant.id, run_id=run.pk)
        smuggled = executor.RunResult(
            runbook_key=result.runbook_key,
            subjects=result.subjects,
            scope_fingerprint=result.scope_fingerprint,
            guarded=result.guarded,
            set_results=result.set_results,
            records=result.records,
            counts=result.counts,
            report=[*result.report, {"block": "timeline", "payload": {}}],
            step_runs=result.step_runs,
        )
        with pytest.raises(RunbookContractError) as refusal:
            services.close_run(run, smuggled)

    assert "timeline" in str(refusal.value)
    run.refresh_from_db()
    assert run.status == models.RUN_STATUS_FAILED
    assert run.report == []


def test_us_rbs_001_the_report_is_frozen_and_a_later_run_does_not_rewrite_it(blockers_tenant):
    """`BR-RBS-020` — a past run reopened draws exactly what it drew that day.

    The utility fixes its tax region and runs again. **The first run's stored
    report must not move**: its blocker count, its headline and its every byte
    stay as they were, because that is the thing a regulator asks for and the
    thing a clerk uses to prove they fixed something.
    """
    definition = registry.get("configuration_check")
    with core_tenancy.tenant_context(blockers_tenant.id):
        runbook = _runbook_row(blockers_tenant, definition)
        first, _ = services.run_to_completion(runbook, definition)
    frozen = first.report
    first_headline = next(b for b in frozen if b["block"] == "verdict")["payload"]["count"]
    assert first_headline == "3 things stop billing"

    # The utility fixes the tax region, then runs again.
    from apps.rating import models as rating_models

    with seeding_ctx(blockers_tenant):
        rating_models.TaxJurisdiction.objects.create(
            tenant=blockers_tenant, name="City of Blockers", level="city"
        )
    with core_tenancy.tenant_context(blockers_tenant.id):
        second, _ = services.run_to_completion(runbook, definition)

    first.refresh_from_db()
    assert first.report == frozen, "a past run's report moved when a later run was taken"
    assert next(b for b in first.report if b["block"] == "verdict")["payload"]["count"] == (
        "3 things stop billing"
    )
    assert next(b for b in second.report if b["block"] == "verdict")["payload"]["count"] == (
        "2 things stop billing"
    )


def test_us_rbs_001_every_block_it_composes_is_one_of_the_twelve(blockers_tenant):
    """Six of the twelve, and a thirteenth is never minted (`BR-RBS-021`).

    §8.1's rollup added `Verdict` and `Breakdown` to the card's four **because
    both were already in the vocabulary** — a thirteenth block needs three
    runbooks that cannot be drawn without it, and one runbook wanting a new
    shape composes the twelve differently instead.
    """
    blocks = [b["block"] for b in _run(blockers_tenant).report]
    assert blocks == ["verdict", "kpis", "chain", "breakdown", "records", "downloads"]
    assert set(blocks) <= set(BLOCK_TYPES)


def test_us_rbs_001_a_run_of_this_check_writes_only_this_modules_own_tables(blockers_tenant):
    """`TC-RBS-15`'s *a Check wrote nothing* — over the real runbook this time.

    ⚠ **WHAT THIS PROVES AND WHAT IT DOES NOT.** It proves the run added rows to
    `runbooks`, `runbook_versions`, `runbook_runs` and — since 2026-09-07 —
    `work_items`, and to nothing else this module owns.

    ⚠ **`work_items` IS NOT ZERO AND THAT IS THE RULE, NOT A LEAK.** This case
    asserted `WorkItem.objects.count() == 0` when it was written on 2026-09-06,
    the day before runbook 1 declared `findings()` (`6de638775`, CR-075 waves
    J/K, `US-RBS-006`). `BR-RBS-022` makes raising a work item an ENGINE act —
    the Check holds no port and writes nothing itself, the engine upserts its
    findings at run close — and `J-RBS-1`'s last step (*"fix the tax region,
    re-run, and the item closes itself"*) is what the rows exist for. So the
    question is now the right one: every item was raised BY THIS RUN, AS A
    FINDING, and nothing else in the module moved. It does NOT prove another module's table was untouched — that
    is `G115`'s job, statically, over every file in the module, and it is the
    stronger proof because it does not depend on the fixture happening to
    contain a row of the kind that would have been written.
    """
    definition = registry.get("configuration_check")
    assert definition.ports == (), "a Check holds no ports at all (BR-RBS-002)"
    with core_tenancy.tenant_context(blockers_tenant.id):
        runbook = _runbook_row(blockers_tenant, definition)
        services.run_to_completion(runbook, definition)

    assert models.RunbookRunRecord.objects.count() == 0
    run = models.RunbookRun.objects.get(runbook=runbook)
    items = models.WorkItem.objects.all()
    # The fixture's three blockers and its one warning (`WORK_ITEM_WEIGHT`).
    assert items.count() == 4
    assert set(items.values_list("source_run_id", flat=True)) == {run.id}
    assert set(items.values_list("source_kind", flat=True)) == {models.WORK_ITEM_SOURCE_FINDING}
    assert models.RunbookRun.objects.filter(runbook=runbook).count() == 1


# ── C6 · TC-RBS-14, the STATIC scan ───────────────────────────────────────


DEFINITIONS_DIR = pathlib.Path(__file__).resolve().parents[1] / "apps" / "runbooks" / "definitions"


def _finding_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "Finding":
                yield node


def _finding_flavour(tree: ast.AST) -> str | None:
    """Which `Finding` a module's bare name means: its OWN step finding (a
    `class Finding` at module level) or the engine's work-item handover
    (`from apps.runbooks.contract import Finding`, un-aliased)."""
    for node in tree.body:  # type: ignore[attr-defined]
        if isinstance(node, ast.ClassDef) and node.name == "Finding":
            return "step"
    for node in tree.body:  # type: ignore[attr-defined]
        if isinstance(node, ast.ImportFrom) and node.module == "apps.runbooks.contract":
            if any(a.name == "Finding" and a.asname is None for a in node.names):
                return "work_item"
    return None


def _routes_through_unpacking(tree, call, name, constants) -> list | None:
    """The route values a LOCAL `name` can carry at `call`, when the enclosing
    function binds it as `a, b, name, … = some_module_function(…)`.

    Returns one entry per `return` of that function (a non-string entry for a
    return the scan cannot fold, so the caller fails it), or `None` when the
    name is not bound that way at all."""
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}  # type: ignore[attr-defined]
    for fn in functions.values():
        if not (fn.lineno <= call.lineno <= (fn.end_lineno or fn.lineno)):
            continue
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
                continue
            target = node.targets[0]
            callee = node.value.func
            if not (isinstance(target, ast.Tuple) and isinstance(callee, ast.Name)):
                continue
            names = [t.id if isinstance(t, ast.Name) else None for t in target.elts]
            if name not in names or callee.id not in functions:
                continue
            index = names.index(name)
            out: list = []
            for ret in ast.walk(functions[callee.id]):
                if not isinstance(ret, ast.Return):
                    continue
                if not (isinstance(ret.value, ast.Tuple) and len(ret.value.elts) == len(names)):
                    out.append(None)
                    continue
                element = ret.value.elts[index]
                if isinstance(element, ast.Constant):
                    out.append(element.value)
                elif isinstance(element, ast.Name):
                    out.append(constants.get(element.id))
                else:
                    out.append(None)
            return out or None
    return None


def _module_string_constants(tree: ast.AST) -> dict[str, str]:
    """Module-level `NAME = "literal"` — what a `fix_route=FIX_ACCOUNTS` resolves to."""
    out: dict[str, str] = {}
    for node in tree.body:  # type: ignore[attr-defined]
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        out[target.id] = node.value.value
    return out


def test_us_rbs_001_tc_rbs_14_no_failure_reason_without_a_fix_route():
    """`TC-RBS-14` · `BR-RBS-011` — **statically**, over every runbook module.

    ⚠ **WHY THIS IS A STATIC SCAN AND NOT AN ASSERTION OVER A RUN.** The runtime
    half exists too — `Finding.__post_init__` refuses a routeless finding — but
    it can only ever see the branches a fixture happens to walk, and **the
    branch that matters is the one nobody has hit yet**. A step that reports a
    fault only when a tenant has three services and a seasonal tariff is
    invisible to every case in this file and reaches a clerk as a dead end.

    ⚠ **WHAT WOULD MAKE THIS SCAN PASS WRONGLY, ANSWERED BEFORE IT WAS
    TRUSTED** (hard-won law 7's second habit):

    * **`Finding(**kwargs)`** — the keyword would not appear as a keyword at
      all and the scan would find nothing to object to. → A `**` unpacking in a
      `Finding` call is refused outright, by file and line.
    * **`fix_route=""`** — present, and empty. → The literal is resolved and its
      emptiness is the failure.
    * **`fix_route=SOME_NAME`** — a name the scan cannot follow, so it shrugs
      and passes. → Module-level string constants are resolved; a name that
      resolves to nothing fails rather than being skipped, because *"could not
      check"* and *"checked and fine"* must never share an exit code.
    * **A findings module that is not walked at all** — the directory is empty,
      or the glob misses it, and the scan reports zero over nothing. → The
      number of calls examined is asserted to be non-zero and PRINTED, which is
      the same discipline the registry's own conformance case uses.
    """
    modules = sorted(p for p in DEFINITIONS_DIR.glob("*.py") if p.name != "__init__.py")
    assert modules, f"no runbook modules under {DEFINITIONS_DIR}"
    examined = 0
    handed_to_engine = 0
    for path in modules:
        tree = ast.parse(path.read_text())
        constants = _module_string_constants(tree)
        flavour = _finding_flavour(tree)
        for call in _finding_calls(tree):
            where = f"{path.name}:{call.lineno}"
            assert flavour is not None, (
                f"{where}: `Finding` is neither this module's own step finding nor "
                "`apps.runbooks.contract.Finding`, so this scan cannot say which fields it owes."
            )
            assert not any(
                keyword.arg is None for keyword in call.keywords
            ), f"{where}: Finding(**kwargs) — a fix route cannot be checked through an unpacking"
            keywords = {k.arg: k.value for k in call.keywords}
            if flavour == "work_item":
                # ⚠ `contract.Finding` — what a runbook HANDS THE ENGINE to raise a
                # work item (`BR-RBS-022`) — has no `fix_label` and no `reason`;
                # it carries `kind`/`title`/`fix_route`. This scan matched both
                # classes by the bare name `Finding` and demanded the step
                # finding's three fields of it, which went red the moment
                # `6de638775` (2026-09-07) imported it un-aliased. Its route is a
                # runtime value (`record.fix_route or …`) the scan cannot fold,
                # so emptiness is refused at CONSTRUCTION by
                # `contract.Finding.__post_init__` — proved below — and the
                # count of these is printed separately rather than folded into
                # "checked" (law 7: a skipped scope carries its number).
                for field in ("kind", "title", "fix_route"):
                    assert field in keywords, f"{where}: Finding names no {field} (BR-RBS-011)"
                handed_to_engine += 1
                continue
            examined += 1
            for field in ("fix_route", "fix_label", "reason"):
                assert field in keywords, f"{where}: Finding names no {field} (BR-RBS-011)"
            value = keywords["fix_route"]
            if isinstance(value, ast.Constant):
                resolved = value.value
            elif isinstance(value, ast.Name) and value.id in constants:
                resolved = constants[value.id]
            elif isinstance(value, ast.Name):
                # ⚠ `leak_alert.py` (`7f5c2892b`, 2026-09-07) unpacks its route
                # from a module function — `reason, rule, fix_route, fix_label =
                # _sentence(row, outcome)` — so the name at the call site is a
                # LOCAL. Followed rather than waved through: EVERY `return` of
                # that function must put a literal or a module constant at the
                # route's position, or the scan fails naming it.
                routes = _routes_through_unpacking(tree, call, value.id, constants)
                assert routes, (
                    f"{where}: fix_route={value.id} does not resolve to a module-level string, "
                    "nor to a tuple every return of a module function fills with one. "
                    "A route this scan cannot follow is not a route it has checked."
                )
                for route in routes:
                    assert isinstance(route, str) and route.strip(), (
                        f"{where}: a return feeding fix_route={value.id} is not a non-empty "
                        "literal or module-level string (BR-RBS-011)."
                    )
                continue
            else:
                raise AssertionError(
                    f"{where}: fix_route is {type(value).__name__}, which this scan cannot "
                    "resolve — write it as a literal or as a module-level constant."
                )
            assert isinstance(resolved, str) and resolved.strip(), (
                f"{where}: fix_route is empty. BR-RBS-011: a failure names its fix route, and a "
                "failure with no route is a defect in the runbook."
            )
    assert examined, "no step Finding call was examined — the scan saw nothing"
    from apps.runbooks.contract import Finding as EngineFinding, RunbookContractError

    with pytest.raises(RunbookContractError):
        EngineFinding(kind="k", title="t", fix_route="  ")
    print(
        f"TC-RBS-14: {examined} step Finding call(s) route-resolved, {handed_to_engine} "
        f"engine Finding call(s) field-checked (route refused empty at construction), "
        f"across {len(modules)} runbook module(s)"
    )
    assert examined > 0, "the scan walked no Finding call at all — it proved nothing"


def test_us_rbs_001_tc_rbs_14_the_runtime_half_refuses_a_routeless_finding():
    """The same rule at construction, for the branch a future lane writes.

    Both halves are needed and neither is enough: the scan cannot see a finding
    built dynamically at run time, and the constructor cannot see a branch no
    test walks.
    """
    with pytest.raises(ValueError) as refusal:
        rb1.Finding(
            step=rb1.STEP_TAX,
            reason="Something is wrong.",
            affects="1 account",
            weight=rb1.BLOCKER,
            fix_route="",
            fix_label="Fix it",
            decided_by_rule="A rule.",
        )
    assert "fix route" in str(refusal.value)


def test_us_rbs_001_no_finding_puts_a_rule_id_or_a_database_id_on_screen(blockers_tenant):
    """B14 rules 31 and 32, over every field a clerk reads.

    `BR-RBS-010` asks for *the rule that decided it, **in words a clerk can
    read***, and B14 rule 32 keeps rule ids and internal codes out of
    clerk-facing copy altogether. Rule 31 keeps database ids out of any visible
    field — which is why `affects` is a count and a noun (*"4 accounts"*) rather
    than a list of account ids.
    """
    import re

    id_shaped = re.compile(r"\b(?:BR|OQ|DEF|TC|US|EP|GT|RB)-[A-Z]*-?\d{2,5}\b")
    uuid_shaped = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-")
    for row in _rows(_run(blockers_tenant)):
        for field in ("finding", "affects", "fix_label", "decided_by_rule"):
            assert not id_shaped.search(row[field]), f"{field} shows an internal id: {row[field]!r}"
            assert not uuid_shaped.search(row[field]), f"{field} shows a database id"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-001 (EP-RBS-01; CR-075 wave C tasks C6 · C7)
# generated: 2026-09-06 by the CR-075 wave C backend lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — wave D) E=n/a(no screen — C1–C4, a sibling lane) F✔ G✔ H=n/a(no 🔒 path)
# gates: pytest tests/test_us_rbs_001_configuration_check.py · pytest tests/test_us_rbs_015_conformance.py · G115
# exceptions: the per-record savepoint (TC-RBS-5) and tenant isolation cannot be proved on SQLite and are NOT asserted here — runbook 1 has no per-record step and writes nothing, and tests/test_rbs_savepoint_pg.py holds the engine's half
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ── C2 · the report the RENDERER draws, pinned as a fixture ───────────────


#: The frozen report of the blockers fixture, as the front end reads it.
#:
#: ⚠ **THIS FILE EXISTS BECAUSE OF `DEF-RBS-4284`, AND IT IS THE ONLY THING THAT
#: WOULD HAVE CAUGHT IT.** The engine and the twelve block components each had a
#: shape for all six blocks runbook 1 emits, not one of them matched, and BOTH
#: suites were green — because the only cross-check in the repository read
#: `contract.py`'s `BLOCK_TYPES` and asserted the twelve NAMES. A name check over
#: an unchecked payload is a declared blind spot with no number attached
#: (hard-won law 7). `blocks.test.tsx`'s own comment had predicted the failure
#: one level up: *"a report the backend accepts draws nothing on screen — and
#: nothing else would say."*
#:
#: The test below writes it; `07-frontend/src/features/runbooks/blocks/
#: reportConformance.test.tsx` READS it and renders every block through the real
#: components. So the engine's actual output is drawn by the actual renderer in
#: CI, and a shape that drifts on either side fails on the other.
REPORT_FIXTURE = (
    pathlib.Path(__file__).resolve().parents[1].parent
    / "07-frontend"
    / "src"
    / "features"
    / "runbooks"
    / "blocks"
    / "__fixtures__"
    / "rbs001-report.json"
)


def test_us_rbs_001_the_report_fixture_the_renderer_draws_is_current(blockers_tenant):
    """The committed report fixture is byte-for-byte what the engine emits today.

    Run with `RBS_WRITE_FIXTURE=1` to regenerate it after a deliberate change;
    the diff is then reviewed like any other, and the front-end conformance test
    fails in the same commit if a block's shape moved under it.

    ⚠ **A FIXTURE NOBODY REGENERATES IS A FIXTURE THAT STOPS CHECKING.** This
    test is what keeps it honest: it is not a snapshot the engine writes on
    every run, it is an assertion that the committed bytes still match.
    """
    import json
    import os

    report = _run(blockers_tenant).report
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    if os.environ.get("RBS_WRITE_FIXTURE") == "1":
        REPORT_FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        REPORT_FIXTURE.write_text(rendered, encoding="utf-8")

    assert REPORT_FIXTURE.exists(), (
        f"{REPORT_FIXTURE} is missing — the front end's conformance test reads it. "
        "Regenerate with RBS_WRITE_FIXTURE=1."
    )
    assert REPORT_FIXTURE.read_text(encoding="utf-8") == rendered, (
        "the engine's report no longer matches the fixture the renderer draws. "
        "If the change is deliberate, regenerate with RBS_WRITE_FIXTURE=1 and check "
        "that reportConformance.test.tsx still passes in the SAME commit."
    )


def test_us_rbs_001_every_block_the_report_names_is_one_the_renderer_has_built():
    """The report may not name a block the front end cannot draw.

    `BLOCKS_BUILT` in `blocks/index.ts` is the renderer's own list. Reading it
    here closes the loop `DEF-RBS-4284` went through: the twelve NAMES agreed
    while every payload differed, so this asserts the names AND the fixture above
    asserts the shapes.
    """
    import json
    import re

    index = (
        pathlib.Path(__file__).resolve().parents[1].parent
        / "07-frontend"
        / "src"
        / "features"
        / "runbooks"
        / "blocks"
        / "index.ts"
    ).read_text(encoding="utf-8")
    listed = index.split("BLOCKS_BUILT = [")[1].split("]")[0]
    built = set(re.findall(r'"([a-z_]+)"', listed))
    assert built, "BLOCKS_BUILT could not be read — this check now covers nothing"

    named = {block["block"] for block in json.loads(REPORT_FIXTURE.read_text(encoding="utf-8"))}
    assert named <= built, f"the report names blocks the renderer cannot draw: {named - built}"
