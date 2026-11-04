# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-002 (seed standard reference data from platform fixtures, S111)
# Rules:    BR-TEN-012 (versioned fixtures, per-list idempotent, toggle-gated,
#           tenant-touched rows never overwritten) · BR-TEN-013 (cross-module
#           writes via owning-module service fns only) · BR-TEN-016 ·
#           BR-TEN-067 (CONFIRMED, PO 2026-08-10, OQ-082 — the STRUCTURAL
#           catalogues are EXEMPT from the S111 toggle and always seed; the
#           toggle governs sample content. NARROWS TC-2, which used to assert
#           that every list is empty when the toggle is off) · BR-MET-034
#           (premises types are seeded Reference data — DEF-017's seventh list)
# Journeys: J1 step 3 (reference lists populated per fixtures)
# Note:     charge/reason/payment/tax lists route through DOCUMENTED seams
#           (apps/tenancy/seams.py); their owning lanes are not authored yet,
#           so those TC halves run against stubs — the real-content integration
#           is skip-until-wired. RLS halves = G5 suite.
# ───────────────────────────────────────────────────────
"""US-TEN-002 — reference-data seeding: toggle, idempotency, no-overwrite."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import apps.billing.services as billing_services
import apps.payments.services as payments_services
import apps.rating.services as rating_services
from apps.tenancy import models, reference_sweep, services
from core import errors

#: **HOW MANY UNITS OF MEASURE A FRESHLY PROVISIONED TENANT RECEIVES, READ FROM
#: THE FIXTURE RATHER THAN TYPED (`CR-063`, 2026-09-02).**
#:
#: ⚠ **IT WAS TYPED IN FOUR PLACES IN THIS FILE AND THE ELEVENTH UNIT BROKE ALL
#: FOUR AT ONCE**, with `assert 27 == 26` naming neither the unit that arrived
#: nor the reason. `connection` was added for **fire**, the eleventh utility
#: service (`BR-RAT-024` amended). **A count typed into a test is a second,
#: silent statement about what the product contains** — the catalogue grew and
#: the literals did not.
#:
#: **NOT ONE OF THE FOUR CASES IS ABOUT THIS NUMBER.** They assert that the seed
#: LANDS, that RLS keeps one tenant's list out of another's, that no declared
#: list is silently SKIPPED, and that a fixture-STATED scope beats a derived one.
#: The count is scaffolding in every one, so it is derived here and a TWELFTH
#: unit moves nothing.
#:
#: ⚠ **THIS IS NOT A LICENCE TO DERIVE EVERY COUNT.**
#: `test_cr010_reference_list_inventory.py` states the same figure as a LITERAL
#: on purpose — its job is *"vocabulary cannot change without the record changing
#: with it"*, so a typed number there is what makes a seeded-list change a
#: visible diff somebody approves. The rule is: **derive it where the number is
#: INCIDENTAL, type it where the number IS the assertion.**
SEEDED_UOM_COUNT = len(
    json.loads(Path(services.FIXTURE_PATH).read_text(encoding="utf-8"))["uoms"]
)

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    audit_actions,
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def owner_seams(monkeypatch):
    """Stub seed_reference_list on every owning module (BR-TEN-013 routing)."""
    calls = SimpleNamespace(rating=[], billing=[], payments=[])

    def recorder(bucket):
        def seed_reference_list(list_code, entries, fixture_version):
            bucket.append({"list": list_code, "entries": entries, "version": fixture_version})
            return len(entries)

        return seed_reference_list

    monkeypatch.setattr(
        rating_services, "seed_reference_list", recorder(calls.rating), raising=False
    )
    monkeypatch.setattr(
        billing_services, "seed_reference_list", recorder(calls.billing), raising=False
    )
    monkeypatch.setattr(
        payments_services, "seed_reference_list", recorder(calls.payments), raising=False
    )
    return calls


def test_us_ten_002_tc1__toggle_on_seeds_lists_with_seed_run_records(
    growth_plan, identity_seam, owner_seams, audit_rows
):
    tenant, result = provisioned_tenant()
    # tenancy-owned UoM list — 26 since CR-010 10.2 (PO 2026-08-17 "yes pls");
    # membership is pinned in full by test_cr010_102, so here the six originals
    # plus the size, not a second full copy to drift.
    uoms = models.Uom.objects.filter(tenant=tenant)
    codes = set(uoms.values_list("code", flat=True))
    assert {"kWh", "kW", "kgal", "ccf", "therm", "month"} <= codes
    assert len(codes) == SEEDED_UOM_COUNT
    assert all(row.is_system for row in uoms)
    # cross-module lists routed through the OWNING module's service fn (BR-TEN-013)
    assert [c["list"] for c in owner_seams.rating] == [
        "charge_codes",
        "tax_jurisdictions",
        # CR-166-BRC10 — rating's three discount lists, seeded from its own constant.
        "discount_program_owners",
        "discount_exclusivity_groups",
        "discount_eligibility",
    ]
    tx_entries = owner_seams.rating[1]["entries"]
    # CR-010 tax ruling (a AND b): the state's own rows PLUS the ALL scaffold.
    # Scaffold rows carry no code — the jurisdiction framework matches on NAME
    # (the table has no code column; rating's omissions note says so).
    #
    # ⚠ TX GREW 2 → 5 ON 2026-08-18 (DEF-254/DEF-273, PO ruling: *"Tax
    # jurisdiction rates (5 TX rows) - already answered"*). r10's five ruled
    # rates need five authorities, so the PUC, the City and the Texas Water
    # Development Board join Texas State and Local. `TX-CITY` is deliberately
    # NAMED "City", the same name the ALL scaffold's city row carries, so a
    # Texas tenant ends with ONE city authority carrying the franchise fee
    # rather than two rows meaning the same thing.
    assert {e.get("code") or e["name"] for e in tx_entries} == {
        "TX-STATE",
        "TX-LOCAL",
        "TX-PUC",
        "TX-CITY",
        "TX-TWDB",
        "County",
        "City",
        "Special district",
    }
    assert [c["list"] for c in owner_seams.billing] == ["reason_codes"]
    # CR-059 CS-18 (2026-09-01): payments now owns TWO routed lists. The second
    # is `bank_rec_difference_reasons` — the reconciliation difference reasons,
    # which were free text until today, so nobody could report on cause. Payments
    # is HOSTED for the first and OWNS the table for the second, and both go
    # through the same seam (BR-TEN-013), which is why both appear here.
    assert [c["list"] for c in owner_seams.payments] == [
        "payment_methods",
        "bank_rec_difference_reasons",
    ]
    # one seed-run record per list, fixture version 2026.08. DEF-017 added the
    # four asset catalogs (metering → assets); the W2 customers SCHEMA + SEAM
    # slice (2026-08-10) added the last two; DEF-017's SEVENTH list —
    # `premises_types` — was added on 2026-08-10 and is the reason this set is
    # now 12. It was in neither registry, so the only way a tenant ever got
    # premises types was the side effect of a premises WRITE: no run row, no
    # audit row, and a brand-new tenant whose S16 wizard could not resolve a
    # type. Every declared list now has a wired owner and a run row.
    # ⚠ THE VERSION IS DERIVED, NOT TYPED (DEF-213). Every pair here used to
    # carry the literal `"2026.08"`, and on 2026-08-17 the fixture was bumped to
    # `2026.08.1` — correctly, because BR-TEN-077 says a content change without
    # a version bump reaches NO existing tenant, and CR-004 had added six lists
    # and DEF-185 had corrected a vocabulary. The bump was right; **these two
    # suites were not moved with it**, and 16 cases went red on the branch and
    # STAYED red, which is what DEF-213 is.
    #
    # Re-typing `"2026.08.1"` here would fix today and break on the next bump,
    # so the version is read from `fixture_version()` — the same single source
    # the product itself uses (`reference_sweep.py`, from the fixture's own
    # `version` key). A test that hardcodes a value the product derives is a
    # test that expires.
    version = reference_sweep.fixture_version()
    runs = models.ReferenceSeedRun.objects.filter(tenant=tenant)
    assert {(r.list_code, r.fixture_version) for r in runs} == {
        (code, version)
        for code in (
            "uoms",
            "charge_codes",
            "tax_jurisdictions",
            "reason_codes",
            "payment_methods",
            "meter_types",
            "read_methods",
            "asset_types",
            "asset_statuses",
            "premises_types",
            "account_statuses",
            "account_types",
            # CR-004's six, added 2026-08-16 and never propagated here — the
            # OTHER half of DEF-213. Twelve became eighteen the day the PO's
            # reference-data change landed, and these two suites kept counting
            # twelve. Seed classification is BR-TEN-067's, recorded in the
            # decision log: occupancy_statuses / device_types are STRUCTURAL
            # (the toggle cannot suppress them), service_size_classes /
            # certification_types / areas are SAMPLE content, and
            # import_mappings seeds NO ROWS but still records a run, because a
            # list that was considered and deliberately left empty is not the
            # same as a list nobody wired.
            "occupancy_statuses",
            "device_types",
            # RENAMED 2026-08-27 by BR-TEN-170 — PO: *"it is utility service
            # size class"*. The hosted table keeps the old name (DEF-970); the
            # list code is what a seed-run row records.
            "service_size_classes",
            "certification_types",
            # CR-166-BRC10 — rating's three discount lists (seeded from the drawing).
            "discount_program_owners",
            "discount_exclusivity_groups",
            "discount_eligibility",
            "areas",
            "import_mappings",
            # CR-010 schema slices (2026-08-18): the account sub-type tree
            # (BR-CUS-067) and the unit-type rows (BR-MET-084) — both
            # discretionary, seeded from the owning module's ratified
            # constant, fixture deliberately empty (DEF-026 posture).
            "account_subtypes",
            "unit_types",
            # CR-059 CS-18 (2026-09-01): reconciliation difference reasons —
            # discretionary, seeded from payments' own ratified constant
            # (`bankrec_models.SEED_DIFFERENCE_REASONS`), fixture deliberately
            # empty (the DEF-026 posture, same as the two above).
            "bank_rec_difference_reasons",
        )
    }
    # 12 → 18 with CR-004's six (DEF-213), → 21 with CS-18's one. Derived from
    # the set above rather than re-typed, so the two can never disagree: an
    # audit row per seeded list is BR-TEN-016, and a count typed separately from
    # the list it counts is the next stale literal waiting to happen.
    assert audit_actions(audit_rows).count("reference.seeded") == 21  # BR-TEN-016
    # DEF-016: a skip is never bare. There is nothing left to skip — the
    # register that held the reasons is empty for the first time.
    seed = result["reference_seed"]
    assert seed["skipped"] == []
    assert seed["skipped_reasons"] == {}
    # ⚠ **`account_types` SEEDS EIGHT PER TENANT SINCE 2026-09-17, AND THIS
    # COMMENT SAID 0 FOR A GOOD REASON UNTIL THAT DAY.** It read: *a PLATFORM
    # table (r5 #12 [D5]) seeded by migration customers.0003 before any tenant
    # exists, so its per-tenant run legitimately creates 0 rows — a run row with
    # count 0 here means "already present platform-wide", never "empty"*. The PO
    # ruled *"utility can get their own account types"* (`BR-CUS-1079`), so the
    # rows are the tenant's, `customers.reference_seed_omissions` is empty
    # because the sentence it carried became false, and a 0 here would now mean
    # what it means for every other list.
    # ⚠ **5 → 6 ON 2026-08-25 AND THIS LINE DID NOT MOVE WITH IT (DEF-840).**
    # BR-CUS-107 (PO ruling closing DEF-701) added the sixth status
    # `disconnected` / `non_billable`, and the fixture, the migration and
    # `SEED_ACCOUNT_STATUSES` all carry six. This literal kept saying five, so
    # the case has been RED on the branch since that ruling landed — found by
    # the CR-039 wave E lane and re-run against the branch tip before being
    # filed (the DEF-486 rule). It is NOT that lane's regression.
    #
    # DERIVED, not re-typed, for exactly the reason the `fixture_version()` note
    # above gives: a test that hardcodes a value the product derives is a test
    # that expires, and this is the second time this file has proved it.
    from apps.customers import services as customers_services

    assert seed["seeded"]["account_statuses"] == len(
        customers_services.SEED_ACCOUNT_STATUSES
    )  # BR-CUS-055 as amended by BR-CUS-107, per tenant
    # DERIVED, not re-typed, for the reason the note above gives.
    assert seed["seeded"]["account_types"] == len(customers_services.SEED_ACCOUNT_TYPES)
    # `premises_types` seeds from metering's OWN ratified set (BR-MET-034
    # SEED_PREMISES_TYPES): the platform fixture deliberately carries no
    # entries for it, so there is one source of those five values, not two.
    from apps.metering import services as metering_services

    assert seed["seeded"]["premises_types"] == len(metering_services.SEED_PREMISES_TYPES)


def test_us_ten_002_tc2__toggle_off_leaves_the_discretionary_lists_empty(
    growth_plan, identity_seam, owner_seams, audit_rows
):
    """AMENDED 2026-08-10 — BR-TEN-067 (CONFIRMED, PO ruling, OQ-082) NARROWS
    this TC and this test is narrowed with it.

    It used to assert that EVERY reference list is empty when the S111 toggle is
    off. That is no longer the rule: the STRUCTURAL CATALOGUES are exempt.
    Meter types, read methods, asset types, asset lifecycle stages, account
    statuses and premises types ALWAYS seed, because they are vocabulary the
    schema requires and not sample content — an account cannot exist without a
    status, and `create_premises` cannot resolve a type that was never seeded
    (BR-MET-034). The toggle governs sample RECORDS and the DISCRETIONARY lists.

    So the assertion splits in two: the structural six are PRESENT, everything
    else is empty and wrote no seed-run row, no audit row and no seam call."""
    tenant, _ = provisioned_tenant(brazosbend_payload(load_defaults=False))

    seeded_lists = set(
        models.ReferenceSeedRun.objects.filter(tenant=tenant).values_list("list_code", flat=True)
    )
    assert seeded_lists == services.STRUCTURAL_REFERENCE_LISTS
    # ⚠ THIS SECOND ASSERTION IS THE POINT, AND IT DID ITS JOB. The one above
    # is DERIVED and would pass no matter what the structural set contained;
    # this one PINS the ratified membership, so adding a list to it goes RED
    # and a human has to say which ruling widened the set. CR-004 added two on
    # 2026-08-16, this went red as designed — and then stayed red for a day
    # because nobody amended it, which is the other half of DEF-213.
    #
    # The two are BR-TEN-067 structural on the decision log's own reasoning:
    # occupancy status is BILLING BEHAVIOUR, not description — r10's five are
    # tenant-billed / owner-billed / landlord-billed / base-only / no billing,
    # so a unit whose occupancy cannot be set has undefined billing, and that
    # is money. Device types follow `asset_types` and `meter_types`, which are
    # already structural for the same reason.
    assert services.STRUCTURAL_REFERENCE_LISTS == {
        "meter_types",
        "read_methods",
        "asset_types",
        "asset_statuses",
        "account_statuses",
        "premises_types",
        "occupancy_statuses",
        "device_types",
        # PO 2026-09-17 (*"utility can get their own account types"*) and
        # BR-TEN-150 clause 3 — both already in `STRUCTURAL_REFERENCE_LISTS`
        # with their reasons; this pin had not caught up (red before CR-166).
        "account_types",
        "owner_categories",
        # CR-166-BRC10 (PO 2026-10-03): *Who qualifies* is a REQUIRED dropdown
        # and ruling 3's four system checks exist only as seeded rows — a
        # utility cannot add one — so a toggled-off tenant must still get them.
        "discount_program_owners",
        "discount_exclusivity_groups",
        "discount_eligibility",
    }

    # …and they really carry rows, not just ledger entries (an account cannot
    # exist without a status; a premises cannot be created without a type).
    from apps.assets import models as asset_models
    from apps.customers import models as customer_models
    from apps.metering import models as metering_models

    with tenant_ctx(tenant):
        assert asset_models.MeterType.objects.filter(tenant=tenant).exists()
        assert asset_models.ReadMethod.objects.filter(tenant=tenant).exists()
        assert asset_models.AssetType.objects.filter(tenant=tenant).exists()
        assert asset_models.AssetLifecycleStage.objects.filter(tenant=tenant).exists()
        assert customer_models.AccountStatus.objects.filter(tenant=tenant).exists()
        assert metering_models.PremisesType.objects.filter(tenant=tenant).exists()

    # The DISCRETIONARY half of TC-2, unchanged: nothing sample-shaped landed.
    assert models.Uom.objects.filter(tenant=tenant).count() == 0
    assert models.ReasonCode.objects.filter(tenant=tenant).count() == 0
    assert models.PaymentMethod.objects.filter(tenant=tenant).count() == 0
    # CR-166-BRC10: rating's ONLY calls are the three structural discount lists.
    assert [c["list"] for c in owner_seams.rating] == [
        "discount_program_owners",
        "discount_exclusivity_groups",
        "discount_eligibility",
    ]
    assert owner_seams.billing == [] and owner_seams.payments == []
    assert not (seeded_lists & {"uoms", "charge_codes", "tax_jurisdictions"})
    # one audit row per structural list, and not one more (BR-TEN-016)
    assert audit_actions(audit_rows).count("reference.seeded") == len(
        services.STRUCTURAL_REFERENCE_LISTS
    )


def test_us_ten_002_tc3__reseed_is_idempotent_counts_unchanged(
    growth_plan, identity_seam, owner_seams
):
    tenant, _ = provisioned_tenant()
    uom_count = models.Uom.objects.filter(tenant=tenant).count()
    run_count = models.ReferenceSeedRun.objects.filter(tenant=tenant).count()
    actor = SimpleNamespace(id=None)
    with tenant_ctx(tenant):
        from django.db import transaction

        with transaction.atomic():  # retry after crash re-enters the seeder
            summary = services._seed_reference_data(tenant, "TX", actor)
    # ⚠ **AMENDED 2026-08-21 (DEF-444).** This read `summary["seeded"] == {}`,
    # on the reasoning that every list already has its seed-run record. That is
    # still true of every list BUT ONE: `tax_jurisdictions` depends on
    # `tenants.state` as well as on the fixture version, and the run row does not
    # carry the state — so a tenant that recorded its state AFTER sign-up could
    # never receive its own state's authorities, from any path. The list is now
    # re-offered on every run and the OWNER's seeder (insert-missing by name)
    # decides whether anything is written.
    #
    # ⚠ **AND THE STUB IS WHY THE ASSERTION MOVED RATHER THAN THE PRODUCT.**
    # `owner_seams` reports `len(entries)` for every call, so under it a replay
    # "creates" 8 rows that the real seeder creates zero of. The real behaviour
    # is asserted end to end in `test_def444_state_tax_jurisdictions.py`
    # (`::test_a_replay_writes_nothing_and_says_nothing`): with the live seeder
    # the count is 0, nothing lands in `seeded`, and no second run row appears.
    # What THIS case protects is unchanged and is the two lines below: a replay
    # writes no row.
    assert set(summary["seeded"]) <= {"tax_jurisdictions"}
    assert models.Uom.objects.filter(tenant=tenant).count() == uom_count
    assert models.ReferenceSeedRun.objects.filter(tenant=tenant).count() == run_count


def test_us_ten_002_tc4__missing_or_corrupt_fixture_rolls_back_everything(
    growth_plan, identity_seam, owner_seams, audit_rows, monkeypatch, tmp_path
):
    monkeypatch.setattr(services, "FIXTURE_PATH", tmp_path / "missing.json")
    with pytest.raises(errors.SysError) as excinfo:
        services.provision_tenant(brazosbend_payload())
    assert excinfo.value.message_key == "signup.reference_fixture_invalid"
    # BR-TEN-001: no half-seeded tenant — the WHOLE transaction rolled back
    assert models.Tenant.objects.count() == 0
    assert models.Uom.objects.count() == 0
    assert "tenant.provision_failed" in audit_actions(audit_rows)

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json")
    monkeypatch.setattr(services, "FIXTURE_PATH", corrupt)
    with pytest.raises(errors.SysError):
        services.provision_tenant(brazosbend_payload())
    assert models.Tenant.objects.count() == 0


def test_us_ten_002_tc5__tenant_touched_rows_survive_newer_fixture_version(
    growth_plan, identity_seam, owner_seams, monkeypatch
):
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        kgal = models.Uom.objects.get(tenant=tenant, code="kgal")
        kgal.name = "Kilogallons (tenant renamed)"
        kgal.save(update_fields=["name", "updated_at"])
        newer = {
            # Any version STRICTLY AHEAD of the shipped fixture's. This read
            # "V2.13.0.1" and broke the day CR-010's schema slices bumped the
            # real fixture to exactly that — the tenant was no longer behind
            # and the seed wrote nothing. A synthetic future version has no
            # business tracking the real one; V99 outruns it for good.
            "version": "V99.0.0.0",
            "uoms": [
                {"code": "kgal", "name": "Thousand gallons v2"},  # must NOT apply
                {
                    "code": "acre-ft",
                    "name": "Acre-foot",
                },  # new → may insert ("Mcf" seeds already, CR-010 10.2)
            ],
        }
        monkeypatch.setattr(services, "_load_seed_fixture", lambda: newer)
        actor = SimpleNamespace(id=None)
        from django.db import transaction

        with transaction.atomic():
            summary = services._seed_reference_data(tenant, "TX", actor)
    assert summary["seeded"]["uoms"] == 1  # only the genuinely-new row
    kgal.refresh_from_db()
    assert kgal.name == "Kilogallons (tenant renamed)"  # BR-TEN-012: untouched
    assert models.Uom.objects.filter(tenant=tenant, code="acre-ft").exists()


def test_us_ten_002_tc6__seeded_lists_are_per_tenant(growth_plan, identity_seam, owner_seams):
    brazos, _ = provisioned_tenant()
    lonestar, _ = provisioned_tenant(lonestarridge_payload(load_defaults=False))
    # selector reads are tenant-scoped: Lone Star Ridge sees zero seeded rows
    from apps.tenancy import selectors

    with tenant_ctx(lonestar):
        assert selectors.lookup_page("uoms", None) == []
    with tenant_ctx(brazos):
        assert len(selectors.lookup_page("uoms", None)) == SEEDED_UOM_COUNT  # CR-010 10.2
    # (RLS FORCE half of this TC = G5 isolation suite on live Postgres)


def test_us_ten_002_seam__owner_lanes_not_authored_lists_skipped_honestly(
    growth_plan, identity_seam
):
    """Without the owning-module functions, a cross-module list whose table
    nobody hosts is SKIPPED — skip-until-wired, never guessed into another
    module's tables (BR-TEN-013).

    The two lists tenancy HOSTS (reason_codes, payment_methods — see the model
    docstrings) are the documented exception: the seam is still consulted
    FIRST, and only when it answers "not wired" does the fixture land in the
    hosted table, so the card is not empty forever. The moment billing/payments
    author seed_reference_list, they win and this fallback stops running.

    AMENDED 2026-08-10 (DEF-016/DEF-017): rating and metering now author their
    seams, so the only lists left skipping were the two the customers module
    owns — and each carried its written reason, which is what stopped the skip
    from being silent.

    AMENDED AGAIN 2026-08-10 (W2 customers SCHEMA + SEAM slice): customers now
    owns its tables and authors `seed_reference_list` too, so NOTHING skips.
    The mechanism this test names is unchanged and still the law — the seam is
    consulted first, an unwired owner still skips honestly — it simply has no
    live example left in this repo. That is the goal state, not the end of the
    rule: the next module to declare a list before it can seed one lands right
    back in the skipped set with a written reason."""
    tenant, result = provisioned_tenant()
    assert result["reference_seed"]["skipped"] == []
    # the tenancy-owned + tenancy-hosted lists seeded; no rows minted for skips
    assert models.Uom.objects.filter(tenant=tenant).count() == SEEDED_UOM_COUNT  # CR-010 10.2
    assert models.ReasonCode.objects.filter(tenant=tenant).count() == 5
    assert models.PaymentMethod.objects.filter(tenant=tenant).count() == 7
    assert all(
        row.is_system for row in models.PaymentMethod.objects.filter(tenant=tenant)
    )  # BR-TEN-036: seeded rows are deactivatable, never deletable
    assert set(
        models.ReferenceSeedRun.objects.filter(tenant=tenant).values_list("list_code", flat=True)
    ) == {
        "uoms",
        "reason_codes",
        "payment_methods",
        "charge_codes",
        "tax_jurisdictions",
        "meter_types",
        "read_methods",
        "asset_types",
        "asset_statuses",
        "premises_types",
        "account_statuses",
        "account_types",
        # CR-004's six, added 2026-08-16 and never propagated here (DEF-213).
        # This is the SEAM case — everything with a wired owner seeds — so all
        # six belong, including `import_mappings`, which seeds NO ROWS and
        # still records a run: a list deliberately left empty is not the same
        # as a list nobody wired, and this test exists to tell them apart.
        "occupancy_statuses",
        "device_types",
        "service_size_classes",  # BR-TEN-170
        "certification_types",
        "areas",
        "import_mappings",
        # CR-010 (2026-08-18): the sub-type tree seeds through the customers
        # seam like its two siblings; the unit-type rows through metering's.
        "account_subtypes",
        "unit_types",
        # CR-059 CS-18 (2026-09-01): payments' second routed list — the
        # reconciliation difference reasons. It is the newest live example of
        # exactly what this case names: the seam is consulted FIRST, payments
        # authors `seed_reference_list`, so payments wins and nothing falls back.
        "bank_rec_difference_reasons",
    }


def test_cr010_item7__the_notification_settings_row_exists_at_provisioning(
    growth_plan, identity_seam
):
    """CR-010 item 7 (PO 2026-08-17): *"we need ready to sue notification …
    there are many gaps in data seeding"* — the dispatch-settings row is
    WRITTEN at provisioning, not materialised on first read.

    What this changes and what it deliberately does not: the S8 Notifications
    tab opens populated from day zero, and "which tenants have a notifications
    row" becomes a database question. The VALUES are unchanged — the model's
    own ratified column defaults, with email and SMS dispatch OFF (OQ-073/074:
    the unsafe option is the one you type) — and the first-read get_or_create
    stays as the repair path for tenants provisioned before this landed.
    """
    from apps.notifications import models as not_models

    tenant, _result = provisioned_tenant()
    with tenant_ctx(tenant):
        row = not_models.NotificationSettings.objects.get(tenant_id=tenant.id)
    assert row.dispatch_batch_size == 500  # BR-BIL-016
    assert str(row.quiet_hours_start) == "08:00:00" and str(row.quiet_hours_end) == "21:00:00"
    assert row.email_dispatch_active is False  # OQ-073 — deferred send, stated
    assert row.sms_dispatch_active is False  # OQ-074 — same posture


def test_def258__the_set12_rule_rows_seed_at_provisioning_too(growth_plan, identity_seam):
    """CR-010 item 7's SECOND half — DEF-258, filed 2026-08-18, fixed 2026-08-19.

    The requirement is ONE sentence naming TWO things: *"the NotificationSettings
    row is to be WRITTEN at provisioning (today it is created on first read), so
    the dispatch home opens populated, **and the SET-12 rule rows with it**"*.
    The test above pins the first half. This pins the half that did not land.

    ⚠ WHY A TEST AND NOT A READING. The rows appear on first read, so every
    screen, every API response and every existing test sees a populated matrix
    whatever provisioning does — the gap is invisible from anywhere except the
    database of a tenant nobody has visited. The live evidence was two
    timestamps twenty hours apart:

        notification_settings  min(created_at) = 2026-08-18 08:19:26
        notification_rules     min(created_at) = 2026-08-19 04:21:17

    RED-PROOF, run before the fix: this test failed on
    `assert 0 == 15` — the provisioned tenant had no rule row at all until
    something read them.

    It asserts the CATALOGUE's own length rather than the literal 15, so the day
    OQ-262 or OQ-249 adds an event this test keeps meaning what it says instead
    of becoming a number to update.
    """
    from apps.notifications import rule_catalog, rule_models

    tenant, _result = provisioned_tenant()
    with tenant_ctx(tenant):
        rules = list(rule_models.NotificationRule.objects.filter(tenant_id=tenant.id))
        channels = rule_models.NotificationRuleChannel.objects.filter(tenant_id=tenant.id).count()
    assert len(rules) == len(rule_catalog.EVENTS)
    assert channels == sum(len(event.channels) for event in rule_catalog.EVENTS)
    by_key = {row.event_key: row for row in rules}
    # The two seeded values that are RULES and not conveniences — an event whose
    # trigger does not exist ships OFF (hard-won law 3, defaults fail closed),
    # and the past-due reminder ships with the CR's own protective filter on.
    assert by_key["past_due_reminder"].skip_accounts_on_payment_plan is True
    for event in rule_catalog.EVENTS:
        assert by_key[event.key].enabled is (event.trigger_blocked_by is None)


def test_cr010_ruling7__regional_defaults_seed_at_provisioning(growth_plan, identity_seam):
    """CR-010 ruling 7 (PO 2026-08-17: *"yes this is good"*): the US-first
    regional set, ratified field by field on the artifact and seeded at
    creation — a fresh tenant has a date format before any human opens a tab.

    Two absences are as ratified as the presences: `accounting_method` stays
    NULL (the PO removed that control in CR-008 ruling 1 — seeding a value
    would revive a claim nothing reads), and `timezone` still comes from the
    signup state, not from this set.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        row = models.TenantSettings.objects.get(tenant=tenant)
    assert row.country == "United States"
    assert row.language == "en-US"
    assert row.date_format == "MM/DD/YYYY"
    assert row.number_format == "1,234.56"
    assert row.time_format == "12-hour"
    assert row.first_day_of_week == "sunday"
    assert (row.fy_start_month, row.fy_start_day) == (1, 1)
    assert (row.close_cadence, row.close_day) == ("monthly", "last day")
    assert row.accounting_method is None  # CR-008 ruling 1 — control removed
    assert row.timezone  # signup-derived, untouched by this ruling


