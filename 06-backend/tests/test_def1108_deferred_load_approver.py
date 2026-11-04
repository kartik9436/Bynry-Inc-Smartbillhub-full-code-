# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-1108 (high) — a deferred load that needs BR-MET-098 approval
#           ALWAYS refused in the WORKER, because `_JobActor` carries no role.
# Decision: 12-governance/02-decision-log.md, 2026-08-27 — "THE APPROVER ON A
#           DEFERRED LOAD WAS ALREADY DECIDED AT THE DOOR, AND THE WORKER WAS
#           ASKING AGAIN". A lane decision, not a PO ruling: BR-MET-098 is
#           CONFIRMED and already names the approver by ROLE, and the product
#           already asks that named person on the request that ENQUEUES the
#           run. Nothing was open; a check was in the wrong place.
# Rules:    BR-MET-098 (the two bars + the approver clause) · BR-MET-035 ·
#           BR-SHL-025 (defence in depth) · CR-026 (ASYNC_ROW_BAR = 5,000)
# Impacts:  apps/metering/import_runs.py (load · _load_locked · _JobActor)
# ───────────────────────────────────────────────────────
"""The guard that should have existed: nothing exercised the deferred load
path ACROSS the approval bar.

⚠ **WHY THIS FILE IS SEPARATE, AND WHY IT IS FAST.** The one test that covered
this seam — `test_cr028_import_targets.py::test_t6__six_thousand_real_rows_
cross_the_async_bar_and_complete` — is `@pytest.mark.slow` in a file that takes
3–5 minutes, which is exactly what makes a targeted `-k` run the habit: the
same condition that hid `DEF-1105`. **A guard nobody runs is not a guard.**
These tests drive the SAME seam on the committed 20-row fixture by lowering
`ASYNC_ROW_BAR` for the duration, so the deferral is real and the worker is
real, at 20 rows instead of 6,000.

**MEASURED, so the claim is not just a comment (hard-won law 1).** Every test
CALL here is under a second — the defect's own case is `0.65s`, against
`110.25s` for `T6`. What the file costs is the shared `seeded` fixture, ~7s per
test, which a full-suite run is paying anyway. **And this file carries NO
`slow` marker**, which is the point: `T6` is the only other test that reaches
this seam and it is marked slow in a 3–5 minute file, so the habit that hid the
defect — a targeted `-k` run — skips it and does not skip this.

**THE BAR IS MONKEYPATCHED, NEVER CHANGED.** `test_the_ratified_bars_are_
untouched` asserts CR-026's 5,000 and BR-MET-098's 5 / 10 in the module, so a
lane that "fixes" a slow test by lowering the constant breaks this file rather
than shipping it.

THE RED THIS FILE WAS WRITTEN AGAINST — branch tip `c260f64`, before a line of
the fix existed, reproduced in a detached worktree:

    tests/test_cr028_import_targets.py::test_t6__six_thousand_real_rows_cross_the_async_bar_and_complete
    apps/metering/import_runs.py:4946: in _load_apply
        return _load_locked(actor, run_id, write_mode, data, reporter)
    E           core.errors.BizError: BIZ-APPROVAL (metering.import.approver_role)
    apps/metering/import_runs.py:5122: BizError
    1 failed, 14 deselected, 5 warnings in 110.25s
"""

import pytest

from apps.metering import import_progress, import_runs, models as metering_models
from core import errors
from core import jobs as core_jobs

from tests.test_cr028_import_targets import ALL_OFF, METERS_MAPPING, _extract, _fixture
from tests.test_cr028_seed import seeded, silvercreek  # noqa: F401 — fixture chain
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _shared_progress_table(settings):
    """The gauge's isolated writer calls postgres' `set_config`, which the
    sqlite test database does not have. `test_t6` takes the same override for
    the same reason; it changes where the gauge row is written, never what the
    stages do."""
    settings.IMPORT_PROGRESS_ISOLATED = False


