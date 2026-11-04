# ── Trace ──────────────────────────────────────────────
# Change:   CR-053 task 13 — *"Print bills"* (W4). PO ruling 2026-08-30,
#           verbatim: *"Im okay with this"* on the PDF-set-plus-manifest
#           recommendation.   Screens: the Print bills screen (no A1 id — see
#           07-frontend/src/routing/screenIds.ts, the same posture
#           `/billing/pending` takes)
#           ⚠ AMENDED 2026-09-01 — CR-053 task 14's MECHANISM: the manifest is
#           written through apps/billing/print_formats.py's named-format
#           registry. OQ-1167 stays OPEN; only the mechanism is built.
#           ⚠ AMENDED 2026-09-01 — CR-051 task 30: the two per-bill broad
#           handlers re-raise a Celery soft time limit instead of holding it as
#           one broken bill (core.jobs.reraise_if_time_limit).
# Rules:    BR-NOT-029 (the print hand-over IS a PDF set plus a manifest; the
#           fourteen manifest columns; (a) discrete address columns, never
#           assembled or split; (b) a bill missing city/state/postal code is
#           REPORTED and held out of the file; (c) no CASS / NCOA / barcode
#           claim; (d) a vendor's mover result is not a source we write from) ·
#           BR-CUS-674 (an address changes when the ACCOUNT HOLDER says so and
#           by no other route — this module only READS) · BR-BIL-030 (the bill
#           is frozen at issue) · BR-BIL-026 (the pinned template version
#           renders the document, for ever) · BR-NOT-027 (the ORIGINAL bytes
#           are the bill; a rebuild is labelled) · BR-BIL-036 (print is the
#           floor) · BR-NOT-013 (delivery is still out of this release — a
#           manifest is rendered output handed over WITH the documents, not a
#           dispatch) · B14 rule 31 (no database id is the visible value of a
#           field) · BR-TEN-043 / G6 (event time is an ARGUMENT; no clock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money DISPLAYS at 2dp)
# Defects:  DEF-2703 (the service-request mailing address is one free-text
#           field) · DEF-2847 (`customers.addresses` has no line2 and no
#           country column) · DEF-2734 (a download built lazily comes back
#           empty — see WHY NOTHING HERE STREAMS)
# Tests:    06-backend/tests/test_cr053_print_set.py ·
#           06-backend/tests/test_cr053_task14_print_formats.py
# Impacts:  apps/billing/print_formats.py (the named formats) ·
#           apps/billing/print_api.py (the two routes) · apps/billing/apps.py
#           (registers this job body and its queue) · apps/billing/
#           customers_seam.print_address_for_account (the address read) ·
#           apps/customers/selectors.print_address_for_account (the owner —
#           the mailing row, else the service address, DEF-BIL-6373) ·
#           apps/tenancy/exports.py (the artifact directory, the retention
#           sweep and the `/api/exports/{job_id}/file` download this reuses)
# ───────────────────────────────────────────────────────
"""CR-053 task 13 — one cycle's bills as a print vendor receives them.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module carries an IDEMPOTENCY KEY
(`scope_key`, so a double-clicked *Build the print set* is one job and not two
passes over ten thousand bills), and an idempotency key is a CLAUDE.md 🔒 path.
AI-authored 2026-08-31 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in 12-governance/09-human-review-ledger.md.

⚠ **THIS FILE DELIBERATELY DID NOT ADD ITSELF TO
`10-scripts/gates/human_owned.txt`.** That list's own header makes changing the
guarded set a PROCESS EVENT — *"the guarded set must not drift with whoever is
coding"* — and `run_jobs.py`, `customers_seam.py`, `payments_seam.py`,
`posting_seam.py` and `pending.py` all took the same posture from the same
position. The glob is REQUESTED in the review-ledger row.

WHAT A PRINT VENDOR ACTUALLY RECEIVES, AND WHY IT IS THIS PAIR
════════════════════════════════════════════════════════════════════════════
One ZIP, and everything in it is paperwork a small mail house accepts with no
vendor negotiation:

    bills/BL-2608-000094.pdf      one print-ready page set per bill
    manifest.csv                  ONE ROW PER BILL, the fourteen ruled columns
    held-back.csv                 every bill this set could NOT hand over, and
                                  why, in a sentence a clerk can act on
    README.txt                    what the set is, what we did NOT do to it

`BR-NOT-029` names the fourteen manifest columns and they are `MANIFEST_HEADER`
below, in the ruled order, and **there is no fifteenth**. A manifest is a
vendor-facing file specification: an extra column is a spec change, so
everything a HUMAN wants to know about the run — how many pages came from the
kept original, how many were rebuilt — is in `README.txt` where it belongs and
not smuggled into the vendor's rows.

THE ADDRESS IS THE THING THE RULES ARE ABOUT, AND IT IS READ-ONLY
════════════════════════════════════════════════════════════════════════════
`BR-NOT-029` clause (a): *"Every manifest address is written from DISCRETE
columns, never assembled from or split out of a single field — splitting an
address is guessing, and a guessed address is mail delivered to the wrong
house."* So the nine address fields come from discrete columns through
`customers_seam.print_address_for_account`, and **nothing in this module
parses, joins or composes an address string.**

⚠ **WHICH ADDRESS: THE MAILING ROW, ELSE THE SERVICE ADDRESS — THE SAME ANSWER
THE DELIVERY QUEUE GIVES (`DEF-BIL-6373`, 2026-09-24).** Until then this module
read the mailing row alone and held every bill whose account had none, while the
queue — since `DEF-PAY-6342` part 1 — addressed the same bill to the premises.
B2 §2 says an absent mailing row MEANS *same as service*, and the PO's ruling of
2026-09-23 (*"ensure you update correct address - mailing or service"*) decided
it; customers answers both from one resolver, so the two cannot drift apart
again. A service address is the premises' four columns plus the unit's LABEL as
line 2 (hard rule 8) — still discrete, still never split.

Clause (b): a bill whose postal address lacks **city, state or postal code**
is REPORTED and held out of the file. That is not this build failing — it is the
rule working. A mailing row with a street and a hole in it is held rather than
swapped for the premises (the customer gave that address, and a mail house needs
all of it); an account with no mailing row goes to its service address and is
held only when the property's own address has the hole. `held-back.csv` names
each one, says which parts are missing, and says WHICH record to fix.

Clause (d) / `BR-CUS-674` (PO 2026-08-31, verbatim *"we cannot make chnges until
account confirm it"*): the hand-over runs ONE DIRECTION. There is no write of
any address column in this module, no queue that proposes one, and no function
that could carry a vendor's answer back. `G60` enforces the absence.

Clause (c): **nothing here says CASS, NCOA or barcode.** The mailer performs all
three and we perform none, and a field claiming otherwise is hard-won law 1 in
its purest form. `README.txt` states the absence in words rather than leaving a
vendor to assume.

A REPRINT NEXT YEAR IS THE SAME DOCUMENT — THE PIN DECIDES, NOT TODAY
════════════════════════════════════════════════════════════════════════════
Two sources, in this order, and the order is the whole of `BR-NOT-027`:

  1. **The bytes kept at issue.** `frozen_bill.reproduce` answers whether an
     original exists; `document_store.fetch` returns it and **re-hashes it on
     the way out**. Those bytes ARE the bill. A kept copy that will not verify
     is HELD and named — never quietly downgraded to a rebuild, because *"no
     copy was kept"* and *"a copy was kept and its bytes are now wrong"* are
     different facts with different remedies (`documents_api._refuse_unreadable`
     records the same judgement).
  2. **A re-render from the bill's OWN PIN**, for every bill issued before the
     document store existed. `documents.render_invoice(invoice)` is called with
     NO template argument, so `documents._pinned` takes `invoices.template_id`
     and `invoices.template_version` off the row — `BR-BIL-026`: *"a reprint
     renders the pinned version forever"*. There is no render-on-latest option
     and this module does not invent one; passing a version would in fact be
     REFUSED by `_pinned` if it disagreed with the pin.

Either way the figures are the frozen ones (`BR-BIL-030`) and no clock, no live
join and no current template reaches the page.

THE PAGE COUNT IS COUNTED, NEVER ESTIMATED
════════════════════════════════════════════════════════════════════════════
It is a manifest column, so it has to be known before the row is written, which
means the PDF has to EXIST before the row is written — that is why this module
produces the page and the row in one pass per bill rather than listing the bills
and rendering them afterwards. A re-render carries `pdf_page_count` from the
renderer itself. A kept original is COUNTED OUT OF ITS OWN BYTES
(`page_count_of`), because re-rendering it to find out how long it is would be
asking today's layout a question about a document it did not draw. A page count
that cannot be read is a HELD bill, not a guess: a mail house quotes on pages.

WHY NOTHING HERE STREAMS, AND WHY THAT IS THE STRONGER FIX (DEF-2734)
════════════════════════════════════════════════════════════════════════════
On 2026-08-30 two CSV downloads streamed a lazy generator, the tenant context
was cleared the moment the view returned, and the file arrived as a header with
no rows — *the download succeeded and nothing errored*.
`core.tenancy.stream_within_tenant_context` exists for that shape and `G58`
guards its two call sites.

**This module has no such call site because it has no lazy body at all.** The
archive is built in the job's own scratch folder by a job body that runs inside
its own tenant context (`core.jobs.run_job` enters it) and uploaded to S3 at
`t/<web name>/export/…` (PO 2026-10-02, `DEF-MET-4954`, `DEF-BIL-9148`); the
download is the platform's `GET /api/exports/{job_id}/file`, which hands over a
signed link to that FINISHED FILE and evaluates no lazy body. There is nothing left to evaluate after
the response starts, so the defect's mechanism is absent rather than guarded
against — which is why `G58`'s call-site list is unchanged and this paragraph
exists instead of a third entry on it.

WHAT IT COSTS, MEASURED, AND WHAT HAPPENS AT TEN THOUSAND
════════════════════════════════════════════════════════════════════════════
Measured on real PostgreSQL 16 with row-level security enforced, over the seeded
utility's 93 issued bills (`10-scripts/cr053_print_set_benchmark.py`,
2026-08-31): **0.012 s and 6.01 database statements a bill**, and about 1.3 KiB
of archive. So the answer to *"what happens at ten thousand?"* is **2.0 minutes,
60,108 statements and a 12.8 MiB file** — and at the 25,000 ceiling, about five
minutes and 32 MiB. Those are the numbers, not an impression of them.

The consequences, stated rather than discovered in production:

  * **It goes on the billing queue** (`run_jobs.BILLING_QUEUE`, PO ruling
    2026-08-31: *"billing will need its own named workers"*), because a print
    set over a whole cycle is exactly the shape of work that queue was named
    for. `background: true` enqueues; with nothing to run the job the caller
    gets the INLINE answer and is told so, never a promise queued into a void
    (`DEF-2487`, hard-won law 3) — the same fallback `api.run_findings` takes.
  * **Memory is flat.** One PDF is held at a time; the two CSVs are written to
    a temporary directory row by row and added to the archive at the end. A
    10,000-bill set costs the same resident memory as a one-bill set.
  * **A ceiling refuses at the door**, before a single page is drawn
    (`refuse_if_oversized`), because a limit discovered half way through is not
    a limit — it is a crash with a half-written archive behind it.

WHAT THIS MODULE IS NOT
════════════════════════════════════════════════════════════════════════════
⚠ **AMENDED 2026-09-01 — THE MANIFEST NOW GOES THROUGH `CR-053` TASK 14's
NAMED FORMAT, AND `OQ-1167` IS STILL OPEN.** This section used to read *"it is
not task 14, the machine-readable vendor extract"*, and half of that is still
true. What is built is the MECHANISM the task asks for — *"the extract behind a
named format parameter"* — in `apps/billing/print_formats.py`: the manifest is
written by a registered `PrintFormat`, an unregistered name is REFUSED with the
list of names that exist, and a vendor's shape arrives as a registration rather
than a change to this file. **What is NOT built and may not be guessed** is the
vendor's answer itself: which format, which fields in which order with which
address form, and how a period's bills are delimited (`OQ-1167` (a), (b), (c)).
One format is registered and it is not an invention — it is `BR-NOT-029`'s own
fourteen columns, one row per bill, as the CSV this product already hands over.

It is **not** a delivery adapter. `BR-NOT-013` keeps delivery out of this
release and `BR-NOT-029` says so in its own last clause: a manifest is part of
the RENDERED OUTPUT, the paperwork handed over with the documents. Nothing here
sends anything anywhere.

It is **not** `apps/billing/exports.py` — the bills-list CSV whose absence keeps
`CR-053` task 10's download glyph disabled. That is a list export through the
`POST /exports` registry; this is a print hand-over. They are different files
for different readers and merging them would give a bookkeeper a zip of PDFs.
"""

