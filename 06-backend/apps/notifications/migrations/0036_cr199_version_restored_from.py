# ── Trace ──────────────────────────────────────────────
# Change:   CR-199-BRC10 S3 — *Make live again* (templates redesign, PO 2026-10-29)
# Rules:    BR-BIL-026 (an edit is a NEW version; history is append-only) ·
#           CLAUDE.md hard rule 4 (a published body is evidence and is never
#           rewritten) · OQ-1340 (audit_log is pruned, so a fact that must
#           outlive it lives on the row)
# Tests:    06-backend/tests/test_cr199_template_variants.py
# ───────────────────────────────────────────────────────
"""notifications 0036 — which version a restored version was copied from.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-29 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.

ONE nullable column on `notification_template_versions`, and a trigger that
makes it WRITE-ONCE. No existing row changes: every version written before this
was typed by somebody, so NULL is the true value for all of them.

WHY A SEPARATE TRIGGER RATHER THAN AN EDIT TO `0006`'s FUNCTION — `0017`'s
reasoning, unchanged: `0006` is the append-only guarantee every published body
leans on, and re-issuing its whole function to add one column would put the
most-relied-on trigger in this module into a diff about something else. This one
refuses exactly one thing — changing `restored_from_version` once it is set or
once the row has left draft — and nothing `0006` would have allowed.
"""

from django.db import migrations, models

WRITE_ONCE_SQL = """
CREATE OR REPLACE FUNCTION notifications_template_version_restored_from_frozen() RETURNS trigger AS $$
BEGIN
  IF NEW.restored_from_version IS DISTINCT FROM OLD.restored_from_version
     AND (OLD.restored_from_version IS NOT NULL OR OLD.status <> 'draft') THEN
    RAISE EXCEPTION 'CR-199 / hard rule 4: template version %% records which version it restored and that fact is write-once',
      OLD.version;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ntv_restored_from_frozen ON notification_template_versions;
CREATE TRIGGER trg_ntv_restored_from_frozen
  BEFORE UPDATE ON notification_template_versions
  FOR EACH ROW EXECUTE FUNCTION notifications_template_version_restored_from_frozen();
"""

DROP_WRITE_ONCE_SQL = """
DROP TRIGGER IF EXISTS trg_ntv_restored_from_frozen ON notification_template_versions;
DROP FUNCTION IF EXISTS notifications_template_version_restored_from_frozen();
"""


def apply_trigger(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(WRITE_ONCE_SQL)


def drop_trigger(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_WRITE_ONCE_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0035_rls_cr198_provider_status_events"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationtemplateversion",
            name="restored_from_version",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.RunPython(apply_trigger, drop_trigger),
    ]
