# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-048 TC-6 (tenant isolation — Lone Star cannot fetch a Brazos
#           Bend photograph) · US-WRK-036 (the signature shape, enforced by the
#           database rather than by a validator) · US-WRK-048 TC-2 (the same key
#           twice writes one row — under a real race)
# Rules:    BR-WRK-046 · BR-WRK-047 · CLAUDE.md hard rule 1 (RLS FORCE) ·
#           hard rule 4's SHAPE (a correction is a new row) · hard-won law 14
#           (the suite runs on SQLite, which has neither PL/pgSQL nor an
#           aborted-transaction state, so all four proofs below pass by vacuum
#           there)
# Tests:    this file — skipped on SQLite BY DESIGN, and the skip is the point
# ───────────────────────────────────────────────────────
"""US-WRK-048 · US-WRK-036 — the four guarantees SQLite cannot check.

Run it with a real database:

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
        DATABASE_URL=postgres://sbh_gate_iso:sbh_gate_iso@localhost:5432/sbh_rlsrole \\
        pytest tests/test_us_wrk_048_evidence_pg.py --reuse-db

WHY THIS FILE EXISTS
────────────────────────────────────────────────────────────────────────────
Four things wave K claims are true, and the suite's own database can prove none
of them:

1. **RLS `FORCE` on both evidence tables.** SQLite has no row-level security at
   all, so `test_tc6_048_another_tenant_cannot_fetch_this_photograph` in the
   unit file proves only that the QUERY is scoped. It says nothing about a
   `raw()`, a `.update()`, a migration or a person at a psql prompt.
   ⚠ **AND A RUN AS THE ORDINARY `smartbillhub` ROLE PROVES NOTHING EITHER**:
   it holds SUPERUSER, and PostgreSQL exempts a superuser from row security
   unconditionally, `FORCE` included (`DEF-2717`). The `rls` fixture refuses
   rather than skips when handed a bypassing role — `assert_is_a_real_proof()`
   — which is what makes a green here mean something.

2. **The append-only trigger.** `work/0016` puts `BEFORE UPDATE OR DELETE` on
   both tables so that *evidence is never edited* holds for the ORM and for
   everything that is not the ORM. SQLite runs no PL/pgSQL, so on the suite's
   own database that trigger does not exist and every assertion about it is
   green over nothing.

3. **The savepoint in `record_attachment`.** Two syncs racing on one
   idempotency key hit the unique constraint; the loser catches it and re-reads.
   ⚠ **On PostgreSQL a failed statement poisons the whole transaction** — without
   the nested `transaction.atomic()` the re-read raises
   `InFailedSqlTransaction` and the sync loses everything after it. **SQLite has
   no aborted-transaction state, so the broken version passes the entire suite,
   green, on every machine** (hard-won law 14, found independently by two lanes
   on 2026-08-29).

4. **The signature shape CHECK.** `ck_work_order_signatures_shape` is what makes
   *never both* a guarantee rather than a validator somebody can route around.
"""

from __future__ import annotations

import pytest
from django.db import DatabaseError, connection, transaction

from apps.tenancy.document_models import StoredDocument
from apps.work import evidence
from apps.work import models as work_models
from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_047_049_evidence import TINY_PNG, _order, _reading, _upload

pytestmark = [pytest.mark.django_db, requires_postgres]


def _any_document_id(order_id):
    """Any stored document belonging to this job, via its attachment row.

    ⚠ A photograph's `source_id` is its own `work_order_attachments.id` and NOT
    the order (`tenancy/0040`), so a document cannot be found by asking for the
    order. The attachment row is what says which job it belongs to.
    """
    row = work_models.WorkOrderAttachment.objects.filter(work_order_id=order_id).first()
    return row.document_id if row else None


# ══════════════════════════════════════════════════════════════════════════
# 1 · RLS — and the proof is read out of pg_class, not out of the migration
# ══════════════════════════════════════════════════════════════════════════
def test_rls_is_enabled_and_forced_on_both_evidence_tables():
    """`relrowsecurity` AND `relforcerowsecurity`, read from the catalogue.

    ⚠ **BOTH FLAGS, AND `ENABLE` ALONE WOULD BE A HOLE.** `ENABLE` exempts the
    table's OWNER, and the application's migration role owns every table in this
    schema — so a table with `ENABLE` and not `FORCE` has a policy that the
    application itself walks straight past. B2 §3 requires both.

    Read from `pg_class` rather than trusting that `work/0017` ran, because a
    migration that ran is not a policy that exists (hard-won law 1).
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname IN ('work_order_attachments','work_order_signatures') "
            "ORDER BY relname"
        )
        rows = cursor.fetchall()
    assert rows == [
        ("work_order_attachments", True, True),
        ("work_order_signatures", True, True),
    ], rows


def test_tc6_048_a_photograph_row_is_invisible_across_the_tenant_boundary(
    rls, brazos, lonestar, dana
):
    """TC-6 — Brazos Bend's attachment rows vanish under Lone Star Ridge.

    ⚠ **THIS IS THE ONE THAT MATTERS MOST IN WAVE K, AND NOT BECAUSE OF THE
    ROW.** `work_order_attachments.document_id` is what
    `document_store.download_url()` mints a four-hour BEARER link from — a URL
    that reads the image with no session and no further check. So a policy
    failure here does not leak a filename; it hands a stranger a photograph
    taken inside somebody's home.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        att = _upload(dana, oid, "img-8841")

    assert_rls_scoped(
        rls,
        "work_order_attachments",
        owner=brazos,
        intruder=lonestar,
        owner_ids={att["id"]},
    )


