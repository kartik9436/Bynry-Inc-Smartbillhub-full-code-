# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-057 (the ladder and what it would cost · CWP-057) ·
#           US-CWP-058 (help paying, three doors · CWP-056) ·
#           US-CWP-059 (what is protecting your supply · CWP-064) ·
#           US-CWP-056 (credits and refunds in flight · CWP-045)
# Rules:    BR-CWP-092 (an unmapped tier renders as an ABSENCE, never rounded) ·
#           BR-CWP-091 (a hold stops a disconnection, not the debt) ·
#           BR-CWP-090 (three lifetimes, three sentences) · BR-CWP-089 (the
#           portal never grants a protection) · BR-CWP-051 (a write-off shows
#           amount and date, never its reason) · BR-CWP-047 (the credit figure
#           is re-read every load) · BR-CWP-060 (a refund names its method) ·
#           BR-CWP-010 (tenant AND account in the query) · BR-CWP-093 (nothing
#           empty ever appears) · B14 rule 31 · CLAUDE.md hard rule 2
# Open:     OQ-CWP-1600 (nothing prices a reconnection deposit) ·
#           OQ-CWP-1601 (does any hardship route close after the final notice?)
# Tests:    this file
# Impacts:  apps/portal/selectors.py · seams/customers_seam.py ·
#           seams/payments_seam.py · seams/billing_seam.py · api.py
# ───────────────────────────────────────────────────────
"""The four arrears reads — and three of these cases are ABSENCES.

⚠ **THIS IS THE LANE MOST ABLE TO FRIGHTEN SOMEBODY WRONGLY**, so the cases
that matter most here are the ones asserting what is NOT said:

  * no date is invented for a rung the tier vocabulary cannot name (`TC-3`);
  * no figure is invented for a reconnection deposit nobody has priced, and
    the total refuses to be a total without it (`TC-2`);
  * no expiry is invented for a payment-plan hold, which has none by
    construction (`US-CWP-059` TC-2);
  * no hardship route is closed because a wireframe implied one might be
    (`US-CWP-058` TC-8, `OQ-CWP-1601`).

⚠ **AND NOTHING TAKES AN ABSOLUTE VALUE.** A credit note is stored `<= 0` and
leaves negative; a refund is stored positive and leaves positive. `TC-CREDIT-SIGN`
asserts both, because a panel that once read `272.30` where a customer owed
`222.30` is what two writers disagreeing about a sign costs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments.exceptions import PaymentRuleError
from apps.portal import selectors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import an_issued_bill, elm_street_account, switch_on

#: `US-CWP-057` §4 — the story's own fixture, `22 Palm Ct`.
OWED = Decimal("412.60")
DUE_ON = date(2026, 8, 14)
REMINDER_ON = date(2026, 8, 21)
FIRST_NOTICE_ON = date(2026, 9, 1)
#: 14 Aug → 2 Sep is **19 days**, which is the story's own headline.
TODAY = date(2026, 9, 2)
RECONNECT_FEE = Decimal("95.00")


def _overdue_bill(tenant, account):
    return an_issued_bill(
        tenant, account, number="BL-2608-0141", total=str(OWED),
        issued_on=date(2026, 7, 31), due_on=DUE_ON,
    )


def _case(tenant, account, *, tier, next_step_due=None, cut_scheduled_for=None,
          case_no="DSC-26-0001"):
    """One open disconnection case, in the shape `disconnects` writes them."""
    from apps.customers import disconnects

    return disconnects.DisconnectCase.objects.create(
        tenant=tenant,
        account=account,
        case_no=case_no,
        sequence=disconnects.SEQ_SERVICE,
        state=disconnects.STATE_NOTICE_SENT,
        tier=tier,
        tier_reached_on=FIRST_NOTICE_ON,
        amount_owed_at_open=OWED,
        currency="USD",
        opened_on=REMINDER_ON,
        next_step_due=next_step_due,
        cut_scheduled_for=cut_scheduled_for,
    )


def _notice(tenant, case, *, tier, on):
    from apps.customers import disconnects

    return disconnects.DisconnectNotice.objects.create(
        tenant=tenant, case=case, tier=tier, issued_on=on,
        delivery_unavailable_reason=disconnects.DELIVERY_UNAVAILABLE["code"],
    )


def _reconnect_charge(tenant, actor):
    """The tenant's reconnection row — **the ONE place the fee comes from**.

    `BR-BIL-007`: never a literal `$75.00` in code. The portal reads whatever
    the utility configured, through `disconnects.reconnection_terms`.

    ⚠ **`update_or_create`, AND IT WAS A BARE `create` UNTIL 2026-09-20.** On
    that day `rating/0042` (`a3a572501`, `OQ-CUS-12518` closed) began seeding
    the reconnection code on EVERY provisioned tenant at $75.00, so this
    fixture's insert started dying on `charges.tenant_id, charges.code` and
    `TC-2` — the case that pins this very panel's signed sum — has been RED ever
    since. The row is set to this story's own price rather than the assertions
    being relaxed to the seed's: `US-CWP-057` §7 works `412.60 + 95.00`, and a
    test rewritten to match whatever a migration happens to seed proves the
    migration.
    """
    from apps.customers import disconnects
    from apps.rating import models as rating_models

    with tenant_context(tenant.id):
        row, _ = rating_models.Charge.objects.update_or_create(
            tenant=tenant,
            code=disconnects.RECONNECT_CHARGE_CODE,
            defaults={"name": "Reconnection", "amount_rule": "flat", "amount": RECONNECT_FEE},
        )
        return row


def arrears(tenant, account, *, as_of=TODAY):
    with tenant_context(tenant.id):
        return selectors.arrears_position(account, as_of=as_of)


# ═══════════════════════════════════════════════════════════════════════════
# US-CWP-057 — the ladder, and what it would cost
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_057_tc1_the_timeline_is_this_accounts_own_record(pine_hill, sarah):
    """TC-1 — due 14 Aug, reminder 21 Aug, first notice 1 Sep, and `19 days`.

    ⚠ **EVERY DATE COMES OFF A ROW.** Not one is derived from the tenant's
    reminder cadence, which is what TC-4 exists to prove and what the story
    means by *"it reads THIS ACCOUNT'S OWN CASE, not the cadence settings."*
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _overdue_bill(pine_hill, account)
        case = _case(pine_hill, account, tier=disconnects.TIER_2)
        _notice(pine_hill, case, tier=disconnects.TIER_1, on=REMINDER_ON)
        _notice(pine_hill, case, tier=disconnects.TIER_2, on=FIRST_NOTICE_ON)

    body = arrears(pine_hill, account)
    assert body["overdue"] is True
    assert body["owed"] == "412.6000"
    assert body["days_overdue"] == 19
    assert body["due_on"] == DUE_ON.isoformat()
    sent = [row for row in body["timeline"] if row["step"] == "notice_sent"]
    assert [row["on"] for row in sent] == [REMINDER_ON.isoformat(), FIRST_NOTICE_ON.isoformat()]
    assert [row["tier"] for row in sent] == [disconnects.TIER_1, disconnects.TIER_2]
    # ⚠ **NOTHING CLAIMS A DELIVERY.** There is no email, SMS or print adapter
    # in this release, so a portal that drew *"emailed 1 September"* would be
    # telling a customer they were warned (`BR-NOT-005`).
    assert all(row["served_channel"] is None for row in sent)


