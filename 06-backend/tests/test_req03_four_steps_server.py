# ── Trace ──────────────────────────────────────────────
# Change:  REQ-03 redrawn, SIX capture steps into FOUR — approved by the PO
#          2026-09-29. The specification is the five PNGs in
#          `05-prototype/new-request-four-steps-2026-09-29/`, read AS IMAGES
#          (B14 rule 42); the README beside them is an index, not the screen.
#          This file is the SERVER half: tasks 1–4 of 12.
# Rules:   PO 2026-09-21, verbatim: *"you ahve to show the error at step you
#          mentioned"* (`DEF-MET-6110`/`6111`, and `DEF-MET-7690` for the shape
#          of the fix) · PO 2026-09-29: *"use american english check = not
#          cheque"* · `BR-SHL-020` r2 (nothing English crosses the wire) ·
#          `BR-CUS-090` (the fee quote) · `BR-NOT-013` (nothing is sent) ·
#          CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money stored
#          at 4, displayed at 2, never multiplied in a browser) · hard-won
#          law 7 (a check whose false pass you cannot describe is a check you
#          do not understand) · hard-won law 14 (the default suite is SQLite)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""REQ-03's four steps, as the SERVER answers them.

════════════════════════════════════════════════════════════════════════════
WHAT EACH SECTION IS ACTUALLY GUARDING
════════════════════════════════════════════════════════════════════════════
**1 · A refusal lands on the step that now holds its field.** The wizard routes
on `params["step"]` and nothing else. A refusal with NO step leaves the clerk
where they are, which is survivable; a refusal with the WRONG step sends them
to a screen the named field is not on, which is worse than silence. Documents
moved 4 → 1, addresses 3 → 2, services 2 → 3, fees and the payment 5 → 3, and
every door is asserted BY VALUE.

**⚠ THE GUARD CASE IS THE ONE THAT MATTERS**, exactly as
`test_the_premise_steps_stamp_does_not_reach_a_refusal_from_elsewhere` is next
door: `on_step` must not relabel a refusal that already named its own step,
and it must not catch anything that is not a catalogue refusal. Widen it into
a blanket handler and those two cases go red instead of a clerk being sent to
the wrong screen.

**2 · The messages card tells the truth about a product that cannot send.**
Three on-submit rows, always three, and the two with no wording say so. The
false pass to fear here is a card that answers `[]` for a tenant with no
stored rows — which would look exactly like *nothing will be sent* — so the
count is asserted, not the emptiness.

**3 · The fee row and its total come from the SERVER.** `amount` is
`quantity × unit_amount` computed in the service, the drawn `Total` is served
as a rounded pair beside its stored value, and the currency is on every one of
them (`DEF-CUS-7806` is the defect for a bare `535.00`).

