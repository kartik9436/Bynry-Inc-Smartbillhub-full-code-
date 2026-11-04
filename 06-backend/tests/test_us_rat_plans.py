# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-001 (Plans list tab, S9) · US-RAT-002 (New Plan guided wizard,
#           S10) · US-RAT-003 (plan lifecycle, versioning & category targeting)
# Rules:    BR-RAT-012/027 (per-service base; plan base DERIVED) · BR-RAT-024
#           (services ⊆ tenant-enabled) · BR-RAT-025 (plan-as-bundle) ·
#           BR-RAT-030 (draft → published → archived) · BR-RAT-037 (version +1
#           with a required reason, append-only log) · BR-RAT-039 (staff
#           assignment only) · BR-RAT-043 (discounts = negative charge rules,
#           budget-billing flag, advisory eligibility) · BR-RAT-017
# Note:     RLS halves of every isolation TC run in the G5 suite on Postgres —
#           sqlite cannot enforce RLS, so the app-filter half is asserted here
#           and the RLS half carries @pytest.mark.isolation + @requires_postgres
#           (DEF-101, 2026-08-15: these were BARE pytest.mark.skip for months,
#           so the pricing module had no cross-tenant read proof on ANY database
#           while the suite reported green — a skipped test is green).
# ───────────────────────────────────────────────────────
"""US-RAT-001 / US-RAT-002 / US-RAT-003 — Plans tab, wizard and lifecycle."""

from decimal import Decimal

import pytest

from apps.rating import api, models, selectors, services
from core import errors
from core.pagination import ListParams

