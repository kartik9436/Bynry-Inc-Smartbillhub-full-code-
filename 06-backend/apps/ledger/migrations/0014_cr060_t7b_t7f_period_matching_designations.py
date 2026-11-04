# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C17 / task T7b (accrue unpaid supplier costs at close) and
#           CR-060 C20 / task T7f (post depreciation).
#           Screens: S42 (the close checklist), S56 (the chart)
# Rules:    BR-LED-006 (the close checklist — AMENDED 2026-09-02, a seventh
#           item) · BR-LED-792 (NEW — period matching, the cost side) ·
#           BR-LED-793 (NEW — how depreciation is posted) · BR-LED-005 (an
#           accrual auto-reverses on day 1) · BR-LED-028 (capture creates no
#           payable — untouched, and the reason this accrual is lawful is that
#           it drains itself) · CLAUDE.md rule 5 · rule 2
# Tests:    06-backend/tests/test_cr060_t7b_unpaid_cost_accrual.py ·
#           06-backend/tests/test_cr060_t7f_depreciation.py ·
#           06-backend/tests/test_us_led_005_gl_designations.py (the CHECK)
# ───────────────────────────────────────────────────────
"""ledger 0014 — designations FOURTEEN, FIFTEEN and SIXTEEN.

HUMAN-OWNED (the chart of accounts decides WHICH GL account money lands in, a
CLAUDE.md 🔒 sensitive path, and migration ordering is another).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-02 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human
sign-off.

WHAT THIS UNBLOCKS, AND WHY IT IS A MIGRATION AT ALL
-----------------------------------------------------
Two month-end postings CR-060 calls MUST and SHOULD each need a counter-account
the product had no pointer to:

  * `accrued_expenses` — C17's credit. At close the utility owes its suppliers
    for commodity it has already SOLD, and today that cost does not enter the
    books until the day it is PAID. The accrual debits each purchase's own cost
    account and credits this one; the day-1 mirror (BR-LED-005) drains it.
  * `depreciation_expense` / `accumulated_depreciation` — C20's pair.
    *"Depreciation is computed and shown on screen and posts nowhere"*
    (CR-060 §4).

`ledger/0003` predicted the cost and `0006` and `0009` have each paid it once:
Django's serializer INLINES `chart.GL_DESIGNATIONS` into the CHECK, so the
database does not follow that tuple. Three more constants without a migration
are accepted by Python and refused by PostgreSQL.

WHAT LANDS IN THE CHART, AND WHAT DELIBERATELY DOES NOT
--------------------------------------------------------
**TWO of the three designations are placed on accounts that ALREADY EXIST** —
`2100 Accrued expenses` and `1730 Accumulated depreciation — meters`, both
`chart.UTILITY_BOOKS_CHART` rows the PO ruled into existence on 2026-09-01/02
from their own 111-row reference chart. Nothing is renamed, retyped or
re-signed: a designation is a pointer AT an account.

**ONE new account is minted — `5700 Depreciation expense`, `signed=False`** —
because the reference chart carries four accumulated-depreciation accounts
(rows 70-73) and NO expense to charge against them, which is half a double
entry. It is listed in `chart.PENDING_FINANCE_RE_SIGN_MATCHING` and its
re-sign route is named in `chart.PERIOD_MATCHING_RE_SIGN_SOURCE`. B5 line 74 is
❄️ FROZEN and is NOT edited here, then or ever, by a lane.

**THE PLACEMENT IS NOT IN THIS MIGRATION.** `services.ensure_period_matching_
accounts` does it, at provisioning and as a top-up on first use, for hard-won
law 4's reason: a migration reaches every host and a seed edit reaches none of
the ones that already exist. A tenant that has renumbered `2100` keeps their
number and the top-up leaves it alone.

WHAT AN OPERATOR MUST KNOW
---------------------------
This drops and re-adds a CHECK constraint on `ledger_accounts`, tens of rows per
tenant. PostgreSQL revalidates against existing rows, every one of which already
satisfies it because the set only GREW. No row is read, written or deleted, and
nothing here touches money.
"""

from django.db import migrations, models

#: The full set AFTER this migration. Spelled out rather than imported from
#: `apps.ledger.chart` for the reason `ledger/0009` gives: a migration must
#: describe the database as it was at the moment it was written, and a later
#: edit to that tuple must produce a NEW migration rather than silently
#: rewriting the meaning of this one.
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
)

#: The thirteen, exactly as `ledger/0009` left them. The reverse path restores
#: this list — a migration that cannot be backed out of is one a deploy cannot
#: back out of.
DESIGNATIONS_BEFORE = DESIGNATIONS_AFTER[:-3]


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
        ("ledger", "0013_cr061_chart_category"),
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
# packet: CR-060 C17 + C20 and tasks T7b + T7f (12-governance/11-change-requests.md
#         §7 · §12) · 04-docs/05-modules/09-ledger/02-business-rules.md
#         BR-LED-005/006/028/792/793 · 04-docs/02-decisions/05-golden-tests.md
#         B5 line 74 (❄️ FROZEN — NOT edited) · CLAUDE.md hard rules 1, 2, 4, 5, 7
# generated: 2026-09-02 by the CR-060 T7b/T7d/T7f lane
# checklist: A✔ B✔ C✔ D=deferred(no API half — a migration) E=deferred(no UI
#         half; claiming or renumbering a designation is the existing GL mapping
#         surface, BR-LED-014) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒
#         HUMAN-REVIEW-PENDING, ledger row appended)
# gates: PROVED RED FIRST — before this migration,
#         tests/test_cr060_t7b_unpaid_cost_accrual.py failed with
#         `ValueError: 'accrued_expenses' is not one of the GL designations the
#         Product Owner has ruled`, raised by
#         apps/ledger/selectors.gl_account_for_designation. That guard was RIGHT
#         to fire and is the reason this migration exists rather than three bare
#         constants being added
# exceptions: (1) THE DESIGNATION PLACEMENT IS NOT HERE — it is
#         `services.ensure_period_matching_accounts`, for hard-won law 4's
#         reason, stated in the docstring · (2) ONE new account (5700) is minted
#         and it is NOT finance-signed; two designations land on accounts that
#         already exist and NOTHING about those accounts changes · (3) no new
#         RLS policy and no new db/rls_*.sql: this creates no table and
#         `ledger_accounts` is already ENABLE+FORCE under the signed B2 §3
#         policy from ledger/0002 · (4) DESIGNATIONS_AFTER is spelled out rather
#         than imported from apps.ledger.chart, deliberately
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
