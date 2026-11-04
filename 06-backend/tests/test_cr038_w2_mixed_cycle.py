# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 W2 (2026-08-26) — the mixed-cycle honesty lane
# Rules:    BR-MET-121 ("reading is reading we store it as it comes" — the
#           days rule's import verdict is WARNING at most; the bill run owns
#           the authoritative days judgment) · BR-MET-122 (a meter not in the
#           tagged cycle is a WARNING, flagged BY NAME, never a silent import
#           and never a hard refusal) · BR-MET-129 (a warned reading POSTS,
#           flags carried onto the committed read; only errors still gate —
#           supersedes BR-MET-015's warning half; the DEF-659 rule half) ·
#           BR-MET-014 (batch tags inherit to rows unless a row overrides —
#           the coherence rule's "stated service") · BR-MET-020 (bounds stay
#           tenant/service config) · BR-MET-033 (membership stamps
#           service_points.cycle_id)
# Tests:    this file. Every guard proved RED first; the failing runs are
#           quoted verbatim in the docstrings.
# Impacts:  apps/metering/validation.py (_days_outcome docstring,
#           RULE_CYCLE_MEMBERSHIP, RULE_SERVICE_COHERENCE, ReadContext) ·
#           apps/metering/services.py (_build_context, validate_read_batch
#           per_service summary, commit_read_batch BR-MET-129 gate,
#           _post_row group-flag carry)
# ───────────────────────────────────────────────────────
"""CR-038 W2 — a mixed cycle becomes honest in the validation engine.

The three rules the PO signed 2026-08-26 (quoted verbatim where each is
enforced): BR-MET-121 (days = warning at most at import), BR-MET-122 (cycle
membership = a named warning), BR-MET-129 (warnings post; errors gate). Plus
the two CR-038 aspect-4/5 pieces those rules unblock: the service-coherence
rule (row's stated service vs the meter's real one) and the per-service batch
summary ("412 electric · 380 water · 388 gas"-shaped data).
"""

from datetime import timedelta
from decimal import Decimal

import pytest

from apps.metering import models, services, validation

from tests.test_us_met_018_plan_registers import (  # noqa: F401
    plan_with_version,
    planned_meter,
)
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    csv_body,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def ctx(**kwargs) -> validation.ReadContext:
    """A ReadContext with the boring parts filled in (the engine is pure)."""
    base = {
        "value": Decimal("1000"),
        "read_at": at("2026-08-03"),
        "channel": "total",
        "unit": "kWh",
        "multiplier": Decimal("1"),
        "register_digits": 5,
        "prior_value": Decimal("900"),
        "prior_read_at": at("2026-07-04"),
    }
    base.update(kwargs)
    return validation.ReadContext(**base)


class Config:
    """A stand-in for a `read_validation_settings` row (attribute reads only)."""

    def __init__(self, **overrides):
        defaults = dict(
            high_pct=Decimal("200"),
            high_abs_kwh=Decimal("50"),
            high_abs_kgal=Decimal("1"),
            low_pct=Decimal("25"),
            zero_scope="active_non_vacant",
            days_flag_min=25,
            days_flag_max=35,
            days_hard_min=20,
            days_hard_max=45,
            mismatch_default_pct=Decimal("3"),
            tou_sum_tolerance_pct=Decimal("1"),
        )
        defaults.update(overrides)
        for name, value in defaults.items():
            setattr(self, name, value)


def outcome_named(row, rule):
    hits = [o for o in (row.rule_outcomes or []) if o["rule"] == rule]
    return hits[0] if hits else None


def seed_cycle(tenant, code="CY-001", **overrides):
    """A cycle definition written directly — the past a test starts from."""
    fields = dict(
        frequency="Monthly", start_day=1, days_to_complete=5, bill_day=31, status="active"
    )
    fields.update(overrides)
    return models.Cycle.objects.create(tenant=tenant, code=code, **fields)


def routed_meter(actor, cycle, asset_no, *, route_code=None, service="electric", uom="kWh"):
    """A meter whose service point is STAMPED into `cycle` through the real
    route machinery (BR-MET-033: membership drives service_points.cycle_id —
    the same chain completeness._expected_meters walks)."""
    asset = a_meter(
        actor,
        asset_no,
        service=service,
        uom=uom,
        unit_label=f"Unit {asset_no}",
        address=f"1408 Bluestem Ln {asset_no}",
    )
    from apps.assets import models as asset_models

    point = asset_models.Asset.objects.get(pk=asset["id"]).service_point
    premises_id = str(models.Unit.objects.get(pk=point.unit_id).premises_id)
    services.create_route(
        actor,
        {
            "code": route_code or f"R-{asset_no}",
            "cycle_id": str(cycle.id),
            "premises_ids": [premises_id],
        },
    )
    return asset


