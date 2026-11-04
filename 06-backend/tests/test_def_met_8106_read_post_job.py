# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-MET-8106 (a 480-reading post ran inside the request and was
#           killed at 60 s after the readings were saved) · DEF-MET-8107 (~52
#           SQL statements per posted reading) · DEF-MET-8108 (the monthly-usage
#           rebuild ran in the request and stopped part-way with no record)
# Ruling:   PO 2026-09-30, decision log "READS UPLOAD 500 ON 480 READINGS" —
#           fixes (A) background post with progress, (B) cut the statements,
#           (C) the rebuild out of the request, recorded and resumable.
# Rules:    BR-MET-055 (the post as a job with progress) · BR-MET-940 (partial
#           posting, unchanged) · hard rule 6 (a second post is refused) ·
#           BR-MET-141 clause 6 (nothing bills from monthly usage) ·
#           DEF-AST-8102 / G140 (a job body reaches no role guard)
# Timing:   10-scripts/def_met_8106_read_post_cost.py (PostgreSQL, 100/480/1000)
# ───────────────────────────────────────────────────────
"""The read-batch post: in a worker above the bar, cheaper per reading, and a
monthly-usage rebuild that can be cut short and pick up where it stopped.

RED FIRST, on the branch base `e04a500af` (the transcripts are in the fix
commit and in `DEF-MET-8106..8108`'s rows):

  * the deferral cases failed on `AssertionError: 4 rows over a bar of 3 must
    not post inline` / `assert 200 == 202` — the base posted inline over a bar
    it did not have;
  * the budget case measured **45.0 statements per reading** (`237 statements
    at 5, 687 at 15`) against a budget of 17;
  * the rebuild cases failed with `KeyError: 'usage_refresh_accounts'` and
    `has no attribute 'USAGE_REFRESH_CHUNK'` — there was no job, the rebuild
    ran inside the post and its progress lived only in the response.

  9 failed, 2 passed on the base: the two that passed are the guards that
  must hold on BOTH sides — a refusal still reaches the clerk, and a second
  reading for one meter still judges against the first.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.customers import services as customers_services
from apps.metering import api, models, services
from apps.tenancy import services as tenancy_services
from core import errors
from core import jobs as core_jobs

from tests import identity_fixtures
from tests.test_def658_read_carries_its_account import _published_plan
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (
    a_meter,
    csv_body,
    make_premises,
    make_unit,
    seed_config,
    stage,
    tenant_ctx,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: Statements one more posted reading may cost — the SLOPE, so the post's
#: fixed cost (the lock, the batch row, the audit row, the export and
#: reconciliation passes) cancels. MEASURED by this test on SQLite:
#: **45.0 before** (branch base `e04a500af`, the usage rebuild's ~10 per
#: reading included because the base ran it inside the request) → **17.0
#: after**: the savepoint pair (law 14), the lineage head, the prior actual
#: head, the trailing actuals, the standing estimates, the unit's plan, the
#: asset's current unit and its assignments, the route hops the fixture's
#: route-less meters fall through to (four), the INSERT and the staged row's
#: one UPDATE. Held AT the measured figure so a regression of one statement per
#: reading goes red; the PostgreSQL profile (17.3 per reading, the same
#: statements) is in `10-scripts/def_met_8106_read_post_cost.py`'s table.
POST_STATEMENTS_PER_READING = 17


class _CapturedDispatch:
    """Record each job instead of running it in the enqueue (JOBS_EAGER) or
    handing it to a broker; `core_jobs.run_pending` then runs it as the worker
    would. `test_def_ast_8102_job_load`'s shape."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def __enter__(self) -> "_CapturedDispatch":
        core_jobs.set_job_dispatcher(self.records.append)
        return self

    def __exit__(self, *exc_info: object) -> None:
        core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)

    def kinds(self) -> list[str]:
        return [r["kind"] for r in self.records]

    def of(self, kind: str) -> dict:
        found = [r for r in self.records if r["kind"] == kind]
        assert len(found) == 1, (kind, self.kinds())
        return found[0]


def _occupied_meters(actor, tenant, count: int, *, prefix: str = "RP") -> list[str]:
    """`count` meters, each on its own unit with an ACTIVE account — the shape
    a real cycle has, so the occupancy and account-stamp paths are exercised."""
    plan = _published_plan(tenant, "electric")
    premises = make_premises(actor, address_line=f"77 {prefix} Row", services_available=["electric"])
    numbers = []
    for n in range(count):
        unit = make_unit(actor, premises["id"], label=f"{prefix} {n}", services=["electric"])
        services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
        services.ensure_service_point(unit["id"], "electric")
        account = customers_services.create_account(
            actor,
            {
                "unit_id": unit["id"],
                "account_type": "residential",
                "opened_at": "2024-01-05",
                "contact": {"full_name": f"{prefix} Resident {n}", "email": f"{prefix}{n}@x.test"},
                "customer": identity_fixtures.customer_block(
                    f"{prefix} Resident {n}", account_type="residential"
                ),
            },
        )
        customers_services.activate_account(actor, account["id"])
        number = f"{prefix}-{n:04d}"
        a_meter(actor, number, unit_id=unit["id"])
        numbers.append(number)
    return numbers


