# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the moment a draft becomes a bill) ·
#           US-BIL-008 (tax lines per authority — TC-10's named break: a tax
#           whose authority has no liability account is REPORTED BY THE RUN,
#           naming the authority, and the rest of the run continues)
#           Screens: S31 step 5 · S31 step 6 · S30 · S41
# Rules:    BR-BIL-004 (an issued bill is immutable; a correction is a new row)
#           · BR-BIL-010 (every line's GL account is stamped AT ISSUE and
#           frozen) · BR-BIL-011 (billing emits the posting handoff and writes
#           no journal line) · BR-BIL-016 (issue writes one delivery record per
#           bill per channel) · BR-BIL-023 (issue covers all remaining drafts
#           OR a named subset) · BR-BIL-024 (the due date is DERIVED — bill
#           date + the cycle's due-days — never typed) · BR-BIL-026 (template +
#           version pinned at issue) · BR-BIL-030 (the locked bill instance) ·
#           BR-BIL-031 (payload version is the DATA contract) · BR-BIL-033 (a
#           bill that cannot render never issues) · BR-BIL-055 (a break never
#           blocks the run) · BR-BIL-058 (release is five separately recorded
#           facts) · BR-BIL-063 (the number was allocated when the DRAFT was
#           created — issue mints nothing) · BR-BIL-037 stage 7
#           (post-to-ledger — EMITTED HERE since 2026-08-11) · BR-MET-009
#           (due = bill_date + due_days, on the cycle) · BR-TEN-043 (event
#           time is named by the caller, never read from a clock) · CLAUDE.md
#           rule 1 (tenant scoping) · rule 2 (money + currency) · rule 4
#           (financial immutability) · rule 5 (ONLY the ledger posting service
#           writes journal lines — this EMITS and writes none) · rule 6
#           (idempotency — the handoff is keyed per invoice+event) · rule 7
#           (every money action writes audit_log)
# Tests:    06-backend/tests/test_us_bil_005_issue.py ·
#           06-backend/tests/test_us_bil_009_posting_handoff.py ·
#           06-backend/tests/test_us_bil_008_tax_lines.py
# Impacts:  apps/billing/models.Invoice + InvoiceLine (the rows this freezes) ·
#           apps/ledger/selectors (the GL map this READS by name) ·
#           apps/billing/posting_seam.post_bill_issue (BR-BIL-011's stage-7
#           handoff, emitted INSIDE this transaction; it reaches
#           apps/ledger/posting.post BY NAME — billing writes no journal line)
#           · apps/billing/documents.render_invoice (BR-BIL-033's precondition,
#           called here before the status moves — a bill that cannot render
#           never issues) · apps/billing/delivery_seam.queue_bill_delivery
#           (BR-BIL-016's queue rows, written inside this transaction; it
#           QUEUES and never sends — R4 is where email is switched on. Since
#           CR-048 wave B it also names the SET-12 event, derived from
#           `corrects_invoice_id` on the locked row, so this utility's
#           Settings → Notifications rule reaches every bill this issues)
# ───────────────────────────────────────────────────────
"""Issue — turn a DRAFT into a real, immutable bill. Phase 5 of the PO's run.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this is a money path and it is the exact
moment financial immutability begins (CLAUDE.md 🔒). AI-authored 2026-08-11
under the PO ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md.

WHAT ISSUE DOES, IN ORDER, AND WHY THE ORDER IS THE DESIGN
----------------------------------------------------------
Everything below happens for ONE bill inside ONE transaction, and every check
happens BEFORE the row is touched. Once the status leaves `draft` the money,
the dates, the number, the template pin and the locked instance are frozen by
the database itself (billing 0002/0006 triggers), so a fact that is not
recorded here can never be recorded at all. That is why issue refuses rather
than proceeding-and-fixing-later: there is no later.

  1. **The number is ALREADY THERE.** BR-BIL-063 (PO ruling 2026-08-11)
     allocates it when the draft is written — *"Give a running number always
     even for Draft; if not use thats okay we will lose it."* **Issue mints
     nothing.** It verifies the number is present and refuses a numberless
     draft, because a bill with no number cannot be quoted by a customer, a
     collector or a court. Anything in this repo still saying "minted at issue"
     is older than that ruling — four such places were found while writing
     this; the two inside `06-backend/tests/` are corrected and the rest are
     named in this lane's report for the files that own them.
  2. **The due date is DERIVED** — BR-BIL-024, `bill date + the cycle's
     due-days`. Both figures live on the cycle (BR-MET-009), and the run's
     `cycle_id` is the reviewed cross-module FK that reaches them. It is never
     a parameter, because a due date that can be typed is a due date that will
     eventually be typed wrong on one bill in a run of a thousand.
  3. **The GL account is stamped on every line** — BR-BIL-010, at issue, and
     frozen. Read through a SEAM to the ledger, which owns the maps (see
     below). A line that cannot resolve its GL account fails the WHOLE bill:
     US-BIL-007 TC-5, *"issue fails atomically if any line cannot resolve a
     GL — nothing partial issues."*
  4. **The template is PINNED** — BR-BIL-026, id + version, so a reprint
     renders what was sent rather than what the tenant's template says today.
  5b. **The DOCUMENT IS RENDERED** — BR-BIL-033, and it happens BEFORE the
     status moves. A bill that cannot render is refused here, while it is still
     a discardable draft; after this point the template pin is frozen and an
     unrenderable bill would have no lawful repair.
  5. **The payload is FROZEN.** It was assembled at DRAFT time on purpose
     (stage 6's docstring gives the reason: assembling it here would re-join
     whatever the customer record says by now, and a name changed between the
     run and the release would print on a bill for a period billed under the
     old one). Issue's job is to make it non-optional: BR-BIL-030's NOT NULL
     binds where the rule speaks, and this is where it speaks.
  6. **Status → issued, `issued_at` set**, in one write.
  7. **`audit_log`** — hard rule 7. Issue is a money action.
  8. **The BALANCED POSTING HANDOFF is emitted** — BR-BIL-011, stage 7 of
     BR-BIL-037, and it happens AFTER the status moves and INSIDE the same
     transaction. DR AR / CR the per-GL buckets of the lines just stamped.
     Billing writes no journal line: the seam hands the request to the ledger's
     posting service, which is the sole writer (CLAUDE.md rule 5).
  9. **The DELIVERY ROWS are queued** — BR-BIL-016, last, and also inside this
     transaction. Money before message: a bill's entry belongs in the books
     before anybody is told about the bill.

WHAT ISSUE DOES AND DOES NOT DO AT THE LEDGER BOUNDARY
------------------------------------------------------

**IT NOW EMITS THE POSTING HANDOFF (BR-BIL-011, stage 7), SINCE 2026-08-11, AND
THIS PARAGRAPH USED TO SAY THE OPPOSITE.** It read: *"It does not post to the
ledger … the posting service is still a stub … Nothing here emits a handoff
either — that is a separate act, and doing it inside issue would put two money
events in one transaction whose failure modes are not the same."* The first
clause stopped being true when `apps/ledger/posting.py` was built the same day,
and the argument in the second was wrong: **they are not two events.** One bill
issuing IS the money event, and the journal entry is where that event is
recorded. Splitting them buys independence of failure at the price of a state
nothing can repair — an issued, immutable bill whose money is in no ledger
account, with hard rule 4 leaving no path to add the entry afterwards.

So step 8 below calls `apps/billing/posting_seam.post_bill_issue` INSIDE this
transaction, after the status has moved: DR the tenant's `accounts_receivable`
designation for `invoices.total`, CR one bucket per distinct `gl_account_id`
across the lines this call just stamped (US-BIL-005 §7, WE-1: DR AR 247.87
against nine buckets). A bill and its journal entry commit together or neither
does.

**BILLING STILL WRITES NO JOURNAL LINE** (CLAUDE.md rule 5). The seam resolves
`apps.ledger.posting.post` BY NAME and hands it a balanced request; the ledger
is the sole writer and `ledger/0004`'s sole-writer trigger is the fence that
makes that structural rather than a promise. Nothing in billing computes,
rounds or nets a money figure for the handoff — every amount is read from the
stored invoice and its frozen lines, and an unbalanced handoff is REFUSED
naming the delta rather than plugged.

See `ISSUE_UNAVAILABLE`, which travels on every result so a caller cannot read
this as a finished pipeline: what stage 7 still cannot say (US-LED-002's
premises/unit chain, a tax bucket's authority) rides there rather than being
assumed handled.

**IT NOW WRITES THE DELIVERY QUEUE (BR-BIL-016), SINCE 2026-08-11, AND THIS
PARAGRAPH USED TO SAY THE OPPOSITE.** It said so truthfully: the notifications
write path published nothing to call and a cross-module write is forbidden
(B1). It publishes one now. Step 9 below calls
`apps/billing/delivery_seam.queue_bill_delivery`, which resolves
`apps.notifications.services.queue_document` BY NAME, inside this same
transaction — so a bill and its delivery rows are one atomic fact. Queueing
after the commit would leave the state nothing can repair: an issued,
immutable bill with no delivery record and no path left that would ever write
one.

**QUEUEING IS NOT SENDING.** Nothing in this path contacts a provider. R2
builds the queue; **R4 is where email is switched on**, and a row resting
`queued` is the finished, correct outcome of a bill run today. What is still
owed rides `ISSUE_UNAVAILABLE` and the seam's own result: no dispatcher, no
render-to-store, and no email/SMS row while the account delivery election
(`accounts.paperless`, PROPOSED-SCHEMA) is unbuilt — every bill gets the print
row BR-BIL-036 makes the floor, and nothing is invented above it.

**IT DOES RENDER (BR-BIL-033), SINCE 2026-08-11.** *"Render BEFORE issue; a
failed render REFUSES the issue."* Step 5b below calls
`apps.billing.documents.render_invoice` on the draft, with the pin this call is
about to write, inside the same transaction and before the status moves — so a
bill that cannot be turned into a document never becomes immutable-and-
unrenderable, which is the hole the ruling was made to close. The render writes
nothing, stores nothing and sends nothing; it is a precondition, and it is the
ONLY thing it claims to be. A render failure is an ordinary `BillingRuleError`,
so it records one break for that bill and the rest of the batch issues
(BR-BIL-055).

The rendered document is then DISCARDED, and that is the piece BR-BIL-036 still
owes: *"every bill is rendered, its document is STORED, and the print batch
goes to the vendor."* Nothing stores it — `outbound_messages` pins the template
so the dispatcher can render at dispatch time and keeps no body, and there is
no document table and no blob store. So issue proves a bill CAN become a
document and keeps no evidence of the one it made.

THE GL SEAM, AND WHY IT IS A SEAM (OQ-106, CLOSED 2026-08-11)
-------------------------------------------------------------
The PO ruled the ownership question the same day this was written: *"A · The
ledger owns it - Your accountant sets it up on a Finance screen, next to the
chart of accounts they already maintain - this is corret; it will be done
during GL cod emapping in settings"*, and *"using attributes on accounts and
Utility services - we can derive how it sum up at Ledger"*. So the maps are
LEDGER-owned (B2 r16 #6 confirmed, EP-LED-02 §Scope superseded on that point),
a designation is an ATTRIBUTE on a ledger account AND on a utility service, and
billing's only lawful move is to ASK (B1 — a module never touches another
module's tables). Billing must not keep a map of its own; if it did, payments
would one day have to ask BILLING for an accounting map in order to record the
per-service cash collections the PO ordered on the same day.

The ledger published two primitives the same day — `revenue_account_id_for_service`
and `gl_account_id_for_designation` — and deliberately did NOT publish a
per-invoice-line adapter, saying why in its own trailer: **the line KINDS are
billing's vocabulary.** That boundary is right, so the kind → account decision
lives here (`_gl_account_for`) and every ACCOUNT it returns comes from its
owner. Billing keeps no map, caches nothing, and falls back to nothing — a
guessed GL account is silent misposting that surfaces as an unexplainable trial
balance months later.

**AND A TAX LINE'S ACCOUNT COMES FROM RATING, NOT THE LEDGER** (BR-BIL-069, PO
ruling 2026-08-11 closing OQ-116). The authority → account mapping lives on
`taxes.liability_gl_account_id`, a tenant-editable column that already existed;
the PO declined a second ledger-side table keyed on the authority precisely
because two homes for one mapping drift. So this module asks rating for the
account and the ledger whether that account is live — two owners, four reads,
no map of its own.

**WHAT THAT MEANS TODAY** (rewritten 2026-08-11 — this paragraph said "an
ordinary bill still cannot issue", and that stopped being true with the ruling
above): **an ordinary bill issues.** Usage and base lines resolve from the
service, which stage 6 now writes onto every line it creates; a tax line
resolves its own authority's 2200-series account from the tax it names, so the
$8.30 on the reference bill posts as State of Texas $6.29 + Harris County $1.01
+ City of Katy $1.00, three lines to three accounts. Two refusals remain and
both are honest gaps rather than blocked paths: a FEE line still names no
charge code (BR-BIL-010 gives each code its own GL and the charge id does not
travel on the priced line at all), and a tax whose authority the tenant has not
yet given an account refuses by name — *"every utility may not have every
account"*, and nothing is force-seeded. Every refusal here is the RATIFIED
behaviour, not a workaround — US-BIL-007 TC-5: *"issue fails atomically if any
line cannot resolve a GL... nothing partial issues"* — and it is refused rather
than stubbed because a stub would crash a batch where a named break lets the
other 499 bills through.

⚠ **THE FEE HALF OF THAT PARAGRAPH EXPIRED ON 2026-08-25 (DEF-714), and it had
been WRONG-BY-CONSEQUENCE for three days before that.** It said *"a FEE line
still names no charge code... and the charge id does not travel on the priced
line at all"*, which described a small honest gap. It was not small: on
2026-08-22 BR-RAT-117 put a fee line on the ORDINARY bill of every tenant that
configures a recurring or auto-apply charge code, so this refusal stopped being
about exotic fees and started refusing every bill those tenants had. **A fee
line now resolves its charge code's own GL account** (`gl_account_id_for_charge`
below, PO ruling 2026-08-25 option A). What still refuses, and correctly, is a
fee that names NO code — a late fee is the live example — and a code the tenant
has not mapped.

ONE BILL IS THE UNIT OF ATOMICITY
---------------------------------
Exactly as `runs.calculate_account` frames phase 2, and for the same reason: a
run of 500 where number 7 fails must issue 499 and report one break
(BR-BIL-055, BR-BIL-047). Each bill gets its own transaction; a break carries a
reason code the screen can group on and never rolls back the morning's work.

RE-ISSUING IS A NO-OP AT THE RUN LEVEL AND A REFUSAL AT THE BILL LEVEL
----------------------------------------------------------------------
Two different questions deserve two different answers, and both are here:

* `issue_run` selects the run's REMAINING DRAFTS. A double-clicked "issue this
  run" therefore finds nothing the second time and issues nothing — the
  no-duplicate guarantee of US-BIL-005 TC-6, obtained from the selection rather
  than from a lock or a flag. Bills named in an explicit subset that are
  already issued come back in `already_issued`: reported, never silently
  dropped, because a caller that asked for 100 and got 60 is owed the reason.
* `issue_invoice` REFUSES a bill that is not a draft. At the single-bill level
  the caller has asked for something impossible, and returning success would
  claim work this call did not do. The database would refuse it too — the
  status guard here is the service-layer half of the same law, and it is what
  protects the SQLite developer database, which has no triggers at all.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db import transaction

from apps.billing import customers_seam
from apps.billing import delivery_seam
from apps.billing import documents
from apps.billing import frozen_bill
from apps.billing import metering_seam
from apps.billing import models
from apps.billing import payments_seam
from apps.billing import pending
from apps.billing import posting_seam
from apps.billing import rating_seam
from apps.billing import runs
from apps.billing import tenancy_seam
from apps.billing.exceptions import BillingRuleError
from core import audit
from core import errors
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.billing")

#: Why a bill could not be issued. CODES, never prose: the phase-3/5 break list
#: groups on them (BR-BIL-040/053) and free text cannot be grouped. `detail` is
#: the sentence a billing clerk reads underneath.
ISSUE_NOT_A_DRAFT = "invoice_is_not_a_draft"
ISSUE_NO_NUMBER = "invoice_no_missing_at_issue"
ISSUE_NO_PAYLOAD = "bill_payload_missing_at_issue"
ISSUE_NO_TEMPLATE_PIN = "template_not_pinned_at_issue"
ISSUE_NO_DUE_TERMS = "cycle_has_no_due_terms"
#: B11 (2026-09-30) — a bill failed for a reason that is not a named rule (a
#: `RuntimeError` such as `frozen_bill.NotFrozen`, a database error, a seam
#: fault). ONE break for that bill; the pass goes on (BR-BIL-055).
ISSUE_FAILED_UNEXPECTEDLY = "issue_failed_unexpectedly"
ISSUE_GL_MAP_UNPUBLISHED = "ledger_has_not_published_the_gl_map"
ISSUE_LINE_UNMAPPED = "line_has_no_gl_account"
ISSUE_LINE_NAMES_NO_SERVICE = "line_names_no_service"
ISSUE_TAX_LINE_UNMAPPABLE = "tax_line_names_no_authority"
#: BR-BIL-069 — the line DOES name its authority and that authority has no
#: 2200-series account yet, or has one the tenant since deactivated. Its own
#: code because it is a different job for a different person: `..._names_no_
#: authority` is a rating-configuration break (a plan rule with no tax behind
#: it), this one is a chart-of-accounts break a clerk fixes on S13 in a minute.
#: Grouping them would put two unrelated fixes under one heading on the phase-3
#: break list.
ISSUE_TAX_AUTHORITY_UNMAPPED = "tax_authority_has_no_live_account"
ISSUE_FEE_LINE_UNMAPPABLE = "fee_line_names_no_charge_code"
#: DEF-714 — the fee line DOES name its charge code and that code has no GL
#: account yet, or one the tenant has since deactivated. Its own code, and for
#: the same reason the two tax codes are two: `..._names_no_charge_code` is a
#: line that arrived anonymous (a late fee computed from B4's rule, which comes
#: from no code at all — a developer's problem), while this one is a
#: chart-of-accounts gap a clerk closes on S13 in a minute by pointing the code
#: at an account. Grouping them would put two unrelated fixes under one heading
#: on the phase-3 break list.
ISSUE_FEE_CHARGE_UNMAPPED = "charge_code_has_no_live_account"
ISSUE_NOT_IN_RUN = "invoice_not_a_draft_of_this_run"
ISSUE_NO_LINES = "invoice_has_no_lines"
#: BR-BIL-033 — the bill could not be turned into a document, so it did not
#: become one. Its own code because it is the break a clerk acts on differently
#: from every other: nothing about the money is wrong.
ISSUE_RENDER_FAILED = "document_render_refused_the_issue"
#: BR-BIL-016 — the bill is fine and its DELIVERY ROW could not be written, so
#: it did not issue. Its own code for the same reason the render's is: nothing
#: about the money is wrong, and a clerk acts on it somewhere else entirely.
ISSUE_DELIVERY_UNQUEUEABLE = "delivery_row_could_not_be_queued"
#: BR-BIL-011 — stage 7's five breaks, and they are FIVE ON PURPOSE because they
#: are five different jobs for four different people:
#:
#:   * `..._service_unavailable` — the ledger's posting module publishes nothing
#:     on this deployment (W5 not migrated). An engineer's problem; no clerk can
#:     fix it and no data change will.
#:   * `..._no_ar_account` — the tenant has designated no `accounts_receivable`
#:     account, so the entry has no debit side. One chart edit on S56, a minute.
#:   * `..._unbalanced` — the bill's own stamped lines do not sum to its own
#:     stored total. NOTHING is plugged; this is a DATA defect upstream of issue
#:     and it wants a developer, not a re-run.
#:   * `..._refused` — the books themselves refused the request (an account that
#:     is not this tenant's, a float, a missing dimension). The ledger's sentence
#:     travels inside the detail.
#:   * `..._negative_bucket` — a GL bucket sums BELOW ZERO, which §7's "CR the
#:     buckets" does not describe. Its own code because it is the only one of the
#:     five that wants a RULING rather than a fix: **OQ-152**, open, and the bill
#:     stays a draft until it is answered rather than posting on a guessed sign.
ISSUE_POSTING_UNAVAILABLE = "ledger_posting_service_unavailable"
ISSUE_POSTING_NO_AR = "no_accounts_receivable_account_designated"
ISSUE_POSTING_UNBALANCED = "posting_handoff_does_not_balance"
ISSUE_POSTING_REFUSED = "ledger_refused_the_posting_handoff"
ISSUE_POSTING_NEGATIVE_BUCKET = "posting_bucket_is_negative_oq_152"

#: The two ledger reads this stamp stands on. Named once so the contract is
#: greppable from BOTH sides of the boundary.
#:
#: The ledger owns the maps (PO ruling 2026-08-11, OQ-106) and published these
#: primitives; it deliberately did NOT publish a per-invoice-line adapter, and
#: said why in its own trailer: **the line KINDS are billing's vocabulary.** So
#: the kind → account decision below lives here, in the module that owns the
#: word "usage", and every ACCOUNT it returns comes from the ledger. Billing
#: keeps no map, no cache and no fallback.
GL_MODULE = "ledger"
GL_REVENUE_READ = "revenue_account_id_for_service"  # (service_code, base=bool) -> id | None
GL_DESIGNATION_READ = "gl_account_id_for_designation"  # (designation) -> id | None
#: Is this id one of the current tenant's LIVE ledger accounts? The ledger owns
#: its own table, so only the ledger can answer — an FK proves existence, never
#: ownership and never that the tenant has not since retired the row (IS-1).
GL_LIVENESS_READ = "account_is_live"  # (account_id) -> bool

#: The TAX half of BR-BIL-010, and it is **rating's**, not the ledger's.
#:
#: The PO closed OQ-116 on 2026-08-11 with option A as amended — *"For each
#: atheority have separate account and tagging"* — and declined option B, a
#: ledger-side table keyed on the authority, because `rating.taxes` already
#: holds that fact and two homes for one mapping drift within a release. So the
#: tenant's authority → account mapping stays on `taxes.liability_gl_account_id`
#: (editable on S13, validated against the ledger when it is written), and this
#: is the read billing asks. Named here beside the ledger reads so the whole
#: contract of the stamp is greppable from one place.
TAX_GL_MODULE = "rating"
TAX_GL_READ = "liability_gl_account_id_for_tax"  # (tax_id) -> id | None

#: The FEE half of BR-BIL-010, and it is **rating's** too — DEF-714, 2026-08-25.
#:
#: *"Charge codes carry their own GL"*: the account lives on
#: `rating.charges.gl_account_id`, the tenant's own column, edited on S13 and
#: validated against the ledger when it is written. One home for the mapping,
#: for the same reason the PO's OQ-116 closure kept one home for a tax
#: authority's — two configuration screens that both claim to say where a fee's
#: money goes will disagree within a release.
#:
#: **THIS READ IS WHY A BILL WITH A FEE CAN ISSUE AT ALL.** The branch below
#: used to refuse EVERY fee line unconditionally, without so much as reading
#: the charge id it was handed, because nothing wrote `invoice_lines.charge_id`
#: — the column had no writer anywhere in the repo. Meanwhile BR-RAT-117 (PO
#: 2026-08-22, *"ruccuring and Autom apply land on bill"*) puts a fee line on
#: the ordinary bill of every tenant that configures a recurring or auto-apply
#: code. The two met at issue and the bill died there: a tenant that used the
#: feature could issue no bill at all. PO ruling 2026-08-25, option A — *"Make
#: issue read the charge code"*.
CHARGE_GL_MODULE = "rating"
CHARGE_GL_READ = "gl_account_id_for_charge"  # (charge_id) -> id | None
#: ⚠ **CR-197-BRC10 / DEF-BIL-10648 — A DISCOUNT'S OWN ACCOUNT.** CR-066 table 3
#: gave every discount a `gl_account_id` and a screen to set it, and NOTHING
#: here read it: every discount line landed in the `discount_contra_revenue`
#: designation whatever the discount said. Now a discount line that names its
#: code asks rating for that discount's own account first and falls back to the
#: designation — so an unmapped discount posts exactly as before. OPTIONAL by
#: design: a rating that has not published it leaves today's behaviour intact.
DISCOUNT_GL_READ = "gl_account_id_for_discount_code"  # (code) -> id | None
DISCOUNT_GL_FILE = "gl_mapping_reads"  # apps/rating/gl_mapping_reads.py

#: WHOSE tax a line is, in words — **PO ruling 2026-08-12, OQ-146 CLOSED**,
#: verbatim *"let the run report it"* (US-BIL-008 TC-10 · BR-BIL-069 (3)). A tax
#: whose authority has no liability account is **reported by the RUN as a break
#: naming the authority**, and the rest of the run continues; it is NOT blocked
#: at setup, because blocking there stops a utility part-way through configuring
#: itself.
#:
#: The break code and the atomic per-bill refusal both already existed. What did
#: not was the NAME: the refusal quoted the line's description, which is the
#: rate CODE somebody typed (*"Tax HARRIS-CO"*), not the body the money is owed
#: to. This read answers *"Harris County"*, so the sentence a clerk reads names
#: the row of S13 they have to open.
#:
#: **DISPLAY ONLY, and the distinction is load-bearing.** Nothing stamps, posts
#: or maps on this string — `TAX_GL_READ` above is the money-bearing read and is
#: keyed on the tax id. Resolving an authority by its wording was option D of
#: OQ-116 and the PO declined it. A missing read here degrades the SENTENCE and
#: never the refusal: see `_authority_label`.
TAX_AUTHORITY_LABEL_READ = "tax_authority_label_for_tax"  # (tax_id) -> str | None

#: `apps.ledger.chart.MINIMUM_BILL_ADJUSTMENT`, one of the eleven designations
#: the PO ruled on 2026-08-11 (OQ-110, option A). Repeated as a string rather
#: than imported because a constants module is still another module's internals
#: — and it is SAFE to repeat precisely here, because the ledger's
#: `gl_account_id_for_designation` RAISES on a designation it does not know. A
#: typo fails loudly at the call instead of resolving to None and looking like
#: an unmapped account.
GL_MINIMUM_BILL_ADJUSTMENT = "minimum_bill_adjustment"
#: US-LED-001's contract table, the *"First-bill deposit line"* row: the credit
#: side is **deposit liability — never revenue**, inside the bill's own issue
#: entry. A deposit is the CUSTOMER'S money held by the utility (BR-PAY-012),
#: and `apps/payments/ledger_seam.py` credits the same designation on the way
#: in, so the two halves of one deposit land in one account.
GL_DEPOSIT_LIABILITY = "deposit_liability"

#: `apps.ledger.chart.DISCOUNT_CONTRA_REVENUE`, the THIRTEENTH designation —
#: PO ruling 2026-08-28, closing `DEF-536`, verbatim: *"you will need differnt
#: GL code for these - dont keep them in same, create differnt category as
#: required and keep them in it"*.
#:
#: A discount does NOT reduce the service's own revenue account. It posts to a
#: separate code in a separate category — standard contra-revenue, and option
#: **(a)** as OQ-152 itself enumerated it. Worked on the frozen GT-1 bill with a
#: 10.00 reduction: electric usage stays **CR 82.08** (not 72.08), base stays
#: **CR 18.50**, the discount account takes **DR 10.00**, and AR is **DR 90.58**
#: — both sides 100.58. The netted form reported 72.08 of electric revenue the
#: utility never earned at that price.
GL_DISCOUNT_CONTRA_REVENUE = "discount_contra_revenue"

#: BR-BIL-035 — WHICH WINDOW the stamped previous balance and payments/credits
#: were read over. Stamped as a VALUE on every bill (`_stamp_balance_forward`),
#: because the record is immutable and a ruling may move the definition (OQ-217
#: did, 2026-10-01 — see below): a reader
#: in 2031 must be able to tell which one their bill was written under without
#: dating the code that wrote it.
#:
#: ⚠ **AMENDED 2026-08-27 — BR-BIL-160 (PO ruling, OQ-530 CLOSED).** It read
#: `open_prior_bills_at_issue` from 2026-08-15 to 2026-08-27, and the window is
#: no longer only the open prior BILLS: it is those bills **and the account's
#: migrated opening balance**, net of what the account's credit position shows
#: as settled against it. The value moves with the definition on purpose — a
#: bill stamped last week and a bill stamped today were written under different
#: rules, and the whole reason this is a VALUE rather than a comment is that
#: each one has to be able to say which.
#:
#: ⚠ **AMENDED 2026-10-01 — `OQ-217` CLOSED (PO, option A, BR-BIL-1065): the
#: WHOLE ACCOUNT SINCE THE LAST BILL.** Every bill stamped from this day reads
#: `whole_account_since_last_bill`; the old value is still written, by name,
#: only on a bill where payments could not answer the new reads
#: (`BALANCE_FORWARD_BASIS_FALLBACK`), so a reader can always tell which
#: definition an immutable bill was written under.
BALANCE_FORWARD_BASIS = "whole_account_since_last_bill"
BALANCE_FORWARD_BASIS_FALLBACK = "open_prior_bills_and_migrated_opening_at_issue"
BALANCE_FORWARD_BASIS_OQ = "OQ-217"

#: What issue does NOT do, carried on every result. The customers module's
#: MOVE_OUT_UNAVAILABLE precedent: a caller must not have to infer an absence,
#: and a reviewer must not have to take a docstring's word for it.
ISSUE_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "posting_emitted_without_the_us_led_002_dimensions",
        "br_ref": "BR-BIL-011 · BR-LED-001 · US-LED-002",
        "detail": "**BR-BIL-011 IS NOW SATISFIED — this entry previously read "
        "`posting_handoff_not_emitted` and said stage 7 was a SEPARATE act that is not run "
        "here, with the posting service 'still a stub'.** Both halves stopped being true on "
        "2026-08-11: `apps/ledger/posting.py` is the built sole writer, and "
        "`issue_invoice` now emits the balanced handoff through "
        "`apps/billing/posting_seam.post_bill_issue` INSIDE the issue transaction — DR the "
        "tenant's `accounts_receivable` designation for `invoices.total`, CR one bucket per "
        "distinct stamped `gl_account_id` (US-BIL-005 §7). Billing still writes no journal "
        "line (CLAUDE.md rule 5) and computes no money figure. WHAT IS STILL OWED IS THE "
        "DIMENSION SET: BR-LED-001 wants premises and unit *resolved account → unit → "
        "premises at posting time* and no module publishes either read (US-LED-002), so "
        "both are NULL; a tax bucket carries no `tax_authority_id` because rating publishes "
        "no `tax_authority_id_for_tax` and billing may not read its ORM; and a bucket names "
        "the INVOICE rather than one invoice line, because §7's bucket is a SUM (WE-1: 15 "
        "stamped lines → 9 buckets). Every one of those rides "
        "`posting_seam.POSTING_UNAVAILABLE` and the per-bill `problems` list.",
    },
    {
        "code": "delivery_queued_but_nothing_dispatched",
        "br_ref": "BR-BIL-016 · BR-BIL-036",
        "detail": "BR-BIL-016's QUEUE HALF IS NOW SATISFIED — this entry previously said "
        "issue wrote no delivery record because the notifications write path published "
        "nothing to call, and it does now: `delivery_seam.queue_bill_delivery` writes one "
        "row per bill per channel inside this transaction. What is still owed is the SEND. "
        "There is no dispatcher (US-NOT-002), no provider adapter (US-NOT-003) and no "
        "provider call anywhere in R2 — email ACTIVATION is R4 on the B12 release table — "
        "so the rows rest `queued`, which is their finished state today and not a failed "
        "send. Two further absences ride the seam's own result: the account delivery "
        "ELECTION (`accounts.paperless` / `.sms_reminders`, PROPOSED-SCHEMA and unbuilt) "
        "cannot be read, so every bill gets the BR-BIL-036 print floor and no email or SMS "
        "row is written on a guess; and the RECIPIENT cannot be resolved at all "
        "(customers publishes no `delivery_recipients_for_account`), so each row records "
        "`recipient_not_resolvable` rather than an address nobody looked up.",
    },
    {
        "code": "document_stored_but_not_handed_to_a_print_vendor",
        "br_ref": "BR-BIL-033 · BR-BIL-036 · BR-NOT-027",
        "detail": "⚠ REWRITTEN 2026-08-30 (CR-049 task 4), because the half it named is "
        "DONE. It read: *'issue proves a bill CAN be rendered and keeps nothing … there is "
        "no document table, no blob store and no delivery queue.'* **Issue now KEEPS the "
        "bill**: both serialisations are frozen into tenancy's write-once document store "
        "before the status moves, and a bill that cannot be kept stays a draft "
        "(`apps/billing/frozen_bill.py`, BR-NOT-027, PO 2026-08-30). BR-BIL-033 is "
        "satisfied as it was. What is STILL owed is the last clause of BR-BIL-036: the "
        "stored page is not handed to a print vendor — the delivery queue is written "
        "(BR-BIL-016) and the dispatcher renders the letter TEXT itself, so nothing carries "
        "this document to a printer. The renderer's own `DOCUMENT_UNAVAILABLE` lists what "
        "the page cannot do (no HTML/CSS engine, OQ-149; the tenant designs no body) and "
        "its `absent` list names every A19 field the snapshot does not carry.",
    },
    {
        "code": "template_assignment_not_resolved",
        "br_ref": "BR-BIL-025",
        "detail": "the category-default / account-override assignment has no table "
        "(r10 #4, US-BIL-021), so the pin cannot be derived. Issue records the pin its "
        "CALLER names and refuses to issue without one — see `issue_invoice`.",
    },
    {
        "code": "payload_tie_out_not_asserted",
        "br_ref": "BR-BIL-032",
        "detail": "HALF of the rule is unassertable and half is now asserted. Unassertable: "
        "`bill_payload.total == invoices.total` — stage 6 stamps no total and no line set "
        "in the payload, so there is nothing to compare it TO. Asserted: the rows tie out "
        "exactly. CORRECTED 2026-08-11 — this entry used to add that 'Σ(6dp lines) vs a "
        "2dp header is not a safe equality', and that is FALSE for this engine: "
        "`apps/rating/pricing/stages/finalize` rounds EVERY line half-up to 2dp once "
        "(BR-RAT-003) and `assemble` sets the total to the sum of those finalized lines, so "
        "GT-10 is 82.08 + 18.50 + 8.13 + 8.30 = 117.01 to the digit and no rounding gap can "
        "exist. The equality is safe; it is `bill_payload` that is empty. Asserted in "
        "tests/test_us_bil_022_documents.py tc7, not enforced as a refusal, because "
        "BR-BIL-032 is PROPOSED and a PROPOSED rule must not block an issue.",
    },
    {
        "code": "autopay_intent_carries_the_gross_total",
        "br_ref": "BR-PAY-015 · BR-PAY-010",
        "detail": "the autopay capture INTENT this issue records carries `invoices.total` — "
        "the bill BEFORE any carried credit was drawn down. That is the figure BR-PAY-015's "
        "contract asks for and PE-12's frozen 292.87 is that figure, so it is what is sent. "
        "**But an enrolled customer with a 57.13 credit would then be scheduled for the "
        "GROSS while owing the NET**, and whether the intent should carry the net has never "
        "been put to the Product Owner. It is REPORTED here rather than chosen: picking "
        "either reading decides how much money is taken from a customer's bank account. "
        "There are no payment rails in this release (`awaiting_rails`), so nothing is "
        "captured on the wrong figure today — which is exactly why it can be raised now "
        "rather than found later.",
    },
)


def fault_signature(problem: BaseException) -> str:
    """DEF-BIL-8747 — the NAME of an unexpected fault, for telling one fault
    met on bill after bill from many different ones.

    The innermost cause's class, by `__cause__` then `__context__`, at most
    eight hops (hard-won law 14: Django's `ProgrammingError` wraps another
    Django error that wraps the driver's, and only the driver's names the real
    thing — `UndefinedColumn`, `UndefinedTable`, `OperationalError` for a
    database that is gone). The MESSAGE is not part of it on purpose: a
    message carries the bill's own number or id, so the same fault would read
    as a different one on every bill."""
    seen = problem
    for _ in range(8):
        inner = seen.__cause__ or seen.__context__
        if inner is None or inner is seen:
            break
        seen = inner
    kind = type(seen)
    return f"{kind.__module__}.{kind.__qualname__}"


class IssuePassStopped(RuntimeError):
    """DEF-BIL-8747 — an issue pass STOPPED because the same unexpected fault
    met `bills` bills in a row (`issue_run`'s `stop_after_same_fault`).

    It is not a bill's break and is never filed as one: a fault of the system
    — code ahead of its database, a database that is gone, a table that is not
    there — is reported ONCE, as a stop, rather than as N bills *not sent*.
    `partial` is what the pass did BEFORE the streak, shaped like an
    `IssuedRun` for `release.record_send_breaks` (`issued`, `broken`): the
    bills it issued, and the genuine breaks it met first, which are still
    filed. The bills of the streak itself are still drafts (each one's
    savepoint rolled it back) and carry no break."""

    def __init__(self, *, fault: str, bills: int, detail: str, partial: Any) -> None:
        super().__init__(
            f"the issue pass stopped: the same fault ({fault}) on {bills} bills in a row. "
            f"Last: {detail}"
        )
        self.fault = fault
        self.bills = bills
        self.detail = detail
        self.partial = partial


@dataclass(frozen=True)
class IssuedPassSoFar:
    """`IssuePassStopped.partial` — the two halves `record_send_breaks` reads."""

    issued: tuple[str, ...]
    broken: tuple[Any, ...]


@dataclass(frozen=True)
class IssueBreak:
    """One bill that could not be issued, and why.

    Mirrors `runs.AccountProblem` on purpose — same discipline, `reason` is a
    stable code the screen groups on and `detail` is the sentence underneath —
    but names the BILL, because a bill is issue's unit of work where an account
    is the calculation's.
    """

    reason: str
    detail: str
    invoice_id: str | None = None
    invoice_no: str | None = None
    account_id: str | None = None


@dataclass(frozen=True)
class IssuedRun:
    """What one issue pass did — and, deliberately, what it did not.

    `issued` and `broken` are the two halves the step-6 screen renders.
    `already_issued` is the third and it is neither: those bills were asked for
    and were already bills, which is the honest answer to a retry and is not an
    error. `unavailable` travels so that "the run issued 480 bills" is never
    read as "the pipeline is finished" — the posting handoff is not built and
    nothing has been dispatched.

    `posted` / `already_posted` count JOURNAL ENTRIES, and they are two counters
    for the same reason `issued` and `already_issued` are: "480 bills reached
    the books this morning" and "480 bills were already in the books" are
    different mornings, and a resumed release must not report the second as the
    first. `already_posted` is the hard-rule-6 replay (US-LED-001 TC-6) — the
    entry was there, this pass wrote nothing, and that is the CORRECT outcome of
    a re-run rather than an error. A bill that could not post did not issue
    either, so it appears in `broken` and in neither counter. `posting_problems`
    carries the DISTINCT codes the seam reported with the number of bills each
    affected, so a run whose every tax bucket lacks an authority says so once
    with a count rather than 480 times.

    `delivery_queued` / `delivery_already_queued` count QUEUE ROWS, not bills:
    BR-BIL-016 is one record per bill per CHANNEL, so a run of 480 bills that
    each go out on paper is 480, and the day the delivery election is readable
    a paperless account contributes two. The two counters are separate for the
    same reason `issued` and `already_issued` are — "480 rows queued" and "480
    rows were already queued" are different mornings, and a resumed batch must
    not report the second as the first. `delivery_problems` carries the DISTINCT
    problem codes the seam reported with the number of bills each affected, so
    a run that could not resolve a single recipient says so once with a count
    rather than 480 times.
    """

    bill_run_id: str | None
    issued: tuple[str, ...] = ()
    already_issued: tuple[str, ...] = ()
    broken: tuple[IssueBreak, ...] = ()
    unavailable: tuple[dict[str, Any], ...] = ISSUE_UNAVAILABLE
    posted: int = 0
    already_posted: int = 0
    posting_problems: tuple[dict[str, Any], ...] = ()
    delivery_queued: int = 0
    delivery_already_queued: int = 0
    delivery_problems: tuple[dict[str, Any], ...] = ()
    #: BR-PAY-010 — how much CARRIED CREDIT this pass drew down, and against how
    #: many bills. `credit_applied` is `None` when the seam could not be reached
    #: on ANY bill, because zero applied and nobody asked are different facts
    #: and only one of them means the customers had no credit.
    credit_applied: Decimal | None = None
    credit_bills: int = 0
    #: BR-PAY-015 — autopay capture INTENTS recorded (`created`) and replayed
    #: (`already_recorded`, the hard-rule-6 no-op a resumed release finds).
    #: Nothing is captured: there are no payment rails in this release.
    autopay_intents: int = 0
    autopay_already_recorded: int = 0
    payment_problems: tuple[dict[str, Any], ...] = ()
    #: BR-MET-053 (DEF-098) — meter reads moved to the BILLED lifecycle by this
    #: pass, and the ones that were already locked (a re-issue; `mark_read_billed`
    #: is idempotent). Counted apart for the reason every other pair here is:
    #: a resumed release must not report "already locked" as work it did.
    #:
    #: ⚠ A ZERO IS NOT NECESSARILY CORRECT and `read_problems` is where it says
    #: so — a base-only run legitimately locks nothing, and a run whose drafts
    #: were priced before `read_id` was carried through the pipeline also locks
    #: nothing and reports `no_read_ids_on_bill`. The two are told apart by the
    #: problem code, never by the count.
    reads_locked: int = 0
    reads_already_billed: int = 0
    read_problems: tuple[dict[str, Any], ...] = ()
    #: ⚠ **WHAT THE BILLS IN THIS RUN COULD NOT FREEZE ONTO THEMSELVES** —
    #: CR-052 W2, the twelve-month usage block (A19 §1.7) and the tenant's bill
    #: message + ways-to-pay (BR-BIL-021). Distinct codes with a bill count,
    #: exactly like `read_problems` beside it and for the same reason: a run of
    #: 480 bills on a tenant that has written no bill copy says so ONCE.
    #:
    #: An EMPTY tuple here means every bill in the pass carries both blocks. It
    #: does not mean the document draws them — that is the render's half, and a
    #: bill that froze an empty usage history is a bill for an account with no
    #: stored months, which the block itself states as an absence rather than
    #: as a zero (BR-MET-106).
    snapshot_problems: tuple[dict[str, Any], ...] = ()
    #: How many Pending-billing queue rows this pass CLOSED (US-BIL-006 TC-3,
    #: BR-BIL-034). It is its own counter and not folded into `issued` because
    #: the two answer different questions: a cycle run issues 1,122 bills and
    #: closes 0 queue rows, and a catch-up sub-run issues 3 and closes 3. A
    #: reader seeing "3 issued" cannot tell whether anybody stopped being owed a
    #: bill; this is that fact.
    queue_rows_resolved: int = 0
    #: ── BR-BIL-025 RESOLVED PER ACCOUNT (CR-052 task 12) ───────────────────
    #: How many bills in this pass were pinned to a template this ACCOUNT's own
    #: chain resolved (`template_resolved_per_account`) and how many fell back
    #: to the RUN's single pin (`template_pinned_by_run`). Two counters for the
    #: reason every other pair here is two: *"1,122 bills each resolved their
    #: own template"* and *"1,122 bills all took the run's"* are different runs,
    #: and until this task landed only the second was possible.
    #:
    #: ⚠ **A RUN WHERE BOTH ARE NON-ZERO IS NORMAL, NOT AN ERROR.** A tenant
    #: with one template resolves the same fallback for every account, and an
    #: EXPLICIT pin typed by the clerk deliberately governs the whole pass — see
    #: `template_pin_explicit` on `issue_run`.
    template_resolved_per_account: int = 0
    template_pinned_by_run: int = 0
    #: Distinct reasons a bill could not resolve its own template, with the
    #: number of bills each affected — the `read_problems` discipline. Empty on
    #: a run where every account answered.
    template_problems: tuple[dict[str, Any], ...] = ()

    @property
    def issued_count(self) -> int:
        return len(self.issued)


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set.

    Refuse loudly rather than run an unscoped query and leave RLS as the only
    thing between one tenant's bills and another's. Same guard, same error, as
    `apps/billing/selectors.py`.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time, the idiom `gather.py` and `tenancy_seam.py` both use:
    no import statement binds billing to the ledger's internals, and the moment
    that lane lands its function this seam starts using it with no re-wiring.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def derive_due_date(
    bill_date: date | None, due_days: int | None, *, cycle_less: bool = False
) -> date:
    """BR-BIL-024 / BR-MET-009 — `bill date + the cycle's due-days`. Pure.

    THE BILL DATE IS THE RUN'S, NOT THE ISSUE TIME, and that is a statement
    worth making out loud because the two differ whenever a run goes out late.
    The rule names "bill date": the clerk's typed one (BR-BIL-070), or the
    cycle's DEFAULT — its bill day in the month after the period ends (OQ-344,
    ruled 2026-08-23; `cycles.bill_date` was dropped by metering 0023 and no
    longer exists). So a run
    planned for 1 Aug with 21 due-days produces 22 Aug on every bill in it,
    whether the batch ran on the 1st or the 3rd — the customer's terms do not
    move because the utility was late, and the figure is reproducible on a
    re-run years later (BR-TEN-043).

    Refuses a negative `due_days` (BR-MET-009: `due_days ≥ 0`); a due date
    before the bill date would put every bill in the run instantly overdue and
    start the late-fee clock (BR-BIL-001) on money nobody has been asked for.
    """
    if bill_date is None or due_days is None:
        if cycle_less:
            # ── B13 (2026-09-30) · A ONE-TIME RUN HAS NO CYCLE TO BLAME ──────
            # The sentence below says *"the cycle carries no …"*, and a
            # one-time bill (`CR-029` D8③) takes its terms from the CLERK
            # because it has no cycle at all — so the refusal named an object
            # the bill does not have. Its own key, `billing.issue.noDueTerms`,
            # so the screen can say *"No days to pay. Set them on the bill."*
            # rather than send a clerk to a cycle. The text keeps the phrase
            # `no bill date and due-days` so `_reason_for` still groups it
            # under `ISSUE_NO_DUE_TERMS` — the reason code is unchanged.
            raise BillingRuleError(
                "this bill has no bill date and due-days pair, so the due date cannot "
                "be derived (BR-BIL-024). A one-time bill takes its days to pay from "
                "the clerk, and nothing here guesses them.",
                br_ref="BR-BIL-024",
                message_key="billing.issue.noDueTerms",
            )
        raise BillingRuleError(
            "the cycle carries no bill date and due-days pair, so the due date "
            "cannot be derived (BR-BIL-024). It is never typed and never "
            "defaulted: a guessed due date decides when a late fee starts."
        )
    if due_days < 0:
        raise BillingRuleError(
            f"the cycle's due_days is {due_days}. BR-MET-009 requires due_days ≥ 0; a "
            "due date before the bill date would make every bill in this run overdue "
            "on the day it was sent."
        )
    return bill_date + timedelta(days=due_days)


def _due_terms_for(bill_run: Any) -> tuple[date | None, int | None]:
    """The run's `(bill_date, due_days)` — the CLERK's date first, or `(None, None)`.

    BR-BIL-070 (PO ruling 2026-08-11, OQ-122 option A — *"Store what they type and
    use it"*): the bill date a clerk types on S31 step 1 is stored on the run and
    is the one that counts. The cycle's own DEFAULT is the FALLBACK, for a run
    where nobody typed one.

    ── CR-029 OQ-344 · WHAT THE FALLBACK IS, RULED 2026-08-23 ────────────────
    ⚠ **THIS READ TOOK `cycle__bill_date` AND NOW TAKES `cycle__bill_day`.** The
    old fallback was a stored calendar DATE from the previous column generation;
    D9 kept a bill DAY (a day-of-month) and turning one into a run's date means
    CHOOSING A MONTH, which nothing ruled — so RC-W5 could not drop the column
    and reported it. The PO ruled it: *"I'd say B - these are defualt - user can
    override"* — **the bill day, in the month AFTER the period ends**.

    **Worked, and it is the figure the PO was shown:** bill day 5, due days 21,
    period 1–31 August → bills **5 Sep**, falls due **26 Sep**.
    `runs.default_bill_date` is that arithmetic, expressed once.

    **NOTHING ALREADY ISSUED MOVES** (CLAUDE.md rule 4): `invoices.due_date` is
    STAMPED at issue and an issued invoice is immutable, so this resolution is
    consulted only while a bill is a DRAFT.

    This read used to take `cycle__bill_date` alone, and that was the whole gap:
    the run priced at the typed date while the due date derived from the cycle's,
    so the wizard PREVIEWED 24 Aug and issue STAMPED 22 Aug on the same bill. The
    lane that built BR-BIL-070 found it, could not close it — this file belonged
    to another lane at the time — and reported it rather than claiming the ruling
    done. `runs.effective_bill_date` is the same precedence, expressed once; this
    calls it rather than restating the rule, so the two cannot disagree.

    Read along the REVIEWED cross-module FK `bill_runs.cycle_id → metering.Cycle`
    (B2 §2 / DB-16), as `values_list`, so nothing here instantiates a metering
    model or imports one — the same posture `apps/billing/selectors.py` takes
    when it reads `account__unit_id`. A published metering selector taking a
    cycle id would be the better long-term shape; metering has not got one
    (`cycle_dict` takes a row, `cycles_list` takes no id), and inventing it is
    another lane's territory. REPORTED, not reached into.

    ── CR-029 D9 · THE DUE TERMS ARE OVERRIDABLE TOO ─────────────────────────
    PO, verbatim 2026-08-23: *"when we configure Cycle we are provideing default
    values; mostly it wil remain as it is but user can over ride them during
    billing"*. The bill date has been overridable since BR-BIL-070; the TERMS
    had no column, so half the ruling could not be built. `bill_runs.due_days`
    (migration 0022) is that column and `runs.effective_due_days` is the same
    precedence expressed once, exactly as `effective_bill_date` is.

    **NOTHING ALREADY ISSUED MOVES** (CLAUDE.md rule 4). Every run created
    before that migration carries `due_days = NULL`, the resolution returns the
    CYCLE's value for it, and the due date is the identical figure this function
    returned before — proved case by case, against dates computed by hand, in
    `tests/test_cr029_rcw1_due_terms.py`.
    """
    if bill_run is None:
        return None, None
    row = (
        models.BillRun.objects.filter(tenant_id=_tenant_id(), pk=bill_run.pk)
        .values_list("bill_date", "due_days", "period_end", "cycle__bill_day", "cycle__due_days")
        .first()
    )
    if not row:
        return None, None
    run_bill_date, run_due_days, period_end, cycle_bill_day, cycle_due_days = row
    return (
        runs.effective_bill_date(run_bill_date, cycle_bill_day, period_end),
        runs.effective_due_days(run_due_days, cycle_due_days),
    )


def _line_facts(lines: list[models.InvoiceLine]) -> tuple[dict[str, Any], ...]:
    """What billing can honestly say about each line, in the caller's order.

    ONE query, joined along the reviewed cross-module FK
    `invoice_lines.service_id → tenancy.Service` (B2 §2 / DB-16) as a
    `values_list`, so a bill of forty lines is not forty round trips and
    nothing here instantiates another module's model.

    FOUR FACTS, and each one is a thing the line ITSELF records rather than
    something this module derives: its kind, its wording, the SERVICE it charged
    for, the CHARGE code behind a fee, and the TAX that produced it. Nothing is
    inferred from the description — matching on a line's wording was option D of
    OQ-116 and the PO declined it, because it costs nothing and misposts money
    silently the first time a tax is renamed or a catalogue is translated.

    ⚠ **HISTORY, kept because it is the reason two of these columns exist.**
    Until 2026-08-11 stage 6 wrote NO `service` on the lines it created, so
    every usage and base line of every real bill carried `service_code=None`
    and was refused below — the whole product could not issue a bill, and the
    message named GL mapping rather than the missing field. And `invoice_lines`
    had no tax column at all, so a tax line could not name its authority. Both
    are now written at draft time (`stages/assemble_document.py`), which is what
    the PO's ruling closing OQ-116 and this lane delivered together.

    ⚠ **AND `charge_id` WAS THE THIRD, until 2026-08-25.** This paragraph read
    *"`charge_id` is still NULL on every fee line, and that gap is REAL and is
    reported rather than worked around"* — and what "reported" meant in
    practice was that `_gl_account_for` refused every fee line and killed the
    whole bill with it (DEF-714). `stages/assemble_document.py` now writes it
    at draft time from the priced line, exactly as it writes `service` and
    `tax`, so the fee line names the code whose GL account BR-BIL-010 resolves.
    A fee that genuinely comes from no code — a late fee, priced by B4's rule —
    still arrives None here and is still refused by name.
    """
    joined = {
        str(pk): (code, str(charge_id) if charge_id else None, str(tax_id) if tax_id else None)
        for pk, code, charge_id, tax_id in models.InvoiceLine.objects.filter(
            tenant_id=_tenant_id(), pk__in=[line.pk for line in lines]
        ).values_list("pk", "service__code", "charge_id", "tax_id")
    }
    facts = []
    for line in lines:
        service_code, charge_id, tax_id = joined.get(str(line.pk), (None, None, None))
        facts.append(
            {
                "kind": line.kind,
                "description": line.description,
                "service_code": service_code,
                "charge_id": charge_id,
                "tax_id": tax_id,
                # CR-197-BRC10 / DEF-BIL-10648 — the line's own column.
                "discount_code": (getattr(line, "discount_code", None) or None),
            }
        )
    return tuple(facts)


def _authority_label(tax_id: Any, *, authority_label: Any, description: str) -> str:
    """The AUTHORITY this tax line is collected for, in a clerk's words.

    OQ-146's *"let the run report it"* asks the run to name the authority, so
    this is the one place that decides what "naming it" means when the name is
    not reachable. Three answers, and the degradation is deliberate:

      * the authority as rating records it — *"Harris County"* — which is what
        the ruling asks for and what S13 shows;
      * the line's own description when rating publishes no label read (an older
        deployment) or the tax resolves to nothing of this tenant's. It is
        weaker — *"Tax HARRIS-CO"* is a rate code — but it is TRUE, and it is
        the string the bill itself carries;
      * `the tax on <description>` when even that is blank.

    **It never returns an empty string and never the word None.** A break row a
    clerk cannot act on is the failure this whole read exists to remove, and a
    refusal that reads *"the authority None has no liability account"* would be
    worse than the code it replaced.

    The label is resolved INSIDE the refusal path and nowhere else — one extra
    query per BROKEN bill, never one per line of every bill that issues.
    """
    label = None
    if callable(authority_label):
        try:
            label = authority_label(tax_id)
        except Exception:  # pragma: no cover - a display read must never break a run
            # A refusal that fails while composing its own message would turn a
            # named break into a 500 and take the other 499 bills with it
            # (BR-BIL-055). The money-bearing decision was already taken above.
            label = None
    text = (label or "").strip()
    if text:
        return text
    fallback = (description or "").strip()
    return fallback or "the tax on this line"


def _gl_account_for(
    facts: dict[str, Any],
    *,
    revenue: Any,
    designation: Any,
    tax_liability: Any,
    charge_gl: Any,
    is_live: Any,
    authority_label: Any = None,
    customer_class: str | None = None,
    discount_gl: Any = None,
) -> str:
    """One line's GL account, from the ledger — or a refusal that names why.

    ⚠ **CR-197-BRC10 (BR-LED-801):** `customer_class` is the bill's account's
    class, handed to the revenue read so a class override wins for a usage or
    base line. It is passed only when known, so a revenue read that predates the
    keyword is still called exactly as before.

    THE KIND DECIDES WHICH LEDGER READ ANSWERS, and the kinds are billing's own
    vocabulary, which is exactly why this lives here: the ledger lane published
    the primitives and said in its trailer that it would not guess billing's
    line kinds. Every account below still comes from the ledger; the only thing
    billing contributes is which question to ask.

      * **usage / base** → the service's revenue account, `base=True` for a
        base charge. The usage/base SPLIT is the ledger's to resolve, including
        the fallback for services the signed chart does not split (a Trash base
        charge lands in Trash revenue) — asking for it twice would be two
        implementations of one rule.
      * **minimum_adjustment** → the `minimum_bill_adjustment` designation, one
        of the eleven the PO ruled on 2026-08-11.
      * **deposit** → the `deposit_liability` designation. US-LED-001's contract
        table: *"First-bill deposit line | (within issue entry) | deposit
        liability — never revenue"*. Added 2026-08-16 (DEF-181): the deposit
        line used to arrive as a FEE and was refused by the branch below for
        want of a charge code it could never have, so **no first bill carrying a
        deposit could issue at all** — and the refusal a clerk read talked about
        charge codes.
      * **discount** → the `discount_contra_revenue` designation, the
        THIRTEENTH, added by the PO's ruling of 2026-08-28 that closed
        `DEF-536`: *"you will need differnt GL code for these - dont keep them
        in same, create differnt category as required and keep them in it"*.

        **Until that ruling this branch DID NOT EXIST**, so a bill carrying a
        reduction fell off the bottom of this function and was refused by the
        generic *"line kind has no GL rule"* sentence — every bill for every
        customer with a discount, drafting and previewing and never issuing
        (DEF-536, filed by the DEF-502 lane that created the reachable state).
        The blocker was a money DECISION and not a missing line of code, which
        is why it waited for a PO ruling rather than being guessed.

        Worked, on the frozen GT-1 bill with a 10.00 reduction: electric usage
        **CR 82.08**, base **CR 18.50**, the discount account **DR 10.00**, AR
        **DR 90.58** — both sides 100.58. Netted against 4100 the same bill
        reports **72.08** of electric revenue the utility never earned at that
        price, which is the whole difference the ruling makes.

        Still refused, by name and never guessed: a tenant whose chart has no
        account carrying the designation, and one who has deactivated it (IS-1).
        Both are one edit on Settings → Configure.

      * **fee** → BR-BIL-010: *"charge codes carry their own GL"*. The account
        is `rating.charges.gl_account_id`, resolved from the line's own
        `charge_id` through **rating's** published read
        (`gl_account_id_for_charge`) and then checked for liveness through the
        ledger's — the same two-owner shape as a tax line, and for the same
        reason: rating owns the MAPPING, the ledger owns the ACCOUNT.

        **Until 2026-08-25 this branch REFUSED EVERY FEE LINE, unconditionally,
        without reading the charge id it was handed** — because nothing wrote
        `invoice_lines.charge_id`: the column shipped in the first migration
        and had no writer anywhere in the repo. At the same time BR-RAT-117 (PO
        2026-08-22, *"ruccuring and Autom apply land on bill"*) puts a fee line
        on the ordinary bill of every tenant that configures a recurring or
        auto-apply charge code. So the draft assembled correctly, every gate
        passed, and **the tenant could issue no bill at all** (DEF-714). The
        assembler now stamps the code at draft time and this resolves it — PO
        ruling 2026-08-25, option A, *"Make issue read the charge code"*.

        Still refused, by name and never guessed: a fee line that names no code
        at all — a LATE FEE is exactly that, its amount computed from B4's own
        rule rather than from a tenant code, and it has no account to resolve
        to; and a code the tenant has not yet pointed at an account, or has
        pointed at one they since deactivated (IS-1).
      * **tax** → the AUTHORITY's own 2200-series liability account, resolved
        from the line's `tax_id` through **rating's** published read
        (`liability_gl_account_id_for_tax`) and then checked for liveness
        through the ledger's. This is BR-BIL-069, the PO's ruling of 2026-08-11
        closing OQ-116 — verbatim: *"For each atheority have separate account
        and tagging; but also ensure you allow Use to manage it since every
        utility may not have every account."* B5 line 74 (❄️ finance-signed
        2026-08-08) already read *"2200-series Tax payable per authority (tenant
        authorities mint their own)"*; the code simply had not implemented it.

        Until that ruling this branch REFUSED, and it refused every ordinary
        bill with it, because a tax line could not say whose tax it was: the
        $8.30 on the reference $117.01 bill is not one tax but State of Texas
        $6.29 + Harris County $1.01 + City of Katy $1.00, three debts to three
        authorities. Now each of the three names its own tax and lands in its
        own account.

        TWO READS, NOT ONE, and the second is not ceremony. Rating owns the
        MAPPING (`taxes.liability_gl_account_id` — the tenant's, editable on
        S13, and deliberately the ONLY home for that fact: the PO declined a
        second ledger-side table). The ledger owns the ACCOUNT, so only the
        ledger can say whether the account is still live — an account the
        tenant deactivated after mapping it (IS-1) would otherwise be frozen
        onto an immutable line, and revenue in a retired bucket is no easier to
        repair than revenue in none.

        Still refused, by name and never guessed: a tax line that names no tax
        at all, and a tax whose authority the tenant has not yet given an
        account. The second is the ordinary state of a fresh tenant and is
        **OQ-146** — whether the product should also refuse it at SETUP time is
        not settled, and this module does not settle it by acting.
    """
    kind = facts["kind"]
    if kind in ("usage", "base"):
        service_code = facts["service_code"]
        if not service_code:
            raise BillingRuleError(
                f"a {kind} line ({facts['description']!r}) names no service, so its "
                "revenue account cannot be resolved (BR-BIL-010). The map is keyed on "
                "the service; a line that does not say which service it charged for "
                "cannot be placed, and per-service revenue cannot be reported."
            )
        if customer_class:
            account_id = revenue(
                service_code, base=(kind == "base"), customer_class=customer_class
            )
        else:
            account_id = revenue(service_code, base=(kind == "base"))
        if not account_id:
            raise BillingRuleError(
                f"service {service_code!r} has no revenue account configured, so its "
                f"{kind} line cannot be stamped (BR-BIL-010). A human sets this on the "
                "GL mapping page; nothing here picks a bucket for it."
            )
        return str(account_id)
    if kind == "minimum_adjustment":
        account_id = designation(GL_MINIMUM_BILL_ADJUSTMENT)
        if not account_id:
            raise BillingRuleError(
                f"no ledger account carries the {GL_MINIMUM_BILL_ADJUSTMENT!r} "
                "designation, so a minimum-bill adjustment line cannot be stamped "
                "(BR-BIL-010). The designation is one of the eleven the PO ruled on "
                "2026-08-11; an account has to be given it on the GL mapping page."
            )
        return str(account_id)
    if kind == "deposit":
        # US-LED-001's contract table: *"First-bill deposit line | (within issue
        # entry) | deposit liability — NEVER revenue"* (BR-BIL-012, WE-6). The
        # DEBIT side is the bill's own AR total, so this line's account is the
        # credit half and the deposit rides into the books inside the ordinary
        # per-GL bucket the posting handoff already builds.
        account_id = designation(GL_DEPOSIT_LIABILITY)
        if not account_id:
            raise BillingRuleError(
                f"no ledger account carries the {GL_DEPOSIT_LIABILITY!r} designation, so "
                "this first bill's security-deposit line cannot be stamped (BR-BIL-010 / "
                "BR-BIL-012). A deposit is the CUSTOMER'S money and is a liability, never "
                "revenue — nothing here falls back to a revenue account, because a bill "
                "that recognised somebody's deposit as income would be doing it on an "
                "immutable record (hard rule 4). The designation is one of the twelve and "
                "is seeded as 2300; a human re-designates one on the GL mapping page."
            )
        return str(account_id)
    if kind == "discount":
        # PO ruling 2026-08-28, closing DEF-536, verbatim: *"you will need
        # differnt GL code for these - dont keep them in same, create differnt
        # category as required and keep them in it"*.
        #
        # THE LINE'S AMOUNT IS NEGATIVE AND THE ACCOUNT IS NOT THE SERVICE'S.
        # BR-RAT-068 makes the reduction its own line beside the full tariff
        # amount so *"subsidy granted is reportable"*; netting it into the
        # service's revenue account would destroy the one figure that makes it
        # reportable, and would make the revenue account state a price the
        # utility never sold at. The SIDE flip — a negative bucket on this
        # account becoming a DEBIT of its absolute value — is
        # `posting_seam.posting_buckets`', not this function's: here the line
        # only learns WHICH account it belongs to.
        # CR-197-BRC10 / DEF-BIL-10648: the discount's OWN account first, when
        # the line names its code and the discount points somewhere live. An
        # unmapped discount — or one whose account was retired — falls through
        # to the designation, which is exactly today's posting.
        own = discount_gl(facts.get("discount_code")) if (discount_gl and facts.get("discount_code")) else None
        if own and is_live(own):
            return str(own)
        account_id = designation(GL_DISCOUNT_CONTRA_REVENUE)
        if not account_id:
            # BR-BIL-010 (the stamp) · BR-BIL-055 (a break never blocks the run)
            # · CLAUDE.md hard rule 4 (an issued bill is immutable) · PO ruling
            # 2026-08-28. The ids live HERE and not in the sentence below: CR-016
            # keeps a rule id off a utility user's screen and keeps the honesty
            # beside the code, which is what this comment is.
            raise BillingRuleError(
                "this bill gives the customer a discount and no account in your chart is set "
                "up to hold discounts, so the line cannot be placed and the bill does not "
                "issue. A discount is recorded in an account of its own and is never taken off "
                "a service's revenue: a discount hidden inside electricity revenue is "
                "indistinguishable from electricity sold cheaper, on a record that can never be "
                "edited afterwards. Your chart starts with 4300 'Customer discounts "
                "(contra-revenue)' for this; set one up, or point this one somewhere else, "
                "under Settings → Configure. The rest of the run carries on — this is one "
                "named break and the other bills go out."
            )
        if not is_live(account_id):
            # BR-BIL-010 · IS-1 (deactivate-first, never delete). Ids here rather
            # than in the sentence, for the reason above (CR-016).
            raise BillingRuleError(
                "the account this bill's discount would go to has been switched off, or "
                "belongs to another utility, so the line cannot be placed and the bill does "
                "not issue. The account is frozen onto the bill the moment it issues, so a "
                "discount recorded against a retired account is as hard to repair as one "
                "recorded against none. Point discounts at a live account under "
                "Settings → Configure."
            )
        return str(account_id)
    if kind == "fee":
        charge_id = facts["charge_id"]
        if not charge_id:
            raise BillingRuleError(
                f"a fee line ({facts['description']!r}) names no charge code, so its GL "
                "account cannot be resolved. BR-BIL-010 gives every charge code its own GL "
                "(`rating.charges.gl_account_id`), and the line has to say which code it "
                "came from. Nothing here substitutes a revenue account for a fee. A fee "
                "reaches this state when it was NOT produced by a charge code at all. "
                "⚠ A LATE FEE IS NO LONGER ONE OF THOSE (BR-BIL-075, PO ruling "
                "2026-08-26, closing DEF-719): its AMOUNT still comes from B4's own rule "
                "(`apps/billing/late_fee.py`), and it now names the tenant's own late-fee "
                "charge code for the account, the same way NSF and reconnection fees do "
                "(`apps/billing/decisions._late_fee_charge_id`). So this refusal means a "
                "gap in what PRODUCED the line, not a tenant's configuration, and no "
                "clerk can close it on a screen."
            )
        account_id = charge_gl(charge_id)
        if not account_id:
            # ⚠ **THIS REFUSAL WAS REACHED BY EVERY TENANT THIS PRODUCT HAD EVER
            # CREATED, AND NOTHING SAID SO FOR WEEKS (`DEF-2386`, 2026-09-02).**
            # The platform seed shipped 28 charge codes and had never written
            # `gl_account_id` on any of them, so a fee line refused here on a
            # brand-new tenant — while the same tenant's sample estate issued
            # 95 invoices, because the branches above resolve a USAGE or BASE
            # line from the SERVICE's designation and never look at a charge
            # code. That asymmetry is the whole reason it stayed invisible, and
            # it is worth remembering the next time a branch here is read as
            # "rare": two of the seeded codes are `recurring`, and BR-RAT-117
            # puts a recurring code on every ordinary bill.
            #
            # **NOTHING IN THIS FILE CHANGED.** The seed was fixed (`CR-066`:
            # `apps.ledger.chart.CHARGE_CODE_ACCOUNTS` and
            # `apps.rating.services.apply_default_gl_accounts`), so this branch
            # now means what its message always claimed — a code the TENANT has
            # not pointed at an account — rather than the state every tenant
            # shipped in. The guard is right and was right; it had nothing to
            # resolve.
            raise BillingRuleError(
                f"the charge code behind this bill's fee line ({facts['description']!r}) has "
                "no GL account, so the line cannot be stamped and this bill does not issue "
                "(BR-BIL-010): *charge codes carry their own GL*. A human points the code at "
                "an account on S13 (Taxes & fees -> charge codes -> GL account); nothing "
                "here falls back to a service's revenue account, because a fee posted into "
                "the electric revenue bucket is indistinguishable from electricity sold, on "
                "a record that is frozen the moment it issues. THE REST OF THE RUN "
                "CONTINUES — this is one named break and the other bills in the batch issue "
                "(BR-BIL-055)."
            )
        if not is_live(account_id):
            raise BillingRuleError(
                f"the charge code behind this bill's fee line ({facts['description']!r}) "
                "points at a ledger account that is not this tenant's, or is one they have "
                "deactivated (IS-1), so the line cannot be stamped (BR-BIL-010): the stamp "
                "freezes with the bill, so a line posted to a retired account is as "
                "unrepairable as one posted to none. A human re-points the code on S13."
            )
        return str(account_id)
    if kind == "tax":
        tax_id = facts["tax_id"]
        if not tax_id:
            raise BillingRuleError(
                f"a tax line ({facts['description']!r}) names no tax, so the authority it "
                "was collected for is unknown and its liability account cannot be resolved "
                "(BR-BIL-010 / BR-BIL-069). Each authority has its OWN 2200-series account "
                "(PO ruling 2026-08-11, OQ-116), so 2200-01 and 2200-03 are "
                "indistinguishable from a line that names neither. Nothing here picks one: "
                "tax credited to the wrong authority is a filing error with a regulator on "
                "the other end of it, not a rounding error. A tax line reaches this state "
                "when its plan rule carried a rate_override for a jurisdiction with no "
                "`taxes` row behind it — a gap a human closes on S13."
            )
        account_id = tax_liability(tax_id)
        if not account_id:
            authority = _authority_label(
                tax_id, authority_label=authority_label, description=facts["description"]
            )
            raise BillingRuleError(
                f"{authority} has no liability account, so this bill's tax line "
                f"({facts['description']!r}) cannot be stamped and this bill does not issue "
                "(BR-BIL-010 / BR-BIL-069). Each tax authority is owed into its OWN "
                "2200-series account and the TENANT chooses it — *'make them choose'* (PO "
                "2026-08-12, OQ-145); where a new account is needed the product GENERATES "
                "its code (OQ-147). Nothing is force-seeded and nothing here invents one: a "
                "guess remits money to the wrong government. A human maps it on S13 (Taxes "
                "& fees → liability GL). THE REST OF THE RUN CONTINUES — the PO ruled on "
                "2026-08-12 that a tax with no account is REPORTED BY THE RUN rather than "
                "blocked at setup (*'let the run report it'*, OQ-146), so this is one named "
                "break and the other bills in the batch issue (BR-BIL-055)."
            )
        if not is_live(account_id):
            authority = _authority_label(
                tax_id, authority_label=authority_label, description=facts["description"]
            )
            raise BillingRuleError(
                f"{authority} is mapped to a ledger account that is not this tenant's, or is "
                f"one they have deactivated (IS-1), so this bill's tax line "
                f"({facts['description']!r}) cannot be stamped (BR-BIL-010): the stamp "
                "freezes with the bill, so a line posted to a retired account is as "
                "unrepairable as one posted to none. A human re-points the tax on S13."
            )
        return str(account_id)
    raise BillingRuleError(
        f"line kind {kind!r} has no GL rule. Billing stores rating's kinds verbatim, so "
        "an unknown one means the seam changed and the bill would post to a bucket "
        "chosen by accident."
    )


def gl_stamps_for_lines(
    lines: list[models.InvoiceLine], *, customer_class: str | None = None
) -> tuple[str, ...]:
    """BR-BIL-010 — one GL account id per line, in order, or REFUSE.

    Billing asks; the LEDGER answers (PO ruling 2026-08-11, OQ-106: the ledger
    owns the maps, and a designation is an attribute on ledger accounts and on
    utility services). This module keeps no map, caches nothing and falls back
    to nothing. Two refusals carry the weight:

    * **The ledger publishes neither read.** Refused, naming both callables.
      Not an empty answer and not a NULL stamp: a line's `gl_account_id` is
      frozen the moment its bill leaves draft, so a bill issued un-stamped can
      never be repaired. Un-stamped revenue is money in no bucket, permanently.
    * **Any line the ledger cannot place.** Refused for the WHOLE bill — that
      is US-BIL-007 TC-5 verbatim: *"issue fails atomically if any line cannot
      resolve a GL (mapping incomplete → staff fixes US-BIL-009, nothing
      partial issues)."* Half a bill in the ledger is worse than no bill.

    FIVE READS, TWO OWNERS. Three are the ledger's (a service's revenue
    account, a designation's account, and whether an account is live); two are
    RATING's — a tax's liability account, which lives on
    `taxes.liability_gl_account_id` because the PO's OQ-116 closure kept one
    home for that mapping (BR-BIL-069), and a charge code's own account on
    `charges.gl_account_id` (DEF-714, PO ruling 2026-08-25), which is the read
    that lets a bill carrying a configured fee issue at all. Billing owns none
    of them and caches none of them; what billing contributes is which question
    a KIND asks.
    """
    revenue = _resolve(GL_MODULE, GL_REVENUE_READ)
    designation = _resolve(GL_MODULE, GL_DESIGNATION_READ)
    is_live = _resolve(GL_MODULE, GL_LIVENESS_READ)
    if revenue is None or designation is None or is_live is None:
        raise BillingRuleError(
            f"apps.{GL_MODULE}.selectors.{GL_REVENUE_READ} / {GL_DESIGNATION_READ} / "
            f"{GL_LIVENESS_READ} are not published, so no line can resolve its GL account "
            "(BR-BIL-010). The ledger owns the GL maps (PO ruling 2026-08-11, OQ-106 "
            "closed). Nothing is guessed and nothing issues un-stamped: the stamp is "
            "frozen at issue and could never be added later."
        )
    charge_gl = _resolve(CHARGE_GL_MODULE, CHARGE_GL_READ)
    if charge_gl is None:
        raise BillingRuleError(
            f"apps.{CHARGE_GL_MODULE}.selectors.{CHARGE_GL_READ} is not published, so a fee "
            "line cannot resolve its charge code's GL account (BR-BIL-010 / DEF-714). "
            "Rating owns that mapping — `charges.gl_account_id`, the tenant's own column, "
            "edited on S13 — for the same reason it owns a tax authority's. Refused rather "
            "than skipped: a bill that issued with its fee lines un-stamped would put the "
            "money in no bucket at all, permanently, because the stamp freezes at issue."
        )
    tax_liability = _resolve(TAX_GL_MODULE, TAX_GL_READ)
    if tax_liability is None:
        raise BillingRuleError(
            f"apps.{TAX_GL_MODULE}.selectors.{TAX_GL_READ} is not published, so a tax line "
            "cannot resolve the authority's liability account (BR-BIL-010 / BR-BIL-069). "
            "Rating owns that mapping — the PO closed OQ-116 on 2026-08-11 keeping ONE "
            "home for it (`taxes.liability_gl_account_id`) rather than a second table in "
            "the ledger. Refused rather than skipped: a bill that issued with its tax "
            "lines un-stamped would owe three authorities out of no bucket at all."
        )
    # The authority LABEL is display text for a refusal (OQ-146) and is
    # deliberately NOT part of the "half an interface is not an interface"
    # check above: a deployment whose rating lane has not published it must
    # still be able to refuse a bill correctly, just less helpfully.
    # `_authority_label` degrades to the line's own description.
    authority_label = _resolve(TAX_GL_MODULE, TAX_AUTHORITY_LABEL_READ)
    discount_gl = _resolve(CHARGE_GL_MODULE, DISCOUNT_GL_READ, DISCOUNT_GL_FILE)
    return tuple(
        _gl_account_for(
            facts,
            revenue=revenue,
            designation=designation,
            tax_liability=tax_liability,
            charge_gl=charge_gl,
            is_live=is_live,
            authority_label=authority_label,
            customer_class=customer_class,
            discount_gl=discount_gl,
        )
        for facts in _line_facts(lines)
    )


def _customer_class_of(invoice: models.Invoice) -> str | None:
    """The bill's account's customer class code, or None (CR-197-BRC10).

    `customers.account_types.code` read as a value along the reviewed FK —
    the same fact `gather._customer_class` gives the pricing engine, so the
    class that priced a bill and the class that places its revenue agree.
    """
    code = (
        models.Invoice.objects.filter(tenant_id=_tenant_id(), pk=invoice.pk)
        .values_list("account__account_type__code", flat=True)
        .first()
    )
    text = str(code).strip() if code else ""
    return text or None


def _refuse_unless_issuable(invoice: models.Invoice) -> None:
    """Everything that must be TRUE before the row is touched, in one place.

    All four are cheap, and all four are unrepairable afterwards. This is also
    the service-layer half of hard rule 4 that the billing 0002 migration says
    it relies on: the developer database is SQLite and has no triggers, so a
    guard that lived only in Postgres would not be a guard where the code is
    written.
    """
    if invoice.status != models.INVOICE_DRAFT:
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} is already {invoice.status} and "
            "cannot be issued again (BR-BIL-004). An issued bill is a fact about what a "
            "customer was told; a correction is a new row, never a second issue."
        )
    if not invoice.invoice_no:
        raise BillingRuleError(
            f"draft {invoice.pk} carries no number. BR-BIL-063 (PO ruling 2026-08-11) "
            "allocates the number when the DRAFT is created — issue mints nothing, so "
            "there is nowhere here to make one up. A bill nobody can quote is not a bill."
        )
    if not invoice.bill_payload:
        raise BillingRuleError(
            f"bill {invoice.invoice_no} has no locked document instance (BR-BIL-030). It "
            "is stamped when the draft is priced, and a bill issued without one can only "
            "ever be re-rendered from live rows that have since moved — which is the "
            "failure the ruling *'keep lock data for that bill'* exists to prevent."
        )
    if not invoice.payload_version:
        raise BillingRuleError(
            f"bill {invoice.invoice_no} has no payload_version (BR-BIL-031). The payload "
            "is a data CONTRACT and a renderer must know which shape it is reading; "
            "without the version the first change to that shape breaks every reprint."
        )


def _money_text(value: Decimal | None) -> str | None:
    """A money figure at the column's own NUMERIC(18,6) scale, as text.

    A FORMAT, not a rounding event (CLAUDE.md rule 2 — round only at
    finalization or display). `bill_payload` is jsonb and JSON has no decimal
    type, so a `Decimal` written straight in becomes a FLOAT the moment anything
    reads it back — the one thing rule 2 forbids outright. Six places is the
    scale the value already has, and `release._money_text` takes the identical
    decision for `bill_run_releases.summary` for the identical reason.
    """
    return None if value is None else f"{value:.6f}"


def _prior_bill_totals(invoice: models.Invoice) -> dict[str, Decimal]:
    """Every EARLIER bill of this account, at the total it was issued with.

    Billing's own column, read from billing's own table — the half of BR-BIL-035
    that does not cross a boundary. `invoices.total` is immutable once issued
    (hard rule 4), so this is a fact rather than a recomputation.

    The bill being stamped cannot appear: it is a DRAFT at this moment and the
    filter takes the locked statuses only. Excluding it by id as well would be a
    second, weaker guarantee that could drift from the first.
    """
    rows = (
        models.Invoice.objects.filter(
            tenant_id=_tenant_id(),
            account_id=invoice.account_id,
            status__in=models.INVOICE_LOCKED_STATUSES,
        )
        .exclude(pk=invoice.pk)
        .values_list("pk", "total")
    )
    return {str(pk): total for pk, total in rows}


def _mark_issued(
    invoice: models.Invoice,
    *,
    issued_at: datetime,
    due_date: date,
    template_id: Any,
    template_version: int,
    frozen: frozen_bill.FreezeOutcome,
) -> None:
    """The one statement in this product that makes a bill immutable.

    ⚠ **`frozen` IS A REQUIRED ARGUMENT AND THAT IS THE WHOLE REASON THIS
    FUNCTION EXISTS.** The status move used to be five assignments and a `save()`
    inline in `_do_issue`. It is a function now so that keeping the document
    cannot be forgotten by a future call site and cannot be reordered past the
    status move by a refactor — `require_frozen` raises here rather than the
    product shipping an issued bill nobody kept a copy of.

    It is the same shape `notifications.dispatcher._mark_sent` takes for a
    letter, and for the same argument: **a guarantee whose only enforcement is
    the order of two statements is one line of refactoring away from being gone**
    (hard-won law 1). The ORDER in `_do_issue` is still the first guarantee; this
    is the second.
    """
    frozen_bill.require_frozen(invoice, frozen)
    invoice.status = models.INVOICE_ISSUED
    invoice.issued_at = issued_at
    invoice.due_date = due_date
    invoice.template_id = template_id
    invoice.template_version = template_version
    invoice.save(
        update_fields=[
            "status",
            "issued_at",
            "due_date",
            "template_id",
            "template_version",
            "updated_at",
        ]
    )


def _whole_account_window(invoice: models.Invoice, position: Any) -> dict[str, Any] | None:
    """🔒 HUMAN-REVIEW-PENDING · **`OQ-217` CLOSED — THE WHOLE ACCOUNT SINCE THE
    LAST BILL** (PO 2026-10-01, option A; BR-BIL-1065). Verbatim: *"A · Show the
    whole account: last bill $34.00 − paid $120.00 + new charges $37.25 = $48.75
    credit, nothing to pay"*.

    Until this ruling the two middle figures were read over the still-OPEN
    earlier bills only, so a customer who paid $120.00 against a $34.00 bill was
    printed *"Previous balance 0.00 · Payments 0.00 · Total due 37.25"* while
    the account held $48.75 of their money (`DEF-BIL-8670`, J72 AC-2026-00007).

    THE THREE FIGURES, EACH SOMEBODY ELSE'S AND ASKED BY NAME (B1):

      * **where the account stands now, before this bill** = what is still open
        (the open earlier bills + the unsettled migrated opening balance — the
        existing `prior_position_for_account`) **minus** what the utility holds
        on account beyond what settled that opening balance (payments' signed
        credit position; a NEGATIVE one is a debt, BR-PAY-041, and adds);
      * **payments & credits** = everything received since the last bill
        (`payments_received_for_account`, refunds netted), allocated or not;
      * **previous balance** = where the account stands + what was received —
        what the account owed when the last bill was sent.

    So `previous − payments + current = total due` is BR-BIL-035's arithmetic
    UNCHANGED, and the total due is where the whole account stands. ❄️ WE-1 —
    one unpaid 45.00 bill, nothing received, no credit — still prints
    **45.00 − 0.00 + 247.87 = 292.87**. The credit drawn at issue
    (`apply_credit_at_issue`, after this stamp) moves money between the account
    and this bill and does not change where the account stands, so the printed
    figure stays right after it (the `DEF-BIL-8670` gap).

    **`DEF-BIL-8412` — *Apply next bill*.** Where this run holds the clerk's
    current *Apply next bill* for a payment posted after the period, payments
    posted after the period end are left OUT of this bill (out of the payments
    line, and added back to where the account stands) and the bill stamps
    `payments_through` = its period end, so the NEXT bill counts them.

    Returns None when payments cannot answer — the caller keeps the previous
    window and says so (`basis`), never a guess.
    """
    from apps.billing import open_balance as open_balance_reader

    return open_balance_reader.whole_account(
        invoice.account_id,
        position,
        since=open_balance_reader.payments_since(invoice.account_id, exclude_invoice_id=invoice.pk),
        through_date=invoice.period_end if _defers_late_payments(invoice) else None,
    )


def _defers_late_payments(invoice: models.Invoice) -> bool:
    """`DEF-BIL-8412` — does this run hold a CURRENT *Apply next bill* answer for
    this account's payment posted after the cut-off?"""
    run = getattr(invoice, "bill_run", None)
    if run is None:
        return False
    from apps.billing import decisions

    return any(
        str(row.account_id) == str(invoice.account_id)
        and row.case == "paid_after_cutoff"
        and row.choice == decisions.CHOICE_APPLY_NEXT_BILL
        for row in decisions.current_decisions(run)
    )


