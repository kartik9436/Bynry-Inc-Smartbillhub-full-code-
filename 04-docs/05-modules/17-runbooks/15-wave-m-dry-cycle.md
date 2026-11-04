# Wave `M` — a full cycle, dry, in production · the evidence and the go/no-go

> `CR-075` wave `M`, tasks `M1`–`M4`. Written 2026-09-06 by the build lane that
> ran it. **This wave produced no feature. It produced this document, and the
> five defects it names.**

---

> ⚠ **THE VERDICT WAS RE-TAKEN ON 2026-09-07 AND IT IS STILL `NO-GO` — SEE §8
> BELOW, WHICH IS THE CURRENT ONE.** Everything above §8 is the cycle of
> 2026-09-06 and is left exactly as it was written: it is a dated measurement of
> a build that no longer exists, and three of the six things it found have since
> been fixed. **Read §8 for what is true today.** The second cycle is closer to a
> `GO` than the first — a live run now binds its writer, queues 812 notices
> rather than 0, and the ladder climbs — and it fails on the same sentence for a
> different reason: **a clerk still cannot read the plan, and there is still
> nothing that approves one.**

## The answer first — **NO-GO for the live half**

**Wave `N` does not start.** The dry cycle did its job: it found six things, and
three of them mean the live half would not do what wave `N` promises. The plan's
own sentence for this moment is *"if the plans were wrong, the live half does not
start"* — the plans are not wrong, but **nobody can read them and nothing would
be sent**, which is the same verdict for a different reason.

`N1` is written in the plan as *"a ONE-LINE change on machinery already
watched … a wave that needs more than this has proved the dry half was not the
same code."* That test has now been run and it comes back the second way. The
five conditions below are what a `GO` needs.

---

## 1 · What was run

**The board.** `L9`'s ladder set did not exist — measured on the seeded demo
tenant, `collections_ladder` resolved **zero** subjects, and a month of dry runs
over an empty board is evidence of nothing (hard-won law 7). So it was built:
`10-scripts/render-checks/rbs_m_seed_ladder.py` puts **1,004 past-due accounts**
on the real `brazosbend` tenant, on top of the **31** debtors the seed already
had — **1,035 accounts with an outstanding position**.

| group | n | why it is on the board |
|---|---:|---|
| reminder due | 300 | rung 1 of `BR-PAY-017` |
| 10-day notice due | 250 | seeded at `friendly` |
| 5-day notice due | 170 | seeded at `first_10_day` |
| final certified letter due | 92 | seeded at `second_5_day` |
| payment plan in good standing | 43 | `BR-CUS-043`'s pause |
| protected — 26 medical · 2 dispute · 3 sample | 31 | the three guards |
| bad address on file | 23 | `accounts.bad_address` |
| under the $25.00 collection floor | 95 | payments' own floor |
| **total** | **1,004** | |

**The cycle.** Five firings, one per Monday, **3 August to 31 August 2026**,
started by hand — `10-scripts/render-checks/rbs_m_dry_cycle.py`.

| # | business day | took | To send | Skipped | new record rows | audit rows | outside the seven tables |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | 2026-08-03 | 15.8s | **835** | 200 | 835 | 835 | none |
| 2 | 2026-08-10 | 15.4s | 0 | 1,035 | 0 | 835 | none |
| 3 | 2026-08-17 | 15.1s | 0 | 1,035 | 0 | 835 | none |
| 4 | 2026-08-24 | 15.8s | **43** | 992 | 43 | 878 | none |
| 5 | 2026-08-31 | 15.3s | 0 | 1,035 | 0 | 878 | none |

Firing 1's 835 by rung: **323 reminder · 250 ten-day · 170 five-day · 92
certified final.** Firing 4's 43 are the payment-plan accounts whose first
instalment fell due on 23 August, so the plan stopped being *current* and
`BR-CUS-043`'s pause lifted — the ladder behaving exactly as payments' law says
it should, a week later, with nobody touching anything.

**Across the month: 878 notices planned for 878 accounts, never one twice.** The
per-record idempotency key — `runbook · action · subject · rung` — holds.

**62 accounts were guarded and never walked at all**: the fixture's 31 (medical,
dispute, sample) and **31 of the demo estate's own sample accounts**.
`BR-RBS-014` works, and the demo data cannot be chased.

---

