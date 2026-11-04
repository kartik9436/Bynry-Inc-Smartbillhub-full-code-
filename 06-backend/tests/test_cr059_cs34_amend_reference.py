# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-34 · task 41 — the named amend endpoint, and CS-34's own
#           proof list: *"Amendment permitted and audited; every money field
#           refused by name; the tender refused once batched; and a bank line
#           proved to match after a reference is corrected."*
# Story:    US-PAY-004 · US-PAY-020/023   Screens: S35 · S21
# Rules:    CLAUDE.md hard rule 4 / BR-PAY-002 (append-only) · hard rule 7 ·
#           hard rule 1 · BR-PAY-025 (batches group by day × tender) ·
#           BR-PAY-004 (a reconciled batch is locked)
# Ruling:   OQ-1322 CLOSED 2026-09-02 (option a) — PO verbatim *"(a) Allow those
#           fields to change"*. CLAUDE.md hard rule 4 is NARROWED for
#           `confirmation`, `memo` and `method_id` and for nothing else.
# Question: OQ-1340 — is a correction's audit row exempt from retention pruning?
#           NOT answered; the response says so and this file asserts that it does.
# Tests:    this file
# Impacts:  apps/payments/amendments.py · apps/payments/amendments_api.py ·
#           apps/payments/migrations/0014_cr059_cs34_amendable_reference.py ·
#           config/urls.py
# ───────────────────────────────────────────────────────
"""CS-34 — what a correction may touch, and the three columns it may move.

**ALL FOUR OF CS-34'S PROOFS ARE LIVE HERE SINCE 2026-09-02**, when the Product
Owner closed `OQ-1322` with *"(a) Allow those fields to change"*:

  * *"every money field refused by name"* — a body carrying `amount`,
    `account_id`, `posted_at`, `cleared_at` or `allocations` is refused with that
    field NAMED, before anything else runs;
  * *"the tender refused once batched"* — with the batch named and its locked
    state distinguished from its open one, because those need different actions;
  * *"amendment permitted and audited"* — the write, in one transaction with its
    audit row;
  * *"a bank line matches after a reference is corrected"* — the corrected value
    is what the next reader sees.

**WHAT WAS NARROWED.** CLAUDE.md hard rule 4 said a payment accepts *no UPDATE
and no DELETE, ever*, enforced by the `payments_payment_immutable` trigger. The
PO's ruling narrows it for **`confirmation`, `memo` and `method_id` and nothing
else**; `payments/0014` is the only place the database's allow list moves, and
`CLAUDE.md` carries the amendment.

⚠ **THIS SUITE CANNOT PROVE ANY OF THAT, AND SAYS SO RATHER THAN IMPLYING IT.**
The triggers exist on PostgreSQL only and `config/settings/test.py` hardcodes
in-memory SQLite, so on the default tier every UPDATE succeeds whether the
migration ran or not — which is precisely why the naive one-line version would
have shipped green and raised on the first real cheque (CLAUDE.md law 14).
`test_cs34__sqlite_proves_nothing_about_the_trigger` states that limit, and the
`@requires_postgres` block below runs the real statements against a live cluster
and SKIPS off PostgreSQL rather than passing vacuously.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import connection, transaction

from apps.payments import amendments, amendments_api, models, services
from apps.payments.exceptions import PaymentRuleError

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)
CHEQUE = Decimal("292.87")

#: CS-34's own example — a mistyped cheque number. The RIGHT one and the WRONG
#: one, so a refusal message can be read for whether it names the field or the
#: value.
WRONG_REF = "10241"
RIGHT_REF = "10214"


def call(view, tenant, **kwargs):
    """One correction as the clerk who recorded the payment (A4 · billing_clerk)."""
    return api_call(view, "post", user=FakeUser(), role="billing_clerk", tenant=tenant, **kwargs)


def a_payment(actor, tenant, *, reference=WRONG_REF):
    """One cleared cheque, RECORDED with its (mistyped) number.

    ⚠ **THE NUMBER IS PASSED AT CREATION AND NOT PLANTED WITH AN `UPDATE`, AND
    THAT IS STILL DELIBERATE AFTER THE RULING.** An earlier draft planted it
    afterwards and PostgreSQL refused:

        django.db.utils.ProgrammingError: BR-PAY-002 / hard rule 4: payment
          PY-260808-0001 is cleared and is append-only — no column may change …
          Changed: confirmation

    `payments/0014` now permits that statement, so the old form would pass — but
    a fixture that reaches the same state through the door under test cannot
    tell a working correction from a broken one. The wrong number arrives the
    way a clerk's wrong number arrives: typed when the payment is recorded.
    """
    account = an_account_of(actor, tenant)
    an_issued_bill(
        tenant,
        account,
        number=f"BL-2608-{uuid.uuid4().hex[:6]}",
        total=CHEQUE,
        issued_on=date(2026, 8, 1),
    )
    recorded = services.record_payment(
        actor,
        account_id=account.pk,
        amount=CHEQUE,
        method_code="check",
        confirmation=reference,
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        idempotency_reference=uuid.uuid4(),
    )
    return models.Payment.objects.get(pk=recorded.payment_id)


def a_banked_batch(actor, tenant, payment, *, status):
    """The deposit batch this cheque was banked in — UNDER A TILL, as P0.6 requires.

    ⚠ **THIS FIXTURE MADE A BATCH WITH NO COUNTER SESSION UNTIL 2026-09-24
    (`DEF-PAY-6399`), AND POSTGRESQL HAS REFUSED THAT SINCE `5831a9cd5`.**
    `payments/0033`'s `trg_deposit_batch_needs_session` (CR-135-BRC07 `P0.6`,
    BR-PAY-025 as amended 2026-09-22: *a batch is one till and one tender*)
    answers the bare `DepositBatch.objects.create` with *"deposit batch
    DEP-260808-CHK cannot be created without a counter session"*. SQLite has
    no trigger, so the four cases that bank a payment stayed green on the
    default tier and red on the one database where CS-34's banked-tender rule
    can actually be proved — `test_cs34__the_trigger_refuses_the_tender_once_
    the_payment_is_banked` among them.

    So the cheque is banked the way every batch now is: Dana opens a till at a
    counter and the batch names it. The code stays `DEP-260808-CHK` — the
    composed shape an older batch carries — because the refusal is asserted to
    NAME the batch a clerk reads, and a code is a code whichever way it was
    minted.
    """
    from apps.payments import bankrec_models as bankrec
    from apps.payments.counter_session_models import CounterSession
    from apps.tenancy import published_content_models as places

    centre = places.ServiceCentre.objects.create(
        tenant=tenant,
        slug=f"main-{uuid.uuid4().hex[:6]}",
        name="Main office",
        address="101 Bend Road",
    )
    till = CounterSession.objects.create(
        tenant=tenant,
        owner=actor.user,
        service_centre=centre,
        opening_float=Decimal("200.0000"),
        opened_at=POSTED_AT,
    )
    batch = bankrec.DepositBatch.objects.create(
        tenant=tenant,
        code="DEP-260808-CHK",
        session=till,
        method=payment.method,
        # `deposited_on` is the drawer day, never the day the bank credits it
        # (BR-PAY-025 / RQ-5).
        deposited_on=date(2026, 8, 8),
        status=status,
        recorded_total=CHEQUE,
    )
    models.Payment.objects.filter(pk=payment.pk).update(deposit_batch_id=batch.pk)
    payment.refresh_from_db()
    return batch


# ══ 1 · EVERY MONEY FIELD REFUSED BY NAME ═══════════════════════════════════


@pytest.mark.parametrize(
    "field, value",
    [
        ("amount", "300.00"),
        ("account_id", "019ff23d-13ee-7aba-a280-58058e492cb9"),
        ("posted_at", "2026-08-09T10:30:00Z"),
        ("cleared_at", "2026-08-09T10:30:00Z"),
        ("allocations", []),
    ],
)
def test_cs34__every_money_field_is_refused_by_name(brazos, dana, field, value):
    """CS-34's first proof, and it is the half of this spec that is finished.

    *"The amount, the account, both dates and the allocations may never be
    [amended]."* Refused BY NAME — the refusal says which field — and refused
    FIRST, before the payment is even looked up, so a body carrying an amount is
    told about the amount rather than about anything else.

    The five are parametrised rather than asserted in one body because a loop
    that stopped at the first offender would prove one field and report five.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        with pytest.raises(PaymentRuleError) as refusal:
            amendments.amend_reference(
                dana,
                payment_id=payment.pk,
                note="typo on the cheque",
                reference=RIGHT_REF,
                body={"reference": RIGHT_REF, "note": "typo", field: value},
            )
        assert field in str(refusal.value)
        assert "hard rule 4" in str(refusal.value)