**4 · The tender reads and writes as `check`.** Both spellings go in; one
comes out.
"""

from decimal import Decimal

import pytest

from apps.customers import applicant_messages
from apps.customers import models as customers_models
from apps.customers import service_request_api as api
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from apps.customers import service_request_steps as steps
from apps.customers.applicant_message_models import ServiceRequestMessage
from apps.payments import counters
from apps.tenancy import published_content_models as content_models
from core import errors
from django.utils import timezone

from tests.fee_quote_helpers import quote_fee
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, lonestar, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Okonkwo, David",
    "applicant_email": "david@example.test",
    "address_as_given": "14 Willow Bend, Springfield",
}


def _make(actor, **overrides):
    return sr.create_request(actor, {**CAPTURE, **overrides})


def _post(view, request, path, **kwargs):
    return api_call(
        view,
        kwargs.pop("method", "post"),
        path,
        user=kwargs.pop("user"),
        role="system_admin",
        tenant=kwargs.pop("tenant"),
        data=kwargs.pop("data", None),
        request_id=str(request.id),
        **kwargs,
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · SIX STEPS BECAME FOUR, AND EVERY REFUSAL KNOWS WHICH ONE IT IS ON
# ══════════════════════════════════════════════════════════════════════════
def test_the_four_steps_are_the_drawn_four_in_the_drawn_order():
    """`01-applicant` · `02-property` · `03-service` · `04-review`.

    Asserted BY VALUE and not by length: a tuple of four in the wrong order
    still has four in it, and the number is what a wizard puts in `?step=`.
    """
    assert steps.CAPTURE_STEPS == ("applicant", "property", "service", "review")
    assert steps.STEP_NUMBER == {"applicant": 1, "property": 2, "service": 3, "review": 4}


def test_the_six_that_were_map_onto_the_four_that_are():
    """The carry-over, as data. Documents 4 → 1 · addresses 3 → 2 · services
    2 → 3 · fees 5 → 3 · check 6 → 4, and the applicant stays at 1."""
    assert steps.SIX_BECAME_FOUR == {
        "customer": "applicant",
        "connection": "service",
        "addresses": "property",
        "documents": "applicant",
        "fees": "service",
        "check": "review",
    }
    assert steps.STEP_NUMBER[steps.SIX_BECAME_FOUR["documents"]] == 1
    assert steps.STEP_NUMBER[steps.SIX_BECAME_FOUR["addresses"]] == 2
    assert steps.STEP_NUMBER[steps.SIX_BECAME_FOUR["connection"]] == 3
    assert steps.STEP_NUMBER[steps.SIX_BECAME_FOUR["fees"]] == 3


def test_a_refusal_raised_inside_on_step_is_stamped_and_otherwise_untouched():
    """The envelope is a STAMP and not a new refusal (`BR-SHL-020` r2)."""
    with pytest.raises(errors.ValidationError) as refused:
        with steps.on_step(steps.STEP_SERVICE):
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="customers.serviceRequest.fieldRequired",
                params={"field": "services"},
                field_errors=[{"field": "services", "code": errors.VAL_REQUIRED}],
            )
    assert refused.value.params["step"] == "service"
    assert refused.value.params["field"] == "services"
    assert refused.value.code == errors.VAL_REQUIRED
    assert refused.value.message_key == "customers.serviceRequest.fieldRequired"
    assert [fe["field"] for fe in refused.value.field_errors] == ["services"]


def test_an_inner_stamp_is_never_relabelled_by_an_outer_one():
    """⚠ **THE GUARD, NOT THE HAPPY PATH.** Nesting two doors must not send a
    clerk to the outer one's screen — the door closest to the field answers."""
    with pytest.raises(errors.ValidationError) as refused:
        with steps.on_step(steps.STEP_REVIEW):
            with steps.on_step(steps.STEP_PROPERTY):
                raise errors.ValidationError(
                    errors.VAL_REQUIRED, message_key="customers.serviceRequest.fieldRequired"
                )
    assert refused.value.params["step"] == "property"


def test_on_step_is_not_a_catch_all():
    """Only the two catalogue refusals. An `AuthError` and a plain crash pass
    through the handlers that already own them, untouched and unstamped."""
    with pytest.raises(errors.AuthError) as auth:
        with steps.on_step(steps.STEP_APPLICANT):
            raise errors.AuthError(errors.AUTH_PERMISSION_DENIED)
    assert "step" not in auth.value.params
    with pytest.raises(ZeroDivisionError):
        with steps.on_step(steps.STEP_APPLICANT):
            1 / 0  # noqa: B018


def test_a_biz_refusal_carries_its_step_and_keeps_its_br_ref():
    """The fee doors raise `BizError`, and a clerk sent to the wrong screen by
    one is no better off than a clerk sent there by a `ValidationError`."""
    with pytest.raises(errors.BizError) as refused:
        with steps.on_step(steps.STEP_SERVICE):
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-CUS-090",
                message_key="customers.serviceRequest.feeTakeInFull",
                params={"amount": "130.0000", "currency": "USD"},
            )
    assert refused.value.params["step"] == "service"
    assert refused.value.params["amount"] == "130.0000"
    assert refused.value.br_ref == "BR-CUS-090"


def test_the_services_door_refuses_on_step_three(brazos, dana):  # noqa: F811
    """Services were step 2 and are step 3 — the table array merged with the
    fees and the payment (PO 2026-09-29)."""
    with tenant_ctx(brazos):
        request = _make(dana)
    response = _post(
        api.service_request_services,
        request,
        f"/api/brazos/service-requests/{request.id}/services",
        user=dana.user,
        tenant=brazos,
        data={"services": "water"},
    )
    assert response.status_code == 422
    assert response.data["params"]["step"] == "service"


def test_an_unknown_service_code_also_refuses_on_step_three(brazos, dana):  # noqa: F811
    """The SHAPE check is the view's and the VALUE check is the service's, and
    both are behind the same door — so both name step 3. A refusal that
    reached the clerk from the service with no step would drop them on
    whatever card they were looking at."""
    with tenant_ctx(brazos):
        request = _make(dana)
    response = _post(
        api.service_request_services,
        request,
        f"/api/brazos/service-requests/{request.id}/services",
        user=dana.user,
        tenant=brazos,
        data={"services": ["unicorn"]},
    )
    assert response.status_code == 422
    assert response.data["params"]["step"] == "service"


