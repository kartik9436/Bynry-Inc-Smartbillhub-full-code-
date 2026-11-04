# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 · the BR-MET-136 follow-up — the per-rule ENABLED switch the
#           S64 lane shipped without (the rule's own last column said so).
# Rules:    BR-MET-136 (PO 2026-08-26, verbatim: "yes every rule that is
#           enabled always run - you ahve to keep default - all enabled") —
#           clause 1 (a flag per (tenant, service)) · clause 2 (default ALL
#           ENABLED at provisioning AND on backfill) · clause 3 (an enabled
#           rule ALWAYS runs; the only lawful non-run is BR-MET-020's
#           skipped-AND-REPORTED fail-safe) · clause 4 (the seven INTEGRITY
#           rules are NOT switchable, and the API refuses BY NAME) · and the
#           trailing clause: "a disabled rule must state on the read that it
#           was disabled rather than vanish" · BR-MET-020 · BR-MET-022/056
#           (outcomes are stored and self-describing) · CLAUDE.md rule 7
#           (every settings write audits field/old/new/actor)
# ───────────────────────────────────────────────────────
"""BR-MET-136 — the judgment-rule ON/OFF switch, per (tenant, service).

Every test's docstring states WHAT IT WOULD CATCH, and the four RED-PROOF
tests quote the ACTUAL failure output produced by breaking the guard first
(hard-won law 7: a guard never proved red is not a guard).
"""

from decimal import Decimal

import pytest

from apps.metering import api as metering_api
from apps.metering import models, selectors, services, validation
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — reads fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    brazos,
    commit_read,
    csv_body,
    lonestar,
    marcus,
    staff_actor,
    stage,
    tenant_ctx,
)
from tests.test_us_ten_helpers import FakeUser, api_call, audit_rows  # noqa: F401

pytestmark = pytest.mark.django_db


# ── pure engine fixtures (no ORM — the validation.py testing style) ─────────
class ServiceConfig:
    """A `read_validation_service_settings` row's SHAPE, switches included."""

    high_pct = Decimal("200")
    high_abs_value = Decimal("50")
    high_abs_unit = "kWh"
    low_pct = Decimal("25")
    zero_scope = "active_non_vacant"
    days_flag_min = 25
    days_flag_max = 35
    days_hard_min = 20
    days_hard_max = 45
    mismatch_default_pct = Decimal("3")
    tou_sum_tolerance_pct = Decimal("1")

    def __init__(self, **overrides):
        self.rule_enabled: dict = {}
        for name, value in overrides.items():
            setattr(self, name, value)


def _high_ctx() -> validation.ReadContext:
    """An electric read 30× its trailing average: 300 kWh against avg 10 kWh —
    ratio 3000% > 200% AND delta 300 kWh > the 50 kWh floor, so the high rule
    WARNS when it is allowed to run."""
    return validation.ReadContext(
        value=Decimal("1300"),
        read_at=at("2026-08-01"),
        unit="kWh",
        multiplier=Decimal("1"),
        prior_value=Decimal("1000"),
        prior_read_at=at("2026-07-01"),
        trailing_actuals=[(Decimal("10"), 30), (Decimal("10"), 30)],
        unit_occupied=True,
        service_code="electric",
    )


def _outcome(outcomes, rule):
    return next(o for o in outcomes if o.rule == rule)


def _severity(outcomes, rule):
    return _outcome(outcomes, rule).severity


