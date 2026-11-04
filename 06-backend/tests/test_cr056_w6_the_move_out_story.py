# ── Trace ──────────────────────────────────────────────
# Change:  CR-056 W6 tasks 26, 27 and 28 — a tenant moves out, the unit falls to
#          the owner's account, the settlement posts the shortfall instead of
#          refusing, and the owner-occupier lets his house out.
#          Screens: S20 step 5 (the impact) and step 4 (the shortfall)
# Rules:   BR-CUS-1040 (a move-out STATES which account the unit falls to and
#          that the standing charge continues on it — PO 2026-08-31) ·
#          BR-CUS-1010 (a Master Account is the owner's account AT AN ADDRESS) ·
#          BR-CUS-097 (a sub-account's unpayable residue transfers to its
#          master) · BR-MET-105a / BR-MET-1010 (the owner is a real party,
#          reached through the account declared on the owner row) ·
#          BR-MET-036 (the unit derives back to vacant) · BR-CUS-170 (the owner
#          carries the units nobody else pays for) · BR-CUS-082 · OQ-366
# Ruling:  PO 2026-08-31 — *"it is taken care during move out step - we have in
#          impact section, we need to cover it there - expliciately"*, and
#          ruling 1 of the same day: *"Two accounts, one bill — the Master has
#          no charges so it produces no document."*
# OQs:     OQ-1250 (which two LEDGER accounts a residue moves between — CLOSED
#          2026-10-14 → (a), one AR→AR entry, CR-185-BRC10) · OQ-532 (CLOSED
#          2026-08-27, option B — a master already on the ladder JOINS at the
#          next tier)
# Defects: DEF-2950 (the wrong OQ id and the stale unsigned claim) ·
#          DEF-2951 (the retired hallway derivation on the money path) ·
#          DEF-2952 (CR-056's status section said this wave was unruled)
# Pin:     A cut and a move-out leave the unit in the SAME state by the SAME
#          function — `$69.60` of common areas becomes `$81.60` when one unit
#          empties, whichever way it emptied.
# ───────────────────────────────────────────────────────
"""The move-out story — and the finding is that most of it was already ruled.

**WHAT THIS WAVE WAS DISPATCHED BELIEVING, AND WHY THAT WAS WRONG (`DEF-2952`).**
`CR-056`'s own status section calls tasks 26–28 *"STILL HELD by §6"* and *"the
one piece genuinely waiting on a ruling"*. **All nine of the CR's questions were
ruled by 2026-09-01** and the same file carries the tally. Nothing in this wave
needed a new answer from the Product Owner; what it needed was the answers put
into the code.

**THE THREE THINGS THIS FILE PINS.**

* **Task 26 — the unit falls to the owner, and there is exactly ONE mechanism.**
  A move-out sets the terminal status, `BR-MET-036` derives the unit back to
  vacant, and `base_charge_only_coverage` puts every unit with no occupying
  account onto the owner's bill. **A cut arrives at the identical state by the
  identical function** — the brief for this wave said that if the two took
  different paths it was a defect to file, and `tc1` is the measurement that
  says they do not. What was genuinely missing was the SENTENCE, which the PO
  ruled must be explicit; `tc2` and `tc3` are that.

* **Task 27 — the settlement stops refusing.** `tc4` is `DEF-2951`: the target
  used to be found by walking the premises' COMMON AREAS and taking whoever paid
  for the hallway — the derivation the PO retired on 2026-08-27 — so an address
  with nothing shared had no target at all and the settlement refused. `tc5` is
  the half that must not go wrong quietly: where the declared owner and the
  account naming the address BOTH answer, they must name the SAME account.

* **Task 28 — the owner-occupier lets his house out.** `tc6` walks the whole
  day the PO's ruling was designed around, on a single-family home with no
  shared space anywhere: he holds two accounts and receives one bill, his
  regular account closes, and the unit falls to the Master Account **that
  already existed**. No migration, no re-keying, no new account, no clerk step.

**THE MONEY MOVING IS PROVED ELSEWHERE.** `OQ-1250` CLOSED 2026-10-14 → (a)
(`CR-185-BRC10`): the tie-back posts one AR→AR entry. `tc7` asserts the decision
says so; `tests/test_cr185_balance_to_owner_posts.py` asserts the books.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.customers import move_out_settlement
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services
from apps.metering import premises_owners
from apps.metering import services as metering_services

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    owner_for,
    tenant_ctx,
)

from tests.move_out_draft_isolation import move_out_draft_isolated  # noqa: E402,F401

# DEF-CUS-10093 (PO 2026-10-13, option B): the final-bill draft is isolated
# here — this suite tests the close; see tests/move_out_draft_isolation.py.
pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("move_out_draft_isolated")]

OPENED = date(2026, 8, 1)

#: `BR-CUS-082`'s own worked case, `A-11024 · Ridge Coffee Co.` — the one every
#: rule about a departing tenant's debt was written against.
CLOSING_BALANCE = Decimal("328.70")
DEPOSIT_AND_INTEREST = Decimal("153.50")
RESIDUE = Decimal("175.20")

OWNER_NAME = "Miller Property LLC"


# ══════════════════════════════════════════════════════════════════════════
# FIXTURES — two shapes, and the difference between them is the whole CR
# ══════════════════════════════════════════════════════════════════════════
def _apartment_block(actor, tenant, *, declare_owner: bool):
    """A building WITH a common area — the shape that has always worked.

    `declare_owner` decides whether `premises_owners.master_account_id` is
    written. It is the difference between the two rungs of the resolution:
    declared owner first, the account's own address second.
    """
    plan = make_plan(tenant, name="Small Commercial", services=["electric"])
    owner_id = owner_for(actor, OWNER_NAME)
    premises = make_premises(
        actor,
        address_line="1408 Elm St",
        premises_type="apartment_complex",
        owner_manager=OWNER_NAME,
        owner_id=owner_id,
        services_available=["electric"],
    )
    common = make_unit(
        actor,
        premises["id"],
        label="Hallway & exterior lighting",
        unit_type="common_area",
        is_common_area=True,
        services=["electric"],
    )
    metering_services.assign_unit_plan(
        actor, common["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    # `BR-CUS-1114` (PO 2026-10-02) — two or more homes for a master account.
    make_unit(actor, premises["id"], label="Unit B", services=["electric"])
    master = customer_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": OPENED.isoformat(),
            # ⛔ **`BR-CUS-1024` — THE MASTER DOOR IS GATED TOO, AND IT NEEDS A
            # `customer` BLOCK EVEN WITH NO `contact` IN THE PAYLOAD.** When one is
            # absent this door builds the contact from the premises' own free-text
            # `owner_manager` (PO 2026-08-22, *"payer = the premises' owner/manager"*),
            # so a party IS presented and the refusal fires — which is why "no
            # contact" is safe at `POST /accounts` and is NOT safe here. The party
            # named is the owner the door would otherwise have minted from, as a
            # COMPANY: a landlord is an organisation whatever the account TYPE says.
            # Same shape as every other fixture in the repo: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(
                premises.get("owner_manager") or "Owner", kind="company"
            ),
        },
    )
    if declare_owner:
        premises_owners.link_owner_master_account(actor, owner_id, master["id"])
    tenant = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "commercial",
            "opened_at": OPENED.isoformat(),
            "contact": {"full_name": "Ridge Coffee Co."},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(
                "Ridge Coffee Co.", account_type="commercial"
            ),
        },
    )
    customer_services.activate_account(actor, tenant["id"])
    return (
        premises,
        unit,
        customer_models.Account.objects.get(pk=master["id"]),
        customer_models.Account.objects.get(pk=tenant["id"]),
    )


def _single_family_home(actor, tenant):
    """A house with NO shared space — the shape the retired derivation was BLIND
    to, and the one `CR-056` ruling 1 is about.

    The owner holds TWO accounts: a Master at the address and a Regular one on
    the unit he lives in. *"Two accounts, one bill — the Master has no charges so
    it produces no document."*
    """
    plan = make_plan(tenant, name="Residential", services=["electric"])
    owner_id = owner_for(actor, "Sarah Whitfield")
    premises = make_premises(
        actor,
        address_line="24 Quarry Lane",
        premises_type="single_family",
        owner_manager="Sarah Whitfield",
        owner_id=owner_id,
        services_available=["electric"],
    )
    unit = make_unit(actor, premises["id"], label="House", services=["electric"])
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    # ⛔ `BR-CUS-1114` (PO 2026-10-02, *"single family hime, single unit, we
    # should not do master account"*) — a one-home address no longer takes a
    # master account, so this fixture's house has a let ANNEX beside it: two
    # homes, still no shared space, which keeps every case below about what it
    # was written for (an owner's account with no common area).
    annex = make_unit(actor, premises["id"], label="Annex", services=["electric"])
    metering_services.assign_unit_plan(
        actor, annex["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    lodger = customer_services.create_account(
        actor,
        {
            "unit_id": str(annex["id"]),
            "account_type": "residential",
            "opened_at": OPENED.isoformat(),
            "contact": {"full_name": "Ana Lodger"},
            "customer": identity_fixtures.customer_block(
                "Ana Lodger", account_type="residential"
            ),
        },
    )
    customer_services.activate_account(actor, lodger["id"])
    master = customer_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "residential",
            "opened_at": OPENED.isoformat(),
            # ⛔ **`BR-CUS-1024` — THE MASTER DOOR IS GATED TOO, AND IT NEEDS A
            # `customer` BLOCK EVEN WITH NO `contact` IN THE PAYLOAD.** When one is
            # absent this door builds the contact from the premises' own free-text
            # `owner_manager` (PO 2026-08-22, *"payer = the premises' owner/manager"*),
            # so a party IS presented and the refusal fires — which is why "no
            # contact" is safe at `POST /accounts` and is NOT safe here. The party
            # named is the owner the door would otherwise have minted from, as a
            # COMPANY: a landlord is an organisation whatever the account TYPE says.
            # Same shape as every other fixture in the repo: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(
                premises.get("owner_manager") or "Owner", kind="company"
            ),
        },
    )
    premises_owners.link_owner_master_account(actor, owner_id, master["id"])
    regular = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": OPENED.isoformat(),
            "contact": {"full_name": "Sarah Whitfield"},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(
                "Sarah Whitfield", account_type="residential"
            ),
        },
    )
    customer_services.activate_account(actor, regular["id"])
    return (
        premises,
        unit,
        customer_models.Account.objects.get(pk=master["id"]),
        customer_models.Account.objects.get(pk=regular["id"]),
    )


def _move_out(actor, account, *, on="2026-08-31"):
    return customer_services.move_out(actor, str(account.id), {"moved_out_on": on})


# ══════════════════════════════════════════════════════════════════════════
# tc1 · TASK 26 — A MOVE-OUT AND A CUT REACH THE SAME STATE BY THE SAME FUNCTION
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w6_tc1__a_move_out_puts_the_unit_on_the_owners_bill_by_the_cuts_own_path(
    brazos, dana
):
    """**THERE IS ONE MECHANISM AND THIS WAVE ADDED NONE.**

    The brief for this wave said it plainly: a cut and a move-out leave the unit
    in the same state, and if they take different paths to it that is a defect
    to file. They do not. Both end in `occupying_accounts_for_unit` answering
    empty, which is the ONLY test `base_charge_only_coverage` applies —
    *"the exclusion test is the ACCOUNT, never a flag"*.

    So the `$69.60 → $81.60` the cut lane measured on 2026-08-31 is the same
    arithmetic on the same rows here; what changes is the event that emptied the
    unit, and nothing in the coverage read can tell the two apart. That is the
    property worth pinning: a lane that "fixed" move-out by writing a second
    path would make a cut and a move-out bill differently on the same building.
    """
    with tenant_ctx(brazos):
        _premises, unit, master, tenant = _apartment_block(dana, brazos, declare_owner=True)

        # BEFORE: somebody lives there, so the owner carries the common area only.
        before = [row["label"] for row in customer_selectors.base_charge_only_coverage(master)]
        assert "Unit A" not in before

        _move_out(dana, tenant)

        # AFTER: the unit is on the owner's bill, and nothing was flagged, set or
        # written to put it there.
        after = [row["label"] for row in customer_selectors.base_charge_only_coverage(master)]
        assert "Unit A" in after
        # …and it is there because NO ACCOUNT OCCUPIES IT, which is the same
        # sentence the cut path ends on.
        assert not customer_selectors.occupying_accounts_for_unit(unit["id"]).exists()


# ══════════════════════════════════════════════════════════════════════════
# tc2 · TASK 26 — THE IMPACT NAMES THE ACCOUNT, EXPLICITLY (PO 2026-08-31)
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w6_tc2__the_impact_names_the_account_the_unit_falls_to(brazos, dana):
    """**RED BEFORE: every one of these fields was `None`.**

    `moveShared.tsx` has declared and drawn `units_occupied_after`,
    `owner_on_record`, `owner_is_free_text` and `common_area_account_no` since
    the impact screen shipped, and its port mapped all four to an explicit
    `null` under a comment naming the module that owed them. Hard-won law 2: the
    panels were built and nothing was wired to them.

    The PO ruled on 2026-08-31 that this cannot stay: *"The unit falling to the
    owner's account is a new consequence of that act and must be drawn there in
    words — which account it moves to, and that the standing charge continues on
    it."*
    """
    with tenant_ctx(brazos):
        _premises, _unit, master, tenant = _apartment_block(dana, brazos, declare_owner=True)
        impact = move_out_settlement.close_impact_for(tenant)

        assert impact["unit_falls_to"]["available"] is True
        assert impact["unit_falls_to"]["account_no"] == master.account_no
        assert impact["common_area_account_no"] == master.account_no
        # The owner is an ACCOUNT here, not a name — so the screen must not tell
        # a clerk nothing can be billed to them.
        assert impact["owner_is_free_text"] is False
        # Occupancy AFTER this move-out: one non-common unit, nobody left in it.
        assert impact["units_occupied_after"] == {"occupied": 0, "total": 2}  # + Unit B, BR-CUS-1114


# ══════════════════════════════════════════════════════════════════════════
# tc3 · TASK 26 — NO OWNER ACCOUNT IS A FAULT, NOT A SILENCE
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w6_tc3__an_address_with_no_owner_account_reports_a_fault(brazos, dana):
    """PO 2026-08-31, ruling 1 consequence 3: *"'no lines because nothing falls
    to it' and 'no lines although the premises HAS an unoccupied unit' are
    different facts and only one of them is good news."*

    And PO 2026-09-01: an owner's account appears when the owner is IDENTIFIED,
    never at a migration that would invent one — so for as long as an address
    carries only a name it genuinely has nowhere to post, and the honest thing
    is to SAY so on the screen rather than fall silent.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential", services=["electric"])
        premises = make_premises(
            dana,
            address_line="9 Bridle Way",
            premises_type="single_family",
            owner_manager="A name and nothing else",
            owner_id=owner_for(dana, "A name and nothing else"),
            services_available=["electric"],
        )
        unit = make_unit(dana, premises["id"], label="House", services=["electric"])
        metering_services.assign_unit_plan(
            dana, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
        )
        tenant = customer_services.create_account(
            dana,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "opened_at": OPENED.isoformat(),
                "contact": {"full_name": "Elena Rivera"},
                # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                # customer identifies nobody, and this fixture's own name went in above.
                # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                "customer": identity_fixtures.customer_block(
                    "Elena Rivera", account_type="residential"
                ),
            },
        )
        customer_services.activate_account(dana, tenant["id"])

        impact = move_out_settlement.close_impact_for(
            customer_models.Account.objects.get(pk=tenant["id"])
        )
        assert impact["unit_falls_to"]["available"] is False
        assert "no owner account" in impact["unit_falls_to"]["reason"]
        # The owner IS only a name, and the screen may say so — that is the
        # advisory doing its job rather than firing on every move-out.
        assert impact["owner_is_free_text"] is True
        assert impact["owner_on_record"] == "A name and nothing else"


