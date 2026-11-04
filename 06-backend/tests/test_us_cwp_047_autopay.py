# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-047 (EP-CWP-09) — autopay: an intent that already exists,
#           waiting for a charge that does not. Screen: CWP-040
# Rules:    BR-CWP-056 (visible, disabled, carrying its reason — never
#           live-but-inert) · BR-PAY-015 (autopay v1 is a capture-INTENT; the
#           row IS the W7 contract, so `amount` and `scheduled_on` are STORED) ·
#           BR-PAY-013 (the Nth bounce puts an account cash-only and off
#           autopay; no rule ever auto-clears it) · BR-CUS-059 (enrolment is
#           capture-only) · BR-CWP-010 (tenant AND account in the query) ·
#           BR-CWP-047 (never cached) · CLAUDE.md hard rule 2
# Cases:    TC-1 the held control · TC-2 the scheduled row · TC-3 the unbilled
#           month · ⚠ TC-4 the correction the intent does NOT follow ·
#           TC-5 no settable date · TC-6 two bounces · TC-7 cash-only ·
#           TC-8 tenant isolation · TC-9 the ceiling that has no column
# ───────────────────────────────────────────────────────
"""**THE ONE CASE THIS FILE EXISTS FOR IS TC-4, AND IT IS A NEGATIVE.**

`BR-PAY-015` stores `amount` and `scheduled_on` on the intent rather than
recomputing them, so *what the customer was told would be drafted* survives a
later correction to the bill. A read that recomputed from the invoice would pass
every other case in this file and fail only the one that matters — silently, on
a customer's money.

⚠ **AND THE HELD CONTROL HAS AN EXPIRY TEST** (hard-won law 2's mirror,
`DEF-CWP-3925`): *"when you write a hold, write the test that fires when the
hold expires, in the same commit"*. The hold here is *no rails*, and the thing
that changes on the day rails land is `models.INTENT_STATUSES` — a status set
that can express a charge. `test_tc1_the_hold_expires_when_the_status_set_grows`
goes RED that day and names the control, which is the only mechanical way this
screen can be told its refusal has stopped being true.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.payments import autopay, models as payments_models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import an_issued_bill, elm_street_account

#: `US-CWP-047` §4 — the story's own fixture.
SEPTEMBER_TOTAL = Decimal("142.18")
SEPTEMBER_DUE = date(2026, 9, 14)
#: TC-4: the SAME bill, corrected afterwards. The intent must not follow it.
CORRECTED_TOTAL = Decimal("138.00")
TODAY = date(2026, 9, 2)


def _enrolled(tenant, account):
    with tenant_context(tenant.id):
        account.autopay = True
        account.save(update_fields=["autopay"])
    return account


def _september_intent(tenant, account):
    """The intent bill issue would have written — through the published door."""
    bill = an_issued_bill(
        tenant,
        account,
        number="BL-2608-0141",
        total=str(SEPTEMBER_TOTAL),
        issued_on=date(2026, 8, 31),
        due_on=SEPTEMBER_DUE,
    )
    with tenant_context(tenant.id):
        autopay.record_intent_at_issue(
            account_id=account.pk,
            invoice_id=bill.pk,
            amount=SEPTEMBER_TOTAL,
            due_date=SEPTEMBER_DUE,
        )
    return bill


def position(tenant, account, *, today=TODAY):
    with tenant_context(tenant.id):
        return autopay.portal_position(account_id=account.pk, today=today)


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 · TODAY, WITH NO RAILS
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc1_the_control_is_held_and_the_real_intent_still_shows(pine_hill, sarah):
    """The switch is refused BY NAME and the *next few* table is still real."""
    account = _enrolled(pine_hill, elm_street_account(pine_hill, sarah))
    _september_intent(pine_hill, account)

    body = position(pine_hill, account)

    assert body["available"] is False
    assert body["held_reason"] == autopay.HELD_NO_AUTOMATIC_CHARGE
    # ⚠ Visible, disabled, carrying its reason — never hidden (BR-CWP-056).
    assert any(one["code"] == "no_charging_path_before_rails" for one in body["problems"])
    # The refusal does not empty the table it sits beside.
    assert body["next_few"][0]["amount"] == "142.1800"


@pytest.mark.django_db
def test_tc1_the_hold_expires_when_the_status_set_grows():
    """⚠ **THE HOLD'S OWN EXPIRY TEST** (hard-won law 2, `DEF-CWP-3925`).

    `HELD_NO_AUTOMATIC_CHARGE` is true only while nothing DRAFTS a payment on
    its own, and `BR-PAY-015` makes that structural: the intent carries ONE
    status, so nothing can record that a draft was attempted, succeeded or
    failed. The day a second status arrives, something is consuming intents and
    this screen's refusal has stopped being true — **the suite goes red here and
    names the control**, rather than the customer meeting a greyed switch over a
    working drafter for a week.

    ⚠ **THE SENTINEL IS THE STATUS SET AND NOT THE EXISTENCE OF A GATEWAY**, and
    that distinction was learned the same day: `apps/payments/gateway.py` landed
    hours after this file was written, and it charges when a CUSTOMER PRESSES A
    BUTTON. That is not autopay, and a test watching the module would have gone
    red over a control whose refusal was still perfectly true.
    """
    assert payments_models.INTENT_STATUSES == (payments_models.INTENT_AWAITING_RAILS,), (
        "a second intent status means something drafts payments now: CWP-040's "
        "Turn autopay on control (HELD_NO_AUTOMATIC_CHARGE in "
        "apps/payments/autopay.py and its catalogue sentence) must be released "
        "in the same commit"
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 / TC-3 · THE *NEXT FEW* TABLE
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc2_the_scheduled_row_is_the_bill_the_customer_was_told(pine_hill, sarah):
    """`14 Sep 2026 · $142.18 · SCHEDULED` — the story's own row."""
    account = _enrolled(pine_hill, elm_street_account(pine_hill, sarah))
    _september_intent(pine_hill, account)

    row = position(pine_hill, account)["next_few"][0]

    assert row["scheduled_on"] == "2026-09-14"
    assert row["amount"] == "142.1800"  # 4 stored, hard rule 2
    assert row["display"] == "$142.18"  # 2 displayed
    assert row["state"] == autopay.SLOT_SCHEDULED


