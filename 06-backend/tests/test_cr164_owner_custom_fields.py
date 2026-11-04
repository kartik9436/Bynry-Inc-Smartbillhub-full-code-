"""`CR-164-BRC10` wave 2 — the owner's own customer fields on New Connection Step 1.

Handed over by the custom-fields lane (`CR-161-BRC10` W4, 2.461.0): the slot
`NEW_CONNECTION_OWNER` was declared and switched off because the answers had no
road from Step 1 to the customer. The road is built here:

    Step 1 (`ownerCustomData`) → commit owner block `customer_custom_data`
    → `_owner_block_in_the_doors_language` puts it on the customer block
    → `create_master_account(..., customer_fields_screen="NEW_CONNECTION_OWNER")`
    → `_validate_customer_block` validates it AS THAT SLOT → the new customer row.

THE WORKED CASE: a utility defines *Loyalty tier* on customers, placed Input on
New Connection Step 1. Balcones Development LLC is built with *Gold* → its
customer row holds `{"loyalty_tier": "Gold"}`. Made REQUIRED and left out, the
press is refused naming `custom_data.loyalty_tier` — and the same field placed
only on New account does NOT bind New Connection (required binds only where it
is typed, BR-TEN-052 as amended).

Through `commit_new_connect` with the browser's own payload, never the door.
"""

from __future__ import annotations

import pytest

from apps.customers import models as customers_models
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.tenancy import custom_fields as cf_law
from apps.tenancy import services as tenancy_services
from core import errors
from tests.test_def_cus_8020_8021_the_create_button import _owner_block, _wizard_plan
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _field(actor, placement, *, required=False):
    field = tenancy_services.create_custom_field(
        actor,
        {"label": "Loyalty tier", "entity": "customers", "data_type": "text", "is_required": required},
    )
    tenancy_services.save_custom_field_placement(actor, field["id"], placement)
    return field


def _owner_customer(built):
    connection = work_tables.Connection.objects.get(pk=built["id"])
    link = customers_models.CustomerAccount.objects.get(account_id=connection.owner_account_id)
    return customers_models.Customer.objects.get(pk=link.customer_id)


def test_the_slot_is_rendered():
    slot = next(s for s in cf_law.SLOTS if s.key == "NEW_CONNECTION_OWNER")
    assert slot.rendered is True


def test_the_owners_answer_reaches_the_new_customer(dana, brazos):
    with tenant_ctx(brazos):
        _field(dana, {"NEW_CONNECTION_OWNER": "input"})
        owner = _owner_block(customer_custom_data={"loyalty_tier": "Gold"})
        built = w6.commit_new_connect(dana, _wizard_plan(owner=owner))
        assert _owner_customer(built).custom_data == {"loyalty_tier": "Gold"}


def test_required_binds_on_new_connection_step_1(dana, brazos):
    with tenant_ctx(brazos):
        _field(dana, {"NEW_CONNECTION_OWNER": "input"}, required=True)
        owner = _owner_block(customer_custom_data={})
        with pytest.raises(errors.ValidationError) as refused:
            w6.commit_new_connect(dana, _wizard_plan(owner=owner))
        assert "custom_data.loyalty_tier" in [e["field"] for e in refused.value.field_errors]


def test_a_field_placed_only_on_new_account_does_not_bind_here(dana, brazos):
    with tenant_ctx(brazos):
        _field(dana, {"S18": "input"}, required=True)
        owner = _owner_block(customer_custom_data={})
        built = w6.commit_new_connect(dana, _wizard_plan(owner=owner))
        assert _owner_customer(built).custom_data == {}