# ══════════════════════════════════════════════════════════════════════════
# RED PROOF 1 — clause 1 + the trailing clause: a disabled rule STATES itself
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_136_red_proof__a_disabled_rule_states_itself_on_the_read():
    """WOULD CATCH: a disabled rule that VANISHES from the read's outcomes
    instead of stating that it was switched off — the exact failure BR-MET-136's
    trailing clause names ("a disabled rule must state on the read that it was
    disabled rather than vanish"). A vanished rule is indistinguishable from a
    rule that passed, and the whole point of the flag is that somebody chose.

    PROVED RED FIRST, two ways, and both matter because the second is the
    TEMPTING implementation.

    (a) `apply_rule_switches` returning its input unchanged — the pre-change
        engine, i.e. no switch at all:

            >       assert high.severity == validation.DISABLED
            E       AssertionError: assert 'warning' == 'disabled'
            E         - disabled
            E         + warning
            FAILED tests/test_cr038_br_met_136_rule_switch.py::
              test_br_met_136_red_proof__a_disabled_rule_states_itself_on_the_read

        — the tenant switched the high-usage check off and the engine flagged
        the read anyway.

    (b) `apply_rule_switches` FILTERING the outcome out instead of replacing it
        (`[o for o in outcomes if switches.get(o.rule, True)]`) — the obvious
        one-liner, and the one the ruling forbids:

            >       high = _outcome(outcomes, validation.RULE_HIGH)
            E       StopIteration
            tests/test_cr038_br_met_136_rule_switch.py:90: StopIteration

        — the rule is simply GONE from the read's outcomes. That is the
        "vanish" BR-MET-136's trailing clause names, and note that nothing else
        in the suite noticed: the row still posted, its severity was still `ok`,
        and only a test that goes LOOKING for the rule by name can tell.
    """
    off = ServiceConfig(rule_enabled={validation.RULE_HIGH: False})
    _consumption, outcomes = validation.evaluate_row(_high_ctx(), off)
    high = _outcome(outcomes, validation.RULE_HIGH)
    assert high.severity == validation.DISABLED
    assert high.detail["reason"] == validation.REASON_TENANT_DISABLED
    assert high.detail["rule_ref"] == "BR-MET-136"


def test_br_met_136__the_same_read_with_the_rule_ON_warns():
    """WOULD CATCH: a switch that turns the rule off for EVERYBODY — the
    control for the red proof above. Same fixture, same tenant, switch absent
    (= enabled): the high-usage rule runs and WARNS."""
    _consumption, outcomes = validation.evaluate_row(_high_ctx(), ServiceConfig())
    assert _severity(outcomes, validation.RULE_HIGH) == validation.WARNING


def test_br_met_136__disabled_is_a_distinct_severity_from_not_evaluated():
    """WOULD CATCH: `disabled` collapsed into `not_evaluated`.

    They are different facts to a clerk. `not_evaluated` is a GAP — the batch
    summary's `unevaluated_rules` exists so somebody goes and closes it.
    `disabled` is a CHOICE — nothing to chase. Collapsing them fills the chase
    list with things nobody needs to chase, which is how a chase list stops
    being read. This asserts the two never leak into each other's list."""
    off = ServiceConfig(rule_enabled={validation.RULE_HIGH: False})
    _consumption, outcomes = validation.evaluate_row(_high_ctx(), off)
    assert validation.DISABLED != validation.NOT_EVALUATED
    unevaluated = [g["rule"] for g in validation.unevaluated(outcomes)]
    disabled = [g["rule"] for g in validation.disabled_rules(outcomes)]
    assert validation.RULE_HIGH in disabled
    assert validation.RULE_HIGH not in unevaluated
    # `factor_flag` has no ratified threshold — a real GAP — and stays one.
    assert validation.RULE_FACTOR in unevaluated
    assert validation.RULE_FACTOR not in disabled


def test_br_met_136__a_disabled_rule_never_decides_the_row():
    """WOULD CATCH: `disabled` ranking at or above `ok`, which would let a
    check the tenant told us NOT to look at block a clean row from posting —
    or become the read's ONE primary status (BR-MET-021). A switch that can
    stop a reading is not a switch, it is a new error."""
    off = ServiceConfig(
        rule_enabled={validation.RULE_HIGH: False, validation.RULE_VACANT_UNIT: False}
    )
    _consumption, outcomes = validation.evaluate_row(_high_ctx(), off)
    assert validation.worst_severity(outcomes) == validation.OK
    assert validation.primary_status(outcomes) == validation.OK


