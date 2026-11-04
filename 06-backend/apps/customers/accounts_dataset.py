# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · the `accounts` DATASET QUERY (brief §7.1 — "datasets
#           are code, definitions are data"; §7.2 — a dataset states ONE grain;
#           §7.5 — the read path; §08 — "every arrow into the database passes
#           through a reviewed dataset").
#           Drawings read as IMAGES (B14 rule 42, PO insisted four times):
#           p059 (R22 Account Census + the head of R23), p060 (R23 Account
#           Activity, R26 Data Quality, the head of R27), p061 (R27 Plans &
#           Discounts), p068–p069 (R41 Migration Assurance), p071 (R24a and the
#           master-account warning), p083–p086 (§7.2/§7.2.1/§7.2.2/§7.2.3/
#           §7.2.4), p087 (§7.5 read path + §7.6 scale), p090–p092 (§08).
# Story:    US-REP-002 (S46 report viewer — the generic render every dataset
#           feeds) · US-REP-008 (the operations canned set, which owns *new &
#           closed accounts*). R22 Account Census is the ONE of the five
#           definitions seeded here whose drawn grain is *one account*.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — `current_tenant_id()` on
#           every queryset, RLS FORCE) · hard rule 2 (money 4 dp stored,
#           percentages 6, both DISPLAY 2; `Decimal` end to end, never float
#           and never cents) · hard rule 4 (**this file writes nothing at
#           all** — no INSERT, UPDATE, DELETE or `save()`) · hard rule 7 (a
#           money ACTION writes `audit_log`; a READ is not an action) ·
#           **hard rule 8 — an address lives on `premises` and every other
#           entity WALKS to it; this query declares no address column of its
#           own and composes none from `customers.addresses`** · NFR-3
#           (universal server pagination — `limit`/`offset`/`sort` in SQL) ·
#           NFR-5 (no hard caps anywhere) · BR-CUS-055 (a status carries a
#           BEHAVIOUR CLASS and code keys off the class, never the tenant's
#           label) · BR-CUS-068 (a master account is a row like any other) ·
#           BR-MET-1161 (one home for an address) · BR-REP-024 (never a 0
#           where a figure could not be computed) · BR-TEN-043 (the business
#           date is an argument, never a clock)
# Tests:    06-backend/tests/test_rep_accounts_dataset.py
#           10-scripts/ds_accounts_audit_notifications_cost.py (the PostgreSQL
#           measurement — hard-won law 14: the suite runs on in-memory SQLite,
#           which cannot answer a question about LIMIT/OFFSET, a plan or RLS)
#           10-scripts/rep_ds_accounts_rls_proof.py (two tenants, three
#           tables, with a red-first control that exits if it is measuring an
#           empty table)
# Impacts:  apps/reports/datasets.py (`ACCOUNTS.paginates`, `ACCOUNTS.grain`,
#           `ACCOUNTS.filters` — REP-UNBLOCK owns that file this session and
#           this lane REPORTS rather than registers) · apps/reports/
#           report_seams.py (the intended cross-module caller)
# ───────────────────────────────────────────────────────
"""THE `accounts` DATASET — **one row per ACCOUNT**, paged and sorted in SQL.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — it publishes a money column (`balance`) and it is
what the Customers reports SAY a utility's book of accounts is. Row in
`12-governance/09-human-review-ledger.md`, written before the review.

═══════════════════════════════════════════════════════════════════════════════
⚠ FIVE REPORTS ARE SEEDED ONTO THIS DATASET AND **ONE** OF THEM IS A REPORT
  ABOUT ACCOUNTS
═══════════════════════════════════════════════════════════════════════════════
`reports/migrations/0003_seed_catalogue.py` seeds R22, R23, R26, R27 and R41
with `dataset="accounts"`. Read as images, their drawings state five different
grains, and only R22's is *one account*:

| report | the drawing's own source line | one row is | verdict |
|---|---|---|---|
| **R22** Account Census | `Customers › Accounts · accounts · As at` | one ACCOUNT | ✅ **served here** |
| **R23** Account Activity | `… · accounts + audit · Event date` | one account-lifecycle EVENT | ❌ refused by name |
| **R26** Data Quality | `… · accounts + premises + assets · As at` | one FINDING (a rule, not a row) | ❌ refused by name |
| **R27** Plans & Discounts | `Customers › Enrolment · accounts + rating · As at` | one ENROLMENT | ❌ refused by name |
| **R41** Migration Assurance | `Compliance › Filings · accounts + journal lines · As at` | one RECONCILIATION CHECK | ❌ refused by name |

⚠ **THE FAILURE MODE THIS REFUSAL PREVENTS IS INVISIBLE, WHICH IS WHY IT IS
WORTH FOUR PARAGRAPHS.** Serving R27 from this grain renders **an account
register under the title *Plans & Discounts*** — real rows, a footing total,
and an answer to a question nobody asked. No gate can see it: the rows are
lawful, the tenant filter is right, the money is 4 dp, and the clerk reads
`318 enrolled` off a tile that counted accounts. The `journal_lines`, `invoices`
and `payments` lanes each met the same premise and each refused the same way
(CR-142-BRC07 §9.1); this is the fourth, and it is the widest.

The refusals are DATA, not prose: `UNSERVABLE_HERE` below names each report,
the grain its drawing states, the read model its facts actually live in, and
the measured evidence. `unservable_reason(code)` is what a caller raises with.

═══════════════════════════════════════════════════════════════════════════════
⚠ *AS AT* IS ANSWERED AS-WAS WHERE HISTORY EXISTS, AS-IS WHERE IT DOES NOT, AND
  THE ROW SAYS WHICH — §7.2.4 (p085), MEASURED AGAINST THE CODE
═══════════════════════════════════════════════════════════════════════════════
⚠ **THE BRIEF IS EVIDENCE, NOT TRUTH, AND THIS IS THE PARAGRAPH THAT PROVED
IT.** §7.2.4 (p085) states, as a MEASUREMENT: *"`06-backend/apps/customers/
models.py` has no effective dating of any kind — no `effective_from`, no
history table … So as-was is not merely unbuilt."* An earlier draft of this
file repeated that sentence and built a permanent excuse out of it.

**It was true when the brief was written and it is FALSE now.** §7.2.4's option
(b) was RULED and then BUILT — `CR-142-BRC07` `P0.18`, 2026-09-26,
`customers/migrations/0072_cr142_p0_18_attribute_history.py`. The table is
`apps/customers/attribute_history_models.py::AccountAttributeHistory`, with
`effective_from`, `effective_to`, and the three columns it shadows
(`account_type_id`, `account_subtype_id`, `status_id`). It is the grep in the
brief's own sentence that is stale: the columns are in
`attribute_history_models.py`, not in `models.py`.

So this query answers *as at* in the shape the brief's NEXT sentence asks for,
verbatim: *"Where history exists it answers as-was … Where it does not —
anything before the table ships — it falls back to as-is and SAYS SO ON THE
FACE OF THE REPORT. One report will state both for the first year, and that is
correct rather than untidy."*

* **MEMBERSHIP is as-at and stored.** `opened_at <= as_of` and (`closed_at IS
  NULL` or `closed_at > as_of`).
* **CLASS, TYPE and STATUS are AS-WAS wherever a history period covers
  `as_of`.** `_as_was_for()` reads them for a whole PAGE in ONE query — never
  `attribute_history.as_was()` per row, which is one round trip per account and
  impossible on a 40,000-row export.
* **WHERE NO PERIOD COVERS THE DATE, THE ROW FALLS BACK TO AS-IS AND SAYS SO.**
  Every row carries `attribute_basis` — `"as_was"` or `"as_is"` — so a mixed
  report is readable rather than a single confident basis line that is true of
  half the rows. `GAP_SOME_ATTRIBUTES_FELL_BACK_TO_AS_IS` is published **only
  when at least one served row actually fell back**, with the count.

⚠ **THE FALLBACK IS NEVER SILENT AND THE MISSING ROW IS NEVER SUBSTITUTED.**
`attribute_history.as_was`'s own docstring: *"`None` … is not the current row
and a caller must not substitute one."* This file does not substitute; it falls
back EXPLICITLY, marks the row, and counts it.

⚠ **AND FOR A DATE BEFORE THE TABLE STARTED RECORDING THE OLD VALUE IS
UNRECOVERABLE.** It survives only in `audit_log`, which is pruned with **no row
type exempt** (PO ruling 2026-09-23). Nothing in this module, and nothing built
on it, may describe that path as a permanent record of a previous value.

═══════════════════════════════════════════════════════════════════════════════
THE TILES KEY OFF THE BEHAVIOUR CLASS, NEVER THE TENANT'S LABEL (BR-CUS-055)
═══════════════════════════════════════════════════════════════════════════════
R22's drawing tiles read **ACCOUNTS · ACTIVE · FINAL · WITH BALANCE**, and the
status words drawn in its rows are *Active* and *Final*. B14 rule 37 makes a
figure drawn in a wireframe an ILLUSTRATION, and BR-CUS-055 makes the rule
explicit for this exact column: *"every status carries a behaviour class so
billing keys off the CLASS, never the tenant's label"*.

**This is the Phase 5 lesson in its own words — *code that was correct while
every row was ours, and wrong the first day a utility wrote one.*** A tile
written as `status__name == "Active"` is right on the seeded tenant and returns
**zero** for a utility that calls the same status *Open*, *Current* or
*En service* (B14 rule 35: a catalogue is written in its own language). It does
not error and it does not look wrong — the tile simply reads `0` over 1,884
live accounts.

So `active` counts `behavior_class IN (billable, billable_base_only)` and the
closed tile counts `behavior_class = terminal`, both from
`BEHAVIOUR_*` below, and `US-CUS-020 TC-3`'s tenant-added *Legal hold* lands in
whichever class its author gave it rather than nowhere.

⚠ **THE DRAWN WORD IS `FINAL` AND THE MEASURE IS NAMED `closed`.** *Final* is a
billing state — `Account.final_read_state` is a real, different column about the
closing read. Naming the measure after the drawn label would make two different
facts share one word in eleven catalogues.

═══════════════════════════════════════════════════════════════════════════════
A MASTER ACCOUNT IS A ROW LIKE ANY OTHER, MARKED, NEVER MERGED (p071, BR-CUS-068)
═══════════════════════════════════════════════════════════════════════════════
The brief's warning, verbatim from the image: *"The master account is a row like
any other, marked, never merged. Its $69.60 of common-area charges is what the
building itself consumes."*

`kind` travels on every row so the renderer can MARK it, and there is no
`exclude(kind="master")` and no roll-up anywhere in this file. Excluding masters
would make the census under-count a campus by one row and lose the common-area
balance; merging them into the premises would produce a total no ledger agrees
with.

═══════════════════════════════════════════════════════════════════════════════
HARD RULE 8 — THE ADDRESS IS WALKED TO, AND THIS FILE HAS NO ADDRESS COLUMN
═══════════════════════════════════════════════════════════════════════════════
R22's drawn warning, verbatim: *"The address column walks to premises and
declares nothing of its own — hard rule 8. Unit B refines the premises by label,
so it shares the street address and may carry its own point on a map."*

`_places()` resolves a PAGE's addresses through `seams.envelope_addresses`,
which is metering's own batched read — **two statements at most for any page**,
never one per row, and never a column here. `customers.addresses` is NOT read:
its `kind='service'` was retired and `DEF-CUS-3653` is the defect that cost,
where an account header composed `Austin, TX 78704` from the retired kind and
would have returned null on every account forever with every test green.

`unit_label` travels beside the street because a unit refines its premises BY
LABEL. `lat`/`lng` do not travel: `BR-MET-1162` narrowed only the coordinate
clause and a census is not a map.

═══════════════════════════════════════════════════════════════════════════════
IT PAGES AND SORTS IN SQL, AND THE EXPORT IS A SEPARATE FUNCTION
═══════════════════════════════════════════════════════════════════════════════
Brief §7.5 (p087): *"Sync — viewing — page 1 — returns rows with limit/offset/
sort applied in SQL. Never the whole result."*

`per` cuts the page with `[offset:offset+limit]` on a QuerySet — one
`LIMIT/OFFSET` — and `sort` is `order_by(*order_terms(...))`. **Nothing is
sorted or sliced in Python anywhere in this file.**

⚠ **`accounts_dataset_stream()` TAKES NO `page` AND NO `per`.** An export cannot
inherit a screen's fifty rows because there is no argument through which to pass
them. A flag would have had that bug; a missing parameter cannot. `NFR-5`
forbids a ceiling on that branch and there is none — `STREAM_CHUNK` is a fetch
buffer and the loop runs until the cursor is exhausted.

**`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET, NEVER OVER THE
PAGE**, which is what makes R22's four tiles foot to the report whether a page
is cut or not — the premise `/outstandings`' withdrawn docstring got backwards.

═══════════════════════════════════════════════════════════════════════════════
ADDITIVITY (§7.2.2, read as an image on p085)
═══════════════════════════════════════════════════════════════════════════════
* `accounts` (the count) — **SEMI-ADDITIVE.** It sums across accounts and
  **never across time**. Two months of censuses added together is 3,894
  accounts at a utility that has 1,947, and §7.2.2's own trap line for this row
  is *"Nothing stops you today."*
* `balance` — **SEMI-ADDITIVE**, for the same reason: it is a balance AS AT a
  date. §7.2.2 puts *AR balance · deposits held · accounts active* in one row.
* `with_balance_pct` / `clean_pct` style shares — **NON-ADDITIVE**, recomputed
  from components, never averaged; `None` rather than `0` when the denominator
  is zero (BR-REP-024).

That declaration is what `REP-P2-MODEL`'s footer refusal reads to print an
em-dash and a reason instead of a number, on screen AND in the CSV. It is
declared honestly here: **this dataset has no fully-additive measure**, and
claiming one would turn the footer back into a wrong total.

═══════════════════════════════════════════════════════════════════════════════
WHAT IT WILL NOT DO
═══════════════════════════════════════════════════════════════════════════════
**It writes nothing.** No INSERT, UPDATE, DELETE or `save()` below.

**It never falls back to zero.** BR-REP-024: a figure that cannot be computed is
`None` beside a named reason in `problems`. An empty filter set has a real count
of `0`, which is a different thing from *not derivable*.

**It states no clock.** `as_of` is an argument (BR-TEN-043), so the figure a
clerk sees at 23:58 and the figure a job takes at 00:02 are explainable, and
yesterday's census is askable.

**It honours no filter it cannot apply.** `route` is declared on the registry's
`ACCOUNTS.filters` and is NOT honoured here; passing it raises rather than
silently serving the whole set under a chip that says otherwise. A filter the
dataset declares and the query drops is the defect `PAYMENTS.filters` already
carries a comment about.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.customers import models, seams
from apps.customers.attribute_history_models import AccountAttributeHistory
from core.pagination import order_terms
from core.tenancy import current_tenant_id

ZERO = Decimal("0")

#: BR-REP-001. R22's eyebrow is `As at` — a STATE basis, not a money-event
#: basis. The `balance` column is the account's stored position, which is the
#: POSTING basis (`BASIS_POSTING` in the registry) and is dated by nothing in
#: this query: it is the balance as the ledger has left it, read at `as_of`'s
#: membership boundary. Both facts travel; neither is inferred.
BASIS = "as_at"

#: The money precision hard rule 2 declares. Stored 4 dp (existing 18,6 columns
#: stay lawful containers), DISPLAYED 2 — and this module displays nothing, so
#: every figure leaves as an exact `Decimal` and the renderer rounds.
_MONEY = DecimalField(max_digits=18, decimal_places=6)

# ── BR-CUS-055 · the BEHAVIOUR CLASSES, never the tenant's label ────────────
BEHAVIOUR_NON_BILLABLE = "non_billable"
BEHAVIOUR_BILLABLE = "billable"
BEHAVIOUR_BILLABLE_BASE_ONLY = "billable_base_only"
BEHAVIOUR_TERMINAL = "terminal"

#: What R22's **ACTIVE** tile counts. Two classes and not one: a Vacation hold
#: is `billable_base_only` and is a live account a clerk still bills.
BEHAVIOUR_ACTIVE: tuple[str, ...] = (BEHAVIOUR_BILLABLE, BEHAVIOUR_BILLABLE_BASE_ONLY)
#: What the drawing labels **FINAL**. Named `closed` here — see the docstring.
BEHAVIOUR_CLOSED: tuple[str, ...] = (BEHAVIOUR_TERMINAL,)

#: BR-CUS-068 / p071. A master is MARKED, never merged and never excluded.
KIND_MASTER = "master"

#: What a caller may order by. Six, because six are what R22's drawing puts a
#: column on. ⚠ **EVERY TUPLE ENDS IN A UNIQUE COLUMN** — a page is a window
#: over an ORDER, and an order that is not total lets two equal rows swap
#: between pages so a clerk sees one twice and another never.
#: `core.pagination.order_terms` refuses to add a tiebreak silently, precisely
#: so it stays the caller's stated decision.
ACCOUNT_SORTS: tuple[str, ...] = (
    "account_no",
    "customer_name",
    "opened_on",
    "closed_on",
    "balance",
    "status",
)
ACCOUNT_DEFAULT_SORT = "account_no"
ACCOUNT_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    # ⚠ The ACCOUNT NUMBER, never the account id — B14 rule 31, and a uuid7
    # sorts by mint time, which is not an order any clerk asked for.
    "account_no": ("account_no", "id"),
    # The CUSTOMER's name is on `customers`, reached through the link table; a
    # sort on it is a join, not a Python key. See `_ordered()`.
    "customer_name": ("_customer_name", "account_no", "id"),
    "opened_on": ("opened_at", "account_no", "id"),
    "closed_on": ("closed_at", "account_no", "id"),
    "balance": ("balance", "account_no", "id"),
    # The tenant's own status NAME, which is what the column shows.
    "status": ("status__name", "account_no", "id"),
}

#: The filters this query HONOURS. `route` is deliberately absent — see
#: `ACCOUNT_FILTERS_NOT_HONOURED`.
ACCOUNT_FILTERS: tuple[str, ...] = (
    "as_of",
    "from",
    "to",
    "class",
    "status",
    "customer_type",
    "service",
)

#: ⚠ Declared by `ACCOUNTS.filters` in the registry and NOT honoured here.
#: Reaching an account's route means walking account → unit → service point →
#: route, and `apps.metering.selectors.route_accounts` answers the question from
#: the other end (one route → its accounts) with no seam published into
#: customers. Serving the WHOLE set under a `Route R-03` chip is the shape
#: hard-won law 2's mirror is about, so this query REFUSES the argument instead.
ACCOUNT_FILTERS_NOT_HONOURED: tuple[str, ...] = ("route",)


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

def GAP_SOME_ATTRIBUTES_FELL_BACK_TO_AS_IS(count: int, served: int) -> dict[str, Any]:
    """Published ONLY when a served row actually fell back — with the COUNT.

    ⚠ **A CAVEAT WITH NO NUMBER BESIDE IT IS INDISTINGUISHABLE FROM AN EMPTY
    ONE** (hard-won law 7's fifth clause: a check reporting zero over a scope it
    silently excludes). *"Some rows may be as-is"* is true of every report
    forever and tells a reader nothing; *"12 of 50 served rows"* tells them how
    much of what they are looking at to trust.
    """
    return {
        "code": "some_rows_have_no_history_period_and_fell_back_to_as_is",
        "br_ref": "brief §7.2.4 (p085) · CR-142-BRC07 P0.18 · BR-REP-024",
        "detail": (
            f"{count} of the {served} rows served have no attribute-history period covering "
            "this date, so their class, type and status are AS-IS — the values they hold today "
            "— rather than as-was. That is every account whose attributes last changed before "
            "apps/customers/attribute_history started recording (customers/0072, 2026-09-26). "
            "Each such row is marked attribute_basis='as_is' individually, so a reader can tell "
            "which. The previous value is not recoverable from anywhere else: it survives only "
            "in audit_log, which is pruned on a retention schedule with no row type exempt."
        ),
        "wanted_reads": (),
    }

GAP_NO_FULLY_ADDITIVE_MEASURE = {
    "code": "every_measure_here_is_a_state_as_at_a_date",
    "br_ref": "brief §7.2.2 (p085)",
    "detail": (
        "accounts and balance are both SEMI-ADDITIVE: they sum across accounts and never "
        "across time. Two months of censuses added together is 3,894 accounts at a utility "
        "that has 1,947. No measure served from this grain is fully additive, so a footer that "
        "totals one down a time axis shows an em-dash and this reason rather than a number."
    ),
    "wanted_reads": (),
}

GAP_PLACE_IS_UNRESOLVED = {
    "code": "an_account_with_no_premises_has_no_address_to_walk_to",
    "br_ref": "CLAUDE.md hard rule 8 · BR-MET-1161 · BR-CUS-1010",
    "detail": (
        "accounts.premises_id is nullable (BR-CUS-1010, the deferred FK into metering) and "
        "accounts.unit_id is nullable too. An account with neither names no place, so the "
        "premises column is absent rather than composed from anywhere else: customers.addresses "
        "kind='service' is RETIRED and reading it is the defect DEF-CUS-3653 records. The "
        "absence IS the fact, and R26 Data Quality is the report that counts it."
    ),
    "wanted_reads": ("apps.metering.selectors.envelope_addresses",),
}


# ═══════════════════════════════════════════════════════════════════════════
#  THE FOUR THIS DATASET CANNOT SERVE — REFUSED BY NAME, WITH WHAT EACH NEEDS
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **A REFUSAL IS DATA HERE AND NOT A COMMENT** (hard-won law 1: a comment
# claiming a guarantee is not the guarantee). `runner.queries_for()` can read
# this, a test asserts it, and `P6.11–P6.25` is sized from it.
#
# Every `evidence` line below was READ FROM THE CODE NAMED IN IT, not taken
# from the brief. The brief is evidence, not truth.

UNSERVABLE_HERE: dict[str, dict[str, Any]] = {
    "account_activity": {
        "report": "R23 Account Activity",
        "drawn_source": "Customers › Accounts · accounts + audit · Event date",
        "drawn_grain": "one account-lifecycle EVENT",
        "why_not_here": (
            "This dataset's grain is one ACCOUNT. R23's tiles are OPENED 38 · CLOSED 14 · "
            "TRANSFERRED 6 · NET +24 over a window — four counts of EVENTS, and one account can "
            "produce several. Serving it from account rows would report the accounts that exist, "
            "not the moves that happened, and a NET of +24 would be unobtainable from either."
        ),
        # ⚠ **BUILT 2026-09-27 as `apps/customers/account_activity.py`
        # (`CR-142-BRC07` `P6.11`, lane REP-P6-JOIN).** This row STAYS as it is:
        # it is what a reader sees if the per-key viewer is ever removed, and
        # `queries.definition_refusal()` asks `VIEWERS` first so the catalogue
        # card and the viewer cannot disagree about whether R23 can be produced.
        # A refusal deleted the day its read model lands is a refusal nobody can
        # read when the wiring rots — which is hard-won law 2's mirror, and the
        # reason `rate_schedules_dataset` keeps its own.
        "needs_read_model": (
            "apps.customers.moves.MoveRecord",
            "apps.customers.transfers.Transfer",
        ),
        "evidence": (
            "MoveRecord carries exactly the two dates the drawing warns about — `performed_at` "
            "(when the clerk did it) and `effective_on` (when it takes effect) — plus `kind` "
            "(move_in | move_out) and `performed_by`, which is the drawing's BY column. "
            "moves.KINDS is a two-tuple, so the drawn `Transferred in` row is NOT a MoveRecord "
            "at all: it is apps/customers/transfers.py's own table. Two tables, one grain, and "
            "neither of them is `accounts`."
        ),
        "warning_obeyed": (
            "p060, verbatim: \"Two date columns because two dates exist — when the clerk did it, "
            "and when it takes effect. A move-in dated 1 October appears in September's activity "
            "and in October's census, and both are right.\" That sentence is ALSO why R22 below "
            "is dated by membership and R23 must be dated by the event: they are two bases, and "
            "one dataset cannot carry both."
        ),
    },
    "data_quality": {
        "report": "R26 Data Quality",
        "drawn_source": "Customers › Accounts · accounts + premises + assets · As at",
        # ⚠ **AND THAT DRAWN SOURCE LINE IS SHORT BY ONE (`DEF-REP-6921`,
        # 2026-09-27).** The fourth drawn row is `Meter with no read in 90 days`,
        # which reads METER READS — a source the line does not name. It is left
        # verbatim above because `drawn_source` records what the DRAWING says;
        # the correction is here, beside it, rather than written into the quote.
        "drawn_grain": "one FINDING — a RULE that failed, with a count",
        "why_not_here": (
            "R26's row is `No mailing address and no premises · Blocking · 4 · 100455 · Bill "
            "cannot be delivered · Accounts`. One row is a CHECK, its severity, how many rows "
            "failed it, ONE example, and the screen that fixes it. Four rows in the drawing "
            "against 1,947 accounts checked. An account-grain query cannot produce it: there is "
            "no account whose row is `Premises with no coordinates, 61`."
        ),
        "needs_read_model": (
            "a data-quality rule set — the checks themselves, which no module holds today",
            "apps.customers.models.Account",
            "apps.metering.models.Premises",
            "apps.assets (the meter fleet, for the no-read-in-90-days check)",
        ),
        "evidence": (
            "Three of the four drawn checks span modules this dataset does not own: `Premises "
            "with no coordinates` reads metering.Premises.lat/lng, `Meter with no read in 90 "
            "days` reads the asset and its last read, and `Active account, no service point` "
            "reads customers.ServiceAgreement against metering. Nothing in this repo enumerates "
            "those checks: grep for a data-quality rule registry returns no module."
        ),
        "warning_obeyed": (
            "p060, verbatim: \"Every row names the screen that fixes it. A quality report that "
            "lists problems without an address is a list of complaints — the Fix in column is "
            "the deliverable.\" The `Fix in` column is part of the RULE, not of any account, "
            "which is the clearest statement that the grain is the check."
        ),
    },
    "plans_and_discounts": {
        "report": "R27 Plans & Discounts",
        "drawn_source": "Customers › Enrolment · accounts + rating · As at",
        "drawn_grain": "one ENROLMENT — an account's membership of ONE programme",
        "why_not_here": (
            "The drawing's own warning is the refusal: three programmes in one table. One "
            "account can be on level pay AND a payment plan AND assistance, which is three rows "
            "at enrolment grain and one row at account grain. Its tiles — ENROLLED 318 (16.3%) · "
            "LEVEL PAY 184 · PAYMENT PLANS 84 ($14,204.00 remaining) · ASSISTANCE 50 — add to "
            "318, and 184+84+50 = 318 only because those are ENROLMENTS. Served from accounts "
            "the columns SINCE, TERMS, INSTALMENT and REMAINING have no account-level value at "
            "all: an account on two programmes has two instalments and two remaining balances."
        ),
        "needs_read_model": (
            "the level-pay / budget-billing enrolment (apps.billing.budget)",
            "the payment-plan agreement (apps.payments)",
            "the assistance / discount enrolment (apps.rating)",
        ),
        "evidence": (
            "The three programmes are owned by three different modules — `apps/billing/"
            "budget.py` for level pay, payments for the plan agreement and its remaining "
            "balance, rating for the assistance discount — and `accounts` carries none of the "
            "four drawn columns. `Account.autopay` is the nearest thing on the table and it is "
            "marked CAPTURE-ONLY in v1 (BR-CUS-059), which is not a programme."
        ),
        "warning_obeyed": (
            "p061, verbatim: \"Three programmes in one table because a clerk asks one question "
            "— what is this account enrolled in. Splitting them into three reports was the "
            "first draft and it made the clerk run three.\" So the joining read must UNION the "
            "three at one grain; it must not become three reports, and it must not become one "
            "account row with three sets of columns."
        ),
    },
    "migration_assurance": {
        "report": "R41 Migration Assurance",
        "drawn_source": "Compliance › Filings · accounts + journal lines · As at",
        "drawn_grain": "one RECONCILIATION CHECK — legacy against loaded",
        "why_not_here": (
            "R41's row is `Account count · 1,884 · 1,884 · 0 · 0 · Match`. One row is a MEASURE "
            "compared across two systems, and four rows cover the whole utility. The LEGACY "
            "column is not in this database at all: it is what the old system said before "
            "cutover. An account-grain query has no column that could hold it."
        ),
        "needs_read_model": (
            "the legacy control totals recorded at cutover — apps.customers.models."
            "AccountImportBatch is the nearest thing and holds row_count / valid_count / "
            "cutover_date, not balances",
            "apps.ledger (the loaded side of Opening balance and Deposits held)",
            "apps.metering (the loaded side of Read history rows)",
        ),
        "evidence": (
            "`AccountImportBatch` carries `row_count`, `valid_count`, `cutover_date` and a "
            "`file_hash`; it carries NO money column, so `Opening balance 44,118.02` and "
            "`Deposits held 18,400.00` have no legacy side stored anywhere. "
            "`AccountOpeningBucket` holds per-account opening amounts by ageing bucket, which "
            "is the loaded side of one of the four checks and not the legacy side of any."
        ),
        "warning_obeyed": (
            "p069, verbatim: \"Tolerance is zero for money and counts, and stated for history. "
            "The sixteen missing read rows are the legacy system's own duplicates, which is why "
            "this report keeps a tolerance column instead of going red — but a money tolerance "
            "above zero would make the report worthless, so it is fixed at zero and not "
            "configurable.\" A ZERO, NON-CONFIGURABLE money tolerance is a property of the "
            "CHECK. There is nowhere on an account row for it to live."
        ),
    },
}


class UnservableFromThisDataset(ValueError):
    """Raised when a caller asks this dataset for a report it does not state.

    ⚠ **IT RAISES RATHER THAN RETURNING AN EMPTY LIST, AND THAT IS THE WHOLE
    POINT.** An empty result reads as *no rows matched*, which is a legitimate
    answer a clerk will act on. A refusal that names the report, the grain and
    the read model is the only output a reader can tell apart from a working
    report — hard-won law 7's third habit: *a check's output must distinguish
    pass from fail to a READER, not merely to an exit code.*
    """


def unservable_reason(code: str) -> dict[str, Any]:
    """The refusal row for one report key, or `KeyError` if it is not refused."""
    return dict(UNSERVABLE_HERE[code])


def refuse(code: str) -> None:
    """Raise `UnservableFromThisDataset` naming the report and what it needs."""
    row = UNSERVABLE_HERE[code]
    raise UnservableFromThisDataset(
        f"{row['report']} is seeded on the `accounts` dataset and states the grain "
        f"'{row['drawn_grain']}'. This dataset states 'one account'. "
        f"{row['why_not_here']} It needs: {', '.join(row['needs_read_model'])}."
    )


@dataclass(frozen=True)
class AccountFactRow:
    """One account, in the dataset's own declared column names.

    ⚠ **`kind` TRAVELS SO A MASTER CAN BE MARKED (BR-CUS-068, p071).** It is
    never filtered out and never merged into anything.

    ⚠ **THERE IS NO ADDRESS COLUMN.** `premises_line1`, `locality` and
    `unit_label` are the PREMISES' own fields, walked to (hard rule 8); a unit
    refines its premises by LABEL and declares no address of its own.

    ⚠ **`account_class` AND `status` ARE AS-WAS WHERE A HISTORY PERIOD COVERS
    `as_of`, AND AS-IS WHERE NONE DOES — `attribute_basis` SAYS WHICH, PER
    ROW.** The fallback is never silent: `GAP_SOME_ATTRIBUTES_FELL_BACK_TO_AS_IS`
    is published with the COUNT whenever a served row took it.
    """

    account_id: str
    account_no: str | None
    kind: str
    customer_id: str | None
    customer_name: str | None
    customer_type: str | None
    account_class: str | None
    status: str | None
    status_behaviour: str | None
    #: `"as_was"` when a history period covered `as_of`, `"as_is"` otherwise —
    #: and `"as_is"` on every read that states no `as_of` at all, which is the
    #: honest label for *today*. §7.2.4: a mixed report states both.
    attribute_basis: str
    opened_on: date | None
    closed_on: date | None
    premises_id: str | None
    premises_no: str | None
    premises_line1: str | None
    unit_label: str | None
    locality: str | None
    services: tuple[str, ...]
    balance: Decimal
    currency: str


def _tenant_id() -> Any:
    return current_tenant_id()


def _base(
    *,
    as_of: date | None,
    opened_from: date | None,
    opened_to: date | None,
    account_class: Any,
    status: Any,
    customer_type: str | None,
    service: str | None,
    **unhonoured: Any,
) -> Any:
    """The filtered set, every criterion a `WHERE` — hard rule 1 first.

    ⚠ **THE TENANT FILTER IS THE FIRST CLAUSE AND IS NOT OPTIONAL.** RLS FORCE
    is on and would refuse a cross-tenant row anyway, but a queryset that relies
    on the database to be the only guard is a queryset that is wrong the day
    somebody runs it as an owner. Belt and policy.

    ⚠ **`as_of` DOES TWO DIFFERENT THINGS AND BOTH ARE REAL.** It is the
    MEMBERSHIP window here (two stored dates), and it is the date the CLASS and
    STATUS filters below resolve as-was against — because a filter must match
    the value the row shows, or the chip lies.

    ⚠ **AN UNHONOURED FILTER RAISES.** Silently ignoring `route` would serve the
    whole utility under a chip that names one route.
    """
    named = {key for key, value in unhonoured.items() if value not in (None, "")}
    if named:
        raise UnservableFromThisDataset(
            "the `accounts` dataset query does not honour "
            + ", ".join(sorted(named))
            + ". Reaching an account's route means walking account → unit → service point → "
            "route and customers publishes no such seam; `apps.metering.selectors."
            "route_accounts` answers from the other end. Serving the whole set under a route "
            "chip would be a live screen behind a broken control."
        )

    rows = models.Account.objects.filter(tenant_id=_tenant_id())
    if as_of is not None:
        # Membership as at the date: opened on or before it, and not yet closed
        # on it. An account with no `opened_at` is INCLUDED — a legacy import
        # that never carried a move-in date is a real account, and excluding it
        # would make a census silently smaller than the utility.
        rows = rows.filter(Q(opened_at__isnull=True) | Q(opened_at__lte=as_of))
        rows = rows.filter(Q(closed_at__isnull=True) | Q(closed_at__gt=as_of))
    if opened_from is not None:
        rows = rows.filter(opened_at__gte=opened_from)
    if opened_to is not None:
        rows = rows.filter(opened_at__lte=opened_to)
    # ⚠ **A FILTER MUST MATCH THE VALUE THE ROW SHOWS, OR THE CHIP LIES.** On
    # an as-at read the CLASS and STATUS columns are as-was wherever a history
    # period covers the date, so filtering on today's column would serve rows
    # whose own displayed class is something else — a chip reading *Residential*
    # over a row that says *Commercial*. Both halves are expressed as `WHERE`
    # clauses: the as-was match for accounts a period covers, and the current
    # column for accounts it does not. Nothing is filtered in Python.
    if as_of is not None and (account_class or status):
        covered = _history_covering(as_of)
        matched = covered
        if account_class:
            matched = matched.filter(account_type_id=account_class)
        if status:
            matched = matched.filter(status_id=status)
        current = Q()
        if account_class:
            current &= Q(account_type_id=account_class)
        if status:
            current &= Q(status_id=status)
        rows = rows.filter(
            Q(id__in=matched.values("account_id"))
            | (~Q(id__in=covered.values("account_id")) & current)
        )
    else:
        if account_class:
            rows = rows.filter(account_type_id=account_class)
        if status:
            rows = rows.filter(status_id=status)
    if customer_type:
        # `person` | `company` on the CUSTOMER, reached through the live link.
        rows = rows.filter(
            customeraccount__ended_at__isnull=True,
            customeraccount__customer__kind=str(customer_type),
        )
    if service:
        # A service the account has an agreement FOR. `ended_on IS NULL` is
        # "still in force" (ServiceAgreement's own column comment).
        point_ids = list(
            models.ServiceAgreement.objects.filter(
                tenant_id=_tenant_id(), ended_on__isnull=True
            ).values_list("service_point_id", flat=True)
        )
        codes = seams.service_codes_for_points(point_ids) or {}
        wanted = [pid for pid in point_ids if codes.get(str(pid)) == str(service)]
        rows = rows.filter(
            id__in=models.ServiceAgreement.objects.filter(
                tenant_id=_tenant_id(), ended_on__isnull=True, service_point_id__in=wanted
            ).values("account_id")
        )
    return rows


def _sum(expression: str, *, only: Q | None = None) -> Any:
    """Σ as a Decimal, with an empty set reading `0` rather than SQL NULL.

    `Coalesce(..., Value(ZERO))` rather than `or ZERO` in Python: an aggregate
    over no rows returns NULL, and *"no accounts"* and *"accounts that net to
    nothing"* are both zero money owed. What is NOT zero-filled is a figure that
    could not be DERIVED; that is `None` beside a named reason (BR-REP-024).
    """
    return Coalesce(
        Sum(expression, filter=only, output_field=_MONEY), Value(ZERO, output_field=_MONEY)
    )


def _one_currency(rows: Any) -> tuple[str | None, dict[str, Any] | None]:
    """The single currency of the filtered set, or no figure at all (DEF-081).

    ⚠ **ASKED BEFORE ANY Σ, NEVER AFTER.** Adding 100 USD to 100 CAD produces
    200 of nothing, and the resulting tile is not visibly wrong — it is a
    plausible number in the wrong unit, which is hard rule 2's whole concern.
    """
    found = sorted({code for code in rows.values_list("currency", flat=True).distinct() if code})
    if len(found) <= 1:
        return (found[0] if found else None), None
    return None, {
        "code": "the_set_holds_more_than_one_currency",
        "br_ref": "CLAUDE.md hard rule 2 · DEF-081",
        "detail": (
            "These accounts are denominated in "
            + ", ".join(found)
            + ". A money total across two currencies is a number in no currency at all, so no "
            "total is published. Filter to one currency to get a figure."
        ),
        "wanted_reads": (),
    }


def _history_covering(on: date) -> Any:
    """The attribute-history periods in force on `on` — hard rule 1 first.

    ⚠ **TWO CLAUSES, NEVER ONE OR'd FILTER AGAINST NULL.** The OPEN period has
    `effective_to IS NULL`, and no comparison against NULL is ever true, so
    `effective_to__gt=on` alone silently returns nothing for every date inside
    the CURRENT period — which is most dates anyone asks about.
    `attribute_history.as_was` records the same trap in its own exceptions
    block; this is the set-shaped form of the same query.
    """
    return AccountAttributeHistory.objects.filter(
        tenant_id=_tenant_id(), effective_from__lte=on
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gt=on))


def _behaviour_q(classes: tuple[str, ...], as_of: date | None) -> Q:
    """`Q` matching accounts whose BEHAVIOUR CLASS is one of `classes`, on basis.

    With no `as_of` this is today's column and nothing else. With one it is the
    same two branches the class/status filter uses: the as-was period where one
    covers the date, today's column where none does. Built as a `Q` so it can
    be handed to `Count(filter=...)` and stay inside the one aggregate call.
    """
    current = Q(status__behavior_class__in=classes)
    if as_of is None:
        return current
    covered = _history_covering(as_of)
    matched = covered.filter(status__behavior_class__in=classes)
    return Q(id__in=matched.values("account_id")) | (
        ~Q(id__in=covered.values("account_id")) & current
    )


def _as_was_for(account_ids: list[Any], on: date) -> dict[str, dict[str, Any]]:
    """A PAGE's as-was class, type and status — **ONE query, never one per row.**

    ⚠ **`attribute_history.as_was()` IS DELIBERATELY NOT CALLED HERE.** It takes
    ONE account id, so a page of fifty is fifty round trips and a 40,000-row
    export is forty thousand — the N+1 `DEF-2723` closed on the accounts list
    and `P2.21` closed on the ageing report. This reads the same table, in the
    same module, in one statement. Nothing crosses a boundary and B1 is not
    bent.

    An id ABSENT from this map has no period covering `on`. That is a STATED
    ABSENCE and the caller falls back to as-is EXPLICITLY and marks the row; it
    never substitutes the current row for a missing one, which is what
    `attribute_history`'s own docstring forbids.
    """
    if not account_ids:
        return {}
    rows = _history_covering(on).filter(account_id__in=account_ids).values(
        "account_id",
        "account_type_id",
        "account_type__name",
        "status_id",
        "status__name",
        "status__behavior_class",
    )
    return {str(row["account_id"]): row for row in rows}


def _customers_for(account_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """A PAGE's customers — ONE query, never one per row.

    The LIVE link only (`ended_at IS NULL`): a transferred-away customer is not
    who the account belongs to now, and showing them would name the wrong party
    on a census. `is_primary` first so a two-customer account names the one the
    bill is addressed to.
    """
    if not account_ids:
        return {}
    rows = (
        models.CustomerAccount.objects.filter(
            tenant_id=_tenant_id(), account_id__in=account_ids, ended_at__isnull=True
        )
        .order_by("account_id", "-is_primary", "created_at")
        .values("account_id", "customer_id", "customer__display_name", "customer__kind")
    )
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row["account_id"])
        if key in found:  # the first is the primary, by the order above
            continue
        found[key] = {
            "customer_id": str(row["customer_id"]),
            "customer_name": row["customer__display_name"],
            "customer_type": row["customer__kind"],
        }
    return found


def _places(accounts: list[Any]) -> dict[str, dict[str, Any]]:
    """A PAGE's addresses, WALKED to `premises` (hard rule 8) in two statements.

    `seams.envelope_addresses` is metering's own batched read — one query for
    the units named and one for the premises named directly. Nothing per row,
    and no address column anywhere in this module.

    ⚠ **`None` FROM THE SEAM MEANS METERING CANNOT ANSWER AND IS NOT AN EMPTY
    MAP.** The two are different facts and are kept apart: an unanswerable seam
    leaves every place absent, which is a fact about the PLATFORM, while an
    answered-but-blank street is a fact about the PROPERTY.
    """
    unit_ids = [a.unit_id for a in accounts if a.unit_id]
    premises_ids = [a.premises_id for a in accounts if a.premises_id and not a.unit_id]
    if not unit_ids and not premises_ids:
        return {}
    envelopes = seams.envelope_addresses(unit_ids=unit_ids, premises_ids=premises_ids)
    if envelopes is None:
        return {}
    by_unit = envelopes.get("units") or {}
    by_premises = envelopes.get("premises") or {}
    resolved: dict[str, dict[str, Any]] = {}
    for account in accounts:
        env = None
        if account.unit_id:
            env = by_unit.get(str(account.unit_id))
        elif account.premises_id:
            env = by_premises.get(str(account.premises_id))
        if env is not None:
            resolved[str(account.id)] = env
    return resolved


def _services_for(account_ids: list[Any]) -> dict[str, tuple[str, ...]]:
    """A PAGE's service codes — R22's SERVICES column, two queries, not two per row.

    ⚠ **HARD RULE 3 IS WHY THESE ARE CODES AND NOT A COUNT.** `Water · Sewer ·
    Trash` is three services with three units of consumption; a column reading
    `3` would invite a total, and `NO TOTAL USAGE TILE ON A MULTI-SERVICE
    ACCOUNT` is the brief's own rule for exactly that reason (p062).

    `ended_on IS NULL` is the agreement's own "still in force".
    """
    if not account_ids:
        return {}
    agreements = list(
        models.ServiceAgreement.objects.filter(
            tenant_id=_tenant_id(), account_id__in=account_ids, ended_on__isnull=True
        ).values_list("account_id", "service_point_id")
    )
    if not agreements:
        return {}
    codes = seams.service_codes_for_points([point for _, point in agreements]) or {}
    grouped: dict[str, list[str]] = {}
    for account_id, point_id in agreements:
        code = codes.get(str(point_id))
        if not code:
            continue
        bucket = grouped.setdefault(str(account_id), [])
        if code not in bucket:
            bucket.append(code)
    return {key: tuple(value) for key, value in grouped.items()}


def _shape(
    account: Any,
    customers: dict[str, dict[str, Any]],
    places: dict[str, dict[str, Any]],
    services: dict[str, tuple[str, ...]],
    as_was: dict[str, dict[str, Any]],
) -> AccountFactRow:
    """One stored account, in the dataset's declared column names.

    ⚠ **THE AS-WAS PERIOD WINS WHERE THERE IS ONE, AND THE ROW SAYS SO.** A
    missing period is a STATED ABSENCE (`attribute_history.as_was` forbids
    substituting the current row for it), so the fallback is explicit, marked
    on the row, and counted in `problems`.
    """
    key = str(account.id)
    customer = customers.get(key) or {}
    place = places.get(key) or {}
    period = as_was.get(key)
    locality_parts = [place.get("city"), place.get("state"), place.get("postal_code")]
    locality = ", ".join([str(part) for part in locality_parts[:2] if part]) or None
    if locality and place.get("postal_code"):
        locality = f"{locality} {place['postal_code']}"
    return AccountFactRow(
        account_id=key,
        # ⚠ The account NUMBER, never the uuid — B14 rule 31.
        account_no=account.account_no,
        kind=account.kind,
        customer_id=customer.get("customer_id"),
        customer_name=customer.get("customer_name"),
        customer_type=customer.get("customer_type"),
        account_class=(
            period["account_type__name"]
            if period
            else (getattr(account.account_type, "name", None) if account.account_type_id else None)
        ),
        status=(
            period["status__name"]
            if period
            else (getattr(account.status, "name", None) if account.status_id else None)
        ),
        status_behaviour=(
            period["status__behavior_class"]
            if period
            else (getattr(account.status, "behavior_class", None) if account.status_id else None)
        ),
        attribute_basis="as_was" if period else "as_is",
        opened_on=account.opened_at,
        closed_on=account.closed_at,
        premises_id=place.get("premises_id"),
        premises_no=None,
        premises_line1=place.get("line1"),
        unit_label=place.get("unit_label"),
        locality=locality,
        services=services.get(key, ()),
        balance=account.balance,
        currency=account.currency,
    )


def _shape_all(materialised: list[Any], as_of: date | None = None) -> list[AccountFactRow]:
    """Four bounded batched reads, then the rows. Never one query per row."""
    account_ids = [a.id for a in materialised]
    customers = _customers_for(account_ids)
    places = _places(materialised)
    services = _services_for(account_ids)
    as_was = _as_was_for(account_ids, as_of) if as_of is not None else {}
    return [_shape(a, customers, places, services, as_was) for a in materialised]


def _ordered(rows: Any, sort: str | None, direction: str) -> Any:
    """The order, applied IN SQL — including the one that needs a join.

    `customer_name` lives on `customers` and is reached through the live link
    row. It is annotated as a correlated subquery rather than joined, because a
    JOIN onto a table an account can have several rows in multiplies the page
    and a page that multiplies is a clerk seeing one account twice.
    """
    from django.db.models import OuterRef, Subquery

    if sort == "customer_name":
        link = (
            models.CustomerAccount.objects.filter(
                tenant_id=_tenant_id(), account_id=OuterRef("pk"), ended_at__isnull=True
            )
            .order_by("-is_primary", "created_at")
            .values("customer__display_name")[:1]
        )
        rows = rows.annotate(_customer_name=Subquery(link))
    return rows.order_by(
        *order_terms(sort, direction, columns=ACCOUNT_SORT_COLUMNS, default=ACCOUNT_DEFAULT_SORT)
    ).select_related("status", "account_type")


def accounts_dataset(
    *,
    as_of: date | None = None,
    opened_from: date | None = None,
    opened_to: date | None = None,
    account_class: Any = None,
    status: Any = None,
    customer_type: str | None = None,
    service: str | None = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = "asc",
    **unhonoured: Any,
) -> dict[str, Any]:
    """THE dataset query — R22 Account Census. One row per account, paged in SQL.

    `per=None` is the whole filtered set. `per` is an integer page size; the
    CALLER clamps it (`core.pagination.clamp_page_size`) and this function does
    not invent one, because a cap invented here is a cap nobody can see
    (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `accounts_dataset_stream()`** — it takes no `page`
    and no `per`, so an export has no argument through which to inherit a
    screen's fifty rows.

    **`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET AND NEVER OVER
    THE PAGE**, so R22's four tiles foot to the report whether a page is cut or
    not.
    """
    rows = _base(
        as_of=as_of,
        opened_from=opened_from,
        opened_to=opened_to,
        account_class=account_class,
        status=status,
        customer_type=customer_type,
        service=service,
        **unhonoured,
    )

    currency, currency_problem = _one_currency(rows)

    # ── the tiles: ONE aggregate call, so every figure is struck over the same
    # snapshot of the same rows. Two round trips could see two different books.
    # ⚠ **THE ALIASES DO NOT SHADOW THE FIELD.** `aggregate(balance=Sum(
    # "balance"))` makes Django resolve the inner name against the alias it is
    # building and raise; it is a real refusal rather than a wrong number, but
    # it only shows when the function is CALLED.
    # ⚠ **THE ACTIVE AND CLOSED TILES READ THE SAME BASIS THE ROWS DO.** On an
    # as-at read a row shows its as-was status, so a tile counted off today's
    # `status__behavior_class` would not foot to the rows underneath it — the
    # exact defect a KPI tile exists to avoid, and one that produces a
    # plausible number rather than an error. `_behaviour_q()` builds the same
    # two-branch predicate the filter above uses, entirely in SQL.
    aggregated = rows.aggregate(
        account_count=Count("id"),
        # BR-CUS-055: the CLASS, never the tenant's label.
        active_count=Count("id", filter=_behaviour_q(BEHAVIOUR_ACTIVE, as_of)),
        closed_count=Count("id", filter=_behaviour_q(BEHAVIOUR_CLOSED, as_of)),
        with_balance_count=Count("id", filter=~Q(balance=ZERO)),
        balance_sum=_sum("balance"),
        with_balance_sum=_sum("balance", only=~Q(balance=ZERO)),
        master_count=Count("id", filter=Q(kind=KIND_MASTER)),
    )
    total_accounts = int(aggregated["account_count"])

    problems: list[dict[str, Any]] = [dict(GAP_NO_FULLY_ADDITIVE_MEASURE)]
    if currency_problem is not None:
        problems.append(currency_problem)


    # ── the page, cut in SQL ────────────────────────────────────────────────
    ordered = _ordered(rows, sort, direction)

    served_page = max(1, int(page or 1))
    if per is None:
        window = ordered
        pages = 1
    else:
        size = max(1, int(per))
        pages = max(1, -(-total_accounts // size))
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        window = ordered[offset : offset + size]

    materialised = list(window)
    shaped = _shape_all(materialised, as_of)
    if any(row.premises_line1 is None for row in shaped):
        problems.append(dict(GAP_PLACE_IS_UNRESOLVED))
    # ⚠ Published only when a SERVED row actually fell back, WITH THE COUNT —
    # a caveat with no number beside it is indistinguishable from an empty one.
    if as_of is not None:
        fell_back = sum(1 for row in shaped if row.attribute_basis == "as_is")
        if fell_back:
            problems.append(GAP_SOME_ATTRIBUTES_FELL_BACK_TO_AS_IS(fell_back, len(shaped)))

    share = None
    if total_accounts:
        share = (Decimal(int(aggregated["with_balance_count"])) / Decimal(total_accounts)) * Decimal(
            100
        )

    return {
        "basis": BASIS,
        "grain": "one account",
        "as_of": as_of,
        "currency": currency,
        "rows": tuple(shaped),
        "totals": {
            # Semi-additive: across accounts, never across time (§7.2.2).
            "accounts": total_accounts,
            "active": int(aggregated["active_count"]),
            "closed": int(aggregated["closed_count"]),
            "with_balance": int(aggregated["with_balance_count"]),
            # BR-CUS-068 / p071 — a master is MARKED, never merged. The count
            # travels so a renderer can say how many rows are marked; it is NOT
            # subtracted from `accounts`.
            "master_accounts": int(aggregated["master_count"]),
            "balance": None if currency_problem else aggregated["balance_sum"],
            "with_balance_amount": None if currency_problem else aggregated["with_balance_sum"],
            # Non-additive: recomputed, never averaged. `None` not `0` when the
            # denominator is zero — a share of nothing is not a number.
            "with_balance_pct": share,
        },
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": total_accounts,
        "problems": tuple(problems),
    }


#: How many rows one round trip of the export fetches. A BUFFER, not a cap
#: (`NFR-5`): the generator goes on until the cursor is exhausted and there is
#: no number any row can be beyond.
STREAM_CHUNK = 2_000


def accounts_on_the_books(*, as_of: date) -> int:
    """How many accounts this utility had on ONE day — R22's membership, counted.

    `CR-142-BRC07` `P6.11` wave 3. R43's ACCOUNTS column is *how many accounts
    were on the books at the end of this fiscal period*, twelve times, and its
    ACCOUNTS tile is the growth between the first and the last.

    ⚠ **IT CALLS `_base` AND DERIVES NOTHING OF ITS OWN, WHICH IS THE POINT.**
    *Membership as at a date* is already decided in one place — `opened_at` on
    or before the day, `closed_at` absent or after it, and an account with no
    `opened_at` INCLUDED because a legacy import that never carried a move-in
    date is a real account. Writing that again here is how the census and the
    trend pack come to report two different sizes for one utility on one day
    (hard-won law 5), and the difference would be invisible: both numbers are
    plausible and neither screen shows the other.

    ⚠ **`.count()` IS AN AGGREGATE AND THE ROWS ARE NEVER BUILT.** At the top of
    the ICP this is forty thousand rows and the answer is one integer; twelve
    periods is twelve aggregates.

    ⚠ **`as_of` IS AN ARGUMENT AND NEVER A CLOCK** (`BR-TEN-043`).
    """
    return int(
        _base(
            as_of=as_of,
            opened_from=None,
            opened_to=None,
            account_class=None,
            status=None,
            customer_type=None,
            service=None,
        ).count()
    )


def accounts_dataset_stream(
    *,
    as_of: date | None = None,
    opened_from: date | None = None,
    opened_to: date | None = None,
    account_class: Any = None,
    status: Any = None,
    customer_type: str | None = None,
    service: str | None = None,
    sort: str | None = None,
    direction: str = "asc",
    **unhonoured: Any,
) -> Iterator[AccountFactRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    ⚠ **THE ABSENCE OF THOSE TWO PARAMETERS IS THE WHOLE DESIGN.** An export
    cannot inherit a screen's fifty rows because there is no argument through
    which to pass them. When the billing register started paging, its export
    inherited the page and shipped a valid-looking file of 50 rows from a
    38,000-row report — a flag would have had the same bug; a missing parameter
    cannot.

    ⚠ **`NFR-5` — NO CAP, ANYWHERE ON THIS PATH.** `STREAM_CHUNK` is a fetch
    buffer rather than a ceiling: the loop runs until the cursor is exhausted.

    The order is applied IN SQL, the same `order_terms` the page uses, so the
    file and the screen sort identically. Labels are resolved per chunk —
    bounded, batched, never one query per row.
    """
    rows = _ordered(
        _base(
            as_of=as_of,
            opened_from=opened_from,
            opened_to=opened_to,
            account_class=account_class,
            status=status,
            customer_type=customer_type,
            service=service,
            **unhonoured,
        ),
        sort,
        direction,
    )
    buffer: list[Any] = []
    for account in rows.iterator(chunk_size=STREAM_CHUNK):
        buffer.append(account)
        if len(buffer) >= STREAM_CHUNK:
            yield from _shape_all(buffer, as_of)
            buffer = []
    if buffer:
        yield from _shape_all(buffer, as_of)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 · the `accounts` dataset query (05-prototype/09 Reports Build Brief.pdf p059–p061, p068–p069, p071 read as IMAGES per B14 rule 42; §7.2/§7.2.2/§7.2.3/§7.2.4 p083–p086; §7.5/§7.6 p087; §08 p090–p092)
# screens: S46 (the viewer) — R22 Account Census
# generated: 2026-09-27 by lane DS-ACCOUNTS
# checklist: A✔ B✔ C✔ D=deferred(registration is lane REP-UNBLOCK's this session — `apps/reports/datasets.py` and `queries.py`; this lane adds NO endpoint and says so rather than claiming one) E✔(the S46 viewer renders every dataset and needs nothing new — the frontend half is owed nothing by this file) F✔ G✔ H=deferred(HUMAN-REVIEW-PENDING — the row is in 12-governance/09-human-review-ledger.md, dated 2026-09-27, written BEFORE the review)
# gates: RED PROVED FIRST, THROUGH pytest — the harness that runs them. Four mutations, four reds, each naming its false pass: the ACTIVE tile keyed on `status__name="Active"` (fixture statuses are French, so it measures 0 active over 3 live) · `totals` struck over the PAGE instead of the book (`accounts: 2` for a per=2 request) · `premises_line1` composed from nothing (DEF-CUS-3653's shape — null on every account forever, every test green) · and the four refusal rows deleted. Restored and re-run GREEN: 51 passed. Isolation on real PostgreSQL 16: `rep_ds_accounts_rls_proof.py` — accounts/audit_log/outbound_messages all ENABLE+FORCE, both policy halves, own rows 75 non-zero beside the neighbour's 0 on three probes, with a red-first control that EXITS if it is measuring an empty table, as a role that is neither SUPERUSER nor BYPASSRLS.
# exceptions: (1) FOUR of the five reports seeded onto this dataset are REFUSED BY NAME in `UNSERVABLE_HERE` — R23, R26, R27 and R41 each state a grain that is not one account · (2) `as_of` answers MEMBERSHIP from two stored dates AND resolves class/type/status AS-WAS through `AccountAttributeHistory` (§7.2.4 option (b), ruled AND BUILT as `P0.18` — the brief's own §7.2.4 measurement that customers "has no effective dating of any kind" is STALE and this file says so rather than repeating it); a row with no period covering the date falls back to as-is, is marked `attribute_basis="as_is"`, and is COUNTED in `problems` · (3) the registry's `route` filter is NOT honoured and raises rather than serving the whole set · (4) this file writes nothing: no INSERT, UPDATE, DELETE or save()
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
