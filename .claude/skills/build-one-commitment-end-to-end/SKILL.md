---
name: build-one-commitment-end-to-end
description: Build ONE approved commitment — a rule, a capability, a defect fix, a wave — all the way to pushed, proved and recorded, and close its record. This is "step 2". Run it on any module or any slice of one - a screen, an endpoint family, a money path, a migration, a background job, a report, a portal page. Use it AFTER step 1 has measured and routed, or after the PO has ruled. Triggers on - step 2, "build the wave", "start this one", "build it", "fix this defect", "implement the ruling", a business rule moving from ruled to built, a conformance file naming what to do first. Scope is ONE commitment and nothing beside it.
---

# Step 2 — build one commitment end to end

## What this is, and what it is not

**You are taking one thing that has already been decided, building it all the way
to pushed and proved, and leaving the record in a state where the next agent —
with only the repo — would build the same thing.**

**ONE commitment. Not the cluster it sits in.** The strongest predictor of a wave
that lands badly in this repo is a wave that grew while it was being built. A
second capability added in passing gets a tenth of the proof the first one got,
and it is always the second one that breaks.

**It is module-agnostic on purpose.** Nothing below names a module. The only thing
that changes between a screen and a nightly job is §1.

---

## 0 · READ THE COMMITMENT AND ITS RULES VERBATIM — THEN CHECK THE RULE AGAINST THE CODE

**Two acts. The second one is the one nobody does.**

**First, read it verbatim.** The story's frontmatter, the business rule, the PO's
words as recorded, the conformance file step 1 left. **Quoted, never summarised** —
a summary is a second artefact that can be wrong on its own.

**Then check the packet is current**, because the repo changes under you: open
questions, the decision log, the defect register, the change requests. Of each:
*was this ruled since the document I am about to build from was written?*

⚠ **AND READ THE STATUS COLUMN, NOT THE PROSE.** A closed question's body goes on
describing the open world and the body is where the instructions live.

⚠ **NOW THE ACT THAT GETS SKIPPED: CHECK THE RULE AGAINST THE CODE BEFORE YOU
BUILD ON IT.** A written rule is a claim about the product, made on a day that has
passed. It is not evidence.

Live examples from one week in this repo:

* A rule said two fields were *"accepted, reported successful, and changed
  nothing"*. **Measured: both are refused before that branch ever runs**, as
  *"unknown field"*. The rule described a bug that does not exist.
* A rule counted **7 writable fields and 11 refused**. The real figures are
  **11 and 34**, and three fields the drawing draws were missing from the count.
* A rule said an upload door was unscanned. **The middleware is global.**

**A comment claiming a guarantee is not the guarantee** (hard-won law 1) — and
neither is a business rule. **If the rule is wrong, amend it, dated, BEFORE you
build on it.** That is step W and its timing clause is the whole point: *before the
thing that depends on it, never "at the end."*

---

## 1 · CLASSIFY THE WORK FIRST — THE BAR IS DIFFERENT FOR EACH

**Decide this before you open a file.** A lane that builds a money path to a
screen's bar has shipped something nothing can catch.

| Kind | What "done" requires that the others do not |
|---|---|
| **Screen** | **Clicked in a browser** at the real address with real data, at the stated widths. No gate here reads rendered output — `tsc`, eslint, every test and every gate pass over a screen that renders nothing. Staff = 1280 and 1440; portal = **390 and 1280**, both mandatory |
| **API** | **Called** — real verb, real path, real body, and you read the response. A test with its own fixture proves the fixture. And: does a refusal reach the client as a *sentence*, or as silence? |
| **Money path 🔒** | Run on **real PostgreSQL**, never the default suite. A finance-signed figure cannot move without a re-sign — it is **STOP**, not a judgment call. `audit_log` on every money action. Stored 4dp, percentages 6dp, **display 2** |
| **Migration 🔒** | Ordering, and the **leaf-node** question: does another lane's migration make two leaves? Django then refuses *every test in the process* and names neither lane |
| **Background job** | **Run it and read what it wrote.** Its failure mode is silence, because nobody is watching. Idempotency is not optional on a bill run or an inbound webhook |
| **Report** | The numbers **tie out** against the thing they report on, computed a second way |
| **Portal page** | Everything under "screen", plus **390px**, plus the accessibility questions. A customer opens their bill on a phone and that is the primary case |

