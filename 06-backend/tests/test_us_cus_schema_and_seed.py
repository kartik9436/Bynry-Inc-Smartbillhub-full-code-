# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-001 (EP-CUS-01 Accounts list — TC-7 isolation half, and the
#           BR-CUS-055 status vocabulary the S17 pill renders) · US-CUS-003
#           (EP-CUS-02 New Account wizard — TC-1's row set, TC-8 isolation
#           half) · US-TEN-002 (reference-data seeding) · US-TEN-009 (the S8
#           card grid)   Screens: S17 · S18 · S8
# Rules:    BR-CUS-055 (five seeded statuses + behaviour classes; PO OQ-058(b),
#           class seed OQ-064 CLOSED) · BR-CUS-016 (status from the lookup) ·
#           BR-CUS-017 (one account ↔ one unit) · BR-TEN-012 (per-list
#           idempotent; tenant-touched rows never overwritten) · BR-TEN-013
#           (a module writes only its own tables) · BR-TEN-031 (owner validates
#           + supplies the /lookups handler) · BR-TEN-036 (seeded rows
#           deactivatable, never deletable) · BR-TEN-065 (the sample-data job
#           needs `Pending activation` to exist) · BR-TEN-030 (codes unique per
#           list per tenant, case-insensitive)
# Note:     The RLS cases carry @pytest.mark.isolation and skip with a VENDOR
#           reason off Postgres (tests/isolation_helpers.py explains why they
#           run under a non-superuser probe role). Each was proved RED against
#           a live database with the customers policies dropped before being
#           trusted green — transcripts in the lane report (Hard-won law 7).
# ───────────────────────────────────────────────────────
"""W2 customers SCHEMA + SEAM slice — the reference-data seam and the RLS half.

Two things are proved here that nothing else can prove:

1. **The seam actually seeds.** `account_statuses` was the last entry standing
   in `apps.tenancy.services.UNSEEDABLE_REFERENCE_LISTS`, and it BLOCKED
   BR-TEN-065 (a sample account must be created `Pending activation`). These
   tests assert the five ratified rows land, with the ratified behaviour
   classes, idempotently, without overwriting a tenant's rename.

2. **The policies are real.** A new tenant table with no isolation test is not
   done. The RLS cases run under `sbh_rls_probe` (NOLOGIN NOSUPERUSER
   NOBYPASSRLS) so the assertions cannot pass vacuously the way they would on
   the app's own superuser connection.
"""

import importlib
import json
from pathlib import Path

import pytest

from apps.customers import lookups as customers_lookups
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.tenancy import api as tenancy_api
from apps.tenancy import models as tenancy_models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import errors

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    iso_tenants,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    FakeUser,
    admin_actor,
    api_call,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

FIXTURE = json.loads(Path(tenancy_services.FIXTURE_PATH).read_text(encoding="utf-8"))

#: The tenant-scoped customers tables that carry ENABLE+FORCE. Six from
#: migration `customers.0002`, and `account_types` makes SEVEN since
#: `customers.0055` (PO ruling 2026-09-17: *"utility can get their own account
#: types"*). ⚠ **IT WAS DELIBERATELY ABSENT AND THAT IS THE WHOLE CHANGE** —
#: `0002`'s own comment says *"FIVE tables, not six"* because r5 #12 [D5] made
#: `account_types` PLATFORM with no `tenant_id` to test.
CUSTOMERS_TENANT_TABLES = (
    "account_types",
    "account_subtypes",
    "account_statuses",
    "accounts",
    "contacts",
    "addresses",
    "service_agreements",
)


# ══════════════════════════════════════════════════════════════════════════
# Helpers — the smallest row set an account needs (metering rows come from
# metering's own models; customers never WRITES them, it only points at them)
# ══════════════════════════════════════════════════════════════════════════
def _unit_for(tenant, label="Unit A"):
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line="1408 Elm St", city="Katy", state="TX"
    )
    return metering_models.Unit.objects.create(tenant=tenant, premises=premises, label=label)


