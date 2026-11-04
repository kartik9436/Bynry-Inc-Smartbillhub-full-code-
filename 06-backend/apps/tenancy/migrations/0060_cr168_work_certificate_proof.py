# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — image 33's PROOF column (a
#           technician's certificate can be held as a file); the server gap
#           lane CREWS reported (CR §19).
# Rules:    CLAUDE.md 🔒 migration ordering
# Tests:    06-backend/tests/test_cr168_srv4_crews.py
# ───────────────────────────────────────────────────────
"""tenancy 0060 — a technician's certificate can be held as a proof document.

Two values and nothing else, `0059`'s shape exactly: the kind
`work_certificate_proof` joins `ck_stored_documents_kind` (49 → 50) and the
source `work_certificate_proof` joins `ck_stored_documents_source` (13 → 14) —
each upload its own source, because a renewal stores a second scan of the same
certificate and `uq_stored_documents_filed` allows one artefact per (source,
content type). No column moves: `technician_certifications.evidence_document_id`
has existed since wave F and nothing ever wrote it.

The rollback REFUSES with a count while any row carries either new value — a
narrower CHECK over such rows would strand them, and `0026`'s write-once trigger
means they could be neither edited nor deleted to make room.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-04 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""

from importlib import import_module

from django.db import migrations, models

_previous = import_module("apps.tenancy.migrations.0059_cr168_work_template_help_document")

NEW_KINDS = ("work_certificate_proof",)
NEW_SOURCES = ("work_certificate_proof",)

KINDS_BEFORE = _previous.KINDS_AFTER
SOURCES_BEFORE = _previous.SOURCES_AFTER
KINDS_AFTER = (*KINDS_BEFORE, *NEW_KINDS)
SOURCES_AFTER = (*SOURCES_BEFORE, *NEW_SOURCES)


def refuse_rollback_over_live_rows(apps, schema_editor):
    StoredDocument = apps.get_model("tenancy", "StoredDocument")
    stuck = StoredDocument.objects.filter(
        models.Q(kind__in=NEW_KINDS) | models.Q(source_type__in=NEW_SOURCES)
    ).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0060: {stuck} stored_documents row(s) already "
            "carry kind or source work_certificate_proof. The narrower constraints would "
            "leave rows the CHECK forbids, and tenancy/0026's write-once trigger means they "
            "could be neither edited nor deleted to make room. Stay on this migration."
        )


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0059_cr168_work_template_help_document")]

    # ⚠ THE REFUSAL IS THE LAST OPERATION, SO IT IS THE FIRST TO RUN ON THE WAY
    # BACK (`DEF-TEN-9655`). Django reverses operations in reverse order; placed
    # first, as in `0020`–`0059`, it ran AFTER the narrower CHECK had already
    # been restored, and the rollback failed on a raw IntegrityError instead of
    # this counted sentence. Proved with a live proof row on PostgreSQL 16.
    operations = [
        migrations.RemoveConstraint(model_name="storeddocument", name="ck_stored_documents_kind"),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=KINDS_AFTER), name="ck_stored_documents_kind"
            ),
        ),
        migrations.RemoveConstraint(model_name="storeddocument", name="ck_stored_documents_source"),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(source_type__in=SOURCES_AFTER), name="ck_stored_documents_source"
            ),
        ),
        migrations.RunPython(migrations.RunPython.noop, refuse_rollback_over_live_rows),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §19 (lane CREWS's server needs: image 33's PROOF) · §20.3
# generated: 2026-10-04 by CR-168 round 5 lane SRV-4
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 migration ordering → review-ledger row)
# gates: makemigrations --check · migrate up → down → up on PostgreSQL 16 (sbh_wsrv4)
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