def _validated_over_the_bar(tenant, actor, monkeypatch):
    """The committed 20-row meters fixture walked to `validated`, with the
    async bar lowered so stage 4 DEFERS exactly as a 6,000-row file does.

    The fixture rejects 3 of its 20 rows (CR-028's worked shape), and 3 of 20
    is 15% — over `APPROVAL_PCT = 5`. So `dry_run` answers `required: True`,
    and this run crosses BOTH bars: the condition `DEF-1108` needs, and the
    reason no fast test ever reached it.

    ⚠ **EACH STAGE RE-ENTERS THE TENANT CONTEXT.** `core_jobs.run_pending` runs
    the job body under the RECORD's own tenant (B3's worker posture) and exits
    that context on the way out — so an ambient context does not survive a
    worker call, exactly as it would not in production where the poller is a
    fresh request. `test_t6` is shaped the same way for the same reason.
    """
    monkeypatch.setattr(import_runs, "ASYNC_ROW_BAR", 5)
    with tenant_ctx(tenant):
        run = _extract(actor, "assets_meters", _fixture("assets_meters.csv"))
        run_id = run["id"]
        transform = import_runs.transform(
            actor, run_id, {"mapping": METERS_MAPPING, "row_handling": ALL_OFF}
        )
        assert transform["deferred"] is True, "the lowered bar must really defer"
        core_jobs.run_pending(transform["job_id"])
    with tenant_ctx(tenant):
        validate = import_runs.validate(actor, run_id)
        assert validate["deferred"] is True
        core_jobs.run_pending(validate["job_id"])
    with tenant_ctx(tenant):
        figures = import_runs.dry_run(actor, run_id, "insert")
        assert figures["approval"]["required"] is True, "the approval bar must be crossed"
    return run_id


def test_the_ratified_bars_are_untouched():
    """CR-026's async bar and BR-MET-098's two approval bars, asserted in the
    module. This file lowers the first per-test with `monkeypatch`; it must
    never be lowered in the source."""
    assert import_runs.ASYNC_ROW_BAR == 5_000
    assert import_runs.APPROVAL_PCT == 5
    assert import_runs.APPROVAL_ROWS == 10


def test_a_job_actor_carries_no_role_at_all():
    """The structural fact the whole defect rests on, asserted rather than
    assumed: `_JobActor` has an id and NO role, by design. If a future lane
    gives it one, this fails and sends the reviewer to the decision-log entry
    rather than to a three-minute integration test."""
    job_actor = import_runs._JobActor("11111111-1111-1111-1111-111111111111")
    assert getattr(job_actor, "role", None) is None
    assert "role" not in getattr(type(job_actor), "__slots__", ())
    assert import_runs._has_approver_role(job_actor) is False


def test_def1108__a_deferred_load_over_the_approval_bar_completes_in_the_worker(
    seeded, monkeypatch
):
    """⛔ **THE DEFECT ITSELF.** Before the fix this run answered 202 and then
    died in the worker with `BIZ-APPROVAL (metering.import.approver_role)` —
    not one good row written, and a role demand the operator never asked for
    and structurally could not satisfy."""
    tenant, actor = seeded
    run_id = _validated_over_the_bar(tenant, actor, monkeypatch)
    with tenant_ctx(tenant):
        load = import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
        assert load["deferred"] is True and load["stage"] == "load"
        core_jobs.run_pending(load["job_id"])

    finished = metering_models.ImportRun.objects.get(pk=run_id)
    assert finished.status == "loaded", "the worker must COMMIT, not refuse"
    assert finished.counts["created"] > 0, "the good rows must actually be written"