# ═══════════════════════════════════════════════════════════════════════════
# 1 · BR-MET-121 — the days verdict is WARNING AT MOST, and that is now LAW
# ═══════════════════════════════════════════════════════════════════════════


def test_br_met_121__days_hard_tier_is_warning_at_most_never_error():
    """BR-MET-121 (PO 2026-08-26), verbatim: *"if there is an issue with
    reading days we flag it ; reading is reading we store it as it comes"* —
    clause (1): the days rule's import-time verdict is **WARNING at most**;
    the 20–45 "hard" tier keeps its distinct `hard: True` detail (so a screen
    can say "outside the hard bound") but never ERRORs.

    Measured before writing this pin: `_days_outcome` has returned WARNING
    for both tiers since 2026-08-11 — the ruling RATIFIES the behavior. This
    test turns the implementation into asserted law so drift to ERROR goes
    RED (sign-off rule 2026-08-11, part 2).

    Guard proved RED first — hard branch flipped to ERROR in the source:
        FAILED tests/test_cr038_w2_mixed_cycle.py::test_br_met_121__days_hard
        _tier_is_warning_at_most_never_error - AssertionError: BR-MET-121:
        the days verdict must be WARNING at most, got 'error' for 52 days
    """
    # 52 days — outside the 20–45 hard bound.
    hard = validation._days_outcome(
        ctx(read_at=at("2026-08-25"), prior_read_at=at("2026-07-04")), Config()
    )
    assert hard.severity == validation.WARNING, (
        f"BR-MET-121: the days verdict must be WARNING at most, got "
        f"{hard.severity!r} for {hard.detail.get('days')} days"
    )
    assert hard.detail["hard"] is True  # the distinct detail the screen reads

    # 22 days — inside the 20–45 hard bound, outside the 25–35 flag bound.
    soft = validation._days_outcome(
        ctx(read_at=at("2026-07-26"), prior_read_at=at("2026-07-04")), Config()
    )
    assert soft.severity == validation.WARNING and soft.detail["hard"] is False

    # And NO span of days ever produces ERROR — a quarterly cycle's 91-day
    # reading imports flagged, never refused (BR-MET-121's whole point).
    reference = at("2026-01-01")
    for days in (0, 1, 15, 19, 30, 46, 91, 365):
        outcome = validation._days_outcome(
            ctx(read_at=reference + timedelta(days=days), prior_read_at=reference),
            Config(),
        )
        assert outcome.severity != validation.ERROR, (days, outcome.severity)