def test_a_signature_row_is_invisible_across_the_tenant_boundary(
    rls, brazos, lonestar, dana
):
    """The same, for the table holding a named person's signature image.

    A specimen signature with an identity attached is the worst single row in
    this wave to leak.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        evidence.capture_signature(dana, oid, {"printed_name": "S. Miller"}, TINY_PNG)
        sig = work_models.WorkOrderSignature.objects.get(work_order_id=oid)

    assert_rls_scoped(
        rls,
        "work_order_signatures",
        owner=brazos,
        intruder=lonestar,
        owner_ids={str(sig.id)},
    )


def test_both_tables_are_denied_with_no_tenant_context_at_all(rls):
    """Deny by default — an unset `app.tenant_id` sees nothing, and does not error.

    The `NULLIF(current_setting('app.tenant_id', true), '')::uuid` form
    (`DEF-639`): deny-by-default WITHOUT erroring on an unset GUC, which is what
    keeps a fresh database buildable (`OQ-354`/`DEF-622`).
    """
    assert_denied_without_context(rls, "work_order_attachments", "work_order_signatures")


# ══════════════════════════════════════════════════════════════════════════
# 2 · The append-only trigger — evidence is never edited
# ══════════════════════════════════════════════════════════════════════════
def test_an_attachment_row_cannot_be_updated(brazos, dana):
    """`BEFORE UPDATE` refuses, and the message says what to do instead.

    ⚠ **THE ORM IS NOT WHERE THIS IS ENFORCED, WHICH IS THE POINT.** Asserted
    through `.update()`, which goes straight to SQL and past any `save()`
    override a model could carry.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        att = _upload(dana, oid, "img-8841")
        with pytest.raises(DatabaseError) as caught:
            with transaction.atomic():
                work_models.WorkOrderAttachment.objects.filter(id=att["id"]).update(
                    device="somebody else's phone"
                )
    assert "append-only" in str(caught.value)


def test_an_attachment_row_cannot_be_deleted(brazos, dana):
    """`BEFORE DELETE` refuses too. A photograph is not withdrawn, it is superseded."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        att = _upload(dana, oid, "img-8841")
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                work_models.WorkOrderAttachment.objects.filter(id=att["id"]).delete()


def test_a_signature_row_cannot_be_updated(brazos, dana):
    """A refusal cannot be quietly turned into a signature afterwards.

    This is the one an unhappy crew would want most, and it is why the
    guarantee is a trigger rather than a code review.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        hanger = _upload(dana, oid, "img-hanger")
        evidence.capture_signature(
            dana,
            oid,
            {
                "refused": True,
                "decline_reason": "Nobody home",
                "door_hanger_attachment_id": hanger["id"],
            },
        )
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                work_models.WorkOrderSignature.objects.filter(work_order_id=oid).update(
                    refused=False
                )


def test_the_correction_path_is_a_new_row_and_it_works(brazos, dana):
    """⚠ **APPEND-ONLY IS NOT A DEAD END, AND THIS PROVES THE WAY OUT EXISTS.**

    A technician who photographed the wrong meter takes another photograph. It
    is a second row with a later `taken_at`, and the reading points at the new
    one. The mistake stays in the record, which is the point — and a supervisor
    can see that a correction happened at all, which is exactly what an in-place
    edit would have destroyed.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        row = _reading(oid, "Opening read, new meter")
        first = _upload(dana, oid, "img-wrong", reading_id=row.id)
        second = _upload(dana, oid, "img-right", reading_id=row.id)

        row.refresh_from_db()
        assert str(row.photo_attachment_id) == second["id"]
        # Both rows survive. The wrong one is still there to be found.
        assert work_models.WorkOrderAttachment.objects.filter(work_order_id=oid).count() == 2
        assert first["id"] != second["id"]


# ══════════════════════════════════════════════════════════════════════════
# 3 · The savepoint — one refused row does not take the batch down
# ══════════════════════════════════════════════════════════════════════════
def test_law14_a_duplicate_key_does_not_poison_the_surrounding_transaction(
    brazos, dana
):
    """Hard-won law 14 — the proof that cannot be made on SQLite.

    ⚠ **WHAT THIS IS ACTUALLY TESTING.** The unique constraint fires inside
    `record_attachment`; it is caught and the row re-read. On PostgreSQL that
    re-read is the statement that would raise `InFailedSqlTransaction` if the
    insert had not been wrapped in its own SAVEPOINT — and then everything after
    it in the sync is lost at COMMIT.

    So the assertion is deliberately about **what happens NEXT**: after the
    duplicate, a THIRD, entirely different photograph must still land. A test
    that only asserted *the duplicate returned the same row* would pass on the
    broken version too, because the exception is caught either way.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        with transaction.atomic():
            first = _upload(dana, oid, "img-8841")
            duplicate = _upload(dana, oid, "img-8841")
            assert duplicate["id"] == first["id"]
            # THE ASSERTION THAT MATTERS: the transaction is still usable.
            third = _upload(dana, oid, "img-8842")
            assert third["id"] != first["id"]

        assert work_models.WorkOrderAttachment.objects.filter(work_order_id=oid).count() == 2


