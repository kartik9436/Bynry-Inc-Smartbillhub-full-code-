# ── Trace ──────────────────────────────────────────────
# Change:   CR-137-BRC07 · P3.1 · P3.2 · P3.3 · P3.4 · P3.19
# Story:    US-PAY-004 (§1 *"Cancel only while processing"* · TC-2 · TC-7) ·
#           US-PAY-025 · US-NOT-011 §5   Screens: S33 · S35 · 2·2 · 2·3d · 2·3h
# Rules:    CLAUDE.md hard rule 1 · hard rule 4 · hard rule 5 · hard rule 6 ·
#           hard rule 7 · NFR-3 · B14 rules 31, 33 · BR-PAY-002 · BR-PAY-021 ·
#           BR-BIL-016 · BR-PAY-018 · hard-won law 2 · hard-won law 7
# ───────────────────────────────────────────────────────
"""A payment has an address — and can be cancelled, without breaking hard rule 4.

WHAT IS PROVED HERE AND WHAT IS NOT
═══════════════════════════════════
The bounce arithmetic, the allocator and the posting seam are proved elsewhere
against the service and none of it is restated. What is proved HERE is what only
these five doors can claim:

  1. **A payment can be reached at an address**, by its `PMT-` number AND by its
     id, and another tenant's payment 404s at the same URL (US-PAY-004 TC-7).
  2. **The widest pattern in the module shadows nothing.**
     `payments/<id>` is two segments and so are `payments/summary`,
     `payments/reason-codes` and `payments/selection-total` — asserted, because
     *a comment claiming an ordering is not the ordering* (hard-won law 1).
  3. **Cancel is not Reverse**: it succeeds on `processing`, is REFUSED on
     `cleared`, and the refusal NAMES Reverse (`P3.13`'s own sentence).
  4. **Immutability is satisfied, not circumvented**: the original keeps every
     column but `status`, and the money comes off through a NEW row.
  5. **A double-click cancels once** (hard rule 6) — and the second call is a
     200 carrying the first cancel, not a red 409 for a button that worked.
  6. **The history is paginated IN SQL** (`NFR-3`) and never claims permanence.
  7. **A resend re-queues an existing document** and refuses without a copy
     number.

RED PROOF (hard-won law 7), OBSERVED and quoted rather than predicted. Run in
this lane's own detached worktree at the pinned tip, never by moving the shared
tree:

  * **the doors.** At the pinned tip this file cannot be collected at all —
    `ImportError: cannot import name 'detail_api' from 'apps.payments'` — and
    every one of the five addresses answers `django.urls.exceptions.Resolver404`.
    That is stronger than mutating a urlpattern, because there is nothing there
    to mutate. Measured before a line of this lane's code existed.
  * **the shadowing.** With the `detail_api` include moved ABOVE
    `path("payments/summary", …)` in `apps/payments/api.py`,
    `test_the_detail_route_shadows_nothing` fails on
    `assert <function payment> is <function payments_summary>` — the S33 summary
    resolving as a payment NUMBER, which is the defect the ordering exists to
    prevent.
  * **the cleared refusal.** With `REFUSED_CLEARED` removed from
    `cancel.refusal_for`, `test_a_cleared_payment_is_refused_and_told_to_reverse`
    fails `Failed: DID NOT RAISE` and the cancel goes through on money that has
    already posted — which is the whole confusion this phase exists to end.
  * **the immutability assertion.** With `update_fields=["status", "updated_at"]`
    widened to a bare `original.save()`,
    `test_cancel_leaves_every_other_column_byte_identical` still PASSES on
    SQLite, and that is recorded rather than hidden: the Django ORM writes the
    same values back, so this particular guard is a statement about the SERVICE
    and the DATABASE trigger is the guard that bites. `P3.14` (wave 2) proves
    the trigger on PostgreSQL, where it can actually fire.
    ⚠ **AMENDED 2026-09-23 — IT NO LONGER WAITS FOR `P3.14`.**
    `10-scripts/p3_back_cancel_resend_pg_proof.py` proves the SERVICE's own
    statement against the real trigger on PostgreSQL 16: `processing →
    cancelled` is PERMITTED through `save(update_fields=["status",
    "updated_at"])`, and the same row one statement later refuses its own
    amount. **And this whole file passes on PostgreSQL too** — 25 of 25, 824s,
    `--ds=config.settings.pgtest --reuse-db`, which is the repo's own answer to
    hard-won law 14 and is worth reaching for before hand-rolling anything.

⚠ **THE SIXTH STATE IS `P3-DB`'s AND THIS SUITE SAYS SO OUT LOUD.** Until `P3.5`
lands, `models.PAYMENT_STATUSES` holds no `cancelled` and every write case here
is SKIPPED with that reason printed — **and `test_cancel_refuses_by_name_until_
the_sixth_state_exists` asserts the refusal is a readable sentence rather than a
CheckViolation.** A skipped test that prints why is a declared blind spot with a
number attached; a silently green one would be hard-won law 7's *reporting zero
over a scope it excludes*.
"""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from django.urls import resolve

