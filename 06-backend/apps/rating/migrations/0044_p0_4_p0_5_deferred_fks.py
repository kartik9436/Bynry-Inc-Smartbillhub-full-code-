# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.4` / `P0.5` / `P0.12` (2026-09-24). Rating's
#           half: five GL pointers, and three of the four remaining deferred
#           FKs. Outcome: *"Ten deferred FKs become zero"*.
# Rules:    `B11 F-3` (the DEFERRED-FK convention) · `B2 §2` (cross-module FKs
#           are the reviewed interface set) · `BR-CUS-1010` · CLAUDE.md hard
#           rule 1 (no RLS policy is touched)
# Tests:    06-backend/tests/test_p0_4_gl_pointers_are_foreign_keys.py ·
#           06-backend/tests/test_def_rat_6494_deferred_fks_not_valid_pg.py
# Defect:   DEF-RAT-6494 — this file killed a production deploy on the day it
#           landed. See the `NOT VALID` section of the docstring.
# ───────────────────────────────────────────────────────
"""rating 0044 — **every deferred pointer in this module becomes real.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering. Ledger row:
`12-governance/09-human-review-ledger.md`, *"A stale GL account id is refused
when it is saved"*.

WHAT THIS DOES — EIGHT CONSTRAINTS, IN TWO GROUPS
--------------------------------------------------
**`P0.4` — the GL pointers → `ledger_accounts`:**

    charges.gl_account_id
    plan_services.gl_account_id
    discounts.gl_account_id
    taxes.liability_gl_account_id
    taxes.collection_allowance_gl_account_id

**`P0.5` — the remaining deferred FKs, out of this module into three others:**

    tax_exemption_certificates.account_id     -> customers.accounts
    tax_exemption_certificates.verified_by_id -> identity.users
    plan_deposit_rules.account_type_id        -> customers.account_types

⚠ **THE BLUEPRINT COUNTS THREE GL POINTERS IN RATING AND THERE ARE FIVE.**
`P0.4`'s row names *"rating.gl_account_id ×2 · rating.liability_gl_account_id"*
and p083 totals *"six GL pointers as bare UUIDs — billing · rating ×3 ·
tenancy ×2"*. Measured from the code on 2026-09-24, the modules the blueprint
names hold **nine**, not six: billing 2, rating 5, tenancy 2. The two the
document does not count in this module are `discounts.gl_account_id` — where
the PO ruled on 2026-08-28 that a reduction posts to a GL code of its own — and
`taxes.collection_allowance_gl_account_id`. **Both are money paths, and
converting three of five would leave two doors open while the outcome sentence
claims they are shut.** All five are done here, the discrepancy is recorded in
the decision log, and `DEF-LED-6483` counts it so it is not a finding that
lives only in this docstring.

⚠ THE CONSTRAINTS ARE ADDED `NOT VALID` — `DEF-RAT-6494`, 2026-09-24
---------------------------------------------------------------------
**THIS MIGRATION KILLED A PRODUCTION DEPLOY ON THE DAY IT LANDED.** It added
all eight VALIDATING, the eighth met a real orphaned row, PostgreSQL refused
it, and the container could not start:

    Applying rating.0044_p0_4_p0_5_deferred_fks...
    django.db.utils.IntegrityError: insert or update on table "plan_deposit_rules"
    violates foreign key constraint "fk_plan_deposit_rules_account_type"
    DETAIL:  Key (account_type_id)=(01a07f66-1139-79aa-a657-0afb2f867087) is not
             present in table "account_types".

**WHERE THAT ROW CAME FROM, AND IT IS NOT A BUG IN ANY WRITER.** That id is a
uuid7 whose timestamp decodes to **2026-09-08 05:03:10 UTC** — a PLATFORM-era
`account_types` row. `customers/0054` turned `account_types` from a platform
table into a per-tenant one: it cloned every platform row per tenant,
repointed the referencing rows, and deleted the platform rows. **Its repoint
list is `REFERENCING = ("Account", "AccountSubtype", "ServiceRequest")` and
`plan_deposit_rules` is not in it** — this column is a bare `UUIDField` with no
foreign key, so nothing refused, `0054`'s own "stranded" guard could not see
it, and the value was left naming a row that no longer exists. **It is exactly
`DEF-RAT-5823`'s root cause, one table further on**, and `0041` repaired only
`rate_plans.account_type_ids`.

**SO THE ROWS ARE NOT CHECKED HERE AND THE CONSTRAINT SAYS SO.** `NOT VALID`
skips the scan of existing rows and PostgreSQL marks the constraint
`convalidated = false`. **Everything forward still holds, measured on
PostgreSQL 16.13 on 2026-09-24 and asserted in
`tests/test_def_rat_6494_deferred_fks_not_valid_pg.py`:** a new INSERT with an
unknown id is refused, a new UPDATE to an unknown id is refused, and DELETING a
referenced parent row is refused. Only the rows already at rest go unexamined.
**Nothing anywhere may call these constraints validated until somebody runs
`VALIDATE CONSTRAINT`** — that is a separate migration, and it is owed once the
existing rows have been ruled on (`OQ-RAT-12633`: a deposit rule is a money
path, `BR-RAT-020/023`, and no lane may delete or repoint one).

MEASUREMENT — ONE DATABASE, ONE DATE, AND NOT A FACT ABOUT YOURS
-----------------------------------------------------------------
⚠ **THE TABLE BELOW IS A MEASUREMENT OF ONE DATABASE ON ONE DATE. IT IS NOT A
PROPERTY OF EVERY DATABASE AND MUST NEVER BE READ AS ONE.** It is what the
seeded dev database held on **2026-09-24** (PostgreSQL 16.13, tenant
`brazosbend`) — a database migrated from empty that same morning, which has
never had `account_types` rebuilt under it and **holds zero
`plan_deposit_rules` rows at all**. The counts are honest and were taken inside
a tenant context, which is the only way to take them: re-counted as superuser
on 2026-09-24 the same database still reports `plan_deposit_rules = 0` and
`charges = 31`. **The flaw is not the arithmetic, it is the scope** — `0 rows`
on a database with no history said nothing whatever about an environment that
has some, and this table was published as though it had. Counted as
`rows / set / orphans`:

    charges.gl_account_id                          31 / 29 / 0
    plan_services.gl_account_id                    10 /  0 / 0
    discounts.gl_account_id                         6 /  6 / 0
    taxes.liability_gl_account_id                   2 /  2 / 0
    taxes.collection_allowance_gl_account_id        2 /  0 / 0
    tax_exemption_certificates.account_id           0 /  0 / 0
    tax_exemption_certificates.verified_by_id       0 /  0 / 0
    plan_deposit_rules.account_type_id              0 /  0 / 0

**THE OTHER SEVEN HAVE THE IDENTICAL EXPOSURE AND ARE ALL `NOT VALID` TOO.**
They survived the deploy that the eighth killed, which is evidence about that
one database and about nothing else. Converting only the column that happened
to fail would leave seven doors to the same failure open on the next deploy.

⚠ **AND `ADD CONSTRAINT` IS *NOT* ITS OWN PROOF — THIS FILE SAID IT WAS.**
The sentence removed here read *"the constraint is its own proof: ADD
CONSTRAINT … FOREIGN KEY validates every existing row and PostgreSQL refuses
the migration if one id names nothing."* **It is false under `FORCE ROW LEVEL
SECURITY`, which every one of these tables carries.** PostgreSQL validates a
new foreign key with an ordinary scan, and that scan is evaluated against the
`B2 §3` policy like any other read. The migration role carries
`app.tenant_id = 00000000-0000-0000-0000-000000000000` — the NO-TENANT
sentinel — in its own `rolconfig`, so the scan matches **no row of any
tenant**. Measured on PostgreSQL 16.13 on 2026-09-24, with one real orphan
present: `manage.py migrate` **exited 0**, the constraint came out
`convalidated = t`, and **the orphan was still there**. So the same statement
dies on a role that can see the rows and silently certifies nothing on the role
that actually runs migrations. `NOT VALID` is the honest form of what was
happening anyway.

⚠ **`plan_deposit_rules.account_type_id` IS `NOT NULL`, SO THERE IS NO REPAIR
THAT COSTS NOTHING.** A bad id cannot be NULLed out, and DELETING the row
changes a utility's standard deposit figure for a class of customer — money,
on a signed rule. That is why nothing here touches a row.

WHY THE MODELS DO NOT BECOME `ForeignKey` FIELDS — see `billing/0030`
----------------------------------------------------------------------
Same reasoning, stated once there: this is `SeparateDatabaseAndState` with
database operations only, because what `P0.4` asks for is that the DATABASE
refuse a bad id, and changing the Python field type is a wide hand-verified
rename across modules other lanes are editing today, in exchange for nothing
the constraint does not already give. The delete behaviour is PostgreSQL's
`NO ACTION` — it REFUSES the deletion of a referenced row, which is the answer
`on_delete=PROTECT` gives, reached from the database side.

REVERSIBLE; SQLITE KEEPS THE PLAIN COLUMNS
-------------------------------------------
`DROP CONSTRAINT IF EXISTS` for each, creating and deleting no row in either
direction. `ALTER TABLE … ADD CONSTRAINT` does not exist on SQLite (the default
test tier), so nothing is written there and no fake guarantee is installed —
`ledger/0005`'s posture. The live assertions are the PostgreSQL suite's.
"""