from __future__ import annotations

import csv
import logging
import re
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator

from django.db.models import Q

from apps.billing import (
    customers_seam,
    documents,
    frozen_bill,
    models,
    print_formats,
    run_jobs,
    selectors,
)
from apps.billing.exceptions import BillingRuleError
from apps.tenancy import document_storage, document_store, exports as export_kernel
from core import jobs as core_jobs
from core.pagination import ListParams

logger = logging.getLogger("smartbillhub.billing")

# ── the job kind ────────────────────────────────────────────────────────────
#: The `<module>.<subject>.<verb>` grammar `billing.run.calculate` and
#: `metering.import.transform` already use. Registered from
#: `BillingConfig.ready` beside the three run verbs — a kind with no handler is
#: a job that fails at the worker with *"no handler registered"*.
PRINT_SET_JOB = "billing.bills.print_set"

# ── what is inside the archive ──────────────────────────────────────────────
#: `BR-NOT-029`, verbatim: *"account number · bill number · customer name ·
#: address line 1 · address line 2 · city · state · postal code · country ·
#: page count · bill date · due date · amount due · the PDF filename."*
#:
#: ⚠ **FOURTEEN, IN THIS ORDER, AND NO FIFTEENTH.** A manifest is a file
#: specification a vendor reads; a column we found useful is a change to their
#: spec. Everything else this run knows goes in `README.txt`.
#:
#: ⚠ **THE TWO IDENTIFIER COLUMNS ARE HUMAN SERIES AND NOT DATABASE IDS**
#: (B14 rule 31, PO 2026-08-30: *"no Databse ID on screen - that is a rule"*).
#: `account_no` and `bill_no` are `BR-CUS-026`/`BR-BIL-022` series; a bill with
#: no number is HELD rather than identified by its uuid, and `pdf_filename` is
#: built from the bill number for exactly the same reason.
MANIFEST_HEADER: tuple[str, ...] = (
    "account_no",
    "bill_no",
    "customer_name",
    "address_line_1",
    "address_line_2",
    "city",
    "state",
    "postal_code",
    "country",
    "page_count",
    "bill_date",
    "due_date",
    "amount_due",
    "pdf_filename",
)

#: `BR-NOT-029` clause (b) — *"REPORTED and held out of the file"*. REPORTED is
#: this file, and it is inside the archive rather than in a log because the
#: person who has to act on it is the clerk holding the zip.
HELD_HEADER: tuple[str, ...] = ("account_no", "bill_no", "reason_code", "reason")

#: The default manifest file name. ⚠ **IT IS THE DEFAULT FORMAT'S NAME AND NOT
#: A CONSTANT ANY MORE (CR-053 task 14).** The file inside the archive is named
#: by whichever `print_formats.PrintFormat` was asked for — a vendor's loader
#: that globs `*.TXT` does not find `manifest.csv`, so the filename is part of
#: their specification exactly as the columns are. This name is what the
#: registry's one registered format writes, so an archive nobody asked a
#: question of is byte-for-byte what task 13 shipped.
MANIFEST_NAME = print_formats.MANIFEST_CSV.filename
HELD_NAME = "held-back.csv"
README_NAME = "README.txt"
#: PDFs live in their own folder so a vendor's loader can glob `bills/*.pdf`
#: without having to exclude the two CSVs by name.
PDF_DIR = "bills"

#: Only a bill that HAS a document may be handed to a printer.
#:
#: **`draft` is excluded because it cannot render at all** — the template pin is
#: written at issue (`BR-BIL-026`), so `documents._pinned` refuses a draft; and
#: it should be excluded anyway, since a draft is not a bill anybody has been
#: sent. **`void` is excluded because posting a voided bill is the one outcome
#: nobody can undo** — hard rule 4 makes the row immutable, but nothing makes an
#: envelope come back. **`paid` is INCLUDED**: a paid bill is still an issued
#: document, and a reprint of last quarter is the case `BR-CUS-040` exists for.
PRINTABLE_STATUSES: tuple[str, ...] = (models.INVOICE_ISSUED, models.INVOICE_PAID)