**Two cross-cutting bars that apply to all of them:**

* **Tenancy.** Never touch a tenant table without `app.tenant_id` set. RLS `FORCE`
  is on. No cross-tenant queryset. A gate reporting a clean zero over a file it
  never looked at is not a passing gate — see §4.
* **A 🔒 sensitive path is authored by AI under the strongest machine gates, flagged
  `HUMAN-REVIEW-PENDING`, with a row in the human-review ledger.** AI implements
  signed law; it never invents it.

---

## 2 · FIND WHAT EXISTS. MOUNT IT, DO NOT COPY IT.

```bash
ls 07-frontend/src/components/     # the kit — a second table is a defect, not a contribution
ls 10-scripts/                     # the tools that own the shared files
```

**Read `10-scripts/`'s listing before you write anything that touches a shared
file.** This is a law, not a tip, and it is a law because of what happened when it
was broken: a lane that had reverted eleven of a sibling's stamps then did
everything right — wrote a push helper, proved its guard could never fire, rewrote
it, watched it refuse before trusting it — and **`10-scripts/push_paths.sh` had
been in the repo the whole time, implemented exactly that refusal, and was
stricter.** The cause of the revert was not a missing guard; it was **an existing
guard nobody looked for.**

**Then: mount, do not copy.** When a form, a table or a panel already exists and
you need it somewhere else, **move it and narrow its props** — do not paste it.

One wave in this repo mounted **8,838 lines and copied 0.** The measurement that
matters is the one after: when the rule it implements changed, it changed in one
place. A copied form is two forms that agree today.

**The mechanics, because "move it" has a trap:** when you move a form to a new
host, **narrow the prop to the type the new host actually has.** A form moved from
a modal that had the full detail object into a page that only has the row object
will type-check against the old type and fail at runtime on the fields the row does
not carry. Narrow the type and let the compiler find them for you.

⚠ **And check the Tailwind ledger in the SAME commit.** A new front-end file must
be listed in `07-frontend/src/styles/route-b-migrated.txt` in the commit that
creates it. The ledger **gates which checker owns the file** — `g31` skips a listed
file, `routeBUtilities.test.ts` owns it — so a file added without its line, or a
line added without its file, turns a check red.

---

## 3 · NEVER INVENT A RULE. MINT THE QUESTION, STUB WITH ITS ID, BUILD TO THE BOUNDARY.

**When the rules run out mid-build you have exactly three options and only one of
them is allowed.**

| | |
|---|---|
| ❌ Choose a value and carry on | This is how a guess becomes signed law. Nobody will ever know it was a guess |
| ❌ Stop and wait | The rest of the commitment is buildable and now is not being built |
| ✅ **Mint the question, stub the gap with its id in the code, build everything up to the boundary** | `raise NotImplementedError("OQ-<MOD>-nnnn")` |

**First, grep — you may be about to re-ask a ruled question:**

```bash
grep -n -i "<subject>" 12-governance/02-decision-log.md 12-governance/01-open-questions.md
```

**A re-ask is a bug in us, not a clarification** (law 13). It also manufactures
inconsistency: a person answering the same thing twice from memory will eventually
answer differently, and then the repo holds two genuine, contradictory rulings.

**Most of the time the answer is that it is YOURS to decide.** Only three things
legitimately reach the PO: a ruling that collides with a signed rule · a frozen
finance figure · a fact only they hold. **A judgment recorded in the decision log
with its reasoning and its worked number is the deliverable; a question is the
failure to make one.**