def test_br_met_136__the_outcome_count_is_unchanged_by_a_switch():
    """WOULD CATCH: a switch implemented as a FILTER. The read must carry the
    same outcomes either way — only what one of them SAYS changes."""
    on = validation.evaluate_row(_high_ctx(), ServiceConfig())[1]
    off = validation.evaluate_row(
        _high_ctx(), ServiceConfig(rule_enabled={validation.RULE_HIGH: False})
    )[1]
    assert [o.rule for o in on] == [o.rule for o in off]


# ══════════════════════════════════════════════════════════════════════════
# RED PROOF 2 — clause 4: the INTEGRITY rules are not switchable, ANYWHERE
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_136_red_proof__a_stored_integrity_switch_is_ignored_by_the_engine():
    """WOULD CATCH: an integrity rule that a row written OUTSIDE the API — a
    shell, a fixture, a future data migration — could switch off. The API
    refuses the attempt (below), but that door is not the only one, and "the
    meter must exist" must not be switchable by ANY path.

    PROVED RED FIRST by removing the `if rule in JUDGMENT_RULES:` guard from
    `validation.rule_switches`, so a stored map is honoured verbatim:

        >       assert (
                    _severity(outcomes, validation.RULE_UNKNOWN_METER) == validation.ERROR
                ), "the meter-must-exist check was switched off"
        E       AssertionError: the meter-must-exist check was switched off
        E       assert 'disabled' == 'error'
        E         - error
        E         + disabled
        FAILED tests/test_cr038_br_met_136_rule_switch.py::
          test_br_met_136_red_proof__a_stored_integrity_switch_is_ignored_by_the_engine

    — a reading for a meter that does not exist, posting clean, because a JSON
    key said so.
    """
    sabotage = ServiceConfig(rule_enabled={rule: False for rule in validation.INTEGRITY_RULES})
    unknown = validation.ReadContext(asset_known=False, service_code="electric")
    _consumption, outcomes = validation.evaluate_row(unknown, sabotage)
    assert (
        _severity(outcomes, validation.RULE_UNKNOWN_METER) == validation.ERROR
    ), "the meter-must-exist check was switched off"


def test_br_met_136__rule_switches_forces_every_integrity_rule_back_on():
    """WOULD CATCH: the same hole, asserted at the function that owns it, so a
    refactor of `evaluate_row` cannot quietly move the guarantee out."""
    switches = validation.rule_switches(
        ServiceConfig(rule_enabled={rule: False for rule in validation.ALL_RULES})
    )
    for rule in validation.INTEGRITY_RULES:
        assert switches[rule] is True, rule
    for rule in validation.JUDGMENT_RULES:
        assert switches[rule] is False, rule


def test_br_met_136__the_two_rule_lists_partition_the_vocabulary():
    """WOULD CATCH: a rule constant added to the engine that lands in NEITHER
    list — switchable-by-accident or locked-by-accident, and invisible either
    way. The judgment set is defined by SUBTRACTION exactly as the ruling
    defines it, so the two can never overlap or leave a gap."""
    assert set(validation.INTEGRITY_RULES) | set(validation.JUDGMENT_RULES) == set(
        validation.ALL_RULES
    )
    assert not set(validation.INTEGRITY_RULES) & set(validation.JUDGMENT_RULES)
    # the ruling names these seven BY NAME — pinned so a rename is a red test
    assert set(validation.INTEGRITY_RULES) == {
        "unknown_meter",
        "retired_meter",
        "unit_missing",
        "negative_usage",
        "rollover",
        "duplicate",
        "export_not_net",
    }


