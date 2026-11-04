# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-022 (the pin at issue, and a reprint that renders the pinned
#           version forever) ·
#           US-BIL-028 (the custom-field snapshot — stamped at draft by
#           apps/billing/custom_snapshot.py and PRINTED here, in the one
#           remark/note section the PO ruled on 2026-08-12 closing OQ-125/OQ-118)
#           Screens: S30 (bill detail · document panel · Remarks & notes) ·
#           S22 (Account → Print bill) · S31 step 6
#           Two further stories are deliberately NOT cited in this header — see
#           the docstring, where G10 reads prose rather than a completion claim.
# Rules:    BR-BIL-026 (template + version PINNED at issue; a reprint renders
#           the pinned version forever; publishing affects only future bills) ·
#           BR-BIL-030 (the bill is LOCKED at issue — the document renders from
#           the stamped instance and joins NOTHING live) · BR-BIL-031 (two
#           version axes: `payload_version` is the DATA contract, the template
#           version is the PRESENTATION; a template DECLARES which payload
#           versions it can render) · BR-BIL-032 (the instance ties out to its
#           rows) · BR-BIL-033 (render BEFORE issue; a failed render REFUSES the
#           issue) · BR-BIL-035 (bill format standalone | balance-forward; the
#           arrears figures are STAMPED, never recomputed at reprint) ·
#           BR-BIL-036 (print is the primary channel) · BR-CUS-040 (a reprint
#           renders the issued document and never recomputes) · BR-RAT-003
#           (round per line, half-up, 2dp, at finalization/display ONLY) ·
#           BR-TEN-043 (event time is named by the caller, never a clock) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money NUMERIC(18,6) +
#           CHAR(3)) · rule 3 (a quantity carries its unit) · rule 4 (financial
#           immutability)
# Tests:    06-backend/tests/test_us_bil_022_documents.py
# Impacts:  apps/billing/issue.py (calls this as BR-BIL-033's precondition — a
#           bill that cannot render never issues) · apps/billing/api.py (the
#           unmounted `GET /invoices/{id}/document`, 11b §2.8) ·
#           apps/billing/stages/assemble_document.py (produces the payload this
#           reads; every field it does NOT stamp is listed on every document
#           this renders) · apps/notifications/services.py (writes BR-BIL-036's
#           PRINT row for every bill; `.pdf` is what that row exists to carry,
#           and there is still no store to put it in or dispatcher to take it)
# ───────────────────────────────────────────────────────
"""HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of 2026-08-09 ("AI will do it; we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not RATIFIED without a recorded human sign-off.

Bill / statement rendering, per A19 §1 — the customer document, from the
snapshot and from nothing else.

✔ **THIS FILE IS ON THE G7 GUARD LIST** (`10-scripts/gates/human_owned.txt`,
line added 2026-08-11 by the process batch — *"Bill document rendering — rounds
money for DISPLAY (CLAUDE.md 🔒) and is now the BR-BIL-033 precondition of
issue"*). ⚠ **THIS PARAGRAPH PREVIOUSLY SAID THE OPPOSITE AND WAS TRUE WHEN
WRITTEN**; it is corrected here rather than left standing, because a docstring
that describes a guard the repo has since gained is hard-won law 1 pointing the
other way. The reading behind the marker is unchanged: this file does no money
ARITHMETIC (EP-BIL-06 §7 — *"templates render money; they never compute it"*),
but it ROUNDS money for display (CLAUDE.md 🔒 "money rounding", B4/BR-RAT-003 —
see `_money`) and since BR-BIL-033 it is a PRECONDITION OF ISSUE: a bug here
either refuses lawful bills or lets an unrenderable one become immutable.

⚠ **SUPERSEDED 2026-10-23 FOR EVERY BILL ISSUED FROM NOW ON (`DEF-BIL-10546`,
PO/QA ruling, decision log "Portal accessibility, Group H").** A customer's
bill page is now a TAGGED PDF/UA-1 file written by WeasyPrint from `_html_for`'s
markup (`_tagged_pdf_for`, `core/tagged_pdf.py`), Liberation Sans embedded. The
section below is the reasoning for the hand-written writer, which is KEPT for
the re-render of a bill issued before v2.88.0 (ruled: *"New bills only. The old
ones stay as issued"*) and as the parity baseline. Its "deployment-image
decision" is the one the PO has now made; it was never a PO ruling before.

TWO SERIALISATIONS, ONE DOCUMENT — AND WHY NO PDF LIBRARY WAS INSTALLED
----------------------------------------------------------------------
A19 §1 heads the bill *"printed + PDF"*. BR-BIL-036 makes print the PRIMARY
channel and the floor, `apps/notifications/services.py` writes a print row for
every bill on that rule, and until 2026-08-11 this module produced nothing that
could be printed — a print channel with nothing printable. That is now closed:
`render_invoice` returns the same `RenderedDocument` it always did, with `body`
(HTML) and `pdf` (bytes) as **two serialisations of ONE structure**. Neither
reads the other's output; both consume the same `document` mapping built once
in `render_invoice`, and `LAYOUTS` holds ONE entry per template version with
BOTH callables on it, so a version can never be pinned for one serialisation
and not the other (BR-BIL-026).

**The PDF is written by this file, with the standard library and nothing else,
and that was an engineering call this lane took and recorded** (decision log
2026-08-11; it was not a PO ruling). The options, plainly:

  * **WeasyPrint** renders the real HTML/CSS — the obvious fit — but needs
    Pango, HarfBuzz and fontconfig as SYSTEM libraries. `06-backend/Dockerfile`
    installs the `pyproject.toml` list and nothing else, so this changes the
    deployment IMAGE. That is an Eng-Lead/PO decision, not a lane's.
  * **ReportLab** (permissive, pure-Python wheels, no system libs) does NOT
    consume HTML: it has its own layout language, so adopting it would create a
    SECOND layout that can drift from `_html` — the thing this module is
    explicitly not allowed to do. Its output also embeds a creation timestamp
    and a document id unless `rl_config.invariant` is set globally.
  * **xhtml2pdf** wraps ReportLab in a small CSS subset and drags html5lib,
    pypdf and Pillow behind it: the largest dependency tree of the three, for
    the weakest fidelity claim.
  * **fpdf2** is small and pure-Python but LGPL-3.0 — a licence class this
    repo does not currently carry, which is a legal call and not a lane's — and
    it has its own layout language too.

None of them is warranted by what this layer must do TODAY. A19's paper
geometry — the logo, the 12-month bar graph, the remittance barcode, the
tenant's own CSS — belongs to the S91–S96 designers and to the
`bill_template_versions` table that does not exist; there is no designed body
to render, so an engine that renders designed bodies has nothing to render.
What IS needed is A19 §1's FIELD ORDER on a printable page, deterministically,
from the frozen payload. PDF's text-and-page model is a documented, stable,
byte-level container and the Base-14 fonts need no embedding, so `_pdf` below
produces that in the standard library — no wheel, no system library, no image
change, no licence, no CVE surface, and **deterministic by construction,
because every byte is written here**.

⚠ **The engine question is NOT closed, it is DEFERRED, and it is OQ-149**
(OPEN). The day `bill_template_versions` lands with a tenant-designed body,
this floor stops being enough and the project needs a real HTML/CSS engine —
which is the day it becomes a deployment-image decision with a concrete
requirement attached. Registered rather than left as a comment (law 1).

WHAT THE PDF IS AND IS NOT
--------------------------
It is the FLOOR: every A19 §1 field, in A19 §1's order, typeset on US Letter in
the Base-14 fonts, paginated, with the remittance stub below a dashed rule. It
is not the tenant's template and does not pretend to be — no usage
graph, no colour, no tenant CSS (⚠ `no logo` STRUCK 2026-10-05, `CR-172-BRC10`: the
letterhead now draws the logo the bill was STAMPED with — see "THE LOGO" below), and it says so on every result in
`DOCUMENT_UNAVAILABLE`. ⚠ THIS LIST SAID `no barcode` UNTIL 2026-09-23. IT IS NOW FULLY
UNTRUE AND IS STRUCK RATHER THAN NARROWED: the remittance stub carries a Code 39
REMITTANCE LINE with its mod-43 check character — account, bill number and
amount in minor units — composed by `apps/billing/remittance.py` from this
bill's own frozen payload (CR-139-BRC07 `P5.10`), and since `DEF-BIL-6325` it
carries the drawn BARS above that line as well. The PDF writer grew `PageFill`,
a filled-rectangle primitive, for it. **A bill printed from this file can be
scanned.** The clause is corrected in place each time, because a refusal that
has quietly become untrue is what cost the customer portal six of its eight
front doors (hard-won law 2's mirror). A print vendor can print it and a customer can read
what they owe; that is the bar BR-BIL-036 sets and it is the bar this meets.

THE ONE RULE THIS FILE EXISTS TO KEEP
-------------------------------------
**The document renders from `invoices.bill_payload` and from the invoice's own
rows. It never joins to customers, premises, units, rating or tenancy.**

That is BR-BIL-030, and the PO's words for it were *"you have to keep lock data
for that bill and save the instance."* The failure it prevents is quiet: Sarah
marries in August and her name changes; a July bill reprinted in December then
prints the new name over the old period's charges, and the immutable rows say
one thing while the paper says another. No `UPDATE` statement is involved —
which is exactly why hard rule 4 alone does not catch it. A renderer that
reaches back into master data to fill a gap rewrites an issued financial
document by reading.

So when the snapshot lacks a field, this file renders an HONEST ABSENCE and
records it in `RenderedDocument.absent`. It never goes and finds the value.
Two guards hold the line, and both were proved RED before they were trusted:
`test_us_bil_022_tc1` renames the live account holder after issue and asserts
the document still prints the stamped name, and `test_us_bil_022_tc2` asserts
the render issues exactly ONE database query — the invoice's own lines — so a
live join fails on the count even if it happens to return the same string.

WHAT THE INVOICE'S OWN ROWS ARE, AND WHY READING THEM IS NOT A LIVE JOIN
-----------------------------------------------------------------------
`invoice_lines` are not master data. They are the financial record of THIS
document, frozen by the same trigger that freezes its money the moment the
status leaves draft (billing 0002/0006), and BR-BIL-004 makes a correction a
new row rather than an edit. Reading them can therefore never show something
different from what the customer was sent. Every money figure printed here
comes from `invoices.total` or from `invoice_lines.amount` as stored; nothing
is recomputed, re-priced or re-summed into a new figure (BR-CUS-040).

Master data is different in kind: `accounts.name`, `units.label`,
`rate_plans.*` and the tenant's own identity all move legitimately after a bill
is sent. Those come from the snapshot or not at all.

THE PIN (BR-BIL-026), AND WHAT IS AND IS NOT HONOURED
-----------------------------------------------------
`invoices.template_id` + `.template_version` are pinned at issue. This module
resolves its layout from the PIN and never from a "current" or "latest
published" pointer — `LATEST_REGISTERED_VERSION` exists so a caller can ask
which layouts are registered, and the render path does not read it. Nor is
there a "render on latest" argument (US-BIL-022 TC-4: *"No such option
exists"*); passing a `template_version` that disagrees with an issued bill's
pin is REFUSED rather than honoured.

⚠ **THIS PARAGRAPH SAID THE TEMPLATE TABLES DID NOT EXIST AND IT IS REWRITTEN
RATHER THAN LEFT STANDING (hard-won law 1).** They exist, they are seeded at
provisioning (DEF-123), and since **2026-08-16** `_layout_for` resolves the
pinned version ROW and renders the `layout_key` that row stores. So the tenant's
CHOICE of layout is honoured, on both serialisations, frozen with the bill.

What is still NOT honoured, and now by ruling rather than by gap: **a tenant's
own DESIGNED page.** PO 2026-08-16, verbatim — *"why cant we give 5 differnt
tempaltes to start with and ask user to choose anyone; we will ahve 1 default
tempalte allways"* — so R2 has no bill-layout designer (S91–S96 are CUT) and the
platform publishes a library of five (`LAYOUT_SPECS`). A tenant chooses one of
them, plus its bill messages and its footer; it does not author markup. That is
what keeps an HTML/CSS engine and its ~200MB font-shaping tree out of the
deployment image — no key can name a page the platform did not write, so nothing
ever has to render one.

Every document still says which door its layout came through, in
`RenderedDocument.layout_source`: `platform-layout-<key>` for a tenant's choice,
`registered-layout-v1` for a bill pinned before the library existed.

THE TWO VERSION AXES (BR-BIL-031)
---------------------------------
`payload_version` is the DATA contract and the template DECLARES which payload
versions it can render. `PAYLOAD_VERSIONS` is that declaration, and a bill whose
payload version is outside it is REFUSED rather than rendered from keys the
layout is guessing at. Today the set is `(1,)` — one payload shape has ever
existed. The refusal matters more than the set: it is what stops the first
payload change from silently printing blanks on every historical reprint.

WHAT THE SNAPSHOT DOES NOT CARRY — REPORTED, NOT WORKED AROUND
--------------------------------------------------------------
BR-BIL-030 lists what the instance must hold: *"tenant identity and branding
reference, customer name, service address, premises/unit, account number, each
meter with its prior and current read and unit, every line grouped by service,
taxes, totals and messages."* Stage 6 stamps a fraction of that. Every gap is
an entry in `RenderedDocument.absent`, and the ones a bill cannot really do
without are:

  * **The masthead** — utility name, address, support phone/email (A19 §1.1).
    Nothing tenant-side is stamped, so the document cannot say who sent it.
  * **The service address** (A19 §1.2). `unit_label` is stamped; the premises
    address is not, so *"Unit A"* has no street.
  * **Bill date and cycle** (A19 §1.2). The cycle's `bill_date` is what
    BR-BIL-024 derives the due date FROM, and it is not on the invoice or in
    the payload; only the derived `due_date` survives.
  * **The whole summary box** (A19 §1.3, BR-BIL-035). Previous balance,
    payments/credits and therefore TOTAL DUE are absent. `invoices.total` is
    the CURRENT CHARGES — the engine's own trailer says prior balance is not in
    it — so the largest number on a utility bill is the one field this
    renderer cannot honestly print. BR-BIL-035 requires payload v1 to carry the
    balance-forward section *"whether or not a given tenant renders it"*; it
    does not, and the tenant's standalone-vs-balance-forward setting is not
    stamped either, so the format cannot be inferred from what is there.
  * **Meter number, prior read, current read** per service (A19 §1.4). Stage 2
    measures all three (`contracts.ServiceReading`) and stage 6 keeps only
    whether a service was measured.
  * **The tax authority and rate** per tax line (A19 §1.6) — the same gap that
    stops a tax line resolving its GL account at issue.
  * **Line → service attribution.** Stage 6 writes no `service` on its lines,
    so *"every line grouped by service"* groups everything under one unnamed
    heading. The payload's own `services` list is rendered beside it, which is
    the closest honest thing: it says which services were read this period.

None of these is guessed and none is fetched. A bill with an absent total due
is visibly broken; a bill with a plausible total due fetched from live data is
invisibly wrong, and only one of those gets fixed.

A BILL THAT CANNOT PRINT ITS TOTAL IS ISSUED AND REPORTED (OQ-117, CLOSED)
--------------------------------------------------------------------------
⚠ **THIS SECTION PREVIOUSLY SAID OQ-117 WAS OPEN AND THAT THIS FILE SHIPPED ONE
OF ITS TWO READINGS. IT WAS TRUE WHEN WRITTEN AND IT IS NOT TRUE NOW.** The
question was whether a bill that renders its charge lines correctly and then
cannot fill in TOTAL DUE is a *failed* render that BR-BIL-033 must refuse.
Reading (A): it is, and nothing issues until stage 6 stamps the balance-forward
section. Reading (B): the render succeeded and the absence is a stamping gap.

**The PO ruled on 2026-08-12, verbatim: _"issue and report it"_.** Reading (B),
with the half this file did not have. The charge lines are correct and the
customer needs them, so the document is never withheld over the missing total —
and the missing total is raised as a RUN PROBLEM THAT NAMES THE BILL
(`RunProblem`, `_run_problems`, `_report`), not left as a row on an object the
issue path discards. That distinction is the whole content of the change: this
module already issued; what it did not do was tell anybody.

It is the same posture the PO took the same day on OQ-150 — *"print a
substitution"* for a name the page's fonts cannot spell — and both reports
leave by the same door for that reason: **tell somebody, do not withhold the
bill.** Refusing would punish a customer for a gap in our stamping (OQ-117) or
in our font (OQ-150), and BR-BIL-055 wants one named break per bill rather than
a wall across a five-hundred-bill run.

What did NOT change: the figure is still never invented. A bill with an absent
total due is visibly broken and gets fixed; a bill with a plausible total due
fetched from live data is invisibly wrong and does not. The refusals this file
still makes are the ones that make rendering impossible — no pin, no locked
instance, an unrenderable payload version, an unreadable figure.

WHICH STORIES THIS FILE SERVES BUT DOES NOT CITE IN ITS HEADER. US-BIL-029
(stage 6 — this is the *"rendered document"* half of its output contract) and
US-BIL-023 (the delivery queue, which will hand this document to the print
vendor). Neither ships here: no queue row is written and nothing is stored
(BR-BIL-036 requires the rendered document to be STORED, and there is no table
and no blob store — reported in `DOCUMENT_UNAVAILABLE`). G10 reads a
Trace-header US-ID as a claim to ship that story's test cases, so they are
named here instead.
"""

from __future__ import annotations

import hashlib
import html
import logging
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from apps.billing import day_share, models, remittance
from apps.billing.exceptions import BillingRuleError
from apps.rating.pricing import wording
from core import money as core_money

#: Where a run problem goes when nobody is holding the return value. Named as a
#: constant because the tests assert on THIS logger and a rename that broke the
#: report would otherwise leave every assertion green (hard-won law 2).
LOGGER_NAME = "smartbillhub.billing"

logger = logging.getLogger(LOGGER_NAME)

#: BR-BIL-031 — the payload shapes the built-in layout DECLARES it can render.
#: A bill outside this set is refused, not rendered from keys guessed at.
PAYLOAD_VERSIONS: tuple[int, ...] = (1,)

#: The version the one built-in layout is registered under. NOT "the latest" —
#: the render path never asks which version is newest (BR-BIL-026).
BUILT_IN_LAYOUT_VERSION = 1

#: What an unstamped field prints. A visible dash plus a named reason on the
#: result, never a blank that reads as "this customer has no service address".
ABSENT_MARK = "—"

#: The line kinds that group under a SERVICE (A19 §1.4/§1.5), in the order the
#: prototype's residential bill prints them. Fees and taxes get their own
#: groups below, which is both A19 §1.5/§1.6 and what `05-prototype/
#: UtilityBilling.html` shows ("Taxes & fees" as a separate band).
SERVICE_LINE_KINDS = ("base", "usage", "minimum_adjustment")

#: The heading over service lines this document cannot NAME — `DEF-2852`.
#:
#: Two different bills land here and both must print a word rather than an id.
#: A line that names no service at all has always printed under it. A line that
#: DOES name one, on a bill issued before stage 6 began stamping the service's
#: name into the payload, now prints under it too: **the id is never the
#: fallback.** B14 rule 31 (PO 2026-08-30, *"no Databse ID on screen - that is
#: a rule"*), and the PO's own BL-2608-000048 is the bill that proved why — it
#: headed two blocks `Service 01a046d3-090d-7eca-a4ac-87723f3a9e3f` and
#: `Service 01a046d3-091d-7a3e-ad48-76d3a7f9e9d3` where a customer should have
#: read *Water* and *Sewer*.
UNNAMED_SERVICE_HEADING = "Charges this period"

#: What a service with no measured consumption tells the CUSTOMER — `DEF-2863`.
#:
#: ⚠ **THE BILL USED TO PRINT THE CONSTANT ITSELF**: the PO's BL-2608-000048
#: read `sewer   not read this period (tariff_prices_no_consumption)`. Two
#: faults in one string, and the second is the one worth naming. The visible
#: fault is an internal token on a customer's bill (B14 rule 32). The quieter
#: fault is the sentence AROUND it — *not read this period* says something went
#: wrong, and for a sewer service billed as a share of the water usage charge
#: (BR-RAT-015) nothing did: there is no sewer register, and there was never
#: going to be a reading.
#:
#: So each reason gets the sentence that is TRUE of it, rather than a
#: translation of its own name. The values are billing's own
#: (`stages/measure_consumption`) plus the ones metering mints and stage 2
#: forwards verbatim (`apps.metering.selectors.READ_ABSENT_*`) — spelled here
#: rather than imported, for the reason every other copy of these strings is
#: spelled rather than imported, and
#: `tests/test_def_2863_absent_reason_sentences.py` walks BOTH modules'
#: constants so a value added on either side fails there instead of reaching a
#: bill as a token.
#:
#: These are the CUSTOMER's words. The CLERK's are the eleven locale
#: catalogues' `billing.run.reason.*` keys, and they say different things on
#: purpose: *"Standing charge only, for an empty unit"* is work to be judged,
#: and *"no usage billed this period"* is a fact about a bill.
SERVICE_ABSENCE_SENTENCES: dict[str, str] = {
    # BR-CUS-055 — the ACCOUNT bills base and no usage (a vacation hold).
    "base_only_account": "no usage billed this period",
    # DEF-990/1060 — THIS TARIFF bills base and no usage, on an account that
    # bills usage normally. A different fact; the same thing to tell a customer.
    "tariff_bills_base_only": "no usage billed this period",
    # PO 2026-09-30 (fixed-charge case 1), the words ruled: *"Water usage: no
    # reading, billed next bill"* — the service's name is the label beside it.
    "usage_billed_next_bill": "usage: no reading, billed next bill",
    # BR-RAT-015 — sewer is a percentage of the WATER usage charge. It has no
    # register, so it was never unread: it was never metered separately.
    "tariff_prices_no_consumption": "not metered separately, billed from another service",
    # BR-RAT-081 — the utility declared that it does not measure this service.
    "service_not_metered": "not metered, billed at a standing rate",
    # The genuine absences. These ARE work for somebody, and the customer is
    # told plainly which of them happened.
    "no_reading_supplied": "not read this period",
    "no_read": "not read this period",
    "no_meter": "no meter on this service",
    "read_flagged": "the reading for this period is being checked",
    # BR-RAT-090 — an unmetered service billed on a COUNT of its assets, where
    # the count could not be determined. Not a reading, so not "not read".
    "asset_count_unavailable": "not counted this period",
    "asset_count_unit_unstated": "not counted this period",
    # CR-062 D1/H2 — a service billed on the SUM of its installed capacity where
    # the equipment does not record how much capacity it is. The customer is not
    # told about size classes: what they can act on is that the utility does not
    # yet have their equipment on file, and B14 rule 32 keeps internal codes off
    # clerk- and customer-facing copy.
    "installed_capacity_unresolved": "equipment not on file this period",
}

#: What an UNRECOGNISED reason prints. The neutral sentence and NOT the token: a
#: customer who reads one word less has lost nothing, and a customer shown
#: `asset_count_unit_unstated` has been shown our internals. The token is
#: recorded as a named absence instead, so the gap becomes a run report rather
#: than a line on somebody's bill.
UNKNOWN_ABSENCE_SENTENCE = "not read this period"


@dataclass(frozen=True)
class AbsentField:
    """One thing A19 asks the bill to print that the snapshot does not carry.

    Carried on the rendered document rather than logged, because the caller
    that renders is the caller that can act: the S30 document panel can badge
    it, the pre-issue check can count it, and a lane report can list it. A
    warning nobody is handed is a warning nobody reads.
    """

    field: str
    br_ref: str
    detail: str


@dataclass(frozen=True)
class RunProblem:
    """Something wrong with a bill that ISSUED ANYWAY — the PO's *"report it"*.

    OQ-117, CLOSED 2026-08-12: *"issue and report it"*. An `AbsentField` says
    what the SNAPSHOT lacks and is addressed to whoever is reading this one
    document; a `RunProblem` is addressed to the person running the bill run,
    who is not holding the document at all (`issue.py` renders to satisfy
    BR-BIL-033 and throws the result away).

    So it carries three things an absence does not, and each is load-bearing:

      * `invoice_no` / `invoice_id` — **it names the bill.** A report a clerk
        cannot trace to one customer is a statistic.
      * `detail` — a reason and a next step in plain English. A code alone is
        not a report; `total_due_not_printable` tells a clerk nothing about
        what to do on Monday morning.
      * it is EMITTED (`_report`), not merely returned, because the caller that
        would otherwise carry it discards it.
    """

    code: str
    invoice_id: str
    invoice_no: str | None
    br_ref: str
    detail: str


@dataclass(frozen=True)
class DocumentField:
    """A labelled value on the document, already display-formatted."""

    label: str
    value: str
    absent: AbsentField | None = None


@dataclass(frozen=True)
class DocumentLine:
    """One printed charge line, straight from a stored `invoice_lines` row."""

    description: str
    quantity: str
    unit_price: str
    amount: str


