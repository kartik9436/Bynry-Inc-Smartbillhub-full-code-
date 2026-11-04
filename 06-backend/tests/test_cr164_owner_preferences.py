"""`CR-164-BRC10` / `DEF-CUS-9195` — step 1's Communication panel reaches the
master account.

THE WORKED CASE: Balcones Development LLC builds two homes; on step 1 the clerk
picks **Español (México)**, ticks **Paperless bill** and **SMS reminders**. The
owner's master account must hold `es-MX`, `paperless=True`, `sms_reminders=True`.
Until this change all three were typed, shown and dropped at the commit
(`DEF-CUS-7863`), so the account held no language and both flags false.

Through `commit_new_connect` with the browser's own payload shape — the path a
clerk's press takes — never through the accounts door directly.
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


def test_language_and_the_two_ticks_reach_the_master_account(dana, brazos):
    owner = _owner_block(preferred_language="es-MX", paperless=True, sms_reminders=True)
    with tenant_ctx(brazos):
        built = w6.commit_new_connect(dana, _wizard_plan(owner=owner))
        connection = work_tables.Connection.objects.get(pk=built["id"])
        account = customers_models.Account.objects.get(pk=connection.owner_account_id)
    assert account.preferred_language == "es-MX"
    assert account.paperless is True
    assert account.sms_reminders is True


def test_an_unpicked_language_is_no_preference_never_english(dana, brazos):
    owner = _owner_block(preferred_language=None, paperless=False, sms_reminders=False)
    with tenant_ctx(brazos):
        built = w6.commit_new_connect(dana, _wizard_plan(owner=owner))
        connection = work_tables.Connection.objects.get(pk=built["id"])
        account = customers_models.Account.objects.get(pk=connection.owner_account_id)
    assert account.preferred_language in (None, "")
    assert account.paperless is False
