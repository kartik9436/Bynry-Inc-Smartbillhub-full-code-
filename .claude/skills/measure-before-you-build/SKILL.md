---
name: measure-before-you-build
description: Measure what a module — or one section of one — actually does today against what it was promised to do, and route every difference. This is "step 1". Run it on any module or any slice of one - a tab, a queue, a wizard, a list, an endpoint family, a nightly job, a report, a portal page. Use it BEFORE any build wave is scoped, and again before telling anybody what a screen does. Triggers on - step 1, audit, conformance, as-built, "what's missing in X", "does X match the blueprint", "check X against the design", "what does X actually do", a blueprint or wireframe PDF arriving, any module folder under 04-docs/05-modules. It ENDS WITH NOTHING BUILT, deliberately.
---

# Step 1 — measure before you build

## What this is, and what it is not

**You are measuring a thing that already exists against a thing that was already
promised, and writing down every place they differ.** That is the whole job.

**It ends with nothing built. That is not a failure of the step, it is the step.**
A lane that fixes the first thing it finds stops measuring — and what it stops
measuring is always the part nobody has looked at, which is where the expensive
findings are. The three worst findings this repo has produced were each found
*after* the point a building lane would have stopped.

**It is module-agnostic on purpose.** Nothing below names a module. Run it on
Accounts, on Assets, on Meter Reads, on the nightly bill run, on one tab of one
screen, on one endpoint family. The only thing that changes is §0.

---

## 0 · NAME YOUR SCOPE, AND SAY WHAT YOU EXCLUDED

**Write two sentences before you read anything.**

1. **What is in** — the addresses, the endpoints, the jobs, the tabs. Be concrete
   enough that somebody else could run the same measurement and get the same list.
2. **What is OUT, and why** — and this half is the one that gets skipped.

**An unstated boundary is read as coverage.** If you measure the reads list and not
the estimation dialog, and you do not say so, your document is read as *"the reads
flow has been measured"* and the dialog is never looked at by anybody, ever. It is
now covered by a document that does not cover it, which is worse than being
uncovered.

**End the scope note with: _"Say so if that boundary is wrong."_** The person who
set you going is the only one who can tell you that you cut the wrong line, and
they will not volunteer it unless asked.

**Scope sizes that work:**

| Scope | When |
|---|---|
| A whole module | Nobody has ever measured it; you have a blueprint for all of it |
| One flow inside a module | The module is large and the flow is coherent — a list + its detail + its edits |
| One screen and its tabs | A redesign, a single blueprint section, a bug cluster |
| One endpoint family | The screens are fine and the API is suspect |
| One job or report | It runs unattended, so nobody has ever watched it |

---

## 1 · `ls` THE FOLDER. NEVER GUESS A FILENAME.

**The documentation layout is NOT uniform across modules, and a lane that assumes
it is will report "there is no specification" over a file that exists.**

Measured across the 17 module folders under `04-docs/05-modules/` (excluding
`_templates`):

| File | Present in |
|---|---|
| `01-overview.md` | **17 of 17** |
| `02-business-rules.md` | **17 of 17** |
| `03-field-map.md` | **17 of 17** |
| `04-flows.md` | **17 of 17** |
| `05-user-stories.md` | **17 of 17** |
| `06-epics/` | **17 of 17** |
| `08-screen-layouts.md` | **6 of 17** |
| `wireframes/` | **5 of 17** |
| `conformance/` | **5 of 17** |
| `07-endpoints.md` | **4 of 17** |
| `10-execution-plan.md` | **4 of 17** |

**So five files and one folder are everywhere, and everything drawing-shaped is in
a minority of modules under a name that differs by module.** Metering's drawn
specification is `09-screen-conformance.md`. The portal's is `08-screen-layouts.md`
plus `09-component-inventory.md` plus `12-reuse-map.md`. Neither name appears in the
other's folder.

```bash
ls 04-docs/05-modules/<module>/
ls 04-docs/05-modules/<module>/conformance/ 2>/dev/null
```

**Then look outside the module folder too**, because the promise is scattered on
purpose: `04-docs/01-spec/` (what to build) · `04-docs/02-decisions/`
(how to build, B14 among them) · `04-docs/03-contracts/` (the interfaces) ·
`12-governance/` (rulings, questions, defects, change requests) ·
`05-prototype/r10-2026-08-16/` (the clickable reference).

---

## 2 · IF THERE IS NO DRAWING — DRAW IT, SHOW IT, THEN STOP

**PO ruling, 2026-09-10.** Three acts, in order, and the middle one is the one that
gets dropped.

1. **Extract a drawn specification INTO THE TREE** from whatever you do have — the
   task text, the prototype, the neighbouring screens, the component that is
   already there.
