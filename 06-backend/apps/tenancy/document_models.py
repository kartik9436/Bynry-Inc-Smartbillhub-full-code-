# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 1 — THE DOCUMENT STORE. Step 5c: "everything on that
#           list is blocked on the same missing thing: THERE IS NOWHERE TO PUT
#           A DOCUMENT."
# Rules:    BR-NOT-027 (PO 2026-08-30 — a legal document is frozen AS THE
#           DOCUMENT when it is sent, not re-rendered from data) · BR-NOT-025
#           (a version any sent document points at is archived, never deleted —
#           the pin is PROVENANCE; THIS table is the document) · BR-BIL-030
#           (the bill's INPUTS are frozen — unchanged, and not this) ·
#           BR-CUS-044 (the e-signed agreement) · BR-LED-019 (remittance
#           receipts) · BR-TEN-031 (the owning module publishes the callable
#           its neighbours use) · NFR-33 (GENERATED vs STORED ARTIFACTS) ·
#           NFR-35 (write-once immutable object lock, 7-year retention) ·
#           CLAUDE.md rule 1 (tenant scoping, RLS FORCE) · rule 4 (financial
#           immutability — corrections are new rows) · rule 7 (audit)
# Tests:    06-backend/tests/test_cr049_t1_document_store.py
# Impacts:  CR-049 task 2 (the dispatcher stores at send) · task 3 (a reprint
#           serves the stored copy) · task 4 (the bill at issue) · task 6 (the
#           e-signed agreement). NONE of them is built here — nothing writes
#           into this store yet, and that is the deliberate scope of task 1.
# ───────────────────────────────────────────────────────
"""The one place a rendered document is kept, and the record that proves it.

WHY THIS TABLE IS TENANCY'S, AND WHY IT IS NOT `notifications`' OR A NEW MODULE
-------------------------------------------------------------------------------
A judgment made under hard-won law 13, written down here so it can be disputed
here rather than rediscovered.

**A stored document is produced by SIX modules, not one.** `NFR-33`'s
STORED-ARTIFACTS list is *"e-signed agreements (BR-CUS-044), uploaded exemption
certificates (BR-CUS-063), remittance receipts (BR-LED-019), account documents
(BR-CUS-036), import source files (BR-MET-017/BR-PAY-023), tenant logos"* —
customers, ledger, metering and payments. `CR-049` step 5b adds the bill
(billing) and the notice, the letter and the receipt (notifications). No domain
module owns more than a fraction of that list.

So hosting the table inside any one producer makes the other five either cross
a boundary B2 §2 forbids, or call a service whose module name is wrong for what
they are storing. **A customer's signed payment-plan agreement filed by the
notifications module reads as a mistake — and the reader who believes it is a
mistake writes a second store.** A second store is the one outcome this table
exists to prevent, because then *"which copy is the document"* has a different
answer per module.

**Tenancy is where this product already keeps its platform capabilities**, and
that is not a stretch — it is the shape of the module already. Tenancy owns
`jobs` (every module dispatches into it through `core.jobs`), `number_series`
(every module allocates through `core.numbering`), `user_preferences`,
`custom_field`, `import_mappings` and `holiday_calendars`. (This list named
`bell_events` until 2026-09-03; that table is gone — DEF-3422 — and the point it
was making is unaffected.)
Every one is a capability the whole product uses and no domain owns, published
as a callable its neighbours import — which is exactly `BR-TEN-031`'s posture
and exactly what a document store is.

It also already holds the ONE stored artefact this backend has today:
`tenants.logo_bytes`, which is itself on `NFR-33`'s list.

**A fifteenth app was written first and then withdrawn**, and the reason is
worth keeping: `G27` fails any module over 200 engine lines that serves no
mounted route, deliberately and with no exemption file, because *"a module at
zero is invisible to every completeness measure the repo computes"*. A document
store has no route of its own until `CR-049` task 3 builds one, so a standalone
module would have shipped merge-blocked on day one. Hosting it in a routed
platform module costs nothing and keeps `G27` honest.

**Cross-module writes stay forbidden.** Billing, notifications, customers,
ledger, metering and payments call `apps.tenancy.document_store.store(...)`;
nothing outside this module touches `StoredDocument` and nothing inside it
touches theirs. This file imports no other app's models — the tenant is a
string FK, which is B2 §2's reviewed interface set.

WHAT THIS TABLE IS, IN ONE SENTENCE
------------------------------------
It is the METADATA — who, what, when, where the bytes are, and what they hashed
to. **The bytes are not in this table and are not in PostgreSQL at all** (PO
ruling 2026-08-30: *"we will need storage - on cloud - define proper
engineering for it"*). They live behind `apps.tenancy.document_storage`, whose
production backend is an S3-compatible object store.

THE WORKED FIGURE, RE-DERIVED HERE RATHER THAN COPIED
------------------------------------------------------
A utility at the top of our stated range is 3,000 connections, billed monthly:

    3,000 × 12                      =  36,000 bills a year
    36,000 × 60 KB                  =    2.16 GB
    36,000 receipts × 30 KB         =    1.08 GB
    ~4,000 notices × 40 KB          =    0.16 GB
                                       ─────────
                                         3.40 GB a year
    × 7 (NFR-35's retention)        =   23.8 GB for ONE utility

    100 such utilities averaging half that:
    100 × (3.40 ÷ 2) × 7            =  1,190 GB — on the order of a TERABYTE

In PostgreSQL that terabyte is in every backup, every restore and every vacuum.
In object storage at standard rates ($0.023 per GB-month) it is

    1,190 × 0.023                   =  $27.37 a month

and with a lifecycle rule moving anything older than a year to cold storage
($0.004 per GB-month):

    170 GB hot × 0.023 + 1,020 GB cold × 0.004  =  $3.91 + $4.08  =  $7.99

— about **$8 a month for a hundred utilities' seven-year archive.** That is the
whole argument for the seam, and it is why the key layout below is DATED: a
lifecycle rule moves cold objects **without reading this table**.

BULK EXPORT — AND WHY "NEVER LIST THE BUCKET" IS WHAT MAKES IT POSSIBLE
------------------------------------------------------------------------
PO ruling 2026-08-30, verbatim: *"if we want to just download all documents for
given utility - we should able to do it quickly"*. **That export is its own
task in `CR-049` and is NOT built here.** What is built here is the two things
it needs from this table, because both are cheap now and a migration later.

**A reader who has just read the rule below will worry that it blocks the
export. It does the opposite.** *"Never list the bucket"* is not a limitation
the export has to work around — the metadata table IS the index, and a better
one than a bucket listing could ever be. A listing returns keys and byte
counts: a folder of UUIDs. This table returns *this is the March bill for
account ACC-1042, it hashed to abc…, it is 61 KB of PDF and it was stored on
the 3rd*. That difference is the whole difference between an export a utility
can use and a directory it cannot.

**THE ARITHMETIC, re-derived rather than assumed**, because it decides what
"quickly" can mean. A 3,000-connection utility, seven years in:

    252,000 bills  +  252,000 receipts  +  28,000 notices  =  532,000 documents
    at 3.40 GB a year × 7                                  =  23.8 GB

    fetched one at a time at ~30 ms each:
    532,000 × 0.030 s   =  15,960 s  =  4.4 HOURS of pure latency
    fetched 100 in parallel:
    15,960 ÷ 100        =     160 s  =  2.7 MINUTES

So *"quickly"* is decided by three things and **the folder layout is none of
them**: enumerate from the database, fetch in parallel, and never proxy the
bytes through this application. The two columns below serve the first.

  * **`display_name`** — the human name, because 532,000 files called
    `0198f3c2-…` are not an export. **The database is the only place that will
    ever know it; the object store never will.**
  * **an index on `(tenant, stored_at)`** — the manifest query IS the export,
    and an unindexed scan of half a million rows is where those hours come
    back.

⚠ TENANT SEPARATION IS THIS ROW. IT IS NOT THE KEY PREFIX.
-----------------------------------------------------------
The storage key begins `t/<utility web name>/` (`CR-160-BRC10`, 2026-10-02 —
`t/<tenant_id>/` before that, and older rows still carry it), and **that is a
naming convention and nothing more.** An object store has no row-level security; a prefix is a string
in a name. What actually prevents a cross-tenant read is that **the only way to
learn a key is to read a row of this table, and this table is RLS
`FORCE`-scoped.** So, and each of these is enforced in
`apps/tenancy/document_store.py` rather than merely asked for here:

  * never list the bucket — the read path is always a database query;
  * never derive a key from a tenant id a caller supplied;
  * never accept a storage key as an input parameter.

A caller in tenant A asking for tenant B's document gets **the same answer** as
one asking for a document that does not exist. Existence must not leak (HR-1).

WRITE-ONCE IS ENFORCED TWICE, AND THE TWO PROTECT DIFFERENT THINGS
-------------------------------------------------------------------
`0026_rls_document_store` puts a trigger on this table that refuses **every**
UPDATE and **every** DELETE — modelled on `billing/migrations/0006`'s invoice
immutability trigger, at the database, because a Python guard is bypassed by
the next `.save()`, by a shell, by a data migration and by any endpoint a
future lane writes.

`NFR-35`'s object lock (WORM, seven-year retention) is configured on the bucket
and protects the BYTES. **The trigger protects the record; the lock protects
the bytes; neither substitutes for the other** — a record with no bytes and
bytes with no record are both unprovable, which is the entire point of freezing
a legal document.

⚠ **THE LOCK HALF IS SUSPENDED 2026-10-02 (`CR-160-BRC10`, PO: *"we dont want
this to be enabled right now - dont lock it"*).** No object is locked now —
legal files included — so today only the TRIGGER holds: the product deletes no
record and no file, but someone with direct access to the storage account
could. Switching the lock back on (`DOCUMENT_STORAGE_OBJECT_LOCK_MODE`) covers
files written after that moment only.

A CORRECTION IS A NEW ROW, exactly as hard rule 4 says of an invoice. A
reissued bill is a new invoice and therefore a new document; a letter sent
again is a new outbound message and therefore a new document. Nothing here is
ever edited.
"""

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

