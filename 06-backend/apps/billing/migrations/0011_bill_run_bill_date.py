# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-001 §5 (S31 step 1 — *"Bill date (shows on statement)"*, the
#           field that has been submitted and discarded since the wizard
#           shipped)
#           Screens: S31 (step 1) · S31.2 (what the run then prices at)
# Rules:    BR-BIL-070 (the bill date a clerk types is STORED and USED — PO
#           ruling 2026-08-11, OQ-122 option A) · BR-BIL-024 (due date = bill
#           date + the cycle's due-days) · BR-RAT-007 (a bill prices on the
#           tariff version in force at the SERVICE date) · BR-TEN-043 (event
#           time is an ARGUMENT — a typed date qualifies, a clock never does) ·
#           BR-BIL-050 (a run is resumable from S30 at any point, so the date
#           cannot live in the browser)
# ───────────────────────────────────────────────────────
"""billing 0011 — `bill_runs.bill_date`, the column the clerk's entry lands in.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-11 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

WHAT IT IS AND WHY IT EXISTS
----------------------------
One nullable `date` column. PO ruling 2026-08-11 closing OQ-122, option A,
verbatim:

    "A Store what they type and use it"

S31 step 1 asks for a bill date. `runCreateBody` in
`07-frontend/src/features/billing/BillRunWizard.tsx` has been POSTing it since
the wizard shipped. `bill_runs` had no column for it (B2 §2 + r10 #7: cycle,
period, status, bill_type, idempotency_key, parent_run, scope_services,
run_by), so `POST /billing/runs` accepted the field and dropped it on the
floor, and every bill in the run priced at the CYCLE's date instead. Nothing on
screen said so.

**Worked, and it is a two-day error in a due date** — the case put to the PO:
cycle 08-A is dated **1 Aug** with 21 due-days; the clerk types **3 Aug**
because the batch slipped. Today every bill prices at 1 Aug tariffs and prints
**due 22 Aug**. With this column the run prices at **3 Aug** and prints **due
24 Aug**.

WHY NULLABLE, AND WHY THAT IS NOT A HEDGE
-----------------------------------------
NULL means *nobody typed a bill date on this run* — a real fact, not a missing
value. `runs.effective_bill_date` reads it as exactly that and falls back to
the cycle's own `bill_date`, which is what every run did before this migration.

NOT NULL was considered and rejected: it needs a value for the rows that
already exist, and the only value available to invent is a clock reading.
BR-TEN-043 and gate G6 both ban a clock in this path precisely because a run
re-executed in 2031 must reach the same tariff version it reached today.

NO DEFAULT, for the same reason — a database-side default is a value nobody
typed, wearing the clothes of a value somebody did.

IMMUTABILITY AND RLS
--------------------
`bill_runs` carries NO immutability trigger and is not meant to: hard rule 4
freezes ISSUED invoices, invoice lines, payments and journal lines, and a run
row is a work record that legitimately changes status through its five phases
(BR-BIL-050). `0002_rls_w3_and_immutability` installs triggers on `invoices`
and `invoice_lines` only; `bill_runs` appears in that migration solely in the
RLS list. Checked in the migration rather than assumed.

RLS needs no new operation. `bill_runs` has carried
`bill_runs_tenant_isolation` under ENABLE + FORCE since `0002` (the signed
B2 §3 template in `db/rls_billing_w3.sql`), and a policy is per TABLE, not per
column — a column added to a protected table is protected.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0010_invoice_line_tax"),
    ]

    operations = [
        migrations.AddField(
            model_name="billrun",
            name="bill_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-001@e9d5a48 (this file's own sources, in order:
#         12-governance/02-decision-log.md 2026-08-11 row "THE BILL DATE A CLERK
#         TYPES IS STORED AND USED (OQ-122 CLOSED, option A)" ·
#         12-governance/01-open-questions.md OQ-122 (CLOSED) ·
#         04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-070 +
#         BR-BIL-024 · 04-docs/02-decisions/02-database-design-brief.md §2
#         billing + Addendum r10 #7)
# generated: 2026-08-11 by Eng-Lead (OQ-122 typed-bill-date lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI — the field already exists on S31 and already POSTs) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: `python manage.py makemigrations --check` → "No changes detected";
#         pytest tests -m "not golden and not isolation" green; GT-8 green
# exceptions: (1) NULLABLE with NO default — NULL is the fact "nobody typed one
#         on this run" and the cycle's date is then used. NOT NULL would need a
#         value invented for existing rows and the only one available is a
#         clock (BR-TEN-043 / G6) · (2) no immutability trigger touched:
#         `bill_runs` has none and correctly has none — hard rule 4 freezes
#         issued financial records, and a run row moves through five phases by
#         design (BR-BIL-050); verified against 0002, which lists `bill_runs`
#         under RLS only · (3) no RLS operation: a policy is per table and
#         `bill_runs` has carried one under FORCE since 0002 · (4) NOT applied
#         to a live Postgres cluster by this lane — no cluster was reachable in
#         this environment (DEF-054); `makemigrations --check` is clean and the
#         suite runs on sqlite. Stated rather than implied, because 0010's
#         trailer records a live-cluster proof and this one cannot
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
