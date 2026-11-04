# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (source-event posting contracts — the DATABASE half of
#           TC-5 "a billing/payments code path INSERTs into journal_lines
#           directly → insert forbidden (sole writer)" and of TC-6 "the same
#           issue handoff replayed twice → one entry, ever")
#           Screens: S56 · S36
# Rules:    CLAUDE.md rule 4 (financial immutability) · rule 5 (balanced pairs;
#           ONLY the ledger posting service writes journal lines) · rule 6
#           (idempotency) · BR-LED-003 (posted entries immutable) · BR-LED-007
#           (tie-out drift is only possible via a posting-service BYPASS — this
#           migration is what makes that bypass impossible rather than merely
#           forbidden) · B2 r13 #8 (posting-service mechanics = Eng-Lead 🔒)
# Tests:    06-backend/tests/test_us_led_001_posting.py ·
#           06-backend/tests/test_us_led_journal_core.py
# ───────────────────────────────────────────────────────
"""ledger 0004 — the SOLE-WRITER fence and the per-source posting guard.

HUMAN-OWNED (migration ordering, idempotency keys AND ledger posting are all
CLAUDE.md 🔒 paths). HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO
ruling of 2026-08-09. Row in 12-governance/09-human-review-ledger.md.

TWO GUARANTEES, BOTH IN THE DATABASE, AND WHY NEITHER COULD LIVE IN PYTHON
--------------------------------------------------------------------------
`ledger/0002` put BALANCE and IMMUTABILITY in the database and said why. This
migration finishes the set with the two laws 0002 left as conventions.

**1 · SOLE WRITER (hard rule 5).** *"Only the ledger posting service writes
journal lines."* Until now that sentence was enforced by nothing: any module
could `JournalLine.objects.create(...)`, a management command could, a data-fix
script could, and the books would move with no balanced pair, no dimensions, no
posting key and no audit row. **BR-LED-007 names that exact bypass as the ONLY
way a subledger tie-out can drift** — so the tie-out panel US-LED-004 builds is
a detector for a hole nothing was closing. `journal_entries` and `journal_lines`
now refuse an INSERT that did not come through `apps/ledger/posting.py`.

The mechanism is the one this codebase already trusts for tenancy: a session
GUC. `posting.post()` opens a narrow window with
`set_config('app.ledger_posting', 'on', true)` inside its own transaction and
closes it again before returning; the trigger refuses every INSERT taken outside
that window. It is the same shape as `app.tenant_id` and RLS, and it is honest
about what it is: **a fence, not a vault.** Anything that can open a database
connection can also issue that `set_config`. What it makes impossible is the
ACCIDENT — a new module, a repair script or a well-meaning `bulk_create` moving
the books without going through the one function that balances, keys, stamps and
audits them. A caller that deliberately forges the GUC has written the words
"I am bypassing the ledger posting service" into its own source, which is the
most a database can ask for and is infinitely more than a docstring.

Only INSERT is gated, and that is sufficient rather than partial: a POSTED entry
is already frozen by 0002's immutability trigger, its lines are already closed to
UPDATE/DELETE *and late INSERT*, and a DRAFT can only exist if some INSERT
created it — which this refuses. So there is no path to a journal row that does
not begin with an INSERT this trigger sees.

**2 · THE PER-SOURCE POSTING GUARD (hard rule 6).** US-LED-001 TC-6: *"the same
issue handoff replayed twice → second replay no-ops on the per-source posting
guard — one entry, ever."* GT-16 (❄️ finance-signed) says the same for the
cutover batch: *"re-posting the same batch is idempotent (no second JE set)."*

**B2 DEFINES NO SUCH KEY, AND THAT IS A FINDING RATHER THAN AN OVERSIGHT ON THIS
LANE'S PART.** §2's `journal_entries` DDL carries no unique constraint at all,
and DB-12 — the consolidated idempotency-uniques register — lists
`(tenant, idempotency_key)` for bill runs, `(tenant, webhook_key)` for payments,
file+tags for imports and `export_batches`, and **nothing for the journal**. The
RULE is signed twice over (TC-6 and GT-16); the MECHANICS are delegated in
signed text — B2 r13 #8: *"Exact DDL + posting-service mechanics = Eng-Lead 🔒"*,
and EP-LED-01 §5 spells the row out: *"Posting guard | per-source idempotency
(mechanics Eng-Lead 🔒, r13 #8) | replay no-ops"*. So the column and its index
are authored here under that delegation, REPORTED as an extension beyond B2 §2's
literal DDL, and the key's composition lives in `apps/ledger/posting.py` where a
reader can see the worked string.

It is a PARTIAL unique index (`WHERE posting_key IS NOT NULL`). A manual JE
(EP-LED-04) has no upstream source event and therefore no replay to guard
against; a plain UNIQUE would have allowed exactly one such entry per tenant
forever, which is the same trap `uq_ledger_accounts_designation` sidesteps for
the same reason.

WHY THE IMMUTABILITY FUNCTION IS REWRITTEN HERE, AND WHY THAT IS NOT OPTIONAL
-----------------------------------------------------------------------------
0002's `ledger_journal_entry_immutable()` freezes a posted entry by NAMING each
column it compares. That is the right shape — the one lawful door
(`auto_reverse_entry_id`) is visible in the source rather than implied — but it
carries a cost that has to be paid on every schema change: **a column the
function does not name is a column a posted entry can still change.** Adding
`posting_key` without touching the trigger would have created a posted,
immutable entry whose idempotency key could be edited afterwards, which is a
door straight back into double-posting: clear the key, replay the handoff, get a
second entry. The function is therefore `CREATE OR REPLACE`d with `posting_key`
in its frozen list, and the test suite proves the new column is frozen rather
than trusting that it was remembered.

PROVED RED BEFORE GREEN, on a live Postgres cluster (hard-won law 7): with the
sole-writer triggers dropped, a raw `JournalLine.objects.create()` outside
`post()` succeeds; with the unique index dropped, replaying one handoff writes
the books twice; with `posting_key` removed from the immutability list, an
`UPDATE` clears the key of a posted entry. Each failure is quoted verbatim in
this lane's row of 12-governance/09-human-review-ledger.md.

Postgres only. The default test database is SQLite, which has neither RLS nor
triggers, so every assertion that depends on this migration carries
`requires_postgres` and SKIPS there rather than passing vacuously. The
service-layer half of both laws (`posting.post()` refuses an unbalanced request
and looks the key up before inserting) is what protects the developer database,
exactly as `apps/billing/issue._refuse_unless_issuable` does for hard rule 4.
"""

