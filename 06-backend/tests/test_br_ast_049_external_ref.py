# ── Trace ──────────────────────────────────────────────
# Story:    CR-046 waves A · B · C1 · D · F · I — the PO ruling of 2026-08-27
#           ("A METER NUMBER IS ALLOCATED FROM THE TENANT'S SERIES, NEVER TAKEN
#           FROM AN UPLOADED FILE", its ADDENDUM, and "THE METER IMPORT'S
#           SPINE, RE-ORDERED BY THE PO")   Screens: WFL-01 assets targets
# Rules:    BR-AST-049 (the ruling, whole) · BR-AST-026 (per-type prefixes;
#           the series is now the ONLY path on this target) · BR-AST-033 (a
#           duplicate serial WARNS, which is why serial_no cannot be a match
#           key) · BR-AST-045 (blank unit → inventory — CONFIRMED, untouched)
#           · BR-TEN-035 (numbers are never renumbered; forward-only)
# Tests:    this file
# Impacts:  apps/assets (models · services · selectors) · apps/metering
#           (import_runs · import_rules · seams · api)
# ───────────────────────────────────────────────────────
"""**BR-AST-049 — the meter number is ISSUED, and the file's own number is kept.**

⚠ **WHY THIS FILE EXISTS SEPARATELY FROM `test_cr028_import_targets.py`.** That
suite proves the assets import WORKS; this one proves the four things the PO
ruled about WHO CHOOSES THE NUMBER, each of which is a promise a later lane
could break without breaking a single assertion over there:

1. a new asset's number comes from the tenant's series and never from the file;
2. the utility's own legacy reference survives the import and identifies ONE row;
3. a row naming a record already on file is REJECTED under *Insert new only*
   and UPDATED under *Insert & update* — which requires stage 3 to know the
   write mode, a thing it did not know until CR-046 wave B;
4. the rehearsal PROJECTS the numbers and **consumes none of them**.

**EVERY ASSERTION HERE WAS DRIVEN RED FIRST** (hard-won law 7); the failures are
quoted in the lane's review-ledger row.
"""

from __future__ import annotations

import csv
import io

import pytest

from apps.assets import models as assets_models
from apps.assets import selectors as assets_selectors
from apps.metering import import_runs, import_rules
from apps.metering import models as metering_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_cr028_import_targets import (  # noqa: F401 — fixture + helper chain
    ALL_OFF,
    METERS_MAPPING,
    _extract,
    _rejects,
)
from tests.test_cr028_seed import seeded, silvercreek  # noqa: F401 — fixture chain
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


#: A file with NO `METER_NO` column at all — the shape a utility cutting a
#: fresh export produces once the template stops asking for a number.
#: ⚠ **`electric`, NOT `water`, AND THE CHOICE IS THE FIXTURE'S NOT A
#: PREFERENCE.** Silvercreek's seeded units already hold a WATER meter each
#: (`W-5000`…), and `AST.UNIT_SERVICE_FREE` rejects a second active meter for
#: the same service on one seat (r10 row 588). A fixture that fell foul of that
#: would be testing the seat rule, not the numbering rule.
#: ⚠ **AND FROM 2026-09-02 THE SEAT HAD TO MOVE, NOT THE SERVICE
#: (`DEF-AST-9259`).** `CR-062` C4 (`70879c9aa`) seeds a meter per unit per
#: METERED service, so `SCW-U-001`…`SCW-U-050` now hold `E-5000`… beside
#: `W-5000`… and an electric row on them is a second meter on a taken seat.
#: Every case below then failed on the seat rule — *"Unit SCW-U-001 already has
#: an active electric meter (E-5000)"* — exactly the fall-through this comment
#: warned about. The rows now seat on `SCW-U-202`…`204`, units the seed leaves
#: empty on a premises that sells electric; the product was right throughout.
NEW_METERS = (
    "EXTERNAL_REF,METER_TYPE,SERVICE,READ_METHOD,MULTIPLIER,UNIT_REF,SERIAL_NO\n"
    "OLD-7001,ami,electric,ami,1,SCW-U-202,SN-AAA-1\n"
    "OLD-7002,ami,electric,ami,1,SCW-U-203,SN-AAA-2\n"
)
NEW_MAPPING = {
    "EXTERNAL_REF": "external_ref",
    "METER_TYPE": "meter_type",
    "SERVICE": "service",
    "READ_METHOD": "read_method",
    "MULTIPLIER": "multiplier",
    "UNIT_REF": "unit_ref",
    "SERIAL_NO": "serial_no",
}


