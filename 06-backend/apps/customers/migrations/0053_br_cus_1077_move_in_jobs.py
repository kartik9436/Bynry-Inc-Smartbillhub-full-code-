"""customers 0053 — `move_in_jobs`, the queue row an approved move-in never had.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering AND RLS policies are
both on CLAUDE.md's sensitive-paths list, and this file carries one of each. The
ledger row is in `12-governance/09-human-review-ledger.md`; AI-authored under the
PO ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*) and
not RATIFIED without a recorded sign-off.

PO ruling 2026-09-16, verbatim: *"it should do B"*, choosing from three options
put to them with each cost named — decision log, *"RULED — OPTION B: APPROVING A
MOVE-IN RAISES A PENDING MOVE-IN JOB, THE WAY A NEW CONNECTION RAISES A DRAFT
BUILD. THE ACCOUNT STILL DOES NOT OPEN AT APPROVAL."* The rule is `BR-CUS-1077`
and the reasoning for every column is in `apps/customers/move_in_jobs.py`'s
docstring, beside the column it governs, rather than restated here.

════════════════════════════════════════════════════════════════════════════
THE TABLE AND ITS POLICY ARE ONE MIGRATION, DELIBERATELY
════════════════════════════════════════════════════════════════════════════
`0042`/`0043`, `0045`/`0046` and `0051`/`0052` each split the `CreateModel` from
its policy across two files. `0030` — the other table in this same module, built
by the same reasoning — keeps them together, and that is the form followed here
for two reasons. **One leaf instead of two**: every extra migration in a tree
several lanes are pushing to is another chance of the two-leaf refusal that names
neither lane. And **hard rule 1 is not a follow-up**: a tenant table that exists
for even one deploy without FORCE on it is a table that can be read across
tenants, so the `ENABLE`/`FORCE`/`CREATE POLICY` runs in the same transaction
that creates it, which is exactly what putting it after the `CreateModel` in one
`operations` list does.

════════════════════════════════════════════════════════════════════════════
WHAT THE CONSTRAINTS ARE FOR
════════════════════════════════════════════════════════════════════════════
`ck_move_in_job_state` pins the two-value vocabulary (`pending`, `done`) at the
database layer as well as in `move_in_jobs.STATES`, so an import or a fixture
cannot introduce a third — the shape `ck_move_record_kind` has one table over.

`uq_move_in_jobs_tenant_request` is the IDEMPOTENCY guarantee and not a tidiness
one: one decision raises one job, so a clerk double-clicking `Approve` gets one
row and a second press reports *"already raised"* rather than making a duplicate
queue entry nobody can tell from the first. `move_in_jobs.raise_for_request`
checks it first so the clerk reads a sentence; this is what makes the check a
guarantee rather than a race.

It is a PLAIN unique, not the partial case-insensitive shape `move_no` and
`customer_no` carry: those are on human-typed NUMBERS that must not collide
across case and may legitimately be NULL. This is a foreign key that is NOT NULL,
where `LOWER()` means nothing and a partial predicate would only weaken it.

════════════════════════════════════════════════════════════════════════════
RLS — ENABLE + FORCE + THE `NULLIF` POLICY (DEF-639), NOT THE BARE CAST
════════════════════════════════════════════════════════════════════════════
CLAUDE.md hard rule 1, written in `0022`'s exact form so the two cannot drift: a
bare `current_setting('app.tenant_id', true)::uuid` raises on the EMPTY STRING an
unset GUC leaves behind, where `NULLIF(..., '')::uuid` yields NULL and the
predicate simply matches nothing. `PostgresOnlySQL` is what keeps the sqlite test
tier runnable — the isolation tier runs on real Postgres.

The reason of its own, which is the one worth reading: each row says that a named
utility has APPROVED somebody's application to take over service at an address.
A tenant able to read another tenant's rows would learn who is moving in where,
before those people are customers of anybody.

**NO BACK-FILL, AND THAT IS A DECISION.** Requests approved before today raised
no job and get none: a row written now would claim a clerk approved a job that
did not exist when they pressed, which is the rewrite-history posture hard rule 4
refuses one table over. The demo tenant's two move-in requests are reachable on
the Requests tab exactly as they were. A back-fill would also have to run as the
app role under RLS FORCE and walk tenants setting `app.tenant_id` — the failure
mode is a migration that sees nothing and reports success — and the honest
version of that is not writing one.

**Rollback (change-process step 8):** this reverses cleanly. The policy drops,
FORCE comes off, and the `CreateModel` reverses to a `DROP TABLE`. What is lost
is the pending queue — every approved move-in that nobody has done yet — and
those requests are still `Approved` with their outcome recorded, so no money,
invoice, ledger row or account depends on the table. Reversing it puts the
product back to the behaviour `DEF-CUS-5398` describes, which is the sentence to
read before running it.
"""

import core.dbfields
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

#: `0022_cr030_w7_disconnect_ladder`'s form, character for character. DEF-639:
#: the bare cast raises on the empty string an unset GUC leaves behind.
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

TABLE = "move_in_jobs"

POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""

REVERSE = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0052_rls_br_cus_1076_service_request_messages"),
        ("identity", "0004_rls_security_policies"),
        ("tenancy", "0044_cr094_i_account_document_source"),
    ]

    operations = [
        migrations.CreateModel(
            name="MoveInJob",
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
                ("state", models.TextField(default="pending")),
                ("raised_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("closed_reason", models.TextField(blank=True, null=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "raised_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="raised_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.user",
                    ),
                ),
                (
                    "request",
                    models.ForeignKey(
                        db_column="request_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="customers.servicerequest",
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
                "db_table": "move_in_jobs",
                "indexes": [
                    models.Index(
                        fields=["tenant", "state", "-created_at"], name="ix_move_in_jobs_state"
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("state__in", ("pending", "done"))),
                        name="ck_move_in_job_state",
                    ),
                    models.UniqueConstraint(
                        fields=("tenant", "request"), name="uq_move_in_jobs_tenant_request"
                    ),
                ],
            },
        ),
        # THE POLICY — after the CreateModel, which is what makes FORCE apply to
        # a table that exists and is still empty.
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]
