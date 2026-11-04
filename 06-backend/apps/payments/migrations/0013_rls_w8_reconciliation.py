# ── Trace ──────────────────────────────────────────────
# Story:    CR-059 wave W8 — reconciliation. Tasks 43–46, the guarantees the
#           model classes in 0011 cannot give.
#           Screens: S8 · S37 · S38 · S39 · S40
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 4 (financial
#           immutability — corrections are new rows) · BR-PAY-019 (every
#           difference carries a reason AND a GL) · BR-PAY-004 (a reconciled
#           batch LOCKS) · BR-TEN-034 (deactivate, never delete)
# ───────────────────────────────────────────────────────
"""payments 0013 — isolation for the W8 tables, and the match set's WRITE-ONCE.

HUMAN-OWNED (RLS policies AND financial immutability are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-01 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md. Applies the SIGNED B2 §3 policy
template VERBATIM per table and invents no new policy shape — the same template
`db/rls_payments_w5.sql` carries for the six W5 tables.

╔══════════════════════════════════════════════════════════════════════════╗
║  THREE NEW TABLES, AND EVERY ONE OF THEM SAYS SOMETHING ABOUT A TENANT'S ║
║  BANK POSITION. THE TEMPLATE IS NOT OPTIONAL FOR ANY OF THEM.            ║
╚══════════════════════════════════════════════════════════════════════════╝

  * `bank_rec_match_sets` / `bank_rec_match_members` — WHICH of our deposits a
    bank credit paid for. A cross-tenant read is somebody else's banking.
  * `bank_rec_difference_reasons` — a tenant's own vocabulary for why its bank
    did not agree with its books.

────────────────────────────────────────────────────────────────────────────
A MATCH SET IS WRITE-ONCE, AND THAT IS THE SAME LAW `bank_lines` ALREADY HAS
────────────────────────────────────────────────────────────────────────────
`payments_bank_line_match_once()` (migration 0005) refuses to re-point a bank
line's batch: *"Re-pointing it would move a batch onto a different bank line
without touching the batch at all."* A match set is the second way to tie the
same money, so it takes the same law rather than a weaker one — otherwise the
guarantee simply moves to whichever door a caller happens to use.

  * `bank_rec_match_sets` — no UPDATE and no DELETE. The set's `matched_total`
    is what the two sides tied at; a set whose total could be rewritten is not
    evidence of anything.
  * `bank_rec_match_members` — the same. Removing a member would silently
    change what a reconciled batch was matched against.

**There is deliberately NO dissolve verb anywhere**, in this migration or in the
service. CS-17 rules that a match may be a SET; nothing ruled how one is undone,
and inventing that here would be this lane ratifying a rule nobody ruled. A set
tied wrongly is a question for the PO, exactly as a batch cut on the wrong day
is (US-PAY-020 TC-5's unratified "regroup event", still unratified).

────────────────────────────────────────────────────────────────────────────
`bank_rec_difference_reasons` IS AN ORDINARY REFERENCE LIST, SO IT IS NOT FROZEN
────────────────────────────────────────────────────────────────────────────
It takes RLS and nothing else. A reference row is EDITED and DEACTIVATED by
design (BR-TEN-034), and the append-only guarantee lives one table away where it
belongs: `bank_rec_resolutions.reason_code` stores the CODE as text, so a
resolution written under `bank_fee` still reads `bank_fee` after somebody
deactivates or renames the list row. The immutability that matters is already
enforced by 0005's `payments_bankrec_append_only()`.

Postgres only. The default test database is SQLite, which has neither RLS nor
triggers, so every law here is ALSO refused at the service layer and every
database-dependent case carries `requires_postgres` and SKIPS there rather than
passing vacuously.
"""

from django.db import migrations

W8_TABLES = (
    "bank_rec_match_sets",
    "bank_rec_match_members",
    "bank_rec_difference_reasons",
)

#: B2 §3's template, repeated per table. Deny-by-default: with `app.tenant_id`
#: unset, `NULLIF(…, '')::uuid` is NULL and the comparison is NULL, so NO row is
#: visible and no row may be written.
RLS_SQL = "\n".join(f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
""" for table in W8_TABLES)

#: NOTE ON `%%`: `schema_editor.execute(sql)` passes `params=()` to psycopg,
#: which then treats the string as a format template, so a lone `%` in a RAISE
#: aborts the migration. Every placeholder is doubled here and arrives at the
#: server as a single `%`. Same reason as payments/0002 and 0005.
MATCH_SET_SQL = """
CREATE OR REPLACE FUNCTION payments_bank_rec_match_write_once() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'BR-PAY-019 / hard rule 4: %% is write-once (attempted %%). A match set is what a bank credit was agreed to pay for; re-pointing or removing it would change what a batch was reconciled against without touching the batch at all. There is no dissolve path — CS-17 rules that a match may be a SET and nothing rules how one is undone.',
    TG_TABLE_NAME, lower(TG_OP);
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_bank_rec_match_set_write_once ON bank_rec_match_sets;
CREATE TRIGGER trg_bank_rec_match_set_write_once
  BEFORE UPDATE OR DELETE ON bank_rec_match_sets
  FOR EACH ROW EXECUTE FUNCTION payments_bank_rec_match_write_once();

DROP TRIGGER IF EXISTS trg_bank_rec_match_member_write_once ON bank_rec_match_members;
CREATE TRIGGER trg_bank_rec_match_member_write_once
  BEFORE UPDATE OR DELETE ON bank_rec_match_members
  FOR EACH ROW EXECUTE FUNCTION payments_bank_rec_match_write_once();
"""

DROP_MATCH_SET_SQL = """
DROP TRIGGER IF EXISTS trg_bank_rec_match_set_write_once ON bank_rec_match_sets;
DROP TRIGGER IF EXISTS trg_bank_rec_match_member_write_once ON bank_rec_match_members;
DROP FUNCTION IF EXISTS payments_bank_rec_match_write_once();
"""


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL)


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in W8_TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def apply_write_once(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(MATCH_SET_SQL)


def drop_write_once(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_MATCH_SET_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0012_cr059_w8_reconciliation"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RunPython(apply_write_once, drop_write_once),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: 12-governance/11-change-requests.md CR-059 §8 (CS-14 · CS-16 · CS-17 · CS-18) + §11 tasks 43–46 · 12-governance/01-open-questions.md OQ-161 (CLOSED 2026-08-12) · 12-governance/02-decision-log.md 2026-08-12 "BUILD MANY-TO-ONE BANK MATCHING" · 04-docs/02-decisions/02-database-design-brief.md §3 (the RLS template) + Addenda r12 #10/#17 · apps/payments/migrations/0005_rls_w5_bankrec_and_lock.py (the shape this follows)
# generated: 2026-09-01 by the CR-059 W8 reconciliation lane
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI — the four screen halves are CR-059 task 48) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check clean · pytest tests/test_cr059_w8_reconciliation.py · the RLS and write-once cases carry requires_postgres and SKIP on the SQLite suite — SEE THE EXCEPTION BELOW, they are NOT claimed as proved
# exceptions: (1) ⚠ **NOTHING IN THIS MIGRATION HAS BEEN PROVED ON A LIVE POSTGRES CLUSTER BY THIS LANE.** The RLS policies and both write-once triggers are Postgres-only and the default suite is in-memory SQLite (config/settings/test.py hardcodes it — CLAUDE.md law 14), so every case that would exercise them SKIPS. Seeding a live cluster is blocked by DEF-2395 and another lane is fixing it. What IS proved is the service-layer half: `reconciliation.match_set` refuses a second tie on the same line or batch by name, and that refusal runs on SQLite. What is NOT proved is that the DATABASE refuses it when a repair script bypasses the service. REPORTED, not claimed
#         (2) `bank_lines.deposit_batch_id` is NOT dropped — see 0011's docstring. CS-17 says "replace the single line-to-batch link with a match set" and this lane kept the column, because dropping it would rewrite every reconciliation settled since 2026-08-11. Recorded as a judgment in 12-governance/02-decision-log.md
#         (3) there is NO dissolve/unmatch path for a match set, in the database or in the service. CS-17 rules the SET in and rules nothing about undoing one
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