from tests.isolation_helpers import (  # noqa: F401 — fixtures resolved by name
    assert_denied_without_context,
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import (
    RES_ELECTRIC_TIERS,
    RES_WATER_TIERS,
    FakeUser,
    api_call,
    audit_actions,
    seeding_ctx,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _seed_catalog(env):
    """The §4 Brazos Bend seed, trimmed to what the list TCs assert."""
    electric = env.tiered_schedule("Res Electric · Tiered", "electric", RES_ELECTRIC_TIERS)
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    commercial = env.flat_schedule("Comm Water · Flat", "water", "2.90")
    env.charge("CONN", "Connection fee", amount="85.00")
    residential = env.plan(
        "Residential Standard",
        "RES-STD",
        [
            {"service": "electric", "base_charge": "18.50", "tariff": electric["id"]},
            {"service": "water", "base_charge": "12.00", "tariff": water["id"]},
        ],
        publish=True,
    )
    small_commercial = env.plan(
        "Small Commercial",
        "COM-SM",
        [
            {"service": "electric", "base_charge": "36.00", "tariff": electric["id"]},
            {"service": "water", "base_charge": "12.00", "tariff": commercial["id"]},
        ],
        publish=True,
    )
    standby = env.plan(
        "Vacant / Standby",
        "STBY",
        [
            {"service": "electric", "base_charge": "10.00", "tariff": electric["id"]},
            {"service": "water", "base_charge": "5.00", "tariff": water["id"]},
        ],
    )
    return {
        "electric": electric,
        "water": water,
        "commercial": commercial,
        "residential": residential,
        "small_commercial": small_commercial,
        "standby": standby,
    }


def _params(**kwargs):
    return ListParams(**{"sort": "name", "dir": "asc", **kwargs})


# ── US-RAT-001 — Plans list tab ─────────────────────────────────────────────
def test_us_rat_001_tc1__list_renders_derived_bases_and_rollup(env):
    seed = _seed_catalog(env)
    with tenant_ctx(env.tenant):
        rows = selectors.plan_list(_params())
        rollup = selectors.rating_rollup()
    assert [row["name"] for row in rows] == [
        "Residential Standard",
        "Small Commercial",
        "Vacant / Standby",
    ]  # default sort name asc
    residential = next(row for row in rows if row["id"] == seed["residential"]["id"])
    # ⚠ **`$20.00`, NOT `$30.50` — `BR-RAT-1040` (PO ruling 2026-09-27,
    # verbatim *"a is good"*), closing `DEF-RAT-6927`.** `$30.50` was
    # `18.50 + 12.00`, the plan's own `plan_services.base_charge` values — the
    # column `BR-RAT-088` retired on 2026-08-20 when the CHARGE CODE took the
    # base over. `$20.00` is `$12.00` electric + `$8.00` water, the signed
    # figures in `core.sample_fixture` (`[W] §1 "Base/mo … Water $8 · Electric
    # $12"`) that this fixture's own base charge codes carry — and what a bill
    # for this plan would actually charge. **On a live tenant the old figure
    # read `$0.00` on every plan**, because every plan written since that
    # ruling leaves the retired column NULL; here it read a number, which is
    # the same bug wearing better clothes.
    assert Decimal(residential["base_charges"]) == Decimal("20.00"), residential["base_charges"]
    assert residential["base_charges_unavailable"] is None
    assert sorted(residential["services"]) == ["electric", "water"]
    # AMENDED 2026-08-21 (DEF-443). The line counts SIX things now, not three.
    # PO: "Summary line has 3 counts, r10 has 6 - missing discounts, taxes &
    # fees, contracts." The whole dict is asserted rather than the added keys,
    # so a future widening cannot land unnoticed.
    assert rollup == {
        "plans": 3,
        "rate_schedules": 3,
        # THREE: `CONN`, and the `BASE-E` and `BASE-W` this fixture declares
        # because activating the two schedules needs them (BR-RAT-088 /
        # DEF-2965). It read 1 — only `CONN` — from before the fixture
        # declared base codes; red since then, brought up to date 2026-10-01
        # (CR-157-BRC10 wave B). Still exact, so a code that appears or goes
        # missing turns it red.
        "charge_codes": 3,
        "discounts": 0,
        "taxes": 0,
        # ⚠ `None`, not `0`. CR-020 is deferred by the PO and there is no
        # contracts table, so this says THE PRODUCT holds no contracts. A `0`
        # would tell this tenant THEY have none, which is a claim about their
        # data that nothing in the product can support.
        "contracts": None,
        "effective_from": "2026-08-01",
    }


def test_def_443__the_rollup_counts_the_discounts_and_taxes_this_tenant_configured(env):
    """DEF-443 — the two counts that were missing, proven non-zero.

    The assertion above pins them at 0 on a catalogue that configures neither,
    which passes just as well against a hard-coded zero. This one configures one
    of each and is what actually shows the counts are counting.
    """
    _seed_catalog(env)
    env.tax("TX State Utility Tax", rate="0.0625")
    with tenant_ctx(env.tenant):
        rollup = selectors.rating_rollup()
    assert rollup["taxes"] == 1
    assert rollup["contracts"] is None  # still deferred; not silently zeroed


def test_us_rat_001_tc2__filter_status_draft_returns_only_the_draft(env):
    _seed_catalog(env)
    with tenant_ctx(env.tenant):
        rows = selectors.plan_list(_params(filters={"status": "draft"}))
    assert [row["name"] for row in rows] == ["Vacant / Standby"]


def test_us_rat_001_tc3__search_matches_name_server_side(env):
    _seed_catalog(env)
    with tenant_ctx(env.tenant):
        rows = selectors.plan_list(_params(q="commercial"))
    assert [row["name"] for row in rows] == ["Small Commercial"]


def test_us_rat_001_tc4__sort_by_accounts_desc(env):
    seed = _seed_catalog(env)
    env.assign(seed["residential"]["id"], env.unit("Unit A"))
    env.assign(seed["residential"]["id"], env.unit("Unit B"))
    env.assign(seed["small_commercial"]["id"], env.unit("Unit C"))
    with tenant_ctx(env.tenant):
        rows = selectors.plan_list(_params(sort="accounts", dir="desc"))
    assert [(row["name"], row["accounts"]) for row in rows][0] == ("Residential Standard", 2)


def test_us_rat_001_tc5__hard_delete_audit_locked_while_accounts_exist(env):
    seed = _seed_catalog(env)
    env.assign(seed["residential"]["id"], env.unit("Unit A"))
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as excinfo:
            services.delete_plan(env.admin, seed["residential"]["id"])
        assert models.RatePlan.objects.filter(pk=seed["residential"]["id"]).exists()
    assert excinfo.value.code == errors.BIZ_LOCKED  # IS-1: archive instead
    assert excinfo.value.params["accounts"] == 1


def test_us_rat_001_tc6__clerk_reads_but_a_forged_post_is_refused(env):
    _seed_catalog(env)
    user = FakeUser(env.owner.id)
    read = api_call(api.plans, "get", user=user, role="billing_clerk", tenant=env.tenant)
    assert read.status_code == 200
    forged = api_call(
        api.plans,
        "post",
        user=user,
        role="billing_clerk",
        tenant=env.tenant,
        data={"name": "Forged", "code": "FORGE", "services": []},
    )
    assert forged.status_code == 403  # A4 / BR-IDN-009 — server-enforced
    assert forged.data["code"] == errors.AUTH_PERMISSION_DENIED


def test_us_rat_001_tc7__lone_star_ridge_sees_only_its_own_plans(env, other_env):
    _seed_catalog(env)
    other_env.plan("Co-op Water Basic", "COOP-W", [{"service": "water", "base_charge": "9.00"}])
    with tenant_ctx(other_env.tenant):
        rows = selectors.plan_list(_params())
    assert [row["name"] for row in rows] == ["Co-op Water Basic"]


PLAN_TABLES = ("rate_plans", "plan_services", "plan_rate_schedules")


@pytest.mark.isolation
@requires_postgres
def test_us_rat_001_tc7_rls__plan_rows_invisible_cross_tenant(env, other_env, rls):  # noqa: F811
    """US-RAT-001 TC-7 at the DATABASE, with the app-layer filter out of the path.

    The app half above (`..._lone_star_ridge_sees_only_its_own_plans`) proves
    the SELECTOR filters. This proves the POLICY does, under a non-superuser
    probe role — the two are different guarantees and only this one survives a
    selector that forgets its `tenant=` clause. Sort/search permutations are
    deliberately NOT re-run here: RLS applies to the relation, not the ORDER BY,
    so the id-guessing probe (`count(... WHERE id = <foreign id>)` = 0) covers
    every permutation at once.
    """
    seed = _seed_catalog(env)
    other_plan = other_env.plan(
        "Co-op Water Basic", "COOP-W", [{"service": "water", "base_charge": "9.00"}]
    )

    assert_rls_scoped(
        rls,
        "rate_plans",
        owner=env.tenant,
        intruder=other_env.tenant,
        owner_ids={str(seed["residential"]["id"]), str(seed["small_commercial"]["id"])},
    )
    assert_rls_scoped(rls, "plan_services", owner=env.tenant, intruder=other_env.tenant)

    # Knowing the id is not access: the intruder names the row and still sees nothing.
    with live_tenant_context(other_env.tenant.id):
        assert rls.count("rate_plans", "id = %s", [str(seed["residential"]["id"])]) == 0
        assert rls.ids("rate_plans") == {str(other_plan["id"])}
    assert_no_foreign_rows_anywhere(rls, other_env.tenant, PLAN_TABLES)


@pytest.mark.isolation
@requires_postgres
def test_us_rat_001_tc7_rls__plans_are_denied_outright_with_no_tenant_context(  # noqa: F811
    env, rls
):
    """CLAUDE.md hard rule 1: absence of tenant context is never 'see everything'.

    With `app.tenant_id` unset the policy's `::uuid` cast of '' fails and the
    query ERRORS — deny-by-default, not filter-by-default.
    """
    _seed_catalog(env)
    assert_denied_without_context(rls, *PLAN_TABLES)


@pytest.mark.isolation
@requires_postgres
def test_us_rat_001_tc7_rls__a_write_into_another_tenants_plans_is_refused(  # noqa: F811
    env, other_env, rls
):
    """WITH CHECK, not just USING — knowing a neighbour's tenant_id is not enough
    to stamp one of your own plan rows with it and hand them your pricing."""
    _seed_catalog(env)
    other_env.plan("Co-op Water Basic", "COOP-W", [{"service": "water", "base_charge": "9.00"}])
    assert_write_into_other_tenant_refused(
        rls, "rate_plans", owner=env.tenant, intruder=other_env.tenant
    )


# ── US-RAT-002 — New Plan guided wizard ─────────────────────────────────────
def _residential_account_type_id(env):
    """This tenant's OWN `residential` account type, as a real row's id.

    ⚠ **THIS USED TO READ `str(env.owner.id)` — THE OWNER USER'S ID, HANDED IN
    AS A CONSUMER CATEGORY (`DEF-RAT-6783`, 2026-09-25).** It was harmless while
    `plan_deposit_rules.account_type_id` was a bare `UUIDField` pointing at
    nothing, and `services._validate_plan_deposit_rules` checks the shape of a
    uuid and never that it names a row. `rating/0044` (2026-09-24) made the
    column a real `DEFERRABLE INITIALLY DEFERRED` foreign key into
    `account_types`, so from that day every PostgreSQL run of a case built from
    this payload died — not at the INSERT, which a deferred constraint accepts,
    but at the end of the transaction, which pytest reports as an **ERROR in
    teardown** attached to a case that passed. `test_us_rat_003_tc7_rls` was one
    of the two errors in the 2026-09-25 isolation proof, and an error is a case
    nobody can say anything about.

    **The default suite never saw it and cannot**: `ALTER TABLE … ADD
    CONSTRAINT` does not exist on SQLite, which is what `config/settings/test.py`
    pins, so the foreign key is simply absent there (CLAUDE.md law 14's shape).

    `account_types` is TENANT-OWNED and seeded with eight rows per tenant
    (`BR-CUS-1079`, PO ruling 2026-09-17), so a real id is one query away and
    the payload stops asserting anything about ids that name nothing.
    """
    from apps.customers import models as customers_models

    # `seeding_ctx`, not `tenant_ctx`: this is called from inside a test's own
    # `with tenant_ctx(...)` in several cases, and `tenant_ctx` CLEARS on exit
    # (`DEF-2761`) — which would leave the rest of that test with no tenant and
    # `create_plan` raising `AUTH-003`. Measured: it did, on the first draft of
    # this helper. `seeding_ctx` saves and puts back.
    with seeding_ctx(env.tenant):
        return str(
            customers_models.AccountType.objects.filter(code="residential").values_list(
                "id", flat=True
            )[0]
        )


def _wizard_payload(env, seed, **overrides):
    payload = {
        "name": "Residential Standard",
        "code": "RES-STD",
        "description": "Electric + water residential bundle",
        "services": [
            {"service": "electric", "base_charge": "18.50", "tariff": seed["electric"]["id"]},
            {"service": "water", "base_charge": "12.00", "tariff": seed["water"]["id"]},
        ],
        "charge_rules": [{"charge": "CONN", "recurrence": "once", "taxable": False}],
        "deposit_rules": [
            {"account_type_id": _residential_account_type_id(env), "amount": "150.00"}
        ],
        "effective_from": "2026-09-01",
    }
    payload.update(overrides)
    return payload


def _wizard_seed(env):
    electric = env.tiered_schedule("Res Electric · Tiered", "electric", RES_ELECTRIC_TIERS)
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    env.charge("CONN", "Connection fee", amount="85.00")
    return {"electric": electric, "water": water}


def test_us_rat_002_tc1__wizard_commit_writes_the_whole_bundle_atomically(env, audit_rows):
    seed = _wizard_seed(env)
    tax = env.tax("TX State Utility Tax", rate="0.0625")
    payload = _wizard_payload(
        env,
        seed,
        tax_rules=[{"jurisdiction": tax["jurisdiction"]["id"]}],
    )
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload)
        plan = services.publish_plan(env.admin, plan["id"])
    assert plan["status"] == "published" and plan["version"] == 1
    assert len(plan["services"]) == 2 and len(plan["rate_schedules"]) == 2
    assert len(plan["charge_rules"]) == 1 and len(plan["deposit_rules"]) == 1
    assert len(plan["tax_rules"]) == 1
    # BR-RAT-1040 — the review step shows the base the CHARGE CODES state
    # ($12.00 electric + $8.00 water), not the Σ of the retired
    # `plan_services.base_charge` column ($18.50 + $12.00). DEF-RAT-6927.
    assert Decimal(plan["base_charges"]) == Decimal("20.00"), plan["base_charges"]
    assert "plan.published" in audit_actions(audit_rows)


def test_us_rat_002_tc2__untouched_penalty_panel_writes_no_row(env):
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, _wizard_payload(env, seed))
        assert (
            models.PlanPenaltyRule.objects.filter(rate_plan_id=plan["id"]).exists() is False
        )  # r5 #10 fallback: tenant defaults apply at billing time
    assert plan["penalty_rule"] is None