def _plan_not_yet_due(
    invoice: models.Invoice, *, due_date: date | None, stands: Decimal
) -> dict[str, Decimal] | None:
    """🔒 HUMAN-REVIEW-PENDING · BR-BIL-1061 (PO 2026-10-01), verbatim: *"A · Ask
    for new charges + this month's instalment: $62 + $45 = $107, with the rest of
    the plan shown as not yet due"*. The plan's arrears stay on the earlier bills
    and in the balance forward; the part of the ACTIVE plan falling due after
    this bill's due date is subtracted from what the bill asks. A clerk's *Skip
    this month* (fixed-charge case 5) leaves this month's instalment not yet due
    too. Capped at what the account owes from before this bill, so a plan can
    never turn a bill into a credit. None when there is no active plan."""
    split = payments_seam.plan_instalments_for_bill(invoice.account_id, due_by=due_date)
    if not split:
        return None
    later = Decimal(str(split.get("not_yet_due") or 0))
    now = Decimal(str(split.get("due_now") or 0))
    run = getattr(invoice, "bill_run", None)
    if run is not None:
        from apps.billing import decisions

        if any(
            str(row.account_id) == str(invoice.account_id)
            and row.case == "plan_instalment_due"
            and row.choice == decisions.CHOICE_SKIP
            for row in decisions.current_decisions(run)
        ):
            later, now = later + now, Decimal("0")
    owed = stands if stands > 0 else Decimal("0")
    later = later if later < owed else owed
    if later <= 0:
        return None
    return {"not_yet_due": later, "due_now": now}


