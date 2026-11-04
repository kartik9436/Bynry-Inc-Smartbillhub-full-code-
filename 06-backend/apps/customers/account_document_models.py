# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 step 2 wave I — `ACC-S8`, "An account can hold a
#           document". Step 1 lane 2 finding F10: *"An account can hold no
#           document. BR-CUS-036 is CONFIRMED and names an `account_documents`
#           table; neither the table nor an upload endpoint exists, and the tab
#           draws five column heads over the stated absence."*
# Story:    US-CUS-011 (Meters · Documents · Notes · Audit) · screen S21, tab
#           `ACC-T10`.
# Rules:    BR-CUS-036 (CONFIRMED, PO closure batch 2026-08-08 — THE table and
#           THE five-value type lookup) · BR-SHL-031 (CONFIRMED — object
#           storage, PDF/PNG/JPG/CSV allowlist, 10 MB cap, "v1 uploads
#           staff-mediated"; its malware-scan clause SUPERSEDED by the PO,
#           2026-09-22/23, DEF-SHL-6347) · NFR-33 (account documents are a
#           STORED ARTIFACT) · NFR-35 (write-once, seven years) · BR-CUS-034
#           (customers keeps no copy of another module's row) · BR-TEN-031 (the
#           owning module publishes the callable its neighbours use) ·
#           CLAUDE.md hard rule 1 (tenant scoping, RLS FORCE) · hard rule 7
#           (audit) · hard rule 8 (an address lives on premises — NO address
#           column is declared here).
# Tests:    06-backend/tests/test_cr094_i_account_documents.py
# Impacts:  07-frontend/src/features/customers/accountDetailTabs.tsx
#           (`AccountDocumentsTab`) · GET/POST /accounts/{id}/documents.
# ───────────────────────────────────────────────────────
"""The filing cabinet on one account: WHICH account, WHAT kind, and WHOSE file.

WHY THIS TABLE EXISTS WHEN A DOCUMENT STORE ALREADY DOES
─────────────────────────────────────────────────────────────────────────────
`apps.tenancy.document_store` is built, tested and holds the bytes, the hash,
the size and the human name. **It is not enough on its own, and the missing
piece is exactly the one `BR-CUS-036` names:** the rule requires a *"type from
lookup System/Contract/KYC/Payment/Correspondence"*, and that vocabulary is a
CUSTOMERS vocabulary. `stored_documents.kind` is the PRODUCT's vocabulary — 36
values naming what a document IS across six modules — and `account_document` is
one of them. Pushing five customer filing categories into that CHECK constraint
would make a platform table grow a column of another module's business meaning
every time a module invented a folder.

So this row is the **filing card** and the stored document is the **file**:

    account_documents.document_id ──▶ stored_documents.id

`BR-CUS-036`'s *"storage ref"* IS that foreign key. **Nothing here stores
bytes, and there is no second storage path** — the one PO standing instruction
this wave was given, verbatim: *"Do all changes based on actual code — also
don't create duplicate code."*

WHAT IS NOT HERE, AND EACH ABSENCE IS A DECISION
─────────────────────────────────────────────────────────────────────────────
**`name` and `size` are NOT columns**, though `BR-CUS-036` lists both. They are
`stored_documents.display_name` and `stored_documents.byte_length`, written by
the same call that stores the bytes and frozen by the same trigger. A second
copy of a file's own name is a second answer to *"what is this file called"*,
and the one on the immutable row is the one that cannot drift. The rule names
the FACTS the tab must show; it does not require this table to hold them twice.

⚠ **THAT ABSENCE IS CLOSED. `BR-CUS-1052` IS THE RULE AND `withdrawn_at` IS THE
COLUMN, AND THEY ARRIVED TOGETHER EXACTLY AS THIS PARAGRAPH SAID THEY WOULD.**
It read, until 2026-09-13: *"No `deleted_at`, and no delete endpoint … So v1
files and lists, and removes nothing. If a removal is ever ruled it arrives as a
rule and a column together."* The PO ruled it — verbatim, *"We should have this
functionality"* — on the wave I report that *"a clerk who files the wrong scan
cannot take it back"*.

**WHAT MOVED IS NARROW AND WHAT DID NOT MOVE IS NAMED.** `BR-SHL-031` still
makes the legal class write-once for seven years and `stored_documents` still
enforces it with a database trigger; `NFR-35` says the same; **neither is
reversed and nothing here may reverse them.** What the clerk's control does is
WITHDRAW THE FILING: `withdrawn_at` is stamped, the row stops being listed,
opened or counted on that account, an audit row names who did it and when — and
**the stored object is not touched at all.** The bytes stay under their
retention lock where the law requires them. (⚠ the object LOCK is suspended from 2026-10-02, `CR-160-BRC10`; the row stays write-once)

**`BR-CUS-036`'s AUDIT-LOCKED CLASSES STILL REFUSE.** `system` and `contract`
are *audit-locked (IS-1 🔒)* and a withdrawal of either is refused BY NAME with
its reason on screen (`BR-SHL-025`) — see `WITHDRAWABLE_TYPES` below. A clerk
may take back a scan they filed; never a contract the system attached.

**No address column** — hard rule 8. A document is filed against an account, and
an account walks to its premises for where it is. Nothing here needs to know.

THE AUDIT POSTURE, DECIDED RATHER THAN ASSUMED
─────────────────────────────────────────────────────────────────────────────
Hard rule 7 requires an audit row for every MONEY action. **Filing a document on
an account is not a money action** — no ledger line moves, no invoice changes,
no payment is taken — so rule 7 does not compel one. **Two are written anyway**,
and the reason is the one `document_store.store()` already gives for its own:
*"who froze this document, and when"* is the question that follows *"show me the
document"*, and a document filed against a financial record is evidence about
that record even when filing it moved no money.

  * `document.stored` — written by the store, about the bytes.
  * `customers.account_document.filed` — written here, about the FILING: which
    account, which type, which clerk. The store's row cannot carry those; it
    does not know what an account is.

A reader deciding whether some future document action needs an audit row should
read this paragraph rather than infer a rule from the code.
"""

