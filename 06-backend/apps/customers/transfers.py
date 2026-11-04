# ── Trace ──────────────────────────────────────────────
# Change:   ⛔ CR-058 tasks 14–18 (2026-09-01) — **a transfer REASSIGNS the
#           account**. This REVERSES CR-030 W7's shipped behaviour; see the
#           module docstring's §0 and BR-CUS-1030.
# Rules:    BR-CUS-1030 (the reassignment — SUPERSEDES what W7 built) ·
#           BR-CUS-1031 (a customer MOVING is a new Service Request) ·
#           BR-CUS-1023 · BR-CUS-1022 · BR-CUS-1011 · OQ-1252 (CLOSED —
#           the debt follows the property) · OQ-1253 (open — must the
#           BUYER be shown it)
# Story:    US-CUS-004 (move-in) · US-CUS-005 (move-out) — a transfer is the
#           THIRD path beside them and owns no story of its own yet.
#           Screens: S89 (Transfers tab + its 5-step wizard) — NOT built here.
# Change:   CR-030 W7 tasks 7.1 (table + RLS, five steps, one commit for both
#           halves) · 7.2 (the exclusion contract) · 7.3 (the deposit carries
#           without a refund-and-recollect; arrears follow)
# Rules:    BR-CUS-017 (one occupying account per unit) · BR-CUS-023 (the
#           deposit is a lookup; every write path is refused) · BR-CUS-024
#           (deposit carry-forward — mechanics PROPOSED) · BR-CUS-025 (the
#           deposit settles EVERYTHING outstanding at close, and that is the
#           only time it moves) · BR-CUS-030 (move-out closes the account) ·
#           BR-CUS-054 (the customer entity and `customer_accounts`) ·
#           BR-CUS-057 (deposit interest — CONFIRMED, NOT BUILT) · BR-CUS-081
#           (settle-and-refund at close) · BR-CUS-082 (a debt surviving closure
#           is chased, ladder restarts at TIER 1) · BR-CUS-089 (money moves
#           only on a `strong` identity match) · BR-CUS-097 (a sub-account's
#           residue moves to its master) · BR-MET-036 (occupancy is derived) ·
#           CLAUDE.md hard rules 1, 2, 4, 5, 7
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.7 (§5.7.2 the
#           list · §5.7.3 the ONE JOB callout · §5.7.4 the five steps · §5.7.5
#           TC-TRF-1..6 · §5.7.6 the five seed rows) · §9 the money map · W7
#           tasks 7.1/7.2/7.3
# Tests:    06-backend/tests/test_w7_transfers.py
# ───────────────────────────────────────────────────────
"""W7 · TRANSFERS — one job, not a move-out followed by a move-in.

🔒 **HUMAN-OWNED · HUMAN-REVIEW-PENDING.** This file holds RLS-scoped writes,
money rounding and — since `BR-CUS-1081` on 2026-09-20 — the capture of customer
IDENTITY (a date of birth, a Social Security number, a driving licence) and the
rewrite of who a live account's money belongs to. All of those are on CLAUDE.md's
sensitive-paths list. **The ledger row is `BR-CUS-1081` in
`12-governance/09-human-review-ledger.md`**, written before review per r11 step 4
and stating in plain English, with the **$150.00** figure, the one judgment a
reviewer should weigh: that nothing the ruling added was made compulsory.
⚠ **This file's `exceptions` note at the foot said there was NO SUCH ROW.** That
was true from 2026-08-25 until 2026-09-20 and it is not any more.

B18 §5.7, verbatim: *"The same customer, a new address — **one job, not a
move-out followed by a move-in.**"*

════════════════════════════════════════════════════════════════════════════
1 · HOW "ONE COMMIT FOR BOTH HALVES" IS GUARANTEED (task 7.1)
════════════════════════════════════════════════════════════════════════════
A transfer closes an account at one unit and opens one at another. Half-applied,
it leaves a customer with **no service** (closed, nothing opened) or **two live
accounts** (opened, the old one never closed) — and the second is worse, because
it bills twice and nobody notices until the customer rings.

`commit_transfer` is the only function that performs either half, and it does
both inside ONE `transaction.atomic()` block:

  1. `django.db.transaction.atomic()` opens.
  2. the transfer row is re-read `select_for_update()` — a second commit of the
     same job blocks here, then finds `committed_at` already set and is refused
     as `BIZ-IDEMPOTENT`. The partial unique index `uq_transfers_open_from`
     (migration 0021) is the same guarantee at the database, for the case where
     two jobs are started rather than one job committed twice.
  3. the OUTGOING half runs through `services.move_out` — the signed BR-CUS-030
     path, not a copy of it.
  4. the INCOMING half runs through `services.create_account` — the public door
     into `services._open_account`, which is *"the one code path that brings an
     account row into existence"* and where BR-CUS-017's occupancy guard lives.
     A second creator here would be a second, drifting copy of the only thing
     standing between one meter and two bills.
  5. the `customer_accounts` link (BR-CUS-054) is written for the new account,
     to the SAME `customers` row the outgoing account hangs off. Same customer
     is what makes this a transfer rather than two jobs.
  6. `committed_at`, `to_account_id`, `state` and `step` are written on the
     transfer row.

Steps 3–6 raise rather than return on any refusal, so the `atomic()` block
unwinds and **nothing** is left behind: no closed account, no orphan account,
no half-linked customer, no `committed_at`. The audit rows the two service
calls write are inside the same transaction and roll back with it, which is the
point of writing them through `audit_log` rather than to a log file.

⚠ **WHAT ATOMICITY DOES *NOT* BUY, AND IT MUST BE SAID:** it makes the two
halves land together. It does not make the MONEY land, because no signed rule
says how money moves on a transfer — section 3 below.

════════════════════════════════════════════════════════════════════════════
2 · THE EXCLUSION CONTRACT (task 7.2) — a CONTRACT, not a filter
════════════════════════════════════════════════════════════════════════════
B18 §5.7.3, verbatim, and it is a callout on the screen:

> **ONE JOB** — *"A transfer appears only here. Its two halves are deliberately
> kept out of Move-ins and Move-outs — the same job listed three times would be
> counted three times."*

and §5.7.3's own gloss: *"**This is a counting contract between tabs.** The
Move-ins tab shows **3** and the Move-outs tab **5**; if a transfer's halves
leaked in they would read 4 and 6 and the KPI strips would lie. **A test must
assert the exclusion**, because nothing else will catch it."*

⚠ **WHERE IT HAD TO LIVE, MEASURED 2026-08-25: NOWHERE, BECAUSE NEITHER LIST
EXISTS YET.** `07-frontend/src/features/customers/AccountsListPage.tsx` renders
the `move-ins` and `move-outs` tabs as `<ArrivesWith … tracks="OQ-350" />` and
`tracks="OQ-346"` — a stated absence, not a table. On the server there is no
`move_in_list`, no `move_out_list` and no move selector of any name in
`apps/customers/selectors.py`, and B18 §6.2 lists their endpoints as `❌`. So
there is no filter to add and no queryset to subtract from.

**What this module publishes instead is the contract itself**, so that the lane
that DOES build those lists cannot build them without meeting it:

    transfer_half_account_ids()   → the account ids a move list must not show
    is_transfer_half(account_id)  → the per-row predicate
    exclude_transfer_halves(qs)   → the queryset filter, ready to use

and `tests/test_w7_transfers.py` asserts BOTH halves of the contract: the
predicate's behaviour on a real committed transfer, AND — statically, over the
tree — that no move-in/move-out list builder has appeared that fails to call
one of the three. That second case is the one that will go red on somebody
else's commit, which is exactly what B18 asks for.

⚠ **AND ONE LEAK VECTOR IS NAMED RATHER THAN CLOSED.** `services.move_out`
writes an `account.closed` audit row and `services.create_account` writes an
`account.created` one, and this module calls both. A Move-outs list built by
reading `audit_log` for `account.closed` WOULD therefore pick up a transfer's
outgoing half. That is not fixable from here — renaming the audit action would
mean editing `services.py`, which is outside this lane's write scope, and the
action name is a contract other readers already depend on. It is REPORTED, and
`exclude_transfer_halves` is the answer for that reader too.

════════════════════════════════════════════════════════════════════════════
3 · THE MONEY (task 7.3) — the deposit carries WITHOUT a refund-and-recollect
════════════════════════════════════════════════════════════════════════════
B18 §5.7.2's MONEY cell stacks up to two sentences — `deposit carried $153.50`
and, beneath it in amber, `arrear follows $542.10`. §5.7.5's TC-TRF-3 is
explicit: *"both carried; **the deposit is not refunded and re-collected**."*

**A TRANSFER IS A THIRD PATH AND IT MUST NOT INHERIT THE MOVE-OUT'S
BEHAVIOUR.** Four signed rules touch this event and they do not agree:

  · **BR-CUS-025** (scope AMENDED, PO 2026-08-12): at close the deposit and its
    interest apply to *"EVERYTHING OUTSTANDING"*, and — verbatim — *"THIS IS THE
    ONLY TIME THE DEPOSIT MOVES"*.
  · **BR-CUS-081** (CONFIRMED, PO 2026-08-24): a closing balance the deposit
    more than covers is SETTLED from the deposit and the difference REFUNDED —
    *"settle the $142.30 and refund $11.20"*.
  · **BR-CUS-082** (CONFIRMED, PO 2026-08-24): a debt surviving closure is
    STILL CHASED and the dunning ladder RESTARTS FROM TIER 1.
  · **BR-CUS-097** (CONFIRMED for the transfer, OPEN on who is chased): a
    sub-account's unpayable residue moves to its master.

Read on a transfer, BR-CUS-025 + BR-CUS-081 say the $153.50 deposit is applied
to the $542.10 arrear and only $387.90 survives; BR-CUS-082 says that $387.90
is then chased with a fresh TIER 1 ladder — against a customer who has not left
and is standing at a new address taking service. B18 §5.7 says instead that BOTH
figures carry, gross, to the new account. **Those are different products, and
choosing between them is resolving an open question by picking a value.**

⚠ **NO OPEN QUESTION COVERS IT. ONE IS OWED AND THIS LANE MAY NOT MINT IT** —
`12-governance/` is outside this lane's write scope, and the prime directive
forbids inventing an OQ id. The question, stated so whoever writes the row does
not have to reconstruct it, with B18's own figures:

    Jenna Park transfers from A-11455 to A-12055 owing $542.10, with $153.50
    of deposit and interest held. Does the close settle $153.50 of the $542.10
    (BR-CUS-025/081) and hand $388.60 to the new account with no deposit — or
    does the whole $153.50 and the whole $542.10 move across, which is what
    B18 §5.7.6 draws and what the Transfers tab's two KPI captions ("not
    refunded and re-collected", "a debt moving to a new account") describe?
    And on the second reading, does BR-CUS-082's TIER 1 ladder start at all,
    given the customer has not left?

**SO NOTHING IS MOVED, AND THAT IS BUILDABLE RATHER THAN A DEAD END**, because
the sentence B18 actually signs off on — *"the deposit is not refunded and
re-collected"* — is a statement about what must NOT happen, and this module can
guarantee it exactly:

  · the outgoing account's `deposit_on_file` is **not touched**, so no refund
    is raised and no `payments.refunds` row is created;
  · the incoming account is opened with **no deposit collected** — `_open_account`
    writes no `deposit_on_file` and `deposit_on_file` is in `services.REFUSED_FIELDS`
    (BR-CUS-023), so there is no re-collection door to walk through by accident;
  · the outgoing account's `balance` is **not touched** — it is a CACHE
    (BR-CUS-015) and the ledger is the source of truth, and only the ledger
    posting service may write a journal line (hard rule 5);
  · no invoice, invoice line, payment or journal entry is edited or deleted
    anywhere in this module (hard rule 4). Nothing here writes money at all.

`money_statement` therefore SERVES the two figures with their provenance and
two stated absences — never a `0.00`, because BR-CUS-057's interest accrual is
CONFIRMED and NOT BUILT and a zero there carries $150.00 where $153.50 is owed
(❄️ WE-7 / GT-23's frozen pair). What is stored on the transfer row is the
clerk's ELECTION, which is a decision and not a movement.

⚠ **BR-CUS-089 IS NOT ENGAGED HERE, AND THE REASON MATTERS.** *"Money moves
only on a `strong` identity match"* is a rule about a RETURNING customer whose
identity has to be matched. A transfer's customer is not matched — it is READ,
from the `customer_accounts` link the outgoing account already carries
(BR-CUS-054). Nothing in this module computes, accepts or reads a match tier,
and no money moves on any tier, so the rule cannot be evaded here. It is also
inert product-wide: its criteria were ruled on 2026-08-25 (*"Name + date of
birth + one government ID"*, closing OQ-364) and `REQ-03.1` collects no date of
birth — DEF-638(2).

════════════════════════════════════════════════════════════════════════════
4 · WHAT IS NOT BUILT HERE, NAMED
════════════════════════════════════════════════════════════════════════════
· **No API route.** `apps/customers/api.py` is outside this lane's write scope.
  B18 §6.2 asks for `POST /transfers · GET /transfers · GET|PATCH /transfers/{id}
  · POST …/commit` and lists all four as `❌`. REPORTED with the handler shapes.
· **No screen.** S89 is task 7.4, a frontend lane's.
· **No seed.** The five `[shot]` rows of §5.7.6 are task 7.12, a data lane's.
· ⚠ **`No transfer_no` — AMENDED 2026-08-27, CR-039 WAVE D TASK 15. The first
  half is REVERSED by a PO ruling; the second half is still exactly true and is
  now `OQ-426`.** It read: *"B18 §5.7 gives the tab no number series of its own
  and its rows are searched by 'Customer, account #, either address, or request
  #'. Minting a series would be inventing a vocabulary."*

  **What changed.** CR-039's provisioning trace, finding 5: *"Transfer and
  disconnect have tables and no number"*, consequence *"A clerk cannot quote a
  reference; nothing on a bill can point at the job that caused a change"*, and
  wave D task 15 is *"a series and number for transfer"*. **So a transfer DOES
  get a number.** `transfer_no` is a column (migration 0028) and
  `_allocate_transfer_no` runs inside `start_transfer`'s transaction.

  **What did NOT change, and it is the reason the column is NULL on every row
  today.** B18 §5.7 still draws no number — measured again on 2026-08-27:
  §5.7.2's columns are `FROM ACCOUNT · CUSTOMER · FROM → TO · OUT DATE · IN
  DATE · STEP · MONEY · STATE`, §5.7.6's five seeded rows carry account numbers
  on both sides, §5.7.7's five wizard steps carry none, and r10 has no transfer
  record at all. `TRF-01` and `TRF-02.n` in that section are SHOT NAMES for the
  screenshots. So *"minting a series would be inventing a vocabulary"* still
  holds for the FORMAT, which is why this lane built the column and the call
  site and left the catalogue alone: **`OQ-426`**, with four worked options and
  `TRF-26-0001` as the day-one figure under the recommended one.
· **`reserved` is not checked at step 2.** §5.7.4 says the target unit must be
  *"vacant and reserved only"*. `units` has NO occupancy and NO status column —
  occupancy is DERIVED from the active account (BR-MET-036, and metering's own
  models say so in as many words) — so "vacant" is checkable and "reserved" is
  a state this product does not store. The refusal that CAN be made is made;
  the other half is served as a stated absence rather than silently dropped.
· **`BR-CUS-086` DOES NOT EXIST.** B18 §11's NEW-rules table lists it — *"A
  transfer is one job and appears in neither Move-ins nor Move-outs"* — and it
  appears in no `02-business-rules.md` anywhere in this repository (measured
  2026-08-25). It is the third instance of DEF-673's shape, after BR-CUS-089
  and BR-CUS-070. It is therefore NOT cited in this file's Trace header, where
  G02 would correctly fail it, and a register row is REPORTED as owed. The
  BEHAVIOUR is built anyway, from B18 §5.7.3's callout, which is quoted above.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models as django_models
from django.db import transaction
from django.utils import timezone

from apps.customers import identity_match, models, seams
from core import audit as core_audit
from core import errors
from core.dbfields import uuid7_pk
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

ZERO = Decimal("0")


# ═══════════════════════════════════════════════════════════════════════════
# THE ROW — `managed = False`; the DDL is migration 0021's
# ═══════════════════════════════════════════════════════════════════════════
class Transfer(django_models.Model):
    """One transfer job — B18 §5.7's *"one job, not a move-out followed by a
    move-in"*.

    ⚠ **`managed = False` AND THE TABLE IS CREATED BY RAW DDL.** The reason is
    written out in `migrations/0021_cr030_w7_transfers.py`: this model cannot
    live in `apps/customers/models.py` (not in this lane's write scope), Django
    therefore never imports it at startup, and a `CreateModel` would leave
    migration state holding a model the app registry does not have —
    `makemigrations --check` answers that with a `DeleteModel`. Unmanaged keeps
    state and registry in agreement whichever way that line lands later. The
    model and the DDL are held together by an introspection test.

    ⚠ **NO MONEY COLUMN.** See §3 of the module docstring: the two figures are
    computed at read time with their gaps, and a stored `deposit_carried` would
    read as money that moved on a path where nothing moved.
    """

    #: B18 §5.7.2's STATE column: `Scheduled` · `In progress` · `Done`.
    #: `cancelled` is the fourth because a started job that is abandoned must
    #: leave the partial unique index — otherwise the account can never be
    #: transferred again.
    STATE_SCHEDULED = "scheduled"
    STATE_IN_PROGRESS = "in_progress"
    STATE_DONE = "done"
    STATE_CANCELLED = "cancelled"
    STATES = (STATE_SCHEDULED, STATE_IN_PROGRESS, STATE_DONE, STATE_CANCELLED)

    id = uuid7_pk()
    tenant = django_models.ForeignKey(
        "tenancy.Tenant", on_delete=django_models.PROTECT, db_column="tenant_id"
    )
    #: CR-039 wave D task 15 — *"a series and number for transfer"*. The number
    #: a clerk quotes down a phone, allocated by `_allocate_transfer_no` INSIDE
    #: `start_transfer`'s own transaction so a job never exists unnumbered.
    #:
    #: ⛔ **THIS NOTE SAID *"NULL ON EVERY ROW TODAY … `OQ-426`"* UNTIL
    #: 2026-09-20 AND IT HAD BEEN FALSE SINCE 2026-08-27 — `DEF-CUS-5945`.**
    #: `OQ-426` was CLOSED that day by the PO, verbatim: *"Transfer TRF-26-0001
    #: … follow same logic that we are following for other numbers we have did
    #: in settings"*. The catalogue carries `TRF-{YY}-{0000}` as the `transfer`
    #: series' seeded default, every provisioned tenant holds the row, and
    #: `test_cr039_wd_transfer_and_case_numbers` asserts a new tenant's first
    #: transfer renders `TRF-26-0001`. **A clerk can quote a transfer's
    #: reference today.**
    #:
    #: ⚠ **THE COST OF THE STALENESS WAS NOT IN THIS FILE, WHICH IS WHY IT IS
    #: WORTH THE SPACE.** The Accounts blueprint's transfer-record page draws a
    #: dashed panel reading *"No transfer numbering series exists, so this sale
    #: carries no reference in the database today"* — a drawing written from
    #: this comment, which then told a screen lane to build the absence instead
    #: of the number. CLAUDE.md's own warning, exactly: a closed question's BODY
    #: goes on describing the open world, and the body is what a lane reads.
    #:
    #: NULL is still possible and still a real answer: a tenant provisioned
    #: before the series was seeded has no row, and `_allocate_transfer_no`
    #: reports rather than raises. It is the uncommon case now, not the only one.
    transfer_no = django_models.TextField(null=True, blank=True)
    from_account = django_models.ForeignKey(
        "customers.Account",
        on_delete=django_models.PROTECT,
        db_column="from_account_id",
        related_name="+",
    )
    #: NULL until step 5 commits. B18 §5.7.2: the FROM ACCOUNT cell reads
    #: `→ —` before the new number exists (TC-TRF-2) — a dash, never a blank.
    to_account = django_models.ForeignKey(
        "customers.Account",
        on_delete=django_models.PROTECT,
        db_column="to_account_id",
        related_name="+",
        null=True,
    )
    #: The SELLER's customer, read from `customer_accounts` (BR-CUS-054) —
    #: never matched.
    #:
    #: ⊕ **NULLABLE SINCE migration 0068 — `BR-CUS-1081` T1, decided 2026-09-23
    #: (`DEF-CUS-6387`).** An account with no customer linked used to be
    #: REFUSED at the commit, five steps after it was picked (*"A-11512 is not
    #: linked to a customer. Link it to one first."*). The PO moved the customer
    #: search to the BUYER, and the seller-side answer was decided rather than
    #: asked (law 13): **the sale goes ahead and the seller is recorded by the
    #: name on the account** — `seller_name` below. NULL here means exactly
    #: that: nobody on file, and the name is what the account carried.
    customer = django_models.ForeignKey(
        "customers.Customer",
        on_delete=django_models.PROTECT,
        db_column="customer_id",
        null=True,
    )
    #: ⊕ **migration 0068 — WHO SOLD IT, AS THE ACCOUNT NAMED THEM.** Written on
    #: EVERY sale at `start_transfer` (the account's primary contact name,
    #: falling back to the linked customer's), so a record page names the
    #: seller whether or not a customer row existed — and names them as they
    #: stood on the day, which a later rename of the customer cannot rewrite.
    seller_name = django_models.TextField(null=True, blank=True)
    #: ⊕ **WHO BOUGHT IT — migration 0060, `BR-CUS-1030`.** PO ruling
    #: 2026-09-20, verbatim: *"we cannot override customer id - seller and
    #: buyer cstmer id are unique those does not change"*.
    #:
    #: ⚠ **`customer` ABOVE IS THE SELLER, BEFORE AND AFTER COMMIT.**
    #: `reassign_account` used to overwrite it with the buyer, which destroyed
    #: the transfer row's only memory of who sold the property — the seller
    #: then survived in `audit_log` alone, which is pruned. The overwrite is
    #: gone, so this table's meaning no longer changes underneath a reader
    #: half way through a job, and `reassign_account`'s own
    #: `seller = transfer.customer` is now true at every moment rather than
    #: only before its own write.
    #:
    #: **NULL before commit, and NULL on every sale committed before 0060** —
    #: those buyers are recoverable from the account's live link, but nothing
    #: back-fills this column, because a guess about a row a regulator may
    #: read is worse than an honest absence.
    #:
    #: No foreign key: this table is `managed = False`, so an FK would be
    #: hand-written DDL the model cannot express — the same call `to_unit_id`
    #: and `request_id` already made, for the same reason.
    buyer_customer_id = django_models.UUIDField(null=True, blank=True)
    #: metering's unit id, with NO foreign key — B2 §2's reviewed cross-module
    #: interface set does not contain this edge (migration 0021 explains).
    to_unit_id = django_models.UUIDField(null=True)
    #: `CR-094-BRC01` — **the service request this transfer was raised from**,
    #: `BR-CUS-080`'s CHILD half, which `link_child`'s docstring has said was
    #: owed since 2026-08-24 (*"the child's `origin_service_request_id` lands
    #: with the child table"* — this table landed without it).
    #:
    #: NULL on every transfer a clerk starts from the account page, which is the
    #: ordinary case and is not an absence to report: `connections.request_id`
    #: says the same of builds, in the same words.
    #:
    #: ⚠ NO FOREIGN KEY, the same call `to_unit_id` above already made, and
    #: migration 0048's docstring gives both reasons — the short one is that the
    #: link is EVIDENCE rather than integrity, and a `PROTECT` edge would make a
    #: request undeletable because a job once pointed at it.
    request_id = django_models.UUIDField(null=True, blank=True)
    out_date = django_models.DateField(null=True)
    in_date = django_models.DateField(null=True)
    step = django_models.SmallIntegerField(default=1)
    state = django_models.TextField(default=STATE_SCHEDULED)
    #: The clerk's step-4 ELECTION. Not a money movement — see §3.
    deposit_carry_elected = django_models.BooleanField(null=True)
    arrears_follow_elected = django_models.BooleanField(null=True)
    money_decided_at = django_models.DateTimeField(null=True)
    #: THE instant both halves became true. One column, written once, inside
    #: the one transaction — see §1.
    committed_at = django_models.DateTimeField(null=True)
    #: `DEF-CUS-9692` (customers/0079) — WHO committed it, beside WHEN. A user
    #: id with no foreign key, like every id on this unmanaged table; NULL on a
    #: sale committed before the column, which the record states as *not
    #: stored* rather than reading the pruned audit log.
    committed_by_id = django_models.UUIDField(null=True, db_column="committed_by")
    cancelled_at = django_models.DateTimeField(null=True)
    #: BR-TEN-057 — the sample-data tag on the owning row, the posture every
    #: other customers table uses so BR-TEN-061 can delete on one predicate.
    is_sample = django_models.BooleanField(default=False)
    created_at = django_models.DateTimeField(default=timezone.now)
    updated_at = django_models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = "transfers"


#: B18 §5.7.4's five steps, verbatim. The tuple is the vocabulary the STEP
#: column counts against (`3 of 5`), and it is five so that a sixth cannot be
#: added without somebody reading this table.
#: ⛔ **REWRITTEN 2026-09-01 — `BR-CUS-1030`. THE JOB CHANGED, SO THE STEPS DID.**
#: They used to read *"Find the new unit (vacant and reserved only)"* and
#: *"Dates — out, in, and whether they are the same day"*, which are the steps of
#: a customer MOVING. **PO ruling:** *"dont create new account - we reassing that
#: account - bascailly I have sold my property - so account get transfer to new
#: person or business; if I move to new location then it is new Service
#: request"*. A sale has no new unit and no second date: the account stays where
#: it is and changes hands on one day.
STEPS: tuple[tuple[int, str], ...] = (
    (1, "Find the account and confirm who is selling"),
    (2, "Who is buying it — name, person or company, and one identifier"),
    (3, "The date of sale"),
    (4, "What the buyer takes on — the balance and the deposit as they stand"),
    (5, "Review — one account, one new owner, one commit"),
)
STEP_COUNT = len(STEPS)


# ═══════════════════════════════════════════════════════════════════════════
# THE STATED ABSENCES — each names the rule it belongs to, never a zero
# ═══════════════════════════════════════════════════════════════════════════
# ⛔ **THREE OF THESE ARE GONE, AND THEY WERE DELETED RATHER THAN LEFT
# UNUSED (2026-09-01, `BR-CUS-1030` + the debt ruling).** A stated absence whose
# question has been answered is a lie with a rule id on it — hard-won law 1 —
# and it is a worse one than a missing comment, because a screen renders it to a
# clerk as *"nobody has decided this yet"*.
#
#   · `transfer_money_rule_does_not_exist` — **ANSWERED.** PO 2026-09-01: *"money
#     follow property - new owner boutght everything property + debt also"*.
#     `OQ-1252`, raised and closed the same day.
#   · `deposit_carry_has_no_transfer_path` — **DISSOLVED.** There is no second
#     account for a deposit to move to. The account stays; the deposit stays on
#     it; nothing is refunded and nothing is re-collected, and now that is
#     structural rather than a promise.
#   · `arrears_follow_has_no_posting_path` — **DISSOLVED, AND THIS IS THE ONE
#     WORTH READING.** It named a real hazard: posting a debt from one account
#     to another needs the ledger, and only the ledger posting service writes a
#     journal line (hard rule 5). **Under the reassignment there is no posting
#     to make.** The balance never moves because the thing it sits on never
#     moves. The two rulings were given independently and they happen to make
#     each other cheap.
#   · `unit_reserved_state_has_no_column` — **IRRELEVANT.** A sale changes no
#     unit, so there is no target unit whose reserved state anyone could ask
#     about.
#
# **The two that SURVIVE are the two that are still true**, and they are about
# READING a figure rather than about moving one.
GAP_DEPOSIT_INTEREST = "deposit_interest_not_readable"
GAP_BALANCE_IS_A_CACHE = "balance_is_the_cached_ar_figure"
#: ⊕ **REPLACED 2026-09-23 — `BR-CUS-1081` T2 (`DEF-CUS-6394`).** It read
#: `premises_owner_record_not_updated` and was stated on EVERY sale. The PO
#: ruled the owner moves for a MASTER account and stays for a regular one, so
#: the only true absence left is a master sale metering could not move.
GAP_PREMISES_OWNER_NOT_MOVED = "premises_owner_not_moved"

DEPOSIT_INTEREST_NOT_READABLE: dict[str, Any] = {
    "code": GAP_DEPOSIT_INTEREST,
    "br_ref": "BR-CUS-057",
    "detail": (
        "BR-CUS-057's deposit-interest accrual is CONFIRMED and NOT BUILT — "
        "`apps.customers.selectors.deposit_interest_accrued` is published by nothing "
        "(US-CUS-023 §7). WE-7/GT-23's frozen pair is $150.00 principal + $3.50 interest = "
        "$153.50, so reading the interest as 0.00 would state $150.00 where $153.50 is held. "
        "The deposit stays on the account either way — a sale moves no money — but the "
        "FIGURE the buyer is shown is short by the interest term until that engine exists."
    ),
}

BALANCE_IS_A_CACHE: dict[str, Any] = {
    "code": GAP_BALANCE_IS_A_CACHE,
    "br_ref": "BR-CUS-015",
    "detail": (
        "`accounts.balance` is the CACHED AR figure and the ledger is the source of truth "
        "(B2's own column comment). The balance shown as following the property is that "
        "cache, read and not recomputed — the same figure the Accounts tab shows. It is "
        "named so no screen prints it as a ledger-verified number."
    ),
}

PREMISES_OWNER_NOT_MOVED: dict[str, Any] = {
    "code": GAP_PREMISES_OWNER_NOT_MOVED,
    "br_ref": "BR-CUS-1081 · BR-MET-151 · B1 (no cross-module write)",
    "detail": (
        "A master account changed hands and the property's owner record could not be "
        "moved to the buyer. The owner record is metering's typed party and carries a "
        "category; where the premises has no typed owner there is no category to carry "
        "and none may be guessed from a name (BR-MET-151 clause 3). Set the owner on "
        "Premises \u2192 Owner matching."
    ),
}


# ── ⊕ 2026-09-20 · `BR-CUS-1081` — THREE MORE, AND EACH IS A DIFFERENT SHAPE ──
#
# ⚠ **A STATED ABSENCE IS NOT A TODO.** Each of these is a fact the product
# genuinely does not record, said out loud on the response so a clerk is never
# left inferring it from silence — which is the whole posture the three above
# already take, and is why they are here rather than in a comment.
GAP_CONTACT_NOT_WRITTEN = "account_had_no_contact_row"
#: ⛔ **RETIRED 2026-09-23 — THREE CODES THE PO'S RULINGS ANSWERED.**
#:   · `mailing_address_still_the_sellers` and `contact_details_still_the_sellers`
#:     — T3 (`DEF-CUS-6393`): the seller's email, phone, mailing address and
#:     autopay are REMOVED at the sale, so neither is true any more.
#:   · `co_applicant_captured_and_not_stored` — T4 (`DEF-CUS-6391`, `OQ-CUS-12514`
#:     closed): a co-applicant is stored as the account's second contact.
#: Deleted rather than left unused: a stated absence whose question has been
#: answered is a lie with a rule id on it (hard-won law 1).

CONTACT_NOT_WRITTEN: dict[str, Any] = {
    "code": GAP_CONTACT_NOT_WRITTEN,
    "br_ref": "BR-CUS-045",
    "detail": (
        "The buyer's email, telephone number and date of birth could not be written to the "
        "account because the account carries no contact row at all. The sale went through: "
        "a buyer must not lose a property because a row nobody ever created is missing. "
        "Add the contact on the account and the details are the buyer's."
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# REFUSALS
# ═══════════════════════════════════════════════════════════════════════════
REFUSAL_NOT_AN_OCCUPANT = "from_account_is_not_an_occupant"
# ⛔ **`REFUSAL_NO_CUSTOMER` (`from_account_has_no_customer_entity`) IS RETIRED
# 2026-09-23 — `BR-CUS-1081` T1 (`DEF-CUS-6387`).** An account with nobody
# linked is SOLD, and the seller is recorded by the name on the account. The
# constant is deleted rather than left unused: an unused refusal constant reads
# as a check that exists. See `_seller_of`.
REFUSAL_ALREADY_COMMITTED = "transfer_already_committed"
REFUSAL_ALREADY_CANCELLED = "transfer_already_cancelled"
REFUSAL_STEP_INCOMPLETE = "transfer_step_incomplete"
#: ⛔ **CR-058 W4 · `BR-CUS-1030` — THE BUYER MUST BE IDENTIFIABLE.**
#: PO ruling 2026-09-01: *"Without identifier we cannot create Customer ID or
#: master account ot regular account"*. A reassignment CREATES no account, so
#: the letter of that rule does not reach it — but its whole point is that **no
#: account may exist with nobody identifiable behind it**, and handing a live
#: ledger to an unidentified party produces exactly that. A lane judgment,
#: recorded in the decision log of 2026-09-01 rather than re-asked (law 13): a
#: refusal is recoverable in thirty seconds by asking for a phone number, and a
#: wrong reassignment is a live account owned by nobody.
REFUSAL_BUYER_NOT_IDENTIFIED = "buyer_has_no_identifier"
#: The buyer is already this account's customer — nothing to reassign, and
#: rewriting the link to itself would write an audit row about a non-event.
REFUSAL_BUYER_IS_THE_SELLER = "buyer_is_already_this_accounts_customer"

# ⛔ **RETIRED 2026-09-01 — `BR-CUS-1030`.** `REFUSAL_TARGET_OCCUPIED`,
# `REFUSAL_SAME_UNIT` and `REFUSAL_IN_BEFORE_OUT` were the refusals of a job
# that opened an account at a NEW unit on a SECOND date. **A sale changes no
# unit and has one date**, so there is no target to be occupied, no same-unit
# case, and no pair of dates that can be out of order. They are DELETED rather
# than left unused: an unused refusal constant reads as a check that exists.


# ═══════════════════════════════════════════════════════════════════════════
# WHAT THE BUYER CARRIES — `BR-CUS-1081`, PO ruling 2026-09-20
# ═══════════════════════════════════════════════════════════════════════════
#
# PO, having walked the wizard in the live product, verbatim: *"step 2 dont
# allow to take kYC documents - DOB, all detaisl we need to create account -
# Similar to Move in request we will need all details for account"*. And, when
# told a backend lane would be needed: *"we have it - we have created it for
# service request move in - use it"*.
#
# **THEY ARE RIGHT ABOUT THE REUSE AND THAT IS WHY THIS IS A DERIVATION AND NOT
# A LIST.** `service_request_service.CAPTURE_FIELDS` is what a clerk may put on
# an application, and a buyer at a counter is the same clerk answering the same
# questions about the same kind of party. A second hand-typed list would drift
# the first time one of them gained a field — which is hard-won law 2's shape
# for a VOCABULARY rather than for a control, and `SignupWizard.tsx`'s
# hand-typed service list is the standing example of what it costs.
#
# ⚠ **SO THE NAMES BELOW ARE CHECKED AGAINST THAT SET, LOUDLY, AT THE DOOR.**
# `_capture_vocabulary()` raises if any of them has left `CAPTURE_FIELDS`, so a
# rename there stops every transfer in the product rather than silently
# narrowing what a buyer carries. An INTERSECTION would have been the obvious
# spelling and it is the wrong one: it shrinks silently, and a capture set that
# quietly stops carrying a date of birth is a match that quietly stops being
# strong (law 7 — ask what would make this check pass wrongly).
#
# ⚠ **THE CHECK IS AT FIRST USE AND NOT AT IMPORT, AND THAT IS FORCED RATHER
# THAN PREFERRED.** `apps/customers/models.py` imports THIS module at the foot
# of its own body (to register the unmanaged `Transfer`), so a module-level
# `import service_request_service` here would re-enter `models` while `models`
# is still executing. The import is therefore inside the function, which is the
# posture `reassign_account` already takes for `selectors` and `services`.
#
# ⚠ **IT IS A SUBSET, AND WHAT IS LEFT OUT IS LEFT OUT FOR ONE REASON.** The
# fields excluded are about a PROPERTY or about an APPLICATION, and a sale has
# neither to ask about: the property is the account's own unit and never moves
# (`BR-CUS-1030`), and the application is this wizard. `address_as_given`,
# `address_unit_as_given`, `billing_address_same`, `billing_address_as_given`,
# `plot_or_parcel`, `what_is_being_built`, `property_type`, `units_on_property`,
# `channel`, `problem_kind`, `what_they_said`, `requested_start`,
# `eligibility_claimed`, `eligibility_note` and the three `fee_*` columns are
# every one of them a question about a job being applied for.
#
# ⛔ **AND `picked_premises_id` / `picked_unit_id` ARE EXCLUDED FOR A SECOND,
# STRONGER REASON — `PICK_FIELDS`' own note.** They name a row in the premises
# register, and a transfer already knows its premises: it is the one the account
# sits on. Accepting a pick here would let a caller point a sale at a building
# it is not about.
#
# ✅ **THE CLERK'S SET, NOT THE GUEST'S.** `PORTAL_CAPTURE_FIELDS` deliberately
# omits `ssn`, `date_of_birth` and `drivers_licence` — *"a guest on the public
# form is refused by name … picking off the premises register is a clerk's act
# at a counter"*. **A transfer buyer is captured by a CLERK**: `set_new_customer`
# and `reassign_account` are both `@require_role(SYSTEM_ADMIN, BILLING_CLERK)`
# and there is no guest door onto a sale anywhere in this product. So the
# identity three are IN, and the portal set is the wrong parent for this.
BUYER_CAPTURE_NAMES: tuple[str, ...] = (
    # WHO — the two the wizard has always sent, under the capture set's own
    # spelling. `display_name` and `kind` remain accepted as the shipped
    # aliases; see `_BUYER_ALIASES`.
    "applicant_kind",
    "applicant_name",
    # ⊕ NEW ON 2026-09-20 — HOW TO REACH THEM. The wizard has been putting an
    # email on the wire since the step was built and `_validated_buyer` dropped
    # it on the floor (`DEF-CUS-5941`).
    "applicant_email",
    "applicant_phone",
    "preferred_language",
    # ⊕ NEW — THE THREE THAT DECIDE WHETHER A MATCH CAN EVER BE STRONG.
    # `BR-CUS-089`'s criteria are **name + date of birth + one government
    # identifier**, so a buyer captured without a date of birth cannot reach
    # `strong` however much else is known — and `discounts.carry_forward_offer`
    # refuses on anything weaker, so **$0.00** of a seller's deposit can follow
    # a buyer who is in fact the same person. `ssn` and `drivers_licence` were
    # already reachable through `identity`; `date_of_birth` was reachable
    # nowhere at all.
    "ssn",
    "date_of_birth",
    "drivers_licence",
    # ⊕ NEW — THE SECOND PERSON ON THE ACCOUNT. A couple buying a house is the
    # ordinary case and the request form has asked for all three since it was
    # built.
    "co_applicant_name",
    "co_applicant_email",
    "co_applicant_phone",
)

#: The subset of `CAPTURE_FIELDS` a transfer's buyer carries. The TUPLE above is
#: the declaration; this is it as a set, and `_capture_vocabulary()` is the one
#: that proves the two agree with the capture set they are taken from.
BUYER_CAPTURE_FIELDS: frozenset[str] = frozenset(BUYER_CAPTURE_NAMES)


def _capture_vocabulary() -> frozenset[str]:
    """`BUYER_CAPTURE_FIELDS`, **proved against `CAPTURE_FIELDS` before use.**

    ⚠ **IT RAISES RATHER THAN NARROWING.** A name that has left the capture set
    is a field this door would go on accepting and no other door would — two
    vocabularies for one fact, which is precisely what the reuse exists to
    prevent. `RuntimeError` is deliberate: it is not a `ValidationError` a clerk
    could be shown, because it is not about their typing.

    Cheap enough to run per call — two set operations over eleven names — so it
    is NOT cached. A cache here would answer from the first import for the life
    of the process, which is the shape that survives a hot reload and lies.
    """
    from apps.customers import service_request_service as sr

    strayed = sorted(BUYER_CAPTURE_FIELDS - sr.CAPTURE_FIELDS)
    if strayed:
        raise RuntimeError(
            "transfers.BUYER_CAPTURE_NAMES has drifted from "
            "service_request_service.CAPTURE_FIELDS: "
            f"{', '.join(strayed)} is no longer captured there. The buyer's set "
            "is REUSED from the request's on the PO's ruling of 2026-09-20; fix "
            "the name or take it out of BUYER_CAPTURE_NAMES deliberately."
        )
    return BUYER_CAPTURE_FIELDS

#: The two spellings the shipped wizard sends, mapped to the capture set's own.
#: **BOTH ARE ACCEPTED AND NEITHER IS RENAMED**, which is `ALIASED_FIELDS`'
#: posture one table over and is here for the same reason: four sibling lanes
#: are live on `TransferWizard.tsx` today, and a door that stopped taking
#: `display_name` would break a screen in the middle of their work for a
#: cosmetic gain. The capture spelling is CANONICAL — it is what a reader
#: greps for and what the contract publishes.
_BUYER_ALIASES: dict[str, str] = {
    "display_name": "applicant_name",
    "name": "applicant_name",
    "kind": "applicant_kind",
    "email": "applicant_email",
    "phone": "applicant_phone",
    "dob": "date_of_birth",
    "driving_licence": "drivers_licence",
}

#: `customers.addresses` `kind='mailing'` — **CLAUDE.md hard rule 8's FIRST
#: NAMED EXCEPTION**, and the only lawful second address in this product:
#: *"where the BILL goes, which for a landlord is another building"*.
#:
#: ⛔ **NO ADDRESS COLUMN IS DECLARED ANYWHERE FOR THIS, AND NONE MAY BE.** The
#: buyer's mailing address is written onto the ACCOUNT at commit through
#: `services.update_account_mailing_address` — the door that already exists,
#: already refuses `kind` from the caller by name, and already treats an empty
#: `line1` as *remove it and post to the service address*. `G85` fails a fourth
#: home and this path gives it nothing to find.
#:
#: ⚠ **`kind` IS NOT IN THIS SET AND MUST NOT BE.** `kind='service'` is RETIRED
#: (`BR-MET-1161`) and the door below writes `mailing` and only `mailing`, so
#: the retired value cannot arrive here even as a typo.
#: ⚠ **`line2` AND `country` ARE REAL COLUMNS AND ARE NOT HERE, WHICH IS A GAP
#: RATHER THAN A CHOICE — `DEF-CUS-5942`.** `customers 0039` added both
#: (`DEF-2847`) because `BR-NOT-029`'s print manifest was emitting them blank on
#: every bill, and `services.ADDRESS_FIELDS` was never widened to match, so the
#: only write door for a mailing address cannot set either. This set is DERIVED
#: from that door's vocabulary rather than typed, so it carries the gap honestly
#: and gains both the day the door does.
def _mailing_vocabulary() -> frozenset[str]:
    """What a buyer's mailing address may carry — **the write door's own set.**

    `services.ADDRESS_FIELDS` minus `kind`, which is exactly what
    `update_account_mailing_address` accepts, taken from it rather than copied
    so the two cannot disagree about a column. Imported inside the function for
    `_capture_vocabulary`'s reason.
    """
    from apps.customers import services

    return frozenset(services.ADDRESS_FIELDS) - {"kind"}


# ═══════════════════════════════════════════════════════════════════════════
# MONEY — hard rule 2: 4 dp stored, 2 dp displayed, never a float
# ═══════════════════════════════════════════════════════════════════════════
def _money(value: Any, what: str) -> Decimal:
    """A money figure or a refusal — NEVER a float and never a silent zero."""
    if isinstance(value, Decimal):
        return value
    raise errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="BR-CUS-015",
        message_key="customers.transfer.money_not_a_decimal",
        params={"what": what, "type": type(value).__name__},
    )


def _stored(amount: Decimal) -> str:
    """Hard rule 2: money is STORED to four decimals."""
    return f"{amount.quantize(Decimal('0.0001')):f}"


def _display(amount: Decimal) -> str:
    """Hard rule 2: money DISPLAYS at two."""
    return f"{amount.quantize(Decimal('0.01')):f}"


def _pair(amount: Decimal | None) -> dict[str, str | None]:
    if amount is None:
        return {"stored": None, "display": None}
    return {"stored": _stored(amount), "display": _display(amount)}


# ═══════════════════════════════════════════════════════════════════════════
# THE NUMBER (CR-039 wave D task 15) — allocated by name, never invented
# ═══════════════════════════════════════════════════════════════════════════
#: The catalogue KEY, not a prefix. Naming the key is not the thing `OQ-426`
#: asks about: what a clerk reads out is the seeded FORMAT, and that is the
#: catalogue's to hold. `apps/metering/connections.py` did exactly this with
#: `CONNECTION_SERIES = "connection"` for the day its own catalogue row was
#: missing, and the key it chose then is the key the catalogue carries now.
TRANSFER_SERIES = "transfer"

#: The stated absence. Same code string `apps/metering/services._allocate_number`
#: has always used, so a reader who has met one has met both.
NUMBERING_SERIES_MISSING = "numbering_series_missing"

TRANSFER_NUMBER_UNAVAILABLE: dict[str, Any] = {
    "code": NUMBERING_SERIES_MISSING,
    "series": TRANSFER_SERIES,
    # ⚠ **`OQ-426` IS A CLOSED QUESTION AND THIS POINTER STAYS, DELIBERATELY —
    # A DRAFT OF `DEF-CUS-5945` SET IT TO `None` AND WENT RED.** The question
    # closed on 2026-08-27 and its register row is where the RULING lives, so a
    # reader following this pointer arrives at the answer rather than at a
    # pending decision. `test_a_transfer_with_no_series_reports_the_absence_and_
    # never_invents_a_number` asserts the key by value, and the serialized
    # absence reaches a screen; changing it would be a contract change to fix a
    # prose problem. **What `DEF-CUS-5945` corrected is the three PROSE claims
    # that said a transfer has no number at all — this report is about a tenant
    # provisioned before the series was seeded, which is a real and rarer case.**
    "open_question": "OQ-426",
    "detail": (
        "This transfer has no reference number yet. A number series for transfers has not "
        "been set up, so nothing has been issued — the job is complete and only its "
        "reference is missing."
    ),
}


def _allocate_transfer_no() -> tuple[str | None, dict[str, Any] | None]:
    """BR-TEN-035 allocation for a transfer. **A missing series is REPORTED,
    never faked** — `apps/metering/services._allocate_number`'s own words.

    ⚠ **CALL THIS INSIDE THE CREATING TRANSACTION.** BR-TEN-035 allocates a
    number inside the issuing transaction so a rolled-back job leaves a gap
    rather than a reused number, and `apps/customers/services._allocate_account_no`
    is the precedent this follows: the allocation happens in the same
    `atomic()` block as the `objects.create(...)`, so a transfer never exists
    unnumbered even for the width of a transaction.

    ⛔ **THIS SAID *"IT RETURNS `(None, reason)` ON EVERY TENANT TODAY —
    `OQ-426`"* UNTIL 2026-09-20 AND IT HAD BEEN FALSE FOR TWENTY-FOUR DAYS**
    (`DEF-CUS-5945`). The `transfer` series is seeded in every provisioned
    tenant at `TRF-{YY}-{0000}` and this returns a real number; `OQ-426` closed
    on 2026-08-27. Returning a reason rather than raising is deliberate and is
    the difference
    between a missing reference and a missing service: a clerk who cannot
    start a transfer because nobody has configured numbering has been stopped
    by our gap, not theirs.
    """
    from core import numbering as core_numbering

    try:
        return core_numbering.next_number(TRANSFER_SERIES, seams.tenant_today()), None
    except core_numbering.NumberingError:
        return None, dict(TRANSFER_NUMBER_UNAVAILABLE)


def _tenant_id() -> Any:
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _audit(actor: Any, action: str, entity_id: Any, *, after: dict[str, Any]) -> None:
    """CLAUDE.md rule 7 — every money action writes `audit_log`.

    A carried deposit and a following arrear are money actions even when the
    product cannot move either: the DECISION that $153.50 and $542.10 stayed
    where they were is the only trace this event leaves, and B18 §5.7.1's KPI
    strip counts `DEPOSITS CARRYING` and `ARREARS FOLLOWING` off exactly it.
    Same posture as `discounts._audit` and `move_out_settlement._audit`.
    """
    core_audit.write_row(
        action=action,
        entity_type="transfer",
        entity_id=entity_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        before=None,
        after=after,
    )


# ═══════════════════════════════════════════════════════════════════════════
# READS
# ═══════════════════════════════════════════════════════════════════════════
def _transfer_or_refuse(transfer_id: Any, *, lock: bool = False) -> Transfer:
    """404-never-403 for an id belonging to another tenant (HR-1)."""
    rows = Transfer.objects.filter(tenant_id=_tenant_id(), pk=transfer_id)
    if lock:
        rows = rows.select_for_update()
    row = rows.first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _account_or_refuse(account_id: Any) -> models.Account:
    from apps.customers import selectors

    return selectors.account_or_404(account_id)


def _seller_of(account: models.Account) -> models.Customer | None:
    """The account's current customer from the `customer_accounts` link
    (`BR-CUS-054`), or `None` when nobody is linked.

    NOT a name match. B18 §2.5 records name matching as the failure the customer
    entity exists to end.

    ⛔ **IT USED TO REFUSE, AND THE REFUSAL IS RETIRED — `BR-CUS-1081` T1,
    DECIDED 2026-09-23 (`DEF-CUS-6387`).** An account with no customer linked
    was refused with *"A-11512 is not linked to a customer. Link it to one
    first."* — and the refusal reached the clerk at STEP 5, after the buyer, the
    date and the money had all been entered, on the PO's own sample account. The
    `CR-058` task-14 judgment that kept it (no account may exist with nobody
    identifiable behind it) is about the account's NEXT holder, and the sale
    itself guarantees that: the BUYER must be identified (`_validated_buyer`)
    and becomes the customer of record. What the old refusal protected was the
    seller's identity, which is a fact about the past.

    **The PO moved the customer search to the buyer** (*"no we have to search
    custoemr id for buyer hence on step 2"*), so nothing in the wizard could any
    longer fix an unlinked seller before the commit — refusing would leave this
    sale impossible to complete at all. **So the sale goes ahead and the seller
    is recorded by the name on the account** (`_seller_name_of`, stored in
    `transfers.seller_name`); this is the posture this file already takes one
    row over for a missing contact — *"a buyer must not lose a property because
    a row nobody ever created is missing"*. Decision log 2026-09-23.
    """
    # ⛔ **`live()` AND NOT `objects` — `DEF-CUS-6046`, MEASURED 2026-09-20.**
    # `customers/0060` made a sale END the seller's link instead of deleting
    # it, so an account that has changed hands holds TWO rows: the old owner's,
    # ended, created FIRST, and the new owner's, live. Reading every row by
    # `created_at` would name the FIRST seller on the second sale of a property.
    link = (
        models.CustomerAccount.live(tenant_id=account.tenant_id, account=account)
        .select_related("customer")
        .order_by("created_at", "id")
        .first()
    )
    return link.customer if link is not None else None


def _seller_name_of(account: models.Account, seller: models.Customer | None) -> str | None:
    """**The name on the account** — who a sale records as its seller.

    The account's primary contact first, because that is the name every screen
    in this product prints for an account (`primary_contact_name`) and the name
    the clerk saw on step 1; the linked customer's display name only where the
    account has no contact row. `None` only where the account carries neither,
    which the record page states as an absence rather than a blank.
    """
    row = (
        models.Contact.objects.filter(
            tenant_id=account.tenant_id, account=account, deleted_at__isnull=True
        )
        .order_by("-is_primary", "created_at", "id")
        .values_list("full_name", flat=True)
        .first()
    )
    name = (row or "").strip() or (seller.display_name.strip() if seller is not None else "")
    return name[:200] or None


def _deposit_interest(account: models.Account, as_of: date | None = None) -> Decimal | None:
    """BR-CUS-057's accrual, or None. NEVER computed here.

    An account holding NO deposit answers ZERO without consulting the engine —
    there is nothing to accrue on. This is `discounts._deposit_interest`'s and
    `move_out_settlement._deposit_interest`'s posture, deliberately identical:
    three modules disagreeing about when a deposit may be read is how a customer
    gets three different answers to one question.

    ⛔ **`as_of` IS PASSED, AND IT WAS NOT FOR TWELVE DAYS — `DEF-CUS-5940`.**
    The seam's published signature became `(account_id, as_of)` on **2026-09-08**
    (`c7485bebc`, `CR-075`'s remaining waves), which is the commit that gave
    `selectors.deposit_interest_accrued` a body at all. Before it, `resolve`
    answered `None` and this line never ran; after it, **every transfer of an
    account holding a deposit raised**::

        TypeError: deposit_interest_accrued() missing 1 required positional
        argument: 'as_of'

    That is `POST /transfers/commit` and `GET /transfers/{id}/money` — **a
    property with a deposit on it could not be sold at all**, for twelve days,
    on a path with fourteen tests over it. `move_out_settlement` was moved in
    the same commit and this was not, which is why the failure is a *widening
    that reached one of two call sites* rather than a bug in either.

    ⚠ **THE DATE IS THE TENANT'S TODAY AND IT IS CHOSEN HERE RATHER THAN
    FORWARDED, WHICH IS A DIFFERENCE FROM `move_out_settlement` WORTH NAMING.**
    That module has an `as_of` of its own and forwards it, `None` included,
    because *"the rule belongs to the engine"*. A transfer has no such
    parameter: step 4 asks for *"the balance and the deposit **as they
    stand**"*, which is today, and `_allocate_transfer_no` already reads
    `seams.tenant_today()` for the same reason. Forwarding `None` instead would
    be worse than raising — the engine answers `None` for an unstated day, so a
    real accrual would come back as `deposit_interest_not_readable` and a clerk
    would be told the figure is unavailable when it is merely unasked for.
    """
    if _money(account.deposit_on_file, "the deposit on file") == ZERO:
        return ZERO
    read = seams.resolve("customers", "deposit_interest_accrued", kind="selectors")
    if read is None:
        return None
    answered = read(account.id, as_of or seams.tenant_today())
    return None if answered is None else _money(answered, "the accrued deposit interest")


@dataclass(frozen=True)
class MoneyStatement:
    """B18 §5.7.2's MONEY cell — up to two sentences, and neither is a movement.

    `deposit_carried is None` means BR-CUS-057 could not answer, NOT that it is
    zero. `arrear_following` is the cached AR figure, named as such.
    """

    currency: str
    deposit_principal: Decimal
    deposit_interest: Decimal | None
    arrear: Decimal

    @property
    def deposit_carried(self) -> Decimal | None:
        if self.deposit_interest is None:
            return None
        return self.deposit_principal + self.deposit_interest

    @property
    def carries_a_deposit(self) -> bool:
        """True when there is a deposit position at all — independent of whether
        its FIGURE can be read. Collapsing 'carries, figure unreadable' into
        'carries nothing' would hide the customer's own money behind an engine
        somebody else has to build."""
        return self.deposit_principal > ZERO

    @property
    def arrear_follows(self) -> bool:
        return self.arrear > ZERO

    @property
    def gaps(self) -> list[str]:
        """What CANNOT be answered here, named.

        ⛔ **THREE ENTRIES LEFT THIS LIST ON 2026-09-01 AND THE LIST IS SHORTER
        BY DESIGN.** It used to open with `transfer_money_rule_does_not_exist`
        UNCONDITIONALLY, so every transfer ever read said *"nobody has ruled
        what happens to this money"*. **Somebody has**: the debt follows the
        property, and the account it sits on does not move. What survives is
        about reading a figure, not about moving one.
        """
        out: list[str] = []
        if self.carries_a_deposit and self.deposit_interest is None:
            out.append(GAP_DEPOSIT_INTEREST)
        if self.arrear_follows:
            out.append(GAP_BALANCE_IS_A_CACHE)
        return sorted(set(out))

    @property
    def sentences(self) -> list[str]:
        """The stacked cell, in B18 §5.7.2's own words. A sentence is emitted
        only when its figure is readable — a `deposit carried $0.00` on an
        unreadable interest term would be a lie in the accent colour."""
        out: list[str] = []
        carried = self.deposit_carried
        if self.carries_a_deposit and carried is not None:
            # ⚠ **THE WORD CHANGED WITH THE ACT.** *"carried"* described a
            # deposit moving between two accounts. Nothing moves at a sale —
            # the deposit stays on the account, which stays — so the sentence
            # says what the buyer is holding rather than what travelled.
            out.append(f"deposit stays with the account ${_display(carried)}")
        if self.arrear_follows:
            # ⚖️ PO 2026-09-01: *"money follow property - new owner boutght
            # everything property + debt also"*.
            out.append(f"the buyer takes on ${_display(self.arrear)}")
        return out


def _statement_for(account: models.Account, as_of: date | None = None) -> MoneyStatement:
    return MoneyStatement(
        currency=account.currency,
        deposit_principal=_money(account.deposit_on_file, "the deposit on file"),
        deposit_interest=_deposit_interest(account, as_of),
        arrear=_money(account.balance, "the account balance"),
    )


def _unavailable_for(statement: MoneyStatement) -> list[dict[str, Any]]:
    """`gaps` above, with each absence's full sentence. Same list, same order,
    same reason — one predicate, so the codes and the prose cannot disagree."""
    out: list[dict[str, Any]] = []
    if statement.carries_a_deposit and statement.deposit_interest is None:
        out.append(DEPOSIT_INTEREST_NOT_READABLE)
    if statement.arrear_follows:
        out.append(BALANCE_IS_A_CACHE)
    return out


def _serialize(transfer: Transfer, statement: MoneyStatement | None = None) -> dict[str, Any]:
    """B18 §5.7.2's row, plus what a detail view needs.

    `to_account_no` is `None` and the FROM cell's second line is the STRING
    `"→ —"` — TC-TRF-2: *"`→ —` in the FROM ACCOUNT cell, not a blank"*. The
    dash is produced here rather than left to the screen because a blank second
    line and an absent one are indistinguishable once rendered.
    """
    from_account = transfer.from_account
    to_account = transfer.to_account
    row: dict[str, Any] = {
        "id": str(transfer.id),
        # CR-039 wave D task 15. The reference a clerk quotes — and, when there
        # is none, the REASON, served beside it rather than left for the screen
        # to guess at. A screen handed `None` alone can only draw a blank or a
        # dash, and neither of those says *"nobody has set up transfer
        # numbering"* (DEF-127's shape: an absence that looks like a value).
        "transfer_no": transfer.transfer_no,
        "transfer_no_unavailable": (
            None if transfer.transfer_no else dict(TRANSFER_NUMBER_UNAVAILABLE)
        ),
        "state": transfer.state,
        "step": transfer.step,
        "step_of": STEP_COUNT,
        "step_label": dict(STEPS).get(transfer.step),
        # ⊕ 0068 — NULL where the account had nobody linked (`DEF-CUS-6387`);
        # `seller_name` is then the only record of who sold it, and it is
        # served on every row whether or not a customer row exists.
        "customer_id": str(transfer.customer_id) if transfer.customer_id else None,
        "seller_name": transfer.seller_name,
        "from_account_id": str(transfer.from_account_id),
        "from_account_no": from_account.account_no,
        "to_account_id": str(transfer.to_account_id) if transfer.to_account_id else None,
        "to_account_no": to_account.account_no if to_account else None,
        # B18 §5.7.2: two lines, `A-10650` above and `→ A-11940` beneath.
        "from_cell": [
            from_account.account_no,
            f"→ {to_account.account_no}" if to_account else "→ —",
        ],
        "to_unit_id": str(transfer.to_unit_id) if transfer.to_unit_id else None,
        "out_date": transfer.out_date.isoformat() if transfer.out_date else None,
        "in_date": transfer.in_date.isoformat() if transfer.in_date else None,
        # §5.7.4: "Same-day rule applies here too" — the outgoing pays the move
        # day and the incoming starts the next day from the same reading.
        "same_day": (
            None
            if transfer.out_date is None or transfer.in_date is None
            else transfer.out_date == transfer.in_date
        ),
        #: ⊕ 0060 — **who bought it, beside a `customer_id` that names who
        #: SOLD it.** Both are on the row so a record page renders *sold by →
        #: bought by* without a second query, and neither is derived from the
        #: account's current link, which answers a different question the day
        #: the property sells again.
        "buyer_customer_id": (
            str(transfer.buyer_customer_id) if transfer.buyer_customer_id else None
        ),
        "deposit_carry_elected": transfer.deposit_carry_elected,
        "arrears_follow_elected": transfer.arrears_follow_elected,
        "committed_at": transfer.committed_at.isoformat() if transfer.committed_at else None,
        "cancelled_at": transfer.cancelled_at.isoformat() if transfer.cancelled_at else None,
    }
    if statement is not None:
        row["money"] = {
            "currency": statement.currency,
            "deposit_carried": _pair(statement.deposit_carried),
            "arrear_following": _pair(statement.arrear if statement.arrear_follows else None),
            "sentences": statement.sentences,
            "gaps": statement.gaps,
            "unavailable": _unavailable_for(statement),
        }
    return row


# ═══════════════════════════════════════════════════════════════════════════
# THE EXCLUSION CONTRACT (task 7.2) — published so a future list must meet it
# ═══════════════════════════════════════════════════════════════════════════
#: Read by `tests/test_w7_transfers.py`'s static half. Any move-in / move-out
#: list builder that appears in this app must call one of these three, or the
#: contract test goes red naming the file. See §2 of the module docstring.
EXCLUSION_CONTRACT: tuple[str, ...] = (
    "transfer_half_account_ids",
    "is_transfer_half",
    "exclude_transfer_halves",
)


def transfer_half_account_ids(*, include_open: bool = True) -> set[str]:
    """Every account id that is one half of a transfer job.

    `include_open` covers B18 §5.7.3's counting contract properly: a transfer
    at step 3 has ALREADY taken its outgoing account out of the Move-outs
    count — the callout says *"a transfer appears only here"*, not *"a
    COMMITTED transfer appears only here"* — and §5.7.6's fixture proves it,
    since `A-11455 · Park, Jenna` sits at `3 of 5` and is not in the Move-outs
    five. A cancelled job releases its account, because nothing about it
    happened.
    """
    rows = Transfer.objects.filter(tenant_id=_tenant_id()).exclude(state=Transfer.STATE_CANCELLED)
    if not include_open:
        rows = rows.filter(committed_at__isnull=False)
    out: set[str] = set()
    for from_id, to_id in rows.values_list("from_account_id", "to_account_id"):
        out.add(str(from_id))
        if to_id:
            out.add(str(to_id))
    return out


def is_transfer_half(account_id: Any, *, include_open: bool = True) -> bool:
    """The per-row predicate B18 §5.7.3 asks a Move-ins / Move-outs list to
    apply. True means: this account's move is part of a transfer and listing it
    as a move-in or a move-out would count one job twice."""
    return str(account_id) in transfer_half_account_ids(include_open=include_open)


def exclude_transfer_halves(queryset: Any, *, field: str = "id") -> Any:
    """The queryset form, for whoever builds `GET /move-ins` and `GET /move-outs`.

    `field` names the column holding the ACCOUNT id — `id` on an `accounts`
    queryset, `account_id` on anything keyed to one.
    """
    excluded = transfer_half_account_ids()
    if not excluded:
        return queryset
    return queryset.exclude(**{f"{field}__in": excluded})


# ═══════════════════════════════════════════════════════════════════════════
# THE FIVE STEPS (task 7.1)
# ═══════════════════════════════════════════════════════════════════════════
def _guard_open(transfer: Transfer) -> None:
    if transfer.committed_at is not None:
        raise errors.BizError(
            errors.BIZ_IDEMPOTENT,
            br_ref="BR-CUS-030",
            message_key="customers.transfer.already_committed",
            params={"transfer_id": str(transfer.id), "reason": REFUSAL_ALREADY_COMMITTED},
        )
    if transfer.cancelled_at is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-030",
            message_key="customers.transfer.already_cancelled",
            params={"transfer_id": str(transfer.id), "reason": REFUSAL_ALREADY_CANCELLED},
        )


def _actor_user_id(actor: Any) -> Any:
    """The committing user's id, or None for an actor with no `users` row."""
    from apps.identity.models import User

    user_id = getattr(actor, "id", None)
    if user_id is None:
        return None
    return user_id if User.objects.filter(pk=user_id).exists() else None


def _touch(transfer: Transfer, *fields: str) -> None:
    transfer.updated_at = timezone.now()
    transfer.save(update_fields=[*fields, "updated_at"])


#: `DEF-CUS-6395` — the account is already part-way through a sale.
REFUSAL_ALREADY_BEING_SOLD = "from_account_already_being_sold"


def sale_refusal(account: models.Account) -> dict[str, Any] | None:
    """**Would `start_transfer` refuse this account?** — asked, never raised.

    ⚠ **ONE FUNCTION FOR TWO DOORS, AND THAT IS THE FIX (`DEF-CUS-6395`).** The
    commit raises what this returns; `POST /transfers/account-preview` SERVES it
    to step 1 the moment the clerk picks the account. Two copies of the rule
    would drift, and a preview that disagreed with the commit is the five-step
    dead end this exists to end.

    ⚠ **THE OPEN-SALE CHECK IS ASKED, NOT CAUGHT.** `uq_transfers_open_from`
    allows one open transfer per account and used to be the only thing standing
    in the way — an `IntegrityError` inside the commit's transaction, which on
    PostgreSQL poisons the whole transaction (hard-won law 14) and reached the
    clerk as a server error. It is asked first, in the same locked read, and
    refused by name.

    Returns `{"code", "br_ref", "message_key", "params"}` or `None`.
    """
    from apps.customers import services

    if not services.is_occupying(account.status):
        return {
            "code": REFUSAL_NOT_AN_OCCUPANT,
            "br_ref": "BR-CUS-030",
            "message_key": "customers.transfer.not_an_occupant",
            "params": {
                "account_no": account.account_no,
                "status": account.status.code,
                "reason": REFUSAL_NOT_AN_OCCUPANT,
            },
        }
    open_sale = Transfer.objects.filter(
        tenant_id=account.tenant_id,
        from_account_id=account.pk,
        committed_at__isnull=True,
        cancelled_at__isnull=True,
    ).exists()
    if open_sale:
        return {
            "code": REFUSAL_ALREADY_BEING_SOLD,
            "br_ref": "BR-CUS-1030",
            "message_key": "customers.transfer.already_being_sold",
            "params": {"account_no": account.account_no, "reason": REFUSAL_ALREADY_BEING_SOLD},
        }
    return None


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def start_transfer(actor: Any, payload: Any = None) -> dict[str, Any]:
    """STEP 1 — *"Find the account and confirm who is selling"*.

    ⛔ **THE SELLER IS READ, NEVER MATCHED AND NEVER TYPED** — the
    `customer_accounts` link (`BR-CUS-054`). B18 §2.5 records name matching as
    the failure the customer entity exists to end.

    ⛔ **AN ACCOUNT WITH NOBODY ON FILE IS SOLD, NOT REFUSED — `BR-CUS-1081`
    T1, decided 2026-09-23 (`DEF-CUS-6387`).** The seller is recorded by the
    name on the account (`seller_name`); `_seller_of` carries the reasoning.

    Only an OCCUPANT may sell, and only one sale of an account may be open at a
    time — both asked by `sale_refusal`, the SAME function the step-1 preview
    door asks, so the clerk is refused on the step where they picked the account
    rather than five steps later (`DEF-CUS-6395`).
    """
    from apps.customers import selectors, services

    data = dict(payload or {})
    account_id = data.get("from_account_id")
    if account_id in (None, ""):
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="customers.transfer.from_account_required"
        )
    with transaction.atomic():
        account = selectors.account_or_404(account_id, lock=True)
        refusal = sale_refusal(account)
        if refusal is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref=refusal["br_ref"],
                message_key=refusal["message_key"],
                params=refusal["params"],
            )
        customer = _seller_of(account)
        # CR-039 wave D task 15. INSIDE the atomic block and BEFORE the row
        # exists (BR-TEN-035 · `services._allocate_account_no`'s shape), so a
        # transfer is never on file without its number.
        transfer_no, _number_unavailable = _allocate_transfer_no()
        transfer = Transfer.objects.create(
            tenant_id=_tenant_id(),
            transfer_no=transfer_no,
            from_account=account,
            customer=customer,
            seller_name=_seller_name_of(account, customer),
            step=1,
            state=Transfer.STATE_SCHEDULED,
        )
        row = _serialize(transfer)
        _audit(actor, "transfer.started", transfer.id, after=row)
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def set_new_customer(actor: Any, transfer_id: Any, payload: Any = None) -> dict[str, Any]:
    """STEP 2 — *"Who is buying it — name, person or company, and one identifier"*.

    ⛔ **THIS REPLACES `set_target_unit`, AND THE REPLACEMENT IS THE WHOLE
    RULING.** That step asked *"which unit is the customer moving to"*; under
    `BR-CUS-1030` a transfer answers *"who is buying this property"* and **the
    unit does not change at all**.

    ⚠ **IT VALIDATES AND STORES NOTHING, AND THAT IS DELIBERATE RATHER THAN
    UNFINISHED.** The buyer's evidence — a name, a kind, and one identifier —
    is a **government identifier**, and `transfers` has no encrypted column to
    put one in; `customers` does (`CR-056` W2, app-layer encrypted with a keyed
    blind index) and it is the module that owns identity. Parking an SSN in a
    workflow table for the length of a wizard would be a second, weaker place a
    person's identity lives, which is exactly what `BR-CUS-1020` exists to stop.
    So the block is CHECKED here — so a clerk is told at step 2 rather than at
    step 5 — and CARRIED to `reassign_account`, which hands it to the one door
    that resolves a customer.

    ⚠ **AND THE "STORES NOTHING" HALF NOW COVERS MORE FIELDS RATHER THAN FEWER
    (2026-09-20).** The buyer carries the whole capture set — a date of birth, a
    telephone number, an email, a preferred language, a co-applicant and a
    mailing address — and **not one of them gets a column on `transfers`
    either.** The reasoning that kept an SSN out is not about encryption, it is
    about a workflow table becoming a second home for a person; a date of birth
    parked here for the length of a wizard would be exactly that. Every one of
    them lands on `customers`, `contacts`, `accounts` or `addresses` at commit,
    through the doors those tables already have.

    **WHAT IT CHECKS**, and it is the file-side mirror of `BR-CUS-1023` rather
    than a second copy of it: a name, a stated kind, and at least one identifier
    belonging to THAT kind. A person is known by a Social Security number, a
    driving licence or a phone; a company by its Tax ID. Everything the
    2026-09-20 ruling added is OPTIONAL — `_validated_buyer`'s own docstring
    carries that judgment and the cost of it.

    ⊕ **IT NOW ANSWERS THE QUESTION THE CLERK IS ABOUT TO GET WRONG.** The
    conformance walk of 2026-09-20: *"The 'Matched an existing customer' line is
    never shown — the match happens on the server at commit and the clerk is
    never told whether they are about to create a new customer or reuse one."*
    `buyer_match` on this response is that line's answer, and it is served here
    because THIS is the step where the clerk can still act on it.
    """
    data = dict(payload or {})
    block = _validated_buyer(data.get("customer"))
    with transaction.atomic():
        transfer = _transfer_or_refuse(transfer_id, lock=True)
        _guard_open(transfer)
        transfer.step = max(transfer.step, 2)
        transfer.state = Transfer.STATE_IN_PROGRESS
        _touch(transfer, "step", "state")
        row = _serialize(transfer)
        # ⚠ **THE NAME ONLY, AND NEVER AN IDENTIFIER** (B14 rule 31's sibling
        # concern: what a screen may show). The audit row records that a buyer
        # was named and who by; the identifiers reach `audit_log` nowhere on
        # this path, because they reach no column on this path.
        row["buyer_name"] = block["display_name"]
        row["buyer_kind"] = block["kind"]
        row["buyer_identifiers_presented"] = sorted(block["identity"])
        # ⚠ **WHAT WAS PRESENTED, NEVER WHAT IT SAID.** The audit row records
        # WHICH captured facts arrived — so a reviewer can see a date of birth
        # was asked for — and none of their VALUES. `_audit` masks identifiers
        # at the boundary one module over; here there is nothing to mask
        # because nothing is written.
        row["buyer_capture_presented"] = sorted(block["capture"])
        row["buyer_mailing_presented"] = block["mailing_address"] is not None
        _audit(actor, "transfer.buyer_named", transfer.id, after=row)
    # ⚠ **OUTSIDE THE TRANSACTION AND AFTER THE AUDIT ROW, ON PURPOSE.** The
    # preview is a READ that changes nothing, and a matcher that raised would
    # otherwise roll back the clerk's step. It is the last thing that happens
    # and the first thing they read.
    row["buyer_match"] = buyer_match(block)
    return row


def buyer_match(block: dict[str, Any]) -> dict[str, Any]:
    """**Is this buyer already on file?** — asked BEFORE the commit, answered
    without writing anything.

    ⛔ **NEW 2026-09-20.** The conformance walk found the gap in one sentence:
    *"the match happens on the server at commit and the clerk is never told
    whether they are about to create a new customer or reuse one."* It is the
    difference between a clerk knowingly reusing a customer and unknowingly
    minting a duplicate, and `DEF-2587` is what the second one costs — a
    landlord written as `C-00001`, `C-00002` and `C-00003` over one Social
    Security number, with the matcher having found the earlier row every time
    and nobody reading the answer.

    ⚠ **IT LINKS NOTHING AND MOVES NOTHING, AND THAT IS `recognise`'s OWN
    GUARANTEE RATHER THAN A PROMISE MADE HERE** (hard-won law 1). This function
    builds `IdentityEvidence` and calls `identity_match.recognise`, which is
    the matcher `service_request_service.suggest_customer_matches` names as
    *"the matcher for a customer"* in its own refusal. No second matcher is
    written and no criteria are re-decided: `BR-CUS-089` is signed and
    **may not be widened to fit what is easy to compute**.

    ⚠ **IT IS ADVISORY AND IT REFUSES NOTHING — `BR-CUS-019`.** *The duplicate
    check is ADVISORY; staff decides.* A weak match is shown, never enforced,
    and a clerk who means to open a second customer for a genuinely different
    party is not stopped.

    **THREE ANSWERS, and `verdict` is which one:**

      * `named` — the clerk POINTED at a customer (`customer_id` or
        `external_ref`) and it exists. The commit will use exactly that one and
        weigh no evidence, so `tier` is `None` rather than `strong`.
      * `matched` — a customer id, `tier: "strong"`, and `basis` saying what
        agreed. The commit will REUSE this customer.
      * `candidates` — somebody looks related and the criteria are not met.
        The commit will CREATE a new customer beside them.
      * `none` — nobody on file. The commit will create a first-timer.

    ⚠ **`missing_for_strong` IS THE HALF THAT MAKES IT ACTIONABLE.**
    `BR-CUS-089` wants name + date of birth + one government identifier, so a
    buyer with a candidate and no date of birth is one question away from a
    reuse instead of a duplicate. Naming the missing fact is what turns *"we
    could not match"* into something a clerk can do about it — and it is why
    the date of birth is OPTIONAL rather than compulsory: a genuine first-time
    buyer has nothing to match against and must not be refused.

    ⚠ **NO NAMES AND NO IDENTIFIERS OF ANYBODY ELSE LEAVE THIS FUNCTION BEYOND
    WHAT THE MATCHER ALREADY PUBLISHES.** `_candidate` decides that shape and
    is customers' own; a richer projection invented here would be this module
    deciding how much of a stranger's record a clerk may see.
    """
    # ⛔ **THE CLERK'S EXPLICIT ANSWER IS CHECKED FIRST, BECAUSE `link_customer`
    # CHECKS IT FIRST — `DEF-CUS-5974`.** A preview that ran only the matcher
    # answered `will_create: true` for a buyer the commit was going to REUSE,
    # whenever the block named a `customer_id` or an `external_ref`:
    # `link_customer` resolves a named customer, then a quoted customer number,
    # then the matcher, then the legacy ref — and a preview that models only the
    # third step is a preview of a different function.
    #
    # ⚠ **IT WAS FOUND BY ASKING LAW 7's SECOND QUESTION OF NEW CODE — *what
    # would make this check pass wrongly* — AND NOT BY A TEST**, because the
    # shipped wizard sends neither key today. That is the worst shape for a
    # wrong answer: unreachable from the one screen that exists, correct in
    # every test written against that screen, and waiting for the first caller
    # who uses the field the door already accepts.
    # ⚠ **`customer_no` IS `link_customer`'s SECOND BRANCH AND IS NOT MODELLED
    # HERE, BECAUSE THIS DOOR CANNOT REACH IT.** `reassign_account` passes
    # `customer_id` and `external_ref` and no `customer_no`, and
    # `_validated_buyer` returns no such key — so there is no payload that would
    # take that branch on a sale. **If a lane ever adds `customer_no` to the
    # buyer block, it must be added here in the same commit**, or this preview
    # starts answering `will_create: true` about a reuse again, which is exactly
    # `DEF-CUS-5974`.
    named = block.get("customer_id") or block.get("external_ref")
    if named:
        tenant_id = _tenant_id()
        row = None
        if block.get("customer_id"):
            try:
                row = models.Customer.objects.filter(
                    tenant_id=tenant_id, id=block["customer_id"]
                ).first()
            except (DjangoValidationError, ValueError, TypeError):
                # ⚠ **A MALFORMED ID IS *NOT RECOGNISED*, NEVER A 500.** Django
                # raises on a string that is not a UUID before the query runs.
                # `link_customer` has the same exposure and answers it with a
                # refusal, which is right at a COMMIT; this is a preview a
                # screen may call on every keystroke, so a half-typed id must
                # fall through to the matcher rather than break the step.
                row = None
        if row is None and block.get("external_ref"):
            row = models.Customer.objects.filter(
                tenant_id=tenant_id, external_ref__iexact=str(block["external_ref"]).strip()
            ).first()
        if row is not None:
            return {
                # ⚠ **`named` AND NOT `matched`.** The clerk POINTED at this
                # customer; nothing was recognised. Calling it a match would
                # claim evidence agreed when none was weighed, and
                # `BR-CUS-089`'s tier is exactly what must not be implied.
                "verdict": "named",
                "matched": str(row.id),
                "tier": None,
                "basis": None,
                "candidates": [],
                "missing_for_strong": [],
                "will_create": False,
            }
    evidence = identity_match.from_payload(
        {
            "name": block["display_name"],
            "date_of_birth": block.get("date_of_birth"),
            **block["identity"],
        },
        kind=block["kind"],
    )
    if not evidence.has_any():
        return {
            "verdict": "none",
            "matched": None,
            "tier": None,
            "basis": None,
            "candidates": [],
            "missing_for_strong": [],
            "will_create": True,
        }
    result = identity_match.recognise(evidence)
    missing: list[str] = []
    if result["matched"] is None and result["candidates"]:
        # Only the facts `BR-CUS-089` names, and only the ones that are ABSENT.
        # A field the clerk already filled in is not a thing to go and ask for.
        if evidence.dob is None and identity_match.FACT_DOB in identity_match.KIND_DATED_FIELDS.get(
            block["kind"], ()
        ):
            missing.append("date_of_birth")
        if not (
            set(block["identity"]) & set(identity_match.GOVERNMENT_ID_FIELDS)
        ) and block["kind"] == identity_match.KIND_PERSON:
            missing.append("ssn_or_drivers_licence")
    return {
        "verdict": (
            "matched"
            if result["matched"]
            else ("candidates" if result["candidates"] else "none")
        ),
        "matched": result["matched"],
        "tier": result["tier"],
        "basis": result["basis"],
        "candidates": result["candidates"],
        "missing_for_strong": missing,
        # ⚠ **THE SENTENCE THE STEP WAS DRAWN TO SAY.** `TRF-02.2` draws
        # *"Matched first, created only on no match"* as its help, and this is
        # that promise stated back as a fact about THIS buyer.
        "will_create": result["matched"] is None,
    }


def _is_uuid(value: str) -> bool:
    """A malformed id is refused as NOT FOUND rather than letting Django's
    `UUIDField` raise a validation error from inside a lookup."""
    import uuid

    try:
        uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return False
    return True


def _validated_buyer(block: Any) -> dict[str, Any]:
    """The buyer's evidence AND what the account needs, or a refusal that NAMES
    what is missing.

    ⛔ **WIDENED 2026-09-20 — `BR-CUS-1081`. IT USED TO TAKE FIVE FACTS AND IT
    NOW TAKES THE CAPTURE SET.** PO, having walked the live wizard: *"step 2
    dont allow to take kYC documents - DOB, all detaisl we need to create
    account - Similar to Move in request we will need all details for account"*,
    and *"we have it - we have created it for service request move in - use
    it"*. The set is `BUYER_CAPTURE_FIELDS`, derived from
    `service_request_service.CAPTURE_FIELDS` and proved against it by
    `_capture_vocabulary()` on every call.

    ⚠ **IT MIRRORS `BR-CUS-1023`; IT DOES NOT RE-DECIDE IT.** Whether the
    evidence actually mints a Customer # is customers' question and
    `link_customer` answers it inside the account door. This exists so the
    clerk is refused at step 2, in front of the form they are typing into,
    rather than at step 5 after they have set a date — which is `BR-CUS-1023`'s
    own clause about naming the missing thing *"at the door where the clerk is
    typing"*.

    ════════════════════════════════════════════════════════════════════════
    WHAT IS REQUIRED, AND WHY THE NEW FIELDS ARE NOT
    ════════════════════════════════════════════════════════════════════════
    **REQUIRED — three, and they are the three that were already required:**
    a NAME, a stated KIND, and at least ONE identifier belonging to that kind.
    That is `BR-CUS-1030`'s note in this file verbatim — *"no account may exist
    with nobody identifiable behind it, and handing a live ledger to an
    unidentified party produces exactly that"* — and nothing in the 2026-09-20
    ruling touches it.

    **EVERYTHING THE RULING ADDED IS OPTIONAL, AND THAT IS A JUDGMENT WITH A
    REASON RATHER THAN A DEFAULT.** The PO named the move-in request as the
    benchmark — *"Similar to Move in request"* — and on that form a date of
    birth, an email, a telephone number, a preferred language, a co-applicant
    and a mailing address are every one of them optional. Making a SALE stricter
    than the application the PO pointed at would refuse a buyer at the counter
    for a field the benchmark does not ask for, which is the opposite of what
    was ruled. `BR-CUS-1023` is the signed minimum — *"Customer ID - minimum
    name and one ID - minimum"* — and it is a MINIMUM, not a maximum.

    ⚠ **THE COST OF THE DATE OF BIRTH BEING OPTIONAL IS REAL AND IS SAID OUT
    LOUD RATHER THAN LEFT TO BE DISCOVERED.** `BR-CUS-089`'s criteria are
    **name + date of birth + one government identifier**, so a buyer captured
    without one can never reach a `strong` tier — and `discounts.
    carry_forward_offer` moves money only on `strong`. A returning customer
    whose deposit is **$150.00** carries **$0.00** of it, and is minted a SECOND
    customer number beside the one they already have. That is not hypothetical:
    `DEF-2587` measured exactly this shape on a landlord and found three
    customer rows over one Social Security number.
    **So it is not required and it is not silent:** `buyer_match` on the step-2
    response reports a candidate that could not be matched strongly AND names
    the missing fact, so the clerk is told what asking one more question would
    buy. A field made compulsory to make a match strong would refuse a genuine
    first-time buyer who has no prior record to match against at all.

    ⚠ **A COMPANY IS NOT ASKED FOR A DATE OF BIRTH OR A LICENCE (`BR-CUS-1022`),
    AND THE REFUSAL IS BY NAME RATHER THAN A DROP.** The rule's own words are
    why: *"asking for both and leaving one blank turns a rule into a habit and
    the blank field eventually gets filled with something."* The vocabulary is
    `service_request_service.KIND_FORBIDDEN_FIELDS`, read rather than copied.

    ⚠ **THE SHIPPED SPELLINGS STILL WORK.** `display_name`, `kind`, `email`,
    `phone`, `dob` and `driving_licence` are mapped to the capture set's own
    names by `_BUYER_ALIASES`. Four sibling lanes are live on
    `TransferWizard.tsx` and a door that stopped taking `display_name` would
    break a screen in the middle of their work.
    """
    from apps.customers import service_request_service as sr

    if not isinstance(block, dict) or not block:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="customers.transfer.buyer_required"
        )

    capture = _capture_vocabulary()
    data: dict[str, Any] = {}
    for key, value in block.items():
        data[_BUYER_ALIASES.get(key, key)] = value

    name = str(data.get("applicant_name") or "").strip()
    kind = identity_match.normalise_kind(data.get("applicant_kind"))
    identity = data.get("identity") or {}
    if not isinstance(identity, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="customers.transfer.buyer_required"
        )
    # ⚠ **THE IDENTIFIERS ARRIVE TWO WAYS AND BOTH ARE HONOURED.** `identity{}`
    # is what the shipped wizard sends; a FLAT `ssn` / `drivers_licence` /
    # `applicant_phone` is what the capture set spells, and the ruling says to
    # reuse that set. Merging here means the contract can publish ONE shape
    # while the live screen keeps working — and the flat form loses to the
    # nested one on a clash, because `identity{}` is the deliberate block and a
    # flat key is the convenience.
    presented_flat = {
        "ssn": data.get("ssn"),
        "drivers_licence": data.get("drivers_licence"),
        "phone": data.get("applicant_phone"),
        "tax_id": data.get("tax_id"),
    }
    merged_identity = {**presented_flat, **identity}
    presented = {
        field: str(value).strip()
        for field, value in merged_identity.items()
        if str(value or "").strip()
    }
    if not name:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.customer.display_name_required",
            params={"reason": REFUSAL_BUYER_NOT_IDENTIFIED},
        )
    if kind is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.customer.kind_required_for_identity",
            params={"reason": REFUSAL_BUYER_NOT_IDENTIFIED},
        )
    if kind not in identity_match.CREATE_IDENTIFIER_FIELDS:
        # ⛔ **DEF-CUS-9646 — A KIND THE TABLE DOES NOT KNOW IS REFUSED BY NAME,
        # BEFORE THE TABLE IS INDEXED.** `normalise_kind` returns an unknown
        # value as typed, on purpose (*"whether it is one of the two lawful
        # kinds is the VALIDATOR's question"*), and this validator then indexed
        # the table with it: `business` — the REQUEST's spelling of a company,
        # one vocabulary over — answered 500 `KeyError`. The sentence is the
        # customer record's own (`services._clean_kind`), so no key is minted.
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.customer.kind_unknown",
            params={"value": str(data.get("applicant_kind")), "reason": REFUSAL_BUYER_NOT_IDENTIFIED},
        )
    allowed = set(identity_match.CREATE_IDENTIFIER_FIELDS[kind])
    # ⊕ **A BUYER FOUND AND LINKED NEEDS NO IDENTIFIER RE-TYPED — T1, PO
    # 2026-09-23 (`DEF-CUS-6386`).** *"search custoemr id for buyer … if custoemr
    # id is found then link it"*. The customer on file IS the evidence: it was
    # minted under `BR-CUS-1023` and its identifiers are held encrypted where
    # this screen is only ever served the last four (`BR-CUS-092(c)`), so
    # demanding one here would refuse on screen what `link_customer` accepts —
    # it takes the clerk's named `customer_id` over everything (`BR-CUS-019`:
    # staff decides; matches resolve by LINKING). New Connect's owner step
    # takes the same posture (`ownerIdentityShortfall`: *"an attached customer
    # needs no evidence"*). ⚠ A PHONE STILL NEVER ATTACHES (`BR-CUS-1024`): the
    # link is the clerk pressing *Link* on a row, never a match on a phone.
    #
    # ⚠ **ONLY A REAL CUSTOMER OF THIS TENANT EXEMPTS — AND ANYTHING ELSE FALLS
    # THROUGH, IT IS NEVER REFUSED HERE.** `DEF-CUS-5974`'s contract: a
    # half-typed id is *"not recognised, never a 500"*, because the preview may
    # be asked on every keystroke. So an id that is malformed, unknown, or
    # another tenant's (HR-1: all three are the same fact from here) earns no
    # exemption and the ordinary identifier rule below applies to it.
    linked_customer = str(block.get("customer_id") or "").strip()
    is_linked = bool(linked_customer) and (
        _is_uuid(linked_customer)
        and models.Customer.objects.filter(tenant_id=_tenant_id(), pk=linked_customer).exists()
    )
    if not (set(presented) & allowed) and not is_linked:
        # ⛔ **NAMED, NEVER A BARE REFUSAL.** `BR-CUS-1023`: the refusal names
        # the missing thing in plain words at the door where the clerk is
        # typing. The message key resolves to the per-kind sentence.
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-CUS-1030",
            # ⚠ **THE EXISTING SENTENCE, DELIBERATELY REUSED.** All eleven
            # catalogues already hold its translation and it already says the
            # right thing per kind — telling a business it needs a driving
            # licence sends somebody to find a document that does not exist.
            message_key=identity_match.NOT_CREATED_MESSAGE_KEY[
                (identity_match.MISSING_IDENTIFIER, kind)
            ],
            params={
                "reason": REFUSAL_BUYER_NOT_IDENTIFIED,
                "accepted": sorted(allowed),
            },
        )

    # ── `BR-CUS-1022` — a company is never asked a person's questions ────────
    # ⚠ **THE REQUEST'S OWN GUARD IS CALLED, NOT A COPY OF ITS TABLE.**
    # `_refuse_fields_for_kind` holds both the vocabulary and the sentence, so
    # the sale and the application refuse the same field on the same day and in
    # the same words — and no twelfth locale key is minted for a rule that
    # already has one (`G15` obliges eleven catalogues for every new key, and
    # four sibling lanes are live in those files today).
    #
    # ⚠ **THE TWO KIND VOCABULARIES ARE BRIDGED HERE AND THE GAP IS STATED.**
    # `customers.kind` is `person | company`; `service_requests.applicant_kind`
    # is `person | business`. `service_request_service`'s own docstring records
    # the split; this maps across it rather than pretending it is not there.
    sr._refuse_fields_for_kind(
        sr._SR.APPLICANT_BUSINESS
        if kind == identity_match.KIND_COMPANY
        else sr._SR.APPLICANT_PERSON,
        {field for field in capture if str(data.get(field) or "").strip()},
    )

    # ── the capture set, cleaned by the functions that already own it ────────
    # ⚠ **`_clean_date_of_birth` IS CALLED, NOT REIMPLEMENTED.** It carries
    # `BR-CUS-1020`'s type decision and its deliberate absence of a plausibility
    # rule; a second parser here would be a second answer to *is this a date*.
    captured: dict[str, Any] = {}
    for field in sorted(capture):
        if field in ("applicant_name", "applicant_kind", "ssn", "drivers_licence"):
            continue  # handled above — identity, not contact
        value = data.get(field)
        if field == "date_of_birth":
            cleaned_dob = sr._clean_date_of_birth(value)
            if cleaned_dob is not None:
                captured[field] = cleaned_dob
            continue
        text = sr._text(value, 200)
        if text:
            captured[field] = text

    return {
        # The three that were always here, under both names: `display_name` and
        # `kind` are what every existing caller and test read, and the capture
        # spellings are what the contract publishes. Neither is dropped.
        "display_name": name[:200],
        "applicant_name": name[:200],
        "kind": kind,
        "applicant_kind": kind,
        # Only the identifiers this kind is known by. A company's Social
        # Security number is not stored anywhere — `BR-CUS-1022`: it would be
        # filed where the company matcher never looks.
        "identity": {field: value for field, value in presented.items() if field in allowed},
        "customer_id": block.get("customer_id"),
        "external_ref": block.get("external_ref"),
        # ⊕ 2026-09-20 — everything the ruling added, already cleaned.
        "capture": captured,
        "date_of_birth": captured.get("date_of_birth"),
        "mailing_address": _validated_buyer_mailing(block.get("mailing_address")),
    }


