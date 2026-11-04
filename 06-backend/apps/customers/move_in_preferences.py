# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 P1.15 — the Billing step's Preferences, Discounts and
#           Tax sections (images 41, 44), lane MVI-MONEY. PO, mock-up v20:
#           *"Preferences - … Paperless billing / Text reminders / Autopay /
#           Portal language — Discounts to claim - Same UI and drop downs; Tax -
#           same Ui and Exemption … date as date pickers and you have to allow
#           uplaod certificate"*.
# Rules:    BR-CUS-059 (autopay is capture-only — stored, never drafted
#           against) · BR-CWP-057 (an instrument is a token, never a number) ·
#           BR-RAT-069 / BR-RAT-110 (an ENROLMENT grants a discount; only a
#           discount the plan carries can be claimed) · BR-RAT-076 (rating
#           decides pending vs verified) · BR-RAT-105 (an exemption certificate
#           is rating's row) · BR-CUS-036 (an account document is filed through
#           its own door) · hard-won law 14 (a SAVEPOINT around anything caught)
#           · CLAUDE.md rules 1, 7
# Change:   CR-171-BRC10 lane RULINGS (2026-10-05) — the clerk's claim and
#           certificate take effect without a System Admin. PO ruling, decision
#           log *"FOUR PO RULINGS IN ONE REPLY"* (2), option (b), verbatim: *"Let
#           billing clerks record it themselves. - we have set the limits so
#           clark can do it - its a day to day work"*. The HELD path is deleted.
# Change:   DEF-CUS-9724 lane RULINGS-2 (2026-10-05) — an exemption removes
#           only the tax named on its certificate; the blanket flag is never
#           set by a move-in certificate. PO, verbatim: *"(a) An exemption
#           removes only the tax named on its certificate. The church pays
#           $6.25."*
# Tests:    06-backend/tests/test_def_cus_9724_exemption_removes_only_its_own_tax.py ·
#           06-backend/tests/test_cr171_p1_15_move_in_preferences.py ·
#           06-backend/tests/test_cr171_p1_29_money_pg.py (PostgreSQL)
# ───────────────────────────────────────────────────────
"""🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — what a move-in decides about how the
account is BILLED beyond the plan: where autopay draws from, which discounts
are claimed, and the tax exemption with its certificate.

AI-authored 2026-10-05 (lane MVI-MONEY, `CR-171-BRC10` P1.15) under the PO
ruling of 2026-08-09; row in `12-governance/09-human-review-ledger.md`
(*"CR-171 MOVE-IN MONEY"*).

**Paperless, text reminders, autopay on/off and portal language are NOT here.**
They were account columns before this CR (`paperless`, `sms_reminders`,
`autopay`, `preferred_language`) and the move-in already writes them through
`CREATE_FIELDS`; the redesign only DRAWS them as dropdowns. This module adds
the three facts that had no move-in door:

1. **`autopay_instrument_id`** — *Autopay from* (image 44). An instrument is the
   CUSTOMER's (`StoredPaymentInstrument` hangs off the customer, so a landlord
   saves one card for four accounts), so it is checked AFTER the account knows
   its customer: it must be a live instrument of that customer, and autopay
   must be on. Capture-only (BR-CUS-059) — nothing here charges it.

2. **`discount_claims`** — the table array of discounts to claim. Each must be
   a discount the unit's PLAN carries on the move-in day (rating's
   `discount_ids_carried`, ruling 2 of 2026-10-03), at most once, and never
   an AUTOMATIC one (`DEF-CUS-9779`: the nightly sync grants and ends those
   from the account's own facts, so a claim was ended overnight) — ⚖️ EXCEPT
   Autopay and Paperless since PO D2 (b) and ruling 4 of 2026-10-06
   (`DEF-RAT-9833`): those are claimed again and switch the account's setting
   On, so the sync keeps them. Each is
   written through rating's own `enrol_account` via
   `discounts.claim_assistance`, so there is ONE grant table and rating decides
   *pending* (proof needed) or *not required* (BR-RAT-076).

3. **`tax_exemption`** — the exemption TYPE (a `TaxExemptionCategory`), the
   certificate number, issued and expiry dates, and the certificate FILE. The
   account's BLANKET columns (`tax_exempt`, `tax_exempt_ref`,
   `tax_exempt_expires`) are NOT set — they zero every authority at once, and
   an exemption removes only the tax on its certificate (`DEF-CUS-9724`, PO
   2026-10-05, see `merge_account_values`); the certificate ROW is rating's
   (`record_exemption_certificate`, BR-RAT-105) — the row a bill run actually
   reads; the FILE is an `account_documents` card (type `kyc`, the evidence a
   clerk holds about the customer, withdrawable if the wrong file went up).

⚖️ **A BILLING CLERK RECORDS BOTH, AND THEY TAKE EFFECT AT ONCE** — PO ruling
2026-10-05 (decision log *"FOUR PO RULINGS IN ONE REPLY"* (2), option (b)),
verbatim: *"Let billing clerks record it themselves. - we have set the limits
so clark can do it - its a day to day work"*. Worked: Marcus records a church's
certificate against a 2.00% city tax and its $100.00 bill carries $0.00 of it.
Rating's two writers admit a Billing Clerk through the same `require_role`
every door uses (no new limit, no second path); the limits the PO means are
the ones already configured — the discount must be on the account's plan, its
value is the approved version's, proof makes it *pending*; the exemption
category (which tax, whether a certificate is required) is System Admin's.

⚠ **THERE IS NO CATCH ON THIS PATH ANY MORE, AND THAT IS DELIBERATE.** Until
2.539.0 an RBAC refusal from rating was caught inside a SAVEPOINT and the claim
parked for a System Admin (*held_for_system_admin*, lane MVI-MONEY, 2.529.0).
The ruling removes the refusal, so the catch would guard nothing — and a catch
that guards nothing hides the day somebody narrows rating's roles again. Every
refusal from rating now propagates and refuses the move-in by name, inside its
one transaction (BR-SHL-019), so nothing is half-written.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from datetime import date
from typing import Any


from apps.customers import models, seams
from core import errors
from core import tenancy as core_tenancy

#: The three keys this module owns on the move-in payload.
FIELDS: tuple[str, ...] = ("autopay_instrument_id", "discount_claims", "tax_exemption")
EXEMPTION_FIELDS: frozenset[str] = frozenset(
    {"category_id", "certificate_ref", "issued_on", "expires_on", "certificate"}
)
CERTIFICATE_FIELDS: frozenset[str] = frozenset({"name", "content_type", "content_base64"})
CLAIM_FIELDS: frozenset[str] = frozenset({"discount_id", "note"})

#: The document type a certificate is filed under (BR-CUS-036's uploadable set).
CERTIFICATE_DOC_TYPE = "kyc"

# ── refusals (each resolves in all eleven catalogues; ≤ six words) ──────────
INSTRUMENT_REFUSED = "customers.moveIn.instrumentRefused"
AUTOPAY_OFF = "customers.moveIn.autopayOff"
DISCOUNT_NOT_OFFERED = "customers.moveIn.discountNotOffered"
DISCOUNT_TWICE = "customers.moveIn.discountTwice"
DISCOUNT_AUTOMATIC = "customers.moveIn.discountAutomatic"
CERTIFICATE_UNREADABLE = "customers.moveIn.certificateUnreadable"
UNKNOWN_FIELD = "customers.account.unknown_field"
NOT_AN_OBJECT = "customers.payload_not_object"
DATE_INVALID = "customers.account.date_invalid"


@dataclass(frozen=True)
class Extras:
    autopay_instrument_id: str | None = None
    discount_claims: tuple[dict[str, Any], ...] = ()
    tax_exemption: dict[str, Any] | None = None
    certificate: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def empty(self) -> bool:
        return not (self.autopay_instrument_id or self.discount_claims or self.tax_exemption)


def _fe(name: str, code: str, key: str, **params: Any) -> dict[str, Any]:
    return {"field": name, "code": code, "message_key": key, "params": params}


def _raise(fe: list[dict[str, Any]]) -> None:
    if fe:
        raise errors.ValidationError(
            fe[0]["code"], message_key=fe[0]["message_key"], params=fe[0]["params"], field_errors=fe
        )


def _day(value: Any, name: str, fe: list[dict[str, Any]]) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        fe.append(_fe(name, errors.VAL_FORMAT, DATE_INVALID))
        return None


def clean(data: dict[str, Any]) -> Extras:
    """POP and validate this module's three keys off the move-in payload.
    Shape only — what needs the account (whose customer, which plan) is
    checked in `apply`, inside the transaction."""
    fe: list[dict[str, Any]] = []
    instrument = str(data.pop("autopay_instrument_id", "") or "").strip() or None
    if instrument is not None and not data.get("autopay"):
        fe.append(_fe("autopay_instrument_id", errors.VAL_RANGE, AUTOPAY_OFF))

    claims_raw = data.pop("discount_claims", None)
    claims: list[dict[str, Any]] = []
    if claims_raw is not None:
        if not isinstance(claims_raw, list):
            raise errors.ValidationError(errors.VAL_FORMAT, message_key=NOT_AN_OBJECT)
        seen: set[str] = set()
        for index, item in enumerate(claims_raw):
            where = f"discount_claims[{index}]"
            if not isinstance(item, dict):
                fe.append(_fe(where, errors.VAL_FORMAT, NOT_AN_OBJECT))
                continue
            for key in sorted(set(item) - CLAIM_FIELDS):
                fe.append(_fe(f"{where}.{key}", errors.VAL_FORMAT, UNKNOWN_FIELD))
            discount_id = str(item.get("discount_id") or "").strip()
            if not discount_id:
                fe.append(_fe(f"{where}.discount_id", errors.VAL_REQUIRED, DISCOUNT_NOT_OFFERED))
                continue
            if discount_id in seen:
                fe.append(_fe(f"{where}.discount_id", errors.VAL_RANGE, DISCOUNT_TWICE))
                continue
            seen.add(discount_id)
            claims.append(
                {"discount_id": discount_id, "note": str(item.get("note") or "").strip()[:200] or None}
            )

    exemption_raw = data.pop("tax_exemption", None)
    exemption: dict[str, Any] | None = None
    certificate: dict[str, Any] | None = None
    if exemption_raw is not None:
        if not isinstance(exemption_raw, dict):
            raise errors.ValidationError(errors.VAL_FORMAT, message_key=NOT_AN_OBJECT)
        for key in sorted(set(exemption_raw) - EXEMPTION_FIELDS):
            fe.append(_fe(f"tax_exemption.{key}", errors.VAL_FORMAT, UNKNOWN_FIELD))
        exemption = {
            "category_id": str(exemption_raw.get("category_id") or "").strip() or None,
            "certificate_ref": str(exemption_raw.get("certificate_ref") or "").strip()[:64] or None,
            "issued_on": _day(exemption_raw.get("issued_on"), "tax_exemption.issued_on", fe),
            "expires_on": _day(exemption_raw.get("expires_on"), "tax_exemption.expires_on", fe),
        }
        file_raw = exemption_raw.get("certificate")
        if file_raw is not None:
            certificate = _clean_certificate(file_raw, fe)
    _raise(fe)
    return Extras(
        autopay_instrument_id=instrument,
        discount_claims=tuple(claims),
        tax_exemption=exemption,
        certificate=certificate,
    )


def _clean_certificate(raw: Any, fe: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The certificate file, carried as base64 in the commit (one transaction —
    a move-in whose certificate cannot be filed opens no account). Size and
    type are `file_document`'s to refuse (BR-SHL-031); only READABILITY is
    checked here."""
    if not isinstance(raw, dict):
        fe.append(_fe("tax_exemption.certificate", errors.VAL_FORMAT, NOT_AN_OBJECT))
        return None
    for key in sorted(set(raw) - CERTIFICATE_FIELDS):
        fe.append(_fe(f"tax_exemption.certificate.{key}", errors.VAL_FORMAT, UNKNOWN_FIELD))
    try:
        content = base64.b64decode(str(raw.get("content_base64") or ""), validate=True)
    except (binascii.Error, ValueError):
        content = b""
    if not content:
        fe.append(_fe("tax_exemption.certificate", errors.VAL_REQUIRED, CERTIFICATE_UNREADABLE))
        return None
    return {
        "name": str(raw.get("name") or "").strip(),
        "content_type": str(raw.get("content_type") or "").strip(),
        "content": content,
    }