# ═══════════════════════════════════════════════════════════════════════════
# THE VOCABULARIES — each a CHECK constraint, deliberately
# ═══════════════════════════════════════════════════════════════════════════
#
# A kind that is not on this list is a document nobody has ruled on, and letting
# one in silently is how a document store becomes a junk drawer with no answer
# to "is this the letter?". Adding a kind is a migration and a decision-log row.
# That friction is the feature, and it is the same posture `export_batches`
# takes with `ck_export_batches_target`.

#: The twelve kinds `CR-049` step 5b puts INSIDE the freeze (PO 2026-08-30).
#: A final bill and a corrected/reissued bill are both `bill` — they are
#: different INVOICES, so they are different rows, which is hard rule 4's
#: "corrections are new rows" arriving here for free.
KIND_BILL = "bill"
KIND_DISCONNECT_NOTICE = "disconnect_notice"  # all three tiers; the 48-hour certified one first
KIND_DUNNING_LETTER = "dunning_letter"
KIND_PAYMENT_RECEIPT = "payment_receipt"
KIND_FAILED_PAYMENT_NOTICE = "failed_payment_notice"
KIND_PLAN_INSTALMENT_DUE = "payment_plan_instalment_due"
KIND_PLAN_INSTALMENT_MISSED = "payment_plan_instalment_missed"
KIND_PLAN_VOIDED = "payment_plan_voided"
KIND_MOVE_IN_WELCOME = "move_in_welcome"
KIND_MOVE_OUT_FINAL_BILL = "move_out_final_bill"
KIND_PLAN_CHANGE_CONFIRMATION = "plan_change_confirmation"
KIND_PAYMENT_PLAN_AGREEMENT = "payment_plan_agreement"  # BR-CUS-044, e-signed

#: `NFR-33`'s STORED ARTIFACTS that `CR-049` step 5b does not name, because they
#: are not documents this product SENDS — they are documents it RECEIVES and
#: cannot re-render. `NFR-35` puts the last of them in the legal-instrument
#: class beside the agreement above.
KIND_EXEMPTION_CERTIFICATE = "exemption_certificate"  # BR-CUS-063
KIND_REMITTANCE_RECEIPT = "remittance_receipt"  # BR-LED-019
KIND_ACCOUNT_DOCUMENT = "account_document"  # BR-CUS-036
KIND_IMPORT_SOURCE_FILE = "import_source_file"  # BR-MET-017 / BR-PAY-023

# ───────────────────────────────────────────────────────────────────────────
# OQ-1164, CLOSED 2026-08-30 — EVERY CUSTOMER DOCUMENT IS FROZEN AT SEND
# ───────────────────────────────────────────────────────────────────────────
#
# The sixteen kinds above were `CR-049` step 5b's scope table. Measured against
# the template catalogue on 2026-08-30: **41 template classes exist, 21 are named
# by that table and 20 are not**, and the dispatcher HELD all twenty rather than
# guessing a kind — correctly, because this list is a CHECK constraint and a
# guess here writes a wrong answer into a seven-year legal record.
#
# The recommendation was put to the Product Owner in plain English — keep all of
# them, because storage is a few kilobytes a message and the risk runs one way
# only: keeping a document you did not need costs almost nothing, and failing to
# keep one you did need loses it permanently. They ruled, verbatim:
#
#     "My recommendation is to keep all of them. - OKY KEEP THEM"
#
# ⚠ **NINETEEN OF THE TWENTY, NOT ALL TWENTY.** The twentieth is
# `staff_bulk_summary`, the in-app staff summary, which the same PO ruled out by
# CHANNEL on 2026-08-26 — *"we dont have to worry about in-app message those are
# mostly FYI ; hence we dont have worry about them"*. **A ruling on a LIST does
# not overturn a ruling on a CHANNEL**, and `in_app` is absent from `CHANNELS`
# below for the same reason. Adding it here would manufacture two genuine PO
# answers that disagree.
#
# ⚠ **NINETEEN CLASSES BECOME SEVENTEEN KINDS, AND THAT IS NOT A MISCOUNT.** A
# kind names the DOCUMENT; `channel` is its own column. That is why the 21 ruled
# classes already collapse onto 12 kinds — `sms_disconnect` and
# `disconnect_notice_48_hour` are both `disconnect_notice`. Two of the nineteen
# pairs collapse the same way: the printed statement and the statement email are
# one document (A19 rule 1 legislates for BOTH — *"both the printed statement and
# the statement email must say nothing is due"*), and bill-ready on email and on
# SMS is one document. Splitting either would encode the channel into the kind
# and leave a regulator asking for "the statement" having to know to ask twice.
# The reasoning and both figures are in `12-governance/02-decision-log.md`.

#: Billing documents that are not the bill itself.
KIND_STATEMENT = "statement"  # the printed statement AND the statement email
KIND_BILL_READY_NOTICE = "bill_ready_notice"  # "your bill is ready", email + SMS
KIND_CORRECTED_BILL_NOTICE = "corrected_bill_notice"
KIND_BILL_INSERT = "bill_insert"

#: Money movements a customer is told about in writing.
KIND_REFUND_CONFIRMATION = "refund_confirmation"
KIND_CREDIT_NOTE_CONFIRMATION = "credit_note_confirmation"
KIND_DEPOSIT_NOTICE = "deposit_notice"  # the LETTER about a deposit…
KIND_WRITEOFF_NOTICE = "writeoff_notice"

#: Account lifecycle.
KIND_ACCOUNT_CLOSED_LETTER = "account_closed_letter"
KIND_AUTOPAY_CONFIRMATION = "autopay_confirmation"

#: Signed instruments, beside `KIND_PAYMENT_PLAN_AGREEMENT` above. ⚠ These are
#: CONTRACTS and are distinct from the letters that announce the same subject:
#: `deposit_agreement` is a signed instrument, `deposit_notice` is a letter.
KIND_SERVICE_AGREEMENT = "service_agreement"
KIND_DEPOSIT_AGREEMENT = "deposit_agreement"  # …and the signed instrument
KIND_AUTOPAY_AUTHORIZATION = "autopay_authorization"

