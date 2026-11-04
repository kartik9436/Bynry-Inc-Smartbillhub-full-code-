# The transfer surface against its blueprint — the wizard, the tab, and the record that does not exist

| | |
|---|---|
| Read | `05-prototype/02 Accounts Menu Blueprint.pdf`, **the 281-page edition** — wizard opening p124, the five steps p125–p130, the Transfers tab p131, the transfer record p132, the wizard's trace block p133. Rendered at 2.0 and read AS IMAGES (B14 rule 42) |
| Against | `07-frontend/src/features/customers/TransferWizard.tsx` (2,471 lines) · `TransfersTab.tsx` (797) · `transferDisconnectShared.tsx` · `transferDisconnectEndpoints.ts` · `accountFinder.tsx` · `06-backend/apps/customers/transfers.py` (1,618) · `transfer_reads.py` (664) · `transfer_disconnect_api.py` |
| Product at | `2.313.2` on the branch when this was written. ⚠ **PARTLY SUPERSEDED AT `2.314.1`, 2026-09-20** — see the amendment below |
| Status | **READ AND NOT RULED** when written. ⚠ **The PO has since walked the wizard themselves** and ruled on every step (decision log, *"THE PO WALKED THE TRANSFER WIZARD IN THE LIVE PRODUCT AND RULED ON EVERY STEP"*, 2026-09-20). |
| Walked | **Not walked** for this document. ⚠ **It HAS been walked since**, in Chromium against the live stack on `brazosbend` — `10-scripts/def_cus_5934_transfer_wizard_walkthrough.mjs`, which presses every control on all five steps. That walk found `DEF-CUS-5948`, which no reading of the code had. |

---

## ⚠ AMENDMENT, 2026-09-24 (`2.351.69`) — THE FIVE PAGE-HEAD TITLES ARE NO LONGER THE DRAWN ONES

**Every row below that reads *Title `<drawn words>` · built · keep* is overtaken,
and a lane re-running this conformance read will otherwise report five
divergences that are RULED rather than drift.** PO, 2026-09-24, verbatim: ***"4 ·
The five transfer headings - b  Shorten all five to the cap"***. B14 rule 33 caps
a heading at three words and forbids a sentence; the drawn five ran 7 · 4 · 4 · 5
· 7 words (counting the em dash on step 5 as a token).

| step | drawn (p127–p131 of the 281-page edition) | on screen at `2.351.69` |
|---|---|---|
| 1 | Find the account, and who is selling | **Account & seller** |
| 2 | Who is buying it | **The buyer** |
| 3 | The date of sale | **The date** |
| 4 | What the buyer takes on | **The money** |
| 5 | Review — one account, one new owner | **Review & confirm** |

**Only the page head moved.** Each step's SECTION heading is still the drawn
wording, in its drawn place, so nothing the long title said has left the screen.
Three of the five short names are the blueprint's own: p131 heads the review's
sections *The buyer*, *The date* and *The money*.

⚠ **DO NOT CARRY THIS TO THE MOVE-OUT.** The PO ruled ***"b) Leave as drawn"***
on ACC-06 step 4's four shortfall path names the same morning. Both rulings are
live; the decision log of 2026-09-24 carries each with the PO's own words.

---

## ⚠ AMENDMENT, 2026-09-20 (`2.314.1`) — WHAT THIS DOCUMENT NOW GETS WRONG

**Read the amendment before the tables.** Three verdicts below were overtaken
within hours of this file being written, and a lane building from the tables
alone would put back things the Product Owner has since ruled off.

| Where | What this file says | What is true at `2.314.1` |
|---|---|---|
| §4, step 4 | *"Right: `Who gets told this figure` — clerk · record · **buyer: Not decided** … **keep**"* | **DELETED.** PO verbatim: ***"why we are showing this"***. It put an undecided internal question in front of a clerk. `OQ-1253` is unchanged and still OPEN — it moved off the screen, not out of the register. |
| §4, step 4 | *"Right: dashed `THE BALANCE IS A RUNNING TOTAL…` — **add**"* | **NOT added, and it should not be.** It is rationale about where a figure comes from, and B14 rule 33 puts rationale at ZERO words on screen. The same ruling that deleted the panel above applies to it. |
| §5, step 5 | the `What goes out to the buyer and the seller` send table (p130) | **Deliberately NOT built.** Measured 2026-09-20 on `brazosbend`: 420 queued messages and **0 ever sent**; **0 of 41 templates** match ownership/transfer/changeover; **no route creates** an outbound message; and the commit plan carries three keys. A tick would be dead four ways at once — hard-won law 2's mirror. The build is `DEF-CUS-5949`. |

**Two live breaks the walk found that this document's code reading did not**, and
they are the reason a conformance file should say *Not walked* as loudly as this
one does: `DEF-CUS-5948` (every exit from the wizard landed on *"This account
could not be opened"* — the tab constant was a path segment and the accounts
router reads that as an account id) and the state of `DEF-CUS-5934`, which was
pressed in every state the step has and did **not** reproduce. Both are in the
decision log for 2026-09-20 with their evidence.

---

## 0 · THE FIRST QUESTION, ANSWERED: THE WIZARD AND THE SERVICE AGREE. **THE BLUEPRINT'S BANNER IS STALE, AND THE TAB IS THE HALF THAT NEVER MOVED.**

The blueprint's own banner repeats on p126, p127, p128, p129 and p130, verbatim:

> **REDESIGN — PUBLISHED 2026-09-11, DRAWN TO THE RULINGS IN §13, NEVER BUILT. TODAY:** *the product's transfer wizard still creates a second account, takes a final read and asks for two dates; BR-CUS-1030 made a transfer a REASSIGNMENT and these five are drawn to that ruling.*

and p133's trace block goes further:

> ⚠ **Blocked in the shipped screen** — *"The buyer is never asked for. The five steps on the running product are still the old job — Leaving · Final reads · Arriving · Money · Review — so the wizard posts a destination unit, two dates and two elections that the commit does not read, and never sends the buyer, which the commit requires. Every attempt refuses at the second of five writes, naming a field that appears on none of the screens."*

**Both sentences were true when they were drawn and neither is true now.** That condition is `DEF-CUS-5075`, and its register row reads **`fixed`**. The repair landed on 2026-09-13; the blueprint was published 2026-09-11 (wizard) and 2026-09-12 (tab and record), so the drawing is between one and two days older than the fix.

**What the code says, with lines:**

| The claim | Measured |
|---|---|
| the wizard's five steps are *Leaving · Final reads · Arriving · Money · Review* | **FALSE.** `transferDisconnectShared.tsx:191-197` declares `Find the account · The buyer · Date of sale · What they take on · Review & confirm` — the drawn five, in the drawn order |
| the wizard never asks for the buyer | **FALSE.** `TransferWizard.tsx:596-616` mounts `BuyerStep` as step 2 and validates on `buyerShortfall(draft) === null`; `transferPlanOf` (`:326-355`) puts `customer: {display_name, kind, identity, email}` on the payload |
| it posts a destination unit, two dates and two elections | **FALSE.** `TransferCommitPlan` (`transferDisconnectEndpoints.ts:205-226`) declares exactly four keys — `from_account_id`, `customer`, `sold_on`, `field_visit?` — and `transferPlanOf` sends only those |
| every attempt refuses at the second of five writes | **NOT REPRODUCED.** The door's five staged writes (`transfer_disconnect_api.py:275-291`) read exactly the four keys the wizard sends. `TransferWizard.test.tsx` + `TransfersTab.test.tsx` = **39 passed, 2 todo**, run 2026-09-20 |
| **the outgoing account is closed and a second one opened** | **FALSE, and this is the structural one.** `transfers.reassign_account` (`transfers.py:1258`) calls neither `services.move_out` nor `services.create_account`; it sets `transfer.customer_id = buyer_id`, re-links `customer_accounts`, and returns a `reassignment` block. **One account, never closed** |

**So the answer is option 3, "something else", and the shape of it matters:** the wizard and the service both moved to reassignment on the same ruling. **The list did not.** `d1066469e` (2026-09-01, CR-058 tasks 10–19) rewrote `transfers.py` by 916 lines and touched `TransfersTab.tsx` by **38** — and all 38 were one added sentence and a link sending a moving customer to a service request. Its columns, its KPI tiles, its read model and its serializer are the flow the ruling deleted.

⚠ **The rest of this document is therefore NOT cosmetic. It splits cleanly in two:**

* **The wizard** — one flow behind its drawing on DETAIL. Five steps named right, one commit, the buyer asked for, the money box drawn. What is missing is a mailing address, a match line, a template picker and the review's edit affordances.
* **The tab and the record** — the tab is the OLD JOB rendered in nine columns, and the record does not exist at any address. A clerk cannot read back a sale they just made.

---

## 1 · Step 1 — `Find the account, and who is selling` (p125–p126)

`TransferWizard.tsx:1089` `LeavingStep` · `:910` `ChangingHandsPanel` · backend `transfers.start_transfer` (`transfers.py:932`).