def _service_point_for(tenant, unit, service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    return metering_models.ServicePoint.objects.create(tenant=tenant, unit=unit, service=service)


def _account_for(tenant, *, account_no="A-10432", status_code="active", unit=None):
    """One account, wired to the seeded status + platform type."""
    status = customers_models.AccountStatus.objects.get(tenant=tenant, code=status_code)
    account_type = customers_models.AccountType.objects.get(code="residential")
    return customers_models.Account.objects.create(
        tenant=tenant,
        unit=unit or _unit_for(tenant),
        account_no=account_no,
        status=status,
        account_type=account_type,
    )


# ══════════════════════════════════════════════════════════════════════════
# US-CUS-001 — the BR-CUS-055 vocabulary lands, exactly as ratified
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_001_tc1__provisioning_seeds_the_five_ratified_statuses(growth_plan, identity_seam):
    """BR-CUS-055, CONFIRMED 2026-08-08 (PO OQ-058 option b; class seed OQ-064
    CLOSED). Five rows, five behaviour classes, verbatim.

    RED before this lane: the customers module owned no tables and authored no
    seam, so `_seed_reference_data` skipped the list and the count was 0.

    ⚠ **THIS ASSERTED FIVE UNTIL 2026-08-25 AND NOW ASSERTS SIX — BR-CUS-107**
    (PO ruling closing DEF-701), which AMENDS BR-CUS-055 by adding
    `disconnected` / "Disconnected" / `non_billable`: the state a CUT account is
    in, which the five could not express. The test NAME is left alone
    deliberately — renaming it would lose the link to US-CUS-001's TC-1 that
    G10 reads — and the sentence above says what changed instead.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = {
            row.code: row for row in customers_models.AccountStatus.objects.filter(tenant=tenant)
        }
    assert set(rows) == {
        "pending_activation",
        "active",
        "marked_disconnect",
        "vacation_hold",
        "closed",
        # BR-CUS-107 (2026-08-25) — the sixth. See its own suite,
        # tests/test_br_cus_107_disconnected_status.py.
        "disconnected",
    }
    assert rows["pending_activation"].behavior_class == "non_billable"
    assert rows["active"].behavior_class == "billable"
    # "consuming until cut" — billable, NOT base-only (OQ-064 closure).
    assert rows["marked_disconnect"].behavior_class == "billable"
    assert rows["vacation_hold"].behavior_class == "billable_base_only"
    assert rows["closed"].behavior_class == "terminal"
    # BR-CUS-107 — a cut account is NOT billable (the service no longer runs),
    # NOT base-only (BR-CUS-103 stops base at the cut, so there is no base to
    # bill) and NOT terminal (it holds a debt, it can pay, and it comes back).
    assert rows["disconnected"].behavior_class == "non_billable"
    assert rows["disconnected"].name == "Disconnected"
    assert rows["vacation_hold"].name == "Vacation hold/Suspended"
    # BR-TEN-036: every seeded row is is_system — deactivatable, never deletable.
    assert all(row.is_system for row in rows.values())


def test_us_cus_001_tc1__br_ten_065_is_unblocked_pending_activation_exists(
    growth_plan, identity_seam
):
    """The named consequence: BR-TEN-065's sample-data job must create its
    sample account `Pending activation`. Until this seam existed there was
    nowhere for that row to live, which is exactly what the
    UNSEEDABLE_REFERENCE_LISTS entry said."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        pending = customers_models.AccountStatus.objects.get(
            tenant=tenant, code="pending_activation"
        )
        account = _account_for(tenant, account_no="A-SAMPLE", status_code="pending_activation")
    assert account.status_id == pending.id
    assert pending.behavior_class == "non_billable"  # a sample account is never billed


