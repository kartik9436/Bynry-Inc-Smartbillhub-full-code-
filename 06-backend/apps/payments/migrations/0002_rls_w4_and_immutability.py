# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (TC-6 "a direct UPDATE on the cleared row → rejected by
#           the append-only trigger"; TC-7 isolation) · US-PAY-006 (the
#           allocation rows a reapply may never edit)
#           Screens: S33 · S35
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 4 (financial
#           immutability — no UPDATE/DELETE on payments; corrections are new
#           rows) · BR-PAY-002 (payments append-only once out of processing;
#           reversal = a new reversing row) · BR-PAY-031 (reapply = reversing
#           allocation rows + new rows, never edits) · NFR-10 (isolation —
#           release blocker)
# ───────────────────────────────────────────────────────
"""payments 0002 — tenant isolation, and the immutability the models cannot give.

HUMAN-OWNED (RLS policies AND financial immutability are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of 2026-08-09.
Applies the SIGNED B2 §3 policy template from
`06-backend/db/rls_payments_w4.sql` verbatim, and invents no new policy shape.
Row in 12-governance/09-human-review-ledger.md.

╔══════════════════════════════════════════════════════════════════════════╗
║  A FREEZE THAT NAMES COLUMNS FAILS OPEN. THIS ONE NAMES NONE.            ║
╚══════════════════════════════════════════════════════════════════════════╝

Two lanes discovered the same hole on 2026-08-11 and it is worth stating in
full, because the obvious way to write this trigger is the broken way.

`billing/0002` and `ledger/0002` both freeze by ENUMERATING the columns that
may not change — `IF NEW.total IS DISTINCT FROM OLD.total OR NEW.due_date IS
DISTINCT FROM OLD.due_date OR …`. That list is correct on the day it is
written and **silently incomplete the moment a migration adds a column.** The
new column is not in the list, so it is not compared, so it is not frozen — and
nothing goes red. The freeze fails OPEN, which is the direction a freeze must
never fail (hard-won law 3), and the only symptom is a financial row that
quietly changed in a column nobody thought about. `billing/0009` and
`billing/0010` each added a column to `invoices` / `invoice_lines` after
`billing/0002` was written; that is how close this is to the surface.

So the triggers below are written the other way round — **DENY BY DEFAULT**:

    frozen_old := to_jsonb(OLD) - MUTABLE_COLUMNS;
    frozen_new := to_jsonb(NEW) - MUTABLE_COLUMNS;
    IF frozen_new IS DISTINCT FROM frozen_old THEN RAISE …

The whole row is compared minus a short, explicit ALLOW list. A column added to
`payments` next month is frozen on the day it is created, with no edit here and
no chance of anybody forgetting. The allow list is three names long and every
one of them is argued below.

THE ALLOW LIST, AND WHY EACH ENTRY IS THERE
-------------------------------------------
It applies **only while the payment is still `processing`** — that is, before
the money has arrived and before anything has been posted to the books. B2 §3
draws exactly this line: *"payments (status<>'processing') … append-only (block
UPDATE/DELETE outright)"*.

  * `status`     the processing → cleared | failed transition (A5 §Payment,
                 flows §2). Without it a payment could never clear.
  * `cleared_at` BR-PAY-021's second date, written by the same transition.
  * `updated_at` Django stamps it on every save; freezing it would make the
                 two rows above unwritable.

Everything else — the amount, the currency, the account, the purpose, the
number, both the posting date and the webhook key — is frozen from the instant
the row exists, even in `processing`. This is NARROWER than B2 §3's literal
parenthetical, which exempts processing rows from the append-only rule
altogether. Narrower, never wider: a $50 payment must not be able to become
$5,000 on its way to clearing. Recorded as a judgment call in the decision log.

**`deposit_batch_id` IS NOT IN THE ALLOW LIST, AND THAT IS A LIVE CONSTRAINT ON
A LANE THAT DOES NOT EXIST YET.** BR-PAY-025 groups CLEARED payments into
day × method deposit batches, which means stamping `deposit_batch_id` on a row
that is already frozen. That door is deliberately shut here: `deposit_batches`
is not built (EP-PAY-06), so opening a door for it now would be opening it on
trust. The lane that builds batches opens it, narrows it to write-once (the
shape `ledger/0002` uses for `auto_reverse_entry_id`), and proves it RED first.
Written down because the next agent has only the repo.

WHAT ELSE THE TRIGGERS DO
-------------------------
**`payments` accepts no DELETE, in any status.** CLAUDE.md hard rule 4 names
payments with no status qualifier (*"no UPDATE/DELETE on issued invoices,
invoice lines, payments, journal entries"*), and money someone handed over has
no delete path: S33's `Cancel` on a processing row is a status move, not a
removal (US-PAY-004 TC-2). Stricter than B2 §3's parenthetical, in the safe
direction, and named here for the reviewer.

**`allocations` accepts no UPDATE and no DELETE at any time.** It has no
processing state to edit through, and BR-PAY-031 is explicit: *"Reapply =
reversing allocation rows + new rows, reason + audit; never edits"*. This
trigger names no columns either — it refuses the statement, not a field.

PROVED RED BEFORE GREEN, on a live cluster: with the triggers dropped, a
cleared payment's `amount` can be updated and its allocation rows deleted; with
them, both statements raise. See the trailer and
tests/test_us_pay_001_record_payment.py.

Postgres only. The default test database is SQLite, which has neither RLS nor
triggers, so the immutability law is ALSO asserted at the service layer and
every database-dependent case carries `requires_postgres` and SKIPS there
rather than passing vacuously.
"""

from pathlib import Path

from django.db import migrations

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_payments_w4.sql"

PAYMENTS_TABLES = ("payments", "allocations")

#: NOTE ON `%%`: `schema_editor.execute(sql)` passes `params=()` down to psycopg,
#: which then treats the string as a format template. A lone `%` in a RAISE would
#: abort the migration, so every placeholder is doubled here and arrives at the
#: server as a single `%`. Same reason as billing/0002 and ledger/0002.
IMMUTABILITY_SQL = """
-- ── payments: append-only once the money has arrived (BR-PAY-002, rule 4) ────
-- The allow list is a CONSTANT inside the function rather than a parameter, so
-- there is exactly one copy of it and it is visible in \\sf output next to the
-- comparison that uses it.
CREATE OR REPLACE FUNCTION payments_payment_immutable() RETURNS trigger AS $$
DECLARE
  -- The ONLY columns a still-processing payment may move. Everything absent
  -- from this list is frozen, INCLUDING every column added after today.
  mutable  text[] := ARRAY['status', 'cleared_at', 'updated_at'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% cannot be removed, in any status. Money that was handed over is financial history; a correction is a new reversing row (BR-PAY-011/013/031), and Cancel on a processing payment is a status move, not a removal.',
      COALESCE(OLD.payment_no, OLD.id::text);
  END IF;

  IF OLD.status <> 'processing' THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is %% and is append-only — no column may change. A reversal, an NSF and a reapply are all NEW rows; this one stands as it was recorded.',
      COALESCE(OLD.payment_no, OLD.id::text), OLD.status;
  END IF;

  -- Still processing: the money has not arrived and nothing has been posted.
  -- The row may take the clearing transition and NOTHING else. Compared as
  -- whole rows minus the allow list, so a column added later is frozen the day
  -- it is created rather than the day somebody remembers to add it here.
  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is processing — only status and cleared_at may change (the clearing transition, BR-PAY-021). The amount, currency, account, purpose, number, posting date and idempotency key are frozen from the moment the row exists. Changed: %%',
      COALESCE(OLD.payment_no, OLD.id::text),
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_payment_immutable ON payments;
CREATE TRIGGER trg_payment_immutable
  BEFORE UPDATE OR DELETE ON payments
  FOR EACH ROW EXECUTE FUNCTION payments_payment_immutable();

-- ── allocations: append-only from birth (BR-PAY-031) ────────────────────────
-- No allow list at all. An allocation has no lifecycle of its own: it is the
-- record that a specific amount of a specific payment met a specific bill, and
-- moving money between bills is two new rows (a negative and a positive), never
-- an edit to this one. The trigger refuses the STATEMENT, so it names no column
-- and cannot fail open when the table grows one.
CREATE OR REPLACE FUNCTION payments_allocation_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'BR-PAY-031 / hard rule 4: allocation %% is append-only (attempted %%). Reapplying a payment writes a REVERSING row and a new row with a reason and an audit entry; nothing edits or removes an allocation that has already been made.',
    COALESCE(OLD.id::text, NEW.id::text), lower(TG_OP);
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_allocation_append_only ON allocations;
CREATE TRIGGER trg_allocation_append_only
  BEFORE UPDATE OR DELETE ON allocations
  FOR EACH ROW EXECUTE FUNCTION payments_allocation_append_only();
"""

DROP_IMMUTABILITY_SQL = """
DROP TRIGGER IF EXISTS trg_payment_immutable ON payments;
DROP TRIGGER IF EXISTS trg_allocation_append_only ON allocations;
DROP FUNCTION IF EXISTS payments_payment_immutable();
DROP FUNCTION IF EXISTS payments_allocation_append_only();
"""


def apply_rls(apps_registry, schema_editor):
    """Apply the signed B2 §3 template, read from the .sql file verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in PAYMENTS_TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def apply_immutability(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(IMMUTABILITY_SQL)


def drop_immutability(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_IMMUTABILITY_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_w4_payment_core"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RunPython(apply_immutability, drop_immutability),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@f4d2b18 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — §2 payments DDL + §3 RLS/immutability template + Addenda r12/r14 — · 04-docs/05-modules/08-payments/06-epics/EP-PAY-01-record-payments.md · 04-docs/05-modules/08-payments/02-business-rules.md · 04-docs/05-modules/08-payments/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W4 payments schema slice — the closed-loop foundation)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN on a live Postgres cluster — with the triggers dropped an UPDATE on a cleared payment's amount SUCCEEDS and an allocation DELETE removes the row; with them both raise. See tests/test_us_pay_001_record_payment.py and the human-review ledger row
# exceptions: the freeze is DENY-BY-DEFAULT (whole-row jsonb comparison minus a
#         three-name allow list) rather than the column-enumerating shape
#         billing/0002 and ledger/0002 use — a named-column freeze fails OPEN on
#         the next migration that adds a column, and two lanes hit that on
#         2026-08-11. The reasoning is in the docstring rather than left to be
#         rediscovered · DELETE is refused on `payments` in EVERY status, which
#         is STRICTER than B2 §3's `status<>'processing'` parenthetical and
#         follows CLAUDE.md hard rule 4's unqualified wording. A DESIGN CHOICE,
#         named for the reviewer · a still-processing payment may move ONLY
#         status/cleared_at/updated_at, also stricter than B2 §3 · the
#         `deposit_batch_id` door BR-PAY-025 will need is deliberately SHUT: the
#         lane that builds `deposit_batches` opens it write-once and proves it
#         RED, and until then a batch stamp on a cleared payment is refused ·
#         Postgres only: the test database is SQLite and has no triggers, so the
#         same law is asserted at the service layer too — a guard that skips
#         silently on the developer's own database is not a guard
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
