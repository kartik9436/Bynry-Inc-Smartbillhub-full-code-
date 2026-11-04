# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-007 (batch context, CSV upload & column mapping) ·
#           US-MET-008 (validation run + per-row dispositions) ·
#           US-MET-009 (duplicate-vs-committed & replace-as-correction) ·
#           US-MET-010 (compliance stamp & atomic commit)
#           Screens: S28 · S25 · S29
# Rules:    BR-MET-012 (staged — no meter_reads row before commit) ·
#           BR-MET-013/014/032 (published template, auto-detect, no mapping
#           memory, tag inheritance) · BR-MET-015 (errors resolved, warnings
#           accepted with a reason) · BR-MET-016/024/053 (supersede, never
#           edit) · BR-MET-017 (compliance stamp) · BR-MET-018 🔒 (file+tags
#           idempotency — commit BLOCKED, OQ-044 option b) · BR-MET-019
#           (consumption with an EXPLICIT unit) · BR-MET-059 (channel model)
# Journeys: J2 step 5 — commit leaves one committed row per (meter, date,
#           channel), status ok/estimated, ready for the rating pickup
# ───────────────────────────────────────────────────────
"""The S28 read-import pipeline, end to end.

The claim these tests defend above all others: **every row that enters the
file comes out of the report**, accepted / flagged / rejected, each with its
reason. A silently dropped row is DEF-016's failure mode, so the batch counts
are asserted to RECONCILE against the row set rather than merely to look
plausible.
"""

from decimal import Decimal

import pytest

from apps.metering import models, read_import, selectors, services
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    commit_read,
    accept_warnings,
    csv_body,
    seed_config,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── US-MET-007: staging (steps 1–2) ─────────────────────────────────────────


def test_us_met_007_tc1__csv_stages_a_batch_and_nothing_else(brazos, marcus, audit_rows):
    """BR-MET-012: an upload creates a STAGED batch only — no read exists."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,Access ok"))
        assert batch["status"] == "staged"
        assert models.MeterRead.objects.count() == 0  # BR-MET-012, the whole point
        assert models.ReadImportRow.objects.filter(batch_id=batch["id"]).count() == 1
    # BR-MET-013: mapping auto-detected against the PUBLISHED template headers.
    assert batch["mapping"]["meter_id"] == "meter_id"
    assert batch["mapping"]["reading"] == "reading"
    assert batch["mapping"]["channel"] == "channel"
    assert "read_batch.staged" in [r["action"] for r in audit_rows]


def test_us_met_007_tc10__a_file_without_a_channel_column_stages_as_total(brazos, marcus):
    """BR-MET-059: absent channel ⇒ `total`, the flat meter's one channel —
    every staged row carries an EXPLICIT channel, never a null."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        body = "meter_id,read_date,reading\nM-7001,2026-08-03,42864\n"
        batch = stage(marcus, body)
        rows = models.ReadImportRow.objects.filter(batch_id=batch["id"])
        assert [r.channel for r in rows] == ["total"]


def test_us_met_007_tc5__a_file_with_no_read_value_column_stages_nothing(brazos, marcus):
    """BR-MET-013: meter/date/value must map before Continue. The step blocks
    with a specific reason and NOTHING is staged — not a partial batch."""
    with tenant_ctx(brazos):
        seed_config()
        with pytest.raises(errors.ValidationError) as exc:
            stage(marcus, "meter_id,read_date\nM-7001,2026-08-03\n")
        assert exc.value.message_key.endswith(read_import.ERR_UNMAPPED)
        assert exc.value.params["missing"] == ["reading"]
        assert models.ReadImportBatch.objects.count() == 0


def test_us_met_007_tc6__non_utf8_and_oversize_files_are_refused(brazos, marcus):
    with tenant_ctx(brazos):
        with pytest.raises(read_import.ImportFileError) as exc:
            read_import.parse_csv("meter_id\n\xff\xfe".encode("utf-16"))
        assert exc.value.code == read_import.ERR_ENCODING
        with pytest.raises(read_import.ImportFileError) as exc:
            read_import.parse_csv(b"x" * (read_import.CSV_BYTE_CAP + 1))
        assert exc.value.code == read_import.ERR_TOO_LARGE