def _stamp_balance_forward(
    invoice: models.Invoice, *, currency: str, due_date: date | None = None
) -> dict[str, Any]:
    """BR-BIL-035 — write the arrears into the locked instance, at issue.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THIS IS THE FIELD THE BILL COULD NOT PRINT (DEF-116, OQ-117)        ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `apps/billing/documents.py` renders every charge line correctly and then
    prints `—` where **TOTAL DUE** belongs, because `invoices.total` is the
    CURRENT CHARGES alone and the arrears were nowhere in `bill_payload`. The
    PO ruled on 2026-08-12 (OQ-117) that such a bill *"issue and report it"*,
    and `documents._run_problems` names the bill on every run. This closes the
    gap that report exists for; the report stays, because a deployment whose
    payments module is unreachable still cannot print the figure and must still
    say so.

    THE ARITHMETIC IS BR-BIL-035'S OWN, and nothing here invents a term:

        previous balance − payments received + this period = total due

    ❄️ Worked on WE-1, the frozen example (`03-field-map.md` §Summary box):
    **45.00 − 0.00 + 247.87 = 292.87**.

    ⚠ **AMENDED 2026-08-27 — BR-BIL-160, THE PO'S OWN RULING (OQ-530 CLOSED).**
    Verbatim: *"so when we run first bill; we have to take opening balance into
    account. you will generate first bill and against previous balance you will
    mention the opening balance."*

    Until that day `previous_balance` read **open INVOICES only**, and a
    migrated opening balance is not an invoice — it lives in
    `account_opening_buckets` with its balanced opening journal entry. So a
    customer who arrived owing **$8,240.00** got a first bill whose previous
    balance printed `—`, and the product told them they were square. ❄️ Worked
    on GT-16's `A-12103`: four bands `84.20 / 62.10 / 0.00 / 121.00` = **267.30**
    now stands where the dash was.

    THE FOUR FIGURES AND WHERE EACH COMES FROM:

      * `previous_balance` — Σ of the account's still-open earlier bills at the
        totals they were ISSUED with (billing's own immutable column) **plus its
        migrated opening balance** — CUSTOMERS' figure, asked for by name
        through `customers_seam` (B1); billing owns no opening bucket and
        computes none.
      * `payments_credits` — Σ of what payments has already allocated against
        those same bills **plus the settled part of that opening balance**. Both
        halves are PAYMENTS' figures, asked for by name (B1); billing owns no
        allocation row and computes none. **The second operand moves with the
        first on purpose:** an opening balance that joined only
        `previous_balance` would be asked for again on every later bill,
        because a payment against it allocates to no invoice in the set.
      * `current_charges` — `invoices.total`, this period and nothing else.
      * `total_due` — the sum of the three, which by construction equals
        *what is still open on the earlier bills* + *this bill*. The pair above
        FOOTS, so the page's arithmetic adds up whatever window the PO rules for
        the split (OQ-217 — ruled 2026-10-01: the whole account since the last
        bill, `_whole_account_window`, BR-BIL-1065).

    **AN UNREACHABLE SEAM STAMPS NULLS, NEVER ZEROS.** Every figure stays absent
    and the reason travels in `problems`; the document prints `—` exactly as it
    does today and the run reports the bill. `0.00` would tell a customer in
    arrears that they are square, on a page that is immutable the moment it is
    written.

    NOTHING HERE ROUNDS. The figures are sums of already-finalized totals and
    are written at the column's own six-decimal scale as TEXT — a Decimal in
    jsonb comes back a float, which rule 2 forbids. B4's rounding law is frozen
    and a stamping helper is not where one of its decisions is taken.

    Returns the block it wrote, for the audit row.
    """
    position = payments_seam.prior_position_for_account(
        invoice.account_id,
        totals_by_invoice_id=_prior_bill_totals(invoice),
        # BR-BIL-160 (PO 2026-08-27, OQ-530) — the FOURTH source. Asked of
        # customers BY NAME through billing's own seam, exactly as the arrears
        # half is asked of payments: billing owns no opening bucket and
        # computes none (B1). Handed IN rather than resolved inside the
        # payments seam so each seam keeps asking only the module it names.
        opening=customers_seam.opening_position_for_account(invoice.account_id),
    )
    current_charges = invoice.total
    previous_balance = position.previous_balance
    payments_credits = position.payments_credits
    open_balance = position.open_balance
    # 🔒 OQ-217 CLOSED (PO 2026-10-01, BR-BIL-1065) — the whole account since
    # the last bill. The open-bills window is kept, and SAID in `basis`, only
    # where payments cannot answer the new reads.
    whole = _whole_account_window(invoice, position)
    basis = BALANCE_FORWARD_BASIS_FALLBACK
    if whole is not None:
        previous_balance = whole["previous_balance"]
        payments_credits = whole["payments_credits"]
        open_balance = whole["open_balance"]
        basis = BALANCE_FORWARD_BASIS
    total_due = None if open_balance is None else open_balance + current_charges
    # 🔒 BR-BIL-1061 (PO 2026-10-01) — a payment plan's part not yet due is not
    # asked for: $62 + $45 = $107, the other $225 printed as not yet due.
    plan = (
        None
        if open_balance is None
        else _plan_not_yet_due(invoice, due_date=due_date, stands=open_balance)
    )
    if plan is not None and total_due is not None:
        total_due = total_due - plan["not_yet_due"]
    block: dict[str, Any] = {
        "previous_balance": _money_text(previous_balance),
        "payments_credits": _money_text(payments_credits),
        "current_charges": _money_text(current_charges),
        "total_due": _money_text(total_due),
        # BR-BIL-1061 — the plan's part not yet due (subtracted above) and this
        # month's instalment (inside the total due). Absent without a plan.
        **(
            {
                "plan_not_yet_due": _money_text(plan["not_yet_due"]),
                "plan_due_now": _money_text(plan["due_now"]),
            }
            if plan is not None
            else {}
        ),
        # DEF-BIL-8412 — the day this bill's payments line stops; the next bill
        # counts what was posted after it. Absent on every other bill.
        **(
            {"payments_through": whole["payments_through"]}
            if whole is not None and whole.get("payments_through")
            else {}
        ),
        # DEF-099 — a money figure never travels without the currency it is in.
        "currency": currency,
        "prior_open_bills": position.bills,
        # BR-BIL-160 — the MIGRATED half of the two figures above, stamped
        # separately so an immutable bill can always say how much of its
        # previous balance the account ARRIVED with and how much of that has
        # been settled. Both are already inside `previous_balance` /
        # `payments_credits`; they are not a fifth and sixth thing to add up.
        # 0.00 on every account that was created in this product rather than
        # migrated into it — which is nearly all of them.
        "opening_balance": _money_text(position.opening_balance),
        "opening_settled": _money_text(position.opening_settled),
        "opening_buckets": position.opening_buckets,
        #: WHICH WINDOW the two middle figures were read over. A value and not a
        #: comment, because it is stamped into an immutable record and a ruling
        #: may move it (OQ-217 did, 2026-10-01): a later reader must be able to tell which definition
        #: their bill was written under without dating the code.
        "basis": basis,
        "basis_oq": BALANCE_FORWARD_BASIS_OQ,
        "problems": [dict(entry) for entry in position.problems],
    }
    payload = dict(invoice.bill_payload or {})
    payload["balance_forward"] = block
    # The four names A19 §1.3 prints and `documents._summary` reads, at the TOP
    # level as well. Duplicated deliberately and written from one dict so they
    # cannot diverge: the renderer has read `payload["previous_balance"]` since
    # it was written, and moving that read would be a second lane's file changing
    # under a third lane's contract.
    for key in ("previous_balance", "payments_credits", "total_due"):
        payload[key] = block[key]
    if "plan_not_yet_due" in block:
        payload["plan_not_yet_due"] = block["plan_not_yet_due"]
    invoice.bill_payload = payload
    invoice.save(update_fields=["bill_payload", "updated_at"])
    return block


