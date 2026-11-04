# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-25 · task 62 — "Reject a request, and correct an
#           approved write-off". The CR's own words: *"once approved,
#           receivables have been permanently reduced and there is no path
#           back — while the append-only rule explicitly says an erroneous
#           write-off is corrected by a NEW row."*
# Story:    US-PAY-012 (write-offs)   Screens: S36 (the queue) · S34
# Rules:    BR-PAY-020 (initiated in payments, approved + reported in finance) ·
#           BR-PAY-002 (append-only — an erroneous write-off is corrected by a
#           NEW row, never an edit) · BR-PAY-037 (both acts recorded
#           distinctly) · BR-PAY-1120 (NEW 2026-09-01 — the four-state set and
#           what each may do next) · CLAUDE.md hard rule 4 · rule 6 · rule 2
# Defect:   DEF-3120 — 0010's freeze comment claims deny-by-default and the
#           function is a FROZEN-COLUMN LIST, so every column added after
#           2026-08-15 was silently mutable. Fixed here.
# ───────────────────────────────────────────────────────
"""payments 0011 — `rejected` and `reversed`, and the freeze that had a hole.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering AND an immutability
trigger over a table that permanently reduces receivables are both CLAUDE.md 🔒
paths. AI-authored 2026-09-01 under the PO ruling of 2026-08-09 (*"AI will do
it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
WHAT CHANGES, IN ONE PARAGRAPH
════════════════════════════════════════════════════════════════════════════
The write-off status set goes from two values to four. `rejected` is a status
move on a row that never posted anything — it moves no money and it is not a
deletion. `reversed` is carried by a **NEW ROW** that reverses an approved one,
never by the original, exactly as a bounced cheque's `reversed` is carried by
its reversing payment row. Five nullable columns arrive with them, one unique
index makes a write-off reversible ONCE, and one check keeps `reverses_write_off`
and `reversal_reason` together — a reversing row that does not say why, or a
`why` on a row that reverses nothing, are both refused by the database.

════════════════════════════════════════════════════════════════════════════
⚠ THE FREEZE IN 0010 WAS NOT WHAT ITS OWN COMMENT SAID (DEF-3120)
════════════════════════════════════════════════════════════════════════════
0010's comment reads, verbatim: *"Deny-by-default, exactly as `refunds` is
frozen by 0006: every column is refused unless it is named below, so a column
added to this table LATER is frozen the day it exists rather than the day
somebody remembers to add it."*

**The function underneath it is the opposite shape.** `refunds` really is
deny-by-default — it builds `to_jsonb(OLD) - mutable` and compares the
remainder, so anything not on the `mutable` list is frozen including columns
that do not exist yet. `write_offs` names NINE FROZEN COLUMNS and raises if any
of them moved, which leaves every OTHER column — every column added after
2026-08-15, all five of this migration's — **freely writable by any UPDATE**.

Nothing was wrong in the product, because no column had been added since. It
would have gone wrong today: `reversal_reason` and `reverses_write_off_id` are
the whole evidence of a correction to bad debt, and an UPDATE could have
re-pointed them at another write-off with the trigger watching and saying
nothing. Hard-won law 1 in its purest form — *a comment claiming a guarantee is
not the guarantee* — so the function is REPLACED here with the `refunds` shape
it always claimed to be, and the claim is now true.

════════════════════════════════════════════════════════════════════════════
THE FOUR TRANSITIONS THE TRIGGER ENFORCES (BR-PAY-1120)
════════════════════════════════════════════════════════════════════════════
  requested → approved   the Finance act. Posts DR write-off / CR AR.
  requested → rejected   the approver's other answer. Posts nothing.
  approved  → ✗          TERMINAL. 0010 already refused this and it still does:
                         un-approving would leave the books saying one thing and
                         the account another. The correction is a NEW ROW.
  rejected  → ✗          TERMINAL, and NEW here. A rejected request that could
                         be approved later would let the same debt be written
                         off twice — once through the resurrected row and once
                         through the fresh request the clerk raised after being
                         refused. Re-raising is a new row, which costs nothing.
  reversed  → ✗          TERMINAL, and NEW here. A reversing row IS a correction;
                         correcting the correction is another new row.

Postgres only. SQLite has neither RLS nor triggers and the developer test
database is in-memory SQLite (`config/settings/test.py` hardcodes it and ignores
`DATABASE_URL` — CLAUDE.md law 14), so **every one of these transitions is ALSO
refused at the service layer** in `apps/payments/writeoffs.py` and asserted
there in tests. A check that skips silently on the database a developer
actually runs is not a check.
"""

import django.db.models.deletion
from django.db import migrations, models

