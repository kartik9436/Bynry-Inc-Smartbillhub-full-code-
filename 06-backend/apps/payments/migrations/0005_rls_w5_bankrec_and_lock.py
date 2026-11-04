# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-023 (TC-3 "on the reconciled batch: no member add/remove, no
#           total change"; TC-5 "API UPDATE on a reconciled batch's
#           recorded_total → rejected — lock trigger"; TC-6 isolation) ·
#           US-PAY-020 (TC-5 a batch total may never be hand-edited; TC-6
#           isolation) · US-PAY-022 (the resolution rows a reconcile may never
#           rewrite)
#           Screens: S37 · S39 · S40
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 4 (financial
#           immutability — corrections are new rows) · BR-PAY-004 (reconciled
#           deposit batches LOCK; Unreconcile is the only reversal) ·
#           BR-PAY-002 (nothing in the money chain is edited in place) ·
#           BR-PAY-025 (membership is day × method, system-derived) · NFR-10
#           (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""payments 0005 — tenant isolation, the reconciled LOCK, and the door 0002 shut.

HUMAN-OWNED (RLS policies AND financial immutability are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of 2026-08-09.
Applies the SIGNED B2 §3 policy template from `06-backend/db/rls_payments_w5.sql`
verbatim, and invents no new policy shape. Row in
12-governance/09-human-review-ledger.md.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE LOCK IS BR-PAY-004. IT IS ENFORCED HERE OR IT IS NOT ENFORCED.      ║
╚══════════════════════════════════════════════════════════════════════════╝

*"Reconciled deposit batches lock; Unreconcile is the only reversal"* — a Django
model cannot refuse a `.save()`, and a service-layer check is bypassed by the
first repair script anybody writes at 2am. The triggers below are the guarantee;
`apps/payments/bankrec_models.py` describes them and claims nothing.

Written DENY-BY-DEFAULT, the shape `payments/0002` argues for at length: the row
is compared as whole jsonb minus a short ALLOW list, so a column added to
`deposit_batches` next month is frozen the day it is created rather than the day
somebody remembers to add it to an enumeration. A freeze that names columns
fails OPEN, which is the direction a freeze must never fail.

  * **`deposit_batches`** — while `status = 'reconciled'` the ONLY change
    permitted is `status` moving back to `'unmatched'` (that IS Unreconcile),
    plus `updated_at`. Every other column, in every other state, is compared:
    `code`, `method_id`, `deposited_on` and `tenant_id` are frozen from birth
    (they are the batch's identity — BR-PAY-025's day × method), while
    `recorded_total`, `bank_total` and `status` move freely until the lock lands.
    DELETE is refused outright, in every status: a batch is the record of what
    physically went to the bank that day.
  * **`deposit_batch_events`** — no UPDATE, no DELETE, ever. US-PAY-023 §5:
    *"never truncated"*, and a trail that can be rewritten is not a trail.
  * **`bank_rec_resolutions`** — the same. An explanation of a money difference
    is financial history the moment it is written, and BR-PAY-019 makes it the
    only thing standing between a difference and a reconcile.
  * **`bank_lines`** — no DELETE; UPDATE may move `deposit_batch_id` ONCE, from
    NULL to a batch. A re-pointed line is how a reconciled batch would silently
    acquire a different bank line, so the match is write-once for the same
    reason the membership below is.

────────────────────────────────────────────────────────────────────────────
THE DOOR `payments/0002` DELIBERATELY SHUT, OPENED HERE — WRITE-ONCE
────────────────────────────────────────────────────────────────────────────
`payments/0002` froze `deposit_batch_id` on every payment past `processing` and
said so in its own docstring, naming this lane:

    "**`deposit_batch_id` IS NOT IN THE ALLOW LIST, AND THAT IS A LIVE CONSTRAINT
    ON A LANE THAT DOES NOT EXIST YET.** … The lane that builds batches opens it,
    narrows it to write-once (the shape `ledger/0002` uses for
    `auto_reverse_entry_id`), and proves it RED first."

That is exactly what happens below. `payments_payment_immutable()` is REPLACED
(not dropped — a replaced function keeps its trigger) so that a payment which is
already financial history may take a batch stamp **once**:

    NULL → a batch id     allowed, once
    a batch id → anything refused, including back to NULL

Everything else about the payment stays frozen in both branches, and the
still-`processing` branch does NOT gain the column: a payment whose money has not
arrived is not in anybody's drawer.

**The consequence is stated rather than discovered later:** a payment belongs to
exactly one deposit batch, forever. There is no regroup path. US-PAY-020 TC-5
mentions "audited regroup events"; nothing ratifies their shape, so nothing is
invented here (prime directive), and the correction for a mis-cut batch is a
question for the PO rather than an UPDATE.

Together with the batch lock this closes the membership half of BR-PAY-004 with
no extra trigger: adding a member changes `recorded_total` (it is Σ members), and
a reconciled batch refuses that change.

PROVED RED BEFORE GREEN, on a live cluster — see the trailer and
tests/test_us_pay_020_023_bank_rec.py.

Postgres only. The default test database is SQLite, which has neither RLS nor
triggers, so every law here is ALSO asserted at the service layer and every
database-dependent case carries `requires_postgres` and SKIPS there rather than
passing vacuously.
"""

from pathlib import Path

from django.db import migrations

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_payments_w5.sql"

W5_TABLES = (
    "bank_accounts",
    "deposit_batches",
    "deposit_batch_events",
    "bank_statement_imports",
    "bank_lines",
    "bank_rec_resolutions",
)

#: NOTE ON `%%`: `schema_editor.execute(sql)` passes `params=()` down to psycopg,
#: which then treats the string as a format template. A lone `%` in a RAISE would
#: abort the migration, so every placeholder is doubled here and arrives at the
#: server as a single `%`. Same reason as payments/0002.
LOCK_SQL = """
-- ── deposit_batches: the BR-PAY-004 lock ────────────────────────────────────
CREATE OR REPLACE FUNCTION payments_deposit_batch_lock() RETURNS trigger AS $$
DECLARE
  -- Columns a batch may move BEFORE it is reconciled. Its identity (tenant,
  -- code, method, day) is absent on purpose and is therefore frozen from birth.
  open_columns  text[] := ARRAY['recorded_total', 'bank_total', 'status', 'updated_at'];
  -- Columns a RECONCILED batch may move: the status, back to 'unmatched', and
  -- nothing else. That single transition IS Unreconcile (BR-PAY-004).
  locked_columns text[] := ARRAY['status', 'updated_at'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-004 / hard rule 4: deposit batch %% cannot be removed. A batch is the record of what physically went to the bank on a day; corrections are new events on its trail, never a deletion.',
      OLD.code;
  END IF;

  IF OLD.status = 'reconciled' THEN
    frozen_old := to_jsonb(OLD) - locked_columns;
    frozen_new := to_jsonb(NEW) - locked_columns;
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'BR-PAY-004: deposit batch %% is RECONCILED and LOCKED — its totals and membership are immutable. Unreconcile is the only way back (audited, Owner/Finance), and it is a state reversal, not a rewrite. Changed: %%',
        OLD.code,
        (SELECT string_agg(key, ', ' ORDER BY key)
           FROM jsonb_each(frozen_new)
          WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
    END IF;
    IF NEW.status <> 'unmatched' AND NEW.status <> OLD.status THEN
      RAISE EXCEPTION 'BR-PAY-004: deposit batch %% is reconciled; the only status it may take is ''unmatched'' (Unreconcile, which returns it for rework). Asked for %%.',
        OLD.code, NEW.status;
    END IF;
    RETURN NEW;
  END IF;

  frozen_old := to_jsonb(OLD) - open_columns;
  frozen_new := to_jsonb(NEW) - open_columns;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-025: deposit batch %% is identified by its tenant, day, method and code — none of them may change. A batch cut on the wrong day is not edited into the right one. Changed: %%',
      OLD.code,
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_deposit_batch_lock ON deposit_batches;
CREATE TRIGGER trg_deposit_batch_lock
  BEFORE UPDATE OR DELETE ON deposit_batches
  FOR EACH ROW EXECUTE FUNCTION payments_deposit_batch_lock();

-- ── the trail and the explanations: append-only from birth ──────────────────
CREATE OR REPLACE FUNCTION payments_bankrec_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'hard rule 4: %% is append-only (attempted %%). The reconciliation trail is never truncated (US-PAY-023 §5) and an explanation of a money difference is history the moment it is written (BR-PAY-019) — a correction is a new row.',
    TG_TABLE_NAME, lower(TG_OP);
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_deposit_batch_event_append_only ON deposit_batch_events;
CREATE TRIGGER trg_deposit_batch_event_append_only
  BEFORE UPDATE OR DELETE ON deposit_batch_events
  FOR EACH ROW EXECUTE FUNCTION payments_bankrec_append_only();

DROP TRIGGER IF EXISTS trg_bank_rec_resolution_append_only ON bank_rec_resolutions;
CREATE TRIGGER trg_bank_rec_resolution_append_only
  BEFORE UPDATE OR DELETE ON bank_rec_resolutions
  FOR EACH ROW EXECUTE FUNCTION payments_bankrec_append_only();

-- ── bank_lines: the match is WRITE-ONCE ─────────────────────────────────────
CREATE OR REPLACE FUNCTION payments_bank_line_match_once() RETURNS trigger AS $$
DECLARE
  mutable text[] := ARRAY['deposit_batch_id', 'updated_at'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-019 / hard rule 4: bank line %% (%%) cannot be removed — it is what the bank said, and a statement that can lose lines cannot be reconciled against.',
      COALESCE(OLD.reference, OLD.id::text), OLD.amount;
  END IF;
  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-019: bank line %% is what the bank posted — its date, reference and amount are frozen. Only the batch it matches may be set, and only once.',
      COALESCE(OLD.reference, OLD.id::text);
  END IF;
  IF OLD.deposit_batch_id IS NOT NULL
     AND NEW.deposit_batch_id IS DISTINCT FROM OLD.deposit_batch_id THEN
    RAISE EXCEPTION 'BR-PAY-019 / BR-PAY-004: bank line %% is already matched to a deposit batch and a match is WRITE-ONCE. Re-pointing it would move a reconciled batch onto a different bank line without touching the batch at all; Unreconcile is the only way back.',
      COALESCE(OLD.reference, OLD.id::text);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_bank_line_match_once ON bank_lines;
CREATE TRIGGER trg_bank_line_match_once
  BEFORE UPDATE OR DELETE ON bank_lines
  FOR EACH ROW EXECUTE FUNCTION payments_bank_line_match_once();

-- ── bank_statement_imports: a file is imported once, and stays as imported ──
CREATE OR REPLACE FUNCTION payments_statement_import_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'BR-PAY-028 / hard rule 4: bank statement import %% is append-only (attempted %%). The file hash, its tags and who imported it are the evidence a re-import is refused against (US-PAY-021 TC-5); a correction is a new import of a corrected file.',
    COALESCE(OLD.file_name, OLD.id::text), lower(TG_OP);
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_statement_import_append_only ON bank_statement_imports;
CREATE TRIGGER trg_statement_import_append_only
  BEFORE UPDATE OR DELETE ON bank_statement_imports
  FOR EACH ROW EXECUTE FUNCTION payments_statement_import_append_only();
"""

DROP_LOCK_SQL = """
DROP TRIGGER IF EXISTS trg_deposit_batch_lock ON deposit_batches;
DROP TRIGGER IF EXISTS trg_deposit_batch_event_append_only ON deposit_batch_events;
DROP TRIGGER IF EXISTS trg_bank_rec_resolution_append_only ON bank_rec_resolutions;
DROP TRIGGER IF EXISTS trg_bank_line_match_once ON bank_lines;
DROP TRIGGER IF EXISTS trg_statement_import_append_only ON bank_statement_imports;
DROP FUNCTION IF EXISTS payments_deposit_batch_lock();
DROP FUNCTION IF EXISTS payments_bankrec_append_only();
DROP FUNCTION IF EXISTS payments_bank_line_match_once();
DROP FUNCTION IF EXISTS payments_statement_import_append_only();
"""

#: The door `payments/0002` shut. CREATE OR REPLACE keeps the trigger that
#: already points at this function, so the change is one function body and no
#: trigger churn. The `processing` branch is byte-for-byte 0002's; only the
#: frozen branch gains the write-once stamp.
MEMBERSHIP_SQL = """
CREATE OR REPLACE FUNCTION payments_payment_immutable() RETURNS trigger AS $$
DECLARE
  -- The ONLY columns a still-processing payment may move (payments/0002).
  mutable      text[] := ARRAY['status', 'cleared_at', 'updated_at'];
  -- The ONLY column a payment that is already financial history may gain, and
  -- it may gain it ONCE: the deposit batch it was banked in (BR-PAY-025).
  batch_stamp  text[] := ARRAY['deposit_batch_id', 'updated_at'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% cannot be removed, in any status. Money that was handed over is financial history; a correction is a new reversing row (BR-PAY-011/013/031), and Cancel on a processing payment is a status move, not a removal.',
      COALESCE(OLD.payment_no, OLD.id::text);
  END IF;

  IF OLD.status <> 'processing' THEN
    -- Append-only, with ONE door: the batch stamp. Everything else is compared
    -- as a whole row, so a column added later is frozen the day it is created.
    frozen_old := to_jsonb(OLD) - batch_stamp;
    frozen_new := to_jsonb(NEW) - batch_stamp;
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is %% and is append-only — no column may change except the deposit batch it is banked in, once (BR-PAY-025). A reversal, an NSF and a reapply are all NEW rows. Changed: %%',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.status,
        (SELECT string_agg(key, ', ' ORDER BY key)
           FROM jsonb_each(frozen_new)
          WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
    END IF;
    IF OLD.deposit_batch_id IS NOT NULL
       AND NEW.deposit_batch_id IS DISTINCT FROM OLD.deposit_batch_id THEN
      RAISE EXCEPTION 'BR-PAY-025 / BR-PAY-004: payment %% is already in deposit batch %% and batch membership is WRITE-ONCE. A batch total is the sum of its members, so moving a payment between batches would rewrite two signed-off day totals at once; there is no regroup path.',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.deposit_batch_id;
    END IF;
    RETURN NEW;
  END IF;

  -- Still processing: the money has not arrived and nothing has been posted.
  -- The row may take the clearing transition and NOTHING else — a payment whose
  -- money has not arrived is not in anybody's drawer, so the batch stamp is NOT
  -- open here.
  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is processing — only status and cleared_at may change (the clearing transition, BR-PAY-021). The amount, currency, account, purpose, number, posting date, deposit batch and idempotency key are frozen from the moment the row exists. Changed: %%',
      COALESCE(OLD.payment_no, OLD.id::text),
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""

#: The reverse: 0002's function, restored exactly as it was written there — the
#: batch stamp closes again and a `migrate payments 0004` leaves the database in
#: the state 0002 created. A reverse that "roughly" restores a freeze is a
#: freeze nobody can trust.
MEMBERSHIP_REVERSE_SQL = """
CREATE OR REPLACE FUNCTION payments_payment_immutable() RETURNS trigger AS $$
DECLARE
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
"""


def apply_rls(apps_registry, schema_editor):
    """Apply the signed B2 §3 template, read from the .sql file verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in W5_TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def apply_lock(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(LOCK_SQL)


def drop_lock(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_LOCK_SQL)


def open_membership_door(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(MEMBERSHIP_SQL)


def shut_membership_door(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(MEMBERSHIP_REVERSE_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0004_w5_deposit_batches_bank_rec"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RunPython(apply_lock, drop_lock),
        migrations.RunPython(open_membership_door, shut_membership_door),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-023@b6e4c19 (the five EP-PAY-06 sources — 04-docs/02-decisions/02-database-design-brief.md §2 + §3 RLS/immutability template + Addenda r12 #10/#17, r14 #1 · 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md US-PAY-020..023 · 08-payments/02-business-rules.md BR-PAY-004/019/025 · 08-payments/03-field-map.md §6 · 08-payments/07-pre-session-model.md §7)
# generated: 2026-08-11 by Eng-Lead (W5 deposit-batch + bank-reconciliation lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN on a live Postgres cluster — with trg_deposit_batch_lock dropped, a reconciled batch's recorded_total UPDATEs successfully; with the membership door left shut, batching a cleared payment raises the 0002 append-only exception; both failures are quoted verbatim in 12-governance/09-human-review-ledger.md. makemigrations --check clean · pytest tests/test_us_pay_020_023_bank_rec.py · -m isolation on live Postgres
# exceptions: (1) this migration REPLACES `payments_payment_immutable()` — the
#         function payments/0002 created — to open `deposit_batch_id` WRITE-ONCE,
#         which is what 0002's own docstring instructed this lane to do. The
#         reverse restores 0002's body exactly, so `migrate payments 0004` shuts
#         the door again
#         (2) the batch lock permits exactly ONE transition out of `reconciled`
#         (→ `unmatched`, i.e. Unreconcile). Any other status change from
#         reconciled is refused, which is STRICTER than BR-PAY-004's wording and
#         is the safe direction
#         (3) DELETE is refused on all five tables, in every state
#         (4) there is NO regroup path for batch membership, by construction —
#         named in the docstring rather than left to be discovered
#         (5) Postgres only: the test database is SQLite and has no triggers, so
#         the same laws are asserted at the service layer too
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
