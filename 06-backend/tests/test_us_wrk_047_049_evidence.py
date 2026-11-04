# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-047 (out-of-range flags, never refuses) TC-1..TC-6 ·
#           US-WRK-049 (the rule column and the file column) TC-1..TC-6 ·
#           US-WRK-048 (three kinds, the key, the four-hour link) TC-1..TC-7 ·
#           US-WRK-036 (the signature, or the refusal) TC-1..TC-6.
#           Screens: Work-033, Work-012, Work-008
# Rules:    BR-WRK-039 · BR-WRK-040 · BR-WRK-046 · BR-WRK-047 · BR-WRK-047a ·
#           BR-WRK-048 · hard rules 1, 3, 7
# Tests:    this file — every TC named in its own test name
# ───────────────────────────────────────────────────────
"""Wave K by TC — and the one thing this file exists to keep apart.

⚠ **`BR-WRK-039` AND `BR-WRK-040` LOOK ALIKE AND ARE OPPOSITES.** An
out-of-range value FLAGS and never blocks; a missing REQUIRED photograph BLOCKS
and is not a flag. Every plausible bug in wave K is a lane collapsing them —
refusing 1,204 because it is outside the bound, or letting a job close with no
photograph of the dial it disputes. `test_tc*_039_*` and `test_tc*_040_*` are
named so that a failure says which of the two broke.

⚠ **`US-WRK-049`'s COLUMNS ARE THE THIRD CONFUSION AND IT IS NOT A RULE.**
`photo_required` is THE RULE — did the template ask. `photo_attachment_id` is
THE FILE — did anybody take one. A test that only checks *the photograph is
there* cannot tell *asked for and not taken* from *never asked*, which is the
question a supervisor reviewing a disputed final read is asking.

WHAT IS **NOT** TESTED HERE, AND WHERE IT IS
────────────────────────────────────────────────────────────────────────────
The append-only trigger, RLS `FORCE`, and the savepoint that keeps a poisoned
transaction from taking the batch with it are all PostgreSQL behaviour. **SQLite
has none of them**, so an assertion about any of the three passes here by
vacuum — hard-won law 14. They live in `tests/test_us_wrk_048_evidence_pg.py`,
which runs against real PostgreSQL 16 as a NOSUPERUSER NOBYPASSRLS role.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.tenancy import document_models
from apps.tenancy.document_models import StoredDocument
from apps.work import evidence, work_documents
from apps.work import models as work_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import THREE_READINGS, _published_template, _raise

pytestmark = pytest.mark.django_db


#: `K3`'s fourth reading. ⚠ **IT EXISTS SO THE *MISSING* CASE CAN BE WRITTEN AT
#: ALL.** The three in wave H's fixture are all photo-required and all get
#: photographs in the happy path, so nothing in that template can ever produce
#: *a photograph was asked for and not taken* — the exact state `BR-WRK-040` is
#: about. `Voltage at socket` is required, wants a photograph, and is left alone
#: by every test that is not about it.
FOUR_READINGS = THREE_READINGS + [
    {
        "prompt": "Voltage at socket",
        "unit_of_measure": "V",
        "min": 110,
        "max": 125,
        "photo_required": True,
    }
]

#: A one-pixel PNG. Small on purpose: every test that is not ABOUT the ceiling
#: should be nowhere near it.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63382127070002b6010534a675aa0000000049454e44ae426082"
)


def _order(actor, tenant):
    tid = _published_template(actor, tenant, tasks=None)
    return _raise(actor, tenant, tid)["id"]


def _order_with_four_readings(actor, tenant):
    """An order whose template asks for FOUR readings — see `FOUR_READINGS`."""
    from apps.work import templates_svc

    tid = _published_template(actor, tenant)
    templates_svc.replace_collection(actor, tid, "readings", FOUR_READINGS)
    templates_svc.publish(actor, tid)
    return _raise(actor, tenant, tid)["id"]


def _two_orders(actor, tenant):
    """Two orders raised from ONE template.

    ⚠ Wave H's `_published_template` calls `_parts`, which creates parts with
    FIXED part numbers, so building a second template inside one test trips
    `uq_parts_tenant_part_no_ci`. Two orders off one template is what the
    cross-order cases actually need anyway — it makes the two jobs as alike as
    possible, so the only thing separating them is the one under test.
    """
    tid = _published_template(actor, tenant)
    return _raise(actor, tenant, tid)["id"], _raise(actor, tenant, tid)["id"]


def _satisfy_required_photos(actor, oid, *, skip_prompt=None):
    """Take every photograph the template asked for — READINGS **and** TASKS.

    ⚠ **TASKS CARRY `photo_required` TOO, AND FORGETTING THEM IS THE EASY
    MISTAKE.** `BR-WRK-040` says *a missing REQUIRED photograph stops the
    close*; it does not say "a missing reading photograph". Wave H's fixture
    template asks for photographs on several TASKS as well, so a test that
    satisfied only the readings and then asserted `can_close` would fail —
    correctly — and look like a bug in the rule rather than a gap in the setup.
    """
    for row in work_models.WorkOrderReading.objects.filter(
        work_order_id=oid, photo_required=True
    ):
        if skip_prompt and row.prompt == skip_prompt:
            continue
        _upload(actor, oid, f"r-{row.seq}", reading_id=row.id)
    for task in work_models.WorkOrderTask.objects.filter(
        work_order_id=oid, photo_required=True
    ):
        _upload(actor, oid, f"t-{task.seq}", task_id=str(task.id))


def _reading(oid, prompt):
    return work_models.WorkOrderReading.objects.get(work_order_id=oid, prompt=prompt)


def _upload(actor, oid, key, *, reading_id=None, payload=TINY_PNG, **extra):
    body = {"idempotency_key": key, "device": "Pixel 7a · D. Ortiz", **extra}
    if reading_id:
        body["reading_id"] = str(reading_id)
    return evidence.record_attachment(actor, oid, body, payload)


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-047 · BR-WRK-039 — out of range FLAGS, and is NEVER refused
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_039_an_out_of_range_reading_is_stored_and_flagged(brazos, dana):
    """TC-1 — 1,204 against a 0–999 bound is STORED, and `in_range` is False.

    The number is what the meter says. Refusing it would leave the true reading
    unrecorded over a bound somebody typed last year.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        row = _reading(oid, "Opening read, new meter")
        out = evidence.set_reading(dana, oid, row.id, {"value": "1204", "unit": "kWh"})
        # Compared as a NUMBER and not as a string: the stored column is 4 dp,
        # but what comes back in the same transaction is the Decimal that was
        # assigned, so "1204" and "1204.0000" are both correct spellings of it.
        assert Decimal(out["value"]) == Decimal("1204")
        assert out["in_range"] is False
        assert _reading(oid, "Opening read, new meter").value is not None