# ── the freeze, in the shape 0010's comment always claimed (DEF-3120) ───────
# `%` is doubled: `schema_editor.execute` passes the string through the DB-API's
# parameter interpolation, and a bare `%` aborts the migration. Same reason as
# 0002, 0006, billing/0002 and ledger/0002.
FREEZE_SQL = """
CREATE OR REPLACE FUNCTION payments_write_offs_append_only() RETURNS trigger AS $$
DECLARE
  -- The ONLY columns a write-off may move after it is written. EVERYTHING
  -- ABSENT FROM THIS LIST IS FROZEN, INCLUDING EVERY COLUMN ADDED AFTER TODAY.
  -- The amount, the account, the reason, the note, the requesting act and the
  -- reversal link are facts from the instant the row exists.
  --
  -- `reverses_write_off_id` and `reversal_reason` are deliberately NOT here: a
  -- reversing row states what it reverses and why AT INSERT, and re-pointing
  -- either afterwards would detach a correction from the bad debt it corrects.
  mutable text[] := ARRAY[
    'status',
    'approved_by', 'approved_on',
    'rejected_by', 'rejected_on', 'rejection_reason',
    'gl_account_id', 'journal_entry_id',
    'updated_at'
  ];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'hard rule 4 / BR-PAY-020: write_offs is append-only — a write-off recorded in error is corrected by a NEW reversing row, never deleted.';
  END IF;

  -- Terminal states. Each one has already had its final effect: `approved`
  -- reduced receivables, `rejected` refused to, and `reversed` IS the
  -- correction. Moving any of them would let one decision be spent twice.
  IF OLD.status IN ('approved', 'rejected', 'reversed')
     AND NEW.status IS DISTINCT FROM OLD.status THEN
    RAISE EXCEPTION 'hard rule 4 / BR-PAY-1120: write-off %% is %% and that is terminal. An approved write-off has already posted DR write-off / CR AR and is corrected by a NEW reversing row; a rejected request is re-raised as a NEW request; a reversing row is itself a correction. Un-picking any of them here would leave the books saying one thing and the account another.',
      OLD.id::text, OLD.status;
  END IF;

  -- Write-once on the entry link: NULL -> set, and never re-pointed. A
  -- re-pointed link would silently detach a write-off from the entry that holds
  -- its bad debt, which is the one question the column exists to answer.
  IF OLD.journal_entry_id IS NOT NULL
     AND NEW.journal_entry_id IS DISTINCT FROM OLD.journal_entry_id THEN
    RAISE EXCEPTION 'hard rule 4: write-off %% already names journal entry %% and the link is written once. A correction to the books is a reversing entry, never a new pointer.',
      OLD.id::text, OLD.journal_entry_id::text;
  END IF;

  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'hard rule 4 / BR-PAY-020: write-off %% is frozen except its decision columns (status, the approval pair, the rejection triple and the two ledger links). The amount a human approved must be the amount that was requested, and a reversal states what it reverses at insert. Changed: %%',
      OLD.id::text,
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_write_offs_append_only ON write_offs;
CREATE TRIGGER trg_write_offs_append_only
  BEFORE UPDATE OR DELETE ON write_offs
  FOR EACH ROW EXECUTE FUNCTION payments_write_offs_append_only();
"""

# The 0010 body, restored VERBATIM. plpgsql has no partial replacement, so a
# reverse has to carry the whole previous function; the diff against 0010 is the
# review. ⚠ Reversing this migration reinstates DEF-3120's hole AND the two
# statuses' rows would then violate `ck_write_offs_status` — which is why the
# constraint is dropped and re-added rather than left to a `RunSQL` pair.
FREEZE_SQL_0010 = """
CREATE OR REPLACE FUNCTION payments_write_offs_append_only() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'hard rule 4 / BR-PAY-020: write_offs is append-only — a write-off recorded in error is corrected by a NEW reversing row, never deleted.';
  END IF;
  IF NEW.tenant_id     IS DISTINCT FROM OLD.tenant_id
  OR NEW.account_id    IS DISTINCT FROM OLD.account_id
  OR NEW.amount        IS DISTINCT FROM OLD.amount
  OR NEW.currency      IS DISTINCT FROM OLD.currency
  OR NEW.reason        IS DISTINCT FROM OLD.reason
  OR NEW.note          IS DISTINCT FROM OLD.note
  OR NEW.requested_by  IS DISTINCT FROM OLD.requested_by
  OR NEW.requested_on  IS DISTINCT FROM OLD.requested_on
  OR NEW.created_at    IS DISTINCT FROM OLD.created_at THEN
    RAISE EXCEPTION 'hard rule 4 / BR-PAY-020: only the APPROVAL columns of a write-off may move (status, approved_by, approved_on, gl_account_id, journal_entry_id). The amount a human approved must be the amount that was requested.';
  END IF;
  IF OLD.status = 'approved' AND NEW.status IS DISTINCT FROM OLD.status THEN
    RAISE EXCEPTION 'hard rule 4 / BR-PAY-020: an APPROVED write-off has already posted DR write-off / CR AR. Un-approving it would leave the books saying one thing and the account another; the correction is a new row.';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_write_offs_append_only ON write_offs;
CREATE TRIGGER trg_write_offs_append_only
  BEFORE UPDATE OR DELETE ON write_offs
  FOR EACH ROW EXECUTE FUNCTION payments_write_offs_append_only();
"""


