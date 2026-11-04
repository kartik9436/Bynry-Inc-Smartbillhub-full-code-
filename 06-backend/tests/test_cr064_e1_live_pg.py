# ── Trace ──────────────────────────────────────────────
# Change:   CR-064 task E1 (PO 2026-09-02) — *"Prove it by breaking it — force
#           one block to fail on a real PostgreSQL, and read the reason off the
#           screen"*.
# Rules:    CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#           PostgreSQL transaction, and the suite runs on SQLite, which does
#           not) · BR-TEN-063 (atomic per module — one block must not stop the
#           rest) · BR-TEN-060 (a block that did not seed is a NAMED line)
# ───────────────────────────────────────────────────────
"""CR-064 E1 — break a block for real, and follow the sentence to the wire.

⚠ **WHY THIS FILE EXISTS SEPARATELY FROM `test_cr064_seventeen_steps.py`, WHICH
ALREADY DRIVES A FAILING BLOCK.** That one raises a Python exception from a fake
seam. This one takes `meter_reads` away from the database underneath a real
seeder, so the block fails the way a genuine schema problem fails: a
`psycopg.errors.UndefinedTable` inside an open transaction.

**That difference is hard-won law 14, and it is the whole reason CR-064 task E1
says "on a real PostgreSQL".** Once any statement errors inside a PostgreSQL
transaction the transaction is ABORTED and every later query raises
`InFailedSqlTransaction` — so an orchestrator that caught the error and carried
on WITHOUT a savepoint would lose everything it did afterwards, at COMMIT, with
the entire suite green: `config/settings/test.py` hardcodes in-memory SQLite and
SQLite has no aborted-transaction state.

`seed_sample_data` opens a nested `transaction.atomic()` per block, which IS a
savepoint, and this is the test that proves it on the vendor where it matters.

RUN IT ON POSTGRESQL — it is `requires_postgres` and SKIPS elsewhere, loudly:

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \\
      SBH_TEST_DB_NAME=test_sbh_cr064 JOBS_EAGER=false \\
      python -m pytest tests/test_cr064_e1_live_pg.py --reuse-db -q -s
"""

import json

import pytest
from django.db import connection

from apps.tenancy import sample_data, selectors
from core import jobs as core_jobs

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    admin_actor,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

requires_postgres = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason="CR-064 E1 is about PostgreSQL's aborted-transaction state, which SQLite does not have",
)


@pytest.fixture()
def plant_tenant():
    tenant, _result = provisioned_tenant()
    return tenant


def _fake_seams_except(monkeypatch, *, keep: str) -> None:
    """One-line fakes on every seam EXCEPT the one whose real seeder we want.

    The real estate takes minutes to plant and this test is about ONE block, so
    everything else is stubbed. `keep` is left real so the break below reaches
    genuine SQL rather than a fake that would never touch the database.
    """
    from importlib import import_module

    for spec in sample_data.SAMPLE_MODULES:
        if spec.key == keep:
            continue
        services = import_module(f"apps.{spec.module}.services")
        monkeypatch.setattr(services, spec.seam, lambda actor: 1, raising=False)


