# ── Trace ──────────────────────────────────────────────
# Change:  CR-136-BRC07 — phase 2, the counter. `P2.13`, the test the drawing
#          commits and never gave a build task to, plus the build behind it
#          (`DEF-PAY-6226`).
# Rules:   CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (four decimals
#          stored) · hard rule 4 (`payments` is append-only; both stamps are
#          written at INSERT or never, and `payments/0014`'s allow list does
#          NOT move) · hard rule 6 (the nightly cut is idempotent) · hard
#          rule 7 (`audit_log`) · BR-SHL-025 · BR-PAY-025 · BR-PAY-1186 ·
#          hard-won law 2 (built is not wired) · hard-won law 7 habit 2 (ask
#          what would make this check pass wrongly)
# Ruling:  PO 2026-09-23 §3.4, verbatim: *"(a) Refuse it. \"Start your counter
#          first.\" One press, then take the money. It is the only option
#          where every cash dollar belongs to somebody"*.
# Tests:   this file.
# ───────────────────────────────────────────────────────
"""*"The id attaches when TAKEN. Not at close."* — `P2.13`, and it did not.

WHAT THIS FILE IS FOR, IN ONE PARAGRAPH
----------------------------------------
`payments.counter_session_id` shipped with `payments/0035`: the column, its
partial index, four readers and `P2.23`'s endpoint refusal. **Nothing wrote
it** (`DEF-PAY-6226`). A clerk could open a till at 08:55, take seventeen
payments and close it at 17:30 against an **empty drawer**, because every
dollar banked under the day's system till — the one phase 0 built for ACH,
card, wire and lockbox and which is openly nobody's. Every check in this repo
passed over it, because each half was correct on its own and **no test
anywhere asked whether anything SET the column**. That is hard-won law 2 on
the money path, and it is the exact outcome §3.4 exists to prevent.

⚠ **THE FALSE PASS THIS FILE IS BUILT AGAINST, NAMED SO IT CANNOT HAPPEN
QUIETLY** (hard-won law 7, habit 2). *Stamp a till id and assert it is there*
passes just as happily when the tender filter is inverted, missing, or
silently swallowing its own refusal — the stamp is there either way. So the
negative is asserted in this same file and at the same strength: **an ACH
recorded while the same clerk's till is open carries NO till and NO batch**,
and a till offered for an electronic tender is refused BY NAME rather than
ignored.

⚠ **WHAT IS NOT HERE.** The RLS false zero, the race and the aborted
transaction are `10-scripts/cr136_p2_counters_postgres_proof.py`: SQLite has
no row-level security, serialises its writers and has no aborted-transaction
state, so all three would pass here by vacuum (hard-won law 14).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.payments import counters, reconciliation, services
from apps.payments import api as payments_api
from apps.payments import bankrec_models as bankrec
from apps.payments import models as payment_models
from apps.payments.counter_session_models import CounterSession
from apps.payments.exceptions import PaymentRuleError
from apps.tenancy import published_content_models as content_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import audit_rows, tenant_ctx  # noqa: F401 — fixtures
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def centre(brazos):
    """A walk-in counter for the till to be at."""
    with tenant_ctx(brazos):
        return content_models.ServiceCentre.objects.create(
            tenant=brazos,
            slug="till-window",
            name="Main office",
            address="101 Bend Road, Brazos Bend, TX 77422",
        )


def _open(actor, centre, *, float_amount="200.0000"):
    return counters.open_counter(
        actor,
        service_centre_id=centre.pk,
        opening_float=Decimal(float_amount),
        opened_at=timezone.now(),
    )


def _take(actor, tenant, *, amount, method_code, till=None, cleared=True):
    """A payment through the REAL write path — no direct stamping anywhere.

    This is the difference from `test_cr136_p2_counters._take`, which reaches
    in and `.update()`s `deposit_batch_id` because when it was written that
    was the only path there was. The whole point of this file is that there
    now is one.
    """
    account = an_account(actor, tenant, account_no=f"A-{uuid.uuid4().hex[:6]}")
    recorded = services.record_payment(
        actor,
        account_id=account.pk,
        amount=Decimal(amount),
        posted_at=timezone.now(),
        cleared_at=timezone.now() if cleared else None,
        method_code=method_code,
        idempotency_reference=uuid.uuid4(),
        counter_session_id=None if till is None else till.pk,
    )
    return payment_models.Payment.objects.get(pk=recorded.payment_id)


# ═══════════════════════════════════════════════════════════════════════════
#  THE CASE THE DRAWING COMMITS — the id attaches WHEN TAKEN
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_13_a_cash_payment_names_its_till_AND_its_batch(brazos, dana, centre):
    """The drawer is not empty. Both stamps, before anything is closed.

    **Asserted while the till is still OPEN**, which is the half of `P2.13`
    that carries its whole point: an earlier draft stamped at close, and the
    drawing kept this test precisely to stop it drifting back.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        payment = _take(dana, brazos, amount="120.0000", method_code="cash", till=opened.session)

        assert opened.session.closed_at is None, "stamped while the till is OPEN, not at close"
        assert payment.counter_session_id == opened.session.pk
        # …and the money is in the till's OWN cash batch, which `open_counter`
        # opened — not a batch this payment invented and not the system till's.
        assert payment.deposit_batch_id == opened.batch.pk
        assert opened.batch.session_id == opened.session.pk


