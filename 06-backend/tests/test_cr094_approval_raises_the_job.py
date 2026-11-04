# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 — approving a service request RAISES THE JOB.
#           PO 2026-09-15, verbatim: *"pass all information to create the new
#           connect requets or move -in request based on selction"*.
#           Drawn p083–p084 of `05-prototype/02 Accounts Menu Blueprint.pdf`,
#           read AS IMAGES at scale 2 (B14 rule 42).
# Rules:    BR-CUS-080 (the child names the request) · BR-CUS-150/152 (a move
#           record is a completed job) · BR-CUS-091 (a disconnect is not a
#           move-out) · BR-WRK-055 (the flow completes whatever the downstream
#           job does) · BR-CUS-090 (quoted · collected · outstanding) ·
#           CLAUDE.md rule 2 (money 4 dp stored, 2 displayed) · rule 7 (audit)
# Defects:  DEF-CUS-5396 · DEF-MET-5397 · DEF-CUS-5398
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CR-094-BRC01 — **`Approve and raise the build`, proved one outcome at a time.**

RED-FIRST PROOF (r11 step 2d, hard-won law 7), and the red is the product as it
stood rather than a mutation: **every case below was written and run against the
branch BEFORE `apps/customers/request_jobs.py` existed**, and each one failed on
the fact that approving created nothing. Quoted from that run:

    FAILED ...::test_approving_a_new_connection_raises_a_build
    E   AttributeError: module 'apps.customers' has no attribute 'request_jobs'
    (…and, with the module present but `raise_job` returning `{}`:)
    E   assert 0 == 1
    E    +  where 0 = Connection.objects.filter(service_request_id=…).count()

    FAILED ...::test_approving_a_transfer_raises_a_transfer_job
    E   assert 0 == 1  (transfers naming this request)
    FAILED ...::test_approving_a_disconnect_raises_a_case_on_the_notice_ladder
    E   assert 0 == 1  (disconnect_cases naming this request)
    FAILED ...::test_approving_a_move_in_says_by_name_that_no_row_is_raised
    E   KeyError: 'not_raised'
    FAILED ...::test_approving_a_move_out_says_by_name_that_no_row_is_raised
    E   KeyError: 'not_raised'

⚠ **THE HARNESS THAT WILL RUN THESE IS `pytest`, AND THAT IS THE HARNESS THEY
WERE PROVED RED IN** — not a script calling the functions directly, which is
`DEF-GOV-3733`'s shape.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY**, asked before trusting any green
(hard-won law 7, habit 2):

  * **A count taken before the approval.** Every case counts rows NAMING THIS
    REQUEST, on a request the case created itself, so a pre-existing row cannot
    satisfy it.
  * **An assertion on the RESPONSE rather than the database.** The response is
    what the code says it did. So each case reads the row back out of the table
    and asserts the request id is ON it — the brief's own bar.
  * **A move-in case that passes because nothing happened.** `test_approving_a
    _move_in_says_by_name_that_no_row_is_raised` would pass over a silent
    no-op, so it asserts the NAMED code and that the move-record table is still
    empty — the absence has to be stated, not merely true.
