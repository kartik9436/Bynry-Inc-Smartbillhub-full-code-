# EP-CUS-10 — The transfer and disconnect wizards (`TRF-02`, `DSC-02`)

**Module:** customers (product name: Accounts) · **Wave:** CR-030 **W7** · **Screens:** the WIZARD half of S89 (`TRF-02.1`…`TRF-02.5`) and of S90 (`DSC-02.1`…`DSC-02.5`) · **Status:** draft

> ⚠ **THIS EPIC EXISTS BECAUSE EP-CUS-08 PUT BOTH WIZARDS OUT OF SCOPE AND NOTHING
> ELSE PICKED THEM UP — hard-won law 8, and the second instance in two days.**
> EP-CUS-08's own Scope section reads: *"**Out:** the two wizards. B18 §3 maps S89
> as 'Transfers tab — list + 5-step wizard' and S90 as 'Disconnects tab — list +
> ladder + 5-step wizard'; **only the list half of each id is built** —
> `TRF-02.1…5` and `DSC-02.1…5` have no route in this application"*. That was
> true and correctly recorded. It stayed true for a day, during which
> `transfers.py` and `disconnects.py` grew every write path either wizard needs,
> and **six lanes reported the gap without any of them owning it** — the exact
> shape of DEF-695, one id over.
>
> **These two stories are written BEFORE the screens merge, not recovered after.**
> Where the screen deliberately does less than B18 draws, §8 of each story says
> so with the id that tracks it. Nothing below is an aspiration.

## Scope

**In:** the two five-step wizards and their routes — `/{tenant}/transfers/new`
(`TRF-02`) and `/{tenant}/disconnects/new` (`DSC-02`), each entered from its own
list tab's primary CTA, each on the shared `WizardFrame`, each ending in ONE
transactional commit (BR-SHL-019).

**Out:** the HTTP doors themselves. `apps/customers/api.py` mounts `GET
/transfers` and `GET /disconnects` and **no write path on either resource**,
while both service modules hold every write behind them. That is the backend
half of both stories and it belongs to the lane that owns `api.py`; §8 of each
story names the exact functions. Also out: a transfer or disconnect DETAIL
screen (neither exists, so neither wizard can resume by id) · the reconnect flow
(task 7.9) · the notice delivery adapter (BR-CUS-100, DEF-692) · the seven
deferred protections (BR-CUS-101, DEF-691) · the restrictor (OQ-385).

---

## Stories

---
id: US-CUS-029
epic: EP-CUS-10
module: customers
screens: [S89]
wave: 7
status: ready
blocked_by: []           # OQ-365 governs what the money may DO, not what the screen may SAY
depends_on: [US-CUS-004, US-CUS-005, US-CUS-027]
journeys: []             # no journey reaches a transfer; J08 covers the final-bill paths a transfer deliberately does NOT take
rules: [BR-CUS-017, BR-CUS-018, BR-CUS-022, BR-CUS-023, BR-CUS-024, BR-CUS-030, BR-CUS-053, BR-CUS-054, BR-CUS-057, BR-CUS-086, BR-CUS-102, BR-SHL-018, BR-SHL-019, BR-SHL-020, BR-SHL-025, BR-SHL-033, BR-SHL-046, BR-SHL-047]
golden_tests: [GT-23]    # ❄️ WE-7's frozen pair — cited as the reason a figure is REFUSED, never computed here
finance_calc: none       # no figure is computed on this screen; two are DISPLAYED as the server sent them and three are REFUSED
---
### US-CUS-029 — The transfer wizard: one job, five steps, and a carried deposit whose total cannot be shown

**1 · Details** — As a **billing clerk**, I want a five-step wizard that closes one
address and opens another **as one job**, so that *"the same customer, a new
address"* is never worked as a move-out followed by a move-in (B18 §5.7.7).

**Entry:** S17 Accounts → tab **Transfers** → `+ New transfer`. **Exit:** back to
that tab, or the done panel naming both halves. **Route:** `/{tenant}/transfers/new`
— top-level and static, NOT account-scoped: `transfers.start_transfer` takes
`from_account_id` in its **payload** because *"Search the account they are
leaving"* is step 1 of the flow, not a prerequisite of reaching it.

**The five steps are `transfers.STEPS`' own five**, in its order — Leaving ·
Final reads · Arriving · Money · Review — and BR-SHL-046 means they are declared
once and read by the rail (DEF-648: a wizard header said six steps while a list
column said four).

**⛔ THE MONEY IS THE STORY, AND MOST OF IT CANNOT BE SHOWN.** §5.7.7 draws
`$150.00 principal + $3.50 interest = $153.50 moving across`, and it foots four
ways over three steps. Measured against what a server can answer:

| Drawn | Servable? | What the screen does |
|---|---|---|
| Deposit principal | ✅ `GET /accounts/{id}` → `deposit_on_file` | Renders it through `MoneyCell` — the server's own string, displayed at 2 dp |
| Current balance | ✅ `balance`, the LEDGER's figure since DEF-127 | Renders it; **null renders its reason and never `$0.00`** |
| Deposit interest | ⛔ BR-CUS-057 CONFIRMED, engine unbuilt (US-CUS-023 §7) | `AbsentValue` with *"It is not zero"* |
| **Carried total** | ⛔ principal + unreadable interest is not a number | `AbsentValue` — **and this is the case that matters** |

**⛔ THE TEMPTING BUG IS NOT A RANDOM FIGURE — IT IS THE PRINCIPAL.** Rendering
`deposit_on_file` in the carried row shows **$150.00** where **$153.50** is held,
looks entirely correct, and keeps $3.50 of the customer's money. That is
❄️ **WE-7 / GT-23**'s frozen pair verbatim, and `transfers.MoneyStatement
.deposit_carried` returns `None` rather than falling back for exactly this
reason. **Proved by mutation:** rendering the principal a second time left every
`not.toContain` assertion in the test file green, so the case that pins it counts
rendered money amounts instead.

**⚠ BR-CUS-102 APPLIES DIRECTLY HERE.** PO 2026-08-25: *"Those are sample only
from Prototype; you calcualte correctly"*. So `$153.50` is not a number to print;
r10 keeps its authority over layout, copy, flows, states and **the rules written
on the screens**, and loses it only over sample DATA. Step 1's drawn
`$150.00 + $4.20 interest` — which disagrees with the same screen's own $153.50
— is DEF-690 and is not rendered at all.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| **BR-CUS-085** *(the drawn STAYS-WITH-YOU sentence)* | *"This customer is not leaving. Their deposit, their discounts and their history move with them — nothing is refunded and re-collected."* Step 1's badge states it; step 4's default election IS it. ✅ **RESOLVED 2026-08-25 (DEF-711) — `BR-CUS-085` IS NOW IN THE REGISTER AND CARRIES EXACTLY THIS SENTENCE.** ~~B18 §5.7.7 attributes this to `BR-CUS-085` and the register does not hold that id — `02-business-rules.md` runs 083 → 086 — and B18 itself proposes the same number for a different statement (*"a parked wizard never holds money"*, B18's NEW-rules table). One number, two claims, neither registered. The screen renders the SENTENCE and cites no id.~~ **PO ruling 2026-08-25: 085 is the DEPOSIT rule; the parked-wizard statement took `BR-CUS-108`.** The screen still renders the SENTENCE — the copy does not change — and the id it may now cite is `BR-CUS-085`. ⛔ **The registered rule binds the PROHIBITION only** (no refund raised, no re-collection possible); the deposit POSITION moving stays `BR-CUS-024` PROPOSED / `OQ-365` OPEN. | **CONFIRMED (BR-CUS-085, 2026-08-25) — prohibition only; POSITION still unsigned** |
| BR-CUS-023 | The deposit is a **lookup** and `deposit_on_file` is a REFUSED input field. **Consequence:** no re-collection is possible on the incoming account, so half of *"without a refund-and-recollect"* holds BY CONSTRUCTION whatever step 4 elects. | CONFIRMED |
| BR-CUS-024 | Deposit carry-forward — **mechanics PROPOSED**, which is why the POSITION does not move even though the no-refund guarantee does hold. | **PROPOSED** |
| BR-CUS-086 | A transfer is ONE JOB and appears in NEITHER Move-ins nor Move-outs. **Consequence for this screen:** the drawn `Split into two` action is DISABLED carrying that sentence — nothing in `transfers.py` can decompose a row, and a split is the rule's exact opposite. | CONFIRMED |
| BR-CUS-017 | Only a VACANT or RESERVED unit may be moved into. Enforced at the commit through `occupying_accounts_for_unit`'s advisory lock, so a unit taken between step 3 and step 5 loses the race THERE, loudly, rather than producing two live accounts on one meter. ⚠ `reserved` **has no column anywhere** (BR-MET-036), so the drawn list of vacant-and-reserved units is not rendered: a list showing a state the schema cannot hold would be inventing it. | CONFIRMED |
| BR-CUS-030 | Closure is conditional on the FINAL BILL SETTLING, not on the date. Step 5 says *"Closed, once the final bill settles"* — the screen states the shape rather than promising a closure on the day. | CONFIRMED |
| BR-CUS-054 | The customer is a first-class entity. Step 1's *"Holds N other accounts"* panel is REAL — `customer.accounts` is the tenant-scoped capability the rule names — and is the only one of step 1's four drawn panels that is. | CONFIRMED |
| BR-CUS-057 | Deposit interest: tenant-set simple annual rate, monthly accrual. **CONFIRMED (rule) · NOT BUILT (engine).** That absence is precisely why a deposit line carries no total. | CONFIRMED / **NOT BUILT** |
| BR-CUS-022 | Proration on a move day. **The same-day rule is RECORDED and not enforced here** — this module writes no bill and no meter read, so the screen states *"no gap and no double bill"* and produces neither. | CONFIRMED — not applied by this screen |
| BR-SHL-019 | Exactly ONE transactional commit. ⚠ `transfers.py` exposes FIVE sequential writes; the screen sends one payload to one door and the orchestration in one transaction is the server's. Firing five POSTs would invent four half-committed states the flow's own footer forbids (*"both halves commit together at the end"*). | CONFIRMED |
| BR-SHL-025 | Every control that cannot act is DISABLED CARRYING ITS REASON: `Split into two`, `Park`, and the two capture surfaces at steps 2 and 3. | CONFIRMED |
| BR-SHL-047 | Every wizard parks. ⚠ This one cannot: it becomes a row only when it commits, so there is nothing to hang a park on. The sentence move-in, move-out and new-connect share is REUSED, so one fix turns all four on. | CONFIRMED — blocked, with its reason |
| OQ-365 | **Does a transfer's deposit and arrears move gross, or does the close settle first?** Four signed rules meet on a transfer and all four were written about a customer who is LEAVING. | **OPEN — non-blocking.** Step 4 ELECTS and moves nothing, and says so |
| CLAUDE.md hard rules 2, 4, 5 | Money displayed 2 dp, rounded once SERVER-side (this screen re-rounds nothing and adds nothing) · financial immutability · **only the ledger posting service writes journal lines**, which is why an elected arrear does not follow. | CONFIRMED |

**3 · Test Cases** *(`07-frontend/src/features/customers/TransferWizard.test.tsx`)*

1. BR-SHL-046 — five steps, declared once, in `transfers.STEPS`' order.
2. The drawn footer is on every step and names the atomic commit.
3. Step 1's badge states *"nothing is refunded and re-collected"* (the drawn copy; ~~B18's `BR-CUS-085` citation is unregistered and is reported, not used~~ — **`BR-CUS-085` was written into the register 2026-08-25 (DEF-711) carrying this sentence, so the citation now resolves; the assertion is unchanged because it asserts the COPY, which did not change**).
4. BR-CUS-086 / BR-SHL-025 — `Split into two` is disabled with its reason.
5. Steps 1–4 issue **no write of any kind** (asserted on the wire).
6. ❄️ **WE-7 / GT-23** — the principal renders, `$153.50` and `$3.50` do not, and
   **exactly one money amount is rendered**, so serving the principal as the
   carried total goes RED.
7. BR-CUS-057 — the interest row is an absence saying *"It is not zero"*.
8. DEF-127 — a null balance renders its reason and never `$0.00`.
9. Step 1 claims no clearance it did not compute (no *"Nothing else is
   attached"*, no *"Nothing blocks this transfer"*).
10. BR-CUS-054 — the sibling-account count is the server's.
11. BR-CUS-030 — step 5 says *"Closed, once the final bill settles"*.
12. The same-day derivation returns `null` on an unset date, never `false`.
13. An in-date before the out-date is refused at the step, as `set_dates` refuses it.
14. The commit payload is exactly `commit_transfer`'s six keys and carries no read.

**8 · What B18 draws that this story does NOT deliver**

| Drawn | Why not | Tracks |
|---|---|---|
| `POST /transfers/commit` and the other five doors | `apps/customers/api.py` mounts no transfer write. `start_transfer`, `set_target_unit`, `set_dates`, `money_statement`, `elect_money`, `review`, `commit_transfer` are reachable only from Python | **OWED — backend half** |
| Steps 2 and 3's register tables with figures | `transfers.py` writes no meter read; a captured value would be discarded by the only door that exists | OWED |
| Step 1's panels (b) relationships and (d) premise | No endpoint publishes sub-meter links, sub-accounts, or the premise's owner and occupancy | OWED |
| Step 3's vacant/reserved unit list, and the refusal that names who holds a unit | `reserved` has no column (BR-MET-036); the refusal comes from the server at commit | OWED |
| The solar/net-metering plan compatibility check | Drawn as a rule with **no BR id and no code** | **RULE OWED** |
| A backflow test obligation surviving the occupant | Drawn as a rule with **no BR id and no code** | **RULE OWED** |
| A senior rate re-checked on transfer | Drawn as a rule; `discounts.py` has no re-check. Rendered as the warning it is drawn as | **RULE OWED** |
| `What we'll send` — three pieces, two ticked | No email, SMS or print adapter in this release | DEF-692 |
| Resume a parked or in-flight transfer | No transfer detail screen and no park store | OWED |

