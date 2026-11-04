# runbooks — Flows & States

Screens: **`RBS-001`** Runbooks home · **`RBS-002`** Templates · **`RBS-003`** My runbooks ·
**`RBS-004`** Runbook detail · **`RBS-005`** Run wizard · **`RBS-006`** Run result ·
**`RBS-007`** Work list · **`RBS-008`** Run history (PO ruling 2026-09-06). States are dotted
(`RBS-005.3`); the per-runbook renderer instances are `-Rn` (`RBS-004-R8`, `RBS-006-R8`).
Wireframes and their build sheets: `04-docs/05-modules/17-runbooks/wireframes/`.

Sequences extracted from the specification's **B2 Interaction diagrams** (figures 31–33) and the
run lifecycle from **B1** (figure 30). ⚠ **The source draws these against its own screen numbers
`S147`–`S154`; they are translated to `RBS-001`–`RBS-008` here by the mapping the decision log
carries, and the source documents are NOT renamed** — re-lettering them would break every
cross-reference. **Where the source's own sequence names a screen inconsistently with its screen
inventory, the inventory wins and the divergence is stamped inline below.**

Nothing here is ratified: the specification decides nothing that is the PO's, and B6's rules are
all `PROPOSED` bar `BR-RBS-013`. Read `02-business-rules.md` before building from a sequence.

---

## 1 · Sequence A — a Check, run by hand: *"Can we bill?"*

*Source figure 31 · specification B2 sequence A.*

```
Clerk       ──▶  RBS-001  presses Run on a Check
RBS-001     ──▶  POST /runbooks/{key}/runs  {mode: "check"}
API         ──▶  engine   create run · status = running · PIN SCOPE
engine      ──▶  tenancy · rating · metering · customers    READ ONLY, NO WRITER BOUND
engine      ──▶  runbook_run_records  (planned_action = report)
                 3 blockers · 6 warnings · each with a fix route
engine      ──▶  work_items  upsert one per open finding (idempotent by fingerprint)
API         ◀──  202 + job id     · under 5,000 records it answers 200 inline
RBS-006     ──▶  renders findings, each linking to the screen that fixes it
```

**The property that matters, and it is the whole safety story:** *"no branch of this sequence can
write to another module. The engine constructs the Check with no action ports bound, so a write is
not refused at runtime — it is **unavailable**."* (`BR-RBS-002`; `TC-RBS-1` goes red when a port
is bound to a Check, and it must fail loudly at **construction**, not at the call.)

**Two engine acts appear in this sequence and neither is a port** (`BR-RBS-022`): the run records
are the engine writing its own table, and `work_items` is the engine upserting findings **when the
run closes**. That is how a Check populates the work list while holding no writer at all.

⚠ **Stamped divergence.** The source's figure 31 ends *"S150 ──▶ renders findings"*. `S150` is
**Runbook detail** (`RBS-004`) in the same document's own screen inventory; the screen that draws
a run's result is `S152` — **`RBS-006`** — and `GET /runbooks/runs/{id}/report` is what it reads.
Written as `RBS-006` above. This is the same class of slip the specification's pass-5 staleness
stamp already caught twice (*"story 006 and phase 1c cited the work list as S151; it is S153"*).

**Work-item ageing, in one line:** thirty daily sweeps over one missing read leave **one** item,
thirty days old (`BR-RBS-017`, `TC-RBS-10`) — the upsert is on `fingerprint`, not an insert.

---

## 2 · Sequence B — a scheduled Action: the collections ladder

*Source figure 32 · specification B2 sequence B.*

