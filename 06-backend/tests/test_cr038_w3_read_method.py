# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 W3 (2026-08-26) — THE READ METHOD ON THE ROW.
# Rules:    BR-MET-123 (the SOURCE is a TAG chosen at upload; the only
#           transports are file — CSV or Excel — and manual; no integration
#           exists and its absence must never block the tag) ·
#           BR-MET-014 (batch tags inherit to every row UNLESS a row-level
#           column overrides — the override half, finally built) ·
#           BR-AST-043 (read_methods is a TENANT-EXTENSIBLE reference list,
#           seeded AMI · AMR · walk-by · Manual · Mobile — never a hardcoded
#           tuple) · BR-MET-032 (validate THEN accept — an unknown value is
#           kept verbatim with its error attached, never snapped) ·
#           CLAUDE.md hard rule 4 (financial immutability — which is why the
#           legacy mapping is applied on READ and no committed row is rewritten)
# Tests:    this file. Every guard proved RED first; the failing run is quoted
#           verbatim in each docstring.
# Impacts:  apps/metering/read_import.py · apps/metering/services.py ·
#           apps/metering/selectors.py · apps/metering/models.py ·
#           apps/metering/api.py · apps/assets/selectors.py (one read-only
#           options selector) · apps/metering/seams.py
# ───────────────────────────────────────────────────────
"""CR-038 W3 — one read-method vocabulary, carried from step 1 to the read.

THE MEASURED PROBLEM these tests pin down: three vocabularies existed and none
travelled with the reading.

  · the METER carried the PO's five words (`read_methods`, tenant-editable) —
    ⚠ EIGHT since BR-MET-142 (2026-08-27), and that is this file's own sequel:
    the three legacy detail words below that mapped to nothing became methods;
  · the BATCH carried six `source_detail` values (walk_by · drive_by ·
    self_read · field_visit · ami_itron · ami_sensus);
  · the committed READ stored three (`ami` · `manual` · `import`).

AMR and Mobile had nowhere to land, and the method was chosen ONCE per file —
so a cycle read half by AMI and half on foot could not say so.
"""

from decimal import Decimal

import pytest

from apps.metering import models, read_import, selectors, services
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    accept_warnings,
    at,
    brazos,
    commit_read,
    marcus,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def bb(brazos):
    """Brazos Bend with `app.tenant_id` SET for the whole test — hard rule 1.

    The W2 lane spells this `with tenant_ctx(brazos):` around each body; a
    fixture is the same thing with the indentation removed, and it keeps the
    context open across the assertions as well as the arrangement.
    """
    with tenant_ctx(brazos):
        yield brazos


# The ratified read-method words, seeded on the meter side
# (apps.assets.services.SEED_READ_METHODS). This tuple is the ASSERTION, not
# the source: the product reads the tenant's own list.
#
# ⚠ **`PO_FIVE` UNTIL 2026-08-27 — BR-MET-142 made it EIGHT** (PO ruling closing
# OQ-392, verbatim: *"(a) Rule each onto one of the five or you can add new
# categories"*). The name is changed rather than the contents quietly extended,
# so a reader who greps `PO_FIVE` in an older lane report finds nothing and
# looks, instead of finding a tuple of eight called five.
PO_EIGHT = ("ami", "amr", "walk_by", "manual", "mobile", "drive_by", "self_read", "field_visit")

HEADER_WITH_METHOD = "meter_id,read_date,reading,channel,service,read_method,notes\n"


def csv_with_method(*rows: str) -> str:
    return HEADER_WITH_METHOD + "".join(r if r.endswith("\n") else r + "\n" for r in rows)


# ── 1 · ONE VOCABULARY ──────────────────────────────────────────────────────