## 2 · What the database diff says (`M2`)

**Nothing outside this module's seven tables was written on any of the five
firings, except `audit_log`, which is required to move.**

⚠ **`M2` asks for "zero rows outside the seven tables" and that is the WRONG
assertion.** `BR-RBS-022` puts the audit row in the engine so that even a Check
leaves a trail, and hard rule 7 says every money action writes one. `audit_log`
is the one table a runbook is supposed to write outside itself. A blanket
exemption would be the hole a real foreign write hides in, so the check asserts
it **to the row**: exactly one audit row per act, every firing. It held on all
five — 835, 835, 835, 878, 878.

**Proved RED first, and it took three tries because two of them were the check
lying to itself:**

1. **Bound writer, mode left at dry.** All ports stayed unbound, the diff went
   red on the *audit* row, and it read like a pass of the red proof. It was not
   one — the check had never been shown to catch a foreign write.
2. **Mode forced live, writer bound.** All 835 acts came back **`held`**: the
   real `queue_notice` refuses a row that names no template (`DEF-RBS-4343`).
   Nothing was written anywhere, so the diff still could not go red.
3. **Mode live, writer bound, and the missing template supplied — nothing
   else.** One firing wrote **1,670 outbound messages** (two channels × 835) and
   **2,505 audit rows**, and the diff named both: `outbound_messages 337 → 2007`
   and *"audit_log +2505, expected +835"*.

⚠ **And the check had law 7's own disease.** Built from *the tables that moved*,
the audit assertion could not fire when **nothing** was audited — and firings 2-5
of the first cycle wrote 835 acts, zero audit rows, and were reported **clean**.
That is *reporting zero over a scope it silently excludes*, inside the check
written to obey law 7, and it was found by reading the output rather than the
exit code. It now measures the audit tables themselves.

---

## 3 · What a person saw on `RBS-006` (`M3`)

**A stack trace.** Verbatim, in Chromium, on a freshly built bundle, opening the
first firing's run at `/brazosbend/runbooks/collections_ladder/runs/{id}`:

> **Unexpected Application Error!**
> Cannot read properties of undefined (reading '0')

None of the five tiles reach the screen. The per-rung table does not draw. The
835 planned notices are not readable anywhere in the product. `DEF-RBS-4352`.

The cause is a contract that exists twice and is checked in neither place the
data actually crosses:

| block | what runbook 8 sends | what the renderer needs |
|---|---|---|
| `breakdown` | `by, rows, rungs` | `heading, columns, rows` |
| `records` | `rows, stopped_before_the_rest` | `columns, rows, total, empty` |
| `downloads` | `files:[{name, outcome}]` | `files:[{id, label, format}]` |

The backend conformance suite refuses a thirteenth block **name** and never looks
at a payload; `types.ts` declares all twelve payloads and never meets the JSON,
because `GET /runbooks/runs/{id}/report` is a deliberate passthrough. Every unit
test asserts the dict the runbook builds rather than the shape the screen
consumes, so all of them pass over a screen that cannot render.

---

## 4 · The six findings

| id | what | why it decides the go/no-go |
|---|---|---|
| `DEF-RBS-4340` | **The ladder could not complete one run.** `acts.plan()` wrote the port's payload into a `jsonb` column verbatim and an `AutomationActor` is not JSON — `TypeError` on the FIRST record of the FIRST firing. **FIXED in this wave**, one line, `core_audit.jsonable`. | It was the whole acting half, unrunnable, with every test green. Fixed, so it does not block `N`. |
| `DEF-RBS-4345` | **A live run executes as a dry run.** `services.run_to_completion` never passes the run's mode to the executor, so `runbook_runs.mode` can read `live` while `build_context` is told `dry` and binds no writer. | **`N1` is not a one-line change.** Flip the mode today and nothing happens at all. |
| `DEF-RBS-4343` | **With a writer bound, all 835 acts are refused.** `queue_notice` is called with no template and no recipients, and `queue_document` refuses a row it cannot render. | **The live half would queue nothing.** Wave `N`'s goal is *248 notices queued*; it would be 0. |
| `DEF-RBS-4347` | **The ladder never climbs.** The runbook queues the notice and records nothing else: `account_collection_state` held 512 rows before the cycle and 512 after, `notice_history` held 0 and 0. | Every customer would get the reminder **and never** the 10-day, 5-day or certified letter. The key then guarantees they never get one again. |
| `DEF-RBS-4348` | **"Check the address works" cannot skip anybody.** It asks whether the ACCOUNT exists, not whether the address does; 23 accounts flagged `bad_address` were all planned a notice and `undeliverable` is unreachable. | Letters posted into the void, and a clerk with no way to see it. |
| `DEF-RBS-4352` | **`RBS-006` crashes on the ladder's result.** | **`M3` cannot be completed.** A plan nobody can read is a plan nobody can approve. |