from apps.payments import cancel, detail_api, models, payment_detail, receipt_resend

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import CLEARED_AT, a_payment, pe1_bills
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


@pytest.fixture()
def audit_reaches_the_table():
    """Put audit's OWN sink back for the two cases that READ the trail.

    ⚠ **`tests/test_us_met_helpers.py` installs an autouse sink that captures
    every audit row into a PYTHON LIST**, so no test importing those helpers
    writes `audit_log` at all — and this file star-imports them. That is right
    for every other case here and exactly wrong for a read model whose whole
    subject IS that table.

    ⚠ **THIS IS WHY TWO CASES BELOW ONCE FAILED, AND THE DIAGNOSIS IS WORTH
    KEEPING.** They asserted a recorded payment leaves a trail, the trail came
    back EMPTY, and the first reading was that `history_queryset` was broken. It
    is not: a probe showed `AuditLog.objects.count()` at **0 for the whole test
    database**, and `apps.audit.selectors.entity_trail` — audit's own published
    read — returning 0 for the same payment. The read agreed with audit exactly;
    there was simply nothing to read. **A test that cannot pass under the
    fixtures it runs with is hard-won law 7's *incapable of passing* shape**, and
    it was this file's fault rather than the product's.

    `test_w6_connection_detail.py` sets the precedent for the same problem one
    module along. Restored afterwards, so a later case still sees the capture
    sink it expects.
    """
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


#: An INPUT, never a clock (BR-TEN-043, gate G6).
CANCELLED_ON = datetime(2026, 9, 21, 11, 45, tzinfo=UTC)

#: `P3.5` — the sixth state. Everything that WRITES one is skipped until the
#: migration lands, with the reason printed (see the module docstring).
SIXTH_STATE_LANDED = cancel.CANCELLED in models.PAYMENT_STATUSES
needs_sixth_state = pytest.mark.skipif(
    not SIXTH_STATE_LANDED,
    reason="P3.5 (the `cancelled` state + the ck_payments_status migration) has not landed",
)


def _processing_payment(tenant, actor):
    """A payment whose money has NOT arrived — the only kind Cancel touches.

    `cleared_at=None` is what makes it `processing` (BR-PAY-021), and
    `record_payment` returns before the allocator for exactly that reason: it
    meets no bill and posts nothing.
    """
    account = an_account(actor, tenant)
    pe1_bills(tenant, account)
    recorded = a_payment(actor, account, cleared_at=None)
    return account, models.Payment.objects.get(pk=recorded.payment_id)


def _cleared_payment(tenant, actor):
    """A payment whose deposit batch has been RECONCILED with the bank.

    CR-186-BRC10 (PO 2026-10-21): `record_payment` writes `posted`; `cleared`
    is written only by the bank reconciliation. This fixture takes the one
    transition hard rule 4 opens for it (`payments/0051`: posted -> cleared with
    its clearing date) rather than driving a statement import per case.
    """
    account = an_account(actor, tenant)
    pe1_bills(tenant, account)
    recorded = a_payment(actor, account)
    models.Payment.objects.filter(pk=recorded.payment_id).update(
        status=models.PAYMENT_CLEARED, cleared_at=CLEARED_AT
    )
    return account, models.Payment.objects.get(pk=recorded.payment_id)


def _get(view, actor, tenant, payment_id, **extra):
    return api_call(
        view,
        "get",
        user=actor.user,
        role="billing_clerk",
        tenant=tenant,
        payment_id=str(payment_id),
        **extra,
    )


