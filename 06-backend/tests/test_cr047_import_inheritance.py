# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-019 (the S68 bulk account import) · US-CUS-003 (S18 create,
#           whose behaviour this change must NOT move) · US-CUS-004 (S19
#           move-in, likewise)   Screens: S68 · S18 · S19 · S21
# Change:   CR-047 (customers lane) — `DEF-2518`
# Defect:   DEF-2518 (high, 2026-08-29) — an imported row whose Status cell is
#           EMPTY became a `pending_activation` account, `_open_service_agreements`
#           sat inside `_make_occupying`, and so the account was written with NO
#           service agreements: no service, no route, no cycle, no plan, no
#           meter. The receipt counted it under "created" beside the good ones.
# Rules:    PO ruling 2026-08-29, verbatim: *"if account is created then we need
#           to inherit details form units - otherwise upadling it later will be
#           big tasks"* · BR-CUS-029 (the account DERIVES its plan from the unit
#           — nothing is copied, everything is a foreign key) · BR-CUS-017 (one
#           LIVE account per unit) · BR-CUS-018 (a draft never blocks the unit)
#           · BR-CUS-022 (billing starts at the service start date) ·
#           BR-CUS-056 (the prior move day) · BR-MET-040 (a plan is REQUIRED at
#           ACTIVATION) · BR-TEN-043 (the caller names the event date; this
#           kernel never reads a clock on their behalf)
# Tests:    this file
# Impacts:  apps/customers/services.py (`_occupancy_guards`, `_make_occupying`,
#           `_inherit_service_links`, `_open_account`, `create_from_import`) ·
#           apps/metering/import_runs.py reads the new `services_linked` key
#           off the seam's return (lane 1) · the S68 receipt renders it (lane 3)
# ───────────────────────────────────────────────────────
"""CR-047 · DEF-2518 — an imported account inherits its unit's services
WHATEVER its status, and the plan is required at ACTIVATION rather than at
creation.

WHAT EACH TEST PROVES, AND WHY IT IS THE THING WORTH PROVING
------------------------------------------------------------
The reference chain is a chain of FOREIGN KEYS and stays exactly as it is —
`accounts` → `service_agreements(service_point_id)` → `service_points(unit_id,
service_id, route_id, cycle_id)` → `units(rate_plan_id)`. Nothing here copies a
plan onto an account; BR-CUS-029 forbids it. What was missing was the FIRST
link: without a `service_agreements` row the whole chain is unreachable from the
account, which is what made an imported draft an account attached to nothing.

  * TC-1 — the RED one. A row with a BLANK Status cell gets its service
    agreements. Before the fix this asserts 0 and fails.
  * TC-2 — `services_linked` is on the seam's return, for lane 1's counters.
  * TC-3 — BR-CUS-018 still holds: a draft does not take the occupancy guards,
    so it may be imported onto a unit a LIVE account already occupies — and it
    still gets its links. This is the half that must NOT become a guard.
  * TC-4 — `started_on`: the row's own `opened_at` when it has one, the RUN's
    cutover/changeover date when it does not. No clock is read (BR-TEN-043).
  * TC-5 — the fail-closed half of TC-4: no `opened_at` AND no `cutover_on`
    refuses rather than inventing a date.
  * TC-6 — Task 11. A plan-less unit no longer blocks the IMPORT door, for a
    draft row and for an `active` row alike.
  * TC-7 — and it still blocks ACTIVATION, which is what BR-MET-040 actually
    says. This is the guard that must survive the move.
  * TC-8 — the S18 door is UNCHANGED: an occupying create on a plan-less unit
    still refuses, and an S18 draft still writes no agreements.
  * TC-9 — the billing backstop, proved rather than claimed (law 1): a draft is
    not in `accounts_for_bill_run` at all, and an account whose unit has no plan
    is refused by `gather.gather_account` with `GATHER_NO_PLAN`.
"""

from datetime import date

import pytest

from apps.billing import gather
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx
from tests.test_us_met_helpers import (  # noqa: F401 — brazos/dana are fixtures
    brazos,
    dana,
    make_premises,
    make_unit,
)

pytestmark = pytest.mark.django_db

CUTOVER = date(2026, 8, 31)