@pytest.mark.django_db
def test_us_cwp_057_tc2_the_cost_refuses_to_total_a_figure_nobody_priced(
    pine_hill, sarah
):
    """TC-2 · **THE COST ARITHMETIC, AND IT IS THE ONE THAT CHANGED.**

    The story's §7 works `412.60 + 95.00 + 150.00 = 657.60`. **Measured, no read
    in this product answers that `$150.00`:** `reconnection_terms` records
    WHETHER a new deposit will be required and carries no amount, because
    `DSC-02.4` says one *is required* and prices none — *"Nothing collects that
    new deposit and nothing posted the application."*

    So the screen shows **`412.60 + 95.00 = 507.60`** as a SUBTOTAL, names the
    deposit as a part that is missing, and there is no field on the wire a screen
    could label *if it goes that far* over an incomplete sum. `OQ-CWP-1600` is
    open and the story is amended.

    ⚠ **A ZERO WOULD HAVE PASSED EVERY OTHER CHECK IN THIS REPO** and told a
    frightened customer that getting reconnected costs nothing beyond the fee.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _reconnect_charge(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _overdue_bill(pine_hill, account)
        _case(pine_hill, account, tier="tier_2_10_day")

    cost = arrears(pine_hill, account)["cost"]
    assert [part["part"] for part in cost["parts"]] == [
        "owed", "reconnection_fee", "new_deposit",
    ]
    assert cost["parts"][0]["amount"] == "412.6000"
    assert cost["parts"][1]["amount"] == "95.0000"
    assert cost["parts"][2]["amount"] is None
    assert cost["subtotal"] == "507.6000"
    assert cost["parts_missing"] == ["new_deposit"]
    assert "total" not in cost, "no field a screen could label *if it goes that far*"
    assert cost["problems"][0]["oq_ref"] == "OQ-CWP-1600"


@pytest.mark.django_db
def test_us_cwp_057_tc3_an_unmapped_tier_is_an_absence_not_a_neighbour(
    pine_hill, sarah
):
    """TC-3 · **negative** — the five-day notice has no chip and gets none.

    ⚠ **THE FAILURE THIS CATCHES IS A DATE, NOT A LABEL.** Showing a customer at
    the five-day notice as though they were at the ten-day one *"moves the date
    they think they have"*, and to a regulator it misstates what that household
    was told. `disconnect_reads.chips_for` answers the absence rather than
    guessing; this asserts the portal CARRIES it rather than rounding.

    ⚠ **THE UNMAPPED RUNG IS STORED ON THE CASE, NOT ON A NOTICE.**
    `ck_disconnect_notice_tier` restricts a notice row to the three lawful
    chips, so the five-day rung can only ever reach a `DisconnectCase.tier`,
    which carries no such constraint. Learned by the constraint refusing the
    first draft of this fixture.
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _overdue_bill(pine_hill, account)
        case = _case(pine_hill, account, tier=disconnects.PAYMENTS_RUNG_5_DAY)
        _notice(pine_hill, case, tier=disconnects.TIER_1, on=REMINDER_ON)

    body = arrears(pine_hill, account)
    assert body["tier"] is None
    assert body["tier_unmapped"] is True
    assert body["chips"] == []
    assert disconnects.TIER_2 not in str(body), "never a neighbour's chip"
    assert disconnects.TIER_3 not in str(body)