#: The two keys `bill_template_versions.options` holds for BR-BIL-021's *"bill
#: messages and footer"*, and the two `documents._footer` has read off the
#: payload since it was written (`payload["message"]`, `payload["ways_to_pay"]`).
#:
#: ⚠ **THE OPTIONS BLOB HAD NO KEY VOCABULARY AT ALL, AND STILL HAS NO
#: VALIDATOR** — `templates_service.save_draft` takes whatever dict it is given.
#: These two names are therefore stated HERE, where they are read, and the pair
#: is the whole contract: a tenant's message reaches its bills when it is stored
#: under `bill_message`, and nowhere else. A third name would be a second
#: convention nobody could see (decision log 2026-08-30, CR-052 task 10).
TEMPLATE_OPTION_BILL_MESSAGE = "bill_message"
TEMPLATE_OPTION_WAYS_TO_PAY = "ways_to_pay"

#: Where each stamped key lands on the payload — the names the RENDERER already
#: reads. Written from one map so the two cannot drift into meaning different
#: things on the two sides of a bill (`documents._footer` / `_stamp_bill_copy`).
BILL_COPY_KEYS: tuple[tuple[str, str], ...] = (
    (TEMPLATE_OPTION_BILL_MESSAGE, "message"),
    (TEMPLATE_OPTION_WAYS_TO_PAY, "ways_to_pay"),
)


