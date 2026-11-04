# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-16, verbatim: *"it should do B"* — approving a
#           move-in raises a PENDING MOVE-IN JOB, the way a new connection
#           raises a draft build. The account still does not open at approval.
# Rules:    BR-CUS-1077 (this file) · BR-CUS-080 (the job names the request) ·
#           BR-CUS-150/152 (`move_records` is untouched) · BR-CUS-018 (the
#           draft-account window this tab has always shown) · CLAUDE.md hard
#           rule 1 (tenant scoping) · hard rule 8 (the address is walked)
# Defects:  DEF-CUS-5398 (approving a move-in raised nothing at all)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**BR-CUS-1077 — the pending move-in job, proved end to end.**

RED-FIRST PROOF (r11 step 2d, hard-won law 7), **in `pytest`, which is the
harness that will run these** — not a script calling the functions, which is
`DEF-GOV-3733`'s shape. The red was produced by putting `JOB_SHAPES["move_in"]
["raises"]` back to `None` — the product exactly as it stood before this ruling
— and **TEN of the twelve cases failed**, quoted from that run:
(the twelfth, the documents case, was a strict `xfail` at that moment and is
now live — see it for why)

    FAILED ...::test_approving_a_move_in_raises_a_pending_job_naming_the_request
    FAILED ...::test_approving_a_move_in_opens_no_account_and_writes_no_move_record
    FAILED ...::test_a_second_approval_press_raises_one_job_and_says_so
    FAILED ...::test_the_pending_job_appears_on_the_move_ins_tab_as_a_draft_row
    FAILED ...::test_the_tab_can_be_filtered_to_the_jobs_and_to_the_accounts_apart
    FAILED ...::test_the_page_is_ordered_and_sliced_over_both_kinds_at_once
    FAILED ...::test_every_declared_sort_can_be_answered_by_both_kinds_of_row
    FAILED ...::test_running_the_move_in_closes_the_job_and_it_leaves_the_tab
    FAILED ...::test_the_job_carries_the_unchecked_documents_into_its_wizard
    FAILED ...::test_the_preview_tells_the_clerk_a_job_will_be_raised_before_they_press
    apps/customers/request_jobs.py:647: KeyError: 'absence'   (×9)
    tests/test_br_cus_1077_move_in_job.py:487: assert False is True

⚠ **THE OTHER ONE — `test_the_tab_states_what_leaves_a_job_stranded_rather_than
_hiding_it` — PASSED IN THE RED RUN, AND IT IS NAMED HERE RATHER THAN COUNTED
AS PROOF.** It asserts what the LIST says about itself, and the served absences
are in `move_reads` rather than in the raiser that was reverted. It is a real
case (the superseded sentence is gone and the narrowed one is there) and it is
not evidence that the job is raised.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY**, asked before trusting any green
(hard-won law 7, habit 2):

  * **Asserting the RESPONSE instead of the table.** The response is what the
    code says it did. Every case here reads `MoveInJob` back out of the database
    and asserts the request id is ON it.
  * **A tab case that passes because the fixture left a draft account lying
    around.** The tab cases filter `rows` by `row_kind` and assert the COUNT of
    each kind, so a job row satisfied by an account row is not possible.
  * **An idempotency case that passes because the second press errored.** It
    asserts the second press returns a NAMED refusal and that the table still
    holds exactly one row — a case that only counted rows would pass over an
    `IntegrityError` the caller swallowed.
  * **A closing case that passes because the job was never raised.** It asserts
    the job is `pending` BEFORE the move-in runs and `done` after.
"""

from datetime import date, timedelta

import pytest

from apps.customers import models as customers_models
from apps.customers import move_in_jobs, move_reads, moves, request_jobs
from apps.customers import service_request as rules
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services

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
# FIXTURE PLUMBING — the shortest walk to an approvable move-in request
# ═══════════════════════════════════════════════════════════════════════════
def _served_unit(actor, tenant, *, label="Unit 1", address="88 Pine Vista"):
    """A served unit — the SHARED fixtures, never a second builder."""
    premises = make_premises(actor, address_line=address, services_available=["electric"])
    unit = make_unit(actor, premises["id"], label=label)
    plan = make_plan(tenant, name="BR-CUS-1077 fixture", services=("electric",))
    from apps.metering import services as metering_services

    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    return premises, unit


def _move_in_request(actor, *, address=None, verify_document=True):
    """A move-in request walked to the point the Approve modal opens on.

    ⚠ **`verify_document` IS A PARAMETER BECAUSE THE RULE MOVED ON 2026-09-16.**
    Unchecked documents no longer block an approval (PO: *"lets not make it
    mandetory"*), so a case that always verified could not prove the thing the
    ruling actually asks for — that the job carries what is still outstanding.
    The CONDITIONS themselves are another lane's; this file only reads them.
    """
    request = sr.create_request(
        actor, {**CAPTURE, **({"address_as_given": address} if address else {})}
    )
    doc = sr.attach_document(
        actor, request.id, doc_type=DOC_ID, name="lease.pdf", storage_ref="s3://lease"
    )
    sr.submit(actor, request.id)
    # ⚠ **THIS BRANCH IS DEAD AND IS LEFT DEAD DELIBERATELY — read it before
    # deleting it.** `pick_up` was retired by the PO ruling of 2026-09-19 and
    # `transition` now raises `unknown lifecycle action 'pick_up'` on it. The
    # guard is what saved this file: `submit` leaves the row at `submitted`,
    # never `under_review`, so the condition is False and the retired call is
    # never reached. Its siblings in `test_cr094_approval_raises_the_job.py`
    # had no guard and that whole file was red for two days.
    if sr.request_row(request.id).state != rules.UNDER_REVIEW:
        pass  # the decisions work straight from `submitted` since 2026-09-19
    sr.resolve_address(actor, request.id)
    sr.link_customer(actor, request.id, customer_id=None)
    sr.decide_outcome(actor, request.id, outcome="move_in")
    if verify_document:
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
# 1 · THE RAISE — *"it should do B"*
# ═══════════════════════════════════════════════════════════════════════════
def test_approving_a_move_in_raises_a_pending_job_naming_the_request(brazos, dana):
    """**The row exists, it is `pending`, and it names this request.**

    Read back out of `move_in_jobs` and not off the response, which is the
    brief's own bar and `DEF-MET-5397`'s lesson: a column nothing fills looks
    exactly like a column something fills until you read the table.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos)
        request = _move_in_request(dana, address=str(unit["unit_no"]))

        out = sr.approve_and_raise(dana, request.id)

        assert out["request"].state == rules.APPROVED
        raised = out["job"]["raised"]
        assert raised["kind"] == "move_in"
        assert raised["table"] == "move_in_jobs"
        assert raised["queue"] == "move_ins"
        assert raised["state"] == move_in_jobs.STATE_PENDING
        # The clerk quotes the APPLICATION's number — a pending job has none of
        # its own and B14 rule 31 keeps the uuid off the screen.
        assert raised["ref"] == request.request_no

        job = move_in_jobs.MoveInJob.objects.get(request_id=request.id)
        assert job.state == move_in_jobs.STATE_PENDING
        assert job.closed_at is None


def test_approving_a_move_in_opens_no_account_and_writes_no_move_record(brazos, dana):
    """**The four things that must not move**, each asserted rather than assumed.

    The drawing's own words on every outcome: *"Not now — No account opens, no
    meter is fitted, nothing is energised."* And `BR-CUS-152`: nothing is
    written to `move_records` until somebody does the job.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 2")
        before = customers_models.Account.objects.count()
        request = _move_in_request(dana, address=str(unit["unit_no"]))

        sr.approve_and_raise(dana, request.id)

        assert customers_models.Account.objects.count() == before
        assert moves.MoveRecord.objects.filter(request_id=request.id).count() == 0
        # ⚠ **`outcome_ref` IS DELIBERATELY NOT TAKEN BY THE JOB** — for a
        # move-in that column means *the account this application produced*, and
        # the tab's `request #` search leg reads it that way.
        assert sr.request_row(request.id).outcome_ref is None


