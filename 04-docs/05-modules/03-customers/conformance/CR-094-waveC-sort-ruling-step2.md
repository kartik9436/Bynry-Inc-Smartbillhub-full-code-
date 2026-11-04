# CR-094-BRC01 · step 2 wave C — `BR-CUS-1046` on all eight lists, with the ordering in SQL

**Built 2026-09-12, version `2.238.0`.** Closes `DEF-CUS-4996`, `DEF-CUS-5060`
and `DEF-CUS-5061`; files `DEF-CUS-5091`. The ruling is the PO's of 2026-09-10
as extended 2026-09-12 (`OQ-CUS-1790`, option (c)); step 1's measurements are
`CR-094-lane1-register-step1.md` and every before-figure below is theirs,
**re-measured on this branch before a line was changed**.

Measured against a booted stack — Django on `127.0.0.1:8640`, the built SPA on
`127.0.0.1:8641`, the seeded `brazosbend` tenant, Chromium at **1440×1000 and
1280×900**, signed in as Dana Whitfield.

---

## 1 · WHAT THE EIGHT TABS OPEN ON NOW

`before` is step 1's measurement, re-confirmed on this branch. `after` is read
off the rendered table where the tab held enough rows to have a position, and
off the queryset's own `ORDER BY` where it did not — the third column says which.

| tab | opened on (before) | opens on (after) | sort control | how *after* was established |
|---|---|---|---|---|
| accounts | `name` A→Z, sorted in **Python** | `created` desc, `ORDER BY` + `LIMIT` | had one; gained `created` | **browser**, 73 rows |
| requests | `received_at` asc | `created` desc | **new** — `request_no` · `applicant` · `received_at` · `state` | **browser**, 18 rows |
| new-connects | `target_activation` asc, nulls last | `created` desc | **new** — `connection_no` · `target_activation` · `state` | **browser**, 8 rows |
| move-ins | `opened_at`, `account_no` | `created` desc | **new** — `account` · `move_in_date` | queryset `ORDER BY` (1 row on screen) |
| move-outs | `closed_at`, `account_no` | `created` desc | **new** — `account` · `move_out_date` | queryset `ORDER BY` (1 row on screen) |
| transfers | `-created_at, -id` ✅ | **unchanged** | **new** — `reference` · `out_date` · `in_date` · `state` | queryset `ORDER BY` (0 rows) |
| disconnects | `account_no` asc | `created` desc | **new** — `account_no` only | **browser**, 7 rows |
| imports | `-created_at` ✅, **capped at 200** | unchanged, **uncapped and server-paged** | `started` · `run_no` · `status` | API envelope |

⚠ **FIVE OF THE EIGHT WERE WALKED WITH ENOUGH ROWS TO READ A POSITION; THREE
WERE NOT, AND THIS SAYS SO RATHER THAN IMPLYING OTHERWISE.** The demo utility
holds ONE move-in, ONE move-out and ZERO transfers, so on those three every
ordering puts the same row first and a browser check there would report success
over anything at all. `10-scripts/cr094c_seed_worklist_rows.py` explains why they
are not seeded: a move-in is *the life of a `BR-CUS-018` draft account*, a
move-out is written by `services.move_out` in one commit, and a transfer has two
halves plus §5.7.3's counting contract that three tabs read — hand-built rows for
any of them would be shapes the product cannot produce, and an ordering proved
over fiction is worse than an ordering not proved.

---

## 2 · THE TWO FIGURES THAT MATTER, BEFORE AND AFTER

### 2.1 Where the newest account lands

| | account | position | page at `per=50` |
|---|---|---|---|
| before | `AC-2026-00052` *Ridge Property LLC*, created that morning | **58 of 73** | **2** |
| after | the same account | **1 of 73** | **1** |

### 2.2 What one page COSTS — rows BUILT, not seconds

`10-scripts/cr094c_accounts_page_cost.py`, on the same 73-account tenant:

| request | rows returned | rows built **before** | rows built **after** |
|---|---|---|---|
| `?per=1` | 1 | **73** | **1** |
| `?per=10` | 10 | **73** | **10** |
| `?per=50` | 50 | **73** | **50** |

⚠ **NEITHER OF THIS REPO'S USUAL INSTRUMENTS CAN SEE THIS, AND THAT IS THE
REUSABLE PART.**

* **The wall clock cannot.** Step 1 measured `?per=1` at 0.107 s and `?per=50` at
  0.102 s and drew the right conclusion from the *equality*. But both figures are
  dominated by fixed overhead at 73 accounts, so after the fix they read
  **0.156 s and 0.157 s** — still equal, still meaningless. A lane reading only
  the clock would have reported no improvement over a change that removed 98% of
  the work.
