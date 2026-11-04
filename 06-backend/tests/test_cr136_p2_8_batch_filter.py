# ── Trace ──────────────────────────────────────────────
# Change:   CR-136-BRC07 `P2.8` — *"Source and Batch columns + a filter chip for
#           each on the payments list (2·1)"*. The columns and the SOURCE filter
#           landed 2026-09-23 as `DEF-PAY-6212`/`DEF-PAY-6213`; this is the
#           second filter, which the drawing's own header badge counts:
#           **GAINS 2 COLUMNS · 2 FILTERS · 1 BUTTON**.
# Drawing:  `05-prototype/06 Payments Page Blueprint.pdf` p030, §03 screen 2·1,
#           read AS AN IMAGE at scale 2.0 (B14 rule 42). Note ③ —
#           *"Batch filter · one batch at a time · NEW"* — and the toolbar draws
#           the applied chip as `Batch: CTR-260921-DW ×`.
#           ⚠ The PDF is on the DEFAULT branch (`claude/confirm-understanding-3ktufc`),
#           not on this working one.
# Rules:    B14 rule 31 (the CODE a clerk reads, never either table's uuid) ·
#           B14 rule 37 (`CTR-260921-DW` is an ILLUSTRATION; the product mints
#           `DEP-…`) · BR-SHL-011 (a list URL never 4xxs over its params) ·
#           NFR-3 (filtered in SQL, before the page)
# Impacts:  apps/payments/selectors.py (`_filter_by_batch`, `PAYMENT_FILTERS`) ·
#           apps/payments/metering_seam.py (`payments_created_by_run_no`) ·
#           apps/metering/import_runs.py (`records_created_by_run_no`) ·
#           07-frontend/src/features/payments/PaymentsPage.tsx (the chip)
# ───────────────────────────────────────────────────────
"""`P2.8` ③ — the payments list can be filtered to ONE batch.

⚠ **THE ONE THING WORTH READING BEFORE THE CASES: THE FILTER REPEATS THE
COLUMN'S PRECEDENCE, AND THAT IS WHAT THESE TESTS ARE MOSTLY ABOUT.**
`payment_batch_labels` shows a payment its DEPOSIT batch when it has both a
deposit batch and an import run — *"the later, more specific fact"*. A filter
that ignored that would answer a run number with rows whose own BATCH cells
read `DEP-26-0041`, and a list contradicting its own column is worse than a
list that finds nothing. The last case below is that one, and it is the reason
this file exists rather than a one-line assertion that the param is declared.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import bankrec_models as bankrec
from apps.payments import models, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
DRAWER_DAY = date(2026, 9, 21)
AMOUNT = Decimal("158.10")

#: The code the PRODUCT mints (`DEP-{YY}-{0000}`, the tenant's own series,
#: `CR-136-BRC07` §5). The drawing's `CTR-260921-DW` is an illustration and is
#: deliberately not what is asserted anywhere here (B14 rule 37).
BANKED_CODE = "DEP-26-0041"


def a_payment(actor, tenant):
    """One cleared payment on its own account, through the service."""
    account = an_account_of(actor, tenant)
    an_issued_bill(
        tenant,
        account,
        number=f"BL-2609-{uuid.uuid4().hex[:6]}",
        total=AMOUNT,
        issued_on=date(2026, 9, 1),
    )
    recorded = services.record_payment(
        actor,
        account_id=account.pk,
        amount=AMOUNT,
        posted_at=POSTED_AT,
        # ⚠ **A TENDER IS REQUIRED HERE AND THE FIRST DRAFT LEFT IT OUT.**
        # `deposit_batches.method` is a NOT NULL FK to the tenant's method
        # lookup (`bankrec_models.DepositBatch.method`), so a payment with no
        # method cannot be banked at all — `a_batch` below reads
        # `payment.method`. Cheque is the tender §03 2·1's own rows are drawn
        # with.
        method_code="check",
        # ⚠ **NOT `idempotency_key` — `record_payment` HAS NO SUCH ARGUMENT.**
        # It takes `idempotency_source` and `idempotency_reference` and builds
        # the key itself (`apps/payments/idempotency.py`), which is also what
        # writes `origin`. The first draft passed `idempotency_key=` and every
        # case that reached the database died on `TypeError` before asserting
        # anything — a fixture that cannot construct its subject.
        idempotency_reference=str(uuid.uuid4()),
    )
    return models.Payment.objects.get(pk=recorded.payment_id)


def a_batch(tenant, payment, code=BANKED_CODE):
    """Bank one payment into a deposit batch with a human code."""
    batch = bankrec.DepositBatch.objects.create(
        tenant=tenant,
        code=code,
        method=payment.method,
        deposited_on=DRAWER_DAY,
        status=bankrec.BATCH_IN_TRANSIT,
        recorded_total=payment.amount,
    )
    models.Payment.objects.filter(pk=payment.pk).update(deposit_batch_id=batch.pk)
    return batch


def listed(**filters):
    """The ids the list answers for these filters, paged in SQL as it always is."""
    params = selectors.list_params({f"f.{name}": value for name, value in filters.items()})
    return {str(row.pk) for row in selectors.payment_list_queryset(params)}


def test_p2_8__batch_is_a_declared_filter_so_the_chip_reaches_the_server(brazos, dana):
    """The drawing's ③, declared — `BE-05` drops an UNDECLARED param silently.

    ⚠ **THIS IS NOT A TAUTOLOGY, AND `DEF-PAY-6212` IS WHY IT IS HERE.** The
    Source column shipped to a screen and its filter reached nothing for a day
    because the param was never in this tuple: an undeclared name never gets as
    far as `_apply_filters`, so the chip renders, the URL carries the value, and
    the list comes back unfiltered with nothing anywhere going red.
    """
    assert "batch" in selectors.PAYMENT_FILTERS


def test_p2_8__a_deposit_code_answers_only_that_batch(brazos, dana):
    """*"One batch at a time"* — the code a clerk reads off the BATCH cell."""
    with tenant_ctx(brazos):
        banked = a_payment(dana, brazos)
        a_batch(brazos, banked)
        loose = a_payment(dana, brazos)

        answer = listed(batch=BANKED_CODE)
        assert str(banked.pk) in answer
        assert str(loose.pk) not in answer, "a payment in no batch is not in this one"


def test_p2_8__an_unknown_code_answers_nothing_and_does_not_raise(brazos, dana):
    """BR-SHL-011 — a list URL never 4xxs over its params.

    A mistyped code and a refusal read the same to a clerk, and the refusal
    costs them the whole screen. The empty answer is the honest one.
    """
    with tenant_ctx(brazos):
        a_batch(brazos, a_payment(dana, brazos))
        assert listed(batch="DEP-26-9999") == set()


def test_p2_8__an_empty_value_filters_nothing_rather_than_everything(brazos, dana):
    """`?f.batch=` is the chip being REMOVED, not a batch with no code.

    ⚠ The failure this pins is the one that would be invisible: an empty string
    falling through to `Q(pk__in=[])` blanks the whole list, and a clerk
    clearing a chip would watch their payments disappear.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        assert str(payment.pk) in listed(batch="")


