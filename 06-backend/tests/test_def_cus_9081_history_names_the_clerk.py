# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-9081 — account history recorded NOBODY as the person who
#          changed an account when the change came through the app.
# Rules:   CLAUDE.md hard rule 7 (every change says who) · CR-142 P0.18 (the
#          as-was history, `apps/customers/attribute_history.py`)
# ───────────────────────────────────────────────────────
"""**A CLERK CHANGES AN ACCOUNT IN THE APP, AND THE HISTORY NAMES THAT CLERK.**

Every API layer builds the B12 §6a actor, `SimpleNamespace(id, role)` — an `id`
and no `pk`. `attribute_history.record` wrote `recorded_by` only when the actor
had a `pk`, so every change a clerk made through the app recorded nobody, and
nothing refused it because the column is nullable. The fixture actor
(`staff_actor`) carries a `pk` that no API layer builds, which is how the suite
stayed green over it (`core.audit.actor_user_id`'s own docstring records the
same trap once before, DEF-BIL-5090).

The change goes through the real view (`PATCH /accounts/{id}`), and the row is
read back through the read the app's reports use (`attribute_history.as_was`);
no endpoint serves `recorded_by` to a screen today.
"""

from __future__ import annotations

import pytest
from django.utils import timezone

from apps.customers import api as customers_api
from apps.customers import attribute_history
from tests.test_us_bil_001_prepare import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


class _SessionUser:
    """What the session hands a view: an authenticated user. The VIEW builds
    the `SimpleNamespace(id, role)` actor from it — that shape is the subject."""

    def __init__(self, user_id):
        self.id = user_id
        self.pk = user_id
        self.is_authenticated = True


def test_def_cus_9081_a_clerk_change_through_the_app_names_the_clerk(brazos, dana, marcus):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="9 Kestrel Close")
        unit = make_unit(dana, premises["id"], label="Unit A")
        account = an_account(brazos, unit["id"], "A-90810")

    response = api_call(
        customers_api.account_item,
        "patch",
        user=_SessionUser(marcus.user.pk),
        role="billing_clerk",
        tenant=brazos,
        data={"paperless": True},
        account_id=str(account.pk),
    )
    assert response.status_code == 200, response.data

    with tenant_ctx(brazos):
        row = attribute_history.as_was(account.pk, on=timezone.localdate())
    assert row is not None, "the change wrote no history row at all"
    assert row.recorded_by_id == marcus.user.pk, (
        f"the history names {row.recorded_by_id!r}, not the clerk who made the change"
    )
