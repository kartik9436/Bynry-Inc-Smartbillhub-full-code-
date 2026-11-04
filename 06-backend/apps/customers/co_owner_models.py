# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 `P1.01` (lane MVI-SCHEMA) — PO, mock-up v2: *"you also
#           need co-owner and capture all details"*; v7: *"Co-owners - can you do
#           tick and collapable"*; v22: a new table only where nothing exists.
# Rules:    BR-CUS-092 (SSN and driving licence captured, encrypted at the
#           application layer, shown as the last four only) · OQ-016 CLOSED
#           (app-layer encryption for high-sensitivity columns) · CLAUDE.md hard
#           rule 1 (RLS FORCE — `customers/0080`) · hard rule 2 (a percentage is
#           stored to 6 places) · hard rule 8 (no address column)
# Migration: apps/customers/migrations/0080_cr171_p1_01_move_in_redesign.py 🔒
# Tests:    06-backend/tests/test_cr171_p1_01_move_in_schema.py ·
#           06-backend/tests/test_cr171_p1_01_rls_pg.py
# Readers:  P1.10 (written at Complete, read on the move-in Account tab) ·
#           P1.20 (an extra message may be addressed to one co-owner)
# ───────────────────────────────────────────────────────
"""**The people who share an account with its holder** — a person's CO-OWNERS
and a company's OWNERS AND OFFICERS, in one table with a `kind`.

🔒 HUMAN-REVIEW-PENDING — the encrypted identity columns (BR-CUS-092) and the
table's migration (`customers/0080`, migration ordering + RLS). Row in
`12-governance/09-human-review-ledger.md`.

═══════════════════════════════════════════════════════════════════════════
1 · WHY A NEW TABLE, AND WHY ONE AND NOT TWO
═══════════════════════════════════════════════════════════════════════════
The PO ruled a new table only where nothing holds the fact (v22, *"use existing
code and files and modify"*). What exists today, weighed:

| Where it could live | Why not |
|---|---|
| `service_requests.co_applicant_*` | Three fields (name, email, phone) on the APPLICATION. The drawing asks for ten facts per person and any number of people, and an application is not the account. |
| `contacts` | One row per account contact with `gov_id_last4` in the clear-ish and no encrypted SSN, no licence, no blind index, no responsibility flag, no stake. Widening it would change a live PII table's meaning for every account that has one. It stays the CONTACT PERSON's home (CR-171 E59). |
| `customer_accounts` (the BR-CUS-054 N:M link) | It links two CUSTOMER rows. A co-owner is captured without a customer number and is never matched or numbered — making each one a `customers` row would put them in every identity search and every carry-forward check (BR-CUS-089). |

A co-owner (image 38) and an officer (image 40) are the same SHAPE — a named
person with an identity, a phone, an email, a photo ID and a role on the account
— differing in four facts. One table with `kind` is what the CR names (§6 (1))
and what one component on screen (P2.24, *"one component, two kinds"*) reads.

═══════════════════════════════════════════════════════════════════════════
2 · THE IDENTITY COLUMNS ARE `customers.Customer`'S, COLUMN FOR COLUMN
═══════════════════════════════════════════════════════════════════════════
`ssn` and `driving_licence` are `EncryptedTextField`s with a `*_bidx` blind
index beside each, written together by `set_identifier` below — the shape
`identity_match.set_identifier` has for a customer. **The crypto contexts are
this table's own** (`account_co_owners.ssn`), so a ciphertext lifted out of
`customers.ssn` RAISES here rather than decrypting (`core.crypto`'s AAD).

⚠ **NO `ssn_last4` COLUMN AND THERE MUST NOT BE** — the last four is a READ
projection (`crypto.last_four`), for the reason `Customer` gives.

⚠ **THE PHONE IS NOT ENCRYPTED, AND THAT FOLLOWS `contacts` RATHER THAN
`customers`.** `customers.phone` is encrypted because it is MATCH evidence
(BR-CUS-089) and needs a blind index; a co-owner is never matched, and the
brief (`P1.01`) names the SSN and the licence and nothing else.

═══════════════════════════════════════════════════════════════════════════
3 · WHAT IS DELIBERATELY NOT HERE
═══════════════════════════════════════════════════════════════════════════
* **No address** (hard rule 8): a co-owner lives at the account's unit or is
  reached by phone and email; a mailing address is `addresses kind='mailing'`.
* **No customer link**: §1's last row.
* **No DELETE door is built here** — nothing is a service in `P1.01`; `P1.10`
  owns the writer and states its own removal rule.
"""

from __future__ import annotations

from typing import Any

from django.db import models
from django.db.models import Q

from core import crypto
from core.crypto import EncryptedTextField
from core.dbfields import CITextField, uuid7_pk
from core.money_fields import percent_field

from apps.customers.models import CONTACT_BY

KIND_CO_OWNER = "co_owner"
KIND_OFFICER = "officer"
KINDS: tuple[str, ...] = (KIND_CO_OWNER, KIND_OFFICER)

#: *Contact by* on image 38 (*Text*) and image 40 (*Email*) is `CONTACT_BY` —
#: ONE list, shared with `contacts.contact_by` and declared in `models.py` (this
#: module is imported at that file's foot, after the list exists).

