"""customers 0022 — CR-030 W7 task 7.5: the three disconnect tables + their RLS.

HUMAN-OWNED (migration ordering AND RLS policy are CLAUDE.md rule-1 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-25 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). ⚠ **A ROW IN
`12-governance/09-human-review-ledger.md` IS OWED AND THIS LANE DOES NOT OWN
THAT FILE.** G7 globs `06-backend/apps/*/migrations/0*.py`, so **G7 FAILS on
this file until the row exists** — reported with this exact path rather than
smoothed over. Not RATIFIED without a recorded human sign-off.

THE THREE
─────────
  disconnect_cases · disconnect_notices · account_protections

Their columns, their three protection LIFETIMES and the reason each constraint
exists are documented on the models in `apps/customers/disconnects.py`, which is
also where the reason these classes are not in `apps/customers/models.py` is
recorded (another lane held that file; `apps/payments/collections_models.py` and
`bankrec_models.py` set the precedent and give the reason: *"two lanes in one
models module is how a migration graph forks"*).

⚠ **ONE LINE IS OWED IN `apps/customers/models.py`, AND UNTIL IT LANDS THIS
MIGRATION IS IN DRIFT.** Measured 2026-08-25: `makemigrations --check --dry-run`
proposes **DELETING** `DisconnectCase`, `DisconnectNotice` and
`AccountProtection` by name, because a model is registered by IMPORTING the
module that defines it and Django imports `apps.customers.models` and nothing
else. The tables this migration creates would be correct on disk while CI kept
proposing to drop them. The fix is the last line of `models.py`:

    from apps.customers import disconnects  # noqa: E402,F401  (registers three models)

`apps/rating/models.py` already ends with exactly that line for
`apps/rating/discounts.py`, and says why: *"deleting it silently un-defines six
tables."* Another lane's file, so REPORTED with the precedent rather than
worked around — and guarded by
`tests/test_w7_disconnects.py::test_customers_models_registers_the_three_disconnect_models`,
which xfails until the line exists.

WHY THE RLS IS IN THIS MIGRATION AND NOT A SEPARATE `_rls_` ONE
───────────────────────────────────────────────────────────────
The repo's convention is a separate policy migration (0017 → 0018, 0019 → 0020),
and it is the better shape. This lane was scoped to ONE migration, so the
policies ride here — stated rather than left to be noticed. **The DEF-622 hazard
does not apply:** that defect is a DATA STEP that clears tenant context inside a
migration, poisoning the deferred-FK validation Django runs at the migration's
exit. There is NO data step here and nothing to seed, and the three tables are
empty when their FKs are validated, so the RI scan reads no rows at all. ⚠ A
later data step in this file would reintroduce exactly that failure, and if one
is ever added it must leave the NIL SENTINEL
`00000000-0000-0000-0000-000000000000` behind rather than `''` (OQ-354).

⚠ **THE POLICY IS THE `NULLIF` FORM, NOT THE BARE CAST — DEF-639.**

    NULLIF(current_setting('app.tenant_id', true), '')::uuid

`, true` makes an unset GUC return NULL instead of RAISING; `NULLIF(…, '')`
turns the empty string into NULL; `tenant_id = NULL` is NULL, which is not TRUE,
so no row is visible and no row may be written. Deny-by-default (hard rule 1)
is unchanged; what changes is that an absent tenant marker no longer bricks a
fresh `migrate`. G41 ratchets this form and these tables are born in it.

WHY EACH OF THE THREE NEEDS THE POLICY, IN ITS OWN TERMS
────────────────────────────────────────────────────────
* `disconnect_cases` — a list of the households one utility is about to cut off,
  with the date. Across a tenant boundary a READ is a competitor's arrears book;
  a WRITE schedules somebody else's customer for disconnection.
* `disconnect_notices` — the append-only record a utility shows a regulator when
  a customer says they were never told. A cross-tenant INSERT forges that
  record; a cross-tenant read discloses who is being chased.
* `account_protections` — **a medical certificate is a clinical fact about a
  named person.** It is the most sensitive row this module writes, and a
  cross-tenant DELETE of one lifts the hold that keeps someone's power on.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. G5's isolation suite proves the policies under a
NON-SUPERUSER probe role, because the app connects as a superuser and superusers
bypass RLS unconditionally, which makes any assertion made on the app's own
connection vacuous (`tests/isolation_helpers.py`).

⚠ **THIS MIGRATION DEPENDS ON `0021_cr030_w7_transfers`, WHICH WAS UNCOMMITTED
IN THE SHARED TREE WHEN THIS FILE WAS WRITTEN (2026-08-25).** W7 task 7.1's
lane is building it beside this one. The dependency is deliberate and is the
LINEAR one: pointing this migration at `0020` instead would leave `customers`
with TWO LEAF NODES, and `migrate` refuses a forked graph ("Conflicting
migrations detected") until somebody writes a merge migration. **So the two must
land in order — 0021 first — and if that lane renames or abandons its file, this
one's `dependencies` must be re-pointed in the same commit.** REPORTED, because
migration ordering is a 🔒 path and a fork found at deploy time is found by a
deploy that fails.

ROLLBACK
────────
Additive and reversible: `PostgresOnlySQL` carries `reverse_sql` that drops each
policy and takes FORCE off, and the three `CreateModel`s reverse to drops. No
data is written by this migration, so nothing is lost by reversing it.
"""

