# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-060 (EP-CWP-11) — *What do you need: six cards, named by
#           what the customer wants.* Screen: CWP-046
# Rules:    BR-CWP-075 (the customer makes four of the eleven transitions and
#           no more) · BR-CWP-076 (every row carries channel `customer_portal`)
#           · BR-CWP-080 (moving out and stopping service are different, and
#           the cards say which) · US-CWP-060 TC-8 (*"read from configuration,
#           never a hardcoded list"*) · CLAUDE.md hard rule 1 (RLS — this table
#           already carries its policy from portal/0002; no new table)
# Tests:    06-backend/tests/test_us_cwp_060_request_hub.py TC-8
# Impacts:  apps/portal/models.py (REQUEST_ERRAND_FIELDS · DEFAULTS ·
#           BRANDING_FIELDS) · apps/portal/settings_service.py ·
#           apps/portal/selectors.py `request_errands`
# ───────────────────────────────────────────────────────
"""portal 0009 — ONE column: `portal_settings.request_errands`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

**WHY A SECOND JSON COLUMN AND NOT `quick_service_categories` READ TWICE.**
`US-CWP-060` TC-8 asks that a tenant who RENAMES a card sees the new label, so
the list has to be configuration rather than a literal in the code. The column
beside it already holds a configurable card list — `CWP-010`'s — and reusing it
would offer a signed-in customer *"copy of a bill"* where this story asks for
*"move out"*. Two audiences, two lists, one row. `models.REQUEST_ERRAND_FIELDS`
carries the full reasoning.

**NO NEW TABLE, SO NO NEW RLS POLICY.** `portal_settings` has carried its
`FORCE` policy since `portal/0002`, and a column inherits the row's protection.
That is stated rather than assumed, because *"a comment claiming a guarantee is
not the guarantee"* (hard-won law 1) cuts both ways: the guarantee here is real
and is one migration back, and a reviewer should be able to check that in one
step rather than wonder.

**DEFAULT `list`, NEVER A SEEDED SIX.** A migration that wrote the six cards
into every existing row would make a READ that answers defaults impossible to
tell from a tenant who genuinely chose those six — the distinction
`quick_service_categories` already draws in `selectors.quick_service_categories`
(*"a read never writes"*). The empty list means *this utility has not configured
its own*, and the selector answers `DEFAULT_REQUEST_ERRANDS` for it.
"""

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0008_rls_portal_credentials"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalsettings",
            name="request_errands",
            field=models.JSONField(blank=True, default=list),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-060@b50adaa0 (EP-CWP-11 + 03-field-map.md snapshot)
# generated: 2026-09-04 by the CR-068 ending lane (US-CWP-060)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 migration ordering — ledger row 09-human-review-ledger.md)
# gates: G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row) · migrate on the SQLite suite
# exceptions: none — one nullable-by-default JSON column on an existing, RLS-protected table
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
