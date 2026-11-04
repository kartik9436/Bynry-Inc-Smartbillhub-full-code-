# ── Trace ──────────────────────────────────────────────
# Change:   OQ-421 CLOSED 2026-08-27 — store the twelve-month usage PER METER
#           as well. PO verbatim: *"(b) Store it per meter too - otherwise we
#           will ahve to calculate it again and again"*.
#           Screens: S50 (the meter's Reads-tab rollup strip)
# Rules:    BR-MET-141 (NEW — the per-meter stored grain) · BR-MET-106 (the
#           account grain this mirrors) · CLAUDE.md hard rule 1 (RLS in the
#           SAME migration — see below) · hard rule 3 (an explicit unit) ·
#           hard rule 4 (corrections are new rows) · rule 6 (idempotency)
# Defects:  DEF-798 (the register-blind sum — the grain of this table IS the
#           fix: 684 and 14 are two rows, and 698 is not representable)
# Tests:    06-backend/tests/test_oq_421_per_meter_monthly_usage.py
# Impacts:  apps/metering/monthly_usage_asset.py (the model, managed=False) ·
#           apps/metering/monthly_usage_service.py (the SOLE writer)
# ───────────────────────────────────────────────────────
"""metering 0039 — `meter_read_asset_monthly_usage`, BR-MET-141's stored grain.

HUMAN-OWNED (migration ordering AND RLS policies are CLAUDE.md 🔒 paths).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-27 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). A row IS APPENDED in
`12-governance/09-human-review-ledger.md` for this file. Not RATIFIED without a
recorded human sign-off.

**WHAT A REVIEWER IS BEING ASKED TO CONFIRM**, in plain English with the figure:

  1. **That a derived number is stored at a SECOND grain.** The account already
     stores one row per (account, service, month). This adds one row per
     (meter, register, month). The PO ruled for it on 2026-08-27 — *"(b) Store
     it per meter too - otherwise we will ahve to calculate it again and
     again"* — with the irreversibility stated to them in OQ-421 first.
  2. **The worked figure.** Sarah's meter M-4412 reports a 684 kWh energy total
     and a 14 kW demand peak on the same July day. This table stores **TWO
     rows** — `total 684.000000 kWh` and `demand 14.000000 kWh` — and the
     account's own BR-MET-106 row stores **684.000000 kWh**. **698 appears
     nowhere**, and cannot: the register is part of the key, so no row in this
     table is a sum across registers. That is DEF-798's measured defect made
     unrepresentable rather than merely fixed.
  3. **That nothing bills off it.** No rate, no invoice line and no charge
     reads this table. It serves the S50 strip and nothing else.
  4. **That reversing it loses a CACHE, not a FACT.** Every column is derivable
     from `meter_reads`; the S50 payload computes the identical figure when no
     row exists. Dropping this table returns the product to its 2026-08-26
     behaviour and loses no statement about any customer.

ADDITIVE ONLY: one new table, no existing table altered, **nothing backfilled**
(the table is EMPTY after this migration and fills the first time
`monthly_usage_service.recompute_account` runs — the same trigger the account
grain already rides, so the two grains can never be stale relative to each
other).

⚠ **RLS IS IN THIS SAME MIGRATION, NOT THE NEXT ONE.** Metering 0024/0025 and
0033/0034 each split the table and its policy across a pair, and each documents
that the pair must be applied together because a tenant table with no policy is
a rule-1 violation in between. This lane was allocated ONE migration number
(0039) by the orchestrator, so the split is not available — and the un-split
form is strictly safer: there is no instant at which the table exists without
`FORCE ROW LEVEL SECURITY`.

⚠ **NUMBERED 0039 BY ALLOCATION, AND 0038 IS A SIBLING LANE'S.** A lane
building register units and multipliers holds `0038` in the same session and
its file is not on this branch, so this migration depends on `0037`, which is
the highest number actually present here (measured: `ls
apps/metering/migrations/`). **AT MERGE THE INTEGRATOR MUST RE-POINT THIS
`dependencies` LIST AT 0038**, or Django reports *"Conflicting migrations
detected; multiple leaf nodes in the migration graph"*. Linearise, do not add a
merge node — rating 0018 records the same call and the reason: a merge node is
a no-op that documents nothing, and both migrations are purely additive so the
order carries no meaning to recover.

⚠ **NOT PARTITIONED, DELIBERATELY.** `meter_reads` is (DB-7/NFR-24). This table
grows with (meters × registers × months), which OQ-421 measured as the real
cost of answer B — it is larger than the account grain by exactly that factor
and still orders of magnitude smaller than the read table for the
<3,000-connection utility this product serves.

⚠ **A STATE-ONLY `CreateModel` PLUS RAW DDL — AND THE PAIR IS THE WHOLE
DISPOSITION, SO READ IT BEFORE "SIMPLIFYING" EITHER HALF.**
`apps/metering/models.py` belongs to another lane this session, so the model
lives in `apps/metering/monthly_usage_asset.py` with `managed = False`.

  * **`CreateModel` FIRST, and it writes NO SQL.** Django refuses to migrate an
    unmanaged model (`_meta.can_migrate()` is false), so this operation records
    STATE and builds nothing. It is here because the model IS reachable at
    app-load — `monthly_usage_service` imports it — so the autodetector sees it,
    and without this operation `makemigrations --check` answers *"Create model
    AssetMonthlyUsage"* forever. **Measured on this branch, not assumed:** the
    check was clean before the writer imported the model and reported that line
    immediately after.
  * **`RunPython` SECOND, and it is what actually builds the table**, in the
    DDL of whichever vendor is connected — because the `CreateModel` above
    cannot.

**Nothing holds those two halves together except a test**, and that is the cost
of the split: `tests/test_oq_421_per_meter_monthly_usage.py::test_the_table_
matches_the_model` introspects the LIVE table and asserts a column for every
model field and no column the model does not declare. A column added to one
half and not the other goes RED there and nowhere else.
"""

