# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-019 (the budget settle-up line that needs this account) ·
#           US-LED-005 (the chart and its designations)   Screens: S30 · S41
# Rules:    BR-BIL-017 (budget billing) · BR-LED-014 (the GL mapping page where a
#           human claims a designation) · CLAUDE.md rule 5 (only the ledger
#           posting service writes journal lines) · rule 2 (money NUMERIC(18,6))
# Tests:    06-backend/tests/test_us_bil_019_budget_bill.py (tc5 — the refusal
#           while the designation is unclaimed) ·
#           06-backend/tests/test_us_led_005_gl_designations.py (the CHECK)
# ───────────────────────────────────────────────────────
"""ledger 0006 — `budget_variance` becomes the TWELFTH GL designation.

HUMAN-OWNED (the chart of accounts decides WHICH GL account money lands in, a
CLAUDE.md 🔒 sensitive path, and migration ordering is another).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-15 under the PO ruling of 2026-08-09.
Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded
human sign-off.

WHAT RULING THIS IMPLEMENTS, IN THE PO'S OWN WORDS
---------------------------------------------------
2026-08-15, verbatim: *"Create seperate account"* — OQ-142, recorded in
12-governance/02-decision-log.md. Three options were put to them and this is the
third: leave the budget variance in receivables; use the already-signed
`unbilled_ar` 1210; or mint it an account of its own.

WHY, WITH THE ❄️ FROZEN WE-8 FIGURES
------------------------------------
A budget-billing month recognises **292.87** of revenue and asks the customer
for **242.00**. The **50.87** left standing is not revenue (already counted),
not tax (already taken) and not an arrear — the customer paid exactly what we
asked them for, and the late fee and dunning ladder are already stopped from
reaching them (OQ-140).

With nowhere of its own to sit, that 50.87 landed in the **1–30 ageing bucket**,
where it is indistinguishable from a delinquency on every AR ageing report and
DSO trend the product prints. Across a year the balance runs
**−50.87 → −40.27 → +2.98**, so it can finish as money the utility OWES while
filed under money it is owed. Neither of the cheaper options fixes that:
receivables IS the problem, and `unbilled_ar` also carries month-end accruals,
so its balance would mix two facts and a reader could trust neither.

⚠ THE DESIGNATION IS NOT THE ACCOUNT, AND ONLY ONE OF THEM LANDS HERE
---------------------------------------------------------------------
This migration adds the DESIGNATION — a product-code change under a PO ruling.
It does **not** add an account, and it seeds nothing.

The ACCOUNT is an addition to **B5 line 74, which is ❄️ FROZEN and finance-signed
2026-08-08**, and needs a **finance re-sign via HUMAN-GUIDE §6** — the same route
the 4160/4170 revenue codes, the separate concession account and the $8.31 tax
addendum are queued on. **B5 is never edited inline.**

So until a human claims this designation on the GL mapping page,
`apps/billing/posting_seam.budget_variance_account_id` **refuses by name**. That
is deliberate and it is not a stub: the question is CLOSED, and what is pending
is a signature, not a decision. Posting the variance to either declined option
would put money in a bucket the ruling exists to empty. Safe to ship refusing —
a settle-up fires at TRUE-UP, six or twelve months after enrolment, so no tenant
reaches it in the first months after deploy.

WHY THIS IS A MIGRATION AT ALL
------------------------------
`ledger/0003` predicted this exact cost in its own exceptions block: *"the
DESIGNATION VALUES are inlined into the CHECK by Django's own serializer, so a
change to apps/ledger/chart.GL_DESIGNATIONS needs a NEW migration — a twelfth
designation therefore cannot arrive without a migration on live tenant data,
which is the cost the PO priced when ruling option A on OQ-110."* This is that
migration, and the prediction was exactly right.

**WHAT AN OPERATOR MUST KNOW.** This drops and re-adds a CHECK constraint on
`ledger_accounts`, a small table (a chart of accounts, tens of rows per tenant).
Postgres validates the new constraint against existing rows, all of which
already satisfy it — the set only grew — so the revalidation is trivially fast
and no row is read, written or deleted. Nothing here touches money.
"""

from django.db import migrations, models

#: The full set AFTER this migration. Spelled out rather than imported from
#: `apps.ledger.chart`: a migration must describe the database as it was at the
#: moment it was written, and a later edit to that tuple must produce a NEW
#: migration rather than silently rewriting the meaning of this one.
DESIGNATIONS_AFTER = (
    "accounts_receivable",
    "deposit_liability",
    "opening_clearing",
    "write_off",
    "minimum_bill_adjustment",
    "customer_credit_balance",
    "cash",
    "undeposited_funds",
    "unbilled_ar",
    "bank_fees",
    "deposit_interest_expense",
    "budget_variance",
)

#: The eleven, exactly as `ledger/0003` wrote them. The reverse path restores
#: this list — a migration that cannot be backed out of is one a deploy cannot
#: back out of.
DESIGNATIONS_BEFORE = DESIGNATIONS_AFTER[:-1]


def _check(designations):
    return models.CheckConstraint(
        condition=models.Q(
            ("designation__isnull", True),
            ("designation__in", designations),
            _connector="OR",
        ),
        name="ck_ledger_accounts_designation",
    )


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("ledger", "0005_partition_journal_lines_by_year"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="ledgeraccount",
            name="ck_ledger_accounts_designation",
        ),
        migrations.AddConstraint(
            model_name="ledgeraccount",
            constraint=_check(DESIGNATIONS_AFTER),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-019@0142a15 (sha1[:7] of the three authorities this slice was
#         authored from, newline-joined in order: the 2026-08-15 decision-log row
#         carrying the PO ruling "Create seperate account" · the OQ-142 row in
#         12-governance/01-open-questions.md · B5 line 74 in
#         04-docs/02-decisions/05-golden-tests.md, ❄️ frozen, which this ruling
#         adds a line to and which is therefore NOT edited here)
# generated: 2026-08-15 by the orchestrating session (OQ-142 ruling lane)
# checklist: A✔ B✔ C✔ D=deferred(no API half — a migration) E=deferred(no UI half; claiming the designation is the existing GL mapping page, BR-LED-014) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: PROVED RED FIRST — before this migration, tests/test_us_bil_019_budget_bill.py::tc5 failed with `ValueError: 'budget_variance' is not one of the eleven GL designations the Product Owner ruled on 2026-08-11 (OQ-110)`, raised by apps/ledger/selectors.py:162. That guard was RIGHT to fire and is the reason this migration exists rather than a bare constant being added
# exceptions: THE DESIGNATION IS ADDED; THE ACCOUNT IS NOT. Nothing is seeded
#         against it — the account is an addition to ❄️ frozen B5 line 74 and
#         needs a finance re-sign via HUMAN-GUIDE §6, so until a human claims the
#         designation `posting_seam.budget_variance_account_id` REFUSES BY NAME.
#         That refusal is asserted by a test rather than left to be discovered ·
#         no new RLS policy and no new db/rls_*.sql: this creates no table and
#         `ledger_accounts` is already ENABLE+FORCE under the signed B2 §3 policy
#         from ledger/0002; a second policy would shadow the signed one ·
#         DESIGNATIONS_AFTER is spelled out rather than imported from
#         apps.ledger.chart, deliberately — a migration must describe the schema
#         at the moment it was written, and importing a live tuple would let a
#         later edit silently rewrite what this migration means
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