def test_the_category_door_refuses_on_step_one(brazos, dana):  # noqa: F811
    """*"move this to appliant sicne it is applicant - arrtributes"* — the
    category left step 2 for step 1, so its refusal did too."""
    with tenant_ctx(brazos):
        request = _make(dana)
    response = _post(
        api.service_request_category,
        request,
        f"/api/brazos/service-requests/{request.id}/category",
        user=dana.user,
        tenant=brazos,
        data={"account_type_code": "not_a_category"},
    )
    assert response.status_code == 422
    assert response.data["params"]["step"] == "applicant"


def test_the_documents_door_refuses_on_step_one(brazos, dana):  # noqa: F811
    """⚠ **DOCUMENTS MOVED 4 → 1 AND THIS IS THE CASE THAT WOULD HAVE CAUGHT
    IT.** A stamp of `documents` — or of step 4, which is now the read-only
    review — would send the clerk to a screen with no document panel on it."""
    with tenant_ctx(brazos):
        request = _make(dana)
    response = _post(
        api.service_request_documents,
        request,
        f"/api/brazos/service-requests/{request.id}/documents",
        user=dana.user,
        tenant=brazos,
        data={"doc_type": ""},
    )
    assert response.status_code == 422
    assert response.data["params"]["step"] == "applicant"


def test_the_fee_line_door_refuses_on_step_three(brazos, dana):  # noqa: F811
    """The fees table was step 5 and is step 3."""
    with tenant_ctx(brazos):
        request = _make(dana)
    response = _post(
        api.service_request_fees,
        request,
        f"/api/brazos/service-requests/{request.id}/fees",
        user=dana.user,
        tenant=brazos,
        data={"charge_code": "", "unit_amount": "10.00"},
    )
    assert response.status_code == 422
    assert response.data["params"]["step"] == "service"


def test_the_payment_door_refuses_on_step_three(brazos, dana):  # noqa: F811
    """`When is it being paid?` is drawn under the fees table on step 3. The
    JSON-float refusal (hard rule 2) is the one every clerk can trip."""
    with tenant_ctx(brazos):
        request = _make(dana)
        quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("45.00"))
    response = _post(
        api.service_request_fee_collection,
        request,
        f"/api/brazos/service-requests/{request.id}/fee-collection",
        user=dana.user,
        tenant=brazos,
        data={"amount": 45.10, "method": "cash", "receipt_no": "RCP-26-0001"},
    )
    assert response.status_code == 422
    assert response.data["code"] == "VAL-002"
    assert response.data["params"]["step"] == "service"


def test_the_till_refusal_is_a_biz_error_and_still_names_step_three(brazos, dana):  # noqa: F811
    """`DEF-CUS-6374`'s refusal is a `BizError` raised in the VIEW rather than
    in the service, so it is the case that proves the stamp covers the whole
    door and not only the write at the end of it."""
    with tenant_ctx(brazos):
        request = _make(dana)
        quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("45.00"))
    response = _post(
        api.service_request_fee_collection,
        request,
        f"/api/brazos/service-requests/{request.id}/fee-collection",
        user=dana.user,
        tenant=brazos,
        data={"amount": "45.00", "method": "cash", "receipt_no": "RCP-26-0002"},
    )
    assert response.status_code == 422
    assert response.data["code"] == "BIZ-COMPLETENESS"
    assert response.data["message_key"] == "payments.counter.till_required"
    assert response.data["params"]["step"] == "service"


# ══════════════════════════════════════════════════════════════════════════
# 2 · WHAT THE CUSTOMER IS TOLD — the review step's new card
# ══════════════════════════════════════════════════════════════════════════
def test_the_card_lists_every_on_submit_row_including_the_ones_that_will_not_go(
    brazos, dana  # noqa: F811
):
    """⚠ **AN ABSENT ROW AND A WITHHELD ONE LOOK IDENTICAL**, which is the
    whole point of the card and the false pass this case exists to refuse: an
    empty `rows` for a request nobody has touched would read on screen as
    *nothing will be sent*.

    Three on-submit occasions, always three, in `OCCASIONS`' order — and the
    counter receipt and the decision are NOT among them, because their moment
    is not submit.
    """
    with tenant_ctx(brazos):
        request = _make(dana)
        card = applicant_messages.on_submit_card(request)
    assert [row["occasion"] for row in card["rows"]] == [
        "request_received",
        "documents_outstanding",
        "balance_outstanding",
    ]
    assert card["rows_total"] == 3
    # Law 7: the blind spot carries a NUMBER. One of the three has wording.
    assert card["available_rows"] == 1
    assert card["delivery"] == {"queued_only": True, "delivers": False, "br_ref": "BR-NOT-013"}


