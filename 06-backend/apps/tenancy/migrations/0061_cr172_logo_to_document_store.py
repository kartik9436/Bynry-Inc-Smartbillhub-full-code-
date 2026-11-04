# ── Trace ──────────────────────────────────────────────
# Change:   CR-172-BRC10 — the utility logo moves from `tenants.logo_bytes` into
#           the common S3 document store (PO 2026-10-05).
# Rules:    CLAUDE.md 🔒 migration ordering · hard-won law 14 · NFR-33 ·
#           BR-TEN-019
# Tests:    06-backend/tests/test_cr172_logo_document_store.py (the move,
#           re-run, storage down, mismatch, and the PostgreSQL run)
# ───────────────────────────────────────────────────────
"""tenancy 0061 — the logo becomes a stored document, and every existing logo moves.

Two halves.

**Schema** — `0060`'s shape exactly: the kind `tenant_logo` joins
`ck_stored_documents_kind` (50 → 51) and the source `tenant_logo` joins
`ck_stored_documents_source` (14 → 15). No column is added or dropped:
`tenants.logo_file_id` already existed to hold *"object-store ref (BR-TEN-019)"*.

**Data** — `services.move_logos_to_store()`, the SAME function
`manage.py move_logos_to_store` runs, so there is one implementation of the move
and it calls the common store (`document_store.store()`/`fetch()`), never a
logo-only path (PO: *"use common compotent to save logo - dont create seperate
code"*). For each utility with bytes on its row, under that utility's own tenant
context and in its own savepoint: store the bytes (and an SVG's PNG rendering),
read them back, accept the copy ONLY when its sha256 equals the row's bytes,
then repoint `logo_file_id` and EMPTY `logo_bytes`. **The column is emptied,
not dropped** — it is dropped in a LATER release, once every environment has
run this and nothing reads it.

⚠ **IT DOES NOT FAIL WHEN STORAGE IS DOWN.** A utility whose copy cannot be
stored or does not match keeps its row exactly as it was — bytes and `sha256:`
reference — and its logo goes on drawing from the row. The count is printed;
`manage.py move_logos_to_store` finishes the job once storage is back. Failing
the migration instead would hold every other schema change in the release
hostage to an object store, which is the opposite of what a logo deserves.

⚠ **IT CALLS LIVE CODE, AND THAT IS SAFE HERE FOR A STATED REASON.** A data
migration normally uses historical models. This one deliberately runs the live
store so the move cannot drift from the upload. On a fresh database there are
no logos, so the loop never reaches the store; on a live database this
migration runs against the schema this release ships. If `stored_documents` is
ever reshaped by a later migration, a database still BEHIND this one must be
migrated through this release first — which is how releases are applied anyway.

**Rollback is a COMMAND, then the previous build — not a reverse migration.**
`manage.py move_logos_to_store --back` copies each moved logo's bytes BACK onto
its row from the store (checked by sha256) and restores its `sha256:`
reference, so the previous build reads every logo again; the schema stays,
because a wider CHECK costs the previous build nothing. Reversing THIS
migration is refused while any `tenant_logo` row exists (`0060`'s refusal, the
last operation so it runs first on the way back — `DEF-TEN-9655`): the
narrower CHECK would strand write-once rows, and a copy-back done inside the
reverse would be rolled back with the refusal's transaction. Stored objects
stay in the bucket (write-once); they cost kilobytes.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-05 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""

from importlib import import_module

from django.db import migrations, models

_previous = import_module("apps.tenancy.migrations.0060_cr168_work_certificate_proof")

NEW_KINDS = ("tenant_logo",)
NEW_SOURCES = ("tenant_logo",)

KINDS_BEFORE = _previous.KINDS_AFTER
SOURCES_BEFORE = _previous.SOURCES_AFTER
KINDS_AFTER = (*KINDS_BEFORE, *NEW_KINDS)
SOURCES_AFTER = (*SOURCES_BEFORE, *NEW_SOURCES)


def move_logos(apps, schema_editor):
    from apps.tenancy import services

    report = services.move_logos_to_store()
    if any(report.values()):
        print(
            f"\n    logos: {report['moved']} moved to the document store, "
            f"{report['already']} already there, {report['left']} left on the row "
            "(run `manage.py move_logos_to_store` once storage is available)"
            if report["left"]
            else f"\n    logos: {report['moved']} moved to the document store, "
            f"{report['already']} already there"
        )


def refuse_rollback_over_live_rows(apps, schema_editor):
    StoredDocument = apps.get_model("tenancy", "StoredDocument")
    stuck = StoredDocument.objects.filter(
        models.Q(kind__in=NEW_KINDS) | models.Q(source_type__in=NEW_SOURCES)
    ).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0061: {stuck} stored_documents row(s) carry kind "
            "or source tenant_logo, and the narrower CHECK would strand these write-once rows. "
            "To go back to the previous build, run `manage.py move_logos_to_store --back` "
            "(it puts every logo's bytes back on its row) and deploy the previous code on "
            "THIS schema."
        )


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0060_cr168_work_certificate_proof")]

    # One savepoint per utility inside `move_logos_to_store` (hard-won law 14);
    # the migration's own transaction holds the constraint change and the move.
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
        migrations.RunPython(move_logos, migrations.RunPython.noop),
        # ⚠ THE REFUSAL IS THE LAST OPERATION, SO IT IS THE FIRST TO RUN ON THE
        # WAY BACK — before the narrower CHECK is restored (`DEF-TEN-9655`).
        migrations.RunPython(migrations.RunPython.noop, refuse_rollback_over_live_rows),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-172-BRC10 · decision log 2026-10-05
# generated: 2026-10-05 by lane LOGO
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 migration ordering → review-ledger row)
# gates: makemigrations --check · migrate up → down → up on PostgreSQL 16 (sbh_wlogo) with live logos
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