def _validated_buyer_mailing(block: Any) -> dict[str, Any] | None:
    """Where the BUYER's bill goes — **CLAUDE.md hard rule 8's named exception.**

    ⛔ **NEW 2026-09-20, ON A PO RULING, AND IT DECLARES NO COLUMN ANYWHERE.**
    The conformance walk of the same day found it missing in one sentence:
    *"there is no `Mailing address` for the buyer, so a landlord's bill has
    nowhere else to go."* An address lives on `premises` and every entity walks
    to it — **except** `customers.addresses` `kind='mailing'`, which is *"where
    the BILL goes, which for a landlord is another building"*. That is the one
    lawful second address and it is where this goes; `G85` fails a fourth home
    and this path gives it nothing to find.

    ⚠ **IT VALIDATES THE SHAPE AND WRITES NOTHING.** The write is
    `services.update_account_mailing_address` at commit — the door that already
    exists, already refuses `kind` from a caller by name so the RETIRED
    `kind='service'` cannot arrive even as a typo, and already treats an empty
    `line1` as *remove the row and post to the service address*. Reaching for
    `models.Address.objects.create` here would have been a second writer for a
    table that has one (hard-won law 11's last clause: look for the tool that
    owns the file).

    **OPTIONAL, and its absence is a real answer.** ⊕ Since T3 (PO 2026-09-23,
    `DEF-CUS-6393`) no block means *bills go by post to the service address*:
    the SELLER's mailing row is REMOVED at the sale rather than kept
    (`_carry_buyer_onto_account`). `line2` rides the moment the write door's
    `ADDRESS_FIELDS` carries it — this set is derived from that door.

    `line1` is required WHEN A BLOCK IS PRESENT: an address with no first line
    is not a place, and the write door would read it as a removal.
    """
    if block in (None, "", {}):
        return None
    if not isinstance(block, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.address.line1_required",
            params={"field": "mailing_address"},
        )
    allowed = _mailing_vocabulary()
    unknown = sorted(set(block) - allowed)
    if unknown:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.address.line1_required",
            params={"field": unknown[0], "accepted": sorted(allowed)},
        )
    cleaned = {
        field: str(value).strip()
        for field, value in block.items()
        if str(value or "").strip()
    }
    if not cleaned.get("line1"):
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.address.line1_required",
            params={"field": "line1"},
        )
    return cleaned


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def preview_buyer(actor: Any, payload: Any = None) -> dict[str, Any]:
    """**Step 2, asked and not answered yet** — validate a buyer and say whether
    they are already on file. `POST /transfers/buyer-preview`.

    ⛔ **NEW 2026-09-20, AND IT EXISTS BECAUSE THE WIZARD HAS NO OTHER MOMENT
    TO ASK.** `POST /transfers/commit` runs all five steps in ONE transaction
    (`transfer_commit`'s own docstring says why), so `set_new_customer` is never
    reached from a browser on its own — and the clerk therefore learns whether
    they created a duplicate customer **after** the sale is done. This is the
    same read, at the moment it is still worth something.

    ⚠ **IT WRITES NOTHING AT ALL — NO TRANSFER ROW, NO CUSTOMER, NO AUDIT.**
    That is what makes it safe to call on every keystroke's worth of a form, and
    it is why it is a separate function rather than a flag on `set_new_customer`:
    a door that sometimes writes is a door nobody can reason about. `recognise`
    carries the same guarantee one module over — *"It links nothing and moves
    nothing"* — and this adds no second matcher beside it.

    ⚠ **IT IS ROLE-GATED LIKE EVERY OTHER TRANSFER DOOR, AND THAT IS NOT
    CEREMONY.** It answers *"is there a customer on file who looks like this
    person"* over a name and a government identifier, which is a search of the
    tenant's customer register. A guest door onto that would be an identity
    oracle.

    ⚠ **IT REFUSES EXACTLY WHAT THE COMMIT REFUSES, THROUGH THE SAME
    FUNCTION.** `_validated_buyer` is called, so a clerk who is short an
    identifier is told here in the same words they would be told at step 5 —
    and a preview that accepted a block the commit would reject would be worse
    than no preview, because they would trust it.
    """
    from apps.customers import selectors

    data = dict(payload or {})
    block = _validated_buyer(data.get("customer"))
    # ⊕ **`DEF-CUS-6395` — THE BUYER-SIDE REFUSAL, ON THE BUYER STEP.** With
    # the account in hand the preview asks the commit's own question — *is this
    # buyer already this account's customer?* — through the SAME function
    # `reassign_account` asks (`_already_this_accounts_customer`), so step 2
    # refuses where the commit would, rather than the clerk meeting it after the
    # date and the money. Optional: a preview without an account answers what
    # it always did.
    refusal: dict[str, Any] | None = None
    account_id = data.get("from_account_id")
    if account_id not in (None, ""):
        account = selectors.account_or_404(account_id)
        already = _already_this_accounts_customer(account, block)
        if already is not None:
            refusal = {
                "code": REFUSAL_BUYER_IS_THE_SELLER,
                "br_ref": "BR-CUS-1030",
                "message_key": "customers.transfer.buyer_is_the_seller",
                "params": {
                    "account_no": account.account_no,
                    "reason": REFUSAL_BUYER_IS_THE_SELLER,
                    "customer_no": already.customer_no,
                },
            }
    return {
        "buyer_name": block["display_name"],
        "buyer_kind": block["kind"],
        "buyer_identifiers_presented": sorted(block["identity"]),
        "buyer_capture_presented": sorted(block["capture"]),
        "buyer_mailing_presented": block["mailing_address"] is not None,
        "buyer_match": buyer_match(block),
        "refusal": refusal,
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def preview_account(actor: Any, payload: Any = None) -> dict[str, Any]:
    """**Step 1, answered the moment the account is picked** —
    `POST /transfers/account-preview`. Writes NOTHING.

    Two jobs, each a defect the PO reported on 2026-09-23:

      * **`DEF-CUS-6395` — the refusal where its cause is picked.** `sale_refusal`
        is the SAME function `start_transfer` raises, so step 1 says *already
        being sold* or *not an occupant* before the clerk types a buyer, instead
        of the commit saying it five steps later.
      * **`DEF-CUS-5182` — the drawn facts the wizard hard-coded as *"Not
        available yet"*.** The cycle, the current period and the next bill come
        from metering's own derivation (`seams.billing_cycle_for_unit`); the
        ledger's start is the account's own `opened_at` — a sale closes no
        account, so the ledger runs unbroken from the day it opened
        (`BR-CUS-1030`). The base charge is not here: the wizard reads it from
        `GET /units/{id}/pricing`, rating's own Σ (`BR-RAT-027`), which the
        move-in wizard already renders — one source, not two.

    And the two facts the review step needs about the SELLER: who they are on
    file (or that nobody is linked — `DEF-CUS-6387`, the sale goes ahead and
    records the name on the account) and whether the account is the premises'
    MASTER account, which decides whether the owner moves (`DEF-CUS-6394`).
    """
    from apps.customers import selectors, services

    data = dict(payload or {})
    account_id = data.get("from_account_id")
    if account_id in (None, ""):
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="customers.transfer.from_account_required"
        )
    account = selectors.account_or_404(account_id)
    seller = _seller_of(account)
    cycle = seams.billing_cycle_for_unit(account.unit_id) if account.unit_id else None
    return {
        "account_no": account.account_no,
        "refusal": sale_refusal(account),
        "seller": (
            {
                "customer_no": seller.customer_no,
                "name": seller.display_name,
                "kind": seller.kind,
            }
            if seller is not None
            else None
        ),
        "seller_name": _seller_name_of(account, seller),
        "is_master": account.kind == services.ACCOUNT_KIND_MASTER,
        "billing_cycle": (
            {"code": cycle["code"], "name": cycle["name"], "bill_day": cycle["bill_day"]}
            if cycle
            else None
        ),
        "current_period": (
            {"start": cycle["period_start"], "end": cycle["period_end"]}
            if cycle and cycle.get("period_start")
            else None
        ),
        "next_bill_on": cycle.get("next_bill_on") if cycle else None,
        "ledger_since": account.opened_at.isoformat() if account.opened_at else None,
    }


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def set_sale_date(actor: Any, transfer_id: Any, payload: Any = None) -> dict[str, Any]:
    """STEP 3 — *"The date of sale"*.

    ⛔ **THIS REPLACES `set_dates`, AND IT IS ONE DATE RATHER THAN TWO.** The
    old step asked for an out date and an in date because the job closed one
    account and opened another. **A sale closes nothing and opens nothing**: the
    account changes hands on one day. `out_date` and `in_date` are both written
    to that day so the stored row stays readable to every existing reader and
    `same_day` is true by construction rather than by a clerk typing it twice.

    ⚠ **THE DATE DECIDES NO BILLING AND IS NOT A PRORATION BOUNDARY.** Nothing
    is prorated at a sale: there is one unbroken account, one service agreement
    and one billing period, and the bill for the period covering the sale is
    issued to whoever owns the account when it is issued. That is the
    consequence of `BR-CUS-1030` and it is stated here so nobody adds a split.
    """
    data = dict(payload or {})
    # `out_date` is accepted as a spelling of the same fact so a caller written
    # against the old signature fails LOUDLY on the missing buyer rather than
    # silently on a key name.
    sold_on = _as_date(data.get("sold_on", data.get("out_date")), "sold_on")
    if sold_on is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="customers.transfer.sale_date_required"
        )
    with transaction.atomic():
        transfer = _transfer_or_refuse(transfer_id, lock=True)
        _guard_open(transfer)
        transfer.out_date = sold_on
        transfer.in_date = sold_on
        transfer.step = max(transfer.step, 3)
        transfer.state = Transfer.STATE_IN_PROGRESS
        _touch(transfer, "out_date", "in_date", "step", "state")
        row = _serialize(transfer)
        _audit(actor, "transfer.sale_date_set", transfer.id, after=row)
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def money_statement(actor: Any, transfer_id: Any) -> dict[str, Any]:
    """STEP 4 (read half) — **what the buyer takes on.**

    ⚖️ **THE DEBT FOLLOWS THE PROPERTY — PO ruling 2026-09-01, verbatim:**
    *"money follow property - new owner boutght everything property + debt
    also"*. This function is what puts the figure in front of a human before
    it becomes somebody else's.

    A pure read: it moves nothing, writes nothing and audits nothing.
    """
    transfer = _transfer_or_refuse(transfer_id)
    statement = _statement_for(transfer.from_account)
    row = _serialize(transfer, statement)
    row["steps"] = [{"step": n, "label": label} for n, label in STEPS]
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def acknowledge_money(actor: Any, transfer_id: Any, payload: Any = None) -> dict[str, Any]:
    """STEP 4 (decision half) — the clerk has SEEN what the buyer takes on.

    ⛔ **THIS REPLACES `elect_money`, AND THE REPLACEMENT IS THE RULING.** That
    function stored the clerk's ELECTION — *should the deposit carry, should the
    arrears follow* — because four signed rules disagreed and no open question
    covered it. **`OQ-1252` was raised and answered inside the hour**: the debt
    follows the property. **There is nothing left to elect.**

    ⚠ **AND THE ELECTION COLUMNS ARE STILL WRITTEN, WITH THEIR MEANING
    NARROWED RATHER THAN A MIGRATION RUN.** `deposit_carry_elected` and
    `arrears_follow_elected` now record the FACT the ruling makes true —
    both `True` whenever there is a position to carry — rather than a choice.
    Rows written before today keep whatever a clerk chose, and are still
    readable. A `NULL`-ing migration over a workflow table would be a schema
    change to say something the ruling already says.

    ⚠ **NOTHING MOVES HERE AND NOTHING MOVES AT COMMIT.** The account carries
    its own ledger, so reassigning the account **is** the debt following the
    property: the balance never moves, because the thing it sits on never
    moves. This function posts no journal line, raises no refund and touches
    neither `deposit_on_file` nor `balance` — see `reassign_account`.

    Audited under CLAUDE.md rule 7 with both figures in the row, because *what
    the buyer took on, as it stood at the moment of sale* is a fact the product
    will be asked about later and cannot reconstruct.
    """
    with transaction.atomic():
        transfer = _transfer_or_refuse(transfer_id, lock=True)
        _guard_open(transfer)
        statement = _statement_for(transfer.from_account)
        transfer.deposit_carry_elected = statement.carries_a_deposit
        transfer.arrears_follow_elected = statement.arrear_follows
        transfer.money_decided_at = timezone.now()
        transfer.step = max(transfer.step, 4)
        transfer.state = Transfer.STATE_IN_PROGRESS
        _touch(
            transfer,
            "deposit_carry_elected",
            "arrears_follow_elected",
            "money_decided_at",
            "step",
            "state",
        )
        row = _serialize(transfer, statement)
        _audit(actor, "transfer.money_acknowledged", transfer.id, after=row)
    return row


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def review(actor: Any, transfer_id: Any) -> dict[str, Any]:
    """STEP 5 (read half) — *"Review — one account, one new owner, one commit"*.

    ⛔ **ONE CONSEQUENCE NOW, NOT TWO.** The old review listed an outgoing half
    (*closed*) and an incoming half (*opened at a new unit*), because that is
    what the job did. Under `BR-CUS-1030` there is one account and it changes
    hands. A review that still drew two halves would be describing a product
    that no longer exists — which is worse than drawing nothing, because a
    clerk would believe it.
    """
    transfer = _transfer_or_refuse(transfer_id)
    statement = _statement_for(transfer.from_account)
    row = _serialize(transfer, statement)
    row["consequences"] = [
        {
            "half": "reassignment",
            "account_no": transfer.from_account.account_no,
            "effect": "customer_changes",
            "on": transfer.out_date.isoformat() if transfer.out_date else None,
            # Said in the review, before anything happens: these are the two
            # things a person would ask about and the two the product must not
            # be silent on.
            "unit_changes": False,
            "account_number_changes": False,
        }
    ]
    row["ready"] = _missing_for_commit(transfer) == []
    row["missing"] = _missing_for_commit(transfer)
    row["unavailable"] = _unavailable_for(statement)
    return row


