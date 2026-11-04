# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-004 (S16 bulk create — premises CSV · unit pattern
#           generator · units CSV with asset columns)
# Rules:    BR-MET-004 (staged, every row validated pre-commit, DUPE callout) ·
#           BR-MET-005 (pattern ≤3,000/run) · BR-MET-031 ({seq}/{floor} tokens,
#           BOTH paths) · BR-MET-038 (10 MB · 10,000-row cap · skip-errors ON ·
#           "N created · N failed" ALWAYS shown) · BR-MET-039 + BR-AST-028
#           (asset columns reference OR create inline — one registry) ·
#           BR-MET-002 (label unique per premise) · BR-MET-048 (batch audit)
# Journeys: J20 step 1 (migration order: premises → units+plans → assets) —
#           the same staged/per-row-error/summary discipline (BR-CUS-051)
# Note:     The §4 file sizes (184/248/412 rows) are scaled down here; the
#           RULES under test (counts, duplicate handling, caps, summaries) are
#           asserted exactly. The staged set is NOT persisted — US-MET-004 §5
#           says "no persistence in v1" (E2 vs 11b §2.5, reported).
# ───────────────────────────────────────────────────────
"""US-MET-004 — staged bulk creation of premises and units."""

import pytest

from apps.assets import models as asset_models
from apps.metering import models, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_asset, make_premises, tenant_ctx

pytestmark = pytest.mark.django_db

PREMISES_CSV = """address,city,state,zip,type,units,owner,services
1408 Bluestem Ln,Katy,TX,77494,Single-family,1,Whitfield Rentals LLC,electric;water
2201 Cane Island Pkwy,Katy,TX,77494,Single-family,1,"Chen, David",electric
500 Mason Rd Plaza,Katy,TX,77494,Commercial building,18,Mason Rd Holdings,electric;water
2200 Riverbend Ct,Katy,TX,77494,Apartment complex,120,Riverbend Apts LP,electric
77 Gulf Fwy Industrial,Katy,TX,77494,Commercial building,1,Northwind Mfg.,electric
"""


def units_csv(premise_no: str) -> str:
    return (
        "premise_id,unit_label,type,services,asset #,serial,asset type\n"
        f"{premise_no},Apt 101,residential,electric,M-8001,,\n"
        f"{premise_no},Apt 102,residential,electric,,SN-77021,meter\n"
        f"{premise_no},Apt 103,residential,electric,,,\n"
        "P-99999,Apt 104,residential,electric,,,\n"
    )


