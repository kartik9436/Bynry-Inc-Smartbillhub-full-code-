# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-037 (EP-INT-10) — their words for our things: a foreign name
#           is a ROW, never a column. Screens: S143 (the *Their words* tab)
# Rules:    BR-INT-032 (a foreign name is a row keyed by target; UNIQUE on the
#           EXTERNAL side — one of their words means exactly one of ours, two of
#           theirs may share one of ours; a fourth partner costs rows and no
#           migration; the ledger's two vendor columns are READ, never widened,
#           until OQ-INT-1480) · BR-INT-031 (an unmapped inbound value records
#           as `other` and shows red; nothing is refused on the way in) ·
#           B14 rule 31 (the visible value is their word and our word — never a
#           database id) · CLAUDE.md hard rule 7 (a mapping decides where money
#           lands on a report, so setting one writes audit_log) · hard rule 1
#           (every read and write below runs under the request's tenant
#           context; the explicit tenant filter is the second guard)
# Questions: both RULED 2026-09-04 and neither is a stub any more.
#           OQ-INT-1480 (retiring `qbo_ref` / `xero_ref`) — HELD: *"hold this
#           requirement for now; we will use our GL code only"*. The columns
#           are neither retired nor widened, ever, and `retire_vendor_columns()`
#           refuses by ruling rather than by absence · OQ-INT-1487 (what Nacha
#           `R02` maps to) — option (b): it records as `other` with the raw code
#           kept, the four signed reasons are NOT widened to five, and mapping
#           it onto one of them (option (c)) was declined, so the writer still
#           refuses `R02` — as a RULED refusal a clerk can read.
# Tests:    06-backend/tests/test_us_int_037_mappings.py (SQLite: TC-1, TC-4,
#           TC-5, TC-6, the in-request duplicate, R02) ·
#           06-backend/tests/test_us_int_037_pg.py (TC-2 the UNIQUE, TC-3 a
#           fourth partner with no migration)
# Impacts:  apps/integrations/services.py (re-exports the writers — B1's one
#           write path) · selectors.py (re-exports the read) · mappings_api.py
#           (`GET` / `PUT /integrations/{key}/mappings`) · manifests/*.py
#           (`vocabularies`) · 07-frontend/src/features/integrations/ValueMappingPage.tsx
# ───────────────────────────────────────────────────────
"""integrations mappings — their word → our thing, as rows a clerk edits on S143.

THE SHAPE, AND WHY IT IS A ROW (US-INT-037)
--------------------------------------------
The chart of accounts carries `qbo_ref` and `xero_ref` — two columns, two
vendors; *"the third one is what makes the shape visible: the first two looked
like fields, and they were always rows."* So a partner's word for one of our
things is a row in `integration_target_reference`, keyed by which outside
system (`target_key`), which kind of thing (`entity_type`) and THEIR word
(`external_value`). A fourth partner costs rows; so does the tenth.

**The UNIQUE is on the EXTERNAL side** — `(tenant, target, type, their word)`.
`ACHCHECK` means exactly one of ours, and `ACHSAVINGS` may mean the same one.
Never the other way round, because a mapping that multiplies rows is a report
nobody can reconcile. The database holds that rule below this code
(`uq_integration_target_ref_external`); `set_rows()` refuses the same request
carrying one of their words twice before a row is touched.

WHAT A ROW POINTS AT — `entity_id` OR `local_value`, AND WHY BOTH ARE FILLED
----------------------------------------------------------------------------
Our side is either a LOOKUP ROW (a payment method, a ledger account, a route,
a meter type, a service — `entity_id` names it) or an ENUM VALUE (a reversal
reason — `entity_id` is NULL and `local_value` carries the value). For a
lookup-backed kind `local_value` ALSO carries the row's CODE, so a runner can
read the mapping without a join and a screen can show the word without an id
(B14 rule 31): the id is the pointer, the code is the word, and the lookup is
re-read on every view so a retired tender shows as unmapped rather than as a
stale name.

THE TWO BOUNDARIES, RULED 2026-09-04 — AND BOTH STAY SHUT
----------------------------------------------------------
They were open questions until the Product Owner answered them, and the answer
to each was to LEAVE IT WHERE IT IS. The code therefore looks almost the same
and MEANS something different: a boundary the next lane must not try to unblock.

* `OQ-INT-1480` — do these rows REPLACE `ledger_accounts.qbo_ref` / `.xero_ref`?
  **HELD**: *"hold this requirement for now; we will use our GL code only"*. So
  the rows sit BESIDE the two columns permanently — `external_for()` reads the
  column for the two vendors it was built for and the row for everybody else —
  no third column is ever added, and the chart gains no fund / department /
  object segments. A partner needing `001.100.51200` is not served, and that is
  the ruling rather than a gap. `retire_vendor_columns()` refuses BY RULING.
* `OQ-INT-1487` — what does Nacha `R02` (*account closed*) map to, given the
  four signed reversal reasons? **Option (b)**: *"widening a signed list for one
  code needs a re-sign; the raw code is kept"*. `R02` takes the ordinary
  unmapped path — it records as `other`, shows red, and the raw code stays on
  the payload. Option (c), mapping it onto one of the four, was DECLINED, so
  `set_rows()` still refuses `R02` — but now with a sentence a clerk can act on
  instead of a question nobody had answered. The row exists, red, and the screen
  says it always records as Other.

INBOUND: DEGRADE, NEVER REFUSE (BR-INT-031)
-------------------------------------------
`record_unknown()` is what the inbound door (wave N) calls when a value
arrives that nobody mapped: it adds the red row and stamps *last seen* on the
connection's non-secret `config`, and the payment itself lands as *Other*.
Refusing a real payment over a vocabulary is worse than misfiling it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.integrations import models
from apps.integrations.registry import MAPPING_ENTITY_TYPES, REGISTRY, Manifest, Registry
from core import audit as core_audit
from core import errors
from core.permissions import SYSTEM_ADMIN, require_role

#: Nacha's *account closed* — `OQ-INT-1487`, ruled 2026-09-04 to option (b).
#: The one word the writer will not record a meaning for, and now for a stated
#: reason: it records as `other` with the raw code kept, and the four signed
#: reasons are not widened to five.
R02_ACCOUNT_CLOSED = "R02"

#: The two vendors whose account references live in COLUMNS on the chart
#: (`ledger/models.py` `qbo_ref`, `xero_ref`). Read, never widened; a third
#: name here is the change `OQ-INT-1480` forbids — HELD 2026-09-04, so this
#: pair is closed for good rather than pending an answer.
LEDGER_COLUMN_TARGETS = {"qbo": "qbo_ref", "xero": "xero_ref"}

#: English fallbacks for the four signed reversal reasons — the catalogue
#: line `integrations.mappings.reason.<code>` wins on screen when present.
REVERSAL_REASON_LABELS = {
    "nsf": "Not enough money",
    "bank_chargeback": "Bank chargeback",
    "data_entry_error": "Keyed wrongly",
    "customer_dispute": "Customer dispute",
}

# ── New World / Logos: CONFIG, NOT CODE (`CR-132-BRC07`) ────────────────────
#
# PO 2026-09-22, ruling the receipt endpoint: *"you can se the same components
# that you use, dont write completely new code"*. **A vocabulary is data.** The
# two things New World needs that no other partner does — our tender in THEIR
# payment-type numbers, and our purpose as THEIR transaction and bill types —
# live here as tables a clerk's mapping row overrides, never as branches in the
# projection. `apps/integrations/newworld.py` reads them and decides nothing.

#: The connection this partner's mapping rows hang off, and the manifest key.
NEWWORLD_TARGET_KEY = "erp_newworld"

#: Their `ReceiptPaymentType` vocabulary, verbatim from the import
#: specification (v2023.1.11). **Five values, and none of them is ACH** — which
#: is what made the tender mapping a question for the PO rather than a lookup.
NEWWORLD_PAYMENT_CASH = "0"
NEWWORLD_PAYMENT_CHECK = "1"
NEWWORLD_PAYMENT_CHARGE = "2"
NEWWORLD_PAYMENT_OTHER = "3"
NEWWORLD_PAYMENT_WIRE = "4"
NEWWORLD_PAYMENT_TYPES = {
    NEWWORLD_PAYMENT_CASH: "Cash",
    NEWWORLD_PAYMENT_CHECK: "Check",
    NEWWORLD_PAYMENT_CHARGE: "Charge",
    NEWWORLD_PAYMENT_OTHER: "Other",
    NEWWORLD_PAYMENT_WIRE: "Wire Transfer",
}

#: **OUR TENDER → THEIR `(ReceiptPaymentType, ReceiptPaymentOtherType)`.**
#: PO ruling 2026-09-22, verbatim: *"we send ACH, Moenry Order and Lockbox - as
#: mapping from our side and wil ask them to map it at their end"*.
#:
#: ⚠⚠ **THE THREE `Other` ROWS CARRY A DEPENDENCY ON NEW WORLD, AND IT IS
#: WRITTEN HERE BECAUSE THIS IS THE FILE SOMEBODY EDITS WHEN IT BITES.** Their
#: specification says `ReceiptPaymentOtherType` *"must match New World's Other
#: Payment Type validation set"* — a list held on THEIR side. **Until their
#: team adds `ACH`, `Money order` and `Lockbox` to it, every receipt carrying
#: one of those three words is rejected at their end.** The PO knows and is
#: asking them. The words are here, in configuration, so a different spelling
#: coming back from their team is a line in this table and a mapping row on the
#: connection — never a rebuild.
#:
#: ⚠ **A CARD IS `Charge` AND CARRIES NO CARD NUMBER.** That is the whole of
#: what this product will ever say about a card to an outside system — see
#: `newworld.py`'s docstring and `G130`.
#:
#: ⚠ **`lockbox` IS IN OUR TENDER LIST AND IT IS NOT A TENDER** — it is a
#: CHANNEL, and a lockbox payment is a cheque that arrived in an envelope. It
#: is mapped for completeness on the PO's instruction, and it **cannot occur in
#: this feed at all**: the New World feed is `origin = webhook` only and a
#: lockbox payment is `origin = import`. The same is true of `cash`, `check`
#: and `money_order`, which are counter and post work. **In practice this feed
#: is ACH and Card**, which is why the ACH row was the one that mattered.
NEWWORLD_TENDER_DEFAULTS = {
    "cash": (NEWWORLD_PAYMENT_CASH, ""),
    "check": (NEWWORLD_PAYMENT_CHECK, ""),
    "cheque": (NEWWORLD_PAYMENT_CHECK, ""),
    "card": (NEWWORLD_PAYMENT_CHARGE, ""),
    "credit_card": (NEWWORLD_PAYMENT_CHARGE, ""),
    "debit_card": (NEWWORLD_PAYMENT_CHARGE, ""),
    "wire": (NEWWORLD_PAYMENT_WIRE, ""),
    "wire_transfer": (NEWWORLD_PAYMENT_WIRE, ""),
    # The three the PO ruled, and the three their validation set does not hold
    # yet. `bank_transfer` is this product's own name for the ACH tender —
    # `seams/payments.py` records it mapping to a partner's `ACHCHECK` — so it
    # takes the ACH row and NOT the wire row: a wire is a different banking
    # instrument with different fees and a different clearing window.
    "ach": (NEWWORLD_PAYMENT_OTHER, "ACH"),
    "bank_transfer": (NEWWORLD_PAYMENT_OTHER, "ACH"),
    "money_order": (NEWWORLD_PAYMENT_OTHER, "Money order"),
    "lockbox": (NEWWORLD_PAYMENT_OTHER, "Lockbox"),
}

#: What a tender we have never seen becomes. A tender is the tenant's OWN
#: lookup row, so a utility may add one this table has never heard of.
#:
#: ⚠ **IT IS `Other` WITH OUR OWN WORD FOR IT, AND IT IS COUNTED.** Sending our
#: own word is a fact about the payment; picking one of their four named types
#: for a tender we cannot identify would be a plausible value, which is the one
#: thing this day's rulings forbid. The receipt goes — *SEND IT · NEVER
#: SILENTLY · NEVER PLUG IT* — and `newworld.Emission.unmapped_tenders` names
#: it so a clerk can add the mapping row.
NEWWORLD_TENDER_FALLBACK = NEWWORLD_PAYMENT_OTHER

#: Our payment purpose → their `ReceiptTransactionType` (64, "the payment
#: code") and `ReceiptTransactionARBillType` (32, our utility bill type).
#:
#: ⚠ **THESE ARE OUR WORDS UNTIL THEIR TEAM SENDS THEIRS, AND THAT IS
#: DELIBERATE RATHER THAN A GAP.** `seams/payments.py` settled the posture for
#: the whole partner surface: publishing OUR code with OUR label is not ETL,
#: and inventing a plausible word in somebody else's vocabulary is. A clerk's
#: mapping row translates each of these in one place on the day we are told
#: what their codes are; nothing in the projection has to change.
NEWWORLD_TRANSACTION_TYPES = {
    "bill": "UTILITY",
    "plan_down": "UTILITY",
    "deposit": "DEPOSIT",
    "prepay": "PREPAY",
}
NEWWORLD_BILL_TYPES = {
    "bill": "UTILITY",
    "plan_down": "UTILITY",
    "deposit": "DEPOSIT",
    "prepay": "PREPAY",
}
#: What an unknown purpose becomes. `UTILITY` and not `""`: their transaction
#: type is how a receipt line is classified at all, and a utility receipt with
#: no type is a receipt their importer cannot file. A purpose we do not
#: recognise is still a utility receipt.
NEWWORLD_TYPE_FALLBACK = "UTILITY"


def newworld_transaction_type(purpose: str) -> str:
    """Their `ReceiptTransactionType` for one of our payment purposes."""
    return NEWWORLD_TRANSACTION_TYPES.get(str(purpose or ""), NEWWORLD_TYPE_FALLBACK)


def newworld_bill_type(purpose: str) -> str:
    """Their `ReceiptTransactionARBillType` for one of our payment purposes."""
    return NEWWORLD_BILL_TYPES.get(str(purpose or ""), NEWWORLD_TYPE_FALLBACK)


def newworld_payment_type(tender_code: str, mapped: str | None) -> tuple[str, str]:
    """One tender → `(ReceiptPaymentType, ReceiptPaymentOtherType)`.

    **Configuration first, shipped default second, our own word last** — and
    none of the three is ever a guess at one of their four named types.

      1 `mapped` is whatever a clerk put on the connection for this tender
        (`external_for(..., "tender", code)`). **If it is one of their five
        type numbers it IS the type; anything else is their OTHER-TYPE WORD and
        the type is `3`.** One row, one field, no composite string — and it is
        what lets New World come back with a different spelling of `ACH` and
        have it fixed by a clerk rather than by a release.
      2 the shipped table above, for the seven tenders the PO ruled.
      3 `3` Other carrying OUR OWN word for the tender, counted as unmapped.

    A payment with NO tender at all — an adjustment, a transfer leg — is `3`
    Other with no other-type: *Other* is the true statement about a row that
    took no money, and it is not the unmapped case.
    """
    code = str(tender_code or "").strip().lower()
    if mapped:
        text = str(mapped).strip()
        if text in NEWWORLD_PAYMENT_TYPES:
            return text, ""
        return NEWWORLD_PAYMENT_OTHER, text
    if not code:
        return NEWWORLD_PAYMENT_OTHER, ""
    known = NEWWORLD_TENDER_DEFAULTS.get(code)
    if known is not None:
        return known
    return NEWWORLD_TENDER_FALLBACK, code


STATE_MAPPED = "mapped"
STATE_UNMAPPED = "unmapped"


# ── our values: the lookups a mapping may point at ──────────────────────────


def our_choices(tenant_id: Any, entity_type: str) -> list[dict[str, Any]]:
    """Every value of OURS a partner's word may mean, for one kind of thing.

    `value` is the CODE (what the screen sends back and what a runner reads),
    `label` is the word a clerk sees, `id` is the lookup row for the kinds
    that have one. No `id` is ever a visible value (B14 rule 31) — it rides
    here so `resolve()` can store the pointer.
    """
    if entity_type == "tender":
        from apps.tenancy.models import PaymentMethod

        rows = PaymentMethod.objects.filter(tenant_id=tenant_id, active=True).order_by("name")
        return [{"value": one.code, "label": one.name, "id": one.id} for one in rows]
    if entity_type == "reversal_reason":
        from apps.payments.models import REVERSAL_REASONS

        return [
            {"value": code, "label": REVERSAL_REASON_LABELS.get(code, code), "id": None}
            for code in REVERSAL_REASONS
        ]
    if entity_type == "ledger_account":
        from apps.ledger.models import LedgerAccount

        rows = LedgerAccount.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True).order_by(
            "code"
        )
        return [
            {"value": one.code, "label": f"{one.code} · {one.name}", "id": one.id} for one in rows
        ]
    if entity_type == "route":
        from apps.metering.models import Route

        rows = Route.objects.filter(tenant_id=tenant_id).exclude(status="inactive").order_by("code")
        return [{"value": one.code, "label": one.name or one.code, "id": one.id} for one in rows]
    if entity_type == "meter_type":
        from apps.assets.models import MeterType

        rows = MeterType.objects.filter(tenant_id=tenant_id, active=True).order_by("name")
        return [{"value": one.code, "label": one.name, "id": one.id} for one in rows]
    if entity_type == "service":
        from apps.tenancy.models import Service

        rows = Service.objects.filter(active=True).order_by("id")
        return [{"value": one.code, "label": one.name, "id": one.id} for one in rows]
    raise ValueError(f"{entity_type!r} is not one of {list(MAPPING_ENTITY_TYPES)}")


def resolve(tenant_id: Any, entity_type: str, local_value: str) -> dict[str, Any] | None:
    """The one of ours called `local_value` (its CODE), or None — never a guess."""
    wanted = str(local_value).strip()
    for one in our_choices(tenant_id, entity_type):
        if one["value"] == wanted:
            return one
    return None


# ── the read: S143's rows ───────────────────────────────────────────────────


def _last_seen(connection: models.IntegrationConnection | None) -> dict[str, str]:
    if connection is None:
        return {}
    return dict((connection.config or {}).get("last_seen") or {})


def _seen_key(entity_type: str, external_value: str) -> str:
    return f"{entity_type}:{external_value}"


def _production_connection(tenant_id: Any, provider_key: str):
    return (
        models.IntegrationConnection.objects.filter(tenant_id=tenant_id, provider_key=provider_key)
        .order_by("environment")
        .first()
    )


def _match(row: models.IntegrationTargetReference, choices: list[dict]) -> dict | None:
    """The choice a stored row points at — by id first, then by code — or
    None when what it pointed at no longer exists (a retired tender)."""
    if row.entity_id is not None:
        for one in choices:
            if one["id"] is not None and str(one["id"]) == str(row.entity_id):
                return one
    if row.local_value:
        for one in choices:
            if one["value"] == row.local_value:
                return one
    return None


def view(
    tenant_id: Any,
    provider_key: str,
    *,
    target_key: str | None = None,
    registry: Registry = REGISTRY,
) -> dict[str, Any]:
    """`GET /integrations/{key}/mappings` — every row for the target, unmapped first.

    The manifest's shipped words and the stored rows are merged: a shipped
    word with no row is an unmapped row; a stored word the manifest never
    listed (an inbound arrival, or a typed one on an open vocabulary) is a row
    too. Choices travel beside the rows so the screen makes one call.
    """
    manifest: Manifest = registry.require(provider_key)
    target = target_key or provider_key
    stored = list(
        models.IntegrationTargetReference.objects.filter(tenant_id=tenant_id, target_key=target)
    )
    seen = _last_seen(_production_connection(tenant_id, provider_key))

    types: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for vocabulary in manifest.vocabularies:
        choices = our_choices(tenant_id, vocabulary.entity_type)
        stored_here = {
            one.external_value: one for one in stored if one.entity_type == vocabulary.entity_type
        }
        words = list(vocabulary.values) + sorted(
            word for word in stored_here if word not in vocabulary.values
        )
        unmapped = 0
        for word in words:
            row = stored_here.get(word)
            local = _match(row, choices) if row is not None else None
            state = STATE_MAPPED if local is not None else STATE_UNMAPPED
            unmapped += state == STATE_UNMAPPED
            rows.append(
                {
                    "entity_type": vocabulary.entity_type,
                    "external_value": word,
                    "local_value": local["value"] if local else None,
                    "local_label": local["label"] if local else None,
                    "state": state,
                    "shipped": word in vocabulary.values,
                    "last_seen_at": seen.get(_seen_key(vocabulary.entity_type, word)),
                    # `OQ-INT-1487` ruled: the control stays disabled and the
                    # SCREEN SAYS WHY. It was `decision_pending` until
                    # 2026-09-04; a key claiming a decision is pending, on a
                    # decision that was made, is hard-won law 1 in a field name.
                    "stays_other": (
                        vocabulary.entity_type == "reversal_reason" and word == R02_ACCOUNT_CLOSED
                    ),
                }
            )
        types.append(
            {
                "entity_type": vocabulary.entity_type,
                "label": vocabulary.label,
                "summary": vocabulary.summary,
                "open": vocabulary.open,
                "choices": [{"value": one["value"], "label": one["label"]} for one in choices],
                "counts": {"rows": len(words), "unmapped": unmapped},
                # `OQ-INT-1480` HELD — the chart's own references stay where
                # they are, permanently.
                "beside_the_chart": vocabulary.entity_type == "ledger_account",
            }
        )
    rows.sort(key=lambda one: (0 if one["state"] == STATE_UNMAPPED else 1, one["external_value"]))
    return {
        "provider": {"key": manifest.key, "display_name": manifest.display_name},
        "target_key": target,
        "types": types,
        "rows": rows,
        "counts": {
            "rows": len(rows),
            "unmapped": sum(1 for one in rows if one["state"] == STATE_UNMAPPED),
        },
    }


# ── the runners' reads ──────────────────────────────────────────────────────


def local_for(tenant_id: Any, target_key: str, entity_type: str, external_value: str):
    """What one of THEIR words means — `{value, label, id}` — or None, which the
    caller records as *Other* (BR-INT-031). Never raises over a vocabulary."""
    row = models.IntegrationTargetReference.objects.filter(
        tenant_id=tenant_id,
        target_key=target_key,
        entity_type=entity_type,
        external_value=external_value,
    ).first()
    if row is None or (row.entity_id is None and not row.local_value):
        return None
    return _match(row, our_choices(tenant_id, entity_type))


def external_for(tenant_id: Any, target_key: str, entity_type: str, local_value: str) -> str | None:
    """THEIR word for one of ours, for an outbound file.

    ⚠ For `qbo` and `xero` on a ledger account the answer is the chart's own
    column — READ here, never widened (OQ-INT-1480). Every other target reads
    the row. An unmapped value answers None; the caller refuses BY NAME
    (BR-INT-031's outbound half), it does not invent a string.
    """
    if entity_type == "ledger_account" and target_key in LEDGER_COLUMN_TARGETS:
        from apps.ledger.models import LedgerAccount

        account = LedgerAccount.objects.filter(
            tenant_id=tenant_id, code=local_value, deleted_at__isnull=True
        ).first()
        return getattr(account, LEDGER_COLUMN_TARGETS[target_key], None) or None
    row = (
        models.IntegrationTargetReference.objects.filter(
            tenant_id=tenant_id, target_key=target_key, entity_type=entity_type
        )
        .filter(local_value=local_value)
        .order_by("external_value")
        .first()
    )
    return row.external_value if row is not None else None


def retire_vendor_columns() -> None:
    """RULED SHUT 2026-09-04, which is not the same as unbuilt.

    `OQ-INT-1480` asked whether these rows should replace `ledger_accounts`'
    `qbo_ref` / `xero_ref`. The Product Owner HELD the requirement — *"hold this
    requirement for now; we will use our GL code only"* — so the two columns
    stay, no third column is ever added, and the chart gains no fund /
    department / object segments.

    ⚠ **A LANE FINDING THIS SHOULD LEAVE IT ALONE.** A stub awaiting a ruling
    invites unblocking; a deliberate absence does not, and telling them apart is
    the whole reason this docstring is longer than the function. The message
    below names the ruling rather than a question, so nothing here reads as work
    somebody forgot to finish.
    """
    raise NotImplementedError(
        "ruled 2026-09-04: the chart keeps qbo_ref and xero_ref and gains no "
        "third column; a partner needing a segmented account string is not served"
    )


# ── the writers ─────────────────────────────────────────────────────────────


def _refuse(code: str, message_key: str, **params: Any) -> errors.ValidationError:
    return errors.ValidationError(code, message_key=message_key, params=params)


@require_role(SYSTEM_ADMIN)
@transaction.atomic
def set_rows(
    *,
    actor: Any,
    tenant_id: Any,
    provider_key: str,
    rows: list[dict[str, Any]],
    target_key: str | None = None,
    registry: Registry = REGISTRY,
) -> list[models.IntegrationTargetReference]:
    """`PUT /integrations/{key}/mappings` — set one or more rows: their word → our value.

    Refuses, before any row is touched: a kind of thing we do not have; a blank
    word; the same word twice in one request (*one of their words means
    exactly one of ours*); a value that is not one of ours (*not one of our
    values*, TC-4); and `R02` on a reversal reason, which is `OQ-INT-1487`'s.
    An empty `local_value` UNMAPS — the row stays, red, so the word is not
    lost. Every row written carries an audit row with before and after
    (hard rule 7: a mapping decides where money lands on a report).
    """
    registry.require(provider_key)
    target = target_key or provider_key
    seen: set[tuple[str, str]] = set()
    planned: list[tuple[str, str, dict | None]] = []
    for one in rows:
        entity_type = str(one.get("entity_type") or "").strip()
        external = str(one.get("external_value") or "").strip()
        local_value = one.get("local_value")
        if entity_type not in MAPPING_ENTITY_TYPES:
            raise _refuse(errors.VAL_UNKNOWN_LOOKUP, "integrations.refusal.mapping_type", kind=entity_type)
        if not external:
            raise _refuse(errors.VAL_REQUIRED, "integrations.refusal.mapping_word")
        if (entity_type, external) in seen:
            raise _refuse(errors.VAL_FORMAT, "integrations.refusal.mapping_twice", word=external)
        seen.add((entity_type, external))
        if entity_type == "reversal_reason" and external == R02_ACCOUNT_CLOSED:
            # Ruled 2026-09-04, option (b): `R02` records as `other` with the
            # raw code kept, and the four signed reasons are not widened. This
            # is a REFUSAL a clerk reads, not a stub awaiting an answer.
            raise _refuse(
                errors.VAL_UNKNOWN_LOOKUP,
                "integrations.refusal.mapping_r02_stays_other",
                word=external,
            )
        resolved = None
        if local_value not in (None, ""):
            resolved = resolve(tenant_id, entity_type, str(local_value))
            if resolved is None:
                raise _refuse(
                    errors.VAL_UNKNOWN_LOOKUP,
                    "integrations.refusal.mapping_not_ours",
                    value=str(local_value),
                )
        planned.append((entity_type, external, resolved))

    written: list[models.IntegrationTargetReference] = []
    for entity_type, external, resolved in planned:
        existing = models.IntegrationTargetReference.objects.filter(
            tenant_id=tenant_id, target_key=target, entity_type=entity_type, external_value=external
        ).first()
        before = (
            {"entity_id": existing.entity_id, "local_value": existing.local_value}
            if existing is not None
            else None
        )
        after = {
            "entity_id": resolved["id"] if resolved else None,
            "local_value": resolved["value"] if resolved else None,
        }
        if existing is None:
            row = models.IntegrationTargetReference.objects.create(
                tenant_id=tenant_id,
                target_key=target,
                entity_type=entity_type,
                external_value=external,
                **after,
            )
        else:
            row = existing
            row.entity_id = after["entity_id"]
            row.local_value = after["local_value"]
            row.save(update_fields=["entity_id", "local_value"])
        core_audit.money_action(
            actor,
            "integration.mapping.set",
            "integration_target_reference",
            row.id,
            before=before,
            after={
                "target_key": target,
                "entity_type": entity_type,
                "external_value": external,
                **after,
            },
        )
        written.append(row)
    return written


def record_unknown(
    *,
    connection: models.IntegrationConnection,
    entity_type: str,
    external_value: str,
    seen_at: datetime | None = None,
) -> models.IntegrationTargetReference:
    """BR-INT-031's inbound half: a word nobody mapped becomes a red row with
    *last seen*, and NOTHING is refused. Called by the inbound door (wave N)
    after it has recorded the payment as *Other*.

    *Last seen* lives on the connection's non-secret `config` — the story's
    own placement (US-INT-037 §5) — because the row is keyed by target, not by
    connection, and the arrival is a fact about this connection.
    """
    if entity_type not in MAPPING_ENTITY_TYPES:
        raise ValueError(f"{entity_type!r} is not one of {list(MAPPING_ENTITY_TYPES)}")
    word = str(external_value).strip()
    if not word:
        raise ValueError("an arriving value with no word cannot be recorded")
    row, _created = models.IntegrationTargetReference.objects.get_or_create(
        tenant_id=connection.tenant_id,
        target_key=connection.provider_key,
        entity_type=entity_type,
        external_value=word,
        defaults={"entity_id": None, "local_value": None},
    )
    config = dict(connection.config or {})
    last_seen = dict(config.get("last_seen") or {})
    last_seen[_seen_key(entity_type, word)] = (seen_at or timezone.now()).isoformat()
    config["last_seen"] = last_seen
    connection.config = config
    connection.save(update_fields=["config", "updated_at"])
    return row


def apply_suggestions(*, actor: Any, tenant_id: Any, manifest: Manifest) -> int:
    """`CR-174-BRC10` — map each still-unmapped word to the manifest's
    SUGGESTED code, where this utility has an active value with that code.

    Runs once, when the connector is switched on. **A suggestion, never a
    creation** — *"Methods come from the tenant's own payment_methods; nothing
    is created"* — so a word whose suggested code the utility does not have
    stays red for a clerk, and a word a clerk already mapped is never moved.
    Written through `set_rows`, so each row carries its audit row (hard rule
    7: a mapping decides where money lands). Answers how many it mapped.
    """
    planned: list[dict[str, Any]] = []
    for vocabulary in manifest.vocabularies:
        if not vocabulary.suggested:
            continue
        ours = {one["value"] for one in our_choices(tenant_id, vocabulary.entity_type)}
        for word, code in vocabulary.suggested.items():
            if code not in ours:
                continue
            if local_for(tenant_id, manifest.key, vocabulary.entity_type, word) is not None:
                continue
            planned.append(
                {"entity_type": vocabulary.entity_type, "external_value": word, "local_value": code}
            )
    if planned:
        set_rows(actor=actor, tenant_id=tenant_id, provider_key=manifest.key, rows=planned)
    return len(planned)


__all__ = [
    "LEDGER_COLUMN_TARGETS",
    "apply_suggestions",
    "R02_ACCOUNT_CLOSED",
    "REVERSAL_REASON_LABELS",
    "STATE_MAPPED",
    "STATE_UNMAPPED",
    "external_for",
    "local_for",
    "our_choices",
    "record_unknown",
    "resolve",
    "retire_vendor_columns",
    "set_rows",
    "view",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-037@87b94265 (EP-INT-10 story + BR-INT-031 · BR-INT-032 verbatim; 03-field-map.md §5 DDL; T-B1)
# generated: 2026-09-03 by the CR-069 wave D build lane
# checklist: A✔ B✔ C✔ D✔(mappings_api.py — GET / PUT /integrations/{key}/mappings) E✔(features/integrations/ValueMappingPage.tsx) F✔ G✔ H=n/a(no RLS written here — the 0002 migration's; no money math; no key)
# gates: pytest tests/test_us_int_037_mappings.py (SQLite) · tests/test_us_int_037_pg.py (PostgreSQL: the UNIQUE, the fourth partner) · G8 (two honest stubs, each naming an OPEN question) · G32 (every message_key here resolves in en.json) · G77 (no `provider_key ==` — the manifest's vocabulary decides)
# exceptions: `record_unknown` writes no audit row — it records an arrival, not a decision; the payment it accompanies is audited by payments · `our_choices` reads five other modules' lookups through the ORM (a READ; B1 forbids cross-module WRITES) · *last seen* lives on `integration_connection.config` by the story's own placement, not on the row
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
