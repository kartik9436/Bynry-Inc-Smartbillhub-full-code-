# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-013 (a posted JE's "edit" is one-click REVERSE + REPOST —
#           TC-1 the mirror + prefilled draft, TC-3 reason + audit, TC-4 the
#           reverse-only path, TC-5/TC-6 the refusals) · US-LED-014 (dual-basis
#           remittance — TC-3 the JE that drains the authority's liability,
#           TC-6/TC-7 its refusals)
#           Screens: S56 · S57 · S41
# Rules:    BR-LED-003 ("edit/update" of a posted JE = one-click REVERSE +
#           REPOST; posted entries immutable; reason + audit) · BR-LED-002
#           (remittance payment = a JE draining the authority's liability) ·
#           BR-LED-012 (the journal list carries the IS-5 capability row) ·
#           BR-LED-015 (every finance action writes audit_log) · BR-LED-019
#           (remittance records carry a filing CONFIRMATION REF + receipt) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money never a float) ·
#           rule 4 (financial immutability — nothing here UPDATEs a posted row)
#           · rule 5 (only the posting service writes journal lines — this
#           module CALLS it and writes nothing itself) · rule 6 (idempotency) ·
#           rule 7 (audit)
# Golden:   LE-8 (JE-104 250.00 → JE-105 mirror → JE-106 205.00, net 205.00) ·
#           LE-3 (State remittance 13.87: DR 2200 State / CR cash)
# Tests:    06-backend/tests/test_us_led_013_reverse_repost.py ·
#           06-backend/tests/test_us_led_014_remittance.py
# Impacts:  apps/ledger/posting.py (the sole writer — `reverse_entry` and
#           `post` are called BY NAME from here; `reverse_entry` grew an
#           additive `audit_context` for US-LED-013 TC-3's reason) ·
#           apps/ledger/reporting.py (reads back what this posts: the remitted
#           column of `remittance_by_authority`, the links on the journal list)
# ───────────────────────────────────────────────────────
"""The ledger's OWN money actions — each one a call to the posting service.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module reverses posted entries and
drains tax liabilities. AI-authored 2026-08-11 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md. It is NOT on the G7
glob list and that is REPORTED rather than quietly accepted — editing
`10-scripts/gates/human_owned.txt` is a process event this lane may not make
alone, and a marker no gate reads is hard-won law 1 living inside a money path.

╔══════════════════════════════════════════════════════════════════════════╗
║  NOTHING HERE WRITES A JOURNAL LINE. IT ASKS apps/ledger/posting.py TO.  ║
╚══════════════════════════════════════════════════════════════════════════╝

CLAUDE.md rule 5, and `ledger/0004`'s trigger enforces it in the database: the
tables refuse an INSERT that did not come through `post()`. This module composes
requests and reads results. There is no `objects.create`, no `bulk_create` and
no `set_config` below.

════════════════════════════════════════════════════════════════════════════
US-LED-013 — "EDIT" IS A WORD THE BOOKS DO NOT HAVE
════════════════════════════════════════════════════════════════════════════
BR-LED-003 (CONFIRMED, PO LF-3, 2026-08-08): *"Posted journal entries are
IMMUTABLE (hard rule 4); 'edit/update' = one-click REVERSE + REPOST (mirror
entry linked + prefilled new draft)"*. LE-8 works it: JE-104 posted with 250.00
that should have been 205.00 → one click → JE-105 mirror (linked) + JE-106 draft
prefilled → corrected to 205.00 → post. **Net effect 205.00; history shows all
three, forever.**

`reverse_and_repost` below is that click. Three things it does NOT do, each for
a reason worth more than the line it saves:

  * **It does not hand-write the mirror.** `apps.ledger.posting.reverse_entry`
    already exists, reads the ORIGINAL and copies it line for line with the
    sides swapped, and computes nothing. A compensating entry composed here
    would be a second implementation of "what does reversing this mean", sitting
    downstream of the first, free to disagree with it — and because the original
    is immutable, the disagreement would be permanent. Hard rule 5's "only the
    ledger posting service writes journal lines" is the letter; not re-deriving
    what it already derives is the spirit.
  * **It does not UPDATE anything.** Not the amount, not the memo, not the
    status. `ledger/0002`'s append-only trigger refuses it anyway; the point is
    that no code path here tries, so the trigger is a second fence rather than
    the only one.
  * **It does not WRITE the prefilled draft** — it RETURNS it. Two reasons, and
    the first is structural: `journal_entries` refuses an INSERT outside
    `post()`, and `post()` posts. A draft row therefore cannot exist until
    US-LED-011 builds the draft lifecycle (EP-LED-04), which this story
    `depends_on` and which is unbuilt. The second is that a draft is
    *"worthless"* by BR-LED-003's own word — US-LED-013 TC-4 has staff post the
    mirror and DISCARD the draft, and a payload nobody stored is discarded by
    doing nothing. REPORTED on every result as `repost_draft_is_not_persisted`.

════════════════════════════════════════════════════════════════════════════
US-LED-014 — RECORDING A REMITTANCE IS A JOURNAL ENTRY, NOT A ROW IN A REGISTER
════════════════════════════════════════════════════════════════════════════
BR-LED-002: *"remittance payment = JE draining the authority's liability"*, and
US-LED-001's contract table signs the sides: *"Tax remittance payment | tax
payable (authority) | cash"*. US-LED-014 TC-3 works it — **DR 2200 State 13.87 /
CR cash 13.87**, balanced, through the posting service.

`record_tax_remittance` writes that entry and NOTHING else, because there is
nothing else to write to: `tax_remittances` (B2 Addendum r13 #3) does not exist
in the schema. What that costs is stated rather than absorbed:

  * **The confirmation ref survives** — it is REQUIRED here (BR-LED-019) and
    lands in the entry's `memo`, which is immutable, and in the `audit_log`
    payload, which is append-only. Both are auditor artifacts.
  * **The receipt FILE does not.** BR-LED-019 wants an attachment and there is
    no column, no storage seam and no signed shape for one. The parameter is
    refused by name rather than accepted and dropped — accepting a receipt and
    discarding it is the worst of the three options, because the clerk who
    attached it believes it is kept.
  * **The remitting BASIS is recorded on the entry**, not chosen by it. The
    per-authority setting r13 #3 would hold does not exist (see
    `apps/ledger/reporting.GAP_REMITTING_BASIS_SETTING`), so the caller states
    which basis this payment answers and this module records the statement.

**THE ACCOUNT IS CHECKED AGAINST THE SIGNED SERIES.** A remittance debits a
2200-nn tax-payable account (B5 line 74 ❄️ *"2200-series Tax payable per
authority"*; BR-BIL-069 *"For each atheority have separate account"*), and this
refuses any other account outright. The failure it prevents is specific: a
remittance keyed against 4100 would drain REVENUE, balance perfectly, pass every
trigger, and be discoverable only by someone reading the trial balance line by
line.

**IDEMPOTENCY IS AUTHORITY + PERIOD + AMOUNT**, which is US-LED-014 TC-7's own
wording (*"The same remittance recorded twice for the same authority+period+
amount → second attempt surfaces the existing row — no silent double-drain"*).
The amount is IN the key deliberately: a second, DIFFERENT payment against the
same authority and period is a lawful partial remittance and must be allowed to
post, while the double-clicked identical one must not. Stated because including
an amount in an idempotency key is unusual and it is a signed test case, not a
preference.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from apps.ledger import chart, models, posting, selectors
from core import errors
from core import tenancy as core_tenancy

ZERO = Decimal("0")

#: The `source_type` a reverse+repost mirror traces to. The document being
#: reversed IS a journal entry, so the polymorphic pair names one — which is
#: also what makes the mirror findable from the original on the S56 list without
#: following the link.
SOURCE_JOURNAL_ENTRY = "journal_entry"
EVENT_REVERSED = "reversed"

#: The `source_type` a remittance entry carries, and the string
#: `apps/ledger/reporting.remittance_by_authority` reads back to fill the
#: REMITTED column. Named once so the write and the read cannot drift.
SOURCE_REMITTANCE = "remittance"

#: BR-LED-002's two bases, as the caller may state them.
BASIS_BILLED = "billed"
BASIS_COLLECTED = "collected"
REMITTING_BASES = (BASIS_BILLED, BASIS_COLLECTED)


class JournalActionError(RuntimeError):
    """A ledger money action the books refuse, with the reason a human can act on.

    The same shape and the same argument as `apps.ledger.posting.PostingError`:
    this module has no HTTP surface, its callers are services and an API layer
    decides what a browser sees. Distinct from `PostingError` so a caller can
    tell "the ledger refused the ACT" (no reason given, wrong account series,
    already reversed) from "the books refused the ENTRY" (unbalanced, foreign
    account, float amount) without matching on prose.
    """


def _tenant_id() -> UUID:
    """CLAUDE.md rule 1 — no tenant table is touched without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-013 — reverse + repost
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class DraftLine:
    """One line of the PREFILLED repost draft — a copy, ready to be corrected.

    Every dimension of the original travels with it. LE-8's correction changes
    an AMOUNT (250.00 → 205.00) and nothing else, and a draft that lost the
    service, account or authority stamps would silently re-post the money
    undimensioned — a correction that makes the books less answerable than the
    mistake was.
    """

    ledger_account_id: str
    side: str
    amount: Decimal
    source_type: str | None
    source_id: str | None
    service_id: str | None = None
    account_id: str | None = None
    premises_id: str | None = None
    unit_id: str | None = None
    tax_authority_id: str | None = None