def test_cs34__an_unknown_field_is_refused_rather_than_ignored(brazos, dana):
    """The spec's own reason for a named endpoint, made checkable.

    *"A route that accepts a partial body invites the next field to be added to
    it."* A field this endpoint does not know is a caller mistake or a rename,
    and silently dropping one is how a clerk comes to believe a correction
    landed.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        with pytest.raises(PaymentRuleError) as refusal:
            amendments.amend_reference(
                dana,
                payment_id=payment.pk,
                note="typo",
                reference=RIGHT_REF,
                body={"reference": RIGHT_REF, "note": "typo", "cheque_date": "2026-08-08"},
            )
        assert "cheque_date" in str(refusal.value)


def test_cs34__a_correction_without_a_note_is_refused(brazos, dana):
    """*"…and a REQUIRED note."*

    The reference is what a bank line is matched on, so changing one changes
    which payment a statement ties to. A month later nobody remembers why it
    moved, and the note is the only thing that will say.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        with pytest.raises(PaymentRuleError) as refusal:
            amendments.amend_reference(
                dana,
                payment_id=payment.pk,
                note="   ",
                reference=RIGHT_REF,
                body={"reference": RIGHT_REF, "note": "   "},
            )
        assert "note" in str(refusal.value)


def test_cs34__another_tenants_payment_is_not_found(brazos, lonestar, dana):
    """CLAUDE.md hard rule 1 + HR-1 — and it refuses BEFORE the stub.

    A cross-tenant id reads as absent, never as somebody else's payment and
    never as *"not implemented"*, which would tell a caller the row exists.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
    with tenant_ctx(lonestar):
        with pytest.raises(PaymentRuleError) as refusal:
            amendments.amend_reference(
                dana,
                payment_id=payment.pk,
                note="typo",
                reference=RIGHT_REF,
                body={"reference": RIGHT_REF, "note": "typo"},
            )
        assert "not one of this tenant's payments" in str(refusal.value)


# ══ 2 · THE TENDER, ONCE BANKED ═════════════════════════════════════════════


def test_cs34__the_tender_is_refused_once_the_payment_is_in_a_batch(brazos, dana):
    """CS-34's second new rule, and it is TRUE WITHOUT ANY WRITE.

    *"The tender may not be amended once the payment has been swept into a
    deposit batch, because batches group by day and tender: changing it would
    move the payment between two batches, one of which may be reconciled and
    locked."*

    The refusal names the batch — `DEP-260808-CHK`, the LABEL a clerk reads on
    S39 and never the batch's database id (B14 rule 31).
    """
    from apps.payments import bankrec_models as bankrec

    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        batch = a_banked_batch(dana, brazos, payment, status=bankrec.BATCH_IN_TRANSIT)

        with pytest.raises(PaymentRuleError) as refusal:
            amendments.amend_reference(
                dana,
                payment_id=payment.pk,
                note="wrong tender",
                tender_id=uuid.uuid4(),
                body={"tender_id": "x", "note": "wrong tender"},
            )
        message = str(refusal.value)
        assert "DEP-260808-CHK" in message
        assert "Take it out of the batch first" in message
        assert str(batch.pk) not in message, "B14 rule 31 — no database id in a refusal"


def test_cs34__a_reconciled_batch_says_so_rather_than_saying_the_same_thing(brazos, dana):
    """An open batch and a locked one need DIFFERENT actions, so they say so.

    An in-transit batch can be re-cut once the payment is out of it. A
    reconciled one is locked by database trigger (BR-PAY-004) and the money has
    been tied to a bank statement — unreconciling is a deliberate, recorded act,
    and telling a clerk to *"take it out of the batch"* would send them at a
    door that refuses.
    """
    from apps.payments import bankrec_models as bankrec

    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        a_banked_batch(dana, brazos, payment, status=bankrec.BATCH_RECONCILED)

        with pytest.raises(PaymentRuleError) as refusal:
            amendments.amend_reference(
                dana,
                payment_id=payment.pk,
                note="wrong tender",
                tender_id=uuid.uuid4(),
                body={"tender_id": "x", "note": "wrong tender"},
            )
        assert "unreconcile" in str(refusal.value).lower()


def test_cs34__a_reference_correction_is_not_blocked_by_the_batch(brazos, dana):
    """Only the TENDER is refused once batched — the cheque number is not.

    The asymmetry is the rule as written: a batch groups by day and tender, so
    the tender decides which batch a payment belongs to and the reference does
    not. A correction that refused both would make CS-34 useless on exactly the
    payments that need it, since a banked cheque is the ordinary case.

    So the cheque number is corrected on a RECONCILED batch's payment, which is
    the assertion: the batch did not stop it.
    """
    from apps.payments import bankrec_models as bankrec

    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        a_banked_batch(dana, brazos, payment, status=bankrec.BATCH_RECONCILED)

        amendments.amend_reference(
            dana,
            payment_id=payment.pk,
            note="typo on the cheque",
            reference=RIGHT_REF,
            body={"reference": RIGHT_REF, "note": "typo on the cheque"},
        )
        payment.refresh_from_db()
        assert payment.confirmation == RIGHT_REF


# ══ 3 · THE WRITE, AND WHAT IT RECORDS ══════════════════════════════════════


def test_cs34__the_correction_lands_and_is_audited(brazos, dana, audit_rows):
    """CS-34's third proof — *"amendment permitted and audited"*.

    `OQ-1322` CLOSED 2026-09-02, PO verbatim *"(a) Allow those fields to
    change"*. The cheque number moves from the mistyped 10241 to 10214, the row
    is read back FROM THE DATABASE rather than off the returned object, and the
    audit row carries the old value and the new — which is the only place the
    old value now lives.

    ⚠ **THE AUDIT HALF IS ASSERTED AT THE SINK, NOT IN `audit_log`, AND THAT IS
    NOT THIS FILE'S CHOICE.** `tests/test_us_met_helpers` installs an AUTOUSE
    capture sink for the whole suite, so no row reaches the table here. What is
    proved is that the kernel was called with the right payload — which is the
    same thing every other payments suite proves, and the honest limit is that a
    broken `apps.audit.services.store_row` would not be caught by this file.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        result = amendments.amend_reference(
            dana,
            payment_id=payment.pk,
            note="typo on the cheque — the bank line reads 10214",
            reference=RIGHT_REF,
            body={"reference": RIGHT_REF, "note": "typo on the cheque"},
        )
        payment.refresh_from_db()
        assert payment.confirmation == RIGHT_REF
        assert result["payment_no"] == payment.payment_no
        assert result["previous"] == {"confirmation": WRONG_REF}
        assert result["corrected"] == {"confirmation": RIGHT_REF}

        written = [row for row in audit_rows if row["action"] == amendments.AUDIT_ACTION]
        assert len(written) == 1, "hard rule 7 — every money action writes audit_log, once"
        row = written[0]
        assert row["entity_type"] == "payments"
        assert row["before"]["confirmation"] == WRONG_REF
        assert row["after"]["confirmation"] == RIGHT_REF
        assert row["after"]["note"].startswith("typo on the cheque")


