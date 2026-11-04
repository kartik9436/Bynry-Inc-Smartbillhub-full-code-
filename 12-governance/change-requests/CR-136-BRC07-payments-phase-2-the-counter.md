# `CR-136-BRC07` · Payments blueprint **phase 2 — The counter**

> **READ THIS FIRST IF YOU ARE A NEW SESSION.** This file is the live progress
> record for phase 2. It exists because the PO asked for one, verbatim
> (2026-09-23): *"also keep a note of phase 2 tasks what is cimpleted and what
> is pending of crete are oer in this chat we will ahve to take it to another
> chat"*. The chat does not survive; this file does (hard-won law 9/10).
> **Every lane updates its own row in §4 in the commit that finishes it.**

| | |
|---|---|
| **Branch** | `claude/laughing-thompson-kpmwih` |
| **Source document** | `05-prototype/06 Payments Page Blueprint.pdf` — phase 2 task table on **pp.16–18**, the six Counter screens on **pp.54–59** |
| **Phase before this** | `CR-135-BRC07` (phase 0, 17 tasks, **DONE**) and phase 1 (23 tasks, **DONE**) |
| **Tasks drawn** | **19** — 3 backend · 2 db · 4 front end · 2 other · 5 test · 3 e2e |
| **Tasks added by PO ruling 2026-09-23** | **4** (§3) — so **23 in total** |
| **Status** | see §4. Nothing was started before 2026-09-23. |

---

## 1 · What phase 2 is

**The biggest single gap in the payments module: six screens behind one table.**

**What a clerk can newly do:** open a till, take a shift's money into one batch,
and balance the drawer. **None of it is possible today** — there is no session,
no float and no count anywhere in the running product.

**Done when:** a clerk opens a counter at 08:55, takes seventeen payments,
closes it at 17:30 with a counted drawer, and a supervisor can see the three
tills nobody counted.

**A till is one person's drawer, for one shift, at one counter window.** Three
clerks at three windows of one office are three tills. One person may have only
one open at a time — `uq_counter_sessions_open_owner` refuses a second, and
that index already exists.

---

## 2 · How the screens are built — the PO said this twice, it is not optional

PO, 2026-09-23, verbatim: *"please ensure for all frotnend tasks use - images
from drawing to create scren, use ui skills from repo - very important"*, and
on 2026-09-22 in the same words for phase 1.

* **B14 rule 42 — a screen is built from the drawing AS AN IMAGE.** Extracted
  text is an index for finding the page, never the specification. Render with
  `10-scripts/pdf/pdf_render.py` at scale 2.0 and **look at the page**.
* **B14 rule 41 — the product UI matches the blueprint EXACTLY.** The only
  thing that reaches the PO is a drawing that contradicts a signed rule — which
  happened four times here and is §3.
* **B14 rule 36** — the drawing gives layout and detail; **`05-prototype/r10-2026-08-16/UI-RULES.md` gives the visual style**, and the shared component kit is how you comply.
* **B14 rule 38** — where the drawing and our UI rules disagree about how a
  FORM is built (side-by-side fields, help under an input, footer button
  order), **the UI rules win**. What the form CONTAINS is still the drawing's.
* **B14 rule 43** — a piece of UI is built as a **component**. Inline code in a
  page is not reuse.
* **B14 rule 21** — Tailwind utilities, no new stylesheet class; add the file to
  `07-frontend/src/styles/route-b-migrated.txt` or `G31` goes red at merge.
* **B14 rule 31** — no database id is ever the visible value of a field.
* **B14 rule 33** — label ≤ 3 words · fact ≤ 6 words · instruction ≤ 6 words per
  sentence · **rationale is ZERO words on screen**.
* **Count B14's own status table before trusting any number in a pointer**,
  including the one in `CLAUDE.md`.

---

## 3 · The four PO rulings of 2026-09-23 — read these before building anything

All four are in `12-governance/02-decision-log.md` at that date, with their
worked figures and their rejected options. **Hard-won law 13: never re-ask.**

### 3.1 · A till never closes itself — the drawing loses

PO: *"(a) Your ruling stands — no auto-close. A System Admin closes it. Dana
cannot work Tuesday until someone is free to do that"*.

* **DO NOT BUILD** the midnight auto-close the blueprint draws at `P2.18`.
* **DO NOT BUILD** the *auto-close* half of the blueprint's `Counter setup`
  setting. It ships with **the float alone** — a setting nothing honours is
  hard-won law 1.
