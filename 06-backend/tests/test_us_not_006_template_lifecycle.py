# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-006 (version lifecycle, publish rights, pinning + category
#           assignment — for EVERY designer S91+)   Screens: S8 · S67 · S94–S106
# Rules:    BR-BIL-026 (edit = a new version; publishing affects FUTURE renders
#           only; a render uses the PINNED version) · BR-BIL-027 (Clerk drafts +
#           test-renders · Admin publishes · a pinned version is audit-locked) ·
#           BR-BIL-025 (category default, account override) · BR-NOT-001
#           (category variants + mandatory default fallback) · BR-NOT-002
#           (contract versions effective-dated) · BR-NOT-006 (type × category ×
#           language; fallback recorded, never a blank) · A19 rule 6 (versioned
#           + audit-logged)
# ───────────────────────────────────────────────────────
"""The seven US-NOT-006 test cases, plus what the store unblocked.

Every case uses the story's own §4 fixtures: the "Past-due reminder" email v2
published / v3 draft, the receipt v1 pinned by sent receipts, the service
agreement v1 (effective Jan 1 2026) / v2 (effective Sep 1 2026), and the actors
Priya Menon (drafts) / Alex Reed (publishes) — cast here as the repo's own
`marcus` (Billing Clerk) and `dana` (System Admin) fixtures, because the names
in the pack are the personas and these are the roles they carry.

⚠ TWO CASES ARE PROVED IN TWO PLACES AND ONLY ONE OF THEM IS HERE. TC-6 (a
direct UPDATE of a published body) and the non-draft DELETE are enforced by a
POSTGRES TRIGGER (migration 0006) as well as by the service. sqlite has no
triggers, so the case below asserts the SERVICE refusal and the database half
lives in `test_us_not_006_template_isolation.py` behind `requires_postgres`.
Stated rather than left to look like full coverage (hard-won law 1).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.notifications import catalogs, models, rendering, services
from apps.notifications import template_models as tm
from apps.notifications import template_service

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: A19 r8's dunning row, reduced to catalogued tokens. Used wherever a case
#: needs a legal printable body and the body itself is not the subject.
REMINDER_BODY = "Hi {first_name}, {balance} is {days_late} days late. Call {support_phone}."

#: A19 r8's receipt row — one transaction and nothing else.
RECEIPT_BODY = "Thanks {first_name}! We received {amount} on {date}. Confirmation {confirmation}."

#: A19 §2's disconnect class, reduced to catalogued tokens and carrying the
#: regulatory marker `mandatory_content` makes non-removable (US-NOT-007 TC-6).
#: ⚠ USED WHERE A CASE NEEDS A CLASS THE PLATFORM DOES NOT SEED. From
#: 2026-08-16 provisioning plants `dunning` and `receipt` on every tenant
#: (DEF-163), so a case whose subject is *"nothing is published"* cannot use
#: those two: the fixture tenant publishes them before the test starts, and the
#: assertion would pass or fail for a reason that has nothing to do with the
#: lifecycle. `disconnect_notice` is catalogued, is NOT seeded (OQ-243 — A19 §2
#: gives three tier bodies and a variant holds one) and carries no
#: effective-dating rule, which makes it the only clean stand-in.
#: This string is a TEST FIXTURE and is not a letter: no tenant renders it.
DISCONNECT_BODY = (
    "Your account {account_no} is past due in the amount of {balance}. Pay by {pay_by_date} "
    "to avoid interruption at {service_address}. {state_puc_ref}"
)

#: A19 §3's payment-plan agreement, reduced to its own tokens.
#: ⚠ `{schedule_table}` ADDED 2026-08-18 AND IT IS NOT DECORATION — the class
#: made it MANDATORY content (BR-NOT-016 CONFIRMED, PO 2026-08-16: *"Print the
#: schedule inside the agreement"*), so a payment-plan body without it is now
#: refused at save. Without this line the two cases below fail with *"the
#: 'contract_payment_plan' class must carry '{schedule_table}'"*, which is the
#: guard doing its job on a fixture rather than on a customer's agreement.
CONTRACT_BODY = (
    "{utility_name} and {customer_name} ({account_no}) agree on {today}: {balance} in {n} "
    "instalments after {down} down, by {payment_method}.\n{schedule_table}\n"
    "Signed {customer_signature} {date}."
)


def variant(actor, code, *, name="Template", category=None, language=None):
    # DEF-207: `register` now reports `(row, created)`. This helper keeps
    # handing back the row alone — nothing in this file asks whether the row
    # was created, and a helper that returned a tuple would push that question
    # onto forty call sites that do not have it.
    row, _created = template_service.register(
        code=code,
        name=name,
        actor=actor,
        category=category or tm.VARIANT_DEFAULT,
        language=language or tm.VARIANT_DEFAULT,
    )
    return row


def published(actor_clerk, actor_admin, code, body, **kwargs):
    """A variant with one published version — the ordinary starting point."""
    template = variant(
        actor_clerk,
        code,
        category=kwargs.pop("category", None),
        language=kwargs.pop("language", None),
    )
    draft = template_service.save_draft(template=template, body=body, actor=actor_clerk, **kwargs)
    template_service.publish(version_row=draft, actor=actor_admin)
    return template, draft


# ── TC-1 · every edit is a NEW append-only version ──────────────────────────
def test_us_not_006_tc1__an_edit_creates_a_new_draft_and_leaves_the_published_row(
    brazos, marcus, dana, audit_rows
):
    """US-NOT-006 TC-1: *"Priya edits 'Past-due reminder' email → New draft v3
    append-only (v2 published untouched); designer header shows 'v3 · edited Aug
    9, 2026'; save audited."*

    The story's fixture is an EMAIL class, and every email class is registered
    in `CLASSES_WITHOUT_CATALOG` (OQ-206) — so the case is run on the printable
    dunning class, which A19 gives tokens to, and the email half is asserted
    separately below as the refusal it currently is. That substitution is named
    rather than quietly made.

    ⚠ **THE COMMERCIAL VARIANT, since 2026-08-16 (DEF-163).** Provisioning now
    publishes the tenant-default `dunning` body on every tenant, so a case that
    asserts *"the first edit produces v1 then v2"* on that variant would be
    counting the platform's seed rather than the lifecycle. A different
    consumer-category variant of the same class starts empty and keeps the
    numbers exact — which is what this case is about. The substitution is named,
    like the one above it.
    """
    with tenant_ctx(brazos):
        template, v1 = published(
            marcus, dana, "dunning", REMINDER_BODY, category=tm.CATEGORY_COMMERCIAL
        )
        v2 = template_service.save_draft(
            template=template, body=REMINDER_BODY + " Thank you.", actor=marcus
        )

    assert (v1.version, v2.version) == (1, 2)
    assert v2.status == tm.VERSION_DRAFT
    v1.refresh_from_db()
    assert v1.status == tm.VERSION_PUBLISHED  # untouched by the edit
    assert v1.body == REMINDER_BODY  # the published bytes did not move
    assert template_service.AUDIT_SAVED in [row["action"] for row in audit_rows]


def test_us_not_006_an_email_class_cannot_be_drafted_because_oq_206_is_open(brazos, marcus):
    """A class with no merge-variable catalog registers and cannot be DRAFTED —
    the variant appears on the S8 card awaiting its content, and the save
    refuses quoting the catalog's own reason.

    ⚠ AMENDED 2026-08-17 (DEF-210). This case was `email_past_due`, and the PO's
    ruling *"please define it for this product"* gave it a palette and a body,
    so it now drafts normally.

    ⚠ **AMENDED AGAIN 2026-08-18 (CR-011 item 9) — THE FAR SIDE OF THE BOUNDARY
    IS NOW EMPTY.** The last four classes with no palette were the contracts, and
    the PO ruled, verbatim: *"the 4 template classes needing legal wording -
    already answer - provide default and allow user to change"*. So
    `contract_deposit` DRAFTS, and this case is inverted to prove it — the thing
    a utility could not do yesterday.

    **What still refuses on a contract, and it is the constraint the CR left
    standing:** BR-NOT-002's effective date. A contract draft with no
    `effective_from` is refused, because *"the version chosen is frozen onto a
    signed agreement forever"* — and that is why no contract is seeded at
    provisioning. Both directions are asserted; a test that only checked a
    refusal would still pass on the day somebody deleted every palette.
    """
    with tenant_ctx(brazos):
        drafts_now = variant(marcus, "email_past_due", name="Past-due reminder")
        assert drafts_now.group == catalogs.GROUP_EMAIL
        template_service.save_draft(template=drafts_now, body="You owe {balance}.", actor=marcus)

        contract = variant(marcus, "contract_deposit", name="Deposit agreement")
        assert contract.group == catalogs.GROUP_CONTRACT
        drafted = template_service.save_draft(
            template=contract,
            body="You agree to a deposit of {amount}. {customer_signature} {date}",
            actor=marcus,
            effective_from=date(2026, 9, 1),
        )
        assert drafted.effective_from == date(2026, 9, 1)

        # BR-NOT-002 — the refusal that remains, and the reason nothing seeds it.
        with pytest.raises(template_service.TemplateRefused, match="effective_from"):
            template_service.save_draft(
                template=contract, body="You agree to a deposit of {amount}.", actor=marcus
            )

        # …and the palette still bites on a contract, which is what a body being
        # ALLOWED must never be confused with.
        with pytest.raises(rendering.RenderRefused, match="meter_no"):
            template_service.save_draft(
                template=contract,
                body="Meter {meter_no}.",
                actor=marcus,
                effective_from=date(2026, 9, 1),
            )


# ── TC-2 · the rights split, server-side ────────────────────────────────────
def test_us_not_006_tc2__a_clerk_cannot_publish_and_an_admin_publish_archives_the_previous(
    brazos, marcus, dana, audit_rows
):
    """US-NOT-006 TC-2, verbatim: *"Priya attempts Publish; Alex publishes →
    Clerk publish server-rejected; Admin publish → v3 published, v2
    auto-archived (one published per template); only renders AFTER see v3."*

    PROVED RED by widening `@require_role(SYSTEM_ADMIN)` on `publish` to include
    BILLING_CLERK: the Clerk's publish then succeeded and this failed with
    `Failed: DID NOT RAISE AuthError`.
    """
    from core import errors

    with tenant_ctx(brazos):
        template, v1 = published(marcus, dana, "dunning", REMINDER_BODY)
        v2 = template_service.save_draft(
            template=template, body=REMINDER_BODY + " (v2)", actor=marcus
        )

        with pytest.raises(errors.AuthError):
            template_service.publish(version_row=v2, actor=marcus)
        v2.refresh_from_db()
        assert v2.status == tm.VERSION_DRAFT  # the refusal changed nothing

        template_service.publish(version_row=v2, actor=dana)

    v1.refresh_from_db()
    v2.refresh_from_db()
    assert (v1.status, v2.status) == (tm.VERSION_ARCHIVED, tm.VERSION_PUBLISHED)
    assert template_service.AUDIT_PUBLISHED in [row["action"] for row in audit_rows]

    # "only renders AFTER see v3" — resolution now points at v2 and the older
    # version is still loadable by its pin, forever.
    with tenant_ctx(brazos):
        assert template_service.resolve(code="dunning").version == v2.version
        assert (
            template_service.load_pinned(template_id=template.pk, version=v1.version).body
            == REMINDER_BODY
        )


# ── TC-3 · contracts are effective-dated (BR-NOT-002) ───────────────────────
def test_us_not_006_tc3__contract_generation_picks_the_version_in_effect(brazos, marcus, dana):
    """US-NOT-006 TC-3, verbatim: *"Service-agreement v2 effective Sep 1;
    generation Aug 20 renders v1, generation Sep 2 renders v2; a contract signed
    on v1 references v1 forever."*

    Run on the payment-plan agreement, because it is the one contract type A19
    gives a token catalog (§3) — the other three were OQ-206 until the PO ruled
    on 2026-08-18 (*"provide default and allow user to change"*) and now have
    authored palettes of their own. Left on this class rather than moved: TC-3's
    own words are about a service agreement, and the version-in-effect mechanism
    is identical on all four.

    Both versions are PUBLISHED at once — which is exactly why the "one
    published per template" index is partial on `effective_from IS NULL`.
    """
    with tenant_ctx(brazos):
        template, v1 = published(
            marcus,
            dana,
            "contract_payment_plan",
            CONTRACT_BODY,
            effective_from=date(2026, 1, 1),
        )
        v2 = template_service.save_draft(
            template=template,
            body=CONTRACT_BODY + " Rev 2.",
            actor=marcus,
            effective_from=date(2026, 9, 1),
        )
        template_service.publish(version_row=v2, actor=dana)

        august = template_service.resolve(code="contract_payment_plan", on_date=date(2026, 8, 20))
        september = template_service.resolve(code="contract_payment_plan", on_date=date(2026, 9, 2))

    assert august.version == v1.version
    assert september.version == v2.version
    v1.refresh_from_db()
    assert v1.status == tm.VERSION_PUBLISHED  # NOT auto-archived — BR-NOT-002


def test_us_not_006_only_contracts_may_be_effective_dated(brazos, marcus):
    """BR-NOT-002 names CONTRACT templates and no other class. An
    effective-dated receipt would be a second publishing model for a class whose
    spec has one, and two published receipts would make "the current receipt"
    ambiguous on a screen that shows one number."""
    with tenant_ctx(brazos):
        receipt = variant(marcus, "receipt", name="Receipt")
        with pytest.raises(template_service.TemplateRefused, match="effective date"):
            template_service.save_draft(
                template=receipt,
                body=RECEIPT_BODY,
                actor=marcus,
                effective_from=date(2026, 9, 1),
            )
        contract = variant(marcus, "contract_payment_plan", name="Plan agreement")
        with pytest.raises(template_service.TemplateRefused, match="effective_from"):
            template_service.save_draft(template=contract, body=CONTRACT_BODY, actor=marcus)


# ── TC-4 · category assignment + account override ───────────────────────────
def test_us_not_006_tc4__resolution_is_override_then_category_then_default(brazos, marcus, dana):
    """US-NOT-006 TC-4: *"Service-agreement default variant by category;
    ACC-9001 override → commercial resolution order account-override → category
    default (BR-BIL-025)."* Crossed with BR-NOT-006's language axis and its
    *"missing variant → tenant-default fallback, never a blank"*.

    The `via` code on every result is what J22 step 3 demands: the fallback is
    RECORDED, *"never a blank, never an unrecorded inference"*.
    """
    with tenant_ctx(brazos):
        default_variant, _ = published(marcus, dana, "dunning", REMINDER_BODY)
        commercial, com_v1 = published(
            marcus,
            dana,
            "dunning",
            REMINDER_BODY + " (commercial)",
            category=tm.CATEGORY_COMMERCIAL,
        )

        exact = template_service.resolve(code="dunning", category=tm.CATEGORY_COMMERCIAL)
        assert (exact.template_id, exact.via, exact.fell_back) == (
            commercial.pk,
            template_service.VIA_EXACT,
            False,
        )

        # An industrial account has no variant of its own — BR-NOT-001's
        # mandatory default fallback answers, and SAYS which axis fell back.
        # `category_fallback` rather than `default_fallback`: the CATEGORY fell
        # back and the language did not, and a screen that says so tells a
        # utility exactly which variant to author next.
        industrial = template_service.resolve(code="dunning", category=tm.CATEGORY_INDUSTRIAL)
        assert industrial.template_id == default_variant.pk
        assert industrial.via == template_service.VIA_CATEGORY_FALLBACK
        assert industrial.fell_back is True

        # BOTH axes falling back is the last resort BR-NOT-001 makes mandatory
        # (*"fallback mandatory"*) and it names itself differently.
        both = template_service.resolve(
            code="dunning", category=tm.CATEGORY_INDUSTRIAL, language="de"
        )
        assert both.via == template_service.VIA_DEFAULT_FALLBACK

        # BR-NOT-006 language fallback: es-MX is requested, no es-MX variant
        # exists, the tenant-default variant answers and the pin records the
        # language ACTUALLY used (J22 step 3).
        spanish = template_service.resolve(
            code="dunning", category=tm.CATEGORY_COMMERCIAL, language="es-MX"
        )
        assert spanish.language == tm.VARIANT_DEFAULT
        assert spanish.via == template_service.VIA_LANGUAGE_FALLBACK

        # BR-BIL-025's override wins outright.
        override = template_service.resolve(
            code="dunning",
            category=tm.CATEGORY_RESIDENTIAL,
            override_template_id=commercial.pk,
        )
        assert (override.version, override.via) == (
            com_v1.version,
            template_service.VIA_ACCOUNT_OVERRIDE,
        )


def test_us_not_006_nothing_resolves_when_no_version_is_published(brazos, marcus):
    """Field map N-1's ratified posture, from the resolution side: *"dispatch
    holds safely on missing published template; content never invented."* A
    DRAFT is never resolved — publishing is what makes a body renderable
    (BR-BIL-027) — so a variant with only a draft resolves to nothing at all.

    ⚠ **ON `disconnect_notice`, since 2026-08-16 (DEF-163)**, and the choice is
    the assertion's whole validity: provisioning publishes `dunning` on every
    tenant, so a draft-only `dunning` variant now resolves — correctly — to the
    seeded default and this case would go green for the wrong reason. The
    disconnect class is catalogued and is deliberately NOT seeded (OQ-243), so
    it is the one printable class on which "nothing is published" is still
    true."""
    with tenant_ctx(brazos):
        template = variant(marcus, "disconnect_notice", name="Disconnect notice")
        template_service.save_draft(template=template, body=DISCONNECT_BODY, actor=marcus)
        with pytest.raises(template_service.TemplateRefused, match="no published"):
            template_service.resolve(code="disconnect_notice")


# ── TC-5 · the audit-lock ───────────────────────────────────────────────────
def test_us_not_006_tc5__a_pinned_version_can_never_be_deleted_and_a_draft_can(
    brazos, marcus, dana
):
    """US-NOT-006 TC-5: *"Delete attempted on receipt v1 (pinned by 3,412 sent
    receipts) → Blocked forever — audit-lock; archive allowed; an unpinned draft
    deletes fine."* T5-02 step 4 is the contrast case in the same test.

    PROVED RED by deleting the `status != draft` branch of `delete_version`: a
    PUBLISHED, pinned receipt version was then deleted outright and this failed
    at the `TemplateRefused` assertion — on Postgres the trigger caught it a
    layer down, which is the point of having both.
    """
    with tenant_ctx(brazos):
        template, v1 = published(marcus, dana, "receipt", RECEIPT_BODY)
        # One real sent receipt pinning it — the story's fixture is 3,412 and
        # the rule does not count.
        services.queue_document(
            source_type="payment",
            source_id="0197b0a0-0000-7000-8000-00000000d001",
            channels=(models.CHANNEL_PRINT,),
            template=services.TemplatePin(
                code="receipt", template_id=template.pk, version=v1.version
            ),
            actor=dana,
        )
        assert template_service.pin_count(v1) == 1

        with pytest.raises(template_service.TemplateRefused, match="can never be deleted"):
            template_service.delete_version(version_row=v1, actor=dana)

        # Archive IS allowed (US-BIL-021 TC-4 pair).
        template_service.archive(version_row=v1, actor=dana)
        v1.refresh_from_db()
        assert v1.status == tm.VERSION_ARCHIVED

        # T5-02 step 4 — an unpinned DRAFT deletes fine.
        draft = template_service.save_draft(
            template=template, body=RECEIPT_BODY + " v2", actor=marcus
        )
        template_service.delete_version(version_row=draft, actor=marcus)
        assert not tm.NotificationTemplateVersion.objects.filter(pk=draft.pk).exists()


def test_us_not_006_a_pinned_draft_is_refused_too(brazos, marcus, dana):
    """The audit-lock's other leg: a DRAFT that something pins is still locked.
    It should be impossible (resolution never pins a draft), which is exactly
    why the check is asserted rather than assumed — the day a caller stamps a
    draft's version onto a row by hand, the delete must still refuse."""
    with tenant_ctx(brazos):
        template = variant(marcus, "receipt", name="Receipt")
        draft = template_service.save_draft(template=template, body=RECEIPT_BODY, actor=marcus)
        services.queue_document(
            source_type="payment",
            source_id="0197b0a0-0000-7000-8000-00000000d002",
            channels=(models.CHANNEL_PRINT,),
            template=services.TemplatePin(
                code="receipt", template_id=template.pk, version=draft.version
            ),
            actor=dana,
        )
        with pytest.raises(template_service.TemplateRefused, match="audit-locked"):
            template_service.delete_version(version_row=draft, actor=marcus)