@pytest.mark.django_db
def test_tc3_the_unbilled_month_carries_no_amount_and_no_invented_date(pine_hill, sarah):
    """`— · NOT BILLED YET` — ⚠ **not an estimate**, and not an invented date.

    The story draws `14 Oct 2026` beside the em dash. **Nothing in this product
    answers what an account's NEXT due date is before the bill is made**: the
    intent is written AT ISSUE (`BR-PAY-015`), and re-deriving billing's
    schedule inside payments would be a second implementation of when a bill
    falls due — the exact thing `CR-068` §2d forbids for money and for the same
    reason. So the row is drawn, the state is real, and the DATE is a stated
    absence rather than a guess.
    """
    account = _enrolled(pine_hill, elm_street_account(pine_hill, sarah))
    _september_intent(pine_hill, account)

    body = position(pine_hill, account)
    ahead = body["next_few"][1]

    assert ahead["state"] == autopay.SLOT_NOT_BILLED_YET
    # ⚠ NEVER an estimate: no amount, and no `0.0000` either.
    assert ahead["amount"] is None
    assert ahead["display"] is None
    assert ahead["scheduled_on"] is None
    assert any(one["code"] == autopay.NEXT_DUE_DATE_NOT_HELD for one in body["problems"])


# ═══════════════════════════════════════════════════════════════════════════
# ⚠ TC-4 · THE CORRECTION THE INTENT DOES NOT FOLLOW
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc4_correcting_the_bill_does_not_move_what_the_customer_was_told(pine_hill, sarah):
    """⚠ **THE CASE THIS FILE EXISTS FOR.**

    `BL-2608-0141` issues at `$142.18`, the intent is written, and the bill is
    then corrected to `$138.00`. The screen still says **`$142.18`** — because
    that is what the customer was told would be drafted, and `BR-PAY-015` makes
    the stored row the W7 contract.
    """
    from apps.billing import models as billing_models

    account = _enrolled(pine_hill, elm_street_account(pine_hill, sarah))
    bill = _september_intent(pine_hill, account)

    with tenant_context(pine_hill.id):
        billing_models.Invoice.objects.filter(pk=bill.pk).update(
            subtotal=CORRECTED_TOTAL, total=CORRECTED_TOTAL
        )

    row = position(pine_hill, account)["next_few"][0]

    assert row["amount"] == "142.1800", (
        "the intent silently followed the correction — a read that recomputes "
        "from the invoice would charge an amount the customer was never shown"
    )
    assert row["display"] == "$142.18"


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 · THE DATE IS NOT SETTABLE
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc5_when_is_the_due_date_and_nothing_offers_to_change_it(pine_hill, sarah):
    """*Always the due date. It cannot be changed.* — stated as DATA, so no lane
    has to remember not to draw the control (`availability.py`'s own posture)."""
    account = _enrolled(pine_hill, elm_street_account(pine_hill, sarah))
    _september_intent(pine_hill, account)

    body = position(pine_hill, account)

    assert body["when"] == autopay.WHEN_DUE_DATE
    assert body["when_settable"] is False


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 / TC-7 · TWO BOUNCES, AND THE SCREEN SAYS WHY
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc6_tc7_a_cash_only_account_is_refused_and_the_reason_names_the_bounces(pine_hill, sarah):
    """⚠ **THE REASON NAMES THE BOUNCES, NOT A CODE** (`BR-PAY-013`).

    `cash_only_no_autopay` is the PRIVILEGE SANCTION and `autopay` stays exactly
    as the customer left it — an enrolled account under the sanction is *not
    autopayable*, which is `is_enrolled`'s own reading. The count travels so the
    catalogue can write *two payments have bounced* in eleven languages.
    """
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        account.autopay = True
        account.cash_only_no_autopay = True
        account.nsf_count = 2
        account.save(update_fields=["autopay", "cash_only_no_autopay", "nsf_count"])

    body = position(pine_hill, account)

    assert body["cash_only"] is True
    assert body["bounces"] == 2
    assert body["held_reason"] == autopay.HELD_CASH_ONLY
    assert body["available"] is False
    # The customer's own election is untouched — nothing here un-asks it.
    assert body["enrolled"] is False
    assert any(one["code"] == autopay.CASH_ONLY for one in body["problems"])


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 · TENANT ISOLATION
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc8_the_intents_shown_are_this_account_s_only(pine_hill, sarah, oak_ridge, elena):
    """⚠ **ASSERTED BY ASKING THE WRONG TENANT FOR THE RIGHT ACCOUNT.**

    `BR-CWP-010` lives in the QUERY, so the way to prove it is to run the read
    under Oak Ridge's context naming a Pine Hill account id and watch it come
    back empty — the shape `US-CWP-012` TC-5 already takes one screen along.
    A test that merely built two tenants' rows and read one would pass over a
    read that filtered in Python instead of in SQL.
    """
    del elena  # the Oak Ridge tenant is the fixture; no actor of theirs is needed
    account = _enrolled(pine_hill, elm_street_account(pine_hill, sarah))
    _september_intent(pine_hill, account)

    with tenant_context(pine_hill.id):
        mine = autopay.intent_rows(account_id=account.pk)
    with tenant_context(oak_ridge.id):
        theirs = autopay.intent_rows(account_id=account.pk)

    assert [row["amount"] for row in mine] == ["142.1800"]
    assert theirs == [], (
        "an Oak Ridge session read a Pine Hill intent by naming its account id — "
        "BR-CWP-010 puts the tenant in the query, not in the screen"
    )
    # And the whole position read is empty of the figure too, not merely the rows.
    with tenant_context(oak_ridge.id):
        body = autopay.portal_position(account_id=account.pk)
    assert body["any_scheduled"] is False
    assert "142.18" not in str(body)