def test_cs34__a_correction_can_be_made_twice(brazos, dana):
    """A correction is NOT a write-once stamp, and the difference is the point.

    `deposit_batch_id` and `journal_entry_id` are stamps — banked once, posted
    once — so both are guarded against re-pointing. A cheque number is a
    CORRECTION, and a clerk who mistypes twice must be able to correct twice; a
    write-once reference would make the second typo permanent, which is the
    failure CS-34 exists to fix.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        for attempt in ("10215", RIGHT_REF):
            amendments.amend_reference(
                dana,
                payment_id=payment.pk,
                note=f"reading the cheque again: {attempt}",
                reference=attempt,
                body={"reference": attempt, "note": "re-read"},
            )
        payment.refresh_from_db()
        assert payment.confirmation == RIGHT_REF


def test_cs34__the_response_says_the_old_value_is_not_kept_forever(brazos, dana):
    """`OQ-1340`, carried on the RESPONSE rather than only in a docstring.

    The PO accepted that the previous cheque number then lives only in the audit
    trail, and on **2026-09-23 they ruled that that row is pruned like any
    other** — *"keep the same rule s; when audit log is delete - it is deleted
    thats okay"*. So no caller may treat this correction as a permanent record
    of the old value, and the response is where a caller learns it.

    ⚠ **THE CODE READ `amendment_history_retention_unruled` UNTIL THAT RULING,
    AND PINNING THE NEW NAME IS THE POINT OF THIS CASE (`P3.18`).** A key whose
    NAME says *unruled* about something that is ruled is the stale-pointer rot
    this repository files most, and it was riding on every successful correction
    response. This assertion is what stops the old name coming back.

    ⚠ **AND THE ENTRY IS A MACHINE FACT, NOT COPY.** B14 rule 33 puts rationale
    at ZERO words on screen, so the front end's `CorrectionRetentionNote` — which
    rendered this sentence in all eleven catalogues — is deleted in the same
    commit. A screen that explains the retention policy in order to be honest
    breaks rule 33 while trying to obey the ruling.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        result = amendments.amend_reference(
            dana,
            payment_id=payment.pk,
            note="typo",
            reference=RIGHT_REF,
            body={"reference": RIGHT_REF, "note": "typo"},
        )
        codes = {gap["code"] for gap in result["unavailable"]}
        assert "amendment_history_is_not_a_permanent_record" in codes
        # The retired spelling, refused BY NAME so a revert is a red line rather
        # than a silently re-introduced lie.
        assert "amendment_history_retention_unruled" not in codes
        assert amendments.OQ_AMENDMENT_RETENTION in str(result["unavailable"])
        # The sentence stopped saying *undecided* on the day it was decided.
        detail = next(
            gap["detail"]
            for gap in result["unavailable"]
            if gap["code"] == "amendment_history_is_not_a_permanent_record"
        )
        assert "has not been decided" not in detail
        assert "pruned on that schedule" in detail