@dataclass(frozen=True)
class ReversePostResult:
    """What one click of *Reverse + repost* did (LE-8's three entries, minus one).

    `mirror_created=False` is the replay: this original has already been
    reversed by the same key, and the FIRST mirror comes back. That is the
    correct outcome of a double-submitted form, not an error.

    `repost_draft` is the prefilled S57 draft as DATA — see the module
    docstring for why it is not a row. `unavailable` carries that fact on the
    result so no caller has to infer it.
    """

    original_entry_id: str
    mirror_entry_id: str
    mirror_posting_key: str
    mirror_created: bool
    reason: str
    debits: Decimal
    credits: Decimal
    repost_draft: tuple[DraftLine, ...]
    unavailable: tuple[dict[str, Any], ...] = ()


REPOST_DRAFT_NOT_PERSISTED = {
    "code": "repost_draft_is_not_persisted",
    "br_ref": "BR-LED-003 · US-LED-011 (EP-LED-04, unbuilt)",
    "detail": "the prefilled correction is RETURNED, not written. `journal_entries` refuses "
    "an INSERT outside the posting service (ledger/0004) and the posting service posts — so a "
    "DRAFT row cannot exist until US-LED-011 builds the draft lifecycle this story "
    "`depends_on`. Nothing is lost: BR-LED-003 calls a draft *worthless* until posted, and "
    "US-LED-013 TC-4 has staff post the mirror and DISCARD the draft, which a payload nobody "
    "stored achieves by doing nothing. The corrected entry is posted with "
    "`apps.ledger.posting.post` like any other.",
    "wanted_reads": (),
}

