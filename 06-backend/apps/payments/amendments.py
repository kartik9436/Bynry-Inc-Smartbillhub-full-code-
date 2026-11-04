# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-34 · task 41 — "Correct what is not money". The CR's own
#           words: *"A mistyped cheque number changes nothing financial and
#           cannot be fixed. It is the smallest item here and it has a real
#           cost: the reference is what a bank line is matched on, so a wrong
#           one is an unmatched line and a reconciliation nobody can finish."*
# Story:    US-PAY-004 (the payment record this corrects) · US-PAY-020/023
#           (bank reconciliation, which matches on the reference)
#           Screens: S35 (the "Correct reference" modal) · S21 (the Payments
#           tab, where a corrected reference shows AS CORRECTED)
# Rules:    CLAUDE.md hard rule 4 + BR-PAY-002 (a payment past `processing`
#           accepts NO UPDATE and NO DELETE, ever — corrections are new rows) ·
#           hard rule 7 (every money action writes `audit_log`) · hard rule 1
#           (tenant scoping) · BR-PAY-025 (batches group by day × tender) ·
#           BR-PAY-004 (a reconciled batch is LOCKED) · BR-SHL-020 (a refusal a
#           human can act on)
# Ruling:   OQ-1322 CLOSED 2026-09-02 (option a). PO verbatim: *"(a) Allow those
#           fields to change"*. CLAUDE.md hard rule 4 is NARROWED for three
#           columns — `confirmation`, `memo`, `method_id` — and for nothing else.
# Ruling:   OQ-1340 CLOSED 2026-09-23 (option b) — a correction's audit row is
#           pruned like any other. PO verbatim: *"keep the same rule s; when
#           audit log is delete - it is deleted thats okay"*. So `audit_log` has
#           ONE retention rule and NO row type is exempt, and the prohibition is
#           now PERMANENT rather than provisional: nothing may call this path a
#           permanent record of the old value, EVER.
# Tests:    06-backend/tests/test_cr059_cs34_amend_reference.py
# Impacts:  apps/payments/amendments_api.py (the named route) · config/urls.py ·
#           apps/payments/migrations/0014_cr059_cs34_amendable_reference.py
# ───────────────────────────────────────────────────────
"""CS-34 — correcting a cheque number, and the rule that stands in the way.

**WHAT CS-34 ASKS FOR.** A mistyped cheque number is not money and cannot be
fixed today. Its cost is real: the reference is what a bank line is matched on,
so a wrong one is an unmatched line and a reconciliation nobody can finish. The
same applies to a memo and to a payment recorded under the wrong tender. The
spec's two new rules, in its own sentences:

  * *"The reference and memo may be amended; the amount, the account, both dates
    and the allocations may never be. Every amendment writes an audit row
    carrying the old value and the new."*
  * *"The tender may not be amended once the payment has been swept into a
    deposit batch, because batches group by day and tender: changing it would
    move the payment between two batches, one of which may be reconciled and
    locked."*

    ⚠ AMENDED 2026-09-22 (`P0.6`): a batch is one TILL and one tender, not one day and one tender. The TENDER half is unchanged, so this refusal still fires; only its stated reason moved.

And its backend note, which THIS FILE IMPLEMENTS IN FULL: *"Deliberately NOT a
PATCH on the payment resource. The rule that there is no edit verb on a payment
path is load-bearing and should stay absolute — a route that accepts a partial
body invites the next field to be added to it. Instead a named endpoint that
accepts only these fields and nothing else, so what can be amended is visible in
the route rather than enforced inside it."*

═══════════════════════════════════════════════════════════════════════════════
⚠ THE COLLISION, AND HOW THE PRODUCT OWNER RESOLVED IT
═══════════════════════════════════════════════════════════════════════════════
**CLAUDE.md hard rule 4 forbade the UPDATE that "amend" means**, and it was
never a convention this module could reinterpret — it is a database trigger, and
this was its refusal QUOTED FROM A REAL POSTGRESQL RUN rather than read off a
migration:

    psycopg.errors.RaiseException: BR-PAY-002 / hard rule 4: payment
      PY-260808-0001 is cleared and is append-only — no column may change
      except the deposit batch it is banked in (BR-PAY-025) and the journal
      entry it posted (US-PAY-009), each once. A reversal, an NSF and a reapply
      are all NEW rows. Changed: confirmation
    CONTEXT: PL/pgSQL function payments_payment_immutable() line 23 at RAISE

**`OQ-1322` CLOSED 2026-09-02 — PO verbatim: *"(a) Allow those fields to
change"*.** The lane recommended (b), a new append-only `payment_amendments`
table, on the ground that *a correction is a new row* is what hard rule 4
already says a correction IS. **The PO chose (a). It is built as ruled and not
re-argued**, and the recommendation is recorded here because the reasoning does
not vanish with the vote.

**WHAT WAS NARROWED, STATED AND NOT ASSUMED.** CLAUDE.md hard rule 4: *"no
UPDATE/DELETE on issued invoices, invoice lines, payments, journal entries —
corrections are new rows."* **The narrowing is exactly three columns —
`confirmation`, `memo`, `method_id` — and the rule stands unchanged for every
other column and every other table it names.** `payments/0014` is the only place
the allow list moves; DELETE is still refused in every status, and the
whole-row comparison still freezes a column added tomorrow. CLAUDE.md carries
the amendment in the same commit, because a hard rule narrowed in code and not
in CLAUDE.md is the divergence that cost eleven days on `BR-RAT-088`.

⚠ **THE COST THE PO ACCEPTED TWICE, AND `OQ-1340` IS NOW CLOSED ON IT.** With
the value changed in place, **the previous cheque number lives ONLY in
`audit_log`, and this product prunes that on a retention schedule** — so a
customer quoting a cheque number from two years ago becomes unfindable by
design. That was put before the `OQ-1322` ruling and the ruling was made anyway.
**Whether a reference-amendment audit row is EXEMPT from pruning was then minted
as `OQ-1340` and put to the PO on 2026-09-23 with the worked case and a
recommendation to EXEMPT it — and they ruled the other way**: *"keep the same
rule s; when audit log is delete - it is deleted thats okay"*. **It is pruned
like any other row.** So the prohibition stops being provisional: **nothing in
this repository may describe this path as a permanent record of the old value —
not *until it is answered*, but EVER** — which is why the response below still
carries that fact in `unavailable[]`.

⚠ **AND THE HONEST BUILD ON A SCREEN IS SILENCE, NOT A DISCLAIMER.** B14 rule 33
puts RATIONALE at **zero words on screen**, so the correction screen says nothing
at all about how long the old value survives; it simply never claims permanence.
A screen that explains the retention policy in order to be honest breaks rule 33
while trying to obey this ruling. **This `unavailable[]` entry is a MACHINE fact
for a caller to reason about, and it was never a string to render** —
`CorrectionRetentionNote`, the component that DID render it in all eleven
languages, is deleted in this same commit (`P3.18`).

⚠ **AND THE NAIVE VERSION WOULD HAVE PASSED EVERY TEST IN THIS REPOSITORY.**
Those triggers exist on **PostgreSQL only** and `config/settings/test.py`
hardcodes in-memory SQLite. So a bulk ORM write of a payment's `confirmation` is
green on the whole suite, on every machine, **and raises on the first real cheque
unless `payments/0014` has run**. That is CLAUDE.md law 14's trap exactly, one
module along from where it was learned, and it is why the write below was proved
against a live PostgreSQL 16 cluster before it was trusted — see the test file's
`requires_postgres` cases.

═══════════════════════════════════════════════════════════════════════════════
WHAT THIS PATH DOES, IN ORDER
═══════════════════════════════════════════════════════════════════════════════
  * the **named endpoint**, so what may be amended is visible in the route
    (`amendments_api.py`) — deliberately not a PATCH;
  * **every money field refused BY NAME** — CS-34's first proof: a body carrying
    `amount`, `account_id`, `posted_at`, `cleared_at` or `allocations` is
    refused with that field named, before anything else runs;
  * the **tender-once-batched refusal** — CS-34's second new rule, refused in
    the service with the batch NAMED and refused again by the trigger for
    whoever bypasses the service;
  * the **required note**;
  * the **write**, and the **audit row** carrying the old value and the new,
    in ONE transaction — hard rule 7, and the trail is the control this
    correction depends on, so a corrected row without its audit row must not be
    reachable.
"""

