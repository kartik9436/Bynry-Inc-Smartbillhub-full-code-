# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 lane AGREEMENT — PO 2026-10-22, decision logs
#           *"Move-in messaging and the welcome email: four answers"* (answer 1,
#           *"email it as a PDF attachment (plus a letter if the customer wants
#           paper)"*; answer 2, *"make this as component so we can use this for
#           other aggrement also and the link should have the expiry date"*) and
#           *"Click-to-accept agreements: the design confirmed with four
#           answers"* (7 days, a setting · tick + date + typed name · expired →
#           staff resend, service continues · no in-portal acceptance)
# Rules:    CLAUDE.md hard rule 1 (every read and write under the tenant in
#           context) · hard rule 6 (a replayed move-in finds its own request) ·
#           hard rule 7 (every state change writes `audit_log`) · hard rule 8
#           (the service address is walked) · law 14 (savepoints) · decision log
#           2026-10-22 *"don't do any hardcoding"* (the link's life is a
#           setting; the email words are Settings templates) · coordinator
#           relay 2026-10-22 (agreement emails are NORMAL priority — no
#           immediate send; that is only for account-access emails)
# Tests:    06-backend/tests/test_cr190_agreements.py ·
#           06-backend/tests/test_cr190_agreements_pg.py
# Impacts:  apps/customers/agreements_api.py (staff) · apps/portal/
#           agreement_api.py (the public page) · apps/customers/
#           notifications_seam.py (the move-in's agreement)
# ───────────────────────────────────────────────────────
"""THE CLICK-TO-ACCEPT AGREEMENT — one reusable piece for every Contracts template.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides who may accept an
agreement and on what proof, through a page that needs no sign-in: the token's
generation, its hash, its single use and its expiry are the whole security of
that page. AI-authored 2026-10-22 under the PO ruling of 2026-08-09 (*"AI will
do it; we will review it later as human"*); row in
`12-governance/09-human-review-ledger.md`.

THE FLOW
─────────────────────────────────────────────────────────────────────────────
`issue()` — for one account and one Contracts-group template:
  1. pins the template's PUBLISHED version (the utility's language, today's
     date: BR-NOT-002's effective-dated resolution) and renders its text ONCE
     for this account — that rendering is what the customer is shown, sent and
     stamped, so the three can never differ;
  2. mints a 256-bit token, stores only its SHA-256, and dates its expiry from
     the utility's `agreement_link_valid_days` (Settings → Customer portal,
     seeded 7);
  3. queues the agreement email (`email_agreement_request`, its words from the
     utility's own Settings template) with the PDF attached, and the printed
     letter as well when the customer has not chosen paperless — or has no
     email address, so that nobody is sent nothing;
  4. writes `customers.agreement.requested` to `audit_log`.
`accept()` — the public page's submit: the tick, today's date in the utility's
  zone, a typed name. Stamps the row, files a PDF stamped *"Accepted on … by …"*
  on the account's documents, queues the confirmation email, audits.
`resend()` — staff: a NEW request and a new link; the old one is VOIDED.
Expiry — at read (every staff list and every public open checks it) and by
  `expire_due()` for a nightly sweep. **Nothing else changes** (PO answer 3).

THE PUBLIC REFUSAL IS ONE REFUSAL
─────────────────────────────────────────────────────────────────────────────
An unknown token, a used one, an expired one and a voided one all answer
`LinkUnavailable` and the page says the same sentence for each: *"This link has
expired. Call the office."* A different answer per case would tell a stranger
which tokens once existed. **Nothing about the account is read before the token
has matched** — the lookup is by hash, then compared in constant time.
"""

from __future__ import annotations

import hmac
import uuid
from datetime import date, datetime, timedelta
from importlib import import_module
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.customers import models
from apps.customers.agreement_models import (
    ORIGIN_MOVE_IN,
    ORIGIN_RESEND,
    ORIGIN_STAFF,
    STATUS_ACCEPTED,
    STATUS_EXPIRED,
    STATUS_PENDING,
    STATUS_VOIDED,
    AgreementRequest,
)
from core import audit as core_audit
from core import errors
from core import link_tokens
from core.tenancy import current_tenant_id

