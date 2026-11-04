# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-016 (bulk corrections — the case, its pinned bill set and
#           the per-bill result rows) · US-BIL-031 (document-only correction —
#           the reissued document instance)
#           Screens: S30
# Rules:    BR-BIL-014 (correction = reason → scope → impact preview →
#           approval → staged idempotent execution → deliver + audit) ·
#           BR-BIL-041 (every reason carries a CLASS and the class derives the
#           mechanism) · BR-BIL-042 (one class per case; strongest present) ·
#           BR-BIL-044 (the preview is a persisted, content-hashed artifact and
#           approval binds the artifact) · BR-BIL-045 (the posting period is
#           resolved and named before confirm) · BR-BIL-046 (the approved set
#           is a PINNED LIST of bills, never a stored query) · BR-BIL-047 (one
#           bill = one transaction = the atomicity unit; no batch rollback) ·
#           BR-BIL-048 (only the latest document in a chain is correctable) ·
#           BR-BIL-004 (originals never change — corrections are new rows) ·
#           BR-BIL-030 (the bill is LOCKED at issue, which is why a document
#           fix produces a NEW instance and never an edit) · BR-BIL-049 (a
#           correction never edits master data; it RECORDS which master-data
#           change it reflects) · BR-TEN-043 (event time is an argument) ·
#           CLAUDE.md rule 1 (tenant scoping, RLS FORCE) · rule 2 (money
#           NUMERIC(18,6) + CHAR(3)) · rule 4 (financial immutability) ·
#           rule 6 (idempotency)
# Tests:    06-backend/tests/test_us_bil_016_bulk_corrections.py ·
#           06-backend/tests/test_us_bil_031_document_correction.py
# Impacts:  apps/billing/corrections.py (the per-bill engine that writes these
#           rows) · apps/billing/bulk_corrections.py (the case layer) ·
#           apps/billing/document_correction.py (the class-D artifact) ·
#           apps/billing/apps.py (registers this module with the app registry)
# ───────────────────────────────────────────────────────
"""The corrections workflow's three tables (B2 Addendum r10 #9 + EP-BIL-04).

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒 path
and `correction_case_bills` carries the money delta a correction moves.
AI-authored 2026-08-11 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in 12-governance/09-human-review-ledger.md.

**WHY THESE CLASSES ARE NOT IN `apps/billing/models.py`.** The same reason
`apps/payments/bankrec_models.py` records for itself: two lanes editing one
models module is how a migration graph forks, and billing's `models.py` is the
busiest file in this repo. `app_label` is `billing`, the tables are billing's
own, and `apps/billing/apps.py` imports this module so the registry sees them.
Folding it back into `models.py` later is a move, not a redesign.

════════════════════════════════════════════════════════════════════════════
WHAT IS TRANSCRIBED FROM SIGNED SCHEMA, AND WHAT IS AN ENG-LEAD DDL CALL
════════════════════════════════════════════════════════════════════════════
`correction_cases` is B2 Addendum **r10 #9** — *"correction cases (+ bulk runs
w/ per-bill results)"*. r10 #15 puts the exact DDL with the Eng-Lead, and r10
names no columns, so every column below cites the rule that puts it there:

  * `correction_class`         — BR-BIL-041/042 (derived, never supplied)
  * `preview` + `preview_hash` — BR-BIL-044 (the artifact approval binds)
  * `posting_period`           — BR-BIL-045 (named before confirm)
  * `correction_case_bills`    — BR-BIL-046 (a PINNED LIST, not a query) and
                                 BR-BIL-047 (per-bill status + failure reason +
                                 the artifact ids, so the case's own claim of
                                 success is checkable against what it produced)

`invoice_document_instances` is **not in r10 at all** and is the table OQ-103's
closure created: the PO ruled option (a) REISSUE on 2026-08-11 — *a corrected
document instance is rendered and attached to the original invoice, the original
retained.* EP-BIL-04's closing section names the absence in those words
(*"there is no reissue/document-instance table, so a class-D correction has
literally no write target"*). This is that table.

════════════════════════════════════════════════════════════════════════════
THE CHAIN EDGE — `invoices.corrects_invoice_id`, RULED 2026-08-12 (OQ-120)
════════════════════════════════════════════════════════════════════════════
**SUPERSEDED (PO 2026-08-11 *"in Histrory log only - at account level"* → PO
2026-08-12 *"Nod to add the link on the new bill"*, OQ-120 CLOSED).** The
paragraph that stood here is quoted verbatim below and must not be built to.

    "WHAT IS DELIBERATELY ABSENT — `invoices.corrects_invoice_id`.
     EP-BIL-04 §5 asks for it and BR-BIL-064 needs the chain — and the PO ruled
     the storage on 2026-08-11, verbatim: **"in Histrory log only - at account
     level"** (OQ-120). So NO column joins a bill to the one that replaced it,
     and this lane adds none. `correction_case_bills.rebill_invoice_id` is not
     that column: it is the CASE's record of what the case produced
     (BR-BIL-047's checkability), not a chain edge on `invoices`, and nothing
     reads it as one. The account-level history log the ruling names is unbuilt
     and its own storage question — whether it is `audit_log` or a distinct
     record — was explicitly left open by that same ruling; see the lane
     report."

**WHAT IS TRUE NOW.** The column exists (migration `0017`) and it lives on the
**replacement**, pointing back at what it replaces. The direction is the whole
of the ruling: an issued invoice is frozen (BR-BIL-004, hard rule 4), so the
ORIGINAL must not gain a value after issue, while a rebill is still a draft at
the moment it learns what it replaces. `corrections.execute_restatement` stamps
it; `corrections.replacement_of` / `.latest_in_chain` read it; `release.
summary_for` follows it, and refused outright — naming this exact column — for
as long as it did not exist.

**WHAT DID NOT CHANGE.** `correction_case_bills.rebill_invoice_id` is still not
a chain edge: it is the CASE's record of what the case produced (BR-BIL-047's
checkability). The two answer different questions — *"what did case CC-2026-041
do?"* versus *"what does this customer owe now?"* — and a bill can be corrected
outside a case's lifetime while its case row is archived. The hard-rule-7 audit
row `execute_restatement` writes also still carries the link; it is owed anyway
and a second copy of a fact in the audit trail costs nothing.

════════════════════════════════════════════════════════════════════════════
IMMUTABILITY IS NOT IN THESE CLASSES
════════════════════════════════════════════════════════════════════════════
A Django model cannot refuse a `.save()` — `apps/billing/models.py` says so of
itself and it is true here. The guarantees live in the migration:
`invoice_document_instances` is append-only by trigger (a reissued document a
later UPDATE could edit is not a document instance, which is BR-BIL-030's own
argument applied to the artifact it created), and all three tables are RLS
ENABLE + FORCE.
"""

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

