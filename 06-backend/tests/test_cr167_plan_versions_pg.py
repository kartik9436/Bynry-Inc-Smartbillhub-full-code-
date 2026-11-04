# ── Trace ──────────────────────────────────────────────
# Change:  CR-167-BRC10 round 2 task 3 — the PostgreSQL half.
# Rules:   BR-RAT-1066 (a plan version has dates; billing gets exactly ONE per
#          date) · CLAUDE.md hard-won laws 7 and 14
# ───────────────────────────────────────────────────────
"""One plan version per date, and the database lock behind it, on a real
PostgreSQL 16.

    cd 06-backend
    DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> JOBS_EAGER=false \\
        pytest tests/test_cr167_plan_versions_pg.py --ds=config.settings.pgtest -s

Every case carries `requires_postgres` and SKIPS by name elsewhere — the
exclusion constraint does not exist on SQLite, so a green run there would prove
nothing (law 7, *incapable of failing*).

⚠ `ex_plan_versions_no_overlap` is DEFERRABLE INITIALLY DEFERRED and the test
transaction never commits, so the lock case says `SET CONSTRAINTS … IMMEDIATE`.
Without that line an overlap would pass whether or not the constraint existed.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction

from apps.rating import models, plan_reads, plan_versioning, plan_writes, resolution_catalogue

from tests.isolation_helpers import requires_postgres
from tests.test_cr167_plans_round2 import DEC_31, JAN_01, _new_version, _published
from tests.test_cr167_plans_round2 import _today  # noqa: F401 — the autouse "today"
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]


def check_deferred_now() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ex_plan_versions_no_overlap IMMEDIATE")
        cursor.execute("SET CONSTRAINTS ex_plan_versions_no_overlap DEFERRED")


def test_every_day_from_12_25_to_01_05_reads_exactly_one_version(env):
    """`BR-RAT-1066` on a real server: v1 to 12/31/2026, v2 from 01/01/2027.
    Every day answers ONE version — never both, never none — and R1's
    candidates cover each day exactly once."""
    plan, _ = _published(env)
    _new_version(env, plan)
    seen = {}
    with tenant_ctx(env.tenant):
        candidates = resolution_catalogue.plan_version_facts(plan["id"])
        day = date(2026, 12, 25)
        while day <= date(2027, 1, 5):
            version = plan_versioning.version_on(plan["id"], day)
            covering = [c for c in candidates if c.effective_from <= day and (c.effective_to is None or day <= c.effective_to)]
            assert len(covering) == 1, day
            assert covering[0].version == version.version_no
            seen[day] = version.version_no
            day += timedelta(days=1)
        floor_dec = plan_versioning.terms_on(models.RatePlan.objects.get(pk=plan["id"]), DEC_31)
        floor_jan = plan_versioning.terms_on(models.RatePlan.objects.get(pk=plan["id"]), JAN_01)
    assert {d: v for d, v in seen.items() if d <= DEC_31} == {d: 1 for d in seen if d <= DEC_31}
    assert {d: v for d, v in seen.items() if d >= JAN_01} == {d: 2 for d in seen if d >= JAN_01}
    assert floor_dec["minimum_bill_amount"] == Decimal("10.000000")
    assert floor_jan["minimum_bill_amount"] == Decimal("12.000000")


def test_the_lock_refuses_two_priceable_versions_on_one_date(env):
    """RED proof of the database half: a second PUBLISHED version whose window
    overlaps v1 is refused by `ex_plan_versions_no_overlap` — written straight
    to the table, past every service-layer check."""
    plan, _ = _published(env)
    with tenant_ctx(env.tenant):
        v1 = models.PlanVersion.objects.get(rate_plan_id=plan["id"], version_no=1)
        with pytest.raises(IntegrityError) as caught:
            with transaction.atomic():
                models.PlanVersion.objects.create(
                    tenant_id=v1.tenant_id,
                    rate_plan_id=plan["id"],
                    version_no=2,
                    snapshot={},
                    status="published",
                    effective_from=date(2026, 12, 1),
                )
                check_deferred_now()
    assert "ex_plan_versions_no_overlap" in str(caught.value)


def test_a_draft_or_a_corrected_row_is_outside_the_lock(env):
    """A *Save new version* draft and a superseded correction never price, so
    neither is in the lock (the predicate is the ruling)."""
    plan, _ = _published(env)
    _new_version(env, plan, publish=False)
    with tenant_ctx(env.tenant):
        check_deferred_now()
        plan_writes.correct(
            env.admin,
            plan["id"],
            {"details": {}, "version": 1, "minimum_bill_amount": "11.00", "reason": "Typed 10 for 11"},
        )
        check_deferred_now()
        assert plan_versioning.version_on(plan["id"], DEC_31).corrects_id is not None


def test_audit__rows_are_words_never_ids_or_json(env):
    """`DEF-RAT-9288`'s server half: the plan's Audit reads in words. The real
    audit store is put back for this case (the shared helpers capture rows in a
    list), because this read is a SQL UNION over the stored table."""
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    try:
        plan, _ = _published(env)
        _new_version(env, plan)
    finally:
        core_audit.set_audit_sink(previous)
    with tenant_ctx(env.tenant):
        qs = plan_reads.plan_audit_queryset(plan["id"], "plan")
        rows = plan_reads.plan_audit_rows(list(qs))
    changes = [row["change"] for row in rows]
    assert "created" in changes and "published" in changes
    for row in rows:
        for text in (row["before_display"], row["after_display"]):
            assert text is None or "{" not in text