def _stamp_usage_history(invoice: models.Invoice) -> dict[str, Any] | None:
    """A19 §1.7 — freeze the twelve-month usage block onto the bill (CR-052 t8).

    🔒 HUMAN-REVIEW-PENDING. Runs inside `issue_invoice`'s transaction, on a row
    that is still a DRAFT, which is the only window `bill_payload` can be
    written in at all (billing 0006 freezes it the moment the status moves).

    **WHY AT ISSUE AND NOT AT DRAFT.** The same reason BR-BIL-035's arrears are
    stamped here: a draft is written when the bill is PRICED and may sit for
    days, and the twelve months a customer is shown must be the twelve months
    as they stood when their bill was produced. Stamping it at draft would show
    a stale eleventh month on any bill that waited.

    **WHY IT IS STAMPED AT ALL AND NOT JOINED AT RENDER TIME.**
    `documents.py`'s `usage_history_not_available` says it exactly: the eleven
    earlier periods are not in the snapshot, and *"reading them from
    `meter_reads` would be the live join BR-BIL-030 forbids"*. Freezing the
    block is what lets the chart exist without the render ever leaving the
    bill.

    **THE WINDOW ENDS AT THE BILL'S OWN PERIOD END, NEVER AT TODAY.**
    BR-TEN-043's event-time law: a June bill re-issued in September carries
    June's twelve months, and a reprint in 2033 carries the same twelve it
    carried on the day it was sent.

    Returns the problem when there is one, so the caller can put it on the
    result; the bill issues either way (BR-BIL-055).
    """
    outcome = metering_seam.usage_history_for(invoice.account_id, as_of=invoice.period_end)
    if outcome.block is None:
        return outcome.problem
    payload = dict(invoice.bill_payload or {})
    payload["usage_history"] = outcome.block
    invoice.bill_payload = payload
    invoice.save(update_fields=["bill_payload", "updated_at"])
    return None


def _pin_for_account(
    draft: models.Invoice, *, run_pin: tuple[Any, int]
) -> tuple[tuple[Any, int], dict[str, Any] | None, bool]:
    """BR-BIL-025 — **THIS ACCOUNT's** template, resolved inside the issue loop.

    HUMAN-OWNED · HUMAN-REVIEW-PENDING (🔒 — it decides which layout is frozen
    onto an immutable financial record; hard rule 4). CR-052 W3 task 12.

    THE RULE, VERBATIM: *"the template resolves per ACCOUNT: account override →
    category default → tenant fallback"*. Until now `issue_run` took ONE pin and
    applied it to every bill in the pass, which the run endpoint reported on
    every response as `one_template_pin_for_the_whole_run`: *"a tenant that has
    set a DIFFERENT template for a consumer category does not get it here — every
    bill of the run pins the fallback."*

    ⚠ **THE ORDER IS NOT IMPLEMENTED HERE.** `templates_service.resolve_for` has
    held all three legs since 2026-08-15 and is the ONE implementation of the
    ruled chain; this function supplies the two ACCOUNT facts it always took as
    arguments and had nowhere to get. Writing the precedence a second time here
    is exactly the *"re-guessed at every call site"* that function's own
    docstring warns about.

    THREE OUTCOMES:

      * **resolved** — the account answered, the chain ran, and the pin is this
        account's own. `(pin, None, True)`.
      * **unreadable** — customers publishes no election read, or the account is
        not resolvable. The RUN's pin stands and the reason rides back, so a
        per-category template that is NOT being honoured is visible rather than
        silent. `(run_pin, problem, False)`.
      * **refused** — the chain itself refuses (an override naming a template
        that does not exist; a tenant with no template; a template with no
        PUBLISHED version). ⚠ **This RAISES rather than falling back**, because
        `resolve_for` says so in its own words: *"a silent fallback would send
        the wrong layout to the one customer somebody deliberately singled
        out."* `issue_run` catches it per bill (BR-BIL-055) — one named break,
        the other bills carry on.
    """
    election = customers_seam.template_election_for_account(draft.account_id)
    if not election.readable:
        return run_pin, election.problem, False
    # Imported at CALL time: `templates_service` imports `template_models`, which
    # imports this module's `models`, and a module-level import here would close
    # the loop. The same reason `_template_options` below imports its row type
    # inside the function.
    from apps.billing import templates_service

    template, version = templates_service.resolve_for(
        consumer_category=election.consumer_category,
        account_override_template_id=election.template_override_id,
    )
    return (template.pk, version.version_no), None, True


def _template_options(template_id: Any, template_version: int) -> dict[str, Any]:
    """The PINNED version row's `options` — the tenant's own bill copy.

    A lookup of the PIN and never of "the current template", for the reason
    `documents._layout_key_of` states beside the identical query: BR-BIL-026
    pins template + version at issue, so a bill from July must not start
    carrying the message a tenant typed in August. There is no `.latest()`, no
    `status=published` filter and no ordering here, deliberately.

    `{}` for a bill whose pin names no row — every bill issued before the
    template library landed — rather than a refusal: those bills printed no
    message and BR-BIL-026 says a reprint shows what was sent.
    """
    if template_id is None:
        return {}
    from apps.billing.template_models import BillTemplateVersion

    # `tenant_id` explicitly, although RLS FORCE would refuse a cross-tenant row
    # anyway (hard rule 1). `documents._layout_key_of` runs the identical lookup
    # without one and is left alone — this file's own convention is the explicit
    # filter (`_line_facts` and `models.InvoiceLine` beside it both carry it),
    # and on a money path the belt is worth the line.
    options = (
        BillTemplateVersion.objects.filter(
            tenant_id=_tenant_id(), template_id=template_id, version_no=template_version
        )
        .values_list("options", flat=True)
        .first()
    )
    return dict(options) if isinstance(options, dict) else {}


def _stamp_bill_copy(
    invoice: models.Invoice, *, template_id: Any, template_version: int
) -> dict[str, Any] | None:
    """BR-BIL-021 — freeze the tenant's bill message and ways-to-pay (CR-052 t10).

    🔒 HUMAN-REVIEW-PENDING. Inside the issue transaction, on a still-DRAFT row.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE TWO FIELDS THE DOCUMENT HAS BEEN ASKING FOR SINCE IT WAS WRITTEN║
    ╚══════════════════════════════════════════════════════════════════════╝
    `documents._footer` reads `payload["message"]` and `payload["ways_to_pay"]`
    and has always found neither, so A19 §1.8's whole footer printed as two
    named absences — and one consequence is the one CR-052 names: **the
    late-fee terms this product is required to disclose are charged correctly
    and never appear on the paper.** They are the TENANT's words (BR-BIL-021
    gives the tenant a bill message and a footer), and this is what carries
    them.

    **THE SOURCE IS THE PINNED TEMPLATE VERSION'S `options`, WHICH IS THE
    RATIFIED HOME.** `apps/tenancy/settings_families.py` says so directly of
    BR-BIL-021's config family: *"bill messages/footer … already has a
    different ratified home"*, and `template_models.BillTemplateVersion.options`
    is that home — *"what the tenant legitimately chooses: its bill messages and
    footer (BR-BIL-021)"*. Reading a tenant-wide setting instead would create a
    SECOND home for one value, which is the drift `settings_seam` refuses for
    the finance controls and for the same reason.

    Freezing it here (rather than joining it at render) is BR-BIL-030: a tenant
    who rewrites their message next year has not rewritten the bill they sent
    this year, and `bill_template_versions` is append-only precisely so the two
    can be told apart.

    **AN EMPTY MESSAGE IS STAMPED AS AN ABSENCE, NOT AS AN EMPTY STRING.** A
    tenant who has typed nothing has said nothing, and `documents._field`
    already turns a `None` into a named absence that cites BR-BIL-021 — which
    is a truer document than one printing a blank line under "Message".
    """
    options = _template_options(template_id, template_version)
    payload = dict(invoice.bill_payload or {})
    stamped: dict[str, Any] = {}
    for option_key, payload_key in BILL_COPY_KEYS:
        value = options.get(option_key)
        text = str(value).strip() if isinstance(value, str) else None
        payload[payload_key] = text or None
        stamped[payload_key] = text or None
    invoice.bill_payload = payload
    invoice.save(update_fields=["bill_payload", "updated_at"])
    if any(stamped.values()):
        return None
    return {
        "code": "tenant_has_written_no_bill_copy",
        "br_ref": "BR-BIL-021 · A19 §1.8",
        "detail": "this tenant's pinned bill template carries neither a bill message nor "
        "ways-to-pay, so the footer of this bill states both as absences. That is the "
        "tenant's own copy and nothing here composes one for them — including the "
        "late-fee terms, which are the tenant's words to write and are charged whether "
        "or not they are printed. One edit on the Templates screen fills both.",
    }


#: The masthead keys, tenancy's name for each beside the payload's. One tuple
#: so the two sides cannot drift — the same shape, and the same reason, as
#: `BILL_COPY_KEYS` above.
MASTHEAD_KEYS: tuple[str, ...] = ("utility_name", "utility_address", "utility_contact")


def _cycle_label_for(bill_run: Any) -> str | None:
    """The cycle a customer would recognise — its name, else its code (`08-A`).

    ONE query, by id, reading two columns across the reviewed `bill_runs.cycle_id`
    FK (B2 §2). `None` on an ad-hoc run, which belongs to no cycle at all
    (`BillRun.cycle` is nullable since billing 0021) and must print an absence
    rather than a borrowed label.
    """
    if bill_run is None:
        return None
    row = (
        models.BillRun.objects.filter(pk=bill_run.pk)
        .values_list("cycle__name", "cycle__code")
        .first()
    )
    if not row:
        return None
    name, code = row
    for value in (name, code):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _stamp_plan_instalment(invoice: models.Invoice) -> dict[str, Any] | None:
    """🔒 DEF-BIL-8243 · *Add to bill* (BR-BIL-1053) — the payment-plan
    instalment a clerk added to this bill, printed as its own line.

    HUMAN-REVIEW-PENDING. Inside the issue transaction, on a still-DRAFT row —
    the only window `bill_payload` can be written in (billing 0006).

    **WHAT IT IS, AND WHAT IT DELIBERATELY IS NOT.** The line names the
    instalment the Check found (`seq`, `due_on`, `amount` on the run's saved
    `plan_instalment_due` finding — payments' own figures, read by payments'
    seam at Check) and nothing else. It is **not an invoice line and not a
    charge**: a plan's instalments are slices of arrears that are already on
    earlier bills, already in receivables through their own postings, and
    already in this bill's balance forward (BR-BIL-035). Making it a charge
    would bill the same dollars twice and post them twice. So `invoices.total`,
    every invoice line and every journal line are untouched; the payload gains
    `payment_plan_instalment` and the document prints it. Worked: $270 on a
    plan of $45 × 6, instalment 3 due 15 Oct, clerk chose *Add to bill* → the
    September bill prints *"Payment plan instalment 3: $45.00 due 2026-10-15"*,
    its total is its own charges, and its amount due is unchanged.

    Only when this run holds a CURRENT `add_to_bill` answer for the account;
    every other bill's payload stays byte-identical. Returns None always — a
    missing finding means there is no line to print, never a refused bill.
    """
    run = getattr(invoice, "bill_run", None)
    if run is None:
        return None
    from apps.billing import check_models, decisions

    chosen = any(
        str(row.account_id) == str(invoice.account_id)
        and row.case == "plan_instalment_due"
        and row.choice == decisions.CHOICE_ADD_TO_BILL
        for row in decisions.current_decisions(run)
    )
    if not chosen:
        return None
    fact = (
        check_models.BillRunFinding.objects.filter(
            tenant_id=invoice.tenant_id,
            bill_run=run,
            account_id=invoice.account_id,
            code="plan_instalment_due",
        )
        .order_by("-checked_at")
        .first()
    )
    params = dict(getattr(fact, "params", None) or {})
    if params.get("amount") is None or not params.get("due_on"):
        return None
    payload = dict(invoice.bill_payload or {})
    payload["payment_plan_instalment"] = {
        "seq": params.get("seq"),
        "due_on": str(params["due_on"]),
        "amount": str(params["amount"]),
        "currency": params.get("currency") or invoice.currency,
    }
    invoice.bill_payload = payload
    invoice.save(update_fields=["bill_payload", "updated_at"])
    return None