@dataclass(frozen=True)
class DocumentGroup:
    """A heading and the lines under it (A19 §1.4 per-service, §1.5, §1.6)."""

    heading: str
    lines: tuple[DocumentLine, ...]
    absent: AbsentField | None = None


@dataclass(frozen=True)
class DocumentUsageMonth:
    """One month on A19 §1.7's twelve-month axis, already display-formatted.

    ⚠ **`absent` IS NOT `quantity == "0"` AND THE TWO MUST NEVER BE CONFLATED**
    (BR-MET-106: *"ABSENT, never 0"*). A month with no stored reading is a
    month nobody measured; a month with a stored 0 is a month somebody measured
    and found no consumption. Drawing the first as a zero bar tells a customer
    their meter read zero, which is a statement about their usage that this
    utility never made.

    `quantity` is the EXACT stored decimal as a string — kept beside the
    display text because a bar's HEIGHT is computed from it and a 2dp display
    string would quantise every bar. It is a quantity and not money, so it
    carries no currency; rule 3 is honoured by `unit` travelling with it.
    """

    label: str
    quantity: str
    quantity_display: str
    unit: str | None
    absent: bool
    #: BR-MET-106 — *"estimates count and are marked"*. A customer looking at a
    #: 628 kWh month is entitled to know part of it was estimated.
    estimated: bool


@dataclass(frozen=True)
class DocumentUsageSeries:
    """One service's twelve months (A19 §1.7), as the frozen snapshot holds it.

    One series per service the account has stored months for — never a summed
    line across services, because kWh and kgal do not add (hard rule 3), and
    never a chip for a service this account does not have.
    """

    heading: str
    unit: str | None
    months: tuple[DocumentUsageMonth, ...]
    months_present: int
    absent: AbsentField | None = None


@dataclass(frozen=True)
class RenderedDocument:
    """The bill as a document — structure first, serialisations second.

    `body` (HTML) and `pdf` (bytes) are TWO SERIALISATIONS OF ONE STRUCTURE:
    both are produced from the same `document` mapping in `render_invoice`,
    neither parses the other, and the pinned template version selects both
    together (`Layout` carries the pair). A later designer preview renders the
    STRUCTURE too rather than parsing either serialisation back apart.

    `absent` and `unavailable` are not decoration. `absent` is what the
    snapshot did not carry (per-bill, varies with the payload); `unavailable`
    is what this module cannot do at all (per-build, the same on every bill).
    Keeping them apart matters: one is fixed by stamping more at issue, the
    other by building something that does not exist yet.

    `pdf_unrepresentable` is a THIRD kind and is neither of those, which is why
    it has its own tuple: the snapshot carried the value and this module can
    render it — the PAGE cannot show it, because the Base-14 fonts encode
    WinAnsi and nothing else. It is per-bill (it depends on the customer's
    name) and it is a defect in the floor, not in the stamp. See OQ-150.

    `problems` is the FOURTH and it is not another kind of absence — it is the
    REPORT the PO ruled on twice on 2026-08-12 (*"issue and report it"* for the
    missing total, *"print a substitution"* for a name the font cannot spell).
    The other three tuples describe the document to whoever is holding it;
    `problems` is addressed to whoever is running the bill run, names the bill,
    and is also emitted on `LOGGER_NAME` because the issue path does not keep
    the document.
    """

    invoice_id: str
    invoice_no: str | None
    template_id: str | None
    template_version: int
    payload_version: int
    layout_source: str
    currency: str
    content_type: str
    body: str
    #: The same document as a printable page (BR-BIL-036's floor). `bytes`, not
    #: `str`: a PDF is a binary container and anything that hands it to a print
    #: vendor, a blob store or an HTTP response wants it in that form.
    pdf: bytes = b""
    pdf_content_type: str = "application/pdf"
    pdf_page_count: int = 0
    masthead: tuple[DocumentField, ...] = ()
    meta: tuple[DocumentField, ...] = ()
    services: tuple[DocumentField, ...] = ()
    groups: tuple[DocumentGroup, ...] = ()
    summary: tuple[DocumentField, ...] = ()
    #: US-BIL-028 — the tenant's own custom fields, as ONE section (PO ruling
    #: 2026-08-12 closing OQ-125/OQ-118). Empty when the tenant defined none;
    #: never a heading over nothing.
    remarks: tuple[DocumentField, ...] = ()
    #: A19 §1.7 — the twelve-month usage block, read from THIS BILL's frozen
    #: `bill_payload.usage_history` and from nothing else (CR-052 task 9).
    #: Empty when the snapshot carries no block, which is every bill issued
    #: before CR-052 task 8 stamped one; never a heading over nothing.
    usage: tuple[DocumentUsageSeries, ...] = ()
    footer: tuple[DocumentField, ...] = ()
    stub: tuple[DocumentField, ...] = ()
    #: `CR-172-BRC10` — the logo this bill was STAMPED with (`bill_payload.
    #: utility_logo`), as both serialisations draw it. None when the bill
    #: carries no stamp (every bill issued before the logo moved to the store)
    #: or the store cannot return it; the bill prints either way.
    logo: "DocumentLogo | None" = None
    absent: tuple[AbsentField, ...] = ()
    pdf_unrepresentable: tuple[AbsentField, ...] = ()
    #: DEF-BIL-10546 — True when `pdf` is the TAGGED page (PDF/UA-1, Liberation
    #: Sans embedded): every draft, so every bill issued from 2026-10-23 on.
    #: False for the re-render of an already-issued bill with no kept original,
    #: which stays on the writer it was printed with (ruled: new bills only).
    pdf_tagged: bool = False
    problems: tuple[RunProblem, ...] = ()
    unavailable: tuple[dict[str, Any], ...] = ()
    #: WHAT the layout named in `layout_source` actually does — `DEF-2826`.
    #:
    #: ⚠ **`layout_source` IS A NAME AND THIS IS THE BEHAVIOUR, AND A READER
    #: NEEDS BOTH.** The S30 viewer had the name since 2026-08-16 and drew every
    #: band unconditionally, so a utility on `compact-letter-v1` was shown a
    #: page that announced compact and looked standard. Nothing on the money was
    #: wrong and no customer received the wrong page — what is posted is the
    #: frozen copy — but the screen exists to show a clerk what a customer will
    #: receive, which is the one thing it could not do.
    #:
    #: `None` only on a document nobody rendered (a hand-built fixture). Every
    #: document `render_invoice` returns carries the spec it rendered on.
    layout: LayoutSpec | None = None


#: What rendering a bill CANNOT do in this build, carried on every document.
#: The `ISSUE_UNAVAILABLE` precedent in `issue.py`: a caller must not have to
#: infer an absence, and a reviewer must not have to take a docstring's word.
DOCUMENT_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "pdf_is_the_print_floor_not_a_designed_template",
        "br_ref": "A19 §1 · BR-BIL-036 · OQ-149",
        "detail": "the PDF is A19 §1's FIELD ORDER typeset on US Letter in the Base-14 "
        "fonts — printable, deterministic, and written by this file with the standard "
        "library so no PDF engine enters the deployment image. It is NOT the tenant's "
        "designed bill: no colour "
        "and no tenant CSS (⚠ `no logo` WAS STRUCK 2026-10-05, CR-172-BRC10: the "
        "letterhead draws the logo the bill was stamped with, from the document store), because `bill_template_versions` holds no designed body to "
        "render. ⚠ THIS SENTENCE READ `no remittance barcode` UNTIL 2026-09-23 AND IS "
        "NOW STRUCK IN FULL (CR-139-BRC07 `P5.10`, then `DEF-BIL-6325`): the stub "
        "carries a Code 39 REMITTANCE LINE with its mod-43 check character, composed by "
        "`apps/billing/remittance.py` from this bill's own frozen payload — account, "
        "bill number and amount in MINOR UNITS, which is what a scanner types into the "
        "Scan source (`P5.8`) — AND, since the PO's *'start putting bar code on bills'*, "
        "the drawn BARS above that line. `PageFill` is the filled-rectangle primitive "
        "that made it possible; `tests/test_def_bil_6325_barcode_round_trip.py` renders "
        "a real bill and DECODES the rectangles back to characters, because *the "
        "function was called* is true of a symbol no scanner can read. A clerk can scan "
        "OUR OWN printed bill. ⚠ WHAT IS STILL ABSENT is the bars on the HTML "
        "serialisation (`DEF-BIL-6340`); the PDF is BR-BIL-036's print floor and is "
        "what a tenant prints. ⚠ THIS SENTENCE ALSO READ `no 12-month usage graph` UNTIL 2026-08-31 "
        "(CR-052 task 9) AND THAT HALF IS NOW FALSE: A19 §1.7's twelve months ARE "
        "printed, as a TABLE of the months frozen on this bill. The PO asked for *'last "
        "12 month consuption table or grpah'*, and a table needs none of the rendering "
        "engine the 2026-08-16 layout ruling keeps out of the deployment image. What is "
        "still absent is a PLOTTED graph, which is why the clause is corrected rather "
        "than simply struck. Paper size is US Letter and is not a tenant choice here — the A19/S91 "
        "Letter-or-A4 option lives on a template that does not exist. OQ-149 is OPEN on "
        "which HTML/CSS engine renders the designed body when it lands, because that "
        "engine (WeasyPrint and its Pango/HarfBuzz system libraries, or a headless "
        "browser) changes the deployment image and is not a lane's call.",
    },
    {
        "code": "pdf_character_repertoire_is_winansi",
        "br_ref": "OQ-150",
        "detail": "the Base-14 fonts are used WITHOUT embedding, so the page can show only "
        "WinAnsi (cp1252) characters. A customer named Nowak or Núñez prints correctly; a "
        "customer named Nowałczyk or 李明 has the characters outside that repertoire "
        "substituted, and every substitution is named per-bill in "
        "`RenderedDocument.pdf_unrepresentable` AND reported as a run problem naming the "
        "bill and the character (`RunProblem`). OQ-150 asked whether it must instead "
        "REFUSE the issue under BR-BIL-033 and the PO CLOSED it on 2026-08-12 — *'print a "
        "substitution'* — the same posture as OQ-117's missing total, ruled the same day. "
        "The HTML serialisation is unaffected; this is a limit of the page, not of the "
        "snapshot.",
    },
    {
        "code": "run_problems_are_logged_and_not_stored",
        "br_ref": "OQ-117 · OQ-150 · BR-BIL-037",
        "detail": "the PO's *'issue and report it'* is honoured with a `RunProblem` on the "
        "rendered document and a WARNING on the `smartbillhub.billing` logger, because "
        "there is nowhere else for it to go: `runs.BlockedAccount` records bills that did "
        "NOT issue, and no table records a problem with a bill that DID. So a run problem "
        "reaches a log and an operator reading it, and does not reach the run summary a "
        "clerk opens on S31. A durable per-bill problem row is owed and is not this "
        "module's to create — reported here rather than left in a comment (hard-won "
        "law 1).",
    },
    {
        "code": "tenant_designs_no_page_of_its_own",
        "br_ref": "BR-BIL-026 · BR-BIL-027 · OQ-149 (CLOSED 2026-08-12/16)",
        "detail": "⚠ CORRECTED 2026-08-16 — this entry read *'`bill_templates` / "
        "`bill_template_versions` do not exist, so the pinned `template_id` resolves to no "
        "stored body'* and that is no longer true, so it is rewritten rather than left "
        "standing (hard-won law 1). The tables exist, every tenant is seeded one at "
        "provisioning (DEF-123), and `_layout_for` now resolves the pinned version ROW and "
        "renders the `layout_key` it stores — so a tenant's CHOICE of layout is honoured "
        "and frozen with the bill. What a tenant still cannot do is DESIGN a page: the PO "
        "ruled on 2026-08-16 that the platform provides ready-made layouts and the tenant "
        "picks one (*'we will ahve 1 default tempalte allways'*), so R2 has no designer, "
        "`LAYOUT_SPECS` is the library, and a key outside it cannot be saved. Colour, logo, "
        "the 12-month usage graph is none of the five layouts' — "
        "it needs a rendering engine the ruling deliberately keeps out. ⚠ THIS ALSO "
        "NAMED `a remittance barcode` UNTIL 2026-09-23: the remittance LINE is now on "
        "every layout whose `stub` switch is on (four of the five; `no-stub-letter-v1` "
        "has no stub to put it on, deliberately), and it needs no engine because it is "
        "text. ⚠ ITS BARS WERE OWED FOR ONE DAY AND ARE NOW DRAWN TOO (`DEF-BIL-6325`), "
        "on the same four layouts and by the same `_barcode_rows` call — still no "
        "engine, because a Code 39 symbol is filled rectangles and this file now has a "
        "primitive that fills one.",
    },
    {
        "code": "document_stored_but_not_handed_to_a_print_vendor",
        "br_ref": "BR-BIL-036 · BR-NOT-027",
        "detail": "⚠ REWRITTEN 2026-08-30 (CR-049 task 4) AND ITS CODE CHANGED, because the "
        "half it named is DONE. It read `document_not_stored` and said *'nothing stores it: "
        "there is no document table and no blob store … a re-render is byte-stable only while "
        "this file is; a stored artifact would be stable forever'*. That was true and is the "
        "defect BR-NOT-027 was ruled on. **Both serialisations of every bill are now frozen at "
        "issue** into tenancy's write-once document store (`apps/billing/frozen_bill.py`), "
        "keeping them is a PRECONDITION of issuing, and `GET /invoices/{id}/document` serves "
        "the kept copy rather than a rebuild. What is STILL owed is the other half of "
        "BR-BIL-036: the print vendor gets nothing from this module. `outbound_messages` "
        "(BR-BIL-016, written at issue since 2026-08-11) pins the template and the dispatcher "
        "renders the letter TEXT at dispatch time; nothing hands it this bill's stored page. "
        "So a bill is kept and is not yet posted.",
    },
)


def _decimal(value: Any) -> Decimal:
    """Money and quantities as Decimal, never float (CLAUDE.md rule 2)."""
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as bad:
        raise BillingRuleError(
            f"a stored figure ({value!r}) on this bill is not a number, so the document "
            "cannot be rendered. Nothing here substitutes a zero: a bill that prints a "
            "zero for a figure it could not read is worse than one that refuses."
        ) from bad


def _money(value: Any, currency: str) -> str:
    """A money figure, rounded to 2dp for DISPLAY only (B4 / BR-RAT-003).

    `core.money.finalize` is the frozen half-up-to-2dp rule, used here at the
    one place B4 permits rounding besides finalization: display. It moves
    nothing in practice — the engine finalizes every line to 2dp already and
    `invoices.total` is their sum (`apps/rating/pricing/stages/assemble.py`),
    so this is idempotent on real data — and it is applied anyway, because a
    figure that arrived at 6dp from anywhere must print as money rather than as
    `100.580000`.

    Nothing rounded here is written back. The stored value keeps its six
    decimals; only the string changes.
    """
    return f"{format(core_money.finalize(_decimal(value)), 'f')} {currency}"


# ⛔ **`_trim` IS GONE, AND THIS COMMENT IS ITS HEADSTONE (2026-08-27).**
#
# It served BOTH a quantity and a unit price, and its docstring was right about
# the unit price and wrong about the quantity:
#
#     "A quantity or a unit price as stored, with trailing zeros dropped.
#      NOT rounded. A unit price is a RATE, not a line amount ... quantizing
#      $0.142000 to $0.14 would print a rate that does not reproduce the line
#      it priced."
#
# Two rulings split it. **DEF-1120:** BR-MET-144 (PO 2026-08-27) puts a QUANTITY
# at *at most two decimals, trailing zeros trimmed*, and this did only the
# trimming — so the printable bill showed `26.2437 kgal` where the reads list
# showed `26.24 kgal`. **OQ-620(a):** the PO ruled a RATE shows *four decimal
# places* with its zeros KEPT — *"A rate is not money and not a quantity"* — so
# `0.142000` prints `0.1420` and `8.290000` prints `8.2900`, where this printed
# `0.142` and `8.29`.
#
# The two rules now round in OPPOSITE directions, so one function cannot serve
# both. It was briefly kept as a thin alias onto `_rate` "in case a call site
# was missed"; it had none, and an alias that silently routes a QUANTITY to the
# RATE rule is dead code carrying a trap — the same reason the IS-9 `PERCENT`
# kind was removed rather than left unused on the day it was written (OQ-621).
# A new call site must pick a side, by name.


def _quantity_text(value: Any) -> str:
    """BR-MET-144 — a quantity at most 2dp, half-up, trailing zeros TRIMMED.

    ⚠ **DELEGATED, NOT RE-DERIVED (DEF-1120, BR-SHL-250 §4).** `billing` may
    import `rating.pricing`, so this is `wording.quantity_text` and not a third
    backend copy of the same rule. The measurement that made this a rule rather
    than a preference: BR-MET-144 was implemented four times on this tree and
    two of the four implemented only half of it, and this file was one of the
    two.
    """
    return wording.quantity_text(value)


def _rate(value: Any) -> str:
    """A unit PRICE: up to 4dp, at least 2 (PO 2026-10-02, narrowing OQ-620(a)).

    ⚠ AMENDED 2026-10-02 — *"Show unit prices with up to 4 decimals and keep
    every total at 2."* `0.042500` prints `0.0425`, `8.290000` prints `8.29`
    (it printed `8.2900` below), `12.5` prints `12.50`. The history below is
    the ceiling's, and the line's `amount` is still `_money`'s two.

    PO 2026-08-27, verbatim: *"What does a tariff rate show? Four ($0.1420). A
    rate is not money and not a quantity - 4 decimal places"*. Same delegation
    as `_quantity_text`, to the same module, for the same reason.

    ⚠ This CHANGES what the printable bill prints, and it is a change the
    ruling makes deliberately: a rate of `0.142000` printed `0.142` here and
    now prints `0.1420`; one of `8.290000` printed `8.29` and now prints
    `8.2900`. **No amount moves** — a unit price is a per-unit rate and the
    line's `amount` is stamped separately by `_money`.
    """
    return wording.rate_text(value)


def _quantity(quantity: Any, unit: Any) -> str:
    """A quantity WITH its unit, or a refusal to print a bare number.

    CLAUDE.md rule 3. `684` on a bill is not checkable by the customer who
    receives it; `684 kWh` is. A line carrying a quantity and no unit is a
    stage-6 refusal already, and if one ever reaches here it prints as an
    explicit absence rather than as a naked figure.
    """
    if quantity is None:
        return ABSENT_MARK
    if not unit:
        return f"{_quantity_text(quantity)} (unit not recorded)"
    return f"{_quantity_text(quantity)} {unit}"


def _field(
    label: str,
    value: Any,
    *,
    br_ref: str = "",
    detail: str = "",
    name: str = "",
) -> DocumentField:
    """A labelled field, or a named absence when the snapshot has no value."""
    if value in (None, ""):
        return DocumentField(
            label=label,
            value=ABSENT_MARK,
            absent=AbsentField(field=name or label, br_ref=br_ref, detail=detail),
        )
    return DocumentField(label=label, value=str(value))


def _pinned(
    invoice: models.Invoice, template_id: Any, template_version: Any
) -> tuple[Any, int]:
    """BR-BIL-026 — the version this bill renders on, and it is not negotiable.

    An ISSUED bill carries its pin and the pin WINS. A caller may pass the same
    values (the issue path does, because it holds them in hand); a caller that
    passes DIFFERENT ones is asking for the thing US-BIL-022 TC-4 says does not
    exist — *"Reprint requested with a 'render on latest' flag → No such option
    exists — pinned version only"* — and is refused rather than obeyed.

    A DRAFT has no pin yet, because the pin is written at issue. That is the
    BR-BIL-033 case: the pre-issue render is handed the pin issue is ABOUT to
    write, so the document that gates the issue is the document the issue
    produces.
    """
    pinned_id = invoice.template_id
    pinned_version = invoice.template_version
    if pinned_version is not None:
        if template_version is not None and int(template_version) != int(
            pinned_version
        ):
            raise BillingRuleError(
                f"bill {invoice.invoice_no or invoice.pk} is pinned to template version "
                f"{pinned_version} and this call asked for version {template_version}. "
                "BR-BIL-026: a reprint renders the pinned version forever — a bill issued "
                "on v3 renders on v3 in 2031 even if v9 is published. There is no "
                "render-on-latest option and this is not one."
            )
        if (
            pinned_id is not None
            and template_id is not None
            and str(template_id) != str(pinned_id)
        ):
            raise BillingRuleError(
                f"bill {invoice.invoice_no or invoice.pk} is pinned to template "
                f"{pinned_id} and this call asked for template {template_id}. The pin is "
                "what makes what the customer was sent reproducible (BR-BIL-026); a "
                "different template is a different document."
            )
        return pinned_id, int(pinned_version)
    if template_version is None:
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} carries no template pin and none was "
            "supplied, so there is no version to render on (BR-BIL-026). An issued bill "
            "always has one; a draft is rendered against the pin its issue is about to "
            "write, which is what BR-BIL-033's pre-issue check passes in."
        )
    return template_id, int(template_version)


def _payload_of(invoice: models.Invoice) -> dict:
    """The stamped instance, or a refusal. BR-BIL-030 / BR-BIL-031.

    Both refusals are the same refusal in different clothes: a document that
    cannot be shown to have come from the locked instance must not be produced,
    because the only alternative source is live master data.
    """
    payload = invoice.bill_payload
    if not isinstance(payload, dict) or not payload:
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} has no locked document instance "
            "(BR-BIL-030), so there is nothing to render it FROM. Rendering it from live "
            "customer, premises and plan rows would print today's facts over a historical "
            "period — the failure the ruling *'keep lock data for that bill'* exists to "
            "prevent."
        )
    version = invoice.payload_version
    if version not in PAYLOAD_VERSIONS:
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} carries payload version {version!r} "
            f"and this layout declares it can render {PAYLOAD_VERSIONS} (BR-BIL-031). The "
            "payload is a DATA contract; rendering an unknown shape prints blanks where "
            "the keys moved, and every one of those blanks is on a customer's bill."
        )
    return payload


def _lines_of(invoice: models.Invoice, lines: Any) -> list[models.InvoiceLine]:
    """The invoice's OWN rows, tenant-scoped by the invoice itself.

    The tenant comes from the invoice row rather than from ambient context, so
    the lines can never belong to another tenant even if the context were wrong
    (CLAUDE.md rule 1; RLS FORCE is the outer guarantee, this is the inner one).

    Ordered by `created_at, id` — the same order `issue.py` stamps GL accounts
    in — so a document renders identically on every re-render. A bill whose
    line order moved between two prints of the same bill would be two
    documents.
    """
    if lines is not None:
        return list(lines)
    return list(
        models.InvoiceLine.objects.filter(
            tenant_id=invoice.tenant_id, invoice=invoice
        ).order_by("created_at", "id")
    )


def _masthead(payload: dict) -> tuple[tuple[DocumentField, ...], list[AbsentField]]:
    """A19 §1.1 — who sent this bill. Nothing tenant-side is stamped."""
    fields = (
        _field(
            "Utility",
            payload.get("utility_name"),
            name="utility_name",
            br_ref="BR-BIL-030",
            detail="A19 §1.1 mastheads the bill with the utility's name; the snapshot "
            "stamps no tenant identity, so the document cannot say who sent it. "
            "BR-BIL-030 lists 'tenant identity and branding reference' as stamped.",
        ),
        _field(
            "Address",
            payload.get("utility_address"),
            name="utility_address",
            br_ref="BR-BIL-030",
            detail="A19 §1.1 utility address — not stamped.",
        ),
        _field(
            "Contact",
            payload.get("utility_contact"),
            name="utility_contact",
            br_ref="BR-BIL-030",
            detail="A19 §1.1 support phone/email — not stamped. The A19 footer also "
            "wants it for 'Questions about your bill?'.",
        ),
    )
    return fields, [f.absent for f in fields if f.absent]