def test_tc2_039_an_out_of_range_reading_does_not_block_the_close(brazos, dana):
    """TC-2 — 1,204 is flagged and the job can STILL close.

    ⚠ This is the assertion that separates `BR-WRK-039` from `BR-WRK-040`. It
    is written with every required photograph present so that the ONLY thing
    that could block the close is the out-of-range value — and it does not.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        _satisfy_required_photos(dana, oid)
        row = _reading(oid, "Opening read, new meter")
        evidence.set_reading(dana, oid, row.id, {"value": "1204", "unit": "kWh"})

        ready = evidence.close_readiness(oid)
        assert ready["can_close"] is True, ready["blocking"]
        assert [f["kind"] for f in ready["flagged"]] == ["out_of_range"]
        # The two lists are SEPARATE and neither leaks into the other.
        assert ready["blocking"] == []


def test_tc3_039_in_range_is_none_when_the_template_set_no_bounds(brazos, dana):
    """TC-3 — None is not False.

    A reading nothing ever questioned must not render a red *out of range*.
    `New meter serial` has neither bound.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        row = _reading(oid, "New meter serial")
        out = evidence.set_reading(dana, oid, row.id, {"value": "8841", "unit": "serial"})
        assert out["in_range"] is None


def test_tc4_039_a_value_inside_the_bounds_is_in_range(brazos, dana):
    """TC-4 — the boundary itself is IN range, not out.

    999 against `max = 999` is the classic off-by-one, and a supervisor seeing
    a red flag on the exact bound the template allows would stop trusting the
    flag entirely.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        row = _reading(oid, "Opening read, new meter")
        assert evidence.set_reading(dana, oid, row.id, {"value": "999", "unit": "kWh"})[
            "in_range"
        ] is True


def test_tc5_039_hard_rule_3_a_reading_with_no_unit_is_refused(brazos, dana):
    """TC-5 · **hard rule 3** — a bare number is refused, not defaulted.

    ⚠ The tempting shortcut is to read the unit off the copied row. That is the
    *unit hidden in a sentence* wave H's model docstring warns about, and wave
    L posts this number into a meter's history where a wrong unit is a wrong
    bill.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        row = _reading(oid, "Opening read, new meter")
        with pytest.raises(errors.ValidationError):
            evidence.set_reading(dana, oid, row.id, {"value": "1204"})