#: The filename is the bill number and nothing else, so a vendor's operator
#: matching a page to a manifest row does it by eye. Anything outside this set
#: is refused rather than substituted — a bill number that needs escaping is a
#: number nobody can quote down a phone line, and silently rewriting it would
#: put a different string in the archive from the one in the `bill_no` column.
SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")

# ── the measured cost (CR-053's own performance clause, PO 2026-08-31) ───────
#: WHAT ONE BILL COSTS, MEASURED — `10-scripts/cr053_print_set_benchmark.py`,
#: real PostgreSQL 16 with row-level security enforced, on the seeded sample
#: utility's **93 issued bills**, 2026-08-31. Three runs: **0.0118 · 0.0071 ·
#: 0.0080** seconds a bill.
#:
#: ⚠ **THE SLOWEST OF THE THREE IS THE ONE PUBLISHED, AND THAT IS DELIBERATE.**
#: The two fast runs had a warm cache; a print set is a rare act, so the run a
#: clerk actually waits through is the cold one. An estimate that is optimistic
#: is worse than no estimate, because the screen says *"about N seconds"* out
#: loud and a person plans around it.
#:
#: ⚠ **IT IS A MEASUREMENT AND NOT A BUDGET.** Nothing enforces it, nothing
#: fails when a set is slower, and no rule depends on it. It exists so the
#: screen and the oversize refusal can say how long a set would take in MINUTES,
#: which is the only form of that number a clerk can act on. Re-run the
#: benchmark when the renderer changes; do not reason it forwards.
#:
#: ⚠ **MEASURED WITH RLS ON.** `DEF-2717` is why that sentence is here: the bill
#: run's first published per-account figure was taken with row-level security
#: BYPASSED and was 25% optimistic. The suite's own settings hardcode in-memory
#: SQLite, so a figure taken there describes a database this product never runs
#: on (CLAUDE.md law 14).
#:
#: **What it projects to**, and this is the answer to *"what happens at ten
#: thousand?"*: 1,000 bills ≈ **0.2 min**, 10,000 ≈ **2.0 min** and **12.8 MiB**
#: of archive. Published in 12-governance/02-decision-log.md with the run.
MEASURED_SECONDS_PER_BILL = 0.012

#: Database statements per bill — **6.01**, same three runs, identical every
#: time. Stated because `CR-053`'s own performance clause asks for exactly this:
#: *"at 10,000 accounts one extra query per account is ten thousand more
#: statements"*. At 10,000 bills that is **60,108 statements**.
#:
#: For scale: the bill RUN's published figure is ~72 statements an account, so a
#: print set costs about a twelfth of what producing the bills cost — which is
#: the shape you would expect, because this pass writes nothing and re-prices
#: nothing. The six are the invoice page, the account (joined by
#: `select_related`, so it is not one of them), the account-exists check and the
#: address read in the seam, the primary contact for the customer name, and the
#: document-store lookup for a kept original.
MEASURED_STATEMENTS_PER_BILL = 6

#: HOW MANY PAGES ONE BILL IS — **2**, measured, not guessed.
#:
#: `10-scripts/` has no benchmark for this one because the measurement is the
#: product's own renderer: every one of the demo utility's **79 printable bills
#: was counted through `_page_for` on 2026-09-15** — the identical call the
#: archive makes — and all 79 came back **2 pages**, at 0.0047 s a bill.
#:
#: ⚠ **THE BLUEPRINT DRAWS `6` AND 6 IS AN ILLUSTRATION** (B14 rule 37 — a
#: figure drawn in a wireframe is never a fact to build to). Screen 28's PAGES
#: tile reads *"~2,424 · 6 a bill, measured"* on a drawing of 404 bills; the
#: number this product would actually print is **2 a bill**, and the tile is
#: built from the measurement rather than from the drawing.
#:
#: ⚠ **IT IS AN ESTIMATE AND THE SCREEN SAYS SO** (`~`). A bill's real page
#: count is only knowable by DRAWING it, and nothing is drawn before a clerk
#: presses the button: no column anywhere stores a page count, so a
#: before-the-fact figure is this constant × the bills that will print. The
#: archive's README carries the TRUE total afterwards (`PrintSetResult
#: .page_total`), which is the number a print shop is invoiced against.
#:
#: Re-measure when the bill layout changes — a template that adds a page moves
#: every quote a print shop gives. Do not reason it forwards.
MEASURED_PAGES_PER_BILL = 2

#: THE LARGEST PRINT SET THIS DEPLOYMENT ACCEPTS.
#:
#: **Where 25,000 comes from:** it is `run_jobs.MAX_ACCOUNTS_PER_RUN_DEFAULT`,
#: deliberately the same number and for the same stated reason — `CLAUDE.md`'s
#: first line puts this product's market at utilities **under 3,000
#: connections**, so 25,000 is eight times the largest utility it is for. A
#: print set cannot exceed the run that produced the bills, so a DIFFERENT
#: ceiling here could only ever be the tighter of two and would refuse a set for
#: bills the same deployment was happy to create. At the measured rate 25,000
#: bills is about **5 minutes** of worker time and about **32 MiB** of archive.
#:
#: **IT IS A DEPLOYMENT SETTING AND THE UNSAFE OPTION IS THE ONE YOU TYPE**
#: (hard-won law 3): an operator raises `BILLING_MAX_BILLS_PER_PRINT_SET`
#: deliberately, and `0` switches the ceiling off and has to be typed too.
#:
#: ⚠ **AND FOR A WHILE THAT SENTENCE WAS NOT TRUE — `DEF-2806`, fixed in
#: v2.119.0.** No settings module declared `BILLING_MAX_BILLS_PER_PRINT_SET`,
#: so Django never exposed it and the `getattr` below always fell through to
#: this default: the environment variable was read by nobody, silently. The
#: name is declared in `config/settings/base.py` through `env.int` now, and
#: `tests/test_cr051_task30_time_limit.py` holds the settings default equal to
#: this literal so the pair cannot drift.
MAX_BILLS_PER_PRINT_SET_DEFAULT = 25_000

# ── held reasons ────────────────────────────────────────────────────────────
#: Stable codes for the machine, beside a sentence for the person. The code is
#: what a later report groups on; the sentence is `BR-SHL-020`'s half — plain
#: language, naming what to do — and it is the only one a clerk reads.
HELD_ADDRESS_INCOMPLETE = "address_incomplete"
HELD_ADDRESS_UNREADABLE = "address_unreadable"
HELD_NO_BILL_NUMBER = "no_bill_number"
HELD_UNSAFE_BILL_NUMBER = "unsafe_bill_number"
HELD_DUPLICATE_FILENAME = "duplicate_filename"
HELD_DOCUMENT_REFUSED = "document_refused"
HELD_ORIGINAL_UNREADABLE = "kept_original_unreadable"
HELD_PAGE_COUNT_UNKNOWN = "page_count_unknown"


@dataclass(frozen=True)
class HeldBill:
    """One bill this set could not hand over, and why — `BR-NOT-029` (b).

    It carries `account_no` and `bill_no` and NEVER an id (B14 rule 31): the
    person reading this file is going to go and look the account up, and a uuid
    is not something they can type into the search box. A bill with no number at
    all is the one case where `bill_no` is blank, and its reason says so.
    """

    account_no: str | None
    bill_no: str | None
    reason_code: str
    reason: str

    def cells(self) -> list[str]:
        return [self.account_no or "", self.bill_no or "", self.reason_code, self.reason]


@dataclass
class PrintSetResult:
    """What one print set produced. Every number here was COUNTED, not assumed.

    `pdf_count` and `manifest_rows` are kept as two fields on purpose even
    though the code makes them equal: the promise `BR-NOT-029` makes is *one
    PDF per bill plus one manifest row per bill*, and a result object that
    stored the figure once could not be asked whether the promise held. The
    caller asserts they match; a set where they did not would be a set a vendor
    prints wrong.
    """

    #: Bills the selection contained, before any were held.
    considered: int = 0
    pdf_count: int = 0
    manifest_rows: int = 0
    page_total: int = 0
    #: How many pages came from the bytes KEPT at issue vs a re-render from the
    #: bill's own pin. Both are lawful (`BR-NOT-027`); the split is in the
    #: README so a reader knows which they are holding.
    from_original: int = 0
    re_rendered: int = 0
    held: list[HeldBill] = field(default_factory=list)
    archive_name: str = ""
    #: The file the manifest rows were written to, named by the FORMAT that
    #: wrote them (CR-053 task 14). The README prints it, so a reader of the
    #: archive is told which file the row count refers to rather than being
    #: left to infer it from a listing.
    manifest_name: str = MANIFEST_NAME

    @property
    def held_count(self) -> int:
        return len(self.held)