def _validated(actor, target, content, mapping, write_mode=None):
    """The three read-only stages, with the run's WRITE MODE stated at stage 1.

    ⚠ It is passed to BOTH `extract` and `validate` on purpose — that is the
    contract CR-046 wave B built, and a helper that exercised only one of them
    would leave the other free to rot."""
    run = import_runs.extract(
        actor,
        {
            "target": target,
            "source_kind": "file",
            "file_name": "br-ast-049.csv",
            "content": content,
            **({"write_mode": write_mode} if write_mode else {}),
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": mapping, "row_handling": ALL_OFF})
    import_runs.validate(actor, run["id"], write_mode)
    return run["id"]


def _series_next(series: str = "asset") -> int:
    return tenancy_models.NumberSeries.objects.get(series=series).next_number


# ══════════════════════════════════════════════════════════════════════════
# A · THE TEMPLATE AND THE NUMBER
# ══════════════════════════════════════════════════════════════════════════


def test_a6__the_downloadable_sample_ships_the_number_cell_blank(seeded):
    """**CR-046 A6, and it is proved by READING THE GENERATED FILE.**

    A column definition that declares `sample=""` is not the guarantee — the
    generated file is (hard-won law 1). `DEF-962` is exactly this failure in
    the other direction: `_asset_column` wrote the key unconditionally, three
    columns shipped empty that should have carried a value, and the definitions
    all looked right.

    ⚠ **AND `SERIAL_NO` MUST BE IN THE HEADER**, because the ruling's own
    safety argument is that the manufacturer's serial is *"what the file still
    supplies"* — and until 2026-08-27 no assets template offered it at all.
    """
    tenant, _actor = seeded
    with tenant_ctx(tenant):
        for target in ("assets_meters", "assets_submeters", "assets_devices"):
            _name, body = import_runs.sample_csv(target)
            rows = list(csv.reader(io.StringIO(body)))
            # DEF-1077 — the header row is the column's LABEL now, so the
            # per-FIELD facts below key off `sample_columns`, the same list
            # `sample_csv` writes.
            _header, worked = rows[0], rows[1]
            fields = [str(c["target"]) for c in import_runs.sample_columns(target)]
            cells = dict(zip(fields, worked))
            assert "asset_no" in fields, f"{target}: the column must STAY (the ADDENDUM)"
            assert cells["asset_no"] == "", (
                f"{target}: the sample proposes {cells['asset_no']!r} as a meter number. "
                "The PO objected to being asked to invent one; a template that fills it "
                "in is that objection shipped as a default."
            )
            assert "serial_no" in fields, f"{target}: the manufacturer's serial is not offered"
            assert "external_ref" in fields, f"{target}: the utility's own number has nowhere to go"


def test_a_blank_number_is_issued_from_the_series_with_its_type_prefix(seeded):
    """BR-AST-026 + BR-AST-049: no number in, an `M-` number out, and the
    counter moved by exactly the number of rows written."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        before = _series_next()
        run_id = _validated(actor, "assets_meters", NEW_METERS, NEW_MAPPING, "insert")
        import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        created = assets_models.Asset.objects.filter(external_ref__in=("OLD-7001", "OLD-7002"))
        assert created.count() == 2
        for asset in created:
            assert asset.asset_no.startswith("M-"), asset.asset_no
            # ⚠ THE FILE'S OWN VALUE IS NOWHERE NEAR THE NUMBER.
            assert not asset.asset_no.startswith("OLD-")
        assert _series_next() == before + 2


def test_the_manufacturer_serial_is_written_exactly_as_the_file_gives_it(seeded):
    """BR-TEN-035's protection, which the ruling says the serial carries. If
    the serial were dropped the ruling would be removing the LAST identifier
    the operator controls."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", NEW_METERS, NEW_MAPPING, "insert")
        import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        assert assets_models.Asset.objects.get(external_ref="OLD-7001").serial_no == "SN-AAA-1"


def test_an_invented_number_is_rejected_and_told_where_its_own_number_goes(seeded):
    """`AST.NUMBER_NOT_ON_FILE` — the PO's objection made checkable.

    ⚠ The fix hint must name `External reference` and `Serial number`. Told
    only *"leave it blank"*, an operator deletes data they have no other home
    for, which is the loss the ruling's consequence paragraph exists to
    prevent."""
    tenant, actor = seeded
    content = (
        "ASSET_NO,METER_TYPE,SERVICE,READ_METHOD,MULTIPLIER,UNIT_REF\n"
        "MADE-UP-1,ami,electric,ami,1,SCW-U-001\n"
    )
    mapping = {
        "ASSET_NO": "asset_no",
        "METER_TYPE": "meter_type",
        "SERVICE": "service",
        "READ_METHOD": "read_method",
        "MULTIPLIER": "multiplier",
        "UNIT_REF": "unit_ref",
    }
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", content, mapping, "insert")
        rejects = _rejects(run_id)
        assert 1 in rejects, rejects
        problem, fix = rejects[1]
        assert "not a number this utility has issued" in problem
        assert "External reference" in fix and "Serial number" in fix


# ══════════════════════════════════════════════════════════════════════════
# B · STAGE 3 LEARNS THE WRITE MODE (CR-046 wave B)
# ══════════════════════════════════════════════════════════════════════════


def test_b2__the_write_mode_reaches_stage_three(seeded):
    """**`DEF-543`'S OBSTACLE IS GONE, AND THIS IS THE TEST THAT KEEPS IT GONE.**

    DEF-543 reasoned that an on-file match must WARN because *"stage 3 does not
    know the write mode"*. `CR-042` moved the CHOICE to step 1 — but the VALUE
    never moved with it: `ImportRun.write_mode` was written only at stage 4, so
    the statement stayed literally true at the server for a different reason
    than the one it gave.

    Two halves, and the second is the one a refactor breaks silently: the run
    must RECORD the mode, and `resolve()` must ACT on it."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", NEW_METERS, NEW_MAPPING, "insert")
        run = metering_models.ImportRun.objects.get(pk=run_id)
        assert run.write_mode == "insert", "the run did not record the mode"

        # ⚠ **THE TWO RECORDING PATHS ARE ASSERTED SEPARATELY, and the first
        # version of this test did not do that.** Stage 1 records the choice
        # and stage 3 re-records it (stage 4's *Change it* walks back to step
        # 1 — DEF-770 — so a run can be judged more than once). With both live,
        # deleting EITHER leaves the test green off the other, which is a
        # check that cannot distinguish pass from fail. Proved by mutation:
        # removing stage 1's line passed until these two blocks were added.
        only_stage_one = import_runs.extract(
            actor,
            {
                "target": "assets_meters",
                "source_kind": "file",
                "file_name": "stage-one-only.csv",
                "content": NEW_METERS.replace("OLD-70", "S1-70"),
                "write_mode": "upsert",
            },
        )
        assert (
            metering_models.ImportRun.objects.get(pk=only_stage_one["id"]).write_mode == "upsert"
        ), "stage 1 did not record the mode on the run"

        only_stage_three = import_runs.extract(
            actor,
            {
                "target": "assets_meters",
                "source_kind": "file",
                "file_name": "stage-three-only.csv",
                "content": NEW_METERS.replace("OLD-70", "S3-70"),
            },
        )
        assert metering_models.ImportRun.objects.get(pk=only_stage_three["id"]).write_mode is None
        import_runs.transform(
            actor, only_stage_three["id"], {"mapping": NEW_MAPPING, "row_handling": ALL_OFF}
        )
        import_runs.validate(actor, only_stage_three["id"], "upsert")
        assert (
            metering_models.ImportRun.objects.get(pk=only_stage_three["id"]).write_mode == "upsert"
        ), "stage 3 did not record the mode on the run"

        by_code = {
            rule.code: rule for rule in import_rules.resolve("assets_meters", tenant.id, "insert")
        }
        assert by_code["AST.NUMBER_ON_FILE"].severity == import_rules.ERROR
        assert "rejected" in by_code["AST.NUMBER_ON_FILE"].sentence

        by_code_upsert = {
            rule.code: rule for rule in import_rules.resolve("assets_meters", tenant.id, "upsert")
        }
        assert by_code_upsert["AST.NUMBER_ON_FILE"].severity == import_rules.WARNING
        # ⚠ THE GENERIC SENTENCE IS RETIRED — a rule that declines to say which
        # outcome applies is withholding the answer now that it knows it.
        for rule in (by_code["AST.NUMBER_ON_FILE"], by_code_upsert["AST.NUMBER_ON_FILE"]):
            assert "the write mode decides" not in rule.sentence.lower()


def test_an_unstated_mode_is_not_insert(seeded):
    """**Hard-won law 3, and `DEF-127`'s rule: an ABSENCE must not be spelled
    the same way as a VALUE.** `insert` is the mode that REJECTS rows, so a
    client that sends no mode must not silently get it."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", NEW_METERS, NEW_MAPPING)
        assert metering_models.ImportRun.objects.get(pk=run_id).write_mode is None
        by_code = {r.code: r for r in import_rules.resolve("assets_meters", tenant.id, None)}
        assert by_code["AST.NUMBER_ON_FILE"].severity == import_rules.WARNING