def test_us_cus_001_tc1__the_fixture_and_the_module_constants_are_one_law():
    """One source of law, three copies, pinned equal.

    The platform fixture, `apps/customers/services.SEED_ACCOUNT_STATUSES` and
    (for types) the migration's own copy all repeat BR-CUS-055 / r5 #12 [D5].
    Duplication is deliberate — a migration must survive a later constant
    change — and this is what stops the copies drifting."""
    ratified_statuses = [
        {"code": code, "name": name, "behavior_class": behavior_class}
        for code, name, behavior_class in customers_services.SEED_ACCOUNT_STATUSES
    ]
    assert FIXTURE["account_statuses"] == ratified_statuses

    ratified_types = [
        {"code": code, "name": name} for code, name in customers_services.SEED_ACCOUNT_TYPES
    ]
    assert FIXTURE["account_types"] == ratified_types
    migration = importlib.import_module("apps.customers.migrations.0003_seed_account_types")
    assert migration.SEED_ACCOUNT_TYPES == customers_services.SEED_ACCOUNT_TYPES


def test_us_cus_001_tc1__account_types_are_platform_rows_seeded_by_the_migration():
    """The consumer categories exist BEFORE any tenant does, identically for all
    of them.

    ⚠ **THIS ASSERTED FOUR UNTIL 2026-08-24 AND NOW ASSERTS EIGHT ROWS —
    BR-CUS-094, which SUPERSEDES B2 r5 #12 [D5]'s four-code list.** PO verbatim:
    *"Expand the signed list to seven"*. Migration 0003 seeded the original four
    and is not edited (migrations are append-only); migration 0019 adds
    `agricultural`, `institutional`, `municipal` and `builder_developer`, and
    flags `government` LEGACY rather than re-labelling it — *"Municipal and
    Institutional are both plausible readings of it ... So no row is re-labelled
    by guess."*

    So the table holds **eight rows: the seven selectable plus one legacy**, and
    `government` keeps its `Government` name and its `active` flag (a legacy
    code is still a valid FK, still filterable, still priceable)."""
    codes = list(
        customers_models.AccountType.objects.order_by("code").values_list("code", flat=True)
    )
    assert codes == [
        "agricultural",
        "builder_developer",
        "commercial",
        "government",
        "industrial",
        "institutional",
        "municipal",
        "residential",
    ]
    legacy = list(
        customers_models.AccountType.objects.filter(legacy=True).values_list("code", flat=True)
    )
    assert legacy == ["government"]
    assert customers_models.AccountType.objects.get(code="government").active is True
    assert not tenancy_models.Tenant.objects.exists(), (
        "the platform rows must be present with NO tenant in the database — that is "
        "what makes them platform rows rather than a per-tenant seed"
    )