#: The account's BLANKET exemption columns — one boolean and one expiry that
#: zero EVERY authority's tax at once (B4.2). A move-in never writes them from
#: a certificate (DEF-CUS-9724).
BLANKET_COLUMNS: tuple[str, ...] = ("tax_exempt", "tax_exempt_ref", "tax_exempt_expires")


def merge_account_values(data: dict[str, Any], extras: Extras) -> dict[str, Any]:
    """`data` as the account write should see it, given the exemption.

    ⚖️ **AN EXEMPTION REMOVES ONLY THE TAX NAMED ON ITS CERTIFICATE** — PO
    ruling 2026-10-05 (decision log *"FIVE PO RULINGS IN ONE REPLY"* (A),
    `DEF-CUS-9724`), verbatim: *"(a) An exemption removes only the tax named on
    its certificate. The church pays $6.25."* Worked: Marcus's church holds a
    certificate for the 2.00% city tax only; on a $100.00 bill it pays $0.00
    city tax and $6.25 state tax.

    Until then (2.529.0) this set `accounts.tax_exempt = True` beside the
    certificate, and that flag is BLANKET — the church paid $0.00 where $6.25
    is owed. So with a `tax_exemption` block in the payload the certificate
    alone decides: the three blanket columns are DROPPED from the account write
    even where the payload carries them (the 2.545.0 Billing step sent
    `tax_exempt: true` beside the block), and the new account keeps its
    defaults (not exempt, no reference, no expiry). A move-in with no block is
    untouched — its blanket columns are the account door's, as before.
    """
    if extras.tax_exemption is None:
        return dict(data)
    return {key: value for key, value in data.items() if key not in BLANKET_COLUMNS}


