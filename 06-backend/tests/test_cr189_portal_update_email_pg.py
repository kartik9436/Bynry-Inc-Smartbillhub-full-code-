"""CR-189-BRC10 on PostgreSQL — what SQLite cannot hold (law 14).

    pytest tests/test_cr189_portal_update_email.py tests/test_cr189_portal_update_email_pg.py \\
        --ds=config.settings.pgtest --reuse-db

The SQLite file runs unchanged under `pgtest` too; this file adds the RLS half:
the code rows the flow writes are invisible to another utility through the
DATABASE, under the non-superuser probe role, and the whole confirm transaction
(contact write, login write, notice, reset, audit) commits on PostgreSQL.
"""

import json

import pytest
from django.test import Client

from apps.portal import email_update
from apps.portal import models as portal_models
from core.tenancy import tenant_context
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_rls_scoped,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import elm_street_account, switch_on

FACTS = {"postcode": "78702", "last_name": "Alvarez"}


def post(tenant, path, body):
    return (
        Client()
        .post(
            f"/api/{tenant.subdomain}/portal/update-email/{path}",
            data=json.dumps(body),
            content_type="application/json",
        )
        .json()
    )


@requires_postgres
@pytest.mark.django_db
def test_pg_the_flows_code_rows_are_invisible_to_another_utility(
    pine_hill, sarah, oak_ridge, elena, rls
):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    found = post(pine_hill, "find", {"account_number": account.account_no, **FACTS})
    sent = post(pine_hill, "send-code", {"ref": found["ref"], "option": found["options"][0]["key"]})
    with tenant_context(pine_hill.id):
        ids = set(
            str(pk)
            for pk in portal_models.PortalOneTimeCode.objects.filter(
                purpose__in=(email_update.PURPOSE_MATCH, email_update.PURPOSE_PROVE)
            ).values_list("pk", flat=True)
        )
    assert {found["ref"], sent["ref"]} <= ids
    assert_rls_scoped(
        rls, "portal_one_time_code", owner=pine_hill, intruder=oak_ridge, owner_ids=ids
    )
