# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 wave 1 lane B (PO rulings 2026-09-15) · blueprint
#           `05-prototype/02 Accounts Menu Blueprint.pdf` entry 06, pages
#           **p077, p082, p083 read AS PAGE IMAGES** at scale 2, and p083's
#           address block re-rendered at scale 6 (B14 rule 42)
#           Screens: REQ-02 (the request's own screen) · REQ-03.3 (capture,
#           addresses and property)
# Rules:    BR-CUS-1055 (the unit count is a CLAIM; the locality is the
#           premises') · BR-CUS-070 (`address_as_given` kept verbatim) ·
#           BR-MET-1161 / CLAUDE.md hard rule 8 (one address home) ·
#           B14 rule 31 (no database id is a visible value) · B14 rule 37 (a
#           drawn figure is an illustration) · NFR-5 (no caps)
# Defects:  DEF-CUS-5386 (the raw premises UUID — the SERVER half) ·
#           DEF-CUS-5385 (the unit count has no column) · DEF-CUS-5400 (G85's
#           blind spot, filed by this lane and NOT fixed here)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The matched place, NAMED — and what the applicant says is on the property.

RED-FIRST PROOF (r11 step 2d · hard-won law 7). Every case below was broken
FIRST, on this tree, and its failure quoted before it was trusted green. The
mutations and their output are in the lane's conformance file,
`04-docs/05-modules/03-customers/conformance/CR-094-BRC01-request-screen-lane-B-the-place-and-the-unit-count.md`.