from typing import Any

from django.db import transaction

from apps.payments import bankrec_models as bankrec
from apps.payments import models
from apps.payments.exceptions import PaymentRuleError
from core import audit, errors
from core import tenancy as core_tenancy

#: The question that AUTHORISES this write, CLOSED by the PO on 2026-09-02 with
#: *"(a) Allow those fields to change"*. One constant so the docstring, the
#: migration and the tests cite the same id.
OQ_AMEND_MECHANISM = "OQ-1322"

#: The question the `OQ-1322` ruling left open, CLOSED by the PO on 2026-09-23
#: with *"keep the same rule s; when audit log is delete - it is deleted thats
#: okay"* — option (b) of three, chosen AGAINST the recommendation. A
#: correction's audit row is pruned like any other: `audit_log` has ONE
#: retention rule and no row type is exempt from it.
OQ_AMENDMENT_RETENTION = "OQ-1340"

#: ⚠ **RENAMED 2026-09-23 (`P3.18`) — IT WAS `amendment_history_retention_unruled`
#: AND THE RETENTION IS NO LONGER UNRULED.** Carried on every successful
#: correction response, so the old name was a live string asserting that a
#: decision had not been taken hours after it was taken. **A key named `_unruled`
#: for a thing that is now ruled is the stale-pointer rot this repository files
#: most**, so it is RENAMED rather than merely reworded — a reader who greps the
#: name must not land on a word that lies about the state of the world.
#:
#: ⚠ **THE FACT IT CARRIES DID NOT CHANGE — ONLY ITS CERTAINTY DID.** Before the
#: ruling this said *"has not been decided"*; now it says the row IS pruned. Both
#: sentences forbid the same thing, which is why the entry stays on
#: `unavailable[]` instead of leaving it: what is unavailable is a PERMANENT
#: RECORD of the replaced value, and that is now permanently true rather than
#: provisionally so.
#:
#: ⚠ **IT IS A MACHINE FACT AND NOT A STRING TO RENDER.** B14 rule 33 puts
#: rationale at zero words on screen, so no screen may turn this into a
#: disclaimer; the honest build is silence. `CorrectionRetentionNote` — the
#: component that DID render it, in all eleven catalogues — is deleted in the
#: same commit as this rename.
AMENDMENT_RETENTION_GAP: dict[str, Any] = {
    "code": "amendment_history_is_not_a_permanent_record",
    "br_ref": f"{OQ_AMENDMENT_RETENTION} · CS-34",
    "detail": "the value this correction replaced is now recorded in the audit trail and "
    "nowhere else, and audit rows are removed on a retention schedule. A correction's audit "
    "row is pruned on that schedule like any other, so this correction must not be relied on "
    "as a permanent record of the previous value.",
}

