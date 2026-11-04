# J-TRF — twenty-five property-sale scenarios, one table, one command, two columns

---
id: JTRFTWENTYFIVE
tier: 1
rules: [BR-CUS-015, BR-CUS-017, BR-CUS-023, BR-CUS-054, BR-CUS-057, BR-CUS-080,
        BR-CUS-085, BR-CUS-089, BR-CUS-1011, BR-CUS-1022, BR-CUS-1023,
        BR-CUS-1024, BR-CUS-1030, BR-CUS-1031, BR-MET-036, BR-MET-044,
        BR-MET-1161, BR-SHL-019, BR-SHL-025, BR-SHL-048, BR-WRK-055]
stories: [US-CUS-004, US-CUS-005, US-CUS-027, US-LED-001]
# ⚠ **THIS IS A COMMITMENT, NOT A DESIGN.** The Product Owner asked for it on
# 2026-09-20, verbatim: *"once you are done with changes for tranfer - do the end
# to end walk - create request , see all transfer work corectly - property,
# address, assets, units - occupancy is updated at unit . assets whow correct
# account - money part is correct, email, communcation is send"*. It is written
# here rather than left in a chat window because a commitment that lives only in
# a conversation is the context leak hard-won law 10 exists to stop.
# ⚠ **ACTIVE.** It runs today and it is PARTLY RED on purpose; see *What red
# means* below.
---

> **Read the drawing, not this file, for what a screen should look like:**
> `04-docs/05-modules/03-customers/blueprint/11-transfer-wizard.md`, extracted
> from `05-prototype/02 Accounts Menu Blueprint.pdf` p124–p133. Read the PDF
> **as images** (B14 rule 42) — extracted text is an index, never the
> specification:
> `06-backend/.venv/bin/python 10-scripts/pdf/pdf_render.py "05-prototype/02 Accounts Menu Blueprint.pdf" <outdir> 3.2 124,125,126,127,128,129,130,131,132,133`

## ⚠ WHAT A TRANSFER IS, BECAUSE HALF THE PRODUCT STILL SAYS OTHERWISE

`BR-CUS-1030`, PO 2026-09-01, verbatim:

> *"dont create new account - we reassing that account - bascailly I have sold
> my property - so account get transfer to new person or business; if I move to
> new location then it is new Service request and we follow the process"*

**ONE ACCOUNT. NEVER CLOSED. SAME UNIT. SAME METERS. ONE UNBROKEN LEDGER. THE
CUSTOMER CHANGES.**

The service and the wizard both moved to that on 2026-09-01. **The Transfers tab
did not** — the commit that rewrote `transfers.py` by 916 lines touched
`TransfersTab.tsx` by 38, all of them one sentence and a link — and the
blueprint's own banner still describes the old job. So a lane repairing a screen
could reasonably conclude the SERVICE was the stale half.
`test_a_transfer_is_a_reassignment_and_this_file_would_notice_if_it_stopped_being_one`
is the one place that says, in five assertions, which half is current.

### Two of the PO's checks need care rather than literal reading

| The PO asked | What the suite asserts, and why |
|---|---|
| *"occupancy is updated at unit"* | **UNCHANGED.** The unit does not change hands; the ACCOUNT does. `BR-MET-036` derives occupancy from the occupying account and that is the same row before and after, so `occupancy: occupied` with the same `account_no` is the right answer. A suite that asserted a CHANGE would be asserting the job the ruling deleted. ⚠ What SHOULD move is the NAME beside it — see the finding below. |
| *"assets show correct account"* | **The account number does not change**, so an asset still pointing at `A-…` is right. The question worth asking is whether anything about an asset wrongly names the old CUSTOMER, and `assets_and_account` asks exactly that. |

## The design requirement, borrowed from the move-out and move-in suites

> *"Otherwise scenario twelve gets a check that scenario three doesn't, and
> nobody notices."*

**So this is ONE TABLE THAT A RUNNER ITERATES, not twenty-five hand-written
walks.** Every row declares its setup, its inputs and a verdict for **every one
of thirteen dimensions**. `declares()` refuses an incomplete row at IMPORT time,
so a half-declared scenario cannot be collected, run and counted as a pass over
checks nobody wrote. A row with nothing to say about a dimension says so in a
printed sentence — `Silent("why")` — rather than omitting the key.