* **No scheduled job may CLOSE a till.** `P2.11`'s notice to the supervisor
  TELLS; it never closes.
  ⚠ **AMENDED 2026-09-23 (`DEF-PAY-6268`). THIS BULLET READ *"No scheduled
  job is written"*, WHICH IS NARROWER THAN THE RULING AND IS WHAT KEPT `P2.11`
  UNFIRED FOR A DAY.** The ruling's own row in `12-governance/02-decision-log.md`
  says, in one sentence, what is forbidden and what is expected: *"only the
  midnight auto-close is struck; **no scheduled job is written**, so `P2.11`'s
  notice to the supervisor is **the only thing that fires overnight** and it
  TELLS rather than CLOSES"*. **A notice nothing schedules fires never, not
  overnight.** A lane reading this bullet, and the identical paraphrase in
  `J-PAY-forgotten-till`, built the notice and left nothing to run it — so the
  cost this section accepts, a clerk who cannot take money until a System Admin
  seals yesterday's till, had no upper bound. `apps/payments/
  counter_watch_schedule.py` now fires the sweep at **06:00 on each utility's
  own clock** and closes nothing; a test asserts that absence from the source of
  both modules. **What stays forbidden is unchanged: no job seals a till.**
* `P2.18`'s journey becomes: *home without closing → **a System Admin
  force-closes** → Not counted → declared next morning with a reason.* The
  declare step, the Not counted list and the required reason all survive.
* `close_kind` still holds exactly `counted`, `forced`, `system`.
* **The accepted cost:** a clerk whose supervisor is unavailable cannot take
  money that morning. The PO chose that explicitly.

### 3.2 · A late count sits BESIDE the forced close, never over it

PO: *"(a) Keep it as a forced close and add the late count beside it"*.

Worked case: Dana's till is force-closed Monday night uncounted; Tuesday she
counts **$1,228.00 against $1,240.00 expected — $12.00 short**, reason *"cheque
stuck to the bag"*. The one row then says **both**: force-closed Monday by the
supervisor, declared Tuesday by Dana, $12.00 short.

* `close_kind` **does not move** and stays at three values. Nothing built in
  phase 0 changes.
* Declaring fills `counted_totals`, `difference` and `note` — NULL on a forced
  close precisely because nobody counted.
* **Two new nullable columns, `declared_at` and `declared_by`** → task `P2.20`.
* **Paired by CHECK constraint, not by a service check**: both set or both
  NULL, and `declared_at` set requires `close_kind = 'forced'`. A counted till
  was already counted; a system till is nobody's.
* **`Not counted` is one derived expression with four readers** — screen 3·1's
  list, its filter chip, `P2.11`'s notice, and phase 2's own done-when. Write
  it once (B14 rule 43).
* Hard rule 4 does not bite (`counter_sessions` is not one of its four frozen
  tables); hard rule 7 does — a declare writes `audit_log`.

### 3.3 · A drawer difference reaches the books

PO: *"(b) Post it. A short writes a balanced pair to a cash over/short account
the day it is declared. Needs one new account added to the chart"*.

* **This supersedes the blueprint's *"The ledger: Nothing — counting is not a
  posting"*, and `P2.15`'s test flips** for a non-zero difference.
* **$12.0000 short →** DR `6850 Cash over and short` · CR `1010 Undeposited
  funds`. **$12.0000 over →** the mirror. **One account, both directions.**
* **New seeded account `6850 Cash over and short`**, expense, category
  operating expenses, between `6800 Bank fees` and `6900 Bad debt` in
  `06-backend/apps/ledger/chart.py`, with its own designation → task `P2.21`.
  **A seeded default a tenant may re-code on Settings → Accounting**, never a
  constant.
* **It posts when the money is COUNTED** — at close on a counted close, at
  declare on a forced one. That is what makes the PO's *"the day it is
  declared"* true of both. **A zero difference posts nothing.**
* **Against `1010`, not `1000`.** Taking money already debits `1010`; the bank
  receives only what was in the drawer, so the difference must leave `1010`
  before the deposit clears it or reconciliation carries a permanent stub.
* **Hard rule 5 untouched** — payments calls the ledger posting service, as
  taking a payment already does. It does not write a journal line itself.

### 3.4 · Cash, cheque and money order are refused without an open till

PO: *"(a) Refuse it. \"Start your counter first.\" One press, then take the
money. It is the only option where every cash dollar belongs to somebody"*.

* **Three of the seven tenders pass through hands — `cash`, `check`,
  `money_order`** — and those three are refused when the person recording them
  has no open till.
* **The other four keep phase 0's system till unchanged** — `ach`, `card`,
  `wire`, `lockbox`. A card swiped at a window is among them on purpose: the
  Close screen counts only cash and cheques, and a card total typed back at the
  system's own figure makes the reconciliation worthless.
* **`payments.counter_session_id` STAYS NULLABLE.** `P2.4` does not move. A
  `NOT NULL` would refuse every ACH, card, wire and lockbox row in the product.
* **Enforced at the endpoint, not by hiding a button** — `BR-SHL-025`.
* **`P2.9` is the way out and is already drawn.** A refusal with no door is
  hard-won law 2's mirror.
* ⚠ **NOT DECIDED: a cheque that arrives in the MAIL.** The case shown to the
  PO was cash at a counter. A back-office clerk keying a mailed cheque never
  sits at a till and this rule would refuse them. **Do not build a silent
  exception and do not widen the ruling** — raise it as a new question when the
  take-payment path is built.

---

## 4 · The task board — **UPDATE YOUR ROW IN THE COMMIT THAT FINISHES IT**

Status values: `NOT STARTED` · `IN PROGRESS <lane>` · `DONE <commit>` · `BLOCKED <why>`.

### The 19 drawn tasks

| Task | Kind | What | Status |
|---|---|---|---|
| `P2.1` | backend | `POST /counters` — opens the session **and its batch in one act**; refuses a second open till for the same person | **DONE ff1b3b3ee** — LANE P2-API |
| `P2.2` | backend | Close, force-close, **declare** — three endpoints, three different rows. Carries §3.2 and §3.3 | **DONE ff1b3b3ee** — LANE P2-API |
| `P2.3` | backend | `GET /counters` and `GET /counters/{id}` with the running split by method | **DONE ff1b3b3ee** — LANE P2-API |
| `P2.4` | db | `payments.counter_session_id` — a **nullable** deferred uuid, the shape `deposit_batch_id` already uses | **DONE `0eed90f56`** (LANE P2-DB, `payments/0035`). ⚠ Built as drawn, and **both reasons the drawing gives for the uuid are false** — `DEF-PAY-6219`: `counter_sessions` is a PAYMENTS table so no module is crossed, and `B11 F-3` is about migration ORDER, which cannot apply to a table that has existed since `payments/0031`. The reason that holds is consistency with `deposit_batch_id`. **Neither column has referential integrity** — stated in the migration, not left to be found |
| `P2.5` | db | An index on `(tenant, counter_session_id)` — the till's running total reads it on every payment | **DONE `0eed90f56`** (LANE P2-DB, `ix_payments_counter_session`). **PARTIAL**, measured on PostgreSQL 16.13 at 40,000 rows by `10-scripts/cr136_p2_5_till_index_measure.py` — and **the measurement refuted the obvious argument for it**: btree dedup makes a NULL key cost ~7 bytes against a real id's ~48, so the saving is **264 kB** at T5's ceiling and decides nothing. What decides it is that the planner provably uses it **under a GENERIC plan**, and that the query it cannot serve wants a `Seq Scan` anyway. Write cost measured and **discarded as noise** |
| `P2.6` | front end | **The six Counter screens** — Counters · My counter · Start · Close · Force close · Declare. From the kit, from the images | **DONE 35f86b374** (LANE P2-SCREENS). Built from p051–p059 as IMAGES at 2.0. Badges `PAY-04` (3·1) and `PAY-07` (3·2) — **not `PAY-03`/`PAY-05`, which r10 already draws for Deposits and Imports.** ⚠ **TWO CONTRACTS THE SCREENS NEED FROM `P2.1`–`P2.3`:** (a) a counter resolves by its **CODE**, because the drawing puts `CTR-260921-DW` in the address bar and B14 rule 31 keeps a database id out of it; (b) `GET /counters` accepts **`f.mine=1`**, the only way a page head can ask *is MY till open?* |
| `P2.7` | front end | `Start counter →` in every payments page head — **missing from the whole product today** | **DONE f77dca804** (LANE P2-SCREENS) — `CounterHeadSlot`, on all seven tabs. **Both of 2·1 ①'s states**, because a slot that always says `Start counter →` offers an act `uq_counter_sessions_open_owner` refuses: with a till open it reads `Your counter · <code> · open` and is the door back to 3·2. Both are ADDRESSES, asserted as such. |
| `P2.8` | front end | Source and Batch columns + a filter chip for each on the payments list (2·1) | **DONE 29bcbb31e** (lane ONEPATH). ⚠ **DRAWING CHECK DONE 2026-09-23 by LANE P2-SCREENS against p030 as an image, and it is NOT clean.** Right: the column ORDER (Source and Batch between Payment # and Posted), the words `Counter`/`Digital`/`Post`, the search placeholder. Missing: **the Batch filter** — the frame draws both chips applied and its own badge reads *2 FILTERS* (`DEF-PAY-6227`). ⚠ **`DEF-PAY-6227` IS NOW BUILT (lane P2-HEAD).** `f.batch` takes the CODE the cell shows and repeats the cell's own precedence — an imported cheque that has since been BANKED reads as its deposit batch, so the import leg excludes anything banked, because a list that contradicts its own column is worse than one that finds nothing. Six cases in `06-backend/tests/test_cr136_p2_8_batch_filter.py`; the chip's options are the batches ON THE PAGE, since a served list of every batch a tenant ever cut is unbounded (`NFR-5`). And a counter payment reads `No batch yet` until its till is banked where the drawing reads the till's own code from the first payment (`DEF-PAY-6228` — now unblocked, `counter_session_id` landed in `payments/0035`). |
| `P2.9` | front end | 2·3a gains the banner — **offers `Start counter →`** rather than only refusing. §3.4's way out | **DONE f77dca804** (LANE P2-SCREENS) — `RecordCounterBanner`, at the top of the Record form. With a till open it names it; with none it says *Start your counter first.* **and carries the door**. ⚠ **It refuses nothing** (`BR-SHL-025` — the check is `P2.23`'s, at the endpoint) and it says **nothing at all** to `ach`/`card`/`wire`/`lockbox`, because §3.4 names only the three tenders that pass through hands. ⚠ **2·3a's agreed move from a modal to `/payments/record/new` WAS a SEPARATE change and is now DONE — `DEF-PAY-6317`, 2026-09-23, LANE RECORD-PAGE.** ⚠ **AND THE WAY IT WAS DEFERRED IS THE FINDING.** This sentence, the `P2.6` conformance note and `CounterDoors.tsx`'s `exceptions:` line all said it verbatim and **none of them was a queue**: it never became a CR row, an open question, a task or a defect, so nothing counted it and no gate could — a lifecycle `exceptions:` line is a docstring, and no check in this repo reads one for work still owed. The PO found it instead, on the deployed build, with the drawing open beside the product: ***"record payment is form - not modal"***. **A deferral recorded only where the code is is a deferral nobody can count** — the same shape as the two lanes who wrote `OQ-1330` in prose and filed no row (CLAUDE.md hard rule 4). |
| `P2.10` | other | Finance picks up the batch — a closed till's batch appears on Deposits ready to match | **DONE** — LANE P2-WIRE (draft) + LANE P2-WIRE-RESUME (re-derived, measured and proved), 2026-09-23. ⚠ **MEASURED BEFORE ANYTHING WAS CHANGED, AND THE TASK POINTS THE OTHER WAY: `bankrec_read.batch_queryset` filtered on `tenant_id` ALONE** (plus `f.status` and `f.method`), so a closed till's batch already appeared and **nothing had to be built for the sentence to be true**. What phase 0 broke is the opposite — since the re-key a batch exists from the moment the drawer OPENS, so **Dana's open till was on Finance → Deposits, statused `in_transit`, folded into the In-transit tile and a candidate for `auto_match` and `reconcile_batch`** — which LOCKS it (`BR-PAY-004`), after which `_recompute_total` refuses the edit and the money taken later can never be accounted for (`DEF-PAY-6266`). **Measured on PostgreSQL 16.13: four rows and `$7,181.10` before, three rows and `$6,568.60` after, `$612.50` held back.** The rule is the blueprint's own word, p059 read as an IMAGE — at Close *"The batch becomes bankable. **It is the deposit batch**"*, and at Start that table changes nothing on Deposits. **ONE expression, EIGHT readers** — `bankrec_models.BANKABLE` (`session_id IS NULL OR session.closed_at IS NOT NULL`), read by the Deposits list · its KPI strip · S38 step 2's hand-match picker · the `needs_a_look` classifier behind it · the reconciliation statement's *deposits in transit* · `auto_match`'s candidate scan · and the two human write paths, the last two refusing BY NAME at the endpoint (`BR-SHL-025`) rather than trusting the row to be off the list. ⚠ **THE FIRST DRAFT OF THIS TASK SAID FOUR READERS AND WIRED TWO** — S38 step 2's hand-match picker, its `needs_a_look` classifier and CS-14's *deposits in transit* were still filtering on `status` alone, so the picker offered a control the service refuses and the statement disagreed with the tile it cites as its definition; found by grepping the remaining `BATCH_IN_TRANSIT` filters and each given a case; `is_bankable` asks the SAME `Q` of the database rather than mirroring it in Python. **No second path was built** — one Deposits list, one condition. **Three populations keep showing and that is load-bearing:** session-less (banked the old way), the SYSTEM till (born closed — every ACH, card, wire and lockbox deposit) and a sealed counter till. ⚠ **The held-back money is SERVED AS A FIGURE, never a silence** — `still_open` on the body, one line on S37 reading *"$612.50 still at one open counter"* (six words, B14 rule 33), because a declared blind spot with no number is indistinguishable from an empty one (law 7). **PROVED RED FIRST IN A BROWSER** on the tip's own query — full stack, built SPA, Chromium at 1440, signed in as Dana: **11 passed · 3 failed**, then **14 · 0** with the fix (`10-scripts/p2_10_11_finance_and_notice_walk.mjs`); red in `pytest` too. 17 backend cases, 24 frontend cases |
| `P2.11` | other | Notification: the unclosed till. **Tells a supervisor; never closes** (§3.1) | **DONE** — LANE P2-WIRE (draft) + LANE P2-WIRE-RESUME (proved) + LANE P2-SCHEDULE (fired it), 2026-09-23. **IT FIRES ON *STILL OPEN* (`closed_at IS NULL`), NOT ON *NOT COUNTED*** — the two are a day and a person apart, and the choice is argued in the decision log: the blueprint's task row names *"the **unclosed** till"* (p017), screen 3·1 draws exactly this state as the words *"still open"* (p051), and **§3.1 made a System Admin's force close the only way an unclosed till gets sealed, so the notice is what PROMPTS it** — a notice on *Not counted* would tell a supervisor about work they had just done, and p059 already gives that moment a different message to a different person (*"the owner is told"*). The expression is written ONCE as `counter_session_models.STILL_OPEN`, beside `NOT_COUNTED` (B14 rule 43). **SET-12 event `counter_left_open`** in `rule_catalog.py` — the reference the blueprint's own row names — staff & system, in-app + email, timing `end_of_banking_day`, LIVE from its first commit, so `BUILT_EVENT_COUNT` is **31** and the staff events are **6**; eleven locale catalogues carry both new keys. ⚠ **IT TELLS AND IT NEVER CLOSES** — `counter_watch.py` contains no write to `counter_sessions` and the ABSENCE is the deliverable, so the till is read back field by field. **The cut-off is a MOMENT** (midnight of the swept day on the tenant's own clock, BR-TEN-081), never a truncated `opened_at::date`, which is `OQ-153`; the day is an INPUT (BR-TEN-043) and `counter_watch` reads no clock at all. **The sweep enters each tenant's context explicitly and reports `tenants_examined` beside `tills_left_open`** — a query with no `app.tenant_id` matches zero rows and reports success, so *"0 left open"* alone is what a sweep that entered no tenant also prints. **PROVED ON REAL POSTGRESQL 16.13** (law 14 — the default suite is in-memory SQLite and the per-tenant savepoint is that law's own shape): one `in_app` queue row, `total_count: 1 · failed_count: 1`, to the System Admin under BR-NOT-021(e) with **no signed-in user**; **every till column byte-identical afterwards**; a re-run wrote nothing (rule 6, derived `uuid5` of tenant and day). **And looked at in a browser** — Settings → Notifications draws *Counter left open · Staff · In-app alert · "When the banking day has ended"* · ON, with no event key on screen. ⚠ **AND IT IS SCHEDULED — LANE P2-SCHEDULE, 2026-09-23, `DEF-PAY-6268`.** This cell read *"**NOT SCHEDULED** — `manage.py sweep_open_counters` is a command and this repo has no beat schedule … **REPORTED, not done**"*, and **the second clause was false when it was written**: five beat entries were already installed from five `AppConfig.ready()` methods, one of them (`payments.collections_ladder`) in this very app. So nothing fired the notice and the cost §3.1 accepted — a clerk who cannot take money until a System Admin seals yesterday's till — had **no upper bound**. **`apps/payments/counter_watch_schedule.py` now fires it at 06:00 ON EACH UTILITY'S OWN CLOCK**, installed by `PaymentsConfig.ready()`: beat fires a fan-out every 900 seconds (a DURATION — BR-TEN-043) and each firing asks each LIVE utility *is it your hour yet, on your clock?*, so Chicago and Honolulu are told five hours apart and neither on the server's morning. **06:00 and not midnight is a judgment and it is in the decision log**: the cut-off for *left open* does NOT move (midnight of the swept day, the tenant's own, a MOMENT not a truncated date), only the telling waits — so `find_open_tills`' late-close allowance, written for *"somebody who closed late, this morning, before the sweep ran"*, can still fire, and the message is in front of the person who can act on it at the moment they can. **IT STILL TELLS AND NEVER CLOSES**: the schedule module contains no write either, and a case asserts the absence from the SOURCE of both files and reads the swept till back field by field. **`G132`** fails any module that declares a beat entry its `ready()` does not install — `G117`'s third clause asked of every module instead of the `runbooks` queue alone — and the proof that matters reads `config.celery.app.conf.beat_schedule`, not `beat_schedule()`. **DONE.** |
| `P2.12` | test | Open and its batch in ONE transaction; a second open for the same person refused | **DONE** — LANE P2-TESTS, 2026-09-23. Two halves. `06-backend/tests/test_cr136_p2_12_14_15_the_counter_contract.py` takes it to the **ENDPOINT**, which `test_cr136_p2_counters.py` cannot: a second `POST /counters` is a **422 `BIZ-COMPLETENESS` carrying the sentence**, not an exception and not a 500, and a refused open leaves **neither** row. `10-scripts/cr136_p2_counters_postgres_proof.py` gains **part A3**, the same race run through `open_counter` itself rather than through raw SQL — proved RED first (index dropped ⇒ **both** service calls win, two open tills, so the service's own `SELECT` was never the barrier). ⚠ **AND IT FOUND `DEF-PAY-6262`:** under a genuine race the loser gets a raw `IntegrityError` naming the index, which travels past `counters_api`'s `except PaymentRuleError` and reaches a clerk as a **500**. The money is safe — A3-2 measures **one till and one batch**, so the atomic block holds — and `open_counter`'s own docstring claims the opposite about the WORDS |
| `P2.13` | test | The till id attaches **when taken, not at close** | **DONE** — LANE P2-TILLWIRE, 2026-09-23, `06-backend/tests/test_cr136_p2_13_the_till_attaches_when_taken.py`. ⚠ **IT HAD NO BUILD TASK BEHIND IT AND NOTHING WROTE THE COLUMN** (`DEF-PAY-6226`) — the build is `P2.24` below. The stamp is asserted **while the till is still OPEN**, which is the half that carries the point. ⚠ **AND THE NEGATIVE IS IN THE SAME FILE, because the positive is worthless without it:** a test that stamps a till id and asserts it is there passes just as happily when the tender filter is inverted or missing, so an **ACH, card, wire and lockbox payment taken while the same clerk's till is open is asserted to carry NO till and NO batch**, and the service refuses a till for those four BY NAME. |
| `P2.14` | test | Close with and without a difference — three states from three endpoints, each distinguishable after | **DONE** — LANE P2-TESTS, 2026-09-23. Driven through the **three endpoints** (`/close`, `/force-close`, `/declare`), which carry three different permission classes and three bodies a service test cannot see. ⚠ **FOUR STATES, NOT THREE:** `counted` · `forced` · **`forced` + declared** (§3.2 — the late count sits BESIDE it) · `system`, and the existing `test_p2_2_the_three_close_states…` builds only two of them and no `system` till at all. Told apart **by a COUNT of signatures asserted whole**, never a loop — a loop is green when the list shrinks, and if `declared_at` left the signature the tally reads `{forced: 2}`, which is exactly the collapse §3.2 exists to prevent. **Proved RED** by dropping `declared_at` from `NOT_COUNTED`: this lane's case went red and the P2-API case stayed green |
| `P2.15` | test | The ledger pair, and the absence of one. ⚠ **FLIPPED BY §3.3** — a non-zero difference now DOES post | **DONE** — LANE P2-TESTS, 2026-09-23. ⚠ **THE OVER HAD NEVER BEEN TESTED, ANYWHERE.** `test_p2_22_a_short_drawer_posts_a_balanced_pair` only ever counts a SHORT, so a seam that put `6850` on the debit whatever the sign passed it for ever. **Proved:** inverting `over = difference > ZERO` in `ledger_seam` turned this lane's OVER case RED and left the existing short case **GREEN** — the whole product posting every drawer difference backwards, with the old coverage green over it. Also new: the posting happens **at DECLARE** on a forced close and **nothing at all** at the force-close itself; a zero difference posts nothing **on either path**; *"balanced at take"* (the half of the drawing §3.3 did NOT move) is asserted; and hard rule 5 is checked by reading the payments module for a direct `JournalLine.objects.create`. On PostgreSQL: **part D2** of the proof adds the mirror, the unsigned amounts (`CHECK (amount >= 0)` is raw DDL and is on no SQLite table) and the declare path under `ck_counter_sessions_declared_together` |
| `P2.16` | test | `Start counter →` asserted **by address** on every payments screen | **DONE** — LANE P2-TESTS, 2026-09-23, `07-frontend/src/features/payments/counterDoors.dom.test.tsx`. ⚠ **`CounterDoors.tsx` HAS NAMED THAT EXACT PATH IN ITS `Tests:` HEADER SINCE `f77dca804` AND THE FILE DID NOT EXIST** (`DEF-PAY-6263`) — hard-won law 1, and nothing in this repo checks a Trace header's path. **Both states, both by ADDRESS**, on **seven** screens: the scope is DERIVED from `PAYMENTS_TABS` rather than hand-listed, so an eighth tab is in scope the day it is declared; Refunds is the one exclusion and its reason (`/finance/refunds`, the FINANCE strip) is **asserted, not assumed**. A COUNT, not a loop. **Proved RED** by removing the slot from `CollectionsPage` — the failure printed `[ 'collections' ]`, which is `DEF-PAY-6237` reproduced and named |
| `P2.17` | e2e | `J-PAY-counter-shift` — 08:55 open with a $200 float · seventeen payments · 17:30 count · close · ends on Finance → Deposits | **DONE** — LANE P2-TESTS, 2026-09-23, `08-qa/01-e2e/journeys/JPAYCOUNTERSHIFT-a-shift-at-the-counter.md`. **Every figure was MEASURED, not planned** — `10-scripts/cr136_p2_17_counter_shift_readback.py` walks the shift on PostgreSQL 16.13 and prints what each step leaves. Cash 6 = `$510.00` and cheque 8 = `$1,284.60` on **two** batches of Dana's till; **card 3 = `$402.15` carries NO till and NO batch** and `record_payment` refuses by name if offered one (§3.4); 3·2 reads cash `$710.00` because **the float sits inside the cash line** (p056, as drawn); counted exactly ⇒ `0.0000`, `counted`, **no journal line**. ⚠ **STEP 6 IS HALF-SERVED AND THE JOURNEY SAYS SO RATHER THAN FAKING IT:** both batches ARE on `GET /deposit-batches` as `in_transit`, and the served row carries **no till and no clerk** — twelve keys, measured and listed. *"Ready to match"* is true; *"from Dana's counter"* is invisible. **That is `P2.10` and it is a COLUMN, not a screen** |
| `P2.18` | e2e | `J-PAY-forgotten-till` — ⚠ **REWRITTEN BY §3.1**: home without closing → **System Admin force-closes** → Not counted → declared next morning with a reason | **DONE** — LANE P2-TESTS, 2026-09-23, `08-qa/01-e2e/journeys/JPAYFORGOTTENTILL-the-till-nobody-closed.md`. **No midnight auto-close is written anywhere in it**, and step 2's assertion is an ABSENCE on purpose: at 00:00 the till is still open, at 03:00 it is still open, and any `close_kind = 'system'` on a PERSON's till is this journey failing. **The accepted cost is a numbered step** — Dana is refused her Tuesday till at 08:05 and cannot take money until a System Admin is free. Ten steps: forced close (supervisor recorded, owner kept, `difference` **NULL and not zero**), *Not counted*, the declare with its required reason, `close_kind` **unmoved**, the pair posted **at declare**, and the till leaving the list. ⚠ **THE GAP IS NAMED RATHER THAN ASSERTED:** `P2.11` is NOT STARTED, so between going home and being found **nothing reaches a human** — the supervisor finds the till only by opening 3·1, and §3.1's accepted cost then has no upper bound |
| `P2.19` | e2e | `J19-month-end-close` regression — the batching rule changed under it in phase 0 | **DONE** — LANE P2-TESTS, 2026-09-23, a regression section appended to `J19-month-end-close.md`. **No step added, no figure moved** — `598.69 / 598.69` and `553.69` are ❄️ signed and changing one is a finance re-sign. What it records: step 1's checklist item is `unreconciled_batch_count`, which counts **BATCHES**, so after `P0.6` the work between Finance and a closed month is **tills × tenders × drawer days** rather than tenders × drawer days — three clerks leave six batches where a day used to leave two. ⚠ **AND A COUNTED CLOSE RECONCILES NOTHING:** a clean `$0.00` shift leaves both its batches `in_transit`, measured. The 2026-08-22 fixture amendment says *"the seeder posts DEP-0731's reconciliation"* — **singular**, written when a drawer day was one batch; on a counter-bearing fixture that no longer clears the item and step 1 reports a second incomplete one. Measured on a migrated clone: **two `(day, tender)` combinations carry more than one batch, the largest 19** — the old key is no longer unique in the data |

### The 4 added by ruling — **not in the drawing**

| Task | Kind | What | From | Status |
|---|---|---|---|---|
| `P2.20` | db | `counter_sessions.declared_at` + `declared_by`, nullable, paired by CHECK, `declared_at` ⇒ `close_kind = 'forced'` | §3.2 | **DONE `0eed90f56`** (LANE P2-DB, `ck_counter_sessions_declared_together`). The second branch opens `close_kind IS NOT NULL` — **`DEF-PAY-6207` for the third time in this table**; without it the constraint is off for every OPEN till. **Proved RED first on PostgreSQL 16**: the naive spelling on the real table ACCEPTED an open till carrying a completed count. Five forbidden rows refused BY NAME, four lawful shapes accepted, forwards/backwards/forwards with `pg_get_constraintdef` read back. `Not counted` is written once as `counter_session_models.NOT_COUNTED`; **nothing imports it yet** — its readers are `P2.2`, `P2.3`, `P2.6`, `P2.11` |
| `P2.21` | backend | Seed `6850 Cash over and short` into `ledger/chart.py` with its designation | §3.3 | **DONE `c38878404`** — LANE P2-LEDGER, 2026-09-23. `cash_over_short` is the EIGHTEENTH GL designation; `6850 Cash over and short` (expense, operating expenses, `signed=False`) sits between `6800` and `6900`; `ledger/0016` moves the CHECK; `ensure_cash_over_short_account` is the first-use top-up. `BR-LED-796`. **Existing tenants DO get it** — the post-migrate reference sweep runs `seed_chart_of_accounts` over every tenant (see §7). **`P2.22` takes `BR-LED-797`**, reserved in `14-id-reservations.md` |
| `P2.22` | backend | Post the difference pair when the money is COUNTED — at close, and at declare. Zero posts nothing | §3.3 | **DONE ff1b3b3ee** — LANE P2-API |
| `P2.23` | backend | Refuse `cash`/`check`/`money_order` recorded with no open till, at the endpoint | §3.4 | **DONE ff1b3b3ee** — LANE P2-API |

### The 2 that were in NEITHER list — **and the absence is part of the finding**

**Nothing on the board above made a payment NAME its till.** `P2.4` shipped
the column, `P2.5` its index, `P2.1`–`P2.3` the readers and `P2.23` the
refusal, and `P2.13` — *"the till id attaches when TAKEN, not at close"* — is
a **TEST task with no build task behind it**. So the drawn 23 could every one
be DONE and the phase's own *done when* still be unreachable: a clerk opens a
counter at 08:55, takes seventeen payments, closes at 17:30 and **the drawer
is empty**, because every dollar banked under the system till, which is
openly nobody's. That is hard-won law 2 at its purest, on the money path, and
it is why these two rows exist rather than being folded into a drawn one.

| Task | Kind | What | From | Status |
|---|---|---|---|---|
| `P2.24` | backend | **The wiring `P2.13` tests and no drawn task builds** — `record_payment` stamps `counter_session_id` AND the till's `deposit_batch_id` in the one INSERT | `DEF-PAY-6226` | **DONE** — LANE P2-TILLWIRE, 2026-09-23. Three edits plus one the defect row did not foresee. `record_payment` gains `counter_session_id=`, resolves the till as a READ (so a replay opens no batch and a refused payment burns no `DEP-` number) and opens the till's batch for THIS tender inside the payment's own transaction. `api.account_payments` **passes the till it already resolved and was throwing away** — one name on one line was the whole defect. `reconciliation._session_for` returns the payment's own till. ⚠ **AND THE CUT'S GROUP KEY HAD TO MOVE WITH IT:** it grouped on the METHOD alone and then asked `_session_for(payments[0])`, correct only while every payment answered the same till — which was true precisely because the answer was always the system one. With a payment naming its own till, **Dana's cash and Marcus's would have been stamped into whichever till sorted first**. ⚠ Both columns are written at INSERT **or never**: `trg_payment_immutable` is `BEFORE UPDATE OR DELETE`, and `counter_session_id` is in neither the `mutable` nor the `stamps` allow list of `payments/0014`, which **does not move**. ⚠ The nightly cut never sees a counter payment — `deposit_batch_id IS NULL` filters it out before the loop, so it is neither re-grouped nor double-counted and hard rule 6 holds. |
| `P2.25` | backend | `f.mine` on `GET /counters`, resolved from the authenticated caller — and an unknown `f.*` REFUSED on that endpoint | `DEF-PAY-6235` | **DONE** — LANE P2-TILLWIRE, 2026-09-23. The page head asked `GET /counters?f.mine=1&per=1` and took the first row; **`f.mine` did not exist**, and `core.pagination.parse_list_params` **drops an undeclared filter silently** (*"undeclared filter names are ignored"*), so the endpoint answered 3·1 — the SUPERVISOR's list of everyone's tills — and `per: 1` made the wrong row arrive faster. ⚠ **The row carries `owner_name` and no owner id, deliberately (B14 rule 31), so the client could only match a person by their DISPLAYED NAME — and a name is not an identity.** Now narrowed server-side from `core_audit.actor_user_id`; an unresolvable caller gets the EMPTY set, never everything. ⚠ **The silent drop is the root cause and is fixed on THIS endpoint only** — making `parse_list_params` refuse globally would change dozens of lists on one screen's authority, so it is `DEF-PAY-6246` instead. |

### Explicitly NOT to be built

| | Why |
|---|---|
| A midnight auto-close job | §3.1 — the PO struck it |
| The *auto-close* half of `Counter setup` | §3.1 — `Counter setup` ships with the float alone |
| A fourth `close_kind` (`declared`) | §3.2 — rejected; `close_kind` stays at three |
| Changing a forced close to `counted` on declare | §3.2 — rejected; it erases who counted what |
| `counter_session_id` as `NOT NULL` | §3.4 — it would refuse every ACH, card, wire and lockbox row |
| A silent exception for mailed cheques | §3.4 — not decided; raise it as a question |

---

## 5 · Where things already are

| | |
|---|---|
| `counter_sessions` table | **Exists** — `payments/0031` creates it, `0032` gives it RLS. Written by nothing yet |
| `close_kind` values | `counted` · `forced` · `system` (`payments/models.py`) |
| `ck_counter_sessions_closed_together` | Three closing facts move together; widened in phase 0 for the system till |
| `uq_counter_sessions_open_owner` | Partial unique — refuses a second OPEN till per person |
| The system till | One per tenant per banking day, **born closed**, no owner, no centre, no closer — for ACH, card, wire, lockbox (`reconciliation.py`) |
| Deposit batch key | `UNIQUE (tenant, session, method)` where session is not null (`payments/0033`) — **one batch per till per tender** |
| Batch numbering | `DEP-{YY}-{0000}` on Settings → Numbering, like every other series |
| `payments.origin` | `entry` · `webhook` · `import`, write-once at creation |
| The seven tenders | `ach` · `card` · `check` · `cash` · `lockbox` · `wire` · `money_order` |
| The tabs | `PAYMENTS_TABS` in `07-frontend/src/features/payments/paymentsShared.tsx`; `counter` is still in `PAYMENTS_TABS_AWAITING_A_SCREEN` → `P2-counter`. **`P2.6` is what takes it off that list** |

---

## 6 · Process

Every lane follows `04-docs/02-decisions/12-engineering-plan.md` Addendum r11 —
step 0 check the packet is current · 1 packet · 2 build (backend · **front end**
· tests · prove it) · W write back as you go · 3 self-verify · 4 close the
record · 5 human review · 6 merge. **Step 7 of the change process is the
version bump** — `10-scripts/allocate.py version --bump change`.

**Law 11 applies to every push**: pin the tip once, re-derive every blob from
it, push through `10-scripts/push_paths.sh`, and read the numstat as
arithmetic. **Law 12 applies to every session start**:
`./10-scripts/check_head_current.sh` before reading a file or believing a grep.

---

## 7 · Dispatch log — who is building what

**Wave 1 dispatched 2026-09-23 from tip `d20e52f64`**, six lanes, each in its own
`git worktree` (hard-won law 12's cheapest mitigation — two lanes that did this
on 2026-08-28 lost nothing to a rewind that reverted 152 files of the shared
tree). **Each lane updates its own rows in §4 and pushes through
`10-scripts/push_paths.sh`.**

| Lane | Tasks | What it owns |
|---|---|---|
| **P2-DB** | `P2.4` · `P2.5` · `P2.20` | the columns, the index, the declare constraint |
| **P2-LEDGER** | `P2.21` | `6850 Cash over and short` in `ledger/chart.py` |
| **P2-SCREENS** | `P2.6` | the six Counter screens, built from the drawing as images (p51–59) |
| **P2-HEAD** | `P2.7` · `P2.8` · `P2.9` | `Start counter →` everywhere, Source + Batch on 2·1, the banner on 2·3a |
| **P2-API** | `P2.1` · `P2.2` · `P2.3` · `P2.22` · `P2.23` | the endpoints, the over/short posting, the no-till refusal |
| **P2-WIRE** | `P2.10` · `P2.11` | Finance picks up the batch, the unclosed-till notice |

**Wave 2 — DISPATCHED AND LANDED 2026-09-23.** ⚠ **THIS PARAGRAPH READ *"NOT YET
DISPATCHED"* UNTIL `437f70f08`, WHICH IS THE FAILURE `CLAUDE.md` NAMES BY ITS
SHAPE:** §4 is the authority and it said `DONE`, while this dispatch log went on
telling a reader the work was waiting. **A status is edited and the BODY — where
the instructions live — rots silently**, and the body is what a lane reads.

Seven of the eight landed together in `437f70f08` (LANE P2-TESTS: `P2.12`,
`P2.14`–`P2.19`); `P2.13` landed earlier with LANE P2-TILLWIRE.

| Tasks | What they waited for, and what they found |
|---|---|
| `P2.12`–`P2.16` (five tests) | each asserts an endpoint or a control wave 1 was writing. ⚠ **`P2.15` FLIPS — see §3.3.** A non-zero difference now DOES post, and the drawing's *"closing writes no journal line"* is superseded. **Two defects came out of writing them — `DEF-PAY-6262` and `DEF-PAY-6263`, both set out in §10** |
| `P2.17`–`P2.19` (three journeys) | `J-PAY-counter-shift` walks the whole phase end to end, every figure **measured** by `10-scripts/cr136_p2_17_counter_shift_readback.py` on PostgreSQL 16.13; `J-PAY-forgotten-till` is **rewritten by §3.1** (System Admin force-closes, no midnight auto-close); `J19-month-end-close` is a regression because phase 0 changed the batching rule underneath it |

⚠ **AND THE TWO JOURNEYS WERE AMENDED AGAIN THE SAME DAY, BECAUSE `P2.10` AND
`P2.11` LANDED UNDER THEM (`7611d80d2`).** Both files named those tasks as
`NOT STARTED` gaps — true when written, false two commits later, and a journey
is read as a specification. That is the same rot this paragraph is an apology
for, caught once by its own author rather than twice by somebody else.

### What lane P2-HEAD adds, having arrived at `P2.7`/`P2.9` after they landed

`P2.7` and `P2.9` were built by LANE P2-SCREENS in `f77dca804` while this lane
was building the same two, and theirs is the one that ships — a second
component doing one job is what B14 rule 43 exists to stop. Three things came
out of reading theirs against this lane's, and all three are fixes to THEIR
component rather than a rival to it:

1. ⛔ **`DEF-PAY-6235` — `useMyOpenCounter` reads `rows[0]` off the
   SUPERVISOR'S list of everyone's tills.** `f.mine=1` is a filter `P2.3` has
   not built and **`BE-05` drops an undeclared filter silently**, so the day
   `GET /counters` is served without that name the page head announces a
   colleague's drawer as **Your counter**, beside a button that takes money.
   The read succeeds, both states render correctly, `per: 1` makes the wrong
   row arrive faster, and nothing goes red. The caller is now matched on
   `owner_name` in the hook as well: with `f.mine` that is a no-op, without it
   it IS the filter. **`P2-API`: if `GET /counters` grows no `f.mine`, say so
   and the client match stays the only narrowing.**
2. ⛔ **`DEF-PAY-6237` — *every payments screen* missed the seventh.** The
   collections ladder (7·3a) is a static route drawing the same seven-tab strip
   with Debtors selected, so `PaymentsPage`'s head does not reach it. It now
   mounts `CounterHeadSlot`.
3. **A flicker in the same hook**: a DISABLED React Query is `pending` with
   `fetchStatus: idle`, so once the read waits on `/me` its own `isLoading` is
   FALSE while the session read is going. `isLoading` now covers both.

⚠ **AND THE BLUEPRINT CONFLATES A COUNTER'S CODE AND ITS BATCH'S.** p030 prints
`CTR-260921-DW` in 2·1's BATCH column and p037 prints the same string in 2·3a's
banner, as though a till had one batch. §5's own key —
`UNIQUE (tenant, session, method)` — gives it **one per TENDER**, so up to
seven, and before a clerk picks a tender there is no single batch code to name.
Two facts, one drawn string; worth knowing before `DEF-PAY-6228` is built.

⚠ **A NOTE FOR WHOEVER PICKS THIS UP: FIVE LANES CONTRADICTED THE DISPATCHING
BRIEFINGS ACROSS PHASES 0 AND 1, AND EVERY ONE OF THEM WAS RIGHT.** Each lane
above was told so, and told to report a briefing it disproves rather than build
to it. **Read their reports as findings, not as status**, and expect some of §4
and §5 of this file to be corrected by them.

---

## 8 · What LANE P2-DB found that this file did not say

Three things, recorded here because the next lane reads the repo and not a
report (hard-won law 10).

1. **The blueprint's reason for `P2.4`'s shape is wrong, twice over**
   (`DEF-PAY-6219`). The shape was built as drawn; only the justification is
   false. It matters because the next lane to touch that column would inherit
   the wrong reason and could not weigh it.
2. **Phase 2 has no reversibility proof and phase 0's guard cannot see one**
   (`DEF-PAY-6220`). `test_p0_16_every_phase_0_migration_is_in_the_
   reversibility_proof` globs `cr135` filenames, so it is true of phase 0 for
   ever and silent about every `cr136` migration. `payments/0035` was proved
   forwards, backwards and forwards again **by hand**, with the definitions read
   back from `pg_get_constraintdef` and `pg_indexes` rather than inferred. That
   covers one migration; six lanes are landing them.
3. **The four PO rulings of 2026-09-23 never reached the payments module's
   business rules** (`DEF-PAY-6221`). `04-docs/05-modules/08-payments/
   02-business-rules.md` contains **zero** occurrences of that date, and
   `BR-PAY-1160` still reads `CONFIRMED 2026-09-22`. The decision log and §3 of
   this file carry all four verbatim, so nothing is lost — but the module's own
   rule file is where a lane looks. **Whoever builds `P2.2`, `P2.22` and `P2.23`
   should amend `BR-PAY-1160` and mint the new rows in the same commit as the
   code**, which is the fan-out `CLAUDE.md` already requires of a closed
   question.

⚠ **AND ONE THING THIS LANE DELIBERATELY DID NOT DO: mint a version.** Nothing
in `payments/0035` changes what a user can see or do — three columns and an
index that no code writes and no screen reads. `G35` clause 4 would require a
`CHANGELOG.md` entry saying so, and a bump is four shared files while six lanes
run. The reasoning is written out in the human-review ledger row.

---

## 9 · What `P2.21` found, for the lanes that come after it

**Written here rather than only in the ledger module, because `P2.22` reads this
file and would otherwise rediscover all three.**

**(a) `6850` WAS FREE AND IT IS NOW TAKEN.** Counted mechanically across all six
seed tuples in `chart.py` rather than grepped: **128 rows before this change,
129 after, every code unique in both**, and exactly three `6xxx` codes before it
(`6800 Bank fees`, `6900 Bad debt`, `6950 Deposit interest expense`). The chart
a tenant is **provisioned** with is **128 accounts**, was 127 — the difference
is `1290 Allowance for doubtful accounts`, which is minted only when a tenant
switches that policy on. ⚠ **A TENANT'S OWN CHART CAN STILL
COLLIDE**: `_create_missing_accounts` skips a code the tenant already holds, so
a utility that hand-added its own `6850` keeps it and `cash_over_short` resolves
to **nothing** for them. `ensure_cash_over_short_account` returns **`None`** in
that case, deliberately — **`P2.22` must refuse on `None` and never substitute
another account**, because hard rule 4 leaves nobody a way to move a journal
line afterwards.

**(b) HOW `P2.22` RESOLVES IT — read the bank-fee posting, it is the same
shape.** `apps/payments/ledger_seam.py` posts `DR _gl(GL_BANK_FEES) / CR
_gl(GL_CASH)` for a returned payment's fee, and `_gl(designation)` resolves
through `apps.ledger.selectors.gl_account_id_for_designation`, raising a NAMED
refusal when the pointer is missing rather than substituting. ⚠ **`GL_BANK_FEES`
is a plain string declared in `ledger_seam.py` and NOT an import of
`apps.ledger.chart`** — that file says why in its own words: *"payments carries
no import edge into ledger"*. So `P2.22` declares **`GL_CASH_OVER_SHORT =
"cash_over_short"`** beside the other six and posts it against the existing
`GL_UNDEPOSITED`. Call
`apps.ledger.services.ensure_cash_over_short_account(actor)` at the top of the
posting first, exactly as the allowance estimate calls its own top-up: **a
posting that refuses because a pointer is missing is a posting a clerk cannot
fix from the screen they are on**, and that screen is the one where they have
just counted a bag of cash.

**(c) ⚠ EXISTING TENANTS *DO* GET A NEW CHART ACCOUNT, AND THREE LEDGER
DOCSTRINGS SAID THEY DO NOT (`DEF-LED-6223`).** The briefing for this task
expected the answer to be *"it does not"*. It is not: `tenancy.services.
seed_reference_data_for_tenant` calls `ledger.services.seed_chart_of_accounts`
**unconditionally** (CR-066 task A3), and `tenancy.reference_sweep.sweep()` runs
that door over `Tenant.objects.all()` from `06-backend/docker-entrypoint.sh`
after every `migrate` (OQ-087, CLOSED 2026-08-10, *"automatic post-migrate,
across all tenants"*). `_create_missing_accounts` is insert-missing, so the
sweep plants `6850` on every live beta tenant at the next deploy and touches
nothing they have renumbered, renamed or retired. **It is proved by a test that
walks the real door** rather than asserted in prose —
`test_cr136_p221__an_existing_tenant_gets_it_from_the_post_migrate_sweep` — so
if somebody later moves the chart top-up behind `structural_only`, it goes red
and names the consequence. **No backfill migration was written**, and one would
have been a second mechanism for a job two paths already do.

**(d) ⚠ THE COMMIT THAT CARRIES `P2.21` HAS ANOTHER LANE'S MESSAGE ON IT, AND
THE WORK IS ALL THERE (`DEF-GOV-6225`).** `c38878404` holds exactly this lane's
twelve paths and nothing else — its parent is the tip this lane pinned and its
numstat shows only this lane's own insertions — but its SUBJECT reads *"A till
can be opened, filled, sealed and counted"*, which is `LANE P2-API`'s. **The
session scratchpad is shared between every lane**, `10-scripts/push_paths.sh`
reads its message from a file the caller names, and P2-API wrote its own message
to `scratchpad/msg.txt` in the seconds between this lane writing that file and
the push reading it. **No content was lost by either lane** and P2-API's files
were never touched — only the text of one commit. It is recorded here because
`git log` is the first place somebody will look for `P2.21` and it will say the
wrong thing; the amendment of record is this row and the `DONE c38878404` above.
**Every check hard-won law 11 prescribes passed on it**, because all of them read
the commit's CONTENT and none of them reads its MESSAGE.

---

## 10 · What LANE P2-TESTS found, for the lanes that come after it

Written here rather than only in a report, because the next agent reads the repo
(hard-won law 10). Five things, and the first two are defects.

**(a) ⛔ `DEF-PAY-6262` — A GENUINE RACE ON *Start counter* REACHES THE CLERK AS
A 500.** `open_counter`'s docstring says its `SELECT … then INSERT` *"exists so
the loser reads a sentence naming their open till instead of a constraint
name"*. Measured on PostgreSQL 16.13 with two threads: the loser receives
`django.db.utils.IntegrityError: duplicate key value violates unique constraint
"uq_counter_sessions_open_owner"`, and `counters_api` catches only
`PaymentRuleError`, so nothing translates it. **The escape is worth more than the
bug:** part A of the proof races two raw `INSERT`s, so it proves the INDEX and
never reaches the service; every service-level case is SEQUENTIAL, where the
`SELECT` does see the first till and the readable refusal is produced perfectly.
**The one path that produces the raw error is the one path nothing ran.** The
money is not at risk — part A3-2 measures **one till and one batch** after the
race, so the atomic block holds — and the fix is a `try/except IntegrityError`
inside `open_counter` that re-raises the same refusal **without re-querying**,
because the transaction is poisoned and no further statement may run (law 14).

**(b) ⛔ `DEF-PAY-6263` — `CounterDoors.tsx` NAMED A TEST FILE THAT DID NOT
EXIST.** Its Trace header has read `Tests: src/features/payments/
counterDoors.dom.test.tsx` since `f77dca804`. Nothing in this repository reads a
Trace header's `Tests:` line and asks whether the path is there, so the claim
reads in review exactly like a true one — hard-won law 1. The file exists now and
is `P2.16`. **The general form is mechanically checkable and nothing checks it.**

**(c) THE OVER HAD NEVER BEEN TESTED AND THE PROOF IS WORTH REPEATING.**
Inverting one line of `ledger_seam.post_counter_difference` — `over = difference
> ZERO` — turns every drawer difference in the product upside down. Before this
lane, `test_p2_22_a_short_drawer_posts_a_balanced_pair` stayed **GREEN** on that
product, because it only ever counts a short. **A pair of directions needs a pair
of cases**, and the sign is expressed in exactly one place.

**(d) `api_call` LEAVES THE TENANT CONTEXT UNSET, AND THE FAILURE POINTS
SOMEWHERE ELSE.** `core.tenancy.tenant_context` CLEARS on exit rather than
restoring what it replaced — correct for a background job, which must never
carry one tenant into the next loop iteration. So a test that wraps endpoint
calls and ORM reads in one outer `with tenant_ctx(...)` loses its tenant at the
FIRST endpoint, and every later statement refuses with **`AUTH-003
BR-TEN-003`** raised from `counters._tenant_id` — which reads like a product
bug in the service under test. Re-enter the context per step. Two further traps
in the same harness, both recorded in the test file: `identity.User` has no
`is_authenticated` (⇒ 403 before the view is entered) and `@require_role` reads
`actor.role` off `request.user`, so the signed-in namespace needs **both**.

**(e) A JOURNEY FIXTURE MUST BE TWO DECIMAL PLACES.** `BR-LED-025` (PO
2026-08-12, *"Refuse and make the caller round"*) makes the ledger refuse a
posting carrying more, **and it refuses the whole payment with it**. A first
draft of `P2.17`'s walk used `$160.5750` a cheque to reach the drawn
`$1,284.60`; `record_payment` raised on the first cheque. Eight cheques of
`$160.58` and one of `$160.54` reach the same total and can actually be taken.
The product was right; the fixture was not.

⚠ **AND ONE THING THIS LANE DID NOT DO: FIX `DEF-PAY-6262`.** The repair is small
and it changes what a clerk is TOLD on a money path, which is `P2-API`'s to
decide — the refusal cannot name the other till's opening date on that path, so
the sentence has to lose a clause. Filed rather than taken quietly.
