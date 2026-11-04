# ID reservations — who may take which ids, and until when

**Why this file exists.** In this repo ids are allocated by `max + 1` against
whatever the allocator can see. That is correct with one lane and wrong with
six: a lane dispatched with "your range is DEF-1000–1019" holds a block that
exists **only in the sentence that dispatched it**, so `file_defect.py` walks
straight through it and hands the next caller an id another lane is already
using. Two id incidents happened within ten minutes on 2026-08-27 — DEF-974
taken twice across branches (**DEF-977**), and `file_defect.py` returning
DEF-1001 out of a block reserved minutes earlier (this file).

A reservation is a promise between lanes. A promise that lives in a chat
message does not survive the chat.

## How to use it

* **Dispatching a lane:** add a row below *before* the lane starts, with the
  block, the lane, and the date. Then put the same block in the dispatch.
* **Taking an id by hand:** read this file first. A block listed ACTIVE is not
  yours, even if the register's `max + 1` lands inside it.
* **Filing from inside your own block:** pass it — `file_defect.py --block 1810-1839`
  — and the allocator works *inside* that range instead of stepping down past it.
  ⚠ **Without the flag it steps past YOUR block too**, because the tool has no way
  to know which lane is running it: the R1–R7 lane, reserved DEF-1810–1839, was
  handed DEF-1793…1796 and renumbered five rows by hand, and one of the numbers it
  was pushed onto had been taken by another lane minutes earlier (`DEF-1814`).
  A block named on the command line but not ACTIVE here is **refused** — a claim
  that lives only in the invocation is the promise this file exists to replace.
* **Finishing a lane:** mark its row `RELEASED` with the date. Ids it actually
  used stay used; the rest of the block returns to the pool. **Do not delete
  the row** — a released block tells the next reader why there is a gap.
* `10-scripts/file_defect.py` reads this file and refuses to allocate inside an
  ACTIVE block that is not its own, naming the block and its owner. It is the
  one place that can enforce this, because it is the one place that allocates.

A gap in the numbers is legitimate and always has been (`g26_defect_register.py`
says so in as many words: *"an abandoned id is legitimate"*). A **collision** is
not.

## Active and released blocks

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-CUS-7910–7919` | **LANE NC5-PHOTOS — the CAPTURE-AND-REPORT lane for New Connect's five built steps (`05-prototype/new-connect-redesign-2026-09-28/built-2026-09-29-five-steps/`), branch `claude/brave-dijkstra-xgfsgz`. It redesigns and fixes NOTHING; the only code it writes is its own walk, `10-scripts/nc5_five_step_photographs.mjs`. ⚠ **`DEF-CUS-7910` WAS ALREADY ALLOCATED BEFORE THIS ROW EXISTED** — `file_defect.py` reported *“it is inside no active block”* and appended it anyway, correctly, and the block is written here afterwards so the remaining ids of this lane are claimed rather than taken one at a time. `7900–7909` immediately below is `LANE MOVEIN-NAV`'s and is untouched. ⚠ **A RESERVATION IN A PRIVATE WORKTREE IS INVISIBLE TO `allocate.py`** — that row's own renumbering records it — so this lane re-verifies every id at push time and treats `push_paths.sh`'s duplicate-id guard as the only final check.** | 2026-09-29 | **ACTIVE** |
| `DEF-IDN-7826` | **LANE SEC-BACK — the server half of the approved Settings → Security redesign (`05-prototype/security-redesign-2026-09-29/`), branch `claude/brave-dijkstra-xgfsgz`.** The four typed numbers become choice lists, and the tab gains the read behind its Audit log card. ⚠ **NO RANGE IS HELD OPEN AND THAT IS DELIBERATE.** One id was needed and one was taken; `file_defect.py` allocated `DEF-IDN-7826` and printed *"it is inside no active block"*, which is the honest state — reserving `7820–7829` afterwards would claim nine numbers a sibling may already hold, and a block claimed after the fact is the promise this file exists to replace, backwards. The precedent is the two *"RELEASED — the id is USED; nothing else taken"* rows further down. ⚠ **`DEF-IDN-7826` IS A BREAKAGE THIS LANE CAUSED IN A SIBLING'S FILE, FILED AND NOT FIXED HERE** — `10-scripts/cr145_security_dropdown_value_census.py` reads `services.SETTING_LIMITS` on purpose so it cannot drift from the validator, but it reads the RANGE shape, and the four entries it counts are choice lists now, so every one raises `KeyError: 'min'`. **`10-scripts/` is the COUNT lane's and two lanes writing one file is law 11**, so the row is the hand-off. **Version `2.394.0`**, from `allocate.py version --bump change`, re-verified against the remote at push time. **No `OQ` minted** — the one thing this lane could not decide (what the two provisional lists finally hold) is answered by running that census against production, not by the PO (law 13). | 2026-09-29 | **RELEASED 2026-09-29** — the id is USED; nothing else taken |
| `DEF-IDN-7810–7819` · `CR-145-BRC08` | **LANE CR145-CLOSE — the change request's CLOSING half: the last hand-typed option lists on Settings → Security (`F2`), the six-setting browser walk (`T10`) and the record, branch `claude/confirm-understanding-3ktufc`.** ⚠ **A THIRD DISJOINT BLOCK, NOT A SLICE OF `DEF-IDN-7500–7539`** — that row reserves the range for the CHANGE REQUEST, so `file_defect.py` walks every candidate inside it past the parent and refuses with *"every id is taken"*, which is true of the block map and false of the register. The row above it (`DEF-INF-7540–7549`) records the same discovery and the same remedy: **a block per change request is not a block per lane.** `7810–7819` sits outside every reserved range and held no id on any `origin` ref when this row was written. ⚠ **AND `G26` CANNOT PROTECT THIS NUMBER** — it counts duplicate id STRINGS, so `DEF-IDN-7810` and `DEF-CUS-7810` both pass green while the PO's ruling of 2026-09-03 makes the running NUMBER one series across every module; four collisions happened in this register on 2026-09-28 for exactly that reason. The only real protection is the unconditional re-verification at push time (`allocate.py defect --verify`), which this lane ran. Version `2.393.6`. | 2026-09-29 | **ACTIVE** |
| `DEF-RAT-7800–7809` | **LANE RAT-AMOUNT-BOX, SECOND BLOCK — `DEF-RAT-7700–7709` COLLIDED AND THE FOUR ROWS TAKEN OUT OF IT WERE RENUMBERED BEFORE THEY WERE EVER PUSHED.** ⚠ **THE ROW BELOW IS LEFT EXACTLY AS IT WAS ON PURPOSE** — `push_register_guard.py` refuses a line that VANISHES from a shared register (`DEF-2837`), and an in-place rewrite of a pushed row is indistinguishable from a revert by subtraction. **The take is appended; the reservation stands, superseded by this row.** ⚠ **WHAT HAPPENED, BECAUSE IT IS LAW 11'S ID CLAUSE HAPPENING TO A LANE THAT WAS FOLLOWING IT.** This lane wrote the `7700–7709` row FIRST and pushed it (`efc2f88b2`), `allocate.py defect --verify` answered *still free on every branch* for `7700`, `7701` and `7702`, and `file_defect.py --block 7700-7709` allocated inside the lane's own block — every step correct, and printed as correct. A sibling then pushed **`DEF-CUS-7700`, `DEF-CUS-7701` and `DEF-INF-7702`** into the same three numbers, because **a worktree that has not fetched cannot see a reservation row**, and because `allocate.py` **cannot reserve — it only removes the stale read**, which its own output says in as many words. ⚠ **NO GATE WOULD HAVE CAUGHT IT: `g26_defect_register.py` counts duplicate ID *STRINGS*** (`Counter(ids)` over the first column), so `DEF-CUS-7700` and `DEF-RAT-7700` are two different strings and both would have shipped green — while the PO's ruling of 2026-09-03 makes the running NUMBER one series across every module, and this file's own `DEF-RAT-7000`/`DEF-CWP-7001` row says so (*"the block is a range of NUMBERS"*). It was caught only by the **unconditional** re-verification at push time that law 11 prescribes. ⚠ **THE UNPUSHED SIDE MOVED, WHICH IS ALWAYS THE CHEAPER HALF.** Their three rows are on the tip and cited from their code; this lane's four were in its own working tree, so they were renumbered **in raw bytes** and re-appended to the tip's register with the prefix proved byte-identical (8,517,507 bytes), and the 16 citations in this lane's five files moved with them. **USED: `DEF-RAT-7800`** (was `7700` — the Product Owner's report: the read-only Amount box on a per-size charge code is EMPTY, so the product's accent focus ring reads as an invalid-field marker; FIXED in `2.392.4`), **`DEF-RAT-7801`** (was `7701` — FILED, not fixed: switching *How the amount is worked out* away from **A fixed amount** hides the whole per-size table while `chargePayload` goes on posting its rows), **`DEF-INF-7802`** (was `7703` — FILED, not fixed: `11-smoke-stack.sh` builds the SPA with no `--mode`, so since `f0739cfc8` every local browser proof bakes in the remote API host and its own content-security policy refuses every call), **`DEF-CUS-7803`** (was `7704` — FILED, not fixed: `serviceNamespace.test.ts` RED since `03d9e1c36` at 16:12 today over another lane's `BuildDetailTabs.tsx`; found by reading the reds this lane did not cause and DATED with `git log -S` rather than called pre-existing without a date). `DEF-RAT-7804–7809` remain UNUSED and free. **Version `2.392.4`** — `2.390.2` was written first and a sibling pushed it while this lane worked (`allocate.py version --verify` answered *TAKEN*), so it was re-bumped from the tip and re-verified; that is `DEF-GOV-3756`'s collision caught by the same unconditional check. | 2026-09-28 | **ACTIVE** |
| `DEF-RAT-7700–7709` | **LANE RAT-AMOUNT-BOX — the Product Owner's beta report on Plans & Rates → edit a charge code → step 2: *"the Amount box will not accept typing, is outlined red, and shows no message"*, and *"then why this field is shown then - user is confuse"*. Branch `claude/confirm-understanding-3ktufc`. MAINTENANCE (`22-product-maintenance-process.md`), not Build — a clerk can reach and use this screen today.** Written here BEFORE the first row is filed, which is what `file_defect.py --block` refuses without — *a block claimed on the command line and nowhere else is the promise that does not survive the chat*. ⚠ **THE BLOCK OPENS AT 7700, WELL CLEAR OF THE FRONTIER (`allocate.py defect` answers `7643`), RATHER THAN AT `max + 1`** — three sibling lanes are live on this branch in their own worktrees at this moment (DISCONNECT in `features/customers/`, REPORTS in `features/reports/`, ACCOUNTS-KPI in `features/customers/AccountsPage.tsx`), so every lane computes `max + 1` correctly and every lane gets the same answer (`DEF-1787`). `allocate.py defect --verify 7700/7701/7702` each answered *still free on every branch* at allocation and were re-verified from the pinned tip at push time. ⚠ **AND `allocate.py --verify` HAS A KNOWN PROSE-SCAN FALSE POSITIVE** — it counts this very row and any citation in a heading, so it can answer *TAKEN* for a number no register holds; it did so for `7220`, `7310` and `7051`. **Ask WHY before renumbering.** **USED: `DEF-RAT-7700`** (the confirmed defect — a read-only money box that is EMPTY, so the product's own accent focus ring reads as an invalid-field marker), **`DEF-RAT-7701`** (FILED, not fixed: switching *How the amount is worked out* away from **A fixed amount** hides the whole per-size table while `chargePayload` goes on posting its rows, so six priced sizes leave the screen with no word and survive invisibly in the payload). `DEF-RAT-7702–7709` remain UNUSED and free. **No `CR` number and no `OQ`** — this is a defect in the beta, which `13-change-process.md` §1 makes the default, and nothing here is a fact only the Product Owner holds. Version **`2.390.2`** (`allocate.py version --bump fix`), re-verified against the remote at push time because two lanes each bumping is `DEF-GOV-3756`. | 2026-09-28 | **ACTIVE** |
| `CR-151-BRC09` | **LANE REVERSAL — the build detail page (`CR-151-BRC09-a-build-gets-its-own-page-again.md`), branch `claude/brave-dijkstra-xgfsgz`. TAKEN 2026-09-28, the SECOND number out of the `BRC09` block the row below reserved.** ⚠ **THIS SUPERSEDES THE *"`CR-151`–`CR-154` are free"* CLAUSE OF THE `CR-150`–`CR-154` ROW BELOW, AND THAT ROW IS LEFT AS IT WAS ON PURPOSE.** A block row records what was reserved when the branch opened; it is not re-edited each time a number leaves the block, because `push_register_guard.py` refuses a line that vanishes from a shared register (`DEF-2837`) and an in-place rewrite of that row is indistinguishable from a revert by subtraction. **The take is appended; the reservation stands.** `CR-152`–`CR-154` remain free. ⚠ **`allocate.py cr --verify 151` ANSWERS *TAKEN*, AND IT IS THE PROSE-SCAN FALSE POSITIVE THE LANE RECORD ROW BELOW NAMES.** Asked WHY before renumbering, as that row instructs, and the answer is conclusive: measured on tip `6d560c12`, the ONLY occurrence of the string `CR-151` anywhere in the tree or on any fetched `origin` ref was **the block row itself**, which spelled out `CR-151`–`CR-154` when it reserved them. `152` and `153` read *free* purely because those two literals were never spelled out; `150` and `154` read *TAKEN* for the same reason `151` does. **No register held `CR-151` and no `CR-151-*.md` existed.** Renumbering on that answer would have let a known blind spot in a tool move a real number. **No version taken** — `CR-150-BRC09` owns `2.390.0`, `G35` holds four literals in lockstep, and two lanes bumping is `DEF-GOV-3756`; the lane that lands the page allocates one. | 2026-09-28 | **ACTIVE** |
| `DEF-CUS-7600–7629` · `OQ-CUS-12770–12779` · `CR-150-BRC09` | **LANE RECORD — the New Connect redesign (`NCT-01`, Accounts → New Connect): eight steps become five, the Product Owner's 18 answers of 2026-09-28, and the 14 bugs the beta reported against deployed `v2.385.1`. Branch `claude/brave-dijkstra-xgfsgz`; two sibling lanes (COMPONENTS and TEXT) are live on it in their own files.** Written here BEFORE the first row is filed, because `file_defect.py --block` refuses a block that lives only in the invocation — *a block claimed on the command line and nowhere else is the promise that does not survive the chat* — and it refused four lanes for exactly that on 2026-09-27/28. ⚠ **THE BLOCK OPENS AT 7600, WELL ABOVE THE FRONTIER (`allocate.py defect` answers `7543`), RATHER THAN AT `max + 1`**, following the `DEF-IDN-7500` precedent of two days ago: sibling lanes compute `max + 1` correctly and all get the same answer (`DEF-1787`). ⚠ **`OQ-CUS-12770` IS TAKEN FROM THE SAME ROW** — `allocate.py oq` answers `12770`, and it is the question *which quantities were 1, 2 and 15?*, which nothing may guess because it is money on a real invoice. ⚠ **AND `allocate.py --verify` HAS A KNOWN PROSE-SCAN FALSE POSITIVE** — it counts this very row and any citation in a heading, so it can answer *TAKEN* for a number no register holds; it did so for `7220`, `7310` and `7051`. **Ask WHY before renumbering.** Version `2.390.0`, allocated once for the whole change request. | 2026-09-28 | **ACTIVE** |
| `CR-150`–`CR-154`, suffix **`BRC09`** | **BRANCH `claude/brave-dijkstra-xgfsgz`.** Change requests raised while this branch is live are numbered from this block and carry `-BRC09`: `CR-150-BRC09` … `CR-154-BRC09`. `CR-150-BRC09` is USED (the New Connect redesign); `CR-151`–`CR-154` are free. **The suffix is provenance and the BLOCK is what makes the number unique** — `13-change-process.md` §0, and `G17` fails a duplicate NUMBER even when the suffixes differ. ⚠ **`BRC09` IS THE NEXT FREE BRANCH CODE AND IT IS NOT A CLEAN GREP.** `BRC01`–`BRC08` are claimed (`BRC07` = `claude/kind-goldberg-k0acqg`, `BRC08` = `claude/confirm-understanding-3ktufc`), and no row anywhere claims `BRC09` — **but six strings in the tree already read `CR-140-BRC09`** (`10-scripts/gates/run_gates.py:609`, `10-scripts/gates/g133_export_columns_agree.py:4`, `07-frontend/src/features/ledger/PaymentsMadePanel.tsx:2`, `ExportView.tsx:2`, `exportView.dom.test.tsx:3`), and **`CR-140` is really `CR-140-BRC07`** — its file is `12-governance/change-requests/CR-140-BRC07-write-offs-link-on-debtors.md`. Those are a mis-typed suffix on somebody else's number, filed as a governance defect out of the block above and named in `CR-150-BRC09` §4; **they are not this branch's and nothing here is renumbered because of them.** The numbers do not collide (140 against 150–154), which is the guarantee that matters. | 2026-09-28 | **ACTIVE** |
| `DEF-IDN-7500–7539` · `CR-145-BRC08` | **`CR-145-BRC08` — six session and lockout rules become per-utility settings within fixed limits (`B1`–`B13`, `F1`–`F6`, `E2`, `E4`, `T1`–`T11`, `D1`–`D6`), branch `claude/confirm-understanding-3ktufc`.** Written here BEFORE the first row is filed, which is what `file_defect.py --block` refuses without — *a block claimed on the command line and nowhere else is the promise that does not survive the chat* — and it refused four lanes for exactly that on 2026-09-27/28. ⚠ **THE BLOCK OPENS AT 7500, WELL ABOVE THE FRONTIER (`7462`), RATHER THAN AT `max + 1`**, because sibling lanes compute `max + 1` correctly and all get the same answer (`DEF-1787`). ⚠ **`BRC08` IS A NEW SUFFIX FOR A NEW BRANCH** — `BRC07` was `claude/kind-goldberg-k0acqg`; the suffix is provenance and the NUMBER is what must be unique, which `G17` enforces even when suffixes differ. ⚠ **AND `allocate.py --verify` HAS A KNOWN PROSE-SCAN FALSE POSITIVE** — it counts this very row and any citation in a heading, so it can answer *TAKEN* for a number no register holds; it did so for `7220`, `7310` and `7051`. **Ask WHY before renumbering.** Version `2.389.0`, allocated once for the whole change request. | 2026-09-28 | **ACTIVE** |
| `DEF-INF-7540–7549` · `CR-145-BRC08` | **LANE SESS-DOCS — the same change request's record and deployment half: the change-request file, the three stories' test cases, the version, `09-infra`, `.env.example`, the beat entry and the end-to-end proof (`D3`–`D6`, `E2`, `E4`, `T11`), branch `claude/confirm-understanding-3ktufc`.** ⚠ **THIS LANE WAS BRIEFED WITH `7530–7539` AND THAT SUB-BLOCK COULD NOT BE USED** — recorded because the reason generalises. `CR-145-BRC08` is being built by THREE lanes and the row above reserves `DEF-IDN-7500–7539` for the CHANGE REQUEST rather than for any one of them, so a per-lane sub-block sits entirely INSIDE it. `file_defect.py` walks its candidate past every id in any OTHER active block, so every number in a nested range is excluded by the parent and it refuses with *"every id is taken"* — which is true of the BLOCK MAP and not of the register, where `DEF-IDN-7500` is the only id in the whole range. ⚠ **THE FIX IS A DISJOINT BLOCK, WHICH IS WHAT THE TOOL ITSELF SAYS:** *"Reserve a second block rather than spilling out of this one."* Narrowing the parent row was the alternative and was NOT taken — it is another lane's row, edited while that lane is live, which is hard-won law 11's revert-by-subtraction waiting to happen. `7540–7549` is outside every reserved range and holds no id on any ref. ⚠ **THE DURABLE LESSON IS THAT A BLOCK PER CHANGE REQUEST IS NOT A BLOCK PER LANE.** When one CR is built by several lanes at once, reserve one row EACH from the start, the way `CR-144-BRC07` did with `DEF-DEP-7400–7429` and `DEF-DEP-7430–7459`. | 2026-09-28 | **ACTIVE** |
| `DEF-DEP-7400–7429` · `CR-144-BRC07` | **LANE DEP-BACKEND — `CR-144-BRC07`, the deployment blockers on the backend: `/api/health` middleware, the migrate-at-start-up collision, CORS, the Origin guard, Secure cookies and HTTPS-behind-proxy (`H1`–`H9`, `X1`–`X6`), branch `claude/kind-goldberg-k0acqg`.** Written here BEFORE the first row is filed, which is what `file_defect.py --block` refuses without — *a block claimed on the command line and nowhere else is the promise that does not survive the chat*, and it refused three lanes for exactly that on 2026-09-27. ⚠ **THE BLOCK OPENS AT 7400, WELL ABOVE THE FRONTIER (`~7311`), RATHER THAN AT `max + 1`.** A sibling lane is live on the front end of this same change request in its own worktree, so both compute `max + 1` correctly and both get the same answer (`DEF-1787`'s mechanism). ⚠ **AND `allocate.py defect --verify` HAS A KNOWN PROSE-SCAN FALSE POSITIVE** — it counts this very row and any citation in a heading, so it can answer *TAKEN* for a number no register holds; it did so for `7220` and `7310` on 2026-09-27/28. **Ask WHY before renumbering.** `CR-144` was allocated with `allocate.py cr` and carries this branch's `BRC07` provenance; the suffix is provenance and the NUMBER is what must be unique (`G17` fails a duplicate number even when suffixes differ). | 2026-09-28 | **ACTIVE** |
| `DEF-DEP-7430–7459` | **LANE DEP-FRONTEND — the same change request's front end: three build modes, the per-environment API base URL, the 12 hand-built API links, and the security policy moving into a `<meta>` tag because there is no Node server on S3 (`FB1`–`FB12`), branch `claude/kind-goldberg-k0acqg`.** Recorded before the first row is filed, same reason as the row above. ⚠ **IT SHARES `CR-144-BRC07` WITH LANE DEP-BACKEND — ONE CHANGE REQUEST, TWO LANES**, because the change process asks for one CR per change and this is one change (a single deployment move) split by where the code lives, not two changes. **One version bump between them: `2.388.0`**, allocated with `allocate.py version --bump change` and re-verified at push time, because two lanes each bumping is `DEF-GOV-3756`'s collision. | 2026-09-28 | **ACTIVE** |
| `DEF-AST-7100–7109` · `CR-143-BRC07` | **LANE AST-SIZE — `CR-143-BRC07`, Size as a column on the asset registry (`S49`), branch `claude/kind-goldberg-k0acqg`.** The defect block was handed to this lane in its dispatch and is recorded here BEFORE the first row is filed, because `file_defect.py --block` refuses a block that lives only in the invocation. ⚠ **IT OPENS AT 7100, ABOVE THE FRONTIER, RATHER THAN AT `max + 1`** — two sibling lanes (REP-EDITOR-B at `7080–7089`, REP-SUBJECTS at `7050–7059`) are live on this branch in their own worktrees at this moment, so every lane computes `max + 1` correctly and every lane gets the same answer (`DEF-1787`'s mechanism). `allocate.py defect --verify 7100` answered *still free on every branch* at allocation and was re-run from the pinned tip at push time. **The `CR` number is a DIFFERENT FAMILY and is not inside this block**: `allocate.py cr` answered `143`, `--verify 143` answered *still free on every branch*, and the `BRC07` suffix is this branch's provenance. **USED: `DEF-AST-7100`** — `AssetDetailPage.tsx` prints the bare size-class CODE (`W-58`) in its Connection size Fact, which is the B14 rule 32 question this change answers for the LIST and which the portal answered for the customer on 2026-09-11; found by this lane, deliberately NOT fixed here because it is a different screen. `DEF-AST-7101–7109` remain UNUSED and free. **No `OQ` minted** — nothing this change decided is a fact only the PO holds (law 13); the five judgments are in the CR's §4 with their reasoning. | 2026-09-27 | **ACTIVE** |
| `DEF-REP-7010–7019` | **LANE REP-VIEWER-UI — the five changes the Product Owner asked for on the Billing Register (`RPT-02`, screen `2·1b`) after looking at deployed `v2.380.3`, branch `claude/kind-goldberg-k0acqg`.** The services column, the usage column, the header block, the KPI band and the filter row. ⚠ **THE BLOCK WAS HANDED TO THIS LANE BY NAME AND IS WRITTEN HERE BEFORE THE FIRST ROW IS FILED**, which is what `file_defect.py --block` refuses without — *a block claimed on the command line and nowhere else is the promise that does not survive the chat*. ⚠ **7010 IS NOT `max + 1`, AND THAT IS THE POINT.** `file_defect.py` answers `7091` from this checkout; three sibling lanes are live in `apps/reports` at this moment and every one of them computes the frontier correctly and gets the same number (`DEF-1787`). Verified free against the REMOTE tip, which is the only world that can answer it. **USED: `DEF-REP-7010`** (the services and usage columns), **`7011`** (the four-line header), **`7012`** (the `Today` shortcut putting the four filter labels on two baselines), **`7013`** (the KPI band's height) and **`7014`** (REPORTED, not taken: the `invoices` dataset types `services` as `text`, so the chips are decided by a column NAME rather than by the dataset — one decision for all forty-six reports, and it belongs to whoever owns `datasets.py`). **`DEF-REP-7015`** (REPORTED, not taken: the CSV export still carries the counted zeros the screen now hides, so a downloaded register and the screen it came from disagree — a JUDGMENT for the PO, not a bug). **`DEF-AST-7016`** (the front-end typecheck is RED on the branch over `AssetSizeColumn.dom.test.tsx`, lane AST-SIZE's file — FILED, not fixed; the number is from this block and the MODULE segment names whose file it is, because `G17` checks the NUMBER and the segment is not part of it). `DEF-REP-7017–7019` remain UNUSED and free. | 2026-09-27 | **ACTIVE** |
| `DEF-7000–7009` | **LANE RAT-6960 — `DEF-RAT-6960`, the customer portal and the bill disagreeing about the same standing charge, branch `claude/kind-goldberg-k0acqg`.** ⚠ **TAKEN AT 7000 RATHER THAN AT `max + 1`, DELIBERATELY AND ON THE COORDINATOR'S INSTRUCTION.** The branch frontier stood at `6982` when this lane started and a sibling had already lost six numbers to races in one day; stepping clear of the frontier is what stops the same collision recurring, and it is the practice `DEF-RAT-6960`'s own reservation row records one block up. **Every number is verified free against the REMOTE at push time with `allocate.py defect --verify`**, which cannot reserve and only removes the stale read. **USED: `DEF-RAT-7000`** (the rating seam and `billing.gather._base_charge_for` disagreeing about a signature since 2026-09-24) and **`DEF-CWP-7001`** (the portal demo fixture's trash base saying `$8.00` where its charge code says `$9.00`). ⚠ **THE MODULE SEGMENT DIFFERS BETWEEN THE TWO AND THE NUMBER IS WHAT IS UNIQUE** — `7001` names a portal fixture, so it carries `CWP` rather than `RAT`; the block is a range of NUMBERS, per the PO ruling of 2026-09-03 that the running number is one series across every module. | 2026-09-27 | **RELEASED 2026-09-27** — 2 of 10 used (`DEF-RAT-7000`, `DEF-CWP-7001`); `7002–7009` were never taken and are free for the next lane |
| `DEF-REP-6990–6999` · `BR-REP-050` | **LANE REP-P6-W3 — the four Phase 6 reports wave 2 did not reach (R43 Trend Pack, R4 Bill Run Readiness, R27 Plans & Discounts, R46 Bill Projection), branch `claude/kind-goldberg-k0acqg`.** ⚠ **THE DEFECT BLOCK WAS HANDED TO THIS LANE AT DISPATCH RATHER THAN COMPUTED, AND THE ROWS BELOW ARE WHY.** The branch's frontier stood at `6980` and a sibling lost **six** numbers to races in one afternoon — `6933`/`6934`, then `6935`/`6936`, then `6962`/`6963` — each verified free when taken and gone by push time. `file_defect.py --block 6990-6999` allocates inside it. **USED: `DEF-BIL-6990`** (the tax-remittance summary reads GL account labels and throws them away). `6991`–`6999` remain UNUSED and free. ⚠ **`BR-REP-050` IS THE SAME LESSON IN A FAMILY `allocate.py` DOES NOT COVER, AND THIS LANE PAID IT.** The rule was written as `BR-REP-043`; by push time **three sibling lanes had landed `BR-REP-043`, `044` and `045`** — the statement's five subjects, the Delivery settings card and the manufacturer rule. Nothing allocates a `BR` id and a hand count reads only this checkout (law 11's id clause). Renumbered to **`050`**, stepping clear of the frontier rather than taking `max + 1` = `046`, and verified free across **every** `refs/remotes/origin` ref at push time. `BR-REP-046`–`049` are LEFT FREE for whichever lane reaches them first. **The version went the same way**: `2.381.0` was written, a sibling pushed it, and this lane ships **`2.382.0`**, re-verified against the remote. | 2026-09-27 | **ACTIVE** |
| `DEF-REP-7070–7079` | **LANE REP-EDITOR-A — the report-editor QUICK PASS (`RPT-02`, screen `2·2`), branch `claude/kind-goldberg-k0acqg`.** Four tasks from the Product Owner's report on deployed v2.380.3: ask for the required record first, name every field in words, never show an empty preview without its reason, and correct `ATTRIBUTES 7 of 5`. Written here **before the first row is filed**, which is the thing `file_defect.py --block` refuses without. ⚠ **7070 IS ABOVE THE FRONTIER, NOT `max + 1`** — the allocator answers `6982` from this checkout and lane REP-EDITOR-B records the same answer for itself in the row below: two lanes, two correct computations, one number (`DEF-1787`). Stepping clear is the only answer that does not race. ⚠ **THIS ROW WAS SPLICED IN ONCE AND VANISHED** — a sibling rewrote this file from the tip in the shared working tree between the splice and the first `file_defect.py --block` call, which then refused the block that had been reserved twenty minutes earlier. Law 11's mechanism two, happening to the reservation file itself; it is why this lane pushes its governance rows before its code rather than after. **USED: `DEF-REP-7070`** (the whole PO report — four symptoms, one screen, one fix) and **`DEF-REP-7071`** (on a MODULE VIEWER the edit panel offers its dataset's columns, none of which the report serves; REPORTED, not taken). `DEF-REP-7072–7079` remain UNUSED and free. | 2026-09-27 | **ACTIVE** |
| `DEF-REP-7080–7089` | **LANE REP-EDITOR-B — wave two of the report-editor redesign (`RPT-02`, screen `2·2`), branch `claude/kind-goldberg-k0acqg`.** The block was handed to this lane in its dispatch briefing and was **never written here**, so `file_defect.py --block 7080-7089` refused it — the guard working exactly as its own refusal sentence says (*“a block claimed on the command line and nowhere else is the promise that does not survive the chat”*). It is recorded now, before the first row is filed. ⚠ **THE BLOCK OPENS AT 7080, ABOVE THE FRONTIER, RATHER THAN AT `max + 1`, WHICH `file_defect.py` ANSWERS AS `6982`.** A sibling lane (REP-EDITOR-A) is running the quick pass over the same screen in its own worktree at this moment and has pushed nothing, so both lanes compute `max + 1` correctly and both get 6982 — `DEF-1787`'s mechanism with two participants. Stepping clear of the frontier is the only answer that does not race. **USED: `DEF-REP-7080`** (the edit panel's Filters section draws every declared filter at once, where p31 §4 draws only the set ones plus `+ Add filter`). `DEF-REP-7081–7089` remain UNUSED and free. ⚠ **NO `OQ` MINTED AND NONE TAKEN BY THIS LANE**: the one thing this lane could not decide — whether the builder becomes a PAGE, reversing the PO's `panel` ruling of 2026-09-26 — is a ruling that collides with a signed ruling, which law 13 sends to the PO rather than to the register. | 2026-09-27 | **ACTIVE** |
| `DEF-REP-7050–7059` | **LANE REP-SUBJECTS — `CR-142-BRC07` `P2.8` / `P2.15` / `P2.16` (the statement's five subjects, `BR-REP-043`) and `P5.5`'s fourth card (`BR-REP-044`), branch `claude/kind-goldberg-k0acqg`.** ⚠ **THE BLOCK OPENS AT 7050, ABOVE EVERY WATERMARK IN THIS FILE, RATHER THAN AT `max + 1`** — the block was dispatched to this lane by name, and sibling lanes are live in `apps/reports`, `apps/payments` and `apps/rating` at this moment, so every one of them computes `max + 1` correctly and every one of them gets the same answer (`DEF-1787`'s mechanism). Verified with `allocate.py defect --verify 7050` (*still free on every branch*) and re-derived from the pinned tip at push time (law 11's id clause). **USED: `DEF-REP-7050`** — the `ruleCards()` pin in `SettingsReferenceData.test.tsx` was RED from `97ac0ddd0` (2026-09-27) because `P4.6` added two `kind: "rules"` cards and did not move the count that pins them; the guard fired on time and nobody read it (hard-won law 7). FIXED in the same commit that adds the Delivery card. **`DEF-REP-7051`** — the unit statement's Occupant column is empty on every line the product has written (stamping landed 2026-09-24; hard rule 4 forbids a backfill), and **`DEF-REP-7052`** — `Subject.head_from` is published and rendered NOWHERE, so no report head names what it is about. **`DEF-REP-7053`** — the statement has a working export stream (`statement_stream`, registered in `MODULE_STREAMS` and measured yielding every row) and the report is not in `exports.RESOURCES`, so `exportable` is false and no Download button is ever offered: hard-won law 2 in its original direction. `DEF-REP-7054–7059` remain UNUSED and free. ⚠ **`allocate.py defect --verify 7051` ANSWERS *TAKEN* AND IS WRONG** — it scans the WORKING TREE's prose, where the id appears in this row and in `CR-142-BRC07` §17.5, so it reads a CITATION as an allocation; `--verify 7052`, which has no such heading, answers *free* from the same tree. That is the prose-scan fault already recorded for `allocate.py oq` (decision log 2026-09-02) and for the `cr` family (`DEF-GOV-4997`). Both ids were confirmed free the only way that answers it: absent from the register at the pinned tip and from every `refs/remotes/origin` ref. | 2026-09-27 | **ACTIVE** |
| `DEF-RAT-6980` | **LANE RAT-5782, SECOND ALLOCATION — `DEF-RAT-6980`, the 28 tests in the rating base-resolution neighbourhood that have been RED on this branch for days and that nobody has read.** Found by reading failures this lane did not cause (hard-won law 7 habit 1) while proving `DEF-RAT-5782`. ⚠ **THIS IS THE SAME LANE'S THIRD AND FOURTH LOSS OF THE FRONTIER IN ONE AFTERNOON** — the row below records `6933`/`6934` and then `6935`/`6936` going to siblings; `6962` and `6963` went the same way twenty minutes later, both answering *TAKEN — a sibling pushed it*. Stepped clear again to `6980`, verified free against the REMOTE at the moment of use, and the register was rebuilt as the pinned tip's bytes plus ONE appended row with the prefix proved byte-identical. **The durable lesson this branch is now paying for four times over: on a branch with this many live lanes, `max + 1` is never the answer — claim a block well clear of the frontier BEFORE you start, which is what this file is for.** **USED: one. No range is held open.** | 2026-09-27 | **RELEASED 2026-09-27** — the id is USED; nothing else taken |
| `DEF-RAT-6960` · `DEF-RAT-6961` | **LANE RAT-5782 — `DEF-RAT-5782`, the bill charging the base charge code the rate schedule names, branch `claude/kind-goldberg-k0acqg`.** Two defect ids for findings this lane made and did NOT fix: `DEF-RAT-6960` (the rate-change impact analysis and the portal's standing charge read the base through `rating.seams.base_charge_for`, which takes no binding) and `DEF-RAT-6961` (the activation gate admits an ACCOUNT-LEVEL `is_base` code that the live read, which narrows on the service, can never return). ⚠ **TAKEN AT 6960 RATHER THAN AT `max + 1`, AND THE FIRST TWO ATTEMPTS WERE LOST TO SIBLINGS INSIDE FORTY MINUTES.** `file_defect.py` allocated `6933`/`6934`; by push time `allocate.py defect --verify` answered *TAKEN — a sibling pushed it* for BOTH. Renumbered to `6935`/`6936`; **those were taken too**, in the twenty minutes it took to rebuild the register. That is law 11's id clause with several participants, and the only answer that does not race is to step clear of the frontier — which stood at `6936`, counted across every `refs/remotes/origin` register rather than from this checkout. `6960` and `6961` were verified free against the remote at push time, and the register was rebuilt as the pinned tip's bytes plus two appended rows with the prefix proved byte-identical. **USED: both. No range is held open** — this is one task, not a wave. | 2026-09-27 | **RELEASED 2026-09-27** — both ids USED at allocation; no block reserved, so there is nothing to return |
| `DEF-LED-6600–6619` · `OQ-INT-6620` | **LANE FIN-P5 — Phase 5 of the Finance blueprint (`05-prototype/07 Finance Blueprint.pdf` p018, §03 p019–p073: the partner contract), branch `claude/kind-goldberg-k0acqg`.** ⚠ **THE BLOCK OPENS AT 6600, ABOVE THE FRONTIER, RATHER THAN AT `max + 1` — WHICH `allocate.py defect` ANSWERS AS `6554`.** **Four Finance-blueprint lanes are dispatched at once** (phases 2, 3, 4 and 5) into their own worktrees off one branch, so every one of them computes `max + 1` correctly and every one of them gets 6554 — `DEF-1787`'s mechanism with four participants. Stepping clear of the frontier is the only answer that does not race, and it is the precedent this table already records for the five `CR-094` step-1 lanes. **`OQ-INT-6620` is taken BY HAND** — nothing in `allocate.py` allocates an `OQ`, and `allocate.py oq` reads `CLAUDE.md`'s own worked examples as the watermark (the known prose-scan bug, decision log 2026-09-02). It is taken from INSIDE this block rather than from the `OQ` register's own frontier for exactly the same reason the defect half steps clear, and it is verified free across every `refs/remotes/origin` ref and re-verified from the pinned tip at push time. | 2026-09-24 | **ACTIVE** |
| `BR-LED-796` · `DEF-LED-6222` · `DEF-LED-6223` | **LANE P2-LEDGER — `P2.21` of the payments blueprint phase 2 (`CR-136-BRC07` §3.3: seed `6850 Cash over and short`), branch `claude/laughing-thompson-kpmwih`.** One business rule and two defect ids, **all three USED at allocation; no block is held open** — this is one task, not a wave. **`BR-LED-796` was taken BY HAND and is the one that needed recording**: `allocate.py` has no `br` family, so the number is the module file's own maximum + 1 (`04-docs/05-modules/09-ledger/02-business-rules.md` stood at `BR-LED-795`) and **nothing can verify it against the remote**. `P2.22` is the very next lane to touch this module and would compute the same maximum from a checkout that does not yet hold this row — which is law 11's id clause exactly, one family over from the one `allocate.py` covers. **So `P2.22` takes `BR-LED-797`.** The two defect ids came from `10-scripts/file_defect.py --id-module LED`, which asks the remote. | 2026-09-23 | **RELEASED 2026-09-23** — all three ids USED at allocation; no block reserved, so there is nothing to return |
| `OQ-PAY-12575` · `OQ-PAY-12576` · `OQ-PAY-12577` | **LANE P0-BATCH — `P0.6` of the payments blueprint (re-keying the deposit batch), branch `claude/laughing-thompson-kpmwih`.** Three open questions and **nothing else**: no `CR` was allocated and no block claimed, because **nothing was executed** — `P0.6` is blocked on `counter_sessions` (`P0.3`–`P0.5`, LANE P0-DB) and on the three answers below, so a CR number taken now would sit unspent against `G17` and against `13-change-process.md` §0's disjoint-block rule. No defect id was taken either: nothing in the product is broken today — it implements `BR-PAY-025` exactly — what is wrong is a row in a task table, and that is recorded in the decision log rather than in the defect register. **Taken by hand**, because `allocate.py` has no `oq` write path that reserves; each was read as the register's maximum + 1 (`allocate.py oq` answered **12575**) and then **`allocate.py oq --verify` was run against the REMOTE for all three** — *"still free on every branch"* — and re-verified from the pinned tip at push time, per law 11's id clause. **USED: all three.** `OQ-PAY-12575` (what number the second till of the day banks under) · `OQ-PAY-12576` (what banks the ACH, card and wire money once every new batch needs a session) · `OQ-PAY-12577` (one batch per session, or per session × tender). **No range is held open** — this is not a wave. | 2026-09-22 | **RELEASED 2026-09-22** — all three ids USED at allocation; no block reserved, so there is nothing to return |
| `DEF-INT-5612`–`5615` · `DEF-GOV-5616` · gate `G128` | **THE CR-115-BRC05 §6 LANE 1 ONE-ADDRESS REFACTOR (2026-09-17).** An operation's address was decided in SEVEN places and the brief named three; `apps/integrations/addressing.py` is the one place now, and `G128` refuses a second. ⚠ **RECORDED AFTER THE FACT, NOT RESERVED AHEAD OF IT, AND SAYING SO IS THE POINT.** Each id was taken one at a time through `file_defect.py --id-module` (which asks the REMOTE) and `allocate.py gate`, and `G128` was re-verified free at push time. `G17 duplicate-ids` is IN THE STANDING RED SET, so the gate that would have caught a collision could not — `allocate.py --verify` was the only live check and it is the one that was run. ⚠ **`allocate.py defect --verify` ANSWERED *TAKEN* FOR ALL FOUR DEFECT IDS AND WAS WRONG**: it reads commit MESSAGES across every ref, and this lane had pushed its code commit — which cites them — before its register commit. Checked by hand: zero occurrences in the register on all 52 remote branches, one commit message, this lane's own. **Nothing was renumbered**, and that false alarm is `DEF-GOV-5616`. **USED: all five defect ids and `G128`. No block is held open** — nothing here is a wave. | 2026-09-17 | **RELEASED 2026-09-17** — every id used at allocation; no range reserved, so there is nothing to return |
| `BR-CUS-1075` | **`CR-094-BRC01` REQUEST-SCREEN WAVE, LANE C — what a refusal and an ask-for-more record, and which of the three things reaches the applicant (`DEF-CUS-5389`).** ⚠ **TAKEN AT 1075 RATHER THAN AT `max + 1`, WHICH IS `BR-CUS-1071`, FOR THIS FILE'S OWN `DEF-1787` REASON:** two sibling lanes are live in `apps/customers` in their own worktrees at this moment — the approve path and the request's read payload — and `BR-CUS-1070` was itself taken at a deliberate distance on 2026-09-13 for the same reason. **Nothing allocates a `BR` id**: `allocate.py` has no `BR` family and `file_defect.py` allocates defects, so the number is read by hand and a hand count reads only this checkout (law 11). A gap costs nothing and a collision moves every citation. `1071`–`1074` are LEFT FREE on purpose, for the siblings that may already hold them. | 2026-09-15 | **SPENT** (one rule, written) |
| `BR-CUS-1070` | **`CR-094-BRC01` CAPTURE WAVE, LANE F — each service on a request carries its own start (`DEF-CUS-5195`, the data half).** ⚠ **TAKEN AT 1070 RATHER THAN AT `max + 1`, WHICH IS `BR-CUS-1055`, AND THE REASON IS THIS FILE'S OWN `DEF-1787` LESSON:** three sibling lanes are live in `apps/customers` in their own worktrees at this moment — the approve path, the request read payload and the messaging seam — so every one of them computes `max + 1` correctly and every one of them gets 1055. Stepping clear of the frontier is the only answer that does not race, and there is no `BR` family in `allocate.py` to ask the remote with. Verified free in the working tree and across every `refs/remotes/origin` ref, and re-verified from the pinned tip at push time (law 11's id clause). **USED: `BR-CUS-1070`** (each service carries its own requested start; neither it nor the job's `Connection date` falls back to the other). **`BR-CUS-1071–1079` are UNUSED and free**, and `BR-CUS-1055–1069` are left where they are for whichever lane reaches them first. **No `OQ` minted and no `DEF` minted** — `DEF-CUS-5195` already names this exact divergence and stays OPEN because its surface is the SCREEN, which is lane D's half of the same defect. | 2026-09-15 | **ACTIVE** |
| `BR-BIL-1040` · `BR-BIL-1041` · `DEF-BIL-5301` · `DEF-BIL-5302` | **`DEF-BIL-5255` + `CR-105-BRC03` — the bill run's standing answers, its name, and the template chosen at Scope (the SCHEMA half).** The two `BR-BIL` ids were taken BY HAND as the billing register's maximum + 1 (`BR-BIL-1039` was the ceiling repo-wide), because there is no `BR` family in `allocate.py` and neither rule amends an existing one: `BR-BIL-1040` is the run's standing answers to the recurring cases and `BR-BIL-1041` is *deciding is not stamping* — the template is CHOSEN at Scope and its version is still PINNED at issue. The two `DEF-BIL` ids came from `file_defect.py --id-module BIL` (*"it is inside no active block"*) and were re-verified free against every fetched `origin` ref at push time. **No `OQ` minted, and law 13 is why:** the only thing that could have been asked — whether a run-level default may pre-answer a case `BR-BIL-015` says is per-account — is a SUPERSESSION and is therefore STATED rather than asked, in the decision log, in `BR-BIL-1040` and in the review-ledger row, which asks the PO for one line confirming it. | 2026-09-14 | **RELEASED 2026-09-14** — all four ids USED; nothing else taken. Shipped as **`2.267.0`**. |
| `DEF-BIL-5090` | **`CR-094-BRC01` STEP 2 WAVE B — the money, sub-type, portal-sentence, dead-copy and Close-out repairs on the Account detail (`S21`).** **ONE id, and it is NOT one of the five this wave repaired** — those are lane 2's and lane 5's, already filed and now closed `fixed` (`DEF-CUS-4998` · `4999` · `5000` · `5004` · `5005`) and `duplicate` (`DEF-CUS-5008`, the same two lines as `4999`). The new row is a defect this wave FOUND and did not fix: `POST /accounts/{id}/disconnect-case/cut` cannot commit a cut, because `billing/one_time.create_one_time_run` writes `run_by_id=getattr(run_by, "pk", run_by)` and the API's actor is `SimpleNamespace(id=…, role=…)` with no `pk`. **Allocated by `file_defect.py`, which reported *"allocated DEF-5090; it is inside no active block"*** — recorded here for exactly that reason, so a sibling stepping up from the frontier does not take it. **Then `allocate.py defect --verify 5090` was run against the REMOTE and answered *still free on every branch*** before the row was written, and the register's prefix was proved byte-identical to the pinned tip's first 5,555,441 bytes afterwards — so a sibling's `DEF-CUS-5089`, which landed in the shared working tree between the read and the write, was neither published nor reverted (law 11's mechanism five). ⚠ **THE ID WAS CITED IN CODE BEFORE IT WAS ALLOCATED, AND THE PLACEHOLDER WAS WRONG.** `cr094_wave_b_seed_cut_account.py` was pushed naming `DEF-CUS-5015`, a number this lane invented; it is corrected to `DEF-BIL-5090` in the next commit. That is `DEF-NOT-4436`'s shape in miniature — an id cited without a register row — and the lesson is the one that row already teaches: cite nothing until the allocator has answered. **USED: `DEF-BIL-5090`. Nothing else taken — no `OQ` minted, because nothing this wave decided is a fact only the PO holds (law 13); the four judgments are in `02-decision-log.md` with their figures.** | 2026-09-12 | **RELEASED 2026-09-12** — the one id USED. |
| `OQ-CUS-1769` | **`CR-094-BRC01` STEP 1 LANE 2 — the Account detail (`S21`), blueprint pages 6–59.** ONE `OQ` id, taken by hand because `file_defect.py` allocates defects and nothing allocates an `OQ`. Taken as the register's maximum + 1: the highest table row in `01-open-questions.md` is `OQ-MET-1768`. ⚠ **`OQ-RAT-12347` IS IN THE SAME FILE AND IS NOT THE MAXIMUM** — five digits where every neighbour is four, minted 2026-09-08 by `CR-081`; reading it as the watermark would skip ten thousand numbers for ever. Verified free against every fetched `origin` ref before the push. It sits BELOW lane 1's `OQ-CUS-1790–1799` block and does not enter it. ⚠ **THE SEVEN DEFECT IDS CAME FROM `file_defect.py` AND THREE OF THEM COLLIDED — `DEF-NOT-4436`'s SHAPE, SEEN LIVE AGAIN.** The tool allocated `5001`–`5003`; `allocate.py defect --verify` then answered **TAKEN** for all three, because a sibling had cited `DEF-MET-5003` (and its neighbours) in `02-decision-log.md` and `04-docs/05-modules/05-assets/02-business-rules.md` **without writing a register row**, and `file_defect.py` reads only the register. They were renumbered BEFORE the commit by rebuilding the register as the pinned tip's bytes plus seven appended lines — **the prefix was proved byte-identical first** — and then re-verified one by one. **USED: `OQ-CUS-1769` · `DEF-CUS-4998` · `DEF-CUS-4999` · `DEF-CUS-5000` · `DEF-CUS-5004` · `DEF-CUS-5005` · `DEF-GOV-5006` · `DEF-GOV-5007`.** Nothing else taken. | 2026-09-12 | **RELEASED 2026-09-12** — every id USED. |
| `OQ-CWP-1767` | **`CR-085` STEP 2 LANE 3 — starting and stopping service.** ONE id, taken by hand because `file_defect.py` allocates defects and nothing allocates an `OQ`. Taken as the register's maximum + 1: the highest table row is `OQ-WRK-1765` and the highest section heading is `OQ-RAT-1766`. ⚠ **`OQ-RAT-12347` IS IN THE SAME FILE AND IS NOT THE MAXIMUM** — it is five digits where every neighbour is four, it was minted on 2026-09-08 by `CR-081`, and reading it as the watermark would skip ten thousand numbers for ever. Said here so the next lane does not re-derive 12348 and think this row was wrong. Re-verified free against every fetched `origin` ref at push time (law 11's id clause). The defect id in the same commit, `DEF-CWP-4930`, came from `file_defect.py` (*"it is inside no active block"*). | 2026-09-11 | **RELEASED 2026-09-11** — the id is USED; nothing else taken. |
| `CWP-076` · `CWP-077` | **`CR-085` STEP 2 LANE 6 — PAYING (2026-09-11).** Two SCREEN ids, for the two screens the PO's *"it should be 3 screens - confirmed"* ruling created out of `CWP-038`: **`CWP-076` Check before you pay** (`/pay-now/check`) and **`CWP-077` Payment made** (`/pay-now/done`). **Taken from `CR-068` §9's own *Next free ground* line, which read `CWP-076`, and written INTO §9 in the same commit** — §9 is the authority the PO delegated (2026-09-03: *"You can assign number CWP-nnn - Assig all unqie numbers"*) and `G82` reads it, so an id that is not there is an id no gate will accept. ⚠ **THE TOOLING CANNOT VERIFY THIS FAMILY:** `allocate.py` knows defects, gates and versions and not `CWP`, so this block is the only thing standing between two lanes reaching for 076. **§9's next-free line was moved to `CWP-078` in the same commit.** **USED: both.** | 2026-09-11 | **RELEASED 2026-09-11** — both ids used, allocated in §9, mirrored into `screenIds.ts` by the merge lane with the routes |
| `CR-090`–`CR-094`, suffix **`BRC01`** | **BRANCH `claude/hi-0jmv62`.** Change requests raised while this branch is live are numbered from this block and carry `-BRC01`: `CR-090-BRC01` … `CR-094-BRC01`. **The suffix is provenance and the BLOCK is what makes the number unique** — see the CR id rule in `13-change-process.md` §0. | 2026-09-10 | **ACTIVE** |
| ⚠ **`CR-090` AND `CR-094` WERE TAKEN BY SIBLING BRANCHES OUT OF THIS BLOCK, 2026-09-10.** `allocate.py cr --verify 90` and `--verify 94` both answer *TAKEN — a sibling pushed it*. **The block was reserved and not honoured**, which is the collision the suffix scheme exists to prevent — and it is worth being precise about what did and did not work: the SUFFIX would not have saved us, because `CR-090-BRC01` and a sibling's `CR-090-BRCxx` are different strings that git merges cleanly; what caught it is `allocate.py --verify` asking the REMOTE at the moment of use, which is the layer `13-change-process.md` §0 says removes the stale read. `CR-091-BRC01` was taken instead. **Nothing is renumbered** — the two sibling CRs are real and pushed. The open question is whether the other branches know the blocks exist; if they do not, the reservation is a note we keep and they do not read. | 2026-09-10 | **BREACHED, RECORDED** |
| ⚠ **THE BLOCK'S STATE, 2026-09-12.** `CR-091-BRC01` (discount services, BUILT) · `CR-092-BRC01` (the Assets menu against its blueprint, step 2 running) · `CR-093-BRC01` (the shared-component findings ruling 7 moved out of 092, OPEN and sized). **`CR-090` and `CR-094` are gone to siblings**, so the block is SPENT: three numbers used, two lost, none left. **A further CR raised on this branch takes a number from `BRC02` (`095`–`099`) only after claiming that block here, or it collides with whichever branch holds it.** Every number above was confirmed with `allocate.py cr --verify <n>` against the REMOTE at the moment it was taken — `93` answered *still free on every branch* on 2026-09-12. | 2026-09-12 | **ACTIVE — BLOCK SPENT** |
| `CR-095`–`CR-099`, suffix **`BRC02`** | **UNCLAIMED — the second concurrent branch takes this block and writes its branch name into this row on the day it starts.** `CR-095-BRC02` … `CR-099-BRC02`. | 2026-09-10 | **OPEN — claim it before use** |
| `CR-100`–`CR-104`, suffix **`BRC03`** | **UNCLAIMED — the third concurrent branch takes this block and writes its branch name into this row on the day it starts.** `CR-100-BRC03` … `CR-104-BRC03`. A block with no branch name in it is not held by anybody; a branch that starts work without writing its name here is the promise-in-a-chat-message this whole file exists to replace. | 2026-09-10 | **OPEN — claim it before use** |
| ⚠ **THE ROW ABOVE IS STALE AND HAS BEEN SINCE 2026-09-14 — `CR-100`–`CR-104` / `BRC03` IS CLAIMED.** `claude/eager-johnson-r0k88b` claimed it that day and wrote a full section for it further down THIS FILE (*"`CR-100`–`CR-104`, suffix `BRC03` — BRANCH `claude/eager-johnson-r0k88b`, Billing"*), which records `CR-100`, `CR-101` and `CR-103` USED and `CR-102`/`CR-104` gone to siblings. **The row above was never amended**, so this register contradicted itself for a day: a summary table saying FREE above a section saying TAKEN, in the one file whose whole purpose is to stop two branches taking one number. It is left standing and corrected here rather than rewritten, which is how row 50 records its own breach. **Read the sections below, not this table, before taking a CR number.** | 2026-09-15 | **CLAIMED — the table above is stale** |
| `DEF-CUS-5060–5069` · `OQ-CUS-1790–1799` | **`CR-094-BRC01` STEP 1 LANE 1 — the Accounts register (`/:tenant/accounts`) and its seven sibling tabs, blueprint pages 3–5.** ⚠ **THE BLOCK OPENS AT 5060 / 1790, ABOVE EVERY WATERMARK IN THIS FILE, RATHER THAN AT `max + 1`.** `10-scripts/allocate.py defect` answers **5008** and **five `CR-094` step-1 lanes are dispatched at once into one shared tree** — so every one of them computes `max + 1` correctly and every one of them gets 5008, which is `DEF-1787`'s mechanism with five participants instead of two. Stepping clear is the only answer that does not race, and sub-letting a live block does not work (this file's own `DEF-2960` lesson). ⚠ **`allocate.py oq` answers `12348` and that is the KNOWN PROSE-SCAN BUG, not the frontier** — it is reading `CLAUDE.md`'s own worked examples `OQ-12345` / `OQ-123456`, recorded in the decision log of 2026-09-02, and it is the same fault the `cr` family carries as `DEF-GOV-4997`. The register's real maximum is **`OQ-1768`**, counted from `12-governance/01-open-questions.md`'s own rows. Both ranges were verified free in the working tree, across every `refs/remotes/origin` ref, and re-verified from the pinned tip at push time (law 11's id clause). **USED: `DEF-CUS-5060`** (six of the eight lists on the Accounts screen open on something other than creation order, against `BR-CUS-1046`), **`DEF-CUS-5061`** (the Imports tab's 200-row cap and its count-less envelope — `NFR-3` and `NFR-5`), **`DEF-SHL-5062`** (B14 rule 13's sort glyph never renders on an unsorted sortable header, shared `DataTable`), **`DEF-CUS-5063`** (the disconnects tab's primary reads `Start a disconnect`, which is in none of B14 rule 4's three grammars) and **`OQ-CUS-1790`** (six of those lists have NO sort control, so the ruling's own *"a clerk's chosen sort still wins"* has nothing to win with). `DEF-CUS-5064–5069` and `OQ-CUS-1791–1799` remain UNUSED and free. | 2026-09-12 | **ACTIVE** |
| `DEF-CUS-5091` | **`CR-094-BRC01` STEP 2 WAVE C — the PO's sort ruling built on all eight lists (the row above is this wave's step 1).** ⚠ **THIS ID IS ABOVE THE FRONTIER AND THE ROW ABOVE STILL HOLDS `DEF-CUS-5064–5069` FREE, WHICH IS THIS LANE'S OWN MISS — RECORDED RATHER THAN RENUMBERED.** `file_defect.py` takes `--block` for exactly this case (*"allocates inside it instead of stepping down past it"*, `DEF-1814`) and this lane did not pass it: it ran the allocator bare, got the register maximum + 1, and filed `DEF-CUS-5090` — which a sibling then took as **`DEF-BIL-5090`** minutes later, the same NUMBER under a different module prefix. **That is the collision `CLAUDE.md` describes for `CR` suffixes happening to a defect id: the STRING is unique and the NUMBER is not, and a number is what a person says out loud.** It was caught because law 11's id clause says to re-derive the ids at push time UNCONDITIONALLY, and `push_paths.sh` refused the push on the register having moved; the row was renumbered to **`5091`** against the new tip's own maximum and re-verified free on every branch before the second attempt. ⚠ **NOT RENUMBERED DOWN INTO 5064, DELIBERATELY:** by the time the block's spare ids were noticed the id was already cited in seven places — the register row, the decision log, the CHANGELOG, `BR-CUS-1046`, `OQ-CUS-1790`, the conformance record and the walkthrough's own expiry check — and respelling a cited id across seven files to save one number is the mass shared-file rewrite law 11 exists to prevent. **So the id stands and this row is the thing that stops a sibling stepping up from the frontier and taking it**, which is the reason `DEF-BIL-5090`'s row two above gives for existing. **USED: `DEF-CUS-5091`** (a clerk's chosen sort does not survive a refresh on seven of the eight tabs — half of `BR-CUS-1046`'s second clause, whose fix is a decision about how eight tabs share one URL). Nothing else taken: no `OQ` minted, because nothing this wave decided is a fact only the PO holds (law 13) — the four judgments are in `02-decision-log.md` with their figures. `DEF-CUS-5064–5069` stay FREE and are still the block a `CR-094` lane should reach for first. | 2026-09-12 | **RELEASED 2026-09-12** — the one id USED. |
| `DEF-CUS-5064` · `DEF-AST-5065` · `DEF-WRK-5066` · `DEF-SHL-5067` | **`CR-094-BRC01` STEP 2 WAVE D — the request queue, the import and the two wizards with no step rail (`2.239.4`).** ✅ **TAKEN FROM LANE 1's OWN BLOCK, WHICH IS WHAT THE ROW ABOVE ASKED THE NEXT `CR-094` LANE TO DO** — `file_defect.py --block 5060-5069`, which allocates inside it instead of stepping down past it (`DEF-1814`), rather than running the allocator bare and landing at `5093` above the frontier. That is wave C's recorded miss not repeated. ⚠ **`allocate.py defect --verify 5064` ANSWERS *TAKEN* AND IT IS THE DOCUMENTED OVER-READ, NOT A COLLISION.** `_claimed_elsewhere` greps the tip's whole tree for `DEF-([A-Z]{3}-)?[0-9]{3,5}`, and the ONLY two claims of the string `5064` anywhere in it are the two rows of this table saying it is free — proved with `git grep -nE "DEF-([A-Z]{3}-)?5064" <tip>` and a 4,000-commit message walk, both empty of any register row. The allocator's own docstring says over-reading is the safe direction; `file_defect.py`, which reads the REGISTER and the REMOTE, allocated it. **USED: `DEF-CUS-5064`** (the detail-page fixture's condition keys are not the server's, so the blocked-approval assertion compared one unresolvable key against itself — a check that could not fail, found by this wave's own new assertion), **`DEF-AST-5065`** (five class tokens rendering nothing on three shipped screens — filed for a red this lane did not cause and closed `duplicate` within the hour, because a sibling filed the same red as `DEF-SHL-5088`; two lanes reading one red is law 7's first habit working, not a fault), **`DEF-WRK-5066`** (the Work rule builder hand-rolls its own step rail — the mirror of `DEF-CUS-5071`, found by the census that row's prevention column asked for, and baselined by name so the check ships GREEN) and **`DEF-SHL-5067`** (`WizardFrame`'s active step badge is near-white on near-white on every wizard in the product, measured with `getComputedStyle` on three of them). `DEF-CUS-5068` and `5069` remain UNUSED and free. **No `OQ` minted** — nothing this wave decided is a fact only the PO holds (law 13), and the one question in its subject (`OQ-CUS-1790`, the requests list opening on the oldest) was already asked and was NOT re-asked; the judgments are in `02-decision-log.md` with their figures. | 2026-09-12 | **RELEASED 2026-09-12** — four ids used, `5068`–`5069` returned free. |
| `DEF-CUS-5072–5079` · `OQ-CUS-1810–1819` | **`CR-094-BRC01` STEP 1 LANE 4 — ending service: the move-out wizard (`S20`), its standalone door, the close-out act, the transfer wizard (`S89`) and the disconnect wizard (`S90`), blueprint pages 98–131.** ⚠ **THE DEFECT HALF WAS ALLOCATED BY `file_defect.py` AND SEVEN OF ITS EIGHT ROWS WERE SWEPT ONTO THE BRANCH BY A SIBLING'S PATHSPEC COMMIT BEFORE THIS LANE COMMITTED THEM** — hard-won law 11 mechanism five (`DEF-168`), seen live. `allocate.py defect --verify` then answered **TAKEN — a sibling pushed it** for `5072`–`5078`, which is TRUE and is the lane's own rows coming back at it; each was read out of `HEAD` by title before anything was renumbered, and **nothing was renumbered**, because a rename would have orphaned seven rows already on the branch. `DEF-CUS-5079` was still uncommitted and is pushed by hand from a temp blob so the three sibling rows sitting beside it in the shared register are neither published nor reverted. **THE `OQ` HALF OPENS AT 1810, ABOVE EVERY WATERMARK, RATHER THAN AT `max + 1`** — lane 2 took `OQ-CUS-1769` and lane 1 holds `OQ-CUS-1790–1799`, so `1800–1809` is left clear for lanes 3 and 5 rather than contested. ⚠ `OQ-RAT-12347` IS IN THE REGISTER AND IS NOT THE MAXIMUM — five digits where every neighbour is four, minted 2026-09-08 by `CR-081`; reading it as the watermark would skip ten thousand numbers for ever (lane 2 recorded the same, above). **USED: `DEF-CUS-5072` · `5073` · `5074` · `5075` · `5076` · `5077` · `5078` · `5079` · `OQ-CUS-1810`.** `1811`–`1819` unused. | 2026-09-12 | **RELEASED 2026-09-12** — `1811`–`1819` returned unused. |
| `BR-BIL-1032` · `DEF-BIL-4713` | **`CR-089` WAVE K — finding things by address (`PUJ-51`/`PUJ-52`/`PUJ-53`).** Two ids, both taken by hand and both re-verified free against every fetched `origin` ref at push time. `DEF-BIL-4713` came from `file_defect.py` (*"it is inside no active block"*); `BR-BIL-1032` was taken as the billing register's maximum + 1 because this module had **no rule at all** for its own list's search set, so there was nothing to amend. No `OQ` minted: wave K raised no question — the PO's sentence settled the requirement and every remaining choice was a judgment this lane made and wrote into the decision log (law 13). | 2026-09-09 | **RELEASED 2026-09-09** — both ids USED; nothing else taken. |
| `DEF-NOT-4436–4439` | **THE CR-076 TEMPLATE-DESIGNER LANE (2026-09-07)** — the surface switcher, the 60/40 split and the Print control on `SET-10`. **Opened at 4436 because `allocate.py defect` says so and `file_defect.py` disagreed**, which is the whole reason this row exists: a sibling had taken `DEF-NOT-4416` and CITED it in `02-decision-log.md` without writing its register row, so the register-only allocator handed it out again and `allocate.py defect --verify 4416` refused it — *TAKEN, a sibling pushed it*. The mis-numbered row was removed by restoring the register to the pinned tip's exact bytes (it was the only difference) and re-filed inside this block. **USED: `DEF-NOT-4436`. `4437`–`4439` unused and free.** ⚠ The lane's own earlier defect, `DEF-NOT-4414`, was filed and closed before this block was opened and sits outside it. | 2026-09-07 | **ACTIVE** |
| `DEF-GOV-3738` · gate `G89` | **THE DUPLICATE-GATE-NUMBER LANE (2026-09-04) — `DEF-GOV-3654` + `DEF-CWP-3734`.** One gate, one number: `g84_provider_error_seam` becomes `G89` (the later of the pair, 05:30), `_assert_registry_sane` gains a fifth check that refuses a duplicate leading G-number, and the `G27` pair is a FROZEN one-entry exception (measured: moving it costs 259 citations across 66 files). Nine wrong bare-`G84` citations corrected. **Taken from the register maximum and the pinned tip at PUSH time**, which is the clause this whole family exists to teach. **USED: `DEF-GOV-3738`; gate `G89`.** | 2026-09-04 | **ACTIVE** |
| `DEF-CWP-3700–3719` · `OQ-CWP-1560–1569` · gate `G84` · migrations `portal 0003–0005` | **THE CR-068 WAVE C BUILD LANE (2026-09-04) — *Start service before identity exists*.** The two tables the applicant's journey needs (`portal_application_drafts`, `portal_consent`) and their RLS, the public availability read with its fees and deposits, the draft that survives a closed tab, the submit that takes the paperless consent, the quick asks, four screens (`CWP-008` · `CWP-047` · `CWP-009` · `CWP-010`), one gate and the wave's browser walkthrough (`04-docs/05-modules/15-portal/10-execution-plan.md` wave C, C1–C6). **The block opens at 3700 / 1560 above every watermark:** `DEF-WRK-3651` and `DEF-MET-3652` were the filed maxima and `OQ-CWP-1510` · `OQ-INT-1530–1539` sit below. Gate numbers re-checked at the moment the file was created — the plan says `G84` and `G81`–`G83` were taken, so `G84` it is. Re-derived from the tip at push time (law 11's id clause). **USED: `DEF-CWP-3700`–`3710`, `OQ-CWP-1560`; gate `G84`; migrations `portal 0003`–`0005`.** ⚠ **`portal 0005` WAS NOT IN THE RESERVATION AND WAS TAKEN THE SAME DAY** — `DEF-CWP-3709`, the future-date CHECK on `portal_consent` rebuilt around the wall clock; an applied constraint cannot be edited in place, so a repair to a migration is always a new migration. | 2026-09-04 | **ACTIVE** |
| `DEF-CWP-3640–3649` · gates `G81–G82` · migrations `portal 0001–0002` | **THE CR-068 WAVE A BUILD LANE (2026-09-03 → 04) — *Switch it on*.** The portal module, its first table and RLS, the guest front page, the two staff screens, the two gates and the browser walkthrough (`04-docs/05-modules/15-portal/10-execution-plan.md` wave A, A1–A9). ⚠ **THE PLAN'S NUMBERS WERE TAKEN BY THE TIME IT WAS BUILT:** it says `G75` and `G78`; `G75`–`G77` are CR-069 wave A's, `G78` CR-070's and `G79`–`G80` CR-069 wave B's, so the write-point gate is **`G81`** and the screen-register gate **`G82`** (`DEF-CWP-3640`). The block opens at 3640 because `DEF-INT-3580–3599` (CR-069 wave B) and `DEF-3600–3619` (corrections) sit below it and `DEF-3632` was the filed maximum at reservation. **No `OQ-` minted**: nothing this wave decided is a fact only the PO holds; the one question it builds against — the response-time target — is `OQ-CWP-1510`, minted by the load ruling. **USED: `DEF-CWP-3640`, `DEF-INT-3641`, `DEF-INT-3642`, `DEF-SHL-3643`, `DEF-INT-3644` (one running number, the module in the id); `3645`–`3649` UNUSED and free.** | 2026-09-03 | **ACTIVE** — wave shipped as `2.133.0`; five ids used, the block stays open for the wave's follow-ups |
| `DEF-3571–3579` (as `DEF-WRK-` · `DEF-CWP-` · `DEF-INT-nnnn`) | **THE DOCUMENT-CORRECTIONS LANE (2026-09-03) — filing what four finished lanes reported and nobody filed.** The Work journey lane (`J60`–`J67`), the portal and integration journey lane (`J30`–`J59`), the portal execution-plan lane and the Work execution-plan lane each reported errors in the documents they were building from — twenty-six findings, in prose, in their reports, none filed and none corrected. This lane verifies each against the primary source, files the real ones and corrects the document with a dated stamp. **Block opened at the register maximum plus one** — `DEF-WRK-3570` was the highest row at reservation time and `DEF-INT-3560–3569` is ACTIVE below it — so no sibling's active block is entered. Module-tagged ids per the PO ruling of 2026-09-03; one running number across modules. **USED: all nine, `DEF-WRK-3571`–`3579`.** ⚠ **OPENED AS `DEF-3571–3599` AND CUT TO `3571–3579` TWENTY MINUTES LATER — `DEF-1787`'s shape, seen live:** the CR-069 wave B lane wrote its `DEF-INT-3580–3599` row into the SHARED working tree between this lane's read of the register and its push, and this lane's pathspec push carried that row onto the branch unread (law 11, `DEF-168`'s mechanism — the numstat said `2 0` for a one-line insert and the hunks were not read). Nothing was lost — wave B's row is on the branch as it wrote it — and `file_defect.py` refused the tenth id because 3580 is theirs, which is the guard working. The remaining rows take the second block below. | 2026-09-03 | **RELEASED 2026-09-03** — full |
| `DEF-3600–3619` (as `DEF-WRK-` · `DEF-CWP-` · `DEF-INT-nnnn`) | **THE DOCUMENT-CORRECTIONS LANE (2026-09-03), second block** — the sixteen findings the first block could not hold once wave B's `3580–3599` was found beneath it. Opened at 3600, above every block this file holds. **USED: `DEF-WRK-3600`–`3603` · `DEF-CWP-3604`–`3612` · `DEF-INT-3613`–`3615`, and two bare governance ids on the lane's own tooling and process — `DEF-3616` (`close_defect.py` matches a module-tagged row only by its bare number) and `DEF-3617` (this lane's first push carried a sibling's uncommitted reservation row). `DEF-3618`–`3619` UNUSED and free.** Every row but `DEF-WRK-3603` (a stale code comment in `features/customers`, left for CR-070 wave B's B3 task, which rewrites that header) is `fixed` with the sha of the commit that corrected its document. ⚠ Re-derived from the pinned tip at push time (law 11's id clause). | 2026-09-03 | **RELEASED 2026-09-03** — every row applied |
| `DEF-INT-3580–3599` · `OQ-INT-1520–1529` · gates `G79–G80` | **THE CR-069 WAVE B BUILD LANE (2026-09-03) — the modal, the gate, the queue (the phase-1 launch).** The adapter protocol and its conformance kit, the five job kinds on their own `integrations` queue with the `celery-integrations` worker, the six write routes (`connect · test · PATCH · DELETE · credential · run`) with the coming-soon refusal and zero secret persistence, the S141 connect/manage modal with the field slot rendered from the manifest, two gates (the queue pair cloned from G59; no `/send` route), the six S141–S146 badges, and the wave's browser walkthrough. **The block opens at 3580 / 1520 above every watermark:** `DEF-WRK-3570` was taken outside any block by the parent lane and `OQ-WRK-1490–1509` · `OQ-INT-1510–1514` are held above. Re-derived from the tip at push time (law 11's id clause). **USED: `DEF-INT-3580` · `DEF-BIL-3581` · `DEF-3582`; gates `G79`–`G80`; no OQ.** | 2026-09-03 | **RELEASED 2026-09-04** — shipped as **2.132.0**. Used `DEF-INT-3580`, `DEF-BIL-3581` (a billing test-order finding, tagged with its own module as the corrections lane's mixed block was) and `DEF-3582` (a tooling finding, bare by rule), and gates `G79` (no `/send` route) and `G80` (the queue pair) — the row read `G78–G79` while a sibling carried it onto the branch ahead of this lane, and `G78` went to CR-070 the same hour. `DEF-INT-3583–3599` and `OQ-INT-1520–1529` unused and free. |
| `DEF-INT-3620–3629` · `OQ-INT-1530–1539` · badges `INT-01`–`INT-06` for `S141`–`S146` | **THE CR-069 WAVE D BUILD LANE (2026-09-03) — their words, and format as a parameter.** The codec registry lifted from the print vendor's (`apps/integrations/codecs.py`), the target-reference rows behind `GET` / `PUT /integrations/{key}/mappings`, S143's *Their words* tab, and the wave's browser walkthrough. **The block opens at 3620 / 1530 above every watermark:** the corrections lane holds `3600–3619` and wave B `3580–3599` · `OQ-INT-1520–1529`. **The six badges are allocated here because this lane mounted the first of the six screens** — the plan's own rule for B7 (*performed by this wave's lane as the first screen mounts*): `INT-01` S141 · `INT-02` S142 · `INT-03` S143 · `INT-04` S144 · `INT-05` S145 · `INT-06` S146, in `10-scripts/gates/g29_allocated_badges.txt`; wave B's own reservation row names the badges and takes these numbers rather than minting a second set. Re-derived from the tip at push time (law 11's id clause). | 2026-09-03 | **ACTIVE** |
| `DEF-INT-3560–3569` · `OQ-INT-1510–1514` · gates `G75–G77` · migrations `integrations 0001–0002` | **THE CR-069 WAVE A BUILD LANE (2026-09-03) — the grid that tells the truth.** The five tables and their RLS, the seventeen manifests and the registry, `GET /integrations`, the Settings → Integrations card grid replacing the placeholder sentence, three gates and the wave's browser walkthrough (`04-docs/05-modules/13-integrations/10-execution-plan.md` wave A, tasks A1–A10). Blocks open ABOVE the register maxima at reservation time (`DEF-3552` used, `DEF-WRK-3542–3551` active; `OQ-WRK-1490–1509` active) so neither can collide with the two documentation lanes' active blocks. Gate numbers: `g74` is the highest file at HEAD. | 2026-09-03 | ACTIVE |
| `OQ-INT-1470–1489` · `S141–S146` · `J48–J59` · `EP-INT-05–13` (with `BR-INT-018–053` · `US-INT-013–046`, reserved this morning below) | **THE CR-069 INTEGRATION SUBSTRATE DOCUMENTATION LANE (2026-09-03) — the ids the module folder cites.** Nineteen questions `OQ-INT-1470`–`1488` are minted in `01-open-questions.md` (the block runs to 1489; **1489 is UNUSED and free**); they are the first ids to carry a module code under the PO's ruling of the same day (decision log). Six screens `S141`–`S146` per `CR-069` §9 — connect/manage modal · connection detail · value mapping · machine credentials · consent (staff) · consent (customer); **`S147` is the next free `S`**. Twelve journeys `J48`–`J59` described in `13-integrations/04-flows.md` Part 2 — **the files in `08-qa/01-e2e/journeys/` are NOT written**; `J60` is next free. Nine epics `EP-INT-05`–`13` hold `US-INT-013`–`046`. ⚠ **ALLOCATED BY HAND FROM THE REGISTER MAXIMUM because no script reads a module-tagged id yet** — `file_defect.py` and the gates expect digits right after `OQ-`/`DEF-`; re-derive from this file before taking anything adjacent. | 2026-09-03 | **ACTIVE** |
| `OQ-CWP-1510` | **THE CR-068 PORTAL LOAD RULING (2026-09-03).** One question minted for the response-time target the PO's ruling refers to and the repo does not hold. `NFR-38`–`NFR-41` take the next four numbers in B6. Nothing else in this block. | 2026-09-03 | **RELEASED** — minted and cited the same hour |
| `OQ-WRK-1490–1509` · `DEF-WRK-3542–3551` · `Work-001–033` · `BR-WRK-001`+ · `US-WRK-001`+ · `EP-WRK-01–10` · `J60–J67` | **THE CR-070 WORK MODULE DOCUMENTATION LANE (2026-09-03), writing `04-docs/05-modules/16-work/`.** Count table approved by the PO the same day (decision log). Screens are `Work-nnn` by PO ruling (*"Use Work-nnn - code for this"*), `Work-001`–`033` = the blueprint's `WS-01`–`33`; the blueprint's `WM-01`–`49` and `WS-` are kept as handles and are not minted. Questions `OQ-WRK-1490` upward and defects `DEF-WRK-3542` upward carry the module code under the PO's ruling of the same day; **`DEF-3541` was the register maximum and `OQ-1489` the end of the block above when this was written** — re-derive before taking one. `BR-WRK-`, `US-WRK-`, `EP-WRK-` are new families (no code `WRK` existed); three digits, like `CWP` and `INT`. Journeys `J60`–`J67` follow `CR-069`'s `J48`–`J59`. ⚠ **The blueprint could be read only to about page 100 of ≥128** (16.3 MB against the 10 MB cap); rows written from the unread §15–§21 are marked so in the module folder. **USED (lane report 2026-09-03): all 33 screens · `BR-WRK-001`–`057` · `US-WRK-001`–`054` · `EP-WRK-01`–`10` · `J60`–`J67` (described in `04-flows.md`; the journey files are NOT written) · `OQ-WRK-1490`–`1497` (eight questions — `1498`–`1509` UNUSED and free) · `DEF-WRK-3542`–`3551` (ten record corrections).** | 2026-09-03 | **RELEASED 2026-09-03** — folder committed and every register row applied |
| gate `G78` · migration `metering 0044` · B2 `Addendum r23` · `DEF-MET-3619` · `DEF-INT-3630` · `DEF-PAY-3631` | **THE CR-070 WAVE A BUILD LANE (2026-09-03) — the module exists, and an order can stand alone.** `apps/work/` (the eleventh code module, five read-only seams, `GET /work-orders`), `metering/0044` (`work_orders.connection_id` nullable, `premises_id` + `account_id`, the `ck_work_orders_has_anchor` CHECK), the Work shell with its Orders tab, gate `G78` (the boundary gate, `CR-070` §12 gate 1) and the wave's browser walkthrough (`16-work/10-execution-plan.md` wave A, tasks A1–A9). **No `OQ-WRK`, no `DEF-WRK` and no `BR-WRK`/`US-WRK` id is minted** — the wave builds four existing stories and mints no rule. ⚠ **`G78` and the CR-069 wave B row above:** that row reserved `G78–G79` at the tip this was written against, and that lane's working copy in the shared tree had already moved itself to `G79–G80` (its `run_gates.py` entries read `G79 no-send-route` · `G80 integrations-queue-split`) when this lane took `G78` — the two lanes agree in the tree and the row above is that lane's to move when it pushes. `metering 0044` follows `0043`. Three defects filed, none of them Work's: `DEF-MET-3619` (a metering test left red by `DEF-2961`'s own fix), `DEF-INT-3630` (the Integrations grid's undeclared utilities paint no colour), `DEF-PAY-3631` (a nineteenth sample block without its provisioning mirror). ⚠ **3620 and 3621 were allocated first and given back**: `file_defect.py` reads the tip and this checkout, and the CR-069 wave D lane's reservation of `DEF-INT-3620–3629` existed only in the shared tree's uncommitted copy of this file — DEF-1787's shape, caught at push by re-reading the shared copy (law 11). | 2026-09-03 | ACTIVE |
| `DEF-3520–3539` | **THE INTEGRATOR, FILING TWO FINDINGS TWO LANES COULD NOT FILE THEMSELVES (2026-09-03).** Both the `C26` sub-metering-tenant lane and the `CS-40` filter-bar lane hit the same wall: `file_defect.py` stepped DOWN past every ACTIVE block and offered ids **a thousand or more below the live frontier**, inside no reservation and therefore inside nobody's promise — `DEF-1787`'s collision shape — and neither lane had `14-id-reservations.md` in scope, so neither could open a block to escape it. **A lane that cannot file a defect stops filing defects**, which is the failure mode worth naming: the C26 lane reported two real findings in prose and filed neither. This block is opened by the integrator so those findings become rows. **USED: `DEF-3520`** (a sample run ADDS five charge codes to the tenant's reference catalogue, 23 → 28, which `BR-TEN-058` says a run must never do — proved pre-existing at `4bd11ebe` in a detached worktree, so it is not any current lane's), **`DEF-3521`** (`C26`'s plan is unbuildable as written: `ledger` appears nowhere in `SAMPLE_MODULES`, so a captured supplier invoice has no seam to be written through and no block to be reported in, and four of C26's six pieces live outside the module the task names). `DEF-3522–3539` remain UNUSED and free. ⚠ **Re-derived from the pinned tip at push time** (law 11's id clause). | 2026-09-03 | **ACTIVE** |
| `DEF-3500–3519` · `OQ-1460–1469` | **THE SEEDING SCREEN FOLLOWS ALL EIGHTEEN STEPS TO THE END, AND A SERVICE SWITCHED ON AFTER SIGNUP STOPS BEING DECLARED METERED (PO 2026-09-03: *"Currently It does not complete all 18 steps on screen - after step 13 it does background job and then just jump insight the applciation, I want to complete all 18 steps on this screen itself; and see all jobs are completed"*).** ONB-04.5 stops polling after three minutes and then NAVIGATES on that timeout, so steps 14–18 are never seen; and `_apply_service_toggle` creates a `tenant_services` row without `billing_basis`, which is `DEF-2409`'s first fault unfixed on the second of the two creation paths. ⚠ **THE BLOCK OPENS AT 3480 / 1450, ABOVE EVERY WATERMARK IN THIS FILE, RATHER THAN AT `max + 1`.** `file_defect.py` stepped DOWN past **fifteen** held blocks and offered **`DEF-2358`** — a four-digit id eleven hundred below the live frontier, inside no reservation and therefore inside nobody's promise, which is exactly the shape `DEF-1787` turns into a collision. Sub-letting a live block does not work either (`DEF-2960`), and every block from 3200 up is ACTIVE. This lane works in its own `git worktree`, so a sibling's rows are in none of the refs this checkout can read, and every id is re-derived from the pinned tip at push time (law 11's id clause). **USED: `DEF-3500`** (the sign-up seeding screen gives up polling on a budget sized for TEN blocks while the plant walks EIGHTEEN, and the give-up phase is inside the automatic hand-over's allowed set — so *"we stopped asking"* is rendered as *"we are done"* and the operator is navigated away from five steps nobody ever saw), **`DEF-3501`** (a finished plant with steps that were never reached reports `ready`, because `anyStepFellShort` counts `failed` and `skipped` and not `not_started` — the exact *"the product said a thing succeeded and the thing had not happened"* shape `CR-064` exists to end), **`DEF-3502`** (`_apply_service_toggle` creates a `tenant_services` row naming six columns and not `billing_basis`, so a service switched on from S8 after signup is declared **metered** whatever it actually is — Fire, Trash, Solar, Battery, Storm water and Sewer included). **No `OQ` minted and none needed** — the three judgments this lane met (whether the automatic hand-over survives at all, what a step the run never reached says on its own line, and how long *"still moving"* is worth waiting for) were decided and written into `02-decision-log.md` with their figures rather than put back to the PO (law 13). `DEF-3503–3519` and `OQ-1460–1469` remain UNUSED and free. ⚠ **THIS BLOCK WAS FIRST OPENED AT `DEF-3480–3499` · `OQ-1450–1459` AND RENUMBERED BEFORE A SINGLE BYTE WAS PUSHED — `DEF-1787` HAPPENING LIVE, AND THE SECOND TIME ON THIS FILE IN ONE DAY.** 3480 was above every watermark this checkout could read, and the 2026-09-03 Product-Owner UI-walk lane, working in its own worktree, opened the identical block and pushed `DEF-3480` while this lane was measuring the plant. Both allocators were correct and neither could see the other. Caught by `push_paths.sh` refusing on a moved path and by re-deriving the register FROM THE PINNED TIP before committing — nothing else could have caught it — and by row order the later one is this lane's, so this lane moved rather than the sibling's pushed row. | 2026-09-03 | **ACTIVE** |
| `DEF-3480–3499` | **THE 2026-09-03 PRODUCT-OWNER UI WALK — the shared-component, routing and ACC-02 half.** The PO walked the deployed build and reported, verbatim: *"no screen IDs are shown on Payment screens"* · *"toolkit is got atatched the Tab line , tehre is no seperations - this is problem on many screens"* · *"on this screen Buttons are misplaced - as per UI rule, we have all Buttons on Top right + too much content here"* · *"Services on this account - I will show name of the service inform of similar to this - E Electric"* · *"on this screen why asset related to Trash , Fire , storm water are not shown"* · *"we did 2 month bills, which means 2 months detaisl are available - why theya re not displayed - Usage trend ... if it is multi service, then you ahve to provdie drop down for each service that is metered"* · *"Can we show deposite data as 4th item on this line - Balance / Plan from unit / Last activity"*. ⚠ **THE BLOCK OPENS AT 3480, ABOVE EVERY WATERMARK IN THIS FILE, RATHER THAN AT `max + 1`.** `file_defect.py` stepped DOWN past **fourteen** held blocks and offered **`DEF-2358`** — a four-digit id eleven hundred below the live frontier, inside no reservation and therefore inside nobody's promise, which is precisely the shape `DEF-1787` turns into a collision. Sub-letting a live block does not work either (`DEF-2960`), and every block from 3200 up is ACTIVE. This lane works in its own `git worktree`, so a sibling's rows are in none of the refs this checkout can read, and every id is re-derived from the pinned tip at push time (law 11's id clause). ⚠ **THIS ROW IS THE ONE FILE THIS LANE WROTE OUTSIDE ITS DISPATCHED SCOPE, AND IT IS RECORDED RATHER THAN LEFT QUIET:** the lane was scoped to the frontend plus the defect and decision registers, and `file_defect.py --block` refuses a range this file does not list — so the alternative to this row was filing seven Product-Owner-reported defects a thousand ids below the frontier, which is the collision this file exists to stop. | 2026-09-03 | **ACTIVE** |
| `DEF-3460–3479` · `OQ-1440–1449` | **UNIVERSAL SEARCH — the topbar box on every screen stops saying *"Search is not available yet"* and starts finding records (PO 2026-09-03: *"Can you enable universal search ?"*, then *"Universal search will search premises , unit assets , master, regular account , customer id, bill, payment, requests"*).** `GET /search` did not exist; the BE-08 kernel, the `onSearch` prop, its debouncer and its ✕ all did, and no route joined them — hard-won law 2, known and deliberate, held open by `DEF-2423`. This lane builds the endpoint, the nine module search sources, the results popover, and REMOVES `check_unwired_props.py`'s by-name exemption for `AppShell.onSearch` in the same commit. ⚠ **THE BLOCK OPENS AT 3460 / 1440, ABOVE EVERY WATERMARK IN THIS FILE, RATHER THAN AT `max + 1`.** `file_defect.py` stepped DOWN past **twelve** held blocks and offered **`DEF-2363`** — a four-digit id a thousand below the live frontier, inside no reservation and therefore inside nobody's promise, which is precisely the shape `DEF-1787` turns into a collision. Sub-letting a live block does not work either (`DEF-2960`), and every block from 3200 up is ACTIVE. This lane works in its own `git worktree`, so a sibling's rows are in none of the refs this checkout can read, and every id is re-derived from the pinned tip at push time (law 11's id clause). **USED: `DEF-3460`** (the ruling that grew this feature says EIGHT groups in its headline and enumerates NINE in its own list — filed BEFORE building on it, and settled by making the code the arbiter: `core/search.GROUP_ORDER` holds nine and a test asserts both the count and the set). **USED: `DEF-3462`** (`check_unwired_props.py` CANNOT guard a prop whose NAME another component also uses — `has_caller()` matches the name across every non-test file and never asks which component receives it, so `PlanWizard.tsx`'s three unrelated `onSearch={…}` have satisfied `AppShell.onSearch` since that wizard shipped; found by red-proving the removal of this lane's own exemption and watching the gate stay GREEN with the wiring deleted). **USED: `DEF-3463`** (AppShell TC-1 red on the branch since `CR-060` T10 added a fifth Finance child and left the count assertion at four — FILED, not fixed: not this lane's, and fixing another lane's test inside a feature commit makes both harder to review). **No `OQ` minted and none needed** — the seven judgment calls this lane met (how many groups may show at once; what the placeholder says now it cannot list nine; whether "View all" needs a results screen; what each group matches on where the signed field list ran out; whether master accounts are their own group; where a row with no detail screen goes; where the rank lives) were decided and written into `02-decision-log.md` with their reasoning rather than put back to the PO (law 13). ⚠ **`DEF-3461` IS NOT THIS LANE'S — A SIBLING TOOK IT OUT OF THIS ACTIVE BLOCK BETWEEN TWO OF THIS LANE'S OWN ALLOCATIONS**, minutes apart, and `file_defect.py` correctly stepped past it to `DEF-3462`. That is `DEF-1787` word for word: the sibling works in its own worktree, its row is in none of the refs this checkout could read at allocation time, and both allocators were right. Recorded rather than reclaimed — the earlier citation keeps the id. `DEF-3464–3479` and `OQ-1440–1449` remain UNUSED and free. | 2026-09-03 | **ACTIVE** |
| `DEF-3420–3439` | **`CR-059` W8 + W11 SCREENS (tasks 48 and 63) — four finished reconciliation backends and two write-off doors that no screen could reach.** `/finance/deposits/statement` (the period tie-out, the line-level explanation, the many-to-one match set and the differences report) and Reject / Put it back on the write-off queue. ⚠ **THE BLOCK OPENS AT 3420, ABOVE EVERY WATERMARK IN THIS FILE, AND IT IS `DEF-1787` SUFFERED RATHER THAN AVOIDED.** `file_defect.py` allocated **`DEF-2367`** and was right about every ref this checkout could read; the `CR-060` finance-screens lane, working in its own worktree, took the identical number and pushed it first — both allocators correct, neither able to see the other. Caught by re-deriving the register FROM THE PINNED TIP at push time, before a single row was committed, and every citation renumbered in the same act: the register row, `apps/payments/writeoffs_api.py`, the backend guard's own function name and the frontend test. **USED: `DEF-3420`** (every write-off refusal read as *"This payment can't be recorded as asked"* because the module raised `payments.record.refused`, a key that RESOLVES — which is why `G32` could not see it). **USED: `DEF-3423`** (this lane's own revert, self-reported: a re-derive script piped through `head` lost its pipe and nine catalogues went out built from a tip two commits older, overwriting ninety values of the `CR-060` C11 rule-34 sweep — repaired within the hour, and caught only by reading the push's numstat as arithmetic). ⚠ **`DEF-3421` WAS SKIPPED BY THE ALLOCATOR AND IS NOT THIS LANE'S** — a sibling branch holds it, and the allocator saw it in a ref this checkout cannot list and stepped past it, which is `DEF-1787`'s clause working. ⚠ **AND COMMIT `cc2fed9f`'s MESSAGE NAMES `DEF-3421` IN ERROR**: the row was written before the id was allocated, and the message is not rewritten — this line is the correction. **No `OQ` and no `BR-` id minted**; the one judgment this lane met — the single subtraction the reconciliation screen does — is written into `02-decision-log.md` rather than put back to the PO (law 13). ⚠ **`DEF-3422` COLLIDED TOO AND THIS LANE MOVED RATHER THAN THE OTHER ROW.** A sibling pushed a Product-Owner-reported defect on `DEF-3422` — inside this ACTIVE block — minutes after this lane's row landed on it. `G17` says *renumber the LATER one*, and by row order that is the sibling's; this lane renumbered ITSELF anyway, because editing another lane's row in a register both are appending to is the mechanism law 11 exists to prevent, and a PO-reported row is the last thing to touch on somebody else's behalf. **Commit messages `cc2fed9f` and `c88465ff` name `DEF-3421` and `DEF-3422` respectively; both are wrong and neither is rewritten — this row is the correction.** `DEF-3424–3439` remain UNUSED and free. | 2026-09-02 | **ACTIVE** |
| `DEF-3400–3419` | **The `DEF-2368` lane — the seeded estate's storm-water assessment grew from 54 ERU across 41 premises to 59 across 43 when `CR-062`'s addendum appended two seats, and the two constants stating it did not move.** ⚠ **THE BLOCK OPENS AT 3400 BECAUSE `DEF-3383` WAS TAKEN OUT OF ANOTHER LANE'S ACTIVE BLOCK AND HAD TO BE GIVEN BACK — `DEF-1787` HAPPENING LIVE.** `file_defect.py` resolved the next free id as `DEF-3383` against the working tree, `HEAD` and three `origin` branches, and it was RIGHT about the register: the highest four-digit id anywhere pushed was `DEF-3382`. What it could not see is that the finance lane's `DEF-3380–3399` row — reserving the whole block and saying *"`DEF-3383–3399` remain UNUSED and free"* **inside its own claim** — reached this file while this lane was working. A block listed ACTIVE is not yours even when `max + 1` lands inside it, so the id was renumbered at push time and every citation of it moved in the same commit. **USED: `DEF-3400`** — `storm_water_size_class_for` assesses the municipal depot at `601 Quarry Hill Ct` as `SW-SF`, a single-family home at 1 ERU / `$4.50`, because `government_building` is neither of the two types it names and falls through to the dwelling branch, while `premises_plan` types that same building's unit `commercial` because *"the depot is a non-dwelling building"*. FILED, not fixed: nothing bills wrongly, and moving a demo total inside the commit that fixes a stale demo total would obscure both. `DEF-3401–3419` remain UNUSED and free. **No `OQ` minted** — every judgment this lane met was decided and written into `02-decision-log.md` with its worked figure rather than put back to the PO (law 13). ⚠ **Re-derived from the pinned tip at push time** (law 11's id clause); this lane works in its own `git worktree`, which is exactly the case `DEF-1787` describes, and this row is what that clause looks like when it fires. | 2026-09-02 | **ACTIVE** |
| `DEF-3380–3399` | **`CR-060` T6c / T6d — the accounting export stops sending a settled supplier cost twice, and the supplier register gains a tie-out row against the books.** ⚠ **OPENED AT 3360 AFTER A REAL COLLISION, NOT AS A PRECAUTION.** `file_defect.py` allocated `DEF-3343`, `DEF-3344` and `DEF-3346` by `max + 1` and **all three landed inside `DEF-3340–3359`, which the row above lists ACTIVE** for the `CR-058`/`CR-064`/`CR-065` reconciliation lane. Two of them then collided outright: that lane pushed its own `DEF-3343` and `DEF-3344` first, and the merge showed both numbers carrying two unrelated defects. This file's own rule is the one that decided it — *"A block listed ACTIVE is not yours, even if the register's max + 1 lands inside it"* — so all three rows and their **24 citations across 14 files** were renumbered at push time (law 11's id clause). **USED: `DEF-3380`** (a settled supplier cost leaves in the accounting export twice — the books carry it and the register section sums it again), **`DEF-3381`** (US-LED-016 TC-6 cannot run on PostgreSQL: its simulated posting bypass is refused by the append-only trigger, so the drift release-blocker is proved only on SQLite), **`DEF-3382`** (two finance read docstrings still say the premises dimension is never stamped, six weeks after it landed). `DEF-3383–3399` remain UNUSED and free. **No `OQ` minted** — every judgment this lane met was decided and written into the decision log rather than put back to the PO (law 13). | 2026-09-02 | **ACTIVE** |
| `DEF-3340–3359` · `OQ-1400–1409` | **The `CR-058` / `CR-064` / `CR-065` reconciliation lane — read every task row of those three CRs against the CODE, tick what is genuinely built with the evidence seen, and build what is left (PO 2026-09-02: status *"based on actual code"*, not from the register's ticks).** ⚠ **THE BLOCK OPENS AT 3340 / 1400, ABOVE EVERY WATERMARK IN THIS FILE.** `file_defect.py` would have stepped DOWN into `DEF-3300–3319` (`CR-065`) or `DEF-3280–3299` (`CR-064`) — both **ACTIVE**, and this file's own `DEF-2960` lesson is that a live block may not be sub-let even when its prose releases the tail. **USED: `DEF-3340`** (the sign-up screen's hand-typed step list is seventeen while the seeder walks eighteen — the Municipal discount step is absent from the first frame, carries no label in any of the eleven catalogues, and three tests were sitting RED on the branch tip), **`DEF-3341`** (three comments still name `uoms` as the only service-scoped list after `CR-065` added a second), **`DEF-3342`** (eleven of `CR-058`'s task rows appear twice, once with their statuses and once blank). **No `OQ` minted** — every judgment this lane met was decided and written down rather than put back to the PO (law 13). ⚠ **`DEF-3343`, `DEF-3344` AND `DEF-3345` WERE TAKEN OUT OF THIS BLOCK BY A SIBLING LANE AND THE ROW SAID THEY WERE FREE — corrected here rather than left standing.** `file_defect.py` computes `max + 1` against the PUSHED world plus its own checkout, so the `CR-062`/`CR-063` reconciliation lane, working in its own worktree, allocated three ids inside a block this file already listed **ACTIVE**. That is `DEF-1787`'s mechanism and both allocators were correct. A THIRD lane then hit the same block minutes later, found two of its numbers already carrying unrelated defects, and renumbered **24 citations across 14 files** out to `DEF-3360–3379` on this file's own rule — *"a block listed ACTIVE is not yours, even if the register's max + 1 lands inside it"*. **The three taken ids stay with the sibling** (the earlier citation keeps it); this lane used only `DEF-3340`, `DEF-3341` and `DEF-3342`. `DEF-3346–3359` and `OQ-1400–1409` remain UNUSED and free. ⚠ **Re-derived from the pinned tip at push time** (law 11's id clause). | 2026-09-02 | **ACTIVE** |
| `DEF-3320–3339` · `OQ-1390–1399` · migration `audit 0006` | **`CR-067` backend half (tasks A1–A5) — a runtime failure becomes reproducible: the permanent audit row keeps a short reference, the technical detail lives beside it in `error_diagnostics` and expires (PO 2026-09-02: *"many times errors will happen run time and it is very difficult to reproduce those error"*).** ⚠ **THE BLOCK OPENS AT 3320 / 1390 BECAUSE `CR-067`'s OWN TEXT MINTED `OQ-1344`, AND THAT ID IS INSIDE ANOTHER LANE'S ACTIVE BLOCK** (`DEF-3200–3219` · `OQ-1340–1349`, the payments correct-reference lane). Taking it would be the sub-letting `DEF-2960` cost us once and that `CR-064` and `CR-065` both stepped around four rows above, for the same reason on the same day. **The citation is CORRECTED in `11-change-requests.md` in the same commit**, in §4 and in task A5's row, so no reader is sent to another lane's question. **USED: `OQ-1390`** (is 90 days right, and does a diagnostic fall under the audit log's retention regime or its own — MINTED, not answered) and **`DEF-3320`** (the sample estate has EIGHTEEN blocks and five sentences in `sample_data.py` still say SEVENTEEN, the sign-up screen's own narration among them — FILED, not fixed: it is `CR-064`'s surface and the `CR-062` J2/J3 lane's insertion). ⚠ **`DEF-3320` WAS FOUND BY PRINTING A REAL RECORD, NOT BY READING** — this lane dumped the diagnostic for the step-8 storage failure and it read `step 8 of 18`, against a docstring one function away that says *"THE LENGTH IS ALWAYS SEVENTEEN AND THAT IS THE POINT"*. Every test asserts `len(SAMPLE_MODULES)`, so nothing was ever going to go red. ⚠ **AMENDED 2026-09-02 BY THE `CR-067` FRONTEND HALF (tasks B1/B2/B3), WHICH TOOK TWO MORE OUT OF THIS SAME BLOCK.** **USED: `DEF-3321`** (`error_diagnostics` is written, expires and is READ BY NOTHING — no route in `06-backend` serves it, so task B2's System-Admin technical panel has no data to draw and no boundary to gate on; it is the `data-tracks` id on the drawer's stated absence) and **`DEF-3322`** (`AUDIT_FILTERS` has no outcome filter and `action` matches ONE code exactly, so task B3's *"Errors only"* toolbar control has nothing to drive — the PO said *"Yes this is required"* and the filter it needs is the server's). `DEF-3323–3339` and `OQ-1391–1399` remain UNUSED and free. **Migration `audit 0006` is claimed so no sibling takes the number** — `DEF-2872`'s two-leaf-nodes failure is the one whose collision breaks every test in the process rather than muddling a register. ⚠ **Re-derived from the pinned tip at push time** (law 11's id clause); this lane works in its own `git worktree`, which is exactly the case `DEF-1787` describes. | 2026-09-02 | **ACTIVE** |
| `DEF-3300–3319` · `OQ-1380–1389` · migrations `tenancy 0034–0035` | **`CR-065` — a size class names the utility service it belongs to, so the Fire rate schedule stops offering *Electric CT-metered* (PO 2026-09-02: *"This is where we are setting rates for fire  you should show only capacity for fire . in Setting a capacity needs to tags to utility services ."*).** ⚠ **THE BLOCK OPENS AT 3300 / 1380 BECAUSE `CR-065`'s OWN TEXT CITED `OQ-1342`, AND THAT ID IS INSIDE ANOTHER LANE'S ACTIVE BLOCK** (`OQ-1340–1349`, the payments correct-reference lane). Taking it would be the sub-letting `DEF-2960` already cost us once and that `CR-064` avoided four rows above by doing exactly this. **The citation is CORRECTED in `11-change-requests.md` in the same commit**, so no reader is sent to another lane's question. **USED: `OQ-1380`** (may one size class belong to MORE than one service — a 2" line is both a water size and a fire size — MINTED, not answered) and **`DEF-3300`** (AST-05's connection-size picker still offers every service's sizes, and its comment cited the rule this CR supersedes). `DEF-3301–3319` and `OQ-1381–1389` remain UNUSED and free. ⚠ **Re-derived from the pinned tip at push time** (law 11's id clause). | 2026-09-02 | **ACTIVE** |
| `DEF-3280–3299` · `OQ-1370–1379` | **`CR-064` — the seeding screen names all seventeen steps, ticks them off one by one and prints the reason on the step that broke (PO 2026-09-02: *"list down all 17 steps and show 1 by 1 when they finish … you ahve to provide specific error on the screen itself"*).** ⚠ **THE BLOCK OPENS AT 3280 / 1370, ABOVE EVERY WATERMARK IN THIS FILE, AND IT IS A RENUMBER RATHER THAN AN ALLOCATION.** `CR-064`'s own text was written naming **`DEF-3221`** for the dropped-`checkpoint` defect and **`OQ-1341`** for the reload question. `DEF-3221` WAS ALREADY TAKEN — it is the red-tip lane's billing refusal row, filed the same day — and `OQ-1341` sits inside `DEF-3200–3219` · `OQ-1340–1349`, which is **ACTIVE** and another lane's; this file's own `DEF-2960` lesson is that sub-letting a live block does not work. That is `DEF-1787` exactly: two correct allocators, neither able to see the other. Both citations are CORRECTED in `11-change-requests.md` in the same commit as this row, so no reader is sent to the wrong defect. **USED: `DEF-3280`** (the plant job records which step it is on and `job_poll` drops it — CR-064 task A2, FIXED in the same lane) and **`OQ-1370`** (may the signup route rebuild the step list from `sample_data_runs` when the operator reloads mid-plant — MINTED, not answered). `DEF-3281–3299` and `OQ-1371–1379` remain UNUSED and free. ⚠ **Re-derived from the pinned tip at push time** (law 11's id clause). | 2026-09-02 | **ACTIVE** |
| `DEF-3240–3259` · `OQ-1350–1359` · `BR-\<MOD\>-1180–1199` · migration `ledger 0012` | **`CR-060` T6 / T6a — A SUPPLIER COST POSTS `DR cost / CR cash` WHEN A CLERK RECORDS IT WAS SETTLED (PO ruling 2026-09-02).** `supplier_invoices.paid_on`, the `PATCH /finance/cost-of-service/{id}` route that sets it, and the posting through `apps/ledger/posting.py`. The block opens at 3200 / 1340 / 1180 rather than at `max + 1` (`DEF-3158`) because `DEF-3180–3199` · `OQ-1330–1339` · `BR-\<MOD\>-1160–1179` is held by the `BR-MET-1160` upload-unit lane, opened the same day and **ACTIVE**; this lane steps clear of it rather than racing for the next number. **USED: `OQ-1350`** (what happens to a settlement when its purchase is later corrected or voided — MINTED, not answered) and **`DEF-3240`** (the register's unsigned-cost-code assertion had been red since `CR-060` T5 landed on 2026-09-01 and nothing said so) and **`DEF-3241`** (`PATCH /finance/cost-of-service/{id}` never forwarded `premises_id`, so T4's editable building was unreachable from the API — filed, NOT fixed, because it belongs to T4's row) and **`DEF-3242`** (`chart.py`'s docstring still says `PENDING_FINANCE_RE_SIGN_COST` *"is still `()`"* and it has held fourteen codes since T5). **NO `BR-` id minted:** `BR-LED-028` is AMENDED in place with its supersedes chain, which is what the change process asks for when a reading of an existing rule moves rather than a new rule arriving. **`DEF-3244–3259`, `OQ-1351–1359` and `BR-\<MOD\>-1180–1199` remain UNUSED and free.** ⚠ **Re-derived from the pinned tip at push time** (law 11's id clause) — this lane works in its own `git worktree`, which is exactly the case `DEF-1787` describes: a sibling's rows are in none of the refs this checkout can see. ⚠ **AND THE COLLISION THIS CLAUSE WARNS ABOUT ACTUALLY HAPPENED, WHICH IS WHY THE BLOCK MOVED FROM `DEF-3200–3219` · `OQ-1340–1349` TO THE NUMBERS ABOVE.** Those were free in this lane's worktree and free in every ref it could see; by push time a sibling had reserved the identical block and pushed rows on `DEF-3200`, `DEF-3201` and `DEF-3202` and a question on `OQ-1340` — `DEF-1787` word for word, and both lanes' `max + 1` was correct. Caught by re-reading the register FROM THE PINNED TIP before writing a single row, which is the only thing that could have caught it: four rows and five code citations were renumbered before anything was pushed. | 2026-09-02 | **ACTIVE** |
| `DEF-3200–3219` · `OQ-1340–1349` · migration `payments 0014` | **The two PO rulings of 2026-09-02, built: the reconciliation statement becomes FACTUAL (`OQ-1310`, task 43) and a payment's reference, memo and tender may be amended in place (`OQ-1322` option a, task 41).** ⚠ **RENUMBERED AT PUSH TIME FROM `DEF-3180–3199` · `OQ-1330–1339`, WHICH IS `DEF-1787` HAPPENING AND BEING CAUGHT.** This lane worked in its own worktree and reserved that block against everything it could see — its tree, its HEAD and every `origin` ref — and while it worked, the `BR-MET-1160` upload-unit lane pushed **the same block**, having computed the same `max + 1` from the same evidence for the same correct reason. Nothing downstream would have caught it: two `OQ-1330`s in a register read as a register. The re-derivation at push time is what found it, so the block moved up and every citation moved with it, in code, in tests and in all six registers, before anything was pushed. **USED: `DEF-3200`** (the reconciliation statement's outstanding-cheque count and amount came off different sets, so a cheque issued after the period end raised the count and not the money; FIXED in the same commit), **`OQ-1340`** (is a correction's audit row exempt from retention pruning? MINTED, not answered — the PO accepted that the old cheque number then lives only in the audit trail, and whether that row survives pruning was never put to them). ⚠ **`DEF-3201` WENT TO A SIBLING** — the `DEF-3108` unit-gate lane filed a CRITICAL row there minutes after this block was pushed, almost certainly having allocated before the reservation reached the remote. This file's own rule applies: the lane that filed it keeps it. **USED 2026-09-02 by the task-42 screen lane, which is the same lane returning for CS-34's other half:** **`DEF-3203`** (the correction door's refusal key was in no catalogue, so every refusal on that path rendered as SILENCE — FIXED), **`DEF-3204`** (the route's docstring still names a stub deleted the same day — FILED), **`DEF-3205`** (`collections_schedule.py` reads the wall clock in a money path and G6 has been red for it since CS-10 landed — FILED, not this lane's to fix), **`DEF-3206`** (the door resolves a tender id that no read served a screen, so the tender third of the ruling was unreachable — FIXED) and **`DEF-3207`** (recording one credit blanks the day's takings figure for the whole payments list — FILED, and it is CS-35 task 23's to fix). **`DEF-3208` and `DEF-3209` were taken the same day by the same lane, returning for CS-35 task 23** — `DEF-3208` is `CR-061`'s chart gaining `4730 Customer credit` while CS-35's own credit-posting test still asserts `6900`, so the payments suite is red at the tip and neither lane could see the other (FILED, not fixed: which account a goodwill credit is filed under is `CR-061`'s designation); **`DEF-3209` is this lane's OWN revert-by-subtraction** over the `CR-060` settlement lane in `endpoints.ts`, self-reported and repaired within the hour, and it is `DEF-1706` word for word — the tip was pinned correctly and the BLOB was forty minutes old. **`DEF-3210–3219` and `OQ-1341–1349` remain UNUSED and free.** ⚠ **Every one of these five was re-derived from the pinned tip at push time and all five were still free** — which is not luck: the first push attempt was REFUSED because thirteen named paths had moved under this lane while it worked, and the re-derivation that followed re-read the register from the tip before a row was written. That is law 11's id clause doing the job it exists for. Migration `payments 0014` is claimed so no sibling takes the number. | 2026-09-02 | **ACTIVE** |
| `DEF-3180–3199` · `OQ-1330–1339` · `BR-\<MOD\>-1160–1179` | **`BR-MET-1160` — a reading whose unit the tariff cannot price is refused WHEN IT IS UPLOADED, on the screen a clerk is standing at (PO ruling 2026-09-02).** The block opens at 3180 / 1330 / 1160 rather than at `max + 1` because `DEF-3150–3179` · `OQ-1320–1329` · `BR-<MOD>-1140–1159` is held by the `CR-059` W10 collections-schedule lane, opened the same day and **ACTIVE**; this lane steps clear of it rather than racing for the next number. **USED: `BR-MET-1160`** (the rule) and **`OQ-1330`** (`BR-MET-136` makes this a switchable judgment rule — should it join the seven locked integrity rules instead? Raised rather than closed, the posture `RULE_GENERATION_CHANNEL` takes for `OQ-417`). **NO DEF MINTED, and that is the honest state for a lane implementing a ruling rather than fixing a fault** — what the product did before today was not a defect, it was a check nobody had asked for. ⚠ **The `BR-` id was RENUMBERED before a single citation was pushed:** the rule was drafted as `BR-MET-144` on the assumption that the metering namespace was still in the low hundreds, and `BR-MET-144` has been the quantity-display rule since 2026-08-27 (PO, closing `DEF-894`). CLAUDE.md's own warning about `BR-` being *"37 ids from the same cliff"* is what prompted the check; the grep took one command and the collision would have put a money-path citation on the wrong rule. **`DEF-3180–3199`, `OQ-1331–1339` and `BR-<MOD>-1161–1179` remain UNUSED and free.** ⚠ **This lane touches NO migration** — the rule adds no column; the pricing unit is derived per read and stored nowhere. ⚠ **Re-derived from the pinned tip at push time** (law 11's id clause). | 2026-09-02 | **ACTIVE** |
| `DEF-3150–3179` · `OQ-1320–1329` · `BR-\<MOD\>-1140–1159` | **`CR-059` W10 — the collection ladder runs on a SCHEDULE, on each utility's own business day (task 54, CS-10), and the first bill's deposit line is proved satisfied on the ISSUED bill (task 13, CS-19).** The block opens at 3150 rather than at `max + 1` for the reason the `DEF-3120` section gives: the `CR-059` W11 write-off lane holds `DEF-3120–3149`, and several sibling lanes are in `apps/payments` in their own worktrees, where `DEF-1787`'s mechanism makes each invisible to the others. **USED: `DEF-3150`** (one step per account per PASS is not one per DAY — four passes on one date walk a two-months-overdue account from the reminder to the ~$8.00 certified final; FIXED), **`DEF-3151`** (`BR-PAY-016`'s partial-payment pause has never fired because no caller supplies `recent_payments`; FILED, blocked on `OQ-1320`), **`DEF-3152`** (`credit.deposit_payments_for_account` said *"NOTHING CALLS IT"* while billing had called it through the seam since 2026-08-15 — the sentence `CR-059` CS-19 was written from; FIXED), **`DEF-3153`** (`billing/api.py` says a cycle-less one-time run cannot issue and cites `OQ-241` as open; it was CLOSED 2026-08-23 and built; FIXED), **`DEF-3155`** (⚠ **PRE-EXISTING AND MEASURED, NOT THIS LANE'S**: `tests/test_us_bil_010_first_bill.py` is **10 failed / 1 passed at the pinned tip `99c0d4fb`**, on a detached worktree with none of this lane's files present — `CR-057` defaulted `SBH_BILLING_RESOLUTION_STEPS` to `R3,R4` on 2026-09-01 and `a_priced_plan` writes no `rate_size_rows` row, so R3 refuses *"connection size 'E-1P-100' has no row on the rate schedule version"* for every case that builds a bill. `DEF-2799`'s exact shape one fixture over); **`DEF-3154`** (S34's *"Nothing runs the collection sequence overnight"* in eleven locales becomes false where the schedule is live — backend half done, the panel is task 55's; FILED); **`OQ-1320`** (over what window does a partial payment count?) and **`OQ-1321`** (where does the record of a collections RUN live?). ⚠ **NO MIGRATION IS ALLOCATED TO THIS LANE** — the two new S70 settings live in the existing `tenant_settings.collections` document, which `settings_families.merge` fills from the ratified default for any tenant whose stored document predates them, so no column, no backfill and no migration number is taken and this lane adds no second leaf. **`DEF-3157`** (⚠ **PRE-EXISTING AND MEASURED, NOT THIS LANE'S**: `tests/test_oq366_ladder_follows_the_master.py` TC-2 and TC-3 are red at the pinned tip — **2 failed / 3 passed, identical on a detached worktree with none of this lane's files present** — because commit `6c722aeb` (2026-09-01) required an identity kind on account creation and their fixture builds one without, so both fail in SETUP before any ladder assertion. Same shape and same day as `DEF-3155`, different cause). ⚠ **`DEF-3156` WENT TO A SIBLING** — the `DEF-2396` service-estate lane filed it inside this block while this lane was allocating; `file_defect.py` fetched, saw it and stepped to 3157, which is the allocator working. This file's own rule applies: the earlier lane keeps it. **`DEF-3158–3179`, `OQ-1322–1329` and `BR-\<MOD\>-1140–1159` are UNUSED and free.** | 2026-09-02 | **ACTIVE** |
| `DEF-3110–3119` · `OQ-1310–1319` · `BR-PAY-1090–1099` · migrations `payments 0012–0013` | **`CR-059` W8 — reconciliation (tasks 43–46): the statement balances and the period read, a resolution that hangs off a LINE, the match SET, and the difference-reason list.** ⚠ **EVERY ONE OF THESE BLOCKS IS THIS LANE'S SECOND CHOICE, AND THE FIRST CHOICE WAS WRONG IN THREE DIFFERENT WAYS — `DEF-1787`'s mechanism, four times over, in one push.** The lane worked from tip `7d95b1d2` and re-derived at push time against `c2265c0e`; between the two, a sibling pushed 68 files, and: **(1)** `OQ-1254` was correct at `max + 1` and sits inside `OQ-1252–1259`, which `CR-058` W3+W4 holds — the register's own max had moved to **1300** and every block through **1309** was spoken for, so this lane opens at **1310**; **(2)** `BR-PAY-1080–1083` sits inside `BR-<MOD>-1070–1089`, reserved, so the block moves to **1090–1099**, which is the gap between that block and `BR-<MOD>-1120–1139`; **(3)** the four defect ids were re-filed through `file_defect.py` **TWICE** — the tip moved again between this lane's two pushes, so the first re-derivation returned `3117 / 3116 / 3115 / 3114` and the second returned **`3113 / 3112 / 3111 / 3110`**, which is what every citation now names. The allocator steps DOWN through reserved blocks, so the ORDER of filing is what reproduces them, and **one re-derivation was not enough**: a push that takes twenty minutes is a window in which the register moves again; and **(4) the worst one, because nothing in law 11 catches it: the MIGRATION NUMBER.** This lane authored `payments 0011` + `0012` and the sibling pushed `payments/0011_cr059_cs25_write_off_states.py` — two leaf nodes in one migration graph, which is `DEF-2872`'s symptom: Django refuses **every test in the process** with *"Conflicting migrations detected"*, names neither lane, and looks like a broken tree. Renumbered to **0012 / 0013**, with the dependency, both docstrings and the register prose moved with the files. **USED: `DEF-3110`** (the difference-reason list has no S8 card), **`DEF-3111`** (Unreconcile reverses the cash and the PO ruled on 2026-08-12 that it does not — `OQ-163`, CLOSED the other way, code unmoved since), **`DEF-3112`** (eleven locale strings tell a clerk a combined bank credit can never be matched, on the page that now matches it), **`DEF-3113`** (the engine told every screen it had no screen and no endpoint, for sixteen days); **`OQ-1310`** (does a reconciliation statement ADD deposits in transit to the bank's closing balance or SUBTRACT them — CS-14 says subtract, a textbook says add, and the gap on CS-14's own figures is **2,244.56**); **`BR-PAY-1090`–`BR-PAY-1093`**, one per spec. **`DEF-3109`** is USED too and sits BELOW this block, not inside it — a fifth defect was filed after the first push (the bank-line panel still says an unmatched line is *counted and left alone* after CS-16 made it explainable) and `file_defect.py` steps DOWN through reserved blocks, so it landed at 3109 rather than at 3114. Recorded here because a reader checking whether 3109 is free would otherwise find it in no block at all. `DEF-3114–3119`, `OQ-1311–1319` and `BR-PAY-1094–1099` remain UNUSED and free. **The lesson worth carrying, and it is the one this file was written for:** re-deriving ids from the tip is necessary and is not sufficient — **a migration number is an id too**, and it is the only one whose collision breaks the whole suite rather than muddling a register. | CR-059 W8 reconciliation lane, 2026-09-01 | ACTIVE |
| `OQ-1290–1299` | **`DEF-2397` — rating's sample data becomes SERVICE-SHAPED.** A tenant that sells electric, gas or storm water received a complete metered estate (70 premises, 118 units, 75 service points, 70 meters, 193 reads) and then **zero bills**, because `apps/rating/sample_data` still guarded every rate schedule on the literals `water`, `sewer` and `trash` after CR-039 wave A made metering and assets service-shaped. Touches `06-backend/core/sample_fixture.py`, `apps/rating/sample_data.py`, `apps/rating/seams.py`, `tests/test_def2397_service_shaped_rating.py` (new), `tests/test_service_billing_coverage.py`, `tests/test_us_ten_019_sample_records.py` and `tests/test_def2799_seeded_size_axis.py`. **No migration and no new DEF or BR id is taken** — the defect row already exists and no business rule changes. **USED: `OQ-1290`** (what does a demo electric, gas or storm-water tenant charge for USAGE? — the BASE is signed and seeded, the usage line is a stored `$0.00` that names this question at the line the figure sits on). ⚠ **A BLOCK IS TAKEN FOR ONE ID ON PURPOSE.** The register's own `max + 1` lands at `OQ-1254` and this lane is in a private `git worktree`, so `file_defect.py` cannot see it and a sibling computing `max + 1` would correctly get the same number — `DEF-1787` exactly, which happened twice on 2026-08-27 and once more on 2026-09-01 to the CR-059 W3 lane above. Claiming above every ACTIVE block costs nine unused numbers and a gap in the numbers is legitimate; a collision is not. | 2026-09-01 | **ACTIVE** |
| `DEF-3060–3079` · `OQ-1280–1284` | **`CR-061` — THE CONTRA-REVENUE ACCOUNT TYPE (PO ruling 2026-09-01, *"no, you cannot file discount under revenue"*).** `LEDGER_ACCOUNT_TYPES` gains a sixth value and the discount account moves from `4300` typed `revenue` to **`4760` typed `contra_revenue`**. Touches `06-backend/apps/ledger/models.py`, `chart.py` and `reporting.py` (all three 🔒 human-owned), one new test file and four existing ones, plus the frontend chart fixture. **No migration is taken and none is needed** — the type vocabulary is validated in Python and by no database `CHECK` in any `ledger/migrations/*`, verified file by file rather than assumed. **USED: `DEF-3060`** (a correction to a seeded chart account can never reach a tenant that already exists — the seed skips the code and no door accepts a change of type; **filed, deliberately NOT fixed**, because whether it MAY be fixed is `OQ-1280`), **`DEF-3061`** (the S56 type picker shows the raw value `contra_revenue` until `finance.gl.type.contra_revenue` lands in the eleven catalogues — this lane was instructed not to edit them, so the key is reported rather than added) and **`OQ-1280`** (does a database that already holds `4300 … revenue` get a migration, or stay wrong?). **No `BR-` block taken and none needed** — this executes a PO ruling against an EXISTING rule (`BR-LED-790`, now SUPERSEDED IN PART) rather than minting one. **A SMALL BLOCK ON PURPOSE:** this lane needed three ids and took twenty, so an id handed out by stepping down into a gap cannot land inside it. `DEF-3062–3079` and `OQ-1281–1284` are UNUSED and return to the pool. | 2026-09-01 | **ACTIVE** |
| `DEF-3030–3059` · `OQ-1270–1279` · `BR-\<MOD\>-1070–1089` | **CR-059 WAVE W3 — THE DOORS, BACKEND: tasks 15 (CS-5) and 17 (CS-6).** `POST /payments/{id}/reverse` and the three missing refund routes (raise · issue · clear), each Admin-gated **in the SERVICE** and not only on the route — which is what both specs actually ask for, and is why this lane edits two files on `human_owned.txt` (`apps/payments/reversal.py`, `apps/payments/refunds.py`) rather than only adding routes. Touches `06-backend/apps/payments/reversal_api.py` (new), `refunds_api.py`, `selectors.py`, `config/urls.py`, `openapi/schema.json`, six existing test files and two new ones. **No migration is taken and none is needed** — CS-5's own spec says *"Data. None. Every column, index and trigger this needs already exists"*, and CS-6's schema change is CS-7's (task 60, contracts). **USED: `DEF-3030`** (S33 tells a clerk in eleven languages that reversing a payment and issuing a refund are unbuilt, and that two questions the PO ruled three weeks ago are still open — filed, NOT fixed, because tasks 16 and 18 own the copy) and **`DEF-3031`** (the step that pays a customer's money out had no check at all on who was doing it — fixed here). **`BR-PAY-1070`** (reversing a payment is Admin-only, gate on the service) and **`BR-PAY-1071`** (issuing a refund is Admin-only, clearing is Admin or Executive, both on the service). ⚠ **THIS BLOCK IS THE SECOND ONE THIS LANE TOOK, AND THE FIRST WAS `DEF-1787` HAPPENING LIVE.** It first claimed `DEF-3000–3029` · `OQ-1260–1269` · `BR-\<MOD\>-1050–1069` and the **CR-060 T2/T3/T4 lane claimed the identical block and pushed it first** (`a8a50b66`). Both allocations were correct at the time and neither lane could see the other: `file_defect.py` reads the working tree, `HEAD` and the `refs/remotes/origin` refs — the PUSHED world plus its own checkout — and both lanes were in private worktrees. **All 37 citations were renumbered together** across the code, the tests, the rules, the gate baseline, the CR, the decision log and the review ledger, because a half-renamed id is worse than the collision. It was caught by re-deriving the ids against the PINNED TIP at push time, which is the check law 11 prescribes for exactly this. | 2026-09-01 | **ACTIVE** |
| `DEF-3000–3029` · `OQ-1260–1269` · `BR-\<MOD\>-1050–1069` · migrations `tenancy 0029` and `ledger 0011` | **`CR-060` TASKS T2 → T3 → T4 — the organisation type, the sub-metering fixture, and per-building recovery.** T2 puts `organisation_type` on `tenant_settings` (`tenancy/0029`) with the three values the PO named in `BR-LED-028`; T3 builds the sub-metering pytest fixture `CR-060` §11 says blocks C8 and C9; T4 puts `premises_id` on `supplier_invoices` (`ledger/0011`) and adds `group_by=premises` to the bought-versus-billed report. **USED: `BR-TEN-1050`** (a tenant declares what kind of organisation it is). **No `DEF-` and no `OQ-` minted** — every question these three tasks raised was answerable from the code or from `CR-060`'s own text, and a lane that can read does not ask (law 13). ⚠ **`BR-TEN-813` WAS ALLOCATED FIRST AND RENUMBERED BEFORE THE PUSH — `DEF-1787`'s hazard, caught by the check that law prescribes.** `max + 1` across the registers correctly gave 813, and 813 sits inside `BR-\<MOD\>-810–829`, which the `DEF-2310`/`DEF-2311` service-declaration lane holds ACTIVE. All eight citations were renamed together across the model, the migration, the two services files and the test — a half-renamed id is worse than the collision. **The migration numbers are reserved here for the same reason** (`DEF-892`: a migration number is ALLOCATED to a lane, never taken from the watermark). | 2026-09-01 | **ACTIVE** |
| `DEF-2805–2817` · `OQ-1240–1249` · `BR-\<MOD\>-1030–1049` | **CR-051 TASK 30's MISSING HALF (the worker time limit) AND CR-053 TASK 14's MECHANISM (the named-format registry).** Task 30 shipped an account ceiling and NO task time limit, so a hung bill run held one of the two worker slots for ever, and the CR's own count read *30 done* over its own prose saying otherwise (`DEF-2829`). Task 14 was deliberately not built because `OQ-1167` — the vendor's file format — is a fact only they hold; that stays true and only the MECHANISM is built, with the one field list this repo has already ratified (`BR-NOT-029`'s fourteen manifest columns). Touches `06-backend/config/settings/base.py`, `06-backend/core/jobs.py`, `06-backend/apps/billing/print_formats.py` (new), `print_set.py`, `print_api.py` and `runs.py`. ⚠ **A SMALL AND ODDLY-SHAPED BLOCK ON PURPOSE:** `file_defect.py` stepped DOWN past two reserved blocks into this gap before the row existed, so the block is drawn to CONTAIN what it handed out. **USED: `DEF-2805`** (a job killed by the HARD task time limit is left `running` for ever and cannot be resumed — filed, deliberately NOT fixed) and **`DEF-2806`** (two billing ceilings said they were deployment overrides and no settings module declared either name — fixed). ⚠ **BOTH IDS WERE RE-DERIVED AT PUSH TIME AND ONE OF THEM MOVED** (`DEF-1787`): the first allocation gave `2817` and `2805`; replaying the allocator against the PINNED TIP gave `2805` and `2806`. **All 22 citations were renumbered together** — the settings file, the rule, the CR, the decision log, the review ledger, the tests and the proof script — because a half-renamed id is worse than the collision. | 2026-09-01 | **ACTIVE** |
| `DEF-2820–2839` · `OQ-1220–1229` | **THE ID GRAMMAR READS FIVE DIGITS (`DEF-2804`, PO ruling 2026-08-31 — *"next question make them 5 digital"*).** Every three-digit id pattern in `10-scripts/` widened to `\d{3,5}`: `gates/common.py` (4 places), `g01`, `g08`, `g10`, `g12`, `g17`, `g51`, `02-trace_lint.py`, `07-e2e-wiring-index.py`, `module_report.py`, `screen_report.py`, the two `render-checks/*.mjs`, plus `07-frontend/src/features/audit/auditEvents.tsx` and one frontend test. ⚠ **NOTHING IS RENUMBERED AND NOTHING IS ZERO-PADDED** — `OQ-291` stays `OQ-291`. Padding would move every citation in every register, docstring and test at once, which is the mass shared-file rewrite law 11 exists to prevent; if it is wanted it is a separate change with its own measured blast radius. A SMALL BLOCK ON PURPOSE: this lane expected to need two or three ids for the register rows the widening makes visible, and needed exactly two. | 2026-08-31 | **RELEASED 2026-08-31** — used **`DEF-2820`** (OQ-1166 cited from a 🔒 rating-math file and read as `OQ-116` for two days; it has a register SECTION and no register ROW) and **`DEF-2821`** (`RULE_ID_SHAPED` named four id vocabularies and implemented three, so it never matched an `EP-` id). **No `OQ-` and no `BR-` minted:** every question this lane met was already ruled — the width by the PO on 2026-08-31, and `OQ-1166` on 2026-08-30 — so there was nothing to ask. `DEF-2822–2839` and `OQ-1220–1229` are UNUSED and return to the pool. |
| `DEF-2790–2799` | **THE `G53` WIDENING — the `OQ-441` ruling's condition, actually tested.** The PO ruled on 2026-08-30 (*"FIX THE CAUSE, NOT THE FIFTH INSTANCE"*) that a file carrying `HUMAN-REVIEW-PENDING` **and a review-ledger row** must be matched by a glob in `10-scripts/gates/human_owned.txt`, and that the five files the ruling names go in as the cause fix's first act. `G53` keyed on `HUMAN-OWNED` instead, so **two of those five — `apps/billing/gather.py` and `apps/billing/metering_seam.py` — were invisible to it**, and the "first act" was never carried out at all. Widening to either marker takes the finding set from **57 files to 62**. Touches `10-scripts/gates/g53_guard_list_coverage.py`, the new `g53_selftest.py`, `g53_unguarded_baseline.txt`, and one exclusion line each in `run_gates.py` and `g42_gate_entrypoints.py`. ⚠ **NOT `human_owned.txt`** — adding a file to that list is a process event and the PO's call, and a lane that widens a check and then quietly satisfies it has committed the same failure one layer up. The whole 62-file backlog is put to the PO as ONE question in `12-governance/09-human-review-ledger.md`. ⚠ **A SMALL BLOCK ON PURPOSE:** this lane needs two ids, and `file_defect.py` stepped DOWN into the `DEF-2580–2609` lane's gap and offered `DEF-2594` — the "row filed outside its lane's own reservation" this table exists to stop. **USED: `DEF-2790`**, and **`DEF-2791`** after the PO answered the same day and the lane continued into executing the ruling. ⚠ THIS ROW WAS MARKED RELEASED AND RE-OPENED WITHIN THE HOUR — a lane that closes its block before its work is finished has to take an id from somewhere, and the somewhere is another lane's block. Release when the pushing stops, not when the first deliverable lands. `DEF-2792–2799` return to the pool. **`DEF-2790` is CLOSED** (fixed at `23368f19` — the gate widened, the ruling executed, `G53` green); **`DEF-2791` stays OPEN** on purpose: it names seven guarded files that still tell the reader they are unguarded, and its own prevention says the durable fix is a gate rather than a prose sweep, which is a lane of its own. | 2026-08-31 | RELEASED 2026-08-31 |
| `DEF-2760–2789` · `OQ-1210–1219` | **`DEF-2717` FOLLOW-UP — THE RUNTIME RLS GUARD** (`06-backend/core/rls_guard.py`, `config/wsgi.py`, `docker-entrypoint.sh`, `apps/tenancy/apps.py`, `config/settings/base.py` + `local.py`, `10-scripts/gates/g56_rls_runtime_guard.py`). A superuser bypasses row-level security COMPLETELY, `FORCE` included, and nothing observable says so — measured on PostgreSQL 16.13, same table, same policy, same `app.tenant_id`: a `NOSUPERUSER NOBYPASSRLS` role read **2 rows**, a `SUPERUSER` read **3**, the third being the OTHER tenant's. ⚠ **RENUMBERED AT PUSH TIME FROM `DEF-2730–2759`, WHICH THE `CR-054` W4 FRONTEND LANE HAD ALREADY CLAIMED AND PUSHED — `DEF-1787` HAPPENING, CAUGHT BY THE CHECK THAT LAW PRESCRIBES.** `file_defect.py` handed out `DEF-2730` correctly at the time: it reads the working tree, `HEAD` and the `refs/remotes/origin` refs, and the sibling was working in its own worktree with rows in none of them. Re-deriving from the PINNED TIP at push time found `2730`–`2734` all occupied. **USED: `DEF-2760`** (the repo records no database role for any deployment, so nobody can tell whether hard rule 1 is enforced anywhere), **`DEF-2761`** (the Postgres suite fakes the tenant marker, so outside the isolation tier it has never exercised RLS at all — raised by a sibling lane as a possible signup outage and MEASURED not to be one: the real `provision_tenant` provisions a tenant end to end under `rolsuper=f rolbypassrls=f`) and **`DEF-2762`** (this lane's own re-derivation script renamed a SIBLING's changelog entry, because it matched on the version literal alone; caught by law 11's `--numstat` arithmetic and fixed with nothing lost). The same re-derivation found the VERSION taken too — this lane had written `2.98.1` and the tip already read `2.99.0`. | 2026-08-31 | **ACTIVE** |
| `DEF-2700–2729` · `OQ-1190–1199` · `BR-\<MOD\>-960–979` | **CR-051 tasks 11, 21, 22 and 23 — MAKING THE RUN SURVIVE SCALE, BACKEND** (`06-backend/apps/billing/**`). Task 21 measures the bill run at 100, 1,000 and 10,000 accounts on real PostgreSQL and publishes the figures — the CR records that **no timing figure for a bill run of any size exists anywhere in this repo**, and tasks 11, 22 and 23 are sized against what it finds. Task 11 writes the checkpoint a killed worker resumes from; task 22 gives the repeated seams a plural form; task 23 is the invoice-line write. **No migration is taken and none is needed** — the checkpoint lives in the `jobs` record's existing `checkpoint` column and the cache is in memory for the length of one pass. ⚠ **WIDENED 2026-08-31 TO CR-051 TASKS 26–30 (the PO's performance question, widened), same lane, same block.** Used: **`DEF-2717`** (every figure this lane published before midday was measured on a SUPERUSER connection, so row-level security was never evaluated — the whole set was re-measured about a quarter higher), **`DEF-2718`** (a sibling overwrote this lane's shared-scratchpad runner with one pointing at a different worktree and a different database; the helpers now live in a lane-private directory), **`DEF-2719`** (`pathlib.read_text()`'s universal-newline translation stripped 11 carriage returns from the defect register on a one-row append — caught by law 11's `--numstat` arithmetic reading 12 insertions against 11 deletions), **`DEF-2720`** (the new run ceiling's refusal reason travels in `params.detail`, which BR-SHL-020 r2 keeps off the screen, so a clerk sees only *"This billing run can't go ahead as asked."*), **`DEF-2722`** (a freshly provisioned utility gets 70 premises and 270 units and **zero customers and zero accounts** — eight sample-plant blocks fail at signup and nothing reads the failure) and **`DEF-2723`** (the accounts list costs 562 ms for seventy-three accounts on an idle system, where one account's detail costs 44 ms and a whole bill costs 18 ms). **No `OQ-` and no `BR-` minted for tasks 26–30:** every question these tasks raised was answerable by measurement, and a lane that can measure does not ask. | 2026-08-31 | **ACTIVE** |
| `DEF-2700–2729` · `OQ-1190–1199` · `BR-\<MOD\>-960–979` | **CR-052 wave W3/W4/W5 tasks 12–17, BACKEND.** Task 12 the template resolved PER ACCOUNT inside the issue loop (`apps/billing/issue.py`, 🔒) · task 13 the `one_template_pin_for_the_whole_run` notice withdrawn (`apps/billing/api.py`) · task 14 the paperless / SMS election columns and the read `apps/billing/delivery_seam.ELECTION_READ` has named since W3 · task 15 email and SMS rows queued for accounts that elected them, print unconditional · task 16 BR-RAT-036's PER-UNIT tax form (🔒 rating math) · task 17 the two discount types that refuse at set-up, which are BLOCKED at the data layer by `OQ-291` and `OQ-292` and are therefore built UP TO THE BOUNDARY in the chain's own terms (R2 swap, R3b deduction) and stubbed there. Takes ONE migration in `apps/customers` (three columns, all additive, all nullable). | 2026-08-31 | **ACTIVE** |
| `DEF-2730–2759` · `OQ-1200–1209` · `BR-\<MOD\>-980–999` | **CR-054 wave W4, FRONTEND — tasks 2, 15, 17, 23, 24 and 25** (`07-frontend/src/features/metering/**`). ⚠ **THE BLOCK WAS RE-DERIVED FROM THE PINNED TIP AT PUSH TIME AND MOVED UP FROM `DEF-2692–2695` — `DEF-1787`'s mechanism, caught by the check that law prescribes.** The lane's base commit was `7aa11e09`, where the register's high-water mark was `DEF-2673`; by push time siblings had taken `DEF-2700–2711`, and this lane's own CR-054 backend half already holds `DEF-2670–2699`. **All 36 occurrences were renamed together** across the code, the tests and the render check — a half-renamed id is worse than the collision. **USED: `DEF-2730`** (S27 divides READINGS by METERS and draws a full 100 % bar on a cycle BR-MET-057 scores at 83.3 %), **`DEF-2731`** (stage 4 said *"Rows that will become readings: 0"* over a post that filed five, and the receipt called those same five *"left without a decision"*), **`DEF-2732`** (the coverage sentence double-counted and read *"expects 5 … cover 5 … 1 have not been read"*), **`DEF-2733`** (the rejects route's two refusals say *run* and *loaded* to a reads clerk — filed, sidestepped at the control, NOT fixed), **`OQ-1200`** (the server publishes no pre-post split, so the button's number is a browser-side port of `would_hold`) **`OQ-1201`** (two counters both called the cycle's expected meters disagree) and **`DEF-2734`** — filed AFTER the block was first written, and the most serious thing this lane found: **both rejects files come back EMPTY on a database whose role does not bypass RLS**, because `read_batch_results_csv` and `import_results_csv` stream a LAZY generator and `TenantContextMiddleware` clears `app.tenant_id` the moment the view returns. The render check passed on it TWICE an hour earlier, on this same code and this same database, while the role was still superuser — `DEF-2717`'s root cause one route over. Backend, and NOT fixed here. **No migration, no `BR-` id and no rule minted** — every rule this lane implements was already signed (`BR-MET-940`, `BR-MET-941`, `BR-MET-129`, `BR-MET-057`, `B4.4`), which is the honest state for a lane whose whole job was to put signed law on a screen. `DEF-2734–2759`, `OQ-1202–1209` and `BR-\<MOD\>-980–999` are UNUSED and free. | 2026-08-31 | **ACTIVE** |
| `DEF-2670–2699` · `OQ-1180–1189` · `BR-\<MOD\>-940–959` | ⚠ **RENUMBERED AT PUSH TIME FROM `DEF-2640–2669` · `OQ-1170–1179` · `BR-\<MOD\>-930–949`, WHICH THE `CR-052` WAVE-W0 LANE HAD ALREADY CLAIMED — `DEF-1787` HAPPENING, CAUGHT BY THE CHECK THAT LAW PRESCRIBES.** Both lanes read the same registers, both correctly computed the same free block, and neither could see the other: `file_defect.py` reads the working tree, `HEAD` and the `refs/remotes/origin` refs — the PUSHED world plus its own checkout — and the sibling was working in its own worktree. Nothing downstream would have caught it; a duplicate id in a 1,100-row register reads as a register. It was found because the push helper re-reads the reservation table from the PINNED TIP and refuses rather than trusting an id allocated twenty minutes earlier. **All 66 occurrences were renamed together across the registers, the rules, the CR, the code comments, the tests and the OpenAPI snapshot** — a half-renamed id is worse than the collision. **CR-054 waves 2 and 4, BACKEND — tasks 8, 10, 14 and 16** (`06-backend/apps/metering/**`). Task 8 the enabled-services endpoint · task 10 `service_coherence` gains a real comparison · task 14 **partial posting** on a read batch (CR-047's ruling applied to reads; 🔒 touches the post gate the hard-rule-6 idempotency block stands in front of) · task 16 the rejects export on a batch. **No migration is taken and none is needed** — every fact the four tasks store already has a column. | 2026-08-30 | **ACTIVE** |
| `DEF-2700–2729` · `OQ-1190–1199` · `BR-\<MOD\>-960–979` | **`CR-052` task 11 and `CR-053` tasks 6 + 8, FRONTEND** (`07-frontend/src/features/billing/**` — the bill detail and the bill document only). Used **`DEF-2712`** (the client's line-kind union named two kinds no server writes), **`DEF-2713`** (`G44` classified `tax_authority` as money), **`DEF-2714`** (the twelve-month usage block is stamped and served by nobody, which BLOCKS `CR-052` task 9) and **`DEF-2715`** (the document prints the server's engineering prose at a clerk); **`DEF-2716`** (three columns on the bill screens print a raw database id, which `B14` rule 31 forbade on 2026-08-30 — filed after the branch tip brought that rule into `CLAUDE.md` mid-lane; **FIXED 2026-08-31 in `2.100.2`**) and **`DEF-2721`** (this lane's own law-11 push helper staged `find . -type f` over a scratchpad `DEF-2314` already records as shared between two lanes, and built a commit carrying an **816-line revert** of `12-governance/11-change-requests.md`; caught before the push by the verify-by-subtraction step, and the helper now stages the manifest it derived and REFUSES anything else) and **`OQ-1190`** (no subtotal per tax authority exists anywhere, and a remittance return is filed per authority). ⚠ **`file_defect.py` handed out `DEF-2609` for that last row** — it stepped DOWN into a reserved gap rather than up when the block above the maximum was taken. The id was genuinely free, and it was renumbered into this block before the push anyway: a row filed outside its lane's own reservation is how this table stops being true. **No `BR-` id minted** — this lane implements signed rules and states none. ⚠ **`DEF-2700–2711` WERE ALL TAKEN BY THE TIME THIS LANE PUSHED, AND THAT IS `DEF-1787` HAPPENING — CAUGHT BY THE CHECK THAT LAW PRESCRIBES.** `file_defect.py` handed out `2707`..`2710` correctly at the time: it reads the working tree, `HEAD` and the `refs/remotes/origin` refs, and two sibling lanes in their own worktrees had rows in none of them. Re-deriving the ids from the PINNED TIP at push time found all four occupied by the `CR-051` measurement lane and the `CR-052` W0 lane. **All four were renumbered together across the code, the tests, the registers, the CR and the changelog** — a half-renamed id is worse than the collision. The same push found the VERSION taken twice over: this lane had written `2.95.0` and the tip already read `2.97.0`. | 2026-08-31 | **ACTIVE** |
| DEF-2640–2669 · OQ-1170–1179 · BR-\<MOD\>-930–939 | **CR-052 wave W0 tasks 1–3 — `Disconnected` at the cut.** Task 1 is NOT built and the block is opened for the reason it is not: assigning BR-CUS-107's seeded status drops the account out of `customers.selectors.accounts_for_bill_run` and the days it consumed BEFORE the cut are billed by nobody, which is BR-CUS-103 unbuilt by a status write. Used **OQ-1170**; **DEF-2640, DEF-2641, DEF-2642** | 2026-08-30 | **ACTIVE** |
| migration `metering 0043` · `DEF-2454`–`2455` | **CR-054 W1 tasks 4/5/7 — the pre-filled reading sheet.** `read_import_rows.row_key`, one nullable text column, depending on `metering 0042` (the real leaf: 0038 is unclaimed and 0042 is the only child of 0041). `DEF-892`: a migration number is ALLOCATED to a lane, never taken from the watermark — this row is the allocation. **USED: `DEF-2454`** (two `TEMPLATE_COLUMNS` targets both accept the header word `register`, so which fact it supplies depends on what else is in the file), **`DEF-2455`** (this lane edited the SHARED checkout from its own worktree, because two of its edit scripts carried a literal `cd` to the repo root; both files were restored byte-identical to HEAD and nothing was lost). | 2026-08-30 | **RELEASED 2026-08-30** — shipped on `claude/confirm-app-version-310jd3`. |
| DEF-2310–2339 · OQ-1050–1059 · BR-\<MOD\>-710–729 | **`DEF-1813` — NO BILLABLE ASSET COUNT CROSSES THE BILLING SEAM, so every UNMETERED service is unbillable by count.** `BR-RAT-081` (PO 2026-08-20) declares a service unmetered; `BR-RAT-090` bills it as a COUNT OF ITS ASSETS ON THE UNIT — ratified worked figure **3 carts × $15.00 = $45.00**, remove one and the next bill is **$30.00** (⚠ this row originally said *$5.00 → $10.00*; that was never the ratified figure — `BR-RAT-090` is CONFIRMED at `$15.00` and `OQ-303`'s closure quotes the PO stating it. Corrected 2026-08-28 by the fixing lane, which took its figure from the rule and not from here). The count is OBSERVED, never typed. The live bill run has NO notion of unmetered services at all, and `asset_count` appears only in the shadow. This is also **the last of the four missing facts** blocking step 4 of the R1–R7 cutover | 2026-08-28 | **RELEASED 2026-08-28** — shipped as **2.79.16**, closing `DEF-1813`: a utility that collects three refuse carts from a property now bills **3 × $15.00 = $45.00** on the live bill run; take one cart away and the next bill is **$30.00**; a property with no carts bills **$0.00** and its bill still issues; a property whose carts have never been counted is **refused by name** and nothing is billed. **USED: `DEF-2310`** (`tenant_services.metered` has a reader and still no writer, so the declaration cannot be made from any screen), **`DEF-2311`** (`tenant_services.billed_uom` likewise — found while choosing where the count's unit comes from, and the reason it comes from the tariff instead), **`DEF-2312`** (the trash sample plan still carries the `$18.00` base `OQ-317` retired, under a comment saying the question is open), **`DEF-2313`** (two new money decisions landed in files no `human_owned.txt` glob matches — the FOURTH time this escape has hit a money path; raised for the PO rather than taken, because that list's header makes adding a line a PO ruling), **`BR-MET-710`** (*metering publishes the billable asset count on the row the service is priced from; `None` is nobody looked and is never `0`; the count crosses without a unit because a count is not a measure*) and **`BR-BIL-710`** (*the bill run prices an unmetered service from the observed count, attaching the tariff's own billed unit, and refuses an absent count by its own name*). **NO OQ WAS MINTED, and law 13 is why:** every question this work could have asked was already ruled — `OQ-283` (the quantity is an observed count), `OQ-303` (`$15.00` per cart), `OQ-317` (option A, the `$18.00` base retired) and `OQ-601` (the carts are a fact about the UNIT). The four judgments that remained are lane decisions, recorded in the decision log of this date with their worked figures and listed separately in the review-ledger row as NOT shown to the PO. **`DEF-2314`** (⚠ **A NEAR MISS ON THIS LANE'S OWN TOOLING, allocated after the block was first released and the row re-opened for it — stated so a reader does not read the extra id as a collision**: two lanes share ONE scratchpad directory and a sibling silently overwrote this lane's law-11 push helper with its own, which `cd`s into a DIFFERENT worktree; running it would have pushed that worktree's files under these path names, and only the pinned-base staleness check refused first). **`DEF-2315–2339`, `OQ-1050–1059` and `BR-<MOD>-712–729` are UNUSED and free.** |
| DEF-2460–2489 · OQ-1100–1109 · BR-\<MOD\>-810–829 | **`DEF-2310` + `DEF-2311` — A UTILITY CANNOT DECLARE WHAT KIND OF SERVICE IT SELLS.** `tenant_services.metered` has a reader and no writer, so `BR-RAT-081`'s declaration cannot be made from any screen or API and `BR-RAT-090`'s per-cart billing is unreachable on every shipped tenant — `metered=False` is written NOWHERE outside a test helper. `billed_uom` is the same column one over: read by metering, assets and rating, written by nothing, so every tenant's answer is `None`. Everything `DEF-1813` built (3 × $15.00 = $45.00) is reachable today only by editing a database row by hand | 2026-08-28 | **RELEASED 2026-08-28** — used **BR-TEN-810** and **BR-TEN-811**. **No DEF and no OQ minted**, which is the honest state for a lane whose whole job was two existing rows: `DEF-2310` and `DEF-2311` are both closed, and minting a third id to describe the same work would make the register count one defect twice. ⚠ **The `metered→unmetered after bills exist` question the dispatch flagged did NOT become an open question** — hard rule 4, `DEF-1813`'s ruling on `DEF-161` and `BR-MET-710`'s period-end observation between them determine the answer, so `BR-TEN-810` records it (forward-only, warns, worked at `3 × $15.00 = $45.00` for a mid-September change) rather than asking the PO to restate their own rules (law 13). **`DEF-2460–2489` and `OQ-1100–1109` are entirely UNUSED and free**; `BR-TEN-812–829` likewise. |
| DEF-2610–2639 · OQ-1150–1159 · BR-\<MOD\>-910–929 | **THE COMPARISON AT SCALE — load the connection-size backlog on the seeded tenant and re-run the two-path report across every account.** The report rests on ONE customer because one meter has a size; with no size the ruled chain cannot be attempted at all. Loading them is now an ORDINARY IMPORT (`DEF-1900` shipped both doors at 2.79.7 — a `Connection size` column on the meters template and a control on the asset screens), so this is a DATA step, not a build. Deliverable: the disagreement classes with a customer count against each, which is what tells the PO whether the known class touches one account or all of them | 2026-08-29 | **ACTIVE** |
| OQ-1160–1169 · DEF-2499–2503 (already taken, see State) | **CR-048 wave B task B11 — the remaining thirteen customer events.** Each of the thirteen had wording seeded on every tenant and no rule that could ever send it. Seven were given a live trigger, five are DRAWN AND REFUSED by name (BR-NOT-018) and one needed no new event because it is the SMS face of a receipt `payment_received` already governs. **The four OQ ids are the five refusals' blockers**: OQ-1160 there is no statement in this product, OQ-1161 nothing declares a planned outage or knows who is on one, OQ-1162 autopay is a capture-only flag so its confirmation would promise a charge nobody can take, OQ-1163 no plan status is `void`. The fifth refusal reuses OQ-249 (Work is R5) and mints nothing. | 2026-08-30 | **IN USE — OQ-1160–1163 taken; 1164–1169 free.** The DEF ids were allocated by `10-scripts/file_defect.py` and stepped DOWN out of reserved blocks on their own, landing at DEF-2499–2503: two plan-notice faults this wave fixed, the four-fault rate-plan letter it rewrote, and two it did NOT fix — the S35 manual modals pinning undeclared codes, and four bulk-correction cases already red at this lane's base commit |
| DEF-2580–2609 · OQ-1140–1149 · BR-\<MOD\>-890–909 | **`DEF-494` — A PLAN CANNOT BE PUBLISHED WITHOUT A START DATE (PO ruling 2026-08-28).** The live path bills any `status='published'` plan and consults NO date; the ruled path treats an undated plan as in force NEVER and refuses at R1. Same plan, opposite answers, and **R1 gates every other step** — the comparison cannot measure R2–R7 until this agrees. The ruling removes the state rather than picking a winner: required at publish, existing undated published plans given a date. **What date to backfill is NOT ruled and must not be guessed** | 2026-08-28 | **RELEASED 2026-08-28** — used **`BR-RAT-890`** and migration `rating 0024`; `DEF-2580–2609`, `OQ-1140–1149` and `BR-\<MOD\>-891–909` returned UNUSED. ⚠ **The lane was cut off by an API rate limit mid-close-out**, so the merge lane finished the record: the version, the changelog, the rule and the decision row are all later than the code they describe, and `DEF-494`'s own row was closed by the merge lane rather than its author — see that row, and `DEF-2103` for why nothing caught it |
| DEF-2550–2579 · OQ-1130–1139 · BR-\<MOD\>-870–889 | **CUTOVER STEP 5's MECHANISM — THE PER-STEP SWITCH, WHICH DOES NOT EXIST.** The approved method is *switch one STEP at a time, each only when its class is at zero*, and there is no seam that lets R1 be served by the chain while R2–R7 stay on the live path. So today the only available move is swapping all seven at once, which the method forbids by name (*"never swap and hope"*). **This is the actual thing standing between the PO's question and a yes.** 🔒 rating math | 2026-08-28 | **RELEASED 2026-08-28** — shipped as **2.79.19**. The seam exists: `06-backend/apps/billing/resolution_switch.py`, one fork at the end of `gather_account`, and **nothing is switched on** — the choice is carried by a deployment setting that is empty everywhere, `apply()` hands back the object it was given, golden-verify **33 PASS / 0 FAIL** and `run_gates` unchanged at **41 PASS / 13 FAIL**. Three of eight steps have a fork (R3+R4 → the base charge, together; R5 → the jurisdiction factor); the other five need their database half moved out of the bill run first and naming one of them REFUSES rather than being ignored. Proved by flipping it BOTH WAYS on one real account: water base **$8.00 → $12.50 → $8.00**, the live `R3/R4` disagreement (`BR-RAT-088`'s charge code against `plan_services.base_charge`, unmigrated on every tenant — `DEF-455`), which is **$4.50 a month per water connection** and is exactly why it stays off until step 4 rules it. **USED: `DEF-2550`** (`resolution_shadow`'s trailer still says it must have no production caller; it now has an INERT one, and the sentence invites a reader to file a false finding), **`DEF-2551`** (the shadow and the switch share the ADAPTER verbatim but each build the catalogue and call `resolve` — six lines that will drift, and `build_catalogue` already changed shape once), **`DEF-2552`** (a switched rule is resolved at gather and `with_readings` rewrites the readings afterwards without re-resolving — harmless for both forked rules and a real constraint on whoever forks R3b), and **`BR-BIL-870`–`BR-BIL-874`** (the deployment names what the chain serves and the default names none · ONE fork, chain run once per account · a switched rule with no answer refuses the ACCOUNT and never falls back · R3 and R4 switch together · a named step with no fork refuses rather than doing nothing). **NO OQ WAS MINTED, and law 13 is why:** the METHOD was ruled by the PO on 2026-08-27 and every remaining choice was ours to make and write down — the carrier, the fork's location, the refusal posture, the joint pair and the master-account refusal are all in the decision log of this date with their worked figures, and listed separately in the review-ledger row as NOT shown to the PO. The ONE thing that did go to the PO is not a question about the product: this file declares `HUMAN-OWNED` and no `human_owned.txt` glob matches it, which a lane may not fix itself. **`DEF-2553–2579`, `OQ-1130–1139` and `BR-<MOD>-875–889` are UNUSED and free.** |
| DEF-2520–2549 · OQ-1120–1129 · BR-\<MOD\>-850–869 | **`DEF-203` — THE UTILITY'S OWN BANK ACCOUNTS CANNOT BE CREATED, so bank reconciliation cannot run for any real tenant.** `bank_accounts` has a model, a unique key and two readers and **no writer**. **PO ruling 2026-08-28:** *"capture bank account in configure. Keep them in section which is logical"* — so a `kind: "list"` card in Settings → Configure → Reference data (`BR-SHL-035`: a new card is DATA, never a new layout), with payments validating and writing it (`BR-TEN-031`) | 2026-08-28 | **RELEASED 2026-08-28** — shipped as **2.79.23**, closing `DEF-203`: a utility can now enter its own bank accounts at **Settings → Configure → Reference data → Bank accounts**, and *"Chase Operating ••4021"* appears in the bank-statement import's step 1 where the picker was empty on every real tenant and could never stop being empty. **USED: `DEF-2520`** (on a USED bank account the shared list view freezes the Code field with *"read-only once used"* while Name stays editable, and because this list has no code column and both address the NAME, a rename still lands — filed against the shared view, not worked around in the handler; `tax_jurisdictions` has been in the same shape since 2026-08-09), **`DEF-2521`** (`G14`'s column-heading ratchet has no way to express *"this screen postdates r10"*, so this card's honest *"Last digits"* heading takes it from **228** to **229** and the only alternatives were worsening a red gate or silencing it; the baseline was NOT raised) and **`BR-PAY-850`** (*a utility captures its own bank accounts as Reference data — name, a 4-digit display mask that is never the account number, and active; deactivate never delete; one writer, and S38 step 1 selects and never creates*). **NO OQ WAS MINTED, and law 13 is why:** the one question this work could have asked — which ledger account a bank account maps to — is already ruled (`OQ-110`'s closure: reconciliation resolves `cash` BY DESIGNATION, one account per tenant), so no field was added and nothing was put back to the PO. The four judgments that remained (the 4-digit cap, the permanent `UNSEEDABLE_REFERENCE_LISTS` entry, the framework's code slot served by the NAME, and letting the DEF-016 and DEF-017 registers compose as *routed **or** written down*) are lane decisions recorded in the decision log of this date with their worked figures. **`DEF-2522`** was ALSO used, for a defect that is NOT this lane's: `owner_categories` is a declared reference list with no card in `referenceDataConfig.ts`, which is `DEF-236`'s exact shape again, and three ratified-set tests are RED on the pushed tip because of it — measured on a clean worktree at the tip with none of this lane's files present (**4 failed / 122 passed**), so it is reported rather than absorbed and `apps/tenancy` is left to the lane that owns it. **`DEF-2523–2549`, `OQ-1120–1129` and `BR-<MOD>-851–869` are UNUSED and free.** |
| DEF-2490–2519 · OQ-1110–1119 · BR-\<MOD\>-830–849 | **`DEF-1250` — SWITCHING A SERVICE ON AFTER SEEDING BADGES EVERY ACCOUNT WITH A SERVICE ITS PLAN CANNOT PRICE, AND THE IDEMPOTENT SEED WILL NEVER FIX IT.** `rating.sample_data` gates the trash schedule and its base row behind `_enabled('trash')` at seed time while `metering.sample_data` seeds trash service points regardless, and `BR-TEN-063` makes the replay a no-op. Still true on the PO's own tenant: `AC-2026-00001` badges WATER · SEWER · TRASH on a plan that states no schedule, no base charge and no billed unit for trash. This is the CAUSE of `DEF-1060`, whose other half is fixed | 2026-08-28 | **RELEASED 2026-08-28** — shipped as **2.79.20**, closing `DEF-1250`: a utility that switches a service on after it is already running can now reload the sample data and actually sell it — the plan gains the service, the addresses offer it, the units take it, and the three-cart household on the walkthrough property bills **3 × $15.00 = $45.00** where it was billed nothing. **USED: `DEF-2490`** (`OQ-317`'s closure — the retired `$18.00` monthly trash base — had never reached the fixture; closed here), **`DEF-2491`** (a later-enabled service is now BILLED and not yet BADGED — `apps/customers` is per-unit idempotent too; filed, not this lane's ground) and **`DEF-2492`** (switching a service on at Settings provisions nothing for it, and what an enable should do to an already-published plan is a product decision nobody has ruled; filed). **`BR-RAT-830`, `BR-RAT-831`, `BR-RAT-832` and `BR-MET-830` are the rules.** ⚠ **THE ROW'S OWN MECHANISM WAS HALF WRONG IN BOTH DIRECTIONS AND IS CORRECTED IN THE REGISTER:** `metering.sample_data` has not seeded service points *regardless of the flag* since CR-039 wave A (`DEF-795`), and the replay did NOT add *nothing* — it added the schedule and the charge code, and skipped only the PLAN's service row and the whole estate. ⚠ **`DEF-2493` WAS FILED FROM THIS BLOCK AFTER THE FIRST RELEASE, and the release was re-opened and re-closed rather than the id being taken quietly:** running the seed suites against this lane's work turned up `test_us_ten_019_tc4` red on `charge_codes: 25 != 23`, and the SAME test run alone on an UNTOUCHED worktree at `8febad7` fails identically — so it is a pre-existing collision between two CONFIRMED rules (`BR-TEN-058` says a sample run never writes a reference catalogue; `DEF-455` requires the base charge codes to be seeded, and `charge_codes` is a registered reference list) and not this lane's. Filed, not decided. **USED: `DEF-2490`, `DEF-2491`, `DEF-2492`, `DEF-2493`. `DEF-2494–2519`, `OQ-1110–1119` (none used — no question was left open) and `BR-<MOD>-833–849` are UNUSED and free.** |
| DEF-2460–2489 · OQ-1100–1109 · BR-\<MOD\>-810–829 | **`DEF-2310` + `DEF-2311` — A UTILITY CANNOT DECLARE WHAT KIND OF SERVICE IT SELLS.** `tenant_services.metered` has a reader and no writer, so `BR-RAT-081`'s declaration cannot be made from any screen or API and `BR-RAT-090`'s per-cart billing is unreachable on every shipped tenant — `metered=False` is written NOWHERE outside a test helper. `billed_uom` is the same column one over: read by metering, assets and rating, written by nothing, so every tenant's answer is `None`. Everything `DEF-1813` built (3 × $15.00 = $45.00) is reachable today only by editing a database row by hand | 2026-08-28 | **RELEASED 2026-08-28** — used **BR-TEN-810** and **BR-TEN-811**. **No DEF and no OQ minted**, which is the honest state for a lane whose whole job was two existing rows: `DEF-2310` and `DEF-2311` are both closed, and minting a third id to describe the same work would make the register count one defect twice. ⚠ **The `metered→unmetered after bills exist` question the dispatch flagged did NOT become an open question** — hard rule 4, `DEF-1813`'s ruling on `DEF-161` and `BR-MET-710`'s period-end observation between them determine the answer, so `BR-TEN-810` records it (forward-only, warns, worked at `3 × $15.00 = $45.00` for a mid-September change) rather than asking the PO to restate their own rules (law 13). **USED, AFTER THE ROW WAS FIRST WRITTEN AS 'NONE USED': `DEF-2460`** — this lane's own first push reverted two register rows and one block release by subtraction, with every law-11 check green, and the row is filed against itself rather than absorbed. **`DEF-2461–2489`, `OQ-1100–1109` and `BR-TEN-812–829` are UNUSED and free.** |
| DEF-2550–2579 · OQ-1130–1139 · BR-\<MOD\>-870–889 | **CUTOVER STEP 5's MECHANISM — THE PER-STEP SWITCH, WHICH DOES NOT EXIST.** The approved method is *switch one STEP at a time, each only when its class is at zero*, and there is no seam that lets R1 be served by the chain while R2–R7 stay on the live path. So today the only available move is swapping all seven at once, which the method forbids by name (*"never swap and hope"*). **This is the actual thing standing between the PO's question and a yes.** 🔒 rating math | 2026-08-28 | **ACTIVE** |
| DEF-2520–2549 · OQ-1120–1129 · BR-\<MOD\>-850–869 | **`DEF-203` — THE UTILITY'S OWN BANK ACCOUNTS CANNOT BE CREATED, so bank reconciliation cannot run for any real tenant.** `bank_accounts` has a model, a unique key and two readers and **no writer**. **PO ruling 2026-08-28:** *"capture bank account in configure. Keep them in section which is logical"* — so a `kind: "list"` card in Settings → Configure → Reference data (`BR-SHL-035`: a new card is DATA, never a new layout), with payments validating and writing it (`BR-TEN-031`) | 2026-08-28 | **ACTIVE** |
| DEF-2490–2519 · OQ-1110–1119 · BR-\<MOD\>-830–849 | **`DEF-1250` — SWITCHING A SERVICE ON AFTER SEEDING BADGES EVERY ACCOUNT WITH A SERVICE ITS PLAN CANNOT PRICE, AND THE IDEMPOTENT SEED WILL NEVER FIX IT.** `rating.sample_data` gates the trash schedule and its base row behind `_enabled('trash')` at seed time while `metering.sample_data` seeds trash service points regardless, and `BR-TEN-063` makes the replay a no-op. Still true on the PO's own tenant: `AC-2026-00001` badges WATER · SEWER · TRASH on a plan that states no schedule, no base charge and no billed unit for trash. This is the CAUSE of `DEF-1060`, whose other half is fixed | 2026-08-28 | **RELEASED 2026-08-28** — shipped as **2.79.20**, closing `DEF-1250`: a utility that switches a service on after it is already running can now reload the sample data and actually sell it — the plan gains the service, the addresses offer it, the units take it, and the three-cart household on the walkthrough property bills **3 × $15.00 = $45.00** where it was billed nothing. **USED: `DEF-2490`** (`OQ-317`'s closure — the retired `$18.00` monthly trash base — had never reached the fixture; closed here), **`DEF-2491`** (a later-enabled service is now BILLED and not yet BADGED — `apps/customers` is per-unit idempotent too; filed, not this lane's ground) and **`DEF-2492`** (switching a service on at Settings provisions nothing for it, and what an enable should do to an already-published plan is a product decision nobody has ruled; filed). **`BR-RAT-830`, `BR-RAT-831`, `BR-RAT-832` and `BR-MET-830` are the rules.** ⚠ **THE ROW'S OWN MECHANISM WAS HALF WRONG IN BOTH DIRECTIONS AND IS CORRECTED IN THE REGISTER:** `metering.sample_data` has not seeded service points *regardless of the flag* since CR-039 wave A (`DEF-795`), and the replay did NOT add *nothing* — it added the schedule and the charge code, and skipped only the PLAN's service row and the whole estate. **`DEF-2493–2519`, `OQ-1110–1119` (none used — no question was left open) and `BR-<MOD>-833–849` are UNUSED and free.** |
| DEF-2430–2459 · OQ-1090–1099 · BR-\<MOD\>-790–809 | **`DEF-536` — A DISCOUNTED BILL DRAFTS AND PREVIEWS AND CANNOT ISSUE.** `issue._gl_account_for` has no branch for kind `discount`, so `BR-BIL-010` refuses the whole bill with the generic unknown-kind sentence. **UNBLOCKED by PO ruling 2026-08-28** — *"you will need differnt GL code for these - dont keep them in same, create differnt category as required and keep them in it"*. Also unwired behind the same door: no `discount_grants` row is written at issue, so budgets and caps never deplete from real bills. 🔒 ledger posting | 2026-08-28 | **RELEASED 2026-08-28.** USED: `DEF-2430` (no `discount_grants` row is written at issue, so budgets and caps never deplete) · `DEF-2431` (nothing flips a programme to `suspended_funding_exhausted`) · `BR-BIL-790` (a discount posts to its own GL code) · `BR-BIL-791` (a negative bucket on that account is a DEBIT; on any other it still refuses, OQ-152 intact) · `BR-BIL-792` (corrections and back-bills re-price WITH the discount) · `BR-LED-790` (the thirteenth designation, seeded 4300, `signed=False`). **UNUSED and free again:** `DEF-2432–2459` · all of `OQ-1090–1099` (no question was raised — the ruling settled every money decision and the rest were judgments this lane made and wrote down) · `BR-BIL-793–809` and the other modules' 790–809. Both defects closed: `DEF-536` and `DEF-537` at `f191a8d`. |
| DEF-2400–2429 · OQ-1080–1089 · BR-\<MOD\>-770–789 | **CUTOVER STEP 3 — SURFACE THE DISAGREEMENTS ON THE PRE-COMMIT SCREEN.** The shadow can attempt a real account as of `DEF-1813` (*attempted 1 · disagreed 1 · blocked_by_reason {}*), so the count is no longer always zero and the panel deliberately held back on 2026-08-27 can now be honest. Measured: **no endpoint serves `summarise()` and no screen reads it** — the report exists only in Python. This is what produces step 4, which is the PO's to rule | 2026-08-28 | **RELEASED** — USED: `DEF-2400` (a guard of ours that passed on its own mutation, caught before merge) `DEF-2401` (the comparison panel asks metering three questions per customer) and `DEF-2402` (the panel took down the whole pre-commit stage over a body it could not read — the one thing the separate endpoint was built to make impossible, arriving through the rendering rather than the request). **OQ-1080–1089 and BR-\<MOD\>-770–789 RETURNED UNUSED** — no open question was minted and no business rule written: the panel implements the recorded method of 2026-08-27 and invents nothing, and every judgment it required is in the decision log rather than in a question. |
| DEF-2370–2399 · OQ-1070–1079 · BR-\<MOD\>-750–769 | **THE SIGN-UP HAND-OVER SCREEN (ONB-04.5) — PO REPORTED 2026-08-28 ON A FRESH DATABASE AND THE LATEST BUILD.** Two faults, both measured. (a) *Go to your utility* renders on `subdomain !== null` with **no `disabled` and no reference to `phase`**, so it is clickable at *Block 2 of 14* — while the auto-redirect three lines above correctly waits for `ready` or `waiting`. (b) `tenancy.signup.foot` is **false in both halves, in all ELEVEN catalogues** (this row said *thirteen* until 2026-08-28; `BR-SHL-041` ratifies eleven locale codes, `i18n/index.ts` holds eleven and `07-frontend/src/i18n/locales/` holds eleven files — all eleven were rewritten): it says migration happens *in Settings* (it is on the Accounts and Assets screens) and that signup *only captures configuration* (the block running underneath the sentence seeds **48 accounts** with contacts, billing addresses and service agreements, plus their units and meters) | 2026-08-28 | **RELEASED 2026-08-28** — used `DEF-2370` (the hand-over button), `DEF-2371` (the false footer) and `DEF-2372` (a defect row whose version resolves to another lane's release). **No OQ and no BR was minted:** the PO's ruling was complete, and both fixes execute rules already signed — `BR-SHL-025` (disabled-with-reason) and B14 rule 32 (the reason gets a declared line). `DEF-2373`–`2399`, `OQ-1070`–`1079` and `BR-<MOD>-750`–`769` were NOT used and return to the pool. |
| DEF-2340–2369 · OQ-1060–1069 · BR-\<MOD\>-730–749 | **`DEF-498` + `DEF-493` — THE RULED CHAIN CANNOT BE SWITCHED ON.** R4's `ChargeCode` expresses a flat amount or a per-size table and CANNOT express a percent or a per-case amount, so five provisioned codes (LATE, TAP, IMPACT, DAMAGE, BULK-WATER) each refuse the WHOLE bill by name — **23 codes, 5 unpriceable**. And R4 narrows by service, class and size and by NOTHING else, reading neither `charges.charge_type` nor `charges.auto_apply`, so a flipped R4 puts **18 codes totalling $799.95** on a bill whose base is **$8.00**. 🔒 rating math | 2026-08-28 | **RELEASED 2026-08-28** — used: `DEF-2340` (a per-case charge and an unpriced charge are the same stored row), `DEF-2341` (the shadow's hand-written copy of the refusal→step map cannot see a new refusal class), `BR-RAT-730` (which charge codes ride an ordinary periodic bill), `BR-RAT-731` (R4 states one amount or refuses by the name of the rule in the way). **NO OQ WAS MINTED** — `DEF-493`'s open question was already ruled (`BR-RAT-117`, PO 2026-08-22), so `OQ-1060–1069` are all unused and returned. `DEF-2342–2369` unused. |
| DEF-2280–2309 · OQ-1040–1049 · BR-\<MOD\>-690–709 | **`DEF-2190` — PER-SIZE PRICES CANNOT BE SET AT ANY LAYER.** `charge_code_amounts` has a model, a migration and readers in `resolution.py`, `resolution_catalogue.py`, `selectors.py` and the shadow — and **no writer outside a test**, and no handler in `rating/api.py` or `rating/services.py`. So `BR-RAT-088`'s own worked example — a 5/8-inch water base at $8.00 and a 2-inch at $34.00 on ONE charge code — cannot be expressed by any utility. This is the missing half of `DEF-1900`: a meter can now RECORD its size and still cannot be PRICED by it. 🔒 rating math | 2026-08-28 | **RELEASED 2026-08-28** — shipped as **2.79.15**, closing `DEF-2190`: a utility can now charge **$8.00** for a 5/8-inch water connection and **$34.00** for a 2-inch one on the SAME charge code, where yesterday both resolved **$8.00**. **USED: `BR-RAT-690`** (*a charge code's amount may be stated per connection size; the size must be one the tenant configured, unioned with sizes the code already priced so a retired size never blocks a save; a code states one amount OR a per-size table, never both, refused at the write rather than on billing day; blank = NOT SERVED and refuses, `0.00` = served free, no row = nobody priced it*), **`DEF-2280`** (the per-size column's own docstring claimed `NUMERIC(18,6)` two lines above a four-place field — corrected, nothing was ever stored wrong) and **`DEF-2281`** (rating pads every served money string to six places, so a four-place column publishes `8.000000` — filed and deliberately NOT fixed, because the padding is shared by every money field in the module and belongs with the migration that narrows the other 55 columns). **NO MIGRATION WAS NEEDED and none was allocated** — `charge_code_amounts` and its unique key have existed since `rating.0010`; what was missing was a validator, a writer and a screen. **NO OQ WAS MINTED, and law 13 is why:** the three questions worth asking were already answered in the repo — where the base lives (`BR-RAT-088`, PO 2026-08-20), what a blank means (`DEF-277`, and `CR-013` part 1's *"blank base = size not served"*), and how many decimals (`BR-RAT-089`/`092`, `OQ-285` CLOSED). The judgments that remained are lane decisions, recorded in the decision log of this date with their worked figures and listed separately in the review-ledger row as NOT shown to the PO. **`DEF-2282–2309`, `OQ-1040–1049` and `BR-<MOD>-691–709` are UNUSED and free.** |
| DEF-2250–2279 · OQ-1030–1039 · BR-\<MOD\>-670–689 | **THE DEPOSIT REGISTER AND THE BOOKS CANNOT AGREE, IN EITHER DIRECTION (`DEF-177` + `DEF-1713`, exact mirrors).** `payments` credits the 2300 deposit liability on every cleared deposit and NOTHING writes `accounts.deposit_on_file`; `create_from_import` writes `deposit_on_file` and posts NOTHING, so the seeded estate carries a **$750.00** deposit register against a **$0.00** liability. Now urgent because `DEF-202` shipped the box that lets a utility set deposit amounts at all. 🔒 ledger posting | 2026-08-28 | **RELEASED 2026-08-28** — shipped as **2.79.13**, closing `DEF-177` and `DEF-1713`: the sample utility's deposit register and its 2300 deposit-liability account both read **$750.00** where they read **$750.00 against $0.00**. **USED: `DEF-2250`** (the tie-out was comparing a control total windowed at `period_end` against `accounts.deposit_on_file`, an UNDATED live column — found by fixing the two above, and it is what made the fix still read as broken), **`BR-CUS-670`** (*the deposit register moves with the money, in both directions — written when a deposit-purpose payment clears, unwritten when one is reversed, by the same amount, in the same transaction as the ledger leg*) and **`BR-CUS-671`** (*a migrated deposit posts DR opening clearing / CR deposit liability, dated at cutover, keyed per (batch, account), immutable*). **NO MIGRATION WAS NEEDED and none was allocated** — `journal_entries.source_type` is an unconstrained TEXT column and the entry reuses the `opening_balance` value B2 Addendum r9 #3 already admits, distinguished by the key's EVENT half (`cutover-deposit:<batch>`); inventing a second source_type would have added a value `apps/ledger/reporting.SOURCE_TYPE_TO_VOCABULARY` refuses to bucket silently, to say what the existing one already says correctly. **NO OQ WAS MINTED, and law 13 is why:** the one question worth asking — what date a migrated deposit books at — was already answered by `BR-CUS-049` (PO AC-4, 2026-08-08: *dated at cutover*), and the 2026-08-27 changeover ruling makes *a date the operator supplies* the SAME date, so two of the three readings on offer were one option. The judgments that remained (the contra leg is the opening-clearing account; the register is written by customers at payments' request; the movement is the amount that CLEARED and never the plan's schedule figure) are lane decisions, recorded in the decision log of this date with their worked figures and listed separately in the review-ledger row as NOT shown to the PO. **`DEF-2251–2279`, `OQ-1030–1039` and `BR-<MOD>-672–689` are UNUSED and free.** |
| DEF-2220–2249 · OQ-1020–1029 · BR-\<MOD\>-650–669 | **`DEF-652` — THE PO's TAX RULING OF 2026-08-27 NEVER REACHED THE DATA.** PO verbatim: *"Tax the full amount before discount — The utility remits tax on the full service value; the discount is the utility's cost, not the tax authority's."* That is `discount_treatment = after`. `rating/models.py:923` still defaults to `before`, nothing seeds it otherwise, so every discounted bill taxes the REDUCED base: $3.19 where the ruling says $4.26, **$1.07 per discounted bill per cycle**. And `03-golden-verify.py` contains the word *discount* **zero** times, which is why two readings looked right for months. 🔒 rating math + migration ordering | 2026-08-28 | **RELEASED 2026-08-28** — shipped as **2.79.12**, fixing `DEF-652`. **USED: `BR-RAT-650`** (*a tax levies on the full service value unless its own authority says otherwise — `taxes.discount_treatment` defaults to `after`*), migration **`rating 0023`** (ALLOCATED here, not taken from the watermark — `DEF-892`; `0022` was the real leaf), and **`DEF-2220`** — `resolution.py`'s R6 header instructs whoever wires the R1–R7 chain to do the very thing this lane just undid (*"discounts apply BEFORE taxes, so a discount reduces the taxable base"*), on the path that is meant to carry pricing into production. Filed rather than fixed: the file is 🔒 human-owned and correcting prose in a guarded money file belongs with the lane that can prove the chain. **NO SECOND DEF WAS MINTED FOR THE FIX ITSELF** — `DEF-652` already described it, and a second row would make the register count one defect twice. **NO OQ WAS MINTED, and law 13 is why:** every question this lane met was already answered in the repo — the PO ruled the substance on 2026-08-27, `BR-RAT-106` ruled that the treatment is per tax, and hard rule 4 ruled what happens to bills already issued. The three judgments that remained (reversing the previous lane's *default stays `before`*; migrating existing rows; leaving a NULL seam answering `before`) are lane decisions with their reasoning in the decision log of this date and listed separately in the review-ledger row — not questions for the PO. `DEF-2221–2249`, `OQ-1020–1029` and `BR-<MOD>-651–669` are **UNUSED and free**. |
| DEF-2190–2219 · OQ-1010–1019 · BR-\<MOD\>-630–649 | **A UTILITY CANNOT EXPRESS ITS OWN PRICES (`DEF-202` · `DEF-254` · `DEF-455` · `DEF-466` · `DEF-515`).** Deposits post nothing; the outside-city money factor multiplies every base and every usage line and NOTHING at any layer can set it, so every bill this product has issued priced at exactly 1.0; tax jurisdictions seed and tax RATES do not, so a tenant declining the sample data bills with no tax and nothing warns; and the seeder writes no base charge codes, so the plan wizard's step 4 is unwalkable on a live tenant. 🔒 rating math — `apps/rating/pricing/**` is guarded; `apps/billing/gather.py` is NOT and probably should be, which is the PO's call and goes to the review ledger | 2026-08-28 | **RELEASED 2026-08-28.** Used: **`DEF-2190`** only — per-size base amounts cannot be set at any layer (`charge_code_amounts` has a model, a migration and two readers and NO writer; `CHARGE_FIELDS` has no `size_amounts` key), found while seeding `DEF-455`'s codes. **No OQ and no BR minted:** every rule this lane needed was already CONFIRMED (`BR-RAT-088`, `BR-RAT-102`, `BR-RAT-020/023`, `BR-RAT-108`) and the two judgement calls — keeping `plan_services.base_charge` until R4 has a production caller, and WARNING rather than seeding or refusing on unpriced taxes — are lane decisions with their reasoning in the decision log, not questions for the PO (hard-won law 13). `DEF-2191–2219`, `OQ-1010–1019` and `BR-<MOD>-630–649` are UNUSED and free. |
| DEF-2160–2189 · OQ-1000–1009 · BR-\<MOD\>-610–629 | **THE METERS IMPORT TEMPLATE IS UNFILLABLE (`DEF-1077`, PO 2026-08-27 *"there is not unit ID or unit name that we can provide - what about this"*), AND A PRODUCTION REFUSAL CARRIES NO TRACE REFERENCE (`DEF-965` / `DEF-1080` second half).** The downloaded file writes our FIELD NAMES as headers, the three accepted shapes of a unit reference live only in two Python docstrings, and the worked example ships blank | 2026-08-28 | **RELEASED** (2026-08-28 — used: `DEF-2160` (the accounts template invents `U-00001`), `DEF-2161` (LOGGING names `apps` and not `core`, so every refusal's trace line is discarded in production), `DEF-2162` (a tenant provisioned before today keeps a default mapping template keyed on field names, so the label-headed sample matches no row — one badge, not a broken import), `DEF-2163` (the premises template ships the words *"Sample lat"* as a map coordinate — found by downloading the file and reading it, hard-won law 6), `DEF-2164` (a test still asserts the alias CR-046 re-pointed on 2026-08-27 — RED on the tip and not caused by this lane), `BR-MET-610`/`611`/`612`. Unused: `DEF-2165–2189`, `OQ-1000–1009` — no open question was minted, because nothing here needed a value chosen (hard-won law 13: a judgment recorded in the decision log is the deliverable); `BR-<MOD>-613–629`) |
| DEF-2130–2159 · OQ-990–999 · BR-\<MOD\>-590–609 | **THE DISCONNECTION AND TRANSFER WORKFLOWS GET THEIR DOORS (`G52`, `DEF-2035`).** Both wizards are built, mounted in `App.tsx` and complete; `06-backend/apps/customers/api.py` serves NONE of the six addresses they post to. 5,436 lines of engine in `disconnects.py` and `transfers.py` reachable only from Python | 2026-08-28 | **RELEASED 2026-08-28** — twenty of `G52`'s twenty-nine now reach a route; the gate reads **220 of 229 reachable, 9 unreached**, and the twenty baseline lines are DELETED, which is that file's own instruction for recording a fix. **USED: `DEF-2130`** (the three account-scoped reads answered **200** for an account id the tenant cannot see — HR-1's posture is 404, and nothing leaked, so this was a posture defect rather than an isolation breach) · **`DEF-2131`** (`ReconnectionTerms.fee` typed non-nullable while its own prose four lines above said *"fee IS NULLABLE"* and the server sends `null` on every tenant here — unfalsifiable until the route was mounted, because a hand-written type over a 404 cannot be contradicted) · **`DEF-2132`** (the two refund doors were mounted and would have refused **every** Admin: `payments/api._actor` returns the raw `User` row, which has no `.role`, and those two are the only `@require_role` services in that module — correct for every prior caller, wrong for the first role-gated one). **`OQ-990–999` UNUSED and returned:** `OQ-374`, `OQ-382`, `OQ-383`, `OQ-384` and `OQ-385` are all still OPEN and the engines already refuse on each, so no new question was owed and none was minted — the routes carry those refusals through and soften none. **TWO `BR-` IDS TAKEN: `BR-CUS-590`** (the transfer commits through ONE door running all five staged writes in one `transaction.atomic()`) and **`BR-CUS-591`** (the ladder is NOT orchestrated — eleven acts, eleven routes, because `schedule_cut` needs a signed certified-mail receipt that arrives days later and one door would have to fabricate it). Both are BUILD decisions under law 13, in `03-customers/02-business-rules.md` with their worked figures, and one word from the PO reverses either. `BR-<MOD>-592–609` and `DEF-2133–2159` free. |
| DEF-2100–2129 · OQ-980–989 | **The merge lane's own block.** Opened for `DEF-2100` — the container rewind that left 117 files of the shared tree holding a 276-commit revert while two lanes built on it, and the law-12 clause that told the session to leave it there | 2026-08-28 | **ACTIVE** |
| DEF-2060–2089 · OQ-960–969 · BR-\<MOD\>-570–589 | **`BR-RAT-120` BUILT — the PO's pricing ruling of 2026-08-28 turned into code.** *"we need to charge account based on connection size they have"*: `served_sizes` becomes what the TENANT HAS CONFIGURED, so R3's *"this size is not served"* refusal can fire instead of silently pricing a 3-inch connection at the 5/8 rate ($8.00 both ways today). 🔒 rating math — the three files went on `human_owned.txt` by PO ruling the same day, so this is the first change under that guard | 2026-08-28 | **RELEASED** (2026-08-28 — DEF-2060 used; OQ-960–969 and BR-570–589 unused: no open question was minted and BR-RAT-120 already existed) |
| DEF-2030–2059 · OQ-950–959 · BR-\<MOD\>-550–569 | **`DEF-1793` — the FIFTH sibling in the *built is not wired* family: a SERVICE or ruled rule with no route, inside a module that already serves routes.** Twelve of the open highs are this shape and all four existing siblings pass over them. **Unblocked 2026-08-28** by the PO adding the three pricing files to `human_owned.txt` — the boundary-gates lane measured this gate at 69 candidates → 6 when scoped to the 🔒 set, and declined to build it because that scope had the hole `DEF-1841` named | 2026-08-28 | **RELEASED 2026-08-28** — shipped `G52 role-gated-doors` in `499a060`. **The 🔒 scope was NOT the one that worked.** That scope answers a FILE-shaped question (*which module does nothing import*) and `DEF-478` is ACTION-shaped: its six services live in a file that is imported, mounted and serving routes. Re-scoped to **`@require_role`** — a DECLARATION that a human performs the act, not a Django convention — and measured **229 actions across 31 backend files; 200 reach a route a person can get to; 29 do not**, in 7 files across 5 modules, **1,838 lines** behind no door. Baseline is the named set of 29. **USED: `DEF-2030`** (the disconnect ladder, 11 actions / 930 lines, and `customers/api.py` mounts only `path("disconnects", disconnects_list)`) · **`DEF-2031`** (the transfer wizard, 7 actions / 386 lines, same shape) · **`DEF-2032`** (`approve_refund` + `void_refund` — money OUT under `BR-PAY-014` with no route at all) · **`DEF-2033`** (three singletons: `close_read_window`, `delete_version`, `save_and_exit`) · **`DEF-2034`** (`test_def400_discount_lifecycle_routes.py:69` excuses `suspend_discount_for_funding` as *"called by the bill run"* and NOTHING calls it — the check `DEF-478` shipped is green on a false sentence). **`OQ-950–959` and `BR-<MOD>-550–569` UNUSED and returned:** every judgment was ours to make and is in `02-decision-log.md` with its measurement (law 13). ⚠ **It does NOT cover `DEF-438`** — the R1–R7 chain carries no role decorators — and the docstring says so rather than letting `19-execution-sequence.md`'s expectation stand. `DEF-2035–2059` unused. |
| DEF-2000–2029 · OQ-940–949 · BR-\<MOD\>-530–549 | **`DEF-1900` — BOTH DOORS FOR THE CONNECTION SIZE (PO 2026-08-28, *"Please do both"*).** A size column on the meters import target, and a size control on `AssetAddWizard` (AST-05) and `AssetDetailPage` (AST-01/02). Chosen from the forty ratified codes, never typed; blank stays lawful; an unknown code is refused at VALIDATE | 2026-08-28 | **RELEASED 2026-08-28** — built and pushed. **NO `DEF-` OR `OQ-` ID WAS TAKEN** (no new defect: `DEF-1900` was CLOSED, not re-filed; no new open question: nothing in the build reached an unruled boundary, and the four judgments the ruling's sentence did not make were already settled in the ruling row). **TWO `BR-` IDS TAKEN: `BR-MET-530`** (the meters import column + `AST.SIZE_CLASS_IN_LOOKUP`) and **`BR-AST-530`** (the AST-05 and S51 controls + the AST-01/02 display). `BR-<MOD>-531–549` and the whole `DEF-`/`OQ-` block are FREE. |
| DEF-1970–1999 · OQ-930–939 | **RE-TRIAGE SAMPLE — how stale is the register really? (`DEF-1930`'s open question).** Step 4's first block found **seven of nine** open highs already fixed, and every triage number in `19-execution-sequence.md` — including the ones the merge lane has been quoting — rests on the open counts being true. This lane draws a RANDOM sample of open highs, decides each on evidence, closes what is provably done, and **reports the RATE with its method**. It fixes nothing | 2026-08-28 | **RELEASED 2026-08-28** — used: **NONE**. The lane's whole deliverable is a MEASUREMENT, so it filed no defect and minted no question: seed `19300827`, 15 rows drawn from the 83 eligible open highs, **3 already fixed / 12 still open / 0 not-a-defect / 0 undecidable**. Rate **20%**, Wilson 95% CI **7–45%**, which excludes `DEF-1930`'s 78% and excludes zero. It closed `DEF-136` · `DEF-357` · `DEF-461` against existing rows — open highs read **81**, not 84. `DEF-1970–1999` and `OQ-930–939` are returned UNUSED |
| DEF-1930–1969 · OQ-910–929 · BR-\<MOD\>-510–529 | **Step 4, first module block — customers, and specifically the SERVICE-REQUEST + MOVE-OUT surface.** Nine of the sixteen open customers highs are one cluster: `DEF-611` · `DEF-628` · `DEF-634` · `DEF-635` · `DEF-637` · `DEF-638` · `DEF-640` · `DEF-648` · `DEF-649` — spec, prototype r10 and the running product disagreeing about one surface. Step 4's own rule is *by module, not by id*, and this is the cluster inside the module | 2026-08-27 | **RELEASED 2026-08-27** — used: `DEF-1930` (the register-hygiene root) and `BR-CUS-510` (the balance cell's two kinds of zero). **No OQ was minted: nothing in the nine needed a PO ruling** — seven were already fixed, and the two that were not resolved from r10/B19, B14 and the decision log. `DEF-1931–1969`, `OQ-910–929` and `BR-<MOD>-511–529` are returned UNUSED |
| DEF-1900–1929 · OQ-900–909 · BR-\<MOD\>-500–509 | **Step 1, HANDED TO METERING — source the connection size** (`DEF-514` · `DEF-1811` · `DEF-1812`). The R1–R7 lane stopped at step 3 having proved the chain cannot be run on a single real account: R3 needs a connection size and `Asset` has no column for one, so `assets_on_unit` publishes none, `route_meter_picker.size_class` is always null and `gather` has nothing to pass. Until this lands, `DEF-438`, `DEF-484`, `DEF-466` and `DEF-515` cannot be fixed as written | 2026-08-27 | **RELEASED 2026-08-27** — shipped as **2.79.5**. `BR-AST-500` (`assets.size_class`, migration `assets/0010`), `BR-AST-501` (the size is billing-affecting) and `BR-MET-500` (`connection_size_for` + the `multiplier` key + `billing_multiplier_for`). `DEF-514`, `DEF-1811` and `DEF-1812` are **fixed**; `DEF-484`'s SOURCE half is built. **USED: `DEF-1900`** (no control and no import column can write the size — the remainder of `DEF-484`) and **`DEF-1901`** (`route_meter_picker` reads `service` and `read_method` out of `assets_on_unit` too, and that dict publishes neither — two more permanently-empty columns beside the one just fixed). **`OQ-900–909` UNUSED and returned:** the size VOCABULARY was already ruled by `BR-TEN-170`/`BR-TEN-171` on 2026-08-27, so law 13's grep found it and nothing needed asking. `BR-<MOD>-502–509` unused. `DEF-1902–1929` unused. ⚠ `DEF-1810` is deliberately NOT resolved — what `served_sizes` MEANS is a money question and is the PO's, through the CONSUMING lane. |
| DEF-1860–1879 · OQ-890–899 · BR-\<MOD\>-490–499 | **Step 3b of `19-execution-sequence.md` — the four gates that are red on something a CUSTOMER sees**: `G28` (76 internal register ids in UI copy, baseline 0), `G32` (four close-out refusals resolving to silence), `G18` (the one genuinely raw key), `G15` (ten parity failures). All four land in the eleven i18n catalogues, which is why this waited for the CR-045 wave G lane to release them | 2026-08-27 | **RELEASED** 2026-08-27 — used `DEF-1860` (G28's Part-3 ratchet rise, 555 vs 498) · `DEF-1861` (G28's id pattern misses an id followed by a Korean letter; the true Part-1 count was 77) · `DEF-1862` (G18's one "renders raw" finding is a false positive — a dot-plural stem) · `DEF-1863` (G15's ten failures are two unrelated defects). No OQ and no BR was needed: nothing here required a ruling. `DEF-1864`–`DEF-1879`, `OQ-890`–`899` and `BR-<MOD>-490`–`499` are unused and free. |
| DEF-1810–1839 · OQ-870–879 · BR-\<MOD\>-470–479 | **Step 1 of `19-execution-sequence.md` — the four criticals as ONE job: `DEF-438` · `DEF-498` · `DEF-493` · `DEF-652`, the R1–R7 rating chain wired into billing.** Dispatched as a single lane ON PURPOSE: the deliverable is the SET OF DISAGREEMENTS between the chain and the live `gather.py` path, and four lanes each reconciling "their" defect would delete that evidence separately. Block is wide because the disagreements themselves are expected to be filed as defects | 2026-08-27 | **RELEASED 2026-08-27** — used **DEF-1810** (R3's size refusal is unreachable through any correct adapter) · **DEF-1811** (the shadow cannot run on a single real account of any tenant) · **DEF-1812** (no meter multiplier crosses billing's read seam) · **DEF-1813** (no billable asset count crosses it either) · **DEF-1814** (`file_defect.py` cannot allocate INTO the block reserved for the lane running it — which is why these five came back as DEF-1793–1796 and DEF-1809 and were renumbered into this block by hand). **No OQ-870–879 and no BR-470–479 minted, deliberately:** step 4 of the cutover method (*rule each class of disagreement*) was never reached, because step 3 measured that the chain cannot be run at all — so nothing was ruled and nothing needed asking. See decision log 2026-08-27, *"R1–R7 STEP 3, DELIVERED"* §5. **DEF-1815–1839 unused.** |
| DEF-1840–1859 · OQ-880–889 · BR-\<MOD\>-480–489 | **Step 3 of `19-execution-sequence.md` — three boundary gates** (frontend↔seed · import↔ledger · template↔series) plus the non-test-importer gate. Every existing gate compares a frontend artefact to another frontend artefact or a document to a document; the three worst escapes of 2026-08-27 each crossed a boundary nothing watches | 2026-08-27 | **RELEASED 2026-08-27** — three gates landed and registered: **G47** service-catalog-parity (frontend↔seed), **G48** import-money-posts (import↔ledger), **G49** identifier-series-contract (template↔series). Suite 32 PASS/15 FAIL → **36 PASS/14 FAIL**; no gate broken. Used **DEF-1840** (five served strings name a Settings tab that does not exist — found by G49 clause (d), and NOT fixed here because two tests pin the wrong wording and the decision log carries it) · **DEF-1841** (the whole R1–R7 resolution chain is rating math, is marked HUMAN-OWNED, and no glob in `human_owned.txt` matches it — G7 has never looked at it; the third occurrence of an escape that file records twice in its own words). **The fourth gate was NOT built, deliberately** — see decision log 2026-08-27, *"THE THREE BOUNDARY GATES, AND WHY THERE IS NO FOURTH"* §4: it is genuinely uncovered by G13/G40/G20, but its only workable scope (the 🔒 set) has the hole `DEF-1841` names, so building it now would ship false assurance. The measurement is recorded so the next lane starts from data. **No OQ-880–889 and no BR-480–489 minted:** nothing here needed a ruling — law 13, a judgment recorded with its reasoning is the deliverable. **DEF-1842–1859 unused.** |
| DEF-940–949 · OQ-520–529 | CR-040 wave B — opening balance on the first bill | 2026-08-27 | **ACTIVE** |
| DEF-980–999 · OQ-530–539 | CR-040 wave B — master account, children and its bill | 2026-08-27 | **ACTIVE** |
| DEF-950–959 · OQ-540–549 | CR-041 — toolbar consistency, tasks 2–6 | 2026-08-27 | **ACTIVE** |
| DEF-**1008**–1019 · OQ-570–579 · BR-\<MOD\>-200–209 | Asset import — the commit fails after a clean dry run | 2026-08-27 | **ACTIVE — NARROWED 2026-08-27.** ⚠ **DEF-1000–1007 are GONE to the CR-041 toolbar lane**, which was dispatched BEFORE this file existed and allocated into what later became this block. Its ids are cited in its code and tests and are merged, so they stay where they are and this block starts at 1008. That lane has in fact been filing from the 960s (962–965) since the allocator started stepping down, so nothing here is lost |
| DEF-1020–1039 · OQ-580–589 · BR-\<MOD\>-210–219 | CR-042 — two write modes, on step 1, on every import | 2026-08-27 | **ACTIVE** |
| DEF-1040–1059 · OQ-590–599 · BR-\<MOD\>-220–229 | CR-043 — the Run bills wizard (DEF-936 blocker, 939, 938, 746, finding 15) | 2026-08-27 | **RELEASED 2026-08-27** — used **1040, 1042, 1043**; **590**. No BR minted: every rule this lane touched was already signed (BR-SHL-018/019/025/047, BR-BIL-005/050, IS-8, B14 rules 2 and 21). ⚠ The dispatch called finding 13 *DEF-935*; **DEF-935 is the asset-import template defect**, fixed the same day by another lane. Finding 13 is **DEF-746**, and the Run bills surface it did not count is **DEF-1043**. |
| DEF-1060–1089 · OQ-**601**–609 · BR-\<MOD\>-230–239 | CR-043 — the bills list and bill detail (DEF-969, 968, 967, 966, 937, 979, the panels) | 2026-08-27 | **ACTIVE — NARROWED 2026-08-27.** ⚠ **OQ-600 is GONE to the CR-041 toolbar lane** for the same reason as the row above: dispatched first, allocated before this file existed, now merged and cited. Its question is *do 18 prompts read "Search …" while 5 read a bare field list, and is that a PO copy call* |
| DEF-1090–1119 · OQ-610–619 · BR-\<MOD\>-240–249 | CR-039 wave F + CR-040 wave E, and DEF-978's stale summary | 2026-08-27 | **ACTIVE** |
| migration `tenancy 0025` | CR-039 wave F task 27 — the implementation order's unique number (`DEF-892`: a migration number is ALLOCATED to a lane, never taken from the watermark). `0023` is unclaimed and `0024` is the CR-039 wave E lane's recorded, unused reservation; both are deliberately skipped, and `0025` depends on `0022`, the real leaf | 2026-08-27 | **ACTIVE** |
| DEF-960–969 · OQ-550–559 | Settings honesty + reference sweep | 2026-08-27 | **RELEASED 2026-08-27** — used 960, 961; 550. ⚠ The merge lane later took **966, 967, 968, 969** out of the released tail for CR-043's findings |
| DEF-960–969 · OQ-550–559 | Settings honesty + reference sweep | 2026-08-27 | **RELEASED 2026-08-27** — used 960, 961; 550 |
| DEF-970–979 · OQ-560–569 | CR-039 wave E tasks 20–21 | 2026-08-27 | **RELEASED 2026-08-27** — used 970–973, 976; 560, 561 |

**DEF-974, DEF-975, DEF-977, DEF-978 were taken by the merge lane** out of the
970s after that block was released, which is lawful and is why the block's row
says which ids it actually used rather than "970–979".

| DEF-1120–1149 · OQ-620–629 · BR-\<MOD\>-250–259 | The DISPLAY-TRUTH sweep — every stored value reaching a screen unformatted, plus a gate | 2026-08-27 | **ACTIVE** |
| DEF-1150–1179 · OQ-630–639 · BR-\<MOD\>-260–269 | Page-header, toolbar capacity and popover clipping (B14 rules 2 and 4) | 2026-08-27 | **ACTIVE** |
| DEF-1180–1219 · OQ-640–659 · BR-\<MOD\>-270–289 | CR-044 — One-time bill, Budget bills and Fix a bill: a workflow each, end to end | 2026-08-27 | **ACTIVE** |

| DEF-1220–1249 · OQ-660–669 · BR-\<MOD\>-290–299 | CR-039 wave F — the commercial model gets a SCREEN (DEF-1092) | 2026-08-27 | **RELEASED 2026-08-27** — used **1220, 1221, 1222**; **660**. No BR minted: every rule S107 needed was already signed (BR-TEN-002/014/240, BR-SHL-020/023/025/034/044, B14 rules 2/17/18/21), which is the honest state for a screen over somebody else's model. ⚠ **AND `DEF-1221` IS ABOUT THIS FILE'S OWN ENFORCER.** `file_defect.py` reads the blocks here and steps DOWN past every ACTIVE one, so a lane whose block sits ABOVE the register's watermark is handed an id inside SOMEBODY ELSE'S block, every time. Measured on this lane's first call: watermark 1179, this block 1220–1249, the tool returned **DEF-1080** — inside CR-043's 1060–1089, and **another lane took DEF-1080 for real the same afternoon**. All three rows were corrected by a byte-exact one-field rewrite of the appended line. Until the tool takes a `--block`, a lane holding a high block must check the id it is given against this table before it trusts it. |
| DEF-1250–1279 · OQ-670–679 · BR-\<MOD\>-300–309 | The bill's two omissions — DEF-990 master base charges · DEF-1060 unit-derived services | 2026-08-27 | **ACTIVE** |
| DEF-1280–1319 · OQ-680–689 · BR-\<MOD\>-310–319 | Customers — the thirteen high-severity open defects | 2026-08-27 | **ACTIVE** |
| DEF-1320–1359 · OQ-690–699 · BR-\<MOD\>-320–329 | Metering — the high-severity open defects | 2026-08-27 | **ACTIVE** |

| DEF-1360–1389 · OQ-700–709 · BR-\<MOD\>-330–339 | CR-045 wave A — the shared toolbar frame (width, orphaned rules, ↓ glyph, slot order) | 2026-08-27 | **ACTIVE** |
| DEF-1390–1419 · OQ-710–719 · BR-\<MOD\>-340–349 | CR-045 wave C — the six new server search legs, Accounts phone/email first | 2026-08-27 | **RESERVED, not started** |
| DEF-1420–1449 · OQ-720–729 · BR-\<MOD\>-350–359 | CR-045 wave D — filters for the seven lists that have none | 2026-08-27 | **RESERVED, not started** |
| DEF-1450–1479 · OQ-730–739 · BR-\<MOD\>-360–369 | CR-045 waves B · E · F — copy, the five missing exports, the gate and the close-out | 2026-08-27 | **RESERVED, not started** |
| DEF-1550–1579 · OQ-780–789 · BR-\<MOD\>-390–399 | **SSN encryption — DEF-632**: capture the Social Security number on the service request, encrypt it at rest through `core.crypto`, show staff the last four only | 2026-08-27 | **ACTIVE** |
| DEF-1580–1609 · OQ-790–799 · BR-\<MOD\>-400–409 | **THE PREMISES OWNER IS THE MASTER ACCOUNT (DEF-650 critical + DEF-1088 high, one piece of work)** — the premises names a real master account rather than free text, an existing master is detected and REUSED at premises creation, the owner's details are shown FROM the account, and the bulk import resolves the owner to a typed record instead of a silent free-text write | 2026-08-27 | **RELEASED 2026-08-27** — used **OQ-790** and **BR-MET-400 · 401 · 402**; migration **metering 0041**. **NO DEF WAS MINTED, which is the honest state for a lane whose whole job was three existing rows** (DEF-650 critical, DEF-1088 and DEF-1247 high) — minting a fourth to describe the same work would have made the register count one defect twice. The whole of DEF-1580–1609 is therefore UNUSED and free. ⚠ **AND `file_defect.py`'s allocation bug (DEF-1221) was never exercised**, for the same reason: nothing called it. A lane that DOES need an id from this block must still check what the tool hands it against this table before trusting it. |
| migration `metering 0041` | `premises_owners.master_account_id` — the one missing link the 2026-08-27 ruling names (*"the ONE MISSING LINK is `owner → master ACCOUNT`"*). `DEF-892`: ALLOCATED, never taken from the watermark. Depends on `metering 0040` (the real leaf — 0038 is unclaimed and 0040 already depends on 0039, so a second child of 0039 would make two leaves) and on `customers 0031` (the FK's target table must exist first on a fresh database) | 2026-08-27 | **ACTIVE** |
| migration `customers 0031` | SSN encryption (DEF-632) — the `service_requests.ssn` column. `DEF-892`: a migration number is ALLOCATED to a lane, never taken from the watermark. ⚠ **`0029` is deliberately NOT taken.** It is unclaimed, but `0030` already depends on `0028`, so a second child of `0028` would make two leaves and Django would demand a merge — `0030`'s own header says exactly this. `0031` depends on `0030`, the real leaf | 2026-08-27 | **ACTIVE** |
| DEF-1650–1689 · OQ-830–849 · BR-\<MOD\>-430–449 | **DEF-724 — the close-out act**: a cut customer reaches a terminal state through a separate `close_out` door (PO 2026-08-27). Used **BR-CUS-430, BR-CUS-431**; **OQ-830**; no DEF minted — DEF-724 is FIXED and DEF-701's customers half is unblocked | 2026-08-27 | **ACTIVE** |
| DEF-1780–1809 · OQ-860–869 · BR-\<MOD\>-460–469 | **`CR-046` wave H — write-back and version.** Used **DEF-1780** (G17 red: `CR-046` defined three rule ids twice) and **DEF-1781** (a signed rule's headline stated the opposite of the ruling in its own body). **No OQ minted.** ⚠ **THREE RULE IDS WERE ALLOCATED OUTSIDE THIS BLOCK ON PURPOSE AND THE REASON IS THIS FILE'S OWN RULE:** `BR-AST-051`, `BR-AST-052` and `BR-CUS-172` are **RENUMBERINGS of existing duplicate definitions**, not new rules, so each takes the next free number in the module namespace it already lives in — a renumbered rule pulled into a reservation block would be a third id for the same law. G17's banner is explicit that a duplicate is fixed by renumbering and never by a baseline entry | 2026-08-27 | **RELEASED 2026-08-27** |
| migration `customers 0035` | **CR-052 W0 task 1 — the cut records what it settled and what to restore.** ⚠ **THIS LANE ALLOCATED `0034` AND HAD TO RENUMBER AT PUSH TIME — `DEF-2711`.** The CR-052 W3/W4 lane took `0034` from its own worktree while this one was working, so both were correct and invisible to each other: `DEF-1787`'s mechanism exactly, one register along. Re-derived from the branch tip at push time and moved to `0035`, depending on `0034_cr052_delivery_election_and_template_override`, the real leaf. `disconnect_cases` gains `status_before_cut` (TEXT — the account status CODE held on the day of the cut, so `restore_service` can put it back; `OQ-1170`'s second half) and `outstanding_at_cut` (NUMERIC(18,4) — what was owed once the whole event had happened; **money 🔒**, CLAUDE.md rule 2). No backfill, no constraint moves, no ninth case state. `DEF-892`: a migration number is ALLOCATED to a lane, never taken from the watermark. Depends on **`customers 0034`**, the real leaf. ⚠ **`0029` is still deliberately NOT taken** — `0030` already depends on `0028`, so a second child of `0028` would make two leaves. **USED: `DEF-2708`** (the disconnection bill charges a full month's base for a part month, $40.00 where 18 of 31 days is $23.23, because metering publishes no `billing_period_for_unit`), **`DEF-2709`** (`test_br_cus_105_static_balance.py` RED on the tip since 2026-08-27 — its `CC-RECON` fixture has no GL account; FIXED here), **`DEF-2710`** (`test_w7_cut_reconnect.py`'s absence test RED on the tip — `new_service_block_for` gained a second caller and the test was not deleted; NOT this lane's). | 2026-08-31 | **ACTIVE** |
| migration `customers 0032` | **DEF-724 — the close-out act.** `disconnect_cases` gains `closed_out_on`, `closed_out_by` and `close_out_reason`; the `ck_disconnect_case_state` CHECK gains `closed_out`; `uq_one_open_disconnect_case_per_account` excludes it so `restart_after_closure` can open the BR-CUS-082 collections case beside it. `DEF-892`: ALLOCATED, never taken from the watermark. Depends on **`customers 0031`**, the real leaf. ⚠ **`0029` is still deliberately NOT taken** — `0030` already depends on `0028`, so a second child of `0028` would make two leaves | 2026-08-27 | **ACTIVE** |

| `DEF-2920–2949` · `OQ-1240–1249` · `BR-\<MOD\>-1020–1039` | **`CR-056` waves W2, W3 and W5 — identity on the customer, the link every door writes, and the customers screen.** ⚠ **RENUMBERED TWICE AT PUSH TIME, AND THE SECOND TIME IS THE INTERESTING ONE.** This lane and the `CR-056` W0/W1 lane both computed `max + 1` correctly, at the same moment, in separate worktrees, and both got `BR-CUS-1000/1001`, `BR-MET-1000` and migration `customers 0036` — `DEF-1787`'s mechanism exactly, since a sibling in its own worktree has rows in none of the refs the other can read. **Both lanes then re-derived at push time and both moved to the SAME next block, `BR-<MOD>-1010–1019`.** The rule this file states settled it: the earlier CITATION keeps the id, that lane pushed its rows first, so this lane moves again — to `BR-CUS-1020`, `BR-CUS-1021` and `BR-MET-1020`. **The lesson, for whoever meets this next: re-deriving from the tip is not enough on its own when two lanes re-derive in the same minute. Re-read the tip AFTER the refusal, not before it** — `push_paths.sh` refusing is the signal that the world moved, and the ids must be recomputed from the world it moved to. **USED: `BR-CUS-1020`** (identity lives on the customer, encrypted, and it is what makes `BR-CUS-089`'s signed criteria assessable), **`BR-CUS-1021`** (every door that opens an account writes the customer link, and a weak match refuses to link BY NAME), **`BR-MET-1020`** (a premises owner reaches the customer they are THROUGH their master account) and **`OQ-1240`** (is `premises_owners.customer_id` dropped, or kept as a dead column?). **NO DEF MINTED** — nothing was found broken that was not already filed, which is the honest state for a lane whose whole job was three waves of a CR. `DEF-2920–2949`, `OQ-1241–1249` and `BR-<MOD>-1022–1039` are UNUSED and free. | 2026-08-31 | **ACTIVE** |
| migration `customers 0036` | **`CR-056` W2 tasks 11 and 15** — `customers` gains a date of birth plus an app-layer-encrypted SSN, driving licence and phone, each with a keyed blind index beside it; `customer_accounts` gains `BR-CUS-089`'s four match columns. 🔒 HUMAN-OWNED (migration ordering AND app-layer encryption). `DEF-892`: a migration number is ALLOCATED to a lane, never taken from the watermark. Depends on **`customers 0035`**, the real leaf. ⚠ **`0029` is STILL deliberately not taken** — `0030` already depends on `0028`, so a second child of `0028` would make two leaves. ⚠ **`0036` WAS CONTESTED AND IS SETTLED:** the `CR-056` W0/W1 lane allocated `0036` for `accounts.premises_id` in its own worktree at the same time; this lane pushed first, that lane re-derived at push time and moved to `0037`, which depends on this one. The graph stays linear and `makemigrations --check` reports no changes. | 2026-08-31 | **ACTIVE** |

| `OQ-1241–1242` · `BR-CUS-1022` (from the `CR-056` W2/W3/W5 block, which released them) | **`CR-056` W2b — identity is per kind: a company is matched on its Tax ID.** The W2/W3/W5 row above states `OQ-1241–1249` and `BR-<MOD>-1022–1039` UNUSED AND FREE, so this wave takes the next ids inside the CR's own block rather than opening a new one — the same CR, the same namespace, one wave later. **USED: `BR-CUS-1022`** (identity is per kind; `BR-CUS-089` narrowed onto persons rather than reversed), **`OQ-1241`** (does a company get an incorporation date?), **`OQ-1242`** (is a sole trader a person or a company?) and **`DEF-2873`** (a master-account refusal with no sentence in any of the eleven catalogues — found by running `G32` over this lane's own three new keys, filed and fixed here because the eleven files were already open). ⚠ **`DEF-2873` IS OUTSIDE EVERY RESERVED BLOCK AND DELIBERATELY SO** — `file_defect.py` stepped DOWN below `2900-2919` and `2920-2949` because both are held by other CR-056 waves, which is this file's own rule for a lane filing against work that has already happened. ⚠ **AND IT WAS RE-DERIVED AT PUSH TIME AND MOVED: `DEF-2873` FIRST, THEN `DEF-2873`.** Between this lane's first allocation and its push a sibling pushed a row, the register moved, and the tool run again from the NEW tip returned a different number — the id had to be renumbered in the decision log before the push. That is law 11's clause working exactly as written: an allocated id is a blob too, and re-reading the tip AFTER the refusal is what caught it. **ALSO USED: `DEF-2870`** — the demo fixture will not load by its documented route on a database created today (`metering.cycle.code_duplicate` on the premises block; ten blocks fall with it and the tenant ends with 0 accounts and 0 customers). Observed, reproduced and filed UNDIAGNOSED; the browser proof opened its two rows through `create_account` instead. `OQ-1243–1249` and `BR-<MOD>-1023–1039` remain UNUSED and free. | 2026-09-01 | **ACTIVE** |
| migration `customers 0038` | **`CR-056` W2b — `customers.tax_id` plus `tax_id_bidx`**, an app-layer-encrypted company Tax ID with a keyed blind index beside it and one btree on `(tenant, tax_id_bidx)`. 🔒 HUMAN-OWNED (migration ordering AND app-layer encryption). No backfill and no key needed to run it: every existing row is NULL in both columns because the fact had nowhere to live. **NO UNIQUE INDEX**, and this time it is a PO ruling rather than a reconstruction — *a duplicate identifier refuses to LINK and never refuses to SAVE* (2026-09-01). `DEF-892`: a migration number is ALLOCATED to a lane, never taken from the watermark. Depends on **`customers 0037_cr056_w1_account_on_the_premises`**, the real leaf, and the number was re-derived from the branch tip at push time. ⚠ **`0029` is still deliberately NOT taken** — `0030` already depends on `0028`, so a second child of `0028` would make two leaves and Django would demand a merge migration. | 2026-09-01 | **ACTIVE** |

## What to do when a lane has already taken an id inside your block

**The earlier lane keeps it.** An id that is cited in committed code, in a test
name or in a rule row cannot move without breaking every one of those citations,
and the lane that has not started yet loses nothing by beginning one number
higher. Narrow the block here, say WHY in its State cell, and tell the lane —
all three of those, because a narrowing nobody is told about is the same failure
one turn later.

**Three id races happened on 2026-08-27 before this file could stop any of them**
— DEF-974 taken twice across branches (**DEF-977**), OQ-580 minted twice within
an hour for unrelated questions (renumbered at merge to OQ-532), and DEF-1000–1007
allocated into a block reserved after that lane was already running (**DEF-978**).
The first two were discovered at merge; the third was visible in advance, which is
the whole difference this file makes.

## The block a merge lane takes

The merge lane holds no standing block. It files against `max + 1` like anyone
else and, when that lands inside an ACTIVE block, it steps **down** into a free
id below the reserved range rather than up past it — a merge-lane defect is
almost always about work that has already happened, so it belongs beside it.
| DEF-2900–2919 · OQ-1230–1239 · BR-\<MOD\>-1010–1019 | **CR-056 waves W0 + W1 — the owner's account moves from a common-area UNIT to the ADDRESS.** W0 writes down the five rulings of the 2026-08-31 analysis session (one quoted, four reconstructed), stamps `BR-CUS-068` and the 2026-08-27 `OQ-500` ruling SUPERSEDED at the sentence, and raises what is still unruled. W1 adds `accounts.premises_id`, makes `accounts.unit_id` NULLABLE, backfills every existing row so no bill moves, and stops `create_master_account` refusing a premises with no common area. **The money that must not move: `1408 Elm Street` bills `$69.60`** — `$41.20` hallway + `$28.40` irrigation. Migration `customers 0037` is allocated in the row below. ⚠ **RE-DERIVED AT PUSH TIME AND RENUMBERED — the `CR-056` W2/W3 lane took `BR-CUS-1000`, `BR-CUS-1001`, `BR-MET-1000` and migration `customers 0036` from its own worktree while this one was working, so both lanes were correct and invisible to each other (`DEF-1787`'s mechanism).** `push_paths.sh` refusing a moved path is what caught it. **BR-\<MOD\>-1000–1009 is therefore NOT this lane's** — the block starts at 1010. **USED: `BR-CUS-1010`, `BR-CUS-1011`, `BR-CUS-1012`, `BR-MET-1010`, `BR-MET-1011`; `DEF-2902` and `DEF-2903`** (both PRE-EXISTING at the tip and measured on a clean detached worktree with none of this lane's files present — `master_account_for` answers `None` for every master account in the product, and `sub_accounts_for_master` raises instead of listing, because the geometric derivation was retired on 2026-08-27 and nothing writes the declared link). **No OQ minted.** `OQ-1230–1239` returns UNUSED: all nine of `CR-056`'s questions were ruled by 2026-09-01 and three drafted ids were withdrawn unwritten rather than raising questions the PO had already answered (law 13) | 2026-09-01 | **ACTIVE** |
| migration `customers 0037` | **CR-056 W1 task 5 — `accounts.premises_id` (a plain UUID, the `resolved_premises_id`/`template_override_id` posture) and `accounts.unit_id` made NULLABLE, plus the backfill that fills `premises_id` from each account's own unit so every existing Master Account bills exactly what it bills today.** Two CHECK constraints replace the NOT NULL the column loses: an account must name a unit or a premises, and a `regular` account must still name a unit. `DEF-892`: a migration number is ALLOCATED to a lane, never taken from the watermark. ⚠ **ALLOCATED AS `0036` AND RENUMBERED AT PUSH TIME (`DEF-2711`'s shape again): the `CR-056` W2/W3 lane took `0036` for `0036_cr056_w2_customer_identity` from its own worktree.** Depends on **`customers 0036_cr056_w2_customer_identity`**, the real leaf. ⚠ **`0029` is still deliberately NOT taken** — `0030` already depends on `0028`, so a second child of `0028` would make two leaves | 2026-09-01 | **ACTIVE** |
| migration `customers 0039` | **`DEF-2847` — `addresses` gains `line2` and `country`, both nullable, nothing backfilled.** ⚠ **ALLOCATED AS `0038` AND RENUMBERED AT PUSH TIME**, the third recorded instance of `DEF-1787`/`DEF-2711` on this table: the `CR-056` W2b lane took `0038` from its own worktree while this one was working, both lanes computed the next free number correctly, and both got the same one. Found by re-deriving the CONTENT and the IDS from the pinned tip in one act (law 11), which is the only thing that can see it. Now depends on `0038_cr056_w2b_company_tax_id`, the real leaf. | 2026-09-01 | **ACTIVE** — the defect lane (governance/platform/shell/notifications/customers batch) |
| `DEF-2960–2989` · `OQ-1243–1246` · `BR-\<MOD\>-1024–1029` | **`CR-056` waves W4 and W5 — no lines, no document; the silent owner account; the unoccupied unit that finds nobody; New Connect creating the premises.** Takes the next free ids inside `CR-056`'s own namespace rather than opening a new block, the way the W2b row did: the W2/W3/W5 row released `DEF-2920–2949`, `OQ-1241–1249` and `BR-\<MOD\>-1022–1039`, and since then `DEF-2920` (W2/W3/W5), `DEF-2921–2923` (a sibling lane), `OQ-1241–1242` and `BR-CUS-1022` (W2b) and `BR-CUS-1023` (W6) have been taken. **USED: `BR-BIL-1024`** (no lines, no document — decided after pricing), **`BR-BIL-1025`** (an account with nothing to bill is not an exception; an unoccupied unit nobody picks up still is), **`BR-MET-1024`** (New Connect may create the address it builds on). **`DEF-2960`** (an unoccupied unit whose base charge IS billed to the owner is reported as having no billable account) and **`DEF-2961`** (New Connect's commit manifest reports a premises it did not create). **No OQ minted** — every question `CR-056` W4 rests on was ruled on 2026-08-31 and re-asking one would be law 13's exact failure. `DEF-2962–2989`, `OQ-1243–1246` and `BR-\<MOD\>-1026–1029` remain UNUSED and free. ⚠ **THIS BLOCK WAS FIRST WRITTEN AS `DEF-2924–2949` AND MOVED BEFORE A SINGLE ID WAS TAKEN.** The `CR-056` W2/W3/W5 row states `DEF-2920–2949` and is still **ACTIVE**, so its PROSE releasing the unused tail and its RANGE disagree — and `file_defect.py` reads the range. It refused every id in the sub-block with *"every id in DEF-2924-2949 is taken"*, which is the allocator doing exactly its job: a range inside somebody else's live block is not free just because their sentence says the ids are. **Sub-letting a live block does not work; take a new one.** | 2026-09-01 | **ACTIVE** |

## `DEF-2962` — an addition to the `DEF-2960–2989` row above, written BELOW it on purpose

**`DEF-2962` is the third id used out of that block**, and it is recorded here rather than inside
the row because `push_paths.sh`'s register guard reads a MODIFIED line as a deleted one — and a
lane that reaches for `ALLOW_REGISTER_DELETIONS=1` to edit its own row is a lane that has taught
itself to reach for it. An append costs nothing and keeps the guard load-bearing.

**What it is:** this lane's OWN law-11 re-derivation of the defect register, done with Python's
`read_text()`, which normalises CRLF to LF — so a two-row APPEND was a whole-file rewrite of every
row a sibling had written with CRLF, and two of them (`DEF-2922`, `DEF-2923`) lost their carriage
returns. **What saw it, and it is the only thing that did:** the numstat printed after the push read
*4 insertions, 2 deletions* where a two-row append must read *2 insertions, 0 deletions*. The
register guard passed correctly — nothing VANISHED, two rows were MODIFIED, and it counts lost
lines. **Nothing was restored and nothing needed to be:** those rows' own lane had rewritten both of
them by the time this was seen, so putting the old bytes back would have reverted their edit, which
is the damage rather than the repair. **Prevention: `read_bytes`/`write_bytes` on every shared
register, never `read_text`.** `DEF-2963–2989` remain UNUSED and free.
| DEF-2950–2959 · OQ-1250–1259 · BR-\<MOD\>-1040–1049 | **`CR-056` wave W6 — the move-out story (tasks 26, 27, 28): a tenant leaves, the unit falls to the owner's account, and the settlement posts the shortfall instead of refusing.** The block is opened OUTSIDE the CR's earlier ranges on purpose: `DEF-2900–2919` (W0/W1) and `DEF-2920–2949` (W2/W3/W5) are both spoken for, and `OQ-1230–1239` was released UNUSED by the W0/W1 lane while `OQ-1241–1242` were taken by W2b — so the next unambiguous run is taken rather than a released one re-entered, which is what made `DEF-978` findable in advance. ⚠ **NARROWED FROM `DEF-2950–2969` AT PUSH TIME**: a sibling had already pushed `DEF-2960–2989` and used five of it, so the overlapping half goes to the lane that got there first — this file's own rule, *"the earlier lane keeps it"* — and re-deriving the ids from the pinned tip is what found it (`DEF-1787`'s mechanism, caught by the check law 11 prescribes). No id of this lane's moves: `2950`, `2951` and `2952` are outside the overlap. **USED: `DEF-2950`, `DEF-2951`, `DEF-2952`; `OQ-1250`; `BR-CUS-1040`.** `DEF-2953–2959`, `OQ-1251–1259` and `BR-\<MOD\>-1041–1049` are UNUSED and free. ⚠ **This lane touches NO migration** — nothing in W6 adds a column, so no migration number is allocated here and none should be read into this row. | 2026-09-01 | **ACTIVE** |

**⚠ `DEF-2963`, `DEF-2964` AND `DEF-2965` WERE TAKEN OUT OF THIS BLOCK BY OTHER LANES**, minutes after
it was reserved and before the reservation reached the tip they were reading — `DEF-1787`'s mechanism
again, one register along. Nothing is renumbered: the ids are cited in their own lanes' work and the
earlier citation keeps the id. **This lane's fourth id is therefore `DEF-2966`** (`CR-056`'s own
`1408 Elm` regression is RED at the tip because `R3,R4` are the shipped default and the fixture
declares no `is_base` charge code — measured on a clean worktree, not this lane's to fix). It was
allocated as `DEF-2963`, the allocator refused that number on the re-derivation, and the two documents
citing it were renumbered before the push — law 11's clause working exactly as written.
**`DEF-2967–2989` remain UNUSED and free.**
| `OQ-1252–1259` · `BR-CUS-1030–1039` · `BR-MET-1030–1039` | **`CR-058` W3 + W4 — the premises import creates an owner's account, and a transfer reassigns instead of recreating (tasks 10–19).** The block deliberately starts at 1030 rather than at `max + 1`: the sibling lane holding `CR-058` tasks 3–9 is working in its own worktree on `apps/customers/services.py` and the two wizards, and `DEF-1787`'s mechanism means neither lane can see the other's allocations until one pushes. `OQ-1243–1249` and `BR-<MOD>-1023–1029` are therefore left free FOR that lane, and this one steps clear rather than racing it for the next number. **USED: `OQ-1252`** (the outstanding balance at the moment of sale — raised OPEN at 2026-09-01 and **CLOSED by the PO within the hour**: *"money follow property"*, so task 18 is BUILT rather than stubbed), **`OQ-1253`** (must the BUYER be shown the debt they are taking on, and where — raised from the same ruling, which says where the money goes and nothing about who is told), **`BR-CUS-1030`** (a transfer REASSIGNS the account — SUPERSEDES the built behaviour at its own sentence), **`BR-CUS-1031`** (a customer MOVING is a new Service Request, not a transfer), **`BR-CUS-1032`** (the new-request door creates a numbered request and nothing else, pinned), **`BR-MET-1030`** (the premises import's owner identity columns and the conditional master account), **`BR-MET-1031`** (the units import creates units and nothing else, pinned by a test). `OQ-1252–1259`, `BR-CUS-1033–1039` and `BR-MET-1032–1039` remain UNUSED and free. ⚠ **Re-derived from the pinned tip at push time (law 11's id clause), because a register read from a local checkout cannot see a sibling's unpushed rows.** | 2026-09-01 | **ACTIVE** |
| BR-CUS-1024 · `DEF-2587` | **`CR-058` wave W1 + W2 — match first, create second, never a duplicate, and both counter screens say which happened.** Tasks 3–9: one `resolve_customer_for_account(...)` every account door calls, wired into `POST /accounts`, `POST /accounts/master` and `POST /accounts/{id}/move-in`, then `NewAccountWizard` and `MoveInWizard` showing the clerk whether the customer was linked, created, or not created and why. **The measured figure this lane exists to move: a landlord at three buildings giving a name and a Social Security number and no date of birth got `C-00001`, `C-00002` and `C-00003` — three customer numbers over one Social Security number (`DEF-2587`). After it, ONE.** **USED: `BR-CUS-1024`** (an exact agreement on the name and one government identifier REUSES the number already on file; a phone does not, ambiguity does not, and a reuse records no tier so **$0.00** of anybody's deposit moves) and **`DEF-2587`**. **No OQ minted** — `CR-058` task 2's three questions are another lane's to raise and this lane answered none of them by inference (law 13). ⚠ **`DEF-2587` was allocated by `10-scripts/file_defect.py` against the tip and re-derived at push time**, because two lanes took the same defect id on 2026-08-27 and the allocator can only see the pushed world plus its own checkout. |
| `DEF-2990–2999` · `BR-MET-1032` | **`BR-MET-1032` — an uploaded spreadsheet stops keeping Social Security numbers in plain text while it waits to be committed, and the checking screen stops showing them back. Both import doors.** `BR-MET-1032` is taken out of the `BR-MET-1032–1039` range the `CR-058` W3+W4 row above declares UNUSED and free, which is what that row invites; it is recorded here so the next reader does not have to infer it from a prose sentence in somebody else's row. **The `DEF-` block deliberately opens at 2990 rather than at `max + 1`:** `DEF-2950–2989` is spoken for by two sibling lanes and has already been renumbered twice today under `DEF-1787`'s mechanism (a sibling in its own worktree has rows in none of the refs this one can read), so this lane steps clear rather than racing for the next number. **USED: `BR-MET-1032`** (an identity cell is encrypted with its blind index the moment it is staged, and the checking screen shows the last four — while the file an operator sends is unchanged and carries the whole number) and **`DEF-2990`** (the new `import_identity.py` declares `HUMAN-REVIEW-PENDING` and no `human_owned.txt` glob matches it, so `G7` does not watch it — G53 says so and **a lane may not fix it**: adding a glob is a PROCESS EVENT and the PO's call, `OQ-441`). **No `OQ` minted** — the four judgments this lane met were decided and written into the decision log rather than put back to the PO (law 13). `DEF-2991–2999` and `BR-MET-1033–1039` remain UNUSED and free. ⚠ **Re-derived from the pinned tip at push time** (law 11's id clause). | 2026-09-01 | **ACTIVE** |
| `DEF-3120–3149` · `OQ-1300–1309` · `BR-\<MOD\>-1120–1139` | **`CR-059` W11 — the write-off lane (tasks 62 and 64): reject and reverse a write-off, and report bad debt.** Opens at 3120 rather than at `max + 1` (3032) because the `CR-059` W3 doors lane holds `DEF-3030–3059` and **three sibling lanes are in `apps/payments` in their own worktrees right now** — deposit release, the reversal/refund screens, and bank reconciliation — none of which this one can see until they push (`DEF-1787`'s mechanism). **The full detail, including which ids are USED and why migration `payments 0011` is allocated here, is the section at the end of this file**, written there on the `DEF-2991` precedent because the tables are edited by several lanes at once. | 2026-09-01 | **ACTIVE** |
| `DEF-3230–3249` · `BR-\<MOD\>-1180–1199` | **The billing-basis lane (`DEF-2409`) — a service declares ONE of THREE billing bases, and all ten get the PO's ruled seed.** PO ruling 2026-09-02: *"Shall we consider Metered, % of service and Capacity based"*, with a ten-row table signed cell by cell. Replaces `tenant_services.metered` (a boolean carrying three cases) with `billing_basis`, rewrites `SERVICE_DEFAULT_UOMS` to carry all ten services and their basis, and adds `panel` — the one unit the platform catalogue was missing. **The full detail is the section at the end of this file**, written there on the `DEF-2991` / `DEF-3120` precedent because the tables are edited by several lanes at once. ⚠ **DRAFTED AS `DEF-3210–3229` AND RENUMBERED BEFORE A SINGLE ID WAS TAKEN.** `DEF-3200–3219` is held by the payments-corrections lane and is **ACTIVE**; its prose releases `DEF-3202–3219` as *UNUSED and free*, and this file's own `DEF-2960` lesson says that does not make them takeable — **sub-letting a live block does not work; take a new one.** So this block opens above every high watermark in the file rather than inside somebody else's range. Migration `tenancy 0030` is allocated here. | 2026-09-02 | **ACTIVE** |
| `DEF-3260–3279` | **`CR-062` group C + H1 — every metered service a utility sells gets its own meters, readings and bill lines (PO statement (8), 2026-09-02).** The seeded estate planted ONE meter per unit and refused every later metered service by name, so a utility selling Electric + Water + Sewer received water and sewer and **no electric line on any of its 95 bills** — not even the signed `$12.00` monthly base, which is `$576.00` a month across 48 homes. ⚠ **THE BLOCK OPENS AT 3260, ABOVE EVERY WATERMARK IN THIS FILE, AND THAT IS `DEF-1787` AVOIDED RATHER THAN SUFFERED.** `file_defect.py` stepped DOWN to `DEF-3093` because 3094 upwards is inside other lanes' ACTIVE blocks — and `DEF-3093` had ALREADY been taken by the `CR-063` fire lane working in its own worktree, whose row is in none of the refs this checkout can read. Both allocators were correct and neither could see the other; a new block above everything is the only answer that does not race. Sub-letting a live block does not work either — this file's own `DEF-2960` lesson. **USED: `DEF-3260`** (the second metered service's July and August walks refused as a register rollback, because `_register_value`'s case-3 replacement discount was applied to a meter that was never replaced — found by running the new regression on real PostgreSQL 16, fixed in the same lane). **No `OQ` and no `BR-` id minted:** `BR-MET-143` is AMENDED in place with its date and its supersedes chain, which is what the change process asks for when a reading of an existing rule moves rather than a new rule arriving; and every judgment this lane met was decided and written into the decision log rather than put back to the PO (law 13). `DEF-3261–3279` remain UNUSED and free. ⚠ **Re-derived from the pinned tip at push time** (law 11's id clause). | 2026-09-02 | **ACTIVE** |
| `DEF-3360–3379` · `OQ-1410–1419` | **`CR-061` STATEMENT (1) — MORE GL CODES AND MORE CATEGORIES (PO ruling 2026-09-01, *"actually you need more GL code s and categories, I tried to assigned using existing code, they are not sufficiencnt"*; completed 2026-09-02 on *"complete 61 based on actual code"*).** A fresh utility's chart goes from **58 accounts to 125**: `chart.UTILITY_BOOKS_CHART`'s 67 rows for the half of a utility's books this product never posts — plant, construction in progress, accumulated depreciation, payables, debt, grants, interfund transfers, net position, petty cash and the clearing accounts — plus `chart.CHART_CATEGORIES`, eighteen headings, and one nullable `ledger_accounts.category` column (`ledger/0013`). **Every one of the 67 is `signed=False`** and lands in a THIRD register, `PENDING_FINANCE_RE_SIGN_BOOKS`: the PO ruled the CODES into existence and that is not a finance signature. ⚠ **THE BLOCK OPENS AT 3360 / 1410, ABOVE EVERY WATERMARK IN THIS FILE, AND IT IS `DEF-1787` SUFFERED AND THEN AVOIDED.** This lane first allocated through `file_defect.py`, which stepped DOWN past six held blocks and landed on **`DEF-2368`** — and by push time a sibling working in its own worktree had already taken that number and pushed it. Both allocators were correct and neither could see the other; the collision was caught by re-reading the register FROM THE PINNED TIP before pushing a single byte, which is the only thing that could have caught it. Sub-letting a live block does not work either — this file's own `DEF-2960` lesson. **USED: `DEF-3360`** (two chart guards pin the pending-signature list to a single code and had been red since `CR-063` landed that morning — FILED, then FIXED in the same lane by making them ask the question instead of pinning the answer) ⚠ **`DEF-3361` WAS DRAFTED FOR THE CONTRA-REVENUE LABEL, RELEASED, AND THEN TAKEN FOR SOMETHING ELSE — READ IT AS THE SECOND THING.** The label defect ALREADY EXISTED as **`DEF-3061`**, filed by the `CR-061` contra-revenue lane on 2026-09-01 at the moment it created the value; a second id for one defect reads as a register and not as an error, so `DEF-3061` is CLOSED by this lane instead and the fix is held by a case in `ledgerAdmin.test.tsx` proved RED first. **`DEF-3361` NOW CARRIES THIS LANE'S OWN REVERT BY SUBTRACTION:** `endpoints.ts` was pushed from a blob read at an earlier sync while DECLARING a later base, and 51 lines of a sibling's `CR-059` and `CR-060` API types left the branch. **A base you did not actually edit from is a base the push helper cannot check**, and every law-11 check passed on it — the numstat's 53 deletions was the only signal. Repaired in the next commit from the reverted content, verified by subtraction. **No `OQ` minted and none needed:** every judgment this lane met was decided and written into `02-decision-log.md` rather than put back to the PO (law 13), and `OQ-1343` (is an impact fee revenue at all) stays OPEN and untouched. `DEF-3362–3379` and `OQ-1410–1419` remain UNUSED and free. ⚠ **Re-derived from the pinned tip at push time** (law 11's id clause) — this lane works in its own `git worktree`, which is exactly the case `DEF-1787` describes. | 2026-09-02 | **ACTIVE** |
| `DEF-3440–3459` · `OQ-1420–1429` | **`CR-060` T6(e) — the *Paid on* field, so the core change of this change request can be reached by a person.** T6 landed the column, the posting and the route on 2026-09-02 and said so in writing: *"(e) THE SCREEN — NOT LANDED"*, with seven catalogue strings *"reported to the caller rather than written here"*. So the books move only for a caller with an HTTP client, and hard-won law 2 is OPEN on the row that carries this CR's whole argument. ⚠ **THE BLOCK OPENS AT 3440 / 1420, ABOVE EVERY WATERMARK IN THE REGISTER, RATHER THAN AT `max + 1`.** `file_defect.py` stepped DOWN past eleven held blocks and offered `DEF-2363` — a four-digit id a thousand below the live frontier, inside no reservation and therefore inside nobody's promise, which is exactly the shape `DEF-1787` turns into a collision. Sub-letting a live block does not work either (`DEF-2960`). This lane works in its own `git worktree`, so a sibling's rows are in none of the refs this checkout can read, and every id is re-derived from the pinned tip at push time (law 11's id clause). | 2026-09-03 | **ACTIVE** |


## `DEF-2991` — an addition to the `DEF-2990–2999` row above, written BELOW it on purpose

**`DEF-2991` is the second id used out of that block**, and it is recorded here rather than inside the row for the reason the `DEF-2962` note four rows up already gives: `push_paths.sh`'s register guard reads a MODIFIED line as a deleted one, and a lane that reaches for `ALLOW_REGISTER_DELETIONS=1` to edit its own row is a lane that has taught itself to reach for it. **This was learned the hard way in the same hour: the edit was made in place, the guard REFUSED the push by name, and the row was rebuilt as this append instead.** The guard was right and the note above it was already written.

**What it is:** this lane's own block replacement in `_failures_csv` dropped the `yield` that writes the failures download's HEADER ROW, so the operator's own file came back with every column unlabelled. **What found it, and it is the only thing that did:** law 11's post-push check read as arithmetic — `git show <commit>` listed `yield _csv_line([*headers, FAILURE_REASON_COLUMN, FAILURE_FIX_COLUMN])` among the deleted lines and nothing had re-added it. Every other check in that law passed on it. **The lane's own new test passed on it too**, because it asserted the Social Security number was IN the downloaded file and never that the file had a SHAPE — a content assertion cannot see a missing header. `DEF-2992–2999` remain UNUSED and free.


## `DEF-3120–3149` · `OQ-1300–1309` · `BR-<MOD>-1120–1139` — `CR-059` W11, the write-off lane (tasks 62 and 64)

Written as its own section rather than as a table row, on the `DEF-2991` precedent immediately
above: the tables are edited by several lanes at once and an appended SECTION collides with
nothing.

**The block: `DEF-3120–3149` · `OQ-1300–1309` · `BR-<MOD>-1120–1139`. Opened 2026-09-01, ACTIVE.**

**`CR-059` CS-25 (task 62) and CS-26 (task 64) — reject and reverse a write-off, and report bad
debt.** Widens the write-off status set from two values to four, adds the reject and reverse
services with their two doors, and adds the bad-debt read behind `GET /bad-debt`.

**The block deliberately opens at 3120 rather than at `max + 1` (which is 3032 today).** The
`CR-059` W3 doors lane holds `DEF-3030–3059` · `OQ-1270–1279` · `BR-<MOD>-1070–1089`, and **three
sibling lanes are working in `apps/payments` in their own worktrees right now** — deposit release,
the reversal/refund screens, and bank reconciliation. `DEF-1787`'s mechanism means none of them can
see another's allocations until one pushes, and that row records the same lane renumbering 37
citations after a collision. Stepping clear by a wide margin costs nothing and is what this file
exists to make possible.

**USED:**
* **`BR-PAY-1120`** — a write-off has four states; `rejected` is a status move on a row that posted
  nothing, `reversed` is a NEW ROW because the row it corrects did post, three states are terminal,
  both new acts are Admin-only with the gate on the service, and the debt returns at its ORIGINAL
  age (measured: 91 days late, 90+ bucket, before the write-off, after the approval and after the
  reversal).
* **`DEF-3120`** — payments migration 0010's freeze comment claims deny-by-default (*"a column added
  to this table LATER is frozen the day it exists"*) and the trigger underneath it is a
  frozen-COLUMN-LIST, so every column added after 2026-08-15 was silently mutable. FIXED in
  migration 0011, which replaces the function with the `refunds` shape it always claimed to be.
* **`DEF-3121`** — an approved write-off reduces receivables in the LEDGER and does not remove the
  debt from Outstandings or from the collection ladder, because nothing on that path writes an
  allocation row. Measured on US-PAY-012 TC-2's own figure: **948.20 owed at 91 days late before the
  write-off, and 948.20 owed at 91 days late after it**, while the ledger has credited AR by 948.20.
  FILED, NOT FIXED — closing it writes money onto the allocation path, which is not this task's.
* **`OQ-1300`** — how is a written-off balance attributed across the services an account takes?
  `CS-26`'s *why* names *"by reason, by month and by service"* and its deliverable names only the
  first two; nothing in the product attributes a write-off across electric, water and gas, and
  choosing an attribution moves every service's revenue line. RAISED, not answered; the report says
  so by name on every result.

* **`DEF-3122`** — the new `apps/payments/bad_debt.py` declares `HUMAN-OWNED` /
  `HUMAN-REVIEW-PENDING` and no glob in `human_owned.txt` matches it, so `G7` does not watch it.
  **A lane may not fix that** — adding a glob is a PROCESS EVENT and the PO's call (`OQ-441`), the
  `DEF-2990` precedent exactly — so it is filed. A review-ledger row IS open for the file.
* **`DEF-3123`** — the finance write-off queue renders **Approve** on every row that is not already
  approved, so with the four-state set it offers Approve on a `rejected` and on a `reversed` row and
  the click returns a red error on a control the screen offered. Filed, NOT fixed: the screens are
  task 63's. Two more on-screen sentences go with it — `payments.writeOffQueue.approveWarning`
  (*"This is not easily undone"*, **eleven languages**) and the page's own
  *"the two this product has"* comment.
* **`DEF-3124`** — the *write-offs YTD* KPI on S32/S36 summed `approved` only, so a reversed
  write-off would have kept inflating it (**948.20** on the KPI against **0.00** on the new bad-debt
  report, adjacent screens, same fact). **FIXED in the same commit by deleting the second
  implementation**: `summary.py` now reads `bad_debt.counted_row_totals`.

**`DEF-3125–3149`, `OQ-1301–1309` and `BR-<MOD>-1121–1139` remain UNUSED and free.**

**Migration `payments 0011`** is allocated to this lane (`DEF-892`: a migration number is ALLOCATED
to a lane, never taken from the watermark). It depends on **`payments 0010_rls_writeoffs_and_intents`**,
the real leaf — `payments` has ten migrations and 0010 is the only leaf, so there is no second-child
hazard here of the kind `customers 0029` records.

⚠ **Every id above is re-derived from the pinned tip at push time** (law 11's id clause), because a
register read from a private worktree cannot see a sibling's unpushed rows.

## `DEF-3150–3179` · `OQ-1320–1329` · `BR-<MOD>-1140–1159` — `CR-059` W10, the collections-schedule lane (tasks 54 and 13)

Written as its own section rather than as a table row, on the `DEF-2991` and `DEF-3120`
precedents immediately above: the tables are edited by several lanes at once and an appended
SECTION collides with nothing.

**The block: `DEF-3150–3179` · `OQ-1320–1329` · `BR-<MOD>-1140–1159`. Opened 2026-09-02, ACTIVE.**

**`CR-059` CS-10 (task 54) — the collection ladder runs on a schedule, on the utility's own
business day — and CS-19 (task 13) — billing's issue path satisfies the first bill's deposit
line.** Adds `apps/payments/collections_schedule.py` and two S70 parameters; changes
`ladder.decide` for the same-day guard; adds no table and no migration.

**The block opens at 3150 rather than at `max + 1` (3125 today) for the reason `DEF-3120`'s
section gives:** the `CR-059` W11 write-off lane holds `DEF-3120–3149` · `OQ-1300–1309`, and
several sibling lanes are working in `apps/payments` in their own worktrees right now.
`DEF-1787`'s mechanism means none of them can see another's allocations until one pushes.
Stepping clear by a margin costs nothing.

**USED:**
* **`DEF-3150`** — *one step per account per PASS is not one step per account per DAY.* Every
  rung's due date is derived from the oldest unpaid bill alone, so on an account 62 days overdue
  all four rungs are past due at once and four passes on ONE `as_of` take four steps — reminder,
  10-day, 5-day and the ~$8.00 certified final, in one afternoon. Reachable today by pressing the
  Outstandings bulk action four times, and routine the moment a scheduler exists
  (`CELERY_TASK_ACKS_LATE` is on, so a re-delivered message IS a second pass). **FIXED** in
  `ladder.decide` (`SKIP_ALREADY_NOTICED_TODAY`), read from the same `last_notice_on` the manual
  S35 modal writes, so a clerk's letter and the job's letter count as one.
* **`DEF-3151`** — BR-PAY-016's partial-payment pause has NEVER fired. `run_ladder` takes the
  figure through `recent_payments` and **no caller in this repository supplies it** — not the new
  schedule and not `POST /collections/run`, which is the only thing that has ever advanced the
  ladder. One of the five recorded stop conditions stops nothing. **FILED, NOT FIXED:** closing it
  needs `OQ-1320` answered first. Carried on every scheduled result as
  `partial_payment_pause_not_supplied`.
* **`DEF-3152`** — `apps/payments/credit.deposit_payments_for_account` carries *"⚠ NOTHING CALLS
  IT"* on its own docstring and billing has called it through `billing/payments_seam` since
  2026-08-15. The seam resolves BY NAME at call time, so a grep for a caller finds nothing — and
  **`CR-059` CS-19 was specified from that sentence** (*"Payments publishes the figure; billing
  never asks for it"*), which dispatched a lane at work already shipped. **FIXED** — the docstring
  now names its caller, and a test asserts the contract from both ends.
* **`DEF-3153`** — `apps/billing/api.py`'s S30 comment says a one-time run *"is refused there
  today, by `issue.derive_due_date`"* and cites **OQ-241** as an open question. OQ-241 was CLOSED
  by the PO on 2026-08-23 (CR-029 D8③) and RC-W2-T4 built the fix; a cycle-less bill has issued
  since. **FIXED** — the comment is corrected rather than deleted, so a reader can see what
  happened to the old behaviour.
* **`DEF-3154`** — S34 prints *"Nothing runs the collection sequence overnight. It only moves when
  someone asks it to from this screen."* in **eleven locale files**
  (`payments.problem.no_scheduled_caller`). With CS-10 landed that sentence is false for a utility
  that has switched the schedule on, on a deployment where beat runs. The BACKEND half is done —
  `ladder.ladder_problems()` withdraws the entry exactly where it is false and keeps it everywhere
  else — but the panel CS-10 asks for (*when it last ran, what it did, when it runs next*) does
  not exist. **FILED, NOT FIXED: the screens are `CR-059` task 55's.**
* **`OQ-1320`** — a partial payment pauses the ladder above the utility's percentage; over WHAT
  WINDOW is a payment counted? Three defensible readings give three different answers on the PO's
  own $150-against-$948 case, and the spread is a disconnection notice sent or not sent. RAISED,
  not answered; `DEF-3151` is blocked on it.
* **`OQ-1321`** — where does the record of a collections RUN live? Three of CS-10's four S34 facts
  are derivable and are published; *when it last ran* and *what it did* are held by nothing.
  RAISED; the table belongs with task 55's panel, and building it here would be a table with no
  reader.

**NO MIGRATION IS ALLOCATED TO THIS LANE.** The two new settings live in the existing
`tenant_settings.collections` document, which `settings_families.merge` fills from the ratified
default for any tenant whose stored document predates them — so no column, no backfill and no
migration number is taken. `payments` still has ten migrations plus `0011` (the W11 lane's), and
this lane adds no second leaf.

* **`DEF-3155`** — ⚠ **PRE-EXISTING AND MEASURED, NOT THIS LANE'S.**
  `tests/test_us_bil_010_first_bill.py` — the suite covering `BR-BIL-012`'s deposit and
  connection charge — is **10 failed / 1 passed at the pinned tip `99c0d4fb`**, measured on a
  detached worktree with none of this lane's files present. `CR-057` defaulted
  `SBH_BILLING_RESOLUTION_STEPS` to `R3,R4` on 2026-09-01, so the ruled chain prices every
  account's base charge, and `tests/test_us_bil_001_prepare.a_priced_plan` writes a tariff
  version and one open-ended tier and **no `rate_size_rows` row** — so R3 refuses by name
  (*"connection size 'E-1P-100' has no row on the rate schedule version … pricing
  'electric'"*) for every case that builds a bill. **`DEF-2799`'s exact shape one fixture
  over**, where it was measured as *"47 of 47 refused at R3"* and fixed for the SAMPLE tenant
  only. FILED, NOT FIXED: `a_priced_plan` is imported by many suites and the same absent fact
  may be missing from other fixtures that no longer run — that is the owning lane's measure to
  take, not a change to make in passing. This lane's own CS-19 cases supply the missing size
  row for themselves and say why in the helper.

* **`DEF-3157`** — ⚠ **PRE-EXISTING AND MEASURED, NOT THIS LANE'S.**
  `tests/test_oq366_ladder_follows_the_master.py` TC-2 and TC-3 — the cases about WHICH
  account a collection sequence chases when a residue is tied back to a master — are red at
  the pinned tip: **2 failed / 3 passed**, identical on a detached worktree with none of this
  lane's files present. Commit `6c722aeb` (2026-09-01, *"no account without an ID"*) required
  an identity kind on account creation and their fixture builds one without, so both fail in
  SETUP with `BIZ-COMPLETENESS customers.account.identity_kind_required` before reaching a
  single ladder assertion. **Same shape and same day as `DEF-3155`, different cause** — a
  correct rule landing without a measure of which fixtures it invalidates. FILED, NOT FIXED:
  the fixture belongs to the lane that owns the master-account work.

⚠ **`DEF-3156` WENT TO A SIBLING AND IS NOT THIS LANE'S.** The `DEF-2396` service-estate lane
filed it inside this block while this lane was allocating — `file_defect.py` fetched the
remote, saw the row and stepped to `DEF-3157`, which is the allocator doing exactly its job
(`DEF-1787`'s mechanism, caught rather than collided with). This file's own rule settles it:
**the earlier lane keeps it.**

**`DEF-3158–3179`, `OQ-1322–1329` and `BR-<MOD>-1140–1159` remain UNUSED and free.**

⚠ **Every id above is re-derived from the pinned tip at push time** (law 11's id clause), because
a register read from a private worktree cannot see a sibling's unpushed rows.

## `DEF-3230–3249` · `BR-<MOD>-1180–1199` — the billing-basis lane (`DEF-2409`, the PO's ten-service seed ruling)

Written as its own appended SECTION as well as a table row, on the `DEF-2991` / `DEF-3120` /
`DEF-3150` precedents above: the tables are edited by several lanes at once and an appended
section collides with nothing, while the ROW is the only thing `file_defect.py` can read.

**The block: `DEF-3230–3249` · `BR-<MOD>-1180–1199`. Opened 2026-09-02, ACTIVE.**

**The work.** The PO ruled on 2026-09-02 that a service is one of THREE things — metered, a
percentage of another service, or capacity-based — and signed a ten-row table of the seeded
default for every service. `tenant_services.metered` is a BOOLEAN and cannot say it. This lane
replaces the column with `billing_basis`, rewrites `SERVICE_DEFAULT_UOMS` to carry all ten
services with their basis and units, adds the one missing unit (`panel`, scoped to solar), and
migrates every existing row.

⚠ **DRAFTED AS `DEF-3210–3229` AND RENUMBERED BEFORE A SINGLE ID WAS TAKEN — law 11's id clause
working, and the second thing it caught is worth more than the first.** The block was chosen from
a register read minutes earlier and `DEF-3200–3219` had landed in between, held by the
payments-corrections lane and **ACTIVE**. Its prose releases `DEF-3202–3219` as *UNUSED and free*,
and this file's own `DEF-2960` lesson settles that: **sub-letting a live block does not work; take
a new one.** So the block moved above every high watermark in the file.

⚠ **AND THE FIRST ATTEMPT AT THE TABLE ROW WAS UNREADABLE TO THE ALLOCATOR, WHICH IS A HAZARD
WORTH LEAVING WRITTEN DOWN.** The row's prose contained a literal `|` inside backticks. Markdown
renders that fine and a human reads the row correctly, but `reserved_blocks()` splits every line
on `|` and reads the FOURTH cell as the state — so a stray pipe silently shifts the state cell,
the row parses as a four-cell row whose state is a DATE, and **the block is invisible to
`file_defect.py` while looking perfectly reserved to every person.** `--block` refusing is what
found it. **A reservation row must contain no pipe of its own.**

**USED:**
* **`BR-TEN-1180`** — a tenant service declares ONE of three billing bases, and the platform seeds
  the ruled default for all ten services. SUPERSEDES `BR-RAT-081`'s two-state declaration at its
  own sentence.
* **`DEF-3230`** — seven of the ten services ship with a seeded unit that cannot produce a
  bill. **FIXED** in this lane.
* **`DEF-3231`** — the sample estate plants a storm-water METER and three months of readings
  for a service the same ruling calls capacity-based, so the demo tenant contradicts its own
  declaration. **FILED, NOT FIXED:** the fix changes what a demo storm-water tenant receives
  and the money does not move today (the usage line is `$0.00` on both paths), so it is a
  judgment for whoever owns `core/sample_fixture.py` rather than a correction this lane may
  make on the way past.

**NO `OQ` IS MINTED.** Every judgment this lane met — broadband's unit, the enum's storage type,
what `unmetered_service_codes()` should ask for — was decided and written into the decision log
rather than put back to the PO (law 13). `DEF-3231–3249` and `BR-<MOD>-1181–1199` remain UNUSED
and free.

⚠ **AMENDED 2026-09-02 BY THE LANE THAT PICKED UP THIS BLOCK'S HANDOVERS.** The paragraph above
said `DEF-3231–3249` were free while `DEF-3232` and `DEF-3233` had already been filed from this
block the same day — a register row going stale within hours of being written, which is what the
ACTIVE state is for. What is USED, corrected:

* **`DEF-3231`** — the storm-water meter the estate plants for a capacity service. FILED, still
  open, still the call of whoever owns `core/sample_fixture.py`.
* **`DEF-3232`** — sewer has no unit and both halves of Settings refuse to save it. **FIXED**
  2026-09-02 by the artifacts lane, which also took **`BR-TEN-1181`** (the primary unit is
  required for `metered` and `capacity` and REFUSED for `share`, narrowing `US-TEN-008` TC-5).
  Sub-letting a live block is what this file warns against, and it was taken anyway for one
  reason worth stating: `DEF-3232` was ALREADY in this block and `BR-TEN-1181` is the rule that
  closes it, so putting the rule in another block would separate a defect from its own fix.
  The `DEF-2960` lesson still stands for anything that is not a direct continuation.
* **`DEF-3233`** — `ALLOW_REGISTER_DELETIONS` became a habit rather than a decision. Filed by the
  billing-basis lane against itself, still open.

`DEF-3234–3249` and `BR-<MOD>-1182–1199` remain UNUSED and free. ⚠ **This list was re-read from
`10-defect-log.csv` rather than from the sentence above it**, which is the only way to write it
correctly: the prose in this file is a snapshot and the register is the fact.

**Migrations `tenancy 0030`, `0031` AND `0032` are allocated to this lane.** `DEF-892`: a
migration number is ALLOCATED, never taken from the watermark. `0030` depends on
**`0029_cr060_t2_organisation_type`**, the real leaf; `0031` on `0030`; `0032` on `0031`. ⚠ `0023`
and `0024` are deliberately NOT taken — `0025` already depends on `0022`, so a second child of
`0022` would make two leaves and Django would demand a merge migration.

⚠ **THIS SECTION CLAIMED ONE MIGRATION NUMBER UNTIL POSTGRESQL SAID OTHERWISE, AND THE REASON IS
WORTH INHERITING.** The change was written as a single atomic migration — `AddField` →
`RunPython` backfill → `RemoveField` — and it **passed the entire test suite**. On a real
PostgreSQL 16.13 with three rows planted in `tenant_services` it failed with *"cannot ALTER TABLE
\"tenant_services\" because it has pending trigger events"*: the table's seven FKs are
`DEFERRABLE INITIALLY DEFERRED`, so updating rows queues trigger events that are not flushed until
COMMIT, and PostgreSQL will not ALTER a table while any are outstanding. `config/settings/test.py`
hardcodes in-memory SQLite, which has no such state (CLAUDE.md law 14).

**So the rule is: a migration is EITHER schema or data, never both, on any table whose rows it
touches** — and it holds in REVERSE too, which is why three migrations rather than two. `0030`
adds, `0031` fills, `0032` drops. All three docstrings say so, because the obvious tidy-up is to
merge them back.

⚠ **Every id above is re-derived from the pinned tip at push time** (law 11's id clause), because
a register read from a private worktree cannot see a sibling's unpushed rows.

## `DEF-3280–3299` · `OQ-1370–1379` — the `CR-064` lane (the seventeen seeding steps on the sign-up screen)

**The block: `DEF-3280–3299` · `OQ-1370–1379`. Opened 2026-09-02, CLOSED the same day.**

Written here on the `DEF-2991` / `DEF-3120` precedent rather than edited into the table row above,
because that row is one line in a register several lanes write at once and an in-place edit of a
register line is a deletion — which is the thing `push_register_guard.py` exists to refuse.

⚠ **THE BLOCK EXISTS BECAUSE `CR-064` WAS WRITTEN WITH TWO IDS THAT WERE ALREADY TAKEN, WHICH IS
`DEF-1787` HAPPENING AGAIN.** The CR named `DEF-3221` for the dropped-`checkpoint` defect and
`OQ-1341` for the reload question. `DEF-3221` had been filed that same morning by the red-tip lane
(a billing refusal, unrelated), and `OQ-1341` sits inside `DEF-3200–3219` · `OQ-1340–1349`, another
lane's **ACTIVE** block — and this file's own `DEF-2960` lesson is that a live block may not be
sub-let, however much of it its prose releases. Both allocators were correct and neither could see
the other. The build lane opened this block above every watermark in the file instead of racing, and
**left the CR's original numbers standing, stamped in place**, rather than rewriting lines a reader
may already have quoted.

**USED — all four, and nothing else:**

* **`DEF-3280`** — the plant job has recorded the label of the block it just finished since
  2026-08-19 and `job_poll` served six keys and not that one, so the poll could answer *"11 of 17"*
  and never *"Meter reads"*. **FIXED** in the same lane (`CR-064` task A2), with a test that goes red
  the moment the key is dropped again.
* **`DEF-3281`** — the lane's own, self-reported minutes after it happened: a pathspec commit that
  named `apps/tenancy/services.py` for thirteen lines carried **125 lines of the `CR-066` lane's
  uncommitted work** with it and left the branch red for tenant creation. **REPAIRED** the same hour
  by re-deriving the file from the pre-commit tip plus this lane's own hunk and pushing it through
  `commit-tree`, which touched no file on disk — so the `CR-066` lane lost nothing and will commit
  all of it itself.
* **`OQ-1370`** — may the sign-up route rebuild the seventeen steps from `sample_data_runs` when the
  operator reloads mid-plant? MINTED, not answered. Non-blocking.
* **`OQ-1371`** — should `push_paths.sh` refuse a path whose working-tree diff carries hunks the
  pushing lane did not write? MINTED from `DEF-3281`, not answered. Non-blocking, and a tooling
  question rather than a product one.

**No `BR-` id was minted.** Nothing in `CR-064` changes a rule: `BR-TEN-060` is applied one surface
earlier, `CR-017`'s resolution is superseded and its ruling kept, and `BR-SHL-020` is not touched —
the reasoning for that last one is a decision-log row of 2026-09-02, judgment (2), rather than an
assumption made in code.

**`DEF-3282–3299` and `OQ-1372–1379` are UNUSED and free.** ⚠ Re-derived from the pinned tip at push
time (law 11's id clause) — twice, because the first push of this block raced a sibling.


## `CR-066` — the GL defaults lane, 2026-09-02

**Migration `rating 0025` is allocated to this lane.** `DEF-892`: a migration number is ALLOCATED,
never taken from the watermark. `0025_cr066_discount_gl_account` depends on
**`0024_def494_publish_needs_a_start_date`**, which was the real leaf when it was written. Schema
only — one nullable UUID column on `discounts` — because a migration that ALTERs a table and
UPDATEs its rows passes the whole SQLite suite and fails on PostgreSQL with *"cannot ALTER TABLE …
because it has pending trigger events"* (the `tenancy 0030/0031/0032` section above records that
lesson at length, and it is CLAUDE.md law 14 in another costume). The fill lives in
`apps.rating.services.apply_default_gl_accounts`, which is idempotent and runs at provisioning and
through the `seed_demo --tenant <sub>` repair door.

**`OQ-1343` is USED** — whether an impact fee is revenue at all or a contribution toward
construction. **It was re-derived from the pinned tip at push time** (law 11's id clause): the
register holds ids up to `OQ-1380`, and `1343` was free in `01-open-questions.md` and referenced
only by `CR-066` itself, which is the id the capture allocated. Nothing else in the `OQ-134x` range
was taken by this lane.

**NO NEW `DEF-` OR `BR-` ID WAS MINTED.** `DEF-2386` already described the defect and was filed
before the fix; a second row would make the register count one defect twice. No business rule
moved — the PO's ruling is a MAPPING, recorded in `chart.py`, the decision log and the CR, and
`BR-TEN-012` and `BR-BIL-010` are honoured rather than amended.

**Gate `G70`** (`g70_charge_code_gl_default.py`) is the next free gate number after `G69`, taken
from the directory listing and the `GATES` registry together — `run_gates._assert_registry_sane`
refuses a duplicate label, so a collision is a red run rather than a silent double-count.


## `CR-060` T7b · T7d · T7f — the month-end postings lane, 2026-09-02

**Migrations `ledger 0014`, `payments 0015` and `payments 0016` are allocated to this lane.**
`DEF-892`: a migration number is ALLOCATED, never taken from the watermark.
`ledger/0014_cr060_t7b_t7f_period_matching_designations` depends on **`0013_cr061_chart_category`**,
which was the real leaf when it was written; `payments/0015_cr060_t7d_allocation_classes` depends on
**`0014_cr059_cs34_amendable_reference`** and `payments/0016` on `0015`. **All three were
re-derived from the pinned tip at push time** (law 11's id clause) — a sibling lane pushing a
`ledger 0014` or a `payments 0015` of its own leaves TWO leaf nodes in that app's graph, which is
`DEF-2872`'s symptom: Django refuses every test in the process with *"Conflicting migrations
detected"*, names neither lane, and looks like a broken tree.

**Three `BR-LED` ids are USED: `BR-LED-792` · `BR-LED-793` · `BR-LED-794`.** The live highest was
`BR-LED-791` (minted by the T7 lane hours earlier the same day) and these are the next three,
re-read from the tip at push time. **`BR-LED-795` and up are UNUSED and free.**

⚠ **AMENDED 2026-09-24 — `BR-LED-795`, `796` AND `797` ARE NOW TAKEN AND `BR-LED-798` IS USED.** `795` and `796` were minted by the P2-LEDGER lane (row above), `797` is claimed by `CR-136-BRC07`, and **`BR-LED-798` is USED** — the batch-posting rule that closes `OQ-LED-12630` (PO ruling 2026-09-24). Re-read from the tip at push time across every `refs/remotes/origin` ref, numerically rather than lexicographically: a `sort -u` over these ids puts `BR-LED-1000` before `BR-LED-794` and reports the wrong maximum. **`BR-LED-799` and up are UNUSED and free.**
⚠ **AMENDED 2026-09-25 — `BR-LED-799` IS NOW USED.** Lane REC minted it for the PO ruling of 2026-09-25 that a supplier's invoice document is kept **seven years** (`OQ-LED-12628` CLOSED). Re-read from the pinned tip at push time across every `refs/remotes/origin` ref and **numerically, not lexicographically** — `BR-LED-1000` sorts before `BR-LED-794` under `sort -u` and reports the wrong maximum, which is why that warning is repeated rather than assumed learned. **`BR-LED-800` and up are UNUSED and free.**

**NO `BR-PAY` ID WAS MINTED.** `BR-PAY-010` is AMENDED — the class walk, its order, its default and
its tenant-setting status are all untouched and only the PERSISTENCE of its result is new — and
`BR-PAY-031`'s append-only rule is applied to the child table rather than restated. A new id would
have made the register hold two rules about one walk.

**NO `OQ` ID WAS MINTED, AND THAT IS THE POINT OF TWO OF THESE TASKS.** T7b's floor (supplier cost
incurred and not yet invoiced) is NOT an open question: a document nobody has cannot be estimated,
so there is nothing to decide and the absence is stated on every answer instead. T7f's floor
(depreciation before the first posted period) is not one either — it is an OPENING BALANCE, a
decision about a tenant's history that `apps/ledger/opening_balances.py` already exists for. T7d
mints none because `OQ-129` and `OQ-174` are both CLOSED and CR-060 C19's ruled disposition is to
record the breakdown rather than reopen either.

**NO `DEF` ID WAS MINTED.** Nothing this lane found was a defect: `DEF-3343`'s double count was
fixed on the export side earlier the same day and this lane's own guard is the same arithmetic
prevented on the accrual side, which is a build and not a fix. **`DEF-3362` and up are UNUSED and
free at the time of writing** — re-derive before taking one.

**Gate numbers: NONE taken.** No new gate was added; `G20`'s park list gains one row
(`apps.assets.selectors.depreciation_movement`) and `G61`, `G64` and the golden harness were RUN
rather than changed.
| `J30`–`J47` | **THE CR-068 PORTAL DOCUMENTATION LANE (2026-09-03).** The eighteen end-to-end journeys of the customer portal, described in full in `04-docs/05-modules/15-portal/04-flows.md` and cited from the `journeys:` frontmatter of the 74 stories in `06-epics/`. ⚠ **THE JOURNEY FILES IN `08-qa/01-e2e/journeys/` ARE NOT WRITTEN YET** and `04-flows.md` says so in its own header rather than letting a frontmatter citation imply a file exists (hard-won law 1). The block is reserved so a sibling lane taking `max + 1` does not land inside it — `J1`–`J29` were the live frontier and `T3M-001`–`279` are a separate generated matrix, so a naive walk returns `J30`. **USED: all eighteen, as descriptions.** | 2026-09-03 | **ACTIVE** |
| `BR-INT-018`–`053` · `US-INT-013`–`046` · `EP-INT-05`+ | **THE CR-069 INTEGRATION SUBSTRATE LANE (2026-09-03).** Allocated by PO ruling of the same day — *"You can change the numbers"* — recorded in `02-decision-log.md`. The design document numbers its own thirty-six rules and thirty-four stories from 1, and `BR-INT-001`–`017` and `US-INT-001`–`012` **already exist in this repository describing different things**, cited from the API contracts, the screen inventory and two decision documents. The offset is **+17 for rules and +12 for stories**, chosen because a reader can do it in their head. ⚠ **The existing ids do not move, so no citation breaks.** ⚠ **The document's own `C1`–`C36` handles are NOT minted** and stay as written. **UNUSED so far** — the document is truncated at about page 106 of a larger file and no story has been written from it yet. | 2026-09-03 | **ACTIVE** |

## The CR-070 re-hosting planning lane (2026-09-04)

**Re-derived from the pinned tip `45ab32e40d086098063abf94252e3d65a90efbc4` at push time (law 11 / `DEF-1787`: an allocated id is a blob, and
two lanes in separate worktrees can correctly compute the same maximum).** The register maxima at that tip were
**`OQ-…-1560`** and **`DEF-…-3724`**; an earlier pin in the same session read `1560` and `3704`, and the ids
below were renumbered from `3706`/`3707` to `3725`/`3726` when the tip moved — which is the whole reason the
rule says re-derive rather than reserve early.

**USED — three ids, module-tagged per the PO ruling of 2026-09-03:**

| Id | What it is |
|---|---|
| `OQ-WRK-1561` | **OPEN.** Which of the five flows a clerk may complete when the field visit has not happened. Move-out is ruled (`BR-WRK-055`); the other five are the utility's own operating policy, which is why it is asked rather than decided. Blocks nothing. |
| `DEF-WRK-3725` | The move-out field visit was planned onto `MoveOutWizard` step 4, which renders as *skipped* on a move-out that settles cleanly. Fixed by moving it to step 2 in wave `P`. |
| `DEF-WRK-3726` | The dispatcher's `source` enum names three flows and the product has six, and wave `G` declares it before waves `M` and `P` write into it. Fixed by widening it in `P1` and amending `G1`. |

**NO `BR-` ID WAS MINTED.** `BR-WRK-055` is **widened** — from move-out alone to all five flows — and
`BR-WRK-026`, `BR-WRK-006`, `BR-WRK-024` and `ck_work_orders_has_anchor` are all **untouched**. A new rule id
would have made the register hold two rules about one posture. `BR-WRK-055`'s original move-out text is kept and
marked superseded in `02-business-rules.md` by wave `P`'s `P8`.

**NO `US-` ID WAS MINTED.** Waves `O` and `P` are built from stories that already exist — `US-WRK-002`, `003`,
`004`, `006`, `017`, `039` — because the ruling changed **where** the work is hosted and not **what** it is. The
54-story coverage check still reads 54/54.

**NO `S-` SCREEN ID WAS MINTED, AND ONE IS RETIRED.** `S88` / `NCT-02` stops being a navigable destination in
wave `O4`; its `screenIds.ts` row and its `g29_allocated_badges.txt` row go in the same commit, and the id is
**not reused**.

**WAVE LETTERS: `O` AND `P` TAKEN, AND NOTHING RENUMBERED.** `A`–`N` keep their letters and `M3` keeps its task
id as a pointer to where it went. Running order is read from the plan's §2 table, not from the alphabet.

**GATE NUMBERS: ONE RESERVED BY SHAPE, NOT BY NUMBER.** Wave `P`'s task `P6` adds one gate and takes **the next
free number at push time** rather than naming one here — `G85` was minted by a sibling lane hours before this
was written, which is the case that makes naming a number in advance a collision waiting to happen.


---

## CR-068 wave D — the ids this wave took, 2026-09-04

**Gate: `G88` (`g88_published_gate_in_the_query.py`) — ⚠ MINTED AS `G84`, RENUMBERED THE SAME DAY.** `G83` was the live
frontier when this wave started and `G84` was free at the moment the file was
created — re-checked then rather than taken from the execution plan, which
named `G75`/`G78` and had both taken out from under it (`DEF-CWP-3634`).
⚠ **THREE LANES TOOK `G84` THAT AFTERNOON** (`g84_module_write_tables.py` at 05:25, `g84_provider_error_seam.py` at 05:30, this one at 06:42) — each read `10-scripts/gates/`, each correctly computed the next free number, and each got 84, because a sibling in its own worktree has its file in none of the places a `ls` can see until it pushes. **This one landed last, so this one moved.** `DEF-CWP-3734`. ⚠ **`G89` IS NOW TAKEN — the SECOND of the three took it on 2026-09-04** (`g84_provider_error_seam.py` → `g89_provider_error_seam.py`, `DEF-GOV-3654`): a gate label number must now be unique, so the pair this row left behind was split too. **`G90` and up are UNUSED and free** — and re-derive at PUSH time, not when the file is created. ⚠ **AND RENUMBERING IS NOT DONE WHEN THE FILE IS RENAMED — IT IS DONE WHEN EVERY CITATION HAS MOVED.** This row's own renumber left EIGHT behind (`DEF-GOV-3738`), including `BR-CWP-094`, which still read *the gate is in the SQL, and `G84` reads it as data* while `G84` meant two other gates.

**Screen ids: NONE MINTED.** `CWP-011`, `CWP-013`, `CWP-014`, `CWP-060`,
`CWP-071`, `CWP-072`, `CWP-073`, `CWP-074` and `CWP-075` are all allocated by
`CR-068` §9 and quoted, never invented. Four are routed in the portal's own
register (`07-frontend/src/portal/routing/screenIds.ts`) and two more staff
badges were added to `g29_allocated_badges.txt` — `CWP-071` and `CWP-073` — for
the two Configure segments whose routes previously showed the Overview's id
(`DEF-CWP-3730`).

**Defects: `DEF-CWP-3727`, `DEF-CWP-3728`, `DEF-CWP-3729`, `DEF-CWP-3730`** —
four, taken by hand from the register's maximum (`DEF-WRK-3726`) because the
tooling does not read the module segment yet. **`DEF-CWP-3734` and up are
UNUSED and free** at the time of writing.

**⚠ NO `OQ` ID WAS MINTED, AND THAT IS THE POINT OF THE WAVE'S BOUNDARY.**
`OQ-1398` — who keeps the help answers current, and in how many languages —
was already open and is still open; this wave built the mechanism to that line
and answered nothing. Everything else it met was ours to decide and is in the
decision log for 2026-09-04 (law 13: *a question is the failure to make a
judgment*). **`BR-CWP` ids: none minted** — `BR-CWP-093`–`096` already say
everything this wave implements, and a fifth rule would have been the same rule
written twice.

**Journeys: none minted.** `J33`, `J34` and `J46` were already written by the
CR-068 documentation lane (`da2fe7ef`); this wave appended what only a build
lane can know — where each one is actually walked — and rewrote nothing.
⚠ Its first draft OVERWROTE two of those three files before `git status`
showed them as modified rather than new; they were restored from `HEAD` byte
for byte. **A new file in a folder of 347 is not necessarily new.**

## 2026-09-04 · `DEF-CWP-3736` + `DEF-CWP-3655` — the portal's colour and its second kit (`2.139.1`)

**Gate number: `G90`** (`g90_dead_custom_properties.py`) — a CSS custom property a component SETS
and no `var()` anywhere READS. **`G91` and up are UNUSED and free** at the time of writing — and
re-derive it, do not trust this sentence.

⚠ **IT WAS `G89` FOR TEN MINUTES, AND THAT IS THE FOURTH COLLISION IN TWO DAYS.** This lane took
the number from the pushed tip — the rule `DEF-CWP-3734` left here that same afternoon — and it
was still wrong, because a sibling lane renamed `g84_provider_error_seam.py` to `G89` at 08:34
while this lane was running its test suite, and this gate landed at 08:44. **The later one
renumbers**, which is the only rule that terminates, so this one moved.

**The part worth keeping: a CHECK caught it, for the first time.** `_assert_registry_sane` — which
that same sibling had written an hour earlier, in the very commit that took `G89` — refused the
whole registry by name: *"gate number(s) ['G89'] claimed by more than one row"*. The three earlier
collisions were each found by a person noticing. `DEF-GOV-3755` carries the residual gap: this
lane's push helper re-derived its DEFECT ids from the pinned tip and refused a stale one in its own
words minutes earlier, and did not do the same for its GATE number, because nothing connected the
two.

**Defects: `DEF-CWP-3737` and `DEF-CWP-3739`**, both taken by hand from the register's maximum
because the tooling does not read the module segment yet.

⚠ **THE SECOND ONE MOVED AT PUSH TIME, AND THAT IS THE PROCEDURE WORKING RATHER THAN A MISHAP.**
It was written as `DEF-CWP-3738`, correctly, against a register whose maximum was `3737` when the
row was drafted. By the time the push helper re-read the register **from the pinned tip**, a
sibling lane had filed `3738` and the helper refused in its own words — *"the register's maximum
moved — `DEF-CWP-3739` is free, not `DEF-CWP-3738`. Renumber the row and every citation of it,
then re-run."* That is exactly the collision `DEF-1787` records for two lanes computing `max + 1`
minutes apart, caught by a check instead of by a reader noticing a duplicate in a 1,655-row file.
**A push helper that REFUSES is worth more than a paragraph telling the next lane to remember**,
and it is the form law 11 asks for.

**No `OQ` id was minted, and the boundary is deliberate.** Two things this wave met were ours to
decide and are in the decision log rather than the question register (law 13): what a tenant's
SECOND colour is for — nothing, today, because no signed rule says — and whether the accent ramp's
hover and active steps are derived or left at the product's. `DEF-CWP-3737` carries the first as a
defect rather than a question, because the field is already built and already wrong.

**No `BR-CWP` id, no screen id, no journey.** Nothing new is on screen: the same screens, in the
utility's own colour, built from the kit that already existed.


## CR-072 — the report is the request (2026-09-04, the build lane)

⚠ **EVERY ID IN THIS SECTION IS THE SECOND SET THIS WAVE WAS GIVEN, AND THE
FIRST SET WAS COMPUTED CORRECTLY.** `DEF-CWP-3737`, `DEF-CWP-3738`,
`BR-CWP-099` and `BR-CWP-100` were all taken from the register's maximum at the
time, and **all four had been taken by the portal-colour lane by push time** — and
the SECOND set collided too (`DEF-CWP-3740` went to a sibling between the first
refusal and the second) —
which is law 11's last clause exactly: `file_defect.py` and a directory listing
see the PUSHED world plus your own checkout, and a sibling working in its own
worktree has rows in neither until it pushes. **`push_paths.sh` refused the push
on nine moved paths, and the ids were re-derived from the pinned tip in the same
act as the blobs.** Nothing downstream would have caught the duplicate.

**Defects: `DEF-CWP-3743`, `DEF-CWP-3744`, `DEF-GOV-3755` and `DEF-CWP-3746`** — four, taken BY HAND from the
register's maximum at the pinned tip (`DEF-CWP-3739`) because the tooling does
not read the module segment yet. **`DEF-GOV-3755` and up are UNUSED and free**
at the time of writing — re-derive it, do not trust this sentence.

**Business rules: `BR-CWP-100`, `BR-CWP-101`, `BR-CUS-1044`, `BR-CUS-1045`** —
four, and each is a statement the code now enforces rather than a restatement of
`CR-072`. The portal pair says what a report IS and who may open an
interruption; the customers pair says what the table carries and what
`attach_interruption` refuses. `BR-CWP-024` and `BR-CWP-028` were AMENDED in
place with their supersession stated, not renumbered.

**Migrations: `customers/0040`** — one, checked against the branch tip at push
time. `0039` was the leaf, and it still was: the same collision that renumbered
`0038`→`0039` twice on this table would have shown up as a refusal from
`push_paths.sh` step 2, and did not.

**⚠ NO `OQ` ID WAS MINTED, AND THAT IS THE POINT.** Everything this wave met was
ours to decide and is in the decision log for 2026-09-04 with its reasoning —
law 13: *a question is the failure to make a judgment*. The five judgments are
listed there by name, including the two the next lane is most likely to want to
re-open (why the link is a plain UUID and not a ForeignKey, and why correcting a
mis-attached report is deliberately not built).

**Screens: none minted.** The clerk's *Open an interruption* control is a
control on the EXISTING Interruption section of `REQ-02`, which `R13` already
settled: screen numbers are the PO's.

⚠ **`DEF-CWP-3746` IS FILED BY A LANE THAT DID NOT CAUSE IT.** `G81` is GREEN at
this lane's base and RED at the tip, and all twelve complaints name
`apps/portal/credentials.py` — the CR-068 wave E lane's file. A red gate on a
shared branch is everybody's and nobody's, and the next lane to run the suite
would otherwise read it as its own. The row is a handoff, and it names the owner.

## 2026-09-04 · `CR-070` wave O — one destination

**Defects: `DEF-WRK-3748`, `DEF-WRK-3749`, `DEF-WRK-3750`, `DEF-CUS-3751`,
`DEF-WRK-3752`** — five, taken BY HAND from the register's maximum at the pinned
tip because the tooling does not read the module segment yet
(`file_defect.py`'s `^"?DEF-(\d+)"?,`). Three are figures the execution plan got
wrong and this lane would have built to (*seven acts* where there are eight,
four KPI TILES described as tabs, three test files where there were two); one is
a pre-existing eslint failure on the branch tip; and `DEF-WRK-3752` is this
lane's own worktree-sync helper silently reverting eleven locale catalogues,
which **`G15` could not see because the damage was symmetric** and only a
browser could. **Re-derive these numbers at push time — do not trust this
sentence** (`DEF-CWP-3734`: three lanes, three correct computations, one
number).

**Gates: `G93 one-build-destination`** — one, and it was **written as `G91` and
renumbered twice on the day it landed**. `G91` and `G92` were both free when
this lane computed them and both were taken by a sibling portal lane before the
push. The number below was re-read from the PINNED TIP, and so was the
`import` line and the registry row in `run_gates.py`.

**Screens: NONE minted, and one RETIRED.** `NCT-02` (`/:tenant/connections/:connectionId`)
leaves `screenIds.ts` and `g29_allocated_badges.txt` in the same commit: the
route still resolves, but it is a doorway that redirects and a badge says
*"this is a screen"*. `G29`'s baseline falls 110 → 109 screens and 118 → 117
routes — **the first time these figures have ever gone down**, and it is the
ratchet working rather than a regression. `Work-002` mints nothing: its layout
now lands on two hosts that already have ids (`PRM-02` and `ACC-02`).

**Business rules: none minted.** Everything this wave met was either already
signed (`BR-WRK-006`, `BR-WRK-026`, `BR-SHL-025`, `BR-MET-110`, `BR-MET-1161`)
or a judgment, and a judgment belongs in the decision log rather than in a rule
number.

**⚠ NO `OQ` ID WAS MINTED, AND THAT IS DELIBERATE.** Five judgments were made
where the rules ran out and every one is in the decision log for 2026-09-04 with
its reasoning — law 13: *a question is the failure to make a judgment*. The two
a later lane is most likely to want to re-open are named there: why the account's
Work tab lists the whole address's jobs and not only its own, and why the Build
tab draws no units table, charges panel or history panel.

**Migrations: none.** `CR-070 §W.10` is explicit that `connections` survives as
plumbing — *"whatever the tables are called underneath"* — so nothing was added,
altered or dropped, and no data moved.
## CR-069 wave E — connect day (2026-09-04)

**Gate: `G94` (`g94_credential_three_exits.py`) — FIVE numbers in one day.** ⚠ **TAKEN TWICE BEFORE IT LANDED, WHICH IS
`DEF-CWP-3734` HAPPENING AGAIN AND THE RE-DERIVATION CATCHING IT.** The file was written as `G89`
against a base where `g88` was the highest; by push time the tip had renamed another lane's
`g84_provider_error_seam.py` to **`g89_provider_error_seam.py`** and a third lane had landed
**`g90_dead_custom_properties.py`**. Both were found by re-reading `10-scripts/gates/` from the
PINNED TIP rather than from the working tree — **and then a THIRD lane registered its own `G91` (`g91_portal_staff_separation.py`) and a `G92` between that re-derivation and the push.** `run_gates`' own `_assert_registry_sane` caught it before any gate ran, which is what that check was added for: *gate number(s) ['G91'] claimed by more than one row*. So the file was `G93` — **and a fifth lane registered ITS own `G93` (`g93_one_build_destination.py`) before this could be pushed, so the file is `G94`** — taken from the tip's REGISTRY rather than from a directory listing — the registry is the authority, because a number can be claimed by a row before its file lands. **`G95` and up are UNUSED and free** — and re-derive at
PUSH time, not when the file is created.

**Defects: `DEF-NOT-3747` and `DEF-GOV-3755`.** ⚠ **ALSO RENUMBERED AT PUSH TIME — this is `DEF-1787` exactly.** The row
was written as `DEF-NOT-3738` against a register whose maximum was `3737`; by push time siblings had
taken **`3738` through `3745`**, so `3738` would have been a duplicate in a 3,700-row register and
nothing downstream would ever have noticed. Re-derived from the tip's copy of the register: the
maximum was `DEF-GOV-3755`, so it became `3746` — **and then a sibling took 3746 too, between that re-derivation and the push, so it renumbered a SECOND time to `3747`.** Twice in one hour, on one row. `DEF-GOV-3755` is this lane's second defect, taken from the pushed tip. **`DEF-…-3755` and up are UNUSED and free** at the time of writing.

**⚠ NO `OQ` ID WAS MINTED, AND THAT IS THE POINT OF THE WAVE'S BOUNDARY.** Six judgments met this
lane where the signed rules ran out and all six were DECIDED and written into the decision log for
2026-09-04 (law 13: *a question is the failure to make a judgment*). The questions that stay open —
`OQ-INT-1479` (Settings is System Admin only), `OQ-INT-1488` (the mailbox volume threshold) — were
already open and are still open; this wave answered neither and built to the line of both.

**`BR-INT` ids: none minted.** `BR-INT-003`, `016`, `019`, `025` and `042` already say everything
this wave implements. `BR-INT-025` and `BR-INT-042` remain **PROPOSED** — implementing a proposed
rule does not ratify it, and a lane may not promote one.

**Screen ids: none minted.** `S141` and `S142` are `CR-069` §9's and were quoted. **Journeys: none
minted** — `J48` and `J49` were written by the documentation lane; this wave APPENDED where each is
actually walked and rewrote nothing.

## CR-068 waves G/M slice — the money list and payment plans (2026-09-04)

**Stories:** `US-CWP-048` (`CWP-041`) · `US-CWP-051` (`CWP-042`) · `US-CWP-052` (`CWP-043`).

**Question: `OQ-CWP-1720` — does missing two instalments end a payment plan?** The portal blueprint
says it does (`P28`, `US-CWP-051` TC-3, `US-CWP-052` TC-7, `J41` steps 2 and 7); the PO ruled on
2026-08-11 that nobody is dropped (*"nodrop we chase for payments until write off"*), and that ruling
is implemented as an ABSENCE and tested. A collision with a signed rule is one of the three things
that legitimately reaches the PO (law 13), so it is MINTED rather than decided here.

⚠ **TAKEN AS `OQ-CWP-1563`, RENUMBERED TO `1565`, AND RENUMBERED AGAIN TO `1569` — LAW 11's ID
CLAUSE, TWICE ON ONE ROW, IN ABOUT TWENTY MINUTES.** The register's maximum was `1562` when the row
was written. At the first push a sibling had landed `OQ-CWP-1563` (the bill-comparison decomposition,
cited from `apps/portal/api.py`'s `bill_comparison`), so `1563` would have been a **duplicate id in a
1,500-row register and nothing downstream would ever have noticed**. This lane took `1565` — stepping
over `1564` deliberately, because another lane was renumbering in the same minutes and `allocate.py`
cannot reserve. **By the time that commit was built, `1565`, `1566`, `1567` and `1568` were ALL taken
too.** The maximum at the tip is now `1568`, so this is `1569`.
**The lesson is the one law 11 already states and it is worth the ink:** every one of those
computations of *"the register's maximum + 1"* was ARITHMETICALLY CORRECT. What was wrong was *which
world the maximum came from* — a sibling in its own worktree has its rows in none of the places a
local listing can see until it pushes. **The only moment the answer can be final is immediately
before the push**, which is where both re-derivations happened. **`OQ-CWP-1570` and up are UNUSED and
free** at the time of writing, and a lane reading this line should re-derive rather than believe it.

**Defects: none filed.** Two findings that would ordinarily be defects are recorded in the decision
log instead, because both are ABSENCES in a table nobody has built on rather than broken behaviour:
`billing.Adjustment` has no writer anywhere in the product, and no per-account write-off read exists.

**`BR-CWP` ids: none minted.** `BR-CWP-050`, `051`, `052`, `061`, `062`, `063`, `064` and `066` already
say everything these three stories implement, and `BR-CWP-066` was CONFIRMED by the PO on 2026-09-04.

**Write points: NONE added.** `write_points.py` still declares six kinds. *Ask for a payment plan* is
a fourth SHAPE of the existing `service_request` write point, which is what `BR-CWP-066` asks for in
its own words: *"raises an ordinary service request under `CR-072`, never a request of a new kind"*.

**Screen ids: none minted** — `CWP-041`, `CWP-042` and `CWP-043` are `CR-068` §9's (`P27`, `P28`,
`P29`) and were quoted. **Journeys: none minted** — `J36` and `J41` were written by the documentation
lane; this slice appended where each is actually walked and rewrote nothing.
## `CR-068` wave H — usage, readings and equipment (2026-09-04)

**Defects: `DEF-CWP-3770`, and it is the ONLY id this lane minted.** Taken from
`10-scripts/allocate.py defect` (which reported `3769` against a register whose maximum was
`DEF-CWP-3768`) and **re-derived from the pinned tip at push time**, per law 11's own instruction:
an allocated id is a blob too. `DEF-…-3770` and up are UNUSED and free at the time of writing.

**⚠ NO `OQ` ID WAS MINTED, AND THAT IS DELIBERATE (law 13).** Five judgments met this lane where the
signed rules ran out — the reading↔bill correspondence, the unbuilt `awaiting_review` suffix, the
`billing_basis` source, how a `capacity` service names its equipment, and the two-call shape that
gets a year-on-year comparison onto a twelve-month chart — and **all five were DECIDED and written
into the decision log for 2026-09-04**. A question is the failure to make a judgment.

**Screen ids: none minted.** `CWP-033`, `CWP-034` and `CWP-037` are `CR-068` §9's own, quoted with
their blueprint labels `P19`, `P20` and `P23`; `G82` checks both halves.

**`BR-CWP` ids: none minted.** `BR-CWP-069`, `071`, `072`, `073`, `093`, `095` and `010` already say
everything these three stories implement, and all seven are CONFIRMED.

**Gate numbers: none taken.** This wave adds no gate — `G81`, `G82`, `G13` and `G31` already cover
its surface, and a fifth that read rendered output is not something this repo can do.

## `CR-068` wave R — track a request, query a bill, ask a question (2026-09-05)

**Stories:** `US-CWP-063` (`CWP-051`) · `US-CWP-065` (`CWP-055`) · `US-CWP-066` (`CWP-054`).

**Open questions: `OQ-CWP-1680`, `OQ-CWP-1681`, `OQ-CWP-1682`** — three, and each is one of the
three things law 13 says legitimately reaches the Product Owner rather than a judgment a lane
should have made. **1680** collides with `BR-CWP-010` (a service request has no account column to
intersect the session's set against). **1681** would need `BR-CWP-001` widened to a seventh kind AND
`BR-MET-035` widened to admit a portal actor, so the portal can raise `metering`'s dispute marker.
**1682** is a signed figure the product cannot honour: `CWP-055`'s box promises a hold on `$142.18`
and `OQ-420` — OPEN since 2026-08-26 — is that nothing records a disputed AMOUNT.

**Defects: `DEF-CWP-3880`, `DEF-CWP-3881`, `DEF-CWP-3882`, `DEF-CWP-3883`.** The last was found merging onto the tip rather than while building — `portalClient.ts` did not PARSE on the branch, so `tsc` was red for every lane — and it is FIXED here because it is in a file this lane had to touch anyway. ⚠ **A FIFTH WAS DRAFTED AND WITHDRAWN, WHICH IS THE RIGHT OUTCOME AND IS RECORDED RATHER THAN QUIETLY DROPPED:** the kit's `SelectInput` was styled `bg-white`, a class this theme clears to nothing (`DEF-974`), and the lane that wrote the component found it themselves through `src/styles/routeBUtilities.test.ts` and fixed it one tip later. There IS a check and it worked; filing a row saying otherwise would have put a false sentence in the one column that turns a bug list into a process fix. All four taken from this lane's
reserved block (3880–3899) and **re-derived from the pinned tip at push time**, per law 11: an
allocated id is a blob too. `allocate.py defect` reported `3779` against a register whose maximum
was lower, so the block sits clear of it; the verification that matters was reading the register
**out of the tip** rather than out of this worktree, because `allocate.py` cannot see a sibling's
unpushed rows and reports its own file's contents as TAKEN. `DEF-…-3884` and up are UNUSED and free
at the time of writing, and a lane reading this line should re-derive rather than believe it.

**Screen ids: none minted.** `CWP-051` (`P37`), `CWP-055` (`P41`) and `CWP-054` (`P40`) are
`CR-068` §9's own, quoted with their blueprint labels; `G82` checks both halves.

**`BR-CWP` ids: none minted.** `BR-CWP-010`, `024`, `026`, `042`, `075`, `076`, `077`, `078`, `079`,
`093` and `056` already say everything these three stories implement, and every one is CONFIRMED.

**Write points: NONE added.** `write_points.py` still declares six kinds. Querying a bill and asking
a question are the FIFTH and SIXTH shapes of the `service_request` write point; withdrawing and
answering are the SEVENTH and EIGHTH, and `BR-CWP-075` is what puts them there —
*"the customer may make exactly four of the eleven request transitions"*. Six kinds, one public
function, eight shapes.

**Gate numbers: none taken.** This wave adds no gate. `G81`, `G82`, `G84`, `G96`, `G13`, `G31`,
`G32`, `G35` and `G40` already cover its surface, and the one check it would want — *does any
catalogue promise a collection hold?* — is a TEST rather than a gate, because it is a wording
constraint on three screens rather than a rule about the repository.


## 2026-09-05 · portal branding lane (DEF-CWP-3736/3737/3723/3720/3774/3655)

**Gate number: `G104` one-declaration-per-component.** Took `G103` first;
`10-scripts/allocate.py gate --verify 103` answered *"gate 103: TAKEN — a sibling
pushed it. Renumber before you commit"* while this lane's suite was running, so it
moved to `G104`. **The later one moves** (`DEF-CWP-3734`), and the sibling's
`G103 holds-cannot-rot` was left exactly where it was.

**Defect numbers: `DEF-SHL-4012` and `DEF-SHL-4013`.** These are not the first
pair this lane allocated. It took `4010` and `4011`, wrote both rows, and on
re-deriving at push time was told *"defect 4010: TAKEN"* and *"defect 4011:
TAKEN"* — siblings had pushed into that range while the rows were being written.
`SHL` because both are in the shared component and catalogue surface rather than
in the portal: `components/Panel.tsx` against
`features/tenancy/settingsShared.tsx`, and two of the eleven locale files.

**Version: `2.173.5`.** Also not the first taken. This lane bumped to
`2.173.2`; by the time the record was ready a sibling had shipped `2.173.2`, then
`2.173.3`, then `2.173.4`.

⚠ **THAT IS THREE FAMILIES COLLIDING UNDER ONE COMMIT — a gate number, two defect
ids and a version — which is exactly the trio `DEF-GOV-3756` and `DEF-CWP-3734`
recorded, and every piece of this lane's arithmetic was right when it was done.**
What was wrong each time was *which world the maximum came from*: the tip moved
under this record repeatedly, once by eight commits between building it and
pushing it. `allocate.py <family> --verify <N>` caught every one, and the pairing
is the thing worth keeping — **the verify is not a step after the blob
re-derivation, it is part of it**, because both answer the same question about the
same pinned tip. `DEF-GOV-3740` asked for exactly this and named the gap it left
for gate numbers; that gap is closed now too.

**The durable form, and it cost three rejected pushes to learn:** when a record
commit touches several shared registers at once, write the re-derivation as a
SCRIPT parameterised by the tip and the ids, not as a series of edits in a
worktree. Re-running it against a new tip is then one command instead of an
afternoon, and the ids cannot drift out of the prose that cites them because the
prose is templated from the same variables.

**No new defect for the `text-danger` orphan `G31` found.** A work lane had
already filed and fixed it as `DEF-WRK-4005` within the hour, from the other
direction. Recorded here because two lanes finding one live defect independently
is the argument for the check, not a duplicate to be tidied away.


## `OQ-CWP-1721` — reserved 2026-09-05 by the portal bill lane

Taken BY HAND from the register maximum (`OQ-CWP-1720`) because the tooling does not read the module
segment yet — `gates/common.py` matches `OQ-\d{3,6}` straight after the family, so an allocator would
have answered against a different number. Re-derived from the branch tip at push time and re-checked
free, which is the only moment that answer can be final (law 11's id clause).

It records the half of `DEF-CWP-3951` a lane may not decide: where a receipt address typed by an
ANONYMOUS caller may be written once notifications can dispatch. The defect itself is fixed — the form
no longer collects what nothing could use — and this is what remains.


## `DEF-WRK-4048` · `DEF-WRK-4046` · `DEF-WRK-4047` — reserved 2026-09-05 by the wireframe-vs-product lane

Taken BY HAND from the register maximum (`allocate.py defect` answered **4045** against the remote, over
1859 numbers across five branches) because the tooling does not read the module segment yet —
`file_defect.py`'s `^"?DEF-(\d+)"?,` and `gates/common.py`'s `OQ-\d{3,6}` both expect digits straight after
the family, so an allocator writing the row would have spelled it `DEF-4045` and a search for
`DEF-WRK-4048` would have found nothing. Re-derived from the branch tip at push time and re-checked free,
which is the only moment that answer can be final (law 11's id clause).

The three are one pass over the six Work drawings the Product Owner put beside the running module:

* **4045** — `Work-013`'s GATE column drew a dash over a reason the row was already carrying. A field
  seeded, seamed, served, typed and read by nothing, with two source files stating in words that it *is*
  shown. Fixed, RED proved first.
* **4046** — `TemplatesPage.tsx` and `TemplateDetailPage.tsx` each described controls as absent that are on
  the screen. Five false statements, all of them holds whose clocks expired when wave E landed the template
  builder. Fixed.
* **4047** — `08-screen-layouts.md`'s divergence table claimed a download glyph is built on the Work lists.
  None of the six renders one, and the file's own `Work-007` entry says so correctly two hundred lines
  above. Fixed.

**No new question was minted and no new gate number was taken.** Two durable checks are proposed inside the
rows (a served-key-with-no-reader check for 4045, and an `is NOT rendered` phrase check for 4046) and
neither is built here, because a gate number is a shared register and three lanes collided on one this
week (`DEF-CWP-3734`).


## `DEF-WRK-4050` — reserved 2026-09-05 by the wireframe-vs-product lane

Taken BY HAND from the register maximum for the same reason as the three above (the tooling does not read
the module segment), and **it is the second id this lane lost to a sibling in one afternoon**: `4045` was
gone by the time the first push was built, and `4049` was gone while this row was being written.
`allocate.py defect --verify` caught both at the only moment the answer can be final. Neither collision cost
anything, which is the point of running the verify in the same breath as the blob re-derivation.

It records the THIRD file in one day whose `// exceptions:` line described a hold that had expired —
`OrdersPage.tsx`, released by CR-070 wave H hours earlier. Filed separately from `DEF-WRK-4046` rather than
folded into it, because three independent instances by three lanes is the evidence that this is a mechanism
and not three lapses, and because folding it in would have edited a register row already pushed.

## `DEF-AUD-4080` and `OQ-AUD-1724` — reserved 2026-09-05 by the G5 isolation-fixture repair lane

Taken BY HAND from each register's maximum, because the tooling still does not read the module segment
(`file_defect.py`'s `^"?DEF-(\d+)",` and `gates/common.py`'s `OQ-\d{3,6}` both expect digits immediately
after the family). `allocate.py defect` agreed on 4080 — it reads only the untagged form, so agreement is a
coincidence worth stating rather than a check that passed; the number that decided it is the defect
register's own last row, and the open-question register's own last row for 1724.

They are one finding, filed as two rows on purpose: the DEFECT records what the archival job does today and
is measured, while the QUESTION is which of three lawful repairs to make — and that one collides with the
Product Owner's 2026-08-24 `BYPASSRLS` ruling (`OQ-354`), which hard-won law 13 names as one of the three
things that legitimately reaches them.

---

## CR-070 wave L — the offline day, one sync, and the read that posts (2026-09-05, `2.195.0`)

⚠ **ALLOCATED BY HAND FROM THE REGISTER MAXIMUM, because no script reads a module-tagged id
yet** — `file_defect.py`, `gates/common.py` and `g08`/`g17`/`g38`/`g50` all expect digits right
after `OQ-`/`DEF-`. Every number below was re-verified free at PUSH TIME with
`10-scripts/allocate.py <family> --verify <N>`, which asks the REMOTE rather than this checkout.
**Two of them had to be renumbered**: `DEF-4060` and `DEF-4061` were free when this lane took
them and TAKEN by a sibling about forty minutes later — law 11's id clause, caught by the verify
and not by anything else. Re-derive from this file before taking anything adjacent.

**USED — one question, four defects:**

| Id | What it is |
|---|---|
| `OQ-WRK-1723` | **OPEN.** Which meter a reading posts to when a job touches two. `BR-WRK-015` gives a reading specification six columns and **none names a meter**, so a one-meter job uses the order's asset anchor and a meter EXCHANGE (`48,221 kWh` out of the old meter, `1,204 kWh` into the new) cannot say which is which. `metering_seam._posting_meter_no` refuses a job with more than one posting reading BY NAME rather than guessing. Blocks the exchange's second read and nothing else. |
| `DEF-WRK-4072` | Metering's event-read door silently DROPS the caller's `unit`. Open — the durable fix is metering's, and `03-field-map.md` D-13 already ruled it *"filed not worked around"*. |
| `DEF-WRK-4073` | `US-WRK-046` TC-1 and `J61` say *channel `field`*; that is a SOURCE, not a register, and a read on it would be invisible to billing. Open — amending the documents is the documentation lane's act. |
| `DEF-WRK-4074` | The execution plan said the message-source constant has ten kinds; it has twelve. Third time in three days. Fixed in the plan, and the fix is *stop quoting the list*. |
| `DEF-WRK-4079` | The headline law-14 test could not fail: it exercised the cheap `exists()` read and never the constraint, so it passed with the savepoint DELETED on real PostgreSQL. Fixed — the duplicate now arrives inside the batch. |

**NO `BR-` ID WAS MINTED.** `BR-WRK-003`, `BR-WRK-041` and `BR-WRK-042` are **amended in place**
with what was built and what was not; `BR-WRK-015` and `BR-MET-110` are untouched. A rule that
already says the thing does not need a second number.

**NO NEW `S` OR `J`.** `Work-012` gains a fourth pane at `jobs/:orderId/close` and keeps badge
`WRK-23` — it is the last pane of a job a technician is already on, not a screen of its own, and a
fourth badge would invite a fourth opinion about when a job may close. `J61` and `J65` are the
journeys this wave serves and **neither is activated**; their banners stand.
## `DEF-CUS-4084` — reserved 2026-09-05 by the G5 isolation-fixture repair lane
**THIS ID WAS TAKEN TWICE BEFORE IT STUCK, AND `--verify` IS THE ONLY REASON IT DID NOT COLLIDE.**
`4081` was gone by the time the row was written — `allocate.py defect` returned **4082** while this
checkout's own register still read 4080 as its maximum, which is the stale read the allocator exists
to remove. The row was written as `DEF-CUS-4082`, and when it was re-verified at push time — in the
same breath as the blob re-derivation, per law 11 — the answer was *"4082: TAKEN — a sibling pushed
it. Renumber before you commit"*. It was renumbered to **4084** and verified free again.
⚠ Worth recording because the near-miss is invisible from either side: the sibling's 4082 is not in
the defect register at all — the allocator found it on a pushed ref this checkout does not read — so
a lane checking only `10-defect-log.csv` would have concluded 4082 was free, twice, correctly, and
still have collided.

## `DEF-SHL-4092` and `DEF-MET-4093` — taken 2026-09-05 by the validate-at-source lane
Both filed through `file_defect.py`, both `--verify`'d free against every remote ref at
allocation and again at push time, in the same breath as the blob re-derivation (law 11).

⚠ **THE TWO ALLOCATORS DISAGREE ABOUT "NEXT", AND A LANE THAT TRUSTS THE HIGHER ONE WASTES
IDS WHILE A LANE THAT TRUSTS THE LOWER ONE IS FINE.** `allocate.py defect` returned **4104**
in the same minute that `file_defect.py` allocated **4092**, and neither is wrong: they read
different worlds. `file_defect.py` reads DEFECT-REGISTER ROWS across the working tree, `HEAD`,
`@{upstream}` and every `refs/remotes/origin` ref. `allocate.py` reads those AND every number
appearing in working-tree CODE and in COMMIT MESSAGES — on the day this was written that was
`+1957` from code and `+12` from commit messages — so its maximum is pulled up by ids that are
merely CITED somewhere and were never filed as rows.

**The reconciliation is `--verify`, and it is the question that actually matters.**
`allocate.py defect --verify 4092` answered *"still free on every branch"*, and a grep across
the tree and `git log --all` confirmed 4092 appears nowhere at all. So the gap between 4092 and
4104 is not twelve taken ids; it is twelve numbers that some register's or document's prose has
mentioned. **Take the number `file_defect.py` gives you and VERIFY it** — asking `allocate.py`
for "next" and using that answer skips a dozen perfectly free ids each time, and the register is
the thing whose maximum a later lane will compute from.

## `CR-073` and `DEF-WRK-4094` — taken 2026-09-05 by the universal-search lane
`CR-073` was taken BY HAND: `allocate.py` has no `cr` family, so the number came from the
"next free number" line in `11-change-requests.md` cross-checked against every
`refs/remotes/origin` ref — `CR-073` appeared on three branches and on all three it was the
*declared next free number*, never a filed CR. The line now reads `CR-074`.

`DEF-WRK-4094` was allocated by `file_defect.py`, which read the working tree, `HEAD` and every
remote ref (three of them carrying rows this checkout has not seen: `+2`, `+7`, `+1`). ⚠ Note the
gap this records once more: `allocate.py defect` would have answered higher, because it counts
numbers merely CITED in code and commit messages as well as filed rows. **Take `file_defect.py`'s
number and `--verify` it** — which was done at push time, in the same breath as the blob
re-derivation.

## 2026-09-05 · CR-070 wave M's fixture lane (`DEF-WRK-4085`)

Module-tagged ids, taken **by hand from each register's own maximum** because the
tooling still reads digits straight after the family (`file_defect.py`'s
`^"?DEF-(\d+)",`, `gates/common.py`'s `OQ-\d{3,6}`) and cannot see the `WRK-`
segment. Each was then re-derived at push time and confirmed free with
`allocate.py <family> --verify N`, which asks the REMOTE rather than this
checkout.

| id | what it is |
|---|---|
| `OQ-WRK-1725` | What is the asset-age rule called — the drawing's *Meter exchange programme* or the plan's and the engine's *Asset age rule*? Both are seeded meanwhile, with disjoint subjects. |
| `OQ-WRK-1726` | Is *Reconnect after payment* a rule we want, and who builds the trigger? The engine has no reader for *payment clears on a disconnected account*, so it is not seeded. |
| `DEF-WRK-4096` | Four of the five rule triggers cannot raise a work order at all — `rules._raise_one` stamps `source = rule.source_module` and `create_work_order` validates against a different vocabulary. The fifth works only because `assets` appears in both by coincidence. |
| `DEF-WRK-4097` | The continuous-flow trigger flags every normally-used meter: 98 subjects on a ~98-meter demo estate, and no floor narrows it below 53. |

⚠ **`OQ-WRK-1724` WAS TAKEN WHILE THIS LANE WORKED** and `allocate.py oq
--verify 1724` said so — *"TAKEN — a sibling pushed it. Renumber before you
commit"* — which is exactly the collision the allocator exists to catch, caught
at the only moment the answer can be final. The numbers above start at 1725
because of it.

⚠ **AND A CITATION GATE CANNOT CATCH THE WORSE HALF OF THIS.** The first draft
of `apps/work/sample_data.py` cited `DEF-WRK-4086`, `OQ-WRK-1491` and
`OQ-WRK-1492` as placeholders. `G106` caught the first — no register ever issued
it — and **could not catch the other two, because both are real questions about
other subjects** (1491 is whether a closed job's cost reaches the books; 1492 is
who may accept a work order). An id that exists is not an id that says what you
meant, which is `DEF-2804`'s lesson one layer up: there, a three-digit pattern
read `OQ-1190` as `OQ-119` and blocked a stub on a different real question.
**Allocate before you cite, not after.**

## 2026-09-06 · `OQ-INT-1727–1729` — the CR-069 / Runbooks boundary lane

**Three questions and ONE DEFECT minted, no version.** This lane wrote documents only:
`BR-INT-054` amended in place, `CR-069` §20 added (all nineteen waves classified),
`10-execution-plan.md` rewritten for what integrations keeps.

| Id | What it asks |
|---|---|
| `OQ-INT-1727` | Waves `C` and `D` shipped work that now sits on the Runbooks side — the per-item run results and the value mappings (screen S143, `2.131.0`, about three people-weeks). Does it move, stay as a named exception, or does Runbooks read it in place? |
| `OQ-INT-1728` | Does *record updates go to Runbooks* cover a write a **person** makes synchronously on a screen (wave `M`'s Create), or only unattended runs? The ruling does not choose. ⚠ **RULED AND CLOSED THE SAME DAY — option (a):** the synchronous write stays with the module that owns the screen, **and the PO added that the same job must ALSO exist as a batch in two forms, scheduled and run-once.** See the decision log, 2026-09-06. |
| `OQ-INT-1729` | Wave `F` is the live lane and the unbuilt half of `F2` is a record update. Stop it, or let it land here and move later? ⚠ **RULED AND CLOSED THE SAME DAY — option (a): stop at the door.** The feedback door stays and is finished here; marking rows `delivered` / `bounced` and the suppression list wait for Runbooks. See the decision log, 2026-09-06. |
| `DEF-INT-4118` | A connector can hold only ONE credential — `Manifest.auth` is a single `Auth` and the shipped database enforces one active credential per connection — so **InvoiceCloud**, who hold our key *and* whose key we hold, cannot be modelled. Allocated by hand from the register maximum (`allocate.py defect` returned 4118) and re-verified at push. |

⚠ **ALLOCATED BY HAND FROM THE REGISTER MAXIMUM, as every module-tagged id still must
be** — `file_defect.py`, `gates/common.py`, `g08`, `g17`, `g38` and `g50` all expect
digits immediately after the family, so nothing reads the `INT-` segment yet.
`allocate.py oq` returned **1727** as the next free number and
`allocate.py oq --verify 1727` was re-run at push time against the re-resolved tip, per
hard-won law 11: an allocated id is a blob and has to be re-derived, not remembered.

⚠ **`OQ-INT-1489` REMAINS UNUSED AND FREE** — the CR-069 documentation lane reserved
`OQ-INT-1470–1489` on 2026-09-03 and used through `1488`. **These three did NOT take
`1489`**, deliberately: the running number is the whole register's maximum plus one
under the PO's ruling of 2026-09-03 (*"register max"*), not the next gap inside an old
per-module block. Taking `1489` would have made these ids look like part of a block they
have nothing to do with, and would have hidden them from anyone re-deriving the maximum.

---

## `DEF-CWP-4165` – `DEF-CWP-4175` — CR-068 wave H, H4 (2026-09-06)

Eleven defect ids, taken by hand from the register's maximum because
`file_defect.py`'s `^"?DEF-(\d+)"?,` cannot read the module segment yet (CLAUDE.md,
*Screen IDs*). Filed in `12-governance/10-defect-log.csv` by the wave-H walkthrough
lane; three of them (`4165`, `4166`, `4167`) are fixed in the same commit range and
eight are open.

⚠ **THEY WERE ALLOCATED AT `4154`–`4164` FIRST AND RENUMBERED AT PUSH TIME, AND THE
RENUMBER IS THE POINT OF THIS ROW.** `allocate.py defect` answered `4154`, correctly,
against everything it could see. While this lane worked, a sibling in its own worktree
took `4154` and `4155` — rows that exist in NO ref a listing can read until they are
pushed. The push helper re-derives the register from the pinned tip **unconditionally,
on every push and not inside any conflict branch**, and it refused by name:

    REFUSING: a sibling took these ids while I worked: ['DEF-CWP-4154', 'DEF-CWP-4155']

That is hard-won law 11's *an allocated id is a blob too*, working — and specifically
its 2026-09-05 clause, which exists because a lane put the same re-derivation inside
the branch that resolves a CONFLICT on the register. The register merged CLEANLY here
too, as an append-only file almost always does; had the check been conditional it would
not have run, and the register would have published two lanes' rows under four shared
numbers.

The shift was `+11`, applied **descending** so an id could never land on one this lane
still held, and applied to all five files that cite them — the register itself, both
render-check scripts and the two `sample_data.py` files whose docstrings name them.
`allocate.py defect --verify 4165` was re-run against the re-resolved tip immediately
before the commit.

⚠ **`DEF-CWP-4154`–`4164` ARE NOT THIS LANE'S AND MUST NOT BE READ AS FREE.** Whatever
the sibling filed under them stands; this row exists so that a later reader who finds
`4154` cited in a stale scratch file does not conclude the register lost a row.

**A VERSION COLLIDED THE SAME WAY, AND THE ALLOCATOR COULD NOT SEE IT EITHER.**
`allocate.py version --bump fix` answered `2.197.6` twice, before and after a fetch,
because the tip stood at `2.197.5`. A sibling's commit message — read while syncing —
already claimed `2.197.6` for CR-068 wave G. This lane took **`2.197.7`** rather than
collide. The allocator removes the STALE read and cannot reserve; it says so in its own
docstring, and this is the rare case it names, caught by a human reading rather than by
a tool.


## 2026-09-06 · `DEF-INT-4223` — the OQ-INT-1728 / OQ-INT-1729 ruling lane

**One defect, no version, no code.** This lane wrote documents and registers only,
recording two PO rulings of 2026-09-06 (`OQ-INT-1728` and `OQ-INT-1729`, both CLOSED)
across the register, the decision log, `BR-INT-054`, `CR-069` §20, the execution plan,
two epics, the story list and the wave-task tracker.

| Id | What it records |
|---|---|
| `DEF-INT-4223` | `EP-INT-12` carried `OQ-INT-1470`, `1471` and `1472` as **OPEN** in four status cells, and still instructs a lane to raise `NotImplementedError` for two of them — while the register has carried all three as **CLOSED** since 2026-09-04 and the epic's own frontmatter says so. The status cells are corrected; the stub instructions are **not**, because what to build in place of each stub is wave `Q`'s work and this lane must not choose it. Found by walking somebody else's question, not by any gate. |

⚠ **ALLOCATED BY `10-scripts/file_defect.py --id-module INT`, which reads the REMOTE as
well as this tree** — the module segment is written into the id and the number is still
the register maximum plus one across every module. The register's own copy in this
worktree was **one row behind the tip** when the lane started, and was re-derived from
the tip (`git show <tip>:<path>`) **before** the row was appended: `file_defect.py`
reaches the remote for the ID and never for the BYTES (`DEF-3523`), so a stale tree
would have published the new row and subtracted a sibling's. The append measured
**1 insertion, 0 deletions**.

## 2026-09-06 · `OQ-RBS-1731`–`1736` — the Runbooks documentation pack

**Six open questions, no defects, no gate, no version, no code.** This lane wrote four
documents into `04-docs/05-modules/17-runbooks/` — `01-overview.md`, `05-user-stories.md`,
the five epics in `06-epics/` and `10-execution-plan.md` — and reserved the block below.

| Block | Lane | Opened | State |
|---|---|---|---|
| `OQ-RBS-1731–1736` | **THE RUNBOOKS PACK (2026-09-06) — `CR-075`, the five-phase plan.** ⚠ *This row read `CR-076` when it was written; the module's change request is `CR-075` and the correction is in the decision log of the same day.* The Product Owner asked that the specification's open decisions land in **phases 4 and 5** rather than blocking phases 1–3, and these are those six. **Phase 4:** `1731` the default cap for a first run · `1732` which actions need a second approval and above what amount · `1733` does an admin approve every run, or may a tenant set a runbook unattended once trusted. **Phase 5:** `1734` may a Check ever write a note to an account automatically · `1735` compose scope, which fields and steps a tenant may use · `1736` may closing the accounting period ever be automated. **USED: all six**, cited in `06-epics/EP-RBS-04`, `EP-RBS-05` and `10-execution-plan.md` §6. | 2026-09-06 | **ACTIVE** |

⚠ **TAKEN BY HAND, BECAUSE THE TOOLING DOES NOT READ THE MODULE SEGMENT YET.**
`file_defect.py`'s `^"?DEF-(\d+)"?,`, `gates/common.py`'s `OQ-\d{3,6}` and `g08`, `g17`,
`g38`, `g50` all expect digits straight after the family, so `OQ-RBS-1731` is invisible to
every one of them. The number is the register maximum plus one: **`OQ-MET-1730` was the
maximum, re-derived from the pinned tip immediately before this row was appended**, and no
`OQ-RBS` id existed anywhere in the register or in this file at that moment (checked, zero
hits in both).

⚠ **THE REGISTER ROWS THEMSELVES ARE NOT WRITTEN AND THAT IS DELIBERATE, NOT AN OVERSIGHT.**
This lane was scoped to four module documents and this reservation. **So
`12-governance/01-open-questions.md` currently has no row for any of the six**, and a lane
grepping the register for `OQ-RBS-1733` will find the citation in the epic and nothing behind
it. **The six questions are written out in full — question, phase, what blocks, and what is
built meanwhile — in `04-docs/05-modules/17-runbooks/10-execution-plan.md` §6**, which is
where their text should be copied from when the rows are minted. **Until then this
reservation is what stops the numbers being taken twice.**

⚠ **NONE OF THE SIX BLOCKS ANYTHING, AND EACH HAS A STATED *BUILT MEANWHILE* THAT PRE-EMPTS
NO ANSWER** — a required cap field with no default, a second approval on *every* money-bearing
action, every run approved by a person with the *"Unattended after"* parameter drawn
read-only, no automatic account note, a step library limited to what phase 5 has shipped, and
⚠ **ALL SIX ARE NOW ANSWERED (PO 2026-09-06), SO *BUILT MEANWHILE* NO LONGER APPLIES TO ANY OF
THEM — and one of the six was answered by being DISSOLVED rather than decided.** *“A step
library limited to what phase 5 has shipped”* described a TENANT reading a step library, and
`BR-RBS-042` rules that a tenant never sees one: the library is **ours**, an internal asset used
from wave `C`, and a tenant sets **input values** from a **tenant-resolved domain**. See
`OQ-RBS-1735` (CLOSED) and the decision log of 2026-09-06.
closing the period staying a named person's act. Each can only be *widened* by an answer,
never contradicted by one.

⚠ **TWO QUESTIONS THE SOURCE LEFT OPEN WERE DECIDED RATHER THAN MINTED, UNDER LAW 13** —
whether *Can we bill?* gives one verdict per tenant or one per service (decided: **per
service, rolled up to a tenant verdict**), and the minimum object set before a bill is
permitted (decided: **exactly runbook 1's ten steps**). Neither collides with a signed rule,
neither moves a ❄️ FROZEN B4/B5 figure, and neither is a fact only the Product Owner holds.
Both are written out with their reasoning in
`04-docs/05-modules/17-runbooks/01-overview.md` §8, **visible to overrule**. **No `OQ` was
minted for either, and no number from this block is spent on them.**

## 2026-09-07 · `OQ-RBS-1759` · `OQ-RBS-1760` · `DEF-RBS-4378` · `DEF-RBS-4379` · `DEF-RBS-4406` — `CR-075` runbooks 28 and 33

**Two open questions taken BY HAND and three defects allocated by the tool.** The build lane
for `US-RBS-043` (runbook 28) and `US-RBS-044` (runbook 33) also allocated the two story ids
by hand from `05-user-stories.md`'s own maximum (`042` → `043`, `044`); `US-` has no
allocator and no register beyond that file.

| Block | Lane | Opened | State |
|---|---|---|---|
| `OQ-RBS-1759` | **THE TEMPLATE LIBRARY CANNOT DRAW A RUNBOOK *UNAVAILABLE*, AND RUNBOOK 33 IS THE FIRST ONE THAT NEEDS IT.** Taken BY HAND — `gates/common.py`'s `OQ-\d{3,6}` and `g08`/`g17`/`g38`/`g50` all expect digits straight after the family, so an `OQ-RBS-` id is invisible to every one of them. **`1757` was taken first and was already gone**: `allocate.py oq --verify 1757` answered *TAKEN — a sibling pushed it*, and it turned out to be the disconnect-eligibility lane's weather-moratorium question. Renumbered to `1759` before the push, which is law 11's id clause working as written. | 2026-09-07 | **OPEN** · **USED**, cited from `definitions/budget_relevel.py` and `RB-133` |
| `OQ-RBS-1760` | **SHOULD A FIFTEENTH PORT MOVE A BUDGET LEVEL?** Taken by hand in the same breath as `1759` and re-verified at push time. | 2026-09-07 | **OPEN** · **USED**, cited from `definitions/budget_relevel.py`, its test and `RB-133` |
| `DEF-RBS-4378` | **TWO RUNBOOKS CITE OPEN QUESTIONS THAT WERE NEVER ISSUED.** Allocated by `10-scripts/file_defect.py` against the remote. ⚠ **`G106` was already reporting it** — *"OQ-RBS-1741 is cited at definitions/__init__.py:170 and no register ever issued it"* — among 37 red gates, which is hard-won law 7's *proved red, then never read* exactly. | 2026-09-07 | **OPEN** |
| `DEF-RBS-4379` | **`G115` HAS BEEN RED SINCE THE FOURTEENTH PORT LANDED** and its constant still reads thirteen. Dated with `git log -S` to `dff6b379` (the port) against `815777f0` (the constant). | 2026-09-07 | **OPEN** |
| `DEF-RBS-4406` | **`validate_report` CLOSES A PAYLOAD'S FIELD NAMES AND NOT THEIR SHAPES.** ⚠ **`4380` WAS CITED IN THE CODE BEFORE THE ALLOCATOR RAN AND THE ALLOCATOR ANSWERED `4406`** — twenty-six numbers had gone in the meantime — so every citation was corrected before the push. Writing an id into a comment before allocating it is the same mistake as computing `max + 1` from a stale read, one step earlier. | 2026-09-07 | **OPEN** |

⚠ **NO GATE NUMBER AND NO VERSION IS CLAIMED IN THIS BLOCK BEYOND `2.218.0`**, which was
taken with `allocate.py version --bump change` and re-verified free at push time.

## 2026-09-06 · `OQ-RBS-1737` · `DEF-RBS-4249` — the Runbooks module's first code, `CR-075` wave A

**One open question, one defect, one gate number, no version claimed in this block.** The
build lane for `CR-075` wave A created `06-backend/apps/runbooks/` (the twelfth code module),
`07-frontend/src/features/runbooks/`, `10-scripts/gates/g115_runbooks_import_census.py`, and
`04-docs/05-modules/17-runbooks/13-selector-inventory.md`.

| Block | Lane | Opened | State |
|---|---|---|---|
| `OQ-RBS-1737` | **HOW A RUNBOOK'S IDEMPOTENCY KEY IS COMPOSED (`CR-075` wave A, from `DEF-RBS-4246`).** Taken by hand as the register maximum + 1 (`1736` → `1737`), re-verified against the tip at push time. **USED**, cited from `06-backend/apps/runbooks/models.py` on the `idempotency_key` column, from `04-docs/02-decisions/02-database-design-brief.md` §2 `### Module: runbooks`, and from the human-review ledger row that withdraws the claim it invalidates. | 2026-09-06 | **ACTIVE** |
| `DEF-RBS-4249` | **A WRONG DOC POINTER THIS LANE SHIPPED AND THEN FILED ON ITSELF.** Allocated by `10-scripts/file_defect.py` against the remote, and re-verified free at push time. | 2026-09-06 | **CLOSED in the commit that opened it** |
| `OQ-RBS-1740` | **DOES `BR-INT-024`'s SKIP-AND-RECORD AND ITS *money ⇒ never catch up* BIND RUNBOOKS NOW THAT `BR-INT-054` HAS MOVED THE SCHEDULER (`CR-075` wave I).** Taken BY HAND as the register maximum + 1 (`1739` → `1740`; `1738` was taken by a sibling between allocation and push, and `allocate.py oq --verify` is what said so), because `gates/common.py`'s `OQ-\d{3,6}` and `g08`/`g17`/`g38`/`g50` all expect digits straight after the family and cannot yet read the module segment. Re-verified with `allocate.py oq` against the remote at push time. **USED**, cited from `12-governance/01-open-questions.md` and from the wave's decision-log row. | 2026-09-07 | **ACTIVE** |
| `G115` | **THE RUNBOOKS IMPORT CENSUS.** Allocated by `10-scripts/allocate.py gate` and re-verified with `--verify 115` in the same breath as the blob re-derivation — `DEF-CWP-3734` was three lanes each computing "the next free gate number" correctly and all getting the same answer. | 2026-09-06 | **ACTIVE** |

⚠ **`DEF-4246` WAS ALLOCATED BY THIS LANE, LOST TO A SIBLING, AND RENUMBERED BEFORE THE PUSH
— WHICH IS THE ID CLAUSE OF LAW 11 WORKING AS WRITTEN.** `file_defect.py` printed
`DEF-4246` correctly against everything it could see; twenty minutes later
`allocate.py defect --verify 4246` answered **`TAKEN — a sibling pushed it. Renumber before
you commit`**, and the row went out as `DEF-GOV-4248`. Nothing downstream would have caught
a duplicate in a 2,000-row register. **The verify is one command and it is the only moment
the answer can be final**; run it in the same breath as re-deriving the blob, never as a
branch of anything.

⚠ **AND THE ID THAT COLLIDED TURNED OUT TO BE THE COORDINATOR'S `DEF-RBS-4246`** — the
finding that the idempotency key contradicts its own worked example, which is what
`OQ-RBS-1737` above exists to settle. The collision was noise; the row behind it was the
most important thing that reached this lane all day.

---

## 2026-09-07 · the letters lane — `DEF-BIL-4448` … `DEF-BIL-4454`, and a collision caught the way the law says

**Reserved and FILED** (all seven are rows in `12-governance/10-defect-log.csv`):

| id | what | state |
|---|---|---|
| `DEF-BIL-4448` | the bill-ready email named none of its eleven values | fixed |
| `DEF-NOT-4449` | the notice generators, the staff resend and both send tests named none either | fixed |
| `DEF-PAY-4450` | the collections ladder's letters named none | fixed |
| `DEF-PAY-4451` | every disconnect notice was pinned to a template class that does not exist | fixed |
| `DEF-BIL-4452` | a bill's queue rows are pinned to a BILLING template, so the bill-ready email cannot be produced at all | open |
| `DEF-PAY-4453` | the friendly reminder pins `collections_reminder_<tone>`, catalogued nowhere | open |
| `DEF-BIL-4454` | `{correction_reason}` has no customer-facing sentence anywhere in this product | open |

⚠ **AND THE ALLOCATION COLLIDED EXACTLY AS LAW 11 PREDICTS, TWICE, AND BOTH TIMES THE
NUMBER WAS RIGHT WHEN IT WAS TAKEN.** `allocate.py defect` answered **4446** for this
lane; by the time the row was written the register carried `DEF-TEN-4446` (the
isolation suite's, pushed at `5b3fee9e`) and `DEF-CWP-4447`, neither of which existed
in any world this checkout could see when the number was computed. The coordinator hit
the same collision from the other side and said so.

**TWO THINGS THIS COST THAT ARE WORTH WRITING DOWN.**

**1 · `file_defect.py` CANNOT SEE A MODULE-PREFIXED ID, AND `CLAUDE.md` ALREADY SAYS
SO.** Its pattern is `^"?DEF-(\d+)"?,`, which does not match `"DEF-CWP-4447"`. So on a
register whose newest rows are all module-tagged it under-counts and hands back a
number that is already taken. The law's own instruction is the workaround — *"a
module-tagged id is taken BY HAND from the register's maximum"* — and the one command
that answers it honestly is:

    grep -oE '^"DEF-(([A-Z]{3})-)?[0-9]{3,5}' 12-governance/10-defect-log.csv \
      | grep -oE '[0-9]{3,5}$' | sort -n | tail -1

**2 · THE ID IS A BLOB, AND SO IS EVERY FILE NAMED AFTER IT.** Renumbering was not one
edit: the number was in two FILE NAMES (`test_def_4446_…py`, `def4446_letters_walkthrough.mjs`),
in their self-references, in a fixture's invoice number, in four test FUNCTION names
and in nine source comments across six modules. A two-phase swap through placeholders
was needed so a target id could not collide with a source id mid-remap. **The stale
`.pyc` beside the renamed test was deleted too** — an orphan `__pycache__` entry for a
module that no longer exists is the kind of thing that makes a later collection error
look like a code fault.

**The register already carries 13 duplicate numbers** — 4003, 4004, 4016, 4019, 4025,
4032, 4033, 4036, 4061, 4134, 4216, 4224, 4256 — and that is **dated, not assumed**:
the identical list comes back from `git show <tip>:12-governance/10-defect-log.csv`.
None of them is this lane's, and each is a pair that got past exactly this gap.

## `DEF-CWP-4442` — the portal offers two languages (2026-09-07)

**Defect closed:** `DEF-CWP-4442`. **Defects filed: `DEF-CWP-4491` and `DEF-4498`** — and each is
the SECOND number this lane allocated for that row, which is the point of writing this down.
`DEF-4492` was taken from under it by `DEF-GOV-4492` between filing and pushing, exactly as
`DEF-CWP-4489` had been by `DEF-MET-4489` an hour earlier. **Twice in one lane, on two different
rows.**

⚠ **`file_defect.py` FIRST RETURNED `DEF-CWP-4489`, AND A SIBLING PUSHED `DEF-MET-4489` WHILE
THIS LANE WAS STILL WORKING.** Two lanes computed *the register maximum plus one* correctly,
minutes apart, and got the same answer — law 11's own collision, exactly as it describes it.
Nothing downstream would have caught it: a duplicate id in a 2,254-row register reads as a
register. What caught it was `push_paths.sh` REFUSING the push on four moved paths, which sent
this lane back to re-read the register **out of the tip** rather than out of its own worktree.
Renumbered to `DEF-CWP-4491` after confirming the tip's maximum was `4490`.

⚠ **THE VERSION WENT THE SAME WAY.** `2.219.0` was taken by a sibling mid-flight; `2.219.1` was
re-verified free on every branch (`allocate.py version --verify 2.219.1`) before being written.

**`BR-CWP-106` minted** — *what the portal may OFFER, which is not what it can DRAW*. It is a
new row rather than a clause on `BR-CWP-105` deliberately: `BR-CWP-105`'s own last sentence says
the two registries answer different questions and must not be folded, and folding the RULES
would be the same mistake one level up. `BR-CWP-105` gained a dated correction where its text
still said this was the next lane's work.

**Screen ids: none minted.** `CWP-024` and `CWP-025` are `CR-068` §9's own.

**Gate numbers: none taken.** This change adds no gate, and the one check that can see it is not
a gate at all — no gate in this repository reads rendered output, so the guard is
`10-scripts/render-checks/def-cwp-4440-portal-language.mjs`, extended rather than duplicated.

**Open questions: none minted, and that is the deliverable rather than an omission.** Law 13:
the only thing here the Product Owner had to answer, they already had. What happens to an account
already holding `de` was a judgment, was made, and is in the decision log with its reasoning; a
tenant set outside the two turned out to need no new behaviour at all and is recorded the same way.

---

## `DEF-AUD-4507` and `DEF-TEN-4508` — allocated 2026-09-07 by the `OQ-AUD-1724` lane (the per-utility archiver)

Two defects. **`DEF-AUD-4507`**, self-reported while closing `OQ-AUD-1724`: the archiver gained a third
run status (`partial`) and the retention screen renders run statuses through a DYNAMIC translation key,
so eleven catalogues can be complete and still print the English word. Filed rather than fixed — this
lane was scoped to `06-backend/core/archival.py` and its tests, and the catalogues are another lane's
live surface.

**`DEF-TEN-4508`** came out of TAKING the isolation proof rather than out of writing code: an isolation
test that landed at 11:19 — seven minutes after the last recorded proof was taken — passes on its own,
passes after its eight immediate predecessors, and fails in the full 107-file run. Filed against tenancy
because the test is theirs; the measurement and the narrowing are in the row.

**The NUMBERS came from `file_defect.py` and then from `allocate.py`, which read the remote refs; the
module segments were supplied by hand** (`--id-module`), because the tooling still does not read the
module segment.

⚠ **AND THIS LANE WAS RENUMBERED FOUR TIMES IN ONE AFTERNOON, WHICH IS THE POINT OF WRITING IT DOWN.**
It first took `4492` and a sibling filed `DEF-RAT-4492` while the row was being written — **the module
segment does NOT make a number unique**: CLAUDE.md says one running number across the whole register, so
`DEF-AUD-4492` beside `DEF-RAT-4492` would have been a duplicate wearing two prefixes. Then `4498` went
the same way, and then `4505` went while the push itself was in flight — *"TAKEN — a sibling pushed it.
Renumber before you commit"* each time. **What finally worked was not allocating more carefully, it was
moving the allocation INSIDE the push loop**, so the numbers are taken from the remote on the same
attempt that writes them and a lost push race renumbers rather than collides. That is law 11's
unconditional re-derivation applied to ids instead of to bytes.

⚠ **TWO VERSION COLLISIONS HAPPENED THE SAME AFTERNOON AND ARE THE SAME MECHANISM ONE FAMILY OVER**:
`2.219.1` and `2.219.2` were each free when this lane bumped and TAKEN by a sibling before it could push.
`allocate.py version --verify` caught both and the lane landed on `2.219.3`. Nothing was lost either
time, which is the point of running the verify in the same breath as the blob re-derivation rather than
at bump time.

---

## 2026-09-07 — `BR-WRK-058`, the two PO rulings on work order types

**Open questions minted: TWO, taken BY HAND from the register's maximum (1763) because
the tooling still cannot read the module segment.** `file_defect.py`'s
`^"?DEF-(\d+)"?,`, `gates/common.py`'s `OQ-\d{3,6}` and `g08`/`g17`/`g38`/`g50` all
expect digits immediately after the family, so a module-tagged id is allocated here
rather than by a script (CLAUDE.md, "Screen IDs").

* **`OQ-WRK-1764`** — a gas-only utility now has no *Billing Issues*, no *Meter
  Change* and no *Re-read*; should the eleven service-neutral rows among water's
  eighteen be common to every service? Raised because the PO was shown *No Water
  Supply* and *Water Truck Services* and answered about those; the eleven were never
  put to them, and re-carving their own list unasked is the mistake the first ruling's
  entry exists to avoid.
* **`OQ-WRK-1765`** — which priority each of the nine types gets by default, with the
  response time each one promises. The PO ruled *"Yes"* to WHETHER; a priority carries
  SLA hours and stamps `due_at` at raise, so WHICH is a promise to a customer.

**Migration numbers: `work/0024` taken.** `0022` (the column) and `0023` (the data)
were this lane's earlier today; `0024` is the retraction the second ruling needs. The
work graph has one leaf, asserted.

**Business rules: none minted.** `BR-WRK-058` already exists and is AMENDED in place
with both rulings, dated — a second rule id for the same subject would be two places
to look for one fact.

**Defect numbers: none taken.** Neither ruling is a defect: the first list was seeded
exactly as ruled and the scoping question was raised by this lane rather than reported
against it. The window `work/0024` closes is the consequence of a ruling landing
between two commits, which the decision log records as such.

**Screen ids · gate numbers: none.** No screen and no gate; the only check that can
see the card is `10-scripts/br_wrk_058_type_levels_walkthrough.mjs`, which is a
walkthrough and not a gate, because nothing in this repository reads rendered output.
| `DEF-RAT-4514–4516` | **THE GAS USAGE PRICE LANE (2026-09-07)** — PO: *"please fix this gap - One real gap, and it is money. Gas bills $0.00 usage"*. Taken BY HAND because `file_defect.py`'s own `max + 1` returns **4512, which is TAKEN**: `DEF-MET-4512` is already cited twice from `06-backend/core/sample_fixture.py` by a sibling lane whose register row is not pushed, so it is invisible to every listing `file_defect.py` can read. `10-scripts/allocate.py defect --verify 4512` is what said so — *"TAKEN — a sibling pushed it. Renumber before you commit"* — and 4513/4514/4515 came back free. ⚠ **THEN IT HAPPENED AGAIN, AT PUSH TIME, WHICH IS THE WHOLE POINT OF RE-VERIFYING THERE:** while this lane worked, a sibling pushed **`DEF-WRK-4513`**, so the gas row moved `4513` → **`4516`** and the block is `4514`–`4516`. The re-derivation of every register blob from the pinned tip is what surfaced it — the append would otherwise have published a duplicate id into a 2,246-row register, where a duplicate reads as a register and not as an error. **This is CLAUDE.md law 11's *an allocated id is a blob too*, twice in one lane: once at allocation and once at push.** The three ids are NOT contiguous by topic and that is deliberate — renumbering the other two to keep them tidy would have moved citations that were already correct. **USED: all three.** `DEF-RAT-4516` is the gas `$0.00` usage line itself. `DEF-TEN-4514` and `DEF-RAT-4515` are two reds found BESIDE it and filed rather than dismissed, per law 7's *read the failures you did not cause*: `4514` is `update_tenant_service` enforcing no role at all, so US-TEN-007 TC-1's server-side refusal has never fired; `4515` is four cases of `test_def2397_service_shaped_rating.py` red on the industrial electric base charge code. **Both were dated by MEASUREMENT, not by `git log -S`** — a second detached worktree at the branch tip with zero edits reproduces each of them, which is the method this branch's squashed whole-tree imports make necessary. | 2026-09-07 | **ACTIVE** |
| `DEF-GOV-4517–4517` | **`allocate.py --verify` COUNTS THE CALLER'S OWN PUSHED COMMIT MESSAGE AS A COLLISION (2026-09-07).** Taken by hand as the register maximum + 1 and re-verified against the remote at push time, the same way as the `DEF-RAT-4514–4516` block above. Filed by the gas-price lane immediately after being told its own two ids were `TAKEN — a sibling pushed it` when no sibling had: the "sibling" was that lane's own first commit, whose message names the ids it is about to file. **USED**, cited from `12-governance/10-defect-log.csv` and from the decision log of 2026-09-07. | 2026-09-07 | **ACTIVE** |

---

## 2026-09-07 · CR-084 (the customer portal as a notification channel) + DEF-NOT-4531/4532

**Defect numbers: `DEF-NOT-4531` and `DEF-NOT-4532`, TAKEN BY HAND, and here is why
that was necessary rather than lazy.** `10-scripts/file_defect.py` reads the register
with `^"?DEF-(\d+)"?,` — digits immediately after the family — so it cannot see a
module-tagged id at all. Asked for the next free number it answered **4512**, which is
**nineteen behind the truth**: `10-scripts/allocate.py defect` asks every remote branch
and answers **4531**, and the register's own last two rows are `DEF-CWP-4510` and
`DEF-GOV-4511`. CLAUDE.md's ID grammar section already prescribes exactly this — *"until
they learn an optional `(?:[A-Z]{3}-)?`, a module-tagged id is taken BY HAND from the
register's maximum and reserved in `14-id-reservations.md`"* — so this is that
reservation. Both were re-verified against the remote at push time
(`allocate.py defect --verify`), which is the only moment the answer can be final.

**Change request: `CR-084` taken**, from the register's own *Next free number* line,
which is bumped to `CR-084` in the same commit. `allocate.py` has no `cr` family.

**Business rules: `BR-NOT-1031` minted.** `BR-NOT-028` was the obvious next number and
is **already taken** (the template change-note rule, `CR-062`); the notifications table
passed `BR-NOT-029` some time ago and its live maximum is `BR-NOT-1030`. Checked by
grepping the whole repository rather than the table alone, because a rule cited from
code before it reaches the table is exactly how a number gets used twice.
`BR-NOT-010` is AMENDED IN PLACE with its date and is not renumbered.

**Migration numbers: none taken, and that is worth stating.** `outbound_messages.channel`
is a plain `TextField` with no CHECK constraint and no choices, so a fifth channel needs
no DDL. `stored_documents.channel` DOES carry one (`ck_stored_documents_channel`) and is
deliberately NOT widened: the portal freezes nothing, because it serves the artefact
another route already froze.

**Screen ids: none.** The channel row is drawn by `S8`'s existing Channels table from
data the server already serves.

**Gate numbers: none.** The two guards are pytest files, which is the harness that will
actually run them.

---

## 2026-09-08 · CR-081 (sewer on the water VOLUME) — `OQ-RAT-12347` + `BR-RAT-1015`

**Open question: `OQ-RAT-12347`, TAKEN BY HAND, and the number is not a typo.**
CLAUDE.md's ID grammar prescribes exactly this — *"until they learn an optional
`(?:[A-Z]{3}-)?`, a module-tagged id is taken BY HAND from the register's maximum and
reserved in `14-id-reservations.md`"* — and `allocate.py` has no `oq` family. The
maximum was computed with the ruled pattern `OQ-(?:[A-Z]{3}-)?\d{3,5}(?!\d)` across
`01-open-questions.md`, `02-decision-log.md`, `11-change-requests.md` and this file,
and it is **12346**, so the next free is **12347**.

⚠ **THAT MAXIMUM IS FIVE DIGITS AND THE LIVE QUESTIONS ARE FOUR, WHICH LOOKS WRONG
AND IS NOT.** The register's highest OPEN question is `OQ-RAT-1766`; the 12346 comes
from an id cited elsewhere in the four files searched. The rule says *the register's
maximum + 1*, so that is what was taken — **ids stay unique, which is the whole point**,
and nothing is renumbered (`OQ-291` is `OQ-291`, never `OQ-00291`). A lane that takes
`1767` instead because it "looks tidier" is the one that collides.

**USED.** `OQ-RAT-12347` is the seventh sewer figure — `WE-6`/`GT-22`, which the
2026-09-08 re-sign did not cover — together with the six downstream payments and ledger
examples that consume `WE-1`'s total. It is cited from `01-open-questions.md`, the
decision log, the change request, the review ledger, the billing workbook,
`10-scripts/03-golden-verify.py`'s Part 4 and
`apps/rating/pricing/models/percent_of_service.py`'s trailer.

**Business rule: `BR-RAT-1015` minted.** `BR-RAT-016` and everything near it is long
taken; the rating table passed 999 some time ago and its live maximum is `BR-RAT-962`,
so the successor to `BR-RAT-015` is minted in the 1000-block beside `BR-RAT-1011`
(`CR-078`, 2026-09-07) rather than renumbered. **`BR-RAT-015` is NOT renumbered and NOT
deleted** — six ❄️ frozen figures and a dozen docstrings cite it by name, and a reader
meeting `$15.80` in an older document needs to be able to date it. It is marked
SUPERSEDED in place, with its successor named.

**Migration number: `rating/0028` taken**, checked against the remote rather than this
checkout (`0027_cr078_backfill_plan_late_fee_charge` is the tip's last).

**Version: `2.230.0`**, a CHANGE bump. `allocate.py version --verify 2.230.0` was re-run
at push time and answered *still free on every branch* — after a sibling had taken
`2.229.3` while this lane worked, which is exactly the read the verify exists to catch.

**Defect numbers: none taken.** Nothing here is a defect: the rule changed, it was
ruled, and the gap that remains is a QUESTION for the PO rather than a fault.

**Gate numbers: none.** The new guard is Part 4 of `10-scripts/03-golden-verify.py`,
which is the harness that will actually run it.

**Screen ids: none.**


## 2026-09-12 · `CR-092-BRC01` step 2 wave C lane 3 — `DEF-MET-4995`, `BR-AST-535`, `BR-AST-536`, version `2.237.8`

**Defect: `DEF-MET-4995`**, allocated by `10-scripts/file_defect.py` (which asks the
REMOTE, not this checkout) and pushed **before** the fix was written, per step W —
a defect is filed before it is fixed so the record shows it was found rather than
quietly repaired. It is the three lists inside an asset answering the whole
history; `/assets/{id}/maintenance` in particular appeared in **no register row at
all**, which is the half wave B lane 2 named and nobody had filed.

**Business rules: `BR-AST-535` and `BR-AST-536` minted.** The assets table's live
maximum was `BR-AST-534` (`CR-092` step 2 lane 4, the same day), so these are the
next two and nothing is renumbered. Verified free across every `refs/remotes/origin`
ref before they were written, not merely against this worktree — `git grep -l` over
the remote refs returned **0 files** for each. ⚠ `allocate.py` has no `BR` family, so
this is the hand path the CLAUDE.md id rule describes, and the check that makes it
safe is the remote grep rather than a `max + 1` over a local copy.

**Version: `2.237.8`**, a FIX bump. `allocate.py version --bump fix` answered it while
`2.237.7` was landing in a sibling commit — which is the read the allocator exists to
correct, and it corrected it: this lane's worktree still held `2.237.6` at the time.
**Re-verify at push time.**

**Open questions: none minted.** Nothing here needed a PO answer. The two judgments
the rules did not settle — two envelope shapes rather than one, and the Reads tab
paging by DATE rather than by row — are recorded in `12-governance/02-decision-log.md`
with their worked figures, which is what hard-won law 13 asks for: *a judgment call
recorded in the decision log with its reasoning is the deliverable; a question is the
failure to make one.*

**Migration numbers: none taken.** No stored column moves, so B2 is untouched.

**Gate numbers: none taken.** `NFR-3` still has no gate and this lane did not mint
one — the honest reason is that a check which enumerates every list-shaped route and
asks whether its view reaches the paginator is a piece of work in its own right, and
half of it (one that only reads this module) would report zero over a scope it
silently excludes, which is the `G32` shape law 7 names.

## 2026-09-13 · `OQ-BIL-12348` — the `Adjust` wave (`DEF-CUS-5126` / `DEF-PAY-5128`)

**Open question: `OQ-BIL-12348`, from `10-scripts/allocate.py oq`, which answered `12348`.**
The maximum it reports is five digits while the live questions are four, for the reason the
`OQ-RAT-12347` note above already records: the rule is *the register's maximum + 1*, the
maximum comes from an id cited elsewhere in the four files searched, and **a lane that takes
`1767` instead because it looks tidier is the one that collides.** Re-verified with
`allocate.py oq --verify 12348` at push time.

⚠ **THE NOTE ABOVE SAYS `allocate.py` HAS NO `oq` FAMILY. IT HAS ONE** — `allocate.py oq`
runs and asks the remote, which is strictly safer than the by-hand count that note
prescribes (law 11: a hand count reads only this checkout). Corrected here rather than
left, because a reader who believes it goes back to counting by hand.

**Defects:** `DEF-CUS-5126` and `DEF-PAY-5128`, both from `10-scripts/file_defect.py`
against the remote. `DEF-PAY-5127` was allocated and then **refused by the tool before
anything was written** — *"taken while this run was reading the remote"* — which is law 11's
id clause catching a live collision at the only moment it can be caught; refiled as `5128`.

---

## `CR-096`–`CR-099`, suffix `BRC02` — BRANCH `claude/hi-0jmv62`, Meter Reads (2026-09-13)

**The block is CLAIMED here before use**, which is what this file exists for: *"a branch that
starts work without writing its name here is the promise-in-a-chat-message this whole file
exists to replace."*

⚠ **`CR-095` WAS ALREADY GONE WHEN THE BLOCK WAS CLAIMED, SO `BRC02` OPENS AT 096.** Verified
against the REMOTE at the moment of use rather than trusted from this file:
`allocate.py cr --verify 95` answers **TAKEN — a sibling pushed it**; `96` and `97` answer
*still free on every branch*.

**That is the second block breached before its owner reached it** — `BRC01` lost `CR-090`
and `CR-094` the same way on 2026-09-10. The lesson is unchanged and is worth restating
because it has now cost three numbers: **the SUFFIX does not make a number unique.**
`CR-095-BRC02` and a sibling's `CR-095-BRCxx` are different STRINGS that git merges
cleanly, and a NUMBER is what a person says out loud. What catches it is
`allocate.py cr --verify` asking the remote at the moment of use, and `G17`, which fails a
duplicate number even when the suffixes differ.

**Nothing is renumbered.** The sibling's `CR-095` is real and pushed.

**USED: `CR-096-BRC02`** — Meter Reads against its blueprint. `CR-097`–`CR-099` remain FREE.

**Reserved 2026-09-13 · ACTIVE.**

## `CR-100`–`CR-104`, suffix `BRC03` — BRANCH `claude/eager-johnson-r0k88b`, Billing (2026-09-14)

**Claimed here before use**, which is what this file is for. Row 52 has held `BRC03` OPEN since
2026-09-10 with the instruction *"the third concurrent branch takes this block and writes its
branch name into this row on the day it starts"* — this is that branch and this is that day.

| | |
|---|---|
| Block | **`CR-100`–`CR-104`**, suffix **`BRC03`** |
| Branch | `claude/eager-johnson-r0k88b` |
| Work | **Billing, step 1** — measuring the seven Billing addresses against `05-prototype/04 Billing, As Built.pdf` |
| First id | **`CR-100-BRC03`** |
| Verified | ⚠ `allocate.py cr --verify 100` answered **TAKEN**, and that is a **FALSE POSITIVE** — `DEF-GOV-5224` |

⚠ **THE ALLOCATOR REPORTS THIS BLOCK'S OWN ENDPOINTS AS TAKEN, AND THE INSTRUCTION IT PRINTS
WOULD HAVE MADE ME ABANDON A BLOCK I LEGITIMATELY HOLD.** `--verify` said TAKEN for `CR-100`
and `CR-104` and FREE for `101`, `102`, `103` — exactly the two numbers row 52 spells out
(*"`CR-100-BRC03` … `CR-104-BRC03`"*) and not the three it leaves to an ellipsis. The only
place either id appears on any branch is that row. **No `CR-100` or `CR-104` file exists on
any branch**, verified with `git ls-tree -r --name-only` across every `origin` ref.
**So the block is whole and this claim stands at 100.** Filed as `DEF-GOV-5224`, because the
failure is asymmetric: a false FREE is caught by `G17` at merge, and a false TAKEN is caught
by nothing — abandoning a free number looks exactly like caution.

⚠ **THE SUFFIX IS PROVENANCE, NOT UNIQUENESS.** Two branches can both reach for 100 and write
`CR-100-BRC03` and `CR-100-BRCxx`: the STRINGS differ, git merges both cleanly because one file
per CR means they touch different files, and **the NUMBER — which is what a person says out loud
and cites from a business rule — collides silently.** What makes it unique is this block being
disjoint, `allocate.py --verify` at push time, and `G17`, which fails a duplicate number even
when the suffixes differ.

⚠ **TWO BLOCKS HAVE ALREADY BEEN BREACHED BEFORE THEIR OWNER REACHED THEM** — `BRC01` lost
`CR-090` and `CR-094` on 2026-09-10, and `BRC02` opened at 096 because `CR-095` was gone by the
time it was claimed. **So this block is verified again at push time, not just here**, and if
`CR-100` is taken by then this row is amended rather than the number being used anyway.

**USED so far: `CR-100-BRC03`** — Billing step 1. `CR-101`–`CR-104` remain FREE.

⚠ **NO VERSION IS TAKEN.** Step 1 builds nothing, and `13-change-process.md` step 7 attaches a
version to a CR that SHIPS. The next free bump is `2.262.0` (current `2.261.4`), and it is left
free for whoever ships first — taking one here would be the `DEF-GOV-3756` mistake (two lanes
both shipped `2.141.0`) with an extra day for it to go stale in.

## `CR-101-BRC03` — Billing STEP 2, the build (2026-09-14)

Taken from this branch's own block (`CR-100`–`CR-104`, claimed above). **`CR-100-BRC03` was
step 1; this is the build it scopes.**

| | |
|---|---|
| Branch | `claude/eager-johnson-r0k88b` |
| Work | **Billing step 2** — building the 281 items step 1's two-way diff routed to `build` |
| Scoped from | `04-docs/05-modules/07-billing/conformance/CR-100-BRC03-billing-step1.md` |
| Version | **NOT TAKEN YET.** Allocated at first ship, not here — `DEF-GOV-3756` was two lanes both writing `2.141.0` |

⚠ **`allocate.py cr --verify 101` ANSWERED `TAKEN` AND IT IS THE FALSE POSITIVE `DEF-GOV-5224`
RECORDS.** Checked the way that defect's own prevention clause prescribes: **no `CR-101` file
exists on any branch** (`git ls-tree` across every `origin` ref), and the string's only
occurrence in the tree is **this file's own row above**, which says `CR-101`–`CR-104` are
free. **The allocator counts an id where it is WRITTEN ABOUT, not where it is USED**, so a
reserved block reports its own spelled-out endpoints as taken. Second time in one day; the
first cost nothing because the row was already filed.

**USED: `CR-100-BRC03`** (step 1) · **`CR-101-BRC03`** (step 2) · **`CR-103-BRC03`** (the Budget Bills journey, blueprint §05 entries 25–25.4, MAINTENANCE).

⚠ **`CR-102` AND `CR-104` ARE GONE TO SIBLINGS AND THIS ROW SAID THEY WERE FREE.** `10-scripts/allocate.py cr --verify 102` answers *"TAKEN — a sibling pushed it"* and `--verify 104` the same; only `103` verified free, and it was re-verified against the REMOTE in the same breath as the push. **A reserved block is not a held block** — nothing writes to the remote when a block is claimed here, so a sibling outside this branch's convention can and did take numbers inside it. The line above is corrected rather than deleted because that is the fact worth keeping: **verify at push time, every time, and never from this row.**

---

## `CR-105`–`CR-109`, suffix `BRC03` — BRANCH `claude/eager-johnson-r0k88b`, the bill run rebuild (2026-09-14)

| | |
|---|---|
| Branch | `claude/eager-johnson-r0k88b` |
| Block | `CR-105` · `CR-106` · `CR-107` · `CR-108` · `CR-109` |
| Suffix | `BRC03` |
| Claimed | 2026-09-14, **before use**, per `13-change-process.md` step 0 |
| Verified | `allocate.py cr --verify 105/106/107` answered *still free on every branch* at claim time; **each is re-verified against the REMOTE at push time, which is the only moment the answer can be final** |

⚠ **WHY A NEW BLOCK: `CR-100`–`CR-104` IS SPENT, AND TWO OF ITS FIVE WENT TO SIBLINGS.**
`allocate.py cr --verify` answers **TAKEN** for all five. Three are ours — `CR-100-BRC03`
(billing step 1, the as-built diff), `CR-101-BRC03` (step 2, the four rails), `CR-103-BRC03`
(the Budget Bills journey). **`CR-102` and `CR-104` were taken by sibling branches out of a
block reserved here**, which is the second time this has happened to a reserved block: the
`BRC01` row above records the same thing for `CR-090` and `CR-094` on 2026-09-10.

**The lesson is already written in that row and it held again: the SUFFIX does not make a
number unique.** `CR-102-BRC03` and a sibling's `CR-102-BRCxx` are different strings in
different files and git merges them cleanly. What caught it both times is `allocate.py --verify`
asking the REMOTE at the moment of use, and `G17`, which fails a duplicate NUMBER whatever the
suffix. **A reservation is a courtesy to branches that read this file; the verify is the thing
that actually protects you.**

⚠ **AND THE PO HAS STATED THERE IS NO PARALLEL BRANCH NOW** (2026-09-14: *"there is no paralle
branch"*). That lowers the collision risk for this block and **does not remove the verify
step** — the two losses above happened while this file said a block was reserved, and a branch
that starts tomorrow will not have read this sentence.

### Allocated from this block

| Id | For | Status |
|---|---|---|
| `CR-105-BRC03` | **The bill template is decided at step 1 Scope** — PO ruling 2026-09-14. The one true CHANGE in the bill-run rebuild; everything else is defect work under `DEF-BIL-5247` and its siblings | **USED 2026-09-14** |
| `CR-106`–`CR-109` | unallocated | free |

**Nothing else taken.** The rebuild's remaining work is routed as DEFECTS on purpose —
`13-change-process.md` §1: *when it is ambiguous it is a DEFECT, not a change, because filing
our misunderstanding as a "change" quietly converts our error into the customer's new
requirement.* The product not matching a drawing the PO signed is our miss, not their change.

## `CR-103-BRC03` §05 entry 25.3 `Asks` — ids taken 2026-09-15 (branch `claude/eager-johnson-r0k88b`)

| | |
|---|---|
| Used | **`OQ-BIL-12359`** · **`DEF-CWP-5330`** · **`DEF-BIL-5331`** · **`DEF-BIL-5332`** |
| Version | **`2.274.0`** (`allocate.py version --bump change`, re-asked after a sibling moved the tip from `2.272.2` to `2.272.3` mid-lane) |
| Nothing else taken | No `CR` number — this is `CR-103-BRC03` continued, the same change request's next wave. No `BR` minted: nothing here states a new rule, and the one rule that would have to move (`BR-CWP-026`) is the PO's, which is why it is an `OQ` and not an edit. No gate number. |

**The `OQ` was taken as the register's MAXIMUM PLUS ONE, which is `12359` and not `1811`.**
`12-governance/01-open-questions.md`'s highest row is `OQ-BIL-12358`, and CLAUDE.md's rule is
*"one running number across the whole register (the register's maximum + 1, so ids stay
unique)"*. ⚠ **Two earlier rows in this file record the OPPOSITE reading** — that
`OQ-RAT-12347` is *"five digits where every neighbour is four … reading it as the watermark
would skip ten thousand numbers for ever"* — and that was a fair call on 2026-09-12, when there
was exactly ONE such id. **There are now twelve, `12347`–`12358`, four of them `OQ-BIL-`,
minted by several lanes over three days.** A frontier that twelve rows have already crossed is
the frontier. Taking `1811` instead would have landed inside `CR-094-BRC01` lane 4's reserved
`OQ-CUS-1810–1819`, which is the collision this file exists to prevent.
`allocate.py oq --verify 12359` answered **still free on every branch**; ⚠ `allocate.py oq`
bare still answers `12348`, which is the documented prose-scan over-read of `CLAUDE.md`'s own
worked examples and not the frontier.

**The three defect ids came from `file_defect.py`**, which reads the register AND the remote,
and were re-verified free before the push.

⚠ **ONE OF THEM WAS CITED IN CODE BEFORE THE ALLOCATOR HAD ANSWERED, AND `G106` CAUGHT IT.**
`apps/billing/customers_seam.py` was written naming **`DEF-BIL-5327`** — a number this lane
guessed from `allocate.py defect`'s answer of `5326` before the module prefixes were assigned —
while the row that finding actually held at the time was `DEF-BIL-5328`. `G106 cited-ids-exist`
named it by file and line, because `DEF-BIL-5327` had never been issued under that prefix.
Corrected before the push, and G106's detail then matched the pristine tree's byte for byte.
**The rule it teaches is the one written two rows above: cite nothing until the allocator has
answered.**

⚠⚠ **AND THE NUMBERS THEN COLLIDED THREE TIMES, WITH THREE DIFFERENT SIBLINGS, ACROSS THREE
TIPS — WHICH IS LAW 11's ID CLAUSE EARNING ITS KEEP RATHER THAN BEING QUOTED.**
`file_defect.py` allocated `5327`, `5328`, `5329` against tip `679329eb`. At push time — and
**unconditionally, as one step on every attempt rather than as a branch of anything** — every id
was re-verified against the CURRENT remote, and three times the answer was **TAKEN**:

| Tip pinned | Who had taken what | This lane's rows became |
|---|---|---|
| `56be25eb` | the **§05 entry 25.2 settle-up lane** pushed `DEF-BIL-5327` and `DEF-BIL-5328` | `5329` · `5330` · `5331` |
| `e4818a8e` | another lane pushed `DEF-BIL-5329` (*"the G7 blind spot final_bill.py sits in"*) | `5330` · `5331` · `5332` |
| `a8a69404` | re-verified again before the push that landed | unchanged |

**Every lane's arithmetic was right every time.** What was wrong was *which world the maximum
came from* — a sibling in its own worktree has its rows in none of the places a listing can see
until it pushes. `allocate.py --verify` cannot RESERVE and does not claim to; it removes the
stale read, and it caught all three.

**This lane's rows moved UP each time and no sibling's row was touched**, which is the only safe
direction: their ids were already on the branch and cited in their own files, and nothing of this
lane's had been pushed, so nothing downstream was orphaned by renaming.

| Filed as | Landed as | Subject |
|---|---|---|
| `DEF-CWP-5327` | **`DEF-CWP-5330`** | a level-pay ask tells the customer to bring a document that does not exist |
| `DEF-BIL-5328` | **`DEF-BIL-5331`** | a finding "reported" in one docstring and filed in no register for fourteen days |
| `DEF-BIL-5329` | **`DEF-BIL-5332`** | the Billing blueprint argues from an open question the PO closed the day before it was drawn |

Renumbered each time by a **single-pass mapping** over every file that cites them, because a
sequential rename would have rewritten this lane's own fresh `5330` into `5332` on the second
pass. The script REFUSES when a clash is detected and nothing changes, and REFUSES when it lifts
anything other than exactly three rows out of the register.

⚠ **AND `push_paths.sh` REFUSED THE FIRST ATTEMPT, CORRECTLY** — six paths had moved between
the base and the tip while the record was being written (the three version literals, the review
ledger, the defect register and `CHANGELOG.md`). That is the guard law 11 asks for, working on
this lane. The answer was to re-derive, not to force.

**`OQ-BIL-12359` was free at every one of those tips.** The VERSION was re-bumped from the
**tip's own literal** on each attempt rather than from a number computed once: the tip went
`2.272.2` → `2.273.0` → `2.273.2` under this lane, and `2.274.0` is the change-bump of the last
of those. ⚠ `allocate.py version --bump change` answered **`2.275.0`** when run inside this
lane's own worktree and **`2.274.0`** from a clean worktree at the tip, because the allocator
counts this checkout too and this checkout already held the answer. **Ask a tree that does not
contain your own work.**

---

## `CR-094-BRC01` LANE G — the date of birth and the driving licence on a service request (2026-09-15)

**TAKEN:** `DEF-CUS-5409`, `DEF-CUS-5410`, `DEF-CUS-5411` · migration **`customers 0050`**.

⚠ **THEY WERE FILED AS `DEF-CUS-5406` AND `DEF-CUS-5407` AND BOTH NUMBERS WERE GONE BY THE TIME
THIS LANE PUSHED — TWO SIBLING LANES TOOK THE SAME TWO NUMBERS FOR DIFFERENT DEFECTS.**
`file_defect.py` allocated them correctly against the remote at the moment they were FILED; the
siblings' rows were in nobody's remote yet. Four rows then sat in the register carrying two ids,
and **a duplicate id in a 2,982-row register reads as a register, not as an error** — `G17` is the
only thing that saw it. Renumbered here with all 15 citations moved in the same commit; the other
lanes' rows keep 5406 and 5407 because theirs landed first. `DEF-CUS-5411` is the row filed about
the collision itself. **THE LESSON IS ONE CLAUSE OF LAW 11 THAT THIS LANE READ AND DID NOT DO:**
*"at push time, re-derive BOTH: the file content AND the ids."* The content was re-derived from the
pinned tip on every push; the ids were not. `10-scripts/allocate.py defect --verify <n>` exists for
exactly this and now runs in this lane's push helper beside the blob re-derivation, as one act.

⚠ **THE MIGRATION NUMBER MOVED TWICE WHILE THIS LANE WAS BUILDING, AND THAT IS THE ROW WORTH
READING.** It was written as `customers 0047`, and by the time it was pushed a sibling had landed
`0047_cr094_service_request_applicant_messages` and `0048_cr094_request_raises_the_job`; renumbered
to `0049`, and a third lane had landed `0049_br_cus_1055_units_on_property`. Two files at one number,
both depending on the same parent, is **two leaf nodes** — and Django then refuses **every test in
the process** with *"Conflicting migrations detected; multiple leaf nodes in the migration graph"*,
which names neither lane and reads like a broken tree (`DEF-2872`, hard-won law 12).

**It cannot be seen from either lane's own checkout**, because the collision does not exist there.
`allocate.py` has no migration family to ask, and `14-id-reservations.md` records a number only
after a lane has chosen one. So the working rule this lane used, and recommends: **re-seat the
migration on the live leaf at push time, in the same unconditional step as the blob re-derivation**
— `ls` the tip's migrations directory, take `leaf + 1`, rewrite the `dependencies` line, and let
`makemigrations --check` refuse the push if the graph is not single-leaf. A number taken when the
file is written is a guess; only the one taken at push time is a reservation.

---

## `CR-110`–`CR-114`, suffix `BRC04` — BRANCH `claude/gifted-johnson-top7zn`, Connectors (2026-09-16)

**CLAIMED 2026-09-16, before the first CR in it was written**, which is what
`13-change-process.md` step 0 asks and what the three breached blocks above show the
cost of skipping.

⚠ **`CR-105`–`CR-109` ARE GONE, SO `BRC04` OPENS AT 110 AND NOT AT 105.**
`allocate.py cr` answers **110** against the REMOTE; `--verify 106` and `--verify 107`
both answer *TAKEN — a sibling pushed it*, and `CR-105-BRC03` is on the branch. Every
number `110`–`114` was verified free on every branch at the moment of claiming:

    cr 110: still free on every branch (this tree not counted)
    cr 111: still free on every branch (this tree not counted)
    cr 112: still free on every branch (this tree not counted)
    cr 113: still free on every branch (this tree not counted)
    cr 114: still free on every branch (this tree not counted)

**USED: `CR-110-BRC04`** — Connectors, the Integration Blueprint built. The PO asked
for **one** change request covering all of it (*"measure all screens- why 5 crs - why
not 1"*, then *"please od it 1 cr"*), so `111`–`114` are held for this branch and are
expected to stay unused. They are claimed anyway rather than left open, because an
unclaimed block is what a sibling reaches into — which is exactly how `BRC01` lost
`CR-090` and `CR-094`, and `BRC02` lost `CR-095`, all before their owners arrived.

⚠ **THE SUFFIX DOES NOT MAKE THE NUMBER UNIQUE AND THIS ROW IS NOT WHAT PROTECTS IT.**
`CR-110-BRC04` and a sibling's `CR-110-BRCxx` are different STRINGS in different FILES,
so git merges both cleanly and the index row is an append on each side — nothing goes
red. What protects the number is `allocate.py cr --verify <n>` asking the REMOTE at the
moment of use, re-run at push time, and `G17` failing a duplicate NUMBER even when the
suffixes differ. The block is a courtesy to siblings; the verify is the check.

---

## `CR-111-BRC04` · the Invoice Cloud API reference — one CR number and four `BR` ids (2026-09-17)

**Taken from this branch's own block** (`CR-110`–`CR-114`, suffix `BRC04`, claimed 2026-09-16
above). `CR-110-BRC04` was the first; this is the second. **`CR-112`–`CR-114` remain FREE.**

⚠ **THE BLOCK'S OWN ROW SAID `111`–`114` WERE "EXPECTED TO STAY UNUSED", AND THAT EXPECTATION IS
NOW WRONG RATHER THAN BREACHED.** It was written on the reasoning that the PO asked for **one** CR
covering the whole Integration Blueprint (*"measure all screens- why 5 crs - why not 1"*). That is
still true of the BLUEPRINT. **This CR is a different arrival** — a partner's API reference and
four rulings on it, none of which is blueprint work — so it is a second change request rather than
a section of `CR-110`. Recorded here rather than silently taken, because a row that says a number
is expected unused is exactly the row a sibling reads before reaching for it.

| Family | Id | Verified |
|---|---|---|
| CR | **`CR-111-BRC04`** | `allocate.py cr --verify 111` → *"still free on every branch (this tree not counted)"*, 2026-09-17, and re-verified from the pinned tip at push time |
| Business rule | **`BR-INT-070`** · **`BR-INT-071`** | `git grep` over every `refs/remotes/origin` ref: **0 hits** |
| Business rule | **`BR-PAY-1150`** · **`BR-PAY-1151`** | `git grep` over every `refs/remotes/origin` ref: **0 hits** |

⚠ **THE FOUR `BR` IDS ARE TAKEN AT A DELIBERATE DISTANCE FROM THE FRONTIER, NOT AT `max + 1`, FOR
THIS FILE'S OWN `DEF-1787` REASON.** The integrations frontier is `BR-INT-065` and the payments
frontier is `BR-PAY-1140`; **three sibling lanes hold files in `apps/integrations` in the shared
tree at this moment** — `partner_api.py`, `expiry.py` and the Integrations tab — so every one of
them computes `max + 1` correctly and every one of them gets the same answer. **Nothing allocates a
`BR` id**: `allocate.py` has no `BR` family and `file_defect.py` allocates defects, so the number is
read by hand and a hand count reads only this checkout (law 11). **`BR-INT-066`–`069` and
`BR-PAY-1141`–`1149` are LEFT FREE on purpose**, for whichever sibling reaches them first. A gap
costs nothing; a collision moves every citation.

**USED: `CR-111-BRC04` · `BR-INT-070` · `BR-INT-071` · `BR-PAY-1150` · `BR-PAY-1151`.**

⚠ **A FIFTH RULING LANDED LATER THE SAME DAY AND TOOK NO NEW ID.** *"you will ahve to remove
company ID filter from all Apis - we cannot tell tenant ID outside our system"* **reverses ruling 1
and the built 2026-09-16 check.** It is recorded in `BR-INT-070` — which was **rewritten before it
was ever pushed**, so no citation of the superseded reading exists to move — and in the same
decision-log entry and the same CR. **No sixth `BR` id was taken:** ruling 5 supersedes ruling 1 on
the same subject, and giving a reversal its own rule number would leave two live rows contradicting
each other in the file whose whole job is to say what the law is.

**NO `OQ` MINTED AND NO `DEF` MINTED, and law 13 is why.** Nothing these five rulings left
unsettled is a fact only the Product Owner holds: **what `remote_utility_id` carries in Invoice
Cloud's `consumer-info` RESPONSE** (their number echoed back, or the field omitted — **never
ours**), the batch's cadence and trigger, and which screen shows a flagged waiver row are all
**ours to decide and write down**. They are named as ours in `BR-INT-070`, `BR-INT-071` and
`BR-PAY-1150`, and the one judgment this lane actually made (the interaction between rulings 3 and
4) is in `02-decision-log.md` with its reasoning. ⚠ **`remote_utility_id` IS FLAGGED AND NOT
DECIDED, AND IT IS NOT PUT TO THE PO EITHER** — it is a consequence of a ruling they have already
made, so it is the building lane's call, not a new question. **No existing OPEN question asks any
of the five**, checked by grep over `01-open-questions.md` for `company_id` (**0 hits**),
`make-payment`, *partner payment*, `late fee` / `waiv` and `credit note` / `overpay`, so nothing is
closed either.

### ⚠ CORRECTION TO THE BLOCK ABOVE, 2026-09-17 — ONE `OQ` **WAS** MINTED, AND THE LINE SAYING OTHERWISE IS LEFT STANDING

**The section above says *"NO `OQ` MINTED AND NO `DEF` MINTED"* and lists *where the partner's own
`company_id` number is stored* among the things that are ours.** ⚠ **BOTH OF THOSE ARE NOW WRONG,
and they are corrected here rather than edited above** — the same discipline this file already
applies to its own breached rows (*"THE ROW ABOVE IS STALE AND HAS BEEN SINCE 2026-09-14"*), and
for the same reason: a register that rewrites itself cannot show a reader what it once said.

**WHAT CHANGED, AND IT WAS A PO NARROWING RATHER THAN A CHANGE OF MIND BY US.** Ruling 2 of
`CR-111-BRC04` was recorded reading *"batch run"* as a file arriving. The Product Owner then
narrowed it the same day:

> *"no this is not there - we will call htheir APis - we will ahnel those APis seperately - rember
> Invoice Cloud is both direction"*

**There is no file.** We dial Invoice Cloud's APIs on a schedule and collect the payments. **That
removed the very thing hard rule 6's existing key is derived from** — `payment_import_batches`
keys on `file_hash` + `tag_fingerprint`, and `file_hash` is *"SHA-256 hex of the exact bytes
uploaded"* — and turned an idempotency this lane had VERIFIED into a real gap on a money path.

| Family | Id | Verified |
|---|---|---|
| Open question | **`OQ-INT-12396`** | *What does Invoice Cloud's payment API give us to key on, so that a scheduled pull re-run does not post the same payment twice?* The register's own maximum is **`OQ-INT-12395`**, counted from its rows, so this is `max + 1`. ⚠ **`allocate.py oq` IS NOT USED AND MUST NOT BE** — it is the documented prose-scan bug, reading `CLAUDE.md`'s own worked examples `OQ-12345` / `OQ-123456` (decision log 2026-09-02). ⚠ **AND THE FOUR-DIGIT BAND IS NO LONGER THE FRONTIER:** `OQ-CUS-1810–1819` and its neighbours are four digits, but `CR-100` and `CR-110` work has minted `12348`–`12395`, so the live watermark is five digits and reading `1769` as the maximum would re-issue a taken id. Verified free in the working tree, across every `refs/remotes/origin` ref, and re-verified from the pinned tip at push time |

⚠ **AND LAW 13 IS SATISFIED RATHER THAN BREACHED BY MINTING IT.** `OQ-INT-12396` is **ROUTED TO
INVOICE CLOUD, NOT TO THE PRODUCT OWNER**, on `OQ-INT-1476`'s precedent (*"does the card processor
accept an idempotency key we supply"*, ROUTED 2026-09-04 to the processor). It is a fact about a
third party's API, not a judgment the Product Owner holds — and **it is not ours to decide either,
because a guess here is a customer paying twice.**

**THE THREE THINGS THAT ARE STILL OURS, RESTATED CORRECTLY:**

* **What `remote_utility_id` carries in Invoice Cloud's `consumer-info` RESPONSE** — their number
  echoed back, or the field omitted. **Never ours.** Unchanged by the narrowing.
* **The cadence — now PARTLY ANSWERED and still open.** The narrowing settles that it is a
  **schedule** whose trigger fires an **outbound call**. At what hour, and whether a tenant sets
  it, is still ours and still a tenant setting rather than a manifest's (`BR-INT-056`).
* **Which screen shows a flagged waiver row.** Unchanged.

⚠ **AND ONE ITEM LISTED ABOVE AS OURS IS NOW VOID, NOT MERELY CHANGED:** *where the partner's own
`company_id` number is stored on the connection*. **Ruling 5 removed the comparison entirely**, so
nothing is stored and no field is added. It is struck here rather than above, for the same reason.

**USED, AFTER THIS CORRECTION: `CR-111-BRC04` · `BR-INT-070` · `BR-INT-071` · `BR-PAY-1150` ·
`BR-PAY-1151` · `OQ-INT-12396`.** Nothing else taken. `CR-112`–`CR-114` remain free;
`BR-INT-066`–`069` and `BR-PAY-1141`–`1149` remain free.

---

## ⚠ `CR-112` IS **USED**, NOT FREE — CORRECTED 2026-09-17 (`DEF-GOV-5610`)

**THE TWO LINES ABOVE THAT SAY *"`CR-112`–`CR-114` remain FREE"* WERE TRUE WHEN WRITTEN AND ARE
WRONG NOW.** They are left standing rather than edited, because what a block said at a moment is
evidence, and this file's whole value is that its rows can be read back. **Read this section as
the current state.**

`CR-112` was **taken and shipped** — the GIS foundation, version `2.290.0`, commit `1c658337` —
and **it has no CR file and never had one.** The work is real and is cited **29 times** across the
repo: `10-scripts/gates/g85_one_address_home.py`, three test files
(`test_cr112_gis_parcels.py`, `test_cr112_gis_search.py`, `test_cr112_gis_match.py`),
`12-governance/02-decision-log.md`, `12-governance/09-human-review-ledger.md`,
`10-scripts/cr112_city_address_keys_walkthrough.mjs`, and `CR-115-BRC05`, which describes it as
shipped.

**WHY THIS MATTERS AND IS NOT BOOKKEEPING:** a sibling branch reading the lines above would
allocate `CR-112` today, correctly, and land on top of all 29 citations. The number would be a
duplicate in fact while `allocate.py cr --verify 112` — which asks the REMOTE for the *number*,
not for this register's prose — answered honestly that it saw no conflict.

⚠ **`CR-113` AND `CR-114` REALLY ARE FREE, AND THE COUNT THAT SAYS OTHERWISE IS A GREP ARTEFACT.**
A search for `CR-114` returns **6 hits** and every one of them is the BLOCK RANGE `CR-110`–`CR-114`
written out, never a change request of that number. This is `DEF-2804`'s shape one family along —
a real id read for a different real string — and it is recorded here so the next reader does not
re-derive the same false positive. **`CR-113`: 0 hits. `CR-114`: 0 hits that are not the range.**

⚠ **`CR-115-BRC05` WAS TAKEN FROM OUTSIDE EVERY BLOCK.** `BRC04` is `CR-110`–`CR-114`; there is no
`BRC05` block in this file and `CR-115` is in none. It was allocated on 2026-09-17 by the session
writing the handover note, under context pressure, and the CR's own §5 records its index row as
knowingly owed. **Nothing is renumbered** — the string is unique and the work is real — but the
provenance is written down here rather than left to be inferred, which is what this file is for.

**CURRENT STATE OF THE `BRC04` BLOCK: `CR-110` USED · `CR-111` USED · `CR-112` USED (no file) ·
`CR-113` FREE · `CR-114` FREE. `CR-115` USED, from outside any block.**

**WHAT IS STILL OWED, AND IT IS NOT CLOSED BY THIS SECTION:** `CR-112` has no file. This records
that the NUMBER is taken, which closes the collision risk; it does not write the change request.
The prevention `DEF-GOV-5610` asks for is a gate that resolves every `CR-<nnn>` citation against
the CR files that exist AND against this register, and fails when a cited number is recorded free.
**`G17` fails a DUPLICATE number and has never asked whether a cited number was ever ISSUED** —
hard-won law 7's *"a citation gate that refuses a repeated id and never asks whether the id was
ever issued"*, still true today.

## `BR-CUS-1079` · `OQ-CUS-12407` · `DEF-CUS-5647` / `DEF-CUS-5648` / `DEF-RAT-5657` — the account-types lane, 2026-09-17

**Branch `claude/kind-wozniak-rl0uzt`, the lane building the PO ruling *"utility can get their own
account types"*.** Recorded here because three of these families are allocated by hand or
against a register whose maximum a sibling lane's unpushed worktree is not in (law 11).

* **`BR-CUS-1079`** — taken as `max + 1` of the customers business-rule family, whose highest was
  `BR-CUS-1078`. ⚠ **`BR-` has NO allocator**: `allocate.py` covers `defect`, `gate`, `oq`, `cr`
  and `version` and nothing else, so this number was read from this checkout alone. It is the
  number in the two migration FILENAMES (`customers/0054_br_cus_1079_…`, `0055_rls_br_cus_1079_…`),
  which is the one place renumbering later is expensive — a migration filename is a dependency
  string in the file after it.
* **`OQ-CUS-12407`** — `allocate.py oq`, which asks the remote. **Not `OQ-CUS-5649`**, which is
  what a hand count of this file's own prose would have produced; the register's real maximum is
  four digits higher and the first draft of `lookups.py` carried the wrong one for twenty minutes.
* **`DEF-CUS-5647`, `DEF-CUS-5648`, `DEF-RAT-5657`** — `file_defect.py --id-module`, which fetches
  first. All three printed *"inside no active block"*, which is true and is not a warning: defect
  ids are not blocked per branch, only CR numbers are.
  ⚠ **AND THE THIRD ONE WAS ALLOCATED `5654` AND COLLIDED ANYWAY, WHICH IS THE LAW-11 CASE ITSELF
  RATHER THAN A MISTAKE.** A sibling took `DEF-GOV-5654` in its own worktree in the same minutes;
  both computations of *the next free number* were right, and neither world contained the other.
  **`allocate.py defect --verify 5654` is what caught it** — *"TAKEN — a sibling pushed it"* — run
  at push time, which is the only moment the answer can be final. The row was renumbered to
  `DEF-RAT-5657` by re-deriving the whole register from the pinned tip and splicing ONE line's
  bytes: 3,214 lines in, 3,214 out, **one line changed**, `git diff --numstat` reporting `1 1`.
  ⚠ **`DEF-CUS-5647` AND `DEF-CUS-5648` VERIFIED AS *TAKEN* TOO AND WERE NOT RENUMBERED — READ THE
  ROW BEFORE BELIEVING THE VERDICT.** They were taken by THIS lane: a sibling's pathspec commit had
  already published them off the shared working tree (law 11, mechanism five), so the verdict was
  accurate and the conclusion *renumber* would have been wrong. `--verify` answers *does this number
  exist on a branch*, never *whose it is*; the register's own title column answers the second.

**No CR number was taken.** This is a PO ruling executed through `r11`, not a change request, and
the ruling's own decision-log entry is its record. A `CR-` number would have been a fifth id with
no file behind it — the state this register already records as owed for `CR-112`.


## `CR-120`–`CR-124`, suffix `BRC06` — BRANCH `claude/kind-wozniak-rl0uzt`, the rate schedule's base-charge binding (2026-09-19)

**Claimed here before use**, which is what this file is for.

| | |
|---|---|
| Block | **`CR-120`–`CR-124`**, suffix **`BRC06`** |
| Branch | `claude/kind-wozniak-rl0uzt` |
| Claimed | 2026-09-19 |
| First id | **`CR-120-BRC06`** — the rate schedule NAMES its base charge code (PO ruling 2026-09-19) |

⚠ **IT OPENS AT 120 AND NOT AT 116, DELIBERATELY.** `allocate.py cr` answers **116** and
`--verify` answers *still free on every branch* for every number from 116 to 124. 116 is the
FRONTIER, and the frontier is exactly where a sibling in its own worktree — whose rows are in
none of the places a listing can see until it pushes — will also land (law 11, `DEF-1787`).
Stepping clear is the only answer that does not race, and it is what this file's own rows have
done six times. **`CR-116`–`CR-119` are LEFT FREE on purpose** for whichever branch reaches the
frontier next; a gap costs nothing and a collision moves every citation.

⚠ **THERE IS NO `BRC06` BLOCK IN THIS FILE UNTIL THIS ROW.** `BRC01` = `CR-090`–`094`,
`BRC02` = `095`–`099`, `BRC03` = `100`–`104` **and** `105`–`109`, `BRC04` = `110`–`114`, and
`CR-115-BRC05` was taken from outside every block on 2026-09-17 and says so. So `BRC06` is minted
here rather than found, and it is minted by writing the branch name into the row — never by
taking the numbers quietly, which is the promise-in-a-chat-message this whole file replaces.

⚠ **THIS BRANCH HAS TAKEN NO CR NUMBER BEFORE.** Its earlier lane (`BR-CUS-1079` · the
account-types ruling, 2026-09-17, recorded further up this file) deliberately took none, on the
reasoning that a PO ruling executed through `r11` is not a change request. **That reasoning does
not carry here and the difference is worth stating:** that lane built a rule the PO had ruled on;
this one adds a CAPABILITY that does not exist — `tariff_versions` has no charge-code column
today — and `13-change-process.md` §1's beta table routes *"it works as agreed, and now that they
have used it they want it different"* to **change**. The classification argument in full is
`CR-120-BRC06`'s own §1.

**USED so far: `CR-120-BRC06`.** `CR-121`–`CR-124` remain FREE.

---

## `DEF-CUS-5970`–`5972` — THE PROPERTY-SALE SCENARIO SUITE (2026-09-20)

⚠ **RESERVED BECAUSE THE FRONTIER RACED TWICE IN FIFTEEN MINUTES, NOT BECAUSE
THE ARITHMETIC WAS WRONG.** This lane filed three rows at `5951`–`5953`,
re-derived the register from the pinned tip at push time exactly as CLAUDE.md
law 11 prescribes, and `allocate.py defect --verify` answered **`5952: TAKEN —
a sibling pushed it`**. It renumbered to `5954`–`5956`, re-derived again, and
the same command answered **`5954: TAKEN`**. Both allocations were correct when
they were made and both were stale by the time the push reached the remote:
`claude/kind-wozniak-rl0uzt` took **five** commits from four lanes in the
twenty minutes this lane spent re-deriving.

**So the answer is the one this file's own `CR-120`–`CR-124` row already gives:
STEP CLEAR OF THE FRONTIER.** `max + 1` is exactly where the next sibling in its
own worktree will land, because its rows are in none of the places a listing can
see until it pushes (law 11, `DEF-1787`). A gap costs nothing; a collision moves
every citation in a 3,400-row register, where a duplicate id reads as a register
and not as an error. `5957`–`5969` are LEFT FREE on purpose for whoever reaches
the frontier next.

**USED: all three**, and each is cited from `06-backend/tests/test_transfer_scenarios.py`
and from `08-qa/01-e2e/journeys/J-TRF-TWENTYFIVE-the-property-sale-scenario-suite.md`:

* `DEF-CUS-5970` — `DEF-CUS-5940`'s THIRD call site, still live at
  `discounts.py:858`, reached by `GET /customers/{id}/deposit-position`.
* `DEF-CUS-5971` — after a sale every screen that shows a NAME still shows the
  seller's; `selectors.account_row` serves the buyer's `customer_no` beside it.
* `DEF-CUS-5972` — selling to the person who already owns the account is not
  refused; the guard compares resolved ids and a phone cannot reuse a customer.

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-CUS-5970–5972` | the property-sale scenario suite (claude), PO walk 2026-09-20 | 2026-09-20 | **ACTIVE** |


---

## `DEF-CUS-6190`–`6194` — LANE MOVE, and the collision that made it necessary (2026-09-22)

⚠ **RESERVED BECAUSE THREE IDS WERE ALREADY LOST TO A LIVE SIBLING, NOT BECAUSE
THE ARITHMETIC WAS WRONG.** This lane filed four rows at `6178`–`6181` through
`file_defect.py`, which asks the REMOTE and answered correctly each time. While
it worked, `LANE REQ-A` filed and pushed **its own** `DEF-CUS-6178`,
`DEF-CUS-6179` and `DEF-CUS-6180` — three completely different defects — and the
re-derivation of the register from the pinned tip is what surfaced it. The
allocator's own line was accurate at every allocation; what was wrong was *which
world the maximum came from*, which is CLAUDE.md law 11's `DEF-1787` exactly,
and the second lane's rows would have published as duplicates into a 3,700-row
register where a duplicate reads as a register and not as an error.

**So this steps clear of the frontier**, which is the answer this file's own
`DEF-CUS-5970`–`5972` row already gives: `max + 1` is precisely where the next
sibling will land, because its rows are in none of the places a listing can see
until it pushes. **`6182`–`6189` are LEFT FREE on purpose** for whoever reaches
the frontier next — a gap costs nothing.

⚠ **`DEF-CUS-6177` IS NOT IN THIS BLOCK AND IS NOT RENUMBERED.** It was pushed
before the collision, it is on the branch, and it is this lane's. Renumbering a
published id moves every citation of it.

**USED:**

* `DEF-CUS-6190` — the transfer wizard's step 1 no longer states three facts its
  own guard demands; red on this branch since 2026-09-20 and read by nobody.
* `DEF-GOV-6191` — a commit went onto the branch carrying another lane's
  message, from a stale `msg1.txt` in the **shared** scratchpad.
* `DEF-CUS-6192` — the parked row's STATE cell holds 27 words, on three screens.
* `DEF-CUS-6193` — 33 customer front-end cases red on the branch, unclassified.

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-CUS-6190–6194` | lane MOVE (`CR-133-BRC07`, `BR-CUS-1090`) | 2026-09-22 | **ACTIVE** |
| `DEF-PAY-7020–7029` | **lane PAY-AGEING** (`DEF-PAY-6940` — the AR Ageing answers the same figures for every as-at date). Dispatched as a reserved block rather than taken as *the next free number*, which is the failure `DEF-CWP-3734` and `DEF-RAT-4514–4516` both record. Re-verified with `10-scripts/allocate.py defect --verify` against the REMOTE in the same breath as the blob re-derivation at push time. **USED: `DEF-PAY-7020`** — a bill that is `void` or `corrected` today cannot be restored to a past date's position, because `invoices` carries `issued_at` and no `voided_at`/`corrected_at`. `7021`–`7029` are UNUSED and stay reserved to this lane. | 2026-09-27 | **ACTIVE** |
| `DEF-REP-7150-7169` | lane REP-P6-W4 — `CR-142-BRC07` `P6.11` wave 4, the last three reports (R4 Bill Run Readiness, R27 Plans & Discounts, R46 Bill Projection). ⚠ **THIS LANE WAS DISPATCHED WITH `7110`–`7129` AND THAT BLOCK WAS NEVER WRITTEN HERE BY THE COORDINATOR** — so nothing on the branch said it was this lane's, the allocator handed `7110`, `7111` and `7112` to the coordinator's own rows, and this lane's two rows had to be RENUMBERED after the fact. That is `file_defect.py`'s own refusal sentence coming true (*"a block claimed on the command line and nowhere else is the promise that does not survive the chat"*), and it is the SECOND time today it has cost a lane — the guard refused two others for the same thing. **The lesson is whose job it is: a block belongs to whoever DISPATCHES it, written before the lane starts, because the lane cannot reserve a block it has not been told about and the allocator cannot see a briefing.** ⚠ **`7140`–`7149` IS LANE RAT-REDS-9's** and is left alone, so this block opens at `7150`. ⚠ **AND THE OQ FAMILY IS IN NEITHER BLOCK**: its running number is `12768`+, so `OQ-REP-12768` and `OQ-REP-12769` came from `allocate.py oq` and are unaffected by the renumber. **USED: `DEF-REP-7150`** (R46's missing component assembler) and **`DEF-AST-7151`** (`tsc` red on the branch, dated to `3bf716c90`). `7152`–`7169` remain UNUSED and free. | 2026-09-27 | **ACTIVE** |
| `DEF-GOV-7060–7069` | lane FIX-SMALL — four unrelated defects cleared together (`DEF-TEN-6935`, `DEF-REP-6924`/`6936`, `DEF-GOV-6930`, `DEF-GOV-6962`) plus `DEF-REP-6931`. Dispatched as a block by the coordinator rather than taken by hand. **USED: `DEF-GOV-7060`** — the two metering catalogue values that still compose a brand name into a translated string, found while building `BR-REP-045` and filed rather than silently converted. | 2026-09-27 | **ACTIVE** |

---

## `BR-CUS-1091` · the address parts on capture step 3 (2026-09-22)

**Lane REQ-A, branch `claude/laughing-thompson-kpmwih`.** One rule id, no CR
number, no defect number: the PO's report of 2026-09-22 row 16 asks for a
capability the product refused by signed rule, so what it needs is a RULE that
reverses the refusal and says how far the reversal goes. `BR-CUS-1055` is
amended in both directions the same day and `BR-CUS-1091` is the new statement.

| Family | Id | How it was checked |
|---|---|---|
| BR | **`BR-CUS-1091`** | `allocate.py` has no `br` family, so the maximum was taken the way that tool takes its own: **`git fetch --all`, then `git grep` for `BR-CUS-1\d{3}` across all 56 `origin/*` refs** under `04-docs` and `12-governance`. 42 ids exist; the highest is **`BR-CUS-1090`** (lane MOVE, pushed to this same branch today). Re-derived from the pinned tip at push time. |

⚠ **THE MIGRATION FILENAME CLAIMED THE NUMBER BEFORE THE RULE EXISTED, AND FOR
TWO HOURS THE ONLY CITATION OF `BR-CUS-1091` IN THE REPO WAS A TEST DOCSTRING.**
That is `DEF-2804`'s shape one step earlier: not an id read as the wrong id, but
an id cited before it was issued — and **the repo has a gate that refuses a
repeated id and none that asks whether an id was ever issued** (hard-won law 7's
*looking at the wrong thing*, recorded on 2026-09-05). It was caught by grepping
for the citation rather than by any check. **A file named for an id is a claim
that the id exists; mint the row in the same commit.**

**USED: `BR-CUS-1091`.**

---

## `BR-CUS-1092` · the application fee comes from a charge code (2026-09-22)

**Lane REQ-A, branch `claude/laughing-thompson-kpmwih`, the second id from this
lane today.** `BR-CUS-1091` is the address parts; this is PO report row 11's
second half — the fee picker, and `Collect later` leaving the screen.

| Family | Id | How it was checked |
|---|---|---|
| BR | **`BR-CUS-1092`** | `allocate.py` has no `br` family, so the maximum is taken the way that tool takes its own: `git fetch --all`, then `git grep` for `BR-CUS-1\d{3}` across all 56 `origin/*` refs under `04-docs` and `12-governance`. The highest on the remote was **`BR-CUS-1090`** (lane MOVE, this same branch); `1091` was taken by this lane an hour earlier and is pushed. Re-derived from the pinned tip at push time. |

**USED: `BR-CUS-1091` · `BR-CUS-1092`.**

⚠ **NO CR NUMBER WAS TAKEN FOR EITHER, AND THAT IS A CLASSIFICATION AND NOT AN
OMISSION.** The PO's report of 2026-09-22 is a list of things wrong with two
screens a clerk is already using, so `12-governance/22-product-maintenance-
process.md` owns it — *can a user do this task in the product today?* Yes, so it
is MAINTENANCE. The rows that only change behaviour are defects
(`DEF-CUS-6173`–`6181`); the two that reverse or extend a signed rule need a RULE
to say how far the reversal goes, which is what these two ids are. A CR number
would have recorded the customer asking for something new, which is the exact
mislabelling `13-change-process.md` step 1 exists to prevent.

---

## `CR-135-BRC07` · payments blueprint phase 0, the database half (2026-09-22)

**Lane P0-DB, branch `claude/laughing-thompson-kpmwih`.** One CR number, one
business rule, three defect ids.

| Family | Id | How it was checked |
|---|---|---|
| CR | **`CR-135-BRC07`** | `allocate.py cr --verify 135` → *"still free on every branch (this tree not counted)"*, twice: at allocation, and again after the tip moved three commits under this lane. |
| BR | **`BR-PAY-1160`** | `allocate.py` has no `br` family, so the maximum was taken the way that tool takes its own: `git fetch`, then `git grep` for `BR-PAY-1\d{3}` across the `origin/*` refs under `04-docs` and `12-governance`. |
| DEF | **`DEF-PAY-6196` · `DEF-PAY-6197` · `DEF-GOV-6198`** | `file_defect.py --id-module PAY` / `--id-module GOV`, which allocates against the remote and appends one row as raw bytes. Each is noted *"inside no active block"*. |

⚠ **`allocate.py cr --verify 135` LATER ANSWERED *"TAKEN — a sibling pushed it.
Renumber before you commit"*, AND IT WAS THIS LANE'S OWN COMMIT.** `CR-135` was
verified free, taken, written into three migration FILENAMES and pushed in
`76c24705f`; the next verify read that push back and named a culprit it had not
checked. **Every one of the six files citing `CR-135` anywhere on the branch
came from that push** — `git grep -l "CR-135" origin/claude/laughing-thompson-kpmwih`
lists six, all this lane's.

**Renumbering on that message would have caused the damage the tool exists to
prevent**: three migrations already applied to a database would have been
orphaned, and the branch would have carried two spellings of one change. Filed
as `DEF-GOV-6198`.

**The durable form is the one worth keeping**: `--verify` answers *is this
number in use on the remote*, which is true and useful, and then states *a
sibling did it*, which it never established. CLAUDE.md hard-won law 7's third
habit — a check's output must distinguish pass from fail to a READER — extends
to attribution, because a check that names the wrong cause is trusted exactly as
much as one that names the right one. **Before renumbering on this message,
grep the refs.**

⚠ **AND THE ROW CAME AFTER THE FILENAMES, WHICH IS `BR-CUS-1091`'s LESSON
REPEATED ONE FAMILY ALONG.** That entry, four sections above, says it in terms:
*"A file named for an id is a claim that the id exists; mint the row in the same
commit."* Three migration files carried `cr135` for about an hour with no CR row
anywhere in the register, and it was a coordinator reading the branch — not any
gate — that noticed. The verify was run and passed; running the verify is not
the same act as filing the row.

**USED: `CR-135-BRC07` · `BR-PAY-1160` · `DEF-PAY-6196` · `DEF-PAY-6197` · `DEF-GOV-6198`.**

---

## `CR-135-BRC07` `P0.6` · re-keying the deposit batch (2026-09-22)

**LANE P0-BATCH-3, branch `claude/laughing-thompson-kpmwih`.** **No new CR
number, no defect id and no business-rule id were taken**, and each absence is
deliberate rather than an oversight:

| Family | Taken? | Why |
|---|---|---|
| CR | **no** — built under the existing `CR-135-BRC07` | `P0.6` is a task of the same phase 0 of the same blueprint, and that CR's register row already names the phase. A second number for one phase would put two spellings of one change on the branch, which is `DEF-GOV-6198`'s own lesson from this same CR. Its row is AMENDED in place, with `2.330.0` beside `2.329.0`. |
| BR | **no** | `BR-PAY-025` already exists and is what changed. A ruling that supersedes half of a signed rule is stamped on that rule, never minted as a new one beside it — otherwise a reader finds two rules and no supersession chain. |
| DEF | **no** | Nothing in the product is broken. `deposit_batches` implemented `BR-PAY-025` exactly as signed; the rule itself moved. ⚠ **One thing WOULD have been a defect and is recorded in the decision log instead**, because it is in a governance document rather than in the product: the row closing `OQ-PAY-12575` states that a two-digit counter *"reaches `DEP-260922-99` and then cannot allocate at all"*, which is measurably untrue. It is corrected where it was written, in the same register, and pinned by an assertion in `test_cr135_p06_deposit_batch_rekey.py` so that nobody has to remember it. |
| VERSION | **`2.330.0`** | `allocate.py version --bump change` → `2.330.0`, then `--verify 2.330.0` re-run **after the tip moved one commit** under this lane: *"still free on every branch"*. Written in all three files `allocate.py` names. |

**No range is held open** — this is one task, not a wave. `OQ-PAY-12575`,
`OQ-PAY-12576` and `OQ-PAY-12577`, reserved by the earlier LANE P0-BATCH and
marked RELEASED above, are all **CLOSED** by this build.

## `CR-136-BRC07` · payments blueprint phase 2, the counter (2026-09-23)

| Family | Taken | How it was verified |
|---|---|---|
| CR | **`CR-136-BRC07`** | `allocate.py cr` answered **136**, then `allocate.py cr --verify 136` → *"still free on every branch (this tree not counted)"*, run against the REMOTE. `CR-134` is unused — `allocate.py` reported the maximum as 135 and 134 was never issued on any branch; nothing is renumbered. |

**No block is reserved and no other family is taken yet.** Phase 2 has 23 tasks
across at least six lanes, and each lane allocates its own defect, gate and
version numbers **at push time** through `allocate.py <family> --verify`, per
hard-won law 11's id clause — a number taken now would be a stale read by the
time it is used. **Lanes append their own row here when they take one.**

**USED: `CR-136-BRC07`.**

## `CR-137-BRC07` · payments phase 3 · `CR-138-BRC07` · payments phase 4 (2026-09-23)

| Family | Taken | How it was verified |
|---|---|---|
| CR | **`CR-137-BRC07`** · **`CR-138-BRC07`** | `allocate.py cr` answered **137**, then `allocate.py cr --verify 137` and `--verify 138`, both → *"still free on every branch (this tree not counted)"*, run against the REMOTE. |

**No block is reserved and no other family is taken yet.** Phase 3 is 21 tasks
and phase 4 is 28, across at least five lanes; each lane allocates its own
defect, gate and version numbers **at push time** through
`allocate.py <family> --verify`, per hard-won law 11's id clause — a number taken
now would be a stale read by the time it is used. **Lanes append their own row
here when they take one.**

**USED: `CR-137-BRC07` · `CR-138-BRC07`.**

## `CR-139-BRC07` · payments phase 5 — settlements and the barcode (2026-09-23)

| Family | Taken | How it was verified |
|---|---|---|
| CR | **`CR-139-BRC07`** | `allocate.py cr` answered **139**, then `allocate.py cr --verify 139` → *"still free on every branch (this tree not counted)"*, run against the REMOTE. |

**No block is reserved and no other family is taken yet.** Phase 5 is 18 tasks
across at least three lanes; each lane allocates its own defect, business-rule,
gate and version numbers **at push time** through `allocate.py <family> --verify`,
per hard-won law 11's id clause — a number taken now would be a stale read by the
time it is used. **Lanes append their own row here when they take one.**

**USED: `CR-139-BRC07`.**

### `CR-139-BRC07` — the ids LANE P5-BACK actually took (2026-09-23)

| Family | Taken | How it was verified |
|---|---|---|
| OQ | **`OQ-PAY-12608`** | `allocate.py oq` answered **12608**, `--verify 12608` twice — at allocation and again at push time — *"still free on every branch (this tree not counted)"*. |
| defect | **`DEF-GOV-6257`** · **`DEF-PAY-6258`** | `10-scripts/file_defect.py --id-module …`, which asks the REMOTE. ⚠ **RENUMBERED AT PUSH TIME FROM `DEF-GOV-6255`/`DEF-PAY-6256`** — the push-time re-verification this law prescribes answered **`TAKEN — a sibling pushed it`** for both, and a sibling really had: `DEF-PAY-6255` and `DEF-GOV-6256` were on the remote by then. **Both numbers were correct when they were computed and stale by the time they were used**, which is law 11's id clause word for word. The register copy was re-derived from the pinned tip and both rows re-filed; every citation of the old pair was rewritten in the same breath. |
| CR | `CR-139-BRC07` — **already USED**, pushed in `fee14d17b` | `allocate.py cr --verify 139` now answers *"TAKEN"*, **which is this lane's own push and is the correct answer**. A later lane reading that must not renumber it. |

**Nothing is reserved and nothing is held open.** `P5.7`, `P5.8` and the five
remaining test/e2e rows allocate their own ids at push time.

## `CR-140-BRC07` · a Write-offs link on the Debtors tab (2026-09-23)

**LANE WRITEOFFS-LINK, branch `claude/laughing-thompson-kpmwih`.** One CR number, one defect
id and one version, **all USED at allocation; no block is held open** — this is one task,
not a wave.

| Family | Taken | How it was verified |
|---|---|---|
| CR | **`CR-140-BRC07`** | `allocate.py cr` answered **140**, then `allocate.py cr --verify 140` → *"still free on every branch (this tree not counted)"*, run against the REMOTE at allocation and again at push time. |
| defect | **`DEF-PAY-6368`** | `10-scripts/file_defect.py --id-module PAY`, which asks the REMOTE, run at push time from the pinned tip. |
| version | **`2.347.0`** | `allocate.py version --bump change`, then `allocate.py version --verify 2.347.0`, at push time. |

**USED: `CR-140-BRC07` · `DEF-PAY-6368` · `2.347.0`.**

## `CR-141-BRC07` · a refund's check number is correctable — lane REFUND-CORRECT (2026-09-23)

| Family | Taken | How it was verified |
|---|---|---|
| CR | **`CR-141-BRC07`** | ⚠ **RENUMBERED AT PUSH TIME FROM `CR-140`.** `allocate.py cr` answered **140** at the start and `--verify` agreed; by push time a sibling had shipped `CR-140-BRC07` (*"a Write-offs link on the Debtors tab"*, `56155c3ec`). Re-allocated against the REMOTE: **141**, then `allocate.py cr --verify 141` at push time. |
| defect | **`DEF-PAY-6398`** | ⚠ **RENUMBERED AT PUSH TIME, MORE THAN ONCE.** `file_defect.py --id-module PAY` allocated 6352 correctly; siblings then filed `DEF-CUS-6352` (`286458b98`), `DEF-BIL-6373` (`35f3cf079`) and `DEF-CUS-6374` (`3bcccc666`) — the same NUMBERS under other modules, `DEF-BIL-5090`'s collision exactly, three times in one afternoon. The number in bold is the one `file_defect.py` allocated from the final pinned tip, which is the only allocation that counts. |
| business rule | **`BR-PAY-1196`** | **Taken BY HAND** — `allocate.py` has no `br` family. The tip's maximum was `BR-PAY-1191`; **1196 rather than 1192** leaves `1192`–`1195` free for the payments lanes working this branch in the same hour, the `BR-PAY-1191` row's own precedent (*"numbered 1191 rather than 1188 to leave headroom"*). Grepped free on the pinned tip at push time. |
| version | **`2.349.0`** | ⚠ **RENUMBERED AT PUSH TIME, TWICE** — from `2.347.0`, which the same sibling shipped, and then from `2.348.0`, taken before `2.348.1` (the US-English sweep, `d351e5fee`) landed. `allocate.py version --bump change` against the remote, re-verified with `allocate.py version --verify` at push time. |
| defect | **`DEF-PAY-6399`** | Filed for FOUR PostgreSQL reds this lane read and did NOT cause — `test_cr059_cs34_amend_reference.py`, red since `5831a9cd5` (P0.6, 2026-09-22), dated with `git log -S payments_deposit_batch_needs_session`. `file_defect.py --id-module PAY`, which asks the remote. |

**Every collision above — and the migration number, `0042` → `0043`, taken by `0042_def_cus_6376_…` the same hour — was caught by law 11's id clause — re-derive every id at push time, unconditionally** — and none by a merge conflict: every register merged cleanly. **Nothing reserved and nothing held open.**

## `DEF-CUS-5975`–`5978` — the four rows that shared `DEF-CUS-5979` / `5980`, renumbered (2026-09-23, lane SMALL-CUS, `DEF-CUS-6343`)

Six defect rows were published under two ids by `DEF-CUS-5984`'s cascading renumber. **All six first
appear in the same commit** (`git log -S` on each title: `d54a7f7d7` locally, which is this clone's
shallow boundary; `39174783a` on GitHub), so the earliest commit cannot pick a winner by itself.
**That commit's own message can, and it is immutable:** *"DEF-CUS-5975 to 5979 filed for what could
not be built here, and DEF-CUS-5980 self-reported: the purge…"*. So the ids the author meant are
5975–5980 in register order, the money tile keeps `5979` and the purge keeps `5980`. `5975`–`5978`
were free on every remote branch and in every file (`git grep`, and `allocate.py defect --verify`
at push time), so the four rows go back to the numbers their author chose, and the commit message
stops pointing at ids nobody holds.

| Row (title opens) | Was | Now |
|---|---|---|
| THE TRANSFERS TAB'S SALE-DATE SORT ORDERS BY from_account__closed_at | `DEF-CUS-5979` | **`DEF-CUS-5975`** |
| THE SELLER IS OVERWRITTEN AT COMMIT (`Sold by`) | `DEF-CUS-5980` | **`DEF-CUS-5976`** |
| THERE IS NO TRANSFER RECORD PAGE AT ANY ADDRESS (`↗ Open`) | `DEF-CUS-5979` | **`DEF-CUS-5977`** |
| THE TRANSFERS SEARCH PROMPT OFFERS 'EITHER ADDRESS' | `DEF-CUS-5980` | **`DEF-CUS-5978`** |
| p131'S ONLY MONEY TILE … IS NOT SERVED | `DEF-CUS-5979` | `DEF-CUS-5979` (keeps) |
| THE TRANSFERS WALKTHROUGH PURGE READ transfer.customer AS 'THE BUYER' | `DEF-CUS-5980` | `DEF-CUS-5980` (keeps) |

**Citations moved by what each sentence is about, not by the number it carried** (the cascade
destroyed that): `TransfersTab.tsx` 9 lines and `TransfersTab.test.tsx` 2. The 2026-09-20 decision-log section's
three citations are NOT edited (the log is append-only); the new decision-log section of
2026-09-23 says how to read them. Left alone on purpose: the sentences that DESCRIBE the duplication (decision log
2026-09-20 and 2026-09-21, `25-session-handoff-2026-09-20.md`, and the six register rows that
reported it) — they are true history. The register was edited as a byte splice of four id fields:
same length, exactly four lines differing, every other byte identical to the tip.

## `DEF-6440`–`DEF-PAY-6454` — the fifteen defect numbers that two ids shared, renumbered (2026-09-24, lane SMALL-CUS)

**PO ruling 2026-09-24, verbatim:** *"Allow the override for this one fix: renumbering these 15
defects in the register? (a) — nothing is deleted, each defect just gets its own number"* (decision
log, *"THE 15 DEFECT NUMBERS SHARED BY TWO IDS ARE RENUMBERED"*, `a9a70bbdc`).

**Which one moved:** in each pair, the id FILED FIRST keeps its number. "Filed" is the first commit
that ADDED the row, read in one pass over `git log -p --reverse` of the register back to 2026-09-06
(the clone was deepened to reach it). The other id takes a fresh number: `allocate.py defect`
answered `6435`; `6440`–`6454` were taken, leaving `6435`–`6439` for siblings filing meanwhile, and
each was re-verified with `allocate.py defect --verify` at push time. **Only the number changed;
every module segment is kept, including the one bare id.**

| Number | Keeps it (filed first) | Moved (filed second) | Now |
|---|---|---|---|
| 4497 | `DEF-MET-4497` (`db147e25d`, 09-07 14:23) | `DEF-4497` (`356664845`, 14:46) | **`DEF-6440`** |
| 4512 | `DEF-WRK-4512` (`b8cc0ca02`, 09-07) | `DEF-TEN-4512` (`61630cf5e`, 09-08) | **`DEF-TEN-6441`** |
| 4710 | `DEF-TEN-4710` (`d6afe7675`, 21:10) | `DEF-CWP-4710` (`3e567ad93`, 21:15) | **`DEF-CWP-6442`** |
| 5137 | `DEF-SHL-5137` (`9faf26d5c`, 04:38) | `DEF-CUS-5137` (`37996c2cd`, 04:42) | **`DEF-CUS-6443`** |
| 5492 | `DEF-SHL-5492` (`6351747f1`, 08:41) | `DEF-INT-5492` (`a460ebaa5`, 08:49) | **`DEF-INT-6444`** |
| 5618 | `DEF-INT-5618` (`dd0267454`, 10:55:59) | `DEF-GOV-5618` (`79f6f0561`, 10:56:18) | **`DEF-GOV-6445`** |
| 5678 | `DEF-IDN-5678` (`e4f4dd9c3`, 16:54) | `DEF-GOV-5678` (`95f06ab99`, 16:55) | **`DEF-GOV-6446`** |
| 5680 | `DEF-INT-5680` (`7c10c943c`, 17:56) | `DEF-RAT-5680` (`2a4da1241`, 18:32) | **`DEF-RAT-6447`** |
| 5681 | `DEF-INT-5681` (`7c10c943c`, 17:56) | `DEF-RAT-5681` (`2a4da1241`, 18:32) | **`DEF-RAT-6448`** |
| 5840 | `DEF-TEN-5840` (`29990f123`, 07:27) | `DEF-RAT-5840` (`c656deea1`, 07:30) | **`DEF-RAT-6449`** |
| 5841 | `DEF-MET-5841` (`29990f123`, 07:27) | `DEF-RAT-5841` (`c656deea1`, 07:30) | **`DEF-RAT-6450`** |
| 6050 | `DEF-CUS-6050` (`2472112d2`, 19:08:59) | `DEF-SHL-6050` (`472557af2`, 19:09:26) | **`DEF-SHL-6451`** |
| 6082 | `DEF-CUS-6082` (`484a54b36`, 21:38) | `DEF-MET-6082` (`c44935dbf`, 21:50) | **`DEF-MET-6452`** |
| 6083 | `DEF-CWP-6083` (`58a749eb3`, 21:41) | `DEF-MET-6083` (`c44935dbf`, 21:50) | **`DEF-MET-6453`** |
| 6234 | `DEF-GOV-6234` (`dad7fb4e3`, 04:36) | `DEF-PAY-6234` (`7662676df`, 04:43) | **`DEF-PAY-6454`** |

**Citations moved in the same commit:** every occurrence in code, tests, walkthroughs, the OpenAPI
schema (one docstring), docs, conformance files and three change-request files — 72 in 37 files —
plus four register rows that cite a moved id as a reference (`DEF-TEN-5343`, `DEF-RAT-5696`,
`DEF-RAT-5708`, `DEF-RAT-5817`). **Deliberately NOT edited:** the append-only registers
(decision log, review ledger, `CHANGELOG.md`, this file), the recovery patch
`12-governance/recovery/2026-09-23/wt-p3back2.patch`, and the five register rows that DESCRIBE a
collision (`DEF-GOV-4723`, `4736`, `4738`, `5621`, `6060`) — those are history and read true as
written; read an old number there through this table. **File names that carry an old number are
kept** (`tests/test_def_4497_base_size_ladder.py`, `tests/test_def_rat_5680_park_a_draft.py`,
`10-scripts/def_rat_5680_park_a_draft_walkthrough.mjs`, `10-scripts/def_pay_6234_unapplied_cash_readback.py`),
because append-only registers cite them by path.

**Proof (the PO's condition):** the register is the same length; 19 lines differ and every one is
byte-identical to the tip's once the 30 ids are masked; the ids that left are exactly the fifteen
movers and the ids that arrived are exactly their fifteen new numbers; 3,905 rows, 3,905 distinct
ids. `G17` PASS (*"13 running number(s) claimed twice, all carried (DEF-GOV-4405)"*) and `G30` PASS.

---

## `DEF-LED-6608` — TAKEN TWICE ON 2026-09-24, AND CAUGHT ON THE REBASE (lane FIN-P3)

Lane **FIN-P3** and a sibling both filed `DEF-LED-6608`, minutes apart, and
**both arithmetics were right**: `file_defect.py` asks the working tree, `HEAD`,
`@{upstream}` and every `refs/remotes/origin` ref, and the remote held neither
row when either allocator asked. Law 11's own sentence, in terms — *"it CANNOT
reserve… it removes the STALE read, which is the common case, and catches the
rare one at the only moment the answer can be final."*

| id | filed by | what it is | outcome |
|---|---|---|---|
| `DEF-LED-6608` | the sibling, pushed first | theirs | **KEPT** |
| `DEF-LED-6608` | lane FIN-P3 | 6·1's close checklist prints the raw code `unpaid_cost_accrual` to a clerk | **RENUMBERED → `DEF-LED-6614`** |

**What found it, and it was not a grep.** The duplicate surfaced as a CONFLICT
when this lane rebased its private worktree onto the moved tip: both sides had
appended to `12-governance/10-defect-log.csv`, the append/append resolution kept
both, and a `csv.DictReader` count over the resolved file reported one duplicate
id out of 3,999 rows. **A duplicate id in a 3,999-row register reads as a
register, not as an error**, so the count is what did it.

**The renumber was a byte-precise splice of the id field on ONE row**, keyed off
that row's own `reported_by` — the sibling's `DEF-LED-6608` is a different
defect and is untouched. Nothing else in the register was read back or written.
All six of this lane's ids (`6609`–`6614`) were then re-verified against the
remote with `allocate.py defect --verify` **in the same breath as the push**,
which is the only moment the answer can be final.

⚠ **THE MORE USEFUL HALF: THIS LANE ALSO FILED TWO DEFECTS AGAINST ITS OWN
CHECKS THE SAME HOUR** (`DEF-GOV-6610`, `DEF-GOV-6611`). Neither was a
collision; both were checks that could not fail. They are recorded here only
because a reader arriving at this section for the id collision should know the
two are unrelated.

---

## `BR-CUS-1096` · a protection warns the clerk and never stops them (2026-09-25)

**Lane PROT, branch `claude/kind-goldberg-k0acqg`.** One rule id, no CR number,
no defect number: a PO ruling of 2026-09-25 reverses what the product does, so
what it needs is a RULE that states the reversal and a closed question behind it
(`OQ-680`). **Nothing was built.**

| Family | Id | How it was checked |
|---|---|---|
| BR | **`BR-CUS-1096`** | `allocate.py` has no `br` family, so the maximum was taken the way that tool takes its own. `grep -o 'BR-CUS-[0-9]\{2,5\}'` over `04-docs/05-modules/03-customers/02-business-rules.md` and then over the whole worktree at the pinned tip: the highest in both is **`BR-CUS-1095`**. Re-derived from the pinned tip at push time. |

**This section is a PURE APPEND.** An in-place edit here once read as a
vanishing line and `push_paths.sh` correctly refused it.

**USED: `BR-CUS-1096`.**

---

## `BR-CUS-1097` · the balance need not be clear to reconnect (2026-09-25)

**Lane PROT, branch `claude/kind-goldberg-k0acqg`, the second id from this lane
today** — `BR-CUS-1096` is the protections ruling, this is the reconnection one,
and the two are one principle. One rule id, no CR number, no defect number: a PO
ruling supersedes half of a CONFIRMED rule (`BR-CUS-104`), so what it needs is a
RULE stating how far the supersession goes. **Nothing was built.**

| Family | Id | How it was checked |
|---|---|---|
| BR | **`BR-CUS-1097`** | `allocate.py` has no `br` family, so the maximum was taken the way that tool takes its own: `grep -o 'BR-CUS-[0-9]\{2,5\}'` over the module file and over the tree at the pinned tip. Highest is **`BR-CUS-1096`** — this lane's own, pushed to this branch an hour earlier. Re-derived from the pinned tip at push time. |

**PURE APPEND**, as the section above.

**USED: `BR-CUS-1097`.**

---

## `BR-CUS-1098` · `BR-CUS-1099` · `BR-CUS-1100` — PO rulings of one principle (2026-09-25)

**Lane RECON, branch `claude/kind-goldberg-k0acqg`.** Four rule ids, no CR
number, no gate number: five PO rulings of 2026-09-25 (four of them minting a
rule here, the fifth being `BR-CUS-1096`, already reserved by lane PROT) plus one
closed question, `OQ-384`. **Nothing was built.**

| Family | Id | How it was checked |
|---|---|---|
| BR | ~~`BR-CUS-1097`~~ | ⚠ **DRAFTED AND RELEASED, NOT USED BY THIS LANE.** At the first pinned tip `0bd39ccb4` the maximum was `BR-CUS-1096` and 1097 was free. **Re-derived at push time against tip `536030753`, `BR-CUS-1097` was TAKEN — by lane PROT, for THE SAME reconnect ruling.** Two lanes were given one decision within the hour. This lane deleted its duplicate rule and cites PROT's id; no second rule was published for one decision. **This is the re-derivation of law 11 doing exactly its job.** |
| BR | **`BR-CUS-1098`** | Re-derived against tip `536030753`: maximum `BR-CUS-1097`, so this is next free. |
| BR | **`BR-CUS-1099`** | Same read, next free. |
| BR | **`BR-CUS-1100`** | Same read, next free. ⚠ **It crosses a power of ten and is NOT zero-padded** — `CLAUDE.md`'s Screen IDs rule: five digits is a CEILING, not a spelling. |

**No OQ id was minted.** The register already held the question that ruling 5
answers — **`OQ-384`**, raised 2026-08-25, *"BLOCKS NEW SERVICE ELSEWHERE — BLOCKS
IT FOR WHOM?"* — so it was **CLOSED and its BODY REWRITTEN** rather than
duplicated. **No question about reconnection and payment existed and none was
invented.**

**This section is a PURE APPEND.** An in-place edit here once read as a vanishing
line and `push_paths.sh` correctly refused it.

**USED: `BR-CUS-1098`, `BR-CUS-1099`, `BR-CUS-1100`. RELEASED: `BR-CUS-1097` (lane PROT holds it).**

---

## `S148` · `US-CUS-032` · Put service back on (2026-09-25, lane RECONNECT)

Reconnection stops being one dialog and becomes a SCREEN of two steps at an
address of its own, built from the PO's four drawings of 2026-09-25
(`Reconnect1` · `Reconnect2` · `MasterReconnect1` · `MasterReconnect2`).
`DEF-CUS-6742` and `DEF-CUS-6743` were filed BEFORE anything was fixed.

| Family | Id | How it was checked |
|---|---|---|
| S | **`S148`** | `04-docs/01-spec/01-screen-inventory.md` says in its own words that **"the next free `S` is now `S148`"** (the `S147` addendum, amended by the runbooks one). `S148`–`S155` appear across 04-docs ONLY as the runbooks source document's own numbering, each line stating *"this repo numbers it `RBS-…`"* — that addendum **allocates no `S` number at all**, so none of the eight is taken. Re-derived from the pinned tip at push time. |
| US | **`US-CUS-032`** | `grep -rhoE "US-CUS-[0-9]{3,5}"` over the whole tree: the maximum REAL id is `US-CUS-031`. The two higher hits — `US-CUS-100` and `US-CUS-10000` — are **fixture strings inside `10-scripts/tests/test_def2804_id_width.py`**, which exists to prove the id pattern reads five digits rather than three. A lane taking the maximum without looking at where it came from would have minted `US-CUS-10001` off the back of a regression test. Re-derived at push time. |
| DEF | `DEF-CUS-6742` · `DEF-CUS-6743` | Allocated by `10-scripts/file_defect.py --id-module CUS`, which asks the REMOTE as well as this checkout (law 11). Pushed within the hour of being taken. |

⚠ **NO `BR` WAS MINTED AND THAT IS THE POINT.** Everything this screen is built
to was ALREADY signed on 2026-09-25 — `BR-CUS-1097` (the balance is shown and
never blocks) and `BR-CUS-1098` (a master's units come back together, residue
transferred up is its own line, one work order per service point). A sixth
application of that principle is the principle applying again, **not a question
to raise** (hard-won law 13). Two DESIGN choices that are NOT signed — *Remote*
as a third way back, and the new deposit drawn as a visible line — are recorded
in the decision log as this repo's judgment, reversible for the cost of one line.

⚠ **NO `OQ` WAS MINTED EITHER.** Nothing on this screen needed a ruling that had
not already been given.

**This section is a PURE APPEND.**

**USED: `S148`, `US-CUS-032`, `DEF-CUS-6742`, `DEF-CUS-6743`.**

---

## 2026-09-25 — lane GATEFIX (C3 + C6 of a checks audit), recorded AFTER the fact, not reserved ahead of it

| Family | Id | How it was checked |
|---|---|---|
| gate | **`G134`** (`g134_route_b_utilities_compile`) | `10-scripts/allocate.py gate` answered `134`; `allocate.py gate --verify 134` re-run against the moved tip `d20813d5b` answered *still free on every branch*. `ls 10-scripts/gates/` shows `g130`–`g133` and nothing higher. ⚠ `_assert_registry_sane()` refuses a duplicate G-NUMBER outright, which is the layer that actually ensures this — `allocate.py` only removes the stale read and **cannot reserve**. |
| DEF | `DEF-GOV-6777` · `DEF-GOV-6778` | ⚠ **RE-DERIVED, AND THE RE-DERIVATION IS THE POINT.** `6775`/`6776` were allocated correctly at tip `3a572853d`; while this lane worked, a sibling pushed `DEF-CUS-6775` and `DEF-CUS-6776` and version `2.352.1`. `allocate.py defect --verify 6775` and `--verify 6776` both answered **TAKEN**, and `version --verify 2.352.1` likewise, so every id and every blob was re-derived from the new pinned tip `d20813d5b` in a fresh worktree before anything was committed — law 11's unconditional push-time re-derivation, which fired on the CLEAN path, not on a conflict. |
| version | `2.352.2` | `allocate.py version --bump fix` against `d20813d5b`, after `--verify 2.352.1` answered TAKEN. |

**USED: `G134`, `DEF-GOV-6777`, `DEF-GOV-6778`, `2.352.2`. No block is held open — nothing here is a wave.**


## `CR-142-BRC07` Reports Phase 0 · the routes/seams/tests/docs half (2026-09-26)

Lane **REP-P0B**, branch `claude/kind-goldberg-k0acqg`, working in a private
`git worktree`. A sibling lane **REP-P0A** builds `P0.1`–`P0.7` and `P0.16` of
the same phase at the same time, so every id here was taken through
`10-scripts/file_defect.py --id-module <MOD>`, which asks the REMOTE and every
`refs/remotes/origin` ref rather than this checkout (law 11's id clause).

| Family | Taken | How |
|---|---|---|
| CR | **none** — built under the existing `CR-142-BRC07` | The two lanes are two halves of ONE phase of one blueprint, and that CR's register row already names it. A second number would put two spellings of one change on the branch, which is `DEF-GOV-6198`'s own lesson. |
| Defect | `DEF-REP-6808` · `DEF-REP-6809` · `DEF-SHL-6810` · `DEF-REP-6804` · `DEF-REP-6805` · `DEF-MET-6806` · `DEF-LED-6807` | `file_defect.py --id-module REP` / `SHL` / `MET` / `LED`. **All seven USED at allocation; no block is held open.** ⚠ **`DEF-REP-6796` WAS NOT TAKEN BY THIS LANE AND THAT IS THE ALLOCATOR WORKING.** A metering lane took it at `630f472c3` while this one was building; `file_defect.py` asks the REMOTE, saw it, and answered 6797. A hand count from this checkout would have taken 6796 twice (law 11's id clause). The last two are reds this lane did not cause, found by reading the suite before pushing. |
| Version | **`2.354.0`** | `allocate.py version --bump change` at 2026-09-26 12:xx, and **re-verified at push time** — lane REP-P0A may bump the same minor, which is `DEF-GOV-3756` exactly (two lanes, two correct computations, one answer). |
| OQ | **none minted.** | Nothing in this half needed a PO answer: every judgment was ours to make and is in the decision log with its figure (law 13). |
| Screen id | **none minted.** `/reports/custom` → `S47`, `/reports/scheduled` and `/reports/history` → `S45`, `/reports/dashboard` → **neither**, stated | A1 gives ONE row for *"Reports scheduled & history"* and none for a reports dashboard. **Minting an S-id is A1's act, not a routing table's**, and A1 has not been re-extracted since r9 was deleted — so the split and the absence are REPORTED in `routing/screenIds.ts`'s own notes rather than papered over with a new id. |
| Migration | `customers/0072` + `customers/0073` | Sequential from `0071`. 🔒 migration ordering and 🔒 RLS — both flagged `HUMAN-REVIEW-PENDING` with a row in `12-governance/09-human-review-ledger.md`. The sibling lane's migrations are in `reports/`, a different app, so the two cannot collide. |


## `CR-142-BRC07` Reports Phase 4 · the delivery half (2026-09-27)

Lane **REP-P4-REST**, branch `claude/kind-goldberg-k0acqg`, working in a private
`git worktree` at pinned tip `2b23c5fa0`. Sibling lanes are in
`apps/reports/queries.py`, `report_seams.py`, `ReportGroupRow.tsx`,
`ReportViewerPage.tsx` and `reportGroupRow.dom.test.tsx` — **none of which this
lane touched**, which is why `P4.4`'s missing door is FILED and not fixed here.

| Family | Taken | How |
|---|---|---|
| CR | **none** — built under the existing `CR-142-BRC07` | One phase of one blueprint. A second number would put two spellings of one change on the branch (`DEF-GOV-6198`'s lesson). |
| Defect | `DEF-REP-6913` · `DEF-REP-6914` · `DEF-SHL-6915` · `DEF-REP-6916` | `file_defect.py --id-module REP` / `SHL`, which asks the REMOTE and every `refs/remotes/origin` ref rather than this checkout (law 11's id clause). **Re-verified at push time.** ⚠ **THE FOURTH IS `6912` AND NOT `6893`, AND THAT IS THE ALLOCATOR WORKING**: siblings took nineteen numbers between this lane's third row and its fourth, and a hand count from this checkout would have taken one of them twice. `DEF-REP-6914` is FIXED in this commit; the other three are OPEN and are reported rather than taken — `6890` needs a file this lane is fenced out of, `6892` is 92 screens in another module, and `6912` is five reds a sibling's suite shipped with. |
| Version | **`2.376.0`** | `allocate.py version --bump change` against tip `2b23c5fa0`, and **re-verified at push time** — a sibling may bump the same minor, which is `DEF-GOV-3756` exactly. |
| OQ | **`OQ-REP-12757`** | `allocate.py oq`. It is a COPY question and the only thing in this build a lane could not decide: the four sentences a scheduled-report email says are ours, and no signed document writes them. Everything else was a judgment and is in the decision log with its worked figure (law 13). |
| Screen id | **none minted.** Delivery has no drawn surface: p040's `4·1` has six columns and none of them is about an envelope. | |
| Migration | **none.** `report_schedules` already exists (`reports/0004`/`0005`, `P4.1`); the message is a row in `outbound_messages`, whose table and unique key are notifications' and unchanged. | |

**USED: `DEF-REP-6913`, `OQ-REP-12757`, `2.376.0`. No block is held open — this
is one task, not a wave.**

## LANE RAT-REDS — `DEF-RAT-7030`–`7039` (2026-09-27)

| `DEF-RAT-7030–7039` | **THE RATING BASE-RESOLUTION REDS LANE (2026-09-27).** Dispatched with this block rather than taking `max + 1`, because a sibling lost six numbers to races the same day. ⚠ **NOTHING WAS USED, AND THE REASON IS WORTH MORE THAN THE BLOCK: `DEF-RAT-7030` WAS FILED AND THEN WITHDRAWN AS A DUPLICATE OF `DEF-RAT-7000`.** Both rows say the same thing — `apps/rating/seams.base_charge_for` passes `code_label=` to `apps/billing/gather._base_charge_for`, which dropped that parameter in `2b5c1b4c6` on 2026-09-24, so the rate-change impact analysis and the portal standing charge answer `TypeError` for every tenant. Lane RAT-6960 filed it first, from the portal door; this lane reached the identical line from the nine red impact tests `DEF-RAT-6980` counted. ⚠ **NEITHER LANE COULD SEE THE OTHER'S ROW WHEN IT ALLOCATED** — both worked in private worktrees, which is law 11's id clause exactly, and the register is the one place a duplicate reads as a register rather than as an error. **WHAT CAUGHT IT WAS `allocate.py defect --verify 7030` AT PUSH TIME**, which answered *TAKEN — a sibling pushed it*. ⚠ **That answer was itself a FALSE POSITIVE of the `DEF-GOV-4517` kind** — the only occurrence of `DEF-RAT-7030` on the tip was THIS ROW, swept into a sibling's pathspec commit from the shared tree — **and checking WHY it was taken is what surfaced the real duplicate one block up.** A verify failure is a reason to look, not a reason to renumber. **The withdrawn row is not in the register: it was never pushed.** `7030`–`7039` are entirely UNUSED and free for the next lane. | 2026-09-27 | **RELEASED 2026-09-27** — 0 of 10 used; `7030`–`7039` are free |

## LANE REP-P6-W4 — `DEF-REP-7150`–`7169` (2026-09-27)

Phase 6 wave 4 of `CR-142-BRC07` `P6.11`: the last three reports of the Reports
rebuild — **R4 Bill Run Readiness**, **R27 Plans & Discounts**, **R46 Bill
Projection** — built in that order, each pushed before the next is started.
Working in a private `git worktree` off pinned tip `3b360d803`.

| Family | Taken | How |
|---|---|---|
| CR | **none** — built under the existing `CR-142-BRC07` | One phase of one blueprint, the same reasoning wave 3 recorded. |
| Defect | block **`7150`–`7169`**, written here BEFORE any allocation | `file_defect.py --id-module REP --block 7150-7169` refuses a block that exists only in a briefing, so the block is recorded first. ⚠ **`7110` IS ALREADY TAKEN AND THE ALLOCATOR SAID SO** — the coordinator's own rows took `7110`–`7112` out of it before this lane pushed. A block written into a briefing is a claim about the remote, and the allocator is the thing that checks it. **Re-verified with `allocate.py defect --verify` at push time.** |
| OQ | **`allocate.py oq`, NOT this block** | ⚠ **THE OQ FAMILY HAS ITS OWN RUNNING NUMBER AND IT IS FAR ABOVE `7129`** — `allocate.py oq` answers **`12768`**, and wave 3's lane took `OQ-REP-12757`. Taking an OQ from the `7110`–`7129` block would have minted a duplicate of a question that already exists, which in a 777-row register reads as a register rather than as an error (law 11's id clause). **A block reserved for one family says nothing about another.** |
| `BR-` | **`BR-REP-060`**, stepped clear of the frontier | A `BR-` id has no allocator. The frontier is `BR-REP-050`; three lanes collided on `043`/`044`/`045` today by taking `max + 1`, so this steps to `060`. **Verified free across every `refs/remotes/origin` ref**, not just this checkout. |
| Version | `allocate.py version --bump change`, re-verified at push time | |
| Migration | **none expected** — all three reports read spines that already exist. | |

## LANE RAT-REDS-9 — `DEF-RAT-7140`–`7149` (2026-09-27)

Lane **RAT-REDS-9**, branch `claude/kind-goldberg-k0acqg`, working in a private
`git worktree` at pinned tip `5a75e6258`. Dispatched with this block rather than
taking `max + 1`, for the reason the RAT-REDS block one up records: siblings lost
six numbers to races the same day, and `allocate.py` asks the remote but cannot
RESERVE.

| Family | Taken | How |
|---|---|---|
| Defect | `DEF-RAT-7140` | `file_defect.py --id-module RAT --block 7140-7149`, **re-verified at push time**. It is the true cause of the eight `test_br_rat_091_rate_change_impact.py` reds, which were parked under `DEF-RAT-7000` whose fix (`bb62396d2`) is an ancestor of every commit the reds were measured at — so the park named a cause that was already closed. |
| CR | **none** — this is a defect fix, not a change to the agreement (`13-change-process.md` §1). | |
| OQ | **none minted.** The collision between BR-RAT-091's ratified `$0.00` base and the sample utility's signed `$8` was ours to decide and is in the decision log with its worked figure (law 13). Neither signed figure moved. | |
| Version | **none bumped** — no CR is closed here. | |
| Migration | **none.** | |

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-RAT-7140–7149` | RAT-REDS-9, branch `claude/kind-goldberg-k0acqg`, worktree at pinned tip `5a75e6258` | 2026-09-27 | **ACTIVE** |

**USED: `DEF-RAT-7140`. `7141`–`7149` are UNUSED and free for the next lane.**

## LANE REP-STMT-SCREEN — `DEF-REP-7290`–`7309` (2026-09-28)

Lane **REP-STMT-SCREEN**, branch `claude/kind-goldberg-k0acqg`, working in a
private `git worktree` off a pinned tip. Dispatched with this block rather than
taking `max + 1`, for the reason every block above it records: `allocate.py`
asks the remote but cannot RESERVE, and three lanes were live on this branch
the same hour.

| Family | Taken | How |
|---|---|---|
| Defect | `DEF-REP-7290` | `file_defect.py --id-module REP --block 7290-7309`, **re-verified at push time**. It is a NEW finding made while proving `DEF-REP-7053` over real HTTP: `GET /api/exports/{job}/file` streams a money CSV with **no `Cache-Control` header at all** — measured, headers quoted in the row — where the neighbouring signed-delivery route sets `no-store, private`. Filed rather than fixed in passing: it is a platform route serving nine lists and S61, not this screen's. |
| CR | **none** — three defect fixes, not a change to the agreement (`13-change-process.md` §1). | |
| OQ | **none minted.** Which of three candidate fixes to take for the collapsing columns was ours to decide and is in the decision log with its worked figure (law 13). No signed rule moved. | |
| Version | `2.385.1` — `allocate.py version --bump fix`, re-verified at push time. | |
| Migration | **none** — nothing here touches a table. | |

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-REP-7290–7309` | REP-STMT-SCREEN, branch `claude/kind-goldberg-k0acqg`, private worktree | 2026-09-28 | **ACTIVE** |

**USED: `DEF-REP-7290` and `DEF-REP-7291`. `7292`–`7309` are UNUSED and free for the next lane.**

## LANE BIL-PLANBASE — `DEF-BIL-7310`–`7329` (2026-09-28)

Lane **BIL-PLANBASE**, branch `claude/kind-goldberg-k0acqg`, working in a
private `git worktree` off a pinned tip. Dispatched with this block rather than
taking `max + 1`, for the reason every block above it records: `allocate.py`
asks the remote but cannot RESERVE, and other lanes are live on this branch the
same hour. The block is written here BEFORE anything is allocated from it.

Building the PO ruling of 2026-09-28 — *"we will never take default value from
plan $8.0 - that is retired"* — over `apps/billing/gather._base_charge_for`
(`DEF-BIL-7170`, critical, already filed by the PO) and the portal demo fixture
(`DEF-CWP-7001`).

| Family | Taken | How |
|---|---|---|
| Defect | **none minted yet** — `DEF-BIL-7170` and `DEF-CWP-7001` are both already filed and this lane CLOSES them. A new row is taken from this block only if a new finding appears. |
| CR | **none** — a defect fix against a ruling already in the decision log, not a change to the agreement (`13-change-process.md` §1). | |
| OQ | **none minted.** The ruling answers the question; what is left — whether the retired column stops being WRITTEN and SHOWN — is named NOT RULED in the decision log entry and is deliberately not touched here. | |
| Version | `allocate.py version --bump fix`, re-verified at push time. | |
| Migration | **none** — nothing here touches a table. | |

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-BIL-7310–7329` | BIL-PLANBASE, branch `claude/kind-goldberg-k0acqg`, private worktree | 2026-09-28 | **ACTIVE** |

**USED: `DEF-BIL-7310` — filed, not fixed: `resolution_switch`'s R2-without-R3/R4 fork still compares the retired `tariff_versions.base_charge`. `7311`–`7329` are UNUSED and free for the next lane.**

Version taken: **`2.387.1`**, `allocate.py version --bump fix`, re-derived from the tip at push time after the first attempt was REFUSED — a sibling had bumped to `2.387.0` while this lane worked, so the number was re-taken against the tip's bytes rather than re-applied over a stale copy (law 11).

## LANE MET-GAPFILTER — `DEF-MET-7220`–`7239` (2026-09-28)

Lane **MET-GAPFILTER**, branch `claude/kind-goldberg-k0acqg`, working in a
private `git worktree` off a pinned tip. Dispatched with this block rather than
taking `max + 1`, for the reason every block above it records: `allocate.py`
asks the remote but cannot RESERVE, and other lanes are live on this branch the
same hour.

**What the lane is doing:** the PO ruling of 2026-09-28 — *"the Units 'Missing
services' block — filter or leave it. - filter"*. The separate
`UnitServiceGaps` block is DELETED, `GET /units/service-gaps` is retired, and
its two facts become a **Missing services** filter plus two columns on the
ordinary units list, with the count carried on the toolbar whether or not the
filter is engaged.

| Family | Taken | How |
|---|---|---|
| Defect | see below | `file_defect.py --id-module MET --block 7220-7239`, **re-verified at push time**. |
| CR | **none** — the ruling is already recorded in `02-decision-log.md` (2026-09-28) and this lane builds it. | |
| OQ | **none minted.** | |
| Version | `allocate.py version --bump change`, re-verified at push time. | |
| Migration | **none** — nothing here touches a table. | |

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-MET-7220–7239` | MET-GAPFILTER, branch `claude/kind-goldberg-k0acqg`, private worktree | 2026-09-28 | **ACTIVE** |

**USED: `DEF-MET-7220`** — PRM-01U's toolbar spills onto a second line the
moment ANY filter chip is applied, against B14 rule 12's one-line grammar.
**Filed, not fixed:** measured in Chromium at 1440 with only the PRE-EXISTING
`f.plan=unplanned` applied, so it is not caused by this lane's chip, and the fix
belongs to the shared `FilterBar` rather than to this screen.
⚠ **`allocate.py defect --verify 7220` ANSWERS `TAKEN` AND IT IS READING THIS
RESERVATION BACK.** It greps pushed code AND remote commit messages, and both
carry `DEF-MET-7220–7239` from the commit that opened this block. That is the
allocator being over-eager in the safe direction on a RESERVED range, not a
sibling collision: no ref's `10-defect-log.csv` holds the id, checked across
every `refs/remotes/origin`. `file_defect.py --block 7220-7239` is what
allocated it and it is the tool that knows about blocks.

**USED: `DEF-MET-7221`** — the unit's Assets tab draws no `On since` date and
its case has been red since at or before `870b4c21f` (2026-09-23). **Dated by a
RUN at that commit in a throwaway worktree, not by a claim** (law 7 habit 1).
Filed, not fixed: it belongs to whoever owns the assets seam.

**Version taken: `2.387.0`** (`allocate.py version --bump change`, re-verified
at push time). **`7222`–`7239` are UNUSED and free for the next lane.**

## LANE REP-EDITOR-PAGE — `DEF-REP-7200`–`7219` (2026-09-28)

Lane **REP-EDITOR-PAGE**, branch `claude/kind-goldberg-k0acqg`, working in a
private `git worktree` off a pinned tip. Dispatched with this block rather than
taking `max + 1`, for the reason every block above it records: `allocate.py`
asks the remote but cannot RESERVE, and other lanes are live on this branch the
same hour.

| Family | Taken | How |
|---|---|---|
| Defect | `DEF-REP-7200` · `DEF-REP-7201` · `DEF-REP-7202` | `file_defect.py --id-module REP --block 7200-7219`, **re-verified at push time**. `7200`: section ⑤ *Group & sort* draws five rows in the drawing (`Level 1`, `Level 2`, `Level 3`, `Subtotals`, `Sort`) and the editor builds three — the last two have authored catalogue keys in all eleven languages and no control; filed not fixed, because honouring them is the runner's half (`P2.17`). `7201`: a global `.view label:has(> select)` rule stacks a label above its control at specificity (0,1,2), beating the component's own `flex` utility — **found by measuring `getComputedStyle` in a browser at 1440 and by nothing else**; the instance on 2·2 is FIXED here by not matching the selector, the general case is not. `7202`: the builder offers a column called `teller` — a stored column name on screen, because `reportWord`'s fallback is the raw name and a key that exists in no language is invisible to a parity check. |
| CR | **none** — this executes the PO ruling of 2026-09-28, which is already captured and already in the decision log (`d8c4bc1cb`). Re-capturing it would be a second CR for one instruction. |
| OQ | **none minted.** *What the clerk sees while choosing* was explicitly handed to this lane to decide (decision log, 2026-09-28). It is decided, with its reasoning, in `ReportEditorPage.tsx`'s own docstring and in `04-docs/05-modules/12-reports/07-builder-screen-2-2-drawn-spec.md` §9. No signed rule moved. |
| Version | `2.386.0` — `allocate.py version --bump change`, re-verified at push time. |
| Migration | **none** — nothing here touches a table. |

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-REP-7200–7219` | REP-EDITOR-PAGE, branch `claude/kind-goldberg-k0acqg`, private worktree | 2026-09-28 | **ACTIVE** |

**USED: `DEF-REP-7200`, `DEF-REP-7201`, `DEF-REP-7202`. `7203`–`7219` are UNUSED and free for the next lane.**

## LANE CORS-HEADERS — `DEF-INF-7616`–`7619` (2026-09-28)

Lane **CORS-HEADERS**, branch `claude/confirm-understanding-3ktufc`, working in a
private `git worktree` off the pinned tip `eb0e5c7c0`. Dispatched to fix a LIVE
beta defect: every API call from the deployed SPA is refused in preflight because
the API grants only django-cors-headers' six default request headers, and the
client sends `X-Support-Ref` on every call.

A block rather than `max + 1` for the reason every block above it records:
`allocate.py` asks the remote and **cannot RESERVE**, and other lanes are live on
this branch and on sibling branches the same hour. ⚠ This worktree's HEAD was 7
commits ahead of the target tip when the lane started — those commits belong to
lane BRC09 and are pushed on `origin/claude/brave-dijkstra-xgfsgz`, so both shared
registers were **re-derived from the tip** before anything was appended, and this
lane's commit carries only its own rows (law 11, mechanism five).

| Family | Taken | How |
|---|---|---|
| Defect | `DEF-INF-7616` | `file_defect.py --id-module INF --block 7616-7619`, **re-verified at push time**. The CORS request/response header grant: `CORS_ALLOW_HEADERS` and `CORS_EXPOSE_HEADERS` were never set, so the preflight refuses `x-support-ref` and `if-none-match` and the browser hides every contract-bearing response header. |
| CR | **none** — a beta report of the product not doing what is expected is a DEFECT by default (`13-change-process.md` §1, PO 2026-09-10). No agreement moved. |
| OQ | **none minted.** No rule ran out: the header lists are read off the front end's own code, and CR-144-BRC07's *"exactly one origin, never `*`"* is untouched. |
| Version | `2.390.1` — `allocate.py version --bump fix`, re-verified at push time. |
| Migration | **none** — nothing here touches a table. |

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-INF-7616–7619` | CORS-HEADERS, branch `claude/confirm-understanding-3ktufc`, private worktree | 2026-09-28 | **ACTIVE** |

**USED: `DEF-INF-7616`. `7617`–`7619` are UNUSED and free for the next lane.**

## LANE REP-BUILD-YOUR-OWN — `DEF-REP-7640`–`7649` (2026-09-28)

Lane **REP-BUILD-YOUR-OWN**, branch `claude/confirm-understanding-3ktufc`,
working in a private `git worktree` off a pinned tip. Maintenance, not build:
the Product Owner pressed `+ Build your own` on **Reports → Catalogue** in
deployed `v2.388.0` and nothing happened.

⚠ **THE BLOCK OPENS AT 7640 AND NOT AT `max + 1`, WHICH `allocate.py defect`
ANSWERS AS `7616`.** `DEF-CUS-7600–7629` is reserved above this row by the New
Connect lane on branch `claude/brave-dijkstra-xgfsgz`, and the allocator cannot
see a RESERVATION — it sees only ids already used, so it would have handed this
lane a number inside somebody else's open block. `7630`–`7639` are left as a
gap rather than claimed, because a block that abuts a live one is the next
lane's off-by-one. Verified `allocate.py defect --verify 7640` → *"still free on
every branch (this tree not counted)"*, at allocation and again at push time.

| Family | Taken | How |
|---|---|---|
| Defect | `DEF-REP-7640` | `file_defect.py --id-module REP --block 7640-7649`, **re-verified at push time**. The `+ Build your own` button on screen 1·1 navigates to `/reports/custom`, which since `P5.10` mounts the SAME catalogue on its Custom sub-tab — so from `/reports/custom` the click does nothing at all and from the catalogue it switches sub-tab to an empty list. A live control in front of a screen that does not exist: hard-won law 2's mirror. |
| CR | **none** — this is a DEFECT and the beta's default is a defect (`12-governance/22-product-maintenance-process.md`, PO 2026-09-10: *"CR is change in product, defect is product does not do what is expected"*). The product did not do what the button promised. |
| OQ | **none minted.** The PO ruled the behaviour in the same breath as reporting it — *"Opens the editor on a blank definition, then Save as"* — so nothing is unanswered. The route SHAPE was ours to decide and is decided in the decision log with its reasoning (law 13). |
| Version | `2.390.1` — `allocate.py version --bump fix`, re-verified at push time. |
| Migration | **none** — nothing here touches a table. `POST /reports/definitions` already creates a report from a draft with `based_on: null`. |

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-REP-7640–7649` | REP-BUILD-YOUR-OWN, branch `claude/confirm-understanding-3ktufc`, private worktree | 2026-09-28 | **ACTIVE** |

**USED: `DEF-REP-7640` and version `2.390.1`. `7641`–`7649` are UNUSED and free
for the next lane.**

## ID MOVE — `DEF-MET-7804`→`7811`, `DEF-MET-7805`→`7812` (2026-09-29)

Lane **GATE-CENSUS**, branch `claude/brave-dijkstra-xgfsgz`. **Not a
reservation — a repair**, recorded here because this file is where this repo
already writes down an id that moved (see the `7800`–`7803` note above).

`DEF-MET-7804`/`7805` and `DEF-CUS-7804`/`7805` were filed minutes apart by two
lanes whose allocators were both right. **The module segment is not part of the
number** (PO 2026-09-03), so those were two pairs of ids sharing one pair of
numbers, and a bare citation of `7804` resolved to two real rows.

**The MET pair moved and the CUS pair did not**, because the CUS ids are cited
in three landed commits and the MET ids in one — the cheaper move. Done with
`10-scripts/renumber_defect.py`, one line rewritten per row, prefix proved
byte-identical over the first 8,528,082 and 8,530,112 bytes. **Zero citations
outside the register** for either id.

⚠ **ONE DANGLING CITATION REMAINS AND IT CANNOT BE REPAIRED, WHICH IS WHY IT IS
WRITTEN HERE.** Commit `4148ded57` on this branch — *"the build record stops
printing machine tokens to a clerk in four places — DEF-MET-7805 — 2.393.7"* —
names the OLD number in its subject, and a commit message is immutable. **A
reader who greps `DEF-MET-7805` and finds only that commit should read
`DEF-MET-7812`.** That cost was known before the move and is the one landed
commit the trade above refers to.

| Old | New | Title (abridged) |
|---|---|---|
| `DEF-MET-7804` | `DEF-MET-7811` | A fix commit was a pure revert: 205 lines of a sibling's `buildViews.tsx` deleted |
| `DEF-MET-7805` | `DEF-MET-7812` | The build detail page prints raw internal codes to the clerk in four places |

**This is the collision `allocate.py`'s new reservation read (`DEF-GOV-7814`)
exists to prevent** — and it happened while that fix was being written, which
is the sharpest argument for it. The allocator now reads this file from every
remote ref, so a number inside an open block is refused BY NAME.

## RESERVATION — Settings → Security redesign, lane SEC-REDESIGN (2026-09-29)

Branch `claude/brave-dijkstra-xgfsgz`, private worktree
`.claude/worktrees/agent-a6cb4c0caf5549d63`. Building the PO-approved redesign
of Settings → Security from `05-prototype/security-redesign-2026-09-29/`
(approved 2026-09-29).

| Family | Taken | How |
|---|---|---|
| Defect | `DEF-IDN-7826`–`DEF-IDN-7835` | `allocate.py defect` against the remote, re-verified at push time. Front-end half of the redesign; `DEF-IDN-7501`'s front-end half closes inside it. |
| CR | `CR-155-BRC09` | `allocate.py cr` against the remote. The PO asked for the screen to change and approved the drawing, so it is a CHANGE and not a defect (`13-change-process.md` §1). |
| Version | `2.394.0` | `allocate.py version --bump change`, re-verified at push time. |
| Migration | **none** — this lane touches no table and no backend file. The audit card's READ and the four new choice lists are the SERVER lane's, in `06-backend/apps/identity/`. |

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-IDN-7826–7835` | SEC-REDESIGN, branch `claude/brave-dijkstra-xgfsgz`, private worktree | 2026-09-29 | **ACTIVE** |

⚠ **`DEF-IDN-7810` IS CITED IN THIS LANE'S BRIEFING AS FILED AND NO ROW EXISTS**
— zero hits in `12-governance/10-defect-log.csv`. It is filed for real inside
this block rather than left as prose, which is CLAUDE.md hard rule 4's own
lesson: *a finding recorded only in the file you happen to be in is a finding
nobody can count.*
---

## `DEF-7660–7669` — lane **AST-ASSIGN-SIZE**, 2026-09-28

Two PO-reported findings worked together on branch
`claude/confirm-understanding-3ktufc`, in a private worktree: a meter can be
installed from inventory with **no connection size**, and the rate-schedule
overlap `apps/rating/migrations/0004` reported and never closed.

⚠ **ONE NUMERIC BLOCK, TWO MODULE PREFIXES.** The module segment is provenance
and the NUMBER is what has to be unique (CLAUDE.md's Screen-IDs section), so
`DEF-AST-…` and `DEF-RAT-…` ids in this lane draw from this one block rather
than from two. Reading it as two blocks is how a lane takes `7661` twice.

⚠ **THE BLOCK STARTS AT `7660` AND NOT AT `7643`, WHICH IS WHAT THE ALLOCATOR
ANSWERED.** `DEF-REP-7640–7649` is ACTIVE one row up and its own note releases
`7641`–`7649`; a block that abuts a live one is the next lane's off-by-one, so
`7650`–`7659` is left as a gap rather than claimed. Verified
`allocate.py defect --verify 7660` and `--verify 7669` → *"still free on every
branch (this tree not counted)"*, at allocation and again at push time.

| Family | Taken | How |
|---|---|---|
| Defect | `DEF-AST-7660` · `DEF-AST-7661` · `DEF-RAT-7662` | `file_defect.py --id-module AST\|RAT --block 7660-7669`, each **re-verified at push time**. |
| CR | **none** — the beta's default is a defect (`22-product-maintenance-process.md`, PO 2026-09-10: *"CR is change in product, defect is product does not do what is expected"*). A form that cannot record the fact the base charge is priced on did not do what was expected. |
| OQ | **none minted.** The requirement boundary is read from ratified law already in the tree — `BR-AST-530` (the size is offered for METERS) and `apps.rating.resolution.service_prices_by_size_class` (which services band). Nothing was decided by choosing a value. |
| Version | `2.390.2` — `allocate.py version --bump fix`, re-verified at push time. |
| Version SHIPPED | `2.392.3`. ⚠ **THE ROW ABOVE IS WHAT WAS RESERVED AND IS LEFT STANDING RATHER THAN CORRECTED, BECAUSE A RESERVATION IS A HISTORICAL CLAIM AND OVERWRITING IT IS HOW A REGISTER LOSES A LANE.** `--verify` then refused `2.390.2`, `2.391.1`, `2.392.1` and `2.392.2` in turn, each taken by a sibling while this lane worked; `2.392.3` verified free on every branch at push time. **FOUR COLLISIONS ON ONE LANE IN ONE AFTERNOON IS THE MEASUREMENT, NOT THE ANECDOTE** — `--bump` reads THIS branch and `--verify` reads EVERY branch, so the two disagree whenever a sibling is mid-flight and only the second is a fact. **This row exists because `push_register_guard.py` REFUSED the obvious edit** (rewriting the row above) as a revert by subtraction, which it is: an append is the only safe write to a shared register, and that is true of a row you believe is your own. |
| Migration | **none** — `assets.size_class` already exists (`BR-AST-500`). Nothing here adds, alters or drops a column, and PART 2 writes no row at all. |

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-7660–7669` | AST-ASSIGN-SIZE, branch `claude/confirm-understanding-3ktufc`, private worktree | 2026-09-28 | **ACTIVE** |

## LANE DSC-WIZARD-REFUSAL — `DEF-CUS-7680`–`7689` (2026-09-28)

Lane **DSC-WIZARD-REFUSAL**, branch `claude/confirm-understanding-3ktufc`,
working in a private `git worktree` off the pinned tip `db075389b`. Dispatched
to fix a LIVE beta defect: the **disconnect wizard** (`DSC-02`,
`/{tenant}/disconnects/new?step=4`, deployed `v2.352.0`) refuses on its last
step after every step is filled and shows the clerk nothing they can act on —
`POST /disconnects/schedule` answers `422 BIZ-COMPLETENESS` carrying the exact
reason in `params.code`, and no screen reads it.

⚠⚠ **THIS LANE'S FIRST BLOCK WAS TAKEN OUT FROM UNDER IT BETWEEN ALLOCATION AND
FILING, AND IT IS WORTH THE PARAGRAPH BECAUSE EVERY STEP WAS DONE CORRECTLY.**
The lane ran `allocate.py defect --verify 7660` and `--verify 7661`, was told
*"still free on every branch"*, wrote the reservation row for `7660`–`7669`,
and ran `file_defect.py`. In the minutes in between, lane **AST-ASSIGN-SIZE**
pushed `DEF-AST-7660`, `DEF-AST-7661` and `DEF-RAT-7662` and a reservation row
claiming the same ten numbers. **`allocate.py` cannot RESERVE and says so** —
it removes the stale read and cannot stop a simultaneous one — and a
RESERVATION row is invisible to it, because it counts ids that are USED.
`file_defect.py` then did the one thing that saved it: it re-read the remote,
answered `DEF-CUS-7663` rather than `7660`, and **printed that this tree's
register was 6 rows behind the tip**, which is the loss-by-subtraction of
CLAUDE.md law 11 caught at the only moment it can be caught. Nothing was
pushed; the tree was fast-forwarded and everything below was re-derived.
**So this block opens at `7680`, clear of `DEF-AST-7660–7669` with `7670`–`7679`
left as a gap.**

⚠⚠ **AND THE VERSION MOVED TWICE, THE SECOND TIME BECAUSE THIS LANE BRIEFLY
TRUSTED ITS OWN ARITHMETIC OVER THE ALLOCATOR.** At allocation
`allocate.py version --bump fix` answered `2.390.2`, which AST's pushed
reservation row already claimed — two lanes shipping one version is
`DEF-GOV-3756` — so this lane reached for the obvious next number, `2.390.3`,
and wrote it into this row, the CHANGELOG and the decision log. **It was
wrong.** Re-run at bump time the allocator answered **`2.392.2`**: AST had
pushed its bump (the tree read `2.390.2`) and, more to the point, the maximum
is taken over the WHOLE MATRIX of branches and some branch already carries
`2.392.1`. `2.390.3` verified as *"still free"* — **and free is not the same as
next**, which is exactly the trap `allocate.py`'s own docstring records for
`2.179.1`.

⚠⚠ **AND IT MOVED A THIRD TIME, AT PUSH TIME, WHICH IS THE ONLY MOMENT THAT
COULD HAVE CAUGHT IT.** By then `origin/claude/brave-dijkstra-xgfsgz` had
pushed `2.392.2` — *"TAKEN — origin/claude/brave-dijkstra-xgfsgz carries it.
Re-bump before you commit."* — so this lane is on **`2.393.4`**, verified free
on every branch at the same breath as the blob re-derivation. **Three
allocations, all arithmetically right, two of them stale before they were
used.** `allocate.py` cannot reserve and does not claim to; what it removes is
the stale read, and running it AGAIN at push time is the whole of the
mitigation.

⚠ **`allocate.py defect --verify 7680` ALSO ANSWERED *"TAKEN — a sibling pushed
it"*, AND THAT ONE IS THIS LANE'S OWN ROW.** It was pushed in `8f9bef45d`
before any code was written, which is the maintenance process working as
intended — file the defect BEFORE fixing it. The register at the tip holds
`DEF-CUS-7680` exactly ONCE and the row is this lane's, so the id stands.
**A `--verify` refusal is a prompt to go and look, not a verdict**: it cannot
tell your own pushed row from a stranger's.

The three authoritative files, the CHANGELOG and the decision log all carry
`2.393.4`.

| Family | Taken | How |
|---|---|---|
| Defect | `DEF-CUS-7680` | `file_defect.py --id-module CUS --block 7680-7689`, **re-verified at push time**. `transfer_disconnect_api._as_catalog_refusal` maps every `DisconnectRuleError` onto one `BIZ_COMPLETENESS` + `customers.disconnects.refused` and puts the service's machine `code` in `params.code` *"so a screen can branch without parsing English"* — and no screen branches. Eighteen distinct refusals reach the clerk as one sentence that names none of them. |
| CR | **none** — a beta report of the product not doing what is expected is a DEFECT by default (`13-change-process.md` §1 · `22-product-maintenance-process.md`, PO 2026-09-10: *"CR is change in product, defect is product does not do what is expected"*). No agreement moved: the server already decided every one of these refusals and already published the code. |
| OQ | **none minted.** No rule ran out. The copy is B14 rule 33's to shape and the branch-on-code instruction is `_as_catalog_refusal`'s own docstring; the refusal SET is the server's and is not widened, narrowed or re-argued here. |
| Version | `2.393.4` — see the paragraph above. `--bump fix` answered `2.390.2` at allocation (reserved by AST) and `2.392.2` at bump time, because the maximum is taken across every branch and one already carries `2.392.1`. Re-verified at push time. |
| Migration | **none** — nothing here touches a table. The step-1 pre-flight is a READ over rows that already exist. |

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-CUS-7680–7689` | DSC-WIZARD-REFUSAL, branch `claude/confirm-understanding-3ktufc`, private worktree | 2026-09-28 | **ACTIVE** |

**USED: `DEF-CUS-7680` and version `2.393.4`. `7681`–`7689` are UNUSED and free
for the next lane.**

### LANE REP-BUILD-YOUR-OWN — what the block actually spent (amended 2026-09-28, same lane)

The section above was written before the first row was filed and it says
**USED: `DEF-REP-7640` and version `2.390.1`**. Both halves moved while the work
was being done, so they are corrected here rather than edited in place — the
row above is already on the branch and a register is a log.

| Family | What was actually taken | Why it moved |
|---|---|---|
| Defect | `DEF-REP-7640` · `DEF-REP-7643` · `DEF-REP-7644` · `DEF-SHL-7645` · `DEF-REP-7646` | `7640` is the defect itself. The other four were found while fixing it and filed rather than absorbed: `7643` the screen-id row that has never existed for `/reports/history/:runId`, `7644` a run-history retention case red for reasons measured to be independent of this lane, `DEF-SHL-7645` the same screen-id drift measured properly at **21 routes with no row, 180 routed against 159 mapped**, and `7646` a comment citing a real defect about something else. ⚠ **`7646` WAS FILED AS `7642` AND RENUMBERED AT PUSH TIME**: `allocate.py defect --verify 7642` answered *TAKEN — a sibling pushed it* on the re-verification law 11 prescribes, so the row was rebuilt onto the tip's bytes under a free number and its two citations moved with it. The allocator asks the remote and cannot reserve; this is the rare case it exists to catch at the only moment the answer can be final. |
| Version | `2.390.2` | The section above says `2.390.1`. A sibling shipped that number (`CR-151-BRC09`) while this lane worked, and `allocate.py version --verify 2.390.1` answered TAKEN. Re-bumped and re-verified against the tip at push time. |

**Still UNUSED and free for the next lane: `7641`, `7642` (taken elsewhere —
do NOT reuse from this block), `7647`, `7648`, `7649`.**

---

## `DEF-CUS-7700–7709` · LANE CUS-TILES — the Accounts register's four status tiles (2026-09-28)

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-CUS-7700–7709` | **LANE CUS-TILES — PO ruling 2026-09-28: the Accounts list carries FOUR tiles (Active · Pending · Disconnecting · Suspended), each of which SETS the list's filter when pressed. Branch `claude/confirm-understanding-3ktufc`, private worktree.** Written here BEFORE the first row is filed, which is what `file_defect.py --block` refuses without — a block claimed on the command line and nowhere else is the promise that does not survive the chat. ⚠ **IT OPENS AT 7700, WELL ABOVE THE FRONTIER (`7641` when this lane started), RATHER THAN AT `max + 1`**, because sibling lanes compute `max + 1` correctly and all get the same answer (`DEF-1787`). Version `2.392.0`, from `allocate.py version --bump change` (`2.391.0` was allocated first and `--verify` found `origin/claude/brave-dijkstra-xgfsgz` had taken it while this lane worked — the collision law 11 exists for, caught at the only moment the answer can be final) and re-verified at push time. | 2026-09-28 | **ACTIVE** |

**USED: `DEF-CUS-7700`, `DEF-CUS-7701`, `DEF-INF-7702`. `7703`–`7709` are UNUSED and free for the next lane.** ⚠ **THE BLOCK IS BY NUMBER, NOT BY PREFIX** — `7702` names an INFRA finding this lane tripped over (the smoke stack builds a production bundle) and takes its number from here rather than from the register frontier, which is what the block is for.

---

## `DEF-CUS-7860–7869` · LANE REQ03-SERVER — New Request, six steps into four: the SERVER half (2026-09-29)

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-CUS-7860–7869` | **LANE REQ03-SERVER — the approved redesign of `REQ-03` (`05-prototype/new-request-four-steps-2026-09-29/`, PO 2026-09-29), tasks 1–4 of 12: the refusal-to-step map, the review step's `What the customer is told` card, the fee row and its total, and `check` rather than `cheque`. Branch `claude/brave-dijkstra-xgfsgz`, private worktree.** Written here BEFORE the first row is filed, which is what `file_defect.py --block` refuses without. ⚠ **IT OPENS AT 7860, WELL ABOVE THE FRONTIER (`7836` when this lane started), RATHER THAN AT `max + 1`**, because three sibling lanes are live on this same redesign and all four would compute `max + 1` correctly and get the same answer (`DEF-1787`). Version `2.398.0`. ⚠ **`2.395.0` AND THEN `2.396.0` WERE EACH ALLOCATED AND `--verify` FOUND A SIBLING HAD SHIPPED BOTH** while this lane worked — the collision law 11 exists for, caught at the only moment the answer can be final. All three lockstep files were then RE-DERIVED FROM THE TIP rather than bumped in place, because the sibling had also moved `07-frontend/package.json` and its lock and this worktree's copies were two versions behind; writing them back would have reverted that by subtraction. ⚠ **The two `DEF-CUS` rows below carry `found_in 2.395.0`, which is the number this lane held when it filed them, and they are LEFT** — rewriting a line of a shared register to correct an off-by-one is the whole-file-write hazard `file_defect.py` exists to prevent, and the row is a log. | 2026-09-29 | **ACTIVE** |

**USED: `DEF-CUS-7860`, `DEF-TEN-7861`, `DEF-CUS-7862`. `7863`–`7869` are UNUSED and free for the next lane.** Also taken, from the module's own sequence and not from this block: **`BR-CUS-1110`** (the tender is spelled `check`). ⚠ **IT WAS ALLOCATED AS `BR-CUS-1100` FIRST AND THAT NUMBER WAS ALREADY TAKEN** — the module's rules table ends at `BR-CUS-1099`, and four more rules live BELOW it as `##` headings rather than table rows, so a lane reading the table takes a number that is in the file three screens further down. The true maximum is `BR-CUS-1105`, found by grepping every file rather than the one that looks authoritative. There is no `allocate.py` family for `BR-`, so this is a hand count, it opens at `1110` rather than `1106` for the reason the defect block opens above the frontier, and it is recorded here because a hand count nobody wrote down is how two lanes take one number. ⚠ **THE BLOCK IS BY NUMBER, NOT BY PREFIX** — `7861` names a TENANCY finding this lane measured (`CENTRE_PAYMENT_METHODS` still spells the tender `cheque` and refuses `check` by name) and takes its number from here rather than from the register frontier, which is what the block is for. It is filed and NOT fixed: `apps/tenancy/` is not this lane's, and `13-change-process.md` §1 routes a product-does-not-do-what-is-expected report to a defect owned by the module that holds the code.

---

## The Move-in navigation lane (`MOVEIN-NAV`) — 2026-09-29

| Block | Lane | Reserved | State |
|---|---|---|---|
| `DEF-CUS-7900–7909` | **LANE MOVEIN-NAV — PO-reported navigation defect on the Move-in flow: *"when user select the move-in user should redirect on move-in list page or move-in request form; on list view draft request should be open in move in -wizard form"*. One rule, three links: an unfinished move-in opens the WIZARD, a finished one opens the RECORD. Branch `claude/brave-dijkstra-xgfsgz`, private worktree.** ⚠⚠ **THIS LANE FIRST RESERVED THE BLOCK AT `7860` AND HAD TO RENUMBER — `DEF-1787` HAPPENING AGAIN, LIVE, AND WORTH THE SPACE BECAUSE EVERY STEP WAS DONE CORRECTLY.** The block was written HERE before the first row was filed, `file_defect.py --block` allocated inside it, and `allocate.py defect --verify` answered *"still free on every branch"* — twice, an hour apart. **It was true both times.** While this lane worked, **lane `REQ03-SERVER` filed its own row at that number** (*"PATCH /service-requests/{id} is the one capture door whose refusals carry no step"*) and pushed first. **Neither lane was wrong: a reservation written in a PRIVATE WORKTREE is in none of the places `allocate.py` can read until it is pushed** — the promise-that-does-not-survive-the-chat blind spot one layer down, where it does not survive the *worktree* either. **What caught it was `push_paths.sh`'s duplicate-id guard at push time**, printing *"appears 2× (was 1× at the tip)"*, and not any of the three correct verifications before it; a duplicate id in an 8.5 MB register reads as a register and not as an error. **The lane renumbered rather than overrode**, which is the only right move — the first number belongs to whoever pushed it. ⚠ **AND THE NEW BLOCK OPENS AT `7900`, WELL ABOVE THE RE-CHECKED FRONTIER (`7870`)**, rather than at `max + 1`, for the reason this file keeps repeating: sibling lanes compute `max + 1` correctly and all get the same answer. `DEF-IDN-7826–7835` is ACTIVE on this same branch. **The durable lesson: reserve HIGH, and treat the push-time guard as the only verification that is final — everything before it removes a stale read and nothing before it can remove a race.** | 2026-09-29 | **ACTIVE** |

**USED: `DEF-CUS-7900`. `7901`–`7909` are UNUSED and free for the next lane.**

**RELEASED WITHOUT EVER BEING USED: the `7860`–`7869` block this lane first held.** No row
of it reached the branch. It is recorded here rather than silently dropped, because a
released block tells the next reader why there is a gap — and this one tells them
something more useful than a gap.

---

## `DEF-CUS-7850–7859` · LANE SCREEN-A — New Request, steps 1 and 2 of the approved four (2026-09-29)

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-CUS-7850–7859` | **LANE SCREEN-A — `REQ-03` redesign, six steps into four. Tasks 5–7 of 12: the Applicant step, Documents moved onto it, and the Property step. Built from `05-prototype/new-request-four-steps-2026-09-29/*.png` (B14 rule 42). Branch `claude/brave-dijkstra-xgfsgz`, private worktree `agent-a9f552d76749ee958`.** Written here BEFORE the first row is filed, which is what `file_defect.py --block` refuses without. ⚠ **IT OPENS AT 7850, WELL ABOVE THE FRONTIER (`7836` when this lane started), RATHER THAN AT `max + 1`** — sibling lanes compute `max + 1` correctly and all get the same answer (`DEF-1787`). ⚠ **SCREEN-B holds steps 3 and 4 of the same file and COPY holds the eleven catalogues**, so every blob here is re-derived from the pinned tip at push time through `10-scripts/push_paths.sh`. | 2026-09-29 | **ACTIVE** |

**USED: `DEF-CUS-7850`, `DEF-CUS-7851`, `DEF-CUS-7852` and `OQ-CUS-7853`.
`7854`–`7859` are UNUSED and free for the next lane.** ⚠ **THE BLOCK IS BY
NUMBER, NOT BY PREFIX** — `7853` is an OPEN QUESTION and takes its number from
here rather than from the register frontier, which is what the block is for.

⚠ **THE VERSION MOVED TWICE AND BOTH MOVES WERE COLLISIONS, WHICH IS THE ROW
WORTH READING.** `allocate.py version --bump change` answered **`2.395.0`** when
this lane started. `push_paths.sh` then REFUSED the push because eight shared
files had moved under it, and the re-verification law 11 prescribes answered
*`2.395.0`: TAKEN — origin/claude/brave-dijkstra-xgfsgz carries it*. A sibling
had shipped it while this lane was building. Re-bumped to **`2.399.0`** — three
numbers higher, because `2.396`, `2.397` and `2.398` had gone the same way — and
re-verified against the tip in the same breath as the blob re-derivation. Every
lane's arithmetic was right; what was wrong was which world the maximum came
from.


---

## `DEF-CUS-7840–7849` · LANE REQ03-SCREEN-B — New Request steps 3 and 4 (2026-09-29)

| Block | Lane | Opened | State |
|---|---|---|---|
| `DEF-CUS-7840–7849` | **LANE REQ03-SCREEN-B — `REQ-03`, the New Request redesign approved by the PO on 2026-09-29, tasks 8–10 of 12: the Services table array, the Application-fees table array, and the Review with its new communication card. Branch `claude/brave-dijkstra-xgfsgz`, private worktree.** Written here BEFORE the first row is filed, which is what `file_defect.py --block` refuses without. ⚠ **IT OPENS AT 7840, ABOVE THE FRONTIER (`7836` when this lane started), RATHER THAN AT `max + 1`**, because sibling lanes compute `max + 1` correctly and all get the same answer (`DEF-1787`). Three live siblings share this branch and one shares this lane's file. | 2026-09-29 | **ACTIVE** |

**USED: `DEF-CUS-7840`. `7841`–`7849` are UNUSED and free for the next lane.**

⚠ **THE VERSION IS `2.395.0` AND THE RE-VERIFICATION COULD NOT BE RUN — SAID OUT
LOUD RATHER THAN LEFT AS A CLEAN-LOOKING SILENCE (law 7's fifth shape: a check
that cannot cover its subject must print what it skipped).** `allocate.py version
--bump change` answered `2.395.0` against a tip carrying `2.394.0` early in this
lane. At push time the container stood at a **load average of 115** with three
sibling lanes running, and `allocate.py version --bump change`, `allocate.py
defect --verify 7840` and a plain `git fetch origin` were each killed at their
timeout without answering; the agent proxy reported eight dropped connections to
`github.com` in the same window. **So the number is arithmetically right against
the world this checkout can see and has NOT been checked against the remote.**
The next lane to touch a version here runs the verify first: if `2.395.0` was
taken while this landed, that is the collision `DEF-GOV-3756` records, and it is
renumbered rather than argued with. The same caveat applies to `DEF-CUS-7840`,
allocated from a frontier of `7836` read before the network degraded.

⚠ **NO CR NUMBER IS TAKEN HERE.** `REQ-03`'s change request belongs to the lane that
captured the PO's nine rulings on 2026-09-29 — the drawings and their README landed in
`d16d29152` as *"the approved specification"* — and two lanes reaching for one CR
number is exactly what the per-branch block in `13-change-process.md` step 0 exists to
prevent. This lane builds tasks 8–10 of that change and cites it by name.

---

## Lane CUS-RED-VERDICT (2026-09-29) — attributing the 53 customers reds

**RESERVED: `DEF-CUS-7920`–`DEF-CUS-7923`.** `7924`–`7929` are UNUSED and free for
the next lane. Frontier read with `10-scripts/allocate.py defect` against the remote
at 10:48 (answered `7920` over 6,669 numbers across the working tree, five origin
refs, code, commit messages and the reservations file); re-verified with
`allocate.py defect --verify` at push time.

⚠ **NO CR NUMBER AND NO NEW STORY.** This lane attributes and repairs reds that
today's two wizard redesigns left behind; the change requests are `CR-150-BRC09`
(New Connect, eight steps → five) and `REQ-03` (New Request, six → four), both
already open and both cited by name rather than re-raised.

⚠ **THE `git log -S` DATING PRESCRIBED BY HARD-WON LAW 7 CANNOT REACH PAST
2026-09-24 IN THIS CHECKOUT, AND A LANE THAT DOES NOT KNOW THAT WILL MISDATE EVERY
PRE-EXISTING RED IT FINDS.** `.git/shallow` is present and the clone holds 543
commits, so `07-frontend/src/features/customers/` appears to have been ADDED whole
— 223 files, 144,925 insertions — by the graft commits `33501f667` and `a2ad9b6c8`.
`git log -S "<any string>" -- 07-frontend/src/features/customers/` therefore answers
`33501f667 2026-09-27 fix(reports): the census shows an account as it WAS` for
strings that have nothing to do with reports, and it answers it **confidently**.
That is law 7's fifth shape exactly — a check answering truthfully about everything
it can see, over a scope it silently excludes. **Date a pre-existing red by RUNNING
it at a named earlier commit in a `git worktree` instead**; this lane used
`5a79d33c0` (2026-09-28T23:57:44, the last commit before today) and the run is the
evidence.

---

## The One-time bill verification lane (`OTB-SIX-KINDS`) — 2026-09-29

| Block | Lane | Reserved | State |
|---|---|---|---|
| `DEF-BIL-7960–7979` | **LANE OTB-SIX-KINDS — the PO asked for every kind of one-time bill to be walked in a real browser: *"on step 1 - you provide 5 types of one time bill options you have to check all 5 cases"*. A VERIFICATION lane: it changes no product code, and every difference it finds is a row here rather than an edit. Branch `claude/brave-dijkstra-xgfsgz`, own isolated PostgreSQL clone `sbh_otb_walk`, own ports 8901/8902.** Written here BEFORE the first row is filed, which is what `file_defect.py --block` refuses without. ⚠ **IT OPENS AT 7960, WELL ABOVE THE FRONTIER (`7930` when this lane started), RATHER THAN AT `max + 1`** — the reason this file keeps repeating: sibling lanes compute `max + 1` correctly and all get the same answer (`DEF-1787`), and four other lanes are live on this same branch today. | 2026-09-29 | **ACTIVE** |

**USED: `DEF-BIL-7960`–`DEF-BIL-7972`** — thirteen rows from one browser walk of both
one-time screens across all six kinds. `7973`–`7979` are UNUSED and free for the next
lane. Frontier read with `10-scripts/allocate.py defect` against the remote before the
first row (answered `7930` over 6,679 numbers across the working tree, four origin refs,
code, commit messages and this file); re-verified with `allocate.py defect --verify` at
push time.

⚠ **NOTHING IN THE PRODUCT WAS EDITED BY THIS LANE.** The only code it wrote is its own
walk script, `10-scripts/def_bil_one_time_six_kinds_walkthrough.mjs`. Two findings it
CONFIRMED rather than filed — the unprorated base charge and the untaxed fee — are
declared absences the server already publishes in `ONE_TIME_UNAVAILABLE` with a PO
ruling behind each, so they are measurements and not new defects.

---

## The signed-schema gate lane (`WAVE-F-SCHEMA-GATE`) — 2026-09-29

| Block | Lane | Reserved | State |
|---|---|---|---|
| `DEF-RAT-7980–7989` · gate number `G137` | **LANE WAVE-F-SCHEMA-GATE — a gate that fails when a constraint the signed schema (B2) declares is not actually built by any migration, plus the review-ledger row for the one that was deferred in `rating/0004` and forgotten.** A CHECK lane: it writes no product code and builds no constraint. The unbuilt `tariff_versions` no-overlap constraint is a SIBLING lane's to build; this lane only makes its absence go red. Branch `claude/brave-dijkstra-xgfsgz`; introspection ran against read-only template `sbh_tpl_c561df3f` and a throwaway clone `sbh_clone_g137proof` it created for the green proof. | 2026-09-29 | **ACTIVE — USED: `DEF-RAT-7980` and the gate number `G137`.** `7981`–`7989` are UNUSED and free for the next lane; release this block when they are wanted. |

Frontier read with `10-scripts/allocate.py defect` and `allocate.py gate` against the
remote before anything was written (`7980` over 6,699 numbers; `137` for the gate), and
re-verified with `--verify` at push time. The block opens at `7980` rather than at the
bare frontier because `DEF-BIL-7960–7979` is held by lane `OTB-SIX-KINDS` on this same
branch and four other lanes are live on it today.

| `DEF-RAT-7991–7999` · gate number `G139` | **LANE WAVE-D-CLERK-REFUSALS — stop database ids reaching clerk screens from the rating engine's refusals, and add the guard that keeps them out.** Nine `raise` sites in `apps/rating/resolution.py` interpolated a plan, tariff or version uuid into the sentence a screen renders; the message TEXT changed and no resolution logic did. Files: `rating/resolution.py` 🔒, `billing/one_time.py`, `billing/gather.py`, `billing/runs.py`, `billing/resolution_switch.py`, `billing/resolution_shadow.py` 🔒, `billing/shadow_report.py`, four front-end render sites, the eleven catalogues, and the new gate. Branch `claude/brave-dijkstra-xgfsgz`. ⚠ **`G137` WAS TAKEN WHILE THIS LANE WORKED** — `allocate.py gate` answered `137` against a working tree that did not yet hold the sibling wave-F row, `run_gates._assert_registry_sane()` refused the duplicate NUMBER by name, and the gate landing LATER renumbered to `G139` (file, label, docstring and every citation), which is the 2026-09-04 precedent. `DEF-RAT-7980` was likewise re-derived to `DEF-RAT-7991` after `file_defect.py` read the remote: it is the sibling lane's row, and three files of this lane's prose cited it for twenty minutes. | 2026-09-29 | **ACTIVE — USED: `DEF-RAT-7991` and the gate number `G139`.** `7992`–`7999` are UNUSED and free for the next lane; release this block when they are wanted. |

---

## The press-Create verification lane (`NC-PRESS-CREATE`) — 2026-09-29

| Block | Lane | Reserved | State |
|---|---|---|---|
| `DEF-CUS-8020–8039` | **LANE NC-PRESS-CREATE — walk the New Connect wizard end to end, PRESS CREATE, and verify in the database that everything it promised was written.** A VERIFICATION lane: it writes no product code. Its only files are two walk scripts (`10-scripts/po20260929_new_connect_press_create.mjs`, `po20260929_new_connect_readback.py`) and this row. Everything it found is a defect row, including the two blockers. Branch `claude/brave-dijkstra-xgfsgz`; ran against an isolated clone `sbh_clone_ncverify` of template `sbh_tpl_c561df3f`, created and dropped by the lane. | 2026-09-29 | **ACTIVE — USED: `DEF-CUS-8020`–`8025`, `DEF-PAY-8026`, `DEF-CUS-8027`.** `8028`–`8039` are UNUSED and free for the next lane; release this block when they are wanted. |

Frontier read with `10-scripts/allocate.py defect` against the REMOTE before anything
was written (`8000` over 6,719 numbers across the working tree, four origin refs, code,
commit messages and this file), and re-verified with `allocate.py defect --verify` at
push time. `DEF-BIL-7960–7979`, `DEF-RAT-7980–7989` and `DEF-RAT-7991–7999` are all held
by sibling lanes on this same branch today, which is why this block opens high.

⚠ **THIS ROW FIRST RESERVED `8000–8019` AND THE FILER WOULD NOT USE IT.**
`file_defect.py` reads this file, sees a number inside an ACTIVE block, and **steps UP
to the first free id above the whole block** — including the lane's own block, which it
has no way to recognise as the caller's. It said so out loud
(*"DEF-8000 is inside 8000-8019, held by LANE NC-PRESS-CREATE … stepping UP"*) and
allocated `DEF-CUS-8020`. So **reserving a block and then filing into it moves you off
it**, and the row that records the reservation is wrong from the first `file_defect.py`
call unless it is written afterwards. The order that works is: run `allocate.py defect`
to read the frontier, file the rows, then record the block the ids actually landed in —
which is what this row now states. Recorded here rather than left as folklore, because
the next lane will reserve a block the same way and be told the same thing.

---

## The rate-schedule no-overlap lane (`RAT-NO-OVERLAP`) — 2026-09-29

| Block | Lane | Reserved | State |
|---|---|---|---|
| `DEF-RAT-8000–8009` | **LANE RAT-NO-OVERLAP — B2 §2 signs an `EXCLUDE USING gist` no-overlap constraint on `tariff_versions` that migration `0001` never materialised, because `btree_gist` was never installed. `rating/0004` reported the gap in its own header and left it "for the human review of this row"; that review never happened, and `services._apply_batch_to_schedule` has since carried a comment asserting the constraint exists (hard-won law 1). Ottumwa Water Works holds four versions of one sewer schedule in force on 2026-10-29 and its one-time and move-out final bills refuse with `AmbiguousSchedule`. Waves A (the guarantee), B (the write paths) and C (the two disagreeing readers). Branch `claude/brave-dijkstra-xgfsgz`.** ⚠ **IT OPENS AT `8000`, TWENTY ABOVE THE FRONTIER (`allocate.py defect` answered `7980` when this lane started, over 6,699 numbers across the working tree, four origin refs, code, commit messages and this file)** — the reason this file keeps repeating: sibling lanes compute `max + 1` correctly and all get the same answer (`DEF-1787`), and several lanes are live on this branch today. Re-verified with `allocate.py defect --verify` at push time. | 2026-09-29 | **ACTIVE** |


## The discount no-overlap lane (`RAT-DISC-OVERLAP`) — 2026-09-29

| Block | Lane | Reserved | State |
|---|---|---|---|
| `DEF-RAT-8050–8059` | **LANE RAT-DISC-OVERLAP — the same class of fault `DEF-RAT-8000` found on `tariff_versions`, closed on `discount_versions`.** Nothing in the database stopped two `active` versions of one discount being in force on one date; **no writer had ever closed a predecessor's window** (supersession here is a STATUS, so `effective_to` was left decorative); and the two readers of the table disagreed by construction — `discount_services.active_version` asked the window question and then `.first()`, while `resolution_catalogue._discount_facts` filtered `status='active'` with **no date predicate at all** and took the highest `version_no`. Files: `rating/discount_services.py` 🔒, `rating/resolution_catalogue.py` 🔒, `rating/migrations/0048` + `0049` 🔒, the eleven catalogues, `10-scripts/rat_schedule_overlap_census.py` (`--discounts`), `10-scripts/gates/g137_declared_constraints_are_built.py`, B2 addendum r26, `tests/test_def_rat_8050_discount_overlap_pg.py`. ⚠ **B2 SIGNED NOTHING FOR DISCOUNTS AT ALL** — zero occurrences of the word — so the constraint needed a B2 amendment and a review-ledger row, not a silent addition. Branch `claude/brave-dijkstra-xgfsgz`; PostgreSQL 16.13 proof on throwaway clones `sbh_clone_d8041` (RED) and `sbh_clone_d8041g` (GREEN, `rating/0045`–`0049` applied). | 2026-09-29 | **ACTIVE — USED: `DEF-RAT-8050` (the overlap), `DEF-RAT-8051` (the taxes sibling — FILED, NOT FIXED), `DEF-RAT-8052` (`G137` could not read an `ALTER TABLE … ADD CONSTRAINT` at all).** `8053`–`8059` are UNUSED and free for the next lane; release this block when they are wanted. |

⚠ **RESERVE THE BLOCK **AFTER** YOU FILE, NOT BEFORE — THIS LANE LEARNED IT THE
EXPENSIVE WAY AND IT IS NOT WRITTEN ANYWHERE ELSE.** `10-scripts/allocate.py
defect` answered `8041`, and this lane then wrote a reservation row for
`DEF-RAT-8041–8049` before filing. `10-scripts/file_defect.py` **reads this
file and steps OVER an active block** — *"DEF-8041 is inside 8041-8049, held by
LANE RAT-DISC-OVERLAP; stepping UP to the first free id above it"* — so it
allocated `8050`, and `8041` then became **permanently unreachable**, because
the allocator takes `max + 1` and not the first free id. Eight files and two
migration filenames had already been written and pushed citing `8041`; they
were renumbered to `8050` in one pass rather than left pointing at a number no
register row will ever carry (`DEF-2804`'s shape — a citation naming the wrong
real id, on a money path). **A reservation is a fence against OTHER lanes and
the allocator cannot tell you from them.** So: allocate and file first, then
write the block around the ids you actually hold.

## The dated-tax lane (`RAT-TAX-DATE`) — 2026-09-29

| Block | Lane | Reserved | State |
|---|---|---|---|
| `DEF-RAT-8060–8069` | **LANE RAT-TAX-DATE — `DEF-RAT-8051`, the taxes sibling of `DEF-RAT-8000`/`8050`, FIXED.** `selectors._authority_tax` took no date: it picked the oldest non-superseded row for a `(tenant, jurisdiction, kind)` by `created_at` and only afterwards asked `tax_in_force`, so a rate change filed as a new row produced NO tax line — $13.72 uncollected on a $196.00 January 2027 bill. The date is now in the choice, two rows in force on one date refuse by name, and the clerk's half reuses `DEF-RAT-7991`'s `message_key` mechanism. Files: `rating/selectors.py` 🔒, `rating/resolution.py` 🔒, `tests/test_def_rat_8051_tax_rate_change.py`, the eleven catalogues, the review ledger, the decision log, `CHANGELOG.md` and the three version files (`2.410.15`). Branch `claude/brave-dijkstra-xgfsgz`. ⚠ **THE IDS WERE ALLOCATED AND FILED BEFORE THIS BLOCK WAS WRITTEN, WHICH IS WHAT THE NOTE ABOVE SAYS TO DO** — `file_defect.py` answered *"DEF-8053 is inside 8050-8059, held by LANE RAT-DISC-OVERLAP; stepping UP"* and allocated `8060`, so the block is drawn around the two numbers this lane actually holds rather than around the ones it hoped for. | 2026-09-29 | **ACTIVE — USED: `DEF-RAT-8060` (nothing in billing catches the new refusal, so an ambiguous tax would fail the RUN rather than the ACCOUNT — unreachable on all current data, 0 overlapping pairs measured) and `DEF-RAT-8061` (`services._detach_tax` looks up tax kind `"flat"`, which is not a tax kind, so `BR-RAT-115`'s last-tax floor cannot see a flat fee — found in passing, not fixed).** `8062`–`8069` are UNUSED and free for the next lane; release this block when they are wanted. |
| `BR-BIL-1049` | **One-time bill redesign R2 — the rule for "two meters on one metered service are two lines" (PO rulings 2026-09-30).** **Taken BY HAND** — `allocate.py` has no BR family (the `BR-PAY-1196` precedent). `BR-BIL-1048` was the maximum `BR-BIL` id in `04-docs`, `12-governance` and `06-backend` on the branch tip, and `1049` lies in the `BR-<MOD>-1041–1049` tail that the `CR-056` W6 row records as *"UNUSED and free"*. No other id was needed: every other 2026-09-30 ruling amends an existing rule (`BR-BIL-300`, `BR-BIL-301`, `BR-BIL-1048`, `BR-RAT-1015`, `BR-RAT-088`, `BR-RAT-1025`, `BR-RAT-090`). | 2026-09-30 | **USED: `BR-BIL-1049`.** Nothing reserved or held open. |
| `BR-BIL-1051–1055` | **Bulk bill run redesign R2 — five new billing rules from the PO's 2026-09-30 review** (continuity · Check never stops at the first problem · payment checks · not in this run / left out by clerk · price at period end). **Taken BY HAND** — `allocate.py` has no BR family (the `BR-BIL-1049` precedent above). `BR-BIL-1049` was the maximum `BR-BIL` id on `origin/claude/upbeat-dirac-olttw0` at 7df0c3957, and a `git grep 'BR-BIL-10[5-9][0-9]'` over all 59 remote refs found **none**; the coordinator then gave `BR-BIL-1050` to the bulk Scope lane (the Scope refusal and warning list), so this lane starts at 1051. Every other ruling of the review amends an existing rule (`BR-BIL-005`, `1040`, `1041`, `070`, `1025`, `034`, `BR-RAT-007`). | 2026-09-30 | **USED: `BR-BIL-1051`–`BR-BIL-1055`.** Nothing held open. |
| `DEF-BIL-8200–8299` | **Bulk bill run redesign R1 — the review-gap defects.** Block given to this lane by the coordinator on 2026-09-30 after unpushed lanes collided on the allocator's max + 1 (`8106`–`8109` taken by the reads-upload lane, `8150`–`8152` pushed, `8160`–`8179` held for the bulk Scope lane). The rows were first appended as `8106`–`8121` and renumbered byte-for-byte to this block before any commit; each id checked with `allocate.py defect --verify` (all free on every branch). | 2026-09-30 | **USED: `DEF-BIL-8200`–`DEF-BIL-8215`** (16; `8215` closed fixed at 7df0c3957 — the drawing's dead links). `8216`–`8299` free to this block's owner. |
| `DEF-*-8150–8399` | **2026-09-30 coordinator, seven parallel lanes filing at once.** 8106–8108 were taken twice (reads-upload `DEF-MET-8106..8109`, bulk Scope `DEF-BIL-8106`, one-time T2/T6 `DEF-BIL-8106..8108`) because none had pushed. Blocks given by the coordinator: `8150–8152` one-time T2/T6 (pushed, renumbered from 8106–8108) · `8160–8179` bulk Scope lane · `8200–8299` bulk records R1 · `8300–8339` one-time E1–E11 · `8340–8359` fee-tax lane · `8360–8399` asset-upload browser walk. `8106–8109` stay with reads-upload. | 2026-09-30 | ACTIVE |
| `DEF-AST-8363–8369` | **2026-09-30 coordinator — the asset-upload walk follow-up lane** (unit Assets tab fetching only the premises' first 200 assets, `DEF-MET-8362`; result-file headers as field names; devices sample pairing backflow with Electric). PO: *"fix it if there is a bug"*. | 2026-09-30 | ACTIVE |
| `DEF-BIL-8153–8159` | **2026-09-30 coordinator — the bill-line layout lane** fixing `DEF-BIL-8150` (minimum top-up line with no meter), `8151` (counted service as two lines, not one per service) and `8152` (comments naming the deleted `OneTimeBillTab`). PO: *"can you ahndle these bugs"*. | 2026-09-30 | ACTIVE |
| `DEF-BIL-8216–8239` · `DEF-BIL-8240–8279` · `BR-BIL-1056+` | **2026-09-30 coordinator — bulk bill run screens lane (8216–8239) and check-engine lane (8240–8279; new BR ids from 1056 after checking the tip).** | 2026-09-30 | ACTIVE |
| `DEF-BIL-8280–8289` | **2026-09-30 coordinator — findings the coordinator files itself** (first: a Check-decision estimate is not recorded as a billed position, so the next actual may bill the estimated usage again). | 2026-09-30 | ACTIVE |
| `DEF-BIL-8240–8279` | **check-engine lane (bulk bill run B7–B21) — the coordinator's second block on the row above, on its own row so `file_defect.py` can read it** (its block regex reads the FIRST range in a cell only, so a row naming two blocks reserves one of them to the tool). | 2026-09-30 | ACTIVE |
| `DEF-BIL-8317–8339` | **2026-09-30 coordinator — the one-time bill defect-fix lane** fixing the J70 walk rows `DEF-BIL-8300`, `8305`, `8310`, `8312`, `8313`, `8315`, `8316` and filing the walk's three unfiled mismatches (invalid fields not tinted, account card 3 columns not 4, already-billed banner placement) inside this block. The rest of `8300–8339` stays with the walk lane that filed it. | 2026-09-30 | ACTIVE |
| `DEF-BIL-8410–8449` | **2026-09-30 coordinator — the remaining bulk bill run lane** (B14 inline fixes, B18 leave out, B19 sign-off summary, B20 not-in-run / catch-up / next cycle, the DEF-BIL-8286 split, screen wiring, A8–A10, DB3). Moved here because `DEF-BIL-8340` was already used by the fee lane, so 8340–8359 was not free. Checked unused on every origin ref before reserving. | 2026-09-30 | **ACTIVE** |
| `DEF-8450–8469` (any `<MOD>` segment; the `*` spelling was unreadable to `file_defect.py`'s block parser, and the row had no state cell, so the tool refused the block — respelled and given its date and state by the lane itself, 2026-09-30) | **2026-09-30 coordinator — the dated-reds lane**: 24 long-standing failures in `test_oq1164_every_customer_document_freezes.py` (21), `test_def_4448_every_letter_carries_its_figures.py`, `test_us_bil_022_documents.py` tc11 and `test_w3_billing_run_decisions.py` tc5 — date each with `git log -S`, fix stale pins, file real regressions before fixing. Checked unused on every origin ref. | 2026-09-30 | ACTIVE |
| `DEF-8470–8489` (any `<MOD>` segment) | **2026-09-30 coordinator — the bulk-run walk-prep lane**: the J72 PostgreSQL seed and Playwright journey specs for the bulk run walks E1–E11, proving tags for changes rows 1–8, and `DEF-BIL-8285` (1408 Elm meters with no connection size). Checked unused on every origin ref. | 2026-09-30 | **ACTIVE** |
| `DEF-8510–8529` (any `<MOD>` segment) | **2026-09-30 coordinator — bulk-run breakdown and scale walk prep (clerk checks F1–F5, S1–S4)**. Checked unused on every origin ref. | 2026-09-30 | **ACTIVE** |
| `DEF-8530–8549` (any `<MOD>` segment) | **2026-09-30 coordinator — gate suite triage (plan T6)**. Checked unused on every origin ref. | 2026-09-30 | **ACTIVE** |
| `DEF-8550–8559` (any `<MOD>` segment) | **2026-09-30 coordinator — bulk-run accuracy walk (clerk checks A1–A6)**. Checked unused on every origin ref. | 2026-09-30 | **ACTIVE** |
| `DEF-8560–8579` (any `<MOD>` segment) | **2026-09-30 coordinator — the one-time bill end-to-end lane (J74)**: eight clerk cases billed and sent in a browser, each verified in the database. Checked unused on every origin ref. | 2026-09-30 | **ACTIVE** |
| `DEF-8580–8599` (any `<MOD>` segment) | **2026-09-30 coordinator — the final bulk-run lane (failing clerk checks, breakdown fixes and walks)**. Checked unused on every origin ref. | 2026-09-30 | **ACTIVE** |
| `DEF-8600–8619` (any `<MOD>` segment) | **2026-09-30 coordinator — B27 batch data loading with DEF-BIL-8490/8491**. Checked unused on every origin ref. | 2026-09-30 | **ACTIVE** |
| `DEF-8620–8629` (any `<MOD>` segment) | **2026-09-30 coordinator — G7 review markers on 23 migrations**. Checked unused on every origin ref. | 2026-09-30 | **ACTIVE** |
| `DEF-8630–8639` (any `<MOD>` segment) | **2026-09-30 coordinator — the Scope-bug verifier (DEF-BIL-8201-8204, 8212, 8213, 8221, 8222)**. Checked unused on every origin ref. | 2026-09-30 | **ACTIVE** |
| `DEF-8640–8649` (any `<MOD>` segment) | **2026-09-30 coordinator — meter swap, re-check on a new price version, default plan (DEF-BIL-8244-8246)**. Checked unused on every origin ref. | 2026-09-30 | **ACTIVE** |
| `DEF-8650–8669` (any `<MOD>` segment) | **2026-09-30 coordinator — the bulk-run database audit and single-account trace (E16, E17)**. Checked unused on every origin ref. | 2026-09-30 | **ACTIVE** |
| `DEF-BIL-8490–8499` | **2026-09-30 coordinator — the B27 step 1 measurement lane** (`10-scripts/bbr_check_cost.py`, `04-docs/05-modules/07-billing/19-check-cost-measured.md`): what the bulk Check costs per account on PostgreSQL 16 and which reads repeat per account. Measurement only, no product code. Checked unused on the origin tip before reserving. | 2026-09-30 | **ACTIVE** |
| `DEF-8500–8509` (any `<MOD>` segment) | **2026-09-30 coordinator — the payment-checks lane** (`DEF-BIL-8240` unmatched payment and bounced payment not reversed, `DEF-BIL-8241` level pay off track; changes row 38). Taken because `DEF-BIL-8490–8499` is the B27 step 1 measurement lane's. Checked unused on every origin ref and in commit messages before reserving. | 2026-09-30 | **ACTIVE** |
| `BR-BIL-1061–1065` · `BR-RAT-1046–1047` | **2026-10-01 six-rulings build lane** — one business rule per ruling of *"SIX PO RULINGS IN ONE MESSAGE"* (payment-plan bill, meter swap per meter, no plan on the unit, final bill with no cycle, whole-account balance forward; the cart prorate and no default plan in rating). Taken above `BR-BIL-1056+` (the check-engine lane's block) after checking the tip. | 2026-10-01 | ACTIVE |
| `BR-BIL-1066` | **2026-10-01 interim-base lane** — the interim bill cuts its base down by days over the account's own cycle (`OQ-242` option (a) for interim, decision log *"TWO PO RULINGS ON THE BASE CHARGE"*). Taken above the six-rulings block after checking every origin ref. | 2026-10-01 | ACTIVE |
| `CR-156-BRC10` · suffix `BRC10` for branch `claude/upbeat-dirac-olttw0` · `BR-RAT-1048–1052` | **2026-10-01 charge-code redesign, wave A** (database, saving, one-row lookup). `allocate.py cr` answered 156; no CR on this branch had carried a suffix, so `BRC10` (the next unused after `BRC09`) is claimed here for this branch. `BR-RAT-1048–1052` taken BY HAND (no BR family in `allocate.py`) after a grep of all 60 origin refs found `BR-RAT-1047` the maximum and none of `1048–1059`. | 2026-10-01 | **ACTIVE** |
| `CR-157-BRC10` | **2026-10-01 rate-schedule redesign, wave A** (row locks on every schedule save path, the named overlap refusal under concurrency, billing reads one record, the direct-version-query gate). `allocate.py cr` answered 157 against the remote; suffix `BRC10` is this branch's, claimed by the `CR-156-BRC10` row above. | 2026-10-01 | **ACTIVE** |
| `CR-158-BRC10` | **2026-10-01 portal document upload for the new-service request** (decision log *"CUSTOMERS MAY NOW UPLOAD DOCUMENTS FROM THE PORTAL — `DF-4` … IS SUPERSEDED FOR THE NEW-SERVICE REQUEST"*). `allocate.py cr` answered 158 against the remote and `--verify 158` reported it free on every branch; suffix `BRC10` is this branch's, claimed by the `CR-156-BRC10` row above. | 2026-10-01 | **ACTIVE** |
| `CR-159-BRC10` · `BR-CUS-1111–1113` · `BR-MET-1188` | **2026-10-01 a portal move-in / new-connection request carried to an ACTIVE customer** (decision log 2026-10-01, the same row as `CR-158-BRC10`, items (3)–(5)). `allocate.py cr` answered 159 against the remote and `--verify 159` reported it free on every branch; suffix `BRC10` is this branch's, claimed by the `CR-156-BRC10` row above. `BR-CUS-1111–1113` and `BR-MET-1188` taken BY HAND (no BR family in `allocate.py`) after a grep of all 60 origin refs found `BR-CUS-1110` and `BR-MET-1187` the maxima. | 2026-10-01 | **ACTIVE** |
| `CR-160-BRC10` | **2026-10-02 storage key by utility web name and module; no object lock for now** (decision log 2026-10-02, commit `4e44763e6`). The number is the one the PO's ruling row already carries; `allocate.py cr --verify 160` answers TAKEN only because of that row and its commit subject — no sibling CR holds 160 (`git grep CR-160` and `git log --grep CR-160` on the remote, 2026-10-02). Suffix `BRC10` is this branch's (`claude/upbeat-dirac-olttw0`). |
| `CR-161-BRC10` | **2026-10-02 tenant custom fields as a complete platform capability** (decision log 2026-10-02, commit `aa4d30f8b`, R1–R6). `allocate.py cr` answered 161 against the remote and `--verify 161` reported it free on every branch; suffix `BRC10` is this branch's (`claude/upbeat-dirac-olttw0`), claimed by the `CR-156-BRC10` row above. Waves W2–W7 run under this one number in other lanes. | 2026-10-02 | **ACTIVE** |
| `CR-162-BRC10` | **2026-10-02 New Connection lifecycle — what Create makes and how a request is approved and activated** (decision log 2026-10-02, commit `56eb54ba9`, Q1–Q3 and items 1, 2, 5–9, 27, 34–36, 38, 48). `allocate.py cr` answered 162 against the remote and `--verify 162` reported it free on every branch; suffix `BRC10` is this branch's, claimed by the `CR-156-BRC10` row above. | 2026-10-02 | **ACTIVE** |
| `CR-163-BRC10` | **2026-10-02 New Connection details view — Add fees after submission, Send a message now, and the Work/Charges/Documents/Messages tab fixes** (decision log 2026-10-02, commit `56eb54ba9`, Table 2 items 1, 2, 14, 15, 18–27; lane NC-B). `allocate.py cr` answered 163 against the remote; `--verify 163` answers TAKEN only because this lane's own defect commit `735cbd25b` names it — no sibling CR holds 163 (`git log --all --grep CR-163`). Suffix `BRC10` is this branch's, claimed by the `CR-156-BRC10` row above. | 2026-10-02 | **ACTIVE** |
| `CR-164-BRC10` | **2026-10-02 New Connection wizard steps 1–5 — the PO's screen-by-screen changes** (decision log 2026-10-02, commit `56eb54ba9`, items 10–31, 46, 47, 49, C, D; lane NC-C). `allocate.py cr` answered 164 against the remote. Suffix `BRC10` is this branch's, claimed by the `CR-156-BRC10` row above. | 2026-10-02 | **ACTIVE** |
| `CR-165-BRC10` | **2026-10-03 Taxes & fees redesign — list, New tax wizard, details and edit** (decision log 2026-10-03, *"GO ON THE TAXES & FEES REDESIGN"*, commit `375f1e499`). `allocate.py cr` answered 165 against the remote and `--verify 165` reported it free on every branch, at allocation and again at tip `ac38c3cca`. Suffix `BRC10` is this branch's (`claude/upbeat-dirac-olttw0`), claimed by the `CR-156-BRC10` row above. | 2026-10-03 | **ACTIVE** |
| `CR-166-BRC10` | **2026-10-03 Discounts redesign — list, New discount form, details with an Accounts tab, edit, and the four lifecycle rulings** (decision log 2026-10-03, *"GO ON THE DISCOUNTS REDESIGN"*, commit `aeea9050e`). `allocate.py cr` answered 166 against the remote and `--verify 166` reported it free on every branch, at allocation and again at push time. Suffix `BRC10` is this branch's (`claude/upbeat-dirac-olttw0`), claimed by the `CR-156-BRC10` row above. | 2026-10-03 | **ACTIVE** |
| `CR-167-BRC10` | **2026-10-03 Plans redesign — list, New plan form (Details · Services · Charges · Billing · Review), details (Overview · Services · Charges · Billing · Units · Audit) and Edit with three choices, built from 44 desktop images** (decision log 2026-10-03, *"GO ON THE PLANS REDESIGN"*, commit `ed47eaddc`). The number is the one the PO's GO row already carries; `allocate.py cr --verify 167` answers TAKEN only because of that row and its commit subject — no sibling CR holds 167 (`git log --grep CR-167` on every origin ref finds only `ed47eaddc`; `git grep CR-167` on every origin ref finds only this branch's decision log, 2026-10-03). Suffix `BRC10` is this branch's (`claude/upbeat-dirac-olttw0`), claimed by the `CR-156-BRC10` row above. | 2026-10-03 | **ACTIVE** |
| `CR-168-BRC10` | **2026-10-04 Work back office redrawn — 65 drawing images and the 36 PO rulings of 23–24 Sep recorded; drawing received, not a go** (decision log 2026-10-04, *"WORK BACK OFFICE — 36 PO RULINGS OF 23–24 SEP RECORDED, 65 DRAWING IMAGES ADDED; NOT A GO TO BUILD"*). `allocate.py cr --verify 168` reported it still free on every branch at allocation (2026-10-04, tip `afab7d192`). At push time it answers TAKEN only because this lane's own image commit `b699a78ca` names it — `git log --remotes --grep CR-168` finds only that commit, and `git grep CR-168` over every origin ref finds nothing in `12-governance/` (the same shape as `CR-167-BRC10` above). Suffix `BRC10` is this branch's (`claude/upbeat-dirac-olttw0`), claimed by the `CR-156-BRC10` row above. | 2026-10-04 | **ACTIVE** |
| `CR-169-BRC10` | **2026-10-04 PostHog user-activity tracking, one project per environment** (decision log 2026-10-04, *"POSTHOG USER-ACTIVITY TRACKING"*). `allocate.py cr` answered 169 against the remote and `--verify 169` reported it free on every branch; suffix `BRC10` is this branch's, claimed by the `CR-156-BRC10` row above. | 2026-10-04 | **ACTIVE** |
| `CR-170-BRC10` | **2026-10-05 Forgot password — its own page with no contact, and back to sign-in after a forced change** (decision log 2026-10-05, the three rows that start *"FORGOT PASSWORD"*). `allocate.py cr` answered 170 against the remote and `--verify 170` reported it free on every branch; suffix `BRC10` is this branch's (`claude/upbeat-dirac-olttw0`), claimed by the `CR-156-BRC10` row above. | 2026-10-05 | **ACTIVE** |
| `CR-172-BRC10` | **2026-10-05 the utility logo moves into the S3 document store and is drawn everywhere** (decision log 2026-10-05, *"THE UTILITY LOGO MOVES FROM A DATABASE COLUMN TO THE S3 DOCUMENT STORE"* and *"THE LOGO-TO-S3 PLAN IS APPROVED AS WRITTEN"*). `allocate.py cr` answered 172 against the remote and `--verify 172` reported it free on every branch; suffix `BRC10` is this branch's, claimed by the `CR-156-BRC10` row above. | 2026-10-05 | **ACTIVE** |
| `CR-171-BRC10` · `OQ-BIL-12788` · `DEF-CUS-9702`, `DEF-CUS-9703` | **2026-10-05 Move-in redesign — list, details view for eight statuses, four-step wizard, completed screen, from 48 images** (decision log 2026-10-05, the rows that start *"MOVE-IN REDESIGN"*). `allocate.py cr` answered **170**; a sibling pushed `CR-170-BRC10` (forgot password) before this lane wrote anything, so it was re-asked and answered **171**; `--verify 171` answers TAKEN only because this lane's own commit `1a72779ab` names it (`git log --all --grep CR-171` finds nothing else). `OQ-BIL-12788` from `allocate.py oq`, `--verify` free on every branch. Suffix `BRC10` is this branch's, claimed by the `CR-156-BRC10` row above. | 2026-10-05 | **ACTIVE** |
| `CR-173-BRC10` | **2026-10-07 New World / Logos receipt file pushed to the City's SFTP folder by a runbook** (decision log 2026-10-07, the three rows that start *"NEW WORLD / LOGOS RECEIPT FILE"*, *"THE NEW WORLD SFTP SETTINGS"* and *"PO APPROVED — THE SEND TO CITY FOLDER SECTION"*). `allocate.py cr` answered 173 against the remote and `--verify 173` reported it free on every branch. Suffix `BRC10` is this branch's (`claude/charming-pascal-k7i2lr`, which carries `CR-171-BRC10`). | 2026-10-07 | **ACTIVE** |
| `CR-174-BRC10` | **2026-10-07 US Payments (Prime) — the three inbound calls on the USPayments card, posting on arrival** (decision log 2026-10-07, the row that starts *"PO RULINGS — US PAYMENTS (PRIME)"*). `allocate.py cr` answered 174 against the remote and `--verify 174` reported it free on every branch; suffix `BRC10` is this branch's (`claude/charming-pascal-k7i2lr`). | 2026-10-07 | **ACTIVE** |
| `CR-175-BRC10` · `DEF-PAY-10010`, `DEF-PAY-10011` | **2026-10-07 a billing clerk may mark an ACH payment returned, any day, with a reason and the bank code** (decision log 2026-10-07, the row that starts *"PO RULING — A BILLING CLERK MAY MARK AN ACH PAYMENT RETURNED"*). `allocate.py cr` answered 175 against the remote and `--verify 175` reported it free on every branch; suffix `BRC10` is this branch's (`claude/charming-pascal-k7i2lr`). | 2026-10-07 | **ACTIVE** |
| `CR-176-BRC10` · `BR-MET-1196`–`1201` | **2026-10-09 Add units redesign — building picked by search and *Use this building*, next-free numbering, one count, services from the building, common area as a choice at the top, *These units* card, grouped Review; and the Units list's selection bar only once a unit is ticked** (decision log 2026-10-09, the row that starts *"PO GO — BUILD THE ADD-UNITS REDESIGN"*; `DEF-MET-10035`). `allocate.py cr` answered 176 against the remote at tip `42970b1b4` and `--verify 176` reported it free on every branch. `BR-MET-1196`–`1201` taken BY HAND (no BR family in `allocate.py`) after a grep of all 61 origin refs found `BR-MET-1195` the maximum, held by `CR-177-BRC10`'s block `1190`–`1195`. Suffix `BRC10` is this branch's (`claude/charming-pascal-k7i2lr`). | 2026-10-09 | **ACTIVE** |
| `CR-177-BRC10` · `BR-MET-1190`–`1195` | **2026-10-09 Add a premise redesign** (decision log 2026-10-09, the rows that start *"PO GO — BUILD THE ADD-A-PREMISE REDESIGN"* and *"PO RULINGS — ADD-A-PREMISE REDESIGN, CONTINUED"*). `allocate.py cr` answered 176, which the Add units lane pushed first; re-asked it answered 177 and `--verify 177` reported it free on every branch. `BR-MET-1190`–`1195` taken BY HAND (no BR family in `allocate.py`) after a scan of all 61 origin refs and the worktree found `BR-MET-1189` the maximum. Suffix `BRC10` is this branch's (`claude/charming-pascal-k7i2lr`). | 2026-10-09 | **ACTIVE** |
| `CR-179-BRC10` | **2026-10-12 Rate Impact report** — proposed rates against billed revenue, by rate schedule or charge code, capacity and class, inside the reporting framework. `allocate.py cr` answered 179 against the remote (178 was this branch's own capture commit, reverted); suffix `BRC10`. | 2026-10-12 | **ACTIVE** |
| `CR-181-BRC10` | **Returning customer: recognise, show balance, reopen on the same unit.** `allocate.py cr` answered 181 against the remote and `--verify 181` reported it free; suffix `BRC10` is this branch's. | 2026-10-13 | **ACTIVE** |
| `BR-CUS-1119` · `DEF-CUS-10125`–`10127` | **CR-181-BRC10 lane REOPEN** — the returning-customer rule (one BR for the four rulings, module sequence: `BR-CUS-1118` was the maximum on all 62 remote refs and `1119` appeared on none) and three defects found while building (`file_defect.py`, remote-checked). | 2026-10-13 | **ACTIVE** |
| `CR-183-BRC10` · `BR-CUS-1120`–`1121` | **Temporary stop** (decision log 2026-10-14 *"TEMPORARY STOP — FOUR PO RULINGS (B1–B4)"*). `allocate.py cr` answered 183 against the remote and `--verify 183` reported it free on every branch; `BR-CUS-1120`–`1121` taken BY HAND (no BR family in `allocate.py`) after a grep of the remote tip found `BR-CUS-1119` the maximum. Suffix `BRC10`. | 2026-10-14 | **ACTIVE** |
| `CR-182-BRC10` | **High consumption alert on a flagged reading (portal message, email, bill note, reading tag).** `allocate.py cr` answered 182 against the remote and `--verify 182` reported it free on every branch; suffix `BRC10` is this branch's. | 2026-10-14 | **ACTIVE** |
| `CR-184-BRC10` | **2026-10-14 Receivables by service** — dataset, library report and the ageing Service filter (decision log 2026-10-14, *"RECEIVABLES BY SERVICE: WHAT IS STILL OWED IS SHARED IN PROPORTION"*). `allocate.py cr` answered 184 against the remote and `--verify 184` reported it free on every branch; suffix `BRC10` is this branch's. | 2026-10-14 | **ACTIVE** |
| `BR-PAY-1200` | **CR-184-BRC10 lane ARSVC** — receivables reported per service by sharing, inside the class order. Taken BY HAND (no BR family in `allocate.py`): `BR-PAY-1199` was the maximum on the branch tip and `1200` appeared on none of the 62 remote refs. | 2026-10-14 | **ACTIVE** |
| `CR-185-BRC10` | **2026-10-14 balance-to-owner posting and the Owner summary report** (decision log *"LANDLORD D2–D5"*). `allocate.py cr` answered 185 against the remote and `--verify 185` reported it free on every branch; suffix `BRC10` is this branch's. | 2026-10-14 | **ACTIVE** |
| DEF-BIL-10200–10209 | **Lane LATEFEE (2026-10-17)** — the late fee applied by the bill run, the flat late fee, and anything its walk finds (decision log 2026-10-17 *"THE LATE FEE IS APPLIED BY THE BILL RUN"*). Taken as a block because `DEF-*-10165`–`10199` are held by sibling lanes not yet pushed, which `file_defect.py` cannot see; filed into with `--block 10200-10209`. | 2026-10-17 | **ACTIVE** |
| DEF-CUS-10230–10249 | **Lane CF-1 (2026-10-18)** — the shared customer form on Move-in, the staff service request and New connect (decision log 2026-10-18 *"CUSTOMER DATA AND UI CONSISTENT ACROSS THE CREATE SCREENS"*). Handed to the lane in its dispatch so it cannot collide with lane CF-2, which works the same day in its own worktree; filed into with `--block 10230-10249`. | 2026-10-18 | **ACTIVE** |
| DEF-CUS-10250–10269 | **Lane CF-2 (2026-10-18)** — customer forms tasks 15–19 (portal apply, approve with category, transfer buyer, edit dialogs, request → move-in carry-forward) and anything its walk finds (decision log 2026-10-18 *"CUSTOMER DATA AND UI CONSISTENT ACROSS THE CREATE SCREENS"*). Given to this lane by the coordinator, so siblings building CF-1 in parallel cannot take the same numbers; filed into with `--block 10250-10269`. | 2026-10-18 | **ACTIVE** |
| `CR-186-BRC10` | **Every payment POSTED at entry, CLEARED at bank reconciliation; one deposit batch per till or provider per day; Invoice Cloud real-time balance** (decision log 2026-10-21, seven entries). `allocate.py cr` answered 186 against the remote and `--verify 186` reported it free on every branch; suffix `BRC10` is this branch's. Defect blocks: lane PAY-CORE `10320`–`10339`, lane BAL-IC `10340`–`10359`. | 2026-10-21 | **ACTIVE** |
| `CR-187-BRC10` | **Native field app (React Native) in `field-app/`; supersedes BR-WRK-045** (decision log 2026-10-21, five entries). `allocate.py cr` answered 187 against the remote; suffix `BRC10` is this branch's. Module code **FLD** (`BR-FLD-`, `OQ-FLD-`, `DEF-FLD-`, `EP-FLD-`, `US-FLD-`) first used here. | 2026-10-21 | **ACTIVE** |
| `OQ-FLD-12794`–`OQ-FLD-12800` | **Lane DOC-C (2026-10-21) — the field app's open questions, design task T-64** (`CR-187-BRC10`; decision log 2026-10-21 *"Where the field-app design lives in the repo"*). `allocate.py oq` answered **12794**; seven taken as a block and each `--verify`'d free on every branch before commit. **USED, all seven:** 12794 speed on the technician's screen · 12795 MDM · 12796 handset retention · 12797 certificate pins · 12798 two-credential sign-in · 12799 bottom bar vs R102 · 12800 the Work blueprint's unread §15–§21. **Not minted, because already ruled the same day** (decision log *"Field app: crash reporter, technician identity in analytics, and the web field app's future"*): the crash reporter (Crashlytics), naming a technician in analytics (yes), and T-72 (deferred until the native app is built). Not duplicated: `OQ-272` (b) and `OQ-1360`. | 2026-10-21 | **ACTIVE** |
| `CR-188-BRC10` | **Staff invitation and reset emails carry a one-time sign-in link; Account access template category; public address setting; Resend invitation** (decision log 2026-10-22). `allocate.py cr` answered 188 against the remote; suffix `BRC10` is this branch's. Defect block for the lane: `10360`–`10379`. | 2026-10-22 | **ACTIVE** |
| `CR-189-BRC10` | **Customer portal self-service "update your registered email" when locked out** (decision log 2026-10-22). `allocate.py cr` answered 189 against the remote; suffix `BRC10` is this branch's. | 2026-10-22 | **ACTIVE** |
| `CR-190-BRC10` | **Every email sent with its real subject and formatted body; move-in welcome details; service agreement by email with click-to-accept** (decision log 2026-10-22). `allocate.py cr` answered 190 against the remote; suffix `BRC10`. Defect blocks: EMAIL-CORE `10420`–`10439`, MOVEIN-MSG `10440`–`10459`, AGREEMENT `10460`–`10479`. | 2026-10-22 | **ACTIVE** |
| `CR-191-BRC10` | **Portal application fee paid online at submission** (decision log 2026-10-23). `allocate.py cr` answered 191 against the remote and `--verify 191` reported it free on every branch; suffix `BRC10`. | 2026-10-23 | **ACTIVE** |
| `CR-192-BRC10` · `BR-MET-1210`–`BR-MET-1218` | **MQ-033 utility-defined meter-read formats, task 10 (server)** (decision log 2026-10-24, the three "MQ-033" rows). `allocate.py cr` answered 192 against the remote (2026-10-24, tip `baf29dbca`); suffix `BRC10`. `BR-MET-1210`–`1218` taken BY HAND (no BR family in `allocate.py`) after a grep of the branch found `BR-MET-1202` the maximum; `1203`–`1209` deliberately LEFT for the concurrent MQ-033 task-9 lane (route assignment) so the two lanes cannot take the same number. ⚠ Task 9 may also have asked `allocate.py cr` and been answered 192 — the coordinator verifies at merge (`allocate.py cr --verify 192`). | 2026-10-24 | **ACTIVE** |
| `CR-193-BRC10` · `BR-WRK-068`–`BR-WRK-070` | **MQ-040 step 1 — working days, the phone's week, End shift, Submit the day** (decision log 2026-10-26). `allocate.py cr` answered 193 against the remote and `--verify 193` reported it free on every branch (2026-10-26, tip `73be6c160`); suffix `BRC10`. `BR-WRK-068`–`070` taken BY HAND (no BR family in `allocate.py`) after a grep of the branch found `BR-WRK-067` the maximum. | 2026-10-26 | **ACTIVE** |
| `CR-194-BRC10` · `BR-WRK-071` | **Refused field work kept on both phone and server** (decision log 2026-10-26, *"store on both"*). `allocate.py cr` answered 194 against the remote; `--verify 194` re-run at push time. Suffix `BRC10`. `BR-WRK-071` taken BY HAND (no BR family in `allocate.py`) after a grep of the tip found `BR-WRK-070` the maximum. | 2026-10-26 | **ACTIVE** |
| `CR-195-BRC10` | **Field-app certificate pinning dormant (A1)** (decision log 2026-10-28, *"start A1"*). `allocate.py cr` answered 195 against the remote and `--verify 195` reported it free on every branch before the first push; after it, `--verify` answers TAKEN only because this lane's own commits (`c69e7107c`, `c91812023`, `5aa856d2c`) and files name it — `git log --remotes --grep CR-195` lists those and nothing else. Suffix `BRC10`. | 2026-10-28 | **ACTIVE** |
| `CR-196-BRC10` | **Chart account code editable by System Admin (with seed_key guards)** (decision log 2026-10-29). `allocate.py cr` answered 196 against the remote and `--verify 196` reported it free on every branch; suffix `BRC10`. Defect `DEF-LED-10647` allocated by `file_defect.py`. | 2026-10-29 | **DONE** |
| `CR-197-BRC10` | **GL mapping one list** (decision log 2026-10-29). `allocate.py cr` answered 197 against the remote; suffix `BRC10`. **`BR-LED-800`, `801`, `802` and `803` are USED** by this CR (re-read numerically from the tip: the highest used was `BR-LED-799`; `BR-LED-1000` appears only inside a warning sentence). **`BR-LED-804` and up are UNUSED and free.** | 2026-10-29 | **ACTIVE** |
