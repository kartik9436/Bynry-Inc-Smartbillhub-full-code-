# ── Trace ──────────────────────────────────────────────
# Component: BE-06 number-series service (B13 §3, W0 kernel lane — component packet)
# Contract:  BR-TEN-035 format grammar + allocation law · US-TEN-012 §5 (number_series
#            storage, tenancy-owned per B2 PM owner map) · B2 r12 #13 (PMT-/DEP-/RCT-
#            series anchored) · B12 §6a (numbering.next(...) call shape at issue)
# Rules:     BR-TEN-035 (grammar; in-transaction allocation; gaps ok, never reused;
#            format changes future-only; issued numbers never renumbered; next-number
#            forward-only; CR-005 clauses (a)–(e): ≤24 chars, pad ≤8, restart period,
#            overflow widens, duplicate prefixes warn, plain option per series) ·
#            BR-TEN-041 (PMT/DEP/RCT/EXP series upgrade) · BR-LED-021 (JE- series) ·
#            BR-TEN-043 (event-time law: issue date is an input, never the wall clock)
# Change:    CR-005 (PO 2026-08-16 — SET-08 Numbering)   Screens: S8 / r10 SET-08
# Questions: OQ-250 (pad minimum of 4 vs shipped ADJ-{000}) · OQ-251 (which entity
#            list — CR's sixteen vs r10's fourteen; built as the union of 22) ·
#            OQ-252 (restart on a date-token-free format is REFUSED)
# Tests:     06-backend/tests/test_be06_numbering.py (mocked sink) · US-TEN-012/TC-1..8
#            land with apps.tenancy (live number_series table + S8 settings tab) ·
#            06-backend/tests/test_cr005_numbering_set08.py (the CR-005 clauses)
# Impacts:   every issuing module — billing invoice_no · payments PMT- · deposit
#            batches DEP- · receipts RCT- · ledger export EXP- · accounts · assets
# ───────────────────────────────────────────────────────
"""BE-06 — the ONE tenant-scoped document-numbering contract every module calls.

BR-TEN-035: a number is a literal prefix + date tokens + exactly one zero-padded
sequence token, allocated INSIDE the issuing transaction from a per-tenant
per-series monotonic counter. Gaps from rolled-back transactions are acceptable;
a number is NEVER reused; format changes apply to future numbers only — issued
numbers are never renumbered or reformatted (they sit on immutable financial
rows, CLAUDE.md rule 4). This module deliberately has NO renumber/reformat API.

Narrow interface (same shape as core.audit): storage is a registered sink.
apps.tenancy owns the `number_series` table (B2 PM owner map: number_series →
tenancy) and registers its allocator in AppConfig.ready():

    core.numbering.set_series_sink(apps.tenancy.services.allocate_series_number)

Sink contract (the SELECT FOR UPDATE allocation law, BR-TEN-035 / B8 locking):
- signature: sink(series: str, issue_date: date) -> (format_string, sequence_number)
- Inside the CALLER's issuing transaction it must `SELECT … FOR UPDATE` the
  tenant's `number_series` row (RLS-scoped by app.tenant_id — the sink never
  receives a tenant parameter), read `format` and `next_number`, advance
  `next_number` by one, and return the pre-advance value as the allocated
  sequence. Under a CR-005 restart period it must ALSO compare the row's
  recorded period against `issue_date`'s and, on a roll FORWARD, put the
  counter back to 1 in the same locked statement. Row-lock + same-transaction allocation is what makes US-TEN-012
  TC-6 true: concurrent issuances get distinct sequential numbers with no
  duplicate and no deadlock; a rollback rolls the counter back with the row
  it would have numbered (a committed gap elsewhere is fine — gaps ok).
- unknown series for this tenant → the sink raises NumberingError (seeding the
  per-tenant series rows is US-TEN-012 / tenant provisioning's job).

Event-time law (BR-TEN-043): the issue date that fills {YYYY}/{YY}/{MM}/{DD}
is ALWAYS an explicit argument — this module never reads the wall clock. The
caller passes the business event's date in the tenant's timezone (bill date,
posting date, …), so a backdated or catch-up issuance numbers under ITS date.

Forward-only settings edits (BR-TEN-035, US-TEN-012 TC-3/TC-5) are enforced
with ensure_forward_only() by the S8 settings save; the kernel hosts the rule
so settings and any future import path refuse identically.
"""

import re
from collections.abc import Callable
from datetime import date
from typing import Any

from core.tenancy import current_tenant_id