# ══════════════════════════════════════════════════════════════════════════
# C1 · REJECT UNDER INSERT, UPDATE UNDER INSERT & UPDATE
# ══════════════════════════════════════════════════════════════════════════


def _load_two(actor):
    run_id = _validated(actor, "assets_meters", NEW_METERS, NEW_MAPPING, "insert")
    import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})


def test_c1__insert_rejects_a_row_naming_a_record_already_on_file(seeded):
    """PO verbatim: *"in case of insert - reject it"*. The SAME file run twice.

    ⚠ **REJECTED, NOT SKIPPED.** A skip reads on a receipt as *"left
    unchanged"* — benign, nothing to do. That is the word this lane had chosen
    before the PO chose a different one."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        _load_two(actor)
        run_id = _validated(actor, "assets_meters", NEW_METERS, NEW_MAPPING, "insert")
        rejects = _rejects(run_id)
        assert set(rejects) == {1, 2}, rejects
        problem, fix = rejects[1]
        assert "already carries this external reference" in problem
        assert "Insert & update" in fix
        run = metering_models.ImportRun.objects.get(pk=run_id)
        assert run.counts["errors"] == 2


def test_c1__insert_and_update_updates_the_details_instead(seeded):
    """The other half of the same PO sentence — *"in case of Insert & Update =
    update the details"* — and no second asset is created."""
    tenant, actor = seeded
    changed = NEW_METERS.replace("SN-AAA-1", "SN-REPLACED-1")
    with tenant_ctx(tenant):
        _load_two(actor)
        before = assets_models.Asset.objects.count()
        run_id = _validated(actor, "assets_meters", changed, NEW_MAPPING, "upsert")
        assert metering_models.ImportRun.objects.get(pk=run_id).counts["errors"] == 0
        receipt = import_runs.load(actor, run_id, {"write_mode": "upsert", "approved": True})
        assert receipt["receipt"]["loaded"] == 2
        assert assets_models.Asset.objects.count() == before
        assert assets_models.Asset.objects.get(external_ref="OLD-7001").serial_no == "SN-REPLACED-1"