# ── the page count, read out of the page ────────────────────────────────────
#: The container `documents._pdf_file` writes declares its own length:
#: `<< /Type /Pages /Kids [...] /Count 2 >>`. That is the authoritative answer
#: for a kept original, because it is what a PDF reader itself uses.
_PAGES_COUNT_RE = re.compile(rb"/Type\s*/Pages\b[^>]*?/Count\s+(\d+)")
#: The fallback, for a page tree written in the other field order. Counting
#: `/Type /Page` objects is exact for a flat one-level tree, which is every
#: document this product writes; `\W` keeps it from matching `/Type /Pages`.
_PAGE_OBJECT_RE = re.compile(rb"/Type\s*/Page(?=\W)")


def page_count_of(pdf: bytes) -> int | None:
    """How many pages this PDF has, or **None** when the bytes do not say.

    ⚠ **None IS A REFUSAL AND NOT A ZERO.** A mail house quotes on pages and
    stuffs envelopes by them, so a wrong count is a wrong invoice and a jammed
    inserter. The caller HOLDS a bill whose count cannot be read rather than
    writing a plausible number into a vendor's file — which is the same posture
    `BR-NOT-029` clause (b) takes about a missing postcode.

    Read out of the DOCUMENT rather than re-derived: a kept original was drawn
    by whatever layout was registered on the day it issued, and asking today's
    renderer how long it is would be asking the wrong question of the wrong
    code. `documents.RenderedDocument.pdf_page_count` is the answer for a page
    this module has just drawn itself, and the two are asserted equal for one
    bill in `tests/test_cr053_print_set.py`.
    """
    if not pdf:
        return None
    declared = _PAGES_COUNT_RE.search(pdf)
    if declared is not None:
        count = int(declared.group(1))
        return count if count > 0 else None
    objects = len(_PAGE_OBJECT_RE.findall(pdf))
    return objects if objects > 0 else None


def pdf_filename_for(invoice_no: str | None) -> str | None:
    """`BL-2608-000094.pdf`, or **None** when the bill has no usable number.

    B14 rule 31 is the whole of this function: a uuid may never be the visible
    value of a field, and a filename on a page a vendor's operator holds is
    about as visible as a field gets. So there is no `str(invoice.pk)` fallback
    — a bill with no number is held and named in `held-back.csv`, where the
    clerk can go and fix it.
    """
    if not invoice_no:
        return None
    if not SAFE_FILENAME_RE.match(invoice_no):
        return None
    return f"{invoice_no}.pdf"


def max_bills_per_print_set() -> int:
    """The ceiling in force, or 0 when an operator has switched it off."""
    from django.conf import settings

    return int(
        getattr(settings, "BILLING_MAX_BILLS_PER_PRINT_SET", MAX_BILLS_PER_PRINT_SET_DEFAULT)
    )


def refuse_if_oversized(count: int) -> int:
    """Refuse a set bigger than this deployment accepts. Returns the count.

    ⚠ **AT THE DOOR, BEFORE A SINGLE PAGE IS DRAWN.** The count is one
    `COUNT(*)` over a selection the list endpoint already knows how to build; a
    ceiling discovered half way through is a crash with a half-written archive
    behind it and nobody to tell, because by then the clerk has gone.

    It names the count, the ceiling and the time the set would have taken, and
    it names the two ways a print set is legitimately made smaller — both of
    which already exist and neither of which needs a rule change: print ONE
    RUN's bills rather than a whole cycle's history, or narrow the issued-date
    window the list itself already filters on.
    """
    ceiling = max_bills_per_print_set()
    if ceiling and count > ceiling:
        minutes = max(1, round(count * MEASURED_SECONDS_PER_BILL / 60))
        raise BillingRuleError(
            f"this print set covers {count:,} bills and this system accepts "
            f"{ceiling:,} at a time, so nothing has been produced. It would have taken "
            f"about {minutes} minute(s). Print one bill run rather than a whole cycle's "
            "history, or narrow the range of issue dates, and build it again."
        )
    return count


# ── the selection ───────────────────────────────────────────────────────────
def print_set_selection(filters: dict[str, str] | None = None, q: str = "") -> Any:
    """The bills this set covers — the S30 list's OWN filter vocabulary.

    Built on `selectors.invoice_list_queryset` rather than on a queryset of its
    own so a print set can never cover a population the bills list cannot show.
    `bill_run_id` and `cycle_id` are both `selectors.INVOICE_FILTERS` members
    already, which is what makes *"every bill in a cycle"* — the PO's own
    description of a print run — a filter and not a new concept.

    ⚠ **THE STATUS FILTER IS OVERRIDDEN, NOT MERGED.** A caller asking for
    `status=draft` is asking for bills that have no document at all; honouring
    it would produce an empty archive that looks like a broken renderer. The
    selection is `PRINTABLE_STATUSES` always, and the screen says so.

    Ordered by bill number so the archive, the manifest and the vendor's stack
    are in ONE stable order — two runs of the same set produce the same
    sequence, which is what makes a re-run diffable.

    ⚠ **`q` IS THE SCREEN'S SEARCH BOX AND IT NARROWS WHAT IS LISTED, NEVER WHAT
    IS PRODUCED** (`DEF-BIL-5354`). Screen 28's table exists so a clerk can
    answer *"is this customer's bill in the set?"* before generating, and the
    blueprint says why: *"the question is usually about one customer's bill."*
    The archive is always built with `q=""` — searching a list must not quietly
    hand a print shop a shorter run, which is the same reason the counts beside
    it are taken over the whole selection.
    """
    chosen = {k: str(v) for k, v in (filters or {}).items() if k in selectors.INVOICE_FILTERS}
    chosen.pop("status", None)
    params = ListParams(q=q, sort="invoice_no", dir="asc", filters=chosen)
    return selectors.invoice_list_queryset(params).filter(status__in=PRINTABLE_STATUSES)


# ── the forecast: what this set would hand over, before anything is drawn ────
#
# ⚠ **THE CLERK USED TO LEARN THIS AFTER GENERATING, WHICH IS TOO LATE**
# (`DEF-BIL-5354`). `held-back.csv` has always named every bill that did not go
# and why — inside the archive, after several minutes of a worker's time. The
# blueprint's screen 28 asks the same question BEFORE the button: *"404 will
# print · 8 held back, each with a reason"*.
#
# **THREE OF THE EIGHT HELD REASONS CAN BE FORECAST AND FIVE CANNOT, AND THAT
# SPLIT IS THE WHOLE DESIGN.** `_add_one` checks cheapest-first: the bill
# number, then the filename collision, then the address, and only then does it
# draw a page. Everything ABOVE the draw is two columns and a seam read, so it
# is forecastable in SQL. Everything at or below it — a refused document, a
# kept original that will not read back, a page count that cannot be taken —
# is only knowable by drawing the page, and a screen that pretended otherwise
# would be guessing at somebody's post.
#
# **`duplicate_filename` IS NOT FORECAST AND IS NOT MISSING EITHER**: the file
# name is the bill number, and `uq_invoices_no` is a UNIQUE index over
# (tenant, invoice_no). Two bills in one tenant cannot carry the same number,
# so the check in `_add_one` is a belt-and-braces guard against a constraint
# that would have to have failed first, and forecasting it would mean counting
# a thing this database forbids.

#: The reasons a bill can be held back WITHOUT drawing its page, in `_add_one`'s
#: own order of precedence. A bill matches at most one, and the first wins —
#: exactly as it does when the archive is built.
FORECASTABLE_HELD_REASONS: tuple[str, ...] = (
    HELD_NO_BILL_NUMBER,
    HELD_UNSAFE_BILL_NUMBER,
    HELD_ADDRESS_INCOMPLETE,
)

#: A bill with no number at all, as a query. Written once because the forecast's
#: three counts have to PARTITION the selection: every later reason excludes the
#: earlier ones, or a bill with no number and no address is counted twice and
#: `will_print + held` stops equalling the population. The blueprint says that
#: out loud — *"404 + 8 = 412. A set that printed 404 of 412 without saying so
#: sends a print shop a short run and tells nobody."*
_NO_BILL_NUMBER_Q = Q(invoice_no__isnull=True) | Q(invoice_no="")


