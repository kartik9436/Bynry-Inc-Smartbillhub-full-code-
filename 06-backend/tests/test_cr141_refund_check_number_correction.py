# ── Trace ──────────────────────────────────────────────
# Change:   CR-141-BRC07 — a refund's check number may be corrected, the same
#           way a payment's can (OQ-PAY-12614, CLOSED 2026-09-23, option b).
# Story:    US-PAY-011 (refunds) §5 ("required for check") · S58
# Rules:    CLAUDE.md hard rule 4 (financial immutability — `refunds` is NOT one
#           of its tables; its freeze is `payments/0006`'s deny-by-default, made
#           write-once for the check number by `payments/0041`) · hard rule 7
#           (every money action writes `audit_log`) · BR-PAY-014 · BR-PAY-021 ·
#           BR-PAY-1071 (who issues a refund — and so who corrects its number)
# Ruling:   PO, verbatim, 2026-09-23: *"One thing needs your sign-off, because
#           it is a money record: (b) Allow a correction, the same way you
#           allowed it for payments on 2 September"*. SHOWN: *Dana sends a
#           refund of $91.60 by check #10241 but types #10214; as built it can
#           never be changed.*
# Migration:06-backend/apps/payments/migrations/0043_cr141_correctable_refund_check_number.py
# ───────────────────────────────────────────────────────
"""A refund's check number may be corrected — through ONE named door, and only it.

**THE FIGURE THIS FILE ASSERTS IS THE ONE THE PO WAS SHOWN**, and nothing is
computed to reach it: a refund of **$91.60**, sent by check **#10241**, typed as
**#10214**. Corrected through `POST /refunds/{id}/correct-reference`, the row
reads #10241 and the audit trail holds both numbers.

════════════════════════════════════════════════════════════════════════════
WHAT THE SIGNATURE COVERS, AND SO WHAT THIS FILE REFUSES
════════════════════════════════════════════════════════════════════════════
*"A signature covers only what was shown"* (CLAUDE.md, the 2026-08-11 sign-off
rule). What was shown was the CHECK NUMBER. The payment rule the PO pointed at
also lets a memo and a tender move; **those were not put to the PO for a refund
and are refused here BY NAME**, beside the amount, the account and the method.

════════════════════════════════════════════════════════════════════════════
THE FOUR PROOFS THE BRIEF ASKS FOR, AND WHICH TIER EACH ONE NEEDS
════════════════════════════════════════════════════════════════════════════
  (i)   the correction SUCCEEDS through the endpoint, and `audit_log` holds both
        values — the TABLE, not the capture sink every other test here uses;
  (ii)  changing `reference` by ANY OTHER write is REFUSED by the database;
  (iii) changing the amount, the account or the method THROUGH the correction
        path is REFUSED — at the door by name, and at the database inside the
        correction window;
  (iv)  correcting a refund that has NO check number yet is REFUSED.

⚠ **(ii) AND THE DATABASE HALVES OF (iii) AND (iv) EXIST ON POSTGRESQL ONLY.**
`config/settings/test.py` hardcodes in-memory SQLite, which has no triggers, so
on the default tier every UPDATE succeeds whether `payments/0043` ran or not
(CLAUDE.md hard-won law 14). Those cases carry `requires_postgres` and SKIP off
PostgreSQL rather than passing vacuously; run them with
`--ds=config.settings.pgtest --reuse-db`.

⚠ **(i) AND (ii) ARE THE TWO DIRECTIONS, AND NEITHER IS WORTH ANYTHING ALONE.**
A test proving only that a raw rewrite is refused would pass just as well if the
correction window never opened — the product would then be exactly as broken as
the PO's worked case. A test proving only that the correction lands would pass
just as well if the column had been thrown open to every writer, which is the
payment path's design (`payments/0014`) and the one this migration deliberately
did NOT copy. `REFUND-MONEY`'s own report names this trap for `0041`.
"""

import importlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection, transaction

from apps.payments import models, refunds, refunds_api
from apps.payments.exceptions import PaymentRuleError
from core import errors

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import executive_actor, tenant_ctx
from tests.test_us_pay_001_record_payment import a_payment, pe1_bills
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