def test_cr010_102__uoms_seed_all_twenty_six_with_stated_scopes(growth_plan, identity_seam):
    """CR-010 10.2 (PO 2026-08-17: *"yes pls"*): a unit for every service — 26
    covering ten until `CR-063` added `connection` for FIRE, the eleventh.
    The figure is derived above rather than repeated here, for the reason
    `SEEDED_UOM_COUNT` gives. A NEW fixture entry states its scope and the seeder validates it
    against the service catalog — stated wins over derived, exactly the
    charge_type precedent."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = {row.code: row for row in models.Uom.objects.filter(tenant=tenant)}
    assert len(rows) == SEEDED_UOM_COUNT
    # one stated scope per new service family, spot-checked at the DB
    assert rows["kVA"].service.code == "electric"
    assert rows["EDU"].service.code == "sewer"
    assert rows["ERU"].service.code == "storm_water"
    assert rows["ton-hr"].service.code == "thermal_heat"
    assert rows["Mbps"].service.code == "broadband"
    # shared units stay All services (NULL) — MMBtu is gas AND thermal,
    # kW-DC is solar AND battery, day is everyone's
    assert rows["MMBtu"].service is None
    assert rows["kW-DC"].service is None
    assert rows["day"].service is None


def test_cr010_tax__every_state_gets_the_scaffold_and_texas_keeps_its_rows(
    growth_plan, identity_seam
):
    """The tax ruling, options a AND b (PO: *"I will go with a and B - default
    available"*): a Texas tenant seeds its state rows PLUS the scaffold; a
    non-Texas tenant — which used to seed ZERO jurisdictions — now gets the
    County · City · Special district structure with not one pre-filled rate."""
    from apps.rating import models as rating_models

    texan, _ = provisioned_tenant()  # brazosbend payload is TX
    with tenant_ctx(texan):
        names = set(
            rating_models.TaxJurisdiction.objects.filter(tenant=texan).values_list(
                "name", flat=True
            )
        )
    assert {"County", "City", "Special district"} <= names  # the scaffold
    assert any("Texas" in name or name == "Local" for name in names)  # the state's own


def test_cr010_103__company_profile_seeds_the_seven_derivable_fields(growth_plan, identity_seam):
    """CR-010 10.3 (PO: *"im okay with your suggestions"*): seven fields seed
    from facts the signup gave us; the five that would be FABRICATED facts on
    a bill (EIN, state utility id, both addresses, phone, logo) stay NULL and
    checklisted — ruled, not forgotten."""
    tenant, _ = provisioned_tenant()
    assert tenant.legal_name == tenant.name
    assert tenant.dba_name == tenant.name
    assert tenant.support_email  # the owner's signup email
    assert tenant.remit_payable_to == tenant.name
    assert tenant.service_hours == "Mon–Fri 8:00 AM–5:00 PM"
    assert (tenant.brand_primary_hex, tenant.brand_accent_hex) == ("#1B5E9E", "#0F7A6B")
    # DEF-TEN-9720 (PO 2026-10-05 (5)): the portal address, or blank with no
    # PUBLIC_APP_ORIGIN (this test's settings) — never smartbillhub.com.
    from core import public_origin

    origin = public_origin.public_app_origin()
    assert tenant.website == (f"{origin}/{tenant.subdomain}/portal" if origin else None)
    # the five ruled-empty stay empty
    assert tenant.ein is None and tenant.state_utility_id is None
    assert tenant.mailing_address is None and tenant.remit_to_address is None
    assert tenant.support_phone is None and tenant.logo_file_id is None