def _missing_for_commit(transfer: Transfer) -> list[str]:
    """Which of steps 2–4 has not been done. Named, never a bare False.

    ⚠ **`step_2_target_unit` IS GONE AND `step_3_dates` IS NOW ONE DATE.** A
    sale changes no unit, so there is no target to be missing.
    """
    missing: list[str] = []
    if transfer.out_date is None:
        missing.append("step_3_sale_date")
    if transfer.money_decided_at is None:
        missing.append("step_4_money")
    return missing


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def reassign_account(actor: Any, transfer_id: Any, payload: Any = None) -> dict[str, Any]:
    """STEP 5 — **THE SAME ACCOUNT, A NEW CUSTOMER.** `BR-CUS-1030`.

    ⛔⛔ **THIS REPLACES `commit_transfer` AND REVERSES WHAT IT DID. READ THIS
    BEFORE CHANGING ANYTHING BELOW.**

    **PO ruling 2026-09-01, verbatim:** *"dont create new account - we reassing
    that account - bascailly I have sold my property - so account get transfer
    to new person or business; if I move to new location then it is new Service
    request and we follow the process"*.

    | | built until 2026-09-01 | ruled |
    |---|---|---|
    | what it does | `move_out` the account, `create_account` at a NEW unit | **reassigns the SAME account** |
    | what changes | the UNIT | the **CUSTOMER** |
    | what it is for | a customer moving | **a property being SOLD** |
    | a customer moving | this door | **a new Service Request** (`BR-CUS-1031`) |

    ⚠ **AND ONE CLOSED DEFECT DIED WITH `commit_transfer`, WHICH IS WHY ITS ID
    IS NOWHERE IN THIS FILE — `DEF-703`.** That row is a `fixed` row whose
    surface names `transfers.py :: commit_transfer, the opening payload`: a
    customer who transferred arrived with `account_type` set and
    `account_subtype` blank, and the fix made the opening payload carry the
    sub-type forward from the outgoing account. **There is no opening payload
    any more.** No account is created here, so there is nothing to copy a
    sub-type ONTO — the account keeps every column it had, sub-type included.
    A lane grepping for `DEF-703` in this file finds this paragraph and not a
    missing fix. **What that row asked for beyond its own fix is still open and
    is NOT this file's:** `DEF-257`'s prevention — that the required account
    shape be a property of every account-creating path rather than of the
    sample estate — was never done, and `services.create_account` is where it
    would live.

    **WHY IT IS NOT COSMETIC.** Reassigning keeps the account number, so the
    address keeps ONE CONTINUOUS LEDGER across a sale — which is what a utility
    means by *the account transferred*. Creating a new account splits that
    history in two and leaves the buyer's bills under a number the property has
    never had.

    ⚖️ **AND IT IS WHY THE DEBT-FOLLOWS-THE-PROPERTY RULING IS NEARLY FREE.**
    PO, the same day: *"money follow property - new owner boutght everything
    property + debt also"*. An account carries its own ledger, so **the balance
    never moves, because the thing it sits on never moves.** Had this door
    stayed as it was built, the ruling would have required lifting a balance off
    one account and posting it onto another — a debt transfer between two
    parties, needing its own money path, its own audit and probably its own
    consent.

    ⛔ **WHAT THIS DOES NOT LICENCE — CLAUDE.md HARD RULE 4, AND IT IS THE ONE
    WAY A LANE COULD STILL GET THIS WRONG.** No UPDATE and no DELETE on an
    issued invoice, invoice line, payment or journal entry. **Invoices already
    issued to the SELLER stay exactly as issued, in the seller's name, for
    ever** — a bill posted to a named person is a record of what was SENT, not a
    statement of who owes it today. The debt following the property is about the
    ACCOUNT's balance; it is not about rewriting history. A lane that reissues
    or re-addresses the seller's documents has broken a hard rule to implement a
    ruling that never asked for it. **This function writes to `customer_accounts`
    and to `transfers`, and to nothing else.**

    **WHAT IT WRITES, IN ORDER, IN ONE TRANSACTION:**

      1. the buyer's customer is RESOLVED through `services.link_customer` — the
         one function that writes `customer_accounts` (`BR-CUS-054`), and the
         one that performs `CR-058`'s governing ruling: match first, create only
         on no match, and only where an identifier is present. **This module
         matches nothing and creates nothing itself.**
      2. the SELLER's link is removed, so the account has exactly one customer.
         `customer_accounts` is an N:M link table and neither an invoice nor a
         payment nor a journal line — hard rule 4 does not reach it, and leaving
         both links would make *"who owns this account"* ambiguous on every
         read.
      3. `transfers` records the job: who it moved from, who it moved to, and
         the balance and deposit AS THEY STOOD at the moment of sale.

    **THE UNIT, THE ACCOUNT NUMBER, THE STATUS, THE SERVICE AGREEMENTS AND THE
    LEDGER ARE ALL UNTOUCHED.** No `move_out`, no `create_account`, no second
    account number, no closure. Every one of those is asserted in
    `tests/test_cr058_w4_transfer_reassigns.py` rather than promised here.

    ⚠ **AND THE BUYER MUST BE IDENTIFIABLE.** PO, the same day: *"Without
    identifier we cannot create Customer ID or master account ot regular
    account"*. A reassignment creates no account, so the letter of that rule
    does not reach it — but its point is that no account may exist with nobody
    identifiable behind it, and handing a live ledger to an unidentified party
    produces exactly that. Refused at step 2 and again here, because a
    service-layer caller does not have to pass through step 2.

    ════════════════════════════════════════════════════════════════════════
    TASK 17 — THE ONE-OWNER-PER-ADDRESS GUARD, SETTLED RATHER THAN WORKED AROUND
    ════════════════════════════════════════════════════════════════════════
    `CR-058` names it as a real obstacle: `BR-CUS-1011` refuses a second Master
    Account at an address, so *"the buyer's account would be refused while the
    seller's is still live"* — and the CR asks for it to be **settled as part of
    the sale, one act, both sides**, rather than worked around.

    **IT IS SETTLED BY TASK 14's DESIGN AND NOT BY A CHECK, AND THAT IS THE
    STRONGEST FORM THE SETTLEMENT CAN TAKE.** The guard fires on
    `create_master_account` — on CREATING a second account at an address that
    already has one. **This function creates no account.** There is one account
    at the address before the sale and the same one after it; what changes is
    the row in `customer_accounts`. So the obstacle does not arise, and it
    cannot be reintroduced without reintroducing the second account the ruling
    removed.

    ⚠ **THAT IS A CLAIM ABOUT THE CODE, SO IT IS ASSERTED RATHER THAN STATED**
    (hard-won law 1: a comment claiming a guarantee is not the guarantee).
    `test_cr058_w4__selling_a_premises_with_a_master_account_never_meets_the_
    one_owner_guard` sells an address that already carries a Master Account and
    asserts the account count at that premises is unchanged — which is the only
    thing that can prove the guard was never reached rather than merely not
    raised today.

    **A SECOND GUARD IS DISSOLVED THE SAME WAY, AND IT IS WORTH NAMING:**
    `BR-CUS-017` (one occupying account per unit) refused the incoming half of
    the old transfer whenever the target unit was taken. There is no incoming
    half and no target unit — the account never leaves the unit it is on — so a
    sale cannot collide with it either.
    """
    from apps.customers import selectors, services

    data = dict(payload or {})
    block = _validated_buyer(data.get("customer"))
    # ⊕ DEF-CUS-10255 — the buyer's own panels (image `07-transfer.png`),
    # proved BEFORE the transaction so a refusal leaves the clerk every field.
    extras = buyer_account_extras(data.get("buyer_account"))
    with transaction.atomic():
        transfer = _transfer_or_refuse(transfer_id, lock=True)
        _guard_open(transfer)
        missing = _missing_for_commit(transfer)
        if missing:
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-CUS-1030",
                message_key="customers.transfer.step_incomplete",
                params={"missing": missing, "reason": REFUSAL_STEP_INCOMPLETE},
            )
        # ⚠ **LOCKED, BECAUSE TWO SALES OF ONE PROPERTY IS THE RACE THIS
        # CANNOT LOSE.** `uq_transfers_open_from` allows ONE open transfer per
        # account, so two jobs cannot exist — but one job committed twice is
        # what `_transfer_or_refuse(lock=True)` above blocks, and this lock is
        # about the ACCOUNT: nothing else may close or re-link it between the
        # figures being read and the link being rewritten.
        account = selectors.account_or_404(transfer.from_account_id, lock=True)
        statement = _statement_for(account)
        # ⛔ **THE FIGURES AS THEY STOOD, READ BEFORE ANYTHING CHANGES.** This
        # is what the buyer took on, and it is the ONLY moment it can be
        # captured — a minute later it is just the account's balance.
        balance_at_sale = _money(account.balance, "the account balance")
        deposit_at_sale = _money(account.deposit_on_file, "the deposit on file")
        seller = transfer.customer
        # ⛔ **THE SELLER'S ADDRESS, READ HERE AND NOWHERE LATER — AND THE
        # ORDER IS THE WHOLE OF IT (`DEF-CUS-5949`).** `contacts` is keyed to
        # the ACCOUNT, and step 4 below (`_carry_buyer_onto_account`,
        # `BR-CUS-1081`) writes the BUYER's email and phone onto exactly that
        # row. A lane that read the contact after the commit would address the
        # seller's *"this account is no longer yours"* letter **to the person
        # who has just bought it** — which is not a failure anything would
        # report: there is a row, it is queued, it names an address, and the
        # address is wrong. So it is captured before anything moves, in the
        # same breath and for the same reason as the two money figures above.
        seller_reach = _contact_reach(account)

        # ── 0 · IS THE BUYER THE PERSON WHO ALREADY OWNS IT? ─────────────────
        # ⛔ **ASKED HERE, BEFORE ANYTHING IS RESOLVED — `DEF-CUS-5972`.** The
        # guard below (step 1) compares the customer id `link_customer`
        # RETURNS against the seller's, and `link_customer` can only return
        # the seller when the buyer presents a government-grade identifier
        # that matches: `identity_match.REUSE_ID_FIELDS` is `(ssn,
        # driving_licence)` for a person and `(tax_id)` for a company, and
        # `reuse_candidate` says so in as many words — *"A PHONE CANNOT REUSE,
        # THOUGH IT CAN CREATE."*
        #
        # **So with the one identifier this step's own help text offers — a
        # phone — the ids ALWAYS differ, the guard ALWAYS passes, and the sale
        # goes through: a SECOND customer number is minted for the same
        # person, the first one's link is deleted, and the number their
        # history hangs off is the one just unlinked.** That is hard-won law
        # 7's *structurally incapable of failing*, in production code rather
        # than in a check, and it stood for nineteen days because no case ever
        # asked the guard to fire.
        #
        # ⚠ **THE TEST IS EVIDENCE AGAINST *THIS ACCOUNT'S* CUSTOMERS AND
        # NOTHING WIDER.** It is not a duplicate check and it must not become
        # one: `BR-CUS-019` makes the duplicate check ADVISORY and `BR-CUS-1024`
        # deliberately lets a different returning person be minted a second
        # number. The question here is narrower and is the one the refusal is
        # named for — *are you selling to somebody who is already a customer of
        # this account?* — so the candidate set is the account's own links.
        already = _already_this_accounts_customer(account, block)
        if already is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-1030",
                message_key="customers.transfer.buyer_is_the_seller",
                params={
                    "account_no": account.account_no,
                    "reason": REFUSAL_BUYER_IS_THE_SELLER,
                    # B14 rule 31 — the NUMBER a person quotes, never the id.
                    "customer_no": already.customer_no,
                    "matched_on": identity_match.basis_sentence(
                        identity_match.agreed_facts(_buyer_evidence(block), already)
                    ),
                },
            )

        # ── 1 · the buyer's customer, resolved by the one function that may ──
        link = services.link_customer(
            account_id=account.id,
            display_name=block["display_name"],
            kind=block["kind"],
            # ⊕ **2026-09-20 — THE DATE OF BIRTH RIDES THE IDENTITY BLOCK.**
            # `identity_match.from_payload` reads `date_of_birth` off exactly
            # this dict, and it is the MIDDLE CLAUSE of `BR-CUS-089`'s
            # *name + date of birth + one government ID*. Without it the best a
            # sale could ever produce was a WEAK match, so a returning buyer's
            # **$150.00** deposit carried **$0.00** and they were minted a
            # second customer number beside the one they already had
            # (`DEF-2587`'s measured shape).
            identity={
                **block["identity"],
                **(
                    {"date_of_birth": block["date_of_birth"]}
                    if block.get("date_of_birth")
                    else {}
                ),
            },
            customer_id=block.get("customer_id"),
            external_ref=block.get("external_ref"),
            actor=actor,
        )
        # ⚠ **`id`, NOT `customer_id` — `link_customer`'s own key.** The
        # not-created branch returns the SAME shape with `id: None`, so this one
        # read distinguishes *"here is the buyer"* from *"nothing was minted"*.
        if not link or not link.get("id"):
            # ⚠ **REFUSED RATHER THAN HALF-DONE.** `link_customer` SKIPS rather
            # than raising when the minimum is not met (`BR-CUS-1023`: it must
            # not roll back an account somebody is opening). Here there is no
            # account being opened — the account already exists and is live —
            # so a skip would leave it with the SELLER's link removed and
            # nobody put in their place. The whole transaction unwinds instead.
            raise errors.BizError(
                errors.BIZ_COMPLETENESS,
                br_ref="BR-CUS-1030",
                message_key=identity_match.NOT_CREATED_MESSAGE_KEY[
                    (identity_match.MISSING_IDENTIFIER, block["kind"])
                ],
                params={"reason": REFUSAL_BUYER_NOT_IDENTIFIED},
            )
        buyer_id = link["id"]
        # ⚠ **KEPT, AND IT IS NOT A DUPLICATE OF STEP 0.** Step 0 asks about
        # EVIDENCE; this asks about the id `link_customer` actually resolved,
        # which is the case where the buyer presented a government-grade
        # identifier that MATCHED a customer this account has no link to yet
        # — a landlord selling to himself under a second name, say. Removing
        # it would trade one unfireable guard for another.
        if seller is not None and str(buyer_id) == str(seller.id):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-1030",
                message_key="customers.transfer.buyer_is_the_seller",
                params={
                    "account_no": account.account_no,
                    "reason": REFUSAL_BUYER_IS_THE_SELLER,
                },
            )

        # ── 2 · the seller stops being this account's customer ───────────────
        # ⚠ **`customer_accounts` IS A LINK TABLE, NOT ONE OF HARD RULE 4's
        # FOUR.** No invoice, invoice line, payment or journal entry is touched
        # by this delete, and every document the seller was ever sent still says
        # what it said. What changes is who the account belongs to FROM NOW ON.
        #
        # ⛔ **THIS DELETED THE LINK UNTIL 2026-09-20, AND THE DELETE WAS THE
        # DEFECT.** PO ruling of that day, verbatim: *"we cannot override
        # customer id - seller and buyer cstmer id are unique those does not
        # change"*. The row is now STAMPED rather than removed (migration
        # 0060): `ended_at` says when they stopped holding it and
        # `ended_by_transfer_id` says WHICH sale ended it — needed because an
        # account sold twice has two ended rows and a back-dated sale makes
        # the timestamps alone ambiguous.
        #
        # ⚠ **`update()` AND NOT A LOOP, DELIBERATELY.** One statement, so a
        # jointly-held account's several seller rows cannot be left half
        # stamped by an exception between two saves.
        #
        # ⚠ **`ended_at__isnull=True` IN THE FILTER IS NOT DECORATION** — it
        # keeps a SECOND sale of the same property from re-stamping the first
        # sale's seller with a later date, which would silently rewrite when
        # they stopped owning it.
        ended = models.CustomerAccount.objects.filter(
            tenant_id=account.tenant_id, account=account, ended_at__isnull=True
        ).exclude(customer_id=buyer_id)
        seller_ids = sorted(str(value) for value in ended.values_list("customer_id", flat=True))
        ended.update(ended_at=timezone.now(), ended_by_transfer_id=transfer.id)

        # ── 3 · the job, recorded ────────────────────────────────────────────
        # ⊕ **THE BUYER GETS A COLUMN; THE SELLER KEEPS `customer_id`.**
        # This line read `transfer.customer_id = buyer_id` until 2026-09-20 and
        # that overwrite was the other half of the same defect: the transfer
        # row forgot who sold the property at the instant it recorded the sale.
        #
        # ⚠ **THE SUITE STATES THE CONTRACT IN CODE, WHICH IS WHY IT SETTLED A
        # DESIGN THIS LANE FIRST GOT BACKWARDS.**
        # `test_transfer_scenarios._transfer_names_the_seller` asks
        # `Transfer.objects.filter(from_account_id=…, customer_id=seller_id)`
        # — so `customer_id` NAMES THE SELLER, permanently. A first draft of
        # this fix added a `seller_customer_id` column and kept the overwrite;
        # it would have shipped, left that check red, and made weakening the
        # check the obvious next move.
        transfer.buyer_customer_id = buyer_id
        # The SAME account on both sides, and that is the point of the row: a
        # reader asking *"what did this transfer do"* is told it moved one
        # account rather than made a second.
        transfer.to_account_id = account.id
        transfer.committed_at = timezone.now()
        # `DEF-CUS-9692` — the clerk who pressed commit, on the row.
        transfer.committed_by_id = _actor_user_id(actor)
        transfer.step = STEP_COUNT
        transfer.state = Transfer.STATE_DONE
        _touch(
            transfer,
            "buyer_customer_id",
            "to_account_id",
            "committed_at",
            "committed_by_id",
            "step",
            "state",
        )
        transfer.refresh_from_db()

        row = _serialize(transfer, statement)
        row["reassignment"] = {
            "account_id": str(account.id),
            "account_no": account.account_no,
            "from_customer_ids": seller_ids,
            "to_customer_id": str(buyer_id),
            "to_customer_name": block["display_name"],
            "sold_on": transfer.out_date.isoformat() if transfer.out_date else None,
            # ⚖️ What the buyer took on, at the moment they took it on. The
            # ruling says the debt follows the property; this is the figure
            # that followed.
            "balance_at_sale": _pair(balance_at_sale),
            "deposit_at_sale": _pair(deposit_at_sale),
            # Proof, in the audit row, that the four things `BR-CUS-1030`
            # forbids did not happen — asserted as facts rather than described.
            "unit_id": str(account.unit_id) if account.unit_id else None,
            "unit_changed": False,
            "account_number_changed": False,
            "account_closed": False,
            "accounts_created": 0,
            "journal_lines_written": 0,
            "refund_raised": False,
        }
        row["customer_match"] = link.get("match")
        # ── 4 · what the buyer carries, onto the tables that own it ──────────
        carried = _carry_buyer_onto_account(actor, account, block)
        row["buyer_carried"] = {
            "written": carried["written"],
            "not_written": carried["not_written"],
        }
        # ⊕ DEF-CUS-10255 — co-buyers, documents, Tax, Discounts, Preferences.
        row["buyer_extras"] = _carry_buyer_extras(
            actor, account, extras, sold_on=transfer.out_date
        )
        # ── 5 · the property's owner — ONLY for a MASTER account (T2) ────────
        # ⛔ **`PREMISES_OWNER_NOT_UPDATED` WAS STATED ON EVERY SALE UNTIL
        # 2026-09-23 (`DEF-CUS-6394`).** PO, verbatim: *"in case of master account -
        # not in case of regualr account - (a) The sale makes the buyer the
        # property's owner."* So a regular account's sale leaves the owner
        # exactly as it is — that is the ruling, not a gap, and nothing is
        # stated — and a master account's sale moves it THROUGH METERING's own
        # door (customers writes no metering table, B1).
        owner = _move_premises_owner(actor, account, block)
        row["premises_owner"] = owner["outcome"]
        row["unavailable"] = _unavailable_for(statement) + owner["gaps"] + carried["gaps"]
        _audit(actor, "transfer.reassigned", transfer.id, after=row)
        # ⚠ **THE FOUR FACTS THE MESSAGES NEED, NAMED INSIDE THE TRANSACTION
        # AND USED OUTSIDE IT.** `buyer_reach` in particular is read from the
        # BUYER BLOCK the clerk typed and NOT back off `contacts`: step 4 has
        # just written those values, but `update_account_contact` refuses an
        # account with no contact row and REPORTS rather than raising, so
        # re-reading the table would silently address the buyer's letter to
        # nobody on exactly the accounts that gap covers.
        sold_on = transfer.out_date
        buyer_name = block["display_name"]
        buyer_reach = _Reach(
            email=block["capture"].get("applicant_email") or None,
            phone=block["capture"].get("applicant_phone") or None,
        )
        # ⊕ 0068 — the NAME ON THE ACCOUNT, recorded at `start_transfer`, so a
        # seller with no customer row is still written to (`DEF-CUS-6387`).
        seller_name = transfer.seller_name or (
            seller.display_name if seller is not None else None
        )
    # ── CR-070 wave P · the changeover read (US-WRK-039, BR-WRK-055) ───────
    #
    # A property sale needs somebody to read the meter on the day it changes
    # hands, and until today this flow could not ask for one. The election comes
    # off STEP 2, *Final reads*, and the job stands on the SAME account — the PO
    # ruled on 2026-09-01 that a transfer reassigns the account rather than
    # creating one, so there is no second account for the job to belong to.
    #
    # ⚠ **AFTER THE COMMIT, and it is `BR-WRK-055` again.** The sale is
    # recorded, the buyer is linked and the account is theirs whether or not a
    # crew could be booked. A field module able to refuse a property transfer
    # would be this product telling somebody they may not sell their house.
    #
    # ⊕ **THE ONE FIELD-VISIT TABLE — `DEF-CUS-6392`, item 12, PO-approved
    # 2026-09-23 (*"this is correct"*).** The election is now the shared
    # `FieldVisitOrders` answer — rows a clerk ADDED (job type, priority, due,
    # assignee, note), or *No visit needed* — read through `_field_visit`
    # exactly as `_move_in` reads it. It was validated before the transaction
    # opened (`transfer_disconnect_api.transfer_commit`), so a row with no job
    # type never reaches this line. The published-template tick still rides
    # the same door for a client that sends it.
    election = services._field_visit(data.get("field_visit"))
    visit_asked = bool(election["template_ids"] or election["orders"])
    visit = services._raise_flow_work(
        actor,
        flow_kind="transfer",
        flow_id=transfer_id,
        template_ids=election["template_ids"],
        orders=election["orders"],
    )
    row["field_visit_declined"] = election["none"]
    row["work_orders"] = visit["work_orders"]
    if visit["warnings"]:
        row["unavailable"] = [*row.get("unavailable", []), *visit["warnings"]]
    # ── `DEF-CUS-5949` · the three messages the commit queues ──────────────
    #
    # ⛔ **UNTIL TODAY A COMMITTED SALE TOLD NOBODY IT HAD HAPPENED.** The PO's
    # own two words on this wizard were *"no commucation options"*:
    # `notifications_seam` published five account write names and not one of
    # them was a transfer, so a house changed hands in silence on both sides.
    #
    # ⚠ **QUEUED IS NOT SENT, AND THE RESPONSE SAYS SO IN EVERY ROW.** Measured
    # on the beta on 2026-09-20: **373 messages are queued in this product and
    # not one has ever been sent** — `sent_at` is null on every row, and
    # `BR-NOT-013` is why: there is no provider adapter on email, SMS or print.
    # `row["messages"]` is a list of QUEUE outcomes and a screen rendering it
    # as *sent* would be stating a delivery this product has never made.
    #
    # ⚠ **AFTER THE COMMIT, beside the work orders and for the same reason.** A
    # queue refusal must never unwind a property sale — the sentence
    # `_raise_flow_work` carries three lines up applies here word for word —
    # and the seam's savepoints are what make that true on PostgreSQL rather
    # than only on SQLite (hard-won law 14).
    row["messages"] = _queue_sale_messages(
        actor,
        transfer_id=transfer_id,
        account=account,
        sold_on=sold_on,
        buyer_customer_id=buyer_id,
        buyer_name=buyer_name,
        buyer_reach=buyer_reach,
        seller_ids=seller_ids,
        seller_name=seller_name,
        seller_reach=seller_reach,
        # The UTILITY's default language, never the account's (`OQ-CUS-12619`,
        # PO 2026-09-23: *"(a) Portal only; emails in English."*). It read
        # `account.preferred_language` until that ruling — which here was the
        # SELLER's preference being used to write to the buyer as well.
        language=seams.tenant_default_language(),
        # A text saying somebody is coming to read the meter is sent ONLY when
        # the clerk asked for a visit. *No visit needed* sends nothing.
        visit_asked=visit_asked,
    )
    return row