# Generated by Django 5.2.17 on 2026-08-25

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

DISCONNECT_TABLES = ("disconnect_cases", "disconnect_notices", "account_protections")


def _policy(table: str) -> str:
    return f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""


def _reverse(table: str) -> str:
    return f"""
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0021_cr030_w7_transfers"),
        ("identity", "0004_rls_security_policies"),
        ("tenancy", "0018_br_cus_092_ein_encrypted"),
    ]

    operations = [
        migrations.CreateModel(
            name="DisconnectCase",
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
                ("sequence", models.TextField(default="service")),
                ("state", models.TextField(default="notice_sent")),
                ("tier", models.TextField(blank=True, null=True)),
                ("tier_reached_on", models.DateField(blank=True, null=True)),
                ("amount_owed_at_open", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency", models.CharField(max_length=3)),
                ("opened_on", models.DateField()),
                ("next_step_due", models.DateField(blank=True, null=True)),
                ("cut_scheduled_for", models.DateField(blank=True, null=True)),
                ("cut_on", models.DateField(blank=True, null=True)),
                ("reconnected_on", models.DateField(blank=True, null=True)),
                ("stopped_on", models.DateField(blank=True, null=True)),
                ("stopped_reason", models.TextField(blank=True, null=True)),
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
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "disconnect_cases",
            },
        ),
        migrations.CreateModel(
            name="DisconnectNotice",
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
                ("tier", models.TextField()),
                ("delivery_state", models.TextField(blank=True, null=True)),
                ("delivery_unavailable_reason", models.TextField(blank=True, null=True)),
                ("issued_on", models.DateField()),
                ("detail", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        db_column="actor_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.user",
                    ),
                ),
                (
                    "case",
                    models.ForeignKey(
                        db_column="case_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notices",
                        to="customers.disconnectcase",
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
                "db_table": "disconnect_notices",
            },
        ),
        migrations.CreateModel(
            name="AccountProtection",
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
                ("effective_from", models.DateField()),
                ("expires_on", models.DateField(blank=True, null=True)),
                ("set_by", models.TextField(default="tenant")),
                ("reference_id", models.UUIDField(blank=True, null=True)),
                ("note", models.TextField(blank=True, null=True)),
                ("lifted_on", models.DateField(blank=True, null=True)),
                ("lifted_reason", models.TextField(blank=True, null=True)),
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
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "account_protections",
                "indexes": [
                    models.Index(
                        fields=["tenant", "account", "kind"], name="ix_protection_account"
                    ),
                    models.Index(fields=["tenant", "expires_on"], name="ix_protection_expiry"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "kind__in",
                                ("medical_certificate", "payment_plan", "weather_moratorium"),
                            )
                        ),
                        name="ck_protection_kind",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("expires_on__isnull", False), ("kind", "medical_certificate")
                            ),
                            models.Q(("expires_on__isnull", True), ("kind", "payment_plan")),
                            models.Q(("expires_on__isnull", False), ("kind", "weather_moratorium")),
                            _connector="OR",
                        ),
                        name="ck_protection_lifetime",
                    ),
                ],
            },
        ),
        migrations.AddIndex(
            model_name="disconnectcase",
            index=models.Index(fields=["tenant", "state"], name="ix_dsc_case_state"),
        ),
        migrations.AddIndex(
            model_name="disconnectcase",
            index=models.Index(fields=["tenant", "cut_scheduled_for"], name="ix_dsc_case_cut_date"),
        ),
        migrations.AddConstraint(
            model_name="disconnectcase",
            constraint=models.UniqueConstraint(
                condition=models.Q(("state__in", ("stopped", "restored")), _negated=True),
                fields=("tenant", "account"),
                name="uq_one_open_disconnect_case_per_account",
            ),
        ),
        migrations.AddConstraint(
            model_name="disconnectcase",
            constraint=models.CheckConstraint(
                condition=models.Q(("sequence__in", ("service", "collections"))),
                name="ck_disconnect_case_sequence",
            ),
        ),
        migrations.AddConstraint(
            model_name="disconnectcase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "state__in",
                        (
                            "notice_sent",
                            "scheduled",
                            "on_hold",
                            "cut",
                            "reconnecting",
                            "stopped",
                            "restored",
                        ),
                    )
                ),
                name="ck_disconnect_case_state",
            ),
        ),
        migrations.AddConstraint(
            model_name="disconnectcase",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("sequence", "collections"), _negated=True),
                    models.Q(("cut_on__isnull", True), ("cut_scheduled_for__isnull", True)),
                    _connector="OR",
                ),
                name="ck_collections_sequence_never_cuts",
            ),
        ),
        migrations.AddIndex(
            model_name="disconnectnotice",
            index=models.Index(fields=["tenant", "case", "issued_on"], name="ix_dsc_notice_case"),
        ),
        migrations.AddConstraint(
            model_name="disconnectnotice",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("tier__in", ("tier_1_reminder", "tier_2_10_day", "tier_3_48_hour"))
                ),
                name="ck_disconnect_notice_tier",
            ),
        ),
    ] + [
        # THE POLICIES — one per table, in the DEF-639 `NULLIF` form. They run
        # AFTER the three CreateModels above, which is what makes the FORCE
        # policy apply to tables that already exist and are still empty.
        PostgresOnlySQL(_policy(table), reverse_sql=_reverse(table))
        for table in DISCONNECT_TABLES
    ]
