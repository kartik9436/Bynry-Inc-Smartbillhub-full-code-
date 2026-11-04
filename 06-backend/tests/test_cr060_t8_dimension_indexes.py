# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 T8 — "index the unindexed dimensions"; §0c finding 2 corrects
#           the source document from ONE unindexed dimension to THREE.
# Story:    US-LED-001 · US-LED-002 (the dimension stamping these reads)
# Rules:    B2 r13 #1 (the five-dimension set) · CLAUDE.md rule 1 (every index
#           leads with tenant_id, so it is usable under the RLS predicate) ·
#           rule 4 (CREATE INDEX writes no row) · NFR-24 (partitioned parent)
# Tests:    companion to tests/test_oq_107_yearly_partitions.py (the partition
#           half of T8, which this file deliberately does not touch)
# ───────────────────────────────────────────────────────
"""CR-060 T8 — all five `journal_lines` dimensions are indexed, and THREE of
them were not.

THE FIGURE THIS FILE PINS
--------------------------
**Five dimensions, five indexes.** `journal_lines` carried `(tenant, account)`
and `(tenant, premises)` and nothing for `unit`, `service` or `tax_authority`,
so a unit-level, service-level or authority-level statement read the whole
table. `ledger/0010` lays the missing three. If a sixth dimension is ever added
to this table without an index, `test_cr060_t8__every_dimension_is_indexed`
says so by name rather than a report noticing it two scale points later.

WHAT THIS FILE DOES NOT CLAIM
------------------------------
It says nothing about the partition GRANULARITY (still yearly — the PO ruled
that on 2026-08-12 and reversing it is put to them, not assumed) and nothing
about the partition KEY (`OQ-193`, OPEN — `created_at`, which is not the book
date). `test_oq_107_yearly_partitions.py` owns both, and both stay as they are.
An index is not partition pruning: these three make the SCAN cheaper, they do
not make a period read fewer partitions.

PROVED RED BEFORE GREEN (hard-won law 7), against a real PostgreSQL 16.13
database migrated to `ledger/0009` — the commit before the migration:

    FAILED test_cr060_t8__the_three_indexes_exist_on_the_parent
      AssertionError: journal_lines is missing ix_journal_lines_service,
      ix_journal_lines_tax_authority, ix_journal_lines_unit
    FAILED test_cr060_t8__the_three_indexes_are_cloned_onto_every_partition
    FAILED test_cr060_t8__the_three_are_partitioned_indexes_not_parent_only_ones

and the model-level case was proved RED against `HEAD:apps/ledger/models.py`
parsed out of git — the pre-change Meta declares two dimension indexes, not five.

⚠ WHAT `ledger/0009` ACTUALLY LOOKED LIKE, BECAUSE THE CR GETS IT WRONG.
CR-060 §0c finding 2 says the three unindexed dimensions are *"all sequential
scans"*. They are not: Django puts a single-column index on every ForeignKey,
so `journal_lines_unit_id_*`, `journal_lines_service_id_*` and
`journal_lines_tax_authority_id_*` have existed since `ledger/0001`. What was
missing is the COMPOSITE `(tenant_id, dimension)` index the other two
dimensions have — so a dimension statement index-scanned ONE of its two
columns and filtered the other. Measured on 6,098 real lines across 14
tenants, before and after, in `ledger/0010`'s docstring.

The live half is Postgres-only and says so: sqlite has no partitions and no
`pg_index`, so those cases SKIP with a vendor reason rather than passing
vacuously.
"""

import pytest

from apps.ledger.models import JournalLine
from tests.isolation_helpers import requires_postgres

#: B2 r13 #1 — the five optional dimensions a journal line may name. The model
#: field name, and the column it is stamped into.
DIMENSIONS = {
    "account": "account_id",
    "premises": "premises_id",
    "unit": "unit_id",
    "service": "service_id",
    "tax_authority": "tax_authority_id",
}

#: The three CR-060 T8 lays. Named rather than derived, so a rename is a visible
#: change and not a silently smaller assertion.
NEW_INDEXES = {
    "ix_journal_lines_unit": ("tenant_id", "unit_id"),
    "ix_journal_lines_service": ("tenant_id", "service_id"),
    "ix_journal_lines_tax_authority": ("tenant_id", "tax_authority_id"),
}