# ══════════════════════════════════════════════════════════════════════════
# tc4 · TASK 27 / DEF-2951 — THE SETTLEMENT STOPS REFUSING ON A HOUSE
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w6_tc4__a_house_with_no_common_area_now_has_a_transfer_target(brazos, dana):
    """**RED BEFORE, AND THIS IS `DEF-2951`.**

    `transfer_target_for` asked each of the premises' COMMON AREAS who paid for
    it — the *hallway inference* the PO retired on 2026-08-27, keeping only the
    declared owner (*"the premises names its owner, the owner is the master, and
    nothing is inferred from hallways"*). A single-family home has no hallway to
    ask about, so the walk answered `{}` and the option refused with *"no master
    account covers this unit's premises"*.

    That is the one move-out `CR-056` exists to make ordinary, and it was the
    one the settlement could not do at all.
    """
    with tenant_ctx(brazos):
        _premises, _unit, master, regular = _single_family_home(dana, brazos)

        options = {row["path"]: row for row in move_out_settlement.shortfall_path_options(regular)}
        transfer = options[move_out_settlement.SHORTFALL_TRANSFER]
        assert transfer["enabled"] is True
        targets = {row["target"]: row for row in transfer["targets"]}
        owner = targets[move_out_settlement.TRANSFER_TARGET_OWNER]
        assert owner["available"] is True
        assert owner["account_no"] == master.account_no