@requires_postgres
def test_cr064_e1_a_real_postgres_failure_reaches_the_poll_body_on_that_step(
    plant_tenant, monkeypatch, capsys
):
    """E1: the table goes away, the block breaks, and step 6 carries the reason.

    Three things are asserted, and the third is the one law 14 is about:

      1. the block that broke is step **7 of 18** by name, and its `detail` is
         the DATABASE's own sentence — not ours, not a paraphrase;
      2. the seventeen around it still report, so one broken block did not take
         the run with it (BR-TEN-063);
      3. **the blocks AFTER the failure still SEEDED.** On PostgreSQL, without a
         savepoint, every one of them would have raised
         `InFailedSqlTransaction` instead — and the SQLite suite would still be
         green. That is the assertion that could not be made anywhere else.
    """
    with tenant_ctx(plant_tenant):
        _fake_seams_except(monkeypatch, keep="metering:seed_sample_reads")

        # ⚠ THE BREAK IS REAL SQL, NOT A RAISED PYTHON OBJECT. The table is
        # renamed out from under the seeder for the duration of the run, so the
        # seeder meets `UndefinedTable` mid-transaction exactly as it would meet
        # a migration that had not been applied.
        with connection.cursor() as cur:
            cur.execute("ALTER TABLE meter_reads RENAME TO meter_reads_cr064_e1")
        try:
            sample_data.seed_sample_data(admin_actor())
        finally:
            with connection.cursor() as cur:
                cur.execute("ALTER TABLE meter_reads_cr064_e1 RENAME TO meter_reads")

        record = core_jobs.enqueue(sample_data.PLANT_JOB_KIND, payload={})
        core_jobs.start(record["id"])
        core_jobs.record_progress(record["id"], done=7, total=18, checkpoint="Meter reads")
        body = selectors.job_poll(record["id"])

    steps = body["steps"]
    # ⚠ EIGHTEEN SINCE 2026-09-02 (`DEF-3340`) — `CR-062`'s addendum put the
    # Municipal discount in at position 6, so the reads block this case
    # breaks is SEVENTH. This file was left red on the branch when the rest
    # of CR-064's literals were corrected, because it is PostgreSQL-only and
    # the default suite skips it — which is law 14's trap wearing a
    # different hat: the vendor that can prove the thing is the vendor
    # nobody runs.
    assert len(steps) == 18

    # ⚠ SELECTED BY KEY, NEVER BY INDEX. An index into a list somebody else
    # can insert into is a check that moves under you: after the discount
    # went in at 6, `steps[5]` was the DISCOUNT and this case would have
    # asserted the database's sentence about the wrong step.
    broke = next(row for row in steps if row["key"] == "metering:seed_sample_reads")
    assert broke["position"] == 7
    assert broke["position"] == 1 + next(
        i
        for i, spec in enumerate(sample_data.SAMPLE_MODULES)
        if spec.key == "metering:seed_sample_reads"
    )
    assert broke["key"] == "metering:seed_sample_reads"
    assert broke["outcome"] == "failed"
    # (1) The DATABASE's own words, carried whole to the wire.
    assert "meter_reads" in broke["detail"]
    assert broke["error_code"]

    # (2) One block did not stop the rest — every step still reports.
    assert all(row["outcome"] != "not_started" for row in steps), (
        "a block that broke left later blocks unrecorded — the run stopped"
    )

    # (3) ⚠ LAW 14'S ASSERTION. Blocks AFTER the failure seeded. Without the
    # per-block savepoint every one of these would carry `InFailedSqlTransaction`
    # instead, and this is the only vendor that can say so.
    # ⚠ SLICED FROM THE BREAK, NOT FROM A TYPED INDEX. `steps[6:]` was the
    # rows after the break while the break was sixth; once it moved the
    # window silently INCLUDED the failed block itself, and a count with a
    # floor under it still passed. A window that drifts onto the wrong rows
    # is worse than no window, because it is trusted.
    later = steps[steps.index(broke) + 1 :]
    after = [row for row in later if row["outcome"] == "seeded"]
    assert len(after) >= 10, (
        "the failed statement poisoned the transaction — the savepoint is gone "
        f"(only {len(after)} of the {len(later)} later blocks seeded)"
    )

    # Printed so the captured body can be lifted into the screen's own fixture
    # — the sentence a person will read comes from HERE and is not retyped.
    with capsys.disabled():
        print("\n──── CR-064 E1 · the poll body a browser would receive ────")
        print(json.dumps(body, indent=2, default=str))


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-064 task E1 (12-governance/11-change-requests.md)
# generated: 2026-09-02 by the CR-064 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: PostgreSQL-only by design — it asserts a PostgreSQL behaviour and
#   says so in its skip reason rather than passing vacuously on SQLite
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