"""

from decimal import Decimal as D

import pytest

from apps.customers import disconnects
from apps.customers import models as customers_models
from apps.customers import moves, request_jobs
from apps.customers import service_request as rules
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from tests.fee_quote_helpers import quote_fee  # DEF-CUS-6416: the catalogue prices the line
from apps.customers import services as customers_services
from apps.customers import transfers
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.metering import services as metering_services

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
    "applicant_name": "Miller, Sarah",
    "applicant_email": "s.miller@example.test",
    "applicant_phone": "512-555-0142",
    "address_as_given": "212 Balcones Drive, Unit 3",
    "property_type": "standalone_owner_occupied",
    "what_they_said": "I want service at a new build",
}


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — the shortest walk to a request that can be approved
# ═══════════════════════════════════════════════════════════════════════════
def _served_unit(actor, tenant, *, label="Unit 3", address="212 Balcones Drive"):
    """A SERVED unit — a premises, a unit and one service point on it.

    ⚠ `make_plan` is the SHARED fixture and is used rather than a local one.
    A second plan builder in this file would be a second place `BR-RAT-030`'s
    published-only rule could be got wrong, and the first draft of this file
    had exactly that bug (`Tariff.code` does not exist).
    """
    premises = make_premises(actor, address_line=address, services_available=["electric"])
    unit = make_unit(actor, premises["id"], label=label)
    plan = make_plan(tenant, name="CR-094 fixture", services=("electric",))
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    return premises, unit


class _EveryAccount(dict):
    """A `positions` map answering one figure for any account — the shape
    `tests/test_w7_disconnects.py` established, reused rather than re-invented.

    The LEDGER BOUNDARY is stood up, not faked: `seams.ArPositions` is the real
    class, so `available` and `amount_for` are the product's own.
    """

    def __init__(self, amount):
        super().__init__()
        self._amount = amount

    def get(self, _key, _default=None):
        return self._amount


def _owes(monkeypatch, amount):
    """The account owes money, so the notice ladder is RUNNING.

    ⚠ The balance is the LEDGER's and not `accounts.balance` — `disconnects
    ._balance_for` reads it through `seams.ar_positions`, and a fixture that
    wrote the cached column would prove nothing about the door it is testing.

    ⚠ **PATCHED AT `disconnects._balance_for` AND NOT AT THE SHARED SEAM, AND
    THAT IS A REAL PRODUCT FACT RATHER THAN TEST CONVENIENCE.** `apps.customers
    .seams` is ONE module object, so patching `ar_positions` on it also answers
    the service request's OWN arrears condition — which then blocks the approval
    with `condition.arrearsOutstanding` before any job can be raised. A
    disconnect is the one outcome where the applicant is expected to owe money,
    so the two rules meet head-on. Narrowing the patch keeps this case about the
    RAISE; the collision itself is recorded in the decision log of 2026-09-15
    and filed, because it is the product's and not this file's.
    """
    positions = disconnects.seams.ArPositions(
        positions=_EveryAccount(amount), currency="USD"
    )
    monkeypatch.setattr(disconnects, "_balance_for", lambda _a: amount)
    monkeypatch.setattr(disconnects, "_positions_for_ladder", lambda *_a, **_k: positions, raising=False)


def _occupant(actor, unit, *, name="Miller, Sarah"):
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


def _request_ready_to_approve(actor, *, outcome, address=None, customer_id=None, fee=None):
    """A request walked to the point the drawn modal opens on.

    Draft → submitted → under review → address resolved → customer linked →
    outcome picked → the one required document verified. That last step is the
    gate the drawing insists on (*"Two required documents are still unchecked …
    approval is exactly the thing it blocks"*) and this helper CLEARS it rather
    than skipping it, so every case below runs through the real gate.
    """
    request = sr.create_request(actor, {**CAPTURE, **({"address_as_given": address} if address else {})})
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
    # ⚠ **`PICK_UP` IS RETIRED AND THIS LINE HAD BEEN RED FOR TWO DAYS
    # (fixed 2026-09-21 by lane APP-8, which did not cause it).** The PO ruling
    # of 2026-09-19 — *"see service request i simple - clark submit it - it is
    # revewed, then decision, apporve, refuse or ask for more - that it … we
    # have to keep it simple"* — cut thirteen lifecycle moves to four, and
    # `pick_up` is one of the nine retired. `rules.PICK_UP` is still DEFINED on
    # purpose, so a stale caller gets `ServiceRequestRuleError: unknown
    # lifecycle action 'pick_up'` rather than an `AttributeError` three frames
    # away — which is exactly what this helper got, and it failed **every one
    # of the 17 cases in this file** from `7b8695616` onward.
    #
    # ⚠ **IT WAS THE SAME SHAPE AS HARD-WON LAW 7'S FIRST BULLET — PROVED RED,
    # THEN NEVER READ.** The file names the right things and says so loudly; it
    # simply nobody's job to read a failure they did not cause. It was found by
    # asking *was this red before I started?* and answering it with `git log -S`
    # rather than assuming.
    #
    # The decisions now work straight from `submitted`, which is what the
    # ruling says and what `test_cr031_service_request.py` already asserts.
    sr.resolve_address(actor, request.id)
    sr.link_customer(actor, request.id, customer_id=customer_id, tier="strong" if customer_id else None)
    sr.decide_outcome(actor, request.id, outcome=outcome)
    sr.verify_document(actor, doc.id)
    return sr.request_row(request.id)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · A NEW CONNECTION — *"Raises a build on the New connects tab, linked back
#     to this request."*  DEF-CUS-5396 / DEF-MET-5397
# ═══════════════════════════════════════════════════════════════════════════
def test_approving_a_new_connection_raises_a_build(brazos, dana):
    """The drawn table's second row, end to end: **the build exists, it is a
    DRAFT, and it names this request.**

    ⚠ `connections.request_id` has existed since `CR-030` W6 and nothing has
    ever filled it (`DEF-MET-5397`). The assertion is on the COLUMN, read back
    out of the table, and not on the response.

    ⚠ **2026-09-23 (`DEF-CUS-6350`): AT A NEW ADDRESS, NOT AT ONE IN PREMISES.**
    This case approved a new connection at an address the resolver had matched
    to a served unit. The PO ruled that a new connection is only for an address
    NOT in Premises — *"we should allow only if address is not available in
    register"* — so the case now runs at an address nobody has on file, and the
    build it raises carries no premises until its wizard's last button.
    """
    with tenant_ctx(brazos):
        request = _request_ready_to_approve(dana, outcome="new_connection")
        assert request.resolved_premises_id is None

        out = sr.approve_and_raise(dana, request.id)

        assert out["request"].state == rules.APPROVED
        raised = out["job"]["raised"]
        assert raised["kind"] == "connection"
        assert raised["table"] == "connections"
        assert raised["queue"] == "new_connects"
        assert raised["state"] == work_tables.DRAFT

        # THE ROW, READ BACK FROM THE DATABASE, NAMING THIS REQUEST.
        builds = list(
            work_tables.Connection.objects.filter(service_request_id=request.id)
        )
        assert len(builds) == 1
        # A new address — the wizard writes the premises at its last button.
        assert builds[0].premises_id is None
        # *"No account opens, no meter is fitted, nothing is energised."*
        assert builds[0].owner_account_id is None
        assert builds[0].activated_at is None

        # BR-CUS-080 — the SR alone answers *what happened to this application*.
        after = sr.request_row(request.id)
        assert after.outcome_kind == "connection"
        assert after.outcome_ref == builds[0].connection_no or after.outcome_ref == str(
            builds[0].id
        )