def test_def1108__the_approving_admin_is_stamped_on_the_job_payload(seeded, monkeypatch):
    """The answer is CARRIED, not re-derived: `load()` records WHO approved,
    after its own role check passed, so `_load_locked` can ask *"was this
    approval given by a role-checked approver?"* where a worker can answer."""
    tenant, actor = seeded
    run_id = _validated_over_the_bar(tenant, actor, monkeypatch)
    seen: list[dict] = []
    real_enqueue = core_jobs.enqueue

    def spy(kind, **kw):  # `enqueue(kind, *, payload, scope_key)` — payload is keyword-only
        seen.append(kw["payload"])
        return real_enqueue(kind, **kw)

    payload = {"write_mode": "insert", "approved": True}
    with tenant_ctx(tenant):
        monkeypatch.setattr(core_jobs, "enqueue", spy)
        import_runs.load(actor, run_id, payload)

    assert len(seen) == 1, "exactly one load job was enqueued"
    stamped = (seen[0].get("data") or {}).get(import_runs.APPROVED_BY_KEY)
    assert stamped == str(actor.id), "the approving admin's id rides the job"
    # …and `load()` worked on a COPY: the caller's dict comes back untouched,
    # so the strip-and-restamp cannot leak the engine's own stamp back to
    # whoever passed the dict in and be re-presented on a later call.
    assert payload == {"write_mode": "insert", "approved": True}


def test_def1108__a_clerk_is_refused_at_the_door_and_never_reaches_a_worker(seeded, monkeypatch):
    """⚠ **THE CHECK MOVED; IT WAS NOT REMOVED** — `DEF-545` is why, and this is
    the caller it named. A service-layer `load(clerk, run, approved=True)` skips
    `api.py` entirely. Under the bar the engine refused it correctly; over the
    bar it deferred and the clerk's self-approval was refused only BY ACCIDENT,
    in a worker. Now it is refused HERE, on the clerk's own call, with the
    identical `BIZ-APPROVAL` — and no job is enqueued at all."""
    tenant, actor = seeded
    run_id = _validated_over_the_bar(tenant, actor, monkeypatch)
    enqueued: list = []
    real_enqueue = core_jobs.enqueue

    def spy(kind, **kw):
        enqueued.append(kind)
        return real_enqueue(kind, **kw)

    with tenant_ctx(tenant):
        clerk = staff_actor(tenant, role="billing_clerk", email="def1108.clerk@test.invalid")
        monkeypatch.setattr(core_jobs, "enqueue", spy)
        with pytest.raises(errors.BizError) as caught:
            import_runs.load(clerk, run_id, {"write_mode": "insert", "approved": True})

    assert caught.value.code == errors.BIZ_APPROVAL
    assert caught.value.message_key == "metering.import.approver_role"
    assert enqueued == [], "the refusal happens BEFORE anything is enqueued"
    assert (
        metering_models.ImportRun.objects.get(pk=run_id).status == "validated"
    ), "a refused load must leave the run exactly where it was"


def test_def1108__a_hand_written_stamp_is_stripped_and_the_clerk_still_refused(seeded, monkeypatch):
    """**THE STAMP CANNOT BE FORGED.** `load()` copies the payload and strips
    any caller-supplied `APPROVED_BY_KEY` before anything reads it, then re-adds
    it only after its own role check passes. A clerk who writes the key by hand
    — with a real admin's id, the strongest form of the attempt — gains nothing
    and is refused on their role exactly as they are without it."""
    tenant, actor = seeded
    run_id = _validated_over_the_bar(tenant, actor, monkeypatch)
    with tenant_ctx(tenant):
        clerk = staff_actor(tenant, role="billing_clerk", email="def1108.forger@test.invalid")
        with pytest.raises(errors.BizError) as caught:
            import_runs.load(
                clerk,
                run_id,
                {
                    "write_mode": "insert",
                    "approved": True,
                    import_runs.APPROVED_BY_KEY: str(actor.id),
                },
            )

    assert caught.value.code == errors.BIZ_APPROVAL
    assert caught.value.message_key == "metering.import.approver_role"