#: What a message can be addressed BY, on one channel each. A two-field tuple
#: rather than a dict so the two are read in one place and a caller cannot pass
#: a phone where an email belongs.
@dataclass(frozen=True)
class _Reach:
    email: str | None = None
    phone: str | None = None


def _contact_reach(account: Any) -> _Reach:
    """The account's primary contact, as an email and a phone.

    ⚠ **THE SAME ROW AND THE SAME ORDERING `selectors.primary_contact_name`
    READS** — `-is_primary`, then oldest — so the address a letter is queued to
    is the one the account screen shows as the contact. Two orderings would let
    a screen and an envelope disagree about who this account's person is, which
    is hard rule 8's reasoning applied to a contact instead of an address.
    """
    row = (
        models.Contact.objects.filter(
            tenant_id=account.tenant_id, account=account, deleted_at__isnull=True
        )
        .order_by("-is_primary", "created_at", "id")
        .first()
    )
    if row is None:
        return _Reach()
    return _Reach(email=(row.email or None), phone=(row.phone or None))


def _queue_sale_messages(
    actor: Any,
    *,
    transfer_id: Any,
    account: Any,
    sold_on: Any,
    buyer_customer_id: Any,
    buyer_name: str | None,
    buyer_reach: _Reach,
    seller_ids: list[str],
    seller_name: str | None,
    seller_reach: _Reach,
    language: str | None,
    visit_asked: bool = True,
) -> list[dict[str, Any]]:
    """The three the blueprint draws: two to the buyer, one to the seller.

    ⊕ **2026-09-23 (`DEF-CUS-5949`, `DEF-CUS-6387`).** Two changes, each a
    fact the review step now shows the clerk before they commit:

      * **the field-visit text goes only when a visit was asked for.** It says
        somebody is coming to read the meter; on *No visit needed* nobody is,
        so it is not queued at all rather than queued untrue;
      * **a seller with no customer row is still written to.** The letter is
        addressed by the name on the account (`transfers.seller_name`) and the
        email the account held before the sale, with no customer id in its
        snapshot — the seller exists even where no row did.

    ⚠ **THREE ROWS COME BACK WHATEVER HAPPENS, AND THAT IS `BR-BIL-036`.**
    *"An account with NO email address is normal, not an exception."* A party
    with no address still gets a queue row carrying `no_email_address` or
    `no_mobile_number`, because a message that was never queued leaves no trace
    and a clerk asking *"was the seller told?"* would get silence rather than
    *"we had nowhere to send it"*.

    ⚠ **THE SELLER'S LETTER IS SKIPPED ONLY WHEN THERE IS NO SELLER**, which is
    a transfer whose `customer_id` was never set — not a seller with no email.
    The two are different facts and only one of them is a missing row.

    ⛔ **`seller_ids` IS A LIST AND ONLY THE FIRST IS WRITTEN TO, WHICH IS A
    STATED LIMIT RATHER THAN A CHOICE MADE QUIETLY.** A jointly-held account
    has several `customer_accounts` rows and the sale ends all of them; one
    letter goes to the customer the transfer row NAMES (`transfers.customer_id`
    — the seller, permanently, since 2026-09-20). Writing to every joint holder
    needs an address per holder, and `contacts` holds one row per ACCOUNT, so
    there is nowhere to read the others from.

    ⚠ **THAT IS `OQ-CUS-12514`'s MIRROR AND IT IS CITED RATHER THAN RE-ASKED**
    (hard-won law 13). That row is open on where a SECOND PERSON on an account
    lives, and names this exact function: *"`reassign_account` deletes every
    link except the buyer's, so a joint purchase would need that rule stated
    rather than assumed"*. The answer that gives a joint BUYER a home is the
    same answer that gives a joint SELLER an address, so minting a second
    question would put two rows in front of the PO for one decision.
    """
    from apps.customers import notifications_seam

    account_no = account.account_no
    service_address = _service_address_for(account)
    queued: list[dict[str, Any]] = [
        notifications_seam.queue_transfer_to_buyer(
            transfer_id=transfer_id,
            account_id=account.id,
            account_no=account_no,
            buyer_customer_id=buyer_customer_id,
            buyer_name=buyer_name,
            buyer_email=buyer_reach.email,
            service_address=service_address,
            sold_on=sold_on,
            actor=actor,
            language=language,
        ),
    ]
    if visit_asked:
        queued.append(
            notifications_seam.queue_transfer_field_visit(
                transfer_id=transfer_id,
                account_id=account.id,
                account_no=account_no,
                buyer_customer_id=buyer_customer_id,
                buyer_name=buyer_name,
                buyer_phone=buyer_reach.phone,
                service_address=service_address,
                sold_on=sold_on,
                actor=actor,
                language=language,
            )
        )
    if seller_ids or seller_name:
        queued.append(
            notifications_seam.queue_transfer_to_seller(
                transfer_id=transfer_id,
                account_no=account_no,
                seller_customer_id=seller_ids[0] if seller_ids else None,
                seller_name=seller_name,
                seller_email=seller_reach.email,
                service_address=service_address,
                sold_on=sold_on,
                actor=actor,
                language=language,
            )
        )
    return queued