The thirteen: **outcome · refusal_name · property_and_address ·
assets_and_account · occupancy_at_unit · money · books_and_payments · unchanged ·
identity · communication · transfer_record · lists_and_counting · friction.**

They map onto the PO's own sentence one for one, which is why there are thirteen
rather than some tidier number:

| The PO's words | The dimension |
|---|---|
| *"create request"* | `outcome` · `transfer_record` |
| *"property, address, … units"* | `property_and_address` |
| *"assets"* · *"assets show correct account"* | `assets_and_account` |
| *"occupancy is updated at unit"* | `occupancy_at_unit` |
| *"money part is correct"* | `money` · `books_and_payments` |
| *"email, communcation is send"* | `communication` |

and the four that are nobody's sentence but every rule's — `refusal_name`,
`unchanged`, `identity`, `lists_and_counting` — are the ones `BR-CUS-1030` makes
load-bearing.

## ⚠ TWO SCORE COLUMNS, AND THEY ARE A SCORING VIEW OVER **ONE** RUN

The move-out suite ran every row TWICE because `settlement_for` takes the final
bill **from its caller**, so *asked with a bill* and *asked without one* are two
genuinely different questions about one customer's money. **A sale takes no such
argument.** Running each row twice here would run the same walk twice and report
the same answer twice, so this suite runs each row ONCE and scores it in two
columns:

| column | what it counts | the question it answers |
|---|---|---|
| **TODAY** | every check whose declaration names no keystone | what is broken NOW, with nothing in flight excusing it |
| **WHEN THE LANES LAND** | every check, keystone or not | what SHOULD pass once the five in-flight keystones land |

⚠ **NOTHING IS SUPPRESSED IN EITHER COLUMN.** Every declared check RUNS on every
row, always; the columns differ only in how a **failure** is counted. That is
deliberately stronger than skipping the check in one pass: **a keystoned check
that PASSES counts as a pass in BOTH columns**, so the day a keystone lands the
report says so by itself instead of waiting for somebody to re-read the table.

⚠ **AND THE KEYSTONE IS PER KEY, NOT PER CHECK.** `identity` holds seven facts
and only two of them wait on the 2026-09-20 ruling. Scoring the whole dimension
as WAITING would hide that the other five already pass; scoring it as FAIL would
put a ruling in flight in the same bucket as a real gap. Both are the mistake the
two columns exist to prevent.

⚠ **COMPLETE in a column means no failure AND nothing left unasserted.** A row
with a check still WAITING is not complete TODAY, however many of its other
checks passed.

## The five keystones

| keystone | what it is |
|---|---|
| `seller_link_ended_not_deleted` | PO ruling 2026-09-20, *"we cannot override customer id - seller and buyer cstmer id are unique those does not change"*. Today `reassign_account` DELETES the seller's `customer_accounts` row and overwrites `transfers.customer_id`, so the seller survives only in `audit_log`, **which is pruned**. |
| `premises_units_meters_assets_on_step_3` | PO ruling 2026-09-20, *"Premises, Units, Meters, Assets, these detaisla re not shown"*. A clerk is asked to sell a property they cannot see. ⚠ **Step 3 only** — the same sitting said it of step 1 too and the PO reversed that half hours later, *"not required - displayed on next step 3"*, because one set of facts in one place is the point. |
| `transfer_message_kind` | PO 2026-09-20, *"no commucation options"*, filed as **`DEF-CUS-5949`**. `notifications_seam` publishes five account message kinds and not one is a transfer, so a sale tells nobody anything. |
| `move_outs_exclusion_rewritten_for_the_sale` | `DEF-CUS-5913`. `transfer_half_account_ids()` names every non-cancelled transfer's `from_account_id` forever and `move_outs_queryset` subtracts it. |
| `transfer_record_page_and_read` | There is no `GET /transfers/{id}` and no record page at any address: a clerk can make a sale and has no way to read it back. |

## The twenty-five

