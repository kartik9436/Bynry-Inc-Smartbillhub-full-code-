# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — invoice_lines) · US-LED-001 (posting contracts —
#           journal_lines)   Screens: S31 · S56 · S36
# Rules:    NFR-24 (the mandatory partition set; its "monthly" wording
#           SUPERSEDED for these two tables by the PO ruling of 2026-08-12) ·
#           NFR-25 (financial partitions never pruned) · B2 §5 (create-ahead;
#           "Candidate key: period_start / created_at") · CLAUDE.md rule 1
#           (tenant scoping, RLS FORCE) · rule 4 (financial immutability) ·
#           rule 5 (balanced pairs, sole writer) · DEF-031 · DEF-027
# Tests:    companion to tests/test_be10_partitioning.py (the monthly half) and
#           tests/test_us_aud_001_partition_rls.py (the catalog-wide guard)
# ───────────────────────────────────────────────────────
"""OQ-107 — `invoice_lines` and `journal_lines` are partitioned BY YEAR.

THE RATIFIED FIGURE THIS FILE PINS
-----------------------------------
PO, 2026-08-12, verbatim: *"Nod to split both by year"* (12-governance/
02-decision-log.md). The option put to them was BY MONTH — NFR-24's own
sentence says monthly — and they answered by year. So the assertion that has to
go RED on drift is a concrete one: **an invoice line written on 3 July 2026
lives in `invoice_lines_2026`, a partition covering 2026-01-01 to 2027-01-01 —
not `invoice_lines_2026_07`.** If someone ever re-monthlies these two tables,
`test_oq_107__the_ruled_granularity_is_yearly_for_both_tables` says so by name.

WHAT THIS FILE DOES NOT CLAIM
------------------------------
It does not claim the partition KEY was ruled. It was not. The PO settled how
big a partition is; `created_at` is the column, chosen from the two B2 §5 names
as signed law, and `test_oq_107__the_key_is_created_at_and_that_is_reported`
exists to keep that visible rather than to bless it. See the ⚠ blocks in
`core/partitioning.py` and in both migrations.

PROVED RED BEFORE GREEN (hard-won law 7). The two guards that stand between a
utility's books and a bad rebuild are each shown to bite, against a real
PostgreSQL, on a real table with real rows:

  * the COLUMN guard — `test_oq_107__rebuild_refuses_a_column_set_it_does_not_know`
    turns a column the migration has never heard of into a refusal, with the
    table untouched;
  * the TIE-OUT — `test_oq_107__rebuild_aborts_when_the_copy_does_not_tie_out`
    makes the copy lose a row and asserts the whole thing is refused BEFORE the
    old heap is released.

Postgres only for the live half: sqlite has no partitions, no RLS and none of
the triggers, so those cases skip with a vendor reason rather than passing
vacuously.
"""

import re
from datetime import date
from pathlib import Path

import pytest

from core import partitioning
from tests.isolation_helpers import requires_postgres

BACKEND = Path(__file__).resolve().parent.parent
BILLING_MIGRATION = BACKEND / "apps/billing/migrations/0016_partition_invoice_lines_by_year.py"
LEDGER_MIGRATION = BACKEND / "apps/ledger/migrations/0005_partition_journal_lines_by_year.py"
EXCEPTIONS_FILE = BACKEND.parent / "10-scripts/gates/partition_exceptions.txt"

YEARLY_TABLES = ("invoice_lines", "journal_lines")


# ── the ruling itself ───────────────────────────────────────────────────────
def test_oq_107__the_ruled_granularity_is_yearly_for_both_tables():
    """PO 2026-08-12: *"Nod to split both by year"* — the worked case.

    A line written on 3 July 2026 goes to `<table>_2026`, one partition
    covering the whole year. The monthly name it would have had under NFR-24 as
    signed is asserted NOT to be produced, because "yearly" is only meaningful
    against the thing it replaced.
    """
    written_on = date(2026, 7, 3)
    for table in YEARLY_TABLES:
        assert partitioning.granularity_of(table) == partitioning.YEARLY
        assert partitioning.partition_name(table, written_on) == f"{table}_2026"
        assert partitioning.partition_name(table, written_on) != f"{table}_2026_07"
        assert partitioning.partition_bounds(table, written_on) == (
            date(2026, 1, 1),
            date(2027, 1, 1),
        )


