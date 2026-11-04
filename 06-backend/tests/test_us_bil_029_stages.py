# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-029 (the run's internal shape — seven stages)
#           Screens: S31.2 · S31.3
# Rules:    BR-BIL-037 (one input, one output per stage) · BR-BIL-039 (stages
#           1–5 PURE: no writes, no external calls, no clock) · BR-CUS-055
#           (behaviour classes; billable-base-only) · BR-MET-040 (a plan is
#           required) · BR-BIL-015 (a missing read is a human choice, never a
#           silent skip) · CLAUDE.md rule 2 (currency) · rule 3 (units)
# ───────────────────────────────────────────────────────
"""Stages 1 and 2: what is billed, and what was used — or why nobody knows.

NO DATABASE IN THIS FILE, and that is the point being asserted as much as any
individual case. BR-BIL-039 makes stages 1–5 pure, and `pytest.mark.django_db`
is absent deliberately: if either stage ever reaches for a query these tests
fail with a database error rather than passing quietly against a connection
that happened to be open. Purity is what lets the S31.2 preview and the real
run be the same code with the last stage withheld — so it is worth a test that
would notice it going away.

THE CASE THIS FILE EXISTS FOR is `tc4`: a missing read must not become a zero.
The two are one careless line apart, and the wrong one bills a customer nothing
for water they used.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.billing.contracts import AccountBillingData, ServiceReading
from apps.billing.exceptions import BillingRuleError
from apps.billing.stages import measure_consumption as stage2
from apps.billing.stages import resolve_subscription as stage1

ELECTRIC = rating_seam.TariffConfig(
    service="electric",
    model="flat",
    billed_unit="kWh",
    base_charge=Decimal("18.50"),
    unit_price=Decimal("0.12"),
)
WATER = rating_seam.TariffConfig(
    service="water",
    model="flat",
    billed_unit="kgal",
    base_charge=Decimal("12.00"),
    unit_price=Decimal("3.00"),
)


def account(**overrides) -> AccountBillingData:
    values = dict(
        account_id="acct-1",
        account_no="A-10432",
        behavior_class=stage1.CLASS_BILLABLE,
        currency="USD",
        tax_exempt=False,
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        cycle_days=30,
        service_days=30,
        rate_plan_id="plan-1",
        rate_plan_name="Residential Standard",
        rate_plan_version=3,
        tariffs=(ELECTRIC,),
        readings=(
            ServiceReading(
                service_code="electric",
                consumption=rating_seam.Quantity(amount=Decimal("684"), unit="kWh"),
            ),
        ),
    )
    values.update(overrides)
    return AccountBillingData(**values)


# ── stage 1 · resolve-subscription ─────────────────────────────────────────


def test_us_bil_029_tc1__stage_1_resolves_what_is_billed():
    """The ordinary path: an active account on a plan, whole period."""
    subscription = stage1.resolve_subscription(account())

    assert subscription.account_no == "A-10432"
    assert subscription.rate_plan_version == 3  # snapshot travels for the bill
    assert subscription.currency == "USD"  # rule 2 — never defaulted
    assert subscription.base_only is False
    assert subscription.period.cycle_days == 30 and subscription.period.service_days == 30


def test_us_bil_029_tc2__a_missing_plan_refuses_rather_than_billing_nothing():
    """BR-MET-040 CONFIRMED — a unit without a plan BLOCKS.

    The failure mode this prevents is the quiet one: an account with no plan
    has no tariffs, so a careless pipeline prices nothing, produces a bill of
    $0.00, and issues it. The customer is told they owe nothing and the utility
    never finds out.
    """
    with pytest.raises(BillingRuleError, match="BR-MET-040"):
        stage1.resolve_subscription(account(rate_plan_id=None, tariffs=()))


def test_us_bil_029_tc3__an_unknown_behaviour_class_refuses_both_ways():
    """Neither default is safe, so there is no default (BR-CUS-055).

    Defaulting to non-billable silently drops a paying customer from the run.
    Defaulting to billable bills someone the rules may forbid billing. Both are
    wrong quietly, which is the worst way to be wrong about money.
    """
    with pytest.raises(BillingRuleError, match="unknown behaviour class"):
        stage1.resolve_subscription(account(behavior_class="probationary"))


def test_us_bil_029_tc3b__a_non_billable_account_never_reaches_the_pipeline():
    """Scope is decided before stage 1; arriving here means gather let it through."""
    with pytest.raises(BillingRuleError, match="not billed"):
        stage1.resolve_subscription(account(behavior_class=stage1.CLASS_NON_BILLABLE))


def test_us_bil_029_tc3c__a_missing_currency_refuses():
    """CLAUDE.md rule 2 — money never travels without its CHAR(3) partner."""
    with pytest.raises(BillingRuleError, match="rule 2"):
        stage1.resolve_subscription(account(currency=""))


def test_us_bil_029_tc3d__a_mid_period_move_in_carries_both_day_counts():
    """B4.3 — the proration factor is derived ONCE, downstream, from both.

    Moved in on the 12th: 19 service days in a 30-day cycle. Carrying both
    numbers rather than a pre-computed factor is what stops base proration and
    tier-threshold scaling being driven by two figures that disagree.
    """
    subscription = stage1.resolve_subscription(account(service_days=19))
    assert (subscription.period.cycle_days, subscription.period.service_days) == (30, 19)


# ── stage 2 · measure-consumption ──────────────────────────────────────────


def test_us_bil_029_tc4__a_missing_read_is_never_a_zero():
    """THE CASE THIS FILE EXISTS FOR (BR-BIL-015).

    A meter nobody could reach and a meter that genuinely did not move produce
    the same number if you are careless. One of them is a customer billed
    nothing for water they used. The absence is carried forward with its
    reason, for a human to resolve — estimate, hold, or bill without the
    service.
    """
    data = account(
        tariffs=(ELECTRIC, WATER),
        readings=(
            ServiceReading(
                service_code="electric",
                consumption=rating_seam.Quantity(amount=Decimal("684"), unit="kWh"),
            ),
            ServiceReading(service_code="water", absent_reason="no_read"),
        ),
    )
    usage = stage2.measure_consumption(stage1.resolve_subscription(data), data)

    assert len(usage.measured) == 1 and usage.measured[0].service_code == "electric"
    assert len(usage.unmeasured) == 1
    missing = usage.unmeasured[0]
    assert missing.service_code == "water"
    assert missing.consumption is None  # NOT Decimal("0")
    assert missing.absent_reason == "no_read"  # the screen groups on this


def test_us_bil_029_tc5__a_genuine_zero_is_measured_and_billable():
    """An empty apartment whose meter really did not move used 0 kWh.

    That is a measurement, not an absence: it prices to $0.00 of usage plus
    whatever base charges the plan carries. Confusing it with a missing read
    would send it to the exception queue every month for no reason.
    """
    data = account(
        readings=(
            ServiceReading(
                service_code="electric",
                consumption=rating_seam.Quantity(amount=Decimal("0"), unit="kWh"),
            ),
        )
    )
    usage = stage2.measure_consumption(stage1.resolve_subscription(data), data)

    assert usage.unmeasured == ()
    assert usage.measured[0].consumption.amount == Decimal("0")
    assert usage.measured[0].consumption.unit == "kWh"  # rule 3 survives


def test_us_bil_029_tc6__a_base_only_account_measures_no_usage_at_all():
    """BR-CUS-055 — Vacation-hold / Suspended bills base charges, not usage.

    `None`, not zero. A $0.00 usage line on the bill asserts the meter was read
    and came to nothing; it was not read, because this account is not being
    billed usage at all. The bill should not show a line for something that was
    never charged.
    """
    data = account(behavior_class=stage1.CLASS_BASE_ONLY)
    subscription = stage1.resolve_subscription(data)
    assert subscription.base_only is True

    usage = stage2.measure_consumption(subscription, data)
    assert usage.measured == ()
    assert usage.unmeasured[0].absent_reason == stage2.ABSENT_BASE_ONLY


def test_us_bil_029_tc7__an_estimated_quantity_says_so():
    """BR-MET-029 — an estimate changes what the bill says, so it travels."""
    data = account(
        readings=(
            ServiceReading(
                service_code="electric",
                consumption=rating_seam.Quantity(amount=Decimal("618"), unit="kWh"),
                estimated=True,
            ),
        )
    )
    usage = stage2.measure_consumption(stage1.resolve_subscription(data), data)
    assert usage.measured[0].estimated is True


def test_us_bil_029_tc8__a_unitless_quantity_raises_rather_than_billing():
    """CLAUDE.md rule 3. Metering never emits one, so this means it was hand-built."""
    data = account(
        readings=(
            ServiceReading(
                service_code="electric",
                consumption=rating_seam.Quantity(amount=Decimal("684"), unit=""),
            ),
        )
    )
    with pytest.raises(BillingRuleError, match="rule 3"):
        stage2.measure_consumption(stage1.resolve_subscription(data), data)


def test_us_bil_029_tc9__the_two_arguments_must_be_the_same_account():
    """Billing one customer for another's usage would be undetectable downstream.

    Every figure on the resulting bill would be internally consistent. Nothing
    later in the pipeline could notice, so the check belongs at the seam.
    """
    data = account()
    other = stage1.resolve_subscription(account(account_id="acct-2", account_no="A-99999"))
    with pytest.raises(BillingRuleError, match="same account"):
        stage2.measure_consumption(other, data)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-029@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure stages) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · NO django_db marker anywhere in this file — deliberate:
#         BR-BIL-039 makes these stages pure, so a stage that starts querying
#         fails here with a database error instead of passing quietly against
#         an open connection. That absence is an assertion.
# exceptions: covers stages 1 and 2 only. Stages 3–5 are rating's and are
#         covered by the golden suite; 6 and 7 are not built. Stated so this
#         file does not read as covering "the run"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