def test_law14_a_whole_offline_day_survives_one_duplicate_in_the_middle(brazos, dana):
    """The real shape: nine photographs, one of them a retry, all inside one sync.

    This is the case the savepoint exists for. Without it the batch is lost from
    the duplicate onwards, and the technician's afternoon is gone with it.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        with transaction.atomic():
            for i in range(4):
                _upload(dana, oid, f"img-{i}")
            _upload(dana, oid, "img-2")  # the retry, mid-batch
            for i in range(4, 9):
                _upload(dana, oid, f"img-{i}")
        assert work_models.WorkOrderAttachment.objects.filter(work_order_id=oid).count() == 9


# ══════════════════════════════════════════════════════════════════════════
# 4 · The signature shape — the CHECK is the rule
# ══════════════════════════════════════════════════════════════════════════
def test_the_database_refuses_a_signature_that_is_both(brazos, dana):
    """`ck_work_order_signatures_shape` — asserted past the validator.

    ⚠ **WRITTEN AS A RAW INSERT ON PURPOSE.** `evidence.capture_signature`
    already refuses this and its refusal is tested in the unit file. What is
    tested HERE is that the guarantee survives a caller who does not go through
    that function — a data fix, a migration, an import. The validator is the
    message; the constraint is the guarantee (hard-won law 1).
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        att = _upload(dana, oid, "img-hanger")
        doc_id = _any_document_id(oid)
        with pytest.raises(DatabaseError) as caught:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO work_order_signatures "
                    "(id, tenant_id, work_order_id, refused, printed_name, "
                    " image_document_id, decline_reason, door_hanger_attachment_id, "
                    " signed_at, created_at) "
                    "VALUES (gen_random_uuid(), %s, %s, true, 'S. Miller', %s, "
                    "'Declined', %s, now(), now())",
                    [str(brazos.id), str(oid), str(doc_id), att["id"]],
                )
    assert "ck_work_order_signatures_shape" in str(caught.value)


def test_the_database_refuses_a_second_signature_on_one_order(brazos, dana):
    """`uq_work_order_signatures_order` — one answer per job, past the validator too."""
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        evidence.capture_signature(dana, oid, {"printed_name": "S. Miller"}, TINY_PNG)
        doc_id = _any_document_id(oid)
        with pytest.raises(DatabaseError):
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO work_order_signatures "
                    "(id, tenant_id, work_order_id, refused, printed_name, "
                    " image_document_id, signed_at, created_at) "
                    "VALUES (gen_random_uuid(), %s, %s, false, 'A. Other', %s, now(), now())",
                    [str(brazos.id), str(oid), str(doc_id)],
                )


def test_the_database_refuses_a_photograph_owned_by_a_reading_and_a_task(brazos, dana):
    """`ck_work_order_attachments_one_owner` — one file is evidence of one row.

    A row claiming both would make `Work-033`'s count wrong in two places at
    once.
    """
    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        reading = _reading(oid, "Opening read, new meter")
        task = work_models.WorkOrderTask.objects.filter(work_order_id=oid).first()
        # Seeded so there IS a document to point at. Without it the INSERT below
        # fails on a NOT NULL violation instead of on the constraint under test —
        # which still raises `DatabaseError`, so the test would have gone green
        # for the wrong reason had it only asserted "something was refused".
        # Asserting the constraint BY NAME is what caught it.
        _upload(dana, oid, "img-seed")
        doc_id = _any_document_id(oid)
        assert doc_id is not None
        with pytest.raises(DatabaseError) as caught:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO work_order_attachments "
                    "(id, tenant_id, work_order_id, document_id, kind, taken_at, "
                    " device, reading_id, task_id, idempotency_key, created_at) "
                    "VALUES (gen_random_uuid(), %s, %s, %s, 'work_order_photo', now(), "
                    "'', %s, %s, 'both', now())",
                    [str(brazos.id), str(oid), str(doc_id), str(reading.id), str(task.id)],
                )
    assert "one_owner" in str(caught.value)