# ── THE PO's WORKED CASE, VERBATIM — copied, never computed ──────────────────
#: *"Dana sends a refund of $91.60 …"*
REFUND_AMOUNT = Decimal("91.60")
#: *"… by check #10241 …"* — the number on the paper that left the building.
CHECK_WRITTEN = "10241"
#: *"… but types #10214"* — the number the clerk keyed at issue.
CHECK_TYPED = "10214"

#: PE-1's two open bills total $292.87; paying $384.47 against them carries a
#: credit of exactly $91.60 — the PO's figure — so the refund below is funded
#: by a real credit and `_credit_or_refuse` passes at request AND at issue.
PAID_AGAINST_PE1 = Decimal("384.47")

REQUESTED_AT = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)
APPROVED_AT = datetime(2026, 9, 21, 9, 30, tzinfo=UTC)
ISSUED_AT = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)

NOTE = "the check stub reads 10241; I keyed 10214"

M0041 = "apps.payments.migrations.0041_def_pay_6331_cheque_number_at_issue"
M0043 = "apps.payments.migrations.0043_cr141_correctable_refund_check_number"


# ── fixtures, reached through the real services — no ORM shortcuts ──────────
def an_account_with_the_po_credit(brazos, marcus):
    """An account holding $91.60 of real credit (PE-1's bills, overpaid)."""
    account = an_account(marcus, brazos)
    pe1_bills(brazos, account)
    recorded = a_payment(marcus, account, amount=PAID_AGAINST_PE1)
    assert recorded.credit_carried == REFUND_AMOUNT, "the PO's figure, not a nearby one"
    return account, recorded


def an_approved_refund(brazos, marcus, dana, *, method=models.REFUND_METHOD_CHECK):
    """$91.60, requested by a clerk and approved by an Admin — NO check number."""
    account, recorded = an_account_with_the_po_credit(brazos, marcus)
    requested = refunds.request_refund(
        marcus,
        payment_id=recorded.payment_id,
        amount=REFUND_AMOUNT,
        method=method,
        reason="Overpayment",
        requested_at=REQUESTED_AT,
    )
    refunds.approve_refund(dana, refund_id=requested.refund_id, approved_at=APPROVED_AT)
    return account, requested.refund_id


def dana_sends_it_as_10214(brazos, marcus, dana):
    """The PO's case, exactly: sent by check #10241, keyed as #10214."""
    account, refund_id = an_approved_refund(brazos, marcus, dana)
    refunds.issue_refund(dana, refund_id=refund_id, issued_at=ISSUED_AT, reference=CHECK_TYPED)
    row = models.Refund.objects.get(pk=refund_id)
    assert row.reference == CHECK_TYPED
    assert row.status == models.REFUND_ISSUED
    return account, refund_id


def _post(view, tenant, *, actor, role="billing_clerk", data=None, **kw):
    return api_call(view, "post", user=actor.user, role=role, tenant=tenant, data=data or {}, **kw)


def _correct(refund_id, *, actor, reference=CHECK_WRITTEN, note=NOTE, body=None):
    return refunds.correct_refund_reference(
        actor,
        refund_id=refund_id,
        reference=reference,
        note=note,
        body=body if body is not None else {"reference": reference, "note": note},
    )


@pytest.fixture()
def audit_reaches_the_table():
    """Put audit's OWN sink back, so proof (i) reads `audit_log` itself.

    `tests/test_us_met_helpers.py` installs an AUTOUSE sink that captures every
    audit row into a Python list — right for every other case here, and exactly
    wrong for a proof whose subject is the TABLE. Same shape and same reason as
    `test_cr137_p3_detail_cancel_receipt.audit_reaches_the_table`. Restored
    afterwards, so a later case still sees the capture it expects.
    """
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


# ══ 0 · THE MIGRATION IS 0041 WITH THREE HUNKS MOVED, AND NOTHING ELSE ═══════