from django.db import migrations, models

#: NOTE ON `%%`: `schema_editor.execute(sql)` passes `params=()` to psycopg,
#: which then treats the string as a format template. A lone `%` in a RAISE
#: would abort the migration, so every placeholder is doubled here and arrives
#: at the server as a single `%`. Same reason as ledger/0002 and billing/0002.
SOLE_WRITER_SQL = """
-- ── hard rule 5: only the posting service writes the books ───────────────────
-- The window is opened by apps/ledger/posting.py with
--   SELECT set_config('app.ledger_posting', 'on', true)
-- inside its own transaction, and closed again before it returns. Every other
-- INSERT lands here.
CREATE OR REPLACE FUNCTION ledger_sole_writer_guard() RETURNS trigger AS $$
BEGIN
  IF coalesce(current_setting('app.ledger_posting', true), '') <> 'on' THEN
    RAISE EXCEPTION 'CLAUDE.md rule 5: %% is written ONLY by the ledger posting service (apps/ledger/posting.py). This INSERT did not come through post(), so it lands nowhere. A money event reaches the books by calling post() with a balanced request; BR-LED-007 names a posting-service BYPASS as the only way a subledger tie-out can drift.',
      TG_TABLE_NAME;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_journal_entries_sole_writer ON journal_entries;
CREATE TRIGGER trg_journal_entries_sole_writer
  BEFORE INSERT ON journal_entries
  FOR EACH ROW EXECUTE FUNCTION ledger_sole_writer_guard();

DROP TRIGGER IF EXISTS trg_journal_lines_sole_writer ON journal_lines;
CREATE TRIGGER trg_journal_lines_sole_writer
  BEFORE INSERT ON journal_lines
  FOR EACH ROW EXECUTE FUNCTION ledger_sole_writer_guard();
"""

DROP_SOLE_WRITER_SQL = """
DROP TRIGGER IF EXISTS trg_journal_entries_sole_writer ON journal_entries;
DROP TRIGGER IF EXISTS trg_journal_lines_sole_writer ON journal_lines;
DROP FUNCTION IF EXISTS ledger_sole_writer_guard();
"""