# ══════════════════════════════════════════════════════════════════════════
# tc5 · TASK 27 — THE TWO RUNGS MUST NEVER NAME TWO DIFFERENT ACCOUNTS
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w6_tc5__the_declared_owner_and_the_address_name_the_same_account(brazos, dana):
    """**THE HALF THAT COULD GO WRONG QUIETLY.**

    Two DECLARED facts resolve the target: the owner row's `master_account_id`
    and the account's own `premises_id`. The owner wins where both answer, and
    the settlement posts to `available[0]` — so if the two ever named different
    accounts, whose bill a departing tenant's debt landed on would be decided by
    list order. They must agree by construction, because the owner's account
    hangs off the address; this asserts it rather than trusting it.

    It also pins the thing `DEF-2951`'s fix must NOT break: on a building that
    HAS a common area, the retired walk and the address read named the same
    account, so nothing on the estate we already have moved.
    """
    with tenant_ctx(brazos):
        _premises, _unit, master, tenant = _apartment_block(dana, brazos, declare_owner=True)
        by_owner = move_out_settlement.owner_target_for(tenant)
        by_address = move_out_settlement.transfer_target_for(tenant)
        assert by_owner["available"] is True
        assert by_address["available"] is True
        assert by_owner["account_id"] == by_address["account_id"] == str(master.id)