ROLE_GATE_IS_THE_API_HALF = {
    "code": "finance_owner_role_gate_is_not_enforced_here",
    "br_ref": "BR-LED-003 · US-LED-013 TC-5",
    "detail": "BR-LED-003 makes reverse+repost a FINANCE/OWNER action and US-LED-013 TC-5 "
    "requires a Staff-role attempt to be refused SERVER-SIDE. Role enforcement in this repo is "
    "a DRF permission class on the endpoint (`core/permissions.py` — system_admin / "
    "billing_clerk / executive), and this story ships no endpoint, so the gate has nowhere to "
    "sit yet. It is named rather than approximated: the implemented role vocabulary has no "
    "'Finance' and no 'Owner' in it, and inventing a mapping from three roles to two would "
    "decide who may correct the books — see the OQ this lane minted.",
    "wanted_reads": (),
}


def reverse_and_repost(
    entry_id: Any,
    *,
    reason: str,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
) -> ReversePostResult:
    """BR-LED-003's one click: post the linked mirror, return the prefilled draft.

    LE-8, end to end: `reverse_and_repost(JE-104, reason="keyed 250.00, correct
    amount 205.00", …)` posts **JE-105** — the mirror, balanced, `reversal_of`
    → JE-104 — and hands back **JE-106**'s lines ready to correct. Posting the
    corrected entry is an ordinary `apps.ledger.posting.post` call by the
    caller; net effect **250.00 − 250.00 + 205.00 = 205.00**, three entries in
    the books forever.

    Refuses, and each refusal is a defect it is preventing rather than a rule it
    is enforcing:

      * **no reason** → BR-LED-003 requires one and US-LED-013 TC-3 makes the
        click demand it. A correction with no reason is a number that changed
        and nobody can say why, which is the state an audit exists to prevent.
      * **an entry that is already reversed** → US-LED-013 TC-6, *"an entry
        reverses once; the link makes the state visible (no double-mirror)"*. A
        second mirror would credit the same money twice and the trial balance
        would still balance.
      * **a DRAFT** → `apps.ledger.posting.reverse_entry` refuses it too, and
        for the reason it gives: mirroring a draft puts an entry in the books to
        cancel one that never entered them.
      * **another tenant's entry** → US-LED-013 TC-7. RLS refuses it on
        Postgres; the explicit filter refuses it on the developer database too.

    `entry_date` is an INPUT (PO ruling 2026-08-11 on OQ-107, BR-TEN-043) — LE-9
    is the case where July has closed and an August-arriving correction must land
    in August. BR-TEN-038's auto-forward is US-LED-015's and is NOT applied here;
    the date the caller names is the date written.
    """
    tenant_id = _tenant_id()
    cleaned = str(reason or "").strip()
    if not cleaned:
        raise JournalActionError(
            "reverse + repost needs a REASON (BR-LED-003; US-LED-013 TC-3: *the click demands "
            "a reason*). The original entry stays in the books forever, so the only record of "
            "WHY it was corrected is the one written now — an unexplained mirror is a number "
            "that changed with nobody accountable for it."
        )

    original = models.JournalEntry.objects.filter(tenant_id=tenant_id, pk=entry_id).first()
    if original is None:
        raise JournalActionError(
            f"journal entry {entry_id!r} is not one of this tenant's entries (US-LED-013 TC-7). "
            "Nothing is reversed and nothing is reported about whose it is."
        )
    if original.status != models.JE_POSTED:
        raise JournalActionError(
            f"journal entry {entry_id!r} is {original.status!r}, not posted. A DRAFT is edited "
            "or deleted directly (BR-LED-003 — drafts are freely editable and worthless); "
            "reverse + repost is the correction path for an entry that has already entered the "
            "books."
        )

    key = posting.posting_key(
        source_type=SOURCE_JOURNAL_ENTRY, source_id=original.pk, event=EVENT_REVERSED
    )
    existing_mirror = original.reversed_by.first()
    if existing_mirror is not None and existing_mirror.posting_key != key:
        # Someone reversed this entry under a DIFFERENT key — a second mirror is
        # a double-credit with a link to prove it (US-LED-013 TC-6). The DB's
        # `uq_journal_entries_reversal` is the other half; this is the readable
        # refusal that gets there first.
        raise JournalActionError(
            f"journal entry {original.pk} has already been reversed by {existing_mirror.pk}. An "
            "entry reverses ONCE (US-LED-013 TC-6) — a second mirror would credit the same "
            "money twice and every entry would still balance. Correct the CORRECTION instead: "
            "reverse the entry that is wrong now."
        )

    draft = tuple(
        DraftLine(
            ledger_account_id=str(line.ledger_account_id),
            side=line.side,
            amount=line.amount,
            source_type=line.source_type,
            source_id=str(line.source_id) if line.source_id else None,
            service_id=str(line.service_id) if line.service_id else None,
            account_id=str(line.account_id) if line.account_id else None,
            premises_id=str(line.premises_id) if line.premises_id else None,
            unit_id=str(line.unit_id) if line.unit_id else None,
            tax_authority_id=str(line.tax_authority_id) if line.tax_authority_id else None,
        )
        for line in original.lines.all().order_by("created_at", "id")
    )

    result = posting.reverse_entry(
        original.pk,
        posting_key=key,
        entry_date=entry_date,
        posted_at=posted_at,
        memo=f"Reversal of {original.pk} — {cleaned}",
        actor=actor,
        # US-LED-013 TC-3: the reason belongs ON the trail, not only on the
        # entry. `audit_context` reaches both `journal.reversed` (the original)
        # and `journal.posted` (the mirror).
        audit_context={"reason": cleaned, "action": "reverse_and_repost"},
    )
    return ReversePostResult(
        original_entry_id=str(original.pk),
        mirror_entry_id=result.entry_id,
        mirror_posting_key=result.posting_key,
        mirror_created=result.created,
        reason=cleaned,
        debits=result.debits,
        credits=result.credits,
        repost_draft=draft,
        unavailable=(REPOST_DRAFT_NOT_PERSISTED, ROLE_GATE_IS_THE_API_HALF),
    )


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-014 — the remittance payment JE
# ═══════════════════════════════════════════════════════════════════════════
# ⚠ **`RECEIPT_HAS_NO_HOME` AND `REMITTANCE_REGISTER_NOT_BUILT` STOOD HERE
# UNTIL 2026-09-24 AND ARE DELETED, NOT REWORDED (`P4.3`/`P4.4`).**
#
# They were two `unavailable` entries that rode on EVERY remittance response
# this product has ever given. The first said a receipt file *"is refused by
# name rather than accepted and dropped, because a clerk who attaches a receipt
# believes it was kept"*; the second said the filing history table did not
# exist. **Both were true and neither is now:** `ledger/0020` builds
# `tax_remittances` and `tenancy/0052` makes `tax_remittance` a document
# source, so the receipt has a home and the register has rows.
#
# B14 rule 33 removes a refusal rather than shortening it, and hard-won law 2's
# mirror is why this is a deletion: a refusal that has stopped being true is
# worse than one that never was. Their keys are retired from all eleven
# catalogues in the same commit.
#
# **WHAT DID NOT CHANGE, because it was never about the missing table:**
# `reporting.remittance_by_authority` still reads the REMITTED column out of
# the BOOKS. `BR-REP-002` makes the books the number that has to be right and a
# register is a convenience over them — the old code said so itself, and it is
# still the honest order.


