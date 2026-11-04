# runbooks — Field Map

**Seven tables, all tenant-scoped, none owned by another module.** Source: the Runbooks
specification **B3**, read at product `2.128.2`. B3's own pass note records what moved in its last
revision: `runbook_runs` gained `parent_run_id` (a required Check's run linked from its caller,
`BR-RBS-027`), `runbooks` gained `origin`, `template_key` and `cloned_from`, `runbook_run_records`
gained a decision with who made it and when, and **`cutover_plans` was added** — its items had
referenced a plan that had no table.

**Every table below carries `tenant_id` and RLS `FORCE` in the same migration that creates it**
(hard rule 1) · **a `uuid7` primary key** · **`created_at` / `updated_at` stamps**, matching the
platform's existing shape. **Money is `NUMERIC(18,4)` stored and displayed to 2** (hard rule 2);
**percentages `NUMERIC(18,6)`, displayed 2** · **currency is `CHAR(3)`** · **never float, never
cents.** A quantity carries its unit (hard rule 3).

**How to read the Type column.** `[B3]` means the specification names the type or the value set.
`†` means the SQL type is **this file's derivation** from the platform's existing shape — B3 names
the column and not its type — and is the build lane's to confirm against the schema brief. **No
column below is invented: every one is named in B3.** Where a rule this repo carries needs a
column B3 does not name, it is a row in *Discrepancies* at the foot and **not** a column here.

⚠ **`02-database-design-brief.md` (B2) CARRIES NONE OF THESE SEVEN TABLES.** Grepped at
`6fed5da8`: the brief has `### Module:` sections for tenancy, identity, metering, customers,
rating, billing, payments, ledger, notifications, audit, integrations and work — and none for this
module. That is `I-2`'s shape from integrations, and it closes the same way: **anchoring the seven
in B2 is the build lane's first task, in the same commit as the brief, not here.** This file is
the specification of the tables, not the schema of record.

⚠ **THE MODULE DIRECTORY AND THE NAV ROUTE ARE TWO DIFFERENT NAMES ON PURPOSE.** The backend
module is **`apps/runbooks`**; the nav route stays **`/{tenant}/operations`** as every wireframe
draws it, until the section name in the navigation is ruled. **B3 and the whole specification say
`apps/operations`** for the module — that name is superseded by the PO's naming ruling of
2026-09-06 for the code, and the seam files keep the source's `operations → <module>` pair naming
so a reader of either document finds the same seam.

---

## 1 · `runbooks` — one row per runbook available to the tenant

| Field | Type/unit | Origin | Validation | Notes |
|---|---|---|---|---|
| `id` | `uuid` (uuid7) † | system-derived | primary key | platform shape |
| `tenant_id` | `uuid` NOT NULL † | system-derived | RLS `FORCE`; every query under the tenant context | hard rule 1 |
| `key` | `text` NOT NULL † | reference-data / user-input | **stable and unique per tenant** `[B3]` | the runbook's address: `/runbooks/{key}` |
| `name` | `text` NOT NULL † | user-input | the display name a clerk sees | `RBS-002` gallery, `RBS-003` list |
| `kind` | `text` — `check \| action` `[B3]` | reference-data | **immutable after creation** `[B3]` | `BR-RBS-001`; a Check is constructed with no ports (`BR-RBS-002`) |
| `category` | `text` — one of the **sixteen** held in code `[B3]` | reference-data | **never free text** `[B3]`; a module declaring one outside the list fails the conformance suite | `BR-RBS-024`; names the owning module whose ports it may call |
| `tags` | `text[]` `[B3]` | user-input | any number; helps a search only | `BR-RBS-024` |
| `origin` | `text` — `shipped \| cloned \| composed` `[B3]` | system-derived | set at creation | `RB-040` (clone), `RB-041` (compose) |
| `template_key` | `text` NULL † | system-derived | the shipped template this copy came from | drives *Template updated · Review →* (`BR-RBS-038`) |
| `cloned_from` | `uuid` NULL † | system-derived | the runbook this one was cloned from | `US-RBS-038` |
| `subject_type` | `text` `[B3]` | reference-data | one of: tenant · account · premise · meter · meter-day · bill · payment · bank line · deposit · parcel · contact feedback · period `[B3]` | what the runbook walks |
| `unit_of_work` | `text` `[B3]` | reference-data | **never the raw row** | `BR-RBS-019`; 176,640 intervals become 1,840 meter-days |
| `enabled` | `boolean` † | user-input | a disabled runbook never fires on its schedule | |
| `trigger_kind` | `text` — `manual \| schedule \| event` `[B3]` | user-input | `BR-RBS-016` for the schedule half | three kinds, five events |
| `cron` | `text` NULL † | user-input | evaluated in `timezone`, on the platform job runner | `BR-RBS-016` |
| `event_kind` | `text` NULL `[B3]` | reference-data | one of `batch.landed` · `feedback.landed` · `bill_run.completed` `[B3]` | integrations emits; the engine subscribes by connection kind |
| `timezone` | `text` `[B3]` | user-input | **the tenant's own**, as the notification schedule already does | `BR-RBS-016` |
| `cap` | `integer` † | user-input | **refuses the run; never truncates** | `BR-RBS-006` |
| `gate_mode` | `text` `[B3]` | user-input | who approves and at which point; a money-bearing action carries a second approval | `BR-RBS-018` — the threshold is the PO's |
| `current_version` | `integer` † | system-derived | points at the newest `runbook_versions` row | `BR-RBS-038` |
| `created_at` · `updated_at` | `timestamptz` † | system-derived | platform stamps | |

