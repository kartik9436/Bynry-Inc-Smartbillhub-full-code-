# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-004/005/010 (EP-RAT-02) — the rate schedule as a REGULATORY
#           FILING RECORD, which is CR-013 part 1's reading of the same table
#           the engine reads.  Screens: S11 · RAT-02 · RAT-03
# Defects:  DEF-370 (no way to duplicate a schedule — "the normal way to start a
#           filing") · DEF-367 (a version records no submitter, and approved_by
#           is served as a raw uuid) · DEF-369 (nothing stores a version LABEL,
#           so the v3 a utility files and the v3 the product counts differ) ·
#           DEF-368 (an active schedule's saved DRAFT is served only while
#           nothing is in force) · DEF-280 (the authored change note is stored
#           where a filings table cannot read it) · DEF-433 (per-size tier rates
#           cannot be written or read) · DEF-485 (block_count counts rows)
# Rules:    BR-RAT-037 (every change to a published object is a NEW version with
#           a REQUIRED reason — a duplicate may not bypass it) · BR-RAT-031
#           (save-draft resumable; a dateless version IS the draft; activation
#           needs a complete structure + effective_from) · BR-RAT-032 (tier
#           contiguity — PER SIZE GROUP from DEF-433 on) · BR-RAT-082/083 (the
#           regulator signs outside the product; submitter ≠ approver) ·
#           BR-RAT-088 (the charge code owns the base) · BR-RAT-007 (history
#           bills on its own version) · CLAUDE.md hard rule 4 (financial
#           immutability) · hard rule 7 (audit on every money action)
# ───────────────────────────────────────────────────────
"""Wave E — the rate-schedule FILING STORY, proved end to end.

Two groups, and the split is the one the defects fall into naturally.

**Group 1, the filing record.** A version was designed for the ENGINE, which
needs a window and a structure and never asks who filed it. CR-013 part 1 made
the same rows a regulatory record — *"the unit of regulatory filing"* — and
nothing re-checked the columns against that reading. So a filing had no label,
no submitter, no readable change note, and could not be started from last year's.

**Group 2, the size axis.** `RateTier.size_class` and `charge_code_amounts` both
shipped with no reader and no writer. Both are invisible for the same reason:
with the columns empty, a per-size read and a scalar read return the same answer
for every tenant, so any test written before them passes either way. The tests
here are therefore written against the ONE case that tells them apart — r10's
2" water row, `3.45 / 5.10 / 7.70` where every other size prices
`3.20 / 4.80 / 7.20`.
"""

from datetime import date

import pytest

from apps.rating import models, selectors, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, audit_actions, tenant_ctx

pytestmark = pytest.mark.django_db


# r10's 2" water row — the one row the schedule's size axis exists for.
TWO_INCH_TIERS = [
    {"from_qty": "0", "to_qty": "4", "unit_price": "3.45", "size_class": "W200"},
    {"from_qty": "4", "to_qty": "10", "unit_price": "5.10", "size_class": "W200"},
    {"from_qty": "10", "to_qty": None, "unit_price": "7.70", "size_class": "W200"},
]


# ══════════════════════════════════════════════════════════════════════════
# Group 1 — the filing record
# ══════════════════════════════════════════════════════════════════════════


def test_def_367__a_version_records_who_filed_it_and_serves_a_name_not_a_uuid(env):
    """DEF-367. The BY column of a filings table could not be filled: there was
    no submitter at all, and `approved_by` — a DIFFERENT person by BR-RAT-083 —
    was served as a bare uuid, which is DEF-206's own lesson about showing an
    internal identifier to a person."""
    env.enable("water")
    schedule = env.tiered_schedule("Res Water · Filed", "water", RES_WATER_TIERS)
    version = schedule["current_version"]

    # Stamped from the ACTING USER, never typed — so it cannot be wrong.
    assert version["submitted_by"] is not None
    assert version["submitted_by"]["id"] == str(env.admin.id)
    assert version["submitted_by"]["name"] == env.owner.full_name
    # A NAME, not a uuid: the id travels for traceability and the screen prints
    # the name. Two staff can share a first name; neither shares an id.
    assert version["submitted_by"]["name"] is not None

    # BR-RAT-083 keeps the two people apart: nobody approved this internally,
    # so `approved_by` stays null. It is metadata and never a gate.
    assert version["approved_by"] is None