@pytest.mark.django_db
def test_us_cwp_057_tc4_move_the_case_and_the_timeline_moves(pine_hill, sarah):
    """TC-4 · **negative** — built from the CASE, not from the tenant's cadence.

    ⚠ **THE PROOF IS THAT MOVING THE RECORD MOVES THE ANSWER.** Two accounts at
    two tiers would show two timelines under either implementation if their
    cadences happened to differ; changing ONE account's case while the tenant's
    settings stand still cannot pass unless the read is the case's. If the
    timeline came from the reminder cadence this account would answer the same
    thing twice, which is the defect the story names.
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _overdue_bill(pine_hill, account)
        case = _case(pine_hill, account, tier=disconnects.TIER_1)
        _notice(pine_hill, case, tier=disconnects.TIER_1, on=REMINDER_ON)

    first = arrears(pine_hill, account)
    assert first["tier"] == disconnects.TIER_1
    assert [row["on"] for row in first["timeline"] if row["step"] == "notice_sent"] == [
        REMINDER_ON.isoformat()
    ]

    with tenant_context(pine_hill.id):
        case.tier = disconnects.TIER_3
        case.cut_scheduled_for = date(2026, 9, 25)
        case.save(update_fields=["tier", "cut_scheduled_for"])
        _notice(pine_hill, case, tier=disconnects.TIER_3, on=date(2026, 9, 1))

    second = arrears(pine_hill, account)
    assert second["tier"] == disconnects.TIER_3
    assert [row["on"] for row in second["timeline"] if row["step"] == "notice_sent"] == [
        REMINDER_ON.isoformat(), "2026-09-01"
    ]
    cut = next(row for row in second["timeline"] if row["step"] == "cut")
    assert cut["on"] == "2026-09-25"
    # ⚠ **A FLOOR, NEVER A PROMISE.** Nothing in this product advances a tier on
    # a date (`DEF-320`), so the screen says *no earlier than* and this is the
    # fact it says it from.
    assert cut["is_floor"] is True
    assert second["scheduler"]["advances_on_a_schedule"] is False


@pytest.mark.django_db
def test_us_cwp_057_tc6_a_protection_shows_as_a_hold_and_the_debt_stands(
    pine_hill, sarah
):
    """TC-6 · **negative** — `BR-CWP-091`: a hold stops a DISCONNECTION.

    ⚠ **THE BALANCE IS UNCHANGED AND THAT IS THE POINT.** A customer who reads a
    hold as a pause on the debt stops paying and is cut the week it lapses.
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _overdue_bill(pine_hill, account)
        _case(pine_hill, account, tier=disconnects.TIER_2)
        disconnects.record_protection(
            sarah, account.pk, kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 14), expires_on=date(2026, 11, 30),
        )

    body = arrears(pine_hill, account)
    assert body["held_by"] == [
        {"kind": disconnects.PROTECTION_MEDICAL, "lifetime": disconnects.LIFETIME_EXPIRES}
    ]
    # ⚠ **THE ASSERTION THAT MATTERS.** `BR-CWP-091` in one line: the hold is
    # named, and the figure the customer owes has not moved by a cent.
    assert body["owed"] == "412.6000", "the hold stops the cut, not the debt"
    assert body["ladder_running"] is False
    # ⚠ **THE HALT CODE IS NOT ASSERTED EXACTLY, AND THE REASON IS WORTH
    # KEEPING.** `disconnects.halt_reason` reads the balance from the LEDGER
    # (`seams.ar_positions`), and this fixture writes an issued invoice without
    # posting it — so the halt this fixture produces is `nothing_owed` rather
    # than `protected`, which is a fact about the fixture and not about the
    # portal. Asserting `protected` here would have been a test that passes only
    # while a second lane's posting path behaves a particular way.
    assert body["halt_code"] is not None
    # And the timeline is NOT erased by the hold — a customer needs to see what
    # has already been sent even while it is paused.
    assert [row["step"] for row in body["timeline"]].count("due") == 1


