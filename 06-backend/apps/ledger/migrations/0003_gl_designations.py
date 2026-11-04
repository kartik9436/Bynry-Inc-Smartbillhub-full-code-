# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-005 (chart of accounts — TC-1 seeded chart, TC-6 isolation;
#           this migration adds the column that lets an entry FIND an account
#           when the tenant has renumbered it)   Screens: S56
# Rules:    BR-BIL-010 (the designation set the GL stamp resolves against) ·
#           CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 5 (balanced
#           pairs — a designation is how the posting service names the two
#           sides without hardcoding 1200 and 3000)
# ───────────────────────────────────────────────────────
"""ledger 0003 — `ledger_accounts.designation`, the eleven GL designations.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and this column feeds
ledger posting). HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO
ruling of 2026-08-09, implementing the PO rulings of 2026-08-11 that closed
OQ-106 (a designation is an ATTRIBUTE, not a designations table) and OQ-110
(the enumeration: eleven, option A). Row in
12-governance/09-human-review-ledger.md.

WHAT THIS ADDS, and nothing else: one nullable column, one index, one partial
unique constraint and one CHECK. No table. No data. **The SEED is not here** —
`apps/ledger/services.seed_chart_of_accounts()` runs at PROVISIONING, per
tenant, inside the provisioning transaction, because the chart is tenant data
and a migration that wrote rows would put a chart into every tenant that
existed at deploy time and into none that arrived afterwards.

────────────────────────────────────────────────────────────────────────────
RLS: NOTHING NEW IS NEEDED HERE, AND THAT IS A FINDING, NOT AN OMISSION
────────────────────────────────────────────────────────────────────────────
CLAUDE.md rule 1 wants ENABLE + FORCE with the B2 §3 template on anything new
and tenant-scoped. **This migration creates no table.** `ledger_accounts`
already carries `ledger_accounts_tenant_isolation` — applied verbatim from
`06-backend/db/rls_ledger_w5.sql` by `0002_rls_w5_and_immutability` — and a
COLUMN added to a table under RLS is covered by that table's policy: the policy
predicate is `tenant_id = current_setting('app.tenant_id')::uuid`, which gates
the ROW, so a new column on a gated row is gated. There is therefore no new
`db/rls_*.sql` file and no lookalike policy, which is deliberate: writing a
second policy for the same table would be the "lookalike policy" CLAUDE.md
warns against, and would quietly shadow the signed one.

This is asserted rather than asserted-in-prose: the G5 isolation suite's
catalog sweep names any table that reached the schema without a policy, and
`tests/test_us_led_005_gl_designations.py` adds an `-m isolation` case that
reads a DESIGNATION across tenants under the NOSUPERUSER probe role and
requires the refusal to come from row-level security. Hard-won law 1 — a
comment claiming a guarantee is not the guarantee, so the guarantee is a test.

────────────────────────────────────────────────────────────────────────────
THE TWO CONSTRAINTS, AND WHAT EACH ONE REFUSES
────────────────────────────────────────────────────────────────────────────
**`uq_ledger_accounts_designation`** — UNIQUE (tenant_id, designation) WHERE
designation IS NOT NULL AND deleted_at IS NULL. One LIVE account per
designation per tenant. This is the database half of the PO's stated reason for
choosing a field over a table: *"unambiguous at posting time"*. Without it, two
accounts could both be `accounts_receivable` and the posting service would pick
one by `ORDER BY` accident — the ambiguity a designations table would have had,
reintroduced through the column. Partial on `deleted_at` so a tenant can
deactivate 1200 and move the designation to a new 1150 (IS-1 deactivate-first);
partial on `designation IS NOT NULL` because most of the chart carries none and
a plain UNIQUE would permit exactly one undesignated account per tenant.

**`ck_ledger_accounts_designation`** — the value is NULL or one of the eleven.
A designation is resolved BY NAME, so `accounts_recievable` is an account
nothing will ever find, and the trial balance would be short by whatever posted
to it. Same class of hole as an unreadable `journal_lines.side`, closed the
same way and for the same reason.

**PROVED RED BEFORE GREEN** on a live cluster — see the trailer and
tests/test_us_led_005_gl_designations.py.

ORDERING. Depends on `0002`, so the column lands on a table that is already
under RLS FORCE and already append-only-guarded; there is never a window where
`ledger_accounts` is queryable across tenants. `tenancy/0006` (the matching
service attributes) depends on THIS migration, so the FK it adds cannot
outrun the table it points at.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0002_rls_w5_and_immutability"),
        ("tenancy", "0005_seed_subscription_plans"),
    ]

    operations = [
        migrations.AddField(
            model_name="ledgeraccount",
            name="designation",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="ledgeraccount",
            index=models.Index(fields=["tenant", "designation"], name="ix_ledger_accounts_desig"),
        ),
        migrations.AddConstraint(
            model_name="ledgeraccount",
            constraint=models.UniqueConstraint(
                condition=models.Q(("designation__isnull", False), ("deleted_at__isnull", True)),
                fields=("tenant", "designation"),
                name="uq_ledger_accounts_designation",
            ),
        ),
        migrations.AddConstraint(
            model_name="ledgeraccount",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("designation__isnull", True),
                    (
                        "designation__in",
                        (
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
                        ),
                    ),
                    _connector="OR",
                ),
                name="ck_ledger_accounts_designation",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-005@663369d (sources: 12-governance/02-decision-log.md 2026-08-11 rows "OQ-106 IS CLOSED" and "OQ-110 CLOSED" · 12-governance/01-open-questions.md OQ-106/OQ-110 · 04-docs/02-decisions/05-golden-tests.md line 74 ❄️ seed chart · 04-docs/05-modules/09-ledger/06-epics/EP-LED-02-chart-mapping.md §Scope as superseded 2026-08-11)
# generated: 2026-08-11 by Eng-Lead (W5 ledger GL-designation lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN on a live Postgres cluster — see the test file
#         and the human-review ledger row
# exceptions: NO new RLS policy and no new db/rls_*.sql file — this migration
#         creates no table, and `ledger_accounts` is already ENABLE+FORCE under
#         the signed B2 §3 policy from 0002; a second policy on the same table
#         would shadow the signed one. Stated here rather than left as a silent
#         absence, and backed by an -m isolation case · the DESIGNATION VALUES
#         are inlined into the CHECK by Django's own serializer, so a change to
#         apps/ledger/chart.GL_DESIGNATIONS needs a NEW migration — a twelfth
#         designation therefore cannot arrive without a migration on live
#         tenant data, which is the cost the PO priced when ruling option A on
#         OQ-110 · nothing NOT NULL: US-LED-005 leaves the chart the tenant's,
#         and BR-BIL-010's "required" is enforced at issue where an unmapped
#         line refuses its bill
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
