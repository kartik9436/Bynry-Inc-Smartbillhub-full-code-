# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-019 (the budget bill: variance on every bill, the annual
#           settle-up) — the FORECAST read, which had no endpoint at all.
#           Screens: §05 entry **25.2 `Settle-up forecast`** of
#           `05-prototype/04 Billing, As Built.pdf`, p124(low)–p126(top).
# Rules:    BR-BIL-017 (annual settle-up month, copied onto the account at
#           enrolment) · BR-BIL-072 (the level is what is due) · BR-BIL-021
#           (every budget parameter is tenant config) · CLAUDE.md rule 1
#           (tenant scoping) · rule 2 (money 4dp, display 2, never a float) ·
#           rule 4's reasoning (the variance derives from APPEND-ONLY events) ·
#           NFR-3 (the page is cut in SQL) · B14 rule 31 (no database id is a
#           field's visible value) · rule 37 (a drawn figure is an
#           illustration, never a fact to build to)
# Golden:   ❄️ WE-8 → GT-24 (B5 FROZEN): level $242; Jul 292.87 · Aug 231.40 ·
#           Sep 198.75; the variance walk −50.87 → −40.27 → +2.98.
# ───────────────────────────────────────────────────────
"""§05 entry 25.2 — the forecast, and the two things it must never get wrong.

**THE THREE MONEY COLUMNS TIE OUT, OR THE SCREEN IS LYING.** The drawing puts
`PAID ON THE LEVEL`, `ACTUAL SO FAR` and `BALANCE` on one row, and a clerk reads
them as one sentence. They are only one sentence if `actual − paid` IS the
balance the engine holds, so that identity is asserted here on the ❄️ frozen
WE-8 chain rather than assumed from the fact that both come from the same table.

**THE DRAWN SIGN IS THE ENGINE'S, INVERTED ONCE, IN ONE PLACE.** The drawing
prints `+$212.80 Collect`; `variance_balance` runs the other way (−50.87 is the
month the customer UNDER-paid). `budget.SettleUp.signed` is the single
reconciliation — *"+ collects, − credits"* — and `balance_signed` is served from
it. A second negation anywhere would flip a customer's money on screen, so the
sign is asserted against the frozen chain in both directions.

**AND THE WITHDRAWN BUTTON IS A TEST, NOT A COMMENT.** The blueprint removed a
bulk *"Settle these 2"* because the cycle run already posts the settle-up
idempotently per invoice. `test_no_write_path` asserts the route answers GET and
refuses POST, so a later lane adding one has to delete a test that says why.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import budget, budget_api, budget_service, models, selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, marcus, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call
from tests.test_us_bil_025_026_bills_read import an_account

pytestmark = pytest.mark.django_db

# ❄️ WE-8 / GT-24 verbatim.
LEVEL = Decimal("242")
JULY = Decimal("292.87")
AUGUST = Decimal("231.40")
SEPTEMBER = Decimal("198.75")

JUL = date(2026, 7, 1)
AUG = date(2026, 8, 1)
SEP = date(2026, 9, 1)

#: The forecast's horizon. An ARGUMENT on every call here, so these assertions
#: do not change meaning on the first of next month — which is the whole reason
#: `_as_of` is a query parameter rather than a clock read.
AS_OF = date(2026, 9, 15)


def enrol(actor, account, *, settle_up_month, currency="USD"):
    status = budget_service.enroll(
        actor=actor,
        account_id=account.id,
        trailing_actuals=(Decimal("2904"),),
        months_of_history=12,
        plan_offers_budget=True,
        currency=currency,
        on_date=date(2026, 6, 28),
    )
    status.settle_up_month = settle_up_month
    status.save(update_fields=["settle_up_month"])
    return status


def forecast(user, tenant, **params):
    return api_call(
        budget_api.budget_settle_up_forecast,
        "get",
        user=user,
        role="system_admin",
        tenant=tenant,
        query={"as_of": AS_OF.isoformat(), **params},
    )


# ══════════════════════════════════════════════════════════════════════════
# The route exists at the address the screen calls
# ══════════════════════════════════════════════════════════════════════════
def test_the_forecast_route_is_actually_mounted(brazos):
    """Resolved THROUGH THE ROOT URLCONF, and by address.

    `DEF-CWP-3925`'s hold-expiry test asserted a screen was registered at one
    address while the router mounted it at another and every check passed over
    both. The static segment also has to beat `<str:account_id>`: without the
    declaration order in `urlpatterns`, `settle-up-forecast` resolves as an
    account id and this screen 404s while every unit test still passes.
    """
    from django.urls import resolve

    match = resolve(f"/api/{brazos.subdomain}/budget-billing/settle-up-forecast")
    assert match.func.cls.__module__ == "apps.billing.budget_api"
    assert match.kwargs == {}, (
        "the static segment was swallowed by <str:account_id>: " f"{match.kwargs}"
    )


def test_no_write_path(brazos, marcus):
    """⚠ THE WITHDRAWN BUTTON, AS A TEST.

    The drawing offered a bulk *"Settle these 2"* and the blueprint took it out:
    the cycle run already posts the settle-up on the account's own bill, inside
    the same write that creates it, idempotently per invoice. A second writer
    for the same money is the thing this asserts against.
    """
    with tenant_ctx(brazos):
        response = api_call(
            budget_api.budget_settle_up_forecast,
            "post",
            user=marcus.user,
            role="system_admin",
            tenant=brazos,
            data={},
        )
    assert response.status_code == 405, response.data


# ══════════════════════════════════════════════════════════════════════════
# The three money columns
# ══════════════════════════════════════════════════════════════════════════
def test_the_three_money_columns_tie_out_on_the_frozen_chain(brazos, marcus):
    """❄️ WE-8: paid 3 × 242 = 726.00, actual 723.02, balance +2.98 → CREDIT.

    `actual − paid` = −2.98, and the drawn BALANCE column is
    `SettleUp.signed` = **−2.98** because the utility owes the customer. The
    same three figures a clerk reads as one sentence.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-7001", contact_name="Navarro, P.")
        enrol(marcus, account, settle_up_month=11)
        for actual, on_date in ((JULY, JUL), (AUGUST, AUG), (SEPTEMBER, SEP)):
            budget_service.record_bill(account_id=account.id, actual=actual, on_date=on_date)

        response = forecast(marcus.user, brazos)

    assert response.status_code == 200, response.data
    row = next(r for r in response.data["results"] if r["account_no"] == "ACC-7001")

    paid = Decimal(row["paid_on_level"])
    actual = Decimal(row["actual_so_far"])
    assert paid == LEVEL * 3 == Decimal("726.00")
    assert actual == JULY + AUGUST + SEPTEMBER == Decimal("723.02")
    assert row["months_billed"] == 3

    # THE IDENTITY. If this ever fails the screen is showing three numbers that
    # do not add up, and a clerk on the telephone is reading them out.
    assert Decimal(row["balance_signed"]) == actual - paid == Decimal("-2.98")
    assert row["settle_up_direction"] == budget.SETTLE_CREDIT
    assert Decimal(row["settle_up_amount"]) == Decimal("2.98")
    # B4.2 — the settle-up is AR-timing and never carries tax.
    assert row["settle_up_taxable"] is False

    # B14 rule 31 — the NUMBER is the visible value; the id is there for the link.
    assert row["account_no"] == "ACC-7001"
    assert row["customer_name"] == "Navarro, P."