#: Field service. ⚠ **THE WORDING EXISTS AND THE FLOW DOES NOT.** No writer
#: queues any of these four — the work-order flow is R5 scope (`OQ-249`) and
#: this ruling explicitly does NOT authorise building it. A kind here says only
#: what the PO ruled: *when* one of these is sent, it is kept. Nothing else was
#: needed to honour that, so nothing else was built (see `catalogs.py`, "Service
#: & field (4)": *"wording can exist before the flow that sends it"*).
KIND_SERVICE_APPOINTMENT = "service_appointment"
KIND_SERVICE_WORK_COMPLETED = "service_work_completed"
KIND_SERVICE_OUTAGE_NOTICE = "service_outage_notice"
KIND_SERVICE_DOOR_HANGER = "service_door_hanger"

#: Field WORK — what a technician's phone sends back, and the report a
#: supervisor's Accept freezes (`CR-070` wave K, `BR-WRK-047`). ⚠ **THESE ARE
#: NOT THE FOUR ABOVE AND THE DIFFERENCE IS THE DIRECTION.** The four above are
#: letters the utility SENDS to a customer about a visit; these three are
#: EVIDENCE the visit produced — a photograph of a meter dial, the customer's
#: signature on the glass, the frozen report of what was done. A door hanger
#: the utility posts through a letterbox is `service_door_hanger`; a photograph
#: OF that door hanger, taken to prove a refused signature, is
#: `work_order_photo`. A lane reaching for the nearest-sounding value would get
#: the wrong one, so both halves are written out here.
#:
#: ⚠ **HOW LONG THEY ARE KEPT IS RULED AND IS NOT SEVEN YEARS** — twelve
#: months, then an export before deletion (`BR-WRK-048`, PO 2026-09-04 on
#: `OQ-WRK-1496`). `apps/work/work_documents.py` holds the regime; nothing is
#: pruned yet because the export does not exist. Do not describe these as
#: permanent, and do not let them inherit `retention_years()`' seven without
#: reading that module first.
KIND_WORK_ORDER_PHOTO = "work_order_photo"
KIND_WORK_ORDER_SIGNATURE = "work_order_signature"
KIND_WORK_ORDER_REPORT = "work_order_report"

#: ONE FILE A CLERK ATTACHED TO A SERVICE REQUEST — the proof of identity, the
#: deed, the site plan an applicant brought to the counter. The PO ruled the
#: capability in with *"you will have to reduce the size and save them on cloud
#: container etc"*; until then the capture screen said *"We cannot take a file
#: yet — there is nowhere to store it"*, which was true.
#:
#: ⚠ **NOT `KIND_ACCOUNT_DOCUMENT`, AND THE DIFFERENCE IS NOT COSMETIC.** A
#: service request very often has NO ACCOUNT — a new-connection applicant is
#: not a customer yet, which is the entire reason they are filling one in. A
#: document filed under the account kind would be claiming an account that does
#: not exist, and the request is the only thing it can honestly hang off.
#:
#: ⚠ **RETENTION IS `retention_years()`' SEVEN AND IS NOT RULED SEPARATELY.**
#: These are the evidence a supply decision was made on, so they sit with the
#: financial records rather than with a job's photographs — `BR-WRK-048`'s
#: twelve months is about a picture of a gasket and does not reach here. If a
#: utility ever asks for a shorter window on applicant paperwork that is a new
#: ruling, not an inference from this line.
KIND_SERVICE_REQUEST_DOCUMENT = "service_request_document"

#: ONE SUPPLIER'S INVOICE, ATTACHED TO THE PURCHASE IT SETTLES — `P5.11` of the
#: Finance blueprint (p064, screen 5·3a *Capture*). `supplier_invoices` has 21
#: columns and not one of them holds a document, so a captured purchase carried
#: the supplier's name and a free-text `reference` while the PDF that settles
#: the argument lived in somebody's inbox. 5·2 *Bought vs billed* argues about a
#: supplier's figure and could not open the document that decides it.
#:
#: ⚠ **THE BLUEPRINT CALLS THIS *"the platform's first general attachment"* AND
#: THAT IS FALSE — `DEF-LED-6527`.** The store has existed since `CR-049`, with
#: six calling modules and three live capture screens, and four of the five
#: things the blueprint said this task would bring are already built: storage,
#: tenant-scoped access, a 10 MB cap and a type allowlist. Virus posture is
#: RULED AWAY, twice (PO 2026-09-23). So this is two names and a migration, not
#: a spike.
#:
#: ⚠ **RETENTION IS RULED: SEVEN YEARS, THE STORE'S OWN SCHEDULE
#: (`BR-LED-799`, PO 2026-09-25 — `OQ-LED-12628` CLOSED).** This note read
#: *"RETENTION IS `OQ-LED-12628` AND IT IS OPEN … an argument to put to the PO,
#: not an answer a lane may adopt"*. **The question was put and answered**,
#: verbatim: *"Seven years, same as tax receipts"*. So a `supplier_invoice` is
#: kept write-once for `document_storage.retention_years()`' SEVEN YEARS under
#: Object Lock `COMPLIANCE` (⚠ the LOCK is suspended for every kind from
#: 2026-10-02 by `CR-160-BRC10` — the row stays write-once and the product
#: deletes nothing; the seven-year period is unchanged) — the SAME call and the SAME schedule as
#: `SOURCE_TAX_REMITTANCE` two values down, which is one mechanism serving two
#: classes rather than two rules. Nothing here writes a retention rule and
#: nothing should: there is no second control to build. ⚠ **THE RULING IS THE
#: PERIOD ONLY** — size, accepted types and behaviour at expiry were not shown
#: to the PO. ⚠ **AND THE 2026-09-23 `audit_log` RULING STILL DOES NOT CARRY
#: OVER**; it is about AUDIT ROWS and the two schedules differ on purpose.
KIND_SUPPLIER_INVOICE = "supplier_invoice"

#: ── `DEF-NOT-8450` (2026-09-30) — THE TWELVE MESSAGE CLASSES ADDED 12–27
#: SEPTEMBER, KEPT UNDER THE PO'S `OQ-1164` RULING OF 2026-08-30 (*"My
#: recommendation is to keep all of them. - OKY KEEP THEM"* — *"kept, not judged
#: one by one"*). Recorded as a coordinator judgement in the decision log on
#: 2026-09-30 and NOT put back to the PO (hard-won law 13).
#:
#: Twelve classes, TEN new kinds, grouped by the rule the 2026-08-30
#: *"seventeen filing categories"* judgement set: **a kind names the DOCUMENT
#: and `channel` is its own column**, so one document on two channels, or one
#: document with a variant, is one kind; two documents at different stages of
#: a process are two kinds, as the payment-plan due / missed / voided notices
#: are. So:
#:   * the two service-request acknowledgements (with and without a fee taken)
#:     are ONE document — "we received your request" — and share a kind;
#:   * received, more-needed, approved and refused are FOUR stages and four
#:     kinds, exactly as the three payment-plan notices are three;
#:   * the buyer's and the seller's letters on a property sale go to different
#:     people and say different things — two kinds;
#:   * the SMS telling a buyer a meter visit is coming is an appointment notice
#:     and REUSES `service_appointment` rather than minting an eleventh kind
#:     (the frozen-documents map says so beside it);
#:   * the scheduled-report email goes to STAFF, not a customer, and is kept
#:     anyway for the one-way-risk reason the PO's ruling gives: keeping a
#:     document you did not need costs almost nothing, failing to keep one you
#:     did need loses it for good.
KIND_ACCOUNT_MESSAGE = "account_message"  # a clerk's own note to a customer
KIND_SERVICE_REQUEST_ACKNOWLEDGEMENT = "service_request_acknowledgement"
KIND_SERVICE_REQUEST_MORE_INFO = "service_request_more_info"
KIND_SERVICE_REQUEST_APPROVED = "service_request_approved"
KIND_SERVICE_REQUEST_REFUSED = "service_request_refused"
KIND_NEW_CONNECTION_QUOTE = "new_connection_quote"
KIND_NEW_CONNECTION_CONFIRMATION = "new_connection_confirmation"
KIND_PROPERTY_SALE_BUYER_LETTER = "property_sale_buyer_letter"
KIND_PROPERTY_SALE_SELLER_LETTER = "property_sale_seller_letter"
KIND_SCHEDULED_REPORT_NOTICE = "scheduled_report_notice"
#: `CR-182-BRC10` (2026-10-14) — the email telling a customer a reading was
#: flagged high. Kept under `OQ-1164`'s *"keep all of them"*; filed under
#: `metering`, the module that owns the reading it is about.
KIND_HIGH_USAGE_ALERT = "high_usage_alert"
#: `CR-188-BRC10` (2026-10-22) — an ACCOUNT-ACCESS email: a staff invitation or
#: reset link, and the customer portal's reset link and codes. Kept under
#: `OQ-1164`'s *"keep all of them"* — decision log 2026-10-22 *"Account-access
#: emails are KEPT … with the one-time link or code REDACTED in the kept copy"*:
#: the kept copy never holds a usable credential
#: (`notifications.frozen_documents.redact_credentials`).
KIND_ACCOUNT_ACCESS_EMAIL = "account_access_email"