---
id: US-CUS-030
epic: EP-CUS-10
module: customers
screens: [S90]
wave: 7
status: ready
blocked_by: []           # the SCREEN is unblocked; five OQs govern what individual controls may do, and each is disabled or warned at its own control
depends_on: [US-CUS-004, US-CUS-028]
journeys: []
rules: [BR-CUS-039, BR-CUS-043, BR-CUS-055, BR-CUS-096, BR-CUS-100, BR-CUS-101, BR-CUS-103, BR-CUS-104, BR-CUS-105, BR-BIL-007, BR-SHL-019, BR-SHL-020, BR-SHL-025, BR-SHL-033, BR-SHL-046, BR-SHL-047]
golden_tests: []
finance_calc: none       # ⚠ ONE figure is displayed (the balance, the server's) and every fee is REFUSED
---
### US-CUS-030 — The disconnect wizard: it schedules, it never cuts, and it will not say "All clear"

⚠⚠ **AMENDED 2026-09-25 — THE WIZARD IS FOUR STEPS AND FIVE RULINGS MOVED
UNDER IT. READ THIS BOX BEFORE ANY ROW BELOW.** The body of this story still
describes the FIVE-step screen in places, because a register body that goes on
describing the old world is what misled three lanes in one evening
(`DEF-WRK-4030`). Every clause this box contradicts is stale.