#: BR-BIL-041's three classes. The operator picks the REASON; the system
#: derives the class; the mechanism is never a dropdown. Kept here rather than
#: in `correction_reasons.py` because the COLUMN's vocabulary and the
#: taxonomy's vocabulary must be one list — two copies is how an enum and its
#: check constraint start disagreeing.
CLASS_RESTATEMENT = "restatement"
CLASS_CREDIT_ONLY = "credit_only"
CLASS_DOCUMENT = "document"
CORRECTION_CLASSES = (CLASS_RESTATEMENT, CLASS_CREDIT_ONLY, CLASS_DOCUMENT)

#: EP-BIL-04's S30 case-list filter set, verbatim: *"status (preview/
#: pending-approval/approved/executing/done/failed)"*, plus `open`, which
#: BR-BIL-047 requires and that list does not carry: *"the case stays OPEN
#: while any bill is unresolved"* — a case with one failed bill is neither done
#: nor failed, and calling it either would be a lie on the screen.
CASE_PREVIEW = "preview"
CASE_PENDING_APPROVAL = "pending_approval"
CASE_APPROVED = "approved"
CASE_EXECUTING = "executing"
CASE_OPEN = "open"
CASE_DONE = "done"
CASE_FAILED = "failed"
CASE_STATUSES = (
    CASE_PREVIEW,
    CASE_PENDING_APPROVAL,
    CASE_APPROVED,
    CASE_EXECUTING,
    CASE_OPEN,
    CASE_DONE,
    CASE_FAILED,
)