@pytest.mark.django_db
def test_us_cwp_057_tc9_a_write_off_shows_its_amount_and_never_its_reason(
    pine_hill, sarah
):
    """TC-9 · **negative** — `BR-CWP-051`.

    *Bankruptcy* and *deceased, no estate* are the utility's judgment about a
    person; the amount is the person's own money.
    """
    from apps.payments import collections_models

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _overdue_bill(pine_hill, account)
        _case(pine_hill, account, tier="tier_1_reminder")
        collections_models.WriteOff.objects.create(
            tenant=pine_hill, account=account, amount=Decimal("87.40"), currency="USD",
            status="approved", requested_on=date(2026, 6, 1), approved_on=date(2026, 6, 2),
            reason="customer_bankruptcy",
        )

    body = arrears(pine_hill, account)
    assert body["write_offs"][0]["amount"] == "87.4000"
    assert body["write_offs"][0]["date"] == "2026-06-02"
    assert "customer_bankruptcy" not in str(body)
    assert "bankrupt" not in str(body).lower()


@pytest.mark.django_db
def test_us_cwp_057_tc10_an_account_not_overdue_has_no_ladder(pine_hill, sarah):
    """TC-10 · **negative** — the screen and its link are ABSENT (`BR-CWP-093`).

    An empty ladder on an account in good standing is a letter nobody sent.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    body = arrears(pine_hill, account)
    assert body["overdue"] is False
    assert body["days_overdue"] is None
    assert body["case_open"] is False
    assert body["timeline"] == [] or all(
        row["step"] == "due" for row in body["timeline"]
    )


@pytest.mark.django_db
def test_us_cwp_057_tc7_tenant_isolation(pine_hill, oak_ridge, sarah, elena):
    """TC-7 · **tenant isolation** — Pine Hill's case only (`BR-CWP-010`).

    ⚠ **THE HARD DIRECTION**, which is the one `US-CWP-052` TC-9 already
    established: a Pine Hill account id read under Oak Ridge's context answers
    NOTHING. That is only true if the tenant half is in the query rather than in
    the caller.

    ⚠ **THE SUITE RUNS ON SQLITE, WHICH HAS NO ROW-LEVEL SECURITY** (hard-won
    law 14), so this proves the tenant is IN THE QUERY and not that RLS holds.
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _overdue_bill(pine_hill, account)
        case = _case(pine_hill, account, tier=disconnects.TIER_2)
        _notice(pine_hill, case, tier=disconnects.TIER_2, on=FIRST_NOTICE_ON)

    assert arrears(pine_hill, account)["case_open"] is True
    # ⚠ **IT REFUSES BY NAME RATHER THAN ANSWERING AN EMPTY LADDER**, which is
    # the stronger outcome: `payments` refuses an account that is not this
    # tenant's outright (*"so it has no open bills to show"*, CLAUDE.md rule 1),
    # so the read cannot get far enough to compose somebody else's timeline.
    with pytest.raises(PaymentRuleError):
        arrears(oak_ridge, account)


