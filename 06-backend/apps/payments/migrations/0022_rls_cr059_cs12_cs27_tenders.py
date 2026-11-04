# ── Trace ──────────────────────────────────────────────
# Story:    CR-059 CS-12 (task 49) · CR-059 CS-27 (task 51) — the guarantees the
#           model class in `tender_models.py` cannot give.
#           Screens: S21 · S22 · S33 · S35 (tasks 50 and 52 — ANOTHER LANE)
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 4 (financial
#           immutability — corrections are new rows) · BR-PAY-1126 (one tender,
#           N payments) · BR-PAY-1127 (the parts sum to the tender exactly)
# ───────────────────────────────────────────────────────
"""payments 0022 — isolation for `payment_tenders`, and its WRITE-ONCE law.

HUMAN-OWNED (RLS policies AND financial immutability are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md. Applies the SIGNED B2 §3 policy
template VERBATIM and invents no new policy shape — the same template
`db/rls_payments_w5.sql` carries for the six W5 tables and 0013 carries for the
three W8 ones.

╔══════════════════════════════════════════════════════════════════════════╗
║  A TENDER ROW SAYS WHAT A NAMED CUSTOMER HANDED OVER, ON WHAT DAY, ON    ║
║  WHICH CHEQUE. A CROSS-TENANT READ IS SOMEBODY ELSE'S BANKING.           ║
╚══════════════════════════════════════════════════════════════════════════╝

────────────────────────────────────────────────────────────────────────────
WRITE-ONCE, AND IT IS THE SAME LAW `bank_rec_match_sets` ALREADY HAS
────────────────────────────────────────────────────────────────────────────
`payments_bank_rec_match_write_once()` (migration 0013) refuses to re-point a
match set, because *"a set whose total could be rewritten is not evidence of
anything"*. A tender is the same kind of object one table along: its `amount` is
**what was in the drawer**, and BR-PAY-1127 — *the parts must sum to the tender
exactly, or the whole submission is refused* — is an arithmetic statement about
that number. Let the number change afterwards and the sum that was checked at
commit stops being true of the row that recorded it, silently, with three
payments still pointing at it.

⚠ **THIS IS NOT NARROWED BY THE 2026-09-02 RULING AND MUST NOT BE READ AS IF IT
WERE.** The PO opened `confirmation`, `memo` and `method_id` on **`payments`**,
through the one endpoint `POST /payments/{id}/correct-reference`, and
CLAUDE.md's own words are that *"`payments/0014` is the ONLY place the
database's allow list moves; widening it anywhere else is a new ruling, not this
one."* So a tender takes hard rule 4 unnarrowed: **no UPDATE and no DELETE, in
any status.**

**A MISTYPED CHEQUE NUMBER IS STILL CORRECTABLE AND NOTHING HERE TAKES THAT
AWAY** — the number a bank line matches on is `payments.confirmation`, which
every part of the tender carries, and that is exactly the column the PO opened.
The tender's own `reference` is the record of what was typed at the time.

**THERE IS DELIBERATELY NO UNDO VERB**, in this migration or in the service. A
tender recorded wrongly is unwound the way any payment is: each part is
REVERSED, which is a new row and not an edit (BR-PAY-002), and BR-PAY-1131 says
reversing a master tender reverses every unit payment it made. Inventing a
"dissolve tender" here would be this lane ratifying a rule nobody ruled — the
same sentence 0013 wrote about a match set, for the same reason.

Postgres only. The default test database is SQLite, which has neither RLS nor
triggers, so every law here is ALSO enforced at the service layer and every
database-dependent case carries `requires_postgres` and SKIPS there rather than
passing vacuously (hard-won law 14: the naive version is green on every machine
in this repository).
"""

from django.db import migrations

TENDER_TABLES = ("payment_tenders",)

#: B2 §3's template, verbatim. Deny-by-default: with `app.tenant_id` unset,
#: `NULLIF(…, '')::uuid` is NULL and the comparison is NULL, so NO row is
#: visible and no row may be written.
RLS_SQL = "\n".join(f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
""" for table in TENDER_TABLES)

#: NOTE ON `%%`: `schema_editor.execute(sql)` passes `params=()` to psycopg,
#: which then treats the string as a format template, so a lone `%` in a RAISE
#: aborts the migration. Every placeholder is doubled here and arrives at the
#: server as a single `%`. Same reason as payments/0002, 0005 and 0013.
WRITE_ONCE_SQL = """
CREATE OR REPLACE FUNCTION payments_tender_write_once() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'hard rule 4 / BR-PAY-1127: payment_tenders is write-once (attempted %%). A tender records what was handed over and its amount is what its parts were checked to sum to; rewriting it would leave three payments pointing at a total nobody ever agreed. Correct a cheque number on the payments (POST /payments/{id}/correct-reference); unwind a tender by REVERSING its parts.',
    lower(TG_OP);
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_payment_tender_write_once ON payment_tenders;
CREATE TRIGGER trg_payment_tender_write_once
  BEFORE UPDATE OR DELETE ON payment_tenders
  FOR EACH ROW EXECUTE FUNCTION payments_tender_write_once();
"""

DROP_WRITE_ONCE_SQL = """
DROP TRIGGER IF EXISTS trg_payment_tender_write_once ON payment_tenders;
DROP FUNCTION IF EXISTS payments_tender_write_once();
"""


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL)


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TENDER_TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def apply_write_once(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(WRITE_ONCE_SQL)


def drop_write_once(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_WRITE_ONCE_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0021_cr059_cs12_cs27_payment_tenders"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RunPython(apply_write_once, drop_write_once),
    ]
