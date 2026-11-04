# CR-126-BRC07 — New Connect is built to its drawing: the create wizard corrected, and the Build tab made into the complete build record

**Raised** 2026-09-21 by the Product Owner, in the working chat session.
**Branch block** `CR-125`–`CR-129`, suffix `BRC07`. The block was claimed for
`claude/kind-wozniak-rl0uzt`; that branch's 58 commits were merged into
**`claude/laughing-thompson-kpmwih`** on 2026-09-21 (merge `fd4a66fa4`), which is where
this CR and its lanes now live. **The suffix is PROVENANCE, not the thing that makes the
number unique** — `CR-126` was verified free against the REMOTE with
`10-scripts/allocate.py cr` at the moment it was taken, and is re-verified at push time.
`CR-127`–`CR-129` remain free.

**Version** `2.321.0` (`10-scripts/allocate.py version --bump change`), to be written in
`07-frontend/package.json`, `07-frontend/package-lock.json` and `06-backend/pyproject.toml`
when the last lane lands. Step 7 is the step usually skipped; it is not skipped here.

---

## ⛔ CORRECTION, 2026-09-20 — THIS CR NAMED AN ADDRESS A PO RULING HAD CLOSED 38 MINUTES EARLIER (`DEF-GOV-6054`)

**Read this before anything below it.** As first written, §3's impact table said the work
was *"a build record page that does not exist yet, at
`/{tenant}/connections/{connection_no}?tab=overview`, with six tabs"*, and §1 said the
application separation was *"the only"* change here. **Both cannot be true**, and the
second is the one that gave it away: putting a screen at that address REVERSES a ruling,
and this file reversed it **by assumption**, which `13-change-process.md` step 2 and
CLAUDE.md law 13 both forbid — *the supersession must be stated, never assumed*.

**WHAT WAS ACTUALLY RULED.** `5495a5978`, `2026-09-20 18:25:47 +0000`, closing
`OQ-MET-12520`. Three options were put with a real case and **the PO chose C**, in their
own words:

> *"C. Your ruling's words were 'you cannot have two different screen' — that's about
> duplication, not about the content. The drawing isn't asking for a duplicate; it's
> asking for completeness we don't have. C gives you both: nothing duplicated, and the
> clerk stops hopping three places."*

**So, and this governs every section below:**

* ⛔ **NO second screen at its own `/connections/…` address.** No route, no `SCREEN_ROUTES`
  row, no `NCT-02` badge. That address is **not vacant**: `App.tsx:1079` routes
  `/connections/:connectionId` to `BuildRedirect`, the doorway built in `CR-070` wave O
  when `ConnectionDetailPage.tsx` was **DELETED** under the 2026-09-04 ruling, and kept
  alive for every bookmark from the three weeks it was live. Building there re-creates a
  screen this product already deleted once.
* ✅ **The property's Build tab becomes the complete build record**, and what the six drawn
  tabs carry lands there **AS SECTIONS**.
* ✅ **Blueprint p100–p107 remain the CONTENT contract in full** — every element this CR
  lists is still what to build. **Only the ADDRESS and the TAB STRIP are superseded.**

**HOW IT IS BUILT, SO THE REMAINING QUESTION COSTS ALMOST NOTHING.** `B14` rule 43 was
ratified the same day — *a piece of UI is built as a COMPONENT; standalone code inside a
page is not reuse*. The header facts, the five tiles, the blocking banner and the four
Overview sections are therefore **components taking their data as props**, mounted on the
Build tab. If the mount point ever moves, a route and three tests move with it and
nothing is rebuilt.

⚠ **AND ONE THING IS GENUINELY UNSETTLED, SO IT IS WRITTEN HERE RATHER THAN DECIDED HERE.**
At **19:02 UTC — 37 minutes AFTER that ruling**, the PO clicked `CON-26-0128` in a browser,
landed on the premises record titled *240 Sable Court*, and said: *"it show premsies - it
should show new connect detail page"*. The timeline was verified against the commit clocks
and their taskbar, not assumed — **an earlier reading that made the complaint the ruling's
INPUT was wrong.** It does not reverse option C on its own: what they saw was a Build tab
carrying a seven-fact strip and eight buttons, which is precisely the incompleteness option
C exists to cure. But two statements by the same person 37 minutes apart pointing different
ways is the ONE category CLAUDE.md law 13 sends back — *a ruling that collides with a signed
rule*. It is put to the PO in plain sentences with the real case; **until it is answered the
build proceeds as option C**, because that is what is ruled.

