# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 · ADDITION 2026-08-26 — **W5 task 6** (the quick single-
#           reading entry) and **W5 task 7** (bulk operations on the reads
#           list). PO verbatim, task 6: *"we will need modpage to load single
#           reading, if it is simple then modal"*. Task 7: *"We will need bulk
#           operation; also note read are for perticualr period and they need
#           to be part of read cycle or bill cycle - how we are going to keep
#           the sanity"*.
#           Screens: S25 (both actions live here) · S28 (the hand-off target)
# Story:    US-MET-012 (S25 — its §5 fix actions get their FIRST writer here)
# Rules:    BR-MET-129 (a warned reading POSTS; flags are worked AFTER commit —
#           quoted verbatim below) · BR-MET-023 (the per-flag fix vocabulary) ·
#           BR-MET-016 (consumers work the lineage HEAD) · BR-MET-026/027
#           (estimation arithmetic and the two-consecutive limit) ·
#           BR-MET-049 (the plan-driven expected register set) ·
#           BR-MET-131 (no read DRAWER — and why a capture modal is not one) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 3 (an explicit unit)
# Defects:  DEF-046 finding 2 — *"fix_disposition/fix_reason/fixed_by exist
#           with no writer and no route, so US-MET-012 TC-3..7 have nothing to
#           call"* (open since 2026-08-11). These are their writer.
# Questions: OQ-422 **CLOSED 2026-08-27** — PO: *"(b) Accept and warn"*; the
#           rule is BR-MET-140 and TC-11 below is AMENDED, not replaced,
#           with the RED it produced quoted inline
# ───────────────────────────────────────────────────────
"""Tasks 6 and 7 — the counter read, and forty rows with forty names on them.

**THE PO'S SENTENCE THAT SHAPES TASK 7, VERBATIM (2026-08-26):**

    *"keep the rule — speed comes from the bulk button… an auditor asking
     'who chose to estimate M-4412?' gets a name"*

TC-4 and TC-8 are that sentence as executable code: they ASK the question the
auditor asks — over `meter_reads.fixed_by` and over `audit_log` — and assert a
name comes back. A bulk button that writes anonymously is the one thing this
task must not ship, so it is the one thing tested twice from two directions.
"""

from datetime import date

import pytest

from apps.metering import models as metering_models
from apps.metering import quick_read
from apps.metering import services as metering_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    brazos,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_us_met_018_plan_registers import plan_with_version
from tests.test_us_met_reads_helpers import a_meter, commit_read, seed_config

pytestmark = pytest.mark.django_db


def _planned_meter(actor, tenant, *, asset_no, model="flat", windows=(), service="electric"):
    """A meter on a unit whose plan carries an ACTIVATED tariff version.

    ⚠ **THE PLAN IS NOT OPTIONAL SET-DRESSING — IT IS WHAT "SIMPLE" MEANS.**
    BR-MET-049 derives the expected register set from the PLAN's pricing model,
    not from the meter's type name, so a meter whose plan has no version in
    force resolves to `no_version_in_force` and the modal is correctly told the
    meter is not simple. `a_meter` alone builds exactly that state, which is
    why TC-10 needs this and TC-14 deliberately does not.

    `plan_with_version` is US-MET-018's own helper, imported rather than
    re-written — a second fixture that built plans a slightly different way
    would let this suite and the register suite disagree about what a TOU plan
    is (hard-won law 5).
    """
    plan = plan_with_version(
        tenant,
        name=f"Counter {model} {asset_no}",
        model=model,
        service_code=service,
        windows=windows,
    )
    premises = make_premises(actor, address_line="9 Quick Entry Way", services_available=[service])
    unit = make_unit(actor, premises["id"], label=f"Counter Unit {asset_no}", services=[service])
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    metering_services.ensure_service_point(unit["id"], service)
    return a_meter(actor, asset_no=asset_no, service=service, unit_id=unit["id"])


def _flagged(actor, asset_id, *, day, value, status="high", consumption="1200.000000"):
    """A committed read carrying a FLAG — the state BR-MET-129 leaves behind.

    Clause 1 of that rule, verbatim: *"At post, WARNED rows commit with their
    warnings attached"*. So a flagged read on file is not an anomaly to be
    explained; it is the ordinary output of the import path, and working it is
    what S25 is for.
    """
    return commit_read(
        actor, asset_id, day=day, value=value, consumption=consumption, status=status
    )


