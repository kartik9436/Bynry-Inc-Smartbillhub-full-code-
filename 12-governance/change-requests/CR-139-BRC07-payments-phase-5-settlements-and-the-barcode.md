# `CR-139-BRC07` · Payments blueprint **phase 5 — Settlements and the barcode**

> **READ THIS FIRST IF YOU ARE A NEW SESSION.** Live progress record for phase 5,
> kept because the PO asked for one that survives the chat.
> **Every lane updates its own row in §4 in the commit that finishes it.**
> §2 of the phase 2 board (`CR-136-BRC07-…`) governs how screens are built.

| | |
|---|---|
| **Branch** | `claude/laughing-thompson-kpmwih` |
| **Source document** | `05-prototype/06 Payments Page Blueprint.pdf` — phase 5 task table **pp.23–25**; screens 5·1, 5·2 and the Scan source on 4·3a |
| **Tasks** | **18** — 3 backend · 3 db · 2 front end · 3 other · 4 test · 3 e2e |
| **What it is** | *"Close the third source, and stop keying paper."* |
| **What a clerk can newly do** | **Tie a bank credit from a provider to the payments inside it**, which nothing does today. **Scan a bill instead of keying it.** |
| **Done when** | A supervisor opens last night's payout and sees the **forty-six payments inside it**; a clerk scans a store's receipts instead of typing them. |
| **Started** | 2026-09-23 — lane **P5-BACK** on `P5.1`–`P5.6`, `P5.9`, `P5.10` and (by PO ruling of the same day) `P5.11`. |

---

## 1 · The third source, in one paragraph

Money reaches this product from three places. Two are closed: a clerk keys it at
the counter, or a file is imported. **The third is a processor that takes card
and ACH money all day and then pays the utility ONE bank credit for the lot,
net of its fee** — and today nothing in the product can say which payments are
inside that credit. The bank-rec screen sees a single deposit it cannot break
down, and the fee is invisible.

**Phase 5 makes the payout a record of its own.** It has members, it has a
gross, a fee and a net, and every payment in it stops reading *Awaiting
settlement*.

---

## 2 · Five things that need care before a line is written

### 2.1 · **The word `settlement` was already taken, in this module, on this path**

`apps/payments/webhooks.py` publishes `CHARGE_SETTLED = "charge.settled"` and a
function `settle_charge`, and there *settlement* means **one payment cleared**.
Phase 5's `settlements` means **a payout batch containing many payments**. Two
meanings, one word, one module — and the drawing does not warn about it.

**The convention this CR sets, so the next lane does not have to guess:** the
phase 5 object is always spelled **payout** in prose and **`Settlement`** in
code, and nothing in `webhooks.py`'s charge path is renamed. `settle_charge` is
about a payment; `ingest_payout` is about a payout.

### 2.2 · **`P5.4`'s money columns: the drawing says `NUMERIC(18,6)` and `CLAUDE.md` hard rule 2 says four**

The task row draws *"Money at `NUMERIC(18,6)`, currency `CHAR(3)`"*. **Hard rule
2 was re-signed by the PO on 2026-08-22** — *"We already confirmed this - MOney 4
decimal, percentage 6 decimal, display both 2 decimal"* — and that ruling
explicitly supersedes the rule's own original `NUMERIC(18,6)`. Existing 18,6
columns stay lawful containers; **what a NEW column DECLARES is four.**

This is B14 rule 37's shape one level down: **a figure in a drawing is an
illustration, and a signed rule is not.** The migration takes `NUMERIC(18,4)`
and says so in its own docstring.

### 2.3 · **`P5.2` is the money-correctness heart of the phase, and the wrong version is the natural one**

A $100.00 card payment with a $2.90 processor fee is **a $100.00 payment and a
$2.90 expense** — never a $97.10 payment. The customer paid the gross; the fee
is the utility's cost of collecting it. Netting it down would make the
customer's account short by $2.90 and the trial balance tie to the wrong number.

⚠ **AND THE BALANCED PAIR IS ALREADY BUILT — MEASURED BEFORE ANYTHING WAS
WRITTEN, AND IT CHANGES WHAT `P5.2` IS.** `OQ-144` (PO 2026-08-11, *"Match net
with a fee line"*) and `OQ-160` (PO 2026-08-12, *the fee may be DERIVED from the
shortfall*) are both **CLOSED**, and `reconciliation.reconcile_batch` →
`ledger_seam.post_batch_reconciled` writes exactly the drawn entry:

    DR 1000 Cash               4,972.90   ← what the bank actually credited
    DR 6800 Bank fees            147.50   ← the processor's fee, ITS OWN LINE
    CR 1010 Undeposited funds  5,120.40   ← what the customers handed over

So **a settlement that posted cash of its own would post the same money twice**
— §5's *two answers to one question* risk, on the money path. `P5.2` is
therefore **not a posting**: it is `OQ-160`'s option (c), the fee taken from the
payout instead of guessed from the gap, through the same door. ⚠ **The drawing's
own Reference column sends this task to `OQ-264`, which is a real CLOSED
question about tender→GL mapping and NOT the one that governs a processor fee**
— filed as `DEF-PAY-6258`, because a real id read for a different real id is the
`DEF-2804` shape and every existence check passes over it.

### 2.4 · **`P5.6`'s pointer collides with hard rule 4, and it is the PO's call**