| Drawn element | Front end | Backend | Verdict |
|---|---|---|---|
| Breadcrumb `Transfers / Transfer`, `← Transfers` | `PageHeader` back-link to `customers.transfers.title` (`:249`) | — | **keep** |
| Kicker `TRANSFER`, title `Find the account, and who is selling` | kicker built; title is the step title | — | **keep** |
| `Step 1 of 5 · Find the account` | built — `customers.wizard.stepOfNamed` off `TRANSFER_STEPS` (`:717-740`) | `STEPS` (`transfers.py:382`) | **keep** — this is `DEF-CUS-5179` repaired; **the register row still reads `open`** |
| `Save & exit` (header, alone) | built; `Split into two` deliberately REMOVED (`:252-261`) | `wizard_parks` | **keep** |
| 5-step stepper | built off one declared list (`BR-SHL-046`) | `STEP_COUNT` | **keep** |
| `Search for the account *` + helper | `AccountFinder` `TextField` (`accountFinder.tsx:184`) | `GET /accounts?q=` (`BR-CUS-053`) | **keep** |
| **Results as a 5-column TABLE** — ACCOUNT · CUSTOMER · SERVICE ADDRESS · STATUS · BALANCE, radio per row | **a native `<select>` of one composed line** (`accountFinder.tsx:235-247`) | list serves the columns already | **change** — `DEF-CUS-5189`, OPEN |
| the disabled `Already being sold` row + *"One sale at a time"* | **not built** — a `<select>` cannot list an unofferable row | `uq_transfers_open_from` refuses it at the database; `start_transfer` raises | **add** — the refusal exists and is invisible until a clerk hits it |
| Panel **`The account — and all of it changes hands`**, 15 rows | **built, 15 rows** (`:1245-1400`): account no, customer no, seller, customer kind, category, status, opened, current balance, deposit on file, deposit interest, autopay, paperless, bill email, phone, preferred language, mailing address | all from `GET /accounts/{id}` | **keep** — this is `DEF-CUS-5180` repaired in `aec56a6ef`; **the register row still reads `open`** |
| Panel **`What is changing hands with it`** — Unit, Unit type, Floor, Floor area, Premises, Service address, Services, Meters, Plan, Base charge, Billing cycle, Ledger | **built** (`ChangingHandsPanel`, `:910-1040`) | unit rows widened out of metering's `unit_detail_dict` | **keep** |
| — Base charge · Billing cycle · Ledger | **rendered as rows STATING THEIR ABSENCE** | **served by nothing** — no cycle column on the account, no price on `unit_plan`, nothing counts unbroken months | **add (backend)** — `DEF-CUS-5182` |
| Right rail: `Stays with you.` note | not found as a distinct note | — | **add** |
| Right rail: red `Selling the property, or moving house?` | built as `Moving house is not a sale. Raise a service request.` (`:1212`) | — | **keep** |
| Right rail: `Said here on purpose` | **not built** | — | **correctly absent** — B14 rule 33 puts RATIONALE at zero words on screen |
| `The same customer elsewhere` — Other accounts · **Affected by this sale** | **built**, both rows (`:1438-1478`) | `customer.accounts` | **keep** |
| `What this sale will not touch` — 6 rows | **built**, all six (`:1496-1546`) | — | **keep** |
| dashed `THE PROPERTY OWNER RECORD` | **not on step 1**; the same fact is on step 5 (`:2351`) | `premises_owners` is not written by the sale | **keep** (placed one step later) |
| `Continue →` | built | — | **keep** |
| — | **three extra paragraphs the drawing does not have**: `Its relationships` (`:1413`), `The premise` (`:1560`), blockers-unchecked (`:1596`), ~90 words of rationale between them | — | **remove** — B14 rule 32's description budget and rule 33's zero-words-of-rationale. Each states a real absence; **two of the three are about data the drawn step never asks for** |

---

## 2 · Step 2 — `Who is buying it` (p126–p127)

`TransferWizard.tsx:1632` `BuyerStep` · backend `transfers.set_new_customer` (`transfers.py:988`).

| Drawn element | Front end | Backend | Verdict |
|---|---|---|---|
| Title `Who is buying it`, `Step 2 of 5 · The buyer` | built | — | **keep** |
| *"Matched first, created only on no match"* | built as the step's help | `_validated_buyer` → `identity_match` | **keep** |
| `Customer kind` select (A person · A company) | built, `trf_buyer_kind` | `BR-CUS-1022` | **keep** |
| `Full name *` + *"As it should appear on the bill."* | built, `trf_buyer_name` | required by `_validated_buyer` | **keep** |
| heading `One identifier — and one is enough` | **not built** — the fields sit with no group heading | `BR-CUS-1023` | **add** (3 words, lawful under rule 33) |
| `Social Security number` · `Driving licence` | built, person branch | encrypted on `customers`, never on the workflow row | **keep** |
| `Phone` + *"A phone identifies a person here."* | built | third person identifier | **keep** |
| `Tax ID` (company branch) | built | `BR-CUS-1022` | **keep** — drawn only in the person state |
| heading `How to reach them` | **not built** | — | **add** |
| `Email` | built, `trf_buyer_email` | carried on the plan | **keep** |
| **`Mailing address` select** (`Same as the service address`) | **NOT BUILT** | `customers.addresses` `kind='mailing'` is the one lawful second address (hard rule 8) | **add** — a landlord buying gets the bill at the property |
| feedback `Matched an existing customer. C-00902 · Vasquez, M., on the phone number.` | **NOT BUILT** — the match happens server-side at commit and the clerk is never told | `identity_match` runs inside `set_new_customer` | **add** — this is the step's whole premise stated back |
| red `Needs one identifier to continue.` | built — `RefusalStrip` on `buyerShortfall` (`:1745`) | `_validated_buyer` raises the same rule | **keep** |
| Right: `Field visit — the changeover read` table (RAISE · REFERENCE · WHAT IT IS · SERVICE · HOW LONG) | built — `RaiseFieldWork` (`components/RaiseFieldWork.tsx:227`) | templates are the tenant's own | **keep** |
| `No visit needed` checkbox, *"A recorded answer, not an unticked box"* | built (`RaiseFieldWork.tsx:240`) | — | **keep** |
| `What happens when you save` — 4 WHEN/WHAT rows | built (`RaiseFieldWork.tsx:244-262`) | `services._raise_flow_work` | **keep** |
| dashed `A FINAL READ, TYPED HERE · There is none, and it is not missing` | built as *"No meter reading is taken. Nothing is closing."* (`:1776`) | no read path on the sale | **keep** |

---

## 3 · Step 3 — `The date of sale` (p127–p128)

`TransferWizard.tsx:1803` `SaleDateStep` · backend `transfers.set_sale_date` (`transfers.py:1104`).

