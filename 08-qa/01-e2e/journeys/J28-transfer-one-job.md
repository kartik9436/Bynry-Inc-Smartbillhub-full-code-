# J28 — Transfer, one job (`A-10650 → A-11940`: the same customer, a new address, two halves and one commit — and the job is counted once)

---
id: J28
tier: 2
rules: [BR-CUS-015, BR-CUS-017, BR-CUS-018, BR-CUS-023, BR-CUS-024, BR-CUS-025, BR-CUS-030, BR-CUS-053, BR-CUS-054, BR-CUS-057, BR-CUS-081, BR-CUS-086, BR-CUS-099, BR-CUS-102, BR-MET-036, BR-TEN-043, BR-SHL-025]
stories: []
# ⚠ **`stories: []` IS A MEASUREMENT, NOT AN OMISSION — and it is a DIFFERENT
# finding from J26's.** Two stories now exist for this surface: **US-CUS-027**
# (S89, the transfers WORKLIST) in
# `04-docs/05-modules/03-customers/06-epics/EP-CUS-08-transfer-disconnect-worklists.md`,
# written 2026-08-25 after the code and saying so (DEF-695). **What owns nothing
# is the half this journey mostly walks:** `apps/customers/transfers.py` — the
# five steps and the one commit (CR-030 W7 tasks 7.1 · 7.2 · 7.3) — whose own
# Trace header still reads *"a transfer … owns no story of its own yet"*.
# **A story is OWED for the transfer WRITE path** (and for `TRF-02.1…5`, the
# wizard B18 §3 puts under the same screen id and which has no route in this
# application).
#
# ⚠ **AND DECLARING US-CUS-027 HERE WOULD PRINT A FALSEHOOD.** The index derives
# `ready_by_stories` from US-IDs cited in `── Trace ──` headers; `transfer_reads.py`
# and `TransfersTab.tsx` still cite US-CUS-004 / US-CUS-005 and state *"NO STORY
# OWNS S89"*, which was true when they were written and is now stale. Declaring
# the story would therefore index this journey `ready_by_stories: false` beside a
# screen that IS built. **Two corrections are owed** — the two Trace headers —
# and until they land the honest declaration is none.
#
# ⚠ **NOT ACTIVATED.** There is no `J28.spec.ts`, so G12 checks 2–5 have nothing
# to bite on. This file is the HANDOFF CONTRACT the prime directive's dependency
# rule asks for — what each step leaves in the DB for the next — written before
# the spec so the spec has something to be written against.
---

**Intent.** *"The same customer, a new address — **one job, not a move-out
followed by a move-in**"* (B18 §5.7). The job is started against a live account,
a vacant unit is chosen, two dates are set, the money decision is RECORDED
without a cent moving, and step 5 closes one account and opens the other **in a
single transaction**. Then the counting contract: the same job must appear on the
Transfers tab and on **neither** move list, because *"the same job listed three
times would be counted three times"* (§5.7.3).

**Fixture.** Tenant **brazos-bend** · clerk **Billing Clerk** · customer
**Iversen, Britt** (ONE customer entity, `customer_accounts`, BR-CUS-054) ·
leaving **`A-10650` · 18 Marten Row** (occupant since Jun 2022, balance
**$0.00**) · arriving **204 Quarry Lane → `A-11940`** · **out Aug 02 · in Aug
02**, the same-day case · deposit **$150.00 principal + $3.50 interest =
$153.50**. Second row, for the arrears leg only: **`A-11455` · Park, Jenna →
`A-12055`**, arrear **$542.10**, at step **3 of 5** — B18 §5.7.6's own
in-progress row, *"the same $542.10 balance the Accounts tab shows at 60+ past"*.