#: ONE HELP DOCUMENT ON A WORK ORDER TEMPLATE — the SOP, the wiring diagram, the
#: manufacturer's sheet a technician opens on the job (`CR-168-BRC10` P3.14, PO
#: ruling 6 of 24 Sep: *"help can be an uploaded document or a video link"*).
#: Until 2026-10-04 the only Work upload was scoped to a WORK ORDER, which a
#: template does not have, so a *document* help row held a reference to nothing.
#: It is copied onto every job raised from the template (`BR-WRK-008`), and the
#: phone already opens a stored document (`mobile._help_row`).
#:
#: ⚠ **RETENTION IS `retention_years()`' SEVEN AND IS NOT RULED SEPARATELY**
#: (lane SRV-3's judgment, decision log *"CR-168 ROUND 4 · SRV-3"*). It is a
#: reference document the utility wrote, not personal data and not a job's
#: photograph (`BR-WRK-048`'s twelve months is about pictures taken in the
#: field). Jobs raised years ago point at it, so it outliving the template is
#: what keeps an old job's help pack openable.
KIND_WORK_TEMPLATE_HELP = "work_template_help"
#: `CR-168-BRC10` image 33's PROOF column (lane SRV-4, `tenancy/0060`) — the
#: scan or photograph of a technician's certificate, held beside the row that
#: says when it runs out. ⚠ **RETENTION IS `retention_years()`' SEVEN** (lane
#: SRV-4's judgment, decision log *"CR-168 ROUND 5 · SRV-4"*): it is the
#: utility's evidence that the person who did a backflow test in 2026 was
#: certified to do it, and an inspector asks about the JOB's date, not today's
#: — so it must outlive the renewal that replaces it, as long as the jobs do.
KIND_WORK_CERTIFICATE_PROOF = "work_certificate_proof"
#: THE UTILITY'S OWN LOGO — `NFR-33`'s *"tenant logos"*, `CR-172-BRC10` (PO
#: 2026-10-05: *"The uploaded logo is stored in S3, the same way the product's
#: other files are stored"* and *"use common compotent to save logo - dont
#: create seperate code"*). Stored in the `tenancy` folder. An SVG upload is TWO
#: documents on one `source_id` — the cleaned SVG and its PNG rendering for
#: print (`BR-TEN-019`) — which is the *"two representations of one document"*
#: `uq_stored_documents_filed` is written to allow. A replaced logo is NOT
#: deleted: bills issued with it still point at it (`BR-TEN-017`).
KIND_TENANT_LOGO = "tenant_logo"

DOCUMENT_KINDS = (
    KIND_BILL,
    KIND_DISCONNECT_NOTICE,
    KIND_DUNNING_LETTER,
    KIND_PAYMENT_RECEIPT,
    KIND_FAILED_PAYMENT_NOTICE,
    KIND_PLAN_INSTALMENT_DUE,
    KIND_PLAN_INSTALMENT_MISSED,
    KIND_PLAN_VOIDED,
    KIND_MOVE_IN_WELCOME,
    KIND_MOVE_OUT_FINAL_BILL,
    KIND_PLAN_CHANGE_CONFIRMATION,
    KIND_PAYMENT_PLAN_AGREEMENT,
    KIND_EXEMPTION_CERTIFICATE,
    KIND_REMITTANCE_RECEIPT,
    KIND_ACCOUNT_DOCUMENT,
    KIND_IMPORT_SOURCE_FILE,
    # ── OQ-1164 (PO 2026-08-30, "OKY KEEP THEM") — 17 kinds for 19 classes ──
    KIND_STATEMENT,
    KIND_BILL_READY_NOTICE,
    KIND_CORRECTED_BILL_NOTICE,
    KIND_BILL_INSERT,
    KIND_REFUND_CONFIRMATION,
    KIND_CREDIT_NOTE_CONFIRMATION,
    KIND_DEPOSIT_NOTICE,
    KIND_WRITEOFF_NOTICE,
    KIND_ACCOUNT_CLOSED_LETTER,
    KIND_AUTOPAY_CONFIRMATION,
    KIND_SERVICE_AGREEMENT,
    KIND_DEPOSIT_AGREEMENT,
    KIND_AUTOPAY_AUTHORIZATION,
    KIND_SERVICE_APPOINTMENT,
    KIND_SERVICE_WORK_COMPLETED,
    KIND_SERVICE_OUTAGE_NOTICE,
    KIND_SERVICE_DOOR_HANGER,
    # ── CR-070 wave K (2026-09-05) — 33 kinds become 36 ──────────────────
    KIND_WORK_ORDER_PHOTO,
    KIND_WORK_ORDER_SIGNATURE,
    KIND_WORK_ORDER_REPORT,
    # ── a clerk's attachment on a service request (2026-09-19) — 36 → 37 ──
    KIND_SERVICE_REQUEST_DOCUMENT,
    # ── the supplier's own invoice behind a purchase (`P5.11`) — 37 → 38 ──
    KIND_SUPPLIER_INVOICE,
    # ── `DEF-NOT-8450` (2026-09-30) — 12 classes, 10 kinds — 38 → 48 ────────
    KIND_ACCOUNT_MESSAGE,
    KIND_SERVICE_REQUEST_ACKNOWLEDGEMENT,
    KIND_SERVICE_REQUEST_MORE_INFO,
    KIND_SERVICE_REQUEST_APPROVED,
    KIND_SERVICE_REQUEST_REFUSED,
    KIND_NEW_CONNECTION_QUOTE,
    KIND_NEW_CONNECTION_CONFIRMATION,
    KIND_PROPERTY_SALE_BUYER_LETTER,
    KIND_PROPERTY_SALE_SELLER_LETTER,
    KIND_SCHEDULED_REPORT_NOTICE,
    # ── `CR-168-BRC10` P3.14 (2026-10-04) — a template's help document — 48 → 49
    KIND_WORK_TEMPLATE_HELP,
    # ── `CR-168-BRC10` image 33 (2026-10-04) — a certificate's proof — 49 → 50
    KIND_WORK_CERTIFICATE_PROOF,
    # ── `CR-172-BRC10` (2026-10-05) — the utility's logo — 50 → 51
    KIND_TENANT_LOGO,
    # ── `CR-182-BRC10` (2026-10-14) — the high consumption alert — 51 → 52
    KIND_HIGH_USAGE_ALERT,
    # ── `CR-188-BRC10` (2026-10-22) — an account-access email, credential redacted — 52 → 53
    KIND_ACCOUNT_ACCESS_EMAIL,
)

# ───────────────────────────────────────────────────────────────────────────
# `CR-160-BRC10` (PO 2026-10-02) — WHICH MODULE'S FOLDER A FILE IS STORED IN
# ───────────────────────────────────────────────────────────────────────────
#
# The object key is `t/<utility web name>/<module>/<yyyy>/<mm>/<file id>[.ext]`
# (`document_storage.key_for`). PO, verbatim: *"Instead of Fucntion can you do
# it module"*, and on the list below *"yes, as listed - you can cosider others
# module also"*.
#
# ⚠ **THE LIST IS FIXED, LOWERCASE, AND NEVER RENAMED.** It is the CODE module
# name and never the product name ("metering", not "Meter Reads"; "rating", not
# "Plans & Rates"), because a product name changes with the copy and a renamed
# folder splits a utility's old files from its new ones for ever — the key is
# written into the row verbatim and nothing moves objects. A new module joins
# the END of this tuple, with a reason written beside it, and only when a
# document kind truly belongs to it (the PO's own example: runbooks).
STORAGE_MODULES = (
    "billing",
    "payments",
    "customers",
    "metering",
    "rating",
    "ledger",
    "notifications",
    "work",
    "portal",
    "reports",
    "integrations",
    "tenancy",  # the utility's logo (`KIND_TENANT_LOGO`, CR-172-BRC10)
    # EVERY EXPORT FILE — list, report and finance exports, the audit-log export
    # and the bill print set — and nothing else. The one segment that is not a
    # code module, by PO ruling 2026-10-02 (decision log, *"EXPORT FILES MOVE
    # FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*): *"You can take
    # module name as export for all export related actions"*, and *"we decided
    # to create separate folder for export at module level so you can identify
    # export related files from that folder"*. The folder IS how an export is
    # identified: the app's delete permission is `t/*/export/*` and
    # `apps/tenancy/export_storage.py` refuses to delete any other key. No
    # DOCUMENT kind maps here — a stored document is never an export.
    "export",
)