def _staged(actor, numbers: list[str], *, day: str = "2026-08-03") -> dict:
    batch = stage(
        actor,
        csv_body(*[f"{m},{day},{4000 + i},total,E," for i, m in enumerate(numbers)]),
    )
    services.validate_read_batch(actor, batch["id"])
    return batch


# ═══ (A) — above the bar, the post is a job ═════════════════════════════════


def test_def_met_8106__a_batch_over_the_bar_posts_in_a_worker(
    brazos, marcus, monkeypatch, settings
):
    """The request answers at once with the job; the WORKER — whose actor has
    no role — writes every reading, moves the gauge to the end, and keeps the
    receipt the screen collects afterwards.

    `IMPORT_PROGRESS_ISOLATED=False` so the gauge is written on the test's own
    connection: the job row exists only inside the test's transaction, which a
    second connection cannot see (the production path is the second one)."""
    settings.IMPORT_PROGRESS_ISOLATED = False
    monkeypatch.setattr(services, "READ_POST_ASYNC_ROW_BAR", 3, raising=False)
    with tenant_ctx(brazos):
        seed_config()
        numbers = _occupied_meters(marcus, brazos, 4)
        batch = _staged(marcus, numbers)
        with _CapturedDispatch() as dispatched:
            result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        assert result.get("deferred") is True, "4 rows over a bar of 3 must not post inline"
        assert result["async"] is True and result["job_id"] and result["status_url"]
        assert result["receipt_url"] == f"/read-batches/{batch['id']}/post-receipt"
        # Nothing is written by the request.
        assert models.MeterRead.objects.filter(import_batch_id=batch["id"]).count() == 0
        assert models.ReadImportBatch.objects.get(pk=batch["id"]).status == "validated"
        job = dispatched.of(services.READ_POST_JOB)
        assert job["payload"]["actor_user_id"] == str(marcus.id)
        assert "role" not in job["payload"]

        with _CapturedDispatch() as after_post:
            core_jobs.run_pending(job["id"])

    with tenant_ctx(brazos):
        done = core_jobs.current(job["id"])
        assert done["status"] == "succeeded", done
        assert done["progress"] == {"done": 4, "total": 4}
        assert done["result_link"] == f"/read-batches/{batch['id']}/post-receipt"
        assert models.MeterRead.objects.filter(import_batch_id=batch["id"]).count() == 4
        receipt = models.ReadImportBatch.objects.get(pk=batch["id"]).post_receipt
        assert receipt["posted_reads"] == 4 and receipt["held_reads"] == 0
        # (C) the worker's post queued the rebuild in its turn.
        assert after_post.kinds() == [services.USAGE_REFRESH_JOB]


def test_def_met_8106__at_or_below_the_bar_nothing_changes(brazos, marcus, monkeypatch):
    monkeypatch.setattr(services, "READ_POST_ASYNC_ROW_BAR", 3, raising=False)
    with tenant_ctx(brazos):
        seed_config()
        numbers = _occupied_meters(marcus, brazos, 3)
        batch = _staged(marcus, numbers)
        with _CapturedDispatch() as dispatched:
            result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        assert not result.get("deferred")
        assert result["posted_reads"] == 3 and result["async"] is False
        assert services.READ_POST_JOB not in dispatched.kinds()


def test_def_met_8106__the_refusals_a_clerk_can_act_on_still_reach_the_clerk(
    brazos, marcus, monkeypatch
):
    """Certification missing is refused ON THE REQUEST — never queued to fail
    in a worker where nobody is looking."""
    monkeypatch.setattr(services, "READ_POST_ASYNC_ROW_BAR", 1, raising=False)
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = _staged(marcus, ["M-7001", "M-7002"])
        with _CapturedDispatch() as dispatched:
            with pytest.raises(errors.ValidationError) as refused:
                services.commit_read_batch(marcus, batch["id"], {"certified": False})
        assert refused.value.message_key == "metering.read_batch.certification_required"
        assert dispatched.records == []


def test_def_met_8106__no_worker_means_a_refusal_not_a_bar_that_never_moves(
    brazos, marcus, monkeypatch
):
    monkeypatch.setattr(services, "READ_POST_ASYNC_ROW_BAR", 1, raising=False)
    monkeypatch.setattr(core_jobs, "dispatch_is_ready", lambda *a, **k: (False, "no worker"))
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = _staged(marcus, ["M-7001", "M-7002"])
        with pytest.raises(errors.BizError) as refused:
            services.commit_read_batch(marcus, batch["id"], {"certified": True})
    assert refused.value.message_key == "metering.import.no_worker"


