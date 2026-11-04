# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 W6 (2026-08-26) — sub-meters + devices
# Rules:    BR-MET-125 (the master-vs-subs unaccounted gap is STORED per
#           premises per period AND REPORTED — PO verbatim *"(a) store +
#           report — keeps the door open"*) · BR-MET-025 (the mismatch flag
#           itself) · BR-MET-124 (device readings are IN SCOPE) ·
#           BR-MET-135 (a device's figure lands in the `generation` register)
#           · BR-MET-020 (thresholds are tenant/service CONFIG) ·
#           CLAUDE.md hard rule 3 (an explicit unit, always)
# Tests:    this file. Every guard proved RED first; the failing runs are
#           quoted verbatim in the docstrings.
# ───────────────────────────────────────────────────────
"""CR-038 W6 — the master/sub gap becomes a real figure, and a device reads.

Three things this file pins:

1. **DEF-791's reproduction, then its repair.** The mismatch rule (BR-MET-025)
   was DEAD on the import path — `_build_context` hardcoded
   `submeter_consumption_sum=None` and nothing anywhere passed a sum.
2. **BR-MET-125's stored figure** — 460 kWh (3.71%) against a 3% tolerance,
   per premises per period, WITH its unit.
3. **BR-MET-135's `generation` channel** — a solar inverter's 612 kWh, through
   the same read pipeline, never summed with consumption.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.assets import models as asset_models
from apps.assets import services as asset_services
from apps.metering import models, selectors, services, submeter_reconciliation, validation

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    commit_read,
    csv_body,
    make_premises,
    make_unit,
    seed_config,
    seed_service_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── the fixture world: one premises, one master, two sub-meters ─────────────
#
# The BR-MET-125 worked figure, verbatim from the PO packet:
#   master 12,400 kWh − Σ subs 11,940 = 460 kWh (3.71%) against a 3% tolerance.
# Split as 5,970 + 5,970 so neither sub is the whole remainder.
MASTER_CONSUMPTION = Decimal("12400")
SUB_A_CONSUMPTION = Decimal("5970")
SUB_B_CONSUMPTION = Decimal("5970")


def a_master_with_two_subs(actor, *, service="electric", uom="kWh"):
    """One premises: a master meter on the building's own unit and two
    sub-meters (BR-AST-003 `parent_asset`) on two tenant units.

    Sub-meter-ness is DERIVED from this structure — nothing in a read file ever
    says "this row is a sub-meter".
    """
    premise = make_premises(actor, address_line="221 Cypress Row", services_available=[service])
    house = make_unit(actor, premise["id"], label="Building", services=[service])
    unit_a = make_unit(actor, premise["id"], label="Unit A", services=[service])
    unit_b = make_unit(actor, premise["id"], label="Unit B", services=[service])
    master = asset_services.create_asset(
        actor,
        {
            "type": "meter",
            "asset_no": "M-9000",
            "service": service,
            "unit": uom,
            "read_method": "walk_by",
            "multiplier": "1",
            "register_digits": 6,
            "unit_id": house["id"],
            "install_date": "2026-01-05",
            "meter_type": "master",
        },
    )
    subs = [
        asset_services.create_asset(
            actor,
            {
                "type": "sub_meter",
                "asset_no": asset_no,
                "service": service,
                "unit": uom,
                "read_method": "walk_by",
                "multiplier": "1",
                "register_digits": 6,
                "unit_id": unit["id"],
                "install_date": "2026-01-05",
                "parent_asset_no": "M-9000",
                "meter_type": "sub_meter",
            },
        )
        for asset_no, unit in (("S-9001", unit_a), ("S-9002", unit_b))
    ]
    return premise, master, subs


def a_priored_batch(actor, master, subs):
    """Prior heads at 2026-07-01, then a staged batch at 2026-08-01 carrying
    the master and both subs. Returns the batch dict."""
    commit_read(actor, master["id"], day="2026-07-01", value=0, unit="kWh")
    for sub in subs:
        commit_read(actor, sub["id"], day="2026-07-01", value=0, unit="kWh")
    body = csv_body(
        f"M-9000,2026-08-01,{MASTER_CONSUMPTION},total,electric,",
        f"S-9001,2026-08-01,{SUB_A_CONSUMPTION},total,electric,",
        f"S-9002,2026-08-01,{SUB_B_CONSUMPTION},total,electric,",
    )
    return stage(actor, body)


def _asset_row(asset_id):
    """The ORM row for an asset the service returned as a dict — the resolver
    takes the row, because sub-meter-ness is a FK and not a payload field."""
    return asset_models.Asset.objects.select_related("service_point", "service_point__unit").get(
        pk=asset_id
    )


def outcomes_for(batch_id, meter_no):
    row = models.ReadImportRow.objects.get(batch_id=batch_id, meter_no_raw=meter_no)
    return row.rule_outcomes or []


# ── 1 · DEF-791: the rule that could never fire ────────────────────────────


def test_cr038_w6_def791__the_mismatch_rule_now_fires_on_the_import_path(brazos, dana):
    """**DEF-791's reproduction, kept as the regression.**

    A master meter and its two sub-meters, validated in one batch. Run against
    the code as it stood on 2026-08-26 — before the group loop existed — it
    failed, verbatim:

        E   AssertionError: DEF-791 reproduced: no `mismatch` outcome on any
            row of a master + 2 sub-meter batch. rules seen on M-9000 =
            ['high', 'low', 'days_threshold', 'out_of_window', 'vacant_unit',
             'cycle_membership', 'service_coherence', 'factor_flag']
        E   assert 0 == 1
        E    +  where 0 = len([])

    Eight rules ran and BR-MET-025 was not among them, because
    `_build_context` hardcoded `submeter_consumption_sum=None` under a comment
    claiming the rule *"runs on the committed group, below"* and there was no
    group loop below, or anywhere else in the codebase.

    It now fires, and asserts the exact figure BR-MET-125 was signed on:
    **12,400 − 11,940 = 460 kWh (3.71%)** against **3%** → WARNING.
    """
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        _, master, subs = a_master_with_two_subs(dana)
        batch = a_priored_batch(dana, master, subs)
        services.validate_read_batch(dana, batch["id"])

        master_rules = outcomes_for(batch["id"], "M-9000")
        mismatch = [o for o in master_rules if o["rule"] == validation.RULE_MISMATCH]
        assert len(mismatch) == 1, (
            "DEF-791 reproduced: no `mismatch` outcome on any row of a master "
            "+ 2 sub-meter batch. rules seen on M-9000 = "
            f"{[o['rule'] for o in master_rules]}"
        )
        detail = mismatch[0]["detail"]
        # Compared as Decimals, not strings: the engine keeps quantities
        # UNROUNDED (B4.4 — round only at finalization/display), so the string
        # carries the multiplier's trailing scale and pinning it would pin the
        # wrong thing.
        assert Decimal(detail["master_consumption"]) == Decimal("12400")
        assert Decimal(detail["submeter_sum"]) == Decimal("11940")
        assert Decimal(detail["gap"]) == Decimal("460")
        assert Decimal(detail["gap_pct"]).quantize(Decimal("0.01")) == Decimal("3.71")
        assert Decimal(detail["tolerance_pct"]) == Decimal("3")
        assert detail["unit"] == "kWh"  # hard rule 3 — never a bare number
        assert detail["expected_submeters"] == 2
        assert detail["resolved_submeters"] == 2
        assert mismatch[0]["severity"] == validation.WARNING


def test_cr038_w6__a_sub_meter_row_carries_no_mismatch_of_its_own(brazos, dana):
    """The rule judges the MASTER, and only the master.

    A sub-meter has no sub-meters of its own, so it gets NO mismatch outcome at
    all — deliberately not an `ok` one, which a clerk would read as "this sub
    reconciled" about a check that was never run on it.
    """
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        _, master, subs = a_master_with_two_subs(dana)
        batch = a_priored_batch(dana, master, subs)
        services.validate_read_batch(dana, batch["id"])
        for meter_no in ("S-9001", "S-9002"):
            rules = [o["rule"] for o in outcomes_for(batch["id"], meter_no)]
            assert validation.RULE_MISMATCH not in rules


def test_cr038_w6__an_unread_sub_meter_skips_the_rule_it_does_not_widen_the_gap(brazos, dana):
    """**The single most damaging thing this rule could do, refused.**

    S-9002 is not in the file. Σ subs is then 5,970 and the master read 12,400,
    which LOOKS like a 6,430 kWh (51.9%) unaccounted loss — a fabricated
    catastrophe manufactured out of one meter nobody walked.

    So an incomplete Σ is `not_evaluated` with reason `submeter_sum_incomplete`
    and the missing sub NAMED, never a bigger gap.

    Guard proved RED first — `resolve_submeter_sum` returning its partial
    `total` instead of None when `resolved < expected`:
        FAILED ...::test_cr038_w6__an_unread_sub_meter_skips_the_rule_it_does_
        not_widen_the_gap - AssertionError: assert 'warning' == 'not_evaluated'
    """
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        _, master, subs = a_master_with_two_subs(dana)
        commit_read(dana, master["id"], day="2026-07-01", value=0, unit="kWh")
        for sub in subs:
            commit_read(dana, sub["id"], day="2026-07-01", value=0, unit="kWh")
        batch = stage(
            dana,
            csv_body(
                f"M-9000,2026-08-01,{MASTER_CONSUMPTION},total,electric,",
                f"S-9001,2026-08-01,{SUB_A_CONSUMPTION},total,electric,",
            ),
        )
        result = services.validate_read_batch(dana, batch["id"])

        # No verdict lands on the row at all — the skip is reported on the
        # BATCH, the same place every unevaluable rule is reported.
        rules = [o["rule"] for o in outcomes_for(batch["id"], "M-9000")]
        assert validation.RULE_MISMATCH not in rules
        unevaluated = {
            gap["rule"]: gap["reason"] for gap in (result.get("unevaluated_rules") or [])
        }
        assert unevaluated.get(validation.RULE_MISMATCH) == (
            validation.REASON_SUBMETER_SET_INCOMPLETE
        )

        # And once posted, the committed-side resolver names WHICH sub is
        # missing, so a person can go and walk it.
        services.commit_read_batch(dana, batch["id"], {"certified": True})
        resolution = submeter_reconciliation.resolve_submeter_sum(
            master=_asset_row(master["id"]), period_month=date(2026, 8, 1)
        )
        assert resolution.total is None
        assert resolution.expected == 2 and resolution.resolved == 1
        assert [u["asset_no"] for u in resolution.unresolved] == ["S-9002"]
        assert resolution.unresolved[0]["reason"] == submeter_reconciliation.UNRESOLVED_NO_READ


def test_cr038_w6__a_sub_in_another_unit_is_excluded_and_named_never_converted(brazos, dana):
    """OQ-004 / hard rule 3: units are never silently converted.

    A sub-meter reading in kgal against a kWh master cannot join the sum. It is
    EXCLUDED and named `unit_differs_from_master`, and because the set is then
    incomplete the whole group skips — a converted number would be a guess and a
    dropped one would be a fabricated loss.
    """
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        _, master, subs = a_master_with_two_subs(dana)
        a_priored_batch(dana, master, subs)
        # A committed sub read in the WRONG unit for the same month.
        commit_read(
            dana, subs[1]["id"], day="2026-08-02", value=99, unit="kgal", consumption="5970"
        )
        resolution = submeter_reconciliation.resolve_submeter_sum(
            master=_asset_row(master["id"]), period_month=date(2026, 8, 1)
        )
        assert resolution.total is None
        mismatched = [
            u
            for u in resolution.unresolved
            if u["reason"] == submeter_reconciliation.UNRESOLVED_UNIT_MISMATCH
        ]
        assert [u["asset_no"] for u in mismatched] == ["S-9002"]
        assert mismatched[0]["unit"] == "kgal"


def test_cr038_w6_br_met_125__the_gap_is_stored_per_premises_per_period(brazos, dana):
    """**BR-MET-125's whole point: the figure SURVIVES the post.**

    PO verbatim, 2026-08-26: *"Open 9 - (a) store + report — keeps the door
    open"*. One row per (premises, master, register, period) holding BOTH
    inputs, the gap WITH its unit (hard rule 3), the percentage and the
    tolerance it was judged against.

    Guard proved RED first — `_store_submeter_reconciliations` not called from
    `commit_read_batch`:
        FAILED ...::test_cr038_w6_br_met_125__the_gap_is_stored_per_premises_
        per_period - apps.metering.models.PremisesSubmeterReconciliation.
        DoesNotExist: PremisesSubmeterReconciliation matching query does not
        exist.
    """
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        premise, master, subs = a_master_with_two_subs(dana)
        batch = a_priored_batch(dana, master, subs)
        services.validate_read_batch(dana, batch["id"])
        services.commit_read_batch(dana, batch["id"], {"certified": True})

        row = models.PremisesSubmeterReconciliation.objects.get(
            premises_id=premise["id"], master_asset_id=master["id"]
        )

    assert row.period_month == date(2026, 8, 1)
    assert row.channel == "total"
    assert row.status == models.PremisesSubmeterReconciliation.STATUS_COMPUTED
    assert row.master_consumption == Decimal("12400.000000")
    assert row.submeter_sum == Decimal("11940.000000")
    assert row.gap_quantity == Decimal("460.000000")
    assert row.gap_pct.quantize(Decimal("0.01")) == Decimal("3.71")
    assert row.tolerance_pct == Decimal("3.000000")
    assert row.within_tolerance is False
    assert row.unit == "kWh"  # hard rule 3 — the stored quantity carries it
    assert row.submeter_count == 2 and row.submeters_resolved == 2
    assert row.unresolved_submeters == []
    assert row.computed_at is not None


def test_cr038_w6_br_met_125__an_uncomputable_gap_is_stored_as_an_absence(brazos, dana):
    """A `not_evaluated` group stores NULL quantities and its REASON — never a
    zero gap, which reads as "this building reconciled perfectly" and is the
    opposite of what happened."""
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        premise, master, subs = a_master_with_two_subs(dana)
        commit_read(dana, master["id"], day="2026-07-01", value=0, unit="kWh")
        for sub in subs:
            commit_read(dana, sub["id"], day="2026-07-01", value=0, unit="kWh")
        batch = stage(dana, csv_body(f"M-9000,2026-08-01,{MASTER_CONSUMPTION},total,electric,"))
        services.validate_read_batch(dana, batch["id"])
        services.commit_read_batch(dana, batch["id"], {"certified": True})

        row = models.PremisesSubmeterReconciliation.objects.get(
            premises_id=premise["id"], master_asset_id=master["id"]
        )

    assert row.status == models.PremisesSubmeterReconciliation.STATUS_NOT_EVALUATED
    assert row.reason == validation.REASON_SUBMETER_SET_INCOMPLETE
    assert row.gap_quantity is None and row.gap_pct is None and row.submeter_sum is None
    assert row.unit == "kWh"  # still explicit — the report says WHICH kWh are missing
    assert row.submeter_count == 2 and row.submeters_resolved == 0
    assert sorted(u["asset_no"] for u in row.unresolved_submeters) == ["S-9001", "S-9002"]


def test_cr038_w6_br_met_020__no_tolerance_anywhere_skips_and_reports(brazos, dana):
    """BR-MET-020's fail-safe reaches this rule too: with no `mismatch_pct` on
    the master and no config row for the service, the gap is NOT judged against
    an invented 3%."""
    with tenant_ctx(brazos):
        resolution = submeter_reconciliation.SubmeterResolution(
            expected=2, resolved=2, total=Decimal("11940"), unit="kWh"
        )
        outcome = validation.submeter_mismatch(
            master_consumption=Decimal("12400"),
            submeter_sum=resolution.total,
            unit="kWh",
            tolerance_pct=None,
            config=None,
            expected_submeters=2,
            resolved_submeters=2,
        )
    assert outcome.severity == validation.NOT_EVALUATED
    assert outcome.detail["reason"] == validation.REASON_NO_CONFIG


def test_cr038_w6_br_met_025__the_masters_own_tolerance_beats_the_service_default(brazos, dana):
    """BR-MET-025's precedence, on the LIVE path: a master carrying
    `loss_tolerance_pct = 5` reconciles at 3.71% and the same batch that warned
    above now passes."""
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        _, master, subs = a_master_with_two_subs(dana)
        asset_row = _asset_row(master["id"])
        asset_row.loss_tolerance_pct = Decimal("5")
        asset_row.save(update_fields=["loss_tolerance_pct"])
        batch = a_priored_batch(dana, master, subs)
        services.validate_read_batch(dana, batch["id"])
        mismatch = [
            o for o in outcomes_for(batch["id"], "M-9000") if o["rule"] == validation.RULE_MISMATCH
        ]
    assert len(mismatch) == 1
    assert mismatch[0]["severity"] == validation.OK
    assert Decimal(mismatch[0]["detail"]["tolerance_pct"]) == Decimal("5")


def test_cr038_w6__the_reconciliation_row_is_tenant_scoped(brazos, lonestar, dana, erin):
    """CLAUDE.md hard rule 1 at the app layer — the live-Postgres RLS proof
    rides the G5 isolation sweep (migration 0033)."""
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        _, master, subs = a_master_with_two_subs(dana)
        batch = a_priored_batch(dana, master, subs)
        services.validate_read_batch(dana, batch["id"])
        services.commit_read_batch(dana, batch["id"], {"certified": True})
        assert (
            models.PremisesSubmeterReconciliation.objects.filter(tenant_id=brazos.id).count() == 1
        )
    with tenant_ctx(lonestar):
        assert (
            models.PremisesSubmeterReconciliation.objects.filter(tenant_id=lonestar.id).count() == 0
        )


# ── 2 · the REPORT half of BR-MET-125 ──────────────────────────────────────


def test_cr038_w6_br_met_125__the_premises_report_serves_the_stored_gap(brazos, dana):
    """The other half of *"store + report"*: a premises-level view of master vs
    Σ subs, per period, reading the STORED row and computing nothing."""
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        premise, master, subs = a_master_with_two_subs(dana)
        batch = a_priored_batch(dana, master, subs)
        services.validate_read_batch(dana, batch["id"])
        services.commit_read_batch(dana, batch["id"], {"certified": True})

        report = selectors.premises_submeter_reconciliation(premise["id"])

    assert report["has_masters"] is True
    assert report["periods"] == ["2026-08-01"]
    assert len(report["rows"]) == 1
    row = report["rows"][0]
    assert row["master_asset_no"] == "M-9000"
    assert row["service_code"] == "electric"
    assert row["unit"] == "kWh"
    assert Decimal(row["master_consumption"]) == Decimal("12400")
    assert Decimal(row["submeter_sum"]) == Decimal("11940")
    assert Decimal(row["gap_quantity"]) == Decimal("460")
    assert Decimal(row["gap_pct"]).quantize(Decimal("0.01")) == Decimal("3.71")
    assert Decimal(row["tolerance_pct"]) == Decimal("3")
    # Hard rule 2 — percentages DISPLAY 2, and the rounding is the SERVER's, so
    # two surfaces cannot come to disagree about the same percentage.
    assert row["gap_pct_display"] == "3.71%"
    assert row["tolerance_pct_display"] == "3.00%"
    assert row["within_tolerance"] is False
    assert row["status"] == "computed"
    assert row["submeter_count"] == 2 and row["submeters_resolved"] == 2


def test_cr038_w6__a_premises_with_no_masters_says_so_rather_than_showing_zero(brazos, dana):
    """An EMPTY report is not "this building reconciles". A premises with no
    master meter has nothing to reconcile and the payload says which of the two
    it is, so the screen draws a sentence instead of a table of zero gaps."""
    with tenant_ctx(brazos):
        seed_config()
        premise = make_premises(dana, address_line="9 Lone Oak", services_available=["electric"])
        unit = make_unit(dana, premise["id"], label="Unit A", services=["electric"])
        a_meter(dana, asset_no="M-8000", unit_id=unit["id"])
        report = selectors.premises_submeter_reconciliation(premise["id"])
    assert report["has_masters"] is False
    assert report["rows"] == [] and report["periods"] == []


def test_cr038_w6__the_report_period_filter_narrows_to_one_month(brazos, dana):
    """`?period=YYYY-MM` narrows; `periods` still lists every stored month, so a
    picker only ever offers real ones."""
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        premise, master, subs = a_master_with_two_subs(dana)
        batch = a_priored_batch(dana, master, subs)
        services.validate_read_batch(dana, batch["id"])
        services.commit_read_batch(dana, batch["id"], {"certified": True})

        august = selectors.premises_submeter_reconciliation(
            premise["id"], period_month=date(2026, 8, 1)
        )
        september = selectors.premises_submeter_reconciliation(
            premise["id"], period_month=date(2026, 9, 1)
        )

    assert len(august["rows"]) == 1 and august["period_month"] == "2026-08-01"
    assert september["rows"] == []
    # An unread month is ABSENT, never a zero-gap row — and the picker still
    # knows August exists.
    assert september["periods"] == ["2026-08-01"]


def test_cr038_w6__the_report_endpoint_is_ROUTED_not_merely_written():
    """**Hard-won law 2: built is not wired.**

    A selector nothing serves and a view in no `urlpatterns` are both invisible
    — every test passes and the feature does not exist. This resolves the real
    URL through the project's own router.

    Guard proved RED first — the `path(...)` line removed from
    `apps/metering/api.py`:
        FAILED ...::test_cr038_w6__the_report_endpoint_is_ROUTED_not_merely_
        written - django.urls.exceptions.Resolver404: {'tried': [...], 'path':
        'api/acme/premises/.../submeter-reconciliation'}
    """
    from django.urls import resolve

    from apps.metering import api as metering_api

    match = resolve(
        "/api/acme/premises/01a03f60-3230-7616-b19c-9a53490a5d22/submeter-reconciliation"
    )
    assert match.func is metering_api.premises_submeter_reconciliation


# ── 3 · DEVICE READINGS (BR-MET-124 + BR-MET-135) ──────────────────────────
#
# PO 2026-08-26, verbatim, reversing the on-file recommendation: *"It is not out
# of scope we will ahve to accept the reading if it comes; curently we are
# onboarding solar based utility and they will need it"*. And on the register:
# *"please add generation"*.
#
# The driving figure is a solar inverter's **612 kWh** in a month.
INVERTER_GENERATION = Decimal("612")


def a_solar_inverter(actor, *, asset_no="PV-1001", uom="kWh", unit_id=None, service="electric"):
    """A PV inverter — `asset_types.category == behind_the_meter`, which is the
    ONE fact that makes it a device rather than a meter.

    Note what it does NOT have: BR-AST-009 requires a service and a UoM only on
    MEASURING types, so a device is lawfully created without either. The unit
    is passed here because a reading needs one (hard rule 3) — the test below
    covers the device that has none.
    """
    if unit_id is None:
        premise = make_premises(actor, address_line="77 Sunfield Way", services_available=[service])
        unit_id = make_unit(actor, premise["id"], label="Roof", services=[service])["id"]
    return asset_services.create_asset(
        actor,
        {
            "type": "pv",
            "asset_no": asset_no,
            "unit": uom,
            "unit_id": unit_id,
            "install_date": "2026-01-05",
        },
    )


def test_cr038_w6_br_met_135__generation_is_in_the_channel_vocabulary():
    """*"please add generation"* — a new VALUE, never a schema change: the
    register list is deliberately extensible (B2 r8 / BR-MET-059)."""
    assert models.CHANNEL_GENERATION == "generation"
    assert models.CHANNEL_GENERATION in models.CHANNELS
    # And it is named as NOT consumption, beside `export`, so anything summing
    # usage excludes both by one constant rather than by two memories.
    assert set(models.NON_CONSUMPTION_CHANNELS) == {"export", "generation"}


def test_cr038_w6_br_met_124__a_device_reading_posts_through_the_same_pipeline(brazos, dana):
    """**BR-MET-124: a reading that comes is ACCEPTED.** A solar inverter's 612
    kWh enters through the ordinary read import — same batch, same validate,
    same commit — against the DEVICE asset.

    Guard proved RED first — `generation` removed from `models.CHANNELS`,
    verbatim:
        E   core.errors.BizError: BIZ-COMPLETENESS
            (metering.read_batch.errors_need_resolution)

    That is the whole of BR-MET-124 before the ruling: the importer reported
    `channel_unknown`, kept the value verbatim (never snapping it to a valid
    register), and the batch refused to post. The utility's reading arrived and
    the product had nowhere to put it.
    """
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        device = a_solar_inverter(dana)
        batch = stage(dana, csv_body(f"PV-1001,2026-08-01,{INVERTER_GENERATION},generation,,"))
        services.validate_read_batch(dana, batch["id"])
        result = services.commit_read_batch(dana, batch["id"], {"certified": True})
        read = models.MeterRead.objects.get(asset_id=device["id"], channel="generation")

    assert result["posted_reads"] == 1
    # ⚠ THE FIGURE IS THE FIGURE. A device has no register in the meter sense,
    # so nothing is subtracted from a prior: 612 in, 612 stored.
    assert read.consumption == Decimal("612.000000")
    assert read.unit == "kWh"  # hard rule 3 — explicit, always
    assert read.channel == "generation"


def test_cr038_w6_br_met_124__the_meter_rules_that_cannot_apply_are_SKIPPED_AND_REPORTED(
    brazos, dana
):
    """**BR-MET-124, verbatim: *"the sixteen meter rules that do not apply are
    skipped and reported, never faked"*.**

    Six of them, each reported with its reason on the row — so "no warnings on
    this inverter" can never quietly mean "we judged its production against a
    consumption threshold and it looked fine".
    """
    with tenant_ctx(brazos):
        seed_config()
        seed_service_config("electric", mismatch_pct=Decimal("3"))
        a_solar_inverter(dana)
        batch = stage(dana, csv_body(f"PV-1001,2026-08-01,{INVERTER_GENERATION},generation,,"))
        services.validate_read_batch(dana, batch["id"])
        outcomes = outcomes_for(batch["id"], "PV-1001")

    by_rule = {o["rule"]: o for o in outcomes}
    for rule in validation.DEVICE_SKIPPED_RULES:
        assert rule in by_rule, f"{rule} vanished instead of being reported"
        assert by_rule[rule]["severity"] == validation.NOT_EVALUATED
        assert by_rule[rule]["detail"]["reason"] == validation.REASON_DEVICE_READ
    # The rules that DO bind a device still ran — this is the same pipeline,
    # not a bypass.
    assert by_rule[validation.RULE_GENERATION_CHANNEL]["severity"] == validation.OK
    assert validation.RULE_DAYS_THRESHOLD in by_rule
    assert validation.RULE_OUT_OF_WINDOW in by_rule
    # And no meter rule sneaked a verdict onto it.
    assert validation.RULE_EXPORT_NOT_NET not in by_rule


def test_cr038_w6_br_met_135__generation_on_a_METER_is_refused_by_name(brazos, dana):
    """`generation` is a DEVICE's register. On a meter the file means `export`
    or it means the wrong asset — and neither is guessed, because putting a
    site's production into a meter's registers is how it becomes billed usage.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(dana, asset_no="M-7001")
        batch = stage(dana, csv_body("M-7001,2026-08-01,612,generation,,"))
        services.validate_read_batch(dana, batch["id"])
        outcomes = outcomes_for(batch["id"], "M-7001")

    refusal = [o for o in outcomes if o["rule"] == validation.RULE_GENERATION_CHANNEL]
    assert len(refusal) == 1
    assert refusal[0]["severity"] == validation.ERROR
    assert refusal[0]["detail"]["reason"] == "generation_on_a_meter"
    # The row is REFUSED, not snapped to `export`.
    assert "use_export_channel" in refusal[0]["detail"]["resolutions"]