#: BR-BIL-014 (bulk): *"scope by run/cycle/plan/service/date-range"*, plus the
#: single-bill case US-BIL-015 opens from one bill.
SCOPE_SINGLE = "single"
SCOPE_RUN = "run"
SCOPE_CYCLE = "cycle"
SCOPE_PLAN = "plan"
SCOPE_SERVICE = "service"
SCOPE_DATE_RANGE = "date_range"
#: `CR-180-BRC10` (PO 2026-10-12, *"one customer and bulk - two options"*) —
#: the two scopes the revamped wizard adds. **One customer** is one account and
#: one OR MANY of its bills (`DEF-BIL-5348`: several months on one account, in
#: ONE case); **a price mistake** is every bill that used a rate, a tax or a
#: charge code between two dates, across runs. The six older kinds stay valid —
#: the old routes keep working (CR-180 §Version and rollback).
SCOPE_ACCOUNT = "account"
SCOPE_PRICE_MISTAKE = "price_mistake"
SCOPE_KINDS = (
    SCOPE_SINGLE,
    SCOPE_RUN,
    SCOPE_CYCLE,
    SCOPE_PLAN,
    SCOPE_SERVICE,
    SCOPE_DATE_RANGE,
    SCOPE_ACCOUNT,
    SCOPE_PRICE_MISTAKE,
)

#: Per-bill execution state (r10 #9's "per-bill results"; BR-BIL-047).
BILL_QUEUED = "queued"
BILL_DONE = "done"
BILL_FAILED = "failed"
BILL_ABANDONED = "abandoned"
BILL_RESULTS = (BILL_QUEUED, BILL_DONE, BILL_FAILED, BILL_ABANDONED)

#: BR-BIL-046: *"↑ count and sum of bills going UP, ↓ count and sum going
#: DOWN, side by side"*. Stored per bill so the aggregate never has to infer a
#: direction from a signed sum it has already added up.
DIRECTION_UP = "up"
DIRECTION_DOWN = "down"
DIRECTION_ZERO = "zero"
DIRECTIONS = (DIRECTION_UP, DIRECTION_DOWN, DIRECTION_ZERO)


