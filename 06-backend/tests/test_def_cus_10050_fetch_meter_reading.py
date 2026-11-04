"""DEF-CUS-10050 — `POST /integrations/meter-reading/fetch`, one meter's reading.

PO ruling 2026-10-11, verbatim: *"this si correct 0 fix it"*. The four
results are `meter_reading.fetch`'s docstring; each case below is one of them,
asked through the real view the screen presses.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.integrations import meter_reading
from apps.integrations import api as integrations_api
from apps.integrations import models as int_models
from apps.integrations import services as integration_services
from core.permissions import BILLING_CLERK
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

NEPTUNE = "meters_neptune360"


def _connect(tenant, actor, *, status=None, enabled=True):
    with tenant_ctx(tenant):
        row = integration_services.connect(
            actor=actor,
            tenant_id=tenant.id,
            provider_key=NEPTUNE,
            environment=int_models.ENVIRONMENT_PRODUCTION,
            config={"site_id": "BRAZOS-01"},
        )
        if status is not None or not enabled:
            int_models.IntegrationConnection.objects.filter(pk=row.pk).update(
                status=status or row.status, enabled=enabled
            )
        return row


def _fetch(tenant, actor, **body):
    return api_call(
        integrations_api.meter_reading_fetch,
        "post",
        f"/api/{tenant.subdomain}/integrations/meter-reading/fetch",
        user=actor.user,
        role=BILLING_CLERK,
        tenant=tenant,
        data=body,
    )


class _Stub:
    def __init__(self, answer=None, boom=False):
        self.answer = answer
        self.boom = boom
        self.asked: list[tuple[str, date | None]] = []

    def latest(self, connection, *, meter_no, as_of):
        self.asked.append((meter_no, as_of))
        if self.boom:
            raise RuntimeError("head-end down")
        return self.answer


@pytest.fixture
def stub(monkeypatch):
    def _bind(**kwargs):
        client = _Stub(**kwargs)
        monkeypatch.setitem(meter_reading.READING_CLIENTS, NEPTUNE, client)
        return client

    return _bind


def test_no_meter_head_end_is_not_connected_and_dials_nothing(brazos, dana, stub):
    client = stub(answer={"value": "1", "unit": "kgal", "read_on": "2026-10-11"})
    answer = _fetch(brazos, dana, meter_no="W-5023")
    assert answer.status_code == 200, answer.data
    assert answer.data == {
        "result": "not_connected",
        "reading": None,
        "message_key": meter_reading.KEY_NOT_CONNECTED,
    }
    assert client.asked == []


def test_a_switched_off_head_end_is_not_connected(brazos, dana, stub):
    _connect(brazos, dana, enabled=False)
    client = stub(answer={"value": "1", "unit": "kgal", "read_on": "2026-10-11"})
    assert _fetch(brazos, dana, meter_no="W-5023").data["result"] == "not_connected"
    assert client.asked == []


def test_another_utilitys_head_end_does_not_connect_this_one(brazos, lonestar, dana, erin, stub):
    _connect(lonestar, erin)
    stub(answer={"value": "1", "unit": "kgal", "read_on": "2026-10-11"})
    assert _fetch(brazos, dana, meter_no="W-5023").data["result"] == "not_connected"


def test_connected_with_no_client_bound_is_unavailable_never_a_made_up_reading(brazos, dana):
    """PO 2026-10-11: the no-client case NAMES the provider — *"Neptune 360
    connected. No reading fetched."* — rather than *"could not give a reading"*."""
    _connect(brazos, dana)
    answer = _fetch(brazos, dana, meter_no="W-5023")
    assert answer.data["result"] == "unavailable"
    assert answer.data["reading"] is None
    assert answer.data["message_key"] == meter_reading.KEY_CONNECTED_NO_READ
    assert answer.data["params"]["provider"]
    assert answer.data["params"]["provider"] != NEPTUNE  # a person's name, never the key


def test_fetched_carries_value_unit_and_date(brazos, dana, stub):
    _connect(brazos, dana)
    client = stub(answer={"value": "3004", "unit": "kgal", "read_on": "2026-10-11"})
    answer = _fetch(brazos, dana, meter_no=" W-5023 ")
    assert answer.status_code == 200, answer.data
    assert answer.data == {
        "result": "fetched",
        "reading": {"meter_no": "W-5023", "value": "3004", "unit": "kgal", "read_on": "2026-10-11"},
        "message_key": None,
    }
    assert client.asked == [("W-5023", None)]


def test_as_of_is_passed_on_and_a_later_reading_is_no_reading(brazos, dana, stub):
    _connect(brazos, dana)
    client = stub(answer={"value": "3004", "unit": "kgal", "read_on": "2026-10-11"})
    answer = _fetch(brazos, dana, meter_no="W-5023", as_of="2026-10-01")
    assert client.asked == [("W-5023", date(2026, 10, 1))]
    assert answer.data["result"] == "no_reading"
    assert answer.data["reading"] is None


def test_the_head_end_holding_nothing_is_no_reading(brazos, dana, stub):
    _connect(brazos, dana)
    stub(answer=None)
    answer = _fetch(brazos, dana, meter_no="W-5023")
    assert answer.data == {
        "result": "no_reading",
        "reading": None,
        "message_key": meter_reading.KEY_NO_READING,
    }


def test_a_reading_with_no_unit_is_unavailable_hard_rule_3(brazos, dana, stub):
    _connect(brazos, dana)
    stub(answer={"value": "3004", "unit": "", "read_on": "2026-10-11"})
    assert _fetch(brazos, dana, meter_no="W-5023").data["result"] == "unavailable"


def test_a_head_end_that_raises_or_last_failed_its_test_is_unavailable(brazos, dana, stub):
    _connect(brazos, dana)
    stub(boom=True)
    assert _fetch(brazos, dana, meter_no="W-5023").data["result"] == "unavailable"
    with tenant_ctx(brazos):
        int_models.IntegrationConnection.objects.filter(provider_key=NEPTUNE).update(
            status=int_models.STATUS_NOT_WORKING
        )
    stub(answer={"value": "3004", "unit": "kgal", "read_on": "2026-10-11"})
    assert _fetch(brazos, dana, meter_no="W-5023").data["result"] == "unavailable"


def test_no_meter_number_or_a_bad_date_is_refused_in_words(brazos, dana):
    missing = _fetch(brazos, dana, meter_no="  ")
    assert missing.status_code == 422, missing.data
    assert meter_reading.KEY_METER_REQUIRED in str(missing.data)
    bad = _fetch(brazos, dana, meter_no="W-5023", as_of="11-Oct-26")
    assert bad.status_code == 422, bad.data
    assert meter_reading.KEY_BAD_DATE in str(bad.data)