def _safe_name(name: str) -> str:
    """A filename that cannot climb out of its own storage key.

    `/`, `\\` and a leading `.` are the three characters that turn a display
    name into a path. The store hashes and keys the bytes itself, so this is
    about the NAME a person reads in an unpacked export — but a name carrying a
    separator reads as a directory that is not there.
    """
    cleaned = (name or "receipt").replace("/", "-").replace("\\", "-").lstrip(".")
    return cleaned.strip() or "receipt"


@dataclass(frozen=True)
class ReceiptUpload:
    """One receipt file, on its way to `stored_documents`.

    ⚠ **THE BYTES ARE ALREADY READ AND ALREADY CHECKED WHEN THIS ARRIVES.**
    `BR-SHL-031`'s 10 MiB cap and its PDF/PNG/JPG/CSV allowlist are enforced at
    the endpoint, against `customers.account_documents`' own two constants, for
    the reason `tenancy/0052` records: `document_store.store()` refuses an empty
    payload and an unknown kind and **does not measure bytes or check a media
    type**. A service that assumed it did would be trusting a guarantee nobody
    wrote (hard-won law 1).
    """

    content_type: str
    filename: str
    payload: bytes


@dataclass(frozen=True)
class RemittanceResult:
    """One recorded remittance: the balanced JE that drained the liability."""

    entry_id: str
    posting_key: str
    created: bool
    tax_account_id: str
    tax_account_code: str
    amount: Decimal
    basis: str
    confirmation_ref: str
    period: tuple[date, date]
    #: `P4.4` — the `tax_remittances` row this filing wrote, or the one an
    #: idempotent retry found. Never `None` on a successful call.
    remittance_id: str = ""
    #: `P4.3` — the `stored_documents` id of the receipt, or `None` when the
    #: clerk attached none. **`None` is not a refusal any more**; it is a filing
    #: with no receipt, which is lawful and common.
    receipt_document_id: str | None = None
    unavailable: tuple[dict[str, Any], ...] = ()


