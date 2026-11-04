# ── Trace ──────────────────────────────────────────────
# Story:    CR-007 (the disconnect notices — the platform writes the defaults,
#           PO ruling 2026-08-17)   Screens: S8 → Notifications
# Rules:    BR-NOT-015 (the rights footer is a platform default a System Admin
#           may override; the override is System-Admin-only and audited) ·
#           BR-TEN-031 (settings CONTENT belongs to the owning module) ·
#           CLAUDE.md rule 1 (tenant scoping — see the RLS note below)
# ───────────────────────────────────────────────────────
"""notifications 0008 — where a utility's rights-clause choices live.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). ⚠ This marker was
ADDED 2026-08-18 by the CR-009 C-section lane: the file shipped 2026-08-17
without it and G7 was RED on exactly that — the one thing the guard exists to
catch (hard-won law 1: enrolment is the docstring's claim, and this file made
none). Nothing else here changed; the migration's content is the CR-007
lane's, reviewed under its own ledger row.

ONE COLUMN ON AN EXISTING TABLE, `notification_settings.disconnect_rights_clauses`.

**NO NEW RLS MIGRATION IS NEEDED AND THAT IS A FACT, NOT AN OMISSION.**
`notification_settings` already carries its tenant-isolation policy from
migration 0004 (`notification_settings_tenant_isolation`, FORCE on), and a policy
governs the ROW, not the column list — so this column is covered by the existing
policy the moment it exists. Adding a table would have needed a new policy, a new
signed `db/rls_*.sql` and a new entry in B2's schema; adding a column to a table
that already has one needs none of those, which is most of why the choice was
made this way (see the model's own note).

**DEFAULT `{}` AND NOT NULL.** An untouched tenant holds the empty map, which
means "every clause is the platform's default and every clause is on". There is
deliberately no NULL state: a nullable column would make "never configured" and
"configured to nothing" two values, and BR-NOT-015's *"the default must be
VISIBLY MARKED as a default"* would then depend on which of the two a tenant
happened to hold.

The backfill is therefore free — Django writes `{}` into every existing row, and
that is exactly the state those tenants are already in.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0007_w4_returned_mail_and_holds"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationsettings",
            name="disconnect_rights_clauses",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-007@rights-footer (12-governance/11-change-requests.md §"CR-007 · The disconnect notices — the platform writes the defaults" · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-015)
# generated: 2026-08-17 by story-coder (CR-007 DISCONNECT-NOTICE lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · `makemigrations --check` clean after this lands · the
#         existing isolation probe for `notification_settings` covers the row and
#         therefore this column; a rights-clause-specific cross-tenant probe is in
#         tests/test_cr_007_disconnect_rights_footer.py and is Postgres-only
# exceptions: no immutability trigger — a rights clause is CONFIGURATION and is
#         meant to be edited; hard rule 4 names invoices, invoice lines, payments
#         and journal lines. What makes an edit accountable is the
#         `notification_settings.updated` audit row `rights_footer.update_clauses`
#         writes in the same transaction, carrying the FULL before and after text
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