## 2 · `runbook_versions` — an immutable snapshot each time the definition changes

| Field | Type/unit | Origin | Validation | Notes |
|---|---|---|---|---|
| `id` · `tenant_id` | `uuid` (uuid7) † | system-derived | RLS `FORCE` | |
| `runbook_id` | `uuid` NOT NULL † | system-derived | FK to `runbooks` | |
| `version` | `integer` NOT NULL `[B3]` | system-derived | unique per runbook †; **every edit makes a new one** | `BR-RBS-038` |
| `definition` | `jsonb` NOT NULL `[B3]` | user-input / reference-data | the whole seven-part object: parameters, steps, guards, gate, cap, requires, ports | see *the parameter types* below |
| `changed_by` | `uuid` `[B3]` | system-derived | the person, from the session | drawn on the Activity tab (`RBS-004.7`) |
| `changed_at` | `timestamptz` `[B3]` | system-derived | | |

**A run stores the version it used, so a later edit never rewrites history** `[B3]`. `TC-RBS-13`
goes red on a definition read live at display time.

⚠ **THE ELEVEN PARAMETER TYPES LIVE INSIDE `definition`, WHICH MEANS NO COLUMN ENFORCES THEIR
PRECISION.** B2b's parameter table declares `money` as *"4 decimals stored, 2 shown"* and
`percent` as *"6 decimals stored, 2 shown"* — the same rule hard rule 2 states for columns. In
`jsonb` there is no `NUMERIC(18,4)` to hold them to it, so **the precision is the parameter
renderer's and the validator's to enforce, and a float written into that document is a hard-rule-2
breach no database constraint can see.** The eleven types: `money` · `integer` · `days` ·
`percent` · `enum` · `toggle` · `text` · `window` · `ref:setting` (read-only, rendered from
Settings with a link) · `ref:object` · `file`. Recorded as `D-3` below.

## 3 · `runbook_runs` — one row per run

| Field | Type/unit | Origin | Validation | Notes |
|---|---|---|---|---|
| `id` · `tenant_id` | `uuid` (uuid7) † | system-derived | RLS `FORCE` | |
| `runbook_id` | `uuid` NOT NULL † | system-derived | FK to `runbooks` | |
| `version` | `integer` NOT NULL `[B3]` | system-derived | **pinned at start**, never re-read | `BR-RBS-038`, `TC-RBS-13` |
| `mode` | `text` — `dry \| live` `[B3]` | user-input | **one code path; the writer is bound or it is not** | `BR-RBS-003`, `TC-RBS-2` |
| `trigger` | `text` — `manual \| schedule \| event` `[B3]` | system-derived | matches how it actually fired | |
| `event_ref` | `text` NULL `[B3]` | integration | the landed batch that started it | named as the scope on the run header (`RB-022`) |
| `parent_run_id` | `uuid` NULL `[B3]` | system-derived | the caller's run when this is a required Check | `BR-RBS-027`, `RB-036` |
| `status` | `text` — `queued · running · awaiting_approval · approved · acting · done · failed · stopped` `[B3]` | system-derived | the state machine in `04-flows.md` §3 | |
| `scope_fingerprint` | `text` `[B3]` | system-derived | **the pinned id list, frozen at start** | `BR-RBS-009`, `TC-RBS-22` |
| `counts` | `jsonb` `[B3]` | system-derived | per-outcome counts, including the ones with no record row | `BR-RBS-035` |
| `report` | `jsonb` `[B3]` | system-derived | **the block list as composed when the run closed, and frozen** | `BR-RBS-020`; a thirteenth block is refused at close, not at render (`TC-RBS-16`) |
| `started_at` · `finished_at` | `timestamptz` † | system-derived | | |
| `approved_by` | `uuid` NULL `[B3]` | user-input | the admin who approved the batch | `BR-RBS-005` |
| `approved_count` | `integer` NULL `[B3]` | user-input | **must match the current plan or the approval conflicts** | `BR-RBS-005`, `TC-RBS-8` |
| `stopped_by` | `uuid` NULL `[B3]` | user-input | who pressed Stop | `RB-005`, `TC-RBS-9` |
| `created_at` · `updated_at` | `timestamptz` † | system-derived | | |

