# 17 · Runbooks — execution plan (phases → waves → tasks)

**Written 2026-09-06 against HEAD `6fed5da8` (product `2.201.1`) from the documentation that exists: the
Runbooks specification (v0.1 draft, 4 September 2026, restructured 5 September, build sheets 6 September),
*Twenty-One Runbooks* (the definitions page, 5 September), the Runbooks market study (5 September),
`12-governance/02-decision-log.md`'s four rulings of 2026-09-06, `BR-INT-054`–`065`,
`04-docs/02-decisions/12-engineering-plan.md` Addendum r11 and `12-governance/13-change-process.md`.**
Paths are relative to the repository root. Wave letters and task ids (`A1`, `B3` …) are this plan's own; the
specification's `RB-` commitment ids appear in a cross-reference column and none is invented here.

⚠ **PHASE ORDER RE-CUT LATER THE SAME DAY BY TWO PRODUCT OWNER RULINGS — §1 IS THE CURRENT ORDER AND THE
TABLES BELOW ARE READ THROUGH IT.** *"once you have foundation I want to prioritise runbook related to
integration first and then rest"* and *"For me integration related to accounting, payment provider, emails,
GIS are important - over other"*. **No wave letter and no task id moved**; two letters changed their contents
and are written `Q′` and `R′` wherever they appear. **If a sentence anywhere below still reads as though the
Checks came second, §1 wins.**

---

## 0 · What this is, and the three rules it obeys

**A PHASE is a launchable increment with a launch sentence.** There are **five**, and each one is something a
utility can see. **A WAVE is a sprint-sized lane** (one or two people, one to two weeks) that **ends in a
demonstration** — a five-to-eight-step script clicked in the running product on the seeded fixture — **and a
version bump.** No wave ends in *"the tables exist"*. A wave held to a boundary by an open question still
demonstrates the boundary: the deliberate absence, the sentence on the screen, the test that asserts it.
**A TASK is one r11 part** — `2a` backend · `2b` frontend · `2c` tests + data · `2d` prove it — or a `ground`,
`gate`, `doc`, `review` or `version` act.

**The Product Owner's rules, verbatim (decision log 2026-09-03, and they govern every plan in this repository):**

> *"we ahve to execute in agile way - each phase/wave should produce tangila eoutcome"*
> *"at the end of each pahse we should abl to luanch some funtionlaity"*
> *"everything should be executed based on actual code, and rules that we place, also ensure you do web
> walkthorugh before you sign off the user story or build"*

**Definition of done for every task and every wave — three parts, all required.**

1. **Actual code.** A lane re-verifies at r11 step 0 before it starts, because the tree moves. ⚠ **This module
   does not exist yet**: `06-backend/apps/runbooks/` and `07-frontend/src/features/runbooks/` are created by
   wave A, so wave A's *touches* column is the only one in this plan that describes files that are not there.
2. **The rules.** Every task names the `BR-RBS-`, `BR-INT-`, B14 or CLAUDE.md rule it satisfies, and every
   wave's exit test **asserts a rule** — a construction failure, a 409, a byte-identical report — never an
   impression.
3. **The web walkthrough.** Every wave's `2d` task is a browser walkthrough of the running product in the
   repo's existing convention (`10-scripts/render-checks/rbs-<wave-letter>-<slug>.mjs`; the shape is
   `cr058-owner-import-and-sale.mjs` — Playwright on the preinstalled Chromium, `SMOKE_BASE`, a database
   nobody else seeds, computed style read in a real engine, screenshots saved). **A story is signed off only
   when its tests are green — on PostgreSQL where law 14 applies — that walkthrough has run green on the
   actual build, and the screens match their build sheets in [`wireframes/`](wireframes/) region by region.**

**How a lane uses this plan.** Take one wave. Run `./10-scripts/check_head_current.sh` **first** (law 12). Do
r11 **step 0** — re-read `01-open-questions.md`, `02-decision-log.md`, `10-defect-log.csv` and
`11-change-requests.md` for anything ruled since 2026-09-06 — **and grep before putting anything to the PO**
(law 13). Assemble the packet: the wave's stories in [`06-epics/`](06-epics/), the rules quoted **verbatim**,
the build sheets in [`wireframes/`](wireframes/). Build in `depends_on` order, **writing back as you go**.
Work in a `git worktree`; commit by pathspec; **push after every task** — a push is the only durable act in
this environment. ⚠ **Before writing any helper that touches a shared file, read `10-scripts/`'s listing**:
`push_paths.sh`, `file_defect.py`, `close_defect.py`, `merge_register.py` and `allocate.py` already own those
jobs, and three reverts in one night on 2026-09-06 were all careful operators reaching for a general-purpose
tool instead.