# ══════════════════════════════════════════════════════════════════════════
# RED PROOF 3 — clause 4 at the API: refuse BY NAME, never ignore
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_136_red_proof__the_api_refuses_to_disable_an_integrity_rule_by_name(brazos):
    """WOULD CATCH: an API that IGNORES `{"duplicate": false}` instead of
    refusing it. A System Admin would be told the save succeeded, see a screen
    that says the check is on, and believe they had turned it off — the
    "built is not wired" shape (hard-won law 2) pointed at a setting.

    PROVED RED FIRST by making `_clean_rule_switches` skip integrity rules
    silently (`continue` with no `fe.append`):

        >           with pytest.raises(errors.ValidationError) as excinfo:
        E           Failed: DID NOT RAISE ValidationError
        FAILED tests/test_cr038_br_met_136_rule_switch.py::
          test_br_met_136_red_proof__the_api_refuses_to_disable_an_integrity_rule_by_name

    — the save returned 200 and the admin's request evaporated. Note what the
    sabotage did NOT break: the row saved correctly, the audit trail was
    correct, and every other test in this file still passed. Only the absence
    of a refusal is wrong, and an absence is what no other check looks for.
    """
    with tenant_ctx(brazos):
        admin = staff_actor(brazos, "system_admin", "lock@brazosbendutilities.test")
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_read_validation_service(
                admin, "electric", {"rule_enabled": {"duplicate": False}}
            )
    err = excinfo.value
    assert err.code == errors.VAL_RANGE
    named = [fe for fe in err.field_errors if fe["params"].get("rule") == "duplicate"]
    assert named, "the refusal must NAME the rule, not just refuse"
    assert named[0]["message_key"] == "metering.read_validation.integrity_rule_locked"
    assert named[0]["params"]["br"] == "BR-MET-136"


def test_br_met_136__an_unknown_rule_name_is_refused_too(brazos):
    """WOULD CATCH: a typo accepted and ignored. `{"hihg": false}` stored
    silently is a tenant who believes the high-usage check is off for the next
    six months of billing."""
    with tenant_ctx(brazos):
        admin = staff_actor(brazos, "system_admin", "typo@brazosbendutilities.test")
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_read_validation_service(
                admin, "electric", {"rule_enabled": {"hihg": False}}
            )
    err = excinfo.value
    assert err.code == errors.VAL_UNKNOWN_LOOKUP
    assert any(fe["params"].get("rule") == "hihg" for fe in err.field_errors)


def test_br_met_136__a_non_boolean_switch_is_refused(brazos):
    """WOULD CATCH: `{"zero": "false"}` — the string — stored and read back as
    truthy, so a rule the tenant turned OFF keeps running. Python's truthiness
    makes this silent; the door refuses it instead."""
    with tenant_ctx(brazos):
        admin = staff_actor(brazos, "system_admin", "str@brazosbendutilities.test")
        with pytest.raises(errors.ValidationError) as excinfo:
            services.save_read_validation_service(
                admin, "electric", {"rule_enabled": {"zero": "false"}}
            )
    assert excinfo.value.code == errors.VAL_FORMAT


# ══════════════════════════════════════════════════════════════════════════
# RED PROOF 4 — clause 2: DEFAULT ALL ENABLED, provisioning AND backfill
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_136_red_proof__every_seeded_row_ships_with_every_rule_enabled(brazos):
    """WOULD CATCH: a provisioning seed (or a backfill) that leaves any rule
    off. BR-MET-136 clause 2 is "default ALL ENABLED, for every service, at
    provisioning AND on backfill", and the acceptance condition is sharper:
    THERE MUST BE NO STATE IN WHICH AN EXISTING TENANT SILENTLY ACQUIRES A
    DISABLED RULE.

    PROVED RED FIRST by declaring the column
    `models.JSONField(default=lambda: {"zero": False})` — one plausible slip, a
    "sensible default" written into DDL:

        >               assert row.rule_enabled == {}, f"{row.service.code} recorded a choice nobody made"
        E               AssertionError: electric recorded a choice nobody made
        E               assert {'zero': False} == {}
        E                 Left contains 1 more item:
        E                 {'zero': False}
        FAILED tests/test_cr038_br_met_136_rule_switch.py::
          test_br_met_136_red_proof__every_seeded_row_ships_with_every_rule_enabled

    The green path asserts the map is EMPTY (no choice recorded) AND that the
    engine reads that as every rule on — both halves, because an empty map read
    as "all off" would pass a test that only checked the column.
    """
    with tenant_ctx(brazos):
        services.ensure_read_validation_settings()
        rows = list(
            models.ReadValidationServiceSettings.objects.filter(tenant_id=brazos.id)
            .select_related("service")
            .all()
        )
        assert rows, "the seed must have created rows to make this assertion mean anything"
        for row in rows:
            assert row.rule_enabled == {}, f"{row.service.code} recorded a choice nobody made"
            switches = validation.rule_switches(row)
            for rule in validation.ALL_RULES:
                assert switches[rule] is True, f"{row.service.code} shipped with {rule} disabled"