def test_br_met_121__a_91_day_span_imports_as_a_flag_not_a_refusal():
    """The quarterly case from the ruling: *"we have to decide whether it is
    for 90 days or whrther it for 30 days or 15 days"* happens at the BILL
    RUN — at import a 91-day span is a warning with both bounds recorded."""
    outcome = validation._days_outcome(
        ctx(read_at=at("2026-10-03"), prior_read_at=at("2026-07-04")), Config()
    )
    assert outcome.severity == validation.WARNING
    assert outcome.detail["days"] == 91
    assert outcome.detail["hard_bounds"] == [20, 45]
    assert outcome.detail["hard"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 2 · BR-MET-129 — a warned reading POSTS; only errors gate
# ═══════════════════════════════════════════════════════════════════════════


def test_br_met_129__an_undispositioned_warned_row_posts_with_its_flags(brazos, marcus):
    """BR-MET-129 (PO 2026-08-26), verbatim: *"No if reading are colelcted we
    have to store the reading, we can give the warning, but we cannot reject
    the reading, when reading are colelcted then only we will know whether
    there is usage or not; otherwise, just tagging vacant and customer using
    utility services - never will be captured - there can be fraud also by
    people"*.

    THE vacant-unit case from the ruling: a first read on a meter whose unit
    has no active account warns `vacant_unit`. Nobody dispositions it. It now
    POSTS, the flag rides on the committed read's `rule_outcomes` (worked
    after commit from the Reads list — US-MET-012), and the committed read's
    `disposition` honestly stays None: nobody accepted, and the code never
    fakes that anyone did. This is the DEF-659 fix's rule half.

    Guard proved RED first — commit gate reverted to the BR-MET-015 skip
    (`"accept" if row.severity == validation.OK else None`):
        FAILED tests/test_cr038_w2_mixed_cycle.py::test_br_met_129__an_undisp
        ositioned_warned_row_posts_with_its_flags - AssertionError: assert 0 == 1
    """
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,,"))
        services.validate_read_batch(marcus, batch["id"])
        # ⚠ deliberately NO accept_warnings — the whole case.
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        staged_row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        read = models.MeterRead.objects.get(
            asset_id=asset["id"], read_at=at("2026-08-03"), channel="total"
        )

    assert staged_row.severity == "warning" and staged_row.disposition is None
    assert result["posted_reads"] == 1
    assert result["status"] == "posted" and result["batch_status"] == "posted"
    assert result["skipped_reads"] == 0 and result["skipped_rows"] == []
    # The flags are ATTACHED to the committed read (BR-MET-129 clause 1).
    vacant = [o for o in read.rule_outcomes if o["rule"] == "vacant_unit"]
    assert vacant and vacant[0]["severity"] == "warning"
    # And the read records that NOBODY dispositioned it — never a synthesized
    # accept.
    assert read.disposition is None


def test_br_met_129__errors_still_gate_the_row(brazos, marcus):
    """BR-MET-129 clause 2: *"ERRORS still refuse until a human resolves them
    — BR-MET-015's error half stands unchanged."*

    ⚠ **AMENDED 2026-08-30 — BR-MET-940 NARROWS "THE POST" TO "THE ROW"
    (CR-054 task 14), AND THE TEST IS AMENDED IN PLACE RATHER THAN DELETED.**
    Its name and its last two assertions were:

        def test_br_met_129__errors_still_gate_the_post(...)
            ...
            assert models.MeterRead.objects.count() == 0  # atomic: nothing landed
        assert caught.value.message_key == "metering.read_batch.errors_need_resolution"
        assert caught.value.params["rows"] == [2]

    The PO ruled the batch-wide refusal out — *"all or nothing will not work -
    we accept what is correct and rejct what i not correct"* — so the unknown
    meter no longer takes the WARNED row down with it. Clause 2 itself is
    untouched and is what is asserted now: the errored row does not post, and
    nothing about it is silent.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(
            marcus,
            csv_body("M-7001,2026-08-03,42864,total,,", "M-9999,2026-08-03,100,total,,"),
        )
        services.validate_read_batch(marcus, batch["id"])
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        # The warned row landed (clause 1); the errored row did not (clause 2).
        assert result["posted_reads"] == 1
        assert models.MeterRead.objects.count() == 1
        assert result["held_reads"] == 1
        assert [row["row_no"] for row in result["held_rows"]] == [2]
        assert result["held_rows"][0]["reason"] == "unresolved_error"


def test_br_met_129__a_disposition_given_is_still_honored(brazos, marcus):
    """Dispositions are no longer REQUIRED for warnings — but one GIVEN still
    rules: a rejected warned row stays out of the post, counted and named
    (the DEF-659 legibility). The seeder's explicit accept-with-reason trail
    stays legal the same way (BR-MET-129: *"its explicit accept-with-reason
    trail may stay as documentation of the demo"*)."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,,"))
        services.validate_read_batch(marcus, batch["id"])
        services.set_row_disposition(
            marcus, batch["id"], 1, {"disposition": "reject", "reason": "wrong route sheet"}
        )
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})

    assert result["posted_reads"] == 0
    assert result["status"] == "posted_nothing"
    assert result["skipped_reads"] == 1
    assert result["skipped_rows"][0]["disposition"] == "reject"