class CorrectionCase(models.Model):
    """One correction — of one bill or of four hundred (BR-BIL-014, r10 #9).

    A bulk case and a single case are the SAME row with a different scope, which
    is EP-BIL-04's own shape (*"bulk corrections are one case with many bills"*)
    and the reason the S30 list offers no bulk row action.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    #: The number a clerk quotes — `CC-2026-001` on an untouched tenant. ⚠ **THIS
    #: COMMENT READ "nothing rules when a case number is allocated … there is no
    #: case series in `core/numbering.py`" UNTIL 2026-10-14, AND NO CASE WAS EVER
    #: NUMBERED** (`DEF-BIL-10147`: every screen read "No case number yet").
    #:
    #: **RULED — G3, PO 2026-10-14** (decision log *"G1–G4 APPROVED"* item 3): a
    #: case takes its number AT SEND from the tenant's `correction_case` series,
    #: default `CC-{YYYY}-{000}`, editable on Settings → Numbering; existing cases
    #: are numbered once, oldest first (`billing/0043`); a deleted series leaves
    #: the case unnumbered and is never blocking — the credit-memo precedent
    #: (`corrections._allocate_credit_note_no`). The allocator is
    #: `corrections.allocate_case_no`, called inside the Send's transaction by
    #: `correction_items._open_case` and `bulk_corrections.open_case`.
    #:
    #: STILL NULLABLE, on purpose: a Send while the series row is missing opens
    #: the case unnumbered and records why (`numbering_gap` on the
    #: `correction.case_sent` / `correction.case_opened` audit row). The partial
    #: unique constraint below keeps two cases of one tenant off one number.
    case_no = models.TextField(null=True, blank=True)

    #: The reason CODES cited (BR-BIL-014: reference data, tenant-extensible).
    #: A LIST because BR-BIL-042 exists — *"a case may carry several reason
    #: codes and takes the STRONGEST class present"*. The lookup table itself is
    #: US-BIL-017's (r10 #13) and is NOT built; `correction_reasons.py` carries
    #: the seeded map and refuses a code it cannot class, which is BR-BIL-041's
    #: guarantee held one layer up until the table lands.
    reason_codes = models.JSONField(default=list)

    #: BR-BIL-041 — DERIVED from the reasons at case creation and never
    #: supplied by a caller. Stored rather than recomputed because a case
    #: approved under a reason whose class a tenant later re-pointed must still
    #: say what it was approved as (the IS-1 audit-lock reasoning).
    correction_class = models.TextField()

    scope_kind = models.TextField(default=SCOPE_SINGLE)
    #: The selector as the operator entered it — run id, cycle, plan, service,
    #: dates. Kept for the audit trail and for the screen; it is explicitly NOT
    #: what execution reads. BR-BIL-046: the approved set is the pinned rows.
    scope = models.JSONField(default=dict)

    status = models.TextField(default=CASE_PREVIEW)

    #: BR-BIL-044 — the nine-section artifact, persisted, and the content hash
    #: approval binds. Execution recomputes the hash and REFUSES on drift, so
    #: the approver's signature covers the numbers they actually saw.
    preview = models.JSONField(default=dict)
    preview_hash = models.TextField(null=True, blank=True)

    #: BR-BIL-045 — resolved at preview against BR-TEN-038 and re-checked at
    #: execute. A closed July posts to the earliest open period, so the month
    #: that moves is not always the month on the bill.
    posting_period = models.DateField(null=True, blank=True)

    initiated_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="initiated_by",
        related_name="correction_cases_initiated",
    )
    approved_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="approved_by",
        related_name="correction_cases_approved",
    )
    #: BR-TEN-043: the business date of the approval, supplied by the caller.
    approved_on = models.DateField(null=True, blank=True)
    executed_on = models.DateField(null=True, blank=True)

    #: BR-BIL-047: *"abandoning a failure is an explicit, reasoned, audited act
    #: rather than a case that quietly reports done"*. Both columns or neither.
    closed_reason = models.TextField(null=True, blank=True)
    closed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="closed_by",
        related_name="correction_cases_closed",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "correction_cases"
        indexes = [
            models.Index(fields=["tenant", "status"], name="ix_corr_cases_status"),
            models.Index(fields=["tenant", "created_at"], name="ix_corr_cases_created"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "case_no"],
                condition=Q(case_no__isnull=False),
                name="uq_correction_cases_no",
            ),
        ]


class CorrectionCaseBill(models.Model):
    """One bill inside a case: its impact, its result, and what it produced.

    THIS ROW IS THE PINNED SET (BR-BIL-046). The scope predicate resolves ONCE,
    at preview, into these rows; execution iterates them and never re-runs the
    query. A bill issued between approval and execution cannot join a set
    somebody already signed off — which is the whole of why the pinning is a
    table and not a `WHERE` clause.

    IT IS ALSO THE IDEMPOTENCY KEY (CLAUDE.md rule 6). `UNIQUE (tenant, case,
    invoice)` plus a `status` that only ever moves queued → done means a
    re-triggered execution finds `done` and does nothing: exactly one credit
    note and one rebill exist per bill per case however many times the job runs
    (US-BIL-016 TC-4/TC-6).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    case = models.ForeignKey(
        CorrectionCase, on_delete=models.PROTECT, db_column="case_id", related_name="bills"
    )
    invoice = models.ForeignKey("billing.Invoice", on_delete=models.PROTECT, db_column="invoice_id")
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (reviewed set, B2 §2)
        "customers.Account", on_delete=models.PROTECT, db_column="account_id"
    )

    #: The per-bill nine-section preview (BR-BIL-044 computed per bill, then
    #: aggregated by BR-BIL-046). The aggregate performs no arithmetic of its
    #: own — US-BIL-016 §7 says so in those words — so these rows are the
    #: evidence and the panel is a display sum over them.
    impact = models.JSONField(default=dict)
    delta_amount = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    currency = models.CharField(max_length=3, default="USD")  # rule 2 partner
    direction = models.TextField(default=DIRECTION_ZERO)
    #: BR-BIL-043/045's warning set. A count of warned rows sorts them first on
    #: the approval screen (BR-BIL-046) — a 240-row preview is not read in order.
    warnings = models.JSONField(default=list)

    status = models.TextField(default=BILL_QUEUED)
    failure_reason = models.TextField(null=True, blank=True)

    #: What this bill's execution actually produced. BR-BIL-047: the case's own
    #: claim of success is checkable against the artifacts, not taken.
    credit_note = models.ForeignKey(
        "billing.CreditNote",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="credit_note_id",
    )
    rebill_invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="rebill_invoice_id",
        related_name="correction_rebill_rows",
    )
    #: A class-C goodwill credit is an ACCOUNT-level adjustment consumed by a
    #: FUTURE bill, never a credit note against this one — PO 2026-08-11,
    #: *"you dont touch the bill; you issue new a good will credit"*.
    goodwill_adjustment = models.ForeignKey(
        "billing.Adjustment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="goodwill_adjustment_id",
    )
    document_instance = models.ForeignKey(
        "billing.InvoiceDocumentInstance",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="document_instance_id",
    )

    executed_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "correction_case_bills"
        indexes = [
            models.Index(fields=["tenant", "case", "status"], name="ix_corr_bills_case"),
            models.Index(fields=["tenant", "invoice"], name="ix_corr_bills_invoice"),
        ]
        constraints = [
            # Rule 6. One row per bill per case — a resumed job re-attempts the
            # failures and cannot enrol a bill twice.
            models.UniqueConstraint(
                fields=["tenant", "case", "invoice"],
                name="uq_correction_case_bill",
            ),
            # BR-BIL-048, the half a database can hold: at most ONE unresolved
            # case row per bill. A second case cannot claim a bill an executing
            # case already holds (US-BIL-016 TC-6). The chain half — "only the
            # LATEST document in a chain is correctable" — is a service check,
            # because the chain lives in the account history log (OQ-120) and
            # no column here can see it.
            models.UniqueConstraint(
                fields=["tenant", "invoice"],
                condition=Q(status=BILL_QUEUED),
                name="uq_correction_bill_in_flight",
            ),
        ]


