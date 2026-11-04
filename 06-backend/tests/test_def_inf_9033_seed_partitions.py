# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-INF-9033 — the standard e2e stack could not boot on a database
#           migrated from 2026-10-01: "no partition of relation meter_reads
#           found for row" at read_at 2024-09-01.
# Rules:    NFR-24 (meter_reads is monthly-partitioned) · CLAUDE.md hard rule 1
#           (every partition is guarded by its tenant policy) · hard-won law 14
#           (the partition half is PostgreSQL's; SQLite has none)
# Tests:    this file
# Impacts:  core/partitioning.py ensure_partitions_cover ·
#           08-qa/01-e2e/stack/seed_e2e_fixture.py
# ───────────────────────────────────────────────────────
"""The seed writes reads into months the database may never have been given.

`metering/0003` makes `meter_reads` partitions relative to the DAY IT RUNS —
24 months back, 3 ahead. The e2e fixture writes a FIXED window that starts in
September 2024. A database migrated in August or September 2026 holds that
month; one migrated from 2026-10-01 does not, and seeding failed. The fix is that
whatever writes a month makes sure the month exists first — never a moved date.

⚠ WHAT WOULD MAKE THIS PASS WRONGLY: a helper that creates the partition and not
its tenant policy (an unguarded partition leaks every utility's reads), so the
PostgreSQL case asserts BOTH; and a seed whose window happens to sit inside the
bootstrap, so the second case asserts the window really does start before it.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest
from django.db import connection

from core import partitioning
from tests.isolation_helpers import requires_postgres

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "08-qa/01-e2e/stack/seed_e2e_fixture.py"


def _fixture_module():
    spec = importlib.util.spec_from_file_location("seed_e2e_fixture_9033", FIXTURE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@requires_postgres
@pytest.mark.django_db
def test_a_month_older_than_the_bootstrap_window_is_created_and_guarded():
    names = partitioning.ensure_partitions_cover("meter_reads", date(2019, 11, 1), date(2020, 1, 1))
    assert names == ["meter_reads_2019_11", "meter_reads_2019_12", "meter_reads_2020_01"]
    children = set(partitioning.partition_children("meter_reads"))
    assert set(names) <= children
    # Guarded in the same breath — never a reachable unguarded state.
    assert not set(names) & set(partitioning.unguarded_partitions("meter_reads"))
    # Idempotent: a second call changes nothing and does not raise.
    assert partitioning.ensure_partitions_cover("meter_reads", date(2019, 11, 1), date(2020, 1, 1)) == names
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_class WHERE relname = 'meter_reads_2019_12'")
        assert cursor.fetchone()[0] == 1


def test_the_range_is_inclusive_and_refuses_a_backwards_range():
    assert partitioning.partition_names_between("meter_reads", date(2024, 9, 1), date(2024, 11, 30)) == [
        "meter_reads_2024_09",
        "meter_reads_2024_10",
        "meter_reads_2024_11",
    ]
    with pytest.raises(partitioning.PartitioningError):
        partitioning.partition_names_between("meter_reads", date(2025, 1, 1), date(2024, 1, 1))


def test_the_seed_ensures_every_month_it_writes_and_the_call_is_load_bearing(monkeypatch):
    module = _fixture_module()
    first = date(*module.READ_MONTHS[0], 1)
    last = date(*module.READ_MONTHS[-1], 1)
    # The window really does start before a bootstrap made on 2026-10-01 — so
    # without the call this seed fails on a fresh database. If the window ever
    # moves inside the bootstrap this case says so instead of passing vacuously.
    bootstrap_start = partitioning.add_months(date(2026, 10, 1), -24)
    assert first < bootstrap_start, (first, bootstrap_start)

    calls = []
    monkeypatch.setattr(
        partitioning,
        "ensure_partitions_cover",
        lambda table, start, end: calls.append((table, start, end)) or [],
    )
    module._ensure_read_partitions()
    assert calls == [("meter_reads", first, last)]