def test_br_met_129__group_flags_are_carried_onto_the_committed_read(brazos, dana):
    """BR-MET-129 clause 1, verbatim: *"WARNED rows commit with their warnings
    attached (`rule_outcomes` carry every flag onto the committed read)"* —
    EVERY flag. The group rules (plan_registers, tou_sum_sanity) are evaluated
    once per (meter, date) during batch validation and stored on the staged
    row; `_post_row` re-runs only the per-row catalog, so before this change a
    TOU meter's shortfall warning silently VANISHED at commit. Now it is
    carried, and it participates in the read's one primary status
    (BR-MET-021).

    Guard proved RED first — `_GROUP_RULES_CARRIED` emptied in the source:
        FAILED tests/test_cr038_w2_mixed_cycle.py::test_br_met_129__group_fla
        gs_are_carried_onto_the_committed_read - AssertionError: assert []
    """
    with tenant_ctx(brazos):
        seed_config()
        plan = plan_with_version(
            brazos,
            name="TOU Residential",
            model="time_of_use",
            windows=("tou_on", "tou_mid", "tou_off"),
        )
        _unit, asset = planned_meter(dana, brazos, plan, asset_no="M-7451")
        batch = stage(dana, csv_body("M-7451,2026-08-03,1200,total,,"))
        services.validate_read_batch(dana, batch["id"])
        staged_row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        assert outcome_named(staged_row, "plan_registers")["severity"] == "warning"
        # No dispositions — BR-MET-129 posts it anyway.
        services.commit_read_batch(dana, batch["id"], {"certified": True})
        read = models.MeterRead.objects.get(
            asset_id=asset["id"], read_at=at("2026-08-03"), channel="total"
        )

    carried = [o for o in read.rule_outcomes if o["rule"] == "plan_registers"]
    assert carried, [o["rule"] for o in read.rule_outcomes]
    assert carried[0]["severity"] == "warning"
    assert "tou_on" in carried[0]["detail"]["missing"]


# ═══════════════════════════════════════════════════════════════════════════
# 3 · BR-MET-122 — cycle membership, flagged by name
# ═══════════════════════════════════════════════════════════════════════════


def test_br_met_122__an_off_cycle_meter_warns_by_name(brazos, dana, marcus):
    """BR-MET-122 (PO 2026-08-26), verbatim: *"Open 1 - (a) flag as warning,
    clerk accepts with a reason"* — *"The cycle-membership rule (W2) imports
    the row, flags it by name ('M-4021 belongs to CY-002, file tagged
    CY-001') … Never a silent import (today's behavior), never a hard
    refusal."*

    Guard proved RED first — the `_cycle_membership_outcome` append removed
    from `evaluate_row` (today's silent import, reproduced):
        FAILED tests/test_cr038_w2_mixed_cycle.py::test_br_met_122__an_off_cy
        cle_meter_warns_by_name - AssertionError: BR-MET-122: the off-cycle
        meter must be flagged, not silently imported
    """
    with tenant_ctx(brazos):
        seed_config()
        cy1 = seed_cycle(brazos, "CY-001")
        cy2 = seed_cycle(brazos, "CY-002", start_day=10)
        routed_meter(dana, cy1, "M-4001")
        routed_meter(dana, cy2, "M-4021")
        batch = stage(
            marcus,
            csv_body("M-4001,2026-08-03,1000,total,,", "M-4021,2026-08-03,2000,total,,"),
            cycle_id=str(cy1.id),
        )
        services.validate_read_batch(marcus, batch["id"])
        in_cycle = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        off_cycle = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=2)

    member = outcome_named(in_cycle, "cycle_membership")
    assert member is not None and member["severity"] == "ok"

    flagged = outcome_named(off_cycle, "cycle_membership")
    assert (
        flagged is not None
    ), "BR-MET-122: the off-cycle meter must be flagged, not silently imported"
    assert flagged["severity"] == "warning"  # never a hard refusal
    assert flagged["detail"]["summary"] == "M-4021 belongs to CY-002, file tagged CY-001"
    assert flagged["detail"]["meter_cycle"] == "CY-002"
    assert flagged["detail"]["file_cycle"] == "CY-001"
    # The row IS imported (severity warning, not error — it can post).
    assert off_cycle.severity == "warning"


def test_br_met_122__a_meter_in_no_cycle_says_that_instead(brazos, marcus):
    """BR-MET-122: a meter in NO cycle states that, by name — not the wrong
    cycle's name and not silence."""
    with tenant_ctx(brazos):
        seed_config()
        cy1 = seed_cycle(brazos, "CY-001")
        a_meter(marcus, "M-4030")  # never routed — service_points.cycle_id NULL
        batch = stage(marcus, csv_body("M-4030,2026-08-03,500,total,,"), cycle_id=str(cy1.id))
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    flagged = outcome_named(row, "cycle_membership")
    assert flagged is not None and flagged["severity"] == "warning"
    assert flagged["detail"]["summary"] == "M-4030 belongs to no cycle, file tagged CY-001"
    assert flagged["detail"]["meter_cycle"] is None