`payments.settlement_id` is built and **nothing can write it.** The immutability
trigger freezes every column of a payment but a short allow list, **in every
status** — proved on PostgreSQL 16.13 by
`10-scripts/cr139_p5_6_pointer_freeze_proof.py`, whose third probe is the
control that makes the first two mean something. Hard rule 4 says widening that
allow list is *"a new ruling, not this one"*, so it is **`OQ-PAY-12608`**, with
three options and a worked figure.

⚠ **ANSWERED 2026-09-24 — OPTION (b): THE COLUMN IS DROPPED (`payments/0044`).**
PO, verbatim: *"p7 (b) — nothing is lost, and the payment-row lock stays exactly
as it is"*. `settlement_members` stays the one record; the immutability trigger
is untouched and `payments/0014` is still the only place the allow list has ever
moved. Built by lane RULINGS-0924, `v2.351.23`.

**Nothing is blocked by it.** `settlement_members` IS the record and
`settlements.awaiting_settlement_filter()` answers *Awaiting settlement* from
it, so the phase's own *Done when* sentence is met in full today.

### 2.5 · **`P5.11` was ruled while this phase was being built, and the drawing's row is superseded**

**PO, 2026-09-23, verbatim:** *"user will manually use it and add reference # and
Tap & pay options in system - we are not going to integrate them drectly"*.

The drawing calls `P5.11` *"Integrations: a card terminal"*. **The PO agrees it
is a device and goes further: it is not ours at all.** No adapter, no manifest,
no webhook, no driver, no settlement callback from a terminal. Its row's **kind
is corrected in §4** so the next reader does not build one.

---

## 3 · What must NOT be built in this phase

| Not this | Why |
|---|---|
| **An integration for `P5.11`** | ⚠ **RULED 2026-09-23** — PO, *"we are not going to integrate them drectly"*. **No adapter, no manifest, no webhook, no driver, no settlement callback from a terminal.** A clerk taps on the device and records the payment with its reference. What WAS built is §4's `P5.11` row. |
| **A *Tap & pay* TENDER** | The seven tenders do not move — **a tap is a card**. `Tap & pay` is a row on the tenant's own `payment_methods` list, editable on Settings. |
| **Anything saying a tap was *confirmed by the provider*** | We never speak to the terminal, so **the product cannot know a tap succeeded**. The reference is what a person read off a device and typed; it is confirmed by a CLERK, exactly like a cheque number (`BR-PAY-1150`'s posture). |
| **A stamp on `payments.settlement_id`** | §2.4. Hard rule 4's trigger refuses it in every status, proved on PostgreSQL. **`OQ-PAY-12608` CLOSED 2026-09-24, option (b): the COLUMN is dropped (`payments/0044`) rather than the lock widened** — so there is nothing left to stamp, and there never was a stub function either (one that always refuses makes its call site look wired, `gateway.py`'s 2026-09-05 precedent). |
| **A second ledger writer** | Hard rule 5. The fee posting calls `ledger_seam`; it does not compose journal lines itself. |
| **A schema change for the barcode** (`P5.10`) | The drawing is explicit: *"No schema change — it is drawn from the bill's existing payload."* |
| **A provider name anywhere in `apps/payments`** | `BR-INT-037` and `G77`. A provider is a manifest plus an adapter (PO ruling 2026-09-05). |
| **Renaming `settle_charge` / `charge.settled`** | §2.1. Two meanings, and the charge one is live on the money path with 15 tests behind it. |
| **A `NOT NULL` on `payments.settlement_id`** | `P5.6`: **null is a real state — *Awaiting settlement***. Every counter, ACH-file and lockbox payment is null forever. |

---

## 4 · The task board — **UPDATE YOUR ROW IN THE COMMIT THAT FINISHES IT**