import core.dbfields
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLE = "meter_read_asset_monthly_usage"

#: B2 §3's policy predicate with DEF-639's cast repair. `NULLIF(…, '')` makes an
#: unset GUC NULL rather than an empty string; `NULL = tenant_id` is NULL and a
#: policy evaluating to NULL admits NOTHING, so the guarantee is identical to
#: the literal cast and it can no longer raise inside `migrate`. Metering 0025
#: carries the full account.
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POSTGRES_DDL = (
    f"""
    CREATE TABLE {TABLE} (
        id                     uuid          NOT NULL PRIMARY KEY,
        tenant_id              uuid          NOT NULL REFERENCES tenants(id),
        account_id             uuid          NOT NULL REFERENCES accounts(id),
        asset_id               uuid          NOT NULL REFERENCES assets(id),
        service_id             uuid          NULL     REFERENCES services(id),
        channel                text          NOT NULL,
        period_month           date          NOT NULL,
        quantity               numeric(18,6) NOT NULL,
        unit                   text          NOT NULL,
        read_count             integer       NOT NULL,
        estimated_read_count   integer       NOT NULL,
        source_read_ids        jsonb         NOT NULL,
        source_fingerprint     text          NOT NULL,
        computed_at            timestamptz   NOT NULL,
        superseded_by_id       uuid          NULL,
        superseded_at          timestamptz   NULL,
        supersede_reason       text          NULL,
        is_sample              boolean       NOT NULL,
        created_at             timestamptz   NOT NULL,
        updated_at             timestamptz   NOT NULL
    );
    """,
    # ONE live statement per meter per register per month — over lineage HEADS
    # only, so a RESTATEMENT is legal (hard rule 4) and a second simultaneous
    # head is not. Scoped on `superseded_by_id` alone, exactly as
    # `uq_monthly_usage_head` is, because a WITHDRAWN month has no successor to
    # point at and sets `superseded_at` only.
    f"""
    CREATE UNIQUE INDEX uq_asset_monthly_usage_head
        ON {TABLE} (tenant_id, asset_id, channel, period_month)
        WHERE superseded_by_id IS NULL;
    """,
    # The S50 strip's own query: one meter, twelve months, every register.
    f"""
    CREATE INDEX ix_asset_monthly_usage_asset_month
        ON {TABLE} (tenant_id, asset_id, period_month);
    """,
    # The account tie-out: every meter of one account for one month, which is
    # what holds the two grains against each other.
    f"""
    CREATE INDEX ix_asset_monthly_usage_acct_month
        ON {TABLE} (tenant_id, account_id, period_month);
    """,
)

#: sqlite DDL — the test database. Types are Django's own sqlite mappings
#: (UUIDField → char(32), DateTimeField → datetime, DecimalField → decimal,
#: JSONField → text, BooleanField → bool), so an ORM read/write over this table
#: behaves identically on both vendors.
SQLITE_DDL = (
    f"""
    CREATE TABLE {TABLE} (
        id                     char(32) NOT NULL PRIMARY KEY,
        tenant_id              char(32) NOT NULL REFERENCES tenants(id),
        account_id             char(32) NOT NULL REFERENCES accounts(id),
        asset_id               char(32) NOT NULL REFERENCES assets(id),
        service_id             char(32) NULL     REFERENCES services(id),
        channel                text     NOT NULL,
        period_month           date     NOT NULL,
        quantity               decimal  NOT NULL,
        unit                   text     NOT NULL,
        read_count             integer  NOT NULL,
        estimated_read_count   integer  NOT NULL,
        source_read_ids        text     NOT NULL,
        source_fingerprint     text     NOT NULL,
        computed_at            datetime NOT NULL,
        superseded_by_id       char(32) NULL,
        superseded_at          datetime NULL,
        supersede_reason       text     NULL,
        is_sample              bool     NOT NULL,
        created_at             datetime NOT NULL,
        updated_at             datetime NOT NULL
    );
    """,
    f"""
    CREATE UNIQUE INDEX uq_asset_monthly_usage_head
        ON {TABLE} (tenant_id, asset_id, channel, period_month)
        WHERE superseded_by_id IS NULL;
    """,
    f"""
    CREATE INDEX ix_asset_monthly_usage_asset_month
        ON {TABLE} (tenant_id, asset_id, period_month);
    """,
    f"""
    CREATE INDEX ix_asset_monthly_usage_acct_month
        ON {TABLE} (tenant_id, account_id, period_month);
    """,
)


