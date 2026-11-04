# ── Trace ──────────────────────────────────────────────
# Change:   CR-061 statement (1) (12-governance/11-change-requests.md) — "you
#           need more GL codes and categories". PO ruling 2026-09-01, completed
#           on the PO's instruction of 2026-09-02, "complete 61 based on actual
#           code".
# Story:    US-LED-005 (chart of accounts: seeded at provisioning,
#           tenant-customizable)   Screens: S56 · Settings → Accounting
# Rules:    BR-LED-014 (the GL mapping page this chart feeds) · BR-LED-015
#           (every chart change audits) · US-LED-005 rule 1 (the tenant's chart
#           is the tenant's — nothing here rewrites a row) · CLAUDE.md hard
#           rule 4 (financial immutability — no journal line is touched)
# Tests:    06-backend/tests/test_cr061_chart_categories.py
# ───────────────────────────────────────────────────────
"""ledger 0013 — `ledger_accounts.category`, one nullable grouping column.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-02 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

WHAT THIS IS, IN ONE SENTENCE
------------------------------
One nullable text column holding the heading an account is read under, so that a
chart of 125 accounts can be scanned by a person instead of only sorted by
number.

WHY IT IS A COLUMN AND NOT DERIVED FROM THE CODE
-------------------------------------------------
`chart.py` exists to prevent exactly one thing, and says so in a banner:
**"Code reads the DESIGNATION. Code never reads the NUMBER."** US-LED-005 lets a
utility renumber accounts receivable from 1200 to 1150 and rename it "Trade
debtors". A category derived from the code would therefore be wrong the moment a
tenant used the freedom the product gives them, which is the same defect OQ-106
was raised to prevent, one level up. So the heading travels WITH the account.

WHY THERE IS NO `CHECK` CONSTRAINT, UNLIKE `designation`
---------------------------------------------------------
`ledger/0003` put a CHECK on `designation` and `ledger/0006` is the migration
that paid for adding a twelfth value to it — Django's serializer INLINES the
values into the constraint, so the database does not follow `chart.py` and every
new designation costs a migration. That price is right for a POINTER the posting
service resolves money through. It is wrong for a GROUPING: nothing resolves an
account by category, no figure changes because of one, and a utility that wants
an eighteenth heading is doing chart work. `type` has been Python-validated on
this same table since the model was written (verified again for CR-061 on
2026-09-01 against every `ledger/migrations/*`, which is what made the sixth
account type a code change rather than a migration), and this column follows it.

WHAT AN OPERATOR MUST KNOW BEFORE DEPLOYING THIS
-------------------------------------------------
`ledger_accounts` is NOT partitioned and is small by nature — one row per account
in a tenant's chart, of the order of a hundred per tenant. One operation:

  * `ADD COLUMN category text NULL` — on PostgreSQL 11+ a nullable column with
    no default rewrites no rows and takes only a brief ACCESS EXCLUSIVE lock to
    update the catalogue.

**NO INDEX, AND THAT IS A DECISION.** The chart list is not paginated and is
bounded by the tenant's own chart rather than by transaction volume; the S56
panel already reads every row and groups in memory. An index on a low-cardinality
column of a hundred-row-per-tenant table buys nothing and costs a write on every
chart edit.

**NO BACKFILL, AND THAT IS THE ONE THING A READER MUST NOT MISREAD.** Every
account on a database provisioned before this migration keeps `category = NULL`,
and that is hard-won law 4 stated as data: a seed change never reaches a tenant
that already has a chart, because `services._create_missing_accounts` skips any
code the tenant already holds. A fresh tenant seeded after this lands gets all
125 rows categorised; an existing tenant sees its chart under one *Uncategorised*
heading until somebody files the rows, and the screen says so rather than hiding
them. Backfilling by CODE is exactly the derivation the section above refuses.
The same gap for a CHANGED seed row is already filed as `DEF-3060` and its
finance half is `OQ-1280`.

**HARD RULE 4 IS NOT ENGAGED.** No journal entry, journal line, invoice, invoice
line or payment is read or written here. A chart heading governs where a future
line is PRESENTED, never what a posted line says; nothing already posted is
rewritten, and nothing could be — `_CHART_FROZEN_ONCE_POSTED` already freezes
`code` and `type` on an account with lines against it, and this column is
neither.

**NO SIGNED FIGURE MOVES.** `G61` reads 130 ❄️ frozen money figures unchanged
before and after, `10-scripts/03-golden-verify.py` 33 PASS / 0 FAIL, and `G64`
14 of 61 engine-verified — a column that stores a heading cannot move an amount.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("ledger", "0012_cr060_t6_supplier_invoice_paid_on"),
    ]

    operations = [
        migrations.AddField(
            model_name="ledgeraccount",
            name="category",
            field=models.TextField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-061-S1@chart-category (the authorities this slice was authored
#         from: 12-governance/11-change-requests.md § CR-061 §0 statement (1),
#         §4's "STATEMENT (1) … NOT DONE HERE" and §5's 111-row reference chart
#         with its Category column · 12-governance/02-decision-log.md — the PO
#         rulings of 2026-09-01 · apps/ledger/chart.py and models.py, read from
#         the code rather than from the document, per the PO's own instruction
#         "complete 61 based on actual code")
# generated: 2026-09-02 by the CR-061 chart-of-accounts lane
# checklist: A✔ B✔ C✔ D✔(GET /ledger/accounts serves `category` and accepts
#            `f.category`; POST and the import accept it) E✔(the chart panel
#            groups by heading) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒
#            HUMAN-REVIEW-PENDING, ledger row appended)
# exceptions: NO INDEX, NO CHECK CONSTRAINT and NO BACKFILL — all three argued
#         in the docstring rather than omitted silently
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