def test_br_met_136__an_existing_row_backfilled_to_an_empty_map_runs_everything(brazos):
    """WOULD CATCH: the BACKFILL half. A row that predates the column holds
    exactly what `AddField` wrote — `{}` — and the engine must read that as all
    enabled. Simulated by writing the pre-migration state back onto a live row,
    because the migration itself cannot be re-run inside a test transaction."""
    with tenant_ctx(brazos):
        row = models.ReadValidationServiceSettings.objects.filter(
            tenant_id=brazos.id, service__code="electric"
        ).first()
        assert row is not None
        row.rule_enabled = {}
        row.save(update_fields=["rule_enabled"])
        switches = validation.rule_switches(row)
    assert all(switches.values())


def test_br_met_136__the_legacy_tenant_row_has_no_switches_and_runs_everything():
    """WOULD CATCH: electric/water on the LEGACY tenant-wide fallback silently
    losing rules. That row has no `rule_enabled` column and never will, so
    `getattr` finds nothing — and "nothing" must mean ALL ENABLED, not all
    off."""

    class LegacyRow:
        high_pct = Decimal("200")
        high_abs_kwh = Decimal("50")
        low_pct = Decimal("25")

    assert all(validation.rule_switches(LegacyRow()).values())
    # …and a service with NO config at all (the BR-MET-020 fail-safe) likewise
    assert all(validation.rule_switches(None).values())


# ══════════════════════════════════════════════════════════════════════════
# clause 3 — an ENABLED rule always runs; the only lawful non-run is BR-MET-020
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_136__disabling_one_rule_leaves_every_other_rule_running():
    """WOULD CATCH: a switch that is a per-batch bypass in disguise — one rule
    off quietly suppressing its neighbours. Clause 3 is "an enabled rule ALWAYS
    runs — no silent skipping, no per-batch bypass"."""
    off = ServiceConfig(rule_enabled={validation.RULE_HIGH: False})
    _consumption, outcomes = validation.evaluate_row(_high_ctx(), off)
    disabled = {o.rule for o in outcomes if o.severity == validation.DISABLED}
    assert disabled == {validation.RULE_HIGH}
    # `low` is the high rule's sibling and shares its helper — it must survive
    assert _severity(outcomes, validation.RULE_LOW) in (validation.OK, validation.WARNING)


def test_br_met_136__the_br_met_020_fail_safe_is_still_the_only_other_non_run():
    """WOULD CATCH: the switch being used to paper over a missing figure. A
    rule with NO configured threshold still reports `not_evaluated` with its
    reason (BR-MET-020 / US-MET-011 TC-9) — it does NOT become `disabled`,
    because nobody chose it."""
    _consumption, outcomes = validation.evaluate_row(_high_ctx(), None)
    high = _outcome(outcomes, validation.RULE_HIGH)
    assert high.severity == validation.NOT_EVALUATED
    assert high.detail["reason"] == validation.REASON_NO_CONFIG


