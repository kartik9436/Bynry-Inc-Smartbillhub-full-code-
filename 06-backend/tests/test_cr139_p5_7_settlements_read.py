# ── Trace ──────────────────────────────────────────────
# Change:  CR-139-BRC07 — the payments blueprint's phase 5, the READ half of
#          `P5.7` (the two Settlements screens) and the whole of the scan door
#          `P5.8` calls. Drawing: p069–p072 and p067–p068, read as IMAGES at
#          2.0 (B14 rule 42).
# Rules:   CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money is a
#          decimal STRING, four places) · B14 rule 31 (no database id is ever
#          the visible value of a field — asserted as a property of the WIRE,
#          which is the only place a test can see it) · NFR-3 (server
#          pagination) · BR-TEN-043 (the caller names the day) · BR-SHL-011 ·
#          hard-won law 7 (every case below answers *what would make this pass
#          wrongly* in its own docstring)
# Defect:  DEF-PAY-6286 — the read no `CR-139-BRC07` §4 task row owned
# Tests:   this file. The screens' own rendering is
#          `07-frontend/src/features/payments/settlementScreens.dom.test.tsx`.
# ───────────────────────────────────────────────────────
"""What the two Settlements screens read, and what the Scan source parses.

WHAT IS NOT HERE, AND WHY — READ THIS BEFORE ADDING TO IT
-----------------------------------------------------------
`config/settings/test.py` hardcodes in-memory SQLite, so **RLS is not what
keeps one tenant's payouts out of another's list here** — the querysets filter
on `tenant_id` and that is what these cases check. The database-level
guarantee is `payments/0039` and is asserted in `test_cr139_p5_rls_pg.py` and
`10-scripts/cr139_p5_rls_and_savepoint_proof.py`, both of which need a real
PostgreSQL. Saying so is the point: a check that cannot cover its whole subject
must print what it skipped beside what it checked (hard-won law 7).
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import models as payment_models
from apps.payments import settlement_models, settlements_read
from apps.payments.exceptions import PaymentRuleError
from apps.tenancy.models import PaymentMethod
from core.pagination import ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import tenant_ctx

pytestmark: list = []

#: ⚠ **A NEUTRAL PROCESSOR KEY, ON PURPOSE.** `BR-INT-037` and `G77` keep a
#: vendor name out of `apps/payments`; a fixture is not that module, but a test
#: that hard-codes a real processor is the string somebody later copies.
PROVIDER = "sandbox_pay"
PAID_OUT_AT = datetime(2026, 9, 21, 7, 14, tzinfo=UTC)
POSTED_AT = datetime(2026, 9, 20, 19, 22, tzinfo=UTC)


def _method(tenant, code: str):
    """The tenant's own tender row — **fetched, not created.**

    ⚠ **THE W0 FIXTURE ALREADY SEEDS THE SEVEN** (`lookup_defaults.json`, plus
    `tap_pay` from `P5.11`), and `uq_payment_methods_tenant_code_ci` refuses a
    second row with the same code. The first draft of this helper CREATED one
    and every case using it died on an integrity error — loudly, which is the
    good outcome, and worth the comment because the seeded list is exactly the
    thing `PROVIDER_SETTLED_TENDERS` names by code.
    """
    found = PaymentMethod.objects.filter(tenant=tenant, code=code).first()
    return found or PaymentMethod.objects.create(tenant=tenant, code=code, name=code.title())


def _account(actor, tenant):
    """One account for a payment to hang off. The same helper shape
    `test_cr139_p5_settlements.py` uses, and for the same reason: these cases
    are about the READ, and routing them through `services.record_payment`
    would make a failure here ambiguous between two modules."""
    from apps.customers import models as customer_models

    from tests.test_us_met_helpers import make_premises, make_unit

    premises = make_premises(
        actor, address_line="1901 Bluestem Ln", services_available=["electric"]
    )
    unit = make_unit(actor, premises["id"], label="Unit A", services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=f"A-{uuid.uuid4().hex[:8]}",
    )


def _payment(tenant, account, *, amount: Decimal, method, reference: str):
    return payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        amount=amount,
        currency="USD",
        method=method,
        confirmation=reference,
        status=payment_models.PAYMENT_CLEARED,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
    )


def _payout(tenant, *, code: str, gross: str, fees: str, net: str, status="received"):
    return settlement_models.Settlement.objects.create(
        tenant=tenant,
        code=code,
        provider=PROVIDER,
        paid_out_at=PAID_OUT_AT,
        gross=Decimal(gross),
        fees=Decimal(fees),
        net=Decimal(net),
        currency="USD",
        status=status,
    )


# ═══════════════════════════════════════════════════════════════════════════
#  5·1 — THE LIST
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_cr139_p5_7_a_row_carries_no_database_id(brazos, dana):
    """B14 rule 31, asserted on the WIRE rather than on a rendered screen.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a screen that never rendered the
    id would satisfy a rendering check while the id travelled — and the next
    lane to add a column would have it to hand. So the assertion is that the
    payload has no `id` member at all, which is the only form of this rule a
    test can enforce for every future consumer at once.
    """
    with tenant_ctx(brazos):
        _payout(brazos, code="STL-260921-CARD", gross="200.0000", fees="5.8000", net="194.2000")
        rows = settlements_read.settlement_rows(
            settlements_read.settlement_list_queryset(ListParams())
        )
    assert len(rows) == 1
    assert "id" not in rows[0]
    assert rows[0]["code"] == "STL-260921-CARD"
    # Hard rule 2 — a decimal STRING at four places, beside its CHAR(3) code.
    assert rows[0]["net"] == "194.2000"
    assert rows[0]["currency"] == "USD"


@pytest.mark.django_db
def test_cr139_p5_7_the_list_filters_and_searches_what_a_clerk_can_read(brazos, dana):
    """`f.state`, `f.provider` and `q` — and `q` matches no id.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a `q` that matched everything
    would satisfy the first assertion and fail the second, which is why the
    negative one is here. A filter silently dropped (`parse_list_params`
    ignores an undeclared name — `DEF-PAY-6235`) would turn a narrowed question
    into the whole list, and the endpoint refuses an undeclared `f.` for
    exactly that reason.
    """
    with tenant_ctx(brazos):
        first = _payout(
            brazos, code="STL-260921-CARD", gross="200.0000", fees="5.8000", net="194.2000"
        )
        _payout(
            brazos,
            code="STL-260920-ACH",
            gross="100.0000",
            fees="0.0000",
            net="100.0000",
        )
        listed = settlements_read.settlement_list_queryset(ListParams(q="260921"))
        assert [row.code for row in listed] == ["STL-260921-CARD"]
        # An id is not something a clerk could have read in order to search for.
        assert not settlements_read.settlement_list_queryset(ListParams(q=str(first.pk))).exists()
        received = settlements_read.settlement_list_queryset(
            ListParams(filters={"state": "received"})
        )
        assert received.count() == 2
        assert (
            settlements_read.settlement_list_queryset(
                ListParams(filters={"provider": "somebody_else"})
            ).count()
            == 0
        )


@pytest.mark.django_db
def test_cr139_p5_7_the_day_shaped_tiles_answer_null_without_an_as_of(brazos, dana):
    """`BR-TEN-043` — and the null is NOT a zero (`DEF-127`).

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a totals function that returned
    `"0.0000"` would render as *"nothing was paid out today"*, which is a
    different and far more alarming statement than *"we cannot answer"*. So the
    assertion is `is None` and not falsiness, and the two tiles that are NOT
    day-shaped are asserted in the same case — an over-eager fix that made
    everything null would otherwise pass.
    """
    with tenant_ctx(brazos):
        _payout(brazos, code="STL-260921-CARD", gross="200.0000", fees="5.8000", net="194.2000")
        queryset = settlements_read.settlement_list_queryset(ListParams())
        blind = settlements_read.settlement_list_totals(queryset, as_of=None)
        assert blind["paid_out_today"] is None
        assert blind["fees_this_month"] is None
        assert blind["totals_unavailable"] == "as_of_missing"
        # Not day-shaped, so they answer regardless.
        assert blind["unmatched"] == 1
        assert blind["awaiting_settlement"] == "0.0000"

        seeing = settlements_read.settlement_list_totals(queryset, as_of=date(2026, 9, 21))
        assert seeing["paid_out_today"] == "194.2000"
        assert seeing["paid_out_today_providers"] == 1
        assert seeing["fees_this_month"] == "5.8000"
        assert seeing["totals_unavailable"] is None


@pytest.mark.django_db
def test_cr139_p5_7_awaiting_settlement_is_a_fact_about_the_tender(brazos, dana):
    """The decision this lane made and wrote down — decision log 2026-09-23.

    A card payment nobody has paid out yet is AWAITING SETTLEMENT. **Cash in
    the till is not** — nobody is ever going to pay the utility out for its own
    drawer, so counting it would give a tile that never falls.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** using
    `settlements.awaiting_settlement_filter()` alone. It answers *"this payment
    is in no payout"*, which is TRUE of the cash as well — its own docstring
    says so and hands the narrowing to the screen. A test with only a card
    payment in it would pass on either version, so the cash row is the control
    that makes this case mean something.

    The worked figure: `$120.00` of card beside `$400.00` of cash reads
    **`$120.00 · 1 payment`**, not `$520.00`.
    """
    with tenant_ctx(brazos):
        card = _method(brazos, "card")
        cash = _method(brazos, "cash")
        account = _account(dana, brazos)
        _payment(brazos, account, amount=Decimal("120.0000"), method=card, reference="auth 4471")
        _payment(brazos, account, amount=Decimal("400.0000"), method=cash, reference=None)
        totals = settlements_read.settlement_list_totals(
            settlements_read.settlement_list_queryset(ListParams()), as_of=None
        )
    assert totals["awaiting_settlement"] == "120.0000"
    assert totals["awaiting_settlement_payments"] == 1


# ═══════════════════════════════════════════════════════════════════════════
#  5·2 — ONE PAYOUT
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_cr139_p5_7_a_payout_resolves_by_the_providers_reference(brazos, dana):
    """p071's address is `…/settlements/STL-260921-CARD`, not a uuid.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a resolver that ALSO accepted a
    primary key would satisfy the happy case and quietly keep rule 31's door
    open, so the unknown-reference case asserts a REFUSAL rather than a
    fallback — and it refuses as ABSENT rather than as forbidden, because a 403
    would confirm the row exists in somebody else's utility (BR-TEN-003, HR-1).
    """
    with tenant_ctx(brazos):
        _payout(brazos, code="STL-260921-CARD", gross="200.0000", fees="5.8000", net="194.2000")
        found = settlements_read.settlement_detail("STL-260921-CARD")
        assert found["code"] == "STL-260921-CARD"
        assert "id" not in found
        # `fees / gross`, computed on the SERVER: dividing two decimal strings
        # in a browser is a float division on a money path (hard rule 2).
        assert found["fee_share"] == "2.90"
        with pytest.raises(PaymentRuleError):
            settlements_read.settlement_detail("STL-NOT-A-PAYOUT")


@pytest.mark.django_db
def test_cr139_p5_7_a_member_row_shows_the_payments_own_amount(brazos, dana):
    """The money-correctness heart of the phase, on the screen that shows it.

    A **$100.00** card payment with a **$2.90** fee is a $100.00 payment and a
    $2.90 expense — never a $97.10 payment.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** asserting only that two numbers
    are present. So the netted figure is asserted ABSENT: a row builder that
    subtracted would still print two columns and would still look right.
    """
    with tenant_ctx(brazos):
        card = _method(brazos, "card")
        account = _account(dana, brazos)
        payment = _payment(
            brazos, account, amount=Decimal("100.0000"), method=card, reference="auth 4471"
        )
        payout = _payout(
            brazos, code="STL-260921-CARD", gross="100.0000", fees="2.9000", net="97.1000"
        )
        settlement_models.SettlementMember.objects.create(
            tenant=brazos,
            settlement=payout,
            payment=payment,
            gross=Decimal("100.0000"),
            fee=Decimal("2.9000"),
        )
        rows = settlements_read.member_rows(
            settlements_read.member_list_queryset(payout, ListParams())
        )
    assert len(rows) == 1
    assert rows[0]["gross"] == "100.0000"
    assert rows[0]["fee"] == "2.9000"
    assert rows[0]["gross"] != "97.1000"
    assert rows[0]["reference"] == "auth 4471"
    assert "id" not in rows[0]
    assert "payment_id" not in rows[0]


@pytest.mark.django_db
def test_cr139_p5_7_one_tenants_payouts_are_not_in_anothers_list(brazos, dana, lonestar):
    """Hard rule 1, at the queryset.

    ⚠ **WHAT THIS DOES NOT PROVE, AND THE NUMBER MATTERS:** the suite runs on
    SQLite, where the RLS policies `payments/0039` installs do not exist at
    all. This asserts the QUERYSET filters; the DATABASE guarantee is two
    PostgreSQL-only proofs (`test_cr139_p5_rls_pg.py` and
    `10-scripts/cr139_p5_rls_and_savepoint_proof.py`), and a green run of this
    file says nothing about them.
    """
    with tenant_ctx(brazos):
        _payout(brazos, code="STL-260921-CARD", gross="200.0000", fees="5.8000", net="194.2000")
        assert settlements_read.settlement_list_queryset(ListParams()).count() == 1
    with tenant_ctx(lonestar):
        assert settlements_read.settlement_list_queryset(ListParams()).count() == 0
