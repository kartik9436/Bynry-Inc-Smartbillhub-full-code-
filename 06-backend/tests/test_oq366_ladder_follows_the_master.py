# ── Trace ──────────────────────────────────────────────
# Rule:     BR-CUS-082 (a debt surviving closure is still chased and the ladder
#           RESTARTS at TIER 1) · BR-CUS-097 as QUALIFIED 2026-08-27 (the
#           residue moves to the master ONLY when a clerk ties it back during
#           move-out) · OQ-366 CLOSED 2026-08-27 (the ladder chases the MASTER,
#           because the sub-account is closed by then)
# Pin:      **$328.70 − $153.50 = $175.20, and TIER 1 fires on the MASTER.**
#           And it fires on the master ONLY for a residue a clerk tied back.
# Rules:    BR-CUS-171 (the master is DERIVED from the premises, so the transfer
#           target and the child link can never name two different accounts) ·
#           BR-CUS-025 (deposit and interest apply first) · BR-MET-105a (the
#           premises owner, whose column does not exist)
# OQs:      OQ-532 (CLOSED 2026-08-27, option B — a master ALREADY at TIER 3 on
#           its own arrears JOINS at TIER 4; this file asserts the RULING is
#           carried and seeds nothing against it. ⚠ This line read OQ-580 and
#           OPEN until DEF-2950 — that id belongs to an import question)
# Defects:  DEF-651 (the ruling BR-CUS-097 came out of)
# Impacts:  apps/customers/move_out_settlement.py
# ───────────────────────────────────────────────────────
"""OQ-366 — whose door the restarted ladder knocks on.

**PO, 2026-08-27, verbatim:** *"Sub account is closed when debt is trasnfer
hence we now follow with owner for debt"*.

Two rules were signed on 2026-08-24 and neither resolved the other:
`BR-CUS-082` restarted the ladder at tier 1 against a debt surviving closure,
and `BR-CUS-097` moved that debt to the master. `move_out_settlement` recorded
the collision honestly and named no subject — *"nothing here names a
subject"* — for three days.

**THE RULING IS STRUCTURAL AND THAT IS WHY IT IS CLEAN:** the sub-account is
CLOSED at the moment the residue transfers, so there is no open account on the
tenant side to chase at all. That also disposes of *both, differently*: a second
ladder would have to run against a closed account.

⚠ **AND IT INHERITS THE SAME DAY'S QUALIFICATION, WHICH IS THE HALF THIS FILE
EXISTS TO PROTECT.** The transfer is CLERK-INITIATED. A residue nobody tied
back does not become the landlord's problem — and therefore must not generate
the landlord's letters. tc4 is that assertion: the same $175.20, written off
instead of tied back, chases the closed account and names no master anywhere.

⚠⚠ **WHAT THIS FILE DELIBERATELY DOES NOT DO (OQ-532).** No fixture here puts
a residue onto a master that ALREADY carries arrears. **That question WAS put
to the Product Owner and IS ruled** — 2026-08-27, option (B), verbatim: *"this
si correct - B — join the existing position — Tier 4, on a larger balance"* — so
a master at tier 3 receives tier 4 rather than a restart. Nothing here seeds it
all the same, because collections has no tables and no ladder runs against
anybody: the ruling is carried as a STATEMENT for W7 to build. tc5 asserts it is
carried on every decision.

⚠ **THIS PARAGRAPH SAID `OQ-580` AND SAID THE QUESTION WAS NEVER ASKED, UNTIL
`DEF-2950`.** The id was renumbered to `OQ-532` at merge on the day it was
minted, and `OQ-580` went to an unrelated import question — which is live and
genuinely open, so the stale sentence read as true to anyone who followed the
citation. Both halves were wrong and both are fixed together.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.customers import move_out_settlement
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

#: BR-CUS-082's own worked case, `A-11024 · Ridge Coffee Co.` — the one both
#: rules were written against and the one OQ-366's closure completes.
CLOSING_BALANCE = Decimal("328.70")
DEPOSIT_AND_INTEREST = Decimal("153.50")
RESIDUE = Decimal("175.20")


def _premises_with_master(actor, tenant):
    plan = make_plan(tenant, name="Small Commercial", services=["electric"])
    premises = make_premises(
        actor,
        address_line="1408 Elm St",
        premises_type="apartment_complex",
        owner_manager="Miller Property LLC",
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
    # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
    top_up_homes(actor, premises["id"])
    master = customer_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": OPENED.isoformat(),
            # ⛔ **`BR-CUS-1024` — THE MASTER DOOR IS GATED TOO, AND IT NEEDS A
            # `customer` BLOCK EVEN WITH NO `contact` IN THE PAYLOAD.** When one
            # is absent this door builds the contact from the premises' own
            # free-text `owner_manager` (PO 2026-08-22, *"payer = the premises'
            # owner/manager"*), so a party IS presented and the refusal fires —
            # which is why "no contact" is safe at `POST /accounts` and is NOT
            # safe here. The party named is therefore the owner the door would
            # otherwise have minted from, as a COMPANY: the seeded owner is
            # `Whitfield Rentals LLC` and a landlord is an organisation whatever
            # the account TYPE says. Same shape as every other fixture in the
            # repo: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(
                premises.get("owner_manager") or "Owner", kind="company"
            ),
        },
    )
    created = customer_services.create_account(
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
            "addresses": [
                {"kind": "mailing", "line1": "1408 Elm St", "city": "Katy", "state": "TX"}
            ],
        },
    )
    customer_services.activate_account(actor, created["id"])
    return (
        customer_models.Account.objects.get(pk=master["id"]),
        customer_models.Account.objects.get(pk=created["id"]),
    )


# ══════════════════════════════════════════════════════════════════════════
# THE ARITHMETIC BOTH RULES WERE WRITTEN AGAINST
# ══════════════════════════════════════════════════════════════════════════
def test_oq366_tc1__the_worked_case_lands_short_by_175_20():
    """$328.70 owed, $153.50 of deposit and interest — **$175.20 survives.**

    Pure: `derive` has no branch inside it and needs no table, so the figure the
    two rulings are about is pinned before anything about routing is asserted.
    """
    settlement = move_out_settlement.derive(
        currency="USD",
        prior_balance=CLOSING_BALANCE,
        final_bill=Decimal("0.0000"),
        deposit_held=DEPOSIT_AND_INTEREST,
        deposit_interest=Decimal("0.0000"),
        siblings=(),
    )
    assert settlement.landing == move_out_settlement.LANDING_SHORT
    assert settlement.shortfall == RESIDUE
    assert CLOSING_BALANCE - DEPOSIT_AND_INTEREST == RESIDUE


# ══════════════════════════════════════════════════════════════════════════
# WHOSE DOOR — OQ-366, CLOSED
# ══════════════════════════════════════════════════════════════════════════
def test_oq366_tc2__a_tied_back_residue_points_the_ladder_at_the_master(brazos, dana):
    """**TIER 1 FIRES ON THE MASTER.**

    The target is RESOLVED from the premises, never supplied — and it resolves
    to the same account `sub_accounts_for_master` calls this tenant's parent,
    which is what stops the child link and the debt target ever disagreeing.
    """
    with tenant_ctx(brazos):
        master, tenant = _premises_with_master(dana, brazos)

        target = move_out_settlement.transfer_target_for(tenant)
        assert target["available"] is True
        assert target["account_no"] == master.account_no
        assert customer_selectors.master_account_for(tenant).account_no == master.account_no

        dunning = move_out_settlement._dunning_for(target)
        assert dunning["chased"] is True
        assert dunning["restarts_at_tier"] == 1
        assert dunning["escalates_to_disconnection"] is False
        assert dunning["subject"] == "master_account"
        assert dunning["subject_account_no"] == master.account_no
        assert "OQ-366" in dunning["subject_br_ref"]
        # ⚠ THE COLLISION IS GONE, and its absence is asserted so nobody
        # re-introduces the "we do not know" answer after it was ruled.
        assert "subject_unresolved" not in dunning


def test_oq366_tc3__the_transfer_option_names_the_master_and_the_owner_still_refuses(brazos, dana):
    """BR-CUS-097's target is enabled; BR-MET-105a's is not, and says why.

    ⚠ **THE REASON CHANGED AND THE OUTCOME DID NOT (`DEF-2951`, `CR-056` W6).**
    This asserted the string `owner_customer_id` — the column BR-MET-105a names
    and nobody ever added — and read that absence as *the owner can never be a
    posting target*. `CR-056` gives every address's owner a real account, so the
    owner target now RESOLVES wherever one is declared. **This fixture declares
    none**: it builds the premises with a free-text `owner_manager` and no typed
    owner row, so the owner target still refuses — on the fact that this address
    has no owner account, which is the case that genuinely remains and which the
    PO ruled ends address by address as owners are identified.
    """
    with tenant_ctx(brazos):
        _master, tenant = _premises_with_master(dana, brazos)
        options = {row["path"]: row for row in move_out_settlement.shortfall_path_options(tenant)}
        transfer = options[move_out_settlement.SHORTFALL_TRANSFER]
        assert transfer["enabled"] is True
        targets = {row["target"]: row for row in transfer["targets"]}
        assert targets[move_out_settlement.TRANSFER_TARGET_MASTER]["available"] is True
        assert targets[move_out_settlement.TRANSFER_TARGET_OWNER]["available"] is False
        reason = targets[move_out_settlement.TRANSFER_TARGET_OWNER]["reason"]
        assert "no owner account" in reason
        # …and it does NOT tell a reader the column is the obstacle any more.
        assert "owner_customer_id" not in reason


# ══════════════════════════════════════════════════════════════════════════
# THE QUALIFICATION — A RESIDUE NOBODY TIED BACK IS NOT THE LANDLORD'S
# ══════════════════════════════════════════════════════════════════════════
def test_oq366_tc4__a_residue_nobody_tied_back_never_names_the_master():
    """**THE HALF THAT PROTECTS THE LANDLORD.**

    BR-CUS-097 as qualified 2026-08-27: *"if clark tied back to A during move
    out process"*. Write the same $175.20 off, or pursue it, and BR-CUS-097
    never fired — so OQ-366's closure does not apply and the restarted ladder
    runs against the closed account. No master is named anywhere in the answer.
    """
    dunning = move_out_settlement._dunning_for(None)
    assert dunning["chased"] is True
    assert dunning["restarts_at_tier"] == 1
    assert dunning["subject"] == "the closed account itself"
    assert dunning["subject_br_ref"] == "BR-CUS-082"
    assert "master_account" not in dunning
    assert "subject_account_no" not in dunning
    assert "landlord" in dunning["subject_detail"]

    # And an UNAVAILABLE target is the same fact: nothing was tied back.
    refused = move_out_settlement._dunning_for(
        {"available": False, "account_no": "AC-2026-00001", "target": "master_account"}
    )
    assert refused["subject"] == "the closed account itself"
    assert "subject_account_no" not in refused


# ══════════════════════════════════════════════════════════════════════════
# WHAT IS RULED AND NOT YET BUILT — OQ-532, CARRIED AND NOT SEEDED
# ══════════════════════════════════════════════════════════════════════════
def test_oq366_tc5__every_decision_carries_oq_532s_ruling_and_no_fixture_answers_it():
    """A master ALREADY on the ladder is a real case, and it IS ruled.

    ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL `DEF-2950`** — that the question
    was unsigned, under the id `OQ-580`, which had been renumbered away from it
    on the day it was minted. `OQ-532` CLOSED on 2026-08-27, option (B): a
    residue arriving on a master already in collections JOINS that ladder, so a
    master at TIER 3 receives **TIER 4** on the larger balance, and
    `BR-CUS-082`'s literal restart-at-tier-1 is NARROWED to a master with no
    ladder running.

    Carried by ID on every decision so it cannot outlive its reason (DEF-445),
    and asserted here so a later lane deleting the sentence goes RED rather than
    quietly building the restart the PO ruled against.
    """
    for target in (None, {"available": True, "account_no": "AC-2026-00099"}):
        dunning = move_out_settlement._dunning_for(target)
        note = dunning["oq_532_master_ladder_position"]
        assert "OQ-532" in note
        assert "CLOSED 2026-08-27" in note
        assert "JOIN" in note and "TIER 4" in note
        # ⚠ The ruling NARROWS BR-CUS-082 rather than replacing it, and the
        # carried text has to say so — a lane reading only `restarts_at_tier`
        # would build the restart on every master.
        assert "NARROWS BR-CUS-082" in note
        # …and the restart is still the rule where no ladder is running.
        assert dunning["restarts_at_tier"] == 1
        # ⚠ **STILL NOT SEEDED, and now for a different reason.** The question
        # is answered; what is missing is collections itself. A fixture putting
        # a residue onto a master with arrears would be asserting a ladder this
        # product does not run.
        assert "no ladder runs against anybody yet" in note
