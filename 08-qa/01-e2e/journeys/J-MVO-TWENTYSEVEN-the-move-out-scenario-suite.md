# J-MVO — twenty-seven move-out scenarios, one table, one command, two columns

---
id: JMVOTWENTYSEVEN
tier: 1
rules: [BR-CUS-021, BR-CUS-025, BR-CUS-030, BR-CUS-031, BR-CUS-050, BR-CUS-055,
        BR-CUS-056, BR-CUS-057, BR-CUS-080, BR-CUS-081, BR-CUS-082, BR-CUS-096,
        BR-CUS-097, BR-CUS-150, BR-CUS-151, BR-CUS-171, BR-CUS-1040,
        BR-BIL-004, BR-BIL-013, BR-MET-036, BR-MET-044, BR-MET-094,
        BR-MET-105a, BR-MET-107, BR-MET-128, BR-SHL-019, BR-SHL-025]
stories: [US-CUS-005, US-BIL-011, US-CUS-023, US-LED-001]
# ⚠ **THIS IS A COMMITMENT, NOT A DESIGN.** The Product Owner asked for it on
# 2026-09-19, verbatim: *"ensure you run end to end walk withmuitle scenarios -
# deposites, settlement, bill creation etc - update all premises, unit, plans ,
# asset and acunt status etc move the pending money to master account - create
# variosu cases and scenarios and do end to end walk to ensure clark is able to
# perform all these task from screen"*. It is written here rather than left in a
# chat window because a commitment that lives only in a conversation is the
# context leak hard-won law 10 exists to stop.
# ⚠ **ACTIVE.** It runs today and it is PARTLY RED on purpose; see *What red
# means* below.
---

> ⚠ **PAGE NUMBERS BELOW ARE THE 281-PAGE EDITION** of
> `05-prototype/02 Accounts Menu Blueprint.pdf`. The move-out wizard is
> **p110–p115**, the list and the record **p117–p118**. Read them AS IMAGES
> (B14 rule 42) — extracted text is an index, never the specification:
> `06-backend/.venv/bin/python 10-scripts/pdf/pdf_render.py "05-prototype/02 Accounts Menu Blueprint.pdf" <outdir> 3.2 110,111,112,113,114,115,117,118`

## The design requirement, borrowed from the move-in suite

> *"Otherwise scenario twelve gets a check that scenario three doesn't, and
> nobody notices."*

**So this is ONE TABLE THAT A RUNNER ITERATES, not twenty-seven hand-written
walks.** Every row declares its setup, its inputs and a verdict for **every one
of thirteen dimensions**. `declares()` refuses an incomplete row at IMPORT time,
so a half-declared scenario cannot be collected, run and counted as a pass over
checks nobody wrote. A row with nothing to say about a dimension says so in a
printed sentence — `Silent("why")` — rather than omitting the key.

The thirteen: **outcome · refusal_name · landing · settlement_money ·
deposit_interest · shortfall_path · books_and_payments · account_status ·
unit_after · final_reads · move_record · close_impact · friction.**

## ⚠ TWO SCORE COLUMNS, AND THE DIFFERENCE BETWEEN THEM IS A MEASUREMENT

`settlement_for` takes the final bill **from its caller**. Asked without one it
answers `landing: null` with `gaps: ["final_bill_not_stated"]` — fail closed,
correctly — step 4's four shortfall radios render live and every POST behind
them refuses with `no_shortfall`.

⚠ **THAT WAS EVERY ACCOUNT IN THE PRODUCT UNTIL 18:47 ON 2026-09-19, AND THIS
SUITE WAS BEING WRITTEN WHEN IT STOPPED BEING TRUE.** `1c69a87ab` landed
`billing.final_bill.preview_final_bill` — step 3's keystone, which calls the
SAME `prepare_final_bill` and the SAME `runs.price_account` the one-time
preview uses, derives the other end of the window through
`cut_bill.first_unbilled_day`, and issues nothing. **Build process step 0 —
*check the packet is current* — is what caught it, an hour after the fact, and
the suite was re-pointed at the product's own door rather than at a figure it
had stated for itself.**

So the two columns are the two settlements, and both are reachable today:

| column | what it asks | the question it answers |
|---|---|---|
| **NO BILL** | `settlement_for(actor, id)` | what a clerk gets when the preview cannot price the account — `preview_final_bill` genuinely refuses when the window cannot be derived |
| **WITH BILL** | `settlement_for(actor, id, final_bill=…, as_of=…)` | the wizard's own call, now that step 3 has a figure |