def _meta(
    invoice: models.Invoice, payload: dict
) -> tuple[tuple[DocumentField, ...], list[AbsentField]]:
    """A19 §1.2 — the bill meta band. Account, customer, address, dates."""
    period = payload.get("period") or {}
    fields = (
        _field(
            "Account",
            payload.get("account_no"),
            name="account_no",
            br_ref="BR-BIL-030",
            detail="A19 §1.2 account number — not stamped on this bill.",
        ),
        _field(
            "Customer",
            payload.get("customer_name"),
            name="customer_name",
            br_ref="BR-BIL-030",
            detail="A19 §1.2 customer name — not stamped on this bill. It is NOT read "
            "from the account record: a name changed since issue would print over a "
            "period billed under the old one.",
        ),
        _field(
            "Service address",
            payload.get("service_address"),
            name="service_address",
            br_ref="BR-BIL-030",
            detail="A19 §1.2 service address, walked from the unit's premises and stamped "
            "at draft (DEF-BIL-8283). Absent on a bill issued before that stamp, or when "
            "the premises has no street. BR-BIL-030 names 'service address, premises/unit'.",
        ),
        _field(
            "Unit", payload.get("unit_label"), name="unit_label", br_ref="BR-BIL-030"
        ),
        # DEF-BIL-8283 — where the bill is POSTED: the account's mailing row, or
        # the service address with its unit where it has none (B2 §2). Stamped
        # at draft beside the name; never read live (BR-BIL-030).
        _field(
            "Mailing address",
            payload.get("mailing_address"),
            name="mailing_address",
            br_ref="BR-BIL-030",
            detail="where the bill is posted — stamped at draft since DEF-BIL-8283, so a "
            "bill issued before then does not carry it. It is NOT read from the account "
            "record: an address changed since issue would print over a bill already sent.",
        ),
        # `DEF-BIL-9787` — the account's PO (A19 rule 4's *"PO number … on the
        # commercial bill"*), stamped at draft by stage 6. Drawn only when the
        # bill carries one: most accounts name no PO and that is not a gap.
        *(
            (
                _field(
                    "PO number",
                    payload.get("po_number"),
                    name="po_number",
                    br_ref="BR-BIL-030",
                ),
            )
            if isinstance(payload.get("po_number"), str) and payload["po_number"].strip()
            else ()
        ),
        _field(
            "Bill #",
            invoice.invoice_no,
            name="invoice_no",
            br_ref="BR-BIL-063",
            detail="the number is allocated when the draft is created; a bill with none "
            "cannot be quoted by the customer who receives it.",
        ),
        _field(
            "Cycle",
            payload.get("cycle"),
            name="cycle",
            br_ref="BR-BIL-030",
            detail="A19 §1.2 cycle label — not stamped, and not on the invoice row.",
        ),
        _field(
            "Bill date",
            payload.get("bill_date"),
            name="bill_date",
            br_ref="BR-BIL-024",
            detail="A19 §1.2 bill date. It lives on the cycle (`cycles.bill_date`) and is "
            "what BR-BIL-024 derives the due date FROM, but neither the invoice nor the "
            "snapshot keeps it, so only the derived due date survives on the document.",
        ),
        _field(
            "Due date",
            invoice.due_date.isoformat() if invoice.due_date else None,
            name="due_date",
            br_ref="BR-BIL-024",
            detail="derived at issue from the cycle; a draft has none.",
        ),
        _field(
            "Service period",
            (
                f"{invoice.period_start.isoformat()} – {invoice.period_end.isoformat()}"
                if invoice.period_start and invoice.period_end
                else None
            ),
            name="service_period",
            br_ref="BR-BIL-011",
        ),
        _field(
            "Days",
            period.get("service_days"),
            name="service_days",
            br_ref="BR-BIL-030",
            detail="the prototype's bill prints a day count beside the service period.",
        ),
    )
    return fields, [f.absent for f in fields if f.absent]


def _service_label(entry: Any) -> str | None:
    """The WORD one stamped `bill_payload["services"]` entry stands for.

    `DEF-2852`. Three sources, in this order, and the third is the interesting
    one:

      * `name` — the platform catalogue's own display name, frozen into the
        payload by stage 6 at draft time (BR-BIL-030: the bill carries what it
        was worth on the day it was sent, so a service renamed next year does
        not re-title it).
      * `code`, CAPITALISED — for a payload stamped with an id and no name, and
        for the services band on every bill issued before the name existed.
        ⚠ `.capitalize()` and NOT `.title()`: the catalogue calls `storm_water`
        *Storm water*, so title-casing would invent *Storm Water*, a second
        name for one service.
      * nothing — and the caller prints its own neutral text. **The id is never
        one of the three.** B14 rule 31.
    """
    if not isinstance(entry, dict):
        return None
    name = entry.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    code = entry.get("code")
    if isinstance(code, str) and code.strip():
        return code.strip().replace("_", " ").capitalize()
    return None


def _service_headings(payload: dict) -> dict[str, str]:
    """`{service_id: the word to head its charge block with}` — `DEF-2852`.

    Built from the FROZEN payload and from nothing else, so the map a bill is
    rendered with is the map that bill was stamped with. An entry carrying no
    id contributes nothing: it cannot be matched to a line, and guessing by
    position would head one service's charges with another's name.
    """
    headings: dict[str, str] = {}
    for entry in payload.get("services") or []:
        if not isinstance(entry, dict):
            continue
        service_id = entry.get("id")
        label = _service_label(entry)
        if service_id and label:
            headings[str(service_id)] = label
    return headings


def _services(payload: dict) -> tuple[tuple[DocumentField, ...], list[AbsentField]]:
    """A19 §1.4's per-service header — what was read, and what was not.

    This is the closest the snapshot gets to *"meter {meter_no} · prior
    {prior_read} · current {current_read} · usage {usage} {unit}"*. It carries
    the service code and whether the period was measured or estimated, which is
    genuinely useful — a bill that says *"water: not read this period"* is the
    reason stage 6 stamps this list at all — and it carries none of the three
    figures A19 asks for. Both facts are on the document.
    """
    entries = payload.get("services") or []
    fields: list[DocumentField] = []
    absent: list[AbsentField] = []
    unreadable_reasons: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        label = _service_label(entry) or ABSENT_MARK
        if entry.get("measured"):
            state = "estimated read" if entry.get("estimated") else "read"
        else:
            # ── DEF-2863 · A SENTENCE, NEVER THE CONSTANT ────────────────────
            # This line read `f"not read this period ({reason})"` and put
            # `tariff_prices_no_consumption` on a customer's bill. See
            # SERVICE_ABSENCE_SENTENCES above for why the SENTENCE changed too
            # and not only the token.
            reason = entry.get("absent_reason")
            state = SERVICE_ABSENCE_SENTENCES.get(str(reason) if reason else "", "")
            if not state:
                state = UNKNOWN_ABSENCE_SENTENCE
                unreadable_reasons.append(str(reason) if reason else "(none recorded)")
        fields.append(DocumentField(label=label, value=state))
    if unreadable_reasons:
        absent.append(
            AbsentField(
                field="service_absent_reason",
                br_ref="BR-BIL-015",
                detail="this bill records "
                + ", ".join(sorted(set(unreadable_reasons)))
                + " as the reason a service was not measured, and the document has no "
                "customer sentence for it, so it printed the neutral one. The value is "
                "deliberately NOT printed — B14 rule 32, and DEF-2863 is what it looks "
                "like when it is. The repair is one entry in "
                "documents.SERVICE_ABSENCE_SENTENCES.",
            )
        )
    if entries:
        absent.append(
            AbsentField(
                field="meter_no · prior_read · current_read",
                br_ref="BR-BIL-030",
                detail="A19 §1.4 prints meter number, prior read, current read and usage "
                "with its unit for every service. Stage 2 measures all of them "
                "(`contracts.ServiceReading` carries prior_read / current_read) and stage "
                "6 keeps only whether the service was measured, so the document can say "
                "WHETHER a meter was read and never WHAT it read.",
            )
        )
    else:
        absent.append(
            AbsentField(
                field="services",
                br_ref="BR-BIL-030",
                detail="the snapshot lists no services at all, so the document cannot "
                "name what this bill charges for.",
            )
        )
    return tuple(fields), absent


def _groups(
    lines: list[models.InvoiceLine], currency: str, payload: dict
) -> tuple[tuple[DocumentGroup, ...], list[AbsentField]]:
    """A19 §1.4/§1.5/§1.6 — the charge lines, grouped as the paper groups them.

    Every figure here is `invoice_lines.amount` as stored. Nothing is re-priced
    and nothing is re-summed into a number the customer has not already been
    charged (BR-CUS-040).

    THE GROUPING IS BY `service_id` AND THE HEADING IS THE NAME THE PAYLOAD
    FROZE — `DEF-2852`.

    ⚠ **THIS PARAGRAPH USED TO END *"so a group carrying a service id prints
    the id and names the absence"*, AND THAT WAS THE DEFECT.** Its reasoning
    was right and its conclusion was not. The reasoning: `tenancy.Service` is
    master data, a service renamed after issue would rewrite a historical
    bill's headings, and BR-BIL-030 asks for the grouping to be STAMPED — all
    true, and `test_us_bil_022_documents.py::…tc2` pins this render to two
    queries so a catalogue lookup here fails on the count as well as the rule.
    The conclusion that followed — print the id — put
    `Service 01a046d3-090d-7eca-a4ac-87723f3a9e3f` on a customer's bill where
    the word *Water* belonged, against B14 rule 31 (PO 2026-08-30: *"no
    Databse ID on screen - that is a rule"*).

    **What BR-BIL-030 actually asks for is a STAMP, and the stamp is where the
    fix went**: stage 6 freezes each service's id and display name into
    `bill_payload["services"]`, and this function reads the frozen word. The
    renderer still joins nothing.

    A line whose service this bill cannot NAME — it names no service, or the
    bill was issued before the stamp existed — falls into ONE group headed
    `UNNAMED_SERVICE_HEADING`, and the absence is recorded. Never the id.
    """
    headings = _service_headings(payload)
    #: `None` is the bucket for every service line this bill cannot name. One
    #: bucket and not one per id: two blocks headed identically would tell a
    #: customer nothing and would still be a grouping by an id they cannot see.
    service_lines: dict[Any, list[models.InvoiceLine]] = {}
    group_headings: dict[Any, str] = {}
    unnamed_service_ids: set[str] = set()
    lines_naming_no_service = False
    fee_lines: list[models.InvoiceLine] = []
    tax_lines: list[models.InvoiceLine] = []
    for line in lines:
        if line.kind == "tax":
            tax_lines.append(line)
        elif line.kind in SERVICE_LINE_KINDS:
            key: Any = None if line.service_id is None else str(line.service_id)
            heading = headings.get(key) if key is not None else None
            if heading is None:
                if key is None:
                    lines_naming_no_service = True
                else:
                    unnamed_service_ids.add(key)
                key = None
                heading = UNNAMED_SERVICE_HEADING
            service_lines.setdefault(key, []).append(line)
            group_headings[key] = heading
        else:
            fee_lines.append(line)

    def row(line: models.InvoiceLine) -> DocumentLine:
        # `DEF-BIL-8744` — a line cut down by days says by how many, so the
        # printed `6 kW × $14.0000` foots to its `$53.20`. On the DESCRIPTION,
        # not the Rate cell: that column is 74pt wide and truncates.
        share = day_share.words(day_share.of_stored_line(line))
        description = line.description or ABSENT_MARK
        return DocumentLine(
            description=f"{description} · {share}" if share else description,
            quantity=_quantity(line.quantity, line.unit),
            unit_price=(
                _rate(line.unit_price) if line.unit_price is not None else ABSENT_MARK
            ),
            amount=_money(line.amount, currency),
        )

    #: `DEF-2852` — why this bill could not name a service. Both can be true at
    #: once and both are reported; the GROUP carries the one that explains its
    #: heading, which is the stamp when there was an id to stamp for.
    no_service_absence = AbsentField(
        field="line.service",
        br_ref="BR-BIL-030",
        detail="A19 §1.4 repeats a block PER SERVICE and BR-BIL-030 stamps "
        "'every line grouped by service'. These lines name no service, so "
        "they print under one heading — the same gap that stops a usage "
        "line resolving its GL account at issue.",
    )
    no_name_absence = AbsentField(
        field="service_name",
        br_ref="BR-BIL-030",
        detail="the lines name a service by id and this bill's frozen snapshot carries "
        f"no name for {len(unnamed_service_ids)} of them, so their charges print under "
        "one neutral heading. The name is NOT read from the service catalog — a service "
        "renamed after issue would re-title a historical bill (BR-BIL-030), and the "
        "render is pinned to this bill's own rows. It is stamped at draft time instead "
        "(DEF-2852), so this absence means the bill was issued BEFORE that stamp "
        "existed; every bill issued since carries the name. The id is never printed in "
        "its place (B14 rule 31).",
    )

    groups: list[DocumentGroup] = []
    absent: list[AbsentField] = []
    for service_id, grouped in service_lines.items():
        group_absent: AbsentField | None = None
        if service_id is None:
            group_absent = (
                no_name_absence if unnamed_service_ids else no_service_absence
            )
        groups.append(
            DocumentGroup(
                heading=group_headings[service_id],
                lines=tuple(row(line) for line in grouped),
                absent=group_absent,
            )
        )
        if group_absent is not None:
            absent.append(group_absent)
    if unnamed_service_ids and lines_naming_no_service:
        # Both faults on one bill. The group can only carry one, so the other is
        # reported on its own rather than being lost — the run report is where a
        # gap becomes work, and a gap nobody can see is a gap nobody fixes.
        absent.append(no_service_absence)
    if fee_lines:
        groups.append(
            DocumentGroup(
                heading="Charges & fees", lines=tuple(row(line) for line in fee_lines)
            )
        )
    if tax_lines:
        groups.append(
            DocumentGroup(
                heading="Taxes",
                lines=tuple(row(line) for line in tax_lines),
                absent=AbsentField(
                    field="tax_authority · tax_rate",
                    br_ref="BR-BIL-030",
                    detail="A19 §1.6 prints tax per authority with its rate — "
                    "'{authority} {rate}% {amount}'. The LINE can now name its tax "
                    "(`invoice_lines.tax_id`, BR-BIL-069 — that is what lets it resolve a "
                    "liability account at issue), but the DOCUMENT still cannot print the "
                    "authority's NAME or its rate: the bill is rendered from the locked "
                    "snapshot and never from live rows (BR-BIL-030), and stage 6 stamps "
                    "neither into `bill_payload`. Resolving the name through a live join "
                    "would rewrite an issued document without an UPDATE, which is the one "
                    "thing the lock exists to prevent — so it is REPORTED as absent, and "
                    "the fix is a snapshot field, not a join.",
                ),
            )
        )
        absent.append(groups[-1].absent)
    return tuple(groups), absent


def _summary(
    invoice: models.Invoice, payload: dict, currency: str
) -> tuple[tuple[DocumentField, ...], list[AbsentField]]:
    """A19 §1.3 — the summary box, and the number it cannot print.

    *"Previous balance · Payments/credits · Current charges · **Total due**"*.
    Current charges is `invoices.total` as stored — the engine's totals stage
    sums finalized lines and its own trailer says prior balance is NOT in it,
    so `invoices.total` is this period and nothing else.

    The other three are BR-BIL-035's balance-forward section, which that rule
    requires payload v1 to carry *"whether or not a given tenant renders it"*.

    ⚠ **THIS DOCSTRING USED TO READ "It does not carry them. So TOTAL DUE — the
    largest number on a utility bill and the one the remittance stub exists for
    — is absent." SINCE 2026-08-15 IT DOES CARRY THEM** (DEF-116).
    `issue._stamp_balance_forward` writes `previous_balance`, `payments_credits`
    and `total_due` into `bill_payload` at issue, before this render runs, so
    the page this function returns is the page the customer gets — WE-1's
    **45.00 − 0.00 + 247.87 = 292.87**, printed rather than dashed.

    **THE DASH IS STILL REACHABLE AND IS STILL RIGHT WHEN IT APPEARS.** The
    arrears half is payments' figure and it is asked for through a seam; on a
    deployment where payments publishes nothing the stamp writes NULLS, not
    zeros, and this box says so. Absent is still not assumed equal to current
    charges: that equality holds only for a STANDALONE tenant (BR-BIL-035), the
    standalone / balance-forward setting is not stamped either, and a bill that
    quietly understates what a customer owes by their arrears is a collections
    problem that looks like a rendering nicety.

    ABSENT DOES NOT MEAN SILENT, since the PO closed OQ-117 on 2026-08-12 with
    *"issue and report it"*. A dash printed here is accompanied by a run problem
    naming the bill (`_run_problems`), so the absence is a thing somebody is
    told about rather than a thing a reader of this document might notice. The
    bill still issues: refusing it would withhold correct charge lines from a
    customer over a gap in what the stamp could reach.

    THE STAMPED FIGURES ARE FORMATTED AS MONEY HERE. They are stored as text at
    the column's own six-decimal scale (a Decimal in jsonb reads back a float,
    which CLAUDE.md rule 2 forbids), and `45.000000` is not what a bill prints.
    `_money` is display rounding, which is the one place besides finalization
    that B4 permits it, and it carries the currency with the amount.
    """
    fields = (
        _stamped_money(
            "Previous balance",
            payload.get("previous_balance"),
            currency,
            name="previous_balance",
            detail="BR-BIL-035 stamps the balance-forward figures at issue so a reprint "
            "shows the arrears as they stood on the bill date. This bill carries none — "
            "the arrears are payments' figure and the seam could not be reached. Reported "
            "per bill rather than printed as 0.00, which would tell a customer in arrears "
            "that they are square.",
        ),
        _stamped_money(
            "Payments & credits",
            payload.get("payments_credits"),
            currency,
            name="payments_credits",
            detail="A19 §1.3. Not stamped on this bill — and never queried live, which "
            "would show money received AFTER the bill was sent.",
        ),
        DocumentField(label="Current charges", value=_money(invoice.total, currency)),
        # 🔒 BR-BIL-1061 (PO 2026-10-01) — a payment plan's part not yet due is
        # printed and NOT asked for: $62 + $45 = $107 due, $225 not yet due.
        *(
            (
                DocumentField(
                    label="Payment plan, not yet due",
                    value=_money(-_decimal(payload["plan_not_yet_due"]), currency),
                ),
            )
            if payload.get("plan_not_yet_due") not in (None, "")
            else ()
        ),
        _total_due_field(payload, currency),
    )
    return fields, [f.absent for f in fields if f.absent]


def _total_due_field(payload: dict, currency: str) -> DocumentField:
    """🔒 A19 §1.3's headline — and, since `OQ-217` closed (PO 2026-10-01), a
    customer in CREDIT is told so: *"$48.75 credit, nothing to pay"*. A negative
    stamped total due prints as `0.00` due with the credit beside it, never as a
    negative amount to pay."""
    raw = payload.get("total_due")
    if raw not in (None, ""):
        amount = _decimal(raw)
        if amount < 0:
            return DocumentField(
                label="Total due",
                value=f"{_money(Decimal('0'), currency)} · credit {_money(-amount, currency)}",
            )
    return _stamped_money(
        "Total due",
        payload.get("total_due"),
        currency,
        name="total_due",
        detail="A19 §1.3's headline figure. `invoices.total` is the CURRENT CHARGES; "
        "total due = previous balance − payments + this period (US-BIL-029 §7 works "
        "it as 247.87 + 45.00 = 292.87) and the arrears half could not be read for "
        "this bill. Not assumed equal to current charges: that holds only for a "
        "standalone-format tenant and the format is not stamped either. The bill "
        "ISSUES with the dash and the gap is reported per bill (OQ-117, PO "
        "2026-08-12).",
    )


def _stamped_money(
    label: str, value: Any, currency: str, *, name: str, detail: str
) -> DocumentField:
    """A money figure the payload STAMPED, printed as money — or a named absence.

    One helper for all three of BR-BIL-035's figures so they cannot drift into
    three different formats on one summary box, which is how a customer ends up
    reading `45.000000` beside `247.87 USD` and calling to ask which is real.
    """
    if value in (None, ""):
        return _field(label, None, name=name, br_ref="BR-BIL-035", detail=detail)
    return DocumentField(label=label, value=_money(value, currency))


def _footer(payload: dict) -> tuple[tuple[DocumentField, ...], list[AbsentField]]:
    """A19 §1.8 — messages, ways to pay, and the legal footer."""
    fields = (
        _field(
            "Message",
            payload.get("message"),
            name="message",
            br_ref="BR-BIL-021",
            detail="⚠ REWRITTEN 2026-08-30 (CR-052 task 10). It read *'Neither is "
            "stamped, so the late-fee terms the prototype prints (the greater of $5.00 or "
            "1.5%) do not reach the paper'* and the first clause is no longer true: "
            "`issue._stamp_bill_copy` freezes the PINNED template version's "
            "`options['bill_message']` onto the bill at issue, which is BR-BIL-021's "
            "ratified home for it. This absence now means what it says — **this tenant "
            "has written no bill message.** Nothing here composes one for them: the "
            "late-fee terms are the tenant's words to write (they are charged whether or "
            "not they are printed), and a platform that wrote a customer's disclosure for "
            "them would be inventing legal copy in one language. One edit on the "
            "Templates screen fills it.",
        ),
        _field(
            "Ways to pay",
            payload.get("ways_to_pay"),
            name="ways_to_pay",
            br_ref="BR-BIL-021",
            detail="A19 §1.8 payment methods. Stamped at issue from the pinned template "
            "version's `options['ways_to_pay']` since 2026-08-30 (CR-052 task 10) — this "
            "absence means the tenant has written none, not that the bill cannot carry "
            "them.",
        ),
    )
    # 🔒 DEF-BIL-8248 · PO 2026-09-30, fixed-charge case 5 — *"the next bill
    # says the plan now ends a month later"*. Only on the bill after a skipped
    # instalment (`gather._plan_extended_notice` stamps it then and never
    # otherwise), so no other bill gains a line or an absence.
    notice = payload.get("payment_plan")
    if isinstance(notice, dict) and notice.get("extended_one_month") and notice.get("ends_on"):
        fields = (
            *fields,
            DocumentField(label=PLAN_EXTENDED_LABEL, value=f"Now ends {notice['ends_on']}."),
        )
    # 🔒 DEF-BIL-8243 — *Add to bill*: the due instalment on its own line
    # (`issue._stamp_plan_instalment`). Information about arrears already in
    # the balance forward, never a charge; absent on every other bill.
    instalment = payload.get("payment_plan_instalment")
    if isinstance(instalment, dict) and instalment.get("amount") and instalment.get("due_on"):
        seq = instalment.get("seq")
        fields = (
            *fields,
            DocumentField(
                label=PLAN_EXTENDED_LABEL,
                value=(
                    f"Instalment {seq}: " if seq is not None else "Instalment: "
                )
                + f"{_money(instalment['amount'], instalment.get('currency') or '')} "
                f"due {instalment['due_on']}.",
            ),
        )
    return fields, [f.absent for f in fields if f.absent]


#: The payment-plan line's label (DEF-BIL-8248) — a heading-sized fact, B14
#: rule 33: *Payment plan* · *Now ends 2027-02-15.*
PLAN_EXTENDED_LABEL = "Payment plan"


#: The heading over the ONE section that carries every custom field.
#:
#: **PO ruling 2026-08-12, verbatim** (closing OQ-125 and OQ-118): *"in remark or
#: note section on bill - applicationd eicde the format for time being"*. A19
#: draws no such section — the eight custom-field areas do NOT each get a
#: designed place on the page, and this is the one place they land.
#: What the document calls itself, in the browser tab, in the `<title>` a mail
#: client shows, and set opposite the letterhead on both serialisations. One
#: name, one constant — two serialisations that called it different things
#: would be two documents (see `_pdf_rows`).
TITLE = "Utility bill"

#: The section headings, shared by BOTH serialisations. ⚠ Until 2026-09-07 each
#: one was a string literal typed into `_html_for` and a second string literal
#: typed into `_pdf_rows`, and they had already drifted: the page printed a
#: MESSAGES heading and an AMOUNT DUE heading the markup did not have, and the
#: two spelled the remittance stub differently. Naming them once is what makes
#: *"the printed page and the email do not diverge"* a property rather than a
#: habit (`DEF-BIL-4524`).
HEADING_SERVICES = "Services this period"
HEADING_CHARGES = "Charges this period"
HEADING_SUMMARY = "Amount due"
HEADING_MESSAGES = "Messages"
HEADING_STUB = "Tear off and return with payment"

#: The stub field that carries the remittance line — named ONCE because two
#: places read it: `_stub()` writes the field and `_pdf_flow` draws the BARS
#: above the field with this label. A literal in both would be two literals,
#: and the day one of them changed the bars would simply stop appearing, on a
#: page no test reads (hard-won law 6).
LABEL_SCAN = "Scan"

REMARKS_HEADING = "Remarks & notes"

#: The entity half of a snapshot key, as a word a customer reads. The keys are
#: `<entity>.<key>` (B2 r17.3) and the entity set is `custom_snapshot`'s own
#: `STAMPED_ENTITIES`; an entity outside this map prints its raw prefix rather
#: than being dropped, because a value with a puzzling label is still the
#: tenant's data and a value silently omitted is not.
REMARK_ENTITY_LABELS: dict[str, str] = {
    "accounts": "Account",
    "premises": "Premises",
    "units": "Unit",
}


def _remark_label(key: str) -> str:
    """`account.service_class` → `Account · Service class`.

    DERIVED FROM THE FROZEN KEY, AND NEVER FROM THE REGISTRY, and that is the
    whole design decision in this function. `custom_field_definitions.label` is
    live master data: reading it here would print THIS March's label above LAST
    January's stamped value, which is precisely the live join BR-BIL-030 exists
    to forbid — satisfying DB-4 to the letter (no UPDATE was issued) while
    rewriting an issued document in substance. The key is stamped with the
    value and cannot move, so the label cannot either.

    The cost is stated rather than hidden: a tenant who labels a field "Member
    number" and keys it `member_no` sees **Account · Member no** on the paper.
    That is a worse label and a truthful one. Giving a tenant control of the
    printed label means stamping the label too, which is a schema change and a
    question for the PO, not a lane's call.
    """
    entity, _, field_key = key.partition(".")
    words = field_key.replace("_", " ").strip()
    printed = (words[:1].upper() + words[1:]) if words else key
    return f"{REMARK_ENTITY_LABELS.get(entity, entity)} · {printed}"


