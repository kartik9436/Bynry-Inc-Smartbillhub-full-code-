# 17 · Runbooks — the contract

**What every runbook implements, and what it never does.**

Thirty-four runbooks looked custom, because each has its own checks and its own result. They are not: every
one is the same declared object, and every result is a composition of the twelve blocks
(`09-component-inventory.md`) drawn by one renderer. **Adding runbook 23 requires no new screen and no
frontend code** — one Python module, and it appears on Templates, sets up on `RBS-004` and reports on
`RBS-006`. That claim is `RB-020`, and this file is what it rests on.

---

## 1 · The object a runbook declares

| # | Declaration | What it is |
|---|---|---|
| 1 | **`key`** · **`kind`** (`check` \| `action`) · **`subject_type`** · **`unit_of_work`** · **`triggers[]`** | identity: what it is called, whether it can write, what it walks, at what grain, and what starts it |
| 2 | **`category`** · **`tags[]`** | **one home** from a fixed list of sixteen — places it in the library, sets its default roles, and **names whose ports it may call**. Tags only help a search. |
| 3 | **`parameters[]`** | typed — the eleven types in `09-component-inventory.md`. **Each declares a DOMAIN, the domain is resolved PER TENANT, and a value may be one, several, or *all* of it** (`BR-RBS-042`). *All* is stored as **the word** and resolved at run start, never expanded at configure time. Anything already in Settings is `ref:setting`, read-only, and never duplicated. |
| 4 | **`resolve(params) → [SubjectRef]`** | one function. It also answers *"matches 1,004 today"* on the setup screen and on step 1 of the wizard. |
| 5 | **`steps[]`** | each: `run(ctx, subject) → outcome`, declaring `writes: bool` and `mode: per_record \| set` |
| 6 | **`guards[]`** | **absolute skips, evaluated before any step.** They cannot be switched off and `RBS-004.4` says so rather than hiding the control. |
| 7 | **`requires`** *(optional)* | one Check run first, **as its own run**, linked from step 1. If it fails, every later step reads **Never reached** and the verdict is No-go. (`RB-036`, `BR-RBS-027`) |
| 8 | **`ports[]`** | the allow-list this runbook may call — **empty for a Check, enforced at construction** |
| 9 | **`report(run) → [Block]`** | composed from records and counts; **frozen on the run when it closes**, so a past run reopened draws exactly what it drew that day |

### Parameters are the ONLY thing a tenant sets — and that is what makes *author no* structural

**PO ruling 2026-09-06.** A runbook is **one fixed process with declared inputs.** Nobody arranges
its steps — not a tenant, ever. PO verbatim: *“you cannot change the logic those are finate steps ; you can change the input to logic … this way, we control the inputs however process remain same , and then out put produced is filtered ; please note every utility will not have all utility services or all combinations of Plans and rates, so we ahve to work in variables”*.

**Three things follow, and every one of them is a build instruction:**

* **A domain, per parameter.** `enum`, `ref:object` and `window` each carry the set a tenant may
  choose from. **`enum` accepts ONE value, SEVERAL, or *ALL*** — B14 already rules the shape:
  **multi-select as chips, never a checkbox wall** (`09-component-inventory.md`, rule 9).
* **The domain is TENANT-RESOLVED, never hardcoded.** *“every utility will not have all utility
  services or all combinations of Plans and rates”*. A two-service utility's *services* domain
  holds two; a utility with three plans sees three; **an empty domain says so** rather than
  drawing an empty dropdown that looks broken.
* ⚠ **AND *ALL* IS A RULE, NOT A VALUE.** Store the **word**; `resolve(params)` expands it **at
  run start** and `BR-RBS-009` pins it there. A utility that sets *all services* while it has
  Water and Sewer, and adds Trash next month, gets **three** on the next run. **Expand it at
  configure time and adding a service silently drops it out of every runbook set to *all*, with
  nothing on any screen to see.**

⚠ **THE STEP LIBRARY IS OURS AND IT IS NOT PART OF THIS CONTRACT'S TENANT-FACING SURFACE.**
**173 step instances across 26 runbooks reduce to 137 distinct steps** (`14-step-library.md`, the hand count of 2026-09-06), used from wave `C` onward to build runbooks. It is an **internal engineering asset**: no
screen draws it and no endpoint serves it. PO verbatim: *“I dont think Utility admin will able to configure these using the 150 bricks that we give - you can keep all these bricks and buld ready to use runbooks - when we later change it will be small er changes for us”*. **There is no filter builder for anybody** — inputs have domains, and that is the whole
mechanism.

