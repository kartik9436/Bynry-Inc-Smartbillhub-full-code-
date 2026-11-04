# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10531 — the bill-ready email said "it is attached to this
#           email" and nothing was attached
# Ruling:   PO 2026-10-22, decision log *"The bill email's link opens the bill
#           PDF directly, with no sign-in"* (*"b direct PDF link"*) and lane
#           BILL-LINK's judgments entry after it
# Rules:    CLAUDE.md hard rule 1 (RLS, in migration billing 0044) · hard rule
#           4 (nothing on the invoice is written — the pointer runs from here)
# Tests:    06-backend/tests/test_def_bil_10531_bill_link.py
# ───────────────────────────────────────────────────────
"""ONE secret link to ONE issued bill's kept PDF.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — the digest and the expiry are the security
of a page that needs no sign-in. AI-authored 2026-10-22 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

⚠ **ONLY A SHA-256 DIGEST OF THE TOKEN IS STORED** (`core.link_tokens`, the
agreement link's scheme). A dump of this table opens nothing.

⚠ **NOTHING ON `invoices` POINTS HERE.** An issued invoice is immutable (hard
rule 4); the row names the bill, never the other way round — the same direction
`stored_documents.source_id` runs for the kept PDF itself.

A link is opened as often as the customer likes until `expires_at` (judgment 3:
reading your bill twice is normal); there is no status column because there is
nothing to move.
"""

from django.db import models

from core.dbfields import uuid7_pk


class BillLink(models.Model):
    """`bill_links` — the bill email's direct PDF link (DEF-BIL-10531)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.PROTECT,
        db_column="invoice_id",
        related_name="bill_links",
    )
    token_hash = models.CharField(max_length=64)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bill_links"
        constraints = [
            models.UniqueConstraint(fields=("token_hash",), name="uq_bill_links_token"),
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("issued_at")),
                name="ck_bill_links_expires_after_issue",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "invoice"], name="ix_bill_links_invoice")]
