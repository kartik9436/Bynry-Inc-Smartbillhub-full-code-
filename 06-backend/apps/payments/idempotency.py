# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (TC-6 "double-click Record ✓ → one row only")
#           Screens: S22 · S35
# Rules:    BR-PAY-003 (inbound payment webhooks are idempotent — webhook_key
#           UNIQUE; double delivery = one row) · BR-PAY-028 (idempotency:
#           webhook_key UNIQUE (rails) + import batch file+tags; **key
#           mechanics Eng-Lead 🔒**) · CLAUDE.md rule 6 (idempotency on
#           inbound payment webhooks) · B2 DB-12 ("(tenant, webhook_key)
#           payments")
# Tests:    06-backend/tests/test_us_pay_001_record_payment.py
# Impacts:  apps/payments/services.record_payment (composes the key) ·
#           apps/payments/models.Payment.webhook_key +
#           uq_payments_webhook_key (the database half)
# ───────────────────────────────────────────────────────
"""The inbound-payment idempotency key. HUMAN-OWNED (CLAUDE.md 🔒 "idempotency keys").

HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
12-governance/09-human-review-ledger.md; it may never reach lifecycle RATIFIED
without a recorded human sign-off.

WHAT IS SIGNED, AND WHAT IS MECHANICS
-------------------------------------
The RULE is signed and is not reinterpreted here.

  * **BR-PAY-003** (CONFIRMED, B2 §payments): *"Inbound payment webhooks are
    idempotent (webhook_key unique)"*.
  * **B2 §2**: `payments.webhook_key text` with `UNIQUE (tenant_id,
    webhook_key)` — *"dedupe double webhook delivery"*.
  * **DB-12**, the consolidated idempotency register: *"(tenant, webhook_key)
    payments"*.
  * **CLAUDE.md hard rule 6**: bill runs and inbound payment webhooks.

The MECHANICS — the exact string those facts are folded into — are delegated by
name: BR-PAY-028 ends *"key mechanics Eng-Lead 🔒"*, and EP-PAY-01's US-PAY-001
field map says the same of the staff submit token (*"client token + unique key
🔒 Eng-Lead"*). That delegation is the only thing decided in this file.
`core/idempotency.py` states the boundary from the other side: *"`payments.
webhook_key` is NOT here. Its shape is DB-12's second row and belongs to the
payments lane."*

    key = "<source>|<reference>"

Worked, so the figure is concrete rather than a description. Marcus double-clicks
Record on check #8842 and the S22 form submits its client token
`3f2b91c4-0d55-4a7e-9a0b-1f5d2c7e8a10` twice:

    entry|3f2b91c4-0d55-4a7e-9a0b-1f5d2c7e8a10

The first submit writes payment PMT-2608-000412 for $292.87. The second submits
the same string, finds the same row, and returns it with `created=False` — one
payment, $292.87 once, one `payment.recorded` audit row, one journal entry. A
gateway redelivering the same event composes

    webhook|stripe:evt_1P9xQ2

and dedupes the same way, against the same unique index.

ONE COLUMN, NOT TWO — the judgment call, stated rather than buried
-----------------------------------------------------------------
B2 defines exactly ONE idempotency column on `payments`, and its comment says
*"inbound webhook idempotency"*. The staff single-entry form needs one too
(US-PAY-001 TC-6) and B2 gives it no column of its own. Two readings:

  (a) the staff token shares `webhook_key`, namespaced so the two sources
      cannot collide — ONE unique index, one place a duplicate is caught;
  (b) a second column, `submit_token`, with a second unique index.

**(a) is what this file implements**, under the BR-PAY-028 delegation, for a
reason that is structural rather than tidy: with two columns there are two
answers to *"has this payment already been recorded?"*, and a path that checks
the wrong one lets money in twice. The `<source>` segment keeps the namespaces
apart — an `entry|…` key and a `webhook|…` key can never be the same string —
so the widened use costs nothing a second column would have bought.

It IS a widening of B2's stated intent, so it is raised rather than assumed:
**OQ-127**, for the PO to confirm or split. The behaviour meanwhile fails
CLOSED (one row, not two), which is the safe direction to be wrong in.

THREE PROPERTIES THE SHAPE IS CHOSEN FOR
----------------------------------------
  * **The tenant is NOT in the string.** It is the other column of the unique
    constraint (`UNIQUE (tenant_id, webhook_key)`), so folding it in as well
    would put the same fact in two places and let one drift from the other. The
    tenant is never client input either way (BR-TEN-003). Same reasoning as
    `core.idempotency.bill_run_key`.
  * **`|` is the separator**, because it cannot occur in a uuid or in the
    snake_case source names this repo uses — the key stays splittable by eye in
    the psql session where somebody is debugging a refused duplicate. Same
    character and same reasoning as `core.idempotency` and
    `apps.ledger.posting`; not imported from either, because each of those
    modules scopes itself to its own keys and says so, and one shared constant
    would make this file depend on that scope.
  * **A missing part is REFUSED, never padded.** Two different payments whose
    keys were both `"entry|"` would collide, which is the exact double-recording
    the key exists to prevent — and the collision would present as "this payment
    was already recorded", i.e. as money silently not taken.

WHAT IS NOT HERE
----------------
The IMPORT key. BR-PAY-028's other half is *"import batch file+tags"* (the
OQ-044 model, BR-PAY-023) and it keys a `payment_import_batches` row, not a
payment. US-PAY-003 owns it and that table is not built; inventing its shape
here would be this module deciding a question the bulk-import lane has to ask
of a real lockbox file.
"""

