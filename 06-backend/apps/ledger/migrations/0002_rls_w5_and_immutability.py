# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (every money event becomes ONE BALANCED entry — its
#           TC-5: "unbalanced entry rejected by the B2 §3 constraint trigger")
#           · US-LED-003 (reversal pairs under append-only books — its TC-5:
#           "UPDATE/DELETE attempted on any posted journal_entries/
#           journal_lines row → rejected outright by the append-only
#           triggers") · US-LED-005 (chart of accounts, TC-6 isolation)
#           Screens: S56 · S36
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 4 (financial
#           immutability — corrections are new rows) · rule 5 (balanced pairs)
#           · BR-LED-003 (posted entries IMMUTABLE; drafts freely editable
#           /deletable; balanced required AT POST) · BR-LED-005 (an accrual's
#           auto-reverse link is written after it is already posted) ·
#           BR-LED-007 (tie-out drift is only possible via a posting-service
#           bypass) · NFR-10 (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""ledger 0002 — tenant isolation, append-only books, and BALANCE.

HUMAN-OWNED (RLS policies, financial immutability AND the balanced-pair rule
are CLAUDE.md 🔒 paths). HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under
the PO ruling of 2026-08-09. Applies the SIGNED B2 §3 policy template from
`06-backend/db/rls_ledger_w5.sql` verbatim, and implements B2 §3's own
`assert_balanced()` sketch. Row in
12-governance/09-human-review-ledger.md.

THREE GUARANTEES, ALL OF THEM IN THE DATABASE
---------------------------------------------
**1 · Tenant isolation.** Three tables, the whole of a tenant's books. Same
B2 §3 template as every other module, read from the .sql file verbatim.

**2 · Append-only (hard rule 4 / BR-LED-003).** A POSTED journal entry cannot
be deleted, cannot be un-posted, and cannot have its date, type, source, memo,
currency or reversal link changed. Its lines cannot be updated, deleted **or
inserted**. A draft can be edited and deleted freely — BR-LED-003 in the PO's
own terms: *"drafts freely editable/deletable before post; balanced required at
post"*, and *"edit/update" of a posted entry = one-click REVERSE + REPOST*.

**3 · Balance (hard rule 5).** Debits equal credits on every posted entry.

WHY BALANCE IS A TRIGGER AND NOT PYTHON. A balance rule is a statement about a
SET of rows, and no application-level hook can see the set: the ORM validates
one line at a time, and by the time the last line is saved the first four are
already committed-in-transaction. A service function can compute the sum — right
up until a management command, a data fix, a `.update()`, a repair script or a
later migration writes lines without calling it, which is precisely the
"posting-service bypass" BR-LED-007 names as the ONLY way tie-out drift can
happen. So it is a DEFERRABLE INITIALLY DEFERRED constraint trigger: the check
runs once, at COMMIT, when the whole entry exists. A rule that only lives in
Python is not a rule.

THE CONTRACT THIS IMPOSES ON THE POSTING SERVICE (write it down — the next
agent has only the repo). **AMENDED 2026-08-11: it is now honoured —
`apps/ledger/posting.py` was built and does exactly these three steps.** The
passage stays because it is where the REASON lives, not the status. Because
lines cannot be inserted into an entry that is ALREADY posted,
`apps/ledger/posting.py` must, inside ONE transaction:

    1. INSERT the journal_entries row as `draft`
    2. INSERT its journal_lines
    3. UPDATE the entry to `posted`   ← balance is asserted here, at COMMIT

That is not an accident of the trigger; it is BR-LED-003's ratified lifecycle
(*balanced required at post*) made structural, and it is the same three steps a
human takes on S57. Inserting an entry directly as `posted` is not forbidden —
it simply fails at COMMIT with "posted with no lines", loudly, rather than
quietly creating an empty entry.

FOUR EDGES THE CHECK WOULD LEAK THROUGH IF IT WERE WRITTEN NAIVELY, and what
closes each:

  * **An entry with NO lines.** B2 §3's sketch fires per INSERTED LINE, so an
    entry with zero lines is never checked and 0 = 0 balances vacuously. The
    check here also hangs off `journal_entries`, and a posted entry with no
    lines is refused (B2 §1: *journal_entry 1:N journal_lines (balanced)*).
  * **A line with an unreadable `side`.** The sums are
    `FILTER (WHERE side='debit')` / `FILTER (WHERE side='credit')`; a row with
    `side='dbit'` lands in neither, so its money vanishes from both totals and
    the entry balances. `ck_journal_lines_side` (0001) makes the two filters
    exhaustive — the CHECK constraint is part of the balance guarantee, not
    decoration.
  * **A draft.** BR-LED-003 makes drafts editable, so a half-written draft
    MUST be allowed to sit unbalanced across commits. Every check below
    therefore returns early unless the entry is `posted`.
  * **Posting an already-written draft.** Nothing inserts a line at that
    moment, so a line-only trigger never fires. The entry-side trigger fires on
    UPDATE, which is exactly the draft → posted transition.

PROVED RED BEFORE GREEN, on a live cluster: with the triggers dropped, a posted
entry accepts 100 debit against 60 credit, and its lines accept UPDATE and
DELETE. With them, every one of those statements raises. See the trailer and
tests/test_us_led_journal_core.py.

Postgres only. The default test database is SQLite, which has neither RLS nor
these triggers, so every assertion that depends on them carries
`requires_postgres` and SKIPS there rather than passing vacuously.
"""

from pathlib import Path

from django.db import migrations

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_ledger_w5.sql"

#: NOTE ON `%%`: `schema_editor.execute(sql)` passes `params=()` down to
#: psycopg, which then treats the string as a format template. A lone `%` in a
#: RAISE would abort the migration, so every placeholder is doubled here and
#: arrives at the server as a single `%`. Same reason as billing/0002.
BALANCE_SQL = """
-- ── the balance rule (hard rule 5; B2 §3 `assert_balanced`) ──────────────────
-- One function, two triggers. It is written to take an ENTRY ID rather than a
-- trigger row so that the line-side and entry-side triggers cannot drift apart
-- into two subtly different definitions of "balanced".
CREATE OR REPLACE FUNCTION ledger_assert_balanced(entry_id uuid) RETURNS void AS $$
DECLARE
  entry_status text;
  line_count   integer;
  debits       numeric;
  credits      numeric;
BEGIN
  SELECT status INTO entry_status FROM journal_entries WHERE id = entry_id;
  IF entry_status IS NULL THEN
    RETURN;            -- the entry was deleted in this same transaction
  END IF;
  IF entry_status <> 'posted' THEN
    RETURN;            -- BR-LED-003: a draft may sit unbalanced until it posts
  END IF;

  SELECT count(*),
         coalesce(sum(amount) FILTER (WHERE side = 'debit'), 0),
         coalesce(sum(amount) FILTER (WHERE side = 'credit'), 0)
    INTO line_count, debits, credits
    FROM journal_lines
   WHERE journal_entry_id = entry_id;

  IF line_count = 0 THEN
    RAISE EXCEPTION 'CLAUDE.md rule 5 / B2 §1: journal entry %% is posted with no lines — an entry with nothing in it is not a journal entry',
      entry_id;
  END IF;

  IF debits <> credits THEN
    RAISE EXCEPTION 'CLAUDE.md rule 5 / BR-LED-003: journal entry %% is UNBALANCED — debits %% <> credits %% . A posted entry must balance to the cent; nothing partial lands.',
      entry_id, debits, credits;
  END IF;
END;
$$ LANGUAGE plpgsql;

-- B2 §3's own trigger, verbatim in shape: per inserted line, deferred to COMMIT
-- so the rest of the entry has had a chance to arrive.
CREATE OR REPLACE FUNCTION ledger_journal_line_balanced() RETURNS trigger AS $$
BEGIN
  PERFORM ledger_assert_balanced(NEW.journal_entry_id);
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS journal_balanced ON journal_lines;
CREATE CONSTRAINT TRIGGER journal_balanced
  AFTER INSERT ON journal_lines
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION ledger_journal_line_balanced();

-- The half B2 §3 does not have: the entry itself. Catches the draft -> posted
-- transition (where no line is written and the line trigger never fires) and
-- the posted-entry-with-no-lines case.
CREATE OR REPLACE FUNCTION ledger_journal_entry_balanced() RETURNS trigger AS $$
BEGIN
  PERFORM ledger_assert_balanced(NEW.id);
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS journal_entry_balanced ON journal_entries;
CREATE CONSTRAINT TRIGGER journal_entry_balanced
  AFTER INSERT OR UPDATE ON journal_entries
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION ledger_journal_entry_balanced();
"""

IMMUTABILITY_SQL = """
-- ── journal_entries: posted is forever (hard rule 4 / BR-LED-003) ────────────
CREATE OR REPLACE FUNCTION ledger_journal_entry_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status = 'posted' THEN
      RAISE EXCEPTION 'hard rule 4 / BR-LED-003: journal entry %% is POSTED and cannot be deleted. A correction is a linked reversing entry, never a removal.',
        OLD.id;
    END IF;
    RETURN OLD;         -- a draft has not entered the books
  END IF;

  IF OLD.status = 'draft' THEN
    RETURN NEW;         -- BR-LED-003: drafts edit freely, including draft -> posted
  END IF;

  -- Posted. Exactly ONE column may still move, and only once: the forward
  -- auto-reverse link. BR-LED-005 posts an accrual's mirror on day 1 of the
  -- NEXT period and links them "both ways" — the accrual is long since posted
  -- by then, so freezing every column would make the ratified rule
  -- unimplementable. It may go NULL -> set; it may never be re-pointed or
  -- cleared, because that would silently detach a mirror that already exists.
  IF OLD.auto_reverse_entry_id IS NOT NULL
     AND NEW.auto_reverse_entry_id IS DISTINCT FROM OLD.auto_reverse_entry_id THEN
    RAISE EXCEPTION 'hard rule 4 / BR-LED-005: journal entry %% already links to its auto-reversal; the link is written once and never moved',
      OLD.id;
  END IF;

  IF NEW.tenant_id      IS DISTINCT FROM OLD.tenant_id
  OR NEW.entry_date     IS DISTINCT FROM OLD.entry_date
  OR NEW.type           IS DISTINCT FROM OLD.type
  OR NEW.status         IS DISTINCT FROM OLD.status
  OR NEW.source_type    IS DISTINCT FROM OLD.source_type
  OR NEW.source_id      IS DISTINCT FROM OLD.source_id
  OR NEW.memo           IS DISTINCT FROM OLD.memo
  OR NEW.currency       IS DISTINCT FROM OLD.currency
  OR NEW.reversal_of    IS DISTINCT FROM OLD.reversal_of
  OR NEW.posted_at      IS DISTINCT FROM OLD.posted_at THEN
    RAISE EXCEPTION 'hard rule 4 / BR-LED-003: journal entry %% is POSTED and immutable — only its auto-reversal link may still be written. An "edit" is a reverse + repost (two new entries), never a change to this row.',
      OLD.id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_journal_entry_immutable ON journal_entries;
CREATE TRIGGER trg_journal_entry_immutable
  BEFORE UPDATE OR DELETE ON journal_entries
  FOR EACH ROW EXECUTE FUNCTION ledger_journal_entry_immutable();

-- ── journal_lines: append-only, and closed to LATE INSERTS ───────────────────
-- A line has no status of its own; it is frozen by its ENTRY's, exactly as an
-- invoice line is frozen by its invoice. INSERT is blocked as well as UPDATE
-- and DELETE: appending a BALANCED pair to an entry that is already posted
-- would slip past the balance check while changing money in a posted entry,
-- which is the one thing hard rule 4 exists to prevent.
CREATE OR REPLACE FUNCTION ledger_journal_line_append_only() RETURNS trigger AS $$
DECLARE
  parent_id     uuid;
  parent_status text;
BEGIN
  parent_id := COALESCE(NEW.journal_entry_id, OLD.journal_entry_id);
  SELECT status INTO parent_status FROM journal_entries WHERE id = parent_id;

  IF parent_status = 'posted' THEN
    RAISE EXCEPTION 'hard rule 4 / BR-LED-003: journal entry %% is POSTED — its lines are frozen (attempted %%). Post a linked reversing entry instead; the books are append-only.',
      parent_id, lower(TG_OP);
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_journal_line_append_only ON journal_lines;
CREATE TRIGGER trg_journal_line_append_only
  BEFORE INSERT OR UPDATE OR DELETE ON journal_lines
  FOR EACH ROW EXECUTE FUNCTION ledger_journal_line_append_only();
"""

DROP_TRIGGERS_SQL = """
DROP TRIGGER IF EXISTS journal_balanced ON journal_lines;
DROP TRIGGER IF EXISTS journal_entry_balanced ON journal_entries;
DROP TRIGGER IF EXISTS trg_journal_entry_immutable ON journal_entries;
DROP TRIGGER IF EXISTS trg_journal_line_append_only ON journal_lines;
DROP FUNCTION IF EXISTS ledger_journal_line_balanced();
DROP FUNCTION IF EXISTS ledger_journal_entry_balanced();
DROP FUNCTION IF EXISTS ledger_assert_balanced(uuid);
DROP FUNCTION IF EXISTS ledger_journal_entry_immutable();
DROP FUNCTION IF EXISTS ledger_journal_line_append_only();
"""

LEDGER_TABLES = ("ledger_accounts", "journal_entries", "journal_lines")


def apply_rls(apps_registry, schema_editor):
    """Apply the signed B2 §3 template, read from the .sql file verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in LEDGER_TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def apply_balance(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(BALANCE_SQL)


def apply_immutability(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(IMMUTABILITY_SQL)


def drop_triggers(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_TRIGGERS_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0001_w5_journal_core"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RunPython(apply_balance, drop_triggers),
        # Immutability last: the balance triggers must already exist when the
        # append-only ones start refusing writes, or a reversed migration could
        # leave a window with neither.
        migrations.RunPython(apply_immutability, drop_triggers),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-001@c7a1f30 (sha1[:7] of the four sources this slice was
#         authored from, concatenated in order:
#         02-database-design-brief.md — §2 ledger DDL + §3 RLS/balance
#         triggers + Addendum r13 — · EP-LED-01-posting-consumption.md ·
#         09-ledger/02-business-rules.md · 09-ledger/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W5 ledger journal-core schema slice)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN on a live Postgres cluster — see the test file
#         and the human-review ledger row
# exceptions: the append-only trigger blocks INSERT into a POSTED entry as well
#         as UPDATE/DELETE, which imposes a three-step contract on the posting
#         service (draft -> lines -> post, one transaction) — written while that
#         service was still a stub and HONOURED since 2026-08-11, when
#         apps/ledger/posting.py was built to exactly that shape. That is
#         BR-LED-003's own lifecycle made structural, but it IS a constraint on
#         a service this slice does not build, and it is stated in the docstring
#         rather than left to be discovered · the ONE narrow door on a posted
#         entry is `auto_reverse_entry_id`, write-once: BR-LED-005 links an
#         accrual to a mirror created a period later, so freezing every column
#         would make a ratified rule unimplementable. A DESIGN CHOICE, named
#         here for the reviewer · drafts are editable and deletable, which is
#         BR-LED-003 verbatim and NARROWER than a literal reading of CLAUDE.md
#         rule 4 ("no UPDATE/DELETE on ... journal entries") — the ledger
#         module's own signed rule governs, and the same draft/issued split is
#         what billing/0002 shipped for invoices · Postgres only: the default
#         test database is SQLite, so every dependent assertion carries
#         `requires_postgres` and SKIPS rather than passing vacuously
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
