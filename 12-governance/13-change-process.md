# The change process — when the product changes after it was agreed

**PO-ruled 2026-08-16.** This is the companion to the build process
(`04-docs/02-decisions/12-engineering-plan.md` → **Addendum r11**). That one says
how a story becomes code. **This one says what happens when the agreement itself
changes** — and it fires on a different trigger, which is why it is a separate
file rather than another addendum: r11 is read when a lane starts a story, this
is read the moment a change arrives.

**Every step below exists because of something that actually went wrong.** Where
that is the case the evidence is named, so nobody later trims a step they think
is ceremony.

---

## 0 · CAPTURE — number it, quote it, date it

**Allocate `CR-###` the moment the change arrives, before any analysis**, and
write the requester's words **verbatim**, with the date, into **its own file at
`12-governance/change-requests/CR-###-<short-slug>.md`** — plus a row in
`12-governance/11-change-requests.md`, which is now the **index**.

⚠ **AMENDED 2026-09-03 BY PO RULING.** This step said *"write the requester's
words verbatim into `12-governance/11-change-requests.md`"* until that date, and
following it literally is how that file reached **2.5 MB and 30,491 lines across
80 change requests** — a size at which GitHub will not render it, every lane
contends for one file, and the register-deletion guard fired on it three times in
a single day. The PO's words: *"one file per CR from here... with
`11-change-requests.md` kept as the index — the CR number, its title, its status,
and a link."* **`CR-001`–`CR-067` did not move and every citation to them still
resolves**; see `12-governance/change-requests/README.md` for the convention and
what was deliberately left alone. **Nothing else in this process changed — only
where the text lands.**

The number exists so every downstream artefact — commit, test, amended rule,
document, version — points back to one thing. The verbatim quote exists because
**a paraphrase of a ruling is how the next agent rebuilds the wrong thing**; that
is hard-won law 10 and it has cost this project a full day.

**Re-read the register immediately before allocating a number.** Lanes collided
on IDs twice on 2026-08-16 alone — once on questions, once on defects, and one
defect row was destroyed and had to be recovered from git history.

### ⚠ AMENDED 2026-09-10 BY PO RULING — A CR NUMBER CARRIES ITS BRANCH, AND EVERY BRANCH OWNS A BLOCK

**PO verbatim:** *"we are going to now work on 2 or 3 branches symeteniouly - so we
dont want two branches write same CR number and when we merge we land into
problem"*, then *"Can you add - branch exten or cone code to this - CR-090–094 -
CR-90-<BRCXX> - this will ensure code never collide?"*, and on being shown the
costs, *"No - I said I want Suffix"* and *"Ensure you assing branch Suffix to CR
number"*.

**THE ID FORM, FROM `CR-090` ONWARD: `CR-<nnn>-<BRCnn>`** — the running number,
then the branch code that raised it. `CR-090-BRC01`. The file is
`12-governance/change-requests/CR-090-BRC01-<short-slug>.md`, so the whole id is
recoverable from a directory listing.

⚠ **`CR-001`–`CR-089` ARE NOT RENUMBERED AND NOT RESPELLED.** They keep their bare
form, every citation of them still resolves, and every tool reads both. Respelling
eighty-nine ids across every register, commit message and rule citation is the mass
shared-file rewrite hard-won law 11 exists to prevent — the same reasoning that
kept `OQ-291` from becoming `OQ-00291` under the five-digit ruling.

**AND THE SUFFIX IS PROVENANCE, NOT THE THING THAT MAKES IT UNIQUE.** Two branches
can both reach for ninety and produce `CR-090-BRC01` and `CR-090-BRC02` — two
different changes, both called ninety, colliding in no file. The string would be
unique and the **number** would not, and a number is what a person says out loud,
writes in a commit subject and cites from a business rule. So the suffix rides on
top of a **disjoint block per branch**, and the block is what carries the
guarantee:

| Branch code | Block | Where it is recorded |
|---|---|---|
| `BRC01` | `CR-090`–`CR-094` | `12-governance/14-id-reservations.md`, one row per branch, opened before the branch starts and marked RELEASED at merge |
| `BRC02` | `CR-095`–`CR-099` | same |
| `BRC03` | `CR-100`–`CR-104` | same — **unclaimed blocks are claimed by writing the branch name into the row**, never by taking the numbers quietly |

**THREE LAYERS, AND ONLY THE LAST ONE ENSURES ANYTHING:**

1. **Before a branch starts** — its block and its branch code go in the
   reservations file. Two branches cannot reach for the same number.
2. **At push time** — `10-scripts/allocate.py cr --verify 090` re-asks **every
   fetched `origin` ref**, not this checkout, because a sibling working in its own
   worktree has its rows in none of the places a listing can see until it pushes.
   Caught here, renumbering costs two files. ⚠ **It cannot RESERVE and does not
   claim to** — nothing writes to the remote, so two branches calling it in the
   same second still get the same answer. It removes the stale read.
3. **At merge** — `G17` fails on a duplicate CR, and it checks the **running
   number** as well as the whole id, so `CR-090-BRC01` and `CR-090-BRC02` go RED
   rather than merging quietly as two ninetys. This is the layer that makes the
   rule hold when somebody forgets the other two.