⚠ **SUPERSESSION, STATED NOT INFERRED.** The PO ruled ***“compose yes, author no”*** on
**2026-09-05**, and this module read *compose* as **the tenant composing**. The ruling of
**2026-09-06 narrows it: WE compose; a tenant SETS and CLONES.** Both are the PO's and the later
governs. **What that buys is that *author no* stops being a rule somebody polices and becomes a
property of the shape** — a tenant who can only choose input values has no path by which to write
logic. `US-RBS-039`'s endpoint surface shrinks accordingly (`07-endpoints.md` E-3).

⚠ **The source calls this a *seven-part object* and its own figure lists NINE declarations.** The count is
recorded rather than picked, because both numbers are in the specification and a later reader will hit the
gap. The likeliest reading: `requires` is stamped *"new to the contract"* by `RB-036` and was added after the
word *seven* was written, and `ports[]` was originally counted with the write story rather than as its own
part. **Cite the declarations by NAME, not by the count.**

## 2 · The two things the engine does that no runbook may

> **Raising work items and writing audit rows are ENGINE acts, not ports.**

A Check produces **findings**; the engine upserts them as work items when the run closes. **That is how a
Check can populate `RBS-007` and still be constructed with no writer at all.** It is also why the work list
ages honestly: items are **upserted, not re-created**, so thirty daily sweeps over one missing read produce
one item, thirty days old.

Approving a list, attaching evidence to a cutover plan item, pressing **Close** on a period — these are acts
a **person** performs from an `Action` block, and the **engine or the owning module** performs them, never
the runbook.

Every money action writes `audit_log` (hard rule 7). The audit row **names the runbook and its version** as
the actor — `RBS-004-R8`'s last step is exactly that, and `RBS-008`'s *By* column is where a clerk reads it.

---

## 3 · Steps — two modes, and the unit of work is never the raw row

**Per-record** steps run once per subject **inside its own savepoint** — the collections ladder, cash
application. **Set** steps run once over the whole pinned set — a tie-out, a totals comparison, the
calculation of each meter's own normal before the per-record pass. **Month-end, cutover and bank
reconciliation are mostly set-mode; without it they would be awkward and slow over 1.2M journal lines.**

⚠ **A per-record savepoint is not the tidy option, it is the only one.** Hard-won law 14: on PostgreSQL a
failed statement aborts the whole transaction, so `try: … except IntegrityError: continue` loses the work at
COMMIT — and **`config/settings/test.py` hardcodes in-memory SQLite, which has no aborted-transaction state**,
so the broken version passes the entire suite green on every machine. Any runbook step that catches a database
error and carries on **must be proved on a real PostgreSQL**.

### The unit of work

**A runbook declares what it walks and the unit is never the raw row. That is a rule, not a preference.**

> Read validation walks the **meter-day**, not the interval: **176,640 intervals become 1,840 records**, and a
> per-record savepoint stays cheap.

`RB-015`'s *done looks like*: an interval batch of 176,640 rows shows on the result as **1,840 meter-days**,
and the run's record count reads **1,840**.

### The subjects — twelve

`tenant` · `account` · `premise` · `meter` · `meter-day` · `bill` · `payment` · `bank line` · `deposit` ·
`parcel` · `contact feedback` · `period`.

⚠ **`premise` here is `premises`, the product's own word and its one address home** (hard rule 8,
`BR-MET-1161`). A runbook that wants an address **walks to the premises**; it never reads an address column
off an account, a meter, a route or a work order, because none of them has one.

---

## 4 · Triggers

| Trigger | Fires when | Used by runbook |
|---|---|---|
| **Manual** | A person presses **Run ▶** | 1 · 2 · 4 · 5 · 6 · 12 · 13 · 16 |
| **Schedule** | Cron **in the tenant's timezone**, on the platform job runner | 3 · 5 · 8 · 9 · 15 · 17 · 18 · 19 |
| **`batch.landed(connection, batch_id, subject_type)`** | An integration connection lands a batch — payments, intervals, statement lines, parcels | 10 · 11 · 14 · 20 · 21 |
| **`feedback.landed(provider, batch_id)`** | Delivery receipts and bounces land | 22 |
| **`bill_run.completed(run_id)`** | A bill run finishes — the break list exists | 6, as the *"run it for the whole break list"* variant |