def test_def3206__the_methods_list_serves_the_id_this_door_resolves(brazos, dana):
    """`DEF-3206` — the door took a key no read gave a screen.

    **Law 2 on a CONTRACT rather than on a prop, which is why nothing caught
    it.** Every refusal above and the write itself are proved with a tender id
    the fixture makes for itself, so the backend half was complete and green.
    `selectors.active_payment_methods()` — the ONE list BR-PAY-026 gives the S33
    filter and the S22 Record form — served `code` and `name` and nothing else,
    so no screen could name a tender and the tender third of the PO's ruling was
    unreachable from the product.

    This asserts the two halves TOGETHER, which is the only way the gap is
    visible: the id the list publishes is an id this door accepts.
    """
    from apps.payments import selectors

    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        served = selectors.active_payment_methods()
        assert served, "BR-PAY-026 seeds six methods; an empty list is a broken fixture"
        assert all("id" in entry for entry in served), "the picker cannot name a tender"
        # Still the vocabulary the filter and the Record form key on — the id is
        # ADDED beside them and replaces neither.
        assert all({"id", "code", "name"} <= set(entry) for entry in served)

        # The half that proves it is the RIGHT id: hand one straight back to the
        # door and it resolves. A read serving a plausible-looking key the write
        # path rejects is the same defect wearing a different shape.
        other = next(entry for entry in served if entry["code"] != payment.method.code)
        result = amendments.amend_reference(
            dana,
            payment_id=payment.pk,
            note="taken by card at the counter, not by cheque",
            tender_id=other["id"],
            body={"tender_id": other["id"], "note": "taken by card at the counter, not by cheque"},
        )
        assert result["corrected"]["method_id"] == other["id"]
        payment.refresh_from_db()
        assert str(payment.method_id) == other["id"]