def test_br_met_122__an_untagged_batch_skips_the_rule_with_its_reason(brazos, marcus):
    """A batch with no cycle tag has no membership expectation to judge — the
    rule SKIPS with a stated reason (the same posture `batch_cycle_coverage`
    takes), visible on the row and in the batch's `unevaluated_rules`."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,,"))
        summary = services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    skipped = outcome_named(row, "cycle_membership")
    assert skipped is not None and skipped["severity"] == "not_evaluated"
    assert skipped["detail"]["reason"] == "batch_not_tagged_with_cycle"
    gaps = {g["rule"]: g["reason"] for g in summary["unevaluated_rules"]}
    assert gaps.get("cycle_membership") == "batch_not_tagged_with_cycle"


def test_br_met_122_x_129__the_off_cycle_warning_posts_and_travels(brazos, dana, marcus):
    """The two rulings composed, the way the PO signed them the same day:
    BR-MET-122 flags the off-cycle row as a WARNING, and BR-MET-129 means that
    warning no longer holds the reading out — it posts undispositioned, the
    flag named on the committed read, to be worked from the Reads list. (A
    clerk's accept-with-reason remains the recorded disposition when given —
    `set_row_disposition` is unchanged.)"""
    with tenant_ctx(brazos):
        seed_config()
        cy1 = seed_cycle(brazos, "CY-001")
        cy2 = seed_cycle(brazos, "CY-002", start_day=10)
        asset = routed_meter(dana, cy2, "M-4021")
        batch = stage(marcus, csv_body("M-4021,2026-08-03,2000,total,,"), cycle_id=str(cy1.id))
        services.validate_read_batch(marcus, batch["id"])
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        read = models.MeterRead.objects.get(
            asset_id=asset["id"], read_at=at("2026-08-03"), channel="total"
        )

    assert result["posted_reads"] == 1
    flagged = [o for o in read.rule_outcomes if o["rule"] == "cycle_membership"]
    assert flagged and flagged[0]["severity"] == "warning"
    assert flagged[0]["detail"]["summary"] == "M-4021 belongs to CY-002, file tagged CY-001"


# ═══════════════════════════════════════════════════════════════════════════
# 4 · service coherence — stated vs real, both named
# ═══════════════════════════════════════════════════════════════════════════


def test_service_coherence__a_disagreeing_stated_service_warns_with_both_named(brazos, marcus):
    """CR-038 W2 aspect 4: *"a service-coherence rule (row's service vs the
    meter's real service)"*. M-7001 is an ELECTRIC meter (its service point's
    service); the row states WATER — a WARNING naming both values, because one
    of the two claims is wrong and only a person knows which.

    Guard proved RED first — the coherence append removed from
    `evaluate_row`:
        FAILED tests/test_cr038_w2_mixed_cycle.py::test_service_coherence__a_
        disagreeing_stated_service_warns_with_both_named - AssertionError:
        assert None is not None
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)  # electric, via its service point
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,water,"))
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    flagged = outcome_named(row, "service_coherence")
    assert flagged is not None
    assert flagged["severity"] == "warning"
    assert flagged["detail"]["stated_service"] == "water"
    assert flagged["detail"]["meter_service"] == "electric"
    assert flagged["detail"]["summary"] == "row says water, meter M-7001 is electric"


def test_service_coherence__nothing_stated_inherits_and_never_flags(brazos, marcus):
    """BR-MET-014: with no row column and no batch service tag the row states
    NOTHING — the read inherits the meter's own service at post, and the rule
    simply does not apply: no outcome at all, not even an ok."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,,"))  # service col empty
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    assert row.service is None  # nothing stated anywhere
    assert outcome_named(row, "service_coherence") is None


def test_service_coherence__an_inherited_batch_tag_that_matches_is_ok(brazos, marcus):
    """BR-MET-014 makes the batch tag the row's EFFECTIVE service, so a batch
    tagged electric over an electric meter records an OK coherence outcome —
    a statement was made and it agrees."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,,"), service="electric")
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    assert row.service == "electric"  # inherited from the batch tag
    agreed = outcome_named(row, "service_coherence")
    assert agreed is not None and agreed["severity"] == "ok"


