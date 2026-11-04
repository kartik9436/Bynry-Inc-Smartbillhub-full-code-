# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C19 / task T7d — the class breakdown on the allocation row.
#           Screens: S41 (the dual-basis remittance table whose collected column
#           this makes computable) · S36 (the tax tie-out's collected side)
#           NOTE: no US-ID is cited ON PURPOSE — G10 reads a Trace-header US-ID
#           as "this file ships that story's TCs", and no story owns C19 yet.
# Rules:    BR-PAY-010 (the allocation order, and the within-invoice class
#           sequence: usage+base → taxes → the tenant-defined class → fees LAST,
#           a TENANT SETTING since 2026-08-12) · BR-PAY-038 (the fourth class is
#           tenant-defined, which is why `line_class` is TEXT and not an enum) ·
#           BR-PAY-031 (a reapply is reversing rows plus new rows, never an
#           edit) · BR-LED-002 (BOTH remittance bases always computed) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money 4 dp written on a
#           NUMERIC(18,6) container) · rule 4 (financial immutability)
# Ruling:   OQ-129 CLOSED 2026-08-16 — the within-bill sequence is BR-PAY-010's
#           tenant setting and a partial payment walks it until the money runs
#           out. OQ-174 CLOSED 2026-08-12 — *"a partial payment covers TAX
#           FIRST"*. THE TWO DISAGREE, and CR-060 C19 rules that the disposition
#           is to RECORD the breakdown rather than pick a winner.
# Tests:    06-backend/tests/test_cr060_t7d_allocation_classes.py
# ───────────────────────────────────────────────────────
"""payments 0015 — `allocation_classes`, the one new table in CR-060.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path and this table carries
money that a tax return is filed from). HUMAN-REVIEW-PENDING — AI-authored
2026-09-02 under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*); row in 12-governance/09-human-review-ledger.md.

WHAT IT IS FOR, WITH THE FIGURE
--------------------------------
`allocations` records a payment, an invoice and an AMOUNT — and not WHICH KINDS
OF CHARGE the money met. So the *collected* tax basis, which a tenant may
already choose to file on, cannot be produced: `apps/ledger/reporting.
remittance_by_authority` returns `collected=None` with its reason attached
rather than showing the billed figure, *"which would have a utility remit tax on
money nobody has paid"*.

Worked, on the signed WE-1 bill: **247.87 = 226.90 of revenue + 20.97 of tax**
(State 13.87 · County 2.22 · City 4.44 · PUC 0.44). A customer pays **150.00**.
Under the SHIPPED class order — usage and base first, taxes second — the 150.00
is entirely absorbed by the 226.90 of revenue and reaches no tax at all, so
**0.00** of tax is collected. Under *tax first* the same payment collects the
whole **20.97**. Both are correct answers to different tenant settings, and until
today the product could not say afterwards which one had happened.
**These rows are that record.**

WHY A CHILD TABLE AND NOT FOUR COLUMNS
---------------------------------------
CR-060's own data note: *"Either four nullable amount columns or a child row per
class; the child row survives a fifth class being added, which the tenant-defined
class makes likely."* BR-PAY-038 already lets a tenant define a class of their
own, so the set is open by rule and four columns would be wrong the first time a
tenant used the feature they were sold.

**RLS AND THE APPEND-ONLY TRIGGER ARE 0016, NOT THIS MIGRATION** — policy SQL and
immutability triggers are their own 🔒 review surface, which is the split
0004/0005, 0007/0008, 0009/0010 and 0012/0013 all use. Until 0016 runs this table
has NO tenant isolation; the two migrations ship in one commit and neither is
deployable alone.

WHAT AN OPERATOR MUST KNOW
---------------------------
`CREATE TABLE` and two indexes. **Nothing is backfilled and nothing can be**: the
breakdown for allocations written before today was computed and never stored
anywhere but the audit payload, which is pruned on a retention schedule. So the
collected basis answers from the day this lands forward, and the read says so by
name rather than reporting a small figure as though it were a whole month.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0014_cr059_cs34_amendable_reference"),
        ("tenancy", "0035_cr065_size_class_service_backfill"),
    ]

    operations = [
        migrations.CreateModel(
            name="AllocationClass",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("line_class", models.TextField()),
                ("amount", models.DecimalField(decimal_places=6, max_digits=18)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "allocation",
                    models.ForeignKey(
                        db_column="allocation_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="classes",
                        to="payments.allocation",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "allocation_classes",
                "indexes": [
                    models.Index(fields=["tenant", "allocation"], name="ix_alloc_classes_alloc"),
                    models.Index(fields=["tenant", "line_class"], name="ix_alloc_classes_class"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "allocation", "line_class"),
                        name="uq_allocation_classes_line",
                    )
                ],
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: 12-governance/11-change-requests.md CR-060 §7 C19 + §12 task T7d ·
#         12-governance/01-open-questions.md OQ-129 (CLOSED 2026-08-16) and
#         OQ-174 (CLOSED 2026-08-12) — the two that disagree ·
#         04-docs/05-modules/07-payments/02-business-rules.md BR-PAY-010 /
#         BR-PAY-031 / BR-PAY-038 · 04-docs/02-decisions/02-database-design-brief.md
#         §2 (`allocations`, five columns and no class) + §3 (the RLS template,
#         applied in 0016) · CLAUDE.md hard rules 1, 2, 4, 7
# generated: 2026-09-02 by the CR-060 T7b/T7d/T7f lane
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI —
#         C19's surface is the EXISTING S41 collected column, which stops
#         returning absent) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒
#         HUMAN-REVIEW-PENDING, ledger row appended)
# gates: makemigrations --check clean · see
#         06-backend/tests/test_cr060_t7d_allocation_classes.py, proved RED first
# exceptions: (1) **NOTHING IS BACKFILLED AND NOTHING CAN BE** — the breakdown
#         for allocations written before today lived only in the audit payload,
#         which is pruned. The collected basis answers from this migration
#         forward and the read names that limit rather than reporting a partial
#         month as a whole one · (2) `line_class` carries NO CHECK constraint:
#         BR-PAY-038 makes the fourth class tenant-defined, so the vocabulary is
#         per-tenant data and an inlined CHECK would freeze one tenant's list
#         into every database (`chart.GL_DESIGNATIONS`' documented trap) · (3)
#         RLS and the append-only trigger are `payments/0016`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
