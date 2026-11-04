# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 lane AGREEMENT — PO 2026-10-22, decision log
#           *"Click-to-accept agreements: the design confirmed with four
#           answers"*
# Rules:    CLAUDE.md hard rule 1 (tenant scoped, RLS FORCE — customers/0089) ·
#           hard rule 7 (every state change audited, `agreements.py`) · hard
#           rule 8 (NO address column: the service address is walked) · B14
#           rule 31 (no id on screen — the token is in the LINK, never shown)
# Tests:    06-backend/tests/test_cr190_agreements.py ·
#           06-backend/tests/test_cr190_agreements_pg.py
# Impacts:  apps/customers/agreements.py (the only writer) ·
#           apps/customers/migrations/0089_cr190_agreement_requests.py
# ───────────────────────────────────────────────────────
"""ONE REQUEST to accept ONE agreement, sent to ONE account, by ONE link.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — the token and its single use are the
security of a public page (`CLAUDE.md` sensitive paths: idempotency keys and
the RLS policy that ships with this table). AI-authored 2026-10-22 under the PO
ruling of 2026-08-09; row in `12-governance/09-human-review-ledger.md`.

WHAT IS KEPT, AND WHY EACH IS KEPT (the PO's *"Proof kept"* list, verbatim
order): the exact VERSION (`template_id` + `template_version` +
`effective_from`), the TICK (`accepted_at` is only ever written by an accept
that carried it), the DATE ENTERED (`accepted_date`), the SUBMISSION TIME
(`accepted_at`), the IP and the BROWSER (`accepted_ip`, `accepted_user_agent`),
and a PDF COPY stamped *"Accepted on … by …"* filed on the account
(`accepted_filing_id` → `account_documents`).

⚠ **ONLY A SHA-256 DIGEST OF THE TOKEN IS STORED.** The token is 256 random
bits, so a plain digest is the right hash (the reasoning `identity.NativeToken`
and lane STAFF-INVITE's `password_links` give) and a dump of this table opens
nothing.

THE FOUR STATES — and what moves a row between them
─────────────────────────────────────────────────────────────────────────────
  pending  ── accept (tick + today's date + typed name) ─▶ accepted
  pending  ── expires_at passes (read or sweep)        ─▶ expired
  pending  ── staff Resend (a new row is issued)       ─▶ voided
Nothing leaves `accepted`, `expired` or `voided`. **An expired agreement
changes nothing else** (answer 3, *"service continues"*): no account flag, no
hold, no message — staff see *Expired* and may resend.
"""

from django.db import models

from core.dbfields import uuid7_pk

STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_EXPIRED = "expired"
STATUS_VOIDED = "voided"
STATUSES = (STATUS_PENDING, STATUS_ACCEPTED, STATUS_EXPIRED, STATUS_VOIDED)

#: Where a request came from. `move_in` is the move-in's Complete; `resend` is
#: staff pressing *Resend agreement*; `staff` is a first request sent by hand.
ORIGIN_MOVE_IN = "move_in"
ORIGIN_RESEND = "resend"
ORIGIN_STAFF = "staff"
ORIGINS = (ORIGIN_MOVE_IN, ORIGIN_RESEND, ORIGIN_STAFF)


class AgreementRequest(models.Model):
    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="account_id",
        related_name="agreement_requests",
    )
    #: The Contracts-group class (`contract_service_agreement` first) and the
    #: EXACT published version shown — plain values, the `TemplatePin` shape.
    template_code = models.TextField()
    template_id = models.UUIDField()
    template_version = models.IntegerField()
    template_language = models.TextField()
    effective_from = models.DateField(null=True, blank=True)
    #: The class's name as the utility calls it, frozen at issue.
    agreement_name = models.TextField()
    #: The agreement text exactly as the customer is shown it — rendered ONCE,
    #: at issue, from the pinned version. Never re-rendered (BR-NOT-027's rule
    #: for a legal document).
    rendered_body = models.TextField()

    token_hash = models.CharField(max_length=64)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.TextField(default=STATUS_PENDING)
    origin = models.TextField()
    #: The move record a move-in request came from — the idempotency key of a
    #: replayed Complete (hard rule 6). NULL for staff and resend requests.
    origin_id = models.UUIDField(null=True, blank=True)
    issued_by = models.UUIDField(null=True, blank=True)
    issued_by_process = models.TextField(null=True, blank=True)

    #: The PDF as sent — a stored document (frozen bytes, content hash).
    sent_document_id = models.UUIDField(null=True, blank=True)
    email_message_id = models.UUIDField(null=True, blank=True)
    letter_message_id = models.UUIDField(null=True, blank=True)

    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_name = models.TextField(null=True, blank=True)
    accepted_date = models.DateField(null=True, blank=True)
    accepted_ip = models.TextField(null=True, blank=True)
    accepted_user_agent = models.TextField(null=True, blank=True)
    #: The `account_documents` filing card of the stamped copy.
    accepted_filing_id = models.UUIDField(null=True, blank=True)

    expired_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.UUIDField(null=True, blank=True)
    replaced_by_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agreement_requests"
        constraints = [
            models.UniqueConstraint(fields=["token_hash"], name="uq_agreement_requests_token"),
            models.UniqueConstraint(
                fields=["tenant", "origin_id", "template_code"],
                condition=models.Q(origin=ORIGIN_MOVE_IN),
                name="uq_agreement_requests_move_in",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=STATUSES), name="ck_agreement_requests_status"
            ),
            models.CheckConstraint(
                condition=models.Q(origin__in=ORIGINS), name="ck_agreement_requests_origin"
            ),
            models.CheckConstraint(
                condition=~models.Q(status=STATUS_ACCEPTED)
                | (
                    models.Q(accepted_at__isnull=False)
                    & models.Q(accepted_date__isnull=False)
                    & models.Q(accepted_name__isnull=False)
                    & ~models.Q(accepted_name="")
                ),
                name="ck_agreement_requests_accepted_proof",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "account", "-issued_at"], name="ix_agreement_req_account"),
        ]
