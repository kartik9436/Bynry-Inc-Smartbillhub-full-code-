# ── Trace ──────────────────────────────────────────────
# Story:    CR-038 W1b (the correction cascade — the Blueprint's Open 10)
#           Screens: S25 · S29
# Rules:    BR-MET-126 (PO 2026-08-26, CONFIRMED) — quoted VERBATIM in the
#           module docstring below, because this file is its acceptance
#           contract · BR-MET-024/053 (a correction is a NEW row; the billed
#           door) · BR-MET-026/028/029 (estimation math — a stale estimate is
#           recomputed through the estimation service, never by subtraction) ·
#           CLAUDE.md rule 4 (corrections are new rows — "we cant cahnge the
#           source data") · rule 1 (tenant scoping) · rule 7 (audit)
# Journeys: J6 (the billed recommendation hands off to the correction door)
# ───────────────────────────────────────────────────────
"""BR-MET-126 — the correction cascade, proven RED first on the worked case.

THE RULE, VERBATIM (04-docs/05-modules/04-metering/02-business-rules.md):
    "THE READING AFTER A CORRECTED ONE: RECOMPUTE UNBILLED AUTOMATICALLY,
    RECOMMEND THROUGH THE MONEY DOOR WHEN BILLED — AND NEVER TOUCH SOURCE DATA
    (PO 2026-08-26, CR-038 · closes the Blueprint's Open 10). PO verbatim:
    '(b) auto-recompute when the next reading is still unbilled; flag it
    through the billed-correction door when it's billed - but we cant cahnge
    the source data, so we will ahve to accept the trust and make the
    recomendation'. (1) After a supersede, the next reading on the same meter
    and register is found in the same transaction. (2) UNBILLED next reading:
    the system recomputes it automatically — as a SUPERSEDING CORRECTION ROW
    (hard rule 4: the original row is never edited; 'we cant cahnge the source
    data'), marked system-generated and naming the correction that triggered
    it. (3) BILLED next reading: the system does not act alone — it FLAGS the
    row through the billed-correction door as a RECOMMENDATION with the worked
    delta, and a human confirms (the read fix and the money fix travel
    together). The Dec/Jan/Feb 200-double-billed-units case is the acceptance
    test, proven red first."

THE WORKED CASE (the Blueprint's, to the digit): Dec 31 reads 4,200; Jan 31
reads 5,000 and is superseded to 5,200; Feb 28 reads 5,800. Before this lane,
February's stored prior stayed 5,000 and its consumption 800 — so the lineage
heads carried 1,000 + 800 = 1,800 kWh against 1,600 actually used: 200 units
billed twice.

RED RUN (law 7 — the defect reproduced before a line of the fix was written;
2026-08-26, worked-case test only, verbatim):

    E   AssertionError: BR-MET-126 worked case: February still stands on
        prior 5,000 / consumption 800 — 1,800 billed against 1,600 used;
        200 units charged twice
    E   assert None is not None
    E    +  where None = <MeterRead: MeterRead object ((UUID('01a03eb9-6966-
        72fe-827d-0f164408dfa3'), datetime.datetime(2026, 2, 28, 0, 0,
        tzinfo=datetime.timezone.utc), UUID('01a03eb9-6f22-7239-a6b2-
        166ec4777ecc')))>.superseded_by_id
    tests/test_cr038_w1b_cascade.py:140: AssertionError
    1 failed in 80.75s (0:01:20)

Every other test in this file was committed in the same red state (the
machinery they pin — `read.cascade_recomputed`, `cascade_stale_billed`,
`stale_prior`, the `cascade` summary — did not exist yet).
"""

from decimal import Decimal

import pytest

from apps.metering import models, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared world
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    commit_read,
    seed_config,
    tenant_ctx,
)


def _chain(actor, asset_id, rows, unit="kWh"):
    """Commit a history of (day, value, prior, consumption, days) actuals."""
    made = []
    for day, value, prior, consumption, days in rows:
        made.append(
            commit_read(
                actor,
                asset_id,
                day=day,
                value=value,
                prior_value=prior,
                consumption=consumption,
                days_since_prior=days,
                unit=unit,
            )
        )
    return made