def _service_address_for(account: Any) -> str | None:
    """The account's service address, WALKED to the premises (hard rule 8).

    An address is stored on `premises` and nowhere else, and every other entity
    derives it by walking. `transfer_reads._premise` is customers' one reader
    for that walk, so this borrows it rather than formatting a second time — a
    second formatter would print one address two ways on two surfaces.
    """
    if account.unit_id is None:
        return None
    from apps.customers import transfer_reads

    return transfer_reads._premise(account.unit_id)


def _buyer_evidence(block: dict[str, Any]) -> Any:
    """The buyer block, as `identity_match` compares things.

    ⚠ **BUILT THROUGH `from_payload` RATHER THAN BY HAND**, so the sale asks
    its question in exactly the vocabulary the matcher answers in, and a field
    added to that vocabulary reaches this path without an edit here.
    """
    return identity_match.from_payload(
        {
            **block["identity"],
            "display_name": block["display_name"],
            **(
                {"date_of_birth": block["date_of_birth"]}
                if block.get("date_of_birth")
                else {}
            ),
        },
        kind=block["kind"],
    )


def _already_this_accounts_customer(account: Any, block: dict[str, Any]) -> Any:
    """The customer of THIS ACCOUNT the presented buyer already is, or None.

    ⛔ **`DEF-CUS-5972`'s whole fix, and the criterion is written here rather
    than inferred, because it is a judgment: NAME **plus at least one other
    comparable fact** that agrees.**

      * **A name alone is never enough.** `CR-056` §4 is a paragraph about
        exactly that — *"A. Kulkarni and Ajinkya Kulkarni are two landlords and
        nothing objects"* — and a sale refused because the buyer happens to
        share the seller's surname would be this product telling somebody they
        may not buy a house.
      * **An identifier alone is never enough either.** A household shares a
        telephone line; `link_customer` says so where it explains why a phone
        may create and may not reuse.
      * **Both together, against a customer THIS ACCOUNT ALREADY HAS, is the
        sentence the refusal is named for** — `buyer_is_already_this_accounts_
        customer`.

    ⚠ **IT IS DELIBERATELY WEAKER THAN `BR-CUS-089`'s `strong`, AND THAT IS
    THE POINT.** `strong` needs name + date of birth + one government ID and
    exists to decide whether MONEY MAY FOLLOW somebody. This decides whether to
    REFUSE AN ACT, which is recoverable in thirty seconds — the clerk is told
    which customer number matched and on what — where letting it through is
    not: the seller's link is deleted and a second customer number is minted
    for a person who already had one. Requiring `strong` here would have left
    the guard exactly as unfireable as it was, because a phone can never reach
    it. Recorded in the decision log of 2026-09-20.

    ⚠ **AND AN EXPLICIT `customer_id` SHORT-CIRCUITS IT.** A buyer block that
    names a customer this account is already linked to is the same refusal with
    no matching needed, and it is the case a screen can produce by picking the
    account's own customer out of a search result.
    """
    # ⛔ **`live()` AND NOT `objects` — `DEF-CUS-6046`'s MIRROR, AND IT REFUSES
    # A LAWFUL SALE RATHER THAN ALLOWING A WRONG ONE.** The question this guard
    # asks is *are you selling to somebody who is ALREADY this account's
    # customer* — a present-tense question. With the bare manager it also sees
    # the ENDED rows, so **a seller buying their own property back would be
    # refused** with `buyer_is_already_this_accounts_customer`, naming a link
    # that stopped being true the day they sold it.
    #
    # ⚠ **AND THAT IS THE EXACT CASE `customers/0060` WENT OUT OF ITS WAY TO
    # ALLOW:** its unique constraint was made PARTIAL (`WHERE ended_at IS
    # NULL`) so the database would permit a repurchase. A guard reading ended
    # rows would have taken that back one layer up, which is the quietest way
    # to undo a migration.
    #
    # `reassign_account` calls this BEFORE step 2 ends the seller's link, so
    # the live set still contains the seller and the guard this function is
    # named for still fires.
    linked = list(
        models.CustomerAccount.live(tenant_id=account.tenant_id, account=account).select_related(
            "customer"
        )
    )
    if not linked:
        return None
    named = str(block.get("customer_id") or "")
    evidence = _buyer_evidence(block)
    for row in linked:
        customer = row.customer
        if named and str(customer.id) == named:
            return customer
        agreed = identity_match.agreed_facts(evidence, customer)
        if identity_match.FACT_NAME in agreed and len(agreed) > 1:
            return customer
    return None