@dataclass(frozen=True)
class PrintSetForecast:
    """What a set over these filters would contain, before a page is drawn.

    `held_by_reason` carries only NON-ZERO reasons, in `FORECASTABLE_HELD_
    REASONS` order, so a screen listing them never draws a row that says
    *"0 bills, no bill number"*.

    ⚠ **`addresses_readable=False` MEANS THE QUESTION COULD NOT BE ASKED, AND
    IT IS NOT A ZERO.** The mailing address belongs to `customers` and is
    reached by name (B1); with nothing published, this forecast counts the two
    reasons it CAN see and says the third is unknown. A screen must state that
    rather than print a confident *"0 held back"* — the difference between
    *nobody is held* and *nobody could ask* is somebody's bill in the post.
    """

    bills: int = 0
    will_print: int = 0
    held: int = 0
    held_by_reason: tuple[tuple[str, int], ...] = ()
    pages: int = 0
    addresses_readable: bool = True


def forecast_print_set(filters: dict[str, str] | None = None) -> PrintSetForecast:
    """The counts screen 28's four tiles are built from — four statements.

    Every count is taken in the DATABASE over the same selection the archive
    will walk, so this answers in the same time at 40,000 bills as at 80
    (`NFR-3`/`NFR-5`: the per-bill loop this replaces was two statements a bill
    and would have been 80,000 of them at the top of the ICP).
    """
    selection = print_set_selection(filters)
    bills = selection.count()
    gap_accounts = customers_seam.account_ids_without_print_address()

    numbered = selection.exclude(_NO_BILL_NUMBER_Q)
    counts: dict[str, int] = {
        HELD_NO_BILL_NUMBER: selection.filter(_NO_BILL_NUMBER_Q).count(),
        # `exclude(regex)` over the NUMBERED rows only: a null invoice_no is
        # already accounted for above, and SQL's three-valued logic would drop
        # it out of both sides of this one.
        HELD_UNSAFE_BILL_NUMBER: numbered.exclude(
            invoice_no__regex=SAFE_FILENAME_RE.pattern
        ).count(),
        HELD_ADDRESS_INCOMPLETE: (
            0
            if gap_accounts is None
            else numbered.filter(invoice_no__regex=SAFE_FILENAME_RE.pattern)
            .filter(account_id__in=gap_accounts)
            .count()
        ),
    }
    held = sum(counts.values())
    will_print = max(bills - held, 0)
    return PrintSetForecast(
        bills=bills,
        will_print=will_print,
        held=held,
        held_by_reason=tuple(
            (reason, counts[reason]) for reason in FORECASTABLE_HELD_REASONS if counts[reason]
        ),
        pages=will_print * MEASURED_PAGES_PER_BILL,
        addresses_readable=gap_accounts is not None,
    )


#: The two things screen 28's WILL IT PRINT column can say, as a filter value.
FORECAST_HELD = "held"
FORECAST_WILL_PRINT = "will_print"


def filter_by_forecast(selection: Any, verdict: str) -> Any:
    """Narrow a selection to the bills that WILL print, or to those held back.

    ⚠ **THE UNION HERE AND THE PARTITION IN `forecast_print_set` MUST AGREE, AND
    A TEST HOLDS THEM TOGETHER.** This asks *is any forecastable reason true*;
    the forecast asks *which one is true first*. A bill with no number and no
    address matches one leg of this and exactly one count there, so
    `filter_by_forecast(…, held).count()` and `forecast.held` are the same
    number — and if a later reason is ever added to one and not the other, the
    door reading *"See the 8 held back"* would open on nine rows.
    """
    gap_accounts = customers_seam.account_ids_without_print_address()
    held = _NO_BILL_NUMBER_Q | ~Q(invoice_no__regex=SAFE_FILENAME_RE.pattern)
    if gap_accounts is not None:
        held |= Q(account_id__in=gap_accounts)
    return selection.filter(held) if verdict == FORECAST_HELD else selection.exclude(held)


def forecast_rows(invoices: Iterable[models.Invoice]) -> dict[str, str | None]:
    """One page of bills → `{invoice id: held reason, or None for will print}`.

    ⚠ **THE ADDRESS QUESTION IS ASKED ONCE FOR THE WHOLE PAGE, NOT ONCE A ROW.**
    Fifty rows through `customers_seam.print_address_for_account` is a hundred
    statements to render one screen; the bulk read narrowed to the page's
    accounts is a fixed handful — the same for 50 rows as for one (`NFR-3`).
    It stopped being exactly ONE on 2026-09-24 (`DEF-BIL-6373`): an account
    with no mailing row walks to its premises, and that is metering's table,
    reached only through metering's read. The precedence is `_add_one`'s and is deliberately
    duplicated nowhere else — both this and `forecast_print_set` above walk
    `FORECASTABLE_HELD_REASONS` in the same order.

    A page whose address seam cannot be reached forecasts every row on its
    bill NUMBER alone; it never guesses that an unreadable address is a
    present one.
    """
    rows = list(invoices)
    verdicts: dict[str, str | None] = {}
    gap: set[str] = set()
    if rows:
        # Narrowed to THIS page's accounts before it is asked, because the
        # service-address leg materialises the accounts it walks
        # (`DEF-BIL-6373`) and a page should never pay for the whole tenant.
        gap_accounts = customers_seam.account_ids_without_print_address(
            account_ids=[invoice.account_id for invoice in rows]
        )
        if gap_accounts is not None:
            gap = {str(one) for one in gap_accounts}
    for invoice in rows:
        if not invoice.invoice_no:
            verdicts[str(invoice.id)] = HELD_NO_BILL_NUMBER
        elif pdf_filename_for(invoice.invoice_no) is None:
            verdicts[str(invoice.id)] = HELD_UNSAFE_BILL_NUMBER
        elif str(invoice.account_id) in gap:
            verdicts[str(invoice.id)] = HELD_ADDRESS_INCOMPLETE
        else:
            verdicts[str(invoice.id)] = None
    return verdicts


# ── one bill ────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class RenderedPage:
    """One bill's printable bytes, with WHERE they came from and HOW LONG."""

    pdf: bytes
    page_count: int
    from_original: bool


def _page_for(invoice: models.Invoice) -> RenderedPage:
    """The kept original if there is one, else the bill's OWN PINNED render.

    Raises `BillingRuleError` for everything a clerk can act on, so the caller
    turns it into a held row and the other 9,999 bills still print
    (`BR-BIL-055`'s posture, one named break per bill).
    """
    reproduction = frozen_bill.reproduce(invoice)
    if reproduction.is_original and reproduction.pdf is not None:
        try:
            # HASH-VERIFIED ON THIS READ, never taken on trust: the one check
            # that catches a document quietly replaced years later.
            kept = document_store.fetch(reproduction.pdf.id)
        except (
            document_storage.ContentHashMismatch,
            document_storage.DocumentStorageError,
            document_store.DocumentStoreError,
        ) as problem:
            raise BillingRuleError(
                # BR-NOT-027 — the kept bytes ARE the bill. The id belongs here.
                "the copy of this bill that was kept when it was issued cannot be read "
                "back, so it is held back rather than reprinted from the stored figures. "
                "A kept copy that has gone wrong is a different problem from no kept copy "
                "at all, and somebody needs to look at this one."
            ) from problem
        pages = page_count_of(kept)
        if pages is None:
            raise BillingRuleError(
                "we could not tell how many pages the kept copy of this bill has. A mail "
                "house quotes and stuffs envelopes by the page, so it is held back rather "
                "than sent with a guessed number beside it."
            )
        return RenderedPage(pdf=kept, page_count=pages, from_original=True)

    # NO TEMPLATE ARGUMENT. `documents._pinned` therefore takes the pin off the
    # invoice row — BR-BIL-026, *"a reprint renders the pinned version
    # forever"*. Passing today's version would be refused by `_pinned` if it
    # disagreed, and there is no render-on-latest option to reach for.
    rendered = documents.render_invoice(invoice)
    if rendered.pdf_page_count <= 0:  # pragma: no cover - the renderer always pages
        raise BillingRuleError(
            "this bill produced a document with no pages at all, so there is nothing to "
            "print. It is held back rather than counted as nothing."
        )
    return RenderedPage(
        pdf=rendered.pdf, page_count=rendered.pdf_page_count, from_original=False
    )