def test_us_rat_002_tc3__save_draft_persists_and_stays_out_of_published_pickers(env):
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, _wizard_payload(env, seed))
        published = selectors.plan_list(_params(filters={"status": "published"}))
    assert plan["status"] == "draft"  # BR-RAT-030: drafts are never billed
    assert plan["id"] not in [row["id"] for row in published]


def test_us_rat_002_tc4__disabled_service_is_refused_by_the_server(env):
    seed = _wizard_seed(env)
    payload = _wizard_payload(
        env, seed, services=[{"service": "gas", "base_charge": "10.00"}]
    )  # Gas is not enabled for Brazos Bend (BR-RAT-024)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_plan(env.admin, payload)
    assert excinfo.value.code == errors.VAL_UNKNOWN_LOOKUP
    assert excinfo.value.field_errors[0]["message_key"] == "rating.service_not_enabled"


def test_us_rat_002_tc5__publish_blocked_when_a_service_has_no_schedule(env):
    seed = _wizard_seed(env)
    payload = _wizard_payload(
        env,
        seed,
        services=[
            {"service": "electric", "base_charge": "18.50", "tariff": seed["electric"]["id"]},
            {"service": "water", "base_charge": "12.00"},  # D2 violation
        ],
    )
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload)
        with pytest.raises(errors.BizError) as excinfo:
            services.publish_plan(env.admin, plan["id"])
        assert selectors.plan_detail(plan["id"])["status"] == "draft"  # nothing published
    assert excinfo.value.code == errors.BIZ_COMPLETENESS
    assert excinfo.value.params["services"] == ["water"]


