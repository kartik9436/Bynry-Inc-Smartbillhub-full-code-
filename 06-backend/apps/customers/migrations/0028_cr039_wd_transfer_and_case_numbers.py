"""customers 0028 — `transfers.transfer_no` and `disconnect_cases.case_no`.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list and the ledger row for this file is in
`12-governance/09-human-review-ledger.md`. The marker is here because the PATH
is the category, not because the body is large (DEF-808).

CR-039 wave D tasks 15 and 16, verbatim: *"a series and number for transfer"*
and *"the same for disconnect"*, against the CR's own trace finding 5 —
*"Transfer and disconnect have tables and no number"*, consequence *"A clerk
cannot quote a reference; nothing on a bill can point at the job that caused a
change"*.

════════════════════════════════════════════════════════════════════════════
WHAT THIS MIGRATION DOES AND DELIBERATELY DOES NOT DO
════════════════════════════════════════════════════════════════════════════
It adds the two COLUMNS and their per-tenant uniqueness. **It does not add a
number series to `core.numbering.SERIES_CATALOG`, and no tenant is seeded one.**

That split is the whole point and it is not a deferral of convenience. A
series' seeded default is DERIVED FROM THE PROTOTYPE, never invented —
`core/numbering.py` says so of `CONNECTION` in its own words: the default is
`CON-{YY}-{0000}` *"because that is what the PO's own New Connect screens draw
— `CON-26-0110`, `CON-26-0117`, `CON-26-0119` (B18 §5.4.9)"*. **Measured
2026-08-27, B18 draws no number for either of these two:**

  · §5.7.2's transfer columns are `FROM ACCOUNT · CUSTOMER · FROM → TO · OUT
    DATE · IN DATE · STEP · MONEY · STATE` — no reference column; §5.7.6's five
    seeded rows and §5.7.7's five wizard steps carry account numbers only.
  · §5.8.2's disconnect columns are `ACCOUNT · CUSTOMER · ADDRESS · OWED · TIER
    · CUT DATE · LAST NOTICE · STATE` — the same; §5.8.6's nine rows likewise.
  · r10 holds no transfer record at all, and draws a disconnection as a WORK
    ORDER (*"Disconnect work order raised · WO-4833"*).

So the format is `OQ-426` (transfer) and `OQ-427` (disconnect), and DEF-615 is
what happens when two places each pick one independently. **The column is the
half that needs a migration; the format is a one-line catalogue row that needs
none.** Shipping the column now means that on the day either question closes,
every new record is numbered with no schema change and no downtime.

════════════════════════════════════════════════════════════════════════════
WHY THE TWO TABLES ARE TOUCHED IN TWO DIFFERENT WAYS
════════════════════════════════════════════════════════════════════════════
`transfers` is `managed = False` — its DDL is migration 0021's raw SQL and 0027
holds STATE ONLY (see both files). Django's schema editor is therefore not
keeping model and table in step for that table, so this migration must do
BOTH halves explicitly:

  · `RunPython(add_transfer_no, drop_transfer_no)` issues the real
    `ALTER TABLE`, in the DDL of whichever vendor is connected;
  · `AddField` puts `transfer_no` into migration STATE and, because
    `Meta.managed = False` makes `can_migrate()` False, issues no DDL of its
    own — there is no double-add.

`disconnect_cases` is an ordinary managed model, so its `AddField` and
`AddConstraint` are the whole story.

⚠ **AND THE TWO HALVES ARE GUARDED BY DIFFERENT THINGS — MEASURED, NOT
ASSUMED (hard-won law 1).** `makemigrations --check` catches only the
DISCONNECT half. Removing this whole file and re-running answers, verbatim:

    Migrations for 'customers':
      apps/customers/migrations/0028_disconnectcase_case_no_and_more.py
        + Add field case_no to disconnectcase
        + Create constraint uq_disconnect_cases_tenant_case_no_ci on model disconnectcase

— **and says nothing about `transfer_no`**, because Django's autodetector
compares only `CreateModel`/`DeleteModel` for an unmanaged model and never its
fields. So the `AddField` on `transfer` is there to keep STATE honest (0027 put
the rest of the field list in state and leaving one out would make state lie),
and it is NOT what would catch its absence.

**What catches the unmanaged half is the introspection test**, and it was
PROVED RED before being trusted green: with the `RunPython` above removed and
the model field left in place,
`tests/test_w7_transfers.py::test_tc_trf_12_the_model_and_the_live_table_agree_column_for_column`
fails with

    AssertionError: model fields with no column: {'transfer_no'}
    assert {'transfer_no'} == set()

════════════════════════════════════════════════════════════════════════════
UNIQUENESS IS PER TENANT, CASE-INSENSITIVE, AND ONLY WHERE A NUMBER EXISTS
════════════════════════════════════════════════════════════════════════════
The shape is `customers 0013`'s `uq_customers_tenant_customer_no_ci`, for the
same reasons: BR-TEN-035 says a number is never reused, a clerk who types
`trf-26-0001` means the row that reads `TRF-26-0001`, and **the partial
predicate is what lets the column exist while the series does not** — every
row is NULL today and NULLs must not collide with each other.

⚠ **`LOWER(...)` in the index rather than a plain column pair.** A plain unique
index would let one tenant hold both `TRF-26-0001` and `trf-26-0001`, which are
one number to every human who reads them and two to the database.

No RLS operation is needed on either table: `transfers` got ENABLE + FORCE and
its policy in 0021, `disconnect_cases` in 0022, and a policy covers a table's
rows, not its columns.
"""