* **The statement count cannot either.** `DEF-2723` made this list cost a
  constant number of statements whatever the page holds, and that guarantee held
  the whole time while the rows those same statements BUILT grew with the tenant.
  `tests/test_def2723_accounts_list_statement_count.py` was green before and is
  green after.

**At T5's ceiling of 40,000 accounts the before-figure is 40,000 rows built to
draw fifty.** That is the arithmetic `NFR-3` exists to prevent, and `NFR-5` is
honoured by there being no cap of any kind in the fix: `per` clamps to the IS-2
vocabulary and `page` clamps into range, and neither ever refuses a row.

---

## 3 · THE FOUR SENTENCES, AND WHY THEY HAD TO CHANGE

Leaving them would have been hard-won law 1 in its purest form — the product
printing a guarantee it no longer keeps. Each is now a **FACT of three words**
plus an **INSTRUCTION of five**, and the clause that followed the dash is gone
because **B14 rule 33 puts RATIONALE at zero words on screen**.

| tab | before | after |
|---|---|---|
| requests | *"Sorted by age, oldest first — the oldest thing waiting is the thing to look at."* | *"Opens newest first. Click Received for oldest first."* |
| new-connects | *"Sorted by target date, soonest first — the next thing due is at the top."* | *"Opens newest first. Click Target for soonest."* |
| move-ins | *"Sorted by move-in date, soonest first. A move-in with no start date is listed first — it cannot open until one is set."* | *"Opens newest first. Click Move-in date for soonest."* |
| move-outs | *"Sorted by move-out date, soonest first."* | *"Opens newest first. Click Move-out date for soonest."* |
| transfers | *"Newest job first — the one started last is the one still in hand."* | *"Opens newest first. Click a column to re-sort."* |
| disconnects | *"Sorted by account number. The ladder stops by itself when a customer pays or agrees a plan, and the row leaves this list."* | *"Opens newest first. Click Account for the alphabet."* |

**Six, not four** — transfers and disconnects were rewritten too. Neither was in
`DEF-CUS-5060`'s list of four, and both would have become false the moment their
tab gained a control: transfers' sentence claimed a fixed order and disconnects'
named an ordering that is no longer the default.

⚠ **ALL ELEVEN CATALOGUES, AND EACH ONE NAMES ITS OWN COLUMN LABEL** (B14 rule
35 — *a catalogue is written in its own language, not translated from English*).
A French clerk reads *"Cliquez Reçue pour les anciennes"* against a header that
says `Reçue`, not against the English word. Fanned in with
`10-scripts/i18n_fanin.py`; every catalogue holds **15,647** keys and G15's
parity was checked before and after.

⚠ **AND TWO OF THESE KEYS DID NOT EXIST IN ANY CATALOGUE.**
`customers.moveIns.list.sortFootnote` and `customers.moveOuts.list.sortFootnote`
were being rendered from an English `defaultValue` in the component — so those
two sentences reached a `ja-JP` or `hi` tenant **in English**, and had done since
the tabs shipped. The same was true of the two move-date COLUMN labels
(`customers.moveIns.col.moveInDate`, `customers.moveOuts.col.moveOutDate`), which
the new sentences name. All four are in the catalogues now. **It was found only
because the sentence had to name the column, and the column had no name to use.**

---

## 4 · FOUR JUDGMENTS MADE HERE, NOT RAISED

1. **The derived sorts stay in Python.** `balance` and `last_bill` are figures in
   the LEDGER and in BILLING, not columns (`BR-CUS-016`; `DEF-127` records that
   the cached `accounts.balance` is written by nothing), as are the `f.ageing` and
   `f.balance_gt` filters. An `ORDER BY` or `WHERE` over either would be a second
   implementation of a figure that already has one, free to disagree with the cell
   the same response renders. `ACCOUNT_DERIVED_SORTS` names the four out loud, and
   `account_page` falls back to the whole-tenant build only for them. **The
   expensive path is now an exception a clerk opts into.**
2. **No `Created` column on any tab.** Neither the blueprint nor B18 draws one;
   the UI skill's §2.5 says an absence is a decision. **The consequence, stated:**
   while a list is on its default no header carries the sort glyph, and the
   sentence under the pager is what states the ordering — which is the mechanism
   six of these tabs already used for that job.
3. **The sort names are the screens' existing column keys**, not tidier ones.
   `DataTable` keys a clerk's saved show/hide/reorder set on `screenId` + column
   key (`BR-SHL-013`, `DEF-647`), so renaming a column to match a cleaner server
   name would have silently discarded every saved column set on this screen. The
   SERVER name moved instead: `received` → `received_at`, `target` →
   `target_activation`, `account_no` → `account` on the two move tabs.