# ── Known series keys (storage rows are the truth; these are the documented set) ──
# US-TEN-012 §5 series enum (S8 Numbering tab):
ACCOUNT = "account"  # prototype default AC-{YYYY}-{00000}
BILL = "bill"  # prototype default BL-{YY}{MM}-{000000}
PAYMENT = "payment"  # prototype default PY-{YY}{MM}{DD}-{0000}; PMT- refs in r12 #13
ADJUSTMENT = "adjustment"  # prototype default ADJ-{000}
ASSET = "asset"  # A1 r4 Assets addendum, default AST-{00000}
# BR-TEN-041 settings-audit upgrade + B2 r12 #13 (tenant-adjustable):
DEPOSIT_BATCH = "deposit_batch"  # DEP- (BR-PAY-025 day×method batches)
RECEIPT = "receipt"  # RCT- (BR-PAY-024 receipts)
EXPORT_BATCH = "export_batch"  # EXP- (BR-LED-004 recorded accounting exports)
# BR-LED-021 (PO 2026-08-12, OQ-176 — verbatim *"Approve a JE- series"*): the
# NINTH series. Journal entries had none, so S56 showed
# `019ff23d-13ee-7aba-a280-58058e492cb9` where LE-8 says **JE-104** and LE-4 says
# **JE-201/JE-202** — a number a finance officer cannot read aloud, quote in an
# email, or find again. Allocated per tenant under BR-TEN-035 like every other
# series here, and stamped when the entry POSTS: a DRAFT has no number.
# ⚠ The recorded ruling also calls the series *"gapless"*. This kernel allocates
# from a monotonic counter where BR-TEN-035 says *"gaps ok, never reused"*, so a
# rolled-back post consumes its number. Both statements are on the record and
# BR-LED-021 flags the conflict; nothing here chooses between them.
JOURNAL_ENTRY = "journal_entry"  # JE- (BR-LED-021 manual + system journal entries)
# ── CR-005 (PO 2026-08-16, SET-08) — the thirteen series the settings screen
# adds. Nine existed; the CR names sixteen entities and prototype r10's SET-08
# table draws fourteen, and THE TWO LISTS ARE NOT THE SAME FOURTEEN (OQ-251).
# Built as the UNION so no lane had to choose between two PO artefacts of the
# same day, on the PO's own economics for the Work rows: *"it should work
# standalone in settings; we will link it later ith work"* — a series that
# issues nothing costs nothing.
PREMISES = "premises"  # already ALLOCATED FROM by apps.metering (PREMISES_SERIES)
UNIT = "unit"  # already ALLOCATED FROM by apps.metering (UNIT_SERIES)
SERVICE_REQUEST = "service_request"  # CR-005 group 1 · r10 SET-08 "Service request #"
CREDIT_MEMO = "credit_memo"  # r10 SET-08 "Credit memo #"
WRITE_OFF = "write_off"  # CR-005 group 2 "Write-off #"
COLLECTIONS_NOTICE = "collections_notice"  # r10 SET-08 "Collections notice #"
# The three WORK rows. PO 2026-08-16, verbatim: *"Yes; it should work standalone
# in settings; we will link it later ith work"* — FORMATS ONLY. No work-order
# table is created by their presence and OQ-249 (is Work a tenth module?) stays
# untouched: a series is a format, not a work order.
# ── CR-030 W6 · NEW CONNECT (PO 2026-08-25) ────────────────────────────────
# PO verbatim, asked what a connection number is: *"you have to add this in
# setting -> number - we are maintaining the formats there - you ahve to give
# multiple formats"*. So a connection is not a format this product imposes; it
# is a row in THIS catalogue with several ready-made options the utility picks
# from, exactly like every other entity.
#
# ⚠ THE BUILD REFUSED TO INVENT ONE, AND THAT WAS RIGHT. Until this row landed,
# `create_connection` returned `numbering_series_missing` with a NULL number
# rather than choosing a format — because DEF-615 is precisely what happens
# when a test and the catalogue each pick independently (`IMP-` vs `RUN-`).
CONNECTION = "connection"
WORK_ORDER = "work_order"
SERVICE_TEMPLATE = "service_template"
DISPATCH_BATCH = "dispatch_batch"
READ_BATCH = "read_batch"  # already ALLOCATED FROM by apps.metering (READ_BATCH_SERIES)
ROUTE = "route"  # CR-006 step 1: *"route ID (from Numbering format, editable)"*
CYCLE = "cycle"  # CR-006 SET-07 step 1 cycle code
IMPORT_RUN = "import_run"  # r10 SET-08 "Import run #"
# ── CR-030 W0 — THE TWENTY-FOURTH SERIES, AND THE ONLY ENTITY IN THE PRODUCT
# THAT HAD NO NUMBER. Accounts, premises, units, bills, payments, assets and
# work orders all carry one; `customers` carried a name and, if imported, the
# legacy system's `external_ref`. So every deposit carry-forward and every "they
# owe money on another account" check rested on a clerk matching a NAME.
#
# The worked case B18 §2.5 puts to the PO: a returning customer holding $153.50
# on a CLOSED account gets it carried across — or does not, because nobody found
# them. That is CR-030's cost #6, and it is one column plus this row.
#
# ⚠ NOT a replacement for `external_ref`, which stays. That is THEIR id in the
# system we migrated from and is what makes a re-import link instead of
# duplicating (BR-CUS-054); this is OURS, and a utility needs both — one to
# reconcile against the old system, one to quote down a phone.
CUSTOMER = "customer"
# ── OQ-342 (PO ruling 2026-08-23, verbatim *"A: a real series (RUN-0001, like
# RT-001)"*) — THE TWENTY-THIRD SERIES. The PO's own SET-07D screenshot draws a
# Run column reading `RUN-0814` and nothing in this product could produce it:
# `bill_runs` had no number column and this catalogue had no bill-run series, so
# the runs list served `run_no: null` and a test held it there rather than let a
# lane derive a grammar from `created_at`, a per-cycle ordinal or a uuid slice.
# D5 ruled `RT-001`/`CY-001` for ROUTES and CYCLES and was never asked about
# runs; this is the ruling that was.
#
# ⚠ **`import_run` IS NOT THIS AND NEVER WAS** — it numbers a READ IMPORT batch.
# It ALSO defaulted to `RUN-{0000}`, so seeding both would have greeted every new
# tenant with a duplicate-prefix warning; the ruling wins and `import_run` opens
# on `IMP-{YY}{MM}{DD}-{00}`, which was already its own second option. `RUN-` is
# still OFFERED there (a duplicate prefix is a CR-005 warning, never a block) and
# **no tenant's stored row moves**: `_seed_number_series` is `get_or_create`, and
# BR-TEN-035 forbids renumbering what has been issued.
BILL_RUN = "bill_run"  # RUN- (OQ-342 — the bill run a utility can quote)
# ── OQ-426 (PO ruling 2026-08-27) — THE TWENTY-SIXTH SERIES, and it closes the
# only refusal CR-039 wave D task 15 left standing. PO verbatim: *"Transfer
# TRF-26-0001 recommend it is one job spanning two accounts, and neither
# account number names it - follow same logic that we are following for other
# numbers we have did in settings."*
#
# `apps/customers/transfers.py` shipped `transfer_no`, its per-tenant CI-unique
# index and an in-transaction `_allocate_transfer_no` on 2026-08-27 and left the
# FORMAT refused, because B18 §5.7 draws no reference on the transfer tab, its
# five seeded rows carry account numbers on both sides, and r10 holds no
# transfer record at all — so there was nothing to derive a default FROM, and
# DEF-615 is what happens when a test and the catalogue each pick one
# independently. **This row is the ruling, not a derivation**: the PO named the
# rendered string, so `TRF-{YY}-{0000}` is FIRST and a counter of 1 in 2026
# renders exactly `TRF-26-0001`.
#
# ⛔ **THE DISCONNECT IS NOT THIS.** ⚠ **AMENDED 2026-08-27 — THIS PARAGRAPH SAID
# "AND IS STILL OPEN (`OQ-427`)" AND THAT STOPPED BEING TRUE THE SAME DAY.** The
# reasoning it recorded is still exactly why the transfer ruling did not close
# `OQ-427` — *"one job spanning two accounts, and neither account number names
# it"* does NOT carry to a record belonging to ONE account whose number already
# names it, and r10 draws a disconnection as a WORK ORDER (*"Disconnect work
# order raised · `WO-4833`"*). What changed is that the PO was asked and
# answered: *"it needs its own series"*. See `DISCONNECT_CASE` below.
TRANSFER = "transfer"  # TRF- (OQ-426 — the transfer a clerk can quote)
# ── OQ-427 (PO ruling 2026-08-27) — THE TWENTY-SEVENTH SERIES. PO verbatim, in
# full: *"it needs its own series"*, answering *"what is a disconnect case
# called — or IS it the work order?"*. **The ruling picks the ANSWER and not the
# PREFIX**, so unlike `TRANSFER` above this row is a DELEGATED choice and is
# recorded as the build's, never as the PO's (decision log 2026-08-27, *"a
# disconnect gets its own series"*).
#
# **`DSC-` over `DC-`, and the reason is who holds the paper.** A customer reads
# this number off a notice saying their water is about to be cut off; `DSC`
# reads as *disconnect* and `DC` reads as nothing.
#
# ⚠ **`DSP-` IS THE DISPATCH BATCH AND IT IS ONE CHARACTER AWAY** in a list an
# admin reads down. That was raised inside `OQ-427` itself, it is NOT solved by
# this choice, and it is accepted rather than papered over — named here so the
# next person to see the two adjacent knows it was seen. It raises no CR-005
# duplicate-prefix warning: `literal_prefix` compares the literals `DSC-` and
# `DSP-`, which differ.
#
# ⛔ **THIS IS NOT THE WORK ORDER, AND THE RULING IS WHAT MAKES THAT TRUE.**
# `WORK_ORDER` (`WO-{0000}`, GROUP_WORK) is untouched: r10's `WO-4833` is the
# two-hour field visit that turns the water off, and a case can sit on the
# ladder for months across three notices and a hold. *"Its own series"* is the
# sentence that separates them, so OQ-249 (is Work a tenth module?) stays
# exactly as open as it was.
DISCONNECT_CASE = "disconnect_case"  # DSC- (OQ-427 — the collections case a customer can quote)
# ── CR-039 wave D task 18 — THE TWENTY-EIGHTH AND TWENTY-NINTH SERIES, AND
# THEY ARE AN **EXTENSION OF A RULING RATHER THAN A RULING**. Flagged that way
# here because one word from the PO reverses them.
#
# **What was ruled** (decision log 2026-08-27, PO verbatim: *"you cna keep them
# as records for audit perpuses"*) is that a move-in and a move-out ARE records.
# The same entry says in as many words that it *"DOES NOT SETTLE D18's
# NUMBERING"*, because a signature covers only what was shown.
#
# **What made the number buildable anyway is that the argument against it
# died the same day.** The transfer's format was ruled with a reason — *"it is
# one job spanning two accounts, and neither account number names it"* — and a
# move belongs to ONE account whose number already names it, so the reason did
# not carry. Then a DISCONNECT, which belongs to one account too, got its own
# series on *"it needs its own series"*. **It cannot be true both that a
# one-account job needs no number of its own and that a disconnect, a
# one-account job, needs one.** Leaving these two unnumbered would rest on an
# argument the PO has just overturned, which is worse than building on a stated
# one.
#
# **TWO SERIES, NOT ONE SHARED `MV-`, and that is the build's call.** A clerk
# reading `MV-26-0004` back down a phone could not say whether it named an
# arrival or a departure; the two are separate flows on separate tabs with
# separate wizards. Two counters is the honest cost of a number that says what
# it names. ⚠ OQ-426 option B had reserved `MV-` for exactly this decision and
# deliberately did not offer it on the TRANSFER series — that reservation is
# what is being spent here, and it is spent on two prefixes rather than one.
#
# `MVI-` and `MVO-` collide with none of the twenty-seven prefixes already
# seeded, and they differ from each other in the LAST character rather than the
# first, which is the same readability hazard `DSC-`/`DSP-` carries and is named
# for the same reason: accepted, not solved.
MOVE_IN = "move_in"  # MVI- (CR-039 wave D 18 — the arrival a clerk can quote)
MOVE_OUT = "move_out"  # MVO- (CR-039 wave D 18 — the departure a clerk can quote)

