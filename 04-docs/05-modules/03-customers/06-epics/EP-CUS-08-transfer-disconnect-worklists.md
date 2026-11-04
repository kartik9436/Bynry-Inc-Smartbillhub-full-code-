# EP-CUS-08 — Transfer and disconnect worklists (`TRF-01`, `DSC-01`)

**Module:** customers (product name: Accounts) · **Wave:** CR-030 **W7** (`2.48.0`) — *not* B12's W7 · **Screens:** S89 (Accounts → **Transfers** tab) · S90 (Accounts → **Disconnects** tab) · **Status:** draft

> ⚠ **THIS EPIC WAS WRITTEN AFTER THE CODE, AND SAYS SO — DEF-695, hard-won law 8.**
> S89 and S90 shipped on 2026-08-25 with **both halves built** (`transfer_reads.py`
> / `disconnect_reads.py`, `TransfersTab.tsx` / `DisconnectsTab.tsx`, and
> `GET /transfers` + `GET /disconnects` mounted in `apps/customers/api.py`) and
> **no user story owned either.** Four source files filed the finding themselves —
> `transfer_reads.py`: *"⚠ **NO STORY OWNS S89.** B18 proposes it and
> `04-docs/05-modules/03-customers/06-epics/` stops short of it … A story is OWED
> and is reported rather than invented here"*; `disconnect_reads.py` the same for
> S90 — and six lanes reported it independently the same day.
> **Every acceptance criterion below is RECOVERED FROM WHAT EXISTS**, checked
> against B18 §5.7 / §5.8 and against the test that asserts it. **Where B18 draws
> something the code does not do, this epic records it as NOT BUILT with the id
> that tracks it** (§8 of each story, plus the two summary tables at the end).
> Nothing here is an aspiration; a story that described one is how the next lane
> builds the wrong thing.

## Scope

**In:** the two **read-only worklists** — S89's list (B18 §5.7.2's eight columns, §5.7.1's
five tiles, §5.7.3's ONE JOB counting callout, the three-leg search) and S90's list
(§5.8.2's eight columns, §5.8.1's five tiles, the six tier chips, the four-leg search),
each an **embedded tab** inside `AccountsListPage` owning no query string (DEF-664).
Both surfaces **state their absences rather than fabricate a figure**: S89's money
lines can carry no amount at all, S90's `LAST NOTICE` makes no delivery claim, and
S90's five unserved segments render disabled with the server's own sentence.

**Out:** **the two wizards.** B18 §3 maps S89 as *"Transfers tab — list **+ 5-step wizard**"*
and S90 as *"Disconnects tab — list + ladder **+ 5-step wizard**"*; **only the list half of
each id is built** — `TRF-02.1…5` and `DSC-02.1…5` have no route in this application
(measured 2026-08-25; `MoveInWizard` and `MoveOutWizard` are the only two wizards
that do). Also out: the transfer WRITE path (`transfers.py`'s lane, task 7.3) · the
ladder/protection WRITE path (`disconnects.py`, tasks 7.6–7.8) · the reconnect flow
(task 7.9) · S22's notice modal (US-CUS-015) · the Move-ins / Move-outs lists whose
counting contract §5.7.3 constrains (neither exists — BR-CUS-086) · the notice
delivery adapter and the proof-of-service columns (BR-CUS-100, **schema owed**) ·
the seven deferred protections (BR-CUS-101) · seed data for §5.7.6's five and
§5.8.6's nine rows (a data lane's, task 7.12) · export.

