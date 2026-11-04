# ── Trace ──────────────────────────────────────────────
# Change:   CR-031 (PO 2026-08-24) · B19 (the PO's screenshots, read screen by
#           screen)   Screens: REQ-01 · REQ-02 · REQ-03.1..6 · REQ-03.sent
# Rules:    BR-CUS-079 · BR-CUS-080 · BR-CUS-070 · B18 §4.6 · CLAUDE.md rules
#           1 (RLS FORCE), 2 (money 4dp/CHAR(3)), 4 (append-only events),
#           6 (idempotent numbering), 7 (audit)
# Questions: OQ-351 · OQ-355 · OQ-356 · OQ-357
# Defects:  DEF-632 · DEF-634 · DEF-635 · DEF-637 · DEF-638
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CR-031 W4 — the service-request object and its lifecycle.

RED-FIRST PROOF (r11 step 2d). **Every guard below was broken FIRST and its
failure quoted before it was trusted green.** Nine mutations, one per guard, each
applied to this tree and reverted (harness in the lane's scratchpad):

  1. numbering made non-idempotent — the `if request.request_no:` short-circuit
     in `allocate_number` removed →
        FAILED ...::test_numbering_is_idempotent
        E  - SR-26-0056
        E  + SR-26-0057
  2. `submit` wired to `allocate_number` (the DEF-634 trigger somebody will be
     tempted to add) →
        FAILED ...::test_no_transition_allocates_a_number
        E  where 'SR-26-0001' = <ServiceRequest …>.request_no
  3. `attach_document` landing `VERIFIED` instead of `NOT_CHECKED` →
        FAILED ...::test_attaching_is_not_verifying
        E  AssertionError: assert 'verified' == 'not_checked'
  4. the approve gate reading no blocking conditions →
        FAILED ...::test_an_unverified_document_blocks_approval
        E  Failed: DID NOT RAISE BizError
     ⚠ **THAT CASE NO LONGER EXISTS UNDER THAT NAME, AND THE RED IT RECORDS IS
     NOW THE PRODUCT (2026-09-16, `BR-CUS-1078`).** The PO ruled that unchecked
     documents no longer block an approval — *"lets not make it mandetory"* —
     so `sr.approve` correctly DOES NOT RAISE here, and the case was rewritten
     as `test_an_unverified_document_is_reported_and_the_approval_goes_through`.
     The record above is left standing because it is the history of how this
     file was proved, not a claim about the product today.
  5. `fee_condition` never blocking on an outstanding line →
        FAILED ...::test_an_unsettled_fee_line_blocks_approval_and_a_waiver_clears_it
  6. `link_child` with its `outcome_ref` guard deleted →
        FAILED ...::test_one_sr_produces_one_live_child
        E  Failed: DID NOT RAISE BizError
  7. `update_request` allowing `address_as_given` after submission (BR-CUS-070) →
        FAILED ...::test_address_as_given_is_never_overwritten
        E  Failed: DID NOT RAISE BizError
  8. the identifier fields silently DROPPED instead of refused (DEF-632) →
        FAILED ...::test_def632_the_identifier_is_refused_by_name
        E  Failed: DID NOT RAISE BizError
  9. the `disconnect` outcome allowed to commit (DEF-638 12.a) →
        FAILED ...::test_def638_a_disconnect_outcome_is_refused_by_name
        E  Failed: DID NOT RAISE BizError

⚠ **THE TENANT-ISOLATION CASE RUNS UNDER THE NON-SUPERUSER PROBE ROLE.** A plain
ORM query inside `tenant_ctx` runs as the app's superuser role and **bypasses
RLS unconditionally**, so an assertion made that way is VACUOUS and has fooled
this repo before (`tests/isolation_helpers.py`, DEF-101 — twelve rating cases
skipped on the one database that could have proved anything). The case at the
bottom carries `requires_postgres` and asserts through `assert_rls_scoped` /
`assert_no_foreign_rows_anywhere`.

⚠ **AND IT SKIPPED IN THE LANE'S OWN CONTAINER, WHICH IS WORTH READING BEFORE
TRUSTING A GREEN RUN.** Two environment faults stopped it, neither introduced
here and both proved pre-existing against `tests/test_us_led_005_gl_designations.py`,
a file this lane never touched:

  * **DEF-622 / OQ-354** — `migrate` cannot reach the end of a fresh Postgres
    database, because three data migrations end by clearing `app.tenant_id` to
    `''` at session level and the deferred FK validation at those same
    migrations' exit then fails with
        django.db.utils.DataError: invalid input syntax for type uuid: ""
        CONTEXT: SQL statement "SELECT fk."tenant_id" FROM ONLY "public"."meter_types" …"
  * the probe-role fixture needs SUPERUSER to run
    `ALTER ROLE sbh_rls_probe NOSUPERUSER NOBYPASSRLS`, and the container's app
    role has neither SUPERUSER nor CREATEROLE, so the fixture skips with its own
    "RLS HALF NOT EXERCISED" reason rather than passing vacuously.

────────────────────────────────────────────────────────────────────────────
⚠ **THE 2026-08-24 SURFACE LANE RE-RAN THIS AND IT IS STILL SKIPPING, FOR A
DIFFERENT REASON THAN IT WAS THAT MORNING. READ THIS BEFORE TRUSTING A GREEN
RUN.**
────────────────────────────────────────────────────────────────────────────
A live PostgreSQL 16 **is** reachable in this container, and a fresh database +
a SUPERUSER role were provisioned for the attempt (so the probe fixture's
`ALTER ROLE … NOSUPERUSER NOBYPASSRLS` would have worked). `migrate` still could
not reach the end, and the failure has MOVED:

    RuntimeError: app.tenant_id is the empty string at the end of the EIN
    backfill. Leave the nil-uuid sentinel instead
    (db/001_tenant_context_default.sql, DEF-639).
    apps/tenancy/migrations/_0018_helpers.py:99

**Cause, measured rather than assumed.** OQ-354 option (A) — substituting the
nil sentinel for `''` in the three data migrations that clear tenant context —
is **still not applied**: `apps/assets/migrations/0003…:100`,
`apps/metering/migrations/0016…:66` and
`apps/tenancy/migrations/0004…:157` each still end
`SELECT set_config('app.tenant_id', '', false)`. That is SESSION level, and
pytest-django migrates in ONE session, so every later migration in the run
inherits `''`. What is new is that BR-CUS-092's EIN backfill now ASSERTS the
condition, so the old silent `DataError` is a named `RuntimeError` — an
improvement, and the same blocker.

**None of those three files is this lane's**, so the fix is not taken here.

────────────────────────────────────────────────────────────────────────────
**SO THE NEW POLICY WAS PROVED BY HAND, AND THIS ONE IS A REAL RUN ON REAL
POSTGRES — not a rehearsal of the morning's.**
────────────────────────────────────────────────────────────────────────────
`service_request_document_requirements` (migration 0020) was built on live
PostgreSQL 16 with its policy text **copied verbatim from the migration**, and
every assertion was made under `SET ROLE sbh_l5_probe`, verified
`rolsuper=f rolbypassrls=f` in the same transcript — so FORCE really applied and
nothing was measured on a connection that bypasses RLS:

  1. tenant A: **1 row** (its own) · 2. tenant B: **1 row**, and **0** of A's
  3. `app.tenant_id` set to `''` → **0 rows, NO ERROR**
  4. `app.tenant_id` RESET → **0 rows, NO ERROR**
  5. `INSERT` into B's tenant → `ERROR: new row violates row-level security
     policy for table "service_request_document_requirements"`; re-stamping A's
     own row with B's tenant id → the same refusal; A's row untouched.

⚠ **(3) AND (4) ARE THE WHOLE POINT OF THE `NULLIF` FORM AND ARE WHY THIS POLICY
IS NOT WRITTEN LIKE THE OTHER 34.** The bare
`current_setting('app.tenant_id')::uuid` **raises** on a blank or missing GUC
instead of denying, which is what makes a fresh database un-buildable (DEF-639 /
OQ-354). Deny-by-default is preserved exactly — 0 rows, both ways — with one
fewer way to brick a deploy.

**What is still OWED and is NOT claimed here:** the five ORIGINAL CR-031 tables
have only the morning lane's hand proof, and **no automated `-m isolation` run
has ever executed against this module on Postgres.** That stays true until the
three migrations above leave the sentinel.

**And the morning lane's own record, kept verbatim:**

**So the policies were proved by hand instead, on a live PostgreSQL 16 database
built around DEF-622, under a role that is `rolsuper=f rolbypassrls=f` (so FORCE
really applied to it):** two tenants, a request plus one row in each of the four
child tables for tenant Alpha — Beta saw **0** rows in all five tables and Alpha
saw **1** in each; with `app.tenant_id` cleared, every read raised
`invalid input syntax for type uuid: ""` (deny-by-default); and re-stamping
Alpha's row with Beta's tenant id was refused with
`new row violates row-level security policy for table "service_requests"`
(the WITH CHECK half). The evidence is in the lane report. **This case still has
to be run for real** on an environment where the probe role can be created —
what is written above is a hand proof, not a passing test.
"""

import json
from datetime import date, timedelta
from decimal import Decimal

import uuid

import pytest

from core import errors

from apps.audit import models as audit_models
from apps.customers import models as customers_models
from apps.customers import service_request as rules
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from tests.fee_quote_helpers import quote_fee  # DEF-CUS-6416: the catalogue prices the line

from tests.isolation_helpers import (
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

SR_TABLES = (
    "service_requests",
    # BR-CUS-095's checklist — added 2026-08-24 with migrations 0019/0020. A
    # SETTINGS table, which is where the temptation to skip RLS is strongest,
    # because nobody's NAME is in it. What IS in it is one utility's compliance
    # posture: exactly which documents they demand before they will connect
    # anybody. A cross-tenant WRITE is worse than a read — ticking
    # `proof_of_identity` on another tenant's `move_in` blocks every one of
    # their approvals until somebody finds the row.
    "service_request_document_requirements",
    "service_request_services",
    "service_request_documents",
    "service_request_fees",
    "service_request_events",
)

#: REQ-03's own worked capture — `14 Willow Bend`, the address B19 §7 renders
#: as `Not on record`.
CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Okonkwo, David",
    "applicant_email": "david@example.test",
    "applicant_phone": "555-0142",
    "address_as_given": "14 Willow Bend, Springfield",
    "property_type": "standalone_owner_occupied",
    "what_they_said": "I'm moving into somewhere",
}


#: **BR-CUS-095's eight designed types are a CLOSED vocabulary now**, because a
#: checklist tick can only be satisfied by an attachment carrying the same name.
#: These three stand in for the free-text `photo_id` / `proof_of_address` /
#: `deed` this file used before the ruling.
DOC_ID = customers_models.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY
DOC_ADDRESS = customers_models.ServiceRequestDocument.DOC_PROOF_OF_ADDRESS
DOC_DEED = customers_models.ServiceRequestDocument.DOC_TENANCY_OR_DEED
DOC_AGREEMENT = customers_models.ServiceRequestDocument.DOC_SIGNED_AGREEMENT


def _seed_sr_series(tenant, opening=1):
    """The `service_request` series IS seeded at provisioning; open it at a
    known counter so the numbers in these assertions come out of the product."""
    from apps.tenancy import models as tenancy_models

    tenancy_models.NumberSeries.objects.update_or_create(
        tenant=tenant,
        series="service_request",
        defaults={"format": "SR-{YY}-{0000}", "next_number": opening},
    )


def _new(actor, **overrides):
    payload = {**CAPTURE, **overrides}
    return sr.create_request(actor, payload)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════
def test_a_request_opens_as_a_draft_and_is_numbered_at_creation(brazos, dana):
    """**BR-CUS-093 (PO 2026-08-24, closing DEF-634): *"At creation — every
    draft is numbered"*.**

    This test used to assert the exact opposite, and the reason it changed is
    the reason the PO gave: the clerk reads `SR-26-0048` down the phone while
    the form is still half-filled. REQ-03's `Save as draft` is on every one of
    the six steps, so a row has to exist before step 2 — and now so does its
    identity."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos, opening=48)
        request = _new(dana)
        assert request.state == rules.DRAFT
        assert request.request_no == "SR-26-0048"
        # The absence is GONE, because there is nothing absent.
        assert reads.list_row(request)["number_absence"] is None


def test_the_happy_path_walks_draft_to_approved_and_stops_there(brazos, dana):
    """⚠ **THIS USED TO WALK TO `completed` AND THE WALK IS NOW FOUR STATES
    LONG — PO ruling 2026-09-19.** It ran
    `draft → submitted → under_review → approved → in_fulfilment → on_hold →
    in_fulfilment → completed`, and five of those moves no longer exist:
    *"once requets is approved then in move in or new connect we take all those
    decision to in fulfill etc - youa re mising too many thing hre - we have to
    keep it simple"*.

    **Approved is the end of the request.** What happens next happens to the
    JOB the approval raises, in another module, and this object stops having an
    opinion about it.

    ⚠ **AND THERE IS NO `pick_up` IN THE MIDDLE ANY MORE.** The decision works
    straight from `submitted` — the PO chose that when both were put to them
    (*"a is correct"*), so nothing auto-writes a state and the row moves when a
    real decision is made.
    """
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.submit(dana, request.id)
        assert sr.request_row(request.id).state == rules.SUBMITTED

        sr.resolve_address(dana, request.id)
        sr.link_customer(dana, request.id)  # searched, nobody found
        sr.decide_outcome(dana, request.id, outcome="new_connection")
        sr.approve(dana, request.id)
        assert sr.request_row(request.id).state == rules.APPROVED


def test_the_nine_retired_moves_are_all_refused_by_name(brazos, dana):
    """⚠ **THE GUARD THAT GOES RED IF ANY OF THE NINE COMES BACK BY ACCIDENT.**

    PO ruling 2026-09-19 left the request five states. Each of these nine was a
    control somewhere in the product a week ago, and the danger is not that one
    is re-added deliberately — it is that one is re-added to make a stale test
    pass. **A refusal by NAME is asserted, not merely an exception:** an
    unknown action and a disallowed one must both arrive as
    `transitionNotAllowed`, which is what makes the portal's dead withdraw
    endpoint answer a customer cleanly instead of raising (`OQ-CUS-12486`).
    """
    with tenant_ctx(brazos):
        assert set(rules.RETIRED_ACTIONS) == {
            "pick_up",
            "info_received",
            "route",
            "hold",
            "resume",
            "complete",
            "withdraw",
            "reopen",
            "manual_close",
        }
        for action in rules.RETIRED_ACTIONS:
            assert action not in rules.TRANSITIONS, f"{action} is back in the state table"
            request = _new(dana)
            sr.submit(dana, request.id)
            with pytest.raises(errors.BizError) as caught:
                sr.transition(dana, request.id, action, reason="a reason, in case one is asked")
            assert caught.value.message_key == "customers.serviceRequest.transitionNotAllowed", (
                f"{action} was refused, but not in words a screen can show"
            )


def test_the_state_table_is_exactly_the_five_states_the_po_ruled(brazos, dana):
    """⚠ **THE OTHER HALF: the moves that must STILL be there, and from where.**

    Approve, refuse and ask-for-more each work from `submitted`, `under_review`
    and `more_info`. The first of those three is the ruling — a clerk decides a
    submitted request without pressing anything first — and it is the one a
    tidy-up would most plausibly undo.
    """
    assert set(rules.TRANSITIONS) == {"submit", "approve", "refuse", "request_info"}
    for action in ("approve", "refuse", "request_info"):
        allowed_from, _ = rules.TRANSITIONS[action]
        assert rules.SUBMITTED in allowed_from, f"{action} no longer works from submitted"
        assert rules.MORE_INFO in allowed_from, f"{action} no longer works from more_info"
    # Every state a request can be put into, derived rather than listed.
    reachable = {lands_in for _, lands_in in rules.TRANSITIONS.values()}
    assert reachable == {"submitted", "approved", "refused", "more_info"}


def test_an_unlawful_transition_is_refused_by_name(brazos, dana):
    """`approve` from `draft` is not a rounding error — it is skipping the
    review the whole object exists for."""
    with tenant_ctx(brazos):
        request = _new(dana)
        with pytest.raises(errors.BizError) as caught:
            sr.transition(dana, request.id, rules.COMPLETE)
        assert caught.value.message_key == "customers.serviceRequest.transitionNotAllowed"


def test_refuse_needs_a_reason_and_keeps_the_request(brazos, dana):
    """TC-REQ-9 · *"Refusing keeps the request and its reason on record."*"""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.submit(dana, request.id)
        with pytest.raises(errors.ValidationError):
            sr.refuse_request(dana, request.id, reason="   ")
        sr.refuse_request(dana, request.id, reason="Arrears at a previous address")
        row = sr.request_row(request.id)
        assert row.state == rules.REFUSED
        assert row.outcome == customers_models.ServiceRequest.OUTCOME_REFUSED
        assert customers_models.ServiceRequest.objects.filter(id=request.id).exists()


def test_a_refusal_is_terminal_and_its_reason_stays_on_the_timeline(brazos, dana):
    """⚠ **TC-REQ-10 REWRITTEN — THERE IS NO REOPEN (PO ruling 2026-09-19).**
    It used to refuse, REOPEN, and assert the refusal survived in the event log.
    `reopen` is one of the nine retired moves: **refuse is terminal, and a
    reapplication is a NEW request.** p085 names `Reopen` explicitly, and this
    is the one place the state table knowingly contradicts the drawing.

    **The half of TC-REQ-10 that mattered is unchanged and is still asserted
    here:** `service_request_events` is APPEND-ONLY and the refusal's reason
    stays readable. B18 §5.3.3 keeps a refused request *because someone turned
    down for arrears at a previous address simply reapplies* — that reasoning
    now argues for keeping the RECORD so the next application can be judged
    against it, rather than for reopening this one.
    """
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.submit(dana, request.id)
        sr.refuse_request(dana, request.id, reason="No proof of address")
        row = sr.request_row(request.id)
        assert row.state == rules.REFUSED
        notes = [e["note"] for e in reads.history_tab(row)]
        assert "No proof of address" in notes
        # Terminal means terminal: there is no move out of `refused` at all.
        assert rules.actions_available(rules.REFUSED) == ()
        with pytest.raises(errors.BizError) as caught:
            sr.transition(dana, request.id, "reopen", reason="They brought the letter in")
        assert caught.value.message_key == "customers.serviceRequest.transitionNotAllowed"
        assert sr.request_row(request.id).state == rules.REFUSED


def test_manual_close_is_retired_and_refuses_in_words_a_screen_can_show(brazos, dana):
    """⚠ **REWRITTEN — `Close by hand` IS GONE (PO ruling 2026-09-19).** It was
    one of the two buttons that started this whole change: the PO put the
    screen beside its drawing and said of it *"this is not required."*, and
    neither `Withdraw` nor `Close by hand` appears once in the blueprint's 242
    pages.

    The service function is KEPT and now refuses, rather than being deleted —
    same reasoning as the portal's withdraw endpoint (`OQ-CUS-12486`): a door
    that has been live is better answering in words than raising.
    """
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.submit(dana, request.id)
        with pytest.raises(errors.BizError) as caught:
            sr.manual_close(dana, request.id, reason="The job will never run")
        assert caught.value.message_key == "customers.serviceRequest.transitionNotAllowed"
        # And the request is exactly where it was — a refused close closes nothing.
        assert sr.request_row(request.id).state == rules.SUBMITTED


# ═══════════════════════════════════════════════════════════════════════════
# 2 · NUMBERING — idempotent, and triggered by nothing (DEF-634)
# ═══════════════════════════════════════════════════════════════════════════
def test_numbering_is_idempotent(brazos, dana):
    """TC-REQ-2 · CLAUDE.md rule 6 — *"the same draft submitted twice → one
    number, not two"*. The second call consumes nothing from the series."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos, opening=56)
        request = _new(dana)
        # Creation consumed exactly one number (BR-CUS-093) …
        assert request.request_no == "SR-26-0056"
        # … and re-calling the allocator neither re-numbers nor consumes.
        again = sr.allocate_number(dana, request.id)
        assert again == {"request_no": "SR-26-0056", "allocated": False}

        other = _new(dana)
        assert other.request_no == "SR-26-0057"
        assert sr.allocate_number(dana, other.id)["allocated"] is False


def test_no_transition_allocates_a_number(brazos, dana):
    """**BR-CUS-093 consequence (e), asserted:** *"`submit` no longer allocates
    anything, so a repeated submit is a state transition on a row that already
    has its identity — the idempotency key is the request itself."*

    The number is fixed at creation and NOTHING downstream may move it. This
    test is what stops a later lane re-wiring `submit` to the allocator: doing
    so would give the request a second number after a clerk had read the first
    one out."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos, opening=70)
        request = _new(dana)
        assert request.request_no == "SR-26-0070"
        sr.submit(dana, request.id)
        assert sr.request_row(request.id).request_no == "SR-26-0070"


def test_br_cus_093_an_abandoned_draft_burns_its_number_and_the_gap_stays(brazos, dana):
    """**BR-CUS-093 consequence (a), verbatim: *"GAPS ARE NORMAL AND MUST NOT BE
    TREATED AS LOSS — an abandoned draft burns its number permanently; nothing
    renumbers, backfills or reuses, and no report may present a gap as a missing
    record."***

    This is the cost the PO accepted in exchange for the clerk being able to
    quote a number down the phone, and it is the clause a well-meaning lane
    would "fix". So it is pinned: `SR-26-0081` is abandoned, `0082` is NOT
    given to the next request, and nothing anywhere hands `0081` out again."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos, opening=81)
        abandoned = _new(dana)
        assert abandoned.request_no == "SR-26-0081"
        # ⚠ **THIS USED TO WITHDRAW THE DRAFT, AND `withdraw` IS RETIRED (PO
        # ruling 2026-09-19).** The rule under test is BR-CUS-093's, not the
        # withdrawal's: a number, once allocated, is never handed out again.
        # An abandoned draft is now simply a draft nobody comes back to —
        # ⚠ **there is no disposal path for a draft at all**, which is a real
        # consequence of the ruling and is reported rather than worked around
        # here: `refuse` is lawful from `submitted` onwards and a draft has not
        # reached it.
        assert sr.request_row(abandoned.id).state == rules.DRAFT
        assert "withdraw" in rules.RETIRED_ACTIONS

        # The next request takes the NEXT number. The gap is not filled.
        following = _new(dana)
        assert following.request_no == "SR-26-0082"

        # …and the burnt number is still on the abandoned row, so a clerk
        # holding a note that says SR-26-0081 still finds what happened to it.
        assert sr.request_row(abandoned.id).request_no == "SR-26-0081"
        assert not hasattr(sr, "renumber")
        assert not hasattr(sr, "compact_numbers")


def test_br_cus_093_a_repeated_submit_is_idempotent(brazos, dana):
    """**BR-CUS-093 consequence (e), verbatim: *"IDEMPOTENCY GETS SIMPLER, NOT
    HARDER (hard rule 6): `submit` no longer allocates anything, so a repeated
    submit is a state transition on a row that already has its identity — the
    idempotency key is the request itself."***

    A double-click must not send the customer two acknowledgements or write two
    state rows. And because `submitted_at` carries the fact, the replay is still
    a no-op forty minutes later when the request has moved to `Under review`."""
    with tenant_ctx(brazos):
        request = _new(dana)
        first = sr.submit(dana, request.id)
        assert first["idempotent_replay"] is False
        events_after_first = customers_models.ServiceRequestEvent.objects.filter(
            request_id=request.id
        ).count()

        second = sr.submit(dana, request.id)
        assert second["idempotent_replay"] is True
        assert sr.request_row(request.id).state == rules.SUBMITTED
        assert (
            customers_models.ServiceRequestEvent.objects.filter(request_id=request.id).count()
            == events_after_first
        )

        # …and the replay survives the request moving on. ⚠ **IT MOVES ON BY
        # BEING PARKED NOW.** This read `sr.transition(…, PICK_UP)` until the PO
        # ruling of 2026-09-19 retired that move; park is the one control left
        # that takes a request out of `submitted`, so the case still proves what
        # it was written to prove — a replay forty minutes later, after the row
        # has moved — rather than being weakened to re-assert `submitted`.
        sr.park(dana, request.id, waiting_on="documents", note="Chased the lease")
        assert sr.request_row(request.id).state == rules.UNDER_REVIEW
        third = sr.submit(dana, request.id)
        assert third["idempotent_replay"] is True
        assert sr.request_row(request.id).state == rules.UNDER_REVIEW


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE TWO DOCUMENT GATES
# ═══════════════════════════════════════════════════════════════════════════
def test_attaching_is_not_verifying(brazos, dana):
    """The detail's `BLOCKING` callout, verbatim: *"attaching a file is not the
    same as verifying it."*"""
    with tenant_ctx(brazos):
        request = _new(dana)
        doc = sr.attach_document(
            dana, request.id, doc_type=DOC_ID, name="licence.pdf", storage_ref="s3://x"
        )
        assert doc.verification_state == customers_models.ServiceRequestDocument.NOT_CHECKED
        assert doc.verified_at is None


def test_a_missing_document_never_blocks_creation(brazos, dana):
    """GATE ONE — REQ-03.4's `NOT BLOCKING` callout: *"A missing document does
    not stop the request being created."*"""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.attach_document(dana, request.id, doc_type=DOC_ADDRESS, required=True)
        result = sr.submit(dana, request.id)
        assert result["request"].state == rules.SUBMITTED
        assert reads.documents_tab(sr.request_row(request.id))["blocks_creation"] is False


def test_an_unverified_document_is_reported_and_the_approval_goes_through(brazos, dana):
    """GATE TWO IS NO LONGER A GATE — PO ruling 2026-09-16, `BR-CUS-1078`,
    verbatim: *"lets not make it mandetory"*.

    ⚠ **THIS CASE WAS `test_an_unverified_document_blocks_approval` AND WAS
    REWRITTEN RATHER THAN RE-POINTED.** Its NAME stated the rule the PO
    reversed, and a case whose name asserts a superseded rule cannot be repaired
    by flipping one assertion — the result reads as a guard for the opposite of
    what it claims to guard. Its old docstring quoted *"1 document still to
    verify. Approval is blocked until somebody checks each one."*; the second
    sentence is superseded and the third — *attaching a file is not the same as
    verifying it* — is still true and is still said.

    **What is guarded now is that the ruling did not buy silence:** the approval
    goes through AND the condition still reports, so the queue and the dialog
    can say what is still wanted.
    """
    with tenant_ctx(brazos):
        request = _new(dana)
        doc = sr.attach_document(
            dana, request.id, doc_type=DOC_ID, name="id.pdf", storage_ref="s3://id"
        )
        sr.submit(dana, request.id)
        sr.resolve_address(dana, request.id)
        sr.link_customer(dana, request.id)
        sr.decide_outcome(dana, request.id, outcome="new_connection")

        # Reported, not refused — and the two are now different lists.
        conditions = reads.conditions_for(sr.request_row(request.id))
        documents = next(c for c in conditions if c.key == "documents_verified")
        assert documents.clear is False
        assert documents.blocking is False
        assert documents.message_key == "customers.serviceRequest.condition.documentsUnverified"
        assert [c.key for c in rules.outstanding_conditions(conditions)] == ["documents_verified"]

        sr.approve(dana, request.id)
        assert sr.request_row(request.id).state == rules.APPROVED

        # …and verifying it still clears the condition, which is the half of the
        # old case that survives the ruling untouched.
        sr.verify_document(dana, doc.id)
        after = reads.conditions_for(sr.request_row(request.id))
        assert next(c for c in after if c.key == "documents_verified").clear is True


def test_a_document_with_no_file_cannot_be_verified(brazos, dana):
    """A clerk certifying nothing is worse than a blank row."""
    with tenant_ctx(brazos):
        request = _new(dana)
        doc = sr.attach_document(dana, request.id, doc_type=DOC_DEED, required=True)
        with pytest.raises(errors.BizError) as caught:
            sr.verify_document(dana, doc.id)
        assert caught.value.message_key == "customers.serviceRequest.documentHasNoFile"


def test_documents_move_by_reference_and_are_never_copied(brazos, dana):
    """**BR-CUS-080's third clause.** Handing off to a child creates NO new
    document row: *"one uploaded file stays ONE row and the audit trail of who
    supplied it survives the hand-off, where a copy would fork it."*"""
    with tenant_ctx(brazos):
        request = _new(dana)
        doc = sr.attach_document(
            dana, request.id, doc_type=DOC_ID, name="id.pdf", storage_ref="s3://id"
        )
        sr.submit(dana, request.id)
        sr.resolve_address(dana, request.id)
        sr.link_customer(dana, request.id)
        sr.decide_outcome(dana, request.id, outcome="new_connection")
        sr.verify_document(dana, doc.id)
        before = customers_models.ServiceRequestDocument.objects.count()

        # ⛔ **THE HAND-OFF IS THE APPROVAL ITSELF SINCE `DEF-CUS-6109`
        # (2026-09-21).** This case used to approve and then call `link_child`
        # by hand with an invented `CON-` number, because approving a request
        # whose address had not resolved raised nothing to link. It does now
        # — PO ruling of that day, *"approve applciation may create a new
        # conenct request - as draft request"* — so the hand-made call is
        # refused by `BR-CUS-080`'s own idempotency (*one decision, one job*),
        # which is the rule working rather than a regression. The REAL hand-off
        # is what is measured now, and it is a stronger case: it walks the path
        # a clerk walks instead of a reference nobody issued.
        sr.approve(dana, request.id)
        assert sr.request_row(request.id).outcome_ref, "the approval raised no child to hand to"

        carried = sr.documents_for_origin(request.id)
        assert customers_models.ServiceRequestDocument.objects.count() == before
        assert [d.id for d in carried] == [doc.id]
        assert carried[0].uploaded_by_id == dana.id  # the audit survives
        assert not hasattr(sr, "copy_documents_to")


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE CONDITIONS THAT GATE APPROVAL
# ═══════════════════════════════════════════════════════════════════════════
def test_approval_needs_an_outcome_first(brazos, dana):
    """`Commit` badged `Nothing picked` — *"Pick what this becomes before
    approving. Until then there is no job to start."*"""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.submit(dana, request.id)
        with pytest.raises(errors.BizError) as caught:
            sr.approve(dana, request.id)
        assert caught.value.message_key == "customers.serviceRequest.outcomeRequired"


def test_an_unsettled_fee_line_blocks_approval_and_a_waiver_clears_it(brazos, dana):
    """⛔ **FLIPPED BACK 2026-09-23 (`OQ-CUS-12617` CLOSED, `DEF-CUS-6420`).** PO,
    verbatim: *"either fee is paid or waived - no other condition"*. The fee
    blocks again, so this case once more asserts that `approve` is REFUSED
    naming `$25.00`, and then that the waiver clears it and the approval goes
    through. Renamed, because *"is reported"* now describes a rule the product
    no longer has. The 2026-09-21 paragraph below is left visible so the chain
    can be read.

    ⛔ **REWRITTEN 2026-09-21 — PO: *"make application fees optional - so
    that we can approve it"*.** This case asserted that `approve` RAISED
    `feeOutstandingAmount`; REQ-03.5's *"it simply cannot be approved yet"* is
    SUPERSEDED in that half, and `BR-CUS-090` clause (1) carries the amendment.

    ⚠ **THE WAIVER HALF IS UNTOUCHED AND IS NOW THE POINT OF THE CASE.** The
    PO ruled *"waiving is options"* the same day: a reason is still required,
    the waiver is still recorded against the acting user, and it still clears
    the figure. What changed is only that the clerk was never stuck waiting for
    it.

    ⚠ Since BR-CUS-090 the condition reads the OUTSTANDING FIGURE, not a line
    count — see the assertion below."""
    with tenant_ctx(brazos):
        request = _new(dana)
        fee = quote_fee(
            dana,
            request.id,
            charge_code="CC-REQFEE",
            unit_amount=Decimal("25.00"),
            basis="per request",
            description="Application processing fee",
        )
        assert fee.amount == Decimal("25.0000")
        assert len(fee.currency) == 3
        sr.submit(dana, request.id)
        sr.resolve_address(dana, request.id)
        sr.link_customer(dana, request.id)
        sr.decide_outcome(dana, request.id, outcome="new_connection")

        # ⚠ **THE KEY CHANGED WITH BR-CUS-090.** It used to be a LINE COUNT,
        # because DEF-637 left the figure contradicted. The review step reads
        # the OUTSTANDING FIGURE and the condition names it — it REPORTS it
        # since 2026-09-21 rather than refusing on it.
        conditions = reads.conditions_for(sr.request_row(request.id))
        outstanding = next(c for c in conditions if c.key == "fee_settled")
        assert outstanding.message_key == (
            "customers.serviceRequest.condition.feeOutstandingAmount"
        )
        assert outstanding.params["amount"] == "25.0000"
        assert outstanding.blocking is True  # ⛔ blocking again, 2026-09-23

        with pytest.raises(errors.BizError) as caught:
            sr.approve(dana, request.id)
        assert caught.value.message_key == (
            "customers.serviceRequest.condition.feeOutstandingAmount"
        )
        assert caught.value.params["amount"] == "25.0000"

        with pytest.raises(errors.ValidationError):
            sr.waive_fee_line(dana, fee.id, reason="")
        sr.waive_fee_line(dana, fee.id, reason="Goodwill — the meter test was ours")
        assert customers_models.ServiceRequestFee.objects.get(id=fee.id).waived_by_id == dana.id
        # …and the condition is CLEAR once it is waived, which is the half of
        # this case that the ruling did not touch.
        cleared = next(
            c for c in reads.conditions_for(sr.request_row(request.id)) if c.key == "fee_settled"
        )
        assert cleared.state == rules.CONDITION_CLEAR
        sr.approve(dana, request.id)
        assert sr.request_row(request.id).state == rules.APPROVED


def test_arrears_are_unknown_rather_than_zero_when_the_books_cannot_be_asked(brazos, dana):
    """DEF-127's law, applied to this condition: **an absent answer is never
    spelled the same way as zero.** A customer with a prior account whose ledger
    position cannot be read blocks; it never reports *nothing outstanding*."""
    with tenant_ctx(brazos):
        request = _new(dana)
        condition = rules.arrears_condition(
            search_done=True, amount_owed=None, books_unavailable_reason="ledger_unwired"
        )
        assert condition.state == rules.CONDITION_UNKNOWN
        assert condition.blocking is True
        assert not condition.clear
        # and an unsearched request blocks too — nobody has looked yet
        assert reads.conditions_for(request)[0].state == rules.CONDITION_BLOCKED


def test_eligibility_never_blocks_either_way(brazos, dana):
    """B19 draws *"None claimed — does not block"*; B18 §5.3.4 states the rule
    for the other branch too — eligibility *"Never blocks service — only the
    discount"*."""
    assert rules.eligibility_condition(claimed=False).blocking is False
    assert rules.eligibility_condition(claimed=True).blocking is False


def test_the_conditions_panel_says_four_and_states_why_not_five(brazos, dana):
    """⚠ **OQ-355.** The screen renders *"4 of 5 conditions clear"* and four are
    identifiable. A payload printing `5` would claim to have checked something
    it cannot name."""
    with tenant_ctx(brazos):
        request = _new(dana)
        summary = rules.conditions_summary(reads.conditions_for(request))
        assert summary["total"] == 4
        assert summary["count_differs_from_design"] == {
            "designed_total": 5,
            "served_total": 4,
            "tracks": "OQ-355",
        }


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE RESOLVER SUGGESTS; THE CLERK DECIDES
# ═══════════════════════════════════════════════════════════════════════════
def test_an_unknown_address_resolves_to_no_premise_and_fits_a_new_connection(brazos, dana):
    """The Location tab: `Resolved to → No premise record` · `Consequence →
    This becomes a new connection`."""
    with tenant_ctx(brazos):
        request = _new(dana)
        evidence = sr.resolve_address(dana, request.id)
        assert evidence.resolution_kind == "no_premise"
        row = sr.request_row(request.id)
        assert row.no_premise_flag is True
        assert row.lookup_found == sr.LOOKUP_NO_PREMISE
        verdicts = {v["outcome"]: v["verdict"] for v in rules.outcome_verdicts(evidence)}
        assert verdicts["new_connection"] == rules.FITS_THE_EVIDENCE
        # ⚠ **BR-CUS-091 WITHDREW THE `not_possible` REASON FOR A DISCONNECT.**
        # It is `possible` — *the evidence does not rule this out and nothing
        # rules it in* — and NOT `fits_the_evidence`, which no screen draws for
        # it. Which evidence state should fit a disconnect is OQ-356.
        assert verdicts["disconnect"] == rules.POSSIBLE


def test_the_drawn_screenshot_reproduces_exactly(brazos, dana):
    """B19 §12.3's verdict table, on its own evidence — served, and the unit is
    vacant.

    ⚠ **IT WAS ONE `fits` AND FOUR `not possible`; IT IS NOW ONE `fits`, TWO
    `not possible` AND TWO `possible`.** Two drawn sentences have been
    WITHDRAWN, each on a ruling, and neither row gained a badge nobody drew:

      * **`disconnect`** — `BR-CUS-091`, PO 2026-08-24, *"Yes customer can
        request it"*. The screen said a disconnect *"is only ever started by
        collections, never from a customer request"*; the list drew one anyway,
        and the ruling says the list was right.
      * **`new_connection`** — `DEF-CUS-6109`, 2026-09-21, **and the drawing
        settled this one rather than a ruling in words.** The screen said
        *"There is already a premise record at this address"* and greyed the
        option on every matched address. **Accounts blueprint p089, read AS AN
        IMAGE at scale 2.4 (`B14` rule 42), draws `A new connection` LIVE on
        `SR-26-0001`**, whose own detail on p088 reads `Matched premises ·
        PR-0731 · exact`, over the callout *"Nothing is preselected,
        deliberately. The resolver matched this address to PR-0731 exactly, and
        that is EVIDENCE — not the decision."* An existing property with no
        service is an ordinary new connection."""
    evidence = rules.Evidence(
        resolution_kind="served_vacant",
        premise_exists=True,
        unit_is_served=True,
        unit_is_vacant=True,
        applicant_holds_account_here=False,
        applicant_holds_live_account_anywhere=False,
    )
    rows = rules.outcome_verdicts(evidence)
    assert [r["outcome"] for r in rows] == [
        "new_connection",
        "move_in",
        "move_out",
        "transfer",
        "disconnect",
    ]
    assert [r["verdict"] for r in rows] == [
        rules.POSSIBLE,
        rules.FITS_THE_EVIDENCE,
        rules.NOT_POSSIBLE,
        rules.NOT_POSSIBLE,
        rules.POSSIBLE,
    ]
    # Every DRAWN refusal still carries the PO's own sentence …
    assert all(r["message_key"] for r in rows if r["verdict"] == rules.NOT_POSSIBLE)
    # … and BOTH withdrawn ones carry NONE, because inventing a replacement
    # sentence is exactly what OQ-356 exists to stop.
    assert rows[0]["message_key"] is None
    assert rows[-1]["message_key"] is None


def test_a_served_vacant_unit_fits_a_move_in(brazos, dana):
    """The resolver reads the real premises/units tables and BR-MET-036's
    derived vacancy — an active account ⇒ occupied, none ⇒ vacant."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="88 Pine Vista")
        # SERVED: a unit with a service point. `unit_is_served` is what
        # separates *"the unit is served and vacant"* from a bare unit row.
        unit = make_unit(dana, premises["id"], label="A", services=["electric"])
        request = _new(dana, address_as_given=unit["unit_no"])
        evidence = sr.resolve_address(dana, request.id)
        assert evidence.premise_exists is True
        assert evidence.unit_is_served is True
        assert evidence.unit_is_vacant is True
        assert sr.request_row(request.id).lookup_found == sr.LOOKUP_SERVED_VACANT
        assert rules.verdict_for("move_in", evidence) == rules.FITS_THE_EVIDENCE
        # ⛔ **THIS READ `NOT_POSSIBLE` UNTIL `DEF-CUS-6109` (2026-09-21).** A
        # served, vacant unit FITS a move-in and does not RULE OUT a new
        # connection — blueprint p089 draws the option live on an address
        # matched exactly. What the evidence fits and what it forbids are two
        # questions, and this case only ever measured the first.
        assert rules.verdict_for("new_connection", evidence) == rules.POSSIBLE


def test_nothing_is_preselected(brazos, dana):
    """*"Nothing is preselected. Approving creates real service and real
    charges, so the decision is made deliberately."*"""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.resolve_address(dana, request.id)
        panel = reads.decision_tab(
            sr.request_row(request.id),
            sr.evidence_for(sr.request_row(request.id)),
            reads.conditions_for(sr.request_row(request.id)),
        )
        assert panel["preselected"] is None
        assert panel["commit"]["outcome"] is None
        assert sr.request_row(request.id).outcome is None


def test_the_clerk_may_override_the_evidence_and_it_is_recorded_not_refused(brazos, dana):
    """CR-031 ruled the CLERK decides. So a pick the evidence marked
    `not_possible` STANDS — and the disagreement is recorded with the verdict
    table exactly as it stood."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.submit(dana, request.id)
        sr.resolve_address(dana, request.id)  # no premise → move_out is not possible
        sr.decide_outcome(dana, request.id, outcome="move_out", note="They rang to leave")
        row = sr.request_row(request.id)
        assert row.outcome == "move_out"
        assert row.decided_against_evidence is True
        assert row.evidence_snapshot["decided"] == "move_out"
        assert len(row.evidence_snapshot["verdicts"]) == 5


# ═══════════════════════════════════════════════════════════════════════════
# 6 · PARK AND RESUME — two controls, not one
# ═══════════════════════════════════════════════════════════════════════════
def test_park_records_what_is_awaited_and_picks_a_submitted_request_up(brazos, dana):
    """B19 §12.2 — `waiting_on` is a COLUMN, orthogonal to state.

    ⚠ **THIS CASE WAS NAMED `…_and_moves_no_state` AND ASSERTED THE OPPOSITE
    UNTIL 2026-09-19.** The PO's ruling that day retired `pick_up`, which was
    the only way into `under_review` — so park inherited that one move, and only
    that one: *a clerk who parks a submitted request has self-evidently picked
    it up*, and the blueprint's own register draws `SR-26-0042` as **Under
    review, waiting on a supervisor**, which is precisely a parked request.

    **Both halves are asserted, because only the pair is the rule:** park moves
    `submitted` → `under_review`, and park moves NOTHING from any other state.
    """
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.submit(dana, request.id)
        remind = date.today() + timedelta(days=7)
        sr.park(
            dana,
            request.id,
            waiting_on="documents",
            note="Chased the tenancy agreement",
            remind_on=remind,
        )
        row = sr.request_row(request.id)
        assert row.state == rules.UNDER_REVIEW  # picked up by the parking
        assert row.waiting_on == "documents"
        assert row.remind_on == remind
        assert reads.list_row(row)["waiting_on"] == "documents"
        with pytest.raises(errors.ValidationError):
            sr.park(dana, request.id, waiting_on="  ")

        # ⚠ **THE OTHER HALF: FROM ANYWHERE ELSE PARK MOVES NOTHING.** A parked
        # `more_info` request is still waiting on the APPLICANT, and moving it
        # would take it off the queue their answer belongs to.
        asked = _new(dana)
        sr.submit(dana, asked.id)
        sr.transition(dana, asked.id, rules.REQUEST_INFO, reason="Send the lease")
        assert sr.request_row(asked.id).state == rules.MORE_INFO
        sr.park(dana, asked.id, waiting_on="documents", note="Applicant chasing landlord")
        assert sr.request_row(asked.id).state == rules.MORE_INFO


def test_resume_clears_the_park_and_keeps_the_note_on_the_timeline(brazos, dana):
    """*"Everything entered stays… and the note goes on its timeline."*"""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.submit(dana, request.id)
        sr.park(dana, request.id, waiting_on="payment", note="Cheque promised Friday")
        sr.resume(dana, request.id, note="Cheque cleared")
        row = sr.request_row(request.id)
        assert row.waiting_on is None
        # ⚠ **RESUME CLEARS THE PARK AND DOES NOT UNDO THE PICK-UP.** Parking
        # moved this to `under_review` (PO ruling 2026-09-19); the clerk who
        # stops waiting has still got the request in their hands, so the state
        # stays and only the awaited-on column is cleared.
        assert row.state == rules.UNDER_REVIEW
        assert "Cheque promised Friday" in [e["note"] for e in reads.history_tab(row)]


def test_save_and_exit_is_the_quieter_control(brazos, dana):
    """`Save & exit` sets no `waiting_on` — that is the whole difference."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.save_and_exit(dana, request.id, {"applicant_phone": "555-0199"})
        row = sr.request_row(request.id)
        assert row.waiting_on is None
        assert row.applicant_phone == "555-0199"


# ═══════════════════════════════════════════════════════════════════════════
# 7 · BR-CUS-070 · BR-CUS-079 · BR-CUS-080
# ═══════════════════════════════════════════════════════════════════════════
def test_address_as_given_is_never_overwritten(brazos, dana):
    """BR-CUS-070, drawn as a footnote: *"The address as the applicant gave it
    is kept verbatim and never overwritten by the resolved record."* TC-REQ-6
    asks for it byte-identical to submission."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="3450 Oak Ridge Dr")
        unit = make_unit(dana, premises["id"], label="1")
        request = _new(dana, address_as_given=unit["unit_no"])
        given = request.address_as_given
        sr.submit(dana, request.id)
        sr.resolve_address(dana, request.id)
        row = sr.request_row(request.id)
        assert row.address_as_given == given
        assert row.resolved_unit_id is not None
        with pytest.raises(errors.BizError) as caught:
            sr.update_request(dana, request.id, {"address_as_given": "somewhere else"})
        assert caught.value.message_key == "customers.serviceRequest.addressAsGivenImmutable"


def test_submitting_records_the_acknowledgement_absence_never_a_sent_state(brazos, dana):
    """**BR-CUS-079 (CONFIRMED)** — and its own clause about absence.

    No delivery adapter exists in this product, and `notifications.SOURCE_TYPES`
    has no `service_request` kind, so the acknowledgement cannot even be QUEUED
    yet. What is recorded is the ABSENCE with its reason — never `sent` (hard-won
    law 1)."""
    with tenant_ctx(brazos):
        request = _new(dana)
        result = sr.submit(dana, request.id)
        ack = result["acknowledgement"]
        assert ack["sent"] is False
        assert ack["state"] in (sr.ACK_NOT_SENT, sr.ACK_QUEUED)
        assert ack["reason"]
        row = sr.request_row(request.id)
        assert row.acknowledgement_state == ack["state"]
        assert row.acknowledgement_absence_reason


def test_an_applicant_with_no_email_or_phone_records_that_reason(brazos, dana):
    with tenant_ctx(brazos):
        request = _new(dana, applicant_email=None, applicant_phone=None)
        result = sr.submit(dana, request.id)
        assert result["acknowledgement"]["reason"] == sr.ACK_NO_ADDRESS


def test_one_sr_produces_one_live_child(brazos, dana):
    """**BR-CUS-080** — *"one SR cannot silently produce two live children for
    one decision"*, and the SR alone answers *"what happened to this
    application"*."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.submit(dana, request.id)
        sr.resolve_address(dana, request.id)
        sr.link_customer(dana, request.id)
        sr.decide_outcome(dana, request.id, outcome="new_connection")
        # ⛔ **THE CHILD IS RAISED BY THE APPROVAL SINCE `DEF-CUS-6109`** — a
        # hand-made `link_child("CON-26-0117")` after it is now refused by the
        # very rule this case guards, so the case would have been proving its
        # own rule against a number no build carries. It takes the build the
        # approval actually raised, which is what a clerk gets.
        sr.approve(dana, request.id)
        row = sr.request_row(request.id)
        raised = row.outcome_ref
        assert raised, "approving a new connection must raise a build to link"
        assert (row.outcome, row.outcome_kind) == ("new_connection", "connection")
        with pytest.raises(errors.BizError) as caught:
            sr.link_child(dana, request.id, child_ref="CON-26-0118")
        assert caught.value.message_key == "customers.serviceRequest.childAlreadyLinked"


def test_a_child_cannot_be_linked_before_an_outcome_is_decided(brazos, dana):
    with tenant_ctx(brazos):
        request = _new(dana)
        with pytest.raises(errors.BizError) as caught:
            sr.link_child(dana, request.id, child_ref="MVI-26-0001")
        assert caught.value.message_key == "customers.serviceRequest.outcomeRequired"


# ═══════════════════════════════════════════════════════════════════════════
# 8 · EVERY REFUSAL BY NAME — the defects this lane would not decide
# ═══════════════════════════════════════════════════════════════════════════
def test_br_cus_092_the_ssn_is_captured_and_the_rest_stay_refused(brazos, dana):
    """✅ **SUPERSEDED 2026-08-27 — DEF-632 IS CLOSED FOR THE SSN.**

    This case asserted the OPPOSITE until today: *"the identifier is refused
    until its encryptor exists"*. It was right when it was written — `OQ-016`
    had closed on app-layer encryption and nothing had been built, so a column
    here would have been clause (d)'s false promise over a government
    identifier.

    **Both preconditions are now met.** `core/crypto.py` exists (AES-256-GCM,
    a fresh 96-bit nonce per write, AAD binding a ciphertext to its column) and
    the PO ruled, verbatim: *"We need to capture SSN and encript it; we have to
    ensure it is working"*. So `ssn` is captured, encrypted at rest and served
    as its last four.

    ⚠ **WHAT THIS CASE NOW GUARDS IS THE SIZE OF THE WIDENING.** The PO ruled on
    the Social Security number on 2026-08-27, and on the date of birth and the
    driving licence on 2026-09-15 — not on identifiers in general. A later lane
    reading *"identifiers are storable now"* would open eleven more columns on
    the strength of one sentence. The at-rest, off-the-wire, off-the-trail and
    fails-closed proofs live in `tests/test_br_cus_092_ssn_capture.py`.
    """
    with tenant_ctx(brazos):
        request = sr.create_request(dana, {**CAPTURE, "ssn": "452-88-4471"})
        # Stored, and stored ENCRYPTED — asserted properly next door; here it is
        # enough that the write is accepted and reads back as what was typed.
        assert request.ssn == "452-88-4471"
        assert reads.applicant_tab(request)["identifier"] == {
            "ssn_last4": "4471",
            "ssn_present": True,
            "stored_encrypted": True,
            # ⚠ **THE LICENCE JOINED THIS DICT ON 2026-09-15** (PO ruling
            # finishing BR-CUS-092(a)) and this applicant gave none — so every
            # licence key reads EMPTY, and `drivers_licence_stored_encrypted`
            # must be False rather than absent: a screen that drew the promise
            # from a missing key would print it over a blank column.
            "drivers_licence_last4": None,
            "drivers_licence_present": False,
            "drivers_licence_stored_encrypted": False,
            # ⊕ **AND THE TAX ID JOINED IT ON 2026-10-02 (`DEF-CWP-9045`)** — a
            # business's number as typed on its PORTAL application, read from
            # the draft (`OQ-CWP-1560` (b)). A counter request has none.
            "tax_id_last4": None,
            "tax_id_present": False,
        }

        # …and the other identifier names still answer BIZ_STATE, by name.
        for field in (
            "social_security_number",
            "gov_id",
            "gov_id_number",
            "id_number",
            "national_id",
            "ein",
            "tin",
            # ⊕ `gov_id_last4` LEFT on 2026-10-18 (lane CF-1): Move-in's
            # *Government ID*, kept as its last four (BR-CUS-045) — see
            # `IDENTIFIER_FIELDS`. Its acceptance is proved in
            # `tests/test_cf1_customer_forms_2026_10_18.py`.
            "ssn_last4",
            "drivers_licence_last4",
            "acting_for",
        ):
            with pytest.raises(errors.BizError) as caught:
                sr.create_request(dana, {**CAPTURE, field: "4471"})
            assert caught.value.message_key == "customers.serviceRequest.identifierNotStorable"

    # ⚠ **`date_of_birth` AND `dob` LEFT THIS LIST ON 2026-09-15** — PO ruling
    # finishing BR-CUS-092(a). `date_of_birth` is captured; `dob` is refused as
    # an ALIAS with the canonical name in the message, which is a different
    # refusal and is proved in `tests/test_br_cus_092_licence_and_dob_capture.py`.
    #
    # ⚠ **AND `capture_applicant_identifier` IS GONE, NOT SILENCED.** It existed
    # to state that the driving licence had no home; it has one. The stub for
    # `suggest_customer_matches` stands and its reason was corrected the same
    # day: the fields exist now and nobody has built a matcher over them.
    with pytest.raises(NotImplementedError, match="BR-CUS-089"):
        sr.suggest_customer_matches()
    assert not hasattr(sr, "capture_applicant_identifier")

    field_names = {f.name for f in customers_models.ServiceRequest._meta.get_fields()}
    assert {"ssn", "drivers_licence", "drivers_licence_bidx", "date_of_birth"} <= field_names
    # ⚠ NO `_last4` COLUMN FOR EITHER ENCRYPTED IDENTIFIER. The last four is a
    # READ projection; a stored one would put four characters back in the
    # clear beside the ciphertext. (`gov_id_last4` is not one of them: the
    # government ID has only ever been kept as four — BR-CUS-045, lane CF-1.)
    assert not (field_names & {"ssn_last4", "drivers_licence_last4", "gov_id", "acting_for"})


def test_def638_acting_for_is_refused_by_name_and_the_dob_half_is_CLOSED(brazos, dana):
    """DEF-638 12.b named TWO fields and the PO ruled on one of them.

    ⚠ **THIS CASE USED TO ASSERT THAT THE DATE OF BIRTH WAS REFUSED, AND THAT
    WAS RIGHT UNTIL 2026-09-15.** The defect's own sentence was *"the detail
    matches ON the date of birth and the six-step capture form never asks for
    it"*; the form asks now, so the half is closed and only `acting_for` stands
    — it has no column, no vocabulary and no ruling.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            sr.create_request(dana, {**CAPTURE, "acting_for": "x"})
        assert caught.value.br_ref == "DEF-632"
        request = _new(dana)
        tab = reads.applicant_tab(request)
        assert tab["acting_for_absence"] == {"tracks": "DEF-638"}
        # The two absences that stood beside it are GONE, in the commit that
        # made them false (hard-won law 2's mirror).
        assert "date_of_birth_absence" not in tab
        assert "drivers_licence_absence" not in tab
        assert tab["date_of_birth"] is None
        # ⚠ **`identifier` IS A KEY NOW — DEF-632 (2026-08-27) and BR-CUS-092(a)
        # FINISHED (2026-09-15).** What this case still guards is that an
        # applicant who gave nothing discloses nothing and claims nothing.
        assert tab["identifier"] == {
            "ssn_last4": None,
            "ssn_present": False,
            "stored_encrypted": False,
            "drivers_licence_last4": None,
            "drivers_licence_present": False,
            "drivers_licence_stored_encrypted": False,
            "tax_id_last4": None,  # DEF-CWP-9045 — a portal business's number only
            "tax_id_present": False,
        }


def test_br_cus_091_a_disconnect_commits_and_is_not_a_move_out(brazos, dana):
    """**BR-CUS-091 (PO 2026-08-24, *"Yes customer can request it"*), closing
    DEF-638 12.a.**

    The list drew `SR-26-0048 · DISCONNECT · Ridge Coffee Co.` and the decision
    panel said one could not exist. The list was right; that reason is
    WITHDRAWN and this used to be the test asserting the refusal.

    ⚠ **What the withdrawn reason got RIGHT is asserted here instead**, because
    it is the half that still matters: a disconnect and a move-out are DIFFERENT
    outcomes — a move-out closes the account and settles the deposit
    (BR-CUS-030), a disconnect leaves it open and accruing (BR-MET-105) — and
    nothing may quietly convert one into the other."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.submit(dana, request.id)
        sr.decide_outcome(dana, request.id, outcome="disconnect", note="Collections asked")
        row = sr.request_row(request.id)
        assert row.outcome == "disconnect"
        # NOT silently rewritten to the neighbouring outcome.
        assert row.outcome != customers_models.ServiceRequest.OUTCOME_MOVE_OUT
        # The child link keeps them apart too — a disconnect job is not a
        # move-out job (W7 owns the job itself).
        assert sr.OUTCOME_CHILD_KINDS["disconnect"] == "disconnect"
        assert sr.OUTCOME_CHILD_KINDS["move_out"] == "move_out"
        assert "disconnect" in customers_models.ServiceRequest.JOB_OUTCOMES


def test_br_cus_091_staff_may_raise_a_disconnect_with_no_applicant_identity(brazos, dana):
    """**BR-CUS-091's consequence, verbatim:** *"a request may now ORIGINATE
    from STAFF (collections) rather than an applicant, so `channel` must
    distinguish them and applicant-identity fields are not required on a
    staff-raised disconnect."*

    Collections raising a disconnect on `500 Main` is not somebody applying for
    anything. Demanding an applicant name would make the clerk invent one, and
    an invented name is indistinguishable from a real one.

    ⚠ **THE ADDRESS CLAUSE MOVED TO SUBMIT ON 2026-09-20 and this case moved
    with it — PO ratification, `DEF-CUS-6006`.** It read *"the address is still
    required either way"* and asserted that at CREATE; *"there is no service
    request about nowhere"* is still true of a REQUEST and was never true of a
    DRAFT. The question this case asks is unchanged — is the address still
    required somewhere? — and the answer is now `_require_submit_minimum`. An
    APPLICANT-raised request with no name is still refused at create, which is
    what stops this widening leaking into the capture form."""
    with tenant_ctx(brazos):
        staff_raised = sr.create_request(
            dana,
            {
                "channel": customers_models.ServiceRequest.CHANNEL_STAFF_COLLECTIONS,
                "address_as_given": "500 Main",
                "what_they_said": "Collections: cut the supply",
            },
        )
        assert staff_raised.applicant_name is None
        assert staff_raised.request_no  # BR-CUS-093 numbers it like any other
        sr.submit(dana, staff_raised.id)
        sr.decide_outcome(dana, staff_raised.id, outcome="disconnect")
        assert sr.request_row(staff_raised.id).outcome == "disconnect"

        # …and the rule did NOT widen for an applicant-raised request.
        with pytest.raises(errors.ValidationError) as caught:
            sr.create_request(dana, {"channel": "walk_in", "address_as_given": "500 Main"})
        assert caught.value.message_key == "customers.serviceRequest.fieldRequired"
        # Nor did the address stop being required — it is asked for at SUBMIT
        # now, which is the only gate that was ever reachable from step 1.
        bare = sr.create_request(
            dana,
            {"channel": customers_models.ServiceRequest.CHANNEL_STAFF_COLLECTIONS},
        )
        assert bare.request_no
        with pytest.raises(errors.ValidationError) as refused:
            sr.submit(dana, bare.id)
        assert refused.value.params["field"] == "address_as_given"


def test_br_cus_094_all_seven_categories_are_selectable_and_government_is_legacy(brazos, dana):
    """**BR-CUS-094 (PO 2026-08-24, *"Expand the signed list to seven"*), closing
    DEF-635 and superseding B2 r5 #12 [D5]'s four-code list.**

    Seven chips were drawn and four were seeded; this test used to assert that
    the other three refused. All seven are real categories a plan can be priced
    for now.

    ⚠ **And `government` is the part the ruling could NOT settle for us**:
    Municipal and Institutional are both plausible readings of it and the stored
    value cannot tell them apart, *"so no row is re-labelled by guess"*. It goes
    LEGACY — unselectable on new records, and lawful in every other respect."""
    with tenant_ctx(brazos):
        request = _new(dana)
        seven = [code for code, _ in customers_models.AccountType.SEVEN_CATEGORIES]
        assert seven == [
            "residential",
            "commercial",
            "industrial",
            "agricultural",
            "institutional",
            "municipal",
            "builder_developer",
        ]
        for code in seven:
            sr.set_customer_category(dana, request.id, account_type_code=code)
            assert sr.request_row(request.id).account_type.code == code

        # ⚠ THE LEGACY CODE IS REFUSED **BY NAME**, and the fix is a human
        # re-pointing the record — not a migration guessing for them.
        with pytest.raises(errors.BizError) as caught:
            sr.set_customer_category(dana, request.id, account_type_code="government")
        assert caught.value.message_key == "customers.serviceRequest.categoryIsLegacy"
        assert caught.value.br_ref == "BR-CUS-094"

        # …and a code nobody has ever seeded is still a different refusal.
        with pytest.raises(errors.ValidationError) as caught:
            sr.set_customer_category(dana, request.id, account_type_code="unobtanium")
        assert caught.value.message_key == "customers.serviceRequest.categoryNotSeeded"


def test_br_cus_094_a_legacy_category_stays_valid_filterable_and_priceable(brazos, dana):
    """**The clause a "tidy-up" lane would break, pinned.**

    *"a legacy code is still a valid FK, still filterable, still priceable ...
    every existing record keeps it and keeps billing exactly as it does
    today."* So: the row is still there, still `active`, still attachable by the
    ORM to an existing record, and **nothing re-labelled it**."""
    with tenant_ctx(brazos):
        row = customers_models.AccountType.objects.get(code="government")
        assert row.legacy is True
        assert row.active is True  # legacy ≠ retired
        assert row.name == "Government"  # NOT renamed to Municipal or Institutional
        assert customers_models.AccountType.objects.filter(legacy=True).count() == 1
        # The seven are what a picker may offer; the eighth is filterable only.
        selectable = set(
            customers_models.AccountType.objects.filter(legacy=False).values_list("code", flat=True)
        )
        assert selectable == {code for code, _ in customers_models.AccountType.SEVEN_CATEGORIES}


def _part_paid_before_the_ruling(request_id, *, quoted, taken, receipt_no="RCP-26-4471"):
    """A request the counter PART-PAID BEFORE 2026-09-24, as data at rest.

    `OQ-CUS-12624` (`DEF-CUS-6455`) refuses a short payment at the desk from
    that day, so `collect_fee` can no longer make this state; rows written
    before it still hold it (*"requests already part-paid keep what was
    taken"*), and the approval gate and the Fees tab must go on reading them.
    The columns are written exactly as the pre-ruling `collect_fee` left them.
    """
    customers_models.ServiceRequest.objects.filter(id=request_id).update(
        fee_quoted=quoted,
        fee_collected=taken,
        fee_currency="USD",
        fee_method="cash",
        fee_receipt_no=receipt_no,
    )
    return sr.request_row(request_id)


def test_br_cus_090_the_counter_takes_the_whole_fee_or_refuses(brazos, dana):
    """**BR-CUS-090, the desk half — FLIPPED 2026-09-24 (`OQ-CUS-12624`,
    `DEF-CUS-6455`).** PO, verbatim: *"all or waived"*.

    This case was `test_br_cus_090_the_counter_accepts_what_is_handed_over`
    and asserted the 2026-08-24 clause *"we acept it and in finance we will
    reconcile"*: $25.00 taken against $130.00, $105.00 left open. Read by
    date, *"all or waived"* supersedes it for application fees. Now: quoted
    **$130.00**, **$25.00** offered → refused naming **$130.00** and nothing
    written; **$130.00** taken → **$0.00 outstanding**, the quote untouched and
    no line waived."""
    with tenant_ctx(brazos):
        request = _new(dana)
        for code, amount in (("CC-REQFEE", "25.00"), ("CC-EXPED", "60.00"), ("CC-METERT", "45.00")):
            quote_fee(dana, request.id, charge_code=code, unit_amount=Decimal(amount))

        quote = sr.fee_total_to_collect(request.id)
        assert quote["quoted"] == Decimal("130.0000")
        assert quote["collected"] == Decimal("0.0000")
        assert quote["outstanding"] == Decimal("130.0000")

        # The counter is offered $25.00 of it. REFUSED, and nothing is written.
        with pytest.raises(errors.BizError) as caught:
            sr.collect_fee(
                dana, request.id, amount=Decimal("25.00"), method="cash", receipt_no="RCP-26-4471"
            )
        assert caught.value.message_key == "customers.serviceRequest.feeTakeInFull"
        assert caught.value.params["amount"] == "130.0000"
        row = sr.request_row(request.id)
        assert row.fee_collected is None
        assert not row.fee_receipt_no

        after = sr.collect_fee(
            dana, request.id, amount=Decimal("130.00"), method="cash", receipt_no="RCP-26-4471"
        )
        assert after["collected"] == Decimal("130.0000")
        assert after["outstanding"] == Decimal("0.0000")
        assert after["receipt_no"] == "RCP-26-4471"
        assert after["method"] == "cash"

        row = sr.request_row(request.id)
        assert row.fee_quoted == Decimal("130.0000")
        assert row.fee_collected == Decimal("130.0000")
        assert len(row.fee_currency) == 3
        assert not customers_models.ServiceRequestFee.objects.filter(
            request=row, waived=True
        ).exists()

        tab = reads.fees_tab(row)
        assert tab["quoted"]["display"] == "130.00"  # rule 2 — display 2
        assert tab["collected"]["display"] == "130.00"
        assert tab["outstanding"]["display"] == "0.00"
        # The $130.00 posts DR 1010 · CR 2400 through payments (2026-09-15).
        assert tab["posts_to_ledger"] is True


def test_br_cus_090_the_outstanding_balance_blocks_approval_on_the_remainder(brazos, dana):
    """⛔ **FLIPPED 2026-09-23, NOT DELETED (`OQ-CUS-12617` CLOSED,
    `DEF-CUS-6420`).** PO, verbatim: *"either fee is paid or waived - no other
    condition"*.

    This case was `test_br_cus_090_the_outstanding_balance_is_reported_and_no
    _longer_blocks`, written on 2026-09-21 from *"make application fees optional
    - so that we can approve it"*, and it approved with $105.00 outstanding.
    Before that it asserted a refusal. It moves a third time with the rule —
    a deleted test is a rule nobody is holding.

    ⚠ **The desk half moved on 2026-09-24 (`OQ-CUS-12624`):** a short payment
    is refused at the counter now, so this case reads a request part-paid
    BEFORE that day. APPROVAL waits on the remainder, and the refusal names
    **$105.00**. A refused press is still never a waiver:
    the debt is still owed afterwards and no line was waived."""
    with tenant_ctx(brazos):
        request = _new(dana)
        quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("130.00"))
        # Part-paid BEFORE 2026-09-24 — the desk refuses a short payment since.
        _part_paid_before_the_ruling(
            request.id, quoted=Decimal("130.0000"), taken=Decimal("25.0000")
        )
        sr.submit(dana, request.id)
        sr.resolve_address(dana, request.id)
        sr.link_customer(dana, request.id)
        sr.decide_outcome(dana, request.id, outcome="new_connection")

        conditions = reads.conditions_for(sr.request_row(request.id))
        fee = next(c for c in conditions if c.key == "fee_settled")
        assert fee.state == rules.CONDITION_BLOCKED
        assert fee.blocking is True
        assert fee.message_key == "customers.serviceRequest.condition.feeOutstandingAmount"
        assert fee.params["amount"] == "105.0000"
        assert "fee_settled" in [c.key for c in rules.blocking_conditions(conditions)]

        # ── THE APPROVAL IS REFUSED, NAMING THE REMAINDER ─────────────────
        with pytest.raises(errors.BizError) as caught:
            sr.approve(dana, request.id)
        assert caught.value.message_key == "customers.serviceRequest.condition.feeOutstandingAmount"
        assert caught.value.params["amount"] == "105.0000"
        assert sr.request_row(request.id).state != rules.APPROVED

        # ── THE DEBT SURVIVED THE REFUSAL, AND NOTHING WAS WAIVED ─────────
        row = sr.request_row(request.id)
        after = reads.fees_tab(row)
        assert after["outstanding"]["display"] == "105.00"
        assert after["shortfall_is_open_balance"] is True
        assert not customers_models.ServiceRequestFee.objects.filter(
            request=row, waived=True
        ).exists()

        sr.collect_fee(
            dana, request.id, amount=Decimal("25.00"), method="cash", receipt_no="RCP-26-4471"
        )  # idempotent replay changes nothing
        assert sr.fee_total_to_collect(request.id)["outstanding"] == Decimal("105.0000")


def test_br_cus_090_one_receipt_number_and_the_collection_is_idempotent(brazos, dana):
    """**CLAUDE.md rule 6 at the counter, where a double-click actually
    happens.** BR-CUS-090 says the request stores ONE receipt number: a repeat
    with the same receipt is a no-op, and a second collection under a different
    receipt is refused rather than summed."""
    with tenant_ctx(brazos):
        request = _new(dana)
        quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00"))
        sr.collect_fee(
            dana, request.id, amount=Decimal("25.00"), method="cash", receipt_no="RCP-26-4471"
        )
        replay = sr.collect_fee(
            dana, request.id, amount=Decimal("25.00"), method="cash", receipt_no="RCP-26-4471"
        )
        assert replay["collected"] == Decimal("25.0000")  # not 50.00

        with pytest.raises(errors.BizError) as caught:
            sr.collect_fee(
                dana, request.id, amount=Decimal("25.00"), method="cash", receipt_no="RCP-26-9999"
            )
        assert caught.value.message_key == "customers.serviceRequest.feeAlreadyCollected"

        # A receipt is REQUIRED — cash with no receipt is cash nobody can
        # reconcile — and the method vocabulary excludes `waive`.
        other = _new(dana)
        with pytest.raises(errors.ValidationError):
            sr.collect_fee(dana, other.id, amount=Decimal("1.00"), method="cash", receipt_no=" ")
        with pytest.raises(errors.ValidationError):
            sr.collect_fee(dana, other.id, amount=Decimal("1.00"), method="waive", receipt_no="R1")


def test_br_cus_090_the_acknowledgement_may_not_say_nothing_is_charged(brazos, dana):
    """**BR-CUS-090 clause (3).** The acknowledgement printed *"Nothing is
    charged and no service changes until we have confirmed what is needed"*
    directly beneath a panel confirming a cash fee was collected. It is the
    FIRST thing an applicant receives and it is customer-facing, *"so a false
    sentence there is a money defect, not a copy nit."*

    The template is notifications' to own, so what this module guarantees is
    that the template cannot reach the false sentence by accident: the fact is
    served, not inferred."""
    with tenant_ctx(brazos):
        no_fee = _new(dana)
        statement = sr.fee_statement(sr.request_row(no_fee.id))
        assert statement["taken"] is False
        assert statement["nothing_is_charged_may_be_said"] is True

        paid = _new(dana)
        quote_fee(dana, paid.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00"))
        sr.collect_fee(
            dana, paid.id, amount=Decimal("25.00"), method="cash", receipt_no="RCP-26-4471"
        )
        result = sr.submit(dana, paid.id)
        statement = result["acknowledgement"]["fee_statement"]
        assert statement["taken"] is True
        assert statement["nothing_is_charged_may_be_said"] is False
        # The amount, the method and the receipt number — the three things the
        # ruling says the sentence must state.
        assert (statement["amount"], statement["method"], statement["receipt_no"]) == (
            "25.0000",
            "cash",
            "RCP-26-4471",
        )


def test_oq357_a_fee_line_is_removed_only_while_the_request_is_a_draft(brazos, dana):
    """OQ-357 closed 2026-09-23 as 'both' — PO approved the step-5 layout with
    both controls. This case read *"removal is not guessed"* and asserted the
    stub until then; it now asserts the ruling's boundary, and the full set of
    refusals lives in `test_def_cus_6408_request_fixes.py`.

    While the request is a DRAFT a mistaken line is taken back out; once it is
    submitted the only way to stop charging it is the per-line waiver, which
    keeps the line and its reason."""
    with tenant_ctx(brazos):
        request = _new(dana)
        fee = quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00"))
        sr.remove_fee_line(dana, fee.id, request_id=request.id)
        assert not customers_models.ServiceRequestFee.objects.filter(id=fee.id).exists()

        kept = quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00"))
        sr.submit(dana, request.id)
        with pytest.raises(errors.BizError) as refused:
            sr.remove_fee_line(dana, kept.id, request_id=request.id)
        assert refused.value.message_key == "customers.serviceRequest.feeRemoveNotDraft"
        assert customers_models.ServiceRequestFee.objects.filter(id=kept.id).exists()


def test_br_cus_095_the_checklist_ships_entirely_unticked(brazos, dana):
    """**BR-CUS-095's sharpest clause, and the one a later lane will be tempted
    to soften:** *"We ship with nothing ticked, and a utility that configures
    nothing blocks nothing."*

    No pre-tick of `proof_of_identity`, however reasonable it looks — a product
    that blocks approvals out of the box for a rule its customer never chose is
    worse than one that blocks none.

    ⚠ **This asserts the TABLE IS EMPTY, not merely that the read returns
    nothing**, because a seed added in a migration would satisfy the second and
    break the ruling."""
    with tenant_ctx(brazos):
        assert customers_models.ServiceRequestDocumentRequirement.objects.count() == 0
        assert sr.required_document_types("move_in") == ()
        request = _new(dana)
        tab = reads.documents_tab(request)
        assert tab["checklist_required"] == []
        assert tab["checklist_unmet"] == []
        assert tab["blocks_approval"] is False
        # The GRID is still served, so a screen can tick a box for the first
        # time — every cell present, every cell `configured: False`.
        grid = sr.document_requirements()
        assert len(grid) == 5 * 8  # five job outcomes × the eight designed types
        assert all(cell["required"] is False and cell["configured"] is False for cell in grid)


def test_br_cus_095_a_ticked_document_is_reported_and_never_blocks_creation(brazos, dana):
    """**The ruling's own worked case, end to end.**

    *"a utility ticks proof of identity and signed service agreement for MOVE-IN
    only → a move-in request submits and sits happily in `Under review` with
    neither attached, and `approve` refuses by name until both are attached AND
    verified; the same tenant's TRANSFER requests tick nothing and approve with
    no documents at all."*

    Two gates, and this is both of them at once (B19 §5)."""
    with tenant_ctx(brazos):
        sr.set_document_requirement(dana, request_type="move_in", doc_type=DOC_ID, required=True)
        sr.set_document_requirement(
            dana, request_type="move_in", doc_type=DOC_AGREEMENT, required=True
        )
        assert sr.required_document_types("move_in") == (DOC_ID, DOC_AGREEMENT)
        assert sr.required_document_types("transfer") == ()

        request = _new(dana)
        # GATE ONE — creation and submission are untouched.
        sr.submit(dana, request.id)
        sr.link_customer(dana, request.id)
        sr.decide_outcome(dana, request.id, outcome="move_in")
        # ⚠ **PICKING THE OUTCOME MOVES NO STATE, AND SINCE 2026-09-19 THERE IS
        # NO `pick_up` BEFORE IT EITHER** — so a submitted request is still
        # submitted after the clerk has said what it becomes.
        assert sr.request_row(request.id).state == rules.SUBMITTED

        # GATE TWO — REPORTS BY NAME, naming what is missing, and does not
        # refuse (`BR-CUS-1078`, PO 2026-09-16). The message key and its count
        # are asserted exactly as they were when this refused: they are what the
        # clerk reads, and they now matter MORE than when they gated something,
        # because they are the only thing left saying which documents are short.
        conditions = reads.conditions_for(sr.request_row(request.id))
        documents = next(c for c in conditions if c.key == "documents_verified")
        assert documents.blocking is False
        assert documents.message_key == (
            "customers.serviceRequest.condition.requiredDocumentMissing"
        )
        assert documents.params["count"] == 2

        # ⚠ ATTACHING IS NOT ENOUGH — a file is not a verification. That half of
        # the ruling is untouched: it decides what is REPORTED, not what is
        # refused.
        first = sr.attach_document(
            dana, request.id, doc_type=DOC_ID, name="id.pdf", storage_ref="s3://id"
        )
        second = sr.attach_document(
            dana, request.id, doc_type=DOC_AGREEMENT, name="sa.pdf", storage_ref="s3://sa"
        )
        assert sr.unmet_required_documents(sr.request_row(request.id)) == (DOC_ID, DOC_AGREEMENT)
        sr.verify_document(dana, first.id)
        assert sr.unmet_required_documents(sr.request_row(request.id)) == (DOC_AGREEMENT,)

        # ⚠ AND THE CHECKLIST IS KEYED ON THE OUTCOME, WHICH IS WHY IT CAN BE
        # ASKED ABOUT ONE NOBODY HAS PICKED (`DEF-CUS-5427`). This request is a
        # move-in; considered as a transfer it wants nothing at all.
        assert sr.unmet_required_documents(sr.request_row(request.id), outcome="transfer") == ()

        sr.verify_document(dana, second.id)
        assert sr.unmet_required_documents(sr.request_row(request.id)) == ()
        # ⚠ **A MOVE-IN NEEDS ITS PLACE BEFORE IT CAN BE APPROVED (2026-09-23,
        # `DEF-CUS-6350`).** Approve now checks the property is in Premises, a
        # unit is chosen and the unit is free. This case is about documents, so
        # it points the request at a vacant unit rather than walking the
        # resolver; the place checks have their own file.
        premises = make_premises(dana, address_line="12 Vacant Row")
        unit = make_unit(dana, premises["id"], label="Unit 1")
        customers_models.ServiceRequest.objects.filter(pk=request.id).update(
            resolved_premises_id=premises["id"], resolved_unit_id=unit["id"]
        )
        sr.approve(dana, request.id)
        assert sr.request_row(request.id).state == rules.APPROVED


def test_br_cus_095_a_tenant_that_ticks_nothing_blocks_nothing(brazos, dana):
    """The other half of the same worked case: the SAME tenant's `transfer`
    requests tick nothing and approve with no documents at all. A checklist for
    one job type may never leak onto another."""
    with tenant_ctx(brazos):
        sr.set_document_requirement(dana, request_type="move_in", doc_type=DOC_ID, required=True)
        request = _new(dana)
        sr.submit(dana, request.id)
        sr.link_customer(dana, request.id)
        sr.decide_outcome(dana, request.id, outcome="transfer")
        sr.approve(dana, request.id)
        assert sr.request_row(request.id).state == rules.APPROVED


def test_br_cus_095_only_the_eight_designed_types_may_be_ticked(brazos, dana):
    """A tick nothing can satisfy is a request nobody can approve, and the row
    would look perfectly valid. So the checklist takes only the EIGHT, and the
    drawn ninth (`other` — REQ-03.4's *Anything else*, badged Optional) is
    attachable and never tickable."""
    with tenant_ctx(brazos):
        eight = customers_models.ServiceRequestDocument.DESIGNED_DOC_TYPES
        assert len(eight) == 8
        with pytest.raises(errors.ValidationError) as caught:
            sr.set_document_requirement(
                dana,
                request_type="move_in",
                doc_type=customers_models.ServiceRequestDocument.DOC_OTHER,
                required=True,
            )
        assert caught.value.message_key == "customers.serviceRequest.documentTypeNotTickable"
        with pytest.raises(errors.ValidationError):
            sr.set_document_requirement(
                dana, request_type="not_a_job", doc_type=DOC_ID, required=True
            )
        # …and `other` IS attachable, because B19 §5 draws it.
        request = _new(dana)
        sr.attach_document(
            dana,
            request.id,
            doc_type=customers_models.ServiceRequestDocument.DOC_OTHER,
            name="letter.pdf",
            storage_ref="s3://x",
        )


# ═══════════════════════════════════════════════════════════════════════════
# 9 · MONEY, AUDIT, AND THE APPEND-ONLY TIMELINE
# ═══════════════════════════════════════════════════════════════════════════
def test_a_fee_is_money_at_four_places_displayed_at_two(brazos, dana):
    """CLAUDE.md rule 2, PO re-sign 2026-08-22."""
    with tenant_ctx(brazos):
        request = _new(dana)
        fee = quote_fee(
            dana,
            request.id,
            charge_code="CC-METERT",
            unit_amount=Decimal("45.005"),
            quantity=Decimal("1"),
        )
        assert fee.amount == Decimal("45.0050")
        served = reads.fees_tab(sr.request_row(request.id))["lines"][0]["amount"]
        assert served["amount"] == "45.0050"
        assert served["display"] == "45.01"
        assert len(served["currency"]) == 3


def test_every_money_action_writes_an_audit_row(brazos, dana, audit_rows):  # noqa: F811
    """CLAUDE.md rule 7."""
    with tenant_ctx(brazos):
        request = _new(dana)
        audit_rows.clear()
        fee = quote_fee(
            dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00")
        )
        sr.waive_fee_line(dana, fee.id, reason="Goodwill")
        actions = [row["action"] for row in audit_rows]
        assert "service_request.fee_quoted" in actions
        assert "service_request.fee_waived" in actions
        assert all(row["actor_user_id"] == dana.id for row in audit_rows)


def test_the_timeline_is_append_only_and_internal(brazos, dana):
    """The History tab is badged **`Internal · never shown to the customer`**,
    and no path in this module edits a row."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.add_note(dana, request.id, note="Rang the applicant; no answer")
        rows = reads.history_tab(sr.request_row(request.id))
        assert all(r["internal"] for r in rows)
        assert rows[0]["note"] == "Rang the applicant; no answer"
        assert not any(name.startswith("edit_note") for name in dir(sr))


def test_the_history_who_column_is_a_name_and_never_a_database_id(brazos, dana):
    """**B14 rule 31 on the server, where the fix actually lives.**

    The blueprint letters the history table `WHEN · WHAT · WHO` and prints
    `S. Ortiz` in the third column (p086 of the 281-page Accounts blueprint;
    it was p082 before the 2026-09-19 upload). All `actor` has ever carried is
    the user's UUID, and the PO's rule is in their own words — *"no Databse ID
    on screen - that is a rule"* — so `history_tab` resolves the NAME and the
    screen prints that.

    ⚠ **THIS IS A BACKEND CASE BECAUSE THE FIX IS A BACKEND ONE.** The screen's
    own tests hand it a fixture carrying `actor_name`, so they would go on
    passing if the server started serving a UUID again, or nothing at all —
    they prove the column renders what it is given and never that the server
    gives the right thing. This asserts the SERVER's answer.

    ⚠ **AND IT ASSERTS THE ABSENCE TOO.** A row written by a background job or
    planted by the seed has no user, and the server returns `None` rather than
    choosing a glyph for every future caller — the screen draws the drawing's
    em dash. A test that only checked the happy row would pass over a server
    that had started returning the string "None".
    """
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.add_note(dana, request.id, note="Rang the applicant; no answer")
        rows = reads.history_tab(sr.request_row(request.id))

        acted = [r for r in rows if r["actor"] is not None]
        assert acted, "the fixture must write at least one row with an actor"
        for row in acted:
            assert row["actor_name"] == dana.user.full_name
            # the id is still served beside the name, and is NOT the name
            assert row["actor_name"] != row["actor"]
            with pytest.raises(ValueError):
                uuid.UUID(str(row["actor_name"]))

        for row in rows:
            if row["actor"] is None:
                assert row["actor_name"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 10 · THE READ MODEL REQ-01/02/03 ARE BUILT AGAINST
# ═══════════════════════════════════════════════════════════════════════════
def test_the_list_is_newest_first_and_segments_by_state(brazos, dana):
    """The list opens on what was just created — `BR-CUS-1046`, PO 2026-09-10.

    ⚠ **THIS CASE ASSERTED THE OPPOSITE FOR THREE DAYS, AND SO DID ITS OWN NAME
    (`DEF-CUS-5403`, fixed 2026-09-15).** It was written to the design sentence
    *"Sorted by age, oldest first — the oldest thing waiting is the thing to look
    at"*, which `BR-CUS-1046` SUPERSEDED in the PO's own words: *"Whenever any
    account is created or any entry is created in the system, it automatically
    sorts it by the alphabetical order. It should always sort it by the creation
    order. The new newly created entries should always show on the top."*

    `service_request_reads` has read `DEFAULT_SORT = "created"` with
    `DEFAULT_DIR = "desc"` since that ruling landed, so **the product was right
    and the test was wrong** — this is a stale assertion being corrected, never a
    guard being weakened to make a suite green. Two separate lanes found it red
    on 2026-09-15 and both correctly declined to touch it, because a test whose
    NAME states the old rule cannot be fixed by flipping one list.
    """
    with tenant_ctx(brazos):
        first = _new(dana, applicant_name="Osei, Grace")
        second = _new(dana, applicant_name="Alvarez, Rosa")
        sr.submit(dana, second.id)
        sr.refuse_request(dana, second.id, reason="No proof of address")
        open_ids = [str(r.id) for r in reads.list_queryset(segment="open")]
        assert open_ids == [str(first.id)]
        closed_ids = [str(r.id) for r in reads.list_queryset(segment="closed")]
        assert closed_ids == [str(second.id)]
        # Newest first: `second` was created after `first`, so it leads.
        assert [str(r.id) for r in reads.list_queryset(segment="all")] == [
            str(second.id),
            str(first.id),
        ]
        assert [str(r.id) for r in reads.list_queryset(segment="all", q="Osei")] == [str(first.id)]


def test_the_kpi_strip_counts_what_the_screen_labels(brazos, dana):
    """`APPROVED, NOT STARTED` is the tile that earns the tab — *"decided, and
    nobody has begun"*.

    ⚠ **WHAT THE TILE ACTUALLY COUNTS IS `state=approved AND outcome_ref IS
    NULL`** (`service_request_reads.kpi_strip`) — *approved, and no job was
    raised* — and this fixture used to reach that state with a NEW CONNECTION.

    ⛔ **IT COULD ONLY DO SO BECAUSE THE RAISER WAS REFUSING, WHICH WAS
    `DEF-CUS-6109`.** A new connection whose address HAD resolved already raised
    a build and already set `outcome_ref`, so it was already outside this tile;
    the unresolved shape counted only because approving it created nothing at
    all. Since 2026-09-21 both shapes raise a draft build, so **no approved new
    connection is ever *not started* by this column's definition.**

    So the fixture uses a **move-out**, which is the outcome that genuinely
    raises no row — `JOB_SHAPES["move_out"]["raises"] is None`, and
    `request_jobs.WIZARD_IS_THE_RECORD` says why in its own words: *"a move-in
    is short enough that the wizard is the record"*. **The tile's meaning is
    untouched; the fixture stops depending on a refusal.**

    ⚠ **AND WHETHER A DRAFT BUILD SHOULD COUNT AS *NOT STARTED* IS A REAL
    QUESTION THIS LANE DID NOT ANSWER.** A draft build with no units is
    plausibly *decided, and nobody has begun* — the approve modal's own drawn
    table says *"Not now — No account opens, no meter is fitted, nothing is
    energised"*. Answering it means reading the BUILD's state from a KPI in
    another module, which is a rule nobody has stated. Filed rather than
    guessed: `DEF-CUS-6121`.
    """
    with tenant_ctx(brazos):
        approved = _new(dana)
        sr.submit(dana, approved.id)
        sr.resolve_address(dana, approved.id)
        sr.link_customer(dana, approved.id)
        sr.decide_outcome(dana, approved.id, outcome="move_out")
        sr.approve(dana, approved.id)
        assert sr.request_row(approved.id).outcome_ref is None

        waiting = _new(dana)
        sr.submit(dana, waiting.id)
        sr.park(dana, waiting.id, waiting_on="documents")

        strip = reads.kpi_strip()
        assert strip["approved_not_started"] == 1
        assert strip["waiting_on_customer"] == 1
        assert strip["oldest_waiting"]["waiting_on"] == "documents"


def test_the_detail_serves_all_six_tabs(brazos, dana):
    with tenant_ctx(brazos):
        request = _new(dana)
        payload = reads.detail(request.id)
        assert set(payload) == {
            "header",
            "actions",
            "applicant",
            "location_and_services",
            "documents",
            "fees",
            "decision",
            "history",
            # ⚠ **A NINTH KEY SINCE 2026-09-29, AND THE STRICT SET IS WHY IT
            # IS HERE RATHER THAN SLIPPING IN.** `told_on_submit` is REQ-03
            # step 4's `What the customer is told` card — not a tab, which is
            # why the name of this case still reads *six tabs*. The set is
            # asserted exactly, on purpose: a payload that grows a key nobody
            # decided to add is how a contract drifts.
            "told_on_submit",
            # ⊕ `CR-161-BRC10` W6 (2026-10-02) — decided, not drifted: the
            # request's own copy of the utility's fields (gap 2) and what
            # approving does with each answer (gap 3 / R5).
            "custom_data",
            "custom_field_copy",
            # ⊕ `CR-183-BRC10` — the temporary stop this request asks for, or
            # `None` on every other request (the Approve window reads it).
            "temporary_stop",
        }
        assert payload["header"]["classification"] == "not_yet_classified"
        # ⚠ **THE DISCONNECT ABSENCE IS GONE — BR-CUS-091.** When a row closes,
        # its stated absence must go, or the screen keeps apologising for
        # something that has been fixed. What replaces it is the distinction the
        # withdrawn reason got RIGHT.
        assert "disconnect_absence" not in payload["decision"]
        assert payload["decision"]["disconnect_is_not_a_move_out"]["rule"] == "BR-CUS-091"
        # …and OQ-356 is still open, so its absence stays.
        assert payload["decision"]["undrawn_verdict_absence"] == {"tracks": "OQ-356"}


def test_a_requested_services_availability_starts_unknown_not_false(brazos, dana):
    """REQ-03.3's CHECK callout: *"we cannot confirm which of the requested
    services are available. That is settled at review."* NULL is *not yet
    asked* and is never spelled the same way as *no*."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_services(dana, request.id, ["electric", "water"])
        served = reads.location_tab(request, sr.evidence_for(request))["services"]
        assert [s["code"] for s in served] == ["electric", "water"]
        assert all(s["available"] is None for s in served)
        with pytest.raises(errors.ValidationError):
            sr.set_services(dana, request.id, ["unobtanium"])


# ═══════════════════════════════════════════════════════════════════════════
# 11 · TENANT ISOLATION — under a NON-SUPERUSER probe role
# ═══════════════════════════════════════════════════════════════════════════
def test_another_tenants_request_is_a_404_not_a_403(brazos, lonestar, dana, erin):  # noqa: F811
    """HR-1 — the app-layer half. The DATABASE half is below; this one only
    proves the boundary does not CONFIRM the row exists."""
    with tenant_ctx(brazos):
        request = _new(dana)
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            sr.request_row(request.id)
        assert reads.list_queryset(segment="all").count() == 0


@pytest.mark.isolation
@requires_postgres
def test_a_service_request_is_rls_scoped(rls, brazos, lonestar, dana, erin):  # noqa: F811
    """⚠ **THE ONLY ASSERTION IN THIS FILE THAT PROVES RLS.**

    A plain ORM query under `tenant_ctx` runs as the app's role, which is a
    SUPERUSER in dev and CI — and superusers bypass row-level security
    unconditionally, FORCE or not. Such an assertion returns rows because the
    policy was never consulted and goes green having proven nothing
    (`tests/isolation_helpers.py`; DEF-101 is what it cost last time). So this
    runs inside `SET ROLE sbh_rls_probe` (NOLOGIN NOSUPERUSER NOBYPASSRLS) and
    the fixture FAILS rather than skips if that role could bypass.

    `service_requests` is the most PII-dense table this module has: an
    applicant's name, email, phone, home address in their own words, their
    language, a co-applicant's contact details — and the whole pipeline of who
    is about to take service, and where.
    """
    with tenant_ctx(brazos):
        owned = _new(dana)
        sr.attach_document(dana, owned.id, doc_type=DOC_ID, storage_ref="s3://id")
        quote_fee(dana, owned.id, charge_code="CC-REQFEE", unit_amount=Decimal("25.00"))
        sr.set_services(dana, owned.id, ["electric"])
        sr.submit(dana, owned.id)
        # BR-CUS-095 — one tick, so the checklist table has a row to hide.
        sr.set_document_requirement(dana, request_type="move_in", doc_type=DOC_ID, required=True)
    with tenant_ctx(lonestar):
        _new(erin, applicant_name="Somebody Else")

    assert_rls_scoped(
        rls, "service_requests", owner=brazos, intruder=lonestar, owner_ids={str(owned.id)}
    )
    for table in SR_TABLES[1:]:
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)
    assert_no_foreign_rows_anywhere(rls, brazos, SR_TABLES)
    assert_no_foreign_rows_anywhere(rls, lonestar, SR_TABLES)


def test_def_657_changing_a_category_twice_serialises_its_audit_before(brazos, dana, audit_rows):
    """**DEF-657 — the second call answered 500 on a running stack.**

    `set_customer_category` builds its audit `before` blob from
    `request.account_type_id` / `.account_subtype_id`. Those are `None` on the
    first call, so it serialised fine; once set they are `UUID` objects, and
    the audit row JSON-serialises `details` — `TypeError: Object of type UUID
    is not JSON serializable`. Measured against a running stack: call one
    **200**, call two **500**, call three with a DIFFERENT code **500**. A
    clerk who changed their mind about the customer category met a 500.

    ⚠ **THE FIX THAT LANDED IS NOT THE ONE THE DEFECT REPORT PROPOSED, AND THE
    DIFFERENCE IS THE POINT.** The report asked for `str(...)` on the two
    `before` values — one line, at this call site. What is in the tree instead
    is `jsonable(before)` in `core.audit.write_row`, stamped `DEF-657 —
    coerced here, at the ONE writer, not at each call site`. That is the
    stronger fix: **every** audit caller in the product is covered, including
    the ones nobody has written yet, and a future `before` blob carrying a
    `Decimal`, a `date` or a `UUID` cannot reintroduce this.

    So this case guards the BEHAVIOUR, not the implementation — it asserts the
    row survives a JSON round-trip, and would pass under either fix and fail
    under neither. Asserting `str()` at this call site would have pinned the
    weaker design in place.

    Calls **two and three** are asserted because call one was never broken.
    """
    with tenant_ctx(brazos):
        request = _new(dana)
        residential = customers_models.AccountType.objects.get(code="residential")

        sr.set_customer_category(dana, request.id, account_type_code="residential")
        # Call two — the one that 500'd. Same code, so only `before` changes.
        sr.set_customer_category(dana, request.id, account_type_code="residential")
        # Call three — a different code: the clerk actually changing their mind.
        sr.set_customer_category(dana, request.id, account_type_code="commercial")

        assert sr.request_row(request.id).account_type.code == "commercial"

    rows = [row for row in audit_rows if row["action"] == "service_request.category_set"]
    assert len(rows) == 3

    # The whole row must survive a JSON round-trip — this is what raised.
    for row in rows:
        json.dumps(row["before"])
        json.dumps(row["after"])

    # Call one had nothing before it; calls two and three name the previous
    # category as a STRING, which is the value that was a raw UUID.
    assert rows[0]["before"]["account_type"] is None
    assert rows[1]["before"]["account_type"] == str(residential.id)
    assert rows[2]["before"]["account_type"] == str(residential.id)
    assert all(isinstance(row["before"]["account_type"], (str, type(None))) for row in rows)


# ═══════════════════════════════════════════════════════════════════════════
# 12 · THE CATEGORY IS READ BACK — B18 task 4.12's reported read-model gap
# ═══════════════════════════════════════════════════════════════════════════
# The row B18 §11 carries reads: *"`service_request_reads.detail` serves NO
# category at all — neither `account_type` nor `account_subtype` appears in any
# tab — so REQ-02 cannot show what a request was categorised as, and a
# half-finished draft reopened from the list cannot restore the chip the clerk
# picked. The column is written (`set_customer_category`) and never read back."*
#
# It is the mirror of hard-won law 2. Law 2 is dead UI over a missing endpoint;
# this is a live WRITE with no READ, and it is quieter — every test passes,
# `set_customer_category` returns 200, the column fills, and the only symptom is
# a clerk seeing seven blank chips over a row that already holds one of them.
# Four cases, and the fourth is the one a "tidy-up" lane would delete.


def test_the_detail_serves_the_category_it_was_given(brazos, dana):
    """The gap, closed: what was written comes back on the detail.

    Asserted through the SAME payload REQ-02 renders (`reads.detail`), not
    through the model — a test that read `request.account_type` would have
    passed on every day this gap existed."""
    with tenant_ctx(brazos):
        request = _new(dana)
        sr.set_customer_category(dana, request.id, account_type_code="builder_developer")

        served = reads.detail(request.id)["applicant"]["customer_category"]
        assert served["not_yet_categorised"] is False
        assert served["account_type"]["code"] == "builder_developer"
        assert served["account_type"]["name"] == "Builder or developer"
        assert served["account_type"]["selectable"] is True
        assert served["account_type"]["legacy"] is False
        # It rides beside the OTHER axis, which is B19 §14.3's whole point: one
        # legal person, one place-or-use, both true at once.
        assert reads.detail(request.id)["applicant"]["person_or_company"] == "person"


def test_an_uncategorised_request_says_not_yet_and_invents_no_default(brazos, dana):
    """A draft that has not reached step 2 carries NO category, and the payload
    says so rather than picking the commonest one.

    ⚠ **`residential` is the wrong default and there is no right one.** Seeding
    a default here would make every abandoned draft look deliberately
    categorised, and BR-CUS-094 makes the category load-bearing on PRICE (*"sets
    which plans are eligible"*), so a guessed chip is a guessed tariff class.

    ⚠ **And it is NOT an `_absence` block.** Nothing is waiting on a ruling or a
    defect — the clerk simply has not got there — so there is no `tracks` key to
    cite and G38's discipline is satisfied by not claiming one."""
    with tenant_ctx(brazos):
        request = _new(dana)
        served = reads.detail(request.id)["applicant"]["customer_category"]
        assert served["not_yet_categorised"] is True
        assert served["account_type"] is None
        assert served["account_subtype"] is None
        assert "tracks" not in served
        assert not any(key.endswith("_absence") for key in served)

        # ⚠ And it is a DIFFERENT field from the header's classification chip,
        # which is the OUTCOME (`NOT YET CLASSIFIED`). Two words, two columns.
        assert reads.detail(request.id)["header"]["classification"] == "not_yet_classified"


def test_a_legacy_category_reads_back_as_picked_and_not_pickable(brazos, dana):
    """**BR-CUS-094's `government`, on a row that already carries it.**

    The ruling keeps a legacy code *"still a valid FK, still filterable, still
    priceable"* and unselectable on new records, and reserves the re-labelling
    for a human: *"Municipal and Institutional are both plausible readings of it
    … so no row is re-labelled by guess."*

    **Which is exactly what a read-back has to be able to say.** A payload
    carrying only the code would leave the screen to look it up in the picker,
    not find it, and render the chip as unset — re-labelling the record to
    *nothing* by omission. So `legacy` and `selectable` travel with it.

    The row is written through the ORM deliberately: `set_customer_category`
    REFUSES `government` (that refusal has its own case above), and the row this
    case describes is one created before the ruling existed."""
    with tenant_ctx(brazos):
        request = _new(dana)
        legacy = customers_models.AccountType.objects.get(code="government")
        customers_models.ServiceRequest.objects.filter(pk=request.id).update(
            account_type_id=legacy.id
        )

        served = reads.detail(request.id)["applicant"]["customer_category"]
        assert served["not_yet_categorised"] is False
        assert served["account_type"]["code"] == "government"
        assert served["account_type"]["name"] == "Government"  # never re-labelled
        assert served["account_type"]["legacy"] is True
        assert served["account_type"]["selectable"] is False


def test_the_sub_category_reads_back_with_its_parent(brazos, dana):
    """**BR-CUS-067's two-level tree, served as a tree.**

    The sub-type is what the help text says *"sets which plans are eligible"*,
    so serving its code without its parent would let a screen draw
    `Residential › Healthcare` — a pair the tree does not contain — without
    anything being able to notice."""
    with tenant_ctx(brazos):
        request = _new(dana)
        residential = customers_models.AccountType.objects.get(code="residential")
        # BR-CUS-067's tree is SEEDED per tenant (SEED_ACCOUNT_SUBTYPES), so
        # this reads the tenant's own row rather than minting a duplicate —
        # `uq_account_subtypes_tenant_code_ci` refuses one, which is how this
        # case found out the seed was already there.
        subtype = customers_models.AccountSubtype.objects.get(tenant=brazos, code="single_family")
        assert subtype.account_type_id == residential.id
        sr.set_customer_category(
            dana, request.id, account_type_code="residential", account_subtype_id=subtype.id
        )

        served = reads.detail(request.id)["applicant"]["customer_category"]
        assert served["account_subtype"]["code"] == "single_family"
        assert served["account_subtype"]["name"] == "Single-family"
        assert served["account_subtype"]["parent_account_type_id"] == str(residential.id)
        assert served["account_type"]["id"] == served["account_subtype"]["parent_account_type_id"]


# ═══════════════════════════════════════════════════════════════════════════
# 13 · TC-REQ-8 — THE APPROVAL THRESHOLD IS **NOT BUILT**, AND THIS IS WHY
# ═══════════════════════════════════════════════════════════════════════════
def test_tc_req_8_there_is_no_approval_threshold_and_br_cus_074_is_unruled(brazos, marcus):
    """**TC-REQ-8 CANNOT BE WRITTEN AS DESIGNED, AND THE ABSENCE IS PINNED HERE
    RATHER THAN LEFT AS A MISSING TEST.**

    B18 §5.3.9 designs it as *"a clerk under the approval threshold → `approve`
    → refused; a supervisor may"*, and B18 §6.4 proposes **BR-CUS-074**
    (*"Approval is threshold-checked; refusal is supervisor-only and requires a
    reason code"*).

    ⚠ **B18 §6.4 IS A PROPOSAL IN A DOCUMENT STAMPED `DRAFT FOR PO REVIEW`, AND
    BR-CUS-074 HAS NEVER BEEN RATIFIED.** Nothing anywhere in this repository
    states **what the threshold is measured in** (a fee balance? a connection
    quote? a unit count?), **what its figure is**, or **which role counts as the
    supervisor** — the identity model has `system_admin` and `billing_clerk` and
    no supervisor tier. Choosing any of the three would resolve an open decision
    by picking a value, which the prime directive forbids.

    **So what is BUILT is the gate that IS ruled** — `approve` refuses on the
    four approval CONDITIONS (documents, fees, arrears, eligibility) and on a
    missing outcome, for every role that may reach the call at all. This case
    asserts that, and it goes RED the day a threshold appears — which is the
    point: whoever adds one has to come back here and name the ruling that
    authorised it.

    Asserted through **Marcus (billing_clerk)**, who is the *"clerk"* in the
    designed sentence, so the case is about the threshold and not about
    BR-SHL-025's role gate."""
    with tenant_ctx(brazos):
        request = _new(marcus)
        sr.submit(marcus, request.id)
        sr.resolve_address(marcus, request.id)
        sr.link_customer(marcus, request.id)  # searched, nobody found
        sr.decide_outcome(marcus, request.id, outcome="new_connection")

        # The ruled gate: a plain billing clerk approves once conditions clear.
        sr.approve(marcus, request.id, note="conditions clear")
        assert sr.request_row(request.id).state == rules.APPROVED
        assert sr.request_row(request.id).decided_by_id == marcus.id

        # …and NOTHING in the payload claims a threshold was consulted. A
        # fabricated `threshold: null` would be worse than the absence — it
        # would read as a built feature that happened to be unset.
        actions = reads.detail(request.id)["actions"]
        assert "threshold" not in json.dumps(actions)


# ═══════════════════════════════════════════════════════════════════════════
# 14 · THE SEED — B18 task 4.14's eight `[shot]` requests, ASSERTED
# ═══════════════════════════════════════════════════════════════════════════
# The eight are declared in `core/sample_fixture.CR030_SERVICE_REQUESTS` and
# planted by `apps/customers/sample_data._seed_cr030_service_requests`, wired
# into `seed_sample_records`. **Nothing asserted any of it** —
# `tests/test_us_ten_019_sample_records.py` never mentions a service request —
# so the fixture J26 exists to run against was itself unguarded. These cases are
# that guard, and they live here rather than in the sample-data file because the
# subject is the CR-031 object and its rules.
#
# ⚠ **THEY DRIVE THE SEEDER DIRECTLY ON A BARE TENANT**, without the CR-030
# estate. That is deliberate: it isolates what the fixture guarantees ANYWHERE
# from what needs eight premises to be true. Anything premises-dependent
# (`resolution_kind`, the evidence badges) is NOT asserted here and is named
# below instead of being quietly relied on.


def _seed_the_eight(actor):
    from apps.customers import sample_data
    from apps.rating import sample_data as rating_sample

    # ⚠ `DEF-CUS-6416` — the server prices a fee line from the catalogue, so the
    # three codes the sample requests quote must exist first, in the order the
    # real loader runs them (rating before customers). Their rows are not
    # counted: this helper answers what the SERVICE-REQUEST seed wrote.
    rating_sample.seed_sample_request_fee_charge_code(actor)
    rating_sample.seed_sample_request_quote_charge_codes(actor)
    return sample_data._seed_cr030_service_requests(actor)


def test_the_seed_plants_the_eight_shot_requests_in_their_drawn_states(brazos, dana):
    """**Task 4.14, asserted end to end through the product's own doors.**

    Spec rule 4 — *"seed through the services a clerk's click uses, never by
    writing rows directly"* — is what makes this fixture worth having, and it is
    also what makes this case meaningful: every state below was REACHED, through
    `create_request` → `submit` → `transition` → `decide_outcome` → `approve` →
    `route` → `park`, so a tightening of any transition guard breaks the seed
    here rather than in some other lane's file three days later."""
    with tenant_ctx(brazos):
        _seed_the_eight(dana)
        rows = {
            r.applicant_name: r
            for r in customers_models.ServiceRequest.objects.filter(tenant_id=brazos.id)
        }
        assert len(rows) == 8
        assert all(r.is_sample for r in rows.values())

        # The six drawn states, all reached — and `waiting_on` is ORTHOGONAL to
        # state, which is the pair the model's own docstring cites.
        assert (rows["Osei, Grace"].state, rows["Osei, Grace"].waiting_on) == (
            "more_info",
            "documents",
        )
        # ⚠ **DRAWN `in_fulfilment`, PLANTED `approved` — AND THAT IS THE RULING,
        # NOT A BROKEN FIXTURE.** `route` is one of the nine moves the PO retired
        # on 2026-09-19, so nothing can put a request into `in_fulfilment` any
        # more: *"once requets is approved then in move in or new connect we take
        # all those decision to in fulfill etc"*. `CR030_SERVICE_REQUESTS` keeps
        # its DRAWN declaration as the record of the blueprint and the row stops
        # where the ruling stops it. Asserted here so that the day the Work
        # callback lands, this line is what says the demo tenant may move again.
        assert rows["Ridge Property LLC"].state == "approved"
        # ⚠ **DRAWN `under_review` WITH NO `waiting_on`, AND THAT COMBINATION IS
        # NOW UNREACHABLE.** Park is the only way into `under_review` since the
        # 2026-09-19 ruling and park cannot be done without saying what is
        # awaited — so a row drawn *under review, waiting on nothing* stays
        # `submitted`. That is the rule working, not a gap in the seed.
        assert rows["Park, Jenna"].state == "submitted"
        assert (rows["Okonkwo, David"].state, rows["Okonkwo, David"].waiting_on) == (
            "under_review",
            "payment",
        )
        assert (rows["Ridge Coffee Co."].state, rows["Ridge Coffee Co."].waiting_on) == (
            "under_review",
            "third party",
        )
        # ⚠ **DRAWN `approved`, PLANTED `submitted` WITH ITS OUTCOME DECIDED
        # (2026-09-23, `DEF-CUS-6350`).** A move-in is approved only onto a unit
        # in Premises that is chosen and free, and `88 Pine Vista` is not in
        # this tenant's Premises — so Approve refuses it by name and the seed
        # leaves the row where the product stopped it, rather than rolling it
        # back to `draft` as one shared savepoint used to.
        assert (rows["Kwan, Michael"].state, rows["Kwan, Michael"].outcome) == (
            "submitted",
            "move_in",
        )
        assert rows["Alvarez, Rosa"].state == "submitted"
        # ⚠⚠ **DRAWN `Submitted` + *waiting on a scheduled date*, AND IT LANDS
        # `under_review` — THE ONE PLACE THE 2026-09-19 RULING CHANGES A ROW THE
        # BLUEPRINT DRAWS.** Parking is what sets `waiting_on`, and parking now
        # picks a submitted request up. So the register's drawn pairing of
        # *Submitted* with a waiting-on reason is no longer reachable through the
        # only door that writes that column.
        #
        # **The two columns are still orthogonal** — `waiting_on` survives the
        # move and is asserted here — which is the part of B19 §12.2 that
        # mattered. What is gone is one drawn COMBINATION, recorded in the
        # decision log rather than quietly re-asserted.
        assert (rows["Thompson, R."].state, rows["Thompson, R."].waiting_on) == (
            "under_review",
            "scheduled date",
        )

        # BR-CUS-080's link, both kinds, on one fixture — *"that is what 'we
        # need to keep them conencted' looks like in seed data."*
        #
        # ⚠ **THE REFERENCE IS THE PRODUCT'S OWN, NOT THE DRAWING'S `CON-26-0117`
        # — `DEF-CUS-6109`, and the SEED ALREADY SAID SO.** Approving now raises
        # a real build on BOTH shapes of address (PO 2026-09-21), so by the time
        # the fixture's cross-wiring step runs the request already names the
        # build the product made, and `sample_data` deliberately *"leaves a child
        # the product already named alone, not overwritten"* — the real
        # reference beats the drawing's (`B14` rule 37: a figure drawn in a
        # wireframe is an illustration, never a fact to build to).
        #
        # ⚠ **IT PASSED AT THE TIP FOR A REASON THAT WAS ITSELF THE DEFECT.** In
        # a freshly seeded tenant this request's address resolves to no premises,
        # so the raiser refused, nothing was linked, and the fixture's drawn
        # number went in unopposed. The assertion was measuring a refusal.
        #
        # So what is asserted is the RULE — one decision, one connection, named
        # on the request — and not a number a wireframe drew.
        linked = rows["Ridge Property LLC"]
        assert linked.outcome_kind == "connection"
        assert linked.outcome_ref, "the approved new connection names no build at all"
        assert linked.outcome_ref.startswith("CON-")
        assert (rows["Kwan, Michael"].outcome_kind, rows["Kwan, Michael"].outcome_ref) == (
            "account",
            "A-12048",
        )

        # BR-CUS-094's categories, set through `set_customer_category`.
        assert rows["Ridge Property LLC"].account_type.code == "builder_developer"
        assert rows["Ridge Coffee Co."].account_type.code == "commercial"
        assert rows["Osei, Grace"].account_type.code == "residential"
        # …and now they READ BACK, which is the 4.12 gap this lane closed.
        served = reads.detail(rows["Ridge Property LLC"].id)["applicant"]["customer_category"]
        assert served["account_type"]["code"] == "builder_developer"


def test_the_seeded_numbers_are_allocated_not_the_drawn_ones(brazos, dana):
    """⚠ **THE FIXTURE CANNOT CARRY `SR-26-0039…0048` AND MUST NOT PRETEND TO.**

    BR-CUS-093 numbers a request AT CREATION from the tenant's own
    `service_request` series, which on a fresh tenant starts at 0001. Seeding
    the drawn numbers would mean writing `request_no` behind the allocator's
    back, or burning 38 numbers on phantom drafts — and consequence (a)'s
    *"gaps are normal"* is about ABANDONED drafts, not manufactured ones.

    So the eight are created OLDEST FIRST, which reproduces the drawn ORDER and
    the drawn AGE column, and the numbers come out `SR-26-0001…0008`. **The
    cross-wiring travels by `CR030_SR_KEY`, never by the printed number**, and a
    J26 spec asserting the literal string `SR-26-0044` will go red on a correct
    fixture."""
    from core import sample_fixture as fixture

    with tenant_ctx(brazos):
        _seed_the_eight(dana)
        by_age = list(
            customers_models.ServiceRequest.objects.filter(tenant_id=brazos.id).order_by(
                "received_at", "id"
            )
        )
        assert [r.request_no for r in by_age] == [f"SR-26-{n:04d}" for n in range(1, 9)]

        drawn = {entry["drawn_no"] for entry in fixture.CR030_SERVICE_REQUESTS}
        assert drawn == {
            "SR-26-0039",
            "SR-26-0042",
            "SR-26-0043",
            "SR-26-0044",
            "SR-26-0045",
            "SR-26-0046",
            "SR-26-0047",
            "SR-26-0048",
        }
        assert not drawn & {r.request_no for r in by_age}

        # The AGE column is RELATIVE (DEF-629's reason: a hardcoded `Aug 08` is
        # 15 days old today and a year old next August), so the oldest thing
        # waiting is still 15 days old whenever the demo is planted.
        ages = [reads.list_row(r)["age_days"] for r in by_age]
        assert ages == [15, 11, 5, 4, 3, 2, 1, 0]


def test_the_seed_carries_br_cus_095s_worked_example_and_softens_no_default(brazos, dana):
    """**BR-CUS-095's sharpest clause, honoured by the seed.**

    *"We ship with nothing ticked, and a utility that configures nothing blocks
    nothing … no helpful pre-tick of proof of identity, however reasonable it
    looks."* The DEMO TENANT ticks two boxes for MOVE-IN only — the ruling's own
    worked example — **through `set_document_requirement`, the same call the
    Settings screen makes**, on that tenant's rows only. No migration, no
    platform row and no code default was changed to make this work, so a tenant
    that never loads sample data still ticks nothing."""
    with tenant_ctx(brazos):
        _seed_the_eight(dana)
        ticked = {
            (r.request_type, r.doc_type)
            for r in customers_models.ServiceRequestDocumentRequirement.objects.filter(
                tenant_id=brazos.id, required=True
            )
        }
        assert ticked == {
            ("move_in", "proof_of_identity"),
            ("move_in", "signed_service_agreement"),
        }
        # A TRANSFER ticks nothing and therefore blocks nothing — the second
        # half of the ruling's worked example, and the half a pre-tick breaks.
        assert writes_required("transfer") == ()

        osei = customers_models.ServiceRequest.objects.get(applicant_name="Osei, Grace")
        docs = reads.detail(osei.id)["documents"]
        # ⚠ `checklist_required` is keyed on the request's OUTCOME, and Osei's
        # is undecided — so it is empty here, and the blocking still comes from
        # the attached-but-unverified row. Asserted rather than assumed.
        assert docs["attached"] == 2
        assert docs["verified"] == 1
        assert docs["blocks_creation"] is False
        # `BR-CUS-1078` — the second gate is gone. `blocks_approval` is served
        # as a literal False rather than removed, and `outstanding` carries the
        # expression it used to.
        assert docs["blocks_approval"] is False
        assert docs["outstanding"] is True


def writes_required(outcome):
    from apps.customers import service_request_service as writes

    return tuple(writes.required_document_types(outcome))


def test_the_seed_reproduces_br_cus_090s_worked_money(brazos, dana):
    """**A $130.00 quote with nothing taken yet → $130.00 outstanding**, read
    back through the Fees tab a clerk actually sees, at CLAUDE.md rule 2's two
    precisions with the `CHAR(3)` currency beside them.

    ⛔ **FLIPPED 2026-09-24 (`OQ-CUS-12624`, `DEF-CUS-6455`).** The seed took
    **$25.00** of the $130.00 at the counter and this case read **$105.00**
    back. The desk refuses a short payment now (PO: *"all or waived"*), so the
    seed takes nothing and the request waits on the whole fee."""
    with tenant_ctx(brazos):
        _seed_the_eight(dana)
        okonkwo = customers_models.ServiceRequest.objects.get(applicant_name="Okonkwo, David")
        fees = reads.detail(okonkwo.id)["fees"]

        assert [line["charge_code"] for line in fees["lines"]] == [
            "CC-REQFEE",
            "CC-EXPEDITE",
            "CC-METERTEST",
        ]
        assert fees["quoted"]["amount"] == "130.0000"
        assert fees["quoted"]["display"] == "130.00"
        assert Decimal(fees["collected"]["amount"]) == Decimal("0")
        assert fees["outstanding"]["display"] == "130.00"
        assert not fees["receipt_no"]
        # Nothing taken, so nothing in the books (`DEF-CUS-6381`: derived from
        # the counter receipt's journal entry) and nothing waived.
        assert fees["posts_to_ledger"] is False
        assert all(line["waived"] is False for line in fees["lines"])


def test_the_seed_replays_without_writing_anything(brazos, dana):
    """**BR-TEN-063 is *"a replay writes nothing AND CHANGES NO COUNT"***, and
    the second half is the one a seeder fails quietly.

    The request NUMBER cannot be the idempotency key here — the series allocates
    it and a replay would allocate a different one, which is exactly the
    double-seed the guard has to catch — so the key is
    `address_as_given` + applicant on a SAMPLE row."""
    with tenant_ctx(brazos):
        first = _seed_the_eight(dana)
        assert first > 0
        before = customers_models.ServiceRequest.objects.filter(tenant_id=brazos.id).count()
        numbers = sorted(
            customers_models.ServiceRequest.objects.filter(tenant_id=brazos.id).values_list(
                "request_no", flat=True
            )
        )

        assert _seed_the_eight(dana) == 0
        assert customers_models.ServiceRequest.objects.filter(tenant_id=brazos.id).count() == before
        assert (
            sorted(
                customers_models.ServiceRequest.objects.filter(tenant_id=brazos.id).values_list(
                    "request_no", flat=True
                )
            )
            == numbers
        )


def test_the_seed_cannot_reproduce_the_drawn_type_column_and_says_so(brazos, dana):
    """⛔ **A FINDING, PINNED: `REQ-01`'s `TYPE` COLUMN AND `REQ-02`'s
    CLASSIFICATION CHIP DISAGREE ABOUT THE SAME REQUEST, AND BOTH ARE DRAWN.**

    B19 §12.1 draws `SR-26-0039 | MOVE-IN | Osei, Grace | … | More info needed`,
    and B19 §12.2 draws the detail of that same request with the chip
    **`NOT YET CLASSIFIED`**. One says the type is known; the other says it is
    not. This is DEF-638 12.a's shape at a different address.

    **Why the fixture lands on the detail's side, and why that is not a seeding
    bug:** the TYPE the list serves is `outcome`, and `outcome` is what the
    CLERK decides on the Decision tab — BR-CUS-071 as worded (*the system
    classifies*) was superseded by CR-031 statement 3 (*the clerk decides*), and
    `resolve_address` deliberately **writes no outcome**. So a request that has
    not been decided HAS no type, and six of the eight have not been decided.
    Seeding one would mean deciding eight requests on the clerk's behalf.

    **What that costs the demo, stated rather than discovered:** the drawn TYPE
    column shows all five job types and the fixture shows **two**; the other six
    render `type_absence: not_yet_classified`. Either the list's TYPE is a
    SECOND column — what the applicant ASKED for, which nothing stores — or the
    drawing is inconsistent with the ruling. **A defect row is owed and no lane
    may pick which.**"""
    with tenant_ctx(brazos):
        _seed_the_eight(dana)
        rows = [
            reads.list_row(r)
            for r in customers_models.ServiceRequest.objects.filter(tenant_id=brazos.id).order_by(
                "received_at", "id"
            )
        ]
        typed = [r for r in rows if r["type"] is not None]
        untyped = [r for r in rows if r["type"] is None]

        assert [r["type"] for r in typed] == ["new_connection", "move_in"]
        assert len(untyped) == 6
        # The absence is SERVED, never a blank chip and never a guessed word.
        assert all(r["type_absence"] == {"reason": "not_yet_classified"} for r in untyped)
        # Osei is the request the two drawings disagree about.
        osei = next(r for r in rows if r["applicant"] == "Osei, Grace")
        assert osei["type"] is None  # the list draws `MOVE-IN`
        assert reads.detail(osei["id"])["header"]["classification"] == "not_yet_classified"


# ═══════════════════════════════════════════════════════════════════════════
# 13 · BR-CUS-106 — THE `AGE` ACCENT IS SEVEN DAYS (PO 2026-08-25, closing D4)
# ═══════════════════════════════════════════════════════════════════════════
def test_br_cus_106_the_age_accent_starts_at_seven_days_inclusive():
    """**BR-CUS-106: *"accents a row once the request is 7 days old or more"*.**

    ⚠ **THIS CASE EXISTS FOR THE BOUNDARY, NOT FOR THE FIGURE.** The eight
    seeded requests cannot tell `>= 7` from `> 7` — their ages are
    15 · 11 · 5 · 4 · 3 · 2 · 1 · 0, so the nearest row to the line is `5d`,
    **two days clear of it**, and a `>` reading passes on the entire fixture.
    Six, seven and eight are asserted here by hand for exactly that reason: 7
    is the day the rule names and the day a careless reading gets wrong.

    `None` in, `None` out is the third case and not a rounding of it: a request
    with no `received_at` has no age, and *"we do not know how old this is"* is
    not the claim *"it is not old"*.
    """
    assert rules.AGE_ACCENT_DAYS == 7
    assert rules.age_is_accented(6) is False
    assert rules.age_is_accented(7) is True  # ⚠ the inclusive boundary
    assert rules.age_is_accented(8) is True
    assert rules.age_is_accented(0) is False
    assert rules.age_is_accented(None) is None


def test_br_cus_106_list_row_serves_the_accent_it_refused_to_serve_before(brazos, dana):
    """The flag reaches the screen from the SERVER, so REQ-01 cannot re-derive
    a threshold of its own.

    Until 2026-08-25 `list_row` deliberately served `age_days` and nothing else
    — decision D4 was open and a payload flag would have meant a lane picking
    the number. The ruling closed it; the refusal must therefore be gone, and
    a row whose age crosses the line must say so.
    """
    from datetime import datetime, time, timezone as dt_timezone

    with tenant_ctx(brazos):
        request = _new(dana, applicant_name="Boundary, Ada")
        for age_days, expected in ((7, True), (6, False)):
            received_at = datetime.combine(
                date.today() - timedelta(days=age_days), time(9, 30), tzinfo=dt_timezone.utc
            )
            customers_models.ServiceRequest.objects.filter(pk=request.id).update(
                received_at=received_at
            )
            row = reads.list_row(customers_models.ServiceRequest.objects.get(pk=request.id))
            assert row["age_days"] == age_days
            assert row["age_is_accented"] is expected


def test_br_cus_106_exactly_two_of_the_eight_seeded_requests_accent(brazos, dana):
    """**The ruling's own worked figure, on the fixture it was worked against.**

    *"at ages 15 · 11 · 5 · 4 · 3 · 2 · 1 · 0 days, exactly two accent (15 and
    11) and six do not."* Asserted by AGE rather than by request number, because
    the seeded numbers are `SR-26-0001…0008` and the drawn ones are
    `SR-26-0039…0048` — BR-CUS-093 numbers at creation from the tenant's own
    series (see `test_the_seeded_numbers_are_allocated_not_the_drawn_ones`).
    """
    with tenant_ctx(brazos):
        _seed_the_eight(dana)
        rows = [
            reads.list_row(r)
            for r in customers_models.ServiceRequest.objects.filter(tenant_id=brazos.id).order_by(
                "received_at", "id"
            )
        ]
        assert [r["age_days"] for r in rows] == [15, 11, 5, 4, 3, 2, 1, 0]
        accented = [r for r in rows if r["age_is_accented"]]
        assert [r["age_days"] for r in accented] == [15, 11]
        assert len(rows) - len(accented) == 6


# ═══════════════════════════════════════════════════════════════════════════
# 14 · THE THREE OWED STORIES, BY NAME (EP-CUS-09 · B18 task 4.16)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THESE ARE ALIASES, AND SAYING SO IS THE POINT.** EP-CUS-09 was written
# AFTER the code (hard-won law 8) and its three stories were deliberately not
# cited in any Trace header, because G10 keys off a citation and demands
# `test_us_cus_0nn_tc*` the moment one appears — *"adding the citation alone
# would make a failing gate fail wider"*. J26's activation needs the citation
# (the wiring index's `ready_by_stories` is what gate G12 check 5 reads), so
# **the citation and these aliases land in one change**, exactly as the epic
# said they must.
#
# Each alias runs the case the epic's own TC table points at, under the B8 name.
# It is NOT a second copy of the assertions: a duplicated assertion is a second
# place for a signed figure to drift (DEF-028's shape). It is the B8-named door
# onto the case that already proves the story, and it fails when that case does.
def test_us_cus_024_tc1_a_capture_saves_one_numbered_draft(brazos, dana):
    """US-CUS-024 TC-1 (= TC-REQ-1) — `REQ-03` saves one numbered draft."""
    test_a_request_opens_as_a_draft_and_is_numbered_at_creation(brazos, dana)


def test_us_cus_024_tc2_the_same_draft_submitted_twice_is_idempotent(brazos, dana):
    """US-CUS-024 TC-2 (= TC-REQ-2) — one number, not two (hard rule 6)."""
    test_br_cus_093_a_repeated_submit_is_idempotent(brazos, dana)


def test_us_cus_024_tc8_twenty_five_dollars_against_a_hundred_and_thirty(brazos, dana):
    """US-CUS-024 TC-8 — BR-CUS-090's worked counter collection: since
    2026-09-24 (`OQ-CUS-12624`) the $25.00 is REFUSED and the $130.00 taken."""
    test_br_cus_090_the_counter_takes_the_whole_fee_or_refuses(brazos, dana)


def test_us_cus_024_tc9_an_identifier_field_is_refused_by_name(brazos, dana):
    """US-CUS-024 TC-9 — BR-CUS-092: refused BY NAME, never silently dropped.

    ⚠ **STILL TRUE, FOR TWELVE NAMES OUT OF THIRTEEN.** DEF-632 (PO 2026-08-27)
    made `ssn` storable and nothing else; the case it delegates to now asserts
    both halves — the SSN round-trips, and every other identifier name still
    answers `BIZ_STATE`.
    """
    test_br_cus_092_the_ssn_is_captured_and_the_rest_stay_refused(brazos, dana)


def test_us_cus_025_tc2_the_list_is_newest_first(brazos, dana):
    """US-CUS-025 TC-2 — `REQ-01` renders oldest first and segments by state."""
    test_the_list_is_newest_first_and_segments_by_state(brazos, dana)


def test_us_cus_025_tc4_the_kpi_strip_counts_what_the_screen_labels(brazos, dana):
    """US-CUS-025 TC-4 — five tiles from the server; OLDEST is never `0 days`."""
    test_the_kpi_strip_counts_what_the_screen_labels(brazos, dana)


def test_us_cus_025_tc5_a_disconnect_row_is_lawful(brazos, dana):
    """US-CUS-025 TC-5 — BR-CUS-091: a DISCONNECT is a lawful type here."""
    test_br_cus_091_a_disconnect_commits_and_is_not_a_move_out(brazos, dana)


def test_us_cus_025_tc14_the_age_accent_is_seven_days(brazos, dana):
    """US-CUS-025 TC-REQ-14 — **REPLACED, not deleted.**

    The case used to prove a 15-day row and a 2-day row were styled IDENTICALLY,
    because decision D4 was open. BR-CUS-106 closed it at seven days inclusive,
    so the inversion is obsolete and the real rule is asserted in its place.
    """
    test_br_cus_106_the_age_accent_starts_at_seven_days_inclusive()
    test_br_cus_106_exactly_two_of_the_eight_seeded_requests_accent(brazos, dana)


def test_us_cus_026_tc_the_detail_serves_all_six_tabs(brazos, dana):
    """US-CUS-026 — `REQ-02`'s six tabs are all served."""
    test_the_detail_serves_all_six_tabs(brazos, dana)


def test_us_cus_026_tc7_an_unverified_document_is_reported_not_refused(brazos, dana):
    """US-CUS-026 TC-7 (= TC-REQ-7) — GATE TWO, as `BR-CUS-1078` left it: the
    document is reported and the approval proceeds."""
    test_an_unverified_document_is_reported_and_the_approval_goes_through(brazos, dana)


def test_us_cus_026_tc9_a_refusal_needs_a_reason_and_keeps_the_request(brazos, dana):
    """US-CUS-026 TC-9 (= TC-REQ-9) — a refusal with no reason is refused."""
    test_refuse_needs_a_reason_and_keeps_the_request(brazos, dana)


def test_us_cus_026_tc10_a_refusal_is_terminal_and_stays_on_the_timeline(brazos, dana):
    """US-CUS-026 TC-10 (= TC-REQ-10) — the timeline keeps the refusal FOREVER.

    ⚠ **RENAMED AND RE-POINTED 2026-09-19.** It delegated to
    `test_a_refusal_survives_a_reopen_in_the_event_log`, which the same ruling
    deleted along with `reopen` — leaving this case raising `NameError` at call
    time rather than failing an assertion. The half of TC-10 that survives the
    ruling is the append-only timeline, and that is what it now delegates to.
    """
    test_a_refusal_is_terminal_and_its_reason_stays_on_the_timeline(brazos, dana)


# ═══════════════════════════════════════════════════════════════════════════
# THE ACTION BAR IS DRIVEN BY STATE — PO ratification 2026-09-20 §1
# ═══════════════════════════════════════════════════════════════════════════
#
# The PO's table, ratified in the words *"this is correct - fix it"* and
# transcribed from `12-governance/02-decision-log.md`:
#
#     | State            | Submit | Approve | Ask for more | Refuse | Park |
#     | Draft            | ✅ only lawful action | ✗ | ✗ | ✗ | ✗ |
#     | Submitted        | ✗ | ✅ | ✅ | ✅ | ✅ (→ Under review) |
#     | Under review     | ✗ | ✅ | ✅ | ✅ | ✗ |
#     | More info needed | ✗ | ✅ | ✅ | ✅ | ✗ |
#     | Approved         | ✗ | ✗ | ✗ | ✗ | ✗ |
#     | Refused          | ✗ | ✗ | ✗ | ✗ | ✗ |
#
#: One row per state: the four moves `TRANSITIONS` allows from it, and whether
#: the screen may offer `Park`.
RATIFIED_ACTION_BAR: tuple[tuple[str, frozenset[str], bool], ...] = (
    (rules.DRAFT, frozenset({rules.SUBMIT}), False),
    (rules.SUBMITTED, frozenset({rules.APPROVE, rules.REFUSE, rules.REQUEST_INFO}), True),
    (rules.UNDER_REVIEW, frozenset({rules.APPROVE, rules.REFUSE, rules.REQUEST_INFO}), False),
    (rules.MORE_INFO, frozenset({rules.APPROVE, rules.REFUSE, rules.REQUEST_INFO}), False),
    (rules.APPROVED, frozenset(), False),
    (rules.REFUSED, frozenset(), False),
)


@pytest.mark.parametrize(("state", "moves", "can_park"), RATIFIED_ACTION_BAR)
def test_the_action_bar_matches_the_ratified_table(state, moves, can_park):
    """The screen's contract, asserted where the screen reads it.

    ⚠ **THE ROW IS NOT SAVED AND DOES NOT NEED TO BE.** `_actions` reads
    `state` and `outcome` and nothing else, and four of these six states can no
    longer be REACHED by any sequence of moves — the 2026-09-19 ruling took the
    nine transitions that led into them out of the table, and `under_review` is
    reached only by parking. Driving each one would be testing the fixture.

    ⚠ **`can_park` CHANGED HERE ON 2026-09-20 AND THE WRITE PATH DID NOT.** It
    answered `not is_terminal(state)`, which is a different question from the
    one the screen asks, and it was wrong on FOUR states: it offered `Park` on
    `draft`, `under_review` and `more_info`, where parking moves nothing, and on
    `approved`, which is **not a terminal state** — `TERMINAL_STATES` is
    `(completed, refused, withdrawn, closed)`. The ratified table says
    `submitted` only, which is also the only state `park` moves anything from.

    **`park()` itself is untouched**, deliberately: it still writes `waiting_on`
    from any non-terminal state and still refuses a terminal one. That refusal
    is a second line of defence, and narrowing the WRITE would go beyond the
    ratification — which is about what the SCREEN offers.
    """
    row = customers_models.ServiceRequest(state=state, outcome="")
    assert set(rules.actions_available(state)) == set(moves)
    assert reads._actions(row, [])["can_park"] is can_park



# ═══════════════════════════════════════════════════════════════════════════
# THE DRAFT MINIMUM — PO ratification 2026-09-20, decision log §3
# ═══════════════════════════════════════════════════════════════════════════
#
# PO, verbatim: *"this is correct"* on the gate table, plus *"we should show a
# message in short to user when this happens"*.
#
# | Gate                      | Required now                   |
# |---------------------------|--------------------------------|
# | Save as draft, steps 1–2  | applicant name alone           |
# | Staff-raised (collections)| nothing                        |
# | Submit                    | applicant name + address       |
#
# **The address requirement MOVES to submit; it does not disappear.** The
# defect it answers: `address_as_given` is captured on step 3 while `Save as
# draft` is a header action on every step, so the control was permanently
# disabled on steps 1 and 2 for every request type in the product.
#
# ⚠ **THE PORTAL DOOR IS DELIBERATELY NOT MOVED.** `create_from_portal` goes
# STRAIGHT to `submitted` (its own comment: *"a guest has no draft to come back
# to"*), so for that door create-time IS submit-time and the submit minimum is
# the one that applies. `_clean_capture`'s `require_address` defaults True and
# only `create_request` passes False.
def test_a_draft_is_created_from_the_applicant_name_alone(brazos, dana):
    """Steps 1–2 of REQ-03 ask for a name and never for an address."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos, opening=48)
        request = sr.create_request(
            dana, {"channel": "physical_form", "applicant_name": "Okonkwo, David"}
        )
        assert request.state == customers_models.ServiceRequest.DRAFT
        # BR-CUS-093 — numbered from the same instant, which is the whole point
        # of the ruling this unblocks: a number to read down the phone before
        # the applicant has finished spelling their surname.
        assert request.request_no == "SR-26-0048"
        assert not request.address_as_given


def test_a_staff_raised_draft_is_created_from_nothing(brazos, dana):
    """BR-CUS-091 keeps the name off a staff-raised request, and the ruling
    takes the address off the create path — so collections opens a row with
    neither and fills it in afterwards."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos, opening=60)
        request = sr.create_request(dana, {"channel": "staff_collections"})
        assert request.state == customers_models.ServiceRequest.DRAFT
        assert request.request_no
        assert not request.applicant_name
        assert not request.address_as_given


def test_an_applicant_raised_draft_still_needs_the_name(brazos, dana):
    """The name did NOT move. Only the address did."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        with pytest.raises(errors.ApiError) as caught:
            sr.create_request(dana, {"channel": "physical_form"})
        assert caught.value.message_key == "customers.serviceRequest.fieldRequired"
        assert caught.value.params["field"] == "applicant_name"


def test_a_draft_started_with_no_address_can_still_be_given_one(brazos, dana):
    """⚠ **THE TRAP THE RULING NAMES, PROVED ABSENT.**

    `BR-CUS-070` makes `address_as_given` immutable *after capture*, and that is
    implemented as *after the row leaves DRAFT* — `service_request_service.py`
    refuses only `if "address_as_given" in cleaned and request.state != DRAFT`.
    A blank therefore does NOT count as captured, so the clerk reaches step 3
    and the field is writable. A draft that could never be given an address
    would be a worse bug than the one being fixed."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        request = sr.create_request(
            dana, {"channel": "physical_form", "applicant_name": "Okonkwo, David"}
        )
        sr.update_request(dana, request.id, {"address_as_given": "14 Willow Bend"})
        assert sr.request_row(request.id).address_as_given == "14 Willow Bend"
        # And once it leaves DRAFT it is frozen again, exactly as before.
        sr.submit(dana, request.id)
        with pytest.raises(errors.BizError) as caught:
            sr.update_request(dana, request.id, {"address_as_given": "somewhere else"})
        assert caught.value.message_key == "customers.serviceRequest.addressAsGivenImmutable"