⚠ **A seventh thing is not a defect and is worth as much: the trust ratchet
works.** `BR-RBS-036` refused the first live run outright —
`runbooks.refusal.dry_run_first` — and there is no route in the product that
clears it, because approving a plan is `L3` and `L3` is not built. The sabotage
had to clear it by hand and says so out loud.

---

## 5 · What a `GO` needs — five conditions, all testable

1. **`DEF-RBS-4352` closed and the plan read on screen.** A person opens
   `RBS-006`, sees *To send 835 · Skipped 200*, the four rungs, and a page of
   record rows. Until then no one can review what would be sent.
2. **`DEF-RBS-4345` closed** — a live run must actually bind a writer, proved by
   a case that opens a live run through `run_to_completion` and asserts
   `port.is_bound` inside the step.
3. **`DEF-RBS-4343` closed** — a template per rung and the account's contacts as
   recipients, proved by an outcome of `done` rather than `held`.
4. **`DEF-RBS-4347` closed, or ruled.** Whose act the tier advance is, is a real
   design question: `payments` owns `run_ladder` and the tier column, and a
   runbook that advanced it itself would be a second writer of a signed rule's
   state. **It is not a question for the Product Owner** (hard-won law 13) — it
   is ours to decide and write down — but it must be decided before a letter
   goes out, because a ladder that cannot climb is not a ladder.
5. **`L3` and `L4` built.** The batch approval carrying the server-side count and
   the cap that refuses a run are listed in wave `L` and are **not on the
   branch**: there is no approval endpoint, and `most_per_run` is a declared
   parameter that nothing enforces. **A run of 835 against a cap of 400 was not
   refused and was not truncated — the cap simply is not there.** Phase 2's
   whole safety story is *a person approves a plan of a known size*, and today
   neither half of that sentence is code.

**`DEF-RBS-4348` is not a blocker** — it costs 23 letters into the void out of
835, which is wrong and is not dangerous — but it should land with the rest.

---

## 6 · What this cycle did NOT soak, stated with its number

* **The scheduler.** `I2` (cron in the tenant's timezone) and `I3` (a missed
  firing raises) are phase 4, so **a person pressed Run five times**. The PLANS
  are soaked over a month; the SCHEDULER has never run once. Wave `I` needs its
  own soak and this cycle says nothing about it.
* **Elapsed time.** Five Mondays were replayed in one afternoon. The run-level
  duplicate check (`OQ-RBS-1737`) keys off the run row's REAL timestamp — rightly,
  it is a fact about the pass — so the first cycle's firings 2-5 came back
  *already sent* for every account **without ever reaching the per-record key**,
  and the run-level check took the credit for the per-record one. The cycle
  script now backdates each finished run to its business day and says so; the
  business days must be in the past for the same reason.
* **Failure.** *"Need a person"* read **0** on all five firings and cannot read
  anything else: `failed` is written only when a BOUND writer raises. `L9`'s
  *"one notice write failing a constraint"* and wave `L`'s *"95 needing a
  person"* are `L11`'s PostgreSQL cases, not a dry cycle's.
* **Scale.** 1,035 accounts took **15 seconds** a firing. The tenant ceiling is
  **40,000** (T5), and two reads in this path are per-account —
  `customers.disconnects.medical_hold_for` and `payments.dunning.
  collections_pause_for` — so the shape is linear with a database round trip per
  account. **Extrapolated, 40,000 accounts is about ten minutes a firing**, which
  is survivable for a weekly job and is a measurement nobody has taken properly.
  It is not a blocker and it is not evidence either; it is a number to re-take
  when a tenant of that size exists.

---

## 7 · How to re-run it