# ── TC-6 · append-only, at the service tier ─────────────────────────────────
def test_us_not_006_tc6__a_published_version_is_never_re_published_or_re_edited(
    brazos, marcus, dana
):
    """US-NOT-006 TC-6: *"Direct UPDATE of a published version's body → Rejected
    — versions are append-only rows; edits create drafts."*

    ⚠ The DIRECT UPDATE is refused by the Postgres trigger in migration 0006 and
    that half is asserted in the isolation suite (sqlite has no triggers). What
    this case proves is the SERVICE tier: there is no function here that edits a
    published body, and re-publishing one is refused by name.
    """
    with tenant_ctx(brazos):
        _template, v1 = published(marcus, dana, "dunning", REMINDER_BODY)
        with pytest.raises(template_service.TemplateRefused, match="already 'published'"):
            template_service.publish(version_row=v1, actor=dana)
        assert not hasattr(template_service, "update_body")


# ── the boundary: the three billing-owned classes ───────────────────────────
def test_us_not_006_the_bill_and_statement_designers_are_billings_not_this_registrys(
    brazos, marcus
):
    """S91–S93 are billing's designers (US-BIL-021) and B2 addendum r10 #4 gives
    them `bill_templates` + `bill_template_versions`. Registering one here would
    be notifications owning billing's tables — the first line of the B1 boundary
    rule. The refusal names the story and the addendum so the reader is not left
    hunting for the reason."""
    with tenant_ctx(brazos):
        for code in ("bill_residential", "bill_commercial", "statement"):
            with pytest.raises(template_service.TemplateRefused, match="r10 #4"):
                variant(marcus, code, name=code)