def test_us_met_004_tc1__premises_csv_stages_then_commits_with_a_summary(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        payload = {
            "kind": "premises_csv",
            "filename": "brazosbend_premises_2026.csv",
            "content": PREMISES_CSV,
        }
        staged = services.stage_import(dana, payload)
        assert staged["preview"] == {
            "rows": 5,
            "valid": 5,
            "warnings": 0,
            "errors": 0,
            "duplicates": 0,
        }
        assert models.Premises.objects.filter(tenant=brazos).count() == 0  # BR-MET-004: staged only
        result = services.commit_import(dana, payload)
        assert models.Premises.objects.filter(tenant=brazos).count() == 5
    # BR-MET-038: the summary is rendered after EVERY create.
    assert result["summary"] == {"created": 5, "failed": 0}
    assert "premises.bulk_created" in [r["action"] for r in audit_rows]  # BR-MET-048


def test_us_met_004_tc7__re_upload_reports_every_row_as_a_duplicate(brazos, dana):
    payload = {"kind": "premises_csv", "filename": "again.csv", "content": PREMISES_CSV}
    with tenant_ctx(brazos):
        services.commit_import(dana, payload)
        staged = services.stage_import(dana, payload)
        assert staged["preview"]["duplicates"] == 5  # BR-MET-004 DUPE callout
        second = services.commit_import(dana, payload)
        assert models.Premises.objects.filter(tenant=brazos).count() == 5  # no double-create
    assert second["summary"] == {"created": 0, "failed": 5}
    merged = dict(payload, options={"merge_duplicates": True})
    with tenant_ctx(brazos):
        third = services.commit_import(dana, merged)
        assert models.Premises.objects.filter(tenant=brazos).count() == 10
    assert third["summary"]["created"] == 5


def test_us_met_004_tc2__pattern_generator_tokens_and_labels(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="2200 Riverbend Ct")
        payload = {
            "kind": "units_pattern",
            "pattern": {
                "premises_id": premise["id"],
                "floors": 6,
                "units_per_floor": 20,
                "label_pattern": "Apt {floor}{seq:00}",
                "unit_type": "residential_submetered",
                "services": ["electric"],
            },
        }
        staged = services.stage_import(dana, payload)
        assert staged["preview"]["total"] == 120  # BR-MET-005 floors × per-floor
        assert staged["rows"][0]["data"]["label"] == "Apt 101"
        assert staged["rows"][-1]["data"]["label"] == "Apt 620"
        result = services.commit_import(dana, payload)
        assert models.Unit.objects.filter(tenant=brazos, premises_id=premise["id"]).count() == 120
    assert result["summary"] == {"created": 120, "failed": 0}


def test_us_met_004_tc5__pattern_over_the_3000_cap_generates_nothing(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        with pytest.raises(errors.BizError) as caught:
            services.stage_import(
                dana,
                {
                    "kind": "units_pattern",
                    "pattern": {
                        "premises_id": premise["id"],
                        "floors": 6,
                        "units_per_floor": 600,
                        "label_pattern": "Apt {floor}{seq:00}",
                    },
                },
            )
        assert models.Unit.objects.filter(tenant=brazos).count() == 0
    assert caught.value.code == errors.BIZ_CAP and caught.value.br_ref == "BR-MET-038"
    assert caught.value.params["max_units"] == 3000


def test_us_met_004_tc11__unknown_pattern_token_is_named(brazos, dana):
    """BR-MET-031: the CONFIRMED grammar is {seq}/{floor} — nothing else."""
    with tenant_ctx(brazos):
        premise = make_premises(dana)
        with pytest.raises(errors.ValidationError) as caught:
            services.stage_import(
                dana,
                {
                    "kind": "units_pattern",
                    "pattern": {
                        "premises_id": premise["id"],
                        "floors": 1,
                        "units_per_floor": 2,
                        "label_pattern": "Apt {building}{seq}",
                    },
                },
            )
    assert caught.value.params["token"] == "{building}"


def test_us_met_004_tc3__units_csv_references_and_creates_assets_in_one_registry(brazos, dana):
    """BR-MET-039 / BR-AST-028: an asset # references existing inventory, a
    serial + type creates a new asset inline — both in the ONE registry."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="2200 Riverbend Ct")
        make_asset(dana, asset_no="M-8001", service="electric", unit="kWh")
        payload = {
            "kind": "units_csv",
            "filename": "riverbend_units.csv",
            "content": units_csv(premise["premise_no"]),
        }
        staged = services.stage_import(dana, payload)
        assert staged["preview"]["rows"] == 4 and staged["preview"]["errors"] == 1
        result = services.commit_import(dana, payload)
        assets = set(
            asset_models.Asset.objects.filter(tenant=brazos).values_list("asset_no", flat=True)
        )
        assigned = asset_models.AssetAssignment.objects.filter(tenant=brazos).count()
    assert result["summary"] == {"created": 3, "failed": 1}
    assert "M-8001" in assets and len(assets) == 2  # one referenced + one created inline
    assert assigned == 2


def test_us_met_004_tc4__unknown_premise_errors_that_row_only(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="2200 Riverbend Ct")
        make_asset(dana, asset_no="M-8001", service="electric", unit="kWh")
        payload = {"kind": "units_csv", "content": units_csv(premise["premise_no"])}
        staged = services.stage_import(dana, payload)
        bad = [r for r in staged["rows"] if r["errors"]]
        assert len(bad) == 1  # only the P-99999 row
        assert [e["code"] for e in bad[0]["errors"]] == ["premise_must_exist"]
        result = services.commit_import(dana, payload)  # skip-errors ON by default
        assert models.Unit.objects.filter(tenant=brazos).count() == 3
    assert result["errors"][0]["reasons"][0]["value"] == "P-99999"


def test_us_met_004_tc12__skip_errors_off_is_all_or_nothing(brazos, dana):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="2200 Riverbend Ct")
        payload = {
            "kind": "units_csv",
            "content": units_csv(premise["premise_no"]),
            "options": {"skip_errors": False},
        }
        with pytest.raises(errors.BizError) as caught:
            services.commit_import(dana, payload)
        assert models.Unit.objects.filter(tenant=brazos).count() == 0
    assert caught.value.code == errors.BIZ_COMPLETENESS and caught.value.br_ref == "BR-MET-004"


def test_us_met_004_tc6__oversize_file_is_rejected(brazos, dana):
    header = "address,city,state,zip\n"
    row = "1 Big Row Ln,Katy,TX,77494\n"
    content = header + row * (((10 * 1024 * 1024) // len(row)) + 10)  # just over 10 MB
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            services.stage_import(dana, {"kind": "premises_csv", "content": content})
    assert caught.value.code == errors.BIZ_CAP
    assert caught.value.message_key == "metering.import.file_too_large"


def test_us_met_004_tc9__row_cap_rejects_at_upload(brazos, dana):
    content = "address\n" + "".join(f"{n} Cap Ln\n" for n in range(10_001))
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            services.stage_import(dana, {"kind": "premises_csv", "content": content})
        assert models.Premises.objects.filter(tenant=brazos).count() == 0  # nothing staged
    assert caught.value.params["max_rows"] == 10_000 and caught.value.br_ref == "BR-MET-038"


@pytest.mark.isolation
def test_us_met_004_tc8__isolation_cross_tenant_premise_never_resolves(
    brazos, dana, lonestar, erin
):
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="500 Mason Rd Plaza")
    with tenant_ctx(lonestar):
        staged = services.stage_import(
            erin, {"kind": "units_csv", "content": units_csv(premise["premise_no"])}
        )
        assert all(r["errors"] for r in staged["rows"])
        # Every row naming a Brazos Bend premise errors "premise must exist" —
        # cross-tenant premise ids never resolve (US-MET-004 TC-8).
        assert all(
            any(e["code"] == "premise_must_exist" for e in r["errors"]) for r in staged["rows"]
        )
