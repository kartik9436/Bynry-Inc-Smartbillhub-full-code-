# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-21 — *"make application fees optional - so that
#           we can approve it"* and *"waiving is options and can you fix the
#           issue here"*; corrected the same day by *"in practical this does
#           not ahppen - it is application fees - customer will pay it once or
#           clark will wavie it off - $20 or $0 - some utilities will not take
#           applciation fees also - so your scenario is hypotetical"*.
# Rules:    BR-CUS-090 (AMENDED 2026-09-21 — the shortfall is reported, not a
#           gate) · BR-CUS-073 (a waiver is an explicit act with a reason) ·
#           CLAUDE.md hard rule 2 (money 4 dp stored, 2 dp displayed) · hard
#           rule 4 (no UPDATE on an issued invoice — a fee line is not one and
#           says so) · hard rule 7 (audit_log on every money action) ·
#           hard rule 1 (tenant scoping)
# Defects:  DEF-CUS-6096 (waive is a silent 500) · DEF-CUS-6097 (the raw
#           `{{receiptNo}}` and its impossible advice) · DEF-CUS-5399 (the two
#           signed screens that disagreed about the gate)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**THE APPLICATION FEE IS `$20` OR `$0`, AND IT NEVER STOPS AN APPROVAL.**

⚠ **THE SECOND HALF OF THAT HEADLINE IS SUPERSEDED 2026-09-23 (`OQ-CUS-12617`
CLOSED, `DEF-CUS-6420`).** PO, verbatim: *"we already told you - either fee is
paid or waived - no other condition"*. **An unpaid fee stops the approval
again**, on the remainder: quoted $130.00, taken $25.00 → refused naming
$105.00. The three shapes below are unchanged and each is still the ordinary
path — paid in full approves, waived approves, no fee at all approves. What
flipped is the case that approved OVER an unpaid fee; it now asserts the
refusal, and it was flipped rather than deleted so the old rule cannot come
back quietly. The headline is left visible beneath this stamp so a reader who
followed it finds out it moved.

WHAT THE PO ACTUALLY DESCRIBED, AND IT RE-ORDERED THIS FILE
------------------------------------------------------------
The case we put to them was a clerk taking a PART payment and coming back for
the rest. Their answer: *"in practical this does not ahppen."* An application
fee is a small flat amount and there are **three shapes and only three**:

1. **paid once, in full** — `$20`, one payment, one receipt;
2. **waived** — and that path was a silent 500 (`DEF-CUS-6096`);
3. **the utility takes none at all** — `$0`, and nothing should ask for one.

So the part-paid case is still asserted here, because the product must not LOSE
a debt it has recorded — but it is the rarest of the three and it is not what
this file leads with.

WHAT WOULD MAKE THESE PASS WRONGLY — law 7's second habit
-----------------------------------------------------------
* **"The approval went through" is the easiest thing to fool.** A build that
  approves everything also approves this. So every positive case here asserts
  the MONEY AFTERWARDS: the outstanding figure is still read, still reported and
  still not a waiver once the request is approved. An approval that silently
  zeroed the fee would satisfy a naive version of these cases and is precisely
  what the ruling forbids.
* **The waive case could pass on a row that was already waived.** It asserts the
  row is NOT waived first, then waives, then reads the flag and the reason and
  the audit row back — three different places, because `waived = True` alone is
  a flag a bug could set.
* **The `line_no`-instead-of-`id` case could pass because the line number
  happens not to exist.** Line 1 DOES exist in that test — the refusal is proved
  against a line number that is real — so what is being asserted is that a line
  NUMBER is not an ADDRESS, not that an unknown row is refused.
* **The `$0` case could pass because nothing was configured at all.** That is
  the point and it is stated rather than assumed: `$0` in this product is *no
  fee line*, because **no tenant-level application-fee setting exists** (see
  the case that says so by name). A test that quietly invented one would be
  proving a product we do not have.

