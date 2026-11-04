# ── Trace ──────────────────────────────────────────────
# Story:  The Invoice Cloud *Make Payment* API — decision log 2026-09-24. The
#         half of hard rule 6 that the everyday suite CANNOT prove.
# Rules:  CLAUDE.md hard rule 6 (idempotency on inbound payments) · hard rule 4
#         (a payment row may not be UPDATEd or DELETEd, so a duplicate is
#         PERMANENT) · hard-won law 14 (prove a transaction-shaped guard on
#         PostgreSQL, because the suite runs on SQLite) · hard-won law 7
#         (a check that is structurally incapable of failing)
# Tests:  this file. The everyday half is
#         tests/test_invoice_cloud_make_payment.py
# Impacts: apps/payments/services.record_payment (the pre-check AND the index) ·
#         apps/payments/models.Payment.webhook_key + uq_payments_webhook_key
# ───────────────────────────────────────────────────────
"""TWO SIMULTANEOUS COPIES OF ONE PAYMENT — ONLY ONE IS TAKEN. PROVED ON POSTGRES.

    DATABASE_URL='postgres://smartbillhub:smartbillhub@127.0.0.1:5432/smartbillhub?sslmode=disable' \\
    JOBS_EAGER=false \\
        pytest tests/test_invoice_cloud_make_payment_pg.py --ds=config.settings.pgtest

⚠ **WHY THIS CANNOT BE A CASE IN THE EVERYDAY FILE.** Hard rule 6 is carried
here by TWO independent guards and the everyday suite can only reach one of
them:

  1. **The pre-check** — `record_payment._existing()` looks the key up BEFORE it
     opens a transaction, so a retry costs one SELECT and burns no `PMT-`
     number. `test_a_replay_is_a_200_…` in the sibling file proves this one,
     and proves it by counting AUDIT ROWS rather than payments, because a
     payment count cannot tell the cheap path from the expensive one.
  2. **`uq_payments_webhook_key`** — the database's own unique index on
     `(tenant_id, webhook_key)`, which catches the copy that slipped past the
     pre-check because the winner had not COMMITTED yet.

**Guard 2 cannot be exercised on the default suite at all.** It needs a row
that is committed in one connection and invisible to another, which is a
property of concurrent transactions; the suite runs every case inside one
rolled-back transaction on in-memory SQLite (`config/settings/test.py`
hardcodes it), where there is no second connection to be invisible to. A case
written there would pass on the pre-check alone and prove nothing about the
index — which is `DEF-058`'s exact shape: **that guard was switched off for a
day and the suite stayed green, because the OTHER layer caught the duplicate.**

⚠ **AND THE STAKES HERE ARE HIGHER THAN A DOUBLE-CLICK.** Hard rule 4 forbids
UPDATE and DELETE on a payment row, so a duplicate this product lets in is
**permanent**: the customer has been recorded as paying twice, the correction
is a second row of its own, and the utility's takings for the day are wrong in
a way that only reconciliation finds.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per law 7
--------------------------------------------------------------------
**1 · Running on SQLite and reporting a pass.** `G5` once ran the whole
tenant-isolation suite on SQLite and called 192 skips a pass. Every case here
carries `requires_postgres`, which SKIPS rather than passes — and the module
asserts the vendor out loud in `test_this_file_is_actually_running_on_postgres`
so a skipped run is visible as a skipped run rather than as a green one.

**2 · "Simulating" the race by calling the endpoint twice.** That exercises the
pre-check and nothing else, which is precisely the thing this file exists to
get past. The first copy is committed **from a second connection** so the
pre-check genuinely cannot see it, which is the only way the INSERT reaches the
index.

**3 · Asserting that the second call raises.** It must NOT raise — a replay is
a `200` carrying the original payment (decision log 2026-09-24). Asserting an
exception would bake in the behaviour the ruling forbids.
"""

from __future__ import annotations

import json
import threading

import pytest
from django.db import connection, connections, transaction

