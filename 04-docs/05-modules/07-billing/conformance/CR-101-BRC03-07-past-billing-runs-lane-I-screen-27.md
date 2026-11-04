# §07 Past billing runs — screen 27, built (CR-101-BRC03, lane I)

**Commitment.** Build blueprint screen 27, `§07 Past billing runs`, into the `history` tab
at `/:tenant/billing/history`, and retire the grey panel (`DEF-BIL-5351`).

**Commit.** `93afce58` — the screen, its twelve cases, the eighteen catalogue keys and the
decision-log entry. This record and the browser walkthrough follow it.

---

## 1 · What was read, as images, and at what scale

Everything below was read with the Read tool as a PICTURE (B14 rule 42 — *"When you use
images to create screens your accuracy is higher; hence dont create screens using only
Text"*). Nothing was taken from the PDF's text layer.

| page | what it is | scale |
|---|---|---|
| `05-prototype/04 Billing, As Built.pdf` **p145** | §07's overview and the clerk's three questions | 2 |
| **p146** (whole page) | screen 27 and its five notes | 2 |
| **p146**, head/tiles/toolbar band | the four tiles and the toolbar, legibly | **4** |
| **p146**, table band | the eight drawn columns and the footer | **4** |
| **p146**, notes band | the five notes beneath the frame | 2.5 |
| **p147**, top band | to confirm §07 ENDS on p146 and §08 begins here | 2.5 |
| **p007**, head band | the SAME page's head, drawn differently — see §3 | 3 |

The crop instrument is a sibling lane's `crop_render.py` in the session scratchpad, used
rather than written again (`10-scripts/pdf/pdf_render.py` renders whole pages, which the
reader then downsamples, so nothing is gained at scale 4 without a crop).

## 2 · Before and after

**Before.** The tab rendered one grey panel: *"Past billing runs list every run with what
it produced and who signed it off. It arrives with the billing run work."* — over a read
that has answered since `CR-029` and an actor column populated since screen 16's BY column
landed. That is `DEF-BIL-5351` and it is hard-won law 2's MIRROR: a live refusal above a
working read. `G13` asks whether a prop is PASSED and nothing asks whether a REFUSAL IS
STILL TRUE, so `tsc`, 12 billing suites and every gate passed over it for weeks.

**After.** A table of every run, newest first, with a Cycle filter, the pagination footer,
an empty state, a filtered-empty state, and three ways into the run each row names.

**What the server really answers, measured against the live demo tenant at
`GET /billing/runs` rather than read off a docstring:**

```
run_no · cycle_id · period_start · period_end · issued_at · accounts ·
bills_issued · held · status · bill_type · created_at ·
ran_by · ran_by_name · label · is_open
```

⚠ **The last four are served and `BillRunHistoryRow` in `api/endpoints.ts` does not declare
them.** `selectors._bill_run_history_row` has served `ran_by_name` since screen 16's BY
column landed. The panel declares `PastRunRow` locally rather than widening the shared type,
because `api/endpoints.ts` is a live sibling lane's file in this wave and two lanes never
edit one file (law 11). **When the shared type is widened, `PastRunRow` collapses into it.**

## 3 · The four judgments, and why each was ours to make

All four are in the decision log under *2026-09-15 · `CR-101-BRC03` §07*, written BEFORE the
code that depends on them (step W). None reached the PO: none collides with a signed rule,
none moves a frozen figure, and none needs a fact only they hold (law 13).

**(a) The page head stays as it is on this tab.** p146 draws this page titled *Past billing
runs* with *34 runs · 11,842 bills issued this year* beneath it and two actions, `Export`
and `Start a run →`. **p007 draws the SAME page** titled *Billing*, with the bills roll-up
and three buttons. Both are frames, so *the frame wins* cannot settle it — B14 rule 37's
third clause — and what the two AGREE on is the SHAPE: a title, one roll-up line,
right-aligned actions, then the seven-tab strip. The shipped head already is that shape, it
is shared by all seven tabs, and re-titling on one tab's authority would put *Past billing
runs* over a page the other frame titles *Billing*. The drawn `Start a run →` IS the shipped
`Start a billing run →` — same act, same destination.

**(b) The drawn `Open` link is built as B14 rule 15's icon.** Rule 15 is RATIFIED and
**G37-ENFORCED**: *"Row actions are ICONS with tooltips, never text links."* The drawing
loses on CONSTRUCTION and wins on CONTENT — rule 38's split, carried to a table — so the
drill-in its note demands (*"Every row opens the run it names … A table you cannot drill
into is a report, and this is a workspace."*) is built **three ways**, and all three go to
the drawn destination: the `RUN` cell is the identity link, the whole row carries `rowHref`,
and the actions column holds the 👁 with its accessible name.

**(c) The `VALUE` column is absent because nothing serves it — NOT because a rule forbids
money here.** `api.py` exception (3) and `selectors.bill_runs_list` both keep money off this
row citing `BR-MET-078` *"Money never touches these surfaces"*. That rule's PO wording is
*"you dont need late fees in this. so dont have anything related to money when you create
route and cycles"* and its subject is r10 `SET-07.3`, the route and cycle **creation**
screens. A run history row is neither, **so the citation is out of scope and the drawn VALUE
column is not blocked by a signed rule.** Written down rather than relied on quietly: a lane
reading those two docstrings would conclude the opposite and build nothing.

**(d) The footer's total.** `GET /billing/runs` is bounded by `limit` (1…200) and serves no
total — `NFR-3`, filed as **`DEF-BIL-5371`**. The footer reads the envelope's `total` when
one is served and falls back to the number of rows the server returned; that is exact for
every tenant whose history fits one page, which is the fallback's whole intended lifetime.

## 4 · What is NOT on screen, why, and the test that fires when it lands

Every absence is named ONCE, in a `RunGap` disclosure **closed by default** (B14 rule 32),
reading: *"A run's value and the year's totals are not served yet. Search, the status filter
and the year filter arrive with them."* No rule id, no route, no rationale (rules 31–33).

| drawn on p146 | why it is not built | the tripwire |
|---|---|---|
| `VALUE`, bold, right-aligned | no endpoint serves a run's value or its currency | **TC-I7** — `HasKey<PastRunRow,"value"\|"amount"\|"currency">` is `false` today; the day the row type declares one, `tsc` goes RED on that line |
| the four tiles — runs this year · bills issued · runs with exceptions · longest run | each is a SERVER aggregate over a year; counting them from the rows on screen is a client-side total over a bounded page (`NFR-3`) | **TC-I8** — the answer type declares `total`; the day `getBillRuns` returns an envelope the fixture stops type-checking |
| search, `Status ▾`, `Year ▾` | the read accepts `f.cycle_id` and nothing else; a search box that searches nothing is a screen lying about what it did | the panel declares no `searchFields`, so `G43`'s rule-19 clause cannot pass wrongly |
| `Export` (drawn twice — head button and toolbar `↓`) | no export route exists for this read; a control with nothing behind it is the defect this screen was built to remove | — |
| the status words `Corrected` and `Abandoned` | `bill_runs.status` is written `"draft"` at creation and **no writer advances it** (`DEF-BIL-5352`) | **TC-I9** — `string extends PastRunRow["status"]` is `true` today and turns `false` the moment the column becomes a vocabulary |

**`Cycle ▾` IS built**, because `f.cycle_id` is real, and the walk presses it.

## 5 · Real data, and the two states that cannot be produced at all

The demo tenant holds **four** bill runs against the **34** p146 illustrates (B14 rule 37 —
a drawn figure is an illustration). Rendered, they are:

```
No number   Not on a cycle  08/01/2026 – 08/31/2026    0  Dana Whitfield  Not issued yet
RUN-0002    CY-001          07/01/2026 – 07/31/2026   39  Dana Whitfield  Issued
No number   CY-001          06/01/2026 – 06/30/2026    1  Nobody recorded  Issued
RUN-0001    CY-001          06/01/2026 – 06/30/2026   40  Dana Whitfield  Issued
```

Three of the drawing's five notes are exercised by real rows: a run with **no number**
(`OQ-342` did not retro-number), a run with **no actor**, and a run that **issued nothing
and is still a row at zero** — which is note 3's whole point, *"a run that vanished would
leave a clerk unable to explain a gap in the numbering to an auditor."*

⚠ **`Abandoned` and `Corrected` were NOT seeded, because they cannot be produced through the
product at all — and that is a finding, not a shortcut.** Grepped: the only writers of
`BillRun.status` are `runs.py:1479` (`"draft"` at creation) and `corrections.py:1759`
(`"issuing"` for a rebill). **A clerk cannot abandon a run, and correcting a run's bills does
not mark the run.** So there is no *"start a run and abandon it"* path to walk. This is
`DEF-BIL-5352`'s subject and it is lane H's to fix; no duplicate row was filed.

⚠ **The two runs in one period the drawing argues for are real in the FIXTURE and not in
this database** — the two June runs share a period but also share a cycle, where p146's
`08-A`/`08-B` are two different cycles. `pastBillingRuns.dom.test.tsx` carries the shape.

## 6 · Proof

| what | result |
|---|---|
| `tsc --noEmit`, local TypeScript | clean — **and proved able to fail first**: a planted `const laneIRedProof: number = "not a number"` produced `TS2322`, and caught a real second error with it (`TableConfig.defaultSort` missing) |
| `vitest run pastBillingRuns.dom.test.tsx` | **12 passed** |
| `vitest run src/styles/routeBUtilities.test.ts` | 11 passed — the Tailwind ledger owns this file |
| sibling suites over `BillsListPage` (5 files) | 48 passed, 3 todo |
| `eslint` on the three files I touched | exit 0 |
| `npx vite build` | built in 17.85s |
| **browser walk, 1440 and 1280** | **30 checks PASS at each** — `10-scripts/cr101_past_runs_walkthrough.mjs` |
| gates, `run_gates.py --changed 93afce58` | 35 PASS · 41 FAIL · 1 SKIP — **no failure names a file or a key of mine**; see §7 |

### Every case was proved RED first, in the harness that will run it

Not by deleting the component — by breaking the one thing each case holds, one mutation at a
time, through `vitest run`, with the file restored and the restore asserted between each:

| broken | the red, verbatim |
|---|---|
| the `Run by` column label | `TC-I1 → column "Run by" is missing or out of order: expected -1 to be greater than 5336` |
| `rowHref` pointed at another run | `TC-I2 → the ROW does not target RUN-0002: expected '<section data-billing-tab="history"…' to contain 'data-row-href=…'` |
| the cycle cell rendering `row.cycle_id` | `TC-I5 → expected … not to contain '>01a0a444-5529-7d5b-b51b-a0f0546811c6<'` |
| a rule id put in the gap title | `TC-I6 → expected [ 'BR-MET-078' ] to deeply equal []` |
| the status pill rendering `row.status` | `TC-I9 → expected … to contain 'Issued'` |
| `billing.arrives.history` put back | `TC-I10 → expected true to be false` |

⚠ **AND THE RED PROOF EARNED ITS KEEP: TC-I2 STAYED GREEN.** As first written it asserted
`toContain("/billing/run?run=<id>")` and was named *"every row opens the run it names"* — but
the identity link and the icon each carry that same address, so pointing the ROW target at a
different run left every assertion passing. It is law 7's *looking at the wrong thing*, in a
case written by a lane that had just read law 7. It now asserts the row's own
`data-row-href` and fails naming the run.

### And the browser walk caught three flaws in its own checks

Each one would have been reported as a product defect by a lane that trusted its first run:

1. **Column headers compared case-sensitively.** p146 inks the header row in CAPS and the
   table type uppercases to match, so `Run by` reaches the screen as `RUN BY`. Six columns
   failed on a screen that was right.
2. **The page was snapshotted before the second query landed.** Rows arrive from
   `GET /billing/runs` and the CYCLE cell fills a moment later from the cycle list, so the
   snapshot caught every cycle cell mid-flight and read as *"the column shows a dash for
   every row"*. **The first screenshots for the PO showed exactly that**, over a screen that
   renders `CY-001` on three of four rows.
3. **`networkidle` is not a settled screen.** Changing the filter changes the query KEY, so
   the table renders its loading skeleton; `networkidle` returned before the refetch began
   and the check read the skeleton. The walk now waits for rows or the zero-results block.

That is law 7's second habit — *ask what would make this check fail wrongly, not only what
makes it pass* — and all three were found by looking at rendered output, which is the only
place they were visible.

## 7 · Reds I did not cause, dated

`run_gates.py --changed 93afce58` reports **41 failures**. None names a file, a key or an id
of mine, and the run itself prints `NOTHING TO COMPARE — no record existed before this run`.
The two that read as a RISE are dated:

* **`G40 unmounted-components` — ROSE by 15.** Its offenders are `FixChangesStep.tsx` and
  `FixGoodwillStep.tsx`. `git log -S "FixGoodwillStep" -- 07-frontend/src/features/billing/`
  dates them to `5efd979c` and `19921e92`, both 2026-09-15 and both **before** `93afce58`.
* **`G98 lint-clean` — eslint is RED.** Its files are under `features/assets` and
  `features/customers`; `eslint` on my three files exits 0.

Spot-checked and not mine: `G45` names `FixWhatStepBulk.tsx` and `RouteReadsPage.tsx`;
`G113` names `DEF-BIL-5354` (lane J's row); `G114` names `ImportRunListResult` in
`api/endpoints.ts`, which I did not touch; `G116` names integrations, work and payments.
`G15` reports **0 missing, 0 extra** and none of my 18 keys is among its 404.

**The product builds** (`vite build`, `tsc`, the SPA serves and the screen works), so §10 of
the build process does not fire.

## 8 · Known divergences from the drawing, recorded rather than built

1. **The page head** — §3(a).
2. **`Open` as an icon rather than a text link** — §3(b), B14 rule 15.
3. **The period format.** p146 draws `01 – 30 Sep 2026`; the screen renders the tenant's
   regional format (`07/01/2026 – 07/31/2026`) through the one `DateCell` path
   (`BR-SHL-023`/`BR-SHL-034`, IS-8). The drawn format is an illustration of a date; the
   tenant's is a signed rule.
4. **An `ACTIONS` header over the drawing's unlabelled last column** — the house pattern,
   the same as `All bills`.
5. **The table's state is not in the URL.** `BR-SHL-011` wants a list's state serialized so a
   filtered view survives a refresh and can be sent to somebody. This tab keeps it in React
   state — **as all four sibling tab bodies do** (`BudgetBillsTab`, `FixABillTab`,
   `OneTimeBillTab`), because the page's URL grammar already belongs to the All-bills table
   and two tables on one address would collide. Named here rather than diverged from alone.

## 9 · One finding filed, and one copy defect handed on

* **`DEF-BIL-5371`** — `GET /billing/runs` is not paginated and serves no total.
* **Not filed, handed on with its evidence:** `billing.run.reopen.gap`, rendered by the bill
  run wizard's own Past-runs panel, reads *"Who started a run, and what it came to in money,
  are not kept against the run — so neither can be shown here."* **The first half is now
  false** — `bill_runs.run_by` is kept, served and on this screen — which is p146's note 1
  and `DEF-BIL-5353`'s shape one layer up, in clerk-facing copy. The file is
  `billRunResume.tsx`, which this lane does not own.

## 10 · Screenshots

`/tmp/claude-0/-home-user-SMARTBillHub/d8cc0edb-6533-58a7-9b8e-548fbd3d8b79/scratchpad/lane-I-shots/`

| file | state |
|---|---|
| `past-runs-1440.png` · `past-runs-1280.png` | the screen, four real runs, both widths |
| `past-runs-1440-absence-open.png` · `past-runs-1280-absence-open.png` | the stated absence, opened |
| `past-runs-1440-empty-filtered.png` · `past-runs-1280-empty-filtered.png` | filtered to a cycle with no runs — the chip, the seven cycles by code, the zero-results state |

---

# ADDENDUM · 2026-09-15, the same afternoon — THE HANDSHAKE FIRED AND THE SCREEN IS NOW WHOLE

Everything above describes the screen as built against the server **as it stood at
13:03**. Lane H landed the server side an hour later, and this addendum records what
changed rather than editing the account above — a reader who followed the first version
needs to find out that it moved.

**Commit.** `26f589f9`, on top of `93afce58` (the screen) and `270e271a` (its record).

## A1 · Every absence in §4 above is now a built column, and the tripwires are how

The five holds were **compile-time tripwires**, and they went red the moment the shared
row type declared the fields — verbatim, and worth quoting because this is what a hold
with a test looks like when it works:

```
pastBillingRuns.dom.test.tsx(241,11): error TS2322:
  Type 'false' is not assignable to type 'true'.
```

| §4 said | now |
|---|---|
| `VALUE` — no endpoint serves a run's value | **BUILT.** `value` + `value_currency`, through `MoneyCell`, two decimals beside its `CHAR(3)` (hard rule 2). A run that issued nothing shows *Nothing billed*, never `$0.00` |
| the four tiles — each a server aggregate | **BUILT** from the served `tiles` block. Nothing is counted in the browser |
| search, `Status ▾`, `Year ▾` | **BUILT.** `q`, `f.status` and `f.year` are accepted; the placeholder is p146's own words |
| `Corrected` and `Abandoned` | **BUILT.** `runs.record_run_outcome` advances the column, and migration `0029` back-fills the history |
| the footer's total | **BUILT.** The envelope's `count`. The `?? rows.length` fallback is deleted |

**And one absence was added, because the type declares it:** `BillRunTiles.longest_run`
is the literal `null` — nothing records how long a run took (`DEF-BIL-5376`) — so the
LONGEST RUN tile reads *Not timed* rather than a zero, and a tripwire in the panel fires
the day that type changes.

**The client-side cycle lookup is DELETED.** The row carries `cycle_code`, so the browser
resolves nothing: a slow or failed cycles read now costs the Cycle chip's options and
never the CYCLE column.

## A2 · The break this found, which a sibling had already fixed

Rebuilding the SPA against the landed backend, **this screen rendered no rows at all.**
The envelope had moved to `{count, next, previous, results}` + `tiles` while its client
still read `body.runs` — `undefined` — so **five surfaces** showed their EMPTY state:
this screen, the run wizard's resume panel, the cycle's Runs tab, Fix a bill's run picker
and Print bills' run picker. `tsc`, every suite and every gate were green, because **a
missing key reads as an empty list and never as an error.**

It was found by rebuilding and walking the screen, which is the only instrument that
could see it. By the time this lane went to push, a sibling had landed
`getBillRunHistory` reading through `readListPageWith` — which ASSERTS the envelope by
name at runtime — so **no duplicate defect row was filed and their reader is what this
screen consumes.** ⚠ **AND THE CLAIM THAT CAUSED IT IS WORTH QUOTING:** the endpoint's
own docstring said *"one caller, `getBillRuns` in `endpoints.ts`, and it moved in the
same commit"*. There were **five** callers and it had not moved.

## A3 · What this lane got wrong, corrected here and in the report

* **§9 above filed `DEF-BIL-5371`** for the unpaginated read. Lane H paginated it in the
  same wave, so that row is **fixed by `26f589f9`'s server-side sibling** rather than by
  this lane — it is left for whoever closes lane H's record to close, and named here so
  it is not lost.
* **The envelope-break row this lane filed took `DEF-BIL-5380`, which a sibling had
  pushed for a different defect.** It was dropped rather than renumbered, because the
  underlying break was already fixed. Reported plainly rather than quietly.
* **The record above says the blast radius was three surfaces.** It is **five**.

## A4 · Proof, re-run end to end

| what | result |
|---|---|
| `tsc --noEmit` | clean |
| `vitest run pastBillingRuns.dom.test.tsx` | **15 passed** (was 12) |
| `eslint` on the two files this lane owns | exit 0 |
| `npx vite build` | built in 16.57s |
| **browser walk, 1440 and 1280** | **29 checks PASS at each**, against the running server |

### The seven rewired cases, each proved RED first

Through `vitest run`, by breaking the one thing each case holds:

| broken | the red |
|---|---|
| `MoneyCell` replaced by the raw string | `TC-I7 → expected … to contain '346,386.55'` |
| the total taken from `rows.length` | `TC-I8 → expected … to contain '87'` |
| the pill composed from `issued_at` again | `TC-I9 → no status PILL reads "Corrected"` |
| a tile's label blanked | `TC-I13 → tile "Runs with exceptions" is missing or out of order` |
| a tile's value hardcoded | `TC-I14 → expected { id: 'bills', … } to match object { value: 51 }` |
| the absent tile printing a zero | `TC-I15 → expected … to have property "value" with value 'billing.runs.tile.noLongest'` |
| the Status chip's label blanked | `TC-I12 → no filter legend reads "Status"` |

⚠ **TWO OF THEM STAYED GREEN ON THE FIRST ATTEMPT, AND BOTH WERE THE SAME FLAW.** TC-I9
searched the WHOLE page for *Corrected* — and the Status filter's panel lists all five
status words, so it found its string somewhere else entirely. TC-I12 searched the whole
page for *Status* — and the column header says it. Both are scoped now, to the status
pill's own markup and to the filter's own `<legend>`, and both fail naming what is
missing. **That is the third and fourth time in this lane that the red-first proof caught
a check looking at the wrong thing**, after `TC-I2` and the walkthrough's three own
flaws — which is the clearest evidence this record can offer for why law 7's proof is a
step and not a formality.
