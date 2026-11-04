# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-053 (EP-CWP-10) — a plan the utility has offered you, and
#           your signature on it. Screen: CWP-063
# Rules:    BR-CWP-065 (a plan activates on the CUSTOMER's signature ALONE) ·
#           BR-CWP-063 (new bills still arrive and still have to be paid) ·
#           BR-CWP-001 (the portal writes rows of exactly SIX kinds — a
#           signature is none of them) · BR-CUS-043 (one live plan per account;
#           late-fee suspension is a PER-PLAN election) · B14 rule 31
# Golden:   ❄️ GT-47 is the instalment arithmetic this READS — nothing here
#           recomputes a schedule
# Open:     OQ-CWP-1566 (the offer's expiry has no column) · OQ-CWP-1567 (the
#           clerk's name lives only on a pruned audit row) · OQ-CWP-1568 (may
#           the portal accept, decline or counter?)
# Tests:    this file
# Impacts:  apps/portal/seams/payments_seam.py `plan_offer_for` ·
#           apps/portal/selectors.py `plan_offer`
# ───────────────────────────────────────────────────────
"""`US-CWP-053`'s cases — and the one §7 says is the worst outcome available.

⚠ **THE FIGURES ON THE OFFER MUST BE BYTE-IDENTICAL TO THE PLAN THAT WOULD
ACTIVATE.** *"A customer who accepts one schedule and receives another is the
worst outcome on this screen."* This read composes
`plans.payment_plans_for_account` — the S24 wizard's OWN read — rather than a
second query, so the identity holds by construction; the tests below assert it
anyway, because a later lane could always add a second path.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.payments import collections_models, plans as payments_plans
from apps.portal import selectors as portal_selectors
from apps.portal.seams import payments_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import elm_street_account, switch_on

TODAY = date(2026, 9, 3)
OFFERED_ON = date(2026, 9, 2)

#: `US-CWP-053` §4's own figures: `$172.20` covered, `$40.00` up front, five at
#: `$22.03` and a final `$22.05`. `40.00 + 5 × 22.03 + 22.05 = 172.20`.
COVERS = Decimal("172.2000")
DOWN = Decimal("40.0000")
REGULAR = Decimal("22.0300")
FINAL = Decimal("22.0500")


def an_offered_plan(tenant, account, *, suspend_late_fees=True, status=None):
    """One plan sitting at `agreement_sent` — the state this screen exists for.

    Written through the ORM rather than through `propose_payment_plan` because
    the WRITE path is the S24 wizard's and is tested there; what this file
    tests is the READ a customer gets, and seeding the row directly is what
    lets a twin fixture sit at a different status without a clerk.
    """
    plan = collections_models.PaymentPlan.objects.create(
        tenant=tenant,
        account=account,
        total_amount=COVERS,
        down_payment=DOWN,
        currency="USD",
        installment_count=6,
        cadence="monthly",
        status=status or collections_models.PLAN_AGREEMENT_SENT,
        suspend_late_fees=suspend_late_fees,
        suspend_disconnect=True,
        proposed_on=OFFERED_ON,
        agreement_sent_on=OFFERED_ON,
    )
    for seq in range(1, 7):
        collections_models.PaymentPlanInstallment.objects.create(
            tenant=tenant,
            plan=plan,
            seq=seq,
            due_date=date(2026, 9 + seq - 1, 14) if seq <= 4 else date(2027, seq - 4, 14),
            amount=FINAL if seq == 6 else REGULAR,
            currency="USD",
        )
    return plan


def read(tenant, account):
    with tenant_context(tenant.id):
        return payments_seam.plan_offer_for([account.pk], as_of=TODAY)


@pytest.mark.django_db
def test_us_cwp_053_tc1_the_offer_reads_at_agreement_sent_with_its_figures(pine_hill, sarah):
    """`$172.20` covered with `$40.00` already received, offered 2 September."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_offered_plan(pine_hill, account)
    offer = read(pine_hill, account)
    assert offer is not None
    assert Decimal(offer["total_amount"]) == COVERS
    assert Decimal(offer["down_payment"]) == DOWN
    assert Decimal(offer["spread"]) == COVERS - DOWN == Decimal("132.2000")
    assert offer["agreement_sent_on"] == "2026-09-02"
    assert offer["status"] == collections_models.PLAN_AGREEMENT_SENT