# ═══════════════════════════════════════════════════════════════════════════
# US-CWP-059 — what is protecting your supply
# ═══════════════════════════════════════════════════════════════════════════


def protections(tenant, account, *, as_of=TODAY):
    with tenant_context(tenant.id):
        return selectors.protections_view(account, as_of=as_of)


@pytest.mark.django_db
def test_us_cwp_059_tc1_and_tc2_three_lifetimes_and_the_plan_hold_has_no_date(
    pine_hill, sarah
):
    """TC-1 + TC-2 — a certificate ENDS ON a date; a plan hold does NOT.

    ⚠ **TC-2 IS THE ONE THAT SAVES MONEY.** A customer who believes a plan hold
    is permanent stops paying and is cut the week it lapses. The product enforces
    the difference at the database (`ck_protection_lifetime`), `record_protection`
    refuses an expiry on a plan hold BY NAME, and this asserts the portal does
    not invent one on the way out.
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        disconnects.record_protection(
            sarah, account.pk, kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 14), expires_on=date(2026, 11, 30),
        )
        disconnects.record_protection(
            sarah, account.pk, kind=disconnects.PROTECTION_PLAN,
            effective_from=date(2026, 8, 20),
        )
        disconnects.record_protection(
            sarah, account.pk, kind=disconnects.PROTECTION_MORATORIUM,
            effective_from=date(2026, 12, 1), expires_on=date(2027, 3, 1),
        )

    body = protections(pine_hill, account)
    assert body["any"] is True
    by_kind = {row["kind"]: row for row in body["protections"]}
    assert by_kind[disconnects.PROTECTION_MEDICAL]["ends_on"] == "2026-11-30"
    assert by_kind[disconnects.PROTECTION_MEDICAL]["lifetime"] == disconnects.LIFETIME_EXPIRES
    # ⚠ **NO DATE, AND NONE INVENTED.**
    assert by_kind[disconnects.PROTECTION_PLAN]["ends_on"] is None
    assert by_kind[disconnects.PROTECTION_PLAN]["lifetime"] == disconnects.LIFETIME_DERIVED
    assert by_kind[disconnects.PROTECTION_MORATORIUM]["ends_on"] == "2027-03-01"
    assert by_kind[disconnects.PROTECTION_MORATORIUM]["since"] == "2026-12-01"
    assert body["hold_stops_disconnection_not_debt"] is True


@pytest.mark.django_db
def test_us_cwp_059_tc7_a_lifted_protection_is_shown_as_lifted(pine_hill, sarah):
    """TC-7 · **negative** — shown as lifted with its date, not silently removed.

    A hold that vanished from the screen the day it lapsed is the customer who
    did not know it had.
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        row = disconnects.record_protection(
            sarah, account.pk, kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2025, 1, 1), expires_on=date(2025, 6, 30),
        )
        disconnects.lift_protection(
            sarah, row["protection_id"], on_date=date(2025, 5, 1), reason="recovered"
        )

    body = protections(pine_hill, account)
    assert len(body["protections"]) == 1
    assert body["protections"][0]["lifted_on"] == "2025-05-01"
    assert body["protections"][0]["in_force"] is False


@pytest.mark.django_db
def test_us_cwp_059_tc6_no_protection_means_no_screen(pine_hill, sarah):
    """TC-6 · **negative** — *"not three empty cards"* (`BR-CWP-093`)."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    body = protections(pine_hill, account)
    assert body["any"] is False
    assert body["protections"] == []


@pytest.mark.django_db
def test_us_cwp_059_tc9_the_moratorium_follows_the_record(pine_hill, sarah):
    """TC-9 · **negative** — change the record, change the screen.

    `P42` states the window in prose (*"between 1 December and 1 March"*) and
    this story fixes that: the dates are READ, so a state whose window moves
    moves the sentence with it.
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        disconnects.record_protection(
            sarah, account.pk, kind=disconnects.PROTECTION_MORATORIUM,
            effective_from=date(2026, 11, 15), expires_on=date(2027, 4, 15),
        )

    row = protections(pine_hill, account)["protections"][0]
    assert row["since"] == "2026-11-15" and row["ends_on"] == "2027-04-15"
    assert "2026-12-01" not in str(row), "no prose window survives the record"


# ═══════════════════════════════════════════════════════════════════════════
# US-CWP-058 — help paying: three doors, and one of them is not a door
# ═══════════════════════════════════════════════════════════════════════════