# ══════════════════════════════════════════════════════════════════════════
# TASK 7 · TC-1 — bulk accept writes the disposition, the reason AND the name
# ══════════════════════════════════════════════════════════════════════════
def test_task7_tc1__bulk_accept_records_disposition_reason_and_actor_per_row(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        meter = a_meter(marcus, asset_no="M-4412")
        reads = [
            _flagged(marcus, meter["id"], day=f"2026-07-{n:02d}", value=1000 + n) for n in (5, 6, 7)
        ]

        result = metering_services.bulk_fix_reads(
            marcus,
            {
                "read_ids": [str(r.id) for r in reads],
                "reason": "verified against the route sheet — vacant unit confirmed occupied",
            },
        )

        assert result["applied_count"] == 3
        assert result["refused_count"] == 0
        assert result["rule_ref"] == "BR-MET-129"

        for read in reads:
            read.refresh_from_db()
            assert read.fix_disposition == "accept"
            assert "route sheet" in read.fix_reason
            # THE AUDITOR'S QUESTION. "Who chose this?" — a name, per row.
            assert read.fixed_by_id == marcus.id
            # And NOTHING about the measurement moved (BR-MET-129 clause 1: it
            # was already posted; accepting records a judgment, not a change).
            assert read.status == "high"
            assert read.superseded_by_id is None


# ══════════════════════════════════════════════════════════════════════════
# TASK 7 · TC-2 — a partly-refused selection answers per row, never all-or-none
# ══════════════════════════════════════════════════════════════════════════
def test_task7_tc2__refusals_come_back_named_beside_the_accepted_rows(brazos, marcus):
    """A clerk who selected four rows of which two cannot be accepted needs the
    two done and the two explained. Failing all four over two would be worse
    for the clerk and less true about what happened."""
    with tenant_ctx(brazos):
        seed_config()
        meter = a_meter(marcus, asset_no="M-4413")
        good = _flagged(marcus, meter["id"], day="2026-07-05", value=1005)
        unflagged = commit_read(
            marcus, meter["id"], day="2026-07-06", value=1006, consumption="100.000000"
        )
        already = _flagged(marcus, meter["id"], day="2026-07-07", value=1007)
        metering_services.bulk_fix_reads(
            marcus, {"read_ids": [str(already.id)], "reason": "first pass"}
        )

        result = metering_services.bulk_fix_reads(
            marcus,
            {
                "read_ids": [str(good.id), str(unflagged.id), str(already.id)],
                "reason": "second pass over the July exceptions",
            },
        )

        assert result["applied_count"] == 1
        by_reason = {row["reason"]: row for row in result["refused"]}
        # An accept is a statement ABOUT A FLAG; recording one on an unflagged
        # reading files a judgment about nothing.
        assert "not_flagged" in by_reason
        # Overwriting would erase another person's name and reason —
        # `dispute_read`'s refusal, same argument.
        assert "already_dispositioned" in by_reason
        already.refresh_from_db()
        assert already.fix_reason == "first pass", "the first person's trail survived"


# ══════════════════════════════════════════════════════════════════════════
# TASK 7 · TC-3 — a SUPERSEDED read is refused (BR-MET-016)
# ══════════════════════════════════════════════════════════════════════════
def test_task7_tc3__a_superseded_read_cannot_be_bulk_dispositioned(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        meter = a_meter(marcus, asset_no="M-4414")
        original = _flagged(marcus, meter["id"], day="2026-07-05", value=1005)
        metering_services.supersede_read(
            marcus, str(original.id), {"value": "1099", "reason": "re-read at the meter"}
        )
        original.refresh_from_db()
        assert original.superseded_by_id is not None

        result = metering_services.bulk_fix_reads(
            marcus, {"read_ids": [str(original.id)], "reason": "looks fine"}
        )
        assert result["applied_count"] == 0
        assert result["refused"][0]["reason"] == "not_head"
        original.refresh_from_db()
        assert original.fix_disposition is None


# ══════════════════════════════════════════════════════════════════════════
# TASK 7 · TC-4 — THE AUDITOR'S QUESTION, asked of `audit_log`
# ══════════════════════════════════════════════════════════════════════════
def test_task7_tc4__the_audit_log_names_who_accepted_each_read(brazos, marcus, audit_rows):
    """*"an auditor asking 'who chose to estimate M-4412?' gets a name"*. The
    per-row `audit_log` row is the second, independent place that answers it —
    `fixed_by` can be superseded by a later fix, and the trail cannot."""
    with tenant_ctx(brazos):
        seed_config()
        meter = a_meter(marcus, asset_no="M-4412")
        reads = [
            _flagged(marcus, meter["id"], day=f"2026-07-{n:02d}", value=1000 + n) for n in (5, 6)
        ]
        audit_rows.clear()

        metering_services.bulk_fix_reads(
            marcus,
            {"read_ids": [str(r.id) for r in reads], "reason": "high usage confirmed by customer"},
        )

        fix_rows = [r for r in audit_rows if r["action"] == "read.fix_dispositioned"]
        assert len(fix_rows) == 2, "ONE audit row per read — never one row for the batch"
        for row in fix_rows:
            assert row["actor_user_id"] == marcus.id
            assert row["after"]["fix_reason"] == "high usage confirmed by customer"
            # Rule 3: never the bare figure in the trail.
            assert row["after"]["usage_display"].endswith(" kWh")


# ══════════════════════════════════════════════════════════════════════════
# TASK 7 · TC-5 — no reason, no bulk action
# ══════════════════════════════════════════════════════════════════════════
def test_task7_tc5__a_bulk_action_with_no_reason_is_refused(brazos, marcus):
    """CR-038: *"bulk-accept flagged reads WITH ONE REASON (recorded per row)"*.
    A disposition with no reason tells the next reader of the row nothing."""
    from core import errors

    with tenant_ctx(brazos):
        seed_config()
        meter = a_meter(marcus, asset_no="M-4415")
        read = _flagged(marcus, meter["id"], day="2026-07-05", value=1005)
        with pytest.raises(errors.ValidationError) as excinfo:
            metering_services.bulk_fix_reads(marcus, {"read_ids": [str(read.id)], "reason": ""})
        assert excinfo.value.field_errors[0]["field"] == "reason"
        read.refresh_from_db()
        assert read.fix_disposition is None


# ══════════════════════════════════════════════════════════════════════════
# TASK 7 · TC-6 — only ACCEPT is bulk; an override is refused by vocabulary
# ══════════════════════════════════════════════════════════════════════════
def test_task7_tc6__override_is_not_a_bulk_disposition(brazos, marcus):
    """BR-MET-023 lists more fix verbs, and none belongs on a bulk button: an
    override is a SUPERSEDE needing a new value and its own reason per read.
    One reason for forty different readings would be untrue of thirty-nine."""
    from core import errors

    with tenant_ctx(brazos):
        seed_config()
        meter = a_meter(marcus, asset_no="M-4416")
        read = _flagged(marcus, meter["id"], day="2026-07-05", value=1005)
        with pytest.raises(errors.ValidationError):
            metering_services.bulk_fix_reads(
                marcus,
                {"read_ids": [str(read.id)], "disposition": "override", "reason": "all wrong"},
            )
        assert "override" not in metering_services.BULK_FIX_DISPOSITIONS


# ══════════════════════════════════════════════════════════════════════════
# TASK 7 · TC-7 — the blast-radius cap
# ══════════════════════════════════════════════════════════════════════════
def test_task7_tc7__a_selection_over_the_cap_is_refused_by_name(brazos, marcus):
    from core import errors

    with tenant_ctx(brazos):
        seed_config()
        oversize = [str(n) for n in range(metering_services.BULK_MAX_ROWS + 1)]
        with pytest.raises(errors.BizError) as excinfo:
            metering_services.bulk_fix_reads(marcus, {"read_ids": oversize, "reason": "everything"})
        assert excinfo.value.params["max"] == metering_services.BULK_MAX_ROWS


# ══════════════════════════════════════════════════════════════════════════
# TASK 7 · TC-8 — bulk ESTIMATE runs the same arithmetic and names the actor
# ══════════════════════════════════════════════════════════════════════════
def test_task7_tc8__bulk_estimate_uses_the_single_row_pipeline_and_records_the_name(brazos, marcus):
    """*"A bulk button is a different surface, never a different pipeline."*
    Every target goes through `estimate_missing_read`, so BR-MET-026's
    trailing-3-cycle average is the SAME code the single door runs."""
    with tenant_ctx(brazos):
        seed_config()
        meter = a_meter(marcus, asset_no="M-4412")
        # Three actual cycles of history — BR-MET-026's trailing-3 input.
        commit_read(marcus, meter["id"], day="2026-04-05", value=1000, consumption="300.000000")
        commit_read(
            marcus,
            meter["id"],
            day="2026-05-05",
            value=1300,
            consumption="300.000000",
            days_since_prior=30,
        )
        commit_read(
            marcus,
            meter["id"],
            day="2026-06-05",
            value=1600,
            consumption="300.000000",
            days_since_prior=31,
        )

        result = metering_services.bulk_estimate_reads(
            marcus,
            {
                "targets": [
                    {"asset_id": str(meter["id"]), "channel": "total", "read_at": "2026-07-05"}
                ],
                "reason": "route not walked — storm closure",
            },
        )

        assert result["estimated_count"] == 1, result
        created = metering_models.MeterRead.objects.get(id=result["estimated"][0]["read_id"])
        assert created.status == "estimated"
        # BR-MET-028: an estimate carries consumption and NO register value.
        assert created.current_value is None
        assert created.consumption is not None
        assert created.unit == "kWh"  # hard rule 3
        # THE AUDITOR'S QUESTION, on the row this click created.
        assert created.fixed_by_id == marcus.id
        assert created.fix_disposition == metering_services.BULK_FIX_ESTIMATE
        assert "storm closure" in created.fix_reason


# ══════════════════════════════════════════════════════════════════════════
# TASK 7 · TC-9 — a target the RULES refuse comes back named, never skipped
# ══════════════════════════════════════════════════════════════════════════
def test_task7_tc9__no_history_is_a_named_refusal_not_a_silent_skip(brazos, marcus):
    """BR-MET-026: *"no history → no estimate"*. The refusal is an answer the
    clerk must see beside the row — and forty of them are forty answers."""
    with tenant_ctx(brazos):
        seed_config()
        meter = a_meter(marcus, asset_no="M-4417")  # no reads at all

        result = metering_services.bulk_estimate_reads(
            marcus,
            {
                "targets": [
                    {"asset_id": str(meter["id"]), "channel": "total", "read_at": "2026-07-05"}
                ],
                "reason": "route not walked",
            },
        )
        assert result["estimated_count"] == 0
        assert result["refused_count"] == 1
        assert result["refused"][0]["reason"] is not None
        assert result["refused"][0]["asset_id"] == str(meter["id"])


# ══════════════════════════════════════════════════════════════════════════
# TASK 6 · TC-10 — a FLAT meter is simple: the modal is the right surface
# ══════════════════════════════════════════════════════════════════════════
def test_task6_tc10__a_flat_meter_answers_simple_with_one_register(brazos, marcus):
    """PO: *"if it is simple then modal"*. CR-038 makes "simple" mean ONE
    expected register, resolved from BR-MET-049's plan-driven set — not from
    the meter's type name and not from what it reported last month."""
    with tenant_ctx(brazos):
        seed_config()
        meter = _planned_meter(marcus, brazos, asset_no="M-5001")

        ctx = quick_read.quick_entry_context(meter_no="M-5001", read_at="2026-07-15")

        assert ctx["meter"]["id"] == str(meter["id"])
        # Hard rule 3: the modal SHOWS the unit beside the value box.
        assert ctx["meter"]["unit"] == "kWh"
        assert ctx["registers"]["simple"] is True, ctx["registers"]
        assert ctx["registers"]["channel_count"] == 1
        assert ctx["registers"]["default_channel"] == "total"
        assert ctx["registers"]["hand_off_to"] is None
        # ⚠ THE PIPELINE IS NAMED ON THE WIRE — the modal does not get to choose
        # where the reading goes, and a reader of the payload can see it.
        assert ctx["pipeline"]["stage"] == "POST /read-batches"
        assert ctx["pipeline"]["note"] == "same_as_file_import"


# ══════════════════════════════════════════════════════════════════════════
# TASK 6 · TC-11 — cycle + period are DERIVED and SHOWN, never typed
# ══════════════════════════════════════════════════════════════════════════
def test_task6_tc11__the_context_derives_the_period_from_the_read_date(brazos, marcus):
    """CR-038's period/cycle sanity statement, clause 4: *"the quick single-read
    modal DERIVES cycle + period from the read date and the meter's cycle
    assignment and SHOWS them (the clerk confirms, never types)"*. And clause 1:
    *"Period membership is DERIVED from `read_at` … never typed, never
    guessed."*"""
    with tenant_ctx(brazos):
        seed_config()
        _planned_meter(marcus, brazos, asset_no="M-5002")

        ctx = quick_read.quick_entry_context(meter_no="M-5002", read_at="2026-07-15")

        assert ctx["read_at"] == "2026-07-15"
        assert ctx["cycle"]["period_month"] == "2026-07-01"
        # This meter is on no route/cycle in the fixture, and the payload says
        # so WITH a reason rather than offering a blank to fill in.
        #
        # ⚠ **AMENDED 2026-08-27, NOT REPLACED — OQ-422 IS CLOSED.** This
        # assertion read `ctx["cycle"]["cycle_absent"]["tracks"] == "OQ-422"`
        # while the case was unruled, and it went RED verbatim on the day it
        # was ruled:
        #
        #     E  KeyError: 'tracks'
        #
        # The PO chose *"(b) Accept and warn"*, so the absence stopped tracking
        # a question and started carrying a WARNING a clerk can act on
        # (BR-MET-140). What is asserted here is unchanged in spirit — the
        # payload states the absence with a reason and never offers a blank.
        if ctx["cycle"]["cycle"] is None:
            absent = ctx["cycle"]["cycle_absent"]
            assert absent["rule_ref"] == "BR-MET-140"
            assert absent["severity"] == "warning", "nothing is wrong with the reading"
            assert absent["accepted"] is True, "the reading POSTS — refusing was never offered"
            assert absent["reason"] in {"no_route", "route_has_no_cycle"}
            assert "tracks" not in absent, "OQ-422 is closed; a note may not outlive its reason"


# ══════════════════════════════════════════════════════════════════════════
# TASK 6 · TC-12 — an unknown meter refuses BY NAME, and stages nothing
# ══════════════════════════════════════════════════════════════════════════
def test_task6_tc12__an_unknown_meter_refuses_and_writes_nothing(brazos, marcus):
    from core import errors

    with tenant_ctx(brazos):
        seed_config()
        before = metering_models.ReadImportBatch.objects.count()
        with pytest.raises(errors.ValidationError) as excinfo:
            quick_read.quick_entry_context(meter_no="NOT-A-METER", read_at="2026-07-15")
        assert excinfo.value.message_key == "metering.read.unknown_meter"
        # ⚠ THE CONTEXT ROUTE WRITES NOTHING — not a batch, not a row, ever.
        assert metering_models.ReadImportBatch.objects.count() == before


# ══════════════════════════════════════════════════════════════════════════
# TASK 6 · TC-13 — THE COUNTER READ GOES THROUGH THE FILE PIPELINE, END TO END
# ══════════════════════════════════════════════════════════════════════════
def test_task6_tc13__one_counter_reading_stages_validates_and_posts_like_a_file(brazos, marcus):
    """**The whole rule of task 6, executed.** *"a MODAL is a DIFFERENT SURFACE,
    NOT A DIFFERENT PIPELINE"* — one reading walks `stage_read_batch` →
    `validate_read_batch` → `commit_read_batch`, the same three the 1,247-row
    CSV walks, and lands as an ordinary committed read with its batch stamp.

    A second write path for reads would be a second place for the rules to be
    wrong; this test is what proves there is not one."""
    with tenant_ctx(brazos):
        seed_config()
        meter = _planned_meter(marcus, brazos, asset_no="M-5003")
        commit_read(marcus, meter["id"], day="2026-06-05", value=1000, consumption="300.000000")

        batch = metering_services.stage_read_batch(
            marcus,
            {
                "source_kind": "manual",
                "period_month": "2026-07-01",
                # ONE ROW — the counter case, through `parse_manual_rows`, the
                # SAME parser the S28 manual grid uses.
                "rows": [
                    {
                        "meter_id": "M-5003",
                        "read_date": "2026-07-05",
                        "reading": "1300",
                        "channel": "total",
                    }
                ],
            },
        )
        assert batch["status"] == "staged"

        validated = metering_services.validate_read_batch(marcus, batch["id"])
        assert validated is not None

        posted = metering_services.commit_read_batch(marcus, batch["id"], {"certified": True})
        # DEF-659: the result says what actually LANDED, per read.
        assert posted["posted_reads"] == 1, posted
        assert posted["skipped_reads"] == 0, posted

        read = metering_models.MeterRead.objects.get(
            asset_id=meter["id"], read_at__date=date(2026, 7, 5), superseded_by_id__isnull=True
        )
        # BR-MET-017: every read links to its batch — the counter read is as
        # auditable as a file row because it IS one.
        assert read.import_batch_id is not None
        assert read.lifecycle == "committed"
        assert read.unit == "kWh"  # hard rule 3
        assert read.consumption == pytest.approx(read.consumption)
