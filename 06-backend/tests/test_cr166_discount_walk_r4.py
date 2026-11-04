# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 4 task 9 — what the discounts web walk found on
#          the server side.
# Defects: DEF-RAT-9325 (a proof-pending enrollment can never be verified)
# ───────────────────────────────────────────────────────
"""The web walk's server-side finds, each written RED first.

DEF-RAT-9325: `discount_services.verify_enrolment` was built and never routed,
so an enrollment in an Apply-and-approve discount whose version needs proof
before the first reduction stayed *Proof pending* for ever, and the account's
bill never carried the discount (Senior 15% on a $60.00 bill: $0.00 where it
should be −$9.00). `POST /discount-enrolments/{id}/verify` is the door.
"""

from datetime import date

import pytest

from apps.rating import api as rating_api
from apps.rating import discount_services
from apps.rating import discounts as dm

from tests.test_cr166_discounts_round2 import _bind, _discount, _home, _reduction_on, _user
from tests.test_cr166_discounts_round2 import _today  # noqa: F401 — the pinned "today"
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, dana, marcus, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def test_def_rat_9321_a_proof_pending_enrolment_is_verified_through_its_door(brazos, dana):
    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
        senior = _discount(dana, proof_required=True, proof_before_first_reduction=True)
        _bind(dana, brazos, senior)
        row = discount_services.enrol_account(dana, senior.id, account["id"], enrolled_on=date(2026, 9, 1))
        assert row["verification_status"] == dm.VERIFICATION_PENDING
        before = _reduction_on(account["id"], date(2026, 10, 15))
    response = api_call(
        rating_api.discount_enrolment_verify,
        "post",
        user=_user(dana),
        role="system_admin",
        tenant=brazos,
        data={},
        enrolment_id=row["id"],
    )
    assert response.status_code == 200, response.data
    assert response.data["verification_status"] == dm.VERIFICATION_VERIFIED
    with tenant_ctx(brazos):
        after = _reduction_on(account["id"], date(2026, 10, 15))
    # $0.00 while the proof is pending, −$9.00 (15% of $60.00) once verified.
    assert (before, after) == (0, 9)


def test_def_rat_9321_only_a_system_admin_verifies(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _unit_row, account = _home(dana, brazos)
        senior = _discount(dana, proof_required=True, proof_before_first_reduction=True)
        _bind(dana, brazos, senior)
        row = discount_services.enrol_account(dana, senior.id, account["id"], enrolled_on=date(2026, 9, 1))
    response = api_call(
        rating_api.discount_enrolment_verify,
        "post",
        user=_user(marcus),
        role="billing_clerk",
        tenant=brazos,
        data={},
        enrolment_id=row["id"],
    )
    assert response.status_code in (403, 404)