**Version.** Scheme `<release>.<change>.<fix>`; the product is **`2.201.1`** at HEAD in both
`07-frontend/package.json:4` and `06-backend/pyproject.toml:193`, held in lockstep by `G35`. **Each wave lands
as its own `<change>` bump with a CHANGELOG entry, and each phase's closing wave carries the phase's entry.**
Absolute numbers are **not pre-assigned here**: sibling lanes bump the same literal concurrently, so each wave
takes the next free `<change>` **at push time**, re-derived from the tip
(`10-scripts/allocate.py version --bump change`, then `--verify` in the same breath as the blob
re-derivation — law 11's id clause; two lanes both shipped `2.141.0` on 2026-09-04).

**The visual reference.** Every wave's walkthrough is judged against
[`wireframes/`](wireframes/)`RBS-*.png` and its `RBS-*.md` build sheet — **the sheet and the frame cannot
disagree, because one is derived from the other.** r10 stays the default for everything the frames do not
draw (the shell, the table conventions, the button tiers, B14 rule 36's shared component kit). **A task is not
done until its screen has been compared to its frame, region by region** (hard-won law 6: no gate in this
repository looks at rendered output).

⚠ **A BUILD SHEET IS THE REGION LIST, NOT THE WHOLE SCREEN — AND 39 OF THE 75 ARE FRAGMENTS WITH NO PAGE
HEAD** (counted 2026-09-06: 75 sheets, 36 carry a `Page head` region and 39 do not). **A lane building one of
those 39 literally would ship a headerless page.** The sheet says what is *inside* the region it draws; the
page head, the shell, the toolbar and the pagination footer come from B14 and the shared kit, and are present
whether or not the sheet mentions them. **Where a sheet and a B14 rule disagree, the RULE wins and the
divergence is stamped in `08-screen-layouts.md`** — which is the same direction the portal and integrations
packs already record.

---

## 1 · The order the Product Owner set on 2026-09-06, and how the five phases map to the specification's eight

⚠ **THE PHASE ORDER WAS RE-CUT ON 2026-09-06 BY A PRODUCT OWNER RULING, AND THE PLAN BELOW IS THAT ORDER,
NOT THE ONE THIS FILE CARRIED WHEN IT WAS WRITTEN THAT MORNING.** PO, verbatim:

> *"For Cr 75 - once you have foundation I want to prioritise runbook related to integration first and then rest"*

And, narrowing which integrations, the same day:

> *"For me integration related to accounting, payment provider, emails, GIS are important - over other"*

**NOTHING IS RENUMBERED AND NO WAVE LETTER MOVES.** `A` is still `A`, `L` is still `L`, and every task id
inside a wave — `L4`, `M2`, `C1a` — means exactly what it meant before, so an existing citation of a wave or
a task still lands. **What changed is which PHASE a wave belongs to.** Two letters also change their
CONTENTS, and they are marked with a prime everywhere they appear so nobody reads the old list into the new
letter: **`Q′`** and **`R′`**.

| New phase | Waves | Ends with |
|---|---|---|
| **1 · The foundation, part one: it can look** | `A` `B` `C` `D` `E` | A clerk presses one button and sees what is stopping billing. **Nothing can write.** |
| **2 · The foundation, part two: it can act** | `L` `M` `N` | The acting half, with sending switched **OFF for a full cycle in production** (`M` is the soak and carries its go/no-go), then the collections ladder goes live |
| **3 · The integration runbooks** | `O` `P` `Q′` | Runs that start themselves when a file lands |
| **4 · Prove it on their data, and the scheduled Checks** | `F` `G` `H` `I` `J` `K` | Test bill, the coverage grid, the work list, schedules, cutover reconciliation, books tie-out |
| **5 · The rest** | `R′` `S` `T` | The non-integration Actions, the eight remaining Checks, and **inputs with tenant-resolved domains** (`BR-RBS-042`) — ⚠ **this cell read *“and compose”* until 2026-09-06; a tenant composes nothing** |

### 1.1 · Why honouring the ruling moves the ACTING HALF into the foundation

**This is not a reinterpretation of what the Product Owner asked for. It is the only order in which the
integration runbooks can run at all.**

**Every runbook fed by an integration is an ACTION, verified card by card in [`11-catalogue/`](11-catalogue/)
on 2026-09-06.** The four that phase 3 builds — **cash application (10)** · **bank reconciliation (14)** ·
**GIS reconciliation (20)** · **undeliverable contacts (22)** — each read `Kind: Action`, and each is
triggered by a landed batch (`batch.landed`, or `feedback.landed` for 22) rather than by a clock or a
person. **An Action WRITES.**

**An Action cannot run before the acting half exists.** The acting half is the thirteen ports with their
writers bound, the batch approval carrying its server-side count, the cap that refuses rather than
truncates, stop, the idempotency key, and the runbook as a **named audit actor**. That is waves `L`, `M`
and `N` — what this file called phase 4 that morning. **Prioritising the integration runbooks therefore
puts the acting half immediately after the foundation, as phase 2**, and phase 3 is the first phase whose
outcome the ruling names.

### 1.2 · Which integrations, and the two runbooks that were in phase 3 and moved out

The second ruling names **four areas**. Mapped against the nineteen connection manifests in
`06-backend/apps/integrations/manifests/` (verified 2026-09-06):

| The PO's area | Manifests | The runbook it feeds |
|---|---|---|
| **accounting** | `accounting_file` · `gl_partner` | **14 · bank reconciliation** (statement landed) |
| **payment provider** | `payments_card` · `payments_kiosk` · `payments_sandbox` · `bank_lockbox_file` | **10 · cash application** (payments landed) |
| **emails** | `email_google` · `email_microsoft` · `email_smtp` · `email_bulk`, with `sms_twilio` and `print_vendor` as the sibling channels | **22 · undeliverable contacts** (`feedback.landed`) |
| **GIS** | `gis_city` · `geocoder_census` · `map_tiles_public` | **20 · GIS reconciliation** (a parcel batch lands) |

⚠ **TWO INTEGRATION-DRIVEN ACTIONS WERE IN PHASE 3 AND ARE NOT ANY MORE — SAID OUT LOUD SO THE GAP READS AS
A DECISION RATHER THAN AN OVERSIGHT.** **11 · leak and high-usage alert** and **21 · read validation on
arrival** are both Actions, both triggered by `batch.landed`, and both would have sat in phase 3 under the
first ruling alone. **They are fed by interval-meter data — `meters_mdm` and `meters_neptune360` — which is
none of the four areas the Product Owner named.** They move to **`R′` in phase 5**. Nothing about them
changed except when they are built.

### 1.3 · The mapping to the specification's eight increments

**The specification has eight increments** (`1a`–`1d`, `2a`–`2c`, `3`). **Every story is still placed
exactly once**; nothing is lost and nothing is duplicated. The source's own increment stays in
[`05-user-stories.md`](05-user-stories.md)'s last column, so a citation of *"phase 2a"* still lands.

| This plan | Source increments | What moved, and why |
|---|---|---|
| **1 · The foundation, part one** | `1a` + versioning and clone from `1c` | Unchanged by the re-cut. `US-RBS-038` and `US-RBS-040` render entirely on `RBS-002`/`RBS-003`/`RBS-004`, and **splitting versioning from the run record it pins would ship a `version` column that means nothing.** |
| **2 · The foundation, part two** | `2a` + `2b` | **Moved here from phase 4 by the 2026-09-06 ruling.** Still one phase built in two halves — dry, then live — and §4 says why in full. |
| **3 · The integration runbooks** | the landed-batch part of `2c`, plus `3`'s runbook 20 | **New grouping.** The four runbooks the PO's four areas feed, plus the event trigger they all need. |
| **4 · Prove it on their data, and the scheduled Checks** | `1b` + `1c` (less the two above) + `1d` | **Moved here from phases 2 and 3.** Two phases' worth of Checks merged into one: they share the property that **nothing in them writes**, and after phase 2 that is no longer the thing that makes a phase safe. |
| **5 · The rest** | the remainder of `2c` + `3` | The non-integration Actions, the eight remaining Checks, and **inputs with tenant-resolved domains** (`BR-RBS-042`). ⚠ **This cell read *“and compose”* until 2026-09-06** — the PO ruled that a tenant sets input values and never arranges steps. |

⚠ **THE EPIC NUMBERS NO LONGER TRACK THE PHASE NUMBERS, AND THE EPICS ARE NOT RENUMBERED** (renumbering
five epics would move every citation of them at once, which is the mass shared-file rewrite law 11 exists to
prevent). **`EP-RBS-04` — *It acts, and you approve* — is now PHASE 2's epic.** `EP-RBS-02` and `EP-RBS-03`
are **both phase 4**. `EP-RBS-05` now spans **two** phases: waves `O`, `P` and `Q′` are phase 3, and waves
`R′`, `S` and `T` are phase 5. Each epic file says this on its own first line, so a lane that opens one
without opening this plan still learns it.

⚠ **PHASE 2 IS ONE PHASE WITH TWO HALVES, NOT TWO PHASES.** The outcome — *it acts, and you approve* — is
one thing a utility gets. The halves are how it is **shipped**, and §4 says why in full.

---

## 2 · The phases — five increments, each with a launch sentence

| Phase | LAUNCH | Exit test — a demonstration, and the rule it asserts | Stories | Waves | Rollback |
|---|---|---|---|---|---|
| **1 · the foundation, part one: it can look** | **A clerk presses one button and sees exactly what is stopping billing, each finding with a button to the screen that fixes it.** Nothing can be written; the engine has no writer bound | Wave E's walkthrough: *Can we bill?* on the blockers fixture reads **3 things stop billing** with three fix routes; then a developer binds a port to that Check and **the build fails, not the run** (`BR-RBS-002`, `TC-RBS-1`) | 001 · 002 · 003 · 015 · 016 · 018 · 038 · 040 · 041 | A · B · C · D · E | **Clean** — nothing outside this module's seven tables has been touched |
| **2 · dry** — the foundation, part two: it can act | **A clerk sees exactly what would be sent to 812 accounts and cannot yet send it** | Wave M's walkthrough after a **full cycle in production**: Review reads **812 to send · 97 skipped · 95 needing a person**, every row naming its rule, and a database diff shows **zero rows written outside this module's seven tables** (`BR-RBS-003`, `BR-RBS-004`) | 010 · 011 · 012 · 014 | L · M | **Clean** — nothing left the building |
| **2 · live** | **About 33 hours a month return, and every notice can name the rule that sent it** | Wave N's walkthrough: **248** notices queued against the tenant's own ladder, **none** to a protected or disputed account; a re-run queues **0** and names the 248; every audit row reads *Collections ladder · version 3* (`TC-RBS-4`, `TC-RBS-12`) | 013 | N | ⚠ **CANNOT BE ROLLED BACK IN THE DIRECTION THAT MATTERS — a notice cannot be unsent.** Disable the runbook and keep the runs |
| **3 · the integration runbooks** | **A file lands and the work starts itself.** The four runbooks that serve the areas the Product Owner named — accounting, payment provider, emails, GIS — run without anyone pressing anything | Wave O's walkthrough: a lockbox batch lands and **cash application starts within a minute** with the batch pinned as its scope, and nobody pressed anything (`BR-RBS-009`, `BR-INT-058`) | 017 · 022 · 026 · 032 · 034 | O · P · Q′ | Per runbook — disable it. Four independent switches, and the event trigger is a fifth |
| **4 · prove it on their data, and the scheduled Checks** | **A utility sees its OWN accounts produce correct bills before go-live** — 25 cells, one per plan × service mix × cycle — **and problems arrive BEFORE the bill run instead of during it**, in one list a clerk opens each morning | Wave G's walkthrough: the grid reads **21 clean · 2 estimated · 2 refused**; a red cell opens that account's test bill and the refusal is **the engine's own**; fixing the rate moves it to **23** (`J-RBS-2`). Then wave I's: **nobody opens the product**; at 06:00 tenant local the sweep runs and thirty sweeps over one missing read produce **one item, thirty days old** (`TC-RBS-10`, `BR-RBS-016`) | 004 · 005 · 006 · 007 · 008 · 009 | F · G · H · I · J · K | **Clean** — no bill number is consumed; disable the schedules and the runs and items stay |
| **5 · the rest** | **Roughly 20 more hours a month. Each new runbook re-uses about 2 shared steps and writes about 4.7 of its own, and arrives with NO NEW SCREEN** ⚠ **THIS CELL READ *“Each new runbook is a week of work rather than a project”* UNTIL 2026-09-06, AND THAT SIZING RESTED ON A LIBRARY A RUNBOOK CAN BE ASSEMBLED FROM.** The hand count of the 26 catalogue cards ([`14-step-library.md`](14-step-library.md), `DEF-RBS-4275`) says it is not that library: **173 step instances reduce to 137 distinct steps**, **122 of them (89%) are used by exactly one runbook**, and the reduction is **20.8%** — a fifth of the step-writing, not a third and not most of it. **Two runbooks share nothing with anything at all** (`RB-105` *Abnormal readings*, 8 steps; `RB-118` *Vacant premises with usage*, 6 steps), so a library cannot make either cheaper. **What the figure above is based on:** 36 shared instances over 26 runbooks is ~1.4 re-used per runbook against ~5.3 written, which is where *2 re-used and 4.7 of its own* comes from. ⚠ **The estimate that moved was OURS, never the PO's — this is a measurement replacing an estimate, not a re-sign.** The model is still worth keeping, for **blast radius** rather than for sizing: fifteen shared steps carry all of the sharing, every one on the money or the write path, and writing, testing and fixing those once is exactly what the PO asked for in *“when we later change it will be small er changes for us”* | Wave T's walkthrough: an admin sets the collections ladder's *services* input to **All**, Trash is added the following month, and the next run covers **three** services — not the two that existed at setup; changing that input drops the runbook to dry-run only until one clean dry run is reviewed. ⚠ **THIS READ *“an admin composes \“Vacant premises, Sewer\” from shipped steps”* UNTIL 2026-09-06** — a tenant never arranges steps (`BR-RBS-042`); **we** build runbooks from the step library and a tenant sets input values | 019–021 · 023–025 · 027–031 · 033 · 035 · 036 · 037 · 039 | R′ · S · T | Per runbook — disable it. The catalogue is sixteen independent switches |

⚠ **THE PRICE OF THE NEW ORDER, STATED RATHER THAN SOLD.** The order this plan carried on the morning of
2026-09-06 put **every Check first** and reached an Action only after the engine had been proved on work
that could not reach a customer. **The new order reaches the dangerous half immediately after the
foundation.** Two things follow, and both are costs:

1. **The safety argument now rests entirely on wave `M`** — a full cycle, dry, in production, with sending
   switched off and a **written go/no-go**. `M` stays **exactly where it is, between `L` and `N`**.
   ⚠ **SHORTENING `M`, OR FOLDING IT INTO `L`, IS THE ONE CHANGE THAT WOULD MAKE THIS REORDER UNSAFE.**
   It is not a formality and it is not a buffer: it is the only cheap opportunity this plan has to be wrong.
2. **The coverage grid — the go-live artefact and the sales artefact at once — now lands in phase 4 rather
   than phase 2.** A utility that has seen 25 green cells on its own data before go-live behaves differently
   from one that has not, and under this order it sees them **three phases later**. That is the price, and it
   is named here rather than left to be discovered by whoever sells the first deal.

⚠ **THE FIXTURE TENANT.** The wireframes draw **`silvercreek / operations`** and `seed_demo` provisions
**Brazos Bend Utilities**; **Silver Creek Water** and **Lone Star Ridge WSC** are named in `tenancy/brand.py`
and in the stories but are **not seeded**. Each wave's `2c` seeds what its demo needs, and the second tenant
is provisioned by the isolation tests. **The build sheets' `silvercreek` is a sample value; the words around
it are not.**
---

## 3 · The waves

**Size:** S ≤ 1 day · M 2–3 days · L 4–5 days, per person. **Demo scripts** are clicked by the walkthrough
named in each wave's `2d` task.

⚠ **THE WAVES ARE LISTED BELOW IN LETTER ORDER, WHICH IS NO LONGER THE BUILD ORDER.** They are left in
letter order so that every existing citation still lands where a reader expects it. **The build order is:**

> **`A` `B` `C` `D` `E`** (phase 1) → **`L` `M` `N`** (phase 2) → **`O` `P` `Q′`** (phase 3) →
> **`F` `G` `H` `I` `J` `K`** (phase 4) → **`R′` `S` `T`** (phase 5)

**Each wave's *Depends on* line is a TECHNICAL dependency, not a position in the queue** — wave `F`
depends on `E` because `F1` needs `E6`, and it is built after `Q′` because that is where phase 4 starts.
⚠ **Three forward dependencies were created by the re-cut and all three are resolved in the waves below
rather than left for a lane to hit: `I1` moves forward to land with wave `L`** (§3's wave `L` and wave `I`
tables both say so), **`batch.landed` / `feedback.landed` are named as wave `O`'s blocking dependency**, and
**the audit actor is a named prerequisite of wave `L`** rather than a note. §5 carries all three with what
each costs if it slips.

---

### Wave A — the module exists and cannot reach past its own seams · phase 1

**Goal a clerk can see:** none yet, and this is the **one** wave in this plan that admits it. Its outcome is a
**gate that goes red**: a planted `from apps.customers.models import Account` in the new module fails the
import census by name and line. ⚠ **A wave whose outcome is a check must show that check FAILING first**, or
it is a check that could not fail — 205 defects, 11.6%, the fourth-largest class in this repository.

**Stories:** `US-RBS-041` · **Depends on:** nothing · **Blocked by:** nothing · **Size:** two people, one week.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **A1** | ground / doc | **THE SCHEMA BRIEF FIRST.** `04-docs/02-decisions/02-database-design-brief.md` gains `### Module: runbooks` with the **seven** tables' DDL, an RLS row per table, and a new addendum. ⚠ **This commit must precede A3's in `git log`** — *"the re-cut register begins at the migration"* | 041 · hard rule 1 | — | `RB-023` | S |
| **A2** | ground | ⚠ **THE FIRST TRAP, AND IT SHIPS AN INVISIBLE PRODUCT.** `07-frontend/src/features/runbooks/` is created **and its paths are added to `07-frontend/src/styles/route-b-migrated.txt` IN THE SAME COMMIT AS THE FIRST COMPONENT** — not as a later tidy-up. **Measured 2026-09-06: that file is 3,241 lines and holds ZERO runbooks paths.** B14 rule 21's migration clause is **PER FILE**: a Tailwind utility is emitted only for a file on that list. **What it costs if skipped:** every utility in this module is a class no stylesheet declares, so **the screen renders as nothing at all** — while `tsc`, eslint and every `toContain("flex")` assertion **pass**, because the class IS in the DOM. Two lanes hit this in one week (`DEF-974`, `DEF-901`), both while fixing OTHER UI defects, and both fixes would have re-broken the screen they repaired | B14-21 · law 2 | — | `DEF-974` | S |
| **A3** | 2a | `06-backend/apps/runbooks/` — `apps.py` with `AppConfig.ready()`, `models.py` (the seven tables), `migrations/0001_initial.py`, `migrations/0002_rls_force.py` (RLS **FORCE** on all seven), `selectors.py` reads · `services.py` writes | 041 · hard rule 1 · `BR-RBS-039` | A1 | `RB-023` | L |
| **A4** | 2a | `apps/runbooks/seams/` — one file per module read, named for the pair; `apps/runbooks/ports/` — **the thirteen port seams as declarations binding NO writer**. Each seam gains its row in the cross-module interface register **in the same commit as the file** | 041 · `BR-RBS-022` · `BR-RBS-039` | A3 | `RB-052` | L |
| **A5** | ground | **The selector inventory.** Every selector a defined runbook needs that no module exposes today — a meter's last good day, an account's ladder tier, a premise's usage over 90 days — listed, with the **owning** module named for each. ⚠ **This is done NOW, not discovered in phase 5**; the owning module adds the selector and this module never reaches past a seam | 041 | A4 | `RB-052` | M |
| **A6** | gate | `10-scripts/gates/` — the **import census** (`TC-RBS-25`): every cross-module import resolves to `*_seam.py`; every seam names a register row; **no `requests`, no `httpx`, no other module's models**; a Check's seams expose reads only. ⚠ **Proved RED through `run_gates.py`, not through `python3 <gate>.py`** — a red proof through the wrong entry point is no proof of the thing that matters (`DEF-GOV-3733`) | 041 · `TC-RBS-25` | A4 | — | M |
| **A7** | 2c · 2d | The isolation fixture and `TC-RBS-7` on **PostgreSQL**; the census shown red on two planted violations, then green. `10-scripts/render-checks/rbs-a-module-boundary.mjs` is a no-UI wave, so `2d` is the **gate transcript**: the red run quoted verbatim, then the green | 041 · law 7 | A6 | — | M |
| **A8** | version · doc | CHANGELOG, next free `<change>` at push time, decision-log row | — | A7 | — | S |

**Wave A — AS BUILT (2026-09-06, the `CR-075` wave A build lane; product `2.207.0`).** Verified
from the code, not from the task table above:

* **`A1` — the schema brief first, and it was NOT already done.** Checked before writing: `grep -c runbook
  04-docs/02-decisions/02-database-design-brief.md` returned **0** at `da60a3f6`. The brief gains `### Module:
  runbooks` with all seven tables' DDL, seven names in §3's RLS list, and **Addendum r24**. That commit
  (`1e3bbe2c`) precedes `A3`'s in `git log`, which is the ordering `US-RBS-041` asserts. A sibling lane added
  **Addendum r25** (the nine seams and thirteen ports as register rows) within the same hour, on top of r24;
  `A4` amended r25 rather than duplicating it.
* **`A2` — the trap, closed with a test rather than a comment.** `07-frontend/src/features/runbooks/` exists
  and `route-b-migrated.txt` carries `features/runbooks/` as a **directory entry** (the `portal/` shape), so a
  file born under it is owned by the compiler check the day it is born. `routeBLedger.test.ts` asserts the
  entry is present, **ends in a slash**, and names a folder that exists — the three ways that line can be
  there and mean nothing. Shown red with the line deleted (`expected [ …(210) ] to include
  'features/runbooks/'`) and red again with the slash removed, then green.
* **`A3` — seven tables, two migrations.** `models.py` (663 lines) holds `Runbook` · `RunbookVersion` ·
  `RunbookRun` · `RunbookRunRecord` · `WorkItem` · `CutoverPlan` · `CutoverPlanItem`, created by
  `migrations/0001_initial.py` (641 lines) with `0002_rls_force.py` (97) immediately after. Both are 🔒 and
  carry `HUMAN-OWNED` + `HUMAN-REVIEW-PENDING` with a row in `09-human-review-ledger.md`. `0001` depends on
  `tenancy` and `identity` and **on no other module**, which is the schema half of `BR-RBS-039`.
* **`A4` — nine seams, thirteen ports, none bound.** `seams/` holds nine `*_seam.py` in the `work` layout;
  `ports/` holds thirteen `PortDeclaration`s across five files, one per owning module. `interfaces.py` is the
  registry; `boundary.py` holds the two types. **`interfaces.bound_ports()` returns `()`** and
  **`ports_for("check")` returns `()`**. ⚠ **The seams name NO selector**, deliberately — naming one no module
  exposes fails `G20`, and naming one nothing calls is dead code. B2 r25 is amended to say so.
* **`A5` — the inventory, and it is 21 of 34 runbooks with the gap declared.** `13-selector-inventory.md`:
  **fourteen absent, three at the wrong door, two not ours.** The five metering rows are one body of work
  rather than five; the wrong-door class is worse than absent because it answers `None`, which reads as *no
  findings*.
* **`A6` — `G115`, registered in `run_gates.py`.** 691 lines, executable, with a self-test that breaks
  thirteen things per run and reports FAIL rather than PASS if any sabotage stops biting.
* **`A7` — the transcript is the demo, because there is no UI.** Two planted violations shown red **through
  the registry path** (`_assert_registry_sane()` then the `GATES` entry, never `__main__`), then green with
  both files restored byte-identically. `test_us_rbs_041_pg.py` proves tenant isolation on **PostgreSQL 16**
  under the non-superuser probe role and **skips** on the SQLite suite, where the guarantee cannot exist.
* **`A8` — `OQ-RBS-1737`, `DEF-GOV-4248`, `DEF-RBS-4249`**, the CHANGELOG entry and the decision-log row.

⚠ **ONE THING IN THIS WAVE IS NOT WHAT THE TASK TABLE ABOVE DESCRIBES, AND IT ARRIVED MID-BUILD.**
`DEF-RBS-4246` found that `runbook_run_records.idempotency_key`'s composition contradicts itself in our own
documents — `BR-RBS-008` names the RUN as a component and `TC-RBS-4`'s *248 notices, not 496* requires that it
does not. **The index is laid as specified** (it is correct under every candidate answer) and **wave A
composes no key anywhere**; the contradiction is written on the column and minted as `OQ-RBS-1737` for wave
`L`. A lane arriving at `L2` should read that question before writing a `_key(...)` helper.


---

### Wave B — the contract, the registry and the conformance suite · phase 1

**Goal a clerk can see:** a developer adds one Python module and it appears in the registry; a module declaring
`category = "Misc"` **stops the process from starting**, naming itself.

**Stories:** `US-RBS-002` · `US-RBS-015` · **Depends on:** A · **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **B1** | 2a | `apps/runbooks/contract.py` — the seven-part object plus `category`, `parameters[]`, `requires`, `report()`; the **eleven** parameter types; the twelve subject types | 015 · `BR-RBS-024` · `BR-RBS-019` | A3 | `RB-020` | L |
| **B2** | 2a | `registry.py` + `runbooks/definitions/` (one module per runbook), registered at `AppConfig.ready()`. **Refuses AT LOAD, never at run time:** an unknown category · a report block outside the twelve · a **Check with a port** · a step with no mode · a missing unit of work | 002 · 015 · `BR-RBS-001` · `BR-RBS-002` · `BR-RBS-021` | B1 | `RB-020` | L |
| **B3** | 2a | `engine/executor.py` — pin scope · evaluate · **per-record steps in their own `SAVEPOINT`** · set steps once · close. ⚠ **The savepoint comment says WHY, or the next lane simplifies it away**: `try/except IntegrityError: continue` aborts the whole PostgreSQL transaction and loses the run, and **passes the entire SQLite suite green** (law 14) | 015 · `BR-RBS-007` · `BR-RBS-023` | B1 | `RB-006` | L |
| **B4** | 2c | **The conformance suite** (`TC-RBS-15`): every registered runbook constructs · resolves on the fixture · dry-runs · a Check wrote nothing · its report validates | 015 · `TC-RBS-15` · `TC-RBS-19` | B2 | `RB-020` | M |
| **B5** | 2c · gate | **`TC-RBS-5` on real PostgreSQL.** A new `06-backend/tests/test_rbs_savepoint_pg.py` beside the existing `test_*_pg.py` files with `requires_postgres`, **run by CI under `config.settings.local` + `DATABASE_URL`**, and **marked skipped in RED wherever only SQLite is available** | `TC-RBS-5` · law 14 | B3 | `RB-038` | M |
| **B6** | 2d | Gate transcript: a Check with a port bound → **build fails**; `Misc` → **process does not start**; a thirteenth block → **suite fails**. Each quoted red, then green | 002 · law 7 | B4 · B5 | — | S |
| **B7** | version · doc | CHANGELOG · version · decision-log row | — | B6 | — | S |

**Wave B — AS BUILT (2026-09-06, the `CR-075` wave B build lane; product `2.208.0`).** Verified from the
code and from runs, not from the task table above:

* **`B1` — `contract.py`, 705 lines, and every refusal fires at CONSTRUCTION.** The object is cited by NAME
  rather than by count, because `12-the-contract.md` §1 says *seven-part* in prose and lists nine in its own
  figure. Declared: `key` · `kind` · `subject_type` · `unit_of_work` · `triggers` · `category` · `tags` ·
  `parameters` · `resolve` · `steps` · `guards` · `requires` · `ports` · `report`. The **eleven** parameter
  types and the **twelve** report blocks are declared here because **no column holds either** — both live in
  `jsonb` (`03-field-map.md` D-3) — and **the twelve block names were minted by this wave**: no machine
  spelling of them existed anywhere in the repository before it (grepped 2026-09-06: zero hits for
  `block_type`, `row_decisions` or a quoted `"verdict"`).
* **`B2` — `registry.py` + `definitions/`, loaded at `AppConfig.ready()`.** ⚠ **IT DOES NOT DISCOVER, AND
  THAT IS A DIVERGENCE FROM THIS ROW.** `pkgutil` + `importlib` was written first and **`G115` refused it by
  file and line**: its rule 3 permits a dynamic import only where the argument is a string LITERAL beginning
  `apps.runbooks.`, because a computed name is a hole a static census cannot follow — and that census is this
  module's boundary. Weakening the module's own gate to save one line per runbook is the wrong trade, so a
  runbook module adds **one line** to `definitions.DEFINITION_MODULES`, and a conformance case reads the
  directory listing and **fails naming any `.py` file the tuple does not carry**. Forgetting the line is a
  RED test; a discovery loop's failure mode is the opposite and worse. `G115` now reports *no dynamic import
  anywhere — every import in this module was followed*.
* **`B3` — `engine/executor.py`.** Scope resolved ONCE and fingerprinted, guards evaluated before any step,
  steps in DECLARATION order, set steps once over the pinned set, per-record steps each in their own
  `transaction.atomic()`. The savepoint comment says WHY, at length, in the file. ⚠ **It catches
  `DatabaseError`, not `IntegrityError`** — a check constraint, a deadlock and a statement timeout abort a
  PostgreSQL transaction identically and a savepoint recovers from all of them, so catching only the narrow
  class would look handled and cover the least.
* **`B4` — the conformance suite, 48 cases, `tests/test_us_rbs_015_conformance.py`.** ⚠ **The live registry
  holds ZERO runbooks in wave B and the suite PRINTS that** beside its verdict, because a suite reporting
  PASS over an empty registry is `G5` calling 192 skips a pass. Every conformance assertion runs today against
  exemplars built in the test and starts covering wave C's `configuration_check.py` with no edit.
* **`B5` — `tests/test_rbs_savepoint_pg.py`, 4 cases, PostgreSQL 16.** `4 passed` under
  `config.settings.local` + `DATABASE_URL`; `4 skipped` on the default suite, each naming why. Its negative
  case implements the naive `try/except IntegrityError: continue` **in the test** and asserts PostgreSQL
  punishes it.
* **`B6` — every refusal shown RED first, in the harness that runs it.** The savepoint deleted from
  `_run_one_record`: `TC-RBS-5` went red on **`assert 3 == 1`** — one refused record became **three lost
  records out of four**, the other two carrying *"An error occurred in the current transaction. You can't
  execute queries until the end of the 'atomic' block."* Five construction refusals disabled one at a time:
  **9 of 48 cases red**, then all 48 green with both files restored **byte-identically**.
* **`B7` — CHANGELOG, version `2.208.0`, decision-log row, and two defects filed.**

⚠ **TWO THINGS IN THIS WAVE ARE NOT WHAT THE TASK TABLE ABOVE DESCRIBES.**

1. **`BR-RBS-024`'s second sentence is NOT enforced, and enforcing it would refuse every Action this module
   ever ships (`DEF-RBS-4262`).** *The category names the owning module whose ports it may call* is broken by
   `12-the-contract.md`'s own §8: runbook 8 is Collections (owning module `payments`) and holds
   `queue_notice` (`notifications`) and `apply_fee` (`billing`); runbook 14 is Finance (`ledger`, which owns
   **no ports at all**) and holds `record_match` (`payments`); the three Data Sync runbooks name
   `integrations`, which owns none. **Counted: 15 of the 21 port bindings in §8 break it, and 9 of the 9
   Actions break it at least once.** Read as PROVENANCE; the allow-list is the runbook's own `ports[]`, which
   §8 itself calls *the whole safety story*. A test pins the reading so a later lane adding the restriction
   meets a red naming the defect.
2. **Nothing composes an idempotency key, and the PostgreSQL proof was designed around that.** `OQ-RBS-1737`
   is OPEN, so the executor writes no `runbook_run_records` row at all and `TC-RBS-5` provokes its collision
   through `work_items`' own `UNIQUE (tenant_id, fingerprint)` instead — **so no key shape is set down even in
   test code for a later lane to copy.**

⚠ **AND STEP 0 FOUND A FAN-OUT THAT HAD NOT HAPPENED (`DEF-RBS-4263`).** The five PO rulings of the same
morning were in the decision log and in **neither** the open-questions register's status column nor its body.
A lane reading `OQ-RBS-1732` at its word would have stubbed a threshold the PO ruled against, or put the same
question to the PO twice. **`OQ-RBS-1731`, `1732`, `1735` and `1736` and six `BR-RBS-` rows are amended in
wave B's commit; `1733` and `1734` are NOT**, because a sibling lane walked those two while this wave was
building and re-applying an hour-old copy of them would have reverted it (law 11, mechanism two).

⚠ **AND THAT SIBLING LEFT WAVE B AN OWED ITEM WITHOUT KNOWING IT.** `BR-RBS-040` — the ruling that a Check
may cause a NOTE, resolved as a third ENGINE act so `BR-RBS-002` stands word for word — closes with *"owed:
a construction test that a Check still holds zero ports after this lands"*. **`TC-RBS-1` and the
execution-context case are that test**, and they were written the same afternoon by a lane that had not read
the row. `BR-RBS-002`'s status cell now says so.

⚠ **`G27` IS STILL RED ON THIS MODULE AND IS REDDER: 2,979 lines of engine and zero mounted routes**, against
1,534 at wave A. That is correct — **wave D clears it by mounting routes** — and it must not be silenced.
**`G74` fell by three**: `Runbook`, `RunbookVersion` and `RunbookRun` got their first writer (`ensure_version`,
`open_run`, `close_run`) and their first reader, so their three baseline lines are DELETED rather than
reworded. Four remain, and one of them is BLOCKED rather than later.

> ✅ **CLEARED 2026-09-06 BY WAVE D TASK `D1`.** `config/urls.py` reaches `apps.runbooks.api` — eight READ
> routes — and **`G27` is PASS for `runbooks`**, at **4,369** engine lines rather than the 2,979 above.
> **`G74` fell by two more**: `RunbookRunRecord` and `WorkItem` got their first READER
> (`selectors.run_records_page`, `run_result_records`, `_open_work_items_by_runbook`), so their lines are
> deleted too and **five** of the seven are now off the baseline. ⚠ Neither of those two has a WRITER yet —
> `RunbookRunRecord` waits on `OQ-RBS-1737` and `WorkItem` on the engine's upsert — and `G74` cannot see a
> half-wired table, so the gap is written into the baseline file's own header rather than lost with the
> deleted lines. The hold in `12-governance/02-decision-log.md` §15 is discharged in the same commit.


---

### Wave C — the two renderers and the first Check · phase 1

**Goal a clerk can see:** *Can we bill?* runs and the result draws a **ten-cell chain, red at the earliest
failure**, with **3 things stop billing** and a button beside each finding.

**Stories:** `US-RBS-016` · `US-RBS-001` · **Depends on:** B · **Size:** two people, two weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **C1a** | 2b | ⚠ **SIX SHARED COMPONENTS THE TWELVE BLOCKS NEED AND THAT DO NOT EXIST — VERIFIED ABSENT FROM `07-frontend/src/components/` ON 2026-09-06.** `VerdictBand` · `Chain` · `ContributionBars` · `OutcomeCard` · `SettingsOwnedField` · `PercentCell`, **plus the `Records` block's SPARKLINE CELL and its GRID DISPLAY MODE.** They are **phase-1 work, not phase 5**, because phase 1 builds the renderer and **phase 2's coverage grid IS that grid mode** — deferring them would make `EP-RBS-02` unbuildable. They join the shared component kit (B14 rule 36), not this module's own folder | 016 · B14-36 · B14-21 | A2 | `RB-016` | **L — sized separately from C1b; the six are the larger half** |
| **C1b** | 2b | **The twelve block components**, one file each, Tailwind only, in `features/runbooks/blocks/`, composed from C1a's six. ⚠ `route-b-migrated.txt` lists the feature root (A2) — **grep it before reaching for a utility** | 016 · B14-21 · B14-36 | C1a | `RB-016` | L |
| **C1c** | 2b | ⚠ **THERE IS NO PERCENT FORMATTER IN THE FRONT END AT ALL — verified 2026-09-06.** `PercentCell` needs one, and **hard rule 2 says percentages DISPLAY at 2 decimals over 6 stored**. ⚠ **And not one percentage in any of the 75 build sheets is drawn at two decimals**, so the sheets cannot be copied literally on this point: **the rule wins and the divergence is stamped in `08-screen-layouts.md`.** The formatter is shared, beside the money one, not a runbooks-local helper | hard rule 2 · B14-36 | C1a | — | S |
| **C2** | 2b | `RBS-006` — the result renderer over `runbook_runs.report`. Built against **`wireframes/RBS-006.*`** region by region | 016 | C1b | — | L |
| **C3** | 2b | `RBS-004` — the setup renderer over a definition, seven tabs. Against **`wireframes/RBS-004.1`–`.7`** | 016 · 001 | C1b | — | L |
| **C4** | 2b | `RBS-005` — the run wizard, **the four-step Check path** (`RBS-005.1`, `.2`, `.6`, plus check-failed). **Every step listed before the first one starts**; a step that does not run carries the reason | 001 | C2 | — | M |
| **C5** | 2a | `definitions/configuration_check.py` — **runbook 1, ten steps**, per-service verdict rolled up to a tenant verdict (the rollup rule is [`01-overview.md`](01-overview.md) §8.1) | 001 · `BR-RBS-010` · `BR-RBS-011` | B2 | `RB-101` | L |
| **C6** | 2a · 2c | **The report is composed at close and FROZEN**; an unknown block is refused **at close**, not at render (`TC-RBS-16`). `TC-RBS-14`'s static scan: **no failure reason without a fix route** | 016 · `BR-RBS-020` | C5 | `RB-016` | M |
| **C7** | 2c | The **blockers fixture**: no tax region · one plan with no rate above 20,000 gallons · 4 accounts with no unit → **exactly 3 blockers, 3 fix routes**; and the per-service rollup case (Sewer red, Water green) | 001 | C5 | — | M |
| **C8** | 2d | `rbs-c-can-we-bill.mjs` — run it, read **3 things stop billing**, click a fix route, and **diff the database: nothing outside the seven tables changed** | 001 · law 6 | C7 | — | M |
| **C9** | version · doc | CHANGELOG · version · decision-log row | — | C8 | — | S |

⚠ **THE STEP LIBRARY STARTS HERE, AND IT IS OURS (`BR-RBS-042`, PO ruling 2026-09-06).**
`C5` writes runbook 1's ten steps, and from this wave onward **every step is written into a
shared library rather than into one runbook**. Measured by hand on 2026-09-06 and recorded in
[`14-step-library.md`](14-step-library.md): **173 step instances across 26 runbooks reduce to 137 distinct steps** (`14-step-library.md`, the hand count of 2026-09-06), **122 of the 137 (89%) are used by exactly one runbook** and fifteen steps carry all of the sharing — the most-used is *“resolve the declared scope into the pinned set”* at seven runbooks, and the reduction is **20.8%** (36 of 173), so the assembly saves **a fifth** of the step-writing rather than a third. The PO's own reason for it is *“when we later change it will be small er changes for us”*.

⚠ **IT IS AN INTERNAL ENGINEERING ASSET AND NOT A FEATURE.** No screen draws it, no endpoint
serves it, and **a utility admin never sees a step list**: PO verbatim, *“I dont think Utility admin will able to configure these using the 150 bricks that we give - you can keep all these bricks and buld ready to use runbooks - when we later change it will be small er changes for us”*. That is why it lands in phase 1 rather than in wave `T`, which is where this plan put it
until 2026-09-06.

⚠ **AND THE SAVING IS THE RISK.** A fix to one shared step lands in **every** runbook that uses
it and **breaks every one of them just as fast**. So **a shared step carries its own tests**, and
**a change to one names which runbooks it moves**. The tenant-facing half is already ruled —
`BR-RBS-038`: a change to a shipped template is **offered** on a tenant's copy and never applied
without a person accepting it.

---

### Wave D — the three surfaces · phase 1

**Goal a clerk can see:** the landing screen answers *is anything waiting on me · what is running now · what can
I run*, and the template library draws **eight** category chips for twelve templates — **none reading Assets or
Work**. ⚠ **THE *ASSETS* HALF OF THAT SENTENCE IS SUPERSEDED FROM 2026-09-07**: `US-RBS-043` landed *Meters past change-out age or never tested* as the Assets category's first runbook, so Assets draws a chip now and only **Work**, Accounts, Customer portal and Business are the empty ones. `RB-019`'s RULE is unchanged and is what the chip row obeys — a category holding no template draws nothing; what moved is which categories hold none. `test_us_rbs_003_endpoints.py` derives that set from the registry rather than naming it, so this pair of sentences is now the only place it is written down by hand.

**Stories:** `US-RBS-003` · `US-RBS-018` · **Depends on:** C · **Size:** two people, one and a half weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **D1** | 2a | `GET /runbooks` · `/{key}` · `/templates` · `/runs` · `/runs/{id}` · `/runs/{id}/report` · `/runs/{id}/records` · the two result CSVs. **Every list pages server-side**, `per` clamped 50/100/200/500/1000, default 50 | 003 · 018 · `NFR-3` | C6 | `RB-024` | L |
| **D2** | 2b | **`RBS-001`** — page head *Runbooks · Checks report. Actions send.*, KPI strip of four, three sections in order, a kept Draft run. Against `wireframes/RBS-001.1`–`.3` | 003 · B14-2 · B14-31 · B14-32 | D1 | — | L |
| **D3** | 2b | **`RBS-002`** — the library, **chips built from the templates present and never from the fixed sixteen** (`TC-RBS-20`); template detail with *What it can touch*, derived from `ports[]` | 018 · `BR-RBS-025` | D1 | `RB-019` | L |
| **D4** | 2b | **`RBS-003`** — My runbooks, all / filtered to Actions / empty | 018 | D1 | — | M |
| **D5** | 2a | **Role visibility defaulting from category**, widenable per runbook by an admin; **Onboarding & Cutover's order rule** (first while a plan is open, last once it closes) | 018 · `BR-RBS-024` · `BR-RBS-026` | D3 | `RB-050` | M |
| **D6** | 2c · 2d | `TC-RBS-20` red on a chip row built from the fixed list, then green. `rbs-d-the-library.mjs` — count the chips, switch to a Finance user, confirm Platform is absent | 018 · law 7 | D5 | — | M |
| **D7** | version · doc | CHANGELOG · version · decision-log row | — | D6 | — | S |

---

### Wave E — the definition surface: add, clone, version · phase 1 · **closes phase 1**

✅ **WAVE E IS COMPLETE AND PHASE 1 IS CLOSED — 2026-09-06, version `2.214.0`.** `E1`, `E2`, `E3`
and wave D's `D5` landed in the morning; `E4`, `E5` and `E6` landed the same evening. Built:
the three write routes (`POST /runbooks` · `POST /runbooks/{key}/clone` · `PUT /runbooks/{key}`),
`runbook_versions` append-only **in the database** (`migrations/0003`), the trust ratchet's state
and its refusal at `services.open_run`, the template-update OFFER and the one act that applies it,
role visibility from the category, Onboarding & Cutover's order rule — **and, from the evening
commits, the mapper `RBS-004` had been missing all day (`DEF-RBS-4308`), the Activity tab over real
data, the screen halves of `TC-RBS-13`/`TC-RBS-24`, and a walkthrough that CLICKS `+ Add`, `Clone`
and `Change limits` instead of driving their routes.**

⚠ **THE GOAL SENTENCE IS NOW TRUE, AND ONE CLAUSE OF IT IS TRUE IN A NARROWER SENSE THAN IT READS.**
*Tom clones Dunning and names it Commercial accounts* — a button, a modal and a landing on the copy's
own screen. *The Activity tab names him and the time* — `v2 · Cap set to 400 · Dana Whitfield ·
09/06/2026`, read out of a browser. *The previous run still reads v3 with its report unchanged* —
asserted on both sides and enforced by a trigger. ⚠ ***Sets the first reminder to 15 days* IS THE
CLAUSE THAT IS NOT LITERALLY TRUE**: a tenant can set the runbook's SETTINGS (its cap, its schedule,
its approval, its visibility) and cannot yet set a PARAMETER value, because `services.EDITABLE_SETTINGS`
has nowhere to put one — `DEF-RBS-4338`. **Change scope** therefore still refuses, with a test that
goes red the day a parameter field joins the edit body.

⚠ **WHAT PHASE 1 STILL CANNOT DO, IN ONE LINE:** press **Run**. `POST /runbooks/{key}/runs` is wave
`L`, phase 2, and `RBS-004`'s `Run ▶` refuses over it with the same shape of clock.


**Goal a clerk can see:** Tom clones *Dunning*, names it *Commercial accounts*, sets the first reminder to 15
days — **both rows appear with their own schedule, cap and dry run**, the Activity tab names him and the time,
and the previous run still reads **v3** with its report unchanged.

**Stories:** `US-RBS-038` · `US-RBS-040` · **Depends on:** D · **Size:** two people, one and a half weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **E1** | 2a | `POST /runbooks` (add a template) · `POST /runbooks/{key}/clone` · `PUT /runbooks/{key}` (**writes a new version**) | 038 · 040 · `BR-RBS-038` | D1 | `RB-040` | M |
| **E2** | 2a | **Versioning**: `runbook_versions` append-only; a run pins its version at start; **the trust ratchet** — an edited Action is dry-run only until one clean dry run is reviewed | 040 · `BR-RBS-036` · `BR-RBS-038` | E1 | `RB-051` | L |
| **E3** | 2a · 2b | **Template updates OFFERED, never applied**: *"Template updated · 1 new step · Review →"* on the copy, changing nothing until pressed | 040 | E2 | `RB-051` | M |
| **E4** | 2b | `RBS-004` Activity tab. ⚠ **No version id and no runbook id is ever the visible value of a field** (B14 rule 31) | 040 · B14-31 | E2 | — | M |
| **E5** | 2c | `TC-RBS-13`, `TC-RBS-24` — the old run's stored report **byte-identical**, the next run at v4, the copy's steps unchanged after a template bump | 040 | E3 | — | M |
| **E6** | 2d · review | `rbs-e-clone-and-version.mjs`, **the phase-1 exit walkthrough**: clone → edit → run → reopen the old run → bind a port to a Check and watch the build fail. **Phase 1's CHANGELOG entry** | 038 · 040 | E5 | — | M |

---

### Wave F — test bill · phase 4

**Goal a clerk can see:** one account priced with **every line explained**, or **one refusal naming the service
and the date** — and `billing`'s number series is untouched.

**Stories:** `US-RBS-004` · **Depends on:** E · **Size:** two people, one and a half weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **F1** | ground | **Draw `RBS-004-R23` and `RBS-006-R23`.** ⚠ Runbook 23 is a **reserved definition — its result screen is NOT DRAWN in the source**, so there is no build sheet to compare against and law 6 cannot be performed. **The frames come first, before a component is written** | 004 · law 6 | E6 | `RB-123` | M |
| **F2** | 2a | `definitions/test_bill.py` — four read steps, **step 2 calls the rating engine's own path**. A seam to rating, in the register | 004 · `BR-RBS-002` | E1 | `RB-123` | L |
| **F3** | 2c | **`TC-RBS-4c`: the same account through the test bill and through a real bill run must produce an identical line set and identical amounts to four decimals.** Planted second implementation goes red | 004 · law 7 | F2 | — | M |
| **F4** | 2b · 2d | The result over `KPIs · Records · Reconciled · Sentence · Downloads`, against F1's sheets. `rbs-f-test-bill.mjs` — price one, refuse one, **assert the number series did not move** | 004 | F1 · F3 | — | M |
| **F5** | version · doc | CHANGELOG · version · decision-log row | — | F4 | — | S |

---

### Wave G — the coverage grid · phase 4

✅ **WAVE G IS COMPLETE — 2026-09-07, version `2.217.0`.** `G1`–`G5` landed together: the composed build
sheet `RBS-006-R24.md`, `definitions/coverage_grid.py`, the `Records` block's grid mode wired and fixed,
14 backend cases and the browser walkthrough `rbs-g-coverage-grid.mjs`.

⚠ **THE GOAL SENTENCE IS TRUE IN SHAPE AND ITS NUMBERS ARE THE FIXTURE'S, NOT THE CARD'S.** On the seeded
utility the grid reads **1 clean · 0 estimated · 2 refused over 3 cells**, and **a red cell opens that
account's own test bill** — pressed in Chromium, landing on `…/runbooks/test_bill/runs/<id>`, a real
frozen result. **21 · 2 · 2 over 25 cells is written against the six-service fixture `US-RBS-005` §4
describes and THAT FIXTURE DOES NOT EXIST IN THIS REPOSITORY**; the demo utility holds three
plan-and-cycle combinations. The card's figure is not wrong, it is a claim about an estate nobody has
seeded — and the grid's own sentence (*All 3 plan and cycle combinations were priced. Left out: 32
sample.*) is what makes the difference readable rather than invisible.