#: EVERY document kind → the ONE module whose folder it is stored in.
#:
#: **THE RULE USED, decided once here so it is not decided per kind later
#: (recorded in the decision log, 2026-10-02):** a kind goes to the module that
#: OWNS THE BUSINESS RECORD THE DOCUMENT IS ABOUT — never the module that
#: happened to send it. Nearly every letter in this product is sent by
#: `notifications`, so filing by sender would put forty kinds in one folder and
#: make the second segment say nothing; filing by subject means
#: `t/<utility>/payments/…` holds every receipt, refund, payment-plan and
#: collections letter, which is the folder somebody actually asks for. The
#: owning tables, checked in code on 2026-10-02:
#:
#:   billing     invoices, credit notes, final bills (`apps/billing`)
#:   payments    payments, refunds, autopay, payment plans, write-offs and the
#:               collections path that sends dunning and disconnect letters
#:               (`apps/payments/collections_models.py`)
#:   customers   accounts, the security deposit (`apps/customers/deposit.py`),
#:               service agreements, service requests, move-in/out, sales
#:   metering    planned and unplanned interruptions (`apps/metering/interruptions.py`)
#:   rating      tax-exemption certificates (`rating.TaxExemptionCertificate`)
#:   ledger      tax remittances and supplier invoices (`apps/ledger`)
#:   work        work orders — the visit letters and the evidence a visit produced
#:   notifications  a clerk's own free-text message, which is about no other record
#:   reports     the scheduled-report email
#:   integrations   a file RECEIVED from outside (a read file, a lockbox file):
#:               import batches exist in four modules, and the one thing every
#:               such file has in common is that another system produced it
#:
#: ⚠ **A PORTAL UPLOAD IS FILED BY ITS KIND, NOT BY ITS DOOR.** A customer's file
#: on a portal application becomes a `service_request_document` at submit, so it
#: is stored under `customers/` beside the same file a clerk attached at the
#: counter. `portal` is on the list for kinds that do not exist yet; `tenancy`
#: holds the utility's logo (`KIND_TENANT_LOGO`, `CR-172-BRC10`).
#:
#: ⚠ **A KIND WITH NO ENTRY IS REFUSED AT STORE TIME**, not defaulted:
#: `module_for_kind` raises, and `tests/test_cr160_storage_key_layout.py` fails
#: the day a kind is added to `DOCUMENT_KINDS` without a line here.
DOCUMENT_KIND_MODULE: dict[str, str] = {
    KIND_BILL: "billing",
    KIND_DISCONNECT_NOTICE: "payments",
    KIND_DUNNING_LETTER: "payments",
    KIND_PAYMENT_RECEIPT: "payments",
    KIND_FAILED_PAYMENT_NOTICE: "payments",
    KIND_PLAN_INSTALMENT_DUE: "payments",
    KIND_PLAN_INSTALMENT_MISSED: "payments",
    KIND_PLAN_VOIDED: "payments",
    KIND_MOVE_IN_WELCOME: "customers",
    KIND_MOVE_OUT_FINAL_BILL: "billing",
    KIND_PLAN_CHANGE_CONFIRMATION: "customers",
    KIND_PAYMENT_PLAN_AGREEMENT: "payments",
    KIND_EXEMPTION_CERTIFICATE: "rating",
    KIND_REMITTANCE_RECEIPT: "ledger",
    KIND_ACCOUNT_DOCUMENT: "customers",
    KIND_IMPORT_SOURCE_FILE: "integrations",
    KIND_STATEMENT: "billing",
    KIND_BILL_READY_NOTICE: "billing",
    KIND_CORRECTED_BILL_NOTICE: "billing",
    KIND_BILL_INSERT: "billing",
    KIND_REFUND_CONFIRMATION: "payments",
    KIND_CREDIT_NOTE_CONFIRMATION: "billing",
    KIND_DEPOSIT_NOTICE: "customers",
    KIND_WRITEOFF_NOTICE: "payments",
    KIND_ACCOUNT_CLOSED_LETTER: "customers",
    KIND_AUTOPAY_CONFIRMATION: "payments",
    KIND_SERVICE_AGREEMENT: "customers",
    KIND_DEPOSIT_AGREEMENT: "customers",
    KIND_AUTOPAY_AUTHORIZATION: "payments",
    KIND_SERVICE_APPOINTMENT: "work",
    KIND_SERVICE_WORK_COMPLETED: "work",
    KIND_SERVICE_OUTAGE_NOTICE: "metering",
    KIND_SERVICE_DOOR_HANGER: "work",
    KIND_WORK_ORDER_PHOTO: "work",
    KIND_WORK_ORDER_SIGNATURE: "work",
    KIND_WORK_ORDER_REPORT: "work",
    KIND_SERVICE_REQUEST_DOCUMENT: "customers",
    KIND_SUPPLIER_INVOICE: "ledger",
    KIND_ACCOUNT_MESSAGE: "notifications",
    KIND_SERVICE_REQUEST_ACKNOWLEDGEMENT: "customers",
    KIND_SERVICE_REQUEST_MORE_INFO: "customers",
    KIND_SERVICE_REQUEST_APPROVED: "customers",
    KIND_SERVICE_REQUEST_REFUSED: "customers",
    KIND_NEW_CONNECTION_QUOTE: "customers",
    KIND_NEW_CONNECTION_CONFIRMATION: "customers",
    KIND_PROPERTY_SALE_BUYER_LETTER: "customers",
    KIND_PROPERTY_SALE_SELLER_LETTER: "customers",
    KIND_SCHEDULED_REPORT_NOTICE: "reports",
    KIND_WORK_TEMPLATE_HELP: "work",
    KIND_WORK_CERTIFICATE_PROOF: "work",
    KIND_TENANT_LOGO: "tenancy",
    KIND_HIGH_USAGE_ALERT: "metering",
    KIND_ACCOUNT_ACCESS_EMAIL: "notifications",
}


def module_for_kind(kind: str) -> str:
    """The storage folder a document of this kind goes in — or a refusal.

    Never a default: a kind somebody added without deciding its module would
    otherwise land in whichever folder a fallback named, and every file written
    before the mistake was noticed stays there (keys are never rewritten).
    """
    module = DOCUMENT_KIND_MODULE.get(kind)
    if module is None or module not in STORAGE_MODULES:
        raise ValueError(
            f"document kind {kind!r} has no storage module. Add it to "
            "DOCUMENT_KIND_MODULE in apps/tenancy/document_models.py, naming one of "
            f"{', '.join(STORAGE_MODULES)} (CR-160-BRC10)."
        )
    return module


#: ⚠ `tenant logo` IS A KIND SINCE 2026-10-05 (`CR-172-BRC10`, `KIND_TENANT_LOGO`
#: above). This note read *"`tenant logo` IS ON `NFR-33`'s LIST AND IS
#: DELIBERATELY NOT A KIND HERE. It already has storage — `tenants.logo_bytes`
#: … and moving it is a migration over live rows that buys this CR nothing."*
#: That was a LANE's choice, never a PO ruling, and the PO reversed it: the
#: logo is stored where every other file is, and `tenants.logo_bytes` is
#: emptied by `tenancy/0061` and dropped in a later release.

#: WHICH ROW this document is about. Six values, because a document is always
#: about exactly one thing, and the read path is a lookup on this pair.
SOURCE_INVOICE = "invoice"  # a bill — billing
SOURCE_OUTBOUND_MESSAGE = "outbound_message"  # a letter / email / SMS — notifications
SOURCE_PAYMENT = "payment"  # a receipt — payments
SOURCE_PAYMENT_PLAN = "payment_plan"  # the e-signed agreement — customers
SOURCE_CUSTOMER_ACCOUNT = "customer_account"  # account documents, certificates — customers
SOURCE_IMPORT_BATCH = "import_batch"  # the source file — metering / payments

