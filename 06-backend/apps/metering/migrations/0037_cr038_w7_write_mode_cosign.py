# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 W7 task 3 (the three write modes, at stage 1) and task 5
#           (async post + co-sign — `cosigned_by` has been SERVED since
#           migration 0003 and never written).
# Rules:    CR-038 R2 (insert · insert & update · replace-as-supersede, for
#           reads, never editing a committed row) · CR-036 (g) (PO 2026-08-26:
#           "you need at step 1 or 2 itself - this is important decision how
#           you will process the data and upload it") · BR-MET-127 (a billed
#           read is refused BY NAME) · OQ-042 closure (co-sign is an optional
#           tenant toggle, supervisor = SysAdmin/Executive) · BR-MET-055 ·
#           CLAUDE.md rule 4 (financial immutability — nothing here enables an
#           UPDATE of a committed read; `replace` means supersede) ·
#           CLAUDE.md rule 1 (no data pass touches rows here — columns only,
#           so no tenant predicate is needed)
# Tests:    06-backend/tests/test_cr038_w7_write_modes.py
# ───────────────────────────────────────────────────────
"""metering 0036 — `write_mode` and `cosigned_at` on `read_import_batches`.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-26 under the PO ruling of 2026-08-09 (*"AI will do it; we will review
it later as human"*). The G7 review-ledger row is written by this lane in
`12-governance/09-human-review-ledger.md`, and it states in plain English WHAT
WAS PUT TO THE PO and what was NOT — the default `insert` and the
`already-on-file` figure were shown; the RLS posture of the two new columns was
not, because they inherit `read_import_batches`' existing FORCEd policy and no
policy statement changes here.

WHY `write_mode` IS NOT NULLABLE WHEN EVERY OTHER STAGE-1 TAG IS
---------------------------------------------------------------
BR-MET-014 makes the stage-1 TAGS optional, and `read_method` (migration 0032)
is nullable for exactly that reason: a method nobody stated reads as "not
stated" and no code branches on it. The write mode is not a tag — it is a
PREMISE, and `commit_read_batch` branches on it for every row. So it must hold
one of the three values at all times, and the default is `insert`: the only
mode of the three that cannot write over a reading already on file.

THE BACKFILL IS A STATEMENT OF HISTORY, NOT A REINTERPRETATION. Every batch
that exists today was posted under a pipeline where a committed duplicate was
an ERROR that gated the whole post — which is precisely what `insert` means
here. `default="insert"` therefore backfills every existing row with what it
actually was, and no data pass is needed.

WHY `cosigned_at` ARRIVES NOW
-----------------------------
`cosigned_by` shipped with migration 0003, has been served by
`selectors.read_batch_dict` on every batch since, and **nothing has ever
written it** — hard-won law 2 ("built is not wired"), and the gap CR-038's
coverage map names in its own row. This migration lands beside the first writer
that column has ever had (`services.cosign_read_batch`). A signature with no
date is not a signature an auditor can use, so the timestamp lands with the
writer rather than after it.

⚠ **WHAT THIS MIGRATION DOES NOT DO.** OQ-042's closure has two halves — a
co-sign DOOR and a tenant TOGGLE that makes posting BLOCK until the co-sign is
given. Only the door lands here. The toggle's home is the S64 read-validation
settings document, whose model and screen are owned by a concurrent lane, and
building half of it into a surface another lane is editing is how two lanes
produce one broken control. The gap is filed as DEF-815 rather than left as a
comment (hard-won law 1).

REVERSIBLE. Dropping the two columns returns the reads rail to a single
implicit `insert` mode and returns `cosigned_by` to being served and unwritten.
No committed read carries either value — both live on the BATCH.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0036_cr038_br_met_136_rule_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="readimportbatch",
            name="write_mode",
            field=models.TextField(default="insert"),
        ),
        migrations.AddField(
            model_name="readimportbatch",
            name="cosigned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 W7 tasks 3 + 5 (CR-038 R2 · CR-036 (g) · BR-MET-127 · BR-MET-129 · OQ-042 closure · BR-MET-055)
# generated: 2026-08-26 by the CR-038 W7 one-rail lane
# checklist: A✔ B=deferred(schema only — behaviour is services/write_modes.py) C✔(tests/test_cr038_w7_write_modes.py) D=deferred(no-API-half — the columns are served by read_batch_dict, which already existed) E✔(the stage-1 control lands in the same lane's frontend commit) F✔ G✔ H=deferred(PO 2026-08-09 — HUMAN-REVIEW-PENDING, ledger row written by this lane)
# exceptions: the OQ-042 co-sign TOGGLE half is NOT built — its home is the S64 settings document owned by a concurrent lane; filed as DEF-815 rather than stubbed silently
# gates: see the lane report
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