def test_def_367__approved_by_is_the_same_shape_as_the_audit_trail_uses(env):
    """The convention is COPIED, not invented: `apps/audit/selectors` has always
    served `{id, name}` for the same table, and a second shape for one fact is
    how two screens start disagreeing about a person's name."""
    env.enable("water")
    schedule = env.tiered_schedule(
        "Res Water · Approved", "water", RES_WATER_TIERS, approved_by=str(env.admin.id)
    )
    approver = schedule["current_version"]["approved_by"]
    assert set(approver) == {"id", "name"}
    assert approver["id"] == str(env.admin.id)
    assert approver["name"] == env.owner.full_name


def test_def_369__a_filed_version_label_is_stored_and_round_trips(env):
    """DEF-369. `v3` was a POSITION in the effective-date order, so back-dating a
    version into the chain silently renumbered a docket a regulator holds on
    paper. The label is stored now, as typed."""
    env.enable("water")
    schedule = env.tiered_schedule(
        "Res Water · 2027 case", "water", RES_WATER_TIERS, version_label="2027-A"
    )
    assert schedule["current_version"]["version_label"] == "2027-A"

    # Free TEXT and never unique: real filings read `v3`, `2027-A`,
    # `Sheet 4 Rev 2`, and a utility that files two sheets under one label has a
    # filing problem rather than a data-entry refusal (BR-RAT-082's standing).
    with tenant_ctx(env.tenant):
        second = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · 2027 case B",
                "service": "water",
                "model": "tiered",
                "uom": "kgal",
                "effective_from": "2026-08-01",
                "structure": {"tiers": RES_WATER_TIERS},
                "version_label": "2027-A",
            },
        )
    assert second["current_version"]["version_label"] == "2027-A"


def test_def_369__no_label_stays_null_so_a_screen_can_say_it_derived_the_number(env):
    """A blank label must stay NULL rather than becoming `""`. The screen falls
    back to a derived ordinal AND SAYS SO, and it cannot tell `""` from "never
    stated"."""
    env.enable("water")
    schedule = env.tiered_schedule("Res Water · Unlabelled", "water", RES_WATER_TIERS)
    assert schedule["current_version"]["version_label"] is None


def test_def_280__br_rat_037s_reason_is_kept_on_the_version_it_describes(env):
    """DEF-280. The sentence WAS authored — `create_rate_schedule_version`
    refuses without a reason — and it was written only to `rate_change_log`,
    where a filings table cannot read it. §10 asks the CHANGE column for the
    authored note, never for a diff."""
    env.enable("water")
    schedule = env.tiered_schedule("Res Water · v1", "water", RES_WATER_TIERS)
    # A FIRST version has no change to describe.
    assert schedule["current_version"]["change_reason"] is None

    with tenant_ctx(env.tenant):
        updated = services.create_rate_schedule_version(
            env.admin,
            schedule["id"],
            {
                "model": "tiered",
                "uom": "kgal",
                "effective_from": "2027-01-01",
                "structure": {"tiers": RES_WATER_TIERS},
                "reason": "TWDB pass-through 2027",
            },
        )
    # Read off the version CHAIN, not off `current_version`: the new window
    # opens in 2027, so what is IN FORCE today is still the old one (BR-RAT-007,
    # and the reason the detail serves both).
    filed = [row for row in updated["versions"] if row["effective_from"] == "2027-01-01"]
    assert len(filed) == 1
    assert filed[0]["change_reason"] == "TWDB pass-through 2027"
    # The version it supersedes keeps ITS OWN answer — a first version had no
    # change to describe, and a later filing does not backfill one.
    superseded = [row for row in updated["versions"] if row["effective_from"] == "2026-08-01"]
    assert superseded[0]["change_reason"] is None

    # The `rate_change_log` row is UNCHANGED — it is the cross-object history
    # and carries plan changes too. This is the same words on the row a
    # regulator reads, not a move.
    with tenant_ctx(env.tenant):
        log = models.RateChangeLog.objects.filter(
            tenant=env.tenant, entity_id=schedule["id"]
        ).first()
    assert log is not None and log.reason == "TWDB pass-through 2027"