def test_p2_13_the_till_finds_its_own_money(brazos, dana, centre):
    """`session_payments_q`'s two facts, both true of one row.

    The running split is what `3·2` renders and what the Close screen counts
    against. Before `DEF-PAY-6226` it read the float and nothing else.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        _take(dana, brazos, amount="120.0000", method_code="cash", till=opened.session)
        _take(dana, brazos, amount="80.5000", method_code="cash", till=opened.session)
        split = counters.running_split(opened.session)
        # $200.00 float + $120.00 + $80.50 = $400.50 expected in the drawer.
        assert Decimal(split["countable_expected"]) == Decimal("400.5000")


def test_p2_13_a_cheque_opens_the_tills_SECOND_batch(brazos, dana, centre):
    """One batch per till per tender (`payments/0033`), opened by the first
    payment of that tender — `OQ-PAY-12599`'s option (c), built.

    Dana's shift taking cash and cheques is **one till and two batches**,
    which is what the bank sees: it credits cash and cheques separately and
    they clear on different days.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        cash = _take(dana, brazos, amount="600.0000", method_code="cash", till=opened.session)
        cheque = _take(
            dana, brazos, amount="640.0000", method_code="check", till=opened.session,
            cleared=False,
        )
        # ⚠ SUPERSEDED 2026-10-21 (CR-186-BRC10). PO: "this is one batch only -
        # it will ahve 1 batch ID not 2". One till, ONE batch, every tender in
        # it — the case keeps its name and now asserts the ruling.
        assert cash.deposit_batch_id == cheque.deposit_batch_id == opened.batch.pk
        batches = bankrec.DepositBatch.objects.filter(session_id=opened.session.pk)
        assert batches.count() == 1, "one till, two tenders, ONE batch"
        assert batches.get().method_id is None
        # Every payment is POSTED at entry (PO 2026-10-21), the cheque included.
        assert cheque.status == payment_models.PAYMENT_POSTED
        assert cheque.counter_session_id == opened.session.pk

        # A second cheque joins the batch the first one opened — it does not
        # open a third (hard rule 6's shape, applied to a batch).
        again = _take(
            dana, brazos, amount="12.0000", method_code="check", till=opened.session,
            cleared=False,
        )
        assert again.deposit_batch_id == cheque.deposit_batch_id
        assert bankrec.DepositBatch.objects.filter(session_id=opened.session.pk).count() == 1


# ═══════════════════════════════════════════════════════════════════════════
#  THE NEGATIVE — what makes the positive above mean anything (law 7 habit 2)
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("tender", ["ach", "card", "wire", "lockbox"])
def test_p2_13_an_ELECTRONIC_payment_is_not_stamped_even_with_a_till_open(
    brazos, dana, centre, tender
):
    """**The check that stops the check above passing wrongly.**

    The same clerk, the same open till, the same second — and an ACH, a card,
    a wire and a lockbox row carry NO till and NO batch. A card swiped at a
    window looks like counter money and is not countable money: the Close
    screen counts what is in a drawer, and a card total typed back at the
    system's own figure makes the reconciliation worthless.

    Recorded exactly as the endpoint does it — `assert_till_open_for_tender`
    answers `None` for these four, so `None` is what travels.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        till = counters.assert_till_open_for_tender(dana, tender)
        assert till is None, "the rule itself must answer None for an electronic tender"
        payment = _take(dana, brazos, amount="500.0000", method_code=tender, till=till)

        assert payment.counter_session_id is None
        # CR-186-BRC10: it IS stamped at posting now — into the office
        # channel's day batch, never into the clerk's till.
        batch = bankrec.DepositBatch.objects.get(pk=payment.deposit_batch_id)
        assert batch.session_id != opened.session.pk
        assert batch.session.system_day is not None and batch.session.channel == "office"
        assert opened.session.closed_at is None, "and the till really was open throughout"


@pytest.mark.parametrize("tender", ["ach", "card", "wire", "lockbox"])
def test_p2_13_the_service_REFUSES_a_till_for_an_electronic_tender(
    brazos, dana, centre, tender
):
    """Two layers, and neither alone decides it.

    A second caller that resolved a till by itself and handed it to
    `record_payment` would otherwise put a card swipe in somebody's drawer.
    The refusal is at the WRITE, by name, rather than trusted to the one door
    that gets it right today.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        with pytest.raises(PaymentRuleError) as refusal:
            _take(dana, brazos, amount="500.0000", method_code=tender, till=opened.session)
    assert "cannot be taken into a counter till" in str(refusal.value)
    # …and it wrote NOTHING: a refusal that leaves an orphan payment behind
    # would be worse than no refusal.
    with tenant_ctx(brazos):
        assert not payment_models.Payment.objects.filter(method__code=tender).exists()