class CorrectionCaseItem(models.Model):
    """ONE correction row of a case — `CR-180-BRC10` B3, the "What was wrong" table.

    PO 2026-10-12, verbatim: *"Instead of that if we do Table array … then user
    can add one otr mulitple correctiosn as per requirements … and then say
    apply this to 1 or more bill"*. So a case is no longer one reason picked from
    a list: it is N rows, each naming WHAT was wrong (`reason`), WHICH thing
    (`item` — a meter, a plan, a schedule, a tax authority, a charge code, a
    discount programme, a field of the page), the value it SHOULD have been
    (`value`, `value2`), and WHICH of the case's bills it applies to
    (`bill_ids`; NULL = every bill in the case).

    **THE ROWS ARE WHAT THE CASE WAS APPROVED ON.** They are written at Send,
    in the same transaction as the case and its pinned bills, and execution
    re-prices FROM them — so an approver's signature covers the corrections
    themselves and not only the figures they produced. `position` keeps the
    clerk's order, because "row 3" is how a refusal names one.

    **NO MONEY COLUMN.** A row's `value` is TEXT, exactly as typed and already
    validated (a reading, a rate %, an amount as a decimal string): the money
    a row produces is the RE-PRICED bill's, computed by the engine and pinned on
    `correction_case_bills.impact`. A second, typed figure here would be a
    second source of truth for the same money (hard rule 2's partner rule:
    one figure, one place).

    `correction_class` is the ROW's class (BR-BIL-041), stored as derived so a
    case read a year later still says what each row was; the case's own class
    is the strongest across its rows (BR-BIL-042, R > C > D).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    case = models.ForeignKey(
        CorrectionCase, on_delete=models.PROTECT, db_column="case_id", related_name="items"
    )
    position = models.IntegerField()
    reason = models.TextField()
    correction_class = models.TextField()
    item = models.TextField(null=True, blank=True)
    act = models.TextField(null=True, blank=True)
    value = models.TextField(null=True, blank=True)
    value2 = models.TextField(null=True, blank=True)
    #: The invoice ids this row applies to, as strings; NULL = every bill in
    #: the case. A LIST rather than a join table because a row is written once,
    #: at Send, and read whole — it is part of the approved artifact.
    bill_ids = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "correction_case_items"
        indexes = [
            models.Index(fields=["tenant", "case"], name="ix_corr_items_case"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "case", "position"], name="uq_correction_case_item_position"
            ),
            models.CheckConstraint(
                condition=Q(correction_class__in=CORRECTION_CLASSES),
                name="ck_correction_case_item_class",
            ),
        ]


class InvoiceDocumentInstance(models.Model):
    """A REISSUED document for a bill whose money is right (US-BIL-031).

    OQ-103, closed by the PO on 2026-08-11 — option **(a) REISSUE**: *a
    corrected document instance is rendered and attached to the original
    invoice, the original retained*. Shown to the PO in these words: *"July's
    bill went to 1408 Bluestem Ln; they moved on 20 July; it came back
    undelivered."*

    THE PAYLOAD IS A CORRECTED COPY, NEVER AN EDIT. `invoices.bill_payload` is
    frozen by the `0006` immutability trigger — deliberately (BR-BIL-030: a
    snapshot that can be edited later is not a snapshot) — so the ONLY lawful
    output is a new row carrying its own payload. The original bill keeps its
    own payload byte-identical forever, and `documents.render_invoice` renders
    this instance from an in-memory copy that is never saved.

    NO MONEY LIVES HERE and none may be added. A class-D correction moves
    $0.00 (BR-BIL-041/043); a row on this table with an amount column would be
    an invitation to move some.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.PROTECT,
        db_column="invoice_id",
        related_name="document_instances",
    )
    case = models.ForeignKey(
        CorrectionCase,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="case_id",
        related_name="document_instances",
    )

    #: 1 for the first reissue, 2 for the next. Instance 0 is not stored: it is
    #: the ORIGINAL, which lives on the invoice and must never be copied here —
    #: two rows claiming to be the issued document is exactly the ambiguity the
    #: still-open half of OQ-103 is about.
    instance_no = models.IntegerField(default=1)

    payload = models.JSONField()
    payload_version = models.IntegerField(default=1)
    #: BR-BIL-026: the reissue renders on the pin the ORIGINAL carries, not on
    #: today's published version. A template change never re-renders history
    #: (BR-BIL-031), and a document correction is not a template change.
    template_id = models.UUIDField(null=True, blank=True)
    template_version = models.IntegerField(null=True, blank=True)
    template_language = models.TextField(null=True, blank=True)

    reason_codes = models.JSONField(default=list)
    #: BR-BIL-049 — *"a correction never edits master data and a master-data
    #: edit is never a correction; the case RECORDS which master-data change it
    #: reflects."* Free text + an optional id, because the customers-module
    #: change this points at may be an account edit, a customer edit or a
    #: premises edit, and a typed FK would pick one of the three.
    master_data_ref = models.TextField(null=True, blank=True)

    #: The FIELDS that differ from the original payload, as {key: [was, now]}.
    #: The approver reads this; a diff computed at render time could not be
    #: shown on the case a year later.
    changed_fields = models.JSONField(default=dict)

    created_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="created_by"
    )
    #: BR-TEN-043 — the business date, supplied. `created_at` is when the row
    #: was written and they are not the same fact.
    reissued_on = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "invoice_document_instances"
        indexes = [
            models.Index(fields=["tenant", "invoice"], name="ix_doc_instances_invoice"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "invoice", "instance_no"],
                name="uq_doc_instance_per_invoice",
            ),
            models.CheckConstraint(
                condition=Q(instance_no__gte=1),
                name="ck_doc_instance_no_positive",
            ),
        ]


