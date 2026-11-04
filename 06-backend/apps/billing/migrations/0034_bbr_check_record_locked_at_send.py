# ── Trace ──────────────────────────────────────────────
# Ruling:   PO 2026-09-30, option A (decision log, *"WHAT HAPPENS TO THE BULK
#           RUN'S CHECK OUTPUT WHEN THE RUN IS SENT"*) — *"Keep as long as the
#           bills (never deleted, like the run and its bills)"*.
# Tests:    tests/test_bbr_check_record_locked.py (refused on PostgreSQL by
#           this trigger; by `check_store.refuse_if_sent` on every database)
# ───────────────────────────────────────────────────────
"""billing 0034 — a SENT run's check record is locked.

HUMAN-OWNED (a financial-immutability rule and migration ordering are CLAUDE.md
🔒 paths). HUMAN-REVIEW-PENDING — AI-authored 2026-09-30 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

Once a run is SENT — a `bill_run_releases` row for it carries `released_at` —
its four check tables take no INSERT, UPDATE or DELETE:

  * `bill_run_decisions` and `bill_run_standing_answers` explain the money on
    the bills that went out (*"Sep water estimated at 5 kgal, accepted by
    J. Ortiz"*), so they are kept as long as the bills and never change;
  * `bill_run_account_checks` is the run's final CHECK REPORT;
  * `bill_run_findings` holds only the final version per account (a re-check
    replaces an account's rows — `check_store.save_account_check`), and that
    final version is what is locked.

Nothing is ever deleted afterwards: there is no retention job, by ruling. The
accounts a sent run did not bill go to Pending billing, and a catch-up run is a
NEW run with its own, fresh check — it never writes into its parent's record.

The same refusal is made in Python (`check_store.refuse_if_sent`) so a clerk
gets a sentence instead of a database error, and so the sqlite suite exercises
it; this trigger is the guarantee, because a guard in one code path is not a
guard against the next one written. Postgres only (`PostgresOnlySQL`).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

TABLES = (
    "bill_run_decisions",
    "bill_run_standing_answers",
    "bill_run_account_checks",
    "bill_run_findings",
)

FUNCTION = """
CREATE OR REPLACE FUNCTION bbr_check_record_locked_at_send() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  run uuid;
BEGIN
  IF TG_OP = 'INSERT' THEN
    run := NEW.bill_run_id;
  ELSE
    run := OLD.bill_run_id;
  END IF;
  IF EXISTS (
    SELECT 1 FROM bill_run_releases r
    WHERE r.bill_run_id = run AND r.released_at IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'bill run % is sent: % is locked', run, TG_TABLE_NAME
      USING ERRCODE = '55000';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END
$$;
"""

TRIGGERS = "".join(f"""
DROP TRIGGER IF EXISTS trg_{table}_locked_at_send ON {table};
CREATE TRIGGER trg_{table}_locked_at_send
  BEFORE INSERT OR UPDATE OR DELETE ON {table}
  FOR EACH ROW EXECUTE FUNCTION bbr_check_record_locked_at_send();
""" for table in TABLES)

REVERSE = (
    "".join(f"DROP TRIGGER IF EXISTS trg_{table}_locked_at_send ON {table};\n" for table in TABLES)
    + "DROP FUNCTION IF EXISTS bbr_check_record_locked_at_send();\n"
)


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0033_rls_bbr_check_store"),
    ]

    operations = [PostgresOnlySQL(FUNCTION + TRIGGERS, reverse_sql=REVERSE)]