def test_read_method_vocabulary_is_the_tenants_own_list(bb, marcus):
    """The ratified words resolve from the TENANT's `read_methods` list.

    ⚠ **AND THE ORDER IS ASSERTED, WHICH IS WHY BR-MET-142's THREE ARE LAST.**
    `reference_list_options` sorts seeded-first by `SEED_READ_METHODS`' own
    index, so appending the new words leaves AMI · AMR · walk-by · Manual ·
    Mobile exactly where a clerk has learned to find them in the S28 dropdown.
    Inserting them alphabetically would have moved four shipped options.

    RED FIRST, verbatim:
        AttributeError: module 'apps.metering.selectors' has no attribute
        'read_method_options'
    """
    a_meter(marcus)  # ensures the assets reference catalogs for this tenant
    options = selectors.read_method_options()
    assert [o["code"] for o in options] == list(PO_EIGHT)
    assert {o["name"] for o in options} == {
        "AMI",
        "AMR",
        "walk-by",
        "Manual",
        "Mobile",
        "Drive-by",
        "Self-read",
        "Field visit",
    }


def test_a_tenant_added_method_is_accepted_and_a_deactivated_one_is_not(bb, marcus):
    """BR-AST-043 / BR-TEN-036: the list is DATA. A tenant that adds `drone`
    may tag a batch `drone`; a tenant that deactivates `mobile` may not.

    RED FIRST, verbatim:
        AttributeError: module 'apps.metering.selectors' has no attribute
        'read_method_options'
    """
    from apps.assets import models as asset_models
    from apps.assets import services as asset_services

    a_meter(marcus)
    asset_services.ensure_reference_catalogs()
    tenant_id = services._tenant_id()
    asset_models.ReadMethod.objects.create(
        tenant_id=tenant_id, code="drone", name="Drone flyover", is_system=False, active=True
    )
    asset_models.ReadMethod.objects.filter(tenant_id=tenant_id, code="mobile").update(active=False)

    assert "drone" in {o["code"] for o in selectors.read_method_options()}
    assert "mobile" not in {o["code"] for o in selectors.read_method_options()}

    batch = stage(marcus, csv_with_method("M-7001,2026-08-03,42864,total,E,,ok"),
                  read_method="drone")
    assert batch["read_method"] == "drone"

    with pytest.raises(errors.ValidationError) as refusal:
        stage(marcus, csv_with_method("M-7001,2026-08-04,42900,total,E,,ok"),
              read_method="mobile")
    assert any(f["field"] == "read_method" for f in refusal.value.field_errors)


def test_amr_and_mobile_finally_have_somewhere_to_land(bb, marcus):
    """The measured gap, closed: the two PO words the old three-value read
    `source` could not express now reach a committed read.

    RED FIRST, verbatim:
        AttributeError: 'MeterRead' object has no attribute 'read_method'
    """
    meter = a_meter(marcus)
    seed_config()
    for day, value, method in (("2026-08-03", "42864", "amr"), ("2026-09-03", "43000", "mobile")):
        batch = stage(
            marcus,
            csv_with_method(f"M-7001,{day},{value},total,E,,ok"),
            read_method=method,
            period_month=f"{day[:7]}-01",
        )
        services.validate_read_batch(marcus, batch["id"])
        accept_warnings(marcus, batch["id"])
        services.commit_read_batch(marcus, batch["id"], {"certified": True})
    stored = list(
        models.MeterRead.objects.filter(
            tenant_id=services._tenant_id(), asset_id=meter["id"]
        ).order_by("read_at")
    )
    assert [r.read_method for r in stored] == ["amr", "mobile"]


# ── 2 · THE COLUMN ON THE TEMPLATE AND THE STAGED ROW ───────────────────────


def test_published_template_carries_a_read_method_column():
    """BR-MET-032: one published template. The method column is IN it, with a
    worked example value, or a clerk cannot state a per-row method at all.

    RED FIRST, verbatim:
        AssertionError: assert 'read_method' in ('meter_id', 'read_date',
        'reading', 'channel', 'service', 'notes')
    """
    assert "read_method" in read_import.PUBLISHED_HEADERS
    header, example = read_import.template_csv().splitlines()[:2]
    assert "read_method" in header.split(",")
    position = header.split(",").index("read_method")
    assert example.split(",")[position] == "walk_by"


