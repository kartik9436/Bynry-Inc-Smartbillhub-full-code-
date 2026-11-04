# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-21, verbatim: *"you can generate meter, sub meter
#           or asset # and assigned it - but theya re not yet installed or
#           actiavted"*, and *"install date on work order completion - yes"*.
# Defects:  DEF-MET-6066 (a build's meter landed status `active`, label
#           *Installed*, behaviour `in_service`) · DEF-MET-6067 (`install_date`
#           stamped with TODAY at creation)
# Rules:    BR-AST-011 (assign-on-create → first assignment row + status
#           active) — NOT superseded; it governs the unit wizard, which is a
#           clerk recording a meter already on the wall · BR-AST-017 (the
#           assignment history is dated and append-only) · BR-AST-031 (a
#           stage's LABEL is never load-bearing) · BR-RAT-090 /
#           `billable_asset_count` (in-service is one of its three predicates)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**A BUILD GENERATES A NUMBER; IT DOES NOT FIT A METER.**

WHAT WAS MEASURED BEFORE A LINE WAS CHANGED, ON A REAL ROW
-----------------------------------------------------------
`create_asset_for_unit` called the way `commit_connection` calls it produced::

    asset_no       M-00001
    install_date   2026-09-20          <- the day of the commit
    status         active / Installed / in_service
    assignment     from_date 2026-09-20

So a build committed on Sunday said every one of its meters had been fitted on
Sunday, on a site nobody had visited. **The asset NUMBER is right** — the PO
ruled that a build may generate and assign one — and the other three are not.

⚠ **IT IS A MONEY CONSEQUENCE AS WELL AS A WORD.** `in_service` is one of
`billable_asset_count`'s three predicates, so an unfitted meter sat in the
population a per-meter or capacity service bills from.

WHY THIS COULD NOT BE SPLIT INTO TWO FIXES
-------------------------------------------
`_create_asset_inner` REFUSES `install_date is None` whenever a unit is named
(`assets.install_date_required`), so dropping the invented date alone makes
every build's meter refuse. The date and the stage move together or not at all.

WHAT IS DELIBERATELY NOT FIXED HERE, AND IT IS `DEF-MET-6066`'s SECOND HALF
----------------------------------------------------------------------------
**The stage vocabulary has no value meaning *assigned, but not installed*.**
The five seeded stages are `inventory · active · needs_repair · in_repair ·
retired`, and `inventory` is the nearest: its BEHAVIOUR is exactly right — not
in service, not billable — and its LABEL reads *Inventory* on a meter earmarked
for a flat. `BR-AST-031` exists so a label is never load-bearing, which is why
this is the right interim answer rather than a wrong one; a sixth stage is a
reference-data change with its own migration, transitions and fixture.

