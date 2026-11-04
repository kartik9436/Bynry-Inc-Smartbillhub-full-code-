# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.6` (2026-09-24) — *"Create the lookup; FK
#           from `tenants.currency`; drop `default="USD"` on
#           `journal_entries.currency` and make it NOT NULL. ⚠ 27 free-text
#           columns exist — this phase converts the two on the money path, not
#           all 27."* Outcome: *"The database refuses an unstamped currency, as
#           `posting.py` already does in Python."*
# Rules:    `OQ-031` (CLOSED → `BR-TEN-036`, PO R6: *enums → lookup tables,
#           seeded defaults, tenant-extensible*) · `BR-TEN-042` (the seeded
#           currency choices) · `BR-TEN-021` (a currency change is
#           forward-only) · CLAUDE.md hard rule 2 (`CHAR(3)`, never a float)
# Tests:    06-backend/tests/test_p0_6_currency_lookup.py
# ───────────────────────────────────────────────────────
"""tenancy 0050 — **what a currency is, written down once.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering, and this one
constrains a money column. Ledger row:
`12-governance/09-human-review-ledger.md`, *"What a currency is, written down
once"*.

WHAT WAS MISSING — MEASURED, NOT ASSERTED
------------------------------------------
Counted from `information_schema` on 2026-09-24: **39 free-text currency
columns**, every one a bare `CharField(3)`, and **no table anywhere saying what
a currency is**. The lawful set lived in a Python tuple in one module
(`tenancy.services.SEED_CURRENCIES`); the symbols lived in a second constant in
`apps/reports/dashboard_format.py`; nothing linked a stored value to either.

⚠ **THE BLUEPRINT SAYS 27. THERE ARE 39** — it was written before the
settlement, counter and correction tables landed. Recorded so the next reader
counts rather than quotes.

WHAT THIS DOES, AND WHAT IT DELIBERATELY DOES NOT
---------------------------------------------------
1. **CREATE `currencies`** — keyed by the CODE, not a surrogate uuid, which is
   what makes it usable at all: 39 columns already hold a `CHAR(3)`, and a uuid
   key would have required rewriting every one of them before a single column
   could reference anything.
2. **SEED the five** `SEED_CURRENCIES` already allows, with the symbols
   `dashboard_format.CURRENCY_SYMBOLS` already renders. Nothing a user can see
   changes: the same five were lawful yesterday.
3. **Two foreign keys, on the money path and nowhere else** —
   `tenants.currency` and `journal_entries.currency`. **Not all 39**, exactly
   as `P0.6` instructs, because the other 37 are a separate piece of work with
   its own blast radius and no task scheduled for it.

⚠ **`journal_entries.currency` IS ALREADY `NOT NULL` WITH NO DATABASE DEFAULT**
— measured before this was written, so the half of `P0.6`'s cell that asks for
that is **already done** and this migration does not pretend to do it. What is
left of that clause is the MODEL, which still carried `default="USD"`; that is
`P0.7`'s, in `apps/ledger/models.py`, and it is where a defaulted currency
could actually enter the books.

NO ORPHANS, PROVED FIRST
-------------------------
Measured on the seeded database (PostgreSQL 16.13, 2026-09-24): `tenants` holds
one row at `USD`; `journal_entries` holds 167, all `USD`. Both codes are seeded
here, so both constraints validate cleanly — and `ADD CONSTRAINT` would refuse
the migration if either did not.

⚠ **SEEDING RUNS BEFORE THE CONSTRAINTS, AND THE ORDER IS THE MIGRATION.** A
foreign key added before the five rows exist would refuse every row already in
the books.

⚠ **NO RLS POLICY, AND THAT IS THE CORRECT ANSWER RATHER THAN AN OMISSION.**
This is PLATFORM reference data with no `tenant_id`, like `subscription_plans`
and unlike `account_statuses`. It could not be tenant-scoped even if we wanted
it: `tenants.currency` references it, and `tenants` is the table every
tenant-scoped row hangs off — a tenant-scoped `currencies` would have to exist
before the tenant that scopes it. `G5`'s RLS-exempt sweep should see it as one
more platform catalog, which is what it is.

REVERSIBLE, AND THE REVERSE INVENTS NOTHING
-------------------------------------------
The constraints drop, then the table. **The reverse deletes the five seeded
rows with the table**, which is lawful precisely because nothing else can point
at them by then — the foreign keys are gone first, and `services.
active_currency_codes()` falls back to `SEED_CURRENCIES`, the same five values,
so the product goes on refusing exactly what it refuses now. Proved forward →
back → forward on real PostgreSQL.

**SQLite (the default test tier) gets the TABLE and the seed and not the two
foreign keys** — `ALTER TABLE … ADD CONSTRAINT` does not exist there
(`ledger/0005`'s posture), so the table and its rows are real everywhere and
the database-level refusal is asserted only where it can exist.
"""