def test_service_coherence__an_unrecognized_stated_value_is_a_gap_not_a_warning(brazos, marcus):
    """A stated value that means nothing in this tenant's enabled set reports
    `not_evaluated` with the value NAMED — a visible gap in the batch summary,
    never a manufactured warning and never a snap to a valid value
    (`read_import` keeps cells verbatim by law).

    ⚠ **AMENDED 2026-08-26 — THIS TEST USED TO ASSERT THAT `"E"` WAS THE GAP,
    AND BR-MET-137 SUPERSEDES THAT HALF.** The W2 lane refused to mint an
    E→electric alias, correctly: DEF-792 REPORTED that every fixture in the
    corpus carries `"E"` and that no signed document said what it meant. The PO
    then answered the reported question — *"yes accept them"* (2026-08-26) — so
    the single letter is now RATIFIED input vocabulary and `E` is tested one
    function down as an OK. What survives here unchanged is the posture the
    ruling did NOT touch: a token that resolves to nothing is still a gap.
    `"zebra"` is that token now.
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,zebra,"))
        summary = services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    gap = outcome_named(row, "service_coherence")
    assert gap is not None and gap["severity"] == "not_evaluated"
    assert gap["detail"]["reason"] == "stated_service_not_an_enabled_service"
    assert gap["detail"]["stated_service"] == "zebra"
    gaps = {g["rule"]: g["reason"] for g in summary["unevaluated_rules"]}
    assert gaps.get("service_coherence") == "stated_service_not_an_enabled_service"
    # And it is a GAP, not a verdict: the row's severity is untouched by it.
    assert row.severity != "error"


def test_br_met_137__a_single_letter_matching_the_meter_is_agreement_not_a_gap(brazos, marcus):
    """**BR-MET-137 (PO 2026-08-26, closes DEF-792): the shorthand resolves.**

    M-7001 is an ELECTRIC meter and the row states `E`. Before the ruling that
    cell was unanswerable — `not_evaluated`, on every legacy file in the corpus,
    because nothing had ever said what `E` meant. The PO said what it means, so
    it is now an **ok**: a statement was made and it agrees.

    Guard proved RED first — `resolve_stated_service` short-circuited to
    `(None, [])`:
        FAILED ...test_br_met_137__a_single_letter_matching_the_meter_is_
        agreement_not_a_gap - AssertionError: assert 'not_evaluated' == 'ok'
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    agreed = outcome_named(row, "service_coherence")
    assert agreed is not None and agreed["severity"] == "ok"
    # The RAW cell is still what the row states — BR-MET-014 keeps it verbatim;
    # the resolution is recorded BESIDE it, never written over it.
    assert agreed["detail"]["stated_service"] == "E"
    assert agreed["detail"]["resolved_service"] == "electric"