def test_the_sign_runs_the_other_way_for_a_collection(brazos, marcus):
    """❄️ WE-8 two months in: balance −40.27 → the drawn BALANCE is **+40.27**
    and the direction is COLLECT. The drawing's `+$212.80 Collect` shape."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-7002")
        enrol(marcus, account, settle_up_month=11)
        for actual, on_date in ((JULY, JUL), (AUGUST, AUG)):
            budget_service.record_bill(account_id=account.id, actual=actual, on_date=on_date)

        response = forecast(marcus.user, brazos)

    row = next(r for r in response.data["results"] if r["account_no"] == "ACC-7002")
    assert Decimal(row["balance_signed"]) == Decimal("40.27")
    assert row["settle_up_direction"] == budget.SETTLE_COLLECT
    assert Decimal(row["settle_up_amount"]) == Decimal("40.27")
    # PAID − ACTUAL is the engine's balance; ACTUAL − PAID is the drawn column.
    assert Decimal(row["actual_so_far"]) - Decimal(row["paid_on_level"]) == Decimal("40.27")


# ══════════════════════════════════════════════════════════════════════════
# The settle-up period, and the month a row settles in
# ══════════════════════════════════════════════════════════════════════════
def test_the_window_restarts_at_the_last_settle_up(brazos, marcus):
    """After a settle-up the balance is zero, so the two sums must restart too.

    An account that trued up in September and has been billed once since shows
    ONE month, not four — otherwise the columns report a year the balance no
    longer covers.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-7003")
        enrol(marcus, account, settle_up_month=SEP.month)
        for actual, on_date in ((JULY, JUL), (AUGUST, AUG)):
            budget_service.record_bill(account_id=account.id, actual=actual, on_date=on_date)
        # September IS its settle-up month: this bill closes the old year.
        budget_service.record_bill(account_id=account.id, actual=SEPTEMBER, on_date=SEP)
        # October opens the new one.
        budget_service.record_bill(
            account_id=account.id, actual=Decimal("250.00"), on_date=date(2026, 10, 1)
        )

        response = forecast(marcus.user, brazos, as_of=AS_OF.isoformat())

    row = next(r for r in response.data["results"] if r["account_no"] == "ACC-7003")
    assert row["months_billed"] == 1, "the window did not restart at the settle-up"
    assert Decimal(row["paid_on_level"]) == LEVEL
    assert Decimal(row["actual_so_far"]) == Decimal("250.00")
    # 242 − 250 = −8.00 held; the drawn column is +8.00 to COLLECT.
    assert Decimal(row["balance_signed"]) == Decimal("8.00")
    assert row["settle_up_direction"] == budget.SETTLE_COLLECT