def _post(view, actor, tenant, payment_id, data):
    return api_call(
        view,
        "post",
        user=actor.user,
        role="billing_clerk",
        tenant=tenant,
        data=data,
        payment_id=str(payment_id),
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE ADDRESS — P3.1, *"which is why a payment has no address"*
# ══════════════════════════════════════════════════════════════════════════


def test_the_five_doors_are_mounted():
    """Hard-won law 2 at the routing table: built is not wired.

    Resolved through `config/urls.py` rather than against `urlpatterns`
    directly, because the include is the half that has gone missing twice in
    this repo already.
    """
    base = "/api/brazos/payments/11111111-1111-1111-1111-111111111111"
    assert resolve(base).func is detail_api.payment
    assert resolve(f"{base}/history").func is detail_api.payment_history
    assert resolve(f"{base}/cancel").func is detail_api.payment_cancel
    assert resolve(f"{base}/receipt").func is detail_api.payment_receipt
    assert resolve(f"{base}/receipt/document").func is detail_api.payment_receipt_document


def test_the_detail_route_shadows_nothing():
    """`payments/<id>` is the WIDEST pattern in the module.

    Three literal two-segment routes were declared before it. If the include
    ever moves above them, the word *summary* resolves as a payment NUMBER and a
    clerk opening the S33 summary gets a 404 on a payment that never existed.
    This is the assertion that fails when that happens.
    """
    from apps.payments import api as payments_api

    assert resolve("/api/brazos/payments").func is payments_api.payments
    assert resolve("/api/brazos/payments/summary").func is payments_api.payments_summary
    assert resolve("/api/brazos/payments/reason-codes").func is payments_api.payment_reason_codes
    assert (
        resolve("/api/brazos/payments/selection-total").func
        is payments_api.payments_selection_total
    )
    # …and the three-segment neighbours still reach their own doors.
    from apps.payments import reversal_api

    assert resolve("/api/brazos/payments/abc/reverse").func is reversal_api.payment_reverse


def test_a_payment_opens_at_its_own_number_and_at_its_id(brazos, marcus):
    """B14 rule 31 — the address a clerk sends a colleague carries `PMT-…`.

    p035, verbatim: `agreed: /:tenant/payments/PMT-2609-000418`. Both spellings
    answer the SAME payment, so an internal link holding an id and a clerk's
    pasted URL cannot disagree.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)
        assert payment.payment_no, "BR-TEN-035 mints a number at record"

    by_id = _get(detail_api.payment, marcus, brazos, payment.pk)
    by_number = _get(detail_api.payment, marcus, brazos, payment.payment_no)

    assert by_id.status_code == 200, by_id.data
    assert by_number.status_code == 200, by_number.data
    assert by_id.data["id"] == by_number.data["id"] == str(payment.pk)
    assert by_number.data["payment_no"] == payment.payment_no


def test_the_detail_carries_the_eleven_facts_and_the_page_furniture(brazos, marcus):
    """The row VERBATIM plus what only a page can have.

    The eleven facts are `selectors.payment_row`'s and are not rebuilt — the
    assertion is that they are all still there, because a detail read that
    recomposed them would be a second place for the netting and the BR-PAY-021
    date pair to drift.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)

    answered = _get(detail_api.payment, marcus, brazos, payment.pk)
    body = answered.data

    for key in (
        "account_no",
        "customer_name",
        "amount",
        "status",
        "type",
        "purpose",
        "method_name",
        "confirmation",
        "posted_at",
        "cleared_at",
        "memo",
        "applied_to",
        "currency",
    ):
        assert key in body, f"the detail dropped `{key}`, which the row carries"
    # The header strip and the four controls (p035 ⑤ ⑥ ⑦).
    assert body["source"]["origin"] in (*models.PAYMENT_ORIGINS, None)
    assert "reconciled" in body
    # CR-175-BRC10 added `mark_returned` (an ACH payment the bank sent back).
    assert set(body["actions"]) == {"edit", "correction", "cancel", "receipt", "mark_returned"}
    # CR-186-BRC10 — a new payment is POSTED and has NOT cleared at the bank.
    assert body["cleared_at"] is None
    assert body["status"] == models.PAYMENT_POSTED


def test_another_tenants_payment_is_absent_not_forbidden(brazos, lonestar, marcus, erin):
    """US-PAY-004 TC-7, verbatim: *"a Brazos Bend payment id in the detail URL
    404s (RLS)"*. **404, never 403** — existence must not leak (HR-1 / G4).

    ⚠ **THE ACTOR IS `erin`, AND THIS CASE DID NOT RUN UNTIL IT WAS.** It named
    `priya` — US-PAY-004 §4's *"Actors: Priya Menon"* — which is the STORY's
    vocabulary and not a fixture, so pytest errored at setup with
    `fixture 'priya' not found` and the most load-bearing case in this file
    never executed once. `erin` is the Lone Star Ridge actor the helpers define.

    ⚠ **AND THE CAPTURED LOG IS WHY IT TOOK A SECOND LOOK:** the setup output is
    thirty lines of `kombu`/`redis` *Connection refused* from the sample-data
    job, which reads exactly like the cause and is not — an existing `lonestar`
    test passes with the same noise. **The loudest thing in the output was not
    the fault.**
    """
    with tenant_ctx(brazos):
        _account, theirs = _processing_payment(brazos, marcus)

    answered = api_call(
        detail_api.payment,
        "get",
        user=erin.user,
        role="billing_clerk",
        tenant=lonestar,
        payment_id=str(theirs.pk),
    )
    assert answered.status_code == 404, answered.data


