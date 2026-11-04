# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10657 — *Put service back on* (S148) refused its own
#           Confirm with "This step is not built yet", so no restoration could
#           be recorded from any screen.
# Ruling:   PO 2026-10-29, C1 verbatim *"Restore = Reconnect request"*; the
#           reading is the lane judgment in `12-governance/02-decision-log.md`
#           2026-10-29 *"C1 'Restore = Reconnect request': what it maps to"*.
# Rules:    BR-CUS-1097 (an owing account is reconnected; the record carries
#           owed / who / when) · BR-PAY-036 (restoration is an explicit staff
#           act — a closed field job never restores by itself) · BR-WRK-055 (the
#           state never waits for the job) · hard rule 1 (tenant scoping) ·
#           hard rule 7 (every step audited) · DEF-NOT-10649 (Service restored).
# ───────────────────────────────────────────────────────
"""The reconnect REQUEST and its COMPLETION, through the two doors S148 calls.

Every case here was run before the doors existed and failed there (red first,
hard-won law 7): `reconnect_read` had no `reconnect_request` and no
`reconnect_complete`, and `restore_service` recorded no figure at restoration.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7, habit 2): asserting the payload
alone. A door that answered 200 and moved nothing would pass that; so each case
reads the CASE ROW, the AUDIT ROW and the MESSAGE ROWS back.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnect_record, disconnects, reconnect_read
from apps.customers import services as customer_services
from apps.notifications import customer_events

from tests.test_def_not_10649_cut_restore_notices import (  # noqa: F401 — autouse fixture
    _cut,
    _fee_and_reads_at_the_boundary,
    _rows,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, erin, lonestar, marcus, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call
from tests.test_w7_disconnects import _owes

pytestmark = pytest.mark.django_db

REQUESTED_ON = "2026-08-28"
RESTORED_ON = "2026-08-29"
#: Brett Calloway's shape: still owing after a part payment.
STILL_OWED = D("804.50")


def _case_no(account_id):
    return disconnects.open_case_for(account_id).case_no


def _post(view, tenant, actor, ref, data, role="billing_clerk"):
    return api_call(view, "post", user=actor.user, role=role, tenant=tenant, data=data, ref=ref)


def _restored_messages(tenant, account_id):
    return _rows(
        tenant,
        account_id=account_id,
        template_code__in=(
            customer_events.TEMPLATE_SERVICE_RESTORED,
            customer_events.TEMPLATE_SERVICE_RESTORED_SMS,
        ),
    )


@pytest.fixture()
def raised(monkeypatch):
    """Work's answer, stubbed AT the customers seam — the template the
    utility's offer would pick, and what the raise was asked for."""
    asked: list = []
    monkeypatch.setattr(
        reconnect_read, "_reconnect_template_for", lambda _account, service: [f"tpl-{service}"]
    )

    def _raise(actor, *, flow_kind, flow_id, template_ids):
        asked.append((flow_kind, list(template_ids)))
        return {"raised": [{"order_no": "WO-9001"}]}

    monkeypatch.setattr(customer_services.seams, "raise_flow_work_orders", _raise)
    return asked