def _manifest_cells(
    invoice: models.Invoice,
    address: customers_seam.MailingAddress,
    *,
    customer_name: str | None,
    page_count: int,
    filename: str,
) -> list[str]:
    """The fourteen ruled columns for one bill, in `MANIFEST_HEADER` order.

    ⚠ **`bill_date` IS `invoices.service_date` AND THAT IS NOT AN
    APPROXIMATION.** `BR-BIL-070` (PO 2026-08-11 closing OQ-122, verbatim *"A
    Store what they type and use it"*) makes the clerk's typed bill date the
    RUN'S SERVICE DATE, and stage 6 stamps it on every invoice the run writes.
    So the date the run billed on is a stored column on the bill itself — no
    join to a cycle, no `effective_bill_date` re-derivation per row, and no
    clock. `due_date` is `BR-BIL-024`'s, derived at issue and stored beside it.

    ⚠ **`amount_due` DISPLAYS AT 2dp AND NOTHING HERE ROUNDS.** CLAUDE.md rule
    2: money is stored to 4 decimals and DISPLAYS at 2, and this file is a
    display. The formatter is `exports.format_money` — the IS-9 writer every
    other file in this product is written with — so there is not a second money
    formatter in the repository to disagree with the first. The figure is
    `invoices.total`, the bill's own finalized total, read and never summed.
    """
    return [
        invoice.account.account_no or "",
        invoice.invoice_no or "",
        customer_name or "",
        address.line1 or "",
        # Always empty today, and it is a schema gap rather than a blank we
        # forgot to fill: `customers.addresses` has no line2 column (DEF-2847).
        # NEVER carved out of line1 — BR-NOT-029 clause (a).
        address.line2 or "",
        address.city or "",
        address.state or "",
        address.postal_code or "",
        # Always empty today for the same reason (DEF-2847). `TenantSettings
        # .country` is the UTILITY's regional setting, and writing it here would
        # assert where a CUSTOMER lives from a fact about us.
        address.country or "",
        str(page_count),
        invoice.service_date.isoformat() if invoice.service_date else "",
        invoice.due_date.isoformat() if invoice.due_date else "",
        export_kernel.format_money(invoice.total),
        filename,
    ]


# ── the archive ─────────────────────────────────────────────────────────────
def _readme(result: PrintSetResult, *, generated_at: datetime) -> str:
    """What is in this archive, and — the part that matters — what is NOT.

    ⚠ **`BR-NOT-029` CLAUSE (c) IS WHY THE SECOND HALF OF THIS FILE EXISTS.**
    *"No screen, document, field name or report may state or imply that an
    address is CASS-certified, NCOA-processed or barcoded, because nothing in
    this product performs any of the three."* A vendor who assumes we did any of
    them mails at the wrong rate or not at all, so the archive says plainly that
    we did none — hard-won law 1 read forwards: the way to not claim a guarantee
    is to write down that you do not provide it.
    """
    return "\n".join(
        (
            "BILLS FOR PRINT",
            "",
            f"Generated: {generated_at.isoformat()}",
            f"Bills considered: {result.considered}",
            f"Bills in this set: {result.manifest_rows}",
            f"PDF files: {result.pdf_count}",
            f"Total pages: {result.page_total}",
            f"  from the copy kept when the bill was issued: {result.from_original}",
            f"  re-drawn from the bill's own stored data and pinned layout: "
            f"{result.re_rendered}",
            f"Bills held back: {result.held_count}  (see {HELD_NAME})",
            f"List of bills: {result.manifest_name}",
            "",
            "WHAT IS IN HERE",
            f"  {PDF_DIR}/         one print-ready PDF per bill, named by its bill number",
            f"  {result.manifest_name}     one row per bill: account and bill number, the customer,",
            "                   the address in separate fields, the page count, the bill",
            "                   and due dates, the amount due and the PDF filename",
            f"  {HELD_NAME}    every bill we could NOT hand over, and why",
            "",
            "WHAT WE HAVE NOT DONE TO THESE ADDRESSES",
            "  These addresses have NOT been CASS-certified.",
            "  They have NOT been NCOA-processed (no mover lookup has been run).",
            "  No Intelligent Mail barcode has been applied.",
            "  We do not perform any of those three and we do not claim to. The address",
            "  fields are our own records, given to us by the account holder, supplied in",
            "  separate columns so that you can standardise them yourselves.",
            "",
            "IF YOU FIND A CUSTOMER HAS MOVED",
            "  Please tell us, and please do not treat it as an instruction. We change a",
            "  customer's address only when the account holder tells us to.",
            "",
        )
    )


def build_print_set(
    invoices: Iterable[models.Invoice],
    archive_path: Path,
    *,
    generated_at: datetime,
    total: int | None = None,
    job_id: Any = None,
    progress_every: int = 25,
    manifest_format: print_formats.PrintFormat | None = None,
) -> PrintSetResult:
    """Write ONE print set to `archive_path`. Returns what it produced.

    ⚠ **ONE PASS, AND ONE BILL IN MEMORY AT A TIME.** The page has to exist
    before the manifest row can carry its page count, so the two are produced
    together per bill rather than in two passes; and the PDF is handed to the
    zip and dropped before the next bill is read. The two CSVs are written row
    by row into a temporary directory and added at the end. Nothing accumulates
    except the held list, which is bounded by the number of bills that are
    WRONG rather than by the number of bills.

    ⚠ **A BILL THAT CANNOT BE HANDED OVER IS HELD, AND THE SET STILL SHIPS.**
    `BR-BIL-055`'s posture, one named break per bill: a broken bill in a set of
    five hundred must not cost the other four hundred and ninety-nine their
    post. Every held bill lands in `held-back.csv` with a sentence.

    `generated_at` is the CALLER's instant and is never read from a clock here
    (`BR-TEN-043`, gate G6 — there is no `timezone.now()` anywhere under
    `apps/billing/`). A worker that picked the job up an hour later must not
    stamp the archive with its own queue latency.

    ── CR-053 TASK 14 · THE MANIFEST IS WRITTEN THROUGH A NAMED FORMAT ────────
    `manifest_format` is a `print_formats.PrintFormat` and `None` means the one
    the registry ships. The file's NAME and its ENCODING both come from it, and
    its COLUMNS are `MANIFEST_HEADER` — `BR-NOT-029`'s ratified fourteen —
    which is passed IN rather than restated there, so one place in this
    repository says what a print vendor receives. A vendor format that names
    its own field list carries it on the format (`OQ-1167` (b)); until one
    does, every format writes the fourteen.
    """
    fmt = manifest_format or print_formats.get(None)
    result = PrintSetResult(archive_name=archive_path.name, manifest_name=fmt.filename)
    seen_filenames: dict[str, str] = {}

    with tempfile.TemporaryDirectory(prefix="print-set-") as scratch:
        scratch_dir = Path(scratch)
        manifest_path = scratch_dir / fmt.filename
        held_path = scratch_dir / HELD_NAME

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            # The writer is CLOSED in a `finally` and not merely flushed: a
            # manifest flushed but not closed can lose its last row, and the
            # archive would carry the truncation without complaining.
            manifest = fmt.open(manifest_path, MANIFEST_HEADER)
            try:
                for invoice in invoices:
                    result.considered += 1
                    held = _add_one(invoice, archive, manifest, seen_filenames, result)
                    if held is not None:
                        result.held.append(held)
                    if job_id is not None and result.considered % progress_every == 0:
                        core_jobs.record_progress(job_id, done=result.considered, total=total)

                with held_path.open("w", encoding="utf-8", newline="") as held_handle:
                    held_writer = csv.writer(held_handle)
                    held_writer.writerow(list(HELD_HEADER))
                    for entry in result.held:
                        held_writer.writerow(entry.cells())
            finally:
                manifest.close()

            archive.write(manifest_path, arcname=fmt.filename)
            archive.write(held_path, arcname=HELD_NAME)
            archive.writestr(README_NAME, _readme(result, generated_at=generated_at))

    if job_id is not None:
        core_jobs.record_progress(job_id, done=result.considered, total=total)
    return result