def test_the_requested_start_travels_onto_the_build(brazos, dana):
    """*"Carry the request's information into the job, not merely a link."*

    `target_activation` is the one date column a draft build has, and the
    application's `Requested start` is what belongs in it.

    ⚠ **2026-09-23 (`DEF-CUS-6350`): AT A NEW ADDRESS, NOT AT ONE IN PREMISES.**
    This case approved a new connection at an address the resolver had matched
    to a served unit. The PO ruled that a new connection is only for an address
    NOT in Premises — *"we should allow only if address is not available in
    register"* — so the case now runs at an address nobody has on file, and the
    build it raises carries no premises until its wizard's last button.
    """
    with tenant_ctx(brazos):
        request = _request_ready_to_approve(
            dana, outcome="new_connection", address="9 Ridgeline Way"
        )
        sr.update_request(dana, request.id, {"requested_start": "2026-05-12"})
        sr.approve_and_raise(dana, request.id)
        build = work_tables.Connection.objects.get(service_request_id=request.id)
        assert build.target_activation is not None
        assert build.target_activation.isoformat() == "2026-05-12"


def test_a_new_connection_with_no_resolved_premises_raises_a_draft_with_no_address(
    brazos, dana
):
    """**`DEF-CUS-6109` — the unresolved shape RAISES A DRAFT, and writes no
    property.**

    ⚠ **THIS CASE WAS
    `test_a_new_connection_with_no_resolved_premises_approves_and_says_why_nothing_was_raised`
    AND IT IS REWRITTEN RATHER THAN RE-POINTED.** Its NAME asserted the
    behaviour the PO reversed on 2026-09-21 — *"then approve applciation may
    create a new conenct request - as draft request"* — and its docstring
    repeated the REASON that was measured false (`DEF-MET-6117`): *"creating
    the address would need the mandatory owner `BR-MET-1010` requires and an
    application does not carry"*. `premises.owner_id` is nullable, the owner
    refusal on a premises create was itself reversed on 2026-08-27 (`DEF-650`),
    and `create_premises` opens the owner's master account last in its own
    savepoint. A case whose name states a superseded rule cannot be repaired by
    flipping one assertion.

    **THE TWO HALVES, AND THE SECOND ONE IS THE ONE A FALSE PASS WOULD HIDE:**

      1. a DRAFT build exists, naming this request — not a refusal;
      2. **no `premises` row was created for it.** `BR-MET-112` says nothing is
         written until the wizard's last button, so a clerk who abandons the
         wizard leaves a draft build and no property. Asserting only (1) — or
         only that `outcome_ref` is non-empty — would pass just as happily over
         a build that had quietly created an address at approval, which is the
         exact defect this rule exists to prevent.
    """
    with tenant_ctx(brazos):
        request = _request_ready_to_approve(dana, outcome="new_connection")
        assert request.resolved_premises_id is None
        premises_before = metering_models.Premises.objects.count()

        out = sr.approve_and_raise(dana, request.id)

        assert out["request"].state == rules.APPROVED
        assert "not_raised" not in out["job"]
        assert out["job"]["raised"]["kind"] == "connection"
        assert out["job"]["raised"]["state"] == "draft"

        builds = list(
            work_tables.Connection.objects.filter(service_request_id=request.id)
        )
        assert len(builds) == 1
        # The draft is real, it names the request, and it has NO ADDRESS.
        assert builds[0].premises_id is None
        assert builds[0].state == "draft"
        # `outcome_ref` names THIS build and not merely something — a test that
        # only asked whether it was non-empty would pass on a draft pointing at
        # the wrong build (hard-won law 7: describe the false pass).
        out["request"].refresh_from_db()
        assert out["request"].outcome_ref == builds[0].connection_no
        # ⛛ **AND NOTHING WAS WRITTEN FOR IT** — `BR-MET-112`.
        assert metering_models.Premises.objects.count() == premises_before


def test_a_new_connection_at_an_address_already_in_premises_is_refused_and_raises_nothing(
    brazos, dana
):
    """⛔ **FLIPPED 2026-09-23 — `DEF-CUS-6350`, PO ruling `OQ-CUS-12615`.**

    This case was `test_a_new_connection_at_an_address_already_on_file_raises_a
    _draft_against_it` (`DEF-CUS-6109`'s second shape), and it raised a draft
    build AGAINST a premises already on file. PO, verbatim: *"we should allow
    only if address is not available in register … on active presmies we cannot
    do new conenct - sicne it is physical address and service conenctions build
    process"*, and *"dont create new request even if property is in draft,
    pending or inactive"*. So an address in Premises, in any status, is a
    move-in and never a new connection. The name stated the superseded rule, so
    the case is rewritten rather than re-pointed.

    **Three halves, and the last is the one a false pass would hide:** the press
    is refused by its sentence key naming the PROPERTY (never an id); nothing is
    raised naming this request; and no second premises appears (hard rule 8).
    """
    with tenant_ctx(brazos):
        premises, _unit = _served_unit(dana, brazos, address="900 Pecan Grove")
        request = _request_ready_to_approve(dana, outcome="new_connection")
        customers_models.ServiceRequest.objects.filter(pk=request.id).update(
            resolved_premises_id=premises["id"],
            resolution_kind="exact",
        )
        premises_before = metering_models.Premises.objects.count()

        from core import errors

        with pytest.raises(errors.BizError) as caught:
            sr.approve_and_raise(dana, request.id)
        assert caught.value.message_key == "customers.serviceRequest.condition.addressInPremises"
        assert caught.value.params["condition"] == "address_not_in_premises"
        assert "900 Pecan Grove" in str(caught.value.params["property"])

        assert sr.request_row(request.id).state != rules.APPROVED
        assert not work_tables.Connection.objects.filter(
            service_request_id=request.id
        ).exists()
        assert metering_models.Premises.objects.count() == premises_before