#: CS-34's own list, verbatim: *"the amount, the account, both dates and the
#: allocations may never be [amended]"*. Named as DATA and refused BY NAME,
#: which is what CS-34's proof asks for — *"every money field refused by
#: name"* — rather than being enforced by the silent absence of a branch.
#:
#: ⚠ **`payment_no`, `currency`, `purpose`, `type` and `status` are here too**
#: even though CS-34 does not list them. CS-34 names what MAY be amended and
#: says the rest never may; a list that enumerated only the five it happened to
#: mention would let the sixth through on the day somebody sent it, which is
#: the *"a route that accepts a partial body invites the next field to be added
#: to it"* failure the spec is written to prevent — one layer in.
FORBIDDEN_FIELDS = (
    "amount",
    "account_id",
    "account",
    "posted_at",
    "cleared_at",
    "allocations",
    "payment_no",
    "currency",
    "purpose",
    "type",
    "status",
    "webhook_key",
    "idempotency_key",
    "journal_entry_id",
    "deposit_batch_id",
    "reverses_payment_id",
)

#: The three fields CS-34 DOES allow, plus the note it requires. Anything else
#: in the body is refused: an unknown field is a caller mistake or a rename, and
#: silently ignoring one is how a clerk comes to believe a correction landed.
AMENDABLE_FIELDS = ("reference", "memo", "tender_id")

AUDIT_ACTION = "payment.reference_amended"


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _payment(tenant_id: Any, payment_id: Any) -> models.Payment:
    """This tenant's payment, or a refusal that does not leak another's.

    HR-1: an unknown id, a malformed id and a cross-tenant id all read the same
    way, because distinguishing them would tell a caller that somebody else's
    payment exists.
    """
    try:
        payment = models.Payment.objects.filter(tenant_id=tenant_id, pk=payment_id).first()
    except (ValueError, TypeError):  # a malformed id is a caller mistake
        payment = None
    if payment is None:
        raise PaymentRuleError(
            f"payment {payment_id!r} is not one of this tenant's payments, so there is "
            "nothing to correct (CLAUDE.md rule 1). Nothing is written.",
            br_ref="BR-PAY-002",
        )
    return payment