def test_def_met_8106__a_double_click_folds_into_the_job_already_queued(
    brazos, marcus, monkeypatch
):
    monkeypatch.setattr(services, "READ_POST_ASYNC_ROW_BAR", 1, raising=False)
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = _staged(marcus, ["M-7001", "M-7002"])
        with _CapturedDispatch():
            first = services.commit_read_batch(marcus, batch["id"], {"certified": True})
            second = services.commit_read_batch(marcus, batch["id"], {"certified": True})
    assert first["job_id"] == second["job_id"]


def test_def_met_8106__the_endpoint_answers_202_and_the_receipt_arrives_after(
    brazos, marcus, monkeypatch
):
    """Wired, not only built (hard-won law 2): the ROUTE answers 202 above the
    bar, and `GET /read-batches/{id}/post-receipt` is 404 until the job has run
    and the synchronous receipt's shape after."""
    monkeypatch.setattr(services, "READ_POST_ASYNC_ROW_BAR", 1, raising=False)
    user = SimpleNamespace(id=marcus.id, pk=marcus.id, is_authenticated=True)
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = _staged(marcus, ["M-7001", "M-7002"])
    with _CapturedDispatch() as dispatched:
        posted = api_call(
            api.read_batch_post,
            "post",
            user=user,
            role="billing_clerk",
            tenant=brazos,
            data={"certified": True},
            batch_id=batch["id"],
        )
    assert posted.status_code == 202, posted.data
    early = api_call(
        api.read_batch_post_receipt,
        "get",
        user=user,
        role="billing_clerk",
        tenant=brazos,
        batch_id=batch["id"],
    )
    assert early.status_code == 404
    with tenant_ctx(brazos):
        core_jobs.run_pending(dispatched.of(services.READ_POST_JOB)["id"])
    receipt = api_call(
        api.read_batch_post_receipt,
        "get",
        user=user,
        role="billing_clerk",
        tenant=brazos,
        batch_id=batch["id"],
    )
    assert receipt.status_code == 200, receipt.data
    assert receipt.data["posted_reads"] == 2
    assert receipt.data["status"] == "posted"
    assert receipt.data["rejects_download"].endswith("results.csv?kind=failures")


def test_def_met_8106__a_second_delivery_of_a_finished_post_writes_nothing_twice(
    brazos, marcus, monkeypatch
):
    """Hard rule 6: the job is redelivered after it committed (acks-late). The
    body meets `already_posted` under the lock and no reading is filed twice."""
    monkeypatch.setattr(services, "READ_POST_ASYNC_ROW_BAR", 1, raising=False)
    actor = services._PostJobActor(marcus.id)
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        a_meter(marcus, "M-7002", unit_label="Unit B", address="1410 Bluestem Ln")
        batch = _staged(marcus, ["M-7001", "M-7002"])
        with _CapturedDispatch():
            services._commit_read_batch_body(actor, batch["id"], {"certified": True})
            with pytest.raises(errors.BizError) as again:
                services._commit_read_batch_body(actor, batch["id"], {"certified": True})
        assert again.value.message_key == "metering.read_batch.already_posted"
        assert models.MeterRead.objects.filter(import_batch_id=batch["id"]).count() == 2


# ═══ (B) — the statement budget ═════════════════════════════════════════════


def _post_cost(actor, numbers: list[str]) -> int:
    batch = _staged(actor, numbers)
    with _CapturedDispatch():
        with CaptureQueriesContext(connection) as captured:
            result = services.commit_read_batch(actor, batch["id"], {"certified": True})
    assert result["posted_reads"] == len(numbers), result.get("held_rows")
    return len(captured.captured_queries)


def test_def_met_8107__a_posted_reading_costs_at_most_the_budget(brazos, marcus, monkeypatch):
    """The SLOPE of statements against readings: the same post at 5 and at 15
    readings, so only what each extra reading costs is left."""
    monkeypatch.setattr(services, "READ_POST_ASYNC_ROW_BAR", 10_000, raising=False)
    with tenant_ctx(brazos):
        seed_config()
        small_meters = _occupied_meters(marcus, brazos, 5, prefix="S")
        large_meters = _occupied_meters(marcus, brazos, 15, prefix="L")
        small = _post_cost(marcus, small_meters)
        large = _post_cost(marcus, large_meters)
    per_reading = (large - small) / 10
    print(f"DEF-MET-8107: {small} statements at 5, {large} at 15 → {per_reading:.1f}/reading")
    assert per_reading <= POST_STATEMENTS_PER_READING, (
        f"a posted reading costs {per_reading:.1f} statements; the budget is "
        f"{POST_STATEMENTS_PER_READING} (DEF-MET-8107 — 480 readings must post well inside 60 s)"
    )


