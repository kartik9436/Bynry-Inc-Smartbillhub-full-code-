# ── Trace ──────────────────────────────────────────────
# Change:  CR-089 wave I (tasks I1–I6) · `PUJ-36` to `PUJ-41` — the unit's
#          Account tab rendered five facts over an accounts table with 33
#          columns and six tables hanging off it.
# Defects: DEF-CUS-4691 (an account protection is on no screen a clerk reaches
#          from a unit) · DEF-CUS-4692 (nine account columns populated on ZERO
#          rows across both demo utilities)
# Rules:   BR-CUS-039 (a protection forbids disconnection) · BR-PAY-013 (the
#          cash-only sanction at the tenant's Nth bounce) · BR-CUS-059 (autopay
#          is the customer's ELECTION and nothing un-asks it) · BR-CUS-055
#          (occupancy keys off the status CLASS) · BR-CUS-068 (a master account
#          is the owner's) · CLAUDE.md hard rule 2 (money stored to 4, and this
#          read serves the STORED scale — it rounds nothing) · rule 1 (nothing
#          is read without `app.tenant_id`) · law 7 (proved RED on the real
#          fault first, in the harness that will run it)
# ───────────────────────────────────────────────────────
"""What the unit's Account tab is served, and the absences it must not flatten.

**THE ONE PROPERTY WORTH STATING FIRST.** Three of the money rows below live in
modules `customers` reads across a seam — payment plans and the dunning ladder
are `payments`', budget billing is `billing`' — and every one of those seams
answers `None` when the owning module cannot be reached. `None` must arrive at
the screen as *could not be read* and NEVER as *there is none*: `DEF-127` is
what collapsing them cost, and it is the failure this file exists to pin.

⚠ **AND ONE CASE HERE IS ABOUT A FIGURE'S SCALE RATHER THAN ITS VALUE.** The
deposit row served the string `"0"` in its first draft, because
`account.deposit_on_file or 0` substitutes the INT zero for a FALSY
`Decimal("0.000000")`. Every value in the product was still correct and nothing
would ever have gone red: no check in this repo compares the SCALE of a money
string. Found by printing the payload against live demo data, which is hard-won
law 6 applied to an API instead of to a screen.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnects, models as customers_models, unit_account_facts
from apps.metering import unit_account

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

AS_OF = date(2026, 9, 8)


# ════════════════════════════════════════════════════════════════════════════
# I1 · A PROTECTION IS THE FIRST THING THE TAB KNOWS ABOUT
# ════════════════════════════════════════════════════════════════════════════
def test_a_medical_certificate_reaches_the_unit_and_holds_disconnection(dana, brazos):
    """`DEF-CUS-4691`. The row was always there; nothing on the unit read it."""
    with tenant_ctx(brazos):
        unit, account = _an_occupied_unit(dana, brazos)
        disconnects.record_protection(
            dana,
            account.pk,
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 7),
            expires_on=date(2026, 11, 5),
        )
        answer = unit_account.unit_account(str(unit['id']))

    protections = answer["facts"]["protections"]
    assert protections["disconnection_held"] is True
    assert protections["kinds_in_force"] == ("medical_certificate",)
    held = protections["in_force"][0]
    assert held["expires_on"] == date(2026, 11, 5)
    # ⚠ **A ROLE, NOT A PERSON.** `account_protections.set_by` defaults to
    # `tenant` and the moratorium's default is `regulator`. `CR-089`'s worked
    # example reads *"set by D. Whitfield"*; no column in this product holds a
    # person's name for a protection, so none is served and none is invented.
    assert held["set_by"] == "tenant"
    assert "author" not in held and "set_by_name" not in held


def test_a_lifted_protection_is_served_as_lapsed_and_holds_nothing(dana, brazos):
    """A hold that ENDED is history a regulator asks about, not a live hold.

    `lifted_on` + `lifted_reason` end a protection WITHOUT deleting it, which is
    why the payload has two lists rather than one filtered one.
    """
    with tenant_ctx(brazos):
        unit, account = _an_occupied_unit(dana, brazos)
        row = disconnects.record_protection(
            dana,
            account.pk,
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 1, 1),
            expires_on=date(2026, 3, 31),
        )
        disconnects.lift_protection(
            dana, row["protection_id"], on_date=date(2026, 2, 1),
            reason="certificate withdrawn",
        )
        answer = unit_account.unit_account(str(unit['id']))

    protections = answer["facts"]["protections"]
    assert protections["disconnection_held"] is False
    assert protections["in_force"] == []
    assert len(protections["lapsed"]) == 1


# ════════════════════════════════════════════════════════════════════════════
# I2 · THE CLASS THAT SELECTS A FIGURE ON THE BILL
# ════════════════════════════════════════════════════════════════════════════
def test_the_customer_class_is_named_with_its_code_and_its_label(dana, brazos):
    """Since `CR-087` a charge code can price per class, so this is not a label.

    The CODE travels beside the NAME deliberately: the name is what a clerk
    reads and the code is what `resolution.AccountFacts.customer_class` narrows
    on, so a screen and a bill cannot end up naming different things.
    """
    with tenant_ctx(brazos):
        unit, _ = _an_occupied_unit(dana, brazos)
        answer = unit_account.unit_account(str(unit['id']))

    customer_class = answer["facts"]["customer_class"]
    assert customer_class["code"] == "residential"
    assert customer_class["name"]
    assert customer_class["legacy"] is False


# ════════════════════════════════════════════════════════════════════════════
# I3 · AUTOPAY IS ONE ANSWER READ FROM TWO COLUMNS
# ════════════════════════════════════════════════════════════════════════════
def test_enrolled_and_not_sanctioned_reads_as_money_that_will_be_taken(dana, brazos):
    with tenant_ctx(brazos):
        unit, account = _an_occupied_unit(dana, brazos)
        customers_models.Account.objects.filter(pk=account.pk).update(autopay=True)
        answer = unit_account.unit_account(str(unit['id']))

    autopay = answer["facts"]["autopay"]
    assert autopay["reading"] == unit_account_facts.AUTOPAY_TAKEN
    assert autopay["will_be_taken"] is True


def test_enrolled_AND_cash_only_reads_as_money_that_will_NOT_be_taken(dana, brazos):
    """⚠ **THE CASE THE CUSTOMER PORTAL SHIPPED WRONG, AND IT COST A WAVE.**

    The account is enrolled — the customer asked for it and `BR-PAY-013` never
    un-asks it — and the sanction means nothing is drafted. A screen reading
    `autopay` alone says *on*, which is the opposite of what happens.

    ⚠ **THE SANCTION IS NOT STAMPED ON HERE EITHER.** `services.record_nsf` is
    called twice and the RULE trips the flag, so this case also proves
    `BR-PAY-013` still works; a test that set the column directly would go green
    on a product where the rule had stopped firing.
    """
    from apps.customers import services

    with tenant_ctx(brazos):
        unit, account = _an_occupied_unit(dana, brazos)
        customers_models.Account.objects.filter(pk=account.pk).update(autopay=True)
        outcome = services.record_nsf(str(account.pk), actor=dana)
        assert outcome.cash_only_no_autopay is False, "one bounce must not trip it"
        outcome = services.record_nsf(str(account.pk), actor=dana)
        assert outcome.flag_tripped_now is True, "the tenant's N is 2 — the second trips it"
        answer = unit_account.unit_account(str(unit['id']))

    autopay = answer["facts"]["autopay"]
    assert autopay["elected"] is True, "the election SURVIVES the sanction (BR-CUS-059)"
    assert autopay["cash_only"] is True
    assert autopay["nsf_count"] == 2
    assert autopay["will_be_taken"] is False
    assert autopay["reading"] == unit_account_facts.AUTOPAY_HELD_CASH_ONLY


# ════════════════════════════════════════════════════════════════════════════
# I4 · FIVE MONEY STATES, AND THE THIRD ANSWER EACH OF THEM CAN GIVE
# ════════════════════════════════════════════════════════════════════════════
def test_every_money_state_is_answered_on_a_quiet_account(dana, brazos):
    """*An absent row reads as "not looked up"; a stated "none" is the answer.*"""
    with tenant_ctx(brazos):
        unit, _ = _an_occupied_unit(dana, brazos)
        facts = unit_account.unit_account(str(unit['id']))["facts"]

    assert facts["payment_plan"]["state"] == unit_account_facts.STATE_NONE
    assert facts["budget_billing"]["state"] == unit_account_facts.STATE_NONE
    assert facts["collections"]["state"] == unit_account_facts.STATE_NONE
    assert facts["bounced_payments"]["count"] == 0
    assert facts["tax_exemption"]["claimed"] is False
    assert facts["deposit"]["any"] is False


def test_a_deposit_is_served_at_the_STORED_scale_and_never_as_a_bare_zero(dana, brazos):
    """⚠ **THE SCALE, NOT THE VALUE — AND `or 0` IS HOW IT WENT WRONG.**

    `Decimal("0.000000")` is FALSY, so `account.deposit_on_file or 0` handed
    back the INT zero and this row served `"0"` where every other money string
    in the product serves `"0.000000"`. No value was wrong, so nothing in this
    repo could go red: **no check anywhere compares the scale of a money
    string.** Found by printing the payload against live demo data.

    Hard rule 2: stored to 4 decimals (the column carries 6 and the rule governs
    what is WRITTEN), rounded ONCE at display by `MoneyCell`. This read rounds
    nothing.
    """
    with tenant_ctx(brazos):
        unit, account = _an_occupied_unit(dana, brazos)
        empty = unit_account.unit_account(str(unit['id']))["facts"]["deposit"]
        assert empty["held"] == "0.000000", "a Decimal zero, not an int zero"
        assert empty["any"] is False
        assert empty["received_on"] is None

        customers_models.Account.objects.filter(pk=account.pk).update(
            deposit_on_file=D("150.000000"), deposit_received_on=date(2026, 6, 1)
        )
        held = unit_account.unit_account(str(unit['id']))["facts"]["deposit"]

    assert held["held"] == "150.000000"
    assert held["currency"] == "USD"
    assert held["received_on"] == date(2026, 6, 1)
    assert held["any"] is True


def test_an_unreadable_neighbour_is_a_THIRD_state_and_never_becomes_none(dana, brazos,
                                                                        monkeypatch):
    """`DEF-127` in one assertion.

    A screen that renders *no payment plan* over a plan it simply could not
    fetch tells a clerk the customer never agreed one. The seam answers `None`
    for *unwired*; this proves that `None` survives all the way out rather than
    being flattened into the empty answer beside it.
    """
    from apps.customers import seams

    monkeypatch.setattr(seams, "payment_plans_for", lambda *a, **k: None)
    monkeypatch.setattr(seams, "budget_enrolment_for", lambda *a, **k: None)
    monkeypatch.setattr(seams, "collection_state_for", lambda *a, **k: None)
    with tenant_ctx(brazos):
        unit, _ = _an_occupied_unit(dana, brazos)
        facts = unit_account.unit_account(str(unit['id']))["facts"]

    assert facts["payment_plan"]["state"] == unit_account_facts.STATE_UNREADABLE
    assert facts["budget_billing"]["state"] == unit_account_facts.STATE_UNREADABLE
    assert facts["collections"]["state"] == unit_account_facts.STATE_UNREADABLE


def test_an_account_nobody_has_chased_is_NOT_in_collections_with_no_reason_attached(dana, brazos):
    """⚠ **PAYMENTS' `paused_reason` IS NOT CARRIED ON THE *NONE* BRANCH.**

    `account_position` answers `no_live_plan` for an account nobody has ever
    chased — true in payments' own vocabulary, and read on this tab it would say
    *collections is paused because there is no payment plan* about an account
    that is not in collections at all. A reason for a state the row is not in is
    worse than no reason.
    """
    with tenant_ctx(brazos):
        unit, _ = _an_occupied_unit(dana, brazos)
        collections = unit_account.unit_account(str(unit['id']))["facts"]["collections"]

    assert collections["state"] == unit_account_facts.STATE_NONE
    assert collections["paused_reason"] is None
    # ⚠ `payments.dunning.disconnect_blocked` is deliberately NOT forwarded: it
    # reads as *may this account be cut* and answers only the payment-plan half.
    # `DEF-PAY-4703`.
    assert "disconnect_blocked" not in collections


# ════════════════════════════════════════════════════════════════════════════
# I5 · THE NOTES, AND WHO IS NOT NAMED ON THEM
# ════════════════════════════════════════════════════════════════════════════
def test_notes_arrive_pinned_first_with_the_customer_visible_flag(dana, brazos):
    from apps.customers import services

    with tenant_ctx(brazos):
        unit, account = _an_occupied_unit(dana, brazos)
        services.create_account_note(
            dana, str(account.pk),
            {"title": "Meter access", "body": "Dog in the side yard — ring first.",
             "customer_visible": True},
        )
        services.create_account_note(
            dana, str(account.pk), {"title": "Medical protection", "pinned": True},
        )
        notes = unit_account.unit_account(str(unit['id']))["facts"]["notes"]

    assert [note["title"] for note in notes] == ["Medical protection", "Meter access"]
    assert notes[0]["pinned"] is True
    assert notes[1]["customer_visible"] is True
    # ⚠ **`author_name` IS NULL ON EVERY NOTE IN THE PRODUCT** while `author_id`
    # is set: `apps.identity.selectors` publishes no `user_display_name`, so
    # customers' resolver always answers None. `DEF-CUS-4704`. The pair is
    # asserted here so the day that read lands, this goes red and the screen's
    # three-state author cell can be simplified.
    assert notes[0]["author_id"] is not None
    assert notes[0]["author_name"] is None


# ════════════════════════════════════════════════════════════════════════════
# I6 · SOMETHING WRITES THE NINE COLUMNS
# ════════════════════════════════════════════════════════════════════════════
def test_credit_tier_travels_with_its_provenance_and_is_never_claimed_as_computed(dana, brazos):
    """`BR-CUS-058` — a COMPUTED cache whose rules (`credit_tier_rules`) are
    unbuilt, so nothing in this product computes it.

    It is SERVED (the column exists and `DEF-CUS-4692` is about columns nothing
    writes) and the screen does not draw it. `computed: False` is what stops the
    next reader treating a seeded letter as a grade the utility awarded.
    """
    with tenant_ctx(brazos):
        unit, _ = _an_occupied_unit(dana, brazos)
        tier = unit_account.unit_account(str(unit['id']))["facts"]["credit_tier"]

    assert tier["computed"] is False
    assert tier["why"] == unit_account_facts.CREDIT_TIER_NOT_COMPUTED


# ════════════════════════════════════════════════════════════════════════════
# A UNIT WITH NO OCCUPANT, AND A UNIT NOBODY MAY READ
# ════════════════════════════════════════════════════════════════════════════
def test_a_vacant_unit_serves_no_account_and_says_which_absence_it_is(dana, brazos):
    with tenant_ctx(brazos):
        unit = _a_unit(dana)
        answer = unit_account.unit_account(str(unit['id']))

    assert answer["account"] is None
    assert answer["facts"] is None
    assert answer["no_account_reason"] == unit_account.NO_ACCOUNT_VACANT
    assert answer["facts_unavailable"] is None, "vacant is an ANSWER, not a failed read"


def test_an_unknown_unit_is_a_refusal_and_not_an_empty_tab(dana, brazos):
    """An empty tab would state that this account has no protections, no notes
    and no plan — three claims nobody made. `unit_row` 404s first."""
    from core import errors

    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            unit_account.unit_account("01a07646-0000-7000-8000-00000000dead")


# ── helpers ─────────────────────────────────────────────────────────────────
#: A counter, so each unit in a file lands on its own premises and no test can
#: pick up another's account through a shared address.
_SEQ = iter(range(1, 500))


def _a_unit(actor):
    """One unit on one premises, with NO account on it — a vacant unit."""
    n = next(_SEQ)
    premises = make_premises(actor, address_line=f"{1400 + n} Bluestem Ln")
    return make_unit(actor, premises["id"], label=f"Unit {n}")


def _an_occupied_unit(actor, tenant):
    """A unit and the ACTIVE account occupying it.

    The account is created through the MODEL rather than through
    `services.create_account` on purpose: this file's subject is the READ, the
    create path has its own suite, and driving the wizard here would make every
    case below depend on a service-layer change it is not about.
    """
    unit = _a_unit(actor)
    n = next(_SEQ)
    account = customers_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=f"A-9{n:04d}",
        status=customers_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customers_models.AccountType.objects.get(code="residential"),
    )
    return unit, account


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-089 wave I (I1–I6) · DEF-CUS-4691 · DEF-CUS-4692 · PUJ-36..PUJ-41
# generated: 2026-09-08 by the CR-089 wave I build lane
# checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
# gates: pytest 06-backend/tests/test_cr089_i_unit_account_facts.py — every case shown RED against the pre-wave read before it was trusted green
# exceptions: E3 the deposit case asserts a money string's SCALE, which no other check in this repo does · E3 `author_name` is pinned NULL because identity publishes no display-name read (DEF-CUS-4704) — the day it does, this goes red and names the screen cell that can then be simplified
# ──────────────────────────────────────────────────────────