# ⚠ **THE TWENTY-NINTH SERIES — CR-068 wave B (`US-CWP-009`, `BR-CWP-028`).**
# A stranger who reports a burst main has no account and no inbox we hold, so
# *"the reference is the entire record of the interaction"*. It is NOT the
# `service_request` series: a report raises BOTH an interruption (the network
# fact, `metering`) and a request on the clerk's worklist (`SR-26-0057`), and
# the number a passer-by is given names the INTERRUPTION. Giving them the SR
# number would put a clerk's case number in a stranger's hand and would make
# `Track` unable to tell the two records apart.
#
# **GROUP — `work`, and the reason is the one `connection` gives.** A crew is
# dispatched; the record's whole life is *looking into it → crew on site →
# resolved*. `customers_premises` is where an ACCOUNT-lifecycle record goes and
# an interruption belongs to nobody's account.
#
# **THE FIRST OPTION IS THE SEEDED DEFAULT AND EVERY PORTAL DOCUMENT NAMES ITS
# RENDERED STRING** — `RP-26-0412` (`US-CWP-007` §4, `US-CWP-009`, `US-CWP-010`
# §4, the wireframes `CWP-006`/`007`/`012`, the wave-B demo script) — so
# `RP-{YY}-{0000}` leads and a counter of 412 in 2026 renders exactly that.
# `RP-` collides with none of the twenty-eight prefixes already seeded (`RT-`
# is the route, `RB-` the read batch, `RCPT-`/`R-` the receipt).
INTERRUPTION_REPORT = "interruption_report"  # RP- (CR-068 wave B — what a passer-by keeps)

# ── THE THIRTY-FIRST SERIES — payments blueprint `P0.13` (PO ruling
# 2026-09-22, verbatim: *"(a) STL-26-0001"*).
#
# **WHAT A SETTLEMENT IS.** A card processor, an ACH originator or a lockbox
# provider takes many payments during a day and pays the utility ONE amount for
# them, later. The blueprint's §03 tab 5 draws that payout as a record a clerk
# opens — *"Which 46 payments made up this $8,047.30?"* — and it has never had a
# number, because it has never had a row.
#
# ⛔ **IT IS NOT THE DEPOSIT BATCH, AND THAT IS THE WHOLE REASON IT IS A SEPARATE
# SERIES.** `DEPOSIT_BATCH` numbers money a person carried to a bank and is
# keyed on their till session (`P0.6`); this numbers money a provider wired,
# which no person ever handled. A settlement borrowing `DEP-` would be
# indistinguishable from a counter drawer on a bank statement.
#
# **`STL-{YY}-{0000}` IS THE PO'S OWN RENDERED STRING, NOT A DERIVATION.** They
# were shown `STL-26-0001` and chose it, so a counter of 1 in 2026 renders
# exactly that. It is the `TRF-`/`MVI-`/`MVO-`/`DSC-` shape, which is what every
# series a clerk quotes down a phone already uses.
#
# ⚠ **A SEEDED DEFAULT A TENANT EDITS, NEVER A CONSTANT** (BR-TEN-035, and the
# ruling was recorded that way). What is ruled is what it STARTS as.
#
# `STL-` collides with none of the thirty prefixes already seeded (`SR-` is the
# service request, `DSC-`/`DSP-` are the near pair this module already names).
# The last option is CR-005's mandatory bare counter.
SETTLEMENT = "settlement"  # STL- (P0.13 — the provider payout a clerk can quote)

# ── G3 (PO 2026-10-14, decision log "G1–G4 APPROVED" item 3) ────────────────
# A correction case (Fix a bill, S30) takes its number AT SEND from this
# series. Ruling, verbatim: *"a correction case takes its number at Send from a
# new tenant series "Correction case", default `CC-{YYYY}-{000}` (e.g.
# CC-2026-001), editable in Settings → Numbering; existing cases are numbered
# once, oldest first; a deleted series leaves the case unnumbered and is never
# blocking (the credit-memo precedent)"*. `DEF-BIL-10147` is the defect it
# closes: every case had read "No case number yet" since W5.
#
# **It is seeded with a YEARLY restart** (`SERIES_DEFAULT_RESTART` below), the
# only series that is: the PO's own example reads `CC-2026-001`, and a year in
# the number whose counter does not start again in January would print
# `CC-2027-214` for the first case of the year. A tenant turns it off on the
# Numbering tab like any other setting. `CC-` collides with no seeded prefix.
CORRECTION_CASE = "correction_case"  # CC- (G3 — the case a clerk quotes from Fix a bill)