```
10-scripts/proof-db.sh clone rbsm --template <the newest sbh_tpl_*>
DATABASE_URL=…/sbh_clone_rbsm python3.12 \
  10-scripts/render-checks/rbs_m_seed_ladder.py --tenant brazosbend --first-monday 2026-08-03
DATABASE_URL=…/sbh_clone_rbsm python3.12 \
  10-scripts/render-checks/rbs_m_dry_cycle.py --tenant brazosbend \
  --mondays 2026-08-03,2026-08-10,2026-08-17,2026-08-24,2026-08-31 --out cycle.json

# the red proof — ON ITS OWN CLONE, because a bound writer burns the keys
DATABASE_URL=…/sbh_clone_rbsmred python3.12 \
  10-scripts/render-checks/rbs_m_dry_cycle.py --tenant brazosbend \
  --mondays 2026-08-03 --bind-writer

# the plans, read by a person
SMOKE_BASE=… SMOKE_RUN_FIRST=<firing 1> SMOKE_RUN_SECOND=<firing 2> \
  node 10-scripts/render-checks/rbs-m-the-cycle-on-screen.mjs
```

---

---

# 8 · The second cycle — 2026-09-07 — and the verdict is still **NO-GO**

> Run by the `CR-075` wave `M` lane on 2026-09-07, against the branch at
> `642a3cee`. Same scripts, same tenant, a fresh clone of the template built
> from that commit. **The first cycle measured a build that no longer exists**;
> three of its six findings had been fixed in the twenty hours between the two,
> so the go/no-go had to be taken again rather than inherited.

## 8.1 · The answer first

**Wave `N` still does not start**, and the reason has moved. On 2026-09-06 the
live half would have queued nothing at all. Today it would queue 812 notices
correctly, on the right accounts, at the right rungs, and climb the ladder —
**and no person could have read that plan before it went out, and no person
could have approved it, because neither the numbers nor the approval exists.**

Phase 2's promise is *a person approves a plan of a known size*. The size is
computed, stored and correct; it is not on the screen; and there is nothing to
press.

## 8.2 · What was run

**The board still does not exist in the seed, measured again.** One dry firing
on a fresh clone before seeding anything: the ladder resolved **31 subjects and
planned 0** — all 31 are the demo estate's own sample accounts, which the guards
skip. `L9`'s fixture is still nobody's, so it was rebuilt:
`rbs_m_seed_ladder.py` puts **1,004 past-due accounts** on the real
`brazosbend` tenant on top of the **31** debtors already there — **1,035
accounts with an outstanding position.**

| group | n | rung due |
|---|---:|---|
| reminder due | 300 | `friendly` |
| 10-day notice due | 250 | `first_10_day` |
| 5-day notice due | 170 | `second_5_day` |
| final certified letter due | 92 | `final_48_hour` |
| payment plan in good standing | 43 | skipped by `BR-CUS-043` |
| protected — 26 medical · 2 dispute · 3 sample | 31 | guarded, never walked |
| bad address on file | 23 | `undeliverable` |
| under the $25.00 collection floor | 95 | skipped by payments' floor |
| **total** | **1,004** | |

**Five firings, one per Monday, 3 to 31 August 2026, started by hand.**

| # | business day | took | To send | Skipped | records | audit rows | outside the seven tables |
|---:|---|---:|---:|---:|---:|---:|---|
| 1 | 2026-08-03 | 16.1s | **812** | 223 | 973 | 812 | none |
| 2 | 2026-08-10 | 16.9s | **812** | 223 | 973 | 812 | none |
| 3 | 2026-08-17 | 15.9s | **812** | 223 | 973 | 812 | none |
| 4 | 2026-08-24 | 17.1s | **855** | 180 | 973 | 855 | none |
| 5 | 2026-08-31 | 16.7s | **855** | 180 | 973 | 855 | none |

By rung, firings 1–3: **300 reminder · 250 ten-day · 170 five-day · 92 certified
final**. Firings 4 and 5 add the **43** payment-plan accounts whose first
instalment fell due on 23 August, so `BR-CUS-043`'s pause lifted on its own and
the reminder rung reads **343**.

**Of the 223 skipped, 62 were GUARDED and never walked at all** — the fixture's
31 and 31 of the demo estate's own sample accounts. The other 138 carry a record
row with their reason: 95 under the collection floor, 43 on a payment plan.