# ══════════════════════════════════════════════════════════════════════════
# Fixture plumbing — built through the REAL service of the module that owns
# each row, never an ORM shortcut across a boundary.
# ══════════════════════════════════════════════════════════════════════════
def _plan(tenant, name="Residential Standard", service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _unit(actor, tenant, *, label="Unit A", services=("electric", "water"), with_plan=True):
    """A vacant unit with one service point per service. `with_plan=False` is
    the migration's day-one state: the estate is on file and the plans are not
    assigned yet."""
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"], label=label)
    if with_plan:
        metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    for code in services:
        metering_services.ensure_service_point(unit["id"], code)
    return unit


def _import_payload(unit_id, *, account_no, account=None, cutover_on=CUTOVER, mapped=None):
    """What `apps.metering.import_runs` hands the seam for ONE judged row."""
    return {
        "mapped": mapped if mapped is not None else {},
        "unit_id": str(unit_id),
        "account_no": account_no,
        "currency": "USD",
        "cutover_on": cutover_on,
        "import_run_id": None,
        "account": account if account is not None else {"account_type": "residential"},
    }


def _agreements(account_id):
    return list(
        customers_models.ServiceAgreement.objects.filter(account_id=account_id).order_by(
            "started_on", "id"
        )
    )


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · the RED one — a BLANK Status cell still inherits the unit's services
# ══════════════════════════════════════════════════════════════════════════
def test_cr047_tc1__blank_status_import_row_still_gets_its_service_agreements(brazos, dana):
    """DEF-2518. The Status column is OPTIONAL in the published template and its
    rule only warns on an UNKNOWN value, never an absent one — so this row is
    the ordinary case, not an edge case."""
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos)
        # No "status" key at all — exactly what `_account_payload_from` produces
        # for a row whose Status cell is empty (it drops None/"" values).
        result = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                unit["id"],
                account_no="A-40001",
                account={"account_type": "residential", "opened_at": "2026-08-15"},
            ),
        )
        account = customers_models.Account.objects.get(pk=result["id"])

        # It IS the draft — this test is not about changing the status.
        assert account.status.code == customers_services.PENDING_STATUS_CODE
        assert account.status.behavior_class == customers_services.CLASS_NON_BILLABLE

        rows = _agreements(account.id)
        assert len(rows) == 2, "the unit's two service points must each have an agreement"
        point_ids = {str(row.service_point_id) for row in rows}
        expected = {
            str(point["id"]) for point in customers_services.seams.service_points_for(unit["id"])
        }
        assert point_ids == expected


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · the cross-lane contract — `services_linked` on the seam's return
# ══════════════════════════════════════════════════════════════════════════
def test_cr047_tc2__services_linked_is_returned_for_lane_1s_counters(brazos, dana):
    with tenant_ctx(brazos):
        draft_unit = _unit(dana, brazos, label="Unit A")
        live_unit = _unit(dana, brazos, label="Unit B")

        draft = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                draft_unit["id"],
                account_no="A-40002",
                account={"account_type": "residential", "opened_at": "2026-08-15"},
            ),
        )
        live = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                live_unit["id"],
                account_no="A-40003",
                account={
                    "account_type": "residential",
                    "opened_at": "2026-08-15",
                    "status": "active",
                },
            ),
        )

        # Both doors report the same fact the same way — an occupying row has
        # always written these links and now says how many.
        assert draft["services_linked"] == 2
        assert live["services_linked"] == 2
        assert draft["services_linked"] == len(_agreements(draft["id"]))

        # Nothing else in the shape moved (the contract lane 1 is built against).
        # ⚠ `customer_not_created` JOINED 2026-09-01 (`BR-CUS-1023`): a name
        # alone no longer mints a Customer number, so `customer_no` is now
        # usually None on this path and this key is WHY. It is additive — every
        # key lane 1 built against is still here — and it exists because a
        # blank number with no sentence beside it is the state CR-056 §4
        # measured (hard-won law 2).
        # ⚠ `customer_created` and `customer_no_from_file` JOINED 2026-09-01
        # (`CR-058` W7 / `BR-CUS-1041` / `DEF-2593`): the receipt has to tell a
        # utility how many customers this file BROUGHT IN and how many it joined
        # to people already on file, and the runner has to know when a customer
        # number came off the file so it can walk the series past it. Additive
        # again — every key lane 1 built against is still here.
        assert set(draft) == {
            "id",
            "account_no",
            "customer_no",
            "customer_not_created",
            "customer_created",
            "customer_no_from_file",
            "opening_total",
            "opening_empty",
            "deposit_on_file",
            "deposit_received_on",
            "services_linked",
        }


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · BR-CUS-018 — inheritance is NOT an occupancy guard
# ══════════════════════════════════════════════════════════════════════════
def test_cr047_tc3__a_draft_import_row_does_not_take_the_occupancy_guards(brazos, dana):
    """BR-CUS-018 is explicit: a draft "never derives occupancy and does not
    block the unit for other move-ins". So importing a draft onto a unit a LIVE
    account already holds must NOT hit BR-CUS-017 — and must still inherit.

    This is the half that would break if the split were done by moving the
    guards rather than by separating them from the inheritance."""
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos)
        live = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                unit["id"],
                account_no="A-40010",
                account={
                    "account_type": "residential",
                    "opened_at": "2026-08-15",
                    "status": "active",
                },
            ),
        )
        draft = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                unit["id"],
                account_no="A-40011",
                account={"account_type": "residential", "opened_at": "2026-08-16"},
            ),
        )
        assert draft["services_linked"] == 2
        assert len(_agreements(draft["id"])) == 2
        # And the live account keeps its own — the two sets of rows coexist,
        # which the schema permits: `service_agreements` has no unique key on
        # (tenant, service_point), only an index.
        assert len(_agreements(live["id"])) == 2


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · what `started_on` a non-occupying account's agreement gets
# ══════════════════════════════════════════════════════════════════════════
def test_cr047_tc4__started_on_is_opened_at_then_the_runs_cutover_date(brazos, dana):
    """BR-TEN-043 — the CALLER names the business event's date and this module
    never reads a clock on their behalf. The row's own `opened_at` is that date
    when the file carried one; when it did not, the RUN's cutover/changeover
    date is the only date in play and it is the same date the opening buckets
    are struck at."""
    with tenant_ctx(brazos):
        dated_unit = _unit(dana, brazos, label="Unit A")
        undated_unit = _unit(dana, brazos, label="Unit B")

        dated = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                dated_unit["id"],
                account_no="A-40020",
                account={"account_type": "residential", "opened_at": "2026-07-01"},
            ),
        )
        undated = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                undated_unit["id"],
                account_no="A-40021",
                account={"account_type": "residential"},
            ),
        )

        assert {row.started_on for row in _agreements(dated["id"])} == {date(2026, 7, 1)}
        assert {row.started_on for row in _agreements(undated["id"])} == {CUTOVER}
        # And the account's own `opened_at` is NOT invented to match: the file
        # did not say when service started, so the column stays empty.
        assert customers_models.Account.objects.get(pk=undated["id"]).opened_at is None