**A dimension that does not depend on the settlement answers identically in
both** — the account's status, the unit's landing, the readings, the move
record — which is why a row can be RED in one column and GREEN in the other
without any assertion being weakened. A row RED in **both** is a real gap and
the report says so by name.

⚠ **COMPLETE in a column means no failure AND nothing left unasserted.** A row
whose landing could not be asserted in a pass is not complete in it, however
many of its other checks passed. Counting it green would report a scenario as
working on the strength of the dimensions that are not what it is about —
hard-won law 7's *reporting zero over a scope it silently excludes*, in a
scoreboard.

Every row also carries `blocked_on`, and every red row prints it. The keystones
are `final_bill_preview`, `dispute_amount_store`, `supervisor_role`,
`move_out_draft_reference` and `wizard_sends_service_request_id`.

## Its relation to `J08`

`J08-final-bill-settlement-five-paths.md` is the DESIGN journey for the same
money: BR-BIL-013's five settlement paths over five accounts in one week, with
❄️ WE-7's `$150.00 + $3.50 = $153.50` anchoring it. **It is a description and
this is a program.** J08 says what the week should look like; this runs it, one
row per case, and prints what the product actually did. Where the two disagree,
J08's frozen figures win and this suite is wrong — the same rule J08 states
about itself and the golden tests.

## Bill creation, through the product's own door

The ORDER group does not state a figure at all: it calls
`preview_final_bill` and asserts what the product prices. p112's dashed panel
is the contract — ***NO BILL IS ISSUED BY THIS SCREEN*** — so O1 asserts
`issues_nothing` and the `books_and_payments` dimension counts invoices,
journal lines and payment rows on every row of the table to prove it.

## The twenty-seven

| group | rows | what they cover |
|---|---|---|
| **LANDING** | L1–L5 | p112's five landings — `settled`, `refund_due`, `short`, `refused_other_debt`, `refused_excess`. *"How the money lands is not a choice. It is one subtraction."* One scenario each, differing in ONE term. |
| **SHORTFALL** | SH1–SH4 | p113's four paths — collect with a forwarding address · a payment plan · **transfer it to the master account** (the PO's own sentence) · write it off. SH4 runs as a BILLING CLERK, because p113's `WHO CAN` column says *A supervisor* for that one path alone. |
| **DEPOSIT** | D1–D5 | none held · covers exactly · covers with excess · falls short · **❄️ WE-7's `$150.00` at 2% for fourteen months = `$3.50`**. |
| **READS** | R1–R4 | p111's three answers — taken · estimated · still due — and a unit with **no meter at all**, which is one of the three honest reasons `accounts.final_read_state` is NULL. |
| **CONSEQUENCE** | C1–C3 | the clerk's step-5 standby dropdown, **both ways**, with its BR-MET-094 money consequence · and p114's *"a move-out removes nothing"*: the plan stays and the meters stay. |
| **ORDER** | O1–O2 | the same account walked bill-then-close and close-then-bill. The second is refused `account_already_closed_for_billing` and **nothing in the product enforces the order**. ⚠ **AMENDED 2026-10-13 (`DEF-CUS-10093`, PO option B): the move-out now ENFORCES it** — Complete drafts the final bill before it writes the close, and refuses to close when the draft cannot be made. Close-then-bill is still refused for any bill except the move-out's own final draft, which may be sent after the close. Walk: `05-prototype/move-out-final-bill-2026-10-13/README.md`. |
| **PROCESS** | P1 | save & exit mid-wizard → find it again → **Resume** from the record → finish. Three PO rulings of 2026-09-19 make that path. |
| **EDGE** | E1–E3 | a master with open sub-accounts (BR-CUS-171) · one dated behind an issued bill (BR-BIL-004) · one raised from a service request. |

## How to run it

    ./10-scripts/move_out_scenarios.sh                # all 27, both columns
    ./10-scripts/move_out_scenarios.sh --prove-red    # break two, show red, restore
    ./10-scripts/move_out_scenarios.sh L3 SH3         # named scenarios only

The suite itself is `06-backend/tests/test_move_out_scenarios.py`, run under
`--ds=config.settings.pgtest --reuse-db` with `JOBS_EAGER=false`.

⚠ **Use `06-backend/.venv/bin/python`.** Nothing on `PATH` in this container can
import Django (`DEF-GOV-4299`).

## What red means

**This walk is written against what the blueprint and the signed rules PROMISE,
not against what the product does today**, so it is a to-do list that runs:
every red row names something that is not built, and its `blocked_on` says what
it is waiting for. **An assertion is never weakened to reach green.** Moving a
row needs a ruling behind it, written down first.