⚠ **CITE NOTHING UNTIL THE ALLOCATOR HAS ANSWERED.** An id written into code before
it is allocated is its own defect class in this repo — it has happened with a
defect number invented in a seed script and with a rule id cited in a business-rules
file that had no register row, which then made the allocator's *"taken"* verdict
correct and unexplainable.

---

## 4 · PROVE EVERY GUARD RED FIRST — IN THE HARNESS THAT WILL RUN IT

**A test you have only seen pass is not evidence.** Break the thing, watch the
check fail, quote the failure, then fix it.

⚠ **AND THE SECOND HALF IS THE ONE THAT COSTS: PROVE IT THROUGH THE PATH THAT WILL
ACTUALLY RUN IT.** Two gates were each shown red, then green, by running the file
directly — which exercises `__main__` and **never the path the suite uses.** Both
were announced green while the suite reported `gate crashed: module has no
attribute 'run'`, twice, among 28 other failures where a new one is easy to miss.
**A red proof through the wrong entry point is not a weaker proof, it is no proof
of the thing that matters.**

**Before you trust a green, ask what would make this check pass WRONGLY.** A check
you cannot describe a false pass for is a check you do not understand. The five
shapes this repo has actually shipped:

1. **Proved red at birth, then never read again** — red for days, three lanes ran
   the suite past it. A guard is a claim only while somebody reads its output.
2. **Structurally incapable of failing** — `diff … | grep -q '^<'` under
   `pipefail` is always false; `npx tsc` with no local install fetches a newer
   compiler, aborts on a config error and reports no type errors at all.
3. **Incapable of passing** — a fixture demanding a grant only a superuser can
   issue, where a superuser bypasses the very policies under test.
4. **Looking at the wrong thing** — a hold-expiry test asserting a screen is
   registered at an address the router was not mounting it at.
5. **Reporting zero over a scope it silently excludes** — and this is the hardest
   to see, because the check is not lying. One gate reported **0 unresolved**,
   truthfully, of everything it could see, over **21 live refusals that reach a
   clerk as silence.** **A declared blind spot with no NUMBER attached is
   indistinguishable from an empty one** — so a check that cannot cover its whole
   subject must print what it skipped beside what it checked.

⚠ **AND A RED PROOF MUST BE A REAL RED.** Deleting a route from `App.tsx` to prove
a routing test goes red proves nothing if the suite mounts its own `<Routes>` —
every case stays green and you have just certified a test that cannot fail. **Name
the assertion that actually holds the thing**, and break THAT.

---

## 5 · BUILT IS NOT WIRED — AND IT RUNS BOTH WAYS

**Forward:** a component with an optional prop that nothing passes is dead UI. It
renders nothing, every test passes, and the feature does not exist. Four defects in
one day. `G13` enforces this — do not silence it.

⚠ **Backward, which `G13` cannot see and which costs more:** a **live screen behind
a dead control.** A button greyed out, a nav word that is a `<span>`, a card whose
`Start →` says *"opens with the next release"* — over a screen that is routed,
tested and live. `G13` asks whether a prop is passed; **nothing asks whether a
REFUSAL is still true.**

**So, in the same commit as your build:**

* **Grep for the control that was holding your thing** and release it.
* **Write the test that fires when a hold expires** — asserting the destination
  **by address and by the screen id it opens**, so the day the screen lands the
  suite goes red and names it. A hold with no such test is a promise nobody is
  keeping.
* **Mount a routed component under the real path pattern.** A fixture that cannot
  tell a working link from a broken one is how this hid: a page mounted bare in a
  `MemoryRouter` with no `/:tenant/…` route built every address as `//portal/…`, a
  protocol-relative URL to another host — **which reads as a perfectly good string
  to `toContain`.**
* **Check the door from the outside.** Start where the user starts. Two screens in
  this repo are routed, built, tested and translated into eleven languages with no
  menu entry, no link and no button. They open only if you type the address.

---