#: ledger/0002's function, re-issued with `posting_key` added to the frozen
#: column list. Everything else is byte-identical to 0002 ON PURPOSE — a
#: rewrite that also "tidied" the other clauses would make the diff between
#: two versions of a hard-rule-4 guard unreadable, which is the last place a
#: reviewer should have to squint.
IMMUTABILITY_SQL = """
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
  -- auto-reverse link (BR-LED-005 — see ledger/0002 for the full argument).
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
  OR NEW.posting_key    IS DISTINCT FROM OLD.posting_key
  OR NEW.memo           IS DISTINCT FROM OLD.memo
  OR NEW.currency       IS DISTINCT FROM OLD.currency
  OR NEW.reversal_of    IS DISTINCT FROM OLD.reversal_of
  OR NEW.posted_at      IS DISTINCT FROM OLD.posted_at THEN
    RAISE EXCEPTION 'hard rule 4 / BR-LED-003: journal entry %% is POSTED and immutable — only its auto-reversal link may still be written. An "edit" is a reverse + repost (two new entries), never a change to this row. (The posting key is frozen with the rest: clearing it would re-open the replay this entry already consumed — hard rule 6.)',
      OLD.id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

#: The 0002 text, verbatim, so a reverse of THIS migration restores the guard
#: that existed before it rather than dropping hard rule 4 on the way back.
IMMUTABILITY_SQL_WITHOUT_POSTING_KEY = IMMUTABILITY_SQL.replace(
    "  OR NEW.posting_key    IS DISTINCT FROM OLD.posting_key\n", ""
)


def _pg_only(sql):
    def run(apps_registry, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        schema_editor.execute(sql)

    return run


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0003_gl_designations"),
    ]

    operations = [
        migrations.AddField(
            model_name="journalentry",
            name="posting_key",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.UniqueConstraint(
                condition=models.Q(("posting_key__isnull", False)),
                fields=("tenant", "posting_key"),
                name="uq_journal_entries_posting_key",
            ),
        ),
        # The column must exist before the trigger that freezes it.
        migrations.RunPython(
            _pg_only(IMMUTABILITY_SQL),
            _pg_only(IMMUTABILITY_SQL_WITHOUT_POSTING_KEY),
        ),
        # Last: once this lands nothing but post() can insert, so it must not be
        # in force while an earlier operation in this same migration might need
        # to touch the tables.
        migrations.RunPython(
            _pg_only(SOLE_WRITER_SQL),
            _pg_only(DROP_SOLE_WRITER_SQL),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-001@c7a1f30 (sources this migration was authored from, in order: 04-docs/02-decisions/02-database-design-brief.md — §2 journal DDL + §3 balance/append-only triggers + Addendum r13 #8 "posting-service mechanics = Eng-Lead 🔒" + the DB-12 idempotency register — · 04-docs/05-modules/09-ledger/06-epics/EP-LED-01-posting-consumption.md US-LED-001 TC-5/TC-6 + §5 "Posting guard" · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-003/007 · 04-docs/02-decisions/05-golden-tests.md GT-16 ❄️ "re-posting the same batch is idempotent")
# generated: 2026-08-11 by Eng-Lead (W5 ledger posting-service lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN on a live Postgres cluster — three mutations
#         (sole-writer triggers dropped · unique index dropped · posting_key
#         removed from the immutability list), each quoted verbatim in the
#         human-review ledger row
# exceptions: `journal_entries.posting_key` and `uq_journal_entries_posting_key`
#         are an EXTENSION beyond B2 §2's literal DDL — §2 gives the table no
#         unique key and DB-12's idempotency register does not list the journal
#         at all. The RULE is signed (US-LED-001 TC-6, GT-16 ❄️); the MECHANICS
#         are delegated by B2 r13 #8. REPORTED for the reviewer, not silently
#         taken · the sole-writer fence is a session GUC, so it stops the
#         ACCIDENTAL bypass and not a deliberate one — stated in the docstring
#         rather than claimed to be more than it is (hard-won law 1) · only
#         INSERT is gated; UPDATE/DELETE on posted rows were already refused by
#         0002 and a draft cannot exist without an INSERT · no new RLS policy:
#         this migration creates no table and adds one column to a row already
#         gated by `journal_entries_tenant_isolation` (ledger/0002) · reversing
#         this migration restores 0002's immutability function rather than
#         dropping it, which is why the reverse SQL is derived from the forward
#         text instead of being retyped
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
