# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-22, verbatim: *"you would ahve created a new move
#           In request ID and add all details from servcies request to it and
#           save it as a draft - do you ahve move in request ID in numbering?"*
#           and *"fix all these issues"* — `CR-133-BRC07`.
# Rules:    BR-CUS-1090 (this file) · BR-CUS-1077 (the job row this numbers) ·
#           BR-CUS-093 (numbered at CREATION, and an abandoned draft burns its
#           number) · BR-CUS-150/151/152 (`move_records` untouched) ·
#           BR-TEN-035 (allocation, and the lawful gap) · CR-122-BRC06
#           (`reserved_move_no`, the mechanism reused) · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 6 (idempotency) · hard rule 8 (the
#           address is walked)
# Tests:    this file, plus `10-scripts/br_cus_1090_move_in_number_readback.py`
#           for the three things SQLite cannot show (the partial expression
#           index, RLS FORCE, and the chain on real seeded data).
# ───────────────────────────────────────────────────────
"""**BR-CUS-1090 — the move-in's number, from approval to the finished record.**

RED-FIRST PROOF (r11 step 2d, hard-won law 7), **in `pytest`, which is the
harness that will run these** — not a script calling the functions, which is
`DEF-GOV-3733`'s shape. The red was produced by replacing the allocation in
`move_in_jobs.raise_for_request` with `move_no, _absence = None, None` — the
product exactly as it stood before this ruling — and **SIX of the seven cases
failed**, quoted from that run::

    FAILED ...::test_approving_a_move_in_numbers_the_job_from_the_move_in_series
    FAILED ...::test_the_list_row_quotes_the_job_s_own_number_not_the_request_s
    FAILED ...::test_the_job_has_a_page_of_its_own_at_its_own_reference
    FAILED ...::test_the_finished_record_adopts_the_job_s_number_rather_than_minting
    FAILED ...::test_a_wizard_opened_on_the_job_carries_its_number
    FAILED ...::test_a_second_approval_press_issues_no_second_number
    assert None is not None
    assert 'MVI-26-0002' == 'MVI-26-0001'

⚠ **THE SEVENTH — `test_the_job_stores_no_fact_the_request_owns` — PASSED IN
THE RED RUN, AND IT IS NAMED HERE RATHER THAN COUNTED AS PROOF.** It asserts an
ABSENCE (no applicant, unit, address, date or service column on `move_in_jobs`)
and that absence was true before this ruling and is true after it. It is a real
case — it is the assertion `BR-CUS-1090`'s own *"the thing a later lane will be
tempted to do"* paragraph names — and it is not evidence that anything was
built.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY**, asked before trusting any green
(hard-won law 7, habit 2):

  * **Asserting that a number is TRUTHY rather than that it is THE SAME ONE.**
    Every arm of the chain allocates from one series, so three different numbers
    are all `MVI-…` and all truthy. Every case below compares the STRING against
    the one the approval issued, which is the only thing that can fail on the
    two-vocabularies defect this rule exists to prevent.
  * **A fixture whose tenant has no `move_in` series row.** Then every number is
    `None`, `None == None`, and the chain cases pass over a product that
    allocates nothing. `test_approving_a_move_in_numbers_the_job_from_the_move_in
    _series` asserts the PREFIX and the format, so that fixture goes red first.
  * **Reading the number off the RESPONSE instead of the row.** The response is
    what the approval says it did; the row is what it did. Both are asserted and
    the row is what the later cases re-read.
  * **A record test that passes because no job existed to adopt from.** The job
    is asserted `pending` WITH its number before the move-in is run, so a case
    that never raised one cannot reach the assertion.
"""

import re

import pytest

from apps.customers import models as customers_models
from apps.customers import move_in_jobs, move_reads, move_record_reads, moves
from apps.customers import service_request as rules
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.tenancy import wizard_parks

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

DOC_ID = customers_models.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY

#: `MVI-{YY}-{0000}` — `apps/tenancy/models.py`'s seeded default for the
#: `move_in` series. Asserted as a SHAPE rather than as a literal, because the
#: format is a tenant's to change on Settings (`BR-TEN-035`) and a test pinned
#: to `MVI-26-0001` would go red the day a demo utility renamed its own series.
MVI = re.compile(r"^MVI-\d{2}-\d{4}$")

CAPTURE = {
    "channel": "counter",
    "applicant_kind": "person",
    "applicant_name": "Okonjo, Ada",
    "applicant_email": "a.okonjo@example.test",
    "applicant_phone": "512-555-0177",
    "address_as_given": "88 Pine Vista",
    "property_type": "standalone_owner_occupied",
    "what_they_said": "I am taking over the flat next month",
}


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — lifted from `test_br_cus_1077_move_in_job.py` unchanged
# ═══════════════════════════════════════════════════════════════════════════
def _served_unit(actor, tenant, *, label="Unit 1", address="88 Pine Vista"):
    premises = make_premises(actor, address_line=address, services_available=["electric"])
    unit = make_unit(actor, premises["id"], label=label)
    plan = make_plan(tenant, name="BR-CUS-1090 fixture", services=("electric",))
    from apps.metering import services as metering_services

    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    return premises, unit


def _move_in_request(actor, *, address=None):
    request = sr.create_request(
        actor, {**CAPTURE, **({"address_as_given": address} if address else {})}
    )
    doc = sr.attach_document(
        actor, request.id, doc_type=DOC_ID, name="lease.pdf", storage_ref="s3://lease"
    )
    # ⚠ **THE SERVICES ARE ASKED FOR EXPLICITLY, AND THE FIRST DRAFT DID NOT.**
    # `create_request` writes no `service_request_services` row, so
    # `services_asked_for` truthfully answered `[]` and two cases went red on a
    # FIXTURE gap rather than a product one. A fixture that cannot produce the
    # fact under test is a case that can only ever fail or pass vacuously.
    sr.set_services(actor, request.id, ["electric"])
    sr.submit(actor, request.id)
    if sr.request_row(request.id).state != rules.UNDER_REVIEW:
        pass  # the decisions work straight from `submitted` since 2026-09-19
    sr.resolve_address(actor, request.id)
    sr.link_customer(actor, request.id, customer_id=None)
    sr.decide_outcome(actor, request.id, outcome="move_in")
    sr.verify_document(actor, doc.id)
    return sr.request_row(request.id)