| Task | Kind | What | Status |
|---|---|---|---|
| `P5.1` | backend | **The settlement ingest** — `settlements.ingest_payout` writes the payout and one `settlement_members` row per payment, resolving each by the `webhook\|<provider>:<event_id>` key the inbound path already composes (never by `confirmation`, which a clerk may correct). ⚠ **A MEMBER WE HOLD NO PAYMENT FOR IS RECORDED, NOT RAISED** — a payout can carry a charge taken before go-live, and refusing the whole message would leave a real bank credit with no record. ⚠ **EACH MEMBER IS WRITTEN IN A SAVEPOINT** (hard-won law 14, this phase's named risk): a bare `try/except` loses the payout and every member already written, on PostgreSQL, at COMMIT. ⚠ **RED-PROVED on the arithmetic refusals; the SAVEPOINT case is `requires_postgres` and skips loudly on SQLite** | **DONE** |
| `P5.2` | backend | **The fee stops being a guess** — ⚠ **THE TASK LINE DESCRIBES SOMETHING ALREADY SHIPPED, AND §2.3 IS WHY.** The balanced pair (DR cash net · DR `6800 Bank fees` · CR what the receipts debited) has been written by `reconcile_batch` since `OQ-144`/`OQ-160` closed in August, and this product has never written a netted payment. What landed is `settlements.stated_processor_fee()` — `OQ-160`'s option (c), returning the SAME `ResolutionInput` a human's explanation does, posting nothing. **`settlements.py` imports no ledger at all** and a structural test asserts that absence. ⚠ **THE ONE REFUSAL DERIVATION CANNOT MAKE:** provider states `$137.50`, bank is `$147.50` short → **`$10.00` unexplained, refused by name**. Under derivation that chargeback reconciles clean forever. ⚠ **The drawing's `OQ-264` citation is the wrong question — `DEF-PAY-6258`** | **DONE** |
| `P5.3` | backend | **Idempotency on a repeat payout** — two guards on two different facts, asserted **separately** (`DEF-058`'s lesson, which `webhooks.py` already keeps): a pre-write SELECT on `(tenant, provider, code)`, and `uq_settlements_provider_code` for the race it cannot close. A redelivery answers `created=False` with the existing payout — **not an error**, because a provider re-sending is a provider behaving correctly | **DONE** |
| `P5.4` | db | **`settlements`** (`payments/0038`) — ⚠ **money at `NUMERIC(18,4)`, not the drawing's 18,6** (§2.2), `CHAR(3)` currency. ⚠ **`code` IS THE PROVIDER'S OWN REFERENCE, not a number we mint** — a payout is their object, the clerk is reading their statement, and it is half the idempotency key; minting one would be a 32nd numbering series and therefore a PO question. ⚠ **THE PROVIDER'S ARITHMETIC IS CHECKED, NEVER RE-DERIVED** — `ck_settlements_net_ties` refuses `gross − fees ≠ net`, because a net we computed would agree with us by construction. ⚠ **`status` AND `bank_line_id` ARE ONE FACT** — `ck_settlements_matched_has_line` makes *matched with no line* unwritable | **DONE** |
| `P5.5` | db | **`settlement_members` and its RLS** (`payments/0038` + `payments/0039`) — *a payment belongs to at most one* is `uq_settlement_members_payment`, a CONSTRAINT and not a habit. ⚠ **`gross` IS THE PAYMENT'S OWN AMOUNT AND THE SERVICE REFUSES A MEMBER WHERE IT IS NOT** — writing the provider's netted figure is the one error this phase exists to prevent. ⚠ **RLS IS ITS OWN MIGRATION AND COVERS BOTH TABLES** — a join row with no policy reads exactly like a working table, because every ordinary query goes through the parent, which IS filtered | **DONE** |
| `P5.6` | db | **`payments.settlement_id`** — a nullable plain uuid, the shape the two sibling pointer columns use (**and `DEF-PAY-6219`'s reason, not the drawing's**: no module is crossed and B11 F-3 is about migration order). ⚠⚠ **THE COLUMN IS BUILT AND NOTHING CAN WRITE IT — HARD RULE 4, `OQ-PAY-12608` OPEN.** The immutability trigger refuses it **in every status**, proved on PostgreSQL 16.13 with a control probe. **Nothing is blocked:** `settlement_members` is the record and `awaiting_settlement_filter()` answers the third state from it, so the phase's *Done when* is met today. **DONE as far as a lane may take it; the stamp is the PO's.** ⚠ **AND THE PO ANSWERED ON 2026-09-24 — OPTION (b), the COLUMN IS DROPPED (`payments/0044`, `v2.351.23`).** *"p7 (b) — nothing is lost, and the payment-row lock stays exactly as it is"*. The third state is read from `settlement_members`, as it always was, and no read in the product changed behaviour on the day it went. | **DONE — column built `b88e6e31f`, DROPPED 2026-09-24 on `OQ-PAY-12608` (b)** |
| `P5.7` | front end | **The two Settlements screens** — 5·1 the list and 5·2 one payout, built from **p069–p072 read as IMAGES at 2.0** (B14 rule 42). ⚠ **THE READ WAS ON NO TASK ROW AND IS BUILT HERE — `DEF-PAY-6286`.** The drawing's own *To build* row (p070) names `settlements` and its members · a provider feed · one new number series · **`GET /settlements`**, and §4 had a task for all but the last; the screens would have been dead UI. `settlements_read.py` + `settlements_api.py` serve `GET /settlements`, `/settlements/{code}` and `/settlements/{code}/members`, all paged and sorted in SQL (`NFR-3`). ⚠ **NO WRITE VERB AT ALL** — p072 step 3, *"What you can do to it — Nothing, and that is the design"*: no header action, no row action but the eye, no empty-state CTA. ⚠ **A PAYOUT RESOLVES BY THE PROVIDER'S REFERENCE** (`/payments/settlements/STL-260921-CARD`) and no row or detail payload carries an `id` at all (B14 rule 31, asserted on the WIRE). ⚠ **THE THIRD STATE NEEDED A DECISION AND IT WAS MADE, NOT ASKED** — `awaiting_settlement_filter()` answers *in no payout*, which is true of the till's cash forever; *awaiting* is now a fact about the TENDER (`card` · `ach` · `tap_pay`), decision log 2026-09-23, worked figure `$1,204.80 · 31 payments` and RED-PROVED with a cash control row. ⚠ **ONE COPY DIVERGENCE, DELIBERATE:** the FEES tile's sub-line says *of provider takings* where p069 says *of card takings* — the same drawing lists an ACH payout, so B14 rule 37 settles it on the shape both halves agree on. ⚠ The `settlements` tab left `PAYMENTS_TABS_AWAITING_A_SCREEN` and its two catalogue keys were retired in the same commit; `sevenTabs.dom.test.tsx` went RED on the hold-expiry case and now asserts the SCREEN. Badges `PAY-08`/`PAY-09` minted | **DONE `9950a6458`** |
| `P5.8` | front end | **The Scan source — the input is BUILT and the CARD STAYS HELD, deliberately.** `components/workflow/ScanInput.tsx` is the focused field (p067 ① · p068 ②, read as IMAGES at 2.0), `POST /billing/remittance/parse` (`apps/billing/remittance_api.py`) is its one door onto the grammar — **it calls `remittance.parse()`**, exactly as §6 instructs, because a second Code 39 mod-43 in TypeScript is two things that can disagree about a mis-read — and the Extract stage renders it the moment `available` flips. **Enter is caught so the scanner's carriage return cannot submit the wizard**, and the scanned rows become a CSV `File` handed to the SAME `chosenFile` a browsed file lands in, so no stage below Extract learned a new word. Three refusals a clerk sees: an empty scan (`P5.15`), a bad check character (`P5.14`) and **a bill already in this batch** — a wedge fires twice on a double-press and one bill twice is two payments. ⚠⚠ **THE CARD WAS NOT SWITCHED ON, AND THAT REVERSES THIS ROW'S OWN TITLE ON PURPOSE.** `P5.10` shipped the remittance LINE; its **BARS** are owed — `remittance.bars()` is specified in full and `documents.py` calls `compose_for_invoice` and never `bars()`, **measured rather than assumed**. A wedge scanner reads BARS. Releasing the card today puts a focused field in front of a clerk holding a sack of bills a scanner reads NOTHING from, which is hard-won law 2's mirror pointing the other way — and `P5.15`'s own `scanSourceIsReachableAndHeld.dom.test.tsx`, landed hours earlier, refuses exactly that with a failure message naming the condition. ⚠ **`DEF-PAY-6274`'s SENTENCE IS CORRECTED IN ALL ELEVEN CATALOGUES**: the held reason now names the BARS instead of citing a `documents.py` claim `P5.10` had already made false. **Releasing it is now ONE line in `kinds.ts` plus one catalogue retire** — three of the four things `P5.15` says move together are done | ✅ **BUILT `9950a6458` · CARD RELEASED 2026-09-23 on `DEF-BIL-6325`** — the bars are drawn and decode-proved, so the hold's condition is met and the flag moved. The four things travelled together: bars in `documents.py`, `available: true`, `workflow.source.scan.notYet` retired from all eleven catalogues, and `P5.8`'s input already behind it. ⚠ **THE ORDER WAS THE JOB** — the PO's words read *enable it and also start putting bar code on bills*, card first; built that way round it would have shipped the silent failure `P5.15` is named for |
| `P5.9` | other | **Integrations: a settlement feed** — a `payout` inbound Operation on the `payments_sandbox` manifest, **data and no migration** (`BR-INT-037`). ⚠ **IT IS A SECOND, DIFFERENT MESSAGE AND NOT A BIGGER `settlement`** — that one means ONE PAYMENT CLEARED. ⚠ **AND ITS KEY IS THE PAYOUT'S OWN ID, NOT AN EVENT ID**: keyed on the delivery, a provider re-sending last night's payout under a fresh event id writes it twice. Adding a real processor adds this same operation to its own manifest and **not one line of `apps/payments`**, which a test asserts by absence | **DONE** |
| `P5.10` | other | **Billing: the remittance line** (`apps/billing/remittance.py`, printed on the stub by `documents.py`) — `ACC-1042$BL-2608-0117$14218%`: account, bill, **amount in MINOR UNITS** and a **Code 39 mod-43** check character (not Luhn, which is defined over digits). **No schema change**; it reads the snapshot's `total_due` — never `invoices.total`, which differs by the arrears — and joins to nothing (`BR-BIL-030`). ⚠ **`documents.py` CLAIMED *no remittance barcode* IN THREE PLACES; ALL THREE CORRECTED** (law 2's mirror — a refusal that became untrue). ⚠ **OWED: THE DRAWN BARS.** `bars()` specifies the symbol in full; the PDF writer has no filled-rectangle primitive. **The hold carries `test_cr139_p5_10_the_bars_are_not_drawn_yet`, red-proved, which names the three places to correct the day they land** | ✅ **DONE IN FULL 2026-09-23** — the line, then the BARS (`DEF-BIL-6325`, PO: *"please enable it and also start putting bar code on bills - we are still in beta and uat - we ahve to make these changes now"*). The PDF writer grew **`PageFill`**, a filled-rectangle primitive — a primitive, not a barcode-shaped special case — and `_barcode_rows` draws `remittance.bars()` on the stub above the human-readable line, which **stays**. Geometry: **X = 1.0 pt (13.9 mil)**, shrinking to fit and refusing below 0.72 pt (10 mil); **wide:narrow 2.5** (2.0 is out of spec below 20 mil); **0.25 in quiet zone held inside the row**, not borrowed from the page margin; **0.5 in bars** in **pure black**, the one mark on the sheet a machine must read. Proved by **DECODING a rendered bill back to characters** with an independently-written Code 39 table — `tests/test_def_bil_6325_barcode_round_trip.py` |
| `P5.11` | **payments — NOT `other`/integrations** | ⚠ **THE DRAWING'S KIND IS SUPERSEDED. PO ruling 2026-09-23:** *"user will manually use it and add reference # and Tap & pay options in system - we are not going to integrate them drectly"*. **We never speak to the device**, so there is no adapter, manifest, webhook or driver to build. What landed is **one seeded row** — `Tap & pay` on the tenant's own `payment_methods` list (`lookup_defaults.json` `V2.48.0.12` → `V2.48.0.13`, delivered to existing tenants by the reference sweep). The terminal's reference goes in **`payments.confirmation`**, already one of the three columns `POST /payments/{id}/correct-reference` may fix, so **`payments/0014`'s allow list does not move.** ⚠ **The seven tenders do not move: a tap is a CARD** — not one of the three needing an open till (`BR-PAY-1164`), and the Close screen still counts only cash and cheques. ⚠ **THE HONEST LIMIT, WRITTEN INTO THE FIXTURE'S OWN COMMENT: the product cannot know a tap succeeded.** | **DONE** |
| `P5.12` | test | **A payout clears the third state** — every payment in it stops reading *Awaiting settlement*. ⚠ **IT WAS ALREADY COVERED AND THE COVER HAD A HOLE, AND THE HOLE WAS MEASURED RATHER THAN ARGUED.** `test_cr139_p5_6_the_third_state_is_answered_from_the_membership` drives a payout and asserts *3 awaiting → 0*; **every payment it holds is inside the payout**, so a filter that emptied for EVERYBODY once any payout existed passes it. Proved: with `awaiting_settlement_filter` broken exactly that way, **that case reports `1 passed`**. What landed is the **CONTROL** — a fourth payment the payout does not name, which must still read *Awaiting settlement*, and the awaiting set must be **exactly** that one row — plus the three asserted **by name** rather than by a count, and a third case proving the state moved with **no payment row written** (`OQ-PAY-12608` — CLOSED 2026-09-24, option (b), so that case now asserts it against `updated_at` and `status` rather than against the dropped column). SQLite | **DONE b88e6e31f** |
| `P5.13` | test | **The fee tie-out** — the balanced pair, with the gross intact. hard rule 5. ⚠ **THE ONE OF THE FOUR THAT WAS GENUINELY NOT COVERED**, and §6 said so: nothing joined `settlements.stated_processor_fee()` to the books — the phase-5 case stops at the `ResolutionInput` and `test_us_pay_022_tc3` drives the three legs from a **hand-written** one. Three new cases make the join on the PO's card day: **DR 1000 `4,972.90` · DR 6800 `147.50` · CR 1010 `5,120.40`**, debits = credits; **the GROSS INTACT read off the payment rows themselves** (`[2,120.40, 3,000.00]`, Σ = `5,120.40`) because the ledger half is green in a build that nets every payment down; and the entry's `source_type` proving **one writer**. ⚠ **ITS FIRST DRAFT HELD A FALSE PASS THIS LANE FOUND BY RED-PROOF** — `reason_code == settlements.REASON_PROCESSOR_FEE` is a constant against itself, and re-spelling it `bank_fee` left all three green; it reads the literal `processor_fee` now. SQLite **+ real PostgreSQL 16.13** (`10-scripts/cr139_p5_13_fee_tie_out_proof.py`) | **DONE b88e6e31f** |
| `P5.14` | test | **A barcode check digit** rejects a mis-read, with the worked case in the test. ⚠ **THE REFUSAL WAS COVERED AND THE SECOND CLAUSE WAS NOT** — three cases in `test_cr139_p5_remittance.py` assert the mis-read, and the only arithmetic a reader could follow was a TOY payload (`0Z` → `Z`), never the line on every printed bill. **The worked sum is now on the page, symbol by symbol:** `ACC-1042$BL-2608-0117$14218` sums to **300** over Code 39's 43-symbol alphabet, `300 mod 43 = 42`, `ALPHABET[42] = '%'`. Its **control** explains the refusal with a figure too: `ACC-1043` moves the sum to **301**, `301 mod 43 = 0`, so the expected check becomes `'0'` and the line carrying `%` is refused. ⚠ **THE TWO ARITHMETICS ARE INDEPENDENT ON PURPOSE** — the total is computed by a loop this test owns and only then compared with `check_character()`; red-proved by moving the alphabet's order, where it names the figure (*"sum to 346, not 300"*) and the existing cases only fail on a literal. No database | **DONE b88e6e31f** |
| `P5.15` | test | **A scan with no barcode fails visibly** rather than silently keying nothing. ⚠ **THE PARSE HALF WAS COVERED; THE HALF A CLERK MEETS WAS NOT, AND `P5.8` IS ANOTHER LANE'S** — so what landed is **the hold, at both ends, keyed on the thing that is actually still missing**. The backend case fails the day `documents.py` calls `remittance.bars()`, naming the four things that move together; the front-end case mounts **`APP_ROUTES` at the real address `/{tenant}/payments/imports/new`** and fails the day the card goes live. ⚠ **BOTH EXISTING TESTS WRITE THEIR OWN `<Route>` OR HAND `SourceCards` ITS PROPS, SO NEITHER CAN TELL A WORKING ADDRESS FROM A BROKEN ONE** (hard-won law 7's *looking at the wrong thing*); red-proved by moving the route — the new case says *"there is no import runner at /brazosbend/payments/imports/new"* and the other two stay green. Carries its own **control** at a wrong address. No database + jsdom. ⚠⚠ **BOTH HOLD CASES FIRED ON 2026-09-23 AND ARE NOW INVERTED RATHER THAN DELETED (`DEF-BIL-6325`).** Each said *delete this case* in its own message; deleting would have left nothing asserting the property that actually matters, which is not *the card is on* but **the card is on IF AND ONLY IF our own paper can be scanned**. Both still read `kinds.ts` and `documents.py` TOGETHER, so a lane that takes the bars off the bill leaves a live card and a RED suite rather than a live card and silence. Every reachability assertion is kept | ✅ **DONE b88e6e31f · HOLD SPENT AND INVERTED 2026-09-23** |
| `P5.16` | e2e | `J-PAY-settle-the-night` — forty-six payments, the fee, one bank credit matched | NOT STARTED |
| `P5.17` | e2e | `J-PAY-scan-the-sack` — fourteen bills scanned at a desk, each filling itself | NOT STARTED |
| `P5.18` | e2e | **Regression** — every journey that ends in a bank match. *Settlements did not move anything under them* | NOT STARTED |