def test_the_card_serves_keys_and_an_address_and_no_english(brazos, dana):  # noqa: F811
    """`BR-SHL-020` r2. MESSAGE is a key, CHANNEL and WHEN are codes; `TO` is
    an email address, which is DATA rather than prose and travels as itself."""
    with tenant_ctx(brazos):
        request = _make(dana)
        card = applicant_messages.on_submit_card(request)
    received = card["rows"][0]
    assert received["message_key"] == "customers.serviceRequest.told.request_received"
    assert received["channel"] == "email"
    assert received["to"] == "david@example.test"
    assert received["when"] == "on_submit"
    assert received["will_send"] is True
    assert received["not_sent_reason"] is None


def test_a_row_that_will_not_be_sent_says_which_kind_of_absence_it_is(brazos, dana):  # noqa: F811
    """The drawing prints *"Not sent — none outstanding"* against the
    documents row of a request with nothing outstanding, and this is that row.

    ⚠ **AND THE FEE ROW IS THE HONEST DIVERGENCE FROM THE DRAWING.** The
    drawing shows it going out `On submit`; with nothing owed it does not, and
    even with money owed it could not — `balance_outstanding` has no template
    class in this product (`DEF-CUS-5417`), which `available` states.
    """
    with tenant_ctx(brazos):
        request = _make(dana)
        card = applicant_messages.on_submit_card(request)
    documents = card["rows"][1]
    assert documents["will_send"] is False
    assert documents["when"] is None
    assert documents["not_sent_reason"] == "none_outstanding"
    assert documents["not_sent_reason_key"] == (
        "customers.serviceRequest.toldNotSent.none_outstanding"
    )
    assert documents["available"] is False
    assert documents["params"] == {"count": 0}


def test_the_fee_row_carries_the_figure_as_a_parameter_with_its_currency(
    brazos, dana  # noqa: F811
):
    """`Fee due — $45.00` is composed on the SCREEN from a number and a
    currency. Nothing here builds that sentence, and the amount travels at its
    four stored places (hard rule 2 — this read rounds nothing)."""
    with tenant_ctx(brazos):
        request = _make(dana)
        quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("45.00"))
        card = applicant_messages.on_submit_card(request)
    balance = card["rows"][2]
    assert balance["params"] == {"amount": "45.0000", "currency": "USD"}
    # It still will not be sent, and the reason is the product's rather than
    # this request's — which is what `available` is for.
    assert balance["will_send"] is False
    assert balance["not_sent_reason"] == "this_product_has_no_wording_for_this_one_yet"
    assert balance["available"] is False


def test_an_applicant_with_no_email_gets_rows_that_say_so(brazos, dana):  # noqa: F811
    """All four service-request classes are EMAIL classes; a phone number
    alone carries none of this wording (`ACK_NO_EMAIL`, the same fact at the
    write door). The rows are still listed."""
    with tenant_ctx(brazos):
        request = _make(dana, applicant_email="", applicant_phone="5125550147")
        card = applicant_messages.on_submit_card(request)
    assert card["to"] is None
    assert card["will_send_rows"] == 0
    assert card["rows"][0]["not_sent_reason"] == "applicant_supplied_no_email_address"


def test_a_clerk_who_unticks_a_row_is_told_that_is_why(brazos, dana):  # noqa: F811
    """A stored departure from the drawn default wins, and the reason names
    the clerk's own act rather than the product's absence."""
    with tenant_ctx(brazos):
        request = _make(dana)
        ServiceRequestMessage.objects.create(
            tenant_id=brazos.id, request_id=request.id, occasion="request_received", send=False
        )
        card = applicant_messages.on_submit_card(request)
    assert card["rows"][0]["will_send"] is False
    assert card["rows"][0]["not_sent_reason"] == "the_clerk_did_not_ask_for_this_one"


