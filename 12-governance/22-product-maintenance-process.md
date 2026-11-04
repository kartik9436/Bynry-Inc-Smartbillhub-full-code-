# The product maintenance process — when the thing exists and somebody is using it

**PO-ruled 2026-09-10.** The companion to the build process
(`04-docs/02-decisions/12-engineering-plan.md` → **Addendum r11**) and to the change
process (`13-change-process.md`).

**WHY THIS FILE HAD TO BE WRITTEN, and it is the finding rather than the preamble:
there was no maintenance process. There never has been.** `r11` is titled *"THE
STORY→CODE PROCESS"* — it is a build process, entered from a story in an epic.
`13-change-process.md` is an intake-and-classify process, entered when the agreement
moves. **Nothing anywhere in this repository said how to fix a defect.** So beta work
was being routed through the change process, because that was the only documented
path that existed — which is exactly how our own misses start being recorded as the
customer's new requirements.

**The phase this exists for, in the PO's words (2026-09-10):** *"we have complete
first round of code writing for entire prodict; it means now we have code for most of
the feature in some of other format; now what we are doing is user testing the
applciation in beta stages and tell us what problems they are facing in UI, in
functionality , in behaviour of the product"*.

---

## WHICH PROCESS AM I IN? — one question

> ## **Can a user do this task in the product today?**
> **No → BUILD.  Yes → MAINTENANCE.**

**The test is about the USER, not about the code.** *"Is there already a file?"* gives
the wrong answer for a new screen inside an existing module.

| The work | Can they do it today? | Track |
|---|---|---|
| A new module | No | **Build** |
| A new screen in an existing module | No | **Build** |
| Something a beta user wants that was never agreed | No | **Build**, entered through a CR |
| A new field or column on a live screen | Yes — they use that screen | **Maintenance** |
| A label is wrong, a tile is missing, a row is in the wrong order | Yes | **Maintenance** |
| A number is wrong on a bill | Yes | **Maintenance** |
| **A live screen redrawn end to end** | Yes | **Maintenance** — see below |

**Who decides: WE do, not the PO.** Classifying work as Build or Maintenance is
bookkeeping against the rule above, and hard-won law 13 puts it squarely in the set
of things we decide and write down. **It goes back to the PO only when the answer
changes what a user can DO or what they were PROMISED** — that is a change, and they
rule on it. When a lane genuinely cannot tell, it says so rather than picking quietly.

### ⚠ THE REDESIGN CASE, NAMED DELIBERATELY — IT IS WHERE THIS WILL GO WRONG FIRST

**A redesign of a screen people already use is MAINTENANCE**, and it is called out by
name here on the PO's instruction (2026-09-10), because the general rule alone will
not survive contact with it.

**Three of the recent change requests are exactly this shape:** Premises & Units
rejourneyed (eleven waves, 55 specifications), the customer portal redesigned (sixty
wireframes, eleven waves), Plans & Rates redrawn (seven tab merges, a wizard step
removed).

**Why it goes wrong: it FEELS like building.** New wireframes, new layout, many
waves, hundreds of lines of new code — every instinct says Build. And a lane that
follows the Build track loses the four things this process exists for: **no
reproduce, no blast radius, no regression pass on the neighbouring screens, and
nobody tells the beta users their screen changed underneath them.**

**It has already gone wrong once, in the biggest of the three.** The property Overview
shipped with three rows missing and four labels different, every suite green, because
five waves each did their own job correctly and no lane owned the screen.

**So a redesign is Maintenance, and it BORROWS EXACTLY ONE THING FROM BUILD: the
drawing step.** It must have a drawn specification in the tree, agreed with the PO,
before code — and it keeps every regression and reporter duty below. **Nothing else
crosses over.**

---

## HOW THE WORK ARRIVES