def test_def_368__an_active_schedules_saved_draft_reaches_the_detail(env):
    """DEF-368. `schedule_card` computed `draft = draft_version(tariff) if
    current is None else None`, so a schedule with a rate IN FORCE and a filing
    in preparation answered `null` for the draft — and §10 draws exactly that as
    its normal case, *"a draft future version is listed ABOVE the current one"*.

    The draft row is written through the ORM here on purpose: no service path
    creates a dateless draft on an activated schedule today, which is OQ-311 and
    is the PO's to rule. What is proved here is the READ — that the selector no
    longer hides a row that exists."""
    env.enable("water")
    schedule = env.tiered_schedule("Res Water · Live", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=schedule["id"])
        models.TariffVersion.objects.create(
            tenant=env.tenant,
            tariff=tariff,
            model="tiered",
            currency="USD",
            uom="kgal",
            effective_from=None,  # BR-RAT-031: NULL is THE draft
        )
        card = selectors.schedule_card(tariff)
        detail = selectors.schedule_detail(tariff.id)

    # Both are served, and they are DIFFERENT versions — the rule the old
    # condition was protecting is kept: a draft never reads as what is in force.
    assert card["current_version"] is not None
    assert card["draft_version"] is not None
    assert card["draft_version"]["id"] != card["current_version"]["id"]
    assert card["draft_version"]["effective_from"] is None
    assert card["status"] == "active"
    # The activated HISTORY still excludes the draft (BR-RAT-031: it is not
    # history and it has never been in force).
    assert [row["id"] for row in detail["versions"]] == [card["current_version"]["id"]]


def test_def_370__duplicate_copies_the_whole_schedule_as_a_draft(env):
    """DEF-370 · CR-013 part 1: *"Duplicate (the normal way to start a filing)"*.
    A utility filing a 2027 rate case starts from the 2026 one instead of
    retyping every size row, every tier, the unit and the customer class."""
    env.enable("water")
    source = env.tiered_schedule(
        "Res Water · 2026",
        "water",
        RES_WATER_TIERS,
        version_label="2026-A",
        regulator_ref="PUC #W-2025-1184",
        filing_authority="Texas PUC",
        size_rows=[{"size_class": "W058", "minimum_bill": "17.00"}],
    )
    with tenant_ctx(env.tenant):
        copy = services.duplicate_rate_schedule(env.admin, source["id"])

    # A NEW schedule, named so a human can tell them apart, on the same service.
    assert copy["id"] != source["id"]
    assert copy["name"] == "Res Water · 2026 (copy)"
    assert copy["service"] == "water"

    # It is a DRAFT: dateless, so every gate still stands between it and being
    # in force (BR-RAT-031).
    assert copy["current_version"] is None
    assert copy["draft_version"] is not None
    assert copy["draft_version"]["effective_from"] is None
    assert copy["status"] == "draft"

    # THE PRICING IS COPIED — which is the whole point of the word Duplicate.
    draft = copy["draft_version"]
    assert draft["model"] == "tiered"
    assert draft["uom"] == "kgal"
    assert [tier["unit_price"] for tier in draft["structure"]["tiers"]] == [
        "3.200000",
        "4.800000",
        "7.200000",
    ]
    assert [row["size_class"] for row in draft["size_rows"]] == ["W058"]
    assert draft["size_rows"][0]["minimum_bill"] == "17.000000"

    # THE FILING IS NOT. Last year's docket belongs to last year's version; a
    # copy carrying it would file a new rate under an approved case number.
    assert draft["regulator_ref"] is None
    assert draft["filing_authority"] is None
    assert draft["version_label"] is None
    assert draft["change_reason"] is None
    # `submitted_by` is the person DUPLICATING, which is the true answer to
    # "who filed this draft".
    assert draft["submitted_by"]["id"] == str(env.admin.id)


