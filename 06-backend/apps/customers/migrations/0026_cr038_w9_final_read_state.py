# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 Amendment 2 · W9 task 4 — the move-out settlement's
#           how-obtained flag: *"the how-obtained flag (taken / due /
#           estimated) lands on `move_out_settlement` (B18 draws it, no column
#           carries it)"*.
# Rules:    BR-CUS-030 (`closed_at` IS the move-out; the flag is derived in
#           the same transaction) · BR-CUS-021/BR-MET-128 (the final read the
#           flag describes commits through metering's event door) · TC-MVO-7
#           (asserted the ABSENCE this column closes) · CLAUDE.md rule 1 (no
#           data pass — column only)
# Tests:    06-backend/tests/test_w9_event_reads.py
# ───────────────────────────────────────────────────────
"""customers 0026 — `accounts.final_read_state` (taken / due / estimated).

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-26 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). ⚠ The G7 ledger row is OWED: this lane may not edit
12-governance/ from its isolated worktree — FLAGGED in the W9 lane report.

WHY THE COLUMN IS ON `accounts` AND NOT ON A SETTLEMENT TABLE
-------------------------------------------------------------
There is no settlement table to put it on. `MoveOutSettlement` says so itself:
*"Nothing in here is stored. There is no `final_settlements` table"* — the
settlement is a pure derivation riding API responses and audit rows. The ONE
durable row a move-out has is the account (`closed_at` IS the move-out date,
BR-CUS-030), so the flag lives beside `closed_at`, written only by
`services.move_out` in the same transaction as the close.

NO BACKFILL, DELIBERATELY. Every existing close predates the event-read door,
so no historical settlement's final read can be honestly classified — NULL is
the truth ("not recorded at close"), and `move_reads` serves it as its own
narrowed absence (`final_read_state_not_recorded`) rather than guessing.

REVERSIBLE. Dropping the column returns the FINAL READ cell's `estimated`
state to the TC-MVO-7 absence; nothing else reads it.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0025_br_cus_107_disconnected_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="final_read_state",
            field=models.TextField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 W9 task 4 (BR-CUS-030 · BR-CUS-021 · BR-MET-128 · TC-MVO-7)
# generated: 2026-08-26 by the CR-038 W9 event-reads lane
# checklist: A✔ B=deferred(schema only — behaviour is services.move_out + move_reads) C✔(tests/test_w9_event_reads.py) D=deferred(rides the existing move-out route) E=deferred(same lane's frontend commits) F✔ G✔ H=deferred(PO 2026-08-09 — HUMAN-REVIEW-PENDING, ledger row OWED)
# exceptions: G7 ledger row + B2 §2 write-back OWED (worktree may not edit 12-governance/ or 04-docs/) — FLAGGED in the lane report
# gates: MEASURED 2026-08-26 by the W9 finishing lane, not claimed — `pytest` over the lane's fourteen suites (test_w9_event_reads · test_w9_reads_seam · test_us_cus_004_005_move_in_out · test_us_cus_004_move_in_race · the four W5 move suites · test_def_035_move_out_guard_wired · the three W7 transfer/disconnect/cut suites · test_w6_connections · test_po_20260812_backbill_segment_estimate) **332 passed, 7 skipped, 1 xfailed in 464.41s** · the estimation suites this lane's `estimation.py` reorder touches (test_us_met_014_estimation + test_cr014_round3_worked_examples) **28 passed** · frontend `vitest` over `src/features/customers` **562 passed, 1 skipped, 37 todo (31 files)** and the six suites this lane wrote or amended **115 passed** · `tsc --noEmit` clean · `eslint` clean · G31 **PASS, 0 undeclared class(es) at baseline 0** (the new capture file is BORN Route B) · G40 **PASS at baseline 1** · G13 **PASS** · G32 **PASS, 0 unresolved** — it was at 8 and every one was this lane's door, fixed here · G14 218→**217**, so this lane contributes 0 of the 22 above its 195 baseline · G27 537, G15 1114, G28 77 and G33 12 all UNMOVED by this lane. REPORTED rather than smoothed: `run_gates.py` is 27 PASS / 16 FAIL overall and **every remaining failure names another lane's file or a pre-existing ratchet** — G1/G3/G7/G8/G10/G12/G26/G29 among them; the one row that named this lane, G11's missing `gates:` trailer, is what this line closes.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
