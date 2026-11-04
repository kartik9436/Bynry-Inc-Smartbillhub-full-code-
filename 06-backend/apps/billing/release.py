# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (S31 step 5 — the summary, the gate and the release)
#           Screens: S31 step 5 · S31 step 6
# Rules:    BR-BIL-056 (the pre-release summary: four figures CONFIRMED; its
#           "frozen as shown" half SUPERSEDED 2026-08-11, option B — the screen
#           RECALCULATES) · BR-BIL-064 (the panel follows the CORRECTION CHAIN,
#           not `bill_run_id` — PO 2026-08-11, OQ-111 option A; CONFIRMED as a
#           rule and blocked on a column that does not exist) ·
#           BR-BIL-057 (the category axes — PROPOSED, the PO
#           said "various categories" and enumerated none) · BR-BIL-058 (the
#           gate is FIVE separately recorded facts) · BR-BIL-059 (each
#           confirmation is shown against its coverage, and coverage NEVER
#           blocks a release) · BR-BIL-055 (a break never blocks the run) ·
#           BR-BIL-053 ("mark for later" is a staff decision) · BR-BIL-051
#           (the downstream work is a background batch) · BR-BIL-023 (issue
#           covers all remaining drafts or a subset) · BR-TEN-043 (event time
#           is named by the caller, never read from a clock) · CLAUDE.md rule 1
#           (tenant scoping) · rule 2 (money + currency) · rule 3 (a quantity
#           carries its unit) · rule 4 (financial records are append-only) ·
#           rule 7 (every money action writes audit_log)
# Change:   CR-048 wave B follow-up (2026-08-30) — `release_run` now sends the
#           ONE staff message a finished bill run owes its operator, through
#           `apps/billing/run_alert_seam.py`. Nothing else in this file moved.
# Tests:    06-backend/tests/test_us_bil_005_release.py (this module) ·
#           06-backend/tests/test_us_bil_005_release_gate.py (the ROW it writes) ·
#           06-backend/tests/test_cr048_staff_alerts_wired.py (the staff alert)
# Impacts:  apps/billing/issue.issue_run (phase 5 calls it; the release gate it
#           enforces is the row THIS module writes) · apps/billing/runs.py
#           (phases 1-3, upstream) · S31 step 5 renders `summary_for` ·
#           apps/billing/run_alert_seam.py (the notifications seam phase 5 now
#           calls; `ReleaseOutcome.staff_alert` carries what it did)
# ───────────────────────────────────────────────────────
"""Phases 4 and 5 of the bill run: the summary, the release gate, the release.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this decides what a human authorises
before money goes out, and it is the last moment at which nothing has been
billed (CLAUDE.md 🔒). AI-authored 2026-08-11 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

The PO described the whole flow on 2026-08-11, verbatim:

    *"…then show the billing summary in how many accounts, how many bills
    generated, how much consumption and how much bill amount and various
    categories; take final confirm from user, compliance confirmation, emails,
    text mandates, auto pay mandates and then release the bills and run the
    batches in background for downstream jobs"*

`summary_for` is the first clause, `authorise_release` the second and
`release_run` the third. Phases 1-3 are `apps/billing/runs.py`.

THE SUMMARY IS A QUERY, AND THAT IS A REVERSAL
----------------------------------------------
BR-BIL-056 used to say the summary was written once at confirm and never
recomputed. **The Product Owner overturned that half on 2026-08-11.** They were
shown it in their own worked figure:

    "You approve 480 bills, $52,847.19. Two bills are voided next week. The
     screen still says 480 / $52,847.19, because that's what you approved."

    A · keep frozen ("what did I approve?")
    B · recalculate live ("what do these total today?")
    C · show both, side by side.

**They chose B.** So `summary_for` computes from the run's CURRENT bills on
every call and holds no cache. A voided bill leaves the figures; re-opening the
run shows 478, not 480.

What that ruling did NOT touch is the RECORD. `authorise_release` writes what
was on screen at sign-off into `bill_run_releases` and nothing ever rewrites it
(hard rule 4). After the ruling that row is the ONLY answer to *"what did I
authorise?"* — the screen no longer answers it — which makes it load-bearing
evidence rather than a stale cache. A frozen column beside a live screen is the
design. `models.BillRunRelease`'s docstring argues it at length.

WHY CONSUMPTION IS THE FIGURE THIS MODULE FUSSES OVER
-----------------------------------------------------
The four figures the PO named are all required (BR-BIL-056, CONFIRMED), and
consumption is the one people forget. A total in dollars cannot tell a utility
that a run is wrong; 412,880 kWh against a normal month can. So it obeys
CLAUDE.md rule 3 without exception:

  * every quantity carries its unit, and a usage line with a quantity and no
    unit is a REFUSAL, never a zero and never a silent drop;
  * nothing is ever summed across units. The group key is (service, unit), so
    a tenant metering water in kgal on one route and m3 on another sees two
    rows rather than a plausible total of neither;
  * a quantity that cannot be attributed to a service is shown as
    `service_code=None` and NAMED in `problems`. It is not guessed from the
    unit — water and sewer both meter in kgal — and it is not dropped, because
    dropping it understates the only figure that exists to be checked.

Money obeys rule 2 the same way: an amount always carries its currency, and a
run whose bills are not all in one currency is refused rather than summed.

WHAT THIS MODULE REFUSES TO DECIDE
----------------------------------
**BR-BIL-057 (the category AXES) is PROPOSED.** The PO said *"and various
categories"* and enumerated none. So what ships is the axes derivable from what
the run already knows, each labelled with its axis name, `axes_status` reads
`"PROPOSED"`, and the axes BR-BIL-057 proposes that this deployment cannot
derive are named in `problems` rather than quietly absent — a missing axis and
an empty axis look identical on a screen. **The SET is not settled and nothing
here may be read as settling it.**

**OQ-111 IS CLOSED (PO 2026-08-11) AND SINCE 2026-08-12 IT IS FULLY BUILT.**
The ruling, verbatim: *"A Replacement counts (panel = what these customers owe
now)"*. Both halves now hold: a rebill carrying this run's `bill_run` is COUNTED
like any other bill, and a SUPERSEDED original is shown at its replacement's
current figure — `current_position_bills` walks
`invoices.corrects_invoice_id` (`CHAIN_COLUMN`) from each of the run's bills to
the head of its chain.

⚠ THIS PARAGRAPH USED TO SAY THE OPPOSITE, and it said so correctly at the
time. Until the PO closed **OQ-120** on 2026-08-12 (*"Nod to add the link on
the new bill"*) there was no column to follow, and a run holding a superseded
bill raised `BillingRuleError` naming the column that did not exist. Migration
`0017` added it; the refusal is gone. What SURVIVES of that refusal is narrower
and still right: a bill marked `corrected` that NOTHING replaces cannot be
resolved, and the panel refuses for it rather than showing one of the two
reachable-but-wrong figures — the original's own total (which nobody owes) or
$0.00 (which is what dropping it like a VOID would show).

❄️ Worked on the PO's own case: **$117.01** issued to ACC-1042 in run 1 and
corrected to **$104.20** by a rebill in run 2 makes run 1's panel read
**$104.20 · 1 bill · 1 account**.

**A CREDIT NOTE WITH NO REPLACEMENT COUNTS TOO — OQ-121, CLOSED BY THE PO ON
2026-08-12.** Verbatim: *"no rebill , Count it like a replacement"*. A class-C
correction (goodwill) writes a credit note and issues no rebill, so there is no
second invoice to count in the original's place; the CREDIT plays that part
instead. On ❄️ GT-6's frozen shape — a **$25.00** credit against a **$247.30**
invoice — the panel reads **$222.30**: the bill is counted, never dropped, and
the figure moves by the credit. A corrected account is therefore not invisible
to the person signing the run off, which is the question the PO was asked.

This module used to REFUSE that case as an unanswered question, stubbed against
OQ-121, because the OQ-111 ruling named a MECHANISM (the replacement) that a
credit-only correction does not produce. That refusal is gone — the PO supplied the
mechanism. **Nothing is written and nothing is touched**: the credit note is
already its own row with its own balanced posting (`corrections.
execute_credit_only` — DR write-off / CR customer credit balance), and this is a
READ of it. The issued invoice keeps its own total forever (hard rule 4).

**BR-BIL-059's coverage counts** are "stored as shown", and the option-B ruling
was put about bills and amount — it never named the coverage counts. So whether
a re-opened run recomputes them is a question for the PO. This module computes
them at call time (a query cannot do otherwise) and carries
`SUMMARY_COVERAGE_BASIS_UNRULED` so the question travels with the answer.

WHAT "BACKGROUND" MEANS TODAY: THE CALLER CHOOSES, AND IT IS REAL EITHER WAY
---------------------------------------------------------------------------
The PO asked for the downstream jobs to *"run the batches in background"*.

⚠ **THIS SECTION WAS HEADED "NOT BACKGROUND" AND SAID SO IN A SENTENCE THAT WAS
ALSO SERVED TO EVERY CALLER, AND IT HAD BEEN FALSE FOR TWELVE DAYS — corrected
2026-08-31 (CR-051 task 4, hard-won law 1).** It read: *"There is no worker on
this deployment — `celery` is a declared dependency with zero `tasks.py`, and
`JOBS_EAGER` runs a job body in-process (TD-17, open). So `release_run` runs the
issue pass INLINE and holds its caller."* **Every clause has expired.** CR-017
landed the worker on 2026-08-19: `apps/tenancy/tasks.py` exists, `config/celery.py`
is the app, `docker-compose.yml` runs the broker and the workers, and
`JOBS_EAGER=False` in production. CR-051 then made billing a caller of it —
`apps/billing/run_jobs.ISSUE_JOB`, whose body calls **this module's own
`release_run`** — and CR-051 task 29 gave those jobs their own `billing` queue
and their own `celery-billing` worker with its own CPU share.

**SO THE TRUE SENTENCE IS: `POST .../issue` with `background: true` hands this
pass to a worker and answers 202 with the poll address; without it, `release_run`
runs INLINE and holds its caller exactly as it always has.** The default is
inline because no timing figure for an issue pass of any size exists yet, and a
threshold chosen without one would be an invented number. If background is asked
for where nothing would drain billing's queue, the pass runs inline and says so
rather than queueing into a void (law 3 — the unsafe option must be the one you
type).

Every downstream batch is still named on the outcome with the rule it owes and
whether it `ran`. Stated rather than implied, because a caller reading "released"
would otherwise assume the bills went out.

Two of them now DO run, both inside the per-bill issue transaction: the
document render (BR-BIL-033) and the delivery-queue write (BR-BIL-016, amended
2026-08-11 — `apps/billing/delivery_seam.py`). **Neither means a bill reached a
customer.** The render proves the bill CAN be rendered and keeps nothing; the
queue write leaves rows resting `queued` and contacts no provider, because
there is no dispatcher and email ACTIVATION is R4 on the B12 release table. A
released run in R2 ends with every bill printed-to-nowhere and queued-to-
nobody, and `RELEASE_HANDOFFS` says exactly that rather than letting `ran: True`
be read as "sent".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Abs

from apps.billing import corrections, issue, models, run_alert_seam, runs
from apps.billing.exceptions import BillingRuleError
from core import audit, errors
from core import tenancy as core_tenancy

#: The bills a run's summary counts. Every status EXCEPT void, which is the
#: exact set the PO's option-B example fixes: *"two bills are voided next week"*
#: and the panel drops them. A draft counts because phase 4 runs BEFORE issue —
#: the whole point of the panel is to show what is about to go out.
COUNTED_OUT_STATUSES: tuple[str, ...] = (models.INVOICE_VOID,)

#: A bill that has been REPLACED. `corrected` is written on the original by an
#: R-class correction (EP-BIL-04 US-BIL-015 TC-1: *"original → `corrected`"*),
#: which also issues a rebill carrying the customer's current position. Under
#: the PO's OQ-111 ruling the panel must show the REPLACEMENT's figure for this
#: account, so a superseded original is never counted at its own total — and,
#: and IS swapped for its replacement since 2026-08-12 — see
#: `current_position_bills`, which walks `CHAIN_COLUMN` to the head of the chain.
SUPERSEDED_STATUSES: tuple[str, ...] = (models.INVOICE_CORRECTED,)

#: THE CHAIN COLUMN, named so a grep from either side finds it. The chain has
#: two legs and this repo now has both: `credit_notes.original_invoice_id`
#: gives original ← credit note, and `invoices.corrects_invoice_id` gives
#: replacement → original (migration `0017`, PO 2026-08-12 closing OQ-120 —
#: *"Nod to add the link on the new bill"*). `selectors.invoice_detail` reads
#: the same column in both directions to serve the API's `rebill_of_invoice_id`
#: / `corrected_by_invoice_id`, which were null on every row until it existed.
#:
#: ⚠ RENAMED FROM `CHAIN_COLUMN` on 2026-08-15. The old name described
#: an absence and the column is present; a constant that says MISSING about
#: something built is exactly the stale comment hard-won law 1 is about.
CHAIN_COLUMN = "invoices.corrects_invoice_id"
CHAIN_API_FIELDS: tuple[str, ...] = ("rebill_of_invoice_id", "corrected_by_invoice_id")
#: The ruling that put the column there. CLOSED — never cite this as an open
#: question or as a stub id (gate G8 rejects a stub against a closed id).
CHAIN_SCHEMA_OQ = "OQ-120"
CHAIN_SCHEMA_RULING = "Nod to add the link on the new bill"
CHAIN_SCHEMA_RULING_DATE = "2026-08-12"

#: BR-BIL-058's five facts, in the order the PO listed them, paired with the
#: column each is recorded in. The fifth has no boolean column and must not get
#: one: it is recorded as WHO confirmed and WHEN, which is a stronger fact than
#: a tick and is what an auditor actually asks for.
CONFIRMATION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("compliance", "compliance_confirmed"),
    ("email_mandate", "email_mandate_confirmed"),
    ("sms_mandate", "sms_mandate_confirmed"),
    ("autopay_mandate", "autopay_mandate_confirmed"),
)
FINAL_CONFIRMATION = "final"

#: Problem codes carried on a summary. CODES, never prose: the phase-4 panel
#: groups on them and a screen cannot group on a sentence.
SUMMARY_NO_COUNTABLE_BILLS = "run_has_no_countable_bills"
SUMMARY_SERVICE_UNATTRIBUTED = "consumption_not_attributable_to_a_service"
SUMMARY_AXES_PROPOSED = "category_axis_set_is_proposed"
SUMMARY_AXIS_UNAVAILABLE = "category_axis_not_derivable"
SUMMARY_COVERAGE_UNAVAILABLE = "mandate_coverage_not_derivable"
SUMMARY_COVERAGE_BASIS_UNRULED = "coverage_counts_live_or_stored_unruled"
SUMMARY_CREDITS_NETTED = "credit_notes_with_no_replacement_netted"
SUMMARY_SERVICE_AXIS_GROSS = "service_axis_is_gross_of_credit_notes"

#: The PO's own words closing OQ-121, 2026-08-12. Kept as a VALUE so the panel,
#: the stored payload and the test all quote the ruling rather than paraphrase
#: it — a paraphrase is what drifts (hard-won law 1).
CREDIT_ONLY_RULING = "no rebill , Count it like a replacement"
CREDIT_ONLY_RULING_DATE = "2026-08-12"

#: The customers read this module would need to show email / SMS coverage
#: (BR-BIL-059). Named once so the contract is greppable from BOTH sides of the
#: boundary, the way `issue.GL_REVENUE_READ` names the ledger's.
#:
#: Billing has ONE reviewed cross-module FK into customers —
#: `invoices.account_id → customers.Account` (B2 §2) — so it may read columns
#: ON that row and join the PLATFORM catalogs (`services`, `account_types`,
#: which carry no tenant_id and are seeded install-wide). It may NOT reach
#: customers' own tenant-owned satellites: `contacts` holds the email address
#: and `account_statuses` holds the BR-CUS-055 behaviour class, and both are
#: customers' internals. Those go through a published selector or they do not
#: happen (B1). Customers has published none, so they do not happen, and the
#: absence is NAMED on the summary rather than rendered as a zero.
COVERAGE_MODULE = "customers"
COVERAGE_READ = "mandate_coverage_for_accounts"

#: BR-BIL-057's proposed axes that this deployment cannot derive, with the
#: reason each is missing. Reported on every summary: an axis that is absent
#: because the data does not exist looks exactly like an axis with no rows.
UNDERIVABLE_AXES: tuple[dict[str, str], ...] = (
    {
        "axis": "delivery_channel",
        "br_ref": "BR-BIL-016",
        "detail": "AMENDED 2026-08-11 — this used to say issue writes no delivery record, "
        "and it does now (`delivery_seam.queue_bill_delivery`). The axis is still not "
        "derivable HERE, for a different and permanent reason: this panel is drawn at "
        "phase 4, BEFORE the release, and the rows are written at issue. There is nothing "
        "to group on because nothing has been queued yet — a run's channel breakdown is "
        "the per-run delivery dashboard's (US-BIL-024, S30), after the fact. A second "
        "reason stands behind it: the account delivery ELECTION (`accounts.paperless`) is "
        "PROPOSED-SCHEMA and unbuilt, so even after issue every bill carries exactly the "
        "BR-BIL-036 print floor and the axis would have one value.",
    },
    {
        "axis": "behavior_class",
        "br_ref": "BR-CUS-055",
        "detail": "the billable / billable-base-only class lives on customers' own "
        "`account_statuses` lookup, which is tenant-owned and tenant-extensible. Billing's "
        "reviewed FK reaches the account row, not that table, and customers publishes no "
        "selector for it.",
    },
    {
        "axis": "exception_state",
        "br_ref": "BR-BIL-029",
        "detail": "over-guardrail, estimated and late-fee-bearing are not columns on a bill. "
        "The guardrail flag has no store (BR-BIL-054) and `estimated` lives inside each "
        "bill's locked payload, which is a per-document snapshot and not a groupable axis.",
    },
)

#: What phase 5 does NOT do, carried on every outcome. Same discipline as
#: `issue.ISSUE_UNAVAILABLE`: a caller must not have to infer an absence, and a
#: reviewer must not have to take a docstring's word for it (hard-won law 1).
RELEASE_HANDOFFS: tuple[dict[str, Any], ...] = (
    # ⚠ **THE ENTRY THAT STOOD HERE — `not_run_in_background`, `ran: False` —
    # SAID "There is no worker on this deployment: `celery` is a declared
    # dependency with zero `tasks.py` … The work the batch will do exists; the
    # batch does not." IT WAS FALSE FROM 2026-08-19 AND IT WAS SERVED ON EVERY
    # RELEASE RESPONSE UNTIL 2026-08-31 (CR-051 task 4).** `api.py` retracted the
    # same claim in its own two tuples on 2026-08-30 and this THIRD copy, in
    # another module, was not looked for — which is why the replacement is a
    # `ran: True` statement of what actually happens rather than a deletion.
    {
        "code": "issue_runs_in_a_worker_when_the_caller_asks",
        "br_ref": "BR-BIL-051",
        # TRUE of the pass as a whole: `POST .../issue` with `background: true`
        # runs THIS function inside `run_jobs.ISSUE_JOB` on billing's own queue.
        # `ran: True` is a statement about the TRANSPORT and about nothing
        # downstream — every other entry in this tuple still says for itself
        # whether its own batch ran.
        "ran": True,
        "detail": "the PO asked for the downstream work to run as background batches, and "
        "phase 5 does when the caller asks for it: `POST /billing/runs/{id}/issue` with "
        "`background: true` hands this pass to a BE-07 worker and answers 202 with the poll "
        "address, so a clerk is not held while 1,122 bills issue. Billing's three job kinds "
        "ride their own `billing` queue, drained by the `celery-billing` service, so a bill "
        "run cannot queue behind a CSV export and a CPU limit aimed at billing does not "
        "touch customers' outbound notices. WITHOUT `background: true` this pass runs INLINE "
        "and holds its caller, which is still the default: no timing figure for an issue "
        "pass of any size exists in this product, and choosing a threshold without one would "
        "be inventing a number. If background is asked for where nothing would drain the "
        "billing queue, the pass runs inline and the response says so rather than accepting "
        "work that would rest `queued` for ever.",
    },
    {
        "code": "document_rendered_at_issue_but_not_stored",
        "br_ref": "BR-BIL-033 · BR-BIL-036",
        "ran": True,
        "detail": "AMENDED 2026-08-11 — this used to read `document_render_not_run` with "
        "`ran: False`, because BR-BIL-033 was CONFIRMED and unsatisfiable: there was no "
        "renderer. There is one. `issue_invoice` calls `documents.render_invoice` inside "
        "the issue transaction before the status moves, so a bill that cannot be turned "
        "into a document does not issue and the release reports it as a break like any "
        "other (BR-BIL-055). WHAT IS STILL OWED IS BR-BIL-036: the document is proved "
        "renderable and then discarded — nothing stores it and nothing hands it to the "
        "print vendor. The renderer also names, on every document, every A19 field the "
        "stamped instance does not carry — including TOTAL DUE, which cannot be printed "
        "at all until stage 6 stamps the BR-BIL-035 balance-forward figures.",
    },
    {
        "code": "delivery_queued_but_not_dispatched",
        "br_ref": "BR-BIL-016 · BR-BIL-036",
        "ran": True,
        "detail": "AMENDED 2026-08-11 — this used to read `delivery_queue_not_written` "
        "with `ran: False`, because the notifications write path published nothing to "
        "call. It publishes `queue_document` now and issue writes one delivery record per "
        "bill per channel through `delivery_seam.queue_bill_delivery`, inside the issue "
        "transaction. So the QUEUE half of BR-BIL-016 RAN. **Nothing was SENT**: there is "
        "no dispatcher (US-NOT-002) and no provider adapter (US-NOT-003), and email "
        "ACTIVATION is R4 on the B12 release table — the rows rest `queued`, which is "
        "their finished state today. Every bill carries the BR-BIL-036 print floor and "
        "nothing above it: the delivery ELECTION (`accounts.paperless`, PROPOSED-SCHEMA) "
        "is unbuilt, so no email or SMS row is written on a guess. Counts ride "
        "`outcome.issued.delivery_queued` / `.delivery_problems`.",
    },
    {
        "code": "posting_handoff_emitted_at_issue",
        "br_ref": "BR-BIL-011",
        "ran": True,
        "detail": "AMENDED 2026-08-11 — this used to read `posting_handoff_not_emitted` "
        "with `ran: False`, because stage 7 was *'a separate act'* and the posting service "
        "was *'still a stub'*. It is not a stub and it is not separate: `issue_invoice` "
        "emits the balanced handoff through `apps/billing/posting_seam.post_bill_issue` "
        "INSIDE each bill's own transaction — DR the tenant's `accounts_receivable` "
        "designation for `invoices.total`, CR one bucket per distinct stamped "
        "`gl_account_id` (US-BIL-005 §7). So a released run now moves money into the books, "
        "and a bill the ledger refuses does not issue at all. Billing still writes no "
        "journal line (CLAUDE.md rule 5): the ledger's posting service is the sole writer "
        "and `ledger/0004`'s trigger is the fence. Counts ride "
        "`outcome.issued.posted` / `.already_posted` / `.posting_problems`; what stage 7 "
        "still cannot say (US-LED-002's premises/unit chain, a tax bucket's authority) "
        "rides `posting_seam.POSTING_UNAVAILABLE`.",
    },
    {
        "code": "breaks_not_queued_for_later",
        "br_ref": "BR-BIL-053",
        "ran": False,
        "detail": "a bill that could not issue is reported as a named break and is NOT "
        "written into the pending-billing queue. 'Mark for later' is a staff decision "
        "(`runs.mark_for_later`), and taking it here would leave no record that anyone had.",
    },
)

#: The scale of the money columns this module reads and writes — NUMERIC(18,6),
#: CLAUDE.md rule 2. Serialising to six places is a FORMAT, not a rounding
#: event: `_money_text` refuses rather than rounds if a value would not survive
#: the trip, so no B4 rounding decision is taken here.
MONEY_SCALE = 6


@dataclass(frozen=True)
class ConsumptionFigure:
    """How much of one service was consumed, in ONE unit. Rule 3, as a type.

    `service_code` is None when the bills do not say which service the quantity
    belongs to — today that is every line, because stage 6 writes no `service`.
    None means "not attributed", never "no service", and it is never resolved
    by inference from the unit.
    """

    service_code: str | None
    quantity: Decimal
    unit: str


@dataclass(frozen=True)
class CategoryFigure:
    """One row of one category breakdown. BR-BIL-057, whose axis set is PROPOSED.

    `axis` travels WITH the row rather than being a dict key, because the axis
    set is the open question: a shape that made the axes structural would have
    to change when the PO rules, and a list of labelled rows does not.
    """

    axis: str
    key: str | None
    bills: int
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class MandateCoverage:
    """What one confirmation is shown AGAINST (BR-BIL-059).

    `covered` / `not_covered` are None when the coverage cannot be counted at
    all. That is a different fact from zero — "0 of 1,122 hold an email
    address" and "we could not count" must never render the same — so the type
    carries the difference instead of flattening it.
    """

    mandate: str
    covered: int | None
    not_covered: int | None
    accounts: int
    amount: Decimal | None = None
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class RunSummary:
    """The phase-4 panel: everything a human is shown before money goes out.

    Computed by `summary_for` from the run's CURRENT bills on every call (PO
    2026-08-11, option B). Nothing here is cached and nothing is read back from
    `bill_run_releases` — a summary function that read the stored row would be
    the bug that ruling created.
    """

    bill_run_id: str
    accounts: int
    bills: int
    consumption: tuple[ConsumptionFigure, ...]
    #: **What these customers owe now**, net of every credit note with no
    #: replacement (PO 2026-08-12, OQ-121). This is the figure that is shown,
    #: signed for and stored on `bill_run_releases.total_amount`.
    amount: Decimal
    currency: str | None
    #: Σ of the bills' own totals, BEFORE the credits — and `credits_applied` is
    #: what was taken off. Both travel with the net because the stored row is the
    #: only surviving answer to *"what did I authorise?"*: a lone net figure
    #: cannot tell a reader a year later whether the run was small or corrected.
    #: GT-6: gross 247.30 · credits 25.00 · amount 222.30.
    gross_amount: Decimal = Decimal("0")
    credits_applied: Decimal = Decimal("0")
    #: CR-059 CS-37 — how many credit notes made up `credits_applied`, and up to
    #: FIVE of them NAMED. Structured, beside the prose, and that is the point:
    #: the sentence in `problems` carries a ruling, a date and a worked GT
    #: figure, none of which belongs on a clerk's screen (B14 rule 32 — no rule
    #: id or internal code in clerk-facing copy; gate G28 — no internal
    #: reference reaches a screen). So S31 renders THESE, and composes its own
    #: one-line sentence from its catalogue.
    #:
    #: ⚠ **EVERY ENTRY IS A NUMBER OR A BILL-AND-DATE. NEVER AN ID.** See
    #: `_credit_note_label`, which is where B14 rule 31's breach was closed.
    credit_count: int = 0
    credits_named: tuple[str, ...] = ()
    by_category: tuple[CategoryFigure, ...] = ()
    coverage: tuple[MandateCoverage, ...] = ()
    problems: tuple[dict[str, Any], ...] = ()
    #: 🔒 PO ruling 2026-09-30 (fixed-charge case 2) — the standing charges a
    #: clerk WAIVED in this run, so Sign off can say *"Waived $26"*. Each entry
    #: is `{"account_no", "amount", "currency"}` — an account NUMBER, never an
    #: id (B14 rule 31). Read from the live decision rows, whose amount the
    #: calculate pass stamped from the one pricing path.
    waived: tuple[dict[str, Any], ...] = ()
    waived_total: Decimal = Decimal("0")
    #: BR-BIL-057. Not a comment — a value, so a screen and a stored payload
    #: both carry the fact that the axis set is not ruled.
    axes_status: str = "PROPOSED"
    axes_br_ref: str = "BR-BIL-057"

    def as_payload(self) -> dict[str, Any]:
        """The jsonb shape `bill_run_releases.summary` stores, per B2 r10.

        Money and quantities serialise as STRINGS at the column's own scale.
        Never floats (rule 2), and never a bare number for a quantity (rule 3):
        every consumption entry carries its unit into the record, because the
        record is the only thing that will still be able to answer "what did I
        authorise?" once the screen has moved on.
        """
        return {
            "accounts": self.accounts,
            "bills": self.bills,
            "consumption": [
                {
                    "service": figure.service_code,
                    "quantity": _money_text(figure.quantity),
                    "unit": figure.unit,
                }
                for figure in self.consumption
            ],
            "amount": _money_text(self.amount),
            "gross_amount": _money_text(self.gross_amount),
            "credits_applied": _money_text(self.credits_applied),
            # CS-37 — stored with the signature, so *"what did I authorise?"*
            # can still name the credit notes a year later. Numbers, never ids.
            "credit_count": self.credit_count,
            "credits_named": list(self.credits_named),
            "currency": self.currency,
            "by_category": [
                {
                    "axis": figure.axis,
                    "category": figure.key,
                    "bills": figure.bills,
                    "amount": _money_text(figure.amount),
                    "currency": figure.currency,
                }
                for figure in self.by_category
            ],
            "axes_status": self.axes_status,
            "axes_br_ref": self.axes_br_ref,
            "coverage": [
                {
                    "mandate": item.mandate,
                    "covered": item.covered,
                    "not_covered": item.not_covered,
                    "accounts": item.accounts,
                    "amount": None if item.amount is None else _money_text(item.amount),
                    "unavailable_reason": item.unavailable_reason,
                }
                for item in self.coverage
            ],
            "problems": list(self.problems),
            "waived": [
                {
                    "account_no": row["account_no"],
                    "account_id": row.get("account_id"),
                    "amount": _money_text(row["amount"]),
                    "currency": row["currency"],
                }
                for row in self.waived
            ],
            "waived_total": _money_text(self.waived_total),
        }


@dataclass(frozen=True)
class Confirmations:
    """BR-BIL-058's five facts, as five values.

    Five and not one. A release that went out without the compliance check is a
    DIFFERENT EVENT from one that did, and *"did anyone check compliance before
    we billed 500 customers?"* is exactly the question the record exists to
    answer — which one undifferentiated `confirmed = true` can never do.

    `final` is the PO's *"take final confirm from user"*. It has no column of
    its own by design: it is recorded as `confirmed_by` + `confirmed_at`, which
    says who and when rather than merely that.
    """

    compliance: bool = False
    email_mandate: bool = False
    sms_mandate: bool = False
    autopay_mandate: bool = False
    final: bool = False


@dataclass(frozen=True)
class ReleaseOutcome:
    """What one release pass did — and, deliberately, what it did not.

    `issued` is the issue lane's own result, passed through rather than
    re-summarised: re-counting it here would create a second version of "how
    many bills went out" that could disagree with the first.

    `handoffs` travels so that "the run released" is never read as "the bills
    are with the customer". Nothing in it ran.

    `staff_alert` is what the ONE staff message this run sends did — queued,
    already queued, suppressed by the utility's own switch, or broken. It is
    carried for the same reason `handoffs` is: a bill run that told nobody it
    finished must be able to say why, rather than leaving a clerk to notice an
    empty bell (CR-048 wave B).
    """

    bill_run_id: str
    release_id: str
    released_at: datetime
    issued: issue.IssuedRun
    handoffs: tuple[dict[str, Any], ...] = field(default=RELEASE_HANDOFFS)
    staff_alert: tuple[dict[str, Any], ...] = ()


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set.

    Refuse loudly rather than run an unscoped query and leave RLS as the only
    thing between one tenant's bills and another's. Same guard, same error, as
    `apps/billing/issue.py` and `apps/billing/selectors.py`.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time, the idiom `gather.py`, `issue.py` and
    `tenancy_seam.py` all use: no import statement binds billing to customers'
    internals, and the moment that lane lands its function this seam starts
    using it with no re-wiring.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _money_text(value: Decimal | None) -> str:
    """A Decimal at the column's own scale, as text. NOT a rounding event.

    `bill_run_releases.summary` is jsonb and every money and quantity column
    behind these figures is NUMERIC(18,6), so six places is the scale the value
    already has. If a value would NOT survive the trip — more than six decimal
    places, i.e. money that came from somewhere this module does not know about
    — this refuses instead of rounding. B4's rounding law is finance-signed and
    frozen, and a display helper is not the place to take one of its decisions.
    """
    if value is None:
        return "0." + "0" * MONEY_SCALE
    text = f"{value:.{MONEY_SCALE}f}"
    if Decimal(text) != value:
        raise BillingRuleError(
            f"the figure {value} cannot be recorded at the {MONEY_SCALE}-decimal scale of "
            "its own column without changing it. Rounding it here would take a B4 decision "
            "in a display helper (CLAUDE.md rule 2 — round only at finalization), so the "
            "summary refuses rather than showing a number that is not the number."
        )
    return text


def counted_bills(bill_run: Any) -> Any:
    """The run's bills as they stand RIGHT NOW — the option-B set.

    Everything except void. This is the query the sibling test file's `tc4`
    writes by hand and pins as the ratified behaviour; it lives here so the
    screen and the test cannot drift apart.

    A REBILL IS IN THIS SET, since the OQ-111 ruling of 2026-08-11 — *"A
    Replacement counts"*. It was excluded before that ruling for want of one.
    A SUPERSEDED original is NOT filtered out here, and this function is not
    where that is handled: `current_position_bills` is the layer that swaps each
    superseded original for the head of its chain (BR-BIL-064). This one stays
    the plain "which rows does this run own" query, because two consumers want
    exactly that — the ACCOUNT set ("480 of 500" is a claim about who was
    billed, not about what they now owe) and the tests that pin the option-B set.
    """
    return (
        models.Invoice.objects.filter(tenant_id=_tenant_id(), bill_run=bill_run)
        .exclude(status__in=COUNTED_OUT_STATUSES)
        .order_by()
    )


def current_position_bills(bill_run: Any) -> Any:
    """The run's bills RESOLVED TO WHAT EACH CUSTOMER OWES NOW (BR-BIL-064).

    **OQ-111 (PO 2026-08-11, option A), verbatim:**

        *"A Replacement counts (panel = what these customers owe now)"*

    The parenthetical is the PO's own and is therefore the rule: this panel
    answers *what do these customers owe NOW*, not *what did this run originally
    produce*. It completes the void ruling of the same day rather than
    contradicting it — a voided bill drops out because nothing is owed, and a
    superseded bill is replaced by its rebill because THAT is what is owed.

    **THIS FUNCTION USED TO BE A REFUSAL, AND IS NOW THE ANSWER.** The rebill is
    a NEW invoice that may carry a DIFFERENT `bill_run` than the original, so the
    summary cannot be a filter on `invoices.bill_run_id`; it has to follow the
    chain. Until 2026-08-12 there was no column to follow and
    `_refuse_superseded_without_chain` raised `BillingRuleError` naming
    `invoices.corrects_invoice_id` on every run holding a superseded bill. The
    PO closed **OQ-120** that day — *"Nod to add the link on the new bill"* —
    the column landed in migration `0017`, and this walk is what it was for.

    ❄️ WORKED ON THE PO'S OWN CASE. Run 1 issues **$117.01** to ACC-1042; a
    rebill in run 2 corrects it to **$104.20**. Run 1's panel now reads
    **$104.20 · 1 bill · 1 account** — not $117.01, which is a figure nobody
    owes, and not $0.00, which is what dropping the superseded bill the way a
    VOID is dropped would have shown.

    THREE THINGS THIS WALK HAS TO GET RIGHT, EACH OF WHICH IS A REAL SHAPE:

    * **De-duplication.** When the rebill carries THIS run's `bill_run` the
      resolved head is already in the set on its own account, and counting it
      twice would read $208.40 for one customer. The set is keyed by primary
      key for that reason.
    * **A voided head.** A rebill later voided leaves the customer owing
      nothing, so the head drops out — the void ruling applied at the end of the
      chain instead of the start of it.
    * **A `corrected` bill with no replacement.** That is not a chain, it is a
      hole: a bill marked superseded that nothing replaced. It REFUSES, because
      the two reachable figures are the same two that were wrong before (the
      original's own total, and zero). Data written before `0017` looks exactly
      like this, which is why the refusal names the migration.

    🔒 HUMAN-REVIEW-PENDING · **ONLY THE SUPERSEDED BILLS ARE WALKED (`DEF-BIL-8697`,
    2026-10-01).** This loaded every bill of the run as a model to look at its
    status and then answered `pk IN (<every id>)`: at 40,008 drafts that was
    8.5 s of loading and a 40,008-parameter list carried by each of the
    panel's ~15 statements after it — `GET …/summary` took 11.2 s. The set is
    the same set: every counted bill that is not superseded (its own head, so
    nothing to walk) plus the live head of each superseded one, answered as a
    FILTER rather than a list, so it stays a subquery whatever the run's size.
    """
    tenant_id = _tenant_id()
    resolved: dict[str, Any] = {}
    orphaned: list[tuple[Any, Any, Any, Any]] = []
    for bill in counted_bills(bill_run).filter(status__in=SUPERSEDED_STATUSES):
        head = corrections.replacement_of(bill)
        if head is None:
            orphaned.append((bill.invoice_no, bill.pk, bill.total, bill.currency))
            continue
        head = corrections.latest_in_chain(head)
        if head.status in COUNTED_OUT_STATUSES:
            # The chain ends in a void: nothing is owed, so nothing is shown.
            continue
        resolved[str(head.pk)] = head
    if orphaned:
        named = ", ".join(
            f"{number or pk} ({currency} {total})" for number, pk, total, currency in orphaned[:5]
        )
        raise BillingRuleError(
            f"this run holds {len(orphaned)} bill(s) marked `corrected` that no bill "
            f"replaces — {named}. The chain column exists ({CHAIN_COLUMN}, migration "
            "0017, PO 2026-08-12 closing OQ-120) and nothing points at these, so the panel "
            "cannot say what the customer owes now. Either the correction predates the "
            "column or something set the status without issuing a replacement; both are "
            "worth a defect row. The two figures that ARE reachable are both wrong and "
            "neither is shown: the original's own total is a figure nobody owes after the "
            "correction, and dropping it the way a VOID is dropped would read 0.00 for a "
            "customer who still owes a replacement."
        )
    # A bill that is not superseded is its own head — `counted_bills` has
    # already taken the void out (COUNTED_OUT_STATUSES).
    own_heads = Q(tenant_id=tenant_id, bill_run=bill_run) & ~Q(
        status__in=(*COUNTED_OUT_STATUSES, *SUPERSEDED_STATUSES)
    )
    if resolved:
        own_heads |= Q(tenant_id=tenant_id, pk__in=list(resolved))
    return models.Invoice.objects.filter(own_heads).order_by()


def _credit_notes_against(bills: Any) -> Any:
    """Every credit note this run's bills carry. ONE definition, used twice.

    The headline amount and the category rows are the same subtraction seen from
    two altitudes, so they read the same set: a breakdown built on a different
    filter from its own total is how two figures on one panel start disagreeing.

    Scoped by `original_invoice__in`, which is the only leg of the correction
    chain that exists (`credit_notes.original_invoice_id`; the REBILL leg is
    `CHAIN_COLUMN` and is OQ-120's). A credit note that references NO
    invoice is not reached: nothing writes one today — `corrections.
    execute_credit_only` always stamps the bill it was raised against — and
    attributing a free-floating account credit to this run's period would be a
    guess about which month it belongs to.
    """
    return models.CreditNote.objects.filter(
        tenant_id=_tenant_id(), original_invoice__in=bills
    ).order_by()


def _credit_magnitude(notes: Any) -> Decimal:
    """Σ |amount| over credit notes. The SIGN IS DECIDED HERE, once.

    `credit_notes.amount` has no stated sign convention: `corrections.
    execute_credit_only` writes `money.finalize(-credited)` — a NEGATIVE
    25.000000 — and the fixtures that pre-date it write a positive one. A panel
    that added the signed column would read $272.30 on one convention and
    $222.30 on the other, and both look plausible on a screen.

    So the magnitude is summed per ROW (`Sum(Abs(...))`, never `abs(Sum(...))`,
    which would cancel a mixed batch into a wrong single number) and the
    DIRECTION is applied once, at the one place that knows it: a credit reduces
    what the customer owes. `execute_credit_only` takes the same decision in the
    same words for its own posting.

    REPORTED, not silently accepted: the model states no convention, so this is
    a reading of two writers rather than a rule. It belongs on `CreditNote` as a
    constraint, and that is another lane's table.
    """
    return notes.aggregate(total=Sum(Abs("amount")))["total"] or Decimal("0")


def _credit_adjustment_for(
    bills: Any, currency: str | None
) -> tuple[Decimal, int, tuple[str, ...]]:
    """The OQ-121 ruling, as arithmetic. **PO 2026-08-12.**

    Verbatim: *"no rebill , Count it like a replacement"*.

    A class-C correction (EP-BIL-04 — goodwill, concession, outage credit)
    writes a credit note referencing the original, issues NO rebill, and leaves
    the original `issued`. ❄️ GT-6 is that shape: **$25.00** against a
    **$247.30** invoice → the panel shows **$222.30**.

    "Like a replacement" is what decides the shape. Under OQ-111 a replacement
    counts and the superseded original does not, so the account appears ONCE at
    what it now owes. Here there is no second invoice, so the same result is
    reached from the one row that exists: the bill is counted (it is not a void
    and is never dropped) and the credit comes off. The panel is *"what these
    customers owe now"* either way — the OQ-111 parenthetical, which is the PO's
    own and is therefore the rule.

    **NOTHING IS WRITTEN.** The credit note already exists with its own balanced
    entry — DR write-off / CR customer credit balance, posted by
    `corrections.execute_credit_only` — and this is a read of it. The issued
    invoice's own `total` is never touched (hard rule 4), which is precisely why
    the gross figure has to be carried alongside the net rather than replacing
    it: the bill still says 247.30 and always will.

    Returns the credited magnitude, how many notes it came from, and up to five
    of them named for the panel's problem row.
    """
    notes = _credit_notes_against(bills)
    foreign = sorted(
        {
            row
            for row in notes.values_list("currency", flat=True).distinct()
            if row and currency is not None and row != currency
        }
    )
    if foreign:
        raise BillingRuleError(
            f"this run's bills are in {currency} and it carries credit note(s) in "
            f"{', '.join(foreign)}. There is no lawful subtraction: {currency} less "
            f"{foreign[0]} is a number with no name, for the same reason kWh is never "
            "subtracted from kgal (CLAUDE.md rule 2 — money is never summed, or netted, "
            "across currencies). BR-TEN-021 makes the tenant currency forward-only, so this "
            "should be unreachable; it refuses loudly rather than quietly if it is reached."
        )
    named = tuple(
        _credit_note_label(number, invoice_no, issued_at, amount)
        for number, invoice_no, issued_at, amount in notes.values_list(
            "credit_note_no", "original_invoice__invoice_no", "issued_at", "amount"
        )[:5]
    )
    return _credit_magnitude(notes), notes.count(), named


def _credit_note_label(
    number: str | None,
    invoice_no: str | None,
    issued_at: Any,
    amount: Decimal,
) -> str:
    """How one credit note is NAMED to the person signing off the run.

    ════════════════════════════════════════════════════════════════════════
    THE ID FALLBACK IS GONE, AND IT IS NOT COMING BACK AS A SAFETY NET
    ════════════════════════════════════════════════════════════════════════
    This line read `f"{number or pk} ({abs(amount)})"` until 2026-09-02, and
    the `or pk` was a **live breach of B14 rule 31**, ratified 2026-08-31 in the
    PO's own words: *"no Databse ID on screen - that is a rule"*. Every credit
    note in the product carried `credit_note_no: null`, so the fallback was not
    an edge case — it was the ONLY branch that ever ran, and a finance user
    signing off a bill run read a sentence with a raw UUID in it.

    `CR-059` CS-37 closes it from both ends: `corrections._allocate_credit_note_
    no` now mints a `CM-` number in the same transaction as the row, and this
    function refuses the id even when there is no number. **CS-37's rollback
    note is explicit that restoring the fallback is not an option** — *"it is a
    rule breach, not a safety net"*.

    ════════════════════════════════════════════════════════════════════════
    WHAT A NUMBERLESS ROW SAYS INSTEAD — the bill and the date, never the id
    ════════════════════════════════════════════════════════════════════════
    CS-37's second new rule, verbatim: *"Where the number is genuinely absent
    on historic rows, the screen shows the bill it was raised against and the
    date, never the id."* Historic rows are **NOT back-filled** — the row
    freezes at issue, and a migration that rewrote history would be exactly the
    thing the freeze exists to prevent — so this branch is permanent, not
    transitional.

    And when neither exists, it says so IN WORDS. That is
    `test_cr059_rule31_collections_account_no`'s own finding one screen along:
    an empty cell breaches rule 31 as loudly as a uuid did, because a person
    reads it as "there is nothing here" about a document that exists.
    """
    magnitude = abs(amount)
    if number:
        return f"{number} ({magnitude})"
    day = "" if issued_at is None else issued_at.date().isoformat()
    if invoice_no and day:
        return f"credit on bill {invoice_no}, {day} ({magnitude})"
    if invoice_no:
        return f"credit on bill {invoice_no} ({magnitude})"
    if day:
        return f"credit of {day}, no number ({magnitude})"
    return f"credit with no number ({magnitude})"


def _consumption_for(bills: Any) -> tuple[tuple[ConsumptionFigure, ...], bool]:
    """Consumption per (service, unit). CLAUDE.md rule 3, enforced twice.

    Returns the figures and whether any quantity could not be attributed to a
    service, so the caller can name the gap rather than leave it to be noticed.

    ONLY `usage` lines. A base charge, a tax and a fee are money, not a measured
    quantity, and a `minimum_adjustment` is an amount rule rather than a reading
    — summing any of them into a consumption figure would report a number no
    meter ever produced.

    A quantity with NO unit is a refusal. `assemble_document` already refuses to
    write one, and that is not the guarantee here: a bill written by an import,
    a fixture or a path not yet built reaches this function too, and hard-won
    law 1 says a comment claiming a guarantee is not the guarantee.
    """
    rows = (
        models.InvoiceLine.objects.filter(
            tenant_id=_tenant_id(), invoice__in=bills, kind="usage", quantity__isnull=False
        )
        .values("service__code", "unit")
        .annotate(quantity=Sum("quantity"))
        .order_by("service__code", "unit")
    )
    figures: list[ConsumptionFigure] = []
    unattributed = False
    for row in rows:
        unit = row["unit"]
        if not unit:
            raise BillingRuleError(
                f"a usage line carries a quantity of {row['quantity']} with no unit "
                "(CLAUDE.md rule 3). The summary refuses it rather than adding it to a "
                "per-service figure: an unlabelled quantity cannot be sanity-checked, and "
                "the consumption panel exists to be sanity-checked before money goes out."
            )
        if row["service__code"] is None:
            unattributed = True
        figures.append(
            ConsumptionFigure(
                service_code=row["service__code"],
                quantity=row["quantity"],
                unit=unit,
            )
        )
    return tuple(figures), unattributed


def _amount_and_currency(bills: Any) -> tuple[Decimal, str | None]:
    """Σ the bill totals, with the currency they are all in. Rule 2's partner.

    A run whose bills are not all in one currency is REFUSED, for the same
    reason kWh and kgal are never added: the sum would be a number with no
    name. BR-TEN-021 makes the tenant currency forward-only so this should be
    unreachable — which is exactly why it must fail loudly if it is reached.
    """
    currencies = sorted({row for row in bills.values_list("currency", flat=True).distinct() if row})
    if len(currencies) > 1:
        raise BillingRuleError(
            f"this run's bills are in {len(currencies)} currencies ({', '.join(currencies)}), "
            "so there is no single amount to show. Money is never summed across currencies "
            "(CLAUDE.md rule 2), any more than kWh is summed with kgal."
        )
    total = bills.aggregate(total=Sum("total"))["total"] or Decimal("0")
    return total, (currencies[0] if currencies else None)


def _categories_for(bills: Any, currency: str) -> tuple[CategoryFigure, ...]:
    """The axes that CAN be derived. BR-BIL-057's SET is not ruled (PROPOSED).

    Three of them, and each is derivable from data billing may lawfully read:

      * **bill_type** — a column on the bill (r10 #12). Billing's own.
      * **consumer_category** — the account's type code, reached along the one
        reviewed cross-module FK (`invoices.account_id → customers.Account`)
        and then into `account_types`, a PLATFORM catalog with no tenant_id
        that is seeded install-wide. The precedent is `selectors.py` reading
        `account__unit_id` along the same edge.
      * **service** — from the usage/base lines' service. Empty of meaning
        today because stage 6 writes no `service`; the axis is still emitted so
        that the day it is populated the panel already answers.

    The rest are named in `UNDERIVABLE_AXES`. Nothing here should be read as
    the answer to *"and various categories"* — that is the PO's to give.

    THE FIRST TWO AXES ARE NET OF CREDIT NOTES, since the OQ-121 ruling of
    2026-08-12. They are a BREAKDOWN of the headline amount, and a breakdown
    that sums to a different total than the figure above it is the discrepancy a
    sign-off panel exists to prevent. Which row a credit belongs in is derived,
    not guessed: the note names its original invoice and that invoice carries
    its own `bill_type` and its own account's category.

    THE SERVICE AXIS IS NOT NETTED and says so on the summary. It sums the
    LINES, so it never tied to the bill totals in the first place, and a
    goodwill credit has no service to belong to — the PO's OQ-105 closure of
    2026-08-11 makes a concession its own category that *"will exclude the
    tax"*, not a reversal of the original's own buckets. Splitting one across
    services would be inventing an attribution nobody ruled.
    """
    figures: list[CategoryFigure] = []
    notes = _credit_notes_against(bills)
    for axis, lookup in (
        ("bill_type", "bill_type"),
        ("consumer_category", "account__account_type__code"),
    ):
        credited = {
            row[f"original_invoice__{lookup}"]: row["credited"] or Decimal("0")
            for row in notes.values(f"original_invoice__{lookup}").annotate(
                credited=Sum(Abs("amount"))
            )
        }
        for row in (
            bills.values(lookup).annotate(n=Count("id"), amount=Sum("total")).order_by(lookup)
        ):
            figures.append(
                CategoryFigure(
                    axis=axis,
                    key=row[lookup],
                    bills=row["n"],
                    amount=(row["amount"] or Decimal("0"))
                    - credited.get(row[lookup], Decimal("0")),
                    currency=currency,
                )
            )
    service_rows = (
        models.InvoiceLine.objects.filter(tenant_id=_tenant_id(), invoice__in=bills)
        .values("service__code")
        .annotate(n=Count("invoice", distinct=True), amount=Sum("amount"))
        .order_by("service__code")
    )
    for row in service_rows:
        figures.append(
            CategoryFigure(
                axis="service",
                key=row["service__code"],
                bills=row["n"],
                amount=row["amount"] or Decimal("0"),
                currency=currency,
            )
        )
    return tuple(figures)


def _coverage_for(
    bills: Any, account_ids: set[str], currency: str | None
) -> tuple[tuple[MandateCoverage, ...], bool]:
    """What each mandate confirmation is shown against (BR-BIL-059).

    **Coverage is SHOWN, never ENFORCED.** *"An account with no email address,
    no SMS opt-in and no autopay mandate still bills, still renders, still
    dispatches and never blocks the release"* — print is the primary channel and
    the floor (BR-BIL-036). Nothing this function returns can refuse anything;
    the confirmations attest that the operator SAW the coverage.

    AUTOPAY is derivable: `accounts.autopay` is a plain column on the row
    billing's reviewed FK reaches, and its amount ties to the same bill set as
    every other figure on the panel. EMAIL and SMS are not: the address lives in
    customers' `contacts` (a tenant-owned satellite billing has no FK to) and
    the SMS opt-in column does not exist at all — it is on the PROPOSED-SCHEMA
    list for `accounts` and is unbuilt. Both go through the published seam, and
    while customers publishes nothing they come back UNAVAILABLE with the reason
    on the row. A zero would be a lie: "0 of 1,122 hold an address" and "we
    could not count" must never render the same.
    """
    total_accounts = len(account_ids)
    coverage: list[MandateCoverage] = []
    unavailable = False

    autopay_bills = bills.filter(account__autopay=True)
    autopay_accounts = {str(row) for row in autopay_bills.values_list("account_id", flat=True)}
    coverage.append(
        MandateCoverage(
            mandate="autopay",
            covered=len(autopay_accounts),
            not_covered=total_accounts - len(autopay_accounts),
            accounts=total_accounts,
            amount=(autopay_bills.aggregate(total=Sum("total"))["total"] or Decimal("0")),
        )
    )

    read = _resolve(COVERAGE_MODULE, COVERAGE_READ)
    for mandate in ("email", "sms"):
        counts = read(sorted(account_ids), mandate=mandate) if read is not None else None
        if counts is None:
            unavailable = True
            coverage.append(
                MandateCoverage(
                    mandate=mandate,
                    covered=None,
                    not_covered=None,
                    accounts=total_accounts,
                    unavailable_reason=(
                        f"customers publishes no `{COVERAGE_READ}`, so {mandate} coverage "
                        "cannot be counted. The address lives in `contacts` and the SMS "
                        "opt-in column is unbuilt (PROPOSED-SCHEMA); billing has no "
                        "reviewed FK to either and does not guess. BR-BIL-059 is "
                        "unaffected: coverage never blocks a release."
                    ),
                )
            )
            continue
        coverage.append(
            MandateCoverage(
                mandate=mandate,
                covered=int(counts.get("covered", 0)),
                not_covered=int(counts.get("not_covered", 0)),
                accounts=total_accounts,
            )
        )
    del currency  # the coverage rows carry counts; only autopay carries money
    return tuple(coverage), unavailable


def summary_for(bill_run: Any) -> RunSummary:
    """Phase 4's panel, computed from the run's bills AS THEY STAND (option B).

    A QUERY on every call. The PO chose *"recalculate live"* on 2026-08-11 over
    their own worked figure — approve 480 bills at $52,847.19, void two, and the
    screen must read 478 — so nothing here caches and nothing reads
    `bill_run_releases`. That row answers a different question and
    `authorise_release` is what writes it.

    The four figures the PO named are all required and all present: **accounts**
    (every account the run touched, so "480 of 500" is honest — the held ones
    are counted from the exclusion queue), **bills**, **consumption per service
    with its unit**, and **amount with its currency**.

    SINCE 2026-08-11 IT ALSO FOLLOWS THE CORRECTION CHAIN (BR-BIL-064). The PO
    ruled *"A Replacement counts (panel = what these customers owe now)"*, so a
    rebill in this run is counted and a superseded original must be shown at its
    replacement's figure. The second half needs a column that does not exist, so
    `current_position_bills` follows `CHAIN_COLUMN` to the replacement rather
    than showing a number nobody owes; it refused outright until the column
    existed (OQ-120, 2026-08-12).

    SINCE 2026-08-12 A CORRECTION WITH NO REPLACEMENT MOVES IT TOO (OQ-121).
    *"no rebill , Count it like a replacement"* — a credit note against one of
    this run's bills comes off the amount, the bill still counts, and GT-6's
    $247.30 invoice with its $25.00 goodwill credit shows $222.30 · 1 bill ·
    1 account. This case was a stub against that question until the PO closed it.

    ALSO SINCE 2026-08-12 THE REPLACEMENT HALF IS BUILT (OQ-120, migration
    0017). `current_position_bills` walks `invoices.corrects_invoice_id` from
    each of this run's bills to the head of its chain, so the PO's worked case —
    $117.01 corrected to $104.20 in a later run — reads **$104.20** here. This
    function refused outright for that case until the column existed.

    ⚠ THE ACCOUNT SET IS TAKEN FROM THE RUN'S OWN BILLS, NOT THE RESOLVED ONES.
    "480 of 500" is a statement about who this run touched, and a correction
    does not change who was billed — only what they owe. Reading the accounts
    off the resolved set would be identical today (a rebill carries the same
    account) and would silently stop being identical the day a correction moves
    a bill between accounts.
    """
    bills = current_position_bills(bill_run)

    billed_accounts = {
        str(row) for row in counted_bills(bill_run).values_list("account_id", flat=True)
    }
    held_accounts = {
        str(row)
        for row in models.BillRunExclusion.objects.filter(
            tenant_id=_tenant_id(), bill_run=bill_run
        ).values_list("account_id", flat=True)
    }

    consumption, unattributed = _consumption_for(bills)
    gross_amount, currency = _amount_and_currency(bills)
    credits_applied, credit_count, credits_named = _credit_adjustment_for(bills, currency)
    amount = gross_amount - credits_applied
    bill_count = bills.count()

    problems: list[dict[str, Any]] = [
        {
            "code": SUMMARY_AXES_PROPOSED,
            "br_ref": "BR-BIL-057",
            "detail": "the PO said 'and various categories' and enumerated none, so the "
            "axis SET is PROPOSED, not ruled. The axes below are what this run can derive; "
            "they are not an answer to the question.",
        }
    ]
    problems.extend({"code": SUMMARY_AXIS_UNAVAILABLE, **entry} for entry in UNDERIVABLE_AXES)
    if unattributed:
        problems.append(
            {
                "code": SUMMARY_SERVICE_UNATTRIBUTED,
                "br_ref": "BR-BIL-056",
                "detail": "some consumption cannot be attributed to a service: the bill "
                "lines carry a quantity and a unit but no service (stage 6 writes none). "
                "It is shown with service = null rather than guessed from the unit — water "
                "and sewer both meter in kgal — and rather than dropped, which would "
                "understate the one figure the panel exists to sanity-check.",
            }
        )
    if credit_count:
        # A total that moved for an unstated reason is the one a clerk approves
        # by mistake, so the panel shows the arithmetic and quotes the ruling.
        problems.append(
            {
                "code": SUMMARY_CREDITS_NETTED,
                "br_ref": "BR-BIL-064 · OQ-121 (CLOSED " + CREDIT_ONLY_RULING_DATE + ")",
                "detail": f"{credit_count} credit note(s) against this run's bills issue no "
                f"replacement bill and are netted into the amount: {', '.join(credits_named)}"
                f"{' and others' if credit_count > len(credits_named) else ''}. "
                f"{_money_text(gross_amount)} less {_money_text(credits_applied)} = "
                f'{_money_text(amount)}. The PO ruled on {CREDIT_ONLY_RULING_DATE}: "'
                f'{CREDIT_ONLY_RULING}" — worked on GT-6, a $25.00 goodwill credit against a '
                "$247.30 invoice shows $222.30. The bill is COUNTED, not dropped, and nothing "
                "on it is altered: the credit note is its own row with its own posting, and "
                "this panel is a read (hard rule 4).",
            }
        )
        problems.append(
            {
                "code": SUMMARY_SERVICE_AXIS_GROSS,
                "br_ref": "BR-BIL-057 · OQ-105",
                "detail": "the bill_type and consumer_category rows below are NET of those "
                "credit notes and tie out to the amount. The SERVICE rows are not: they sum "
                "the bill LINES rather than the bill totals, and a goodwill credit has no "
                "service to belong to — the PO's OQ-105 closure makes a concession its own "
                "category that excludes tax, not a reversal of the original's buckets. "
                "Splitting one across services would invent an attribution nobody ruled.",
            }
        )
    if not bill_count:
        problems.append(
            {
                "code": SUMMARY_NO_COUNTABLE_BILLS,
                "br_ref": "BR-BIL-056",
                "detail": "this run has no bills to release. That is not the same as a run "
                "of zero value: check the run's scope and its break list before reading it "
                "as 'nothing to bill'.",
            }
        )

    waived = _waived_for(bill_run, billed_accounts)

    coverage, coverage_unavailable = _coverage_for(bills, billed_accounts, currency)
    if coverage_unavailable:
        problems.append(
            {
                "code": SUMMARY_COVERAGE_UNAVAILABLE,
                "br_ref": "BR-BIL-059",
                "detail": "one or more mandate coverage counts could not be computed on "
                "this deployment; each says so on its own row. Coverage is SHOWN and never "
                "enforced, so nothing is blocked by the absence.",
            }
        )
    problems.append(
        {
            "code": SUMMARY_COVERAGE_BASIS_UNRULED,
            "br_ref": "BR-BIL-059",
            "detail": "BR-BIL-059 stores the coverage counts AS SHOWN, and the 2026-08-11 "
            "option-B ruling was put about bills and amount — it never named these counts. "
            "So whether a re-opened run recomputes them is a question for the PO. They are "
            "computed at call time here because a query cannot do otherwise; the stored row "
            "keeps what was shown at sign-off either way.",
        }
    )

    return RunSummary(
        bill_run_id=str(getattr(bill_run, "pk", bill_run)),
        accounts=len(billed_accounts | held_accounts),
        bills=bill_count,
        consumption=consumption,
        amount=amount,
        currency=currency,
        gross_amount=gross_amount,
        credits_applied=credits_applied,
        # CS-37 — the same two values the prose sentence below already carried,
        # published STRUCTURALLY so S31 can name the credit notes without
        # parsing a paragraph that quotes a ruling and a golden-test figure.
        credit_count=credit_count,
        credits_named=credits_named,
        by_category=_categories_for(bills, currency) if currency else (),
        coverage=coverage,
        problems=tuple(problems),
        waived=waived,
        waived_total=sum((row["amount"] for row in waived), Decimal("0")),
    )


def totals_for(bill_run: Any) -> dict[str, Any]:
    """The panel's HEADLINE only — bills and amount, net of credit notes, with
    the currency — computed by the SAME functions `summary_for` uses, live on
    every call (option B, 2026-08-11), so the two cannot disagree.

    🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8809` (2026-10-01). The bulk run page
    draws two figures of `summary_for`'s panel — the Sent card's total and the
    Send step's bill count — and asked for all of it: consumption per service,
    three category axes, coverage and the waived list, ~1.1 s at 40,008 bills
    (3.1 s beside the page's other reads), on the read the Sent card waits for.
    This answers what the page draws in ~5 statements. Same refusals, in the
    same order: a superseded bill nothing replaces (`current_position_bills`),
    bills in two currencies, a credit note in a foreign one."""
    bills = current_position_bills(bill_run)
    gross_amount, currency = _amount_and_currency(bills)
    credits_applied, credit_count, _named = _credit_adjustment_for(bills, currency)
    return {
        "bill_run_id": str(getattr(bill_run, "pk", bill_run)),
        "bills": bills.count(),
        "amount": gross_amount - credits_applied,
        "currency": currency,
        "gross_amount": gross_amount,
        "credits_applied": credits_applied,
        "credit_count": credit_count,
    }


def _waived_for(bill_run: Any, billed_accounts: set[str]) -> tuple[dict[str, Any], ...]:
    """The accounts whose standing charges were WAIVED in this run (PO ruling
    2026-09-30, fixed-charge case 2) and are not billed in it, each with the
    amount its decision row carries. A row with no amount yet (never through
    a calculate pass) is not shown: a waiver of an unpriced figure has no
    figure to put on the Sign off line."""
    from apps.billing import decisions, gather

    rows = [
        row
        for row in decisions.current_decisions(bill_run)
        if row.case == "base_only_billing"
        and row.choice == decisions.CHOICE_WAIVE
        and row.amount is not None
        and str(row.account_id) not in billed_accounts
    ]
    if not rows:
        return ()
    accounts = _resolve("customers", "account_queryset")
    numbers = (
        {
            str(pk): number
            for pk, number in accounts()
            .filter(pk__in=[row.account_id for row in rows])
            .values_list("pk", "account_no")
        }
        if accounts is not None
        else {}
    )
    currency = gather._tenant_currency()
    return tuple(
        {
            "account_no": numbers.get(str(row.account_id), ""),
            # Record links (PO 2026-10-19): the number opens the account.
            "account_id": str(row.account_id),
            "amount": row.amount,
            "currency": currency,
        }
        for row in sorted(rows, key=lambda r: numbers.get(str(r.account_id), ""))
    )


def missing_confirmations(confirmations: Confirmations, confirmed_by: Any) -> tuple[str, ...]:
    """Which of BR-BIL-058's five facts are not recorded. ALL of them, not the first.

    A gate that named one at a time would make a clerk walk the five toggles
    one refusal at a time, and the epic's TC-10 asks for the untaken
    confirmation to be NAMED — plural is the useful reading.
    """
    missing = [name for name, _column in CONFIRMATION_COLUMNS if not getattr(confirmations, name)]
    if not confirmations.final or confirmed_by is None:
        missing.append(FINAL_CONFIRMATION)
    return tuple(missing)


def record_send_breaks(bill_run: Any, issued: Any) -> dict[str, int]:
    """File each bill this issue pass could not send, and close the ones a
    retry sent (DEF-BIL-8421, DEF-BIL-8581, clerk check F3).

    A SEND break is a `bill_run_breaks` row at stage `send`: the account, the
    break's reason code and its sentence, retryable. It is the same work list
    Calculate's breaks use, so it survives a refresh and two clerks see the
    same rows. A bill a later pass issued closes its row as `issued`; a send
    break is never closed as `drafted`, because its draft never failed.

    Never raises into the release (BR-BIL-055: a break never blocks the run):
    `runs.record_break` and `runs.clear_break` each hold their own savepoint.
    Answers `{"filed": n, "closed": n}`."""
    from apps.billing import runs as billing_runs

    tenant_id = _tenant_id()
    broken = [b for b in getattr(issued, "broken", ()) or () if getattr(b, "account_id", None)]
    # A bill that is no longer a draft WENT — a second Send pressed at the same
    # moment meets it already issued (the per-bill row lock, `issue_invoice`)
    # and must not file it as *not sent* (clerk check F4).
    still_drafts = {
        str(pk)
        for pk in models.Invoice.objects.filter(
            tenant_id=tenant_id,
            pk__in=[b.invoice_id for b in broken if b.invoice_id],
            status=models.INVOICE_DRAFT,
        ).values_list("pk", flat=True)
    }
    broken = [b for b in broken if b.invoice_id and str(b.invoice_id) in still_drafts]
    sent = [str(one) for one in getattr(issued, "issued", ()) or ()]
    numbers = {
        str(pk): str(account_id)
        for pk, account_id in models.Invoice.objects.filter(
            tenant_id=tenant_id, pk__in=sent
        ).values_list("pk", "account_id")
    }
    account_nos = {
        str(account_id): account_no
        for account_id, account_no in models.Invoice.objects.filter(
            tenant_id=tenant_id, pk__in=[b.invoice_id for b in broken if b.invoice_id]
        ).values_list("account_id", "account__account_no")
    }
    filed = 0
    for one in broken:
        row = billing_runs.record_break(
            bill_run,
            billing_runs.Break(
                account_id=str(one.account_id),
                account_no=str(
                    account_nos.get(str(one.account_id)) or one.invoice_no or one.account_id
                ),
                stage=models.BREAK_STAGE_SEND,
                reason=str(one.reason),
                detail=str(one.detail),
                retryable=True,
            ),
        )
        filed += 1 if row is not None else 0
    closed = 0
    send_rows = set(
        str(a)
        for a in models.BillRunBreak.objects.filter(
            tenant_id=tenant_id,
            bill_run=bill_run,
            stage=models.BREAK_STAGE_SEND,
            resolution__isnull=True,
        ).values_list("account_id", flat=True)
    )
    for invoice_id in sent:
        account_id = numbers.get(invoice_id)
        if account_id is not None and account_id in send_rows:
            closed += billing_runs.clear_break(
                bill_run, account_id, resolution=models.BREAK_RESOLUTION_ISSUED
            )
    return {"filed": filed, "closed": closed}


def authorise_release(
    *,
    bill_run: Any,
    summary: RunSummary,
    confirmations: Confirmations,
    confirmed_by: Any,
    confirmed_at: datetime,
    actor: Any = None,
) -> models.BillRunRelease:
    """The gate: record WHAT WAS SHOWN and WHO authorised it. Writes nothing else.

    `summary` is the panel THE HUMAN SAW, passed back in rather than recomputed
    here, and that is the whole point of the row: recomputing at write time
    would store what happened to be true a moment later, which is not what
    anybody signed. The four columns are taken from that same object, so the
    record and its payload can never disagree with each other.

    ⚠ Nothing binds the presented summary to a server-rendered one. A caller
    that passed a stale or fabricated payload would be recorded as having shown
    it. Closing that needs a signed render token, which does not exist, and
    inventing a "the figures moved since you looked" refusal would be inventing
    a rule the PO never gave. REPORTED (human-review ledger), not silently
    accepted.

    `confirmed_at` is a PARAMETER and never a clock read (BR-TEN-043): the
    caller names when the business event happened, so a retried submit records
    one moment rather than two.

    **REFUSES A RUN WHOSE DRAFTS PREDATE THEIR OWN DECISIONS** — `DEF-BIL-5271`,
    BR-BIL-053's last clause extended past breaks to decisions. See the comment
    at the top of the body; the number and the accounts come from
    `runs.stale_drafts`.

    **AND A RUN PINNED TO A TEMPLATE THAT CAN NO LONGER BE PRINTED** —
    `DEF-BIL-5302`, BR-BIL-026. Both refusals are BEFORE the five confirmations
    for the same reason: a clerk who has ticked all five and is then refused on
    something they were never shown reads the refusal as the gate being broken.

    Refuses, naming every untaken confirmation, while any of the five is
    missing — and refuses a summary with no currency, because there is no
    currency for `bill_run_releases.currency` to hold and a release of nothing
    is not a release (BR-BIL-058: the gate is the last moment at which nothing
    has been billed).
    """
    # ── `DEF-BIL-5271`(b) · BR-BIL-053's LAST CLAUSE, EXTENDED ──────────────
    # *"The run cannot enter phase 4 with an unresolved break row"* — and a
    # DECISION IS NOT A BREAK. A clerk who bulk-decides 44 estimated accounts
    # resolves no break and breaks nothing, so the gate's `outstanding` number
    # stayed 0 while 44 drafts kept their pre-decision figures. This is the
    # clause that makes the scoped re-price non-optional: a run whose drafts
    # predate their own decisions cannot be authorised at all.
    #
    # ⚠ **FIRST, BEFORE THE FIVE CONFIRMATIONS.** A clerk who has ticked all
    # five and is refused on a sixth thing they were never shown reads the
    # refusal as the gate being broken; refusing on the state of the RUN before
    # asking about the state of the FORM puts the two in the order a person
    # meets them. Imported inside the call for the reason every other
    # billing→billing late import in this package has one: `runs` reaches this
    # module's siblings and a module-level cycle is not worth the tidiness.
    from apps.billing import runs as billing_runs

    billing_runs.refuse_stale_drafts(bill_run)
    # ── `DEF-BIL-5302` · THE TEMPLATE CHOSEN AT SCOPE IS STILL PRINTABLE ─────
    # PO ruling 2026-09-14: *"in this step 1 scope - you will ahve to also
    # decide on billing template"*. A template can be retired or unpublished
    # between Scope and Send — that gap is exactly when a tenant edits their
    # templates — and today the fault is discovered INSIDE the issue loop, by
    # `IssuedRun.template_problems`, after the batch has started and after a
    # clerk has signed. Checked here so it stops where a clerk can act on it.
    billing_runs.refuse_unresolvable_template(bill_run)
    tenant_id = _tenant_id()
    missing = missing_confirmations(confirmations, confirmed_by)
    if missing:
        raise BillingRuleError(
            f"release refused: {', '.join(missing)} not confirmed (BR-BIL-058). The gate is "
            "five separately recorded facts — compliance, email mandate, text mandate, "
            "autopay mandate, and the final confirm itself, which is who said go and when. "
            "One undifferentiated tick could not answer 'did anyone check compliance before "
            "we billed these customers?', which is the question this record exists for."
        )
    if summary.currency is None:
        raise BillingRuleError(
            f"run {getattr(bill_run, 'pk', bill_run)} has no bills to release, so there is "
            "no amount and no currency to record. Money is never recorded without its "
            "currency partner (CLAUDE.md rule 2), and an authorisation of nothing would be "
            "a signature against a blank page."
        )

    with transaction.atomic():
        row = models.BillRunRelease.objects.create(
            tenant_id=tenant_id,
            bill_run=bill_run,
            summary=summary.as_payload(),
            account_count=summary.accounts,
            bill_count=summary.bills,
            total_amount=summary.amount,
            currency=summary.currency,
            compliance_confirmed=confirmations.compliance,
            email_mandate_confirmed=confirmations.email_mandate,
            sms_mandate_confirmed=confirmations.sms_mandate,
            autopay_mandate_confirmed=confirmations.autopay_mandate,
            # AN ID OR AN INSTANCE, and the caller may hold either — the exact
            # shape `runs.create_run` takes for `bill_runs.run_by`, for the same
            # reason. The API layer knows the signatory only as
            # `request.user.id` (identity's User is another module's model and
            # billing may not import it, B1/G6), while a service-to-service
            # caller has the row in hand. `confirmed_by_id` accepts both;
            # `confirmed_by=<uuid>` raised `ValueError: Cannot assign … must be
            # a "User" instance` and took the whole request with it.
            confirmed_by_id=audit.actor_user_id(confirmed_by),  # DEF-BIL-5090
            confirmed_at=confirmed_at,
        )
        # Hard rule 7, inside the same transaction so the authorisation cannot
        # stand without its trail row. No payload content goes in — BR-AUD-006
        # keeps PII out of the trail and the summary is on the row itself.
        audit.money_action(
            actor if actor is not None else confirmed_by,
            "bill_run.release_authorised",
            "bill_run",
            str(getattr(bill_run, "pk", bill_run)),
            before=None,
            after={
                "release_id": str(row.pk),
                "account_count": summary.accounts,
                "bill_count": summary.bills,
                "total_amount": _money_text(summary.amount),
                "currency": summary.currency,
                "compliance_confirmed": confirmations.compliance,
                "email_mandate_confirmed": confirmations.email_mandate,
                "sms_mandate_confirmed": confirmations.sms_mandate,
                "autopay_mandate_confirmed": confirmations.autopay_mandate,
                "confirmed_at": confirmed_at.isoformat(),
            },
        )
    return row


def pending_releases(bill_run: Any = None) -> Any:
    """Authorised but NOT released — the position a crash leaves behind.

    Epic TC-13. Without this state a restart either asks for authorisation a
    second time, for a release the user already gave, or assumes it was given
    and sends bills nobody approved. The partial index on the table
    (`ix_bill_release_pending`) exists for exactly this read.
    """
    rows = models.BillRunRelease.objects.filter(
        tenant_id=_tenant_id(), released_at__isnull=True
    ).order_by("-confirmed_at")
    return rows if bill_run is None else rows.filter(bill_run=bill_run)


def completed_releases(bill_run: Any = None) -> Any:
    """AUTHORISED AND RELEASED — `pending_releases`' other half.

    Added 2026-08-15 for the phase-5 route (DEF-116). It exists so the API can
    tell a REPLAY from a FORGERY without a queryset of its own: a second
    `POST .../issue` on a run whose release is already stamped is a
    double-clicked Send and answers 200 `created: false`, while the same call on
    a run with NO release row at all is US-BIL-005 TC-14's forged post and is
    refused. Those two deserve opposite answers and only the row can tell them
    apart.

    Newest first, because the answer to *"was this run released?"* is the LAST
    release: a run can hold several (a catch-up sub-run, a resumed batch), and
    each is its own authorisation that happened.
    """
    rows = models.BillRunRelease.objects.filter(
        tenant_id=_tenant_id(), released_at__isnull=False
    ).order_by("-released_at")
    return rows if bill_run is None else rows.filter(bill_run=bill_run)


def complete_release(
    *,
    bill_run: Any,
    release_row: models.BillRunRelease,
    released_at: datetime,
    actor: Any = None,
    issued_count: int,
    already_issued_count: int,
    broken_count: int,
) -> Any:
    """The END of phase 5, after the issue pass: the run's status word, the
    `released_at` stamp, the release's audit row, and the staff summary.

    Lifted out of `release_run` unchanged (DEF-BIL-8726) so the Send in batches
    of 500 (`send_batches`) finishes a release ONCE, after its last batch,
    with the same code an inline release runs. It takes the three COUNTS the
    audit row and the summary carry rather than the pass's `IssuedRun`, because
    a batched Send has no single pass to hand over — `send_batches` counts them
    from the bills. Answers the staff alert. The ORDER is still the design:
    nothing here runs before every bill that could issue has issued.
    """
    with transaction.atomic():
        # ── BR-BIL-1045 · THE RUN'S STATUS ADVANCES HERE AND NOWHERE ELSE ───
        #
        # ⚠ **`bill_runs.status` HAD NO WRITER PAST CREATION UNTIL 2026-09-15
        # (`DEF-BIL-5352`), SO EVERY FINISHED RUN READ *Draft* — INCLUDING ONE
        # THAT HAD ISSUED 1,251 BILLS.** The blueprint's screen 27 draws that
        # column, so it stopped being a defect nobody could see.
        #
        # **INSIDE THE ATOMIC BLOCK AND AFTER THE ISSUE PASS, for the same
        # reason `released_at` is stamped here and not earlier:** a crash
        # mid-issue must not leave a run claiming to have gone out. The issue
        # pass has already returned by this line, so the counts
        # `record_run_outcome` reads are the counts that actually happened, and
        # if this transaction rolls back the word rolls back with the stamp.
        #
        # It reads rows rather than `issued.issued_count`: a resumed release
        # finds bills a previous pass issued, and those are as issued as the
        # ones this pass put out. `runs.record_run_outcome` carries the whole
        # argument, including why a run with breaks left reads `issuing` rather
        # than `abandoned`.
        run_status = runs.record_run_outcome(bill_run, actor=actor)
        release_row.released_at = released_at
        # Only this column moves. The figures, the confirmations and the
        # confirmer are append-only (hard rule 4) and `released_at` is the one
        # field the row is designed to gain later — which is also why no blanket
        # immutability trigger can exist on this table.
        release_row.save(update_fields=["released_at"])
        audit.money_action(
            actor,
            "bill_run.released",
            "bill_run",
            str(getattr(bill_run, "pk", bill_run)),
            before={"released_at": None},
            after={
                "release_id": str(release_row.pk),
                "released_at": released_at.isoformat(),
                "issued": issued_count,
                "already_issued": already_issued_count,
                "broken": broken_count,
                "bill_count_authorised": release_row.bill_count,
                "total_amount_authorised": _money_text(release_row.total_amount),
                "currency": release_row.currency,
                "job": None if actor is not None else "billing.release",
                # BR-BIL-1045 — the word this run now carries, recorded in the
                # SAME audit row as the release rather than in one of its own.
                # The status is a reading of what the release just did, so a
                # second row saying *the word changed* would double-count one
                # event in the register a clerk reads (hard rule 7 asks for an
                # audit row per money ACTION, and this is that action).
                "run_status": run_status,
            },
        )

    # ── CR-048 wave B · THE RUN IS FINISHED, SO TELL SOMEBODY ──────────────
    #
    # This is the point a bill run ends, and it is the ONE place a staff summary
    # belongs: after the issue pass, after `released_at` is stamped, after the
    # audit row — so the message describes work that has actually happened, and
    # so a crash mid-issue leaves no message claiming a run went out.
    #
    # ONE message for the whole run, whatever it touched (BR-NOT-020). The
    # counts are the caller's and are not re-counted here — an inline release's
    # `IssuedRun`, or a batched Send's count of its bills (DEF-BIL-8726): a
    # second version of "how many bills went out" that could disagree with the
    # first is exactly what US-BIL-005 forbids. `already_issued` counts because those bills were
    # asked for and are bills; `broken` counts in BOTH figures, because a bill
    # the run touched and could not issue is a record processed and a record
    # failed.
    #
    # ⚠ NOTHING THIS CALL DOES CAN REACH THE BILLS. The seam holds a savepoint
    # and swallows no reason — see `run_alert_seam`'s docstring for why a `try`
    # alone is not enough on PostgreSQL.
    staff_alert = run_alert_seam.queue_run_summary(
        run_id=getattr(bill_run, "pk", bill_run),
        total_count=issued_count + already_issued_count + broken_count,
        failed_count=broken_count,
        finished_at=released_at,
        actor=actor,
    )

    return staff_alert


def release_run(
    *,
    bill_run: Any,
    release_row: models.BillRunRelease,
    released_at: datetime,
    issued_at: datetime,
    template_id: Any,
    template_version: int,
    invoice_ids: tuple[Any, ...] | None = None,
    actor: Any = None,
    dispatch_not_before: datetime | None = None,
    on_progress: Any = None,
    template_pin_explicit: bool = False,
) -> ReleaseOutcome:
    """Phase 5 — *"and then release the bills"*. Issues them, then stamps the row.

    THE ORDER IS THE DESIGN. The issue pass runs FIRST and `released_at` is
    stamped only once it returns, because `released_at` is what marks a release
    done: stamping it first would turn a crash mid-issue into a run that claims
    to have gone out. Stamping it last means a crash leaves exactly the state
    epic TC-13 describes — the row exists with `released_at` NULL, authorised
    but not released — which `pending_releases` finds and a resume continues
    rather than re-authorising.

    RESUMING IS SAFE because issue is idempotent by construction: a second pass
    finds no remaining drafts and issues nothing (issue TC-6). The idempotency
    is in the write, which is the only place it cannot rot.

    ⚠ **THE SENTENCE "NOTHING HERE TRACKS PROGRESS, BECAUSE NOTHING NEEDS TO"
    STOOD HERE AND IS CORRECTED RATHER THAN LEFT STANDING (hard-won law 1).** It
    was true while this pass could only be reached from a request that held the
    caller: nobody could poll, so nobody could read a gauge. CR-051 task 9 makes
    this pass reachable from a BE-07 job, and `on_progress(done, total,
    invoice_no)` is passed straight through to `issue.issue_run`, which calls it
    once per bill. A resumed release still needs no CHECKPOINT — that half of
    the old sentence is intact and is why the idempotency lives in the write.
    NULL, and every existing caller, behaves exactly as before.

    IT DOES NOT RE-IMPLEMENT ISSUE. `issue.issue_run` is the money path and it
    owns the gate check, the per-bill transaction, the GL stamp and the
    immutability boundary. This calls it. Its `template_id` / `template_version`
    are passed straight through and are CALLER-SUPPLIED. ⚠ **THE REASON GIVEN
    HERE — *"because BR-BIL-025's template assignment has no table"* — EXPIRED ON
    2026-08-15 and is corrected rather than left standing (hard-won law 1).**
    `bill_templates` landed that day and `templates_service.resolve_for`
    implements the ruled order; since CR-052 task 12 the pin is resolved PER
    ACCOUNT inside `issue.issue_run`, and what is passed through here is the
    RUN's pin — the answer for an account whose own chain cannot be read, and
    the whole answer when the caller typed one (`template_pin_explicit`). What
    is still true is the load-bearing half: a bill issued with no pin can never
    record what rendered it.

    `released_at` and `issued_at` are PARAMETERS and never clock reads
    (BR-TEN-043), so a resumed batch stamps the moment the business event
    happened rather than the moment the retry ran.

    `dispatch_not_before` is S31 step 6's *"send now vs scheduled"* choice. It
    is carried onto the delivery rows this release queues and NOWHERE else: it
    does not delay the issue, the posting or the release itself, because a bill
    is billed when it is billed and only its DELIVERY can wait (BR-BIL-016;
    BR-NOT-009's quiet hours ride the same column). NULL means eligible
    immediately.

    A BREAK NEVER BLOCKS THE RELEASE (BR-BIL-055). A bill that cannot issue
    comes back named on `outcome.issued.broken` and the release still completes,
    because it did complete for everything that could go. Those breaks are NOT
    written into the pending-billing queue: "mark for later" is a staff decision
    (BR-BIL-053, `runs.mark_for_later`) and taking it here would leave no record
    that anyone had. Named in `RELEASE_HANDOFFS` rather than left to be noticed.
    """
    _tenant_id()
    if release_row.released_at is not None:
        raise BillingRuleError(
            f"release {release_row.pk} was already released at "
            f"{release_row.released_at.isoformat()}, so this run is not released again. A "
            "second authorised release of a run — a catch-up sub-run, a resumed batch — is "
            "a SECOND row with its own confirmations; re-releasing this one is a "
            "double-click or a replayed job, and an issued bill cannot be un-issued."
        )
    missing = missing_confirmations(
        Confirmations(
            compliance=release_row.compliance_confirmed,
            email_mandate=release_row.email_mandate_confirmed,
            sms_mandate=release_row.sms_mandate_confirmed,
            autopay_mandate=release_row.autopay_mandate_confirmed,
            final=release_row.confirmed_at is not None,
        ),
        release_row.confirmed_by_id,
    )
    if missing:
        raise BillingRuleError(
            f"release {release_row.pk} cannot be released: {', '.join(missing)} not "
            "confirmed (BR-BIL-058). The gate is checked here AND at issue on purpose — a "
            "forged call straight to issue and a half-filled authorisation row are "
            "different bugs, and after the door there is no un-issuing."
        )

    issued = issue.issue_run(
        release_row.bill_run if bill_run is None else bill_run,
        issued_at=issued_at,
        template_id=template_id,
        template_version=template_version,
        invoice_ids=invoice_ids,
        actor=actor,
        dispatch_not_before=dispatch_not_before,
        on_progress=on_progress,
        # CR-052 W3 task 12 — did the CALLER type this pin, or is it the
        # tenant's fallback? Passed straight through and decided nowhere here:
        # BR-BIL-025 resolves per ACCOUNT inside the issue loop, and an
        # explicitly typed pin is a statement about THIS RUN that per-account
        # resolution must not discard silently.
        template_pin_explicit=template_pin_explicit,
    )

    # DEF-BIL-8421 / clerk check F3 — the bills that could not go are FILED,
    # each with its reason, so Sent lists them apart after a refresh and a
    # *Retry failed* re-issues exactly those. Before this they lived only in the
    # response of the request (or the job) that issued, and were gone on reload.
    record_send_breaks(release_row.bill_run if bill_run is None else bill_run, issued)

    staff_alert = complete_release(
        bill_run=release_row.bill_run if bill_run is None else bill_run,
        release_row=release_row,
        released_at=released_at,
        actor=actor,
        issued_count=issued.issued_count,
        already_issued_count=len(issued.already_issued),
        broken_count=len(issued.broken),
    )

    return ReleaseOutcome(
        bill_run_id=str(getattr(bill_run, "pk", bill_run)),
        release_id=str(release_row.pk),
        released_at=released_at,
        issued=issued,
        staff_alert=staff_alert,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by story-coder (W3 bill-run lane — the PO's phases 4-5)
#         · AMENDED 2026-08-11 by Eng-Lead (stage-7 posting-handoff lane —
#         `RELEASE_HANDOFFS` only: `posting_handoff_not_emitted` / `ran: False`
#         became `posting_handoff_emitted_at_issue` / `ran: True`, because issue
#         now emits the BR-BIL-011 handoff inside each bill's transaction. No
#         logic in this file changed)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half yet) E=deferred(no-frontend-half yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_005_release.py — every guarantee was
#         broken deliberately first and the measured failure quoted in the lane
#         report (hard-won law 7). AMENDED 2026-08-11 (correction-chain lane):
#         the OQ-111 guard was re-proved RED three ways before it was trusted —
#         `Failed: DID NOT RAISE BillingRuleError` with the guard removed, and
#         the two wrong panels it protects against measured directly, `PANEL
#         SHOWED bills=1 amount=117.010000000000` (bill_run_id filter kept) and
#         `PANEL SHOWED bills=0 amount=0` (superseded dropped like a void).
#         AMENDED 2026-08-15 (correction-rulings lane): the three OQ-121 cases
#         were written FIRST and run against the pre-ruling build, where all
#         three failed with the pre-ruling stub's own words — `NotImplementedError:
#         OQ-121: this run holds a bill carrying a credit note with no
#         replacement (CN-2607-000012 (25.000000))` at
#         apps/billing/release.py:655 — the refusal the PO's ruling removed. The pre-ruling figure is also pinned as DATA in tc48c
#         (`naive == Decimal("247.300000")`), so the number the ruling MOVED
#         cannot be rediscovered later as a surprise.
# exceptions: (1) NOTHING CALLS THIS. There is no endpoint and no S31 step-5
#         screen, so phase 4 is built and not wired (hard-won law 2, stated
#         rather than implied). G13 guards frontend props, not backend callers.
#         (2) BR-BIL-057's AXIS SET IS NOT DECIDED HERE. Three axes are derived
#         and labelled, `axes_status` reads PROPOSED, and the axes that cannot
#         be derived are named with their reasons. The SET remains the PO's.
#         (3) OQ-111 IS CLOSED AND IMPLEMENTED AS FAR AS THE SCHEMA ALLOWS
#         (AMENDED 2026-08-11, correction-chain lane). PO ruling, verbatim: *"A
#         Replacement counts (panel = what these customers owe now)"*. Built:
#         a rebill carrying this run's `bill_run` is COUNTED like any other
#         bill, which is the ruling from the replacement end. NOT buildable:
#         a SUPERSEDED original must be shown at its replacement's figure, and
#         no column reaches the replacement — `invoices.corrects_invoice_id`
#         does not exist (EP-BIL-04 §5, W5/R3) and the API's
#         `rebill_of_invoice_id`/`corrected_by_invoice_id` are null for the same
#         reason. That case raises `BillingRuleError` naming the column, NOT a
#         stub against a closed question (G8 would reject that, correctly), and
#         refuses to show either reachable figure: the original's own total (a
#         figure nobody owes) or 0.00 (what dropping it like a VOID would give).
#         Both were MEASURED under mutation — `PANEL SHOWED bills=1
#         amount=117.010000000000` and `PANEL SHOWED bills=0 amount=0`. Which
#         column on which table carries the rebill leg is OQ-120.
#         (3b) A CREDIT NOTE WITH NO REPLACEMENT COUNTS — OQ-121 CLOSED, PO
#         2026-08-12 (AMENDED 2026-08-15, correction-rulings lane). This line
#         USED to read "not covered by the ruling", and the case USED to be a
#         stub against that question, because the OQ-111 ruling named a
#         mechanism — the replacement — that a class-C correction does not
#         produce. The PO supplied one, verbatim: *"no rebill , Count it like a
#         replacement"*. So the credit comes off the panel and the bill still
#         counts: ❄️ GT-6's $247.30 invoice with its $25.00 goodwill credit shows
#         **222.30**, gross and credit both carried alongside it on the summary
#         and in the stored payload. NOTHING IS WRITTEN AND NOTHING IS TOUCHED —
#         the credit note is its own row with its own balanced posting
#         (`corrections.execute_credit_only`, DR write-off / CR customer credit)
#         and this is a read; the issued invoice keeps its own total forever
#         (hard rule 4). The bill_type and consumer_category axes are netted the
#         same way so the breakdown ties to the headline; the SERVICE axis is
#         not (it sums lines, and a concession has no service under OQ-105) and
#         says so in `problems`. THE SIGN IS THIS MODULE'S READING, NOT A RULE:
#         `credit_notes.amount` has no stated convention — `execute_credit_only`
#         writes -25.000000 and the older fixtures write +25.00 — so magnitudes
#         are summed per row and the direction is applied once. A constraint on
#         that column belongs to the table's own lane. REPORTED.
#         (4) CONSUMPTION CANNOT BE ATTRIBUTED TO A SERVICE on this deployment:
#         stage 6 writes no `service` on its lines, so every quantity groups
#         under service = null. Shown and named, never guessed from the unit.
#         (5) EMAIL AND SMS COVERAGE ARE UNAVAILABLE — customers publishes no
#         `mandate_coverage_for_accounts`, the address lives in a table billing
#         has no reviewed FK to, and the SMS opt-in column is unbuilt. Reported
#         on the row as unavailable, never as zero. BR-BIL-059 is satisfied
#         either way: coverage never blocks a release.
#         (6) THE PRESENTED SUMMARY IS TRUSTED. Nothing binds it to a
#         server-rendered payload; a drift refusal would be a rule the PO never
#         gave, so it is reported rather than invented.
#         (7) "BACKGROUND" IS NOT TRUE. The issue pass runs inline; every
#         downstream batch is named in `RELEASE_HANDOFFS` with whether it
#         `ran`. AMENDED 2026-08-11 (delivery-queue lane): this line used to say
#         every one of them carried `ran: False`, and two no longer do — the
#         pre-issue render (BR-BIL-033) and the delivery-queue write
#         (BR-BIL-016) both run inside the per-bill issue transaction. NEITHER
#         SENDS ANYTHING: the render keeps nothing and the queue write contacts
#         no provider, because there is no dispatcher and email ACTIVATION is
#         R4. `ran: True` on a handoff means the work happened, never that a
#         customer received a bill.
#         (8) THIS FILE IS ON THE G7 LIST AND ITS MARKERS ARE LOAD-BEARING
#         (CORRECTED 2026-08-15). This line used to say `apps/billing/release.py`
#         matched no glob in 10-scripts/gates/human_owned.txt and that G7
#         therefore enforced nothing here — that was true when it was written and
#         is false now: line 17 of that list names this path, *"Release gate +
#         phase-4 summary — authorises issue and stamps released_at (CLAUDE.md
#         rule 4/7)"*. The HUMAN-OWNED · HUMAN-REVIEW-PENDING markers in the
#         module docstring are kept for that reason and must not be removed until
#         a human sign-off is recorded in 12-governance/09-human-review-ledger.md.
#         A stale exception line is exactly the "comment claiming a guarantee"
#         hard-won law 1 is about, which is why it is corrected rather than left.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
