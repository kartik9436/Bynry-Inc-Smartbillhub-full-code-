# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-015 (S22's disconnect-notice modal — the only story that
#           owns any part of this surface; S90 still has none and one is OWED)
#           Screens: S22 · S90 (`DSC-02.3`, B18 §5.8)
# Change:   DEF-692 — B18 drew four delivery channels, marked certified mail
#           REQUIRED for legal proof, and no adapter existed for any of them.
# Rules:    BR-CUS-100 (the SEND is in-app; the PROOF is a record a person
#           enters; a tier-3 cut must not be schedulable on an unrecorded
#           service — PO 2026-08-25) · BR-CUS-039 (certified mail REQUIRED on
#           the final tier) · BR-MET-110 (the same human-record discipline —
#           *"somebody decided, and the record must name them"*) ·
#           BR-NOT-005 (a notice is WRITTEN; only the dispatcher sends) ·
#           BR-CUS-082 (a closed account cannot be cut) · BR-TEN-003 (a
#           cross-tenant id is a 404, never a 403) · BR-TEN-043 (the event date
#           is an argument, never a wall clock) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 4 (corrections are new rows) · rule 7 (audit)
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.8.2 (`LAST
#           NOTICE` is a delivery claim this product cannot make) · `DSC-02.3`
#           (the ladder's *"Served Aug 22 · certified mail"*, `HOW IT GOES OUT`
#           with certified mail *"Required at tier 3 — proof of service"*, and
#           `NOTICE SERVED Aug 22 certified mail, signed for`)
# ───────────────────────────────────────────────────────
"""BR-CUS-100 — the proof of service, and the cut it stands in front of.

**THE CASE THIS FILE EXISTS FOR IS
`test_br_cus_100__a_tier_3_cut_is_refused_on_an_unrecorded_service`**, and it is
the one to read first. `DEF-692` is a screen that draws certified mail as
`Required at tier 3 — proof of service` over a product with no adapter for any
channel at all. The PO's answer separates the two halves — BR-CUS-100, verbatim:

    "So the two halves are separated and neither pretends to be the other: the
    SEND is in-app (and later email/SMS/print), and the PROOF is a **record a
    person enters** — the channel used, the reference, and the date it was
    signed for. That is what a regulator asks to see, and recording it is
    honest where claiming to have sent it is not."

— and puts one guard in front of the most serious action this product takes:
*"a tier-3 cut must not be schedulable on an unrecorded service, because that
is the one thing on this screen whose absence is not merely untidy."*

⚠ **TWO ASSERTIONS HERE ARE DELIBERATELY NEGATIVE AND MUST STAY THAT WAY.**

  1. `test_recording_proof_does_not_claim_a_send` asserts that `delivery_state`
     is STILL NULL after a proof is recorded, with its reason intact. Recording
     what a person did at a post office says nothing about whether this product
     delivered anything, and a lane that "tidies" this by setting
     `delivery_state = 'certified sent'` has rebuilt DEF-692 exactly.
  2. `test_the_signature_is_not_required_and_that_question_is_OWED` asserts that
     a cut is schedulable on a certified item that has NOT yet been signed for.
     **That is not a ruling that unclaimed mail is sufficient** — it is the
     absence of one. Nothing signed says whether the signature must come back
     first, and `assert_service_proved` therefore does not read `signed_for_on`.
     If a later lane makes this test assert the opposite, it must be because the
     PO ruled — not because a green test looked safer.

**RED PROVED FIRST for every guard** (hard-won law 7). Each was broken under a
`# BREAK: … — RESTORE …` marker, run, the failure quoted in the lane report, and
the mutation reverted — DEF-666 is a lane that died mid-proof and left its
mutation in a shared tree, so no marker survives in this file.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnects
from apps.tenancy import models as tenancy_models  # noqa: F401 — parity with the W7 suite

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    audit_rows,
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_w7_disconnects import _account, _at_tier, _owes

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 25)

#: `DSC-02.3`'s own worked case — `A-11340 · 77 Industrial Way`, $8,240.00
#: outstanding, tier 3 served **Aug 22 by certified mail** and the earliest
#: lawful cut computed at **Aug 24**. The figures are the drawn screen's, so a
#: reader can hold this file beside it.
NORTHWIND_OWED = D("8240.00")
SERVED_ON = date(2026, 8, 22)
CUT_ON = date(2026, 8, 24)
ARTICLE_NO = "7020 1810 0001 2345 6789"


def _case_at_tier_3(actor, tenant, monkeypatch, *, name="Northwind Mfg."):
    """An account walked to TIER 3 through the real `advance()`, never by UPDATE.

    A tier set with an UPDATE proves that a column can hold a string. What these
    tests need is a case that ARRIVED at tier 3 through the gate every other
    path goes through — and, crucially, that therefore has a REAL tier-3 notice
    row for a proof to be recorded against.
    """
    _owes(monkeypatch, NORTHWIND_OWED)
    account = _account(actor, tenant, name=name)
    _at_tier(actor, account["id"], disconnects.TIER_3)
    return account


def _tier_3_notice(account_id):
    case = disconnects.open_case_for(account_id)
    return disconnects.latest_notice_at_tier(case, disconnects.TIER_3)


# ════════════════════════════════════════════════════════════════════════════
# THE COLUMNS — A NOTICE IS RAISED, NOT SERVED, AND THE GAP IS THE QUEUE
# ════════════════════════════════════════════════════════════════════════════
def test_a_raised_notice_carries_no_proof_and_the_nulls_are_the_queue(brazos, marcus, monkeypatch):
    """BR-CUS-100 — the six columns say a notice was RAISED, never that it was SERVED.

    `BR-MET-110`'s shape, and `apps/metering/connections.py` states it for
    `work_orders.accepted_by` in its own words: *"Nullable because an order can
    be completed and not yet reviewed — that gap IS the review queue, and a NULL
    here is the only thing that says an order is waiting for a person."*
    """
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        row = _tier_3_notice(account["id"])

        assert row.service_channel is None
        assert row.proof_reference is None
        assert row.served_on is None
        assert row.signed_for_on is None
        assert row.proof_recorded_by_id is None
        assert row.proof_recorded_at is None

        # Three notices were raised climbing the ladder; all three are waiting.
        queue = disconnects.notices_awaiting_proof()
        assert len(queue) == 3
        assert [entry["tier"] for entry in queue] == [
            disconnects.TIER_1,
            disconnects.TIER_2,
            disconnects.TIER_3,
        ]
        assert all(entry["recorded"] is False for entry in queue)

        proof = disconnects.service_proof_for(
            disconnects.open_case_for(account["id"]), tier=disconnects.TIER_3
        )
        assert proof["recorded"] is False
        assert proof["absence"] == "awaiting_proof_of_service"


# ════════════════════════════════════════════════════════════════════════════
# ⛔ THE GUARD — *"a tier-3 cut must not be schedulable on an unrecorded service"*
# ════════════════════════════════════════════════════════════════════════════
def test_br_cus_100__a_tier_3_cut_is_refused_on_an_unrecorded_service(brazos, marcus, monkeypatch):
    """**THE CASE THIS FILE EXISTS FOR.** BR-CUS-100, verbatim: *"a tier-3 cut
    must not be schedulable on an unrecorded service, because that is the one
    thing on this screen whose absence is not merely untidy."*

    The case is at tier 3, the balance is real, nothing protects the account and
    `assert_cut_reachable` passes — every OTHER condition for a cut is met. The
    only thing missing is a person's record of how the final notice was served,
    and that alone refuses it.
    """
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.schedule_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert refusal.value.code == "cut_on_unrecorded_service"
        assert refusal.value.br_ref == "BR-CUS-100"

        # The refusal is not a side effect of some other guard: the case is
        # otherwise cut-ready, which `assert_cut_reachable` confirms in silence.
        disconnects.assert_cut_reachable(disconnects.open_case_for(account["id"]))

        # And nothing was written. A refused cut leaves no date behind.
        case = disconnects.open_case_for(account["id"])
        assert case.cut_scheduled_for is None
        assert case.state != disconnects.STATE_SCHEDULED


def test_recording_the_proof_is_what_lets_the_cut_be_scheduled(brazos, marcus, monkeypatch):
    """The same case, one attestation later — `DSC-02.3`'s own worked dates.

    *"NOTICE SERVED Aug 22 certified mail, signed for"* → the cut is schedulable
    for Aug 24. **This test is the other half of the guard above**: a guard that
    only ever refuses is indistinguishable from a broken path.
    """
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        recorded = disconnects.record_proof_of_service(
            marcus,
            notice.id,
            channel=disconnects.SERVE_CERTIFIED_MAIL,
            reference=ARTICLE_NO,
            served_on=SERVED_ON,
            signed_for_on=SERVED_ON,
        )
        assert recorded["recorded"] is True
        assert recorded["channel"] == disconnects.SERVE_CERTIFIED_MAIL
        assert recorded["reference"] == ARTICLE_NO
        assert recorded["served_on"] == "2026-08-22"

        scheduled = disconnects.schedule_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert scheduled["state"] == disconnects.STATE_SCHEDULED
        assert scheduled["cut_scheduled_for"] == "2026-08-24"


def test_a_tier_3_proof_must_name_certified_mail(brazos, marcus, monkeypatch):
    """`DSC-02.3`: certified mail is *"Required at tier 3 — proof of service"*.

    BR-CUS-039 says the same of the final tier in its own words. A door hanger
    is a real, recordable service — it is simply not the one two signed
    documents require before a cut, so the record is ACCEPTED and the CUT is
    refused. Those are different answers and the product gives both.

    ⚠ If a utility lawfully serves tier 3 another way — personal delivery, a
    sheriff — that is a ruling to take with the PO. This lane did not take it;
    the refusal names `TIER_3_REQUIRED_CHANNEL` so the amendment has one home.
    """
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        disconnects.record_proof_of_service(
            marcus,
            notice.id,
            channel=disconnects.SERVE_DOOR_HANGER,
            reference="crew-4491",
            served_on=SERVED_ON,
        )
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.schedule_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert refusal.value.code == "tier_3_proof_not_certified"
        assert refusal.value.br_ref == "BR-CUS-039"


def test_the_signature_is_not_required_and_that_question_is_OWED(brazos, marcus, monkeypatch):
    """A DELIBERATELY NEGATIVE ASSERTION — read the docstring before changing it.

    A certified item posted on Aug 22 and not yet signed for schedules the cut.
    **This is not a ruling that unclaimed mail suffices.** Nothing in
    BR-CUS-100, `DSC-02.3`, BR-CUS-039 or any other signed document says whether
    the signature must have COME BACK before a cut, and choosing either reading
    here would decide for real households whether an unclaimed letter stops a
    disconnection. `assert_service_proved` therefore does not read
    `signed_for_on` at all, and the question is REPORTED as owed.
    """
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        recorded = disconnects.record_proof_of_service(
            marcus,
            notice.id,
            channel=disconnects.SERVE_CERTIFIED_MAIL,
            reference=ARTICLE_NO,
            served_on=SERVED_ON,
        )
        assert recorded["signed_for_on"] is None

        scheduled = disconnects.schedule_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert scheduled["cut_scheduled_for"] == "2026-08-24"


def test_a_cut_with_no_tier_3_notice_at_all_is_refused_with_its_own_absence(
    brazos, marcus, monkeypatch
):
    """*"Nothing was raised"* and *"nobody said how it went out"* are different facts.

    A regulator asks about both, so `service_proof_for` answers them with
    different `absence` codes even though the cut is refused either way.
    """
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        case = disconnects.open_case_for(account["id"])
        # The tier-3 letter is withdrawn from the record; the chip stays.
        disconnects.DisconnectNotice.objects.filter(case=case, tier=disconnects.TIER_3).delete()

        assert disconnects.service_proof_for(case)["absence"] == "no_notice_at_this_tier"
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.schedule_cut(marcus, account["id"], cut_on=CUT_ON, as_of=TODAY)
        assert refusal.value.code == "cut_on_unrecorded_service"


# ════════════════════════════════════════════════════════════════════════════
# THE SEND AND THE PROOF ARE NOT THE SAME RECORD — DEF-692's OWN CONFUSION
# ════════════════════════════════════════════════════════════════════════════
def test_recording_proof_does_not_claim_a_send(brazos, marcus, monkeypatch):
    """A DELIBERATELY NEGATIVE ASSERTION — `delivery_state` STAYS NULL.

    BR-CUS-100: *"proof of service is a **legal artefact produced outside this
    product**: a posted item, a tracking number, a signature that came back. No
    adapter can manufacture one."* Recording what a person did at a post office
    says nothing about whether THIS PRODUCT delivered anything, and there is
    still no email, SMS or print adapter in this release. A lane that "tidies"
    this by setting `delivery_state = 'certified sent'` has rebuilt DEF-692.
    """
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        payload = disconnects.record_proof_of_service(
            marcus,
            notice.id,
            channel=disconnects.SERVE_CERTIFIED_MAIL,
            reference=ARTICLE_NO,
            served_on=SERVED_ON,
        )
        notice.refresh_from_db()
        assert notice.delivery_state is None
        assert notice.delivery_unavailable_reason == disconnects.DELIVERY_UNAVAILABLE["code"]
        # …and the payload says so out loud, so no caller can read a recorded
        # proof as a delivery this product performed.
        assert payload["delivery_state"] is None
        assert payload["delivery"]["code"] == "delivery_adapter_absent"


def test_the_in_app_bell_is_a_send_and_is_refused_as_a_serving_channel(brazos, marcus, monkeypatch):
    """⛔ BR-CUS-100's whole point, as a refusal.

    *"IN-APP DOES NOT SATISFY CERTIFIED MAIL, AND THE RULE MUST NOT BE READ AS
    IF IT DID."* In-app is the confirmed SEND channel for the notice; it can
    never be the proof that the notice was served.
    """
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.record_proof_of_service(
                marcus,
                notice.id,
                channel=disconnects.SERVE_IN_APP_IS_A_SEND,
                reference="bell-991",
                served_on=SERVED_ON,
            )
        assert refusal.value.code == "in_app_is_a_send_not_a_proof"
        notice.refresh_from_db()
        assert notice.proof_recorded_at is None


def test_an_undrawn_channel_is_refused_rather_than_stored(brazos, marcus, monkeypatch):
    """`DSC-02.3` draws five ways a notice is served; a sixth needs a ruling."""
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.record_proof_of_service(
                marcus,
                notice.id,
                channel="carrier_pigeon",
                reference="X-1",
                served_on=SERVED_ON,
            )
        assert refusal.value.code == "service_channel_unknown"


# ════════════════════════════════════════════════════════════════════════════
# WHAT THE RECORD MUST CONTAIN, AND WHO IT NAMES
# ════════════════════════════════════════════════════════════════════════════
def test_a_proof_without_its_reference_is_refused(brazos, marcus, monkeypatch):
    """BR-CUS-100 names three things the record IS: *"the channel used, the
    reference, and the date it was signed for"*. A proof with no article number
    is what a regulator cannot check."""
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.record_proof_of_service(
                marcus,
                notice.id,
                channel=disconnects.SERVE_CERTIFIED_MAIL,
                reference="   ",
                served_on=SERVED_ON,
            )
        assert refusal.value.code == "proof_needs_a_reference"


def test_a_signature_cannot_come_back_before_the_item_was_served(brazos, marcus, monkeypatch):
    """One of the two dates is a typing error, and the statutory period is
    computed from the served date (`DSC-02.3`: *"Computed as Aug 22 plus 48
    hours"*). Accepting it would compute a lawful cut date from a fiction."""
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.record_proof_of_service(
                marcus,
                notice.id,
                channel=disconnects.SERVE_CERTIFIED_MAIL,
                reference=ARTICLE_NO,
                served_on=SERVED_ON,
                signed_for_on=date(2026, 8, 20),
            )
        assert refusal.value.code == "signed_for_before_served"


def test_the_record_names_the_person_and_the_moment(brazos, marcus, monkeypatch):
    """BR-MET-110, cited by BR-CUS-100 as the same discipline: *"somebody
    decided, and the record must name them."*"""
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        disconnects.record_proof_of_service(
            marcus,
            notice.id,
            channel=disconnects.SERVE_CERTIFIED_MAIL,
            reference=ARTICLE_NO,
            served_on=SERVED_ON,
        )
        notice.refresh_from_db()
        assert str(notice.proof_recorded_by_id) == str(marcus.id)
        assert notice.proof_recorded_at is not None
        # BR-TEN-043 is not violated: the BUSINESS date is the argument, and the
        # wall clock records only when the attestation was made.
        assert notice.served_on == SERVED_ON


def test_recording_proof_writes_an_audit_row(brazos, marcus, monkeypatch, audit_rows):
    """CLAUDE.md rule 7 as this module widens it — *"every state change in this
    module writes `audit_log`"* — and BR-MET-110's own reason: the human act is
    the part that must be auditable."""
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        disconnects.record_proof_of_service(
            marcus,
            notice.id,
            channel=disconnects.SERVE_CERTIFIED_MAIL,
            reference=ARTICLE_NO,
            served_on=SERVED_ON,
        )
        assert disconnects.AUDIT_PROOF_RECORDED in audit_actions(audit_rows)
        written = [row for row in audit_rows if row["action"] == disconnects.AUDIT_PROOF_RECORDED][
            -1
        ]
        assert written["after"]["reference"] == ARTICLE_NO
        assert written["after"]["channel"] == disconnects.SERVE_CERTIFIED_MAIL


# ════════════════════════════════════════════════════════════════════════════
# WRITTEN ONCE — HARD RULE 4's DISCIPLINE ON A REGULATOR'S RECORD
# ════════════════════════════════════════════════════════════════════════════
def test_a_recorded_proof_is_never_re_pointed(brazos, marcus, monkeypatch):
    """Hard rule 4 — *"corrections are new rows"* — applied to the record a
    utility shows a regulator when a customer says they were never told.

    The first write fills columns that were NULL because the notice was waiting
    for them. A second is refused by name, and the original survives untouched.
    """
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        disconnects.record_proof_of_service(
            marcus,
            notice.id,
            channel=disconnects.SERVE_CERTIFIED_MAIL,
            reference=ARTICLE_NO,
            served_on=SERVED_ON,
        )
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.record_proof_of_service(
                marcus,
                notice.id,
                channel=disconnects.SERVE_POSTED,
                reference="another-one",
                served_on=date(2026, 8, 23),
            )
        assert refusal.value.code == "proof_already_recorded"

        notice.refresh_from_db()
        assert notice.proof_reference == ARTICLE_NO
        assert notice.service_channel == disconnects.SERVE_CERTIFIED_MAIL
        assert notice.served_on == SERVED_ON


def test_the_database_holds_the_proof_ALL_OR_NOTHING(brazos, marcus, monkeypatch):
    """A half-recorded proof is the shape that would let the guard pass on a row
    naming no channel and no article number — a cut authorised by a record that
    says nothing. The service refuses it; the DATABASE is what makes the
    sentence true of the data (hard-won law 1)."""
    from django.db.utils import IntegrityError

    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        notice.served_on = SERVED_ON  # a date, and nothing else
        with pytest.raises(IntegrityError):
            notice.save(update_fields=["served_on"])


def test_the_database_refuses_a_channel_nobody_drew(brazos, marcus, monkeypatch):
    """`ck_disconnect_notice_service_channel` — the vocabulary, held by the
    database as well as by `record_proof_of_service`, because a guard in Python
    is not a guarantee about the data."""
    from django.db.utils import IntegrityError
    from django.utils import timezone

    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice = _tier_3_notice(account["id"])

        notice.service_channel = disconnects.SERVE_IN_APP_IS_A_SEND
        notice.proof_reference = "bell-991"
        notice.served_on = SERVED_ON
        notice.proof_recorded_at = timezone.now()
        with pytest.raises(IntegrityError):
            notice.save(
                update_fields=[
                    "service_channel",
                    "proof_reference",
                    "served_on",
                    "proof_recorded_at",
                ]
            )


# ════════════════════════════════════════════════════════════════════════════
# TENANT SCOPING — CLAUDE.md RULE 1, AND BR-TEN-003's 404
# ════════════════════════════════════════════════════════════════════════════
def test_a_notice_from_another_tenant_is_not_found_never_forbidden(
    brazos, lonestar, marcus, erin, monkeypatch
):
    """BR-TEN-003 — a cross-tenant id is a 404, never a 403. A refusal that
    distinguishes *"not yours"* from *"does not exist"* tells a competitor which
    of their neighbours' households are being chased."""
    with tenant_ctx(brazos):
        account = _case_at_tier_3(marcus, brazos, monkeypatch)
        notice_id = _tier_3_notice(account["id"]).id

    with tenant_ctx(lonestar):
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.record_proof_of_service(
                erin,
                notice_id,
                channel=disconnects.SERVE_CERTIFIED_MAIL,
                reference=ARTICLE_NO,
                served_on=SERVED_ON,
            )
        assert refusal.value.code == "notice_not_found"
        assert refusal.value.br_ref == "BR-TEN-003"
        # …and the queue read is scoped the same way.
        assert disconnects.notices_awaiting_proof() == ()


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-CUS-100 (PO 2026-08-25, closing DEF-692) · BR-CUS-039 ·
#         BR-MET-110 (the cited discipline) · `DSC-02.3` · B18 §5.8.2
# generated: 2026-08-25 by lane PROOF (W7 proof of service)
# checklist: A✔ B=deferred(no frontend half — S90 is task 7.11 and is not in
#         this lane's write scope; the queue read is REPORTED as unwired)
#         C✔ D=deferred(no API half — S90's endpoints are tasks 7.11/7.9)
#         E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — measured, not claimed
# exceptions: (1) whether a tier-3 cut requires the SIGNATURE to have come back
#         is written nowhere and is REPORTED as owed; `assert_service_proved`
#         does not read `signed_for_on`. (2) whether a proof CORRECTION is a new
#         notice or a dedicated row is likewise unwritten — the second write is
#         refused and the question REPORTED. (3) `notices_awaiting_proof` is
#         BUILT AND NOT WIRED (hard-won law 2) — no screen calls it yet.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