**Why the gate is not optional here: git will not catch this one.** One file per CR
means two branches writing ninety touch two *different* files, and the index row is
an append, so both sides merge clean and nothing goes red. The collision is
invisible to the merge and visible only to a reader.

---

## 1 · CLASSIFY — the kinds, and the rule is deliberately harsh on us

| Kind | Register | Example |
|---|---|---|
| **New requirement** | change | *"Add the year to the deposit code"* |
| **We built the wrong thing** | **defect** | The picker offered rate schedules; the endpoint wanted plans |
| **Reversal of a signed decision** | change | *"Reference data" becomes "Configure"* |
| **Scope removal** | change | *"Five templates, no designer"* — deleted six screens |
| **Bug** | defect | A finance tile rendering the literal text `null USD` |
| **UI / copy only** | change | Still real work: eleven catalogues and a re-verified screen |
| **Process change** | decision log + the process file | This document |
| ⚠ **SCREEN-SHAPED** — *added 2026-09-10* | **change OR defect, AND it routes differently from here** | Anything that alters what a person SEES: a row, a column, a tile, a tab, a label, an order |

### ⚠ THE SEVENTH KIND IS A ROUTING FLAG, NOT A SIXTH CATEGORY (added 2026-09-10)

**`screen-shaped` sits ACROSS the kinds above rather than beside them.** A screen-shaped
item is still a change or still a defect — the test in the beta clause below decides
which. What the flag adds is **three obligations the other kinds do not carry**:

1. **It must name a DRAWING FILE** — step 3 refuses to proceed without one.
2. **It must name a SCREEN OWNER** — one lane owns the screen for the length of the
   work, per step 6.
3. **It closes with a CONFORMANCE DIFF** — the drawn labels, in the drawn order, on
   the rendered page, per step 8.

**Why it earns its own flag, and the figure is NOT the one first quoted for it.** This
flag was proposed on the strength of *"32% of defects are a screen not matching its
design"*. **That number was wrong** — it came from bucketing a free-text column by
keyword, and two readers doing it independently disagreed by twenty points. Counted
against the register's twelve-value vocabulary, `design-divergence` is **10.8%** of the
1,143 defects filed in the nine days to 2026-09-09.

**The flag still earns its place, and the honest argument is a better one than the
wrong figure was: only 23.9% of those defects touch the front end AT ALL.** So a screen
not matching its design is **124 of the 273 front-end defects — nearly half of
everything that goes wrong on a screen.** A share of the whole register hides that; a
share of the front end does not. **The classifier could not see any of it**, so the
work that goes wrong most often *on a screen* was being dispatched exactly like the
work that never touches one.

**WHEN IT IS AMBIGUOUS, IT IS A DEFECT.** That is the harder classification for
whoever is writing it down, and that is exactly why it is the rule.

### ⚠ AND FROM THE BETA, THAT IS NOT AN EDGE CASE — IT IS THE DEFAULT (PO ruling 2026-09-10)

**PO verbatim:** *"youa re write cCR is change in product, defect is product does
not do what is expected"*.

**The first round of code is written and the product is with beta users**, so the
incoming work is no longer stories being built for the first time — it is people
using the thing and telling us what is wrong with the UI, the functionality and the
behaviour. **That changes the DEFAULT this table is read with.**

| What the beta user is telling you | What it is |
|---|---|
| The product does not do what was agreed | **DEFECT** — this is the majority of beta traffic |
| The screen does not look like the screen we agreed | **DEFECT** |
| It works as agreed, and now that they have used it they want it different | **CHANGE** |
| They want something that was never agreed at all | **CHANGE** |

**Route a beta finding to the change register only when the product does what was
agreed.** Anything else is a defect, and the two are not interchangeable
bookkeeping: **filing our own miss as a "change" converts our mistake into the
customer's new requirement**, and it does it silently. Do that often enough and the
change register stops describing the product and starts describing our errors —
at which point nobody can read either register for what it is for.

**Both registers stay busy in the beta and that is correct.** The test is one
sentence, and it is the PO's: **did the product do what was expected?** If no, it is
a defect however politely it was reported. If yes, and they want it different, it is
a change however small. **A
misunderstanding filed as a "change" quietly converts our error into the
customer's new requirement** — and on 2026-08-16 four separate findings were of
that shape. A change register full of things that were really our mistakes tells
you nothing about the product and everything that is wrong about the reporting.

---

## 2 · WHAT IS BEING REVERSED — quoted, never summarised

Name the signed statement this contradicts, in its own words. Three outcomes:

* **Nothing signed** → proceed.
* **A business rule** → amend it in the module's `02-business-rules.md`, stamped
  CONFIRMED or SUPERSEDED with its date, **and re-stamp every document that
  cites it in the same commit.** A rule amended in one place and cited in four
  is a rule that will be read wrongly three times.
* **A ❄️ FROZEN money figure (B4/B5)** → **STOP.** That is a finance re-sign via
  HUMAN-GUIDE §6, never an inline edit. The figure is not ours to move.

**THE SUPERSEDES CHAIN IS PART OF THE ROW.** CR-014 may reverse CR-002; without
the link the register becomes a pile rather than a history, and the third
reversal of the same decision looks like a first.

---