---

## 5 · What the drawing warns about, and it is p025

| Risk | What it means for this phase |
|---|---|
| **A green suite proves nothing here** | **Seventeen of the eighteen rule breaches cannot be caught by any machine in this repo** — no gate reads rendered output. `P5.7` and `P5.8` need a walk against the drawing **in a browser** or they ship the rule instead of the code. |
| **SQLite hides the import failure** | A load writes hundreds of payments in one transaction, and **on PostgreSQL a single failed statement poisons the whole transaction** — skipping a bad row needs a **SAVEPOINT**, never a bare `try/except`. The suite runs on in-memory SQLite, **which has no such state**. That is hard-won law 14, and it is **this phase's named risk** because `P5.1` writes forty-six members in one go. |
| **A hold outlives its reason** | When a phase writes a hold, it writes **the test that fires when the hold expires — asserting the destination by address — in the same commit.** |
| **Two answers to one question** | This audit found three duplicate implementations. **Before adding a component, check whether the kit already owns that job.** |
| **Immutability is not a convention** | Exactly one act in this plan writes a payment row in place (Edit, three columns, one named endpoint). ⚠ **`P5.6` is a migration adding a nullable column, which is not that act** — it writes no existing row's money. |
| **A migration with no way back** | Migration ordering is a 🔒 sensitive path. Phase 5's three migrations each need a reverse. |

