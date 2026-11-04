# ── Trace ──────────────────────────────────────────────
# Change:   `BR-CUS-1094` (PO 2026-09-23) — the master account's **Units** tab.
#           PO verbatim: *"show all units with its status what wil be billed to
#           master account - can we do that?"*
# Rule:     BR-CUS-1094 (a vacant unit's bill goes to the premises' master
#           account; an occupied one's to its own tenant; **decided when the
#           bill run starts, NOT STORED**) · BR-CUS-170 (the owner's bill
#           carries every unit nobody else pays for) · BR-CUS-068 (a master
#           account IS an ordinary `accounts` row with `kind='master'`) ·
#           BR-CUS-1010 (it hangs off the ADDRESS) · BR-MET-036 (occupancy is
#           DERIVED from the active account — `units` has no such column) ·
#           BR-CUS-055 (occupying keys off the status BEHAVIOUR CLASS) ·
#           BR-CUS-1040 (no per-unit PRICE is stated outside a bill run)
# Impacts:  apps/customers/selectors.master_unit_billing_page ·
#           apps/customers/api.account_units
# ───────────────────────────────────────────────────────
"""**Who pays for each unit in this building, decided now and stored nowhere.**

PROVED RED (hard-won law 7), in the harness that runs it, against a detached
`git worktree` at the branch tip `726efa7f3` — where `master_unit_billing_page`
appears nowhere — with this file copied in. The failure and the command are
quoted in the Lifecycle block at the foot of this file.

⚠ **THE RED WAS TAKEN IN A WORKTREE AND NOT BY REVERTING THE SHARED TREE**
(law 11's mechanism two), for the same reason `test_cr094_r7_master_accounts_tab`
records: other lanes were reading `apps/customers/` at the time.

⚠ **WHAT THIS FILE IS REALLY GUARDING IS THE PROHIBITION, NOT THE PAYLOAD.**
`BR-CUS-1094`'s load-bearing clause is that no column may cache which units a
master pays for. A cached answer is wrong the first time a tenant moves in and
**nothing would go red** — so `tc5` moves a tenant in and asserts the answer
moves with them, in the same process, with nothing re-seeded and nothing
invalidated. That is the test the rule asks for; the rest of this file is the
screen.
"""

from datetime import date

import pytest

from apps.customers import models as customer_models
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from core.pagination import ListParams

from tests import identity_fixtures
from tests.br_cus_1114_fixtures import top_up_homes
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

OPENED = date(2026, 8, 1)


def _params(**over):
    """The endpoint's own defaults, so a test asks what a screen asks."""
    base = {
        "q": "",
        "sort": customer_selectors.MASTER_UNIT_DEFAULT_SORT,
        "dir": customer_selectors.MASTER_UNIT_DEFAULT_DIR,
        "page": 1,
        "per": 50,
        "filters": {},
    }
    base.update(over)
    return ListParams(**base)


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


def _flat(actor, premises, plan=None, *, label):
    """A dwelling. **A plan is OPTIONAL on purpose** — a vacant unit with no
    plan is billed NOTHING by `gather._unbilled_unit_tariffs`, which skips the
    coverage entry outright on `not has_plan`, and `tc4` is that case.
    """
    unit = make_unit(actor, premises["id"], label=label, services=["electric"])
    if plan is not None:
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


def _tenant_account(actor, unit, *, name, activate=True):
    """A tenant on a unit.

    ⚠ **`activate` IS NOT A CONVENIENCE AND THE DEFAULT IS NOT COSMETIC.**
    `create_account` leaves the row in `pending_activation`, whose behaviour
    class is `non_billable` — and `occupying_accounts_for_unit` is explicit
    that such a row **does not occupy** (`BR-CUS-018`, CONFIRMED: a
    draft/pending account *"never derives occupancy and does not block the unit
    for other move-ins"*).

    So a unit whose only account is pending is **VACANT** for every purpose on
    this tab, and its bill goes to the master. That is the ruling, not a gap —
    and `tc11` is the case that says so out loud, because it is the answer a
    clerk is most likely to be surprised by.

    ⚠ **THIS LANE'S FIRST DRAFT MISSED IT AND THE SUITE CAUGHT IT**, reporting
    every occupied unit as vacant. Worth recording: the fixture was wrong and
    the product was right, which is the direction that usually gets "fixed"
    the wrong way round.
    """
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": OPENED.isoformat(),
            "contact": {"full_name": name},
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )
    if activate:
        customer_services.activate_account(actor, created["id"])
    return created