4. **One `order_terms` helper, not seven `if sort == …` ladders** — the PO's
   standing instruction of the same day, *"dont create duplcate code"*. Seven
   copies is seven places for the descending branch to forget the tiebreak the
   ascending one remembers, and the symptom of that is a row appearing on two
   pages, which raises no exception anywhere.

---

## 5 · WHAT THIS LANE GOT WRONG, AND WHAT CAUGHT IT

**None of the three was caught by a gate, a type checker or a unit test.**

### 5.1 · All eight lists opened on the OLDEST row, with every test green

The first draft stored `("-created_at", "-id")` in all seven sort maps **and**
declared `DEFAULT_DIR = "desc"`. `order_terms` flipped the term for `desc`
exactly as documented, the two minuses cancelled, and the default became
*oldest first* — `BR-CUS-1046` inverted and shipped as a working feature.

**The unit test was green because it had been written to the same wrong
convention as the code.** What found it was `curl`-ing the endpoint and reading
the first three account numbers: build-process step **2d**, *prove it by
clicking*. The test now asserts the CONVENTION — a term is stored ascending and
*newest first* is `desc` over it — and its own docstring records that it once
asserted the opposite.

### 5.2 · A stale `runserver` served the previous module, twice

Both times the process survived a `kill` of the wrong pid, answered `200`, drew a
real screen and served the PREVIOUS code. The first time it looked like the fix
had not worked; the second it produced a wrong `sorts` vocabulary. **Both were
false findings about working code**, which is the failure a walkthrough is
supposed to prevent rather than manufacture. The walkthrough now **reads the
served sort vocabulary and asserts it matches the source**, which is a check a
stale process cannot pass.

### 5.3 · Two drafts of one assertion named a row instead of a rule

Both asserted that a specific seeded reference would be first, and both were
wrong for different reasons — the rendered cell carries a `Master` kind chip
beside the number, and the demo data already held a request received earlier than
anything the seeder plants. **A check that knows a row rather than a rule reports
a FAIL over a correct ordering.** The walkthrough now asks two questions neither
seeding nor demo data can break: did the order CHANGE when the header was
pressed, and does the SCREEN render what the SERVER ordered.

---

## 6 · WHAT IS STILL OWED, EACH ROUTED

1. **`DEF-CUS-5091` — a chosen sort does not survive a refresh on seven of the
   eight tabs.** It WINS everywhere; it survives a reload only on the accounts
   tab, the one of the eight keeping its table state in the query string. The
   other seven hold it in `useState` by `DEF-664`'s deliberate design, because
   all eight tabs share ONE query string and each one's `?sort=` would overwrite
   the others'. **That is half of `BR-CUS-1046`'s second clause**, and fixing it
   is a decision about how eight tabs share one address rather than a line of
   code. The walkthrough asserts the current truth and names the row, so the day
   it is fixed the check goes red and says which defect it belongs to.
2. **`DEF-SHL-5062` — no sort glyph on an unsorted column** (B14 rule 13's first
   clause) is `CR-093-BRC01`'s. **Stated, not built.** It now applies to sixteen
   more headers than it did this morning, which raises its value and does not
   move its owner.
3. **The three Imports tabs still page in the browser.** The server is uncapped
   and paged; `getImportRuns` asks for the top IS-2 page size so all three behave
   as they did, with the ceiling lifted from 200 to 1,000. Converting them needs
   the server to publish the `loaded` and `rejected` SUMS over the whole filtered
   set first — all three compute their KPI tiles by summing `rows`, so paging on
   the server without those sums would turn three tiles from totals-over-
   everything into totals-over-one-page. **A wrong figure is worse than a
   truncated list**, which is why the server half shipped alone and the client
   half is filed. Two of the three tabs are other modules' screens.
4. **`sort=created` is declared on the accounts list and reachable only by URL**,
   since no column carries it (§4.2). A clerk who chooses a column cannot click
   their way back to the default; they reopen the tab. Recorded here rather than
   filed, because adding the column is the thing §4.2 declined to do.

---

## 7 · HOW TO RE-RUN EVERY FIGURE ABOVE

| what | command |
|---|---|
| what each tab opens on | `python3 10-scripts/cr094_lane1_register_measure.py --base http://127.0.0.1:8640` (step 1's instrument, unchanged — it prints its own before/after) |
| rows built per page | `cd 06-backend && python3 ../10-scripts/cr094c_accounts_page_cost.py` |
| enough rows to see an order | `cd 06-backend && python3 ../10-scripts/cr094c_seed_worklist_rows.py` (`--remove` to undo) |
| the screen, at both widths | `node 10-scripts/cr094c_sort_walkthrough.mjs` |
| the ordering itself | `cd 06-backend && JOBS_EAGER=false pytest tests/test_br_cus_1046_lists_open_newest_first.py --reuse-db` — 23 cases |