def test_the_card_never_reads_another_tenants_row(brazos, lonestar, dana):  # noqa: F811
    """⚠ **HARD RULE 1, AND THE QUERY IS SCOPED IN PYTHON RATHER THAN LEFT TO
    RLS** — the default suite is SQLite, which has no row-level security at
    all, so a queryset leaning on the policy would pass this file and be the
    one thing nothing in it can check (hard-won law 14's shape).

    Lonestar holds an unticked `request_received` for an id that is Brazos'.
    Read inside Brazos, the row must be invisible and the drawn default must
    stand.
    """
    with tenant_ctx(brazos):
        request = _make(dana)
    with tenant_ctx(lonestar):
        ServiceRequestMessage.objects.create(
            tenant_id=lonestar.id, request_id=request.id, occasion="request_received", send=False
        )
    with tenant_ctx(brazos):
        card = applicant_messages.on_submit_card(request)
    assert card["rows"][0]["will_send"] is True


def test_the_card_is_served_on_the_detail_the_review_step_already_reads(brazos, dana):  # noqa: F811
    """Hard-won law 2. A card computed by nothing a screen calls is not a
    feature — and a second route for it would let the rows and the fee figures
    they quote come from two reads that can disagree."""
    with tenant_ctx(brazos):
        request = _make(dana)
        detail = reads.detail(request.id)
    assert detail["told_on_submit"]["rows_total"] == 3


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE FEE ROW, AND A TOTAL THE BROWSER NEVER ADDS UP
# ══════════════════════════════════════════════════════════════════════════
def test_the_fee_row_carries_every_drawn_column_from_the_server(brazos, dana):  # noqa: F811
    """`FEE · CHARGED PER · QTY · UNIT PRICE · AMOUNT`, and `AMOUNT` is
    `quantity × unit_amount` computed in the service.

    **Worked, the drawn case:** one `Connection fee`, charged per request, qty
    1, $45.00 → `$45.00`. Here with qty 3 → `$135.00`, which is the assertion
    that goes red the day a screen starts multiplying (`DEF-088`, `DEF-127`).

    ⚠ **`UNIT PRICE` IS THE CATALOGUE'S AND `CHARGED PER` IS NOT — WHICH IS
    `DEF-CUS-7862` AND WAS FOUND BY THIS CASE.** `add_fee_line` reads the price
    through `rating.selectors.charge_by_code` and refuses a caller that offers
    a different one (`DEF-CUS-6416`), so UNIT PRICE genuinely comes from the
    fee. `basis` does not: it is `_text(basis, 60)` off the request body, so
    CHARGED PER is whatever the browser sent and **null when it sends
    nothing** — which is what this assertion found. The catalogue has no
    column to read it from. The row asserted below is therefore the truth as
    built, and the drawing's `Request` is a value a screen supplies.
    """
    with tenant_ctx(brazos):
        request = _make(dana)
        quote_fee(
            dana,
            request.id,
            charge_code="CC-REQFEE",
            unit_amount=Decimal("45.00"),
            quantity=3,
            basis="request",
        )
        bare = _make(dana)
        quote_fee(dana, bare.id, charge_code="CC-REQFEE", unit_amount=Decimal("45.00"))
        tab = reads.fees_tab(sr.request_row(request.id))
        unset = reads.fees_tab(sr.request_row(bare.id))
    line = tab["lines"][0]
    # CHARGED PER — a code that the SCREEN words, round-tripped exactly.
    assert line["basis"] == "request"
    assert line["quantity"] == "3.0000"
    assert line["unit_amount"] == {"amount": "45.0000", "display": "45.00", "currency": "USD"}
    assert line["amount"] == {"amount": "135.0000", "display": "135.00", "currency": "USD"}
    # ⚠ `DEF-CUS-7862`, asserted rather than left implicit: nothing fills it in.
    assert unset["lines"][0]["basis"] is None


def test_the_drawn_total_is_the_servers_and_carries_its_currency(brazos, dana):  # noqa: F811
    """⚠ **`DEF-CUS-7806` IS THE DEFECT FOR A BARE `535.00`**, so the currency
    is asserted and not assumed. Two lines, $45.00 and $60.00 → `$105.00`."""
    with tenant_ctx(brazos):
        request = _make(dana)
        quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("45.00"))
        quote_fee(dana, request.id, charge_code="CC-EXPED", unit_amount=Decimal("60.00"))
        tab = reads.fees_tab(sr.request_row(request.id))
    assert tab["total"] == {"amount": "105.0000", "display": "105.00", "currency": "USD"}