def test_cr141__the_forward_body_is_0041_with_exactly_three_hunks_replaced():
    """The byte-for-byte proof, made a test so it cannot rot into a claim.

    plpgsql has no partial replacement, so `0043` restates the whole of
    `payments_refund_immutable`. **The diff against `0041` IS the review** —
    and this case rebuilds `0043`'s body FROM `0041`'s by replacing exactly the
    three blocks `0043` names, each of which must occur in `0041` exactly once,
    and requires the result to be byte-identical. A fourth change anywhere — a
    reworded refusal, a dropped DELETE guard, a column slipped onto the allow
    list — makes the two strings differ and this goes red.
    """
    old = importlib.import_module(M0041)
    new = importlib.import_module(M0043)
    rebuilt = old.WRITE_ONCE_REFERENCE_SQL
    assert len(new.HUNKS) == 3
    for before, after in new.HUNKS:
        assert rebuilt.count(before) == 1, f"a hunk must name ONE place in 0041:\n{before}"
        rebuilt = rebuilt.replace(before, after)
    assert rebuilt == new.CORRECTABLE_REFERENCE_SQL


def test_cr141__the_reverse_restores_0041_byte_for_byte():
    """An unapply must land on EXACTLY what came before (hard-won law 3).

    Not a DROP — that would leave `refunds` unfrozen — and not `0006`'s body,
    which would silently re-freeze the check number `0041` opened at issue.
    """
    old = importlib.import_module(M0041)
    new = importlib.import_module(M0043)
    assert new.RESTORE_0041_SQL == old.WRITE_ONCE_REFERENCE_SQL


def test_cr141__the_payments_function_is_not_touched():
    """`payments/0014` stays the ONLY place `payments`' allow list has moved.

    CLAUDE.md hard rule 4 names `payments`; it does not name `refunds`. Restating
    `payments_payment_immutable` here from any older copy would silently revert
    the PO's three-column correction of 2026-09-02.
    """
    new = importlib.import_module(M0043)
    for sql in (new.CORRECTABLE_REFERENCE_SQL, new.RESTORE_0041_SQL):
        assert "payments_payment_immutable" not in sql
        assert "CREATE OR REPLACE FUNCTION payments_refund_immutable()" in sql


# ══ 1 · THE CORRECTION ITSELF — the PO's worked case, through the service ════


def test_cr141__the_po_case_10214_becomes_10241_and_is_audited(brazos, marcus, dana, audit_rows):
    """*Dana sends a refund of $91.60 by check #10241 but types #10214.*

    Corrected. The row is read back FROM THE DATABASE, the money is exactly
    where it was, and the audit row carries the old number and the new.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        before = models.Refund.objects.get(pk=refund_id)

        result = _correct(refund_id, actor=dana)

        row = models.Refund.objects.get(pk=refund_id)
        assert row.reference == CHECK_WRITTEN
        assert result["previous"] == {"reference": CHECK_TYPED}
        assert result["corrected"] == {"reference": CHECK_WRITTEN}
        # The check number is the ONLY thing that moved.
        for column in (
            "amount",
            "currency",
            "account_id",
            "payment_id",
            "method",
            "status",
            "issued_at",
            "journal_entry_id",
        ):
            assert getattr(row, column) == getattr(before, column), column
        assert row.amount == REFUND_AMOUNT

        written = [r for r in audit_rows if r["action"] == refunds.AUDIT_REFERENCE_CORRECTED]
        assert len(written) == 1, "hard rule 7 — one audit row per correction"
        assert written[0]["entity_type"] == "refund"
        assert written[0]["before"] == {"reference": CHECK_TYPED}
        assert written[0]["after"]["reference"] == CHECK_WRITTEN
        assert written[0]["after"]["note"] == NOTE


def test_cr141__a_clerk_who_mistypes_twice_can_correct_twice(brazos, marcus, dana):
    """A correction is not a write-once stamp — the payment path's own reason.

    A clerk who fixes #10214 to #10421 and then reads the stub again must be
    able to fix it a second time; a correction that could happen only once
    would make the second typo permanent, which is the failure being corrected.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        _correct(refund_id, actor=marcus, reference="10421")
        _correct(refund_id, actor=marcus, reference=CHECK_WRITTEN)
        assert models.Refund.objects.get(pk=refund_id).reference == CHECK_WRITTEN