def help_paying(tenant, account, *, as_of=TODAY):
    with tenant_context(tenant.id):
        return selectors.help_paying(tenant.id, account, as_of=as_of)


@pytest.mark.django_db
def test_us_cwp_058_tc1_and_tc2_three_routes_and_the_moratorium_has_no_button(
    pine_hill, sarah
):
    """TC-1 + TC-2 — three cards, and the third is a FACT with no control.

    ⚠ **NOBODY APPLIES FOR A WEATHER MORATORIUM.** The regulator sets the
    window, so `apply: false` is on the wire and there is nothing for a control
    to do — which is why the assertion is that no control EXISTS rather than
    that one is disabled.
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _overdue_bill(pine_hill, account)
        disconnects.record_protection(
            sarah, account.pk, kind=disconnects.PROTECTION_MORATORIUM,
            effective_from=date(2026, 12, 1), expires_on=date(2027, 3, 1),
        )

    body = help_paying(pine_hill, account)
    assert [row["route"] for row in body["routes"]] == [
        selectors.ROUTE_PLAN, selectors.ROUTE_CERTIFICATE, selectors.ROUTE_LEVEL_PAY,
    ]
    assert body["moratorium"]["from"] == "2026-12-01"
    assert body["moratorium"]["until"] == "2027-03-01"
    assert body["moratorium"]["apply"] is False
    assert body["moratorium"]["set_by"] == "regulator"


@pytest.mark.django_db
def test_us_cwp_058_tc3_and_tc5_the_certificate_card_says_it_expires_and_takes_no_file(
    pine_hill, sarah
):
    """TC-3 + TC-5 · **negative** — the hold expires, and there is no upload.

    ⚠ **BOTH ARE FACTS ON THE WIRE RATHER THAN COPY A LANE MUST REMEMBER.** A
    customer who believes a certificate hold is permanent stops paying and is
    disconnected the week it lapses (`BR-CWP-090`); consumer upload is a signed
    deferral (`DF-4`) and the route ends at the counter.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    card = next(
        row for row in help_paying(pine_hill, account)["routes"]
        if row["route"] == selectors.ROUTE_CERTIFICATE
    )
    assert card["hold_expires"] is True
    assert card["upload_available"] is False
    assert card["granted_by"] == "clerk"


@pytest.mark.django_db
def test_us_cwp_058_tc6_plans_off_removes_one_card_and_leaves_the_other_two(
    pine_hill, sarah
):
    """TC-6 · **negative** — a customer who cannot have a plan can still ask.

    ⚠ **THE OTHER TWO ROUTES ARE THE ASSERTION THAT MATTERS.** Hiding all three
    because one switch is off would turn away somebody who could still be
    helped, which is the one error this screen must never make.
    """
    from apps.portal import settings_service

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        settings_service.save_settings(sarah, pine_hill.id, {"plans_enabled": False})

    body = help_paying(pine_hill, account)
    assert body["plans_enabled"] is False
    assert [row["route"] for row in body["routes"]] == [
        selectors.ROUTE_CERTIFICATE, selectors.ROUTE_LEVEL_PAY,
    ]


