# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 Amendment 2 · W9 task 1 — the metering write door for EVENT
#           READS (move-in · move-out · transfer · disconnect · new connect).
# Rules:    BR-MET-128 (PO 2026-08-26, verbatim: "it will be as per event -
#           bascially we will ahve to create an record in reading that such
#           reading ahs been colelcted - and it is generated due to that
#           event; + plus the user") · BR-CUS-021 (reads commit through
#           metering's own append-only service) · CLAUDE.md rule 4 spirit /
#           BR-MET-016 (append-only: the stamp is written AT INSERT, never by
#           a later UPDATE) · CLAUDE.md rule 1 (no data pass touches rows here
#           — columns only, so no tenant predicate is needed)
# Tests:    06-backend/tests/test_w9_event_reads.py
# ───────────────────────────────────────────────────────
"""metering 0032 — `event_context` on `meter_reads` and `read_import_batches`.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-26 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). ⚠ The G7 ledger row is OWED: this lane works in an isolated
worktree and may not edit 12-governance/09-human-review-ledger.md — the row is
FLAGGED in the W9 lane report for the merging session's central write-back,
exactly as the B2 §2 seam rows are.

WHY TWO COLUMNS AND NOT ONE
---------------------------
BR-MET-128 puts the EVENT on the committed READ. But a committed `meter_reads`
row accepts exactly one lawful UPDATE — the supersede pair (B2 r8) — so the
stamp must be present AT INSERT, and the insert happens inside the shared
`_post_row` pipeline, which reads everything batch-shaped off the BATCH
(`source_detail`, `uploaded_by` already travel this way). So the event lands on
the batch while it is STAGED (mutable — BR-MET-012/017), and `_post_row` copies
it onto every read it posts. One write path, no committed-row update, and the
five ordinary batch doors leave both columns NULL.

The USER half of BR-MET-128 adds NO column: an event batch's `uploaded_by` is
the acting user and `_post_row` already stamps it onto the read as
`imported_by`. Only the event had nowhere to live.

NO BACKFILL, DELIBERATELY. No historical read was collected by a wizard event —
the wizards refused `initial_reads`/`final_reads` payloads until this change
(BR-CUS-021's unbuilt half, measured in CR-038 Amendment 2) — so NULL on every
existing row is the truth, not a gap.

REVERSIBLE. Dropping the columns loses the event stamps and returns the wizards
to stating the absence; nothing else depends on them.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0034_rls_cr038_w6_submeter_reconciliation"),
    ]

    operations = [
        migrations.AddField(
            model_name="meterread",
            name="event_context",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="readimportbatch",
            name="event_context",
            field=models.TextField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 W9 task 1 (BR-MET-128 · BR-CUS-021 · BR-MET-129)
# generated: 2026-08-26 by the CR-038 W9 event-reads lane
# checklist: A✔ B=deferred(schema only — behaviour is services.commit_event_reads) C✔(tests/test_w9_event_reads.py) D=deferred(no-API-half — the door is a seam, not a route) E=deferred(the wizard halves land in the same lane's frontend commits) F✔ G✔ H=deferred(PO 2026-08-09 — HUMAN-REVIEW-PENDING, ledger row OWED per the module docstring)
# exceptions: the G7 ledger row and the B2 §2 interface rows are OWED — this worktree may not edit 12-governance/ or 04-docs/; both are FLAGGED in the lane report
# gates: MEASURED 2026-08-26 by the W9 finishing lane, not claimed — `pytest` over the lane's fourteen suites (test_w9_event_reads · test_w9_reads_seam · test_us_cus_004_005_move_in_out · test_us_cus_004_move_in_race · the four W5 move suites · test_def_035_move_out_guard_wired · the three W7 transfer/disconnect/cut suites · test_w6_connections · test_po_20260812_backbill_segment_estimate) **332 passed, 7 skipped, 1 xfailed in 464.41s** · the estimation suites this lane's `estimation.py` reorder touches (test_us_met_014_estimation + test_cr014_round3_worked_examples) **28 passed** · frontend `vitest` over `src/features/customers` **562 passed, 1 skipped, 37 todo (31 files)** and the six suites this lane wrote or amended **115 passed** · `tsc --noEmit` clean · `eslint` clean · G31 **PASS, 0 undeclared class(es) at baseline 0** (the new capture file is BORN Route B) · G40 **PASS at baseline 1** · G13 **PASS** · G32 **PASS, 0 unresolved** — it was at 8 and every one was this lane's door, fixed here · G14 218→**217**, so this lane contributes 0 of the 22 above its 195 baseline · G27 537, G15 1114, G28 77 and G33 12 all UNMOVED by this lane. REPORTED rather than smoothed: `run_gates.py` is 27 PASS / 16 FAIL overall and **every remaining failure names another lane's file or a pre-existing ratchet** — G1/G3/G7/G8/G10/G12/G26/G29 among them; the one row that named this lane, G11's missing `gates:` trailer, is what this line closes.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
