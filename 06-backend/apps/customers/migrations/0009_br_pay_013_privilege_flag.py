# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-009 (the bounce) · US-CUS-008 (the S21 account header the
#           flag renders on)   Screens: S21 · S33 · S34
# Rules:    BR-PAY-013 (NSF: … nsf_count++; N NSFs (default 2, config) →
#           cash-only/no-autopay flag) · B2 Addendum r12 #12 (`accounts.nsf_count`
#           + cash-only/no-autopay privilege flag) · B2 r14 #5 (`nsf_privilege_n`)
#           · CLAUDE.md rule 1 (the accounts RLS policy already covers this
#           column — a column inherits its table's policy)
# ───────────────────────────────────────────────────────
"""customers 0009 — the BR-PAY-013 privilege flag (DEF-070).

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-15 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
WHY THIS COLUMN DID NOT EXIST, AND WHAT ITS ABSENCE COST
════════════════════════════════════════════════════════════════════════════
B2 Addendum r12 #12 reads, verbatim: *"NSF fields: `accounts.nsf_count` +
cash-only/no-autopay privilege flag [BR-PAY-013]"*. **Only the first half was
ever built.** `apps/customers/models.Account` carried `nsf_count` and no flag of
any kind, so BR-PAY-013's second sentence — *"N NSFs (default 2, config) →
cash-only/no-autopay flag"* — had nowhere to land and **the second bounce did
nothing at all**. J12 step 4 turns on exactly this: two returned cheques, one
account, and at the tenant default N=2 the account goes cash-only and off
autopay. That step could not pass and nothing said so, because no NSF service
existed to reach for the flag and find it missing (DEF-070).

════════════════════════════════════════════════════════════════════════════
ONE BOOLEAN, AND THE THREE THINGS IT IS NOT
════════════════════════════════════════════════════════════════════════════
  * **It is not two flags.** The signed line names ONE — *"cash-only/no-autopay
    privilege flag"* — and two columns would let a row say cash-only-but-still-
    on-autopay, a state no rule describes and no screen could explain.
  * **It is not `autopay` turned off.** `accounts.autopay` is the customer's
    own ELECTION (BR-CUS-059). Flipping it here would destroy that election
    with nothing to restore when a staff member lifts the privilege flag, and
    the customer would have to re-enrol for a punishment that had ended. The
    flag is the enforcement and `apps.payments.autopay.is_enrolled` reads it.
  * **It is not a timestamp.** J12 step 6 asks the audit trail to reconstruct
    *"both bounces, both fees, the flag trip and any lift — who/when at each
    step"*, and that is `audit_log`'s job (hard rule 7). A `flagged_on` column
    would be a second, weaker copy of a trail that already exists.

NOT NULL DEFAULT false, so every existing account is unflagged the moment this
applies — which is the truth: no account has ever reached the threshold, because
until now nothing counted.

⚠ **NOTHING AUTO-CLEARS IT.** J12 step 6, verbatim: *"the cash-only flag REMAINS
— no rule auto-clears it; lifting it is an explicit staff config action,
audited"*. There is therefore no unset path in `record_nsf` and no scheduled
sweep anywhere. The LIFT is a staff action that has no story of its own yet and
is REPORTED rather than invented here — `apps/customers/services.record_nsf`
says so in its own docstring.

No RLS work is needed and none is done: a column inherits the policy of the
table it is added to, and `accounts` has carried `ENABLE + FORCE ROW LEVEL
SECURITY` since customers 0002. Stated rather than assumed, because "the policy
covers it" is exactly the kind of claim hard-won law 1 is about — the isolation
suite re-asks it.

Applied to a live PostgreSQL 16 cluster by this lane — see the lane report.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0008_rls_account_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="account",
            name="cash_only_no_autopay",
            field=models.BooleanField(default=False),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-009@be6fc76 (sha1[:7] of the three sources this defect fix was authored
#         from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md
#         Addendum r12 #12 + r14 #5 · 04-docs/05-modules/08-payments/02-business-rules.md
#         BR-PAY-013 · 08-qa/01-e2e/journeys/J12-nsf-life.md steps 4 and 6.
#         Raised as DEF-069 + DEF-070 in 12-governance/10-defect-log.csv)
# generated: 2026-08-15 by the seams lane (DEF-069 + DEF-070)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a migration) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migration ordering 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: makemigrations --check clean · migrate from empty on live PostgreSQL 16 · tests/test_us_pay_009_nsf.py
# exceptions: ONE boolean and not two (the signed line names one flag) · `accounts.autopay` is NOT flipped (it is the customer's election, BR-CUS-059 — the flag is the enforcement) · no `flagged_on` column (J12 step 6 puts the who/when in audit_log) · NO clearing path anywhere: nothing auto-clears it and the staff LIFT has no story yet, so it is reported and not invented
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