def test_cr141__a_cleared_refund_can_still_be_corrected(brazos, marcus, dana):
    """The bank statement is usually where the typo is FOUND.

    A check that cleared under #10241 while the row says #10214 is the case
    the correction exists for; a status gate at `issued` would refuse it at
    exactly the moment somebody notices.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        refunds.clear_refund(
            dana, refund_id=refund_id, cleared_at=datetime(2026, 9, 24, 9, 0, tzinfo=UTC)
        )
        _correct(refund_id, actor=dana)
        row = models.Refund.objects.get(pk=refund_id)
        assert row.reference == CHECK_WRITTEN
        assert row.status == models.REFUND_CLEARED


def test_cr141__the_response_never_calls_the_trail_a_permanent_record(brazos, marcus, dana):
    """`OQ-1340`, CLOSED 2026-09-23: a correction's audit row is pruned like any other.

    PO: *"keep the same rule s; when audit log is delete - it is deleted thats
    okay"*. The replaced number lives ONLY in `audit_log`, so the response carries
    the payment path's own machine fact — the same code, one vocabulary — and a
    caller can reason about it. It is not copy: B14 rule 33 puts rationale at
    zero words on screen.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        result = _correct(refund_id, actor=dana)
        codes = {gap["code"] for gap in result["unavailable"]}
        assert codes == {"amendment_history_is_not_a_permanent_record"}
        assert "OQ-1340" in result["unavailable"][0]["br_ref"]
        assert "permanent record of the previous value" in result["unavailable"][0]["detail"]


# ══ 2 · WHAT THE DOOR REFUSES, BY NAME ═══════════════════════════════════════


@pytest.mark.parametrize(
    "field, value",
    [
        ("amount", "100.00"),
        ("account_id", "019ff23d-13ee-7aba-a280-58058e492cb9"),
        ("method", "ach"),
        # The payment rule lets these two move. They were NOT shown to the PO
        # for a refund, so they are NOT signed — refused by name, not ignored.
        ("memo", "re-read"),
        ("tender_id", "019ff23d-13ee-7aba-a280-58058e492cb9"),
        ("status", "cleared"),
        ("issued_at", "2026-09-22T10:00:00Z"),
    ],
)
def test_cr141__proof_iii_the_correction_refuses_every_other_field_by_name(
    brazos, marcus, dana, field, value
):
    """Proof (iii), the SERVICE half — refused FIRST, and refused BY NAME.

    Parametrised rather than looped, because a loop that stopped at the first
    offender would prove one field and report seven.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        with pytest.raises(PaymentRuleError) as refusal:
            _correct(
                refund_id,
                actor=dana,
                body={"reference": CHECK_WRITTEN, "note": NOTE, field: value},
            )
        assert field in str(refusal.value)
        assert "check number" in str(refusal.value)
        assert models.Refund.objects.get(pk=refund_id).reference == CHECK_TYPED


def test_cr141__an_unknown_field_is_refused_rather_than_ignored(brazos, marcus, dana):
    """A field this door does not know is a caller mistake or a rename.

    Silently dropping one is how a clerk comes to believe a correction landed.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        with pytest.raises(PaymentRuleError) as refusal:
            _correct(
                refund_id,
                actor=dana,
                body={"reference": CHECK_WRITTEN, "note": NOTE, "check_date": "2026-09-21"},
            )
        assert "check_date" in str(refusal.value)


def test_cr141__proof_iv_a_refund_with_no_check_number_is_refused(brazos, marcus, dana):
    """Proof (iv), the SERVICE half. An approved refund has no check number yet.

    Writing the first number is the ISSUE act — `POST /refunds/{id}/issue`,
    which checks the credit, posts the money and audits the payout. A
    "correction" that could write the first number would be a second way to put
    a check number on a refund whose money never moved.
    """
    with tenant_ctx(brazos):
        _account, refund_id = an_approved_refund(brazos, marcus, dana)
        with pytest.raises(PaymentRuleError) as refusal:
            _correct(refund_id, actor=dana)
        assert "no check number yet" in str(refusal.value)
        row = models.Refund.objects.get(pk=refund_id)
        assert row.reference is None
        assert row.status == models.REFUND_APPROVED


def test_cr141__an_ach_refund_sent_without_a_number_is_refused_too(brazos, marcus, dana):
    """The refusal is about the NUMBER, not the method or the status.

    An ACH refund is lawfully issued with no reference (BR-PAY-014, *"check/ACH
    v1"*). It is ISSUED and still has nothing to correct.
    """
    with tenant_ctx(brazos):
        _account, refund_id = an_approved_refund(
            brazos, marcus, dana, method=models.REFUND_METHOD_ACH
        )
        refunds.issue_refund(dana, refund_id=refund_id, issued_at=ISSUED_AT)
        with pytest.raises(PaymentRuleError) as refusal:
            _correct(refund_id, actor=dana)
        assert "no check number yet" in str(refusal.value)