from apps.integrations import invoice_cloud_payment as ic
from tests.isolation_helpers import requires_postgres  # noqa: F401
from tests.test_invoice_cloud_make_payment import (  # noqa: F401
    ACCOUNT_NO,
    BILL_NO,
    REFERENCE,
    _account,
    _body,
    _bytes,
    _connect,
    _issue,
    _payments,
    _post,
    invoice_cloud,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx


#: ⚠ **`serialized_rollback=True` IS NOT NOISE AND MUST NOT BE TIDIED AWAY
#: (`DEF-3522`, and `tests/conftest.py` names this trap and this flag as its
#: answer).** A `transaction=True` case tears down by FLUSHING, and the flush
#: empties the PLATFORM reference data the migrations seed —
#: `subscription_plans` among them. Without it the FIRST transactional case
#: here passes and then deletes the catalogue, and every later one dies at
#: SETUP inside an unrelated helper on
#: `SubscriptionPlan.objects.get(code="growth")` — a failure that names neither
#: test and reads as broken plumbing rather than as a proof that never ran.
#: **This lane met it exactly that way**: three errors, one pass, and the
#: passing one was the case that ran first.
_TRANSACTIONAL = pytest.mark.django_db(transaction=True, serialized_rollback=True)


@requires_postgres
@pytest.mark.django_db
def test_this_file_is_actually_running_on_postgres():
    """⚠ **THE CASE THAT STOPS A SKIPPED RUN READING AS A GREEN ONE.**

    `requires_postgres` is a `skipif`, and a skip is a pass to every eye that
    is not looking for it — CLAUDE.md law 7's *structurally incapable of
    failing*, and `G5`'s 192 skips reported as a pass. This one states the
    vendor, so a run that produced nothing is a run that says so.
    """
    assert connection.vendor == "postgresql", (
        "this file's whole purpose is the aborted-transaction and unique-index "
        f"behaviour PostgreSQL has and SQLite does not; it ran on {connection.vendor}"
    )


@requires_postgres
@_TRANSACTIONAL
def test_two_simultaneous_copies_of_one_payment_take_the_money_once(brazos, dana):
    """⚠ **THE DATABASE'S OWN GUARD, WITH THE PRE-CHECK BLINDED.**

    The shape of the race, which is a real one on a daily push: Invoice Cloud
    sends `TID161007`, times out waiting for our answer, and sends it again
    while the first is still in flight. **Both copies run their pre-check
    before either has committed, so both see nothing and both try to INSERT.**

    This reproduces it deterministically rather than by hoping two threads
    interleave: the first copy is committed **through a second connection**, so
    the second copy's pre-check — which runs in this connection's own snapshot
    — cannot see it, and its INSERT goes to the index. That is the only path
    that exercises `uq_payments_webhook_key`, and it is why this case exists.

    **What must happen: ONE payment row, and the loser gets a `200` naming the
    winner.** Not an exception, not a `409`, and above all not a second row —
    hard rule 4 makes a duplicate permanent.
    """
    with tenant_ctx(brazos):
        _connect(brazos, dana)
        account = _account(brazos, dana)
        _issue(brazos, account)

    # ── the WINNER, committed from another connection ────────────────────
    #
    # A thread gets its own connection, so its COMMIT is a real commit and not
    # a savepoint inside this test's. That is what makes the pre-check below
    # genuinely blind to it.
    outcome: dict = {}

    def _first() -> None:
        try:
            response = _post(brazos)
            outcome["status"] = response.status_code
            outcome["body"] = json.loads(_bytes(response))
        except Exception as exc:  # pragma: no cover - reported, never swallowed
            outcome["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            connections.close_all()

    winner = threading.Thread(target=_first)
    winner.start()
    winner.join(timeout=60)
    assert not winner.is_alive(), "the first copy never finished"
    assert "error" not in outcome, outcome.get("error")
    assert outcome["status"] == 200, outcome

    # ── the LOSER, whose pre-check we blind on purpose ────────────────────
    #
    # ⚠ **PATCHING `_existing` IS THE WHOLE TECHNIQUE AND IT IS NOT A
    # SHORTCUT.** It is the code-level equivalent of *the winner had not
    # committed yet*: the pre-check answers `None`, the transaction opens, a
    # `PMT-` number is taken, the INSERT runs, and `uq_payments_webhook_key`
    # is the only thing standing between the utility and a permanent second
    # payment. With the real pre-check in place this case would pass on layer
    # 1 and say nothing at all about layer 2 — `DEF-058` exactly.
    from apps.payments import services as payment_services

    real_existing = payment_services._existing
    calls: list[int] = []

    def _blind_once(tenant_id, key):
        """Blind the PRE-CHECK and nothing else.

        ⚠ **THE FIRST DRAFT PATCHED THIS TO RETURN `None` ALWAYS, AND THAT
        BROKE THE THING IT WAS TESTING.** `record_payment` calls `_existing`
        TWICE: once before the transaction (the pre-check) and once inside
        `except IntegrityError` (to find the winner and answer with it). A
        blanket patch blinds both, so the recovery finds nothing, re-raises,
        and the endpoint answers **500** — and the case would then have been
        "fixed" by asserting a 500, baking in the opposite of the ruling.

        **One-shot is also the truthful model of the race.** In production the
        pre-check misses because the winner has not COMMITTED yet, and by the
        time the unique index fires the winner HAS committed — so the second
        lookup finds it. That is exactly what this does.
        """
        calls.append(1)
        return None if len(calls) == 1 else real_existing(tenant_id, key)

    payment_services._existing = _blind_once
    try:
        second = _post(brazos)
    finally:
        payment_services._existing = real_existing

    assert len(calls) >= 2, (
        "the INSERT never reached `uq_payments_webhook_key` — `record_payment` did not "
        "enter its `except IntegrityError` recovery, so this case proved the pre-check "
        "again and said nothing about the index"
    )

    assert second.status_code == 200, _bytes(second)
    body = json.loads(_bytes(second))
    assert body["duplicate"] is True, (
        "the loser of the race must be told it is a replay, not that it failed — "
        "a partner told its request failed sends the money again"
    )
    assert body["payment_no"] == outcome["body"]["payment_no"], (
        "the loser must be handed the payment that EXISTS, so their reconciliation "
        "matches ours rather than a row that was rolled back"
    )

    with tenant_ctx(brazos):
        assert _payments(brazos).count() == 1, (
            "TWO payments for one Invoice Cloud reference. Hard rule 4 forbids UPDATE and "
            "DELETE on a payment, so this is permanent: the customer is recorded as having "
            "paid twice and the day's takings are wrong"
        )
        assert (
            _payments(brazos).get().webhook_key == "webhook|invoice_cloud:TID161007"
        )


@requires_postgres
@_TRANSACTIONAL
def test_a_refused_payment_leaves_no_half_written_row_behind(brazos, dana):
    """⚠ **HARD-WON LAW 14 ON THIS PATH: A REFUSAL THAT ABORTS THE TRANSACTION.**

    On PostgreSQL one failed statement poisons the whole transaction, and every
    later query raises `InFailedSqlTransaction`. So a refusal inside
    `record_payment` — a deactivated tender, a currency the account does not
    hold — has to leave the caller able to carry on and the database with
    nothing half-written. **SQLite has no aborted-transaction state, so the
    broken version of this passes the entire default suite green.**

    The case sends a tender this tenant does not have, asserts the `422`, and
    then **makes a good payment on the same connection**. The second half is
    the real assertion: if the refusal had poisoned the transaction, the good
    payment is what would blow up, and it would blow up in production on the
    next delivery of the day's batch rather than here.
    """
    with tenant_ctx(brazos):
        _connect(brazos, dana)
        account = _account(brazos, dana)
        _issue(brazos, account)

    refused = _post(brazos, body=_body(**{ic.FIELD_METHOD: "carrier_pigeon"}))
    assert refused.status_code == 422, _bytes(refused)
    assert json.loads(_bytes(refused))["code"] == ic.CODE_PAYMENT_REFUSED

    with tenant_ctx(brazos):
        assert not _payments(brazos).exists(), "a refused payment left a row behind"

    good = _post(brazos)
    assert good.status_code == 200, (
        f"the refusal poisoned the connection — this is hard-won law 14 and it is "
        f"invisible on SQLite: {_bytes(good)!r}"
    )
    with tenant_ctx(brazos):
        assert _payments(brazos).count() == 1


@requires_postgres
@pytest.mark.django_db
def test_the_unique_index_is_actually_on_the_table():
    """The guard the case above leans on, asserted to EXIST.

    ⚠ **A TEST THAT PROVES A RACE IS CAUGHT SAYS NOTHING ABOUT WHY.** If the
    index were dropped by a later migration the race case would still pass —
    the pre-check would catch it in most orderings — and the one time it
    mattered there would be two payments and no explanation. This reads
    `pg_indexes`, which is a fact about the deployed schema rather than about
    this process.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = 'payments' "
            "AND indexname = 'uq_payments_webhook_key'"
        )
        row = cursor.fetchone()
    assert row is not None, (
        "uq_payments_webhook_key is gone from `payments`. Hard rule 6's second layer on "
        "every inbound payment path — the partner door, the gateway webhook and the "
        "staff form — rests on this index"
    )
    definition = row[0].lower()
    assert "unique" in definition
    assert "tenant_id" in definition and "webhook_key" in definition, (
        "the index must be on (tenant_id, webhook_key): without the tenant one utility's "
        "reference would block another's, and with the tenant alone it would block "
        "everything"
    )