def test_cr038_w6_br_met_135__a_device_reading_on_a_consumption_register_is_refused(brazos, dana):
    """The mirror, and the one that protects a bill: a PV inverter's figure
    arriving on `total` is generation about to be billed as usage. Refused."""
    with tenant_ctx(brazos):
        seed_config()
        a_solar_inverter(dana)
        batch = stage(dana, csv_body(f"PV-1001,2026-08-01,{INVERTER_GENERATION},total,,"))
        services.validate_read_batch(dana, batch["id"])
        outcomes = outcomes_for(batch["id"], "PV-1001")

    refusal = [o for o in outcomes if o["rule"] == validation.RULE_GENERATION_CHANNEL]
    assert len(refusal) == 1
    assert refusal[0]["severity"] == validation.ERROR
    assert refusal[0]["detail"]["reason"] == "device_reading_on_a_consumption_register"


def test_cr038_w6__a_device_with_no_uom_is_refused_with_the_DEVICE_resolution(brazos, dana):
    """CLAUDE.md hard rule 3 has no "assume kWh" branch, and BR-AST-009 lets a
    device carry no UoM at all — so this is the first thing a real device
    reading meets. The refusal names the DEVICE's own fix, because "set the
    meter's UoM" sends a clerk to the wrong screen."""
    with tenant_ctx(brazos):
        seed_config()
        premise = make_premises(
            dana, address_line="79 Sunfield Way", services_available=["electric"]
        )
        unit = make_unit(dana, premise["id"], label="Roof", services=["electric"])
        device = asset_services.create_asset(
            dana,
            {
                "type": "pv",
                "asset_no": "PV-1002",
                "unit_id": unit["id"],
                "install_date": "2026-01-05",
            },
        )
        assert _asset_row(device["id"]).unit in (None, "")  # lawful, per BR-AST-009
        batch = stage(dana, csv_body("PV-1002,2026-08-01,612,generation,,"))
        services.validate_read_batch(dana, batch["id"])
        outcomes = outcomes_for(batch["id"], "PV-1002")

    missing = [o for o in outcomes if o["rule"] == validation.RULE_UNIT_MISSING]
    assert len(missing) == 1
    assert missing[0]["severity"] == validation.ERROR
    assert "set_device_uom" in missing[0]["detail"]["resolutions"]


