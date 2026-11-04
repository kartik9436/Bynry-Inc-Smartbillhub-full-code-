# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-007 TC-5 (issue fails atomically if any line cannot resolve
#           a GL) · US-BIL-005 (the GL stamp at issue)
#           Screens: S30 · S31 · S13 (where the tenant maps the authority)
# Rules:    BR-BIL-069 (a tax line names its AUTHORITY; each authority has its
#           OWN 2200-series liability account; the tenant manages both — PO
#           ruling 2026-08-11 closing OQ-116) · BR-BIL-010 (every invoice line
#           carries a GL account resolved at issue and FROZEN) · BR-BIL-004 /
#           CLAUDE.md rule 4 (financial immutability) · BR-TEN-037 (tax
#           jurisdictions are tenant-entered) · B5 line 74 ❄️ (*"2200-series Tax
#           payable per authority — tenant authorities mint their own"*)
# ───────────────────────────────────────────────────────
"""billing 0010 — `invoice_lines.tax_id`, the column that lets a bill issue.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-11 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

WHAT IT IS
----------
One nullable FK, `invoice_lines.tax_id → taxes.id`, and it is the whole of the
TAGGING half of BR-BIL-069. The PO's words, verbatim: *"For each atheority have
separate account and tagging; but also ensure you allow Use to manage it since
every utility may not have every account."*

A single tax charge is usually several taxes. On the reference $117.01 bill the
$8.30 is State of Texas 6.25% = $6.29 + Harris County 1.00% = $1.01 + City of
Katy 1.00% = $1.00 over the $100.58 taxable base — three authorities, three
debts, three returns to file. Before this column a tax line recorded only
`kind='tax'`, its wording and its amount, so $6.29 could not be identified as
Texas's; BR-BIL-010's stamp had nothing to resolve and refused the bill. That
refusal was correct — a guess remits the wrong money to a tax authority — and
it is also why NO BILL IN THIS PRODUCT COULD BE ISSUED. This column closes it.

WHY IT LANDS NOW: NO BILL HAS BEEN ISSUED YET, AND THAT WAS VERIFIED
---------------------------------------------------------------------
Not assumed. On the live cluster this lane ran against, before writing this
file:

    SELECT status, count(*) FROM invoices GROUP BY status;   ->  (0 rows)
    SELECT count(*) FROM invoice_lines;                      ->  0

So this is one ALTER TABLE on an empty table. After go-live it would be the
same ALTER **plus a backfill of rows hard rule 4 forbids editing** — an issued
invoice line cannot be UPDATEd at all (see below), so the tax identity of every
bill issued before this column would be unrecoverable except by voiding and
re-billing. BR-BIL-069 records that timing argument as accepted.

WHY AN FK AND NOT A BARE UUID
-----------------------------
`invoice_lines.gl_account_id` is a plain uuid because `ledger_accounts` did not
exist when it was written (the B11 F-3 deferred-FK convention). That reasoning
does not apply here: `taxes` is a table that EXISTS, and this table already
carries two reviewed cross-module FKs into the same module — `tariff_version_id
→ rating.tariff_versions` and `charge_id → rating.charges` (B2 §2 / DB-16). A
third alongside them is the shape the reviewed interface set already has.

`ON DELETE` is Django's `PROTECT`, matching both neighbours: a tax an issued
bill points at is part of a financial record, and IS-1's deactivate-first
(`taxes.deleted_at`) is how a tenant retires one.

THE IMMUTABILITY TRIGGER: CHECKED, NOT ASSUMED — AND NOT RE-EMITTED
--------------------------------------------------------------------
`0009` had to re-emit `billing_invoice_immutable()` for its new column, and its
docstring states the general law it learned: **PostgreSQL stores a function
body as TEXT**, so a column added later is a column the freeze does not know
about — the guard fails open while every test stays green. That is a real trap
and it was checked here rather than reasoned about.

It does not bite on THIS table. `billing_invoice_line_immutable()` (installed by
`0002`) names no columns at all:

    IF parent_status IS NOT NULL AND parent_status <> 'draft' THEN
      RAISE EXCEPTION 'BR-BIL-004 / hard rule 4: invoice % is % — its lines
                       cannot be % . A correction is a new row.'

A line has no status of its own, so it is frozen by its INVOICE's status and
the trigger refuses the whole statement — every UPDATE and every DELETE, every
column, including ones that did not exist when it was written. Re-emitting an
identical function body would be a no-op that made this file look as though it
had fixed something.

**PROVED ON A LIVE POSTGRES CLUSTER (hard-won law 7), after applying this
migration.** One statement, run twice: it sets the new column on a line, by id.
With the parent invoice a `draft` it reported one row changed. With the same
invoice `issued` — nothing else altered — it raised

    BR-BIL-004 / hard rule 4: invoice BL-2607-000101 is issued — its lines
    cannot be update . A correction is a new row.

and removing that same row raised its twin. Both halves, and the statements
themselves, are in the human-review-ledger row; the SQL is not repeated here
because G6 greps this file for exactly that shape and the grep is right to.
"The trigger covers it" is precisely the kind of claim hard-won law 1 exists
about, so it was run rather than reasoned about.

RLS
---
No new policy. `invoice_lines` already carries `invoice_lines_tenant_isolation`
under ENABLE + FORCE from `0002` (the signed B2 §3 template in
`db/rls_billing_w3.sql`), and a policy is per TABLE, not per column — a column
added to a protected table is protected. `taxes` is itself RLS-scoped
(BR-TEN-037), so the FK cannot reach across tenants either: a crafted tax id
belonging to another tenant is invisible to the reads that resolve it.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0009_w2_custom_snapshot"),
        # The FK target. Named explicitly so the B2 §7 ordering is a declared
        # fact rather than a coincidence of when the two apps happened to run.
        ("rating", "0004_schedule_drafts_and_plan_eligibility"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoiceline",
            name="tax",
            field=models.ForeignKey(
                blank=True,
                db_column="tax_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="rating.tax",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@e9d5a48 (this file's own sources, in order:
#         12-governance/02-decision-log.md 2026-08-11 row "EACH TAX AUTHORITY
#         GETS ITS OWN LIABILITY ACCOUNT…" (PO ruling closing OQ-116) ·
#         12-governance/01-open-questions.md OQ-116 (CLOSED) ·
#         04-docs/05-modules/07-billing/02-business-rules.md BR-BIL-069 +
#         BR-BIL-010 · 04-docs/02-decisions/05-golden-tests.md line 74 ❄️ ·
#         04-docs/02-decisions/02-database-design-brief.md §2 billing + r10 #1)
# generated: 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: applied to a LIVE Postgres cluster; `makemigrations --check` clean.
#         Immutability PROVED on that cluster after the ALTER: the new column
#         updates freely while the invoice is a draft and raises
#         "BR-BIL-004 / hard rule 4: invoice BL-2607-000101 is issued — its
#         lines cannot be update" once it is issued. Transcript verbatim in
#         12-governance/09-human-review-ledger.md
# exceptions: (1) the `invoice_lines` immutability trigger is deliberately NOT
#         re-emitted. 0009 had to re-emit the INVOICES trigger because that one
#         freezes by NAMING columns; `billing_invoice_line_immutable()` names
#         none and refuses every UPDATE/DELETE by parent status, so it covers a
#         column added afterwards. Checked on a live cluster, not reasoned
#         about — the difference between the two triggers is the whole content
#         of this exception · (2) no RLS operation: a policy is per table and
#         `invoice_lines` has carried one under FORCE since 0002 · (3) no
#         backfill and no data migration — `invoices` was verified EMPTY on the
#         live cluster first; a bill issued before this column could never be
#         repaired, only credited and re-billed (hard rule 4)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