@pytest.mark.django_db
def test_us_cwp_053_the_instalments_SUM_to_what_the_plan_covers(pine_hill, sarah):
    """§7's invariant, and the test the story says catches a plan that silently
    covers the wrong figure: `$40.00` + `5 × $22.03` + `$22.05` = `$172.20`."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_offered_plan(pine_hill, account)
    offer = read(pine_hill, account)
    scheduled = sum((Decimal(row["amount"]) for row in offer["installments"]), Decimal("0"))
    assert scheduled == Decimal("132.2000")
    assert scheduled + Decimal(offer["down_payment"]) == COVERS
    # ⚠ The rounding lands on the LAST row and nowhere else (BR-CUS-043).
    assert Decimal(offer["installments"][-1]["amount"]) == FINAL


@pytest.mark.django_db
def test_us_cwp_053_tc3_a_plan_at_PROPOSED_is_not_an_offer_yet(pine_hill, sarah):
    """⚠ **`agreement_sent` IS THE ONLY STATE THIS SCREEN EXISTS FOR.** A plan
    the clerk is still building has not been offered to anybody, and showing it
    would tell a customer to accept something nobody has sent them."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_offered_plan(pine_hill, account, status=collections_models.PLAN_PROPOSED)
    assert read(pine_hill, account) is None


@pytest.mark.django_db
def test_us_cwp_053_an_ACTIVE_plan_is_not_an_offer_either(pine_hill, sarah):
    """An accepted plan belongs on `CWP-043`, which is `US-CWP-052`'s screen."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        plan = an_offered_plan(pine_hill, account)
        plan.status = collections_models.PLAN_ACTIVE
        plan.signed_on = TODAY
        plan.save(update_fields=["status", "signed_on"])
    assert read(pine_hill, account) is None


@pytest.mark.django_db
def test_us_cwp_053_an_account_with_no_plan_answers_None(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    assert read(pine_hill, account) is None


@pytest.mark.django_db
def test_us_cwp_053_tc9_the_consequences_are_read_from_THIS_PLANS_elections(pine_hill, sarah):
    """`BR-CUS-043` — late-fee suspension is a PER-PLAN election, so a plan with
    it OFF says fees still apply rather than promising they stop (J41 step 4).
    Four hardcoded bullets would be wrong on exactly that plan."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_offered_plan(pine_hill, account, suspend_late_fees=False)


    with tenant_context(pine_hill.id):
        body = portal_selectors.plan_offer(account, today=TODAY)
    consequences = body["offer"]["consequences"]
    assert portal_selectors.CONSEQUENCE_LATE_FEES_CONTINUE in consequences
    assert portal_selectors.CONSEQUENCE_LATE_FEES_STOP not in consequences
    # BR-CWP-063 — on the row since 2026-08-11 so no screen has to remember it.
    assert portal_selectors.CONSEQUENCE_NEW_BILLS_STILL_DUE in consequences
    assert portal_selectors.CONSEQUENCE_NO_DISCONNECT in consequences


