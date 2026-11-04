"""Quote a service-request fee the way the product now does — at a price the
tenant's charge-code catalogue carries.

⚠ **WHY THIS EXISTS (`DEF-CUS-6416`, 2026-09-23).** `add_fee_line` used to store
whatever `unit_amount` it was handed, and these suites leaned on that: they
quoted `CC-REQFEE` at `$130.00`, `$25.00` and `$0.01` on tenants whose catalogue
held no such code at all. The server now PRICES a line from the charge code at
the moment of the Add and REFUSES a figure that disagrees, so a test that wants
a line at `$130.00` must first say so where a utility would — on the charge
code. That is all `quote_fee` does, and it does it through the ORM because a
fixture setting a price is a tenant act, not the door under test.

The line itself still goes in through `add_fee_line`, the published door, so
every refusal and every audit row these suites assert is the product's own.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.customers import service_request_service as sr
from apps.rating import models as rating_models
from core import tenancy as core_tenancy


def price_charge_code(code: str, amount: Any) -> rating_models.Charge:
    """The current tenant's live, flat, one-time `code`, priced at `amount`.

    Created where the tenant has none; where it has one (a provisioned `CONN`,
    or a code a test mapped to a GL account first), only its price moves and
    everything else a test set on it — its account above all — is kept.
    """
    tenant_id = core_tenancy.current_tenant_id()
    charge = rating_models.Charge.objects.filter(tenant_id=tenant_id, code=code).first()
    if charge is None:
        return rating_models.Charge.objects.create(
            tenant_id=tenant_id,
            code=code,
            name=f"{code} fee",
            charge_type="one_time",
            amount_rule="flat",
            amount=Decimal(str(amount)),
        )
    charge.amount = Decimal(str(amount))
    charge.amount_rule = "flat"
    charge.deleted_at = None
    charge.save(update_fields=["amount", "amount_rule", "deleted_at"])
    return charge


def quote_fee(actor: Any, request_id: Any, *, charge_code: str, unit_amount: Any, **kwargs: Any):
    """`add_fee_line`, with the catalogue first set to the price being quoted."""
    price_charge_code(charge_code, unit_amount)
    return sr.add_fee_line(
        actor, request_id, charge_code=charge_code, unit_amount=unit_amount, **kwargs
    )