#: DEF-BIL-10091 — the three bulk Fix a bill acts that run as background jobs.
JOB_ACT_PREVIEW = "preview"
JOB_ACT_SEND = "send"
JOB_ACT_ISSUE = "approve_issue"
JOB_ACTS = (JOB_ACT_PREVIEW, JOB_ACT_SEND, JOB_ACT_ISSUE)


class CorrectionJob(models.Model):
    """ONE bulk Fix a bill act run in the background — `DEF-BIL-10091`.

    A bulk preview, Send and Approve-and-issue each took about three minutes on
    38 bills, and a production web worker is killed at sixty seconds. Decision
    log 2026-10-13 (*FIX A BILL RELEASED IN 2.573.0*): bulk runs as a JOB, with
    progress on screen. The `jobs` row (`core.jobs`) carries the status and
    the progress a screen polls; THIS row carries what the act is about and
    what it produced, because the job kernel stores no answer.

    * `preview` — the scope, the rows, the business date, and the answer:
      `answer` holds the totals and every section of the A3 answer EXCEPT the
      per-bill rows, which are `CorrectionJobBill`s so a page of a 40,000-bill
      preview is one indexed read (`NFR-3`). `built` holds what Send needs to
      open the case from this preview without pricing again.
    * `send` — `source` is the preview it opens from; `case` the case it opened.
    * `approve_issue` — `case` is the case approved and issued; `result` the
      per-bill succeeded / failed / skipped lists.

    `refusal` is a refusal the act met — *"Figures changed. Check again."* —
    by `message_key`, which the screen translates. A refusal is the act's
    ANSWER, so the job itself succeeds; `jobs.error` is kept for faults.

    **NO MONEY IS WRITTEN HERE.** The figures are the preview's, held as the
    clerk saw them, exactly as `correction_cases.preview` holds them after Send;
    nothing on this row posts, issues or allocates. BR-BIL-014 (no money-bearing
    write before approval) is therefore untouched, and a preview a clerk walks
    away from blocks no bill (BR-BIL-048 reads `correction_case_bills` only).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    job_id = models.UUIDField(null=True, blank=True)
    act = models.TextField()
    scope = models.JSONField(default=dict)
    items = models.JSONField(default=list)
    as_of = models.DateField(null=True, blank=True)
    preview_hash = models.TextField(null=True, blank=True)
    answer = models.JSONField(null=True, blank=True)
    built = models.JSONField(null=True, blank=True)
    source = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, db_column="source_id"
    )
    case = models.ForeignKey(
        CorrectionCase, on_delete=models.PROTECT, null=True, blank=True, db_column="case_id"
    )
    refusal = models.JSONField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True)
    created_by_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "billing"
        db_table = "correction_jobs"
        indexes = [
            models.Index(fields=["tenant", "job_id"], name="ix_corr_jobs_job"),
            models.Index(fields=["tenant", "case"], name="ix_corr_jobs_case"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(act__in=JOB_ACTS),
                name="ck_correction_job_act",
            ),
        ]


class CorrectionJobBill(models.Model):
    """ONE bill of a background bulk PREVIEW, in the order the screen pages it.

    `row` is the A3 `bills[]` entry the screen draws (with the bill's impact
    merged under it, as the one-request preview served it); `impact` is the
    BillImpact Send pins on `correction_case_bills`. Paged by `position`
    (`NFR-3`): no cap on how many a preview may hold (`NFR-5`).

    TWO ORDERS, BOTH KEPT. `position` is the order the screen shows (warned
    bills first, then the largest movement — BR-BIL-046); `seq` is the order
    the bills were priced in, which is the order Send creates the case's rows
    in and approval executes them in, so the bills of one account draw on
    carried credit in the order Check promised (`DEF-BIL-10087`)."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    job = models.ForeignKey(
        CorrectionJob, on_delete=models.CASCADE, db_column="correction_job_id", related_name="bills"
    )
    position = models.IntegerField()
    seq = models.IntegerField()
    invoice_id = models.UUIDField()
    row = models.JSONField(default=dict)
    impact = models.JSONField(default=dict)

    class Meta:
        app_label = "billing"
        db_table = "correction_job_bills"
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "job", "position"), name="uq_correction_job_bill_position"
            ),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-016@c41f9a2 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/07-billing/06-epics/EP-BIL-04-corrections.md · 04-docs/05-modules/07-billing/02-business-rules.md · 04-docs/02-decisions/02-database-design-brief.md Addendum r10 #9/#13/#15 · 08-qa/01-e2e/journeys/J11-bulk-correction.md)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — models only; the S30 endpoints are US-BIL-015/016's API half and no correction endpoint exists) E=deferred(no-frontend-half — S30's Fix-a-bill tab is unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report for the verbatim run — ruff · black · makemigrations --check · pytest · run_gates