from django.db import models

from core.dbfields import uuid7_pk

# ═══════════════════════════════════════════════════════════════════════════
# THE TYPE LOOKUP — `BR-CUS-036`'s five values, quoted
# ═══════════════════════════════════════════════════════════════════════════
#
# `BR-CUS-036`, verbatim: *"type lookup System/Contract/KYC/Payment/
# Correspondence"*. These five, in that order, and adding a sixth is a migration
# and a decision-log row — the same posture `stored_documents.kind` takes, for
# the same reason: a free-text folder name is a rule nobody can satisfy.
#
# ⚠ **THE DRAWING'S CHIPS ARE `All` `Correspondence` `Evidence` AND `Evidence`
# IS NOT ONE OF THESE FIVE.** `ACC-T10`'s toolbar is a wireframe; `BR-CUS-036`
# is CONFIRMED signed law. A wireframe cannot amend a signed vocabulary, so the
# filter follows the rule and the difference is FILED rather than silently
# resolved either way — `04-docs/05-modules/03-customers/conformance/` and the
# decision log of 2026-09-12 both carry it. (B14 rule 37 is the same instinct
# about a drawn NUMBER; this is a drawn VALUE, and the reasoning transfers.)
TYPE_SYSTEM = "system"
TYPE_CONTRACT = "contract"
TYPE_KYC = "kyc"
TYPE_PAYMENT = "payment"
TYPE_CORRESPONDENCE = "correspondence"

DOCUMENT_TYPES = (
    TYPE_SYSTEM,
    TYPE_CONTRACT,
    TYPE_KYC,
    TYPE_PAYMENT,
    TYPE_CORRESPONDENCE,
)

#: ⚠ **WHAT A CLERK MAY UPLOAD IS A SUBSET, AND THE RULE SAYS SO IN ITS OWN
#: WORDS.** `BR-CUS-036`: *"system-generated documents (welcome pack, signed
#: agreements, deposit letters) attach automatically"* and *"system/contract
#: docs audit-locked (IS-1 🔒)"*. A document a clerk hands to the product is by
#: definition not system-generated, so `system` is refused at the door — letting
#: one in by hand would make *"this was generated by the product"* a claim a
#: person could type. `contract` stays uploadable because a countersigned lease
#: arrives on paper; it is the LOCK that makes it audit-locked, and the lock is
#: that nothing in this product can ever edit or remove it.
UPLOADABLE_TYPES = (
    TYPE_CONTRACT,
    TYPE_KYC,
    TYPE_PAYMENT,
    TYPE_CORRESPONDENCE,
)

