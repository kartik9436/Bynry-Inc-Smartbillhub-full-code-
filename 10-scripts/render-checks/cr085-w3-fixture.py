# ── Trace ──────────────────────────────────────────────
# Change:  CR-085 wave 3 — "I need a copy of something" (CPB-14 · CPB-15 ·
#          CPB-19 · CPB-20)
# Rules:   BR-CWP-045 (documents are SERVED, never re-rendered) · BR-NOT-027
#          (frozen at dispatch, against the MESSAGE) · CLAUDE.md hard rule 1
#          (every read and write names its tenant — RLS is OFF where this runs)
# Tests:   fixture prep for 10-scripts/render-checks/cr085-w3-documents.mjs
# ───────────────────────────────────────────────────────
"""A RECEIPT, A LETTER AND A MISSING COPY ON THE DEMO TENANT.

WHY THIS FILE EXISTS
--------------------
Wave 3's whole subject is **taking a copy of something that is not a bill**, and
on `seed_portal_demo`'s estate every document a portal login can see is a bill.
Counted on a freshly seeded Pine Hill, 2026-09-08:

    outbound messages   invoice/pdf_print 80 · invoice/portal 79 ·
                        payment/pdf_print 68 · payment/email 68 ·
                        payment/sms 67 · move/pdf_print 1 · move/email 1
    stored documents    invoice → bill: 160.   Receipts: NONE. Letters: NONE.

So the receipt rows exist in the queue and **not one of them has a kept copy**,
because `dispatch_outbound` holds every single one:

    ! render_held_missing_template: queue row … is pinned to template … v1 and
      that version could not be loaded

…and the two demo logins (`ana@`, `maria@`) hold accounts with no payments at
all. A walkthrough run against that estate would open `CWP-031`, see three
bills, and report green over the two cases this wave is about — the exact shape
this repository calls *a check that cannot fail*.

WHAT IT PLANTS, AND WHAT IT DELIBERATELY DOES NOT
-------------------------------------------------
Against **`ana@example.test`'s** account:

  1. **A payment with a receipt whose copy was kept.** `CPB-20`'s row control
     and `CPB-14`'s row control both point at it.
  2. **A payment with a receipt whose copy was NOT kept.** The honest refusal —
     *We kept no copy of this.* — has to be walkable too, or the fix reads as
     *the refusal is gone* rather than *the refusal is now true*.
  3. **A letter with no number of its own** (`source_type='notice'`), whose copy
     WAS kept. This is the row that can only be had in the year's archive, and
     the reason `CPB-15` is not merely a convenience.

⚠ **THE ARTEFACT IS STORED DIRECTLY RATHER THAN RENDERED, AND THAT IS STATED
RATHER THAN HIDDEN.** `frozen_documents.freeze_for_dispatch` is the real path
and it needs a published template version this estate does not have — its own
dispatch cycle says so, 68 times. What is under test in wave 3 is the SERVING
path, so this plants exactly what a successful freeze plants (a
`stored_documents` row against the OUTBOUND MESSAGE, which is `_stored`'s second
lookup) and claims nothing about the render. A fixture that pretended to
exercise `freeze_for_dispatch` would be proving the half that already works.

⚠ **IT IS IDEMPOTENT.** A replay finds its own rows by their numbers and leaves
them alone, so a lane can re-run it between browser passes.

HOW TO RUN IT
-------------
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr085-w3-fixture.py)
"""

import datetime as dt
from decimal import Decimal

from apps.customers import models as customers_models
from apps.notifications import models as notifications_models
from apps.payments import models as payments_models
from apps.tenancy import document_store
from apps.tenancy.models import Tenant
from core.tenancy import tenant_context

TENANT = "pine-hill"
#: The householder both demo walkthroughs sign in as.
LOGIN = "ana@example.test"

KEPT_RECEIPT = "PMT-2608-W3KEPT"
LOST_RECEIPT = "PMT-2608-W3LOST"

RECEIPT_PDF = b"%PDF-1.4\n% Pine Hill Water & Power - receipt for $38.44\n%%EOF\n"
LETTER_PDF = b"%PDF-1.4\n% Pine Hill Water & Power - about your supply\n%%EOF\n"

tenant = Tenant.objects.filter(subdomain=TENANT).first()
if tenant is None:
    raise SystemExit(f"no tenant {TENANT!r} — run manage.py seed_portal_demo first")