def _move_premises_owner(actor: Any, account: Any, block: dict[str, Any]) -> dict[str, Any]:
    """T2 — the property's owner, moved to the buyer ONLY for a MASTER account.

    PO ruling 2026-09-23, verbatim: *"in case of master account - not in case of
    regualr account - (a) The sale makes the buyer the property's owner."*
    (`DEF-CUS-6394`, `BR-CUS-1081`).

      * **a regular account** — `outcome.state = "unchanged"`, and NOTHING is
        stated as missing: the owner staying put is the ruling, not a gap;
      * **a master account** — metering's `transfer_premises_owner` moves it
        (customers writes no metering table, B1), and when metering could not
        (no typed owner to carry a category from — BR-MET-151 clause 3 forbids
        guessing one — or the door is unwired) the reason is STATED as
        `PREMISES_OWNER_NOT_MOVED`, never left for a clerk to infer.
    """
    from apps.customers import services

    is_master = getattr(account, "kind", None) == services.ACCOUNT_KIND_MASTER
    if not is_master or not getattr(account, "premises_id", None):
        return {"outcome": {"state": "unchanged", "is_master": bool(is_master)}, "gaps": []}
    answer = seams.transfer_premises_owner(
        actor,
        account.premises_id,
        account.id,
        {
            "name": block["display_name"],
            "email": block["capture"].get("applicant_email") or None,
            "phone": block["capture"].get("applicant_phone") or None,
        },
    )
    if answer and answer.get("moved"):
        return {
            "outcome": {
                "state": "moved",
                "is_master": True,
                "owner_id": answer.get("owner_id"),
                "reused": bool(answer.get("reused")),
            },
            "gaps": [],
        }
    reason = (answer or {}).get("reason") or "premises_owner_door_unwired"
    return {
        "outcome": {"state": "not_moved", "is_master": True, "reason": reason},
        "gaps": [{**PREMISES_OWNER_NOT_MOVED, "reason": reason}],
    }


