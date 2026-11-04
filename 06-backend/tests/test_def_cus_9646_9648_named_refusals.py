# ── Trace ──────────────────────────────────────────────
# Defects: DEF-CUS-9646 (POST /transfers/commit answered 500, KeyError
#          'business', for a buyer kind the identifier table does not know)
#          DEF-CUS-9648 (POST /accounts/{id}/disconnect-case/cut answered 500
#          for an account id that is not a uuid, where GET /accounts/{id}
#          answers 404)
# Change:  CR-168-BRC10 round 6, lane CREWS-2.
# Rules:   BR-CUS-1023 (a refusal names the missing thing) · CLAUDE.md hard
#          rule 1 / BR-TEN-003 (an id this tenant cannot see is a 404) ·
#          hard-won law 7 (red first)
# ───────────────────────────────────────────────────────
"""Two 500s that should have been sentences.

RED FIRST, on `3cd891cfb` (quoted in the lane report):

  * DEF-CUS-9646 — ``KeyError: 'business'`` raised out of ``_validated_buyer``
    at ``identity_match.CREATE_IDENTIFIER_FIELDS[kind]``.
  * DEF-CUS-9648 — ``django.core.exceptions.ValidationError: ['“None” is not a
    valid UUID.']`` (or the driver's own) out of the case write routes, which
    resolve the account inside the service and never through the 404 door the
    reads use (`_account_or_404`, DEF-2130).
"""

from __future__ import annotations

import pytest

from apps.customers import transfer_disconnect_api as doors
from apps.customers import transfers
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, marcus, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


# ── DEF-CUS-9646 ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", ["business", "trust", "Partnership"])
def test_an_unknown_buyer_kind_is_refused_by_name_and_never_a_keyerror(brazos, kind):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            transfers._validated_buyer(
                {"display_name": "Acme Holdings", "kind": kind, "identity": {"tax_id": "74-1234567"}}
            )
    assert caught.value.message_key == "customers.customer.kind_unknown"
    assert caught.value.params["value"] == kind


def test_the_commit_door_answers_a_named_422_for_an_unknown_buyer_kind(brazos, marcus, monkeypatch):
    from tests.test_w7_transfers import _mover
    from tests.test_w7_worklists import _wire_interest

    _wire_interest(monkeypatch)
    with tenant_ctx(brazos):
        _customer, account, _unit = _mover(marcus, brazos)
    response = api_call(
        doors.transfer_commit,
        "post",
        user=marcus.user,
        role="billing_clerk",
        tenant=brazos,
        data={
            "from_account_id": str(account.id),
            "sold_on": "2026-10-01",
            "customer": {
                "display_name": "Acme Holdings",
                "kind": "business",
                "identity": {"tax_id": "74-1234567"},
            },
        },
    )
    assert response.status_code == 422, response.data
    assert response.data["message_key"] == "customers.customer.kind_unknown", response.data


def test_the_two_lawful_kinds_still_pass(brazos):
    with tenant_ctx(brazos):
        person = transfers._validated_buyer(
            {"display_name": "Ana Ruiz", "kind": "person", "identity": {"phone": "5125550101"}}
        )
        company = transfers._validated_buyer(
            {"display_name": "Acme", "kind": "Company", "identity": {"tax_id": "74-1234567"}}
        )
    assert person["kind"] == "person"
    assert company["kind"] == "company"


# ── DEF-CUS-9648 ─────────────────────────────────────────────────────────────

CASE_WRITES = [
    "open_disconnect_case",
    "advance_disconnect_case",
    "record_disconnect_notice",
    "commit_cut",
    "finish_cut",
    "record_visit",
    "stop_by_hand",
    "mark_reconnecting",
    "restore_service",
]


@pytest.mark.parametrize("view_name", CASE_WRITES)
@pytest.mark.parametrize("account_id", ["None", "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_a_case_write_on_a_malformed_or_absent_account_is_a_404(brazos, marcus, view_name, account_id):
    view = getattr(doors, view_name)
    try:
        response = api_call(
            view,
            "post",
            user=marcus.user,
            role="system_admin",
            tenant=brazos,
            data={"cut_on": "2026-10-04", "as_of": "2026-10-04"},
            account_id=account_id,
        )
    except Exception as exc:  # the 500 the defect is about, made legible
        pytest.fail(f"{view_name}({account_id!r}) raised {type(exc).__name__}: {exc}")
    assert response.status_code == 404, (view_name, account_id, response.status_code, response.data)
