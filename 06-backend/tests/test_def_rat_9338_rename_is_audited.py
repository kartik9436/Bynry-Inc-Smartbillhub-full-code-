"""`DEF-RAT-9338` — renaming a discount must be in its audit.

Found by the CR-166-BRC10 web walk, step 7 (2026-10-03, PostgreSQL 16): Edit ›
Name and details renamed *Autopay discount* to *Autopay savings* and changed its
funding source; the Audit tab showed only the funding source, because
`update_discount` took its *before* snapshot after it had already assigned the
new code and name. A rename ALONE wrote no audit row at all (before == after).
"""

import pytest

from apps.rating import discount_services

from tests.test_cr166_discounts_round2 import _discount
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import audit_rows, brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _updated_rows(trail, discount_id):
    """Read from the capture sink (`audit_rows` points `core.audit` at a list,
    so nothing reaches `audit_log` in this suite). The census is asserted
    non-empty below, so a sink that captured nothing cannot pass."""
    assert trail, "the audit capture sink recorded nothing at all"
    return [r for r in trail if r["action"] == "discount.updated" and str(r["entity_id"]) == str(discount_id)]


def test_a_rename_alone_writes_one_audit_row_naming_the_old_name_and_code(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        senior = _discount(dana)
        old_name, old_code = senior.name, senior.code
        discount_services.update_discount(dana, senior.id, {"name": "Seniors' savings", "code": "SENIORS"})
        rows = _updated_rows(audit_rows, senior.id)
    assert len(rows) == 1
    assert (rows[0]["before"]["name"], rows[0]["before"]["code"]) == (old_name, old_code)
    assert (rows[0]["after"]["name"], rows[0]["after"]["code"]) == ("Seniors' savings", "SENIORS")


def test_a_rename_with_a_funding_change_keeps_the_old_name_in_before(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        senior = _discount(dana)
        old_name = senior.name
        discount_services.update_discount(
            dana, senior.id, {"name": "Seniors' savings", "funding_source": "City budget"}
        )
        rows = _updated_rows(audit_rows, senior.id)
    assert len(rows) == 1
    assert rows[0]["before"]["name"] == old_name
    assert rows[0]["after"]["name"] == "Seniors' savings"
    assert rows[0]["after"]["funding_source"] == "City budget"