def _dec_jan_feb(actor, asset_no="M-9101", service="electric", uom="kWh"):
    """The Blueprint's worked fixture: 4,200 → 5,000 → 5,800."""
    seed_config()
    asset = a_meter(actor, asset_no=asset_no, service=service, uom=uom)
    dec, jan, feb = _chain(
        actor,
        asset["id"],
        [
            ("2025-12-31", "4200", None, "0", None),
            ("2026-01-31", "5000", "4200", "800.000000", 31),
            ("2026-02-28", "5800", "5000", "800.000000", 28),
        ],
        unit=uom,
    )
    return asset, dec, jan, feb


def _head_for(read):
    """The current lineage head standing where `read` stood."""
    return models.MeterRead.objects.get(
        asset_id=read.asset_id,
        read_at=read.read_at,
        channel=read.channel,
        superseded_by_id__isnull=True,
    )


def _outcome(read, rule):
    for entry in read.rule_outcomes or []:
        if entry.get("rule") == rule:
            return entry
    return None


def _audit_actions(rows, action):
    return len([row for row in rows if row["action"] == action])


# ── The acceptance test: the 200 double-billed units ────────────────────────
@pytest.mark.django_db
def test_br_met_126_worked_case__the_200_double_billed_units_are_recomputed(
    brazos, marcus, audit_rows
):
    with tenant_ctx(brazos):
        asset, dec, jan, feb = _dec_jan_feb(marcus)
        corrected = services.supersede_read(
            marcus, jan.id, {"value": "5200", "reason": "customer photo — register misread"}
        )
        assert Decimal(corrected["current_value"]) == Decimal("5200")
        assert Decimal(corrected["consumption"]) == Decimal("1000")  # 5,200 − 4,200

        feb.refresh_from_db()
        assert feb.superseded_by_id is not None, (
            "BR-MET-126 worked case: February still stands on prior 5,000 / "
            "consumption 800 — 1,800 billed against 1,600 used; 200 units "
            "charged twice"
        )
        new_feb = _head_for(feb)
        assert str(new_feb.id) == str(feb.superseded_by_id)
        # The recompute: prior = the corrected register, consumption re-derived.
        assert new_feb.prior_value == Decimal("5200")
        assert new_feb.current_value == Decimal("5800")  # source register untouched
        assert new_feb.consumption == Decimal("600.000000")
        assert new_feb.unit == "kWh"  # rule 3 — never without its unit
        # 1,000 + 600 = 1,600 across the heads — exactly what the meter used.
        heads_total = sum(
            row.consumption
            for row in selectors._read_heads().filter(asset_id=asset["id"])
            if row.consumption is not None
        )
        assert heads_total == Decimal("1600")
        # Hard rule 4 — the source rows are visible and untouched.
        feb.refresh_from_db()
        assert feb.current_value == Decimal("5800")
        assert feb.prior_value == Decimal("5000")
        assert feb.consumption == Decimal("800.000000")
        # Marked system-generated, naming the correction that triggered it.
        marker = _outcome(new_feb, "cascade_recomputed")
        assert marker is not None, "the replacement row carries no system-generated marker"
        assert marker["detail"]["system_generated"] is True
        assert marker["detail"]["br_ref"] == "BR-MET-126"
        assert marker["detail"]["triggered_by_read_id"] == corrected["id"]
        assert marker["detail"]["superseded_read_id"] == str(feb.id)
        # The caller sees what the cascade did (server-side visibility).
        assert corrected["cascade"]["recomputed"] == [str(new_feb.id)]
        assert corrected["cascade"]["flagged"] == []
        # Money-adjacent state moved → audit (hard rule 7).
        assert _audit_actions(audit_rows, "read.cascade_recomputed") == 1