⚠ **EACH CELL IS A REAL CHILD RUN OF RUNBOOK 23, `parent_run` SET** — which is what makes *"a red cell
opens that account's test bill"* a door rather than a sentence, and it is the same three calls wave `I4`
uses for `requires`. **The cost is stated:** a grid of 25 writes 25 extra `runbook_runs` rows and
`RBS-008` does not filter on `parent_run` yet.

⚠ **AND THE GRID DRAWS NOTHING ON THE DEMO SEED WITHOUT HELP (`DEF-RBS-4369`)** — `seed_demo` marks all
72 of its accounts sample and `BR-RBS-014` correctly excludes them. The grid was right and the fixture
was the problem; `rbs_g_seed_coverage.py` promotes a deterministic subset and refuses to report fewer
than two cells.


**Goal a clerk can see:** **21 clean · 2 estimated · 2 refused** over the utility's own accounts; a red cell
opens that account's test bill; fixing the rate moves it to **23**.

**Stories:** `US-RBS-005` · **Depends on:** F · **Size:** two people, one and a half weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **G1** | ground | Draw `RBS-004-R24` and `RBS-006-R24` — the same absence as F1 | 005 · law 6 | F4 | `RB-124` | M |
| **G2** | 2a | `definitions/coverage_grid.py` — **a deterministic pick**, runbook 23 per cell, grouped by outcome. **Sample records never picked** | 005 · `BR-RBS-014` | F2 | `RB-124` | L |
| **G3** | 2b | The **grid display mode of the `Records` block** — no thirteenth block | 005 · `BR-RBS-021` | G1 | — | M |
| **G4** | 2c | `TC-RBS-5b` (two runs, same 25, same order) · `TC-RBS-5c` (no sample) · `TC-RBS-5e` (**states what it left out** rather than a silent `LIMIT 25`) | 005 | G2 | — | M |
| **G5** | 2d · review | **Journey `J-RBS-2` written to `08-qa/01-e2e/journeys/`** and clicked: run → red cell → refusal → fix the rate → re-run → **23**. **Phase 4's first half is closed by this wave; its CHANGELOG entry is wave `K`'s** | 005 · law 6 | G4 | — | M |