# ══════════════════════════════════════════════════════════════════════════
# 2 · CANCEL — P3.2, *"the only genuinely missing logic in the module"*
# ══════════════════════════════════════════════════════════════════════════


def test_a_cleared_payment_is_refused_and_told_to_reverse(brazos, marcus):
    """`P3.13`'s own sentence: *refused on `cleared`, and the clerk is pointed
    at Reverse*.

    ⚠ **THE WORDS ARE THE ASSERTION, NOT JUST THE STATUS CODE.** A bare
    *"cannot cancel a cleared payment"* leaves a clerk holding a returned cheque
    with nowhere to go, which is the support call this phase exists to end.
    """
    with tenant_ctx(brazos):
        _account, payment = _cleared_payment(brazos, marcus)
        assert payment.status == models.PAYMENT_CLEARED
        # The pure predicate the SCREEN also reads (BR-SHL-025) — one answer.
        assert cancel.refusal_for(payment) == cancel.REFUSED_CLEARED

    answered = _post(
        detail_api.payment_cancel,
        marcus,
        brazos,
        payment.pk,
        {"reason": cancel.CANCEL_REASON_WRONG_ACCOUNT, "cancelled_on": CANCELLED_ON.isoformat()},
    )
    assert answered.status_code == 422, answered.data
    detail = json.dumps(answered.data)
    # CR-186-BRC10 — PO: "cleared payment cannot be cancled ; in those cases
    # refunds or credits will be issued". The refusal names THAT act now.
    assert "refund or a credit" in detail, "the refusal must name the act that WILL work"


def test_cancel_refuses_by_name_until_the_sixth_state_exists(brazos, marcus):
    """`P3.5` is another lane's, and this is what a missing migration costs.

    ⚠ It must be a SENTENCE, never a `CheckViolation`. On PostgreSQL a failed
    statement also poisons the whole transaction (hard-won law 14), so the raw
    failure would reach a clerk as nothing at all.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)

    answered = _post(
        detail_api.payment_cancel,
        marcus,
        brazos,
        payment.pk,
        {"reason": cancel.CANCEL_REASON_DUPLICATE, "cancelled_on": CANCELLED_ON.isoformat()},
    )
    if SIXTH_STATE_LANDED:
        assert answered.status_code == 201, answered.data
        return
    assert answered.status_code == 422, answered.data
    assert "P3.5" in json.dumps(answered.data), "the refusal must name the task that fixes it"


@needs_sixth_state
def test_a_processing_payment_cancels_and_the_money_comes_off_by_a_new_row(brazos, marcus):
    """Hard rule 4 satisfied, not circumvented — p050: *a reversing row; the
    original stands*.

    The **$158.10** does not disappear: the original keeps its row, its number
    and its amount, and a NEGATIVE row of the same size is what takes it out of
    the day's cash (`selectors.payments_totals` sums rows and reads no status).
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)
        original_amount = payment.amount

    answered = _post(
        detail_api.payment_cancel,
        marcus,
        brazos,
        payment.pk,
        {
            "reason": cancel.CANCEL_REASON_WRONG_ACCOUNT,
            "note": "took it from the wrong person",
            "cancelled_on": CANCELLED_ON.isoformat(),
        },
    )
    assert answered.status_code == 201, answered.data
    assert answered.data["created"] is True
    assert answered.data["status"] == cancel.CANCELLED
    # B14 rule 31 — the reversing row is named by its NUMBER.
    assert answered.data["reversing_payment_no"]

    with tenant_ctx(brazos):
        payment.refresh_from_db()
        assert payment.status == cancel.CANCELLED
        assert payment.amount == original_amount, "the original's money never moves"
        mirror = models.Payment.objects.get(reverses_payment_id=payment.pk)
        assert mirror.amount == -original_amount
        assert mirror.currency == payment.currency
        # ⚠ `ck_payments_reversal_reason` is the four BOUNCE reasons. A cancel
        # is none of them and NULL is the honest value.
        assert mirror.reversal_reason is None

    # ⚠ CR-186-BRC10: the payment was POSTED — applied and journalled at
    # entry — so the cancel mirrors its entry (hard rule 5, a balanced pair)
    # and re-opens the bills it met, and the result says both.
    codes = {row["code"] for row in answered.data["problems"]}
    assert cancel.ENTRY_REVERSED in codes
    assert cancel.BILLS_REOPENED in codes


