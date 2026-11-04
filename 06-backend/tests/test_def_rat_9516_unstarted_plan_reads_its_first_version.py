# ── Trace ──────────────────────────────────────────────
# Change:  CR-167-BRC10 round 4 task 10 (lane PLAN-WALK) — the full web walk.
# Defect:  DEF-RAT-9516 — a plan that has not started yet was READ "as of
#          today" as its NEWEST version: with v1 from 11/01/2026 ($10.00
#          minimum) and v2 from 01/01/2027 ($12.00), today (10/03/2026) the
#          tabs and Edit showed $12.00, Fix a mistake corrected v2 as
#          "v2 · today", and Audit called an edit made while only v1 existed
#          "v2". The plan READS now take a day no window covers as the first
#          version that starts after it; billing's `version_on` is untouched.
# Rules:   BR-RAT-1066 (a plan version has dates) · BR-RAT-1067
# ───────────────────────────────────────────────────────
"""Written RED against the tip before the fix (quoted in `CR-167-BRC10` §18)."""

import pytest

from apps.rating import plan_reads, plan_versioning, plan_writes
from apps.rating import models

from tests.test_cr167_plan_fixes import stored_audit  # noqa: F401 — the real audit store
from tests.test_cr167_plans_round2 import _contract, _new_version, _schedule
from tests.test_cr167_plans_round2 import _today  # noqa: F401 — the autouse "today" (10/03/2026)
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _unstarted(env):
    """v1 from 11/01/2026 at $10.00, then v2 from 01/01/2027 at $12.00 —
    both published, today 10/03/2026 (nothing in force yet)."""
    schedule = _schedule(env)
    with tenant_ctx(env.tenant):
        plan = plan_writes.create(env.admin, _contract(schedule, effective_from="2026-11-01", publish=True))
    return plan


def test_def_rat_9516__today_reads_the_version_that_will_apply_first(env):
    plan = _unstarted(env)
    _new_version(env, plan)
    with tenant_ctx(env.tenant):
        sections = plan_reads.plan_sections(plan["id"])
    assert sections["plan_version"]["version"] == 1
    assert sections["plan_version"]["effective_from"] == "2026-11-01"
    assert sections["details"]["minimum_bill_display"] == "10.00"


def test_def_rat_9516__an_edit_before_the_start_is_named_v1_in_audit(env, stored_audit):  # noqa: F811
    plan = _unstarted(env)
    with tenant_ctx(env.tenant):
        plan_writes.patch(env.admin, plan["id"], {"details": {"description": "Homes from November."}})
    _new_version(env, plan)
    with tenant_ctx(env.tenant):
        rows = plan_reads.plan_audit_rows(list(plan_reads.plan_audit_queryset(plan["id"], "plan")))
    edited = [row for row in rows if row["change"] == "edited"]
    assert [row["version"]["version"] for row in edited] == [1]


def test_def_rat_9516__billing_still_reads_each_day_by_its_window(env):
    """The guard: billing's `version_on` is unchanged — 12/31/2026 v1,
    01/01/2027 v2."""
    plan = _unstarted(env)
    _new_version(env, plan)
    with tenant_ctx(env.tenant):
        assert plan_versioning.version_on(plan["id"], plan_versioning.date(2026, 12, 31)).version_no == 1
        assert plan_versioning.version_on(plan["id"], plan_versioning.date(2027, 1, 1)).version_no == 2
        assert models.RatePlan.objects.filter(pk=plan["id"]).count() == 1


def test_def_rat_9516__a_duplicate_of_an_unstarted_plan_copies_the_version_it_starts_with(env):
    plan = _unstarted(env)
    _new_version(env, plan)
    with tenant_ctx(env.tenant):
        copy = plan_writes.duplicate(env.admin, plan["id"], {"name": "Copy", "code": "CPY"})
        row = models.RatePlan.objects.get(pk=copy["id"])
    assert str(row.minimum_bill_amount).startswith("10.")