def test_def1108__the_shared_body_accepts_the_doors_answer_from_a_real_job_actor(
    seeded, monkeypatch
):
    """⛔ **THE GUARD, DRIVEN DIRECTLY AT THE SEAM.** `_load_apply` is *"the one
    path a request and a worker share"*. Called with a REAL `_JobActor` — an id
    and no role, exactly what `_stage_job` builds — it must COMMIT when the
    door's answer is present. If a future edit re-introduces a role demand on
    this body, this fails in seconds rather than in a three-minute slow test."""
    tenant, actor = seeded
    run_id = _validated_over_the_bar(tenant, actor, monkeypatch)
    with tenant_ctx(tenant):
        job_actor = import_runs._JobActor(str(actor.id))
        assert getattr(job_actor, "role", None) is None, "the premise of the whole defect"
        import_runs._load_apply(
            job_actor,
            run_id,
            "insert",
            {"approved": True, import_runs.APPROVED_BY_KEY: str(actor.id)},
            import_progress.NULL,
        )

    assert metering_models.ImportRun.objects.get(pk=run_id).status == "loaded"


def test_def1108__the_shared_body_still_refuses_a_worker_with_no_answer_to_carry(
    seeded, monkeypatch
):
    """⚠ **AND THE CHECK WAS MOVED, NOT DELETED — this is the half that proves
    it.** The same `_JobActor`, the same run, WITHOUT the door's stamp, must
    still be refused with the identical `BIZ-APPROVAL`. An unstamped payload
    means `load()`'s role check never ran, and `DEF-545`'s engine layer exists
    for exactly that caller. **A fix that merely exempted workers would pass the
    test above and fail this one.**"""
    tenant, actor = seeded
    run_id = _validated_over_the_bar(tenant, actor, monkeypatch)
    with tenant_ctx(tenant):
        job_actor = import_runs._JobActor(str(actor.id))
        with pytest.raises(errors.BizError) as caught:
            import_runs._load_apply(
                job_actor, run_id, "insert", {"approved": True}, import_progress.NULL
            )

    assert caught.value.code == errors.BIZ_APPROVAL
    assert caught.value.message_key == "metering.import.approver_role"


def test_def1108__under_the_bar_nothing_changed(seeded):
    """The synchronous path is untouched: below `ASYNC_ROW_BAR` the request
    actor still carries a real role, `_load_locked` still refuses a clerk on it,
    and no stamp exists anywhere. `DEF-545`'s engine layer keeps working exactly
    as it did."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        run = _extract(actor, "assets_meters", _fixture("assets_meters.csv"))
        run_id = run["id"]
        import_runs.transform(actor, run_id, {"mapping": METERS_MAPPING, "row_handling": ALL_OFF})
        import_runs.validate(actor, run_id)
        assert import_runs.dry_run(actor, run_id, "insert")["approval"]["required"] is True
        clerk = staff_actor(tenant, role="billing_clerk", email="def1108.sync@test.invalid")
        with pytest.raises(errors.BizError) as caught:
            import_runs.load(clerk, run_id, {"write_mode": "insert", "approved": True})

    assert caught.value.code == errors.BIZ_APPROVAL
    assert caught.value.message_key == "metering.import.approver_role"


def test_def1108__the_sweep__the_two_worker_actor_postures_are_both_deliberate():
    """⚠ **THE SWEEP, KEPT HONEST.** If `_JobActor` has no role then EVERY
    `@require_role` reachable from a worker has this defect's shape. The
    decision-log entry swept all six registered job bodies by hand and found
    exactly one — this one. The repo has two live postures for a worker actor
    and both are asserted here, so a new job body cannot quietly acquire a third
    by accident:

      * **metering** — `_JobActor`, id only: the role was checked at the door
        and the ANSWER travels (`APPROVED_BY_KEY`).
      * **tenancy** — `_PlantActor`, which SETS `role = "system_admin"` on
        purpose (BR-TEN-001: the provisioning owner IS the tenant's System
        Admin).
    """
    from apps.tenancy.sample_data import _PlantActor

    assert import_runs._has_approver_role(import_runs._JobActor("x")) is False
    assert _PlantActor("x").role == "system_admin", (
        "tenancy manufactures the owner's role deliberately (BR-TEN-001) — if "
        "that changes, re-run the sweep in the DEF-1108 decision-log entry"
    )
