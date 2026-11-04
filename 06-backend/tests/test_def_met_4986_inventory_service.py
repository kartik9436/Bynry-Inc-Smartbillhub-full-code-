# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-4986 — the utility service the add-asset wizard REQUIRES on
#          step 1 is discarded on the wizard's DEFAULT destination. An asset
#          left in inventory keeps no service at all, and until CR-092 lane 5
#          nothing on any screen said so.
# Rules:   BR-AST-009 (a measuring type must declare a service) ·
#          BR-AST-011 (assign-on-create vs leave-in-inventory) ·
#          B2 r4 (the service lives on the SERVICE POINT, which only exists
#          once the asset sits on a unit)
# Question: OQ-MET-1768 — where an unassigned asset's declared service lives.
#          OPEN. This file asserts what the product does TODAY and refuses to
#          choose an answer (prime directive).
# ───────────────────────────────────────────────────────
"""**The service is validated, then dropped — proved on the row, not on a toast.**

⚠ **WHY THIS COULD NOT BE SEEN FROM THE SCREEN, AND WHY IT NEEDS A TEST AT ALL.**
The wizard refuses a meter with no service, refuses one whose service the tenant
has not enabled, and then — on the destination it *defaults to* — writes a row
with no service on it. What the clerk sees is a success toast. The front-end
suite asserts that `addPayload()` CONTAINS `service`, which it does; the loss
happens one module across, under the write.

**The mechanism, in three lines of product code:**

* `assets` has **no `service` column** — `information_schema` on the development
  database returns exactly one service-ish column, `service_point_id`;
* `selectors._service_of()` DERIVES the served `service` from that point;
* `services._create_asset_inner()` reaches for a point only
  ``if unit_id and service_code``.

`_check_measuring_requirements` already says so in its own docstring — *"The
unassigned service declaration has no column to live in; that gap is reported,
not invented around"* — and this file is that report made executable.

⚠ **IT PINS TODAY'S BEHAVIOUR AND DOES NOT BLESS IT.** Where the declaration
should live — a column on `assets`, or a service point with no unit — is
`OQ-MET-1768` and is OPEN. When it is answered this file goes RED and names the
question, which is the point: a gap nothing asserts is a gap the next lane
closes by accident or re-opens by accident.

Proved RED first by asserting the opposite (that an inventory spare keeps its
service): ``AssertionError: assert None == 'water'``.
"""

from __future__ import annotations

import pytest

from apps.assets import models, selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_asset, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def test_def_met_4986__an_inventory_spare_keeps_no_service(brazos, dana):
    """The wizard's DEFAULT destination. Same field, same typed value."""
    with tenant_ctx(brazos):
        spare = make_asset(
            dana,
            asset_no="DEF4986-INVENTORY",
            service="water",
            unit="kgal",
            size_class=None,
        )
        # The form was accepted, so the value passed every check the server has.
        assert spare["asset_no"] == "DEF4986-INVENTORY"

        row = models.Asset.objects.get(tenant_id=brazos.id, asset_no="DEF4986-INVENTORY")
        # ⚠ THE ROW, not the response — the response is what the screen shows.
        assert row.service_point_id is None
        # And the served view agrees, because it derives the service from that
        # point and there is none: the clerk's answer is simply gone.
        served = selectors.asset_detail(str(row.id))
        assert served["service"] is None, (
            "If this is no longer None, OQ-MET-1768 has been answered — update "
            "this file, the screen's sentence and DEF-MET-4986 together."
        )


def test_def_met_4986__the_same_answer_on_a_unit_is_kept(brazos, dana):
    """The other destination, so the pair shows the difference is the UNIT."""
    with tenant_ctx(brazos):
        premise = make_premises(dana, address_line="1408 Bluestem Ln")
        seat = make_unit(dana, premise["id"], label="Unit A", services=["water"])
        placed = make_asset(
            dana,
            asset_no="DEF4986-ASSIGNED",
            service="water",
            unit="kgal",
            size_class=None,
            unit_id=seat["id"],
            install_date="2026-09-12",
        )
        row = models.Asset.objects.get(tenant_id=brazos.id, asset_no="DEF4986-ASSIGNED")
        assert row.service_point_id is not None
        assert selectors.asset_detail(str(placed["id"]))["service"] == "water"


def test_def_met_4986__the_service_is_still_REQUIRED_and_still_CHECKED(brazos, dana):
    """The half that is not broken, asserted so a fix cannot 'solve' this by
    dropping the requirement — which would be the cheapest wrong answer."""
    from core import errors

    with tenant_ctx(brazos):
        with pytest.raises(errors.ApiError) as refused:
            make_asset(dana, asset_no="DEF4986-NOSVC", service=None, unit="kgal")
        assert any(
            entry.get("message_key") == "assets.service_required"
            for entry in (refused.value.field_errors or [])
        )