from django.db import migrations

#: (constraint name, table, column, referenced table). Frozen text, never
#: derived from the live models.
FOREIGN_KEYS = (
    # P0.4 — the GL pointers
    ("fk_charges_gl_account", "charges", "gl_account_id", "ledger_accounts"),
    ("fk_plan_services_gl_account", "plan_services", "gl_account_id", "ledger_accounts"),
    ("fk_discounts_gl_account", "discounts", "gl_account_id", "ledger_accounts"),
    ("fk_taxes_liability_gl_account", "taxes", "liability_gl_account_id", "ledger_accounts"),
    (
        "fk_taxes_collection_allowance_gl_account",
        "taxes",
        "collection_allowance_gl_account_id",
        "ledger_accounts",
    ),
    # P0.5 — the remaining deferred FKs
    ("fk_tax_exemption_certificates_account", "tax_exemption_certificates", "account_id", "accounts"),
    (
        "fk_tax_exemption_certificates_verified_by",
        "tax_exemption_certificates",
        "verified_by_id",
        "users",
    ),
    ("fk_plan_deposit_rules_account_type", "plan_deposit_rules", "account_type_id", "account_types"),
)


def add_sql(name: str, table: str, column: str, target: str) -> str:
    """The EXACT statement `_add` runs, as one string.

    Factored out for `DEF-RAT-6494` so the PostgreSQL proof executes what this
    migration executes rather than a copy of it that can drift away from it —
    `tests/test_def_rat_6494_deferred_fks_not_valid_pg.py` imports this. **The
    `NOT VALID` at the end is the fix; see the docstring above.**
    """
    return (
        f"ALTER TABLE {table} ADD CONSTRAINT {name} "
        f"FOREIGN KEY ({column}) REFERENCES {target}(id) "
        "DEFERRABLE INITIALLY DEFERRED NOT VALID"
    )


def _add(_apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        for name, table, column, target in FOREIGN_KEYS:
            cursor.execute(add_sql(name, table, column, target))


def _drop(_apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        for name, table, _column, _target in FOREIGN_KEYS:
            cursor.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0043_cr130_percent_basis"),
        # Every referenced table must exist before anything points at it.
        ("ledger", "0001_w5_journal_core"),
        ("customers", "0070_p0_2_primary_holder"),
        ("identity", "0005_cr070_f_field_technician"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(_add, _drop)],
            state_operations=[],
        ),
    ]
