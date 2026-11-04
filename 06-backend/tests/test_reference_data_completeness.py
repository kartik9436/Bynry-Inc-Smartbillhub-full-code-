# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-002 (seed standard reference data from platform fixtures,
#           S111) · US-TEN-009 (the S8 Reference-data card grid)
#           Defects:  DEF-016 (charge codes seeded zero rows and the skip was
#           silent) · DEF-017 (SEVEN reference lists never in the fixture or the
#           seeder at all) · DEF-026 (the production guard refused the ONE path
#           that only production needs — `--tenant` reference-data backfill)
# Rules:    BR-TEN-012 (versioned fixtures, per-list idempotent, tenant-touched
#           rows never overwritten) · BR-TEN-013 (cross-module writes only via
#           the owning module's service functions; unwired = skip) ·
#           BR-TEN-016 (every seed writes its audit row) · BR-TEN-031 (the
#           owning module validates and writes its list) · BR-TEN-036 (seeded +
#           tenant-extensible) · BR-TEN-056 clause 3 (report honestly when a
#           module's seam is not wired — "the failure mode that left charge
#           codes empty was a skip reported into a summary nobody reads") ·
#           BR-TEN-064 (the environment guard is PER PATH; EP-TEN-03 TC-12 says
#           the three paths are asserted separately) · BR-MET-034 (premises
#           types are seeded, tenant-extensible Reference data — DEF-017's
#           seventh list) · BR-RAT-020/023 (deposits are `plan_deposit_rules`,
#           which SUPERSEDE the prototype's single DEPO-R checkbox) ·
#           BR-AST-004/031/043 (the four asset catalogs' ratified value sets) ·
#           CLAUDE.md rule 2 (money is NUMERIC(18,6) from decimal strings)
# ───────────────────────────────────────────────────────
"""DEF-016 + DEF-017 + DEF-026 — reference-data COMPLETENESS and HONESTY.

Three defects, one law: after a tenant is provisioned, every reference list the
product declares is either SEEDED or written down WITH A REASON — and there has
to be a way to fill a tenant that was provisioned before a list existed.
"Skipped into a summary nobody reads" is not a state, and neither is "the fix
exists but refuses to run on the only host that needs it".

Each check here was proved RED against the defect it was written for before it
was trusted green (Hard-won law 7); the red-then-green transcripts are in the
lane report. The red conditions, for anyone re-proving them:

  DEF-016 · rename `seed_reference_list` in apps/rating/services.py
           → charge_codes/tax_jurisdictions seed 0 rows and go UNEXPLAINED.
  DEF-017 · drop the rows from services.SEED_LIST_OWNERS
           → those lists are neither seeded nor registered; or restore
             metering's old router (meter_types → 0, read_methods → KeyError)
             and the four asset catalogs go empty. For the SEVENTH list, drop
             BOTH `premises_types` registrations (LOOKUP_LISTS and
             SEED_LIST_OWNERS) and six tests go red naming it.
  DEF-026 · move the production refusal back to the first statement of
             seed_demo's `handle()`, before `options["tenant"]` is read
           → the `--tenant` and `--check` cases fail with "refuses under
             production settings" while the demo-fixture case stays green,
             which is exactly the per-path split BR-TEN-064 rules.
"""

import io
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import override_settings

from apps.assets import services as asset_services
from apps.rating import models as rating_models
from apps.rating import services as rating_services
from apps.tenancy import models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services

from tests.isolation_helpers import requires_postgres
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import provisioned_tenant, tenant_ctx
from apps.rating.charge_prices import flat_amount as _flat  # CR-156-BRC10: the amount is a dated row

pytestmark = pytest.mark.django_db

FIXTURE = json.loads(Path(services.FIXTURE_PATH).read_text(encoding="utf-8"))
FIXTURE_CHARGES = {entry["code"]: entry for entry in FIXTURE["charge_codes"]}


def _lists(report):
    return {row["list"]: row for row in report["lists"]}