## 4 · `runbook_run_records` — one row per record examined: the plan, then the outcome

| Field | Type/unit | Origin | Validation | Notes |
|---|---|---|---|---|
| `id` · `tenant_id` | `uuid` (uuid7) † | system-derived | RLS `FORCE` | |
| `run_id` | `uuid` NOT NULL † | system-derived | FK to `runbook_runs` | |
| `subject_type` | `text` `[B3]` | system-derived | the twelve subjects | |
| `subject_id` | `uuid` `[B3]` | system-derived | **the id of another module's row — read through a seam, never joined across** | `BR-RBS-039` |
| `planned_action` | `text` `[B3]` | system-derived | written at evaluation, **before any act**; a Check's finding is a record whose planned action is `report` `[B3]` | `BR-RBS-004` |
| `decided_by_rule` | `text` `[B3]` | system-derived | **the rule that decided it, in words a clerk can read** | `BR-RBS-010` |
| `outcome` | `text` `[B3]` | system-derived | written after the act; the plan and the outcome share one row on purpose | |
| `reason` | `text` `[B3]` | system-derived | plain language, no rule id on screen (B14 rule 32) | |
| `fix_route` | `text` `[B3]` | system-derived | **a failure with no route is a defect in the runbook** | `BR-RBS-011`, `TC-RBS-14` |
| `decision` | `text` NULL `[B3]` | user-input | a row decision: pick account · confirm overpayment · accept theirs · keep ours | runbooks 10 and 20; performed through the owning module's port |
| `decided_by` | `uuid` NULL `[B3]` | user-input | | |
| `decided_at` | `timestamptz` NULL `[B3]` | system-derived | | |
| `amount` | `NUMERIC(18,4)` `[B3]` | system-derived | **stored 4, displayed 2** | hard rule 2; ⚠ **no currency column beside it — `D-2`** |
| `data` | `jsonb` `[B3]` | system-derived | the per-record extras a block needs: twelve sparkline values, ours and theirs, the bank's reason text `[B3]` | |
| `idempotency_key` | `text` `[B3]` | system-derived | **runbook + run + record + action kind** | `BR-RBS-008` |
| `created_at` · `updated_at` | `timestamptz` † | system-derived | | |

**`UNIQUE (tenant_id, idempotency_key)` — this index is what makes a retry safe.** B3 says so in
its own note, and it is the whole of hard rule 6 for this module: **the second run of the ladder
on the same day queues nothing, because every key it computes is already in this index.** Worked,
from the fixture: running the ladder twice queues **248 notices in total, not 496**; the second
Done screen reads **0 queued** and names the 248 already sent (`RB-007`). `TC-RBS-4` goes red with
the key removed. ⚠ **It is a UNIQUE INDEX and not application code on purpose** — a retry arrives
concurrently, and two workers each finding no row and each writing one is exactly the race an
index refuses and a `SELECT`-then-`INSERT` does not.

⚠ **A volume runbook does not write a row per subject.** `BR-RBS-035`: a record row for anything
acted on or flagged, and a **count per outcome** in `runbook_runs.counts` for the rest. Read
validation over 80,000 meter-days writes **38** run records — 31 estimated, 7 queued — and a count
of 80,000 (`RB-042`, `TC-RBS-23`).

## 5 · `work_items` — everything waiting on a person, whatever raised it