| group | rows | what they cover |
|---|---|---|
| **SALE** | SL1–SL4 | who is buying, and on what evidence — a new person · a COMPANY matched on its Tax ID · a returning PERSON (who gets a second number, and that IS `BR-CUS-1024`) · a buyer with a **phone and nothing else**, which is `BR-CUS-1023`'s weakest lawful identifier. |
| **MONEY** | MN1–MN4 | arrears and no deposit · a deposit and no arrears · **neither** · a deposit whose INTEREST cannot be read. **The two zeros are the point on every one of them.** |
| **PROPERTY** | PR1–PR3 | two meters · a unit with **no meter at all** · a neighbour at the same address, untouched, both walking to ONE premises (hard rule 8). |
| **REFUSAL** | RF1–RF5 | no identifier · selling to the current owner · **one sale at a time** · an account already closed · an account with nobody on file, whose refusal must name the FIX. |
| **DOOR** | DR1–DR2 | the wizard's ONE POST end to end · and the same POST refused, with **zero rows surviving** — `transfer_commit`'s own claim about itself, proved on PostgreSQL because law 14 says a rollback claim that passes on SQLite says nothing. |
| **PROCESS** | PC1 | Save & exit → the parked list → **Resume** → finish. |
| **COUNTING** | CT1–CT2 | `DEF-CUS-5913`, sold in May and genuinely moved out in September · and the Transfers list with the set the other tabs subtract. |
| **UNCHANGED** | UN1–UN2 | hard rule 4 — the seller's issued documents are untouched · the seller keeps every other account they hold. |
| **IDENTITY** | ID1 | the seller remains discoverable after the sale. **This is the row the 2026-09-20 ruling is about.** |
| **REQUEST** | RQ1 | a sale raised from an approved service request — **the second door in**, and the PO's own *"create request"*. |

## Every figure reads back from PostgreSQL

Not from a service's return value and never from a screen. `observe()` goes to
`accounts`, `customer_accounts`, `customers`, `transfers`, `service_agreements`,
`units`, `premises`, `assets`, `payments`, `journal_lines`, `invoices`,
`outbound_messages` and `wizard_parks`.

⚠ **THE TWO ZEROS ARE DERIVED FROM THE TABLES, NOT READ OFF A FIELD.**
`BR-CUS-085` — *nothing is refunded and re-collected* — is drawn on step 5 as
`Refunded to the seller $0.00` and `Re-collected from the buyer $0.00`, and
**neither row is served by anything today**. Reading a field that does not exist
would be a check that cannot fail, so the suite computes both from what
PostgreSQL holds: the deposit on the account BEFORE minus AFTER is what was
refunded, and any payment row written against the account is what was
re-collected.

⚠ **AND THE ADDRESS IS WALKED, NEVER COMPARED WITH A COPY.** Hard rule 8 — an
address is stored on `premises` and NOWHERE else. `property_and_address` asserts
two things together: that the address the product serves for the unit is the one
`premises` holds, and that the `units` table declares **no address column at
all**. `BR-MET-1162` narrows exactly one clause of that rule — a unit may carry
its own `lat`/`lng` — which is why those two are deliberately absent from the
forbidden list and `city` is on it by name.

## What red means

**This suite is expected to be partly red and that is the deliverable.** It is
written against what the blueprint and the signed rules PROMISE, not against what
the product currently does. Every red row names something that is not built and
the report says which keystone it waits on. **Do not weaken an assertion to make
it green** — move the product, or move the row with a ruling behind it.

## Safety — the beta is never opened

A sale rewrites `customer_accounts`, writes a permanent `transfers` row, raises
work orders and writes `audit_log`; the audit rows and the transfer row have no
undo, and thirteen database triggers refuse the deletes a tenant drop would need.
So the throwaway utility is **a whole PostgreSQL database**:
`--ds=config.settings.pgtest` puts the run on `test_sbh_<checkout>_<digest>` and
the beta named in `DATABASE_URL` is opened for nothing at all. Each scenario
provisions its own tenant inside that database through the real signup path and
`django_db` rolls the whole graph back.

`10-scripts/transfer_scenarios.sh` counts the beta's accounts, transfers,
customer links, customers, payments, journal lines, invoices, queued messages and
parked drafts BEFORE and AFTER anyway — **a claim nobody has checked is not a
safety guarantee** (hard-won law 1).