def _by_label(rows):
    return {row["label"]: row for row in rows}


def test_br_cus_1094_tc1__every_unit_is_listed_occupied_and_vacant_alike(brazos, dana):
    """**The PO's own question: show ALL units, with status.**

    The existing `Accounts` tab (`BR-CUS-1048`) lists units that HAVE a tenant.
    This is the other half and it is why the rule was raised: a vacant unit has
    no account, so it appears on no accounts list anywhere, and the building's
    vacancy picture was invisible from the owner's screen.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        _common_area(dana, premises, plan, label="Hallway lighting")
        occupied = _flat(dana, premises, plan, label="Unit A")
        _flat(dana, premises, plan, label="Unit B")  # vacant
        _tenant_account(dana, occupied, name="Alvarez, M.")
        master = _master(dana, premises)

        rows, total, counts = customer_selectors.master_unit_billing_page(
            master["id"], _params()
        )

        assert total == 3
        assert counts == {
            "units": 3,
            "occupied": 1,
            "vacant": 2,  # the empty flat AND the hallway — nobody lives in either
            "billed_here": 2,  # the hallway (agreement) + the empty flat (rule)
            "billed_nobody": 0,
        }
        assert sorted(row["label"] for row in rows) == [
            "Hallway lighting",
            "Unit A",
            "Unit B",
        ]


def test_br_cus_1094_tc2__an_occupied_unit_is_billed_to_its_own_tenant(brazos, dana):
    """**The tenant half does not move** — `BR-CUS-1094` adds a payer for units
    that have none, it does not re-route anybody. The row names the tenant's
    own account number, which is what a clerk rings about.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        unit = _flat(dana, premises, plan, label="Unit A")
        tenant_account = _tenant_account(dana, unit, name="Alvarez, M.")
        master = _master(dana, premises)

        rows, _total, _counts = customer_selectors.master_unit_billing_page(
            master["id"], _params()
        )
        row = _by_label(rows)["Unit A"]

        assert row["occupancy"] == "occupied"
        assert row["payer"] == customer_selectors.UNIT_PAYER_TENANT
        assert row["account_no"] == tenant_account["account_no"]
        assert row["not_charged"] is None