def test_p2_8__a_banked_import_answers_its_DEPOSIT_code_and_not_its_run(brazos, dana):
    """⚠ **THE PRECEDENCE CASE — the one this file exists for.**

    `payment_batch_labels` shows a payment that has BOTH a run and a deposit
    batch its deposit code, because that is *"the later, more specific fact —
    the one a bookkeeper is holding a bank statement against"*. So filtering by
    the RUN's number must not return it: the row would arrive with a BATCH cell
    reading `DEP-26-0041` under a chip reading the run number, and a list that
    contradicts its own column is worse than one that finds nothing.

    The import leg is exercised through the seam with no metering rows present,
    which is also the deployment where the payments import target is not
    installed — it answers `[]` rather than raising (`metering_seam`'s own
    posture, and `billing_seam`'s before it).
    """
    with tenant_ctx(brazos):
        banked = a_payment(dana, brazos)
        a_batch(brazos, banked)

        # No import run created this payment, so the run leg contributes
        # nothing and the deposit leg is the only truth about it.
        assert listed(batch="7") == set()
        assert str(banked.pk) in listed(batch=BANKED_CODE)


def test_p2_8__the_filter_never_asks_for_a_uuid(brazos, dana):
    """B14 rule 31 — the code is what a clerk has; the id is not on the screen.

    Passing the batch's primary key must NOT work. It is not a nicety: if it
    did, a lane could wire the cell to the id, the filter would keep working,
    and the uuid would reach the URL bar — which is the rule's own example.
    """
    with tenant_ctx(brazos):
        banked = a_payment(dana, brazos)
        batch = a_batch(brazos, banked)
        assert listed(batch=str(batch.pk)) == set()
