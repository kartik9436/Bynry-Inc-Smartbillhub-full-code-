# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-AST-8102 (critical) — an asset upload of more than 200 rows
#          wrote NOTHING: the load is deferred to a background job whose actor
#          carries no role (by design, `import_runs._JobActor`), and the
#          create path called the `@require_role`-guarded opening-read helper
#          unconditionally, so row 1 raised `AuthError` AUTH-002, the refusal
#          escaped the per-row catch and the whole load rolled back.
# Ruling:  PO GO 2026-09-30 on the defect, with its steps: skip the inner role
#          gate on the import path (never give the worker a role) · capture an
#          opening read only when the row HAS one · a non-rule exception on one
#          row rejects that row and the load continues.
# Rules:   BR-MET-035 (the role is checked at the door) · DEF-2515 / DEF-1108
#          (the same class, one level shallower) · CLAUDE.md law 14
# Tests:   this file; the static guard is gate G140 (job bodies reach no
#          role-guarded function)
# ───────────────────────────────────────────────────────
"""A 201-row devices upload, run the way production runs it: over the 200-row
load bar, so the load is DEFERRED and executed by the job runner as
`_JobActor` — no threshold is lowered, the real bar decides.

RED on the branch base `70c3cc7de` (clean worktree): the job raised
`core.errors.AuthError: AUTH-002 (BR-AST-032)` and the run held 0 assets.
"""

from __future__ import annotations

import csv
import io

import pytest

from apps.assets import models as asset_models
from apps.metering import import_runs
from apps.tenancy import services as tenancy_services
from core import errors
from core import jobs as core_jobs

from tests.test_def962_def963_assets_template import (  # noqa: F401 — fixtures
    ALL_OFF,
    _estate,
    ottumwa,
    ottumwa_admin,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ROWS = 201


class _CapturedDispatch:
    """Record the job instead of running it inside the enqueue (JOBS_EAGER)
    or handing it to a broker — then `run_pending` runs it as the worker."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def __enter__(self) -> "_CapturedDispatch":
        core_jobs.set_job_dispatcher(self.records.append)
        return self

    def __exit__(self, *exc_info: object) -> None:
        core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)


def _devices_file(rows: int) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["Device type", "External reference", "Serial number", "Service"])
    for n in range(rows):
        writer.writerow(["backflow", f"JOB-{n:04d}", f"SN-{n:04d}", "water"])
    return buffer.getvalue()


def test_def_ast_8102_a_deferred_load_of_201_devices_writes_all_201(ottumwa, ottumwa_admin):
    assert import_runs.async_row_bar(import_runs.TARGET_ASSETS_DEVICES, "load") < ROWS
    with tenant_ctx(ottumwa):
        _estate(ottumwa_admin, count=1)
        run = import_runs.extract(
            ottumwa_admin,
            {
                "target": import_runs.TARGET_ASSETS_DEVICES,
                "source_kind": "file",
                "file_name": "devices-201.csv",
                "content": _devices_file(ROWS),
                "session_ref": "sess_8102",
            },
        )
        import_runs.transform(
            ottumwa_admin, run["id"], {"mapping": run["detected_mapping"], "row_handling": ALL_OFF}
        )
        import_runs.validate(ottumwa_admin, run["id"])
        before = asset_models.Asset.objects.count()
        with _CapturedDispatch():
            answer = import_runs.load(
                ottumwa_admin, run["id"], {"write_mode": "insert", "approved": True}
            )
        assert answer["deferred"] is True, "the real 200-row bar must defer this load"
        core_jobs.run_pending(answer["job_id"])
        assert asset_models.Asset.objects.count() - before == ROWS


def test_def_ast_8102_a_non_rule_fault_on_one_row_rejects_that_row_only(
    ottumwa, ottumwa_admin, monkeypatch
):
    """Step 3: an unforeseen exception on ONE row rejects that row, with a
    plain reason, and every other row still loads (savepoint per row)."""
    from apps.assets import services as asset_services

    original = asset_services._create_asset_for_import

    def _explode_on_second(actor, data):
        if data.get("external_ref") == "JOB-0001":
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-AST-032")
        return original(actor, data)

    with tenant_ctx(ottumwa):
        _estate(ottumwa_admin, count=1)
        run = import_runs.extract(
            ottumwa_admin,
            {
                "target": import_runs.TARGET_ASSETS_DEVICES,
                "source_kind": "file",
                "file_name": "devices-3.csv",
                "content": _devices_file(3),
                "session_ref": "sess_8102b",
            },
        )
        import_runs.transform(
            ottumwa_admin, run["id"], {"mapping": run["detected_mapping"], "row_handling": ALL_OFF}
        )
        import_runs.validate(ottumwa_admin, run["id"])
        monkeypatch.setattr(asset_services, "_create_asset_for_import", _explode_on_second)
        import_runs.load(ottumwa_admin, run["id"], {"write_mode": "insert", "approved": True})
        refs = set(asset_models.Asset.objects.values_list("external_ref", flat=True))
        assert {"JOB-0000", "JOB-0002"} <= refs
        assert "JOB-0001" not in refs
        from apps.metering import models as metering_models

        rejected = metering_models.ImportRunRow.objects.get(run_id=run["id"], row_no=2)
        assert rejected.outcome == "rejected"
        assert rejected.problem


def test_U13_250_carts_uploaded_by_the_worker_are_counted_on_their_units(ottumwa, ottumwa_admin):
    """Plan U13 — 250 devices, over the 200-row bar so the WORKER loads them,
    50 carts on each of five units; the bill's count for trash on every unit
    is 50. Run on PostgreSQL 16 as well as the default suite (law 14)."""
    from apps.assets import selectors as asset_selectors
    from apps.metering import seams as metering_seams

    with tenant_ctx(ottumwa):
        units = [unit for _premises, unit in _estate(ottumwa_admin, count=5)]
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(["Device type", "External reference", "Service", "Size", "Unit"])
        # ⚠ BY NUMBER, NEVER BY LABEL (`DEF-AST-9265`). `_estate` labels its
        # units `Unit 0`…`Unit 4`, and with the sample utility seeded
        # (`JOBS_EAGER=true`, the PostgreSQL run) other units carry `Unit 1`…
        # too, so a label refuses as ambiguous and this case tested the unit
        # resolver instead of the worker's count. Passed on SQLite only.
        for n in range(250):
            writer.writerow(
                ["container_cart", f"U13-{n:03d}", "trash", "CART-64", units[n % 5]["unit_no"]]
            )
        run = import_runs.extract(
            ottumwa_admin,
            {
                "target": import_runs.TARGET_ASSETS_DEVICES,
                "source_kind": "file",
                "file_name": "carts-250.csv",
                "content": buffer.getvalue(),
                "session_ref": "sess_u13",
            },
        )
        import_runs.transform(
            ottumwa_admin, run["id"], {"mapping": run["detected_mapping"], "row_handling": ALL_OFF}
        )
        import_runs.validate(ottumwa_admin, run["id"])
        with _CapturedDispatch():
            answer = import_runs.load(
                ottumwa_admin, run["id"], {"write_mode": "insert", "approved": True}
            )
        assert answer["deferred"] is True
        core_jobs.run_pending(answer["job_id"])
    # `run_pending` leaves the tenant context it entered for the job; re-enter.
    with tenant_ctx(ottumwa):
        today = metering_seams.tenant_today()
        counts = [
            asset_selectors.billable_asset_count(unit["id"], "trash", today) for unit in units
        ]
        assert counts == [50, 50, 50, 50, 50]