## Proving it can fail — hard-won law 7

A suite first seen green is a suite nobody has proved.
`MOVE_OUT_BREAK=<id>:<dimension>` corrupts what the runner **OBSERVED** for one
dimension before the checkers see it — not what the row declared — so what it
proves is that the checker really reads PostgreSQL's answer and compares it,
which inverting a verdict would not. `--prove-red` breaks **two different
checkers** (`_subset`, which compares a declared dict against a table read, and
`check_move_record`, which has logic of its own), shows each red on its own row
and nothing else, and then shows the same rows green again.

## Safety — and why the beta is never opened

**A move-out COMMITS.** It closes an account, ends every open service agreement,
writes readings through metering's event door and writes a permanent
`move_records` row. Readings are append-only and payments and journal lines are
under CLAUDE.md hard rule 4 — thirteen triggers refuse a DELETE outright.
**There is no undo.**

So the throwaway utility is a whole PostgreSQL **database** and not a tenant
inside the live one: `config.settings.pgtest` puts the run on
`test_sbh_<checkout>_<digest>`, each scenario provisions its OWN tenant through
the real signup path, and `django_db` rolls the whole graph back. The runner
counts the beta's accounts, move records, payments, journal lines, invoices and
parked drafts **before and after** anyway — a claim nobody has checked is not a
safety guarantee (hard-won law 1).

## Law 14 — why this runs on PostgreSQL and not on the default suite

`config/settings/test.py` hardcodes in-memory SQLite, which has **no
aborted-transaction state**, so code that catches a database error and continues
passes the whole suite green and loses the work at COMMIT the first time a real
row is refused. A move-out is one transaction (`BR-SHL-019`) carrying a reading
commit, a status change, service-agreement ends, an audit row, a move record and
a queued message — exactly the shape that trap hides in. Every figure in this
suite is read back from real PostgreSQL.

## What it found — 2026-09-19, the first run

**Twenty-seven scenarios, fifty-four passes.** With the final bill stated —
the wizard's own path since `1c69a87ab` landed at 18:47 — **sixteen are complete
and eleven are red.** With no bill stated, **one** is complete, which is the
measurement rather than a complaint: the settlement is built to fail closed and
does.

**Five of the eleven are real gaps waiting on nothing.** The other six are one
missing store and two missing wires, and each says which.

### 2026-09-20 · the second run — `E1` closes, and nothing else moved

**`E1` is GREEN 7/7 in both columns** (`BR-CUS-1082`, `DEF-CUS-5930`,
`v2.314.2`): a master account with two open sub-accounts is refused before any
write, so no status changes, no agreement ends and no `move_records` row is
allocated. The two numbers move **16 → 17 complete with the bill stated** and
**1 → 2 with none**.

⚠ **AND THE ROW-BY-ROW DIFF IS THE CHECK, NOT THE TOTALS.** Two totals can hold
still while two rows swap places, so both tables were compared line by line:
**exactly one of the twenty-seven lines differs and it is `E1`**; the other
twenty-six are byte-identical in both columns. The beta was counted before and
after both runs and is unchanged — 78 accounts · 2 move records · 74 payments ·
751 journal lines · 92 invoices · 1 parked draft.

### 2026-09-20 · the third run — `E1` REVERSES, and the score is measured not assumed

**`E1` no longer asserts a refusal, because there is no longer a refusal to
assert.** PO ruling of the same day closed `OQ-CUS-12515` on option (b) —
verbatim, *"option B - give a warning and allow it; if owner has sold the
property to new owner then we are transfering all libalities and ownership to
new owner"* — so a master account with open sub-accounts now **COMMITS**, and
what the row pins is that the clerk is TOLD. The row was **rewritten, never
deleted**: the contract it guards is still real and a row that vanishes takes
its coverage with it.

**What `E1` declares now:** `outcome=committed` · `account_status=CLOSED` · a
real `move_record` (it was `None`) · and, under `settlement_money`, the warning
**by its code and by its count** —
`open_sub_accounts_warning: master_closed_over_open_sub_accounts` and
`open_sub_accounts_warned_count: 2` beside the settlement's own
`open_sub_accounts: 2`. `refusal_name` becomes a declared `Silent` with its
reason, because nothing refuses.

⚠ **THE TWO NUMBERS WERE RE-MEASURED RATHER THAN CARRIED FORWARD, AND THEY HAD
MOVED ON THEIR OWN.** The brief this lane was given said the suite stood at
*18 of 27*; at the tip it actually measured **20 of 27 complete WITH the bill
stated** and **5 of 27 with none**, because other lanes had landed work in
between. **A score quoted from a document is a claim about the past** — the
before column here is a run of this suite at `64a4299c0`, not a number copied
out of the section above.