#: ⚠ **WHAT A CLERK MAY TAKE BACK IS A DIFFERENT SUBSET AGAIN, AND IT IS NOT
#: `UPLOADABLE_TYPES` MINUS NOTHING.** `BR-CUS-036`: *"system/contract docs
#: audit-locked (IS-1 🔒)"*. **`contract` is UPLOADABLE AND NOT WITHDRAWABLE**,
#: and that asymmetry is the rule rather than an oversight: a countersigned
#: lease arrives on paper and has to get in, and the LOCK is that once it is in,
#: nothing in this product takes it out again.
#:
#: ⚠ **THE TWO LISTS ARE THEREFORE NOT DERIVABLE FROM EACH OTHER AND MUST NOT BE
#: MADE SO.** A sixth type added to `DOCUMENT_TYPES` appears in NEITHER of them
#: until somebody decides, which is the posture `UPLOADABLE_TYPES` already takes
#: and for the same reason — a default of "removable" on a filing cabinet is the
#: wrong way for a mistake to fall (hard-won law 3: the unsafe option is the one
#: you type).
WITHDRAWABLE_TYPES = (
    TYPE_KYC,
    TYPE_PAYMENT,
    TYPE_CORRESPONDENCE,
)

#: The complement, named rather than computed at every call site — it is what a
#: screen needs to say WHY a control is disabled (`BR-SHL-025`) and what a test
#: asserts the refusal over.
AUDIT_LOCKED_TYPES = tuple(t for t in DOCUMENT_TYPES if t not in WITHDRAWABLE_TYPES)