def test_us_rat_002_tc6__negative_base_charge_is_refused(env):
    seed = _wizard_seed(env)
    payload = _wizard_payload(env, seed, services=[{"service": "electric", "base_charge": "-5.00"}])
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_plan(env.admin, payload)
    assert excinfo.value.code == errors.VAL_RANGE
    assert excinfo.value.field_errors[0]["field"] == "services[0].base_charge"


def test_us_rat_002_tc7__duplicate_plan_name_is_rejected(env):
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        services.create_plan(env.admin, _wizard_payload(env, seed))
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_plan(env.admin, _wizard_payload(env, seed, code="RES-STD-2"))
    assert excinfo.value.field_errors[0]["message_key"] == "rating.plans.duplicate_name"


def test_us_rat_002_tc8__cross_tenant_schedule_is_never_selectable(env, other_env):
    seed = _wizard_seed(env)
    foreign = other_env.flat_schedule("Co-op Water Flat", "water", "3.10")
    payload = _wizard_payload(
        env, seed, services=[{"service": "water", "base_charge": "12.00", "tariff": foreign["id"]}]
    )
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_plan(env.admin, payload)
    assert excinfo.value.field_errors[0]["message_key"] == "rating.plans.unknown_schedule"


@pytest.mark.isolation
@requires_postgres
def test_us_rat_002_tc8_rls__pickers_are_rls_scoped(env, other_env, rls):  # noqa: F811
    """US-RAT-002 TC-8 at the DATABASE: every wizard picker source is scoped.

    The app half proves `create_plan` REFUSES a foreign tariff id with
    `rating.plans.unknown_schedule`. That refusal is a selector lookup returning
    nothing — so it depends on the app filter. This asserts the three picker
    tables themselves (tariffs, charges, tax_jurisdictions) are invisible
    cross-tenant at the policy level, which is what makes the refusal survive a
    selector that loses its `tenant=` clause.
    """
    seed = _wizard_seed(env)
    env.tax("TX State Utility Tax", rate="0.0625")
    other_env.flat_schedule("Co-op Water Flat", "water", "3.10")
    other_env.charge("COOP", "Co-op fee", amount="7.00")
    other_env.tax("Hays County", jurisdiction={"name": "Hays County", "level": "county"})

    for table in ("tariffs", "charges", "tax_jurisdictions"):
        assert_rls_scoped(rls, table, owner=env.tenant, intruder=other_env.tenant)

    # The exact id the app half refuses is also unreadable at the database.
    with live_tenant_context(other_env.tenant.id):
        assert rls.count("tariffs", "id = %s", [str(seed["electric"]["id"])]) == 0
    assert_denied_without_context(rls, "tariffs", "charges", "tax_jurisdictions")