| Drawn element | Front end | Backend | Verdict |
|---|---|---|---|
| Title `The date of sale` | built | — | **keep** |
| `Date of sale *` + *"The day the account changes hands."* | built, `trf_sold_on` | `sold_on`, written to BOTH `out_date` and `in_date` so `same_day` is true by construction | **keep** |
| *"One date, not two."* | built in the step docstring; on screen as the help | replaced `set_dates` | **keep** |
| red `Nothing is prorated at a sale.` | built | stated in `set_sale_date`'s docstring | **keep** |
| `What changes hands on that day` — the same panel with CURRENT PERIOD and NEXT BILL in place of floor/floor area | **built** — `ChangingHandsPanel period` (`:910`, `period` flag) | — | **keep** |
| — Current period · Next bill | **stated absent**, same cause as base charge | **served by nothing** | **add (backend)** — `DEF-CUS-5182` |
| Right: `What the date does` — 3 rows | **not built as a panel** | the facts exist | **add** |
| Right: `What the date does not do` — 5 rows incl. `Move the deposit · No — there is nowhere to move it to` | **not built** | true by construction | **add** — this is the panel that stops a clerk expecting a deposit refund |
| dashed `A CLOSING STATEMENT FOR THE SELLER · Nothing produces one` | **not built** | true — no final bill, no settlement run | **add** |
| red `The buyer pays for days the seller used.` | **not built** | consequence of `BR-CUS-1030` | **add** — the drawing calls it *"the one thing on this wizard a clerk should say out loud to a buyer on the phone"* |

---

## 4 · Step 4 — `What the buyer takes on` (p128–p129)

`TransferWizard.tsx:1926` `TakeOnStep` · backend `transfers.acknowledge_money` (`transfers.py:1161`).

| Drawn element | Front end | Backend | Verdict |
|---|---|---|---|
| Title `What the buyer takes on` | built | — | **keep** |
| bordered box `As it stands on 05/09/2026` | built, headed with the sale date once set (`:1958-1961`) | `_statement_for` | **keep** |
| `Account balance` | built | `accounts.balance` — a CACHE (`BR-CUS-015`) | **keep** |
| `Deposit on file` | built | lookup only (`BR-CUS-023`) | **keep** |
| `Deposit interest earned` → `— not recorded` | built with the drawn reason | `BR-CUS-057` confirmed, **unbuilt** | **keep** |
| **`Taken on by the buyer`** (the total) | built | — | **keep** |
| red `The debt goes with the property.` | built | `OQ-1252` closed 2026-09-01 | **keep** |
| `Fees to collect on this sale` → dashed `THERE ARE NONE` | built (`:2112-2126`) | no change-of-ownership fee exists anywhere | **keep** |
| `Before you continue` → `I have shown this to the buyer` | built, `trf_shown_to_buyer`; **not a gate**, deliberately | recorded with the sale | **keep** |
| Right: `Why there is nothing to decide here` | **not built** | the two switches are gone — `elect_money` was replaced | **correctly absent** — rule 33 rationale |
| Right: dashed `DEPOSIT INTEREST` (the `$150.00` vs `$153.50` gap) | the FACT is on the row; the dashed explanation is not | `BR-CUS-057` | **keep** |
| Right: dashed `THE BALANCE IS A RUNNING TOTAL, NOT A RE-DERIVED ONE` | **not built** | `BR-CUS-015` — the server names the cache | **add** — it is a claim about money's provenance, not rationale |
| Right: `Who gets told this figure` — clerk · record · **buyer: Not decided** | **built**, all three (`:2082-2103`) | `OQ-1253` OPEN | **keep** |

---

## 5 · Step 5 — `Review — one account, one new owner` (p129–p130)

`TransferWizard.tsx:2180` `TransferReviewStep` · `:2377` `TransferDone` · backend `transfers.review` (`:1211`) and `reassign_account` (`:1258`).

| Drawn element | Front end | Backend | Verdict |
|---|---|---|---|
| Title `Review — one account, one new owner` | built as `One account, one new owner` | — | **keep** |
| `The account being sold` block, 14 rows | built as a **summary line**, not the 14 rows | all served | **change** — the drawing repeats step 1's facts here |
| `The buyer` block — name, kind, identifier given, SSN, licence, phone, email, mailing, **`Matched to`**, **`New customer created`** | built: name, kind, identifier given. **`Matched to` and `New customer created` are NOT built** | `reassign_account` knows both | **add** — a clerk confirming a sale cannot see whether they are about to create a customer |
| **`✎ Step N` edit affordance on each block** | **NOT BUILT** — no edit link anywhere in the step | — | **add** — without it a correction is five clicks back through `← Back` |
| `The changeover read` block — jobs raised, per-service rows, `A reading recorded by this sale · None — there is no such thing` | **NOT BUILT** | `work_orders` is on the commit response | **add** |
| `The date` block — date, recorded as, current period, next bill, prorated | built as one `Date of sale` line | — | **change** |
| `The money` block — 8 rows incl. `Refunded to the seller $0.00`, `Re-collected from the buyer $0.00`, `Fees collected — there are none` | built: `Account balance` + `Shown to the buyer`. **The three zero-movement rows are absent** | all knowable | **add** — those three rows are what say *nothing moved* |
| `What will happen when you confirm` — 7 WHEN/WHAT rows | built as 4 sentences (`:2312-2334`) | matches the door | **keep** |
| `One transaction. All five writes land together or none does.` | built | `transaction.atomic()` at `transfer_disconnect_api.py:279` | **keep** |
| red `The account keeps the seller's contact details and settings.` | built (`:2346`) | true — the sale touches none of them | **keep** |
| `The property's owner record still wants updating by hand.` | built (`:2351`) | `premises_owners` untouched | **keep** |
| **`What goes out to the buyer and the seller`** — 5-row SEND table (WHAT IT SAYS · TO · CHANNEL · TEMPLATE · WHEN) | **NOT BUILT.** The screen says *"Nothing is sent by this screen. No channel exists yet."* | `notifications_seam` exists; no transfer message kind is wired | **add** — the largest single gap in the wizard |
| **the template picker** — search + 5-row TEMPLATE/GROUP/CHANNEL/VARIANT/VERSION table, draft listed and unpickable | **NOT BUILT** | templates exist (`TemplateCatalog`) | **add** |
| `← Back` / `Complete the sale ✓` | built | `POST /transfers/commit` (`transfer_disconnect_api.py:926`) | **keep** |
| the done screen | built — `TransferDone` (`:2377`): account, new owner, `Unchanged: the unit, the meters, the plan and the ledger`, `Back to transfers` | `reassignment` block on the 200 | **keep** |