# ══════════════════════════════════════════════════════════════════════════
# DEF-016 — the skip can no longer be silent
# ══════════════════════════════════════════════════════════════════════════
def test_us_ten_002_tc1_def016__no_declared_list_is_quietly_empty(growth_plan, identity_seam):
    """THE DEF-016 GUARD. Every list in LOOKUP_LISTS is seeded, or registered in
    UNSEEDABLE_REFERENCE_LISTS with a reason. Nothing else is allowed.

    RED on the defect: with rating's seam absent, `charge_codes` has 0 rows and
    no register row, so `unexplained` contains it and this fails naming it.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        report = services.reference_data_report()
    assert report["unexplained"] == [], (
        "reference lists are EMPTY with no recorded reason — wire the owning "
        "module's seed_reference_list seam or record why in "
        f"UNSEEDABLE_REFERENCE_LISTS: {report['unexplained']}"
    )
    # …and the register is not a dumping ground: everything in it is genuinely
    # empty, so a stale excuse for a list that now seeds fails too.
    rows = _lists(report)
    for list_code in services.UNSEEDABLE_REFERENCE_LISTS:
        assert not rows[list_code]["count"], (
            f"{list_code} has rows but is still listed as unseedable — remove its "
            "UNSEEDABLE_REFERENCE_LISTS entry, the lane landed"
        )


def test_us_ten_002_tc1_def016__every_skip_carries_its_reason(growth_plan, identity_seam):
    """BR-TEN-056 clause 3: an unwired seam still skips (BR-TEN-013), but the
    skip arrives with prose a human reads, not just a list code.

    AMENDED 2026-08-10 (W2 customers SCHEMA + SEAM slice): the last two skips
    are gone — customers owns its tables and authors its seam — so this now
    asserts the INVARIANT rather than an example. Whatever skips (today:
    nothing) must carry a written reason, and nothing may be UNEXPLAINED. The
    day a new module declares a list before it can seed one, the same assertion
    catches a bare skip."""
    _, result = provisioned_tenant()
    seed = result["reference_seed"]
    assert set(seed["skipped_reasons"]) == set(seed["skipped"]), (
        "a skip without a recorded reason is exactly the DEF-016 shape: "
        f"skipped={seed['skipped']} reasons={sorted(seed['skipped_reasons'])}"
    )
    for list_code in seed["skipped"]:
        reason = seed["skipped_reasons"][list_code]
        assert len(reason) > 80 and "UNEXPLAINED" not in reason, list_code


def test_us_ten_002_tc1_def016__charge_codes_are_not_empty_after_provisioning(
    growth_plan, identity_seam
):
    """The defect itself, at the surface the PO saw: the S8 Charge-codes card.

    RED on the defect: rating had no seeding seam, so this count was 0.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = {row.code: row for row in rating_models.Charge.objects.filter(tenant=tenant)}
        cards = {card["list"]: card for card in tenancy_selectors.lookup_cards()}
    assert rows, "charge_codes seeded zero rows — DEF-016"
    assert cards["charge_codes"]["count"] == len(rows)