# ═══════════════════════════════════════════════════════════════════════════
# 2 · A TRANSFER — *"One customer, a different address of ours."*
# ═══════════════════════════════════════════════════════════════════════════
def test_approving_a_transfer_raises_a_transfer_job(brazos, dana):
    """A transfer job, `scheduled` at step 1 of 5 — **raised, not done.**"""
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, address="1408 Elm Street", label="Unit B")
        account = _occupant(dana, unit, name="Tan, Wei")
        customer_id = customers_models.CustomerAccount.objects.get(
            account_id=account["id"]
        ).customer_id
        request = _request_ready_to_approve(
            dana,
            outcome="transfer",
            address=str(unit["unit_no"]),
            customer_id=customer_id,
        )

        out = sr.approve_and_raise(dana, request.id)

        raised = out["job"]["raised"]
        assert raised["kind"] == "transfer"
        assert raised["queue"] == "transfers"
        rows = list(transfers.Transfer.objects.filter(request_id=request.id))
        assert len(rows) == 1
        assert rows[0].state == transfers.Transfer.STATE_SCHEDULED
        assert rows[0].step == 1
        assert str(rows[0].from_account_id) == str(account["id"])
        # Raised, not done: nothing has moved yet.
        assert rows[0].to_account_id is None
        assert rows[0].committed_at is None


# ═══════════════════════════════════════════════════════════════════════════
# 3 · A DISCONNECT — *"Raises a case and starts the notice ladder."*
# ═══════════════════════════════════════════════════════════════════════════
def test_approving_a_disconnect_raises_a_case_on_the_notice_ladder(
    brazos, dana, monkeypatch
):
    """`BR-CUS-091` — *"Yes customer can request it"*. The case lands in
    `notice_sent`, which IS the notice ladder starting, and **nothing is cut.**

    ⚠ It is NOT a move-out: the account stays OPEN and accruing (BR-MET-105)
    where a move-out closes it (BR-CUS-030), and this case asserts that
    distinction survives the raise.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, address="1408 Elm Street", label="Unit A")
        account = _occupant(dana, unit, name="Okafor, D.")
        customer_id = customers_models.CustomerAccount.objects.get(
            account_id=account["id"]
        ).customer_id
        # A case only opens where the ladder is RUNNING — something must be
        # owed, and *owed* is the LEDGER's answer.
        _owes(monkeypatch, D("240.0000"))
        request = _request_ready_to_approve(
            dana,
            outcome="disconnect",
            address=str(unit["unit_no"]),
            customer_id=customer_id,
        )

        out = sr.approve_and_raise(dana, request.id)

        assert "raised" in out["job"], out["job"]
        raised = out["job"]["raised"]
        assert raised["kind"] == "disconnect"
        assert raised["queue"] == "disconnects"
        cases = list(disconnects.DisconnectCase.objects.filter(request_id=request.id))
        assert len(cases) == 1
        assert cases[0].state == disconnects.STATE_NOTICE_SENT
        assert str(cases[0].account_id) == str(account["id"])
        # Nothing is cut and the account is not closed.
        assert cases[0].cut_on is None
        assert customers_models.Account.objects.get(pk=account["id"]).closed_at is None


# ═══════════════════════════════════════════════════════════════════════════
# 4 · A MOVE-IN AND A MOVE-OUT — the absence, STATED (DEF-CUS-5398)
# ═══════════════════════════════════════════════════════════════════════════
def test_approving_a_move_out_says_by_name_that_no_row_is_raised(brazos, dana):
    """`request_jobs` §3 — **`move_records` cannot be the raised job**, and the
    product says so rather than doing nothing quietly.

    A move record is written by a flow that has already committed
    (`BR-CUS-150`), it is never updated (`BR-CUS-152`), and it carries the very
    account the job would create — which the drawing forbids approval from
    opening. So the outcome is recorded, the money stays readable, and the
    absence is NAMED.

    ⚠ **THIS CASE WAS PARAMETRIZED OVER `["move_in", "move_out"]` UNTIL
    2026-09-16 AND IS NOW THE MOVE-OUT ALONE (PO ruling, *"it should do B"*,
    `BR-CUS-1077`).** The move-in half is superseded: approving a move-in now
    raises a pending `move_in_jobs` row, and its cases are in
    `tests/test_br_cus_1077_move_in_job.py`.

    **It is rewritten rather than re-pointed, and the NAME is why.** A case
    called *a move says no row is raised* that runs only for a move-out states a
    rule this product no longer has, and the repo has paid for that twice — the
    list-order cases of 2026-09-15 and the applicant-message cases of the same
    week. Flipping one assertion under an old name is how a superseded rule
    survives in the suite.

    ⚠ This case would pass over a silent no-op, so it asserts the CODE as well
    as the empty table.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, address="1408 Elm Street", label="Unit E")
        request = _request_ready_to_approve(
            dana, outcome="move_out", address=str(unit["unit_no"])
        )

        out = sr.approve_and_raise(dana, request.id)

        assert out["request"].state == rules.APPROVED
        assert out["job"]["not_raised"]["code"] == "move_wizard_is_the_record"
        assert moves.MoveRecord.objects.filter(request_id=request.id).count() == 0