---

### Wave H — the work list · phase 4

🟡 **WAVE H IS FIVE SIXTHS DONE — 2026-09-07, version `2.217.0`. `H1`, `H2`, `H3` and `H4` landed; `H5`
is HALF DONE and `H6` is done.**

Built: the engine upserts a run's findings into `work_items` **by fingerprint** at run close
(`engine/work_items.py`), the fingerprint is `<tenant>|<runbook>|<subject>|<kind>` and **never contains
the run id**, the item **closes itself** when the finding stops recurring, `GET · PATCH /work-items[/{id}]`
serve and edit it paged on the server, and `RBS-007` draws it at `/{tenant}/runbooks/work`. 15 backend
cases and 9 DOM cases; `TC-RBS-10` was shown RED on an insert-instead-of-upsert (thirty rows) before it
was shown green (one row, thirty days old), and self-closing has its own red half because
`if not findings: return` is the natural line that would break it with everything else still green.

⚠ **WHAT `H5` STILL OWES, EXACTLY.** `J-RBS-1`'s walkthrough is written and CLICKED for the half this
wave can perform: the work list draws six items raised by two runbooks, every row links to the run that
raised it, the ages read from the FIRST sighting, and **Resolve is pressed and the row leaves the open
list**. What is NOT clicked is the journey's own last leg — *fix the tax region, re-run, 3 → 2, and the
item closes itself* — because **fixing a tax region and re-running are two acts this product cannot
perform from a screen**: `POST /runbooks/{key}/runs` is wave `L`'s and it is not built. The closing half
is proved by `test_us_rbs_006_work_items.py` against the engine and by the seed script's `--again`, and
the journey file says so rather than claiming a click nobody made.

⚠ **AND THE `Mine` CHIP IS ABSENT.** `GET /work-items` filters on `f.owner` and the screen does not hold
the viewer's id — `useTenantRegional` publishes the tenant's display settings, not the viewer's identity.
A chip that filtered to somebody else's work would be worse than no chip. Three chips, not four.


**Goal a clerk can see:** one screen holding findings, exceptions and human tasks together — and **thirty daily
sweeps over one missing read are one item, thirty days old**.

**Stories:** `US-RBS-006` · **Depends on:** G · **Size:** two people, one and a half weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **H1** | 2a | The engine upserts findings into `work_items` **by fingerprint** at run close. ⚠ **The fingerprint must NOT contain the run id** or every run makes a new row | 006 · `BR-RBS-017` · `BR-RBS-022` | C6 | — | M |
| **H2** | 2a | `GET · PATCH /work-items[/{id}]` — assign, resolve, reopen; **server-side paging** | 006 · `NFR-3` | H1 | `RB-024` | M |
| **H3** | 2b | **`RBS-007`**, populated and all-clear, against `wireframes/RBS-007.1___RBS-007.2` | 006 · B14-31 | H2 | — | L |
| **H4** | 2c | `TC-RBS-10` red on insert-instead-of-upsert, then green; **the item closes itself when the finding stops recurring** | 006 · law 7 | H1 | — | M |
| **H5** | 2d | **Journey `J-RBS-1` written and clicked**: run *Can we bill?* → open the work list → fix the tax region → re-run → **3 → 2, and the item closes itself** | 006 · law 6 | H4 | — | M |
| **H6** | version · doc | CHANGELOG · version · decision-log row | — | H5 | — | S |

---

### Wave I — schedules, the pre-bill sweep and run history · phase 4

**Goal a clerk can see:** **nobody opens the product.** At 06:00 tenant local the sweep runs, and the morning's
work list holds the accounts that would have failed, each with its step and its fix.

⚠ **`I1` SAID *IT LANDED IN PHASE 2 WITH WAVE `L`* AND IT HAD NOT — CORRECTED 2026-09-07 (`DEF-RBS-4353`).**
The 2026-09-06 re-cut moved the `I1` ROW into wave `L`'s table and struck it here in the same edit, on the
reasoning that wave `M`'s soak and wave `O`'s event trigger both need a job kind to run on. **Wave `L`
landed; `I1` did not.** The two strings `runbooks.check` and `runbooks.act` were in three documents and in
zero Python files, and `apps/runbooks/apps.py`'s own `ready()` docstring said so. **It is built by this
wave, 2026-09-07**, together with the `runbooks` queue and the `celery-runbooks` worker that drains it, and
`G117` now refuses a tree carrying one half without the other. **The wave was one task smaller on paper and
was not, which is why nobody may read a struck row as evidence.**

**Stories:** `US-RBS-007` · **Depends on:** H · **Size:** two people, one and a half weeks (was two, less `I1`).

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **I1** | 2a | ✅ **DONE 2026-09-07, HERE — IT WAS STRUCK AS *ALREADY DONE* AND WAS NOT (`DEF-RBS-4353`).** Job kinds on the **existing** platform runner — `runbooks.check` and `runbooks.act` — registered in `apps/runbooks/scheduler.py` together with the `runbooks` queue they ride, in one statement, plus `docker-compose.yml`'s `celery-runbooks` consumer in the same commit. ⚠ **One scheduler, not two**: integration fetches and runbook runs are kinds on the one runner (`BR-INT-054`). `G117` fails a tree with routing and no consumer, or a beat entry declared and never installed | 007 · `BR-INT-054` | A3 | `RB-012` | L |
| **I2** ✅ | 2a | ✅ **DONE 2026-09-07.** **Cron evaluated in the TENANT's timezone.** ⚠ `DEF-MET-4101`'s root cause is a clock question answered in the wrong frame — every check compared UTC while the product showed local, so the two never met. **The test asserts the tenant's wall clock, not UTC** | 007 · `BR-RBS-016` | I1 | `RB-012` | M |
| **I3** ✅ | 2a | ✅ **DONE 2026-09-07.** **A missed firing RAISES** — run history shows **Failed**, naming the missed time; **never a silent catch-up and never six replays** | 007 · `BR-RBS-016` | I2 | `RB-012` | M |
| **I4** ⏸ | 2a | ⏸ **NOT BUILT 2026-09-07 — the wave I lane ran out of runway after `I1`, `I2`, `I3`, `I6` and the walkthrough, and says so rather than leaving the row to be read as done.** `registry.validate_requires()` refuses a dangling requirement at STARTUP and `services.open_run` takes a `parent_run`; nothing calls the required Check first. **`requires` wired** — the required Check runs as its own run, `parent_run_id` set, linked from step 1; a failure stops the caller with **"Never reached"** on every later step | 007 · `BR-RBS-027` | I1 | `RB-036` | M |
| **I5** ⏸ | 2a | ⏸ **NOT BUILT 2026-09-07 — see `I4`. It depends on `I4`, so the two land together.** `definitions/billing_readiness.py` — **runbook 3, eight steps**, step 8 prices a sample **through the real engine** | 007 | F2 · I4 | `RB-103` | L |
| **I6** ✅ | 2b | ✅ **DONE 2026-09-07** — `RBS-008` is routed at `/{tenant}/runbooks/runs`, `RBS-001`'s *History →* is released, and `RBS-004` Overview's *Next* is a real date. **`RBS-008`** run history, against `wireframes/RBS-008`; the next-run line on `RBS-004` Overview **in the tenant's zone, with the zone named** | 007 | I3 | — | M |
| **I7** ◑ | 2c · 2d | ◑ **PART DONE 2026-09-07 — the timezone and missed-firing halves are built and walked (`rbs-i-the-clock.mjs`, ten sections green in Chromium); `TC-RBS-21` waits on `I4` and `TC-RBS-22` on `I5`.** `TC-RBS-21` · `TC-RBS-22` · the timezone case on two tenants. `rbs-i-nobody-opens-it.mjs` — **advance the clock, do not log in, then read the work list** | 007 · law 6 | I5 · I6 | — | L |
| **I8** ✅ | version · doc | ✅ **DONE 2026-09-07 — version 2.216.0, its CHANGELOG entry, three decision-log rows and `BR-RBS-016` stamped.** CHANGELOG · version · decision-log row | — | I7 | — | S |

---

### Wave J — cutover reconciliation and plan evidence · phase 4

✅ **WAVE `J` IS BUILT — 2026-09-07.** `definitions/cutover_readiness.py` (runbook 2, **nine SET
steps**), `apps/runbooks/cutover.py` (plans, items, evidence) and three routes. Measured through the
engine on the seeded utility, against a trial balance built from the loaded bills with twelve lines
deliberately short: **No-go · Balances off by USD 1,204.05 · 11 accounts disagreeing across 12
lines.** The eleven-versus-twelve is the PO's **bill grain** doing its job — one account carries two
of the broken bills, and at account grain those two would have netted and reported a tie.