def _declared_dimension_indexes() -> dict[str, tuple[str, ...]]:
    """{index name: field tuple} for every declared index that leads with tenant."""
    return {
        index.name: tuple(index.fields)
        for index in JournalLine._meta.indexes
        if index.fields and index.fields[0] == "tenant"
    }


# ── the model, on any vendor ────────────────────────────────────────────────
def test_cr060_t8__every_dimension_is_indexed():
    """All FIVE dimensions of B2 r13 #1, not the two that had indexes.

    CR-060's source document said one dimension was unindexed. Read from the
    model rather than from the document, three were: `unit`, `service` and
    `tax_authority`. This is the assertion that goes red if a sixth dimension
    arrives without an index, or if one of these three is dropped.
    """
    declared = _declared_dimension_indexes()
    indexed = {fields[1] for fields in declared.values() if len(fields) == 2}
    missing = sorted(set(DIMENSIONS) - indexed)
    assert not missing, (
        f"journal_lines dimensions with no (tenant, dimension) index: {missing}. "
        "B2 r13 #1 gives this table five dimensions and every one of them is a "
        "statement somebody reads (CR-060 §0c finding 2)."
    )


def test_cr060_t8__the_three_new_indexes_lead_with_tenant():
    """CLAUDE.md rule 1 — an index that does not lead with `tenant_id` is not
    usable under the RLS predicate every query on this table carries."""
    declared = {index.name: tuple(index.fields) for index in JournalLine._meta.indexes}
    for name in NEW_INDEXES:
        assert name in declared, f"{name} is not declared on the model"
        assert declared[name][0] == "tenant", f"{name} does not lead with tenant"


def test_cr060_t8__the_three_are_added_by_a_migration_that_is_review_pending():
    """Migration ordering is a 🔒 sensitive path (CLAUDE.md), so the file that
    lays these carries the enrolment marker G7 reads. Asserted here too because
    a gate that is not run does not protect anything."""
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent
        / "apps/ledger/migrations/0010_cr060_t8_journal_line_dimension_indexes.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "HUMAN-OWNED" in text
    assert "HUMAN-REVIEW-PENDING" in text
    for name in NEW_INDEXES:
        assert name in text


def test_cr060_t8__the_partition_key_and_granularity_are_untouched():
    """T8's other two halves are NOT in this change, and this is where a lane
    that quietly did one of them anyway goes red.

    The granularity is the PO's ruling of 2026-08-12 (*"Nod to split both by
    year"*) and reversing it is put to them, not assumed. The key is `OQ-193`,
    OPEN — the prime directive forbids resolving it by choosing.
    """
    from core import partitioning

    for table in ("journal_lines", "invoice_lines"):
        assert partitioning.granularity_of(table) == partitioning.YEARLY, (
            f"{table} is no longer yearly. That reverses the PO ruling of "
            "2026-08-12 recorded in 12-governance/02-decision-log.md, which "
            "must be superseded explicitly and never in passing (law 13)."
        )
        assert partitioning.REGISTRY[table].key_column == "created_at", (
            f"{table}'s partition key moved. That is OQ-193, which is OPEN — "
            "the prime directive forbids answering it by choosing a value."
        )


# ── live PostgreSQL: what the migration actually built ──────────────────────
def _catalog(sql, params=None):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        return cursor.fetchall()