def test_us_ten_002_tc1_def016__seeded_charge_money_is_the_fixture_verbatim(
    growth_plan, identity_seam
):
    """CLAUDE.md rule 2. Every seeded figure equals the fixture's own decimal
    STRING (percent points → fraction is a representation change, not a new
    number — models.Charge / US-RAT-008 TC-3). Nothing rounds, nothing floats."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = {row.code: row for row in rating_models.Charge.objects.filter(tenant=tenant)}

    late = rows["LATE"]
    assert late.percent == Decimal(FIXTURE_CHARGES["LATE"]["percent"]) / 100
    assert late.min_amount == Decimal(FIXTURE_CHARGES["LATE"]["min_amount"])
    assert late.amount_rule == "percent_with_minimum"
    for code in ("CONN", "DISC", "NSF"):
        assert _flat(rows[code]) == Decimal(FIXTURE_CHARGES[code]["amount"]), code
        assert rows[code].amount_rule == "flat", code
    # every stored figure is a Decimal, never a float (HR-2)
    for row in rows.values():
        for value in (_flat(row), row.percent, row.min_amount, row.max_amount):
            assert value is None or isinstance(value, Decimal)


def test_us_ten_002_tc1_def016__a_charge_code_with_no_ratified_figure_is_reported_not_invented(
    growth_plan, identity_seam
):
    """A fixture code with no amount is not created — and the seam SAYS SO by
    name, which is the whole point of DEF-016.

    AMENDED 2026-08-10 (PO ruling). TAMPER has left this set: the PO ruled
    **$250.00** (EP-RAT-03 §4) over the billing workbook's $500.00 and made it
    the PLATFORM default, so the fixture prices it and it seeds like any other
    flat fee. DEPO-R is the only member left, and its reason changed KIND:
    it is not "no ratified figure", it is BR-RAT-020/023 — deposits are
    `plan_deposit_rules` per consumer category, which explicitly supersede the
    prototype's single DEPO-R checkbox. A platform-wide DEPO-R amount would
    encode a model the PO already replaced, so the register says that in prose
    rather than leaving it looking like a gap."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        stored = set(
            rating_models.Charge.objects.filter(tenant=tenant).values_list("code", flat=True)
        )
    figureless = {
        entry["code"]
        for entry in FIXTURE["charge_codes"]
        if not entry.get("amount") and not entry.get("percent")
    }
    # CR-010 A2 (PO 2026-08-17) split "figureless" into THREE ratified kinds:
    #   · the two DEPOSIT codes stay unseeded — BR-RAT-020/023's ruling, amounts
    #     live on the plan's deposit rules;
    #   · the four `pricing: per_case` codes SEED with no figure — "actual
    #     cost, entered per case" was on the table the PO confirmed;
    #   · absence WITHOUT the marker still means "nobody priced it" and still
    #     refuses. None of the 25 is in that state.
    assert figureless == {"DEPO-R", "DEPO-C", "DAMAGE", "TAP", "IMPACT", "BULK-WATER"}
    per_case = {
        entry["code"]
        for entry in FIXTURE["charge_codes"]
        if entry.get("pricing") == "per_case"
    }
    assert per_case == {"DAMAGE", "TAP", "IMPACT", "BULK-WATER"}
    assert per_case <= stored  # ratified-unpriced codes DO seed…
    with tenant_ctx(tenant):
        damage = rating_models.Charge.objects.get(tenant=tenant, code="DAMAGE")
    # …with no invented fee, and SAYING it is entered when used (DEF-2340,
    # PO 2026-10-01 point 3) — before that fix the rule was NULL, the same row
    # as a code nobody priced.
    assert _flat(damage) is None and damage.amount_rule == "per_case"
    assert stored.isdisjoint({"DEPO-R", "DEPO-C"})  # the deposit ruling holds
    assert "TAMPER" in stored  # the $250 ruling, seeded
    reported = {
        note["entry"]: note["reason"]
        for note in rating_services.reference_seed_omissions(
            "charge_codes", FIXTURE["charge_codes"]
        )
    }
    assert set(reported) == {"DEPO-R", "DEPO-C"}  # per_case rows are not omissions
    # both deposit notes are the RULING, not the generic "nobody priced it" line
    for code in ("DEPO-R", "DEPO-C"):
        assert "BR-RAT-020" in reported[code] and "BR-RAT-023" in reported[code]
        assert "supersede" in reported[code].lower()


def test_us_ten_002_tc1__tamper_is_the_po_ruling_and_the_seeded_class_is_confirmed(
    growth_plan, identity_seam
):
    """PO ruling 2026-08-10, asserted at the DB where it lands.

    Two ratified sources disagreed (EP-RAT-03 §4 $250.00 · billing workbook §1
    and WE-11 $500.00) and the PO ruled $250.00 as the PLATFORM default. Money
    is a decimal STRING into NUMERIC(18,6) — never float, never cents
    (CLAUDE.md rule 2) — and `charge_type` is the confirmed S12 class per code,
    which the platform seed used to leave NULL on every tenant."""
    # CR-010 A2 (PO 2026-08-17: *"extend this list to 25 items"*) — the full
    # 25, every class shown to the PO on the artifact before it shipped.
    expected_types = {
        "LATE": "penalty",
        "CONN": "one_time",
        "DISC": "one_time",
        "NSF": "penalty",
        "DEPO-R": "refundable",
        "TAMPER": "penalty",
        "RECON": "one_time",
        "DEPO-C": "refundable",
        "TRANSFER": "one_time",
        "METER-TEST": "one_time",
        "AFTER-HRS": "one_time",
        "RETURN-TRIP": "one_time",
        "DAMAGE": "one_time",
        "RE-READ": "one_time",
        "TAP": "one_time",
        "IMPACT": "one_time",
        "HYDRANT": "recurring",
        "TEMP-SVC": "one_time",
        "SEASONAL": "one_time",
        "SAME-DAY": "one_time",
        "MOVE-OUT": "one_time",
        "CC-CONV": "one_time",
        "PAPER": "recurring",
        "INSPECT": "one_time",
        "BULK-WATER": "one_time",
    }
    assert {e["code"]: e.get("charge_type") for e in FIXTURE["charge_codes"]} == expected_types
    assert len(expected_types) == 25  # the ruled size, pinned as a number too

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = {row.code: row for row in rating_models.Charge.objects.filter(tenant=tenant)}
    assert _flat(rows["TAMPER"]) == Decimal("250")
    assert _flat(rows["TAMPER"]) == Decimal(FIXTURE_CHARGES["TAMPER"]["amount"])
    assert isinstance(_flat(rows["TAMPER"]), Decimal)  # HR-2: never a float
    assert rows["TAMPER"].amount_rule == "flat"
    for code, row in rows.items():
        assert row.charge_type == expected_types[code], code