def _add_one(
    invoice: models.Invoice,
    archive: zipfile.ZipFile,
    manifest: Any,
    seen_filenames: dict[str, str],
    result: PrintSetResult,
) -> HeldBill | None:
    """One bill into the archive, or the reason it stayed out. No exceptions escape.

    THE ORDER OF THE CHECKS IS DELIBERATE AND IT IS CHEAPEST-FIRST: the bill
    number and the address are two reads, and rendering a page is by far the
    most expensive thing this module does. A bill with no postcode is held
    before its PDF is drawn, so a tenant where `DEF-2703` holds every bill costs
    a few queries rather than a full render pass.
    """
    account_no = getattr(invoice.account, "account_no", None)
    filename = pdf_filename_for(invoice.invoice_no)
    if filename is None:
        if not invoice.invoice_no:
            return HeldBill(
                account_no,
                None,
                HELD_NO_BILL_NUMBER,
                # B14 rule 31 is WHY the internal id is not substituted; saying so
                # on screen would be putting an internal reference in front of a
                # clerk to explain why an internal reference is absent.
                "this bill has no bill number, so there is nothing to name its page with "
                "and nothing to put in the list for the printer to match it to. Give the "
                "bill a number and build the set again.",
            )
        return HeldBill(
            account_no,
            invoice.invoice_no,
            HELD_UNSAFE_BILL_NUMBER,
            f"the bill number {invoice.invoice_no!r} contains characters that cannot be "
            "used in a file name, and we do not quietly rewrite it: the name on the page "
            "and the number in the list have to read the same.",
        )
    if filename in seen_filenames:
        return HeldBill(
            account_no,
            invoice.invoice_no,
            HELD_DUPLICATE_FILENAME,
            f"another bill in this set is already named {filename}, so adding this one "
            "would replace it. Two bills are carrying the same bill number, which should "
            "not be possible. Nothing has been replaced and this one is held back.",
        )

    address = customers_seam.print_address_for_account(invoice.account_id)
    if not address.readable:
        problem = address.problem or {}
        return HeldBill(
            account_no,
            invoice.invoice_no,
            HELD_ADDRESS_UNREADABLE,
            str(problem.get("detail") or "this account's mailing address could not be read."),
        )
    if address.missing:
        # BR-NOT-029 clause (b). WHICH record to fix depends on which address
        # the bill goes to (`DEF-BIL-6373`): the account's own mailing row, or
        # — with none — the property's address, where hard rule 8 keeps it.
        parts = ", ".join(part.replace("_", " ") for part in address.missing)
        if address.source == "mailing_address":
            where, fix = (
                "this account's mailing address",
                "Add the missing parts to the account's mailing address",
            )
        elif address.source == "service_address":
            where, fix = (
                "this account has no mailing address, and its service address",
                "Add the missing parts to the property's address, or give the account a "
                "mailing address,",
            )
        else:
            where, fix = (
                "this account has no mailing address and no property street to fall back "
                "on, so it",
                "Give the account a mailing address, or add the property's street,",
            )
        return HeldBill(
            account_no,
            invoice.invoice_no,
            HELD_ADDRESS_INCOMPLETE,
            f"{where} has no {parts}. A mail house cannot standardise, barcode or rate an "
            "address without all of those, so the bill is held back rather than sent with "
            f"the gap filled in by us. {fix} and build the set again.",
        )

    try:
        page = _page_for(invoice)
    except BillingRuleError as refusal:
        reason_code = (
            HELD_ORIGINAL_UNREADABLE
            if "kept when it was issued" in str(refusal)
            else HELD_PAGE_COUNT_UNKNOWN
            if "page count" in str(refusal)
            else HELD_DOCUMENT_REFUSED
        )
        return HeldBill(account_no, invoice.invoice_no, reason_code, str(refusal))
    except Exception as broken:  # noqa: BLE001 - one bill never takes the set down
        # BR-BIL-055's posture. A layout that raises something the renderer did
        # not translate must cost ONE bill its post, not five hundred.
        #
        # ⚠ **EXCEPT THE ONE EXCEPTION THAT IS ABOUT THE WHOLE SET** (CR-051
        # task 30). Celery's soft time limit is an ordinary `Exception` raised
        # ONCE, and drawing a page is where this job spends nearly all of its
        # time — so this handler is the single most likely place for it to
        # land. Held as a broken bill, it would file the run's only warning
        # against one customer and print the other nine thousand past a limit
        # that then never fires again.
        core_jobs.reraise_if_time_limit(broken)
        logger.warning(
            "print set: bill %s could not be drawn (%s)", invoice.invoice_no, broken, exc_info=True
        )
        return HeldBill(
            account_no,
            invoice.invoice_no,
            HELD_DOCUMENT_REFUSED,
            "this bill's page could not be produced, so it is held back. Nothing about "
            "the bill's money is in question and the bill itself is unchanged.",
        )

    try:
        customer_name = selectors._customer_name(invoice.account)
    except Exception as broken:  # noqa: BLE001 - a seam that cannot answer holds one bill
        core_jobs.reraise_if_time_limit(broken)  # CR-051 task 30 — never here
        logger.warning("print set: no customer name for bill %s (%s)", invoice.invoice_no, broken)
        customer_name = None

    archive.writestr(f"{PDF_DIR}/{filename}", page.pdf)
    manifest.writerow(
        _manifest_cells(
            invoice,
            address,
            customer_name=customer_name,
            page_count=page.page_count,
            filename=filename,
        )
    )
    seen_filenames[filename] = str(invoice.invoice_no)
    result.pdf_count += 1
    result.manifest_rows += 1
    result.page_total += page.page_count
    if page.from_original:
        result.from_original += page.page_count
    else:
        result.re_rendered += page.page_count
    return None


# ── the artifact ────────────────────────────────────────────────────────────
def archive_filename(tenant_id: Any, *, period: str, generated_at: datetime) -> str:
    """IS-11's five segments, with `.zip` — `{tenant}_bills-print_{period}_pdf-set_{generated}.zip`.

    The same shape `exports.artifact_filename` composes for a CSV, and it is not
    imported from there because that helper hardcodes `.csv` and this is not
    one. `generated_at` is the CALLER's instant (`BR-TEN-043` / G6: there is no
    clock under `apps/billing/`), formatted in the tenant's own zone so the name
    reads as the local moment a clerk pressed the button.
    """
    tz = export_kernel.tenant_timezone(tenant_id)
    generated = generated_at.astimezone(tz).strftime("%Y%m%dT%H%M")
    return "_".join((export_kernel.tenant_slug(tenant_id), "bills-print", period, "pdf-set", generated)) + ".zip"


def period_segment_for(filters: dict[str, str] | None) -> str:
    """The `{period}` filename segment, from the caller's OWN issued-date range.

    `exports.period_segment` reads `from`/`to`; the bills list names the same
    window `issued_from`/`issued_to`, so the keys are mapped rather than a
    second derivation being written. With no range the set covers whatever the
    filters selected and says `all`.
    """
    chosen = filters or {}
    return export_kernel.period_segment(
        {"from": chosen.get("issued_from"), "to": chosen.get("issued_to")}, default="all"
    )


# ── the job ─────────────────────────────────────────────────────────────────
def would_run() -> tuple[bool, str]:
    """Would a print set enqueued right now actually be EXECUTED? (`DEF-2487`.)

    Asks about BILLING'S OWN QUEUE, which is a different question from *"is any
    worker alive"* since `CR-051` task 29 split it: a healthy `celery` worker
    answers a broadcast ping while the `billing` queue has no consumer at all,
    and a set enqueued into that would say *queued* for ever.
    """
    return core_jobs.dispatch_is_ready(PRINT_SET_JOB)


def enqueue_print_set(
    *,
    filters: dict[str, str],
    generated_at: datetime,
    count: int,
    actor_user_id: Any = None,
    format_name: str | None = None,
) -> dict[str, Any]:
    """One print set to the billing worker. Returns the record; the API answers 202.

    The ceiling is checked HERE and not in the worker, so an oversized set is
    refused while a person is still looking at the screen — a worker that
    discovered it would have nobody to tell.

    **THE SCOPE KEY IS THE IDEMPOTENCY.** `billing:print-set:<format>:<the
    filters>` — so a double-clicked *Build the print set* returns THE EXISTING
    RECORD rather than starting a second pass over the same ten thousand bills.
    It is keyed on the SELECTION and not on the instant: two clicks a second
    apart are one intention, and including `generated_at` would make every
    click a new job, which is the same as having no key at all.

    ⚠ **THE FORMAT IS PART OF THE KEY (CR-053 task 14), AND LEAVING IT OUT
    WOULD BE A BUG WITH NO SYMPTOM.** Two requests over the same bills in two
    different vendor formats are two different files and two different
    intentions; folded onto one scope key the second caller would be handed the
    FIRST one's archive and told it succeeded. The format is refused here too,
    before the record exists, for the same reason the ceiling is: a worker that
    discovered an unknown format would have nobody to tell.
    """
    refuse_if_oversized(count)
    fmt = print_formats.get(format_name)
    scope = ";".join(f"{key}={filters[key]}" for key in sorted(filters))
    return core_jobs.enqueue(
        PRINT_SET_JOB,
        payload={
            "filters": {str(k): str(v) for k, v in filters.items()},
            "generated_at": generated_at.isoformat(),
            "count": int(count),
            "format": fmt.name,
            "actor_user_id": None if actor_user_id is None else str(actor_user_id),
        },
        scope_key=f"billing:print-set:{fmt.name}:{scope}",
    )


