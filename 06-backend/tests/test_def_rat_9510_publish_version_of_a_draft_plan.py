# ── Trace ──────────────────────────────────────────────
# Change:  CR-167-BRC10 round 4 task 10 (lane PLAN-WALK) — the full web walk.
# Defect:  DEF-RAT-9510 — `POST /plans/{id}/versions/{n}/publish` accepted a
#          DRAFT plan's own v1: the version became published while the plan
#          stayed a draft. The server half of DEF-RAT-9506 (whose fix took the
#          screen's door away and left this one open).
# Rules:   BR-RAT-1066 (a version is published from a PUBLISHED plan; a draft
#          plan is published as a whole, by *Publish plan*)
# ───────────────────────────────────────────────────────
"""Written RED against the tip before the fix (quoted in `CR-167-BRC10` §18)."""

import pytest

from apps.rating import models, plan_versioning, plan_writes
from core import errors

from tests.test_cr167_plans_round2 import _contract, _new_version, _published, _schedule
from tests.test_cr167_plans_round2 import _today  # noqa: F401 — the autouse "today"
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def test_def_rat_9510__a_draft_plans_v1_is_not_published_through_the_version_door(env):
    schedule = _schedule(env)
    with tenant_ctx(env.tenant):
        # A start AFTER today: a past start is refused for another reason
        # (`version_start_in_past`) and would hide the defect.
        draft = plan_writes.create(env.admin, _contract(schedule, effective_from="2026-11-01"))
        with pytest.raises(errors.BizError) as caught:
            plan_writes.publish_version(env.admin, draft["id"], 1)
        # Nothing moved: the plan AND its version are still drafts.
        plan = models.RatePlan.objects.get(pk=draft["id"])
        statuses = list(models.PlanVersion.objects.filter(rate_plan=plan).values_list("status", flat=True))
    assert caught.value.message_key == "rating.plans.version_of_draft"
    assert plan.status == "draft"
    assert statuses == [plan_versioning.VERSION_DRAFT]


def test_def_rat_9510__a_published_plans_saved_v2_still_publishes(env):
    """The guard: the door DEF-RAT-9364 built for a published plan is unchanged."""
    plan, _ = _published(env)
    _new_version(env, plan, publish=False)
    with tenant_ctx(env.tenant):
        answer = plan_writes.publish_version(env.admin, plan["id"], 2)
    assert answer["version"] == 2
