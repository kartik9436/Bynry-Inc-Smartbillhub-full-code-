# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-FLD-10603 (MQ-036) — *Raise work* from the phone's Home sent an
#           order that stood on nothing; `raise_from_field` refused it
#           (`work.order.anchor_required`) and nothing reached Work → Orders
# Rules:    BR-WRK-006 (an order stands on an anchor) · BR-FLD-00024 (R24 — the
#           number is the server's) · BR-MET-1202 (the phone's position at
#           capture) · hard rule 8 (the address lives on the premises)
# Tests:    this file · field-app/tests/sync/raiseShapes.test.ts (the handset)
# ───────────────────────────────────────────────────────
"""The two raise bodies the phone sends, through the real raise door.

`field-app/tests/sync/support/raiseShapes.json` holds the phone's exact bodies
for `POST /work/mobile/orders` — raised from Home with a picked place, and
carried from a job. `field-app/tests/sync/raiseShapes.test.ts` asserts the
phone's own send path still produces exactly those, and this file POSTs exactly
those to the real door. Neither side can move without the other going red —
which is the gap DEF-FLD-10603 fell through: the phone only ever raised from a
job, and the server's tests wrote their own bodies."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.work import api as _work_api  # noqa: F401 — loads first; field_orders_api is imported by it
from apps.work import field_orders_api
from apps.work.field_order_models import WorkFieldRaise

from tests.test_cr187_gaps import _call, _token
from tests.test_cr187_order_helpers import job, order, template
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SHAPES_FILE = (
    Path(__file__).resolve().parents[2]
    / "field-app" / "tests" / "sync" / "support" / "raiseShapes.json"
)
SHAPES = json.loads(SHAPES_FILE.read_text(encoding="utf-8"))


def _fill(value, specifics):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            filled = _fill(v, specifics)
            if filled is not None:
                out[k] = filled
        return out
    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
        return specifics[value[1:-1]]
    return value


def _shape(name, **specifics):
    """The phone's body, with only its placeholders filled in. A placeholder
    filled with None is left out, as the phone leaves out a null."""
    base = {"captured_at": "2026-03-15T16:05:00.000Z", "fix_at": "2026-03-15T16:04:00.000Z"}
    return _fill(SHAPES[name], {**base, **specifics})


def _post(tenant, tech, body):
    answer = _call(
        field_orders_api.mobile_orders, tenant, tech, {**body, "capture_token": _token(tech)}
    )
    return answer


def test_a_raise_from_home_with_a_picked_place_is_accepted_and_numbered(brazos, dana):
    """MQ-036 — the body the phone sends from Home, with the premises picked
    on *Where*, raises an order on that premises: numbered by the server,
    pending for the office, the phone's position kept."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        premises_id = order(oid).premises_id
        body = _shape(
            "fromHome",
            key="home-raise-1",
            template_id=str(tid),
            template_version="2",
            premises_id=str(premises_id),
        )
        answer = _post(brazos, tech, body)
        assert answer.status_code == 201, answer.data
        new = order(answer.data["order_id"])
        row = WorkFieldRaise.objects.get(key="home-raise-1")
    assert answer.data["order_no"].startswith("WO-")
    assert answer.data["status"] == "pending" and answer.data["carried_from"] is None
    assert new.premises_id == premises_id
    assert answer.data["premise"] is not None
    assert row.note == "Hydrant leaking at the kerb" and row.urgency == "normal"
    assert answer.data["position"]["lat"] == "30.261200"


def test_the_same_body_with_no_place_is_refused_by_name(brazos, dana):
    """The defect itself: no `premises_id` — what the phone sent from Home
    before the *Where* card — is refused with the key FF-50 renders."""
    with tenant_ctx(brazos):
        _oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        body = _shape(
            "fromHome", key="home-raise-2", template_id=str(tid), template_version="2", premises_id=None
        )
        answer = _post(brazos, tech, body)
    # A 4xx: the phone keeps it as REFUSED and shows the key's words (receipts.ts).
    assert answer.status_code == 422, answer.data
    assert answer.data["message_key"] == "work.order.anchor_required"


def test_a_raise_carried_from_a_job_is_unchanged(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Leak investigation")
        carried = order(oid)
        body = _shape(
            "fromJob",
            key="job-raise-1",
            template_id=str(tid),
            template_version="2",
            carried_from=str(oid),
            premises_id=str(carried.premises_id) if carried.premises_id else None,
            account_id=str(carried.account_id) if carried.account_id else None,
            asset_id=str(carried.asset_id) if carried.asset_id else None,
        )
        answer = _post(brazos, tech, body)
        assert answer.status_code == 201, answer.data
        new = order(answer.data["order_id"])
    assert answer.data["carried_from"]["order_no"] == carried.order_no
    assert new.premises_id == carried.premises_id and answer.data["urgency"] == "same_day"