2. **Put it to the PO in plain English and get a yes.** The labels and the row
   order, read as sentences. **Never as an id to go and look up.**
3. **Then, and only then, is there something to measure against.**

**Skipping step 2 is how your guess at a layout becomes the agreed design by
default** — and nobody ever ratified it, so nobody can ever be said to have been
wrong about it.

**A URL is not a drawing. "The design doc" is not a drawing. A drawing nobody in
this tree can open is not a drawing.** If the specification lives in a PDF, a
slide deck or somebody's head, your first deliverable is to get it into the tree
as text somebody can `grep`.

---

## 3 · SAY WHICH KIND OF SURFACE THIS IS — THE BAR IS DIFFERENT FOR EACH

**"I measured it" means five different things and you must say which one you did.**

| Surface | What measuring it actually means | The trap |
|---|---|---|
| **A screen** | It is **clicked**, in a browser, at the real address, with real data | No gate in this repo reads rendered output. `tsc`, eslint, every test and every gate pass over a screen that renders nothing |
| **An API** | It is **called** — the real verb at the real path with a real body, and you read the response | A test with its own fixture proves the fixture, not the server. One screen's fixture was right and the product was wrong for days |
| **A money path** | It is run **on real PostgreSQL**, never the default suite | `config/settings/test.py` hardcodes in-memory SQLite, which has no aborted-transaction state. The broken version passes everything, green, on every machine (law 14) |
| **A job** | It is **run**, and you read what it wrote | Nobody watches an unattended job. Its failure mode is silence |
| **A portal page** | It is opened at **390px** as well as 1280 | Staff screens are laptop-and-desktop only; a customer opens their bill on a phone, and that is the primary case |

**Write down which one you did, and which ones you did not.** A document that says
*"measured"* over a surface that was only read is the same fault as an unstated
boundary, one layer down.

---

## 4 · EXERCISE IT THE WAY ITS USER REACHES IT, AND RECORD WHAT YOU DID

**Reading the code tells you what it would do. Driving it tells you what it does.**

The reading-detail crash that headlined one blueprint was found **by clicking a
meter, in one click**. Every unit test of that screen passed, because every one
supplied its own array fixture over an endpoint that had started answering a paged
envelope. **The fixture was right and the product was wrong**, and no amount of
reading either would have told you.

**"The way its user reaches it" is load-bearing** and it is the half that gets cut:

* **Start where the user starts** — the front page, the menu, the link. Not the URL.
  Two screens in this repo were routed, built, tested and translated in eleven
  languages with **no door**: no menu entry, no link, no button. They open only if
  you type the address. A suite that mounts the screen directly can never see this.
* **Use the real data**, not a fixture. A fixture is a claim about the server.
* **Do the thing the user came to do**, all the way to the outcome — not to the
  point where the form looks right.

**Record the drive as a script, in the tree**, not as a sentence in your report:
`10-scripts/<cr>_<what>_walkthrough.mjs` is this repo's form and there are dozens of
them. A recorded drive is re-runnable by the next lane; a sentence is a claim.

---

## 5 · QUOTE THE PROMISE. NEVER LINK IT.

**The labels, the row order, the exact strings, in your working notes, in front of
you while you measure.** A link gets skimmed. A quote gets compared.

`"Read route"` is not `"Reading route"`. Half of everything filed as *"the screen
doesn't match its design"* is a correct row with a reworded label — and on the
front end that category is **nearly half of everything that goes wrong**.

**Quote it verbatim, never summarised.** A summary is a second artefact that can
be wrong on its own, and this repo has a long record of exactly that: one pointer
to a rule count has been wrong six separate times, always in the same direction,
because ratifying a rule and updating the pointer to it are two acts and only the
first one feels like the work.

---

## 6 · COUNT WHAT IS DRAWN. NEVER A SENTENCE ABOUT IT.

**A specification's prose is not evidence about the specification.** It is another
claim, written by a person, at a different time from the drawing, and it drifts.

Measured on one blueprint in this repo, in one document:

* the **prose** said twelve rows;
* the **caption** under the same figure said eleven;
* the **drawing** drew twelve;
* the document said it carried **21 specifications** and carried **17**.

**Count the drawing. Then say which of the three you counted**, so the next reader
knows what your number is a number OF.

**And a figure drawn in a wireframe is an ILLUSTRATION, never a fact to build to**
— B14 rule 37, ratified 2026-09-10 in the PO's own words. When two frames of one
drawing show the same fact differently, **build the shape they agree on and ignore
both sets of figures.** Do not file a defect for a sample value.

---