def test_the_legacy_reference_names_one_record_and_only_one(seeded):
    """BR-AST-049's uniqueness, refused BY NAME rather than as an
    `IntegrityError` — a 500 off a constraint name would abort a 1,847-row
    commit instead of reporting one bad row."""
    from apps.assets import services as assets_services

    tenant, actor = seeded
    with tenant_ctx(tenant):
        _load_two(actor)
        with pytest.raises(errors.BizError) as caught:
            assets_services.create_asset(
                actor,
                {
                    "type": "meter",
                    "service": "electric",
                    "meter_type": "ami",
                    "external_ref": "old-7001",  # ⚠ LOWERED — the index is CI
                },
            )
        assert caught.value.message_key == "assets.external_ref_duplicate"


# ══════════════════════════════════════════════════════════════════════════
# D · THE DRY RUN TELLS THE TRUTH AND SPENDS NOTHING
# ══════════════════════════════════════════════════════════════════════════


def test_d1_d4__the_dry_run_projects_the_numbers_and_consumes_none_of_them(seeded):
    """**CR-046 D1 + D4, and D4 is the one worth having.**

    PO, the same day: *"these decisiona should be taken just before updating
    teh record in the database"*. A rehearsal that allocated would burn a
    number per rehearsal, and a rehearsal is allowed to be run twice — the
    series would then show gaps nobody can account for, growing every time an
    operator re-ran a file to clear rejects.

    So: the counter before and after must be IDENTICAL, across two rehearsals,
    and the numbers projected must be the ones the commit actually issues."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", NEW_METERS, NEW_MAPPING, "insert")
        before = _series_next()

        figures = import_runs.dry_run(actor, run_id, "insert")
        import_runs.dry_run(actor, run_id, "insert")  # twice — a rehearsal may repeat

        assert _series_next() == before, (
            "the dry run MOVED the asset series. A rehearsal that allocates burns a "
            "number on a row that may never load (CR-046 D4)."
        )
        issued = figures["will_issue"]
        assert issued["count"] == 2
        assert issued["next_number"] == before
        assert all(number.startswith("M-") for number in issued["numbers"]), issued

        import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        written = sorted(
            assets_models.Asset.objects.filter(
                external_ref__in=("OLD-7001", "OLD-7002")
            ).values_list("asset_no", flat=True)
        )
        assert written == sorted(issued["numbers"]), (
            "the rehearsal named numbers the commit did not issue — a dry run that "
            "lies is worse than none (B15 §16 TC-16)"
        )


def test_d2__the_dry_run_names_the_status_each_row_lands_in(seeded):
    """OQ-840's own question — *"what status you will ahve on this meters"*.

    ⚠ **THE LABELS ARE THE TENANT'S** (BR-AST-031 lets them rename a stage), so
    this asserts the CODES and the classes and takes the names from the same
    rows the product would."""
    tenant, actor = seeded
    mixed = NEW_METERS + "OLD-7003,ami,electric,ami,1,,SN-AAA-3\n"
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", mixed, NEW_MAPPING, "insert")
        figures = import_runs.dry_run(actor, run_id, "insert")
        outcomes = {row["code"]: row for row in figures["will_create_outcomes"]}
        assert outcomes["active"]["behavior_class"] == "in_service"
        assert outcomes["active"]["rows"] == 2
        assert outcomes["inventory"]["behavior_class"] == "available"
        assert outcomes["inventory"]["rows"] == 1
        expected = assets_selectors.import_outcome_stages()
        assert outcomes["inventory"]["name"] == expected["inventory"]["name"]
        # BR-AST-045 stands: the blank-unit row is NOT a reject (OQ-840).
        assert figures["rejected"] == 0


# ══════════════════════════════════════════════════════════════════════════
# F · WHAT THE NEW ORDER MADE LOAD-BEARING
# ══════════════════════════════════════════════════════════════════════════


def test_f1__the_seat_checks_own_meter_exemption_survives_a_correction_rerun(seeded):
    """**CR-046 F1 — the exemption now carries the WHOLE correction re-run and
    had no test of its own.**

    `_eval_unit_service_free` exempts the row whose own meter already holds the
    seat. Before BR-AST-049 that exemption keyed on `asset_no`, which a
    corrected file carried. It no longer does — the operator's file has never
    held a SMARTBillHub number — so the exemption has to resolve through
    `external_ref` instead. Without it, EVERY row of a corrected re-run is
    rejected with *"this unit already has an active water meter"*, which is the
    pile of rejects the ruling's ADDENDUM warns a lane about."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        _load_two(actor)
        # The same file again, corrected, in the mode a correction uses.
        run_id = _validated(
            actor,
            "assets_meters",
            NEW_METERS.replace("SN-AAA-2", "SN-FIXED-2"),
            NEW_MAPPING,
            "upsert",
        )
        rejects = _rejects(run_id)
        assert rejects == {}, (
            "a corrected re-run was rejected for the seats its own meters already "
            f"hold: {rejects}"
        )


