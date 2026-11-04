# ── Trace ──────────────────────────────────────────────
# Story:    CR-136-BRC07 §3.3 / task P2.21 — a drawer difference reaches the
#           books. PO ruling 2026-09-23, over the payments blueprint's own
#           "counting is not a posting".
#           Screens: S56 (the chart) · the six Counter screens (P2.6)
# Rules:    BR-LED-796 (NEW — one cash over/short account serves both
#           directions, seeded at 6850, resolved by designation) ·
#           BR-LED-040 (a tenant may rename and re-point it) · BR-LED-042
#           (one LIVE account per designation) · CLAUDE.md rule 5 (only the
#           ledger posting service writes journal lines) · rule 2 · rule 4
# Tests:    06-backend/tests/test_cr136_p221_cash_over_short_account.py ·
#           06-backend/tests/test_us_led_005_gl_designations.py (the CHECK)
# ───────────────────────────────────────────────────────
"""ledger 0016 — designation EIGHTEEN, `cash_over_short`.

HUMAN-OWNED (the chart of accounts decides WHICH GL account money lands in, a
CLAUDE.md 🔒 sensitive path, and migration ordering is another).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-23 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human
sign-off.

WHAT THIS UNBLOCKS
-------------------
A clerk counts the drawer at the end of a shift and it does not match what the
product expected. Until today that difference reached nothing: the payments
blueprint says in as many words *"The ledger: Nothing — counting is not a
posting"*, and `P2.15` had committed that sentence as a test.

The PO reversed it on 2026-09-23, verbatim: *"(b) Post it. A short writes a
balanced pair to a cash over/short account the day it is declared. Needs one
new account added to the chart"*. **DR `6850 Cash over and short` / CR `1010
Undeposited funds`** for a $12.0000 short, and the mirror for a $12.0000 over —
**one account, both directions**, which is what *cash over and short* means.

`ledger/0003` predicted this cost and `0006`, `0009`, `0014` and `0015` have
each paid it once: Django's serializer INLINES `chart.GL_DESIGNATIONS` into the
CHECK, so the database does not follow that tuple. One more constant without a
migration is accepted by Python and refused by PostgreSQL.

WHAT DOES *NOT* LAND HERE, AND BOTH ABSENCES ARE DELIBERATE
------------------------------------------------------------
**NO ACCOUNT IS CREATED BY THIS MIGRATION, AND UNLIKE `0015` THE ROW *IS* IN
THE PROVISIONING SEED.** `chart.SEED_CHART` carries `6850` between `6800 Bank
fees` and `6900 Bad debt`, so every tenant provisioned from today gets it with
the other 127. A migration that also INSERTED it would have to loop every
tenant with `set_config` under RLS and would duplicate what two existing paths
already do — `services.seed_chart_of_accounts`, which is insert-missing and is
run for **every existing tenant** by the automatic post-migrate reference sweep
(`tenancy.seed_reference_data_for_tenant` → `docker-entrypoint.sh`, OQ-087),
and `services.ensure_cash_over_short_account`, the first-use top-up this change
adds for the tenant the sweep has not reached yet. See that function's
docstring for the measured chain.

**NO POSTING.** `P2.22` owns the balanced pair, in payments, through the ledger
posting service (hard rule 5 — payments writes no journal line). This change
puts the POINTER and the account on the chart; nothing calls it yet.

WHAT AN OPERATOR MUST KNOW
---------------------------
This drops and re-adds a CHECK constraint on `ledger_accounts`, tens of rows per
tenant. PostgreSQL revalidates against existing rows, every one of which already
satisfies it because the set only GREW. No row is read, written or deleted, and
nothing here touches money.
"""

from django.db import migrations, models

#: The full set AFTER this migration. Spelled out rather than imported from
#: `apps.ledger.chart` for the reason `ledger/0009` gives and `0014` and `0015`
#: repeat: a migration must describe the database as it was at the moment it was
#: written, and a later edit to that tuple must produce a NEW migration rather
#: than silently rewriting the meaning of this one.
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
    "cash_over_short",
)

#: The seventeen, exactly as `ledger/0015` left them. The reverse path restores
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
        ("ledger", "0015_cr060_t15_allowance_designation"),
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
# packet: CR-136-BRC07 §3.3 + task P2.21
#         (12-governance/change-requests/CR-136-BRC07-payments-phase-2-the-counter.md) ·
#         12-governance/02-decision-log.md 2026-09-23 (the PO ruling, with both
#         worked directions and the reason it posts against 1010 rather than
#         1000) · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-796
#         (NEW) · 04-docs/02-decisions/05-golden-tests.md B5 line 74 (❄️ FROZEN
#         — NOT edited) · CLAUDE.md hard rules 1, 2, 4, 5, 7
# generated: 2026-09-23 by LANE P2-LEDGER (CR-136-BRC07 P2.21)
# checklist: A✔ B✔ C✔ D=deferred(no API half — a migration; the chart is already
#         served by GET /ledger/accounts and the new row appears on it) E=deferred(no UI
#         half; the account is edited on the EXISTING Settings → Accounting →
#         Chart of accounts screen, which needed no change to show a 128th row)
#         F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row
#         appended)
# gates: PROVED RED, THEN GREEN, ON REAL POSTGRESQL 16 — and the red was taken
#         from a database standing at the constraint `ledger/0015` leaves, by
#         cloning a seeded template (`sbh_tpl_bc23a826`, whose CHECK lists
#         seventeen designations and not `cash_over_short`) and running the
#         INSERT the seed itself makes. Copied off the run:
#           RED   ERROR:  new row for relation "ledger_accounts" violates check
#                 constraint "ck_ledger_accounts_designation"
#           GREEN after applying THIS migration's own DDL — taken from
#                 `manage.py sqlmigrate ledger 0016`, not hand-written — the
#                 same INSERT returns the row:
#                 6850 | Cash over and short | expense | cash_over_short |
#                 operating_expenses
#           AND   a typo (`cash_over_shrot`) is STILL refused with the same
#                 message, so this migration WIDENED the guard and did not
#                 loosen it
#         ⚠ the red was NOT taken through pytest, and saying so is the point
#         (hard-won law 7 — a red proof through the wrong entry point is no
#         proof of the thing that matters): the harness drops its test database
#         at the end of a run, so there was none standing at 0015 to point it
#         at. What was exercised instead is the database's own refusal, which is
#         the thing this migration exists to move.
#         GREEN IN THE HARNESS: `tests/test_cr136_p221_cash_over_short_account.py`
#         13 passed on live PostgreSQL 16 (2,392s under a loaded box) and 13
#         passed on the default sqlite suite with one vendor-skip
# exceptions: (1) THE ACCOUNT IS NOT CREATED HERE — it is in `chart.SEED_CHART`,
#         so provisioning plants it, the post-migrate reference sweep tops up
#         every EXISTING tenant, and `services.ensure_cash_over_short_account` is
#         the first-use door for the window between the two · (2) `6850` is
#         signed=False: the PO ruled that the POSTING must have a home, and a
#         posting ruling is not a finance signature on a chart row (the same
#         reading 4155, 4760 and UTILITY_BOOKS_CHART's 67 rows carry) · (3) no
#         new RLS policy and no new db/rls_*.sql: this creates no table and
#         `ledger_accounts` is already ENABLE+FORCE under the signed B2 §3 policy
#         from ledger/0002 · (4) DESIGNATIONS_AFTER is spelled out rather than
#         imported, deliberately
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