## 6 · THE SHARED TREE: RE-DERIVE FROM THE PINNED TIP, VERIFY BY SUBTRACTION, PUSH OFTEN

**Many lanes share one working tree and one index.** Everything here is hard-won
law 11 and 12; read them in `CLAUDE.md` — this is the operating summary.

**Use the tool that owns the file. Always.**

| Job | Tool |
|---|---|
| Push a set of paths | `10-scripts/push_paths.sh` — pins the tip once, refuses a moved path, refuses base-is-tip, guards a vanishing register line |
| Take a number | `10-scripts/allocate.py <family> --verify <n>` — asks the **remote**, not this checkout |
| File a defect | `10-scripts/file_defect.py … --id-module <MOD>` — appends ONE row as raw bytes, refuses to edit |
| Close a defect | `10-scripts/close_defect.py --fixed-commit <sha>` |
| Check HEAD is where you left it | `10-scripts/check_head_current.sh` — **the first command of every session** |

**Never round-trip a shared register through a serialiser.** Python's `csv` writer
re-serialises every row: a one-row append comes back as a 1,967-hunk diff, no data
lost — **and that is what makes it dangerous**, because every check the law
prescribes comes back clean and *"read the hunks and confirm every one is yours"*
becomes impossible to perform at all.

**The four post-push checks, and what each one is blind to:**

1. `git show <commit>` — **read the hunks.** Confirm every one is yours, not merely
   that yours is present. `--stat` cannot answer this and has been trusted to twice.
2. `git diff --numstat "$TIP" <commit>` — **read it as arithmetic.** On a two-row
   append, `2 insertions, 1 deletion` is a destroyed row, not noise.
3. `git show HEAD:<path> | grep <your marker>` — your change survived.
4. `git diff --numstat <your last commit on this file> <the rebased one>` — **this
   is the one everybody skips.** Every other check measures against the tip, and
   **the tip is defined as the world without your work in it**, so none of them
   protects you from your own earlier, committed-but-unpushed self. A lane deleted
   its own function this way and every check passed.

**And after a `commit-tree` push, move the FILES too** — `git merge --ff-only
origin/<branch>`. `commit-tree` builds from the pinned tip and updates **no file on
disk**; a `git reset --mixed` afterwards leaves a loaded revert of every file your
siblings touched, **and `git status` reports CLEAN**, because the index matches the
tree it was just told to match. Verify by subtraction: `git diff --numstat "$TIP"`
must print nothing.

**PUSH EVERY TWENTY MINUTES. A push is the only durable act in this environment.**
The container's filesystem, `.git` included, can be restored from a session-start
snapshot; a commit alone does not survive it. A partial fix on the branch beats a
complete one in a dead container.

---

## 7 · VERSION: ALLOCATE, VERIFY, AND READ THE WARNING

**Every shipped change carries a version.** `<release>.<change>.<fix>`, one source
of truth, visible on screen, recorded on the CR or the defect row.

```bash
python3 10-scripts/allocate.py version --bump change
python3 10-scripts/allocate.py version --verify <the number you took>
```

⚠ **AND READ THE SECOND LINE IT PRINTS.** The verdict answers *"has anybody
PUSHED this number?"* — and a version is **claimed by editing three tracked files
in a shared tree, long before anybody pushes.** The tree is the one place the
verdict does not look, so the allocator prints a separate tree-claim warning beside
it. Two lanes shipped the same number twice in one afternoon and every lane's
arithmetic was right; what was wrong was **which world the maximum came from.**

⚠ **AND VERSIONS COMPARE AS TUPLES OF INTEGERS, NEVER AS TEXT.** `"2.9.0" > "2.10.0"`
is true as strings and false as versions.

**The step exists because it is the step usually skipped.** This repo's front end
read `0.0.1` after 159 recorded defects and the backend carried no version at all —
so when two production defects were reported, neither the PO nor the product could
say which build they were looking at.

---

## 8 · CLOSE THE RECORD — AND WRITE IT SO A HUMAN CAN READ IT