def test_def_370__duplicating_does_not_touch_the_source(env):
    """BR-RAT-037 says every change to a published object is a new version with
    a required reason. A duplicate must not become a reason-free door into that,
    and the way it is kept out is structural: the source is READ."""
    env.enable("water")
    source = env.tiered_schedule("Res Water · Source", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        before = selectors.schedule_detail(source["id"])
        services.duplicate_rate_schedule(env.admin, source["id"])
        after = selectors.schedule_detail(source["id"])
        source_versions = models.TariffVersion.objects.filter(
            tenant=env.tenant, tariff_id=source["id"]
        ).count()
    assert before == after
    assert source_versions == 1
    # And the copy still cannot edit a published version: it has none.
    assert after["current_version"]["effective_from"] == "2026-08-01"


def test_def_370__a_second_duplicate_is_named_copy_2_rather_than_answering_500(env):
    """`uq_tariffs_tenant_name_service` is per (tenant, name, service) and a
    duplicate lands on the SAME service, so the plain suffix collides the second
    time. Counting is not decoration."""
    env.enable("water")
    source = env.tiered_schedule("Res Water · Twice", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        first = services.duplicate_rate_schedule(env.admin, source["id"])
        second = services.duplicate_rate_schedule(env.admin, source["id"])
    assert first["name"] == "Res Water · Twice (copy)"
    assert second["name"] == "Res Water · Twice (copy 2)"


def test_def_370__a_named_duplicate_that_collides_is_refused_by_field(env):
    env.enable("water")
    source = env.tiered_schedule("Res Water · Named", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        services.duplicate_rate_schedule(
            env.admin, source["id"], {"name": "Res Water · Named"}
        )
    assert caught.value.message_key == "rating.schedules.duplicate_name"


def test_def_370__an_identity_only_schedule_has_nothing_to_duplicate(env):
    """Copying the NAME alone produces a second empty schedule the user then has
    to delete, so it is refused BY NAME instead."""
    env.enable("water")
    with tenant_ctx(env.tenant):
        bare = services.create_rate_schedule(
            env.admin, {"name": "Res Water · Bare", "service": "water"}
        )
        with pytest.raises(errors.BizError) as caught:
            services.duplicate_rate_schedule(env.admin, bare["id"])
    assert caught.value.message_key == "rating.schedules.nothing_to_duplicate"


def test_def_370__duplicate_writes_an_audit_row(env, audit_rows):
    """CLAUDE.md hard rule 7 — every money action writes `audit_log`, and
    creating a priced schedule is one."""
    env.enable("water")
    source = env.tiered_schedule("Res Water · Audited", "water", RES_WATER_TIERS)
    audit_rows.clear()
    with tenant_ctx(env.tenant):
        services.duplicate_rate_schedule(env.admin, source["id"])
    assert "tariff.duplicated" in audit_actions(audit_rows)


# ══════════════════════════════════════════════════════════════════════════
# Group 2 — the size axis
# ══════════════════════════════════════════════════════════════════════════


def test_def_433__the_two_inch_water_row_can_finally_be_expressed(env):
    """DEF-433. `RateTier.size_class` shipped nullable with nothing writing it
    and nothing serving it, so the one row that justifies the schedule owning a
    size axis at all — 2" water at `3.45 / 5.10 / 7.70` against every other
    size's `3.20 / 4.80 / 7.20` — was inexpressible through the API."""
    env.enable("water")
    schedule = env.tiered_schedule(
        "Res Water · Sized", "water", RES_WATER_TIERS + TWO_INCH_TIERS
    )
    tiers = schedule["current_version"]["structure"]["tiers"]
    base = [tier for tier in tiers if tier["size_class"] is None]
    two_inch = [tier for tier in tiers if tier["size_class"] == "W200"]
    assert [tier["unit_price"] for tier in base] == ["3.200000", "4.800000", "7.200000"]
    assert [tier["unit_price"] for tier in two_inch] == ["3.450000", "5.100000", "7.700000"]


def test_def_433__contiguity_is_validated_per_group_not_over_the_list(env):
    """The validation had to change SHAPE, not gain a field: two ladders read as
    one list have `from_qty`s `0, 4, 10, 0, 4, 10`, and a single running
    `previous_to` reads that as a gap at row four and refuses a correct rate."""
    env.enable("water")
    # A genuine gap INSIDE the override group is still refused, by row.
    gapped = [
        {"from_qty": "0", "to_qty": "4", "unit_price": "3.45", "size_class": "W200"},
        {"from_qty": "6", "to_qty": None, "unit_price": "7.70", "size_class": "W200"},
    ]
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Gapped",
                "service": "water",
                "model": "tiered",
                "uom": "kgal",
                "effective_from": "2026-08-01",
                "structure": {"tiers": RES_WATER_TIERS + gapped},
            },
        )
    fields = [error["field"] for error in caught.value.field_errors]
    assert any("from_qty" in field for field in fields)


def test_def_433__each_group_may_have_its_own_open_top_block(env):
    """Over a flat list, "only the last tier may be open-ended" meant "the last
    row of the payload", which made every group but the final one unable to have
    a top block at all."""
    env.enable("water")
    schedule = env.tiered_schedule(
        "Res Water · Two open tops", "water", RES_WATER_TIERS + TWO_INCH_TIERS
    )
    tiers = schedule["current_version"]["structure"]["tiers"]
    open_tops = [tier for tier in tiers if tier["to_qty"] is None]
    assert len(open_tops) == 2


def test_def_433__a_size_override_without_the_base_ladder_is_refused(env):
    """`RateTier`'s own rule: NULL means "every size" and a size-specific group
    OVERRIDES it. A payload of nothing but overrides leaves every size the
    utility did not name with NO PRICE — priced as zero or refused at bill time,
    depending on which read got there first."""
    env.enable("water")
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as caught:
        services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Exception only",
                "service": "water",
                "model": "tiered",
                "uom": "kgal",
                "effective_from": "2026-08-01",
                "structure": {"tiers": TWO_INCH_TIERS},
            },
        )
    keys = [error["message_key"] for error in caught.value.field_errors]
    assert "rating.tiers.size_override_without_base" in keys