def _stamp_bill_header(
    invoice: models.Invoice, *, bill_date: date | None, bill_run: Any
) -> dict[str, Any] | None:
    """`DEF-2865` — who sent this bill, for what period, and when.

    🔒 HUMAN-REVIEW-PENDING. Inside the issue transaction, on a still-DRAFT row —
    the only window `bill_payload` can be written in at all (billing 0006 freezes
    it the moment the status moves).

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  EVERY BILL THIS PRODUCT HAS ISSUED PRINTED AN EM-DASH FOR ALL SIX   ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `documents._masthead` asks the payload for `utility_name`, `utility_address`
    and `utility_contact`; `_meta` asks it for `cycle` and `bill_date`. Nothing
    wrote any of them, so the PO's BL-2608-000048 could not say who sent it, what
    cycle it belonged to, or when it was raised — while printing a DUE date
    derived from the bill date it did not show.

    ⚠ **THE ABSENCES WERE ALL CORRECTLY RECORDED, WHICH IS WHY THIS LASTED.**
    Each one names its rule and its reason, and `tc8` asserts they ARE named
    absences — so the gap read as a decision taken and honoured, and the only
    test on it passed whether it was a week old or permanent. The machinery is
    right; what was missing is anybody counting.

    **AT ISSUE AND NOT AT DRAFT**, for the reason `_stamp_bill_copy` and
    `_stamp_balance_forward` beside it give: a draft may sit for days, and these
    are facts about the bill that was SENT.

    **STAMPED AND NOT JOINED** (BR-BIL-030). A utility that changes its trading
    name next year has not changed the bill it sent this year, and the render is
    pinned to two queries so a live read would fail on the count as well as on
    the rule — the identical shape as `DEF-2852`'s service names.

    **NOTHING IS INVENTED.** A tenant that has written no address gets `None` and
    the document says so with BR-BIL-030 beside it; a run with no cycle (a
    one-off bill belongs to none) stamps no cycle. The problem returned when
    NOTHING could be stamped rides the result like the delivery seam's
    (BR-BIL-055) — an unattributable bill is worse than a refused one only if
    nobody is told, and this is the telling.
    """
    payload = dict(invoice.bill_payload or {})
    masthead = tenancy_seam.bill_masthead()
    stamped: dict[str, Any] = {}
    for key in MASTHEAD_KEYS:
        value = masthead.get(key)
        text = str(value).strip() if isinstance(value, str) and value.strip() else None
        payload[key] = text
        stamped[key] = text
    # BR-BIL-070 — the CLERK's typed date where the run carries one, else the
    # cycle's own bill day. `_due_terms_for` has already resolved that precedence
    # for the due date; this stamps the SAME figure rather than re-deriving it,
    # because a bill whose printed bill date and printed due date disagree about
    # which day the bill was raised is a dispute waiting to happen.
    payload["bill_date"] = bill_date.isoformat() if bill_date else None
    payload["cycle"] = _cycle_label_for(bill_run)
    # CR-172-BRC10 — the logo this bill is ISSUED with: the stored PNG's id in
    # the common document store, a write-once object, so a reprint draws this
    # exact picture whatever is uploaded later (BR-TEN-017, BR-BIL-030
    # "branding reference"). None when the utility has no logo in the store; it
    # is not one of the identity facts below, so a bill with no logo is not
    # reported as unattributable.
    payload["utility_logo"] = tenancy_seam.bill_logo()
    invoice.bill_payload = payload
    invoice.save(update_fields=["bill_payload", "updated_at"])
    if any(stamped.values()):
        return None
    return {
        "code": "utility_identity_not_recorded",
        "br_ref": "BR-BIL-030 · A19 §1.1",
        "detail": "this tenant has recorded no trading name, no mailing address and no "
        "support contact, so the masthead of this bill states all three as absences and "
        "the customer cannot tell who sent it. Nothing here invents one — the subdomain "
        "is a routing fact, not a name anybody chose. One edit on the Settings company "
        "tab fills all three.",
    }


def issue_invoice(
    invoice: models.Invoice,
    *,
    issued_at: datetime,
    template_id: Any,
    template_version: int,
    actor: Any = None,
    dispatch_not_before: datetime | None = None,
) -> models.Invoice:
    """Issue ONE draft. All of it, or none of it, in one transaction.

    `issued_at` is a PARAMETER and never a clock read. BR-TEN-043's event-time
    law: the caller names when the business event happened, so a resumed batch,
    a replay and a re-run all stamp the same moment rather than three. (It is
    also why nothing in this module reads a wall clock — G6 greps every money
    path for one, and rightly.)

    `template_id` / `template_version` are the BR-BIL-026 pin. They are supplied
    rather than derived because the assignment that would derive them
    (BR-BIL-025 — category default or account override) has no table yet, and a
    bill issued with no pin can never record which template rendered it: the
    columns are frozen by the same trigger that freezes the money. So issue
    refuses without them rather than issuing a bill that BR-BIL-026 can never
    be satisfied for. Reported in `ISSUE_UNAVAILABLE`.

    `dispatch_not_before` is S31 step 6's *"send now vs scheduled"* choice,
    carried onto the delivery rows. NULL means eligible immediately. Like
    `issued_at` it is a PARAMETER and never a clock read (BR-TEN-043).

    The posting and delivery outcomes come back on the returned bill as
    TRANSIENT `.posting` / `.delivery` attributes — not columns, never saved.
    The return type stays the invoice because that is what every caller binds
    to; `issue_run` reads the attributes to report journal-entry and queue
    counts on its own result.

    Raises `BillingRuleError` for every condition a human can act on — an
    already-issued bill, a numberless draft, a missing locked instance, an
    unpinnable template, a cycle with no due terms, an unmapped line, a bill
    the books refuse. The caller records the break and carries on to the next
    bill (BR-BIL-055); it does not roll the run back.

    **A POSTING REFUSAL REFUSES THE ISSUE.** `posting_seam.PostingRefused` is a
    `BillingRuleError` like any other, and it is raised inside this transaction,
    so the bill stays a discardable DRAFT rather than becoming an immutable
    record whose money never reached the books (BR-BIL-011, CLAUDE.md rule 4).
    """
    if template_id is None or template_version is None:
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} has no template pin. BR-BIL-026 "
            "pins the template and its version AT ISSUE and a reprint renders that "
            "version forever; both columns freeze the moment the status moves, so a bill "
            "issued without a pin can never say what it was rendered with."
        )

    with transaction.atomic():
        # Re-read under a row lock inside the transaction: two workers racing
        # the same draft must serialise here rather than both writing an issue.
        # (SQLite has no row locks and ignores this; Postgres is where a batch
        # actually runs, and the status check below is re-evaluated on the
        # locked row rather than on the caller's stale copy.)
        locked = models.Invoice.objects.select_for_update().get(
            tenant_id=_tenant_id(), pk=invoice.pk
        )
        _refuse_unless_issuable(locked)

        bill_date, due_days = _due_terms_for(locked.bill_run)
        due_date = derive_due_date(
            bill_date,
            due_days,
            # B13 — a run with no cycle is a one-time run; its refusal says so.
            cycle_less=locked.bill_run is None or locked.bill_run.cycle_id is None,
        )

        lines = list(locked.lines.all().order_by("created_at", "id"))
        if not lines:
            raise BillingRuleError(
                f"bill {locked.invoice_no} has no lines. A bill with a total and no "
                "lines cannot be explained to the customer who receives it, and its "
                "posting handoff would have nothing to credit."
            )
        # ── BR-BIL-035 — THE BALANCE-FORWARD SECTION IS STAMPED HERE ────────
        # *"The figures are STAMPED into `bill_payload` at issue (BR-BIL-030),
        # so a reprint shows the arrears as they stood on the bill date, never
        # as they stand today."* This is that stamp, and it is at issue because
        # the rule says at issue: stage 6 wrote the payload at DRAFT time, when
        # the customer may not yet have made the payment this bill has to show.
        #
        # BEFORE the render on purpose. The render is BR-BIL-033's precondition
        # and it is supposed to prove that THE document the customer gets can be
        # produced; a render run before the stamp would prove a different page —
        # the one with a dash where the total due belongs.
        #
        # STILL A DRAFT AT THIS LINE, which is the only window in which
        # `bill_payload` can be written at all (billing 0006 freezes it the
        # moment the status moves).
        balance_forward = _stamp_balance_forward(
            locked, currency=locked.currency, due_date=due_date
        )
        # ── CR-052 W2 · THE TWO BLOCKS THE DOCUMENT ASKS FOR AND NEVER GETS ──
        # Both stamped HERE for the same three reasons the balance-forward block
        # above is: the payload is writable only while this row is a draft, the
        # figures must be as they stood on the BILL DATE rather than as they
        # stand today, and the render below is BR-BIL-033's precondition — a
        # render taken before these stamps would prove a DIFFERENT page from the
        # one the customer receives, and `frozen_bill` would then keep that one.
        #
        # Neither can stop a bill. Each returns a named problem instead, which
        # rides the result exactly as the delivery and posting seams' do
        # (BR-BIL-055): a missing usage chart and an unwritten tenant message
        # are both worse as a refused bill than as an absence on the page.
        stamp_problems = [
            problem
            for problem in (
                _stamp_usage_history(locked),
                _stamp_bill_copy(
                    locked, template_id=template_id, template_version=template_version
                ),
                # `DEF-2865` — the masthead, the cycle and the bill date. Third
                # on this list and for the same three reasons as the two above:
                # the payload is writable only while this row is a draft, these
                # are facts about the bill that was SENT, and the render below is
                # BR-BIL-033's precondition — a render taken before this stamp
                # would prove a page with six em-dashes on it rather than the
                # page the customer receives.
                _stamp_bill_header(locked, bill_date=bill_date, bill_run=locked.bill_run),
                # 🔒 DEF-BIL-8243 — *Add to bill* on a plan instalment: the
                # instalment is printed as its own line. Same window, same
                # reasons as the three above; it never refuses a bill.
                _stamp_plan_instalment(locked),
            )
            if problem is not None
        ]
        #
        # BR-BIL-033, CONFIRMED (PO 2026-08-10, OQ-089): *"Render BEFORE issue;
        # a failed render REFUSES the issue — stage 6 is a precondition of
        # issuing, not a consequence of it."*
        #
        # HERE, and not after the status moves, because after the status moves
        # there is no repair: the template pin freezes with the money, and a
        # bill that is immutable and unrenderable is the one state this pipeline
        # had no escape hatch for. The draft is still discardable at this line.
        #
        # The pin passed in is the pin this call is ABOUT to write, so the
        # document that gates the issue is the document the customer would get
        # — not a different one rendered on a different template. `lines` is
        # handed over because it is already loaded; the render adds no query.
        #
        # ⚠ **IT NO LONGER DISCARDS THE RESULT, AND THIS PARAGRAPH USED TO SAY
        # IT DID (CR-049 task 4, 2026-08-30).** It read: *"BR-BIL-036 wants the
        # document STORED and sent to the print vendor and there is nowhere to
        # put it, so this proves renderability and discards the result."* There
        # is somewhere to put it now — tenancy's write-once document store — and
        # `frozen_bill.freeze_at_issue` below keeps BOTH serialisations of THIS
        # render. The document that gates the issue is therefore the document
        # that is kept and the document the customer is later shown: one render,
        # not three.
        #
        # A `BillingRuleError` from here is still an ordinary break: this bill
        # does not issue, the rest of the batch does (BR-BIL-055).
        #
        # ⚠ THE DUE DATE IS PUT ON THE IN-MEMORY ROW FIRST, AND THAT IS LOAD-
        # BEARING RATHER THAN TIDY. `documents._meta` reads `invoice.due_date`,
        # which is NULL on a draft, so a render taken before this assignment
        # produces a bill with a dash where the due date belongs — a different
        # document from the one `GET /invoices/{id}/document` serves a minute
        # later. Freezing THAT would freeze a page no customer ever gets, which
        # is the substitution BR-NOT-027 exists to forbid. The row is not saved
        # here; the assignment only makes the render honest.
        locked.due_date = due_date
        rendered = documents.render_invoice(
            locked,
            template_id=template_id,
            template_version=template_version,
            lines=lines,
        )

        # ── BR-NOT-027 (PO 2026-08-30) — KEEP THE BILL, THEN ISSUE IT ───────
        # *"any legal document when send - it is freezed … otherwie everytime we
        # reproduce it using data in table, we might change something about it
        # and that is not correct"*.
        #
        # BEFORE the status moves, and inside this transaction, for the same
        # reason the render is: after the status moves there is no repair. A
        # bill that is immutable and has no kept copy can never acquire one, and
        # every reprint of it for seven years would be a rebuild presented as the
        # document. A refusal here takes the whole issue with it and the draft is
        # still a correctable draft.
        #
        # `frozen_bill` argues why a bill needed this at all when BR-BIL-030
        # already freezes its data: the DATA is frozen, the tenant's template ROW
        # is frozen by billing 0019's trigger, and **the CODE that draws the page
        # is frozen by nothing**. A layout is Python, and a build that publishes a
        # different library sends an already-pinned bill down `_layout_for`'s
        # stand-in door. Neither writes anything on the invoice, which is exactly
        # why hard rule 4 does not catch either.
        frozen = frozen_bill.freeze_at_issue(
            locked, rendered, moment=issued_at, actor=actor, job=None if actor else "billing.issue"
        )
        if not frozen.may_issue:
            problem = frozen.problem or {}
            # ⚠ THE SENTENCE NAMES NO RULE ID, DELIBERATELY (G28). This one CAN
            # reach a person — it travels on the run report a clerk reads — and
            # BR-NOT-027 is a string only we can look up. The rule is cited in
            # this block's comment above and in `frozen_bill`'s docstring, which
            # is where a reader who needs it will be.
            raise BillingRuleError(
                f"bill {locked.invoice_no or locked.pk} was rendered and could not be KEPT "
                f"({problem.get('code', 'unknown')}): {problem.get('detail', '')} "
                "Keeping a copy of the document is a precondition of issuing it, so the bill "
                "stays a draft rather than becoming an immutable record of a document nobody "
                "has."
            )

        # CR-197-BRC10 (BR-LED-801): the account's customer class decides
        # whether a class revenue row applies. Read along the reviewed
        # cross-module FK `invoices.account → customers.accounts` as a value,
        # the same shape `_line_facts` uses for the service code.
        stamps = gl_stamps_for_lines(lines, customer_class=_customer_class_of(locked))
        for line, gl_account_id in zip(lines, stamps, strict=True):
            line.gl_account_id = gl_account_id
            # Lines are still on a DRAFT here, which is the only window in which
            # they can be written at all — their invoice's status is what
            # freezes them (billing 0002).
            line.save(update_fields=["gl_account_id", "updated_at"])

        # BR-AUD-003: `before` is the changed-fields diff and must be READ, not
        # assumed. A draft with a due date already on it is not a state this
        # module writes, but a trail row that reported None for it would be
        # evidence of something that did not happen.
        before = {
            "status": locked.status,
            "due_date": locked.due_date.isoformat() if locked.due_date else None,
            "issued_at": locked.issued_at.isoformat() if locked.issued_at else None,
            "template_id": str(locked.template_id) if locked.template_id else None,
            "template_version": locked.template_version,
        }
        _mark_issued(
            locked,
            issued_at=issued_at,
            due_date=due_date,
            template_id=template_id,
            template_version=template_version,
            frozen=frozen,
        )

        # Hard rule 7 — inside the same transaction, so the bill cannot stand
        # without its trail row (core.audit fails loudly rather than losing it).
        # No payload content goes in: BR-AUD-006 keeps PII out of the trail, and
        # the locked instance is on the row itself for anyone entitled to read it.
        audit.money_action(
            actor,
            "invoice.issued",
            "invoice",
            str(locked.pk),
            before=before,
            after={
                "status": locked.status,
                "invoice_no": locked.invoice_no,
                "issued_at": issued_at.isoformat(),
                "due_date": due_date.isoformat(),
                "template_id": str(template_id),
                "template_version": template_version,
                "total": str(locked.total),
                "currency": locked.currency,
                "lines_gl_stamped": len(stamps),
                # Hard rule 7 covers the ARREARS too, since 2026-08-15. The
                # balance-forward figures are stamped into an immutable record
                # and are what the customer is asked to pay; a trail row that
                # carried only the current charges could not answer "what did
                # this bill say they owed?" after a dispute. BR-AUD-006 is
                # unaffected — these are money figures, never PII.
                "balance_forward": balance_forward,
                # BR-NOT-027, 2026-08-30. The store writes its own
                # `document.stored` row per artefact; this is the OTHER half of
                # the same question — "was this bill kept, and as what" — asked
                # of the bill rather than of the document. A regulator holding a
                # bill asks it in that direction, and an issue trail row that
                # could not answer it would send them to a second register to
                # find out whether an original exists at all. Hashes, never
                # bytes: BR-AUD-006 keeps content out of the trail.
                "documents_frozen": len(frozen.documents),
                "document_hashes": {
                    document.content_type: document.content_hash for document in frozen.documents
                },
                "job": None if actor is not None else "billing.issue",
            },
        )

        # ── STAGE 7 (BR-BIL-037) — the balanced posting handoff ─────────────
        # BR-BIL-011: *"one bill = one document + N GL-coded lines + one
        # balanced journal entry (DR AR total / CR per-GL buckets); posting
        # service is the sole writer."* This EMITS that entry. It writes no
        # journal line — the seam resolves `apps.ledger.posting.post` by name
        # and the ledger's own sole-writer trigger (ledger/0004) is what makes
        # that structural rather than a promise (CLAUDE.md rule 5).
        #
        # INSIDE THIS TRANSACTION, and that is the whole design decision. A bill
        # and its journal entry are ONE fact: committed apart, the two states
        # they can reach are both unrepairable — an issued, immutable bill whose
        # money is in no ledger account (hard rule 4 leaves no path to add the
        # entry later), or an entry with no document to explain it, which is
        # exactly the drift BR-LED-007 exists to detect. A `PostingRefused` here
        # takes the issue with it and the draft is still a draft.
        #
        # AFTER the status moves and after the audit row, because the entry's
        # `source_id` is an invoice that exists and because the lines it buckets
        # are the ones this call has just stamped. `locked.lines` is NOT
        # re-queried: `lines` are the same objects, carrying the stamps written
        # a few lines above, so the handoff reads BR-BIL-010's answer rather
        # than asking the same question a second time and risking a different
        # one.
        #
        # `posted_at` is the bill's own `issued_at` — a PARAMETER, never a clock
        # read (BR-TEN-043, gate G6), so a resumed batch stamps one moment
        # rather than three. The BOOK date is the seam's to name from the bill
        # (US-BIL-009 §1's handoff carries `service_date`).
        posting = posting_seam.post_bill_issue(
            locked,
            lines=lines,
            posted_at=issued_at,
            actor=actor,
        )

        # ── 🔒 DEF-2430 / DEF-BIL-5341 — WHAT THIS BILL GRANTED, RECORDED ────
        # PO ruling 2026-10-03, *"A · Yearly caps don't count down - a"*. Each
        # discount line names its programme (`invoice_lines.discount_code`,
        # billing/0040) and rating records one `discount_grants` row per
        # enrolment, against the version in force on the service date, so a
        # yearly cap, a lifetime cap and a budget count down from REAL bills.
        # Worked (PO 2026-10-04): $35.00 credit, $300.00 calendar-year cap, an
        # $80.00 bill — Jan–Aug −$35.00 ($280.00), Sep −$20.00, Oct–Dec $0.00.
        #
        # INSIDE THIS TRANSACTION, after the status moves and after the
        # posting, for the reason the posting is: the grant names an invoice
        # that exists, and a bill and the subsidy it spent are ONE fact. A
        # refusal (the account no longer holds that enrolment on the service
        # date) takes THIS bill's issue with it and no other's (BR-BIL-055).
        # Idempotent per (enrolment, bill) at the database (rule 6), so a
        # replayed issue cannot count a subsidy twice.
        grants = rating_seam.record_discount_grants(locked, lines=lines, actor=actor)

        # BR-BIL-016 — one delivery record per bill per channel, INSIDE this
        # transaction. Not after it: an issued bill is immutable, so a bill
        # committed without its delivery rows is a bill nobody would ever be
        # sent and no later path would notice. Here, a queue failure takes the
        # issue with it and the draft is still a draft.
        #
        # AFTER the money is written rather than before, because the delivery
        # row belongs to a bill that exists: the queue row carries the invoice's
        # id as its source ref, and BR-BIL-036's print row is a promise about a
        # document, not about a draft that may yet break on a GL stamp.
        #
        # THE SEAM QUEUES; IT DOES NOT SEND. No provider is contacted anywhere
        # in this call (email ACTIVATION is R4), and its result names what it
        # could not do — see `ISSUE_UNAVAILABLE`.
        #
        # ⚠ IT ALSO NAMES THE SET-12 EVENT NOW (CR-048 wave B, 2026-08-29), and
        # NOTHING IS PASSED FROM HERE. `delivery_seam.event_for_bill` reads
        # `locked.corrects_invoice_id` — `bill_corrected` for the rebill leg of
        # a correction, `bill_ready` for every other bill — so the utility's
        # Settings → Notifications rule is applied to this bill and a channel it
        # switched off is not queued. `locked` is the row re-read under the lock
        # above, so the link `corrections.execute_restatement` stamped on the
        # draft is the one read here. The event is DERIVED rather than a
        # parameter on this function precisely so the three callers of
        # `issue_invoice` — the cycle run, `fee_bill`, and the correction — have
        # nothing to get wrong; the argument is in `event_for_bill`'s docstring.
        delivery = delivery_seam.queue_bill_delivery(
            locked,
            dispatch_not_before=dispatch_not_before,
            actor=actor,
        )

        # ── THE TWO PAYMENTS-SIDE WRITES THAT BELONG AT ISSUE ───────────────
        # Both were BUILT and CALLED BY NOTHING — hard-won law 2, and the
        # payments lane could not close it from its own side because the caller
        # is billing's (B1).
        #
        # INSIDE THIS TRANSACTION, after the status moves, for the same reason
        # the posting handoff and the delivery rows are: each names an invoice
        # that EXISTS. A credit spent against a draft that then broke on a GL
        # stamp would be a customer's money moved for a bill nobody received,
        # and an intent promising a capture for a bill that never issued would
        # have staff chasing money that is not owed.
        #
        # CREDIT FIRST, INTENT SECOND, and the order is load-bearing: the
        # intent's amount is what the customer will actually be asked for, so
        # the drawdown has to have happened before it is recorded. (What the
        # intent carries today is `invoices.total`, and that is REPORTED rather
        # than quietly netted — see `ISSUE_UNAVAILABLE`.)
        #
        # NEITHER MAY BREAK A RUN THAT IS OTHERWISE FINE: an unpublished seam
        # is reported on the outcome and the bill issues (BR-BIL-055). A
        # payments RULE refusal is a different thing — it is money, it is
        # translated into `BillingRuleError` by the seam (DEF-047's lesson) and
        # it takes THIS bill's issue with it and no other's.
        credit = payments_seam.apply_credit_at_issue(
            locked, actor=actor, occurred_on=issued_at.date()
        )
        autopay = payments_seam.record_autopay_intent(locked, actor=actor)

        # ── THE BILLED LOCK ON EVERY READ THIS BILL PRICED (DEF-098) ────────
        # `apps.metering.services.mark_read_billed` was published FOR THIS CALL
        # and nothing made it, so a read that HAD been billed still read as
        # `committed`: a clerk correcting it took the plain supersede path and
        # NO correction linkage was recorded — the exact failure US-MET-016
        # exists to prevent (BR-MET-053, "read fix and money fix travel
        # together").
        #
        # INSIDE THIS TRANSACTION and AFTER the status moves, for the same
        # reason the posting handoff and the delivery rows are: the lock names
        # an invoice that EXISTS. A read locked against a draft that then broke
        # on a GL stamp would be a read nobody could correct in the ordinary
        # way, for a bill nobody ever received.
        #
        # The ids come off the bill's OWN frozen snapshot (BR-BIL-030), which
        # is the only surface that survives to here — `issue_invoice` receives
        # the Invoice and nothing else. See the seam's docstring for why that
        # is a better answer than a run-scoped map.
        #
        # IT CANNOT BREAK A RUN (BR-BIL-055): every failure rides
        # `.reads.problems` and the bill issues. The lock protects a FUTURE
        # correction; the bill is the money.
        reads = metering_seam.mark_reads_billed(locked, actor=actor)
        # 🔒 DEF-BIL-8280 (PO direction 2026-09-30) — a clerk's estimate this
        # bill charged is saved into Meter Reads AT ISSUE (never at draft), so
        # the next real reading is trued up against it and the same usage is
        # not billed twice. Reported, never raised (BR-BIL-055).
        estimates = metering_seam.record_billed_estimates(locked, actor=actor)
        # 🔒 PO ruling 2026-09-30 (fixed-charge case 5) — a clerk's *"Skip
        # this month"* on a plan instalment EXTENDS the plan by one month,
        # through the PAYMENTS module's own service, at issue and never at
        # draft. Its own savepoint (law 14) and never raised: a bill is not
        # refused for want of a plan to extend (BR-BIL-055).
        plan_extension: dict[str, Any] = {"extended": False, "reason": "not_a_run_bill"}
        if getattr(locked, "bill_run_id", None) is not None:
            try:
                with transaction.atomic():
                    plan_extension = payments_seam.extend_plans_for_skips(
                        bill_run=locked.bill_run, account_id=str(locked.account_id), actor=actor
                    )
            except Exception as refused:  # noqa: BLE001 — reported, see above
                logger.warning("plan extension for %s refused: %s", locked.pk, refused)
                plan_extension = {"extended": False, "reason": "refused", "ends_on": None}
        # 🔒 CR-185-BRC10 (coordinator ruling 2026-10-14) — a move-out whose
        # clerk tied the residue back to the owner RECORDED that tie-back at
        # commit and posts it NOW, when its final bill is in the books: after
        # this bill's entry, its deposit legs and the credit drawdown above,
        # so the amount is what the closed account actually owes. Customers
        # owns the figure and the ledger writes the entry; billing only names
        # the bill and the moment (B1, hard rule 5). Its own savepoint (law 14)
        # and never raised: the bill is not refused for want of a tie-back
        # (BR-BIL-055), and a refused post leaves the tie-back pending.
        balance_to_owner: dict[str, Any] = {"posted": False, "reason": "not_a_final_bill"}
        if getattr(locked, "bill_type", None) == "final":
            try:
                with transaction.atomic():
                    balance_to_owner = customers_seam.post_pending_balance_to_owner(
                        locked, issued_at=issued_at, actor=actor
                    )
            except Exception as refused:  # noqa: BLE001 — reported, see above
                logger.warning("balance to owner for %s refused: %s", locked.pk, refused)
                balance_to_owner = {"posted": False, "reason": "refused"}
    # TRANSIENT attributes, never columns and never saved: `issue_run` needs the
    # posting and delivery outcomes to report them, and the return type of this
    # function is the BILL — which is what every existing caller and test binds
    # to.
    locked.posting = posting
    locked.grants = grants
    locked.delivery = delivery
    locked.credit = credit
    locked.autopay = autopay
    locked.reads = reads
    locked.estimates = estimates
    locked.plan_extension = plan_extension
    locked.balance_to_owner = balance_to_owner
    # CR-052 W2 — the two payload stamps report the same way everything else
    # here does. A tuple and not a seam outcome because there is no seam to
    # name: one of them asks metering (through `metering_seam`) and the other
    # reads billing's own template row, and what a run needs from both is the
    # same short list of named absences.
    locked.snapshot_problems = tuple(stamp_problems)
    return locked