def test_oq_107__audit_log_and_meter_reads_stay_monthly():
    """The ruling covered *both big tables*, and nothing else.

    NFR-28 (audit_log) and BR-MET-055 (meter_reads) are untouched signed law;
    a change that made everything yearly would be a wider change than the PO
    made, and this is where that would go red.
    """
    for table in ("audit_log", "meter_reads"):
        assert partitioning.granularity_of(table) == partitioning.MONTHLY
        assert partitioning.partition_name(table, date(2026, 7, 3)) == f"{table}_2026_07"


def test_oq_107__the_key_is_created_at_and_that_is_reported():
    """The COLUMN was never put to the PO — only the granularity was.

    `created_at` is one of the two candidates B2 §5 names in signed text for
    both tables. The other, `period_start`, is NULLABLE on `invoice_lines` and
    cannot be a RANGE key at all; `journal_lines` has no book date to range over
    (entry_date is a column of `journal_entries`). Pinned here so that a change
    of key is a visible change and not a quiet one.
    """
    for table in YEARLY_TABLES:
        assert partitioning.REGISTRY[table].key_column == "created_at"
        assert partitioning.REGISTRY[table].financial is True


def test_oq_107__yearly_create_ahead_is_the_current_year_plus_one():
    """B2 §5's runway, expressed in each table's own units.

    Three months ahead of a monthly table and one year ahead of a yearly one.
    A yearly table with `ahead=3` would mint partitions into 2030 for nothing.
    """
    for table in YEARLY_TABLES:
        assert partitioning.REGISTRY[table].create_ahead == 1
        assert partitioning.plan_create_ahead(table, date(2026, 8, 15)) == [
            f"{table}_2026",
            f"{table}_2027",
        ]


def test_oq_107__a_yearly_partition_only_detaches_once_all_its_months_are_cold():
    """NFR-25/28's 24-month hot window is never SHORTENED by the coarser grain.

    In August 2026 the window reaches back to August 2024, which is inside the
    2024 partition — so 2024 is not a DETACH candidate and 2023 is. A horizon
    rounded the other way would offer a partition holding rows only 19 months
    old, which is a retention promise broken by an off-by-one.
    """
    existing = [date(2023, 1, 1), date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1)]
    for table in YEARLY_TABLES:
        assert partitioning.detach_candidates(table, date(2026, 8, 9), existing) == [
            f"{table}_2023"
        ]


def test_oq_107__yearly_partition_ddl_carries_year_bounds_and_its_policy():
    """One string: the CREATE and the B2 §3 tenant policy (DEF-027, law 3)."""
    for table in YEARLY_TABLES:
        sql = partitioning.create_partition_sql(table, date(2026, 7, 3))
        name = f"{table}_2026"
        assert f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF {table}" in sql
        assert "FROM ('2026-01-01') TO ('2027-01-01')" in sql
        assert f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY;" in sql
        assert f"CREATE POLICY {name}_tenant_isolation ON {name}" in sql


def test_oq_107__both_tables_are_in_the_create_ahead_set():
    """A partitioned parent outside ACTIVE_TABLES is neither renewed nor guarded.

    That is the failure `meter_reads` demonstrated (the quiet half of DEF-027),
    so the two tables joined the set in the SAME change that partitioned them.
    `outbound_messages` is deliberately absent and stays absent: PO 2026-08-11
    ruled it unpartitioned (OQ-108).
    """
    assert set(YEARLY_TABLES) <= partitioning.ACTIVE_TABLES
    assert "outbound_messages" not in partitioning.ACTIVE_TABLES


