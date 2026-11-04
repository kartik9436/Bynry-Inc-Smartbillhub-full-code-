# ── Trace ──────────────────────────────────────────────
# Component: BE-10 tests (core/partitioning.py) — pure month math, DDL text, the
#            never-drop law, and the create-ahead plan. Live partition TCs
#            (US-AUD-001 TC-1 on Postgres) belong to the G5/CI lane.
# ───────────────────────────────────────────────────────
"""BE-10 unit tests: partition names/bounds per B2 §5, create-ahead = current
+ 3, detach candidates honor the 2-year hot window, financial tables are named
never-pruned, and no drop API exists at all (NFR-24/25/28)."""

from datetime import date

import pytest

from core import partitioning


# ── US-AUD-001 TC-1 (math half): Aug 2026 ⇒ 2026_08..2026_11 ────────────────
def test_us_aud_001_tc1__create_ahead_plan_is_current_plus_three():
    names = partitioning.plan_create_ahead("audit_log", date(2026, 8, 9), ahead=3)
    assert names == [
        "audit_log_2026_08",
        "audit_log_2026_09",
        "audit_log_2026_10",
        "audit_log_2026_11",
    ]


def test_be10_tc02_partition_name_grammar():
    assert partitioning.partition_name("audit_log", date(2026, 1, 31)) == "audit_log_2026_01"


def test_be10_tc03_month_bounds_are_half_open_and_cross_year():
    start, end = partitioning.month_bounds(date(2026, 12, 15))
    assert (start, end) == (date(2026, 12, 1), date(2027, 1, 1))


def test_be10_tc04_create_sql_targets_parent_with_half_open_range():
    sql = partitioning.create_partition_sql("audit_log", date(2026, 8, 1))
    assert "CREATE TABLE IF NOT EXISTS audit_log_2026_08 PARTITION OF audit_log" in sql
    assert "FROM ('2026-08-01') TO ('2026-09-01')" in sql


def test_be10_tc05_registry_is_exactly_the_nfr24_mandatory_set():
    assert set(partitioning.REGISTRY) == {
        "audit_log",
        "meter_reads",
        "invoice_lines",
        "journal_lines",
        "outbound_messages",
    }


def test_be10_tc05b_active_tables_holds_the_landed_parents():
    """`meter_reads` was ADDED here on 2026-08-10 — deliberately, per DEF-027.

    This assertion is the reason the frozenset is pinned at all: flipping a
    table on changes what the scheduled `maintain_partitions` job touches, so
    it should never happen as a side effect of some other edit.

    Why it changed. `apps/metering/0003_w2_reads` (W2) created the partitioned
    `meter_reads` parent and bootstrapped a FIXED window — 24 months back plus
    3 ahead — then reported, in its own docstring, that it could not flip this
    entry on because the frozenset and this test belong to core/'s owner. The
    consequence it left behind was two-fold:

      * nothing RENEWED those partitions, so reads INSERTs would have started
        failing once the 3-month lead ran out — a silent clock, not a bug
        anyone would see coming;
      * nothing GUARDED partitions minted later, which is DEF-027 itself.

    Both close by the job knowing about the table.

    `invoice_lines` and `journal_lines` joined on 2026-08-15, with the two
    migrations that rebuilt them as YEARLY parents under the PO ruling of
    2026-08-12 ("Nod to split both by year", OQ-107) — in the SAME change,
    because `meter_reads` had already shown what a partitioned parent outside
    this set costs.

    `outbound_messages` (W6) stays OFF and stays off PERMANENTLY: the PO ruled
    on 2026-08-11 (OQ-108) that it is not partitioned at all, because monthly
    RANGE would force `created_at` into every unique constraint and let a
    re-released bill send twice. The executor refuses a table with no parent
    (tc09), and tests/test_def_027_partition_rls_create_ahead.py fails if a
    partitioned parent ever exists in the database while missing from this set.
    """
    assert partitioning.ACTIVE_TABLES == frozenset(
        {"audit_log", "meter_reads", "invoice_lines", "journal_lines"}
    )


def test_be10_tc06_detach_candidates_honor_two_year_hot_window():
    # NFR-28: months strictly older than 24 months from Aug 2026 (< Aug 2024).
    existing = [date(2024, 6, 1), date(2024, 7, 1), date(2024, 8, 1), date(2026, 7, 1)]
    candidates = partitioning.detach_candidates("audit_log", date(2026, 8, 9), existing)
    assert candidates == ["audit_log_2024_06", "audit_log_2024_07"]


def test_be10_tc07_financial_tables_named_never_pruned():
    # NFR-25 verbatim set — the law is greppable, and there is NO drop API.
    assert partitioning.FINANCIAL_NEVER_PRUNED == frozenset(
        {"journal_lines", "invoice_lines", "invoices", "payments", "allocations"}
    )
    drop_shaped = [name for name in dir(partitioning) if "drop" in name.lower()]
    assert drop_shaped == []  # deliberate absence, like numbering's missing renumber API


def test_be10_tc08_unregistered_table_refused():
    with pytest.raises(partitioning.PartitioningError):
        partitioning.plan_create_ahead("accounts", date(2026, 8, 9))