```
scheduler   ──▶  jobs  enqueue operations.runbook.act · Monday 07:00 TENANT LOCAL
engine      ──▶  resolve scope · PIN 1,004 account ids to the run
engine      ──▶  evaluate per record IN A SAVEPOINT · NO WRITES YET
engine      ──▶  runbook_run_records  (the plan)
                 812 to send · 97 skipped · 95 need a person
engine      ──▶  cap check  812 > 400  ──▶  status = awaiting_approval, BLOCKED
notifications ──▶ staff alert: "A run needs you"  (in-app bell; no vendor needed)
Clerk       ──▶  RBS-003  narrows scope, or raises the cap deliberately
Clerk       ──▶  POST /runbooks/runs/{id}/approve  {approved_count: 400}
engine      ──▶  notifications.queue_document()  ×400 · idempotency key per record
engine      ──▶  audit_log  ×400 · actor = runbook, version 3
engine      ──▶  work_items  95 exceptions  ·  results CSV ×2
```

**Two things to read here, both from the source:** *"the cap does not truncate — the run stops and
asks"* (`BR-RBS-006`; `TC-RBS-3` must first fail on a build that truncates to 400), and *"the
approval carries a count, so a clerk who approves a plan that has since changed gets a conflict
rather than a surprise"* (`BR-RBS-005`; approving with 812 after the plan moved to 806 returns
**409** and queues nothing — `TC-RBS-8`).

**Where the clerk actually stands.** The cap refusal is `RBS-005.7` — *"Too many for one run"*
with **Narrow scope · Raise limit · Send first 400** as the clerk's own three choices, and **no
notice is queued until one is pressed** (`RB-004`). The approval is `RBS-005.4`, which is a
danger-tier commit behind a consequence box: *"Queue 400 notices now. / Charge no fees. None are
due. / Leave 412 for next run. / Leave 95 accounts for you."* (B14 rules 6, 11 and 33).

**Stop is reachable at every moment** (`RBR-02`): pressing Stop at 120 of 400 leaves the run
`stopped` with **120 queued, 280 untouched**, and the result reads *"Re-run would send 280"*
(`RB-005`, `TC-RBS-9` — a stop that only sets a flag nothing reads must go red).

⚠ **Stamped divergence, second one.** The figure calls the port `notifications.queue_document()`
and is quoted verbatim above; **B2b's port table names it `queue_notice`** (with `queue_receipt`
beside it for a receipt document). One port, two spellings, one document. `03-field-map.md` §9
carries the contract's thirteen names, which is the list a build lane implements.

**The re-run is the idempotency proof, in the browser rather than a unit test** (`J-RBS-3`):
running the ladder twice on the same day queues **248 in total, not 496**, because
`UNIQUE (tenant_id, idempotency_key)` refuses the second write (`BR-RBS-008`, `TC-RBS-4`).

⚠ **Every notice is `Queued`, never `Sent`** — no delivery provider is connected, PO ruling
17 August 2026. The word on every result screen is *queued*.

⚠ **`audit_log` actor = *the runbook, version 3* is NOT available yet.** An automated action has
no identity in the platform today: a blank actor means *a system job*, so every automation is
indistinguishable. `BR-RBS-015` / `RB-011` is **BLOCKED on the audit module and must land before
any Action writes anything** — *"or a person will appear to have personally sent 812 letters at
07:00 on a Monday."*

---

## 3 · Sequence C — a cutover plan calling a runbook

*Source figure 33 · specification B2 sequence C.*

```
Implementer ──▶  cutover plan item "Reconcile opening balances"
plan item   ──▶  POST /runbooks/cutover-reconciliation/runs
engine      ──▶  compares loaded balances to the uploaded legacy trial balance
engine      ──▶  runbook_run_records
                 12 accounts disagree · total variance $1,204.05
plan item   ◀──  status = evidence attached · run id + figures stored on the item
Implementer ──▶  resolves 12 · re-runs · item goes green on a zero-variance result
```

**This is the whole integration between a plan and the engine**: a plan item **optionally** names
a runbook (`cutover_plan_items.runbook_key`), and the run's result becomes the item's evidence
(`last_run_id`, `evidence_ref`). **A null `runbook_key` is a human task the engine never
performs** — completed by a person attaching a file or ticking it.