#: The column each ciphertext is bound to. A test asserts these against the
#: field declarations rather than trusting this comment (hard-won law 1).
CRYPTO_CONTEXT: dict[str, str] = {
    "ssn": "account_co_owners.ssn",
    "driving_licence": "account_co_owners.driving_licence",
}
BIDX_COLUMN: dict[str, str] = {
    "ssn": "ssn_bidx",
    "driving_licence": "driving_licence_bidx",
}


class AccountCoOwner(models.Model):
    """One co-owner of a person's account, or one owner/officer of a company's.

    MANAGED, registered by `models.py`'s import at its foot — the pattern
    `move_in_jobs.MoveInJob` and `moves.MoveRecord` follow.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The account they share. NOT NULL: a co-owner is written at Complete
    #: (`P1.10`), when the account exists; before that the wizard's parked
    #: values hold them (`wizard_parks.values`).
    account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="account_id",
        related_name="co_owners",
    )
    #: `co_owner` | `officer` — CHECK-constrained.
    kind = models.TextField()
    full_name = models.TextField()  # PII
    #: Co-owner only: *Spouse*, *Partner*, … — the dropdown's vocabulary is the
    #: screen's (P2.24) and is free text here, as `channel` is on a request.
    relationship = models.TextField(null=True, blank=True)
    #: Officer only: *Managing member*, *Director*, …
    title = models.TextField(null=True, blank=True)
    #: Officer only: the stake, a PERCENTAGE stored to 6 places (hard rule 2),
    #: 0–100 inclusive, in percent points (`50.000000`), through
    #: `core.money_fields.percent_field` so the place count cannot drift. NULL =
    #: not stated.
    ownership_pct = percent_field(null=True, blank=True)
    #: Officer only: *Signs* on image 40, and *personal guarantee* (v2 row).
    signs_for_company = models.BooleanField(default=False)
    personal_guarantee = models.BooleanField(default=False)
    date_of_birth = models.DateField(null=True, blank=True)  # PII
    ssn = EncryptedTextField(null=True, blank=True, crypto_context="account_co_owners.ssn")
    ssn_bidx = models.TextField(null=True, blank=True)
    driving_licence = EncryptedTextField(
        null=True, blank=True, crypto_context="account_co_owners.driving_licence"
    )
    driving_licence_bidx = models.TextField(null=True, blank=True)
    phone = models.TextField(null=True, blank=True)  # PII — §2's last paragraph
    email = CITextField(null=True, blank=True)  # PII (DB-15 citext, as `contacts`)
    contact_by = models.TextField(null=True, blank=True)
    #: The PHOTO ID — a filing card on the same account (`AccountDocument`),
    #: never a second file column. NULL is *"No ID"* on the card's summary line.
    photo_id_document = models.ForeignKey(
        "customers.AccountDocument",
        on_delete=models.PROTECT,
        db_column="photo_id_document_id",
        related_name="+",
        null=True,
        blank=True,
    )
    #: *"Also responsible for the bills"* (image 38).
    responsible_for_bills = models.BooleanField(default=False)
    #: BR-TEN-057 — the sample tag rides the owning row.
    is_sample = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "customers"
        db_table = "account_co_owners"
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=KINDS), name="ck_account_co_owners_kind"),
            models.CheckConstraint(
                condition=Q(contact_by__isnull=True) | Q(contact_by__in=CONTACT_BY),
                name="ck_account_co_owners_contact_by",
            ),
            models.CheckConstraint(
                condition=Q(ownership_pct__isnull=True)
                | (Q(ownership_pct__gte=0) & Q(ownership_pct__lte=100)),
                name="ck_account_co_owners_ownership_pct",
            ),
            # An officer's four facts are an officer's: a co-owner carrying a
            # title or a stake is a row the screen could not have drawn.
            models.CheckConstraint(
                condition=Q(kind=KIND_OFFICER)
                | (
                    Q(title__isnull=True)
                    & Q(ownership_pct__isnull=True)
                    & Q(signs_for_company=False)
                    & Q(personal_guarantee=False)
                ),
                name="ck_account_co_owners_officer_facts",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "account"], name="ix_account_co_owners_account"),
            # Equality probes on a blind-index token, as `customers` has them.
            models.Index(fields=["tenant", "ssn_bidx"], name="ix_account_co_owners_ssn_bidx"),
            models.Index(
                fields=["tenant", "driving_licence_bidx"], name="ix_account_co_owners_dl_bidx"
            ),
        ]


def set_identifier(row: AccountCoOwner, field: str, value: Any) -> None:
    """Write one encrypted identifier AND its blind-index token, in one act.

    `identity_match.set_identifier`'s posture for a customer: a ciphertext with
    no token is unfindable, a token with no ciphertext is an oracle over a value
    nobody can read. Clearing (`None`/`''`) clears both. The caller saves.
    """
    if field not in CRYPTO_CONTEXT:
        raise ValueError(f"{field} is not an encrypted co-owner column")
    cleaned = None if value in (None, "") else str(value).strip()
    setattr(row, field, cleaned)
    setattr(row, BIDX_COLUMN[field], crypto.blind_index(cleaned, context=CRYPTO_CONTEXT[field]))