> ⚠ **THE DEPOSIT FIGURE IS $153.50 AND `TRF-02.1` DRAWS `$150.00 + $4.20`.**
> `150.00 + 4.20 = 154.20`, which is not the `$153.50` on the same screen's search
> row, twice on step 4 and again on step 5 — **DEF-690**, closed by **BR-CUS-102**
> (PO 2026-08-25, verbatim: *"Those are sample only from Prototype; you calcualte
> correctly"*). This journey uses the pair that FOOTS. ❄️ **WE-7 / GT-23** is the
> frozen authority for it and is cited as the reason a figure is REFUSED here,
> never computed.

| # | Step · screen | Handoff contract (what this step leaves) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | **`TRF-02.1` LEAVING** — the clerk finds `A-10650`. `transfers.start_transfer(actor, {"from_account_id": …})`. | One `transfers` row: `from_account_id`, `customer_id` **read from `customer_accounts`**, `to_account_id` **NULL**, `step=1`, `state='scheduled'`, and — ⚠ **AMENDED 2026-08-27** — a **`transfer_no`**, allocated from the `transfer` series INSIDE this call's own `atomic()` (BR-TEN-035). On a tenant provisioned from the current catalogue the first one is **`TRF-26-0001`**; `OQ-426` ruled the format (PO: *"Transfer TRF-26-0001 … follow same logic that we are following for other numbers we have did in settings"*) and it is tenant-editable on S8 like every other series. ⛔ **A tenant provisioned BEFORE that ruling has no `transfer` row yet** (`_seed_number_series` is `get_or_create`; the repair door is `manage.py seed_demo --tenant <sub>`), and until it is re-seeded the number is NULL and the payload carries `transfer_no_unavailable` with its reason — **never a dash and never an invented id**. `uq_transfers_open_from` now refuses a second open job on this account. Audit `transfer.started`. | ✅ **TC-TRF-2 — the FROM cell reads `A-10650` over `→ —`, and the dash is the SERVER's** (`transfers._serialize` writes the literal, *"because a blank second line and an absent one are indistinguishable once rendered"*). ⛔ An account that is not an OCCUPANT is refused by name (`from_account_is_not_an_occupant`): a draft never took a unit (BR-CUS-018) and a closed one has already left (BR-MET-036). ⛔ An account with **no customer entity** is refused rather than having one invented (`from_account_has_no_customer_entity`). | BR-CUS-054 · BR-CUS-030 · BR-CUS-018 |
| 1a | **`TRF-02.1`'s four panels** — the account, its relationships, the customer's other accounts, the premise. | Nothing. A read. | ⛔ **THREE OF THESE PANELS ARE DRAWN WRONG AND ARE NOT COPIED — DEF-690**: a `60+ past due` chip over a `$0.00 · nothing outstanding` balance, an interest figure that does not foot, and a `Standalone` claim contradicted elsewhere on the same screen. ✅ Panel (d)'s *"Hillside Holdings · **free text, not an account**"* IS right and agrees with BR-MET-113/116 — the owner has no posting target. | BR-CUS-102 · DEF-690 |
| 2 | **`TRF-02.3` ARRIVING (code step 2)** — `transfers.set_target_unit(actor, id, {"to_unit_id": …})`. | `to_unit_id` set (a metering id, **no FK** — B2 §2's reviewed interface set does not carry this edge), `step=2`, `state='in_progress'`. Audit `transfer.target_unit_set`. | ✅ **TC-TRF-5 — a unit with a live account is REFUSED and the refusal NAMES the blocker**: `target_unit_has_a_live_account` carries `occupied_by`, the way the drawing does (*"88 Pine Vista has an active account (A-11603, Thompson R.) with a move-out booked for Aug 31"*). ⛔ The `Reserved` half of *"only vacant and reserved units appear"* is served as a stated absence — `unit_reserved_state_has_no_column` — because occupancy is DERIVED and `units` stores no status (BR-MET-036). ⚠ **THIS IS A CHECK, NOT A RESERVATION**: the real mutual exclusion is BR-CUS-017's advisory lock inside `_open_account`, which step 5 goes through, so a race loses at commit rather than producing two live accounts on one meter. | BR-CUS-017 · BR-MET-036 |
| 3 | **`TRF-02.3` dates (code step 3)** — `set_dates({"out_date": "2026-08-02", "in_date": "2026-08-02"})`. | `out_date`, `in_date`, `step=3`. `same_day` rides every serialisation. Audit `transfer.dates_set`. | ✅ **TC-TRF-4 — same day, and it is RECORDED, not enforced**: *"18 Marten Row is billed through that day's reading, and 204 Quarry Lane starts from its own on the same date. **No gap and no double bill.**"* The proration and the shared reading are BR-CUS-022's and the reads lane's — **this module writes no bill and no meter read**, and says so rather than implying it did. ⛔ `in_date < out_date` is refused (`in_date_before_out_date`): a gap in service nobody asked for. | BR-CUS-022 *(cited, not exercised)* · BR-CUS-030 |
| 3a | **`TRF-02.2` FINAL READS · `TRF-02.3` opening reads** — 3 registers out, **4 registers in** (a net meter is two registers on one meter). | ⛔ **NOTHING.** No read row is written by this journey. | ⛔ **THE DRAWN GUARANTEE IS UNASSERTABLE HERE** — *"every opening read equals its prior final, so no consumption is invented at the boundary"* is metering's to keep and `transfers.py` never touches a read. Recorded because the wizard puts it between steps 1 and 3 and a lane reading only the code would not know it was promised. | — *(owed: a read-boundary rule id)* |
| 4 | **`TRF-02.4` MONEY** — `money_statement` (read), then `elect_money(actor, id, {"deposit_carry": true, "arrears_follow": true})`. | `deposit_carry_elected`, `arrears_follow_elected`, `money_decided_at`, `step=4`. Audit `transfer.money_elected` **carrying both figures and both absences**. ⛔ **No money column, no ledger row, no payment row, no refund.** | ✅ **TC-TRF-3's SIGNED HALF: `$153.50` is not refunded and re-collected** — *"The customer is not leaving, so the $153.50 held on A-10650 moves to the new account with its interest intact. Refunding it and taking a new one would cost them the interest and delay the move."* The guarantee is held **by construction**: `deposit_on_file` is a REFUSED input (BR-CUS-023), so no re-collection is expressible. ⛔ **AN ELECTION IS NOT A MOVEMENT.** What is stored is that a human decided; nothing settles, posts or moves — **OQ-365**. ⛔ **`$0.00` IS FORBIDDEN ON EITHER LINE**: an unreadable BR-CUS-057 interest serves `null` with `deposit_interest_not_readable`, because reading it as zero serves **`$150.00`** where **`$153.50`** is held and keeps $3.50 of the customer's money. | BR-CUS-023 · BR-CUS-024 · BR-CUS-057 · OQ-365 · rule 5 |
| 5 | **`TRF-02.5` REVIEW & CONFIRM** — `review` (read), then `commit_transfer`. | **ONE `transaction.atomic()`**: `services.move_out` closes `A-10650` on Aug 02 (the SIGNED BR-CUS-030 path, not a copy) · `services.create_account` opens `A-11940` at the new unit on Aug 02 (through the ONE door, so BR-CUS-017's lock and occupancy guard apply) · a `customer_accounts` row links the **same** customer · `to_account_id`, `committed_at`, `step=5`, `state='done'`. Audit `transfer.committed`. | ✅ **TC-TRF-6 — old `closed_at` set, new `opened_at` set, and each links to the other**, the link being the transfer row itself rather than a new column on `accounts` (the same fact in two places is two facts). ✅ **BOTH OR NEITHER** — *"If the opening reads at 204 Quarry Lane cannot be taken, the closure at 18 Marten Row does not happen either — otherwise the customer ends up with no account anywhere."* ✅ The audit row carries the PROOF of the two things TC-TRF-3 forbids: `deposit_on_file_before`, `balance_before`, `refund_raised: false`, `deposit_recollected: false`, **`journal_lines_written: 0`**. ⛔ A commit missing any of steps 2–4 is refused with the step NAMED (`step_2_target_unit` · `step_3_dates` · `step_4_money`), never a bare `false`. | BR-CUS-030 · BR-CUS-017 · rule 4 · rule 5 |
| 6 | **S89 · `GET /transfers`** — the job appears on the Transfers tab. | Nothing written. | ✅ Eight columns, §5.7.2's own: `A-10650` over `→ A-11940`, `Iversen, Britt`, both addresses, both dates, `5 of 5`, `deposit carried $153.50`, **Done**. ⛔ **NOT searchable by request #** — BR-CUS-099 (PO 2026-08-25) ruled the leg away, and *"there is now no way to get from a service request to the transfer it became"* was accepted, not overlooked. ⛔ A row with **no** money lines renders `—` and that dash means **none** (§5.7.6's `A-11109 · Osei, Grace`); a row whose figure cannot be READ renders the server's sentence. The two must not look alike. | BR-CUS-099 · BR-CUS-053 · BR-SHL-025 |
| 7 | **THE COUNTING CONTRACT** — `GET /move-ins` and `GET /move-outs` (`move_reads.move_ins_list` / `move_outs_list`). | Nothing written. | ✅ **TC-TRF-1 — the job is in NEITHER.** And it is load-bearing rather than formal: `commit_transfer` closes its outgoing half **through `services.move_out`**, so every committed transfer writes a `closed_at` and a terminal status and is INDISTINGUISHABLE from a move-out by the window the Move-outs list selects; the incoming half is created by `services.create_account` and can land in exactly the draft class the Move-ins window selects. `transfers.exclude_transfer_halves` is the only thing keeping both off. ⚠ **The exclusion covers OPEN transfers, not only committed ones** — Park, Jenna at `3 of 5` is absent from the Move-outs five. ✅ Each list publishes `exclusion.half_account_ids` = `transfers.transfer_half_account_ids()` **CALLED, not re-derived**, and the callout the clerk reads is the same string the server serves. | BR-CUS-086 · §5.7.3 |
| 8 | **INVARIANCE** — after the commit: `accounts.deposit_on_file` on `A-10650` is **unchanged**; `accounts.balance` is **unchanged**; **zero** journal lines exist for either half; no `payments` row; no refund; the new account's plan came from the **UNIT**, not from the old account. | — | ✅ *"The new unit carries its own plan. Residential Standard v3 there too, **but by coincidence, not by carry-over**"* — the screen states the account-derives-plan rule in the only place a user would wonder, and as a WARNING rather than a reassurance. ⛔ **Only the ledger posting service writes journal lines** (hard rule 5), which is why *"arrears follow"* is an ELECTION and not a posting. | rule 4 · rule 5 · BR-CUS-015 |

## What this journey CANNOT yet assert, and why

| # | Not asserted | Blocked on |
|---|---|---|
| a | **Any of it through a screen.** `TRF-02.1…5` has **no route in this application** (no `TransferWizard` of any name is imported by `07-frontend/src/App.tsx`, measured 2026-08-25), and **no endpoint exists for any transfer WRITE step** — `apps/customers/api.py` mounts `GET /transfers` and nothing else. Every step above is a service call. | CR-030 W7 task 7.4's wizard half; an API surface; a story for the write path. |
| b | **That the deposit and the arrear actually MOVE.** **OQ-365 — OPEN, non-blocking**: four signed rules meet on a transfer (BR-CUS-023/024/025/081) and all four were written about a customer who is **leaving**. Nothing moves and the statement says so. | The PO. Until then `deposit_carry_has_no_transfer_path` and `arrears_follow_has_no_posting_path` ride the answer. |
| c | **The arriving address GAINS A SERVICE.** The band on every drawn step reads `LEAVING [E][W]` → `ARRIVING [E][W][S]` — **sewer is new** — and nothing in `transfers.py` reasons about a service the old address did not have. | A rule id. **Owed** — B18 §5.7.7 flags it and it has none. |
| d | **Plan/asset compatibility.** *"There is solar here, paired with net meter M-8803. **The plan on this unit must support net metering or the export will not be credited.**"* Drawn as a rule, has no id, and no code checks it. A customer moved onto a non-net-metering plan generates export nobody credits. | A rule id and a check. **Owed.** |
| e | **That a senior discount is RE-CHECKED.** *"Senior rate must be re-checked — **eligibility depends on the premises, not the person**."* `discounts.py` has no re-check on transfer, so a carried discount would under-bill every month until somebody noticed. | A rule id and a call. **Owed.** |
| f | **That the backflow-test obligation survives the occupant.** *"**The backflow test obligation belongs to the premise, not the occupant** — it comes with the unit and its next test is due in 22 days."* Drawn as a rule; no id; nothing models an obligation that outlives a tenancy. | A rule id. **Owed.** |
| g | **That the STEP column means the same thing to a clerk and to the database.** `transfers.STEPS` is B18 **§5.7.4**'s five verbatim (find account · find unit · dates · money · review); the wizard **§5.7.7** draws five DIFFERENT screens (leaving · **final reads** · arriving · money · review), where the drawn step 3 contains the code's steps 2 **and** 3 and the drawn step 2 has no code step at all. **`3 of 5` therefore denotes two different states.** | A defect row — **OWED, no id** — and a ruling on which five the STEP column counts. |
| h | **The transfer confirmation reaching the customer.** `What we'll send` ticks two of three at commit. Nothing here writes a notification; `BR-MET-115` removed New Connect's `On creation` trigger and *"a transfer confirmation at commit is a different case"* — recorded because the next reader will ask, not because it is built. | notifications' own change. |
| i | **§5.7.6's five seeded rows as a fixture.** Task 7.12 seeds them through the real five steps (`sample_data.py`), so the fixture exists — but no browser spec consumes it. | `J28.spec.ts`. |