def _remarks(invoice: models.Invoice) -> tuple[DocumentField, ...]:
    """A19 has no remark section; the PO made one — US-BIL-028 TC-9.

    Reads `invoices.custom_snapshot` and NOTHING else. That column is stamped at
    draft by `apps/billing/custom_snapshot.py`, the single DB-17 allowlisted
    module, and it holds `dict[str, str]` — display strings, already formatted
    at stamp time under the PO's temporary application-format grant (US-BIL-028
    TC-10: `10432` not `10,432` · `1.5` · ISO `2026-03-04` · `Locked gate, Dog
    on site`). **Nothing here formats, parses or computes**, which is what keeps
    BR-TEN-048 structural: this function cannot turn a custom field into money
    because it never sees a number.

    **ORDER IS BY KEY, and it is not the order the tenant defined the fields
    in.** `custom_snapshot` is a `jsonb` column and PostgreSQL does not preserve
    object key order — it stores keys sorted by length then bytes — so the
    registry order the stamp wrote is already gone by the time anything reads
    the row back. Sorting explicitly is therefore not a choice between two
    available orders; it is the difference between an order this file decides
    and one the storage engine decides. It also groups the entities together,
    since the entity is the key's prefix. A tenant-chosen print order needs the
    order stamped WITH the values, which is a schema change and a PO question.

    An EMPTY snapshot returns `()` and the section is omitted whole — never a
    heading with nothing under it, and never the word "None". A tenant that has
    defined no custom fields has no remarks, and a bill that printed an empty
    Remarks box would invite the question of what was supposed to be in it.

    A snapshot holding a non-string is a bug in the stamp, not something to
    paper over: it is REFUSED here, by name, so a bill that would print
    `{'a': 1}` to a customer never becomes immutable (BR-BIL-033 turns this into
    one named break on one bill, and the rest of the batch issues).
    """
    snapshot = getattr(invoice, "custom_snapshot", None) or {}
    if not isinstance(snapshot, dict):
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} carries a custom-field snapshot of "
            f"type {type(snapshot).__name__}, and B2 r17.3 stores a JSON OBJECT of strings. "
            "The document is refused rather than rendered from a shape nobody stamped."
        )
    fields: list[DocumentField] = []
    for key in sorted(snapshot):
        value = snapshot[key]
        if not isinstance(value, str):
            raise BillingRuleError(
                f"bill {invoice.invoice_no or invoice.pk}: custom field {key!r} holds "
                f"{type(value).__name__} where BR-BIL-030 stores a display STRING. "
                "Nothing is coerced — `str()` on it would print onto a customer's bill "
                "and could never be corrected once the bill is issued."
            )
        fields.append(DocumentField(label=_remark_label(key), value=value))
    return tuple(fields)


#: A19 §1.7's own words are *"Usage graph: 12-month bars (optional)"*. Two
#: words, because rule 33 caps a heading at three and this is a heading.
USAGE_HEADING = "Usage history"


def _usage(payload: dict) -> tuple[tuple[DocumentUsageSeries, ...], list[AbsentField]]:
    """A19 §1.7 — the twelve-month block, from THIS BILL's frozen snapshot.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE ONLY LAWFUL SOURCE IS THE STAMP, AND THAT IS THE WHOLE POINT    ║
    ╚══════════════════════════════════════════════════════════════════════╝
    Reads `payload["usage_history"]` and NOTHING else — no query, no join, no
    clock. `metering_seam.usage_history_for` froze BR-MET-106's stored monthly
    grain onto the bill at issue (CR-052 task 8) with the axis ending at the
    BILL's own period end, so a June bill reprinted in 2033 still draws
    2025-07..2026-06. Reading the account's live usage here instead would be
    exactly the join `BR-BIL-030` forbids and would redraw every historical
    bill from today's data — which is `DEF-2714`'s core finding and the reason
    a frontend could not honestly build this half on its own.

    **THIS IS A PROJECTION, NOT A PASS-THROUGH, AND THE DIFFERENCE IS RULE 31.**
    The stamped block is metering's read model: it carries `account_id` and a
    database `id` on every service, and it carries metrics and a window
    vocabulary that belong to the account screen's filter rather than to a
    printed bill. A bill document publishes the customer's MONTHS — a label, a
    quantity, its unit — and no identifier. So this builds billing's own
    structure from those keys instead of forwarding the dict, which is also
    what keeps `selectors.invoice_detail`'s `budget` exception from becoming a
    habit of opening the payload wherever it is convenient.

    NOTHING RAISES FOR A SHAPE THIS DOES NOT RECOGNISE. A bill issued before
    task 8 has no block at all and simply has no section (the `_remarks`
    posture — never a heading over nothing); a block whose shape is not the one
    metering publishes becomes ONE named absence rather than a refused bill,
    because A19 marks this section OPTIONAL and BR-BIL-055 says a courtesy
    never blocks a bill. The money is the bill; the chart is the courtesy.
    """
    block = payload.get("usage_history")
    if not isinstance(block, dict):
        return (), []
    raw_series = block.get("series")
    if not isinstance(raw_series, list):
        return (), [
            AbsentField(
                field="usage_history",
                br_ref="A19 §1.7 · BR-MET-106",
                detail="this bill's snapshot carries a usage block with no series in it, so "
                "no month can be drawn from it. Nothing is read live to fill the gap "
                "(BR-BIL-030).",
            )
        ]

    series: list[DocumentUsageSeries] = []
    for entry in raw_series:
        if not isinstance(entry, dict):
            continue
        service = entry.get("service")
        heading = ""
        if isinstance(service, dict):
            # The service NAME, never its `id` — B14 rule 31, and a bill is the
            # last place a database key should surface.
            heading = str(service.get("name") or service.get("code") or "")
        if not heading:
            continue
        months: list[DocumentUsageMonth] = []
        present = 0
        for point in entry.get("points") or []:
            if not isinstance(point, dict):
                continue
            absent = bool(point.get("absent"))
            if not absent:
                present += 1
            quantity = point.get("quantity")
            months.append(
                DocumentUsageMonth(
                    label=str(point.get("month") or ""),
                    quantity="" if quantity is None else str(quantity),
                    quantity_display=str(point.get("quantity_display") or ""),
                    unit=(str(point["unit"]) if point.get("unit") else None),
                    absent=absent,
                    estimated=bool(point.get("estimated")),
                )
            )
        if not months:
            continue
        unit_absence = entry.get("unit_absence")
        series.append(
            DocumentUsageSeries(
                heading=heading,
                unit=(str(entry["unit"]) if entry.get("unit") else None),
                months=tuple(months),
                months_present=present,
                # A window whose months disagree about the unit has no single
                # axis and no summable figure (hard rule 3, OQ-358 one level
                # up). Stated on the section rather than silently mixed.
                absent=(
                    AbsentField(
                        field="usage_history.unit",
                        br_ref="A19 §1.7 · OQ-358",
                        detail="the stored months for this service do not agree about their "
                        "unit, so they share no axis and are drawn without one.",
                    )
                    if isinstance(unit_absence, dict)
                    else None
                ),
            )
        )
    return tuple(series), []


def _stub(
    invoice: models.Invoice, payload: dict, summary: tuple[DocumentField, ...]
) -> tuple[DocumentField, ...]:
    """A19 §1.8's remittance stub — `{account_no}`, `{total_due}`, `{due_date}`.

    It reuses the summary's total-due field rather than deriving a second one:
    a stub that disagreed with the box above it is how a customer pays the
    wrong amount.
    """
    total_due = next(f for f in summary if f.label == "Total due")
    fields = [
        DocumentField(
            label="Account", value=str(payload.get("account_no") or ABSENT_MARK)
        ),
        # DEF-BIL-8283 — the torn-off stub names WHO paid as well as which
        # account, from the same frozen name the bill heads with.
        DocumentField(
            label="Customer", value=str(payload.get("customer_name") or ABSENT_MARK)
        ),
        DocumentField(label="Bill #", value=str(invoice.invoice_no or ABSENT_MARK)),
        DocumentField(
            label="Amount due", value=total_due.value, absent=total_due.absent
        ),
        DocumentField(
            label="Due date",
            value=invoice.due_date.isoformat() if invoice.due_date else ABSENT_MARK,
        ),
    ]
    # ── CR-139-BRC07 `P5.10` · THE REMITTANCE LINE ──────────────────────────
    # *"On the three-to-five standard layouts, carrying account, invoice,
    # amount and a check digit. No schema change — it is drawn from the bill's
    # existing payload."*
    #
    # ⚠ **IT IS ON THE STUB AND NOWHERE ELSE ON THE PAGE.** The stub is the
    # part that is torn off and handed over a counter, so it is the only place
    # a scanner will ever be pointed at — and a second copy higher up the sheet
    # would be a second thing to keep in step with this one.
    #
    # ⚠ **`compose_for_invoice` READS THE FROZEN PAYLOAD AND JOINS TO NOTHING**
    # (`BR-BIL-030`). `None` is an honest absence and it gets NO field at all —
    # printing a line with a placeholder in it would produce a perfectly
    # scannable barcode for an account that does not exist.
    #
    # ⚠ **THE BARS ARE NOT DRAWN YET AND THIS IS THE HUMAN-READABLE LINE.**
    # `apps/billing/remittance.py` specifies the symbol in full (`bars()`);
    # what is missing is a filled-rectangle primitive in the PDF writer. It is
    # in the phase 5 board's `P5.10` row and held by a test that goes RED the
    # day one arrives, rather than left as a comment (hard-won law 1).
    #
    # ⚠ **THE AMOUNT IS THE STAMPED `total_due`, NOT `invoices.total`.** They
    # are different figures and the difference is the whole of A19 §1.3:
    # `invoices.total` is THIS PERIOD'S CHARGES, and total due is previous
    # balance − payments + this period. A stub that scanned the current charges
    # would take a payment that leaves the customer in arrears and looks paid.
    # A bill whose snapshot has no `total_due` prints its dash (OQ-117) and
    # gets no line at all, for the same reason.
    line = remittance.compose_for_invoice(payload or {}, invoice_no=invoice.invoice_no)
    if line:
        fields.append(DocumentField(label=LABEL_SCAN, value=line))
    return tuple(fields)


# ═══════════════════════════════════════════════════════════════════════════
# THE PLATFORM'S READY-MADE LAYOUTS — PO ruling 2026-08-16, OQ-149's other half
# ═══════════════════════════════════════════════════════════════════════════
# **THE RULING, VERBATIM:** *"why cant we give 5 differnt tempaltes to start
# with and ask user to choose anyone; we will ahve 1 default tempalte allways"*.
#
# So there is no bill-layout DESIGNER in R2 (S91–S96 are CUT) and the platform
# publishes a small library the tenant chooses from. This section is that
# library, and it is written as ONE renderer plus a `LayoutSpec` rather than as
# five copies of `_html`, for a reason worth stating: five hand-written layouts
# are five places for A19's field ORDER to drift, and a customer holding page
# three of a "compact" bill would have no way to know their neighbour's
# "standard" bill listed the same charges in a different sequence. One flow, five
# switches — every layout emits A19's sections in A19's order or omits one whole.
#
# ⚠ **EVERY SWITCH BELOW CHANGES WHAT IS ON THE PAPER.** `templates_service` had
# it right when it refused to fill the gap with placeholder keys: *"a chooser
# offering four identical options is worse than one offering one honest one."*
# So there is no `theme` string, no colour and no font choice — those would
# render identically in a Base-14 PDF — and each spec removes or moves a whole
# A19 section, which both serialisations show and a test can assert.
@dataclass(frozen=True)
class LayoutSpec:
    """One platform layout, as the switches that make it different.

    `key` is what `bill_template_versions.layout_key` stores and what the pin
    resolves through. It is NOT the version number: two tenants on version 1 of
    their own template can be on different layouts, which is the whole point of
    a chooser, and `_layout_for` therefore reads the pinned VERSION ROW rather
    than counting.
    """

    key: str
    #: A19 §1.1. Suppressed by the letterhead layout, which leaves the space for
    #: pre-printed stationery — the utility's own address is already on the page.
    masthead: bool = True
    #: A19 §1.4's per-service band. The compact layout drops it: on a
    #: single-service bill it repeats the charge group heading underneath it.
    services_band: bool = True
    #: The charge table's Usage and Rate columns. Without them a line is
    #: description + amount, which is what a customer on a flat plan needs and
    #: all a two-line trash bill can honestly fill.
    detail_columns: bool = True
    #: A19 §1.3's summary box ABOVE the charges rather than below them. The
    #: figure most customers are looking for is the amount due.
    summary_first: bool = False
    #: A19 §1.8's remittance stub. A tenant that takes payment by ACH or portal
    #: only is posting a page with a tear-off nobody returns.
    stub: bool = True
    #: Blank rows reserved at the top of the printed page. Only the letterhead
    #: layout uses them, and they exist so the suppressed masthead does not
    #: simply move every line up into the pre-printed area.
    reserve_rows: int = 0


#: The platform's library. FIVE, per the ruling. `standard-letter-v1` is
#: byte-identical to what this module rendered before the library existed —
#: deliberately, because every bill already issued is pinned to a version that
#: resolves to it, and BR-BIL-026 says a reprint renders what was sent.
LAYOUT_SPECS: tuple[LayoutSpec, ...] = (
    LayoutSpec(key="standard-letter-v1"),
    LayoutSpec(
        key="compact-letter-v1",
        services_band=False,
        detail_columns=False,
    ),
    LayoutSpec(key="summary-first-letter-v1", summary_first=True),
    LayoutSpec(key="no-stub-letter-v1", stub=False),
    LayoutSpec(key="letterhead-letter-v1", masthead=False, reserve_rows=6),
)

#: The key a tenant gets when nothing has been chosen, and the key every bill
#: issued before the library existed resolves to. Named, never `LAYOUT_SPECS[0]`
#: by position — a re-ordering of that tuple must not silently repaper a utility.
DEFAULT_LAYOUT_KEY = "standard-letter-v1"


#: ⚠ **THE DOCUMENT'S OWN STYLESHEET, AND IT TRAVELS INSIDE THE DOCUMENT**
#: (`DEF-BIL-4524`, 2026-09-07). Until this constant, `grep -c font-family` over
#: this whole app returned 0: `_html` emitted correct semantic markup and no
#: design at all, so every bill this product has produced was unstyled HTML.
#:
#: **It is inlined rather than linked because of where this page goes.** The
#: document is emailed, printed, and shown in a `srcDoc` iframe with
#: `sandbox=""` (`BillDocumentPage`); a `<link>` reaches none of those. It is
#: also FROZEN at issue (`frozen_bill.py`), and a bill that reprints in 2031 has
#: to carry its own appearance — a stylesheet fetched from a URL is a bill whose
#: look depends on a deployment that may not exist.
#:
#: **The values are the product's, not a second design system** — ink #201e1d,
#: muted #6b6664, hairline #d8d5d3, accent #ec3013, Archivo, from
#: `07-frontend/src/styles/tokens.css` (B14's authority, r10's values). The face
#: falls back to Helvetica/Arial, which is what the PDF sets, so the two
#: serialisations look like each other on a machine with no webfont.
#: `--faint` (an absent value, the stub's dashed rule) is `#6b6767`, the
#: product's grey-600: it was `#97918e`, 3.11:1 on white, and portal a11y
#: Group A decision 8 (PO/QA 2026-10-23) moved it to 5.58:1. The old writer's
#: `FAINT` is left as it was — it prints only re-renders of bills issued
#: before v2.88.0, which Group H ruling 3 keeps exactly as issued.
DOCUMENT_STYLESHEET = """
:root{--ink:#201e1d;--muted:#6b6664;--faint:#6b6767;--hair:#d8d5d3;--accent:#ec3013;--paper:#fff}
@page{size:letter;margin:0.62in}
*{box-sizing:border-box}
body{margin:0;background:#f3f2f2;color:var(--ink);
 font-family:"Archivo","Helvetica Neue",Helvetica,Arial,sans-serif;
 font-size:12px;line-height:1.45;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.bill{max-width:7.3in;margin:0 auto;background:var(--paper);padding:0.62in;
 font-variant-numeric:tabular-nums}
.bill[data-layout-key="letterhead-letter-v1"]{padding-top:1.9in}
.masthead{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;
 border-bottom:2px solid var(--accent);padding-bottom:10px;margin-bottom:18px}
.masthead .utility{margin:0;font-size:20px;font-weight:800;letter-spacing:-.01em;line-height:1.15}
.masthead .brand{display:flex;align-items:flex-start;gap:12px}
.masthead .logo{display:block;max-height:48px;max-width:180px;width:auto;height:auto}
.masthead .utility-line{margin:2px 0 0;font-size:10.5px;color:var(--muted)}
.masthead .kind{margin:2px 0 0;font-size:10.5px;font-weight:700;letter-spacing:.16em;
 text-transform:uppercase;color:var(--accent);text-align:right;white-space:nowrap}
.masthead .kind-no{margin:3px 0 0;font-size:10.5px;color:var(--muted);text-align:right}
.bill[data-layout-key="letterhead-letter-v1"] .masthead{justify-content:flex-end}
section,footer{margin:0 0 14px}
h2{margin:20px 0 6px;padding-bottom:4px;border-bottom:1px solid var(--hair);
 font-size:9px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
table{width:100%;border-collapse:collapse}
caption{caption-side:top;text-align:left;font-weight:700;font-size:12px;padding:8px 0 2px}
.meta th,.services th,.remarks th,.messages th,.stub th{width:1.55in;text-align:left;
 font-weight:400;font-size:10px;color:var(--muted);padding:2px 8px 2px 0;vertical-align:top}
.meta td,.services td,.remarks td,.messages td,.stub td{padding:2px 0;vertical-align:top}
.group thead th{font-size:9px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
 color:var(--muted);text-align:right;padding:3px 0;border-bottom:1px solid var(--hair)}
.group thead th:first-child{text-align:left}
.group td{padding:4px 0;border-bottom:1px solid #eceae8;text-align:right;color:var(--muted)}
.group td:first-child{text-align:left;color:var(--ink);padding-right:12px}
.group td:last-child{color:var(--ink);width:1.1in}
.group th:last-child{width:1.1in}
.summary table{margin-top:10px}
.summary th{text-align:left;font-weight:400;color:var(--muted);padding:2px 0}
.summary td{text-align:right;padding:2px 0}
.summary tr:last-child th,.summary tr:last-child td{border-top:1.5px solid var(--ink);
 padding-top:7px;font-size:15px;font-weight:800;color:var(--ink)}
.usage-series th{font-size:9px;font-weight:700;letter-spacing:.04em;color:var(--muted);
 text-align:right;padding:3px 0 3px 8px}
.usage-series td{text-align:right;padding:3px 0 3px 8px;border-bottom:1px solid #eceae8}
.estimated-note{margin:4px 0 0;font-size:9px;font-style:italic;color:var(--muted)}
.stub{margin-top:26px;border-top:1px dashed var(--faint);padding-top:10px}
.stub h2{margin-top:0;border:0;padding:0}
footer.messages{margin-top:18px}
.absent td,.absent th,p.absent{color:var(--faint)}
@media print{body{background:var(--paper)}.bill{max-width:none;margin:0;padding:0}}
"""


#: The language a bill is WRITTEN in, which is what `<html lang>` and the
#: tagged PDF's `/Lang` must declare (DEF-BIL-10546). Every label this module
#: prints is English (`TITLE`, the headings, `UTILITY BILL`) and no bill has
#: ever been rendered in another language, so `en` is the true answer and not
#: a default. A customer's own name or the utility's own message may be in
#: another language; the document's language is the language of its words.
DOCUMENT_LANGUAGE = "en"


def _logo_alt(masthead: list[DocumentField]) -> str:
    """The logo's text alternative: the utility's stamped name, then "logo".

    A tagged PDF requires every `Figure` to carry `/Alt` (PDF/UA-1 7.3), and
    WeasyPrint takes it from `alt`. The name is the stamped one, never a live
    read (BR-BIL-030); with no name stamped it is just "Utility logo".
    """
    name = masthead[0].value if masthead and not masthead[0].absent else ""
    return f"{name} logo" if name else "Utility logo"


def _barcode_html(line: str) -> str:
    """The Code 39 bars for the remittance line, as DECORATION (`DEF-BIL-10546`).

    The hand-written page draws these as filled rectangles (`_barcode_rows`);
    the tagged page draws the SAME elements, at the SAME X-dimension, as an
    SVG used as a CSS background. A background is an ARTIFACT in a tagged PDF,
    which is right: the bars are a machine-readable copy of the line printed
    directly under them, and a screen reader that announced them would read
    the line twice. `aria-hidden` says the same thing to the HTML's readers.

    No bars at all when `_barcode_x` says the line is too long to draw at the
    minimum width — the same refusal the hand-written page makes.
    """
    import base64

    elements = remittance.bars(line)
    x = _barcode_x(elements)
    if not x:
        return ""
    rects: list[str] = []
    cursor = 0.0
    for is_bar, width in elements:
        span = x * (BARCODE_WIDE if width >= 2 else 1.0)
        if is_bar:
            rects.append(
                f'<rect x="{cursor:.3f}" y="0" width="{span:.3f}" height="{BARCODE_HEIGHT:g}"/>'
            )
        cursor += span
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{cursor:.3f}pt" '
        f'height="{BARCODE_HEIGHT:g}pt" viewBox="0 0 {cursor:.3f} {BARCODE_HEIGHT:g}" '
        f'fill="#000">{"".join(rects)}</svg>'
    )
    data = base64.b64encode(svg.encode("ascii")).decode("ascii")
    return (
        f'<div class="barcode" aria-hidden="true" style="width:{cursor:.3f}pt;'
        f"height:{BARCODE_HEIGHT:g}pt;margin:{BARCODE_PAD:g}pt 0 2pt {BARCODE_QUIET:g}pt;"
        f"background:url(data:image/svg+xml;base64,{data}) no-repeat;"
        f'background-size:100% 100%"></div>'
    )


def _stub_tables(
    stub: tuple[DocumentField, ...], rows: Callable[[tuple[DocumentField, ...]], str]
) -> str:
    """The stub's fields, with the bars ABOVE the scan line as on the page."""
    head = tuple(f for f in stub if f.label != LABEL_SCAN)
    scan = tuple(f for f in stub if f.label == LABEL_SCAN)
    html_out = f"<table>{rows(head)}</table>"
    if scan:
        html_out += _barcode_html(scan[0].value) + f"<table>{rows(scan)}</table>"
    return html_out