def test_the_move_record_names_the_request_when_the_wizard_commits(brazos, dana):
    """The other half of §3: **the link is real, and the wizard fills it.**

    Without this case `move_records.request_id` would be a slot nothing fills —
    hard-won law 2 on data, which is the shape `DEF-837` took.

    ⚠ **A MOVE-OUT REQUEST SINCE 2026-09-23 (`DEF-CUS-6350`).** This approved a
    MOVE-IN onto `Unit C` while `Ncube, T.` still held it, then moved her out.
    Approve now refuses a move-in onto an occupied unit and names the occupier,
    so that order is no longer one the product allows. What this case guards —
    the wizard fills `move_records.request_id` — is the same for the request
    that asks for the move-out, which is the one that names her account.
    """
    with tenant_ctx(brazos):
        _premises, unit = _served_unit(dana, brazos, address="77 Cedar Court", label="Unit C")
        outgoing = _occupant(dana, unit, name="Ncube, T.")
        request = _request_ready_to_approve(
            dana, outcome="move_out", address=str(unit["unit_no"])
        )
        sr.approve_and_raise(dana, request.id)

        customers_services.move_out(
            dana,
            outgoing["id"],
            {"moved_out_on": "2026-08-01", "service_request_id": str(request.id)},
        )
        record = moves.MoveRecord.objects.get(request_id=request.id)
        assert record.kind == moves.KIND_MOVE_OUT
        assert str(record.account_id) == str(outgoing["id"])


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE MONEY — *"The $105.00 still outstanding here travels with it."*
# ═══════════════════════════════════════════════════════════════════════════
def test_the_outstanding_money_travels_by_the_link_and_is_never_copied(brazos, dana):
    """`BR-CUS-090`'s worked figure, on the preview the modal renders.

    Quoted **$130.00**, taken **$25.00** at the counter → **$105.00**
    outstanding, stored at 4 dp and displayed at 2 (CLAUDE.md rule 2).

    ⚠ **`copied_onto_the_job` IS ASSERTED FALSE ON PURPOSE.** None of the four
    job tables has a column meaning *the application's open fee balance*, and a
    second copy of a figure that already has an owner is how two numbers come to
    disagree — `moves.py` §1 and `Transfer`'s docstring each refuse exactly that
    in their own words.

    ⛔ **FLIPPED 2026-09-23 — `DEF-CUS-5399`'s CASE, ON THE THIRD RULING
    (`OQ-CUS-12617` CLOSED, `DEF-CUS-6420`).** Until today this approved WITH
    the $105.00 outstanding, on the 2026-09-21 ruling *"make application fees
    optional - so that we can approve it"*. PO, 2026-09-23: *"either fee is paid
    or waived - no other condition"*. So the press is now REFUSED naming
    $105.00, and the waiver is what releases it. Flipped rather than deleted:
    this case is the one that went red on 2026-09-21 and named the change, and
    it does the same job today. The figure it reads is unchanged, through the
    same reader before and after — which is what proves there is only one place
    it comes from.

    ⚠ At a NEW address since the same day (`DEF-CUS-6350`): a new connection at
    an address in Premises is refused for a different reason, and this case is
    about the money.
    """
    from core import errors

    with tenant_ctx(brazos):
        request = _request_ready_to_approve(
            dana,
            outcome="new_connection",
            fee=D("130.00"),
        )
        # ⚠ A request PART-PAID BEFORE 2026-09-24 (`OQ-CUS-12624`, `DEF-CUS-6455`):
        # the desk now refuses a short payment, so `collect_fee` can no longer
        # make this state and the columns are written as it left them. Rows
        # written before the ruling still hold it — *"requests already part-paid
        # keep what was taken"* — and this preview must go on reading them.
        from apps.customers import models as customers_models

        customers_models.ServiceRequest.objects.filter(id=request.id).update(
            fee_quoted=D("130.0000"),
            fee_collected=D("25.0000"),
            fee_currency="USD",
            fee_method="cash",
            fee_receipt_no="RCP-26-4471",
        )

        preview = request_jobs.approval_preview(sr.request_row(request.id), "new_connection")
        money = preview["carries"]["money"]
        assert money["outstanding"]["display"] == "105.00"
        assert money["outstanding"]["amount"] == "105.0000"
        assert money["travels"] == "by_the_link"
        assert money["copied_onto_the_job"] is False
        # ⛔ True since 2026-09-23 — the money gates approval again.
        assert money["gates_approval"] is True

        with pytest.raises(errors.BizError) as caught:
            sr.approve_and_raise(dana, request.id)
        assert caught.value.message_key == "customers.serviceRequest.condition.feeOutstandingAmount"
        assert caught.value.params["amount"] == "105.0000"
        assert not work_tables.Connection.objects.filter(
            service_request_id=request.id
        ).exists()
        still_owed = request_jobs.carried_money(sr.request_row(request.id))
        assert still_owed["outstanding"]["display"] == "105.00"

        # ── WAIVING RELEASES IT ────────────────────────────────────────────
        # The waiver is addressed by the row's own id (`DEF-CUS-6096`).
        line = customers_models.ServiceRequestFee.objects.get(request_id=request.id)
        sr.waive_fee_line(dana, line.id, reason="Settled at the counter next day")
        sr.approve_and_raise(dana, request.id)
        build = work_tables.Connection.objects.get(service_request_id=request.id)
        carried = request_jobs.carried_money(sr.request_row(build.service_request_id))
        # ⚠ **`-25.00` AND NOT `0.00`, AND THAT IS THE PRODUCT BEING RIGHT.**
        # `fee_total_to_collect`'s own docstring: *"`outstanding` IS SIGNED, and
        # is not clamped at zero"* — waiving the $130.00 line leaves the $25.00
        # the counter took with nothing quoted against it, and a clamp would
        # hide a cash overage from finance. Asserted as the figure it is.
        assert carried["outstanding"]["display"] == "-25.00"
        # ⚠ And nothing was COPIED onto the build — `quote_total` is the BUILD's
        # quote and stays empty until its own wizard's step 7.
        assert build.quote_total is None


