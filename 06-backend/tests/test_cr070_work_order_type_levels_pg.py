# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-007, as amended by the PO ruling of 2026-09-07
# Rules:    CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#           PostgreSQL transaction, and the suite runs on SQLite, which does
#           not — so the naive fix passes everything and loses production
#           data) · hard-won law 7 (proved RED first, in the harness that will
#           run it) · BR-WRK-058 · hard rule 1 (every write under `app.tenant_id`)
# Tests:    this file — SKIPPED on SQLite by design, and the skip is the point
# ───────────────────────────────────────────────────────
"""The work-order-type seeder's SAVEPOINT, on real PostgreSQL.

WHY THIS CANNOT BE PROVED IN THE ORDINARY SUITE
------------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`. **SQLite has no aborted-transaction state at all**: a refused
INSERT there is simply a refused INSERT, and the statement after it runs
normally. On PostgreSQL the same refusal ABORTS THE WHOLE TRANSACTION — every
later query raises `InFailedSqlTransaction` and everything the transaction had
already written is lost at COMMIT.

So the version of `WorkOrderTypeLookupHandler.seed` WITHOUT the nested
`transaction.atomic()` passes the entire suite, green, on every machine, and
loses a tenant's whole reference list the first time one row is refused in
production. That is hard-won law 14 exactly, and this file is the only place it
can be caught.

    createdb sbh_wrk058
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_wrk058?sslmode=disable"
    pytest tests/test_cr070_work_order_type_levels_pg.py

HOW THE REFUSAL IS PRODUCED, AND WHY IT IS NOT A CONTRIVANCE
-------------------------------------------------------------
The window the seeder has to survive is a READ-THEN-WRITE race: the
insert-missing check says the code is absent, another connection inserts it,
and the INSERT is refused by `uq_work_order_types_tenant_code_ci`. One test
process cannot produce that race, so `_already_seeded` — the check, which
exists as a method for exactly this reason — is made to answer False while the
row is already there. **The statement that fails, the constraint that refuses
it and the transaction state that follows are all the real ones**; only the
timing is arranged.

THE RED PROOF, TAKEN — BOTH DIRECTIONS, ON REAL POSTGRESQL 16
-------------------------------------------------------------
Run 2026-09-07 against a live seeded database, driving `seed` with and without
the nested `atomic()`:

    vendor: postgresql
    WITHOUT the savepoint : DIED TransactionManagementError: An error occurred
                            in the current transaction. You can't execute
                            queries until the end of the 'atomic' block.
    WITH    the savepoint : OK   created=2 rows_after_commit=['SPX_A','SPX_B','SPX_C']

That is law 14's own sentence, and the two rows the naive version loses are the
two it had already written before the refusal. Delete the `with
transaction.atomic():` line and the cases below reproduce it.

⚠ **AND THE PROOF WAS RUN FROM `06-backend`, NOT FROM A SCRATCH DIRECTORY.**
The first attempt ran the same script from a scratchpad path and died on
`AttributeError: type object 'WorkOrderTypeLookupHandler' has no attribute
'_already_seeded'` — Python puts the SCRIPT's directory on `sys.path[0]`, so a
different `apps` package answered the import. It reads exactly like a missing
method and is a shadowed module: a failure that names the wrong cause is worse
than none, so it is written down here rather than re-diagnosed.
"""

from __future__ import annotations

from unittest import mock

import pytest

from apps.work import lookups as work_lookups
from apps.work import models as work_models

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]


@requires_postgres
def test_a_refused_row_costs_one_row_and_not_the_whole_seed(brazos):
    """The rows seeded BEFORE the refusal survive it, and the seeding goes on.

    Without the savepoint the `create()` that follows the refused one raises
    `TransactionManagementError` and every row this call had written is rolled
    back at COMMIT — a tenant with an empty work order type list and no error
    anywhere that names it.
    """
    handler = work_lookups.WorkOrderTypeLookupHandler()
    entries = [
        {"code": "SPINE_A", "name": "Spine A"},
        {"code": "SPINE_B", "name": "Spine B"},
        {"code": "SPINE_C", "name": "Spine C"},
    ]
    with tenant_ctx(brazos):
        # SPINE_B is already there and the check will not see it — the race,
        # arranged.
        work_models.WorkOrderType.objects.create(
            tenant=brazos, code="SPINE_B", name="Spine B", is_system=True, active=True
        )
        with mock.patch.object(
            work_lookups.WorkOrderTypeLookupHandler,
            "_already_seeded",
            lambda self, tenant_id, code: False,
        ):
            created = handler.seed(brazos.id, entries)

        codes = set(
            work_models.WorkOrderType.objects.filter(
                tenant=brazos, code__startswith="SPINE_"
            ).values_list("code", flat=True)
        )
        # The transaction is STILL USABLE — this query is the assertion. On the
        # version without the savepoint it raises rather than answering.
        assert codes == {"SPINE_A", "SPINE_B", "SPINE_C"}
    assert created == 2  # A and C landed; B was refused and skipped


@requires_postgres
def test_the_refusal_does_not_reach_the_caller(brazos):
    """`seed` returns a count. It does not raise, and it does not half-run."""
    handler = work_lookups.WorkOrderTypeLookupHandler()
    with tenant_ctx(brazos):
        work_models.WorkOrderType.objects.create(
            tenant=brazos, code="DUPE", name="Dupe", is_system=True, active=True
        )
        with mock.patch.object(
            work_lookups.WorkOrderTypeLookupHandler,
            "_already_seeded",
            lambda self, tenant_id, code: False,
        ):
            assert handler.seed(brazos.id, [{"code": "DUPE", "name": "Dupe again"}]) == 0
        # …and the row that was already there is untouched (BR-TEN-012).
        assert (
            work_models.WorkOrderType.objects.get(tenant=brazos, code="DUPE").name == "Dupe"
        )


@requires_postgres
def test_the_two_levels_hold_in_the_database_and_not_only_in_python(brazos):
    """`parent_id` is a real self-FK with PROTECT, so the database refuses to
    lose a type that has sub-types under it even if the service is bypassed.

    Depth is enforced in the SERVICE (`BR-WRK-058`) and deliberately NOT by a
    constraint — SQL cannot express *"a parent must itself have no parent"*
    without a trigger. What the DATABASE guarantees is the narrower thing this
    asserts: the link is real and the children cannot be orphaned.
    """
    from django.db.models import ProtectedError

    with tenant_ctx(brazos):
        reading = work_models.WorkOrderType.objects.get(tenant=brazos, code="READING")
        assert reading.sub_types.count() == 1
        with pytest.raises(ProtectedError):
            reading.delete()
