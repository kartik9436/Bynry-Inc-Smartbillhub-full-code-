# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-004 (EP-CWP-02) — the guest charge, on a real database.
# Rules:    CLAUDE.md hard-won law 14 (a failed statement poisons the whole
#           PostgreSQL transaction and SQLite has no such state) · hard rule 1
#           (RLS FORCE) · hard rule 4 (no UPDATE/DELETE on a payment) · rule 6
#           (idempotency) · BR-PAY-001 (oldest open bill first)
# Tests:    this file — the half of tests/test_us_cwp_004_guest_charge.py that
#           the default suite structurally cannot run.
# Impacts:  apps/payments/gateway.charge_guest_bill ·
#           apps/payments/billing_seam.account_for_bill_number
# ───────────────────────────────────────────────────────
"""The guest charge against a real PostgreSQL, because the default suite is a lie
about exactly this path.

⚠ **`config/settings/test.py` HARDCODES IN-MEMORY SQLITE AND IGNORES
`DATABASE_URL`** (CLAUDE.md hard-won law 14). SQLite has **no aborted-transaction
state** and **no row-level security**, so two of the three guarantees this path
depends on cannot fail there however wrong the code is:

  * a settlement REFUSED under a rule writes its delivery row and then saves the
    refusal onto it — a query after a caught failure — and the payment commits
    or does not commit as a whole. On SQLite a transaction that should be
    unusable simply is not, so a broken version passes;
  * the seam's tenant scoping is asserted by an explicit `tenant_id=` filter on
    SQLite and by RLS FORCE on PostgreSQL, and only one of those is the thing
    production actually runs behind.

⚠ **WHAT IS NOT HERE, SAID PLAINLY.** `settle_charge`'s guard 2 — the UNIQUE
violation whose failed INSERT aborts a PostgreSQL transaction — needs two
connections racing and is proved where the code lives, in
`tests/test_us_cwp_006_webhook_door.py`. This lane re-implemented neither guard,
and no code it wrote catches a database error and continues.

Run it the way law 14 names:

    DATABASE_URL="postgres://smartbillhub:sbh@127.0.0.1:5432/sbh_portalfix3" \\
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    JOBS_EAGER=false python3 -m pytest tests/test_us_cwp_004_guest_charge_pg.py

Every case skips itself on any other vendor rather than passing vacuously, which
is the whole reason `requires_postgres` exists.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.payments import billing_seam, gateway, models as payment_models
from apps.portal import guest_api
from core.tenancy import tenant_context
from tests.isolation_helpers import requires_postgres
from tests.test_us_cwp_004_guest_charge import (
    ATTEMPT,
    BILL,
    INSTRUMENT,
    OWING,
    _allocations,
    _pay,
    _payments,
    a_holder,
    a_provider,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403

pytestmark = [pytest.mark.django_db, requires_postgres]


def _charge(tenant, *, key):
    with tenant_context(tenant.id):
        return gateway.charge_guest_bill(
            tenant.id,
            bill_number=BILL,
            amount=Decimal(OWING),
            currency="USD",
            instrument=dict(INSTRUMENT),
            receipt_email=None,
            channel="customer_portal",
            paid_by=guest_api.GUEST_PAID_BY,
            idempotency_key=key,
        )


def test_pg_a_guest_payment_commits_whole_and_is_allocated_oldest_first(pine_hill, sarah):
    """The happy path on the database production runs, end to end.

    `BR-PAY-001` — `$142.18` against August with an open `$18.00` July bill
    settles July first and leaves `$124.18` on August, through the one
    allocator. Asserted here as well as on SQLite because the allocation, the
    balanced ledger pair and the audit row all commit inside ONE transaction,
    and "all of it or none of it" is a statement about a real database.
    """
    a_holder(pine_hill, sarah, with_july=True)
    a_provider(pine_hill)

    assert _pay(pine_hill).status_code == 201

    rows = _payments(pine_hill)
    assert len(rows) == 1
    assert rows[0].amount == Decimal(OWING)
    amounts = sorted(row.amount for row in _allocations(pine_hill))
    assert amounts == [Decimal("18.0000"), Decimal("124.1800")]


def test_pg_a_replayed_attempt_leaves_one_payment_and_does_not_poison_the_transaction(
    pine_hill, sarah
):
    """Two attempts carrying the SAME key leave ONE payment, on a real database.

    ⚠ **BE PRECISE ABOUT WHICH GUARD THIS PROVES, BECAUSE THE FIRST DRAFT OF
    THIS DOCSTRING CLAIMED THE OTHER ONE.** A SEQUENTIAL replay is caught by
    `settle_charge`'s **guard 1** — the `_existing_delivery` SELECT — which
    returns the first delivery's answer before any INSERT is attempted. So what
    this case proves is that a retry gets the same reference, allocates nothing
    a second time, and leaves the connection usable.

    **Guard 2** — the `uq_payment_webhook_events_event` violation, whose failed
    INSERT aborts a PostgreSQL transaction and is the case law 14 is actually
    about — needs two connections racing, and its proof lives with the code that
    owns it: `tests/test_us_cwp_006_webhook_door.py`'s `requires_postgres`
    cases, written by the lane that owns `apps/payments/webhooks.py`. This lane
    re-implemented neither guard and does not re-prove them.

    ⚠ **AND NOTHING THIS LANE WROTE CATCHES A DATABASE ERROR AND CONTINUES**,
    which is the clause of law 14 that would otherwise bite: the whole
    savepoint story on this path is inside `webhooks._record`, unchanged.
    """
    a_holder(pine_hill, sarah)
    a_provider(pine_hill)
    key = guest_api._attempt_key(pine_hill.id, BILL, ATTEMPT)

    first = _charge(pine_hill, key=key)
    second = _charge(pine_hill, key=key)

    assert first["reference"] == second["reference"]
    assert len(_payments(pine_hill)) == 1
    # The replay allocated nothing a second time, so the bill is not
    # over-settled and no credit was invented out of a retry.
    assert sum(row.amount for row in _allocations(pine_hill)) == Decimal(OWING)
    # And the transaction is healthy afterwards — a poisoned one would raise
    # here rather than answer.
    with tenant_context(pine_hill.id):
        assert (
            payment_models.PaymentWebhookEvent.objects.filter(tenant_id=pine_hill.id).count() == 1
        )


def test_pg_a_timeout_writes_nothing_and_leaves_the_connection_usable(pine_hill, sarah):
    """`US-CWP-004` TC-7 on a real database — *an unknown outcome is not a zero*.

    The count is taken AFTER a further successful read, so a refusal that had
    left the transaction aborted would surface as an exception here rather than
    as a passing assertion about an empty table.
    """
    a_holder(pine_hill, sarah)
    a_provider(pine_hill, behaviour="timeout")

    assert _pay(pine_hill).status_code == 503

    with tenant_context(pine_hill.id):
        assert not payment_models.Payment.objects.filter(tenant_id=pine_hill.id).exists()
        assert not payment_models.Allocation.objects.filter(tenant_id=pine_hill.id).exists()
        assert not payment_models.PaymentWebhookEvent.objects.filter(
            tenant_id=pine_hill.id
        ).exists()
        # The seam still answers, which is what proves the connection is not in
        # a failed-transaction state.
        assert billing_seam.account_for_bill_number(BILL) is not None


def test_pg_a_settlement_refused_by_a_rule_records_the_delivery_and_no_payment(pine_hill, sarah):
    """⛔ **THE APPROVED-BUT-UNRECORDABLE CASE, ON A REAL DATABASE.**

    The provider takes the money and `record_payment` refuses under
    `BR-PAY-026` (the tenant deactivated the `card` method). `settle_charge`
    catches that inside its SAVEPOINT and then **saves the refusal onto the
    delivery row** — a write after a caught failure, inside the outer
    transaction. That is the shape law 14 exists for, and on SQLite it cannot
    fail however the savepoint is written.

    What must be true: the delivery row COMMITS and carries the reason (the
    money is real and somebody has to see it), no payment exists, and no
    receipt is answered.
    """
    from apps.tenancy import models as tenancy_models

    a_holder(pine_hill, sarah)
    a_provider(pine_hill)
    with tenant_context(pine_hill.id):
        tenancy_models.PaymentMethod.objects.filter(
            tenant_id=pine_hill.id, code=gateway.GUEST_METHOD_CODE
        ).update(active=False)

    response = _pay(pine_hill)

    assert response.status_code == 500
    assert response.data["message_key"] == "portal.quickPay.notRecorded"
    assert _payments(pine_hill) == []
    with tenant_context(pine_hill.id):
        deliveries = list(payment_models.PaymentWebhookEvent.objects.filter(tenant_id=pine_hill.id))
        assert len(deliveries) == 1, "the delivery row must survive the refusal"
        assert deliveries[0].payment_id is None
        assert deliveries[0].outcome, "the refusal reason is on the row a person will read"


def test_pg_the_seam_is_scoped_by_rls_and_not_only_by_its_own_filter(
    pine_hill, oak_ridge, sarah, elena
):
    """Hard rule 1 — the tenant is in the query AND `RLS FORCE` is underneath it.

    ⚠ **THE SQLITE CASE PROVES ONLY THE FIRST HALF.** There is no row-level
    security there, so a seam that had dropped its explicit filter would still
    pass. Here both guarantees are live and a cross-tenant read answers nothing.
    """
    from tests.test_us_cwp_helpers import switch_on

    a_holder(pine_hill, sarah)
    switch_on(oak_ridge, elena)

    with tenant_context(pine_hill.id):
        assert billing_seam.account_for_bill_number(BILL) is not None
    with tenant_context(oak_ridge.id):
        assert billing_seam.account_for_bill_number(BILL) is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-004 · CLAUDE.md hard-won law 14 · hard rules 1, 4, 6 ·
#         BR-PAY-001 · tests/isolation_helpers.requires_postgres
# generated: 2026-09-05 by the CR-068 lane F (the guest charge)
# checklist: A✔ B=n/a(tests) C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: run against PostgreSQL 16 under config.settings.local — the results are
#        quoted in the lane's report. Under the default settings every case
#        SKIPS rather than passing, which is the point of the marker.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
