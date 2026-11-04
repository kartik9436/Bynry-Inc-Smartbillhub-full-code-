# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 `P1.01` (lane MVI-SCHEMA) — the ONE customers migration
#           for every new fact the move-in redesign needs (CR §6, §8 P1.01).
# Rules:    CLAUDE.md hard rule 1 (RLS ENABLE + FORCE in the same migration) ·
#           hard rule 2 (money 4, percentage 6) · hard rule 8 (no address
#           column) · BR-CUS-092 (encrypted SSN/licence + blind index) ·
#           BR-CUS-1077 (`cancelled`, CR-171 S2) · CR-171 §8.3 (rollback)
# Models:   apps/customers/co_owner_models.py · apps/customers/move_in_extras.py
#           · apps/customers/models.py (Customer, Account) ·
#           apps/customers/move_in_jobs.py
# Tests:    06-backend/tests/test_cr171_p1_01_move_in_schema.py ·
#           06-backend/tests/test_cr171_p1_01_rls_pg.py
# ───────────────────────────────────────────────────────
"""customers 0080 — the move-in redesign's schema, in one migration.

HUMAN-OWNED — migration ordering and RLS policies are CLAUDE.md 🔒 sensitive
paths. 🔒 HUMAN-REVIEW-PENDING — AI-authored 2026-10-05 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md` (`CR-171-BRC10 P1.01`); not RATIFIED
without a recorded human sign-off.

WHAT IT ADDS — ADDITIVE ONLY (CR-171 §8.3)
------------------------------------------
* **`account_co_owners`** — a person's co-owners and a company's owners and
  officers, one table with `kind` (`co_owner` | `officer`); SSN and driving
  licence encrypted at the application layer with a blind index beside each
  (BR-CUS-092, `customers.Customer`'s shape); the photo ID is an
  `account_documents` filing card; `responsible_for_bills`.
* **`move_fee_lines`** — the *Fees* table of a move-in, on `move_records`.
* **`move_extra_messages`** — the added rows of its *Messaging* table.
* **`customers.trading_as` · `business_type` · `registered_in`** and
  **`accounts.po_number` · `bills_go_to` · `autopay_instrument_id`** and
  **`contacts.job_title` · `contact_by`** (lane MVI-IDN's ask, CR-171 §9.IDN) —
  nullable; nothing back-filled.
* **`move_in_jobs.state`** — the CHECK widens to admit `cancelled`.

WHAT IT DELIBERATELY DOES NOT ADD
---------------------------------
* **No tax-exemption column.** `rating.TaxExemptionCertificate` already holds
  the exemption's TYPE (`category`) and its ISSUED date (`issued_on`), with
  `certificate_ref` and `expires_on`; the certificate FILE is an
  `account_documents` row (`P1.15`). Reused, per the brief.
* **No `taxable` on a fee line** — `OQ-BIL-12788` is OPEN (CR-171 §7 Q1).
* **No parked-fee table** — before Complete the wizard's parked JSON holds it.

RLS — THE THREE NEW TABLES, IN THIS MIGRATION
---------------------------------------------
ENABLE + FORCE with the `NULLIF` predicate (DEF-622/DEF-639's form, which
`customers/0074` records is the rule and B2 §3's code block now carries), so an
unset `app.tenant_id` admits nothing rather than raising. `PostgresOnlySQL`
skips honestly on SQLite. Proof: `tests/test_cr171_p1_01_rls_pg.py`.

ROLLBACK — THE DOWN PATH REFUSES WHILE A CLERK'S RECORD WOULD BE LOST
---------------------------------------------------------------------
Reversing drops the three tables and eight columns and narrows the CHECK. It
**refuses first**, naming each count, while any of these exist: a co-owner, a
fee line, an extra message, a `cancelled` job, or a non-NULL value in any of the
eight new columns — because dropping them deletes records a clerk wrote (CR-171
§8.3; the eight columns are added to §8.3's four for the same reason). To
reverse anyway, remove those rows deliberately first; this migration will not
do it for you.

⚠ **THE COUNT RUNS PER TENANT, WITH `app.tenant_id` SET, AND FILTERS ON
`tenant_id` TOO** — `rating/0039`'s lesson (DEF-RAT-5799): a migration role that
does not bypass RLS sees ZERO rows on a FORCEd table with no tenant set, and a
guard counting zero would let the reverse drop everything while reporting
nothing. Setting the tenant makes RLS admit that tenant's rows; the explicit
`WHERE tenant_id` keeps a bypassing role from counting every tenant's rows once
per tenant. The setting in force before the guard ran is put back after it.
"""

