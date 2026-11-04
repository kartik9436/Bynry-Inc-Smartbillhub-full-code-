# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (CR-023 P4 stage 3) · CR-028 AST-W3 (the three assets
#           targets)   Screens: WFL-01.meters/submeters/devices.3 (Validate)
# Change:   CR-047 — the assets half of "one bad row costs one row, not the
#           migration": the refusals `apps.assets.services._create_asset_inner`
#           raises that the REHEARSAL could not see.
# Rules:    BR-AST-047 (a sub-meter's allocation share) · BR-AST-007/027 (a
#           device's test interval is a number of MONTHS; the seeded default
#           is what a blank cell takes) · BR-MET-090/091 (a rule is a declared
#           row) · BR-AST-045 · BR-AST-033/049 · BR-AST-011 · BR-AST-026
# Tests:    this file
# Impacts:  apps/metering/import_rules.py (the two new rules + evaluators)
# ───────────────────────────────────────────────────────
"""CR-047 assets — **which of the writer's refusals the rehearsal cannot see.**

The change request's finding is that `_create_asset_inner` refuses by name and
`_load_assets_rows` had no savepoint, so one refusal cost the whole run. The
sibling lane adds the savepoint; this file is the other half — moving the
refusals a stage earlier, to where an operator can still fix the file.

⚠ **THE ANSWER IS NOT THE ONE THE CR PROPOSED, AND THE EVIDENCE IS HERE.** Four
rules were proposed. Three of them are already delivered by rules this
catalogue has carried since CR-046, and the fourth is delivered by the loader
itself; adding them would have rejected rows the loader writes without
complaint. The cases below prove that, one refusal at a time, so the next lane
reading the CR does not rebuild them.

What was actually missing is two RANGE refusals — a sub-meter's allocation
share above 100%, and a device's test frequency below one month. Both parse
cleanly, so `AST.VALUES_PARSE` says nothing about them; both are then refused
inside `apps.assets.services._validate_asset`, which is under the write.

**RED-FIRST PROOF (r11 step 2d · hard-won law 7) — quoted from the run made
BEFORE the two rules were declared, on this same tree:**

    FAILED tests/test_cr047_assets_rules.py::
        test_alloc_share_above_100_is_rejected_at_the_rehearsal
    E   AssertionError: assert 'flagged' == 'rejected'

    FAILED tests/test_cr047_assets_rules.py::
        test_a_test_frequency_of_zero_months_is_rejected_at_the_rehearsal
    E   AssertionError: assert 'flagged' == 'rejected'

— `flagged` is the rehearsal telling the operator those rows WILL load, with a
remark. They will not: the same two payloads, put to the writer, come back
refused, and the two cases at the foot of this file assert that refusal by name
so the rules can never be softened without the reason going red with them. With
the rules declared, both rows are `rejected` at stage 3 with their row number
and a sentence a clerk can act on.
"""

import pytest

from apps.metering import import_rules, import_runs, models as metering_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

ALL_OFF = {key: False for key in import_runs.ROW_HANDLING_KEYS}

SUBMETERS_MAPPING = {
    "SERVICE": "service",
    "PARENT": "parent_asset_no",
    "ALLOC": "allocation_share_pct",
}
# ⚠ SERVICE since 2026-09-30 — a required column on the devices sheet (PO ruling;
# plan U2), so every device file here names the one its backflow serves.
DEVICES_MAPPING = {
    "DEVICE_TYPE": "type",
    "SERVICE": "service",
    "TEST_FREQ": "test_interval_months",
}