def test_br_cus_1094_tc3__a_vacant_unit_is_billed_to_this_master(brazos, dana):
    """**The ruling itself**, and the answer comes from the SAME function the
    bill run uses (`base_charge_only_coverage`), never from a second derivation.

    The common area is billed here too, and for a DIFFERENT reason that the row
    states: an agreement somebody wrote (`BR-CUS-068`) rather than a rule that
    stops applying the day a tenant moves in.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        _common_area(dana, premises, plan, label="Hallway lighting")
        _flat(dana, premises, plan, label="Unit B")
        master = _master(dana, premises)

        rows, _total, _counts = customer_selectors.master_unit_billing_page(
            master["id"], _params()
        )
        by_label = _by_label(rows)

        empty = by_label["Unit B"]
        assert empty["occupancy"] == "vacant"
        assert empty["payer"] == customer_selectors.UNIT_PAYER_THIS_ACCOUNT
        assert empty["payer_basis"] == customer_selectors.UNIT_BASIS_VACANT
        assert empty["not_charged"] is None

        hallway = by_label["Hallway lighting"]
        assert hallway["payer"] == customer_selectors.UNIT_PAYER_THIS_ACCOUNT
        assert hallway["payer_basis"] == customer_selectors.UNIT_BASIS_AGREEMENT

        # ⚠ **THE TWO SETS ARE DISJOINT BY CONSTRUCTION AND THIS ASSERTS IT.**
        # `runs._billed_units` depends on that property; a screen that double
        # counted would print a unit twice on the tab a clerk acts on.
        assert len({row["label"] for row in rows}) == len(rows)


def test_br_cus_1094_tc4__a_vacant_unit_with_no_plan_says_it_is_not_charged(brazos, dana):
    """**A payer alone would be a promise the run does not keep.**

    `gather._unbilled_unit_tariffs` skips a coverage entry outright on
    `not has_plan` — *"an unplanned EMPTY unit has no base charge to omit and
    nobody to send one to"* — so a row reading only *billed to this account*
    would be false. `BR-CUS-1094`'s own clause: **the refusal names the UNIT,
    not a count.** The reason is read from billing's own coverage entry.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        _flat(dana, premises, plan, label="Unit A")  # planned, vacant → charged
        _flat(dana, premises, None, label="Unit Z")  # NO plan, vacant → nothing
        master = _master(dana, premises)

        rows, _total, _counts = customer_selectors.master_unit_billing_page(
            master["id"], _params()
        )
        by_label = _by_label(rows)

        assert by_label["Unit A"]["not_charged"] is None
        unplanned = by_label["Unit Z"]
        assert unplanned["payer"] == customer_selectors.UNIT_PAYER_THIS_ACCOUNT
        assert unplanned["not_charged"] == customer_selectors.UNIT_NOT_CHARGED_NO_PLAN


def test_br_cus_1094_tc5__the_answer_moves_when_a_tenant_moves_in(brazos, dana):
    """⚠ **THE PROHIBITION, AND THE ONLY TEST IN THIS FILE THAT COULD NOT BE
    WRITTEN IF THE ANSWER WERE STORED.**

    `BR-CUS-1094`: *"every month this is dynamic siaution and hence unit and
    account valid for billing are decied at the time of billing start only"* —
    and, in the rule's own words, *"a cached answer is wrong the first time a
    tenant moves in and nothing would go red"*.

    So: read the building, move a tenant in, read it again **in the same
    process**, with nothing re-seeded and no cache invalidated. The unit must
    change hands. A column caching the split would keep the first answer and
    this assertion is what would catch it.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        unit = _flat(dana, premises, plan, label="Unit B")
        # `BR-CUS-1114` (PO 2026-10-02) — a master needs two homes; the second is
        # LET, so the vacant counts below are still Unit B's alone.
        _tenant_account(dana, _flat(dana, premises, plan, label="Unit A"), name="Neighbour, N.")
        master = _master(dana, premises)

        before, _t, counts_before = customer_selectors.master_unit_billing_page(
            master["id"], _params()
        )
        assert _by_label(before)["Unit B"]["payer"] == (
            customer_selectors.UNIT_PAYER_THIS_ACCOUNT
        )
        assert counts_before["vacant"] == 1
        assert counts_before["billed_here"] == 1

        tenant_account = _tenant_account(dana, unit, name="Okafor, T.")

        after, _t2, counts_after = customer_selectors.master_unit_billing_page(
            master["id"], _params()
        )
        row = _by_label(after)["Unit B"]
        assert row["payer"] == customer_selectors.UNIT_PAYER_TENANT
        assert row["account_no"] == tenant_account["account_no"]
        assert row["occupancy"] == "occupied"
        assert counts_after["vacant"] == 0
        assert counts_after["billed_here"] == 0


def test_br_cus_1094_tc6__the_two_occupancy_reads_agree(brazos, dana):
    """**Metering's derived occupancy and this read's must never disagree.**

    Metering asks `active_account_for_unit`; this read asks
    `occupying_accounts_for_unit`, which is the one `base_charge_only_coverage`
    and the bill run use. Both key off `BR-CUS-055`'s behaviour class, so they
    must give one answer — and if they ever stop, one row on this tab would say
    *vacant* in its status pill and *billed to the tenant* beside it.

    This is the assertion that goes red on that, and it is here rather than in
    a docstring because hard-won law 1 says a comment claiming a guarantee is
    not the guarantee.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        occupied = _flat(dana, premises, plan, label="Unit A")
        _flat(dana, premises, plan, label="Unit B")
        _common_area(dana, premises, plan, label="Hallway lighting")
        _tenant_account(dana, occupied, name="Vance, R.")
        master = _master(dana, premises)

        rows, _total, _counts = customer_selectors.master_unit_billing_page(
            master["id"], _params()
        )

        assert rows, "the building has units"
        for row in rows:
            assert row["metering_occupancy"] == row["occupancy"], row["label"]
            # And the metering half really did arrive — an absent overlay would
            # make the loop above vacuously true for every row (law 7's
            # *incapable of failing* shape).
            assert "status" in row, row["label"]