⚠ **AND THE ROW-BY-ROW DIFF IS THE CHECK, NOT THE TOTALS**, for the reason the
run above already gives: two totals can hold still while two rows swap places.

### The real gaps — red in BOTH columns, waiting on nothing

| row | what a clerk would see |
|---|---|
| **`DEF-CUS-5930`** · E1 | ⚠⚠ **FIXED 2026-09-20 in `v2.314.2`, THEN THE FIX ITSELF WAS REVERSED THE SAME DAY IN `v2.317.0` — PO ruling, `OQ-CUS-12515` option (b): the move-out is WARNED, not refused. Read `BR-CUS-1082` for the live rule; everything below describes the defect and the refusal that briefly answered it, and is kept for its correction.** **A master account with two open sub-accounts moved out.** `settlement_for` SERVES `open_sub_accounts` and `services.move_out` never read it: the account closed, its agreements ended and a numbered `move_records` row was written. `services.move_out` now refuses before any write, and step 1 of the wizard refuses too, both reading the ONE count `selectors.sub_accounts_for_master` answers. ⚠⚠ **AND THE RULE NAMED ABOVE WAS THE WRONG ONE — `DEF-CUS-5950`.** This row said *"BR-CUS-171, 'a parent with open children cannot be moved out' … a move the SIGNED rule forbids"*. `BR-CUS-171` signs the parent/child LINK and carries no move-out clause; the sentence is `B19 §15.8`'s, which says of itself *"THIS IS NOT IN ANY SIGNED RULE … It needs ratifying before W5 builds step 1."* The refusal now lives on its own row, **`BR-CUS-1082`**, marked a LANE JUDGMENT with **`OQ-CUS-12515`** open for the ratification. |
| **`DEF-CUS-5931`** · O1 | **Step 3 prices the last month from reads step 6 has not written.** p111 states it itself — *"The reads are committed with the close, not before it"* — so on step 3 the closing register does not exist and `resolution.MeterMultiplierUnstated` refuses: `BR-MET-056` stores the factor USED and *an absent factor is NOT 1*. The order the wizard uses and the order billing needs are not the same order. |
| **`DEF-CUS-5922`** · P1 | ⚠ **FILED BY A SIBLING THE SAME EVENING AND CITED RATHER THAN RE-FILED** — they found it from the other end, an unexecuted backend case that can never pass. **A parked move-out cannot be opened from its own record.** `wizard_parks._allocate_draft_reference` allocates for `move_in` and for nothing else, so a move-out draft carries NO reference — and `/moves/{ref}` is keyed on the reference. The `Resume` action the PO asked for on 2026-09-19 cannot be reached for a move-out at all, `_in_flight` reads `moved_in_on`/`effective_on` and never `moved_out_on` so the date does not show, and `move_outs_list`'s window is CLOSED ACCOUNTS so an unfinished move-out is in no list. |
| **`DEF-CUS-5933`** · R2 | **An estimated final read is committed and the record files it under nought.** `commit_event_reads` returns `posted_reads = len(posted)` and puts an estimate in a SEPARATE `estimates` list, so `reads_committed` counts none — while `accounts.final_read_state` reads `estimated`, which can only be true if a committed head EXISTS. One move-out, two answers about one row. |
| **`DEF-CUS-5932`** · O2 | **The sentence that explains the order is unreachable.** `prepare_final_bill` calls `gather_single` and only THEN reads `data.behavior_class`, so a closed account fails plan resolution first: what a clerk gets is *no plan version in force on 2026-01-28* (`BR-RAT-007`), not the carefully written *"the final bill therefore has to be produced BEFORE the move-out writes the close"*. The product knows why they are stuck and tells them something else. |
| **`DEF-CUS-5908`'s shape** · SH4 | **`Write it off` is taken by a billing clerk.** p113's `WHO CAN` column says *A supervisor* for that path and *Any clerk* for the other three. `shortfall_decision` is `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` with no per-path qualification, `shortfall_path_options` declares no `who_can`, so a screen cannot grey the radio — and `core.permissions` holds three roles, none of them a supervisor. It is `DEF-CUS-5908`'s shape on the way out. |

### ⚠ THE GREEN `SH` ROWS DO NOT MEAN A CLERK CAN DO IT — `DEF-CUS-5927`