#: 256 random bits, URL-safe — `identity.NativeToken`'s size. The scheme is
#: `core.link_tokens` since DEF-BIL-10531, shared with the bill email's link.
TOKEN_BYTES = link_tokens.TOKEN_BYTES
#: The page's route, relative to the product's public origin. The one place the
#: backend names it; the screen's route is `PORTAL_ROUTES` `/agreements/:token`.
AGREEMENT_PATH = "/{tenant}/portal/agreements/{token}"
#: Who wrote a row when no person did.
PROCESS = "customers.agreements"
#: The outbound source kind (`notifications.models.SOURCE_TYPES`).
SOURCE_AGREEMENT = "agreement"
REQUEST_EMAIL = "email_agreement_request"
ACCEPTED_EMAIL = "email_agreement_accepted"
#: The longest name a person may type (a sentence is not a name).
MAX_NAME_LENGTH = 200

AUDIT_ENTITY = "agreement_request"
AUDIT_REQUESTED = "customers.agreement.requested"
AUDIT_ACCEPTED = "customers.agreement.accepted"
AUDIT_VOIDED = "customers.agreement.voided"
AUDIT_EXPIRED = "customers.agreement.expired"


class AgreementRefused(Exception):
    """A staff-side refusal a person can act on (no published version, …)."""

    def __init__(self, code: str, message_key: str, **params: Any) -> None:
        self.code = code
        self.message_key = message_key
        self.params = params
        super().__init__(code)


class LinkUnavailable(Exception):
    """THE public refusal — unknown, used, expired or voided, one answer."""


# ═══════════════════════════════════════════════════════════════════════════
# Small reads, by name (B1: another module is reached through its published
# function, never its tables)
# ═══════════════════════════════════════════════════════════════════════════


def _tenant_id() -> Any:
    tenant_id = current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None)


def _digest(token: str) -> str:
    return link_tokens.digest(token)


def _notifications(name: str) -> Any:
    return import_module(f"apps.notifications.{name}")


def contract_codes() -> tuple[str, ...]:
    """Every template class in the Contracts group — the classes this component
    serves (*"use this for other aggrement also"*). Read from the catalogue,
    never listed here."""
    catalogs = _notifications("catalogs")
    return tuple(
        code for code, klass in catalogs.CATALOGS.items() if klass.group == catalogs.GROUP_CONTRACT
    )


def link_valid_days() -> int:
    """The utility's setting (PO 2026-10-22, *"7 Days"* — a setting, not a constant)."""
    from apps.customers import portal_seam

    return portal_seam.agreement_link_valid_days(_tenant_id())


def _today() -> date:
    from apps.customers import seams

    return seams.tenant_today()


def _zone() -> Any:
    from apps.customers import seams

    return seams.tenant_timezone()


def _tenant_row() -> Any:
    from apps.tenancy import models as tenancy_models

    return tenancy_models.Tenant.objects.filter(pk=_tenant_id()).first()


def support_phone() -> str | None:
    """The utility's own number, Settings → Company (never typed into a screen)."""
    from apps.tenancy import selectors as tenancy_selectors

    try:
        return tenancy_selectors.company_profile().get("support_phone") or None
    except Exception:  # noqa: BLE001 — a dead end still renders without a number
        return None


def agreement_link(token: str) -> str | None:
    """`PUBLIC_APP_ORIGIN` + the page's path. None when no origin is configured —
    the email is then NOT queued and the caller says why (law 3: never a
    relative link nobody can open)."""
    from core import public_origin

    origin = public_origin.public_app_origin()
    tenant = _tenant_row()
    if origin is None or tenant is None:
        return None
    return origin + AGREEMENT_PATH.format(tenant=tenant.subdomain, token=token)


def _holder(account: Any) -> Any:
    link = (
        models.CustomerAccount.objects.filter(tenant_id=account.tenant_id, account_id=account.pk)
        .select_related("customer")
        .order_by("created_at", "id")
        .first()
    )
    return link.customer if link is not None else None