# ═══════════════════════════════════════════════════════════════════════════
# 6 · THE PUBLISHED SHAPE — what wave 2's modal renders and must not compute
# ═══════════════════════════════════════════════════════════════════════════
def test_the_preview_carries_the_five_drawn_rows_for_every_outcome(brazos, dana):
    """p084's `WHAT APPROVING WILL DO` — five `THEN` / `WHAT` rows, in order.

    The first, fourth and fifth never change; the second and third do. Asserted
    for all five outcomes so an outcome cannot quietly lose its table.
    """
    with tenant_ctx(brazos):
        request = _request_ready_to_approve(dana, outcome="new_connection")
        for outcome in customers_models.ServiceRequest.JOB_OUTCOMES:
            preview = request_jobs.approval_preview(request, outcome)
            assert preview["known"] is True
            rows = preview["rows"]
            assert [r["then"] for r in rows] == ["now", "now", "now", "next", "not_now"]
            assert rows[0]["what"] == "request_becomes_approved_and_recorded_against_you"
            assert rows[2]["what"] == "the_outstanding_travels_with_it"
            assert rows[4]["what"] == "no_account_no_meter_nothing_energised"
            assert preview["not_now"] == (
                "no_account_opens",
                "no_meter_is_fitted",
                "nothing_is_energised",
            )
            # Every outcome names the queue it feeds and whether it raises a row.
            assert preview["creates"]["queue"]
            assert preview["creates"]["names_this_request"] is True


def test_the_decision_tab_publishes_a_preview_for_every_option(brazos, dana):
    """**The modal reads the repo, not this lane.**

    The detail's decision tab carries one preview per option, keyed by outcome,
    so wave 2 can redraw the drawn table as a radio moves with no round trip and
    no arithmetic of its own.
    """
    with tenant_ctx(brazos):
        request = _request_ready_to_approve(dana, outcome="new_connection")
        row = sr.request_row(request.id)
        panel = reads.decision_tab(row, sr.evidence_for(row), reads.conditions_for(row))
        published = panel["what_approving_will_do"]
        assert set(published) == set(customers_models.ServiceRequest.JOB_OUTCOMES)
        assert published["new_connection"]["creates"]["table"] == "connections"
        # ⚠ **THIS READ `is False` UNTIL 2026-09-16** — the move-in raised no
        # row. `BR-CUS-1077` (PO, *"it should do B"*) gave it one, and the
        # preview is what the modal draws, so the sentence moved here too.
        assert published["move_in"]["creates"]["raises_a_row"] is True
        assert published["move_in"]["creates"]["table"] == "move_in_jobs"
        assert published["disconnect"]["creates"]["table"] == "disconnect_cases"
        assert published["transfer"]["creates"]["table"] == "transfers"


def test_the_preview_names_what_would_stop_the_job_before_the_clerk_commits(brazos, dana):
    """`blockers` — what would stop the RAISE, which never stops the APPROVAL.

    The drawn callout is *"the money does not gate approval and the documents
    do"*, so a request whose job cannot be raised is still approved with the
    reason named. This case proves the preview says so BEFORE the button, which
    is the whole point of a preview.
    """
    with tenant_ctx(brazos):
        # ⛔ **`new_connection` NO LONGER HAS A BLOCKER AND THAT IS
        # `DEF-CUS-6109`** — an unresolved address raises a DRAFT build and the
        # wizard writes the address at its last button, so there is nothing to
        # warn the clerk about. The case is re-pointed at an outcome that
        # genuinely still has one rather than deleted, because what it guards —
        # *the preview says so BEFORE the button* — is unchanged.
        request = _request_ready_to_approve(dana, outcome="new_connection")
        assert request.resolved_premises_id is None
        assert request_jobs.approval_preview(request, "new_connection")["creates"][
            "blockers"
        ] == []

        transfer = request_jobs.approval_preview(request, "transfer")
        codes = [b["code"] for b in transfer["creates"]["blockers"]]
        assert request_jobs.NO_LIVE_ACCOUNT in codes