| Field | Type/unit | Origin | Validation | Notes |
|---|---|---|---|---|
| `id` · `tenant_id` | `uuid` (uuid7) † | system-derived | RLS `FORCE` | |
| `source_kind` | `text` `[B3]` | system-derived | a Check's finding · an Action's exception · a cutover plan's human task `[B1]` | one table, three sources |
| `source_run_id` | `uuid` NULL † | system-derived | **provenance back to the run that raised it** `[B1]` | null for a human task |
| `fingerprint` | `text` NOT NULL `[B3]` | system-derived | **upserted by fingerprint** | `BR-RBS-017` |
| `title` | `text` `[B3]` | system-derived | what a clerk reads on `RBS-007` | |
| `weight` | `integer` † `[B3]` | system-derived | how the list orders itself | |
| `subject_ref` | `text` `[B3]` | system-derived | the row it is about | |
| `fix_route` | `text` `[B3]` | system-derived | the screen that fixes it | `BR-RBS-011` |
| `owner_user_id` | `uuid` NULL `[B3]` | user-input | assigned from `RBS-007` | |
| `due_on` | `date` `[B3]` | user-input | | |
| `status` | `text` `[B3]` | system-derived / user-input | assign · resolve · reopen (`PATCH /work-items/{id}`) | |
| `resolved_at` | `timestamptz` NULL `[B3]` | system-derived | | |
| `created_at` · `updated_at` | `timestamptz` † | system-derived | the age a clerk sees is `created_at`, not the last sighting | |

**`UNIQUE (tenant_id, fingerprint)` †** is what the upsert needs. **The daily pre-bill sweep
raises the same missing read for thirty days; that must be one item ageing, not thirty items**
`[B3]`. `TC-RBS-10`: thirty daily sweeps over one missing read produce **one** work item, thirty
days old; it goes red on an insert instead of an upsert.

⚠ **The engine writes this table, never a runbook.** A Check produces findings; the engine upserts
them when the run closes. **That is how a Check populates the work list while being constructed
with no writer at all** (`BR-RBS-022`) — and it is why *raise a work item* is **not** a port. See
`D-1`.

## 6 · `cutover_plans` — a go-live plan, one per cutover

| Field | Type/unit | Origin | Validation | Notes |
|---|---|---|---|---|
| `id` · `tenant_id` | `uuid` (uuid7) † | system-derived | RLS `FORCE` | |
| `name` | `text` `[B3]` | user-input | | |
| `go_live_on` | `date` `[B3]` | user-input | | |
| `status` | `text` `[B3]` | system-derived / user-input | **open or closed is what orders the library** | `BR-RBS-026`: Onboarding & Cutover sorts first while it is open, last once it closes |
| `closed_at` | `timestamptz` NULL `[B3]` | system-derived | | |
| `created_at` · `updated_at` | `timestamptz` † | system-derived | | |

Added in B3's last pass; before it, `cutover_plan_items` referenced a plan that had no table.

## 7 · `cutover_plan_items` — the plan's tasks, some backed by a runbook

| Field | Type/unit | Origin | Validation | Notes |
|---|---|---|---|---|
| `id` · `tenant_id` | `uuid` (uuid7) † | system-derived | RLS `FORCE` | |
| `plan_id` | `uuid` NOT NULL `[B3]` | system-derived | FK to `cutover_plans` | |
| `seq` | `integer` `[B3]` | user-input | the item's position; `PATCH /cutover-plans/{id}/items/{seq}` addresses it | |
| `title` | `text` `[B3]` | user-input | | |
| `owner` | `text` / `uuid` † `[B3]` | user-input | B3 names the column and not whether it is a user reference | resolved by the build lane |
| `due_on` | `date` `[B3]` | user-input | | |
| `runbook_key` | `text` NULL `[B3]` | user-input | **a null key is a human task the engine never performs** `[B3]` | |
| `last_run_id` | `uuid` NULL `[B3]` | system-derived | the run whose result is this item's evidence | `RB-035` |
| `evidence_ref` | `text` NULL `[B3]` | system-derived | the run id and its figures, stored on the item | *"Evidence attached · $1,204.05 variance"* |
| `status` | `text` `[B3]` | system-derived / user-input | goes green on a zero-variance re-run | |
| `created_at` · `updated_at` | `timestamptz` † | system-derived | | |

---

## 8 · Three modelling decisions B3 defends, kept here with what it costs to skip each