from django.db import migrations, models
from django.db.models.functions import Lower

#: The `ALTER TABLE`, valid on both vendors. `text NULL` is the same declaration
#: Postgres and sqlite take, and 0021's own DDL pair already writes `text` on
#: both sides for this table's `state` column.
ADD_TRANSFER_NO = "ALTER TABLE transfers ADD COLUMN transfer_no text NULL;"

#: One statement for both vendors: sqlite has supported partial and expression
#: indexes since 3.9, and Postgres has always. Written once so the two cannot
#: drift the way 0021's frozen DDL pair can.
ADD_TRANSFER_NO_INDEX = (
    "CREATE UNIQUE INDEX uq_transfers_tenant_transfer_no_ci "
    "ON transfers (tenant_id, LOWER(transfer_no)) "
    "WHERE transfer_no IS NOT NULL;"
)

DROP_TRANSFER_NO_INDEX = "DROP INDEX IF EXISTS uq_transfers_tenant_transfer_no_ci;"

#: ⚠ Postgres drops a column with `ALTER TABLE … DROP COLUMN`; sqlite has
#: supported the same statement since 3.35 (2021). Both are well inside this
#: product's floor, so the reverse is real rather than an
#: `IrreversibleError` — a migration whose reverse is a lie is worse than one
#: that says it cannot go back.
DROP_TRANSFER_NO = "ALTER TABLE transfers DROP COLUMN transfer_no;"


def add_transfer_no(apps, schema_editor):  # type: ignore[no-untyped-def]
    """The column and its index on the UNMANAGED `transfers` table.

    Frozen text, not derived from the live model — the same discipline
    migration 0021's docstring records for the `CREATE TABLE`: DDL that reaches
    into the current model class silently changes what it builds every time
    somebody edits the model, which is how a fresh database and an upgraded one
    come to disagree about columns.
    """
    schema_editor.execute(ADD_TRANSFER_NO)
    schema_editor.execute(ADD_TRANSFER_NO_INDEX)


def drop_transfer_no(apps, schema_editor):  # type: ignore[no-untyped-def]
    schema_editor.execute(DROP_TRANSFER_NO_INDEX)
    schema_editor.execute(DROP_TRANSFER_NO)


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0027_transfer"),
    ]

    operations = [
        # ── transfers (unmanaged): the DDL, then the state ──────────────────
        migrations.RunPython(add_transfer_no, drop_transfer_no),
        migrations.AddField(
            model_name="transfer",
            name="transfer_no",
            field=models.TextField(blank=True, null=True),
        ),
        # ── disconnect_cases (managed): AddField IS the DDL ─────────────────
        migrations.AddField(
            model_name="disconnectcase",
            name="case_no",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="disconnectcase",
            constraint=models.UniqueConstraint(
                models.F("tenant"),
                Lower("case_no"),
                condition=models.Q(("case_no__isnull", False)),
                name="uq_disconnect_cases_tenant_case_no_ci",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-039 wave D tasks 15/16 (12-governance/11-change-requests.md) +
#         OQ-426 / OQ-427 (12-governance/01-open-questions.md). ⚠ G1 wants
#         `US-XXX-###@<hex>` and this line cannot honestly supply one: no story
#         owns a CR wave task. DEF-810 records that the packet grammar has no
#         form for CR- or DEF-driven work and that 277 files are in this
#         position.
# generated: 2026-08-27 by the CR-039 wave D tasks 15/16 lane
# checklist: A✔ B✔(transfers.py + disconnects.py allocate from these columns)
#         C=n/a D=n/a E✔(S89/S90 render the number or its stated absence)
#         F✔ G✔ H=PENDING(🔒 migration ordering — ledger row written the same
#         day, before review, per r11 step 4)
# gates: `makemigrations --check --dry-run` → "No changes detected" with this
#         file present, and `+ Add field case_no to disconnectcase` +
#         `+ Create constraint uq_disconnect_cases_tenant_case_no_ci` WITHOUT
#         it — the DISCONNECT half only; see the docstring on why the
#         autodetector is silent about the unmanaged `transfer_no`. The
#         unmanaged half was PROVED RED on
#         `test_tc_trf_12_the_model_and_the_live_table_agree_column_for_column`
#         with the RunPython removed and the model field left in place:
#         `AssertionError: model fields with no column: {'transfer_no'}`
#         (hard-won law 7). NO POSTGRES IN THIS CONTAINER — the RLS this
#         migration relies on is 0021's and 0022's and is unchanged; a column
#         addition needs none.
# exceptions: this migration adds NO number series and seeds NO tenant a
#         format. Both columns are NULL on every row until OQ-426 / OQ-427
#         close, and the writers report `numbering_series_missing` rather than
#         inventing a prefix. Whether existing rows are backfilled on that day
#         is asked inside both questions and is NOT decided here.
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