**The PO relays beta findings in the working chat session, consolidated** (their
words, 2026-09-10: *"we are working on it; and conslidated details will be reported
to you; we will do it using chats"*). A direct tester-to-register channel is theirs to
design and is not assumed here.

**Then it is classified, and in the beta the default is DEFECT** — PO ruling
2026-09-10, *"CR is change in product, defect is product does not do what is
expected"*. The routing table is in `13-change-process.md` §1. **Did the product do
what was expected? No → defect, however politely reported. Yes, and they want it
different now they have used it → change.**

---

## WHAT GETS FIXED FIRST

`13-change-process.md` already rules the principle — **by severity across the product,
not by which change request happened to find it.** What was missing is what severity
means, so it is stated here once:

| Order | When | Example |
|---|---|---|
| **1 · Now, ahead of everything** | Money is wrong, or data is being lost or corrupted | A bill charges the wrong amount; a payment posts twice |
| **2 · Next** | Someone cannot complete a core task at all, and there is no workaround | A customer cannot pay; a clerk cannot issue a bill |
| **3 · The queue** | It works, but it is wrong or confusing | A wrong label, a missing row, an awkward flow |
| **4 · When you are in that file anyway** | Cosmetic, debt, tidying | Spacing, a stale comment, a dead key |

**Two things it explicitly is NOT: not by who shouted loudest, and not by which change
request happens to be open.** A money defect in billing outranks everything inside the
CR somebody is working on today.

---

## THE STEPS

### 0 · REPRODUCE IT — before you read a line of code

**The highest-value ten minutes in this whole process, and the build process has no
equivalent because greenfield has nothing to reproduce.**

Get to the state the reporter was in and **see it with your own eyes**. Record how:
which tenant, which account, which screen, which button, what you expected, what
happened. That record is what step 4 proves against.

**If you cannot reproduce it, that is a FINDING, not a delay** — say so, and ask the
one question that would let you. **Never fix what you have not seen.** A fix aimed at
what you think they meant is how the same thing gets reported twice.

### 1 · LOCATE IT — the real file, not the assumed one

Read the screen that is actually mounted at that address, not the one whose name
matches. **A hold-expiry test once asserted a screen was registered at one address
while the router mounted it at another, and both opened onto *"not built yet"* with
every check passing.**

### 2 · BLAST RADIUS — what else uses this?

**Greenfield has almost no blast radius; the beta has real people on the adjacent
screens.** Before changing anything shared — a component, a seam, a selector, a rule
— list what else consumes it.

⚠ **And the mirror, which is invisible to every check here: what else USED it that you
are about to remove?** Before retiring a value, a field or a helper, **grep for its
CONSUMERS** — an absence is invisible to every check this repo has. Retiring one
address kind silently returned null on every account header forever, with `tsc` and
every test green.

### 2.5 · IF IT IS A SCREEN, LOAD THE UI SKILL — PO ruling, 2026-09-10

**PO verbatim: *"please use this in all agents when you correct the screens"*.**

**Any fix that changes what a person sees loads the skill **FROM THE REPO** —
`.claude/skills/react-tailwind-css-ui-generator/SKILL.md` — and follows it.**
⚠ **THE PATH IS PART OF THE RULE (PO, 2026-09-10: *"please use it form repo"*):** an
account-level skill of the same name exists and was an empty placeholder reading
`Test`. A lane that resolves the bare name to that copy gets nothing and cannot tell.
The repo copy is the reviewed one, it travels with the branch, and it is the only one
anybody can watch change. Not a summary of it, not a
dispatcher's paraphrase of it — the file. It carries the pre-flight that catches the
failures nothing else can see (a Tailwind utility in a non-migrated file renders as
**nothing at all** while every test passes), the kit, the copy caps, the eleven
catalogues, and the close-out this process's §8 depends on.

⚠ **NAME IT, NEVER RESTATE IT.** On the day this was ruled, four lanes were dispatched
with the skill's own §2 and §4 rewritten into their briefs in the dispatcher's words.
**That is a second copy, and a second copy drifts** — it is the same mechanism that has
made this repository's UI rule-count wrong five separate times.

### 3 · THE MINIMAL FIX

**What the defect needs, and no more.** Do not widen the change, do not tidy the
neighbourhood, do not refactor on the way past. If you find a second problem, **file
it** — that is what the register is for, and the fix order above decides when it gets
worked.

### 4 · PROVE IT AGAINST THE REPRODUCTION

Go back to step 0's recorded state and **do the same thing again.** The proof is that
the reported symptom is gone, in a browser, not that a test turned green.

**And write the test that would have caught it** — beside the code, in its module's
own suite. That is step 9's first and cheapest option, and it is not a new gate.

### 5 · REGRESSION — walk the neighbours

**A fix that breaks an adjacent screen is worse than the defect it fixed**, because
the defect was known and the regression is not. Walk what step 2 listed. For a
screen-shaped fix, that means the screens that share the component you touched.

### 6 · ACCESSIBILITY — for any customer-portal screen you touch

**PO ruling 2026-09-10: the customer portal is held to WCAG 2.1 Level AA**, and a
utility's procurement team is owed a conformance report naming, criterion by
criterion, whether we support it, partly support it, or do not.

**We do not run an accessibility project. Every portal screen we touch comes out
accessible before it goes back** — the same shape as the responsive ruling. 93 portal
files, fixed as we pass through them, and the report is then written from the record
of what was actually checked rather than from intention.

**Eight questions, roughly ten minutes, and only on a screen you were already
touching:**

| # | The question |
|---|---|
| 1 | Can you do everything on this screen using only the keyboard — no mouse? |
| 2 | Can you always see where you are as you tab through it? |
| 3 | Does every box you type into have a label properly attached to it? |
| 4 | Does the page have one main heading, and headings in a sensible order? |
| 5 | Is the text dark enough against its background to read? |
| 6 | Does it still work when the window is narrow and when the text is enlarged? |
| 7 | When something happens — *payment received* — is it announced, not just shown? |
| 8 | Before money moves, can the customer check it or undo it? |

⚠ **THE HONEST POSITION, so nobody claims more than we have: as of 2026-09-10 this
repository contains NO accessibility tooling at all** — no axe, no Lighthouse, no
jest-axe, no pa11y, no accessibility lint rule — **zero accessibility test files, and
no WCAG documentation.** 13 of 93 portal files use any `aria-` or `role=`. Whatever
assessment has been described to a customer, its evidence is not here and nothing
prevents it regressing. **A conformance row saying *"partly, finished by <date>"*
costs nothing. A row saying *"supported"* that we cannot evidence is the one that
carries real exposure.**

⚠ **AND ONE NUMBER FROM THAT STANDARD CHANGES A FIGURE WE AGREED ELSEWHERE:** reflow
is required at **320px**, and our agreed portal design target is **390**. That gap is
real, it is recorded here rather than quietly absorbed, and it is the kind of thing a
criterion-level report surfaces and a bullet list does not.

### 7 · VERSION AND ROLLBACK — both before shipping, not after

The version rule is unchanged (`13-change-process.md` §7): the middle number moves at
merge, in wave order, changelog in the same commit.

**AND THE ROLLBACK RULE, PO-SET 2026-09-10 AND DELIBERATELY SIMPLE:**

> *"for time being - Code only — Revert the commit. Done."*

**That is the rule. Do not build machinery for anything else.**

⚠ **ONE LINE OF HONESTY GOES WITH IT, AND IT IS A FLAG RATHER THAN A PROCEDURE.** Some
fixes cannot be undone by reverting, and the doc must not imply otherwise: a fix that
**repairs data** leaves the repaired rows behind when the code is reverted, and a fix
that **sends something out** — a migration applied, bills re-issued, a notice mailed —
cannot be recalled at all. **Where a fix is one of those, SAY SO in one sentence before
it ships.** Nothing more is required and nothing is built for it. A fix nobody can undo
is a decision rather than an experiment, and the person shipping it should know which
one they are making.

### 8 · CLOSE — and tell the reporter, naming the build

Every surface verified rather than assumed, the defect row closed with what actually
moved and the version it landed in, and — the part the build process has no reason to
have — **the reporter is told, and told which build to look in.**

*"Fixed in 2.234.16"* is the whole requirement. **A beta tester who reports three
things and hears nothing back stops reporting**, and then the beta stops producing the
only real signal we have.

### 9 · HARDEN · 10 · REAP

**Identical to `13-change-process.md` §9 and §10 — they are not repeated here.**
Turn one thing this taught us into a check that fires by itself, **reaching for a new
gate LAST and only with the PO's agreement**; then delete the scaffolding this fix
created, and the thing it superseded, in the same commit.

---

## WHAT IS IDENTICAL TO THE BUILD TRACK — deliberately

**These do not differ, and that is what stops the two processes drifting apart:**

check HEAD is real before reading a file · read `CLAUDE.md` and the four registers ·
decide and write it down before building on it · prove a new guard fails first,
through the entry point that will really run it · read the reds you did not cause and
**date** the ones you call pre-existing · commit by pathspec and verify the hunks are
yours · push immediately, because a push is the only durable act in this environment.

**The tracks differ at the ENDS. They are the same in the middle.**

---

## DEFERRED, WITH A DATE ON IT

| What | Ruling |
|---|---|
| **Performance and security** | **PO 2026-09-10: *"we will look at it later when we go live"*.** Not in scope for the beta maintenance loop. Recorded here so it returns to the agenda at go-live rather than evaporating |
| **A direct tester-to-register intake channel** | Being designed by the PO; findings arrive consolidated through the chat session until then |
| **Who reviews a maintenance fix** | Open. The build track has human review; this track has not yet been given one |

---

## BOOTING A STACK FOR THE BROWSER PROOF — THE CONTAINER IS SHARED, NOT JUST THE TREE

This process **orders** a browser proof: *"proof against the reproduction in a browser"*,
because **no gate in this repo reads rendered output**. So every lane that follows it
boots a stack and then tears one down, and the tear-down is where it goes wrong.

⚠ **`pkill -f "server.mjs"` MATCHES EVERY LANE'S SERVER, NOT YOURS.** Self-reported on
2026-09-20 by a lane that had just finished a clean 18-of-18 walk: two of its three kills
were correctly scoped to its own ports, and the third was a bare pattern. Nothing was
provably lost — no sibling SPA was running, and six sibling backends were alive and
untouched afterwards — but **the lane could not prove that retroactively**, and said so
rather than claiming *not mine*, which is the move CLAUDE.md law 7 names as costing more
than the mistake.

**THE RULE: kill by the PID you recorded, or by a pattern that contains your own port.**
`pkill -f "PORT=8931.*server.mjs"`, never `pkill -f "server.mjs"`. Same for `node`,
`vite`, `python`, `manage.py` and `runserver`.

⚠ **AND THE GENERAL FORM IS THE HALF WORTH KEEPING.** CLAUDE.md law 11 bans any command
that makes the shared **working tree** momentarily not-what-it-was — `git stash`,
`git checkout -- <path>`, `git restore`, `git reset --hard`, `git clean` — because for
those seconds other lanes are reading a tree you silently emptied. **A container with
seven lanes in it is a shared space in more ways than the index**, and the same
reasoning covers shared **processes**, shared **ports** and shared **databases**. A lane
that would never run `git stash` will run `pkill -f` without the rule coming to mind,
for the same reason law 11 records about the stash: the dangerous use is a throwaway
diagnostic, where the breadth is incidental to the intent.

**What that lane did right, and it is the pattern to copy:** it **migrated and seeded its
own isolated database** (`sbh_ncd2`, dropped afterwards) precisely so no sibling's data
could move, and it booted through `server.mjs` — the deployed join — rather than a dev
server, so the walk exercised what a user actually gets. **Isolate the database, record
the PIDs, scope the kills, and boot the real join.**

---

## ⚠ THE BROWSER PROOF DOES NOT TYPE-CHECK, AND 55 OF 56 WALK SCRIPTS PROVE IT

This process orders a browser proof because no gate here reads rendered output. **That
proof has a hole in it, and it is measured rather than asserted:**

```
$ grep -rhoE "(npm run build|vite build)" 10-scripts/*.mjs | sort | uniq -c
     55 vite build
      1 npm run build
$ grep '"build"' 07-frontend/package.json
     "build": "tsc --noEmit && vite build",
```

**`npm run build` is `tsc --noEmit && vite build`. Fifty-five of fifty-six walk scripts
run the second half alone.** `vite` strips types without checking them, so it builds a
perfectly good bundle out of code that does not compile.

**So a lane can build, drive Chromium, watch every assertion pass, and report a green
walk over a branch that does not type-check.** That is exactly what happened on
2026-09-20 (`DEF-CUS-6090`): `tsc` clean at 21:16, red at 21:52 with eleven sibling
commits in between, and a **successful `vite build` at 21:50** in the middle of it. The
walk was not lying; it was answering a question nobody had asked it.

**THE HABIT: run `tsc --noEmit` against the TIP before you push, not only against the base
you started from.** `tsc` is a **whole-tree** check, so unlike your tests it can be broken
by a file you have never opened — a sibling can turn it red between your last clean run
and your push. A walk script that boots a bundle is not a substitute and cannot be one.

⚠ **AND THIS IS WHY A BREAK LIKE THAT GETS FILED THREE AND FOUR TIMES OVER.** On
2026-09-20 two separate compile breaks were each filed by multiple lanes — every lane
correctly reading a failure it had not caused, every lane dating it, and every lane
measuring against **its own base** while the fix had already landed on the tip. Re-read
the failing file from the live tip and re-run the check **before** filing; see the
decision-log section of that date.

---

## A WAIT WITH NO CLOCK IN IT NEVER ENDS — AND IT LOOKS EXACTLY LIKE WORK IN PROGRESS

**Measured on 2026-09-21, by the PO looking at the background-task panel and asking
*"some of the tasks are running from few hours? are they valid?"*.** Sixteen tasks were
listed. Two were real lanes, both alive and writing within seven seconds. **Six were
dead** — one at **4h59m**, another at **4h58m**, four more between 59m and 1h11m — and
every one of them was the same shape:

```
until [ -s /tmp/claude-0/rec1-gates.log ]; do sleep 15; done; tail -40 …
```

**All three polled files existed and were ZERO BYTES, and no process was writing to any
of them.** `[ -s ]` is false for an empty file, so the condition could never become true.
The lanes that started these waits had finished; their worktrees and their runs were torn
down with the logs still empty, and the waits outlived them and polled forever.

⚠ **THIS IS CLAUDE.md HARD-WON LAW 7's *INCAPABLE OF PASSING* SHAPE, WITH ONE EXTRA
TWIST THAT MAKES IT WORSE: IT NEVER REPORTS ANYTHING AT ALL.** A gate that cannot pass at
least prints a red line somebody can read. A wait that cannot finish prints nothing,
occupies a slot, and **presents to the reader as a long-running job** — which is
indistinguishable from a slow one. The register already carries the sibling of this:
a lane's own monitor "reported no events" because its completion check also matched a
sibling's `run_gates`, so it never saw its own run end. **Both are a condition that was
true of the world when it was written and stopped being true when something else ended.**

**THE RULE: every wait carries a deadline and says which way it exited.**

```
timeout 1800 bash -c 'until [ -s "$LOG" ]; do sleep 15; done' \
  && echo "LOG ARRIVED"  ||  echo "GAVE UP AFTER 30m — the producer is gone, go read it yourself"
```

Three things it must do, and the third is the one that gets skipped:
* **A DEADLINE**, chosen from how long the thing you are waiting for actually takes —
  not a round number that feels safe.
* **A CHECK THAT THE PRODUCER IS STILL ALIVE**, not only that the output is absent.
  `kill -0 "$PID"` answers it. An absent log and a live writer is *waiting*; an absent
  log and a dead writer is *finished badly*, and they need opposite responses.
* **OUTPUT THAT DISTINGUISHES THE TWO TO A READER** — law 7's habit 3. `BOTH DONE`
  printed by a loop that can only print `BOTH DONE` is not a result.

**AND CLEAN UP AFTER YOURSELF THE WAY THE SECTION ABOVE SAYS:** a lane that records its
PIDs and scopes its kills should also stop its own waits before it reports. The six here
were found only because a human read a panel and asked. **Nothing in this repo counts a
background task that is quietly doing nothing**, which is the same blind spot as a guard
red for days with nobody reading it.

---

## ⚠ A THROWAWAY WORKTREE IS CHEAP — WHEN THE TIP MOVES, DELETE IT AND MAKE A NEW ONE

**Self-reported 2026-09-28 by the New Connect walk lane (`DEF-MET-7804`), after
one of its own commits turned out to be a PURE REVERT of 205 lines.**

Law 11's `commit-tree` push needs a tree whose bytes are *the pinned tip plus
your own hunks*, and on a busy branch the cheapest way to get one is a
`git worktree add --detach <tip>` you throw away afterwards. That much is
right, and this file already recommends the sibling habit for databases and
ports.

**What is NOT safe is keeping that worktree when the tip moves.** The lane ran
`git merge --ff-only` in it; git printed `Updating <old>..<new>` and then did
**not** complete, because `git apply --3way` had left changes staged in that
worktree's index. The tree became a **MIX** — some paths at the new tip, some
at the old — which is exactly the state `DEF-2100` describes and calls the
hardest to reason about. Three of the four files the lane had edited were
silently back at their old content with the edits gone, and the fourth was 205
lines stale.

⚠ **AND `push_paths.sh`'s `REDERIVED_FROM_TIP=1` IS AN ASSERTION THE TOOL
CANNOT CHECK.** It exists for the case where you genuinely just rebuilt every
named path from the tip's bytes, and the refusal that offers it
(`DEF-GOV-4061`) is correct to offer it. **It was true when the worktree was
made and false by the time the push ran.** Every other check in law 11 passed:
the file count was right, `git show` printed only that lane's own hunks, no
suite imported the deleted lines, and nothing went red.

**What found it was the closing `git diff --numstat <tip> <commit>` the script
prints, read AS ARITHMETIC** — `33 205 buildViews.tsx` — which the script's own
message calls *"your only proof"* the moment you pass that flag. Read it. A
deletion count you did not intend is this bug, every time.

**THE HABIT, and it is two lines rather than a tool:**

* **When the tip moves, `git worktree remove --force` and add a new one at the
  new tip.** Never fast-forward a worktree that has anything staged or
  modified. Re-applying a small patch onto a fresh checkout costs a minute;
  reasoning about a mixed tree costs an incident.
* **Re-derive, re-stamp and push in one unbroken sequence.** The version, the
  register rows and the file blobs all go stale together, and the gap between
  "I rebuilt this" and "I pushed it" is the whole of the window this defect
  lives in.