def test_submit_refuses_a_request_with_no_address(brazos, dana):
    """*"There is no service request about nowhere."* The requirement moved
    here; it did not disappear."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        request = sr.create_request(
            dana, {"channel": "physical_form", "applicant_name": "Okonkwo, David"}
        )
        with pytest.raises(errors.ApiError) as caught:
            sr.submit(dana, request.id)
        assert caught.value.message_key == "customers.serviceRequest.fieldRequired"
        assert caught.value.params["field"] == "address_as_given"
        assert sr.request_row(request.id).state == customers_models.ServiceRequest.DRAFT


def test_submit_refuses_a_staff_raised_request_with_no_address(brazos, dana):
    """A staff-raised row may be created from nothing; it may not be SUBMITTED
    from nothing. BR-CUS-091 lifts the applicant identity and never the
    address."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        request = sr.create_request(dana, {"channel": "staff_collections"})
        with pytest.raises(errors.ApiError) as caught:
            sr.submit(dana, request.id)
        assert caught.value.params["field"] == "address_as_given"
        sr.update_request(dana, request.id, {"address_as_given": "500 Main"})
        # No applicant name, and that is lawful for this channel — BR-CUS-091.
        result = sr.submit(dana, request.id)
        assert result["request"].state == customers_models.ServiceRequest.SUBMITTED