def test_cs34__an_unknown_tender_is_refused_rather_than_stored(brazos, dana):
    """A write path must resolve what it is about to store.

    `method_id` is a foreign key. An id naming nothing would be caught by
    PostgreSQL as a constraint violation and by SQLite as NOTHING AT ALL — a
    dangling tender on every payment corrected through the default suite. The
    refusal is the service's, in words, before either database is asked.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        with pytest.raises(PaymentRuleError) as refusal:
            amendments.amend_reference(
                dana,
                payment_id=payment.pk,
                note="wrong tender",
                tender_id=uuid.uuid4(),
                body={"tender_id": "x", "note": "wrong tender"},
            )
        assert "active payment methods" in str(refusal.value)
        payment.refresh_from_db()
        assert payment.method_id is not None


def test_cs34__a_refused_correction_writes_nothing(brazos, dana, audit_rows):
    """Hard rule 7 owes an audit row for an action that HAPPENED.

    A row written for a correction that was REFUSED would be a false event in
    the one trail this correction's control depends on. So a body carrying an
    amount leaves the payment untouched and writes no correction row.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        with pytest.raises(PaymentRuleError):
            amendments.amend_reference(
                dana,
                payment_id=payment.pk,
                note="typo",
                reference=RIGHT_REF,
                body={"reference": RIGHT_REF, "note": "typo", "amount": "300.00"},
            )
        payment.refresh_from_db()
        assert payment.confirmation == WRONG_REF, "the row is untouched"
        assert [row for row in audit_rows if row["action"] == amendments.AUDIT_ACTION] == []