def _tender(tenant_id: Any, tender_id: Any) -> Any:
    """This tenant's ACTIVE payment method for an id, or a refusal naming why.

    ⚠ **A WRITE PATH MUST RESOLVE WHAT IT IS ABOUT TO STORE.** `method_id` is a
    foreign key, so an id that names nothing would be caught by PostgreSQL as a
    constraint violation and by SQLite as nothing at all — a dangling tender on
    every payment corrected through the default suite. The refusal is the
    service's, in words, before either database is asked.

    A DEACTIVATED method is refused for `services._method`'s reason, run one
    step further: IS-1 deactivates rather than deletes, and a tenant that
    retired a method has said stop using it — correcting a payment ONTO one
    would put a retired tender on a live row.

    The lookup model is reached through `Payment.method` itself — the REVIEWED
    cross-module FK (B2 §2) this function is about to write — rather than by
    importing tenancy. Same destination as `services._method`'s named resolve,
    and it cannot drift from the column being set.
    """
    lookup = models.Payment._meta.get_field("method").remote_field.model
    try:
        row = lookup.objects.filter(tenant_id=tenant_id, pk=tender_id, active=True).first()
    except (ValueError, TypeError):  # a malformed id is a caller mistake
        row = None
    if row is None:
        raise PaymentRuleError(
            "that tender is not one of this tenant's active payment methods, so the "
            "correction would leave the payment pointing at nothing. Pick a method from the "
            "list; a method that has been deactivated is one the utility has said stop using.",
            br_ref="BR-PAY-026",
        )
    return row


def refuse_money_fields(body: dict[str, Any]) -> None:
    """CS-34's first proof — *"every money field refused BY NAME"*.

    Refused BEFORE anything is read or written, and named in the refusal so a
    clerk (or the developer wiring the modal) is told which field is the
    problem rather than being handed a generic rejection.

    **This is the half of CS-34 that is load-bearing and buildable today.** The
    spec's argument for a named endpoint is that *"a route that accepts a
    partial body invites the next field to be added to it"*; this function is
    that argument made checkable, so the invitation is refused in code rather
    than in a comment.
    """
    offenders = [name for name in FORBIDDEN_FIELDS if name in body]
    if offenders:
        raise PaymentRuleError(
            f"a payment's {', '.join(offenders)} can never be corrected. Money that was "
            "handed over is financial history: the amount, the account, both dates and the "
            "allocations are frozen from the moment the row exists, and a correction to any "
            "of them is a REVERSAL plus a new payment, never an edit (CLAUDE.md hard rule 4). "
            "Only the reference, the memo and the tender may be corrected here.",
            br_ref="BR-PAY-002",
        )
    unknown = [
        name
        for name in body
        if name not in AMENDABLE_FIELDS and name not in ("note", "idempotency_key")
    ]
    if unknown:
        raise PaymentRuleError(
            f"this correction does not accept {', '.join(sorted(unknown))}. It accepts the "
            "reference, the memo, the tender and a note saying why — and nothing else, so "
            "what can be corrected is visible in the route rather than hidden inside it.",
            br_ref="BR-PAY-002",
        )


def refuse_tender_change_once_batched(payment: models.Payment) -> None:
    """CS-34's second new rule, and it needs no write to be true.

    *"The tender may not be amended once the payment has been swept into a
    deposit batch, because batches group by day and tender: changing it would
    move the payment between two batches, one of which may be reconciled and
    locked."*

    ⚠ AMENDED 2026-09-22 (`P0.6`): a batch is one TILL and one tender, not one day and one tender. The TENDER half is unchanged, so this refusal still fires; only its stated reason moved.

    The refusal names the BATCH and its state, because those are the two facts
    that tell a clerk what to do next: an in-transit batch can be re-cut after
    the payment is taken out of it; a reconciled one is locked by trigger
    (BR-PAY-004) and unreconciling is a deliberate, recorded act.
    """
    if payment.deposit_batch_id is None:
        return
    batch = bankrec.DepositBatch.objects.filter(
        tenant_id=payment.tenant_id, pk=payment.deposit_batch_id
    ).first()
    # `DepositBatch.code` — `DEP-260808-CHK`, the LABEL a clerk reads on S39.
    # Not `id`: B14 rule 31 forbids a database id being the visible value of a
    # field, and this string reaches a refusal a clerk is shown.
    where = batch.code if batch is not None and batch.code else None
    locked = batch is not None and batch.status == bankrec.BATCH_RECONCILED
    raise PaymentRuleError(
        "the tender cannot be corrected once this payment has been banked"
        + (f" — it is in deposit {where}" if where else "")
        + (
            ". That batch is reconciled and locked, so the money has been tied to a bank "
            "statement; unreconcile it first if the tender really is wrong."
            if locked
            else ". Deposits are grouped by day and tender, so changing the tender would move "
            "this payment into a different batch. Take it out of the batch first."
        ),
        br_ref="BR-PAY-025",
    )