def run_print_set_job(record: dict[str, Any]) -> str:
    """The BE-07 body: write the archive, return its DOWNLOAD ROUTE.

    Runs under the record's tenant context — `core.jobs.run_job` enters it — so
    the selection behind the archive is the caller's own tenant's, enforced by
    RLS on Postgres and by the explicit tenant filter `selectors
    .invoice_queryset` applies on every tier (hard rule 1).

    NO CLOCK (`BR-TEN-043` / G6). `generated_at` is the instant the CALLER
    stamped, carried on the payload as an ISO-8601 string and parsed back here,
    exactly as `run_jobs.run_issue_job` carries `issued_at`.

    The link it returns is the PLATFORM download `/api/exports/{job_id}/file`,
    which serves a FINISHED FILE and touches no database — see the module
    docstring on why that is the answer to `DEF-2734` rather than a guarded
    stream.
    """
    payload = record.get("payload") or {}
    tenant_id = record["tenant_id"]
    filters = {str(k): str(v) for k, v in (payload.get("filters") or {}).items()}
    generated_at = datetime.fromisoformat(str(payload["generated_at"]))
    # CR-053 task 14. A payload written before this key existed — a message
    # already in the broker during a deploy — carries no `format` and gets the
    # registry's default, which is the file it was going to get anyway. An
    # UNKNOWN name still refuses here rather than falling back: the door check
    # in `enqueue_print_set` is the one a person sees, and this is the one that
    # stops a hand-written payload producing the wrong file quietly.
    manifest_format = print_formats.get(payload.get("format"))

    # ⚠ THE WHOLE ARCHIVE IS BUILT IN THIS JOB'S OWN SCRATCH FOLDER (`DEF-BIL-9148`;
    # PO 2026-10-02, exports move to S3). It used to be written straight into the
    # shared artifacts folder, so a build that died part way left a partial ZIP
    # beside every utility's finished downloads. Now the folder — ZIP, manifest
    # and held-back list — is removed when the `with` closes, on success and on
    # failure, and only a FINISHED archive is uploaded (in parts) to
    # `t/<web name>/export/…`. Scratch needed ≈ the archive: ~2.7 KB a bill
    # (measured, 09-infra/04-exports-to-s3.md §3). Old sets are no longer swept
    # here — the daily per-utility sweep does it.
    with export_kernel.scratch_dir() as folder:
        path = Path(folder) / archive_filename(
            tenant_id, period=period_segment_for(filters), generated_at=generated_at
        )

        selection = print_set_selection(filters)
        result = build_print_set(
            _iterate(selection),
            path,
            generated_at=generated_at,
            total=payload.get("count"),
            job_id=record["id"],
            manifest_format=manifest_format,
        )
        logger.info(
            "print set wrote %s PDF(s), %s manifest row(s), %s held, into %s",
            result.pdf_count,
            result.manifest_rows,
            result.held_count,
            path.name,
        )
        return export_kernel.finish_artifact(
            record["id"], path, tenant_id=tenant_id, content_type=export_kernel.ZIP_CONTENT_TYPE
        )


def _iterate(selection: Any) -> Iterator[models.Invoice]:
    """The selection, one row at a time, with the account already joined.

    `select_related("account")` is not an optimisation detail worth hiding: the
    manifest reads `account_no` for every row, and without it a 10,000-bill set
    costs 10,000 extra statements — which is precisely the arithmetic `CR-053`'s
    performance clause asks every per-account addition to be measured against.
    """
    return selection.select_related("account").iterator(chunk_size=200)


def register() -> None:
    """Register the body and its queue. Called from `BillingConfig.ready`.

    On BILLING'S OWN QUEUE (`run_jobs.BILLING_QUEUE`, PO ruling 2026-08-31:
    *"billing will need its own named workers - otherwise it will slow down the
    system"*). A print set over a whole cycle is the exact shape of work that
    ruling was about, and routing it anywhere else would put it back in the two
    worker slots shared with exports, imports and customers' outbound notices.
    """
    core_jobs.set_job_handler(PRINT_SET_JOB, run_print_set_job)
    core_jobs.set_job_queue(PRINT_SET_JOB, run_jobs.BILLING_QUEUE)
    # The archive is downloaded through the PLATFORM route
    # `GET /api/exports/{job_id}/file`, which serves only kinds that declared
    # themselves. Registering here rather than in tenancy is the same posture as
    # the handler above: the module that owns the WORK owns the statement.
    export_kernel.register_export_kind(PRINT_SET_JOB)


__all__ = [
    "HELD_HEADER",
    "MANIFEST_HEADER",
    "MANIFEST_NAME",
    "MAX_BILLS_PER_PRINT_SET_DEFAULT",
    "MEASURED_SECONDS_PER_BILL",
    "MEASURED_STATEMENTS_PER_BILL",
    "PRINTABLE_STATUSES",
    "PRINT_SET_JOB",
    "HeldBill",
    "PrintSetResult",
    "archive_filename",
    "build_print_set",
    "enqueue_print_set",
    "max_bills_per_print_set",
    "page_count_of",
    "pdf_filename_for",
    "period_segment_for",
    "print_set_selection",
    "refuse_if_oversized",
    "register",
    "run_print_set_job",
    "would_run",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-053 task 13 (12-governance/11-change-requests.md) + BR-NOT-029
#         (04-docs/05-modules/10-notifications/02-business-rules.md) +
#         BR-CUS-674 (03-customers/02-business-rules.md) + BR-BIL-026/030/036
#         (07-billing/02-business-rules.md) + the PO ruling of 2026-08-30
#         (12-governance/02-decision-log.md)
# generated: 2026-08-31 by the CR-053 W4 print-bills lane
# checklist: A✔ B✔ C✔ D✔(apps/billing/print_api.py) E✔(the Print bills screen)
#         F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_cr053_print_set.py · golden-verify 33 PASS /
#         0 FAIL before and after (nothing here computes money) · SIX GUARDS
#         PROVED RED FIRST, each quoted in the lane report and in
#         12-governance/09-human-review-ledger.md
# ⚠ CORRECTED 2026-09-30 (gate triage T6) — THE `human_owned.txt` SENTENCE BELOW IS
#   HISTORY, NOT THE CURRENT STATE: this path was added to the list by PO
#   ruling 2026-09-30 (option A, commit `dabb8a323`), so G7 reads its markers.
# exceptions: (1) NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS
#         FILE, so G7 does not read the HUMAN-OWNED markers above. REPORTED in
#         the review-ledger row and never self-granted — editing that list is a
#         process event, the posture `run_jobs.py` took from the same position.
#         (2) `address_line_2` AND `country` ARE STRUCTURALLY EMPTY.
#         `customers.addresses` has neither column (DEF-2847) and no customer
#         table in this product has a country at all; `TenantSettings.country`
#         is the UTILITY's. BR-NOT-029 clause (a) forbids carving line 2 out of
#         line 1 and clause (b) does not require either field, so both are
#         emitted blank and the archive's README says why.
#         (3) MOST BILLS WILL BE HELD ON A TENANT WHOSE ACCOUNTS CAME FROM
#         SERVICE REQUESTS (DEF-2703 — the mailing address is one free-text
#         blob). CR-053 task 13 says this in its own words: *"That is the rule
#         working, not the build failing."*
#         (4) IT DOES NOT DELIVER ANYTHING. BR-NOT-013 keeps delivery out of
#         this release; a manifest is rendered output handed over WITH the
#         documents, which BR-NOT-029's own last clause states.
#         (5) NO PROVENANCE COLUMN ON THE MANIFEST. BR-NOT-029 names fourteen
#         columns and a manifest is a vendor's file spec; the original/rebuilt
#         split is a page total in README.txt instead.
#         (6) THE RETENTION SWEEP HAD TO LEARN ABOUT `.zip`
#         (`exports.purge_expired`), which globbed `*.csv` and would have kept
#         every print set on disk for ever. One-line change, named here because
#         it is a shared file this module made necessary.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