def test_cr141__a_voided_refund_is_closed(brazos, marcus, dana):
    """`0006`'s VOID guard is untouched: a voided refund is finished.

    Nothing about a voided check was put to the PO, so the correction door does
    not reopen one.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        refunds.void_refund(
            dana,
            refund_id=refund_id,
            voided_at=datetime(2026, 9, 22, 9, 0, tzinfo=UTC),
            void_reason="lost in the post",
        )
        with pytest.raises(PaymentRuleError) as refusal:
            _correct(refund_id, actor=dana)
        assert "cancelled" in str(refusal.value)
        assert models.Refund.objects.get(pk=refund_id).reference == CHECK_TYPED


@pytest.mark.parametrize("reference", ["", "   ", None])
def test_cr141__a_correction_cannot_erase_the_number(brazos, marcus, dana, reference):
    """A correction REPLACES a check number; it never removes one.

    US-PAY-011 §5 makes a check refund's number required at issue. A blank
    "correction" would undo that requirement after the money had left.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        with pytest.raises(PaymentRuleError) as refusal:
            _correct(
                refund_id,
                actor=dana,
                reference=reference,
                body={"reference": reference, "note": NOTE},
            )
        assert "new check number" in str(refusal.value)
        assert models.Refund.objects.get(pk=refund_id).reference == CHECK_TYPED


def test_cr141__the_same_number_is_not_a_correction(brazos, marcus, dana, audit_rows):
    """Correcting #10214 to #10214 would write an audit row saying nothing moved.

    The audit trail is the only place a replaced number lives, so it is not
    filled with noise.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        with pytest.raises(PaymentRuleError) as refusal:
            _correct(refund_id, actor=dana, reference=f" {CHECK_TYPED} ")
        assert CHECK_TYPED in str(refusal.value)
        assert not [r for r in audit_rows if r["action"] == refunds.AUDIT_REFERENCE_CORRECTED]


def test_cr141__a_correction_needs_a_note(brazos, marcus, dana):
    """The payment path's refusal, mirrored: *"a correction needs a note saying why"*.

    The number is what bank reconciliation matches the outgoing check on, so
    changing it changes which bank line the refund ties to — and a month later
    nobody remembers why it moved.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        with pytest.raises(PaymentRuleError) as refusal:
            _correct(refund_id, actor=dana, note="  ")
        assert "note" in str(refusal.value)