def _html_for(spec: LayoutSpec) -> Callable[[dict[str, Any]], str]:
    """Bind one layout's HTML serialiser. See `LayoutSpec` for the switches."""

    def render(document: dict[str, Any]) -> str:
        """The structured document as HTML. Deterministic, escaped, no clock.

        Semantic markup, and — since 2026-09-07 — the DESIGN that goes with it,
        carried in a `<style>` inside the document (`DOCUMENT_STYLESHEET`, and
        `DEF-BIL-4524` for why it is inline). A19's field ORDER is still what
        this has to get right; the stylesheet decides nothing about WHICH fields
        appear, only how they are set. Every value is escaped — a customer name
        is user input and a bill is a document other people open.
        """

        def esc(value: Any) -> str:
            return html.escape(str(value), quote=True)

        def rows(fields: tuple[DocumentField, ...]) -> str:
            return "".join(
                f'<tr class="{"absent" if f.absent else "field"}">'
                # DEF-BIL-10546 — `scope` makes the label the ROW's header, so
                # the tagged PDF (and a screen reader on the HTML) pairs each
                # value with its label instead of reading a grid of cells.
                f'<th scope="row">{esc(f.label)}</th><td>{esc(f.value)}</td></tr>'
                for f in fields
            )

        def summary_section() -> str:
            # A19 §1.3. The heading appears where the PAGE prints one — above
            # the charges, in the layout whose whole point is that the amount
            # due comes first. Under the charges it needs no heading on either
            # serialisation: the figures sit in the charge table's own column.
            heading = f"<h2>{esc(HEADING_SUMMARY)}</h2>" if spec.summary_first else ""
            return (
                f'<section class="summary">{heading}'
                f'<table>{rows(document["summary"])}</table></section>'
            )

        # ⚠ **A LETTERHEAD, NOT A LABELLED BAND (`DEF-BIL-4524`).** This was
        # the same `<th>Utility</th><td>…</td>` table every other section uses,
        # which printed the words *Utility*, *Address* and *Contact* down the
        # left of the page — the Product Owner quoted exactly those three lines
        # back off the running screen. Nobody labels their own letterhead. The
        # labels are suppressed on BOTH serialisations and
        # `test_us_bil_022_tc13` asserts they reach NEITHER, so this cannot
        # drift back into a page that introduces its own name.
        masthead = list(document["masthead"])
        # DEF-BIL-10546 — the document's ONE first-level heading, so the tagged
        # PDF's outline starts at H1 and every section `h2` below it nests.
        kind = '<h1 class="kind">UTILITY BILL</h1>'
        if document["invoice_no"]:
            kind += f'<p class="kind-no">Bill {esc(document["invoice_no"])}</p>'
        parts = [
            f'<!doctype html><html lang="{DOCUMENT_LANGUAGE}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{esc(TITLE)}"
            f'{" " + esc(document["invoice_no"]) if document["invoice_no"] else ""}</title>'
            f"<style>{DOCUMENT_STYLESHEET}</style></head><body>",
            f'<article class="bill" data-layout-key="{esc(spec.key)}"'
            f' data-template-version="{esc(document["template_version"])}"'
            f' data-payload-version="{esc(document["payload_version"])}"'
            f' data-layout-source="{esc(document["layout_source"])}">',
        ]
        if spec.masthead:
            letterhead = "".join(
                f'<p class="{"utility" if index == 0 else "utility-line"}'
                f'{" absent" if field.absent else ""}">{esc(field.value)}</p>'
                for index, field in enumerate(masthead)
            )
            # CR-172-BRC10 — the stamped logo beside the name, as the PNG the
            # page also draws, carried IN the document (a data: URI) so a
            # saved or emailed copy shows it with no request to anybody.
            logo = document.get("logo")
            if logo is not None:
                letterhead = (
                    f'<div class="brand"><img class="logo" alt="{esc(_logo_alt(masthead))}" '
                    f'src="data:image/png;base64,{logo.base64}"><div>{letterhead}</div></div>'
                )
            parts.append(
                f'<header class="masthead"><div>{letterhead}</div><div>{kind}</div></header>'
            )
        else:
            # The letterhead layout leaves the utility's own space empty for its
            # pre-printed stationery. The bill still has to say what it IS.
            parts.append(f'<header class="masthead"><div>{kind}</div></header>')
        parts.append(
            f'<section class="meta"><table>{rows(document["meta"])}</table></section>'
        )
        if spec.summary_first:
            parts.append(summary_section())
        if spec.services_band and document["services"]:
            parts.append(
                f'<section class="services"><h2>{esc(HEADING_SERVICES)}</h2>'
                f'<table>{rows(document["services"])}</table></section>'
            )
        parts.append(f'<section class="charges"><h2>{esc(HEADING_CHARGES)}</h2>')
        for group in document["groups"]:
            head = (
                '<thead><tr><th scope="col">Description</th><th scope="col">Usage</th>'
                '<th scope="col">Rate</th><th scope="col">Amount</th></tr></thead>'
                if spec.detail_columns
                else '<thead><tr><th scope="col">Description</th>'
                '<th scope="col">Amount</th></tr></thead>'
            )
            body = "".join(
                (
                    f"<tr><td>{esc(line.description)}</td><td>{esc(line.quantity)}</td>"
                    f"<td>{esc(line.unit_price)}</td><td>{esc(line.amount)}</td></tr>"
                    if spec.detail_columns
                    else f"<tr><td>{esc(line.description)}</td>"
                    f"<td>{esc(line.amount)}</td></tr>"
                )
                for line in group.lines
            )
            parts.append(
                f'<table class="group"><caption>{esc(group.heading)}</caption>'
                f"{head}<tbody>{body}</tbody></table>"
            )
        parts.append("</section>")
        if not spec.summary_first:
            parts.append(summary_section())
        # US-BIL-028 — the tenant's own fields, in EVERY layout. There is no
        # `remarks: bool` switch on `LayoutSpec` and deliberately so: the other
        # switches drop things this platform draws (a masthead, a rate column, a
        # tear-off stub), and dropping one of those loses nothing a tenant put
        # there. A layout that dropped the remark section would delete the
        # tenant's OWN data from the paper on the strength of a chooser click.
        # Omitted whole when there is nothing to say (see `_remarks`).
        # A19 §1.7 — CR-052 task 9. In EVERY layout and with no `LayoutSpec`
        # switch, for the reason the remarks section has none: the switches drop
        # things the PLATFORM draws, and this is the customer's own consumption
        # record. A TABLE, not a plotted graph — the PO's own words are *"last
        # 12 month consuption table or grpah"*, and a table needs none of the
        # rendering engine the 2026-08-16 ruling keeps out of the image.
        # Omitted whole when the snapshot carries no block.
        if document["usage"]:
            parts.append(f'<section class="usage"><h2>{esc(USAGE_HEADING)}</h2>')
            estimated_seen = False
            for entry in document["usage"]:
                head = "".join(f'<th scope="col">{esc(m.label)}</th>' for m in entry.months)
                body = "".join(
                    # BR-MET-106 — an unmeasured month is ABSENT, never `0`. The
                    # cell carries the state as an attribute so a reader (and a
                    # render check) can tell "no reading" from "read zero".
                    #
                    # ⚠ DEF-BIL-10546 (2026-10-23): the cell now prints the
                    # dash the PAGE has always printed (`_usage_rows`), and an
                    # estimated month carries the page's `*` with the page's
                    # `* estimated` note below. This markup became the input to
                    # the customer's tagged PDF, and it read differently from
                    # the page it replaces — an empty cell and a separate row
                    # of bare `E`s, which a screen reader announces as "blank"
                    # and "E" with nothing to say what E means. The page's
                    # wording was the one a customer already had.
                    f'<td data-absent="{"true" if m.absent else "false"}">'
                    f"{ABSENT_MARK if m.absent else esc(m.quantity_display)}"
                    f"{'*' if (m.estimated and not m.absent) else ''}</td>"
                    for m in entry.months
                )
                if any(m.estimated and not m.absent for m in entry.months):
                    estimated_seen = True
                caption = entry.heading + (f" · {entry.unit}" if entry.unit else "")
                parts.append(
                    f'<table class="usage-series"><caption>{esc(caption)}</caption>'
                    f"<thead><tr>{head}</tr></thead>"
                    f"<tbody><tr>{body}</tr></tbody>"
                    f"</table>"
                )
                if entry.absent is not None:
                    parts.append(f'<p class="absent">{esc(entry.absent.detail)}</p>')
            if estimated_seen:
                parts.append('<p class="estimated-note">* estimated</p>')
            parts.append("</section>")
        if document["remarks"]:
            parts.append(
                f'<section class="remarks"><h2>{esc(REMARKS_HEADING)}</h2>'
                f'<table>{rows(document["remarks"])}</table></section>'
            )
        parts.append(
            f'<footer class="messages"><h2>{esc(HEADING_MESSAGES)}</h2>'
            f'<table>{rows(document["footer"])}</table></footer>'
        )
        if spec.stub:
            parts.append(
                f'<section class="stub"><h2>{esc(HEADING_STUB)}</h2>'
                f"{_stub_tables(document['stub'], rows)}</section>"
            )
        parts.append("</article></body></html>")
        return "".join(parts)

    return render


def _html(document: dict[str, Any]) -> str:
    """The standard layout's HTML — kept as a module-level name because callers
    and tests written before the library existed reach for it, and because
    `standard-letter-v1` must stay the thing every already-issued bill renders
    as (BR-BIL-026)."""
    return _html_for(LAYOUT_SPECS[0])(document)


# ═══════════════════════════════════════════════════════════════════════════
# THE PRINTABLE PAGE (BR-BIL-036's floor) — PDF, standard library only
# ═══════════════════════════════════════════════════════════════════════════
# Everything below writes the SAME `document` mapping `_html` writes, as a
# page. It is the second serialisation of one structure, never a second
# layout: nothing here reads `_html`'s output and nothing there reads this.
#
# WHY IT IS HAND-WRITTEN rather than delegated to a library is argued in the
# module docstring, and the short version is that every candidate either
# changes the deployment image (WeasyPrint's Pango/HarfBuzz), brings its own
# layout language and so its own drift (ReportLab, fpdf2), or both.
#
# DETERMINISM IS THE PROPERTY THIS SECTION EXISTS TO GUARANTEE, and it is the
# reason a hand-written writer is a feature rather than a chore. PDF writers
# routinely stamp `/CreationDate`, `/ModDate` and a random `/ID` into every
# file; two reprints of one bill then differ byte-for-byte while looking
# identical, every test still passes, and the difference is found by whoever
# diffs an archive against a reprint years later. Nothing here reads a clock or
# a random source — there is no `/Info` dictionary at all, and `/ID` is a hash
# of the file's own bytes, so two renders of one bill are the same file and two
# different bills are not. `test_us_bil_022_tc12` asserts it and G6 greps this
# module for a wall clock.

# ── The typeset page ────────────────────────────────────────────────────────
# ⚠ **THIS SECTION USED TO BE COURIER AND SPACE-PADDING, AND THAT IS THE
# DEFECT IT WAS REWRITTEN FOR (`DEF-BIL-4524`, 2026-09-07).** Every column was
# aligned by padding a fixed-pitch string to a character count, which is exact,
# deterministic and needs no font metrics — and which produces a page that
# reads as terminal output. The Product Owner, looking at the bill-layout
# chooser (S8 → Configure → Templates), where each preview frame shows exactly
# these bytes: *"you still gen me like this - I want formated templated not
# like this; we agrred like this"*.
#
# The page is now set in Helvetica, with rules, colour, right-aligned figures
# and real whitespace. Two properties of the old writer are KEPT rather than
# traded away, because both were load-bearing:
#
#   * **DETERMINISM.** No clock, no random source, no `/Info` dates, `/ID` a
#     hash of the file's own bytes. `test_us_bil_022_tc12` still asserts it.
#   * **NO DEPENDENCY.** Still the standard library and nothing else, still the
#     unembedded Base-14 fonts, still no change to the deployment image. OQ-149
#     (a real HTML/CSS engine, for a tenant's OWN designed body) is untouched
#     and still OPEN — this is the PLATFORM's five layouts, typeset.
#
# WHAT PROPORTIONAL TYPE COSTS, AND HOW THAT COST WAS PAID
# --------------------------------------------------------
# Courier's whole appeal here was that a column position is integer arithmetic
# on characters. Helvetica needs an advance-width table, and the module
# docstring's own objection to ReportLab named the risk exactly: *"a font-metric
# table to transcribe and get subtly wrong"*. A table typed in by hand is a
# silent defect — a wrong width for `1` misaligns every money column on every
# bill by a hair, and nothing in this repo reads rendered output (law 6).
#
# **So it was not transcribed. It was MEASURED, from the same Base-14 metrics a
# reader uses**, and the measurement is reproducible: `10-scripts/
# measure_base14_widths.py` writes a probe PDF that draws eight copies of each
# WinAnsi character, reads back the word boxes a PDF text layer reports, and
# divides. Four sample strings then computed to the measured width to the
# hundredth of a point. The script prints exactly the two literals below, so
# the next reader checks them by re-running it rather than by trusting this
# paragraph (law 1).

#: US Letter in PDF user-space units (1/72"). A19 §1 says "letter/A4" and the
#: S91 designer defaulted to "US Letter (8.5 × 11)"; the tenant's choice lives
#: on a template body that does not exist, so this is the default rather than
#: a decision (reported in `DOCUMENT_UNAVAILABLE`).
PAGE_WIDTH = 612
PAGE_HEIGHT = 792
PAGE_MARGIN = 56
#: The right-hand edge every figure on the page is aligned to. A bill is read
#: down its money column, so there is exactly ONE of these.
PAGE_RIGHT = PAGE_WIDTH - PAGE_MARGIN
CONTENT_WIDTH = PAGE_RIGHT - PAGE_MARGIN
#: The page furniture sits below this; the flow never crosses it.
PAGE_FLOOR = 66

#: Type sizes. Restrained on purpose: a bill is a financial document, so the
#: scale is name → total → body → label, and nothing else competes.
SIZE_UTILITY = 15
SIZE_TITLE = 9
SIZE_BODY = 9
SIZE_SMALL = 8
SIZE_LABEL = 7.5
SIZE_SECTION = 7
SIZE_TOTAL = 11
SIZE_FOOT = 7.5

#: The product's own palette (07-frontend/src/styles/tokens.css), not a second
#: one invented for paper: ink #201e1d, muted #6b6664, faint #97918e, hairline
#: #d8d5d3, accent #ec3013. B14's authority, r10's values.
INK = (0.125, 0.118, 0.114)
MUTED = (0.42, 0.40, 0.392)
FAINT = (0.592, 0.569, 0.557)
HAIRLINE = (0.847, 0.835, 0.827)
ACCENT = (0.925, 0.188, 0.075)

#: Fixed-pitch was the old page's alignment mechanism; here it is a typographic
#: choice with one job — a run of digits that must line up under itself.
#: Helvetica's digits are already tabular (every one is 556/1000), so money
#: needs no second face and there is none.
FONT_REGULAR = "F1"
FONT_BOLD = "F2"
FONT_ITALIC = "F3"

#: What a character outside the page's repertoire prints as. Chosen to be
#: visibly wrong: a name that silently loses its diacritics is a name nobody
#: notices is wrong, and this substitution is also NAMED on the result.
UNREPRESENTABLE_MARK = "?"


@dataclass(frozen=True)
class PdfSerialisation:
    """The document as a page, with what the page could not show.

    A plain `bytes` return would have had to lose `unrepresentable`, and the
    only places left to put it would have been a module-level accumulator (not
    thread-safe) or a mutated input mapping (a serialiser that edits its
    source). Both are worse than one small result object.
    """

    data: bytes
    page_count: int
    unrepresentable: tuple[AbsentField, ...] = ()
    #: The characters the page could not encode, deduplicated and sorted. Kept
    #: apart from `unrepresentable`'s prose because OQ-150's ruling asks the run
    #: to name *the bill and the character* — a report that has to regex a
    #: sentence to find the character would break the first time the sentence
    #: is reworded.
    characters: tuple[str, ...] = ()


@dataclass(frozen=True)
class Layout:
    """ONE registered template version's TWO serialisations of one document.

    The pair is deliberately a single registry entry rather than two parallel
    dicts. Two dicts can disagree — a version registered for HTML and missing
    for PDF would render the pinned layout on screen and a stand-in on paper,
    and BR-BIL-026 would be half-kept, which is the same as broken. One entry
    means the pin selects both or neither.
    """

    html: Callable[[dict[str, Any]], str]
    pdf: Callable[[dict[str, Any]], PdfSerialisation]
    #: DEF-BIL-10546 — the TAGGED page (PDF/UA-1) for a document made now. Its
    #: own entry on the same pair, so a version can never be pinned for one
    #: page writer and not the other (the reason this class exists at all).
    tagged_pdf: Callable[[dict[str, Any]], PdfSerialisation] | None = None


def _winansi(text: str) -> tuple[bytes, tuple[str, ...]]:
    """Text as the page can encode it, plus every character it could not.

    The Base-14 fonts are used unembedded, so the repertoire is WinAnsi
    (cp1252): Latin-1 plus the smart quotes, the dashes this file already
    prints (`—` U+2014, `–` U+2013) and the euro sign. A Polish, Czech,
    Turkish, Vietnamese or Chinese name falls outside it.

    Nothing here transliterates. A substituted character is returned as well as
    written, so the caller can NAME it on the document — the same posture the
    rest of this file takes toward a value it cannot honestly print. Control
    characters become spaces: a newline inside a PDF literal string is legal
    and would silently shift the rest of the line.
    """
    encoded = bytearray()
    lost: list[str] = []
    for char in text:
        if ord(char) < 0x20 or ord(char) == 0x7F:
            encoded += b" "
            continue
        try:
            encoded += char.encode("cp1252")
        except UnicodeEncodeError:
            encoded += UNREPRESENTABLE_MARK.encode("ascii")
            lost.append(char)
    return bytes(encoded), tuple(lost)


def _pdf_literal(raw: bytes) -> bytes:
    """A PDF literal string. `(`, `)` and `\\` are the only escapes needed."""
    out = bytearray(b"(")
    for byte in raw:
        if byte in (0x28, 0x29, 0x5C):
            out.append(0x5C)
        out.append(byte)
    out.append(0x29)
    return bytes(out)


def _widths(groups: dict[int, str]) -> dict[str, float]:
    """A width table from `{advance: the characters that have it}`.

    Grouped rather than listed one per line because 216 characters share 28
    widths, and a reader checking `0123456789` are all 556 can see it in one
    line instead of counting ten.
    """
    table: dict[str, float] = {}
    for advance, characters in groups.items():
        for character in characters:
            table[character] = float(advance)
    return table


#: MEASURED, not transcribed — see this section's header and
#: `10-scripts/measure_base14_widths.py`, which prints this literal.
HELVETICA_WIDTHS = _widths(
    {
        191: "'",
        222: "ijl‘’‚",
        260: "|¦",
        278: " !,./:;I[\\]ft·ÌÍÎÏìíîï",
        333: "()-`r¡¨­¯²³´¸¹ˆ˜“”„‹›",
        334: "{}",
        350: "•",
        355: '"',
        365: "º",
        370: "ª",
        389: "*",
        400: "°",
        469: "^",
        500: "Jcksvxyzçýÿšž",
        537: "¶",
        556: "#$0123456789?L_abdeghnopqu¢£¤¥§«µ»àáâãäåèéêëðñòóôõöùúûüþƒ–†€",
        584: "+<=>~¬±×÷",
        611: "FTZ¿ßøŽ",
        667: "&ABEKPSVXYÀÁÂÃÄÅÈÉÊËÝÞŠŸ",
        722: "CDHNRUwÇÐÑÙÚÛÜ",
        737: "©®",
        778: "GOQÒÓÔÕÖØ",
        833: "Mm",
        834: "¼½¾",
        889: "%æ",
        944: "Wœ",
        1000: "ÆŒ—…‰™",
        1015: "@",
    }
)

#: The same measurement for the bold face. It is NOT the regular table with a
#: multiplier — `M` is 833 in both and `A` is 667 against 722, so a guessed
#: ratio misaligns exactly the headings a reader checks first.
HELVETICA_BOLD_WIDTHS = _widths(
    {
        238: "'",
        278: " ,./I\\ijl·ÌÍÎÏìíîï‘’‚",
        280: "|¦",
        333: "!()-:;[]`ft¡¨­¯²³´¸¹ˆ˜‹›",
        350: "•",
        365: "º",
        370: "ª",
        389: "*r{}",
        400: "°",
        474: '"',
        500: "zž“”„",
        556: "#$0123456789J_aceksvxy¢£¤¥§«¶»àáâãäåçèéêëýÿšƒ–†€",
        584: "+<=>^~¬±×÷",
        611: "?FLTZbdghnopquµ¿ßðñòóôõöøùúûüþŽ",
        667: "EPSVXYÈÉÊËÝÞŠŸ",
        722: "&ABCDHKNRUÀÁÂÃÄÅÇÐÑÙÚÛÜ",
        737: "©®",
        778: "GOQwÒÓÔÕÖØ",
        833: "M",
        834: "¼½¾",
        889: "%mæ",
        944: "Wœ",
        975: "@",
        1000: "ÆŒ—…‰™",
    }
)

#: Helvetica-Oblique carries the SAME advances as Helvetica — it is the same
#: outlines sheared — so the italic face needs no third table.
WIDTHS: dict[str, dict[str, float]] = {
    FONT_REGULAR: HELVETICA_WIDTHS,
    FONT_BOLD: HELVETICA_BOLD_WIDTHS,
    FONT_ITALIC: HELVETICA_WIDTHS,
}

#: A character the table has never seen — which after `_winansi` can only be a
#: control code — measures as a digit. It is a fallback, not a guess about
#: typography: it keeps a column from collapsing rather than pretending to be
#: right.
FALLBACK_ADVANCE = 556.0


def text_width(text: str, font: str, size: float, tracking: float = 0.0) -> float:
    """How wide `text` prints, in points. The one measurement on this page.

    Right alignment, centring, wrapping and truncation all resolve to this
    call, so a wrong number here is wrong everywhere at once — which is exactly
    why the tables it reads were measured rather than typed (see the header).
    """
    table = WIDTHS[font]
    total = sum(table.get(character, FALLBACK_ADVANCE) for character in str(text))
    return total * size / 1000.0 + tracking * len(str(text))


@dataclass(frozen=True)
class PageCell:
    """One string, placed. `x` is its LEFT edge, or its RIGHT edge when right-aligned."""

    text: str
    x: float
    font: str = FONT_REGULAR
    size: float = SIZE_BODY
    colour: tuple[float, float, float] = INK
    right: bool = False
    tracking: float = 0.0
    #: Points below the row's own baseline. Lets one row carry a name and the
    #: line under it without inventing a second row kind for every pairing.
    dy: float = 0.0


@dataclass(frozen=True)
class PageRule:
    """A horizontal rule, drawn `dy` points below the row's baseline."""

    x0: float = PAGE_MARGIN
    x1: float = PAGE_RIGHT
    dy: float = 4.0
    weight: float = 0.5
    colour: tuple[float, float, float] = HAIRLINE
    dash: bool = False


@dataclass(frozen=True)
class PageFill:
    """A FILLED RECTANGLE, `dy` points below the row's baseline.

    The page's second drawing primitive, beside `PageRule`'s stroked line, and
    it is deliberately a PRIMITIVE rather than a barcode: a rectangle is what
    the PDF imaging model fills (`re` … `f`), and the first caller wanting one
    happened to be a symbology. A `PageFill` that knew about bars would have to
    be widened again by the next caller — a swatch, a keyline, a solid table
    header — and each widening is a chance to get the geometry wrong somewhere
    a person can see it.

    `x` is the LEFT edge and `dy` is how far below the baseline the rectangle's
    BOTTOM edge sits, so it reads the same way `PageRule.dy` does; the shape
    then grows UPWARDS by `height`. Nothing here knows what a module is.
    """

    x: float
    width: float
    height: float
    dy: float = 0.0
    colour: tuple[float, float, float] = INK


@dataclass(frozen=True)
class PageImage:
    """THE LOGO, placed (`CR-172-BRC10`) — the page's one picture.

    Read the same way as `PageFill`: `x` is the LEFT edge, `dy` is how far
    below the row's baseline the BOTTOM edge sits, and the picture grows
    upwards by `height`. Which picture is not a field: a bill page carries at
    most one image, the utility's logo, and `_pdf_file` names it `/Im1`.
    """

    x: float
    width: float
    height: float
    dy: float = 0.0


@dataclass(frozen=True)
class PageRow:
    """One unit of the flow: what it draws, and how much vertical space it takes.

    Rows are geometry-free ABOVE the page — they carry offsets from their own
    baseline and nothing about where that baseline lands. `_pdf_pages` places
    them and `_pdf_page_stream` draws them, which is what keeps pagination a
    property of the flow rather than something each section has to remember.
    """

    height: float
    cells: tuple[PageCell, ...] = ()
    rules: tuple[PageRule, ...] = ()
    #: Filled rectangles. Drawn BEFORE the cells and the rules, so a solid
    #: block is a background and never a lid over the text on its own row.
    fills: tuple[PageFill, ...] = ()
    #: Pictures — the logo, `CR-172-BRC10`. Drawn first, under everything.
    images: tuple[PageImage, ...] = ()
    #: A run of rows that must not be split across a page break — a group
    #: heading with no lines under it is furniture on the next sheet.
    keep_with_next: int = 0
    #: Space this row is holding OPEN on purpose. ⚠ Without it the letterhead
    #: layout's reserved band was silently dropped: an empty row at the top of a
    #: sheet is normally a gap nobody asked for, and `_pdf_pages` skips one —
    #: which is exactly right for a section gap and exactly wrong for the inch
    #: this layout leaves for the utility's own pre-printed stationery.
    reserved: bool = False
    #: This row and everything after it sit at the FOOT of the page rather than
    #: where the flow happens to have got to. A remittance stub is torn off the
    #: bottom of the sheet; one floating in the middle of the page is a stub the
    #: customer has to cut out with scissors.
    anchor_bottom: bool = False


def _wrap(
    text: str, width: float, font: str = FONT_REGULAR, size: float = SIZE_BODY
) -> list[str]:
    """Break text to `width` POINTS, on spaces where it can.

    ⚠ **THIS TOOK A CHARACTER COUNT UNTIL 2026-09-07 AND NOW TAKES POINTS**
    (`DEF-BIL-4524`). The guarantee is unchanged and is still narrower and
    stricter than `textwrap`'s: never return a line wider than `width` (a long
    unbroken token is hard-split rather than allowed to overrun the margin) and
    never return an empty list, so a caller always has a first line to place.
    """
    if width <= 0:
        return [""]
    lines: list[str] = []
    current = ""

    def fits(candidate: str) -> bool:
        return text_width(candidate, font, size) <= width

    for word in str(text).split():
        while not fits(word):
            cut = len(word)
            while cut > 1 and not fits(word[:cut]):
                cut -= 1
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:cut])
            word = word[cut:]
            if not word:
                break
        if not word:
            continue
        if not current:
            current = word
        elif fits(f"{current} {word}"):
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _truncate(
    text: Any, width: float, font: str = FONT_REGULAR, size: float = SIZE_BODY
) -> str:
    """One cell's text, shortened with an ellipsis rather than allowed to overrun."""
    value = str(text)
    if text_width(value, font, size) <= width:
        return value
    while value and text_width(f"{value}…", font, size) > width:
        value = value[:-1]
    return f"{value}…"