def test_row_read_method_is_parsed_and_an_unknown_one_is_kept_verbatim():
    """Validate THEN accept (BR-MET-032). The parser does not know the tenant's
    list — it carries the value; services judges it. An unknown value is NEVER
    snapped to the nearest valid one.

    RED FIRST, verbatim:
        KeyError: 'read_method'      ← detect_mapping knew no such target
    """
    mapping, _headers, rows = read_import.parse_csv(
        csv_with_method(
            "M-7001,2026-08-03,42864,total,E,Walk-By,ok",
            "M-7002,2026-08-03,100,total,E,teleportation,ok",
            "M-7003,2026-08-03,200,total,E,,ok",
        ).encode("utf-8")
    )
    assert mapping["read_method"] == "read_method"
    assert rows[0].read_method == "walk_by"  # case + separator folded, nothing else
    assert rows[1].read_method == "teleportation"  # VERBATIM, never snapped
    assert rows[2].read_method is None  # absent → the batch tag inherits


def test_batch_tag_inherits_to_every_row_unless_the_row_overrides(bb, marcus):
    """BR-MET-014, VERBATIM: *"Batch tags (month/cycle/route/service/source)
    inherit to every row unless a row-level column overrides"*. This is the
    override half — an UNBUILT rule until now, not an undecided one.

    RED FIRST, verbatim:
        AttributeError: 'ReadImportRow' object has no attribute 'read_method'
    """
    a_meter(marcus)
    a_meter(marcus, asset_no="M-7002", unit_label="Unit B", address="2 Bluestem Ln")
    batch = stage(
        marcus,
        csv_with_method(
            "M-7001,2026-08-03,42864,total,E,,inherits",
            "M-7002,2026-08-03,555,total,E,ami,overrides",
        ),
        read_method="walk_by",
    )
    rows = models.ReadImportRow.objects.filter(batch_id=batch["id"]).order_by("row_no")
    assert [r.read_method for r in rows] == ["walk_by", "ami"]
    assert models.ReadImportBatch.objects.get(pk=batch["id"]).read_method == "walk_by"


def test_a_mixed_cycle_can_finally_say_so(bb, marcus):
    """THE MEASURED PROBLEM: *"the method is chosen ONCE per file, so a cycle
    read half by AMI and half on foot cannot say so."* It can now.

    RED FIRST, verbatim:
        AttributeError: 'ReadImportRow' object has no attribute 'read_method'
    """
    a_meter(marcus)
    a_meter(marcus, asset_no="M-7002", unit_label="Unit B", address="2 Bluestem Ln")
    batch = stage(
        marcus,
        csv_with_method(
            "M-7001,2026-08-03,42864,total,E,ami,head-end file",
            "M-7002,2026-08-03,555,total,E,walk_by,walked it",
        ),
        read_method="ami",
    )
    rows = models.ReadImportRow.objects.filter(batch_id=batch["id"]).order_by("row_no")
    assert [r.read_method for r in rows] == ["ami", "walk_by"]


def test_an_unknown_row_method_flags_the_row_and_stages_the_batch(bb, marcus):
    """A bad ROW never blocks the FILE (BR-MET-032). The row stages carrying
    its own error and its verbatim value; nothing is dropped.

    RED FIRST, verbatim:
        AssertionError: assert 'ok' == 'error'
        ← the unknown method sailed through with nothing said
    """
    a_meter(marcus)
    batch = stage(
        marcus,
        csv_with_method("M-7001,2026-08-03,42864,total,E,teleportation,ok"),
        read_method="walk_by",
    )
    row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
    assert row.severity == "error"
    assert row.read_method == "teleportation"  # kept, never coerced to the batch tag
    codes = [
        (o.get("detail") or {}).get("code") for o in row.rule_outcomes if o.get("rule") == "parse"
    ]
    assert read_import.ERR_READ_METHOD_UNKNOWN in codes


# ── 3 · CARRIED ONTO THE COMMITTED READ AND SERVED ──────────────────────────