# ══════════════════════════════════════════════════════════════════════════
# the write door: persistence, merge, audit
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_136__a_switch_save_persists_and_writes_its_own_audit_row(brazos, audit_rows):
    """WOULD CATCH: BR-MET-136's "and its audit row" going unwritten, or being
    folded into the thresholds row where "who turned the vacant-unit check off"
    becomes a grep through every figure edit the tenant ever made."""
    audit_rows.clear()
    saved = api_call(
        metering_api.read_validation_service_settings,
        "put",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
        data={"rule_enabled": {"vacant_unit": False}},
        service="electric",
    )
    assert saved.status_code == 200
    assert saved.data["rule_enabled"]["vacant_unit"] is False
    assert saved.data["rule_enabled"]["high"] is True
    rows = [r for r in audit_rows if r["action"] == "settings.read_validation.rule_switched"]
    assert len(rows) == 1
    assert rows[0]["before"] == {"service": "electric", "vacant_unit": "on"}
    assert rows[0]["after"] == {"service": "electric", "vacant_unit": "off"}
    assert rows[0]["actor_user_id"] is not None
    # a switch-only save must NOT claim a threshold changed
    assert not [r for r in audit_rows if r["action"] == "settings.read_validation.service_updated"]


def test_br_met_136__naming_one_rule_never_re_enables_the_others(brazos):
    """WOULD CATCH: a switch map REPLACED rather than merged. A partial PUT is
    partial for thresholds; it must be partial here too, or a save about the
    zero check silently switches the vacant-unit check back on."""
    with tenant_ctx(brazos):
        admin = staff_actor(brazos, "system_admin", "merge@brazosbendutilities.test")
        services.save_read_validation_service(
            admin, "electric", {"rule_enabled": {"vacant_unit": False}}
        )
        services.save_read_validation_service(admin, "electric", {"rule_enabled": {"zero": False}})
        row = models.ReadValidationServiceSettings.objects.get(
            tenant_id=brazos.id, service__code="electric"
        )
    assert row.rule_enabled == {"vacant_unit": False, "zero": False}


def test_br_met_136__a_no_op_switch_save_writes_nothing(brazos, audit_rows):
    """WOULD CATCH: an audit row per PUT rather than per CHANGE — the settings
    posture the threshold save already keeps."""
    with tenant_ctx(brazos):
        admin = staff_actor(brazos, "system_admin", "noop136@brazosbendutilities.test")
        services.save_read_validation_service(admin, "electric", {"rule_enabled": {"zero": False}})
        audit_rows.clear()
        services.save_read_validation_service(admin, "electric", {"rule_enabled": {"zero": False}})
    assert [r["action"] for r in audit_rows] == []


def test_br_met_136__switching_a_rule_back_on_is_recorded_both_ways(brazos, audit_rows):
    """WOULD CATCH: an audit trail that only records switching OFF. Turning a
    check back on is equally a decision somebody made."""
    with tenant_ctx(brazos):
        admin = staff_actor(brazos, "system_admin", "backon@brazosbendutilities.test")
        services.save_read_validation_service(admin, "electric", {"rule_enabled": {"zero": False}})
        audit_rows.clear()
        services.save_read_validation_service(admin, "electric", {"rule_enabled": {"zero": True}})
    rows = [r for r in audit_rows if r["action"] == "settings.read_validation.rule_switched"]
    assert len(rows) == 1
    assert rows[0]["before"] == {"service": "electric", "zero": "off"}
    assert rows[0]["after"] == {"service": "electric", "zero": "on"}


def test_br_met_136__a_created_row_starts_all_enabled(brazos):
    """WOULD CATCH: a CREATE that requires the switch map (it must not — the
    default is ratified) or that creates a row with rules already off."""
    with tenant_ctx(brazos):
        tenancy_models.TenantService.objects.filter(
            tenant_id=brazos.id, service__code="gas"
        ).update(enabled=True)
        admin = staff_actor(brazos, "system_admin", "gas136@brazosbendutilities.test")
        saved = services.save_read_validation_service(
            admin,
            "gas",
            {
                "high_pct": "200",
                "high_abs_value": "5",
                "high_abs_unit": "ccf",
                "low_pct": "25",
                "zero_scope": "active_non_vacant",
                "days_flag_min": 25,
                "days_flag_max": 35,
                "days_hard_min": 20,
                "days_hard_max": 45,
                "mismatch_pct": "3",
                "tou_sum_tolerance_pct": "1",
            },
        )
    assert all(saved["rule_enabled"].values())


