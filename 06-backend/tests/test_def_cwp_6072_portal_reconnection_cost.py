# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CWP-6072 — CWP-057's *What it would cost* adds a reconnection
#           fee the balance it is adding to already holds. Screen: CWP-057
#           (`P43`, the rail panel · `testKey` if-it-goes-that-far)
# Rules:    CLAUDE.md hard rule 2 (money 4 dp stored, 2 dp displayed) · hard
#           rule 4 (this path writes nothing — it is a READ) · BR-CUS-104 (PO
#           2026-08-25) · PO ruling 2026-08-27 / DEF-708 (the cut RAISES and
#           ISSUES the fee) · BR-CWP-093 (an absence is an absence)
# Open:     OQ-CWP-1600 (nothing in this product prices a reconnection deposit)
# Tests:    this file
# Impacts:  apps/portal/selectors.py :: _if_it_goes_that_far · arrears_position
# ───────────────────────────────────────────────────────
"""**THE SAME $75.00, COUNTED TWICE, ON THE CUSTOMER'S OWN SCREEN.**

`commit_cut` raises and ISSUES the reconnection fee inside the cut's own
transaction (DEF-708, PO ruling 2026-08-27). From that instant the fee is an
OPEN BILL, so the portal's balance read already contains it — and
`_if_it_goes_that_far` went on adding it a second time.

Measured on `A-11340` / `DSC-26-0001` on 2026-09-20, after the first cut this
product has ever completed: **owed `$75.00` + reconnection fee `$75.00` =
subtotal `$150.00`**, where the `$75.00` owed **IS** the fee bill the cut
issued.

⚠ **IT WAS LATENT RATHER THAN LIVE, WHICH IS WHY IT HAD TO BE FIXED NOW.** The
screen returns its empty state unless `overdue` is true, and the fee bill is due
on the day of the cut, so on 2026-09-20 nothing rendered. It fires on the first
day that account carries any other past-due bill, which is the ordinary case.

**THE SHAPE, AND IT IS THE STAFF FIX'S (`DEF-CUS-6050`, commit 7bd236063).** A
figure built by ADDING two sources has to know whether they overlap, and the
overlap is created by the very act the figure describes. `customers` now
publishes that fact — `reconnection_terms()['to_clear']['basis']
['fee_in_arrears']`, keyed on `case.cut_on` and not on a list of states — so
this screen READS it instead of deriving a third copy. Two copies of this
arithmetic is how the staff figures came to disagree; the fix there deleted one,
and this one must not add it back.

⚠ **THE FEE IS STILL SHOWN.** A customer must be able to see what they are
being charged, so the row keeps its amount and is marked as already inside the
figure; it is the SUM that stops adding it.

PROVED RED FIRST, through pytest, which is the harness that runs it — the
failures are quoted in the lane report.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.portal import selectors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import an_issued_bill, elm_street_account, switch_on

pytestmark = pytest.mark.django_db

#: The tenant's own configured price. **Never a literal in the assertions** —
#: `BR-BIL-007`, and the portal reads whatever the utility configured.
RECONNECT_FEE = Decimal("95.00")
#: `A-11340`'s real shape after its cut: the ONLY open bill is the fee bill, so
#: what the customer owes and what the fee is are the SAME money seen twice.
FEE_BILL_DUE_ON = date(2026, 8, 14)
TODAY = date(2026, 9, 2)


def _charge(tenant):
    """The tenant's reconnection charge, at THIS test's price.

    ⚠ **`update_or_create`, NOT `create`** — the shared fixtures already seed a
    row on this code for some tenants, and a bare insert dies on
    `charges.tenant_id, charges.code`. The price is still read from the
    catalogue by the product (`BR-BIL-007`); nothing here is a literal in the
    assertions.
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


def _no_charge(tenant):
    """The tenant has NO reconnection charge at all — `TC-5`'s world.

    The row is REMOVED rather than the assertions relaxed, which is
    `_scheduled(charge=False)`'s posture on the staff side for `DEF-705`'s
    reason: a test that waters down its expectations to match a fixture proves
    the fixture.
    """
    from apps.customers import disconnects
    from apps.rating import models as rating_models

    with tenant_context(tenant.id):
        # CR-156-BRC10 — a flat amount is an *All sizes* row now (PROTECT FK).
        rating_models.ChargeCodeAmount.objects.filter(charge__code=disconnects.RECONNECT_CHARGE_CODE).delete()
        rating_models.Charge.objects.filter(code=disconnects.RECONNECT_CHARGE_CODE).delete()