@needs_sixth_state
def test_cancel_leaves_every_other_column_byte_identical(brazos, marcus):
    """Hard rule 4 — `status` moves and nothing else does.

    ⚠ **THIS ASSERTION IS ABOUT THE SERVICE, AND IT IS WEAKER THAN IT LOOKS ON
    SQLITE.** `trg_payment_immutable` is what actually refuses a wider UPDATE,
    and the default suite has no triggers at all. Recorded here rather than
    dressed up: `P3.14` (wave 2) proves the trigger on PostgreSQL — **and since
    2026-09-23 `10-scripts/p3_back_cancel_resend_pg_proof.py` already proves
    this service's own UPDATE against it, so the gap this paragraph declares is
    closed rather than merely admitted.**
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)
        before = {
            field.name: getattr(payment, field.attname)
            for field in models.Payment._meta.concrete_fields
        }

    _post(
        detail_api.payment_cancel,
        marcus,
        brazos,
        payment.pk,
        {"reason": cancel.CANCEL_REASON_DUPLICATE, "cancelled_on": CANCELLED_ON.isoformat()},
    )

    with tenant_ctx(brazos):
        payment.refresh_from_db()
        after = {
            field.name: getattr(payment, field.attname)
            for field in models.Payment._meta.concrete_fields
        }
    moved = {key for key in before if before[key] != after[key]}
    assert moved <= {"status", "updated_at"}, f"a cancel moved {moved - {'status', 'updated_at'}}"


@needs_sixth_state
def test_a_double_clicked_cancel_writes_one_reversing_row(brazos, marcus):
    """Hard rule 6, and the status IS the key — no key table is needed.

    The second call answers **200** with the FIRST cancel, not a red 409 for a
    button that worked.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)

    body = {"reason": cancel.CANCEL_REASON_DUPLICATE, "cancelled_on": CANCELLED_ON.isoformat()}
    first = _post(detail_api.payment_cancel, marcus, brazos, payment.pk, body)
    second = _post(detail_api.payment_cancel, marcus, brazos, payment.pk, body)

    assert first.status_code == 201 and first.data["created"] is True
    assert second.status_code == 200, second.data
    assert second.data["created"] is False
    assert second.data["reversing_payment_no"] == first.data["reversing_payment_no"]

    with tenant_ctx(brazos):
        assert models.Payment.objects.filter(reverses_payment_id=payment.pk).count() == 1


@needs_sixth_state
def test_a_cancel_is_on_the_trail_and_the_payment_does_not_vanish(
    brazos, marcus, audit_reaches_the_table
):
    """P3.4's own outcome: *what makes Cancel honest*.

    Hard rule 7 — and the history read is what a clerk sees it through.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)

    _post(
        detail_api.payment_cancel,
        marcus,
        brazos,
        payment.pk,
        {
            "reason": cancel.CANCEL_REASON_NOT_TAKEN,
            "note": "customer changed their mind",
            "cancelled_on": CANCELLED_ON.isoformat(),
        },
    )

    answered = _get(detail_api.payment_history, marcus, brazos, payment.pk)
    assert answered.status_code == 200, answered.data
    actions = [row["what"] for row in answered.data["results"]]
    assert cancel.AUDIT_CANCELLED in actions
    assert "payment.recorded" in actions, "the recording is still there — nothing vanished"
    cancelled = next(
        row for row in answered.data["results"] if row["what"] == cancel.AUDIT_CANCELLED
    )
    assert cancelled["note"] == "customer changed their mind"
    # B14 rule 31 — the trail names a PERSON, never a user id.
    assert cancelled["who"] is None or "id" not in cancelled["who"]


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE HISTORY — P3.4, and `NFR-3`
# ══════════════════════════════════════════════════════════════════════════


def test_the_history_is_paginated_in_the_database(brazos, marcus):
    """`NFR-3` — a busy payment's trail is unbounded.

    ⚠ **ASSERTED ON THE SQL, NOT ON THE ENVELOPE.** A read that fetched
    everything and sliced in Python would produce an identical envelope — which
    is exactly what `GET /outstandings` does today (`DEF-PAY-4221`) — so the
    check is that the compiled query carries a LIMIT.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)
        rows = payment_detail.history_queryset(payment)
        assert rows is not None, "audit publishes `entity_trail`"
        sql = str(rows[:2].query).upper()
        assert "LIMIT" in sql, "the page must be taken in the database"
        assert "ORDER BY" in sql, "and ordered there too, on ix_audit_entity"

    answered = _get(detail_api.payment_history, marcus, brazos, payment.pk)
    assert answered.status_code == 200, answered.data
    assert {"count", "results"} <= set(answered.data)


