# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-FLD-10582 (beta MQ-015) — the meter and point on the job card,
#           on real PostgreSQL
# Rules:    CLAUDE.md hard rule 1 (RLS FORCE, tenant scope) · hard rule 8 +
#           BR-MET-1162 · BR-WRK-006
# Tests:    this file — skipped on SQLite BY DESIGN
# ───────────────────────────────────────────────────────
"""The card's meter is read across a module seam (`assets_seam.job_meter`), so
the one question SQLite cannot answer is whether that read stays inside the
tenant when the app's own filter is not what stands in the way. Under the
NON-SUPERUSER probe role (the connected role may bypass row security, and a
green under it would prove nothing), another utility's meter is invisible to
the seam and to a bare query alike."""

from __future__ import annotations

import pytest

from apps.work.seams import assets_seam
from tests import test_def_fld_10582_job_card_meter_point as cases
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    RlsProbe,
    live_tenant_context,
    requires_postgres,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin · marcus
from tests.test_us_met_helpers import make_asset
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]


def test_the_card_names_its_meter_on_postgres(brazos, dana):
    cases.test_the_card_names_the_jobs_own_asset(brazos, dana)


def test_the_unit_fallback_holds_on_postgres(brazos, dana):
    cases.test_a_job_on_a_unit_names_the_one_in_service_meter_there(brazos, dana)


def test_the_units_point_wins_on_postgres(brazos, dana):
    cases.test_a_units_own_point_wins_and_says_so(brazos, dana)


def test_the_premises_point_holds_on_postgres(brazos, dana):
    cases.test_the_premises_point_is_on_the_card_and_says_so(brazos, dana)


def test_the_seam_read_never_crosses_a_tenant_under_rls(rls_probe_role, brazos, lonestar, dana, erin):
    with tenant_ctx(brazos):
        mine = make_asset(dana, asset_no="W-5000", service="water", unit="gal", model="Neptune T-10")
    probe = RlsProbe(rls_probe_role)
    probe.assert_is_a_real_proof()

    # The owner, as the non-superuser role: the seam answers.
    with live_tenant_context(brazos.id), probe._as_role():
        assert assets_seam.job_meter(mine["id"])["asset_no"] == "W-5000"

    # Another utility, as the non-superuser role: the seam answers nothing, and
    # neither does a bare SELECT with no tenant filter — RLS is what refuses.
    with live_tenant_context(lonestar.id), probe._as_role() as cursor:
        assert assets_seam.job_meter(mine["id"]) is None
        cursor.execute("SELECT count(*) FROM assets WHERE id = %s", [mine["id"]])
        assert cursor.fetchone()[0] == 0