# ══════════════════════════════════════════════════════════════════════════
# the served picture (S64's contract)
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_136__the_overview_serves_the_switchable_vocabulary(brazos):
    """WOULD CATCH: S64 hard-coding either rule list. A screen that lists the
    rules itself disagrees with the engine the first time a rule is added —
    silently, because nothing compares them."""
    read = api_call(
        metering_api.read_validation_settings,
        "get",
        user=FakeUser(),
        role="system_admin",
        tenant=brazos,
    )
    assert read.data["judgment_rules"] == list(validation.JUDGMENT_RULES)
    assert read.data["integrity_rules"] == list(validation.INTEGRITY_RULES)
    for entry in read.data["services"]:
        assert set(entry["rule_enabled"]) == set(validation.JUDGMENT_RULES), entry["service"]
        assert all(entry["rule_enabled"].values()), entry["service"]


def test_br_met_136__the_wire_expands_the_map_so_the_screen_never_guesses(brazos):
    """WOULD CATCH: the stored map (choices only) travelling to the screen
    verbatim, leaving S64 to infer that an absent key means enabled. One place
    knows the convention — `selectors._rule_switch_map` — and it is the
    engine's side of the wire."""
    with tenant_ctx(brazos):
        row = models.ReadValidationServiceSettings.objects.get(
            tenant_id=brazos.id, service__code="electric"
        )
        row.rule_enabled = {"zero": False}
        row.save(update_fields=["rule_enabled"])
        served = selectors.read_validation_service_dict(row)
    assert served["rule_enabled"]["zero"] is False
    assert set(served["rule_enabled"]) == set(validation.JUDGMENT_RULES)
    assert served["rule_enabled"]["high"] is True


# ══════════════════════════════════════════════════════════════════════════
# end to end: a staged batch states the disabled rule on the row AND the batch
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_136__a_validated_batch_states_the_disabled_rule_on_row_and_summary(brazos, marcus):
    """WOULD CATCH: the statement stopping at the engine. BR-MET-136's trailing
    clause is about what a CLERK sees, so the `disabled` outcome has to survive
    into stored `rule_outcomes` AND be summarised on the batch beside — never
    inside — `unevaluated_rules`."""
    with tenant_ctx(brazos):
        admin = staff_actor(brazos, "system_admin", "batch136@brazosbendutilities.test")
        services.save_read_validation_service(
            admin, "electric", {"rule_enabled": {"vacant_unit": False}}
        )
        meter = a_meter(marcus, "M-8136", service="electric", uom="kWh", address="1 Switch Ln")
        commit_read(marcus, meter["id"], day="2026-07-01", value=1000, consumption="10")
        batch = stage(marcus, csv_body("M-8136,2026-08-01,1300,total,electric"))
        summary = services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(tenant_id=brazos.id, batch_id=batch["id"])
    stated = [o for o in row.rule_outcomes if o["rule"] == "vacant_unit"]
    assert stated, "the disabled rule vanished from the row's stored outcomes"
    assert stated[0]["severity"] == validation.DISABLED
    assert stated[0]["detail"]["reason"] == validation.REASON_TENANT_DISABLED
    assert {d["rule"] for d in summary["disabled_rules"]} == {"vacant_unit"}
    assert "vacant_unit" not in {g["rule"] for g in summary["unevaluated_rules"]}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 · BR-MET-136 (04-docs/05-modules/04-metering/02-business-rules.md)
# generated: 2026-08-26 by the CR-038 BR-MET-136 rule-switch lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(DOM half is
#         07-frontend/src/features/tenancy/SettingsReadValidation.test.tsx)
#         F✔ G✔ H=PENDING (🔒 migration — ledger row appended)
# gates: ruff✔ black✔ makemigrations --check✔ · the four red proofs quote their
#        ACTUAL pre-fix failure output in their own docstrings (law 7)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