def test_commit_carries_the_row_method_onto_the_read_and_serves_it(bb, marcus):
    """The whole point of the lane: the method TRAVELS WITH THE READING.

    RED FIRST, verbatim:
        AttributeError: 'MeterRead' object has no attribute 'read_method'
    """
    meter = a_meter(marcus)
    seed_config()
    batch = stage(
        marcus,
        csv_with_method("M-7001,2026-08-03,42864,total,E,amr,drive route"),
        read_method="walk_by",
    )
    services.validate_read_batch(marcus, batch["id"])
    accept_warnings(marcus, batch["id"])
    services.commit_read_batch(marcus, batch["id"], {"certified": True})
    read = models.MeterRead.objects.get(tenant_id=services._tenant_id(), asset_id=meter["id"])
    assert read.read_method == "amr"  # the ROW's, not the batch's
    served = selectors.read_dict(read)
    assert served["read_method"] == "amr"
    assert served["read_method_origin"] == "recorded"


def test_the_staged_row_payload_serves_the_method(bb, marcus):
    """S28 step 4 shows the clerk what each row is tagged with.

    RED FIRST, verbatim:
        KeyError: 'read_method'
    """
    a_meter(marcus)
    batch = stage(
        marcus,
        csv_with_method("M-7001,2026-08-03,42864,total,E,ami,ok"),
        read_method="walk_by",
    )
    rows = selectors.read_batch_rows(models.ReadImportBatch.objects.get(pk=batch["id"]))
    assert rows[0]["read_method"] == "ami"
    assert batch["read_method"] == "walk_by"


# ── 4 · THE LEGACY MAPPING — DECLARED, TESTED, APPLIED ON READ ──────────────


def test_legacy_mapping_is_a_declared_table_and_never_guesses():
    """The mapping decision, made explicit and pinned.

    APPLIED ON READ, never as a rewrite of stored rows — see the docstring of
    `read_import.legacy_read_method`. The legacy `source` values plus the six
    legacy `source_detail` values are mapped ONLY where the old word and a
    ratified method are THE SAME WORD. Nothing here is ever a nearest neighbour.

    ⚠ **ALL SIX DETAIL WORDS NOW MAP, AND THE RULE ABOVE DID NOT BEND TO ALLOW
    IT — BR-MET-142 (PO 2026-08-27, closing `OQ-392`).** This docstring said
    *"`drive_by`, `self_read` and `field_visit` name no PO method and are
    therefore NOT GUESSED: they resolve to None"*, and that refusal was right at
    the time. The PO's answer was not to pick a neighbour for each; it was to
    DELEGATE (*"(a) Rule each onto one of the five or you can add new
    categories"*) and the build grew the vocabulary. So those three now map to
    methods **of the same name**, which is the same rule producing a different
    answer because the ratified set changed underneath it.

    RED FIRST, verbatim (this case, on the day the vocabulary grew):
        AssertionError: assert 'drive_by' is None

    RED FIRST when the function was first written, kept as the record:
        AttributeError: module 'apps.metering.read_import' has no attribute
        'legacy_read_method'
    """
    m = read_import.legacy_read_method
    # source alone
    assert m("ami", None) == "ami"
    assert m("manual", None) == "manual"
    assert m("import", None) is None  # a TRANSPORT, not a method — never guessed
    assert m("estimated", None) is None  # nobody collected an estimate
    # source_detail is more specific and wins where it names a PO word
    assert m("import", "walk_by") == "walk_by"
    assert m("import", "ami_itron") == "ami"
    assert m("import", "ami_sensus") == "ami"
    assert m("manual", "walk_by") == "walk_by"
    # ⚠ THE THREE THAT USED TO NAME NO METHOD. Each now maps to a method of the
    # SAME NAME (BR-MET-142) — not to a neighbour, which is the whole point.
    assert m("import", "drive_by") == "drive_by"
    assert m("import", "self_read") == "self_read"
    assert m("import", "field_visit") == "field_visit"
    # ⚠ AND THE MAPPING IS AN IDENTITY, NOT A TRANSLATION, FOR ALL THREE. A
    # later lane "tidying" one of these onto `amr`/`manual`/`mobile` would be
    # re-labelling history nobody verified, which is exactly what the ruling
    # declined to do.
    for legacy in ("drive_by", "self_read", "field_visit"):
        assert read_import.LEGACY_READ_METHOD_BY_DETAIL[legacy] == legacy
    # every mapped target is one of the ratified words
    assert set(read_import.LEGACY_READ_METHOD_BY_DETAIL.values()) <= set(PO_EIGHT)
    assert set(
        v for v in read_import.LEGACY_READ_METHOD_BY_SOURCE.values() if v is not None
    ) <= set(PO_EIGHT)
    # ⚠ NO LEGACY WORD IS LEFT UNMAPPED. This is the half OQ-392 closed: before
    # today three of the six served `read_method_origin = not_stated`, which was
    # an ABSENCE dressed as a value. `not_stated` now means what it says.
    assert set(read_import.LEGACY_READ_METHOD_BY_DETAIL) == set(models.SOURCE_DETAILS)