# ── Groups — the SET-08 section kickers, in the order the screen prints them ──
GROUP_CUSTOMERS = "customers_premises"
GROUP_BILLING = "billing_payments"
GROUP_FINANCE = "finance"
GROUP_WORK = "work"
GROUP_ASSETS = "assets_reads"
SERIES_GROUPS = (GROUP_CUSTOMERS, GROUP_BILLING, GROUP_FINANCE, GROUP_WORK, GROUP_ASSETS)

#: THE CATALOG: series key → (group, ready-made options). **The FIRST option is
#: the seeded default** (`apps.tenancy.services.SERIES_DEFAULTS` derives from
#: this, so the screen can never offer a list that omits what a tenant already
#: has). The last option of every list is a BARE COUNTER — CR-005, verbatim:
#: *"Plain-number option is mandatory in every category (user rule): just
#: `{00000}` with no prefix"*. `test_cr005_numbering_set08.py` refuses a list
#: that loses it, refuses one whose first entry fails `validate_format`, and
#: refuses a default that duplicates another series' prefix.
#:
#: Where r10's SET-08 draws a row, ITS option list is used verbatim (Account,
#: Premises, Service request, Bill, Receipt, Payment, Adjustment, Credit memo,
#: Deposit batch, Journal, Collections notice, Work order, Asset, Import run).
#: The eight the design does not draw follow the same shape. **A default is a
#: DEFAULT** (BR-TEN-036's posture, and BR-TEN-035 makes every one of them
#: tenant-editable from this screen) — none of these prefixes is a rule.
SERIES_CATALOG: dict[str, tuple[str, tuple[str, ...]]] = {
    ACCOUNT: (
        GROUP_CUSTOMERS,
        ("AC-{YYYY}-{00000}", "ACCT-{00000}", "{YYYY}{00000}", "A-{YY}-{0000}", "CUST-{000000}", "{0000000}"),
    ),
    PREMISES: (GROUP_CUSTOMERS, ("P-{00000}", "PRM-{YYYY}-{0000}", "PREM-{000000}", "{00000}")),
    UNIT: (GROUP_CUSTOMERS, ("U-{00000}", "UNIT-{0000}", "U-{YY}-{0000}", "{00000}")),
    SERVICE_REQUEST: (
        GROUP_CUSTOMERS,
        ("SR-{YY}-{0000}", "CASE-{YYYY}-{000}", "SR-{000000}", "REQ-{YY}{MM}-{000}", "{000000}"),
    ),
    # ── CR-030 W0 — the twenty-fourth series. ⚠ APPENDED to the customers
    # group rather than slotted beside ACCOUNT, and that is not cosmetic: this
    # dict's ORDER IS THE ORDER THE SETTINGS SCREEN PRINTS
    # (`test_cr005_the_tab_read_carries_group_options_and_restart` pins the
    # first four rows), so putting it next to `account` — which reads better —
    # would silently move four rows on a shipped screen. Additive placement
    # moves nothing and needed no test edit, which is the tell that it is right.
    #
    # `C-{00000}` leads: the shortest thing a clerk can read back down a phone,
    # and no other seeded default starts `C-` (CM- is the credit memo, CN- the
    # collections notice, CY- the cycle — distinct literals, so the
    # duplicate-prefix warning stays silent out of the box). `CUST-{000000}` is
    # offered SECOND despite being the more obvious word, because it is already
    # an OPTION on the ACCOUNT series above: a tenant taking it in both places
    # would be reading two different things off one prefix.
    CUSTOMER: (
        GROUP_CUSTOMERS,
        ("C-{00000}", "CUST-{000000}", "C-{YYYY}-{0000}", "CU-{YY}-{0000}", "{00000}"),
    ),
    BILL: (
        GROUP_BILLING,
        (
            "BL-{YY}{MM}-{000000}",
            "BILL-{YYYY}-{00000}",
            "INV-{YY}-{00000}",
            "{YYYY}{MM}{DD}-{0000}",
            "B{000000}",
            "{00000000}",
        ),
    ),
    PAYMENT: (
        GROUP_BILLING,
        ("PY-{YY}{MM}{DD}-{0000}", "PAY-{YYYY}-{00000}", "P-{000000}", "PMT-{YY}-{00000}", "{00000000}"),
    ),
    RECEIPT: (
        GROUP_BILLING,
        ("R-{0000}", "RCPT-{YY}{MM}-{000}", "REC-{000000}", "R{YYYY}-{00000}", "{000000}"),
    ),
    ADJUSTMENT: (GROUP_BILLING, ("ADJ-{000}", "ADJ-{YYYY}-{0000}", "A-{YY}{MM}-{000}", "{00000}")),
    CREDIT_MEMO: (GROUP_BILLING, ("CM-{0000}", "CR-{YYYY}-{000}", "CMEMO-{00000}", "{000000}")),
    WRITE_OFF: (GROUP_BILLING, ("WOF-{0000}", "WOF-{YYYY}-{0000}", "BD-{00000}", "{000000}")),
    # OQ-342: `RUN-{0000}` FIRST because the PO named the rendered string —
    # *"a real series (RUN-0001, like RT-001)"* — and a counter of 1 through
    # this format is exactly `RUN-0001`. Billing group, beside the BILL series
    # whose documents a run produces.
    BILL_RUN: (GROUP_BILLING, ("RUN-{0000}", "RUN-{YYYY}-{0000}", "BR-{YY}{MM}-{000}", "{000000}")),
    # ⚠ **THE SEEDED DEFAULT'S PAD WENT FROM `{00}` TO `{0000}` ON 2026-09-22
    # (`P0.6`), AND THE PO'S OWN EXAMPLE IS WHY.** Ruling of that date,
    # verbatim: *"(b) Put it in Settings today — **DEP-260922-0001** — Settings
    # → Numbering, like every other number"*. Four digits is the number they
    # wrote, and from that day the banking path ALLOCATES from this series
    # instead of composing `DEP-{YY}{MM}{DD}-{METHOD}` by hand, so this row
    # stopped being decorative and started numbering real deposits.
    #
    # ⚠ **A JUDGMENT RECORDED IN THE DECISION LOG SAID `{00}` WOULD "REACH
    # DEP-260922-99 AND THEN NOT ALLOCATE AT ALL". THAT IS NOT TRUE AND IS NOT
    # WHY THIS CHANGED.** `render` never truncates — *"a counter that outgrows
    # its pad keeps all its digits"* — so `{00}` at 100 renders
    # `DEP-260922-100`, unique and lawful; `will_overflow` is a WARNING the
    # Settings screen raises and its own docstring says *"never a refusal:
    # refusing would stop a bill run over cosmetics"*. **The same measurement
    # is why the yearly restart that judgment proposed was NOT taken**: it was
    # argued from "9,999 batches for ever", which is equally untrue, and it
    # would have put `numbering_restart_backdated` on a money path — cutting
    # last December's batch in January would be REFUSED by name. A cosmetic
    # gain is not worth a live refusal on the banking path.
    #
    # ⚠ **EXISTING TENANTS HOLD `{00}` IN A ROW THEY OWN AND ARE NOT MIGRATED.**
    # `_seed_number_series` is `get_or_create` per series, so a configured row
    # keeps ITS format and ITS counter; a seeded default governs a NEW tenant.
    # Changing what a utility has already configured is a different act and
    # nobody has ruled on it. They are reported, not rewritten — and they still
    # work, for the reason two paragraphs up.
    DEPOSIT_BATCH: (
        GROUP_BILLING,
        ("DEP-{YY}{MM}{DD}-{0000}", "DEP-{0000}", "BATCH-{YY}-{000}", "{00000}"),
    ),
    # ⚠ `JE-{MM}{DD}{YY}-{0000}` IS FIRST BY PO RULING OF 2026-09-23, verbatim:
    # *"you need je-MMDDYY- nnnn like this otherwise it will not work"*
    # (Finance blueprint `P0.13`). It SUPERSEDES `JE-{000000}`, which stood
    # here from CR-005 (2026-08-17) because BR-LED-021 named that exact string
    # as the seed. A worked figure: an entry dated **2 Aug 2026**, first of the
    # series, is **`JE-080226-0001`**.
    #
    # Measured against the BR-TEN-035 grammar BEFORE it was written here: the
    # format is **22 characters** against `MAX_FORMAT_LENGTH` 24, its pad is
    # **4** against `MAX_PAD` 8, it carries exactly one counter token, and
    # every date token in it ({MM} {DD} {YY}) is in `DATE_TOKENS`.
    # `validate_format` accepts it — `tests/test_p0_13_je_series_format.py`
    # asserts all four facts rather than trusting this comment (law 1).
    #
    # ⚠ **IT DOES NOT SORT CHRONOLOGICALLY AS TEXT, AND THAT IS KNOWN AND
    # ACCEPTED RATHER THAN SOMETHING TO BE DISCOVERED.** `JE-011526-0001`
    # sorts BEFORE `JE-020325-0001` though it is eleven months later, because
    # the MONTH leads the string. So **no list may order journal entries by
    # this number**: the S56 journal orders by `entry_date`
    # (`reporting.journal_entry_list`), and
    # `tests/test_p0_10_je_numbering_behaviour.py` pins the mis-sort as
    # DELIBERATE so a later lane cannot "fix" it into a chronological sort
    # that this format can never deliver.
    #
    # `JE-{000000}` is KEPT, second, so a tenant already on it stays on it and
    # nothing silently re-formats a series someone chose. r10 draws
    # `JE-{YYYY}-{0000}`; it follows.
    JOURNAL_ENTRY: (
        GROUP_FINANCE,
        (
            "JE-{MM}{DD}{YY}-{0000}",
            "JE-{000000}",
            "JE-{YYYY}-{0000}",
            "JRNL-{YY}{MM}-{000}",
            "J-{000000}",
            "{000000}",
        ),
    ),
    COLLECTIONS_NOTICE: (
        GROUP_FINANCE,
        ("CN-{YY}-{00000}", "NOTICE-{YYYY}-{0000}", "CN-{000000}", "{000000}"),
    ),
    EXPORT_BATCH: (GROUP_FINANCE, ("EXP-{YY}{MM}-{0000}", "EXP-{00000}", "GL-{YYYY}-{0000}", "{000000}")),
    #: ⚠ THE FIRST OPTION IS THE SEEDED DEFAULT, and it is `CON-{YY}-{0000}`
    #: because that is what the PO's own New Connect screens draw — `CON-26-0110`,
    #: `CON-26-0117`, `CON-26-0119` (B18 §5.4.9). The other four are offered, not
    #: implied: a utility that numbers straight through, or wants the full year,
    #: or prefixes differently, picks and the product does not argue.
    CONNECTION: (
        GROUP_WORK,
        ("CON-{YY}-{0000}", "CON-{YYYY}-{0000}", "CON-{0000}", "NC-{YY}{MM}-{000}", "{000000}"),
    ),
    WORK_ORDER: (
        GROUP_WORK,
        ("WO-{0000}", "WO-{YYYY}-{0000}", "JOB-{YY}{MM}-{000}", "W{000000}", "{000000}"),
    ),
    SERVICE_TEMPLATE: (GROUP_WORK, ("ST-{0000}", "TMPL-{000}", "SVC-{YYYY}-{000}", "{00000}")),
    DISPATCH_BATCH: (GROUP_WORK, ("DSP-{YY}{MM}{DD}-{00}", "DISP-{0000}", "DB-{YYYY}-{000}", "{00000}")),
    ASSET: (GROUP_ASSETS, ("AST-{00000}", "M-{0000}", "ASSET-{YYYY}-{000}", "{00000}")),
    READ_BATCH: (GROUP_ASSETS, ("RB-{YY}{MM}-{0000}", "READ-{YYYY}-{0000}", "RDB-{00000}", "{000000}")),
    ROUTE: (GROUP_ASSETS, ("RT-{000}", "ROUTE-{0000}", "R-{YY}-{000}", "{00000}")),
    CYCLE: (GROUP_ASSETS, ("CY-{000}", "CYC-{YYYY}-{000}", "C-{0000}", "{00000}")),
    IMPORT_RUN: (GROUP_ASSETS, ("IMP-{YY}{MM}{DD}-{00}", "RUN-{0000}", "RUN-{YYYY}-{000}", "{000000}")),
    #: ⚠ **APPENDED AT THE END OF THE DICT, NOT SLOTTED BESIDE `ACCOUNT`, AND
    #: THAT IS THE SAME REASONING `CUSTOMER`'s COMMENT CARRIES.** This dict's
    #: ORDER IS THE ORDER THE SETTINGS SCREEN PRINTS, and the frontend buckets
    #: the flat list BY GROUP (`SettingsNumberingTab` `groups`), so a
    #: `customers_premises` row appended here renders LAST inside *Customers &
    #: premises* and moves no shipped row at all.
    #:
    #: **GROUP — `customers_premises`, not `work`, and the choice is stated
    #: rather than assumed.** `connection` sits in `work` because a new connect
    #: is a FIELD job — somebody goes out and connects a service. A transfer is
    #: an ACCOUNT-lifecycle job: nobody is dispatched, the record lives in
    #: `apps/customers/transfers.py`, and S89 is a Customers screen. An admin
    #: hunting for *"Transfer #"* looks where accounts and premises are.
    #:
    #: **THE FIRST OPTION IS THE SEEDED DEFAULT AND THE PO NAMED ITS RENDERED
    #: STRING** — *"Transfer TRF-26-0001"* — so `TRF-{YY}-{0000}` leads and
    #: counter 1 in 2026 renders exactly that. The other three are OFFERED, not
    #: implied (BR-TEN-035 makes every one tenant-editable on S8). `TRF-`
    #: collides with none of the twenty-five prefixes already seeded.
    #:
    #: ⚠ **`MV-` IS DELIBERATELY NOT OFFERED.** OQ-426's option B noted that
    #: *move* is the product's own word but that it PRE-EMPTS CR-039 tasks
    #: 17–19 (move-in / move-out records), which are blocked on their own
    #: ruling. Offering it here would let a tenant pick a prefix for a
    #: vocabulary the PO has not been asked about yet.
    TRANSFER: (
        GROUP_CUSTOMERS,
        ("TRF-{YY}-{0000}", "TRF-{YYYY}-{0000}", "TRF-{0000}", "XFR-{YY}{MM}-{000}", "{000000}"),
    ),
    #: ⚠ **APPENDED, for the third time and the same reason** — this dict's ORDER
    #: IS THE ORDER S8 PRINTS, so a `customers_premises` row added at the end
    #: renders LAST inside *Customers & premises* and moves no shipped row.
    #:
    #: **GROUP — `customers_premises`, and `work` is the WRONG answer here for a
    #: sharper reason than it was for the transfer.** `connection` sits in `work`
    #: because a new connect is a FIELD job. A disconnect HAS a field job — r10
    #: draws it, `WO-4833` — and the PO's ruling (*"it needs its own series"*) is
    #: precisely the statement that the CASE is not that visit. Filing the case
    #: in the work group would blur the one distinction the ruling drew. The
    #: record lives in `apps/customers/disconnects.py` and S90 is a Customers
    #: tab, so this is where an admin hunting for *"Disconnect case #"* looks.
    #:
    #: **THE FIRST OPTION IS THE SEEDED DEFAULT AND IT IS THE BUILD'S CHOICE, NOT
    #: THE PO's.** The ruling delegated the format (decision log 2026-08-27), so
    #: `DSC-{YY}-{0000}` leads and a counter of 1 in 2026 renders exactly
    #: `DSC-26-0001` — the figure that question offered as its option A. The
    #: other four are OFFERED, not implied (BR-TEN-035 makes every one
    #: tenant-editable on S8), and the last is CR-005's mandatory bare counter.
    #:
    #: ⚠ **`WO-`-SHAPED IS DELIBERATELY NOT OFFERED HERE.** A tenant that wants
    #: its cases to read like work orders can type `WO-{0000}` into the format
    #: box — BR-TEN-035 allows it and CR-005 answers with a duplicate-prefix
    #: WARNING, never a block. Shipping it as a ready-made OPTION would offer
    #: back the answer the ruling rejected.
    DISCONNECT_CASE: (
        GROUP_CUSTOMERS,
        ("DSC-{YY}-{0000}", "DSC-{YYYY}-{0000}", "DSC-{0000}", "DISC-{YY}{MM}-{000}", "{000000}"),
    ),
    #: ⚠ **APPENDED, and these two are the fourth and fifth in a row** — the
    #: dict's ORDER IS THE ORDER S8 PRINTS, so `customers_premises` rows added
    #: at the end render last inside *Customers & premises* and move nothing.
    #:
    #: **GROUP — `customers_premises`, and this one is not a close call.** A
    #: move is an ACCOUNT-LIFECYCLE job: nobody is dispatched, the record lives
    #: in `apps/customers/moves.py`, and both flows are tabs on the Accounts
    #: page. `work` is where a FIELD job goes (`connection`).
    #:
    #: **THE FIRST OPTION IS THE SEEDED DEFAULT AND IT IS THE BUILD'S CHOICE.**
    #: The PO ruled the RECORD (*"you cna keep them as records for audit
    #: perpuses"*) and the decision log states in as many words that the ruling
    #: *"DOES NOT SETTLE D18's NUMBERING"*. See the `MOVE_IN` / `MOVE_OUT`
    #: comment above for why the build extends the disconnect's ruling rather
    #: than leaving these unnumbered — **one word from the PO reverses it.**
    #: `MVI-{YY}-{0000}` at counter 1 in 2026 renders `MVI-26-0001`;
    #: `MVO-{YY}-{0000}` renders `MVO-26-0001`.
    #:
    #: ⚠ **A SHARED `MV-` IS DELIBERATELY NOT OFFERED ON EITHER.** Offering it
    #: would let a tenant point both series at one prefix and then be unable to
    #: tell an arrival from a departure off the number — which is the exact
    #: property these two were split to preserve. A tenant that genuinely wants
    #: one vocabulary can still type it (BR-TEN-035 allows any valid format;
    #: CR-005 answers a duplicate prefix with a WARNING, never a block).
    MOVE_IN: (
        GROUP_CUSTOMERS,
        ("MVI-{YY}-{0000}", "MVI-{YYYY}-{0000}", "MVI-{0000}", "IN-{YY}{MM}-{000}", "{000000}"),
    ),
    MOVE_OUT: (
        GROUP_CUSTOMERS,
        ("MVO-{YY}-{0000}", "MVO-{YYYY}-{0000}", "MVO-{0000}", "OUT-{YY}{MM}-{000}", "{000000}"),
    ),
    #: ⚠ **APPENDED, for the sixth time and the same reason** — this dict's
    #: ORDER IS THE ORDER S8 PRINTS and the frontend buckets the flat list BY
    #: GROUP, so a `work` row added at the end renders LAST inside *Work &
    #: connections* and moves no shipped row.
    #:
    #: See the `INTERRUPTION_REPORT` comment above for the group choice and for
    #: why `RP-26-0412` is not an `SR-` number. The last option is CR-005's
    #: mandatory bare counter.
    INTERRUPTION_REPORT: (
        GROUP_WORK,
        ("RP-{YY}-{0000}", "RP-{YYYY}-{0000}", "RPT-{YY}{MM}-{000}", "OUT-{0000}", "{000000}"),
    ),
    #: ⚠ **APPENDED, for the seventh time and the same reason** — this dict's
    #: ORDER IS THE ORDER S8 PRINTS and the frontend buckets the flat list BY
    #: GROUP, so a `billing_payments` row added at the end renders LAST inside
    #: *Billing & payments* and moves no shipped row.
    #:
    #: `GROUP_BILLING` and not `GROUP_FINANCE`: a settlement is a payments
    #: record a counter supervisor opens beside the deposit batch, which is in
    #: this group. Finance holds the journal, the collections notice and the
    #: accounting export — what the BOOKS produce, not what the money did.
    #:
    #: The third option is the one a card processor's own statement usually
    #: carries (a payout per day), offered rather than implied.
    SETTLEMENT: (
        GROUP_BILLING,
        ("STL-{YY}-{0000}", "STL-{YYYY}-{0000}", "STL-{YY}{MM}{DD}-{00}", "STL-{0000}", "{000000}"),
    ),
    #: ⚠ **APPENDED, for the eighth time and the same reason** — this dict's
    #: ORDER IS THE ORDER S8 PRINTS and the frontend buckets the flat list BY
    #: GROUP, so a `billing_payments` row added at the end renders LAST inside
    #: *Billing & payments*, after Settlement, and moves no shipped row.
    #:
    #: `CC-{YYYY}-{000}` FIRST because the PO ruled it (G3, 2026-10-14). The
    #: others are the catalogue's usual shapes; the last is CR-005's mandatory
    #: bare counter.
    CORRECTION_CASE: (
        GROUP_BILLING,
        ("CC-{YYYY}-{000}", "CC-{YY}-{0000}", "FIX-{YYYY}-{0000}", "CC-{00000}", "{000000}"),
    ),
}

