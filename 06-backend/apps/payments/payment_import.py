# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-2 — "Import a lockbox or CSV remittance file",
#           buildable now. Verbatim: *"A utility on a bank lockbox receives one
#           file a day carrying hundreds of cheques. Today every one is typed by
#           hand, and the story covering it has been a draft since W4."*
# Story:    US-PAY-003 (bulk payments in via the ratified staged pattern)
#           Screens: S35 (Lockbox modal) · S33 (batch filter + link back)
# Rules:    BR-PAY-023 (bulk = staged import: batch → per-row validation →
#           preview → commit; file+SHA-256 stamp; idempotency file+tags;
#           account-match heuristics FLAG FOR REVIEW, never auto-guess
#           silently) · BR-PAY-028 🔒 (file+tags key; mechanics Eng-Lead) ·
#           BR-PAY-033 (the posting date comes FROM FILE DATA at import) ·
#           BR-PAY-021 (posting date ≠ clearing date — always both) ·
#           BR-TEN-081 / OQ-153 (a typed date means midnight in the UTILITY's
#           own timezone) · BR-TEN-043 / gate G6 (the caller names the day) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 2 (money is Decimal) ·
#           rule 6 (idempotency) · rule 7 (audit) · hard-won law 14 (a failed
#           statement poisons the whole PostgreSQL transaction)
# Ruling:   PO 2026-08-11 — lateness is judged by the ACTUAL date the money
#           arrived, never the posting or import date (OQ-131 CLOSED, BR-PAY-033
#           won the contradiction and US-PAY-003 TC-3 is stamped SUPERSEDED).
#           PO 2026-08-12 — *"a receipt with no arrival date falls back to its
#           recorded date"*. **Both halves are settled and neither is re-asked
#           (law 13).**
# Tests:    06-backend/tests/test_cr059_cs2_payment_import.py
# Impacts:  apps/payments/lockbox.parse_remittance_file (the pure kernel this
#           drives) · apps/payments/services.record_payment (the ONE writer this
#           commit calls, once per matched row) · apps/payments/models
#           PaymentImportBatch/PaymentImportRow (payments/0021)
# ───────────────────────────────────────────────────────
"""The staged remittance import: upload → validate → preview → commit.

⚠ **CORRECTED 2026-09-30 (gate triage T6) — THE `human_owned.txt` SENTENCE BELOW IS
HISTORY, NOT THE CURRENT STATE.** This path was added to
`10-scripts/gates/human_owned.txt` by PO ruling 2026-09-30 (option A, commit
`dabb8a323`, with 51 others), so `G7` reads its markers now.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 this composes the file+tags idempotency
key for imported money and is the path that turns a bank file into hundreds of
payments. AI-authored 2026-09-03 under the PO ruling of 2026-08-09. **No glob in
`10-scripts/gates/human_owned.txt` matches this file**; editing that list is a
process event and the PO's call, not a lane's (`cheques.py` and
`allocation_release.py` each record the identical finding). REPORTED.

════════════════════════════════════════════════════════════════════════════
CS-2's TWO NEW RULES, AND THE SECOND IS THE ONE THAT WILL BE ERODED
════════════════════════════════════════════════════════════════════════════
**1 · NOTHING IS APPLIED ON UPLOAD.** *"A remittance import is staged: upload →
validate → preview → commit; nothing is applied on upload"* — the same shape the
meter-read import already uses. `stage_import` writes two staging tables and no
payment. A clerk who uploads the wrong file has moved no customer's balance.

**2 · A ROW THAT CANNOT BE MATCHED WITH CERTAINTY IS LEFT FOR A PERSON, AND A
NAME-AND-AMOUNT HEURISTIC NEVER COMMITS ON ITS OWN.**

⚠ **WHY THIS SECOND ONE NEEDS ITS REASON WRITTEN DOWN RATHER THAN JUST ITS
BEHAVIOUR.** It looks like timidity. It is not, and the next lane to meet a
utility with four hundred review rows a day will be told, reasonably, that
"Ann Ross · $292.87 matched exactly one account, just post it." Here is what
that costs when it is wrong: the money lands on a DIFFERENT customer's account,
which pays down THEIR bill, which stops THEIR collection ladder, while the
customer who actually paid is chased for arrears they settled. Two customers are
wrong, both silently, and the correction is a reversal on one account and a new
payment on the other — hard rule 4 means neither can simply be edited away.

A name is not an identifier. Two households called Ross on one street is
ordinary; a payer name typed by a bank's data-entry contractor is not even
reliably the customer's. **So `name_amount` sets the account as a SUGGESTION,
marks the row `review`, and the commit skips it.** A person confirms it through
`assign_row_account`, which records who decided and lands the row as `manual`.

════════════════════════════════════════════════════════════════════════════
THE MATCH LADDER, IN THE EPIC'S OWN PRIORITY ORDER
════════════════════════════════════════════════════════════════════════════
US-PAY-003 §5: *"account match by account # → invoice # → name+amount heuristic
FLAGGED FOR REVIEW — never auto-guessed silently."*

    account #   the customer quoting OUR number, or a legacy reference this
                utility itself loaded. The strongest statement available.
                → clean
    invoice #   the customer quoting a bill WE issued. Equally specific, and it
                also tells us which bill they meant.                → clean
    name+amount a GUESS.                                            → review
    nothing     also review, not error — an unmatched cheque is WORK, not a
                fault. The money is real and somebody has to place it.

**`error` is reserved for a row that could not be READ** — no amount, an amount
that is not a number, a date the kernel cannot parse. That distinction is the
one the preview counts rest on, and a screen that conflates them tells a clerk
that four hundred perfectly good cheques are broken.

════════════════════════════════════════════════════════════════════════════
DATES: THE FILE'S, THEN THE RECORDED DAY — BOTH HALVES RULED, NEITHER GUESSED
════════════════════════════════════════════════════════════════════════════
BR-PAY-033: *"imports default it from file data where present"* — and that rule
WON the 2026-08-11 contradiction against US-PAY-003 TC-3, which had taken the
posting date at import to be the commit moment. The PO ruled the ACTUAL arrival
date authoritative. Lateness is judged on it (BR-BIL-071), so getting this wrong
charges a late fee to somebody who paid on time.

Where a row carries no date at all, the PO ruled the following day: *"a receipt
with no arrival date falls back to its recorded date"*, worked as *"entered 20
Aug against a bill due 22 Aug → no fee; entered 25 Aug → still overdue, so the
fallback forgives nothing."* **The fallback forgives nothing** — it is the
recorded day, not a generous one.

`recorded_on` is the CALLER's business day (BR-TEN-043, gate G6). No clock is
read here. A file date becomes a moment at midnight in the UTILITY's own
timezone, which is BR-TEN-081 as closed by OQ-153 — a Houston clerk's *22
August* is not UTC's.

════════════════════════════════════════════════════════════════════════════
⚠ THE COMMIT LOOP USES A SAVEPOINT PER ROW AND THAT IS THE ONLY OPTION
════════════════════════════════════════════════════════════════════════════
CLAUDE.md hard-won law 14, in full force here: this is precisely the
`try: … except IntegrityError: continue` shape, because BR-PAY-023 requires
*"per-row errors skip with a report"*.

**On PostgreSQL a plain try/except does not work.** Once any statement errors
inside a transaction the transaction is ABORTED; every later query raises
`InFailedSqlTransaction` and the whole batch is lost at COMMIT — after
reporting success. A nested `transaction.atomic()` (a SAVEPOINT) is not the tidy
option, it is the ONLY option.

**And the suite cannot show you this.** `config/settings/test.py` hardcodes
in-memory SQLite, which has no aborted-transaction state, so the broken version
passes every test on every machine and fails the first time a real row is
refused in production. `test_cr059_cs2_payment_import.py` carries the
`@requires_postgres` cases that prove the skip on a live cluster.

**Do not "simplify" the nested atomic away.** That sentence is in the code as
well as here, at the loop itself, because this docstring is not what the next
lane will be reading when they do it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from django.db import DatabaseError, transaction

from apps.payments import lockbox, models, services, settings_seam
from apps.payments.exceptions import PaymentRuleError
from core import audit as core_audit
from core import tenancy as core_tenancy

#: Hard rule 7 — every money action writes `audit_log`. Three of them, because
#: staging, committing and discarding are three different things a person did.
AUDIT_STAGED = "payment.import_staged"
AUDIT_COMMITTED = "payment.import_committed"
AUDIT_DISCARDED = "payment.import_discarded"
AUDIT_ROW_ASSIGNED = "payment.import_row_assigned"

#: The customers and billing reads this needs, BY NAME. Payments never imports
#: another module (B1); an absent seam REFUSES rather than answering "no match",
#: because "no match" is a sentence about a customer's money.
CUSTOMERS_MODULE = "customers"
ACCOUNT_INDEX_READ = "account_import_index"
BILLING_MODULE = "billing"
INVOICE_QUERYSET_READ = "invoice_queryset"


@dataclass(frozen=True)
class StagedImport:
    """What `stage_import` wrote, and nothing about money."""

    batch_id: str
    rows: int
    duplicate_of: str | None = None
    problems: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class BatchPreview:
    """BR-PAY-023's preview: *"matched / needs review / errors"*."""

    batch_id: str
    status: str
    counts: dict[str, int]
    total_matched: Decimal
    problems: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class CommitResult:
    """What the commit did, and — as importantly — what it did NOT do."""

    batch_id: str
    committed: int
    skipped: int
    payment_ids: tuple[str, ...] = ()
    #: One entry per row that did not become a payment, each naming the row and
    #: why. BR-PAY-023's *"per-row errors skip with a report"* — this IS the
    #: report, and a row that skipped without one would be money nobody chases.
    skipped_rows: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    problems: tuple[dict[str, Any], ...] = ()