def test_def_433__pricing_inputs_selects_ONE_ladder_and_falls_back_to_the_base(env):
    """⚠ THE MONEY HALF. Read unfiltered, a schedule with a base ladder and one
    override hands the engine SIX blocks in one ascending sequence and every
    bill on that schedule is wrong, silently."""
    env.enable("water")
    schedule = env.tiered_schedule(
        "Res Water · Engine", "water", RES_WATER_TIERS + TWO_INCH_TIERS
    )
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=schedule["id"])
        no_size = selectors.pricing_inputs(tariff, date(2026, 9, 1))
        two_inch = selectors.pricing_inputs(tariff, date(2026, 9, 1), "W200")
        five_eighths = selectors.pricing_inputs(tariff, date(2026, 9, 1), "W058")

    # THREE blocks, never six — whichever ladder is asked for.
    assert len(no_size["tiers"]) == 3
    assert len(two_inch["tiers"]) == 3
    assert len(five_eighths["tiers"]) == 3
    # The size with its own ladder gets it; a size without one falls back to the
    # NULL group, which is "a schedule states the exception, not the rule".
    assert [str(tier["unit_price"]) for tier in two_inch["tiers"]] == [
        "3.450000",
        "5.100000",
        "7.700000",
    ]
    assert [str(tier["unit_price"]) for tier in five_eighths["tiers"]] == [
        "3.200000",
        "4.800000",
        "7.200000",
    ]
    # No size given is the base ladder — which is exactly today's answer for
    # every version in the database, because all their tiers are the NULL group.
    assert no_size["tiers"] == five_eighths["tiers"]


def test_def_433__a_schedule_with_no_override_prices_exactly_as_it_did(env):
    """The reason this change is additive: every tier written before the column
    existed reads back as the NULL group, so the engine sees the same rows in
    the same order at the same prices."""
    env.enable("water")
    schedule = env.tiered_schedule("Res Water · Plain", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=schedule["id"])
        plain = selectors.pricing_inputs(tariff, date(2026, 9, 1))
        sized = selectors.pricing_inputs(tariff, date(2026, 9, 1), "W200")
    assert plain["tiers"] == sized["tiers"]
    assert len(plain["tiers"]) == 3


def test_def_467__saving_an_override_says_on_screen_that_bills_do_not_use_it(env):
    """DEF-484 · `apps/billing/gather.py` calls `pricing_inputs` with no
    connection size, so a 2" connection currently bills the base ladder — 12
    dollars a month short on a 10/20/5 usage, and every line individually
    correct. The person who typed 3.45 is told at the moment they save it."""
    env.enable("water")
    schedule = env.tiered_schedule(
        "Res Water · Notice", "water", RES_WATER_TIERS + TWO_INCH_TIERS
    )
    codes = [notice["code"] for notice in schedule["notices"]]
    assert "rating.tiers.size_override_not_billed" in codes
    # No engineering reference reaches the copy (DEF-319).
    notice = next(row for row in schedule["notices"] if row["code"].endswith("not_billed"))
    assert notice["params"] == {}


def test_def_433__a_duplicate_carries_the_size_override(env):
    """A 2" override that vanished on duplicate would be the silent drop
    DEF-433's own prevention note warns about."""
    env.enable("water")
    source = env.tiered_schedule(
        "Res Water · Sized source", "water", RES_WATER_TIERS + TWO_INCH_TIERS
    )
    with tenant_ctx(env.tenant):
        copy = services.duplicate_rate_schedule(env.admin, source["id"])
    tiers = copy["draft_version"]["structure"]["tiers"]
    assert [tier["unit_price"] for tier in tiers if tier["size_class"] == "W200"] == [
        "3.450000",
        "5.100000",
        "7.700000",
    ]