def test_tc6_039_a_unit_that_disagrees_with_the_order_is_refused(brazos, dana):
    """TC-6 — `therm` against a job raised in `kWh` is refused.

    A mismatch means the phone and the order disagree about what was measured,
    which is not a thing to store and flag; it is a thing to refuse.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        row = _reading(oid, "Opening read, new meter")
        with pytest.raises(errors.ValidationError):
            evidence.set_reading(dana, oid, row.id, {"value": "1204", "unit": "therm"})


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-049 · BR-WRK-040 — the RULE column and the FILE column
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_049_the_rule_and_the_file_are_different_columns(brazos, dana):
    """TC-1 — `photo_required` is set by the TEMPLATE and untouched by uploading.

    Taking a photograph fills the FILE column and must not move the RULE
    column: *this reading wanted a photograph* stays true afterwards, which is
    what makes the record readable six months later.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        row = _reading(oid, "Opening read, new meter")
        assert row.photo_required is True
        assert row.photo_attachment_id is None

        att = _upload(dana, oid, "img-8842", reading_id=row.id)
        row.refresh_from_db()
        assert row.photo_required is True, "the RULE moved when only the FILE should have"
        assert str(row.photo_attachment_id) == att["id"]


def test_tc2_040_a_missing_required_photograph_warns_and_never_stops_the_close(brazos, dana):
    """TC-2 — **FLIPPED 2026-10-21: `BR-WRK-040` SUPERSEDED (PO: *"warn"*).**
    The job MAY close, and the warning still NAMES the reading.

    `Voltage at socket` is required, wants a photograph and has none. Until
    the ruling this case asserted `can_close is False`.
    """
    with tenant_ctx(brazos):
        oid = _order_with_four_readings(dana, brazos)
        ready = evidence.close_readiness(oid)
        assert ready["can_close"] is True
        assert ready["blocking"] == []
        prompts = [b["prompt"] for b in ready["missing_photos"]]
        assert "Voltage at socket" in prompts