| Decision | Why, in one line | What it costs to skip |
|---|---|---|
| **The plan and the outcome share one row** | *"What did it say it would do versus what it did"* **is the audit** | Two tables make the comparison a join, and the audit becomes a query nobody writes |
| **Findings are not their own table** | A Check's finding is a run record whose `planned_action` is `report` — one shape, one query, one CSV writer | A second table, a second renderer and two answers to *what did this run find* |
| **The work item is separate, and upserted by fingerprint** | Thirty daily sweeps over one missing read are **one item ageing** | Thirty rows for one problem, and a work list nobody can read after a fortnight |
| **The report is frozen on the run** | `report(jsonb)` is the block list as composed at close; a later change to a report function never alters a past result | A result screen that reads differently every time the code moves — the thing a regulator asks for, gone |
| **`UNIQUE (tenant, idempotency_key)`** | A retry is refused **by the database**, concurrently-safe | 496 notices instead of 248, and no test that can see it |

---

## 9 · Seams and ports — where this module reaches out, and never writes

**Three routes to the database and no fourth** (spec B1): the engine writes the module's own seven
tables · an Action writes another module's data **only through a port**, after the gate · every
read goes through **a seam file this module owns**, under the tenant context with RLS forced. **No
raw SQL, no cross-module queryset, no HTTP client anywhere in the module** (`BR-RBS-039`,
`TC-RBS-25` — an import census).

### The nine read seams — one file per module read

| Seam | What crosses | Direction |
|---|---|---|
| `operations → customers` | accounts, contacts, flags, protections | read only |
| `operations → metering` | premises, units, meters, reads, meter-days | read only |
| `operations → rating` | plans, rate schedules, tariffs | read only |
| `operations → billing` | bills, bill runs, break lists | read only |
| `operations → payments` | payments, deposits, plans in flight, bank lines | read only |
| `operations → ledger` | period postings, journal lines | read only |
| `operations → notifications` | what was queued, and to which channel | read only |
| `operations → tenancy` | settings — **policy is read, never duplicated** (`RBR-03`) | read only |
| `operations → integrations` | a landed batch, for the three events | read only |

**A selector that does not exist yet is added by the module that owns the table, never by this
module reaching past it** (spec B2b). Every seam is **a row in the cross-module interface
register**, added in the same commit as the file.

### The thirteen ports — the only way a runbook writes

| Port | Owning module | What it does |
|---|---|---|
| `queue_notice` | notifications | Writes a queue row; the dispatcher sends |
| `queue_receipt` | notifications | A receipt document to the queue |
| `apply_payment` | payments | Applies a landed payment by the allocation order |
| `post_credit` | payments | A credit to an open account |
| `raise_refund` | payments | A refund awaiting its own approval |
| `apply_fee` | billing | A fee by rule, behind the second approval (`BR-RBS-018`) |
| `record_match` | payments | A bank line matched to a deposit batch |
| `write_read` | metering | A validated meter-day as a read, source stamped |
| `apply_premise_change` | metering | One field on one premise, before-and-after kept |
| `suppress_channel` | customers | A contact channel marked undeliverable, dated |
| `flag_account` | customers | A flag with a reason |
| `flag_meter` | metering | *"Told about a leak on"* a date |
| `schedule_retry` | payments | A retry of a failed debit |

Each maps to **one service function in the owning module**, each is **idempotent per record**, and
each writes **its own audit row with the runbook as actor** (`BR-RBS-015`, blocked on the audit
module). **A Check holds none of them** — the list is empty at construction, so a write is
*unavailable*, not refused (`BR-RBS-002`). **A new runbook needing a new port is adding a reviewed
interface, not a custom write.**

---

## Discrepancies & gaps — verified against the source and the repo at `6fed5da8`