def _carry_buyer_onto_account(actor: Any, account: Any, block: dict[str, Any]) -> dict[str, Any]:
    """The buyer's captured facts, written onto the tables that already own
    them — **and onto no new column anywhere.**

    ⛔ **NEW 2026-09-20 — `BR-CUS-1081`.** PO: *"all detaisl we need to create
    account - Similar to Move in request"*, and *"we have it - we have created
    it for service request move in - use it"*. The reuse is the point, so every
    write below goes through a door that was already built, already role-gated
    and already audited:

      | what | where it lands | the door |
      |---|---|---|
      | name · kind · SSN · licence · **date of birth** | `customers` | `services.link_customer` (above) |
      | email · phone · date of birth | `contacts` | `services.update_account_contact` |
      | preferred language | `accounts` | `services.update_account` |
      | mailing address | `customers.addresses` `kind='mailing'` | `services.update_account_mailing_address` |
      | a co-applicant | `contacts`, the NON-primary row | `services.set_account_co_applicant` |
      | KYC documents | `account_documents` `doc_type='kyc'` | `POST /accounts/{id}/documents` |

    ⚠ **THE ACCOUNT'S CONTACT WAS THE SELLER'S AND NOBODY WAS CHANGING IT.**
    `TransferWizard.tsx` says so on its own review step — *"Autopay and the bill
    email stay the seller's. Change them next."* — which is an accurate
    description of a product that hands a house over and goes on emailing the
    bill to the person who sold it. The wizard has been putting the buyer's
    email on the wire since the step was built and `_validated_buyer` dropped it
    (`DEF-CUS-5941`). It is written now, and **the seller's values are in the
    `before` half of the contact door's own audit row**, which is what makes a
    PII overwrite reviewable rather than silent.

    ⚠ **`update_account_contact` IS A CORRECTION PATH AND REFUSES AN ACCOUNT
    WITH NO CONTACT ROW** — *"minting a contact here would let a PATCH create a
    person, which the wizards own."* That refusal is right for a PATCH and would
    be wrong here: it would roll a whole sale back because an account nobody had
    ever put a contact on was sold. So the absence is CAUGHT and REPORTED rather
    than raised — the sale completes, and `contact_not_written` says why in the
    response. A buyer must not lose a house to a missing row.

    ⊕ **A CO-APPLICANT IS STORED — `DEF-CUS-6391`, PO 2026-09-23 (T4).** This
    paragraph read *"A CO-APPLICANT HAS NOWHERE TO GO AND THAT IS STATED, NOT
    DROPPED"*, with `co_applicant_not_stored` in the response, under
    `OQ-CUS-12514`. The PO answered it: *"a) Store a second person on the
    account (name, email, phone), shown on the account page"*. So it is the
    account's NON-primary `contacts` row, written through
    `services.set_account_co_applicant`, and the account page shows and edits
    it — which is what made the second row lawful: law 2's objection was a row
    no screen shows, and a screen shows it now.

    ⚠ **EVERY ONE OF THESE IS AUDITED BY THE DOOR IT GOES THROUGH** (hard rule
    7), so this function writes no audit row of its own. A second row about the
    same write would double-count every money action on this path.

    Returns what was written and what was not, for the response and for the
    review step. **It never returns a value that was captured** — only the names
    of the fields that moved.
    """
    from apps.customers import services

    written: list[str] = []
    unavailable: list[dict[str, Any]] = []
    captured = block["capture"]

    # ══════════════════════════════════════════════════════════════════════
    # ⛔ T3 — THE SELLER'S REACH ENDS AT THE SALE (PO ruling 2026-09-23,
    # `DEF-CUS-6393`). Verbatim: *"(a) At the sale, the seller's email, phone and
    # autopay are removed. The buyer's are used if given; otherwise bills go
    # by post to the service address."*
    # ══════════════════════════════════════════════════════════════════════
    # Until that ruling this function WROTE the buyer's email and phone only
    # when given and otherwise LEFT THE SELLER'S, stating the fact as
    # `contact_details_still_the_sellers` / `mailing_address_still_the_sellers`
    # — so every bill after a sale went on reaching the person who sold the
    # house. Both codes are RETIRED: the account's contact row is now the
    # buyer's whole, and what the buyer did not give is EMPTY rather than the
    # seller's.
    #
    # ⚠ **THE DATE OF BIRTH AND THE LAST FOUR GO WITH THEM, AND THAT IS A LANE
    # JUDGMENT RECORDED IN THE DECISION LOG (2026-09-23).** The ruling names
    # email, phone and autopay; the row it is about is `contacts`, which after
    # this write names the BUYER. A seller's date of birth or the last four of
    # the seller's government id left on a row naming somebody else is the
    # seller's PII filed under the buyer, which `BR-CUS-045` exists to prevent.
    contact_changes: dict[str, Any] = {
        "full_name": block["display_name"],
        "email": captured.get("applicant_email") or None,
        "phone": captured.get("applicant_phone") or None,
        # `contacts.dob` is a plain date and `customers.date_of_birth` is the
        # same fact one table over — `BR-CUS-1020` settled the type precisely
        # so the two are comparable. Both are written; neither is derived.
        "dob": block["date_of_birth"].isoformat() if block.get("date_of_birth") else None,
        "gov_id_last4": None,
    }
    # ⚠ **ASKED, NOT CAUGHT.** Catching the door's `NotFoundError` would
    # swallow a genuinely missing ACCOUNT as readily as a missing contact, and
    # a caught exception mid-transaction is hard-won law 14's trap on
    # PostgreSQL. So the question is asked first, in the same locked
    # transaction, and the answer decides.
    has_contact = models.Contact.objects.filter(
        tenant_id=account.tenant_id, account=account, deleted_at__isnull=True
    ).exists()
    if has_contact:
        services.update_account_contact(actor, account.id, contact_changes)
        written.append("contact")
    else:
        # The one gap that survives: an account nobody ever put a contact on.
        # The sale still completes — a buyer must not lose a property because a
        # row nobody created is missing.
        unavailable.append(CONTACT_NOT_WRITTEN)

    # ── the account's preferred language ────────────────────────────────────
    if captured.get("preferred_language"):
        services.update_account(
            actor, account.id, {"preferred_language": captured["preferred_language"]}
        )
        written.append("preferred_language")

    # ── where the bill goes — hard rule 8's one named exception ─────────────
    # The buyer's mailing address when given; otherwise the SELLER's row is
    # REMOVED, which is what *"otherwise bills go by post to the service
    # address"* means in this schema — no mailing row IS *same as service*
    # (B2 §2, and `update_account_mailing_address`'s own docstring: an empty
    # `line1` deletes the row).
    mailing = block.get("mailing_address")
    if mailing:
        services.update_account_mailing_address(actor, account.id, mailing)
        written.append("mailing_address")
    else:
        had_mailing = models.Address.objects.filter(
            tenant_id=account.tenant_id, account=account, kind="mailing", deleted_at__isnull=True
        ).exists()
        if had_mailing:
            services.update_account_mailing_address(actor, account.id, {"line1": ""})
            written.append("mailing_address_removed")

    # ── autopay — the seller's bank instruction stops at the sale ──────────
    # `accounts.autopay` IS the enrolment (`payments.autopay.is_enrolled` reads
    # it and nothing else), so switching it off is the whole removal; the
    # `cash_only_no_autopay` SANCTION is a different fact about the ACCOUNT
    # and is not touched.
    if account.autopay:
        services.update_account(actor, account.id, {"autopay": False})
        written.append("autopay_removed")

    # ══════════════════════════════════════════════════════════════════════
    # ⛔ T4 — A CO-APPLICANT IS STORED (PO ruling 2026-09-23, `DEF-CUS-6391`,
    # closing `OQ-CUS-12514`). Verbatim: *"a) Store a second person on the
    # account (name, email, phone), shown on the account page"*.
    # ══════════════════════════════════════════════════════════════════════
    # A second `contacts` row, `is_primary = false` — the table has always
    # allowed more than one row per account (no unique index on the account),
    # so no column is added. The seller's own second person, if the account
    # had one, goes with the seller: `set_account_co_applicant` REPLACES.
    co_applicant = {
        "full_name": captured.get("co_applicant_name") or "",
        "email": captured.get("co_applicant_email") or None,
        "phone": captured.get("co_applicant_phone") or None,
    }
    services.set_account_co_applicant(
        actor, account.id, co_applicant if co_applicant["full_name"] else None
    )
    if co_applicant["full_name"]:
        written.append("co_applicant")

    return {
        "written": sorted(written),
        # The CODES for the response's own summary, and the full stated-absence
        # DICTS for `unavailable`, which is where a clerk actually reads them.
        "not_written": sorted(gap["code"] for gap in unavailable),
        "gaps": unavailable,
    }