## 3 · IMPACT — eleven surfaces, and the last three are the ones that get missed

| Surface | Ask |
|---|---|
| User stories | Which — and does any become **obsolete**? |
| Business rules | Amend, supersede, or unaffected |
| Build steps / waves | Does the order change? |
| Documents | **Every** citing document, same commit |
| Code | Which modules, and which are 🔒 |
| Test cases | The cases the story declares |
| E2E journeys | Which assert the OLD behaviour and will now fail correctly |
| Seed data | Is the demo tenant now describing something untrue? |
| **Open questions** | **Both ways: what does this ANSWER, and what does it RE-OPEN?** |
| **The demo fixture** | Does a person driving the product still see a coherent utility? |
| **THE DRAWING** | **Which screens does this change, and WHERE IS EACH ONE DRAWN?** Name the file, not a page. |

### ⚠ THE DRAWING SURFACE, ADDED 2026-09-09 — BECAUSE A SCREEN SHIPPED NOT LOOKING LIKE ITS DESIGN AND EVERY CHECK PASSED

The Product Owner opened the property Overview and it did not match the screen
we had agreed with them. **Three rows were missing outright** — *Read route*,
*Billing cycle*, *Common areas* — **four labels were different**, one column was
drawn as two, services rendered as letter badges instead of words, and the four
tiles were the wrong four. `tsc` clean, every suite green, every gate PASS.

**The cause was this table.** Read the ten surfaces above as they stood: user
stories, business rules, waves, documents, code, test cases, journeys, seed
data, open questions, the fixture. **Not one of them is the screen's design.**
So `CR-089`'s task rows were written the only way this process asks for —
*what a person can do and see* — and the lanes were dispatched with those
sentences. The layout, the labels, the row order and the provenance clauses
lived only in a published page no lane could open. **Three of the agreed labels
exist nowhere in the product to this day**, because nobody was ever asked for
them.

**Nobody skipped a step. There was no step.** This process was built for rules,
money and behaviour — the things that can be argued about in words — and it was
blind to layout.

**So the ask is deliberately worded to be unanswerable by hand-waving: NAME THE
FILE.** A URL is not an answer, and neither is *"the design doc"*. A drawing a
lane cannot open is a drawing that will not be built. If the change touches a
screen and no drawn specification exists in the tree, **creating one is the
first task of the CR, not an afterthought** — see
`04-docs/05-modules/04-metering/09-screen-conformance.md` for the shape: header,
actions in order, tabs, tiles with their detail lines, ordered fact rows with
their exact labels, table columns, footer, and the rules that screen must obey.

### ⚠ AND FROM 2026-09-10 THIS SURFACE CAN REFUSE, RATHER THAN MERELY ASK

**A screen-shaped item that names no drawing file DOES NOT PROCEED PAST THIS STEP.**
Not a warning, not a note in the impact table — a stop. The first task of the work
becomes **creating the drawing** and putting it to the PO in plain English for a yes,
exactly as the UI build skill's §1 sets out.

**Because the ask as originally written was answerable by hand-waving and was
therefore answered that way.** *"The design doc"* and a URL both satisfy a question
that only ASKS. They do not satisfy one that REFUSES. And the failure this closes is
not hypothetical: the property Overview shipped with three rows missing, four labels
different and one column drawn as two, with every suite green, because the layout
lived in a page no lane could open.

**And it runs the other way too:** when a drawing changes in review, the file
changes in the same commit. A screen agreed with the PO and not extracted into
the tree is a screen that will drift back.

**The open-questions surface is here because of a specific failure.** On
2026-08-16 two questions were put back to the PO that the repo had already
answered — a ruling had closed them **by consequence**, carrying neither
question's number, so a staleness sweep keyed on `OQ-### … CLOSED` could not see
it. **A change must be checked against the open register in both directions**,
and that check is a human reading, not a grep.

---

## 4 · WHAT IS ALREADY BUILT AND IS NOW WRONG

The expensive question. Three places to look, each with an example from the day
this process was written:

* **Code already shipped on the old rule.** The deposit-code ruling of 12 Aug
  reached every *document* that day and the *code* not at all — for three days
  the code still refused the anniversary batch citing the question as OPEN.
* **Data already written.** Provisioning-time changes reach a tenant when it is
  created and never afterwards — the same law that makes editing `.env.example`
  useless to a host that already has one. `silver-creek-water` still has no bill
  template. **A change to provisioning without a repair path leaves every
  existing tenant behind, permanently.**
* **Lanes building right now against the old rule.**
* ⚠ **WHICH CHECKS ARE NOW WRONG — added 2026-09-10, and it is the one nobody
  thinks of.** A change to behaviour makes some existing test assert the OLD truth.
  That test does not fail helpfully; it either fails for a reason that reads as
  unrelated, or it goes on passing over a product that has moved. **NAME THEM HERE**,
  by file, before any code is written — the tests, the gates, the baselines and the
  walkthroughs that encode the behaviour being changed. **A check left asserting a
  superseded truth is not neutral: it actively defends the old behaviour**, and the
  next lane reads its green as permission. Checks that do not check are **26.5% of the
  1,143 defects filed in the nine days to 2026-09-09 — the LARGEST category in the
  register**, ahead of wrong logic, ahead of a stale record, and two and a half times
  the share of a screen not matching its design. This is where a good many of them are
  minted.