## How to run it

    ./10-scripts/transfer_scenarios.sh                 # all 25, both columns
    ./10-scripts/transfer_scenarios.sh --prove-red     # break two, show red, restore
    ./10-scripts/transfer_scenarios.sh SL1 MN4         # named rows only

⚠ **`06-backend/.venv/bin/python` IS THE INTERPRETER.** Nothing on `PATH` imports
Django and a gate prints a **false** sentence claiming none can (`DEF-GOV-5925`),
which stopped two lanes.

**Proving it can fail** (hard-won law 7): `TRANSFER_BREAK=<id>:<dimension>`
corrupts that one OBSERVATION before the checkers see it. Corrupting the
observation rather than the declaration is deliberate — it proves the checker
really reads PostgreSQL's answer and compares it, which inverting a verdict would
not. `--prove-red` does two of them on **two different checkers**, `_subset` and
`check_outcome`, because one break proving one checker leaves eleven unproved.

## ⚠ What this suite does NOT check — printed on every run

| | |
|---|---|
| **U1** | **Whether a clerk can do any of this ON A SCREEN.** It never opens a browser, and **this flow has no walkthrough script** while move-in, move-out, the account bar, the portal and nine CRs all have one. That absence is the largest single blind spot here. `DEF-CUS-5934` — *"step 4 when last tick is press - uI breaks"* — was found by the PO clicking, over 39 green front-end cases and a clean `tsc`. |
| **U2** | **That any message ever reaches a human.** 426 messages are queued in this product and not one has ever been sent. The suite asserts what a commit QUEUES and counts what was SENT; a queue is never reported as a delivery. |
| **U3** | **The premises OWNER record following the sale.** It does not, and that is drawn rather than broken — `reassign_account` says so on every commit. What cannot be tested is whether anybody then does it by hand. |
| **U4** | **Whether the BUYER is ever shown what they took on.** `OQ-1253` is OPEN. Asserting either answer would be resolving an open question by choosing a value. |
| **U5** | **A sale on an account that already carries an ISSUED invoice.** `UN1` proves hard rule 4 negatively — no invoice row created, updated or deleted — and not positively against a real bill in the seller's name. Issuing one needs a bill run. |

## What it found, and where those findings live now

Three things the walk found are filed rather than left in the suite:

| | |
|---|---|
| **`DEF-CUS-5970`** | `DEF-CUS-5940`'s **third call site**, still live. `discounts.py:858` makes the same one-argument call, and `GET /customers/{id}/deposit-position` raises `TypeError` for any customer holding a closed account with a deposit — proved by calling it, not read off the source. 5940 names two call sites and the grep answers four. |
| **`DEF-CUS-5971`** | **After a sale every screen that shows a NAME still shows the seller's.** `selectors.account_row` serves the buyer's `customer_no` beside the seller's `name`, on one row; the asset's billing chain and the unit's Occupant column say the same. RED on 17 and 18 of the 25 rows. |
| **`DEF-CUS-5972`** | **Selling to the person who already owns the account is not refused.** The guard compares resolved customer ids, and a phone cannot reuse a customer by design — so with the identifier the step's own help text offers, the ids always differ, the guard cannot fire, and the sale mints a second number for the same person and deletes the first one's link. `RF2` is that row. |

A fourth was found by this suite and fixed by a sibling lane within the hour,
from the opposite direction: **`DEF-CUS-5940`**, a sale of an account holding a
deposit raising `TypeError` on three surfaces — including `GET /transfers`
once PER ROW. `SL1`, `MN2` and `MN4` carry a deposit and are the rows that
found it.

## Its relation to the other transfer files

* `08-qa/01-e2e/journeys/J28-transfer-one-job.md` is the DESIGN journey for the
  same flow. **It is a description and this is a program.**
* `04-docs/05-modules/03-customers/conformance/transfer-against-its-blueprint.md`
  measured the whole surface against the drawing on 2026-09-20, **from code**.
  This suite is the half that runs.
* `06-backend/tests/test_cr058_w4_transfer_reassigns.py` holds nineteen
  hand-written cases for the reassignment itself. This suite does not replace
  them; it walks the estate, the money, the lists and the messages AROUND them.
