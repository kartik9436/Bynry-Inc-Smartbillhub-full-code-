# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 RC-W1 task W1-T3 (B17 §3 D9 · §6 · §7) — the run's due-days
#           OVERRIDE. The cycle keeps bill day + due days as DEFAULTS.
# Rules:    D9, PO verbatim 2026-08-23 — *"when we configure Cycle we are
#           provideing default values; mostly it wil remain as it is but user
#           can over ride them during billing"* · BR-BIL-024 (due date = bill
#           date + the cycle's due-days) · BR-BIL-070 (the clerk's typed bill
#           date is stored and wins — the override this one completes) ·
#           BR-MET-009 (`due_days ≥ 0`) · CLAUDE.md rule 4 (nothing already
#           issued moves) · CLAUDE.md 🔒 sensitive paths (migration ordering —
#           HUMAN-REVIEW-PENDING)
# ───────────────────────────────────────────────────────
# 🔒 HUMAN-REVIEW-PENDING (PO 2026-08-09: "AI will do it; we will review it
# later as human") — a row in 12-governance/09-human-review-ledger.md is OWED
# for this file and is reported by the RC-W1 lane rather than written by it.
# ───────────────────────────────────────────────────────
"""billing 0022 — CR-029 D9: `bill_runs.due_days`, the run's override of the
cycle's default due-days.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-23 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*). ⚠ Its row in `12-governance/09-human-review-ledger.md` is
OWED: the RC-W1 lane does not write governance files and has REPORTED the row
for the CR-029 close-out to add.

WHY THE COLUMN EXISTS AT ALL. D9 has two halves and only one of them was
buildable: `bill_runs.bill_date` has carried the clerk's typed bill date since
migration 0011 (BR-BIL-070), and the DUE terms had nowhere to go — so *"user
can over ride them during billing"* was half a ruling with half a schema.

NULLABLE, NO DEFAULT, AND THAT IS THE WHOLE SAFETY ARGUMENT. Every run that
exists today gets NULL, NULL means *nobody overrode the terms on this run*, and
`runs.effective_due_days(None, cycle.due_days)` returns the cycle's value — the
identical figure `issue._due_terms_for` returned before this migration. **No
already-issued due date can move** (CLAUDE.md rule 4), and
`tests/test_cr029_rcw1_due_terms.py` proves it over a table of the pre-CR cases
with the expected dates computed by hand rather than from the code under test.

A NOT NULL column with a backfilled default would have been the dangerous
version: it would have to invent a due-days for every historical run, and the
only value available to invent is the cycle's — which then STOPS being an
override and starts being a copy that drifts.

NO MONEY MOVES (BR-MET-078 · change process step 2). Due-days is DATE
arithmetic, not an amount: no rate, no currency, no ❄️ FROZEN B4/B5 figure is
touched, so no finance re-sign is triggered. The one money-adjacent property —
that a due date never precedes its bill date — is BR-MET-009 and is enforced by
`issue.derive_due_date`, which refuses a negative whichever column it came from.

RLS: NOTHING TO RE-POLICE. `bill_runs` has carried ENABLE + FORCE and the B2 §3
tenant-isolation policy since billing's W3 migration, and that policy is
ROW-scoped — a new column on an already-policed table is covered the moment it
exists.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0021_one_time_bill_runs"),
    ]

    operations = [
        migrations.AddField(
            model_name="billrun",
            name="due_days",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 (04-docs/02-decisions/17-cr029-routes-cycles-design.md) §3 D9 / §6 / §7 RC-W1 T3 + the CR-029 record in 12-governance/11-change-requests.md
# generated: 2026-08-23 by the CR-029 RC-W1 lane
# checklist: A✔ B=deferred(RC-W2-T2 owns the run wizard's override control) C✔(tests/test_cr029_rcw1_due_terms.py) D✔ E✔ F✔ G✔ H=PENDING(🔒 migration ordering — HUMAN-REVIEW-PENDING, ledger row OWED and reported)
# gates: makemigrations --check clean · billing + metering suites green
# exceptions: none — one nullable column, no backfill, no data touched
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