def test_cr038_w6__a_generation_read_never_lands_on_the_billing_seam(brazos, dana):
    """**"never summed with consumption"** — asserted against
    `billing_reads_for_unit`, the seam BILLING reads for a period's usage.

    ⚠ **AND THIS CASE ALONE DOES NOT PROVE THE EXCLUDE LIST.** Run with
    `models.NON_CONSUMPTION_CHANNELS` removed from
    `billing_reads_for_unit`'s exclusion it still PASSED — because a device is a
    non-measuring type (BR-AST-009), so `create_asset` gives it NO service
    point, and the seam walks service points. A generation read therefore never
    enters that queryset in the first place.

    That is a real second line of defence and it is worth pinning — a future
    lane that gives devices service points would break it and this would go red.
    But the exclude list is proved by the net-meter case BELOW, which is where
    the live defect was. Written down because a guard that cannot fail is worse
    than no guard (DEF-182's lesson), and this one nearly shipped claiming a RED
    it had never produced.
    """
    with tenant_ctx(brazos):
        seed_config()
        premise = make_premises(
            dana, address_line="81 Sunfield Way", services_available=["electric"]
        )
        unit = make_unit(dana, premise["id"], label="Roof", services=["electric"])
        meter = a_meter(dana, asset_no="M-7300", unit_id=unit["id"])
        a_solar_inverter(dana, asset_no="PV-1003", unit_id=unit["id"])
        commit_read(
            dana,
            meter["id"],
            day="2026-08-01",
            value=42864,
            consumption="684",
            unit="kWh",
        )
        # The device's own production, on the same unit, in the same period.
        batch = stage(dana, csv_body(f"PV-1003,2026-08-01,{INVERTER_GENERATION},generation,,"))
        services.validate_read_batch(dana, batch["id"])
        services.commit_read_batch(dana, batch["id"], {"certified": True})

        billed = selectors.billing_reads_for_unit(
            unit["id"], period_start=date(2026, 8, 1), period_end=date(2026, 8, 31)
        )

    electric = [row for row in billed if row["service_code"] == "electric"]
    assert len(electric) == 1
    # The METER's 684 kWh — not 612, and not 1,296.
    assert str(electric[0]["consumption"]) == "684.000000"
    assert electric[0]["absent_reason"] is None