def test_us_cus_001_tc4__a_replay_writes_nothing_and_never_overwrites_a_rename(
    growth_plan, identity_seam
):
    """BR-TEN-012: per-list idempotent, and a tenant-touched row survives.

    A tenant that renames "Vacation hold/Suspended" to its own vocabulary must
    not have it silently reset by the next backfill."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        hold = customers_models.AccountStatus.objects.get(tenant=tenant, code="vacation_hold")
        hold.name = "Snowbird hold"
        hold.save(update_fields=["name", "updated_at"])
        # Force the list to be reconsidered the way a backfill does.
        tenancy_models.ReferenceSeedRun.objects.filter(
            tenant=tenant, list_code="account_statuses"
        ).delete()
        summary = tenancy_services.seed_reference_data_for_tenant(tenant, admin_actor())
        hold.refresh_from_db()
        count = customers_models.AccountStatus.objects.filter(tenant=tenant).count()
    assert summary["seeded"] == {"account_statuses": 0}  # every row already there
    assert hold.name == "Snowbird hold"
    # 5 → 6 on 2026-08-25: BR-CUS-107 adds `disconnected` (non_billable).
    assert count == 6


def test_us_cus_001_tc6__statuses_are_seeded_per_tenant_not_shared(growth_plan, identity_seam):
    """The lookup is TENANT-scoped (unlike account_types): two tenants get two
    independent row sets, and a rename in one is invisible in the other."""
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=True))
    with tenant_ctx(brazos):
        brazos_ids = set(
            customers_models.AccountStatus.objects.filter(tenant=brazos).values_list(
                "id", flat=True
            )
        )
    with tenant_ctx(lonestar):
        lonestar_ids = set(
            customers_models.AccountStatus.objects.filter(tenant=lonestar).values_list(
                "id", flat=True
            )
        )
    # 5 → 6 on 2026-08-25: BR-CUS-107 adds `disconnected` (non_billable).
    assert len(brazos_ids) == len(lonestar_ids) == 6
    assert not (brazos_ids & lonestar_ids)


# ══════════════════════════════════════════════════════════════════════════
# US-CUS-001 / US-TEN-009 — the two S8 cards can finally be COUNTED
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_001_tc1__both_customers_cards_render_with_live_counts(growth_plan, identity_seam):
    """BR-TEN-029/031. Before this lane the registry carried both lists with
    `handler=None`, so the cards were absent and `reference_data_report()`
    could only answer "unwired" — a list can be seeded and STILL look missing
    if nothing can count it."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        cards = {card["list"]: card for card in tenancy_selectors.lookup_cards()}
    # Hard-won law 2 — "built is not wired". Registering a handler is only half
    # the story; this drives tenancy's REAL endpoint so the S8 card is proven
    # reachable over HTTP, not just from the service layer.
    listing = api_call(
        tenancy_api.lookups,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        list_code="account_statuses",
    )
    assert listing.status_code == 200
    served = {row["code"]: row for row in listing.data["results"]}
    assert served["vacation_hold"]["behavior_class"] == "billable_base_only"
    types = api_call(
        tenancy_api.lookups,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=tenant,
        list_code="account_types",
    )
    assert types.status_code == 200
    # ⚠ EIGHT since BR-CUS-094 (PO 2026-08-24): the seven selectable categories
    # plus the legacy `government`, which the S8 card still LISTS because a
    # legacy code stays filterable and priceable. ⚠ **The card does not yet
    # publish the `legacy` flag** — `AccountTypeLookupHandler` is another
    # module's file, so a picker built against `/lookups/account_types` will
    # still offer `government`. REPORTED by the CR-031 surface lane, which
    # serves the split list at `GET /service-requests/categories`.
    assert {row["code"] for row in types.data["results"]} == {
        "residential",
        "commercial",
        "industrial",
        "agricultural",
        "institutional",
        "municipal",
        "builder_developer",
        "government",
    }
    # 5 → 6 on 2026-08-25: BR-CUS-107 adds `disconnected` (non_billable).
    assert cards["account_statuses"]["count"] == 6
    assert cards["account_statuses"]["owner"] == "customers"
    assert cards["account_types"]["count"] == 8
    assert cards["account_types"]["owner"] == "customers"