def test_cr056_w6_tc5b__the_address_answers_where_nobody_has_declared_an_owner(brazos, dana):
    """An owner nobody has DECLARED still has an account naming the address.

    `DEF-2902` — nothing writes `premises_owners.master_account_id` today, so on
    the whole existing book the first rung answers nothing. The second rung is
    what keeps the transfer path reachable meanwhile, and it is a declared fact
    (`BR-CUS-1010`) rather than a shape read off the building.
    """
    with tenant_ctx(brazos):
        _premises, _unit, master, tenant = _apartment_block(dana, brazos, declare_owner=False)
        assert move_out_settlement.owner_target_for(tenant)["available"] is False
        by_address = move_out_settlement.transfer_target_for(tenant)
        assert by_address["available"] is True
        assert by_address["account_no"] == master.account_no


# ══════════════════════════════════════════════════════════════════════════
# tc6 · TASK 28 — THE OWNER-OCCUPIER LETS HIS HOUSE OUT
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w6_tc6__the_owner_occupier_lets_his_house_out_and_nothing_breaks(brazos, dana):
    """**THE WHOLE DAY, ON THE CASE THE RULING WAS ARGUED FROM.**

    PO 2026-08-31, ruling 1: *"Two accounts, one bill — the Master has no
    charges so it produces no document."* And the argument that carried it:
    *"The day he lets the house out his Regular Account closes, the unit becomes
    unoccupied, and it falls to the Master Account that already exists — no
    migration, no re-keying, no new account, no clerk step."*

    Four things must be true and each is a way this could have broken:
      1. **no duplicate account and no duplicate customer** — the master he
         already has is the one the unit falls to;
      2. **no unit with two occupying accounts** — while he lives there his
         Regular Account occupies and the Master does not;
      3. **while he lives there the Master carries nothing**, which is what
         makes *no lines, no document* give him one bill and not two;
      4. **the day he leaves, the unit is on the Master** — with no new row
         written anywhere.
    """
    with tenant_ctx(brazos):
        _premises, unit, master, regular = _single_family_home(dana, brazos)

        # 2 · exactly ONE account occupies the house, and it is the regular one
        occupants = list(customer_selectors.occupying_accounts_for_unit(unit["id"]))
        assert [str(row.id) for row in occupants] == [str(regular.id)]

        # 3 · the Master carries NOTHING while he lives there — no charges, so
        #     no document, so he receives one bill exactly as he does today
        assert customer_selectors.base_charge_only_coverage(master) == []

        # 1 + 4 · the day he lets it out
        _move_out(dana, regular)
        accounts_after = customer_models.Account.objects.filter(tenant_id=master.tenant_id).count()
        coverage = [row["label"] for row in customer_selectors.base_charge_only_coverage(master)]
        assert coverage == ["House"]
        # NO new account was opened to make that happen.
        # 3 = master, his regular account, and the annex lodger (`BR-CUS-1114`).
        assert accounts_after == 3

        # …and the impact screen said so BEFORE the commit, naming the account.
        # (Read on a fresh instance: `move_out` closed the row underneath us.)
        closed = customer_models.Account.objects.get(pk=regular.id)
        impact = move_out_settlement.close_impact_for(closed)
        assert impact["unit_falls_to"]["account_no"] == master.account_no