def test_p2_13_a_CLOSED_till_takes_no_more_money(brazos, dana, centre):
    """The drawer has been counted and its deposit footed.

    A payment arriving afterwards would put a signed-off count permanently
    out — and `close_counter` has already recomputed the batch totals.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        counters.close_counter(
            dana,
            session_id=opened.session.pk,
            counted_totals={"cash": "200.0000"},
            closed_at=timezone.now(),
            note=None,
        )
        with pytest.raises(PaymentRuleError) as refusal:
            _take(dana, brazos, amount="10.0000", method_code="cash", till=opened.session)
    assert "already closed" in str(refusal.value)


def test_p2_13_a_till_from_ANOTHER_tenant_resolves_to_nothing(brazos, lonestar, dana, erin):
    """Hard rule 1, and it needs its own case here.

    `counter_session_id` carries **no referential integrity** — `payments/0035`
    states that rather than leaving it to be found — so this service is the
    only guard there is. A foreign till must be refused by NAME; resolving it
    would put Brazos Bend's cash in Lone Star's drawer.
    """
    with tenant_ctx(lonestar):
        # A person's till needs a CENTRE as well as an owner:
        # `ck_counter_sessions_system_is_nobodys` runs both ways, and a till
        # with an owner and no service centre is refused by name.
        their_centre = content_models.ServiceCentre.objects.create(
            tenant=lonestar,
            slug="lonestar-window",
            name="Lone Star counter",
            address="9 Water Street, Lone Star, TX 75668",
        )
        foreign = CounterSession.objects.create(
            tenant=lonestar,
            owner_id=erin.id,
            service_centre=their_centre,
            opening_float=Decimal("0.0000"),
            opened_at=timezone.now(),
        )
    with tenant_ctx(brazos):
        with pytest.raises(PaymentRuleError) as refusal:
            _take(dana, brazos, amount="10.0000", method_code="cash", till=foreign)
    assert "does not exist for this utility" in str(refusal.value)


# ═══════════════════════════════════════════════════════════════════════════
#  HARD-WON LAW 2 — the ENDPOINT actually passes it
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_13_the_RECORD_ENDPOINT_passes_the_till_it_resolved(brazos, dana, centre):
    """**The one line the defect was.**

    `api.account_payments` already called `assert_till_open_for_tender` and
    **threw its return value away**, so `P2.23` read DONE, the refusal worked,
    and no payment ever named a till. A service that accepts a till nobody
    hands it is dead UI's back-end twin.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        account = an_account(dana, brazos, account_no=f"A-{uuid.uuid4().hex[:6]}")
    # ⚠ **`is_authenticated` IS REQUIRED AND THE ACTOR FIXTURE HAS NO SUCH
    # ATTRIBUTE.** `core.permissions._role_of` returns None without it — the
    # request is then 403 AUTH-002 before the view is reached, which reads
    # exactly like a permission bug in the endpoint. The `id` must still be
    # DANA's, because `api._actor` hands `request.user` straight to
    # `counters.open_counter_for`, which is how the till is found at all.
    signed_in = SimpleNamespace(id=dana.id, pk=dana.id, is_authenticated=True)
    response = api_call(
        payments_api.account_payments,
        "post",
        user=signed_in,
        role="system_admin",
        tenant=brazos,
        data={
            "amount": "75.0000",
            "posted_at": "2026-09-23",
            "cleared_at": "2026-09-23",
            "method": "cash",
            "idempotency_key": str(uuid.uuid4()),
        },
        account_id=str(account.pk),
    )
    assert response.status_code in (200, 201), getattr(response, "data", response)
    with tenant_ctx(brazos):
        payment = payment_models.Payment.objects.get(pk=response.data["id"])
        assert payment.counter_session_id == opened.session.pk
        assert payment.deposit_batch_id == opened.batch.pk


def test_p2_13_hard_rule_7_names_the_till_on_the_trail(brazos, dana, centre, audit_rows):
    """Whose drawer, and which deposit — neither reconstructable later.

    The till is write-once and the batch is sealed at close, so if the money
    action does not carry them at the moment the money is taken, nothing ever
    can.
    """
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        payment = _take(dana, brazos, amount="45.0000", method_code="cash", till=opened.session)
    recorded = [
        row
        for row in audit_rows
        if row.get("entity_id") == str(payment.pk) and "recorded" in str(row.get("action"))
    ]
    assert recorded, f"no `payment recorded` audit row among {[r.get('action') for r in audit_rows]}"
    after = recorded[-1].get("after") or {}
    assert after.get("counter_session_id") == str(opened.session.pk)
    assert after.get("deposit_batch_id") == str(opened.batch.pk)