def test_be10_tc09_unlanded_table_refused_by_executor():
    # outbound_messages is registered (NFR-24 names it) but has no partitioned
    # parent — the executor refuses rather than emitting DDL against a table it
    # cannot partition. (This case used meter_reads until 2026-08-10 and
    # invoice_lines until 2026-08-15; each moved on when its parent landed and
    # it joined ACTIVE_TABLES — see tc05b. outbound_messages will not move: the
    # PO ruled on 2026-08-11 that it stays unpartitioned, so this case has a
    # permanent subject for the first time.)
    with pytest.raises(partitioning.PartitioningError):
        partitioning.ensure_partitions("outbound_messages", date(2026, 8, 9))


def test_be10_tc10_unsafe_identifier_refused():
    with pytest.raises(partitioning.PartitioningError):
        partitioning.partition_name("audit_log; DROP POLICY", date(2026, 8, 1))


# ── DEF-027: a partition cannot be minted without its tenant policy ─────────
def test_be10_tc11_policy_text_matches_the_signed_b2_sql():
    """`core/rls.py` emits the SIGNED B2 §3 template and not a lookalike.

    The template exists as code because a partition's NAME is only known at run
    time. That is exactly the situation in which a policy quietly drifts from
    the signed one, so the two are diffed statement by statement here against
    `06-backend/db/rls_audit_w0.sql` — the finance/human-signed file.

    One statement is allowed to differ: `DROP POLICY IF EXISTS` before the
    CREATE, the idempotency line `apps/audit/0003` and `apps/metering/0004`
    already write. Anything else means someone edited a signed rule inline,
    which needs a re-sign (HUMAN-GUIDE §6), not a passing test.
    """
    from core.migrationtools import load_db_sql
    from core.rls import tenant_isolation_policy_sql

    def statements(sql: str) -> list[str]:
        body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        return [" ".join(s.split()) for s in body.split(";") if s.strip()]

    # ⚠ THE FILTER MUST APPLY TO BOTH SIDES, AND IT DID NOT (fixed 2026-08-24).
    # The docstring above has always said "one statement is allowed to differ:
    # DROP POLICY IF EXISTS before the CREATE" — but the comprehension stripped
    # it from `generated` ONLY. That was harmless while the signed file had no
    # DROP line, and DEF-333 added one on 2026-08-2x to make every RLS policy
    # re-runnable ("guard all 94 RLS policies so a re-run cannot kill the
    # deploy"). From that commit the two lists could never be equal and this
    # test could never pass, whatever the policy text said.
    #
    # ⚠ SO IT HAS BEEN RED, UNREAD, EXACTLY WHILE THE THING IT GUARDS WAS BEING
    # REWRITTEN. DEF-639 changed this very policy expression across 204
    # literals on 2026-08-24 — the one change this assertion exists to catch —
    # and it could not have objected. It agrees now (both sides read the
    # `NULLIF(current_setting('app.tenant_id', true), '')::uuid` form), which is
    # the answer it should have been giving all along.
    def without_drop(sqls: list[str]) -> list[str]:
        return [s for s in sqls if "DROP POLICY" not in s]

    signed = without_drop(statements(load_db_sql("rls_audit_w0.sql")))
    generated = without_drop(statements(tenant_isolation_policy_sql("audit_log")))
    assert generated == signed, (
        "the partition policy text has drifted from the signed B2 §3 template in "
        f"db/rls_audit_w0.sql\n  signed:    {signed}\n  generated: {generated}"
    )


def test_be10_tc12_every_partition_ddl_carries_its_policy():
    """There is no way to ask this module for an UNGUARDED partition.

    DEF-027's root cause was that creating a partition and guarding it were two
    separate acts, and only the first one ever ran on a schedule. So the CREATE
    and the B2 §3 policy are one string, and this asserts it for every table in
    the registry rather than for the one table someone thought of.
    """
    for table in sorted(partitioning.REGISTRY):
        sql = partitioning.create_partition_sql(table, date(2026, 8, 1))
        name = partitioning.partition_name(table, date(2026, 8, 1))
        assert f"PARTITION OF {table}" in sql
        assert f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY;" in sql
        assert f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY;" in sql
        assert f"CREATE POLICY {name}_tenant_isolation ON {name}" in sql
        # DEF-639 (PO 2026-08-24): the predicate is NULLIF-wrapped so an unset
        # tenant DENIES instead of raising. A partition minted from the old
        # form would re-break fresh-database builds, so this pin moves with it.
        assert "NULLIF(current_setting('app.tenant_id', true), '')::uuid" in sql
        assert "current_setting('app.tenant_id')::uuid" not in sql
        # Idempotent — re-running the create-ahead job IS the remediation path.
        assert f"DROP POLICY IF EXISTS {name}_tenant_isolation ON {name};" in sql
        assert sql.index("PARTITION OF") < sql.index("ENABLE ROW LEVEL SECURITY"), (
            "the guard must follow the CREATE in the same batch — a policy "
            "issued before the table exists is an error, not a guarantee"
        )


def test_be10_tc13_policy_sql_refuses_an_unsafe_identifier():
    from core.rls import RlsError, tenant_isolation_policy_sql

    with pytest.raises(RlsError):
        tenant_isolation_policy_sql("audit_log; DROP POLICY x ON y")
