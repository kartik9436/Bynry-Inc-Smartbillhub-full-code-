# CR-181-BRC10 · Move-in: a returning customer is recognised, their old balance shown, and their old account reopened on the same unit

**Raised:** 2026-10-13 by the Product Owner, in chat, while testing move-in on Ottumwa Water Works.
**Requester's words (verbatim):** *"in move-in - user hase entered the previosly move-out cutomer who has pending balance ; on move-in step2 - user has entereed consumer number, phone, email click on search cutomer id - system show no match found why?; also system is not fetching pending balnce show on the sceen"* and *"one account closed using move out ; after 3 year same customer come back again for same property then we should allo w same account to move in - so this account should show in move in list"*.
**Rulings (verbatim, 2026-10-13):** *"Q1 C both; Q2 - Reopen, for the same unit only ; Q3 - give opton to use whether pay it now or carry itr - Must pay first · Carry it onto the reopened account · Clerk chooses"* and *"Q4 - keep 5 years right now"*.

## 1 · Classification
A **change**: it reverses in part the PO ruling of 2026-10-05 (decision log *"FOUR PO RULINGS IN ONE REPLY"* (1): *"if match based on our logic then we say match if it is not then we dont say it"*) by adding two ways a customer is shown, and adds a capability (reopen) the product never had. Not a defect: the search did what its rule said.