def _occupant(actor, unit, *, name="Prior, Tenant"):
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-07-01",
            "contact": {"full_name": name},
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE ALLOCATION — *"do you ahve move in request ID in numbering?"*
# ═══════════════════════════════════════════════════════════════════════════
def test_approving_a_move_in_numbers_the_job_from_the_move_in_series(brazos, dana):
    """**The job carries `MVI-{YY}-{0000}` from the moment the clerk presses.**

    Asserted on BOTH the response and the stored row: the response is what the
    approval says it did, the row is what it did, and a product that returned a
    number without writing one would pass on the first alone.

    The FORMAT is asserted rather than a literal, so a fixture whose tenant has
    no `move_in` series row — where every number is `None` and every later
    comparison is `None == None` — fails here first.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 2")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)

        row = move_in_jobs.MoveInJob.objects.get(request_id=request.id)
        assert row.move_no is not None
        assert MVI.match(row.move_no), row.move_no
        assert move_in_jobs.serialize(row)["move_no"] == row.move_no
        # Exactly one of the pair, never both — the shape every move surface
        # in this product serves.
        assert move_in_jobs.serialize(row)["move_no_unavailable"] is None


def test_a_second_approval_press_issues_no_second_number(brazos, dana):
    """**One decision raises one job and burns one number** (hard rule 6).

    `BR-CUS-093` clause (e)'s posture: the second press is refused BY NAME and
    the series is not touched, so a clerk double-clicking Approve does not spend
    a counter. The refusal carries the number it already issued, because a
    clerk who pressed twice still needs to be told which job exists.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 3")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        first = move_in_jobs.MoveInJob.objects.get(request_id=request.id).move_no

        again = move_in_jobs.raise_for_request(dana, sr.request_row(request.id))
        assert again["code"] == move_in_jobs.JOB_ALREADY_RAISED
        assert again["move_no"] == first
        assert move_in_jobs.MoveInJob.objects.filter(request_id=request.id).count() == 1
        assert move_in_jobs.MoveInJob.objects.get(request_id=request.id).move_no == first


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE SCREEN — the identity stops being the request it came from
# ═══════════════════════════════════════════════════════════════════════════
def test_the_list_row_quotes_the_job_s_own_number_not_the_request_s(brazos, dana):
    """**The REFERENCE column holds a reference to THIS job.**

    Before this ruling the cell served `move_in_not_completed` and the screen
    fell back to the SERVICE REQUEST number, linking back to the application —
    an application's number standing in for a job's. The number is the job's
    now, and the walk back is still on the row.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 4")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        expected = move_in_jobs.MoveInJob.objects.get(request_id=request.id).move_no

        rows = [
            row
            for row in move_reads.move_ins_list()["rows"]
            if row["row_kind"] == move_reads.ROW_KIND_PENDING_JOB
        ]
        assert len(rows) == 1
        row = rows[0]
        assert row["move_no"] == expected
        assert row["move_no_unavailable"] is None
        # ⚠ **THE CONNECTION IS KEPT AND ONLY ITS PLACE MOVES.** A row that
        # dropped the request would have traded one lost link for another.
        assert row["request"]["request_no"] == request.request_no


def test_the_job_has_a_page_of_its_own_at_its_own_reference(brazos, dana):
    """**`/moves/{ref}` resolves a pending job — the third arm.**

    Without it the link the list now draws would 404 on every approved move-in:
    a reference printed on a live list, wrapped in a door that opens nothing.
    That is hard-won law 2's mirror and it is exactly what `DEF-CUS-5922` cost
    one flow over.

    ⚠ **LOWERCASE, DELIBERATELY.** The blueprint's own URL is
    `/brazosbend/moves/mvi-26-0114` and the number a clerk quotes is upper;
    `uq_move_in_jobs_tenant_move_no_ci` is what makes that one row.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 5")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        ref = move_in_jobs.MoveInJob.objects.get(request_id=request.id).move_no

        detail = move_record_reads.record_detail(ref.lower())
        assert detail["state"] == move_record_reads.STATE_APPROVED
        assert detail["move_no"] == ref
        assert detail["kind"] == "move_in"
        # THE DETAILS THE PO ASKED FOR, every one read through the link.
        assert detail["title"] == CAPTURE["applicant_name"]
        assert detail["address_line"]  # walked to the premises (hard rule 8)
        assert detail["request"]["request_no"] == request.request_no
        assert [s["code"] for s in detail["services"]] == ["electric"]
        # ⛔ And what an approved job genuinely cannot answer says so rather
        # than rendering an empty box (`DEF-127`).
        assert detail["what_happened"]["account_opened"]["value"] is None
        assert (
            detail["what_happened"]["account_opened"]["unavailable"]["code"]
            == "move_in_approved_and_not_started"
        )
        assert detail["park_id"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE CHAIN — one number, three tables (`move_in_jobs` §4)
# ═══════════════════════════════════════════════════════════════════════════
def test_a_wizard_opened_on_the_job_carries_its_number(brazos, dana):
    """**The park CARRIES the job's number and burns no counter.**

    `wizard_parks._draft_reference` prefers a carried number over an
    allocation; `move_in_no` joined `CARRIED_REFERENCE_KEYS` for this. The
    from-scratch path is asserted in the same case, because a change that made
    EVERY move-in draft carry something would pass the first assertion and
    break every wizard opened from the Move-ins tab.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 6")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        issued = move_in_jobs.MoveInJob.objects.get(request_id=request.id).move_no

        assert wizard_parks._draft_reference("move_in", {"move_in_no": issued}) == issued
        fresh = wizard_parks._draft_reference("move_in", {})
        assert fresh != issued
        assert MVI.match(fresh), fresh


def test_the_finished_record_adopts_the_job_s_number_rather_than_minting(brazos, dana):
    """**The number a clerk has been quoting is the number it is filed under.**

    This is the whole reason the change is more than a column. `record_move`
    prefers **draft → job → mint**; without the middle arm the queue would print
    one number and `move_records` would hold another, which is the
    two-vocabularies cost `record_move`'s own comment spells out.

    The job is asserted `pending` WITH its number BEFORE the move-in runs, so a
    case that never raised one cannot reach the comparison.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 7", address="2201 Cedar Ln")
        outgoing = _occupant(dana, unit, name="Baptiste, Marie")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        # ⚠ **THE OUTGOING OCCUPANT LEAVES BEFORE THE APPROVAL, NOT AFTER IT
        # (2026-09-23, `DEF-CUS-6350`).** This case approved over a unit
        # `Baptiste, Marie` still held and moved her out afterwards. Approve now
        # checks the unit is free (`BR-CUS-1095`, PO: *APPROVE checks the property
        # and unit before it is pressed*) and names the occupier, so the order
        # below is the product's order and not fixture plumbing.
        customers_services.move_out(dana, outgoing["id"], {"moved_out_on": "2026-09-19"})
        sr.approve_and_raise(dana, request.id)

        job = move_in_jobs.MoveInJob.objects.get(request_id=request.id)
        assert job.state == move_in_jobs.STATE_PENDING
        issued = job.move_no
        assert issued is not None

        result = customers_services.move_in(
            dana,
            outgoing["id"],
            {
                "account_type": "residential",
                "status": "active",
                "opened_at": "2026-09-20",
                "contact": {"full_name": CAPTURE["applicant_name"]},
                "customer": identity_fixtures.customer_block(
                    CAPTURE["applicant_name"], account_type="residential"
                ),
                "service_request_id": str(request.id),
            },
        )

        assert result["move_no"] == issued
        record = moves.MoveRecord.objects.get(id=result["move_record_id"])
        assert record.move_no == issued
        # ⛔ **`BR-CUS-152` IS NOT NARROWED.** Exactly one record row exists and
        # it was INSERTed; nothing was promoted and no row changed table.
        assert moves.MoveRecord.objects.filter(kind=moves.KIND_MOVE_IN, move_no=issued).count() == 1
        # The job is done and the number stayed on it — the queue row is the
        # provenance of the number, not a second claim to it.
        job.refresh_from_db()
        assert job.state == move_in_jobs.STATE_DONE
        assert job.move_no == issued


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE ABSENCE THE RULE DEPENDS ON — carried, never copied
# ═══════════════════════════════════════════════════════════════════════════
def test_the_job_stores_no_fact_the_request_owns(brazos, dana):
    """**The details are CARRIED through the link and COPIED nowhere.**

    ⚠ **THIS CASE PASSED IN THE RED RUN AND IS NOT EVIDENCE THAT ANYTHING WAS
    BUILT.** It is here because `BR-CUS-1090`'s *"the thing a later lane will
    be tempted to do"* paragraph names exactly this temptation — the PO's
    sentence says *"add all details from servcies request to it"*, and a lane
    reading that as *add columns* would break `move_in_jobs` §2 and CLAUDE.md
    hard rule 8 in one commit.

    An address column would be a fourth home `G85` fails BY NAME; the rest
    would be second copies of facts the request owns, free to disagree with it
    the day somebody edits one.
    """
    columns = {field.name for field in move_in_jobs.MoveInJob._meta.get_fields()}
    for forbidden in (
        "applicant_name",
        "unit",
        "unit_id",
        "premises",
        "premises_id",
        "requested_start",
        "services",
        "address",
        "address_line",
        "city",
        "postcode",
        "lat",
        "lng",
    ):
        assert forbidden not in columns, f"{forbidden} is the request's and must not be copied"
    # And the facts ARE reachable — an absence that hid them would be the
    # opposite defect.
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 8")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        job = move_in_jobs.MoveInJob.objects.select_related("request").get(
            request_id=request.id
        )
        assert job.request.applicant_name == CAPTURE["applicant_name"]
        assert [s["code"] for s in move_in_jobs.services_asked_for(job.request)] == ["electric"]