def test_cr047_tc5__no_opened_at_and_no_cutover_refuses_rather_than_guessing(brazos, dana):
    """Fail closed (hard-won law 3). The runner always resolves a changeover
    date — a provisional one when the operator gave none — so this state is not
    reachable from S68 today; a fourth caller that skipped it would otherwise
    get a silently clock-derived date, which is exactly what BR-TEN-043
    forbids."""
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos)
        with pytest.raises(errors.BizError) as raised:
            customers_services.create_from_import(
                actor=dana,
                payload=_import_payload(
                    unit["id"],
                    account_no="A-40030",
                    account={"account_type": "residential"},
                    cutover_on=None,
                ),
            )
        assert raised.value.br_ref and "BR-TEN-043" in raised.value.br_ref
        # The sentence is the one the operator already sees when a run has no
        # changeover date (G32 — a raised key must resolve to a customer
        # sentence, and the locale catalogues are lane 3's file, not this one's).
        assert raised.value.message_key == "customers.import.cutover_required"
        assert customers_models.Account.objects.filter(account_no="A-40030").count() == 0


def test_cr047_tc5b__a_migrated_closed_account_inherits_its_services_CLOSED(brazos, dana):
    """B2 §2 declares `service_agreements.ended_on` as *"NULL = still in
    force"*, and `selectors.service_codes_for` reads exactly that column to
    badge S17's service chips. So a migration's CLOSED accounts get their links
    — the ruling asks for them and a final-bill reprint needs them — dated
    closed, through the same `_end_service_agreements` a real move-out uses.
    Writing them OPEN would state in the database that a finished tenancy is
    current."""
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos)
        closed = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                unit["id"],
                account_no="A-40035",
                account={
                    "account_type": "residential",
                    "status": "closed",
                    "opened_at": "2024-03-01",
                    "closed_at": "2026-06-30",
                },
            ),
        )
        rows = _agreements(closed["id"])
        assert closed["services_linked"] == 2
        assert {row.started_on for row in rows} == {date(2024, 3, 1)}
        assert {row.ended_on for row in rows} == {date(2026, 6, 30)}

        # And the S17 chips read empty, which is what a closed tenancy means.
        account = customers_models.Account.objects.get(pk=closed["id"])
        assert customers_selectors.service_codes_for(account) == []


