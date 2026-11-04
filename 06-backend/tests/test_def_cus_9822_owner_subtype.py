"""`DEF-CUS-9822` (N1) — the Sub-category picked on New Connect step 1 reaches
the owner's account.

THE WORKED CASE: Balcones Development LLC builds two homes; on step 1 the clerk
picks **Commercial** and, under it, the utility's own sub-type **Healthcare**.
The owner's master account must carry `account_subtype = healthcare`. Until this
change step 1 offered two hand-typed words (*Construction temporary*,
*Permanent*) whatever the category, sent them as `sub_category`, and the server
dropped the key — so every build's account read no sub-type.

Through `commit_new_connect` with the browser's own payload shape.
"""

from __future__ import annotations

import pytest

from apps.customers import models as customers_models
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from tests.test_def_cus_8020_8021_the_create_button import _owner_block, _wizard_plan
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _clinic(tenant):
    commercial = customers_models.AccountType.objects.get(tenant=tenant, code="commercial")
    return customers_models.AccountSubtype.objects.create(
        tenant=tenant, account_type=commercial, code="nct01_clinic", name="Walk-in clinic"
    )


def test_the_chosen_sub_type_reaches_the_owner_account(dana, brazos):
    with tenant_ctx(brazos):
        _clinic(brazos)
        owner = _owner_block(account_type="commercial", account_subtype="nct01_clinic")
        built = w6.commit_new_connect(dana, _wizard_plan(owner=owner))
        connection = work_tables.Connection.objects.get(pk=built["id"])
        account = customers_models.Account.objects.get(pk=connection.owner_account_id)
        assert account.account_subtype is not None, "the sub-type was dropped at the commit"
        assert account.account_subtype.code == "nct01_clinic"


def test_no_sub_type_is_no_sub_type(dana, brazos):
    with tenant_ctx(brazos):
        owner = _owner_block(account_type="commercial")
        built = w6.commit_new_connect(dana, _wizard_plan(owner=owner))
        connection = work_tables.Connection.objects.get(pk=built["id"])
        account = customers_models.Account.objects.get(pk=connection.owner_account_id)
        assert account.account_subtype_id is None