#: Storage rows are still the truth; this is the documented set (32 as of G3's
#: correction-case series, 2026-10-14; 31 at the payments blueprint's `P0.13`
#: settlement series; 30 at CR-068 wave B's
#: `interruption_report`, 24 at CR-030 W0's customer series,
#: 23 after OQ-342, 22 after CR-005, nine before it).
KNOWN_SERIES = frozenset(SERIES_CATALOG)

# ── BR-TEN-035 format grammar ───────────────────────────────────────────────
# Tokens: {YYYY} {YY} {MM} {DD} (issue date, tenant timezone) + exactly one
# zero-padded sequence token {0…0} whose length IS the pad width.
DATE_TOKENS = ("YYYY", "YY", "MM", "DD")
YEAR_TOKENS = ("YYYY", "YY")
MONTH_TOKEN = "MM"
_TOKEN_RE = re.compile(r"\{([^{}]*)\}")
_SEQUENCE_TOKEN_RE = re.compile(r"^0+$")

# CR-005 (BR-TEN-035 clause (a)), verbatim: *"validated: max 1 counter, only
# allowed tokens, ≤ 24 chars"* and *"counter {0000…} (pad length 4–8)"*.
MAX_FORMAT_LENGTH = 24
MAX_PAD = 8
# ⚠ THE PAD MINIMUM OF FOUR IS DELIBERATELY NOT A CONSTANT HERE — OQ-250. The
# shipped `ADJ-{000}` default (pad 3, seeded into every tenant since
# provisioning began) and nine of r10 SET-08's own dropdown options sit below
# it, so enforcing it would refuse formats the product already stores and the
# design already draws — on a row the admin never touched. A short pad is not
# unsafe: `render` never truncates, so `ADJ-{000}` at 1,000 is `ADJ-1000`.