def test_a_job_raised_before_the_column_says_so_and_does_not_blame_settings(brazos, dana):
    """**Two absences, and sending a clerk to Settings for nothing is the bug.**

    ⚠ **FOUND IN A BROWSER AND BY NOTHING ELSE** (hard-won law 6). The first
    version of this change served `numbering_series_missing` for every
    unnumbered job — *"A number series for move-ins has not been set up"* —
    which is TRUE of an unconfigured tenant and **FALSE of every job
    `BR-CUS-1077` raised between 2026-09-16 and 2026-09-22.** Those tenants have
    a series; the jobs simply predate the column and `customers/0064` refuses to
    back-fill them. A clerk reading the wrong sentence goes to Settings →
    Numbering, finds the format perfectly configured, and learns that the
    product is lying to them.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** asserting only that SOME absence
    is served. Both arms serve one. The case asserts WHICH, on both sides, so a
    change that collapsed them back into one code goes red.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 11")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        job = move_in_jobs.MoveInJob.objects.select_related("request").get(
            request_id=request.id
        )

        # A job raised TODAY with no number can only mean an unconfigured
        # tenant, so that is the sentence it gets.
        job.move_no = None
        cell = move_reads.move_in_job_reference(job)
        assert cell["move_no"] is None
        assert cell["move_no_unavailable"]["code"] == moves.NUMBERING_SERIES_MISSING

        # The same row, raised before the column existed, gets the other one.
        job.created_at = job.created_at.replace(
            year=2026, month=9, day=17
        )
        cell = move_reads.move_in_job_reference(job)
        assert cell["move_no_unavailable"]["code"] == "move_in_job_predates_its_number"
        # ⛔ And it must NOT tell them to go and configure something.
        assert "has not been set up" not in cell["move_no_unavailable"]["detail"]

        # A NUMBER beats both, and neither absence rides with it.
        job.move_no = "MVI-26-0999"
        cell = move_reads.move_in_job_reference(job)
        assert cell == {"move_no": "MVI-26-0999", "move_no_unavailable": None}


@pytest.mark.parametrize("bad", ["MVI-99-9999", "not-a-reference", ""])
def test_a_reference_this_tenant_does_not_hold_is_not_found(brazos, dana, bad):
    """**A 404 and never a 403** (HR-1) — the boundary must not confirm that a
    row exists somewhere else. Parameterised over the three shapes a wrong
    reference arrives in: a well-formed number nobody holds, a string that is
    not a reference at all, and an empty path segment."""
    from core import errors

    # ⚠ **`NotFoundError` DERIVES FROM `Exception`, NOT FROM `ApiError`**
    # (`core/errors.py`). The first draft of this case asserted `ApiError` and
    # went red over a product that was refusing correctly — a test looking at
    # the wrong thing, which is the shape hard-won law 7 names.
    with tenant_ctx(brazos), pytest.raises(errors.NotFoundError):
        move_record_reads.record_detail(bad)


def test_the_move_ins_list_keeps_the_pending_job_out_of_move_records(brazos, dana):
    """**`BR-CUS-150` is untouched: no draft is written to `move_records`.**

    The crux of `CR-133-BRC07` §5 in one assertion. A number existing before
    the move happens must not mean a RECORD existing before the move happens,
    and the two live in different tables precisely so that it does not.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 9")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        before = moves.MoveRecord.objects.count()
        sr.approve_and_raise(dana, request.id)
        assert moves.MoveRecord.objects.count() == before
        assert customers_models.Account.objects.filter(
            id__in=[]  # no account was opened either — the Approve drawing's own rule
        ).count() == 0