def _apply_freeze(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return  # SQLite has no triggers; the service layer carries the same rule
    schema_editor.execute(FREEZE_SQL)


def _restore_0010_freeze(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(FREEZE_SQL_0010)


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0004_rls_security_policies"),
        ("payments", "0010_rls_writeoffs_and_intents"),
    ]

    operations = [
        # ── the rejection triple ────────────────────────────────────────────
        migrations.AddField(
            model_name="writeoff",
            name="rejected_by",
            field=models.ForeignKey(
                blank=True,
                db_column="rejected_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="write_offs_rejected",
                to="identity.user",
            ),
        ),
        migrations.AddField(
            model_name="writeoff",
            name="rejected_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="writeoff",
            name="rejection_reason",
            field=models.TextField(blank=True, null=True),
        ),
        # ── the reversal pair ───────────────────────────────────────────────
        migrations.AddField(
            model_name="writeoff",
            name="reverses_write_off",
            field=models.ForeignKey(
                blank=True,
                db_column="reverses_write_off_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="reversals",
                to="payments.writeoff",
            ),
        ),
        migrations.AddField(
            model_name="writeoff",
            name="reversal_reason",
            field=models.TextField(blank=True, null=True),
        ),
        # ── the status set widens (CS-25's own "Data" line) ─────────────────
        migrations.RemoveConstraint(
            model_name="writeoff",
            name="ck_write_offs_status",
        ),
        migrations.AddConstraint(
            model_name="writeoff",
            constraint=models.CheckConstraint(
                condition=models.Q(status__in=("requested", "approved", "rejected", "reversed")),
                name="ck_write_offs_status",
            ),
        ),
        # ── one reversal per write-off (hard rule 6) ────────────────────────
        migrations.AddConstraint(
            model_name="writeoff",
            constraint=models.UniqueConstraint(
                condition=models.Q(reverses_write_off__isnull=False),
                fields=("tenant", "reverses_write_off"),
                name="uq_write_offs_reverses",
            ),
        ),
        migrations.AddConstraint(
            model_name="writeoff",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(reverses_write_off__isnull=False, reversal_reason__isnull=False)
                    | models.Q(reverses_write_off__isnull=True, reversal_reason__isnull=True)
                ),
                name="ck_write_offs_reversal_pair",
            ),
        ),
        # ── DEF-3120 — the freeze becomes what its comment always said ──────
        migrations.RunPython(_apply_freeze, _restore_0010_freeze),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §7 (write-offs, three modules three verbs) · §8 CS-25 · §11
#         task 62 · apps/payments/migrations/0010 · apps/payments/migrations/0006
#         (the `refunds` freeze this copies) · BR-PAY-020 · BR-PAY-002 ·
#         BR-PAY-037 · BR-PAY-1120
# generated: 2026-09-01 by the CR-059 W11 write-off lane
# checklist: A✔ B✔ C✔ D=deferred(CR-059 task 63/65 own P10) E=deferred(same)
#            F✔ G✔ H=deferred(PO 2026-08-09)
# gates: the trigger's five refusals were each proved RED first — see the lane
#         report and tests/test_cr059_cs25_write_off_states.py
# exceptions:
#   E1 FIVE new columns, where CS-25's Data line names TWO. The two it names are
#      the reversal pair (`reverses_write_off_id`, `reversal_reason`); the other
#      three are the rejection triple, which that line does not mention because
#      it describes only the reversal half. Recorded in
#      12-governance/02-decision-log.md with the worked figure.
#   E2 NO new index. The bad-debt read (CS-26) filters `(tenant, status)` and
#      then a date range, and `ix_write_offs_status` already leads with exactly
#      that pair. A utility under 3,000 connections writes off tens of rows a
#      year, not thousands.
#   E3 The trigger is Postgres-only and the developer suite is SQLite
#      (CLAUDE.md law 14). Every transition it refuses is ALSO refused in
#      `writeoffs.py` and asserted there — REPORTED, not silently skipped.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