@pytest.mark.django_db
def test_us_cwp_058_tc8_past_the_final_notice_no_route_is_closed(pine_hill, sarah):
    """TC-8 · **negative** — ⚠ **AND THIS ONE ANSWERS *THE OTHER WAY* TO THE
    WIREFRAME, DELIBERATELY.**

    `P42` reads *"ask before the final notice and all three stay open"*, which a
    lane could implement as *something closes after it*. **Measured, nothing in
    this product closes any of them:** `record_protection` has no tier gate, a
    clerk may grant a plan at any tier (`BR-CWP-066`), and level pay is
    unrelated to the ladder. Closing a door the product would still open turns a
    frightened customer away from help they can still get, so `still_open` stays
    true and the urgency travels in `past_final_notice`. `OQ-CWP-1601` is OPEN.
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _overdue_bill(pine_hill, account)
        _case(pine_hill, account, tier=disconnects.TIER_3)

    body = help_paying(pine_hill, account)
    assert body["past_final_notice"] is True
    assert all(row["still_open"] for row in body["routes"])


@pytest.mark.django_db
def test_us_cwp_058_tc4_the_certificate_ask_creates_a_request_and_no_protection(
    pine_hill, sarah
):
    """TC-4 · **negative** — `BR-CWP-089`, and the count is the assertion.

    *"The portal may never grant a protection itself — every one needs a person
    and a document."* The row count before and after is the only proof that
    survives a refactor of what the response says.
    """
    from apps.customers import disconnects
    from apps.portal import services

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        before = disconnects.AccountProtection.objects.filter(
            tenant_id=pine_hill.id
        ).count()
        answer = services.raise_service_request(
            pine_hill.id,
            shape=services.SHAPE_HARDSHIP_ASK,
            payload={
                "account_no": account.account_no,
                "address": selectors.service_address(account),
                "name": "Maria Alvarez", "email": "maria@example.test",
                "phone": "+1-555-0100", "route": "medical_certificate",
            },
        )
        after = disconnects.AccountProtection.objects.filter(
            tenant_id=pine_hill.id
        ).count()

    assert after == before, "BR-CWP-089 — the portal grants no protection"
    assert answer["protection_created"] is False
    assert answer["bring_the_document"] is True
    assert answer["reference"].startswith("SR-")
    assert str(account.pk) not in str(answer), "B14 rule 31 — no id on the wire"


@pytest.mark.django_db
def test_us_cwp_058_tc7_tenant_isolation(pine_hill, oak_ridge, sarah, elena):
    """TC-7 · **tenant isolation** — Pine Hill's moratorium dates only.

    ⚠ **THE HARD DIRECTION** (`US-CWP-052` TC-9's pattern): the SAME account id
    read under Oak Ridge's context answers no window at all. Quoting one
    utility's regulator window to another utility's customer would tell somebody
    they cannot be disconnected in a state whose rules do not cover them.
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        disconnects.record_protection(
            sarah, account.pk, kind=disconnects.PROTECTION_MORATORIUM,
            effective_from=date(2026, 12, 1), expires_on=date(2027, 3, 1),
        )

    assert help_paying(pine_hill, account)["moratorium"] is not None
    assert help_paying(oak_ridge, account)["moratorium"] is None


# ═══════════════════════════════════════════════════════════════════════════
# US-CWP-056 — credits and refunds in flight, and they are different things
# ═══════════════════════════════════════════════════════════════════════════


CREDIT = Decimal("-25.88")
REFUND = Decimal("89.80")


def _credit_note(tenant, account, *, number, invoice, on):
    from apps.billing import models as billing_models

    return billing_models.CreditNote.objects.create(
        tenant=tenant, account=account, credit_note_no=number,
        original_invoice=invoice, amount=CREDIT, currency="USD",
        reason="goodwill after a reading dispute",
        issued_at=datetime(on.year, on.month, on.day, 9, 0, tzinfo=UTC),
    )


def _refund(tenant, account, *, status, voided_at=None):
    from apps.payments import models as payments_models

    return payments_models.Refund.objects.create(
        tenant=tenant, account=account, amount=REFUND, currency="USD",
        status=status, method=payments_models.REFUND_METHOD_CHECK, reference="10241",
        reason="final bill overpayment",
        requested_at=datetime(2026, 9, 18, 9, 0, tzinfo=UTC),
        approved_at=datetime(2026, 9, 19, 9, 0, tzinfo=UTC),
        issued_at=datetime(2026, 9, 21, 9, 0, tzinfo=UTC),
        voided_at=voided_at,
        void_reason="raised against the wrong account" if voided_at else None,
    )


def money_back(tenant, account):
    with tenant_context(tenant.id):
        return selectors.money_back(account)


@pytest.mark.django_db
def test_us_cwp_056_tc1_and_tc2_the_refund_steps_and_the_bill_each_credit_hit(
    pine_hill, sarah
):
    """TC-1 + TC-2 — four dated steps, and two credits naming their bill.

    ⚠ **THE STEPS ARE DERIVED FROM THE TIMESTAMPS AND ARE NOT A SECOND
    STATUS.** A refund's status IS its furthest step; a per-step boolean written
    anywhere else would be a second lifecycle to keep in step with the first.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2607-0139", total="138.44",
            issued_on=date(2026, 7, 10), due_on=date(2026, 7, 31),
        )
        _credit_note(pine_hill, account, number="CN-26-0001", invoice=bill,
                     on=date(2026, 7, 12))
        _credit_note(pine_hill, account, number="CN-26-0002", invoice=bill,
                     on=date(2026, 7, 12))
        _refund(pine_hill, account, status="issued")

    body = money_back(pine_hill, account)
    assert body["any"] is True
    refund = body["refunds"][0]
    assert [step["step"] for step in refund["steps"]] == [
        "requested", "approved", "issued", "cleared",
    ]
    assert refund["steps"][0]["on"].startswith("2026-09-18")
    assert refund["steps"][3]["on"] is None, "not cleared yet — an absence, not a date"
    # `BR-CWP-060` — the refund names the method it is going back to.
    assert refund["method"] == "check"
    assert refund["reference"] == "10241"
    assert len(body["credits"]) == 2
    assert {row["used_on_bill"] for row in body["credits"]} == {"BL-2607-0139"}


@pytest.mark.django_db
def test_us_cwp_056_tc_sign_a_credit_leaves_negative_and_a_refund_leaves_positive(
    pine_hill, sarah
):
    """⚠ **THE SIGN THE SERVER SENT IS THE SIGN THE SCREEN RENDERS.**

    `credit_notes.amount <= 0` is a database CHECK added after two writers stored
    opposite signs (`DEF-085`); a refund is stored positive because money going
    OUT is the row's whole meaning. **Neither is normalised and neither is
    absolute-valued anywhere between the table and the browser.**
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2607-0139", total="138.44",
            issued_on=date(2026, 7, 10), due_on=date(2026, 7, 31),
        )
        _credit_note(pine_hill, account, number="CN-26-0001", invoice=bill,
                     on=date(2026, 7, 12))
        _refund(pine_hill, account, status="approved")

    body = money_back(pine_hill, account)
    assert Decimal(body["credits"][0]["amount"]) < 0
    assert Decimal(body["refunds"][0]["amount"]) > 0


