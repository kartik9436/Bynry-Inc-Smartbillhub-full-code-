# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 step 2 wave F — R7 / `ACC-S17`, the **Accounts** tab
#           on a master account's detail screen. Drawing: `05-prototype/
#           02 Accounts Menu Blueprint.pdf` p189–192, pinned at `033981d4f`.
# Rule:     BR-CUS-1048 (this tab, PO 2026-09-12) · BR-CUS-068 (a master
#           account IS an ordinary `accounts` row, `kind='master'`) ·
#           BR-CUS-1010 (it hangs off the ADDRESS — `premises_id` set,
#           `unit_id` null) · B14 rule 31 (no database id on screen)
# Impacts:  apps/customers/selectors.account_detail_dict (`covered_units`)
# ───────────────────────────────────────────────────────
"""`covered_units` — the one field the Accounts tab could not derive.

The blueprint draws the master's own row with its UNIT cell reading *Common
areas ×2*, and names the source in its own table: *"A real, direct linkage —
this account's own open service agreements … `covered_unit_ids(account)`"*. A
master names NO unit (`BR-CUS-1010`), so `unit_label` is null on its row and
the one cell the tab exists to explain had nothing at all to render.

**PROVED RED (hard-won law 7), in the harness that runs it and against a tree
that does not carry the change** — a detached `git worktree` at the branch tip
`c9d4a1bea`, where `covered_units` appears nowhere in `selectors.py`, with this
file copied in:

    $ JOBS_EAGER=false python -m pytest tests/test_cr094_r7_master_accounts_tab.py \\
        -p no:randomly -q
    >           assert detail["covered_units"] == 2
    E           KeyError: 'covered_units'
    >           assert detail["covered_units"] is None
    E           KeyError: 'covered_units'
    2 failed, 4 warnings in 282.45s

⚠ **THE RED WAS TAKEN IN A WORKTREE RATHER THAN BY REVERTING THE SHARED ONE**,
and that is the point worth keeping: five other lanes were reading
`apps/customers/` at the time, and a four-minute window with the field taken out
would have been a revert they could not see (law 11's mechanism two). A red
proof must not cost somebody else's tree.

⚠ **`None` FOR AN ORDINARY ACCOUNT, NEVER `0` OR `1`.** An ordinary account's
coverage is its own unit and the question is not asked of it, so the tab that
reads this field does not exist on its screen. A `0` would read as *this
account covers nothing*, which is a claim; a `1` would invite a second screen
to print *Common areas ×1* over a flat.
"""

from datetime import date

import pytest

from apps.customers import models as customer_models
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services
from apps.metering import services as metering_services

from tests.br_cus_1114_fixtures import top_up_homes
from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

OPENED = date(2026, 8, 1)


def _plan(tenant):
    return make_plan(tenant, name="Small Commercial", services=["electric"])


def _premises(actor):
    return make_premises(
        actor,
        address_line="1408 Elm Street",
        premises_type="apartment_complex",
        owner_manager="Elm Street Holdings LLC",
        services_available=["electric", "water"],
    )


def _common_area(actor, premises, plan, *, label):
    unit = make_unit(
        actor,
        premises["id"],
        label=label,
        unit_type="common_area",
        is_common_area=True,
        services=["electric"],
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    return unit


def _ordinary_unit(actor, premises, plan, *, label):
    unit = make_unit(actor, premises["id"], label=label, services=["electric"])
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    return unit


def _master(actor, premises):
    # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
    top_up_homes(actor, premises["id"])
    return customer_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": OPENED.isoformat(),
            "customer": identity_fixtures.customer_block(
                premises.get("owner_manager") or "Owner", kind="company"
            ),
        },
    )


def test_cr094_r7_tc1__a_master_serves_the_count_of_units_its_agreements_reach(brazos, dana):
    """**TWO common areas ⇒ `covered_units: 2`** — BR-MET-101's own building.

    The count is `covered_unit_ids`, which is what billing prices, so the cell
    on screen and the units on the owner's bill cannot disagree. `$41.20`
    hallway lighting + `$28.40` shared irrigation = the signed `$69.60`; what
    those units add up to belongs on the account's **Bills** tab and the
    blueprint says so, which is why this is a COUNT and not money.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        _common_area(dana, premises, plan, label="Hallway & exterior lighting")
        _common_area(dana, premises, plan, label="Shared irrigation")
        master = customer_models.Account.objects.get(pk=_master(dana, premises)["id"])

        detail = customer_selectors.account_detail_dict(master)
        assert detail["covered_units"] == 2
        # …and it is a COUNT, never ids: B14 rule 31 keeps a database key off
        # the screen, and nothing on this tab needs one.
        assert isinstance(detail["covered_units"], int)
        # The master names no unit at all, which is WHY the cell needs this.
        assert detail["unit_label"] is None
        assert detail["kind"] == "master"


def test_cr094_r7_tc2__an_ordinary_account_serves_none_and_not_a_number(brazos, dana):
    """An ordinary account answers `None` — the question is not asked of it."""
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        unit = _ordinary_unit(dana, premises, plan, label="Unit A")
        created = customer_services.create_account(
            dana,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "opened_at": OPENED.isoformat(),
                "contact": {"full_name": "Ncube, T."},
                "customer": identity_fixtures.customer_block(
                    "Ncube, T.", account_type="residential"
                ),
            },
        )
        account = customer_models.Account.objects.get(pk=created["id"])

        detail = customer_selectors.account_detail_dict(account)
        assert detail["covered_units"] is None
        assert detail["kind"] == "regular"