# ═══════════════════════════════════════════════════════════════════════════
#  WHAT THE NIGHTLY CUT DOES WITH IT — hard rule 6
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_13_the_nightly_cut_never_sees_a_counter_payment(brazos, dana, centre):
    """Filtered out before the loop, not skipped-and-reported.

    `cut_deposit_batches` selects `deposit_batch_id IS NULL`, and a counter
    payment carries its batch from the moment it was taken. So it is neither
    re-grouped nor double-counted, it is not in `skipped` either, and the
    till's batch is untouched. **A second cut on the same day cuts nothing**
    — hard rule 6, still true after this change.
    """
    today = timezone.now().date()
    with tenant_ctx(brazos):
        opened = _open(dana, centre)
        payment = _take(dana, brazos, amount="120.0000", method_code="cash", till=opened.session)
        batch_before = payment.deposit_batch_id

        first = reconciliation.cut_deposit_batches(
            actor=dana, day=today, occurred_at=timezone.now()
        )
        assert str(payment.pk) not in [row["payment_id"] for row in first.skipped]
        after = payment_models.Payment.objects.get(pk=payment.pk)
        assert after.deposit_batch_id == batch_before, "the cut did not re-group a till's money"

        second = reconciliation.cut_deposit_batches(
            actor=dana, day=today, occurred_at=timezone.now()
        )
        assert second.payments_batched == 0, "hard rule 6 — a second cut cuts nothing"


def test_p2_13_the_cut_groups_by_TILL_and_tender_not_tender_alone(brazos, dana, marcus, centre):
    """**Two clerks' cash is two deposits, and this is the case that proves
    the group key had to move with `_session_for`.**

    `cut_deposit_batches` grouped on the METHOD alone and then asked
    `_session_for(payments[0])` — correct only while every payment answered
    the same till, which was true precisely because the answer was always the
    system one. With a payment naming its own till, **Dana's cash and
    Marcus's would have been stamped into whichever till sorted first**: one
    clerk held to the other's drawer, with every check in this repo green.

    The rows here carry a till and NO batch, which is the road
    `_session_for`'s branch exists for — the two hand-recording doors
    `api.py` names as not calling the till guard, and every row
    `payments/0035` left NULL.
    """
    today = timezone.now().date()
    with tenant_ctx(brazos):
        dana_till = _open(dana, centre).session
        marcus_till = _open(marcus, centre).session
        made = []
        for actor, till, amount in (
            (dana, dana_till, "600.0000"),
            (marcus, marcus_till, "880.0000"),
        ):
            payment = _take(actor, brazos, amount=amount, method_code="cash", till=till)
            # Take the batch back off, so the row reaches the cut the way a
            # payment that took another road would.
            payment_models.Payment.objects.filter(pk=payment.pk).update(deposit_batch_id=None)
            made.append(payment.pk)

        reconciliation.cut_deposit_batches(actor=dana, day=today, occurred_at=timezone.now())
        rows = {p.pk: p for p in payment_models.Payment.objects.filter(pk__in=made)}
        dana_batch = bankrec.DepositBatch.objects.get(pk=rows[made[0]].deposit_batch_id)
        marcus_batch = bankrec.DepositBatch.objects.get(pk=rows[made[1]].deposit_batch_id)

    assert dana_batch.pk != marcus_batch.pk, "one cash batch for two tills is the defect"
    assert dana_batch.session_id == dana_till.pk
    assert marcus_batch.session_id == marcus_till.pk


def test_p2_13_session_for_still_answers_the_system_till_for_everything_else(
    brazos, dana
):
    """The fallback is the ruling's own second half, not a stand-in.

    PO 2026-09-22: *"we have to make process uniform for all hence we should
    geneate system generated till"*. A utility taking $14,280 of ACH on a
    Tuesday has no clerk, no drawer and no till.
    """
    today = timezone.now().date()
    with tenant_ctx(brazos):
        payment = _take(dana, brazos, amount="14280.0000", method_code="ach")
        assert payment.counter_session_id is None
        reconciliation.cut_deposit_batches(actor=dana, day=today, occurred_at=timezone.now())
        banked = payment_models.Payment.objects.get(pk=payment.pk)
        assert banked.deposit_batch_id is not None
        batch = bankrec.DepositBatch.objects.get(pk=banked.deposit_batch_id)
        assert batch.session.system_day == today, "an ACH banks under the day's system till"
        assert batch.session.owner_id is None, "which is openly nobody's"