# ── CR-005 restart periods (BR-TEN-035 clause (b)) ──────────────────────────
RESTART_NEVER = "never"
RESTART_YEARLY = "yearly"
RESTART_MONTHLY = "monthly"
RESTART_PERIODS = (RESTART_NEVER, RESTART_YEARLY, RESTART_MONTHLY)

#: The restart period a NEW tenant's row is seeded with, where it is not
#: `RESTART_NEVER`. One entry: the correction case (G3 — see `CORRECTION_CASE`).
#: Every other series is seeded never-restarting, as it always was. A seeded
#: default the tenant edits, never a rule.
SERIES_DEFAULT_RESTART: dict[str, str] = {CORRECTION_CASE: RESTART_YEARLY}


class NumberingError(RuntimeError):
    """Kernel misuse or unusable series state — an issuance may not proceed
    without its number, so this aborts the issuing transaction loudly."""


# The sink: one callable, one series key + the ISSUE DATE in, (format,
# sequence) out — the SELECT FOR UPDATE allocation itself lives with the
# number_series owner.
#
# ⚠ THE ISSUE DATE JOINED THIS SIGNATURE WITH CR-005 AND IT HAD TO. The restart
# period (BR-TEN-035 clause (b)) is decided by WHICH PERIOD THE NUMBER IS BEING
# ISSUED INTO, and the storage row is the only place that can compare that
# against the period it last counted in — atomically, under the same row lock
# that hands out the sequence. Passing the date is what lets the sink do it
# without reading a clock (BR-TEN-043) and without a second round trip.
SeriesSink = Callable[[str, date], tuple[str, int]]
_sink: SeriesSink | None = None