def test_tc3_040_an_optional_missing_photograph_does_not_stop_the_close(brazos, dana):
    """TC-3 · **negative** — *never asked* is not *asked and not taken*.

    ⚠ This is the case a single nullable column could not express. `New meter
    serial` has `photo_required = False` and no photograph, and that is a job
    that closes.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        serial = _reading(oid, "New meter serial")
        assert serial.photo_required is False
        _satisfy_required_photos(dana, oid)

        ready = evidence.close_readiness(oid)
        assert ready["can_close"] is True, ready["blocking"]
        assert ready["missing_photos"] == []
        assert all(b["prompt"] != "New meter serial" for b in ready["missing_photos"])


def test_tc4_040_the_two_sentences_are_different_things(brazos, dana):
    """TC-4 — a photo gap and a flagged value at once, kept apart.

    Both conditions on ONE order: `Voltage at socket` has no photograph
    (warns — `BR-WRK-040` as superseded 2026-10-21), `Opening read` is 1,204
    (flags). Neither stops the close, and they still land in two lists: absent
    evidence and an unusual value are different questions for the office.
    """
    with tenant_ctx(brazos):
        oid = _order_with_four_readings(dana, brazos)
        opening = _reading(oid, "Opening read, new meter")
        _upload(dana, oid, "img-8842", reading_id=opening.id)
        evidence.set_reading(dana, oid, opening.id, {"value": "1204", "unit": "kWh"})

        ready = evidence.close_readiness(oid)
        assert ready["can_close"] is True
        assert ready["blocking"] == []
        assert {b["kind"] for b in ready["missing_photos"]} == {"missing_required_photo"}
        assert {f["kind"] for f in ready["flagged"]} == {"out_of_range"}
        # Neither list contains the other's item.
        assert not any(f["kind"] == "missing_required_photo" for f in ready["flagged"])
        assert not any(b["kind"] == "out_of_range" for b in ready["missing_photos"])


def test_tc5_049_the_footer_counts_readings_and_required_photographs(brazos, dana):
    """TC-5 — `Work-033`'s footer numbers come from the SERVER.

    *3 of 4 readings captured · 2 of 3 required photographs*. A screen that
    computed them itself would be a second opinion about whether a job closes.
    """
    with tenant_ctx(brazos):
        oid = _order_with_four_readings(dana, brazos)
        rows = list(
            work_models.WorkOrderReading.objects.filter(work_order_id=oid).order_by("seq")
        )
        for row in rows[:3]:
            evidence.set_reading(
                dana, oid, row.id, {"value": "10", "unit": row.unit_of_measure}
            )
        for row in [r for r in rows if r.photo_required][:2]:
            _upload(dana, oid, f"img-{row.seq}", reading_id=row.id)

        ready = evidence.close_readiness(oid)
        assert (ready["readings_captured"], ready["readings_total"]) == (3, 4)
        # ⚠ The photograph counters span READINGS **and** TASKS, because
        # `BR-WRK-040` does not distinguish them — a required photograph is a
        # required photograph. Three of the four readings want one, and the
        # template's tasks want more; two have been taken.
        taken, total = ready["required_photos_taken"], ready["required_photos_total"]
        assert taken == 2
        assert total >= 3


def test_tc6_049_a_photograph_cannot_belong_to_a_reading_on_another_order(brazos, dana):
    """TC-6 — the check a foreign key could not make.

    Syncing nine jobs and attaching job 4's photograph to job 5's reading is
    the mistake a phone actually makes. An FK would prove the reading EXISTS;
    only this proves it belongs to THIS ORDER.
    """
    with tenant_ctx(brazos):
        mine, theirs = _two_orders(dana, brazos)
        foreign = _reading(theirs, "Opening read, new meter")
        with pytest.raises(errors.NotFoundError):
            _upload(dana, mine, "img-x", reading_id=foreign.id)


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-048 · the kinds, the key, the ceiling, the link, the retention
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_048_a_photograph_lands_as_a_work_order_photo_document(brazos, dana):
    """TC-1 — one `stored_documents` row, kind `work_order_photo`, on the ORDER.

    The source is the work order and not the account: a photograph answers
    *what did the crew find on this visit*, and filing it under the customer
    would lose which visit the moment a second job ran at the same premises.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        att = _upload(dana, oid, "img-8841")
        row = work_models.WorkOrderAttachment.objects.get(id=att["id"])
        doc = StoredDocument.objects.get(id=row.document_id)
        assert doc.kind == document_models.KIND_WORK_ORDER_PHOTO
        # ⚠ THE SOURCE IS THE ATTACHMENT ROW, NOT THE ORDER, and `tenancy/0040`
        # is why: `uq_stored_documents_stored` allows ONE artefact per
        # (tenant, source_type, source_id, content_type), so under
        # `SOURCE_WORK_ORDER` the SECOND `image/jpeg` on one job is refused by
        # the database. Which job it belongs to is `work_order_attachments`'
        # entire purpose.
        assert doc.source_type == document_models.SOURCE_WORK_ORDER_ATTACHMENT
        assert str(doc.source_id) == att["id"]
        assert doc.byte_length == len(TINY_PNG)


def test_tc2_048_the_same_key_twice_writes_one_row(brazos, dana):
    """TC-2 · `BR-WRK-047` — a re-sync adds **ZERO** rows.

    A phone that loses signal halfway through nine photographs retries the
    whole batch. Without this the supervisor sees every photograph twice.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        first = _upload(dana, oid, "img-8841")
        second = _upload(dana, oid, "img-8841")
        assert first["id"] == second["id"]
        assert second["duplicate"] is True
        assert work_models.WorkOrderAttachment.objects.filter(work_order_id=oid).count() == 1
        # And no orphan document either — the early return happens BEFORE the
        # bytes are stored, so a retry does not fill the bucket. Counted through
        # the attachment rows, because a photograph's document hangs off its own
        # attachment id rather than off the order (`tenancy/0040`).
        assert StoredDocument.objects.filter(
            id__in=work_models.WorkOrderAttachment.objects.filter(
                work_order_id=oid
            ).values_list("document_id", flat=True)
        ).count() == 1


def test_tc3_048_an_unknown_kind_is_refused_by_the_database(brazos, dana):
    """TC-3 · **negative** — the CHECK constraint is real and `work_order_note`
    is not one of the 36.

    ⚠ Asserted through `document_store.store()` rather than a raw INSERT,
    because the whitelist a writer meets is the one that matters.
    """
    from apps.tenancy import document_store

    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        with pytest.raises(Exception):
            document_store.store(
                kind="work_order_note",
                source_type=document_models.SOURCE_WORK_ORDER,
                source_id=oid,
                content_type="image/png",
                display_name="x.png",
                payload=TINY_PNG,
                process="tests",
            )


def test_tc4_048_over_100kb_is_shrunk_never_refused_and_a_non_image_is_refused(brazos, dana):
    """TC-4 · ⚠ **SUPERSEDED 2026-10-04 (`DEF-WRK-9641`).** This asserted that a
    photograph over 100 KB is REFUSED naming both numbers. PO, verbatim: *"we
    have to ensure phone is copressing it - but you cannot reject the photo -
    that will drop the data"*. The ceiling is a storage target now: a real
    image over it is shrunk and stored (`test_def_wrk_9641_...`), and what is
    still refused is a file that is not an image at all — asserted here, with
    nothing stored."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        not_an_image = b"\x89PNG" + b"\x00" * (work_documents.MAX_PHOTO_BYTES + 1)
        with pytest.raises(errors.ValidationError) as caught:
            _upload(dana, oid, "img-huge", payload=not_an_image)
        assert caught.value.message_key == "work.attachment.not_an_image"
        assert work_models.WorkOrderAttachment.objects.filter(work_order_id=oid).count() == 0