def _issue_one(
    draft: models.Invoice,
    *,
    run_pin: tuple[Any, int],
    template_pin_explicit: bool,
    issued_at: datetime,
    actor: Any,
    dispatch_not_before: datetime | None,
) -> tuple[models.Invoice, bool, dict[str, Any] | None]:
    """ONE bill of `issue_run`'s pass: its template pin, then its issue.

    Returns `(billed, per_account, pin_problem)`. Lifted out of the loop
    unchanged (B11, 2026-09-30) so the loop can hold the two steps inside ONE
    savepoint — the counters stay in the loop, updated only after the bill has
    actually issued, so a bill that breaks is counted as a break and nothing
    else.

    BR-BIL-025 — this ACCOUNT's template, or the run's with its reason. A
    chain that REFUSES (an override naming a template that does not exist) is
    one named break for this bill and the pass continues, which is BR-BIL-055
    exactly. Falling back would send the wrong layout to the one customer
    somebody deliberately singled out — `resolve_for`'s own words.
    """
    if template_pin_explicit:
        pin, pin_problem, per_account = run_pin, None, False
    else:
        pin, pin_problem, per_account = _pin_for_account(draft, run_pin=run_pin)
    billed = issue_invoice(
        draft,
        issued_at=issued_at,
        template_id=pin[0],
        template_version=pin[1],
        actor=actor,
        dispatch_not_before=dispatch_not_before,
    )
    return billed, per_account, pin_problem


def issue_run(
    bill_run: models.BillRun,
    *,
    issued_at: datetime,
    template_id: Any,
    template_version: int,
    invoice_ids: tuple[Any, ...] | None = None,
    actor: Any = None,
    require_release: bool = True,
    dispatch_not_before: datetime | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
    template_pin_explicit: bool = False,
    finish_run: bool = True,
    stop_after_same_fault: int | None = None,
) -> IssuedRun:
    """BR-BIL-023 — issue ALL the run's remaining drafts, or a named subset.

    `stop_after_same_fault` (DEF-BIL-8747, the Send's circuit breaker) STOPS
    the pass by raising `IssuePassStopped` once that many bills IN A ROW have
    failed with the same unexpected fault (`fault_signature`). A bill that
    issues resets the count, and so does a different fault; a named rule
    refusal (`BillingRuleError`) is a bill's own break and neither counts nor
    resets. None — the default, and every caller but `send_batches` — never
    stops, exactly as before: B11's one-break-per-bill is unchanged for them.

    `finish_run=False` (DEF-BIL-8726, the Send in batches of 500) issues the
    bills and SKIPS the run-wide close (`finish_issue_pass`): a batch is one
    five-hundredth of a Send, and the queue rows the RUN closes and opens are
    the run's, so `send_batches` calls the close ONCE after the last batch.
    `queue_rows_resolved` is then 0 on the batch's answer, because the batch
    closed nothing. Every other caller keeps the default and is unchanged.

    `invoice_ids=None` means all remaining drafts, which is also the retry
    story: a second call finds no remaining drafts and issues nothing (TC-6).
    A subset is exactly the bills named, and one that is already issued comes
    back in `already_issued` rather than vanishing from the count.

    THE GATE IS NOT OPTIONAL (BR-BIL-058, US-BIL-005 TC-14). Issue requires a
    `bill_run_releases` row for this run with all four confirmations recorded —
    compliance, email mandate, text mandate, autopay mandate — plus the row's
    own existence, which IS the fifth fact (who confirmed and when). *"Forged
    POST straight to issue with no release record"* is refused here, at the
    door, because after the door there is no un-issuing. `require_release` is
    an explicit escape for a caller that has its own authorisation record
    (there is none today); it is a named argument rather than a silent default
    so that switching it off is a decision somebody typed.

    ONE BILL AT A TIME (BR-BIL-055/047). A bill that breaks is recorded with
    its reason and the pass continues: 499 issued and one named break, never a
    rollback of the other 499. There is no batch rollback and there never will
    be — an issued bill cannot be un-issued.

    POSTING IS COUNTED, NOT RE-DONE, AND IT IS NOT RETRIED. Each bill emits its
    own balanced handoff inside its own transaction (BR-BIL-011, stage 7), so
    this pass only totals them — `posted` (entries written), `already_posted`
    (the hard-rule-6 replays a resumed release finds already in the books) and
    the DISTINCT problem codes with the number of bills each affected. A bill
    the books refuse does not issue, so it appears in `broken` and in neither
    counter: `posted + already_posted == len(issued)`, always.

    THE TEMPLATE IS RESOLVED PER ACCOUNT (BR-BIL-025, CR-052 W3 task 12).
    `template_id` / `template_version` are the RUN's pin and they are still
    required, because every bill must have one and a tenant fact is what answers
    when an account cannot. Inside the loop each draft resolves its OWN chain —
    **account override → category default → tenant fallback** — through
    `templates_service.resolve_for`, the one implementation of that order.
    `template_resolved_per_account` and `template_pinned_by_run` count which
    happened, and a bill whose chain REFUSES is one named break (BR-BIL-055),
    never a silent fall back to a layout nobody chose for that customer.

    ⚠ **`template_pin_explicit=True` TURNS THAT OFF FOR THE WHOLE PASS, AND IT
    IS THE ONE CASE WHERE IT SHOULD BE.** The issue endpoint accepts an explicit
    `template_id` + `template_version` in the body; a clerk who typed one has
    made a statement about THIS RUN, and resolving each account's own template
    over the top would discard it silently. Absent — which is every caller that
    does not type a pin — the run's pin is the tenant FALLBACK and per-account
    resolution is exactly what BR-BIL-025 asks for.

    DELIVERY IS COUNTED, NOT RE-DONE. Each bill queues its own rows inside its
    own transaction (BR-BIL-016), so this pass only totals them —
    `delivery_queued`, `delivery_already_queued`, and the DISTINCT problem
    codes with the number of bills each affected. A retry of this run finds no
    remaining drafts and therefore queues nothing; a retry that DOES reach a
    bill again finds its rows already there and reports them as
    `already_queued`, because the idempotency key is the database's
    (CLAUDE.md rule 6). Nothing here is dispatched: R2 queues, R4 sends.
    """
    tenant_id = _tenant_id()
    if require_release:
        # ⚠ **`released_at IS NULL` — B11, 2026-09-30.** `release.release_run`
        # refuses a row whose `released_at` is already stamped (*"re-releasing
        # this one is a double-click or a replayed job, and an issued bill
        # cannot be un-issued"*), and this gate did NOT ask the same question:
        # any row that had EVER been confirmed authorised issue for ever, so a
        # direct call to issue after the release completed walked through a
        # door the release itself had closed. A second authorised release is a
        # SECOND row with its own confirmations (`release.py`'s own words), and
        # that row is exactly what this now finds.
        authorised = models.BillRunRelease.objects.filter(
            tenant_id=tenant_id,
            bill_run=bill_run,
            compliance_confirmed=True,
            email_mandate_confirmed=True,
            sms_mandate_confirmed=True,
            autopay_mandate_confirmed=True,
            released_at__isnull=True,
        ).exists()
        if not authorised:
            raise BillingRuleError(
                f"run {bill_run.pk} has no authorised release, so nothing may be issued "
                "(BR-BIL-058, US-BIL-005 TC-14). The gate is five separately recorded "
                "facts — compliance, email mandate, text mandate, autopay mandate, and "
                "the confirmation itself — and it is the last moment at which nothing "
                "has been billed."
            )

    selection = models.Invoice.objects.filter(tenant_id=tenant_id, bill_run=bill_run)
    already_issued: list[str] = []
    broken: list[IssueBreak] = []
    if invoice_ids is not None:
        wanted = [str(invoice_id) for invoice_id in invoice_ids]
        selection = selection.filter(pk__in=wanted)
        found = {str(pk) for pk in selection.values_list("pk", flat=True)}
        already_issued = [
            str(pk)
            for pk in selection.exclude(status=models.INVOICE_DRAFT).values_list("pk", flat=True)
        ]
        # An id that is not in this run at all is REPORTED, not dropped. It is
        # another tenant's bill (RLS and the tenant filter make it invisible),
        # another run's, or a typo — and a caller who asked for 100 and is told
        # about 99 has no way to find the hundredth.
        broken.extend(
            IssueBreak(
                reason=ISSUE_NOT_IN_RUN,
                detail=(
                    f"bill {invoice_id} is not a draft of run {bill_run.pk} for this "
                    "tenant, so this run cannot issue it. Nothing was issued for it and "
                    "nothing was silently skipped."
                ),
                invoice_id=invoice_id,
            )
            for invoice_id in wanted
            if invoice_id not in found
        )
    drafts = list(selection.filter(status=models.INVOICE_DRAFT).order_by("invoice_no", "id"))

    issued: list[str] = []
    # BR-BIL-011's counters, gathered per bill exactly as BR-BIL-016's are. A
    # bill that could not POST did not issue either — it is in `broken` and in
    # neither counter — so `posted + already_posted == len(issued)` is a
    # property of every pass and a caller can assert it.
    posted_entries = 0
    replayed_entries = 0
    posting_problems: dict[str, dict[str, Any]] = {}
    # BR-BIL-016's counters, gathered per bill and reported once. A run of 480
    # bills that could not resolve a single recipient must say that ONCE with a
    # count — 480 identical problem dicts is a wall, not a report.
    queued_rows = 0
    already_queued_rows = 0
    delivery_problems: dict[str, dict[str, Any]] = {}
    # BR-PAY-010's counter starts as None rather than 0: "nobody could ask" and
    # "these customers had no credit" are different answers and the second is a
    # money claim. It becomes a Decimal the first time any bill gets an answer.
    credit_total: Decimal | None = None
    credit_bill_count = 0
    intents_created = 0
    intents_replayed = 0
    payment_problems: dict[str, dict[str, Any]] = {}
    # DEF-098 — how many meter reads this pass moved to BILLED, and how many
    # were already locked (a re-issue). Two counters for the reason every other
    # pair here is two: "1,122 reads locked this morning" and "1,122 reads were
    # already locked" are different mornings.
    reads_locked = 0
    reads_already_billed = 0
    read_problems: dict[str, dict[str, Any]] = {}
    snapshot_problems: dict[str, dict[str, Any]] = {}
    # ── CR-051 task 10 — NFR-4's gauge over the issue pass ──────────────────
    # `on_progress(done, total, invoice_no)` is called after EVERY bill, issued
    # or broken, so the denominator is the one the screen shows. It is OPTIONAL
    # and defaults to nothing: an inline caller answers before anyone could poll
    # it, and a gauge nobody reads is a write for nothing.
    #
    # ⚠ **A REPORTER THAT RAISES MUST NOT UN-ISSUE A BILL.** By the time it is
    # called the bill is already immutable (hard rule 4) and there is no
    # un-issuing; letting a broken gauge escape here would abandon the rest of
    # the pass over a progress bar. So it is logged and the pass continues —
    # BR-BIL-055's posture applied to a peripheral, not to a bill.
    issue_total = len(drafts)
    issue_done = 0

    def _report(invoice_no: Any) -> None:
        if on_progress is None:
            return
        try:
            on_progress(issue_done, issue_total, str(invoice_no or ""))
        except Exception:  # noqa: BLE001 — see the block above
            logger.warning(
                "issue progress reporting failed on run %s", getattr(bill_run, "pk", None)
            )

    # ── CR-052 W3 task 12 — BR-BIL-025's per-account counters ─────────────
    resolved_per_account = 0
    pinned_by_run = 0
    template_problems: dict[str, dict[str, Any]] = {}
    run_pin = (template_id, template_version)
    # ── DEF-BIL-8747 — the circuit breaker's count (see the docstring) ──────
    # The fault the last unexpected failures shared, and the bills that met it
    # in a row since the last bill that issued.
    streak_fault: str | None = None
    streak_bills: list[str] = []

    for draft in drafts:
        try:
            # ⚠ **ONE SAVEPOINT PER BILL, AROUND EVERYTHING THIS BILL DOES — B11,
            # 2026-09-30 (hard-won law 14).** `issue_invoice` already holds its
            # own `transaction.atomic()`; the pin resolution above it did not,
            # and a caller that runs this pass inside a transaction (a job, a
            # test, a future request) would have its WHOLE transaction aborted
            # on PostgreSQL by one bill's failed statement — every later bill
            # then raising `InFailedSqlTransaction` and the pass lost at COMMIT.
            # This block is the savepoint that makes the `except` below safe:
            # a failure rolls back to it and the next bill starts clean. It is
            # not tidiness and it must not be "simplified" away.
            with transaction.atomic():
                billed, per_account, pin_problem = _issue_one(
                    draft,
                    run_pin=run_pin,
                    template_pin_explicit=template_pin_explicit,
                    issued_at=issued_at,
                    actor=actor,
                    dispatch_not_before=dispatch_not_before,
                )
            if per_account:
                resolved_per_account += 1
            else:
                pinned_by_run += 1
            if pin_problem is not None:
                key = str(pin_problem.get("code"))
                seen = template_problems.get(key)
                if seen is None:
                    template_problems[key] = {**pin_problem, "bills": 1}
                else:
                    seen["bills"] += 1
        except BillingRuleError as problem:
            broken.append(
                IssueBreak(
                    reason=_reason_for(problem),
                    detail=str(problem),
                    invoice_id=str(draft.pk),
                    invoice_no=draft.invoice_no,
                    account_id=str(draft.account_id),
                )
            )
            issue_done += 1
            _report(draft.invoice_no)
            continue
        except Exception as problem:  # noqa: BLE001 — see below
            # ── B11 · A FAILURE THAT IS NOT A RULE STILL BREAKS ONE BILL ────
            # `frozen_bill.NotFrozen` is a `RuntimeError`, a render or a seam
            # can raise anything, and a database error is a `DatabaseError`.
            # Until 2026-09-30 any of them escaped this loop and ABANDONED THE
            # PASS mid-run — the bills before it issued, the bills after it
            # never tried, and no break naming the one that failed. BR-BIL-055
            # is the rule: one named break, the other 499 still go. The
            # savepoint above has already rolled this bill back, so the draft
            # is still a draft and nothing half-issued survives. It is LOGGED
            # with its traceback because, unlike a rule refusal, it is a fault
            # somebody has to go and look at.
            logger.exception(
                "issue of bill %s on run %s failed unexpectedly",
                draft.invoice_no,
                getattr(bill_run, "pk", None),
            )
            broken.append(
                IssueBreak(
                    reason=ISSUE_FAILED_UNEXPECTEDLY,
                    detail=(
                        f"bill {draft.invoice_no or draft.pk} could not be issued: "
                        f"{type(problem).__name__}: {problem}. It is still a draft and "
                        "nothing on it was issued; every other bill in the run went on."
                    ),
                    invoice_id=str(draft.pk),
                    invoice_no=draft.invoice_no,
                    account_id=str(draft.account_id),
                )
            )
            issue_done += 1
            _report(draft.invoice_no)
            # ── DEF-BIL-8747 · THE SAME FAULT ON BILL AFTER BILL IS THE SYSTEM'S
            # On `sbh_send40k` the code ran one migration ahead of its database
            # and every bill failed `column invoice_lines.pricing_trace does not
            # exist`: 22,640 breaks in five minutes, each telling a clerk one
            # bill was *not sent*, and the release completed. A fault met on
            # `stop_after_same_fault` bills IN A ROW is not those bills' — so
            # the pass STOPS here, once, and the streak's bills are left as
            # what they are: drafts with no break (the savepoint above rolled
            # each back, so raising out is safe on PostgreSQL — nothing in this
            # transaction is aborted). What came before the streak travels in
            # `partial` so its genuine breaks are still filed.
            if stop_after_same_fault is not None:
                fault = fault_signature(problem)
                if fault != streak_fault:
                    streak_fault, streak_bills = fault, []
                streak_bills.append(str(draft.pk))
                if len(streak_bills) >= stop_after_same_fault:
                    in_streak = set(streak_bills)
                    raise IssuePassStopped(
                        fault=fault,
                        bills=len(streak_bills),
                        detail=f"{type(problem).__name__}: {problem}",
                        partial=IssuedPassSoFar(
                            issued=tuple(issued),
                            broken=tuple(b for b in broken if b.invoice_id not in in_streak),
                        ),
                    ) from problem
            continue
        streak_fault, streak_bills = None, []
        issued.append(str(draft.pk))
        posting = getattr(billed, "posting", None)
        if posting is not None:
            # `created` is the hard-rule-6 fork: a NEW entry, or the replay that
            # found the first one and wrote nothing (US-LED-001 TC-6). Counted
            # apart because a resumed release must not report "already in the
            # books" as "posted this morning".
            if posting.created:
                posted_entries += 1
            else:
                replayed_entries += 1
            for entry in posting.problems:
                key = str(entry.get("code"))
                seen = posting_problems.get(key)
                if seen is None:
                    posting_problems[key] = {**entry, "bills": 1}
                else:
                    seen["bills"] += 1
        # BR-PAY-010 / BR-PAY-015, counted per bill and reported once — the
        # same discipline the posting and delivery counters take, for the same
        # reason: a run of 480 bills whose payments module is unmigrated must
        # say so ONCE with a count, not 480 times.
        credit = getattr(billed, "credit", None)
        if credit is not None:
            if credit.applied is not None:
                credit_total = (credit_total or Decimal("0")) + credit.applied
                if credit.applied > 0:
                    credit_bill_count += 1
            for entry in credit.problems:
                _count_problem(payment_problems, entry)
        autopay = getattr(billed, "autopay", None)
        if autopay is not None:
            if autopay.created:
                intents_created += 1
            elif autopay.intent_id is not None:
                intents_replayed += 1
            for entry in autopay.problems:
                _count_problem(payment_problems, entry)

        reads = getattr(billed, "reads", None)
        if reads is not None:
            reads_locked += reads.locked
            reads_already_billed += reads.already_billed
            for entry in reads.problems:
                _count_problem(read_problems, entry)

        # CR-052 W2 — the usage-history and bill-copy stamps, folded the same
        # way. `getattr` with a default because a bill issued through a path
        # that predates this attribute must not take the run down.
        for entry in getattr(billed, "snapshot_problems", ()) or ():
            _count_problem(snapshot_problems, entry)

        delivery = getattr(billed, "delivery", None)
        if delivery is None:  # pragma: no cover - defensive
            continue
        queued_rows += len(delivery.queued)
        already_queued_rows += len(delivery.already_queued)
        for entry in delivery.problems:
            key = f"{entry.get('code')}|{entry.get('channel') or ''}"
            seen = delivery_problems.get(key)
            if seen is None:
                delivery_problems[key] = {**entry, "bills": 1}
            else:
                seen["bills"] += 1
        issue_done += 1
        _report(draft.invoice_no)

    # US-BIL-006 TC-3 / BR-BIL-034 and DEF-BIL-8410 — the run-wide close, in
    # `finish_issue_pass` so a batched Send can run it ONCE after its last
    # batch (DEF-BIL-8726). Same code, same order, same idempotency.
    resolved_queue_rows = (
        finish_issue_pass(bill_run=bill_run, issued_at=issued_at, actor=actor) if finish_run else 0
    )

    return IssuedRun(
        bill_run_id=str(bill_run.pk),
        issued=tuple(issued),
        already_issued=tuple(already_issued),
        broken=tuple(broken),
        posted=posted_entries,
        already_posted=replayed_entries,
        posting_problems=tuple(posting_problems.values()),
        delivery_queued=queued_rows,
        delivery_already_queued=already_queued_rows,
        delivery_problems=tuple(delivery_problems.values()),
        credit_applied=credit_total,
        credit_bills=credit_bill_count,
        autopay_intents=intents_created,
        autopay_already_recorded=intents_replayed,
        payment_problems=tuple(payment_problems.values()),
        reads_locked=reads_locked,
        reads_already_billed=reads_already_billed,
        read_problems=tuple(read_problems.values()),
        snapshot_problems=tuple(snapshot_problems.values()),
        queue_rows_resolved=resolved_queue_rows,
        # CR-052 W3 task 12 — BR-BIL-025 per account.
        template_resolved_per_account=resolved_per_account,
        template_pinned_by_run=pinned_by_run,
        template_problems=tuple(template_problems.values()),
    )