# ── (3) BILLED next reading: a recommendation, never a silent rewrite ───────
@pytest.mark.django_db
def test_br_met_126__billed_next_read_is_flagged_with_the_worked_delta_not_rewritten(
    brazos, marcus, audit_rows
):
    with tenant_ctx(brazos):
        asset, dec, jan, feb = _dec_jan_feb(marcus, asset_no="M-9102")
        assert services.mark_read_billed(feb.id) is True
        result = services.supersede_read(
            marcus, jan.id, {"value": "5200", "reason": "customer photo — register misread"}
        )
        feb.refresh_from_db()
        # No automatic change: no new row, values untouched, lineage open.
        assert feb.superseded_by_id is None
        assert feb.prior_value == Decimal("5000")
        assert feb.consumption == Decimal("800.000000")
        # The RECOMMENDATION: stale prior, worked delta, and the door through.
        flag = _outcome(feb, "cascade_stale_billed")
        assert flag is not None, "the billed read carries no recommendation flag"
        assert flag["severity"] == "warning"
        detail = flag["detail"]
        assert detail["br_ref"] == "BR-MET-126"
        assert detail["stale_prior_value"] == "5000.000000"
        assert detail["expected_prior_value"] == "5200.000000"
        assert detail["stored_consumption"] == "800.000000"
        assert detail["recomputed_consumption"] == "600.000000"
        assert detail["delta"] == "200.000000"  # the double-billed units
        assert detail["unit"] == "kWh"
        assert detail["door"] == "correct_billed_read"
        assert detail["triggered_by_read_id"] == result["id"]
        # Surfaced where flags already surface: the needs-attention chip.
        assert feb.status == "stale_prior"
        counts = selectors.needs_attention_counts()
        assert counts["flagged"] >= 1
        assert (
            selectors._read_heads()
            .exclude(status__in=("ok", "estimated"))
            .filter(id=feb.id)
            .exists()
        )
        # The cascade reports the boundary and stops there.
        assert result["cascade"]["flagged"] == [str(feb.id)]
        assert result["cascade"]["recomputed"] == []
        assert result["cascade"]["stopped"] == "billed_boundary"
        assert _audit_actions(audit_rows, "read.cascade_recommendation") == 1


# ── (2 continued) the cascade walks on and converges honestly ───────────────
@pytest.mark.django_db
def test_br_met_126__third_reading_is_evaluated_and_left_alone_when_its_prior_still_stands(
    brazos, marcus
):
    """Mar 31 measures from February's own register (5,800), which the
    correction never touched — evaluated the same way, found current, kept."""
    with tenant_ctx(brazos):
        asset, dec, jan, feb = _dec_jan_feb(marcus, asset_no="M-9103")
        mar = commit_read(
            marcus,
            asset["id"],
            day="2026-03-31",
            value="6300",
            prior_value="5800",
            consumption="500.000000",
            days_since_prior=31,
        )
        result = services.supersede_read(
            marcus, jan.id, {"value": "5200", "reason": "register misread"}
        )
        mar.refresh_from_db()
        assert mar.superseded_by_id is None  # its prior register never changed
        assert mar.consumption == Decimal("500.000000")
        new_feb = _head_for(feb)
        assert new_feb.consumption == Decimal("600.000000")
        assert result["cascade"]["recomputed"] == [str(new_feb.id)]
        assert result["cascade"]["stopped"] == "end_of_chain"