def test_cs34__the_audit_shape_carries_the_old_value_and_the_new(brazos, dana):
    """*"Every amendment writes an audit row carrying the old value and the new."*

    Composed and asserted rather than promised, so that whichever reading of the
    open question wins, the evidence half is already decided and identical.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        shape = amendments.audit_shape(
            payment, reference=RIGHT_REF, memo=None, tender_id=None, note="typo on the cheque"
        )
        assert shape["action"] == "payment.reference_amended"
        assert shape["entity_type"] == "payments"
        assert shape["before"] == {"confirmation": WRONG_REF}
        assert shape["after"]["confirmation"] == RIGHT_REF
        assert shape["after"]["note"] == "typo on the cheque"


# ══ 4 · THE ROUTE — NAMED, AND NOT A PATCH ══════════════════════════════════


def test_cs34__the_route_is_named_and_resolves(brazos, dana):
    """CS-34's backend note, as a resolvable path.

    *"A named endpoint that accepts only these fields and nothing else, so what
    can be amended is visible in the route rather than enforced inside it."*
    Resolved through the ROOT URLconf so a future lane cannot lose the
    `config/urls.py` include silently (hard-won law 2).
    """
    from django.urls import resolve

    match = resolve(f"/api/{brazos.subdomain}/payments/{uuid.uuid4()}/correct-reference")
    assert match.func is amendments_api.payment_correct_reference


def test_cs34__no_edit_verb_is_added_to_any_payment_path(brazos, dana):
    """*"The rule that there is no edit verb on a payment path is load-bearing
    and should stay absolute."*

    Read off the URLconf rather than off this lane's memory: every pattern whose
    route begins `payments` is asked which methods its view declares, and none
    of them may declare PATCH, PUT or DELETE. So a lane that adds one later goes
    red here whichever file it adds it in.
    """
    from django.urls import get_resolver

    def walk(resolver, prefix=""):
        for entry in resolver.url_patterns:
            route = prefix + str(getattr(entry, "pattern", ""))
            if hasattr(entry, "url_patterns"):
                yield from walk(entry, route)
            else:
                yield route, entry

    offenders = []
    for route, entry in walk(get_resolver()):
        if "payments" not in route:
            continue
        view_class = getattr(entry.callback, "cls", None)
        if view_class is None:
            continue
        allowed = {method.upper() for method in view_class.http_method_names}
        # `api_view` sets `http_method_names` to exactly the verbs the decorator
        # was given, so this reads what the ROUTE serves rather than DRF's
        # defaults — which is the only reading that can go red on a new verb.
        offenders.extend(
            f"{route}:{verb}" for verb in ("PATCH", "PUT", "DELETE") if verb in allowed
        )
    assert offenders == [], f"a payment path grew an edit verb: {offenders}"


def test_cs34__the_route_refuses_a_money_field_over_http(brazos, dana):
    """The refusal reaches a CALLER as a refusal, not as a stack trace.

    Asserted on the RESPONSE rather than on a raised exception, and the
    difference matters: DRF's handler turns a catalog exception into a 4xx
    envelope, so a test that only caught the Python exception would still pass
    on a view that swallowed it and answered 200.

    `BIZ-IMMUTABLE` and not `BIZ-COMPLETENESS`: every refusal on this path is
    *"that field is financial history"* or *"that batch is closed"*, and a
    completeness code would tell the screen the clerk left something out.
    """
    from core import errors

    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        response = call(
            amendments_api.payment_correct_reference,
            brazos,
            payment_id=str(payment.pk),
            data={"reference": RIGHT_REF, "note": "typo", "amount": "300.00"},
        )
        # 409, because `BIZ-IMMUTABLE` is a CONFLICT with the state of the row
        # and not a malformed request — the envelope's own status map
        # (`errors.HTTP_STATUS_BY_CODE`) decides that, not this route.
        assert response.status_code == 409
        assert response.data["code"] == errors.BIZ_IMMUTABLE
        # B14 rule 32 / CR-016 — the CODE is a support-line string and the
        # screen never prints it; what a clerk reads comes from the catalogue
        # entry for `message_key`.
        assert response.data["message_key"] == "payments.correct_reference.refused"


# ══ 5 · WHAT SQLITE CANNOT PROVE (CLAUDE.md law 14) ═════════════════════════


def test_cs34__sqlite_proves_nothing_about_the_trigger(brazos, dana):
    """The limit, STATED rather than left to be discovered.

    `payments_payment_immutable` exists on **PostgreSQL only** and
    `config/settings/test.py` hardcodes in-memory SQLite. So on the default
    suite an UPDATE of the **amount** succeeds — this case asserts that it does,
    which is the honest way to record that the guard is absent here rather than
    a green assertion that means nothing.

    **That is exactly why the write this file exercises had to be proved on a
    real cluster**: a version that opened `confirmation` and accidentally opened
    the amount with it would be green on every machine in this repository.
    """
    if connection.vendor == "postgresql":
        pytest.skip("this case documents the SQLite tier; the Postgres ones follow")
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        models.Payment.objects.filter(pk=payment.pk).update(amount=Decimal("1.00"))
        payment.refresh_from_db()
        assert payment.amount == Decimal("1.00"), (
            "SQLite has no triggers, so hard rule 4 is INVISIBLE here — even for the "
            "amount, which no ruling has ever made correctable. That is law 14"
        )


@requires_postgres
def test_cs34__the_trigger_now_allows_the_three_columns(brazos, dana):
    """THE RULING AT THE DATABASE — run against the real cluster.

    `OQ-1322` CLOSED 2026-09-02: *"(a) Allow those fields to change"*. The raw
    statement that raised `BR-PAY-002 / hard rule 4` before `payments/0014` now
    succeeds, and it succeeds at the DATABASE with no Django layer in between
    that could be mistaken for the guard.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE payments SET confirmation = %s, memo = %s WHERE id = %s",
                [RIGHT_REF, "re-read from the cheque", str(payment.pk)],
            )
        payment.refresh_from_db()
        assert payment.confirmation == RIGHT_REF
        assert payment.memo == "re-read from the cheque"