def test_tc4b_048_the_ceiling_is_binary_kilobytes(brazos, dana):
    """TC-4b — 100 KB is `100 * 1024`, not 100,000.

    The handset's compressor works in binary kilobytes. A decimal ceiling would
    refuse a file the phone had correctly compressed to "100 KB" — on the last
    photograph of a nine-photograph day, with no way for the technician to act
    on the refusal.
    """
    assert work_documents.MAX_PHOTO_BYTES == 102400


def test_tc5_048_nothing_claims_seven_years_and_the_regime_is_twelve_months(brazos):
    """TC-5 · `BR-WRK-048` — the ruled regime, and the export that gates it.

    ⚠ **AMENDED 2026-09-05.** This TC used to assert that NOTHING anywhere
    named a retention period, which was right while `OQ-WRK-1496` was open. It
    closed on 2026-09-04: twelve months, then an export before deletion. The
    old assertion would now go red against a correctly built repo.
    """
    policy = work_documents.retention_policy()
    assert policy.months == 12
    assert policy.export_before_delete is True
    assert policy.held_while_matter_open is True
    # Seven years was the blueprint's assumption and is not the ruling.
    assert policy.months != 84


def test_tc6_048_another_tenant_cannot_fetch_this_photograph(brazos, lonestar, dana, erin):
    """TC-6 · **tenant isolation** — a 404, byte-identical to one that does not exist.

    ⚠ HR-1: existence must not leak. A 403 would confirm the photograph is
    real, which is the one thing a stranger must not learn from a refusal.

    ⚠ **AND THIS IS THE APPLICATION HALF ONLY.** SQLite has no row-level
    security, so this proves the QUERY is scoped and proves nothing about the
    policy. `tests/test_us_wrk_048_evidence_pg.py` is where RLS `FORCE` is
    evidence (hard-won law 14).
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        att = _upload(dana, oid, "img-8841")

    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            evidence.attachment_link(oid, att["id"])


def test_tc7_048_retention_is_ruled_and_prune_refuses_while_the_export_is_absent(brazos):
    """TC-7 — `retention_policy()` answers; `prune_due()` refuses.

    ⚠ **THIS TC USED TO BE A STUB ASSERTION** — that `retention_policy()`
    raised `NotImplementedError("OQ-WRK-1496")`. The question closed on
    2026-09-04, so it does not raise, and a stub naming a closed question would
    be a lie about the state of the repo.

    What DOES refuse is the pruning, and for the ruled reason rather than for
    want of a ruling: *an export that does not exist is not a retention
    policy*. The refusal names the ruling and says what to build first.
    """
    assert work_documents.retention_policy().may_prune is False
    with pytest.raises(work_documents.ExportPathMissing) as caught:
        work_documents.prune_due()
    message = str(caught.value)
    assert "12 months" in message
    assert "export" in message.lower()
    # It tells the next lane the ORDER of operations, not merely that it refused.
    assert "OQ-WRK-1496" in message


def test_tc7b_048_no_pruning_job_is_scheduled_for_work_kinds(brazos):
    """TC-7b — the job is NOT on the beat schedule, and that is deliberate.

    Asserted by name so that the day somebody schedules one, this goes red and
    asks whether the export was built first.
    """
    from apps.work import work_documents as wd

    assert not hasattr(wd, "run_prune_job")


def test_tc8_048_the_link_expires_in_four_hours(brazos, dana):
    """TC-8 · `US-WRK-048` — the link's life is FOUR HOURS and it is a bearer token.

    Whoever holds the URL reads this one photograph with no session and no
    further check until it expires. The TTL is the document store's own cap,
    which REFUSES a longer setting rather than clamping it.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        att = _upload(dana, oid, "img-8841")
        link = evidence.attachment_link(oid, att["id"])
        assert link["expires_in_seconds"] == 4 * 60 * 60
        assert link["url"]