# ════════════════════════════════════════════════════════════════════════════
# 1 · CONFIRM ON A CUT CASE IS THE RECONNECT REQUEST
# ════════════════════════════════════════════════════════════════════════════
def test_confirm_on_a_cut_case_creates_the_reconnect_request_and_restores_nothing(
    brazos, marcus, monkeypatch, audit_rows, raised
):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        _owes(monkeypatch, STILL_OWED)
        ref = _case_no(account["id"])
        answer = _post(
            reconnect_read.reconnect_request,
            brazos,
            marcus,
            ref,
            {"on_date": REQUESTED_ON, "services": ["electric"]},
        )
        assert answer.status_code == 200, answer.data
        case = disconnects.DisconnectCase.objects.get(case_no=ref)
        # The REQUEST: the case awaits its visit, and service is NOT back yet.
        assert case.state == disconnects.STATE_RECONNECTING
        assert case.reconnected_on is None
        # One reconnect job per row left on *Work order*, by the utility's template.
        assert raised == [("reconnect", ["tpl-electric"])]
        assert answer.data["work_orders"] == [{"order_no": "WO-9001"}]
        # No *Service restored* message for a request.
        assert not _restored_messages(brazos, account["id"]).exists()
        # BR-CUS-1097 — owed / who / when, on the audit row.
        mine = [r for r in audit_rows if r.get("action") == disconnects.AUDIT_RECONNECTING]
        assert len(mine) == 1
        assert mine[0]["actor_user_id"] is not None
        assert mine[0]["after"]["owed_at_reconnection"]["stored"] == "804.5000"
        assert mine[0]["after"]["on_date"] == REQUESTED_ON


def test_a_row_on_no_visit_raises_no_job_and_the_request_still_stands(
    brazos, marcus, monkeypatch, raised
):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        ref = _case_no(account["id"])
        answer = _post(
            reconnect_read.reconnect_request, brazos, marcus, ref, {"on_date": REQUESTED_ON}
        )
        assert answer.status_code == 200, answer.data
        assert raised == []
        assert disconnects.DisconnectCase.objects.get(case_no=ref).state == (
            disconnects.STATE_RECONNECTING
        )


def test_an_account_still_owing_is_never_refused_the_request(
    brazos, marcus, monkeypatch, raised
):
    """BR-CUS-1097 — the figure is shown, nothing refuses (worked: $8,315.00)."""
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        _owes(monkeypatch, D("8315.00"))
        answer = _post(
            reconnect_read.reconnect_request,
            brazos,
            marcus,
            _case_no(account["id"]),
            {"on_date": REQUESTED_ON, "services": ["electric"]},
        )
        assert answer.status_code == 200, answer.data
        assert [w["code"] for w in answer.data["warnings"]] == ["money_still_owed"]


def test_a_request_needs_its_date(brazos, marcus, monkeypatch, raised):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        answer = _post(
            reconnect_read.reconnect_request, brazos, marcus, _case_no(account["id"]), {}
        )
        # The platform's VAL refusal (422) naming the field — never a server-clock date.
        assert answer.status_code == 422, answer.data
        assert answer.data["message_key"] == "customers.date_required"


# ════════════════════════════════════════════════════════════════════════════
# 2 · COMPLETING THE REQUEST RESTORES SERVICE AND TELLS THE CUSTOMER ONCE
# ════════════════════════════════════════════════════════════════════════════
def test_completing_the_request_restores_service_and_queues_service_restored_once(
    brazos, marcus, monkeypatch, audit_rows, raised
):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        _owes(monkeypatch, STILL_OWED)
        ref = _case_no(account["id"])
        _post(reconnect_read.reconnect_request, brazos, marcus, ref, {"on_date": REQUESTED_ON})
        done = _post(
            reconnect_read.reconnect_complete, brazos, marcus, ref, {"on_date": RESTORED_ON}
        )
        assert done.status_code == 200, done.data
        case = disconnects.DisconnectCase.objects.get(case_no=ref)
        assert case.state == disconnects.STATE_RESTORED
        assert case.reconnected_on == date(2026, 8, 29)
        assert {row.channel for row in _restored_messages(brazos, account["id"])} == {
            "email",
            "sms",
        }
        # A second press is refused and queues nothing new — exactly once.
        again = _post(
            reconnect_read.reconnect_complete, brazos, marcus, ref, {"on_date": RESTORED_ON}
        )
        assert again.status_code == 422, again.data
        assert _restored_messages(brazos, account["id"]).count() == 2
        # BR-CUS-1097 — what was owed AT RESTORATION, who and when.
        mine = [r for r in audit_rows if r.get("action") == disconnects.AUDIT_RESTORED]
        assert len(mine) == 1
        assert mine[0]["actor_user_id"] is not None
        assert mine[0]["after"]["owed_at_restoration"]["stored"] == "804.5000"
        assert mine[0]["after"]["reconnected_on"] == RESTORED_ON


