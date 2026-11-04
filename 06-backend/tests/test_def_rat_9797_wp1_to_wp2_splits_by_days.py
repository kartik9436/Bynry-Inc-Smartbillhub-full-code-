# ── Trace ──────────────────────────────────────────────
# Ruling:  PO 2026-10-06, B (a), verbatim: "When a plan's base code is changed
#          (Plan A moves from WP-1 to WP-2), when does it take effect? (a) From
#          a date you choose, like other plan changes ("Change from a date"). A
#          bill straddling the date splits by days: WP-1 up to the date, WP-2
#          after."
# Defect:  DEF-RAT-9797 (a rate schedule names exactly one base code)
# Rules:   BR-RAT-1025 · BR-RAT-114 (the mid-period split) · GT-34's mechanism
# ───────────────────────────────────────────────────────
"""B (a) needs no new mechanism: the base-code change is a new schedule VERSION
from a date, each version names its own base code, and the ordinary run already
splits a straddling period at the version boundary.

Fixture: water, June 2026 (30 days), the new version starts June 16. The old
version names WP-1 ($30.00 a month), the new one WP-2 ($60.00). The bill
carries ONE base line per side, WP-1 for June 1–15 and WP-2 for June 16–30 —
never WP-2 for the whole month, never WP-1 for the whole month.
"""

from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from tests.test_br_rat_114_midperiod_split import (
    PERIOD_END,
    a_cycle,
    a_cycled_water_unit,
    a_repricing_water_plan,
    an_ordinary_bill,
)
from tests.test_us_bil_001_prepare import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures (brazos, dana)
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _base_code(tenant, code, amount, classes=None):
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=code,
        name=f"{code} water base",
        charge_type="recurring",
        amount_rule="flat",
        amount=Decimal(amount),
        service=tenancy_models.Service.objects.get(code="water"),
        is_base=True,
        applies_to_customer_classes=classes or [],
    )


def test_wp1_to_wp2_on_the_16th_bills_wp1_to_the_15th_and_wp2_after(brazos, dana):
    with tenant_ctx(brazos):
        plan, versions = a_repricing_water_plan(brazos, name="WP Water", old="2.000000", new="2.000000")
        cycle = a_cycle(brazos, "WP-1-2")
        unit = a_cycled_water_unit(
            dana, brazos, cycle, plan, asset_no="W-9797", reads=[(PERIOD_END, "10.000000")]
        )
        account = an_account(brazos, unit["id"], "A-97971")
        # The fixture's own $0.00 base code is retired: WP-1 and WP-2 are the bases.
        rating_models.Charge.objects.filter(tenant=brazos, code="BASE-W-R114").update(is_base=False)
        account_class = account.account_type.code
        wp1 = _base_code(brazos, "WP-1", "30.00")
        # WP-2 names the account's class — an every-class WP-2 beside an
        # every-class WP-1 is refused by the ruled overlap guard (A (a)).
        wp2 = _base_code(brazos, "WP-2", "60.00", classes=[account_class])
        versions["old"].base_charge_code = wp1
        versions["old"].save(update_fields=["base_charge_code"])
        versions["new"].base_charge_code = wp2
        versions["new"].save(update_fields=["base_charge_code"])

        invoice = an_ordinary_bill(brazos, cycle, "wp1-wp2")

        base_lines = sorted(
            (line for line in invoice.lines.all() if line.kind == "base"),
            key=lambda line: line.description,
        )
        by_version = {str(line.tariff_version_id): line for line in base_lines}
        assert set(by_version) == {str(versions["old"].id), str(versions["new"].id)}, [
            (line.description, line.amount) for line in base_lines
        ]
        old_line = by_version[str(versions["old"].id)]
        new_line = by_version[str(versions["new"].id)]
        # By days: 15 of 30 at WP-1's $30.00, 15 of 30 at WP-2's $60.00.
        assert old_line.amount == Decimal("15.00"), old_line.description
        assert new_line.amount == Decimal("30.00"), new_line.description
        assert billing_models.Invoice.objects.filter(account_id=account.id).count() == 1