def test_an_account_that_already_settled_this_month_is_a_year_out(brazos, marcus):
    """⚠ It must not appear on the `SETTLING THIS MONTH` tile twice in one year.

    Its month IS this month and it has already been trued up, so its next
    settle-up is next year — `months_away` 12, not 0.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-7004")
        enrol(marcus, account, settle_up_month=AS_OF.month)
        budget_service.record_bill(account_id=account.id, actual=JULY, on_date=JUL)
        budget_service.record_bill(
            account_id=account.id, actual=SEPTEMBER, on_date=date(2026, 9, 1)
        )

        response = forecast(marcus.user, brazos)

    row = next(r for r in response.data["results"] if r["account_no"] == "ACC-7004")
    assert row["months_away"] == 12
    assert row["settles_this_month"] is False
    assert row["settles_in_year"] == AS_OF.year + 1
    assert row["settles_in_month"] == AS_OF.month
    assert response.data["summary"]["settling_this_month"] == 0


def test_the_month_and_year_a_row_settles_in(brazos, marcus):
    """`SETTLES IN` is a month AND a year, projected from the horizon.

    Standing in September 2026: month 11 is Nov 2026, month 1 is Jan 2027.
    """
    with tenant_ctx(brazos):
        november = an_account(brazos, marcus, account_no="ACC-7005", label="Unit N")
        january = an_account(brazos, marcus, account_no="ACC-7006", label="Unit J")
        enrol(marcus, november, settle_up_month=11)
        enrol(marcus, january, settle_up_month=1)

        response = forecast(marcus.user, brazos)

    rows = {r["account_no"]: r for r in response.data["results"]}
    assert (rows["ACC-7005"]["settles_in_month"], rows["ACC-7005"]["settles_in_year"]) == (11, 2026)
    assert (rows["ACC-7006"]["settles_in_month"], rows["ACC-7006"]["settles_in_year"]) == (1, 2027)
    # The drawing lists nearest first, and the ORDER is cut in SQL.
    order = [r["account_no"] for r in response.data["results"]]
    assert order.index("ACC-7005") < order.index("ACC-7006")


# ══════════════════════════════════════════════════════════════════════════
# The tiles, and what they refuse to add up
# ══════════════════════════════════════════════════════════════════════════
def test_the_tiles_count_and_total_this_month_only(brazos, marcus):
    """`TO COLLECT` and `TO CREDIT` are POSITIVE magnitudes over the accounts
    settling this month; everyone else is `LATER IN THE YEAR`."""
    with tenant_ctx(brazos):
        owing = an_account(brazos, marcus, account_no="ACC-7010", label="Unit 1")
        ahead = an_account(brazos, marcus, account_no="ACC-7011", label="Unit 2")
        later = an_account(brazos, marcus, account_no="ACC-7012", label="Unit 3")
        enrol(marcus, owing, settle_up_month=AS_OF.month)
        enrol(marcus, ahead, settle_up_month=AS_OF.month)
        enrol(marcus, later, settle_up_month=3)
        # owing: 242 − 292.87 = −50.87 held → collect 50.87
        budget_service.record_bill(account_id=owing.id, actual=JULY, on_date=JUL)
        # ahead: 242 − 198.75 = +43.25 held → credit 43.25
        budget_service.record_bill(account_id=ahead.id, actual=SEPTEMBER, on_date=JUL)

        response = forecast(marcus.user, brazos)

    summary = response.data["summary"]
    assert summary["settling_this_month"] == 2
    assert summary["settling_month"] == AS_OF.month
    assert summary["to_collect_accounts"] == 1
    assert Decimal(summary["to_collect_amount"]) == Decimal("50.87")
    assert summary["to_credit_accounts"] == 1
    assert Decimal(summary["to_credit_amount"]) == Decimal("43.25")
    assert summary["currency"] == "USD"
    assert summary["later_accounts"] == 1
    assert summary["later_months"] == 1


def test_two_currencies_get_the_counts_and_no_totals(brazos, marcus):
    """CLAUDE.md rule 2 — 100 USD + 100 CAD is not 200 of anything.

    `_summary`'s rule on the neighbouring screen, carried over unchanged: the
    tile shows the COUNT and states no total rather than inventing a rate.
    """
    with tenant_ctx(brazos):
        usd = an_account(brazos, marcus, account_no="ACC-7020", label="Unit U")
        cad = an_account(brazos, marcus, account_no="ACC-7021", label="Unit C")
        enrol(marcus, usd, settle_up_month=AS_OF.month, currency="USD")
        enrol(marcus, cad, settle_up_month=AS_OF.month, currency="CAD")
        budget_service.record_bill(account_id=usd.id, actual=JULY, on_date=JUL)
        budget_service.record_bill(account_id=cad.id, actual=JULY, on_date=JUL)

        response = forecast(marcus.user, brazos)

    summary = response.data["summary"]
    assert summary["settling_this_month"] == 2
    assert summary["to_collect_accounts"] == 2
    assert summary["to_collect_amount"] is None, "two currencies were added together"
    assert summary["currency"] is None
    assert summary["currencies"] == ["CAD", "USD"]


def test_an_account_with_no_settle_up_month_is_counted_not_hidden(brazos, marcus):
    """⚠ A stated absence, never a blank row.

    `settle_up_month` is nullable — a tenant that has never published one
    (BR-BIL-021, never defaulted) enrols without it — and such an account never
    trues up. It is out of the rows and IN `no_settle_month`, so the screen can
    say so instead of quietly forecasting for fewer people than are enrolled.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-7030")
        status = budget_service.enroll(
            actor=marcus,
            account_id=account.id,
            trailing_actuals=(Decimal("2904"),),
            months_of_history=12,
            plan_offers_budget=True,
            currency="USD",
            on_date=date(2026, 6, 28),
        )
        status.settle_up_month = None
        status.save(update_fields=["settle_up_month"])

        response = forecast(marcus.user, brazos)

    assert [r["account_no"] for r in response.data["results"]] == []
    assert response.data["summary"]["no_settle_month"] == 1