#: A field job — the photographs, the signature and the report all hang off the
#: work order that produced them (`CR-070` wave K). ⚠ **IT IS THE ORDER AND NOT
#: THE ACCOUNT, deliberately.** A photograph of a meter dial is evidence about a
#: VISIT: it answers *what did the crew find at 14 Palm Court on 15 March*, and
#: filing it under the customer account would lose which visit it belonged to
#: the moment a second job ran at the same premises. `for_source()` on the order
#: is how `Work-008` lists a job's evidence, and it could not be written any
#: other way round.
SOURCE_WORK_ORDER = "work_order"

#: ⚠ **A PHOTOGRAPH'S SOURCE IS ITS OWN ATTACHMENT ROW, NOT THE ORDER, AND THE
#: REASON IS THE UNIQUE CONSTRAINT TWENTY LINES BELOW THIS ONE.**
#: `uq_stored_documents_stored` allows ONE artefact per
#: `(tenant, source_type, source_id, content_type)`, and its own docstring gives
#: the reason: a bill's PDF and its HTML are two representations of ONE
#: document, and a source carrying two artefacts of the same shape would make
#: *"serve the frozen copy"* a choice, which is a re-render wearing a different
#: coat.
#:
#: **That reasoning is exactly right and it does not describe a job's
#: photographs.** Nine pictures of a meter cupboard are not nine renderings of
#: the work order; they are nine independent facts that happen to share a job,
#: all `image/jpeg`, and under `SOURCE_WORK_ORDER` the second one is refused by
#: the database. Found by `US-WRK-049` TC-3 on 2026-09-05, which uploads two.
#:
#: So a photograph hangs off `work_order_attachments.id` — one document per
#: attachment row, which is trivially unique and honest about what the document
#: is a copy of. The ORDER is still reachable: `work_order_attachments` is the
#: table that says which job a photograph belongs to, which is its whole job.
#: ⚠ **The SIGNATURE and the REPORT stay on `SOURCE_WORK_ORDER`** — there is
#: exactly one signature per order and the report versions differ by
#: `content_type` — so this value is for photographs and nothing else.
SOURCE_WORK_ORDER_ATTACHMENT = "work_order_attachment"

#: ONE FILED DOCUMENT ON A CUSTOMER ACCOUNT — `CR-094-BRC01` wave I, `ACC-S8`,
#: `BR-CUS-036`. ⚠ **IT IS THE `account_documents` ROW AND NOT THE ACCOUNT, FOR
#: EXACTLY THE REASON A PHOTOGRAPH IS ITS ATTACHMENT ROW** (see
#: `SOURCE_WORK_ORDER_ATTACHMENT` above and `tenancy/0040`).
#: `uq_stored_documents_filed` allows ONE artefact per
#: `(tenant, source_type, source_id, content_type)` with a NULL channel, so
#: under `SOURCE_CUSTOMER_ACCOUNT` a clerk's **second** `application/pdf` on one
#: account is refused by the database. That constraint is right and is not
#: widened: its reasoning is about RENDERINGS of one document, and a lease, a
#: driver's licence and a landlord's letter are not three renderings of an
#: account.
#:
#: ⚠ **`SOURCE_CUSTOMER_ACCOUNT` KEEPS ITS COMMENT AND LOSES THE FIRST HALF OF
#: ITS JOB.** It still names the exemption certificate (`BR-CUS-063`), of which
#: there is one per account per authority. A lane reaching for the
#: nearest-sounding value for a FILED account document should take this one.
SOURCE_ACCOUNT_DOCUMENT = "account_document"

#: ONE FILE ATTACHED TO A SERVICE REQUEST — and **it is the
#: `service_request_documents` ROW, NOT THE REQUEST**, for the third time in
#: this file and for exactly the reason the other two give (see
#: `SOURCE_WORK_ORDER_ATTACHMENT` and `SOURCE_ACCOUNT_DOCUMENT` above,
#: `tenancy/0040` and `tenancy/0044`).
#:
#: `uq_stored_documents_filed` allows ONE artefact per
#: `(tenant, source_type, source_id, content_type)` where the channel is NULL,
#: and its reasoning is about RENDERINGS: a bill's PDF and its HTML are two
#: representations of one document, so a source carrying two artefacts of the
#: same shape would make *"serve the frozen copy"* a CHOICE.
#:
#: ⚠ **THAT REASONING IS RIGHT AND IT DOES NOT DESCRIBE A COUNTER.** An
#: applicant for a new connection hands over a driving licence AND a tenancy
#: agreement AND a site plan — three `application/pdf`s on one request, none of
#: them a rendering of the other two. Under `SOURCE_CUSTOMER_ACCOUNT` or a
#: request-scoped source the FIRST would be filed and the SECOND refused by the
#: database, on the most ordinary thing a clerk does.
#:
#: ⚠ **SO THE CONSTRAINT IS NOT WIDENED.** Widening it would weaken a real
#: guarantee on `invoices` for every other module. What is wrong for this case
#: is the SOURCE, not the rule. A document's `source_id` is its own
#: `customers.service_request_documents.id`, which is trivially unique and
#: honest about what the document is a copy of: itself. The REQUEST is not lost
#: — `service_request_documents` is the table that says which request a file
#: belongs to, which is its entire job, and the Documents tab lists from there.
SOURCE_SERVICE_REQUEST_DOCUMENT = "service_request_document"

#: THE PURCHASE a supplier invoice belongs to — `ledger.SupplierInvoice`
#: (`P5.11`). ⚠ **IT IS THE INVOICE AND NOT THE SUPPLIER, deliberately.** A
#: utility buys from one wholesaler every month; filing the PDF under the
#: SUPPLIER would put twelve documents in one place with nothing saying which
#: purchase each settles, and 5·2's argument is always about one figure in one
#: period. `for_source()` on the invoice is how 5·3a lists what it has.
SOURCE_SUPPLIER_INVOICE = "supplier_invoice"

#: THE FILING a receipt belongs to — `ledger.TaxRemittance` (`P4.3`/`P4.4`).
#: `BR-LED-019` requires it: *"remittance records carry a filing CONFIRMATION
#: REF + receipt file attachment (auditor artifact)"*, and until 2026-09-24 the
#: form refused the file BY NAME because there was no row to hang it on —
#: `journal.RECEIPT_HAS_NO_HOME`, which goes with this value.
#:
#: ⚠ **IT IS THE FILING AND NOT THE AUTHORITY, deliberately** — the same
#: reasoning as `SOURCE_SUPPLIER_INVOICE` one value up. A utility files with
#: Bexar County every month; under the AUTHORITY twelve receipts would sit in
#: one place with nothing saying which return each proves, and an auditor's
#: question is always about one period. `for_source()` on the filing is how the
#: Payments-made panel lists what it has.
#:
#: ⚠ **AND IT IS NOT `SOURCE_PAYMENT`.** That value means a `payments` row — a
#: customer paying the utility. A remittance is the utility paying an authority
#: and touches no `payments` row at all; reusing the nearest-sounding value
#: would file a tax receipt among customer receipts and make
#: `for_source(payment)` answer about something else entirely.
#:
#: ⚠ **RETENTION IS `retention_years()`' SEVEN AND IS NOT RULED SEPARATELY** —
#: which, unlike `OQ-LED-12628`'s supplier invoice, is the answer this document
#: already needs: a filing receipt is a tax record, and seven years is the
#: schedule every other tax record in this product is kept on. Stated rather
#: than assumed silently.
SOURCE_TAX_REMITTANCE = "tax_remittance"

#: ONE HELP DOCUMENT ON A WORK ORDER TEMPLATE IS ITS OWN SOURCE (`CR-168-BRC10`
#: P3.14) — the attachment pattern one value up, and for its reason:
#: `uq_stored_documents_filed` allows ONE artefact per (source, content type), so
#: under the TEMPLATE a second PDF (the SOP and the wiring diagram) would be
#: refused. `source_id` is a uuid minted per upload; WHICH template a file
#: serves is said by the help row whose `ref` names it, and the template's
#: content route answers only for a document one of its help rows names.
SOURCE_WORK_TEMPLATE_HELP = "work_template_help"