# ── the migrations, read as text ────────────────────────────────────────────
@pytest.mark.parametrize("path", [BILLING_MIGRATION, LEDGER_MIGRATION])
def test_oq_107__migration_sql_has_no_lone_percent(path):
    """DEF-064 — one un-doubled `%` shipped a product that could not migrate.

    Django hands migration SQL to the driver with an EMPTY PARAMS TUPLE, so the
    driver attempts %-interpolation and dies on a lone `%`; sqlite's backend
    never sees it and every test passes. These two migrations sidestep the class
    entirely — they build no `%` at all, and `core.partitioning` executes every
    statement through `cursor.execute(sql)` with no params argument — and this
    keeps it that way.
    """
    text = path.read_text(encoding="utf-8")
    sql_blocks = re.findall(r'"""\n(CREATE TABLE.*?)"""', text, re.S)
    assert sql_blocks, f"{path.name}: no DDL block found — has the shape changed?"
    for block in sql_blocks:
        assert "%" not in block, f"{path.name}: a literal % in migration SQL (DEF-064)"


@pytest.mark.parametrize(
    "path,table",
    [(BILLING_MIGRATION, "invoice_lines"), (LEDGER_MIGRATION, "journal_lines")],
)
def test_oq_107__migration_column_list_matches_its_own_ddl(path, table):
    """The declared COLUMNS and the declared DDL cannot drift apart.

    `core.partitioning` refuses to run when the live table disagrees with
    COLUMNS, which makes COLUMNS load-bearing — so it has to be the same list
    the DDL creates, in the same order, or the refusal would fire on a correct
    database.
    """
    text = path.read_text(encoding="utf-8")
    ddl = re.search(rf"CREATE TABLE {table} \((.*?)\n\) PARTITION BY", text, re.S).group(1)
    from_ddl = [
        m.group(1)
        for m in re.finditer(r"^\s{2}([a-z_][a-z0-9_]*)\s+\S", ddl, re.M)
        if m.group(1) != "PRIMARY"
    ]
    declared = re.search(r"COLUMNS = \[(.*?)\]", text, re.S).group(1)
    from_list = re.findall(r'"([a-z_][a-z0-9_]*)"', declared)
    assert from_ddl == from_list