⚠ **THE SAME 812 ARE RE-PLANNED EVERY WEEK, AND THAT IS THE NEW BEHAVIOUR
WORKING.** The first cycle planned 835 once and then 0, 0, 43, 0, because a
record row existing at all was read as *this act has been performed*. Wave `N`
changed the question to read the OUTCOME: `planned`, `held` and `failed` mean
nothing was written, so they are resumable. A dry plan therefore no longer
excludes a customer from the ladder for ever — which is the whole of
`DEF-RBS-4347`'s second half — and the price is that **a dry cycle can no longer
demonstrate the no-double-send guarantee.** That is now only demonstrable live,
and it was: see §8.4.

## 8.3 · What the database diff says (`M2`)

**Clean on all five firings.** Nothing outside this module's seven tables moved,
and `audit_log` moved by **exactly the number of acts each run performed** —
812, 812, 812, 855, 855 — which is the assertion `M2` should have asked for and
did not (the first cycle's §2 argues why, and that argument stands).

⚠ **THE CHECK ITSELF WAS THE FIRST FINDING — `DEF-RBS-4381`.** Between the two
cycles `DEF-RBS-4352`'s fix made every result table conform to the renderer's
payload contract, so a record row became `{id, meta, cells}`. The check read
`row["outcome"]`, got nothing for every row on every firing, concluded the run
had performed **zero acts**, and failed five clean firings against 812 real audit
rows. **It failed loudly and that was luck**: the same blindness with the
arithmetic the other way round is a green cycle over a check that can no longer
see its own subject. It now reads both shapes, COUNTS the rows it cannot read,
and prints that number beside the verdict.

⚠ **AND THE DIFF HAS ONE BLIND SPOT, STATED WITH ITS NUMBER.** It compares ROW
COUNTS, so an `UPDATE` in place is invisible to it. That is not theoretical: the
second live firing of the red proof advanced the collections tier on **812 rows**
of `account_collection_state` and the table's count did not move at all. A
declared blind spot with no number attached is indistinguishable from an empty
one, so it is in the script's own docstring with that figure.

## 8.4 · The red proof, and what it revealed about the live half

Run on its own clone, mode live, the runbook on the allow-list, **and nothing
else patched.** The first cycle's proof had to force the mode and hand the port a
template; both patches are deleted rather than made conditional, so if either
regressed this proof would fail instead of hiding it.

**Firing 1, live:** all **812 acts came back `queued`**, not `held`.

| table | before | after |
|---|---:|---:|
| `outbound_messages` | 337 | **1,961** |
| `notice_history` | 0 | **1,624** |
| `account_collection_state` | 512 | **812** |
| `audit_log` | 3,372 | 6,320 (**+2,948**) |

**The diff went red on all three foreign tables**, which is what `M2` exists to
prove. And the tiers moved exactly one rung each: 300 accounts with no state
arrived at `friendly`, the 250 at `friendly` became `first_10_day`, the 170
became `second_5_day`, the 92 became `final_48_hour`. **The ladder climbs.**

**Firing 2, live, one week later:** **720 queued** — every account except the 92
already at the end of the ladder — and `notice_history` 1,624 → 3,064.

**Firing 3, live, the SAME business day repeated:** **0 queued.** 720 accounts
came back skipped with payments' own reason, 95 under the floor, 92 at the end
of the ladder, 43 on a plan, 23 undeliverable; **no record row, no audit row,
nothing written anywhere.** That is wave `N`'s *"a re-run queues 0"*, measured.

## 8.5 · What a person saw on `RBS-006` (`M3`)

**The screen opens now.** `DEF-RBS-4352` is closed: the run renders, the per-rung
table draws its four rungs with planned, queued and failed, and **no control on
the page can send, approve or apply** — 18 controls read, none of them dangerous.

**And a clerk still cannot read the plan.** Three things, each filed:

* **`DEF-RBS-4387` — the five headline tiles draw their labels and no numbers.**
  Verbatim from the page: `TO SEND` · `SKIPPED` · `NEED A PERSON` · `NOT SET UP`
  · `FEES DRAFTED`, with nothing under any of them, and `TOOK 16s` beside them
  drawing its value perfectly. The runbook builds each tile as
  `{"label": "To send", "value": 812}` — a bare integer — where the block has
  read a value cell since wave `C`. **The number 812 appears nowhere on the
  screen.** It is the same shape as `DEF-RBS-4375`, fixed the same day on a
  different screen, and the payload check added with `DEF-RBS-4352` cannot see it
  because it validates which KEYS a payload carries and not what TYPE each value
  is.
* **`DEF-RBS-4388` — 977 table rows in one page, no pager, `NFR-3` breached.**
  `RecordsBlock` genuinely pages and its own header says `rows` is *the current
  page only*; the frozen report hands it all 973. The paging endpoint this module
  built — `GET /runbooks/runs/{id}/records` — is never called by the screen at
  all. The report measures 35 kB compressed for 1,035 accounts, so at the
  40,000-account ceiling it is about 1.4 MB in one `jsonb` column and roughly
  38,000 `<tr>` in one page.
* **`DEF-RBS-4389` — the Planned column reads `queue_notice` on all 973 rows.**
  An internal step key on a clerk's table, and one that names a port runbook 8
  has not held since this morning. The sentence a clerk should read — *Queue the
  10-day notice* — is written by the runbook already and used by nothing.

⚠ **AND THE TILE CHECK WAS ITSELF LOOKING AT THE WRONG THING.** It asserted
`pageText.includes("To send")`, which fails on a strip that upper-cases its
labels and **passes on a strip that draws every label and not one number** — the
exact screen it was pointed at. It now requires a number beside the label and
was shown to match a strip that has values and refuse the one this screen draws.

## 8.6 · The five conditions from §5, each with today's measurement

| # | condition (2026-09-06) | today |
|---|---|---|
| 1 | `DEF-RBS-4352` closed **and the plan read on screen** | ⛔ **half.** The screen opens; the numbers are not on it (`DEF-RBS-4387`) and the record table draws 977 rows with no pager (`DEF-RBS-4388`) |
| 2 | `DEF-RBS-4345` closed — a live run binds a writer | ✅ **met**, measured: the red proof needed no patch and wrote 1,961 queue rows |
| 3 | `DEF-RBS-4343` closed — an act comes back `done`, not `held` | ✅ **met for runbook 8**, measured: 812 `queued`. It got there by a different route than the defect describes — the act is `step_ladder` now, and payments' own senders bring their templates — so **the defect row stays open for `queue_notice`'s other three runbooks** |
| 4 | `DEF-RBS-4347` closed or ruled | ✅ **ruled and built**, measured: `account_collection_state` 512 → 812 and `notice_history` 0 → 1,624, every account exactly one rung |
| 5 | `L3` **and** `L4` built | ⛔ **half.** `L4` refuses: a cap of 400 against 973 walked gave a `failed` run carrying *planned 973 · cap 400 · pinned 1,035* and zero records. **`L3` is not on the branch** — no approval endpoint, and no screen shows a plan and offers approval |

**Two new blockers of the same kind:**

* **`DEF-RBS-4387`** is condition 1 restated. A plan nobody can read is a plan
  nobody can approve, which was the first cycle's own sentence for
  `DEF-RBS-4352`.
* **`DEF-RBS-4382` — the cap a clerk reads is not the cap that is enforced.**
  `RB-108` shows *Most per run · 400* as an input; `run_parameters` resolves it
  to 400 on every firing; **nothing reads it.** What the engine compares against
  is `runbook.cap`, a different field, null until an admin types one — so this
  cycle walked 973 subjects a week against a number on the card that says 400,
  and nothing was refused. Set the column and it refuses correctly. Two fields
  mean one thing and only one of them does anything.

## 8.7 · Two more findings, and one number that is not a defect

* **`DEF-RBS-4380` — a run's per-record list is emptied by the NEXT run.** After
  the five firings, `GET /runbooks/runs/{id}/records` returns **0 rows for four
  of the five runs**, while each of those runs' own frozen report still says
  **973**. The row is re-pointed at whichever run last resumed it, which is
  deliberate and documented; that it empties the earlier run is not. It does not
  show on `RBS-006` today only because the screen reads the frozen report and
  never asks the endpoint — the other half of `DEF-RBS-4388`.
* **`DEF-RBS-4386` — *Email, then post* queues both at once.** One live firing
  over 812 accounts wrote **1,624** queue rows and **1,624** notice-history rows,
  split exactly 812 email and 812 printed, every rung. The card's own guards say
  *a dead channel is skipped, never sent to* and *one notice goes per account per
  run*. Whichever reading is right, the cost of the wrong one is the postage on
  812 letters and a second copy of a legal notice.
* **`DEF-RBS-4383` — `already_noticed_today` reaches a clerk as a raw code**, on
  720 of 1,035 rows on any repeated run, where every other skip on the same
  screen reads as a sentence.
* **Not a defect, and worth the number: on a weekly live schedule an account
  walks the whole ladder in about a month.** Two live firings a week apart left
  **262 accounts at the certified final letter**. Every step was payments'
  own decision under `BR-PAY-017` — the runbook asks and payments answers — so
  this is the signed rule doing what it says. It is recorded because it is the
  first time anyone has watched it happen end to end.

## 8.8 · What this cycle did NOT soak, stated with its number

* **The scheduler, again — and it exists now.** `I2` and `I3` landed on
  2026-09-07: `scheduler.decide()` correctly makes the ladder due at
  **2026-09-07 12:00 UTC** for *Mondays 07:00 `America/Chicago`*, and
  `next_run_at` returns **2026-09-14 12:00 UTC**. **Not one firing in this cycle
  went through `sweep()`** — a person pressed Run five times. **The plans are
  soaked and the scheduler is not**, and wave `I` still owes its own soak.
* **Elapsed time.** Five Mondays were replayed in one afternoon and each run is
  backdated to its business day, for the reason §6 already gives.
* **Failure.** *"Need a person"* read **0** on all five firings and can read
  nothing else in a dry run: `failed` is written only when a bound writer raises.
  That is `L11`'s PostgreSQL case, not a dry cycle's.
* **Scale.** 1,035 accounts took **16 seconds** a firing, unchanged from the
  first cycle. Extrapolated to the 40,000-account ceiling that is about **ten
  minutes a firing**, which is survivable for a weekly job and is still a number
  nobody has measured properly.

## 8.9 · What a `GO` now needs

1. **`DEF-RBS-4387` closed** — a person opens `RBS-006` and reads *To send 812 ·
   Skipped 223* in the tiles. Until then condition 1 of §5 is not met, for the
   second cycle running.
2. **`L3` built** — an approval that carries the server-side count and refuses
   with `runbooks.refusal.plan_changed` when the plan has moved. There is
   currently nothing in the product a person can press to approve a plan.
3. **`DEF-RBS-4382` settled** — one number for *most per run*, enforced where a
   clerk reads it. A cap on the card that nothing enforces is worse than no cap,
   because it is believed.
4. **`DEF-RBS-4386` ruled** — does *Email, then post* mean both or a fallback?
   Ours to decide and write down (law 13), and it must be decided before a live
   run, because it doubles the postage on every notice.
5. **`DEF-RBS-4388` closed enough to review 812 rows** — a clerk approving a plan
   pages through it; today the screen draws all of it at once and asks the
   server for none of it.

`DEF-RBS-4380`, `DEF-RBS-4383` and `DEF-RBS-4389` are not blockers. They should
land with the rest.

⚠ **TWO REGISTER ROWS ARE STALE AND WERE DELIBERATELY LEFT ALONE.**
`DEF-RBS-4343` and `DEF-RBS-4347` both read `open` while their fixes are on the
branch and are measured above. The wave `N` lane that fixed them was still
pushing while this cycle ran, and closing another lane's row is a one-line byte
splice on a shared register that two lanes must not make at once. **Named here
so it is not lost**: whoever closes them should cite `dff6b379`.


---

## Lifecycle

* packet: `CR-075` wave `M` tasks `M1`–`M4` (`10-execution-plan.md`)
* generated: 2026-09-06 by the `CR-075` wave `M` build lane; **§8 added
  2026-09-07 by the lane that re-ran the cycle against `642a3cee`**
* status: **VERIFIED-UNRATIFIED** — the figures are from a running product on
  real PostgreSQL; the NO-GO is this lane's judgment, recorded in
  `12-governance/02-decision-log.md` and open to being overruled with a reason.
* ⚠ **§1–§7 ARE THE 2026-09-06 CYCLE AND ARE HISTORY. §8 IS THE CURRENT
  VERDICT.** They are kept side by side rather than merged because the value of
  this document is that the same measurement was taken twice, twenty hours
  apart, on two different builds — and because a rewritten §1 would have quietly
  destroyed the evidence that three defects were real.