# ══════════════════════════════════════════════════════════════════════════
# Filters, and the horizon argument
# ══════════════════════════════════════════════════════════════════════════
def test_the_direction_filter_cuts_in_sql(brazos, marcus):
    with tenant_ctx(brazos):
        owing = an_account(brazos, marcus, account_no="ACC-7040", label="Unit 1")
        ahead = an_account(brazos, marcus, account_no="ACC-7041", label="Unit 2")
        enrol(marcus, owing, settle_up_month=11)
        enrol(marcus, ahead, settle_up_month=11)
        budget_service.record_bill(account_id=owing.id, actual=JULY, on_date=JUL)
        budget_service.record_bill(account_id=ahead.id, actual=SEPTEMBER, on_date=JUL)

        collect = forecast(marcus.user, brazos, **{"f.direction": budget.SETTLE_COLLECT})
        credit = forecast(marcus.user, brazos, **{"f.direction": budget.SETTLE_CREDIT})
        month = forecast(marcus.user, brazos, **{"f.month": "11"})
        nothing = forecast(marcus.user, brazos, **{"f.month": "4"})

    assert [r["account_no"] for r in collect.data["results"]] == ["ACC-7040"]
    assert [r["account_no"] for r in credit.data["results"]] == ["ACC-7041"]
    assert len(month.data["results"]) == 2
    assert nothing.data["results"] == []