---

---

## 5b · What was proved, and where each proof runs

**Three harnesses, because no one of them can answer all three questions —
and §5's *a green suite proves nothing here* is why this section exists.**

| Proof | Where it runs | What it establishes |
|---|---|---|
| `tests/test_cr139_p5_remittance.py` | **no database at all** | 21 cases. The worked line `ACC-1042$BL-2608-0117$14218%`, the mod-43 check, the mis-scan, the empty scan, the unencodable character, `total_due` vs `invoices.total`, and **the hold that expires** |
| `tests/test_cr139_p5_settlements.py` | SQLite (the default suite) | the arithmetic refusals, both idempotency guards **separately**, the two structural guards, and the third state read from the membership |
| the same file's `requires_postgres` case | **real PostgreSQL** | the **SAVEPOINT**. It SKIPS loudly on SQLite, and the skip is the point |
| `tests/test_cr139_p5_rls_pg.py` | **real PostgreSQL** | `ENABLE` + `FORCE` on BOTH tables, no-context denial, cross-tenant invisibility of **the member row on its own**, and the `WITH CHECK` |
| `10-scripts/cr139_p5_6_pointer_freeze_proof.py` | **real PostgreSQL 16.13** | the immutability trigger refuses `settlement_id` **in every status** — with a CONTROL probe, without which a merely-unwritable table would pass identically. **RUN, exit 0** |
| `10-scripts/cr139_p5_rls_and_savepoint_proof.py` | **real PostgreSQL 16.13** | `ENABLE`+`FORCE` on both tables, both policies two-sided, and **law 14 BOTH WAYS**. **RUN, exit 0** |

