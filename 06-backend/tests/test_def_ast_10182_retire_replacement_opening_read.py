# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-AST-10182 — Assets → Retire with a replacement meter took no
#           opening reading for the NEW meter. PO ruling 2026-10-17 (decision
#           log "WHERE A USER ENTERS A METER READING", gap 2): opening reading
#           + read date for the new meter, and Fetch.
# Rules:    BR-AST-021/022 (one transaction) · AST-B-14 (the opening read is
#           metering's `capture_opening_read`) · hard rule 1 (tenant scoping)
#           · hard rule 3 (the read carries the meter's own unit) · rule 7
# ───────────────────────────────────────────────────────
"""The retire records the replacement's opening reading, with its date.

RED FIRST: before `_capture_replacement_opening_read` the retire ignored
`replacement_opening_read` — the new meter had NO reading after the retire
(`assert reads == 1` failed with `0 == 1`) and none of the refusals fired.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.assets import models as asset_models
from apps.assets import services as asset_services
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import a_meter, at, commit_read, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _spare(actor, asset_no="M-9101", service="electric", uom="kWh"):
    """An inventory meter — what the retire wizard's replacement picker offers."""
    return asset_services.create_asset(
        actor, {"type": "meter", "asset_no": asset_no, "service": service, "unit": uom}
    )


def _reads(asset_id):
    from apps.metering import models

    return list(models.MeterRead.objects.filter(asset_id=asset_id).order_by("read_at"))


def test_retire_with_replacement_records_the_new_meters_opening_read_on_its_date(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        old = a_meter(dana, asset_no="M-7101")
        commit_read(dana, old["id"], day="2026-08-03", value="42864", consumption="684")
        spare = _spare(dana)
        result = asset_services.retire_asset(
            dana,
            old["id"],
            {
                "reason": "failed",
                "retire_date": "2026-09-01",
                "final_read_value": "43566",
                "replaced_by": "M-9101",
                "replacement_opening_read": "12",
                "replacement_opening_read_date": "2026-08-31",
            },
        )
        assert result["status"] == "retired"
        new_reads = _reads(spare["id"])
        assert len(new_reads) == 1
        opening = new_reads[0]
        assert opening.current_value == Decimal("12.000000")
        assert opening.read_at == at("2026-08-31")
        assert opening.unit == "kWh"  # hard rule 3: the NEW meter's own unit
        assert opening.source == "manual" and opening.source_detail == "opening_read"
        # The old meter's final read is on the old meter, on the retire date.
        old_final = [r for r in _reads(old["id"]) if r.source_detail == "final_read"]
        assert len(old_final) == 1 and old_final[0].read_at == at("2026-09-01")
    actions = [r["action"] for r in audit_rows]
    assert "asset.replacement_opening_read_captured" in actions
    assert "read.opening_read_captured" in actions


def test_the_opening_read_date_defaults_to_the_retire_date(brazos, dana):
    with tenant_ctx(brazos):
        old = a_meter(dana, asset_no="M-7102")
        spare = _spare(dana, asset_no="M-9102")
        asset_services.retire_asset(
            dana,
            old["id"],
            {
                "reason": "failed",
                "retire_date": "2026-09-01",
                "replaced_by": "M-9102",
                "replacement_opening_read": "0",
            },
        )
        assert [r.read_at for r in _reads(spare["id"])] == [at("2026-09-01")]


def test_a_blank_opening_read_records_nothing(brazos, dana):
    with tenant_ctx(brazos):
        old = a_meter(dana, asset_no="M-7103")
        spare = _spare(dana, asset_no="M-9103")
        asset_services.retire_asset(
            dana,
            old["id"],
            {"reason": "failed", "retire_date": "2026-09-01", "replaced_by": "M-9103",
             "replacement_opening_read": ""},
        )
        assert _reads(spare["id"]) == []


@pytest.mark.parametrize(
    "extra, key",
    [
        ({"replacement_opening_read_date": "2099-01-01"}, "assets.replacement_opening_read_future"),
        ({"replacement_opening_read_date": "31/08/2026"}, "assets.bad_date"),
    ],
)
def test_a_future_or_unreadable_date_refuses_and_nothing_retires(brazos, dana, extra, key):
    with tenant_ctx(brazos):
        old = a_meter(dana, asset_no="M-7104")
        spare = _spare(dana, asset_no="M-9104")
        with pytest.raises(errors.ValidationError) as caught:
            asset_services.retire_asset(
                dana,
                old["id"],
                {"reason": "failed", "retire_date": "2026-09-01", "replaced_by": "M-9104",
                 "replacement_opening_read": "5", **extra},
            )
        assert caught.value.field_errors[0]["message_key"] == key
        assert asset_models.Asset.objects.get(id=old["id"]).status.code != "retired"
        assert _reads(spare["id"]) == []


def test_a_future_dated_retire_still_refuses_a_defaulted_future_opening_read(brazos, dana):
    """The date defaults to the retire date — a forward-dated retire must name one."""
    future = (date.today() + timedelta(days=400)).isoformat()
    with tenant_ctx(brazos):
        old = a_meter(dana, asset_no="M-7105")
        _spare(dana, asset_no="M-9105")
        with pytest.raises(errors.ValidationError) as caught:
            asset_services.retire_asset(
                dana,
                old["id"],
                {"reason": "failed", "retire_date": future, "replaced_by": "M-9105",
                 "replacement_opening_read": "5"},
            )
        assert caught.value.field_errors[0]["message_key"] == "assets.replacement_opening_read_future"


def test_an_opening_read_without_a_replacement_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        old = a_meter(dana, asset_no="M-7106")
        with pytest.raises(errors.ValidationError) as caught:
            asset_services.retire_asset(
                dana,
                old["id"],
                {"reason": "failed", "retire_date": "2026-09-01", "replacement_opening_read": "5"},
            )
        assert (
            caught.value.field_errors[0]["message_key"]
            == "assets.replacement_opening_read_needs_replacement"
        )


def test_an_unreadable_value_refuses_the_whole_retire(brazos, dana):
    with tenant_ctx(brazos):
        old = a_meter(dana, asset_no="M-7107")
        spare = _spare(dana, asset_no="M-9107")
        with pytest.raises(errors.ValidationError):
            asset_services.retire_asset(
                dana,
                old["id"],
                {"reason": "failed", "retire_date": "2026-09-01", "replaced_by": "M-9107",
                 "replacement_opening_read": "twelve"},
            )
        assert asset_models.Asset.objects.get(id=old["id"]).status.code != "retired"
        assert _reads(spare["id"]) == []


def test_tenant_isolation_another_utilitys_meter_cannot_be_the_replacement(
    brazos, dana, lonestar, erin
):
    """Hard rule 1: a replacement named by another tenant's number is unknown here,
    and no reading lands on the other tenant's meter."""
    with tenant_ctx(lonestar):
        theirs = _spare(erin, asset_no="M-9108", service="water", uom="kgal")
    with tenant_ctx(brazos):
        old = a_meter(dana, asset_no="M-7108")
        with pytest.raises(errors.ValidationError) as caught:
            asset_services.retire_asset(
                dana,
                old["id"],
                {"reason": "failed", "retire_date": "2026-09-01", "replaced_by": "M-9108",
                 "replacement_opening_read": "5"},
            )
        assert caught.value.field_errors[0]["message_key"] == "assets.replacement_unknown"
    with tenant_ctx(lonestar):
        assert _reads(theirs["id"]) == []