def test_oq_107__the_exception_lines_are_gone_not_re_filed():
    """G16's two lawful outcomes, and which one this change took.

    The gate's message on a CLOSED question offers exactly two: implement the
    ruling and delete the line, or re-file it as PO-RULED. The ruling was to
    PARTITION, so the lines are deleted. A `PO-RULED` line for either table
    would mean somebody exempted a table the PO told us to partition.
    """
    body = [
        line.strip()
        for line in EXCEPTIONS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    for table in YEARLY_TABLES:
        assert not any(line.startswith(f"{table} ") for line in body), (
            f"{table} still has an exception line. It is partitioned now — the "
            "exception is stale and G16 fails on it."
        )
    assert any(line.startswith("outbound_messages PO-RULED ") for line in body), (
        "outbound_messages' RATIFIED exemption (PO 2026-08-11, OQ-108) must stay — "
        "deleting it drops the table out of G16's sight, which is DEF-031's shape"
    )


# ── live PostgreSQL: what the migrations actually built ─────────────────────
def _catalog(sql, params=None):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        return cursor.fetchall()


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
@pytest.mark.parametrize("table", YEARLY_TABLES)
def test_oq_107__the_table_really_is_a_yearly_partitioned_parent(table):
    """Ask PostgreSQL, not the registry — a claim in code is not the schema."""
    assert partitioning.is_partitioned_parent(table)
    children = partitioning.partition_children(table)
    assert children, f"{table} is partitioned but has no partitions"
    for child in children:
        assert re.fullmatch(rf"{table}_\d{{4}}", child), (
            f"{child} is not a yearly partition name. The PO ruled by year on "
            "2026-08-12; a _YYYY_MM name here means someone re-monthlied it."
        )
    key = _catalog(
        "SELECT a.attname FROM pg_partitioned_table p "
        "JOIN pg_attribute a ON a.attrelid = p.partrelid AND a.attnum = p.partattrs[0] "
        "WHERE p.partrelid = to_regclass(%s)",
        [table],
    )
    assert key and key[0][0] == partitioning.REGISTRY[table].key_column


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
@pytest.mark.parametrize("table", YEARLY_TABLES)
def test_oq_107__the_primary_key_contains_the_partition_key(table):
    """PostgreSQL requires it, and B2 §2 already writes this shape for meter_reads."""
    columns = [
        row[0]
        for row in _catalog(
            "SELECT a.attname FROM pg_constraint c "
            "JOIN unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord) ON true "
            "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum "
            "WHERE c.conrelid = to_regclass(%s) AND c.contype = 'p' ORDER BY k.ord",
            [table],
        )
    ]
    assert columns == ["tenant_id", partitioning.REGISTRY[table].key_column, "id"]


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
def test_oq_107__the_ledger_guarantees_survived_the_rebuild():
    """All three `journal_lines` triggers are back, on the parent AND each partition.

    They were replayed from `pg_get_triggerdef` rather than restated in the
    migration, so this is the assertion that the replay actually happened —
    balance (hard rule 5), append-only (hard rule 4) and the sole-writer fence
    (ledger/0004). PostgreSQL clones a parent's row triggers to partitions,
    including partitions the create-ahead job mints later.
    """
    expected = {
        "journal_balanced",
        "trg_journal_line_append_only",
        "trg_journal_lines_sole_writer",
    }
    targets = ["journal_lines", *partitioning.partition_children("journal_lines")]
    for target in targets:
        names = {
            row[0]
            for row in _catalog(
                "SELECT t.tgname FROM pg_trigger t "
                "WHERE t.tgrelid = to_regclass(%s) AND NOT t.tgisinternal",
                [target],
            )
        }
        assert expected <= names, f"{target} is missing {sorted(expected - names)}"

    # The invoice-line half of hard rule 4, same question.
    for target in ["invoice_lines", *partitioning.partition_children("invoice_lines")]:
        names = {
            row[0]
            for row in _catalog(
                "SELECT t.tgname FROM pg_trigger t "
                "WHERE t.tgrelid = to_regclass(%s) AND NOT t.tgisinternal",
                [target],
            )
        }
        assert "trg_invoice_line_immutable" in names, f"{target} lost hard rule 4"


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
@pytest.mark.parametrize("table", YEARLY_TABLES)
def test_oq_107__every_partition_is_guarded_by_name(table):
    """The catalog-wide sweep in test_us_aud_001_partition_rls covers this too.

    It is repeated by name here so the two new tables cannot become the case
    that sweep silently stops reaching — non-vacuity, the same reason that file
    still names `audit_log` explicitly.
    """
    assert partitioning.unguarded_partitions(table) == []
    parent = _catalog(
        "SELECT c.relrowsecurity, c.relforcerowsecurity, "
        "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) "
        "FROM pg_class c WHERE c.oid = to_regclass(%s)",
        [table],
    )[0]
    assert parent == (True, True, 1), f"{table}'s own guard is {parent}"


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
@pytest.mark.parametrize("table", YEARLY_TABLES)
def test_oq_107__the_create_ahead_job_mints_a_guarded_yearly_partition(table):
    """The real job body, for a year nothing has reached yet."""
    far = date(date.today().year + 6, 5, 4)
    expected = partitioning.plan_create_ahead(table, far)
    assert not (set(expected) & set(partitioning.partition_children(table)))

    created = partitioning.ensure_partitions(table, far)
    assert created == expected
    assert set(created) <= set(partitioning.partition_children(table))
    assert partitioning.unguarded_partitions(table) == []


# ── the two guards, proved RED on a real table with real rows ───────────────
PROBE_TABLE = "oq107_rebuild_probe"

PROBE_DDL = f"""
CREATE TABLE {PROBE_TABLE} (
  id         uuid          NOT NULL,
  tenant_id  uuid          NOT NULL,
  created_at timestamptz   NOT NULL,
  amount     numeric(18,6) NOT NULL,
  PRIMARY KEY (tenant_id, created_at, id)
) PARTITION BY RANGE (created_at);
"""

PROBE_COLUMNS = ["id", "tenant_id", "created_at", "amount"]


@pytest.fixture
def probe_table(monkeypatch):
    """A registered, populated, flat table to run the real rebuild against.

    The two tables the migrations touch are already partitioned by the time any
    test runs, so `convert_to_partitioned` would no-op on them. This gives the
    guards something real to refuse: three rows, a money column and a tenant
    column, torn down with the test transaction.
    """
    from django.db import connection

    entry = partitioning.PartitionedTable(
        PROBE_TABLE,
        "created_at",
        financial=True,
        wave="test",
        granularity=partitioning.YEARLY,
        create_ahead=1,
    )
    monkeypatch.setitem(partitioning.REGISTRY, PROBE_TABLE, entry)
    with connection.cursor() as cursor:
        cursor.execute(
            f"CREATE TABLE {PROBE_TABLE} (id uuid NOT NULL PRIMARY KEY, "
            "tenant_id uuid NOT NULL, created_at timestamptz NOT NULL, "
            "amount numeric(18,6) NOT NULL);"
        )
        # ⚠ THE ROWS GO IN BEFORE THE POLICY, AND THE ORDER IS THE WHOLE FIX
        # (2026-09-05). The policy carries FORCE ROW LEVEL SECURITY, which
        # applies WITH CHECK to the table OWNER as well — so with the policy
        # already on and no `app.tenant_id` set, this INSERT is refused and all
        # three cases below error in setup. It used to be accepted because the
        # test connection was a SUPERUSER, which bypasses RLS entirely
        # (DEF-GOV-4036).
        #
        # Seeding first rather than seeding under a context is deliberate: the
        # three rows belong to TWO different tenants on purpose, which is what
        # makes the rebuild guards below meaningful, and no single context can
        # write both. The table is guarded from the next statement onwards,
        # which is the state every guard here is written against.
        cursor.execute(
            f"INSERT INTO {PROBE_TABLE} (id, tenant_id, created_at, amount) VALUES "
            "('00000000-0000-0000-0000-00000000000a',"
            " '11111111-1111-1111-1111-111111111111', '2026-07-03T10:00:00Z', 88.600000),"
            "('00000000-0000-0000-0000-00000000000b',"
            " '11111111-1111-1111-1111-111111111111', '2025-07-03T10:00:00Z', 12.000000),"
            "('00000000-0000-0000-0000-00000000000c',"
            " '22222222-2222-2222-2222-222222222222', '2026-01-02T10:00:00Z', 47.500000);"
        )
        cursor.execute(partitioning.tenant_isolation_policy_sql(PROBE_TABLE))
    return PROBE_TABLE


def _probe_state():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {PROBE_TABLE} NO FORCE ROW LEVEL SECURITY;")
        cursor.execute(f"SELECT count(*), sum(amount) FROM {PROBE_TABLE}")
        return cursor.fetchone()


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
def test_oq_107__rebuild_refuses_a_column_set_it_does_not_know(probe_table):
    """RED PROOF 1 — a column the migration never heard of stops the rebuild.

    A later migration adding a column to `invoice_lines` and nobody updating
    the DDL here would otherwise build a parent MISSING that column and lose it
    on every row. The refusal names both lists and changes nothing.
    """
    from django.db import connection
    from django.db.migrations.state import ProjectState  # noqa: F401

    with connection.schema_editor(atomic=False) as editor:
        with pytest.raises(partitioning.PartitioningError) as excinfo:
            partitioning.convert_to_partitioned(
                editor,
                table=PROBE_TABLE,
                parent_ddl=PROBE_DDL,
                columns=["id", "tenant_id", "created_at"],  # `amount` missing
                today=date(2026, 8, 15),
                money_column="amount",
            )
    message = str(excinfo.value)
    assert "does not have the columns this migration was written against" in message
    assert "amount" in message
    assert not partitioning.is_partitioned_parent(PROBE_TABLE), "it rebuilt anyway"
    assert _probe_state() == (3, __import__("decimal").Decimal("148.100000"))


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
def test_oq_107__rebuild_aborts_when_the_copy_does_not_tie_out(probe_table, monkeypatch):
    """RED PROOF 2 — a copy that loses a row never reaches the DROP.

    The tie-out is the one thing standing between a rebuild and a utility's
    books, so it is made to fail on purpose: `_tie_out` is wrapped to report one
    row fewer after the copy, exactly as a lost row would. The rebuild must
    refuse, name both figures, and leave the old heap where it is.
    """
    from django.db import connection

    real = partitioning._tie_out
    calls = {"n": 0}

    def losing_a_row(cursor, table, money_column):
        calls["n"] += 1
        rows, money, digest = real(cursor, table, money_column)
        return (rows - 1, money, digest) if calls["n"] > 1 else (rows, money, digest)

    monkeypatch.setattr(partitioning, "_tie_out", losing_a_row)

    with connection.schema_editor(atomic=False) as editor:
        with pytest.raises(partitioning.PartitioningError) as excinfo:
            partitioning.convert_to_partitioned(
                editor,
                table=PROBE_TABLE,
                parent_ddl=PROBE_DDL,
                columns=PROBE_COLUMNS,
                today=date(2026, 8, 15),
                money_column="amount",
            )
    message = str(excinfo.value)
    assert "did not tie out after the copy" in message
    assert "NOTHING has been committed" in message
    # The aside table still holds every original row — the DROP never ran.
    from django.db import connection as conn

    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT to_regclass(%s) IS NOT NULL", [f"{PROBE_TABLE}{partitioning._ASIDE_SUFFIX}"]
        )
        aside_survived = cursor.fetchone()[0]
        cursor.execute(
            f"SELECT count(*), sum(amount) FROM {PROBE_TABLE}{partitioning._ASIDE_SUFFIX}"
        )
        assert cursor.fetchone() == (3, __import__("decimal").Decimal("148.100000"))
    assert aside_survived, "the old heap was released despite a failed tie-out"


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
def test_oq_107__a_clean_rebuild_carries_every_row_byte_for_byte(probe_table):
    """The green case the two red ones are measured against.

    Three rows across two years and two tenants go in flat and come out routed
    into `_2025` and `_2026`, with the row digest unchanged — which is the whole
    claim CLAUDE.md hard rule 4 needs from a table rebuild.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {PROBE_TABLE} NO FORCE ROW LEVEL SECURITY;")
        before = partitioning._tie_out(cursor, PROBE_TABLE, "amount")

    with connection.schema_editor(atomic=False) as editor:
        report = partitioning.convert_to_partitioned(
            editor,
            table=PROBE_TABLE,
            parent_ddl=PROBE_DDL,
            columns=PROBE_COLUMNS,
            today=date(2026, 8, 15),
            money_column="amount",
        )

    assert report["rows"] == 3
    assert report["partitions"] == [
        f"{PROBE_TABLE}_2025",
        f"{PROBE_TABLE}_2026",
        f"{PROBE_TABLE}_2027",
    ]
    assert partitioning.is_partitioned_parent(PROBE_TABLE)
    assert partitioning.unguarded_partitions(PROBE_TABLE) == []

    with connection.cursor() as cursor:
        cursor.execute(f"ALTER TABLE {PROBE_TABLE} NO FORCE ROW LEVEL SECURITY;")
        after = partitioning._tie_out(cursor, PROBE_TABLE, "amount")
    assert after == before, "a row changed in the copy"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-001@8d956fb (sha1[:7] of the three authorities this slice was
#         authored from, newline-joined in order: the 2026-08-12 decision-log row
#         carrying the PO ruling "Nod to split both by year" · the OQ-107 row in
#         12-governance/01-open-questions.md · NFR-24's own sentence in
#         04-docs/02-decisions/06-non-functional-requirements.md)
# generated: 2026-08-15 by story-coder (OQ-107 partitioning lane)
# checklist: A✔ B✔ C✔ D=deferred(no API half) E=deferred(no UI half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED before green against a live PostgreSQL 16.13 — the column guard
#         was shown to refuse a DDL missing `amount` with the table untouched, and the
#         tie-out was made to lose a row and shown to abort with the old heap still
#         holding all three; the green case ties out to the same row digest
# exceptions: the live half skips under sqlite rather than passing vacuously (no
#         partitions, no RLS, none of the triggers there) · the rebuild guards are
#         proved on a throwaway registered probe table because the two real tables
#         are already partitioned by the time any test runs, so the real machinery
#         would correctly no-op on them
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