⚠ **AND ONE OF THOSE TWO SCRIPTS EXISTS BECAUSE THE PYTEST HARNESS COULD NOT
BE MADE TO ANSWER IN TIME, WHICH IS WORTH SAYING PLAINLY.**
`tests/test_cr139_p5_rls_pg.py` is the right home for the RLS assertions and it
stays. But building a PostgreSQL test database on this machine, with several
lanes' suites running, took **the better part of an hour and three attempts** —
twice defeated by a leftover `test_sbh_wt_…` database from a killed run that
still had a session on it, which surfaces as **22 setup ERRORS and 28 passes**
and reads like a code failure. `cr139_p5_rls_and_savepoint_proof.py` answers the
same questions **in under a second** against an already-migrated database. **A
proof nobody can run in a minute is a proof that stops being run.**

**What was actually run, and the numbers:**

* `tests/test_cr139_p5_remittance.py` — **21 passed** (no database).
* The six structural cases — **7 passed in 0.5 s**, and they now need **no
  database at all**: the module-level `django_db` mark became per-test, so a
  question about a file on disk stops paying an 18-minute test-database build.
* `tests/test_cr139_p5_settlements.py` on SQLite — **20 passed · 1 skipped**
  (`requires_postgres`, loudly) **· 2 failed**, and both failures were the two
  structural guards reading their own subject's prose. Fixed, red-proved, and
  re-run green.
* Both PostgreSQL scripts — **exit 0**, output quoted in this CR's decision-log
  row.

**Guards proved RED before being trusted green, each in the harness that runs it:**

* **The hold-expiry test** — a `remittance.bars(...)` call added to
  `documents.py` → *"the bars are being drawn — good. Now: …"*, naming the
  three places to correct. Reverted; green. ⚠ **Its FIRST draft went red on
  this CR's own prose**, which is why it greps for a CALL and not for the word
  *barcode*.
