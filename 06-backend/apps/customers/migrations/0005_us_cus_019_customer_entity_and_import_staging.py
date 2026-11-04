# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-019 (EP-CUS-07 — the brownfield account import)
#           Screens: S17 · S68
# Rules:    BR-CUS-054 (the first-class customer entity — B2 r9 #1's own
#           column list) · BR-CUS-051 (staged import mechanics) ·
#           CLAUDE.md rule 6 / B2 DB-12 ("file+tags imports" idempotency) ·
#           CLAUDE.md rule 1 / DB-1 (RLS FORCE on every tenant table — the
#           policies for these four tables are in 0006)
# ───────────────────────────────────────────────────────
"""customers 0005 — the BR-CUS-054 customer entity + the US-CUS-019 staging pair.

HUMAN-OWNED (migration ordering 🔒 + idempotency keys 🔒). HUMAN-REVIEW-PENDING
— AI-authored 2026-08-11 under the PO ruling of 2026-08-09 ("AI will do it; we
will review it later as human"). Row in
12-governance/09-human-review-ledger.md.

FOUR TABLES, and where each column comes from
─────────────────────────────────────────────
`customers` + `customer_accounts` — **B2 r9 #1, verbatim**: *"`customers` (kind
person|company, display_name, external_ref UNIQUE per tenant) +
`customer_accounts` N:M link [BR-CUS-054]"*. Nothing is added to that list. The
UNIQUE is PARTIAL (`WHERE external_ref IS NOT NULL`) because a customer created
by the S18 wizard has no legacy reference and N of those must coexist; it is
case-insensitive because `CUST-118` and `cust-118` are one customer in every
legacy export.

`account_import_batches` + `account_import_rows` — **US-CUS-019 §5, verbatim**
("tenant, filename, uploaded_by, row/valid counts, committed_at" and "batch,
row_no, raw jsonb, errors jsonb, account_id NULL until commit"), PLUS three
columns §5 does not list and that CLAUDE.md rule 6 requires:

    file_hash        SHA-256 of the upload, server-side
    tag_fingerprint  SHA-256 of the batch-level tags (the cutover date)
    cutover_date     US-CUS-021 §5 "one date per batch"

🔒 THE IDEMPOTENCY UNIQUE, and why it is PARTIAL
────────────────────────────────────────────────
`UNIQUE (tenant_id, file_hash, tag_fingerprint) WHERE committed_at IS NOT NULL`
is B2 DB-12's "file+tags imports" for this story. Scoped to COMMITTED batches
because re-STAGING a file is legitimate — an operator re-opens the wizard, or
fixes a value and looks again — and it is the second COMMIT that would create
1,240 duplicate accounts. `apps/metering/models.ReadImportBatch` scopes its own
file+tags unique to POSTED batches for exactly this reason; this is the same
decision, not a new one.

The database half is the BACKSTOP, not the guard: `services.commit_account_import`
looks the prior committed batch up FIRST and refuses with BIZ-IDEMPOTENT naming
it, so the operator is told *which* run already did the work rather than
getting an integrity error. Both halves exist on purpose, and the test observes
the SERVICE path rather than only the outcome — DEF-058's lesson, where a
database unique silently substituted for a deleted application guard and
nothing went red.

**Every table here lands EMPTY.** No data step, no tenant context needed.
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0004_r17_custom_data"),
        ("identity", "0004_rls_security_policies"),
        ("tenancy", "0008_rls_custom_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountImportBatch",
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
                ("filename", models.TextField()),
                ("cutover_date", models.DateField(blank=True, null=True)),
                ("file_hash", models.TextField(blank=True, null=True)),
                ("tag_fingerprint", models.TextField(blank=True, null=True)),
                ("row_count", models.IntegerField(default=0)),
                ("valid_count", models.IntegerField(default=0)),
                ("skip_errors", models.BooleanField(default=True)),
                ("committed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="uploaded_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "account_import_batches",
            },
        ),
        migrations.CreateModel(
            name="AccountImportRow",
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
                ("row_no", models.IntegerField()),
                ("raw", models.JSONField()),
                ("errors", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        blank=True,
                        db_column="account_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="customers.account",
                    ),
                ),
                (
                    "batch",
                    models.ForeignKey(
                        db_column="batch_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="customers.accountimportbatch",
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
                "db_table": "account_import_rows",
            },
        ),
        migrations.CreateModel(
            name="Customer",
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
                ("kind", models.TextField(default="person")),
                ("display_name", models.TextField()),
                ("external_ref", models.TextField(blank=True, null=True)),
                ("custom_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                "db_table": "customers",
            },
        ),
        migrations.CreateModel(
            name="CustomerAccount",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="customers.account",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        db_column="customer_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="customers.customer",
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
                "db_table": "customer_accounts",
            },
        ),
        migrations.AddIndex(
            model_name="accountimportbatch",
            index=models.Index(fields=["tenant", "-created_at"], name="ix_account_imports_recent"),
        ),
        migrations.AddConstraint(
            model_name="accountimportbatch",
            constraint=models.UniqueConstraint(
                condition=models.Q(("committed_at__isnull", False), ("file_hash__isnull", False)),
                fields=("tenant", "file_hash", "tag_fingerprint"),
                name="uq_account_import_batches_idempotency",
            ),
        ),
        migrations.AddIndex(
            model_name="accountimportrow",
            index=models.Index(fields=["tenant", "batch"], name="ix_account_import_rows_batch"),
        ),
        migrations.AddConstraint(
            model_name="accountimportrow",
            constraint=models.UniqueConstraint(
                fields=("batch", "row_no"), name="uq_account_import_rows"
            ),
        ),
        migrations.AddIndex(
            model_name="customer",
            index=models.Index(fields=["tenant", "display_name"], name="ix_customers_tenant_name"),
        ),
        migrations.AddConstraint(
            model_name="customer",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                django.db.models.functions.text.Lower("external_ref"),
                condition=models.Q(("external_ref__isnull", False)),
                name="uq_customers_tenant_external_ref_ci",
            ),
        ),
        migrations.AddIndex(
            model_name="customeraccount",
            index=models.Index(fields=["tenant", "account"], name="ix_customer_accounts_account"),
        ),
        migrations.AddConstraint(
            model_name="customeraccount",
            constraint=models.UniqueConstraint(
                fields=("customer", "account"), name="uq_customer_accounts_pair"
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-019@248ffac (EP-CUS-07 lead story, sha1 of the epic file; co-packet customers 02-business-rules@554f391)
# generated: 2026-08-11 by story-coder (W2 customers slice 4 — the brownfield account import)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — migration) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — migration ordering + idempotency keys 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: see the lane report — makemigrations --check clean · migrate from empty on sqlite · tests/test_us_cus_019_account_import.py 13 passed
# exceptions: `customers` + `customer_accounts` are built from B2 r9 #1's OWN column list (kind person|company, display_name, external_ref UNIQUE per tenant, N:M link) — apps/customers/models.py had claimed no column list existed and that claim was FALSE, corrected in the same lane · the `external_ref` unique is PARTIAL (an S18-created customer has no legacy ref) and CASE-INSENSITIVE (legacy exports are inconsistent) — neither clause is stated in r9 #1, both are REPORTED · `customer_accounts` is unique on the PAIR, honouring B2's literal "N:M link", so nothing here forbids a jointly-held account · the three columns §5 does not list (`file_hash`, `tag_fingerprint`, `cutover_date`) exist because CLAUDE.md rule 6 / DB-12 requires the file+tags key; the unique is scoped to COMMITTED batches for the same reason metering scopes its own to POSTED ones · `account_import_value_maps` (r9 #4's third table) is NOT built — US-CUS-020 owns it, and a table with no writer is a promise · NOT applied to a live PostgreSQL cluster by this lane (DEF-054 — none reachable in this environment); stated rather than left as a silent absence
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