**The record is not paperwork after the work. It is the work's only durable half**
(law 9, law 10). The conversation does not survive; the repo does. **The test is not
"was a decision made" — it is "would the next agent, with only the repo, build the
same thing?"**

| What | Where |
|---|---|
| What shipped, in plain English, **with a figure** | `CHANGELOG.md`, under its version |
| A ruling, a figure, an option chosen | `12-governance/02-decision-log.md`, verbatim + the worked number shown |
| A rule the PO stated or changed | the module's `02-business-rules.md`, CONFIRMED or SUPERSEDED **with its date** — and every citing document stamped in the same commit |
| What was shown to the PO, in plain English with a figure | `12-governance/09-human-review-ledger.md`, **before** review |
| A design constraint or workflow shape | the epic's §1 and §3, plus a journey file when it spans modules |
| **Why it is built this way** | the file's own docstring — that is what a docstring is FOR |
| The proof you ran | `04-docs/05-modules/<module>/conformance/<CR>-<wave>-step2.md` |

⚠ **A RULING IS A FAN-OUT, NOT A STATUS EDIT.** One ruling left **eight** surfaces
saying different things: the register row's status, the register row's **body**, the
decision log, the module's business rules, the change request, the epic, the
execution plan and the story frontmatter. **Walk all of them in the same commit.**

⚠ **AND WRITE IT THE WAY YOU WOULD SAY IT OUT LOUD.** Plain sentences, a concrete
figure where one matters, an id only where somebody would use it to look something
up themselves. A status report in this repo once carried ~40 defect ids, ~12 gate
ids and the words *shadow run*, *baseline*, *ratchet* and *blob* in answer to a
one-sentence question, and the PO's reply was *"I did not understand what are you
talking about"*. **Nothing can catch this** — no gate reads a chat reply. **The
test: if a paragraph cannot be read aloud to somebody who has never seen the
register, it is not finished.** The detail belongs in the repo; the reply carries
the meaning.

**Then move the rule from *ruled* to *built*** — the business rule's status, the
story's status, the CR's step-7 version row, the defect's `fixed_commit`. **A
commitment that is built and still recorded as ruled will be built again.**

---

## 9 · REPORT WHAT YOU LEFT, WHAT YOU GOT WRONG, AND EVERY RED YOU DID NOT CAUSE

**Three things, and all three are uncomfortable, which is why they are a numbered
step rather than a matter of conscience.**

**1 · What you left.** Name it as a thing, with an id, routed. *"The rest of the
tab"* is not a handover. If you built three of thirteen actions, say which three
and which ten, and file the ten.

**2 · What you got wrong.** If a figure you gave earlier was wrong, correct it in
the report **plainly and once**, and correct it in the repo. Two of this session's
worst moments were a wrong field count and a wrong description of a server's
behaviour, both told to the PO with confidence. **Correcting it costs a sentence;
leaving it costs a ruling written on a false premise.**

⚠ **And when a correction cannot be a subtraction** — because the push guard
refuses a vanishing register line, or because the wrong sentences have been cited
elsewhere — **leave the wrong text visible beneath a dated ⚠ stamp** rather than
quietly deleting it. A reader who followed the old sentence needs to find out that
it moved.

**3 · Every red you did not cause, WITH ITS DATE.** Law 7's first habit. Before you
push, look at every red line in the suite and ask *was this red before I started?*
— **and check it, because it is a claim about history:**

```bash
git log -S "<the failing symbol>" -- <file>
```

Two lanes once reported the same red in good faith and in almost the same words as
*"pre-existing, not mine"*, **and the second was the lane that had caused it.**
Neither ran the command. **The dismissal costs more than the revert**, because a
revert is caught by the next reader while two confident *not mine* reports tell
every subsequent reader not to look — which is how a true red acquires the
protective colouring of a known one.

---

## 10 · A RED THAT BREAKS THE BUILD IS YOURS, WHOEVER CAUSED IT