⚠ **WHAT THIS FILE DOES NOT ASSERT, SAID OUT LOUD.** It proves the READ serves
the premises number, the unit number and the locality. It does **not** prove the
screen draws them — `ServiceRequestDetailPage.tsx` still renders
`loc.resolved_premises_id` and therefore still prints a UUID to a clerk, which
is `DEF-CUS-5386` and stays OPEN. Wave 2 owns that screen and this lane did not
touch it. A payload nothing renders is hard-won law 2's dead half, so the
handover is written where a screen lane will read it rather than left implied.
"""

import pytest

from core import errors

from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Miller, Sarah",
    "address_as_given": "212 Balcones Drive",
}


def _seed_sr_series(tenant, opening=1):
    from apps.tenancy import models as tenancy_models

    tenancy_models.NumberSeries.objects.update_or_create(
        tenant=tenant,
        series="service_request",
        defaults={"format": "SR-{YY}-{0000}", "next_number": opening},
    )


def _new(actor, **overrides):
    return sr.create_request(actor, {**CAPTURE, **overrides})


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE MATCHED PLACE IS NAMED, NOT KEYED — DEF-CUS-5386
# ═══════════════════════════════════════════════════════════════════════════
def test_the_matched_premises_and_unit_are_served_by_their_own_numbers(brazos, dana):
    """p083 draws `Matched premises PR-0731 · exact` and `Matched unit
    U-001884 · exact`, and the product served a raw UUID.

    ⚠ **THE DRAWN NUMBERS ARE ILLUSTRATIONS (B14 rule 37).** This asserts the
    numbers THIS product allocates, not the blueprint's.
    """
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        premises = make_premises(
            dana, address_line="212 Balcones Drive", city="Austin", state="TX",
            postal_code="78704",
        )
        unit = make_unit(dana, premises["id"], label="3", services=["electric"])
        request = _new(dana, address_as_given=unit["unit_no"])
        sr.resolve_address(dana, request.id)

        place = reads.detail(request.id)["location_and_services"]

        # The ids still travel — rule 31 forbids an id as the VISIBLE VALUE of
        # a field, not in the response, and a screen that lost them could not
        # link anywhere (DEF-2716's proved fix keeps the id on `title=`).
        assert place["resolved_premises_id"] == str(premises["id"])
        assert place["resolved_unit_id"] == str(unit["id"])
        # …and beside them, the two things a clerk can read down a telephone.
        assert place["resolved_premises_no"] == premises["premise_no"]
        assert place["resolved_unit_no"] == unit["unit_no"]
        assert place["resolved_premise_address"] == "212 Balcones Drive"
        assert place["resolved_match"] == reads.MATCH_BY_EXACT_REFERENCE
        # DEF-CUS-10705 — the unit's LABEL travels too, so the head can draw
        # `212 Balcones Drive · 3 · Austin` (p082) and not drop the apartment.
        assert place["resolved_unit_label"] == "3"


def test_an_unresolved_request_names_no_place_and_invents_none(brazos, dana):
    """p077: *"An address that matches nothing is not refused… a new connection
    at a field with no address yet is exactly the job this wizard exists for."*

    So every named field is `None` — never the id, and never a blank string
    that would read on screen as *we looked and found nothing there*.
    """
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        request = _new(dana, address_as_given="A field off Farm Road 12")
        evidence = sr.resolve_address(dana, request.id)
        assert evidence.resolution_kind == "no_premise"

        place = reads.detail(request.id)["location_and_services"]
        assert place["resolved_premises_id"] is None
        assert place["resolved_premises_no"] is None
        assert place["resolved_unit_no"] is None
        assert place["resolved_unit_label"] is None
        assert place["premise_locality"] is None
        assert place["resolved_match"] is None


def test_a_premises_with_no_number_falls_back_to_its_address_and_never_to_the_id(
    brazos, dana
):
    """⚠ **`premise_no` AND `unit_no` ARE BOTH NULLABLE**, so *the number is not
    known* is a real state and not a fault — a tenant that never turned its
    numbering series on has rows without them.

    The screen needs something a person can read in that case, and it must not
    be the key: that is the defect coming straight back. `premise_address`
    travels for exactly this, and the unit falls back to its LABEL.
    """
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        premises = make_premises(dana, address_line="77 Cedar Court")
        unit = make_unit(dana, premises["id"], label="A", services=["water"])
        request = _new(dana, address_as_given=unit["unit_no"])
        sr.resolve_address(dana, request.id)

        # ⚠ **THE NUMBERS GO AFTER THE MATCH, AND THAT ORDER IS THE TEST.** The
        # resolver finds a unit BY its reference, so nulling the numbers first
        # simply produces an unmatched request and proves nothing about the
        # fallback — which is exactly what the first draft of this case did:
        #     E   AssertionError: assert None == '77 Cedar Court'
        # A resolved id whose row carries no readable number is the real state
        # (a tenant that never turned its numbering series on), and it is
        # reached by taking the numbers away from a match that already exists.
        metering_models.Premises.objects.filter(pk=premises["id"]).update(premise_no=None)
        metering_models.Unit.objects.filter(pk=unit["id"]).update(unit_no=None)
        place = reads.detail(request.id)["location_and_services"]

        assert place["resolved_premises_no"] is None
        assert place["resolved_premise_address"] == "77 Cedar Court"
        # the LABEL, which is what a person calls it — never the uuid
        assert place["resolved_unit_no"] == "A"
        assert place["resolved_unit_no"] != place["resolved_unit_id"]


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE LOCALITY IS THE PREMISES', WALKED TO — hard rule 8 / BR-MET-1161
# ═══════════════════════════════════════════════════════════════════════════
def test_the_town_state_and_postcode_come_from_the_premises_and_not_from_the_request(
    brazos, dana
):
    """PO ruling 2026-09-15, verbatim: *"if we have unit or street address then
    we should take it from premises/Unit - it means its a search and if not
    foudn them alow user to add them"*.

    p083 draws the whole address on one line — `As given → 212 Balcones Drive,
    Unit 3, Austin TX 78704` — and the town in it is the matched PREMISES'
    fact. This is `DEF-CUS-3653`'s fix on a second screen.
    """
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        premises = make_premises(
            dana, address_line="212 Balcones Drive", city="Austin", state="TX",
            postal_code="78704",
        )
        unit = make_unit(dana, premises["id"], label="3", services=["electric"])
        request = _new(dana, address_as_given=unit["unit_no"])
        sr.resolve_address(dana, request.id)

        detail = reads.detail(request.id)
        assert detail["location_and_services"]["premise_locality"] == {
            "city": "Austin",
            "state": "TX",
            "postal_code": "78704",
        }
        # The HEAD draws the address line ABOVE the tabs, so it carries it too.
        assert detail["header"]["premise_locality"] == {
            "city": "Austin",
            "state": "TX",
            "postal_code": "78704",
        }


def test_the_request_holds_no_address_column_of_its_own_beyond_what_was_typed(
    brazos, dana
):
    """⚠ **THE FENCE, MOVED BY A RULING RATHER THAN TORN DOWN — `BR-CUS-1091`,
    PO 2026-09-22, verbatim: *"correct address will be on presmies but first
    time you will ahve to take the details to match it"*.**

    ⚠ **THIS CASE FORBADE `address_city_as_given` UNTIL 2026-09-24 AND HAD BEEN
    RED FOR TWO DAYS (`DEF-CUS-6458`).** Three columns of exactly those names
    were written on 2026-09-15 and ruled out of this table the same hour
    (`BR-CUS-1055`); the PO reversed that on 2026-09-22 and the reversal reached
    `CAPTURE_FIELDS`, the model, the migration and the screen — and not this
    case, which is the whole of the defect.

    **WHAT IS STILL FENCED, AND IT IS THE HALF THAT MATTERS.** Hard rule 8 says
    where an address is STORED as the truth: on `premises`, and nowhere else. It
    says nothing about what a member of the public may TYPE, which is why every
    one of the three permitted columns is spelled `_as_given` — the posture
    `address_as_given` and `interruptions.location_text` already carry. **A BARE
    `city` WOULD BE THE FOURTH HOME** `G85` refuses by name, so the bare
    spellings are asserted refused here, and refused BY NAME rather than dropped
    silently: a silently dropped field is a form that says it recorded something
    it did not.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7): asserting only that the
    bare names are absent. A table that had lost the three `_as_given` columns
    would satisfy that and would be the 2026-09-22 ruling silently reverted — so
    their PRESENCE is asserted in the same breath, and this case goes red in
    either direction.
    """
    from apps.customers import models as customers_models

    declared = {f.name for f in customers_models.ServiceRequest._meta.get_fields()}
    for forbidden in (
        # ⚠ NOT `state` — that is the request's own WORKFLOW state
        # (`draft`/`submitted`/…), not an address part.
        "city",
        "state_as_given",
        "postal_code",
        "postcode",
        "zip_code",
    ):
        assert forbidden not in declared, (
            f"`service_requests.{forbidden}` would be a fourth address home. "
            "An address is stored on `premises` (CLAUDE.md hard rule 8); the "
            "locality is walked to — see service_request_reads.resolved_place."
        )
    for permitted in (
        "address_city_as_given",
        "address_state_as_given",
        "address_postal_code_as_given",
    ):
        assert permitted in declared, (
            f"`service_requests.{permitted}` is BR-CUS-1091's record of what the "
            "applicant said, ruled onto this table by the PO on 2026-09-22. "
            "Losing it is that ruling reverted."
        )

    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        request = _new(dana)
        # The parts the ruling allows are taken…
        sr.update_request(dana, request.id, {"address_city_as_given": "Austin"})
        assert (
            customers_models.ServiceRequest.objects.get(pk=request.id).address_city_as_given
            == "Austin"
        )
        # …and a BARE address part is still refused by name, never dropped.
        with pytest.raises(errors.ValidationError):
            sr.update_request(dana, request.id, {"city": "Austin"})


def test_what_the_applicant_typed_is_never_replaced_by_what_was_matched(brazos, dana):
    """p083's footnote, verbatim: *"What they typed is kept beside what we
    matched, never replaced by it. The resolver is evidence; if the two ever
    disagree, the clerk can see both."* (`BR-CUS-070`.)

    Proved on a DISAGREEMENT, because two fields that happen to be equal cannot
    tell you which one the screen is reading.
    """
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        premises = make_premises(
            dana, address_line="212 Balcones Drive", city="Austin", state="TX",
            postal_code="78704",
        )
        unit = make_unit(dana, premises["id"], label="3", services=["electric"])
        # What the applicant said and what the register holds are not the same
        # words — the resolver still finds the unit, by its reference.
        request = _new(dana, address_as_given=unit["unit_no"])
        sr.resolve_address(dana, request.id)

        place = reads.detail(request.id)["location_and_services"]
        assert place["address_as_given"] == unit["unit_no"]
        assert sr.request_row(request.id).address_as_given == unit["unit_no"]
        assert place["resolved_premise_address"] == "212 Balcones Drive"
        assert place["premise_locality"]["city"] == "Austin"


# ═══════════════════════════════════════════════════════════════════════════
# 3 · BOTH ADDRESSES REACH THE SCREEN — the PO's *"service address and also
#     allow to take billing address"*
# ═══════════════════════════════════════════════════════════════════════════
def test_the_billing_address_and_its_same_as_service_flag_both_reach_the_screen(
    brazos, dana
):
    """⚠ **NOTHING WAS BUILT FOR THIS AND THAT IS THE FINDING.** The PO ruled
    *"we have to show service address and also allow to take billing address"*;
    the capture endpoint has taken both since REQ-03.3 and the read has served
    both since W4. The gap is on the SCREEN, which draws neither.

    So this case exists to hold the payload still while wave 2 builds against
    it: a later lane tidying `location_tab` cannot drop either field without
    going red, and the two travel as TWO fields, because *"same as service"* and
    *"they gave us a different one"* are different facts.
    """
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        request = _new(dana)
        place = reads.detail(request.id)["location_and_services"]
        assert place["billing_address_same"] is True
        assert place["billing_address_as_given"] is None

        sr.update_request(
            dana,
            request.id,
            {
                "billing_address_same": False,
                "billing_address_as_given": "PO Box 41, Austin TX 78767",
            },
        )
        place = reads.detail(request.id)["location_and_services"]
        assert place["billing_address_same"] is False
        assert place["billing_address_as_given"] == "PO Box 41, Austin TX 78767"


# ═══════════════════════════════════════════════════════════════════════════
# 4 · UNITS ON THE PROPERTY — BR-CUS-1055, *"we need to build this"*
# ═══════════════════════════════════════════════════════════════════════════
def test_the_unit_count_is_captured_stored_and_served(brazos, dana):
    """p077 asks `How many units are on this property? *` helped by *"What the
    applicant says is there"*; p082 prints `Units on the property · 6`.

    Before this column the number survived only in free-text notes, *"which no
    screen and no rule can read"* — the drawing's own annotation.
    """
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        request = _new(dana, units_on_property=6)
        assert sr.request_row(request.id).units_on_property == 6
        assert reads.detail(request.id)["location_and_services"]["units_on_property"] == 6


def test_the_unit_count_is_a_whole_number_or_a_stated_absence(brazos, dana):
    """A count that is not a whole number is REFUSED BY NAME rather than
    coerced, and an unanswered one stays `None` — which a screen renders as
    *not supplied* and not as zero units.

    ⚠ **ZERO IS ACCEPTED AND A NEGATIVE IS NOT.** Vacant land with a connection
    request on it genuinely has no units; refusing zero would make a clerk type
    `1` about a field with no building on it.
    """
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        assert sr.request_row(_new(dana).id).units_on_property is None

        with pytest.raises(errors.ValidationError):
            _new(dana, units_on_property="six")
        with pytest.raises(errors.ValidationError):
            _new(dana, units_on_property=-3)

        assert sr.request_row(_new(dana, units_on_property=0).id).units_on_property == 0
        # A string of digits off an HTML form is a whole number, not a refusal.
        assert sr.request_row(_new(dana, units_on_property="12").id).units_on_property == 12


def test_no_maximum_is_enforced_on_the_unit_count(brazos, dana):
    """`NFR-5` — no hard cap anywhere, and `CLAUDE.md` makes that flexibility
    load-bearing: nobody may add a maximum that would have to be removed when a
    bigger tier arrives.

    A 40,000-unit estate is beyond anything the ICP models and is accepted
    anyway, because the alternative is a number somebody has to justify.
    """
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        request = _new(dana, units_on_property=40_000)
        assert sr.request_row(request.id).units_on_property == 40_000


def test_the_unit_count_stays_editable_after_submission_and_the_address_does_not(
    brazos, dana
):
    """⚠ **A LANE JUDGMENT, ASSERTED SO IT IS NOT REDISCOVERED AS AN ACCIDENT**
    (decision log 2026-09-15).

    `BR-CUS-070` freezes the address the applicant gave once the request is
    submitted. It does not name the unit count, and the blueprint's own match
    table draws that count as a CLAIM the register may agree or disagree with
    (`Units on the property · 6` against `6 units on PR-0731` → `Agrees`). A
    clerk who learns the building has six flats rather than four should be able
    to say so; a clerk who wants to rewrite the address after the fact may not.
    """
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        request = _new(dana, units_on_property=4)
        sr.transition(dana, request.id, "submit")

        sr.update_request(dana, request.id, {"units_on_property": 6})
        assert sr.request_row(request.id).units_on_property == 6

        with pytest.raises(errors.BizError):
            sr.update_request(dana, request.id, {"address_as_given": "Somewhere else"})
        assert sr.request_row(request.id).address_as_given == "212 Balcones Drive"