def test_us_ten_002_tc1_def016__the_register_is_prose_a_human_can_act_on():
    """An entry in UNSEEDABLE_REFERENCE_LISTS is the reviewable artifact that
    replaces the silent skip, so it must actually say something.

    AMENDED 2026-08-10 (W2 customers SCHEMA + SEAM slice): the register is now
    EMPTY, which is the goal state — every declared list is genuinely seeded.
    An empty register is therefore no longer a failure; a register with a
    one-line excuse in it still is, and so is an entry for a list the registry
    does not declare."""
    for list_code, reason in services.UNSEEDABLE_REFERENCE_LISTS.items():
        assert list_code in services.LOOKUP_LISTS, list_code
        assert len(reason) > 120, f"{list_code}: a one-liner is not a reason"


# ══════════════════════════════════════════════════════════════════════════
# DEF-017 — the six lists that were in no fixture and no seeder
# ══════════════════════════════════════════════════════════════════════════
DEF_017_LISTS = (
    "meter_types",
    "read_methods",
    "asset_types",
    "asset_statuses",
    "account_statuses",
    "account_types",
    # The SEVENTH, found 2026-08-10. `premises_types` was in NEITHER registry
    # even though apps.metering.services.seed_reference_list has handled the
    # list code since it was written — so the only way a tenant ever got
    # premises types was the side effect of `ensure_reference_catalogs()` on a
    # premises WRITE. No seed-run row, no audit row, no line in the
    # reference-data report: the one list whose absence was invisible.
    "premises_types",
)


def test_us_ten_002_tc1_def017__all_seven_missing_lists_are_declared_in_the_seeder():
    """RED on the defect: none of them was in SEED_LIST_OWNERS, so the
    seeder never even tried."""
    routed = dict(services.SEED_LIST_OWNERS)
    for list_code in DEF_017_LISTS:
        assert list_code in routed, f"{list_code} is in no seeder — DEF-017"
        # the registry and the seeder must not disagree about who owns a list
        assert routed[list_code] == services.LOOKUP_LISTS[list_code].owner, list_code


def test_us_ten_002_tc1_def017__premises_types_seeds_at_provisioning_with_its_ledger_row(
    growth_plan, identity_seam
):
    """DEF-017's seventh list, end to end.

    RED on the defect: `premises_types` is in neither LOOKUP_LISTS nor
    SEED_LIST_OWNERS, so a freshly provisioned tenant has NO premises types (the
    only seeder is a side effect of a premises write that has not happened yet),
    no `reference_seed_runs` row and no `reference.seeded` audit row. The S16
    guided-add wizard cannot resolve a type on such a tenant.

    The values come from metering's OWN ratified set (BR-MET-034
    SEED_PREMISES_TYPES) and NOT from a mirrored copy in the platform fixture:
    one source, so there is nothing to drift."""
    from apps.metering import models as metering_models
    from apps.metering import services as metering_services

    assert "premises_types" not in FIXTURE  # deliberately not mirrored

    tenant, result = provisioned_tenant()
    with tenant_ctx(tenant):
        rows = metering_models.PremisesType.objects.filter(tenant=tenant)
        codes = set(rows.values_list("code", flat=True))
    assert codes == {code for code, _ in metering_services.SEED_PREMISES_TYPES}
    assert all(row.is_system for row in rows)  # BR-TEN-036
    assert result["reference_seed"]["seeded"]["premises_types"] == len(codes)
    assert models.ReferenceSeedRun.objects.filter(
        tenant=tenant, list_code="premises_types", fixture_version=FIXTURE["version"]
    ).exists()


