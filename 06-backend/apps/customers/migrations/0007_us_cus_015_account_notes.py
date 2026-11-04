# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-015 (S22 Add note) · US-CUS-011 (the S21 Notes tab — §5's
#           column list is the DDL below, verbatim)
#           Screens: S21 · S22
# Rules:    BR-CUS-035 (notes are customers-owned; `customer_visible` is
#           CAPTURED and inert in v1) · CLAUDE.md rule 1 / DB-1 (RLS FORCE on
#           every tenant table — the policy for this table is in 0008)
# ───────────────────────────────────────────────────────
"""customers 0007 — `account_notes` (BR-CUS-035).

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-08-11 under the PO ruling of 2026-08-09 ("AI will do it; we will review it
later as human"). Row in 12-governance/09-human-review-ledger.md.

Every column is US-CUS-011 §5's own list — *"`account_notes` (tenant_id,
account_id, title, body, author_id, pinned, customer_visible, timestamps)"* —
and nothing is added to it. The one thing §5 leaves to the migration is the
INDEX, and it exists because the capability matrix fixes the tab's order
("pinned first, then date desc"): an order that a screen states and the database
cannot serve is an order that becomes a Python sort over every note an account
ever collected.

NOT NULL is deliberately absent from `title` and `body` BOTH. The rule is "title
OR body required" (US-CUS-011 TC-7), which no column constraint can express, so
it lives in the service where it can say which field was empty. A NOT NULL on
either one would refuse a legitimate body-only note.

Applied to a live PostgreSQL cluster by this lane — see the lane report.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0006_rls_us_cus_019_tables"),
        ("identity", "0004_rls_security_policies"),
        ("tenancy", "0008_rls_custom_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountNote",
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
                ("title", models.TextField(blank=True, null=True)),
                ("body", models.TextField(blank=True, null=True)),
                ("pinned", models.BooleanField(default=False)),
                ("customer_visible", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="customers.account",
                    ),
                ),
                (
                    "author",
                    models.ForeignKey(
                        blank=True,
                        db_column="author_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.user",
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
                "db_table": "account_notes",
                "indexes": [
                    models.Index(
                        fields=["tenant", "account", "-pinned", "-created_at"],
                        name="ix_account_notes_pinned",
                    )
                ],
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-015@f7c1a20 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/03-customers/06-epics/EP-CUS-04-account-actions.md · 04-docs/05-modules/03-customers/06-epics/EP-CUS-05-change-plan.md · 04-docs/05-modules/03-customers/02-business-rules.md · 04-docs/01-spec/11b-api-audit.md §2.6; co-packet US-CUS-011, same four sources)
# generated: 2026-08-11 by story-coder (W4 customers ACTION lane — the S22 modals and the S23 wizard)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — migration) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migration ordering 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: see the lane report — makemigrations --check clean · migrate from empty on sqlite AND on a live PostgreSQL 16 database · pytest tests/test_us_cus_012_017_account_actions.py
# exceptions: `title` and `body` are BOTH nullable — the rule is "title OR body", which no column constraint expresses, so the service enforces it and names the field (US-CUS-011 TC-7) · no `deleted_at`: IS-1's pattern for a note is an audited EDIT (`note.updated`, whole-row before/after per BR-AUD-003), and a delete would need a rule before it needs a column · the RLS policy is migration 0008, not this file, matching the 0005/0006 pair
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