def test_submit_refuses_an_applicant_raised_request_whose_name_was_cleared(brazos, dana):
    """`update_request` is `partial=True` and checks no required field, so the
    name can be blanked after creation. Submit is where that is caught."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        request = sr.create_request(dana, {"channel": "staff_collections"})
        sr.update_request(
            dana,
            request.id,
            {"channel": "physical_form", "address_as_given": "14 Willow Bend"},
        )
        with pytest.raises(errors.ApiError) as caught:
            sr.submit(dana, request.id)
        assert caught.value.params["field"] == "applicant_name"


def test_the_portal_door_still_requires_the_address_at_creation(brazos, dana):
    """`create_from_portal` submits in the same transaction, so its minimum is
    the SUBMIT minimum and nothing about it moved."""
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        with pytest.raises(errors.ApiError) as caught:
            sr.create_from_portal(
                {"applicant_name": "Okonkwo, David", "applicant_phone": "555-0142"}
            )
        assert caught.value.message_key == "customers.serviceRequest.fieldRequired"
        assert caught.value.params["field"] == "address_as_given"


# ═══════════════════════════════════════════════════════════════════════════
# THE BACK CONTROL NAMES WHERE IT EXITS TO — PO report 2026-09-20 §8
# ═══════════════════════════════════════════════════════════════════════════
#
# The PO pressed the back control on an approved MOVE-IN request and landed on
# the requests list: *"when i lick on register - it shoudl take me to movein
# list page - instead it takes me to request list page"*. Four catalogue keys
# rendered the identical string `The register` and went to four destinations.
#
#: The queue each outcome's work lands on. ⚠ **THE EXPECTED VALUE IS READ BACK
#: OUT OF `request_jobs.JOB_SHAPES` RATHER THAN TYPED HERE**, because a second
#: copy of that map is exactly what the ruling forbids — *"that map is the
#: single source; a second one is how two screens come to disagree"*. What this
#: asserts is that the HEADER reads it, and that it reads it only once approved.
@pytest.mark.parametrize(
    "outcome",
    [
        customers_models.ServiceRequest.OUTCOME_NEW_CONNECTION,
        customers_models.ServiceRequest.OUTCOME_MOVE_IN,
        customers_models.ServiceRequest.OUTCOME_MOVE_OUT,
        customers_models.ServiceRequest.OUTCOME_TRANSFER,
        customers_models.ServiceRequest.OUTCOME_DISCONNECT,
    ],
)
def test_an_approved_request_names_the_queue_its_work_landed_on(outcome):
    """One queue per outcome, from the map that already answers the question."""
    from apps.customers import request_jobs

    row = customers_models.ServiceRequest(state=rules.APPROVED, outcome=outcome)
    assert reads._queue_for(row) == request_jobs.JOB_SHAPES[outcome]["queue"]


@pytest.mark.parametrize(
    "state", [rules.DRAFT, rules.SUBMITTED, rules.UNDER_REVIEW, rules.MORE_INFO, rules.REFUSED]
)
def test_an_unapproved_request_names_no_queue(state):
    """⚠ **AN OUTCOME BEFORE APPROVAL IS A PROPOSAL, NOT A DESTINATION.**
    `decision.commit.outcome` can be written and rewritten while a clerk
    thinks, and no job exists on any queue to go and look at. So a request
    carrying `move_in` and sitting in `draft` still goes back to the requests
    list — where it was raised, and the only place an unapproved one is
    findable."""
    row = customers_models.ServiceRequest(
        state=state, outcome=customers_models.ServiceRequest.OUTCOME_MOVE_IN
    )
    assert reads._queue_for(row) is None



def test_a_draft_takes_the_screens_own_payload_shape_blank_address_and_all(brazos, dana):
    """⚠ **THE SHAPE THE EIGHT CASES ABOVE DO NOT TEST — `DEF-CUS-6008`.**

    Every case above OMITS `address_as_given`, and Django's `TextField` default
    then puts `""` in the column. **The capture screen never omits it**: a
    controlled input always sends a string, so what actually arrives on step 1
    is `address_as_given: ""` — and `_text("")` returns `None` against a NOT
    NULL column. The create died with `NotNullViolation` in a browser while all
    eight of those cases were green, because the shape under test was a shape
    the product does not send.

    So this one posts what `capturePayload` posts, blanks and all.
    """
    with tenant_ctx(brazos):
        _seed_sr_series(brazos)
        request = sr.create_request(
            dana,
            {
                "channel": "physical_form",
                "applicant_kind": "person",
                "applicant_name": "Osei, Grace",
                "applicant_email": "",
                "applicant_phone": "",
                "address_as_given": "",
                "address_unit_as_given": "",
                "what_they_said": "",
            },
        )
        assert request.address_as_given == ""
        assert request.request_no
        # And a PATCH that still carries the blank does not reach the constraint
        # by the other door — `update_request` is partial and sends the same "".
        sr.update_request(dana, request.id, {"address_as_given": "", "applicant_phone": "555-0142"})
        assert sr.request_row(request.id).address_as_given == ""
        # The submit gate reads it as absent, which is what "" means here.
        with pytest.raises(errors.ApiError) as caught:
            sr.submit(dana, request.id)
        assert caught.value.params["field"] == "address_as_given"
