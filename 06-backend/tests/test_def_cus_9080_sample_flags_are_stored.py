# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-9080 — the sample account flags never stored the delivery
#          election or the tax exemption.
# Rules:   CR-089 I6 (`seed_account_flags`: at least one account carries each
#          flag) · CR-142 P0 (account history records WHO changed the account)
# ───────────────────────────────────────────────────────
"""**THE TWO FLAGS LAND, WITH THE ACTOR THE ORCHESTRATOR ACTUALLY PASSES.**

The sample orchestrator hands every block a stand-in actor — `id`, `pk`, `role`
and the real `user` behind them (`staff_actor` builds the same shape). Account
history's `recorded_by` is a foreign key into `users`, so the stand-in itself
was refused (*"must be a User instance"*), the seeder logged it at INFO and moved
on, and the seeded tenant carried neither flag: `A-10650 kept no delivery
election`, `A-10714 kept no tax exemption`.
"""

from __future__ import annotations

import pytest

from apps.customers import models as customer_models
from apps.customers import sample_account_flags
from apps.customers.attribute_history_models import AccountAttributeHistory
from tests.test_us_bil_001_prepare import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def test_def_cus_9080_both_flags_are_stored_and_history_names_the_seed_user(brazos, dana):
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="18 Marten Row")
        for index in range(3):
            unit = make_unit(dana, premises["id"], label=f"Unit {index + 1}")
            an_account(brazos, unit["id"], f"A-9080{index}")

        # `dana` is the orchestrator's shape: id, pk, role AND the real user.
        assert getattr(dana, "_meta", None) is None
        sample_account_flags.seed_account_flags(dana)

        accounts = customer_models.Account.objects.filter(tenant_id=brazos.id)
        reach = [a for a in accounts if a.paperless and a.sms_reminders]
        exempt = [a for a in accounts if a.tax_exempt]
        assert len(reach) == 1, "the delivery election was not stored"
        assert len(exempt) == 1, "the tax exemption was not stored"
        assert exempt[0].tax_exempt_ref == sample_account_flags.TAX_EXEMPT_REF

        # …and the history row says WHO: the real seed user, not nobody.
        recorded = set(
            AccountAttributeHistory.objects.filter(
                tenant_id=brazos.id, account_id__in=[reach[0].pk, exempt[0].pk]
            ).values_list("recorded_by_id", flat=True)
        )
        assert recorded == {dana.user.pk}