## 2 · What is reversed or added
| Before | After |
|---|---|
| *Search customer ID* shows **found** (SSN / licence) or **possible** (name + date of birth) and nothing weaker | **Q1 C** — also shows (a) **same name and phone** as a third, weaker level, and (b) **the unit's last occupant** when the name typed matches them. Both carry the customer's accounts and what each still owes (from the books). The clerk still chooses *Use this customer* or *Not them*. |
| Every move-in opens a NEW account | **Q2** — when the customer moving in is the one whose account on **this same unit** was closed, the clerk may **Reopen** that account (same number, full history) or open a new one. Another unit always gets a new account (BR-CUS-017 unchanged: at most one active account per unit). |
| Old debt invisible at move-in | **Q3** — when the reopened account still owes money, the clerk chooses **Must pay first** (Complete is refused until the balance is paid, through Payments' own record-payment) or **Carry it** (the balance stays on the reopened account and appears on the next bill). Shown on step 2 and on Review. |
| — | **Q4** — reopen is offered only when the account was closed **within the last 5 years** (a tenant setting, default 5). Older closed accounts get a new account. |

## 3 · Tasks
| # | Task |
|---|---|
| B1 | `customers/owner_lookup.search`: add the `name_phone` level and the `last_occupant` level (the vacant unit's most recently closed account's customer); each row keeps its accounts and outstanding from the ledger. |
| B2 | Move-in commit: `reopen_account_id` — validate same unit, same customer, closed, closed within N years (setting, default 5), unit vacant; account active from the move-in date, `closed_at` cleared, new service agreements, plan / deposit / fees re-derived from today's unit plan; audit row `account_reopened`. Issued bills, payments and journal lines untouched (hard rule 4). |
| B3 | Balance choice `pay_first` / `carry`: pay_first refuses Complete until the account's outstanding is 0; carry records the choice and the figure on the move-in. |
| B4 | Settings: *Reopen a closed account within* N years (default 5). |
| F1 | Step 1: for a vacant unit, the last account with what it owes. |
| F2 | Step 2: the two new match levels, labelled; *Reopen AC-… / New account* when it applies; the balance and the *Must pay first / Carry it* choice. |
| F3 | Review and the Move-ins list / details: *Reopened AC-…* and the balance choice. |
| T1 | Tests (SQLite + PostgreSQL): each match level; reopen same unit; refused on another unit, someone else's account, over 5 years, unit occupied; pay-first blocks then completes after payment; carry keeps the balance; no issued row changes. |
| E1 | Walk: Viktor Valdez moving back into SCW-U-022 with a balance — both balance choices; records checked (accounts, service agreements, ledger, audit). |

## 4 · Status — BUILT, NOT RELEASED (lane REOPEN, 2026-10-13)

**Rule:** `BR-CUS-1119` (customers business rules), minted for the four rulings. **Judgments of ours:** decision log *"RETURNING CUSTOMER — HOW THE FOUR RULINGS WERE BUILT: NINE JUDGMENTS OF OURS"*. **No version bumped and no CHANGELOG line** — the release lane does both.

| # | Built |
|---|---|
| B1 | `owner_lookup.search` — `name_phone` and `last_occupant` (needs `unit_id`), each row with `last_occupant` and `reopen` (`move_in_reopen.offer_for`: account, closed date, eligible / reason, what it owes, the window). New Connection's answer unchanged. The email is not used (no customer row holds one). |
| B2 | `customers/move_in_reopen.py` + `_open_account(reopen=…)`: `reopen_account_id` checked BEFORE the transaction (same unit · this customer's · closed, not a cancelled move-in · within N years · unit empty · start after its own close), then the row is locked and UPDATEd (status, `opened_at`, `closed_at` cleared, preferences) and new service agreements opened through `_make_occupying` (BR-CUS-017 under the unit lock). Audit `account.reopened` (the CR's task line said `account_reopened`; dotted, as every other action). |
| B3 | `reopen_balance` `pay_first` / `carry`; asked only when owed. Owed = ledger AR **net of credit held** (judgment 2). Pay first refused `customers.moveIn.reopen.payFirst` until $0.00; carry records the figure. Table `move_in_reopenings` (`customers/0083`, RLS in the same file), audit `move_in.reopen_balance`. |
| B4 | S66 *Billing defaults* › *Reopen closed accounts within* N **Years** (`reopen_within_years`, default 5, 0–50, 0 = never). |
| F1 | Step 1 History: the last account and *Owes $…* (`history.previous.outstanding`). |
| F2 | Step 2: *Same name and phone*, *Lived here last* (own words, distinct from Q5's); the search sends the unit; `ReopenChoice` — *Reopen AC-… / New account*, *Owes $…*, *Must pay first / Carry it*, *Record payment* opening Payments' own `RecordPaymentModal`, then the figure re-read. A reopen refusal at Complete lands back on step 2 beside the choice. |
| F3 | Review (*Returning customer — Reopened AC-… · $… carried / Must pay first*; account number *Reopened AC-…*), the move-in details and the Move-ins list (*Reopened AC-…*). |
| T1 | `tests/test_cr181_returning_customer_reopen.py` — 15 cases, SQLite **and** PostgreSQL 16; `ReopenChoice.dom.test.tsx` — 12 cases. Red first: removing the name-and-phone level, the pay-first refusal, the other-unit guard or the window each turns its case red (4 failed, quoted in the lane report). |
| E1 | `05-prototype/returning-customer-2026-10-13/` — both choices walked in the browser, records checked (README). |

**Worked on the dev data (E1):** Viktor Valdez, AC-2026-00022 on SCW-U-022, closed 09/30/2026 owing **$168.18**. *Carry it* → MVI-26-0027 on AC-2026-00022, *carry, $168.18*, the $168.18 still owed, the five issued bills and 53 journal lines byte-identical. *Must pay first* (after a second move-out) → refused until an ACH payment of $168.18 → MVI-26-0030, *pay first, $0.00*.

**Open items (not built here):**
1. `DEF-CUS-10125` — the Move-outs list reads `accounts.closed_at`, so a reopened account's earlier move-out leaves that list (the record stays).
2. `DEF-CUS-10126` — cancelling a move-in that reopened an account would close it with the earlier tenancy's dates lost.
3. On a reopened account the move-in details' *Messages* tile counts the whole account's messages (earlier tenancy included), and *Earliest legal start* reads *No earlier tenancy* (the tenancy before is the same account).
4. A debt with no bill the allocator can meet (a cutover opening balance) is paid as CREDIT, not against AR; *pay first* nets it (judgment 2), but the search's accounts table keeps showing AR (`DEF-CUS-9756`'s rule) — the two figures can differ on such an account.
5. `DEF-CUS-10127` — two move-in suites that call `move_out` have been red since 2.574.0 (unrelated to this CR, found running neighbours).