def test_a_historical_read_keeps_what_it_carries_and_the_mapping_is_applied_on_read(bb, marcus):
    """CLAUDE.md hard rule 4: a committed read is never rewritten. The row on
    file keeps `source='manual'`/`source_detail='walk_by'` and its
    `read_method` column stays NULL; the METHOD is derived at serve time and
    says so.

    RED FIRST, verbatim:
        AttributeError: 'MeterRead' object has no attribute 'read_method'
    """
    meter = a_meter(marcus)
    read = commit_read(marcus, meter["id"], day="2026-07-03", value="42180")
    models.MeterRead.objects.filter(pk=read.pk).update(source="manual", source_detail="walk_by")
    read.refresh_from_db()
    assert read.read_method is None  # NOT rewritten
    served = selectors.read_dict(read)
    assert served["read_method"] == "walk_by"
    assert served["read_method_origin"] == "derived"
    assert served["source"] == "manual"  # the stored fact is still served


def test_a_historical_read_that_states_no_method_says_not_stated(bb, marcus):
    """`source='import'` with no detail is a TRANSPORT and nothing else. The
    product refuses to invent a collection method for it.

    RED FIRST, verbatim:
        KeyError: 'read_method_origin'
    """
    meter = a_meter(marcus)
    read = commit_read(marcus, meter["id"], day="2026-07-03", value="42180")
    assert read.source == "import" and read.source_detail is None
    served = selectors.read_dict(read)
    assert served["read_method"] is None
    assert served["read_method_origin"] == "not_stated"


# ── 5 · THE AMI OPTION THAT REFUSES (BR-MET-123) ────────────────────────────


def test_the_ami_tag_is_available_while_the_ami_transport_is_refused(bb, marcus):
    """BR-MET-123, VERBATIM: *"there is no integration yet; but it should not
    stop us from tagging the soruce and accepting the CSV or excel file"*.

    So: a file COLLECTED by AMI is tagged `ami` and uploaded as a file, and the
    head-end transport is still refused because nothing is behind it.

    RED FIRST, verbatim:
        KeyError: 'read_method'      ← the batch payload served no such tag
    """
    a_meter(marcus)
    batch = stage(
        marcus,
        csv_with_method("M-7001,2026-08-03,42864,total,E,,head-end export"),
        read_method="ami",
    )
    assert batch["read_method"] == "ami"
    assert batch["source_kind"] == "csv"  # the TRANSPORT is a file, as it must be

    with pytest.raises(errors.ValidationError) as refusal:
        stage(
            marcus,
            csv_with_method("M-7001,2026-08-04,42900,total,E,,x"),
            source_kind="ami_replay",
        )
    assert any(f["field"] == "source_kind" for f in refusal.value.field_errors)


def test_an_export_record_inherits_the_method_of_the_read_that_created_it(bb, marcus):
    """BR-AST-029's derived export record is the SAME collection: it inherits
    the method rather than reporting none.

    RED FIRST, verbatim:
        AttributeError: 'MeterRead' object has no attribute 'read_method'
    """
    from apps.assets import models as asset_models

    meter = a_meter(marcus)
    seed_config()
    asset_models.Asset.objects.filter(pk=meter["id"]).update(net_metering=True)
    batch = stage(
        marcus,
        csv_with_method("M-7001,2026-08-03,42864,total,E,,ok"),
        read_method="ami",
    )
    services.validate_read_batch(marcus, batch["id"])
    accept_warnings(marcus, batch["id"])
    services.commit_read_batch(marcus, batch["id"], {"certified": True})
    export = models.MeterRead.objects.get(
        tenant_id=services._tenant_id(), asset_id=meter["id"], channel=models.CHANNEL_EXPORT
    )
    assert export.read_method == "ami"