---

## 6 · The Transfers tab (p131) — **THE HALF THAT NEVER MOVED**

`TransfersTab.tsx:353` (columns) · `:489` (`transfersKpis`) · backend `transfer_reads.list_row` (`:413`), `kpi_strip` (`:538`), `transfers._serialize` (`:790`).

The drawing's own red note on this screen: **"One account, not two — and that is the whole point of this flow."** The built list still draws two.

### Columns

| Drawn | Front end | Backend | Verdict |
|---|---|---|---|
| `REFERENCE` | built, first, sortable (`:362`) | `transfer_no` + `transfer_no_unavailable` | **keep** |
| `ACCOUNT` | built as **`From account`**, a TWO-LINE cell `A-10650` / `→ A-11940` or `→ —` (`:375-385`) | `from_cell`, a two-element list written in `_serialize:822` | **change** — one account, one line. The arrow is the second account the ruling removed |
| `ADDRESS` | **not built** | `_premise()` exists and is used for `from_to` | **add** |
| `SOLD BY` (the seller) | **not built** | `transfer.customer_id` is OVERWRITTEN with the buyer at `reassign_account:1458`; the seller survives only in the `reassignment` block on the commit response and in `audit_log` | **add (backend first)** — the list cannot name the seller today |
| `SOLD TO` (the buyer) | built as **`Customer`**, one column serving both roles | `customer` = whoever the row points at now | **change** |
| `SALE DATE` | built as **two** columns, `Out date` and `In date` (`:423-434`) | `out_date` and `in_date`, both written to the same day since 2026-09-01 | **remove one** — two date columns that are equal by construction |
| `STEP` | built, `3 of 5` (`:437`) | `step_cell` off `STEP_COUNT` | **keep** |
| `TAKEN ON` (the balance at sale) | built as **`Money`** — up to two stacked sentences, `deposit carried $153.50` / `arrear follows $542.10` | `money_cell` (`transfer_reads.py:344`) | **change** — the drawing wants ONE figure; both stacked sentences describe positions that do not move |
| `STATE` | built (`:454`) | `Transfer.STATES` | **keep** |
| row action `↗ Open` | **not built** — the file's §4 says *"There is no transfer detail screen, so a 👁 icon would link onto nothing"* | — | **add, after §7** |
| — | `From → to` (two premises) (`:402`) | `from_to` with `to_absence: target_unit_not_chosen_yet` | **remove** — `to_unit_id` is never set by any live path |

### The KPI strip

| Drawn | Front end | Backend | Verdict |
|---|---|---|---|
| `OPEN` — *"a sale part-way through"* | built | `live.count()` | **keep** |
| `SELLING THIS WEEK` — *"sale date within 7 days"* | built as **`Moving this week`** | `_within_the_week(out_date)` | **change** — the word, not the arithmetic |
| **`OWED ON ACCOUNTS BEING SOLD` `$318.40`** — a SUM | **not built** | **not served** — `kpi_strip` returns five counts and no money | **add** |
| — | `Deposits carrying` (count) | `deposit_carry_elected=True` | **remove** — the column now records *"there is a position"*, not a choice; the drawing drops the tile |
| — | `Arrears following` (count) | `arrears_follow_elected=True` | **remove** — same |
| — | `Completed this month` | `committed_at` this month | **remove** — not drawn |

### Everything else on the tab

| Drawn | Front end | Backend | Verdict |
|---|---|---|---|
| head `ACCOUNTS` / `The register` / `10 tabs · Transfers · 1 still open` | owned by `AccountsListPage`'s single `PageHeader` across ten tabs | — | **keep** — changing it from this lane retitles nine siblings (the same reasoning the Move-outs file records) |
| `+ New transfer` primary | **BUILT AND LIVE** — `AccountsListPage.tsx:979-984` navigates to `TRANSFER_WIZARD_ROUTE`; the empty-state CTA at `TransfersTab.tsx:742-749` does the same | — | **keep**. ⚠ `TransfersTab.tsx:89-93` still says *"No transfer wizard route exists in this application … drawn DISABLED"* — **hard-won law 1: a comment claiming an absence is not the absence** |
| segments `Open · Selling this week · Completed · All` | **absent** | — | **correctly absent** — B14 rule 12 replaced the fixed strip with removable chips; the Move-outs file records the same refusal and the reason |
| `Filter ▾` | built — `FilterBar` over the server's `state` vocabulary (`:713`) | `TRANSFER_FILTERS = ("state",)` | **keep** |
| search `by reference, account, address or name` | built — prompt reads *"Customer, account #, or either address…"* | `SEARCH_FIELDS` includes `reference` | **change (copy)** — the prompt does not offer the reference it can answer, and *"either address"* is the two-address flow |
| `Columns ▾` | built | — | **keep** |
| `⇩ Export` | **not built** | `apps/customers/` registers no `transfers` export resource | **do not draw** — `BR-SHL-010` / `DEF-1005`, same as Move-outs |
| `1–2 of 2 · Rows per page 50 100 200` | built (`DataTable`) | server pagination | **keep** |
| red `One account, not two` | built as `exclusion.callout`, served verbatim from the payload (`:652-660`) | `transfer_reads` | ⚠ **the STRING is still §5.7.3's counting contract**, which is about two halves. **change (copy)** |
| *"One date, because there is only one."* | **not built** | — | **add** |
| *"Taken on is the balance at the moment of sale."* | **not built** | — | **add**, with the column |
| dashed `THE REFERENCE IN THE FIRST COLUMN` | built — `RecordNumberCell` renders the server's REASON, not a dash | `TRANSFER_NUMBER_UNAVAILABLE` | **keep** |
| the banner's *"the waiting on column is the addition"* | **no `waiting on` column is drawn on p131** and none is built | — | **could not establish** — see §9 |