#: ONE CERTIFICATE PROOF IS ITS OWN SOURCE (`CR-168-BRC10` image 33, lane
#: SRV-4) — the help document's shape and for its reason: a renewal uploads a
#: second scan of the same certificate, and `uq_stored_documents_filed` allows
#: one artefact per (source, content type). `source_id` is minted per upload;
#: WHICH certificate a file proves is said by `technician_certifications.
#: evidence_document_id`, and the content route answers only for that.
SOURCE_WORK_CERTIFICATE_PROOF = "work_certificate_proof"

#: ONE LOGO UPLOAD IS ITS OWN SOURCE (`CR-172-BRC10`) — the help-document
#: shape: `source_id` is minted per upload, so a replacement is a new source and
#: an SVG's two representations share one. WHICH upload is the utility's logo
#: today is said by `tenants.logo_file_id`, and only that row's reference is
#: ever served.
SOURCE_TENANT_LOGO = "tenant_logo"

SOURCE_TYPES = (
    SOURCE_INVOICE,
    SOURCE_OUTBOUND_MESSAGE,
    SOURCE_PAYMENT,
    SOURCE_PAYMENT_PLAN,
    SOURCE_CUSTOMER_ACCOUNT,
    SOURCE_IMPORT_BATCH,
    SOURCE_WORK_ORDER,
    SOURCE_WORK_ORDER_ATTACHMENT,
    SOURCE_ACCOUNT_DOCUMENT,
    SOURCE_SERVICE_REQUEST_DOCUMENT,
    SOURCE_SUPPLIER_INVOICE,
    SOURCE_TAX_REMITTANCE,
    SOURCE_WORK_TEMPLATE_HELP,
    SOURCE_WORK_CERTIFICATE_PROOF,
    SOURCE_TENANT_LOGO,
)

#: The three channels a document can be SENT on. Spelled exactly as
#: `apps.notifications.models` spells them, so the dispatcher (task 2) hands the
#: value straight through and the two vocabularies cannot drift into synonyms.
#: ⚠ `in_app` IS ABSENT ON PURPOSE — PO 2026-08-30, verbatim: *"we dont have to
#: worry about in-app message those are mostly FYI ; hence we dont have worry
#: about them"*. `in_app_messages.body` already stores its own render, so
#: nothing is lost, and a lane sweeping *"freeze every outbound row"* through
#: here finds this sentence rather than a gap.
CHANNEL_PRINT = "pdf_print"
CHANNEL_EMAIL = "email"
CHANNEL_SMS = "sms"
CHANNELS = (CHANNEL_PRINT, CHANNEL_EMAIL, CHANNEL_SMS)


#: WHERE the bytes went. Read on the way back out: a row written by one backend
#: cannot be fetched by another, and a deployment that switches backends without
#: migrating its objects learns that from this column instead of from a 404.
#:
#: ⚠ **`aws_s3`, NOT `s3`** — PO ruling 2026-08-30, verbatim: *"curently we will
#: start with AWS, but we need to keep it multi cloud - google or any other
#: cloud - in future we mght have differnt requirements"*. The value names the
#: CLOUD and not the protocol, because the protocol is portable and **the
#: guarantee is not**: S3 Object Lock, a GCS bucket retention policy and an
#: Azure immutability policy are three different mechanisms behind one promise,
#: and a row that says only `s3` cannot tell you which of them held. A future
#: `gcs` or `azure_blob` is a new value, a migration and a decision-log row.
#: (This column read `s3` for one migration; `0027` renamed it before anything
#: had ever written a row.)
class StoredDocumentImmutable(RuntimeError):
    """Something tried to change or remove a frozen document.

    ⚠ **THIS IS THE SECOND-BEST GUARANTEE, AND IT SAYS SO.** The real one is
    the `stored_documents_write_once` trigger in migration `0026` — a database
    refusal that a shell, a data migration and a future endpoint all meet. This
    class exists for the two things the trigger cannot do: give a Python caller
    a message that names the rule, and hold the same line on **SQLite**, which
    `config/settings/test.py` hardcodes and which has no triggers at all. A
    check that skips silently on the database a developer actually runs is not
    a check.
    """


BACKEND_AWS_S3 = "aws_s3"
BACKEND_FILESYSTEM = "filesystem"
STORAGE_BACKENDS = (BACKEND_AWS_S3, BACKEND_FILESYSTEM)