def test_the_idempotency_key_is_untouched_by_this_lane():
    """🔒 BOUNDARY, ASSERTED SO IT CANNOT DRIFT. BR-MET-018's file+tags key is
    a CLAUDE.md sensitive path whose exact mechanics are the OQ-044 closure's.
    Adding `read_method` to the key would change the fingerprint every ALREADY
    POSTED batch would compute today, so this lane does NOT touch it and
    REPORTS the question instead (lane report → Eng-Lead).

    RED FIRST: this guard was written after the decision and proved by
    deliberately appending "read_method" to IDEMPOTENCY_TAG_FIELDS, verbatim:
        AssertionError: assert ('period_month', 'cycle_id', 'route_id',
        'service', 'source_kind', 'source_detail', 'read_method') ==
        ('period_month', 'cycle_id', 'route_id', 'service', 'source_kind',
        'source_detail')
    """
    assert read_import.IDEMPOTENCY_TAG_FIELDS == (
        "period_month",
        "cycle_id",
        "route_id",
        "service",
        "source_kind",
        "source_detail",
    )


def test_a_manual_entry_batch_carries_its_method_too(bb, marcus):
    """The manual grid is the OTHER lawful transport (BR-MET-123 clause 2) and
    it tags exactly the same way.

    RED FIRST, verbatim:
        AttributeError: 'ReadImportRow' object has no attribute 'read_method'
    """
    a_meter(marcus)
    batch = services.stage_read_batch(
        marcus,
        {
            "source_kind": "manual",
            "read_method": "manual",
            "period_month": "2026-08-01",
            "rows": [
                {
                    "meter_id": "M-7001",
                    "read_date": "2026-08-03",
                    "reading": "42864",
                    "channel": "total",
                },
                {
                    "meter_id": "M-7001",
                    "read_date": "2026-08-04",
                    "reading": "42900",
                    "channel": "total",
                    "read_method": "mobile",
                },
            ],
        },
    )
    rows = models.ReadImportRow.objects.filter(batch_id=batch["id"]).order_by("row_no")
    assert [r.read_method for r in rows] == ["manual", "mobile"]


def test_a_batch_with_no_method_stages_and_says_nothing_rather_than_guessing(bb, marcus):
    """The tag is OPTIONAL, exactly like the other BR-MET-014 tags. A clerk who
    states none gets NULL — never a defaulted `manual` nobody chose.

    RED FIRST, verbatim:
        KeyError: 'read_method'
    """
    a_meter(marcus)
    batch = stage(marcus, csv_with_method("M-7001,2026-08-03,42864,total,E,,ok"))
    assert batch["read_method"] is None
    row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
    assert row.read_method is None


def test_final_read_capture_records_the_method_it_actually_used(bb, marcus):
    """A final read typed on the move/retire form is a MANUAL collection, and
    now says so instead of leaving the method blank.

    RED FIRST, verbatim:
        AttributeError: 'MeterRead' object has no attribute 'read_method'
    """
    meter = a_meter(marcus)
    seed_config()
    services.capture_final_read(
        asset_id=meter["id"], value="42864", read_at="2026-08-03", actor=marcus
    )
    read = models.MeterRead.objects.get(tenant_id=services._tenant_id(), asset_id=meter["id"])
    assert read.source == "manual"
    assert read.read_method == "manual"