def test_cr038_w6__a_net_meters_EXPORT_row_never_becomes_its_billed_consumption(brazos, dana):
    """**A LIVE DEFECT ON THE MONEY PATH, FOUND BY THIS LANE — REPORTED for a
    defect row.**

    `billing_reads_for_unit` excluded the TOU windows and `demand` from the
    "latest head" race and NOT `export` — while `_ensure_export_records` writes
    a net meter's export row with the SAME `read_at` as its total row and a
    LATER uuid7 id (BR-AST-029: one 0-value, review-flagged export record per
    net-metering cycle that has none). Ordered `-read_at, -id`, the EXPORT row
    won, and because its status is `missing` the whole service reported
    `absent_reason: flagged` — a net meter's real **684 kWh never reached a
    bill**.

    `generation` (BR-MET-135) is the same hazard on new equipment, which is why
    both are excluded by one named constant.

    Guard proved RED first — `NON_CONSUMPTION_CHANNELS` removed from the
    exclusion, verbatim:
        E       AssertionError: the export row won the latest-head race:
                consumption=None absent=read_flagged
        E       assert 'read_flagged' is None

    Note `consumption=None`, not a wrong number: the export row's status is
    `missing`, so the seam reported the whole electric service as FLAGGED and
    billing had no usage at all for a meter that had been read.
    """
    with tenant_ctx(brazos):
        seed_config()
        premise = make_premises(
            dana, address_line="83 Sunfield Way", services_available=["electric"]
        )
        unit = make_unit(dana, premise["id"], label="Unit A", services=["electric"])
        net = asset_services.create_asset(
            dana,
            {
                "type": "net_meter",  # BR-AST-010: net metering is locked ON
                "asset_no": "M-7400",
                "service": "electric",
                "unit": "kWh",
                "read_method": "walk_by",
                "multiplier": "1",
                "register_digits": 6,
                "unit_id": unit["id"],
                "install_date": "2026-01-05",
            },
        )
        commit_read(dana, net["id"], day="2026-07-01", value=42180, unit="kWh")
        batch = stage(dana, csv_body("M-7400,2026-08-01,42864,total,electric,"))
        services.validate_read_batch(dana, batch["id"])
        services.commit_read_batch(dana, batch["id"], {"certified": True})

        # The export half really was written — this is the row that used to win.
        assert models.MeterRead.objects.filter(
            asset_id=net["id"], channel="export", read_at=at("2026-08-01")
        ).exists()

        billed = selectors.billing_reads_for_unit(
            unit["id"], period_start=date(2026, 8, 1), period_end=date(2026, 8, 31)
        )

    electric = [row for row in billed if row["service_code"] == "electric"]
    assert len(electric) == 1
    assert electric[0]["absent_reason"] is None, (
        "the export row won the latest-head race: "
        f"consumption={electric[0]['consumption']} absent={electric[0]['absent_reason']}"
    )
    assert str(electric[0]["consumption"]) == "684.000000"