def test_br_cus_1094_tc7__no_column_stores_the_split(brazos, dana):
    """⚠ **THE PROHIBITION ASKED OF THE SCHEMA RATHER THAN OF THE ANSWER.**

    `tc5` proves the answer is live today. This proves nobody can make it stale
    tomorrow by adding the obvious column: `units` carries no occupancy and no
    stored status (`BR-MET-036`), and `accounts` carries no list of units it
    pays for.

    A lane adding either would be doing the reasonable thing — caching a read
    that walks a building — and this is what tells them it is ruled out.

    ⚠ **THIS IS THE ONE CASE IN THIS FILE THAT PASSED AT THE TIP, AND IT COULD
    NOT HAVE DONE OTHERWISE.** An absence is true before the change and after
    it, so law 7's *prove it red first* has nothing to offer here — and saying
    so is the point: **what would make this pass wrongly is nothing, and what
    would make it fail is the exact future edit it exists to catch.** It is a
    tripwire, not a proof, and a reader who mistook it for one would be
    counting a check that cannot fail today among the ones that can.
    """
    unit_columns = {field.name for field in metering_selectors.models.Unit._meta.get_fields()}
    for forbidden in ("occupancy", "occupancy_status", "status", "billed_to", "payer"):
        assert forbidden not in unit_columns, forbidden

    account_columns = {field.name for field in customer_models.Account._meta.get_fields()}
    for forbidden in ("covered_units", "vacant_units", "billed_unit_ids", "paid_unit_ids"):
        assert forbidden not in account_columns, forbidden


def test_br_cus_1094_tc8__an_ordinary_account_answers_none(brazos, dana):
    """`None`, not `[]` — the same return `premises_scope_for_account` uses.

    An ordinary account pays its own bill and has no building to answer for.
    The endpoint turns this into the 404-never-403 refusal, so the tab simply
    does not exist on an ordinary account's screen.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        unit = _flat(dana, premises, plan, label="Unit A")
        account = _tenant_account(dana, unit, name="Ncube, T.")

        assert (
            customer_selectors.master_unit_billing_page(account["id"], _params()) is None
        )


def test_br_cus_1094_tc9__the_list_pages_filters_and_searches_on_the_server(brazos, dana):
    """`NFR-3` — the page, the filter and the search are all the SERVER's.

    ⚠ **AND `NFR-5`: THERE IS NO CAP.** `per` is the `IS-2` vocabulary's job and
    `page` clamps into range; neither ever refuses a row that exists. A building
    with more units than a page holds is paged, never truncated — which is the
    T4/T3 flexibility `CLAUDE.md` calls load-bearing rather than tidy.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        occupied = _flat(dana, premises, plan, label="Unit A")
        _flat(dana, premises, plan, label="Unit B")
        _flat(dana, premises, plan, label="Unit C")
        _tenant_account(dana, occupied, name="Alvarez, M.")
        master = _master(dana, premises)

        page1, total, _counts = customer_selectors.master_unit_billing_page(
            master["id"], _params(per=2, page=1)
        )
        page2, total2, _c2 = customer_selectors.master_unit_billing_page(
            master["id"], _params(per=2, page=2)
        )
        assert total == total2 == 3
        assert [row["label"] for row in page1] == ["Unit A", "Unit B"]
        assert [row["label"] for row in page2] == ["Unit C"]

        vacant_only, vacant_total, _c3 = customer_selectors.master_unit_billing_page(
            master["id"], _params(filters={"billed_to": "this_account"})
        )
        assert vacant_total == 2
        assert sorted(row["label"] for row in vacant_only) == ["Unit B", "Unit C"]

        found, found_total, _c4 = customer_selectors.master_unit_billing_page(
            master["id"], _params(q="unit c")
        )
        assert found_total == 1
        assert found[0]["label"] == "Unit C"