## 7 · MEASURE WITH COMMANDS AND PASTE THE NUMBERS

**A figure you counted by reading is a guess wearing a number's clothes.**

This is not a general caution, it is the single most reliable way this step goes
wrong, and the author of this file did it: an account edit screen was reported to
the PO as **7 fields writable and 11 refused**. It is **11 and 34**. Both halves
were wrong and three fields the drawing actually draws were missing from the count
entirely. The correction cost a ruling that had already been written down.

**So: `grep -c`, `wc -l`, a `python3` one-liner, a `curl`, a `getComputedStyle` —
and paste the command beside the number.** A number with its command attached can
be re-run by the next lane. A number without one has to be taken on trust, and this
repo's record says do not.

**Particularly for:**

| Claim | The command that settles it |
|---|---|
| "N fields on this form" | count the DOM, not the interface — `document.querySelectorAll(...)` |
| "the endpoint accepts X" | `curl` it and read the body. A silent accept and a refusal look identical from the client |
| "this spacing is wrong" | `getComputedStyle`, in the browser, at the stated width |
| "N of these exist" | `grep -c` with the pattern printed |
| "it was red before I started" | `git log -S "<the failing symbol>" -- <file>` — see §8 |

---

## 8 · BEFORE YOU WRITE "NOTHING DOES X", GREP FOR X

**An absence is the easiest finding to write and the easiest to get wrong**, because
you are reporting on something you did not find, and *not finding* has two causes.

Two live examples from one week:

* *"There is no adjustments table"* — there was one, with rows in it.
* *"There is no statement template"* — there was one, rendering.
* *"The customers upload door is not scanned"* — the malware middleware is
  **global**; every upload door in the product goes through it. *(True that
  week; the PO removed the scan on 2026-09-22/23 and the middleware is deleted,
  `DEF-SHL-6347` — the lesson about searching for the THING stands.)*

Each of those reached a report. Each was a lane that searched for the name it
expected rather than for the thing.

**So search for the THING under at least three names**: what the screen calls it,
what the table would be called, what the endpoint would be called. Then search for
its consumers. **Then say where you looked** — an absence with no search behind it
is an opinion.

⚠ **And the mirror: before you retire or remove something, grep for its
CONSUMERS.** One retired enum value cost a live screen line that would have
returned null on every account for ever, with `tsc` and every test green. **An
absence is invisible to every check this repo has.**

---

## 9 · ROUTE EVERY FINDING. AMBIGUOUS IS A DEFECT.

**A finding that is not routed is a finding that is lost.** Four destinations, and
the routing decision is yours to make, not the PO's:

| What you found | Where it goes |
|---|---|
| The product **does not do** something it was promised to do | **DEFECT** — `10-scripts/file_defect.py … --id-module <MOD>`, which appends ONE row as raw bytes and refuses to edit |
| The product does what it promised and the **promise should change** | **CHANGE REQUEST** — `12-governance/13-change-process.md`, one file per CR |
| A user **can do the task today** and it is wrong or broken | **MAINTENANCE** — `12-governance/22-product-maintenance-process.md` |
| A user **cannot do the task at all** today | **BUILD** — the r11 process, a story, a wave |
| A fact **only the PO holds** — a price, a deadline, a tax authority's rule | **OPEN QUESTION**, minted and stubbed |

⚠ **WHEN IT IS AMBIGUOUS IT IS A DEFECT, NOT A CHANGE.** This is a ruled rule and
the reasoning matters more than the rule: **filing our own misunderstanding as a
"change" quietly converts our error into the customer's new requirement**, and the
record then says they asked for it.

⚠ **AND BEFORE YOU MINT A QUESTION, GREP FOR IT** (hard-won law 13):

```bash
grep -n -i "<subject>" 12-governance/02-decision-log.md 12-governance/01-open-questions.md
```

Asking the PO something already ruled is not a clarification, it is a bug in us —
and it manufactures inconsistency, because a person answering twice from memory
will eventually answer differently and then the repo holds two genuine rulings
that contradict each other. **The short list of what legitimately reaches the PO:**
a ruling that collides with a signed rule · a frozen finance figure · a fact only
they hold. **Everything else is ours to decide and write down.**

⚠ **AND READ THE STATUS COLUMN, NOT THE BODY.** A closed question's body goes on
describing the open world, and the body is what a lane actually reads. One
question read **CLOSED** in its status column while its own body still said the
feature was unbuilt — and a briefing written from that body nearly deleted a PO
ruling from four documents.

---

## 10 · QUOTE EVERY STATED ABSENCE AND ASK IF IT IS STILL TRUE

**This is the finding nobody is looking for, and it is the one with the shortest
distance to a customer.**