* **The no-ledger guard** — an import added **inside a function body** →
  *"imports ['apps.payments.ledger_seam']"*. That form is invisible to a grep
  at the top of a file, which is the point of reading the AST.
* **The no-vendor guard** — a `provider_key ==` comparison added → *"compares
  `provider_key` at line 454"*.

⚠ **AND BOTH STRUCTURAL GUARDS WENT RED ON THEIR OWN SUBJECT'S DOCSTRINGS
FIRST.** `settlements.py` EXPLAINS that it must not import the ledger and
EXPLAINS that `G77` fails a `provider_key ==` comparison, so a substring search
finds both phrases in the paragraphs that forbid them. **A check that asks
about wording is not a check about code** — both now parse the file as Python,
and a vendor name is looked for only in string LITERALS, never in prose.

---

## 5c · Reds on the branch that this lane did NOT cause

**Read the failures you did not cause, and date them** (hard-won law 7 habit 1,
and `DEF-CWP-4187`'s lesson that *"pre-existing"* is a claim about history).

* **`makemigrations --check` is RED, and it is not payments'.**
  `tenancy.StoredDocument`'s `kind` CHECK drifted from `DOCUMENT_KINDS` with no
  migration. **Dated with `git log -S`, not assumed: `7b8695616`, 2026-09-19**,
  four days before this lane started. Confirmed by running `makemigrations
  --check` in a **clean worktree at the tip**, where it is red with this lane's
  work entirely absent. Filed as **`DEF-GOV-6257`**. ⚠ It is not cosmetic: the
  auto-generated `payments/0038` arrived carrying tenancy's change, which would
  have landed one module's unreviewed constraint inside another's review. It
  was deleted and the dependency repointed.

## 6 · Dispatch

| Lane | Tasks | State |
|---|---|---|
| **P5-BACK** | `P5.1` · `P5.2` · `P5.3` · `P5.4` · `P5.5` · `P5.6` · `P5.9` · `P5.10` · `P5.11` | **LANDED 2026-09-23.** Nine of the eighteen |
| **P5-TESTS** | `P5.12` · `P5.13` · `P5.14` · `P5.15` | **LANDED 2026-09-23**, `b88e6e31f`. Four of the eighteen |
| **P5-SCREENS** | `P5.7` · `P5.8` — and the READ `P5.7` needed and no row owned (`DEF-PAY-6286`) | **LANDED 2026-09-23, `9950a6458`.** Two of the eighteen, plus one unowned dependency. `P5.8`'s card stays HELD — see its row |
| *(unassigned)* | `P5.16` · `P5.17` · `P5.18` | — |

⚠ **THIS TABLE AND §4 SAID DIFFERENT THINGS ABOUT THE SAME FOUR ROWS, AND BOTH
WERE WRITTEN THE SAME DAY BY THE SAME LANE.** §4 read **NOT STARTED** four
times while this table said `P5.14` and `P5.15` *"landed with their subject"*
and the notes below said `P5.12` *"is already asserted"*. **Neither was simply
wrong** — §4 was right that the ROWS were not done and this table was right
that most of the WORK was — and a lane reading either one alone would have
built the wrong thing: from §4, four test files that already exist; from here,
nothing at all. **It is the status-column-versus-body rot CLAUDE.md records
under the prime directive, inside one document**, and it is why `P5-TESTS`
began by MEASURING rather than by writing. The measurement, in one line:
**two of the four were already covered, one was covered with a hole a control
found, and one — `P5.13` — was not covered at all.**

**What the next lane inherits, in one line each:**

* **`P5.7`** reads `settlements` and `settlement_members`; both are built, both
  are RLS-forced, and both are indexed for a paged list (`NFR-3`).
* **`P5.8`** calls `apps.billing.remittance.parse()` — **do not re-derive the
  grammar**; that is the whole reason it is a module.
* **`P5.12`**–**`P5.15`** are DONE — `06-backend/tests/test_cr139_p5_12_to_p5_15.py`
  (10 cases), `07-frontend/src/features/payments/scanSourceIsReachableAndHeld.dom.test.tsx`
  (4 cases) and `10-scripts/cr139_p5_13_fee_tie_out_proof.py` (13 probes on real
  PostgreSQL 16.13, **ALL PARTS PASSED, exit 0**, under two seconds).
* ✅ **THE CARD IS SWITCHED ON — 2026-09-23, `DEF-BIL-6325`.** This bullet read
  *"`P5.8`'s LANE MUST READ TWO THINGS BEFORE IT SWITCHES THE CARD ON"* and
  named `DEF-PAY-6274` and `DEF-PAY-6273`. The PO overruled the hold the same
  day — *"please enable it and also start putting bar code on bills - we are
  still in beta and uat - we ahve to make these changes now"* — and it was
  released by **removing its reason rather than by overruling it**: the bars
  went on the paper first.
  **The four things moved together**, in this order: (1) `PageFill` +
  `_barcode_rows` in `apps/billing/documents.py`; (2) `SCAN_PAPER_CARD` to
  `available: true`; (3) `workflow.source.scan.notYet` retired from all eleven
  catalogues through `10-scripts/i18n_fanin.py`; (4) `P5.8`'s input, already
  built, is what the card now opens onto.
  ⚠ **`DEF-PAY-6273`'s SURFACE IN `kinds.ts` WENT WITH IT** — the docstring no
  longer names `workflowSources.test.ts`, a file that has never existed. It
  names `scanSourceIsReachableAndHeld.dom.test.tsx` and
  `test_cr139_p5_12_to_p5_15.py`, which are the two cases that really hold it.
  The register row is not closed by this lane; only the false citation is gone.

**`P5.8` depends on `P5.10`.** A focused scan input with no barcode on the bill
reads nothing, which is why the drawing ships the barcode in this phase rather
than with the screen. ⚠ **THAT DEPENDENCY WAS THE WHOLE OF `DEF-BIL-6325`'s RISK
AND IT WAS HONOURED IN THE BUILD ORDER, NOT ONLY ON PAPER:** the bars landed and
were decode-proved BEFORE the flag moved, so at no point did a clerk have a live
Scan card over a bill with nothing on it to scan.

---

## 7 · WHAT LANE P5-SCREENS LEFT, AND THE THREE THINGS A NEXT LANE SHOULD KNOW

**1 · `GET /settlements` EXISTED IN NO TASK ROW AND THE SCREENS WOULD HAVE BEEN
DEAD UI.** §4 has a writer (`P5.1`–`P5.3`), a schema (`P5.4`–`P5.6`) and two
screens (`P5.7`); the read between them belonged to nobody, although the
drawing's own *To build* row names it. Filed as **`DEF-PAY-6286`** and built in
the same commit as the screens. **The general shape is worth more than the
fix:** nothing in this repository counts a blueprint *To build* row against a
CR's board, so an unowned dependency is indistinguishable from a deliberate
deferral. Tick each item of a screen's *To build* row against a task row before
a board is called complete.

**2 · TWO REDS ON THE BRANCH THAT ARE NOT THIS LANE'S, BOTH DATED RATHER THAN
ASSUMED** (hard-won law 7 habit 1, and `DEF-CWP-4187`'s lesson that
*"pre-existing"* is a claim about history):

* **`tsc --noEmit` WAS RED AND IS GREEN AGAIN, AND THE SECOND HALF OF THAT IS
  WHY IT IS STILL WRITTEN DOWN.** `RevenueArPage.tsx:761`, `TS2339: Property
  'rows' does not exist on type 'NoInfer<WriteOffApprovalRow[]>'`, dated with
  `git log -S` to **`68db7d740`, 2026-09-23 09:13:33** — twenty minutes before
  this lane's worktree existed. It was fixed by a sibling at **`0fd91c287`**
  while this lane worked, and **the row this lane had drafted for it was
  DROPPED rather than pushed**: the tip's register already carries two rows
  naming it, and a third for a filed, fixed defect is the noise that makes a
  3,700-row register unreadable. `tsc --noEmit` exits **0** on the re-derived
  tree.
* **13 payments vitest cases fail in 4 files** — `OutstandingsTab`,
  `cashTotal.dom`, `writeOffDecisions`, `writeOffOneQueue`. **Measured in a
  clean worktree at `09039da1e`: the identical 13**, so not one of them is this
  lane's. `G29`, `G15`, `G32` and `G43` were each run at the tip AND here for
  the same reason; `G15` and `G32` are byte-identical numbers, `G43` is
  identical, and `G29`'s remaining gap is exactly the tip's (`DEF-SHL-6047`).

**2b · BOTH OF THIS LANE'S DEFECT IDS WERE TAKEN BY SIBLINGS BETWEEN
ALLOCATION AND PUSH, AND `allocate.py --verify` IS WHAT CAUGHT IT.** They were
filed as `DEF-PAY-6269` and `DEF-LED-6271` through `file_defect.py`, which
allocates against the remote correctly at the moment it runs. Four hours later
the remote held **both numbers, written by other lanes** — the exact collision
CLAUDE.md law 11 describes, and the reason its last clause says to re-derive
ids **unconditionally at push time** rather than only when a register
conflicts. Renumbered to **`DEF-PAY-6286`** and **`DEF-LED-6287`**, and the
register was rebuilt as *the tip's bytes plus two raw appended rows* with the
prefix proved byte-identical, never round-tripped through a parser. **Nothing
downstream would have caught the duplicate**: a repeated id in a 3,700-row
register reads as a register, not as an error.

**3 · THE SCAN INPUT IS LIVE OVER A BILL WHOSE BARS ARE NOT DRAWN.** `P5.10`
shipped the remittance LINE and its `bars()` specification; the PDF writer has
no filled-rectangle primitive, so the stub carries readable text and not a
symbol. A clerk can key the line and the whole grammar, refusal and round-trip
path is exercised — but **a wedge scanner cannot read our own bill until the
bars land**, and `test_cr139_p5_10_the_bars_are_not_drawn_yet` is the hold that
fires when they do. `P5.17` (*fourteen bills scanned at a desk*) should be read
with that in mind: the journey works from a barcode, and our own paper is not
one yet.

**`P5.8` depends on `P5.10`.** A focused scan input with no barcode on the bill
reads nothing, which is why the drawing ships the barcode in this phase rather
than with the screen. ⚠ **THAT DEPENDENCY WAS THE WHOLE OF `DEF-BIL-6325`'s RISK
AND IT WAS HONOURED IN THE BUILD ORDER, NOT ONLY ON PAPER:** the bars landed and
were decode-proved BEFORE the flag moved, so at no point did a clerk have a live
Scan card over a bill with nothing on it to scan.