**THE SHAPE: `Choose · Check · Schedule · Confirm`** — four words, each naming
an act, built from the rebuild's own drawings AS IMAGES (B14 rule 42). The
carry-over, so nothing is lost by subtraction:

| was | is |
|---|---|
| 1 Account & reason | **1 Choose** — the account, the reason and the services |
| 2 Protections | **2 Check** — and the ladder check is HERE ONLY |
| 3 Notice & date | **3 Schedule** — the notice, the date and who goes |
| 4 Fees & consequences | **4 Confirm** |
| 5 Review | **4 Confirm** — the old 4 and 5 were one screen twice |

**THE FIVE RULINGS OF 2026-09-25, ONE PRINCIPLE: *the product tells the clerk
what is true and does not stop them acting.*** `BR-CUS-1096` (a protection WARNS
and never refuses) · `BR-CUS-1097` (the balance need not be clear to reconnect —
**it SUPERSEDES `BR-CUS-104`'s gate clause**) · `BR-CUS-1098` (a master
account's cut is a building's cut; an occupant's protection warns) ·
`BR-CUS-1099` (no recorded proof of certified service WARNS) · `BR-CUS-1100`
(the block marks the ACCOUNT and the CUSTOMER, never the address).
**Friction before proceeding was declined FOUR times** — a typed reason, a
tick-to-acknowledge and a supervisor are all ruled out, and a sixth case of this
shape is the principle applying again rather than a question to raise
(CLAUDE.md hard-won law 13).

⛔ **THE SCREEN IS BUILT TO ALL FIVE AND THE SERVER IS NOT.** `halt_reason` →
`HALT_PROTECTED`, `assert_service_proved` → `cut_on_unrecorded_service` and
`reconnect_blockers` → `not_settled` all still REFUSE. The rulings are CONFIRMED
and the wiring is owed; a server refusal reaches the clerk through the frame's
commit failure with every entered value preserved.

**1 · Details** — As a **billing clerk**, I want a FOUR-step wizard that
SCHEDULES a disconnection — Choose · Check · Schedule · Confirm — so that a cut
is *"nothing until the scheduled date"* and every step of the way there is
recorded.

**Entry:** S17 Accounts → tab **Disconnects** → `Start a disconnect`. **Route:**
`/{tenant}/disconnects/new`, static and top-level for the reason US-CUS-029 gives.
**Exit:** the scheduled panel, naming the date and saying nothing has been cut.

**⛔ THE COMMIT SCHEDULES.** The footer is on all five steps — *"nothing is cut
until the scheduled date"* — and the button reads **`Schedule the disconnection
✓`**, never *Cut*. `schedule_cut` records the date and three elections;
`commit_cut` performs the act on the day, from somewhere else. And the ladder
stops itself (`halt_reason` / `ladder_state`), so the promise made to the customer
— *"it stops automatically if they pay or agree a plan"* — is one the code keeps.

**⛔ TWO OF `DSC-02.4`'s DRAWN STATEMENTS WERE REVERSED THE MORNING IT WAS
CAPTURED, AND THE SCREEN FOLLOWS THE RULES.**

| `DSC-02.4` drew | The ruling, PO 2026-08-25 | What the screen says |
|---|---|---|
| *"Keep charging base and standing charges — a disconnected account still accrues"* | **BR-CUS-103** (closing OQ-380, verbatim **"no"**) | *"Stop the base and standing charges at the cut"* — with the drawn sentence rendered BESIDE it, stamped as reversed |
| The fee *"When service is restored"* | **BR-CUS-104** (PO: *"does reconnection need $8,315.00 - this is correct"*) | *"…at the cut, not at restoration"*, and *"what is owed now plus that fee"* |
| — | **BR-CUS-105**, derived from both | *"Leave the balance unchanged from the cut date onward"* |

**A lane building faithfully from the drawing would have shipped both reversals as
features with every gate green**, which is why all three are pinned by tests that
were shown RED against exactly that mutation. The superseded sentences are kept
beside their supersessions rather than deleted — the posture
`disconnects.CUT_WILL` takes in Python, and for its stated reason: a reader
holding r10 next to the product must be able to find the old sentence and be told
it no longer binds.

**⛔ AND THE FEE IS NEVER A LITERAL.** BR-BIL-007: it is the tenant's own
`CC-RECON` charge code. `$75.00` is Brazos Bend's configured amount; `$45.00`,
`$35.00`, `$8,315.00` and `$7,740.00` are the drawn fixture's arithmetic. **No
seed in this repository creates `CC-RECON` at all (DEF-700)**, so the honest
answer on every tenant in this tree is an absence — and that is what renders.

**⛔ THE ONE SENTENCE THE SCREEN REFUSES TO RENDER IS `All clear`.** `DSC-02.2`
draws TEN protection checks and chips the step green. `protection_check` answers
**three** and serves a fourth — dispute — as `outcome: "unavailable"`, because
*"a green clearance derived from a table that does not exist would authorise a
cut"*. Six are unbuilt (BR-CUS-101 / DEF-691). The step's own drawn sentence is
why this matters — *"cutting service to a protected household is the single most
serious thing this product can do"* — and the tier-3 letter **promises the
customer three of the ten by name**. So the step reports what was checked and
what was not, separately, and produces no summary.

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| **BR-CUS-103** | **Base charges STOP at the cut.** A customer with no service pays nothing for it; the cost of coming back is the reconnection fee. Worked: `A-11488`, cut 2026-08-18 owing **$612.75**, still owes **$612.75** a month later. ⚠ The product does the opposite today BY OMISSION — `commit_cut` never touches billing. | CONFIRMED — PO 2026-08-25 (OQ-380). Code defect: **DEF-707** |
| **BR-CUS-104** | **The reconnection fee lands AT THE CUT**, and that TIMING clause is untouched signed law. ⚠⚠ **ITS GATE CLAUSE IS SUPERSEDED — `BR-CUS-1097`, PO 2026-09-25, verbatim: *"Show what's still owed and let the clerk proceed"*.** The sentence *"a customer must clear the arrears PLUS the fee before `mark_reconnecting` will accept them"* **must not be built to, cited as current, or restated in a docstring**; `$8,315.00` is now what the clerk is SHOWN, not what they must collect first. | TIMING **CONFIRMED** — PO 2026-08-25 (OQ-381) · GATE **SUPERSEDED 2026-09-25** by `BR-CUS-1097`. Code defect: **DEF-708** · this document's own stale restatement: **`DEF-CUS-6751`** |
| **BR-CUS-105** | The two together make a cut account's balance **STATIC** — it moves only on payment, correction or restoration. | CONFIRMED — derived 2026-08-25 |
| BR-BIL-007 | Reconnect/NSF fees are tenant-configured charge codes, never literals. **Consequence: no fee figure is rendered on this screen at all.** | CONFIRMED |
| BR-CUS-039 | Certified mail is REQUIRED on the final tier and SMS never stands alone. `schedule_cut` refuses below tier 3 and refuses without recorded proof of service. | CONFIRMED |
| BR-CUS-100 | The SEND and the PROOF are two different records — the proof is *"a record a person enters"*. **Consequence:** every delivery channel on step 3 is disabled with its reason; the product claims no delivery. | CONFIRMED — DEF-692 |
| BR-CUS-101 | Seven of the ten drawn protections are deferred. **Consequence:** no `All clear` chip, ever. | CONFIRMED — DEF-691 |
| BR-CUS-055 | Five account statuses are seeded and **none of them is `disconnected`**, so the cut state lives on `disconnect_cases.state` and nothing writes the account row. A PO amendment is owed. | CONFIRMED — gap: **DEF-701** |
| BR-SHL-025 | Disabled-with-its-reason, used five times: the restrictor treatment, four delivery channels, `Park`, the fee panel, the crew-outcome record. | CONFIRMED |
| BR-SHL-046 | The steps are declared once — **FOUR since 2026-09-25**, in `DISCONNECT_STEPS`. | CONFIRMED |
| OQ-382 | **Which of the five drawn reasons may actually cut, and on whose authority?** Four have no lawful path — `schedule_cut` requires tier 3 plus certified proof, and none of the four involves a ladder. | **OPEN.** All five are selectable; the four are WARNED, not hidden |
| OQ-383 | **A crew attends and does not cut — what is recorded?** ✅ **CLOSED 2026-09-20 — PO ruling, `BR-CUS-1083`.** Four outcomes: locked gate · access refused · paid at the door · disputed. The first three clear the cut date and return the case to `notice_sent`; a dispute stops the ladder. This row read *"Nothing can be. The case stays `scheduled` with a date in the past"* until that day. | **CLOSED.** `POST /accounts/{id}/disconnect-case/visit`; the case record's `Record visit` |
| OQ-384 | **"Blocks new service elsewhere" — for whom?** | ✅ **CLOSED 2026-09-25 → `BR-CUS-1100`.** PO, verbatim: *"you ahve to mark account and Customer ID also"* — the **ACCOUNT and the CUSTOMER record, never the premises**. Step 4 now names both, and names the address as NOT marked: the split is load-bearing, because not marking the address is what stops a new tenant being punished for the previous occupant's debt. ⛔ The block is still computed and consumed by nothing (`NEW_SERVICE_BLOCK_UNCONSUMED`) |
| OQ-385 | **What is a restricted service charged?** The money rule that blocks the restrictor, which B18 draws as the DEFAULT treatment for water. | **OPEN — and AMENDED 2026-09-25.** The option is no longer OFFERED at all: a control nobody may press beside a paragraph explaining why is a dead control AND rationale on screen, and removing it answers both (B14 rule 33). The server's refusal and `RESTRICTOR_UNBUILDABLE` are untouched, and `SERVICE_TREATMENTS` still carries the third value, so the day a schema can hold a restricted supply the option comes back from there |
| CLAUDE.md hard rules 2, 5, 7 | Money 2 dp displayed, rounded server-side · only the ledger posting service writes journal lines (so an applied deposit is an ELECTION and no reduced arrear is computed) · every money action audits. | CONFIRMED |

**3 · Test Cases** *(`07-frontend/src/features/customers/DisconnectWizard.test.tsx`)*

1. BR-SHL-046 — **FOUR** steps in the drawn order, each label ONE word.
2. The wizard schedules and never cuts — footer and button both say so.
3. Steps 1–4 issue no write of any kind.
4. **BR-CUS-103** — base STOPS, and the drawn sentence appears only as superseded.
5. **BR-CUS-104** — at the cut, in the consequence row **and** the note beside it.
6. **BR-CUS-105** — the balance is static from the cut date.
7. BR-CUS-103 — the `will not` column no longer claims a cut fails to stop growth.
8. BR-BIL-007 / DEF-700 — none of the five drawn fee figures appears.
9. The deposit application is an election — `$7,740.00` is not computed.
10. DEF-691 — no `All clear`; 3 checked against 7 unchecked, counted from the list.
11. The review restates the protections absence at the commit.
12. OQ-385 — the restrictor is NOT offered, and its sentence is gone with it (2026-09-25; these two read *"present, disabled"* and *"a draft with a restrictor cannot advance"* until then).
13. `BR-CUS-1096` / `BR-CUS-1099` — a live protection and a missing proof each WARN, and the screen nowhere says either stops the cut.
14. OQ-382 — an unreachable reason is selectable and warned.
15. OQ-383 — ✅ **CLOSED 2026-09-20.** A crew that does not cut is RECORDED and the case moves (`BR-CUS-1083`). This line read *"is stated unrecordable"* until then.
16. `BR-CUS-1100` — the cut marks the ACCOUNT and the CUSTOMER, and the screen says the address is NOT marked (this read *"rendered without a subject"* until 2026-09-25).
17. The earliest lawful cut date is not computed and no date is implied.
18. DEF-692 — every channel disabled, certified mail included.
19. The payload is `schedule_cut`'s five arguments with `{service: treatment}`.
20. DEF-127 — a null balance is not `$0.00`, which matters most here.

**8 · What B18 draws that this story does NOT deliver**

| Drawn | Why not | Tracks |
|---|---|---|
| `POST /disconnects/schedule` and the ladder/protection reads | ⚠ **PARTLY PAID OFF.** Every one of these is MOUNTED (`transfer_disconnect_api.py`, 2026-08-28) — what was missing was a SCREEN calling them, which is the different half. `schedule_cut`, `commit_cut`, `record_protection` and `reconnection_terms` gained one with `CR-125-BRC07`; ✅ **`mark_reconnecting` and `restore_service` gained one on 2026-09-20** (PO: *"Today a utility can cut supply and cannot restore it from the product"*). **STILL WITHOUT A DOOR: `open_case`, `advance`, `record_notice`, `lift_protection`, `record_proof_of_service`** — five, down from ten. | **OWED — five write paths, no screen** |
| The `All clear` chip and seven of the ten checks | Six unbuilt, one unanswerable | DEF-691 / BR-CUS-101 |
| The three-rung ladder with served dates, and the tier-3 letter as the customer receives it | `ladder_state` and `disconnect_notices` are served over no HTTP door; and no adapter delivers anything | DEF-692 |
| `EARLIEST LAWFUL CUT`, locked and computed | **Nothing in this product performs the weekend/holiday roll**, and B18's fixture cannot prove one (Aug 22 2026 is a Saturday, Aug 24 the Monday) — so `+48h` would implement *"+2 days"* and agree with the drawing by luck | **QUESTION OWED — no rule id exists for the roll** |
| A restrictor per service | The schema holds cut and not-cut; the blocker is a price nobody has ruled | OQ-385 |
| A crew outcome | ✅ **BUILT 2026-09-20** — four outcomes, `disconnect_visits` | `BR-CUS-1083` (OQ-383 CLOSED) |
| The fee table's three amounts | Tenant charge codes, none seeded | BR-BIL-007 / DEF-700 |
| B14 rule 6's **danger tier** on the commit button | ✅ **PAID OFF 2026-08-25** (`DEF-712`) — one optional tier threaded through `WizardFrame` → `WorkingButton`, asserted on the RENDERED class rather than on the prop. | **DONE** |
| A rail whose four segments are `<button disabled>` | ✅ **PAID OFF 2026-09-25.** Four controls a screen reader announces and a keyboard tabs through, none of which ever acts — hard-won law 2's mirror. `WizardFrame` gained `railNavigable`, opt-in and absent everywhere else, so the other twenty-two wizards are byte-identical. | **DONE** |
| Fees priced by the account's PLAN and CATEGORY | `_fee_table()` asks the TENANT's one charge catalogue — no plan, no category — so a residential and a commercial account are quoted the same figure. Step 4 names the account's own plan and category as a fact about the ACCOUNT and says where the figure really came from. | **`DEF-CUS-6752`** |
| A `Deposit applied` subtraction above the reconnection figure | `_to_clear` is `arrears + fee` and subtracts nothing, and cannot: applying a deposit is a balance-sheet posting (hard rule 5). The row is NOT drawn; the ELECTION is, because it is real and stored. | **`DEF-CUS-6753`** |
| A place for the clerk's `What happened` note | `schedule_cut` takes five keyword arguments and none is a note. It is KEPT on the draft and survives a park; it does not yet reach the case. | **`DEF-CUS-6754`** |
| The occupant count, the per-occupant protections and the residue transferred up | `BR-CUS-1098` wants all three. `GET /accounts/{id}/units` answers the first and the disconnect path calls nothing; the rest is on no wire. Each renders a stated absence rather than a zero — `0 occupying accounts` would say a building is empty. | **OWED — reads** |
| `What we'll send` — four pieces | No delivery channel | DEF-692 |

---

## Summary — what both wizards have in common

1. **Both are built and neither can write.** Every service function exists;
   `apps/customers/api.py` mounts two GETs and nothing else. Each screen calls
   its door, the call fails, and `WizardFrame` renders A18 §4's failure with the
   server's own words and every answer still on screen — which is preferable to a
   screen that renders a fixture, because a screen with a fixture in it looks
   finished and is not.
2. **Both refuse figures rather than fabricate them.** Between them they decline
   to render nine drawn money amounts, each with the reason in visible text.
3. **Both state what they did not check.** No `Standalone`, no *"Nothing blocks
   this transfer"*, no `All clear` — the three drawn clearances neither screen can
   compute.
4. **Both are entered from a CTA that was disabled until they existed**, and the
   two tests asserting that disablement were INVERTED rather than deleted: a case
   asserting *"not built yet"* against a mounted route is a test pinning a
   falsehood, and it would have stayed green over a dead button forever.

<!-- Lifecycle: written 2026-08-25 by lane W7WIZ, alongside the screens rather
     than after them (hard-won law 8). Sources: B18 §5.7.7 and §5.8.7 (captured
     from the drawing 2026-08-25), `apps/customers/transfers.py`,
     `apps/customers/disconnects.py`, EP-CUS-08's Scope, and the two rulings of
     2026-08-25 (BR-CUS-103, BR-CUS-104) with BR-CUS-105 derived from them.
     ⚠ The SCREEN IDs S89/S90 are B18's proposals and A1 allocates neither —
     S82–S90 still read "remain reserved" as amended 2026-08-24, so both routes
     carry `ids: NONE` in `screenIds.ts` and neither screen draws a visible tag.
     Allocation is the PO's (decision D1) and is REPORTED, not taken here. -->

---

---
id: US-CUS-032
epic: EP-CUS-10
module: customers
screens: [S148]
wave: 7                  # the epic's CR-030 W7; the STORY arrived with the PO drawings of 2026-09-25
status: built            # the two steps are live at `/{tenant}/disconnects/:ref/reconnect`; the COMMIT is not — §8
blocked_by: []           # nothing blocks the screen; what it does not do is stated in §8 and each absence carries its own id
depends_on: [US-CUS-030] # the disconnect wizard writes the case this screen reads
journeys: [J29-disconnect-to-reconnect]
rules: [BR-CUS-104, BR-CUS-1097, BR-CUS-1098, BR-WRK-055]
golden_tests: []
finance_calc: none       # every figure in the money table is the server's; the total is the LEDGER's and is never summed on screen (BR-CUS-104)
---
## `US-CUS-032` — Put service back on (`S148`, two steps)

**Status:** built, and its commit is not. **Wave:** the PO drawings of
2026-09-25. **Screens:** `S148` (`/{tenant}/disconnects/:ref/reconnect`).

> ⚠ **THIS STORY EXISTS BECAUSE THE SCREEN DID NOT HAVE ONE — hard-won law 8,
> and it is the `S1` lesson in the same module.** *Mark reconnecting* and
> *Restore service* were written on 2026-08-25, given a dialog on 2026-09-20 and
> never given an epic. A screen with no story is a screen nobody owns and nobody
> can diff against a design; `DEF-CUS-6743` is what that cost.

### 1 · What the clerk does

A clerk opens the disconnect case, follows *Put service back on*, and lands on a
page with an address they can send. **Step 1 · Choose:** the account, its
customer, its address, **its TYPE — master or regular** — the cut date, the
balance, a *Restore on* date, and a TABLE of which services go back on. Each row
says where the service point is, what the meter is, **how it goes back** (work
order · remote · no visit), an instruction for whoever attends, and a work order
the clerk **raises from the row**. Rows can be removed and services added.
**Step 2 · Confirm:** the same facts read back, **what is still owed as a
table** — arrears, reconnection fee, deposit applied, paid since, still owed —
the deposit, and what happens when service returns.

**On a master account:** one line says all the units come back together, the
services table gains a *who it reaches* column and a row for the unit meters
that cannot be split, and the money table gains **transferred-up residue as its
own line** (`BR-CUS-1098`).

### 2 · The rules it is built to

* **`BR-CUS-1097`** — the balance is SHOWN and never blocks. Step 2 states the
  figure in one sentence — *"$139.80 still owed. You may continue."* — and
  nothing on this screen refuses over it.
* **`BR-CUS-1098`** — a master's units come back together; one work order per
  affected service point; residue transferred up is its own line.
* **`BR-CUS-104`** — the fee landed AT the cut and is inside the balance, so the
  money table draws it as a LINE and takes the TOTAL from the ledger. Summing
  the rows would be the $8,390.00 the PO did not confirm.
* **B14 rule 44** — the drawing decides the CONTENT; our UI standard decides how
  it is built, **including the frame**, so the two steps ride `WizardFrame`'s
  rail rather than the drawn two-cell bar.
* **B14 rule 43** — the table array is `EditableTable` from the kit, REUSED.
  Lane WIZARD needs the same shape for the disconnect steps and should reuse it
  too; nothing new was written.
* **B14 rule 33** — rationale is ZERO WORDS. The warning states a figure and
  four words and explains nothing.

### 3 · Test cases

| TC | What it asserts |
|---|---|
| TC-1 | The money table foots: arrears + fee − paid since = still owed, and *still owed* is the ledger's figure rather than a sum computed on screen |
| TC-2 | `paid_since` is **$0.00 when nothing has been paid** — the first draft added the fee twice and reported $75.00 paid on an account nobody had paid a cent against |
| TC-3 | A master account draws the *all units together* line, the *who it reaches* column and the transferred-up line; a regular account draws none of them |
| TC-4 | The meter is `—` and never invented when no asset is on file |
| TC-5 | The commit renders DISABLED WITH ITS REASON AS VISIBLE TEXT while the server says it would refuse, and the reason is the server's own code |
| TC-6 | The route is `/:tenant/disconnects/:ref/reconnect` and it opens `S148` — the hold-expiry assertion for the door lane CUTPATH owes |

### 8 · What this screen deliberately does not do

* **It does not commit.** `disconnects.mark_reconnecting` refuses over
  `not_settled` against `BR-CUS-1097` (`DEF-CUS-6742`), and the write that
  records the rule's four facts — what was owed, what was paid, who, when — does
  not exist. The screen says so rather than reporting a restoration that did not
  happen.
* **It does not collect a deposit.** Nothing in this product collects one on
  this path, so the new deposit is a LINE and never a field (hard-won law 2).
* **It does not split a master's transferred-up residue** from the owner's own
  debt, because no read in this product can. The line is drawn with its reason
  where the figure would be.
* **It does not open from the case yet.** That control belongs to another lane
  and the door is FILED rather than quietly left.

<!-- Lifecycle: written 2026-09-25 by lane RECONNECT, alongside the screen
     rather than after it (hard-won law 8). Sources: the four PO drawings of
     2026-09-25 read as IMAGES (B14 rule 42), `BR-CUS-1097`, `BR-CUS-1098`,
     `BR-CUS-104`, `12-governance/02-decision-log.md` 2026-09-25. -->
