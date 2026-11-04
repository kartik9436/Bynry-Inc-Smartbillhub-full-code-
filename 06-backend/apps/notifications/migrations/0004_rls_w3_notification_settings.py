# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-004 (TC-7 isolation — "Lone Star Ridge dispatch home: its own
#           batch size (500 seeded), its own provider status; Brazos Bend config
#           invisible (RLS)")   Screens: S8
# Rules:    CLAUDE.md rule 1 (never touch a tenant table without app.tenant_id;
#           RLS FORCE is on) · B2 §3 policy template · DB-1 · BR-NOT-009 (the
#           quiet-hours window this table stores is a compliance control) ·
#           NFR-10 (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""notifications 0004 — tenant isolation for `notification_settings`.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-15 under the PO ruling of 2026-08-09. Applies the SIGNED
B2 §3 policy template from `06-backend/db/rls_notifications_settings_w3.sql`
verbatim and invents no new policy shape. Row in
12-governance/09-human-review-ledger.md.

THE INTERESTING HALF OF THIS POLICY IS `WITH CHECK`, NOT `USING`. Unlike
`outbound_messages` — which holds one customer's name and address per row — this
table holds no personal data whatsoever. What it holds is CONTROL: the batch
size, and the hours of the day a utility is permitted to email and text its
customers. A cross-tenant read discloses two numbers. A cross-tenant WRITE moves
another utility's quiet-hours window, and the visible consequence is a 23:00
late-payment text to their customers, from their address, with nothing in their
own audit trail to explain it (T5-23's incident, caused from outside).

Deny-by-default, not filter-by-default: with `app.tenant_id` unset the template's
`::uuid` cast of `''` raises and NO row is visible. FORCE applies the policy to
the table owner too — without it, the application role (a superuser in dev/CI)
would be exempt and the guarantee would exist only in this docstring.

PROVED RED BEFORE GREEN. With `apply_rls` neutered to a no-op and the test
database rebuilt, the G5 catalog sweep names this table; see the trailer for the
verbatim failure.

Postgres only — SQLite has no RLS, so the unit tier proves SHAPE (the `tenant`
column every policy depends on) and says so rather than implying coverage.
"""

from pathlib import Path

from django.db import migrations

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_notifications_settings_w3.sql"


def apply_rls(apps_registry, schema_editor):
    """Apply the signed B2 §3 template, read from the .sql file verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    table = "notification_settings"
    schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
    schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
    schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_w3_notification_settings"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-004@3c1f8ab (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md — US-NOT-004 §1/§5 — · 10-notifications/02-business-rules.md · 10-notifications/03-field-map.md §1 · 08-qa/01-e2e/journeys/T7-16-quiet-hours-window-change.md + T7-17-dispatch-batch-size-change.md)
# generated: 2026-08-15 by story-coder (W3 notifications delivery-core lane — the dispatch-config slice)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST on a live Postgres cluster — with `apply_rls` neutered
#         to a no-op and the test database rebuilt, the G5 catalog sweep
#         `test_g5_the_rls_exempt_list_is_exactly_what_b2_declares` reported
#         "AssertionError: tenant-scoped table(s) with NO row-level security
#         policy: ['notification_settings'] — every one is a cross-tenant read
#         away", and this story's own isolation cases failed alongside it
#         ("Failed: DID NOT RAISE DatabaseError" for the no-context probe and
#         for the cross-tenant write). Restored: green. Verbatim transcripts in
#         the lane report · ruff✔ black✔
# exceptions: no immutability trigger — a settings row is CONFIGURATION and is
#         meant to be edited (T7-16 and T7-17 both turn these knobs mid-drain);
#         hard rule 4 names invoices, invoice lines, payments and journal lines,
#         none of which this table holds. What makes an edit accountable is the
#         `notification_settings.updated` audit row the service writes
#         (BR-TEN-016 family, field map §1), not an append-only table · the
#         policy covers this ONE table; `notification_templates` is EP-NOT-02
#         and is still not built
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