with tenant_context(tenant.id):
    from apps.portal import models as portal_models

    credential = portal_models.PortalCredential.objects.filter(email=LOGIN).first()
    if credential is None:
        raise SystemExit(
            f"no portal login {LOGIN!r} — run def-cwp-3965-fixture.py first; this "
            "fixture plants documents FOR a login and does not create one"
        )
    # ⚠ **THE ACCOUNT SET IS DERIVED THE WAY THE PRODUCT DERIVES IT**
    # (`BR-CWP-009`: exactly two sources, re-derived on every read, never
    # trusted from a stored column). A fixture that queried accounts its own
    # way could plant a document onto an account this login cannot actually
    # see, and the walkthrough would then report a missing row as a bug.
    from apps.portal import session as portal_session

    entries = portal_session.account_set(
        tenant.id, customer_id=credential.customer_id, credential_id=credential.pk
    )
    account_ids = [entry.account_id for entry in entries]
    account = customers_models.Account.objects.filter(pk=account_ids[0]).first() if account_ids else None
    if account is None:
        raise SystemExit("the login holds no account")
    print(f"planting on {account.account_no} ({LOGIN})")

    def a_receipt(number, *, keep, when, amount):
        payment = payments_models.Payment.objects.filter(payment_no=number).first()
        if payment is None:
            payment = payments_models.Payment.objects.create(
                tenant_id=tenant.id,
                account=account,
                amount=Decimal(amount),
                currency="USD",
                payment_no=number,
                posted_at=when,
            )
        message = notifications_models.OutboundMessage.objects.filter(
            source_type="payment", source_id=payment.pk
        ).first()
        if message is None:
            message = notifications_models.OutboundMessage.objects.create(
                tenant_id=tenant.id,
                account=account,
                source_type="payment",
                source_id=payment.pk,
                channel="pdf_print",
                status="queued",
                template_code="receipt",
                created_at=when,
                # `ck_outbound_msgs_address_or_reason` — a row carries the
                # address it will be delivered to, or states why it has none.
                # It can never carry neither (`BR-BIL-036`, made structural).
                recipient_address="1408 Elm St · A, Pine Hill",
            )
        if keep and not document_store.for_source(
            source_type="outbound_message", source_id=message.pk
        ).found:
            document_store.store(
                kind="payment_receipt",
                source_type="outbound_message",
                source_id=message.pk,
                channel="pdf_print",
                display_name=f"receipt/2026/08/{number}.pdf",
                content_type="application/pdf",
                payload=RECEIPT_PDF,
                # `store` takes an actor OR a process, and *nobody knows* is not one of
                # the answers a legal document may give.
                process="cr085-w3",
            )
        return payment, message

    august = dt.datetime(2026, 8, 12, 10, 0, tzinfo=dt.timezone.utc)
    a_receipt(KEPT_RECEIPT, keep=True, when=august, amount="38.4400")
    a_receipt(LOST_RECEIPT, keep=False, when=august, amount="21.0000")

    # ── A LETTER WITH NO NUMBER OF ITS OWN ────────────────────────────────
    # `source_type='notice'` resolves to no invoice number and no payment
    # number, so `documents()` publishes `reference: null` and the row cannot
    # be addressed one at a time. It is the case `CPB-15`'s archive exists for.
    letter = notifications_models.OutboundMessage.objects.filter(
        source_type="notice", account=account, template_code="dunning_letter"
    ).first()
    if letter is None:
        import uuid

        letter = notifications_models.OutboundMessage.objects.create(
            tenant_id=tenant.id,
            account=account,
            source_type="notice",
            source_id=uuid.uuid4(),
            channel="pdf_print",
            status="queued",
            template_code="dunning_letter",
            created_at=dt.datetime(2026, 8, 20, 9, 0, tzinfo=dt.timezone.utc),
            recipient_address="1408 Elm St · A, Pine Hill",
        )
    if not document_store.for_source(
        source_type="outbound_message", source_id=letter.pk
    ).found:
        document_store.store(
            kind="dunning_letter",
            source_type="outbound_message",
            source_id=letter.pk,
            channel="pdf_print",
            display_name="letter/2026/08/a-reminder.pdf",
            content_type="application/pdf",
            payload=LETTER_PDF,
            # `store` takes an actor OR a process, and *nobody knows* is not one of
            # the answers a legal document may give.
            process="cr085-w3",
        )

    # ── A LIVE PAYMENT PLAN WHOSE AGREEMENT WE KEPT ──────────────────────
    # ⚠ **WITHOUT THIS THE WAVE'S FOURTH CONTROL IS NEVER WALKED.** `CPB-14`
    # released `CWP-043`'s *↓ Agreement* from `portal.yourPlan.agreementHeld`,
    # and the walkthrough's step 8b SKIPPED on every run because `ana@` holds
    # no plan at all (`plans: []`, measured 2026-09-08). A skip that can never
    # stop being a skip is the shape this repository calls *a check that cannot
    # fail* — the same fault the rest of this fixture exists to prevent for the
    # receipt and the letter, left standing on the one control nobody had seen.
    #
    # ⚠ **THE AGREEMENT IS FILED AGAINST THE OUTBOUND MESSAGE, NOT THE PLAN**,
    # and that is not a shortcut. `notifications` spells a plan `"plan"` while
    # `tenancy` spells it `"payment_plan"` and its CHECK constraint permits only
    # the second, so `for_source(source_type="plan", ...)` can never match a
    # stored row — `notifications_seam.plan_agreement_bytes` says so in its own
    # docstring (`DEF-CWP-4688`, filed not fixed). Only the DISPATCH lookup can
    # hit, so planting it any other way would prove nothing about the path the
    # product actually uses.
    #
    # The figures are `US-CWP-052` §7's invariant, which the screen asserts:
    # `40.00 + 5 x 22.03 + 22.05` = **`172.20`**.
    from apps.payments import collections_models

    AGREEMENT_PDF = b"%PDF-1.4\n% Pine Hill Water & Power - payment plan agreement\n%%EOF\n"

    plan = collections_models.PaymentPlan.objects.filter(
        account=account, status__in=collections_models.LIVE_PLAN_STATUSES
    ).first()
    if plan is None:
        plan = collections_models.PaymentPlan.objects.create(
            tenant_id=tenant.id,
            account=account,
            total_amount=Decimal("172.2000"),
            down_payment=Decimal("40.0000"),
            currency="USD",
            installment_count=6,
            cadence="monthly",
            status=collections_models.PLAN_ACTIVE,
            proposed_on=dt.date(2026, 7, 20),
            agreement_sent_on=dt.date(2026, 7, 22),
            signed_on=dt.date(2026, 7, 23),
        )
        amounts = [Decimal("22.0300")] * 5 + [Decimal("22.0500")]
        for seq, amount in enumerate(amounts, start=1):
            collections_models.PaymentPlanInstallment.objects.create(
                tenant_id=tenant.id,
                plan=plan,
                seq=seq,
                due_date=dt.date(2026, 8 + seq - 1, 14)
                if 8 + seq - 1 <= 12
                else dt.date(2027, 8 + seq - 13, 14),
                amount=amount,
                currency="USD",
            )

    agreement_msg = notifications_models.OutboundMessage.objects.filter(
        source_type="plan", source_id=plan.pk
    ).first()
    if agreement_msg is None:
        agreement_msg = notifications_models.OutboundMessage.objects.create(
            tenant_id=tenant.id,
            account=account,
            source_type="plan",
            source_id=plan.pk,
            channel="pdf_print",
            status="queued",
            template_code="payment_plan_agreement",
            created_at=dt.datetime(2026, 7, 22, 9, 0, tzinfo=dt.timezone.utc),
            recipient_address="1408 Elm St \u00b7 A, Pine Hill",
        )
    if not document_store.for_source(
        source_type="outbound_message", source_id=agreement_msg.pk
    ).found:
        document_store.store(
            kind="payment_plan_agreement",
            source_type="outbound_message",
            source_id=agreement_msg.pk,
            channel="pdf_print",
            display_name="plan/2026/07/payment-plan-agreement.pdf",
            content_type="application/pdf",
            payload=AGREEMENT_PDF,
            # `store` takes an actor OR a process, and *nobody knows* is not one of
            # the answers a legal document may give.
            process="cr085-w3",
        )

    from apps.portal import selectors

    listed = selectors.documents(account)["documents"] or []
    groups = {}
    for row in listed:
        groups.setdefault(row["group"], []).append(row)
    print(f"  {len(listed)} document(s) on CWP-031 for this account:")
    for group, rows in sorted(groups.items()):
        kept = sum(1 for one in rows if one["stored_document"]["available"])
        numbered = sum(1 for one in rows if one["reference"])
        print(f"    {group:8} {len(rows):3}  kept: {kept}  with a number: {numbered}")
    bundle = selectors.documents_bundle(account, today=dt.date.today())
    print(
        f"  the year's archive: {bundle['verdict']}, "
        f"{bundle['kept']} of {bundle['listed']} listed"
    )
    from apps.portal.seams import payments_seam

    current = payments_seam.current_plans(account.pk, as_of=dt.date.today())
    for one in current["plans"]:
        print(
            f"  CWP-043 plan: status={one['status']} live={one['live']} "
            f"total={one['total']} agreement_available={one['agreement_available']}"
        )
    print(f"\nsign in as {LOGIN} / Pine-Hill-2026! and open /{TENANT}/portal/documents")