@requires_postgres
def test_cs34__the_trigger_still_refuses_the_amount(brazos, dana):
    """THE HALF THAT DID NOT MOVE, and it is the half worth proving.

    The narrowing is three columns. Everything else on `payments` is exactly as
    frozen as it was, and the whole-row comparison that freezes a column added
    tomorrow is untouched — so a lane that widened the allow list one field too
    far goes red here.
    """
    from django.db import DatabaseError

    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        # ⚠ **A SAVEPOINT AROUND IT, AND IT IS DELIBERATE.** On PostgreSQL a
        # failed statement poisons the whole transaction, so without the nested
        # atomic the NEXT query — `tenant_ctx.__exit__` resetting
        # `app.tenant_id` — raises `TransactionManagementError` and the test
        # fails in its own teardown having already proved its point. CLAUDE.md
        # law 14, biting the proof of law 14.
        with pytest.raises(DatabaseError) as refused, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE payments SET amount = %s WHERE id = %s",
                    ["1.00", str(payment.pk)],
                )
        assert "append-only" in str(refused.value)
        assert "hard rule 4" in str(refused.value)
        payment.refresh_from_db()
        assert payment.amount == CHEQUE


@requires_postgres
def test_cs34__the_trigger_refuses_the_tender_once_the_payment_is_banked(brazos, dana):
    """CS-34's second rule, at the DATABASE and not only in the service.

    The service refuses it with the batch NAMED, which is what a clerk needs.
    This is the same rule for whoever opens a cursor instead — because a Python
    check is not a guarantee, which is the whole reason `payments/0014` exists.
    """
    from django.db import DatabaseError

    from apps.payments import bankrec_models as bankrec

    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        a_banked_batch(dana, brazos, payment, status=bankrec.BATCH_IN_TRANSIT)
        with pytest.raises(DatabaseError) as refused, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE payments SET method_id = NULL WHERE id = %s", [str(payment.pk)]
                )
        assert "BR-PAY-025" in str(refused.value)
        # …and the cheque number is still correctable on the same banked row.
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE payments SET confirmation = %s WHERE id = %s",
                [RIGHT_REF, str(payment.pk)],
            )
        payment.refresh_from_db()
        assert payment.confirmation == RIGHT_REF