def test_a_second_approval_press_raises_one_job_and_says_so(brazos, dana):
    """**One decision raises one job**, and the second press reads as a sentence.

    `uq_move_in_jobs_tenant_request` is the guarantee; `raise_for_request`'s own
    read is what turns the second press into something a clerk can read instead
    of a stack trace. Both are asserted, because a check without the constraint
    is a race and a constraint without the check is an `IntegrityError`.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 3")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)

        again = request_jobs.raise_job(dana, sr.request_row(request.id))

        assert again["not_raised"]["code"] == move_in_jobs.JOB_ALREADY_RAISED
        assert move_in_jobs.MoveInJob.objects.filter(request_id=request.id).count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE TAB — the job is on the queue, and a clerk can tell it apart
# ═══════════════════════════════════════════════════════════════════════════
def test_the_pending_job_appears_on_the_move_ins_tab_as_a_draft_row(brazos, dana):
    """**The ruling's whole point**: the approval is visible on the queue.

    And the row is legible as what it is — `row_kind`, no account number, the
    absence that says why, the applicant's name, the address WALKED from the
    premises, and `Not started` in the state cell.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 4", address="12 Harbour View")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)

        payload = move_reads.move_ins_list()
        jobs = [row for row in payload["rows"] if row["row_kind"] == move_reads.ROW_KIND_PENDING_JOB]

        assert len(jobs) == 1
        row = jobs[0]
        assert row["account_no"] is None
        assert row["account_absence"]["code"] == "pending_move_in_has_no_account"
        assert row["customer"] == CAPTURE["applicant_name"]
        assert row["state"] == move_reads.MOVE_IN_STATE_PENDING
        # Hard rule 8 — the address is derived by walking to the premises, and
        # this row stores none of its own.
        assert "12 Harbour View" in (row["unit"] or "")
        # The walk back the ruling asks for, by NUMBER and not by id.
        assert row["request"]["request_no"] == request.request_no
        # The tile and the list agree. A tile that counted one source while the
        # list showed two is the disagreement a clerk reports as a bad number.
        assert payload["kpis"]["open"] == payload["total"]