# ── The bill's geometry, in points ──────────────────────────────────────────
#: The charge table. Description wraps; the three figure columns are RIGHT
#: aligned to a fixed edge, which is what makes a bill readable down its money
#: column instead of across its rows.
COL_AMOUNT_RIGHT = PAGE_RIGHT
COL_AMOUNT_WIDTH = 76.0
COL_RATE_RIGHT = COL_AMOUNT_RIGHT - COL_AMOUNT_WIDTH
COL_RATE_WIDTH = 74.0
COL_USAGE_RIGHT = COL_RATE_RIGHT - COL_RATE_WIDTH
COL_USAGE_WIDTH = 76.0
#: The gutter between the description and the first figure column, so a long
#: description never touches a number.
COL_GUTTER = 10.0
COL_DESCRIPTION_WIDTH = COL_USAGE_RIGHT - COL_USAGE_WIDTH - PAGE_MARGIN - COL_GUTTER
#: Without the usage and rate columns (the compact layout) the description gets
#: the space they were using.
COL_DESCRIPTION_WIDE = COL_AMOUNT_RIGHT - COL_AMOUNT_WIDTH - PAGE_MARGIN - COL_GUTTER

#: A label/value band (meta, services, remarks, messages, stub). The label
#: column is narrow and quiet; the value carries the line.
COL_LABEL_WIDTH = 104.0
COL_VALUE_X = PAGE_MARGIN + COL_LABEL_WIDTH
COL_VALUE_WIDTH = PAGE_RIGHT - COL_VALUE_X

#: A19 §1.7's twelve-month strip. Six to a row, each right-aligned in its own
#: column, so a figure sits under its month rather than beside it.
USAGE_MONTHS_PER_ROW = 6
COL_USAGE_MONTH = CONTENT_WIDTH / USAGE_MONTHS_PER_ROW

#: Vertical rhythm. Generous rather than dense: A19 asks for one page and a
#: bill that fits by crowding is a bill nobody reads.
LEAD_BODY = 12.0
LEAD_TIGHT = 10.0
LEAD_SECTION = 15.0
LEAD_GAP = 5.0

#: ⚠ **KEPT AS A NAME BECAUSE `test_us_bil_022_tc13` READS IT.** The anti-drift
#: guard asks that a field's LABEL reaches both serialisations when it is short
#: enough to be printed as one, and it needs a number for "short enough". It is
#: now a point width rather than a character count; the test measures with the
#: same table this page does.
COL_LABEL = COL_LABEL_WIDTH


# ═══════════════════════════════════════════════════════════════════════════
# THE REMITTANCE SYMBOL'S PHYSICAL GEOMETRY — DEF-BIL-6325
# ═══════════════════════════════════════════════════════════════════════════
# `apps/billing/remittance.py::bars()` says WHICH elements the symbol has and
# which of them are wide. Everything below says how WIDE and how TALL they are
# on a US Letter page, which is the half a scanner actually cares about. The
# two are kept apart on purpose: the symbology is a standard and these are a
# page's affordances, and a renderer that re-derived the symbology would be the
# second copy `remittance.py`'s own docstring exists to prevent.
#
# ⚠ **A BARCODE A SCANNER CANNOT READ IS WORSE THAN NO BARCODE**, because the
# clerk has no way to tell the two apart: both end with nothing in the field.
# So each number here is a decision with a reason, not a value that looked
# about right.

#: The NARROW element width — Code 39's X-dimension — in points. 1.0 pt is
#: 1/72 in ≈ **13.9 mil**, comfortably above the 7.5-mil floor the symbology
#: allows and inside the 10–20 mil band a 300/600-dpi office printer renders
#: without rounding a narrow bar into its neighbour's cell. Bigger would scan
#: better still and does not fit: see `_barcode_x` for what happens instead.
BARCODE_X_MAX = 1.0

#: The X-dimension below which we DO NOT DRAW AT ALL. 0.72 pt is **10 mil**.
#: The symbology's own floor is 7.5 mil, and that figure assumes print quality
#: we cannot promise about a tenant's office laser; 10 mil is the width at
#: which a wedge scanner reads a laser-printed Code 39 without ceremony.
#: **Below it the bars are omitted and the human-readable line still prints** —
#: a line a person keys is a working fallback, and a symbol nobody can decode
#: is a control over a door onto nothing (hard-won law 2's mirror).
BARCODE_X_MIN = 0.72

#: WIDE : NARROW. The symbology permits 2.0–3.0, and **2.0 is out of spec at
#: our X-dimension**: below 20 mil the ratio must be at least 2.25, because the
#: printer's ink spread is a fixed absolute amount and it eats a larger share
#: of a narrow element than of a wide one. 2.5 sits in the middle of what is
#: left and costs 12% of the symbol's width against 2.0.
#: ⚠ `bars()` reports a wide element as `2` — that is a MODULE COUNT in the
#: symbology's own terms, not an instruction to draw it at twice the width.
BARCODE_WIDE = 2.5

#: The blank margin either side, in points. 18 pt is **0.25 in**, which is the
#: absolute quiet zone Code 39 asks for and is also ≥ 10 X-dimensions anywhere
#: in the band between `BARCODE_X_MIN` and `BARCODE_X_MAX`. Many scanners do
#: not merely decode worse without it — they do not decode at all, because the
#: quiet zone is how the decoder finds where the symbol starts.
#: ⚠ **HELD INSIDE THE ROW RATHER THAN BORROWED FROM THE PAGE MARGIN.** The
#: 56-pt page margin would satisfy it today, and it would stop doing so the
#: first time somebody put a cell on this row, silently, with every test green.
BARCODE_QUIET = 18.0

#: Bar height in points: 36 pt is **0.5 in**. The symbology's guidance of 15%
#: of the symbol's own length would ask for 65 pt — nearly an inch of stub for
#: a symbol nobody scans at an angle — and its absolute floor is 0.25 in. Half
#: an inch clears that floor by 100% and is what a remittance stub carries.
BARCODE_HEIGHT = 36.0

#: Clear space between the bars and the human-readable line beneath them.
BARCODE_PAD = 4.0

#: PURE BLACK, and the one place on this page that is not `INK`.
#: ⚠ **THIS IS A SCANNING DECISION, NOT A STYLING ONE.** `INK` is a warm dark
#: grey — `(0.125, 0.118, 0.114)`, about 88% black — chosen so a page of text
#: does not glare. A decoder works on the CONTRAST between a bar and the paper
#: behind it, and 12% of it given away for typographic warmth is 12% of the
#: margin that lets a worn print, a photocopy or a fax still decode. The bars
#: are the only marks on this sheet a machine has to read, so they get all of
#: it.
BARCODE_INK = (0.0, 0.0, 0.0)

#: The widest the symbol itself may be, quiet zones already taken out.
BARCODE_SPAN = CONTENT_WIDTH - 2 * BARCODE_QUIET


def _barcode_units(elements: tuple[tuple[bool, int], ...]) -> float:
    """The symbol's width in X-dimensions, summed from the elements themselves.

    ⚠ **SUMMED, NEVER COMPUTED FROM THE CHARACTER COUNT.** The closed form for
    Code 39 is `14.5·L + 28` at this ratio and it is right today; it stops
    being right the moment `bars()` changes anything about its inter-character
    gap, and it would stop being right SILENTLY — the symbol would still draw,
    slightly too wide or too narrow for its box, and nothing but a decode would
    notice. Reading the elements costs one loop and cannot drift from them.
    """
    return sum(BARCODE_WIDE if width >= 2 else 1.0 for _, width in elements)


def _barcode_x(elements: tuple[tuple[bool, int], ...]) -> float:
    """The X-dimension this symbol gets, or `0.0` when it may not be drawn.

    The preferred width, shrunk only as far as the page forces and never below
    `BARCODE_X_MIN`. A line long enough to need less than that gets NO BARS,
    and the caller prints the human-readable line exactly as before.
    """
    units = _barcode_units(elements)
    if units <= 0:
        return 0.0
    x = min(BARCODE_X_MAX, BARCODE_SPAN / units)
    return x if x >= BARCODE_X_MIN else 0.0


def _barcode_rows(line: str) -> list[PageRow]:
    """The drawn Code 39 symbol for `line`, as one row of filled rectangles.

    ⚠ **THE HUMAN-READABLE LINE IS NOT REPLACED BY THIS AND MUST NOT BE.** It
    is what a person keys when no scanner is to hand, what a clerk reads back
    to a customer on the telephone, and the only part of the stub that still
    works when the sheet is folded through the symbol. The bars are drawn ABOVE
    it, which is where Code 39 has always put its own text.

    ⚠ **NO `except RemittanceError` HERE, AND THAT IS DELIBERATE.** Every
    character `bars()` can refuse is a character `remittance._normalise`
    already refused when the line was composed, and `_PATTERNS` carries all 43
    alphabet symbols plus the guard — so the raise is unreachable from a line
    this product printed. An `except` that returned no bars would convert a
    disagreement between the two modules into a bill that quietly prints
    without a symbol, which is the exact silent failure this whole change
    exists to remove.
    """
    elements = remittance.bars(line)
    x = _barcode_x(elements)
    if not x:
        # Law 1: this absence is not a comment claiming a guarantee. It is
        # measured — `test_def_bil_6325_a_line_too_long_to_scan_draws_no_bars`
        # builds a line that cannot fit and asserts the page carries none.
        return []

    fills: list[PageFill] = []
    cursor = PAGE_MARGIN + BARCODE_QUIET
    for is_bar, width in elements:
        span = x * (BARCODE_WIDE if width >= 2 else 1.0)
        if is_bar:
            fills.append(
                PageFill(
                    x=cursor,
                    width=span,
                    height=BARCODE_HEIGHT,
                    dy=-BARCODE_PAD,
                    colour=BARCODE_INK,
                )
            )
        cursor += span
    return [PageRow(BARCODE_HEIGHT + BARCODE_PAD, fills=tuple(fills))]


def _band_rows(
    fields: tuple[DocumentField, ...], *, leading: float = LEAD_BODY
) -> list[PageRow]:
    """A label/value band. The label is quiet, the value carries the line."""
    rows: list[PageRow] = []
    for field in fields:
        lines = _wrap(field.value, COL_VALUE_WIDTH)
        rows.append(
            PageRow(
                leading,
                (
                    PageCell(
                        _truncate(
                            field.label, COL_LABEL_WIDTH - 8, FONT_REGULAR, SIZE_LABEL
                        ),
                        PAGE_MARGIN,
                        FONT_REGULAR,
                        SIZE_LABEL,
                        MUTED,
                    ),
                    PageCell(lines[0], COL_VALUE_X, FONT_REGULAR, SIZE_BODY, INK),
                ),
            )
        )
        for continuation in lines[1:]:
            rows.append(
                PageRow(
                    LEAD_TIGHT,
                    (
                        PageCell(
                            continuation, COL_VALUE_X, FONT_REGULAR, SIZE_BODY, INK
                        ),
                    ),
                )
            )
    return rows


def _section_rows(heading_text: str) -> list[PageRow]:
    """A section heading: small, tracked, quiet, with a hairline under it.

    The heading is the only piece of furniture on the page that repeats, so it
    is the piece that must not shout. B14's own vocabulary for a section label
    — uppercase, tracked, muted — set on paper.
    """
    return [
        PageRow(LEAD_SECTION),
        PageRow(
            LEAD_TIGHT,
            (
                PageCell(
                    heading_text.upper(),
                    PAGE_MARGIN,
                    FONT_BOLD,
                    SIZE_SECTION,
                    MUTED,
                    tracking=0.9,
                ),
            ),
            (PageRule(dy=5.0, weight=0.5, colour=HAIRLINE),),
            keep_with_next=1,
        ),
        PageRow(LEAD_GAP),
    ]


def _charge_rows(document: dict[str, Any], layout: "LayoutSpec") -> list[PageRow]:
    """A19 §1.4/§1.5/§1.6 — the charges, one group at a time.

    Label left, figures right, a hairline between rows, and the group's own
    subtotal-free heading above. The compact layout drops the usage and rate
    columns and gives their space to the description, which is what a flat-rate
    line and a two-line trash bill can honestly fill.
    """
    rows: list[PageRow] = []
    detail = layout.detail_columns
    description_width = COL_DESCRIPTION_WIDTH if detail else COL_DESCRIPTION_WIDE
    for group in document["groups"]:
        rows.append(PageRow(LEAD_GAP))
        rows.append(
            PageRow(
                LEAD_BODY,
                (PageCell(group.heading, PAGE_MARGIN, FONT_BOLD, SIZE_BODY, INK),),
                keep_with_next=2,
            )
        )
        header: list[PageCell] = [
            PageCell(
                "Description", PAGE_MARGIN, FONT_BOLD, SIZE_LABEL, MUTED, tracking=0.5
            )
        ]
        if detail:
            header.append(
                PageCell(
                    "Usage",
                    COL_USAGE_RIGHT,
                    FONT_BOLD,
                    SIZE_LABEL,
                    MUTED,
                    right=True,
                    tracking=0.5,
                )
            )
            header.append(
                PageCell(
                    "Rate",
                    COL_RATE_RIGHT,
                    FONT_BOLD,
                    SIZE_LABEL,
                    MUTED,
                    right=True,
                    tracking=0.5,
                )
            )
        header.append(
            PageCell(
                "Amount",
                COL_AMOUNT_RIGHT,
                FONT_BOLD,
                SIZE_LABEL,
                MUTED,
                right=True,
                tracking=0.5,
            )
        )
        rows.append(
            PageRow(
                LEAD_TIGHT,
                tuple(header),
                (PageRule(dy=4.0, weight=0.6, colour=HAIRLINE),),
                keep_with_next=1,
            )
        )
        for line in group.lines:
            wrapped = _wrap(line.description, description_width)
            cells: list[PageCell] = [PageCell(wrapped[0], PAGE_MARGIN)]
            if detail:
                cells.append(
                    PageCell(
                        _truncate(line.quantity, COL_USAGE_WIDTH),
                        COL_USAGE_RIGHT,
                        right=True,
                        colour=MUTED,
                    )
                )
                cells.append(
                    PageCell(
                        _truncate(line.unit_price, COL_RATE_WIDTH),
                        COL_RATE_RIGHT,
                        right=True,
                        colour=MUTED,
                    )
                )
            cells.append(
                PageCell(
                    _truncate(line.amount, COL_AMOUNT_WIDTH),
                    COL_AMOUNT_RIGHT,
                    right=True,
                )
            )
            rows.append(
                PageRow(
                    LEAD_BODY,
                    tuple(cells),
                    (PageRule(dy=4.0, weight=0.4, colour=HAIRLINE),),
                )
            )
            for continuation in wrapped[1:]:
                rows.append(
                    PageRow(
                        LEAD_TIGHT,
                        (PageCell(continuation, PAGE_MARGIN, colour=MUTED),),
                    )
                )
        # ⚠ **`group.absent` IS NOT PRINTED, AND THE FIRST DRAFT OF THIS
        # REWRITE PRINTED IT (`DEF-BIL-4524`, caught by opening the screen).**
        # An `AbsentField.detail` is addressed to US: it cites A19 §1.6 and
        # BR-BIL-069 and explains why the snapshot carries no tax authority. On
        # a legible page that paragraph landed under the Taxes group **on a
        # customer's bill**, in full, rule ids and all. `_html` has never
        # emitted it, so printing it also broke the one thing this pair exists
        # to keep. The absence still travels on `RenderedDocument.absent` and
        # still reaches the run report; the customer's paper is not where it
        # belongs. (The usage series is different and IS printed: `_html` emits
        # it, so the two agree — see `_usage_rows`.)
    return rows


def _summary_rows(document: dict[str, Any]) -> list[PageRow]:
    """A19 §1.3's summary, in the charge table's OWN amount column.

    The eye runs straight down from a charge to the total it is part of, so the
    figures share one right edge with the lines above them. **Total due** is the
    largest number on a utility bill and is set as such: a heavier rule above
    it, bold, two points up.
    """
    rows: list[PageRow] = [PageRow(LEAD_GAP)]
    for field in document["summary"]:
        total = field.label == "Total due"
        rows.append(
            PageRow(
                LEAD_BODY + (4.0 if total else 0.0),
                (
                    PageCell(
                        field.label,
                        PAGE_MARGIN,
                        FONT_BOLD if total else FONT_REGULAR,
                        SIZE_TOTAL if total else SIZE_BODY,
                        INK if total else MUTED,
                        dy=3.0 if total else 0.0,
                    ),
                    PageCell(
                        field.value,
                        COL_AMOUNT_RIGHT,
                        FONT_BOLD if total else FONT_REGULAR,
                        SIZE_TOTAL if total else SIZE_BODY,
                        INK,
                        right=True,
                        dy=3.0 if total else 0.0,
                    ),
                ),
                (PageRule(dy=-8.0, weight=1.1, colour=INK),) if total else (),
            )
        )
    return rows


def _usage_rows(document: dict[str, Any]) -> list[PageRow]:
    """A19 §1.7's twelve months, six to a row, figure under month."""
    rows: list[PageRow] = []
    estimated_seen = False
    for entry in document["usage"]:
        rows.append(PageRow(LEAD_GAP))
        caption = entry.heading + (f" · {entry.unit}" if entry.unit else "")
        rows.append(
            PageRow(
                LEAD_BODY,
                (PageCell(caption, PAGE_MARGIN, FONT_BOLD, SIZE_BODY, INK),),
                keep_with_next=2,
            )
        )
        months = list(entry.months)
        for start in range(0, len(months), USAGE_MONTHS_PER_ROW):
            chunk = months[start : start + USAGE_MONTHS_PER_ROW]
            labels: list[PageCell] = []
            figures: list[PageCell] = []
            for index, month in enumerate(chunk):
                right = PAGE_MARGIN + COL_USAGE_MONTH * (
                    start % USAGE_MONTHS_PER_ROW + index + 1
                )
                labels.append(
                    PageCell(
                        month.label,
                        right,
                        FONT_BOLD,
                        SIZE_LABEL,
                        MUTED,
                        right=True,
                        tracking=0.4,
                    )
                )
                if month.absent:
                    # BR-MET-106 — ABSENT, never 0. A `0` here would tell a
                    # customer their meter was read and showed no usage.
                    figures.append(
                        PageCell("—", right, FONT_REGULAR, SIZE_BODY, FAINT, right=True)
                    )
                    continue
                text = month.quantity_display
                if month.estimated:
                    estimated_seen = True
                    text = f"{text}*"
                figures.append(
                    PageCell(text, right, FONT_REGULAR, SIZE_BODY, INK, right=True)
                )
            rows.append(PageRow(LEAD_TIGHT, tuple(labels), keep_with_next=1))
            rows.append(
                PageRow(
                    LEAD_BODY,
                    tuple(figures),
                    (PageRule(dy=4.0, weight=0.4, colour=HAIRLINE),),
                )
            )
        if entry.absent is not None:
            for note in _wrap(
                entry.absent.detail, CONTENT_WIDTH, FONT_ITALIC, SIZE_SMALL
            ):
                rows.append(
                    PageRow(
                        LEAD_TIGHT,
                        (PageCell(note, PAGE_MARGIN, FONT_ITALIC, SIZE_SMALL, MUTED),),
                    )
                )
    if estimated_seen:
        rows.append(
            PageRow(
                LEAD_BODY,
                (PageCell("* estimated", PAGE_MARGIN, FONT_ITALIC, SIZE_SMALL, MUTED),),
            )
        )
    return rows


def _pdf_rows(
    document: dict[str, Any], spec: "LayoutSpec | None" = None
) -> list[PageRow]:
    """The whole document as an ordered list of placed rows.

    THE ORDER IS A19 §1's AND IS THE SAME ORDER `_html` EMITS — masthead, meta
    band, services, charge groups, summary box, messages, remittance stub. Two
    serialisations that disagreed about ORDER would be two documents, so the
    two functions are written against the same mapping and
    `test_us_bil_022_tc13` asserts every value on the structure reaches BOTH.

    Rows carry offsets from their own baseline and nothing about where that
    baseline lands; placing them on pages is `_pdf_pages`' job and drawing them
    is `_pdf_page_stream`'s. Keeping the three apart is what makes pagination a
    property of the flow rather than something each section has to remember.
    """
    layout = spec if spec is not None else LAYOUT_SPECS[0]
    rows: list[PageRow] = []

    # The letterhead layout reserves the top of the page for the utility's own
    # pre-printed stationery — blank, because something drawn there prints over
    # the letterhead it was supposed to leave room for.
    if layout.reserve_rows:
        rows.append(PageRow(LEAD_BODY * layout.reserve_rows, reserved=True))

    # A19 §1.1 — the letterhead. THE UTILITY'S NAME, not the word "Utility":
    # the masthead's labels are suppressed on BOTH serialisations, and
    # `test_us_bil_022_tc13` asserts they reach NEITHER, so this cannot drift
    # into a page that labels its own letterhead again.
    kind_cells: list[PageCell] = [
        PageCell(
            "UTILITY BILL",
            PAGE_RIGHT,
            FONT_BOLD,
            SIZE_TITLE,
            ACCENT,
            right=True,
            tracking=1.4,
        )
    ]
    if document["invoice_no"]:
        kind_cells.append(
            PageCell(
                f"Bill {document['invoice_no']}",
                PAGE_RIGHT,
                FONT_REGULAR,
                SIZE_SMALL,
                MUTED,
                right=True,
                dy=13.0,
            )
        )
    #: How far the block on the RIGHT reaches below its own baseline. The accent
    #: rule has to clear it, and on the letterhead layout there is no utility
    #: name on the left to push it down — which is how the rule came to be
    #: struck through the bill number the first time this was drawn.
    kind_depth = max((cell.dy for cell in kind_cells), default=0.0)
    head: list[PageRow] = []
    #: How far the LOGO reaches below the name's baseline (`CR-172-BRC10`).
    logo_depth = 0.0
    if layout.masthead:
        masthead = list(document["masthead"])
        name = masthead[0] if masthead else None
        # CR-172-BRC10 — the stamped logo at the left of the letterhead, its
        # top level with the top of the name, and the name and address moved
        # right of it. The letterhead layout (`masthead=False`) draws none: its
        # top of page is the utility's own pre-printed stationery.
        logo = document.get("logo")
        images: tuple[PageImage, ...] = ()
        text_x = float(PAGE_MARGIN)
        if logo is not None:
            width, height = logo.placed_size()
            logo_depth = height - LOGO_ABOVE_BASELINE
            images = (PageImage(x=PAGE_MARGIN, width=width, height=height, dy=logo_depth),)
            text_x = PAGE_MARGIN + width + LOGO_GAP
        head.append(
            PageRow(
                LEAD_BODY + 8.0,
                tuple(
                    (
                        [PageCell(name.value, text_x, FONT_BOLD, SIZE_UTILITY, INK)]
                        if name
                        else []
                    )
                    + kind_cells
                ),
                images=images,
            )
        )
        for field in masthead[1:]:
            for line in _wrap(
                field.value, CONTENT_WIDTH * 0.6, FONT_REGULAR, SIZE_SMALL
            ):
                head.append(
                    PageRow(
                        LEAD_TIGHT,
                        (PageCell(line, text_x, FONT_REGULAR, SIZE_SMALL, MUTED),),
                    )
                )
    else:
        head.append(PageRow(LEAD_BODY + 8.0, tuple(kind_cells)))
    rows.extend(head)
    # The rule sits below whichever column of the letterhead runs deeper — the
    # utility's address on the left, the bill line on the right, or the logo.
    clearance = max(
        0.0, max(kind_depth, logo_depth) + 6.0 - sum(row.height for row in head[1:])
    )

    # THE RULE. The one piece of colour on the page, and the line the wireframe
    # is built around: everything above it is who sent this, everything below it
    # is what it says.
    rows.append(
        PageRow(
            LEAD_SECTION + clearance,
            (),
            (PageRule(dy=-6.0, weight=1.6, colour=ACCENT),),
        )
    )

    # A19 §1.2 — the bill meta band.
    rows.extend(_band_rows(document["meta"]))

    if layout.summary_first:
        rows.extend(_section_rows(HEADING_SUMMARY))
        rows.extend(_summary_rows(document))

    # A19 §1.4's per-service header, as far as the snapshot carries it.
    if layout.services_band and document["services"]:
        rows.extend(_section_rows(HEADING_SERVICES))
        rows.extend(_band_rows(document["services"]))

    rows.extend(_section_rows(HEADING_CHARGES))
    rows.extend(_charge_rows(document, layout))

    if not layout.summary_first:
        rows.extend(_summary_rows(document))

    # A19 §1.7 — CR-052 task 9, the same section the HTML emits and in the same
    # place in the flow, for the reason this function's docstring gives.
    if document["usage"]:
        rows.extend(_section_rows(USAGE_HEADING))
        rows.extend(_usage_rows(document))

    # US-BIL-028 — the tenant's own fields, in EVERY layout.
    if document["remarks"]:
        rows.extend(_section_rows(REMARKS_HEADING))
        rows.extend(_band_rows(document["remarks"]))

    # A19 §1.8 — messages and ways to pay.
    rows.extend(_section_rows(HEADING_MESSAGES))
    rows.extend(_band_rows(document["footer"]))

    # A19 §1.8 — the remittance stub, below the dashed rule the wireframe cuts
    # along. It is LAST and on the same flow, so a stub can never be printed
    # from figures the customer did not also see above it.
    if layout.stub:
        # ⚠ **BUILT BEFORE THE HEADING, BECAUSE THE HEADING COUNTS THEM.**
        # `keep_with_next` used to be `len(document["stub"])` — the number of
        # FIELDS — which was already one short of the number of ROWS whenever a
        # value wrapped, and the barcode row makes it shorter still. It costs
        # nothing to count the rows that actually exist.
        stub_rows: list[PageRow] = []
        for field in document["stub"]:
            # DEF-BIL-6325 — the bars go ABOVE their own human-readable line,
            # which is where Code 39 puts its text and is why this is a loop
            # rather than one `_band_rows` call.
            if field.label == LABEL_SCAN:
                stub_rows.extend(_barcode_rows(field.value))
            stub_rows.extend(_band_rows((field,), leading=LEAD_TIGHT))
        rows.append(PageRow(LEAD_SECTION + 6.0))
        rows.append(
            PageRow(
                LEAD_BODY,
                (
                    PageCell(
                        HEADING_STUB.upper(),
                        PAGE_MARGIN,
                        FONT_BOLD,
                        SIZE_SECTION,
                        MUTED,
                        tracking=1.0,
                    ),
                ),
                (PageRule(dy=-11.0, weight=0.7, colour=FAINT, dash=True),),
                keep_with_next=len(stub_rows),
                anchor_bottom=True,
            )
        )
        rows.append(PageRow(LEAD_GAP))
        rows.extend(stub_rows)
    return rows