WHY THIS FILE IS NOT `_pg`
---------------------------
Nothing here catches a database error and continues, so hard-won law 14's trap
is not reachable: the counter receipt's posting is `test_cr094_counter_receipt_
posts.py`'s subject and is not re-proved here. The default in-memory SQLite run
is honest for every case below.
"""

from decimal import Decimal

import pytest

from core import errors

from apps.customers import models as customers_models
from apps.customers import service_request as rules
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from tests.fee_quote_helpers import quote_fee  # DEF-CUS-6416: the catalogue prices the line

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    dana,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

CAPTURE = {
    "channel": "counter",
    "applicant_kind": "person",
    "applicant_name": "Miller, Sarah",
    "applicant_email": "s.miller@example.test",
    "applicant_phone": "512-555-0142",
    "address_as_given": "212 Balcones Drive, Unit 3",
    "property_type": "standalone_owner_occupied",
    "what_they_said": "I want service at a new build",
}

DOC_ID = customers_models.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY


def _ready(actor, *, fee=None):
    """A request walked to the point the Approve modal opens on."""
    request = sr.create_request(actor, dict(CAPTURE))
    doc = sr.attach_document(
        actor, request.id, doc_type=DOC_ID, name="driving-licence.pdf", storage_ref="s3://id"
    )
    if fee is not None:
        quote_fee(
            actor,
            request.id,
            charge_code="CC-REQFEE",
            description="Application fee",
            unit_amount=fee,
        )
    sr.submit(actor, request.id)
    sr.resolve_address(actor, request.id)
    sr.link_customer(actor, request.id)
    sr.decide_outcome(actor, request.id, outcome="new_connection")
    sr.verify_document(actor, doc.id)
    return sr.request_row(request.id)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · SHAPE 3 — THE UTILITY THAT TAKES NO APPLICATION FEE
#     *"some utilities will not take applciation fees also"*
# ═══════════════════════════════════════════════════════════════════════════
def test_a_utility_that_takes_no_fee_meets_no_fee_gate_and_no_fee_refusal(brazos, dana):
    """**`$0` — and `$0` must be invisible, not merely harmless.**

    The whole path, with no fee line ever added: the totals are zero, the
    approval condition is CLEAR rather than merely non-blocking, nothing is
    refused, and the request approves.

    ⚠ **WHAT THIS CASE DOES NOT PROVE, STATED SO NOBODY READS IT WIDER.** It
    proves the GATE and the REFUSALS are absent. It does **not** prove the fee
    SCREEN is absent — the Fees panel, its `Record what was handed over` button
    and the `Application fee settled` row still render on a `$0` request today,
    and that is `DEF-CUS-6102`, filed rather than fixed, because hiding a panel
    needs a tenant setting that does not exist (the case below).
    """
    with tenant_ctx(brazos):
        request = _ready(dana, fee=None)

        totals = sr.fee_total_to_collect(request.id)
        assert totals["quoted"] == Decimal("0.0000")
        assert totals["collected"] == Decimal("0.0000")
        assert totals["outstanding"] == Decimal("0.0000")
        assert totals["receipt_no"] is None

        # CLEAR, not `blocked, blocking=False`. A utility with no fee has
        # nothing outstanding to be TOLD about either.
        fee = next(
            c for c in reads.conditions_for(sr.request_row(request.id)) if c.key == "fee_settled"
        )
        assert fee.state == rules.CONDITION_CLEAR
        assert fee.blocking is False
        assert fee.message_key is None

        conditions = reads.conditions_for(sr.request_row(request.id))
        assert "fee_settled" not in [c.key for c in rules.blocking_conditions(conditions)]
        assert "fee_settled" not in [c.key for c in rules.outstanding_conditions(conditions)]

        sr.approve(dana, request.id)
        assert sr.request_row(request.id).state == rules.APPROVED
        # Nothing appeared on the way through.
        assert not customers_models.ServiceRequestFee.objects.filter(request_id=request.id).exists()


def test_no_tenant_setting_exists_for_the_application_fee_and_that_is_stated(brazos, dana):
    """⛔ **A `$0` UTILITY CANNOT BE CONFIGURED — IT CAN ONLY BE ONE BY DEFAULT.**

    The PO's requirement is about a UTILITY (*"some utilities will not take
    applciation fees"*), and this product has no per-tenant application-fee
    setting at all: a fee exists on a request if and only if somebody called
    `add_fee_line` on that request. So `$0` is not a configured posture, it is
    the absence of an act — which means nothing can decide to hide a fee screen,
    because nothing knows the utility charges none.

    ⚠ **THE COMPARISON IS DELIBERATE AND IT IS IN THIS ASSERTION.**
    `BR-CUS-095`'s document checklist is exactly that missing shape, one table
    over: `ServiceRequestDocumentRequirement` is per `(request_type × doc_type)`,
    *"we ship with nothing ticked, and a utility that configures nothing blocks
    nothing"*. The fee has no equivalent. This case asserts the presence of the
    one and the absence of the other, so the day a fee setting is built it goes
    RED and names itself — rather than the gap living in a docstring nobody
    re-reads (hard-won law 1).
    """
    with tenant_ctx(brazos):
        # The precedent EXISTS …
        assert hasattr(customers_models, "ServiceRequestDocumentRequirement")
        assert callable(sr.required_document_types)

        # … and the fee has no counterpart. Named one by one rather than by a
        # pattern, because a pattern would go green on a rename.
        assert not hasattr(customers_models, "ServiceRequestFeeRequirement")
        assert not hasattr(sr, "required_fee_lines")
        assert not hasattr(sr, "tenant_application_fee")
        fee_fields = {f.name for f in customers_models.ServiceRequestFee._meta.get_fields()}
        assert "request" in fee_fields  # it is a per-REQUEST row …
        assert "request_type" not in fee_fields  # … and never a per-tenant rule

        # ⚠ **2026-10-06 (`DEF-CUS-9819`) — THE POSTURE NOW EXISTS, AS A PRICE
        # AND NOT AS A SWITCH.** PO: *"No - we wil ahve application fees as zero
        # and pprovide option to waive off"*. The utility marks ONE charge code
        # as its application fee and every new request gets its line; a $0
        # utility prices that code at $0.00. Still no Settings switch and no
        # per-request-type rule (asserted above) — the mark lives on the code.
        from apps.rating import models as rating_models

        charge_fields = {f.name for f in rating_models.Charge._meta.get_fields()}
        assert "is_application_fee" in charge_fields
        assert callable(sr.add_application_fee_line)


# ═══════════════════════════════════════════════════════════════════════════
# 2 · SHAPE 2 — WAIVING, WHICH WAS A SILENT 500 (DEF-CUS-6096)
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_6096_the_fees_payload_carries_the_row_id_the_waive_needs(brazos, dana):
    """**The whole defect, in one round trip.**

    The screen can only send what the payload gives it. Until 2026-09-21 the
    payload gave `line_no` and nothing else, so the row action sent `"1"` — and
    `POST .../fees/{fee_id}/waive` addresses the row by uuid. This asserts the
    id is served, that it is the ROW's id, and that it is accepted by the
    endpoint the screen actually calls.
    """
    with tenant_ctx(brazos):
        request = _ready(dana, fee=Decimal("20.00"))
        row = customers_models.ServiceRequestFee.objects.get(request_id=request.id)

        tab = reads.fees_tab(sr.request_row(request.id))
        (line,) = tab["lines"]
        assert line["id"] == str(row.id)
        assert line["line_no"] == 1  # still served — it is what the clerk reads

        # The id the payload serves is the id the waive takes.
        sr.waive_fee_line(dana, line["id"], reason="Waived at the counter")
        row.refresh_from_db()
        assert row.waived is True


def test_def_cus_6096_a_line_number_is_refused_cleanly_and_is_never_a_500(brazos, dana):
    """⚠ **THE SECOND LINE OF DEFENCE, AND IT IS THE HALF THAT WAS A 500.**

    Line 1 exists on this request, so what is being proved is that a line
    NUMBER is not an ADDRESS — not that an unknown row is refused. Before
    today, `filter(id="1")` raised `django.core.exceptions.ValidationError`
    inside the ORM, which is not one of our typed refusals: it left the API as
    a 500, the screen swallowed it, and the clerk pressed the button four more
    times.

    It is now the same 404 a row belonging to another tenant gets (`HR-1` — the
    boundary must not confirm what exists), which is a shape every screen in
    this product already knows how to render.
    """
    with tenant_ctx(brazos):
        request = _ready(dana, fee=Decimal("20.00"))
        row = customers_models.ServiceRequestFee.objects.get(request_id=request.id)
        assert row.line_no == 1  # the number the screen used to send IS real

        for not_an_id in ("1", "", "not-a-uuid", 1):
            # `deny_as_not_found` — a typed 404 the API renders, never a crash.
            # ⚠ Asserted as `NotFoundError` and NOT as "some exception": a bare
            # `Exception` here would go green on the very `ValidationError` this
            # case exists to refuse.
            with pytest.raises(errors.NotFoundError):
                sr.waive_fee_line(dana, not_an_id, reason="Waived at the counter")

        row.refresh_from_db()
        assert row.waived is False  # and nothing was touched on the way


def test_def_cus_6096_waiving_records_who_why_and_when_and_writes_the_audit_row(
    brazos, dana, audit_rows
):
    """*"A reason is required and recorded against your name"* (REQ-03.5), and
    **a money action writes `audit_log`** (CLAUDE.md hard rule 7).

    Asserted in three places rather than one, because `waived = True` alone is a
    flag any bug could set.
    """
    with tenant_ctx(brazos):
        request = _ready(dana, fee=Decimal("20.00"))
        row = customers_models.ServiceRequestFee.objects.get(request_id=request.id)
        assert row.waived is False

        with pytest.raises(errors.ValidationError):
            sr.waive_fee_line(dana, row.id, reason="   ")  # no reason, no waiver

        sr.waive_fee_line(dana, row.id, reason="Utility takes no application fee")
        row.refresh_from_db()
        assert row.waived is True
        assert row.waive_reason == "Utility takes no application fee"
        assert row.waived_by_id is not None
        assert row.waived_at is not None

        # ⚠ **THROUGH THE CAPTURE SINK, NOT THROUGH `AuditLog.objects`.**
        # `audit_rows` is this suite's BE-03 fixture and it REPLACES the sink,
        # so nothing reaches the table at all under test: a query against
        # `AuditLog` here answers *no row* for a row that was written, which is
        # a check that cannot tell pass from fail (law 7). Every other file in
        # this repo asserts a trail the same way, for the same reason.
        written = [r for r in audit_rows if r["action"] == "service_request.fee_waived"]
        assert len(written) == 1
        assert written[0]["entity_type"] == "service_request"
        assert written[0]["after"]["reason"] == "Utility takes no application fee"
        assert written[0]["before"]["waived"] is False

        # And the approval condition is CLEAR once the line is waived — a waived
        # line is not an outstanding fee (its own docstring's promise).
        totals = sr.fee_total_to_collect(request.id)
        assert totals["outstanding"] == Decimal("0.0000")
        fee = next(
            c for c in reads.conditions_for(sr.request_row(request.id)) if c.key == "fee_settled"
        )
        assert fee.state == rules.CONDITION_CLEAR


# ═══════════════════════════════════════════════════════════════════════════
# 3 · SHAPE 1 — PAID ONCE; AND THE GATE, WHICH FIRES AGAIN SINCE 2026-09-23
# ═══════════════════════════════════════════════════════════════════════════
def test_a_fee_paid_once_in_full_clears_the_condition_and_approves(brazos, dana):
    """`$20` quoted, `$20` taken, one receipt. The ordinary day."""
    with tenant_ctx(brazos):
        request = _ready(dana, fee=Decimal("20.00"))
        sr.collect_fee(
            dana, request.id, amount=Decimal("20.00"), method="cash", receipt_no="RCP-26-0001"
        )
        totals = sr.fee_total_to_collect(request.id)
        assert totals["outstanding"] == Decimal("0.0000")
        assert totals["receipt_no"] == "RCP-26-0001"

        fee = next(
            c for c in reads.conditions_for(sr.request_row(request.id)) if c.key == "fee_settled"
        )
        assert fee.state == rules.CONDITION_CLEAR

        sr.approve(dana, request.id)
        assert sr.request_row(request.id).state == rules.APPROVED


def test_an_unpaid_fee_stops_the_approval_by_name_and_is_never_a_waiver(brazos, dana):
    """⛔ **FLIPPED 2026-09-23 — THE FEE GATES APPROVAL AGAIN (`DEF-CUS-6420`).**

    This case was `test_an_unpaid_fee_is_reported_after_approval_and_is_never_a
    _waiver` and it approved a request over a `$20` fee nobody had paid. The PO
    ruled on 2026-09-23 that the fee is *"paid or waived - no other condition"*,
    so the name stated a rule the product no longer has and the case is
    rewritten rather than re-pointed (the same correction the document cases
    took on 2026-09-16).

    **What survives from the old case, and it is the half that mattered:** a
    refused press is still never a waiver and never a forgotten debt. The `$20`
    is still outstanding after the refusal, at 4 dp stored and 2 displayed, and
    no line was waived on the way.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** a refusal for some OTHER reason.
    So the refusal is asserted by its sentence key AND the figure it names — the
    `$20` — rather than as "some BizError".
    """
    with tenant_ctx(brazos):
        request = _ready(dana, fee=Decimal("20.00"))

        fee = next(
            c for c in reads.conditions_for(sr.request_row(request.id)) if c.key == "fee_settled"
        )
        assert fee.state == rules.CONDITION_BLOCKED
        assert fee.blocking is True  # ⛔ True again since 2026-09-23
        assert fee.params["amount"] == "20.0000"

        with pytest.raises(errors.BizError) as caught:
            sr.approve(dana, request.id)
        assert caught.value.message_key == "customers.serviceRequest.condition.feeOutstandingAmount"
        assert caught.value.params["amount"] == "20.0000"
        assert caught.value.params["condition"] == "fee_settled"
        assert sr.request_row(request.id).state != rules.APPROVED

        after = reads.fees_tab(sr.request_row(request.id))
        assert after["outstanding"]["display"] == "20.00"  # rule 2 — display 2
        assert after["outstanding"]["amount"] == "20.0000"  # rule 2 — store 4
        assert not customers_models.ServiceRequestFee.objects.filter(
            request_id=request.id, waived=True
        ).exists()

        # …and the WAIVER is the way out, which is the other half of the ruling.
        line = customers_models.ServiceRequestFee.objects.get(request_id=request.id)
        sr.waive_fee_line(dana, line.id, reason="Waived at the counter")
        sr.approve(dana, request.id)
        assert sr.request_row(request.id).state == rules.APPROVED


def _part_paid_before_the_ruling(request, *, taken, receipt_no):
    """**A request the counter part-paid BEFORE 2026-09-24 — data at rest.**

    `OQ-CUS-12624` (PO 2026-09-24, *"all or waived"*) refuses a short payment
    at the desk from today, so `collect_fee` can no longer MAKE this state.
    Rows written before the ruling still hold it, and the ruling says what
    happens to them: *"requests already part-paid keep what was taken"*. The
    columns are therefore written directly, exactly as the pre-ruling
    `collect_fee` left them, and no counter receipt is invented beside them —
    this file is about the approval gate and the waive, not the posting.
    """
    customers_models.ServiceRequest.objects.filter(id=request.id).update(
        fee_quoted=Decimal("130.0000"),
        fee_collected=taken,
        fee_currency="USD",
        fee_method="cash",
        fee_receipt_no=receipt_no,
    )
    return sr.request_row(request.id)


def test_def_cus_5399_part_paid_is_refused_on_the_remainder_and_a_waiver_releases_it(
    brazos, dana
):
    """**`BR-CUS-090`'s worked figure, on a request part-paid before 2026-09-24.**

    Quoted **$130.00**, **$25.00** taken at the counter before the desk began
    refusing a short payment (`OQ-CUS-12624`) → the approval is refused naming
    **$105.00** (stored `105.0000`, CLAUDE.md rule 2).

    Waiving the line releases it. ⚠ **A waiver is per LINE, so waiving the
    `$130.00` line leaves the `$25.00` the counter took with nothing quoted
    against it — `-25.00`, a cash overage finance reconciles** — and that is
    CLEAR, not a debt (`fee_total_to_collect`: *"`outstanding` IS SIGNED"*).
    """
    with tenant_ctx(brazos):
        request = _ready(dana, fee=Decimal("130.00"))
        _part_paid_before_the_ruling(request, taken=Decimal("25.0000"), receipt_no="RCP-26-4471")

        with pytest.raises(errors.BizError) as caught:
            sr.approve(dana, request.id)
        assert caught.value.message_key == "customers.serviceRequest.condition.feeOutstandingAmount"
        assert caught.value.params["amount"] == "105.0000"
        assert sr.request_row(request.id).state != rules.APPROVED

        line = customers_models.ServiceRequestFee.objects.get(request_id=request.id)
        sr.waive_fee_line(dana, line.id, reason="Settled at the counter next day")
        assert sr.fee_total_to_collect(request.id)["outstanding"] == Decimal("-25.0000")
        sr.approve(dana, request.id)
        assert sr.request_row(request.id).state == rules.APPROVED


def test_oq_cus_12624_a_short_payment_is_refused_and_the_whole_fee_is_taken(
    brazos, dana, audit_rows
):
    """**THE DESK TAKES THE WHOLE FEE OR NOTHING — `OQ-CUS-12624`, PO 2026-09-24.**

    PO, verbatim: *"all or waived"*. Quoted **$130.00**, **$25.00** offered →
    refused, naming the whole **$130.00** (stored `130.0000`), and NOTHING is
    written: no collected figure, no receipt number, no audit row. Then the
    whole **$130.00** is taken on the same receipt and the approval clears.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY (law 7):** a refusal raised AFTER
    the columns were written would still raise — so the row is read back and
    must hold no receipt, and the full payment on the SAME receipt number must
    then succeed rather than be refused as a second collection.
    """
    with tenant_ctx(brazos):
        request = _ready(dana, fee=Decimal("130.00"))
        with pytest.raises(errors.BizError) as caught:
            sr.collect_fee(
                dana, request.id, amount=Decimal("25.00"), method="cash", receipt_no="RCP-26-4471"
            )
        assert caught.value.message_key == "customers.serviceRequest.feeTakeInFull"
        assert caught.value.params["amount"] == "130.0000"
        assert caught.value.params["currency"] == "USD"
        assert caught.value.br_ref == "BR-CUS-090"
        row = sr.request_row(request.id)
        assert row.fee_receipt_no in (None, "")
        assert row.fee_collected is None
        assert not [r for r in audit_rows if r["action"] == "service_request.fee_collected"]

        # More than the fee is not "all" either — the same refusal, the same figure.
        with pytest.raises(errors.BizError) as over:
            sr.collect_fee(
                dana, request.id, amount=Decimal("150.00"), method="cash", receipt_no="RCP-26-4471"
            )
        assert over.value.message_key == "customers.serviceRequest.feeTakeInFull"
        assert over.value.params["amount"] == "130.0000"

        sr.collect_fee(
            dana, request.id, amount=Decimal("130.00"), method="cash", receipt_no="RCP-26-4471"
        )
        assert sr.fee_total_to_collect(request.id)["outstanding"] == Decimal("0.0000")
        sr.approve(dana, request.id)
        assert sr.request_row(request.id).state == rules.APPROVED


def test_def_cus_5399_taking_the_remainder_is_refused_and_only_a_waiver_releases_it(brazos, dana):
    """**FLIPPED 2026-09-24 (`OQ-CUS-12624`) — the strict xfail this replaces
    waited for the $105.00 remainder to be TAKEN; the PO ruled it is not.**

    It read *"Taking the $105.00 REMAINDER is refused today … this case goes
    RED (strict xfail) the day a second collection is accepted"*. PO, verbatim:
    *"p4 - i already calrified this - all or waived"* — so a request part-paid
    before the ruling **keeps what was taken and can only waive the rest**.
    Quoted $130.00, $25.00 taken on `RCP-26-4471` → the $105.00 on
    `RCP-26-4472` is refused as a second collection naming the first receipt;
    the waiver is the one way out, and it approves.
    """
    with tenant_ctx(brazos):
        request = _ready(dana, fee=Decimal("130.00"))
        _part_paid_before_the_ruling(request, taken=Decimal("25.0000"), receipt_no="RCP-26-4471")
        with pytest.raises(errors.BizError) as caught:
            sr.collect_fee(
                dana, request.id, amount=Decimal("105.00"), method="cash", receipt_no="RCP-26-4472"
            )
        assert caught.value.message_key == "customers.serviceRequest.feeAlreadyCollected"
        assert caught.value.params["receipt_no"] == "RCP-26-4471"
        assert sr.fee_total_to_collect(request.id)["outstanding"] == Decimal("105.0000")
        assert sr.request_row(request.id).fee_collected == Decimal("25.0000")

        line = customers_models.ServiceRequestFee.objects.get(request_id=request.id)
        sr.waive_fee_line(dana, line.id, reason="Rest waived at the counter")
        sr.approve(dana, request.id)
        assert sr.request_row(request.id).state == rules.APPROVED


# ═══════════════════════════════════════════════════════════════════════════
# 4 · DEF-CUS-6097 — THE PARAMETER AND THE SENTENCE THAT READS IT
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_6097_the_refusal_param_is_named_exactly_as_the_catalogue_reads_it(brazos, dana):
    """⚠ **A SILENT MISMATCH, WHICH IS THE ONLY KIND i18next PRODUCES.**

    The server passed `receipt_no`; all eleven catalogues interpolated
    `{{receiptNo}}`. i18next renders an unmatched placeholder VERBATIM rather
    than throwing, so there was no console error, no failing render and no
    failing check anywhere — a clerk simply read the word `{{receiptNo}}` on
    screen, four lines below the receipt number it was supposed to quote.

    This case is written against the PARAM NAME and the CATALOGUE TEXT
    together, because either one alone passes while the pair is broken. That is
    the whole shape of the defect.
    """
    import json
    from pathlib import Path

    with tenant_ctx(brazos):
        request = _ready(dana, fee=Decimal("20.00"))
        sr.collect_fee(
            dana, request.id, amount=Decimal("20.00"), method="cash", receipt_no="RCP-26-0001"
        )
        with pytest.raises(errors.BizError) as caught:
            sr.collect_fee(
                dana, request.id, amount=Decimal("20.00"), method="cash", receipt_no="RCP-26-9999"
            )

    key = "customers.serviceRequest.feeAlreadyCollected"
    assert caught.value.message_key == key
    assert caught.value.params["receipt_no"] == "RCP-26-0001"

    locales = (
        Path(__file__).resolve().parents[2] / "07-frontend" / "src" / "i18n" / "locales"
    )
    served = set(caught.value.params) | {"ref"}  # `ref` is the client's own
    for path in sorted(locales.glob("*.json")):
        sentence = json.loads(path.read_text(encoding="utf-8"))[key]
        placeholders = set(__import__("re").findall(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}", sentence))
        assert placeholders <= served, f"{path.name}: {placeholders - served} is filled by nobody"
        assert "receipt_no" in placeholders, f"{path.name} stopped quoting the receipt"

    # ⚠ **AND THE ADVICE IT USED TO GIVE WAS IMPOSSIBLE.** It read *"Record
    # further payment in Payments."* These fees never reach an account ledger —
    # `fees_tab` serves `posts_to_ledger: False`, and the open balance is the
    # request's OWN columns (`quoted − settled − collected`), which nothing in
    # Payments writes. A refusal that sends a clerk somewhere that cannot help
    # is worse than one that says nothing.
    english = json.loads((locales / "en.json").read_text(encoding="utf-8"))[key]
    assert "Payments" not in english