# ═══════════════════════════════════════════════════════════════════════════
# TC-9 · THE CEILING THAT HAS NO COLUMN
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_tc9_the_ceiling_is_offered_and_refused_because_nothing_stores_one(pine_hill, sarah):
    """*"or set a ceiling and we will ring you above it"* — offered, held.

    ⚠ **`accounts` HAS NO CEILING COLUMN**, so a screen that let somebody type
    `$200.00` would take a number nowhere to put. The choice is on the wire as a
    refused option with its reason; the SENTENCE is the catalogue's.
    """
    from apps.customers import models as customers_models

    account = _enrolled(pine_hill, elm_street_account(pine_hill, sarah))
    _september_intent(pine_hill, account)

    body = position(pine_hill, account)

    assert body["ceiling"] is None
    assert any(one["code"] == autopay.CEILING_NOT_STORED for one in body["problems"])
    # ⚠ The other half of the hold's expiry test: the day a column exists, the
    # option stops being a refusal and this goes red naming the screen.
    columns = {field.name for field in customers_models.Account._meta.get_fields()}
    assert "autopay_ceiling" not in columns, (
        "a ceiling column exists now: CWP-040's How much choice must stop "
        "refusing (autopay.CEILING_NOT_STORED) in the same commit"
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE ABSENCE `BR-CWP-093` ASKS FOR
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_an_account_with_no_intents_says_so_rather_than_drawing_an_empty_table(pine_hill, sarah):
    """Nothing empty ever appears: no intent means one sentence, not a table
    with a header and no rows."""
    account = _enrolled(pine_hill, elm_street_account(pine_hill, sarah))

    body = position(pine_hill, account)

    assert body["any_scheduled"] is False
    assert [row["state"] for row in body["next_few"]] == [autopay.SLOT_NOT_BILLED_YET]


# ═══════════════════════════════════════════════════════════════════════════
# THE WIRE — hard-won law 2, *built is not wired*
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **A READ NOTHING SERVES IS NOT A SCREEN.** `portal_position` above is
# exercised as a function by every case in this file, and a function with no
# route behind it renders nothing with every test green. These two cases open
# the actual door.


@pytest.mark.django_db
def test_the_autopay_endpoint_answers_and_never_lets_a_browser_cache_it(pine_hill, sarah):
    """`GET accounts/{id}/autopay` — 200, the real figure, and `no-store`.

    ⚠ **`BR-CWP-047` APPLIES BECAUSE THE SCHEDULED FIGURE IS MONEY.** A drafted
    amount cached in a browser is the same hazard as a cached balance.
    """
    from django.test import Client

    from tests.test_us_cwp_helpers import MARIA_EMAIL, MARIA_PASSWORD, enrol_maria, switch_on

    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    account = _enrolled(pine_hill, elm_street_account(pine_hill, sarah))
    _september_intent(pine_hill, account)

    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    response = client.get(f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/autopay")

    assert response.status_code == 200, response.content
    assert "no-store" in response["Cache-Control"]
    body = response.json()
    assert body["next_few"][0]["display"] == "$142.18"
    assert body["available"] is False


@pytest.mark.django_db
def test_the_autopay_route_offers_no_way_to_turn_it_on(pine_hill, sarah):
    """⚠ **`US-PAY-024` TC-5 AT THE EDGE.** *"Any v1 code path attempts to
    charge the stored method (or a 'Retry autopay' action) → Impossible."*

    It is enforced by absence, so the assertion is about absence: the route
    accepts `GET` and nothing else, and the portal edge carries no route whose
    name mentions charging, retrying or enrolling.
    """
    from django.test import Client

    from apps.portal import api as portal_api
    from tests.test_us_cwp_helpers import MARIA_EMAIL, MARIA_PASSWORD, enrol_maria, switch_on

    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    account = _enrolled(pine_hill, elm_street_account(pine_hill, sarah))

    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    posted = client.post(
        f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/autopay",
        data={},
        content_type="application/json",
    )
    assert posted.status_code == 405, posted.content

    routes = [str(one.pattern) for one in portal_api.urlpatterns]
    for forbidden in ("charge", "retry", "autopay/on", "autopay/enrol"):
        assert not any(forbidden in one for one in routes), (
            f"the portal edge exposes {forbidden!r}: BR-PAY-015 forbids a charging "
            "path before rails, and TC-5 is enforced by there being nothing to call"
        )
