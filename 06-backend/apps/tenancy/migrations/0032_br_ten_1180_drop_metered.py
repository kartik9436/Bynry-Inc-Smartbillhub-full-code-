# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-2409 · DEF-3230 — see 0030 for the full trace. This drops the
#           boolean the three-value column replaced.
# Rules:    BR-TEN-1180 (SUPERSEDES BR-RAT-081's two-state declaration) ·
#           CLAUDE.md law 14 (why this is not part of 0031)
# Tests:    06-backend/tests/test_br_ten_1180_billing_basis.py
# ───────────────────────────────────────────────────────
"""tenancy 0032 — drop `tenant_services.metered`, and nothing else.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-02 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

⚠ **SCHEMA ONLY, AND THAT IS THE RULE RATHER THAN THE STYLE.** `0031` writes
every row of `tenant_services`; this alters the table. On PostgreSQL those two
acts cannot share a transaction — the FKs on this table are `DEFERRABLE INITIALLY
DEFERRED`, so the writes queue trigger events that are not flushed until COMMIT,
and the ALTER is refused with *"cannot ALTER TABLE … because it has pending
trigger events"*. Measured on 16.13; invisible on the SQLite suite (law 14).

WHY THE COLUMN GOES RATHER THAN STAYING ALONGSIDE
--------------------------------------------------
PO ruling 2026-09-02, verbatim: *"we are in beta stage - so no real utility is
actually onboarded yet - so there is no real data yet - hence you can fix it; I
will delete the DB and relaunch"*. Keeping both would leave two columns that can
disagree, and the whole defect is a reader getting a confident two-state answer
about a three-state fact.

**NOTHING IN THE PRODUCT LOSES A READER.** `TenantService.metered` survives as a
read-only Python property equal to `billing_basis == "metered"`, so the ~30 call
sites across ten backend files that ask `BR-RAT-081`'s question — *is there a
register?* — are untouched. What cannot survive is a WRITE or a FILTER, and there
were exactly two of those; both moved with the column and both argued the choice
in their own docstrings.

REVERSIBILITY
--------------
Reversing re-adds `metered` with its original default of `TRUE`, and `0031`'s
own reverse then fills it from `billing_basis`. The order Django unwinds them in
is what makes that work: this migration first (the column exists again), then
`0031` (the values go back into it). Neither one both writes and alters.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("tenancy", "0031_br_ten_1180_backfill"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="tenantservice",
            name="metered",
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2409@billing-basis — see 0030's trailer for the full authority list
# generated: 2026-09-02 by the billing-basis lane (DEF-2409)
# checklist: A✔ B✔ C✔ D✔ E=deferred(the S8 control is a sibling lane's, built against the same contract) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: applied FORWARD and REVERSE against a REAL PostgreSQL 16.13 over three
#         planted rows, with the per-basis counts recorded at both ends
# exceptions: NO CHECK CONSTRAINT is added in place of the boolean — the
#         vocabulary is validated in the service against `models.BILLING_BASES`,
#         this table's own convention for all six comparable TEXT columns
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