def _pdf_pages(rows: list[PageRow]) -> list[list[tuple[PageRow, float]]]:
    """Break the flow into pages, never opening one with blank space.

    A19 wants a single page and most bills are one; a bill with many services
    is not, and silently dropping its overflow would be the worst possible way
    to keep the promise.

    ⚠ **ROWS NOW HAVE HEIGHTS, SO THE BREAK IS MEASURED RATHER THAN COUNTED**
    (`DEF-BIL-4524`). It also honours `keep_with_next`, which the counted
    version could not express: a section heading alone at the foot of a sheet
    is furniture, and a *Charges this period* whose first line is overleaf reads
    as a page with no charges on it.
    """
    top = PAGE_HEIGHT - PAGE_MARGIN
    pages: list[list[tuple[PageRow, float]]] = []
    page: list[tuple[PageRow, float]] = []
    y = top
    index = 0
    while index < len(rows):
        row = rows[index]
        if row.anchor_bottom:
            # Everything from here down is torn off the bottom of a sheet, so it
            # is placed FROM the floor upwards rather than from wherever the
            # flow reached. It goes on this page if the whole block clears the
            # last row drawn, and on a fresh one otherwise — never half here and
            # half overleaf, because a stub split across two sheets is a stub
            # neither of them carries.
            block = rows[index:]
            needed = sum(item.height for item in block)
            if page and y - needed < PAGE_FLOOR:
                pages.append(page)
                page = []
                y = top
            y = PAGE_FLOOR + needed
            for item in block:
                y -= item.height
                page.append((item, y))
            break
        needed = row.height
        for follower in rows[index + 1 : index + 1 + row.keep_with_next]:
            needed += follower.height
        if page and y - needed < PAGE_FLOOR:
            pages.append(page)
            page = []
            y = top
        if not page and not row.cells and not row.rules and not row.reserved:
            # A gap is the space BETWEEN two things; at the top of a sheet it is
            # a margin nobody asked for. A RESERVED band is the opposite — it is
            # the whole point of the letterhead layout — so it is kept.
            index += 1
            continue
        y -= row.height
        page.append((row, y))
        index += 1
    pages.append(page)
    return pages


def _pdf_page_stream(
    placed: list[tuple[PageRow, float]], *, page_no: int, page_count: int, footer: str
) -> tuple[bytes, tuple[str, ...]]:
    """One page's content stream, plus every character it could not encode."""
    ops = bytearray()
    lost: list[str] = []

    def show(cell: PageCell, baseline: float) -> None:
        encoded, missing = _winansi(cell.text)
        lost.extend(missing)
        if not encoded:
            return
        width = text_width(cell.text, cell.font, cell.size, cell.tracking)
        x = cell.x - width if cell.right else cell.x
        red, green, blue = cell.colour
        ops.extend(b"BT %s rg\n" % _pdf_number3(red, green, blue))
        if cell.tracking:
            ops.extend(b"%s Tc\n" % _pdf_number(cell.tracking))
        ops.extend(
            b"/%s %s Tf %s %s Td %s Tj\n"
            % (
                cell.font.encode("ascii"),
                _pdf_number(cell.size),
                _pdf_number(x),
                _pdf_number(baseline - cell.dy),
                _pdf_literal(encoded),
            )
        )
        if cell.tracking:
            ops.extend(b"0 Tc\n")
        ops.extend(b"ET\n")

    def stroke(rule: PageRule, baseline: float) -> None:
        red, green, blue = rule.colour
        y = baseline - rule.dy
        ops.extend(
            b"%s RG %s w\n" % (_pdf_number3(red, green, blue), _pdf_number(rule.weight))
        )
        if rule.dash:
            ops.extend(b"[4 3] 0 d\n")
        ops.extend(
            b"%s %s m %s %s l S\n"
            % (
                _pdf_number(rule.x0),
                _pdf_number(y),
                _pdf_number(rule.x1),
                _pdf_number(y),
            )
        )
        if rule.dash:
            ops.extend(b"[] 0 d\n")

    def fill(box: PageFill, baseline: float) -> None:
        """One filled rectangle — `rg` is the NON-stroking colour, `f` fills it.

        ⚠ **`rg` AND NOT `RG`, WHICH IS THE ONE WAY TO GET THIS SILENTLY
        WRONG.** `stroke()` above sets `RG`, the STROKING colour, because it
        ends in `S`. A fill takes its paint from the non-stroking colour, so a
        rectangle emitted after a `RG` and filled with `f` comes out in
        whatever `rg` was last set to — which on this page is the colour of the
        last piece of text drawn. The symbol would still be a symbol and would
        still be the right shape; it would simply be the wrong ink, and on a
        muted label colour a scanner's contrast margin goes with it.

        `show()` sets its own `rg` inside every `BT`/`ET`, so the state this
        leaves behind cannot reach a later cell.
        """
        red, green, blue = box.colour
        ops.extend(
            b"%s rg %s %s %s %s re f\n"
            % (
                _pdf_number3(red, green, blue),
                _pdf_number(box.x),
                _pdf_number(baseline - box.dy),
                _pdf_number(box.width),
                _pdf_number(box.height),
            )
        )

    for row, baseline in placed:
        for picture in row.images:
            # CR-172-BRC10 — `cm` scales the unit square the image occupies to
            # its placed size; `q`/`Q` keep that transform off everything after.
            ops.extend(
                b"q %s 0 0 %s %s %s cm /Im1 Do Q\n"
                % (
                    _pdf_number(picture.width),
                    _pdf_number(picture.height),
                    _pdf_number(picture.x),
                    _pdf_number(baseline - picture.dy),
                )
            )
        for box in row.fills:
            fill(box, baseline)
        for rule in row.rules:
            stroke(rule, baseline)
        for cell in row.cells:
            show(cell, baseline)

    # The page furniture: a hairline, the bill it belongs to, and which sheet
    # of how many. A loose sheet off a print run has to say what it is.
    ops.extend(
        b"%s RG 0.4 w %s %s m %s %s l S\n"
        % (
            _pdf_number3(*HAIRLINE),
            _pdf_number(PAGE_MARGIN),
            _pdf_number(PAGE_FLOOR - 14),
            _pdf_number(PAGE_RIGHT),
            _pdf_number(PAGE_FLOOR - 14),
        )
    )
    show(PageCell(footer, PAGE_MARGIN, FONT_REGULAR, SIZE_FOOT, FAINT), PAGE_FLOOR - 26)
    show(
        PageCell(
            f"Page {page_no} of {page_count}",
            PAGE_RIGHT,
            FONT_REGULAR,
            SIZE_FOOT,
            FAINT,
            right=True,
        ),
        PAGE_FLOOR - 26,
    )
    return bytes(ops), tuple(lost)


def _pdf_number(value: float) -> bytes:
    """A PDF real, formatted the SAME WAY every time.

    Two decimals and no exponent, because `repr` of a float is
    platform-and-value dependent and `test_us_bil_022_tc12` asserts two renders
    of one bill are byte-identical. A hundredth of a point is a five-thousandth
    of a millimetre; nothing on this page needs more and determinism needs the
    formatting to be a decision rather than an accident.
    """
    text = f"{value:.2f}"
    if text == "-0.00":
        text = "0.00"
    return text.encode("ascii")


def _pdf_number3(red: float, green: float, blue: float) -> bytes:
    """One colour, as the three PDF reals a `rg`/`RG` operator takes."""
    return b"%s %s %s" % (_pdf_number(red), _pdf_number(green), _pdf_number(blue))


def _pdf_file(streams: list[bytes], page_count: int, logo: "DocumentLogo | None" = None) -> bytes:
    """The PDF container: catalog, page tree, fonts, pages, xref, trailer.

    NO `/Info` DICTIONARY, so there is no `/CreationDate` and no `/ModDate` to
    make two reprints differ; `/ID` is a hash of the file's own body, so it is
    reproducible AND still does what `/ID` is for — two renders of one bill
    share it and two different bills do not. Object numbers are assigned in a
    fixed order and the streams are uncompressed, which also makes a diff of
    two PDFs readable by a human deciding whether a change was intended.

    ⚠ **THE THREE FONTS ARE HELVETICA AND NOT COURIER SINCE 2026-09-07**
    (`DEF-BIL-4524`). Still Base-14, so still unembedded and still no change to
    the deployment image; `WIDTHS` above is what replaced fixed pitch as the
    alignment mechanism.
    """
    first_page = 6
    first_stream = first_page + page_count
    # CR-172-BRC10 — the logo, when there is one: an image XObject (and its
    # alpha as a soft mask) numbered AFTER the content streams, so every object
    # number a bill without a logo has is unchanged.
    image_no = first_stream + page_count
    mask_no = image_no + 1
    xobjects = b" /XObject << /Im1 %d 0 R >>" % image_no if logo is not None else b""
    kids = " ".join(f"{first_page + i} 0 R" for i in range(page_count))
    bodies: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids.encode("ascii"), page_count),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
        b"/Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique "
        b"/Encoding /WinAnsiEncoding >>",
    ]
    for index in range(page_count):
        bodies.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << "
            b"/F1 3 0 R /F2 4 0 R /F3 5 0 R >>%s >> /Contents %d 0 R >>"
            % (PAGE_WIDTH, PAGE_HEIGHT, xobjects, first_stream + index)
        )
    for stream in streams:
        bodies.append(
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream)
        )
    if logo is not None:
        smask = b" /SMask %d 0 R" % mask_no if logo.alpha is not None else b""
        bodies.append(
            b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
            b"/BitsPerComponent 8 /Filter /FlateDecode%s /Length %d >>\nstream\n%s\nendstream"
            % (logo.width, logo.height, smask, len(logo.rgb), logo.rgb)
        )
        if logo.alpha is not None:
            bodies.append(
                b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceGray "
                b"/BitsPerComponent 8 /Filter /FlateDecode /Length %d >>\nstream\n%s\nendstream"
                % (logo.width, logo.height, len(logo.alpha), logo.alpha)
            )

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for number, body in enumerate(bodies, start=1):
        offsets.append(len(out))
        out.extend(b"%d 0 obj\n%s\nendobj\n" % (number, body))
    xref_at = len(out)
    out.extend(b"xref\n0 %d\n0000000000 65535 f \n" % (len(bodies) + 1))
    for offset in offsets:
        out.extend(b"%010d 00000 n \n" % offset)
    file_id = hashlib.sha256(bytes(out)).hexdigest()[:32].upper().encode("ascii")
    out.extend(
        b"trailer\n<< /Size %d /Root 1 0 R /ID [<%s> <%s>] >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(bodies) + 1, file_id, file_id, xref_at)
    )
    return bytes(out)


def _pdf_for(spec: LayoutSpec) -> Callable[[dict[str, Any]], PdfSerialisation]:
    """Bind one layout's PDF serialiser. Same switches, same flow, same order."""

    def render(document: dict[str, Any]) -> PdfSerialisation:
        return _pdf(document, spec)

    return render


def _tagged_pdf_for(spec: LayoutSpec) -> Callable[[dict[str, Any]], PdfSerialisation]:
    """Bind one layout's TAGGED PDF serialiser — `DEF-BIL-10546`, Group H.

    The page a customer receives from 2026-10-23 on (PO/QA ruling, decision log
    *"Portal accessibility, Group H"*): this layout's OWN HTML serialisation,
    turned into a PDF/UA-1 file by `core.tagged_pdf` (WeasyPrint, Liberation
    Sans embedded). It is not a third layout — it reads `_html_for(spec)`'s
    output and nothing else, so the screen copy and the paper copy are the
    same markup and cannot drift apart.

    The hand-written `_pdf` above is KEPT, for two reasons, both ruled: an
    already-issued bill that has no kept original is re-rendered on the writer
    it was printed with (*"New bills only. The old ones stay as issued"* — no
    accessible copy of an old bill is generated), and the parity test proves
    the tagged page says what that writer said, figure for figure.
    """
    html_of = _html_for(spec)

    def render(document: dict[str, Any]) -> PdfSerialisation:
        from core import tagged_pdf

        # The same page furniture `_pdf` draws: the bill number, and Page n of N.
        printed = tagged_pdf.render(
            html_of(document), footer=f"Bill {document['invoice_no'] or ABSENT_MARK}"
        )
        unrepresentable: tuple[AbsentField, ...] = ()
        if printed.characters:
            unrepresentable = (
                AbsentField(
                    field="pdf_text",
                    br_ref="OQ-150 · BR-BIL-033 · DEF-BIL-10546",
                    detail="this bill's text contains "
                    f"{', '.join(printed.characters)} — character(s) the bill's font "
                    "(Liberation Sans, PO ruling 2026-10-23) has no glyph for — and each "
                    f"printed as '{tagged_pdf.UNREPRESENTABLE_MARK}' on the PAGE. The HTML "
                    "serialisation and the stamped payload are unaffected. The PO closed "
                    "OQ-150 on 2026-08-12 — *'print a substitution'* — so this reports "
                    "rather than refuses.",
                ),
            )
        return PdfSerialisation(
            data=printed.data,
            page_count=printed.page_count,
            unrepresentable=unrepresentable,
            characters=printed.characters,
        )

    return render


def _pdf(document: dict[str, Any], spec: LayoutSpec | None = None) -> PdfSerialisation:
    """The pinned layout's PAGE — A19 §1's field order, printable.

    Deterministic: no clock, no random source, no `/Info` dates, a content
    hash for `/ID`, and a row order that comes from the caller's stable line
    ordering (`_lines_of` sorts by `created_at, id`). The same bill renders the
    same bytes today and on a reprint in 2031.
    """
    pages = _pdf_pages(_pdf_rows(document, spec))
    footer = f"Bill {document['invoice_no'] or ABSENT_MARK}"
    streams: list[bytes] = []
    lost: list[str] = []
    for index, page in enumerate(pages, start=1):
        stream, missing = _pdf_page_stream(
            page, page_no=index, page_count=len(pages), footer=footer
        )
        streams.append(stream)
        lost.extend(missing)
    unrepresentable: tuple[AbsentField, ...] = ()
    if lost:
        unrepresentable = (
            AbsentField(
                field="pdf_text",
                br_ref="OQ-150 · BR-BIL-033",
                detail="this bill's text contains "
                f"{', '.join(sorted(set(lost)))} — character(s) the Base-14 fonts cannot "
                f"encode without an embedded font — and each printed as "
                f"'{UNREPRESENTABLE_MARK}' on the PAGE. The HTML serialisation and the "
                "stamped payload are unaffected: the value is not missing, the page cannot "
                "show it. OQ-150 asked whether that should REFUSE the issue (BR-BIL-033) "
                "instead of printing a substituted name, and the PO CLOSED it on "
                "2026-08-12 — *'print a substitution'* — so this build reports rather than "
                "refuses, for OQ-117's reason, ruled the same day: refusing here would "
                "stop a bill the customer is owed over a defect in the FLOOR document.",
            ),
        )
    return PdfSerialisation(
        data=_pdf_file(streams, len(pages), document.get("logo")),
        page_count=len(pages),
        unrepresentable=unrepresentable,
        characters=tuple(sorted(set(lost))),
    )


#: template version -> the layout that renders it. ONE entry: this build ships
#: one built-in layout, in both serialisations. `LAYOUTS.get(pinned)` and never
#: `max(LAYOUTS)` — see `_layout_for`, and see US-BIL-022 TC-4 for why there is
#: no other door.
LAYOUTS: dict[int, Layout] = {
    BUILT_IN_LAYOUT_VERSION: Layout(
        html=_html, pdf=_pdf, tagged_pdf=_tagged_pdf_for(LAYOUT_SPECS[0])
    )
}

#: ⚠ **THE LIBRARY, KEYED BY `layout_key` — the registry that actually decides
#: what a bill looks like since 2026-08-16.** `LAYOUTS` above is keyed by
#: template VERSION NUMBER and is a survival from the days before
#: `bill_template_versions` existed; it is kept because every bill issued under
#: it is pinned to a version that must keep rendering the same page forever
#: (BR-BIL-026), and it is consulted only when a pin resolves to no version row.
LAYOUTS_BY_KEY: dict[str, Layout] = {
    spec.key: Layout(
        html=_html_for(spec), pdf=_pdf_for(spec), tagged_pdf=_tagged_pdf_for(spec)
    )
    for spec in LAYOUT_SPECS
}

#: The same library keyed the same way, as the SWITCHES rather than the two
#: callables — `DEF-2826`.
#:
#: ⚠ **IT EXISTS BECAUSE A `Layout` IS TWO CLOSURES AND ANSWERS NOTHING.**
#: `_html_for(spec)` binds the spec and hands back a function; the spec itself
#: is then unreachable, so a caller holding a rendered document could say WHICH
#: layout produced it (`layout_source`) and could not say WHAT that layout does.
#: The S30 viewer did exactly that: it printed *"Rendered from
#: platform-layout-compact-letter-v1"* and then drew every band unconditionally,
#: including the two `compact-letter-v1` suppresses. The sentence narrated a
#: guarantee the page did not perform, which is hard-won law 1 in its most
#: convincing form.
SPECS_BY_KEY: dict[str, LayoutSpec] = {spec.key: spec for spec in LAYOUT_SPECS}

#: Which layouts are registered, for a caller that wants to KNOW. Deliberately
#: never consulted by `render_invoice`: reading "the latest" on the render path
#: is how a 2026 bill starts printing on a 2031 template (BR-BIL-026).
LATEST_REGISTERED_VERSION = max(LAYOUTS)


def _layout_key_of(template_id: Any, template_version: int) -> str | None:
    """The `layout_key` of the PINNED version row, or None if there is no row.

    ⚠ **THIS IS THE ONE QUERY `render_invoice` MAKES BEYOND THE BILL AND ITS
    LINES, and it is a lookup of the PIN — never of "the current template".**
    BR-BIL-026 pins template + version at issue and a reprint renders THAT
    version; publishing a new one affects only future bills. So this reads the
    row the bill names and nothing else: there is no `.latest()`, no
    `status=published` filter and no ordering here, because every one of those
    would make a bill from July start printing on August's chosen layout.

    Returns None — rather than refusing — for a bill whose pin names no row.
    That is every bill issued before the library landed, and BR-BIL-026 says a
    reprint renders what was sent: those fall through to the version-number
    registry, which is the one built-in layout, which is what they were printed
    on. Refusing them would make the whole of a utility's back catalogue
    unprintable to fix a layout nobody had chosen yet.
    """
    if template_id is None:
        return None
    from apps.billing.template_models import BillTemplateVersion

    row = (
        BillTemplateVersion.objects.filter(
            template_id=template_id, version_no=template_version
        )
        .values_list("layout_key", flat=True)
        .first()
    )
    return row or None


def _layout_for(
    template_version: int, template_id: Any = None
) -> tuple[Layout, str, LayoutSpec]:
    """The layout this bill's PIN resolves to, where it came from, and what it DOES.

    Three doors, in this order, and the order is the rule:

      1. **the pinned version row's `layout_key`** — the tenant's own choice,
         frozen with the bill. This is what the chooser writes and what
         BR-BIL-026 makes permanent for every bill already pinned to it.
      2. **the version-number registry** — the pre-library door, for a bill
         whose pin names no row (see `_layout_key_of`).
      3. **the built-in layout, NAMED** — never `max(LAYOUTS)`, so the fallback
         cannot quietly become a render-on-latest.

    Every document says which door it came through, in `layout_source`, on both
    serialisations. A reader holding a bill can therefore tell a tenant-chosen
    layout from a stand-in without running anything.

    ⚠ **THE THIRD MEMBER IS THE SPEC THAT WAS ACTUALLY USED, AND IT IS NOT
    DERIVABLE FROM `layout_source` — `DEF-2826`.** Two of the four doors return
    a STAND-IN, and the source string then names the layout that was ASKED FOR
    as well as the one that ran (*"…standing-in-for-unpublished-x"*). A caller
    parsing that string to recover the switches would recover the wrong ones on
    exactly the bills where being wrong matters. So the spec is returned rather
    than reconstructed, and a stand-in returns the stand-in's own spec, which is
    what the page in the customer's hand was built from.

    The pre-library doors return the DEFAULT spec deliberately, not an empty
    one: `LAYOUTS[BUILT_IN_LAYOUT_VERSION]` is byte-identical to
    `standard-letter-v1` (see `LAYOUT_SPECS`), so its switches ARE the default
    spec's and saying anything else would misdescribe a bill that renders
    correctly.
    """
    key = _layout_key_of(template_id, template_version)
    if key is not None:
        chosen = LAYOUTS_BY_KEY.get(key)
        if chosen is not None:
            return chosen, f"platform-layout-{key}", SPECS_BY_KEY[key]
        # A key the platform does not publish. It cannot arrive through
        # `templates_service.save_draft` (which refuses one) but it CAN arrive
        # on a row written by a build that published a layout this one does
        # not — a rollback. The bill still prints, on the named stand-in, and
        # says so rather than 500ing a customer's document.
        return (
            LAYOUTS_BY_KEY[DEFAULT_LAYOUT_KEY],
            f"platform-layout-{DEFAULT_LAYOUT_KEY}-standing-in-for-unpublished-{key}",
            SPECS_BY_KEY[DEFAULT_LAYOUT_KEY],
        )
    layout = LAYOUTS.get(template_version)
    if layout is not None:
        return (
            layout,
            f"registered-layout-v{template_version}",
            SPECS_BY_KEY[DEFAULT_LAYOUT_KEY],
        )
    return (
        LAYOUTS[BUILT_IN_LAYOUT_VERSION],
        f"built-in-layout-v{BUILT_IN_LAYOUT_VERSION}"
        f"-standing-in-for-pinned-v{template_version}",
        SPECS_BY_KEY[DEFAULT_LAYOUT_KEY],
    )