def set_series_sink(sink: SeriesSink | None) -> None:
    """Register (or clear, with None) the allocation sink. apps.tenancy only."""
    global _sink
    _sink = sink


def validate_format(format_string: str) -> None:
    """BR-TEN-035 grammar check; raises catalog VAL-002 with the specific problem.

    Used by the S8 settings save (US-TEN-012 TC-4: reject with the specific
    problem, Save blocked) and defensively at allocation time — a malformed
    stored format must fail loudly, never misprint a document number.
    """
    from core import errors  # local import: kernels stay decoupled at import time

    def refuse(problem: str, **params: str) -> None:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="settings.numbering.format_invalid",
            params={"problem": problem, **params},
        )

    if not format_string or not format_string.strip():
        refuse("empty")
    # A stray { or } would silently drop the token from the scan — name the
    # typo before diagnosing what tokens remain.
    if format_string.count("{") != format_string.count("}"):
        refuse("unbalanced_braces")
    sequence_tokens = 0
    for token in _TOKEN_RE.findall(format_string):
        if _SEQUENCE_TOKEN_RE.match(token):
            sequence_tokens += 1
        elif token not in DATE_TOKENS:
            refuse("unknown_token", token="{" + token + "}")
    if sequence_tokens == 0:
        refuse("no_sequence_token")
    if sequence_tokens > 1:
        refuse("multiple_sequence_tokens")
    # CR-005 clause (a). Checked AFTER the token scan on purpose: "too long" is
    # a useless thing to be told about a format whose real problem is a typo'd
    # token, and the length is the cheapest problem to fix once the shape is
    # right.
    if len(format_string) > MAX_FORMAT_LENGTH:
        refuse("too_long", max=str(MAX_FORMAT_LENGTH), length=str(len(format_string)))
    if pad_length(format_string) > MAX_PAD:
        refuse("pad_too_long", max=str(MAX_PAD))


def pad_length(format_string: str) -> int:
    """Digits in the counter token — the pad width. 0 when there is no counter
    (only reachable from `validate_format`, which refuses that case itself)."""
    for token in _TOKEN_RE.findall(format_string):
        if _SEQUENCE_TOKEN_RE.match(token):
            return len(token)
    return 0


def literal_prefix(format_string: str) -> str:
    """The literal characters before the first token — what CR-005 calls the
    prefix when it asks for a warning on *"duplicate prefixes across entities"*.

    A format that OPENS with its counter (`{00000}`, the mandatory plain option)
    has an EMPTY prefix, and empty prefixes are never "duplicates" of each
    other: every plain series would otherwise warn against every other plain
    series, which is the one configuration the CR calls mandatory.
    """
    head, brace, _ = format_string.partition("{")
    return head if brace else format_string


def will_overflow(format_string: str, next_no: int) -> bool:
    """CR-005 clause (c): is the counter already past what its pad can show?

    `ADJ-{000}` at 1,000 renders `ADJ-1000` — four digits in a three-digit pad.
    Nothing breaks (numbers stay unique and sortable-by-value, if not by
    string), so this is a WARNING the screen raises, never a refusal: refusing
    would stop a bill run over cosmetics.
    """
    pad = pad_length(format_string)
    return pad > 0 and next_no >= 10**pad


def period_key(restart_period: str, issue_date: date) -> str:
    """Which counting period `issue_date` falls in, for this restart setting.

    `""` when the series never restarts — one unbroken counter, which is what
    every series stored before CR-005 has and keeps.
    """
    if restart_period == RESTART_YEARLY:
        return f"{issue_date.year:04d}"
    if restart_period == RESTART_MONTHLY:
        return f"{issue_date.year:04d}-{issue_date.month:02d}"
    return ""