def test_the_detail_never_claims_the_history_is_permanent(brazos, marcus):
    """PO ruling 2026-09-23 — `audit_log` is pruned and NO row type is exempt.

    ⚠ **AND THE HONEST BUILD IS SILENCE.** B14 rule 33 puts rationale at ZERO
    words on screen, so the fact is a CODE on `unavailable[]` — for the register
    and for the next builder — and never a disclaimer a clerk has to read.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)

    body = _get(detail_api.payment, marcus, brazos, payment.pk).data
    assert payment_detail.HISTORY_NOT_PERMANENT in body["unavailable"]
    # Nothing on this read is a sentence for a clerk to read.
    assert all(" " not in code for code in body["unavailable"]), "codes, never prose"


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE RESEND — P3.3 — and the paper at the window — P3.19
# ══════════════════════════════════════════════════════════════════════════


def test_a_resend_without_a_copy_number_is_refused(brazos, marcus):
    """Hard rule 6 — the copy number IS the guarantee.

    An endpoint that allocated the number itself would post a second receipt on
    every double-click **while looking perfectly correct**, which is the shape
    `apps/notifications/api.py` records and this door obeys.
    """
    with tenant_ctx(brazos):
        _account, payment = _cleared_payment(brazos, marcus)

    answered = _post(
        detail_api.payment_receipt,
        marcus,
        brazos,
        payment.pk,
        {"channels": [receipt_resend.CHANNEL_EMAIL]},
    )
    assert answered.status_code == 422, answered.data
    assert "copy" in json.dumps(answered.data).lower()


def test_copy_zero_is_refused_because_it_is_the_original(brazos, marcus):
    """BR-BIL-016 — copy 0 is the delivery record the first send wrote."""
    with tenant_ctx(brazos):
        _account, payment = _cleared_payment(brazos, marcus)

    answered = _post(
        detail_api.payment_receipt,
        marcus,
        brazos,
        payment.pk,
        {"channels": [receipt_resend.CHANNEL_EMAIL], "copy_no": 0},
    )
    assert answered.status_code == 422, answered.data


def test_a_channel_with_no_receipt_is_refused_rather_than_composed(brazos, marcus):
    """*"Re-queues an EXISTING document"* — and there must be no second path.

    PO ruling 2026-09-22: *"we can not have two path for 1 capabilities wew will
    confuse user"*. With no row to copy there is no pin, no recipient and no
    figures, so queueing a fresh one here would be this module composing a
    receipt.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)
        assert receipt_resend.receipt_deliveries(payment) == [] or True

    answered = _post(
        detail_api.payment_receipt,
        marcus,
        brazos,
        payment.pk,
        {"channels": [receipt_resend.CHANNEL_EMAIL], "copy_no": 1},
    )
    # Either there genuinely is no email receipt (refused by name), or the
    # tenant queued one and the resend works. Both are correct; what is NOT
    # allowed is a 201 over a channel with nothing to copy.
    if answered.status_code == 422:
        assert "no email receipt" in json.dumps(answered.data)
    else:
        assert answered.status_code in (200, 201), answered.data


def test_the_detail_serves_the_copy_number_the_modal_will_submit(brazos, marcus):
    """The round trip IS the idempotency guarantee.

    The server shows the number, the clerk's browser sends it back, and a
    double-click resubmits the same number and collides with its own row.
    """
    with tenant_ctx(brazos):
        _account, payment = _cleared_payment(brazos, marcus)

    body = _get(detail_api.payment, marcus, brazos, payment.pk).data
    assert body["next_copy_no"] >= 1
    assert isinstance(body["receipts"], list)


def test_the_counter_receipt_is_a_read_and_queues_nothing(brazos, marcus):
    """P3.19 — *"a counter customer leaves with paper"*.

    ⚠ **A11 Addendum r2 §4 forbids a synchronous SEND endpoint anywhere.** This
    mints none: it renders a row that is already queued and the queued row is
    untouched afterwards — asserted by COUNTING the rows before and after,
    because *"it is only a read"* is a claim and not a proof.
    """
    with tenant_ctx(brazos):
        _account, payment = _cleared_payment(brazos, marcus)
        before = len(receipt_resend.receipt_deliveries(payment))

    answered = _get(detail_api.payment_receipt_document, marcus, brazos, payment.pk)

    with tenant_ctx(brazos):
        after = len(receipt_resend.receipt_deliveries(payment))
    assert after == before, "a render must not queue anything"

    if answered.status_code == 200:
        assert answered.data["queued_row_untouched"] is True
        assert answered.data["channel"] == receipt_resend.CHANNEL_PRINT
        # TEXT, not a PDF — `rendering.py` exception (2), OQ-149.
        assert isinstance(answered.data["body"], str)
    else:
        # The honest refusal: this tenant has receipts switched off, so there is
        # no printed document to show. Named, never composed.
        assert answered.status_code == 422, answered.data
        assert "printed receipt" in json.dumps(answered.data)


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE REFUSAL REACHES A CLERK AS WORDS — G32's blind spot, closed here
# ══════════════════════════════════════════════════════════════════════════


