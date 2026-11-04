# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 T4 / C3 (12-governance/11-change-requests.md) — "Give the
#           supplier invoice a premises". C9's per-building recovery reads it.
# Story:    US-LED-018 (capture) · US-LED-020 (bought vs billed)  Screens: S73 · S74
# Rules:    BR-LED-029 (what a captured supplier invoice holds — AMENDED with
#           this change to add the optional premises) · BR-LED-031 (all-or-
#           nothing, AMENDED from per-service-per-period to per-service-per-
#           PREMISES-per-period when the report is grouped by building) ·
#           BR-MET-046 (a unit never moves between premises — which is what
#           makes a building a stable grouping key) · CLAUDE.md rule 1
#           (tenant scoping — the column is scoped by the row's own tenant_id
#           and by metering's tenant-scoped read on the way in)
# Tests:    06-backend/tests/test_cr060_t4_premises_recovery.py
# ───────────────────────────────────────────────────────
"""ledger 0011 — `supplier_invoices.premises_id`, and the index that reads it.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path, and this
table is the bought half of the one figure no accounting package can produce).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-01 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

WHAT THIS IS, IN ONE SENTENCE
------------------------------
One nullable pointer at the building a supplier invoice was bought for, so
bought-versus-billed can be computed per building instead of per tenant.

WHY IT IS THE WHOLE OF C3, IN CR-060'S OWN WORDS
-------------------------------------------------
*"THE CAUSE IS ONE MISSING COLUMN: `supplier_invoices` carries a service, an
amount and a volume — and no premises, no unit, no meter. The receivable side
already carries premises on every journal line. Only the cost side cannot say
where the money went."* A sub-metering company runs forty buildings, and
blending a leaking building with a tight one *"produces an average that
describes neither and points at nothing anyone can go and fix"*.

WHY NULLABLE, AND WHY THE NULL IS A REAL STATE
-----------------------------------------------
It is not an unfilled field waiting to be backfilled. Three lawful shapes:

  * a **utility** running one distribution system buys bulk water for the
    whole system and has no building to name — it will never fill this in;
  * a **tenant-wide** cost has no building by nature, and after CR-060 T5 that
    is most of the vocabulary: payroll, insurance, professional fees, office
    rent, the utility's own property and franchise taxes;
  * a **sub-metering company** fills it on every commodity purchase, because
    that is the figure it opened the product for.

**NO ROW IS BACKFILLED AND NONE COULD BE.** Every supplier invoice captured to
date was captured with no building, and there is no rule anywhere that says
which building an existing row belongs to. Guessing one would put money against
a building nobody bought it for, and the per-building report would then be
confidently wrong — which is worse than the absent-with-reason the
reconciliation already knows how to say.

WHY A REAL FK RATHER THAN A DEFERRED UUID — A CORRECTION TO CR-060 §9
----------------------------------------------------------------------
CR-060 §9's table asks for *"nullable UUID, deferred FK to metering, matching
how every other cross-module pointer here is declared"*. Those two clauses
disagree, and the SECOND one is right: read from `apps/ledger/models.py`, every
cross-module pointer in this module is a real FK with `on_delete=PROTECT` —
`JournalLine.service` → tenancy, `.account` → customers, `.premises` and
`.unit` → metering, `.tax_authority` → rating. `JournalLine`'s own docstring
states the rule the module follows: *"They are FKs rather than plain uuids
because every target table already exists; the B11 F-3 deferred-uuid convention
applies only where it does not."* `metering.Premises` has existed since
metering 0001, so the deferred convention does not apply here.

It matters beyond tidiness: the by-premises money figure and the per-building
recovery figure are the same building seen from the receivable side and the
cost side, and declaring the two pointers differently is how they eventually
disagree about which buildings exist.

WHAT AN OPERATOR MUST KNOW BEFORE DEPLOYING THIS
-------------------------------------------------
`supplier_invoices` is NOT partitioned and is small by nature — one row per
supplier invoice a utility receives, a few dozen a month. Two operations:

  * `ADD COLUMN premises_id uuid NULL REFERENCES premises(id)` — on PostgreSQL
    11+ a nullable column with no default does not rewrite the table; the FK is
    validated against zero existing non-null values, so there is no scan.
  * `CREATE INDEX ix_supplier_invoices_prem` — a plain b-tree on an ordinary
    (unpartitioned) table. Not `CONCURRENTLY`: Django's `AddIndex` does not
    emit it, and at this table's size the SHARE lock is milliseconds.

Measured on the live development database, PostgreSQL 16.13, 2026-09-01: the
whole migration applies and reverses in well under a second, `supplier_invoices`
holds its row count and its md5 row digest across both directions, and the
column comes back NULL on every existing row because nothing backfills it.

**HARD RULE 4 IS NOT ENGAGED.** A captured supplier invoice is on none of the
four immutable lists (issued invoices, invoice lines, payments, journal
entries) — `SupplierInvoice`'s own docstring says so and BR-LED-034 makes the
row editable while its period is open. Nothing here updates a row in any case:
`ADD COLUMN` with no default writes no heap tuples.

WHAT THIS MIGRATION DELIBERATELY DOES NOT DO
---------------------------------------------
**IT DOES NOT ADD `paid_on`.** CR-060 §9 lists the two `supplier_invoices`
columns together, and they belong to different tasks for a reason that is
recorded rather than assumed: `paid_on` is C1 / T6, whose own row says it
*"needs a RECORDED RULING first, because it changes the trial balance"*, and
CR-060 §15 makes it the one change on the whole list that is not
rollback-cheap. A nullable date column looks harmless and is the trigger for a
posting path; it is not landed by a task whose job is a report grouping.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("ledger", "0010_cr060_t8_journal_line_dimension_indexes"),
        # The FK target. Named at its own leaf rather than at 0001 so a fresh
        # database builds `premises` before this constraint is declared.
        ("metering", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="supplierinvoice",
            name="premises",
            field=models.ForeignKey(
                blank=True,
                db_column="premises_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="metering.premises",
            ),
        ),
        migrations.AddIndex(
            model_name="supplierinvoice",
            index=models.Index(
                fields=["tenant", "premises", "period_start"],
                name="ix_supplier_invoices_prem",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060-T4@supplier-invoice-premises (the authorities this slice was
#         authored from: 12-governance/11-change-requests.md — CR-060 §7 C3 and
#         C9, §9's two `supplier_invoices` rows, §11's test table and the T4 row
#         in §12 · 04-docs/05-modules/09-ledger/02-business-rules.md
#         BR-LED-029/030/031 · apps/ledger/models.py SupplierInvoice and
#         JournalLine, read from the model rather than from the document)
# generated: 2026-09-01 by the CR-060 T2/T3/T4 lane
# checklist: A✔ B✔ C✔ D✔(POST /finance/cost-of-service takes premises_id; GET …/reconciliation takes group_by=premises) E✔(S73 capture form + S74 grouping) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: G16 partition coverage PASS before and after (`supplier_invoices` is not in NFR-24's set; recorded because a migration is a 🔒 sensitive path) · applied FORWARD and REVERSE against a REAL PostgreSQL 16.13; row count and md5 row digest identical at both ends, and `premises_id` is NULL on every pre-existing row because nothing backfills it · proved RED first: the companion test file fails at collection on this migration's parent, ledger/0010
# exceptions: A REAL FK, NOT THE "deferred FK" CR-060 §9's wording asks for —
#         the same table's own convention and `JournalLine`'s stated rule both
#         say a real FK, and the correction is argued in the docstring rather
#         than taken silently · NO BACKFILL, and none is possible: no rule says
#         which building an already-captured purchase belongs to · `paid_on` is
#         NOT added here — it is C1/T6, which needs a recorded ruling first
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