# exceptions: (1) ~~NO `invoices.corrects_invoice_id` IS ADDED. The PO ruled the
#         rebill link lives "in Histrory log only - at account level" (OQ-120,
#         2026-08-11), and `correction_case_bills.rebill_invoice_id` is the
#         CASE's record of what it produced, not a chain edge on `invoices`.~~
#         **SUPERSEDED 2026-08-12 (PO, OQ-120 CLOSED — "Nod to add the link on
#         the new bill").** The column EXISTS as of migration `0017` and lives
#         on the REPLACEMENT. The second sentence still stands:
#         `correction_case_bills.rebill_invoice_id` remains the case's record
#         and is still not a chain edge. See this module's docstring.
#         (2) `invoice_document_instances` IS NOT IN ADDENDUM r10 — it is the
#         table OQ-103's closure created, an Eng-Lead DDL call under r10 #15,
#         recorded in 12-governance/02-decision-log.md rather than only here.
#         (3) THE REASON-CODE LOOKUP (r10 #13) AND ITS `class` COLUMN ARE NOT
#         BUILT HERE. They are US-BIL-017's table; this lane holds the seeded
#         map in `correction_reasons.py` and refuses any code it cannot class,
#         so BR-BIL-041's guarantee holds one layer up. REPORTED.
#         (4) These classes are in their own module, not `models.py` — the
#         `apps/payments/bankrec_models.py` precedent, for the same reason.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