def holder_name(account: Any) -> str | None:
    """The customer's name: the linked customer's display name, else the
    account's primary contact (an account opened before `customer_accounts`
    links existed has only the contact). Walked on the browser walk of
    2026-10-22, where the demo account printed `——` for its own customer."""
    holder = _holder(account)
    name = (getattr(holder, "display_name", None) or "").strip()
    if name:
        return name
    contact = (
        models.Contact.objects.filter(
            tenant_id=account.tenant_id, account_id=account.pk, deleted_at__isnull=True
        )
        .order_by("-is_primary", "id")
        .values_list("full_name", flat=True)
        .first()
    )
    return (contact or "").strip() or None


def context_for(account: Any) -> dict[str, Any]:
    """The facts an agreement prints about its customer and account.

    The customer, the account number and the service address come from the
    ONE shared customer-details builder (`notifications.customer_context`,
    CR-190-BRC10 lane MOVEIN-MSG), so an agreement names its customer and
    their address exactly as the welcome and every other letter does (the
    address WALKED to the premises — hard rule 8). The name keeps this
    module's own fallback to the account's primary contact (`holder_name`)
    for the case the builder answers `None`."""
    context_module = _notifications("customer_context")
    shared = context_module.customer_context(account.pk)
    name = shared.get("customer_name") or holder_name(account)
    return {
        "first_name": shared.get("first_name") or context_module.greeting_name(name),
        "customer_name": name,
        "account_no": shared.get("account_no") or account.account_no,
        "service_address": shared.get("service_address"),
        "service_start_date": account.opened_at,
        "today": _today(),
        # The contract's signature block (`{customer_signature}`, `{date}`) is
        # left BLANK on purpose: on paper it is signed by hand, and online the
        # acceptance is the stamp the accepted copy carries. An empty string
        # renders as nothing; None would print the named-absence mark.
        "customer_signature": "",
        "date": "",
    }


def _listing_name(code: str) -> str:
    listing = _notifications("catalogs").LISTINGS.get(code)
    return listing.name if listing is not None else code


# ═══════════════════════════════════════════════════════════════════════════
# ISSUE
# ═══════════════════════════════════════════════════════════════════════════


def _pinned_text(account: Any, template_code: str) -> tuple[Any, Any, str]:
    """(pin, pinned body, rendered text) — or `AgreementRefused` when the utility
    has published no version of this agreement (BR-NOT-002 seeds none)."""
    template_service = _notifications("template_service")
    rendering = _notifications("rendering")
    tenancy_seam = _notifications("tenancy_seam")
    utility = getattr(tenancy_seam, "tenant_default_language", lambda: None)()
    # PO option B, 2026-10-29: the account's own language where the utility
    # published this agreement in it, the utility's default otherwise — the
    # one ladder every message uses (`notifications.message_language`).
    message_language = _notifications("message_language")
    language = message_language.language_for(
        template_code,
        stated=message_language.account_language(getattr(account, "pk", None)),
        utility=utility,
        on_date=_today(),
    )
    try:
        pin = template_service.resolve(code=template_code, language=language, on_date=_today())
        body = template_service.load_pinned(template_id=pin.template_id, version=pin.version)
        rendered = rendering.render(
            template_code=template_code,
            template_version=pin.version,
            body=body.body,
            context=context_for(account),
            language=pin.language,
        )
    except template_service.TemplateRefused:
        raise AgreementRefused(
            "agreement_not_published", "customers.agreement.notPublished", template_code=template_code
        ) from None
    except rendering.RenderRefused:
        raise AgreementRefused(
            "agreement_not_renderable", "customers.agreement.notRenderable", template_code=template_code
        ) from None
    return pin, body, rendered.body


def _facts(row: AgreementRequest) -> dict[str, Any]:
    from apps.tenancy import selectors as tenancy_selectors

    try:
        profile = tenancy_selectors.company_profile()
    except Exception:  # noqa: BLE001
        profile = {}
    return {
        "utility_name": profile.get("dba_name") or profile.get("legal_name"),
        "agreement_name": row.agreement_name,
        "version": row.template_version,
        "effective_from": row.effective_from.isoformat() if row.effective_from else None,
        "account_no": row.account.account_no,
        "customer_name": holder_name(row.account) or "",
    }