@pytest.mark.django_db
def test_us_cwp_053_tc2_5_6_ALL_THREE_CONTROLS_ARE_HELD_and_no_write_path_exists(pine_hill, sarah):
    """⚠ **THE BOUNDARY THIS STORY STOPS AT, ASSERTED RATHER THAN DESCRIBED.**

    `BR-CWP-001` lists the six kinds of row the portal may write and a plan
    signature is none of them. So the body says all three controls are held,
    and — the half a comment could not promise — `apps.portal.services` exposes
    no function that could move a plan. `G81` fails the build on a seventh
    write point; this asserts the portal has not grown one behind its back.
    """
    from apps.portal import services as portal_services

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_offered_plan(pine_hill, account)


    with tenant_context(pine_hill.id):
        body = portal_selectors.plan_offer(account, today=TODAY)
    assert body["offer"]["actions_held"] is True
    assert body["offer"]["actions_held_reason"] == "OQ-CWP-1568"

    # ⚠ **THE ASSERTION IS ABOUT A PLAN'S STATE, NOT ABOUT THE WORD *plan*.**
    # A first draft refused any public name containing "plan" and went RED on
    # `PLAN_ASK_NOTE` — a CONSTANT another lane added for `US-CWP-051`, whose
    # *ask for a plan* raises a SERVICE REQUEST, which is write point ② and
    # entirely lawful. A check that cannot tell a request from a signature
    # would have blocked a correct feature, which is worse than not checking.
    #
    # What this actually forbids is a portal CALLABLE that moves a plan:
    # accepting, declining, signing or activating one. G81 already refuses any
    # public function here that no write point declares; this names the four
    # verbs, so the day somebody adds `accept_plan` and a matching row, the
    # test says so rather than the gate quietly going green on a seventh kind.
    moves_a_plan = ("accept", "decline", "sign", "activate")
    for name in dir(portal_services):
        if name.startswith("_") or not callable(getattr(portal_services, name)):
            continue
        lowered = name.lower()
        assert not (
            "plan" in lowered and any(verb in lowered for verb in moves_a_plan)
        ), f"portal.services grew {name} — a plan signature is not one of the six writes"

    # And nothing moved the row.
    with tenant_context(pine_hill.id):
        plan = payments_plans.live_plan_for(account.pk)
    assert plan.status == collections_models.PLAN_AGREEMENT_SENT
    assert plan.signed_on is None