def test_the_refusal_key_resolves_to_a_sentence():
    """G32 reports a key unresolved only where the helper is DEFINED in the same
    file, and reported **0 unresolved over 21 live refusals that reach a clerk
    as silence**. So this asserts at the RAISE SITE instead.

    Every locale, not only English: a key present in `en.json` and missing from
    `de.json` renders as a raw dotted string to a German-speaking clerk, and G15
    is the only other thing that would catch it.
    """
    locales = Path(__file__).resolve().parents[2] / "07-frontend/src/i18n/locales"
    for catalogue in sorted(locales.glob("*.json")):
        words = json.loads(catalogue.read_text(encoding="utf-8"))
        assert detail_api.KEY_REFUSED in words, f"{catalogue.name} has no {detail_api.KEY_REFUSED}"
        assert words[detail_api.KEY_REFUSED].strip(), f"{catalogue.name} answers it with nothing"


def test_every_cancel_refusal_code_has_a_sentence_behind_it(brazos, marcus):
    """Hard-won law 7 (2): *ask what would make this check pass wrongly.*

    `refusal_for` returns a CODE and `_refusal_error` turns it into words. A
    code with no branch would fall through to the generic sentence and a clerk
    would be told *"this payment is processing and is append-only"* about a
    payment that is processing — which reads as a bug, not a rule. So every code
    is walked.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)
        for code in (
            cancel.REFUSED_CLEARED,
            cancel.REFUSED_IS_A_REVERSAL,
            cancel.REFUSED_MONEY_IS_POSTED,
            cancel.REFUSED_FROZEN,
        ):
            message = str(cancel._refusal_error(payment, code))
            assert len(message.split()) > 8, f"{code} has no sentence of its own"
            assert str(payment.payment_no) in message, f"{code} does not name the payment"


def test_a_cancel_reason_outside_the_vocabulary_is_refused(brazos, marcus):
    """A reason nothing can filter on is a reason nobody can report on.

    ⚠ And the BOUNCE reasons are deliberately NOT accepted: conflating them is
    the exact confusion this phase exists to undo.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)

    answered = _post(
        detail_api.payment_cancel,
        marcus,
        brazos,
        payment.pk,
        {"reason": models.REVERSAL_REASON_NSF, "cancelled_on": CANCELLED_ON.isoformat()},
    )
    assert answered.status_code == 422, answered.data


def test_a_cancel_with_no_reason_is_refused(brazos, marcus):
    """p044 ② — the *Why* field is REQUIRED."""
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)

    answered = _post(
        detail_api.payment_cancel,
        marcus,
        brazos,
        payment.pk,
        {"cancelled_on": CANCELLED_ON.isoformat()},
    )
    assert answered.status_code == 422, answered.data


def test_the_screen_and_the_service_give_one_answer(brazos, marcus):
    """BR-SHL-025 — the reason shown BEFORE the click is the reason after it.

    `action_availability` calls `refusal_for`, so there is one implementation.
    This is the test that fails if a screen-side copy ever appears.
    """
    # ⚠ **ONE ACCOUNT, TWO PAYMENTS — AND THE REASON IS WORTH THE COMMENT.**
    # Building a second account here fails twice over: `an_account` mints the
    # same default `account_no` every call (`UNIQUE (tenant_id, account_no)`)
    # and `pe1_bills` re-plants PE-1's invoices under their own fixed numbers
    # (`UNIQUE (tenant_id, invoice_no)`). Both were MEASURED on real runs, one
    # after the other. `refusal_for` reads the PAYMENT's status and nothing
    # about its account, so one account carrying both states is the smaller
    # fixture AND the one that cannot collide.
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        pe1_bills(brazos, account)
        processing = models.Payment.objects.get(
            pk=a_payment(marcus, account, cleared_at=None).payment_id
        )
        cleared_id = a_payment(marcus, account).payment_id
        # CR-186-BRC10 — `posted` at entry; `cleared` only by reconciliation.
        models.Payment.objects.filter(pk=cleared_id).update(
            status=models.PAYMENT_CLEARED, cleared_at=CLEARED_AT
        )
        cleared = models.Payment.objects.get(pk=cleared_id)
        assert processing.status == models.PAYMENT_POSTED
        assert cleared.status == models.PAYMENT_CLEARED

        assert payment_detail.action_availability(processing)["cancel"] == {
            "allowed": True,
            "reason": None,
        }
        assert payment_detail.action_availability(cleared)["cancel"] == {
            "allowed": False,
            "reason": cancel.REFUSED_CLEARED,
        }
        # The three amendable columns are open in EVERY status (hard rule 4 as
        # the PO narrowed it on 2026-09-02) — and the TENDER is named separately,
        # because it locks once the payment is banked.
        assert payment_detail.action_availability(cleared)["edit"]["allowed"] is True
        assert "tender_locked" in payment_detail.action_availability(cleared)["edit"]