from __future__ import annotations

from typing import Any

#: The one separator, named once. See the module docstring for why it is `|`.
KEY_SEPARATOR = "|"

#: The staff single-entry form's client token (US-PAY-001 TC-6, BR-PAY-028).
SOURCE_ENTRY = "entry"
#: A payment rail's own event id (BR-PAY-003). Nothing dispatches through this
#: path in R2 — W7 owns the rails — but the key shape is schema-ready, which is
#: exactly what EP-PAY-01 §Scope says of `webhook_key`.
SOURCE_WEBHOOK = "webhook"
#: A committed row of a staged lockbox/CSV import (BR-PAY-023). The BATCH's own
#: idempotency is file+tags and lives with US-PAY-003; this names the per-ROW
#: key so a re-committed batch cannot double a payment even if the batch guard
#: is bypassed.
SOURCE_IMPORT = "import"

#: `CR-174-BRC10` — a PAYMENT AGENT's own payment id (US Payments (Prime) is
#: the first): `agent|pay_uspayments:900000000123`. A fourth namespace rather
#: than `webhook|…` for the reason `models.PAYMENT_ORIGIN_AGENT` gives — the
#: source IS the payment's origin (`services.record_payment` writes one from
#: the other), and that origin must stay out of the New World feed (PO D3,
#: 2026-10-07). HUMAN-REVIEW-PENDING with the rest of this file.
SOURCE_AGENT = "agent"

SOURCES: tuple[str, ...] = (SOURCE_ENTRY, SOURCE_WEBHOOK, SOURCE_IMPORT, SOURCE_AGENT)


class PaymentKeyError(ValueError):
    """A key was asked for with a part missing, or from an unknown source.

    Refuses rather than composing a short key. A key of `"entry|"` would be the
    same string for every numberless submit a tenant ever makes, so the SECOND
    payment of the day would be refused as a duplicate of the first — money not
    taken, reported as money already taken. Failing loudly at composition time
    is the only version of this that a human can act on.
    """


def inbound_payment_key(*, source: str, reference: Any) -> str:
    """The idempotency key for ONE inbound payment: where it came from + its id.

    Pure and total — same two inputs ⇒ same string, always, with no clock, no
    ordering assumption and no database read. That is what lets a caller check
    for the duplicate BEFORE doing any work and still be backstopped by
    `uq_payments_webhook_key` if it loses a race.

    `source` is one of `SOURCES`; an unknown one is refused rather than passed
    through, because a typo'd namespace is a key that will never match the row
    it was meant to dedupe against and the duplicate lands as a second payment.
    """
    if source not in SOURCES:
        raise PaymentKeyError(
            f"{source!r} is not one of the inbound payment sources {list(SOURCES)} "
            "(BR-PAY-003 webhooks · BR-PAY-023 imports · US-PAY-001 staff entry). A "
            "namespace nobody defined produces a key that matches nothing, so the "
            "duplicate it was meant to catch is recorded as a second payment."
        )
    text = "" if reference is None else str(reference).strip()
    if not text:
        raise PaymentKeyError(
            f"an inbound payment key needs a reference as well as the source (got "
            f"{source!r}, {reference!r}). BR-PAY-003 wants 'double delivery = one row'; "
            "a key composed with the reference missing would be identical for every "
            "payment from that source, so the second one of the day would be refused "
            "as a duplicate of the first."
        )
    return KEY_SEPARATOR.join((source, text))


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@f4d2b18 (the four payments sources — B2 §2 + Addenda r12/r14 (DB-12) · EP-PAY-01-record-payments.md · 08-payments/02-business-rules.md (BR-PAY-003/028) · 08-payments/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W4 payments closed-loop lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)  [D and E CLOSED 2026-08-11: POST /accounts/{id}/payments REQUIRES the client token as `idempotency_key` and the S22/S35 modal mints one per opened form]
# gates: ruff✔ black✔ · PROVED RED: with the pre-insert lookup removed and the unique constraint dropped, the double-submit case records TWO payments and doubles the money — quoted in the lane report before either guard was trusted green (hard-won law 7)
# exceptions: B2 names ONE idempotency column on `payments` and comments it
#         "inbound webhook idempotency"; this file WIDENS it to carry the staff
#         submit token as well, namespaced (`entry|…` vs `webhook|…`), under the
#         BR-PAY-028 delegation ("key mechanics Eng-Lead 🔒"). One column means
#         one answer to "has this already been recorded?"; two columns mean a
#         path can check the wrong one. RAISED as OQ-127 rather than assumed,
#         and the behaviour fails CLOSED meanwhile · the IMPORT BATCH key
#         (file+tags, BR-PAY-023/OQ-044) is NOT here: it keys a
#         `payment_import_batches` row, US-PAY-003 owns it, and that table is
#         not built
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
