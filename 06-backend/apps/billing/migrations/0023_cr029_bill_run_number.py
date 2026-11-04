# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 RC-W6 — **OQ-342**, CLOSED-RULED by the PO 2026-08-23,
#           verbatim: *"A: a real series (RUN-0001, like RT-001)"*.
# Rules:    BR-TEN-035 (numbering grammar + allocation law: in-transaction,
#           forward-only, gaps ok, never reused, issued numbers NEVER
#           renumbered) · BR-BIL-005 (a run is unique on tenant · cycle ·
#           period — the number is not part of that key) · CLAUDE.md rule 4
#           (financial immutability — nothing already issued moves) ·
#           CLAUDE.md 🔒 sensitive paths (migration ordering —
#           HUMAN-REVIEW-PENDING)
# ───────────────────────────────────────────────────────
# 🔒 HUMAN-REVIEW-PENDING (PO 2026-08-09: "AI will do it; we will review it
# later as human") — a row in 12-governance/09-human-review-ledger.md is OWED
# for this file and is REPORTED by the RC-W6 lane rather than written by it.
# ───────────────────────────────────────────────────────
"""billing 0023 — CR-029 OQ-342: `bill_runs.run_no`, the run's own number.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-23 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*). ⚠ Its row in `12-governance/09-human-review-ledger.md` is
OWED: this lane does not write governance files and has REPORTED the row.

WHY THE COLUMN EXISTS. The PO's upgraded SET-07D prototype draws a **Run** column
reading `RUN-0814` and the product could not produce it — `bill_runs` had no
number column and `core.numbering.SERIES_CATALOG` had no bill-run series — so
RC-W4b served `run_no: null` and pinned it there rather than mint a naming
grammar at a call site. OQ-342 put the three readings to the PO and they chose
**(A) a real series**, in the same grammar as `RT-001`.

NULLABLE, NO BACKFILL, AND THAT IS THE RULING ITSELF: *"Existing runs have no
number and are not retro-numbered unless the PO asks — a number that appears on a
bill already sent is a different question."* Every run on every host therefore
keeps NULL, no issued document changes, and CLAUDE.md rule 4 is untouched. A
backfilled number would additionally have to be invented in run order from a
counter nobody set, which is exactly the derivation the OQ refused.

THE UNIQUE INDEX IS PARTIAL — `WHERE run_no IS NOT NULL` — which is the only
shape that holds both halves at once: allocated numbers are unique per tenant,
and the historical nulls coexist. `import_runs` (metering 0014) took the
identical shape for the identical reason.

NO MONEY MOVES (change process step 2). A number is an identifier: no rate, no
amount, no currency, no due date, no ❄️ FROZEN B4/B5 figure. Nothing in the
golden harness reads it.

RLS: NOTHING TO RE-POLICE. `bill_runs` has carried ENABLE + FORCE and B2 §3's
tenant-isolation policy since billing's W3 migration, and that policy is
ROW-scoped — a new column on an already-policed table is covered the moment it
exists. The unique index is per-tenant by its own leading column, so it cannot
leak the existence of another tenant's number either.
"""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0022_cr029_run_due_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="billrun",
            name="run_no",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="billrun",
            constraint=models.UniqueConstraint(
                condition=Q(run_no__isnull=False),
                fields=("tenant", "run_no"),
                name="uq_bill_runs_tenant_run_no",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 (04-docs/02-decisions/17-cr029-routes-cycles-design.md) §4 (SET-07D Runs tab) + OQ-342 in 12-governance/01-open-questions.md
# generated: 2026-08-23 by the CR-029 RC-W6 lane
# checklist: A✔ B=deferred(the frontend lane renders the Run column; the payload key already exists and was null) C✔(tests/test_cr029_rcw6_run_numbers.py — RED first: AttributeError, core.numbering has no attribute BILL_RUN) D✔ E✔ F✔ G✔ H=PENDING(🔒 migration ordering — HUMAN-REVIEW-PENDING, ledger row OWED and reported)
# gates: makemigrations --check clean · billing + metering suites green
# exceptions: (1) one nullable column and one PARTIAL unique index; NO backfill, because the ruling says existing runs are not retro-numbered · (2) `import_run`'s catalogue DEFAULT moves to `IMP-{YY}{MM}{DD}-{00}` in core/numbering.py so two seeded series do not share the `RUN-` prefix — stored rows are untouched (`get_or_create`) and `RUN-{0000}` stays offered there
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