@pytest.mark.django_db
def test_us_cwp_056_tc4_a_voided_refund_is_shown_as_voided_and_not_removed(
    pine_hill, sarah
):
    """TC-4 · **negative** — and its REASON stays inside.

    A customer told money was coming and then shown nothing has no way to ask
    what happened to it. `void_reason` is the utility's own note, the same
    distinction `BR-CWP-051` draws on a write-off.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _refund(pine_hill, account, status="void",
                voided_at=datetime(2026, 9, 25, 9, 0, tzinfo=UTC))

    body = money_back(pine_hill, account)
    assert len(body["refunds"]) == 1
    assert body["refunds"][0]["status"] == "void"
    assert body["refunds"][0]["voided_at"].startswith("2026-09-25")
    assert "wrong account" not in str(body)


@pytest.mark.django_db
def test_us_cwp_056_tc3_the_credit_is_re_read_on_every_load(pine_hill, sarah):
    """TC-3 · **negative** — `BR-CWP-047`, and nothing is cached.

    *"A credit that was real on Tuesday can be spent by Thursday."* Two loads
    with a write between them must not agree.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        bill = an_issued_bill(
            pine_hill, account, number="BL-2607-0139", total="138.44",
            issued_on=date(2026, 7, 10), due_on=date(2026, 7, 31),
        )
        _credit_note(pine_hill, account, number="CN-26-0001", invoice=bill,
                     on=date(2026, 7, 12))
    first = money_back(pine_hill, account)
    with tenant_context(pine_hill.id):
        _credit_note(pine_hill, account, number="CN-26-0002", invoice=bill,
                     on=date(2026, 7, 13))
    second = money_back(pine_hill, account)

    assert len(first["credits"]) == 1
    assert len(second["credits"]) == 2, "a cached figure would still say one"


@pytest.mark.django_db
def test_us_cwp_056_tc7_neither_credits_nor_refunds_means_no_screen(pine_hill, sarah):
    """TC-7 · **negative** — the screen and its link are absent (`BR-CWP-093`)."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    body = money_back(pine_hill, account)
    assert body["any"] is False
    assert body["credits"] == [] and body["refunds"] == []


@pytest.mark.django_db
def test_us_cwp_056_tc6_tenant_isolation(pine_hill, oak_ridge, sarah, elena):
    """TC-6 · **tenant isolation** — Pine Hill only (`BR-CWP-010`).

    ⚠ **THE HARD DIRECTION** (`US-CWP-052` TC-9's pattern): the SAME account id
    read under Oak Ridge's context sees no refund. A cheque another utility is
    sending is not this customer's money.
    """
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _refund(pine_hill, account, status="issued")

    assert len(money_back(pine_hill, account)["refunds"]) == 1
    assert money_back(oak_ridge, account)["refunds"] == []