def test_f3__the_sub_meter_parent_reference_is_unchanged(seeded):
    """**CR-046 F3 — proved UNCHANGED so no later lane "fixes" it.**

    The ADDENDUM: `parent_asset_no` *"is unchanged and needs no work …
    `_eval_parent_meter_on_file` already requires the master to be on file
    already, so the number being cited is one we issued."* It is still a
    template column, still required on the sub-meters target, and it still
    takes OUR number when the file has one.

    ⚠ **THE ADDENDUM'S *"needs no work"* TURNED OUT TO BE WRONG, and the
    correction is the block of tests below this one.** The column's SHAPE is
    unchanged — that is what this test pins. What the ADDENDUM did not see is
    that the numbering ruling removed the operator's ability to KNOW our
    number on a first migration, so the cell now has to accept two more ways
    of naming the same master. See `test_a_sub_meter_names_its_master_…`."""
    tenant, _actor = seeded
    with tenant_ctx(tenant):
        columns = {c["target"]: c for c in import_runs.target_columns("assets_submeters")}
    parent = columns["parent_asset_no"]
    assert parent["required"] is True
    assert parent["kind"] == "asset_ref"
    assert parent["label"] == "Parent / master meter"
    # ⚠ AND ITS ALIASES ARE UNTOUCHED — `asset_no`'s were re-pointed to
    # `external_ref`; a lane doing the same here would break the one reference
    # that legitimately quotes a number we issued.
    assert import_runs.ASSETS_SUBMETERS_ALIASES["parent_asset_no"] == (
        "parent_mtr",
        "parent",
        "parent meter",
        "master",
        "parent_asset_no",
    )