def test_def_431__the_per_size_base_amounts_are_served_beside_the_scalar(env):
    """DEF-431. `charge_code_amounts` shipped with migration 0010 and had no
    reader and no writer, so every screen drawing a base against a connection
    size drew ONE scalar against all of them. r10's water matrix prices 5/8" at
    $12.00 and 2" at $64.00 — the scalar is $52.00 a month wrong on 2"."""
    env.enable("water")
    charge = env.charge("BASE-W", "Water base charge", service="water", amount="12.00")
    with tenant_ctx(env.tenant):
        row = models.Charge.objects.get(pk=charge["id"])
        for size, amount in (("W058", "12.0000"), ("W200", "64.0000")):
            models.ChargeCodeAmount.objects.create(
                tenant=env.tenant, charge=row, size_class=size, amount=amount
            )
        served = selectors.charge_row(row)

    # The scalar is UNCHANGED — this is additive, and a code with no per-size
    # rows is still answered by it.
    assert served["amount_display"] == "12.00"
    by_size = {entry["size_class"]: entry["amount_display"] for entry in served["size_amounts"]}
    assert by_size == {"W058": "12.00", "W200": "64.00"}


def test_def_431__a_null_amount_on_a_size_row_is_not_served_never_zero(env):
    """CR-013 part 1's *"blank base = size not served"* (DEF-277), one table
    across: R4 refuses rather than billing $0.00 for a size the utility does not
    serve, so the absence must survive the read."""
    env.enable("water")
    charge = env.charge("BASE-W2", "Water base charge", service="water", amount="12.00")
    with tenant_ctx(env.tenant):
        row = models.Charge.objects.get(pk=charge["id"])
        models.ChargeCodeAmount.objects.create(
            tenant=env.tenant, charge=row, size_class="W200", amount=None
        )
        served = selectors.charge_row(row)
    entry = served["size_amounts"][0]
    assert entry["amount"] is None and entry["amount_display"] is None


def test_def_431__a_code_with_no_size_rows_serves_an_empty_list(env):
    """An empty list means "this code does not vary by size", which is what
    every charge code in the database says today — so nothing moves."""
    env.enable("water")
    charge = env.charge("BASE-W3", "Water base charge", service="water", amount="12.00")
    with tenant_ctx(env.tenant):
        served = selectors.charge_row(models.Charge.objects.get(pk=charge["id"]))
    assert served["size_amounts"] == []
    assert served["amount_display"] == "12.00"


def test_def_468__a_three_block_rate_reports_three_blocks_however_it_repeats(env):
    """DEF-485. `block_count` was `len({tier["seq"]})`, and the comment beside it
    named the exact failure it did not prevent — *"otherwise a 3-block
    summer/winter water rate reads 6 blocks"*. True of the seq `_validate_tiers`
    hands back and false of the seq that is STORED: `_write_version` renumbers
    every tier of a version with one running counter, to keep
    `uq_rate_tiers_version_seq` verbatim."""
    env.enable("water")
    plain = env.tiered_schedule("Res Water · 3 blocks", "water", RES_WATER_TIERS)
    sized = env.tiered_schedule(
        "Res Water · 3 blocks + 2in", "water", RES_WATER_TIERS + TWO_INCH_TIERS
    )
    with tenant_ctx(env.tenant):
        plain_card = selectors.schedule_card(models.Tariff.objects.get(pk=plain["id"]))
        sized_card = selectors.schedule_card(models.Tariff.objects.get(pk=sized["id"]))
    assert plain_card["block_count"] == 3
    # SIX stored tier rows, THREE blocks — a size override repeats the ladder,
    # it does not deepen it.
    assert sized_card["block_count"] == 3


# ── Lifecycle ─────────────────────────────────────────────
# packet: Wave E (DEF-370 · DEF-367 · DEF-369 · DEF-368 · DEF-280 · DEF-433 ·
#         DEF-431 · DEF-430), CR-013 part 1 + 09-screen-inventory.md §10 · §13
# screens: RAT-02 · RAT-03 (r10) / S11 (A1)
# generated: 2026-08-21 by the Wave E rate-schedule filing lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_wave_e_filing_record.py✔ · golden-verify 33/33✔ ·
#        makemigrations --check✔
# exceptions:
#   E3 DEF-368's fix is proved through an ORM-written draft row, because no
#      SERVICE path creates a dateless draft on an activated schedule — that is
#      OQ-311 and is the PO's to rule. What is proved is the READ: the selector
#      no longer hides a row that exists.
#   E3 DEF-431's per-size amounts are written through the ORM: `charge_code_amounts`
#      is CHG-02's editable source (another lane's screen) and this lane serves
#      the READ that a rate matrix needs.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