def test_cr141__an_executive_cannot_correct_it(brazos, marcus, dana):
    """Who corrects the number is who writes the check: Admin or Billing Clerk.

    `BR-PAY-1071` as amended 2026-09-03 (*"q6 yes Clark can issue refund"*).
    An Executive may mark a refund cleared — a bank fact — and may not issue
    one, so it may not rewrite what was issued either. The service gate is the
    enforcement (BR-SHL-025); the route mirrors it.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        with pytest.raises(errors.AuthError):
            _correct(refund_id, actor=executive_actor())
        assert models.Refund.objects.get(pk=refund_id).reference == CHECK_TYPED


def test_cr141__another_tenants_refund_is_not_found(brazos, lonestar, marcus, dana, erin):
    """HR-1: a refund in another utility reads exactly like one that does not exist."""
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
    with tenant_ctx(lonestar):
        with pytest.raises(PaymentRuleError) as refusal:
            _correct(refund_id, actor=erin)
        assert "not one of this tenant's refunds" in str(refusal.value)
    with tenant_ctx(brazos):
        assert models.Refund.objects.get(pk=refund_id).reference == CHECK_TYPED


def test_cr141__the_issue_act_still_refuses_a_different_number(brazos, marcus, dana):
    """WRITE-ONCE STAYS FOR THE ISSUE WRITE — only the correction door opened.

    A refund recorded with its number already known keeps it at issue, exactly
    as `0041` made it. What changed is the refusal's last sentence: it names
    the door that CAN change it, instead of saying it never changes.
    """
    with tenant_ctx(brazos):
        account, recorded = an_account_with_the_po_credit(brazos, marcus)
        requested = refunds.request_refund(
            marcus,
            payment_id=recorded.payment_id,
            amount=REFUND_AMOUNT,
            method=models.REFUND_METHOD_CHECK,
            reference=CHECK_WRITTEN,
            reason="Overpayment",
            requested_at=REQUESTED_AT,
        )
        refunds.approve_refund(dana, refund_id=requested.refund_id, approved_at=APPROVED_AT)
        with pytest.raises(PaymentRuleError) as refusal:
            refunds.issue_refund(
                dana, refund_id=requested.refund_id, issued_at=ISSUED_AT, reference=CHECK_TYPED
            )
        assert "Correct check number" in str(refusal.value)
        assert "never changed" not in str(refusal.value)


# ══ 3 · THE ROUTE — named, and not a PATCH ═══════════════════════════════════


def test_cr141__the_route_is_named_and_resolves(brazos):
    """Resolved through the ROOT URLconf, so a lost include goes red (law 2)."""
    from django.urls import resolve

    match = resolve(f"/api/{brazos.subdomain}/refunds/{uuid.uuid4()}/correct-reference")
    assert match.func is refunds_api.refund_correct_reference


def test_cr141__no_edit_verb_is_added_to_any_refund_path(brazos):
    """The correction is a named POST. No refund path grows PATCH, PUT or DELETE."""
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
        if "refunds" not in route:
            continue
        view_class = getattr(entry.callback, "cls", None)
        if view_class is None:
            continue
        allowed = {method.upper() for method in view_class.http_method_names}
        offenders.extend(f"{route}:{v}" for v in ("PATCH", "PUT", "DELETE") if v in allowed)
    assert offenders == [], offenders


def test_cr141__the_door_corrects_over_http(brazos, marcus, dana):
    """A Billing Clerk — the person who writes the check — corrects it over HTTP."""
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
    answered = _post(
        refunds_api.refund_correct_reference,
        brazos,
        actor=marcus,
        data={"reference": CHECK_WRITTEN, "note": NOTE},
        refund_id=str(refund_id),
    )
    assert answered.status_code == 200, answered.data
    assert answered.data["corrected"] == {"reference": CHECK_WRITTEN}
    assert answered.data["previous"] == {"reference": CHECK_TYPED}
    assert answered.data["refund"]["reference"] == CHECK_WRITTEN
    assert answered.data["refund"]["amount"].startswith("91.60")


def test_cr141__the_door_refuses_the_amount_over_http(brazos, marcus, dana):
    """Asserted on the RESPONSE: a 409 envelope, not a stack trace, not a 200."""
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
    answered = _post(
        refunds_api.refund_correct_reference,
        brazos,
        actor=marcus,
        data={"reference": CHECK_WRITTEN, "note": NOTE, "amount": "100.00"},
        refund_id=str(refund_id),
    )
    assert answered.status_code == 409
    assert answered.data["code"] == errors.BIZ_IMMUTABLE
    assert answered.data["message_key"] == "payments.refunds.correct.refused"
    with tenant_ctx(brazos):
        assert models.Refund.objects.get(pk=refund_id).reference == CHECK_TYPED


def test_cr141__an_executive_is_refused_at_the_door(brazos, marcus, dana):
    """The route mirrors the service gate and never widens it (BR-SHL-025)."""
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
    answered = _post(
        refunds_api.refund_correct_reference,
        brazos,
        actor=dana,
        role="executive",
        data={"reference": CHECK_WRITTEN, "note": NOTE},
        refund_id=str(refund_id),
    )
    assert answered.status_code == 403


# ══ 4 · WHAT SQLITE CANNOT PROVE (hard-won law 14) ═══════════════════════════


def test_cr141__sqlite_proves_nothing_about_the_trigger(brazos, marcus, dana):
    """The limit, STATED rather than left to be discovered.

    On the default tier a raw rewrite of the check number SUCCEEDS — there is no
    trigger — so every database-half proof below had to run on PostgreSQL.
    """
    if connection.vendor == "postgresql":
        pytest.skip("this case documents the SQLite tier; the PostgreSQL ones follow")
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        models.Refund.objects.filter(pk=refund_id).update(reference="99999")
        assert models.Refund.objects.get(pk=refund_id).reference == "99999", (
            "SQLite has no triggers, so the freeze is INVISIBLE here — that is law 14"
        )


# ══ 5 · THE FOUR PROOFS ON POSTGRESQL ════════════════════════════════════════


def _open_window(refund_id):
    """Open the correction window the way `refunds.correct_refund_reference` does."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config(%s, %s, true)", [refunds.CORRECTION_WINDOW_GUC, str(refund_id)]
        )