# ══════════════════════════════════════════════════════════════════════════
# SUB-METERS · THE MIGRATION PATH THE NUMBERING RULING BROKE
# ══════════════════════════════════════════════════════════════════════════
#
# Decision log 2026-08-27, "SUB-METERS ARE ALREADY THEIR OWN UPLOAD": under
# the ruling a master's number is issued by US at import, so a sub-meter file
# naming its masters by the OLD system's identifiers rejects every row for
# masters that loaded a minute earlier. *"That is not a migration path; it is
# a punishment."*

SUBS = (
    "EXTERNAL_REF,METER_TYPE,SERVICE,READ_METHOD,MULTIPLIER,UNIT_REF,PARENT_MTR,ALLOC_PCT\n"
    "OLD-SUB-1,sub_meter,electric,manual,1,SCW-U-001,{parent},40\n"
)
SUBS_MAPPING = {
    "EXTERNAL_REF": "external_ref",
    "METER_TYPE": "meter_type",
    "SERVICE": "service",
    "READ_METHOD": "read_method",
    "MULTIPLIER": "multiplier",
    "UNIT_REF": "unit_ref",
    "PARENT_MTR": "parent_asset_no",
    "ALLOC_PCT": "allocation_share_pct",
}


def _master(actor):
    """One master meter, loaded exactly as a first migration loads it: no
    number in the file, so its number is one the operator has never seen."""
    _load_two(actor)
    return assets_models.Asset.objects.get(external_ref="OLD-7001")