def test_us_rat_002_tc9__discounts_are_negative_charge_rules_and_budget_billing_is_a_flag(
    env, audit_rows
):
    seed = _wizard_seed(env)
    env.charge("PAPERLESS", "Paperless discount", charge_type="recurring", amount="2.00")
    env.charge("AUTOPAY", "Autopay discount", charge_type="recurring", amount="3.00")
    payload = _wizard_payload(
        env,
        seed,
        charge_rules=[
            {"charge": "PAPERLESS", "amount_override": "-2.00", "recurrence": "recurring"},
            {"charge": "AUTOPAY", "amount_override": "-3.00", "recurrence": "recurring"},
        ],
        budget_billing=True,
        eligibility={"cap_subsidy": True},  # ADVISORY — never blocks (BR-RAT-043)
    )
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload)
    overrides = sorted(Decimal(rule["amount_override"]) for rule in plan["charge_rules"])
    assert overrides == [Decimal("-3.00"), Decimal("-2.00")]
    assert plan["budget_billing"] is True
    # US-RAT-002 §5: the CAP box is STORED ON THE PLAN (rate_plans.eligibility)
    # and rides the plan snapshot into the audit row (advisory-WITH-audit).
    assert plan["eligibility"] == {"cap_subsidy": True}
    created = next(row for row in audit_rows if row["action"] == "plan.created")
    assert created["after"]["eligibility"] == {"cap_subsidy": True}
    # BR-RAT-039: no self-serve/zone availability field exists anywhere.
    assert "available_for_new_signup" not in plan