def test_us_cus_001_tc1__no_reference_list_is_unexplained_or_empty_any_more(
    growth_plan, identity_seam
):
    """DEF-016's guard. ⚠ AMENDED 2026-08-18 — this test asserted a state the
    product deliberately LEFT on 2026-08-16 and had been red ever since.

    It read *"nothing is UNEXPLAINED **and** nothing is empty, so the register
    is empty too"*, which was true the day it was written. On 2026-08-16, under
    PO delegation (*"meaningful and relevant data - decide for me"*, decision
    log that date), `import_mappings` was REGISTERED in
    `UNSEEDABLE_REFERENCE_LISTS` with a written reason: an import mapping maps
    the tenant's OWN file's columns, so a seeded one would describe a file
    layout this tenant does not have.

    Registering it is precisely what DEF-016's guard asks for — *"a reference
    list may not be quietly absent"* — and a registered list is reported as
    `empty`/`unwired` WITH its reason rather than as `UNEXPLAINED`. So the
    signal that must stay clean is `unexplained`, and it does.

    The assertion is therefore SHARPENED, not loosened: `unexplained` must
    still be empty (that is the machine-checkable one `seed_demo` exits
    non-zero on), and `empty` must contain EXACTLY the lists somebody wrote a
    reason for — asserting the two sets are equal, so a list going quietly
    absent still goes red, and so does a reason written for a list that is not
    actually empty.

    ⚠ AMENDED AGAIN 2026-08-22 (CR-028 AST-W3-T8): BR-AST-048 superseded the
    2026-08-16 empty-list half for `import_mappings` — each assets import
    target now seeds ONE GENERATED system default template, so the list is no
    longer empty and its register entry came OUT (which is what removing an
    entry looks like). The register is empty again, and both signals stay
    machine-checked."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        report = tenancy_services.reference_data_report()
    assert report["unexplained"] == []
    assert sorted(report["empty"]) == sorted(tenancy_services.UNSEEDABLE_REFERENCE_LISTS)
    assert set(tenancy_services.UNSEEDABLE_REFERENCE_LISTS) == set()


def test_us_cus_001_tc3__a_tenant_may_add_its_own_status_with_a_behaviour_class(
    growth_plan, identity_seam
):
    """BR-CUS-055 tenant-extensible (US-CUS-020 TC-3 maps legacy `LGL` onto a
    tenant-added "Legal hold"). The class is REQUIRED — billing keys off the
    class, never the label."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        created = tenancy_services.create_lookup_entry(
            admin_actor(),
            "account_statuses",
            {"code": "legal_hold", "name": "Legal hold", "behavior_class": "non_billable"},
        )
        assert created["is_system"] is False
        assert created["behavior_class"] == "non_billable"
        # BR-CUS-055 names exactly four classes; a fifth is refused, not stored.
        with pytest.raises(errors.ValidationError) as excinfo:
            tenancy_services.create_lookup_entry(
                admin_actor(),
                "account_statuses",
                {"code": "weird", "name": "Weird", "behavior_class": "sort_of_billable"},
            )
        assert excinfo.value.code == errors.VAL_UNKNOWN_LOOKUP
        # BR-TEN-030: the code is unique per tenant, case-insensitively.
        with pytest.raises(errors.ValidationError):
            tenancy_services.create_lookup_entry(
                admin_actor(),
                "account_statuses",
                {"code": "ACTIVE", "name": "Active again", "behavior_class": "billable"},
            )


def test_us_cus_001_tc5__a_seeded_status_is_deactivatable_but_never_deletable(
    growth_plan, identity_seam
):
    """BR-TEN-036. `used_by` is honestly 0 today (nothing writes accounts yet),
    so BR-TEN-034's used-row lock cannot bite — this one still does."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = customers_models.AccountStatus.objects.get(tenant=tenant, code="closed")
        handler = customers_lookups.AccountStatusLookupHandler()
        assert handler.used_by(row) == 0
        handler.set_active(row, False)
        row.refresh_from_db()
        assert row.active is False
        with pytest.raises(errors.BizError) as excinfo:
            handler.delete(row)
        assert excinfo.value.code == errors.BIZ_LOCKED


def test_us_cus_003_tc1__the_account_types_card_is_read_only_because_it_is_platform(
    growth_plan, identity_seam
):
    """r5 #12 [D5]. One tenant admin editing a PLATFORM row would be editing
    every other tenant's vocabulary, so every write REFUSES with that reason
    rather than quietly succeeding."""
    tenant, _ = provisioned_tenant()
    handler = customers_lookups.AccountTypeLookupHandler()
    with tenant_ctx(tenant):
        row = customers_models.AccountType.objects.get(code="government")
        assert handler.serialize(row)["name"] == "Government"  # readable
        for call in (
            lambda: handler.create({"code": "coop", "name": "Co-op"}),
            lambda: handler.update(row, {"name": "Municipal"}),
            lambda: handler.set_active(row, False),
            lambda: handler.delete(row),
        ):
            with pytest.raises(errors.BizError) as excinfo:
                call()
            assert excinfo.value.code == errors.BIZ_LOCKED
    # Seven selectable + one legacy = eight (BR-CUS-094). The platform table is
    # still READ-ONLY to a tenant admin, which is what this test is about: not
    # one of the four writes above created, renamed, deactivated or deleted a
    # row, and `government` is still named "Government".
    assert customers_models.AccountType.objects.count() == 8


# ══════════════════════════════════════════════════════════════════════════
# US-CUS-003 — the S18 row set is storable (the SCHEMA half of TC-1)
# ══════════════════════════════════════════════════════════════════════════
def test_us_cus_003_tc1__account_contact_address_and_agreement_persist_together(
    growth_plan, identity_seam
):
    """US-CUS-003 TC-1's storage half: "account + contacts + addresses rows +
    service_agreements rows". The WIZARD is the account-CRUD slice; what this
    asserts is that the tables it will write actually hold the row set, wired
    to the metering unit and service point through the B2 §2 reviewed FKs."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        unit = _unit_for(tenant)
        account = _account_for(tenant, account_no="A-12048", unit=unit)
        customers_models.Contact.objects.create(
            tenant=tenant,
            account=account,
            full_name="Elena Rivera",
            email="elena.rivera@example.com",
            gov_id_last4="4218",
        )
        customers_models.Address.objects.create(
            tenant=tenant, account=account, kind="mailing", line1="1408 Elm St"
        )
        agreement = customers_models.ServiceAgreement.objects.create(
            tenant=tenant,
            account=account,
            service_point=_service_point_for(tenant, unit),
            started_on="2026-08-15",
        )
        assert account.unit_id == unit.id
        assert account.contact_set.count() == 1
        assert account.address_set.count() == 1
        assert agreement.ended_on is None  # NULL = still in force
        assert account.balance == 0 and account.currency == "USD"