def test_br_met_137__a_single_letter_disagreeing_with_the_meter_still_warns(brazos, marcus):
    """The shorthand does not make disagreement disappear. `W` on an ELECTRIC
    meter resolves to water and then warns with both named — the same warning
    the full word `water` earns, because BR-MET-137 adds a vocabulary and
    changes no verdict."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,W,"))
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)

    flagged = outcome_named(row, "service_coherence")
    assert flagged is not None and flagged["severity"] == "warning"
    assert flagged["detail"]["stated_service"] == "W"
    assert flagged["detail"]["resolved_service"] == "water"
    assert flagged["detail"]["meter_service"] == "electric"


def test_br_met_137__an_ambiguous_letter_is_refused_with_both_candidates_named():
    """**BR-MET-137 clause 2 — the letter the product REFUSES to resolve.**

    A tenant selling both **sewer** and **solar** writes `S`. Two enabled
    services start with it, and a silently-picked one prices the wrong charge on
    somebody's bill — so the resolver returns no answer and names both, and the
    file is asked for the one character that settles it.

    ⚠ **THE SAME LETTER IS FINE NEXT DOOR, AND THAT IS THE DESIGN.** The set
    resolved against is the TENANT'S enabled services (BR-MET-003: a tenant may
    only state a service it sells), never the platform's ten-row catalogue. So
    `S` is sewer for a utility without solar and unanswerable for the one with
    both — asserted below, because a reader would reasonably expect a fixed
    alias table and this is deliberately not one.

    A pure-function test: the ambiguity needs two enabled services sharing a
    letter, which is a property of the ENABLED SET rather than of any fixture,
    and stating the set here is what makes the case readable.
    """
    from apps.metering import validation

    both = ["electric", "water", "sewer", "solar"]
    resolved, candidates = validation.resolve_stated_service("S", both)
    assert resolved is None, "an ambiguous letter must never be guessed"
    assert candidates == ["sewer", "solar"], "both candidates are named, in a stable order"

    # The neighbouring tenant, same letter, no solar — it resolves cleanly.
    sewer_only = ["electric", "water", "sewer"]
    assert validation.resolve_stated_service("S", sewer_only) == ("sewer", ["sewer"])

    # And `T` is the same shape for trash/thermal.
    trash_and_thermal = ["trash", "thermal"]
    assert validation.resolve_stated_service("t", trash_and_thermal) == (None, ["thermal", "trash"])


def test_br_met_137__the_full_service_code_still_wins_and_a_multi_letter_token_is_never_a_prefix():
    """**Clause 4: the shorthand ADDS, it replaces nothing** — and the one way
    a prefix rule goes wrong is a token that is not a single letter matching a
    longer code by accident.

    `electric` resolves as the exact match it always was. `elec` resolves to
    NOTHING — it is neither a code nor a single letter, and treating it as a
    prefix would be the alias-inventing the W2 lane refused and the PO's ruling
    did not authorise: they ratified single letters, and a signature covers only
    what was shown.
    """
    from apps.metering import validation

    enabled = ["electric", "water", "gas"]
    assert validation.resolve_stated_service("electric", enabled) == ("electric", ["electric"])
    assert validation.resolve_stated_service("ELECTRIC", enabled) == ("electric", ["electric"])
    assert validation.resolve_stated_service("elec", enabled) == (None, [])
    assert validation.resolve_stated_service("", enabled) == (None, [])
    assert validation.resolve_stated_service("E", []) == (None, []), "no enabled set, no vocabulary"


# ═══════════════════════════════════════════════════════════════════════════
# 5 · the per-service batch summary
# ═══════════════════════════════════════════════════════════════════════════


def test_per_service__the_validate_summary_counts_rows_by_service(brazos, marcus):
    """CR-038 W2 aspect 5: *"a per-service batch summary at review ('412
    electric · 380 water · 388 gas')"* — rows/ok/warnings/errors per service,
    keyed by the meter's REAL service (what the row will be judged and posted
    as), server side only. A row whose meter cannot answer falls back to its
    stated service, else "unknown".

    Guard proved RED first — the `per_service` summary line removed:
        FAILED tests/test_cr038_w2_mixed_cycle.py::test_per_service__the_vali
        date_summary_counts_rows_by_service - KeyError: 'per_service'
    """
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")  # electric
        a_meter(
            marcus,
            "W-2001",
            service="water",
            uom="kgal",
            unit_label="Unit W",
            address="1410 Bluestem Ln",
        )
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,,",  # electric — first read warns (vacant)
                "W-2001,2026-08-03,120,total,,",  # water — same
                "M-9999,2026-08-03,7,total,,",  # unknown meter — error, no service
            ),
        )
        summary = services.validate_read_batch(marcus, batch["id"])

    per_service = summary["per_service"]
    assert per_service["electric"]["rows"] == 1
    assert per_service["electric"]["warnings"] == 1
    assert per_service["electric"]["errors"] == 0
    assert per_service["water"] == {"rows": 1, "ok": 0, "warnings": 1, "errors": 0}
    assert per_service["unknown"] == {"rows": 1, "ok": 0, "warnings": 0, "errors": 1}
    # Every row is counted exactly once.
    assert sum(bucket["rows"] for bucket in per_service.values()) == 3


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 W2 task list (2026-08-26) · BR-MET-121/122/129 verbatim ·
#         BR-MET-014 · the CR-038 aspect-4/5 sentences
# generated: 2026-08-26 by the CR-038 W2 mixed-cycle lane
# checklist: A✔ B=deferred(backend-only lane by the CR task split) C✔(this
#            file — every guard RED first, runs quoted) D=deferred(no new API
#            route; the summary rides the existing validate response)
#            E=deferred(W2 frontend) F✔ G✔ H=deferred(not a 🔒 path — no
#            money, no RLS policy, no idempotency key; flags and counts only)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
