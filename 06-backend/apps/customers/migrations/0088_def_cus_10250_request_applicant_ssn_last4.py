# ── Trace ──────────────────────────────────────────────
# Change:   DEF-CUS-10250 — the portal application carries Move-in's fields
#           into the service request (PO 2026-10-18, decision log "CUSTOMER
#           DATA AND UI CONSISTENT ACROSS THE CREATE SCREENS").
# Rules:    hard rule 1 (`service_requests` keeps its per-TABLE RLS policy; the
#           new column inherits it) · BR-CUS-092(c) (the SSN last four is
#           stored ENCRYPTED, never in the clear)
# Tests:    06-backend/tests/test_def_cus_10250_portal_apply_carry_forward.py
# ───────────────────────────────────────────────────────
"""customers 0088 — one nullable encrypted column on `service_requests`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-18 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md (lane CF-2).

⚠ **ONE COLUMN, NOT SIX.** Lane CF-2 first wrote this as `0087` with six
columns; lane CF-1's `0087_cf1_request_customer_form` landed the same day with
the co-applicant cards, *contact by*, the two preference ticks and the mailing
address under their own names, so five of the six were the same facts twice.
They were dropped for CF-1's, and the portal writes CF-1's columns. What CF-1
does not have is the portal applicant's SSN last four (the portal asks four
digits and never the whole number), so that is all this adds.

NULLABLE, NO BACKFILL: a request written before today was never asked it, and
NULL is the truth about it. No money figure reads it.

ROLLBACK: reverse drops the column. Portal requests sent since lose the SSN
last four the applicant typed; nothing else moves.
"""

import core.crypto
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0087_cf1_request_customer_form"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="applicant_ssn_last4",
            field=core.crypto.EncryptedTextField(
                blank=True, crypto_context="service_requests.applicant_ssn_last4", null=True
            ),
        ),
    ]