import core.crypto
import core.dbfields
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

NEW_TABLES = ("account_co_owners", "move_fee_lines", "move_extra_messages")

POLICIES = "".join(f"""
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {t}_tenant_isolation ON {t};
CREATE POLICY {t}_tenant_isolation ON {t}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
""" for t in NEW_TABLES)

REVERSE_POLICIES = "".join(f"""
DROP POLICY IF EXISTS {t}_tenant_isolation ON {t};
ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
""" for t in NEW_TABLES)

#: What the reverse would destroy, as (label, table, predicate). Every predicate
#: is ANDed with `tenant_id = <tenant>` by the guard.
GUARDED: tuple[tuple[str, str, str], ...] = (
    ("co-owners / owners and officers", "account_co_owners", "TRUE"),
    ("fee lines", "move_fee_lines", "TRUE"),
    ("extra messages", "move_extra_messages", "TRUE"),
    ("cancelled move-in jobs", "move_in_jobs", "state = 'cancelled'"),
    (
        "company names (trading as / business type / registered in)",
        "customers",
        "trading_as IS NOT NULL OR business_type IS NOT NULL OR registered_in IS NOT NULL",
    ),
    (
        "contact details (job title / contact by)",
        "contacts",
        "job_title IS NOT NULL OR contact_by IS NOT NULL",
    ),
    (
        "bill routing / autopay source (PO on bills / bills go to / autopay from)",
        "accounts",
        "po_number IS NOT NULL OR bills_go_to IS NOT NULL OR autopay_instrument_id IS NOT NULL",
    ),
)


def _forward_noop(apps, schema_editor):
    """Nothing to do going up — the guard is the reverse's first step."""