def validate_restart_period(format_string: str, restart_period: str) -> None:
    """BR-TEN-035 clause (b) / OQ-252 — the guard that keeps a restart from
    re-minting a number a customer already has.

    Yearly restart needs a YEAR token; monthly needs a MONTH token AND a year
    token. `{MM}-{0000}` restarted monthly repeats every January, which is the
    same duplicate one boundary further out.
    """
    from core import errors

    if restart_period not in RESTART_PERIODS:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="settings.numbering.restart_unknown",
            params={"restart_period": str(restart_period)},
        )
    if restart_period == RESTART_NEVER:
        return
    tokens = set(_TOKEN_RE.findall(format_string))
    has_year = any(token in tokens for token in YEAR_TOKENS)
    if restart_period == RESTART_YEARLY and not has_year:
        _refuse_restart("needs_year_token")
    if restart_period == RESTART_MONTHLY and (MONTH_TOKEN not in tokens or not has_year):
        _refuse_restart("needs_year_and_month_tokens")


def _refuse_restart(problem: str) -> None:
    from core import errors

    raise errors.ValidationError(
        errors.VAL_FORMAT,
        message_key="settings.numbering.restart_invalid",
        params={"problem": problem},
    )


def render(format_string: str, sequence: int, issue_date: date) -> str:
    """One number from format + counter value + explicit issue date. Pure —
    rendering never touches storage, so an issued number can never be
    recomputed differently later (it was stamped once, forever)."""
    validate_format(format_string)
    if sequence < 0:
        raise NumberingError(f"sequence {sequence} is negative — counters are monotonic")

    def fill(match: re.Match) -> str:
        token = match.group(1)
        if _SEQUENCE_TOKEN_RE.match(token):
            # Pad = token length; a counter that outgrows its pad keeps all its
            # digits (never truncated — truncation could collide, BR-TEN-035).
            return str(sequence).zfill(len(token))
        return _date_token_values(issue_date)[token]

    return _TOKEN_RE.sub(fill, format_string)


def next_number(series: str, issue_date: date) -> str:
    """Allocate + render the next number for a series — call INSIDE the issuing
    transaction (BR-TEN-035). The B12 §6a sketch `numbering.next("BL", tenant)`
    maps here with one kernel-lane correction: tenant comes from app.tenant_id
    context, NEVER a caller parameter — a caller cannot number into another
    tenant's series (same law as the audit writer, backed by RLS).
    """
    if not series:
        raise NumberingError("a series key is required (BR-TEN-035)")
    if not isinstance(issue_date, date):
        # BR-TEN-043: the caller names the business event's date explicitly;
        # this kernel refuses to guess "today" on its behalf.
        raise NumberingError("issue_date must be an explicit date (event-time law, BR-TEN-043)")
    if current_tenant_id() is None:
        raise NumberingError(f"no tenant context set for series {series!r} — refuse, never guess")
    if _sink is None:
        raise NumberingError(f"no series sink registered — cannot allocate {series!r} number")
    # CR-005: the sink needs the date to decide a period restart under the same
    # row lock that hands out the sequence (BR-TEN-035 clause (b)).
    format_string, sequence = _sink(series, issue_date)
    return render(format_string, sequence, issue_date)


def _date_token_values(issue_date: date) -> dict[str, str]:
    """The four date tokens' literal text for one date — the SAME mapping
    `render` fills with, kept in one place so the writer and the reader below
    can never disagree about what a `{YY}` looks like."""
    return {
        "YYYY": f"{issue_date.year:04d}",
        "YY": f"{issue_date.year % 100:02d}",
        "MM": f"{issue_date.month:02d}",
        "DD": f"{issue_date.day:02d}",
    }


def sequence_of(format_string: str, value: Any, issue_date: date) -> int | None:
    """🔒 HUMAN-REVIEW-PENDING (numbering, DEF-577 — row in 12-governance/09-human-review-ledger.md).

    THE INVERSE OF `render` FOR ONE ISSUE DATE: which counter value would this
    format have had to stand at to produce `value` on `issue_date` — or None
    when this format could not have produced it at all, at any counter value.

    It exists to answer ONE question, and only that question: *is a number the
    series is about to hand out already in the table?* (DEF-577 — the `unit`
    series stood at 102 on the demo database while units up to `U-00420` were
    already on file, so the next "Add unit" raised a duplicate key.) The answer
    has to be exact in BOTH directions:

    * A number this format CAN produce must be recognised, or the catch-up
      stops short of it and the collision happens anyway.
    * A number it CANNOT produce must be refused, or a customer's own numbering
      drags the counter somewhere it never needed to go. `SCW-U-001` is not a
      `U-{00000}` number at any counter value; neither is `P-9001`, because
      `P-{00000}` at 9,001 renders `P-09001`. Both are returned as None.

    Exactness is bought by RE-RENDERING rather than by trusting the scan: the
    digits are read out with a regex, then `render` is asked what it would have
    written for them, and the answer only counts if it is character-identical.
    That makes this function correct by construction against the one thing it
    has to agree with.

    DATE TOKENS ARE PINNED TO `issue_date` (BR-TEN-043 — no clock is read here).
    A collision can only ever be with a number whose non-counter characters are
    identical to what would be rendered today, so `P-2025-0007` is simply not a
    candidate for a `P-{YYYY}-{0000}` issuance dated in 2026 — it is a different
    number and cannot be re-minted by today's counter.
    """
    if not isinstance(issue_date, date):
        raise NumberingError("issue_date must be an explicit date (event-time law, BR-TEN-043)")
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    validate_format(format_string)

    pattern: list[str] = []
    cursor = 0
    for match in _TOKEN_RE.finditer(format_string):
        pattern.append(re.escape(format_string[cursor : match.start()]))
        token = match.group(1)
        if _SEQUENCE_TOKEN_RE.match(token):
            # The pad is not asserted here — an overflowed counter keeps all its
            # digits (`ADJ-{000}` at 1,000 is `ADJ-1000`), and the re-render
            # below is what refuses a wrongly padded lookalike.
            pattern.append(r"(\d+)")
        else:
            pattern.append(re.escape(_date_token_values(issue_date)[token]))
        cursor = match.end()
    pattern.append(re.escape(format_string[cursor:]))

    found = re.fullmatch("".join(pattern), text)
    if found is None:
        return None
    sequence = int(found.group(1))
    return sequence if render(format_string, sequence, issue_date) == text else None


def preview(format_string: str, next_no: int, issue_date: date) -> str:
    """The S8 live preview (US-TEN-012): what the NEXT number would look like.
    Validates + renders only — allocates nothing, advances nothing."""
    return render(format_string, next_no, issue_date)


def ensure_forward_only(current_next: int, proposed_next: int) -> None:
    """BR-TEN-035: next-number edits are forward-only (≥ current) — a backward
    edit could re-mint a number already stamped on an immutable row
    (US-TEN-012 TC-5: 'must be ≥ current'; collision impossible by construction).
    """
    if proposed_next < current_next:
        from core import errors

        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="settings.numbering.next_number_backward",
            params={"min": current_next},
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-06@05736ee (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-06..BE-09)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest tests/test_be06_numbering.py 16/16✔ (live number_series TCs land with US-TEN-012) · suite 147/147✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (BR-TEN-035 status PROPOSED not CONFIRMED-frozen in US-TEN-012 §2 vs CONFIRMED in the BR register · payment-series default prefix PY- (prototype/US-TEN-012 §4) vs PMT- (r12 #13, EP-PAY-01, search test data))
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