# ── US-RAT-003 — lifecycle, versioning & category targeting ─────────────────
def test_us_rat_003_tc1__content_edit_bumps_version_and_logs_before_after(env, audit_rows):
    seed = _wizard_seed(env)
    sewer_schedule = None
    env.enable("sewer")
    sewer_schedule = env.flat_schedule("Sewer · Flat", "sewer", "8.00", uom="kgal")
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, _wizard_payload(env, seed))
        plan = services.publish_plan(env.admin, plan["id"])
    unit = env.unit("Unit A")
    env.assign(plan["id"], unit, plan_version=plan["version"])
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        updated = services.update_plan(
            env.admin,
            plan["id"],
            {
                "services": [
                    {
                        "service": "electric",
                        "base_charge": "18.50",
                        "tariff": seed["electric"]["id"],
                    },
                    {"service": "water", "base_charge": "12.00", "tariff": seed["water"]["id"]},
                    {"service": "sewer", "base_charge": "8.00", "tariff": sewer_schedule["id"]},
                ],
                "reason": "council resolution 2026-41",
            },
        )
        log = models.RateChangeLog.objects.get(entity_id=plan["id"])
    assert updated["version"] == plan["version"] + 1
    assert sorted(updated["services"], key=lambda row: row["service"])[1]["service"] == "sewer"
    assert log.reason == "council resolution 2026-41" and log.actor_id == env.owner.id
    assert len(log.before["services"]) == 2 and len(log.after["services"]) == 3
    assert (
        models.UnitPlanAssignment.objects.get(unit=unit).plan_version == plan["version"]
    )  # BR-CUS-013 snapshot untouched
    assert "plan.version_created" in audit_actions(audit_rows)


def test_us_rat_003_tc2__reassignment_snapshots_the_new_version_append_only(env):
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, _wizard_payload(env, seed))
        plan = services.publish_plan(env.admin, plan["id"])
        services.update_plan(
            env.admin, plan["id"], {"description": "revised", "reason": "council resolution"}
        )
    unit = env.unit("Unit A")
    first = env.assign(plan["id"], unit, plan_version=1)
    first.assigned_to = TODAY  # noqa: F405 — the customers seam closes the row
    first.save(update_fields=["assigned_to"])
    second = env.assign(plan["id"], unit, plan_version=2)
    assert models.UnitPlanAssignment.objects.filter(unit=unit).count() == 2  # append-only
    assert (first.plan_version, second.plan_version) == (1, 2)


def test_us_rat_003_tc3__archiving_a_zero_account_draft_keeps_it_visible_under_archived(env):
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(
            env.admin, _wizard_payload(env, seed, name="Vacant / Standby", code="STBY")
        )
        archived = services.archive_plan(env.admin, plan["id"])
        published = selectors.plan_list(_params(filters={"status": "published"}))
        archived_rows = selectors.plan_list(_params(filters={"status": "archived"}))
    assert archived["status"] == "archived"
    assert plan["id"] not in [row["id"] for row in published]
    assert [row["id"] for row in archived_rows] == [plan["id"]]


def test_us_rat_003_tc4__publishing_a_draft_writes_the_audit_row(env, audit_rows):
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, _wizard_payload(env, seed))
        audit_rows.clear()
        published = services.publish_plan(env.admin, plan["id"])
    assert (plan["status"], published["status"]) == ("draft", "published")
    assert "plan.published" in audit_actions(audit_rows)


def test_us_rat_003_tc5__edit_without_a_reason_is_blocked_before_anything_is_written(env):
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, _wizard_payload(env, seed))
        plan = services.publish_plan(env.admin, plan["id"])
        # ⚠ AMENDED 2026-10-03 (`BR-RAT-1067`, PO ruling 1 of the plans
        # redesign): a DESCRIPTION is name-and-details and saves on the same
        # version with no reason; the gate now holds for a PRICE, refused by
        # name before anything is written.
        with pytest.raises(errors.ValidationError) as excinfo:
            services.update_plan(env.admin, plan["id"], {"minimum_bill_amount": "12.00"})
        after = selectors.plan_detail(plan["id"])
        assert models.RateChangeLog.objects.count() == 0
    assert excinfo.value.message_key == "rating.plans.field_needs_new_version"
    assert (after["version"], after["description"]) == (1, plan["description"])