**The arithmetic runs at four decimals and displays at two** (hard rule 2): the fixture holds a
legacy trial balance of `$412,880.4400` against loaded balances differing on 12 accounts by
`$1,204.0500`, and the screen reads `$1,204.05`.

⚠ **`RB-035` waits on OPEN decision 8** — whether the cutover plan is a product screen now or a
spreadsheet for the first two customers. Until that is ruled, the plan half of this sequence is
specified and not built.

⚠ **Most cutover steps have no executor, and the cutover plan is NOT a runbook** (the source's own
absence register). *The plan shares the work list, not the engine.* Ruled by the specification on
4 September 2026 — **the PO was not asked**, so it stays visible to overrule.

---

## 4 · The run lifecycle — six steps, and Checks skip two of them

*Source figure 30 · specification B1 "How a run moves". The engine is the process; a runbook is
the logic registered against it.*

```
1 · TRIGGER    Fire            Manual, schedule or event. A job is enqueued.
      │                        ⤷ one runner, not two: operations.runbook.check
      │                          and operations.runbook.act are job kinds on the
      │                          platform's existing job runner (RBR-08: one run
      │                          per runbook at a time; a second Run is refused)
      ▼
2 · SCOPE      Resolve and pin The id list is FROZEN and stored with the run.
      │                        ⤷ each runbook declares its own resolve function —
      │                          there is deliberately no shared query abstraction
      │                        ⤷ BR-RBS-009 · TC-RBS-22: an account becoming past
      │                          due after the run starts is absent from the plan
      ▼
3 · EVALUATE   Checks, no writes  Per record, IN A SAVEPOINT. Findings accumulate.
      │                        ⤷ a step declares its mode: per_record (once per
      │                          subject, own savepoint) or set (once over the
      │                          whole pinned set) — BR-RBS-023 · TC-RBS-17
      │                        ⤷ guards are evaluated BEFORE any step, and win
      │                          over every check — BR-RBS-012 · TC-RBS-6
      ▼
4 · GATE       Approve the batch  CHECKS SKIP THIS. ACTIONS CANNOT.
      │                        ⤷ the approval carries the count; a moved plan
      │                          conflicts — BR-RBS-005 · 409
      │                        ⤷ a money-bearing action carries a SECOND approval
      │                          — BR-RBS-018, threshold open (decision 3)
      ▼
5 · ACT        Through the ports  Idempotent per record. Cap enforced. Stoppable.
      │                        ⤷ thirteen ports, each one service function in its
      │                          owning module; a Check holds NONE
      ▼
6 · CLOSE      Result and audit   Two files, work items raised, audit rows written.
                                 ⤷ the report is composed ONCE, at close, from the
                                   twelve blocks, and frozen — BR-RBS-020
                                 ⤷ a report naming a thirteenth block is refused
                                   AT CLOSE, never at render — TC-RBS-16
```

**A Check's wizard is four steps, not six** — it skips **Gate** and **Act** entirely (`RB-001`;
ruled by the specification on 4 September 2026, the PO not asked). On screen that is the step rail
of `RBS-005`: *Scope · Checking · Review · Approve · Applying · Done* for an Action, and the same
rail without Approve and Applying for a Check.

**Every step is listed before the first one starts** (`RBR-01`), each filling in as it completes,
and **any step that does not run carries the reason it did not** — including *"Never reached"*.
That is not invented here: it is the pattern the product already uses when it seeds a new utility,
adopted because the PO asked to see all the steps up front rather than watch a list grow.

### The run status machine — `runbook_runs.status`

```
                    ┌────────────── an Action, cap not reached, gate satisfied ─────────────┐
                    │                                                                        ▼
queued ──▶ running ─┼──▶ awaiting_approval ──approve {approved_count}──▶ approved ──▶ acting ──▶ done
   │          │     │            │                     │                                │
   │          │     │            │                     └── count ≠ current plan ──▶ 409, NOTHING QUEUED
   │          │     └──── a Check: no gate exists on this path ──────────────────────────▶ done
   │          │
   │          ├──▶ failed    (a missed schedule firing RAISES rather than silently catching up)
   │          └──▶ stopped   (Stop, at any moment: records already acted STAY acted)
   └──────────────▶ failed   (the job never started)
```