**Tables:** customers-owned `transfers` · `disconnect_cases` · `disconnect_notices` ·
`account_protections` · `accounts` · `customers` / `customer_accounts` (BR-CUS-054).
Read-only crossings, through the reader that already owns each: metering's
`unit_ids_matching` (address), assets' `unit_ids_for_asset_search` (meter #),
`seams.ar_positions` (the ledger's OWED figure), `seams.tenant_today` (BR-TEN-043).
**No journal line is written by either screen** (CLAUDE.md hard rule 5) and **no money
moves** on S89 at all (OQ-365).

## Capability matrix (list screens only — B9 conformance)

| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| **S89** `TRF-01` | customer display name · customer # · **from** account # · **to** account # · **either address** (from-unit OR to-unit, via metering's `unit_ids_matching`). ⛔ **NOT request #** — BR-CUS-099 (PO 2026-08-25) ruled the leg away. Min 2 chars (`MIN_SEARCH_CHARS`, IS-3) | **NONE drawn and none built** — §5.7.2 draws no segment strip for this tab. ⚠ **Cancelled transfers are excluded from the list entirely**, so a clerk cannot find one | `-created_at, -id` — *"newest job first: the tab is a worklist and the job started last is the one a clerk is still holding"*; `id` secondary for a stable page boundary (IS-2) | **NONE** — `list_queryset` takes no `sort`; no column is declared `sortable` | **Default (8, B18 §5.7.2, all visible):** FROM ACCOUNT (two lines) · CUSTOMER · FROM → TO · OUT DATE · IN DATE · STEP · MONEY · STATE. **Available: none extra** | **NONE** — no transfer detail screen exists, so a 👁 icon would link onto nothing (law 2) | **NONE** | **NONE** |
| **S90** `DSC-01` | customer (primary contact name) · account # · address · **meter #** — every leg through the reader that already owns it, *"so the Disconnects box finds exactly what the Accounts box finds"* (BR-CUS-053) | **Six segments DRAWN, ONE SERVED.** `All` (served) · `At notice` · `Due to cut` · `On hold` · `Cut` · `Reconnecting` — the five render **disabled carrying the server's sentence** (BR-SHL-025); the API translates the refusal into `customers.disconnects.segment.unavailable` rather than a 500 | `account_no` ASC, `id` tiebreak. ⚠ **Deliberately NOT by urgency:** ranking `At notice`, `Due to cut` and `On hold` against each other is the same unruled precedence OQ-374 refuses to take | **NONE** — `_rows_for` takes no `sort`; no column is declared `sortable` | **Default (8, B18 §5.8.2, all visible):** ACCOUNT · CUSTOMER · ADDRESS · OWED · TIER · CUT DATE · LAST NOTICE · STATE. **Available: none extra** | **NONE** — the S22 modal and the five-step **danger-tier** flow have no route; *"a button onto nothing is bad; a danger button onto nothing is worse"* | **NONE** | **NONE** |

## Stories

---
id: US-CUS-027
epic: EP-CUS-08
module: customers
screens: [S89]
wave: 7                  # CR-030 W7 (`2.48.0`) — NOT B12's wave 7
status: ready
blocked_by: []           # the LIST is unblocked; OQ-365 blocks what the money cell may DO, not what it may SAY
depends_on: [US-CUS-004, US-CUS-005, US-CUS-007]
journeys: []             # no journey reaches the transfers list; J08 covers the final-bill paths a transfer deliberately does NOT take
rules: [BR-CUS-015, BR-CUS-023, BR-CUS-024, BR-CUS-025, BR-CUS-053, BR-CUS-054, BR-CUS-057, BR-CUS-081, BR-CUS-086, BR-CUS-099, BR-CUS-102, BR-TEN-043, BR-SHL-010, BR-SHL-011, BR-SHL-012, BR-SHL-013, BR-SHL-025]
golden_tests: [GT-23]    # ❄️ WE-7's frozen pair — cited as the reason a figure is REFUSED, never computed here
finance_calc: none       # no figure is computed on this screen; two are DISPLAYED and both may be refused
---
### US-CUS-027 — The transfers worklist: one job, two addresses, and a money cell that may show no figure at all

**1 · Details** — As a **billing clerk**, I want the Accounts screen's **Transfers** tab to list every live transfer — the account being left with the new account number **beneath it on a second line**, the customer, both addresses, both dates, how far through the five steps it is, what the money is doing and what state it is in — above a five-tile strip, so that *"the same customer, a new address"* is handled as **one job, not a move-out followed by a move-in** (B18 §5.7).

**Entry:** S17 Accounts → tab **Transfers** (`AccountsListPage.tsx`; the tab mounts `TransfersTab`). No standalone route exists, so this is always the embedded copy (DEF-664 — see US-MET-021 §1 for the whole rule and its stated price: **a page or search choice here does not survive a reload**). **Exit:** none — the row goes nowhere, because no transfer detail screen exists.

**What it calls:** `GET /transfers` → `apps/customers/api.transfers_list` → `transfer_reads.list_transfers(q, page, per, as_of)`. ⚠ **Gated `AdminOrClerk`, deliberately narrower than A4's Executive VIEW on Accounts**, because the MONEY cell is the same statement `transfers.money_statement` gates with `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` — mounting `AnyTenantRole` here would hand an Executive figures the layer below refuses them.

**⛔ NO MONEY MOVES IN A TRANSFER, AND THE CELL MUST NOT SUGGEST OTHERWISE.** §5.7.2 draws `MONEY` as up to two stacked sentences — `deposit carried $153.50` above, `arrear follows $542.10` beneath, in **amber**. Both are **statements about positions that do not move.** `transfers.money_statement` serves the two figures **plus stated absences**, four of them on a row carrying both a deposit and an arrear: `transfer_money_rule_does_not_exist` (always — OQ-365) · `deposit_carry_has_no_transfer_path` · `arrears_follow_has_no_posting_path` (only the ledger posting service writes journal lines — hard rule 5) · `balance_is_the_cached_ar_figure` (BR-CUS-015), and a fifth, `deposit_interest_not_readable`, whenever BR-CUS-057's accrual cannot be read.

**⛔ SO A LINE MAY CARRY NO FIGURE, AND THAT IS THE POINT.** `MoneyStatement.sentences` emits a sentence only when its figure is readable, which on its own would make an unreadable deposit look **identical to no deposit at all**. `money.lines` therefore emits the `deposit_carried` line either way, with `text: null`, `amount: {stored: null, display: null}` and the absence attached — and the screen renders **the server's reason as visible text**.

**⛔ `$0.00` IS FORBIDDEN HERE, AND SO IS THE PRINCIPAL — with the measured figure.** The writer lane's red-first proof: reading the unwired BR-CUS-057 interest as ZERO served **`$150.00`** where **`$153.50`** is held — *"the tempting zero does not merely lose precision, it serves the principal AS the carried amount and keeps $3.50 of the customer's money"* (❄️ **WE-7 / GT-23**'s frozen pair). Showing `$0.00` is DEF-127's *"looks exactly like a settled account"* one column over. **A row with NO lines at all renders `—`, and that dash means *none*** — §5.7.6's `A-11109 · Osei, Grace`, who holds no deposit and owes nothing.

**⚠ THE ONE JOB CALLOUT IS A COUNTING CONTRACT, NOT DECORATION.** §5.7.3 is a `[shot]` callout **on the screen**: *"A transfer appears only here. Its two halves are deliberately kept out of Move-ins and Move-outs — the same job listed three times would be counted three times."* The Move-ins tab shows **3** and Move-outs **5**; if a transfer's halves leaked in they would read 4 and 6 and the KPI strips would lie. This list is the *"only here"* half, so it filters nothing out and instead **publishes the complement**: `exclusion.half_account_ids` is `transfers.transfer_half_account_ids()` **called, not re-derived**, and the callout the clerk reads is the same string served on `exclusion.callout`. ⚠ **Neither move list exists yet** (BR-CUS-086), so the contract is enforced before the thing it constrains exists — including a static case that scans `apps/customers/*.py` and fails, naming the file, the moment a move list appears that calls none of the three helpers.

**⛔ FOUR THINGS §5.7.2 DRAWS THAT THIS STORY DOES NOT DELIVER** — see §8: a **`+ New transfer` primary** (no wizard route; the empty-state CTA is drawn disabled with that reason) · **a row action** (no transfer detail — law 2) · **the `request #` search leg** (BR-CUS-099 ruled it away) · **a sort control** (the server fixes the order). And one more the epic scope names: **`TRF-02.1…5`, the five-step wizard B18 §3 puts under the same id, is not built.**

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-CUS-086 | *"A transfer is ONE JOB and appears in NEITHER Move-ins nor Move-outs."* Listing it in both *"would show one customer's single move as two jobs and let two clerks work it independently"*. §5.7.6's Jenna Park sits at step `3 of 5` and is correctly absent from the Move-outs five — **the exclusion covers OPEN transfers, not just committed ones**. | CONFIRMED — transcribed 2026-08-25 from B18 §11 / §5.7.3 (DEF-673, third instance) |
| BR-CUS-099 | **The transfers list does not search by request number.** PO 2026-08-25, verbatim: *"Drop the leg — remove 'or request #' from the box"*. The box now offers exactly what the data can answer: customer · account # · either address. ⚠ **The consequence was accepted, not overlooked:** there is now no way to get from a service request to the transfer it became. | CONFIRMED — PO 2026-08-25 (DEF-688) |
| BR-CUS-102 | **The prototype's numbers are samples; the product computes.** PO 2026-08-25, verbatim: *"Those are sample only from Prototype; you calcualte correctly"*. Applies directly here: `TRF-02.1` draws *"$150.00 + $4.20 interest"* where four other screens say **$153.50**. ⚠ **The boundary is narrow** — r10 remains authoritative for layout, copy, flows, states and **the rules written on the screens**; only the sample DATA loses that standing. | CONFIRMED — PO 2026-08-25 (DEF-690) |
| BR-CUS-015 | `accounts.balance` is a **CACHE**. The arrear this cell shows is that cache, and `balance_is_the_cached_ar_figure` names it **so no screen prints it as a ledger-verified number**. | CONFIRMED |
| BR-CUS-054 | The customer is a first-class entity; the CUSTOMER cell reads `customers.display_name` + `customer_no` through the `customer_accounts` link the transfer row carries — **never a contact name on the account**, because *a transfer is the same customer* and the entity is the thing being searched. | CONFIRMED — PO OQ-057 (b) |
| BR-CUS-053 | The search legs, and the address leg goes through **metering's own selector** (`seams.unit_ids_matching`) rather than a second address matcher — matched against BOTH `from_account.unit_id` and `transfers.to_unit_id`, which is §5.7.2's *"either address"* in one OR-group. | CONFIRMED |
| BR-CUS-057 | Deposit interest = tenant-set simple annual rate, monthly accrual, payout at refund/closure. **CONFIRMED AND NOT BUILT** — `deposit_interest_accrued` is published by nothing (US-CUS-023 §7). That absence is precisely why a deposit line may carry no figure. | CONFIRMED (rule) · **NOT BUILT (engine)** |
| BR-CUS-023 | The deposit is a **lookup**, and `deposit_on_file` is a REFUSED input field. Consequence for this screen: **no re-collection is possible on the incoming account**, so half of B18 task 7.3 (*"without a refund-and-recollect"*) is guaranteed **by construction**. | CONFIRMED |
| BR-CUS-024 | Deposit carry-forward — **mechanics PROPOSED**, which is why the POSITION does not move even though TC-TRF-3's *"not refunded and re-collected"* guarantee IS held. | **PROPOSED** |
| BR-CUS-025 / BR-CUS-081 | Closure settles the deposit against the final bill first. ⚠ **These were written about a customer who is LEAVING**, and a transferring customer is not leaving — which is the whole of OQ-365. Neither is applied by this screen. | CONFIRMED (for closure) — **not applicable here; OPEN via OQ-365** |
| BR-TEN-043 | The event date is an **argument, never a wall clock**. `as_of` defaults to `seams.tenant_today()` — the tenant's calendar, not the server's — because `MOVING THIS WEEK` and `COMPLETED THIS MONTH` are windows a clerk reads against their own. The basis is served as DATA (`period_basis: "tenant_month_to_date"`) rather than assumed. | CONFIRMED |
| **The two election tiles count DECISIONS, not movements** | `DEPOSITS CARRYING` and `ARREARS FOLLOWING` count `deposit_carry_elected` / `arrears_follow_elected` on open rows. Counting the FIGURES instead *"would count Osei's row the moment somebody opened it, before any human decided anything."* | **PROPOSED** — derivation of §5.7.1's two captions + the writer lane's stated reason for storing an election |
| **`MOVING THIS WEEK` uses `out_date`** | §5.7.4's same-day rule — *"outgoing pays the move day, incoming starts the next day from the same reading"* — makes the move day the OUT date. Inclusive at both ends, forward-looking only. Worked on §5.7.6: the tile reads **1** under `out_date` (Park, Aug 28) and **0** under `in_date`. | **PROPOSED** — derivation of §5.7.1's caption + §5.7.4's rule |
| **The `→ —` dash is the SERVER's** | `transfers._serialize` builds `from_cell` as two strings and writes the literal itself, *"because a blank second line and an absent one are indistinguishable once rendered"*. The screen prints the two strings it was given and produces no dash of its own. | **PROPOSED** — derivation of §5.7.2 + TC-TRF-2, one authority per cell |
| BR-SHL-010 / 011 / 012 / 013 / 025 | The shared list contract, as on S86: undeclared capabilities do not render · the URL grammar clamps and never errors (**and this embedded list owns no query string** — DEF-664) · the framework owns the empty/failed states **and a failed read never renders the empty state** · column prefs key on `screenId = "S89"` · a control that cannot be used renders **disabled with its reason**. | CONFIRMED (each) · the embedded-URL exception **PROPOSED** — DEF-664 |
| CLAUDE.md hard rules 1, 2, 4, 5 *(cited, not restated)* | Tenant scoping under RLS FORCE · money stored 4 dp / **displayed 2 dp, rounded once, SERVER-side** (this screen never re-rounds) · financial immutability · **only the ledger posting service writes journal lines** — which is why the arrear cannot follow. | CONFIRMED — hard rules |
| OQ-365 | **Does a transfer's deposit and arrears move gross, or does the close settle first?** Four signed rules meet on a transfer and all four were written about a customer who is leaving. | **OPEN — non-blocking.** Nothing moves; the statement says so |

**3 · Test Cases**

*(Backend: `06-backend/tests/test_w7_worklists.py`. Frontend: `07-frontend/src/features/customers/TransfersTab.test.tsx`.)*

| TC | Scenario | Expected | Asserted by |
|---|---|---|---|
| TC-1 | Clerk opens Accounts → **Transfers** with §5.7.6's five rows seeded | The eight drawn columns render Park's row: `A-11455` over `→ A-12055`, `Park, Jenna`, `901 Hillside Ave → 26 Meadowbank Rise`, Aug 28 / Sep 03, **`3 of 5`**, both money sentences, **In progress** | `test_trf_the_columns_and_steps_are_b18s_own` · FE *"§5.7.2 — the eight drawn columns render §5.7.6's Park row"* |
| TC-2 *(TC-TRF-2)* | A transfer at step 1, before a target unit is chosen (`A-11109 · Osei`) | `FROM ACCOUNT` is TWO LINES and the second reads **`→ —`**, not a blank; the `FROM → TO` cell says the new address *"has not been chosen yet"* **in words**, because that is a stage of the job and not lost data | `test_trf_the_from_cell_is_two_lines_and_reads_a_dash_before_the_new_number` · FE *"TC-TRF-2 — the FROM ACCOUNT cell is two lines and reads `→ —` before the new account exists"* · FE *"the target address is a STAGE of the job, said in words, not a blank"* |
| TC-3 | The new account is created at step 2 | The second line carries `→ A-12055` **as soon as it exists** | `test_trf_the_second_line_carries_the_new_number_as_soon_as_it_exists` |
| TC-4 *(TC-TRF-3)* | Park holds a **$153.50** deposit position and a **$542.10** arrear, both elected to carry | MONEY stacks two sentences — `deposit carried $153.50` in ink, `arrear follows $542.10` in **amber** (tone is DATA, carried on `lines[].tone`, so B14's colour decision is made once in the design). **The deposit is not refunded and re-collected** | `test_trf_money_stacks_two_sentences_with_the_arrear_in_amber` · FE *"§5.7.2 — the MONEY cell stacks both sentences and the arrear is amber"* |
| TC-5 *(negative — the money one)* | The account HOLDS a deposit whose carried figure cannot be read, because BR-CUS-057's interest engine is unwired | The `deposit_carried` line is still emitted, with `text: null` and `amount.stored`/`amount.display` **null**, and the screen renders **the server's REASON as visible text**. ⛔ **Never `$0.00`, and never the principal `$150.00`** — the figure ❄️ WE-7 / GT-23 makes measurable: `$150.00` where **`$153.50`** is held keeps `$3.50` of the customer's money | `test_trf_money_never_fabricates_a_figure` · FE *"⛔ a deposit whose figure cannot be read renders the REASON — never `$0.00`, never the principal"* |
| TC-6 *(negative)* | `A-11109 · Osei, Grace` — no deposit, nothing owed | MONEY renders **`—`**, which means *none* and is a **different claim** from an unreadable figure; the cell-level reasons ride in the title rather than as five paragraphs on every row | FE *"a row with NO money lines renders `—`, which means none and is a different claim"* |
| TC-7 | Any row carrying both positions | The payload names **four absences** (five with the interest one) and **nothing moves**: no refund is raised, no re-collection is possible (BR-CUS-023), the outgoing balance stays `$542.10`, and **zero journal lines** are written | `test_trf_money_states_the_four_absences_and_moves_nothing` |
| TC-8 *(TC-TRF-1)* | The ONE JOB contract | `exclusion.callout` is served and **rendered verbatim from the payload**, `exclusion.contract` is `transfers.EXCLUSION_CONTRACT` carried through, and `half_account_ids` is `transfer_half_account_ids()` **called, never re-derived** — so the set a Move-ins/Move-outs list must subtract is the SAME set this list was built from. Every account id on this list is in that set | `test_trf_the_list_publishes_the_exclusion_contract_and_never_re_implements_it` · FE *"§5.7.3 — the ONE JOB callout is drawn, and it is the SERVER's sentence"* |
| TC-9 | The KPI strip over §5.7.6's five rows | **2 · 1 · 1 · 1 · 3** — open (Park + Osei) · moving this week (Park's Aug 28; Osei's Sep 14 is not) · deposits carrying · arrears following · completed this month (Aug 02/05/09) | `test_trf_the_kpi_tiles_count_elections_not_figures` · FE *"§5.7.1 — the five drawn figures reach the strip"* |
| TC-10 | Somebody opens Osei's row without deciding anything | `DEPOSITS CARRYING` and `ARREARS FOLLOWING` stay at **1** — the tiles count the clerk's ELECTION, not a figure | `test_trf_the_kpi_tiles_count_elections_not_figures` |
| TC-11 | Search `Meadowbank` (the **target** address), then `Hillside` (the origin), then `Park`, then the account # | Each returns the one job — *"either address"* is §5.7.2's whole point, and the target half is the one a Move-outs list could never answer. `Nothing At All` returns 0 | `test_trf_search_finds_either_address_and_states_the_request_leg_absence` |
| TC-12 *(negative)* | A clerk types a request number, `SR-26-0047` | **Nothing matches, and the box never offered it** — `search.legs` is exactly `(customer, account_no, either_address)`, `search.unavailable` is **`[]`**, and the hint contains no *"request"*. That last assertion is the one that catches a later lane copying §5.7.2's drawn placeholder back in (BR-CUS-099) | `test_trf_search_finds_either_address_and_states_the_request_leg_absence` |
| TC-13 *(negative)* | Three transfers, `page=1&per=2` then `page=2&per=2` | 3 total, 2 pages, 2 + 1 rows, and **no row appears on both pages** — *"a row appeared on two pages — the order is not stable"* | `test_trf_the_list_paginates` |
| TC-14 *(negative)* | `GET /transfers` fails | The failure state renders with a retry — **never** the empty state, which would assert *"you have none"* | FE *"a failed read never renders the empty state — that would assert 'you have none'"* |
| TC-15 *(negative)* | The tenant has no transfers, so the empty state renders its `+ New transfer` CTA | Disabled with its reason — *"The transfer wizard is not built yet, so this cannot start here."* (BR-SHL-025 / law 2) | FE *"BR-SHL-025 / law 2 — the empty state's CTA is DISABLED with its reason"* |
| TC-16 *(isolation — tenant data)* ⛔ **NOT COVERED TODAY** | A Lone Star Ridge session calls `GET /transfers` while Brazos Bend holds all five jobs | **None of Brazos Bend's rows, and none of its tiles.** `list_queryset` filters `tenant_id=_tenant_id()`, `require_tenant` sets `app.tenant_id` and RLS `FORCE` is the law — but ⛔ **no test asserts it: `test_w7_worklists.py` names ONE tenant fixture (`brazos`) and has no cross-tenant case** (measured 2026-08-25). **A test is OWED**, and until it exists this row is a claim about the code, not a proven guarantee (hard-won law 1) | — **OWED** |
| TC-17 | The tab is mounted and opened | It **calls** `GET /transfers` — *"the endpoint is not merely mounted"* (law 2) | FE *"law 2 — the tab CALLS `GET /transfers`"* |
| TC-18 *(negative)* | Every column header is clicked | Nothing sorts — the server orders newest-first and takes no `sort`, and no column is declared sortable | FE *"no column is sortable — the server orders newest-first and takes no `sort`"* |
| TC-19 | Every string on the tab | No raw translation key reaches the screen; every call site carries a `defaultValue`. ⛔ **The search prompt is the declared exception** (as on S86) — the sentence owed is the server's amended `SEARCH_HINT`, *"Customer, account #, or either address…"*, and **the old four-leg wording must not come back** | FE *"no raw translation key reaches the screen — every call site carries a defaultValue"* |
| TC-20 *(NOT BUILT — recorded, not claimed)* | A clerk cancels a transfer, then looks for it | **It is gone.** `list_queryset` excludes `state=cancelled` — *"a cancelled job releases its account, because nothing about it happened"* — so there is no way to find one from this screen. Stated rather than discovered | — (REPORTED in `transfer_reads.py` §6; no id) |
| TC-21 *(NOT BUILT — recorded, not claimed)* | A clerk pages, searches, and reloads | The page and the search are lost; the URL is the Accounts page's. DEF-664's deliberate trade; **no test asserts it** — it holds by construction | — (**DEF-664**) |

**4 · Test Data** — Tenant **Brazos Bend Utilities** (`brazos`), actor **Marcus** (Billing Clerk, the `marcus` fixture `test_w7_worklists.py` uses). Rows = B18 §5.7.6's five, verbatim:

| From → to | Customer | Addresses | Out | In | Step | Money | State |
|---|---|---|---|---|---|---|---|
| A-10650 → A-11940 | Iversen, Britt | 18 Marten Row → 204 Quarry Lane | Aug 02 | Aug 02 | 5 of 5 | deposit carried $153.50 | Done |
| A-10714 → A-11996 | Haddad, Nour | 3 Kestrel Close → 71 Alder Street | Aug 05 | Aug 06 | 5 of 5 | deposit carried $150.00 | Done |
| A-10877 → A-12031 | Bianchi, Marco | 44 Larkspur Way → 88 Foundry Row | Aug 09 | Aug 12 | 5 of 5 | deposit carried $150.00 | Done |
| **A-11455 → A-12055** | **Park, Jenna** | 901 Hillside Ave → 26 Meadowbank Rise | Aug 28 | Sep 03 | **3 of 5** | deposit carried $154.20 · **arrear follows $542.10** | In progress |
| A-11109 → — | Osei, Grace | 12 Harbour View → 500 Main · 210 | Sep 14 | Sep 14 | 1 of 5 | — | Scheduled |

The five steps (`transfers.STEPS`, served as DATA so a sixth could not be silently restated): **1** find the account and confirm the customer · **2** find the new unit (vacant and reserved only) · **3** dates — out, in, and whether they are the same day · **4** money — deposit carry, arrears follow, final and opening reads · **5** review — both consequences, one commit.

**⚠ TWO FIGURES IN THAT TABLE ARE THE DRAWING'S AND ARE NOT THE PRODUCT'S — BR-CUS-102 governs.** §5.7.6 prints Park's deposit as **$154.20** while four other screens (and step 4, which shows its working, `150.00 + 3.50`) say **$153.50** — and `TRF-02.1` prints *"$150.00 + $4.20 interest"*. **The frozen pair is ❄️ WE-7 / GT-23: `$150.00` principal + `$3.50` interest = `$153.50`.** Park's **$542.10** arrear is the same balance the Accounts tab shows at `60+ past` — *"one customer, two tabs, one figure"* — and that cross-check must hold. Isolation fixture: a Lone Star Ridge tenant with its own transfers (**owed — see TC-16**). ⛔ **The five rows are not seeded yet** — task 7.12, a data lane's.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `FROM ACCOUNT`, line 1 | S89 col 1 (identity) | B18 §5.7.2 | `transfers.from_account → accounts.account_no` | text | system-derived | always present |
| `FROM ACCOUNT`, line 2 | S89 col 1 | B18 §5.7.2 · TC-TRF-2 | `transfers.to_account → accounts.account_no`, else the literal **`→ —`** written by `transfers._serialize` | text | system-derived | **never blank, never null** — one authority for the dash |
| `CUSTOMER` | S89 col 2 | B18 §5.7.2 · BR-CUS-054 | `customers.display_name` + `.customer_no`, via the `customer_accounts` link | text | computed-display | the ENTITY, never a contact on the account |
| `FROM → TO` | S89 col 3 | B18 §5.7.2 (*"either address is the whole point"*) | `accounts.unit_id` and `transfers.to_unit_id` → metering's `selectors._premise_cell` (⚠ cross-module READ) | text | computed-display | `to` null before step 2 → `to_absence.reason = "target_unit_not_chosen_yet"`, rendered **in words** |
| `OUT DATE` / `IN DATE` | S89 cols 4–5 | B18 §5.7.2 · §5.7.4 | `transfers.out_date` / `.in_date` | date | user-input | nullable → `—`; same-day is normal (three of the five drawn rows) |
| `STEP` | S89 col 6 | B18 §5.7.2 (*"(of 5)"*) | `f"{transfers.step} of {transfers.STEP_COUNT}"`, built **server-side** from the writer's own constant | text | computed-display | the step's NAME is the tooltip — the column is one cell wide |
| `MONEY` → `lines[]` | S89 col 7 | B18 §5.7.2 (*"stacks up to two sentences"*) | `accounts.deposit_on_file` + BR-CUS-057 accrual (⛔ **unbuilt**) · `accounts.balance` (a **CACHE**, BR-CUS-015) | `{stored, display}` USD, or **both null** | computed-display | ⛔ **never `$0.00`, never the principal.** Stored 4 dp / displayed 2 dp, rounded **once, server-side**; the screen never re-rounds |
| `MONEY` → `lines[].tone` | S89 col 7 | B18 §5.7.2 (*"in **amber**"*) | not stored — `LINE_TONE = {deposit: ink, arrear: amber}` served as DATA | enum | reference-data | an unrecognised tone renders as ordinary ink, **never as nothing** |
| `MONEY` → `unavailable[]` | S89 col 7 | OQ-365 · BR-CUS-015/024/025/057 · hard rule 5 | not stored — `transfers._unavailable_for(statement)`, carried through **verbatim** | dicts | computed-display | this module authors **no** explanation of its own about money |
| `STATE` | S89 col 8 | B18 §5.7.6 | `transfers.state` (`scheduled` · `in_progress` · `done` · `cancelled`) | enum | system-derived | ⚠ tone is the **SCREEN's**; B18 draws none. ⛔ **`cancelled` is never listed** |
| `exclusion.callout` / `.contract` / `.half_account_ids` | S89 panel | B18 §5.7.3 · BR-CUS-086 | `transfers.EXCLUSION_CONTRACT` + `transfer_half_account_ids()` — **called, never re-derived** | text / ids | computed-display | the sentence a clerk reads IS the contract a Move-ins list must meet |
| KPI ×5 | S89 strip | B18 §5.7.1 | `transfers.committed_at` (open / completed-this-month) · `.out_date` (moving this week) · `.deposit_carry_elected` / `.arrears_follow_elected` (the two elections) | int | computed-display | `period_basis` and `as_of` served as DATA (BR-TEN-043) — no clock is picked silently |
| Search: `request #` | S89 toolbar | B18 §5.7.2 (drawn) | ⛔ **GAP, RULED AWAY — `transfers` has no service-request column and no join.** `connections.service_request_id` is the shape it would take (one nullable column) | — | — | **BR-CUS-099** — the leg is gone, `search.unavailable` is `[]` |
| Column preference key | S89 | BR-SHL-013 | `user_preferences` key `table.S89.columns` (`TableConfig.screenId = "S89"`) | jsonb | system-derived | identity column unhideable |
| Page / search state | S89 | BR-SHL-011 · **DEF-664** | ⛔ **GAP — nowhere.** Component state only | — | user-input | does not survive a reload |
| Audit | — | CLAUDE.md #7 | **none — this screen writes nothing and moves no money** | — | — | read-only surface |

**6 · Acceptance**

- **Given** §5.7.6's five jobs, **Then** the eight drawn columns render each one, Park reads `3 of 5` with both money sentences, and the strip reads **2 · 1 · 1 · 1 · 3**.
- **Given** a transfer at step 1, **Then** the FROM cell's second line reads **`→ —`** and the target address is stated as a stage of the job in words.
- **Given** a deposit whose carried figure cannot be read, **Then** the line renders **the server's reason** and **neither `$0.00` nor `$150.00`** appears anywhere in the cell.
- **Given** a row with no positions at all, **Then** it renders `—`, which is a different claim and looks different.
- **Given** any row, **Then** the payload names why nothing moves, and **zero journal lines** exist for the transfer.
- **Given** the ONE JOB callout, **Then** it is the server's own sentence, and `half_account_ids` is the same set a future Move-ins list must subtract.
- **Given** a request number typed into the search box, **Then** nothing matches and the box never offered it.
- **Given** a Lone Star Ridge session, **Then** no Brazos Bend row or tile is reachable — ⛔ **and a test asserting it is OWED.**
- **Given** any further work on this story, **Then** OQ-365 is **not** answered by choosing a value, and no figure is invented to fill a refused line.

**7 · Finance Calculation** — **N/A: this screen computes no money.** It **displays** two positions and may refuse either, and the refusal is the rule:

```
deposit_carried  = accounts.deposit_on_file + BR-CUS-057 accrued interest
                 = UNREADABLE while the accrual engine is unbuilt  →  line emitted, figure NULL
arrear           = accounts.balance                                →  a CACHE (BR-CUS-015), named as such
movement         = none. 0 journal lines, no refund, no re-collection (BR-CUS-023 refuses the field)
```

**Worked, and it is the reason `$0.00` is banned rather than merely discouraged** (❄️ **WE-7 / GT-23**, frozen): a held deposit of **`$150.00`** at the tenant's rate accrues **`$3.50`**, so the carried position is **`$153.50`**. Reading the unwired interest term as `0.00` serves **`$150.00`** — *"it serves the principal AS the carried amount and keeps $3.50 of the customer's money."* Serving `$0.00` instead is DEF-127's *"looks exactly like a settled account"*. **Both are forbidden; the absence is served instead.** GT ref: **GT-23** — cited as the frozen pair that makes the error measurable, **not** as a calculation this screen performs.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-365 | **When a customer transfers between units, do the deposit and the arrears move gross, or does the close settle first?** (A) settle first, as a close — BR-CUS-025/081 hand `$388.60` across with no deposit and BR-CUS-082 then chases it at TIER 1, against a customer who has not left · (B) move gross, as §5.7.6 draws and task 7.3 states — *"Deposit carries WITHOUT a refund-and-recollect; arrears follow"* — but **no posting path exists** for it either. | What the money cell may **DO**. It does not block what it may **SAY**: the list, both figures and their absences ship | Product Owner (chat session) | **OPEN — non-blocking.** Nothing moves and the statement says so |
| — *(no OQ minted by this story)* | Every gap S89 carries already has an id or is a stated, deliberate exclusion. **This story mints nothing** (see US-MET-021 §8 for the reasoning). | — | — | — |
| ⛔ **OWED, no id** | **No cross-tenant test exists for this list** (TC-16). `test_w7_worklists.py` names one tenant fixture. The scoping is in the code and in RLS; **the assertion is missing**, and hard-won law 1 says a guarantee nothing checks is a note, not a guarantee. | Nothing shipped — it is a test gap, not a behaviour gap | Eng Lead, via a test this lane may not write | **REPORTED — a test is OWED** |
| ⛔ **OWED, no id** | **A test's NAME is now stale.** `test_trf_search_finds_either_address_and_states_the_request_leg_absence` asserts `search["unavailable"] == []` since BR-CUS-099 withdrew the absence — the body is correct and current, the name still promises an absence that no longer exists. A reader grepping for the request-leg behaviour finds a name that contradicts the ruling. | Nothing | Eng Lead | **REPORTED — a rename is OWED** |
| ⛔ **NOT BUILT, no id** | **`TRF-02.1…5`, the five-step transfer wizard.** B18 §3 maps S89 as *"Transfers tab — list **+ 5-step wizard**"* and §5.7.7 captures all five screens; **only the list half of the id is built.** The empty-state CTA is disabled with that reason. | Starting a transfer from this screen | already scoped out of this epic | **OUT OF SCOPE — recorded so the id is not read as complete** |
| **DEF-664** | Page/search state does not survive a reload (TC-21). The fix is namespacing the list params — **BR-SHL-011's to settle, not a lane's**. | Shareability of S89's list state | already filed | **FILED** |

---
id: US-CUS-028
epic: EP-CUS-08
module: customers
screens: [S90]
wave: 7                  # CR-030 W7 (`2.48.0`) — NOT B12's wave 7
status: blocked
blocked_by: [OQ-374]     # the segment strip and the chip cell; the list, the tiles and the columns are BUILT
depends_on: [US-CUS-015, US-CUS-005, US-PAY-011]
journeys: [J08]          # step 2b — "a green assertion naming either party is a FAILURE"
rules: [BR-CUS-039, BR-CUS-043, BR-CUS-053, BR-CUS-082, BR-CUS-097, BR-CUS-098, BR-CUS-100, BR-CUS-101, BR-NOT-005, BR-PAY-017, BR-TEN-043, BR-SHL-010, BR-SHL-011, BR-SHL-012, BR-SHL-013, BR-SHL-023, BR-SHL-025]
golden_tests: []
finance_calc: none       # the OWED column is the ledger's figure, DISPLAYED; nothing here computes money
---
### US-CUS-028 — The disconnects worklist: the ladder, its protections, and the column that makes no delivery claim

**1 · Details** — As a **collections clerk**, I want the Accounts screen's **Disconnects** tab to list every account on the ladder **and** every account a protection is holding — with what is owed, which tier or which hold it is under, when the cut is scheduled, when the last notice was issued and what state it is in — above a five-tile strip, so that I can work the ladder from one screen instead of a notice modal (B18 §5.8: *"Today this is a notice modal and nothing else — no list, no ladder, no protections gate"*).

**Entry:** S17 Accounts → tab **Disconnects** (`AccountsListPage.tsx`; the tab mounts `DisconnectsTab`). Embedded, no query string (DEF-664). **Exit:** none — there is no disconnect detail screen and no route into the five-step flow.

**What it calls:** `GET /disconnects` → `apps/customers/api.disconnects_list` → `disconnect_reads.list_disconnects(segment, q, page, per, as_of)`, gated `AdminOrClerk` for the same reason S89 is.

**⚠ THE ROW SET IS A UNION, AND THE UNION IS DRAWN, NOT CHOSEN:** open disconnect cases **∪** accounts with a protection in force. §5.8.6's `A-11902 · Okafor` sits on the tab at `HELD · MEDICAL` owing `$948.20` with **no cut date and no last notice** — an account that never entered the ladder — so a list of cases alone would be missing three of the nine drawn rows. A union is also the safe shape while OQ-374 is open: it can only ever show a row that belongs under one reading, **never hide one**. Cases in `stopped` or `restored` are excluded, because §5.8.3 says the row *"leaves this list"*.

**⚠ `halt_reason` IS RECOMPUTED ON EVERY ROW, EVERY READ, AND IS NOT MEMOIZED.** The writer's own words: *"a RUN cached on a row outlives the debt."* That is what makes TC-DSC-1 true on this list — the customer who pays leaves it on the next read, **with nothing cancelled by hand** (§5.8.3: *"STOPS ITSELF"*). The OWED column is a different matter and IS read once for the page, because it is a display figure and not a decision.

**⛔ `LAST NOTICE` MAKES NO DELIVERY CLAIM — DEF-692 / BR-CUS-100.** §5.8.2 draws the column as `emailed` · `posted` · `certified sent` · `certified signed` · `—`, and **the same section carries the design's own warning against it**: *"There is no email, SMS or print adapter in this release … This column is drawn against a capability that does not exist, and a lane must render the absence rather than fabricate a delivery state."* So the cell renders **two facts and nothing else** — which TIER the notice was, and the DATE it was issued — with `delivery_state` written NULL by the writer, read NULL here, and the reason travelling with the cell. **There is deliberately no map from a delivery state to a label anywhere in `DisconnectsTab.tsx`**, and that ABSENCE FROM THE SOURCE is what makes the guarantee checkable rather than promised (hard-won law 1). **BR-CUS-100 half-settles it** — the SEND is in-app, through the ordinary notification queue — **and the other half is not settled by it:** proof of service is a legal artefact produced outside this product, `disconnect_notices` cannot hold it today, and *"a tier-3 cut must not be schedulable on an unrecorded service."*

**⛔ AND NOTHING ADVANCES THE LADDER ON A SCHEDULE — DEF-320.** `NO_SCHEDULER` rides on every ladder answer this list serves: *"no runner, job, queue or timer in this product reads a date and acts on it (measured 2026-08-25) … `next_step_due` is a STORED DATE THAT NOTHING WATCHES. A tier advances when something calls `advance()`, and today that is a test or a screen."*

**⛔ `$0.00` IS FORBIDDEN AS A FABRICATION AND REQUIRED AS A FACT, ON THE SAME COLUMN.** DEF-127: a fabricated `$0.00` *"looks exactly like a settled account"* — and on THIS tab it looks like an account nobody should be chasing — so when the ledger reading fails, `owed.display` is null and the cell renders **the server's reason as a sentence**. But **`A-11507` genuinely owes `$0.00` and is on this tab** (TC-DSC-8 — paid, awaiting a reconnection visit), so a real zero and an unreadable figure both appear here and **must look different**. That is exactly why the absence is a sentence and not a dash.

**⛔ NO ROW NAMES A CHASED PARTY — OQ-366.** BR-CUS-082 restarts the ladder at TIER 1 on a debt that survived closure; BR-CUS-097 moves a sub-account's residue to its MASTER; **neither says whose door the letters go to.** `restart_after_closure()` takes no `subject` and no `tier` parameter, so both readings are **unrepresentable rather than merely discouraged**, and this list must not undo that by inference: `subject` is `None` on every row, a collections-sequence row carries `chase_subject_unresolved` **out loud rather than by omission**, and the CUSTOMER column states the account the debt was measured on — a fact about the row, never a claim about who is pursued. **J08 step 2b: *"a green assertion naming either party is a FAILURE."***

**⛔ FIVE OF SIX SEGMENTS ARE OFF, AND ONE CELL MAY WEAR TWO CHIPS — OQ-374.** The two facts underneath are **independent axes**: `On hold` is COMPUTED from `account_protections` (`disconnects.STATE_ON_HOLD` is declared, is in migration `0022`'s CHECK vocabulary, and is **assigned nowhere in this repository** — measured 2026-08-25), while `At notice` · `Due to cut` · `Cut` · `Reconnecting` are the stored `disconnect_cases.state`. §5.8.3's ladder diagram draws exactly that path (`T1 · T2 · T3 -.-> HOLD`), so it is designed rather than accidental, and §5.8.6's fixture never shows the collision — **the drawing cannot be read for an answer.** So `segment=all` is served, the other five are **disabled with the server's own sentence**, the STATE cell serves **both axes** with `one_cell_is_unresolved` on a collision, and the TIER cell serves **every applicable chip in the drawn order** with `ambiguous: true`. *"Picking one would be inventing a precedence; dropping the others would hide a protection from a screen that authorises a cut."*

**2 · Business Rules**

| BR | Statement | Status |
|---|---|---|
| BR-CUS-039 | The three ladder tiers, certified on the final one; medical-hold accounts excluded. `disconnects.ladder_tier_of(case)` is **THE one place that answers "which tier"** — this list calls it and respells nothing. | CONFIRMED |
| BR-CUS-043 | An **active AND current** payment plan pauses dunning and disconnect. Read from payments on every call (`LIFETIME_DERIVED`) — a stored date cannot answer it. | CONFIRMED |
| BR-CUS-098 | **When a protection lapses, the ladder RESTARTS AT TIER 1.** PO 2026-08-25, verbatim *"Back to tier 1"*, closing DEF-689. ⛔ **`TC-DSC-3` in B18 §5.8.5 states the OPPOSITE** (*"resumes where it was, not from tier 1"*) and is **WRONG AS WRITTEN AND SUPERSEDED** — left visible in B18 rather than deleted, *"because a test case stating the opposite of a signed rule is how the wrong thing gets built"*. **Worked cost, on the record:** a customer at `TIER 3 · 48-HOUR` who produces a medical certificate receives **three more notices** (reminder → 10-day → certified) — roughly **eighteen further days** on the drawn intervals — before a cut can be scheduled again. | CONFIRMED — PO 2026-08-25 |
| BR-CUS-100 | **A disconnect notice travels the notification queue and is delivered IN-APP; certified mail is RECORDED as proof of service, never CLAIMED as a send.** PO 2026-08-25, verbatim: *"you amke the provision and send in app messages - we discussed this before"*. ⛔ **The proof half is schema-owed:** `disconnect_notices` carries no proof reference, served-at date or serving channel, so **`delivery_state` stays NULL with its reason** and *"a tier-3 cut must not be schedulable on an unrecorded service."* | CONFIRMED (the channel) · **schema OWED (proof of service)** |
| BR-CUS-101 | **Three protections are the release; the other seven are a clerk's job until they are built.** PO 2026-08-25, verbatim: *"3 is okay to start with"*. `DSC-02.2` draws ten; medical certificate, active payment plan and weather moratorium are built. ⚠ **The tier-3 letter promises a right to dispute that no machine guard checks** — a promise held by a person, and the distinction *"belongs on the record rather than in somebody's memory"*. | CONFIRMED (three) · **the seven deferred; the tick's meaning OWED** |
| BR-CUS-082 | A debt surviving closure is **still chased** and the ladder restarts at TIER 1. | CONFIRMED — PO 2026-08-24 |
| BR-CUS-097 | A sub-account's unpayable residue moves to its **MASTER**. Its *"who is chased"* half is **OPEN** (OQ-366). | CONFIRMED (the move) · **OPEN (the party)** |
| BR-NOT-005 | A notice is **WRITTEN**; only the dispatcher sends. This is the rule `DELIVERY_UNAVAILABLE` cites, and the reason a NULL `delivery_state` is correct rather than missing data. | CONFIRMED |
| BR-PAY-017 | Payments' own dunning rungs, one of which — `second_5_day` — **B18 §5.8.2 draws no chip for**. Mapping it onto TIER 2 shows a customer at the 5-day notice as though they were at the 10-day one; onto TIER 3, as though a 48-hour certified letter had gone out. *"Both are statements to a regulator about what a customer was told, so neither is made"* and the cell renders `unmapped_rung`. ⛔ **A RULING IS OWED: either §5.8 grows a fourth chip or BR-PAY-017 loses a rung.** | CONFIRMED (the rungs) · **the chip mapping OWED** |
| BR-CUS-053 | The four search legs, each through the reader that already owns it — metering's `unit_ids_matching` (address), assets' `unit_ids_for_asset_search` (meter #), customers' own contact-name read — *"so the Disconnects box finds exactly what the Accounts box finds."* | CONFIRMED |
| BR-SHL-023 | **ONE money formatting path, one currency symbol.** `owed.display` is the server's already-2-dp string and `MoneyCell` prints it without re-rounding (idempotent: `min == max == 2`). | CONFIRMED |
| BR-TEN-043 | The event date is an argument, never a wall clock; `as_of` defaults to `seams.tenant_today()`. `DUE TO CUT THIS WEEK` is inclusive at both ends and **forward-looking only** — ⚠ **a scheduled cut whose date has PASSED is neither accented nor counted**, which is what the caption says and *"is not obviously what a clerk wants"*; stated rather than quietly widened. | CONFIRMED (the rule) · the forward-only window **PROPOSED** — derivation of §5.8.1's caption |
| **The tiles OVERLAP by design; the segments may not** | `AT NOTICE`'s four INCLUDE the two scheduled rows `DUE TO CUT THIS WEEK` also counts — *"somewhere on the ladder"* is the caption's own word for it, and 4 + 2 + 3 + 1 + 1 = **11 over nine rows**. A KPI is a count and may double-count; a SEGMENT is a place a row LIVES, which is why the segments are what OQ-374 blocks and the tiles are not. | **PROPOSED** — derivation of §5.8.1's captions against §5.8.6's nine rows |
| **`CUT, AWAITING PAYMENT` does not print its drawn caption** | §5.8.1 writes *"still accruing base charges"* and calls it *"a money statement: the meter is off and the base charge is not."* ⚠ **RULED 2026-08-25 — BR-CUS-103 (PO, closing OQ-380): base charges STOP at the cut.** The caption is therefore not withheld as unverified; it is withheld because it is **FALSE**, and the tile says what the figure IS — a count of cases in the `cut` state. The absence was renamed to `CUT_ACCRUAL_CAPTION_SUPERSEDED` / `cut_accrual_caption_superseded` on 2026-08-25 (**DEF-716**), on both sides of the stack in one commit, and `06-backend/tests/test_def_716_cut_accrual_caption.py` pins the two halves. ⚠ It still makes **no claim about what those customers owe** — the reconnection fee does not reach the balance (DEF-708, open). | ✔ **RULED (BR-CUS-103, 2026-08-25) · copy fixed under DEF-716** |
| BR-SHL-010 / 011 / 012 / 013 / 025 | The shared list contract, as on S86 and S89 — including **a failed read never renders the empty state**, which here would assert *"nobody is on the ladder"*. Column prefs key on `screenId = "S90"`. | CONFIRMED (each) · the embedded-URL exception **PROPOSED** — DEF-664 |
| CLAUDE.md hard rules 1, 2 *(cited, not restated)* | Tenant scoping under RLS FORCE · money stored 4 dp / displayed 2 dp, rounded once server-side. | CONFIRMED — hard rules |
| OQ-374 | **When a disconnect case is both on a tier and protected, which segment holds it and which chip does it wear?** | **OPEN — blocking S90's six segments and its chip cell** |
| OQ-366 | **When a sub-account's residue moves to its master, who does the ladder chase?** | **OPEN — no row names a party** |

**3 · Test Cases**

*(Backend: `06-backend/tests/test_w7_worklists.py`. Frontend: `07-frontend/src/features/customers/DisconnectsTab.test.tsx`.)*

| TC | Scenario | Expected | Asserted by |
|---|---|---|---|
| TC-1 | Clerk opens Accounts → **Disconnects** with §5.8.6's nine rows seeded | The eight drawn columns render `A-11812 · Bramble Bakery`: owed **$2,410.00**, chip `TIER 2 · 10-DAY`, no cut date, last notice present, state `Notice sent` | `test_dsc_the_list_paginates_and_serves_b18s_columns` · FE *"§5.8.2 — the eight drawn columns render §5.8.6's Bramble Bakery row"* |
| TC-2 | The six tier chips | Exactly **six** — `TIER 1 · REMINDER` · `TIER 2 · 10-DAY` · `TIER 3 · 48-HOUR` (accent) · `HELD · MEDICAL` · `HELD · PAYMENT PLAN` · `HELD · WEATHER MORATORIUM` (grey) — in B18's drawn order, **and the `—` is an ABSENCE, not a seventh chip** | `test_dsc_there_are_exactly_six_tier_chips_and_the_dash_is_not_one` · FE *"the chip tones are the server's decision, applied and not re-derived"* |
| TC-3 *(TC-DSC-2, TC-DSC-4)* | A ladder chip and a HELD chip, from real rows | Both render with the server's tone; a medical certificate on file produces `HELD · MEDICAL` and the ladder is frozen | `test_dsc_a_ladder_chip_and_a_held_chip_render_from_real_rows` |
| TC-4 *(negative — OQ-374, the chip)* | `A-11812` is at `TIER 2 · 10-DAY` owing **$2,410.00** and files a medical certificate | **BOTH chips render**, in the drawn order, with `ambiguous: true` and a *"two apply"* note — **never one ranked over the other, and never one dropped.** *"Picking one would invent a precedence; dropping one would hide a protection from a screen that authorises a cut"* | `test_dsc_chips_are_a_list_and_no_precedence_is_invented` · FE *"⛔ OQ-374 (the chip) — two applicable chips are BOTH rendered and flagged, never ranked"* |
| TC-5 *(negative)* | A row with no tier at all — `A-11507`, and separately an account on payments' `second_5_day` rung | The `—` says **WHICH** absence it is: `no_tier_reached` (nothing sent; the row is here for a protection, a cut awaiting payment or a reconnection visit) versus `unmapped_rung` (a rung B18 draws no chip for). **The two causes are distinguishable** | `test_dsc_a_row_with_no_tier_renders_the_dash_as_an_absence` · FE *"the TIER `—` says WHICH absence it is, and the two causes are distinguishable"* |
| TC-6 | The six segments | Exactly six, in B18 §5.8.2's drawn order, labelled verbatim | `test_dsc_there_are_exactly_six_segments_in_b18s_drawn_order` |
| TC-7 *(negative — OQ-374, the segment)* | `GET /disconnects?segment=at_notice` | **Refused by name.** The selector raises `NotImplementedError` carrying the question **in full and with no invented OQ id**, and the API turns it into a readable `ValidationError` (`message_key="customers.disconnects.segment.unavailable"`) — *"a clerk must not meet it as a stack trace"*. ⚠ **This differs from S86's sibling refusal, which surfaces as a ≥500** — see §8 | `test_dsc_only_the_all_segment_is_served_and_an_open_question_is_owed` |
| TC-8 *(negative)* | The screen renders the strip | Six tabs, `All` selected, **five disabled carrying the server's own sentence**, and **the route is never called to discover the refusal**. Before the first response the strip holds only `All` | FE *"⛔ OQ-374 — six segments are drawn, FIVE are DISABLED with the reason, and the route is never asked"* · FE *"the segment strip holds only `All` before the first response"* |
| TC-9 *(TC-DSC-6 — the delivery one)* | Any row carrying a notice | The cell renders **the tier and the issued date only**. `delivery_state` is NULL, `DELIVERY_UNAVAILABLE` rides with the cell, and **no notice is ever recorded or rendered as `emailed`, `posted`, `certified sent` or `certified signed`** — there is no map from a delivery state to a label in the source, which is the checkable form of the guarantee | `test_dsc_last_notice_never_claims_a_delivery` · FE *"⛔ TC-DSC-6 — no delivery claim appears anywhere on the tab"* |
| TC-10 | A row with no notice at all (§5.8.6's three HELD rows) | `—`, **and the delivery reason still travels with the cell** — so a clerk expecting a channel learns why there is none instead of reading a gap as lost data | FE *"a notice-less row draws `—` and still carries the delivery reason"* |
| TC-11 *(negative — DEF-127)* | The ledger reading for OWED fails | The cell renders the server's **reason as a sentence** — never `$0.00`, never a dash. *"A dash would read as 'nothing owed' on the one screen where that is the most expensive thing to say wrongly"* | `test_dsc_owed_states_its_absence_and_never_fabricates_a_zero` · FE *"⛔ DEF-127 — an unreadable OWED renders the reason, and never `$0.00`"* |
| TC-12 *(TC-DSC-8)* | `A-11507` genuinely owes **$0.00** and is `Reconnecting` at tier `—` | It renders as **money** — a real `$0.00` — so the two absences cannot be confused with each other or with a settled account | FE *"TC-DSC-8 — a REAL `$0.00` renders as money, so the two absences cannot be confused"* |
| TC-13 | `A-11340` is due to cut **Aug 24** and `A-11720` **Aug 26** | Both take the **accent**, and the accent is a **fact about the date decided by the SERVER** (`cut_date_is_this_week`) — re-deriving it in the screen would put a second calendar in the product. Inclusive at both ends, forward-looking only | `test_dsc_cut_date_is_accented_only_within_seven_days` · FE *"§5.8.2 — CUT DATE takes the accent when the SERVER says it is this week"* |
| TC-14 *(TC-DSC-1)* | A customer pays in full at TIER 2 | The ladder **stops automatically** and the row leaves the list on the next read — **nothing is cancelled by hand**. `halt_reason` is recomputed per row, per read, precisely so *"the customer who paid on Friday"* does not get *"a certified letter on Monday"* | `test_dsc_the_halt_reason_is_recomputed_on_every_read` |
| TC-15 *(negative — OQ-366)* | A collections-sequence row, after a sub-account's residue moved to its master | **`subject` is `None`** and `chase_subject_unresolved` is served **out loud**; the CUSTOMER column states the account the debt was measured on and **no party is named anywhere.** J08 step 2b: *a green assertion naming either party is a FAILURE* | `test_dsc_no_row_names_the_chased_party` · FE *"⛔ OQ-366 — no row names a chased party"* |
| TC-16 | The KPI strip over §5.8.6's nine rows | **4 · 2 · 3 · 1 · 1** — and they **overlap by design**: `AT NOTICE`'s four include the two scheduled rows `DUE TO CUT` also counts (4+2+3+1+1 = 11 over 9). The union hides nothing | `test_dsc_the_kpi_tiles_overlap_by_design_and_the_union_hides_nothing` · FE *"§5.8.1 — the five drawn figures reach the strip…"* |
| TC-17 *(negative)* | The `CUT, AWAITING PAYMENT` tile | It does **not** print §5.8.1's drawn caption *"still accruing base charges"* — the tile says what the figure is (cases with the service off) and `CUT_ACCRUAL_CAPTION_SUPERSEDED`'s reason rides in the title. ⚠ **THE REASON CHANGED ON 2026-08-25 AND THE CELL DID NOT (DEF-716).** It read *"because whether a cut account keeps accruing is **billing's** behaviour and no rule states it"* — true when written, and **BR-CUS-103 (PO 2026-08-25, closing OQ-380) states it**: base charges **STOP** at the cut. So the caption is withheld because it is **FALSE**, not because it is unverified — a different sentence with a different fix, which is the whole of DEF-716 | `06-backend/tests/test_def_716_cut_accrual_caption.py` · FE *"…and the CUT tile does not print its caption as fact"* |
| TC-18 | Search `Sandoval`, then `A-11655`, then the service address, then a meter # | Each leg matches through the reader that owns it; a term shorter than `MIN_SEARCH_CHARS` means *"too short to search on"*, **not** *"no matches"* | `test_dsc_search_covers_customer_account_and_address` |
| TC-19 *(negative)* | The nine rows, `per=2` | Paginated with a **stable** boundary (`account_no`, then `id`), and B18's eight columns served as DATA. ⚠ **The order is deliberately NOT urgency** — ranking `At notice`, `Due to cut` and `On hold` is the same unruled precedence OQ-374 refuses | `test_dsc_the_list_paginates_and_serves_b18s_columns` · FE *"no column is sortable — the order is the server's and is deliberately not urgency"* |
| TC-20 *(negative)* | The STATE cell on a row that is both at `notice_sent` and protected | **Both axes render** — `stored` and `held_by` — with `one_cell_is_unresolved: true` and the reason attached. **Never a silent winner.** §5.8.6's nine rows all have exactly one of the two, so the drawn screen renders unchanged | FE *"§5.8.2 — the STATE cell serves BOTH axes and marks the collision rather than picking one"* |
| TC-21 *(negative)* | `GET /disconnects` fails | The failure state renders with a retry — **never** the empty state, which here would assert *"nobody is on the ladder"* | FE *"a failed read never renders the empty state — that would assert 'nobody is on the ladder'"* |
| TC-22 *(negative)* | Nobody is on the ladder, so the empty state renders its `Start a disconnect` CTA | **Disabled with its reason** — §5.8.4 step 5 is a **danger-tier commit** and the flow has no route: *"a live button onto nothing is bad; a danger one is worse"* | FE *"BR-SHL-025 / law 2 — the empty state's CTA is DISABLED with its reason (a danger commit onto nothing is worse)"* |
| TC-23 *(isolation — tenant data)* ⛔ **NOT COVERED TODAY** | **TC-DSC-9, drawn in B18 §5.8.5:** tenant B calls `GET /disconnects` | **None of tenant A's.** `disconnects_list`'s own docstring names this case — *"the selector filters on `app.tenant_id` and `require_tenant` is what sets it"* — and the union, the protections query and the ledger read are all tenant-scoped under RLS FORCE. ⛔ **But no test asserts it: `test_w7_worklists.py` names ONE tenant fixture** (measured 2026-08-25). **A test is OWED**, and until it exists this is a claim, not a proven guarantee | — **OWED** (B18 draws it as TC-DSC-9) |
| TC-24 | The tab is mounted and opened | It **calls** `GET /disconnects` — *"the endpoint is not merely mounted"* (law 2) | FE *"law 2 — the tab CALLS `GET /disconnects`"* |
| TC-25 | Every string on the tab | No raw translation key reaches the screen. ⚠ **Two slots, two keys:** the chip cell's *"two apply"* fragment is `…tier.ambiguousShort`, **not** `…tier.ambiguous`, which already holds the backend's full refusal sentence and would put a paragraph where a two-word fragment belongs on every ambiguous row | FE *"no raw translation key reaches the screen — every call site carries a defaultValue"* |
| TC-26 *(NOT BUILT — recorded, not claimed)* | Anyone waits for TIER 1 to become TIER 2 on its due date | **Nothing happens.** `NO_SCHEDULER` (DEF-320): no runner, job, queue or timer in this product reads a date and acts on it; `next_step_due` is a stored date nothing watches. The absence is served on every ladder answer this list returns | — (**DEF-320**, carried in the payload) |
| TC-27 *(NOT BUILT — recorded, not claimed)* | A clerk pages, searches, and reloads | The page and the search are lost (DEF-664's trade); **no test asserts it** — it holds by construction | — (**DEF-664**) |

**4 · Test Data** — Tenant **Brazos Bend Utilities** (`brazos`), actor **Marcus** (Billing Clerk). Rows = B18 §5.8.6's nine, verbatim — ⚠ with `LAST NOTICE` shown as **DRAWN**, which the product deliberately does **not** render (BR-CUS-100):

| Account | Customer | Owed | Tier | Cut date | Last notice *(drawn — NOT rendered)* | State |
|---|---|---|---|---|---|---|
| A-11507 | Greaves, Tom | **$0.00** | — | Aug 12 | certified signed | Reconnecting |
| A-11488 | Doyle, Patrick | $612.75 | — | Aug 18 | certified signed | **Cut** |
| **A-11340** | **Northwind Mfg.** | **$8,240.00** | TIER 3 · 48-HOUR | **Aug 24** | certified signed | **Scheduled** |
| A-11720 | Calloway, Brett | $1,204.50 | TIER 3 · 48-HOUR | **Aug 26** | certified sent | Scheduled |
| A-11812 | Bramble Bakery | $2,410.00 | TIER 2 · 10-DAY | — | posted | Notice sent |
| A-11780 | Whitfield, Dana | $318.60 | TIER 1 · REMINDER | — | emailed | Notice sent |
| A-11902 | Okafor, Emmanuel | $948.20 | HELD · MEDICAL | — | — | On hold |
| A-11655 | Sandoval, Rita | $205.40 | HELD · PAYMENT PLAN | — | — | On hold |
| A-11933 | Iqbal, Nadia | $402.15 | HELD · WEATHER MORATORIUM | — | — | On hold |

**Cross-tab agreement that must hold** (§5.8.6): `A-11340` appears here, on Accounts as `Marked disconnect`, and on Move-outs at step 1 of 4 — **the same account, three tabs, one figure**. `A-11780` appears here at TIER 1 and on Move-outs with an estimated read. Additional fixtures this story needs: an account at `notice_sent` **that also files a medical certificate** (TC-4/TC-20's collision — §5.8.6 never draws one) · an account on payments' `second_5_day` rung (TC-5's `unmapped_rung`) · a forced ledger-read failure (TC-11) · a collections-sequence case after a residue move (TC-15) · a second tenant (TC-23, **owed**). ⛔ **The nine rows are not seeded yet** — task 7.12, a data lane's. ⚠ **BR-CUS-102 applies to every figure above:** these are the prototype's samples; where the product computes, the product wins.

**5 · Data Fields / Mapping**

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| `ACCOUNT` | S90 col 1 (identity) | B18 §5.8.2 | `accounts.account_no` | text | system-derived | the row id is `account_id` — a row may exist with no case at all |
| `CUSTOMER` | S90 col 2 | B18 §5.8.2 | `selectors.primary_contact_name(account)` — the same cell S17 renders, *"so one account reads one way on both tabs"* | text | computed-display | ⚠ **a fact about the row, NEVER a claim about who is chased** (OQ-366) |
| `ADDRESS` | S90 col 3 | B18 §5.8.2 | `accounts.unit_id` → metering's `selectors._premise_cell` (⚠ cross-module READ) | text | computed-display | `—` when absent |
| `OWED` | S90 col 4 | B18 §5.8.2 | **the LEDGER's figure** via `seams.ar_positions(ids)` — ONE read for the page (DEF-127's posture), formatted by `disconnects._money` | `{stored 4dp, display 2dp}` + `currency` | computed-display | ⛔ **null on a failed read → the REASON renders, never `$0.00`.** A real `$0.00` renders as money (TC-DSC-8) |
| `TIER` → `chips[]` | S90 col 5 | B18 §5.8.2 (six chips) | `disconnects.ladder_tier_of(case)` + `protections_for(account)` → `CHIP_FOR_PROTECTION` | list of `{code,label,tone}` | computed-display | ⚠ **a LIST, in the drawn order, with `ambiguous` flagged** — nothing chosen, nothing dropped (OQ-374) |
| `TIER` → `unavailable[]` | S90 col 5 | BR-PAY-017 · B18 §5.8.2 | not stored — `CHIP_ABSENCE_NO_TIER` / `CHIP_ABSENCE_UNMAPPED` / `CHIPS_AMBIGUOUS` | dicts | computed-display | the `—` names **which** absence it is |
| `CUT DATE` | S90 col 6 | B18 §5.8.2 (*"accent when it is this week"*) | `disconnect_cases.cut_scheduled_for` + `cut_date_is_this_week` served as DATA | date + bool | computed-display | inclusive both ends, **forward-looking only** — a passed cut date is neither accented nor counted |
| `LAST NOTICE` | S90 col 7 | B18 §5.8.2 · BR-CUS-100 · **DEF-692** | `disconnect_notices.issued_on` + `.tier`; **`disconnect_notices.delivery_state` is written NULL and read NULL** | date + enum + **null** | computed-display | ⛔ **GAP — no delivery adapter exists.** No branch in the screen can produce `emailed`/`posted`/`certified sent`/`certified signed` |
| *proof of service* | S90 col 7 (implied by `DSC-02.3`) | BR-CUS-100 | ⛔ **GAP — NO COLUMN.** `disconnect_notices` has no proof reference, no served-at date and no serving channel. **Schema OWED**; *"a tier-3 cut must not be schedulable on an unrecorded service"* | — | user-input (would be) | **BR-CUS-100, schema owed** |
| `STATE` | S90 col 8 | B18 §5.8.2 · §5.8.3 | **BOTH axes:** `disconnect_cases.state` (stored) + `held_by` (COMPUTED from `account_protections`) + `one_cell_is_unresolved` | enum + list + bool | computed-display | ⛔ **`STATE_ON_HOLD` is declared, is in migration `0022`'s CHECK vocabulary and is assigned NOWHERE** (measured 2026-08-25) — which is why `On hold` cannot be a stored state (OQ-374) |
| `ladder.runs` / `halt_code` | S90 row payload | §5.8.3 (*"STOPS ITSELF"*) | **nothing stores it** — `disconnects.halt_reason()` computed per row, per read | bool + code | computed-display | ⚠ never memoized: *"a RUN cached on a row outlives the debt"* |
| `ladder.scheduler` | S90 row payload | **DEF-320** | ⛔ **GAP — no runner, job, queue or timer.** `NO_SCHEDULER` (`advances_on_a_schedule: False`) rides on every ladder answer | dict | computed-display | `next_step_due` is a stored date **nothing watches** |
| `protections[]` | S90 row payload | BR-CUS-101 · §5.8.3 | `account_protections` (kind, effective_from, expires_on, lifted_on, reason) — liveness of a `payment_plan` READ from payments every time | rows | computed-display | ⛔ **three of ten** built (BR-CUS-101); the other seven are a clerk's job |
| `subject` / `chase_subject_unresolved` | S90 row payload | **OQ-366** · J08 step 2b | ⛔ **GAP by construction — `subject` is always `None`.** `restart_after_closure()` takes no `subject` and no `tier` parameter, so both readings are unrepresentable | null + dict | computed-display | **a green assertion naming either party is a FAILURE** |
| KPI ×5 | S90 strip | B18 §5.8.1 | ladder chips over open cases · `cut_scheduled_for` window · protections in force · `state == cut` · `state == reconnecting` | int | computed-display | the tiles **overlap by design**; `cut_awaiting_payment` carries `CUT_ACCRUAL_CAPTION_SUPERSEDED` (renamed from `CUT_ACCRUAL_UNVERIFIED` on 2026-08-25, DEF-716 — BR-CUS-103 settled the question the old name implied was open) |
| Segment strip | S90 toolbar | B18 §5.8.2 | ⛔ **GAP — no precedence, no partition.** `SEGMENT_PRECEDENCE_UNRULED` carries the question in full | — | — | **OQ-374** |
| Column preference key | S90 | BR-SHL-013 | `user_preferences` key `table.S90.columns` (`TableConfig.screenId = "S90"`) | jsonb | system-derived | identity column unhideable |
| Page / search state | S90 | BR-SHL-011 · **DEF-664** | ⛔ **GAP — nowhere.** Component state only | — | user-input | does not survive a reload |
| Audit | — | CLAUDE.md #7 | **none — this list writes nothing.** §5.8.5 TC-DSC-7's `audit_log` write belongs to the COMMIT in the five-step flow, which is out of scope | — | — | read-only surface |

**6 · Acceptance**

- **Given** §5.8.6's nine rows, **Then** the eight drawn columns render each one, and the strip reads **4 · 2 · 3 · 1 · 1** with the overlap intact.
- **Given** the union, **Then** the three HELD rows that never entered the ladder appear — a list of cases alone would be missing three of nine.
- **Given** any notice, **Then** the tier and the issued date render and **no delivery claim appears anywhere on the tab**; a notice-less row draws `—` and still carries the reason.
- **Given** a failed ledger read, **Then** the OWED cell renders a sentence; **given** `A-11507`, **Then** it renders a real `$0.00` as money, and the two look different.
- **Given** a row that is both on a tier and protected, **Then** **both** chips render, flagged ambiguous, and the STATE cell serves **both** axes with the collision marked — **never a silent winner**.
- **Given** any of the five unserved segments, **Then** the tab renders it disabled with the server's own sentence and the route is never called to find out; **given** a direct API call for one, **Then** the refusal is a readable sentence, not a stack trace.
- **Given** a payment in full, **Then** the ladder stops by itself and the row leaves on the next read, with nothing cancelled by hand.
- **Given** a collections-sequence row, **Then** **no party is named**, and the absence says so out loud.
- **Given** a second tenant, **Then** nothing of the first's is reachable — ⛔ **and a test asserting it (TC-DSC-9) is OWED.**
- **Given** any further work on this story, **Then** OQ-374 and OQ-366 are **not** answered by choosing a value.

**7 · Finance Calculation** — **N/A: this screen computes no money.** The `OWED` column is the **ledger's** figure, read once per page through `seams.ar_positions` and formatted by `disconnects._money` — the same formatter `case_payload` uses, *"so the OWED column and the case payload cannot round a figure two ways"*. Hard rule 2's two shapes travel together:

```
owed.stored   = the ledger's position, 4 dp          e.g. 2410.0000
owed.display  = the same figure, 2 dp, rounded ONCE server-side   →  "2410.00"   → rendered $2,410.00
owed          = null   ⇔  the ledger read failed     →  the REASON renders; never $0.00, never a dash
```

**Worked, on the two cases that must not be confused:** `A-11812` owes **$2,410.00** and renders as money. `A-11507` owes **$0.00** — a REAL zero, on the tab because a reconnection visit is due — and **also** renders as money. A third row whose ledger read failed renders **a sentence**. Three outcomes, three appearances, and DEF-127 is the reason the third is not a dash. **GT ref: none** — no golden test applies; nothing here is computed.

**8 · Open Questions**

| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-374 | **When a disconnect case is both on a tier and protected, which segment holds it and which chip does it wear?** Worked, in the PO's own terms: *Bramble Bakery (`A-11812`) is at `TIER 2 · 10-DAY` owing **$2,410.00** and files a medical certificate. Does that row appear under `At notice`, under `On hold`, or both — and does its chip read `TIER 2 · 10-DAY` or `HELD · MEDICAL`?* (A) protection wins both · (B) tier wins both · (C) segment and chip split. | **S90's segment strip and its chip column.** The list, the eight columns, the five tiles, the union, the search and the pagination all ship; the tab offers **one filter instead of six** | Product Owner (chat session) | **OPEN — blocking** |
| OQ-366 | **When a sub-account's unpaid debt moves to its master, who does the reminder ladder chase — the departed tenant, or the master?** | **Whose name goes on the letters.** Nothing on this screen: no row names a party, by construction | Product Owner (chat session) | **OPEN — non-blocking here** |
| — *(no OQ minted by this story)* | Every gap S90 carries already has an id or is an explicitly stated absence in the payload. **This story mints nothing** (see US-MET-021 §8). | — | — | — |
| ⛔ **OWED, no id** | **Proof of service has no home.** `DSC-02.3` marks certified mail *"Required at tier 3 — proof of service"*; BR-CUS-100 separates the SEND (in-app) from the PROOF (**a record a person enters** — channel, reference, signed-for date), and `disconnect_notices` **cannot hold it today**. Until it can, `delivery_state` stays NULL with its reason **and a tier-3 cut must not be schedulable on an unrecorded service.** | Recording that a tier-3 notice was served; the schedulability guard that depends on it | Product Owner / Eng Lead — **BR-CUS-100 names the schema as owed** | **REPORTED — schema OWED** |
| ⛔ **OWED, no id** | **Payments' `second_5_day` rung has no chip.** Either B18 §5.8 grows a fourth chip or BR-PAY-017 loses a rung. Mapping it onto TIER 2 or TIER 3 would be *"a statement to a regulator about what a customer was told"*, so neither is made and the cell renders `unmapped_rung`. | The TIER cell on any account on that rung | Product Owner (chat session) | **REPORTED — a ruling is OWED** |
| ~~⛔ **OWED, no id**~~ **OQ-380 → BR-CUS-103** | ~~**`CUT, AWAITING PAYMENT · still accruing base charges` is a billing claim nothing in this packet rules or implements.**~~ **RULED 2026-08-25: base charges STOP at the cut (PO, answer "no").** The tile carries `CUT_ACCRUAL_CAPTION_SUPERSEDED`, which withholds the drawn caption as FALSE rather than as unverified. | Nothing — the count ships; only the caption is withheld | ~~Product Owner / billing~~ **ANSWERED** | **CLOSED — BR-CUS-103 (OQ-380), copy landed under DEF-716 on 2026-08-25** |
| ⛔ **OWED, no id** | **No cross-tenant test exists**, although B18 §5.8.5 draws it as **TC-DSC-9** and `disconnects_list`'s docstring cites it by name (TC-23). | Nothing shipped — a test gap | Eng Lead | **REPORTED — a test is OWED** |
| ⛔ **OWED, no id** | **The same refusal behaves two ways on two sibling worklists** — `GET /disconnects` translates it into a readable sentence; `GET /connections` lets it surface as a **≥500** (US-MET-021 §8). One problem, two answers. | Nothing today — both tabs disable their segments client-side | Product Owner / Eng Lead, via a **defect** row this lane may not write | **REPORTED — a defect row is OWED** |
| ⛔ **NOT BUILT, no id** | **`DSC-02.1…5`, the five-step disconnect flow, and the reconnect flow.** B18 §3 maps S90 as *"Disconnects tab — list + ladder **+ 5-step wizard**"*; **only the list half of the id is built.** The empty-state CTA is disabled with that reason, and the reason it must stay disabled is that step 5 is a **danger-tier commit**. | Starting or committing a disconnect from this screen | already scoped out of this epic | **OUT OF SCOPE — recorded so the id is not read as complete** |
| **DEF-320** *(a defect, not a question)* | Nothing advances the ladder on a schedule: no runner, job, queue or timer reads a date and acts on it. Carried on every ladder answer as `NO_SCHEDULER`. | Automatic tier progression | already filed | **FILED — stated in the payload, not implied** |
| **DEF-692** *(closed → BR-CUS-100)* | `LAST NOTICE` was drawn against a capability that does not exist. Half-settled: the send is in-app; the proof is not settled (row 4 above). | — | — | **CLOSED 2026-08-25 → BR-CUS-100** |
| **DEF-664** | Page/search state does not survive a reload (TC-27). | Shareability of S90's list state | already filed | **FILED** |
| **DEF-689** *(closed → BR-CUS-098)* | B18 §5.8.5's `TC-DSC-3` states the opposite of the signed rule and is **left visible in B18, superseded**. Anyone implementing the ladder must read BR-CUS-098, not that cell. | — | — | **CLOSED 2026-08-25 → BR-CUS-098** |

---

## What B18 draws that the code does NOT do — S89 and S90

| Screen | B18 draws | Built? | Tracked by |
|---|---|---|---|
| S89 | §5.7.2 `request #` search leg | **No — ruled away** | **BR-CUS-099** (PO 2026-08-25) |
| S89 | §5.7.6 money figures on every row | **No — a line may carry NO figure**; `$0.00` and the principal `$150.00` are both forbidden | **OQ-365** · BR-CUS-057 unbuilt · ❄️ WE-7/GT-23 |
| S89 | any money MOVEMENT (deposit carry, arrears follow) | **No — nothing moves; four absences are named** | **OQ-365** (OPEN) |
| S89 | `+ New transfer` primary · a row action | **No** — no wizard route, no detail screen; the CTA is disabled with its reason | BR-SHL-010 / law 2 |
| S89 | §3's *"+ 5-step wizard"* under the same id (`TRF-02.1…5`) | **No — only the list half of S89 exists** | out of scope, **recorded** |
| S89 | a way to find a **cancelled** transfer | **No** — they are excluded from the list entirely | REPORTED, no id |
| S90 | §5.8.2 `LAST NOTICE` delivery states | **No — no delivery claim is made anywhere**; the column shows tier + issued date only | **DEF-692 → BR-CUS-100** (send settled, **proof schema OWED**) |
| S90 | §5.8.2 six exclusive segments | **No — one served**; five disabled with the server's sentence | **OQ-374** (OPEN) |
| S90 | §5.8.2 ONE tier chip per row | **No — every applicable chip is served, flagged ambiguous** | **OQ-374** (OPEN) |
| S90 | §5.8.1 `still accruing base charges` | ~~**No — the caption is withheld as unverified**~~ **No — the caption is withheld as FALSE** | ~~**OWED, no id**~~ **OQ-380 → BR-CUS-103** (PO 2026-08-25: base STOPS at the cut) · copy landed under **DEF-716** |
| S90 | `DSC-02.2`'s ten protection checks | **No — three built** | **BR-CUS-101** (PO: *"3 is okay to start with"*); the seven deferred |
| S90 | §5.8.3's ladder advancing over time | **No — nothing reads a date and acts on it** | **DEF-320** |
| S90 | §5.8.5 `TC-DSC-3` (ladder resumes where it was) | **Correctly NOT built — the cell is wrong** | **BR-CUS-098**: restarts at **TIER 1** |
| S90 | a chip for payments' `second_5_day` rung | **No — the `—` says `unmapped_rung`** | **OWED, no id** (BR-PAY-017 vs §5.8.2) |
| S90 | `+ New disconnect` primary · a row action · the reconnect flow | **No** — the danger-tier flow has no route; the CTA is disabled with its reason | BR-SHL-010 / law 2 |
| S90 | §3's *"+ 5-step wizard"* under the same id (`DSC-02.1…5`) | **No — only the list half of S90 exists** | out of scope, **recorded** |
| both | a shareable / reloadable list URL (BR-SHL-011 *"shareable"*) | **No** — embedded tabs own no query string | **DEF-664** |
| both | §5.7.6's five and §5.8.6's nine seeded rows | **No** — the seed is a data lane's task | B18 §11 W7 task 7.12 |
| both | a cross-tenant assertion (§5.8.5 draws **TC-DSC-9**) | **No test exists** — the scoping is in the code and in RLS; the assertion is missing | **OWED, no id** |
