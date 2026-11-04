# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-010 (the S52 staged bulk import) — RETIRED by CR-028
#           AST-W3-T5 (BR-AST-046, PO 2026-08-22: the import modal converts to
#           the workflow on every tab; BR-MET-096: one runner, never a second
#           pipeline). The behaviors TC-1..TC-11 asserted now live on the
#           runner's three assets targets — tests/test_cr028_import_targets.py.
# Rules:    BR-AST-046 (tab-named workflow imports) · BR-MET-096 (one runner) ·
#           CR-026 ("existing single-shot import paths migrate onto the
#           runner") · hard-won law 4's instinct (committed batches stay
#           readable — the tables are kept, only the write verbs refuse)
# Journeys: J20 step 1 now runs through WFL-01 (target assets_meters)
# ───────────────────────────────────────────────────────
"""US-AST-010's path is CLOSED — this file asserts the closure.

The staged `POST /assets/imports` + `/commit` pair was the FIFTH import shape
in the tree (models.py's own count). CR-028 moved the assets import onto the
one ETL runner, so the two write verbs now REFUSE with a catalog sentence that
points at it — a refusal, deliberately not a 404, because "bulk import is
gone" and "bulk import moved" are different products. The batch TABLES and
their read selector stay: a committed batch is tenant history.
"""

import pytest

from apps.assets import models, selectors, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def test_stage_import_refuses_and_points_at_the_runner(brazos, dana):
    """The upload verb refuses BY NAME — and stages NOTHING on the way out."""
    with tenant_ctx(brazos):
        before = models.AssetImportBatch.objects.count()
        with pytest.raises(errors.BizError) as caught:
            services.stage_import(dana, {"content": "asset #\nM-6001\n"})
        assert caught.value.message_key == "assets.import_moved_to_runner"
        assert caught.value.br_ref == "BR-AST-046"
        assert caught.value.params["targets"] == [
            "assets_meters",
            "assets_submeters",
            "assets_devices",
        ]
        assert models.AssetImportBatch.objects.count() == before
        assert models.Asset.objects.filter(tenant=brazos).count() == 0


def test_commit_import_refuses_the_same_way(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            services.commit_import(dana, "01a02a0c-0000-7000-8000-000000000000", {})
        assert caught.value.message_key == "assets.import_moved_to_runner"
        assert models.Asset.objects.filter(tenant=brazos).count() == 0


def test_an_old_committed_batch_stays_readable(brazos, dana):
    """The door is closed, not the room: history written before the
    retirement is still served by the read selector."""
    from django.utils import timezone

    with tenant_ctx(brazos):
        batch = models.AssetImportBatch.objects.create(
            tenant=brazos,
            filename="bbu-meters-2026.csv",
            row_count=3,
            valid_count=2,
            committed_at=timezone.now(),
        )
        models.AssetImportRow.objects.create(
            tenant=brazos, batch=batch, row_no=1, raw={"source": {}, "resolved": {}}
        )
        read = selectors.import_batch(batch.id)
    assert read["committed"] is True
    assert read["preview"]["rows"] == 3
    assert len(read["rows"]) == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-028/B16@2026-08-22 §4.7b ("no second pipeline survives") · AST-W3-T5
# generated: 2026-08-22 by the CR-028 AST-W3 lane (REWRITE — the TC-1..TC-11 behaviors this file used to assert are the runner's now, asserted in tests/test_cr028_import_targets.py)
# checklist: A✔ B✔ C✔ D=n/a(service-level; the API routes call these verbs directly) E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_us_ast_010_import.py
# exceptions: the refusal is asserted at the SERVICE (the API views are one-line pass-throughs already covered by the error-envelope suite) · the readable-batch case writes its fixture rows directly — the write verbs that used to produce them are the very thing this file proves refuse
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