def test_the_total_is_not_the_sum_of_the_amount_column_once_a_line_is_waived(
    brazos, dana  # noqa: F811
):
    """⚠ **THE CASE THAT SAYS WHY THE TOTAL IS SERVED AT ALL.** A waived line
    keeps its own `amount` and its `waived: true` (`DEF-CUS-6423`), so a
    browser summing the drawn AMOUNT column reads $105.00 while the fee due is
    $45.00. The server's answer is the one on the screen."""
    with tenant_ctx(brazos):
        request = _make(dana)
        quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("45.00"))
        second = quote_fee(dana, request.id, charge_code="CC-EXPED", unit_amount=Decimal("60.00"))
        sr.waive_fee_line(dana, second.id, reason="goodwill")
        tab = reads.fees_tab(sr.request_row(request.id))
    column = sum(Decimal(line["amount"]["amount"]) for line in tab["lines"])
    assert column == Decimal("105.0000")
    assert tab["total"]["display"] == "45.00"


# ══════════════════════════════════════════════════════════════════════════
# 4 · `check`, NOT `cheque` — PO 2026-09-29
# ══════════════════════════════════════════════════════════════════════════
def test_the_stored_tender_vocabulary_is_american_english():
    """The enum is the stored value, and it moved. `cheque` survives as an
    ACCEPTED INPUT and is never one of the three this product offers."""
    sr_model = customers_models.ServiceRequest
    assert sr_model.FEE_METHOD_CHECK == "check"
    assert sr_model.FEE_METHODS == ("cash", "card", "check")
    assert "cheque" not in sr_model.FEE_METHODS
    assert sr_model.FEE_METHOD_ALIASES == {"cheque": "check"}


def test_both_spellings_go_in_and_only_one_comes_out():
    """⚠ **NORMALISED AT THE WRITE DOOR**, so a caller that has not been
    redeployed keeps working and the column holds one spelling. Retiring the
    input outright is `DEF-CUS-3653`'s mistake."""
    assert sr.normalised_fee_method("cheque") == "check"
    assert sr.normalised_fee_method("check") == "check"
    assert sr.normalised_fee_method("cash") == "cash"


def _collect(brazos, dana, request, **body):  # noqa: F811
    return _post(
        api.service_request_fee_collection,
        request,
        f"/api/brazos/service-requests/{request.id}/fee-collection",
        user=dana.user,
        tenant=brazos,
        data=body,
    )


def _with_a_till_open(brazos, dana, slug):  # noqa: F811
    centre = content_models.ServiceCentre.objects.create(
        tenant=brazos, slug=slug, name="Main office", address="101 Bend Road"
    )
    counters.open_counter(
        dana,
        service_centre_id=centre.pk,
        opening_float=Decimal("0.0000"),
        opened_at=timezone.now(),
    )


def test_a_check_taken_at_the_counter_reads_back_as_check(brazos, dana):  # noqa: F811
    """**The mismatch reported 2026-09-28, measured on this door.** The
    service request spelled the tender `cheque` and `payments` spells it
    `check`; a clerk sending the American word had to be carried by
    `payments.counter_receipts.FEE_METHOD_TO_TENDER`. Now the word the clerk
    sends is the word the column holds."""
    with tenant_ctx(brazos):
        request = _make(dana)
        quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("45.00"))
        _with_a_till_open(brazos, dana, "check-window")
    response = _collect(
        brazos,
        dana,
        request,
        amount="45.00",
        method="check",
        receipt_no="RCP-26-0010",
        check={"number": "10241", "bank": "First National", "date": "2026-05-12"},
    )
    assert response.status_code == 200
    with tenant_ctx(brazos):
        assert sr.request_row(request.id).fee_method == "check"
        assert reads.fees_tab(sr.request_row(request.id))["fee_method"] == "check"


def test_the_old_spelling_is_still_accepted_and_is_stored_the_new_way(brazos, dana):  # noqa: F811
    """A caller that has not been redeployed must not start refusing. It is
    accepted, and it is never written back."""
    with tenant_ctx(brazos):
        request = _make(dana)
        quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("45.00"))
        _with_a_till_open(brazos, dana, "cheque-window")
    response = _collect(
        brazos,
        dana,
        request,
        amount="45.00",
        method="cheque",
        receipt_no="RCP-26-0011",
        cheque={"number": "10242", "bank": "First National", "date": "2026-05-12"},
    )
    assert response.status_code == 200
    with tenant_ctx(brazos):
        assert sr.request_row(request.id).fee_method == "check"