⚠ **`J2` SAYS *"read once through the import runner"* AND IT IS NOT, AND THE REASON IS DECISIVE
RATHER THAN A PREFERENCE.** `trial_balance` **is not one of the six `IMPORT_TARGETS`**, so
`metering.import_runs.extract` refuses it by name and a runbook calling
`staged_import_batch("trial_balance")` could **never** get a batch back — a check **incapable of
passing**, hard-won law 7's third shape. The file is therefore the `file` parameter's own content,
parsed by the runbook, with every unreadable line KEPT as a finding carrying its line number.
Recorded in the decision log of 2026-09-07 with its two other reasons; the day `metering` adds the
target, `resolve()` is where it changes.

⚠ **`J2`'s `requires` IS DECLARED AND THE ENGINE DOES NOT YET RUN IT** — that is task `I4` and wave
`I` has not landed. **Step 1 says so out loud** rather than drawing a tick nobody computed, and
`test_step_one_says_the_sub_run_did_not_run` is the test that goes RED the day `I4` lands, which is
what hard-won law 2's mirror asks for in the same commit as the hold.

**Goal a clerk can see:** *No-go · 2 of 9 steps not clear · Balances off by **$1,204.05** · 2 plan items open* —
and after the twelve are resolved and it is re-run, **the plan item goes green on its own**.

**Stories:** `US-RBS-008` · **Depends on:** I · **Size:** two people, one and a half weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **J1** ✅ | 2a | `cutover_plans` + `cutover_plan_items` behaviour; `GET · POST /cutover-plans` · `PATCH /cutover-plans/{id}/items/{seq}` · `POST …/evidence`. **A NULL `runbook_key` is a human task the engine never performs** — and `attach_evidence` REFUSES one by name, so a run can never complete somebody's signature | 008 | A3 | `RB-035` | M |
| **J2** ✅ | 2a | `definitions/cutover_readiness.py` — **nine steps, `requires` runbook 1** declared (the engine does not yet RUN it — `I4`), the trial balance as a **`file`** parameter ⚠ **read as the parameter's own CONTENT, not through the import runner** — `trial_balance` is not one of the six `IMPORT_TARGETS`, so the runner route is a check incapable of passing (decision log 2026-09-07) | 008 · `BR-RBS-027` | I4 | `RB-102` | L |
| **J3** ✅ | 2a | **The run's result becomes the item's evidence** — run id and figures on the item, read from the FROZEN report; a zero-variance re-run turns it green. ⚠ *Zero variance* is read as **the verdict carries no blocker**, not as *the difference is 0.00*: a run whose balances tie perfectly but which found sample data present is not a cutover anybody should tick | 008 | J1 · J2 | `RB-035` | M |
| **J4** ✅ | 2c | **The cutover pair**: legacy TB **$412,880.4400** against loaded balances differing on **12 LINES** by **$1,204.0500**; **one line per OPEN INVOICE** (PO 2026-09-05), not per account. ⚠ **The plan said *12 accounts* and the fixture is 12 LINES** — at bill grain one account may carry several, which is exactly what the grain is for, and `test_the_grain_is_the_BILL_and_an_account_may_carry_several` is the case that proves it matters | 008 · hard rule 2 | J2 | — | M |
| **J5** | 2b · 2d | The `Verdict` + `Reconciled` blocks on `RBS-006-R2`; `rbs-j-cutover.mjs` — read **$1,204.05** on screen, resolve, re-run, watch the item go green | 008 · law 6 | J4 | — | M |
| **J6** | version · doc | CHANGELOG · version · decision-log row | — | J5 | — | S |

---

### Wave K — books tie-out · phase 4 · **closes phase 4**

✅ **WAVE `K` IS BUILT — 2026-09-07, AND PHASE 4's CODE IS COMPLETE FOR `F`, `J` AND `K`.**
`definitions/month_end.py` — runbook 9, **eight SET steps and one per-record**, tax tolerance
`$0.0000` **refused at CONSTRUCTION** rather than at run time. Measured through the engine on the
seeded utility, **August 2026**: *Not balanced · 6 of 9 steps clear · USD 1,195.05 unapplied · Tax
off by USD 816.45 · Tax remittance not done.* Receivables **$7,984.68 = $7,984.68** (Ties), deposits
held **$750.00 = $750.00** (Ties), supplier cost ties. **Close period ✓** in the danger tier,
DISABLED, carrying *"4 blockers open."*