def create_table(apps, schema_editor):  # type: ignore[no-untyped-def]
    """The table, in the DDL of whichever vendor is actually connected.

    Frozen text on both sides, on purpose: a migration that reached into the
    live model class for its DDL would silently change what it builds every
    time somebody edits the model, which is the Django anti-pattern that makes
    a fresh database and an upgraded one disagree about columns.
    """
    statements = POSTGRES_DDL if schema_editor.connection.vendor == "postgresql" else SQLITE_DDL
    for statement in statements:
        schema_editor.execute(statement)


def drop_table(apps, schema_editor):  # type: ignore[no-untyped-def]
    schema_editor.execute(f"DROP TABLE IF EXISTS {TABLE};")


POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""

REVERSE_POLICY = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    # ⚠ DEPENDS ON 0037 AND IS NAMED 0039 — see the module docstring. A sibling
    # lane holds 0038 on another branch; the integrator re-points this list at
    # it on merge, or Django refuses with "multiple leaf nodes".
    dependencies = [
        ("metering", "0037_cr038_w7_write_mode_cosign"),
    ]

    operations = [
        # STATE ONLY — Django will not migrate an unmanaged model, so this
        # builds nothing. It exists so the autodetector stops asking for it.
        # ⚠ The FK fields (tenant, account, asset, service) are deliberately
        # absent: Django omits related fields from an unmanaged model's state,
        # and adding them here by hand would make `makemigrations --check`
        # demand their removal. They are real columns in the DDL below and the
        # introspection test is what holds the two accounts of this table
        # together.
        migrations.CreateModel(
            name="AssetMonthlyUsage",
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
                ("channel", models.TextField()),
                ("period_month", models.DateField()),
                ("quantity", models.DecimalField(decimal_places=6, max_digits=18)),
                ("unit", models.TextField()),
                ("read_count", models.IntegerField()),
                ("estimated_read_count", models.IntegerField(default=0)),
                ("source_read_ids", models.JSONField(default=list)),
                ("source_fingerprint", models.TextField()),
                ("computed_at", models.DateTimeField()),
                ("superseded_by_id", models.UUIDField(blank=True, null=True)),
                ("superseded_at", models.DateTimeField(blank=True, null=True)),
                ("supersede_reason", models.TextField(blank=True, null=True)),
                ("is_sample", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "meter_read_asset_monthly_usage",
                "managed": False,
            },
        ),
        # THE TABLE ITSELF — the operation above cannot build it.
        migrations.RunPython(create_table, drop_table),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE_POLICY),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-421 as ruled 2026-08-27 (decision log item 12) + BR-MET-141 + DEF-798
# generated: 2026-08-27 by the OQ-421/OQ-422 lane
# checklist: A✔ B=deferred(policy+DDL only — the behaviour TCs assert through the writer) C✔ D=deferred(no-API-half — no new route) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row APPENDED)
# gates: makemigrations --check clean · ruff✔ black✔ · sqlite migrate applied (PostgresOnlySQL skips honestly)
# exceptions: E3 the DDL and the RLS policy are in ONE migration rather than the metering 0024/0025 pair — one number was allocated to this lane, and the un-split form leaves no instant where the table exists without FORCE RLS · E3 DEF-639's `NULLIF` predicate rather than B2 §3's literal cast (identical guarantee, see 0034's account) · E3 policy SQL inline rather than in 06-backend/db/ — the EIGHTH file to want the same relocation, REPORTED not resolved · E3 a STATE-ONLY `CreateModel` (unmanaged, so it writes no SQL) plus raw DDL that actually builds the table, because `apps/metering/models.py` is another lane's this session — the two halves are held together by the introspection test and by nothing else · E3 LIVE POSTGRES PROOF NOT RUN IN THIS CONTAINER — the G5 isolation sweep is the gate and is REPORTED as owed for this table
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