def test_def_met_8107__two_readings_for_one_meter_still_judge_the_second_against_the_first(
    brazos, marcus
):
    """The one thing the batch cache must NOT hold: a meter's prior reading. A
    file with the 3rd and the 10th of August for one meter posts the 10th with
    the 3rd as its prior — the consumption is the difference, not the whole
    register."""
    with tenant_ctx(brazos):
        seed_config()
        a_meter(marcus, "M-7001")
        batch = stage(
            marcus,
            csv_body("M-7001,2026-08-03,4000,total,E,", "M-7001,2026-08-10,4100,total,E,"),
        )
        services.validate_read_batch(marcus, batch["id"])
        with _CapturedDispatch():
            result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        assert result["posted_reads"] == 2
        second = models.MeterRead.objects.get(import_batch_id=batch["id"], read_at__day=10)
    assert second.prior_value == 4000
    assert second.consumption == 100


# ═══ (C) — the monthly-usage rebuild is its own, resumable job ═════════════


def test_def_met_8108__the_post_queues_the_rebuild_instead_of_running_it(
    brazos, marcus, monkeypatch
):
    from apps.metering import monthly_usage_service

    restated: list[str] = []
    real = monthly_usage_service.recompute_account

    def _counting(account_id, **kwargs):
        restated.append(str(account_id))
        return real(account_id, **kwargs)

    monkeypatch.setattr(monthly_usage_service, "recompute_account", _counting)
    with tenant_ctx(brazos):
        seed_config()
        numbers = _occupied_meters(marcus, brazos, 2)
        batch = _staged(marcus, numbers)
        with _CapturedDispatch() as dispatched:
            result = services.commit_read_batch(marcus, batch["id"], {"certified": True})
        assert result["usage_refresh_accounts"] == 2
        assert result["usage_refresh_status"] == "queued"
        job = dispatched.of(services.USAGE_REFRESH_JOB)
        assert result["usage_refresh_job_id"] == job["id"]
        # Nothing restated by the request — that was the 60-second tail.
        assert restated == []
        accounts = job["payload"]["account_ids"]
        core_jobs.run_pending(job["id"])
    assert restated == accounts
    with tenant_ctx(brazos):
        finished = core_jobs.current(job["id"])
        assert finished["status"] == "succeeded"
        assert finished["checkpoint"]["next"] == 2
        assert finished["checkpoint"]["accounts_restated"] == 2


def test_def_met_8108__a_rebuild_cut_short_resumes_where_it_stopped(
    brazos, marcus, monkeypatch
):
    """The reproduction's 267-of-480, in miniature: the worker dies after the
    first account. The record says so (failed, checkpoint `next: 1`), and the
    kernel's own resume carries on from account 2 — account 1 is not restated
    a second time."""
    monkeypatch.setattr(services, "USAGE_REFRESH_CHUNK", 1)
    with tenant_ctx(brazos):
        seed_config()
        numbers = _occupied_meters(marcus, brazos, 3)
        batch = _staged(marcus, numbers)
        with _CapturedDispatch() as dispatched:
            services.commit_read_batch(marcus, batch["id"], {"certified": True})
        job = dispatched.of(services.USAGE_REFRESH_JOB)
        ids = job["payload"]["account_ids"]

        real = services._refresh_monthly_usage
        seen: list[list[str]] = []

        def _dies_on_the_second_chunk(actor, account_ids, **kwargs):
            seen.append(list(account_ids))
            if len(seen) == 2:
                raise RuntimeError("worker killed")
            return real(actor, account_ids, **kwargs)

        monkeypatch.setattr(services, "_refresh_monthly_usage", _dies_on_the_second_chunk)
        with pytest.raises(RuntimeError):
            core_jobs.run_pending(job["id"])
    with tenant_ctx(brazos):
        stopped = core_jobs.current(job["id"])
        assert stopped["status"] == "failed"
        assert stopped["checkpoint"]["next"] == 1, "the record names where it stopped"
        monkeypatch.setattr(services, "_refresh_monthly_usage", real)
        seen.clear()

        calls: list[list[str]] = []

        def _counting(actor, account_ids, **kwargs):
            calls.append(list(account_ids))
            return real(actor, account_ids, **kwargs)

        monkeypatch.setattr(services, "_refresh_monthly_usage", _counting)
        core_jobs.resume(job["id"])
    with tenant_ctx(brazos):
        assert calls == [[ids[1]], [ids[2]]], "resumed from the checkpoint, not from the top"
        finished = core_jobs.current(job["id"])
        assert finished["status"] == "succeeded"
        assert finished["checkpoint"]["next"] == 3
