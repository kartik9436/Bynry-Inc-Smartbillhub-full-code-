"""DEF-MET-9232 — a New Connection letter names the customer, the account and the address.

Found by the New Connection end-to-end web walk (2026-10-03): *Send now* on the
quote letter of `CON-26-0144` queued a copy reporting
`render_context_missing_tokens: account_no, currency, customer_name,
service_address`, and the Messages tab's preview printed dashes for the name and
address. The letters' bodies greet the customer by name and quote the account
number and the service address; the render context carried only the build
number, the target date and the amount.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7, habit 2): a context that carried
the KEYS with no values — so each value is compared with the account's own row
(its number, Maria's name, her street), never merely asserted present.
"""

from __future__ import annotations

import pytest

from apps.metering import connection_messages as letters
from apps.work import connection_models as work_tables

from tests.test_def_cus_9228_single_family_owner_pays import _maria_builds, _owner_account
from tests.test_portal_request_to_active import (  # noqa: F401 — fixtures
    _ctx,
    cedar,
    clerk,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam

pytestmark = pytest.mark.django_db


def _occasion(code):
    return next(one for one in letters.OCCASIONS if one.code == code)


def test_the_build_created_letter_names_maria_her_account_and_her_street(cedar, clerk):
    built = _maria_builds(clerk, cedar, quote_lines=[], quote_due_days=None)
    account = _owner_account(cedar, built["id"])
    with _ctx(cedar):
        connection = work_tables.Connection.objects.get(pk=built["id"])
        context, gap = letters._context(connection, _occasion("build_created"))
    assert gap is None
    assert context["customer_name"] == "Maria Alvarez"
    assert context["account_no"] == account.account_no
    assert context["service_address"] == "14 Oak St, Austin, TX 78701"
    assert context["connection_no"] == connection.connection_no


def test_a_build_with_no_owner_account_states_each_absence(cedar, clerk):
    """No owner, no account: the keys travel with None — *genuinely absent*,
    which the queue reads differently from *forgotten*."""
    built = _maria_builds(
        clerk, cedar, owner=None, quote_lines=[], quote_due_days=None, quote_payer=None
    )
    with _ctx(cedar):
        connection = work_tables.Connection.objects.get(pk=built["id"])
        context, _gap = letters._context(connection, _occasion("build_created"))
    for key in ("customer_name", "account_no", "service_address"):
        assert key in context and context[key] is None