class StoredDocument(models.Model):
    """One frozen document: the record of it, and the address of its bytes.

    ⚠ **THIS ROW IS NEVER UPDATED AND NEVER DELETED.** The database refuses
    both (`0026_rls_document_store`'s `tenancy_stored_document_write_once`
    trigger). Do not add a `save()` path that expects otherwise; do not add a
    `status` column and reach for it. If a document changes, it is a different
    document and it is a different row.

    THE KEY LAYOUT IS `t/<utility web name>/<module>/<yyyy>/<mm>/<document_id>[.ext]`
    — e.g. `t/austin-water/billing/2026/09/<id>.pdf` — ⚠ **AMENDED 2026-10-02
    BY `CR-160-BRC10` (PO).** It read `t/<tenant_id>/<yyyy>/<mm>/<document_id>`
    (`CR-049` decision 3) until then, and **every row written before that keeps
    the key it was written with**: nothing was moved and no `storage_key` was
    rewritten, so this column holds BOTH shapes and both are read. Its parts:

      * **the utility first** (`tenants.subdomain`, its web name), so one
        prefix is one utility and a bucket policy, an access log or a
        per-utility export can be written against a prefix;
      * **then the owning module** (`DOCUMENT_KIND_MODULE` above), so one
        utility's bills and one utility's work-order photographs are two
        prefixes;
      * **dated**, so a lifecycle rule moves objects older than a year to cold
        storage **without reading this table** — which is what turns the $8 a
        month in the module docstring from theory into a bucket setting.

    It is composed in `document_storage.key_for()` from THIS ROW's own tenant,
    kind and id. It is never composed from an argument and never parsed to
    recover them: a key is an OUTPUT of the row, never an input to it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    #: WHAT this document is (`DOCUMENT_KINDS`). Not derivable from
    #: `source_type`: three different notices all have
    #: `source_type = outbound_message`, and a regulator asks for a KIND — *"the
    #: disconnection letter"* — never for a table.
    kind = models.TextField()

    #: WHICH row it is about. `source_id` is a plain UUID and NOT a foreign key,
    #: for the same reason `invoices.template_id` is not one (BR-NOT-025): it
    #: points into six different modules' tables and PostgreSQL has no
    #: polymorphic FK. **The cost is stated rather than hidden** — nothing at the
    #: database stops a row pointing at an id that no longer exists — and it is
    #: bounded by the fact that every one of those six tables is itself
    #: append-only or `PROTECT`-ed.
    source_type = models.TextField()
    source_id = models.UUIDField()

    #: HOW it reached the customer, or NULL. **NULL is a FACT, not an absence of
    #: knowledge** — it means the document was stored when it was CREATED rather
    #: than when it was SENT. The bill frozen at issue (`CR-049` task 4) is the
    #: case this exists for, and so is a signed agreement, which is filed rather
    #: than posted. A document that WAS sent always carries its channel.
    channel = models.TextField(null=True, blank=True)

    #: The object's address inside the backend below. Never an input, never
    #: parsed — see the class docstring and `document_storage.key_for`.
    storage_key = models.TextField()
    storage_backend = models.TextField()

    #: sha256 of the exact bytes, lowercase hex. `export_batches.content_hash` is
    #: the worked precedent in this codebase — *"the summary rows exactly as
    #: handed over"*. It is written HERE and set as the object's own checksum,
    #: and `document_store.fetch` re-hashes what comes back and refuses a
    #: mismatch: a silent byte change is what the freeze exists to prevent, and
    #: a hash nobody verifies prevents nothing.
    content_hash = models.TextField()
    byte_length = models.IntegerField()
    content_type = models.TextField()

    #: THE HUMAN NAME — `bills/2026/03/ACC-1042-INV-000123.pdf`. Required, and
    #: **SUPPLIED BY THE WRITER, NEVER COMPOSED HERE**, which is a decision and
    #: not an omission: a usable name needs the account number and the invoice
    #: number, and those live in `customers` and `billing`. Composing it in this
    #: module would mean reading two other modules' tables — the cross-module
    #: read B2 §2 forbids — so the only place that CAN compose it is the module
    #: that is already holding the document it is about.
    #:
    #: The recommended shape is `<kind>/<yyyy>/<mm>/<human reference>.<ext>`,
    #: mirroring the storage key so an unpacked export reads like the bucket
    #: without exposing a single storage key. It is **validated, not composed**
    #: (`document_store._require_display_name`): non-empty, no leading slash, no
    #: `..`, under 255 characters.
    #:
    #: **NOT UNIQUE**, deliberately. A corrected bill and the bill it corrects
    #: are two documents about one account in one month and may reasonably carry
    #: names a person cannot tell apart; the id and the hash are what tell them
    #: apart, and forcing a difference here would push a writer into inventing a
    #: suffix that means nothing.
    display_name = models.TextField()

    stored_at = models.DateTimeField(auto_now_add=True)

    #: WHO OR WHAT stored it. Both are nullable and at least one is required
    #: (`ck_stored_documents_actor`): a bill run has no user and a person
    #: uploading a certificate has no job, and *"nobody knows"* is not one of the
    #: answers a legal document may give. `stored_by_process` is a dotted path —
    #: `billing.issue`, `notifications.dispatcher` — so the writer is findable
    #: from the row without reading the audit trail.
    stored_by_user_id = models.UUIDField(null=True, blank=True)
    stored_by_process = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "stored_documents"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=DOCUMENT_KINDS), name="ck_stored_documents_kind"
            ),
            models.CheckConstraint(
                condition=Q(source_type__in=SOURCE_TYPES), name="ck_stored_documents_source"
            ),
            models.CheckConstraint(
                condition=Q(channel__in=CHANNELS) | Q(channel__isnull=True),
                name="ck_stored_documents_channel",
            ),
            models.CheckConstraint(
                condition=Q(storage_backend__in=STORAGE_BACKENDS),
                name="ck_stored_documents_backend",
            ),
            #: A zero-byte document is not a document. It is the shape a failed
            #: render takes, and storing one would make "the letter exists"
            #: true about an empty file.
            models.CheckConstraint(
                condition=Q(byte_length__gt=0), name="ck_stored_documents_length"
            ),
            #: An export of 532,000 files named after their UUIDs is not an
            #: export. An empty name is the shape a writer takes when it did
            #: not think about this, so it is refused rather than defaulted.
            models.CheckConstraint(condition=~Q(display_name=""), name="ck_stored_documents_name"),
            #: A stored document with no author is unprovable. See the fields.
            models.CheckConstraint(
                condition=(
                    Q(stored_by_user_id__isnull=False)
                    | (Q(stored_by_process__isnull=False) & ~Q(stored_by_process=""))
                ),
                name="ck_stored_documents_actor",
            ),
            #: One key, one object. The key is composed from the id, so a
            #: collision means two rows claim the same bytes.
            models.UniqueConstraint(
                fields=["tenant", "storage_key"], name="uq_stored_documents_key"
            ),
            #: ⚠ **ONE ARTEFACT PER (DOCUMENT, CHANNEL, REPRESENTATION), AND
            #: THAT IS WHAT MAKES THE FREEZE MEAN ANYTHING.** If one source
            #: could carry two artefacts of the same shape, *"serve the frozen
            #: copy"* would have to CHOOSE one — and a chooser is a re-render
            #: wearing a different coat. `content_type` is in the key because a
            #: bill legitimately stores a PDF **and** an HTML of the same
            #: document (`CR-049` task 4): two representations of one thing, not
            #: two documents.
            #: **Two constraints rather than one**, because PostgreSQL treats
            #: NULLs as distinct in a unique index, so a NULL channel would not
            #: be constrained at all — the shape `export_batches` already gives
            #: `batch_no`.
            models.UniqueConstraint(
                fields=["tenant", "source_type", "source_id", "channel", "content_type"],
                condition=Q(channel__isnull=False),
                name="uq_stored_documents_sent",
            ),
            models.UniqueConstraint(
                fields=["tenant", "source_type", "source_id", "content_type"],
                condition=Q(channel__isnull=True),
                name="uq_stored_documents_filed",
            ),
        ]
        indexes = [
            #: THE read path: *"give me the document for this bill"*. One indexed
            #: lookup, then one object GET — tens of milliseconds, and it is the
            #: common case the PO named (*"later document retrival become an
            #: issue"*).
            models.Index(
                fields=["tenant", "source_type", "source_id"], name="ix_stored_docs_source"
            ),
            #: THE list path: a tenant's documents of one kind, newest first.
            #: **Always this index, never a bucket listing** — the reasoning is
            #: in `document_store.list_for_kind`.
            models.Index(fields=["tenant", "kind", "stored_at"], name="ix_stored_docs_kind"),
            #: THE EXPORT path: every document this utility holds, newest first
            #: — the manifest query of the bulk export the PO asked for on
            #: 2026-08-30. Half a million rows unindexed is where the 4.4 hours
            #: above come back.
            models.Index(fields=["tenant", "stored_at"], name="ix_stored_docs_all"),
            #: ⚠ THERE IS DELIBERATELY NO SEPARATE `(tenant, kind)` INDEX.
            #: `ix_stored_docs_kind` above is `(tenant, kind, stored_at)`, and
            #: PostgreSQL serves any `(tenant, kind)` lookup from its leftmost
            #: columns. A second index over the same prefix would never be
            #: chosen, and would still be written on every insert.
        ]

    # ── the freeze, restated in Python ──────────────────────────────────
    # The database is what enforces this (migration 0026's trigger). These two
    # exist so that a Python caller gets a sentence naming the rule instead of
    # a `psycopg` error, and so the guarantee is also asserted on SQLite, which
    # the test settings hardcode and which has no triggers.
    #
    # ⚠ **NEITHER OF THESE CAN BE THE GUARANTEE, AND THE REASON IS worth
    # knowing rather than trusting:** `QuerySet.update()` and
    # `QuerySet.delete()` do not call them. They emit SQL directly, which is
    # precisely the shape hard-won law 1 warns about — a Python guard that
    # reads like a lock. On PostgreSQL the trigger catches those too; on SQLite
    # nothing does, and that is stated here rather than discovered.

    def save(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if not self._state.adding:
            raise StoredDocumentImmutable(
                f"stored document {self.pk} cannot be updated (BR-NOT-027, NFR-35). "
                "What the customer read is frozen at the moment it was stored; a "
                "correction is a NEW row, exactly as it is for an invoice."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise StoredDocumentImmutable(
            f"stored document {self.pk} cannot be deleted (BR-NOT-027, NFR-35). It is "
            "the document a customer was sent, kept as evidence for seven years."
        )

    def __str__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.kind} {self.source_type}:{self.source_id}"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 task 1 (sources: 12-governance/11-change-requests.md CR-049 steps 5b/5c/5d(e) · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-027 · 04-docs/02-decisions/06-non-functional-requirements.md NFR-33/NFR-35 · 12-governance/02-decision-log.md 2026-08-30 · 06-backend/apps/ledger/models.py ExportBatch, the worked precedent)
# generated: 2026-08-30 by the CR-049 task 1 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — nothing writes into this store until CR-049 task 2, and no endpoint serves it until task 3) E=deferred(no-frontend-half — CR-049 task 3) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the write-once trigger and the RLS policy were each shown REFUSING on live PostgreSQL and each shown ACCEPTING with the guard dropped. Verbatim transcripts in 06-backend/tests/test_cr049_t1_document_store.py and the lane report.
# exceptions: (1) TENANCY HOSTS AND OWNS IT — the argument is the module docstring's first section, and a standalone `documents` app was written and withdrawn because G27 fails a 200-line module with no mounted route. (2) `source_id` is a plain UUID, not an FK: it points into six modules' tables and PostgreSQL has no polymorphic FK — the cost is stated in the field comment. (3) `kind`/`source_type`/`channel` are CHECK-constrained vocabularies, so a new kind is a migration — deliberate friction, argued above the constants. (4) tenant logos are on NFR-33's list and are NOT a kind here; they already have storage and moving them buys this CR nothing.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