# ══════════════════════════════════════════════════════════════════════════
# TC-6/7 · Task 11 — BR-MET-040 fires at ACTIVATION, not at creation
# ══════════════════════════════════════════════════════════════════════════
def test_cr047_tc6__a_unit_without_a_plan_no_longer_blocks_the_import_door(brazos, dana):
    """BR-MET-040's own text is *"Plan is REQUIRED at account activation"*. A
    migration loads accounts on day one and assigns plans on day two; the plan
    is a REFERENCE (BR-CUS-029), so the day it appears on the unit every account
    under it has it, with nothing to backfill."""
    with tenant_ctx(brazos):
        draft_unit = _unit(dana, brazos, label="Unit A", with_plan=False)
        active_unit = _unit(dana, brazos, label="Unit B", with_plan=False)

        draft = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                draft_unit["id"],
                account_no="A-40040",
                account={"account_type": "residential", "opened_at": "2026-08-15"},
            ),
        )
        active = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                active_unit["id"],
                account_no="A-40041",
                account={
                    "account_type": "residential",
                    "opened_at": "2026-08-15",
                    "status": "active",
                },
            ),
        )
        assert draft["services_linked"] == 2
        assert active["services_linked"] == 2


def test_cr047_tc7__activation_still_refuses_a_unit_without_a_plan(brazos, dana):
    """The guard that must survive the move (law 7's other half: prove the thing
    you kept is still there)."""
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos, with_plan=False)
        created = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                unit["id"],
                account_no="A-40050",
                account={"account_type": "residential", "opened_at": "2026-08-15"},
            ),
        )
        with pytest.raises(errors.BizError) as raised:
            customers_services.activate_account(dana, created["id"])
        assert raised.value.br_ref == "BR-MET-040"

        # And the same account activates once the plan is on the unit — the
        # reference chain, doing what BR-CUS-029 says it does.
        metering_services.assign_unit_plan(dana, unit["id"], {"tariff_id": str(_plan(brazos).id)})
        activated = customers_services.activate_account(dana, created["id"])
        assert activated["status"] == "active"


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · the S18 door is UNCHANGED (this ruling is about the migration)
# ══════════════════════════════════════════════════════════════════════════
def test_cr047_tc8__the_s18_create_door_is_unchanged(brazos, dana):
    with tenant_ctx(brazos):
        # (a) an occupying S18 create on a plan-less unit still refuses.
        bare = _unit(dana, brazos, label="Unit A", with_plan=False)
        with pytest.raises(errors.BizError) as raised:
            customers_services.create_account(
                dana,
                {
                    "unit_id": str(bare["id"]),
                    "account_type": "residential",
                    "opened_at": "2026-08-15",
                    "status": "active",
                },
            )
        assert raised.value.br_ref == "BR-MET-040"

        # (b) an S18 DRAFT still writes no service agreements. The ruling names
        # the import door; widening it to S18 is a decision for the PO and is
        # REPORTED rather than taken here.
        planned = _unit(dana, brazos, label="Unit B")
        draft = customers_services.create_account(
            dana,
            {
                "unit_id": str(planned["id"]),
                "account_type": "residential",
                "opened_at": "2026-08-15",
            },
        )
        assert _agreements(draft["id"]) == []


# ══════════════════════════════════════════════════════════════════════════
# TC-9 · the billing backstop, PROVED (law 1 — a comment is not a guarantee)
# ══════════════════════════════════════════════════════════════════════════
def test_cr047_tc9__a_draft_is_out_of_the_run_and_a_planless_unit_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos, with_plan=False)
        draft = customers_services.create_from_import(
            actor=dana,
            payload=_import_payload(
                unit["id"],
                account_no="A-40060",
                account={"account_type": "residential", "opened_at": "2026-08-15"},
            ),
        )
        # (a) the run does not select it at all — `accounts_for_bill_run`
        # filters on OCCUPYING_BEHAVIOR_CLASSES, so a draft's agreements are
        # read by nothing until its status changes.
        scoped = list(customers_selectors.accounts_for_bill_run([str(unit["id"])]))
        assert [row.account_no for row in scoped] == []

        # (b) and were it selected, the plan-less unit is refused by name.
        account = customers_models.Account.objects.get(pk=draft["id"])
        with pytest.raises(gather.GatherProblem) as raised:
            gather.gather_account(
                account=account,
                service_date=date(2026, 9, 1),
                period_start=date(2026, 8, 1),
                period_end=date(2026, 8, 31),
                cycle_days=31,
            )
        assert raised.value.reason == gather.GATHER_NO_PLAN