def test_us_cus_003_tc1__account_number_is_unique_within_a_tenant_only(growth_plan, identity_seam):
    """B2 §4 ux_accounts_no. The SAME account number in another tenant is a
    different account, not a collision."""
    from django.db import IntegrityError, transaction

    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=True))
    with tenant_ctx(brazos):
        _account_for(brazos, account_no="A-10432")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _account_for(brazos, account_no="A-10432")
    with tenant_ctx(lonestar):
        twin = _account_for(lonestar, account_no="A-10432")
        assert twin.account_no == "A-10432"


# ══════════════════════════════════════════════════════════════════════════
# RLS — the G5 half. Live Postgres, non-superuser probe role.
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
@requires_postgres
def test_us_cus_001_tc7_rls__accounts_are_invisible_across_tenants(growth_plan, identity_seam, rls):
    """US-CUS-001 TC-7, the database half: under Lone Star Ridge's context,
    Brazos Bend's account is not filtered out of a result set — it is never in
    one, and its id cannot be guessed into visibility.

    Proved RED by dropping `accounts_tenant_isolation` on the live database:
    the probe then sees BOTH tenants' rows and this fails naming the leak.
    """
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=True))
    with live_tenant_context(brazos.id):
        secret = _account_for(brazos, account_no="A-10432")
    with live_tenant_context(lonestar.id):
        mine = _account_for(lonestar, account_no="A-20011")

    assert_rls_scoped(rls, "accounts", owner=brazos, intruder=lonestar, owner_ids={str(secret.id)})
    with live_tenant_context(lonestar.id):
        # id-guessing: the attack that survives a missing app-layer filter.
        assert rls.count("accounts", "id = %s", [str(secret.id)]) == 0
        assert rls.ids("accounts") == {str(mine.id)}
    assert_write_into_other_tenant_refused(rls, "accounts", owner=brazos, intruder=lonestar)