def test_us_met_007_tc7__an_unparseable_date_is_kept_verbatim_not_coerced(brazos, marcus):
    """BR-MET-032 validate-then-accept: the row stages WITH its parse error;
    "13/45/2026" never becomes a date."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,13/45/2026,42864,total,E,"))
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
    assert row.read_at is None
    assert row.read_at_raw == "13/45/2026"  # kept verbatim
    assert row.severity == "error"
    assert row.rule_outcomes[0]["detail"]["code"] == read_import.ERR_DATE_UNPARSEABLE


def test_us_met_007_tc9__mapping_is_re_detected_every_upload_never_remembered(brazos, marcus):
    """BR-MET-032 / OQ-040 CLOSED: no mapping memory exists to consult. The
    detector is a pure function of the headers it is handed."""
    first = read_import.detect_mapping(["Meter #", "Read date", "Read value"])
    second = read_import.detect_mapping(["meter_id", "read_date", "reading"])
    assert first["meter_id"] == "Meter #" and second["meter_id"] == "meter_id"
    # There is no persistence API to call — the absence IS the rule.
    assert not hasattr(read_import, "save_mapping")


def test_us_met_007_tc2__a_row_service_overrides_the_batch_tag(brazos, marcus):
    """BR-MET-014: tags inherit unless a mapped column overrides that row."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        a_meter(marcus, "M-7002", unit_label="Unit B", service="water", uom="gal")
        batch = stage(
            marcus,
            csv_body("M-7001,2026-08-03,42864,total,,", "M-7002,2026-08-03,412000,total,W,"),
            service="electric",
        )
        rows = {
            r.meter_no_raw: r for r in models.ReadImportRow.objects.filter(batch_id=batch["id"])
        }
    assert rows["M-7001"].service == "electric"  # inherited
    assert rows["M-7002"].service == "W"  # row override beats the tag