def _run_problems(
    invoice: models.Invoice,
    currency: str,
    absent: list[AbsentField],
    page: PdfSerialisation,
) -> tuple[RunProblem, ...]:
    """The PO's *"report it"*, built — one entry per thing worth waking somebody for.

    NOT every absence becomes a problem, and that restraint is the point. An
    unstamped bill message or a service heading that prints an id is a gap in
    what stage 6 stamps and it is already listed in `absent`; promoting all
    twelve to run problems would put twelve warnings on every bill of every run
    and bury the two the PO actually ruled on. Two qualify today:

      * **the TOTAL DUE** — OQ-117, *"issue and report it"*. It is the largest
        number on a utility bill and its absence changes what the customer can
        do with the page they were sent.
      * **a character the page cannot spell** — OQ-150, *"print a
        substitution"*, ruled the same day and the same way. The bill goes out;
        the run names the bill AND the character so somebody can fix the record.

    Both details name the bill and end in something a person can do. A code
    with no bill number is a statistic, and a bill number with no next step is
    a complaint.
    """
    bill = invoice.invoice_no or str(invoice.pk)
    problems: list[RunProblem] = []
    if any(field.field == "total_due" for field in absent):
        problems.append(
            RunProblem(
                code="total_due_not_printable",
                invoice_id=str(invoice.pk),
                invoice_no=invoice.invoice_no,
                br_ref="OQ-117 · BR-BIL-035 · BR-BIL-033",
                detail=(
                    f"bill {bill} was ISSUED without a printable total due. Its charge "
                    f"lines are correct and its current charges are "
                    f"{_money(invoice.total, currency)}, but BR-BIL-035's balance-forward "
                    "figures (previous balance, payments & credits) are not stamped into "
                    f"`bill_payload`, so the summary box and the remittance stub both "
                    f"print '{ABSENT_MARK}' where the amount due belongs. The bill was NOT "
                    "withheld — PO 2026-08-12, *'issue and report it'*: the customer needs "
                    "the charge lines and they are right. TO FIX: stage 6 "
                    "(apps/billing/stages/assemble_document.py) must stamp the "
                    "balance-forward section BR-BIL-035 already requires payload v1 to "
                    "carry. UNTIL IT DOES: a customer asking what they owe must be "
                    "answered from their account balance, not from this page."
                ),
            )
        )
    for field in page.unrepresentable:
        # The ruling asks the run to name the bill AND THE CHARACTER, so the
        # characters come from `page.characters` rather than out of the prose
        # next door — a report that had to read a sentence back apart would
        # break the first time somebody reworded it.
        characters = ", ".join(page.characters) or "one or more characters"
        problems.append(
            RunProblem(
                code="pdf_character_substituted",
                invoice_id=str(invoice.pk),
                invoice_no=invoice.invoice_no,
                br_ref=field.br_ref,
                detail=(
                    f"bill {bill} was ISSUED with a substitution on its printed page: it "
                    f"contains {characters}, which the Base-14 fonts cannot encode without "
                    f"an embedded font, and each printed as '{UNREPRESENTABLE_MARK}'. The "
                    "bill was NOT withheld — PO 2026-08-12, *'print a substitution'*. TO "
                    "FIX: check this customer's record. If the name is right the PAGE is "
                    "at fault and needs an embedded Unicode font (OQ-149); if the name is "
                    "wrong, correct it and the next bill prints cleanly. The HTML and the "
                    "stamped payload hold the correct characters either way, so nothing "
                    "was lost from the record — only from the paper."
                ),
            )
        )
    return tuple(problems)


def _report(problems: tuple[RunProblem, ...]) -> None:
    """Say it out loud. The half that makes `problems` a report and not a field.

    `issue.py` renders every bill to satisfy BR-BIL-033 and DISCARDS the
    result, so a run problem that only rode home on the return value would
    reach precisely nobody — built, unwired, and green (hard-won law 2). One
    WARNING per problem per render is the floor: it names the bill, it says
    what to do, and it lands wherever the deployment sends `smartbillhub.*`.

    ⚠ It fires on a REPRINT too, and that is deliberate rather than overlooked:
    the reprint of a bill that could not print its total still cannot print it,
    and a report that went quiet after the first render would let the condition
    disappear from view while it was still true. What this is NOT is a durable
    record — there is no run-problem table for a bill that ISSUED (the
    `BlockedAccount` channel in `runs.py` is for bills that did not), so a log
    line is the strongest thing this module can reach from where it stands.
    That gap is named in `DOCUMENT_UNAVAILABLE` rather than left as a comment.
    """
    for problem in problems:
        logger.warning("%s [%s · %s]", problem.detail, problem.code, problem.br_ref)


#: ⚠ **THE KEYS A LAYOUT READS — named ONCE, 2026-08-16 (returned-mail lane).**
#: Every layout in `LAYOUTS_BY_KEY` indexes this mapping directly, so the set is
#: a contract between `render_invoice` and eleven renderers, and it GREW on
#: 2026-08-16 when US-BIL-028 added `remarks`.
#:
#: It is named because a caller outside `render_invoice` that wants the same
#: mapping — the layout-library test compares one bill across all five layouts —
#: could otherwise only hand-copy the key list, and a hand-copied list goes
#: stale the first time a section is added. It did: `test_us_bil_021_tc20`
#: listed eleven keys, `remarks` became the twelfth, and the test died on
#: `KeyError: 'remarks'` inside a layout rather than on anything about layouts.
#: `document_mapping` below rebuilds the mapping from a finished document, and
#: the same test asserts that what `render_invoice` actually passes is exactly
#: these names — so the next section added here cannot quietly desync.
# ═══════════════════════════════════════════════════════════════════════════
# THE LOGO — `CR-172-BRC10` (PO 2026-10-05), BR-TEN-017, BR-TEN-019
# ═══════════════════════════════════════════════════════════════════════════
#
# A bill draws the logo it was STAMPED with: `bill_payload.utility_logo` names
# a stored document in the common store (the PNG — an SVG logo was rendered to
# PNG once, at upload, which is BR-TEN-019's *"rasterized for PDF/print"*). A
# stored document is write-once, so the picture on a reprint is the picture on
# the original, whatever the utility uploads later.
#
# ⚠ **THIS IS THE ONE READ THE RENDER MAKES BEYOND THE INVOICE'S OWN ROWS, AND
# IT IS NOT MASTER DATA.** `test_us_bil_022_tc2` pins the render at two queries
# for a bill with no logo. A stamped bill adds the stored document BY ITS ID —
# a frozen object, the same kind of read as the pinned template version — and
# the decoded picture is kept per process, so a 36,000-bill run reads it once.
#
# ⚠ **A LOGO THE STORE CANNOT RETURN IS LEFT OFF; THE BILL STILL PRINTS.** A
# picture on a heading is never a reason to refuse a bill (BR-BIL-033 is about
# the bill's facts) — the same posture `tenancy_seam.bill_masthead` takes.

#: The logo's placed size on the page, in points: at most `LOGO_MAX_HEIGHT`
#: tall and `LOGO_MAX_WIDTH` wide, at its own aspect ratio.
LOGO_MAX_HEIGHT = 40.0
LOGO_MAX_WIDTH = 132.0
#: How far the logo's top sits above the name's baseline — the name's cap
#: height, so the top of the picture and the top of the name line up.
LOGO_ABOVE_BASELINE = SIZE_UTILITY * 0.72
#: The gap between the logo and the name beside it.
LOGO_GAP = 12.0


@dataclass(frozen=True)
class DocumentLogo:
    """The utility's logo as both serialisations draw it.

    `png` is the stored PNG exactly (the HTML carries it as a `data:` URI);
    `rgb` and `alpha` are its samples, zlib-compressed, for the PDF's image
    XObject and soft mask. Deterministic: the same PNG always yields the same
    bytes, so `test_us_bil_022_tc12`'s byte-identical reprint still holds.
    """

    document_id: str
    png: bytes
    width: int
    height: int
    rgb: bytes
    alpha: bytes | None

    @property
    def base64(self) -> str:
        import base64

        return base64.b64encode(self.png).decode("ascii")

    def placed_size(self) -> tuple[float, float]:
        """(width, height) in points on the page — fitted, never stretched."""
        if self.width <= 0 or self.height <= 0:
            return 0.0, 0.0
        scale = min(LOGO_MAX_HEIGHT / self.height, LOGO_MAX_WIDTH / self.width)
        return round(self.width * scale, 2), round(self.height * scale, 2)


_DECODED_LOGOS: dict[str, DocumentLogo] = {}
_DECODED_LOGOS_MAX = 32


def logo_for(stamp: Any) -> DocumentLogo | None:
    """The stamped logo, decoded — or None when there is none or it cannot be read.

    `stamp` is `bill_payload["utility_logo"]` (`{"document_id", "content_type"}`),
    or what `tenancy_seam.bill_logo()` answers for the Bill layout preview,
    which shows the logo the NEXT bill will carry.
    """
    if not isinstance(stamp, dict) or not stamp.get("document_id"):
        return None
    from apps.billing import tenancy_seam

    document_id = str(stamp["document_id"])
    try:
        png = tenancy_seam.logo_png(document_id)
    except Exception:  # noqa: BLE001 — a missing picture never stops a bill
        logger.warning("bill logo %s could not be read; the bill prints without it", document_id)
        return None
    if not png:
        return None
    key = hashlib.sha256(png).hexdigest()
    cached = _DECODED_LOGOS.get(key)
    if cached is not None and cached.document_id == document_id:
        return cached
    decoded = _decode_logo(document_id, png)
    if decoded is None:
        return None
    if len(_DECODED_LOGOS) >= _DECODED_LOGOS_MAX:
        _DECODED_LOGOS.pop(next(iter(_DECODED_LOGOS)))
    _DECODED_LOGOS[key] = decoded
    return decoded


def _decode_logo(document_id: str, png: bytes) -> DocumentLogo | None:
    import io
    import zlib

    try:
        from PIL import Image

        with Image.open(io.BytesIO(png)) as opened:
            image = opened.convert("RGBA")
    except Exception:  # noqa: BLE001 — an unreadable picture is left off
        logger.warning("bill logo %s is not a readable PNG; the bill prints without it", document_id)
        return None
    alpha_band = image.getchannel("A")
    opaque = alpha_band.getextrema() == (255, 255)
    return DocumentLogo(
        document_id=document_id,
        png=png,
        width=image.width,
        height=image.height,
        rgb=zlib.compress(image.convert("RGB").tobytes(), 9),
        alpha=None if opaque else zlib.compress(alpha_band.tobytes(), 9),
    )


LAYOUT_FIELDS: tuple[str, ...] = (
    "invoice_no",
    "template_version",
    "payload_version",
    "layout_source",
    "masthead",
    "meta",
    "services",
    "groups",
    "summary",
    "remarks",
    # A19 §1.7 — the THIRTEENTH, added by CR-052 task 9. The comment above is
    # this section's own history repeating: `remarks` became the twelfth and a
    # hand-copied key list died on `KeyError: 'remarks'`. Adding it here is what
    # makes both serialisations and every layout receive it together.
    "usage",
    "footer",
    "stub",
    # `CR-172-BRC10` — the FOURTEENTH: the utility's logo, read from the stored
    # document THIS BILL was stamped with. Last, so no existing position moves.
    "logo",
)


def document_mapping(document: "RenderedDocument") -> dict[str, Any]:
    """The exact mapping the layouts rendered, rebuilt from a finished document.

    `RenderedDocument` carries every one of `LAYOUT_FIELDS` as a field of the
    same name — deliberately, so a rendered bill can be handed back to another
    layout without re-reading the invoice. That is what a comparison across the
    five platform layouts needs, and it is the only supported way to get one:
    building the dict by hand is how it goes stale.
    """
    return {name: getattr(document, name) for name in LAYOUT_FIELDS}


def render_invoice(
    invoice: models.Invoice,
    *,
    template_id: Any = None,
    template_version: Any = None,
    lines: Any = None,
) -> RenderedDocument:
    """Render ONE bill as its document. The whole public surface of this module.

    Returns BOTH serialisations of one structure: `.body` is the HTML and
    `.pdf` is the printable page (BR-BIL-036's floor), built from the same
    mapping by the same pinned `Layout`. Rendering both is not optional and
    there is no `pdf=False` argument, because BR-BIL-033 asks *can this bill
    become a document?* and a bill whose PAGE cannot be produced has not
    answered yes — a print channel is what every bill has (BR-BIL-036), so the
    page is the answer that matters most.

    Reads exactly two things: the invoice row it is handed, and that invoice's
    own `invoice_lines`. No other table is touched, and `lines` may be passed
    by a caller that already holds them (the issue path does) so the render
    costs zero extra queries inside its transaction. The PDF adds no query and
    no read of its own: it is a pure function of the mapping already built.

    No clock, anywhere. Every date on the document is a stored date
    (BR-TEN-043; G6 greps this module for a wall clock and rightly).

    `template_id` / `template_version` are the pin. An issued bill's own pin
    always wins and a disagreeing argument is refused (BR-BIL-026). A draft has
    no pin, so the pre-issue render is handed the pin issue is about to write —
    which is what makes BR-BIL-033's *"render before issue"* the same document
    as the one the customer gets.

    Raises `BillingRuleError` for everything a human can act on: no pin, no
    locked instance, an unrenderable payload version, an unreadable figure. It
    does NOT raise for a field the snapshot omits — that renders as a named
    absence, because refusing every bill whose masthead is unstamped would
    refuse every bill this system currently produces, and the gap belongs in a
    report rather than in a batch failure.
    """
    pinned_id, pinned_version = _pinned(invoice, template_id, template_version)
    payload = _payload_of(invoice)
    currency = invoice.currency
    if not currency:
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} has no currency, so its money cannot "
            "be printed (CLAUDE.md rule 2 — every amount carries its CHAR(3) partner). "
            "A number with no currency on a bill is not an amount."
        )

    masthead, absent_masthead = _masthead(payload)
    meta, absent_meta = _meta(invoice, payload)
    services, absent_services = _services(payload)
    groups, absent_groups = _groups(_lines_of(invoice, lines), currency, payload)
    summary, absent_summary = _summary(invoice, payload, currency)
    remarks = _remarks(invoice)
    usage, absent_usage = _usage(payload)
    footer, absent_footer = _footer(payload)
    stub = _stub(invoice, payload, summary)

    layout, layout_source, layout_spec = _layout_for(pinned_version, pinned_id)
    document = {
        "invoice_no": invoice.invoice_no,
        "template_version": pinned_version,
        "payload_version": invoice.payload_version,
        "layout_source": layout_source,
        "masthead": masthead,
        "meta": meta,
        "services": services,
        "groups": groups,
        "summary": summary,
        # US-BIL-028. Read off the INVOICE ROW's own `custom_snapshot` column
        # and not out of `bill_payload`: the two are stamped together in the
        # same statement (stages/assemble_document.py) and frozen by the same
        # trigger, and the column is where B2 r17.3 puts it.
        "remarks": remarks,
        # A19 §1.7 — CR-052 task 9. Built from `bill_payload.usage_history` and
        # nothing else, so both serialisations below draw the frozen months and
        # neither can reach a live read (BR-BIL-030).
        "usage": usage,
        "footer": footer,
        "stub": stub,
        # CR-172-BRC10 — the logo the bill was STAMPED with, never the current
        # one (BR-TEN-017). One read of a write-once stored document, cached
        # per process, so a reprint in 2031 draws the same picture.
        "logo": logo_for(payload.get("utility_logo")),
    }
    # ONE mapping, TWO serialisations, and the PIN selected both together. A
    # PDF built from a re-derived structure — or registered in its own dict —
    # could disagree with the HTML about what this bill says, and the customer
    # holds the page while the dispute reads the screen.
    #
    # BR-BIL-033 COVERS BOTH, and the translation below is what makes that
    # true. A layout that raises something other than `BillingRuleError` — a
    # `TypeError` on an unexpected value, a `KeyError` on a mapping key a
    # future serialisation forgot — would otherwise escape `issue_invoice`'s
    # per-bill handler and take the whole batch down with it, which is exactly
    # the outcome BR-BIL-055 forbids. Here it becomes one named break on one
    # bill: the sentence carries `issue.py`'s `ISSUE_RENDER_FAILED` phrase, the
    # bill stays a correctable draft, and the other 499 issue.
    # DEF-BIL-10546 — WHICH PAGE WRITER. A DRAFT is a document being made NOW:
    # the pre-issue render whose bytes `frozen_bill` keeps (BR-BIL-033), a
    # move-out's drafted final bill, a layout preview. It gets the TAGGED page
    # (PDF/UA-1), per the PO/QA ruling of 2026-10-23 (Group H). An invoice that
    # has ALREADY LEFT DRAFT keeps the writer it was printed with: its kept
    # original is served wherever one exists and this render is not reached,
    # and where none exists (a bill issued before v2.88.0) the ruling is *"New
    # bills only. The old ones stay as issued"* — no accessible copy of an old
    # bill is generated, so its re-render stays the hand-written page.
    tagged = invoice.status == models.INVOICE_DRAFT and layout.tagged_pdf is not None
    try:
        body = layout.html(document)
        page = layout.tagged_pdf(document) if tagged else layout.pdf(document)
    except BillingRuleError:
        raise
    except Exception as broken:  # noqa: BLE001 - see the comment above
        raise BillingRuleError(
            f"bill {invoice.invoice_no or invoice.pk} was refused by its layout "
            f"({layout_source}) with {type(broken).__name__}: {broken} — so the document "
            "cannot be rendered, and BR-BIL-033 refuses the issue rather than let a bill "
            "become immutable and unprintable. The bill is still a draft and still "
            "correctable; nothing about its money is in question."
        ) from broken

    # OQ-117, CLOSED (PO 2026-08-12): *"issue and report it"*. AFTER both
    # serialisations have succeeded, because a bill that could not be rendered
    # at all took the `raise` above and is not an issued bill with a reportable
    # gap — it is a refusal, and the two must not be confused in the run log.
    absent_all = (
        absent_masthead
        + absent_meta
        + absent_services
        + absent_groups
        + absent_summary
        + absent_usage
        + absent_footer
    )
    problems = _run_problems(invoice, currency, absent_all, page)
    _report(problems)
    return RenderedDocument(
        invoice_id=str(invoice.pk),
        invoice_no=invoice.invoice_no,
        template_id=str(pinned_id) if pinned_id is not None else None,
        template_version=pinned_version,
        payload_version=invoice.payload_version,
        layout_source=layout_source,
        currency=currency,
        content_type="text/html; charset=utf-8",
        body=body,
        pdf=page.data,
        pdf_page_count=page.page_count,
        masthead=masthead,
        meta=meta,
        services=services,
        groups=groups,
        summary=summary,
        remarks=remarks,
        usage=usage,
        footer=footer,
        stub=stub,
        logo=document["logo"],
        absent=tuple(absent_all),
        pdf_unrepresentable=page.unrepresentable,
        pdf_tagged=tagged,
        problems=problems,
        unavailable=DOCUMENT_UNAVAILABLE,
        # DEF-2826 — the spec the two serialisations above were built from, so a
        # reader of this document can DRAW what they were told was rendered.
        layout=layout_spec,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-022@5397d5f (sha1[:7] of the four sources this file was
#         authored from, concatenated in order: 04-docs/01-spec/19-document-templates.md
#         — A19, the bill layout — · 04-docs/05-modules/07-billing/06-epics/
#         EP-BIL-06-templates-delivery.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md. Recomputed 2026-08-11; note that the
#         `@e9d5a48` its billing neighbours carry no longer reproduces (their
#         four sources now hash to 729c662), so those stamps are stale.
# generated: 2026-08-11 by Eng-Lead (W3 bill-document lane) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: the Taxes group's absent-field note corrected: the LINE names its tax now; the SNAPSHOT still carries no authority NAME or rate) · AMENDED 2026-08-12 by story-coder (OQ-117 CLOSED "issue and report it" + OQ-150 CLOSED "print a substitution": the two rulings gain a `RunProblem` channel that names the bill and is emitted, because the issue path discards the document)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — GET /invoices/{id}/document is not mounted) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_022_documents.py 16 passed (11 + the
#         PDF lane's tc12 determinism · tc13 no-drift · tc14 BR-BIL-033 for the
#         page · tc15 structural validity · tc16 WinAnsi) · FIFTEEN MUTATIONS
#         PROVED RED BEFORE ANY GREEN WAS TRUSTED — the original nine plus the
#         PDF lane's six — every one quoted verbatim in
#         12-governance/09-human-review-ledger.md. Suite and gate figures for
#         each lane pass are in the lane reports; every number quoted anywhere
#         here was read, not assumed.
#         ✔ G7 NOW GUARDS THIS FILE. The trailer previously read "⚠ G7 reports
#         105 guarded files and THIS FILE IS NOT ONE OF THEM" and was true when
#         written; `10-scripts/gates/human_owned.txt` gained the glob on
#         2026-08-11 and G7 reports 107 guarded files conforming.
# exceptions: (1) THE PDF IS THE PRINT FLOOR, NOT THE TENANT'S DESIGNED BILL —
#         and this item previously read "HTML, NOT PDF … this build has no PDF
#         library", which was TRUE WHEN WRITTEN and is now false. There is still
#         no PDF library; there is now a PDF, written here with the standard
#         library so that no dependency decision was taken at all (the survey —
#         WeasyPrint's system libraries, ReportLab's second layout language,
#         xhtml2pdf's tree, fpdf2's LGPL — is in the module docstring and in
#         12-governance/02-decision-log.md 2026-08-11). What the page does NOT
#         have: logo, 12-month usage graph, remittance barcode, colour, tenant
#         CSS, or a paper size other than US Letter. Rendering the tenant's
#         DESIGNED body needs an HTML/CSS engine that changes the deployment
#         image — **OQ-149, OPEN** (the PO explicitly did NOT answer it in the
#         2026-08-12 batch). A character outside WinAnsi prints substituted, is
#         NAMED per bill (`pdf_unrepresentable`) and is REPORTED as a run
#         problem naming the bill and the character. This item previously read
#         "whether it should instead refuse the issue is OQ-150, OPEN" and was
#         true when written: **OQ-150 CLOSED 2026-08-12 — *"print a
#         substitution"*.**
#         (2) THE TENANT'S TEMPLATE BODY IS NOT HONOURED. `bill_templates` /
#         `bill_template_versions` (r10 #4) do not exist, so `template_id`
#         resolves to nothing and one built-in layout stands in for every pinned
#         version. The VERSION axis IS honoured — the pin selects, the render
#         path never reads `LATEST_REGISTERED_VERSION`, a disagreeing
#         `template_version=` argument is refused, and there is no
#         render-on-latest option (US-BIL-022 TC-4). Every document names its
#         `layout_source` so no reader has to take this on trust.
#         (3) NOTHING IS STORED AND NOTHING IS DELIVERED. BR-BIL-036 makes print
#         the primary channel and requires the document to be STORED; there is
#         no document table and no blob store, and `outbound_messages` (which
#         billing DOES write at issue since 2026-08-11) pins the template and
#         keeps no body. So there is now a PRINTABLE PDF and it is thrown away
#         the moment it has proved the bill renderable. Rendering is reachable
#         from `issue.py`; delivery is not reachable from anywhere, and
#         `GET /invoices/{id}/document` is not mounted, so no human can open
#         one either (hard-won law 2 — built is not wired).
#         (4) THE SNAPSHOT IS MISSING MOST OF WHAT A19 PRINTS, and every gap is
#         on the document rather than in this comment: masthead (utility name /
#         address / contact), service address, bill date, cycle, meter numbers
#         with prior and current reads, tax authority and rate, the tenant's
#         message and footer, and — the one that matters most — the whole
#         BR-BIL-035 balance-forward section, so TOTAL DUE cannot be printed at
#         all. `invoices.total` is the CURRENT CHARGES. None of it is fetched
#         live: that would rewrite an issued document by reading (BR-BIL-030).
#         Since 2026-08-12 the total's absence is also REPORTED per bill — see
#         (5) — so it is no longer only a row on a discarded object.
#         (5) IT DOES NOT REFUSE A BILL FOR AN ABSENT FIELD, AND THAT IS NOW
#         RULED. This item previously read "**OQ-117, OPEN**, not a settled
#         reading … which is why it is put to the PO rather than taken", and it
#         was true when written. **The PO CLOSED OQ-117 on 2026-08-12: *"issue
#         and report it"*.** Refusals stay for what makes rendering impossible
#         (no pin, no locked instance, an unrenderable payload version, an
#         unreadable figure); an unstamped masthead or an unprintable TOTAL DUE
#         renders as a named absence AND — the part that was missing — as a
#         `RunProblem` that names the bill, says what is wrong in plain English
#         and says what to do, emitted on `LOGGER_NAME` because `issue.py`
#         discards the document it renders. Never stubbed as
#         `NotImplementedError`: that crashes a batch where BR-BIL-055 wants one
#         named break per bill. What is still owed: nothing STORES a problem for
#         a bill that issued (`runs.BlockedAccount` is for bills that did not),
#         so the report reaches a log and not the S31 run summary — reported in
#         `DOCUMENT_UNAVAILABLE` as `run_problems_are_logged_and_not_stored`.
#         (6) NO TIE-OUT IS ENFORCED HERE (BR-BIL-032). The half that IS
#         assertable — Σ(`invoice_lines.amount`) == `invoices.total`, exactly,
#         because the engine finalizes every line to 2dp and the total is their
#         sum — is asserted in tests/test_us_bil_022_documents.py tc7 rather
#         than made a refusal: BR-BIL-032 is PROPOSED, and a PROPOSED rule that
#         blocks issue is a rule nobody ruled. The half that is NOT assertable
#         is `bill_payload.total`, which stage 6 does not stamp.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