# ── (4) estimates: recomputed through the estimation service's own math ─────
@pytest.mark.django_db
def test_br_met_126__a_following_estimate_is_recomputed_through_the_estimation_service(
    brazos, marcus
):
    """Trailing-3 daily average (BR-MET-026), never raw register subtraction.

    History 600 + 600 over 30 + 30 days → 20/day → the standing estimate was
    600 over 30 days. The middle actual is corrected 2,200 → 2,500, so its
    consumption becomes 900 and the average (900 + 600) ÷ 60 = 25/day → the
    estimate must become 750.000000, recomputed by estimation.estimate."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus, asset_no="M-9104")
        _chain(
            marcus,
            asset["id"],
            [
                ("2025-10-01", "1000", None, "0", None),
                ("2025-10-31", "1600", "1000", "600.000000", 30),
                ("2025-11-30", "2200", "1600", "600.000000", 30),
            ],
        )
        nov = models.MeterRead.objects.get(read_at=at("2025-11-30"))
        est = commit_read(
            marcus,
            asset["id"],
            day="2025-12-30",
            value=None,
            consumption="600.000000",
            days_since_prior=30,
            estimated=True,
        )
        est.estimation_method = "trailing_3_avg"
        est.consecutive_estimate_no = 1
        est.save()
        result = services.supersede_read(
            marcus, nov.id, {"value": "2500", "reason": "field verification"}
        )
        est.refresh_from_db()
        assert est.superseded_by_id is not None
        new_est = _head_for(est)
        assert new_est.current_value is None  # BR-MET-028 — an estimate has no register
        assert new_est.status == "estimated"
        assert new_est.consumption == Decimal("750.000000")
        assert new_est.estimation_method == "trailing_3_avg"
        marker = _outcome(new_est, "cascade_recomputed")
        assert marker is not None
        assert marker["detail"]["triggered_by_read_id"] == result["id"]
        assert str(new_est.id) in result["cascade"]["recomputed"]


# ── (4 continued) the true-up actual after the estimate is recomputed too ───
@pytest.mark.django_db
def test_br_met_126__cascade_continues_through_the_estimate_to_the_true_up_actual(brazos, marcus):
    """The third reading in the chain — BR-MET-029's register arithmetic:
    stored (3,400 − 2,200) − 600 = 600; after the correction and the estimate's
    own recompute, (3,400 − 2,500) − 750 = 150.000000."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus, asset_no="M-9105")
        _chain(
            marcus,
            asset["id"],
            [
                ("2025-10-01", "1000", None, "0", None),
                ("2025-10-31", "1600", "1000", "600.000000", 30),
                ("2025-11-30", "2200", "1600", "600.000000", 30),
            ],
        )
        nov = models.MeterRead.objects.get(read_at=at("2025-11-30"))
        est = commit_read(
            marcus,
            asset["id"],
            day="2025-12-30",
            value=None,
            consumption="600.000000",
            days_since_prior=30,
            estimated=True,
        )
        true_up = models.MeterRead.objects.create(
            tenant_id=brazos.id,
            asset_id=asset["id"],
            read_at=at("2026-01-29"),
            channel="total",
            prior_value=Decimal("2200"),
            current_value=Decimal("3400"),
            multiplier=Decimal("1"),
            consumption=Decimal("600.000000"),
            unit="kWh",
            source="import",
            status="ok",
            lifecycle="committed",
            days_since_prior=30,
            trues_up_read_ids=[str(est.id)],
        )
        result = services.supersede_read(
            marcus, nov.id, {"value": "2500", "reason": "field verification"}
        )
        new_est = _head_for(est)
        assert new_est.consumption == Decimal("750.000000")
        true_up.refresh_from_db()
        assert true_up.superseded_by_id is not None
        new_true_up = _head_for(true_up)
        assert new_true_up.prior_value == Decimal("2500")
        assert new_true_up.current_value == Decimal("3400")  # source data untouched
        assert new_true_up.consumption == Decimal("150.000000")
        assert new_true_up.trues_up_read_ids == [str(new_est.id)]
        assert result["cascade"]["recomputed"] == [str(new_est.id), str(new_true_up.id)]