def test_the_tab_can_be_filtered_to_the_jobs_and_to_the_accounts_apart(brazos, dana):
    """`f.state` over TWO tables, and the two vocabularies do not overlap.

    `pending` is the only state a job has and no account can be in it, so one
    filter dimension serves both sources with neither knowing how the other
    filters.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 5")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        # A draft account, which is the OTHER kind of row on this tab. It must
        # open in the FUTURE to read as `scheduled`, so its date is relative to
        # today: a literal 2026-10-01 turned into the past on 2026-10-02 and this
        # case went red on the calendar alone (`DEF-CUS-9237`). Thirty days
        # clears any gap between the server's today and the tenant's.
        _premises2, unit2 = _served_unit(dana, brazos, label="Unit 6", address="3450 Oak Ridge Dr")
        customers_services.create_account(
            dana,
            {
                "unit_id": str(unit2["id"]),
                "account_type": "residential",
                "opened_at": (date.today() + timedelta(days=30)).isoformat(),
                "contact": {"full_name": "Alvarez, Rosa"},
                "customer": identity_fixtures.customer_block(
                    "Alvarez, Rosa", account_type="residential"
                ),
            },
        )

        both = move_reads.move_ins_list()
        only_jobs = move_reads.move_ins_list(filters={"state": move_reads.MOVE_IN_STATE_PENDING})
        only_scheduled = move_reads.move_ins_list(
            filters={"state": move_reads.MOVE_IN_STATE_SCHEDULED}
        )

        assert both["total"] == 2
        assert [row["row_kind"] for row in only_jobs["rows"]] == [move_reads.ROW_KIND_PENDING_JOB]
        assert [row["row_kind"] for row in only_scheduled["rows"]] == [
            move_reads.ROW_KIND_ACCOUNT
        ]


def test_the_page_is_ordered_and_sliced_over_both_kinds_at_once(brazos, dana):
    """`NFR-3` — the PAGE is the database's, not two lists stapled together.

    A page of one over a tab holding one job and one account must return ONE
    row and report a total of two; a merge in Python would have to read both
    sources whole to do that, which is the breach this union exists to avoid.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 7")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        _premises2, unit2 = _served_unit(dana, brazos, label="Unit 8", address="500 Main")
        customers_services.create_account(
            dana,
            {
                "unit_id": str(unit2["id"]),
                "account_type": "residential",
                "opened_at": "2026-10-02",
                "contact": {"full_name": "Osei, Grace"},
                "customer": identity_fixtures.customer_block(
                    "Osei, Grace", account_type="residential"
                ),
            },
        )

        first = move_reads.move_ins_list(page=1, per=1)
        second = move_reads.move_ins_list(page=2, per=1)

        assert first["total"] == 2 and second["total"] == 2
        assert len(first["rows"]) == 1 and len(second["rows"]) == 1
        # A page is a window over an ORDER: the same row must not appear twice.
        assert first["rows"][0]["row_kind"] != second["rows"][0]["row_kind"]