def test_completion_is_refused_before_the_request(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        ref = _case_no(account["id"])
        answer = _post(
            reconnect_read.reconnect_complete, brazos, marcus, ref, {"on_date": RESTORED_ON}
        )
        assert answer.status_code == 422, answer.data
        assert answer.data["params"]["code"] == "not_reconnecting"
        assert disconnects.DisconnectCase.objects.get(case_no=ref).state == disconnects.STATE_CUT
        assert not _restored_messages(brazos, account["id"]).exists()


def test_an_unreadable_balance_is_recorded_as_an_absence_at_restoration(
    brazos, marcus, monkeypatch, audit_rows, raised
):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        ref = _case_no(account["id"])
        _post(reconnect_read.reconnect_request, brazos, marcus, ref, {"on_date": REQUESTED_ON})
        _owes(monkeypatch, D("0"), available=False)
        done = _post(
            reconnect_read.reconnect_complete, brazos, marcus, ref, {"on_date": RESTORED_ON}
        )
        # Restoration does not read the money to decide anything — it records it.
        assert done.status_code == 200, done.data
        assert done.data["owed_at_restoration"] is None
        assert done.data["owed_at_restoration_absence"]["code"] == "balance_unreadable"


# ════════════════════════════════════════════════════════════════════════════
# 3 · THE REQUEST'S STATUS IS ON THE CASE
# ════════════════════════════════════════════════════════════════════════════
def test_the_case_record_carries_the_reconnect_request_jobs(brazos, marcus, monkeypatch, raised):
    seen: list = []

    def _visits(*, flow_kind, source_ref):
        seen.append((flow_kind, source_ref))
        return {"raised": 1, "done": 0, "accepted": 0, "orders": [{"order_no": "WO-9001"}]}

    from apps.customers import seams as customer_seams

    monkeypatch.setattr(customer_seams, "flow_work_visits", _visits)
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        ref = _case_no(account["id"])
        case = disconnects.DisconnectCase.objects.get(case_no=ref)
        # Before the request there is no request to show.
        assert disconnect_record.reconnect_work_orders_panel(case) is None
        _post(reconnect_read.reconnect_request, brazos, marcus, ref, {"on_date": REQUESTED_ON})
        case.refresh_from_db()
        panel = disconnect_record.reconnect_work_orders_panel(case)
        assert panel["value"]["orders"] == [{"order_no": "WO-9001"}]
        assert ("reconnect", ref) in seen


# ════════════════════════════════════════════════════════════════════════════
# 4 · TENANT ISOLATION AND ROLE
# ════════════════════════════════════════════════════════════════════════════
def test_another_utility_cannot_request_or_complete_this_case(
    brazos, marcus, lonestar, erin, monkeypatch, raised
):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        ref = _case_no(account["id"])
    for view in (reconnect_read.reconnect_request, reconnect_read.reconnect_complete):
        probed = _post(view, lonestar, erin, ref, {"on_date": REQUESTED_ON}, role="system_admin")
        assert probed.status_code == 404, (view.__name__, probed.status_code, probed.data)
    with tenant_ctx(brazos):
        assert disconnects.DisconnectCase.objects.get(case_no=ref).state == disconnects.STATE_CUT


def test_an_executive_cannot_request_a_reconnect(brazos, marcus, monkeypatch, raised):
    with tenant_ctx(brazos):
        account, _payload = _cut(marcus, brazos, monkeypatch)
        ref = _case_no(account["id"])
        answer = _post(
            reconnect_read.reconnect_request,
            brazos,
            marcus,
            ref,
            {"on_date": REQUESTED_ON},
            role="executive",
        )
        assert answer.status_code == 403, answer.data