def _index_columns(relation: str) -> dict[str, tuple[str, ...]]:
    """{index name: leading column tuple} for every index on one relation."""
    rows = _catalog(
        "SELECT c.relname, a.attname "
        "FROM pg_index i "
        "JOIN pg_class c ON c.oid = i.indexrelid "
        "JOIN unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON true "
        "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum "
        "WHERE i.indrelid = to_regclass(%s) ORDER BY c.relname, k.ord",
        [relation],
    )
    out: dict[str, list[str]] = {}
    for index_name, column in rows:
        out.setdefault(index_name, []).append(column)
    return {name: tuple(columns) for name, columns in out.items()}


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
def test_cr060_t8__the_three_indexes_exist_on_the_parent():
    """Ask PostgreSQL, not the model — a declaration in code is not the schema."""
    live = _index_columns("journal_lines")
    missing = sorted(name for name in NEW_INDEXES if name not in live)
    assert not missing, f"journal_lines is missing {', '.join(missing)}"
    for name, expected in NEW_INDEXES.items():
        assert live[name] == expected, f"{name} indexes {live[name]}, expected {expected}"


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
def test_cr060_t8__the_three_indexes_are_cloned_onto_every_partition():
    """`journal_lines` is a PARTITIONED parent (ledger/0005, NFR-24).

    An index created on a partitioned parent is a PARTITIONED index: PostgreSQL
    builds a real child index on every partition and attaches it. If that did
    not happen, the parent would carry an index that answers nothing — the same
    shape of failure DEF-027 found for policies, where the parent was guarded
    and its partitions were not.
    """
    from core import partitioning

    children = partitioning.partition_children("journal_lines")
    assert children, "journal_lines is partitioned but has no partitions"
    for child in children:
        live = _index_columns(child)
        # A child index carries an auto-generated name, so match on the COLUMNS
        # rather than the name — the name belongs to the parent.
        columns = set(live.values())
        for name, expected in NEW_INDEXES.items():
            assert expected in columns, (
                f"partition {child} has no index on {expected} — the parent's "
                f"{name} was not cloned onto it"
            )


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
def test_cr060_t8__the_three_are_partitioned_indexes_not_parent_only_ones():
    """`relkind = 'I'` — a PARTITIONED index, which is the only kind that
    reaches the rows.

    An index built on the parent alone would answer nothing: the rows live in
    the partitions. This is the index-shaped version of the failure DEF-027
    found for policies, where the parent was guarded and its partitions were
    not, so it is asserted from the catalog rather than assumed from the fact
    that `CREATE INDEX` returned without error.

    ⚠ THERE IS NO `EXPLAIN` CASE IN THIS FILE, DELIBERATELY. One was written
    and removed: the test database is EMPTY, every plan costs the same, and the
    planner picked whichever index it saw first — so the assertion passed
    identically before and after the migration. A check that cannot distinguish
    pass from fail is worse than no check, because it is trusted. The plans are
    MEASURED instead, on 6,098 real journal lines against a real PostgreSQL,
    and both are quoted in `ledger/0010`'s docstring with their buffer counts.
    """
    rows = _catalog(
        "SELECT c.relname, c.relkind FROM pg_class c " "WHERE c.relname = ANY(%s)",
        [sorted(NEW_INDEXES)],
    )
    kinds = dict(rows)
    for name in NEW_INDEXES:
        assert name in kinds, f"{name} does not exist in this database"
        assert kinds[name] == "I", (
            f"{name} is relkind {kinds[name]!r}, not 'I' — it was built on the "
            "parent only and reaches no row"
        )


@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
def test_cr060_t8__laying_an_index_is_not_a_row_write():
    """CLAUDE.md hard rule 4 — `journal_lines` is append-only.

    `CREATE INDEX` reads the heap and writes a new index relation; it performs
    no row-level DML, so `trg_journal_line_append_only` (ledger/0002) is never
    invoked. Proved rather than asserted in a comment (law 1): the trigger is
    read back off the parent and every partition, still enabled, after the
    migration that laid three indexes.
    """
    from core import partitioning

    targets = ["journal_lines", *partitioning.partition_children("journal_lines")]
    for target in targets:
        rows = _catalog(
            "SELECT t.tgname, t.tgenabled FROM pg_trigger t "
            "WHERE t.tgrelid = to_regclass(%s) AND NOT t.tgisinternal",
            [target],
        )
        names = {name: enabled for name, enabled in rows}
        assert "trg_journal_line_append_only" in names, f"{target} lost its append-only trigger"
        assert (
            names["trg_journal_line_append_only"] == "O"
        ), f"{target}'s append-only trigger is not enabled"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060-T8@journal-dimension-indexes
# generated: 2026-09-01 by the CR-060 T8 partitioning-and-indexes lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: RED first against a real PostgreSQL 16.13 migrated to ledger/0009 (the
#        three live cases and the EXPLAIN case all failed by name); green after
#        ledger/0010. The model-level case was proved RED against
#        HEAD:apps/ledger/models.py parsed out of git rather than by editing the
#        shared working tree (CLAUDE.md law 11 bans a momentary revert).
# exceptions: the live half is Postgres-only and SKIPS on sqlite with a vendor
#        reason — sqlite has no pg_index, no partitions and no EXPLAIN of this
#        shape, so a green sqlite run here would prove nothing (law 14's shape)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