def _refused(sql, params):
    """Run one statement in a SAVEPOINT and return the database's refusal.

    ⚠ The savepoint is load-bearing: on PostgreSQL a failed statement poisons
    the whole transaction, so without it the NEXT query — `tenant_ctx` resetting
    `app.tenant_id` on the way out — raises in teardown (hard-won law 14,
    biting its own proof).
    """
    with pytest.raises(DatabaseError) as refused, transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
    return str(refused.value)


@requires_postgres
def test_cr141__pg_proof_i_the_door_corrects_and_audit_log_holds_both(
    brazos, marcus, dana, audit_reaches_the_table
):
    """PROOF (i) — through the endpoint, past the REAL trigger, into the REAL table.

    #10214 → #10241 succeeds, and `audit_log` — the table, read back with the
    ORM, not the capture list — holds BOTH numbers on one row.
    """
    from apps.audit.models import AuditLog

    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
    answered = _post(
        refunds_api.refund_correct_reference,
        brazos,
        actor=marcus,
        data={"reference": CHECK_WRITTEN, "note": NOTE},
        refund_id=str(refund_id),
    )
    assert answered.status_code == 200, answered.data
    with tenant_ctx(brazos):
        assert models.Refund.objects.get(pk=refund_id).reference == CHECK_WRITTEN
        rows = list(
            AuditLog.objects.filter(action=refunds.AUDIT_REFERENCE_CORRECTED, entity_id=refund_id)
        )
        assert len(rows) == 1
        assert rows[0].before == {"reference": CHECK_TYPED}
        assert rows[0].after["reference"] == CHECK_WRITTEN
        assert rows[0].after["note"] == NOTE


@requires_postgres
def test_cr141__pg_proof_ii_any_other_write_of_the_number_is_refused(brazos, marcus, dana):
    """PROOF (ii) — the column is NOT thrown open; only the window opens it.

    Three shapes of "any other write", because each is a real way a lane or a
    repair script reaches the row: a raw statement, a bulk ORM update, and an
    ordinary model save. And a fourth that is subtler: a window open for a
    DIFFERENT refund does not open this one — the window carries an id, and
    the trigger compares it with the row's own.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        other_id = uuid.uuid4()

        raw = _refused("UPDATE refunds SET reference = %s WHERE id = %s", ["10241", str(refund_id)])
        assert "written once" in raw
        assert "POST /refunds/{id}/correct-reference" in raw

        with pytest.raises(DatabaseError), transaction.atomic():
            models.Refund.objects.filter(pk=refund_id).update(reference=CHECK_WRITTEN)

        with pytest.raises(DatabaseError), transaction.atomic():
            row = models.Refund.objects.get(pk=refund_id)
            row.reference = CHECK_WRITTEN
            row.save(update_fields=["reference", "updated_at"])

        with transaction.atomic():
            _open_window(other_id)
            elsewhere = _refused(
                "UPDATE refunds SET reference = %s WHERE id = %s", ["10241", str(refund_id)]
            )
        assert "written once" in elsewhere

        assert models.Refund.objects.get(pk=refund_id).reference == CHECK_TYPED


@requires_postgres
@pytest.mark.parametrize(
    "assignment, named",
    [
        ("amount = 100.00", "amount"),
        # A BEFORE trigger fires ahead of the foreign-key check, so an id that
        # names no account is refused for the right reason: it is not the
        # refund's own.
        ("account_id = '019ff23d-13ee-7aba-a280-58058e492cb9'", "account_id"),
        ("method = 'ach'", "method"),
        ("status = 'cleared'", "status"),
    ],
)
def test_cr141__pg_proof_iii_the_window_moves_the_number_and_nothing_else(
    brazos, marcus, dana, assignment, named
):
    """PROOF (iii), the DATABASE half — inside the correction window itself.

    The window is the one lawful way to move `reference`, so it is the one place
    a widening would hide. Each money column is tried ALONE and ALONGSIDE a
    lawful check-number change, and both are refused with the column named.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        before = models.Refund.objects.get(pk=refund_id)
        for sql in (
            f"UPDATE refunds SET {assignment} WHERE id = %s",
            f"UPDATE refunds SET reference = '10241', {assignment} WHERE id = %s",
        ):
            with transaction.atomic():
                _open_window(refund_id)
                message = _refused(sql, [str(refund_id)])
            assert "nothing else" in message, message
            assert named in message, message
        after = models.Refund.objects.get(pk=refund_id)
        assert (after.reference, after.amount, after.account_id, after.method, after.status) == (
            before.reference,
            before.amount,
            before.account_id,
            before.method,
            before.status,
        )