def test_us_met_007_tc3__manual_entry_uses_the_same_parser(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7108")
        batch = services.stage_read_batch(
            marcus,
            {
                "source_kind": "manual",
                "source_detail": "self_read",
                "period_month": "2026-08-01",
                "rows": [{"meter_id": "M-7108", "read_date": "2026-08-03", "reading": "89204"}],
            },
        )
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
    assert row.channel == "total" and row.value == Decimal("89204")


def test_us_met_007__the_ami_replay_card_is_refused_until_its_seam_exists(brazos, marcus):
    """US-MET-007 §5: the card renders DISABLED until the B7 head-end seam
    lands. Accepting it would promise a replay nothing can perform."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            services.stage_read_batch(
                marcus,
                {"source_kind": "ami_replay", "period_month": "2026-08-01", "rows": [{}]},
            )


# ── US-MET-008: validation over staged rows (step 3) ────────────────────────


def test_us_met_008__every_staged_row_is_accounted_for_in_the_counts(brazos, marcus):
    """DEF-016 guard: the composition must RECONCILE — every row lands in
    exactly one severity bucket and the buckets sum to the row count."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        a_meter(marcus, "M-7002", unit_label="Unit B")
        batch = stage(
            marcus,
            csv_body(
                "M-7001,2026-08-03,42864,total,E,",
                "M-9999,2026-08-03,1000,total,E,",  # unknown meter → error
                "M-7002,13/45/2026,500,total,E,",  # parse error
            ),
        )
        summary = services.validate_read_batch(marcus, batch["id"])
    counts = summary["counts"]
    assert counts["rows"] == 3
    assert counts["reconciles"] is True  # nothing dropped between file and report
    assert counts["severity_total"] == 3


def test_us_met_008_tc8__an_unknown_meter_errors_and_creates_nothing(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        batch = stage(marcus, csv_body("M-9999,2026-08-03,1000,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
    rules = {o["rule"]: o for o in row.rule_outcomes}
    assert rules["unknown_meter"]["severity"] == "error"
    assert row.asset_id is None  # never auto-create a meter


def test_us_met_008_tc5_tc6__errors_block_the_post_and_an_override_needs_a_reason(brazos, marcus):
    """BR-MET-015: an error must be resolved before that ROW can post, and an
    override without a reason is refused.

    ⚠ **AMENDED 2026-08-30 — BR-MET-940 SUPERSEDES THE HALF THIS TEST ASSERTED
    (CR-054 task 14), AND THE TEST IS CHANGED IN PLACE RATHER THAN DELETED.**

    It used to assert that an unresolved error refused the WHOLE BATCH:

        with pytest.raises(errors.BizError) as exc:
            services.commit_read_batch(marcus, batch["id"], {"certified": True})
        assert exc.value.code == errors.BIZ_COMPLETENESS
        assert exc.value.params["rows"] == [1]

    The PO ruled that shape out — *"all or nothing will not work - we accept
    what is correct and rejct what i not correct"* — after CR-047 shipped
    partial posting for the account importer. What BR-MET-015 still governs is
    the ROW, and that is what is asserted now: the errored reading does NOT
    post, it comes back with a reason, and the two disposition refusals below
    (TC-6's *reason required*, and *no plain accept of an error*) are untouched
    by the ruling and untouched here.
    """
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-07-03", value=88204, consumption=600)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,88102,total,E,"))  # negative usage
        services.validate_read_batch(marcus, batch["id"])

        # TC-6 and its sibling run FIRST now, because the commit below closes
        # the batch (BR-MET-017) and a disposition on a posted batch would be
        # refused for a different reason than the one under test.
        with pytest.raises(errors.ValidationError):  # TC-6: reason required
            services.set_row_disposition(
                marcus, batch["id"], 1, {"disposition": "override", "value": "88304"}
            )
        # And a plain accept of an ERROR is refused outright (BR-MET-015).
        with pytest.raises(errors.ValidationError):
            services.set_row_disposition(marcus, batch["id"], 1, {"disposition": "accept"})

        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        # The ROW is still held — BR-MET-015's error half, unchanged — and now
        # it says why instead of refusing the batch it is in.
        assert result["posted_reads"] == 0
        assert result["held_reads"] == 1
        assert result["unresolved_errors"] == 1
        assert [row["row_no"] for row in result["held_rows"]] == [1]
        # Scoped to THIS batch: the fixture's own history read is `source
        # ="import"` too, so a bare source filter would count the past.
        assert models.MeterRead.objects.filter(import_batch_id=batch["id"]).count() == 0


def test_us_met_008_tc7__a_rejected_row_is_excluded_but_retained(brazos, marcus, audit_rows):
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        services.set_row_disposition(
            marcus, batch["id"], 1, {"disposition": "reject", "reason": "already posted in 08-A"}
        )
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
    assert result["posted_reads"] == 0
    assert row.disposition == "reject" and row.disposition_reason  # retained with its reason
    assert result["counts"]["rejected"] == 1
    assert "read_row.dispositioned" in [r["action"] for r in audit_rows]


# ── US-MET-009: duplicates ──────────────────────────────────────────────────


def test_us_met_009_tc1__a_committed_duplicate_errors_with_the_existing_read(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        existing = commit_read(marcus, asset["id"], day="2026-08-03", value=42864, consumption=684)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
    duplicate = [o for o in row.rule_outcomes if o["rule"] == "duplicate"][0]
    assert duplicate["severity"] == "error"
    assert duplicate["detail"]["existing_read_id"] == str(existing.id)


def test_us_met_009_tc8__the_same_date_on_another_channel_is_not_a_duplicate(brazos, marcus):
    """BR-MET-052: the key is (meter, date, CHANNEL). Both records coexist."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus, "M-7450")
        commit_read(marcus, asset["id"], day="2026-08-03", value=44562, consumption=424)
        batch = stage(marcus, csv_body("M-7450,2026-08-03,13210,tou_on,E,"))
        services.validate_read_batch(marcus, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
    assert not [o for o in row.rule_outcomes if o["rule"] == "duplicate"]


def test_us_met_009_tc4__an_intra_batch_duplicate_errors_on_the_second_row(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7420")
        batch = stage(
            marcus,
            csv_body("M-7420,2026-08-03,1000,total,E,", "M-7420,2026-08-03,1200,total,E,"),
        )
        services.validate_read_batch(marcus, batch["id"])
        rows = list(models.ReadImportRow.objects.filter(batch_id=batch["id"]).order_by("row_no"))
    assert not [o for o in rows[0].rule_outcomes if o["rule"] == "duplicate"]
    second = [o for o in rows[1].rule_outcomes if o["rule"] == "duplicate"][0]
    assert second["detail"]["scope"] == "intra_batch" and second["detail"]["first_row_no"] == 1


def test_us_met_009_tc3__replace_existing_supersedes_and_never_edits(brazos, marcus, audit_rows):
    """BR-MET-016/053: the original stays intact apart from its two closure
    columns, and the head resolves to the new row."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-07-03", value=42180, consumption=612)
        original = commit_read(
            marcus, asset["id"], day="2026-08-03", value=42864, consumption=684, prior_value=42180
        )
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42876,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        services.set_row_disposition(
            marcus,
            batch["id"],
            1,
            {"disposition": "override", "value": "42876", "reason": "collector re-read"},
        )
        services.commit_read_batch(marcus, batch["id"], {"certified": True})

        original.refresh_from_db()
        heads = list(
            models.MeterRead.objects.filter(
                asset_id=asset["id"],
                channel="total",
                read_at=at("2026-08-03"),
                superseded_by_id__isnull=True,
            )
        )
    assert len(heads) == 1  # exactly one lineage head per (asset, date, channel)
    assert original.superseded_by_id == heads[0].id and original.superseded_at is not None
    assert original.current_value == Decimal("42864")  # the ORIGINAL value is untouched
    # US-MET-009 §4: consumption recomputed on the head = 42,876 − 42,180 = 696.
    assert heads[0].consumption == Decimal("696.000000")
    assert heads[0].unit == "kWh"  # rule 3 — never bare
    assert "read.superseded" in [r["action"] for r in audit_rows]


# ── US-MET-010: compliance stamp & atomic commit ────────────────────────────


def test_us_met_010_tc1__commit_posts_one_row_per_meter_date_channel(brazos, marcus, audit_rows):
    """J2 step 5's handoff contract: committed reads, one per channel, each
    with its batch linkage, an explicit channel and an explicit unit."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-07-03", value=42180, consumption=612)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        accept_warnings(marcus, batch["id"])  # BR-MET-015: vacant-unit warning accepted
        result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        read = models.MeterRead.objects.get(
            asset_id=asset["id"], read_at=at("2026-08-03"), channel="total"
        )
    assert result["status"] == "posted" and result["posted_reads"] == 1
    # US-MET-008 §4: (42,864 − 42,180) × 1 = 684.000000 kWh.
    assert read.consumption == Decimal("684.000000")
    assert read.unit == "kWh" and read.channel == "total"
    assert read.lifecycle == "committed" and str(read.import_batch_id) == batch["id"]
    assert read.days_since_prior == 31
    assert "read_batch.posted" in [r["action"] for r in audit_rows]


def test_us_met_010_tc4__posting_without_certification_is_blocked(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        with pytest.raises(errors.ValidationError) as exc:
            services.commit_read_batch(marcus, batch["id"], {})
    assert exc.value.code == errors.VAL_REQUIRED
    assert models.MeterRead.objects.count() == 0


def test_us_met_010_tc5__an_identical_resubmission_is_blocked_with_who_and_when(brazos, marcus):
    """BR-MET-018 🔒 / OQ-044 closure option b: the file+tags key BLOCKS the
    second commit and names the original — there is no double-post path."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        body = csv_body("M-7001,2026-08-03,42864,total,E,")
        first = stage(marcus, body)
        services.validate_read_batch(marcus, first["id"])
        accept_warnings(marcus, first["id"])
        services.commit_read_batch(marcus, first["id"], {"certified": True})

        second = stage(marcus, body)  # same file, same tags
        services.validate_read_batch(marcus, second["id"])
        with pytest.raises(errors.BizError) as exc:
            services.commit_read_batch(marcus, second["id"], {"certified": True})
        assert models.MeterRead.objects.count() == 1  # never doubled
    assert exc.value.code == errors.BIZ_IDEMPOTENT
    assert exc.value.params["batch_id"] == first["id"]
    assert exc.value.params["posted_at"] is not None


def test_us_met_010_tc6__a_changed_row_makes_a_different_batch(brazos, marcus):
    """The file half of the key is the SHA-256 of the bytes: one changed row
    is a new batch (and the per-row duplicate rule still guards the overlap)."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        a_meter(marcus, "M-7002", unit_label="Unit B")
        first = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, first["id"])
        accept_warnings(marcus, first["id"])
        services.commit_read_batch(marcus, first["id"], {"certified": True})
        second = stage(
            marcus,
            csv_body("M-7001,2026-08-03,42864,total,E,", "M-7002,2026-08-03,900,total,E,"),
        )
        summary = services.validate_read_batch(marcus, second["id"])
        # Not an idempotency block — a genuine new batch whose overlapping row
        # is caught by the per-row duplicate rule instead (BR-MET-016).
        assert summary["counts"]["errors"] == 1  # the overlapping row only


def test_us_met_010_tc3__a_failure_mid_commit_posts_nothing(brazos, marcus, monkeypatch):
    """Atomic by construction: the transaction rolls back and the batch stays
    un-posted — no partial batch is ever visible."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        a_meter(marcus, "M-7002", unit_label="Unit B")
        batch = stage(
            marcus,
            csv_body("M-7001,2026-08-03,42864,total,E,", "M-7002,2026-08-03,900,total,E,"),
        )
        services.validate_read_batch(marcus, batch["id"])
        accept_warnings(marcus, batch["id"])

        calls = {"n": 0}
        real = services._post_row

        # ⚠ AMENDED 2026-08-26 (CR-038 W2): `**kwargs` rather than a fixed
        # signature. `_post_row` gained keyword-only `enabled_services` /
        # `cycle_codes` (the BR-MET-122 mixed-cycle facts), and a double that
        # pins the OLD arity fails with `TypeError: explode() got an
        # unexpected keyword argument 'enabled_services'` — which
        # `pytest.raises(RuntimeError)` does not catch, so the ATOMICITY this
        # test exists to prove goes unasserted behind a signature complaint.
        # The double now forwards whatever the real function is called with.
        def explode(actor, b, row, config, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("simulated DB error at row 2")
            return real(actor, b, row, config, **kwargs)

        monkeypatch.setattr(services, "_post_row", explode)
        with pytest.raises(RuntimeError):
            services.commit_read_batch(marcus, batch["id"], {"certified": True})
        assert models.MeterRead.objects.count() == 0
        assert models.ReadImportBatch.objects.get(pk=batch["id"]).status != "posted"


def test_us_met_010_tc2__the_compliance_stamp_is_stored_and_rendered(brazos, marcus):
    """BR-MET-017: hash, uploader, timestamp, session and IP are recorded once
    and rendered from storage (the S29 Compliance metadata block)."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        body = csv_body("M-7001,2026-08-03,42864,total,E,")
        batch = services.stage_read_batch(
            marcus,
            {
                "source_kind": "csv",
                "source_detail": "walk_by",
                "period_month": "2026-08-01",
                "file_name": "brazosbend_reads_08A.csv",
                "file_content": body,
                "session_ref": "sess_9f27",
                "ip": "98.200.114.7",
            },
        )
    stamp = batch["compliance"]
    assert stamp["file_hash"] == read_import.file_sha256(body.encode("utf-8"))
    assert stamp["file_name"] == "brazosbend_reads_08A.csv"
    assert stamp["session_ref"] == "sess_9f27" and stamp["ip"] == "98.200.114.7"
    assert stamp["uploaded_at"] is not None


def test_us_met_010__a_posted_batch_refuses_further_writes(brazos, marcus):
    """BR-MET-017 append-only: once posted, the batch takes no more edits."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus)
        batch = stage(marcus, csv_body("M-7001,2026-08-03,42864,total,E,"))
        services.validate_read_batch(marcus, batch["id"])
        services.commit_read_batch(marcus, batch["id"], {"certified": True})
        for call in (
            lambda: services.validate_read_batch(marcus, batch["id"]),
            lambda: services.discard_read_batch(marcus, batch["id"]),
            lambda: services.set_row_disposition(
                marcus, batch["id"], 1, {"disposition": "reject", "reason": "late"}
            ),
        ):
            with pytest.raises(errors.BizError):
                call()


def test_us_met_009_tc6__a_committed_read_has_no_update_or_delete_path(brazos, marcus):
    """BR-MET-053 / CLAUDE.md rule 4: the ONLY UPDATE a committed row accepts
    sets superseded_by_id + superseded_at. There is no value-edit service and
    no delete service — the absence is the enforcement, so it is asserted."""
    assert not hasattr(services, "update_read")
    assert not hasattr(services, "delete_read")
    write_paths = [n for n in dir(services) if n.startswith(("update_read", "delete_read"))]
    assert write_paths == []


def test_us_met_016_tc4__a_billed_read_refuses_a_plain_supersede(brazos, marcus):
    """BR-MET-053: the BILLED lock has no bypass — the correction must travel
    with the money fix through J6 (US-MET-016, billing's half)."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        read = commit_read(marcus, asset["id"], day="2026-07-03", value=42180, consumption=612)
        models.MeterRead.objects.filter(id=read.id, read_at=read.read_at).update(lifecycle="billed")
        with pytest.raises(errors.BizError) as exc:
            services.supersede_read(marcus, str(read.id), {"value": "42190", "reason": "fix"})
    assert exc.value.code == errors.BIZ_LOCKED


def test_us_met_016_tc1__supersede_appends_a_head_and_re_runs_the_flags(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        commit_read(marcus, asset["id"], day="2026-07-03", value=42180, consumption=612)
        original = commit_read(
            marcus, asset["id"], day="2026-08-03", value=42864, consumption=684, prior_value=42180
        )
        new = services.supersede_read(
            marcus, str(original.id), {"value": "42876", "reason": "collector re-read"}
        )
        chain = selectors.read_chain(new["id"])
    assert new["consumption"] == "696.000000" and new["unit"] == "kWh"
    assert [entry["version"] for entry in chain] == [1, 2]
    assert chain[0]["id"] == str(original.id) and chain[1]["id"] == new["id"]
    assert new["rule_outcomes"]  # BR-MET-022: flags re-evaluated on the new row


def test_us_met_007_tc8__staging_and_resolution_never_cross_tenants(brazos, lonestar, marcus, erin):
    """US-MET-008/TC-9: the same meter number exists in both tenants and each
    batch resolves only its own — the app-layer half of the isolation proof
    (the live-RLS half is the G5 suite)."""
    with tenant_ctx(brazos):
        seed_config()
        bb_asset = a_meter(marcus, "M-7001", service="water", uom="gal")
    with tenant_ctx(lonestar):
        seed_config()
        lsr_asset = a_meter(erin, "M-7001", address="9 Ridge Rd", service="water", uom="gal")
        batch = stage(erin, csv_body("M-7001,2026-08-03,4000,total,W,"))
        services.validate_read_batch(erin, batch["id"])
        row = models.ReadImportRow.objects.get(batch_id=batch["id"], row_no=1)
        assert str(row.asset_id) == lsr_asset["id"]
        assert str(row.asset_id) != bb_asset["id"]
        assert models.ReadImportBatch.objects.filter(tenant=lonestar).count() == 1
    with tenant_ctx(brazos):
        assert models.ReadImportBatch.objects.filter(tenant=brazos).count() == 0