⚠ **`K2`'s *"ABSENT (not disabled)"* IS WRONG AND IS AMENDED — `DEF-RBS-4360`.** Five sources say
DISABLED WITH ITS REASON and two say absent, and the five include every artefact that is actually
built against: the **`RBS-006-R9` build sheet** (*"danger · default · 14px · DISABLED — reason on the
button title"*, and a build sheet is the acceptance check), **`RB-109`**, **`RB-109`'s own stated
absences section** which CLOSED this question that way under `RBR-06`, **`contract.PAYLOAD_FIELDS`**
where `enabled: false` structurally requires `reason`, and the shipped **`ActionBlock.tsx`**. **The
distinction is worth more than the ruling: a control is ABSENT when the CAPABILITY does not exist**
— wave `L7`'s Approve, because nothing can send — **and DISABLED when a PRECONDITION is not met.**

⚠ **AND THE FIRST THING THE TIE-OUT FOUND WAS A FAULT IN THE COMPARISON IT READS — `DEF-LED-4356`.**
`ledger.tie_out._tax_row` takes the GL side cumulative to `period_end` and the register side for the
period only, so from the second posted period it reports drift equal to every earlier period's tax
**on a correct book** — the exact sentence `tie_outs`' own docstring says would be wrong. July's
drift is the real **−$2.30**; August's **+$816.45** is July's cumulative GL. **Filed, not fixed:**
another module's signed money comparison on a 🔒 path. Runbook 9 NAMES it on the row.

**Goal a clerk can see:** *Not balanced · 6 of 9 steps clear · Tax off by **$14.25** · **$312.00** unapplied ·
3 bank lines unmatched* — each linking to the screen that settles it; and on a clean period, **Close period ✓**
in the danger tier, pressed by a person.

**Stories:** `US-RBS-009` · **Depends on:** J · **Size:** two people, one and a half weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **K1** ✅ | 2a | `definitions/month_end.py` — **nine steps: eight SET, one per-record**; **tax tolerance `$0.0000`, refused at CONSTRUCTION** — a run-time check would mean a raised tolerance living on a live schedule | 009 · `BR-RBS-029` · `BR-RBS-023` | B3 | `RB-109` | L |
| **K2** ✅ | 2b | The `Action` block's **Close period ✓** — danger tier (B14 rule 6), ⚠ **DISABLED WITH ITS REASON while blockers remain, NOT absent** (`DEF-RBS-4360`: this row said *absent* against five sources including the build sheet and the shipped renderer), and performed by the **ledger's** own service | 009 · `BR-RBS-030` · B14-6 | K1 | — | M |
| **K3** ✅ | 2c | `TC-RBS-17` — the set step **once**, the per-record step once per subject, asserted on the DECLARATION and again through the engine's own `step_runs` counter rather than by counting side effects | 009 · law 7 | K1 | `RB-018` | M |
| **K4** | 2c | August 2026: **3 bill runs · 4,118 payments · 61 adjustments**; the unbalanced case at exactly the three figures; a period off by **$0.01** proving the floor | 009 | K1 | — | M |
| **K5** | 2d · review | `rbs-k-month-end.mjs` — unbalanced, then balanced, then press Close and watch **the ledger** post. **Phase 4's CHANGELOG entry** | 009 · law 6 | K4 | — | M |

---

### Wave L — the acting half, with sending switched OFF · phase 2 · dry

⚠ **THIS WAVE MOVED FROM PHASE 4 TO PHASE 2 ON 2026-09-06** (§1). It is now the first wave after the
foundation, and everything dangerous in this module is in it.

⚠ **AN AUTOMATED ACTION HAS NO NAME, AND THAT IS A NAMED PREREQUISITE OF THIS WAVE — NOT A NOTE.**
`BR-AUD-003` says `actor_user_id` NULL means *"system job"*, so **every automation in the product is
indistinguishable from every other**, and a runbook with no identity of its own would have to borrow a staff
login — **a person would appear to have personally sent 812 letters at 07:00 on a Monday.** Task `L1` closes
it, in the audit module, and **`L1` is not this module's code.** ⚠ **This blocked the old phase 4 and now
blocks PHASE 2, which is three phases earlier.** **What it costs if it slips: the whole of phases 2, 3 and 5
stop** — no writer may be bound until it lands (`L2` depends on `L1`), so the acting half does not start, and
with it neither the integration runbooks nor the rest of the catalogue. It is the single largest schedule
risk this plan carries.

⚠ **AND `I1` — THE TWO JOB KINDS ON THE PLATFORM RUNNER — LANDS HERE, WITH THIS WAVE.** `I1` keeps its id
and its description (see wave `I`), because renumbering it would move every citation of it. It moves because
**wave `M`'s soak and wave `O`'s event trigger both need something to run unattended on, and wave `I` is now
phase 4** — leaving it there would make phases 2 and 3 depend on a later phase, which is not a cost, it is a
broken order. **`I2` (cron in the tenant's timezone), `I3` (a missed firing raises) and the rest of wave `I`
stay in phase 4**, and until they land **wave `M`'s cycle is started BY HAND every Monday** — see `M1`.

**Goal a clerk can see:** Review reads **812 to send · 97 skipped · 95 needing a person**, every row naming its
rule in words — **and there is no button that can send anything.**

**Stories:** `US-RBS-010` · `US-RBS-011` · `US-RBS-012` · `US-RBS-014` · **Depends on:** E (was K, before the 2026-09-06 re-cut) · **Size:** two people, three weeks.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **L1** | ground · 🔒 | ✅ **DONE 2026-09-06 — THE AUDIT ACTOR EXISTS.** Landed as **`US-AUD-010` / `BR-AUD-019`** in the AUDIT module (migration `audit/0007`), which is where it always belonged. `audit_log` carries `actor_kind` · `actor_label` · `actor_version`; a runbook passes `core.audit.AutomationActor("runbook", "Returned payments", "4")` and a clerk reads **"Returned payments, version 4"**. It **cannot** borrow a staff login: the writer refuses a named actor that also carries a user id, and so does the table's CHECK. `TC-RBS-12` was shown **red first at the pinned tip `a10eae00`** (*"the actor is BLANK"* / *"borrowed Alex Reed's login"*), then green — `06-backend/tests/test_us_aud_010_audit_actor.py`. ⚠ **`L2` IS STILL WHOLLY UNDONE AND IS THIS MODULE'S OWN WORK:** the platform can now express the actor; nothing in Runbooks yet PASSES one, because no port has a writer behind it | 014 · `BR-RBS-015` · hard rule 7 | E6 | `RB-011` | L |
| ~~**I1**~~ (moved back) | 2a | ⚠ **THIS ROW WAS NEVER BUILT AND WAVE `I` BUILT IT INSTEAD, 2026-09-07 (`DEF-RBS-4353`).** The 2026-09-06 re-cut moved the task here and struck it in wave `I`; wave `L` landed `L1`, `L2`, `L5` and `L6` and left this one. **It is done in wave `I`, where the row it was struck from lives** — see wave `I` above. Kept here, struck, so a citation of `I1` from either table still lands and so the miss is visible rather than tidied away | 007 · `BR-INT-054` | A3 | `RB-012` | — |
| **L2** | 2a · 🔒 | **The thirteen ports bind their writers** — one service function in its owning module each, **idempotent per record**, each writing its own audit row **through the engine**. `HUMAN-REVIEW-PENDING` + a row in `09-human-review-ledger.md` **in plain English with a worked figure** | 010 · `BR-RBS-022` | L1 · A4 | `RB-017` | L |
| **L3** | 2a · 🔒 | **The gate** — batch approval carrying the **server-side** count; **409 + `runbooks.refusal.plan_changed`** when the plan has moved; **the second approval on every money-bearing action** | 011 · `BR-RBS-005` · `BR-RBS-018` | L2 | `RB-003` · `RB-014` | L |
| **L4** | 2a · 🔒 | **The cap — it REFUSES the run and never truncates.** *"Too many for one run"* with **Narrow scope · Raise limit · Send first 400** as the clerk's own choices; **raising the limit writes a new version** | 011 · `BR-RBS-006` | L3 | `RB-004` | M |
| **L5** | 2a · 🔒 | **Stop, reachable at every moment**; **the idempotency key** on (runbook, run, record, action kind) with a **UNIQUE index on (tenant, idempotency_key)** | 012 · `BR-RBS-008` | L2 | `RB-005` · `RB-007` | L |
| **L6** | 2a | `definitions/dunning.py` — **runbook 8, registered as an Action with its ports declared and the runbook DISABLED for live**; guards evaluated **before** step 1 | 010 · `BR-RBS-012` · `BR-RBS-014` | L2 | `RB-108` | L |
| **L7** | 2b | `RBS-005`'s remaining steps — **Review · Approve · Applying · Done**, plus **cap refused**; the `RBS-004` **Limits** tab. **The Approve control is absent in the dry half, not greyed** | 010 · 011 | L4 | — | L |
| **L8** | 2b | The in-app staff alert when a run needs a person — the product's own bell, **no delivery provider involved** | 011 | L4 | `RB-034` | S |
| **L9** | 2c | **The ladder set**: 1,004 past due — 812 notice · 43 plan in good standing · 31 protected · 23 undeliverable · 95 over the fee limit (**97 skipped** = 43+31+23). **The guarded accounts**: 2 medical · 2 dispute · **3 sample**. **The failure row**: one notice write failing a constraint | 010 · 012 | L6 | — | M |
| **L10** | 2c | `TC-RBS-2` · `TC-RBS-3` · `TC-RBS-6` · `TC-RBS-8` · `TC-RBS-9` · `TC-RBS-11` · `TC-RBS-22`, **each shown RED on the specific wrong build named in `EP-RBS-04`** — a build that truncates, a guard after the checks, an approval ignoring the count, a stop that only sets a flag | law 7 | L9 | — | L |
| **L11** | 2c · **PG** | **`TC-RBS-5` and `TC-RBS-4` on real PostgreSQL** — one record failing a constraint leaves the other **1,003** committed; the ladder twice queues **248**, not 496 | law 14 | L9 | `RB-006` | M |
| **L12** | 2d · review | `rbs-l-the-dry-half.mjs` — dry-run the ladder, read the four figures, confirm **97 skipped** includes the protected account, confirm **there is no Approve that sends** | 010 · law 6 | L11 | — | M |
| **L13** | version · doc | CHANGELOG · version · decision-log row · review-ledger rows for **every 🔒 task**, each in plain English with a figure | — | L12 | — | M |

---

### Wave M — a full cycle, dry, in production · phase 2 · dry · **closes the dry half**

⚠ **THIS WAVE'S OUTPUT IS EVIDENCE, NOT CODE. It is the reason the phase is split, and skipping it collapses
the split into nothing.**

⚠ **AFTER THE 2026-09-06 RE-CUT, THIS WAVE IS THE WHOLE SAFETY ARGUMENT.** The old order reached an Action
only after the engine had been proved on Checks that could not touch a customer; the new order reaches the
acting half immediately after the foundation. **What preserves the argument is that `M` stays exactly where
it is, between `L` and `N`, at its full length.** ⚠ **SHORTENING IT, OR FOLDING IT INTO `L`, IS THE ONE
CHANGE THAT WOULD MAKE THE REORDER UNSAFE** — and it is the change that will look most attractive, because
`M` produces no code and a lane under pressure reads that as slack. It is not slack. It is a cycle of real
plans a person has read and a database diff nobody can argue with, and `M4`'s go/no-go is what stands
between a misconfigured ladder and three thousand wrong notices that cannot be unsent.

**Goal a clerk can see:** a month of dry runs they can read — *"here is what it would have done every Monday"* —
and **a database diff showing nothing outside this module's seven tables was written.**

**Stories:** none new · **Depends on:** L · **Size:** one person, one cycle (elapsed), a few days of work.

| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **M1** | ground | The ladder runs in **DRY mode** on a real tenant, once a week for a full cycle. Every Monday it plans and stops. ⚠ **STARTED BY HAND, NOT BY A SCHEDULE, UNTIL WAVE `I` LANDS — AND `I2`/`I3` LANDED 2026-09-07, so a re-soak of this cycle no longer needs a person pressing Run; the scheduler's own soak is owed and is named in the wave `I` record** — `I2` (cron in the tenant's timezone) and `I3` (a missed firing raises) are phase 4 under the 2026-09-06 re-cut, so a person presses Run each Monday. **What that costs, said plainly: the PLANS are soaked and the SCHEDULER is not**, and the scheduler gets its own soak when wave `I` lands. The go/no-go in `M4` is about the plans, so it is unaffected | 010 | L13 | — | S |
| **M2** | 2c · gate | **A recurring database diff** asserting zero rows written outside the seven tables, run after each dry firing and **shown RED first with a writer deliberately bound** | law 7 | M1 | — | M |
| **M3** | 2d | The cycle's plans read by a person, **and the discrepancies filed as defects rather than explained away**. ⚠ **READ THE FAILURES YOU DID NOT CAUSE** — and where a red is called pre-existing, **date it** with `git log -S "<the failing symbol>" -- <file>` (`DEF-CWP-4187`) | law 7 | M2 | — | M |
| **M4** | review | **The go/no-go for the live half**, written down with what the cycle showed. **The dry half is not a formality**: if the plans were wrong, the live half does not start | — | M3 | — | S |

✅ **WAVE `M` IS RUN AND THE VERDICT IS `NO-GO`** (2026-09-06). The evidence is
`15-wave-m-dry-cycle.md`; the ruling and its figures are in the decision log of the same day.

**What it showed.** `L9`'s board did not exist — the ladder resolved **zero** accounts on the seeded tenant
— so it was built: **1,004 past-due accounts** on a real tenant, on top of the **31** the seed already had.
Five firings, one a Monday, 3 → 31 August, **started by hand** (the cron is `I2`/`I3`, phase 4 — so *the
plans are soaked and the scheduler is not*). Firing 1 planned **835** notices — 323 reminder · 250 ten-day ·
170 five-day · 92 certified final; firings 2, 3 and 5 planned **0**; firing 4 planned **43**, the
payment-plan accounts whose pause lifted on its own. **878 notices for 878 accounts across the month, never
one twice.** **62 accounts were guarded and never walked.** The database diff was clean on all five and was
proved RED on a real foreign write — 1,670 outbound messages — at the third attempt.

⚠ **`M2`'s "zero rows outside the seven tables" is the WRONG assertion and the first run said so:**
`audit_log` is outside them and `BR-RBS-022` REQUIRES it to move. It is asserted to the row instead — exactly
one audit row per act — because a blanket exemption is the hole a real foreign write hides in.

**Six defects. Three of them block `N`:** `DEF-RBS-4345` (a live run executes as a DRY run — `N1` is not a
one-line change), `DEF-RBS-4343` (with a writer bound every act is refused for want of a template — the live
half would queue **0**, not 248) and `DEF-RBS-4352` (`RBS-006` crashes on the ladder's result, so nobody can
read the plan). A fourth is worse than any of them for the customer: `DEF-RBS-4347` — **the ladder never
climbs**; `account_collection_state` held 512 rows before the cycle and 512 after, `notice_history` 0 and 0.
`DEF-RBS-4340` was found and FIXED in this wave (the ladder could not complete one run at all).
`DEF-RBS-4348` is not a blocker.

⚠ **AND `L3` AND `L4` ARE NOT ON THE BRANCH.** There is no approval endpoint and nothing enforces
`most_per_run`: **a run of 835 against its own default cap of 400 was neither refused nor truncated.** Phase
2's promise is *a person approves a plan of a known size* and today neither half of that sentence is code.

✅ **AND IT WAS RUN AGAIN ON 2026-09-07, AGAINST `642a3cee`, BECAUSE THE BUILD IT MEASURED NO LONGER
EXISTED — THE VERDICT IS STILL `NO-GO` AND THE REASON HAS MOVED.** Evidence: `15-wave-m-dry-cycle.md`
§8. Three of the first cycle's six findings had been fixed in the twenty hours between the two, so
inheriting the verdict would have been a claim about a build nobody was shipping.

**What the second cycle showed.** The board still is not in the seed — one firing before seeding
resolved **31 subjects and planned 0**, all of them guarded sample accounts — so it was rebuilt:
**1,004 past-due accounts** on top of the **31** already there. Five firings, Mondays 3–31 August,
started by hand. Firings 1–3 planned **812** (300 reminder · 250 ten-day · 170 five-day · 92
certified final); firings 4–5 planned **855**, the 43 payment-plan accounts whose pause lifted on 23
August. **62 accounts were guarded and never walked.** The database diff was **clean on all five**,
with `audit_log` moving by exactly the number of acts each run performed, and it was proved RED on a
real live firing: **812 acts came back `queued`**, `outbound_messages` 337 → 1,961, `notice_history`
0 → 1,624, `account_collection_state` 512 → 812. **The ladder climbs** — every account exactly one
rung — and a live firing repeated on the same day queued **0**.

⚠ **THE NO-GO NOW RESTS ON ONE SENTENCE: A CLERK CANNOT READ THE PLAN AND NOBODY CAN APPROVE ONE.**
`DEF-RBS-4387` — `RBS-006` draws the five headline tiles as **labels with no numbers**, so the figure
812 appears nowhere on the screen; `DEF-RBS-4388` — 977 rows in one page with no pager, `NFR-3`, and
the paging endpoint never called; and **`L3` is still not on the branch**, so there is no approval at
all. `L4` IS built and refuses correctly: a cap of 400 against 973 walked gave a `failed` run
carrying *planned 973 · cap 400 · pinned 1,035*. ⚠ **But `DEF-RBS-4382`: the number a clerk reads is
not the number enforced** — `RB-108`'s *Most per run · 400* resolves on every run and is read by
nothing, while the engine compares against `runbook.cap`, which is null until an admin types one.

**Eight defects — seven in the product and one in this wave's own check. Three block `N`:** `DEF-RBS-4387` (no numbers on screen) · `DEF-RBS-4388`
(`NFR-3` on the record table) · `DEF-RBS-4382` (two caps, one enforced). Not blocking:
`DEF-RBS-4380` (a run's per-record list is emptied by the next run — 0 rows from the endpoint for
four of five runs against 973 in each frozen report) · `DEF-RBS-4383` (a raw skip code on screen) ·
`DEF-RBS-4386` (*Email, then post* queues both — 1,624 messages for 812 accounts) · `DEF-RBS-4389`
(the Planned column reads `queue_notice`). `DEF-RBS-4381` was the CHECK itself and is fixed here.

⚠ **AND `I2`/`I3` LANDED THE SAME DAY AND THIS CYCLE STILL DID NOT USE THEM.** `scheduler.decide()`
correctly makes the ladder due at **2026-09-07 12:00 UTC** for *Mondays 07:00 `America/Chicago`*, and
**not one firing went through `sweep()`**. The plans are soaked twice over; the scheduler has still
never run a runbook.


---

### Wave N — the ladder goes live · phase 2 · live · **closes phase 2**

⚠ **A DELIVERY PROVIDER MUST BE CONNECTED, or this changes nothing a customer can see** — the queue fills and
nothing leaves the building.

**Goal a clerk can see:** **248 notices queued** against the tenant's own ladder, **none** to a protected or
disputed account; a re-run queues **0** and names the 248; every audit row reads *Collections ladder ·
version 3*.

**Stories:** `US-RBS-013` · **Depends on:** M · **Size:** two people, one week.

⛔ **BLOCKED 2026-09-06 BY `M4`'s NO-GO — DO NOT START THIS WAVE.** Five conditions, all testable, are
listed in `15-wave-m-dry-cycle.md` §5: `DEF-RBS-4352` closed and the plan readable on screen ·
`DEF-RBS-4345` closed so a live run actually binds a writer · `DEF-RBS-4343` closed so an act comes back
`done` rather than `held` · `DEF-RBS-4347` closed or ruled (whose act the tier advance is — **ours to decide
and write down, not the Product Owner's**, law 13) · `L3` and `L4` built. ⚠ **`N1` reads *"a ONE-LINE change
on machinery already watched — a wave that needs more than this has proved the dry half was not the same
code."* That test has been run and it comes back the second way.**

⛔ **STILL BLOCKED AFTER THE SECOND CYCLE, 2026-09-07 — AND THREE OF THE FIVE CONDITIONS ABOVE ARE NOW
MET.** `DEF-RBS-4345` and `DEF-RBS-4347` are fixed and MEASURED (a live firing bound its writer, queued
**812** notices and climbed every account exactly one rung); `DEF-RBS-4343` no longer bites runbook 8,
which holds `step_ladder` rather than `queue_notice`; `DEF-RBS-4352` is closed and the screen opens; and
`L4` refuses correctly. ⚠ **A lane has been building this wave while it was blocked** — the fixes above
are its work and they are good — **but the block has not lifted**, and the new conditions are in
`15-wave-m-dry-cycle.md` §8.9: **`DEF-RBS-4387`** (`RBS-006` draws the five headline tiles as labels with
no numbers, so *To send 812* is nowhere on the screen — condition 1 restated for the second cycle
running) · **`L3` still not on the branch** (there is nothing a person can press to approve a plan) ·
**`DEF-RBS-4382`** (the *Most per run · 400* a clerk reads is enforced by nothing; the engine reads a
different field that is null by default) · **`DEF-RBS-4386` ruled** (does *Email, then post* mean both or
a fallback — one live firing queued **1,624** messages for **812** accounts) · **`DEF-RBS-4388`** enough
that a clerk can page 812 rows rather than be handed all of them at once.


| Task | r11 | What it touches | Stories · rules | Depends on | Xref | Size |
|---|---|---|---|---|---|---|
| **N1** | 2a | **The runbook's mode flips to live.** ⚠ **This is a ONE-LINE change on machinery already watched — `BR-RBS-003`, the same code path.** A wave that needs more than this has proved the dry half was not the same code | 013 · `BR-RBS-003` | M4 | — | S |
| **N2** | 2c | `TC-RBS-4` live · `TC-RBS-6` live (protected and disputed accounts receive **nothing**) · `TC-RBS-13a` (**the word is Queued; no screen says Sent**) | 013 | N1 | `RB-007` | M |
| **N3** | 2d | **Journey `J-RBS-3` written and clicked**: dry → confirm 97 skipped → approve 400 → **stop at 120** → re-run → **280, not 400** | 013 · law 6 | N2 | — | M |
| **N4** | 2d | The audit trail read end to end: **400 rows naming the runbook and its version, none naming a person**; run history reads **By: Schedule** | 014 | N3 | `RB-011` | S |
| **N5** | version · doc · review | **Phase 2's CHANGELOG entry.** ⚠ **State the rollback before shipping** (change process step 8): **a notice cannot be unsent** — the rollback is *disable the runbook and keep the runs*, and it is not a rollback of what was sent | — | N4 | — | S |

---

### Waves O · P · Q′ — the integration runbooks · phase 3

⚠ **THIS IS THE PHASE THE 2026-09-06 RULING NAMES**, and its four runbooks are the four the second ruling's
areas feed: **accounting · payment provider · emails · GIS** (§1.2). **Every one is an Action**, so every one
of them needs phase 2 to have landed first — the ports bound, the cap, stop, the idempotency key and the
audit actor.

**Every wave here is the same shape: one module per runbook — scope, steps, report — and NO FRONTEND CODE.**
The conformance suite is the acceptance test; the walkthrough reads the figures off `RBS-006`. **If a wave
here needs a component, the contract failed and the failure is in phases 1 and 2.**

| Wave | Builds | Stories | Goal a clerk can see | Size |
|---|---|---|---|---|
| **O** | **The event trigger** — `batch.landed` · `feedback.landed` · `bill_run.completed`, subscribed by connection kind, **the batch pinned as the run's scope**. ⚠ Integrations replies at the door and stops; our work may happen a second later (`BR-INT-058`). ⚠ **BLOCKED ON A DEPENDENCY THAT IS SCOPED TO NOBODY — see below and §5** | 017 | A lockbox batch lands and **cash application starts within a minute**, the batch named on the run header. Nobody pressed anything | 2 people, 1.5 weeks |
| **P** | **Cash application** (10) — the payment provider · **bank reconciliation** (14) — accounting | 022 · 026 | *"129 applied · 6 need you · 3 duplicates held"* at 06:30 with a by-source table; *"15 matched · 3 need you · $1,910.00 unmatched"*, each unmatched line beside its nearest batch, the bank fee as a tile | 2 people, 1.5 weeks |
| **Q′** ✅ **DONE 2026-09-06** | **GIS reconciliation** (20) — GIS · **undeliverable contacts** (22) — emails. ⚠ **`Q′`, NOT `Q`: this letter held four different runbooks before 2026-09-06** (§1) | 032 · 034 | *"980 applied · 218 need you · 12 never touched"* with **Ours · Theirs** on every queued row; *"31 suppressed · 27 fell back · 4 nothing left"*, with where each suppressed channel fell back to | 2 people, 1.5 weeks |

### Wave `Q′` — what actually landed, 2026-09-06

**Two modules, no frontend code, and the conformance suite as the acceptance test** — the shape this phase
declares, held. `06-backend/apps/runbooks/definitions/gis_reconciliation.py` (seven steps) and
`undeliverable_contacts.py` (six). **No wave here needed a component**, which is the plan's own test of
whether phases 1 and 2 got the contract right, and it passed: the two result screens are `RBS-006` rendering
the twelve blocks it already had.

**The figures the seeded utility actually produces**, which are NOT the card's illustrative ones: **"2 to
apply · 5 need you · 1 never touched"** over nine county parcels, and **"5 to suppress · 5 would fall back ·
0 nothing left"** over five returned letters, with **Post · 5 · 5 · Email 5** in the by-channel table.

**Nothing is written by either.** Runbook 20's `apply_premise_change` IS bound and
`engine.acts.LIVE_ENABLED_RUNBOOKS` is empty for the whole catalogue; runbook 22's two ports bind no writer at
all (`DEF-RBS-4331`), and each port's own refusal is recorded rather than papered over.

⚠ **THE TRIGGER GAP BELOW IS CONFIRMED FROM THE OTHER SIDE, AND IT IS WORSE THAN THE NOTE SAYS FOR RUNBOOK 20
ALONE.** `batch.landed` and `feedback.landed` are still emitted by nothing — but `gis_city`'s
`reconcile_parcels` operation is **stubbed as well**, so even a tenant with a working GIS connection has no
parcels anywhere to reconcile. Its manifest docstring says *"its RUNNER is wave Q's work on the Runbooks side
of `BR-INT-054`"*, which reads as this wave and **is not**: under `BR-INT-054` as amended 2026-09-06,
integrations connects and Runbooks transforms, and landing the county's rows is integrations' half. **So the
second door — a parcel file a person uploaded, staged through `metering`'s own importer and never loaded — is
not a convenience here; it is the only door that opens at all.** The same is true of runbook 22, where the
only feedback this deployment can produce is a letter a clerk marks returned.

**Seven judgments were taken rather than put to the Product Owner**, each recorded with its reasoning in
`12-governance/02-decision-log.md` under *CR-075 WAVE Q′* — the second door, the stubbed operation, a `window`
parameter for runbook 22, attempts rather than days for a soft bounce, two card fields this product does not
hold, which differences reach the decision table, and where the cap is read.

⚠ **INTEGRATIONS EMITS NEITHER EVENT, AND NOBODY OWNS BUILDING THEM. THIS IS WAVE `O`'s BLOCKING
DEPENDENCY, AND IT IS THE ONE THAT DECIDES WHETHER PHASE 3 EXISTS AT ALL.**
`batch.landed(connection, batch_id, subject_type)` and `feedback.landed(provider, batch_id)` **do not exist**
— verified 2026-09-06, **zero occurrences anywhere under `06-backend/apps/integrations/`, and zero in the
backend at all.** All four of this phase's runbooks trigger off them, and two more (11 and 21, now in `R′`)
do as well.
**Whose half it is: INTEGRATIONS'.** Under `BR-INT-054` as amended 2026-09-06, integrations keeps exactly
three things — **building a connection · holding keys and secrets · the lifecycle of a connection** — and
*"a batch landed on this connection"* is a **lifecycle** fact about the connection, not a judgment about
what is inside the file. The rule's own worked example draws the line in the same place: a run row recording
*a connection authenticated, pulled a file and took three seconds* is integrations'; a row recording *what
was decided about the 899 rows inside that file* is Runbooks'.
**It is CR-069's work, and it is currently scoped to nobody** — no CR-069 wave commissions it, and
`BR-INT-054` commissions nothing at all until CR-069 and Runbooks are taken together.
⚠ **WHAT IT COSTS IF IT SLIPS: phase 3 has no trigger.** The four runbooks still work — they can be run by
hand from `RBS-005` and they will produce the right figures — but *"a file lands and the work starts
itself"*, which is the whole launch sentence of this phase, does not happen. **A cashier presses Run every
morning instead of finding the cash already applied**, which is most of the hours the phase is meant to
return. **It must be raised on CR-069 as a scoped piece of work before phase 2 closes**, or phase 3 starts
with its foundation missing.

---

### Waves R′ · S · T — the rest · phase 5

⚠ **SIX OF THESE RUNBOOKS ARE PARKED BY THE PRODUCT OWNER, 2026-09-07 — DO NOT DESIGN THEM.**
Verbatim: *"Please park those runbook - we will handle them later … I will give you full list what
needs to be done, they are not yet design"*. They are **29, 30, 31, 32, 34 and 35**, and each of
their cards now carries the same instruction inline, because the card is what a lane actually reads.
**A lane landing on one does nothing** — it does not write the card, mint a question or build a
stub; the parking IS the answer until the list arrives. Three of the six would SEND MESSAGES TO
CUSTOMERS if they turned out to be Actions, and who they write to, what they say and when they fire
are facts only the utility holds.

⚠ **SO `CR-075`'s BUILDABLE SCOPE IS CLOSED AT 28 OF 34 RUNBOOKS** — 15 Checks and 13 Actions, all
registered, constructing and walked. The six are not late, not blocked and not owed by engineering.
**What is still owed here is engineering's and is recorded elsewhere:** phase 2 holds wave `M`'s own
`NO-GO` (a clerk cannot read a plan or approve one) and wave `O` has no trigger (integrations emits
no *batch landed* event, and no change request commissions one).

**Same shape as phase 3 — one module per runbook, no frontend code — and the same acceptance test.**

| Wave | Builds | Stories | Goal a clerk can see | Size |
|---|---|---|---|---|
| **R′** | **The Actions that are NOT fed by one of the four named areas.** ⚠ **`R′`, NOT `R`** (§1). In order: **returned payments** (26) · **autopay pre-notification** (17) — *both touch the payment provider and neither is triggered by a landed batch, so they are the obvious next two after phase 3's four; see the note below* — then **leak and high-usage alert** (11) · **read validation on arrival** (21) — *both moved OUT of phase 3 on 2026-09-06 because interval-meter data is none of the four areas the PO named* — then **deposit review** (15) · **payment plans** (25) · **move-outs and final bills** (27) | 036 · 029 · 023 · 033 · 027 · 035 · 037 | *"851 queued · 2 debits need you"* with each failed debit reading the bank's reason in words; **176,640 intervals become 1,840 records**; nine leak alerts a clerk can read word for word; *"48 credited · 13 refunds await approval · $296.40 interest"* | 2 people, 5.5 weeks |
| **S** | **The eight remaining Checks** — 4 · 5 · 6 · 12 · 13 · 16 · 18 · 19. Every one has **no writer, no port and nothing to approve**, so they ship faster than the Actions and may be taken in any order | 019 · 020 · 021 · 024 · 025 · 028 · 030 · 031 | *"Up $82.20 · usage +38% …"* read aloud to a customer; *"14 eligible · 9 removed since the letter"*; *"1,146 bills go up · 121 by more than 15%"* | 2 people, 4 weeks |
| **T** | **Inputs with tenant-resolved domains** — every input declares its domain, domains resolve **per tenant**, an input accepts **one value, several, or *all*** (`BR-RBS-042`), *all* stored as **the word** and resolved at run start, plus the **trust ratchet**, which now bites when a tenant **changes an input** rather than when anybody composes | 039 | An admin opens the collections ladder, sets *services* to **All**, and sees **three** services after Trash is added — not the two that existed at setup; a two-service utility's *services* list offers two; changing an input drops the runbook to dry-run only until one clean dry run is reviewed | 2 people, **~1 week** (was 2) |

⚠ **THIS ROW READ *“Compose — the step library, the filter builder, conformance on save, the trust ratchet”* UNTIL 2026-09-06, AND IT DESCRIBED A TENANT DOING THREE THINGS THE PO HAS NOW RULED A TENANT NEVER DOES.** Stamped rather than deleted, because a lane that read the old row would otherwise be corrected without learning why.

**What was wrong, clause by clause.** *“The step library”* — **the library is real and it STAYS; what was wrong is WHO TOUCHES IT.** It is **OURS**: **173 step instances across 26 runbooks reduce to 137 distinct steps** (`14-step-library.md`, the hand count of 2026-09-06), and it is an **internal engineering asset used from wave `C` onward** — how we build runbooks — **not a phase-5 deliverable and not a screen a tenant opens.** PO verbatim, 2026-09-06: *“I dont think Utility admin will able to configure these using the 150 bricks that we give - you can keep all these bricks and buld ready to use runbooks - when we later change it will be small er changes for us”*. **The reason is adoption, not architecture.** *“The filter builder”* — **gone, for everybody.** Nobody composes filter expressions; inputs have domains and that is the whole mechanism. *“Conformance on save”* stays as `BR-RBS-037` but is **ours to satisfy at build time**, not a tenant's save button.

**So wave `T` mostly DISSOLVES rather than shrinking.** The step library moves EARLIER (wave `C`); what is left here is inputs, domains, multi-select, *all*, and the ratchet. **It is CHEAPER than what was written** — the eleven parameter types, `resolve(params)` and scope pinning (`BR-RBS-009`) already exist, so what is owed is the DOMAIN on each parameter and the multi-select shape B14 already rules (chips, never a checkbox wall).

⚠ **THE SUPERSESSION, STATED RATHER THAN INFERRED.** The PO ruled ***“compose yes, author no”*** on **2026-09-05**; this plan read *compose* as **the TENANT composing**. The ruling of **2026-09-06 narrows it: WE compose; a tenant SETS and CLONES.** Both are the PO's and the later governs. *Author no* is unchanged and is now **self-enforcing by shape**: a tenant who can only choose input values has no path by which to write logic.

⚠ **AND THE SHARED STEP'S PAYOFF IS SMALLER THAN THIS PLAN CLAIMS — MEASURED, NOT ESTIMATED.** **173 step instances across 26 runbooks reduce to 137 distinct steps** (`14-step-library.md`, the hand count of 2026-09-06), **122 of the 137 (89%) are used by exactly one runbook** and fifteen steps carry all of the sharing — the most-used is *“resolve the declared scope into the pinned set”* at seven runbooks, and the reduction is **20.8%** (36 of 173), so the assembly saves **a fifth** of the step-writing rather than a third. **This plan's *“each new runbook is a week of work rather than a project”* rests on a library a runbook can be assembled out of, and a new runbook re-uses about 2 steps and writes about 4.7 of its own** — so phase 5 was owed a re-size on 4.7 new steps per runbook. ⚠ **THAT RE-SIZE HAS SINCE BEEN DONE — §1's phase-5 row now reads *“re-uses about 2 shared steps and writes about 4.7 of its own”* and carries the measurement.** This paragraph read *“this lane does not re-size it here”* until 2026-09-06 and was true when written; it is kept, corrected, because a hazard note that still says a fix is owed is exactly the stale body CLAUDE.md warns a lane will act on. `DEF-RBS-4275` carries the rest of the fan-out. The model is still worth having, for **blast radius**: fifteen shared steps carry all the sharing, every one of them on the money or write path, and a fix to one lands in every runbook using it — **and breaks every one just as fast**, which is why a shared step carries its own tests and a change to one names which runbooks it moves (`BR-RBS-038` holds the tenant-facing half).

⚠ **WHY RETURNED PAYMENTS (26) AND AUTOPAY PRE-NOTIFICATION (17) ARE NOT IN PHASE 3, RECORDED RATHER THAN
DECIDED SILENTLY.** Both touch the **payment provider**, which is one of the four areas the Product Owner
named — so a reader could reasonably expect them in phase 3. **Neither is triggered by a landed batch:**
**17** runs on a schedule (*at 08:00, "851 queued · 2 debits need you"*), and **26** is a reserved definition
whose trigger the source does not state. Phase 3's grouping is *runs that start themselves when a file
lands*; a runbook with a clock in it does not belong to that outcome however important its area. **They are
therefore the head of `R′`**, and the first two things built after phase 3 finishes. **If the Product Owner
wants the payment-provider area finished rather than the landed-batch trigger proved, these two move up and
phase 3 becomes six runbooks** — that is a one-line change to this table and it is theirs to make, not
ours.

**Each of these six waves ends the same way:** its runbooks' cards appear on `RBS-002`, their setups render
on `RBS-004` and their results on `RBS-006`, the conformance suite passes them, a walkthrough reads the
wave's figures off the screen, and a CHANGELOG entry lands with the next free `<change>`. **Wave `Q′`
carries phase 3's entry; wave `T` carries phase 5's.**

⚠ **AND EVERY HOLD IN THESE TWO PHASES CARRIES ITS EXPIRY TEST IN THE SAME COMMIT.** A card held on
`RBS-002` until its module lands asserts its destination **by address and by screen id**, so the day the
module lands the suite goes **red** and names the card. Sixteen holds without those tests is `DEF-CWP-3925`
at sixteen times the scale — the portal shipped a front page with **two working doors out of eight**, over
screens that were routed, tested and live, and 42 test files with 391 cases were all green.

⚠ **THE WORK LIST IS NOT BUILT YET WHEN THESE ACTIONS FIRST RUN, AND THAT IS A CONSEQUENCE OF THE RE-CUT
RATHER THAN AN OVERSIGHT.** `RBS-007` and the `work_items` upsert are wave `H`, which is **phase 4** — after
the acting half in phase 2 and after the integration runbooks in phase 3. Until it lands, **an exception
raised by an Action is readable only on its own run's result screen (`RBS-006`), not gathered with every
other open item in one list a clerk opens each morning.** The rows are still written — the table is created
by phase 1's migration and the engine's upsert is `H1` — so nothing is lost, only ungathered. ⚠ **The
re-cut also improves one thing here, and it is worth saying: `EP-RBS-03`'s test data assumed Actions did not
exist yet and proved the exception kind on a row seeded by hand. Under this order the ladder is already
live, so wave `H` can prove it on a REAL exception.**

---

## 4 · Why phase 2 is split into a dry half and a live half, and what the 2026-09-06 re-cut costs

⚠ **THIS SECTION WAS ABOUT PHASE 4 UNTIL 2026-09-06.** The split is unchanged; the phase it sits in moved
from fourth to second (§1). **Everything below matters MORE at second than it did at fourth**, because the
old order had three phases of Checks in front of it and this one has one.

**Everything dangerous about this feature lives in the acting half:** the ports, the cap, the stop, the
idempotency key, the audit actor. **Shipping all of it with sending switched OFF means the risky code runs
against real accounts, in production, for a full cycle, while being unable to do anything.** Then the live half
is a **one-line change to a runbook's kind** on machinery that has already been watched.

**Merging the two saves a week and removes the only cheap opportunity to be wrong safely.**

⚠ **THE FAILURE THAT HURTS IS NOT A RUNBOOK DOING NOTHING — SOMEONE NOTICES THAT.** It is **a misconfigured
runbook queueing three thousand wrong disconnection notices in four minutes, and a notice cannot be unsent.**
The cap, the dry run, the batch approval and the stop button are **first-release requirements, not hardening
for later.** Everything else in this module is negotiable; those four are not.

**Three things make the split real rather than ceremonial, and a lane that drops any of them has merged the
halves without saying so:**

1. **`BR-RBS-003` — dry and live are the SAME code path**, differing only in whether the writer is bound. A dry
   half on its own path proves nothing about the live one, which is why `TC-RBS-2` is first shown red on a
   deliberately divergent second implementation.
2. **Wave M is a wave**, with a version bump and a demonstration. It produces no code and it is not optional:
   its output is a cycle of real plans a person has read and a database diff nobody can argue with.
3. **Wave M4 is a go/no-go, written down.** If the dry cycle's plans were wrong, **the live half does not
   start.** A split whose second half is automatic is not a split.

### 4.1 · What the new order costs, said rather than sold

**The old order put every Check first and reached an Action only after the engine had been proved on work
that could not reach a customer.** That was a real safety property and the re-cut spends it. **What is bought
with it is the Product Owner's own priority — the integration runbooks, which are all Actions and cannot run
before the acting half exists.** Both halves of that trade are true and the plan states both.

**Three costs, each named so nobody has to discover it:**

1. **The safety argument now rests entirely on wave `M`.** In the old order, `L` arrived after `F`–`K` had
   exercised the engine on six Checks over real data. Now `L` arrives after `E`. **`M` stays exactly where it
   is, between `L` and `N`, at its full length — shortening it, or folding it into `L`, is the one change
   that would make this reorder unsafe.**
2. **The coverage grid lands in phase 4 instead of phase 2.** It is the **go-live artefact and the sales
   artefact at once**: a utility that has seen 25 green cells on its own data before go-live behaves
   differently from one that has not, and no incumbent can show a prospect their own data producing correct
   bills before they sign. **Under this order the first customer sees it three phases later than it would
   have.** That is the price of the ruling and it is the one a salesperson will feel first.
3. **The work list arrives after the Actions that fill it** (wave `H`, phase 4). Until it lands an exception
   is readable on its own run's result screen and nowhere else — see the note at the end of §3.

---

## 5 · What this plan depends on that is not in this module

⚠ **THE 2026-09-06 RE-CUT MADE TWO OF THESE URGENT AND ONE OF THEM UNOWNED.** Both were already on this
list; what changed is when they are needed. **The audit actor blocked the old phase 4 and now blocks phase
2. The two events blocked the old phase 5 and now block phase 3.** Each row below states what it costs if it
slips, because a dependency without a cost attached is a note nobody acts on.

| Dependency | Gates | State at 2026-09-06, and what it costs if it slips |
|---|---|---|
| **1 · THE AUDIT ACTOR — an automated action had no name.** `BR-AUD-003`: `actor_user_id` NULL meant *"system job"*, so **every automation in the product was indistinguishable from every other**, and a runbook would have had to borrow a staff login — **a person would appear to have personally sent 812 letters at 07:00 on a Monday** | **A NAMED PREREQUISITE OF WAVE `L`**, before any writer is bound — **not a note.** ⚠ **This blocked the old phase 4 and then PHASE 2** | ✅ **CLOSED 2026-09-06 — and this row is left standing rather than deleted, because the next reader needs to know it was a dependency and how it went.** `US-AUD-010` / `BR-AUD-019` landed it in the AUDIT module (migration `audit/0007`), and `TC-RBS-12` was shown **red first at the pinned tip `a10eae00`** on the platform as it stood, then green. ⚠ **THIS WAS NEVER A QUESTION FOR THE PRODUCT OWNER AND WAS PUT TO THEM ONCE AS THOUGH IT WERE** — `BR-RBS-015` had already ruled it; the missing thing was a BUILD nobody had scheduled (CLAUDE.md hard-won law 13). ⚠ **WHAT IS STILL OWED IS THIS MODULE'S, NOT AUDIT'S:** `L2` binds a writer behind the ports and PASSES the actor. The platform can express it; Runbooks does not yet use it, so **phase 2 is unblocked on this axis and on this axis only** |
| **2 · INTEGRATIONS EMITS NEITHER EVENT.** `batch.landed(connection, batch_id, subject_type)` and `feedback.landed(provider, batch_id)` **do not exist — verified 2026-09-06, ZERO occurrences under `06-backend/apps/integrations/` and zero in the backend at all** | **WAVE `O`, and through it every runbook in phase 3.** Manual and schedule wait on nothing | **Not built, and SCOPED TO NOBODY.** Under `BR-INT-054` as amended 2026-09-06 integrations keeps *building a connection · holding keys and secrets · the lifecycle of a connection* — and *"a batch landed on this connection"* is a **lifecycle** fact, so **it is integrations' half to build and it is CR-069's work.** No CR-069 wave commissions it today. ⚠ **COST IF IT SLIPS: phase 3 has no trigger.** The four runbooks still work by hand from `RBS-005` and still produce the right figures, but *"a file lands and the work starts itself"* — the phase's whole launch sentence — does not happen, and a cashier presses Run every morning instead of finding the cash already applied. **Raise it on CR-069 as scoped work before phase 2 closes** |
| **3 · ~~NOTHING BUILDS THE ACCOUNTING FILE'S CONTENTS~~ — CLOSED 2026-09-06, AND THE ROW IS KEPT BECAUSE THE REASONING IS WORTH MORE THAN THE CONCLUSION.** This row said an accounting runbook *"needs a fourteenth port or an engine act, which is a reviewed interface change and a rule change, not a lane's decision"*. **The Product Owner split it and the split dissolves it** (decision log 2026-09-06, *"THE ACCOUNTING EXPORT IS TWO THINGS"*): pushing a file to an accounting system does need the fourteenth port and is still an unraised change request; **producing a file a clerk DOWNLOADS and uploads needs nothing new**, because a download is not a write to a business record and `downloads` is one of the twelve blocks, built in wave `C1b`. The PO's own sentence: *"utility clark can down the file and upload it in Quickbook if integration is not yet enabled, isnt it?"* The file's six columns were ruled the same day — **date · account code · description · debit · credit · reference** | **BUILT — [`RB-136`](11-catalogue/RB-136-accounting-export.md), `US-RBS-042`, a Check in the Finance category whose input is the accounting month** | ⚠ **WHAT IS STILL OWED IS AN ADDRESS, NOT A PORT (`DEF-RBS-4312`).** The two result files carry the nine RECORD columns — no date, no account code — so a general journal cannot be expressed in them, and `results/{done|not-done}.csv`'s alternation makes a third file name a deliberate 404. One endpoint row, one `re_path` arm and one streaming view. **The general lesson: the capability was reported absent because this lane looked for it in the shape it expected — an outbound PORT — and never for the shape it already had, a DOWNLOAD** |
| **4 · A delivery provider connected** — the notification queue fills and nothing leaves the building | **Wave N**, the live half of phase 2 | Until then the word is **Queued** and no screen may say *Sent*. **COST IF IT SLIPS: phase 2's live half changes nothing a customer can see**, and the ~33 hours a month it returns are not returned |
| **5 · Selectors other modules do not expose yet** — a meter's last good day, an account's ladder tier, a premise's usage over 90 days | Waves `P`, `Q′`, `R′`, `S` and `I` | **Inventoried in task `A5`, before the first Check is written.** The owning module adds each; this module never reaches past a seam. ⚠ **The re-cut moved `P` and `Q′` three phases earlier, so the selectors those four runbooks need are wanted SOONER than `A5` assumed** — `A5` is still phase 1, which is why it still works |
| **6 · `OQ-INT-1727`** — the value mappings and per-item run results, ≈3 people-weeks already shipped on the integrations side, now on the Runbooks side of the line | Nothing in this plan | **OPEN and the PO's** — it is a ruling colliding with signed, shipped work. **They keep running where they are and move as a unit; nothing is rebuilt** |

⚠ **`CR-075` IS THIS MODULE'S CHANGE REQUEST AND ITS FILE NOW EXISTS** —
[`../../../12-governance/change-requests/CR-075-runbooks-module.md`](../../../12-governance/change-requests/CR-075-runbooks-module.md).
An earlier draft of this section said the file was unwritten and named `CR-076`; that was true when it was
written and is not true now.

---

## 6 · The open questions — six, none blocking anything, and three of them now arrive in PHASE 2

⚠ **THIS SECTION'S HEADING READ *"all in phases 4 and 5"* UNTIL 2026-09-06 AND THAT IS NO LONGER TRUE.** The
Product Owner's earlier instruction — *"phase them in to 4 or 5 phases and ask questions in phase 4 and 5"*
(`CR-075` §0) — is **overtaken in effect by the 2026-09-06 ruling**, and the honest statement is that
**nobody moved the questions: the WORK moved earlier and the questions came with it.** `OQ-RBS-1731`,
`1732` and `1733` all hang on wave `L`, and wave `L` is now phase 2. **`OQ-RBS-1736` moves too**, from phase
5 to phase 4, because its deliberate absence is built in wave `K`.

**Nothing else about them changed, and the part that matters is unchanged: NOT ONE OF THEM BLOCKS ANYTHING.**
Every one has a stated *built meanwhile* that an answer can only ever **widen**, so a question arriving three
phases sooner costs a conversation and never a stub. **That is why the re-cut did not need the Product Owner
to answer anything before it could be applied.**

⚠ **The block `OQ-RBS-1731`–`1736` is reserved in [`../../../12-governance/14-id-reservations.md`](../../../12-governance/14-id-reservations.md)**, taken **by hand** from the register maximum (`OQ-MET-1730`) plus one, because the tooling does not read the module segment yet — `file_defect.py`'s `^"?DEF-(\d+)"?,`, `gates/common.py`'s `OQ-\d{3,6}` and `g08`/`g17`/`g38`/`g50` all expect digits straight after the family. The search pattern for these two families is **`(?:OQ|DEF)-(?:[A-Z]{3}-)?\d{3,5}(?!\d)`**, and the lookahead is load-bearing (`DEF-2804`: `OQ-\d{3}` returned `OQ-119` for `OQ-1190` and put a stub against the wrong question for two days).

| OQ | Question | Phase | Blocks | **Built meanwhile — a deliberate absence, not a guess** |
|---|---|---|---|---|
| **`OQ-RBS-1731`** | **The default cap for a first run** — a number the Product Owner is comfortable seeing acted on unattended | **2 · dry** (`L4`) — *was phase 4* | nothing | **`cap` is a REQUIRED field with NO default. An Action cannot be enabled until an admin sets one.** Safer than any number a lane could pick, and it pre-empts no answer |
| **`OQ-RBS-1732`** | **Which actions need the second approval, and above what amount** | **2 · dry** (`L3`) — *was phase 4* | nothing | **EVERY money-bearing action carries it, with no threshold.** A threshold can only widen what is permitted, so shipping without one cannot be wrong in the dangerous direction |
| **`OQ-RBS-1733`** | **Does an admin approve every run, or may a tenant set a runbook to run unattended once trusted?** Runbook 11 is the first candidate | **2 · dry** (`L3`) — *was phase 4* — and `US-RBS-023`, which moved with runbook 11 into wave `R′` in **phase 5** | nothing | **Every run is approved by a person, and the *"Unattended after"* parameter is drawn READ-ONLY.** No option is pre-empted |
| **`OQ-RBS-1734`** | **May a Check ever write a note to an account automatically?** | **5** (wave `S`, `US-RBS-019` and `US-RBS-025`) — unchanged | nothing | **It does not.** The clerk adds the explanation with **one button**, performed by the customers module. ⚠ **A *yes* would be a FOURTEENTH port and a narrowing of `BR-RBS-002`** — which is precisely why it is the PO's and not a lane's |
| **`OQ-RBS-1735`** | ~~Compose scope — which fields and which steps may a tenant use?~~ **CLOSED 2026-09-06 by PO ruling: THE QUESTION HAD THE WRONG SHAPE.** A tenant uses **no** steps and filters **no** fields. A runbook is one fixed process with declared **inputs**; a tenant picks **one value, several, or *all*** from a **tenant-resolved domain**, and **we** arrange the steps from a library only we see (`BR-RBS-042`). | — | nothing | **What is built instead:** every parameter declares a domain, the domain is read per tenant, *all* is stored as **the word** and resolved at run start (`BR-RBS-009`). ⚠ **The old answer in this cell — *“the step library is the steps phase 5 has shipped”* — described a tenant reading that library and is WRONG**; the library is ours and moves to wave `C` |
| **`OQ-RBS-1736`** | **May closing the accounting period ever be automated once every tie-out is clear, or does it stay a named person's act?** | **4** (wave `K`) — *was phase 5*; wave `K` moved and the question moved with it | nothing | **It stays a named person's act** (`BR-RBS-030`), built in wave K. A later *yes* is an addition; a *no* is the status quo |

⚠ **AND TWO QUESTIONS THE SOURCE LEFT OPEN ON PHASE 1 ARE **DECIDED**, NOT MINTED.** Under law 13 — neither
collides with a signed rule, neither moves a ❄️ FROZEN B4/B5 figure, neither is a fact only the Product Owner
holds — **a judgment recorded with its reasoning is the deliverable and a question is the failure to make
one.** Both are written out in [`01-overview.md`](01-overview.md) §8, **visible to overrule**:

* ***Can we bill?* produces one verdict per SERVICE, rolled up to a tenant verdict** (§8.1). A two-service
  utility fixing water must see sewer still red, or the screen cannot show progress at all.
* **The minimum object set is exactly runbook 1's TEN STEPS** (§8.2). A second enumeration of the same fact
  would disagree within a week, and the steps are already ordered by the chain a bill needs.

---

## 7 · Coverage — every story placed exactly once

| Phase | Wave | Stories | | Phase | Wave | Stories |
|---|---|---|---|---|---|---|
| **1** | A | 041 | | **4** | F | 004 |
| **1** | B | 002 · 015 | | **4** | G | 005 |
| **1** | C | 016 · 001 | | **4** | H | 006 |
| **1** | D | 003 · 018 | | **4** | I | 007 |
| **1** | E | 038 · 040 | | **4** | J | 008 |
| **2 · dry** | L | 010 · 011 · 012 · 014 | | **4** | K | 009 |
| **2 · dry** | M | — (evidence) | | **5** | R′ | 036 · 029 · 023 · 033 · 027 · 035 · 037 |
| **2 · live** | N | 013 | | **5** | S | 019 · 020 · 021 · 024 · 025 · 028 · 030 · 031 |
| **3** | O | 017 | | **5** | T | 039 |
| **3** | P | 022 · 026 | | | | |
| **3** | Q′ | 032 · 034 | | **later** | U | **043** · **044** |
| | | | | | **Total** | **43 · placed once · none blocked** |

⚠ **THE RE-CUT MOVED FIVE STORIES BETWEEN WAVES AND NOT ONE BETWEEN EPICS.** `026` (bank reconciliation)
moved from `Q` into `P`; `032` and `034` (GIS reconciliation, undeliverable contacts) moved from `R` into
`Q′`; `023` and `033` (leak alert, read validation) moved from `P` into `R′`; and `029`, `027`, `036`, `035`,
`037` are gathered in `R′`. **Every one of the twelve is still placed exactly once**, and all twelve are
still `EP-RBS-05`'s.

⚠ **WAVE `U` IS THE FIRST OF THE *NAMED ONLY* CARDS AND IT WAS NOT IN THIS PLAN.** The plan covers
runbooks 1–27 and 36; runbooks 28–35 arrived with **one sentence each and no card**, so no wave owned
them. `US-RBS-043` (runbook 28, Assets) and `US-RBS-044` (runbook 33, Billing) were built on
2026-09-07 and are placed here rather than left off the table — a story with code and no row is the
shape `G23`'s own header calls *"every lane was honest; nothing added the honest notes up"*.
**Neither is blocked**: `OQ-RBS-1759` and `OQ-RBS-1760` are open beside runbook 33 and each is a
stated absence in the shipped code rather than a stub awaiting an answer. **Six named-only cards
remain** — 29, 30, 31, 32, 34 and 35 — and they are **PARKED by the Product Owner (2026-09-07), not
awaiting a lane.** See the notice above this section's table.

**Twenty-one waves. Roughly 35 people-weeks** at this plan's own sizes, **unchanged by the re-cut — the ruling
moves work, it does not add or remove any.** The three buckets are the same numbers as before, read against
the new phases:

* **Waves `A`–`K` — 15 people-weeks.** These are now **phase 1** (`A`–`E`) and **phase 4** (`F`–`K`).
* **Waves `L` `M` `N` — 5 people-weeks.** These are now **phase 2**, plus one cycle of elapsed soak in wave
  `M` that costs almost no work.
* **Waves `O`–`T` — 14 people-weeks.** These are now **phase 3** (`O` `P` `Q′`) and **phase 5** (`R′` `S`
  `T`). The internal re-cut holds the total: `P` + `Q` + `R` was 2.5 + 3 + 3 = **8.5 weeks** and
  `P` + `Q′` + `R′` is 1.5 + 1.5 + 5.5 = **8.5 weeks**.

⚠ **These are this plan's sizes and nobody else's**, and wave M's calendar length is a cycle whatever its
effort — a figure that answers *"how long"* and a figure that answers *"how much work"* are different
measurements, and quoting one as the other understated the integrations backlog about fourfold.

---

## 8 · Hazards a lane will meet, written down so they cost a paragraph rather than a cycle

* **`route-b-migrated.txt` before any Tailwind utility.** A class no stylesheet declares renders as **nothing
  at all**, and `tsc`, eslint and every `toContain("flex")` assertion pass on it because the class **is** in
  the DOM (B14 rule 21, `DEF-974`). Task `A2`, first frontend commit.
* **The SQLite suite cannot see the savepoint.** `config/settings/test.py` hardcodes in-memory SQLite, which
  has no aborted-transaction state. **The naive `try/except IntegrityError: continue` passes the entire suite
  green on every machine and loses the run in production** (law 14). Tasks `B5` and `L11` run on PostgreSQL or
  prove nothing.
* **`--reuse-db` was silently ignored until 2026-09-04**, costing 133 seconds per `pytest` invocation. It works
  now; run these suites with `JOBS_EAGER=false --reuse-db`. ⚠ **A flag that is silently ignored is worse than
  one that errors, and only the wall clock finds it.**
* **Prove every new gate RED through `run_gates.py`**, never through `python3 <gate>.py` — `G85` and `G87` were
  both announced green while the suite reported `gate crashed: AttributeError` (`DEF-GOV-3733`).
* **Read the failures you did not cause**, and when you call one pre-existing, **date it**:
  `git log -S "<the failing symbol>" -- <file>`. Two lanes reported the same red in good faith and almost the
  same words on 2026-09-06, and the second was the lane that had caused it (`DEF-CWP-4187`). ⚠ **A confident
  *not mine* tells every later reader not to look.**
* **A check that reports zero over a scope it silently excludes is indistinguishable from an empty one.** `G32`
  reported **0 unresolved** truthfully, of everything it could see, over **21 live refusals that reach a clerk
  as silence**. This module adds six refusal keys — `runbooks.refusal.plan_changed` · `over_cap` ·
  `check_cannot_write` · `already_running` · `guard_required` · `nothing_to_decide` — **in all eleven catalogues**, and any
  check over them prints **what it skipped beside what it checked**.
* **The six shared components the blocks need do not exist** — `VerdictBand`, `Chain`,
  `ContributionBars`, `OutcomeCard`, `SettingsOwnedField`, `PercentCell`, plus the `Records` block's
  sparkline cell and its grid mode (verified absent 2026-09-06). **They are phase-1 work** — task `C1a` — and
  **wave `G`'s coverage grid IS the grid mode**, so deferring them makes `EP-RBS-02` unbuildable rather than
  merely late. ⚠ **The 2026-09-06 re-cut moved wave `G` from phase 2 to phase 4, which makes this hazard
  EASIER to get wrong, not harder:** the gap between building the component and needing it is now three
  phases instead of one, so the temptation to defer it is larger and the day it bites is further away.
* **There is no percent formatter in the front end at all**, and **no percentage in any of the 75 build sheets
  is drawn at two decimals** — while hard rule 2 says percentages are stored to **6** and **displayed at 2**.
  Task `C1c` adds the shared formatter and stamps the divergence; **a lane copying a sheet literally on this
  point ships the wrong number of decimals on a money-adjacent figure.**
* **A refusal sentence is five or six words** (B14 rule 33), a screen has **a description budget of one
  sentence per section** (rule 32), **no database id is ever the visible value of a field** (rule 31), and a
  catalogue is **written in its own language, not translated from English** (rule 35).
* **An address is stored on `premises` and nowhere else** (hard rule 8). ⚠ **`kind='service'` is RETIRED and a
  write asking for it is refused BY NAME**; `G85` fails a fourth home. Before retiring anything, **grep for its
  CONSUMERS** — closing that door cost a screen line that would have returned null on every account forever
  with `tsc` and every test green (`DEF-CUS-3653`).
* **`NFR-3` and `NFR-5`.** Every list this module serves pages on the server, and **no table, index or code
  path enforces a maximum account count per tenant.** ⚠ The four existing breaches each name the abandoned
  3,000-connection ceiling as their excuse (`DEF-PAY-4221`); this module inherits the paging and copies none of
  the excuse.