@requires_postgres
def test_cr141__pg_proof_iii_the_door_refuses_money_fields_on_postgres(brazos, marcus, dana):
    """PROOF (iii), the DOOR half, on the real database: nothing is written."""
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
    for field, value in (
        ("amount", "100.00"),
        ("account_id", str(uuid.uuid4())),
        ("method", "ach"),
    ):
        answered = _post(
            refunds_api.refund_correct_reference,
            brazos,
            actor=marcus,
            data={"reference": CHECK_WRITTEN, "note": NOTE, field: value},
            refund_id=str(refund_id),
        )
        assert answered.status_code == 409, (field, answered.data)
        assert field in answered.data["params"]["detail"]
    with tenant_ctx(brazos):
        row = models.Refund.objects.get(pk=refund_id)
        assert row.reference == CHECK_TYPED
        assert row.amount == REFUND_AMOUNT


@requires_postgres
def test_cr141__pg_proof_iv_no_number_yet_is_refused_at_both_layers(brazos, marcus, dana):
    """PROOF (iv) — an approved refund has no check number; nothing corrects one.

    At the door, in words a clerk can act on. And at the database, inside an
    open window, so a caller that skipped the service still cannot use the
    correction window to write the FIRST number — that is the issue act's.
    """
    with tenant_ctx(brazos):
        _account, refund_id = an_approved_refund(brazos, marcus, dana)
    answered = _post(
        refunds_api.refund_correct_reference,
        brazos,
        actor=marcus,
        data={"reference": CHECK_WRITTEN, "note": NOTE},
        refund_id=str(refund_id),
    )
    assert answered.status_code == 409, answered.data
    assert "no check number yet" in answered.data["params"]["detail"]
    with tenant_ctx(brazos):
        with transaction.atomic():
            _open_window(refund_id)
            message = _refused(
                "UPDATE refunds SET reference = %s WHERE id = %s", ["10241", str(refund_id)]
            )
        assert "no check number yet" in message
        assert models.Refund.objects.get(pk=refund_id).reference is None


@requires_postgres
def test_cr141__pg_a_refund_still_cannot_be_deleted(brazos, marcus, dana):
    """The half of `0006`'s freeze a whole-body restatement could drop by accident."""
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        with transaction.atomic():
            _open_window(refund_id)
            message = _refused("DELETE FROM refunds WHERE id = %s", [str(refund_id)])
        assert "cannot be removed" in message
        assert models.Refund.objects.filter(pk=refund_id).exists()


@requires_postgres
def test_cr141__pg_the_window_does_not_outlive_the_correction(brazos, marcus, dana):
    """The service SHUTS the window before it returns.

    A window left open for the rest of the transaction would turn the next
    statement against the same refund — in the same request — into a lawful
    rewrite. Asserted by trying one straight after a successful correction.
    """
    with tenant_ctx(brazos):
        _account, refund_id = dana_sends_it_as_10214(brazos, marcus, dana)
        with transaction.atomic():
            _correct(refund_id, actor=dana)
            message = _refused(
                "UPDATE refunds SET reference = %s WHERE id = %s", ["55555", str(refund_id)]
            )
        assert "written once" in message
        assert models.Refund.objects.get(pk=refund_id).reference == CHECK_WRITTEN


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-PAY-12614 (CLOSED 2026-09-23, option b) · 12-governance/02-decision-log.md
#         2026-09-23 "SIGNED: A REFUND'S CHECK NUMBER MAY BE CORRECTED" ·
#         apps/payments/migrations/0041 (the body this restates) · 0014 and
#         amendments.py (the payment precedent) · CLAUDE.md hard rule 4, law 14
# generated: 2026-09-23 by lane REFUND-CORRECT
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