# ── (3 continued) a billed ESTIMATE is flagged, and stays countable ─────────
@pytest.mark.django_db
def test_br_met_126__a_billed_estimate_is_flagged_and_keeps_its_estimated_status(brazos, marcus):
    """Its status must stay `estimated` — `_standing_estimates` and the true-up
    count standing estimates BY that status, and the flag must not break the
    arithmetic it warns about. The recommendation lives in rule_outcomes; the
    chip gap for this one shape is REPORTED, not papered over."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus, asset_no="M-9106")
        _chain(
            marcus,
            asset["id"],
            [
                ("2025-10-01", "1000", None, "0", None),
                ("2025-10-31", "1600", "1000", "600.000000", 30),
                ("2025-11-30", "2200", "1600", "600.000000", 30),
            ],
        )
        nov = models.MeterRead.objects.get(read_at=at("2025-11-30"))
        est = commit_read(
            marcus,
            asset["id"],
            day="2025-12-30",
            value=None,
            consumption="600.000000",
            days_since_prior=30,
            estimated=True,
        )
        assert services.mark_read_billed(est.id) is True
        result = services.supersede_read(
            marcus, nov.id, {"value": "2500", "reason": "field verification"}
        )
        est.refresh_from_db()
        assert est.superseded_by_id is None
        assert est.consumption == Decimal("600.000000")  # untouched
        assert est.status == "estimated"  # NOT stale_prior — see docstring
        flag = _outcome(est, "cascade_stale_billed")
        assert flag is not None
        assert flag["detail"]["recomputed_consumption"] == "750.000000"
        assert flag["detail"]["door"] == "correct_billed_read"
        assert result["cascade"]["stopped"] == "billed_boundary"


# ── (1) no next reading → nothing to do ─────────────────────────────────────
@pytest.mark.django_db
def test_br_met_126__correcting_the_last_reading_cascades_to_nothing(brazos, marcus):
    with tenant_ctx(brazos):
        asset, dec, jan, feb = _dec_jan_feb(marcus, asset_no="M-9107")
        before = models.MeterRead.objects.count()
        result = services.supersede_read(marcus, feb.id, {"value": "5900", "reason": "re-read"})
        assert models.MeterRead.objects.count() == before + 1  # the correction only
        assert result["cascade"]["recomputed"] == []
        assert result["cascade"]["flagged"] == []
        assert result["cascade"]["stopped"] == "end_of_chain"


# ── the billed-correction door cascades too ─────────────────────────────────
@pytest.mark.django_db
def test_br_met_126__the_billed_correction_door_triggers_the_same_cascade(
    brazos, marcus, monkeypatch
):
    """A billed January corrected through `correct_billed_read` leaves February
    exactly as stale as the plain path — the cascade runs from both doors."""
    monkeypatch.setattr(
        services.seams,
        "invoice_ref",
        lambda _id: {"id": str(_id), "invoice_no": "BL-2601-000042", "status": "issued"},
    )
    with tenant_ctx(brazos):
        asset, dec, jan, feb = _dec_jan_feb(marcus, asset_no="M-9108")
        assert services.mark_read_billed(jan.id) is True
        result = services.correct_billed_read(
            marcus,
            jan.id,
            {
                "value": "5200",
                "reason": "meter tested — register misread",
                "invoice_id": "019f0000-0000-7000-8000-00000000c101",
            },
        )
        feb.refresh_from_db()
        assert feb.superseded_by_id is not None
        new_feb = _head_for(feb)
        assert new_feb.prior_value == Decimal("5200")
        assert new_feb.consumption == Decimal("600.000000")
        assert result["cascade"]["recomputed"] == [str(new_feb.id)]


# ── tenant scoping: the cascade never crosses tenants ───────────────────────
@pytest.mark.django_db
def test_br_met_126__the_cascade_stays_inside_its_tenant(brazos, marcus, lonestar, erin):
    with tenant_ctx(lonestar):
        # Lone Star Ridge is the Water-only isolation tenant — its twin chain
        # is a water meter, same registers, different world.
        _asset, _dec, _jan, other_feb = _dec_jan_feb(
            erin, asset_no="M-9109", service="water", uom="kgal"
        )
    with tenant_ctx(brazos):
        asset, dec, jan, feb = _dec_jan_feb(marcus, asset_no="M-9109")
        services.supersede_read(marcus, jan.id, {"value": "5200", "reason": "misread"})
    other_feb.refresh_from_db()
    assert other_feb.superseded_by_id is None  # the twin chain next door untouched
    assert other_feb.prior_value == Decimal("5000")
