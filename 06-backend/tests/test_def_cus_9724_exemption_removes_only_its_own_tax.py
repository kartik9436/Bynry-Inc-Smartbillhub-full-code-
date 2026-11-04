# ── Trace ──────────────────────────────────────────────
# Change:  DEF-CUS-9724 (CR-171-BRC10, lane RULINGS-2) — PO ruling 2026-10-05,
#          decision log "FIVE PO RULINGS IN ONE REPLY" (A), verbatim:
#          "(a) An exemption removes only the tax named on its certificate.
#          The church pays $6.25."
# Rules:   BR-RAT-105 (a certificate is per tax; accounts.tax_exempt is
#          BLANKET) · B4.2 · hard-won law 14 (runs on PostgreSQL too)
# ───────────────────────────────────────────────────────
"""**A move-in's tax exemption removes ONLY the tax named on its certificate.**

THE PO's FIGURE: Marcus's church holds a certificate against the 2.00% CITY
tax. On a $100.00 bill it pays **$0.00** city tax and **$6.25** state tax
(6.25%), so its tax total is **$6.25** — not $0.00.

Until this fix the move-in also set the account's blanket `tax_exempt` flag
(`move_in_preferences._account_values`, 2.529.0; and the Billing step sent
`tax_exempt: true` beside the certificate), and the blanket flag zeroes every
authority at once — so the church paid $0.00 where $6.25 is owed.

The bill is priced the way a bill run prices it: the account context's
`tax_exempt` is `gather._tax_exempt_on(account, day)` (the BLANKET flag) and the
tax rules are `plan_tax_rules(..., account_id=…)` (the per-tax certificate).
The P1.15 test priced with a hard-coded `tax_exempt=False`, which is why it
never saw the blanket flag.

PROVED RED FIRST (hard-won law 7), at ee321e1d8:

    AssertionError: assert Decimal('0.00') == Decimal('6.25')
"""

import uuid
from decimal import Decimal

import pytest

from apps.billing import gather, rating_seam
from apps.customers import services as customers_services
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors
from tests.test_cr013_p4_tax_model import (
    FULL_MONTH,
    HUNDRED,
    INSIDE_CITY,
    NO_USAGE,
    a_tax,
    attach,
    today_of,
)
from tests.test_cr171_p1_15_move_in_preferences import _exemption, _move_in, _vacated
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _price(plan, account, today):
    """The tax on a $100.00 bill, with BOTH exemption facts a bill run reads."""
    rules = rating_selectors.plan_tax_rules(
        plan.id,
        today,
        customer_class="commercial",
        premises=INSIDE_CITY,
        services=("electric",),
        account_id=str(account.id),
    )
    priced = rating_seam.price_period(
        tariff=HUNDRED,
        consumption=NO_USAGE,
        period=FULL_MONTH,
        account=rating_seam.AccountContext(
            currency="USD", tax_exempt=gather._tax_exempt_on(account, today)
        ),
        taxes=tuple(
            rating_seam.TaxRule(
                code=rule["code"],
                rate=None if rule.get("rate") is None else Decimal(str(rule["rate"])),
                tax_id=rule.get("tax_id"),
                flat_amount=(
                    None if rule.get("flat_amount") is None else Decimal(str(rule["flat_amount"]))
                ),
            )
            for rule in rules
        ),
    )
    return priced


def _church(marcus_actor, tenant, payload_extra=None):
    today = today_of(tenant)
    with tenant_ctx(tenant):
        _u, plan, outgoing = _vacated(marcus_actor, tenant)
        city_tax, city = a_tax(
            tenant, "City", name="City utility tax", kind="percent", rate=Decimal("0.020000")
        )
        _state_tax, state = a_tax(
            tenant, "Texas State", name="TX State", kind="percent", rate=Decimal("0.062500")
        )
        attach(tenant, plan, city)
        attach(tenant, plan, state)
        category = rating_models.TaxExemptionCategory.objects.create(
            tenant=tenant, tax=city_tax, code="CHURCH", name="Religious organisation"
        )
        extra = dict(tax_exemption=_exemption(category))
        extra.update(payload_extra or {})
        result = _move_in(marcus_actor, outgoing, **extra)
        account = customers_services.models.Account.objects.get(pk=result["id"])
        priced = _price(plan, account, today)
    return account, priced


def test_def_cus_9724__the_church_pays_the_state_tax_and_only_the_city_tax_is_removed(
    brazos, marcus
):
    account, priced = _church(marcus, brazos)
    taxes = {line.description: line.amount for line in priced.lines_of("tax")}
    assert priced.tax_total == Decimal("6.25")
    assert taxes == {"Tax WD · Texas State": Decimal("6.25")}
    assert account.tax_exempt is False, "a per-tax certificate never sets the blanket flag"


def test_def_cus_9724__the_billing_steps_blanket_keys_beside_a_certificate_are_not_written(
    brazos, marcus
):
    """The 2.545.0 Billing step sent `tax_exempt: true` (and the reference and
    expiry) BESIDE the certificate block. With a certificate in the payload the
    certificate decides: the three blanket columns are not written from it."""
    account, priced = _church(
        marcus,
        brazos,
        {
            "tax_exempt": True,
            "tax_exempt_ref": "IA-EX-2231",
            "tax_exempt_expires": "2027-01-15",
        },
    )
    assert (account.tax_exempt, account.tax_exempt_ref, account.tax_exempt_expires) == (
        False,
        None,
        None,
    )
    assert priced.tax_total == Decimal("6.25")


def test_def_cus_9724__an_account_with_no_certificate_pays_both(brazos, marcus):
    """The control: the same plan, no certificate — $2.00 + $6.25 = $8.25."""
    today = today_of(brazos)
    with tenant_ctx(brazos):
        _u, plan, outgoing = _vacated(marcus, brazos)
        _c, city = a_tax(
            brazos, "City", name="City utility tax", kind="percent", rate=Decimal("0.020000")
        )
        _s, state = a_tax(
            brazos, "Texas State", name="TX State", kind="percent", rate=Decimal("0.062500")
        )
        attach(brazos, plan, city)
        attach(brazos, plan, state)
        result = _move_in(marcus, outgoing)
        account = customers_services.models.Account.objects.get(pk=result["id"])
        priced = _price(plan, account, today)
    assert priced.tax_total == Decimal("8.25")
    assert uuid.UUID(str(account.id))