@pytest.mark.isolation
@requires_postgres
def test_us_cus_003_tc8_rls__the_whole_customers_row_set_is_scoped(growth_plan, identity_seam, rls):
    """US-CUS-003 TC-8: every table the wizard writes, not just `accounts`.

    A policy on the parent row is not a policy on its children — `contacts`
    carries the PII (BR-CUS-045) and `service_agreements` carries the service
    history, and each needs its own FORCE policy. Proved RED table by table.
    """
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=True))
    owned = {}
    with live_tenant_context(brazos.id):
        unit = _unit_for(brazos)
        account = _account_for(brazos, account_no="A-10432", unit=unit)
        owned["contacts"] = customers_models.Contact.objects.create(
            tenant=brazos, account=account, full_name="Sarah Miller", dob="1991-03-18"
        )
        owned["addresses"] = customers_models.Address.objects.create(
            tenant=brazos, account=account, line1="1408 Elm St"
        )
        owned["service_agreements"] = customers_models.ServiceAgreement.objects.create(
            tenant=brazos,
            account=account,
            service_point=_service_point_for(brazos, unit),
            started_on="2026-08-15",
        )
        owned["account_subtypes"] = customers_models.AccountSubtype.objects.create(
            tenant=brazos, code="submetered", name="Sub-metered"
        )
    with live_tenant_context(lonestar.id):
        _account_for(lonestar, account_no="A-20011")

    for table, row in owned.items():
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar, owner_ids={str(row.id)})
        assert_write_into_other_tenant_refused(rls, table, owner=brazos, intruder=lonestar)


@pytest.mark.isolation
@requires_postgres
def test_us_cus_001_tc7_rls__account_statuses_are_scoped_and_deny_without_context(
    growth_plan, identity_seam, rls
):
    """The reference list is tenant data too — a tenant's added "Legal hold"
    must not appear in another tenant's status select (US-CUS-020 TC-6).

    Also the deny-by-default half (HR-1): with `app.tenant_id` unset the
    `::uuid` cast of '' fails and the table answers nothing at all, for every
    customers tenant table.
    """
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=True))
    with live_tenant_context(brazos.id):
        brazos_ids = set(
            str(pk)
            for pk in customers_models.AccountStatus.objects.filter(tenant=brazos).values_list(
                "id", flat=True
            )
        )
    assert_rls_scoped(
        rls,
        "account_statuses",
        owner=brazos,
        intruder=lonestar,
        owner_ids=brazos_ids,
        min_owner_rows=5,
    )
    assert_denied_without_context(rls, *CUSTOMERS_TENANT_TABLES)