def _customer_id(account_id: Any) -> Any:
    return (
        models.CustomerAccount.objects.filter(account_id=account_id)
        .order_by("-created_at")
        .values_list("customer_id", flat=True)
        .first()
    )


def apply(
    actor: Any,
    account: Any,
    extras: Extras,
    *,
    on_day: date | None,
    evidence_cards: list[str] | None = None,
) -> dict[str, Any] | None:
    """Write the three facts for the account the move-in just opened. INSIDE the
    move-in's transaction: a refusal rolls everything back (BR-SHL-019).

    `evidence_cards` (`DEF-CUS-9780`) — the account's *Assistance evidence*
    filing cards from this same move-in (`move_in_documents.evidence_cards`);
    each claim that lands *pending* carries them as its proof."""
    if extras.empty:
        return None
    answer: dict[str, Any] = {}
    if extras.autopay_instrument_id:
        answer["autopay"] = _autopay(account, extras.autopay_instrument_id)
    if extras.discount_claims:
        answer["discounts"] = _claims(
            actor, account, extras.discount_claims, on_day, evidence_cards or []
        )
    if extras.tax_exemption is not None:
        answer["tax_exemption"] = _exemption(actor, account, extras)
    return answer


def _autopay(account: Any, instrument_id: str) -> dict[str, Any]:
    listing = seams.resolve("payments", "list_for_customer", kind="instruments")
    customer_id = _customer_id(account.pk)
    live = []
    if listing is not None and customer_id is not None:
        live = listing(core_tenancy.current_tenant_id(), customer_id=customer_id)
    # `ref` is the instrument's id in payments' own view; `usable` is false for
    # an expired card or a status that is not live (BR-CWP-057's read).
    match = next((row for row in live if str(row.get("ref")) == instrument_id), None)
    if match is None or not match.get("usable"):
        _raise([_fe("autopay_instrument_id", errors.VAL_UNKNOWN_LOOKUP, INSTRUMENT_REFUSED)])
    account.autopay_instrument_id = instrument_id
    account.save(update_fields=["autopay_instrument_id", "updated_at"])
    return {
        "instrument_id": instrument_id,
        "brand": match.get("brand"),
        "last_four": match.get("last_four"),
    }