@pytest.mark.parametrize("name_it_by", ["asset_no", "serial_no", "external_ref"])
def test_a_sub_meter_names_its_master_three_ways(seeded, name_it_by):
    """**THE MIGRATION PATH, RESTORED.** The master may be named by our meter
    number, by its serial, or by the utility's own external reference — and
    the last two are the only ones a first migration's file actually holds."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        master = _master(actor)
        token = getattr(master, name_it_by)
        assert token, name_it_by
        run_id = _validated(
            actor, "assets_submeters", SUBS.format(parent=token), SUBS_MAPPING, "insert"
        )
        assert _rejects(run_id) == {}, _rejects(run_id)
        import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        sub = assets_models.Asset.objects.get(external_ref="OLD-SUB-1")
        # ⚠ WHICHEVER WAY IT WAS NAMED, IT HANGS OFF THE SAME MASTER.
        assert sub.parent_asset_id == master.id
        # BR-AST-026 — and a sub must never look like a master in a list or on
        # a work order, so it takes the `SM-` prefix off the SAME series.
        assert sub.asset_no.startswith("SM-"), sub.asset_no
        assert sub.type.code == "sub_meter"


def test_a_serial_carried_by_two_masters_is_refused_by_name_never_picked(seeded):
    """⚠ **`BR-AST-033` MAKES A DUPLICATE SERIAL WARN-BUT-ALLOW**, so a serial
    is not unique and cannot silently identify a master.

    Resolving to the first would hang the sub-meter off the WRONG device, and
    the only symptom would be a wrong bill months later. The row must say
    WHICH ONES and offer the two identifiers that ARE unique."""
    tenant, actor = seeded
    twin = NEW_METERS + "OLD-7003,ami,electric,ami,1,SCW-U-204,SN-AAA-1\n"
    with tenant_ctx(tenant):
        run_id = _validated(actor, "assets_meters", twin, NEW_MAPPING, "insert")
        import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        first = assets_models.Asset.objects.get(external_ref="OLD-7001")
        second = assets_models.Asset.objects.get(external_ref="OLD-7003")
        assert first.serial_no == second.serial_no == "SN-AAA-1"

        sub_run = _validated(
            actor, "assets_submeters", SUBS.format(parent="SN-AAA-1"), SUBS_MAPPING, "insert"
        )
        rejects = _rejects(sub_run)
        assert 1 in rejects, rejects
        problem, fix = rejects[1]
        assert "carried by more than one meter" in problem
        assert first.asset_no in problem and second.asset_no in problem
        assert "meter number" in fix and "external reference" in fix
        assert not assets_models.Asset.objects.filter(external_ref="OLD-SUB-1").exists()


def test_an_update_never_re_hangs_a_sub_meter_on_a_different_master(seeded):
    """**A SPREADSHEET IS NOT WHERE THAT IS DECIDED.** The master is what a
    sub's share is calculated FROM, so re-parenting changes what a bill is
    worked out of — the same reason an update never moves a meter between
    units (BR-AST-034). The re-parenting flow is `reassign_asset`, which asks,
    audits, and carries children with their parent (BR-AST-037)."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        master = _master(actor)
        other = assets_models.Asset.objects.get(external_ref="OLD-7002")
        run_id = _validated(
            actor, "assets_submeters", SUBS.format(parent=master.asset_no), SUBS_MAPPING, "insert"
        )
        import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})

        # The same file, re-cut to point the sub at the OTHER master.
        rerun = _validated(
            actor,
            "assets_submeters",
            SUBS.format(parent=other.asset_no).replace(",manual,", ",walk_by,"),
            SUBS_MAPPING,
            "upsert",
        )
        import_runs.load(actor, rerun, {"write_mode": "upsert", "approved": True})
        sub = assets_models.Asset.objects.get(external_ref="OLD-SUB-1")
        assert sub.parent_asset_id == master.id, "the update RE-HUNG the sub-meter"
        # …and the spec field beside it DID update, so this is not a dead path.
        assert sub.read_method is not None and sub.read_method.code == "walk_by"


# ══════════════════════════════════════════════════════════════════════════
# WAVE I · THE TWO TARGETS CR-046 NEVER NAMED
# ══════════════════════════════════════════════════════════════════════════
#
# `import_runs.TARGETS` holds SIX, not four. CR-046 was written naming four and
# the PO's sub-meter question surfaced the omission; both extra targets carry
# the identifier law. I2/I3/I4 are the sub-meter block above; these are I1, I5
# and I6, which are the *"same shape you have already built once"* — and the
# way to say that honestly is to assert it rather than to claim it.

ASSET_TARGETS = ("assets_meters", "assets_submeters", "assets_devices")


@pytest.mark.parametrize("target", ASSET_TARGETS)
def test_i1_i5__the_identifier_law_holds_on_all_three_assets_targets(seeded, target):
    """**CR-046 I1 + I5.** The column set and the rule set, per target — the two
    halves that make the law true, asserted where a later lane would break one
    and leave the other looking right."""
    tenant, _actor = seeded
    with tenant_ctx(tenant):
        columns = {c["target"]: c for c in import_runs.target_columns(target)}
        # The number column STAYS, ships blank, and says what blank means.
        assert columns["asset_no"]["sample"] == ""
        assert columns["asset_no"]["label"].endswith("number (existing only)")
        # `DEF-MET-9257`: the tab is *Numbering* (renamed in the hint 2026-08-30).
        assert "Settings › Numbering ›" in columns["asset_no"]["help"]
        # The two columns the ruling's own reasoning depends on.
        assert "serial_no" in columns
        assert "external_ref" in columns

        codes = {r.code: r for r in import_rules.resolve(target, tenant.id, "insert")}
        # An invented number blocks in BOTH modes, so it is a plain ERROR…
        assert codes["AST.NUMBER_NOT_ON_FILE"].severity == import_rules.ERROR
        # …and a row naming a record already on file blocks only under insert.
        assert codes["AST.NUMBER_ON_FILE"].severity == import_rules.ERROR
        assert (
            import_rules.resolve(target, tenant.id, "upsert")
            and {r.code: r for r in import_rules.resolve(target, tenant.id, "upsert")}[
                "AST.NUMBER_ON_FILE"
            ].severity
            == import_rules.WARNING
        )
        assert codes["AST.EXTERNAL_REF_UNIQUE"].severity == import_rules.ERROR