⚠ **THIS IS THE NEWEST RULE HERE AND IT NARROWS §9. Read them together.**

§9 tells you to date a red you did not cause and say so out loud. **That is right for
a failing check. It is wrong for a broken build**, and the difference is not a matter
of degree:

| | A failing check | A build that does not build |
|---|---|---|
| Who is blocked | the lane that owns that check | **everybody, including the customer** |
| What the next lane can do | work around it | **nothing** |
| What "correctly dated, not mine" achieves | it gets the right lane looking | **nothing at all** |

**On 2026-09-13 the Docker frontend build was broken by two static `node:` imports
with no types. THREE separate lanes each ran it, each correctly established that the
red was not theirs, each said so accurately in their report — and none of them fixed
it.** Every one of them followed §9 exactly. The build stayed broken. That is the
whole case for this rule: **§9 executed perfectly still leaves the product
unbuildable, because "not mine" is a true statement that fixes nothing.**

**So the rule is:**

> **If the product does not build, does not start, or cannot be deployed, it is
> yours to fix the moment you find it — whoever caused it, whatever wave you are
> in, whatever else you were doing.** Fix it, push it, file it against the cause
> with its date, and say in your report that you found it and fixed it.

**The test for whether this rule applies is one question: _can the next lane do
their work?_** A red gate on a file nobody is touching — §9, date it and say so. A
build that will not compile, a migration graph with two leaves, a dev server that
will not start, a test suite that cannot collect — **§10, it is yours.**

⚠ **And fix it to the house pattern, not to the first thing that compiles.** The
build above was fixed with the dynamic-import form this repo already uses in four
other test files. A lane inventing its own fix for a shared break has replaced one
problem with two.

---

## 11 · THE SHARED MACHINE

**Other lanes are on this box right now.** Compute, ports and tools are shared and
the failure mode is that everybody's work stops at once.

* **Never kill a process you did not start.** Two independent checks before
  reclaiming anything: it is not yours, **and** it is provably idle — age plus
  zero connections, not age alone. Eleven orphaned dev servers once held **1.9 GB**
  for 33 hours; reclaiming them needed both checks, and the second is what made it
  safe.
* **Stop your own.** A dev server, a watcher, a `--reuse-db` run — stop it when the
  wave ends. Your orphan is the next lane's mystery.
* **Do not run the full gate suite to check your one thing.** It is minutes of
  shared CPU and it buries a real new red among the existing ones. Run your gate.
  Run the suites your change touches.
* **Run the transaction-sensitive suites with `JOBS_EAGER=false --reuse-db`.** One
  lane measured a twelve-file run at an hour that took **four minutes** with the
  eager flag off.
* **Fewer lanes beat more lanes in one tree**, and a lane in its own `git worktree`
  beats both. On the day a rewind reverted 152 files of the shared tree, the two
  lanes working in their own worktrees lost nothing.

---

## The close-out checklist

- [ ] The commitment is quoted verbatim, and **the rule was checked against the code**
- [ ] The kind of work is named (§1) and built to that kind's bar
- [ ] The kit was searched; everything reusable was **mounted, not copied**
- [ ] `10-scripts/` was listed before anything touched a shared file
- [ ] New front-end files are in the Tailwind ledger **in the same commit**
- [ ] No rule invented; every gap is a minted question with its id in the code
- [ ] Every guard proved **red first, in the harness that will run it**
- [ ] Built **and** wired — forward, and the hold released backward, with its test
- [ ] Pushed, hunks read, subtraction verified, and verified against **your own**
      previous commit
- [ ] Version allocated, verified, and the **tree-claim warning read**
- [ ] Changelog, decision log, business rule, review row, conformance file — the
      rule moved from **ruled** to **built**
- [ ] Report names what was left, what was wrong, and **every red with its date**
- [ ] **The product builds.** If it did not, you fixed it (§10)
- [ ] Your processes are stopped