# ── what the store unblocked: a queue row that renders ──────────────────────
def test_us_not_006_a_queue_row_is_pinned_at_write_and_renders_at_dispatch(brazos, marcus, dana):
    """The unblock, asserted end to end.

    Before this story `rendering.render_for_dispatch` refused EVERY row with
    *"there is no store to load that version's body from"*. Now: the pin is
    resolved once at queue-write (BR-BIL-026 — a template published between
    queueing and dispatch cannot change the document) and the dispatcher renders
    from it.

    Money is 2dp with its currency and the figure comes from the CALLER's
    context — `247.30`, never `247.3`, and never a float (CLAUDE.md rule 2).
    """
    with tenant_ctx(brazos):
        template, v1 = published(marcus, dana, "receipt", RECEIPT_BODY)
        write = services.queue_document(
            source_type="payment",
            source_id="0197b0a0-0000-7000-8000-00000000d003",
            channels=(models.CHANNEL_PRINT,),
            template=services.TemplatePin(code="receipt"),
            actor=dana,
        )
        row = models.OutboundMessage.objects.get(pk=write.messages[0].id)

        assert (row.template_id, row.template_version) == (template.pk, v1.version)
        assert services.QUEUE_PIN_RESOLVED in {problem["code"] for problem in write.problems}

        artifact = rendering.render_for_dispatch(
            row,
            context={
                "first_name": "Sarah",
                "amount": Decimal("247.300000"),
                "date": date(2026, 8, 9),
                "confirmation": "RCT-2608-0455",
            },
        )

    # ⚠ AMENDED 2026-10-22 (merge, lane MERGE-EMAILS): `CR-190-BRC10` writes money
    # in a message with its currency SYMBOL in the utility's region (decision log
    # "Move-in messages built", item 3 — PO: *"the symbol comes from the
    # utility's currency and region settings"*), so `247.30 USD` is now `$247.30`.
    # Still two places, still the caller's figure, still never a float.
    assert "$247.30" in artifact.body
    assert "247.3 " not in artifact.body  # the float shape, refused everywhere
    assert artifact.template_version == v1.version