class AccountDocument(models.Model):
    """One filing card: this account holds this document, of this type.

    ⚠ **ONE CODE PATH UPDATES A ROW HERE AND EXACTLY ONE, AND THE RULE THAT
    PERMITS IT IS `BR-CUS-1052`** (PO 2026-09-13, verbatim: *"We should have
    this functionality"*). This docstring read *"Nothing in this product updates
    or deletes a row here — there is no endpoint that can … A lane adding one
    must say which rule permits it"*; this is that sentence being answered
    rather than removed.

    **The path is `account_documents.withdraw_document()` and it sets three
    columns — `withdrawn_at`, `withdrawn_by` and nothing else.** Every other
    column of every row is still written once and never again, and there is
    still **no DELETE** in this product for this table. `ck_account_documents_
    withdrawal` is the database's half of it: a withdrawal that does not name
    its withdrawer is refused.

    ⚠ **CLAUDE.md HARD RULE 4 IS NOT IN PLAY AND SAYING SO IS THE POINT.** It
    names issued invoices, invoice lines, payments and journal entries; a filing
    card is none of those and no money moves when one is withdrawn. The rule
    that DOES govern this table's target — `BR-SHL-031`'s write-once seven
    years on `stored_documents` — is untouched: **a withdrawal writes nothing to
    that table and reads nothing back out of it.**
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="account_id",
        related_name="documents",
    )

    #: `BR-CUS-036`'s *"storage ref"*. ⚠ **A FOREIGN KEY AND NOT A STRING.**
    #: `service_request_documents.storage_ref` is a nullable TextField that
    #: nothing has ever written, which is what a "ref" becomes when there is
    #: nowhere for it to point. There is somewhere now.
    #:
    #: ⚠ **CROSS-MODULE FK, customers → tenancy, and it is in B2 §2's reviewed
    #: interface set** — the same direction and the same posture as
    #: `work_order_attachments.document_id` (`CR-070` wave K). `PROTECT`,
    #: because the target cannot be deleted anyway (`0026`'s write-once
    #: trigger) and a CASCADE here would describe a deletion that cannot
    #: happen.
    document = models.ForeignKey(
        "tenancy.StoredDocument",
        on_delete=models.PROTECT,
        db_column="document_id",
        related_name="+",
    )

    #: One of `DOCUMENT_TYPES`. A CHECK constraint, deliberately — see above.
    doc_type = models.TextField()

    #: WHO filed it. Nullable for the reason every actor column in this repo is
    #: nullable: `BR-CUS-036`'s system-generated documents *"attach
    #: automatically"* and have no human behind them, and a NOT NULL column
    #: would force one to be invented. ⚠ A document with NEITHER a user NOR a
    #: process is refused by `ck_account_documents_actor` — *"nobody knows"* is
    #: not an answer a filing cabinet may give, which is the same line
    #: `ck_stored_documents_actor` holds one table across.
    uploaded_by = models.ForeignKey(  # ⚠ cross-module customers→identity (B2 §2)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="uploaded_by",
        related_name="+",
    )
    #: A dotted path — `customers.move_in`, `billing.issue` — when the product
    #: filed it rather than a person. Mirrors `stored_documents.stored_by_process`
    #: so the two rows agree about who acted.
    uploaded_by_process = models.TextField(null=True, blank=True)

    #: ⚠ **STORED, NOT DERIVED FROM `stored_at`, AND THE TWO ARE DIFFERENT
    #: FACTS.** `stored_documents.stored_at` is when the BYTES landed. This is
    #: when the document was FILED on the account. They are the same instant
    #: today because the upload does both in one call — and a back-filed
    #: document (a lease signed in March, scanned in September) is the case
    #: that makes them diverge, which is a column that must exist before it is
    #: needed rather than a migration over live rows afterwards.
    uploaded_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    # ═══════════════════════════════════════════════════════════════════════
    # THE WITHDRAWAL — `BR-CUS-1052`, and the two columns it needs
    # ═══════════════════════════════════════════════════════════════════════

    #: WHEN the filing was taken back. NULL on every filing that is still on the
    #: account, which is what every read filters on.
    #:
    #: ⚠ **THIS IS A TOMBSTONE, NOT A DELETION, AND THE DIFFERENCE IS THE WHOLE
    #: RULING.** The row stays, the `document_id` stays, the stored object stays
    #: under its seven-year lock. What changes is that this account no longer
    #: holds this document: it is not listed, not counted, not openable, and
    #: `document_link` answers a withdrawn filing exactly as it answers one that
    #: never existed.
    #:
    #: ⚠ **AND NOTHING IN THE PRODUCT PUTS IT BACK — A JUDGMENT, NOT AN
    #: OVERSIGHT.** Nothing was ruled about restoring a withdrawn filing, so the
    #: narrower thing was built and the reasoning is in the decision log of
    #: 2026-09-13: gone from the clerk's view, recoverable only by somebody with
    #: the audit trail. A restore control is a second decision and it is
    #: unmade.
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    #: WHO took it back. ⚠ **NOT NULLABLE-IN-PRACTICE AND THE CHECK SAYS SO** —
    #: unlike `uploaded_by`, which is nullable because the product files
    #: documents itself, **no automation withdraws anything.** There is exactly
    #: one caller and it is a staff endpoint. So there is deliberately **no
    #: `withdrawn_by_process` column**: an optional column nothing ever writes
    #: is dead schema that every test passes over (hard-won law 2), and
    #: inventing one would also invite the automated withdrawal nobody ruled.
    withdrawn_by = models.ForeignKey(  # ⚠ cross-module customers→identity (B2 §2)
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="withdrawn_by",
        related_name="+",
    )

    class Meta:
        db_table = "account_documents"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(doc_type__in=DOCUMENT_TYPES),
                name="ck_account_documents_type",
            ),
            #: A filing with no filer is unprovable. See `uploaded_by`.
            models.CheckConstraint(
                condition=(
                    models.Q(uploaded_by__isnull=False)
                    | (
                        models.Q(uploaded_by_process__isnull=False)
                        & ~models.Q(uploaded_by_process="")
                    )
                ),
                name="ck_account_documents_actor",
            ),
            #: One filing card per stored document. The card is minted BEFORE
            #: the document and its id is the document's `source_id`, so two
            #: cards claiming one document means two accounts claim one file.
            models.UniqueConstraint(
                fields=["tenant", "document"], name="uq_account_documents_document"
            ),
            #: `BR-CUS-1052`: *"the withdrawal writes an audit row naming who
            #: did it and when"*. The audit row is hard rule 7's half; this is
            #: the ROW's half — a filing that is off the account must be able to
            #: say who took it off. It is the same line `ck_account_documents_
            #: actor` holds for the filing: *"nobody knows"* is not an answer a
            #: filing cabinet may give.
            #:
            #: ⚠ **IT IS A BACKSTOP AND NEVER THE MECHANISM.**
            #: `withdraw_document()` refuses an unresolvable actor BEFORE it
            #: writes, because a CHECK firing mid-transaction is hard-won law
            #: 14's trap — on PostgreSQL it poisons everything after it, and
            #: SQLite (which the suite runs on) has no such state, so a caller
            #: relying on the constraint would pass every test and fail in
            #: production.
            models.CheckConstraint(
                condition=(
                    models.Q(withdrawn_at__isnull=True)
                    | models.Q(withdrawn_by__isnull=False)
                ),
                name="ck_account_documents_withdrawal",
            ),
        ]
        indexes = [
            #: THE tab's own query: this account's documents, newest first
            #: (`NFR-3` — the list is paginated in SQL, never in Python). A
            #: landlord with four hundred filings does not sort them in the
            #: application, which is the same sentence `ix_account_notes_pinned`
            #: exists for one table across.
            models.Index(
                fields=["tenant", "account", "-uploaded_at"],
                name="ix_account_documents_recent",
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.doc_type} on account {self.account_id}"