**`DEF-CUS-6049` WAS FILED ON THE WRONG DIAGNOSIS AND IS CORRECTED, NOT WITHDRAWN.** The
link is not pointing at the wrong place — `buildHomePath` sending a clerk to the premises'
Build tab is right under this ruling, and its three tests stay as they are for now. **The
defect is that the Build tab is not the build record**, which is the same work this CR
already carries.


---

## 0 · CAPTURE — the requester's words, verbatim

Six messages, in order, none paraphrased.

> *"i want you to do similar excercise for new connect - we have updated drawring in
> blueprint for new conenct. do the mapping and start tasks for Create new Connect +
> Actions, list view, detaisl view + actions"*

> *"no - we are keeping application process and new connect process seperate - applciation
> is submitted - reviewed and approved or rejected - once that is doen application life is
> completed. then approve applciation may create a new conenct request - as draft request -
> this request is new work and recognized seperately from applcaition and hence we should
> not make it dependent on applciation #"*

> *"you can generate meter, sub meter or asset # and assigned it - buttheya re not yet
> installed or actiavted"*

> *"install date on work order completion - yes, start the work"*

> *"Header (p100) - this is correct +actions ; this is coorect - Overview — tiles (p100) +
> Overview — Live state … + Actions (p105–107) - actions are correct - can you start the
> build for New COnnect request detail view"*

> *"build new connect request creet and detial view using images of drawing not text; use
> UI genration skills - this is important"*

Two further one-line rulings arrived in the same sitting and are carried in §4:
*"we ahe to say activate"* and *"here filter only active Utility services for that Tenant"*.

**The scope is a measured table, not a description.** Every step of the wizard and every
section, data element and action of the record page was mapped against the drawing and
against the code, and the PO confirmed it **section by section** on 2026-09-21 — the
header and its three buttons, the five tiles, all four Overview sections, all six tabs and
all the actions. That table is `12-governance/28-new-connect-measured-2026-09-21.md`.

---

## 1 · CLASSIFY — one CHANGE, and a large DEFECT set in one container

**The application/new-connect separation is a CHANGE**, and the only one here. It reverses
a design that is already built: the wizard's pricing path leans on an application, and the
PO has ruled the two processes independent. See §2.

**Everything else is DEFECT repair.** `B14` rule 41 already says the product UI matches the
blueprint exactly, and `DEF-GOV-5248` already gives the blueprint layout, copy, **flows**
and states for any module that has one. A screen that does not match a drawing it was
supposed to match is the product not doing what it was promised to do — **a defect by the
beta's own routing rule** (PO 2026-09-10: *"CR is change in product, defect is product does
not do what is expected"*). This file is the container, not a re-classification.

⚠ **AND THE RECORD PAGE IS THE REDESIGN CASE THE MAINTENANCE PROCESS NAMES ON PURPOSE.**
`12-governance/22-product-maintenance-process.md` says a live screen redrawn end to end is
MAINTENANCE, borrowing exactly one thing from Build — the drawing step — and that a lane
following Build loses reproduce, blast radius, regression and the reporter. ⚠ **BUT THE
BUILD RECORD PAGE IS NOT A REDESIGN: IT DOES NOT EXIST.** No route, no component, no
registry entry. *Can a user do this task in the product today?* **No** — so the record page
is BUILD (`r11`), while the create-wizard corrections are MAINTENANCE. Both are in this
CR; the lanes are told which process they are in.

---

## 2 · WHAT SIGNED STATEMENT IS BEING REVERSED

**Nothing frozen. No ❄️ B4/B5 money figure is touched**, so no finance re-sign is required.

**One built design is superseded, and it is named rather than assumed.** The wizard today
treats the application as the thing a build hangs from: a build made through it **cannot
raise a charge at all**, because the pricing path expects an application to have carried
one. The PO's ruling makes the two independent — *"we should not make it dependent on
applciation #"* — so:

* `request_id` becomes **provenance only**: carried, shown as *where this came from*, never
  required and never a dependency;
* a build raised directly, with no application behind it, **must price itself and raise its
  own charges**;
* an approved application **may** create a new-connect request as a DRAFT, and the
  application's life ends there.

⚠ **THIS REVERSES CODE THAT IS ALREADY SHIPPED, WHICH IS WHY IT IS A CHANGE AND NOT A
DEFECT.** The rule goes into the customers module's business rules marked SUPERSEDED with
its date, and the ruling verbatim into `12-governance/02-decision-log.md`, in the commit
that builds it — not after.

A second built behaviour is superseded by the asset ruling: **`install_date` is written on
WORK ORDER COMPLETION**, not at commit. Today it was measured defaulting to *today* at
creation, so every build through the wizard has been recording an install that has not
happened. Asset numbers themselves ARE generated at commit — the PO is explicit — they are
simply not installed and not activated.

---

## 3 · IMPACT

| Surface | What moves |
|---|---|
| Screens | the create wizard's steps 1, 2, 4, 6 and 8; **the property's Build tab made into the complete build record** — the drawn header facts, five tiles, blocking banner and four Overview sections, plus what the other five drawn tabs carry, all AS SECTIONS and all as components (rule 43). ⛔ No `/connections/` route — see the correction at the top |
| API | one record read serving every drawn element; the 8 connection endpoints with no door; a pricing path that no longer requires an application |
| Schema | `owner_type`, `prefix`, `scope` have **no column** on the build; *Approved by* and *Activated at* have **no source anywhere**; nothing records what has been **settled** against a quote |
| Rules | the application-dependency rule (§2) · `install_date` timing · *activate*, never *energise* |
| Open questions | `OQ-1360` (the going-live customer's own fire list) is untouched. The service-list question is CLOSED by *"filter only active Utility services for that Tenant"* |
| Demo fixture | a build with a gate work order outstanding, so the greyed `Activate units` button has something true to be greyed about |
| Locale | thirteen catalogues, through `10-scripts/i18n_fanin.py` — **and the fan-in is refusing today** on a pre-existing parity gap (id-ID, ja-JP, ko-KR hold 18,759 keys; the other ten hold 18,760). That blocks every lane and is fixed first |
| Governance | this file · the decision log · the customers business rules · the human-review ledger row for the migration · `12-governance/28-new-connect-measured-2026-09-21.md` |

---

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

**The create wizard, in five places:**

1. **Step 1 takes no documents.** PO: *"you ahve to take documents - rest is all good"*. A
   reusable document-storage component was built earlier in the same session precisely so
   it could be used here — PO: *"document sotrage - we need to make it compoentn so thatw e
   cna use it in other palces also"*. It is REUSED, never rewritten.
2. **Step 4 offers eleven services to a utility that sells two.** `newConnectShared.tsx`
   exports `TEN_SERVICES`, a hand-typed list — **the third in the front end**. CLAUDE.md
   hard-won law 2 records exactly what these cost: an eleventh service does not appear on
   screen on its own and it **fails silently**, with the row present, the API serving it,
   and `tsc` and every test green.
3. **Step 2 silently loses a picked address's service list.**
4. **Step 6 can never raise a charge** — §2.
5. **Step 8 says *energise*.** PO: *"we ahe to say activate"*. `NewConnectReviewStep.tsx`
   reads `whatEn: "Units energise one at a time"`, the missed instance of an earlier
   change request.

**The record page: it does not exist.** Every element the drawing shows is measured today
against the property's Build tab, its Work orders tab and the account — three places for
one subject, which is what the PO's *"you cannot have two different screen"* ruling
forbids. **Backend is far ahead of the front end**: of the drawn elements missing from the
screen, more than half are **already served** — the connection number, the originating
request, the plan block, the payer, the created date. That is a rendering gap, not a data
gap, and it is why the front-end lanes outnumber the backend one.

**Lanes building right now** are dispatched from `fd4a66fa4`, each in its own
`git worktree`, and each is told which files it owns so no two write the same file.

---

## 5 · SIZE, IN PLAIN ENGLISH WITH A FIGURE

Seven lanes. A Build tab carrying seven facts and eight buttons becomes the complete build
record — **five tiles, four
Overview sections totalling 25 rows, and three header buttons**. Five wizard corrections.
One migration on a 🔒 sensitive path, flagged `HUMAN-REVIEW-PENDING` with its ledger row.
**Three drawn facts have no source anywhere** — the customer-class chip, *Approved by* and
*Activated at* — plus five *Owner & scope* fields with no column, and those five are the
same fields the wizard already collects and discards, **so one fix serves both ends**.

No fast path: this touches a money rule (§2) and it touches data.

---

## 6 · EXECUTE — through `r11`, with two rulings that override the usual method

**Build from the drawing AS AN IMAGE.** PO, verbatim: *"build new connect request creet and
detial view using images of drawing not text; use UI genration skills - this is
important"*. That is `B14` rule 42 restated by the person who ratified it. Every lane
renders its pages with `10-scripts/pdf/pdf_render.py` from
`05-prototype/02 Accounts Menu Blueprint.pdf` and **reads the PNG**; extracted text is an
index for finding a page, never the specification.

**Use the UI generation skill** — `react-tailwind-css-ui-generator` — before writing TSX.

Pages: **p92–p99** the create wizard · **p100–p104** the record's content, which becomes
the Build tab's sections ·
**p105–p107** the actions.

⚠ **EVERY FIGURE DRAWN IS AN ILLUSTRATION, NEVER A FACT TO BUILD TO** (`B14` rule 37).
Shape and labels from the drawing; numbers from the API.

⚠ **ONE PLACE THE RULING BEATS THE DRAWING:** the blocking banner on p100 reads *"four
units cannot **energise** until it passes"*. Our copy says **activate**, everywhere.

**The greyed `Activate units` button is the trap this repo already paid for.** CLAUDE.md
hard-won law 2's mirror — a live screen behind a dead control — cost eight doors on the
customer portal this month. So a control shipped disabled carries **the test that fires
when the hold expires, in the same commit**, asserting the destination by ADDRESS and by
screen id.

---

## 7 · VERSION

`2.321.0`, written in all three files when the last lane lands, and re-verified with
`allocate.py version --verify` at that moment because two lanes shipping the same version
has already happened once (`DEF-GOV-3756`).

---

## 8 · CLOSE, AND THE ROLLBACK STATED BEFORE SHIPPING

**Rollback** is per lane, because they land separately:
* the wizard corrections revert as ordinary front-end commits;
* the record page is a NEW route — reverting it removes a door and takes nothing away,
  because nothing pointed at it before;
* **the migration is the one that needs thought.** It reverses, and reversing DESTROYS the
  *Owner & scope*, *Approved by* and *Activated at* values captured after it ran. That is
  stated here rather than discovered: a reverse on a database that has taken real builds is
  not a clean undo.

**The reporter is told which build to look in** — the maintenance process's closing step,
and the reason it exists is that a tester who reports three things and hears nothing stops
reporting.

---

## 9 · THE ACCEPTANCE WALK — WHAT "DONE" MEANS, IN THE PO'S OWN WORDS

**PO, verbatim, 2026-09-20, given while the lanes were running:**

> *"when new connect build complete - can you to end to end web walk - create a new
> conenct request - take variations of all kind - do ultiple request submission check
> whther clark is able to create these request with ease. then also try to create the new
> conenct request from servcie requesta nd see whether it is working. then complete the
> new connect request - see at submit does it create premsies, units, services, plan and
> asete and account of owner a smaster account , money handling, audit handling, documents
> are stored etc - then whether request is available in the list view - you can search,
> filter etc"*

⚠ **THIS IS NOT A TEST SUITE AND MUST NOT BE SATISFIED BY ONE.** It is walked **in a
browser**, against a running product, because **no gate in this repo reads rendered
output** (CLAUDE.md hard-won law 6) and nine defects were once found this way and by
nothing else. A green suite is not an answer to any line below.

**Part 1 — RAISE, MANY TIMES AND IN VARIETY.** Not one happy path: a single house, a
seven-unit apartment block, a build with one service and a build with several, a developer
and a private owner, a picked existing address and a new one, with documents and without.
**And the question being asked is not "does it submit" — it is whether a clerk can do this
with EASE**, several times in a row. Count the presses, name every place the wizard makes
them type something it already knows, and say where it made them stop and think.

**Part 2 — RAISE IT FROM A SERVICE REQUEST.** An approved application creating a new
connect as a DRAFT. ⚠ **This is the path the PO ruled on this day** — the application's
life ENDS there, and the build is separate work that prices itself. Walk it and prove the
draft is not dependent on the application.

**Part 3 — COMPLETE IT, AND CHECK WHAT IT LEFT BEHIND.** At submit, each of these is a
separate yes or no, checked in the database and on the screen, never inferred from a
success message:

* the **premises** exists · the **units** exist and inherit the premises' services
* the **services** are attached · the **plan** is assigned
* the **assets** — meter, sub-meter, asset numbers GENERATED and assigned, and **not
  installed and not activated** (PO ruling 2026-09-21), with `install_date` written
  **on work-order completion** and not at commit
* an **account** exists with the **owner as its master account**
* **money handling** — the charges raised, the quote total, what is settled, every figure
  4dp stored and 2dp displayed
* **audit handling** — `audit_log` written for every money action (hard rule 7)
* **documents** — the files taken at step 1 actually stored and readable afterwards

**Part 4 — FIND IT AGAIN.** The build appears in the list view; search finds it by
connection number, premise, address, applicant and request number; the filters narrow it;
the column selector works. ⚠ **`NFR-3`** — the list is server-paginated.

**Reporting:** every failure gets a defect row **before it is fixed** (step W), and the
walk is reported in plain sentences with figures — how many builds raised, how many
presses, what was missing — not as a pass/fail table.

### 9.1 · WHAT THE EASE HALF OF §9 COST, AND WHAT IT COSTS NOW (lane EASE-1, 2026-09-21)

§9's question is *"check whther clark is able to create these request with ease"*, and
that is the half a pass/fail table cannot answer. Measured in Chromium on an isolated
clone at `v2.322.0`, before and after, by the walk itself:

| the build | presses before | presses after | characters |
|---|---|---|---|
| three units at an address already on file (`w5`) | **24** | **23** | 67 → 67 |
| a single house with a connection fee (`w7`) | 32 | 32 | 94 → 94 |
| a seven-unit block with a document (`w3`) | 33 | 33 | 122 → 122 |
| a seven-unit block, a per-unit charge and a document (`w8`) | **38** | **38** | 124 → 124 |

**So the range is 24–38 → 23–38 presses and 67–124 characters unchanged, and not one
change anywhere adds a press.** The press count is the floor a clerk cannot go below, and
two of the eight defects do not appear in it at all — which is the point worth reading:

* **Sixteen date boxes came off step 4 of a seven-unit block** (`step 4 grid: 16 asset
  cells · 16 size cells · 0 install-date cells`, where it read `16` install-date cells
  before). The walk never pressed them, so they never entered the count; a clerk looking
  at sixteen date pickers pre-filled with a plausible date does. Every one was discarded
  at the commit.
* **Step 6 went from *"0 money figures"* to *"$45.00 · $315.00"*** on the same build. No
  press moved; what moved is that the clerk can now see what they are about to charge
  somebody. The old path was *press Create, then read the invoice*.

**What the walk gained.** §9 part 4 — the list — was written into this section and walked
by nothing. `PART=list` now opens the New connects tab, reads every WORD in the filter
panel, ticks one, reads the address, reloads it and reads the row count again. It found
both list defects and it is what proves them fixed: *"every word in the filter panel is a
word, not a code"* and *"the filter survived a reload: 1 row(s) both times"*, against
`in_progress_draft · parked` and `1 row filtered, 11 after opening the same address`.

⚠ **AND ITS RAW-CODE DETECTOR TESTS CASE RATHER THAN UNDERSCORES**, because the first
version found `in_progress_draft` and reported `parked` as fine — a lowercase English word
sitting between `Draft`, `On hold` and `Activated`. Half a defect found is how a defect
survives being found.


### 9.2 · PARTS 1 AND 3, WALKED AGAIN AT `v2.322.0` (lane WALK-A, 2026-09-21)

Nine builds raised in Chromium on an isolated clone (`sbh_clone_walka`, dropped
afterwards), booted through `server.mjs` on its own port. **Eight committed and
one was refused correctly**, by the step-3 label check `DEF-MET-6111` added.

| the build | presses | characters |
|---|---|---|
| three units at an address already on file (`w5`) | **23** | 67 |
| a new service at an existing unit (`w6`) — refused at step 3, correctly | 23 | 67 |
| a single house, one service, no common area (`w4`) | 27 | 94 |
| a single house, both services, no common area (`w1`) | 28 | 94 |
| the same with a common area (`w2`) | 29 | 94 |
| a single house with the step-4 grid actually USED (`w9`) | 30 | 94 |
| a seven-unit block with a document (`w3`) | 33 | 122 |
| a single house with a connection fee (`w7`) | 33 | 96 |
| a seven-unit block, a per-unit charge and a document (`w8`) | **38** | 124 |

⚠ **THE COUNTS ABOVE LEAVE OUT STEP 2'S OPTIONAL *Premises name*, AND THEY DID SO
BY ACCIDENT BEFORE THEY DID SO ON PURPOSE.** The walk looked for `#nc_premises_name`
and the id is `#nc_premise_name`, singular — `page.$` returned null, the loop skipped
it without a word, and **every build this script has ever raised left `premises.name`
NULL**, which a part-3 readback then reports as a product finding. Fixed here, and
both spellings are tried so it cannot go quiet again if the id moves; typing it costs
one press and eleven characters (`w1`: 28 → 29, 94 → 105). The table keeps the
figures for a clerk who does not type it, because the field is optional and a single
house has no building name.

**So the range is 23–38 presses and 67–124 characters**, unchanged from §9.1 —
which is the point: nothing on this walk added a press, and the eight defects
below cost a clerk nothing in keystrokes. They cost them elsewhere.

**WHAT THE PRESS COUNT CANNOT SEE, AND IT IS MOST OF WHAT WAS FOUND.** Three of
the ten rows filed are controls a walk can press happily and a clerk cannot:

* **Twenty-two occupancy controls for seven facts** on the seven-unit block —
  seven on step 3, fourteen on step 4 (one per unit AND service, a fact a unit
  cannot have two of), and a build-wide radio on step 8. All write one key, so
  the water row silently moves the electric row (`DEF-CUS-6127`).
* **Sixteen asset-type pickers and sixteen size pickers that go nowhere.**
  `w9` exists to prove it: `Generator (customer premise)` and
  `Electric CT-metered` were picked through the screen, the commit answered 200,
  and the database holds `asset_type=meter, size_class=NULL` (`DEF-CUS-6122`).
  It is `DEF-CUS-6101`'s mechanism one field over, twice, and **it was invisible
  because every variation pressed straight through step 4.**
* **A plan that does not cover what the build sells.** Step 2 says
  *"WON'T COVER — the plan misses Water"* and lets the clerk past; five of the
  nine builds are in that state and no screen after step 2 mentions it again
  (`DEF-CUS-6131`).

#### Part 3 · the nine nouns, each asked of the database AND of a screen

Measured on `CON-26-0136` — a seven-unit block, developer, both services, a
per-unit connection fee, one document.

| what §9 asks | the database | the screen |
|---|---|---|
| the premises exists | `P-00085`, `1937 Walk Two W8 Lane, Austin TX 78704`, apartment complex, `services_available ["electric","water"]` | the premise header and the Build tab both show it |
| the units exist and inherit the premises' services | 8 rows — `1`–`7` plus `Common area` — each with **2 service points and 2 `connection_services`** | the record's units section has all 8; **the Build tab renders no units section** |
| the services are attached | `electric` ×8 and `water` ×8, all `pending` | both tags on the Build tab header |
| the plan is assigned | `IND` on all 7 dwellings, **none on the common area** (correct, PO 2026-09-16) | `plan: "Industrial"`, with no word about Water being uncovered |
| the assets | `M-00032`–`M-00047`, **16 numbers generated and assigned**, `status=inventory`, `install_date` NULL on every one — **the PO's 2026-09-21 ruling holds** | the asset register says `Inventory`; the build record publishes `status: null` and `size: null` |
| an account with the owner as master | `AC-2026-00058`, `kind=master`, customer *Walk2 w8 Developments LLC* | the account screen says **Master account** |
| money handling | quote `315.0000` stored / `315.00` displayed · bill `BL-2609-000094`, issued, one line `Connection fee 7 × 45.000000 = 315.000000` · taken `0.0000` · outstanding `315.0000` | the bill shows `$315.00`; **its Charges tab shows `Subtotal $0.00 · Tax $0.00 · Total $315.00`** (`DEF-BIL-6124`) |
| audit handling | `invoice.drafted`, `invoice.issued`, `journal.posted`, plus `premises.created`, `account.master_created`, `connection.committed` and 16 `asset.created` — **hard rule 7 holds on every money action** | the record's audit section has 4 rows; **the Build tab renders no audit section** |
| documents | `w8-proof.pdf`, `application/pdf`, **193 bytes, byte-identical** to what was attached, under the tenant's own storage prefix | the account's Documents tab lists it |

**Two of the nine are answerable only through the API.** `GET /connections/{id}/record`
serves six sections — units 8, charges 1, work orders 5, communication 7, audit
4, outstanding 0 — and `buildViews.tsx` reads `record.tiles` and never
`record.sections`, so the charges, the messages and the audit trail of a
committed build reach no screen at all (`DEF-MET-6125`).

**And the premise register does not know who owns the building.** `premises.owner_id`
is NULL on all five builds and on 80 of the tenant's 86 premises, so the
Overview reads *"Needs an owner · Nothing can be billed yet · Find an owner"*
four lines from a Build tab showing `OUTSTANDING 315.00` (`DEF-MET-6123`).

#### What the walk gained

`VARIATION=w9` uses step 4's grid instead of counting it, picking the **last**
option every control offers so a choice cannot be mistaken for a default;
`PART=record CONNO=<n>` runs parts 3 and 3b alone, so the two lanes walking §9
at once do not have to spend a service request to reach part 3; and part 3c
opens the three screens the build read cannot speak for — the premise register's
owner, the asset register's status words, and the bill behind `money.invoice_no`.
Each of the three found something.

### 9.3 · PARTS 2 AND 4, WALKED INDEPENDENTLY (lane WALK-B, 2026-09-21)

Walked in Chromium against the deployed join (`server.mjs`), on this lane's own clone
`sbh_clone_walkb` stamped `bc23a826e`, with the API on 8631 and the SPA on 8731 — no port
and no database shared with the lane walking parts 1 and 3. A sibling had built part 2 the
day before and reported it working, so nothing below is taken from that report.

**PART 2 — both address shapes reached a finished build, and the draft is independent of the
application.**

| what §9 claims | what the walk measured |
|---|---|
| approving raises a DRAFT and opens its wizard | `SR-26-0004` → `CON-26-0130` (no premises), `SR-26-0008` → `CON-26-0131` (on `P-00057`), both landing on `/connections/new?build=…` |
| the request names its own build | `outcome_ref` **compared** with the build: `CON-26-0130` and `CON-26-0131`, not merely non-empty |
| the wizard opens prefilled | **7 of step 1's 21 controls** already answered; step 2 on the applicant's own address |
| abandoning leaves a draft and **no property** | **79 premises · 131 units** before and after, builds 9 → 10 → 11 |
| finishing the resumed draft finishes THAT draft | builds **11 before the last press and 11 after**; premises 79 → 80, units 131 → 132; the commit answered `200` with the id it was given |
| a rule refusal reaches the clerk as words | duplicate unit label → `422`, **step 3**, *"A unit number here is taken. Change the unit numbers."* · uncountable charge → `422`, **step 6**, *"A charge here cannot be billed. Check the charges."* Both kept the footer and wrote nothing. |

⛔ **THE ONE THING THAT DOES NOT WORK IS GETTING BACK IN (`DEF-CUS-6132`).** The abandoned
draft is on the tab, reading `Draft`, naming its request — and where the address resolved its
number and its eye go to `/premises/<id>?tab=build`, whose `Edit details` is **disabled**
reading *"No edit path exists yet."*; where the address had **not** resolved the row carries
**no link at all**. The wizard is at `/connections/new?build=<id>` and nothing points there.
Everything after the abandon in this walk was reached by typing that address, which the
script says out loud because a clerk cannot.

**One thing the application holds and step 1 does not show:** the customer category
(`residential` on both requests). The applicant's name, email, phone and party kind all come
through.

**PART 4 — found again, and `NFR-3` proved rather than asserted.** §9.1 recorded that *"with
11 rows on file a second page cannot be walked in a browser today"*. **45 empty draft builds
were raised through the product's own `POST /connections`**, taking the list to 54:

* opening the tab asks the server `?page=1&per=50&sort=created&dir=desc` → **50 rows**;
* pressing `Next page` asks `?page=2&per=50&sort=created&dir=desc` → **4 rows**;
* **no row appears on both pages**, so the server sliced and the browser did not.

All five searches §9 names were typed into the box, all five reached the server as `?q=…`,
and all five returned the row they name: `CON-26-0129` → 1 · `P-00059` → 2 · `500 Main St` →
2 · `Ridge Property LLC` → 1 · `SR-26-0002` → 1. The filter narrowed 9 rows to 1, reached the
address and survived a reload; the column selector took `Actions` out (10 columns → 9) and
that survived a reload too. B14 rule 31 holds — **no database id among 450 cell values** —
and rule 33 holds on the headers, the longest being two words.

⛔ **`DEF-CUS-6133` — the filter offers `Draft` twice**, because `DEF-CUS-6098` gave
`in_progress_draft` the word `draft` already had. A clerk has two identical boxes.

**Reported, not filed:** searching by premise or by applicant returns the right row and
**nothing on screen says why** — the PREMISE column draws the address, and the APPLICANT
column is `defaultVisible: false` by a decision `NewConnectsTab` argues in its own words. The
column chooser turns the applicant on; there is no premise-number column to turn on at all.

⚠ **AND THE PROBE THAT NEARLY FILED A DEFECT AGAINST A CORRECT LIST IS WORTH READING.**
`GET /connections?per=1` answers **nine** rows with `next: null`; `?per=2&page=2` answers the
same nine with `previous: null`. That reads exactly like an unpaginated list. It is not —
`clamp_page_size`'s vocabulary is 50/100/200/500/1000, so **`per` clamps UP** and one page
holds all nine. The walk now carries that sentence beside the check.

#### 9.3a · AND THE WAY OUT THE PRODUCT INTENDS IS THE ONE THAT BREAKS (`DEF-CUS-6135`)

`DEF-CUS-6132` above is about a clerk who walks away. Chasing the door the product DOES
intend turned up something worse, and it is the most serious thing in this walk.

There are three ways out of the wizard. **`Save & exit` throws away what was typed — and that
is correct**, `B19 §12.2` says so in as many words, so it is recorded here only because it
looks exactly like a bug. **`Park` is the one that keeps the work**, and its own panel
promises: *"Reopening this from your Waiting on list brings you back to this step with
everything you have typed. Nothing is created or changed until you finish the wizard."*

Walked on `CON-26-0131`, the build raised by approving `SR-26-0008`:

* the park row is written with **an empty reference**, so the row it puts on the New connects
  tab has a **blank connection number** — it names nothing a clerk can say out loud;
* its door is `/connections/new?parked=<park-id>` with **no `build=`**, so the reopened
  wizard does not know which build it is finishing;
* the typing does come back, exactly as promised;
* **and the last press created a SECOND build.** The commit answered `200` with
  **`CON-26-0132` and a new id** — not the id it was finishing — on the same property,
  reading `from —`, and a unit was created (131 → 132). **`CON-26-0131` is still a draft,
  still naming `SR-26-0008`.**

One piece of work, **three rows** on the tab, and the real build has lost its application.

The cause is one sentence that stopped being true: `BR-SHL-048(c)` — *"a parked wizard holds
nothing"* — was ruled when a New Connect held nothing until its last button. `DEF-CUS-6109`
made a build exist before the wizard finishes and the park was never told. `PHASE=park` in
`cr126_s9_request_to_record_walk.mjs` drives it now, and its verdict is the ID the commit
answers with rather than any count — a walk that checked the marker came back would pass,
because it does, and a walk that counted rows on the list counts parked wizards among them.