def test_br_cus_1094_tc10__no_price_is_stated_on_any_row(brazos, dana):
    """`BR-CUS-1040`: *"NO PRICE IS STATED — a single what the empty unit will
    cost figure is the rating engine's and nothing publishes a per-unit standing
    charge outside a bill run."*

    This tab states a PAYER. `owed` is a different question — what the unit owes
    TODAY, metering's own column, carried through untouched — and it is never a
    forecast. A `will_cost` or `base_charge` key appearing here would be this
    screen inventing a figure the run has not computed.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        _flat(dana, premises, plan, label="Unit B")
        master = _master(dana, premises)

        rows, _total, _counts = customer_selectors.master_unit_billing_page(
            master["id"], _params()
        )

        for row in rows:
            for forbidden in ("base_charge", "will_cost", "forecast", "estimated_amount"):
                assert forbidden not in row, forbidden


def test_br_cus_1094_tc11__a_pending_tenant_leaves_the_unit_billed_to_the_master(
    brazos, dana
):
    """⚠ **THE ANSWER A CLERK IS MOST LIKELY TO BE SURPRISED BY, AND IT IS
    RULED.**

    A unit whose only account is `pending_activation` is VACANT: `BR-CUS-018`
    (CONFIRMED) says a draft/pending account *"never derives occupancy and does
    not block the unit for other move-ins"*, and `occupying_accounts_for_unit`
    reads exactly that. So the bill goes to the master until the move-in is
    activated.

    **This is the screen earning its keep.** Without it, a clerk who has
    captured five move-ins and not activated them would find out at the bill
    run that all five units billed the landlord. Here it is on screen, before.

    The row still names the pending account nowhere, because it is not the
    payer — and naming it would be the screen contradicting the run.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        unit = _flat(dana, premises, plan, label="Unit P")
        _tenant_account(dana, unit, name="Pending, P.", activate=False)
        master = _master(dana, premises)

        rows, _total, counts = customer_selectors.master_unit_billing_page(
            master["id"], _params()
        )
        row = _by_label(rows)["Unit P"]

        assert row["occupancy"] == "vacant"
        assert row["payer"] == customer_selectors.UNIT_PAYER_THIS_ACCOUNT
        assert row["payer_basis"] == customer_selectors.UNIT_BASIS_VACANT
        assert row["account_no"] is None
        # Unit P and the empty second home `_master` adds for `BR-CUS-1114`.
        assert counts["vacant"] == 2
        assert counts["occupied"] == 0


