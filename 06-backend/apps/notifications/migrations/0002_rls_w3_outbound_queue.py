# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-001 (TC-6 isolation — "Lone Star Ridge queue query: its rows
#           only; Brazos Bend's 1,124-bill rows invisible (RLS FORCE)")
#           Screens: S8 · S30 · S35
# Rules:    CLAUDE.md rule 1 (never touch a tenant table without app.tenant_id;
#           RLS FORCE is on) · B2 §3 policy template · DB-1 · BR-NOT-005 (the
#           queue is platform-wide, so one leak here spans every module) ·
#           NFR-10 (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""notifications 0002 — tenant isolation for `outbound_messages`.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-11 under the PO ruling of 2026-08-09. Applies the SIGNED
B2 §3 policy template from `06-backend/db/rls_notifications_w3.sql` verbatim,
and invents no new policy shape. Row in
12-governance/09-human-review-ledger.md.

WHY THIS TABLE IS THE ONE TO GET RIGHT. Most tenant tables hold a tenant's own
operational data. This one holds its CUSTOMERS' personal data in the form most
directly usable by somebody who should not have it: name, service address,
phone number and email address, one row per person per message, snapshotted at
queue time so it stays readable long after the source row changes. A missing
policy here is not a data leak in the abstract — it is another utility's
mailing list, already formatted for sending.

It is also platform-wide (r12 #16): bills, receipts, collection notices, plan
notices and report emails all land in this single table, so one missing policy
would span every module at once rather than one module's rows.

Deny-by-default, not filter-by-default: with `app.tenant_id` unset the
template's `::uuid` cast of `''` raises and NO row is visible. FORCE applies the
policy to the table owner too.

PROVED RED BEFORE GREEN, on a live cluster: with the policy neutered, the G5
catalog sweep in `tests/test_tenant_isolation.py` names `outbound_messages` as
a tenant-scoped table with no row-level security, and the story's own isolation
cases see both tenants' rows. See the trailer for the verbatim failure.

Postgres only — SQLite has no RLS, so the unit tier asserts SHAPE (the
`tenant` column every policy depends on) and says so rather than implying
coverage.
"""

from pathlib import Path

from django.db import migrations

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_notifications_w3.sql"


def apply_rls(apps_registry, schema_editor):
    """Apply the signed B2 §3 template, read from the .sql file verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    table = "outbound_messages"
    schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
    schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
    schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_w3_outbound_queue"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-001@2e6b19d (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — Addendum r10 #8 + r12 #16 + r16 #1/#6/#7 — · 04-docs/05-modules/10-notifications/06-epics/EP-NOT-01-outbound-queue.md · 10-notifications/02-business-rules.md · 10-notifications/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 notifications outbound-queue schema slice)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST on a live Postgres cluster. With `apply_rls` neutered
#         to a no-op and the test database rebuilt, `-m isolation` went
#         5 failed / 59 passed / 12 skipped, and the CATALOG SWEEP named the
#         table by name — `test_g5_the_rls_exempt_list_is_exactly_what_b2_
#         declares` reported "AssertionError: tenant-scoped table(s) with NO
#         row-level security policy: ['outbound_messages'] — every one is a
#         cross-tenant read away", with pytest's own set diff printing "Extra
#         items in the left set: 'outbound_messages'". The four story cases
#         failed alongside it: deny-without-context and cross-tenant-write both
#         "Failed: DID NOT RAISE DatabaseError"; TC-6 "outbound_messages: under
#         <A>'s context the database exposed rows of {<B>}"; and the catalog
#         read "outbound_messages has no row-level security". Restored:
#         64 passed / 12 skipped, up from the 59/12 baseline by exactly the
#         five cases this policy makes possible. ruff✔ black✔
# exceptions: applies the B2 §3 template to ONE table, which is the whole
#         notifications RLS surface today — `notification_templates` is
#         EP-NOT-02 and does not exist, and the base `notifications` table B2 §3
#         listed was REPLACED by `outbound_messages` (r12 #16, field-map N-6
#         disposition in 0001) so it will never need a policy · no immutability
#         trigger ships here: a queue row is NOT a financial record (hard rule 4
#         names invoices, invoice lines, money movements and journal lines, and
#         this table holds none of them), and its status legitimately advances
#         and is legitimately reset by the ratified re-queue action
#         (US-NOT-013). Forward-only status transitions are the DISPATCHER's
#         guard (US-NOT-002) and are not built — stated so the absence is
#         findable rather than mistaken for coverage (hard-won law 1)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