**Read this before reading SH1, SH2 and SH3 as working.** Those rows record a
shortfall decision because **this suite passes the final bill to
`shortfall_decision`**. The wizard does not. A browser walk on 2026-09-19
confirmed it end to end, and it is worse than a missing argument: **the READ
learns the figure and the WRITE is never given it**, so step 4 renders three
live radios over a `409 customers.move_out.no_shortfall` and the screen prints
*"there is no shortfall to decide"* directly beneath its own `SHORT BY
$1,591.85`.

`e00b5dca6` and **`DEF-CUS-5929`** settled which half is at fault —
that row exists because `DEF-CUS-5927`'s browser evidence is right and its
stated CAUSE is not: `shortfall_decision` already reads
`final_bill` off the payload and `api._settlement_payload` already parses it, so
**no backend change is needed** — what reaches the endpoint today is `{path}`
alone. The remaining work is that the step-4 POST must carry `final_bill` and
`as_of`, the same two values step 3's preview already produced and the
close-impact read already sends.

### The other wire

**`E3`** — the backend links a move-out to the service request it fulfils
(`moves.record_move` stores `request_id`, and the record dimension PASSES), and
`MoveOutWizard.tsx` names no such field, so on the product a clerk uses the link
can never be made. Hard-won law 2 exactly: built, not wired.

### Red only in WITH BILL — the excess landings, all one cause

**L2, L4, L5 and D3 gap on `open_disputes_not_readable`.** Nothing in this
product stores a disputed AMOUNT — no model, no `db_table`, no seam, no
publisher — so `_open_dispute_total` answers None and **every credit-direction
close in the product states no landing.** Three of the five landings p112 draws
as *"one arithmetic"* are therefore unreachable, and `refused_excess` cannot be
reached at all. ⚠ `metering`'s `disputed_at` on a meter read is NOT this: that
is a quantity in dispute and BR-CUS-096 conditions on an amount, so wiring it
would hold a refund because somebody queried a dial.

### What the product now answers that the drawing says it cannot

p115 names **six consequences the product cannot yet state**. Measured on every
row: **four are SERVED** — premises occupancy afterwards, the owner on record,
the vacant-charge position and the master-account effect — and **two are
stated ABSENT**: payment-plan progress and what happens to the assets. No
consequence was DEFAULTED on any row, which is the check that matters: *a blank
consequence and a harmless one look identical once a screen guesses.*

### The friction list

Every item is derived from the PAYLOAD and the DATABASE, because this suite
never opens a screen.

* **The step-5 standby dropdown has no door of its own.** The PO ruled on
  2026-09-19 that the clerk chooses what the unit becomes; `PATCH /units/{id}`
  refuses `vacant_standby_auto` BY NAME and the only writer is the ASSIGN-PLAN
  door. So making that choice re-assigns the unit's plan, warns
  `unit_plan_override_on_occupied_unit` and writes a dated plan-history row for
  a decision that is not about the plan. It is a money decision (BR-MET-094 —
  whether the owner pays the base charge while the unit stands empty).
* **p113 asks for four things no door accepts:** a FORWARDING ADDRESS on the
  collect path, INSTALMENTS · FIRST PAYMENT DATE · AMOUNT EACH · THE CUSTOMER'S
  AGREEMENT on the payment plan, and A REASON on the write-off. A debt can be
  made to stop existing with nothing recorded about why.
* **`DEF-CUS-5927`, from the other side.** The SERVICE takes a final bill on the
  shortfall decision and the SCREEN does not send one. This suite passes it,
  which is the only reason SH1–SH3 record a decision at all; a clerk on the
  wizard gets a 409 on every path, over three radios the same screen has just
  drawn enabled.
* **An account closes with a reading still outstanding** and nothing in the
  close raises the work of going to take it.

## What this walk CANNOT see

Five things, each printed on every run rather than left out:

1. **Whether a clerk can do any of it on a SCREEN.** This suite drives the
   services the six steps post to. It never opens a browser, so it cannot see a
   radio that renders disabled, a figure that renders as a dash, or a
   `Save & exit` that loses what was typed. Hard-won law 6 — diff the running
   app against the drawing — is the other half, and no gate in this repository
   performs it. Two rows reach into the front end for one fact each and say so.
2. **The refund reaching the customer.** `refund_disposition` records a decision
   and moves no money.
3. **What the customer is told.** p114 states the cost itself: *"Queued is not
   sent. Rows are written and no sender picks them up."*
4. **The move-out REASON.** p110: *"Five options are named on screen and none of
   them is stored."* There is nothing to read back.
5. **BR-CUS-096's held excess on a real dispute.** Nothing in this product
   stores a disputed AMOUNT, so `refused_excess` is not merely unreached — it is
   unreachable, and every excess landing gaps because of it.