⚠ **THE UNIT ASSIGNMENT IS STILL WRITTEN AND ITS `from_date` IS NOT AN INSTALL
DATE.** `AssetAssignment.from_date` is NOT NULL and answers a different
question — *from when is this asset earmarked for this unit* — which is today,
truthfully. Dropping the assignment instead would leave a build's meters
floating in inventory with nothing tying them to the units they were made for.
"""

from __future__ import annotations

import pytest

from apps.assets import models as asset_models
from apps.assets import services as assets_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _unit(actor):
    premises = make_premises(actor, address_line="212 Balcones Drive")
    return make_unit(actor, premises["id"], label="Apt 1", unit_type="residential")


def _asset(made) -> asset_models.Asset:
    return asset_models.Asset.objects.get(id=made["id"])


# ═══════════════════════════════════════════════════════════════════════════
# 1 · WHAT A BUILD CREATES
# ═══════════════════════════════════════════════════════════════════════════
def test_a_builds_meter_gets_its_NUMBER_and_no_install_date(brazos, dana):
    """`DEF-MET-6067` — *"install date on work order completion - yes"*."""
    with tenant_ctx(brazos):
        unit = _unit(dana)
        made = assets_services.create_asset_for_unit(
            actor=dana,
            unit_id=unit["id"],
            service_point_id=None,
            payload={"type": "meter", "service": "electric", "asset_no": None},
            installed=False,
        )
        row = _asset(made)
        # ⚠ **THE POSITIVE ASSERTION COMES FIRST AND IT IS LOAD-BEARING.** The
        # ruling's first half is that a build MAY generate and assign a number,
        # so a fix that simply stopped creating the asset would satisfy every
        # absence below and break the thing the PO said was fine.
        assert row.asset_no, "the build must still allocate a meter number"
        assert row.install_date is None


def test_a_builds_meter_is_NOT_in_service_which_is_the_money_half(brazos, dana):
    """`DEF-MET-6066`. `in_service` is one of `billable_asset_count`'s three
    predicates, so this is what keeps an unfitted meter out of a bill."""
    with tenant_ctx(brazos):
        unit = _unit(dana)
        made = assets_services.create_asset_for_unit(
            actor=dana,
            unit_id=unit["id"],
            service_point_id=None,
            payload={"type": "meter", "service": "electric", "asset_no": None},
            installed=False,
        )
        row = _asset(made)
        # ⚠ **ASSERTED ON `behavior_class`, NEVER ON THE LABEL OR THE CODE.**
        # `BR-AST-031`: a stage's label is never load-bearing, and the day a
        # sixth stage lands (`DEF-MET-6066`'s second half) the CODE will move
        # and this guarantee must not.
        assert row.status.behavior_class != "in_service"


def test_the_unit_still_knows_which_meter_is_coming(brazos, dana):
    """The assignment is written, dated today, and it is NOT an install date.

    Dropping it would have been the easy way to satisfy the two cases above and
    would have lost the only link between a build's meters and its units."""
    with tenant_ctx(brazos):
        unit = _unit(dana)
        made = assets_services.create_asset_for_unit(
            actor=dana,
            unit_id=unit["id"],
            service_point_id=None,
            payload={"type": "meter", "service": "electric", "asset_no": None},
            installed=False,
        )
        assignment = asset_models.AssetAssignment.objects.get(asset_id=made["id"])
        assert str(assignment.unit_id) == str(unit["id"])
        assert assignment.from_date is not None
        assert assignment.to_date is None  # BR-AST-017 — the current row


# ═══════════════════════════════════════════════════════════════════════════
# 2 · WHAT THE UNIT WIZARD CREATES — BR-AST-011, UNTOUCHED
# ═══════════════════════════════════════════════════════════════════════════
def test_the_unit_wizards_meter_is_STILL_installed_on_creation(brazos, dana):
    """⚠ **THE FLAG DEFAULTS TO THE OLD BEHAVIOUR, AND THIS IS THE CASE THAT
    SAYS SO.** `BR-AST-011`'s assign-on-create is a clerk recording a meter
    that is already on the wall; the ruling is about a meter a BUILD creates
    before anybody has been to site. Without this case a lane could 'simplify'
    the flag away and take a signed rule with it."""
    with tenant_ctx(brazos):
        unit = _unit(dana)
        made = assets_services.create_asset_for_unit(
            actor=dana,
            unit_id=unit["id"],
            service_point_id=None,
            payload={"type": "meter", "service": "electric", "asset_no": None},
        )
        row = _asset(made)
        assert row.install_date is not None
        assert row.status.behavior_class == "in_service"


def test_an_installed_asset_with_no_date_is_STILL_refused_by_name(brazos, dana):
    """`BR-AST-011`'s own refusal, proved still live.

    ⚠ **THIS IS THE CASE THAT STOPS THE FIX BECOMING A HOLE.** The change
    relaxes `assets.install_date_required` — and relaxes it ONLY under
    `installed=False`. A relaxation that leaked would let any caller assign a
    meter to a unit with no install date at all."""
    with tenant_ctx(brazos):
        unit = _unit(dana)
        with pytest.raises(errors.ValidationError) as caught:
            assets_services.create_asset(
                dana,
                {
                    "type": "meter",
                    "service": "electric",
                    "unit_id": unit["id"],
                    "install_date": None,
                },
            )
        assert "install_date" in str(caught.value)