def test_a_malformed_horizon_is_refused_not_ignored(brazos, marcus):
    """A silently-ignored argument is worse than a refused one — hard-won law 14
    closes on exactly that shape (`--reuse-db` did nothing for weeks)."""
    with tenant_ctx(brazos):
        response = api_call(
            budget_api.budget_settle_up_forecast,
            "get",
            user=marcus.user,
            role="system_admin",
            tenant=brazos,
            query={"as_of": "the 3rd"},
        )
    assert response.status_code == 422, response.data
    # And it reaches the clerk as WORDS, not as silence: the catalogue resolves
    # this key, which `core.errors` asserts at the raise site.
    assert response.data["message_key"] == "billing.ops.date_format"


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-5327 — the column this lane had to fix before it could reuse it
# ══════════════════════════════════════════════════════════════════════════
def test_def_bil_5327__actual_to_date_counts_billed_months_only(brazos, marcus):
    """⚠ REGRESSION. `budget_actuals_to_date` summed every event carrying an
    `actual`, and a settle-up month writes TWO such rows for one bill.

    Measured before the fix on this exact chain: **$921.77 over 4 months** where
    **$723.02 over 3** is true — September counted twice, and the month count
    inflated with it so the row looked internally consistent.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus, account_no="ACC-7050")
        status = enrol(marcus, account, settle_up_month=SEP.month)
        for actual, on_date in ((JULY, JUL), (AUGUST, AUG)):
            budget_service.record_bill(account_id=account.id, actual=actual, on_date=on_date)
        budget_service.record_bill(account_id=account.id, actual=SEPTEMBER, on_date=SEP)

        served = selectors.budget_actuals_to_date([status.pk])

    total, months = served[status.pk]
    assert Decimal(total) == JULY + AUGUST + SEPTEMBER == Decimal("723.02")
    assert months == 3
    # The settle-up row is still there and still carries the actual — the fix is
    # in what the SUM selects, not in what the ledger records.
    with tenant_ctx(brazos):
        settled = models.AccountBudgetEvent.objects.filter(
            budget_status_id=status.pk, event=models.BUDGET_EVENT_SETTLED
        )
        assert settled.count() == 1
        assert settled.first().actual == SEPTEMBER

# ── Lifecycle ─────────────────────────────────────────────
# packet: 05-prototype/04 Billing, As Built.pdf §05 entry 25.2 (p124-p126, read
#         as images at scale 2) · 04-docs/05-modules/07-billing/
#         02-business-rules.md BR-BIL-011/017/021 · 08-worked-examples.md WE-8 ·
#         04-docs/02-decisions/05-golden-tests.md GT-24 (❄️ FROZEN)
# generated: 2026-09-15 by the §05 entry 25.2 build lane
# checklist: A✔ B✔ C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: JOBS_EAGER=false python3.12 -m pytest tests/test_s80_settle_up_forecast.py
#         -q --reuse-db -p no:randomly — 13 passed. The DEF-BIL-5327 case was
#         proved RED first, on this exact chain: $921.77 over 4 months served
#         where $723.02 over 3 is true.
# exceptions: (1) every figure asserted here is the ❄️ frozen WE-8 chain, QUOTED
#         so drift goes red — no frozen figure is moved · (2) the drawing's own
#         numbers (100412, +$212.80, 37 rows) are ILLUSTRATIONS under B14 rule
#         37 and NONE of them is asserted; the cases assert the SHAPE · (3) the
#         horizon is an argument on every call, so these assertions do not
#         change meaning on the first of next month · (4) `test_no_write_path`
#         asserts an ABSENCE — the bulk settle-up the blueprint withdrew — so a
#         later lane adding one has to delete a test that says why.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