def test_us_rat_003_tc6__the_change_log_has_no_mutation_path_anywhere(env):
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, _wizard_payload(env, seed))
        services.publish_plan(env.admin, plan["id"])
        services.update_plan(env.admin, plan["id"], {"description": "v2", "reason": "audit"})
    # r5 #14 append-only: no service function and no route can amend a row.
    assert not [
        name for name in dir(services) if "rate_change_log" in name or name.endswith("_log_update")
    ]
    assert [
        route.pattern._route for route in api.urlpatterns if "rate-changes" in route.pattern._route
    ] == ["rate-changes"]
    response = api_call(
        api.rate_changes,
        "patch",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={"reason": "tampered"},
    )
    assert response.status_code == 405


def test_us_rat_003_tc7__history_rows_are_tenant_scoped(env, other_env):
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, _wizard_payload(env, seed))
        services.publish_plan(env.admin, plan["id"])
        services.update_plan(env.admin, plan["id"], {"description": "v2", "reason": "audit"})
    with tenant_ctx(other_env.tenant):
        rows = selectors.history_list(_params(dir="desc", sort="changed_at"))
    assert rows == []


@pytest.mark.isolation
@requires_postgres
def test_us_rat_003_tc7_rls__history_is_rls_scoped(env, other_env, rls):  # noqa: F811
    """US-RAT-003 TC-7 at the DATABASE: the append-only rate_change_log is scoped.

    `rate_change_log` is the 7-year reproducibility record (BR-RAT-017/037) — it
    holds the before/after money of every price change. A History filter that
    lost its tenant clause would show one utility what its neighbour charges.
    Filter permutations are not re-enumerated: the policy is on the relation, so
    the id-guessing probe covers all of them.
    """
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, _wizard_payload(env, seed))
        services.publish_plan(env.admin, plan["id"])
        services.update_plan(env.admin, plan["id"], {"description": "v2", "reason": "audit"})

    other_seed = other_env.flat_schedule("Co-op Water Flat", "water", "3.10")
    with tenant_ctx(other_env.tenant):
        other_plan = services.create_plan(
            other_env.admin,
            {
                "name": "Co-op Water Basic",
                "code": "COOP-W",
                "services": [
                    {"service": "water", "base_charge": "9.00", "tariff": other_seed["id"]}
                ],
                # ⚠ BR-RAT-890 (PO ruling 2026-08-28, closing DEF-494): a rate
                # plan CANNOT be published without a start date. `publish_plan`
                # refuses an undated plan, and that refusal is the product
                # working — an undated published plan bills FOREVER through
                # `selectors.plan_ref`, which consults no date, while
                # `PlanVersion.in_force_on` says it is in force NEVER. This
                # payload predates the rule; `_wizard_payload` (the Brazos side
                # of the same case) has carried a date all along.
                "effective_from": "2026-09-01",
            },
        )
        services.publish_plan(other_env.admin, other_plan["id"])
        services.update_plan(
            other_env.admin, other_plan["id"], {"description": "v2", "reason": "co-op board"}
        )

    assert_rls_scoped(rls, "rate_change_log", owner=env.tenant, intruder=other_env.tenant)
    assert_no_foreign_rows_anywhere(rls, other_env.tenant, ("rate_change_log",))
    assert_denied_without_context(rls, "rate_change_log")


# ── US-RAT-002 §5 — plan eligibility storage (schema-gap fix) ───────────────
def test_us_rat_002_tc9_eligibility__round_trips_on_the_plan_and_survives_reload(env):
    """US-RAT-002 §5 stores the step-5 boxes ON THE PLAN — before the
    rate_plans.eligibility column they vanished on reload."""
    seed = _wizard_seed(env)
    boxes = {"cap_proof": True, "min_demand_kw": 25, "owner_occupied": False}
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, _wizard_payload(env, seed, eligibility=boxes))
        reloaded = selectors.plan_detail(plan["id"])
        stored = models.RatePlan.objects.get(pk=plan["id"]).eligibility
    assert plan["eligibility"] == boxes
    assert reloaded["eligibility"] == boxes  # the reload the gap broke
    assert stored == boxes  # …because it is a column now, not an audit-only echo


def test_us_rat_002_tc9_eligibility__edit_lands_in_the_audit_before_and_after(env, audit_rows):
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(
            env.admin, _wizard_payload(env, seed, eligibility={"cap_proof": True})
        )
        services.publish_plan(env.admin, plan["id"])
        audit_rows.clear()
        services.update_plan(
            env.admin,
            plan["id"],
            {"eligibility": {"cap_proof": False}, "reason": "CAP program ended"},
        )
    # ⚠ AMENDED 2026-10-03 (`BR-RAT-1067`): the intended-for ticks are name and
    # details — saved on the SAME version, so the row is `plan.details_updated`.
    logged = next(row for row in audit_rows if row["action"] == "plan.details_updated")
    assert logged["before"]["eligibility"] == {"cap_proof": True}
    assert logged["after"]["eligibility"] == {"cap_proof": False}