def refuse_while_rows_exist(apps, schema_editor):
    """CR-171 §8.3 — refuse the reverse, naming the counts, while it would
    delete a record a clerk wrote. See the module docstring's last section."""
    connection = schema_editor.connection
    postgres = connection.vendor == "postgresql"
    tenant_ids = list(apps.get_model("tenancy", "Tenant").objects.values_list("id", flat=True))
    totals: dict[tuple[str, str], int] = {}
    with connection.cursor() as cursor:
        previous = None
        if postgres:
            cursor.execute("SELECT current_setting('app.tenant_id', true)")
            previous = cursor.fetchone()[0]
        try:
            for tenant_id in tenant_ids:
                if postgres:
                    cursor.execute(
                        "SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)]
                    )
                for label, table, predicate in GUARDED:
                    cursor.execute(
                        f"SELECT count(*) FROM {table} WHERE tenant_id = %s AND ({predicate})",
                        [str(tenant_id) if postgres else tenant_id.hex],
                    )
                    totals[(label, table)] = totals.get((label, table), 0) + cursor.fetchone()[0]
        finally:
            if postgres:
                cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [previous or ""])
    held = [f"{count} {label} ({table})" for (label, table), count in totals.items() if count]
    if held:
        raise RuntimeError(
            "customers/0080 will not reverse: it would delete "
            + "; ".join(held)
            + ". These are records a clerk wrote (CR-171 §8.3). Remove them "
            "deliberately first if the rollback must go ahead."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0079_def_cus_9692_transfer_committed_by"),
        ("identity", "0008_cr145_withdraw_long_timeouts_per_tenant"),
        ("metering", "0076_def_wrk_6737_outcome_check"),
        ("tenancy", "0060_cr168_work_certificate_proof"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountCoOwner",
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
                ("kind", models.TextField()),
                ("full_name", models.TextField()),
                ("relationship", models.TextField(blank=True, null=True)),
                ("title", models.TextField(blank=True, null=True)),
                (
                    "ownership_pct",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("signs_for_company", models.BooleanField(default=False)),
                ("personal_guarantee", models.BooleanField(default=False)),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                (
                    "ssn",
                    core.crypto.EncryptedTextField(
                        blank=True, crypto_context="account_co_owners.ssn", null=True
                    ),
                ),
                ("ssn_bidx", models.TextField(blank=True, null=True)),
                (
                    "driving_licence",
                    core.crypto.EncryptedTextField(
                        blank=True, crypto_context="account_co_owners.driving_licence", null=True
                    ),
                ),
                ("driving_licence_bidx", models.TextField(blank=True, null=True)),
                ("phone", models.TextField(blank=True, null=True)),
                ("email", core.dbfields.CITextField(blank=True, null=True)),
                ("contact_by", models.TextField(blank=True, null=True)),
                ("responsible_for_bills", models.BooleanField(default=False)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "account_co_owners",
            },
        ),
        migrations.CreateModel(
            name="MoveExtraMessage",
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
                ("seq", models.SmallIntegerField()),
                ("template_key", models.TextField()),
                ("recipient", models.TextField()),
                ("channel", models.TextField()),
                ("send_when", models.TextField()),
                ("notification_id", models.UUIDField(blank=True, null=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                "db_table": "move_extra_messages",
            },
        ),
        migrations.CreateModel(
            name="MoveFeeLine",
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
                ("seq", models.SmallIntegerField()),
                ("kind", models.TextField()),
                ("source", models.TextField()),
                ("charge_code_id", models.UUIDField(blank=True, null=True)),
                ("code", models.TextField()),
                ("description", models.TextField(blank=True, null=True)),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("note", models.TextField(blank=True, null=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                "db_table": "move_fee_lines",
            },
        ),
        migrations.RemoveConstraint(
            model_name="moveinjob",
            name="ck_move_in_job_state",
        ),
        migrations.AddField(
            model_name="account",
            name="bills_go_to",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="account",
            name="autopay_instrument_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contact",
            name="job_title",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contact",
            name="contact_by",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="contact",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("contact_by__isnull", True),
                    ("contact_by__in", ("email", "text", "phone", "letter")),
                    _connector="OR",
                ),
                name="ck_contacts_contact_by",
            ),
        ),
        migrations.AddField(
            model_name="account",
            name="po_number",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="business_type",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="registered_in",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="customer",
            name="trading_as",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="account",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("bills_go_to__isnull", True),
                    ("bills_go_to__in", ("account_holder", "contact_person")),
                    _connector="OR",
                ),
                name="ck_accounts_bills_go_to",
            ),
        ),
        migrations.AddConstraint(
            model_name="moveinjob",
            constraint=models.CheckConstraint(
                condition=models.Q(("state__in", ("pending", "done", "cancelled"))),
                name="ck_move_in_job_state",
            ),
        ),
        migrations.AddField(
            model_name="accountcoowner",
            name="account",
            field=models.ForeignKey(
                db_column="account_id",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="co_owners",
                to="customers.account",
            ),
        ),
        migrations.AddField(
            model_name="accountcoowner",
            name="photo_id_document",
            field=models.ForeignKey(
                blank=True,
                db_column="photo_id_document_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="customers.accountdocument",
            ),
        ),
        migrations.AddField(
            model_name="accountcoowner",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="moveextramessage",
            name="co_owner",
            field=models.ForeignKey(
                blank=True,
                db_column="co_owner_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="customers.accountcoowner",
            ),
        ),
        migrations.AddField(
            model_name="moveextramessage",
            name="move_record",
            field=models.ForeignKey(
                db_column="move_record_id",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="extra_messages",
                to="customers.moverecord",
            ),
        ),
        migrations.AddField(
            model_name="moveextramessage",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddField(
            model_name="movefeeline",
            name="move_record",
            field=models.ForeignKey(
                db_column="move_record_id",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="fee_lines",
                to="customers.moverecord",
            ),
        ),
        migrations.AddField(
            model_name="movefeeline",
            name="tenant",
            field=models.ForeignKey(
                db_column="tenant_id",
                on_delete=django.db.models.deletion.PROTECT,
                to="tenancy.tenant",
            ),
        ),
        migrations.AddIndex(
            model_name="accountcoowner",
            index=models.Index(fields=["tenant", "account"], name="ix_account_co_owners_account"),
        ),
        migrations.AddIndex(
            model_name="accountcoowner",
            index=models.Index(fields=["tenant", "ssn_bidx"], name="ix_account_co_owners_ssn_bidx"),
        ),
        migrations.AddIndex(
            model_name="accountcoowner",
            index=models.Index(
                fields=["tenant", "driving_licence_bidx"], name="ix_account_co_owners_dl_bidx"
            ),
        ),
        migrations.AddConstraint(
            model_name="accountcoowner",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind__in", ("co_owner", "officer"))),
                name="ck_account_co_owners_kind",
            ),
        ),
        migrations.AddConstraint(
            model_name="accountcoowner",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("contact_by__isnull", True),
                    ("contact_by__in", ("email", "text", "phone", "letter")),
                    _connector="OR",
                ),
                name="ck_account_co_owners_contact_by",
            ),
        ),
        migrations.AddConstraint(
            model_name="accountcoowner",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("ownership_pct__isnull", True),
                    models.Q(("ownership_pct__gte", 0), ("ownership_pct__lte", 100)),
                    _connector="OR",
                ),
                name="ck_account_co_owners_ownership_pct",
            ),
        ),
        migrations.AddConstraint(
            model_name="accountcoowner",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("kind", "officer"),
                    models.Q(
                        ("title__isnull", True),
                        ("ownership_pct__isnull", True),
                        ("signs_for_company", False),
                        ("personal_guarantee", False),
                    ),
                    _connector="OR",
                ),
                name="ck_account_co_owners_officer_facts",
            ),
        ),
        migrations.AddIndex(
            model_name="moveextramessage",
            index=models.Index(
                fields=["tenant", "move_record"], name="ix_move_extra_messages_move"
            ),
        ),
        migrations.AddConstraint(
            model_name="moveextramessage",
            constraint=models.CheckConstraint(
                condition=models.Q(("recipient__in", ("customer", "co_owner", "unit_owner"))),
                name="ck_move_extra_messages_recipient",
            ),
        ),
        migrations.AddConstraint(
            model_name="moveextramessage",
            constraint=models.CheckConstraint(
                condition=models.Q(("channel__in", ("email", "text", "letter", "portal"))),
                name="ck_move_extra_messages_channel",
            ),
        ),
        migrations.AddConstraint(
            model_name="moveextramessage",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "send_when__in",
                        (
                            "on_complete",
                            "day_before_move_in",
                            "on_move_in_date",
                            "day_before_visit",
                        ),
                    )
                ),
                name="ck_move_extra_messages_send_when",
            ),
        ),
        migrations.AddConstraint(
            model_name="moveextramessage",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("recipient", "co_owner"), ("co_owner__isnull", False)),
                    models.Q(
                        models.Q(("recipient", "co_owner"), _negated=True),
                        ("co_owner__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="ck_move_extra_messages_co_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="moveextramessage",
            constraint=models.UniqueConstraint(
                fields=("move_record", "seq"), name="uq_move_extra_messages_seq"
            ),
        ),
        migrations.AddIndex(
            model_name="movefeeline",
            index=models.Index(fields=["tenant", "move_record"], name="ix_move_fee_lines_move"),
        ),
        migrations.AddConstraint(
            model_name="movefeeline",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind__in", ("deposit", "fee"))), name="ck_move_fee_lines_kind"
            ),
        ),
        migrations.AddConstraint(
            model_name="movefeeline",
            constraint=models.CheckConstraint(
                condition=models.Q(("source__in", ("plan", "charge_code"))),
                name="ck_move_fee_lines_source",
            ),
        ),
        migrations.AddConstraint(
            model_name="movefeeline",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gte", 0)), name="ck_move_fee_lines_amount"
            ),
        ),
        migrations.AddConstraint(
            model_name="movefeeline",
            constraint=models.UniqueConstraint(
                fields=("move_record", "seq"), name="uq_move_fee_lines_seq"
            ),
        ),
        # THE POLICIES — after the CreateModels, so FORCE lands on tables that
        # exist and are still empty (hard rule 1, same migration).
        PostgresOnlySQL(POLICIES, reverse_sql=REVERSE_POLICIES),
        # THE GUARD — LAST, so on the way down it is the FIRST thing to run,
        # before any column or table is dropped.
        migrations.RunPython(_forward_noop, reverse_code=refuse_while_rows_exist),
    ]