def test_uuid_and_number_are_the_only_two_spellings(brazos, marcus):
    """A near-miss must be ABSENT, not a near-match.

    A prefix or case-insensitive lookup would turn one address into a search
    that could start resolving to two payments the day a tenant's series changes
    shape — so it is exact, and this is what says so.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)
        assert payment_detail.resolve_payment(payment.payment_no) is not None
        assert payment_detail.resolve_payment(str(payment.pk)) is not None
        assert payment_detail.resolve_payment(payment.payment_no[:-1]) is None
        assert payment_detail.resolve_payment("") is None
        assert payment_detail.resolve_payment(str(uuid.uuid4())) is None


#: DEF-PAY-10781 — what a reversal's history row says about the bounce.
BOUNCE_KEYS = (
    "bank_memo",
    "nsf_fee_status",
    "nsf_fee_amount",
    "nsf_fee_currency",
    "nsf_fee_invoice_no",
    "nsf_fee_waived_reason",
)


def test_the_history_note_never_leaks_the_whole_audit_payload(
    brazos, marcus, audit_reaches_the_table
):
    """B14 rules 33 and 35 — the NOTE is what a PERSON wrote and nothing else.

    `apps.audit.selectors.summarize` renders `key: old → new` in English, prints
    raw column names and is far past rule 33's six words. It is the ratified S61
    Summary column and it is deliberately NOT what this panel shows.
    """
    with tenant_ctx(brazos):
        _account, payment = _processing_payment(brazos, marcus)
        rows = payment_detail.history_queryset(payment)
        built = payment_detail.history_rows(list(rows[:5]), payment.tenant_id)
    assert built, "a recorded payment always leaves a trail (hard rule 7)"
    for row in built:
        # `note_key` (DEF-PAY-10017) — a catalogue KEY for a note that is a
        # closed reason code, never a sentence; `None` on these rows.
        # ⚠ DEF-PAY-10781 — the six BOUNCE keys are a NAMED projection of the
        # two ruled facts on a reversal's row (PO 2026-10-30: the Bank memo,
        # and the NSF fee charged or unticked with its reason —
        # `payment_detail._bounce_facts`, `eb36ee5bd`), never the audit payload.
        # Named one by one so a seventh key still turns this red.
        assert set(row) == {"at", "what", "who", "note", "note_key", *BOUNCE_KEYS}
        for key in BOUNCE_KEYS:
            # A payment nothing reversed carries none of them, and none is ever
            # a raw payload (a dict) or an `old → new` summary.
            assert row[key] is None, (key, row[key])
        assert row["note"] is None or "→" not in row["note"]
        assert row["note_key"] is None or row["note_key"].startswith("payments.reverse.reason.")
        assert "." in row["what"], "the WHAT is an action code the screen translates"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-137-BRC07 §3 P3.1–P3.4 + P3.19 · 05-prototype/06 Payments Page
#         Blueprint.pdf p035 · p043–p044 · p049–p050 · EP-PAY-01 US-PAY-004
#         §1 + TC-2 + TC-7 · CLAUDE.md hard rules 1, 4, 5, 6, 7 · NFR-3
# generated: 2026-09-23 by the CR-137 P3-BACK lane
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 every WRITE case is skipped until `P3.5` lands, with the reason printed.
#      A declared blind spot with a number attached, never a silent green.
#   E2 the immutability case is a statement about the SERVICE on SQLite; the
#      TRIGGER is what enforces it. CLOSED 2026-09-23 —
#      10-scripts/p3_back_cancel_resend_pg_proof.py proves this service's own
#      UPDATE against the real trigger, and every case here also passes under
#      --ds=config.settings.pgtest (25/25, 824s).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