---

## 7 · The transfer record — `/transfers/trf-26-0021` (p132) — **NOT BUILT, AT ANY ADDRESS**

The blueprint's own banner: **"TODAY: no transfer record page exists."** That is true and it is the sharpest gap on this surface.

* **No route.** `grep "transfers/:" 07-frontend/src` returns nothing; `App.tsx:1096` mounts `/transfers/new` and nothing else under `/transfers`.
* **No component.** There is a `MoveRecordPage.tsx`; there is no transfer equivalent.
* **No endpoint.** `transfer_disconnect_api.py` mounts `transfers/commit`, `transfers/{id}/money` and `transfers/{id}/cancel`. `GET /transfers/{id}` does not exist.

This is **not built** — not *built but no door*. Both halves are missing.

| Drawn on p132 | Front end | Backend | Verdict |
|---|---|---|---|
| Header `TRANSFER TRF-26-0021` · `Tan, Wei → Ferraro, L.` | — | — | **add** |
| chips `Completed` · `Account reassigned` · `Sold 05/07/2026` | — | `state`, `committed_at` | **add** |
| red `There is one account here, and it never closed.` | — | true | **add** |
| `WHAT HAPPENED` — 11 rows incl. **`Sold by`** and **`Sold to`** | — | ⚠ `transfer.customer_id` holds only the BUYER after commit; the SELLER is in the `reassignment` block of the commit response and in `audit_log`, which is **pruned on a retention schedule** | **add — backend first.** A record page cannot name the seller from the transfer row |
| `Changeover read · 2 jobs raised · both completed` | — | `work_orders` on the commit response only | **add** |
| `Committed by · S. Ortiz · 05/07/2026 14:06` | — | `audit_log` | **add** |
| `WHAT DID NOT CHANGE` — 7 rows incl. `The ledger · One continuous history, 38 months` | — | nothing counts unbroken months (same gap as step 1's `Ledger` row) | **add** |
| `THE MONEY, AS IT STOOD ON THE DAY` — 7 rows | — | `balance_at_sale` / `deposit_at_sale` ARE captured by `reassign_account:1480-1481` | **add (front end only)** — the figures are already recorded |
| `WHAT THIS RECORD DOES NOT SAY` — 3 rows | — | `OQ-1253`, `premises_owners`, account contacts | **add** |
| `Open the customer` · `Open the account` | — | — | **add** — both targets exist |
| *"This record has no actions"* | — | — | **keep as drawn** — unlike the move-out record, nothing here waits on a decision |

---

## 8 · Two live defects the transfer's counting contract causes, and one gap in the proof

### 8a · `DEF-CUS-5913` — an account sold in March and genuinely moved out in September is filtered off the Move-outs list

`transfers.transfer_half_account_ids()` (`transfers.py:865`) names **every non-cancelled transfer's `from_account_id`, forever**, and `move_reads.move_outs_queryset` subtracts it (`move_reads.py:2640`). The exclusion was correct while a committed transfer closed its outgoing half through `services.move_out`; **`BR-CUS-1030` removed the closure and nothing re-read the consumers.** The transfer's counting contract now reaches into another screen and deletes real rows from it. The code says so at `move_reads.py:2620-2631` and files it rather than fixing it, because changing a counting contract is a ruling.

### 8b · `DEF-CUS-5914` — the three tests that guard that contract have not run for 19 days

Measured here on 2026-09-20, `pytest tests/test_w5_move_worklists.py`:

```
3 failed, 27 passed
tests/test_w5_move_worklists.py:268  AttributeError: module 'apps.customers.transfers' has no attribute 'set_target_unit'
tests/test_w5_move_worklists.py:1274 AttributeError: ... no attribute 'set_target_unit'
tests/test_w5_move_worklists.py:1321 AttributeError: ... no attribute 'set_target_unit'
```

**Red before I started, and dated rather than asserted** (CLAUDE.md law 7, habit 1): `set_target_unit` left `transfers.py` in `d1066469e`, **2026-09-01**, the CR-058 commit that rewrote the module by 916 lines. The three are `test_a_committed_transfer_never_appears_as_a_move_out`, `test_a_transfers_incoming_half_never_appears_as_a_move_in` and `test_an_open_transfer_is_excluded_too_not_only_a_committed_one` — the file's own header calls the first **"CASE 1 OF THE FOUR, and the one §5.7.3 says nothing else will catch."**

⚠ **The two are one fault seen twice.** The guard that would have caught 5913 is the guard 5914 silenced, and it was silenced by the same commit that created the condition.

### 8c · The wizard is green and **unwalked**

`TransferWizard.test.tsx` + `TransfersTab.test.tsx` = 39 passed, 2 todo. p133's row reads **`Walked: Not walked.`** and **no walkthrough script for this surface exists** — `10-scripts/` holds walkthroughs for the move-in job, the account bar, the portal and nine CRs, and none for a transfer. Every claim in §1–§5 that the wizard MATCHES the drawing is a claim about source, not about pixels (hard-won law 6: no gate in this repo reads rendered output).

---

## 9 · What I could NOT establish

* **The `waiting on` column.** p131's banner says *"the Transfers tab exists and was walked; the `waiting on` column is the addition"*, and **no column of that name is drawn on p131** — the drawn table ends `STEP · TAKEN ON · STATE`. It may feed the STATE cell's `In progress` / `Waiting`, as the Move-outs list does off `waiting_on`. Unresolved from the image alone.
* **p131's opening prose contradicts p131's own drawing.** Above the banner it reads *"Onto the Transfers tab, with two dates rather than one. A transfer has an out date and an in date…"* and *"a move-out followed by a move-in would refund $150.00 and take it again"*, while the screen below it reads *"One date, because there is only one. This used to be a flow with an out date and an in date."* **I took the DRAWN SCREEN**, per B14 rule 41 and rule 37. Whether that prose is a survival from the previous edition or a live instruction is a question for the PO.
* **Whether the commit genuinely lands end to end against a running stack.** I did not boot one. The unit suites are green and the payload keys match the door's reads by inspection; that is not the same proof.
* **Three register rows read `open` over code that appears repaired** — `DEF-CUS-5179` (the step line), `DEF-CUS-5180` (step 1's row count), and the status of the `DEF-CUS-5182` absences. I did not close them; closing a row is a fan-out and this lane is read-only.

---

## 10 · What would actually have to be built, ordered by what a clerk cannot do without it

1. **The transfer record page and `GET /transfers/{id}`** — §7. A clerk can make a sale and then has **no way to read it back**. Everything else on this surface is a sale that is harder to make; this one is a sale that cannot be checked. It needs a backend leg before a front-end one, because the transfer row no longer holds the SELLER (`reassign_account:1458` overwrites `customer_id`) and the only other copy is in `audit_log`, which is pruned.
2. **`DEF-CUS-5913` — stop the transfer subtracting real move-outs from another screen's list.** A genuine move-out on a previously-sold account is invisible today, and nothing tells anybody. Repair `DEF-CUS-5914`'s three tests in the same commit, or the fix is unguarded again.
3. **Rebuild the Transfers tab's columns and tiles to the sale** — §6. Nine columns of the old job: two account numbers with an arrow between them, two identical date columns, one `Customer` column doing the work of `Sold by` and `Sold to`, and two KPI tiles counting elections nobody makes. A clerk reading this list is reading a flow the product stopped performing on 2026-09-01. Needs `sold_by` served first, same root as (1).
4. **Step 5's `What goes out` table and template picker** — §5. Today the screen says *"Nothing is sent by this screen. No channel exists yet."* Neither the buyer nor the seller is told the account changed hands, and the drawing lists three messages that should go on commit.
5. **Step 2's `Mailing address` and the `Matched an existing customer` line** — §2. A buyer's bill has nowhere else to be addressed, and the step's whole premise (*"matched first, created only on no match"*) is never shown to the clerk who is about to create a customer.
6. **`DEF-CUS-5189` — the step-1 result table.** A `<select>` cannot show a STATUS, a BALANCE, or the `Already being sold` row the drawing lists precisely so a clerk can see why it is not offered. The database refuses a second open sale; the screen refuses to explain it.
7. **Step 3's two right-hand panels and step 4's provenance note** — §3, §4. `Move the deposit · No — there is nowhere to move it to` and `The buyer pays for days the seller used` are the two sentences that stop a clerk promising a refund or a prorated bill on the phone.
8. **Step 5's `✎ Step N` edits, the `Matched to` / `New customer created` rows, the three zero-movement money rows and the changeover-read block** — §5. Review-screen completeness.
9. **Step 1's three rationale paragraphs off, and `DEF-CUS-5182`'s three absent rows served** — §1. The first is ~90 words the UI rules already forbid; the second is base charge, billing cycle and ledger length, which no reader serves.
10. **Copy: the search prompt, the one-job callout, and `TransfersTab.tsx:89-93`'s false absence** — §6. Cheap, and the last is hard-won law 1 sitting in the file as a comment that tells the next lane the wizard has no route.

---

## 11 · WHAT CHANGED THE SAME DAY THIS FILE WAS WRITTEN — §7 IS NOW HALF TRUE (2026-09-20)

⚠ **§7's heading — *"NOT BUILT, AT ANY ADDRESS"* — WAS TRUE WHEN IT WAS
MEASURED AND IS NO LONGER TRUE OF THE FRONT END.** It is amended here rather
than rewritten in place, because a section's own reading is the record of what
was measured on the day; what follows is the record of what happened next.

**The PO ruled the same day: *"buildit - use drawing images. screens hosuld
match exactly to drawing"*.** The screen is built —
`07-frontend/src/features/customers/TransferRecordPage.tsx`, mounted at
`/:tenant/transfers/:ref` after the static `/transfers/new`, with 27 unit cases
and a browser walk (`10-scripts/po20260920_transfer_record_walkthrough.mjs`,
33 assertions). **Version 2.316.0.**

⚠ **IT WAS BUILT BEFORE `transfer-record-what-is-durable.md` WAS READ, AND THE
TWO AGREE ON EVERY POINT THAT MATTERS** — which is worth recording, because two
lanes reaching the same answer separately is the only evidence either one is
right. That file says the reference IS servable, that the two `$0.00` rows are
**constants of the rule**, that `Sold by`, the two money snapshots and
`Buyer matched or created` have no durable home, that the page must never read
today's balance and label it as the sale's, and that the doors should follow the
move record's `doors` shape. The screen does all six.

### §7's table, re-read
| Drawn on p132 | Now |
|---|---|
| Header, chips, red banner | **BUILT.** The banner keeps its FACT in four words; its 24-word second sentence is CUT as rationale (B14 rule 33) and every clause of it is a ROW of *Nothing changed* |
| `WHAT HAPPENED` — 11 rows | **BUILT**, all eleven, each served or stating its own absence. `Committed by` carries its TIME, as p132 draws it |
| `WHAT DID NOT CHANGE` — 7 rows | **BUILT.** Three of them (`unit and meters`, `plan`, `service agreements`) are the RULE rather than a reading: `BR-CUS-1030` forbids the sale touching any of them. `The ledger`'s length is a stated absence — §7 was right that nothing counts unbroken months |
| `THE MONEY` — 7 rows | **BUILT.** `Refunded to seller` and `Re-collected from buyer` read `$0.00` **from `BR-CUS-085`**, not from a server read — that pair is what the screen exists to prove. Deposit interest states *counted at settlement* (PO 2026-09-19) and is **never** zeroed |
| `WHAT THIS RECORD DOES NOT SAY` — 3 rows | **BUILT.** ⚠ `Buyer told · Not decided` is `OQ-1253` and is kept UNDER PROTEST — the PO struck the wizard's equivalent panel the same day (*"why we are showing this"*). One word removes it |
| `Open the customer` · `Open the account` | **BUILT**, and they are the only two controls on the page |
| *"This record has no actions"* | **KEPT AS DRAWN**, and asserted as a COUNT so a third control goes red |

### THE DASHED REFERENCE PANEL IS STALE, AND §7 CARRIED IT FORWARD
p132's dashed block reads *"No transfer numbering series exists"*. **`OQ-426`
reads CLOSED in the register's status column**, ruled 2026-08-27 — PO verbatim,
*"Transfer TRF-26-0001 … follow same logic that we are following for other
numbers we have did in settings"*. The screen renders both arms: the number when
there is one, the server's own absence when there is not. `DEF-CUS-5945` records
how the drawing came to say otherwise. **This is the prime directive's own
lesson in a drawing rather than a register row: the status column decides, and a
body that contradicts it is stale until proved otherwise.**

### WHAT IS STILL OWED, AND EACH IS FILED
* **`GET /transfers/{ref}` is still not mounted** — §7's *"backend first"*
  reading stands. Until it answers, the address renders one sentence saying the
  reference names no transfer. A sibling lane is building it.
* **`DEF-CUS-5982` — no door points at the screen.** `TransfersTab.tsx`
  §4 still refuses a row action over *"There is no transfer detail screen, so a
  👁 icon would link onto nothing"*, which stopped being true at this commit.
  That file is held by another lane today, so the door is OWED rather than
  taken.
* **`DEF-SHL-5983` — the breadcrumb leaf.** p132 draws
  `Accounts / Transfers / TRF-26-0021`; the shell derives crumbs from its nav
  config and has no mechanism for a record's own reference. `/moves/:ref` has
  the same gap.
* **§8c is closed for this screen and open for the wizard.** *"No walkthrough
  script for this surface exists"* was true of the whole surface; there is one
  now for the RECORD. The five wizard steps — where the PO found step 4 breaking
  the screen — still have none.

### AMENDED THE SAME HOUR — THE BREADCRUMB HALF WAS ALREADY BUILT (2.316.1)

⚠ **§11 SAID THE SHELL *"HAS NO MECHANISM FOR A RECORD'S OWN REFERENCE"*, AND
THAT WAS ALREADY FALSE WHEN IT WAS WRITTEN.** `components/crumbLeaf.ts` landed
the same day against `DEF-374` — open since 2026-08-21, *"no wizard or detail
screen can supply its own breadcrumb leaf"* — and its own note asked for exactly
one shell-level mechanism rather than nine per-screen ones. The transfer record
now calls `useCrumbLeaf(reference)`, so p132's last crumb and the browser tab
both read `TRF-26-0001`.

**What remains is narrower and is what `DEF-SHL-5983` now says:** the ancestors
`Accounts / Transfers` still do not resolve, because `breadcrumbFor` reads
`SHELL_NAV` and both `/transfers/:ref` and `/moves/:ref` hang outside it. The row
is `partially-fixed` rather than closed.

⚠ **THE LESSON IS THIS LANE'S OWN AND IT COST A DEFECT ROW:** the gap was real,
the fix existed, and nothing connected them because the finding was written from
the shell's own comment rather than from a listing of what had just landed.
`ls` the neighbourhood before filing an absence — the same habit CLAUDE.md
prescribes for `10-scripts/` before writing a helper.