def finish_issue_pass(*, bill_run: models.BillRun, issued_at: datetime, actor: Any = None) -> int:
    """The RUN-WIDE close of an issue pass: queue rows this run billed close,
    and the accounts its saved Check kept out enter the queue. Returns how many
    rows closed. Lifted out of `issue_run` unchanged (DEF-BIL-8726) so the Send
    in batches runs it once, after the last batch; both halves are idempotent,
    so a resumed Send that runs it again closes and opens nothing twice."""
    # US-BIL-006 TC-3 / BR-BIL-034 — **hold ≠ forget, and the door SHUTS here.**
    # An account leaves the Pending-billing queue when a bill exists for it over
    # the period it was held for, and this is the only moment at which that
    # becomes true. Doing it here rather than on the catch-up screen is what
    # makes it structural: a clerk who never opens the queue still sees the chip
    # decrement, and a resolution can never be recorded for a bill that did not
    # issue. `resolve_for_run` is idempotent (it only ever moves a NULL
    # `resolved_at` forward), so a re-issued run closes nothing twice.
    #
    # It reads INVOICES rather than this pass's `issued` list on purpose: a
    # resumed release whose bills issued in an earlier pass must still clear the
    # queue, and `already_issued` is exactly that case.
    resolved = pending.resolve_for_run(bill_run=bill_run, resolved_at=issued_at, actor=actor)
    # 🔒 DEF-BIL-8410 · BR-BIL-1054 — and every account the run's saved Check
    # kept out (blocked, still waiting on a decision, left out) ENTERS the
    # queue here, at Send, so a catch-up run can bill it. Idempotent per
    # (run, account); nothing is written for an account this run billed.
    pending.queue_not_in_run(bill_run=bill_run, actor=actor)
    # CR-169-BRC10 §2 row 9 — the run's Send is finished. Sent AFTER COMMIT,
    # never inside the money transaction, and keyed on the run so a resumed
    # Send that closes twice is one event. A count, never an amount.
    from config import product_analytics

    product_analytics.capture_after_commit(
        "bill_run_finalised",
        tenant_id=bill_run.tenant_id,
        actor_id=product_analytics.actor_id_of(actor),
        properties={"queue_rows_resolved": resolved},
        dedupe_key=str(bill_run.pk),
    )
    return resolved


def _count_problem(seen: dict[str, dict[str, Any]], entry: dict[str, Any]) -> None:
    """Fold one bill's problem into the run's DISTINCT set, with a bill count.

    The same shape the posting and delivery counters already use, extracted so
    the payments counters cannot drift from them: a run of 480 bills that hit
    one condition reports it ONCE with `bills: 480`, because 480 identical
    dicts is a wall rather than a report.
    """
    key = str(entry.get("code"))
    found = seen.get(key)
    if found is None:
        seen[key] = {**entry, "bills": 1}
    else:
        found["bills"] += 1


#: Phrase → reason code. The stages raise `BillingRuleError` with a sentence a
#: clerk can act on (that is the contract `exceptions.py` states); the break
#: list needs a stable key to GROUP on, and grouping on prose is grouping on
#: nothing. Mapped here rather than by giving every raise site a subclass,
#: because the sentences are the interface the screen shows and this table is
#: one place to look when a new refusal is added.
_REASON_PHRASES = (
    # BR-BIL-011's stage-7 refusals come FIRST of all. Two of them name a bill by
    # number and one of them contains the word "account", so every one would be
    # absorbed by a neighbouring phrase below and reported as a delivery or a
    # mapping problem — and "this bill did not reach the books" is not either of
    # those things.
    ("apps.ledger.posting publishes no", ISSUE_POSTING_UNAVAILABLE),
    ("designation, so this bill's posting handoff", ISSUE_POSTING_NO_AR),
    ("a NEGATIVE posting bucket", ISSUE_POSTING_NEGATIVE_BUCKET),
    ("does not foot", ISSUE_POSTING_UNBALANCED),
    ("cannot be placed in a posting bucket", ISSUE_POSTING_UNBALANCED),
    ("nothing to credit against its AR debit", ISSUE_POSTING_UNBALANCED),
    ("the books refused bill", ISSUE_POSTING_REFUSED),
    ("could not be keyed for posting", ISSUE_POSTING_REFUSED),
    # BR-BIL-016's refusals, next for the same reason the render's are: their
    # sentences name a bill by number and would otherwise be absorbed by a
    # neighbouring phrase and reported as a pin problem.
    ("cannot leave a delivery record", ISSUE_DELIVERY_UNQUEUEABLE),
    ("could not be queued for delivery", ISSUE_DELIVERY_UNQUEUEABLE),
    ("could not say what will be rendered", ISSUE_DELIVERY_UNQUEUEABLE),
    ("published interface is not an interface", ISSUE_DELIVERY_UNQUEUEABLE),
    # BR-BIL-033's refusals come FIRST. Several of them would otherwise be
    # absorbed by a neighbouring phrase below and reported as a payload or pin
    # problem, and "this bill's money is fine, its document is not" is a
    # different thing for a clerk to be told.
    ("there is nothing to render it FROM", ISSUE_RENDER_FAILED),
    ("carries payload version", ISSUE_RENDER_FAILED),
    ("is pinned to template", ISSUE_RENDER_FAILED),
    ("so its money cannot be printed", ISSUE_RENDER_FAILED),
    ("so the document cannot be rendered", ISSUE_RENDER_FAILED),
    ("cannot be issued again", ISSUE_NOT_A_DRAFT),
    ("has no lines", ISSUE_NO_LINES),
    ("carries no number", ISSUE_NO_NUMBER),
    ("no locked document instance", ISSUE_NO_PAYLOAD),
    ("no payload_version", ISSUE_NO_PAYLOAD),
    ("no template pin", ISSUE_NO_TEMPLATE_PIN),
    ("no bill date and due-days", ISSUE_NO_DUE_TERMS),
    ("due_days is", ISSUE_NO_DUE_TERMS),
    (f"{GL_REVENUE_READ} / {GL_DESIGNATION_READ}", ISSUE_GL_MAP_UNPUBLISHED),
    (f"{TAX_GL_READ} is not published", ISSUE_GL_MAP_UNPUBLISHED),
    (f"{CHARGE_GL_READ} is not published", ISSUE_GL_MAP_UNPUBLISHED),
    ("names no service", ISSUE_LINE_NAMES_NO_SERVICE),
    # BR-BIL-069's two tax breaks, and they are two ON PURPOSE — see the code
    # constants. Both come BEFORE the generic mapping phrases below, because a
    # tax break is fixed on S13 and a revenue break on the GL mapping page.
    ("names no tax, so the authority", ISSUE_TAX_LINE_UNMAPPABLE),
    ("has no liability account", ISSUE_TAX_AUTHORITY_UNMAPPED),
    ("is mapped to a ledger account that is not this tenant", ISSUE_TAX_AUTHORITY_UNMAPPED),
    ("names no charge code", ISSUE_FEE_LINE_UNMAPPABLE),
    # DEF-714's two fee breaks, two ON PURPOSE like the tax pair above: the
    # line ABOVE names no code and wants a developer, these name one and want a
    # clerk on S13. Both come before the generic mapping phrases below.
    ("has no GL account, so the line cannot be stamped", ISSUE_FEE_CHARGE_UNMAPPED),
    ("points at a ledger account that is not this tenant", ISSUE_FEE_CHARGE_UNMAPPED),
    ("has no revenue account configured", ISSUE_LINE_UNMAPPED),
    ("designation, so a minimum-bill adjustment", ISSUE_LINE_UNMAPPED),
    ("has no GL rule", ISSUE_LINE_UNMAPPED),
)


def _reason_for(problem: BillingRuleError) -> str:
    message = str(problem)
    for phrase, reason in _REASON_PHRASES:
        if phrase in message:
            return reason
    # A refusal nobody has coded yet must still be VISIBLE and groupable —
    # named as unclassified rather than silently folded into a neighbour.
    return "issue_refused_unclassified"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane — the PO's phase 5) ·
#         AMENDED 2026-08-25 by lane FEELINE (DEF-714 / DEF-201 — PO ruling
#         2026-08-25 option A, *"Make issue read the charge code"*: the `fee`
#         branch of `_gl_account_for` RESOLVES instead of refusing; one new read,
#         rating's `gl_account_id_for_charge`, plus the ledger's existing
#         `account_is_live`; one new break code
#         `charge_code_has_no_live_account`. Nothing else about issue changed and
#         no money figure moved — golden 33 PASS/0 FAIL, byte-identical) ·
#         AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane: the tax
#         branch of `_gl_account_for` RESOLVES instead of refusing; two new
#         reads — rating's `liability_gl_account_id_for_tax` and the ledger's
#         `account_is_live`; new break code `tax_authority_has_no_live_account`)
#         · AMENDED 2026-08-11 by Eng-Lead (stage-7 posting-handoff lane:
#         `issue_invoice` EMITS the BR-BIL-011 handoff through
#         `apps/billing/posting_seam.post_bill_issue` inside its transaction;
#         `issue_run` aggregates `posted` / `already_posted` /
#         `posting_problems`; five new break codes)
#         · AMENDED 2026-08-15 by Eng-Lead (US-BIL-008 lane — OQ-146's *"let the
#         run report it"*: `_authority_label` + rating's
#         `tax_authority_label_for_tax`, so the unmapped-authority break names
#         *Harris County* rather than the rate code `Tax HARRIS-CO`. No break
#         code, no refusal and no money path changed — only the SENTENCE; the
#         mutation that reinstates the old message is RED on
#         tests/test_us_bil_008_tax_lines.py tc10/tc10b)
# checklist: A✔ B✔ C✔ D✔(`POST /billing/runs/{id}/issue` → `api.run_issue`, apps/billing/api.py:1099, included by config/urls.py) E✔(S31's wizard: 07-frontend/src/features/billing/BillRunWizard.tsx calls `issueBillRun` at its release step) ⚠ CORRECTED 2026-08-16 by the billing-9 lane, and the correction is the point (DEF-157): this row deferred BOTH halves with the reason *"no billing endpoints yet"*, and was TRUE WHEN WRITTEN on 2026-08-11. The run endpoints landed 2026-08-15 and nothing compares a deferral string against the URLconf, so G23 went on counting US-BIL-008 (tax lines per authority) as unreachable on the strength of this line alone — a stale claim inflating a count, hard-won law 1. Both halves were re-verified by reading the route table and the caller, not by reading a sentence F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_005_issue.py 12 passed on live
#         Postgres, 11 + 1 vendor-skip on sqlite · pytest -m golden 12 passed /
#         1 xfailed · run_gates 14 PASS / 1 FAIL (G1, another lane's ledger
#         files) / 1 SKIP · THIRTEEN mutations proved RED plus a live-cluster
#         trigger drop — verbatim in 12-governance/09-human-review-ledger.md
# exceptions: (1) WHO CALLS THIS — CORRECTED 2026-08-11 (stage-7 lane). This
#         entry read "NOTHING CALLS THIS YET. Phase 5's orchestrator does not
#         exist", and that stopped being true when the release lane landed:
#         `apps/billing/release.release_run` calls `issue_run`. ⚠ **AND THE
#         PARENTHESIS THAT FOLLOWED — "INLINE … because there is no worker:
#         celery is a declared dependency with zero `tasks.py`" — IS ITSELF
#         CORRECTED 2026-08-31 (CR-051 task 4).** The worker landed on
#         2026-08-19 (CR-017) and billing became a caller of it: `run_jobs.
#         ISSUE_JOB` runs `release_run` — and therefore THIS function — in a
#         worker on billing's own `billing` queue whenever `POST .../issue`
#         carries `background: true`. Inline is still the DEFAULT and is still
#         a real path. So the BACKGROUND BATCH (BR-BIL-051) is no longer
#         missing either; what is missing is a measured threshold that would
#         let the product choose for the caller. Hard-won law 2 twice over,
#         applied to this file's own trailer.
#         (2) THE GL STAMP IS WIRED TO THE LEDGER'S REAL READS
#         (`revenue_account_id_for_service` · `gl_account_id_for_designation` ·
#         `account_is_live`, published 2026-08-11 under OQ-106's closure) AND TO
#         RATING'S (`liability_gl_account_id_for_tax`, BR-BIL-069) and resolves
#         real accounts in the provisioned fixture — 4100 usage / 4105 base for
#         Electric, and a 2200-series account per tax authority. The kind → read
#         decision lives here because the ledger's own trailer declined to guess
#         billing's line kinds. Nothing cites an OQ as a stub: OQ-106 and OQ-116
#         are CLOSED and what remains is data, not a question.
#         (3) REWRITTEN 2026-08-11 — this entry said "AN ORDINARY BILL STILL
#         CANNOT ISSUE" and that stopped being true when the PO closed OQ-116
#         and this lane implemented it (BR-BIL-069). **An ordinary bill issues**:
#         stage 6 now writes `service` on every usage/base line and `tax_id` on
#         every tax line, so per-service revenue is computable from
#         `invoice_lines` and a $8.30 tax posts as three lines to three
#         authorities' own 2200-series accounts. TWO REFUSALS REMAIN, both
#         honest gaps rather than blocked paths: a FEE line names no charge code
#         (BR-BIL-010 gives each code its own GL, `rating.charges.gl_account_id`;
#         the charge id travels on neither `rating_seam.RatedLine` nor
#         `BillRunDecision`, so there is nothing for stage 6 to write), and a tax
#         whose authority the tenant has not yet given an account — *"every
#         utility may not have every account"*, so nothing is force-seeded and
#         nothing here invents one. Neither is worked around by parsing a
#         description: that was option D of OQ-116 and the PO declined it.
#         (3b) WHETHER SETUP SHOULD REFUSE A TAX WITH NO ACCOUNT — rather than
#         letting the refusal land here at issue — is **OQ-146**, minted by this
#         lane and NOT decided by it. This module implements the issue-time half
#         because BR-BIL-010 already requires it ("issue fails atomically if any
#         line cannot resolve a GL"); it adds no setup-time refusal.
#         (3c) THE REMAINING GAPS ARE NAMED IN PROSE RATHER THAN RAISED AS THE
#         PRIME DIRECTIVE'S STUB. That stub form would crash the batch on the
#         first affected bill; a named BillingRuleError lets the run record one
#         break per bill and carry on (BR-BIL-055), which is what
#         `exceptions.py` says that class is for.
#         (4) THE TEMPLATE PIN IS SUPPLIED, NOT DERIVED — BR-BIL-025's
#         assignment has no table. Issue refuses without a pin rather than
#         issuing a bill whose template columns freeze empty forever.
#         (5) NOT DONE, with its rule: the payload tie-out (BR-BIL-032,
#         PROPOSED — stage 6's payload has no total to tie to). It rides
#         `ISSUE_UNAVAILABLE` on every result.
#         (5aa) BR-BIL-011's POSTING HANDOFF IS DONE — AMENDED 2026-08-11
#         (stage-7 lane). This line used to name it, beside BR-BIL-032, among
#         the things issue does not do, and that was true when it was written:
#         `apps/ledger/posting.py` was a nine-line `NotImplementedError`. It is
#         the built sole writer now, and `issue_invoice` emits the balanced
#         handoff through `apps/billing/posting_seam.post_bill_issue` INSIDE the
#         issue transaction — DR the tenant's `accounts_receivable` designation
#         for `invoices.total`, CR one bucket per distinct stamped
#         `gl_account_id` (US-BIL-005 §7: WE-1 = DR AR 247.87 against nine
#         buckets). A bill and its journal entry commit together or neither
#         does; a refusal from the books leaves a DRAFT. **Billing writes no
#         journal line** — the seam resolves `apps.ledger.posting.post` by name
#         and ledger/0004's sole-writer trigger is the fence. WHAT IS STILL
#         OWED: US-LED-002's premises/unit chain (nobody publishes the reads), a
#         tax bucket's `tax_authority_id` (rating publishes no
#         `tax_authority_id_for_tax`), and the fact that a bucket names the
#         INVOICE rather than one invoice line, because §7's bucket is a SUM.
#         All three ride the result rather than being assumed handled.
#         (5ab) A NEGATIVE BUCKET REFUSES, NAMING **OQ-152** — minted by this
#         lane and NOT decided by it. A discount is a negative charge rule
#         (BR-RAT-043, OQ-055 closed), §7 makes the buckets CREDITS, and
#         flipping the side to post the absolute value is a money rule nobody
#         has signed.
#         (5a) BR-BIL-016's QUEUE HALF IS DONE — AMENDED 2026-08-11
#         (delivery-queue lane). This line used to name "the delivery queue rows
#         (BR-BIL-016)" among the things issue does not do, and that was true
#         when it was written: `apps/notifications/services.py` was a two-line
#         docstring. It now publishes `queue_document`, and `issue_invoice`
#         calls it through `apps/billing/delivery_seam.py` INSIDE the issue
#         transaction, so a bill and its delivery rows commit together. NOTHING
#         IS SENT: there is no dispatcher and no provider adapter, email
#         ACTIVATION is R4 (B12 release table), and a row resting `queued` is
#         the finished state of a bill run today. Two absences remain and ride
#         the seam's result rather than being assumed handled — the delivery
#         ELECTION (`accounts.paperless`, PROPOSED-SCHEMA) cannot be read so
#         every bill gets exactly the BR-BIL-036 print floor, and the RECIPIENT
#         cannot be resolved at all so each row carries
#         `recipient_not_resolvable` instead of an address nobody looked up.
#         (5b) BR-BIL-033 IS DONE — CORRECTED 2026-08-11 (bill-document lane).
#         This line used to name the pre-issue render as "CONFIRMED and
#         unsatisfiable — there is no renderer", and that was true when it was
#         written. `apps/billing/documents.py` now renders, `issue_invoice`
#         calls it inside the transaction before the status moves, and a
#         failure records an `ISSUE_RENDER_FAILED` break for that bill and
#         leaves the batch alone. What is STILL not done is BR-BIL-036's half:
#         the document is proved renderable and then discarded, because there
#         is no document table and no blob store. (AMENDED 2026-08-11: that
#         sentence used to end "and no delivery queue" — there is one now, see
#         (5a); what the queue still cannot hold is the rendered ARTEFACT.)
#         (5c) THE Σ-vs-2dp CLAIM IN THE BR-BIL-032 ENTRY WAS WRONG AND IS
#         CORRECTED. It said Σ(6dp lines) against a 2dp header is not a safe
#         equality; the engine finalizes every line half-up to 2dp exactly once
#         (BR-RAT-003) and sets the total to the sum of those lines, so the
#         equality is exact — GT-10: 82.08 + 18.50 + 8.13 + 8.30 = 117.01. The
#         real obstacle is only that `bill_payload` carries no total to compare.
#         (6) `_reason_for` maps a refusal's SENTENCE to a code. The sentences
#         are the clerk-facing contract and the codes are the screen's grouping
#         key; a subclass per refusal would have put the code at forty raise
#         sites instead of one table.
# revised: 2026-08-27 (OQ-530 opening-balance lane) — **BR-BIL-160.** `_stamp_balance_
#         forward` asks `customers_seam.opening_position_for_account` by name and hands
#         it to `prior_position_for_account`; the block gains `opening_balance`,
#         `opening_settled` and `opening_buckets`, and `BALANCE_FORWARD_BASIS` moves to
#         `open_prior_bills_and_migrated_opening_at_issue` so an immutable bill still
#         says which definition wrote it. ❄️ GT-16's `A-12103` reads
#         **267.30 − 0.00 + 247.87 = 515.17** where it read a dash (DEF-980); ❄️ WE-1's
#         **292.87** is asserted unmoved. OQ-217 stays OPEN.

# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