# ═══════════════════════════════════════════════════════════════════════════
# 7 · THE GUARDS THE RAISE MUST NOT BYPASS
# ═══════════════════════════════════════════════════════════════════════════
def test_an_unverified_document_is_reported_and_the_approval_goes_through(brazos, dana):
    """**PO ruling 2026-09-16 — unchecked documents no longer block.**

    ⚠ **THIS CASE WAS `test_an_unverified_document_still_blocks_and_raises_nothing`
    AND IT WAS REWRITTEN RATHER THAN RE-POINTED.** Its NAME stated the rule the
    PO reversed — *"lets not make it mandetory"* — and a case whose name asserts
    a superseded rule cannot be repaired by flipping one assertion; the result
    reads as a guard for the opposite of what it says it guards. The same
    correction the applicant-message cases took on 2026-09-15.

    **What is guarded now is that the ruling did not buy silence.** The approval
    goes through AND the condition is still reported: not clear, not blocking,
    and named in `outstanding` so the queue and the dialog can both say what is
    still wanted. The PO asked for both halves in one sentence.

    ⚠ **At a new address since 2026-09-23 (`DEF-CUS-6350`)** — a new connection
    at an address in Premises is refused, and this case is not about that.
    """
    with tenant_ctx(brazos):
        sr.set_document_requirement(
            dana, request_type="new_connection", doc_type=DOC_ID, required=True
        )
        request = sr.create_request(dana, dict(CAPTURE))
        sr.attach_document(
            dana, request.id, doc_type=DOC_ID, name="id.pdf", storage_ref="s3://id"
        )
        sr.submit(dana, request.id)
        # `pick_up` is retired — PO 2026-09-19. See `_request_ready_to_approve`.
        sr.resolve_address(dana, request.id)
        sr.link_customer(dana, request.id)
        sr.decide_outcome(dana, request.id, outcome="new_connection")

        # The condition is NOT clear and does NOT block — the two are now
        # different answers, which is the whole of the ruling in code.
        before = reads.conditions_for(sr.request_row(request.id))
        documents = next(c for c in before if c.key == "documents_verified")
        assert documents.clear is False
        assert documents.blocking is False
        assert documents.message_key is not None, "the clerk must still be TOLD which"
        assert [c.key for c in rules.blocking_conditions(before)] == []
        assert [c.key for c in rules.outstanding_conditions(before)] == ["documents_verified"]

        answer = sr.approve_and_raise(dana, request.id)
        assert answer["request"].state == rules.APPROVED
        assert work_tables.Connection.objects.filter(
            service_request_id=request.id
        ).count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CUS-5427 · THE BLOCKER IS KNOWN BEFORE THE PRESS, AND THE OUTCOME IS NOT
#     WRITTEN WHEN THE APPROVAL THAT FOLLOWS IT WILL FAIL
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **RED-FIRST, IN `pytest`, AT `fa61e2a8`** — the tip this lane started from.
# What each one found there is quoted on the case.
def test_the_conditions_can_be_asked_about_an_outcome_nobody_has_picked_yet(
    brazos, dana
):
    """**The clerk's own pick is what creates the blocker, so the question has
    to be askable before the pick.**

    The document checklist is keyed on the OUTCOME (`BR-CUS-095`), so a request
    with nothing decided reports every condition clear — truthfully — over a
    `move_in` that is about to want two documents. Measured on `SR-26-0003` in a
    browser: the commit went live and the refusal arrived after the outcome had
    been saved.

    ⚠ RED at `fa61e2a8`: `TypeError: conditions_for() got an unexpected keyword
    argument 'outcome'`.
    """
    with tenant_ctx(brazos):
        premises, unit = _served_unit(dana, brazos, address="212 Balcones Drive")
        sr.set_document_requirement(
            dana, request_type="move_in", doc_type=DOC_ID, required=True
        )
        request = sr.create_request(
            dana, {**CAPTURE, "address_as_given": str(unit["unit_no"])}
        )
        sr.submit(dana, request.id)
        # `pick_up` is retired — PO 2026-09-19. See `_request_ready_to_approve`.
        sr.resolve_address(dana, request.id)
        sr.link_customer(dana, request.id)
        row = sr.request_row(request.id)
        assert row.outcome is None

        stored = reads.conditions_for(row)
        assert next(c for c in stored if c.key == "documents_verified").clear is True

        considered = reads.conditions_for(row, outcome="move_in")
        documents = next(c for c in considered if c.key == "documents_verified")
        assert documents.clear is False
        assert documents.blocking is False

        # …and the same answer rides on the decision tab, per option, which is
        # what the modal reads as a radio moves.
        tab = reads.decision_tab(row, sr.evidence_for(row), stored)
        assert tab["what_approving_will_do"]["move_in"]["conditions"]["outstanding"] == [
            "documents_verified"
        ]
        assert tab["what_approving_will_do"]["new_connection"]["conditions"]["outstanding"] == []