def test_us_not_006_an_unpinnable_row_holds_and_says_why(brazos, marcus, dana):
    """A document queued while its template had no published version keeps its
    place in the queue and HOLDS at dispatch, naming the reason (field map N-1).
    It is never rendered against today's published version — that is the
    re-render BR-BIL-026 forbids, and it is why the pin is stamped at
    queue-write rather than looked up at dispatch.

    ⚠ **ON `disconnect_notice`, since 2026-08-16 (DEF-163):** a `dunning` row
    now resolves its pin at queue-write from the seeded body, which is the fix
    working. An UNPINNABLE row needs a class with nothing published, and the
    disconnect class is exactly that until OQ-243 is ruled — which also makes
    this the case a real utility hits today."""
    with tenant_ctx(brazos):
        write = services.queue_document(
            source_type="notice",
            source_id="0197b0a0-0000-7000-8000-00000000d004",
            channels=(models.CHANNEL_PRINT,),
            template=services.TemplatePin(code="disconnect_notice"),
            actor=dana,
        )
        row = models.OutboundMessage.objects.get(pk=write.messages[0].id)
        assert row.template_version is None
        assert services.QUEUE_PIN_UNRESOLVED in {problem["code"] for problem in write.problems}

        with pytest.raises(rendering.RenderRefused, match="no pinned template version"):
            rendering.render_for_dispatch(row)

        # Publishing now does NOT retro-pin the row: the message must be queued
        # again. Stated in the refusal so an operator is not left re-queueing
        # forever.
        published(marcus, dana, "disconnect_notice", DISCONNECT_BODY)
        row.refresh_from_db()
        assert row.template_version is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-006@9a4f21c (the four US-NOT-006 sources — EP-NOT-02 §1/§3/§5 · 10-notifications/02-business-rules.md · 04-flows.md §2 · J22/T4-08/T4-09/T5-02)
# generated: 2026-08-15 by story-coder (W3 notifications CONTENT lane — the template store)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the S8 endpoints are not in this lane) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · every guard proved RED before green (hard-won law 7) — the
#         Admin-only publish gate, the audit-lock, the effective-dating rule and
#         the billing-boundary refusal; transcripts in the lane report
# exceptions: (1) TC-1 AND TC-3 ARE RUN ON SUBSTITUTED CLASSES and it is named in
#         each docstring: the story's email fixture is OQ-206-blocked (no token
#         catalog) and three of the four contract types are too, so the printable
#         dunning class and the payment-plan agreement (A19 §3, the one
#         catalogued contract) carry the cases. The LIFECYCLE under test is
#         class-independent.
#         (2) TC-6's DIRECT UPDATE IS PROVED ON POSTGRES ONLY (migration 0006's
#         trigger, asserted in the isolation suite). This file proves the service
#         tier and says so rather than implying full coverage.
#         (3) TC-7 (isolation) IS NOT HERE — it is
#         tests/test_us_not_006_template_isolation.py, behind `requires_postgres`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