def _run(actor, target, content, mapping, *, write_mode="insert"):
    run = import_runs.extract(
        actor,
        {
            "target": target,
            "source_kind": "file",
            "file_name": "cr047-assets.csv",
            "content": content,
            "session_ref": "sess_cr047_ast",
            "write_mode": write_mode,
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": mapping, "row_handling": ALL_OFF})
    import_runs.validate(actor, run["id"])
    return run["id"]


def _rows(run_id):
    return {
        row.row_no: row
        for row in metering_models.ImportRunRow.objects.filter(run_id=run_id).order_by("row_no")
    }


def _hits(run_id, code):
    row = metering_models.ImportRuleResult.objects.filter(run_id=run_id, rule_code=code).first()
    assert row is not None, f"{code} was not even DECLARED on this run (BR-MET-091)"
    return row.hits


def _master(actor, tenant):
    """One ACTIVE electric master meter, seated on a unit — everything
    `AST.PARENT_ON_FILE` requires of a sub-meter's parent."""
    from apps.assets import services as asset_services

    premises = make_premises(actor, services_available=["electric", "water"])
    unit = make_unit(actor, premises["id"], label="CR047 Master Unit")
    master = asset_services.create_asset(
        actor,
        {
            "type": "meter",
            "asset_no": "M-7001",
            "service": "electric",
            "unit": "kWh",
            "multiplier": "1",
            "unit_id": unit["id"],
            "install_date": "2024-01-01",
        },
    )
    return master


# ══════════════════════════════════════════════════════════════════════════
# THE TWO REFUSALS THE REHEARSAL COULD NOT SEE
# ══════════════════════════════════════════════════════════════════════════
def test_alloc_share_above_100_is_rejected_at_the_rehearsal(brazos, dana):
    """⛔ **BR-AST-047 — a share of the master above the whole master.**

    `_validate_asset` refuses `allocation_share_pct > 100` by name
    (`assets.allocation_share_range`), and until this rule the rehearsal said
    the row would load: the existing `AST.ALLOC_WITHIN_MASTER` measures the
    in-file TOTAL under one master, warns, and lets the row through.
    """
    with tenant_ctx(brazos):
        _master(dana, brazos)
        content = "SERVICE,PARENT,ALLOC\nelectric,M-7001,150\nelectric,M-7001,40\n"
        run_id = _run(dana, import_runs.TARGET_ASSETS_SUBMETERS, content, SUBMETERS_MAPPING)

        rows = _rows(run_id)
        assert rows[1].outcome == "rejected"
        assert _hits(run_id, "AST.ALLOC_SHARE_IN_RANGE") == 1
        # The sentence is for a clerk: the operator's own cell value, no ids.
        assert "150" in rows[1].problem
        assert "%" in rows[1].problem


def test_a_lawful_share_is_untouched_by_the_new_rule(brazos, dana):
    """⚠ **THE LAWFUL ROW THIS RULE MUST NOT REJECT.** Two rows of 60% under
    one master total 120% — which the WARNING already flags — but neither row
    on its own exceeds the master, and the writer accepts both. A rule that
    fired on the total would reject rows the loader writes without complaint.
    """
    with tenant_ctx(brazos):
        _master(dana, brazos)
        content = (
            "SERVICE,PARENT,ALLOC\nelectric,M-7001,60\nelectric,M-7001,60\nelectric,M-7001,100\n"
        )
        run_id = _run(dana, import_runs.TARGET_ASSETS_SUBMETERS, content, SUBMETERS_MAPPING)

        rows = _rows(run_id)
        assert _hits(run_id, "AST.ALLOC_SHARE_IN_RANGE") == 0
        # 100 exactly is the boundary and it is LAWFUL — `> 100` is the writer's
        # own predicate, quoted rather than approximated.
        assert rows[3].outcome != "rejected"
        for row_no in (1, 2):
            assert rows[row_no].outcome != "rejected"


def test_a_test_frequency_of_zero_months_is_rejected_at_the_rehearsal(brazos, dana):
    """⛔ **A DEVICE TESTED EVERY ZERO MONTHS.** `0` is how a clerk spells
    *"never"* in a spreadsheet, it parses as a whole number, and
    `_validate_asset` then refuses it (`assets.test_interval_range`) from
    under the write. Blank is the lawful way to say the same thing.
    """
    with tenant_ctx(brazos):
        content = "DEVICE_TYPE,SERVICE,TEST_FREQ\nbackflow,water,0\nbackflow,water,12\nbackflow,water,\n"
        run_id = _run(dana, import_runs.TARGET_ASSETS_DEVICES, content, DEVICES_MAPPING)

        rows = _rows(run_id)
        assert rows[1].outcome == "rejected"
        assert _hits(run_id, "AST.TEST_INTERVAL_POSITIVE") == 1
        assert "0" in rows[1].problem
        # ⚠ THE TWO LAWFUL ROWS. A stated interval loads; a BLANK one loads and
        # takes the seeded default for its type (`SEED_TEST_INTERVAL_MONTHS`),
        # which is exactly why a rule demanding a value would be wrong.
        assert rows[2].outcome != "rejected"
        assert rows[3].outcome != "rejected"


def test_a_negative_test_frequency_is_rejected_too(brazos, dana):
    """`-6` parses (`KIND_INTEGER` accepts a sign) and the writer refuses it on
    the same `months < 1` predicate, so the rule quotes that predicate rather
    than testing for zero."""
    with tenant_ctx(brazos):
        content = "DEVICE_TYPE,SERVICE,TEST_FREQ\nbackflow,water,-6\n"
        run_id = _run(dana, import_runs.TARGET_ASSETS_DEVICES, content, DEVICES_MAPPING)
        assert _rows(run_id)[1].outcome == "rejected"


# ══════════════════════════════════════════════════════════════════════════
# THE RULES ARE DECLARED ROWS, SCOPED TO ONE TARGET (BR-MET-090/091)
# ══════════════════════════════════════════════════════════════════════════
def test_each_new_rule_is_declared_on_its_own_target_and_nowhere_else():
    """A sub-meter carries an allocation share and a device carries a test
    frequency; neither column exists on the other's template, so a rule
    declared on both would be listed against a column the operator was never
    offered."""
    codes = {
        target: {rule.code for rule in rules}
        for target, rules in import_rules.PLATFORM_CATALOG.items()
    }
    assert "AST.ALLOC_SHARE_IN_RANGE" in codes["assets_submeters"]
    assert "AST.TEST_INTERVAL_POSITIVE" in codes["assets_devices"]
    for target in ("assets_meters", "assets_devices", "premises", "units", "accounts"):
        assert "AST.ALLOC_SHARE_IN_RANGE" not in codes[target]
    for target in ("assets_meters", "assets_submeters", "premises", "units", "accounts"):
        assert "AST.TEST_INTERVAL_POSITIVE" not in codes[target]


def test_both_new_rules_have_an_evaluator_registered():
    """BR-MET-091: a rule the product cannot evaluate is DECLARED and marked
    unavailable. These two can be evaluated, so they must be in `EVALUATORS` —
    hard-won law 2, because a declared rule with no evaluator returns nothing
    and every test that only reads the rule LIST still passes."""
    for kind in ("alloc_share_in_range", "test_interval_positive"):
        assert kind in import_rules.EVALUATORS


def test_both_new_rules_block_the_load():
    """The writer refuses these rows whatever this table says, which is why
    they are TIER 1 and ERROR — the posture `AST.SERVICE_AT_PREMISES` states:
    a switchable rule would tell an operator the load succeeded when it did
    not."""
    declared = [
        rule
        for target in ("assets_submeters", "assets_devices")
        for rule in import_rules.PLATFORM_CATALOG[target]
        if rule.code in ("AST.ALLOC_SHARE_IN_RANGE", "AST.TEST_INTERVAL_POSITIVE")
    ]
    assert len(declared) == 2
    for rule in declared:
        assert rule.tier == import_rules.TIER_STRUCTURAL
        assert rule.severity == import_rules.ERROR
        assert rule.action == import_rules.REJECT_ROW
        assert rule.blocks


# ══════════════════════════════════════════════════════════════════════════
# WHY THE OTHER FOUR PROPOSED RULES WERE **NOT** WRITTEN — the evidence, so
# the next lane reading CR-047 does not rebuild them.
# ══════════════════════════════════════════════════════════════════════════
def test_a_number_already_on_file_never_reaches_the_writers_hard_block(brazos, dana):
    """⛔ **`AST.NUMBER_NOT_ALREADY_ON_FILE` WAS NOT WRITTEN, AND THIS IS WHY.**

    `_create_asset_inner` raises `BR-AST-033` when the number it is about to
    write is already on file. Since the PO ruling of 2026-08-27 no file-supplied
    number can reach that line at all:

      * a quoted number that IS on file is `AST.NUMBER_ON_FILE`, which under
        `insert` is re-declared ERROR/reject_row by `_for_write_mode`, and under
        `insert & update` routes the row to the UPDATE path instead of a create;
      * a quoted number that is NOT on file is `AST.NUMBER_NOT_ON_FILE`, an
        ERROR already;
      * and the create branch of `_load_assets_rows` pops `asset_no` outright,
        so the number always comes from the tenant's series.

    A third rule would have been a third sentence about the same cell.
    """
    with tenant_ctx(brazos):
        master = _master(dana, brazos)
        content = "DEVICE_TYPE,SERVICE,TEST_FREQ\nbackflow,water,12\n"
        assert master["asset_no"]
        run_id = _run(dana, import_runs.TARGET_ASSETS_DEVICES, content, DEVICES_MAPPING)
        # The two rules that own the number question are DECLARED on this run.
        for code in ("AST.NUMBER_ON_FILE", "AST.NUMBER_NOT_ON_FILE"):
            assert metering_models.ImportRuleResult.objects.filter(
                run_id=run_id, rule_code=code
            ).exists()


def test_an_external_ref_already_on_file_is_rejected_under_insert_by_the_existing_rule(
    brazos, dana
):
    """⛔ **`AST.EXTERNAL_REF_FREE` WAS NOT WRITTEN.** BR-AST-049's hard block
    (`_refuse_duplicate_external_ref`) is unreachable from the import for the
    same structural reason: `_key_of` treats `ext:<ref>` as a MATCH KEY, so a
    row whose legacy reference is on file is either updated (`insert & update`)
    or rejected at stage 3 by `AST.NUMBER_ON_FILE` under `insert` — which
    already reads BOTH identifiers (`_eval_asset_no_on_file`).

    An unconditional *"the legacy reference is free"* rule would have rejected
    the correction re-run that `external_ref` matching exists to serve.
    """
    from apps.assets import services as asset_services

    with tenant_ctx(brazos):
        premises = make_premises(dana, services_available=["electric", "water"])
        unit = make_unit(dana, premises["id"], label="CR047 Ext Unit")
        asset_services.create_asset(
            dana,
            {
                "type": "backflow",
                "asset_no": "BF-7100",
                "external_ref": "LEG-42",
                "unit_id": unit["id"],
                "install_date": "2024-01-01",
            },
        )
        content = "DEVICE_TYPE,SERVICE,TEST_FREQ,LEGACY\nbackflow,water,12,LEG-42\n"
        run_id = _run(
            dana,
            import_runs.TARGET_ASSETS_DEVICES,
            content,
            {**DEVICES_MAPPING, "LEGACY": "external_ref"},
        )
        rows = _rows(run_id)
        assert rows[1].outcome == "rejected"
        assert _hits(run_id, "AST.NUMBER_ON_FILE") == 1


def test_a_blank_install_date_on_an_assigned_row_is_lawful_and_loads(brazos, dana):
    """⛔ **`AST.INSTALL_DATE_REQUIRED_WHEN_ASSIGNED` WAS NOT WRITTEN, AND
    WRITING IT WOULD HAVE BEEN A DEFECT.**

    BR-AST-011's refusal is real, and `_load_assets_rows` never reaches it: the
    create branch does `payload.setdefault("install_date", str(today))` on every
    seated row — `create_asset_for_unit`'s own posture. So a file with no
    install-date column at all is lawful, and a rule demanding one would have
    rejected every row of it.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, services_available=["electric", "water"])
        unit = make_unit(dana, premises["id"], label="CR047 Seat Unit")
        content = f"DEVICE_TYPE,SERVICE,TEST_FREQ,UNIT\nbackflow,water,12,{unit['unit_no']}\n"
        run_id = _run(
            dana,
            import_runs.TARGET_ASSETS_DEVICES,
            content,
            {**DEVICES_MAPPING, "UNIT": "unit_ref"},
        )
        rows = _rows(run_id)
        assert rows[1].outcome != "rejected", rows[1].problem
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["counts"]["created"] == 1
        assert receipt["counts"]["unit_tagged"] == 1


def test_an_unresolved_lookup_never_reaches_the_writer(brazos, dana):
    """⛔ **`AST.LOOKUPS_RESOLVE` WAS NOT WRITTEN.** Stage 2 resolves every
    `KIND_LOOKUP` cell against the tenant's own index and stores `None` when it
    misses; `_asset_payload_from` then drops every `None`. So an unknown meter
    type or read method never crosses the seam and the writer's
    `VAL_UNKNOWN_LOOKUP` refusal cannot fire — which is exactly why
    `AST.METER_TYPE_IN_LOOKUP` and `AST.READ_METHOD_IN_LOOKUP` are warnings
    that say *"this row will load with no meter type set"* and are RIGHT to be.

    The two lookup misses that WOULD reach a refusal already carry ERROR rules
    of their own: `AST.DEVICE_TYPE_ON_FILE` (a non-null FK) and
    `AST.SIZE_CLASS_IN_LOOKUP` (BR-MET-530).
    """
    with tenant_ctx(brazos):
        content = "DEVICE_TYPE,SERVICE,TEST_FREQ\nnot_a_device_type,water,12\n"
        run_id = _run(dana, import_runs.TARGET_ASSETS_DEVICES, content, DEVICES_MAPPING)
        rows = _rows(run_id)
        assert rows[1].outcome == "rejected"
        assert _hits(run_id, "AST.DEVICE_TYPE_ON_FILE") == 1


# ══════════════════════════════════════════════════════════════════════════
# THE REFUSAL EACH NEW RULE MOVES FORWARD — asserted BY NAME, so neither rule
# can be softened without the reason for it going red at the same moment.
# ══════════════════════════════════════════════════════════════════════════
def test_the_writer_really_does_refuse_a_share_above_100(brazos, dana):
    """`_validate_asset`'s own refusal, through the import's own seam. This is
    what `AST.ALLOC_SHARE_IN_RANGE` exists to move one stage earlier, and
    without it this refusal reaches the operator only from under the write."""
    from apps.assets import services as asset_services

    with tenant_ctx(brazos):
        master = _master(dana, brazos)
        with pytest.raises(errors.ValidationError) as caught:
            asset_services.create_from_import(
                dana,
                {
                    "type": "sub_meter",
                    "service": "electric",
                    "unit": "kWh",
                    "parent_asset_no": master["asset_no"],
                    "allocation_share_pct": "150",
                },
            )
        assert caught.value.message_key == "assets.allocation_share_range"


def test_the_writer_really_does_refuse_a_zero_month_test_interval(brazos, dana):
    """The same, for the devices target's frequency column."""
    from apps.assets import services as asset_services

    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            asset_services.create_from_import(dana, {"type": "backflow", "test_interval_months": 0})
        assert caught.value.message_key == "assets.test_interval_range"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-047 assets-rules lane (11-change-requests.md CR-047; BR-MET-090/091 CONFIRMED)
# generated: 2026-08-29 by the CR-047 assets-rules lane
# checklist: A✔ B=n/a(no-frontend-half) C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr047_assets_rules.py · DEF-2516's pre-existing set unchanged
# exceptions: the four rules CR-047 proposed are NOT written — each is pinned above with the rule that already carries it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