def test_br_cus_1094_tc12__a_common_area_the_master_does_not_cover_reaches_nobody(
    brazos, dana
):
    """⚠ **THE ONE ROW WHERE TWO CELLS SAY DIFFERENT THINGS, PINNED HERE SO
    NOBODY "TIDIES" THE TRUTHFUL ONE AWAY.**

    A common area created AFTER the master account exists is not attached to it
    — `create_master_account` writes agreements for the common areas present
    when it runs, and `_attach_named_master_account` is an explicit,
    opt-in door in metering. So such a unit is in neither set billing reads:
    `covered_unit_ids` excludes it (no open agreement) and
    `base_charge_only_coverage` excludes it BY NAME (`is_common_area`).

    **Billing therefore raises nothing for it, and `runs._billed_units` reports
    it as a unit in the cycle with no billable account.** That is
    `BR-CUS-1094`'s stated refusal, and `payer: nobody` is the screen saying the
    same thing.

    ⚠ **AND `OccupantCell` — metering's own, imported — SAYS *"Always billed to
    the owner."* ON THAT SAME ROW**, because `BR-MET-101` is a statement of the
    general rule and not a claim about this run. The two cells are answering
    different questions and on this one row they read as a contradiction, with
    the OPTIMISTIC one being the imported sentence. **`Billed to` is the one
    telling the truth about the next bill.** Filed as `DEF-CUS-6309` rather
    than resolved here: changing `OccupantCell` changes the property page too,
    which is a second screen and a second blast radius.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        _common_area(dana, premises, plan, label="Hallway lighting")
        master = _master(dana, premises)
        # Added AFTER the master exists, so nothing attaches it.
        _common_area(dana, premises, plan, label="Bike store")

        rows, _total, counts = customer_selectors.master_unit_billing_page(
            master["id"], _params()
        )
        by_label = _by_label(rows)

        assert by_label["Hallway lighting"]["payer"] == (
            customer_selectors.UNIT_PAYER_THIS_ACCOUNT
        )
        orphan = by_label["Bike store"]
        assert orphan["is_common_area"] is True
        assert orphan["payer"] == customer_selectors.UNIT_PAYER_NOBODY
        assert orphan["payer_basis"] is None
        # …and the counts separate it, because `BR-CUS-1094` says *no lines
        # because nothing falls to it* and *no lines although the premises HAS
        # an unoccupied unit* are different facts.
        assert counts["billed_nobody"] == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: `BR-CUS-1094` (PO 2026-09-23) — the master account's Units tab.
#         Drawing: `05-prototype/Premises & Units Blueprint 2.pdf` pages 23–25,
#         read as IMAGES at scale 2.0 (B14 rule 42). That drawing is the
#         PROPERTY's Units tab; **no blueprint page draws this tab**, so its
#         design language is followed and its subject is not.
# generated: 2026-09-23 by lane MA-UNITS
# gates: PROVED RED FIRST in the harness that runs it — a detached worktree at
#        the branch tip `726efa7f3`, which does not carry the selector:
#          $ JOBS_EAGER=false python -m pytest \
#              tests/test_br_cus_1094_master_units_tab.py -p no:randomly -q \
#              --reuse-db
#          9 failed, 1 passed, 6 warnings in 332.41s
#        The cause, confirmed directly in that same tree:
#          AttributeError: module 'apps.customers.selectors' has no attribute
#          'MASTER_UNIT_DEFAULT_SORT'
#        — an AttributeError rather than an assertion, because the selector
#        does not exist at the tip at all, which is the honest shape for a new
#        read.
#        ⚠ **THE ONE THAT PASSED IS `tc7`, AND IT IS SAID HERE RATHER THAN
#        ROUNDED TO "PROVED RED".** `tc7` asserts that four column names are
#        ABSENT from two models, which is true at the tip and true after this
#        change — so **it can never go red on this commit and was never going
#        to.** That is its job: it is a guard against a FUTURE lane caching the
#        split, and a prohibition has no red-at-birth proof available to it.
#        Reporting ten reds here would have been the false pass hard-won law 7
#        asks every author to go looking for.
# exceptions: E4 `tc7` asserts the ABSENCE of four column names on two models.
#   It is the only shape available: `BR-CUS-1094`'s prohibition is about a
#   column nobody has added, and an absence is invisible to every other check
#   this repo has (`CLAUDE.md` hard rule 8's own closing lesson) · E4 no
#   PostgreSQL-only case is needed here — nothing in this read catches a
#   database error and continues, so hard-won law 14's trap is not reachable
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
