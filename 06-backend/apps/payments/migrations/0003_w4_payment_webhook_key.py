# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (record a payment)   Screens: —
# Rules:    CLAUDE.md hard rule 6 (idempotency on inbound payment webhooks) ·
#           B2 §2 payments — `UNIQUE (tenant_id, webhook_key)`, "dedupe double
#           webhook delivery"
# ───────────────────────────────────────────────────────
"""payments 0003 — the webhook dedupe key B2 signs, as a database constraint.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path and this table carries
money). HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of
2026-08-09; the payments lane's row in 12-governance/09-human-review-ledger.md
covers it.

WHY THIS IS A SEPARATE MIGRATION AND NOT PART OF 0001. It is not a design
choice: the payments lane declared the constraint on the model and its container
was restarted before `makemigrations` ran, so the model and the schema disagreed
and `makemigrations --check` failed. Generating it is completing that lane's
work, not extending it — the constraint's text, its fields and its name are the
lane's, unchanged, and B2 §2 is where they come from.

NULLS ARE DISTINCT, DELIBERATELY. Most payments carry no webhook key at all
(a cheque, a counter payment, an import row), and both PostgreSQL and SQLite
treat NULL as distinct in a unique index — so every keyless row coexists and no
partial predicate is needed to make the signed DDL work. A `WHERE webhook_key IS
NOT NULL` here would be a deviation from B2 dressed as a precaution.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0004_r17_custom_data"),
        ("payments", "0002_rls_w4_and_immutability"),
        ("tenancy", "0008_rls_custom_field"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.UniqueConstraint(
                fields=("tenant", "webhook_key"), name="uq_payments_webhook_key"
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@e9d5a48 (B2 §2 payments · 08-payments/02-business-rules.md)
# generated: 2026-08-11 by Eng-Lead — completing the payments lane's declared
#            constraint after its container restarted mid-`makemigrations`
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · makemigrations --check → "No changes detected"
# exceptions: the CONSTRAINT is the payments lane's and B2's; this file adds no
#         rule and changes no field. It exists because a model may not declare a
#         constraint the schema does not have — the two disagreeing is the state
#         `makemigrations --check` exists to catch, and it caught it.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