def amend_reference(
    actor: Any,
    *,
    payment_id: Any,
    note: str,
    reference: str | None = None,
    memo: str | None = None,
    tender_id: Any = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """`POST /payments/{id}/correct-reference` — CS-34's named endpoint.

    Every validation CS-34 asks for runs here, and since the PO's ruling of
    2026-09-02 (`OQ-1322`, option a) so does the write: `confirmation`, `memo`
    and `method_id` are the three columns CLAUDE.md hard rule 4 is narrowed for,
    and `payments/0014` is what makes the UPDATE lawful at the database.

    ⚠ **THE ORDER IS DELIBERATE AND IS PART OF THE SPEC.** The refusals come
    FIRST, so a body carrying an amount is refused as an amount and never
    reaches the write — the one thing CS-34's proof asks for by name.

    ⚠ **THE UPDATE AND THE AUDIT ROW ARE ONE TRANSACTION.** Hard rule 7 owes an
    audit row for a money action that happened, and the trail is the ONLY place
    the previous value now lives, so a corrected row without its audit row must
    not be reachable — not by an exception, not by a partial commit. The shape
    is composed BEFORE the update because `before` is read off the row as it
    stands; composing it afterwards would record the new value twice.

    ⚠ **THE WRITE IS `save(update_fields=…)` AND NOT A BULK ORM WRITE, AND THAT
    IS DELIBERATE TWICE OVER.** It names exactly the columns that may move, so a
    field added to this function later has to be named here to be written at
    all; and it goes through the model, which is where `updated_at`'s `auto_now`
    lives — so the "last changed" stamp moves with the correction without this
    money path ever reading a clock (BR-TEN-043). The bulk path would do
    neither. **Tenant scoping is the row's own** (CLAUDE.md rule 1): the
    instance came from `_payment`, which filters on `tenant_id`, so this cannot
    reach another tenant's payment — and RLS `FORCE` backs that up on the only
    database where it matters.
    """
    body = dict(body or {})
    refuse_money_fields(body)

    if not (note or "").strip():
        raise PaymentRuleError(
            "a correction needs a note saying why. The reference is what a bank line is "
            "matched on, so changing one changes which payment a bank statement ties to — "
            "and a month later nobody remembers why it moved.",
            br_ref="BR-PAY-002",
        )
    if reference is None and memo is None and tender_id is None:
        raise PaymentRuleError(
            "nothing was given to correct. Send the reference, the memo or the tender.",
            br_ref="BR-PAY-002",
        )

    tenant_id = _tenant_id()
    payment = _payment(tenant_id, payment_id)
    method = None
    if tender_id is not None:
        refuse_tender_change_once_batched(payment)
        method = _tender(tenant_id, tender_id)

    shape = audit_shape(payment, reference=reference, memo=memo, tender_id=tender_id, note=note)

    columns: list[str] = []
    for column, value in (
        ("confirmation", reference),
        ("memo", memo),
        ("method_id", None if method is None else method.pk),
    ):
        if value is not None:
            setattr(payment, column, value)
            columns.append(column)

    with transaction.atomic():
        # `updated_at` rides along so the model's own `auto_now` stamps it —
        # Django writes an `auto_now` column only when it is named here.
        payment.save(update_fields=[*columns, "updated_at"])
        write_audit(actor, shape)

    return {
        # The payment's own NUMBER is what a clerk reads (B14 rule 31); the id
        # rides alongside so the screen can navigate, never as a shown value.
        "payment_id": str(payment.pk),
        "payment_no": payment.payment_no,
        "corrected": {key: value for key, value in shape["after"].items() if key != "note"},
        "previous": dict(shape["before"]),
        "note": note,
        # ⚠ The previous value now lives only in the audit trail, and `OQ-1340`
        # is CLOSED: that row is pruned on the ordinary schedule like any other
        # (PO, 2026-09-23). Carried on the RESPONSE so a CALLER can reason about
        # it — never so a screen can print it, which B14 rule 33 forbids.
        "unavailable": [dict(AMENDMENT_RETENTION_GAP)],
    }


def audit_shape(
    payment: models.Payment,
    *,
    reference: str | None,
    memo: str | None,
    tender_id: Any,
    note: str,
) -> dict[str, Any]:
    """The audit row CS-34 requires, as a value rather than as a promise.

    *"Every amendment writes an audit row carrying the old value and the new."*
    Built as a value rather than inline at the write site so the tests can
    assert the shape directly: the OLD value and the NEW value, side by side,
    against the payment's own number.

    ⚠ **`before` CARRIES THE OLD VALUE AND IS NOW THE ONLY PLACE IT LIVES** —
    which is exactly the cost the PO accepted when they ruled option (a) on
    2026-09-02, and `OQ-1340` then asked whether this row at least survives
    pruning. **It does not** (PO, 2026-09-23, option b): `audit_log` has one
    retention rule and this row is inside it, so the old value is genuinely
    gone once the schedule reaches it.
    **Composed BEFORE the update**, because `before` is read off the row as it
    stands; composing it afterwards would record the new value twice.
    """
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    if reference is not None:
        before["confirmation"] = payment.confirmation
        after["confirmation"] = reference
    if memo is not None:
        before["memo"] = payment.memo
        after["memo"] = memo
    if tender_id is not None:
        before["method_id"] = None if payment.method_id is None else str(payment.method_id)
        after["method_id"] = str(tender_id)
    after["note"] = note
    return {
        "action": AUDIT_ACTION,
        "entity_type": "payments",
        "entity_id": str(payment.pk),
        "payment_no": payment.payment_no,
        "before": before,
        "after": after,
    }


def write_audit(actor: Any, shape: dict[str, Any]) -> dict[str, Any]:
    """Hard rule 7's writer for this path — inside the update's transaction.

    Kept beside `audit_shape` rather than inlined at the write site, so the two
    halves of the same obligation are read together and neither can be
    "simplified" away without the other becoming obviously pointless.
    """
    return audit.money_action(
        actor,
        shape["action"],
        shape["entity_type"],
        shape["entity_id"],
        before=shape["before"],
        after=shape["after"],
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §7 (how the module works today) · §8 CS-34 · §11 task 41 ·
#         12-governance/02-decision-log.md 2026-09-02 (OQ-1322 CLOSED, option a)
#         · apps/payments/migrations/0014_cr059_cs34_amendable_reference.py ·
#         CLAUDE.md hard rule 4 (NARROWED 2026-09-02) · hard-won law 14
# generated: 2026-09-02 by the CR-059 W7 correct-what-is-not-money lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(CR-059 task 42 owns S35's modal and S21's
#            corrected-value hover — and the control may now be ENABLED, which
#            it could not be while the write was stubbed) F✔ G✔
#            H=deferred(PO 2026-08-09)
# exceptions:
#   E1 THE WRITE NARROWS CLAUDE.md HARD RULE 4 for three columns —
#      `confirmation`, `memo`, `method_id` — on the PO's ruling of 2026-09-02
#      ("(a) Allow those fields to change"). The rule stands unchanged for every
#      other column and every other table it names, and CLAUDE.md carries the
#      amendment in the same commit.
#   E2 no PATCH, PUT or DELETE verb is added to any payment path, by design —
#      CS-34 says the absence of an edit verb is load-bearing and stays absolute.
#   E3 THE OLD VALUE NOW LIVES ONLY IN `audit_log`, WHICH IS PRUNED — and
#      OQ-1340 is CLOSED (PO 2026-09-23, option b): a correction's audit row is
#      pruned like any other. The fact rides on every successful response as
#      `amendment_history_is_not_a_permanent_record` for a CALLER to reason
#      about, and nothing in this repo calls the path a permanent record of the
#      old value. ⚠ It is not a string to render: B14 rule 33 puts rationale at
#      zero words on screen, so the honest build on the screen is SILENCE.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
