"""DEF-RAT-9298 — sample data must still map a tax's liability account.

2.472.0 (CR-165-BRC10 round 2, PO ruling 2026-10-03 on CR-008: *"Pick it when
you create the tax; change it later only in Settings -a llow it"*) made
`update_tax` refuse `liability_gl_account_id` on a live tax. The sample-data
step `_map_liability_account` still called `update_tax`, so the WHOLE rating
block of a fresh utility's sample data failed at its first tax: no taxes after
it, no discounts, nothing seeded after them (BIZ-IMMUTABLE
rating.taxes.liability_edit_in_settings).

The fix routes the mapping through Settings › Accounting's own door,
`set_tax_liability_account` — the one place the ruling allows it after
creation. This test is red on the pre-fix tree (the BizError above) and green
after it.
"""

from datetime import date
from decimal import Decimal

from apps.rating import models as rating_models
from apps.rating import sample_data
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import staff_actor, tenant_ctx


def test_9298_sample_data_maps_the_liability_account_of_a_live_tax(brazos):
    actor = staff_actor(brazos)
    with tenant_ctx(brazos):
        authority, _ = rating_models.TaxJurisdiction.objects.get_or_create(
            tenant=brazos, name="DEF-9298 City"
        )
        tax = rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=authority,
            name="DEF-9298 city tax",
            kind="percent",
            rate=Decimal("0.020000"),
            effective_from=date(2026, 1, 1),
        )
        assert tax.liability_gl_account_id is None

        sample_data._map_liability_account(actor, tax.id, "DEF-9298 City")

        tax.refresh_from_db()
        assert tax.liability_gl_account_id is not None
