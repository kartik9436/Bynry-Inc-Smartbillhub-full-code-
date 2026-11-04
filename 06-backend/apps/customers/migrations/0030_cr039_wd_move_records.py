"""customers 0030 — `move_records`, the table a move-in and a move-out never had.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list and the ledger row for this file is in
`12-governance/09-human-review-ledger.md`. The marker is here because the PATH
is the category, not because the body is large (DEF-808).

CR-039 wave D tasks 17–19, against the CR's own trace finding 5, verbatim:
*"Transfer and disconnect have tables and no number; **move-in and move-out have
NO RECORD AT ALL**"*, consequence *"A clerk cannot quote a reference; nothing on
a bill can point at the job that caused a change."*

PO ruling 2026-08-27, verbatim and in full: *"you cna keep them as records for
audit perpuses"*. The rules the columns implement are `BR-CUS-150`–`BR-CUS-153`;
the reasoning for each column is in `apps/customers/moves.py`'s docstring, beside
the column it governs, rather than restated here.

════════════════════════════════════════════════════════════════════════════
⚠ THIS IS `0030` AND `0029` DOES NOT EXIST. THAT IS DELIBERATE.
════════════════════════════════════════════════════════════════════════════
Migration numbers in this repo are ALLOCATED TO A LANE, not taken from a
watermark — DEF-892 is what happens when several lanes each take "the next free
number" from a shared register on the same day. `customers 0030` is this lane's
reservation; `0029` is somebody's to spend. Django's autodetector proposed
`0029_cr039_wd_move_records` and it was renamed by hand.

**Nothing about the graph depends on the digits.** This migration `dependencies`
on `0028_cr039_wd_transfer_and_case_numbers`, which is the real leaf today, so a
`0029` landing later also on 0028 makes two leaves and Django asks for a merge —
the ordinary, visible outcome, and the reason a gap is safe where a silently
duplicated number would not be.

════════════════════════════════════════════════════════════════════════════
AN ORDINARY MANAGED `CreateModel`, UNLIKE `transfers` NEXT DOOR
════════════════════════════════════════════════════════════════════════════
`transfers` is `managed = False` with raw-SQL DDL in `0021` and state-only in
`0027`, because the lane that built it could not touch `apps/customers/models.py`
and a `CreateModel` would have left state holding an unregistered model.
`disconnect_cases` (0022) is an ordinary managed model in exactly this position —
its own module, imported at the foot of `models.py` — and this follows that one.
`models.py` now carries `from apps.customers import moves` deliberately, so the
registration does not depend on some unrelated module happening to import it
(which is the accident `0027`'s docstring records).

**Measured, not assumed (hard-won law 1):** delete this file and
`makemigrations --check` answers `+ Create model MoveRecord` at once.

════════════════════════════════════════════════════════════════════════════
UNIQUENESS IS PER TENANT, CASE-INSENSITIVE, AND ONLY WHERE A NUMBER EXISTS
════════════════════════════════════════════════════════════════════════════
`uq_move_records_tenant_move_no_ci` is the shape `customers 0013` established
for `customer_no` and `customers 0028` repeated for `transfer_no` / `case_no`,
for the same three reasons: BR-TEN-035 never reuses a number; a clerk typing
`mvi-26-0001` means the row that reads `MVI-26-0001`, which is ONE number to a
human and two to a plain unique index; and **the partial predicate is what lets
the column be NULL** on a host provisioned before 2026-08-27, whose tenant has
no `move_in` / `move_out` series row until `manage.py seed_demo --tenant
<subdomain>` writes one. NULLs must not collide with each other.

`ck_move_record_kind` pins the two-value vocabulary at the database layer as
well as in `moves.KINDS`, so an import or a fixture cannot introduce a third.

════════════════════════════════════════════════════════════════════════════
RLS — ENABLE + FORCE + THE `NULLIF` POLICY (DEF-639), NOT THE BARE CAST
════════════════════════════════════════════════════════════════════════════
CLAUDE.md hard rule 1. The policy runs AFTER the `CreateModel`, which is what
makes FORCE apply to a table that exists and is still empty, and it is written in
`0022`'s exact form so the two cannot drift: a bare
`current_setting('app.tenant_id', true)::uuid` raises on the EMPTY STRING that an
unset GUC leaves behind, where `NULLIF(..., '')::uuid` yields NULL and the
predicate simply matches nothing. `PostgresOnlySQL` is what keeps the sqlite test
tier runnable — the isolation tier runs on real Postgres.

**Rollback (change-process step 8):** this migration reverses cleanly. The policy
drops, FORCE comes off, and the `CreateModel` reverses to a `DROP TABLE`. **What
is lost by reversing it is the records themselves** — unlike `0028`, whose two
columns were NULL on every row, this table HOLDS data from the first move-in
after it lands. Nothing else reads it, so no bill, no invoice and no ledger row
depends on it; but a reversal is a deletion of an audit trail, and that is the
sentence to read before running it.
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
import django.utils.timezone
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

#: `0022_cr030_w7_disconnect_ladder`'s form, character for character. DEF-639:
#: the bare cast raises on the empty string an unset GUC leaves behind.
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

TABLE = "move_records"

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
        ("customers", "0028_cr039_wd_transfer_and_case_numbers"),
        ("identity", "0004_rls_security_policies"),
        ("tenancy", "0021_cr039_wave_f_commercial_model"),
    ]

    operations = [
        migrations.CreateModel(
            name="MoveRecord",
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
                ("move_no", models.TextField(blank=True, null=True)),
                ("kind", models.TextField()),
                ("effective_on", models.DateField()),
                ("performed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("reads_committed", models.SmallIntegerField(default=0)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="customers.account",
                    ),
                ),
                (
                    "from_account",
                    models.ForeignKey(
                        blank=True,
                        db_column="from_account_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="customers.account",
                    ),
                ),
                (
                    "performed_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="performed_by",
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
                "db_table": "move_records",
                "indexes": [
                    models.Index(
                        fields=["tenant", "account", "-performed_at"], name="ix_move_rec_account"
                    ),
                    models.Index(
                        fields=["tenant", "from_account"], name="ix_move_rec_from_account"
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("kind__in", ("move_in", "move_out"))),
                        name="ck_move_record_kind",
                    ),
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("move_no"),
                        condition=models.Q(("move_no__isnull", False)),
                        name="uq_move_records_tenant_move_no_ci",
                    ),
                ],
            },
        ),
        # THE POLICY — after the CreateModel, which is what makes FORCE apply to
        # a table that exists and is still empty.
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]