def test_us_rat_002_tc9_eligibility__never_blocks_assignment(env):
    """BR-RAT-043: advisory ONLY. A plan whose every box is unticked still
    publishes and still takes an assignment — nothing reads it as a gate."""
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(
            env.admin,
            _wizard_payload(env, seed, eligibility={"cap_proof": False, "owner_occupied": False}),
        )
        published = services.publish_plan(env.admin, plan["id"])
    assert published["status"] == "published"
    assignment = env.assign(plan["id"], env.unit("Unit E"))
    assert assignment.rate_plan_id == plan["id"]
    with tenant_ctx(env.tenant):
        assert selectors.plan_detail(plan["id"])["accounts"] == 1


def test_us_rat_002_tc9_eligibility__defaults_to_an_empty_map(env):
    seed = _wizard_seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, _wizard_payload(env, seed))
    assert plan["eligibility"] == {}


def test_us_rat_002_tc5_picker__a_draft_schedule_cannot_be_attached_to_a_plan(env):
    """BR-RAT-031: drafts are excluded from plan-builder pickers until
    activated — the picker list and the write path agree."""
    # BR-RAT-088 / DEF-2965: activation needs the service's base charge code, declared
    # the way the utility would (red on 9910f15a8, CR-156-BRC10 wave A, and every tip since;
    # fixture brought up to date 2026-10-01, CR-157-BRC10 wave B).
    env._base_codes_for_activation("water")
    with tenant_ctx(env.tenant):
        activated = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Inclining",
                "service": "water",
                "model": "tiered",
                "effective_from": "2026-08-01",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        draft = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Draft",
                "service": "water",
                "model": "tiered",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
        picker = selectors.plan_builder_schedules("water")
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_plan(
                env.admin,
                {
                    "name": "Draft-backed",
                    "code": "DRAFTY",
                    "services": [
                        {"service": "water", "base_charge": "12.00", "tariff": draft["id"]}
                    ],
                },
            )
    assert [row["id"] for row in picker] == [activated["id"]]
    assert excinfo.value.field_errors[0]["message_key"] == "rating.plans.draft_schedule"
    with tenant_ctx(env.tenant):
        assert models.RatePlan.objects.filter(code="DRAFTY").exists() is False


# ── DEF-RAT-5693 · an ARCHIVED schedule is refused AS ARCHIVED ───────────────
#
# PO ruling 2026-09-17, verbatim: *"so dont allow archive plans to be selected
# in plans - only active rates schedule should be selected"*.
#
# The picker half is `selectableSchedules` in `PlanWizard.tsx`. This is the
# server half, and the fix here is the WORD rather than the refusal: an archived
# schedule was already refused, with `rating.plans.unknown_schedule` — *"We
# don't recognise that rate schedule"* — said to somebody who picked the value
# off a list the product had just given them. The id resolves; the row is
# archived; the message must say so.
def test_def_rat_5693__archived_schedule_is_refused_as_archived_not_unknown(env):
    seed = _wizard_seed(env)
    retired = env.flat_schedule("Retired Water — Flat 2025", "water", "4.80")
    with tenant_ctx(env.tenant):
        services.archive_rate_schedule(env.admin, retired["id"])
        payload = _wizard_payload(
            env,
            seed,
            services=[{"service": "water", "base_charge": "12.00", "tariff": retired["id"]}],
        )
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_plan(env.admin, payload)
    error = excinfo.value.field_errors[0]
    assert error["message_key"] == "rating.plans.archived_schedule"
    # The plan is still refused — this changes the WORD, never the gate.
    with tenant_ctx(env.tenant):
        assert models.RatePlan.objects.filter(code=payload["code"]).exists() is False


def test_def_rat_5693__a_genuinely_unknown_id_keeps_the_unknown_wording(env):
    """The CONTROL. A refusal that said *archived* for every bad id would pass
    the case above and be a worse message than the one it replaced."""
    seed = _wizard_seed(env)
    payload = _wizard_payload(
        env,
        seed,
        services=[
            {
                "service": "water",
                "base_charge": "12.00",
                "tariff": "01a0b071-0000-7000-8000-000000000000",
            }
        ],
    )
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.create_plan(env.admin, payload)
    assert excinfo.value.field_errors[0]["message_key"] == "rating.plans.unknown_schedule"
