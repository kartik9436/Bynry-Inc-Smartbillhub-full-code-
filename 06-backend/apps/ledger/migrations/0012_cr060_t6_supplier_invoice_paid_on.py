# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 T6 / C1 (12-governance/11-change-requests.md) — "Post
#           supplier costs on settlement", the CR's own "core change".
#           PO ruling 2026-09-02 (12-governance/02-decision-log.md, top row).
# Story:    US-LED-018 (capture)
#           Screens: S73 (R8 "Costs" — *"Paid on — blank until you pay it"*)
#           ⚠ The posting-contract story is deliberately NOT named in this
#           header: G23 attributes this trailer's `D✔` to every US-ID it finds
#           anywhere in the header, and the source-event posting contracts are
#           not API-reached by a column.
# Rules:    BR-LED-028 (AMENDED 2026-09-02 — full accounts payable is still
#           declined; a date recording that payment happened ELSEWHERE is not
#           accounts payable) · BR-LED-034 (a captured invoice is editable
#           while its period is open, with before/after audit) · BR-TEN-038 /
#           BR-LED-006 (a settlement dated into a closed period books forward)
#           · CLAUDE.md hard rule 5 (only the posting service writes journal
#           lines) · rule 7 (every money action audits)
# Tests:    06-backend/tests/test_cr060_t6_settlement_posting.py ·
#           06-backend/tests/test_us_led_018_capture.py (the REWRITTEN
#           posting-boundary case, T6a)
# ───────────────────────────────────────────────────────
"""ledger 0012 — `supplier_invoices.paid_on`, the one column C1 asks for.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path, and this
column is the trigger for a posting path). HUMAN-REVIEW-PENDING — AI-authored
2026-09-02 under the PO ruling of 2026-08-09. Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human
sign-off.

WHAT THIS IS, IN ONE SENTENCE
------------------------------
One nullable date saying the utility settled this supplier invoice, so that the
cost of buying water can reach the books on the day it was actually paid.

WHY A COLUMN THAT LOOKS HARMLESS IS THE ONE ledger/0011 REFUSED TO ADD
-----------------------------------------------------------------------
`ledger/0011` added `premises_id` and said in its own docstring why it left this
one alone: *"a nullable date column looks harmless and is the trigger for a
posting path; it is not landed by a task whose job is a report grouping."* It is
landed here, by the task whose job it is, and only because the ruling exists —
CR-060 T6's row requires *"a RECORDED RULING first, because it changes the trial
balance"*, and the PO gave it on 2026-09-02:

    "why cant to add the check that whether this is paid or unpaid and allow
     clark to udpaet it - that way we can reconcicle - again system of record we
     dont have to match we can take input from Clark and close it"

WHY THE COLUMN CAN LAND WITHOUT MOVING A SIGNED FIGURE
------------------------------------------------------
This is the part an operator most needs, and it is arithmetic rather than
reassurance. **`paid_on` is NULL on every existing row and nothing backfills
it**, and the service refuses to post for a row whose `paid_on` is unset. So on
any database as it stands today the settlement path is unreachable, no journal
entry is written, and LE-1's finance-signed July trial balance stays exactly
**598.69 = 598.69**.

The figure moves the day a clerk records the FIRST settlement, not the day this
migration applies. Settling all nine of LE-11's July purchases — **$51,902.50** —
takes it to **52,351.19 = 52,351.19**, and moving LE-1's signed 598.69 at all
takes the HUMAN-GUIDE §6 re-sign route and never an inline edit. The
review-ledger row states that boundary in those words.

⚠ **AND THE NUMBER IN CR-060 IS 150.00 HIGH — MEASURED 2026-09-02, NOT COPIED.**
C1 and the decision-log row of that day both say **52,501.19**, which is
598.69 + 51,902.50 and assumes nothing already on the books changes sides. One
account does: a trial balance carries each account's NET balance on ONE side,
LE-1 leaves **150.00 of debit in 1000 Cash**, and paying suppliers CREDITS cash
so 1000 nets to −51,752.50 and leaves the debit column altogether. The footing
therefore rises by 51,902.50 − 150.00. **Nothing signed moved:** 598.69 is the
signature and 52,501.19 was a projection written into a change request. The
correction is in `12-governance/02-decision-log.md` so that the re-sign, when it
is owed, reaches a person with the figure the product computes;
`tests/test_cr060_t6_settlement_posting.py` asserts both numbers and the 150.00
between them.

WHAT AN OPERATOR MUST KNOW BEFORE DEPLOYING THIS
-------------------------------------------------
`supplier_invoices` is NOT partitioned and is small by nature — one row per
supplier invoice a utility receives, a few dozen a month. One operation:

  * `ADD COLUMN paid_on date NULL` — on PostgreSQL 11+ a nullable column with
    no default rewrites no rows and takes only a brief ACCESS EXCLUSIVE lock to
    update the catalogue.

**NO INDEX, AND THAT IS A DECISION RATHER THAN AN OMISSION.** The register's
paid/unpaid split is a filter over a table of a few hundred rows read one tenant
and one period at a time, already covered by `ix_supplier_invoices_period`. An
index on a column that is NULL on every row buys nothing and costs a write on
every capture. `ledger/0011` laid its index with its column for the opposite
reason and said why — *"an index is free on a small table and costs a
maintenance window on a large one"* — and the same argument, applied to a
column nothing groups by, says not to.

**NO CHECK CONSTRAINT.** `paid_on < invoice_date` looks wrong and is lawful: a
utility on a standing order can be debited before the invoice is written. The
rules that DO bind this column — it cannot be cleared or moved once its
settlement has posted — live in `apps/ledger/cost_capture.py`, where a refusal
can say why. A database CHECK cannot.

**HARD RULE 4 IS NOT ENGAGED.** A captured supplier invoice is on none of the
four immutable lists (issued invoices, invoice lines, payments, journal
entries); `SupplierInvoice`'s docstring says so and the table deliberately
carries no immutability trigger, only the `ledger_supplier_invoice_no_delete()`
one from `ledger/0008`. Nothing here updates a row in any case: `ADD COLUMN`
with no default writes no heap tuples.

**WHAT IT DOES NOT DO.** It creates no `2500 Accounts payable` account and needs
none — the settlement posts `DR cost / CR cash` and never credits a payable, so
the liability the PO refused on 2026-08-16 is not created at any point. That
absence in `chart.COST_OF_SERVICE_CHART` was deliberate before the ruling and
stays correct after it.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("ledger", "0011_cr060_t4_supplier_invoice_premises"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplierinvoice",
            name="paid_on",
            field=models.DateField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060-T6@supplier-invoice-paid-on (the authorities this slice was
#         authored from: 12-governance/02-decision-log.md — the PO ruling of
#         2026-09-02, in full · 12-governance/11-change-requests.md CR-060 §7
#         C1, §9's `supplier_invoices` rows, §12 rows T6/T6a/T6b/T6c/T6d/T19/T20,
#         §13 WHAT NOT TO TOUCH and §15's rollback note ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-028/034/035 ·
#         apps/ledger/models.py SupplierInvoice and apps/ledger/posting.py,
#         read from the code rather than from the document)
# generated: 2026-09-02 by the CR-060 T6/T6a lane
# checklist: A✔ B✔ C✔ D✔(PATCH /finance/cost-of-service/{id} accepts paid_on + settled_at) E=deferred(the S73 "Paid on" field and its two state sentences are new catalogue strings and the locale files are another lane's — keys and English text reported to the caller, the same posture CR-060 T4(e) took) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: G16 partition coverage PASS before and after (`supplier_invoices` is not in NFR-24's set; recorded because a migration is a 🔒 sensitive path) · applied FORWARD, REVERSED and re-applied FORWARD against a REAL PostgreSQL 16.13 (`sbh_t6_migcheck`, a scratch database built by `manage.py migrate` under `config.settings.local`): `supplier_invoices` goes 22 columns -> 23 -> 22 -> 23, and `information_schema` reports `paid_on` as `date, is_nullable = YES`. ⚠ THE TABLE WAS EMPTY THERE, SO NO ROW-DIGEST CLAIM IS MADE FOR IT - a fresh database has no captured purchases, and inventing some to digest would have proved nothing about a column that is NULL on every row by construction. The evidence that it works WITH ROWS is the law-14 run: five transaction-sensitive cases of `tests/test_cr060_t6_settlement_posting.py` were run under `DJANGO_SETTINGS_MODULE=config.settings.local` against real PostgreSQL and passed (5 passed in 708.75s), capturing nine invoices, settling them and reading the trial balance back · proved RED first: the companion test file fails at collection on this migration's parent, ledger/0011
# exceptions: NO INDEX and NO CHECK constraint — both argued in the docstring
#         rather than omitted silently · NO BACKFILL: no rule says when an
#         already-captured purchase was paid, and a guessed settlement date
#         would post real money on a day nobody chose
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