def _claims(
    actor: Any,
    account: Any,
    claims: tuple[dict[str, Any], ...],
    on_day: date | None,
    evidence_cards: list[str] | None = None,
) -> list[dict[str, Any]]:
    from apps.customers import discounts

    carried_fn = seams.resolve("rating", "discount_ids_carried", kind="discount_services")
    when = on_day or seams.tenant_today()
    carried = {str(one) for one in (carried_fn(account.pk, when) if carried_fn else set())}
    fe = [
        _fe(f"discount_claims[{index}].discount_id", errors.VAL_RANGE, DISCOUNT_NOT_OFFERED)
        for index, claim in enumerate(claims)
        if claim["discount_id"] not in carried
    ]
    _raise(fe)
    # DEF-CUS-9779 — an AUTOMATIC discount is the nightly sync's to grant and
    # end (PO 2026-10-03 ruling (3)); a claim of one was enrolled here and
    # ended the next night. Refused by name, read from the stored
    # `enrolment_mode` through rating's one reader — never a list of codes.
    #
    # ⚖️ AMENDED 2026-10-06 (`DEF-RAT-9833`) — PO D2 (b), verbatim: *"Offer
    # Autopay and Paperless at move-in as drawn"*. Only what NO person may add
    # is refused now (`hand_refused_discount_ids` — Municipal account,
    # *Everyone on the plan*); a claim of Autopay or Paperless switches the
    # account's setting On inside `claim_assistance` (ruling 4, reading (b)).
    automatic_fn = seams.resolve("rating", "hand_refused_discount_ids", kind="discount_services")
    automatic = automatic_fn([claim["discount_id"] for claim in claims], when) if automatic_fn else set()
    _raise(
        [
            _fe(f"discount_claims[{index}].discount_id", errors.VAL_RANGE, DISCOUNT_AUTOMATIC)
            for index, claim in enumerate(claims)
            if claim["discount_id"] in automatic
        ]
    )
    attach = (
        seams.resolve("rating", "attach_enrolment_proof", kind="discount_services")
        if evidence_cards
        else None
    )
    out: list[dict[str, Any]] = []
    for claim in claims:
        # Rating's own grant writer, through customers' claim door; the status
        # (*pending* / *not_required*) is rating's (BR-RAT-076).
        row = discounts.claim_assistance(actor, account.pk, claim["discount_id"])
        status = (row or {}).get("status")
        entry: dict[str, Any] = {"discount_id": claim["discount_id"], "status": status}
        # DEF-CUS-9780 — the evidence taken at the counter goes ON the
        # enrolment it supports, so the System Admin who verifies it finds it
        # there. Rating's writer, which never verifies: a pending claim stays
        # pending and BR-RAT-076 still holds the reduction until it is verified
        # (PO ruling (2) of 2026-10-05).
        enrolment_id = ((row or {}).get("enrolment") or {}).get("id")
        if attach is not None and status == "pending" and enrolment_id:
            entry["proof_attached"] = len(attach(actor, enrolment_id, evidence_cards, on_day))
        out.append(entry)
    return out


def _exemption(actor: Any, account: Any, extras: Extras) -> dict[str, Any]:
    from apps.customers import account_documents

    exemption = extras.tax_exemption or {}
    out: dict[str, Any] = {"certificate": None, "document": None, "status": None}
    if exemption.get("category_id"):
        record = seams.resolve("rating", "record_exemption_certificate")
        payload = {"account_id": str(account.pk)}
        for key in ("certificate_ref",):
            if exemption.get(key):
                payload[key] = exemption[key]
        for key in ("issued_on", "expires_on"):
            if exemption.get(key):
                payload[key] = exemption[key].isoformat()
        if record is not None:
            out["certificate"] = record(actor, exemption["category_id"], payload)
            out["status"] = "recorded"
    if extras.certificate is not None:
        upload = extras.certificate
        out["document"] = account_documents.file_document(
            actor,
            account.pk,
            {
                "doc_type": CERTIFICATE_DOC_TYPE,
                "name": upload["name"] or "tax-exemption-certificate.pdf",
                "content_type": upload["content_type"],
            },
            upload["content"],
        )
    return out