**STATE WHAT HAPPENS TO IN-FLIGHT WORK: _stop and redirect_, or _let it land and
change it after_.** On 2026-08-16 rulings arrived while five lanes were building
and nothing said which — that is a collision waiting to happen, and the requester
is the only person who can answer it.

---

## 5 · SIZE IT AND CONFIRM — with a fast path, or the process gets bypassed

Put it back in plain English **with a concrete figure**: what changes, what it
costs, what breaks. The requester confirms or redirects **before** work starts.

**THE FAST PATH, and it is not a loophole:** if the change touches **no rule, no
money and no data**, it is a one-line CR and it is simply done. A copy fix that
needs a ceremony is a process that will be bypassed for small things, then for
medium things, and then it protects nothing.

⚠ **AND ONE MORE LINE, ADDED 2026-09-10: HOW WILL WE KNOW IT LOOKS RIGHT?** Sizing
answers *what does it cost* and *what breaks*; **nothing in it has ever asked about
APPEARANCE**, which is the thing that goes wrong most. For a screen-shaped item the
answer is a sentence naming the drawing and who will diff against it — *"the property
Overview, row by row against its conformance file, walked at 1280 and 1440"*. **If
that sentence cannot be written at sizing time, the work is not sized.**

**Never as an ID to go and look up.** The standing instruction is a rule and a
worked number in plain English — *"a bill of $292.87 for a customer holding a
$57.13 credit captures $235.74"*, not *"per BR-PAY-015"*.

---

## 6 · EXECUTE — through the normal build process

Addendum r11, steps 2–6. **A change is not a special path.** It is an ordinary
build with a different origin, and it earns the same 2a/2b/2c/2d, the same
write-back obligation, and the same refusal to answer an open question.

### ⚠ ASSIGN LANES BY SCREEN, NOT BY FILE (2026-09-09) — AND THE REASON IS A COLLISION BETWEEN TWO SAFETY RULES

**Every lane of `CR-089` did its own job correctly and the screen still came out
wrong**, because five different waves each added one row to the property
Overview and **no lane was ever asked to make that screen match its drawing**.

**The trap is that the obvious defence causes it.** Hard-won laws 11 and 12
spend some four hundred lines on one danger: in a shared tree, two lanes editing
one file silently revert each other. It is the most-documented hazard in this
repository and it fired four times in one week — one near-miss would have
deleted an entire migration. So the natural way to dispatch parallel work is to
**split by file**, and that is what was done.

**But a screen is made of many files, and many screens share one file.** Split
by file and no lane owns a screen. **The measure that protects the code is the
measure that fragments the design, and until today only the first was written
down.**

**So, when a CR changes screens:**

* **A screen has ONE owner for the length of the CR.** That lane owns the
  screen's drawing, its header, its layout and its rows — not a task inside it.
* **Where two screens share a file, SERIALISE them.** One lane, then the next.
  Slower, and it is what makes a screen somebody's. Running them together is the
  choice that produced this failure.
* **Where a lane cannot reach into another's file**, it does what wave H did on
  2026-09-09: file the gap **with a check that goes red the day the hold
  expires**, so the next lane in that file is told by the suite rather than by
  memory. That handoff worked end to end between two lanes that never spoke, and
  it is the pattern to copy.
* ⚠ **THE BRIEF NAMES THE UI SKILL — IT DOES NOT PARAPHRASE IT (PO ruling 2026-09-10).**
  PO verbatim: *"please use this in all agents when you correct the screens"*. **Every
  lane dispatched against a screen loads the skill **FROM THE REPO** —
  `.claude/skills/react-tailwind-css-ui-generator/SKILL.md` — and follows it.**
  ⚠ **THE PATH IS PART OF THE RULE (PO, 2026-09-10: *"please use it form repo"*).**
  An account-level skill of the same name exists and was an empty placeholder reading
  `Test`; a lane that resolves the name to that copy gets nothing and does not know it.
  **The repo copy is the one under review, the one that travels with the branch, and
  the only one anybody can see change.** ⚠ **AND THE FAILURE THIS CLOSES WAS COMMITTED THE HOUR IT WAS RULED:** four
  lanes were dispatched to diff `CR-089`'s screens against its blueprint, and their
  briefs **restated the skill's §2 inventory and §4 comparison in the dispatcher's own
  words** instead of naming the file. That is a fifth copy of a rule that already lives
  in one place — the identical mechanism that has made this repository's UI rule-count
  wrong five times running. The lanes were corrected mid-flight; the rule is written
  here so the next dispatcher does not have to be. **A brief that summarises the skill
  has already drifted from it.**
* ⚠ **THE LANE'S BRIEF QUOTES THE DRAWING — IT DOES NOT LINK IT (added 2026-09-10).**
  The labels, in order, the columns, the tiles and their detail lines, written INTO
  the task row the lane is dispatched with. **A link is a drawing that will be
  skimmed; a quote is a drawing that will be built.** This is the cheapest of all the
  changes on this page and it addresses the largest category in the register: every
  lane of `CR-089` did its own job correctly and the screen still came out wrong,
  because the task sentences described what a person could DO and the layout lived
  somewhere none of them opened.