| # | Where | Finding | Disposition |
|---|---|---|---|
| **D-1** | spec **A5/B1** vs **B2b** | **THE SOURCE CONTRADICTS ITSELF ON THE PORTS.** The architecture section says *"a small allow-list of named calls… queue a notice, flag an account, **raise a work item**, apply a fee"* and its write-routes table says **"four named calls"**; `RB-052` repeats *"the four port seams"*. **B2b's contract lists THIRTEEN ports** and states in its own figure that **raising work items and writing audit rows are ENGINE acts, not ports** — which is what lets a Check populate the work list while holding no writer at all. `RB-017` is titled *"Thirteen ports"*, the absence register carries the same sentence, and the market study calls Kraken's approved-action layer *"our thirteen ports under another name"*. | **THIRTEEN, and `raise_work_item` is NOT one of them.** The architecture prose is stale in two ways at once — the count and the membership — and B2b is the contract. Written thirteen throughout §9 above. ⚠ A lane building the four-call version gives every Check a writer, which is `BR-RBS-002` gone. |
| **D-2** | `runbook_run_records.amount` | **No currency column.** B3 gives `amount(18,4)` and names no `CHAR(3)` beside it, while hard rule 2 requires one wherever money is stored. The fixture's own figures are dollars (`$412,880.4400`, `$1,204.0500`) and every screen draws `$`. | **A GAP, not a column added here.** Either the amount is always the tenant's own currency and the column is derivable, or it is not and the table needs `currency CHAR(3)`. That is a schema decision for the B2 anchoring task, recorded so it is decided rather than defaulted. |
| **D-3** | `runbook_versions.definition` | **`money` and `percent` parameters live in `jsonb`**, where no column type holds them to 4 and 6 decimals. | The precision is the parameter renderer's and the validator's; `RB-021`'s *done looks like* already says a money field **shows two decimals and stores four** on `RBS-004.3`/`RBS-004.5`. Named here so a build lane does not assume the database is enforcing it. |
| **D-4** | `work_items` vs `apps/work` | **A name that reads like a collision and is not one.** The `work` module (CLAUDE.md module map, `CR-070`) owns crews, technicians, parts, **work orders**, templates, assignments, schedules and labour rates. `work_items` is this module's table — findings, exceptions and human tasks, one shared surface — and no `work_items` table exists in the codebase today (grep: one unrelated key, `metering/sample_data.py:2398`). The category **Work** in the sixteen names the `work` module as the owner of the ports a Work-category runbook may call; it holds **no runbook yet** and is never drawn (`BR-RBS-025`). | Kept as B3 names it. ⚠ **Two things named *work* in one product is a support question waiting to happen**, and runbook 29 (*Overdue field orders*) reads BOTH: it waits on the Work module and it raises work items. Recorded, not renamed — a rename is a decision, and the specification has not been through the change process. |
| **D-5** | module directory | **The source says `apps/operations` everywhere**; this repo builds **`apps/runbooks`** after the PO's naming ruling of 2026-09-06, while the nav route stays `/{tenant}/operations` as the wireframes draw it and the seam files keep the `operations → <module>` pair naming. | Recorded here so the three names are deliberate and none looks like a typo. The nav word is settled when the section name is. |
| **D-6** | B2 schema brief | **None of the seven tables is anchored in `04-docs/02-decisions/02-database-design-brief.md`** (grepped: `runbook_runs`, `runbook_run_records`, `cutover_plan`, `work_items` — zero hits). | `I-2`'s shape from integrations, and it closes the same way: a `### Module: runbooks` section in the brief, in the same commit as the first migration, **before `runbooks/0001` is written**. Not done here — this documentation pass does not edit B2. |
| **D-7** | `cutover_plan_items.owner` | B3 names the column and not whether it holds a user id or a typed name. Every other actor column in the seven (`changed_by`, `approved_by`, `stopped_by`, `decided_by`, `owner_user_id`) is a `uuid`. | Left as `text` / `uuid` **unresolved** rather than guessed. A cutover plan's owner may legitimately be a person outside the tenant's user table — the implementer — which is exactly why it is not assumed. |
| **D-8** | `12-the-contract.md` **§5** vs **§8** | **THE CATEGORY CANNOT BE THE PORT ALLOW-LIST, AND ENFORCING IT WOULD REFUSE EVERY ACTION THIS MODULE DEFINES (`DEF-RBS-4262`, found by `CR-075` wave B writing the construction checks).** §5 and `BR-RBS-024` both end *"the category names the owning module whose ports it may call"*, and §5 spells it out — *"a Collections runbook reaches `payments`' ports and no other module's"*. §8's coverage table, one page later, breaks it everywhere: runbook 8 is **Collections** (owning module `payments`) and holds `queue_notice` (`notifications`) and `apply_fee` (`billing`); runbook 14 is **Finance** (owning module `ledger`, which owns **no ports at all**) and holds `record_match` (`payments`); runbooks 20, 21 and 22 are **Data Sync** (`integrations`, which owns none) and hold `apply_premise_change`, `write_read`, `suppress_channel` and `flag_account`. **Counted: 15 of the 21 port bindings in §8 break the sentence, and 9 of the 9 Actions break it at least once.** | **Read the sentence as PROVENANCE — the module the runbook is ABOUT — and NOT as a restriction.** The allow-list is the runbook's own `ports[]`, which §8 itself calls *the whole safety story*. `apps/runbooks/contract.py` enforces membership in the thirteen and emptiness for a Check, and declines this one by name; `BR-RBS-024`'s status cell carries the same note, dated 2026-09-06. A conformance case pins the reading, so a lane that later adds the restriction meets a red naming the defect rather than nine runbooks that stop loading. |
