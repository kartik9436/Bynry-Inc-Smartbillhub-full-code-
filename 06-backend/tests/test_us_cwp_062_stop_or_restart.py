# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-062 (EP-CWP-11) — *stop or restart service, and the screen
#           names the cheaper option.* Screen: CWP-052
# Rules:    BR-CWP-080 (a disconnect leaves the account OPEN and standing
#           charges keep running) · BR-CWP-081 (where stopping is more
#           expensive than closing, the screen says so, WITH BOTH FIGURES) ·
#           BR-RAT-088 (the CHARGE CODE owns the base amount; a plan displays
#           it, never defines it) · BR-CWP-026 (a portal form creates work and
#           changes no account) · BR-CWP-010 · CLAUDE.md hard rule 2
# Tests:    this file
# Impacts:  apps/portal/seams/rating_seam.py `standing_charge_monthly` ·
#           apps/portal/selectors.py `stop_or_restart` ·
#           apps/portal/services.py `_stop_restart` · apps/portal/api.py
# ───────────────────────────────────────────────────────
"""`US-CWP-062`'s cases — and the arithmetic the whole screen turns on.

⚠ **THE VERDICT IS COMPUTED AND `US-CWP-062` §7 SAYS WHY IT MUST BE:** *"a
screen that always says stopping is cheaper is wrong for a long absence."* So
the two cases that matter are the two sides of the crossover, and they are
asserted as literal money rather than as a comparison of two variables:

    five months  ·  5 × $18.50 = $92.50   against  $185.00 + $150.00 = $335.00
                 →  STOPPING is cheaper
    nineteen     · 19 × $18.50 = $351.50  against  $335.00
                 →  CLOSING is cheaper

`$335.00 ÷ $18.50 = 18.1`, so nineteen is the first month that crosses it —
which is the correction `DEF-CWP-3608` made to TC-3 on 2026-09-03, when it
still said *twelve* and `12 × $18.50 = $222.00` does not exceed `$335.00`.

⚠ **`$18.50` IS SET ON THE CHARGE CODE HERE AND NOT TAKEN FROM THE FIXTURE.**
`apps/portal/sample_data.py` seeds water's base at `$12.00` and says of its own
figures that they are *"NOT figures any story asserts"*. The story asserts
`$18.50`, so the test moves the price the product actually reads — the charge
code, `BR-RAT-088`'s single source — and that is also what proves TC-7: the
figure follows the PLAN and is not a constant in the portal.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from apps.portal import selectors as portal_selectors
from apps.portal.seams import rating_seam
from apps.rating import models as rating_models
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)

#: `US-CWP-062` §4's own figures.
STANDING_CHARGE = Decimal("18.5000")
CONNECTION_FEE = Decimal("185.0000")
NEW_DEPOSIT = Decimal("150.0000")
STOP_FROM = date(2026, 11, 1)
RESTART_FIVE_MONTHS = date(2027, 4, 1)
RESTART_NINETEEN_MONTHS = date(2028, 6, 1)


def _price_the_base(tenant, amount: Decimal | None) -> None:
    """Move water's base charge to `amount`, or take it away entirely.

    ⚠ **THE CHARGE CODE, BECAUSE THAT IS WHERE THE BASE LIVES** (`BR-RAT-088`,
    PO 2026-08-20: *"the CHARGE CODE owns the base amount; a plan displays it,
    never defines it"*). Writing the plan's own `base_charge` column instead
    would move a figure the product stopped reading on 2026-08-31 and the test
    would pass over a screen showing the old price.

    ⚠ **THE OTHER TWO COLUMNS ARE CLEARED, AND THE REASON CHANGED ON
    2026-09-28.** It used to be that `apps/portal/sample_data.py` seeded
    `plan_services.base_charge` at `$8.00` as well as the charge code, so
    moving only the code left the plan stating a DIFFERENT figure and
    `gather._base_charge_for` REFUSED the whole read by name. That refusal is
    gone (`DEF-BIL-7170`: *"we will never take default value from plan $8.0 -
    that is retired"*) and the fixture no longer writes the column at all
    (`DEF-CWP-7001`), so clearing them here is belt and braces on a tenant that
    may have been seeded before either change.

    ⚠⚠ **SEWER AND TRASH ARE PRICED AT `$0.00`, AND THAT IS THE FIX FOR SIX
    RED CASES IN THIS FILE — `DEF-CWP-7001`.** This account has taken water,
    sewer AND trash since 2026-09-06 (`CR-068` wave H), and the portal fixture
    gives all three an `is_base` charge code — water `$12.00`, sewer `$8.00`,
    trash `$9.00`. `standing_charge_monthly` SUMS them, so the account's
    standing charge was `$18.50 + $8.00 + $9.00 = $35.50` and every figure in
    this file, all of them derived from `US-CWP-062` §4's `$18.50`, was
    arithmetically wrong. **Nothing showed it**, because the plan's `$8.00`
    disagreed with trash's `$9.00` and the read refused the WHOLE figure — a
    screen that could never print its own number, which is what `DEF-CWP-7001`
    was filed for.

    **A ZERO AND NOT A SILENCE, and the difference is a PO ruling.** A stored
    `0.00` is a PRICE and bills `$0.00` (PO 2026-08-19, verbatim *"print
    $0.00"*); taking the code away is *nobody has stated this service's base*,
    which REFUSES and would take the whole read down with it. It is also the
    honest shape for this utility: sewer is billed as a share of water usage
    and trash per cart, and neither needs a standing charge of its own.

    `None` takes WATER's base code away rather than setting it to zero — TC-8's
    case, and the distinction is the whole of that test: *no standing charge*
    and *a standing charge of `$0.00`* are different claims about a utility.
    """
    with tenant_context(tenant.id):
        rating_models.PlanService.objects.filter(
            tenant_id=tenant.id, service__code="water"
        ).update(base_charge=None)
        rating_models.TariffVersion.objects.filter(
            tenant_id=tenant.id, tariff__service__code="water"
        ).update(base_charge=None)
        # Every OTHER service's standing charge is an explicit zero, so the
        # account's standing charge is WATER's and `US-CWP-062` §4's figures
        # hold. See this function's docstring for why a zero and not a silence.
        rating_models.Charge.objects.filter(
            tenant_id=tenant.id, is_base=True, deleted_at__isnull=True
        ).exclude(service__code="water").update(amount=Decimal("0.0000"))
        rows = rating_models.Charge.objects.filter(
            tenant_id=tenant.id, is_base=True, service__code="water", deleted_at__isnull=True
        )
        if amount is None:
            rows.update(is_base=False)
        else:
            rows.update(amount=amount)


def _read(tenant, account, *, stop_from=STOP_FROM, start_again=RESTART_FIVE_MONTHS):
    class _Principal:
        tenant_id = tenant.id

    with tenant_context(tenant.id):
        return portal_selectors.stop_or_restart(
            _Principal(),
            account,
            stop_from=stop_from,
            start_again=start_again,
            today=date.today(),
        )


@pytest.mark.django_db
def test_us_cwp_062_tc1_the_box_says_the_account_stays_open(pine_hill, sarah):
    """TC-1 / TC-4 — `BR-CWP-080`, stated on the wire and never inferred.

    ⚠ **IT PREVENTS THE MOST EXPENSIVE MISUNDERSTANDING IN THE PRODUCT**
    (`US-CWP-062` §1): assuming a stopped supply stops the bill. A screen that
    had to derive that sentence could stop saying it.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _price_the_base(pine_hill, STANDING_CHARGE)
    answer = _read(pine_hill, account)
    assert answer["account_stays_open"] is True
    assert answer["months"] == 5
    assert answer["standing_charge_monthly"] == "18.5000"


@pytest.mark.django_db
def test_us_cwp_062_tc2_five_months_of_92_50_against_335_00_says_stopping(pine_hill, sarah):
    """TC-2 — the comparison arithmetic, as literal money.

    `5 × $18.50 = $92.50` against `$185.00 + $150.00 = $335.00`.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _price_the_base(pine_hill, STANDING_CHARGE)
    answer = _read(pine_hill, account)
    assert answer["cost_of_stopping"] == "92.5000"
    assert answer["connection_fee"] == "185.0000"
    assert answer["new_deposit"] == "150.0000"
    assert answer["cost_of_closing"] == "335.0000"
    assert answer["cheaper"] == portal_selectors.CHEAPER_STOPPING
    assert answer["no_verdict"] is None


@pytest.mark.django_db
def test_us_cwp_062_tc3_nineteen_months_of_351_50_against_335_00_says_closing(
    pine_hill, sarah
):
    """TC-3 · negative — the verdict FLIPS, and it must.

    ⚠ **THIS CASE READ *TWELVE* UNTIL 2026-09-03 (`DEF-CWP-3608`) AND COULD NOT
    HAVE PASSED:** `12 × $18.50 = $222.00`, which does NOT exceed `$335.00`, so
    twelve months still says *stopping*. The crossover is
    `$335.00 ÷ $18.50 = 18.1`, so nineteen is the first month that crosses it.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _price_the_base(pine_hill, STANDING_CHARGE)
    answer = _read(pine_hill, account, start_again=RESTART_NINETEEN_MONTHS)
    assert answer["months"] == 19
    assert answer["cost_of_stopping"] == "351.5000"
    assert answer["cost_of_closing"] == "335.0000"
    assert answer["cheaper"] == portal_selectors.CHEAPER_CLOSING


@pytest.mark.django_db
def test_us_cwp_062_twelve_months_still_says_stopping(pine_hill, sarah):
    """The other half of `DEF-CWP-3608`, asserted so the correction cannot be
    quietly reverted: `12 × $18.50 = $222.00`, LESS than `$335.00`."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _price_the_base(pine_hill, STANDING_CHARGE)
    answer = _read(pine_hill, account, start_again=date(2027, 11, 1))
    assert answer["months"] == 12
    assert answer["cost_of_stopping"] == "222.0000"
    assert answer["cheaper"] == portal_selectors.CHEAPER_STOPPING


@pytest.mark.django_db
def test_us_cwp_062_tc7_the_figure_follows_the_plan_and_is_not_a_constant(pine_hill, sarah):
    """TC-7 — a tenant whose standing charge differs gets THEIR figure.

    The same account, the same dates, a different price on the charge code:
    `5 × $30.00 = $150.00`. A portal that held `$18.50` anywhere would fail
    here, which is what this case is for.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _price_the_base(pine_hill, Decimal("30.0000"))
    answer = _read(pine_hill, account)
    assert answer["standing_charge_monthly"] == "30.0000"
    assert answer["cost_of_stopping"] == "150.0000"
    assert answer["cheaper"] == portal_selectors.CHEAPER_STOPPING


@pytest.mark.django_db
def test_us_cwp_062_tc8_no_standing_charge_says_so_rather_than_showing_zero(
    pine_hill, sarah
):
    """TC-8 · negative — a service with NO standing charge.

    ⚠ **`$0.00` WOULD READ AS A SAVING**, and a comparison built on a missing
    figure would tell a customer that stopping for nineteen months costs
    nothing. The reason travels and the verdict is withheld.

    ⚠ **THE REASON IS THE ENGINE'S OWN AND IS NOT RE-WORDED HERE.** With no
    base stated anywhere, `gather._base_charge_for` REFUSES rather than
    answering `None` — `DEF-277`, *"a blank base is size not served, not a
    zero"* — and that refusal travels as `standing_charge_unavailable`. What
    matters to the customer is the same either way and is what this asserts:
    no figure, no verdict, and the screen saying so in words.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _price_the_base(pine_hill, None)
    answer = _read(pine_hill, account)
    assert answer["standing_charge_monthly"] is None
    assert answer["cost_of_stopping"] is None
    assert answer["cheaper"] is None
    assert answer["no_verdict"] == portal_selectors.NO_VERDICT_NO_STANDING
    # A reason is PRESENT — the screen may not be left saying nothing at all.
    assert answer["standing_charge_unavailable"]


@pytest.mark.django_db
def test_us_cwp_062_no_restart_date_gives_no_verdict_rather_than_a_free_stop(
    pine_hill, sarah
):
    """An open-ended stop has no months to multiply, so it has no cost — and a
    cost of `None` must not become a cost of zero, which would make stopping
    cheaper than everything forever."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _price_the_base(pine_hill, STANDING_CHARGE)
    answer = _read(pine_hill, account, start_again=None)
    assert answer["months"] is None
    assert answer["cost_of_stopping"] is None
    assert answer["cheaper"] is None
    assert answer["no_verdict"] == portal_selectors.NO_VERDICT_NO_RESTART_COST


@pytest.mark.django_db
def test_us_cwp_062_tc5_a_restart_before_the_stop_is_refused(pine_hill, sarah):
    """TC-5 · negative — refused at the EDGE with a field error, so the screen
    can say which box is wrong."""
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    refused = client.get(
        f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/stop-or-restart"
        "?stop_from=2026-11-01&start_again=2026-10-01"
    )
    assert refused.status_code == 422, refused.content
    assert b"start_again" in refused.content


@pytest.mark.django_db
def test_us_cwp_062_tc6_an_account_outside_the_session_set_is_refused(pine_hill, sarah):
    """TC-6, first half · `BR-CWP-010` — both halves in the query.

    ⚠ **AN ACCOUNT OUTSIDE THE SET AND ONE THAT DOES NOT EXIST ANSWER THE SAME
    404**, so the set cannot be enumerated by watching which refusal comes back
    — `_account_in_set`'s own contract, exercised on this route.
    """
    import uuid

    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    refused = client.get(
        f"/api/{pine_hill.subdomain}/portal/accounts/{uuid.uuid4()}/stop-or-restart"
        "?stop_from=2026-11-01&start_again=2027-04-01"
    )
    assert refused.status_code == 404, refused.content


@pytest.mark.django_db
def test_us_cwp_062_tc6_the_figures_are_this_utilitys_own(pine_hill, sarah, oak_ridge, elena):
    """TC-6, second half · *the figures with a Pine Hill session are Pine
    Hill's standing charge and connection fee*.

    ⚠ **THIS IS THE HALF A 404 CANNOT PROVE.** Refusing another utility's
    account says nothing about whether the PRICES came from the right utility.
    So Oak Ridge's water base is moved to `$99.00` and Pine Hill's answer must
    not budge off `$18.50` — which it cannot, because the read names the tenant
    in the query (`G96`) rather than leaning on row-level security the suite's
    SQLite does not have (hard-won law 14).
    """
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = elm_street_account(pine_hill, sarah)
    _price_the_base(pine_hill, STANDING_CHARGE)
    with tenant_context(oak_ridge.id):
        rating_models.Charge.objects.filter(tenant_id=oak_ridge.id, is_base=True).update(
            amount=Decimal("99.0000")
        )
    answer = _read(pine_hill, account)
    assert answer["standing_charge_monthly"] == "18.5000"
    assert answer["cost_of_stopping"] == "92.5000"


@pytest.mark.django_db
def test_us_cwp_062_the_ask_raises_a_request_and_stops_nothing(pine_hill, sarah):
    """The write — one `service_requests` row, and NOTHING else moves.

    ⚠ **`BR-CWP-026` AND `BR-CWP-080` TOGETHER.** The account is byte-identical
    afterwards: the same status, the same service agreements, the supply still
    on. The response says `supply_stopped: false` so no confirmation screen can
    imply otherwise.
    """
    from apps.customers import models as customers_models

    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _price_the_base(pine_hill, STANDING_CHARGE)
    with tenant_context(pine_hill.id):
        before = customers_models.Account.objects.get(pk=account.pk)
        agreements_before = customers_models.ServiceAgreement.objects.filter(
            tenant_id=pine_hill.id, account_id=account.pk, ended_on__isnull=True
        ).count()
        status_before = before.status_id

    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    sent = client.post(
        f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/stop-or-restart/ask",
        data={
            "stop_from": "2026-11-01",
            "start_again": "2027-04-01",
            "reason": "the property is empty over winter",
            "name": "Maria Alvarez",
            "phone": "512-555-0101",
            "email": MARIA_EMAIL,
        },
        content_type="application/json",
    )
    assert sent.status_code == 200, sent.content
    body = sent.json()
    assert body["supply_stopped"] is False
    assert body["account_stays_open"] is True
    assert body["reference"].startswith("SR-")

    with tenant_context(pine_hill.id):
        after = customers_models.Account.objects.get(pk=account.pk)
        assert after.status_id == status_before
        assert (
            customers_models.ServiceAgreement.objects.filter(
                tenant_id=pine_hill.id, account_id=account.pk, ended_on__isnull=True
            ).count()
            == agreements_before
        )
        row = customers_models.ServiceRequest.objects.get(request_no=body["reference"])
        # BR-CWP-076 — the channel, forced by the write and never set by the caller.
        assert row.channel == "customer_portal"
        # BR-CWP-080 — the clerk's own row repeats the sentence the customer read.
        assert "The account stays open" in row.what_they_said
        assert "the property is empty over winter" in row.what_they_said
        # BR-CWP-026 — nothing links this row to an account, by rule.
        assert getattr(row, "account_id", None) is None


@pytest.mark.django_db
def test_us_cwp_062_the_ask_refuses_a_restart_before_the_stop_too(pine_hill, sarah):
    """The write refuses it as well as the edge, so a caller that skipped the
    screen cannot put an impossible row on a clerk's worklist."""
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    refused = client.post(
        f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/stop-or-restart/ask",
        data={"stop_from": "2026-11-01", "start_again": "2026-10-01"},
        content_type="application/json",
    )
    assert refused.status_code == 422, refused.content


@pytest.mark.django_db
def test_us_cwp_062_the_read_is_never_cached(pine_hill, sarah):
    """`BR-CWP-047` — the body carries what this customer pays a month."""
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    _price_the_base(pine_hill, STANDING_CHARGE)
    client = Client()
    client.post(
        f"/api/{pine_hill.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    response = client.get(
        f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/stop-or-restart"
        "?stop_from=2026-11-01&start_again=2027-04-01"
    )
    assert response.status_code == 200, response.content
    assert "no-store" in response["Cache-Control"]
    assert response.json()["cheaper"] == "stopping"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-062@b50adaa0 (EP-CWP-11)
# generated: 2026-09-04 by the CR-068 ending lane
# checklist: A✔ B✔ C✔ D✔(api.stop_or_restart · ask_to_stop_or_restart) E✔(portal/requests/StopOrRestart.tsx) F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_062_stop_or_restart.py · G81 · G84 · G96 · G82
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