def _fee_bill(tenant, account):
    """The bill `commit_cut` issues — the reason the position already holds it."""
    return an_issued_bill(
        tenant, account, number="BL-2609-000081", total=str(RECONNECT_FEE),
        issued_on=date(2026, 7, 31), due_on=FEE_BILL_DUE_ON,
    )


def _case(tenant, account, *, cut_on):
    """One disconnection case, cut or not cut.

    ⚠ **`cut_on` IS THE ONLY THING THAT VARIES BETWEEN THE TWO CASES BELOW**,
    deliberately: it is the fact `commit_cut` writes in the same transaction
    that issues the fee, and nothing else writes it.
    """
    from apps.customers import disconnects

    #: ⚠ **`ck_cut_records_the_price_of_coming_back`** — a cut case MUST carry
    #: the deposit election and the price it was cut at. That is the schema
    #: saying what `commit_cut` writes, and a fixture that dodged it would be
    #: testing a state the product cannot produce.
    cut_facts = (
        {}
        if cut_on is None
        else {
            "deposit_disposition": disconnects.DEPOSIT_HELD,
            "reconnection_fee_amount": RECONNECT_FEE,
            "reconnection_fee_code": disconnects.RECONNECT_CHARGE_CODE,
        }
    )
    return disconnects.DisconnectCase.objects.create(
        tenant=tenant,
        account=account,
        case_no="DSC-26-0001",
        sequence=disconnects.SEQ_SERVICE,
        state=disconnects.STATE_NOTICE_SENT if cut_on is None else disconnects.STATE_CUT,
        tier=disconnects.TIER_2,
        tier_reached_on=date(2026, 8, 21),
        amount_owed_at_open=RECONNECT_FEE,
        currency="USD",
        opened_on=date(2026, 8, 21),
        cut_on=cut_on,
        **cut_facts,
    )


def _cost(tenant, account):
    with tenant_context(tenant.id):
        return selectors.arrears_position(account, as_of=TODAY)["cost"]


def _row(cost, part):
    return next(row for row in cost["parts"] if row["part"] == part)


def test_tc1_after_the_cut_the_fee_is_not_added_to_a_balance_that_holds_it(
    pine_hill, sarah
):
    """TC-1 · **THE DEFECT.** Owed `$95.00`, fee `$95.00`, subtotal `$95.00`.

    The one open bill IS the fee bill, which is `A-11340`'s measured shape. The
    pre-fix answer was `$190.00` — the same money quoted twice to a frightened
    customer on the screen that tells them what getting their supply back costs.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _charge(pine_hill)
    with tenant_context(pine_hill.id):
        _fee_bill(pine_hill, account)
        _case(pine_hill, account, cut_on=date(2026, 8, 25))

    cost = _cost(pine_hill, account)
    assert _row(cost, "owed")["amount"] == "95.0000"
    assert cost["subtotal"] == "95.0000", (
        "after the cut the fee is an ISSUED bill and is already in what the "
        "customer owes; adding it again quotes one whole fee too much"
    )
    assert cost["subtotal"] != "190.0000"


def test_tc2_the_fee_is_still_shown_and_is_marked_as_already_inside_the_figure(
    pine_hill, sarah
):
    """TC-2 · **NOT ADDED IS NOT THE SAME AS NOT SHOWN.**

    A customer must be able to see what they are being charged. Dropping the row
    would leave the panel unable to say the fee exists at all; leaving it
    unmarked would leave a reader with arithmetic that does not add up. The row
    keeps its amount and carries `already_owed`.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _charge(pine_hill)
    with tenant_context(pine_hill.id):
        _fee_bill(pine_hill, account)
        _case(pine_hill, account, cut_on=date(2026, 8, 25))

    cost = _cost(pine_hill, account)
    fee = _row(cost, "reconnection_fee")
    assert fee["amount"] == "95.0000", "the fee is still stated"
    assert fee["already_owed"] is True
    assert _row(cost, "owed")["already_owed"] is False
    assert _row(cost, "new_deposit")["already_owed"] is False
    #: ⚠ **THE FEE IS NOT IN `parts_missing`.** It is not missing from the
    #: total — it is INSIDE it. Naming it as missing would tell the customer
    #: there is another fee still to come.
    assert cost["parts_missing"] == ["new_deposit"]