**Three kinds — manual, schedule and event — over five trigger rows, of which three are event names.** (The
specification's heading reads *"three kinds, five events"*; the five is the row count.)

**Integrations emits the events; the engine subscribes runbooks to them by connection kind.** Both integration
fetches and runbook runs are **job kinds on the one existing runner — one scheduler, not two.**

⚠ **The three event kinds are BLOCKED-BY the integration substrate (`CR-069`); manual and schedule wait on
nothing** (`RB-022`). A runbook whose only trigger is an event is not runnable until that lands, and a screen
must say so rather than offering a **Run ▶** that refuses.

---

## 5 · Categories — sixteen, eleven in use

**A runbook has exactly one category and any number of tags. Three things read the category**, and the third
is what makes it an engineering fact rather than a label:

1. **The template library filters by it** — and **a category with no TEMPLATE draws no chip**, because a chip
   that filters to nothing is dead UI (`RB-019`). `RBS-002.1` draws **eight chips for twelve templates**.
   ⚠ **The test is a template, not a configured runbook:** *Accounts* holds no runbook in the table below and
   still draws `Accounts 1`, because the reserved *Move-outs* template lives there.
2. **Role visibility defaults from it.** Owner and Admin see every runbook; the last column below says who
   else does by default; an Admin may widen or narrow it per runbook (`RB-050`).
3. **It names the OWNING MODULE — the module whose ports the runbook may call.** A Collections runbook
   reaches `payments`' ports and no other module's, **and a Check reaches none.**

| Category | Runbooks | Owning module — whose ports it may call | Seen by default, beyond Owner and Admin |
|---|---|---|---|
| Platform | 1 | `tenancy` | — |
| **Onboarding & Cutover** *(added)* | 2 | `tenancy` · the cutover plan in operations | — |
| Data Hygiene | 19 | `customers` · `metering`, read only | + Staff |
| **Premises** | 18 | `metering` — premises and units | + Staff |
| Plans & Rates | 16 | `rating` | — |
| Assets | none yet | `metering` — assets | + Staff |
| Accounts | none yet | `customers` | + Staff |
| Reads | 5 · 11 | `metering` | + Staff |
| Billing | 3 · 4 · 6 | `billing` | + Staff · Finance |
| **Collections** *(added)* | 8 · 12 · 15 | `payments` — the ladder lives in its settings | + Finance |
| Payments | 10 · 13 · 17 | `payments` | + Finance |
| Finance | 9 · 14 | `ledger` | + Finance |
| Work | none yet | `work` | + Staff |
| Customer portal | none yet | `customers` — the portal | + Staff |
| Business | none yet | `reports` | — |
| Data Sync | 20 · 21 · 22 | `integrations` | — |

⚠ **The category is *Premises*, not *Service points*.** Decision log 2026-09-06: **category names use the
product's OWN existing word wherever the product already has one** — *"A second name for a thing the product
has already named is how a clerk learns two vocabularies for one screen."* The specification's *Service
points* is superseded; nothing else in that list moved.

**Two categories were added to the fourteen we were given, one was declined, five are empty.** *Onboarding &
Cutover* runs once per utility and should sort first before go-live and last after it; nothing else behaves
that way. *Collections* holds three runbooks that share the collections ladder and the same gate on money
owed, and **a collections clerk is not a cashier**. ***Communications* was declined**: 8, 17 and 22 all queue
notices, but **a notice is the channel, not the question**, so it stays a tag.

⚠ **The category list is closed by the same rule as the block list: a seventeenth category needs THREE
runbooks that fit nowhere else.** A runbook module declaring a category not on this list fails the suite
(`RB-019`).

---

## 6 · Ports — the allow-list, **thirteen** today

**A port is the only way a runbook reaches another module or a partner.** Each maps to **one service function
in the owning module**, so the platform's ban on cross-module writes holds, and **the list of everything
automation can do to a customer is one table.** A new runbook that needs a new port is **adding a reviewed
interface, not a custom write.**

| Port | Owning module | What it does |
|---|---|---|
| `queue_notice` | `notifications` | Writes a queue row; the dispatcher sends |
| `queue_receipt` | `notifications` | A receipt document to the queue |
| `apply_payment` | `payments` | Applies a landed payment by the allocation order |
| `post_credit` | `payments` | A credit to an open account |
| `raise_refund` | `payments` | A refund awaiting its own approval |
| `record_match` | `payments` | A bank line matched to a deposit batch |
| `schedule_retry` | `payments` | A retry of a failed debit |
| `apply_fee` | `billing` | A fee by rule, **behind the second approval** |
| `write_read` | `metering` | A validated meter-day as a read, **source stamped** |
| `apply_premise_change` | `metering` | One field on one premise, **before-and-after kept** |
| `flag_meter` | `metering` | *"Told about a leak on"* a date |
| `suppress_channel` | `customers` | A contact channel marked undeliverable, **dated** |
| `flag_account` | `customers` | A flag with a reason |

**Five modules own ports: `notifications` (2) · `payments` (4) · `billing` (1) · `metering` (3) ·
`customers` (2).** No port reaches `ledger`, `rating`, `tenancy` or `integrations` — those are **read-only**
to a runbook, which is why *Month-end completion*'s **Close** is a person's act performed by `ledger`, and
why *Rate change preview* can model a draft tariff and change nothing.

### ⚠ The source contradicts itself here, and thirteen is right

**The architecture section says a runbook writes through *"four named calls into the owning module's service:
queue a notice, flag an account, raise a work item, apply a fee"*, and its summary sentence repeats it —
*"it writes nothing of theirs except through the four ports"*, and *"the four port seams"* appears FIVE more
times — the B2b seams paragraph, `RB-052` twice (its commitment card and its register row), `US-RBS-041`, and
the build-notes section. The contract section, one page later, lists THIRTEEN ports and states explicitly
that raising a work item is an ENGINE act and not a port at all.**

**Resolved, and the reason is written out here rather than left to be re-derived:**

* **THIRTEEN is right.** It is the later and finer statement, it names an owning module for each entry, and
  it is the list the twenty-one result wireframes need: `record_match` is drawn on runbook 14, `write_read`
  on 21, `apply_premise_change` on 20, `suppress_channel` on 22, `post_credit` and `raise_refund` on 15,
  `schedule_retry` on 17. **The four-port sentence cannot draw any of them.**
* **`raise a work item` IS NOT A PORT.** The same figure that lists the thirteen states in its own heading
  that *raising work items and writing audit rows are engine acts*. It is also the load-bearing half of the
  design: a Check is **constructed with no ports** and must still populate `RBS-007`, which is impossible if
  raising a work item is a port.
* **So the *four named calls* sentence is STALE, and it is wrong twice over** — it undercounts thirteen as
  four, and three of the four it names (`queue_notice`, `flag_account`, `apply_fee`) are real ports while the
  fourth is an engine act. **It reads as an early draft written before the port list was enumerated.**
* **Wherever a document says *"the four port seams"*, read *"the port seams"*.** The seam-per-write rule is
  unaffected; only the number is.

⚠ **This note exists because the stale claim is in SEVEN places and the correct one in ONE** — counted:
`"four named calls"` and `"the four ports"` twice in the architecture section, `"the four port seams"` five
times more. **A lane grepping for *port* finds the wrong answer seven times out of eight.** When `RB-052` and
`US-RBS-041` are next edited, the word *four* comes out — that is a fan-out, not a status edit.

⚠ **A SECOND LANE REACHED THE SAME RESOLUTION INDEPENDENTLY, WHICH IS THE BEST EVIDENCE THIS FILE HAS.** The
same contradiction is recorded as divergence **D-1** in this module's `03-field-map.md`, whose port table
lists the identical thirteen with the identical owning modules, and again in `04-flows.md`,
`11-catalogue/README.md` and `CR-075`. Two readings of one source, taken separately, landed on thirteen and
on *raise-work-item is not a port*. **If a future lane finds a fourth reading, it is arguing with two.**

---

## 7 · Seams, not clients — the part a builder is most likely to get wrong

**The object above says what a runbook DECLARES. It does not say how its steps reach the data**, and a lane
that does not know this repository will write an HTTP client against the product's own API, or import another
module's models. **Both are wrong here.**

* **Every READ of another module is a seam file the runbook module OWNS**, named for the pair, **calling the
  owner's selector by name, in process, under the tenant context.** Nine are named:
  **operations → `customers` · `metering` · `rating` · `billing` · `payments` · `ledger` · `notifications` ·
  `tenancy`** (for settings) **· `integrations`** (for a landed batch).
* **Every WRITE is a port** (§6). **A Check is constructed with none**, so a write from a Check is a
  **construction error, not a runtime one**.
* **Every seam gets a row in the cross-module interface register** — B2 §2's reviewed set — **added in the
  same commit as the file**.
* **A selector that does not exist yet is added by the module that OWNS the table**, never by the runbook
  module reaching past it.
* **No HTTP client anywhere in the module**, and no importing another module's models. The test that proves
  it is a **census of the module's imports** (`TC-RBS-25`).

**This is B1's existing rule applied to a new module, and the pattern is already in the repository twice** —
`billing` carries **nine** (`apps/billing/rating_seam.py`, `customers_seam.py`, `metering_seam.py`,
`payments_seam.py`, `posting_seam.py`, `settings_seam.py`, `tenancy_seam.py`, `delivery_seam.py`,
`run_alert_seam.py`) and `work` carries **eight** (`apps/work/seams/assets_seam.py`, `billing_seam.py`,
`customers_seam.py`, `identity_seam.py`, `metering_seam.py`, `notifications_seam.py`, `payments_seam.py`,
`tenancy_seam.py`). ⚠ **The two differ in LAYOUT and a lane must pick one deliberately: `billing` puts its
seams flat in the app package, `work` puts them in a `seams/` sub-package.** With nine seams and a gate to
write against them, **follow `work`** — a directory is what `G78` globs and what a ninth seam does not
crowd. **Reach for the existing pattern rather than inventing a client.** `G78` fails a foreign write from
the `work` module's first
commit; **the runbooks module needs its own equivalent gate from its own first commit**, and per hard-won law
7 it must be proved RED first — and proved red **through `run_gates`, not through `python3 <gate>.py`**, which
is the path `DEF-GOV-3733` showed exercises `__main__` and never the registry.

⚠ **Two naming questions this file does not settle, both recorded so nobody answers them twice:**

1. **The code module's name.** The routes and the source's seam names say `operations`; the docs module is
   `17-runbooks`; the product word is **Runbooks** (PO 2026-09-06: *"we coin the word Runbooks"*). Neither
   `apps/operations` nor `apps/runbooks` exists on disk.
2. **The seam file's name.** The source says seams are *"named for the pair (operations → customers)"*. **The
   repository's existing convention names only the FAR side** — `apps/work/seams/customers_seam.py`, not
   `work_customers_seam.py`. **Follow the repository**: `apps/<module>/seams/customers_seam.py`. The pair is
   already in the path.

---

## 8 · Coverage — every defined runbook against the contract

**The proof the framework holds: each row is one Python module — scope, steps, report — and no frontend code.**
Blocks are `09-component-inventory.md`'s twelve; this table is the citable source for *which runbook uses
which block*, and the reasons are recorded there.

| # | Runbook | Kind | Category | Trigger | Subject · unit | Step modes | Blocks | Ports |
|---|---|---|---|---|---|---|---|---|
| 1 | Configuration check | Check | Platform | Manual | Tenant · config graph | set · per record | KPIs · Chain · Records · Downloads | — *(engine raises work items)* |
| 2 | Ready for cutover? | Check | Onboarding & Cutover | Manual | Tenant + uploaded file · plan items | set | Verdict · KPIs · Chain · Reconciled · Records · Downloads | — *(engine attaches evidence to plan)* |
| 3 | Ready for billing? | Check | Billing | Schedule | Account · one cycle | per record | Verdict · KPIs · Records · Downloads | — |
| 4 | Why is this bill higher? | Check | Billing | Manual | Account · one | per record (1) | KPIs · Ranked · Reconciled · Sentence · Facts | — |
| 5 | Abnormal readings | Check | Reads | Schedule · manual | Meter · 12 months | per record | KPIs · Records *(sparkline)* · Action *(raise items)* · Downloads | — |
| 6 | Why did this not bill? | Check | Billing | Manual | Account · one, or a break list | per record (1) | Sentence · Chain · Facts · Records | — |
| 8 | Dunning and notices | Action | Collections | Schedule | Account · past due | per record | KPIs · Breakdown · Records · Downloads | `queue_notice` · `apply_fee` |
| 9 | Month-end completion | Check | Finance | Schedule | Period | set | Verdict · KPIs · Reconciled · Records · Action *(close, by a person)* · Downloads | — *(Close is a ledger act a person performs)* |
| 10 | Cash application | Action | Payments | ⚡ Payments landed | Payment · a day's batch | per record | KPIs · Breakdown · Records · Downloads | `apply_payment` · `queue_receipt` |
| 11 | Leak and high-usage alert | Action | Reads | ⚡ Intervals landed | Meter-day | set *(own normal)* · per record | KPIs · Records · Sentence · Downloads | `queue_notice` · `flag_meter` |
| 12 | Disconnect eligibility | Check | Collections | Manual | Account · last tier | per record | Verdict · KPIs · Records · Action *(approve list)* · Downloads | — *(approval is engine-owned; a crew acts)* |
| 13 | Payment trace | Check | Payments | Manual | Account or payment · one | per record (1) | Verdict · Chain · Facts · Action *(route to move)* | — |
| 14 | Bank reconciliation | Action | Finance | ⚡ Statement landed | Bank line | set *(match)* · per record | KPIs · Records · Downloads | `record_match` |
| 15 | Deposit review | Action | Collections | Schedule | Deposit | per record | KPIs · Records · Action *(approve refunds)* · Downloads | `post_credit` · `raise_refund` · `queue_notice` |
| 16 | Rate change preview | Check | Plans & Rates | Manual | Bill · one cycle + a draft schedule | per record · set *(sums)* | KPIs · Ranked · Records · Breakdown · Downloads | — |
| 17 | Autopay pre-notification | Action | Payments | Schedule | Account · autopay | per record | KPIs · Records · Downloads | `queue_notice` · `flag_account` · `schedule_retry` |
| 18 | Vacant premises with usage | Check | Premises | Schedule | Premise · 90 days | per record | KPIs · Records · Action *(raise items)* · Downloads | — |
| 19 | Data hygiene | Check | Data Hygiene | Schedule | Tenant | set | KPIs · Breakdown · Action *(raise items)* · Downloads | — |
| 20 | GIS reconciliation | Action | Data Sync | ⚡ Parcels landed | Parcel ↔ premise | per record | KPIs · Breakdown · Records · **Row decisions** · Downloads | `apply_premise_change` |
| 21 | Read validation on arrival | Action | Data Sync | ⚡ Intervals landed | Meter-day | set *(roll-up)* · per record | KPIs · Records · Downloads | `write_read` |
| 22 | Undeliverable contacts | Action | Data Sync | ⚡ Feedback landed | Contact feedback | per record | KPIs · Breakdown · Records · Downloads | `suppress_channel` · `flag_account` |

**Twelve Checks, nine Actions.** **Every Action's ports are on this table and nowhere else** — that is the
whole safety story, and it is what `RBS-002.2`'s *What it can touch* and `RBS-004.1`'s *This can* render.

**There is no runbook 7.** PO ruling 2026-09-05: *"Keep as numbered: 1 to 22 with no 7"*, and the reserved
block 23–35 continues the same series — **34 runbooks, 21 defined and 13 reserved.** Runbooks 23–27 have a
setup wireframe and **no result wireframe**; 28–35 have neither, only a commitment card (`RB-128`–`RB-135`).

---

## 9 · What a runbook may never do — the short list

1. **Write another module's table directly.** Every write is a port; every port is one service function in the
   owning module. Cross-module writes are forbidden (B2 §2, DB-16).
2. **Write anything at all, if it is a Check.** `ports[]` is empty and it is **enforced at construction**, so
   the failure is a build error and not a bad Monday.
3. **Import another module's models, or call the product's own HTTP API.** Reads go through a seam; a census
   of the module's imports proves it (`TC-RBS-25`).
4. **Touch a guarded record.** Guards are absolute and evaluated before any step.
5. **Exceed its cap.** `RBS-005.7` is what a refused cap looks like, and **Send first 400** is a deliberate
   choice a clerk makes — never what the system quietly did.
6. **Resolve its scope twice.** Scope is pinned to the run at step 1 (`RB-008`); an account that becomes past
   due mid-run is not in the review list and is not acted on.
7. **Report a thirteenth block.** Refused at run close; it never reaches the screen (`RB-016`).
8. **Declare a seventeenth category.** The module fails the suite (`RB-019`).
9. **Say *Sent* where it means *Queued*.** Until a delivery provider is connected nothing leaves the building
   and no copy may claim otherwise.
10. **Walk the raw row.** The unit of work is declared and it is never the interval, the journal line or the
    reading (`RB-015`).