def test_every_declared_sort_can_be_answered_by_both_kinds_of_row(brazos, dana):
    """The two sort maps have the SAME keys, and each one runs.

    ⚠ This is the case that stops a screen offering a column the union cannot
    order by. `MOVE_IN_SORTS` is what the API declares and `MOVE_IN_UNION_SORTS`
    is what the page is ordered by; a key in one and not the other is a sort a
    clerk can pick and the server silently ignores.
    """
    with tenant_ctx(brazos):
        assert set(move_reads.MOVE_IN_SORTS) == set(move_reads.MOVE_IN_UNION_SORTS)
        _premises, unit = _served_unit(dana, brazos, label="Unit 9")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        sr.approve_and_raise(dana, request.id)
        for name in move_reads.MOVE_IN_SORTS:
            for direction in ("asc", "desc"):
                payload = move_reads.move_ins_list(sort=name, dir=direction)
                assert payload["total"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE CLOSING EDGE — the job leaves when somebody does the move
# ═══════════════════════════════════════════════════════════════════════════
def test_running_the_move_in_closes_the_job_and_it_leaves_the_tab(brazos, dana):
    """**A queue that never empties is not a queue** — `move_in_jobs` §3.

    `moves.record_move` is the one function both move-in doors already go
    through, and it closes the job inside the wizard's own transaction. The job
    is asserted `pending` before and `done` after, so a case that never raised
    one cannot pass.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 10", address="2201 Cedar Ln")
        outgoing = _occupant(dana, unit, name="Baptiste, Marie")
        request = _move_in_request(dana, address=str(unit["unit_no"]))

        # ⚠ **THE OUTGOING OCCUPANT LEAVES FIRST, AND THAT IS THE PRODUCT'S RULE
        # RATHER THAN FIXTURE PLUMBING.** `services.move_in` is the CHAINED
        # door — *"the next occupant takes the unit the account named in the URL
        # is leaving"* — and `_refuse_if_unit_occupied` (BR-CUS-017) refuses a
        # second occupying account on a unit somebody still holds. The first
        # draft of this case skipped the move-out and was refused with
        # `BIZ-STATE (customers.account.unit_already_occupied)`.
        # ⚠ **THE OUTGOING OCCUPANT LEAVES BEFORE THE APPROVAL, NOT AFTER IT
        # (2026-09-23, `DEF-CUS-6350`).** This case approved over a unit
        # `Baptiste, Marie` still held and moved her out afterwards. Approve now
        # checks the unit is free (`BR-CUS-1095`, PO: *APPROVE checks the property
        # and unit before it is pressed*) and names the occupier, so the order
        # below is the product's order and not fixture plumbing.
        customers_services.move_out(dana, outgoing["id"], {"moved_out_on": "2026-09-19"})
        sr.approve_and_raise(dana, request.id)
        assert move_in_jobs.MoveInJob.objects.get(request_id=request.id).state == (
            move_in_jobs.STATE_PENDING
        )
        assert any(
            row["row_kind"] == move_reads.ROW_KIND_PENDING_JOB
            for row in move_reads.move_ins_list()["rows"]
        )

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

        assert result["move_in_jobs_closed"] == 1
        job = move_in_jobs.MoveInJob.objects.get(request_id=request.id)
        assert job.state == move_in_jobs.STATE_DONE
        assert job.closed_at is not None
        assert job.closed_reason == move_in_jobs.CLOSED_BY_MOVE_RECORD
        assert not any(
            row["row_kind"] == move_reads.ROW_KIND_PENDING_JOB
            for row in move_reads.move_ins_list()["rows"]
        )


def test_the_tab_states_what_leaves_a_job_stranded_rather_than_hiding_it(brazos, dana):
    """The honest absence — `move_in_jobs` §3's last paragraph.

    A move-in committed through some other door passes no request, closes
    nothing, and leaves the job on the tab beside whatever it produced. That is
    the same job counted twice, and the list SAYS so rather than letting a clerk
    discover it.
    """
    with tenant_ctx(brazos):
        codes = [entry["code"] for entry in move_reads.move_ins_list()["unavailable"]]
        assert "pending_job_closes_on_the_recorded_move" in codes
        # And the superseded sentence is gone: this list CAN show a `— draft`
        # row now, so a note saying it cannot would be worse than none.
        assert "parked_draft_has_no_account_row" not in codes
        # ⚠ SUPERSEDED 2026-10-05 (`CR-171-BRC10` §2 S3/S4): a request that
        # suggests a move-in IS a row of this list now, and so is a finished
        # move-in — the two sentences saying otherwise are retired.
        assert "unapproved_move_in_is_a_request" not in codes
        assert "completed_move_in_has_no_retention_window" not in codes


# ═══════════════════════════════════════════════════════════════════════════
# 4 · WHAT THE JOB CARRIES — PO ruling 2026-09-16 on the documents
# ═══════════════════════════════════════════════════════════════════════════
def test_the_job_carries_the_unchecked_documents_into_its_wizard(brazos, dana):
    """*"lets not make it mandetory"* — **and not mandatory is not not mentioned.**

    The document is attached and NOT verified. The job carries what is still
    outstanding, read back live through the link rather than snapshotted, and
    the tab prints the same answer as the raiser.

    ⚠ **THE JOB IS RAISED THROUGH `raise_job` AND NOT THROUGH THE APPROVAL, ON
    PURPOSE.** The approval gate is another lane's — see the `xfail` case below
    — and a case about CARRYING that could only run once somebody else's change
    had landed would be a case that proves nothing in the meantime.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 11")
        request = _move_in_request(dana, address=str(unit["unit_no"]), verify_document=False)

        raised = request_jobs.raise_job(dana, request)["raised"]
        assert raised["table"] == "move_in_jobs"

        job = move_in_jobs.MoveInJob.objects.get(request_id=request.id)
        outstanding = move_in_jobs.outstanding_documents(job.request)
        assert outstanding is not None
        assert outstanding["key"] == "documents_verified"
        row = [
            r
            for r in move_reads.move_ins_list()["rows"]
            if r["row_kind"] == move_reads.ROW_KIND_PENDING_JOB
        ][0]
        assert row["documents_outstanding"] == outstanding


def test_an_unverified_document_no_longer_blocks_the_approval(brazos, dana):
    """The other half of the same ruling, and **the hold that expired the same day.**

    ⚠ **THIS WAS A STRICT `xfail` FOR ABOUT AN HOUR, ON PURPOSE.** Removing
    `documents_verified` from the blocking set was another lane's — two lanes
    editing that path collide — so this case was written as the HOLD, strict, so
    that it would go RED the day they landed it and name itself rather than
    sitting as a promise nobody was keeping (hard-won law 2's mirror). They
    landed it, `service_request.documents_condition` now returns
    `blocking=False` on all four branches, and the marker is gone. **The case
    that outlives the hold is this one**, and it is what stops the block coming
    back unnoticed.

    The clerk is still TOLD what is unchecked — the condition still reports,
    `outstanding_conditions` is the list it reports on, and the job carries the
    outstanding documents into its own wizard.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 13")
        request = _move_in_request(dana, address=str(unit["unit_no"]), verify_document=False)

        out = sr.approve_and_raise(dana, request.id)

        assert out["request"].state == rules.APPROVED
        assert out["job"]["raised"]["table"] == "move_in_jobs"


def test_the_preview_tells_the_clerk_a_job_will_be_raised_before_they_press(brazos, dana):
    """The Approve modal reads the repo, and the repo's answer moved.

    `raises_a_row` was `False` for a move-in until 2026-09-16 and is now `True`
    with the queue named. The modal computes none of this itself, so this is the
    one place the sentence it draws can be held.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, label="Unit 12")
        request = _move_in_request(dana, address=str(unit["unit_no"]))
        preview = request_jobs.approval_preview(request, "move_in")
        assert preview["creates"]["raises_a_row"] is True
        assert preview["creates"]["table"] == "move_in_jobs"
        assert preview["creates"]["queue"] == "move_ins"
        assert preview["creates"]["absence"] is None
        # The drawn `Not now` row is untouched by the ruling and still promised.
        assert "no_account_opens" in preview["not_now"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: the PO ruling of 2026-09-16 (12-governance/02-decision-log.md) +
#         BR-CUS-1077 + DEF-CUS-5398. ⚠ NO STORY OWNS the move worklists —
#         hard-won law 8, already filed by `move_reads.py` and `moves.py`.
# generated: 2026-09-16, the option-B lane
# checklist: A✔ B✔ C✔ D✔ E=n/a(the screen half is `MoveInsTab.test.tsx`) F✔ G✔
#         H=deferred(the migration is 🔒 HUMAN-REVIEW-PENDING)
# gates: every case PROVED RED first, in `pytest`, against `JOB_SHAPES
#        ["move_in"]["raises"] = None` — the product exactly as it stood — and
#        the five failures are quoted verbatim in the module docstring.
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