def test_tc3_before_the_cut_nothing_changes_and_the_fee_is_still_added(
    pine_hill, sarah
):
    """TC-3 · **THE OTHER SIDE OF THE CUT, PINNED SO THE FIX CANNOT OVERSHOOT.**

    Before the cut the fee is a QUOTE: the ledger and the bills both exclude it,
    and a total that dropped it would quote a price short by the whole fee —
    which is `DEF-708`'s own shape, the gate that let somebody back in short.
    Owed `$95.00` + fee `$95.00` = `$190.00`.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _charge(pine_hill)
    with tenant_context(pine_hill.id):
        _fee_bill(pine_hill, account)
        _case(pine_hill, account, cut_on=None)

    cost = _cost(pine_hill, account)
    assert cost["subtotal"] == "190.0000"
    assert _row(cost, "reconnection_fee")["already_owed"] is False


def test_tc4_the_basis_rides_the_payload_and_names_which_question_was_answered(
    pine_hill, sarah
):
    """TC-4 · **THE PORTAL QUOTES THE MODULE AND DERIVES NOTHING.**

    `customers` decides whether the fee has reached the books, off `case.cut_on`
    — the fact `commit_cut` writes, never a list of states (`DEF-CUS-6050`). The
    portal carries that answer through so a later reader can see WHICH question
    the subtotal answered rather than inferring it.
    """
    from apps.customers import disconnects

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _charge(pine_hill)
    with tenant_context(pine_hill.id):
        _fee_bill(pine_hill, account)
        _case(pine_hill, account, cut_on=date(2026, 8, 25))

    cost = _cost(pine_hill, account)
    assert cost["basis"]["fee_in_arrears"] is True
    assert cost["basis"]["code"] == disconnects.TO_CLEAR_AFTER_THE_CUT["code"]


def test_tc5_a_cut_with_no_readable_fee_still_states_the_total(pine_hill, sarah):
    """TC-5 · **AN UNREADABLE FEE AFTER THE CUT SUBTRACTS NOTHING.**

    The fee is already inside what the customer owes, so a catalogue row edited
    or deleted months later cannot blank out the figure — and the fee is NOT
    reported as a part missing from the total, because it is not missing from
    it. (Before the cut the opposite holds and `US-CWP-057` TC-2 pins it: a sum
    over one known half quotes a price short by the whole fee.)
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _no_charge(pine_hill)
    with tenant_context(pine_hill.id):
        _fee_bill(pine_hill, account)
        _case(pine_hill, account, cut_on=date(2026, 8, 25))

    cost = _cost(pine_hill, account)
    assert _row(cost, "reconnection_fee")["amount"] is None
    assert _row(cost, "reconnection_fee")["already_owed"] is True
    assert cost["subtotal"] == "95.0000"
    assert cost["parts_missing"] == ["new_deposit"]


def test_tc6_every_amount_leaves_at_four_decimals_and_none_at_six(pine_hill, sarah):
    """TC-6 · hard rule 2 — 4 dp stored on the wire, never a raw `Decimal`.

    The staff fix caught a six-decimal `Decimal` about to reach a clerk on this
    same figure. Nothing here may print one: every amount is a string quantized
    to four decimals, and the screen does the 2 dp.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _charge(pine_hill)
    with tenant_context(pine_hill.id):
        _fee_bill(pine_hill, account)
        _case(pine_hill, account, cut_on=date(2026, 8, 25))

    cost = _cost(pine_hill, account)
    amounts = [row["amount"] for row in cost["parts"]] + [cost["subtotal"]]
    for amount in amounts:
        if amount is None:
            continue
        assert isinstance(amount, str), f"{amount!r} is not a string"
        assert Decimal(amount) == Decimal(amount).quantize(Decimal("0.0001"))
        assert len(amount.split(".")[1]) == 4, f"{amount!r} is not four decimals"


def test_tc7_this_read_writes_nothing(pine_hill, sarah):
    """TC-7 · hard rule 4 — the panel is a READ.

    Row counts on every table a reconnection figure could touch are identical
    either side of the call. The staff fix says the same of its own half: *"no
    row, no journal line, no audit row."*
    """
    from apps.billing import models as billing_models
    from apps.customers import disconnects
    from apps.ledger import models as ledger_models
    from apps.audit import models as audit_models
    from apps.payments import models as payment_models

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _charge(pine_hill)
    with tenant_context(pine_hill.id):
        _fee_bill(pine_hill, account)
        _case(pine_hill, account, cut_on=date(2026, 8, 25))

    tables = (
        billing_models.Invoice,
        ledger_models.JournalEntry,
        ledger_models.JournalLine,
        payment_models.Payment,
        audit_models.AuditLog,
        disconnects.DisconnectCase,
    )
    with tenant_context(pine_hill.id):
        before = [model.objects.count() for model in tables]
    _cost(pine_hill, account)
    with tenant_context(pine_hill.id):
        after = [model.objects.count() for model in tables]
    assert before == after