#: ⊕ **DEF-CUS-10255 — WHAT THE BUYER'S OWN PANELS SEND** (PO 2026-10-18,
#: decision log *"Same day … Billing-step sections"*: *"Transfer: Move-in's
#: Tax, Discounts and Preferences panels for the buyer: corect"*; image
#: `07-transfer.png` adds the co-buyer full card and the documents table).
#: Every key is the MOVE-IN's own, read by the move-in's own cleaners, so a
#: sale and a move-in cannot disagree about what a co-owner card or a tax
#: certificate is.
BUYER_ACCOUNT_KEYS: frozenset[str] = frozenset(
    {
        "co_owners",
        "documents",
        "tax_exemption",
        "discount_claims",
        "paperless",
        "sms_reminders",
        "autopay",
        "autopay_instrument_id",
    }
)


@dataclass
class BuyerAccountExtras:
    people: Any = None
    extras: Any = None
    account_values: dict[str, Any] | None = None


def buyer_account_extras(raw: Any) -> BuyerAccountExtras:
    """Validate the buyer's panels — shape only, before any write.

    Absent (`None`) is the old wizard's commit and changes nothing. Unknown
    keys are refused BY NAME (`DEF-632`'s lesson: a silently dropped field is a
    screen that says *saved* over a value that went nowhere).
    """
    from apps.customers import move_in_people, move_in_preferences

    if raw in (None, {}):
        return BuyerAccountExtras()
    if not isinstance(raw, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key="customers.payload_not_object")
    unknown = sorted(set(raw) - BUYER_ACCOUNT_KEYS)
    if unknown:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="customers.account.unknown_field",
            params={"field": f"buyer_account.{unknown[0]}"},
        )
    people = move_in_people.pop(
        {key: raw[key] for key in ("co_owners", "documents") if key in raw}
    )
    extras = move_in_preferences.clean(
        {
            key: raw[key]
            for key in ("tax_exemption", "discount_claims", "autopay", "autopay_instrument_id")
            if key in raw
        }
    )
    account_values = {
        key: bool(raw[key]) for key in ("paperless", "sms_reminders", "autopay") if key in raw
    }
    return BuyerAccountExtras(people=people, extras=extras, account_values=account_values)


def _carry_buyer_extras(
    actor: Any, account: Any, extras: BuyerAccountExtras, *, sold_on: date | None
) -> dict[str, Any]:
    """Write the buyer's panels onto the account just reassigned — through the
    MOVE-IN's own writers, inside the sale's transaction (a refusal unwinds it).

    ⚠ **THE SELLER'S CO-OWNERS LEAVE WITH THE SELLER.** A co-buyer card is
    the buyer's household, and the seller's spouse is nobody on the buyer's
    account — the same *reach ends at the sale* reasoning as T3 above. They are
    removed whenever the buyer's panels were sent at all; each removal is
    audited with the name (no identifier).

    ⚠ **THE SELLER'S TAX EXEMPTION AND DISCOUNTS ARE NOT COPIED** — the
    buyer's are entered on their own panels and written here. What happens to
    a seller's certificate or enrolment that is still on the account is NOT
    settled by this function: rating offers no door that ends a certificate at
    a date (only *revoke*, which says the claim never stood), and that gap is
    `DEF-CUS-10256`, reported rather than papered over.
    """
    from apps.customers import co_owner_models, move_in_people, move_in_preferences, services

    if extras.people is None and extras.extras is None and not extras.account_values:
        return {"sent": False}
    answer: dict[str, Any] = {"sent": True}
    if extras.account_values:
        services.update_account(actor, account.id, dict(extras.account_values))
        answer["account"] = sorted(extras.account_values)
    removed = 0
    for row in co_owner_models.AccountCoOwner.objects.filter(
        tenant_id=account.tenant_id, account=account
    ):
        core_audit.write_row(
            action="customers.account.co_owner_removed_at_sale",
            entity_type="account_co_owner",
            entity_id=row.pk,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            before={"account_id": str(account.pk), "full_name": row.full_name},
            after=None,
        )
        row.delete()
        removed += 1
    answer["seller_co_owners_removed"] = removed
    if extras.people is not None:
        answer["people"] = move_in_people.write_at_complete(
            actor, account_id=account.id, block=extras.people
        )
    if extras.extras is not None and not extras.extras.empty:
        opened = models.Account.objects.select_related("account_type").get(pk=account.pk)
        answer["billing"] = move_in_preferences.apply(actor, opened, extras.extras, on_day=sold_on)
    return answer


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def cancel_transfer(actor: Any, transfer_id: Any, payload: Any = None) -> dict[str, Any]:
    """Abandon a started job.

    It exists because `uq_transfers_open_from` allows ONE open transfer per
    outgoing account: without a cancel, a job started against the wrong account
    would block that account from ever being transferred again. A committed
    transfer cannot be cancelled — the accounts have already moved and hard rule
    4's posture applies: a correction is a new job, not an edit of this one.
    """
    data = dict(payload or {})
    with transaction.atomic():
        transfer = _transfer_or_refuse(transfer_id, lock=True)
        _guard_open(transfer)
        transfer.cancelled_at = timezone.now()
        transfer.state = Transfer.STATE_CANCELLED
        _touch(transfer, "cancelled_at", "state")
        row = _serialize(transfer)
        row["reason"] = data.get("reason")
        _audit(actor, "transfer.cancelled", transfer.id, after=row)
    return row


def _as_date(value: Any, field: str) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            # CR — key moved UP a level 2026-08-28 (lane DOORS). The sentence
            # ("{{field}} is not a date we can read.") names no workflow, and
            # `transfer_disconnect_api._required_date` serves BOTH the transfer
            # and the disconnect ladder through one helper. One sentence under
            # two keys is two places for one string to drift; a disconnect
            # clerk being told about a "transfer" is the other wrong answer.
            message_key="customers.date_not_iso",
            params={"field": field, "value": str(value)},
        ) from exc


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-004@HEAD · US-CUS-005@HEAD
#         (04-docs/02-decisions/18-cr030-onboarding-design.md §5.7 · §9 · W7
#          tasks 7.1/7.2/7.3 ·
#          04-docs/05-modules/03-customers/02-business-rules.md BR-CUS-015/017/
#          018/023/024/025/030/054/057/081/082/089/097 ·
#          04-docs/05-modules/04-metering/02-business-rules.md BR-MET-036 ·
#          12-governance/02-decision-log.md 2026-08-24 (nine rulings) and
#          2026-08-25 (four rulings on the deposit carry-forward))
# generated: 2026-08-25 by the CR-030 W7 transfers lane (S2)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
#         D: B18 §6.2's four transfer routes have no handler; `apps/customers/
#         api.py` is not in this lane's write scope and the shapes are REPORTED.
#         E: S89 is task 7.4, a frontend lane's.
# gates: see the lane report — measured, not claimed.
# exceptions: (1) ⛔ **AMENDED 2026-09-20 — THIS FILE NOW HAS A ROW.** It read
#         "NOT ON THE G7 GLOB LIST AND NO ROW IN 12-governance/09-human-review-
#         ledger.md", which was true from 2026-08-25 and stopped being true when
#         `BR-CUS-1081` gave this file customer-identity capture and a ledger row
#         was written for it. The GLOB LIST half still stands — enrolling a path
#         is a process event (B12 r2) — so what changed is the row, not the
#         glob. `discounts.py` and `move_out_settlement.py` still record the
#         original shape for themselves and are untouched.
#         (2) THE MODEL LIVES OUTSIDE `models.py` AND IS `managed = False`. One
#         line — `from apps.customers import transfers` (with a `noqa: F401`
#         comment, as rating's does) at the foot
#         of `apps/customers/models.py`, the shape `apps/rating/models.py:1628`
#         already uses — retires the whole arrangement. REPORTED.
#         (3) `to_unit_id` CARRIES NO FK. B2 §2 makes cross-module FKs the
#         REVIEWED interface set and this edge is not in it. Resolved through
#         `seams.unit_row` instead. REPORTED.
#         (4) NO BUSINESS-RULE ID EXISTS FOR THE EXCLUSION CONTRACT. B18 §11
#         names `BR-CUS-086` and no `02-business-rules.md` defines it — DEF-673's
#         shape, third instance. Not cited in the Trace header (G02 would fail
#         it, correctly); a register row is REPORTED as owed.
#         (5) NO OPEN QUESTION COVERS THE TRANSFER'S MONEY RULE. One is owed and
#         this lane may not mint it (prime directive). The question is written
#         out verbatim in §3 of the module docstring, with B18's own figures, so
#         whoever writes the row does not have to reconstruct it. No
#         `NotImplementedError` is raised, because there is no OQ id to name and
#         a stub citing a fabricated one is worse than a stated absence.
#         (6) SIX NEW `message_key`s ARE NAMED AND NOT SHIPPED:
#         `customers.transfer.money_not_a_decimal · .from_account_required ·
#         .from_account_has_no_customer (retired 2026-09-23, DEF-CUS-6387) ·
#         .not_an_occupant · .target_unit_required
#         · .target_is_the_same_unit · .target_unit_occupied · .dates_required ·
#         .in_date_before_out_date · .date_not_iso · .already_committed ·
#         .already_cancelled · .step_incomplete`. `07-frontend/src/i18n/locales/`
#         is outside this lane's write scope; the keys and their English are in
#         the lane report. G32 will count them until that fan-in lands.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
