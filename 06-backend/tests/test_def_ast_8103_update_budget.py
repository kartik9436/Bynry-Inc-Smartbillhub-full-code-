# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-AST-8103 — updating 400–500 assets by upload took ~14 s for 500
#          (≈19 SQL statements per row) and, with JOBS_EAGER=true on the
#          deployment, ran inside the request, so a bigger file met the 60 s
#          gunicorn timeout.
# Ruling:  PO GO 2026-09-30, step 5: a test that fails when statements-per-row
#          for an asset update exceeds the new budget (CaptureQueriesContext).
# Tests:   this file; the PostgreSQL timing is
#          10-scripts/def_ast_8103_upload_cost.py
# ───────────────────────────────────────────────────────
"""Statements per UPDATED row, measured as a SLOPE: the same re-upload at two
sizes, so the run's fixed cost (the lock, the index, the receipt, the rollback
point) cancels and only what each extra row costs is left.

⚠ **A SLOPE AND NOT A TOTAL, ON PURPOSE.** A budget on the total passes a
per-row regression on a small file and fails a harmless fixed cost on a large
one; the slope answers the only question that grows with the file.
"""

from __future__ import annotations

import csv
import io

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.assets import models as asset_models
from apps.metering import import_runs

from tests.test_def962_def963_assets_template import (  # noqa: F401 — fixtures
    ALL_OFF,
    _estate,
    ottumwa,
    ottumwa_admin,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: Statements an UPDATED asset row may cost at the load — the budget the PO's
#: step 1 asked for (~5 real statements). MEASURED by this test's slope:
#: **22.0/row before** (branch base `70c3cc7de` + the U7 override, through
#: `update_asset.__wrapped__`) → **7.0/row after**: the savepoint pair the
#: runner needs (law 14), one asset read, one asset write, one audit row, the
#: reads count BR-AST-012 asks when a 💲 field moved, and the import row's
#: own save. Held at the measured figure so any regression goes red.
UPDATE_STATEMENTS_PER_ROW = 7


def _file(rows: list[dict[str, str]]) -> str:
    header = ["Meter number (existing only)", "External reference", "Service", "Multiplier",
              "Manufacturer"]  # fmt: skip
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([row.get(h, "") for h in header])
    return buffer.getvalue()


def _run(actor, content, write_mode):
    run = import_runs.extract(
        actor,
        {
            "target": import_runs.TARGET_ASSETS_METERS,
            "source_kind": "file",
            "file_name": "meters.csv",
            "content": content,
            "session_ref": "sess_8103",
            "write_mode": write_mode,
        },
    )
    import_runs.transform(
        actor, run["id"], {"mapping": run["detected_mapping"], "row_handling": ALL_OFF}
    )
    import_runs.validate(actor, run["id"], write_mode)
    return run["id"]


def _update_cost(actor, prefix: str, count: int) -> int:
    """Create `count` meters, then re-upload them changing two cells; return
    the statements the UPDATE load issued."""
    rows = [{"External reference": f"{prefix}-{n}", "Service": "water", "Multiplier": "1"}
            for n in range(count)]  # fmt: skip
    run_id = _run(actor, _file(rows), "insert")
    import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
    numbers = dict(
        asset_models.Asset.objects.filter(external_ref__startswith=f"{prefix}-").values_list(
            "external_ref", "asset_no"
        )
    )
    assert len(numbers) == count
    updates = [
        {"Meter number (existing only)": numbers[f"{prefix}-{n}"],
         "External reference": f"{prefix}-{n}", "Service": "water",
         "Multiplier": "2", "Manufacturer": "Acme"}
        for n in range(count)
    ]  # fmt: skip
    run_id = _run(actor, _file(updates), "upsert")
    with CaptureQueriesContext(connection) as captured:
        import_runs.load(actor, run_id, {"write_mode": "upsert", "approved": True})
    assert asset_models.Asset.objects.filter(
        external_ref__startswith=f"{prefix}-", manufacturer="Acme"
    ).count() == count
    return len(captured.captured_queries)


def test_def_ast_8103_an_updated_asset_row_costs_at_most_the_budget(ottumwa, ottumwa_admin):
    with tenant_ctx(ottumwa):
        _estate(ottumwa_admin, count=1)
        small = _update_cost(ottumwa_admin, "S", 5)
        large = _update_cost(ottumwa_admin, "L", 15)
    per_row = (large - small) / 10
    print(f"DEF-AST-8103: {small} statements at 5 rows, {large} at 15 → {per_row:.1f}/row")
    assert per_row <= UPDATE_STATEMENTS_PER_ROW, (
        f"an updated asset row costs {per_row:.1f} statements; the budget is "
        f"{UPDATE_STATEMENTS_PER_ROW} (DEF-AST-8103 — 500 rows must finish well inside 60 s)"
    )