* **Name the owner in the task table.** A row with no owner is a row that falls
  in the seam between two waves — which is exactly where the four wrong tiles
  sat, correctly filed as a defect by a lane that could not fix them, and then
  belonging to nobody.

### ⚠ THE TASK TABLE CARRIES A STATUS COLUMN, FROM THE DAY THE CR IS WRITTEN (2026-09-02)

**A change request whose completion lives only in prose reads as ZERO PER CENT
DONE to anything that is not a careful human**, and on 2026-09-02 that sent a
lane to rebuild finished work on a money path.

What happened, because the shape matters more than the rule: `CR-062` and
`CR-063` write their tasks as `| # | Task | Notes |` — **no status column** —
and record completion in prose paragraphs underneath (*"A1–A6 ARE DONE
(2026-09-02, …)"*). Every one of those paragraphs is true, dated and specific.
But a survey looking for a per-row status found none and reported **70 of 71**
and **30 of 34** rows outstanding for work that had shipped that same day. Fire
was billing `$12.00` and `$110.00` on real invoices while the register read as
untouched. (⚠ **The `$110.00` is quoted here as the figure of 2026-09-02 and is
NOT current**: the PO removed the private hydrant from fire's size list on
2026-09-03 and that customer now bills `$60.00`. The process failure this
paragraph records is unaffected.)

**It is the `33/33` failure one register along**, and worth naming as the same
bug: a number that is right about what it measured and wrong about what it is
quoted for. Prose completion measures *what a reader was told*; a status column
measures *what a row says about itself*. Only the second survives being counted.

**So, from this date:**

  * **Every task row carries its own status**, set when the row is written and
    moved when the work lands. A row that is done says so ON THE ROW.
  * **Prose completion notes stay** — they carry the date, the lane and the
    evidence, and a status column cannot hold any of that. The column is not a
    replacement for the paragraph; it is the half a machine can read.
  * **A row is ticked with what was SEEN, not with what was intended** — the
    file, and what was in it. The reconciliations of 2026-09-02 were done by
    reading the code, because that is the only source that cannot be stale.

⚠ **THE SIXTY-FIVE EARLIER CHANGE REQUESTS ARE NOT RETROFITTED, AND THAT IS
DELIBERATE.** Adding a column to every task table in this file is precisely the
mass shared-file rewrite hard-won law 11 exists to prevent — one commit touching
every CR at once, in a register several lanes append to by the hour. They are
reconciled **when a lane is next in them**, which is when somebody is reading
the code anyway.

---

## 7 · VERSION — the step the PO says is usually skipped, and the reason it is

**PO, 2026-08-16: _"it will change the product version; so you should have
product version changes - many times this step is not followed correctly"_.**

**The state on the day this was written, which is the argument for every rule
below:** `07-frontend/package.json` reads **`0.0.1`** after **159 recorded defects**
(register count, 2026-08-16) and months of work. The backend carries **no version
at all** — no `__version__`, no constant, nothing. **Nothing shows a version to a
user.** So when the PO reported two production defects that morning, neither they
nor the product could say which build they were looking at.

Four rules, and the last is what makes it stick:

1. **ONE SOURCE OF TRUTH, derived everywhere else.** Not `package.json` *and* a
   constant *and* a document. Two committed copies of a generated file drifted
   within a day once already (hard-won law 5).
2. **VISIBLE IN THE RUNNING APP.** If a user cannot read the version on screen,
   a defect report cannot name it, and "is it fixed?" becomes unanswerable.
3. **EVERY CR AND EVERY DEFECT FIX RECORDS THE VERSION IT LANDED IN.**
4. **A GATE REFUSES** a CR marked done with no version, and a version bump with
   no CHANGELOG entry. **A step that depends on someone remembering is a step
   that is "many times not followed correctly"** — which is precisely the PO's
   complaint, and the only durable answer is a machine that will not let it pass.

**Scheme:** `<release>.<change>.<fix>` — R2, fourteenth change, seventh fix
since → **`2.14.7`**. A deploy stamps it; nothing else may.

### ⚠ AMENDED 2026-08-26 BY PO RULING — WHEN EACH NUMBER MOVES

**PO verbatim: _"We have to bump version when major when minor so we are able to
keep track of"_.** Two answers, and both supersede what this file said before.

| Number | What moves it | What does NOT move it |
|---|---|---|
| **`<release>`** — the first | **A NAMED RELEASE, declared by the PO.** A demo to a customer, a go-live, a scope boundary they name. | A breaking migration. A signed-rule change. A round-number boundary. **Nothing automatic** — a number that moved on engineering events a customer never sees would stop being a release. Today's 52 changes all stay inside release 2. |
| **`<change>`** — the middle | **EVERY WAVE**, at the moment it merges. | Not once per CR. The per-CR rule is SUPERSEDED: a defect reported against a per-CR version names eleven waves and dozens of files, and *"so we are able to keep track of"* is the whole point. |
| **`<fix>`** — the last | A defect fix, as before. | Unchanged by this ruling. |

**⚠ A WAVE BUMPS AT MERGE TIME, IN THE ORDER WAVES LAND — NEVER IN ITS OWN
BRANCH.** This is the cost the ruling accepts, and it was stated when the ruling
was made. Parallel waves collide on the four literals G35 holds in lockstep
(`package.json`, `package-lock.json`'s **two** copies, `pyproject.toml`); two
branches each claiming `2.54.0` produce a merge resolution that is somebody
picking a number, which is the exact failure this whole step exists to prevent.
So the bump is the **integrator's** act, not the lane's, and it lands in the
same commit as the merge or immediately after it.

**AND THE CHANGELOG ENTRY LANDS IN THAT SAME COMMIT.** Rule 4 above says a gate
must refuse a version bump with no CHANGELOG entry. **2.52.0 was cut with no
entry — the very next version after that rule was written** (DEF-806). Per-wave
bumping multiplies the chances to repeat it by roughly ten, so the gate is not
optional under this ruling: it is what makes per-wave bumping safe rather than
ten times as fragile.

**The product CHANGELOG is a real changelog**, not the design-handoff log at
`04-docs/CHANGELOG.md`, which is a different artefact serving a different reader.

---

## 8 · CLOSE — and state the rollback before shipping, not after

Every impacted surface **verified, not assumed** — the same standard a defect
closure is held to. The register row says what actually moved, with its version.

**AND STATE WHAT HAPPENS IF THIS WAS WRONG.** For a rule change, the reversal is
another CR. **For a migration or a data change it may not be reversible at all —
and that is worth knowing before it ships.** A change nobody can undo is a
decision, not an experiment, and it should be taken as one.

### ⛔ THE CLOSURE BAR — A CR IS NOT CLOSED UNTIL A PERSON DID THE TASK ON THE SCREEN (PO ruling 2026-08-18)

**Verbatim, and it is a standing rule for every CR from here:**

> *"in this session CR is not closed until we have confirm user is able to
> perform tasks using screen/broswer/UI"*

**What this changes.** Steps 0–7 could all be satisfied — rules quoted, code
written, tests green, version assigned, rollback stated — and the CR still does
not close. The closing evidence is **a person performing the task in a browser**,
against the real stack, and it is the LAST gate rather than a nice-to-have.

**What counts, and what does not:**

| Counts | Does NOT count |
|---|---|
| A browser walkthrough against a booted stack (Postgres + Django + the BUILT SPA), signed in through the real sign-in form | A green unit or integration suite, at any size |
| Assertions on **rendered text a person reads** | Assertions on API responses or component props |
| Every task the CR promises, performed end to end — create, edit, and the refusals | The happy path only |
| A re-run **over its own leftovers**, not only a pristine seed | One green run on a freshly reset database |
| **The screen compared to its DRAWING, row by row** — every label, in order | *"the feature works"* |

### ⛔ AND THE BAR GAINED ITS FOURTH ROW ON 2026-09-09 — DIFF THE SCREEN AGAINST ITS DRAWING

**The bar above was met in full and the screen was still wrong.** A person did
perform every task in a browser, against a booted stack, over real data. Every
row was green. **And the property Overview did not look like the design the PO
had agreed** — three rows missing, four labels different, one column drawn as
two.

**Because the bar asked whether the task could be PERFORMED, and never whether
the screen MATCHED.** Those are different questions and only the first was being
asked.

**So the closing evidence now includes a row-by-row comparison**: the drawn
labels, in the drawn order, present on the rendered page. Not *"it works"* —
*"it is the screen we agreed"*.

⚠ **This is the one place the repository has always known it was exposed and
never closed the gap.** It says so about itself in two places: *"no gate in this
repo reads rendered output"*, and *"most B14 rules are RATIFIED and
UNENFORCED"*. And hard-won law 6 is literally *"diff the running app against the
prototype — nine defects were found this way and by nothing else."*

**That law is the only hard-won law with no tool behind it.** Every other one
produced a gate, a script, or a refusal that fires by itself. This one has
always depended on a person remembering — and the entire hard-won-laws section
is a record of what happens to rules that depend on remembering. **A per-screen
walkthrough asserting the drawn labels in order is what turns it from a habit
into something that fires on its own**, and until one exists for a screen, that
screen's conformance is an unchecked claim.

**Why this is a rule and not a preference.** It is hard-won law 6 promoted to a
gate: *"No gate looks at rendered output. Nine defects were found this way and by
nothing else."* CR-004 met every other bar and then a walkthrough found **five
screens answering HTTP 500 with the whole suite green**. CR-006 is green on 21
tests and 343 assertions and is still marked BUILT-NOT-PROVEN for exactly this
reason. **Built and green is not the same statement as works.**

**The honest consequence, stated rather than discovered later:** this bar is
UNMET on CRs whose records already read as finished. Applying it retroactively is
the point, not a side effect — see the closure audit in `11-change-requests.md`
under CR-011.

**And it composes with r11 step 2b/2d**, which already demand a frontend half and
a click-through per STORY. This is the same evidence demanded once more at the
CHANGE boundary, because a CR spans stories and no single story's walkthrough
proves the change a requester actually asked for.

---

### ⛔ THE OTHER HALF OF THE BAR — A DEFECT IS NOT A CR BLOCKER (PO challenge, 2026-08-19)

**The PO asked, verbatim:** *"You already completed 3 runs on this why you wna tot do one
more? same is the case with 08 and 09 and 10; - why you are not closing it and every time
keep something open we are losing time why dont you fix it in one go ? I wnat to
uderstand"*.

**They were right, and this section is the fix.** The closure bar above says a person must
do the task on the screen. It never said *"and no defect may remain open in that area"* —
but that is how it was being applied, and applying it that way makes a CR **impossible to
close by construction**:

> A walkthrough exists to FIND defects. Every walkthrough finds some. If found defects
> reopen the CR, then every walkthrough that succeeds at its job prevents the closure it
> was run to produce. The loop has no fixed point. CR-006 ran **three** complete
> walkthroughs and stayed open through all three — not because the change was not
> delivered, but because each run did what it was for.

**So the rule, stated once and applied from here:**

**A defect blocks its CR only if it is one of THAT CR's OWN REQUIREMENTS not working.**
Everything else is a defect row with its own life, and the CR closes over it.

| Found during a CR's walkthrough | Blocks the CR? |
|---|---|
| A sentence in the CR text does not work on the screen | **YES** — the change was not delivered |
| A rule the CR states is not enforced | **YES** |
| A number the CR fixes is wrong on screen | **YES** |
| Polish — wrong button label, an ordinal, spacing | no |
| B14 debt, i18n debt, untranslated strings | no — **product-wide debt, tracked product-wide** |
| A pre-existing bug the walkthrough happened to surface | no — it predates the CR |
| A bug in an adjacent module the CR does not touch | no |
| A gap the CR text never asked for | no — that is a NEW CR, not this one |

**Three consequences, all deliberate:**

1. **A CR closes with open defects against it, and that is CORRECT.** The closure record
   names them by ID, so nothing is hidden — it says *"closed; DEF-xxx, DEF-yyy open against
   this surface"*. A reader can see both facts at once, which the old all-or-nothing status
   could never express.
2. **Defects are worked by SEVERITY across the product, not by which CR happened to find
   them.** A `high` in billing outranks a `low` in the CR that is currently open. Sorting
   the queue by CR is how 99 open defects accumulate while four CRs sit at 95% done.
3. **The blocking test is written down at close time**, in the closure record: *this defect
   blocks because the CR says X and X does not happen*. If that sentence cannot be written,
   the defect does not block.

**⚠ The one thing this does NOT relax.** The walkthrough itself is still required, and
still means a person performing the task in a browser against a booted stack. A CR that has
never been walked is not closeable under this section — it is closeable under the section
above once someone walks it. This rule shortens the tail; it does not remove the bar.

---

## 9 · HARDEN — turn one thing this change taught us into a check that fires by itself

**PO-added 2026-09-10.** Every change ends by converting **one** thing it learned into
something that will catch the same class of problem next time without anybody
remembering to look.

**WHY THIS IS A STEP AND NOT A HABIT, measured:** checks that do not check were
**26.5% of the 1,143 defects filed in the nine days to 2026-09-09 — the LARGEST
category in the register**, and larger than wrong logic and wrong money combined. **And the reason it stays that large is that we
file a check-that-does-not-check as a defect, fix the defect, and never fix the
BLINDNESS.** The finding gets closed. The hole it came through stays open.

**What counts as hardening, in descending order of value:**

| | What | Example from this repo |
|---|---|---|
| **Best** | A TEST that goes RED on the class of problem, not the instance — living next to the code it guards, run by that code's own suite | A duplicate CR *number* fails even when the branch suffixes differ |
| **Good** | An existing check taught to see what it was blind to | A gate reading two directories that print the number of files it does NOT read |
| **Good** | A hold that carries the test which fires the day it expires | Assert the destination by ADDRESS and by the screen id it opens |
| **Acceptable** | A number printed where there was only a claim | *"21 live refusals reach a clerk as silence"* beside *"0 unresolved"* |
| **Not hardening** | Fixing the instance · a comment · a line in a document nobody greps | — |

⚠ **PROVE IT RED FIRST, THROUGH THE ENTRY POINT THAT WILL REALLY RUN IT.** A guard
shown red via `python3 <gate>.py` and never through the suite's own path is **no
proof of the thing that matters** — that exact mistake announced two gates green
while the suite reported them crashed, twice in one day.

⚠ **AND ASK WHAT WOULD MAKE YOUR NEW CHECK PASS WRONGLY.** A check you cannot
describe a false pass for is a check you do not understand. The shapes this repo has
already produced: structurally incapable of failing · incapable of passing · looking
at the wrong thing · reporting zero over a scope it silently excludes.

**A change that genuinely learned nothing worth checking says so in one line, in its
closure record, and that line is reviewable.** It is allowed and it should be rare.

### ⛔ AND A NEW GATE IS NOT THE DEFAULT ANSWER — IT IS THE HEAVIEST ONE, AND IT NEEDS AGREEMENT (PO ruling 2026-09-10)

**PO verbatim:** *"please dont add gates in random - we have to agree to gates and
stay if new gate is required then we shoudl have process to agree it"*.

**The state that prompted it, measured the same day: 123 registered gates, 125 gate
files, and a full run reporting 76 PASS, 40 FAIL, 7 SKIP** — with the verdict line
reading `MERGE BLOCKED` on every single run, because the verdict is binary and forty
gates fail. **Gates have proliferated faster than anyone can read them**, and the
cost of one more is paid by every lane on every run, forever.

**So hardening reaches for a new gate LAST. Work down this list and stop at the first
one that fits:**

| Order | Option | Why it is preferred |
|---|---|---|
| **1** | **A test beside the code** | Owned by the module, run by its suite, dies with the code it guards. Costs nobody else anything |
| **2** | **Teach an EXISTING gate to see what it was blind to** | No new run cost, and it makes a check that already runs actually cover its subject |
| **3** | **Print a NUMBER where there was only a claim** | A declared blind spot with a figure beside it is worth more than a new check with none |
| **4** | **A new gate** | **Only when the first three genuinely cannot do it — and only with the PO's agreement** |

**HOW A NEW GATE GETS AGREED — five questions, answered in plain English before it is
written, not after:**

1. **Which existing gate nearly does this, and why can it not be extended?**
2. **Why can a test not do it?** — a thing checkable next to the code is a test, not a
   gate.
3. **What does it cost every run**, in seconds, on top of the existing suite?
4. **What would make it pass WRONGLY?** A check you cannot describe a false pass for
   is a check you do not understand.
5. **Who owns it, and what would make us DELETE it?** A gate with no retirement
   condition never leaves.

Put those five to the PO in plain sentences with a concrete figure, take the ruling,
and record it in `12-governance/02-decision-log.md` with its number. **A gate that
appears without that record is one somebody added on their own judgment, which is
what this ruling stops.**

⚠ **AND IT RUNS THE OTHER WAY — A GATE NOBODY ACTS ON IS DELETED, NOT INHERITED.**
Forty red gates is not forty problems being worked; it is forty places a genuinely
new failure can hide, which is exactly how a duplicate-id gate stayed red for two and
a half days while three lanes ran the suite past it. When the red set is triaged,
*delete* is a legitimate and expected outcome for a gate nobody will ever act on —
and it needs the same agreement, for the same reason.

---

## 10 · REAP — delete what this change created and no longer needs

**PO-added 2026-09-10**, and extended the same day with the PO's size ruling:
*"we cannot keep on increase the code and repo size - we need to limit it; otherwise
if we have to maintain this code for 5 years - our repo size will outgrow ourself"*.

### 10.1 The scaffolding

**Built-but-not-wired was ~8% of the defects in those same nine days, and it is
ENTIRELY SELF-INFLICTED** — every one of those was created by us and cleaned by
nobody, because the lane that creates scaffolding is finishing and the lane that
would remove it never knows it exists. Five lanes created dead locale keys in one
week and two argued in writing for keeping them.

Before closing, delete:

* **locale keys nothing renders** — in all eleven catalogues;
* **tests orphaned by the change** — a test for a screen that no longer exists is not
  coverage, it is a check that cannot fail;
* **holds whose screens have landed** — a control still refusing over a live screen;
* **fixtures, flags, shims and baselines** the change made unnecessary;
* ⚠ **the thing this change SUPERSEDED.** When a screen is redrawn, the old one goes
  **in the same commit**. Today both survive, and the next lane cannot tell which is
  current.

### 10.2 The size discipline

**Measured 2026-09-10, and the result is not what anyone expected:** the fastest
growing thing in this repository **is not code**. Over fourteen days the largest
single contributor was `12-governance/02-decision-log.md` at **+44,677 lines**, then
`11-change-requests.md` at **+16,140** and `CHANGELOG.md` at **+12,807**. The
governance folder is **18MB**, and one register already reached **2.5MB — the size at
which GitHub refuses to render it**, which is why CRs were split one file each.

| Mechanism | The rule |
|---|---|
| **Registers roll over** | An append-only register that grows forever becomes unreadable, then unrenderable, then a contention point every lane fights over. **Split by period, keep the index.** This is the fix already applied to change requests; the decision log is next and is the larger problem |
| **Net lines is a number in the closure record** | **Not a cap — a figure that has to be written down.** A maintenance fix that adds 500 lines net should have to say why. Nobody argues with a budget they never see |
| **Delete-on-supersede** | See 10.1. The old screen, the old rule's implementation, the replaced helper |
| **No new component the kit already has** | Already a UI rule. This makes it something the closure record reports |

⚠ **WHAT REAP IS NOT: a licence to tidy.** Delete only what THIS change created or
superseded. Deleting a sibling's scaffolding because it looks dead is how a shared
tree loses work, and *"it looked dead"* is not evidence — grep for its CONSUMERS
first, because an absence is invisible to every check this repo has.

---

## How the requester communicates a change

**However they like, in one sentence, whenever they like.** No form, no template,
no ID.

That is deliberate and it is not laziness on their part. The PO has said plainly:
*"you give me all these codes; im human dont understand"*. **The burden of
structuring belongs to us**, not to the person who knows what the product should
do. They say what they want; we classify it, work out the impact, and put it back
as *"here is what changes, here is the figure — confirm?"*

**The one thing only they can tell us: is it urgent, or is it a thought.**
Stop-and-redirect versus next-time-you-are-in-there. Everything else in this
process we can work out ourselves; that we cannot.
