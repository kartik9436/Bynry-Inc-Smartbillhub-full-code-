# ── Trace ──────────────────────────────────────────────
# Defects: DEF-536 (a discounted bill drafts and previews and CANNOT ISSUE)
# Story:    US-LED-005 (the chart and its designations) · US-BIL-005 §7 (the
#           posting handoff this unblocks)   Screens: S56 · Settings → Configure
# Rules:    BR-BIL-010 (every line's GL account is stamped at issue) ·
#           BR-BIL-011 (one bill = one balanced JE) · BR-RAT-068 (a discount is
#           an overlay — its own line, so subsidy granted is reportable) ·
#           CLAUDE.md rule 5 (only the ledger posting service writes journal
#           lines) · rule 2 (money 4dp stored, display 2)
# Tests:    06-backend/tests/test_def_536_discount_gl.py ·
#           06-backend/tests/test_us_led_005_gl_designations.py (the CHECK)
# ───────────────────────────────────────────────────────
"""ledger 0009 — `discount_contra_revenue` becomes the THIRTEENTH designation.

HUMAN-OWNED (the chart of accounts decides WHICH GL account money lands in, a
CLAUDE.md 🔒 sensitive path, and migration ordering is another).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-28 under the PO ruling of 2026-08-09.
Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded
human sign-off.

WHAT RULING THIS IMPLEMENTS, IN THE PO'S OWN WORDS
---------------------------------------------------
2026-08-28, verbatim: *"you will need differnt GL code for these - dont keep
them in same, create differnt category as required and keep them in it"* —
recorded in 12-governance/02-decision-log.md, answering the designation
question `DEF-536` had been blocked on since 2026-08-22.

WHY, WITH THE ❄️ FROZEN GT-1 FIGURES
------------------------------------
A 10.00 goodwill reduction on the GT-1 bill, the two ways it could be booked:

    old (netted into the service)      ruled (its own GL)
    CR electric usage    72.08         CR electric usage     82.08
    CR electric base     18.50         CR electric base      18.50
                                       DR customer discounts 10.00
    DR accounts receivable 90.58       DR accounts receivable 90.58

Both balance at **100.58**. The left-hand form reports **72.08** of electric
revenue the utility never earned at that price; the right-hand form states the
reduction as its own figure a finance person can read, and leaves the revenue
account saying what electricity actually sold for. That is standard
contra-revenue, and it is option **(a)** as OQ-152 itself enumerated it on
2026-08-11.

⚠ IT ALSO REMOVES OQ-152's FAILURE MODE
---------------------------------------
OQ-152 closed 2026-08-12 — *"a bill whose GL bucket sums below zero REFUSES to
issue"* — and `apps/billing/posting_seam.posting_buckets` refuses by that name
(`posting_bucket_is_negative_oq_152`). A discount netted against the service's
own account is what drives a bucket below zero. Posted as a **DEBIT** to this
designation's account, no bucket goes negative, so that refusal cannot fire on
a discount at all. **Both rulings stand; neither is superseded**, and the
negative-bucket refusal still fires for anything else that could drive a bucket
negative.

⚠ THE DESIGNATION AND THE ACCOUNT BOTH LAND, AND ONLY ONE OF THEM IS SIGNED
---------------------------------------------------------------------------
This migration adds the DESIGNATION — a product-code change under a PO ruling.
`apps/ledger/chart.SEED_CHART` also gains **4300 Customer discounts
(contra-revenue)**, `signed=False`, listed in `PENDING_FINANCE_RE_SIGN`,
declared exactly as 4160/4170 and 4180 were on the day each arrived. B5 line 74
is ❄️ FROZEN and is **NOT edited inline**; the account's code and name await a
finance re-sign via HUMAN-GUIDE §6.

Seeded rather than left to refuse — unlike `budget_variance` — because the
ruling settles the DESIGNATION and explicitly leaves the code to be *"created
as required"*, and because an unseeded designation reproduces DEF-536 for every
fresh tenant: a discounted bill would still not issue. A tenant that wants a
different number renumbers it on Settings → Configure (PO 2026-08-12, *"Confirm:
under Configure"*), which is the same right US-LED-005 gives them over AR.

WHY THIS IS A MIGRATION AT ALL
------------------------------
`ledger/0003` predicted the cost and `ledger/0006` paid it once already: Django's
serializer INLINES `chart.GL_DESIGNATIONS` into the CHECK, so the database does
not follow that tuple. A thirteenth constant without a migration is accepted by
Python and refused by Postgres.

**WHAT AN OPERATOR MUST KNOW.** This drops and re-adds a CHECK constraint on
`ledger_accounts`, a small table (tens of rows per tenant). Postgres validates
the new constraint against existing rows, all of which already satisfy it — the
set only grew — so the revalidation is trivially fast and no row is read,
written or deleted. Nothing here touches money.
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
    "discount_contra_revenue",
)

#: The twelve, exactly as `ledger/0006` left them. The reverse path restores
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
        ("ledger", "0008_supplier_invoices"),
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
# packet: US-LED-005@749d8da (sha1[:7] of the authorities this slice was
#         authored from, newline-joined in order: 12-governance/02-decision-log.md
#         — the 2026-08-28 row carrying the PO ruling verbatim ·
#         12-governance/01-open-questions.md — OQ-152, CLOSED 2026-08-12, which
#         this composes with · 04-docs/02-decisions/05-golden-tests.md — B5 line
#         74, ❄️ frozen, which this ruling adds a line to and which is therefore
#         NOT edited here · 04-docs/05-modules/09-ledger/02-business-rules.md —
#         BR-LED-790). Closes DEF-536's designation half.
# generated: 2026-08-28 by the DEF-536/DEF-537 discount-posting lane
# checklist: A✔ B✔ C✔ D=deferred(no API half — a migration) E=deferred(no UI half; claiming or renumbering the designation is the existing GL mapping surface under Settings → Configure, BR-LED-014) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: PROVED RED FIRST — before this migration,
#         tests/test_def_536_discount_gl.py failed with
#         `ValueError: 'discount_contra_revenue' is not one of the GL
#         designations the Product Owner has ruled`, raised by
#         apps/ledger/selectors.gl_account_for_designation. That guard was RIGHT
#         to fire and is the reason this migration exists rather than a bare
#         constant being added
# exceptions: THE DESIGNATION IS ADDED AND SO IS ITS SEED ACCOUNT (4300,
#         signed=False, in PENDING_FINANCE_RE_SIGN) — the divergence from
#         ledger/0006, which added a designation and no account, is stated in
#         the docstring above with its reason · no new RLS policy and no new
#         db/rls_*.sql: this creates no table and `ledger_accounts` is already
#         ENABLE+FORCE under the signed B2 §3 policy from ledger/0002 ·
#         DESIGNATIONS_AFTER is spelled out rather than imported from
#         apps.ledger.chart, deliberately — a migration must describe the schema
#         at the moment it was written
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