def test_a_refused_approval_leaves_no_outcome_behind(brazos, dana, monkeypatch):
    """**The whole of `DEF-CUS-5427`'s second half, on real PostgreSQL.**

    The dialog used to post the decision and then the approval. When the SECOND
    failed the first had already been written and the request sat at `Under
    review` carrying an outcome — looking decided while being nothing of the
    kind. The outcome now travels WITH the approval, inside one transaction.

    The blocker here is the ARREARS question, which the 2026-09-16 ruling
    deliberately left standing: it asks whether anybody looked, which is a
    question about a person and cannot be answered later by a job.

    ⚠ RED at `fa61e2a8`: `TypeError: approve_and_raise() got an unexpected
    keyword argument 'outcome'`.

    ⚠ **AND IT IS A POSTGRES CASE (hard-won law 14).** The rollback being proved
    is a real one; on SQLite a half-written outcome could survive a shape of
    this bug that PostgreSQL refuses outright.
    """
    from core import errors

    with tenant_ctx(brazos):
        premises, unit = _served_unit(dana, brazos, address="212 Balcones Drive")
        request = sr.create_request(
            dana, {**CAPTURE, "address_as_given": str(unit["unit_no"])}
        )
        sr.submit(dana, request.id)
        # `pick_up` is retired — PO 2026-09-19. See `_request_ready_to_approve`.
        sr.resolve_address(dana, request.id)
        # NOT linked — so *nobody has looked* and the arrears condition blocks.
        row = sr.request_row(request.id)
        assert row.outcome is None
        assert [c.key for c in rules.blocking_conditions(reads.conditions_for(row))] == [
            "no_blocking_arrears"
        ]

        with pytest.raises(errors.BizError):
            sr.approve_and_raise(dana, request.id, outcome="new_connection")

        after = sr.request_row(request.id)
        # ⚠ **`submitted`, NOT `under_review` — PO ruling 2026-09-19
        # (`DEF-CUS-6105`).** This read `UNDER_REVIEW` because the helper above
        # used to move the row there with `pick_up`, which is one of the nine
        # retired moves. The decisions now work straight from `submitted` and
        # nothing auto-writes a state on the way in, which is what
        # `test_cr031_service_request.py` already asserts in its own words.
        # **What this line is FOR is unchanged: a refused approval must not
        # move the row**, and it still proves that — against the state the row
        # is actually in.
        assert after.state == rules.SUBMITTED
        # ⚠ THE ASSERTION THE WHOLE DEFECT IS ABOUT.
        assert after.outcome is None, "a refused approval wrote the outcome anyway"
        assert after.decided_at is None
        assert (
            customers_models.ServiceRequestEvent.objects.filter(
                request=after, note_type="outcome:new_connection"
            ).count()
            == 0
        )


def test_the_outcome_travels_with_the_approval_when_nothing_blocks(brazos, dana):
    """The happy half of the same door: one call, both writes.

    ⚠ RED at `fa61e2a8`: `TypeError: approve_and_raise() got an unexpected
    keyword argument 'outcome'`.

    ⚠ **At a new address since 2026-09-23 (`DEF-CUS-6350`)** — a new connection
    at an address in Premises is refused, and this case is not about that.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, dict(CAPTURE))
        sr.submit(dana, request.id)
        # `pick_up` is retired — PO 2026-09-19. See `_request_ready_to_approve`.
        sr.resolve_address(dana, request.id)
        sr.link_customer(dana, request.id)
        assert sr.request_row(request.id).outcome is None

        answer = sr.approve_and_raise(dana, request.id, outcome="new_connection")
        after = sr.request_row(request.id)
        assert after.outcome == "new_connection"
        assert after.state == rules.APPROVED
        assert answer["request"].state == rules.APPROVED


def test_one_approval_raises_one_job_even_when_called_twice(brazos, dana):
    """`BR-CUS-080` — *"one SR cannot silently produce two live children for one
    decision"*. A double-click is an ordinary event.

    ⚠ **At a new address since 2026-09-23 (`DEF-CUS-6350`)** — a new connection
    at an address in Premises is refused, and this case is not about that.
    """
    with tenant_ctx(brazos):
        request = _request_ready_to_approve(dana, outcome="new_connection")
        sr.approve_and_raise(dana, request.id)
        second = request_jobs.raise_job(dana, sr.request_row(request.id))
        assert second["not_raised"]["code"] == request_jobs.ALREADY_LINKED
        assert work_tables.Connection.objects.filter(
            service_request_id=request.id
        ).count() == 1


def test_every_raise_writes_an_audit_row(brazos, dana, audit_rows):
    """CLAUDE.md rule 7 — the decision that creates a job is accountable.

    ⚠ Asserted against the `audit_rows` CAPTURE SINK and not against
    `AuditLog`. The shared `test_us_met_helpers` fixture replaces the platform
    sink with a list for the length of a test, so a query on the table finds
    **nothing** and an assertion written that way passes or fails for a reason
    that has nothing to do with the code under test — law 7's *looking at the
    wrong thing*, which this case hit on its first run (`AssertionError: []`).

    ⚠ **At a new address since 2026-09-23 (`DEF-CUS-6350`)** — a new connection
    at an address in Premises is refused, and this case is not about that.
    """
    with tenant_ctx(brazos):
        request = _request_ready_to_approve(dana, outcome="new_connection")
        sr.approve_and_raise(dana, request.id)
        raised_rows = [r for r in audit_rows if r["action"] == "service_request.job_raised"]
        assert len(raised_rows) == 1, sorted({r["action"] for r in audit_rows})
        row = raised_rows[0]
        assert row["entity_type"] == "service_request"
        assert str(row["entity_id"]) == str(request.id)
        assert row["after"]["table"] == "connections"
        assert row["after"]["kind"] == "connection"