A **stated absence** is the product saying *"this cannot be done"* — a disabled
button, a greyed nav word, a card reading *"opens with the next release"*, a
docstring saying a path is not built, a refusal sentence.

**Every one of them was true when it was written. A share of them is false now**,
because landing the screen and releasing the control that pointed at it are two
acts and only the first one feels like the work.

Measured on the portal front page, 2026-09-05: **two working doors out of eight.**
Five cards, the sign-in bar and three of four nav words were all still refusing
over screens that had shipped days earlier. **42 test files, 391 cases, `tsc` and
every gate passed over it**, because each wave tested its own screen at its own
address and the question *"has the door started pointing at it yet"* belonged to
nobody.

**So: collect every stated absence in your scope into a list, and against each one
write whether it is still true.** Then check the other direction too: a primary
button that renames itself to a disabled *"that path is not built"* over an
endpoint that **is served, and whose own server-side copy tells clerks to use it.**

⚠ **AND WHEN YOU FIND A LIVE HOLD, WRITE THE TEST THAT FIRES WHEN IT EXPIRES** —
asserting the destination **by address and by the screen id it opens** — or the
next lane inherits the same silence.

---

## 11 · NAME WHAT YOU DELIBERATELY DID NOT FILE

**A judgment not to file something is a finding.** Write it down with its reason.

Three things belong here and each is filed wrongly at least once a week:

* **A sample figure in a drawing** — rule 37 says it is an illustration. Not a
  defect. Say you saw it and say why you left it.
* **A difference the drawing and the UI rules disagree about.** Where a drawing and
  B14 disagree about how a **form is built** — side-by-side fields, help text
  placement, footer button order — **the UI rules win** (rule 38). What the form
  CONTAINS is still the drawing's to decide. File the *difference*, follow the rule.
* **A red you did not cause.** Do not swallow it — see §12 — but do not file it as
  yours either.

**And the reverse: a thing you filed that you are not sure about.** Say so in the
row. A defect register that holds only certainties is a register somebody is
editing to look tidy.

---

## 12 · HAND STEP 2 WHAT ONLY YOU KNOW

**Your document is the only artefact of this step.** Whatever is in your head at
the end of it and not in the file is gone — the conversation does not survive, the
repo does.

**Write it to `04-docs/05-modules/<module>/conformance/<CR>-<lane>-step1.md`.** That
is where this repo's step-1 output lives; the folder exists in 5 of 17 module
folders and you create it the first time a module is measured.

**It must carry, at minimum:**

1. **The scope and the exclusion** from §0, verbatim.
2. **The version and commit you measured at** — `2.249.2 · 72f2a823f`. A measurement
   with no version on it decays into an unfalsifiable claim within a day.
3. **Which surfaces you actually drove** (§3) and which you only read.
4. **Every finding, routed, with its id** — the defect number, the CR number, the
   question number. An id cited before it is allocated is its own defect class;
   **cite nothing until the allocator has answered.**
5. **Every number with the command that produced it** (§7).
6. **The stated-absence list with its still-true column** (§10).
7. **What you did not file, and why** (§11).
8. **⚠ EVERY RED YOU DID NOT CAUSE, WITH ITS DATE.** Law 7's first habit. Before you
   finish, look at every red line in the suite and ask *was this red before I
   started?* — **and that is a claim about history, so check it like any other
   claim:** `git log -S "<the failing symbol>" -- <file>` answers it in one command.
   Two lanes once reported the same red in good faith and in almost the same words
   as *"pre-existing, not mine"*, **and the second was the lane that had caused
   it.** Neither ran the command. **Calling a red pre-existing without dating it
   does the exact opposite of what the habit is for**, because it tells every
   subsequent reader not to look.
9. **The ordered list of what step 2 should do first**, and why that order.

**Then stop.** Hand it over. **Do not build.**

---

## The close-out checklist

- [ ] Scope written, exclusions written, *"say so if that boundary is wrong"* asked
- [ ] Folder `ls`'d, not guessed
- [ ] A drawn specification exists in the tree — or you drew one and showed it
- [ ] The surface kind is named, and you drove it the way its user reaches it
- [ ] The promise is quoted, not linked
- [ ] Every count is of the drawing, and says so
- [ ] Every number has its command beside it
- [ ] Every "nothing does X" has a search behind it, under three names
- [ ] Every finding routed; ambiguous filed as a defect; no question re-asked
- [ ] Stated absences listed with a still-true column
- [ ] What you chose not to file is written down
- [ ] Every red you did not cause is named **with its date**
- [ ] Written to `conformance/`, with the version and commit on it
- [ ] **Nothing built**