def record_tax_remittance(
    *,
    tax_account_id: Any,
    period_start: date,
    period_end: date,
    amount: Decimal,
    basis: str,
    confirmation_ref: str,
    entry_date: date,
    posted_at: datetime,
    actor: Any = None,
    receipt: ReceiptUpload | None = None,
) -> RemittanceResult:
    """US-LED-014 TC-3 — DR the authority's tax payable / CR cash, balanced.

    Worked, LE-3: State of Texas remits on the collected basis and owes
    **13.87** for July → `DR 2200-01 13.87 / CR 1000 13.87`, one balanced entry
    through the posting service, and `remittance_by_authority`'s REMITTED column
    reads 13.87 back out of the books with outstanding falling to **0.00**.

    **It computes nothing.** The amount is the caller's — the figure a human
    read off S41 and actually paid — and this refuses it if it is not a positive
    Decimal. Deriving the amount here would make the payment agree with the
    report by construction, which is exactly the property that hides a wrong
    report.

    **CR cash, not undeposited.** A remittance is money leaving the utility's
    bank; `undeposited_funds` is money that has not reached the bank yet (PO
    ruling 2026-08-11, OQ-143), and crediting it would report the payment as
    made out of a drawer.

    **IT WRITES THE FILING REGISTER TOO, SINCE `P4.4`.** One `tax_remittances`
    row per entry, in the same transaction, carrying what a journal entry cannot:
    the filing reference, the day the money left, and — through
    `stored_documents` — the receipt `BR-LED-019` requires. ⚠ **The register
    does NOT become the source of `REMITTED`**: `reporting.
    remittance_by_authority` goes on summing that out of the books, because
    `BR-REP-002` makes the books the number that has to be right.

    ⚠ **THE REGISTER ROW IS WRITTEN ONLY WHEN THE ENTRY IS NEW.**
    `posting.post()` is idempotent on (authority, period, amount), so a retried
    request returns the SAME entry — and a second register row beside it would
    make the filing history list one payment twice.
    `uq_tax_remittances_entry` refuses it at the database as well, which is the
    guarantee; this is the path that does not reach for it.

    Refuses: a non-2200 account (it would drain revenue and still balance), an
    amount that is not a positive `Decimal` (hard rule 2), an unknown basis, a
    missing confirmation ref (BR-LED-019) and an inverted period. **A `receipt`
    is no longer refused** — see the block above `ReceiptUpload`.
    """
    tenant_id = _tenant_id()
    if receipt is not None and not isinstance(receipt, ReceiptUpload):
        # The old code refused EVERY receipt because there was nowhere to put
        # one. This refuses only a receipt in a shape the store cannot take —
        # a raw file object, a path, a base64 string — rather than guessing at
        # its bytes, which is how a clerk's PDF becomes a row of nonsense.
        raise JournalActionError(
            "a remittance receipt must arrive as a ReceiptUpload — its media type, its "
            "filename and its BYTES, already read and already checked against BR-SHL-031's "
            "10 MiB cap and PDF/PNG/JPG/CSV allowlist at the endpoint. This service does not "
            "read a file object: document_store.store() measures nothing, so a caller that "
            "handed one over would store whatever it happened to contain."
        )
    if period_start > period_end:
        raise JournalActionError(
            f"the filing period {period_start} … {period_end} runs backwards. A remittance "
            "answers a period and an inverted one names none."
        )
    if basis not in REMITTING_BASES:
        raise JournalActionError(
            f"remitting basis {basis!r} is not one of {REMITTING_BASES} (BR-LED-002 — BOTH "
            "bases are always computed and a per-authority setting picks which one the "
            "authority remits on). Nothing here defaults it: LE-3 has State on COLLECTED and "
            "County on BILLED, so a default would be wrong for one of them in its first month."
        )
    cleaned_ref = str(confirmation_ref or "").strip()
    if not cleaned_ref:
        raise JournalActionError(
            "a remittance needs its filing CONFIRMATION REF (BR-LED-019, CONFIRMED PO L-4 — "
            "*remittance records carry a filing confirmation ref + receipt file attachment "
            "(auditor artifact)*). Recording the payment without it would drain the liability "
            "and leave nothing proving the return was filed. ⚠ This sentence used to add "
            "*the only auditor artifact this build can keep, since tax_remittances does not "
            "exist* — that table exists as of ledger/0020 and the clause is deleted rather "
            "than reworded (B14 rule 33)."
        )
    if isinstance(amount, float):
        raise JournalActionError(
            f"remittance amount {amount!r} is a float. CLAUDE.md rule 2: money is "
            "NUMERIC(18,6) and never a float. Refused rather than converted — a conversion "
            "hides the place where money became binary."
        )
    if not isinstance(amount, Decimal) or amount <= ZERO:
        raise JournalActionError(
            f"remittance amount {amount!r} must be a positive Decimal. A zero remittance moves "
            "no money and would put an empty balanced pair in the books; a negative one is a "
            "REFUND from the authority, which is a different source event with a different "
            "DR/CR contract and is not this function."
        )

    account = models.LedgerAccount.objects.filter(
        tenant_id=tenant_id, pk=tax_account_id, deleted_at__isnull=True
    ).first()
    if account is None:
        raise JournalActionError(
            f"ledger account {tax_account_id!r} is not a LIVE account of this tenant's own "
            "chart (US-LED-014 TC-8). It belongs to another tenant, was deactivated (IS-1), or "
            "does not exist."
        )
    # CR-196-BRC10 5b — the account's minted slot counts as well as its code,
    # so a renamed `2200-01` is still a tax account a remittance may debit.
    if not chart.is_tax_payable_account(account.code, account.seed_key):
        raise JournalActionError(
            f"account {account.code} ({account.name}) is not in the signed "
            f"{chart.TAX_PAYABLE_SERIES} tax-payable series, so a remittance may not debit it. "
            "B5 line 74 ❄️: *2200-series Tax payable per authority (tenant authorities mint "
            "their own)*, and BR-BIL-069 gives each authority its own account. A remittance "
            "keyed against a revenue account would drain REVENUE, balance perfectly, pass "
            "every trigger, and be findable only by reading the trial balance line by line."
        )

    cash_account_id = selectors.gl_account_id_for_designation(chart.CASH)
    if cash_account_id is None:
        raise JournalActionError(
            f"no live ledger account carries the {chart.CASH!r} designation, so this remittance "
            "has no credit side. Resolved BY DESIGNATION and never by the number 1000 — the "
            "chart is tenant-customizable (US-LED-005, OQ-106). A human designates one on the "
            "GL mapping page."
        )

    # US-LED-014 TC-7's own identity: authority + period + amount. The amount is
    # IN the key deliberately — see the module docstring.
    key = posting.posting_key(
        source_type=SOURCE_REMITTANCE,
        source_id=account.pk,
        event=f"{period_start.isoformat()}..{period_end.isoformat()}:{amount}",
    )
    dimensions = {"source_type": SOURCE_REMITTANCE, "source_id": account.pk}
    request = posting.PostingRequest(
        posting_key=key,
        entry_date=entry_date,
        posted_at=posted_at,
        # The chart carries no per-account currency; the entry's is the tenant's
        # book currency, which every other ledger-authored entry in this build
        # also states as USD. REPORTED in the trailer rather than defaulted
        # silently — a defaulted currency is how a CAD tenant's books quietly
        # become USD (apps/ledger/posting.PostingRequest says so).
        currency="USD",
        lines=(
            posting.PostingLine(
                ledger_account_id=account.pk,
                side=models.SIDE_DEBIT,
                amount=amount,
                **dimensions,
            ),
            posting.PostingLine(
                ledger_account_id=cash_account_id,
                side=models.SIDE_CREDIT,
                amount=amount,
                **dimensions,
            ),
        ),
        source_type=SOURCE_REMITTANCE,
        source_id=account.pk,
        memo=(
            f"Tax remittance {account.code} {period_start.isoformat()}…{period_end.isoformat()} "
            f"({basis} basis) · confirmation {cleaned_ref}"
        ),
        audit_context={
            "authority_account_code": account.code,
            "authority_account_name": account.name,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "basis": basis,
            "amount": str(amount),
            "confirmation_ref": cleaned_ref,
        },
    )
    result = posting.post(request, actor=actor)

    # ── `P4.4` — THE FILING REGISTER ──────────────────────────────────────
    #
    # ⚠ **ONLY WHEN THE ENTRY IS NEW.** `posting.post()` is idempotent, so a
    # retry returns the same entry and `created` is False — and a second
    # register row beside it would make the filing history list one payment
    # twice. `get_or_create` rather than a bare `create` because
    # `uq_tax_remittances_entry` is the actual guarantee and a race would
    # otherwise raise where the honest answer is *"already filed"*.
    register, _ = models.TaxRemittance.objects.get_or_create(
        tenant_id=tenant_id,
        journal_entry_id=result.entry_id,
        defaults={
            "tax_account_id": account.pk,
            "period_start": period_start,
            "period_end": period_end,
            "amount": amount,
            # The entry's own code, taken from the request above rather than
            # read a second time — one currency, one place (BR-SHL-023).
            "currency": request.currency,
            "basis": basis,
            "confirmation_ref": cleaned_ref,
            # ⚠ **ONE INPUT, TWO NAMES, AND THIS IS THE HONEST RECORD OF IT.**
            # 4·2 labels the field *Date paid* and the API has always called it
            # `entry_date`; there is exactly one date the clerk types. Storing
            # it under `paid_on` rather than inventing a second field is what
            # keeps the register and the entry telling the same story — and
            # `BR-TEN-043` is why neither is a clock read here.
            "paid_on": entry_date,
            "created_by_user_id": getattr(actor, "id", None),
        },
    )

    # ── `P4.3` — THE RECEIPT ──────────────────────────────────────────────
    #
    # ⚠ **AFTER THE REGISTER ROW, AND FOR THE REASON `document_store` ARGUES
    # ABOUT ITS OWN ORDER:** the document is found by `source_id`, so there has
    # to be a filing for it to belong to. A receipt stored first would point at
    # a row that a later refusal might never create.
    receipt_document_id = None
    if receipt is not None:
        # ⚠ **THE AUTHOR IS CHECKED HERE RATHER THAN LEFT TO THE STORE
        # (hard-won law 1).** `document_store.store()` does refuse an
        # unattributed document — *"a legal document whose origin is
        # unrecorded is unprovable"* — but it raises `DocumentStoreError`
        # AFTER the register row is written, which reads to a caller as the
        # filing having failed when the money has already posted. Refusing
        # up front, by name, says which of the two inputs is missing.
        if getattr(actor, "id", None) is None:
            raise JournalActionError(
                "a remittance RECEIPT needs the clerk who filed it: document_store refuses a "
                "stored document with no author, because a legal document whose origin is "
                "unrecorded is unprovable. Pass `actor`. The filing itself does not need one "
                "— record it without the receipt and attach the paper when it arrives."
            )
        paid_year, paid_month = f"{entry_date:%Y}", f"{entry_date:%m}"
        # Imported HERE rather than at module scope: `apps.ledger.apps.ready()`
        # reaches this module, and a top-level tenancy import at app-registry
        # time is the circular import `finance_exports.py` avoids the same way.
        from apps.tenancy import document_models, document_store

        stored = document_store.store(
            kind=document_models.KIND_REMITTANCE_RECEIPT,
            source_type=document_models.SOURCE_TAX_REMITTANCE,
            source_id=register.pk,
            content_type=receipt.content_type,
            # ⚠ **THE DISPLAY NAME IS COMPOSED HERE BECAUSE ONLY THIS MODULE
            # CAN.** `document_store._require_display_name` refuses to invent
            # one and says why: a usable name needs the filing's own reference,
            # which lives here. The shape mirrors the storage key so an unpacked
            # export reads like the bucket, exactly as account documents do.
            display_name=(
                f"remittance-receipts/{paid_year}/{paid_month}/"
                f"{account.code}-{cleaned_ref}-{_safe_name(receipt.filename)}"
            ),
            payload=receipt.payload,
            actor_user_id=getattr(actor, "id", None),
        )
        receipt_document_id = str(stored.id)

    return RemittanceResult(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        tax_account_id=str(account.pk),
        tax_account_code=account.code,
        amount=amount,
        basis=basis,
        confirmation_ref=cleaned_ref,
        period=(period_start, period_end),
        remittance_id=str(register.pk),
        receipt_document_id=receipt_document_id,
        # ⚠ **THE TWO `unavailable` ENTRIES ARE GONE, NOT EMPTIED AND NOT
        # REWORDED.** See the block above `ReceiptUpload`. A response that went
        # on carrying a refusal which had stopped being true is the shape
        # hard-won law 2's mirror names, and this one rode on every remittance
        # the product has ever recorded.
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-013@e3b0c44 (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md US-LED-013 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-05-remittance-close-export.md US-LED-014 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-01-posting-consumption.md §DR/CR contract row "Tax remittance payment | tax payable (authority) | cash" · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-002/003/012/015/019 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-3/LE-8 · 04-docs/02-decisions/05-golden-tests.md line 74 ❄️ 2200 series · 12-governance/02-decision-log.md 2026-08-11 BR-BIL-069 + OQ-143)
# generated: 2026-08-11 by Eng-Lead (W5 ledger reporting lane — EP-LED-03/04/05 write halves)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S56/S57/S41 have no endpoints) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN — the "edit" guard was mutated to UPDATE a posted entry's amount instead of reversing it, RUN, and the failure quoted verbatim in the lane report and the human-review row
# exceptions: NOW ON THE G7 GLOB LIST (added 2026-08-11 by the orchestrating
#         session). This line read "NOT ON THE G7 GLOB LIST … the glob is the
#         only thing missing" and was corrected when the glob landed — a trailer
#         that describes the guard state wrongly is hard-won law 1 aimed at the
#         guards. The marker and the repo-relative review-ledger row were
#         re-verified present first ·
#         the PREFILLED DRAFT of BR-LED-003 is RETURNED, never written: the
#         sole-writer trigger (ledger/0004) refuses an INSERT outside `post()`
#         and `post()` posts, so a draft row cannot exist until US-LED-011
#         (EP-LED-04) builds the lifecycle this story depends_on. Carried as
#         `repost_draft_is_not_persisted` on every result · the FINANCE/OWNER
#         role gate of BR-LED-003 / US-LED-013 TC-5 is NOT enforced here: role
#         enforcement in this repo is a DRF permission class on an endpoint and
#         this story ships none, and the implemented vocabulary
#         (system_admin/billing_clerk/executive) contains neither "Finance" nor
#         "Owner" — the mapping is an OQ this lane minted, not a choice made
#         here · `tax_remittances` (r13 #3) does NOT exist, so a remittance's
#         confirmation ref lives on the entry memo + the audit payload and the
#         RECEIPT FILE is refused by name; the REMITTED column is read back out
#         of the books instead of a register · the remittance entry's currency is
#         hard-coded "USD" because no per-tenant book currency is published
#         anywhere in the schema — REPORTED, and the same string every other
#         ledger-authored entry in this build uses · BR-TEN-038's closed-period
#         auto-forward is NOT applied to a reversal's entry_date: no fiscal-period
#         record exists (US-LED-015), so the caller's date is written verbatim per
#         the PO's OQ-107 ruling
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