def _pdf(row: AgreementRequest, stamp: dict[str, Any] | None = None) -> bytes:
    from apps.customers import agreement_pdf

    # DEF-BIL-10546 — a tagged page, declaring the language the agreement was
    # published in, which is the language of nearly every word on it.
    return agreement_pdf.render(
        _facts(row), row.rendered_body, stamp=stamp, language=row.template_language
    )


def _file_name(row: AgreementRequest, suffix: str = "") -> str:
    return f"{row.agreement_name}{suffix}.pdf".replace("/", "-")


def _queue(**kwargs: Any) -> Any:
    services = _notifications("services")
    return services.queue_document(**kwargs)


def _queue_agreement(
    actor: Any,
    row: AgreementRequest,
    token: str,
    *,
    wants_paper: bool,
    job: str | None,
    channels: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """The email (PDF attached) and, if wanted, the letter. Returns outcome rows.

    `channels` is a clerk's per-move-in Step 4 choice (CR-190-BRC10, PO *"allow
    untick and channel change per move-in"*), already validated against
    `customer_events.default_allowed_channels`. None is the default: the email,
    plus the letter when the customer has not chosen paperless. A choice of the
    printed letter alone sends no email; a choice of email keeps the PO's
    *"plus a letter if the customer wants paper"*.
    """
    send_email = channels is None or "email" in channels
    letter_chosen = channels is not None and "pdf_print" in channels
    services = _notifications("services")
    attachments = _notifications("attachments")
    from apps.tenancy import document_models, document_store

    outcome: dict[str, Any] = {"email": None, "letter": None, "problems": []}
    link = agreement_link(token)
    language = getattr(_notifications("tenancy_seam"), "tenant_default_language", lambda: None)()
    if not send_email:
        pass
    elif link is None:
        outcome["problems"].append({"code": "public_origin_not_configured"})
    else:
        _notifications("agreement_templates").ensure_seeded(actor=actor)
        expires_on = row.expires_at.astimezone(_zone()).date()
        context = {
            **context_for(row.account),
            "agreement_name": row.agreement_name,
            "agreement_link": link,
            "link_expires_on": expires_on,
        }
        write = _queue(
            source_type=SOURCE_AGREEMENT,
            source_id=row.pk,
            channels=("email",),
            template=services.TemplatePin(code=REQUEST_EMAIL),
            account_id=row.account_id,
            render_context=context,
            actor=actor,
            job=job,
            language=language,
            on_date=_today(),
        )
        message = write.messages[0] if write.messages else None
        outcome["problems"].extend(list(write.problems))
        if message is not None:
            row.email_message_id = message.id
            outcome["email"] = {
                "id": str(message.id),
                "created": message.created,
                "unavailable_reason": message.unavailable_reason,
            }
            # The PDF AS SENT — frozen bytes, filed under the email row it rides.
            found = document_store.for_source(
                source_type=document_models.SOURCE_OUTBOUND_MESSAGE,
                source_id=message.id,
                content_type="application/pdf",
            )
            ref = getattr(found, "document", None)
            if ref is None:
                ref = document_store.store(
                    kind=_document_kind(row.template_code),
                    source_type=document_models.SOURCE_OUTBOUND_MESSAGE,
                    source_id=message.id,
                    content_type="application/pdf",
                    display_name=(
                        f"agreements/{row.issued_at:%Y}/{row.issued_at:%m}/"
                        f"{row.account.account_no}-{_file_name(row)}"
                    ),
                    payload=_pdf(row),
                    actor_user_id=_actor_id(actor),
                    process=None if _actor_id(actor) else PROCESS,
                )
            row.sent_document_id = ref.id
            attachments.attach_documents(
                message.id,
                [
                    {
                        "document_id": str(ref.id),
                        "filename": _file_name(row),
                        "content_type": "application/pdf",
                    }
                ],
            )
    email_reaches = bool(outcome["email"]) and not outcome["email"]["unavailable_reason"]
    if letter_chosen or wants_paper or not email_reaches:
        letter = _queue(
            source_type=SOURCE_AGREEMENT,
            source_id=row.pk,
            channels=("pdf_print",),
            template=services.TemplatePin(
                code=row.template_code,
                template_id=row.template_id,
                version=row.template_version,
                language=row.template_language,
            ),
            account_id=row.account_id,
            render_context=context_for(row.account),
            actor=actor,
            job=job,
            on_date=_today(),
        )
        message = letter.messages[0] if letter.messages else None
        outcome["problems"].extend(list(letter.problems))
        if message is not None:
            row.letter_message_id = message.id
            outcome["letter"] = {"id": str(message.id), "created": message.created}
    row.save(update_fields=["email_message_id", "letter_message_id", "sent_document_id"])
    return outcome


def _document_kind(template_code: str) -> str:
    """The stored kind of an agreement PDF — the contract's own ruled kind
    (`frozen_documents`' map), else an account document."""
    from apps.tenancy import document_models

    mapping = getattr(_notifications("frozen_documents"), "DOCUMENT_KIND_BY_TEMPLATE_CLASS", {})
    kind = mapping.get(template_code)
    return kind if kind in document_models.DOCUMENT_KINDS else document_models.KIND_ACCOUNT_DOCUMENT


def issue(
    actor: Any,
    account_id: Any,
    template_code: str,
    *,
    origin: str = ORIGIN_STAFF,
    origin_id: Any = None,
    job: str | None = None,
    channels: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Send one agreement to accept. Returns `{request, delivery}`.

    A move-in replayed with the same move record finds its own request and
    writes nothing (hard rule 6, `uq_agreement_requests_move_in`)."""
    tenant_id = _tenant_id()
    if template_code not in contract_codes():
        raise AgreementRefused("not_an_agreement", "customers.agreement.notAnAgreement")
    account = models.Account.objects.filter(tenant_id=tenant_id, pk=account_id).first()
    if account is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if origin == ORIGIN_MOVE_IN and origin_id is not None:
        existing = AgreementRequest.objects.filter(
            tenant_id=tenant_id, origin=ORIGIN_MOVE_IN, origin_id=origin_id,
            template_code=template_code,
        ).first()
        if existing is not None:
            return {"request": summary(existing), "delivery": None, "created": False}

    pin, body, text = _pinned_text(account, template_code)
    token = link_tokens.mint()
    now = timezone.now()
    with transaction.atomic():
        try:
            with transaction.atomic():  # law 14: a lost race must not poison the move-in
                row = AgreementRequest.objects.create(
                    tenant_id=tenant_id,
                    account=account,
                    template_code=template_code,
                    template_id=pin.template_id,
                    template_version=pin.version,
                    template_language=pin.language,
                    effective_from=body.effective_from,
                    agreement_name=_listing_name(template_code),
                    rendered_body=text,
                    token_hash=_digest(token),
                    issued_at=now,
                    expires_at=now + timedelta(days=link_valid_days()),
                    status=STATUS_PENDING,
                    origin=origin,
                    origin_id=origin_id,
                    issued_by=_actor_id(actor),
                    issued_by_process=None if _actor_id(actor) else (job or PROCESS),
                )
        except IntegrityError:
            existing = AgreementRequest.objects.filter(
                tenant_id=tenant_id, origin=origin, origin_id=origin_id,
                template_code=template_code,
            ).first()
            if existing is None:  # pragma: no cover — a different constraint
                raise
            return {"request": summary(existing), "delivery": None, "created": False}
        delivery = _queue_agreement(
            actor,
            row,
            token,
            wants_paper=not bool(account.paperless),
            job=job,
            channels=tuple(channels) if channels else None,
        )
        core_audit.write_row(
            action=AUDIT_REQUESTED,
            entity_type=AUDIT_ENTITY,
            entity_id=row.pk,
            actor_user_id=_actor_id(actor),
            after={
                "account_id": str(account.pk),
                "template_code": template_code,
                "template_version": pin.version,
                "origin": origin,
                "expires_at": row.expires_at.isoformat(),
                "email_message_id": str(row.email_message_id) if row.email_message_id else None,
                "letter_message_id": str(row.letter_message_id) if row.letter_message_id else None,
            },
        )
    return {"request": summary(row), "delivery": delivery, "created": True}


def resend(actor: Any, account_id: Any, request_id: Any) -> dict[str, Any]:
    """*Resend agreement* — a new link; the old one is voided in the same act."""
    tenant_id = _tenant_id()
    old = AgreementRequest.objects.filter(
        tenant_id=tenant_id, account_id=account_id, pk=request_id
    ).select_related("account").first()
    if old is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    _expire_if_due(old)
    if old.status == STATUS_ACCEPTED:
        raise AgreementRefused("already_accepted", "customers.agreement.alreadyAccepted")
    with transaction.atomic():
        result = issue(actor, account_id, old.template_code, origin=ORIGIN_RESEND)
        if old.status == STATUS_PENDING:
            old.status = STATUS_VOIDED
            old.voided_at = timezone.now()
            old.voided_by = _actor_id(actor)
        old.replaced_by_id = result["request"]["id"]
        old.save(update_fields=["status", "voided_at", "voided_by", "replaced_by_id"])
        core_audit.write_row(
            action=AUDIT_VOIDED,
            entity_type=AUDIT_ENTITY,
            entity_id=old.pk,
            actor_user_id=_actor_id(actor),
            after={"status": old.status, "replaced_by": str(old.replaced_by_id)},
        )
    return result


# ═══════════════════════════════════════════════════════════════════════════
# EXPIRY — at read, and a sweep
# ═══════════════════════════════════════════════════════════════════════════


def _expire_if_due(row: AgreementRequest, now: datetime | None = None) -> bool:
    now = now or timezone.now()
    if row.status != STATUS_PENDING or row.expires_at > now:
        return False
    with transaction.atomic():
        moved = AgreementRequest.objects.filter(pk=row.pk, status=STATUS_PENDING).update(
            status=STATUS_EXPIRED, expired_at=now
        )
        if moved:
            core_audit.write_row(
                action=AUDIT_EXPIRED,
                entity_type=AUDIT_ENTITY,
                entity_id=row.pk,
                after={"status": STATUS_EXPIRED, "expires_at": row.expires_at.isoformat()},
            )
    row.status, row.expired_at = STATUS_EXPIRED, now
    return bool(moved)


def expire_due(now: datetime | None = None) -> int:
    """Every pending request past its expiry, for the tenant in context."""
    now = now or timezone.now()
    count = 0
    for row in AgreementRequest.objects.filter(
        tenant_id=_tenant_id(), status=STATUS_PENDING, expires_at__lte=now
    ):
        count += int(_expire_if_due(row, now))
    return count


# ═══════════════════════════════════════════════════════════════════════════
# STAFF READS
# ═══════════════════════════════════════════════════════════════════════════


def summary(row: AgreementRequest) -> dict[str, Any]:
    """What the account screen shows. No token, no hash, no internal id beyond
    the row id the screen keys on (B14 rule 31: never displayed)."""
    return {
        "id": str(row.pk),
        "template_code": row.template_code,
        "agreement_name": row.agreement_name,
        "version": row.template_version,
        "status": row.status,
        "issued_at": row.issued_at,
        "expires_at": row.expires_at,
        "accepted_at": row.accepted_at,
        "accepted_date": row.accepted_date,
        "accepted_name": row.accepted_name,
        "accepted_document_id": str(row.accepted_filing_id) if row.accepted_filing_id else None,
        "sent_by_email": row.email_message_id is not None,
        "sent_by_letter": row.letter_message_id is not None,
    }


def requests_for_account(account_id: Any) -> list[dict[str, Any]]:
    """Every request on this account, newest first — expiry applied at read.
    One account holds a handful (one per agreement per resend), so this is a
    bounded read rather than a paged one."""
    tenant_id = _tenant_id()
    if not models.Account.objects.filter(tenant_id=tenant_id, pk=account_id).exists():
        raise errors.deny_as_not_found("BR-TEN-003")
    rows = list(
        AgreementRequest.objects.filter(tenant_id=tenant_id, account_id=account_id).order_by(
            "-issued_at"
        )
    )
    now = timezone.now()
    for row in rows:
        _expire_if_due(row, now)
    return [summary(row) for row in rows]


# ═══════════════════════════════════════════════════════════════════════════
# THE PUBLIC PAGE
# ═══════════════════════════════════════════════════════════════════════════


def _by_token(token: Any) -> AgreementRequest:
    """The live request this token opens — or `LinkUnavailable`, one answer for
    every reason. Looked up by DIGEST, then compared in constant time."""
    text = str(token or "")
    if not text or len(text) > 128:
        raise LinkUnavailable()
    digest = _digest(text)
    row = (
        AgreementRequest.objects.filter(tenant_id=_tenant_id(), token_hash=digest)
        .select_related("account")
        .first()
    )
    if row is None or not hmac.compare_digest(row.token_hash, digest):
        raise LinkUnavailable()
    _expire_if_due(row)
    if row.status != STATUS_PENDING:
        raise LinkUnavailable()
    return row


def public_view(token: Any) -> dict[str, Any]:
    """`GET` — what the page shows once the token has matched."""
    row = _by_token(token)
    facts = _facts(row)
    return {
        "utility_name": facts["utility_name"],
        "customer_name": facts["customer_name"],
        "account_no": facts["account_no"],
        "agreement_name": row.agreement_name,
        "version": row.template_version,
        "effective_from": row.effective_from,
        "text": row.rendered_body,
        "expires_at": row.expires_at,
        "today": _today(),
    }


def public_document(token: Any) -> tuple[bytes, str]:
    """`GET …/document` — the PDF exactly as sent."""
    from apps.tenancy import document_store

    row = _by_token(token)
    payload = document_store.fetch(row.sent_document_id) if row.sent_document_id else _pdf(row)
    return payload, _file_name(row)


def public_unavailable() -> dict[str, Any]:
    """The dead end's facts: the utility's own number, from Settings."""
    return {"state": "unavailable", "support_phone": support_phone()}


def accept(
    token: Any,
    *,
    agreed: Any,
    accepted_date: Any,
    typed_name: Any,
    ip: str | None,
    user_agent: str | None,
) -> dict[str, Any]:
    """`POST …/accept` — tick + today's date + a typed name (PO answer 2, *"B"*).

    The token is matched FIRST; only then are the fields checked, so a bad field
    can never be used to probe for a live token. Field refusals name the field.
    """
    row = _by_token(token)
    field_errors: list[dict[str, Any]] = []
    if agreed is not True:
        field_errors.append({"field": "agreed", "code": errors.VAL_REQUIRED,
                             "message_key": "customers.agreement.tickRequired"})
    name = " ".join(str(typed_name or "").split())
    if not name:
        field_errors.append({"field": "name", "code": errors.VAL_REQUIRED,
                             "message_key": "customers.agreement.nameRequired"})
    elif len(name) > MAX_NAME_LENGTH:
        field_errors.append({"field": "name", "code": errors.VAL_RANGE,
                             "message_key": "customers.agreement.nameTooLong"})
    today = _today()
    try:
        entered = date.fromisoformat(str(accepted_date or "")[:10])
    except ValueError:
        entered = None
    if entered != today:
        field_errors.append({"field": "date", "code": errors.VAL_RANGE,
                             "message_key": "customers.agreement.dateMustBeToday"})
    if field_errors:
        raise errors.ValidationError(
            errors.VAL_RANGE if len(field_errors) == 1 and field_errors[0]["code"] == errors.VAL_RANGE
            else errors.VAL_REQUIRED,
            message_key="customers.agreement.acceptRefused",
            field_errors=field_errors,
            br_ref="CR-190-BRC10",
        )
    now = timezone.now()
    with transaction.atomic():
        moved = AgreementRequest.objects.filter(pk=row.pk, status=STATUS_PENDING).update(
            status=STATUS_ACCEPTED,
            accepted_at=now,
            accepted_date=entered,
            accepted_name=name,
            accepted_ip=(ip or "")[:64] or None,
            accepted_user_agent=(user_agent or "")[:512] or None,
        )
        if not moved:  # a second tab won the race — the link is now used
            raise LinkUnavailable()
        row.refresh_from_db()
        filing_id = _file_stamped_copy(row)
        row.accepted_filing_id = filing_id
        row.save(update_fields=["accepted_filing_id"])
        core_audit.write_row(
            action=AUDIT_ACCEPTED,
            entity_type=AUDIT_ENTITY,
            entity_id=row.pk,
            after={
                "account_id": str(row.account_id),
                "template_code": row.template_code,
                "template_version": row.template_version,
                "accepted_date": entered.isoformat(),
                "accepted_at": now.isoformat(),
                "agreed": True,
                "filing_id": str(filing_id),
                # BR-AUD-006 — the name, IP and browser are on the row for those
                # entitled to read it; the trail records only that they exist.
                "name_given": True,
                "ip_recorded": bool(ip),
                "user_agent_recorded": bool(user_agent),
            },
        )
        _queue_confirmation(row)
    return {"state": "accepted", "agreement_name": row.agreement_name,
            "accepted_date": row.accepted_date, "accepted_name": row.accepted_name}


def _file_stamped_copy(row: AgreementRequest) -> Any:
    """The stamped PDF, filed on the account as a `contract` document
    (`BR-CUS-036`: *"signed agreements attach automatically"* — audit-locked)."""
    from apps.customers.account_document_models import TYPE_CONTRACT, AccountDocument
    from apps.tenancy import document_models, document_store

    local = row.accepted_at.astimezone(_zone())
    payload = _pdf(
        row,
        stamp={
            "accepted_date": row.accepted_date.isoformat(),
            "accepted_name": row.accepted_name,
            "accepted_at": local.strftime("%Y-%m-%d %H:%M %Z"),
        },
    )
    card_id = uuid.uuid5(row.pk, "accepted-copy")
    name = _file_name(row, f" - accepted {row.accepted_date.isoformat()}")
    ref = document_store.store(
        kind=document_models.KIND_ACCOUNT_DOCUMENT,
        source_type=document_models.SOURCE_ACCOUNT_DOCUMENT,
        source_id=card_id,
        content_type="application/pdf",
        display_name=(
            f"account-documents/{local:%Y}/{local:%m}/{row.account.account_no}-{name}"
        ),
        payload=payload,
        process=PROCESS,
    )
    with transaction.atomic():  # law 14
        card = AccountDocument.objects.create(
            id=card_id,
            tenant_id=row.tenant_id,
            account_id=row.account_id,
            document_id=ref.id,
            doc_type=TYPE_CONTRACT,
            uploaded_by_process=PROCESS,
            uploaded_at=row.accepted_at,
        )
    core_audit.write_row(
        action="customers.account_document.filed",
        entity_type="account_document",
        entity_id=card.id,
        after={
            "account_id": str(row.account_id),
            "doc_type": TYPE_CONTRACT,
            "document_id": str(ref.id),
            "byte_length": len(payload),
            "content_type": "application/pdf",
            "process": PROCESS,
        },
    )
    return card.id


def _queue_confirmation(row: AgreementRequest) -> None:
    """The confirmation email — normal priority, the regular dispatch cycle."""
    services = _notifications("services")
    _notifications("agreement_templates").ensure_seeded()
    language = getattr(_notifications("tenancy_seam"), "tenant_default_language", lambda: None)()
    _queue(
        source_type=SOURCE_AGREEMENT,
        source_id=uuid.uuid5(row.pk, "accepted-confirmation"),
        channels=("email",),
        template=services.TemplatePin(code=ACCEPTED_EMAIL),
        account_id=row.account_id,
        render_context={
            **context_for(row.account),
            "agreement_name": row.agreement_name,
            "accepted_on": row.accepted_date,
            "accepted_name": row.accepted_name,
        },
        job=PROCESS,
        language=language,
        on_date=_today(),
    )


__all__ = [
    "AgreementRefused",
    "LinkUnavailable",
    "accept",
    "contract_codes",
    "expire_due",
    "issue",
    "link_valid_days",
    "public_document",
    "public_unavailable",
    "public_view",
    "requests_for_account",
    "resend",
]