def _tenant_id() -> Any:
    """This request's tenant, or refuse (CLAUDE.md hard rule 1)."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        # The RULE is carried in `br_ref`, which is structured and reaches the
        # audit row; it stays out of the sentence, because an id in the words a
        # clerk reads is provenance rather than help (B14 rule 32, CR-016).
        raise PaymentRuleError(
            "no tenant is set on this connection, so an import cannot be staged against "
            "anybody's accounts. Nothing was written.",
            br_ref="BR-TEN-003",
        )
    return tenant_id


def _actor_user_id(actor: Any) -> Any:
    """The acting user's ID, from whatever shape the caller's `actor` is.

    ⚠ **`actor` IS NOT A `User`, AND ASSIGNING IT TO A USER FK RAISES.** Every
    service in this module takes an actor object that carries `id`, `pk`, `role`
    and a `user` — `core.audit.money_action` reads it exactly this way — so the
    FK is set by ID rather than by object. A `getattr(actor, "pk", None)` truth
    test passes on that namespace and then fails inside Django with
    `Cannot assign … must be a "User" instance`, which is why the ID is taken
    here once instead of at three call sites.
    """
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """A neighbour's published callable, resolved AT CALL TIME, or None.

    The seam shape every other file in this module uses (B1). An absence is
    None; what an absence MEANS is the caller's to decide, and here it means
    refuse — see `_account_index`.
    """
    from importlib import import_module

    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    fn = getattr(target, attribute, None)
    return fn if callable(fn) else None


def _account_index() -> dict[str, dict[str, Any]]:
    """Every account, keyed the way an import file references one (CR-046 C4).

    Published by customers precisely so an importer need not walk their ORM.
    **An unwired seam REFUSES rather than returning an empty index**, because an
    empty index answers "no account matched" for every row in the file — which
    is a sentence about four hundred customers' money, produced by a missing
    import.
    """
    read = _resolve(CUSTOMERS_MODULE, ACCOUNT_INDEX_READ)
    if not callable(read):
        raise PaymentRuleError(
            "apps.customers.selectors.account_import_index is not published, so this process "
            "cannot see accounts and would report every row in the file as unmatched. Refused "
            "rather than answered wrongly.",
            br_ref="BR-CUS-054",
        )
    return read()


def _invoice_index(numbers: set[str]) -> dict[str, dict[str, Any]]:
    """`{lowered invoice_no: {invoice_id, account_id}}` for the bills a file names.

    Read through billing's OWN published tenant-scoped queryset by name, the
    same resolution `billing_seam.invoice_numbers` uses in the other direction.
    Only the numbers the file actually mentions are looked up: a lockbox file
    naming six bills must not pull a utility's whole invoice table into memory.
    """
    if not numbers:
        return {}
    queryset = _resolve(BILLING_MODULE, INVOICE_QUERYSET_READ)
    if queryset is None:  # pragma: no cover - billing publishes it
        return {}
    # ⚠ **CASE, AND WHY THREE SPELLINGS RATHER THAN AN `iexact` OR AN OR-CHAIN.**
    # A bill number is OURS — minted by the tenant's own number series, upper
    # case — but the string in the file was typed or scanned by the bank's data
    # entry, and `bl-0141` is the same bill as `BL-0141` to everyone except an
    # `IN` clause. A four-hundred-row file cannot become four hundred `iexact`
    # clauses, and lowering the COLUMN would defeat its index. Three literal
    # spellings per reference is one indexed lookup and covers every case a
    # generated identifier can arrive in.
    wanted = {
        spelling for number in numbers for spelling in (number, number.upper(), number.lower())
    }
    rows = queryset().filter(invoice_no__in=sorted(wanted)).values("id", "invoice_no", "account_id")
    return {
        str(row["invoice_no"])
        .strip()
        .lower(): {
            "invoice_id": row["id"],
            "account_id": row["account_id"],
        }
        for row in rows
        if row["invoice_no"]
    }


def _moment(day: date) -> datetime:
    """A file's calendar date as a moment — midnight in the UTILITY's clock.

    BR-TEN-081 as closed by OQ-153, and DEF-094 is what happens when a write
    path anchors at UTC while the read path uses the tenant's zone: a Houston
    clerk's *22 August* is stored as `2026-08-22T00:00:00Z` and every screen
    shows *21 August*.
    """
    return datetime.combine(day, time.min, tzinfo=settings_seam.tenant_timezone())


# ══ 1 · UPLOAD ══════════════════════════════════════════════════════════════


def stage_import(
    actor: Any,
    *,
    file_name: str | None,
    payload: bytes,
    tags: dict[str, Any] | None = None,
    source_kind: str = "lockbox",
    uploaded_at: datetime | None = None,
) -> StagedImport:
    """Bytes → a staged batch and its rows. **No payment is created.**

    The file is stamped here and keyed here, before anything else happens:
    `file_hash` is a SHA-256 of the exact bytes, computed server-side and never
    accepted from a client, and `tag_fingerprint` is the 🔒 tag half
    (BR-PAY-028). A file whose (hash, tags) pair has already been COMMITTED is
    refused naming the batch that did it — OQ-044's closure, option b, which
    blocks the commit rather than the staging.

    ⚠ **A ROW THAT WILL NOT PARSE IS STILL STAGED**, carrying its reason. That
    is BR-PAY-023's *"per-row errors skip with a report"* reaching back to the
    parse: a file of four hundred cheques with one smudged date must not cost a
    clerk the other three hundred and ninety-nine.
    """
    tenant_id = _tenant_id()
    if not payload:
        raise PaymentRuleError(
            "no file was uploaded, so there is nothing to stage.", br_ref="BR-PAY-023"
        )

    file_hash = lockbox.file_sha256(payload)
    tag_values = dict(tags or {})
    fingerprint = lockbox.remittance_tag_fingerprint(tag_values)

    # 🔒 The file+tags check, BEFORE any write. The database constraint is the
    # structural half and catches a race; this is the half that can name WHO
    # imported it and WHEN, which is what OQ-044's closure asks a refusal to say.
    already = (
        models.PaymentImportBatch.objects.filter(
            tenant_id=tenant_id,
            file_hash=file_hash,
            tag_fingerprint=fingerprint,
            status=models.IMPORT_COMMITTED,
        )
        .order_by("committed_at")
        .first()
    )
    if already is not None:
        raise PaymentRuleError(
            f"this file has already been imported — batch {already.pk}, committed "
            f"{already.committed_at.isoformat() if already.committed_at else 'earlier'}. "
            "Importing it again would pay every customer in it twice. If the bank sent a "
            "corrected file, its bytes differ and it imports normally.",
            br_ref="BR-PAY-028",
        )

    try:
        parsed = lockbox.parse_remittance_file(payload)
    except lockbox.BankFileError as refusal:
        # The kernel is pure and raises a ValueError; this is the boundary that
        # turns it into the module's own refusal, the same way
        # `reconciliation.py` does for the statement half (DEF-047's lesson).
        raise PaymentRuleError(str(refusal), br_ref="BR-PAY-023") from refusal

    with transaction.atomic():
        batch = models.PaymentImportBatch.objects.create(
            tenant_id=tenant_id,
            source_kind=source_kind,
            file_name=file_name,
            file_hash=file_hash,
            tag_fingerprint=fingerprint,
            tags=_json_tags(tag_values),
            uploaded_by_id=_actor_user_id(actor),
            uploaded_at=uploaded_at,
            status=models.IMPORT_STAGED,
            counts={},
        )
        models.PaymentImportRow.objects.bulk_create(
            [
                models.PaymentImportRow(
                    tenant_id=tenant_id,
                    batch=batch,
                    row_no=line.line_no,
                    account_ref_raw=line.raw.get("account_ref") or None,
                    invoice_ref_raw=line.raw.get("invoice_ref") or None,
                    payer_name_raw=line.raw.get("payer_name") or None,
                    amount_raw=line.raw.get("amount") or None,
                    paid_on_raw=line.raw.get("paid_on") or None,
                    reference_raw=line.raw.get("reference") or None,
                    amount=line.amount,
                    paid_on=line.paid_on,
                    reference=line.reference,
                    match_method=models.MATCH_NONE,
                    match_state=models.ROW_ERROR if line.error else models.ROW_REVIEW,
                    match_detail=line.error,
                )
                for line in parsed
            ]
        )
        core_audit.money_action(
            actor,
            AUDIT_STAGED,
            "payment_import_batch",
            str(batch.pk),
            after={
                "file_name": file_name,
                "file_hash": file_hash,
                "tag_fingerprint": fingerprint,
                "tags": _json_tags(tag_values),
                "rows": len(parsed),
                # Stated on the trail, not only in a docstring: a reader of this
                # row must not have to know that staging moves no money.
                "payments_created": 0,
                "status": models.IMPORT_STAGED,
            },
        )
    return StagedImport(batch_id=str(batch.pk), rows=len(parsed))


def _json_tags(tags: dict[str, Any]) -> dict[str, Any]:
    """Tags as JSON-safe values, so the stored copy explains the fingerprint."""
    return {
        name: (value.isoformat() if isinstance(value, date) else value)
        for name, value in tags.items()
    }


# ══ 2 · VALIDATE (the match ladder) ═════════════════════════════════════════


def validate_batch(actor: Any, *, batch_id: Any) -> BatchPreview:
    """Run the match ladder over every staged row and recompute the counts.

    Idempotent: a clerk may re-run it after loading the missing accounts, and it
    re-reads every row from scratch. **It never moves a row a PERSON has already
    decided** — a `manual` match is somebody's judgement and re-validating must
    not quietly overwrite it with a heuristic.
    """
    tenant_id = _tenant_id()
    batch = _mutable_batch(tenant_id, batch_id)

    rows = list(
        models.PaymentImportRow.objects.filter(tenant_id=tenant_id, batch_id=batch.pk).order_by(
            "row_no"
        )
    )
    accounts = _account_index()
    wanted = {
        str(row.invoice_ref_raw).strip()
        for row in rows
        if row.invoice_ref_raw and row.match_method != models.MATCH_MANUAL
    }
    invoices = _invoice_index(wanted)

    with transaction.atomic():
        for row in rows:
            if row.match_method == models.MATCH_MANUAL:
                continue  # a person decided; a heuristic does not get to argue
            _match_row(row, accounts=accounts, invoices=invoices)
            row.save(
                update_fields=[
                    "account",
                    "invoice_id",
                    "match_method",
                    "match_state",
                    "match_detail",
                    "updated_at",
                ]
            )
        batch.counts = _counts(tenant_id, batch.pk)
        batch.status = models.IMPORT_VALIDATED
        batch.save(update_fields=["counts", "status", "updated_at"])

    return _preview(batch, tenant_id)


def _match_row(
    row: models.PaymentImportRow,
    *,
    accounts: dict[str, dict[str, Any]],
    invoices: dict[str, dict[str, Any]],
) -> None:
    """One row down the ladder. Mutates in place; the caller saves.

    ⚠ **THE ORDER IS THE EPIC'S AND IT IS NOT A PREFERENCE.** A file that names
    both an account and an invoice is answered by the ACCOUNT, because that is
    what the payer said the money is for; the invoice would narrow it to one
    bill and the allocator's own rules (BR-PAY-010) decide that better than a
    remittance line does.
    """
    if row.amount is None:
        # A parse failure already wrote `match_detail`; leave it exactly as the
        # kernel worded it rather than replacing it with a vaguer sentence.
        row.match_state = models.ROW_ERROR
        row.match_method = models.MATCH_NONE
        row.account = None
        row.invoice_id = None
        return

    reference = (row.account_ref_raw or "").strip().lower()
    if reference:
        hit = accounts.get(reference) or accounts.get(f"ext:{reference}")
        if hit is not None:
            row.account_id = hit["id"]
            row.invoice_id = None
            row.match_method = models.MATCH_ACCOUNT_NO
            row.match_state = models.ROW_CLEAN
            row.match_detail = f"account {hit['account_no'] or hit['id']}, named by the file"
            return
        # ⚠ NOT an error. The file named an account this utility does not have —
        # a legacy number, a typo, or an account not migrated yet. A person
        # decides; the money is real either way.
        row.account = None
        row.invoice_id = None
        row.match_method = models.MATCH_NONE
        row.match_state = models.ROW_REVIEW
        row.match_detail = (
            f"the file names account {row.account_ref_raw!r}, which is not on file here. "
            "Nothing is guessed from it."
        )
        return

    invoice_ref = (row.invoice_ref_raw or "").strip().lower()
    if invoice_ref:
        bill = invoices.get(invoice_ref)
        if bill is not None:
            row.account_id = bill["account_id"]
            row.invoice_id = bill["invoice_id"]
            row.match_method = models.MATCH_INVOICE_NO
            row.match_state = models.ROW_CLEAN
            row.match_detail = f"bill {row.invoice_ref_raw}, named by the file"
            return
        row.account = None
        row.invoice_id = None
        row.match_method = models.MATCH_NONE
        row.match_state = models.ROW_REVIEW
        row.match_detail = (
            f"the file names bill {row.invoice_ref_raw!r}, which is not on file here."
        )
        return

    # ⚠ **THE HEURISTIC. IT SUGGESTS AND IT NEVER COMMITS** — CS-2's second new
    # rule, and the reason is in the module docstring rather than here because
    # it needs the space: a name is not an identifier, and posting to the wrong
    # customer breaks two accounts silently and can only be undone by a
    # reversal on one and a new payment on the other.
    name = (row.payer_name_raw or "").strip().lower()
    if name:
        candidates = [
            entry
            for key, entry in accounts.items()
            if not key.startswith("ext:") and _payer_matches(entry, name)
        ]
        unique = {entry["id"]: entry for entry in candidates}
        if len(unique) == 1:
            only = next(iter(unique.values()))
            row.account_id = only["id"]
            row.invoice_id = None
            row.match_method = models.MATCH_NAME_AMOUNT
            row.match_state = models.ROW_REVIEW
            row.match_detail = (
                f"{row.payer_name_raw!r} looks like account {only['account_no'] or only['id']}. "
                "A name is not an identifier, so this is a SUGGESTION: confirm it before the "
                "money is posted."
            )
            return
        row.account = None
        row.invoice_id = None
        row.match_method = models.MATCH_NONE
        row.match_state = models.ROW_REVIEW
        row.match_detail = (
            f"{len(unique)} accounts could be {row.payer_name_raw!r}. Nothing is chosen for you."
            if unique
            else f"nothing on file matches the payer {row.payer_name_raw!r}."
        )
        return

    row.account = None
    row.invoice_id = None
    row.match_method = models.MATCH_NONE
    row.match_state = models.ROW_REVIEW
    row.match_detail = (
        "this row names no account, no bill and no payer, so there is nothing to match it on."
    )


def _payer_matches(entry: dict[str, Any], name: str) -> bool:
    """Does this index entry look like the payer the file named?

    ⚠ **DELIBERATELY BLUNT.** The index carries the account number and its
    external reference, not the customer's name, and payments may not go and
    fetch names from another module row by row for a four-hundred-line file.
    So this matches on the ONE thing the index does hold that a payer name can
    legitimately equal: a legacy external reference a utility loaded from its
    old system, where the "number" was often the household's name.

    That is a narrow net on purpose. A wider one would produce more suggestions,
    and a suggestion this module cannot justify is worse than none: every one of
    them is a row a person has to read and dismiss. When customers publishes a
    name index the way it publishes `account_import_index`, this is the one
    function that changes.
    """
    external = str(entry.get("external_ref") or "").strip().lower()
    return bool(external) and external == name


# ══ 2b · A PERSON DECIDES ═══════════════════════════════════════════════════


def assign_row_account(
    actor: Any, *, row_id: Any, account_id: Any, reason: str
) -> models.PaymentImportRow:
    """A person places a review row on an account. **This is the only way.**

    CS-2's second rule says a heuristic never commits on its own; this is the
    other side of that sentence — the door through which it eventually can. The
    row becomes `manual`/`clean`, which `validate_batch` will not overwrite, and
    the audit row records WHO decided, since after the commit the payment itself
    carries no trace of having been a guess.
    """
    tenant_id = _tenant_id()
    if not (reason or "").strip():
        raise PaymentRuleError(
            "placing a payment on an account by hand needs a reason. It is the only record of "
            "why this money was judged to be this customer's.",
            br_ref="BR-PAY-023",
        )
    row = models.PaymentImportRow.objects.filter(tenant_id=tenant_id, pk=row_id).first()
    if row is None:
        raise PaymentRuleError(
            f"import row {row_id} is not this tenant's. Nothing was changed.", br_ref="BR-TEN-003"
        )
    batch = _mutable_batch(tenant_id, row.batch_id)
    if row.amount is None:
        raise PaymentRuleError(
            "this row carries no readable amount, so there is no payment to place. Correct the "
            "file and import it again — its bytes will differ, so it is a new file.",
            br_ref="BR-PAY-023",
        )
    accounts = _account_index()
    known = {entry["id"] for entry in accounts.values()}
    if str(account_id) not in known:
        raise PaymentRuleError(
            f"account {account_id} is not one of this tenant's, so this row cannot be placed "
            "on it. Nothing was changed.",
            br_ref="BR-TEN-003",
        )

    before = {
        "account_id": str(row.account_id) if row.account_id else None,
        "match_method": row.match_method,
        "match_state": row.match_state,
    }
    with transaction.atomic():
        row.account_id = account_id
        row.match_method = models.MATCH_MANUAL
        row.match_state = models.ROW_CLEAN
        row.match_detail = f"placed by hand: {reason.strip()}"
        row.save(
            update_fields=["account", "match_method", "match_state", "match_detail", "updated_at"]
        )
        batch.counts = _counts(tenant_id, batch.pk)
        batch.save(update_fields=["counts", "updated_at"])
        core_audit.money_action(
            actor,
            AUDIT_ROW_ASSIGNED,
            "payment_import_row",
            str(row.pk),
            before=before,
            after={
                "account_id": str(account_id),
                "amount": str(row.amount),
                "match_method": models.MATCH_MANUAL,
                "match_state": models.ROW_CLEAN,
                "reason": reason.strip(),
                "payments_created": 0,
            },
        )
    return row


# ══ 3 · PREVIEW ═════════════════════════════════════════════════════════════


def preview_batch(*, batch_id: Any) -> BatchPreview:
    """BR-PAY-023's preview, read-only. Counts recomputed from the ROWS.

    ⚠ **NOT read off `batch.counts`.** A denormalised figure that disagrees with
    its rows is the shape this repo has been bitten by more than once, and the
    preview is the number a clerk decides on. The stored copy is a cache for a
    list screen; this is the answer.
    """
    tenant_id = _tenant_id()
    batch = models.PaymentImportBatch.objects.filter(tenant_id=tenant_id, pk=batch_id).first()
    if batch is None:
        raise PaymentRuleError(
            f"import batch {batch_id} is not this tenant's.", br_ref="BR-TEN-003"
        )
    return _preview(batch, tenant_id)


def _preview(batch: models.PaymentImportBatch, tenant_id: Any) -> BatchPreview:
    counts = _counts(tenant_id, batch.pk)
    total = Decimal("0")
    for amount in models.PaymentImportRow.objects.filter(
        tenant_id=tenant_id, batch_id=batch.pk, match_state=models.ROW_CLEAN
    ).values_list("amount", flat=True):
        total += amount or Decimal("0")
    return BatchPreview(
        batch_id=str(batch.pk), status=batch.status, counts=counts, total_matched=total
    )


def _counts(tenant_id: Any, batch_id: Any) -> dict[str, int]:
    """`{clean, review, error, committed, rows}` — every one from the rows."""
    rows = models.PaymentImportRow.objects.filter(tenant_id=tenant_id, batch_id=batch_id)
    tally = {state: 0 for state in models.ROW_STATES}
    committed = 0
    total = 0
    for state, payment_id in rows.values_list("match_state", "payment_id"):
        total += 1
        if state in tally:
            tally[state] += 1
        if payment_id is not None:
            committed += 1
    tally["committed"] = committed
    tally["rows"] = total
    return tally


# ══ 4 · COMMIT ══════════════════════════════════════════════════════════════


def commit_batch(actor: Any, *, batch_id: Any, recorded_on: date) -> CommitResult:
    """Post every CLEAN row as a payment. Review and error rows are skipped.

    `recorded_on` is the caller's business day (BR-TEN-043, gate G6) and it is
    the FALLBACK arrival date for a row whose file carried none — the PO's
    2026-08-12 ruling, which *"forgives nothing"*: it is the recorded day, not a
    kind one.

    ⚠ **THE SAVEPOINT PER ROW IS THE ONLY OPTION AND MUST NOT BE SIMPLIFIED
    AWAY** (CLAUDE.md hard-won law 14). On PostgreSQL, once any statement errors
    inside a transaction the transaction is ABORTED and every later query raises
    `InFailedSqlTransaction` — so a plain `try/except … continue` around
    `record_payment` loses the ENTIRE batch at COMMIT while reporting that four
    hundred payments were recorded. The default test suite is in-memory SQLite,
    which has no aborted-transaction state, so the broken version is green
    everywhere and fails first in production.

    ⚠ **AND THE OUTER `atomic()` IS NOT AROUND THE LOOP.** Each row commits on
    its own, because BR-PAY-023 says *"per-row errors skip with a report"* — a
    batch that rolls back wholesale on row 397 has thrown away 396 good
    payments, which is the behaviour the staged pattern exists to avoid.
    """
    tenant_id = _tenant_id()
    batch = _mutable_batch(tenant_id, batch_id)
    if batch.status != models.IMPORT_VALIDATED:
        raise PaymentRuleError(
            f"batch {batch.pk} is {batch.status!r} and has not been validated, so nothing is "
            "known about which rows may be posted. Validate it first — that is what the staged "
            "pattern is for.",
            br_ref="BR-PAY-023",
        )

    rows = list(
        models.PaymentImportRow.objects.filter(tenant_id=tenant_id, batch_id=batch.pk).order_by(
            "row_no"
        )
    )
    payment_ids: list[str] = []
    skipped: list[dict[str, Any]] = []

    for row in rows:
        if row.payment_id is not None:
            continue  # already posted by an earlier, partial commit
        if row.match_state != models.ROW_CLEAN or row.account_id is None:
            skipped.append(
                {
                    "row_no": row.row_no,
                    "state": row.match_state,
                    "detail": row.match_detail
                    or "not matched to an account with certainty, so no money was posted",
                }
            )
            continue
        try:
            # ⚠ **NESTED `atomic()` = SAVEPOINT. NOT TIDINESS — THE ONLY OPTION.**
            # Law 14: without it, one refused row aborts the whole PostgreSQL
            # transaction and every later row raises InFailedSqlTransaction,
            # losing the batch at COMMIT after reporting success. SQLite cannot
            # show you this. Do not flatten it.
            with transaction.atomic():
                recorded = _record_row(actor, batch=batch, row=row, recorded_on=recorded_on)
        except (PaymentRuleError, DatabaseError, ValueError) as refusal:
            # The savepoint has rolled back; this connection is usable again.
            # The reason is written OUTSIDE that savepoint, in its own, so the
            # report survives even though the payment did not.
            with transaction.atomic():
                row.commit_error = str(refusal)
                row.save(update_fields=["commit_error", "updated_at"])
            skipped.append({"row_no": row.row_no, "state": row.match_state, "detail": str(refusal)})
            continue
        payment_ids.append(recorded)

    with transaction.atomic():
        batch.counts = _counts(tenant_id, batch.pk)
        batch.status = models.IMPORT_COMMITTED
        batch.committed_at = _moment(recorded_on)
        batch.committed_by_id = _actor_user_id(actor)
        batch.save(update_fields=["counts", "status", "committed_at", "committed_by", "updated_at"])
        core_audit.money_action(
            actor,
            AUDIT_COMMITTED,
            "payment_import_batch",
            str(batch.pk),
            before={"status": models.IMPORT_VALIDATED},
            after={
                "status": models.IMPORT_COMMITTED,
                "file_name": batch.file_name,
                "file_hash": batch.file_hash,
                "payments_created": len(payment_ids),
                "rows_skipped": len(skipped),
                "recorded_on": recorded_on.isoformat(),
            },
        )

    return CommitResult(
        batch_id=str(batch.pk),
        committed=len(payment_ids),
        skipped=len(skipped),
        payment_ids=tuple(payment_ids),
        skipped_rows=tuple(skipped),
    )


def _record_row(
    actor: Any, *, batch: models.PaymentImportBatch, row: models.PaymentImportRow, recorded_on: date
) -> str:
    """One row → one payment, through the module's ONE writer.

    **BR-PAY-033's date, and the PO's fallback.** `posted_at` comes from the
    file's own arrival date where it carried one, because lateness is judged
    on the day the money actually arrived (PO 2026-08-11, BR-BIL-071) and a
    lockbox date IS the day the bank received it. Where the file carried none,
    it falls back to `recorded_on` — the PO's 2026-08-12 ruling, which
    *"forgives nothing"*. **No clearing date is passed:** a payment is `posted`
    at entry and clears only when its deposit batch is reconciled
    (`CR-186-BRC10`); this paragraph said otherwise until `DEF-PAY-10696`.

    **The tender is `lockbox`, by code** (`DEF-PAY-10696`, LBX-06): no method
    was passed before 2026-10-30 and every imported payment carried a blank one.

    `idempotency_reference` is `<batch id>:<row no>` under `source="import"`, so
    a batch committed twice — a retry, a crash between rows — records each row
    once. That is CLAUDE.md rule 6 reaching per ROW, underneath the file+tags
    key that guards the FILE, and the two catch genuinely different things
    (DEF-058: two guards on one fact are one guard).

    ⚠ **THE BILL THE FILE NAMED IS NOT PASSED AS AN ALLOCATION TARGET, AND
    THAT IS A DECISION RATHER THAN AN OMISSION.** US-PAY-003 §5 says the
    committed rows are *"each allocated per BR-PAY-010 by US-PAY-006"* —
    BR-PAY-010 being the tenant's own configurable order. A remittance line
    naming `BL-0141` tells us WHOSE money this is; it does not tell us that the
    utility wants it applied to that bill ahead of an older one, and
    `allocation._check_targets` treats a named bill as a STAFF INSTRUCTION
    (`specific` / `split`) that overrides the walk. Turning a bank's reference
    field into that instruction would silently override every tenant's
    allocation policy, four hundred times a morning, on the strength of what a
    lockbox operator typed.

    So `invoice_id` stays on the staged row as PROVENANCE — it is how the
    account was found and the screen shows it — and the allocator runs its
    ordinary course. A utility that wants remittance lines to direct allocation
    is asking for a new rule, not for this default to be quietly different.
    """
    arrival = row.paid_on or recorded_on
    moment = _moment(arrival)
    recorded = services.record_payment(
        actor,
        account_id=row.account_id,
        amount=row.amount,
        posted_at=moment,
        method_code="lockbox",
        confirmation=row.reference,
        memo=f"imported from {batch.file_name or 'a remittance file'}, row {row.row_no}",
        idempotency_source="import",
        idempotency_reference=f"{batch.pk}:{row.row_no}",
    )
    row.payment_id = uuid.UUID(str(recorded.payment_id))
    row.commit_error = None
    row.save(update_fields=["payment_id", "commit_error", "updated_at"])
    return str(recorded.payment_id)


# ══ 5 · PUT IT DOWN ═════════════════════════════════════════════════════════


def discard_batch(actor: Any, *, batch_id: Any, reason: str) -> models.PaymentImportBatch:
    """A clerk puts a file down. The batch is KEPT, never deleted.

    Nothing is undone because nothing was done: a staged batch has created no
    payment, which is the whole point of rule 1. The row survives so that an
    auditor can see a file arrived and was set aside, and so a second upload of
    the same file is a fresh batch rather than a mystery.
    """
    tenant_id = _tenant_id()
    if not (reason or "").strip():
        raise PaymentRuleError(
            "discarding an import needs a reason. A bank file that arrived and vanished is the "
            "one thing a bookkeeper cannot reconcile.",
            br_ref="BR-PAY-023",
        )
    batch = _mutable_batch(tenant_id, batch_id)
    with transaction.atomic():
        before = {"status": batch.status}
        batch.status = models.IMPORT_DISCARDED
        batch.save(update_fields=["status", "updated_at"])
        core_audit.money_action(
            actor,
            AUDIT_DISCARDED,
            "payment_import_batch",
            str(batch.pk),
            before=before,
            after={
                "status": models.IMPORT_DISCARDED,
                "file_name": batch.file_name,
                "reason": reason.strip(),
                "payments_created": 0,
            },
        )
    return batch


def _mutable_batch(tenant_id: Any, batch_id: Any) -> models.PaymentImportBatch:
    """This tenant's batch, and refuse if it is finished.

    The database says the same thing (`payments/0021`'s freeze trigger) and this
    is not a substitute for it: the trigger is the guarantee, and this is the
    sentence a clerk reads instead of a constraint violation. Two checks on one
    fact would be one check if they were on the same layer — these are not.
    """
    batch = models.PaymentImportBatch.objects.filter(tenant_id=tenant_id, pk=batch_id).first()
    if batch is None:
        raise PaymentRuleError(
            f"import batch {batch_id} is not this tenant's. Nothing was changed.",
            br_ref="BR-TEN-003",
        )
    if batch.status == models.IMPORT_COMMITTED:
        raise PaymentRuleError(
            f"batch {batch.pk} is committed and names recorded payments, so it cannot be "
            "changed. Correct the payments themselves — a reversal, or a reapply — never the "
            "file that made them.",
            br_ref="BR-PAY-002",
        )
    if batch.status == models.IMPORT_DISCARDED:
        raise PaymentRuleError(
            f"batch {batch.pk} was discarded. Upload the file again if it should be imported "
            "after all; its bytes are unchanged, so nothing about the first attempt blocks it.",
            br_ref="BR-PAY-023",
        )
    return batch
