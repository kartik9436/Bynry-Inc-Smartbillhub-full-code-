# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C5 / task T15 — the allowance for doubtful debts. PO ruling
#           2026-09-03, over a recommendation to defer.
#           Screens: S56 (the chart), S42 (the close checklist)
# Rules:    BR-LED-795 (NEW — the allowance is a BALANCE adjusted to a target,
#           never an accrual that reverses) · BR-PAY-020 (write-off posting —
#           NARROWED, not superseded: direct while the policy is off) ·
#           BR-LED-005 (an accrual auto-reverses on day 1 — and this is
#           deliberately NOT one) · CLAUDE.md rule 5 · rule 2 · rule 4
# Tests:    06-backend/tests/test_cr060_t15_allowance.py ·
#           06-backend/tests/test_us_led_005_gl_designations.py (the CHECK)
# ───────────────────────────────────────────────────────
"""ledger 0015 — designation SEVENTEEN, `allowance_doubtful_accounts`.

HUMAN-OWNED (the chart of accounts decides WHICH GL account money lands in, a
CLAUDE.md 🔒 sensitive path, and migration ordering is another).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human
sign-off.

WHAT THIS UNBLOCKS
-------------------
`1290 Allowance for doubtful accounts` was DELIBERATELY not seeded, and
`apps/ledger/chart.py` judgment 3 said why in its own words: *"seeding an
allowance account offers a utility an accounting policy this product does not
implement, on a signed write-off path. T15 owns it."*

T15 is ruled. PO 2026-09-03, verbatim: *"Why I recommended deferring it. Three
reasons: let's do this"* — the heading of the argument for deferring, quoted
back and chosen against. So the policy is implemented (`apps/ledger/
allowance.py`) and the pointer it resolves through has to exist in the CHECK
before any account can carry it.

`ledger/0003` predicted this cost and `0006`, `0009` and `0014` have each paid it
once: Django's serializer INLINES `chart.GL_DESIGNATIONS` into the CHECK, so the
database does not follow that tuple. One more constant without a migration is
accepted by Python and refused by PostgreSQL.

WHAT DOES *NOT* LAND HERE, AND BOTH ABSENCES ARE DELIBERATE
------------------------------------------------------------
**NO ACCOUNT IS CREATED BY THIS MIGRATION.** `1290` is minted by
`services.ensure_allowance_account`, for hard-won law 4's reason — a migration
reaches every host and a seed edit reaches none of the ones that already exist —
AND for a second reason this designation has and the other sixteen do not:
**the account appears when a tenant SWITCHES THE POLICY ON, never before.** Most
utilities under 3,000 connections are not audited and never book an allowance;
that was one of the three reasons the PO was shown and chose against, and it is
still true of the tenants who do not turn it on. Their chart stays at 125.

**NO CHANGE TO THE WRITE-OFF PATH.** BR-PAY-020's `DR write-off / CR AR` is
unchanged for every tenant with the policy off, which today is all of them
(`allowance_for_doubtful_accounts_enabled` defaults to false — hard-won law 3,
the unsafe option is the one you type). The switch lives in
`apps/payments/ledger_seam.post_write_off` and is proved by a case that fails
when a write-off and an estimate both hit `6900`.

WHAT AN OPERATOR MUST KNOW
---------------------------
This drops and re-adds a CHECK constraint on `ledger_accounts`, tens of rows per
tenant. PostgreSQL revalidates against existing rows, every one of which already
satisfies it because the set only GREW. No row is read, written or deleted, and
nothing here touches money.
"""

from django.db import migrations, models

#: The full set AFTER this migration. Spelled out rather than imported from
#: `apps.ledger.chart` for the reason `ledger/0009` gives and `0014` repeats: a
#: migration must describe the database as it was at the moment it was written,
#: and a later edit to that tuple must produce a NEW migration rather than
#: silently rewriting the meaning of this one.
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
    "discount_contra_revenue",
    "accrued_expenses",
    "depreciation_expense",
    "accumulated_depreciation",
    "allowance_doubtful_accounts",
)

#: The sixteen, exactly as `ledger/0014` left them. The reverse path restores
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
        ("ledger", "0014_cr060_t7b_t7f_period_matching_designations"),
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
# packet: CR-060 C5 + task T15 (12-governance/11-change-requests.md §7 · §12) ·
#         12-governance/02-decision-log.md 2026-09-03 (the PO ruling, with the
#         three reasons for deferring recorded so the trade is on file) ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-795 (NEW) ·
#         04-docs/02-decisions/05-golden-tests.md B5 line 74 (❄️ FROZEN — NOT
#         edited) · CLAUDE.md hard rules 1, 2, 4, 5, 7
# generated: 2026-09-03 by the CR-060 T15 lane
# checklist: A✔ B✔ C✔ D=deferred(no API half — a migration) E=deferred(no UI
#         half; switching the policy on is the S71 Finance-controls page, which
#         this change adds five parameters to) F✔ G✔ H=deferred(PO 2026-08-09 —
#         🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: PROVED RED FIRST — before this migration,
#         tests/test_cr060_t15_allowance.py failed with
#         `ValueError: 'allowance_doubtful_accounts' is not one of the GL
#         designations the Product Owner has ruled`, raised by
#         apps/ledger/selectors.gl_account_for_designation. That guard was RIGHT
#         to fire and is the reason this migration exists rather than one bare
#         constant being added
# exceptions: (1) THE ACCOUNT IS NOT CREATED HERE and is not in the provisioning
#         seed either — `services.ensure_allowance_account` mints it when a
#         tenant switches the policy on, so a utility that never books an
#         allowance is never offered one and the chart stays at 125 for them ·
#         (2) `1290` is signed=False: the PO ruled the POLICY, and a policy
#         ruling is not a finance signature on a chart row (the same reading
#         UTILITY_BOOKS_CHART's 67 rows carry) · (3) no new RLS policy and no new
#         db/rls_*.sql: this creates no table and `ledger_accounts` is already
#         ENABLE+FORCE under the signed B2 §3 policy from ledger/0002 ·
#         (4) DESIGNATIONS_AFTER is spelled out rather than imported, deliberately
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
