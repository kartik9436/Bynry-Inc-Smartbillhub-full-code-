# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-006 (TC-6 "Direct UPDATE of a published version's body →
#           Rejected — versions are append-only rows" · TC-7 isolation "Lone
#           Star Ridge template list → its own versions only; Brazos Bend's
#           invisible (RLS)")   Screens: S8 · S67
# Rules:    CLAUDE.md rule 1 (never touch a tenant table without app.tenant_id;
#           RLS FORCE is on) · rule 4 (a published body is evidence of what a
#           customer was sent — corrections are new rows, never rewrites) ·
#           BR-BIL-026 (append-only versions; publishing affects future renders
#           only) · BR-BIL-027 (a pinned version is audit-locked and can never
#           be deleted) · B2 §3 policy template · DB-1 · NFR-8 (a version is
#           retained forever) · NFR-10 (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""notifications 0006 — isolation and append-only law for the template store.

HUMAN-OWNED (RLS policies and migration ordering are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-15 under the PO ruling of
2026-08-09. Applies the SIGNED B2 §3 policy template from
`06-backend/db/rls_notification_templates_w3.sql` verbatim and invents no new
policy shape. Row required in 12-governance/09-human-review-ledger.md.

TWO DIFFERENT GUARANTEES, DELIBERATELY IN ONE MIGRATION BECAUSE NEITHER IS
SUFFICIENT ALONE
--------------------------------------------------------------------------
**RLS decides whose rows you may touch.** These tables hold no customer's name;
they hold the utility's own letters, its regulatory footer and the terms of its
contracts. A cross-tenant WRITE is the quiet one: publish a version into a
neighbour's registry and their next disconnect notice renders a body they never
wrote, on their letterhead, to their customers.

**The trigger decides what may change on a row you legitimately own.** US-NOT-006
TC-6 is stated as a negative — *"Direct UPDATE of a published version's body →
Rejected — versions are append-only rows; edits create drafts"* — and a service
check alone leaves `.update()`, a shell, a data migration and every future
endpoint outside it. `apps/billing/migrations/0002` makes the same call for
issued invoices and for the same reason (hard rule 4).

WHAT THE TRIGGER ALLOWS ON A NON-DRAFT ROW, AND WHY EACH
--------------------------------------------------------
`status`, `published_at`, `published_by`, `archived_at`, `updated_at`. Those are
the lifecycle stamps — draft → published → archived — and freezing them would
freeze publishing itself. Everything that decides WHAT THE DOCUMENT SAYS —
`body`, `subject`, `preheader`, `version`, `effective_from`, `template_id`,
`tenant_id` — is frozen the moment the row leaves draft.

A DRAFT may be edited freely: nothing has been sent from it, and nothing can pin
it (`template_service.resolve` returns published versions only).

A non-draft row can never be DELETEd. NFR-8's *"v2 retained FOREVER"* and
US-NOT-006 TC-5's audit-lock are the same guarantee from two sides, and T5-02
step 4's contrast case — deleting an unpinned DRAFT — is what stays possible.

Postgres only — sqlite has neither RLS nor the BR-AUD-002-style triggers, so the
unit tier proves the SHAPE (the `tenant` column every policy depends on, the
service-level refusals) and says so rather than implying coverage. The live
assertions belong to the G5 isolation suite.
"""

from pathlib import Path

from django.db import migrations

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_notification_templates_w3.sql"

#: ⚠ `%%` — a literal percent sign in a plpgsql format string must be DOUBLED in
#: a Python-side migration, because Django's schema editor runs the SQL through
#: parameter interpolation. `apps/billing/migrations/0002` writes it the same
#: way for the same reason.
APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION notifications_template_version_append_only() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status <> 'draft' THEN
      RAISE EXCEPTION 'BR-BIL-027 / NFR-8: template version %% is %% and can never be deleted; it is what every document pinned to it renders from. Archive is the ratified door, and publishing a NEW version is how a template changes',
        OLD.version, OLD.status;
    END IF;
    RETURN OLD;
  END IF;

  -- A draft has been sent to nobody and can be pinned by nothing.
  IF OLD.status = 'draft' THEN
    RETURN NEW;
  END IF;

  IF NEW.body           IS DISTINCT FROM OLD.body
  OR NEW.subject        IS DISTINCT FROM OLD.subject
  OR NEW.preheader      IS DISTINCT FROM OLD.preheader
  OR NEW.version        IS DISTINCT FROM OLD.version
  OR NEW.effective_from IS DISTINCT FROM OLD.effective_from
  OR NEW.template_id    IS DISTINCT FROM OLD.template_id
  OR NEW.tenant_id      IS DISTINCT FROM OLD.tenant_id THEN
    RAISE EXCEPTION 'BR-BIL-026 / hard rule 4: template version %% is %% — its body is append-only. What a customer was sent is frozen; an edit creates a NEW draft version (US-NOT-006 TC-6). Only the lifecycle stamps may still move',
      OLD.version, OLD.status;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ntv_append_only ON notification_template_versions;
CREATE TRIGGER trg_ntv_append_only
  BEFORE UPDATE OR DELETE ON notification_template_versions
  FOR EACH ROW EXECUTE FUNCTION notifications_template_version_append_only();
"""

DROP_APPEND_ONLY_SQL = """
DROP TRIGGER IF EXISTS trg_ntv_append_only ON notification_template_versions;
DROP FUNCTION IF EXISTS notifications_template_version_append_only();
"""


def apply_rls(apps_registry, schema_editor):
    """Apply the signed B2 §3 template, read from the .sql file verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in ("notification_templates", "notification_template_versions"):
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def apply_append_only(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(APPEND_ONLY_SQL)


def drop_append_only(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_APPEND_ONLY_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0005_w3_notification_templates"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RunPython(apply_append_only, drop_append_only),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-006@9a4f21c (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-02-templates-rendering.md — US-NOT-006 §1/§3/§5 — · 10-notifications/02-business-rules.md · 10-notifications/04-flows.md §2 · 08-qa/01-e2e/journeys/J22-template-life.md + T5-02-delete-pinned-template-version.md)
# generated: 2026-08-15 by story-coder (W3 notifications CONTENT lane — the template store)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST on a live Postgres cluster — with `apply_rls` neutered
#         to a no-op and the test database rebuilt, the G5 catalog sweep named
#         both tables as tenant-scoped with NO policy and this story's isolation
#         cases failed alongside it; with `apply_append_only` neutered, a direct
#         UPDATE of a PUBLISHED version's body succeeded and US-NOT-006 TC-6
#         failed with "Failed: DID NOT RAISE". Both restored: green. Verbatim
#         transcripts in the lane report · ruff✔ black✔
# exceptions: (1) TWO GUARANTEES IN ONE MIGRATION and neither substitutes for the
#         other: RLS decides WHOSE rows may be touched, the trigger decides WHAT
#         may change on one legitimately owned.
#         (2) THE LIFECYCLE STAMPS STAY MUTABLE on a non-draft row (`status`,
#         `published_at`, `published_by`, `archived_at`, `updated_at`) — freezing
#         them would freeze publishing itself. Everything that decides what the
#         DOCUMENT SAYS is frozen.
#         (3) POSTGRES ONLY. sqlite has neither RLS nor triggers; the unit tier
#         proves the service-level refusals and the G5 suite proves the database
#         ones. Stated rather than implied.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