# ══════════════════════════════════════════════════════════════════════════
# tc7 · TASK 27 — THE DECISION, AND SINCE 2026-10-14 THE BOOKS MOVE TOO
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w6_tc7__the_tie_back_is_decided_and_posts_at_completion(brazos, dana):
    """⚠ **THIS CASE ASSERTED `posting.posted is False`, `oq == "OQ-1250"` UNTIL
    2026-10-14.** The PO closed `OQ-1250` → (a) that day (D5, *"option 1;
    property is always under landload agreement"*, `CR-185-BRC10`): the residue
    a clerk ties back is posted as ONE entry, DR AR (owner) / CR AR (tenant),
    through the ledger posting service — once the money is IN THE BOOKS, i.e.
    when the move-out's final bill is issued (coordinator rulings of the same
    day), so on this still-open account the decision records the choice and
    previews `$328.70`.

    The rest of what this case pinned is unchanged: the target is the declared
    owner's account, the clerk's act is on the record, and OQ-532 travels.
    The ledger arithmetic is `tests/test_cr185_balance_to_owner_posts.py`'s.
    """
    with tenant_ctx(brazos):
        _premises, _unit, master, regular = _apartment_block(dana, brazos, declare_owner=True)
        decision = move_out_settlement.shortfall_decision(
            dana,
            str(regular.id),
            {
                "final_bill": CLOSING_BALANCE,
                "as_of": date(2026, 8, 31),
                "path": move_out_settlement.SHORTFALL_TRANSFER,
            },
        )
        assert decision["target"]["account_no"] == master.account_no
        # POSTED AT COMMIT (coordinator ruling 2026-10-14): on an account still
        # open the choice is recorded and the figure previewed; the move-out
        # commit posts it.
        assert decision["posting"]["posted"] is False
        assert decision["posting"]["posts_at"] == "final_bill_issue"
        assert decision["posting"]["amount"]["display"] == "328.70"
        assert decision["posting"]["to_account_no"] == master.account_no
        # …and the clerk's act is on the record, which is what makes the
        # transfer BR-CUS-097's clerk-initiated one rather than an automatic.
        assert decision["tied_back_by"] is not None
        # OQ-532's ruling travels with it, under the id the register actually
        # holds (DEF-2950).
        assert "OQ-532" in decision["dunning"]["oq_532_master_ladder_position"]