from django.db import migrations, models

#: The five, frozen here rather than read from `services.SEED_CURRENCIES`:
#: `customers/0069`'s reasoning — a migration that consulted a live constant
#: would silently change meaning the next time the constant moved. The symbols
#: are transcriptions of `Intl.NumberFormat("en-US", {style: "currency"})`,
#: identical to `apps/reports/dashboard_format.CURRENCY_SYMBOLS`.
SEED = (
    ("USD", "US Dollar", "$", 2, 10),
    ("CAD", "Canadian Dollar", "CA$", 2, 20),
    ("MXN", "Mexican Peso", "MX$", 2, 30),
    ("EUR", "Euro", "€", 2, 40),
    ("GBP", "Pound Sterling", "£", 2, 50),
)

FOREIGN_KEYS = (
    ("fk_tenants_currency", "tenants", "currency", "currencies", "code"),
    ("fk_journal_entries_currency", "journal_entries", "currency", "currencies", "code"),
)


def _seed(apps_registry, _schema_editor):
    Currency = apps_registry.get_model("tenancy", "Currency")
    for code, name, symbol, minor_units, sort in SEED:
        # INSERT-MISSING, never UPDATE — `customers/0003`'s rule. A row an
        # operator has already edited (a symbol, a sort order) is left exactly
        # as it is, so re-applying is a no-op.
        Currency.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "symbol": symbol,
                "minor_units": minor_units,
                "is_active": True,
                "sort": sort,
            },
        )


def _unseed(apps_registry, _schema_editor):
    """Remove only the five rows THIS migration seeded.

    A currency a platform operator added afterwards is not ours to delete, and
    a `DELETE FROM currencies` would take it. The table is dropped immediately
    after by the reverse of `CreateModel` anyway; this keeps the data step's
    own reverse honest about what it owns.
    """
    Currency = apps_registry.get_model("tenancy", "Currency")
    Currency.objects.filter(code__in=[row[0] for row in SEED]).delete()


def _add_foreign_keys(_apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        for name, table, column, target, target_column in FOREIGN_KEYS:
            cursor.execute(
                f"ALTER TABLE {table} ADD CONSTRAINT {name} "
                f"FOREIGN KEY ({column}) REFERENCES {target}({target_column}) "
                "DEFERRABLE INITIALLY DEFERRED"
            )


def _drop_foreign_keys(_apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        for name, table, *_rest in FOREIGN_KEYS:
            cursor.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0049_p0_4_gl_pointers_become_foreign_keys"),
        # `journal_entries` must exist before anything constrains its currency.
        ("ledger", "0001_w5_journal_core"),
    ]

    operations = [
        migrations.CreateModel(
            name="Currency",
            fields=[
                ("code", models.CharField(max_length=3, primary_key=True, serialize=False)),
                ("name", models.TextField()),
                ("symbol", models.TextField()),
                ("minor_units", models.IntegerField(default=2)),
                ("is_active", models.BooleanField(default=True)),
                ("sort", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "currencies", "ordering": ("sort", "code")},
        ),
        # ⚠ SEED BEFORE CONSTRAIN. A foreign key added before the five rows
        # exist would refuse every row already in the books.
        migrations.RunPython(_seed, _unseed),
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(_add_foreign_keys, _drop_foreign_keys)],
            state_operations=[],
        ),
    ]