@pytest.mark.django_db
def test_us_cwp_053_the_expiry_and_the_clerks_name_are_NAMED_ABSENCES_not_guesses(pine_hill, sarah):
    """⚠ **NO COLUMN HOLDS THE EXPIRY, AND IT IS NOT INVENTED.**

    `payment_plans` carries `proposed_on`, `agreement_sent_on`, `signed_on` and
    `closed_on` and no expiry (`OQ-CWP-1566`). A computed `offered_on + 14`
    would state a deadline this product cannot enforce.

    ⚠ **THE CLERK'S NAME MOVED, AND THIS ASSERTION MOVED WITH IT** (`CR-085`
    `CPB-21`, `OQ-CWP-1567` CLOSED 2026-09-08 option (a)). It read
    `offered_by_unavailable == "OQ-CWP-1567"` and now reads `not_recorded`,
    because there IS a column and this plan simply has nothing in it: the
    fixture writes the row through the ORM without an actor, which is exactly
    the shape of every plan written before the migration. The absence is still
    NAMED and still not guessed — what changed is why it is absent.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_offered_plan(pine_hill, account)


    with tenant_context(pine_hill.id):
        body = portal_selectors.plan_offer(account, today=TODAY)
    offer = body["offer"]
    assert offer["expires_on"] is None
    assert offer["expires_on_unavailable"] == "OQ-CWP-1566"
    assert offer["offered_by"] is None
    assert offer["offered_by_unavailable"] == "not_recorded"
    # The expiry column genuinely does not exist — asserted so that the day it
    # is added, this test says so rather than the screen quietly staying silent.
    assert not hasattr(collections_models.PaymentPlan, "offer_expires_on")


@pytest.mark.django_db
def test_cr085_cpb21_the_offer_NAMES_THE_PERSON_WHO_SET_IT_UP(pine_hill, sarah):
    """`CPB-21` — *"The plan reads 'Agreed with … on Aug 14'"*.

    ⚠ **`OQ-CWP-1567` CLOSED 2026-09-08, OPTION (a).** The clerk used to exist
    only on the `payment_plan.rows_written` audit row, and `audit_log` is
    pruned on a retention schedule — so option (b), publishing an audit read,
    would have made this sentence true for a while and then quietly false on a
    plan that is still running, with nothing going red on the day it turned.
    The plan keeps the fact itself now.

    ⚠ **A NAME, NEVER AN ID** (B14 rule 31). `payments` resolves the person
    because the portal may not read `identity` at all (`BR-CWP-004`; `G91`
    reads the portal's identity seam with `ast` and fails on a second model).
    Both halves are asserted: the name is served, and no id reaches the body.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        plan = an_offered_plan(pine_hill, account)
        # ⚠ `sarah` is a staff ACTOR (a namespace carrying id, pk, role and
        # user), which is what `core.audit.money_action` takes. The FK wants
        # the row.
        plan.offered_by = sarah.user
        plan.save(update_fields=["offered_by"])
        body = portal_selectors.plan_offer(account, today=TODAY)
    offer = body["offer"]
    assert offer["offered_by"] == sarah.user.full_name
    assert offer["offered_by_unavailable"] is None
    # B14 rule 31 — the id the seam resolved from never reaches the browser.
    assert "offered_by_user_id" not in offer
    assert str(sarah.pk) not in repr(offer)


@pytest.mark.django_db
def test_cr085_cpb21_the_WIZARDS_OWN_WRITE_PATH_records_the_clerk(pine_hill, sarah):
    """The column is filled by the S24 wizard, not only by a fixture.

    ⚠ **THIS IS THE HALF A SEEDED ROW CANNOT PROVE** (hard-won law 2: built is
    not wired). `an_offered_plan` writes through the ORM, so every assertion
    above would pass over a `propose_payment_plan` that never set the column.
    This drives the REAL write and reads the value back out of the published
    read.
    """
    from apps.customers import payment_plan as customers_payment_plan

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    # ⚠ **THE WIZARD'S OWN ARITHMETIC, ❄️ FROZEN AS `GT-47`, CALLED RATHER
    # THAN TYPED** — a fixture that typed six figures would prove the row
    # renders and prove nothing about the schedule.  The seam's contract is
    # `((seq, due_date, amount), …)`; `build_schedule` returns the richer
    # object the wizard draws from, so it is narrowed here exactly as
    # `apps/customers` narrows it.
    built = customers_payment_plan.build_schedule(
        total=COVERS,
        down_payment=DOWN,
        installments=6,
        cadence="monthly",
        first_due_date=date(2026, 9, 14),
    )
    schedule = tuple((row.seq, row.due_date, row.amount) for row in built.installments)
    with tenant_context(pine_hill.id):
        payments_plans.propose_payment_plan(
            actor=sarah,
            account_id=account.pk,
            total_amount=COVERS,
            down_payment=DOWN,
            installments=6,
            schedule=schedule,
            proposed_on=OFFERED_ON,
        )
        rows = payments_plans.payment_plans_for_account(account.pk, as_of=TODAY)
    assert rows[0]["offered_by_name"] == sarah.user.full_name
    assert rows[0]["offered_by_user_id"] == str(sarah.pk)


@pytest.mark.django_db
def test_cr085_cpb21_a_plan_written_by_NOBODY_names_nobody(pine_hill, sarah):
    """⚠ **AN AUTOMATION MUST NOT BORROW A PERSON.**

    `core.audit.money_action`'s own docstring is emphatic that an
    `AutomationActor` has no `.id` and that resolving it by `getattr` alone
    *"writes a BLANK row … and the failure is invisible until a customer
    disputes a fee six weeks later"*. Here the blank IS the right answer, and
    this test exists so that a later lane which "simplifies" the actor read
    into something that invents a fallback user goes red.
    """
    from apps.customers import payment_plan as customers_payment_plan
    from core.audit import ACTOR_KIND_RUNBOOK, AutomationActor

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    # ⚠ **THE WIZARD'S OWN ARITHMETIC, ❄️ FROZEN AS `GT-47`, CALLED RATHER
    # THAN TYPED** — a fixture that typed six figures would prove the row
    # renders and prove nothing about the schedule.  The seam's contract is
    # `((seq, due_date, amount), …)`; `build_schedule` returns the richer
    # object the wizard draws from, so it is narrowed here exactly as
    # `apps/customers` narrows it.
    built = customers_payment_plan.build_schedule(
        total=COVERS,
        down_payment=DOWN,
        installments=6,
        cadence="monthly",
        first_due_date=date(2026, 9, 14),
    )
    schedule = tuple((row.seq, row.due_date, row.amount) for row in built.installments)
    with tenant_context(pine_hill.id):
        payments_plans.propose_payment_plan(
            actor=AutomationActor(kind=ACTOR_KIND_RUNBOOK, name="Arrears sweep", version="1"),
            account_id=account.pk,
            total_amount=COVERS,
            down_payment=DOWN,
            installments=6,
            schedule=schedule,
            proposed_on=OFFERED_ON,
        )
        body = portal_selectors.plan_offer(account, today=TODAY)
    offer = body["offer"]
    assert offer["offered_by"] is None
    assert offer["offered_by_unavailable"] == "not_recorded"


@pytest.mark.django_db
def test_us_cwp_053_the_body_carries_NO_DATABASE_ID(pine_hill, sarah):
    """B14 rule 31 — and there is nothing on this screen that needs to name the
    plan back to the server, because all three controls are held."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        plan = an_offered_plan(pine_hill, account)


    with tenant_context(pine_hill.id):
        body = portal_selectors.plan_offer(account, today=TODAY)
    text = repr(body)
    assert str(plan.pk) not in text
    assert str(plan.pk)[:8] not in text
    assert str(account.pk) not in text
    assert "id" not in body["offer"]


@pytest.mark.django_db
def test_us_cwp_053_tc8_TENANT_ISOLATION_an_oak_ridge_session_sees_no_pine_hill_offer(
    pine_hill, sarah, oak_ridge, elena
):
    """`BR-CWP-010` — the tenant half, proved from the side that matters: an
    Oak Ridge session handed Pine Hill's own account id gets nothing."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_offered_plan(pine_hill, account)
    with tenant_context(oak_ridge.id):
        assert payments_seam.plan_offer_for([account.pk], as_of=TODAY) is None
    assert read(pine_hill, account) is not None, "the read itself still works"


# ═══════════════════════════════════════════════════════════════════════════
# CR-085 · `CPB-03` — THE AGREEMENT IS SERVED, NOT HELD
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THE HOLD IT REPLACES WAS A HOLD ON NOTHING.** `CWP-063`'s *The agreement ↓*
# read *Downloads are not ready yet* over a document this product had already
# frozen and could already serve: `bill_document_pdf` has streamed the same kind
# of bytes, out of the same store, behind the same `download` permission, since
# `US-CWP-034`.
#
# ⚠ **THE FIXTURE FREEZES IT AGAINST THE MESSAGE, WHICH IS THE ONLY PLACE IT
# EVER LANDS.** `frozen_documents` freezes an agreement at DISPATCH, so the
# stored row's `source_type` is `outbound_message` and the plan is reached
# through the queue row that carried it. Freezing it against the plan directly
# would be a state this product never produces, and a test in one is a test of
# nothing (`DEF-WRK-4121`).

AGREEMENT_PDF = b"%PDF-1.4 cr085 cpb03 agreement\n"


@pytest.fixture()
def agreement_docs_dir(tmp_path, settings):
    """A per-test document directory, so no case reads another's bytes."""
    settings.DOCUMENT_STORAGE_BACKEND = "filesystem"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
    settings.DOCUMENT_STORAGE_DIR = str(tmp_path / "documents")
    return tmp_path / "documents"


def a_posted_agreement(tenant, account, plan):
    """The agreement as a POSTED letter, frozen the way the dispatcher freezes."""
    from apps.notifications import models as notification_models
    from apps.tenancy import document_models, document_store

    message = notification_models.OutboundMessage.objects.create(
        tenant=tenant,
        source_type="plan",
        source_id=plan.pk,
        channel=notification_models.CHANNEL_PRINT,
        account=account,
        template_code="contract_payment_plan",
        status=notification_models.STATUS_SENT,
        # ⚠ `ck_outbound_msgs_address_or_reason` — a queue row states WHERE it
        # went or WHY it could not. A print row carries the posting address.
        recipient_address="1408 Elm St · A",
    )
    return document_store.store(
        kind=document_models.KIND_PAYMENT_PLAN_AGREEMENT,
        source_type=document_models.SOURCE_OUTBOUND_MESSAGE,
        source_id=message.pk,
        content_type="application/pdf",
        display_name="payment-plan-agreement.pdf",
        payload=AGREEMENT_PDF,
        channel=notification_models.CHANNEL_PRINT,
        process="notifications.dispatcher",
    )


@pytest.mark.django_db
def test_cr085_cpb03_the_kept_agreement_is_SERVED_byte_for_byte(
    pine_hill, sarah, agreement_docs_dir
):
    """`CPB-03` — *a customer can download what we sent them*, for a plan.

    ⚠ **BYTE-IDENTICAL, AND HASH-VERIFIED ON THE WAY OUT.**
    `document_store.fetch` recomputes the hash rather than taking it on trust,
    so a copy whose bytes moved refuses instead of being served — `BR-NOT-027`'s
    posture, and the same one `printed_bill_bytes` takes.
    """
    from apps.portal.seams import notifications_seam

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        plan = an_offered_plan(pine_hill, account)
        a_posted_agreement(pine_hill, account, plan)
        served = notifications_seam.plan_agreement_bytes(plan_id=plan.pk)

    assert served is not None, "the agreement was frozen and the seam could not find it"
    payload, content_type, filename = served
    assert payload == AGREEMENT_PDF
    assert content_type == "application/pdf"
    # B14 rule 31 — named for what it IS, never for a row id.
    assert filename == "payment-plan-agreement.pdf"


@pytest.mark.django_db
def test_cr085_cpb03_a_plan_with_NO_kept_copy_answers_None_and_never_a_re_render(
    pine_hill, sarah, agreement_docs_dir
):
    """⚠ **NO FALLBACK** (`BR-CWP-045`). A re-render would hand the customer a
    document that is not the one they were sent, and the screen already has a
    sentence for the absence."""
    from apps.portal.seams import notifications_seam

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        plan = an_offered_plan(pine_hill, account)
        assert notifications_seam.plan_agreement_bytes(plan_id=plan.pk) is None


@pytest.mark.django_db
def test_cr085_cpb03_the_SCREENS_available_flag_and_the_download_cannot_disagree(
    pine_hill, sarah, agreement_docs_dir
):
    """⚠ **THE INVARIANT THE WHOLE CHANGE STANDS ON.**

    The button is drawn from `offer.agreement.available`, which
    `correspondence_reads._stored` computes; the bytes come from a different
    function. If the two ever asked different questions, the screen would offer
    a download that refuses — a hold and a promise disagreeing about one
    document. This asserts them together, in both directions, so a later lane
    that changes one is told about the other.
    """
    from apps.portal.seams import notifications_seam

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        plan = an_offered_plan(pine_hill, account)
        before = portal_selectors.plan_offer(account, today=TODAY)["offer"]["agreement"]
        assert before["available"] is False
        assert notifications_seam.plan_agreement_bytes(plan_id=plan.pk) is None

        a_posted_agreement(pine_hill, account, plan)
        after = portal_selectors.plan_offer(account, today=TODAY)["offer"]["agreement"]
        assert after["available"] is True
        assert notifications_seam.plan_agreement_bytes(plan_id=plan.pk) is not None