def test_us_ten_002_tc1_def017__premises_types_reports_as_seeded_not_as_empty(
    growth_plan, identity_seam
):
    """…and it REPORTS, which is the half that made it invisible.

    UNTIL 2026-08-17 this case pinned the `uncounted` state: metering owned the
    table and had authored no lookup handler, so the report could neither call
    the list empty (false — five rows) nor seeded (uncheckable), and `uncounted`
    was the honest third answer. DEF-236's fix (apps/metering/lookups.py,
    CR-010 item 2) registered the handler, so the report can now COUNT the five
    rows live — the state this docstring's previous revision said was "what is
    still missing". The `uncounted` state itself stays in the report machinery
    for the next module that seeds before it can count.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        report = services.reference_data_report()
    row = _lists(report)["premises_types"]
    assert row["state"] == "seeded"
    assert row["owner"] == "metering"
    assert row["count"] == 6  # counted LIVE through the DEF-236 handler (6 = CR-010 item 4)
    assert row["seed_run_count"] == 6
    assert report["uncounted"] == []  # nothing left in the workaround state
    assert "premises_types" not in report["empty"]
    assert "premises_types" not in report["unexplained"]


def test_us_ten_002_tc1_def017__every_declared_list_is_routed_by_the_seeder():
    """The general form: a list can be added to the S8 grid only together with
    a seeding route. This is what stops the next DEF-017.

    ⚠ **AMENDED 2026-08-28 (DEF-203) — THE TWO REGISTERS NOW COMPOSE, AND THE
    GUARD IS NOT WEAKER FOR IT.** This asserted plain equality, which reads as
    *"every declared list is seeded"* — true of every list this product had
    until `bank_accounts`. That one is a tenant's OWN banking relationship:
    nobody but the utility knows what their accounts are called, and a seeded
    example would be a fake bank account sitting in a picker that imports real
    money. It is EMPTY on every tenant by design, permanently.

    DEF-016 already built the machinery for exactly that statement —
    `UNSEEDABLE_REFERENCE_LISTS`, whose entries are prose a reviewer reads and
    which a sibling test refuses at under 120 characters. So the rule becomes
    **routed, OR written down with its reason** — and a new list carrying
    NEITHER still fails here, which is the whole of what DEF-017 asked for.
    Recorded in 12-governance/02-decision-log.md, 2026-08-28."""
    declared = set(services.LOOKUP_LISTS)
    routed = {code for code, _ in services.SEED_LIST_OWNERS}
    assert (
        routed <= declared
    ), f"the seeder routes a list the registry does not declare — {sorted(routed - declared)}"
    assert (declared - routed) <= set(services.UNSEEDABLE_REFERENCE_LISTS), (
        "declared reference lists with NO seeding route and NO written reason: "
        f"{sorted((declared - routed) - set(services.UNSEEDABLE_REFERENCE_LISTS))} — "
        "route it in SEED_LIST_OWNERS or say in UNSEEDABLE_REFERENCE_LISTS why it "
        "can never be seeded (DEF-017 + DEF-016)"
    )


def test_us_ten_002_tc1_def017__the_four_asset_catalogs_seed_at_provisioning(
    growth_plan, identity_seam
):
    """Routed tenancy → metering → assets (BR-TEN-013: no module writes another
    module's tables). RED on the defect: metering short-circuited meter_types to
    0 and raised KeyError for read_methods."""
    from apps.assets import models as asset_models

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        counts = {
            "meter_types": asset_models.MeterType.objects.filter(tenant=tenant).count(),
            "read_methods": asset_models.ReadMethod.objects.filter(tenant=tenant).count(),
            "asset_types": asset_models.AssetType.objects.filter(tenant=tenant).count(),
            "asset_statuses": asset_models.AssetLifecycleStage.objects.filter(
                tenant=tenant
            ).count(),
        }
    assert counts == {
        "meter_types": len(asset_services.SEED_METER_TYPES),
        "read_methods": len(asset_services.SEED_READ_METHODS),
        "asset_types": len(asset_services.SEED_ASSET_TYPES),
        "asset_statuses": len(asset_services.SEED_LIFECYCLE_STAGES),
    }


@pytest.mark.parametrize(
    "list_code,constant,keys",
    [
        ("meter_types", "SEED_METER_TYPES", ("code", "name")),
        ("read_methods", "SEED_READ_METHODS", ("code", "name")),
        ("asset_types", "SEED_ASSET_TYPES", ("code", "name", "category")),
        ("asset_statuses", "SEED_LIFECYCLE_STAGES", ("code", "name", "behavior_class")),
    ],
)
def test_us_ten_002_tc1_def017__fixture_mirrors_the_owning_modules_ratified_set(
    list_code, constant, keys
):
    """One source of law, two copies, pinned equal.

    The values are rule-cited constants in apps/assets/services.py (BR-AST-043
    meter types + read methods · BR-AST-004/009/042 types · BR-AST-031 stages
    over the A5 v4 stage set). The fixture repeats them so the platform seed is
    complete and readable — and this test is what stops the two drifting, which
    is the only real cost of the duplication."""
    ratified = [dict(zip(keys, row, strict=True)) for row in getattr(asset_services, constant)]
    assert FIXTURE[list_code] == ratified


def test_us_ten_002_tc1_def017__account_lists_seed_from_the_ratified_sets(
    growth_plan, identity_seam
):
    """SUPERSEDES `…__account_lists_are_reported_not_invented` (2026-08-10).

    That test asserted the two customers lists legitimately SKIPPED, and that
    `account_statuses` was absent from the fixture because three sources named
    three different sets. Both halves are now out of date, for two different
    reasons worth keeping straight:

      · The VALUES were never really in doubt after 2026-08-08 — BR-CUS-055
        (PO OQ-058 option b, class seed OQ-064 CLOSED) supersedes B2's
        `account_status` ENUM, A5 §Account (itself marked UNKNOWN) and the S8
        prototype card alike. The old note here reflected the pre-ruling state.
      · The MECHANISM was the real blocker, and the W2 customers SCHEMA + SEAM
        slice removed it: the module now owns its tables and authors
        `seed_reference_list`.

    RED against the pre-slice tree: no `account_statuses` table exists, the
    seam is absent, and both lists skip with zero rows.
    """
    assert [entry["code"] for entry in FIXTURE["account_statuses"]] == [
        "pending_activation",
        "active",
        "marked_disconnect",
        "vacation_hold",
        "closed",
        # BR-CUS-107 (PO 2026-08-25, closing DEF-701) — the sixth, in class
        # `non_billable`: the state a CUT account is in, which the five could
        # not express. Fixture V2.48.0.0; see
        # tests/test_br_cus_107_disconnected_status.py.
        "disconnected",
    ]
    # ⚠ **FOUR UNTIL 2026-09-17.** PO ruling *"utility can get their own account
    # types"* (`BR-CUS-1079`) makes the rows per tenant, so a fixture listing
    # four would give a new tenant FOUR types and no Agricultural, Institutional,
    # Municipal or Builder — a drift that had been there since `BR-CUS-094` and
    # was harmless only while the table was global. `V2.48.0.12`.
    assert [entry["code"] for entry in FIXTURE["account_types"]] == [
        "residential",
        "commercial",
        "industrial",
        "agricultural",
        "institutional",
        "municipal",
        "builder_developer",
        "government",
    ]
    _, result = provisioned_tenant()
    assert result["reference_seed"]["skipped"] == []
    for list_code in ("account_statuses", "account_types"):
        assert list_code not in services.UNSEEDABLE_REFERENCE_LISTS


@pytest.mark.parametrize(
    "list_code,constant,keys",
    [
        ("account_statuses", "SEED_ACCOUNT_STATUSES", ("code", "name", "behavior_class")),
        ("account_types", "SEED_ACCOUNT_TYPES", ("code", "name")),
    ],
)
def test_us_ten_002_tc1_def017__customers_fixture_mirrors_its_ratified_set(
    list_code, constant, keys
):
    """The same "one law, two copies, pinned equal" discipline the four asset
    catalogs get — applied to the two customers lists (BR-CUS-055 statuses,
    r5 #12 [D5] types)."""
    from apps.customers import services as customer_services

    ratified = [dict(zip(keys, row, strict=True)) for row in getattr(customer_services, constant)]
    assert FIXTURE[list_code] == ratified


# ══════════════════════════════════════════════════════════════════════════
# --tenant: filling a tenant that already exists (and staying idempotent)
# ══════════════════════════════════════════════════════════════════════════
def test_us_ten_002_tc3__backfill_fills_a_tenant_that_missed_a_list(growth_plan, identity_seam):
    """The operator case: a tenant provisioned before a list existed. Simulated
    by deleting one list's seed-run row and its rows, then backfilling."""
    tenant, _ = provisioned_tenant()
    actor = SimpleNamespace(id=None, pk=None)
    with tenant_ctx(tenant):
        # CR-156-BRC10 — a flat amount is an *All sizes* row now (PROTECT FK).
        rating_models.ChargeCodeAmount.objects.filter(tenant=tenant).delete()
        rating_models.Charge.objects.filter(tenant=tenant).delete()
        models.ReferenceSeedRun.objects.filter(tenant=tenant, list_code="charge_codes").delete()
        summary = services.seed_reference_data_for_tenant(tenant, actor)
        restored = rating_models.Charge.objects.filter(tenant=tenant).count()
    assert summary["seeded"] == {"charge_codes": restored}
    # Priced rows PLUS the four `pricing: per_case` codes, which seed unpriced
    # by the CR-010 A2 ruling; only the two deposit codes stay out (BR-RAT-020/023).
    assert restored == len(
        [
            e
            for e in FIXTURE["charge_codes"]
            if e.get("amount") or e.get("percent") or e.get("pricing") == "per_case"
        ]
    )


def test_us_ten_002_tc3__backfill_replay_writes_nothing(growth_plan, identity_seam):
    """BR-TEN-010 posture: a replay writes nothing and changes no count."""
    tenant, _ = provisioned_tenant()
    actor = SimpleNamespace(id=None, pk=None)
    with tenant_ctx(tenant):
        before = {
            "charges": rating_models.Charge.objects.filter(tenant=tenant).count(),
            "uoms": models.Uom.objects.filter(tenant=tenant).count(),
            "runs": models.ReferenceSeedRun.objects.filter(tenant=tenant).count(),
        }
        first = services.seed_reference_data_for_tenant(tenant, actor)
        second = services.seed_reference_data_for_tenant(tenant, actor)
        after = {
            "charges": rating_models.Charge.objects.filter(tenant=tenant).count(),
            "uoms": models.Uom.objects.filter(tenant=tenant).count(),
            "runs": models.ReferenceSeedRun.objects.filter(tenant=tenant).count(),
        }
    assert first["seeded"] == {} and second["seeded"] == {}
    assert before == after


def test_us_ten_002_tc3__backfill_never_overwrites_a_tenant_edit(growth_plan, identity_seam):
    """BR-TEN-012: a row the tenant touched survives a backfill untouched."""
    tenant, _ = provisioned_tenant()
    actor = SimpleNamespace(id=None, pk=None)
    with tenant_ctx(tenant):
        late = rating_models.Charge.objects.get(tenant=tenant, code="LATE")
        late.name = "Late fee (renamed by the tenant)"
        late.save(update_fields=["name", "updated_at"])
        models.ReferenceSeedRun.objects.filter(tenant=tenant, list_code="charge_codes").delete()
        services.seed_reference_data_for_tenant(tenant, actor)
        late.refresh_from_db()
    assert late.name == "Late fee (renamed by the tenant)"


# ══════════════════════════════════════════════════════════════════════════
# The command surface (sqlite-safe halves)
# ══════════════════════════════════════════════════════════════════════════
def test_seed_demo_check_still_writes_nothing_and_exits_zero():
    out = io.StringIO()
    call_command("seed_demo", "--check", stdout=out)  # no raise == exit 0
    assert "database vendor" in out.getvalue()
    assert not models.Tenant.objects.exists()


@pytest.mark.skipif(connection.vendor == "postgresql", reason="the refusal only fires off Postgres")
def test_seed_demo_tenant_flag_refuses_off_postgres_before_touching_tenant_tables():
    """Same Postgres guard as the demo path — tenant context is a Postgres GUC,
    so a backfill must refuse before it reads a tenant table."""
    with pytest.raises(CommandError) as excinfo:
        call_command("seed_demo", "--tenant", "brazosbend", stdout=io.StringIO())
    assert "blocked" in str(excinfo.value)


def test_seed_demo_exposes_the_backfill_flags():
    """The flags are the operator-facing half of both fixes; a rename that
    silently drops one would leave live tenants unfillable again."""
    from apps.tenancy.management.commands.seed_demo import Command

    parser = Command().create_parser("manage.py", "seed_demo")
    options = {action.dest for action in parser._actions}
    assert {"check", "tenant", "allow_empty_reference_lists"} <= options


# ══════════════════════════════════════════════════════════════════════════
# DEF-026 — the production guard is per PATH, not per COMMAND
# ══════════════════════════════════════════════════════════════════════════
# The defect: `handle()` raised the production refusal at its very first
# statement, BEFORE `options["tenant"]` was read. So `--tenant <subdomain>` —
# the reference-data backfill for a tenant that ALREADY EXISTS — could not run
# under production settings, which is the only place real tenants exist. A live
# tenant that signed up before a reference list existed was unfillable.
#
# BR-TEN-064 (CONFIRMED, PO 2026-08-10) rules the guard per path, and EP-TEN-03
# TC-12 says the three paths are asserted SEPARATELY — one test each, below,
# because "the guard differs per path" is exactly what one combined assertion
# would hide.
#
# RED on the defect (re-prove it by restoring the old ordering — move the
# refusal back to the top of `handle()`): the `--tenant` case and the `--check`
# case both fail with "seed_demo refuses under production settings"; the demo
# case stays green, which is the point of splitting them.
PRODUCTION_SETTINGS = "config.settings.production"
PRODUCTION_REFUSAL = "refuses under production settings"


@override_settings(SETTINGS_MODULE=PRODUCTION_SETTINGS)
def test_def026_tc12a__the_demo_fixture_path_still_refuses_in_production():
    """(a) UNCHANGED, and deliberately so. The demo path mints a tenant with a
    PUBLISHED owner password and echoes it in the closing summary — that must
    never touch a production database (BR-TEN-064 keeps `seed_demo`'s refusal)."""
    with pytest.raises(CommandError) as excinfo:
        call_command("seed_demo", stdout=io.StringIO())
    assert PRODUCTION_REFUSAL in str(excinfo.value)
    assert not models.Tenant.objects.exists()


@override_settings(SETTINGS_MODULE=PRODUCTION_SETTINGS)
def test_def026_tc12b__the_tenant_backfill_path_is_not_refused_in_production():
    """(b) THE FIX. `--tenant` creates no tenant, no user, no credential and no
    subscription, so the fixture-credential reason for the refusal does not
    apply to it — and production is the only host where it is any use.

    Vendor-agnostic on purpose: on sqlite the backfill still refuses, for the
    POSTGRES reason (tenant context is a Postgres GUC), and on Postgres it gets
    as far as "no such tenant". Either way the refusal it hits is no longer the
    production one, which is the whole defect. The positive case — it really
    runs and really seeds — is the Postgres-gated test below."""
    with pytest.raises(CommandError) as excinfo:
        call_command("seed_demo", "--tenant", "brazosbend", stdout=io.StringIO())
    assert PRODUCTION_REFUSAL not in str(excinfo.value)
    assert not models.Tenant.objects.exists()  # it provisions nothing, ever


@override_settings(SETTINGS_MODULE=PRODUCTION_SETTINGS)
def test_def026_tc12c__check_stays_write_free_and_exits_zero_in_production():
    """(c) `--check` is a REPORT. It writes nothing on any host, and the
    operator who most needs to read it is standing in front of the production
    box — so it exits 0 there too, and says which paths that host allows."""
    out = io.StringIO()
    call_command("seed_demo", "--check", stdout=out)  # no raise == exit 0
    report = out.getvalue()
    assert "database vendor" in report
    assert "demo-fixture seeding REFUSED here" in report
    assert "backfill RUNS here" in report
    assert not models.Tenant.objects.exists()


@requires_postgres
def test_def026_tc12b_live__backfill_really_runs_in_production_and_fills_the_tenant(
    growth_plan, identity_seam
):
    """(b) positive, on the vendor the command actually needs.

    The operator case DEF-026 blocked: a tenant that already exists, missing a
    reference list, on a host running production settings. The backfill must
    RUN, restore the list, and still provision nothing.

    RED on the defect: with the refusal at the top of `handle()` this raises
    CommandError("seed_demo refuses under production settings") and the tenant
    keeps its empty list forever."""
    tenant, _ = provisioned_tenant()
    tenants_before = models.Tenant.objects.count()
    with tenant_ctx(tenant):
        # CR-156-BRC10 — a flat amount is an *All sizes* row now (PROTECT FK).
        rating_models.ChargeCodeAmount.objects.filter(tenant=tenant).delete()
        rating_models.Charge.objects.filter(tenant=tenant).delete()
        models.ReferenceSeedRun.objects.filter(tenant=tenant, list_code="charge_codes").delete()

    out = io.StringIO()
    with override_settings(SETTINGS_MODULE=PRODUCTION_SETTINGS):
        call_command("seed_demo", "--tenant", tenant.subdomain, stdout=out)

    with tenant_ctx(tenant):
        restored = rating_models.Charge.objects.filter(tenant=tenant).count()
    # Priced rows PLUS the four `pricing: per_case` codes, which seed unpriced
    # by the CR-010 A2 ruling; only the two deposit codes stay out (BR-RAT-020/023).
    assert restored == len(
        [
            e
            for e in FIXTURE["charge_codes"]
            if e.get("amount") or e.get("percent") or e.get("pricing") == "per_case"
        ]
    )
    assert "reference-data backfill" in out.getvalue()
    # provisions nothing: no new tenant, and none of the demo fixture's own
    # objects (the published owner password never reaches this path).
    assert models.Tenant.objects.count() == tenants_before
    assert not models.Tenant.objects.filter(subdomain="brazosbend").exclude(pk=tenant.pk).exists()