@requires_postgres
def test_cs34__a_payment_still_cannot_be_deleted(brazos, dana):
    """The other half of hard rule 4, untouched by the narrowing.

    The ruling was about three columns changing. DELETE is refused in every
    status, as it always was, and a migration that replaced the whole function
    body is exactly where that could have been dropped by accident.
    """
    from django.db import DatabaseError

    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        with pytest.raises(DatabaseError) as refused, transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM payments WHERE id = %s", [str(payment.pk)])
        assert "cannot be removed" in str(refused.value)
        assert models.Payment.objects.filter(pk=payment.pk).exists()


@requires_postgres
def test_cs34__the_service_corrects_a_reference_on_postgres(brazos, dana, audit_rows):
    """END TO END ON THE REAL DATABASE — the case that makes the rest true.

    Everything above this block runs on SQLite, where the trigger does not
    exist and therefore proves nothing about it. This one drives
    `amend_reference` on PostgreSQL 16: the correction lands through the
    service, past the real trigger, and its audit row is written in the same
    transaction — so neither is a Python check pretending to be a database.
    """
    with tenant_ctx(brazos):
        payment = a_payment(dana, brazos)
        amendments.amend_reference(
            dana,
            payment_id=payment.pk,
            note="typo on the cheque — the bank line reads 10214",
            reference=RIGHT_REF,
            body={"reference": RIGHT_REF, "note": "typo on the cheque"},
        )
        payment.refresh_from_db()
        assert payment.confirmation == RIGHT_REF
        assert [row for row in audit_rows if row["action"] == amendments.AUDIT_ACTION]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §7 · §8 CS-34 · §11 task 41 · 12-governance/02-decision-log.md
#         2026-09-02 (OQ-1322 CLOSED, option a) · CLAUDE.md hard rule 4
#         (NARROWED 2026-09-02) · law 14 ·
#         apps/payments/migrations/0014_cr059_cs34_amendable_reference.py
# generated: 2026-09-02 by the CR-059 W7 correct-what-is-not-money lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(CR-059 task 42 owns S35 and S21) F✔ G✔
#            H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — with `refuse_money_fields` returning early, all five
#        parametrised money-field cases fail on `DID NOT RAISE
#        PaymentRuleError`; and with `payments/0014`'s trigger body swapped back
#        to 0006's on a live PostgreSQL 16 cluster, three cases fail verbatim on
#        `django.db.utils.ProgrammingError: BR-PAY-002 / hard rule 4: payment
#        PY-260808-0001 is cleared and is append-only — no column may change
#        except the deposit batch it is banked in (BR-PAY-025) and the journal
#        entry it posted (US-PAY-009), each once. … Changed: confirmation`.
#        GREEN with the migration applied: 25 passed, 1 skipped on PostgreSQL 16
#        (the skip is the SQLite-tier case, which skips there on purpose)
# exceptions:
#   E1 `test_cs34__sqlite_proves_nothing_about_the_trigger` asserts the ABSENCE
#      of the guard on the default tier. That is deliberate: a case that
#      silently skipped would leave a reader believing the tier proves something
#      it cannot.
#   E2 every case outside the `@requires_postgres` block runs on SQLite, where
#      the trigger does not exist. What those cases prove is the SERVICE, and
#      the five Postgres cases are what prove the database
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