def test_tc9_048_upload_ticket_states_the_ceiling_rather_than_presigning_s3(brazos, dana):
    """TC-9 · `BR-WRK-047a` — the ticket points at THIS application.

    The blueprint asked for a direct pre-signed PUT. At 100 KB that costs the
    content hash, the byte count, the tenant check, the audit row and the
    ceiling itself, and buys one fewer hop. The route still exists so the phone
    is told the ceiling by the SERVER rather than carrying it as a constant an
    old build can get wrong — which is the whole failure the PO described.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        ticket = evidence.upload_ticket(dana, oid, {})
        assert ticket["max_bytes"] == work_documents.MAX_PHOTO_BYTES
        assert str(oid) in ticket["upload_url"]
        assert "amazonaws" not in ticket["upload_url"]
        assert ticket["long_edge_px"] == 1600


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-036 · BR-WRK-046 — the signature, or the refusal, never both
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_036_a_signature_is_a_printed_name_and_an_image(brazos, dana):
    """TC-1 — *S. Miller* signs, and both halves are recorded with who and when."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        out = evidence.capture_signature(
            dana, oid, {"printed_name": "S. Miller"}, TINY_PNG
        )
        assert out["refused"] is False
        assert out["printed_name"] == "S. Miller"
        assert out["decline_reason"] is None
        row = work_models.WorkOrderSignature.objects.get(work_order_id=oid)
        assert row.image_id is not None
        assert row.captured_by_id == dana.id


def test_tc2_036_a_refusal_records_the_reason_and_the_door_hanger(brazos, dana):
    """TC-2 — r10 verbatim: *if refused, record decline reason and photo of door hanger*."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        hanger = _upload(dana, oid, "img-hanger")
        out = evidence.capture_signature(
            dana,
            oid,
            {
                "refused": True,
                "decline_reason": "Nobody home; hanger left on the door",
                "door_hanger_attachment_id": hanger["id"],
            },
        )
        assert out["refused"] is True
        assert out["printed_name"] is None
        assert out["door_hanger_attachment_id"] == hanger["id"]


def test_tc3_036_never_both(brazos, dana):
    """TC-3 · **negative** — a row carrying a name AND a decline reason is refused.

    It is not a record of anything that happened.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        hanger = _upload(dana, oid, "img-hanger")
        with pytest.raises(errors.ValidationError):
            evidence.capture_signature(
                dana,
                oid,
                {
                    "refused": True,
                    "decline_reason": "Declined",
                    "door_hanger_attachment_id": hanger["id"],
                    "printed_name": "S. Miller",
                },
            )


def test_tc4_036_a_refusal_without_a_door_hanger_is_refused(brazos, dana):
    """TC-4 · **negative** — the photograph is what makes the refusal evidence.

    Without it the row is an unevidenced claim that somebody declined, which is
    the thing a dispute turns on.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        with pytest.raises(errors.ValidationError):
            evidence.capture_signature(
                dana, oid, {"refused": True, "decline_reason": "Declined"}
            )


def test_tc5_036_a_signature_without_a_printed_name_is_refused(brazos, dana):
    """TC-5 · **negative** — a squiggle nobody can attribute.

    Six months later, in a dispute, the printed name is the only thing that
    says WHO made the mark.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        with pytest.raises(errors.ValidationError):
            evidence.capture_signature(dana, oid, {"printed_name": "  "}, TINY_PNG)


def test_tc6_036_one_signature_per_order(brazos, dana):
    """TC-6 · **negative** — a second signature would raise *which of these two
    is the customer's answer*, and there is no lawful reading of that."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        evidence.capture_signature(dana, oid, {"printed_name": "S. Miller"}, TINY_PNG)
        with pytest.raises(errors.ValidationError):
            evidence.capture_signature(dana, oid, {"printed_name": "A. Other"}, TINY_PNG)


def test_tc6b_036_no_signature_yet_is_not_a_refusal(brazos, dana):
    """TC-6b — `None` and *refused* are different states and render differently.

    A job nobody has asked about yet must not show as *the customer declined*.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        assert evidence.signature_for_order(oid) is None