- `awaiting_approval` is also where the **cap** parks a run: 812 planned against a limit of 400
  **blocks** and asks; it never truncates to 400 (`BR-RBS-006`).
- **A required Check runs first as its own run** and is linked from step 1 of the caller through
  `runbook_runs.parent_run_id`; a failed requirement stops the caller and every later step reads
  *"Never reached"* (`BR-RBS-027`, `TC-RBS-21`).
- **An edited Action re-enters dry run.** After any edit, Run offers **only** a dry run until one
  clean dry run of the new version has been reviewed (`BR-RBS-036`, the trust ratchet).
- **The version is pinned at start** and the run's stored plan and report never change afterwards
  (`BR-RBS-038`): a result screen from last month reads exactly as it did.

### Where each step may touch the database — three routes and no fourth

| Route | Who writes | What | Who may not |
|---|---|---|---|
| **1 · this module's own seven tables** | the engine | the definition and its versions, runs, pinned scope, run records, decisions, work items, cutover plans | **a runbook's step code never writes these directly** — it returns findings and the engine records them |
| **2 · the ports** | an Action, through the engine, **after the gate** | thirteen named calls into the owning module's service, each idempotent per record, each writing its own audit row with the runbook as actor | **a Check is constructed with no ports**, so a write from a Check is a construction error, not a runtime one |
| **3 · reads** | any runbook | through each module's query layer, under the tenant context with RLS **forced** | **no raw SQL, no cross-tenant queryset** — a scope function that forgets the tenant is refused by the database, not by a reviewer |

⚠ **THE SOURCE CONTRADICTS ITSELF ON ROUTE 2 AND THE CONTRACT WINS.** Its architecture section
says *"four named calls… queue a notice, flag an account, **raise a work item**, apply a fee"*.
Its contract section lists **thirteen** ports and states that **raising work items and writing
audit rows are engine acts, never ports** — which is precisely what lets a Check populate the work
list while holding no writer. `RB-017` is titled *"Thirteen ports"* and the market study calls
them *"our thirteen ports"*. **Thirteen, and `raise_work_item` is not one of them**
(`03-field-map.md` §9 lists them; discrepancy `D-1`).

---

## 5 · The three journeys these sequences are proved by, in a real browser

| Journey | Steps | The assertion that makes it worth running |
|---|---|---|
| `J-RBS-1` · Get to billable | Open Runbooks → run *Can we bill?* → open the work list → fix the tax region → re-run | The blocker count falls from **3 to 2** and the work item **closes itself** — proving the item is derived, not hand-managed |
| `J-RBS-2` · Prove it on their data | Run the coverage grid → click a red cell → read the refusal → fix the rate → re-run | The grid moves from **21 clean to 23**, and the refusal sentence on screen is **the engine's own**, not a second implementation's |
| `J-RBS-3` · A guarded send | Run the ladder dry → confirm 97 skipped → approve 400 → stop at 120 → re-run | **120 acted, 280 untouched**, and the re-run queues **280 rather than 400** — the idempotency key doing its job in a browser |

⚠ **No journey file exists in `08-qa/01-e2e/journeys/` for any of these.** The ids are the
specification's own (`J-RBS-1`…`3`), they are **not** in the platform's `J##` series, and nothing
has been reserved for them. Hard-won law 1: this table describes three journeys, it does not claim
three files.

⚠ **`TC-RBS-5` is the one that will be got wrong.** The savepoint case (step 3 above) **cannot be
proved on the default suite** — `config/settings/test.py` hardcodes in-memory SQLite, which has no
aborted-transaction state, so a skip-and-continue written the obvious way passes everywhere and
loses the run the first time PostgreSQL refuses a row. It must be marked as requiring PostgreSQL
and run there (`RB-038`), **or it proves nothing** (CLAUDE.md hard-won law 14).