DEVICES = (
    "ASSET_NO,EXTERNAL_REF,DEVICE_TYPE,SERVICE,PREMISE_ID,SERIAL_NO\n"
    "{number},OLD-BF-1,backflow,water,P-00101,SN-BF-1\n"
)
DEVICES_MAP = {
    "ASSET_NO": "asset_no",
    "EXTERNAL_REF": "external_ref",
    "DEVICE_TYPE": "type",
    "SERVICE": "service",  # required on the devices sheet since 2026-09-30 (plan U2)
    "PREMISE_ID": "premises",
    "SERIAL_NO": "serial_no",
}


def test_i5__a_device_takes_its_number_from_the_series_and_keeps_the_old_one(seeded):
    """**CR-046 I5, behaviourally.** A structural assertion proves the columns
    and the rules are declared; only a run proves they are WIRED (law 2).

    Two runs of the same file: one inventing a number, which must be rejected
    with the sentence that says where a number comes from, and one leaving it
    blank, which must load with a `BF-` number off the shared asset series."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        invented = _validated(
            actor, "assets_devices", DEVICES.format(number="OLD-BF-1"), DEVICES_MAP, "insert"
        )
        rejects = _rejects(invented)
        assert 1 in rejects, rejects
        assert "not a number this utility has issued" in rejects[1][0]

        run_id = _validated(
            actor, "assets_devices", DEVICES.format(number=""), DEVICES_MAP, "insert"
        )
        assert _rejects(run_id) == {}, _rejects(run_id)
        import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        device = assets_models.Asset.objects.get(external_ref="OLD-BF-1")
        # BR-AST-026's per-type prefix, off the SAME counter the meters use.
        assert device.asset_no.startswith("BF-"), device.asset_no
        assert device.serial_no == "SN-BF-1"


def test_i6__inventory_is_a_status_and_is_not_offered_as_a_target(seeded):
    """⛔ **CR-046 I6 — the misreading that would have become a fourth template
    nobody needs.**

    The PO's own list read *"meters, sub mters, behind the meter and
    investor"*, and the fourth thing is **inventory**. It is a STATUS — where
    any of the three asset KINDS lands when its Unit column is left blank
    (BR-AST-045) — and there is no inventory target, nor may there be one.

    ⚠ **THERE IS NO STEP-1 TARGET PICKER TO POLICE, AND THAT IS THE ANSWER TO
    THE PO'S QUESTION RATHER THAN A GAP.** The target is preselected by the
    entry point the operator came through — `AssetImportWorkflow`'s
    `ASSET_IMPORT_TARGETS` maps the three S49 tabs onto the three asset
    targets, and premises, units and accounts each have their own. So the six
    are named plainly, each by the tab it belongs to, and inventory is offered
    nowhere. This test is what keeps that true: it asserts the vocabulary is
    exactly six and that nothing inventory-shaped has joined it.

    ⚠ **EIGHT, NOT SIX, SINCE 2026-09-22 (`DEF-AST-9259`)** — `parts` joined
    the one importer on 2026-09-07 (`ab382ca64`, CR-077) and `payments` on
    2026-09-22 (`c8bce7c8a`, a lockbox file). Both are their own modules'
    targets with their own screens, neither is inventory-shaped, and the
    inventory assertion below is what this test exists for — so the set is
    brought up to the vocabulary rather than the check loosened to a subset."""
    assert set(import_runs.TARGETS) == {
        "premises",
        "units",
        "assets_meters",
        "assets_submeters",
        "assets_devices",
        "accounts",
        "parts",
        "payments",
    }
    assert not [t for t in import_runs.TARGETS if "inventor" in t or "stock" in t], (
        "an inventory/stock TARGET has appeared. Inventory is a STATUS "
        "(BR-AST-045); a target for it would teach every operator the "
        "misreading CR-046 I6 exists to prevent."
    )