@pytest.mark.isolation
@requires_postgres
def test_po_20260917_rls__account_types_are_the_tenants_own_and_not_shared(
    growth_plan, identity_seam, rls
):
    """⚠ **THIS TEST ASSERTED THE EXACT OPPOSITE UNTIL 2026-09-17, AND IT IS
    REWRITTEN RATHER THAN DELETED.**

    It was called `..._account_types_are_platform_and_shared_on_purpose` and it
    pinned two things: that `account_types` had NO `tenant_id` column, and that
    two tenants really did see the same eight rows. Both were true and both were
    the r5 #12 [D5] posture. **The PO reversed it** — *"utility can get their own
    account types"* — so the test that guarded the old world now guards the new
    one, at the same point in the file, keeping the history in view. Deleting it
    would have removed the only place that ever asked this question out loud.

    What it pins now, and each half is the mirror of a half it used to pin:

      · the column EXISTS and is NOT NULL — `0002`'s own comment predicted this
        day in as many words (*"account_types grew a tenant_id — it now NEEDS an
        RLS policy"*);
      · the policy is read back from `pg_class`/`pg_policy` rather than trusted
        because the migration ran, with `rowsecurity`, `forcerowsecurity` AND
        both the `USING` and `WITH CHECK` halves;
      · **two tenants each add a type with the SAME CODE and neither sees the
        other's.** That is the point of the whole change: a code stopped being a
        platform-wide fact, so the per-tenant unique constraint must ACCEPT the
        collision and RLS must hide each row from the other utility.
    """
    from django.db import connection

    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=True))

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'account_types' AND column_name = 'tenant_id'"
        )
        row = cursor.fetchone()
        assert row is not None, (
            "account_types lost its tenant_id — the PO ruling of 2026-09-17 "
            "(*utility can get their own account types*) is being undone"
        )
        assert row[0] == "NO", "account_types.tenant_id must be NOT NULL"

        cursor.execute(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = 'account_types'"
        )
        rowsecurity, forced = cursor.fetchone()
        assert rowsecurity and forced, (
            "account_types must carry ENABLE *and* FORCE row level security — "
            "FORCE is what makes the policy apply to the table owner, which is "
            "the role the app connects as"
        )

        cursor.execute(
            "SELECT pg_get_expr(polqual, polrelid), pg_get_expr(polwithcheck, polrelid) "
            "FROM pg_policy WHERE polrelid = 'account_types'::regclass"
        )
        policies = cursor.fetchall()
        assert len(policies) == 1, f"expected one policy on account_types, found {len(policies)}"
        using_expr, with_check_expr = policies[0]
        for half, expr in (("USING", using_expr), ("WITH CHECK", with_check_expr)):
            assert expr and "app.tenant_id" in expr and "tenant_id =" in expr, (
                f"account_types' {half} half does not test tenant_id against "
                f"app.tenant_id: {expr!r}"
            )

    # ── the seed, per tenant ────────────────────────────────────────────────
    # EIGHT: BR-CUS-094's seven selectable + `government`, kept as a LEGACY row
    # rather than re-labelled ("a city water department and a state university
    # are different things and the stored value cannot tell them apart").
    # Counted from the model's own constants so the next ruling moves this with
    # it instead of leaving a number to rot.
    expected = len(customers_models.AccountType.SEVEN_CATEGORIES) + len(
        customers_models.AccountType.LEGACY_CODES
    )
    assert expected == 8, f"the seeded account-type list is {expected}, not 8 — say so here"
    for tenant in (brazos, lonestar):
        with live_tenant_context(tenant.id):
            assert customers_models.AccountType.objects.filter(tenant=tenant).count() == expected

    # ── TWO TENANTS, ONE CODE, AND NEITHER SEES THE OTHER'S ─────────────────
    added = {}
    for tenant in (brazos, lonestar):
        with live_tenant_context(tenant.id):
            added[tenant.id] = customers_models.AccountType.objects.create(
                tenant=tenant,
                code="marina_berth",
                name=f"Marina berth ({tenant.subdomain})",
                is_system=False,
                active=True,
            )
    assert added[brazos.id].id != added[lonestar.id].id, (
        "both tenants must own a SEPARATE row for the same code — one shared row "
        "would be the platform posture wearing a tenant column"
    )

    brazos_ids = set()
    with live_tenant_context(brazos.id):
        brazos_ids = {
            str(pk)
            for pk in customers_models.AccountType.objects.filter(tenant=brazos).values_list(
                "id", flat=True
            )
        }
    assert_rls_scoped(
        rls,
        "account_types",
        owner=brazos,
        intruder=lonestar,
        owner_ids=brazos_ids,
        min_owner_rows=expected + 1,
    )
    assert_write_into_other_tenant_refused(rls, "account_types", owner=brazos, intruder=lonestar)
    assert_denied_without_context(rls, *CUSTOMERS_TENANT_TABLES)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-001@a2e1d59 (story+rules snapshot — EP-CUS-01 lead story; co-packets EP-CUS-02@bbed56d · customers 02-business-rules@f125a9c)
# generated: 2026-08-10 by story-coder (W2 customers SCHEMA + SEAM slice)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half in this slice — the lists are served through tenancy's /lookups endpoints, exercised here through tenancy's services) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests -m "not golden and not isolation"✔ · pytest tests -m isolation✔ (sqlite tier skips the four RLS cases with a vendor reason) + live-Postgres isolation run✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔
# exceptions: every RLS case was proved RED on live Postgres by dropping the relevant policy before being trusted green (Hard-won law 7) — transcripts in the lane report · US-CUS-001 TC-5 (a second active account on a unit) is NOT asserted here: BR-CUS-017's proposed partial unique index is not constructible once status is a lookup FK, and tests/test_w2_models.py pins that ABSENCE instead so the gap stays visible · used_by counts are honestly 0 while nothing writes `accounts`, so BR-TEN-030/034 cannot be exercised yet
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