def test_a_supersede_carries_the_original_method_forward(bb, marcus):
    """A correction is a NEW row for the SAME collection — it inherits the
    method rather than losing it.

    RED FIRST, verbatim:
        AttributeError: 'MeterRead' object has no attribute 'read_method'
    """
    meter = a_meter(marcus)
    seed_config()
    batch = stage(
        marcus,
        csv_with_method("M-7001,2026-08-03,42864,total,E,walk_by,ok"),
        read_method="walk_by",
    )
    services.validate_read_batch(marcus, batch["id"])
    accept_warnings(marcus, batch["id"])
    services.commit_read_batch(marcus, batch["id"], {"certified": True})
    original = models.MeterRead.objects.get(
        tenant_id=services._tenant_id(), asset_id=meter["id"], superseded_by_id__isnull=True
    )
    services.supersede_read(
        marcus,
        original.id,
        {"value": "42870", "reason": "transcription error on the route sheet"},
    )
    head = models.MeterRead.objects.get(
        tenant_id=services._tenant_id(),
        asset_id=meter["id"],
        channel="total",
        superseded_by_id__isnull=True,
    )
    assert head.current_value == Decimal("42870.000000")
    assert head.read_method == "walk_by"


def test_the_demo_fixture_tags_every_read_batch_with_its_meters_own_method():
    """The demo shows a RECORDED method, and the batch agrees with the meter.

    A fixture where every read reported `derived` would demonstrate the gap
    rather than the fix. This pins the two CR-030 account-detail meters:
    M-4021 is AMI and its reads are tagged `ami`; M-4022 is an AMR water meter
    on a drive-by round and its reads are tagged `drive_by`. Batch and meter
    agreeing is the assertion; neither value is minted here.

    ⚠ **M-4022 WAS `mobile` UNTIL 2026-08-27 AND THE REASON IT WAS IS THE
    INTERESTING PART.** This docstring used to justify it by quoting the
    fixture: *"`CR030_A10432_METERS`, whose own comment calls `mobile` 'the
    seeded read-method code for a drive-by round'"*. That comment was never a
    decision — it asserted `drive_by ≈ Mobile` in prose — and OQ-392 cited this
    very chain as the repo contradicting itself. BR-MET-142 settled it the other
    way: `drive_by` is a method of its own, `mobile` is about what DEVICE was
    used. **A comment claiming a rule is not the rule (hard-won law 1) — and a
    TEST that quotes the comment as its authority inherits the mistake, which is
    what this docstring did for a day.**

    So the assertion is unchanged and is now backed by the third statement that
    always agreed: the batch's own legacy `source_detail`, which has read
    `drive_by` since the fixture was written.

    RED FIRST, verbatim (M-4022's batch tag flipped to "amr"):
        AssertionError: assert 'amr' == 'mobile'
    """
    from core import sample_fixture

    by_asset = {m["asset_no"]: m for m in sample_fixture.CR030_A10432_METERS}
    for meter_reads in sample_fixture.CR030_A10432_READS:
        meter = by_asset[meter_reads["asset_no"]]
        assert meter_reads["read_method"] == meter["read_method"]
    # ⚠ THE THIRD STATEMENT, PINNED SO THE STALE-COMMENT CHAIN CANNOT REFORM.
    # The AMR water meter's legacy `source_detail` and its read METHOD are now
    # the same word, which is what the fixture always meant and could not say.
    water = next(r for r in sample_fixture.CR030_A10432_READS if r["asset_no"] == "M-4022")
    assert water["source_detail"] == "drive_by"
    assert water["read_method"] == "drive_by"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 W3 (read method) — BR-MET-123 + BR-MET-014 quoted verbatim
# generated: 2026-08-26 by the CR-038 W3 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred (🔒 idempotency key deliberately
#            untouched — REPORTED to the Eng-Lead, guarded above)
# gates: see the lane report
# exceptions: the legacy mapping is applied ON READ, not by a data migration —
#             hard rule 4 forbids rewriting a committed read. ⚠ AMENDED
#             2026-08-27 (BR-MET-142): the second half of this sentence read
#             "and three of the six legacy source_detail words name no PO
#             method, so a migration would have to guess". All six map now, each
#             to a method of its own name, so a migration would no longer have
#             to guess — and it STILL DOES NOT SHIP, because hard rule 4 is the
#             load-bearing half and several of those readings are billed. A
#             backfill is a separate, flagged migration with the PO's word on
#             it. REPORTED, not done.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
