# ── Trace ──────────────────────────────────────────────
# Change:   CR-199-BRC10 · lane TPL-SRV-EMAIL · task S4 (rich email wording)
# Ruling:   PO 2026-10-29, ruling 2A — a simple rich editor (bold, link,
#           button, list) with a SAFE preview
# Rules:    BR-BIL-026 / CLAUDE.md hard rule 4 (a version that left draft is
#           evidence of what was sent — its layout is frozen with its words) ·
#           rule 1 (no policy change: the table's RLS is untouched)
# Tests:    06-backend/tests/test_cr199_rich_email_pg.py
# ───────────────────────────────────────────────────────
"""notifications 0037 — **a template version says whether its email is rich.**

HUMAN-OWNED (migration ordering and an append-only trigger are CLAUDE.md 🔒
paths). HUMAN-REVIEW-PENDING — AI-authored 2026-10-29 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

One column, `body_format`, `plain` | `rich`, NOT NULL DEFAULT `plain`. Every
existing version reads `plain` — which is exactly how each was sent — so no
row's meaning changes.

**THE SAME LAYOUT A CUSTOMER WAS SENT IS FROZEN WITH THE WORDS.** `0006`'s
trigger freezes `body`, `subject` and the rest of a non-draft version by NAME
(a deny list), so a new column would be editable on a published row unless it
is named too. A rich body re-read as plain prints its markup as characters, so
the format is as much the document as the words. Following `0017`'s precedent
this is a SECOND trigger rather than an edit to `0006`'s function, which stays
byte-identical: each guard can be read and reversed on its own.

**Rollback:** `migrate notifications 0036` — the trigger, the CHECK and the
column go. Roll the code back with it. A rich version saved meanwhile then
reads as plain text with its markup visible; nothing is lost from the body.

Postgres only for the trigger; sqlite has none (tests carry `requires_postgres`).
"""

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

#: `%` single — `PostgresOnlySQL` performs no %-substitution (`0017`'s note).
FORMAT_FROZEN_SQL = """
CREATE OR REPLACE FUNCTION notifications_template_version_format_frozen() RETURNS trigger AS $$
BEGIN
  IF OLD.status <> 'draft' AND NEW.body_format IS DISTINCT FROM OLD.body_format THEN
    RAISE EXCEPTION 'BR-BIL-026 / hard rule 4: template version % is % — its email format is frozen with its body. An edit creates a NEW draft version.',
      OLD.version, OLD.status;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ntv_format_frozen ON notification_template_versions;
CREATE TRIGGER trg_ntv_format_frozen
  BEFORE UPDATE ON notification_template_versions
  FOR EACH ROW EXECUTE FUNCTION notifications_template_version_format_frozen();
"""

REVERSE_FORMAT_FROZEN_SQL = """
DROP TRIGGER IF EXISTS trg_ntv_format_frozen ON notification_template_versions;
DROP FUNCTION IF EXISTS notifications_template_version_format_frozen();
"""


class Migration(migrations.Migration):
    dependencies = [
        # 🔒 ORDERING — named explicitly; the tip's newest notifications migration (lane B's `0036`).
        ("notifications", "0036_cr199_version_restored_from"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationtemplateversion",
            name="body_format",
            field=models.TextField(default="plain"),
        ),
        migrations.AddConstraint(
            model_name="notificationtemplateversion",
            constraint=models.CheckConstraint(
                condition=models.Q(body_format__in=("plain", "rich")),
                name="ck_ntv_body_format",
            ),
        ),
        PostgresOnlySQL(sql=FORMAT_FROZEN_SQL, reverse_sql=REVERSE_FORMAT_FROZEN_SQL),
    ]
