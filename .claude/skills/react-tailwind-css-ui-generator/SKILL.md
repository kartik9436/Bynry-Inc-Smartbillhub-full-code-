---
name: react-tailwind-css-ui-generator
description: Build or change any screen, component, tab, table, form or piece of UI in this repo's React/Tailwind front end (07-frontend), and turn a wireframe into a pixel-perfect implementation of it. Use it BEFORE writing the first line of TSX, and again before calling the screen done. Triggers on - build a screen, add a tab, add a column, add a field, change a label, wire a route, "match the design", "make it look like the wireframe", "pixel perfect", any S### or CWP-### screen id, any work under 07-frontend/src/pages, /components or /i18n.
---

# Building a screen in SMARTBillHub

## What this file is for

Two halves, and you need both.

**Part A is the craft** — how a wireframe becomes a screen that actually looks like
it. Generic, and written out rather than assumed.

**Part B is this repository's traps.** They matter because **every way this repo gets
screens wrong passes `tsc`, passes eslint, passes every test, and passes every
gate.** That is not bad luck, it is the shape of the problem: no gate here reads
rendered output. Measured over the nine days to 2026-09-09, of 1,140 defects filed:

| share | what it was |
|---|---|
| **26.5%** | a check that does not check |
| **17.4%** | wrong logic — the code runs and answers wrongly |
| **16.8%** | the written record is wrong or overtaken |
| **10.8%** | **the screen does not match its design** |
| **7.8%** | the words are wrong — wording, a missing key, an untranslated string |
| **6.5%** | built but not wired — a dead control, a key nothing renders |

⚠ **THOSE FIGURES WERE FIRST QUOTED AS *32% SCREEN, 6% LOGIC* AND BOTH WERE WRONG
(corrected 2026-09-10, the day they were written).** They came from bucketing a free-text
column by keyword, twice, by two different readers, who disagreed by twenty points. The
counted figures above come from the register's twelve-value vocabulary.
**10.8% IS STILL THE REASON THIS FILE EXISTS, and the honest way to say it is this:
only 23.9% of defects touch the front end AT ALL, so a screen not matching its design
is 124 of the 273 front-end defects — NEARLY HALF OF EVERYTHING THAT GOES WRONG ON A
SCREEN.** A share of the whole register understates it; a share of the front end does
not.

**Read Part C's never-do list before you start, not after you finish.**

---
---

# PART A — FROM WIREFRAME TO SCREEN

## 1 · START FROM THE DRAWING, NEVER FROM THE PROMPT

**A sentence about behaviour is not a specification for a screen.** On 2026-09-09
the property Overview shipped with three rows missing, four labels different and one
column drawn as two — every suite green — because five waves each added one row from
a task sentence, and the layout lived only in a page no lane could open.

**Find the drawn specification IN THE TREE before anything else:**

* **the module's own drawings** — every module folder under `04-docs/05-modules/`
  carries them and the filenames differ by module. Look for a screen-conformance
  file, a screen-layouts file, a component inventory, a reuse map. Metering's
  `09-screen-conformance.md` and the portal's `08-screen-layouts.md` +
  `09-component-inventory.md` + `12-reuse-map.md` are the worked examples —
  **`ls` the module folder rather than guessing a filename**;
* the clickable reference — `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`
  (layout, copy, flows and states only — **never port its runtime**).

**A URL is not a drawing. "The design doc" is not a drawing. A drawing a lane cannot
open is a drawing that will not be built.**

### ⚠ 1.1 · LOOK AT THE PICTURE. EXTRACTED TEXT IS AN INDEX, NOT THE DRAWING

**PO ruling, 2026-09-13, verbatim:**

> *"When you use images to create screens your accuracy is higher; hence dont
> create screens using only Text"*

**So: render the blueprint's pages as IMAGES and READ THEM WITH YOUR EYES.** The
extracted markdown under a module's `blueprint/` folder is an INDEX — it tells
you which screen is on which page and lets you grep — and it is **not** the
specification. Build from the image; use the text to cross-check spelling and to
find your page.

**This is not a preference, and the repo already proved it before the PO said
it.** `CR-094`'s own step-1 record reads *"54 pages read as IMAGES at scale 2,
never from the text layer"*, and another says *"prose quoted from the text layer"*
is the unreliable half. **The wireframes are VECTOR ART.** A text extractor
returns the labels and silently loses everything that is DRAWN rather than
written:

| survives extraction | lost, and only the image has it |
|---|---|
| field labels, values, headings | which fields sit SIDE BY SIDE vs stacked |
| the words of a button | what is a TABLE and what is a list of facts |
| a sentence of help text | column widths, alignment, what lines up with what |
| the order of lines in one column | which of two columns a block is in |
| | grouping rules, emphasis, relative weight |
| | where a control sits inside its heading |

⚠ **AND IT LOSES SCREEN BOUNDARIES.** In the Accounts blueprint the extractor
gives screens 09 and 10 the SAME starting page, and 16 and 17 the same — it could
not tell where one screen ends and the next begins. A lane reading only text
cannot know that; a lane looking at the page can see it in a second.

**How to render, in this container.** `pdftoppm`/poppler will not install, `PIL`
times out and `pypdf` crashes on a broken `cryptography` build — which is why
`10-scripts/pdf/` exists and why you must not reach for any of them:

```bash
mkdir -p <outdir>                                   # the script does NOT create it
python3 10-scripts/pdf/pdf_render.py <file.pdf> <outdir> 2 60,61,62
#                                    ^file        ^out  ^scale ^pages
```
Scale **2** gives 2448x1584 and is what earlier lanes used; go to **4** for a
dense table you cannot read. Then open each PNG with the **Read** tool — that is
the whole point of the ruling.

⚠ **THE BLUEPRINT PDFs LIVE ON THE DEFAULT BRANCH, NOT ON A WORKING BRANCH.**
Six of them. Get one out without switching branches:

```bash
git ls-tree -r --name-only origin/<default-branch> -- 05-prototype | grep -i pdf
git show "origin/<default-branch>:05-prototype/<name>.pdf" > /tmp/<name>.pdf
```
`git remote show origin | grep "HEAD branch"` names the default branch. **A lane
that reports "the drawing is not in the repo" has looked at one branch** — that
mistake was made in this project on 2026-09-13 and corrected by the PO.


**QUOTE the drawing into your working notes — do not link it.** The labels, in order,
in front of you while you type. A link gets skimmed; a quote gets built.

### If no drawn spec exists in the tree — PO ruling, 2026-09-10

**Draw it, show it, then build. In that order, and the middle step is not optional.**

1. **Extract a drawn spec INTO THE TREE** from whatever you do have — the task text,
   the prototype, the neighbouring screens, the existing component.
2. **Put it to the PO in plain English and get a yes** — the labels and the row
   order, read as sentences. **Never as an id to go and look up.** One round trip, and
   it stops your guess at a layout becoming the agreed design by default.
3. **Then build to it.** The drawing is now what the close-out diffs against.

---

## 2 · READ THE WIREFRAME BEFORE YOU BUILD IT

**Do not start typing at the top-left of the picture.** Decompose it first, in
writing. This takes ten minutes and it is the difference between a screen that
resembles the design and one that matches it.

### 2.1 Inventory it — write this list out

Go through the wireframe and record, in order:

* **The header** — kicker, title, subtitle. What does the back arrow say it exits to?
* **The actions** — every button, **in the order they appear**, with its exact label
  and which is primary, secondary or danger.
* **The tabs**, in order, and which is default.
* **The tiles / stat cards** — how many, what each is called, and the detail line
  under each number.
* **The fact rows** — for each: the **exact label**, the value, and where the value
  comes from. Row order is part of the design, not a detail.
* **The tables** — every column, in order, its alignment (text left, numbers right),
  and what a row's actions are.
* **The footer** — pagination, totals, wizard actions.
* **The states** — empty, loading, error, and every refusal with its exact sentence.

**Copy the strings verbatim.** *"Read route"* is not *"Reading route"*. Half the
"screen doesn't match" defects in this repo are a correct row with a reworded label.

### 2.2 Separate chrome from data

Mark each element as **chrome** (frame, labels, structure — always present) or
**data** (comes from the API, may be absent, may be long, may be zero).

Every data element needs an answer for: **what does this look like when it is empty,
when it is loading, when it fails, and when it is ten times longer than the sample?**
A wireframe shows one happy row. Real data is not one happy row.

### 2.3 Find the repetition

Anything that appears more than once is a component, not a copy-paste. Anything that
already exists in the kit is a component you must not write again.

### 2.4 Read the rhythm, not the pixels

Look at the gaps between things. They are almost never arbitrary — they are a small
set of values repeating (a spacing scale). Identify the scale rather than measuring
each gap. Same for type: a handful of sizes and weights, used consistently.

### 2.5 Write down what is ABSENT

An absence is a decision. If the wireframe has no delete action, no export, no
secondary tab — that is the design, not an oversight for you to fill in. If you
believe something is missing, **say so; do not add it.**

---

## 3 · BUILD IT IN THIS ORDER, AND ONLY THIS ORDER

Each step is finished before the next begins. Styling a structure you have not
settled is how a screen ends up held together with absolute positioning.

**1 · Semantic structure, no styling at all.**
Get the right elements: a `<button>` for something that acts, an `<a>` for something
that navigates, a `<table>` for tabular data, a `<label>` bound to every input,
real heading levels in order. **A clickable `<div>` is a defect** — it is invisible
to a keyboard and to a screen reader. Look at it unstyled: it should still read as
the right document.

**2 · Layout.**
Flex for one-dimensional rows and columns, grid for two-dimensional arrangements.
**Never absolute positioning to fake a layout**, and never a fixed pixel height on
anything that holds text.

**3 · Spacing, from the scale.**
Use the scale's steps. If a gap seems to want a value that is not on the scale, the
answer is the nearest scale value — not an arbitrary one. Consistent rhythm is what
reads as "designed"; a one-off value reads as a mistake even when it matches the
wireframe more closely.

**4 · Type, from the scale.**
Sizes and weights from the system. **No inline font sizes** — this repo once had six
different table font sizes and five different button font sizes on screens that were
all supposed to be one.

**5 · Colour, from the tokens.**
Never a raw hex. If the colour you need is not a token, you are either using the
wrong token or the design needs a new one — and a new token is a decision, not
something to inline.

**6 · States, all of them.**
Default · hover · **focus-visible** · active · disabled · loading · empty · error ·
the refusal. A screen with only its default state is a third of a screen.

**7 · Responsive, last.**
Build at 1280, then check 390. Narrow layouts **stack**; they do not shrink. A row of
four tiles becomes one column, not four tiny tiles. Nothing scrolls sideways.

---

## 4 · WHAT "PIXEL PERFECT" ACTUALLY MEANS HERE

**It does not mean eyeballing pixels. It means matching the SYSTEM** — the same
tokens, scale, components and states the design was drawn from. Two screens built
from the same system match each other automatically; two screens eyeballed against
pictures drift apart the moment anything changes.

**So the check is a structured comparison, not a squint.** Put the wireframe and the
running screen side by side at the same width, and compare in this order — stop and
fix at the first difference, because a missing element makes every later comparison
meaningless:

1. **Presence** — is every element from your §2.1 inventory actually on the screen?
2. **Order** — rows, columns, tabs, actions, in the drawn sequence?
3. **Labels** — every string, character for character?
4. **Alignment** — do things line up on the same edges as the drawing?
5. **Spacing rhythm** — same relative gaps, from the scale?
6. **Weight and size** — heading vs label vs value, same hierarchy?
7. **Colour and state** — including hover, focus and disabled?

**Where the wireframe and the design system disagree, the system wins** — and you
**file the difference** rather than silently following either one.

---

## 5 · MODAL OR SCREEN?

⚠ **THIS IS ALREADY RULED, AND IT IS RULED AS A DELIBERATE NON-RULE.** B14 rule 30
proposed *"a form that does not leave the user's current context opens in a DIALOG"*
and it was **DECLINED on 2026-08-30.** The PO answered the INSTANCE and not the
rule — *"for estimate reads - keep it modal"* — and in the same sentence said of
rule 31 *"that is a rule"*, so the contrast is deliberate. The number 30 is left
unused on purpose. **Do not re-raise it, and do not invent a rule in its place.**

**What B14 says to do instead: follow the estimate precedent** — three fields, one
outcome, returns to the list it was launched from — and note that **there is nothing
here for a gate to check.**

So the test, read off that precedent:

| Use a **MODAL** when ALL of these hold | Use a **SCREEN** when ANY of these hold |
|---|---|
| a handful of fields | it needs an address a person can send or bookmark |
| one outcome | it must survive a refresh |
| it returns to the list it was launched from | more than one step, or more than one outcome |
| nobody needs to link to it | it holds a table or a list of its own |
| losing it on refresh costs nothing | someone would want to come back to it later |

* **Always a dialog:** a destructive confirm — disconnect, retire, reverse,
  write-off — using the shared `ConfirmDialog` with the **danger tier**.
* **Never** open a modal from inside a modal.
* **If your case does not resemble the estimate precedent, ASK.** Deciding it
  yourself is how a non-rule quietly becomes a rule nobody ratified.

---

## 6 · RESPONSIVE — AND WHO IT IS ACTUALLY FOR

⚠ **PO ruling, 2026-09-10, and it is an AUDIENCE split rather than a screen-size
rule.** Verbatim: *"Calrk and Utility admin is laptop, and desktop application - not
mobile; COnsumer can be both mobile and other screen sizes"*, and on scope: *"we dont
have to do evertyhing right now - whenever we touch those screen skills MD should
talk about it"*.

| Who the screen is for | What is required |
|---|---|
| **Clerk · utility admin — the staff app** | **Laptop and desktop. NOT mobile.** Build it at desktop width and stop. Do not spend effort making a staff table work on a phone; nobody uses it there |
| **Customer — the portal** | **Mobile AND every other size.** A customer opens their bill on a phone, and that is the primary case rather than an edge one |

**Scope: this is NOT a retrofit programme.** Nothing existing is being swept. **The
rule applies to the screen you are touching, when you touch it** — which is why it
lives in this file rather than in a migration plan.

### THE EXACT SIZES — approved by the PO, 2026-09-10

**Two numbers do all the work: `390` and `1280`.** Everything between them is the
layout stretching; everything above `1280` is the container capping. A screen that is
right at both ends almost always survives the middle.

**The breakpoints below are Tailwind's own defaults on purpose** — `md` 768, `lg`
1024, `xl` 1280 — so none of this needs a custom config, and a lane reaching for
`md:` gets the agreed number without looking it up.

#### Staff app — clerk · utility admin

| Headline | Width | What it means |
|---|---|---|
| **Wide desktop** | **1920** | Must not break. Content is CAPPED AND CENTRED rather than stretched — a 1,900px-wide table row is unreadable |
| **Desktop — THE DESIGN TARGET** | **1440** | **Build here.** It is the laptop most staff have, and it is the width B14's own toolbar measurement uses: *~1,360px of controls in the ~1,150px a 1,440px laptop gives you* |
| **Laptop minimum** | **1280** | **Everything must work here.** No clipping, no horizontal scroll, every control reachable |
| **Below 1280** | — | **NOT SUPPORTED, DELIBERATELY.** Spend no effort. If it scrolls sideways on a small screen that is an accepted outcome, not a defect to file |

#### Customer portal

| Headline | Width | What it means |
|---|---|---|
| **Phone — THE DESIGN TARGET** | **390** | **Build here first.** A customer opens their bill on a phone; that is the primary case, not an edge one |
| **Large phone** | **430** | Must work. No new layout — the 390 layout with more room |
| **Tablet portrait** | **768** (`md`) | The first layout change allowed. One column may become two; cards may become a table |
| **Tablet landscape · small laptop** | **1024** (`lg`) | Full layout available |
| **Desktop** | **1280+** (`xl`) | Content capped and centred. **A portal page is not a staff page** — it does not fill a 1920 screen |

#### What you actually verify

| Interface | Verify at | Ignore |
|---|---|---|
| **Staff** | **1280 and 1440** | Anything narrower |
| **Portal** | **390 and 1280** | Nothing — those two are the mandatory pair |

⚠ **THESE TABLES DESCRIBE WHERE WE ARE GOING, NOT WHERE WE ARE.** The stylesheets
already hold **10 max-width rules at 760, 899, 900, 1024, 1100 and 1440** — existing
behaviour at widths that appear in neither table. **Nothing is being swept**: under
the ruling above, those get looked at when somebody touches that screen. Do not go
hunting them, and do not "fix" one in passing.

### For a customer-facing screen

Design at desktop width, then **verify at 390px** — the width the portal
walkthroughs use.

* **Stack, never shrink.** Four tiles become one column, not four tiny tiles.
* **A table does not become a small table.** Either it becomes cards, or it scrolls
  sideways **inside its own container** — the page body never scrolls sideways.
* **Nav collapses to something that fits.** On 2026-09-05 the portal menu measured
  **461px inside a 390px phone**, on every signed-in page.
* **Every control must be reachable at both widths.** Nothing exists only when wide.
* **Touch targets are finger-sized**, not mouse-sized.

⚠ **None of this is a ratified B14 rule — it is our method, written down.** If it
should become binding UI law with a rule number, that is a separate act and it needs
the PO to rule it in.

---
---

# PART B — THIS REPOSITORY'S TRAPS

## 7 · THE PRE-FLIGHT — FIVE CHECKS, TWO MINUTES, EVERY TIME

### 7.1 ⚠ Is your file on the migration ledger? — and what actually happens if it is not

**⚠ THIS SECTION STATED THE WRONG MECHANISM UNTIL 2026-09-12 — corrected by PO
ruling, verbatim: *"Yes correct it"* (`DEF-GOV-5102`).** It said a Tailwind
utility is emitted ONLY for a file on `07-frontend/src/styles/route-b-migrated.txt`
and that one written elsewhere "renders as nothing at all". **It renders fine.**
`src/styles/tailwind.css` imports the utilities with `source(none)` and then
declares `@source "../"`, so the compiler scans the whole of `src/`. Measured
against the built stylesheet: of ten utilities each used in exactly one UNLISTED
file, **ten of ten are emitted as real rules.**

**WHAT THE LEDGER ACTUALLY GATES IS WHICH CHECKER OWNS YOUR FILE**, and its own
header says so:

* **listed** → `routeBUtilities.test.ts` owns it and asks the STRICTER question:
  every class token must either compile through the real Tailwind compiler or be
  declared by a stylesheet. `g31_declared_classes.py` skips it.
* **not listed** → `G31` owns it and demands that every class be **declared by a
  `.css` file**. A utility is not, so **G31 goes RED at merge.**

**So the cost of a utility in an unlisted file is a red gate, not an invisible
element — and the fix is to ADD THE FILE TO THE LEDGER**, never to reach for a
stylesheet class. Reaching for the class is what rule 21 forbids, and it is what
the wrong version of this paragraph talked three lanes into doing.

```bash
# Which checker owns your file? (a hit = the stricter test owns it)
grep -n "pages/YourScreen.tsx" 07-frontend/src/styles/route-b-migrated.txt
```

**THE INVISIBLE-CLASS TRAP IS REAL, IT IS JUST A DIFFERENT ONE**, and it is what
`DEF-SHL-5088` and `DEF-SHL-5100` cost on three live screens on 2026-09-12: a
utility whose NAME the theme does not define (`text-danger` where the tone is a
scale, `bg-surface-muted` where no such key exists, a bare `rounded` where every
radius is 0) compiles to nothing, and so does an arbitrary value naming a custom
property nothing declares — that one worse, because it compiles to a real rule the
browser then drops. **`tsc` passes, eslint passes, and
`expect(el.className).toContain("text-danger")` passes, because the class
genuinely IS in the DOM.** `routeBUtilities.test.ts` catches both, on listed files
only — so on an unlisted file nothing does.

```bash
grep -n "pages/YourScreen.tsx" 07-frontend/src/styles/route-b-migrated.txt
```

* **A NEW screen or component → PUT IT ON THE LIST** and write it in Tailwind,
  adding no class to any stylesheet. The ledger holds new files as well as migrated
  ones, for the same reason: it names classes no stylesheet declares. ⚠ **Add the
  line and migrate the file in the SAME commit** — a line added without the file
  actually being in Tailwind turns the vitest check red.
* **An existing file already on the list** → Tailwind utilities, as above.
* **An existing file NOT on the list** → **reuse a class the stylesheet already
  declares.** That adds nothing either. **Do not migrate someone else's file as a
  side effect of your change** — a migration is its own work with its own proof.

### 7.2 Does the component already exist?

```bash
ls 07-frontend/src/components/          # 45 components today
```
`DataTable`, `Button`, `Chip`, `ChipMultiSelect`, `ConfirmDialog`, `ConsequenceBox`,
`CustomFields`, `AppShell` and the rest are the kit. **A second table, a third button
size or a bespoke dialog is a defect, not a contribution.**

### 7.3 Do your catalogue keys exist — in all eleven languages?

```bash
ls 07-frontend/src/i18n/locales/        # de en es es-MX fr-FR hi id-ID it-IT ja-JP ko-KR pt-BR
```
**A missing key reaches a clerk as SILENCE, not as an error.** 21 live refusals were
found rendering as nothing, while the gate that checks this truthfully reported
**0 unresolved** — of everything it could see.

### 7.4 Is there already a rule about this?

`04-docs/02-decisions/14-ui-conventions.md` is **B14 — the binding UI rules.**
**Read the file, never a summary of it, and never a count of it.** The count in
`CLAUDE.md` has been wrong five separate times, always in the same direction,
because ratifying a rule and updating the pointer to it are two acts and only the
first feels like the work. **Read the status column** before assuming a rule is
checked — most are RATIFIED and UNENFORCED.

### 7.5 What does the screen already do?

Read the current component before changing it. Half the "screen doesn't match"
defects are a row that was already right, reworded by someone who never saw it.

---

## 8 · BUILD FROM THE KIT

**Layout and detail come from the captured pack. Visual style comes from
`05-prototype/r10-2026-08-16/UI-RULES.md`. The shared component kit is how you comply
with both.** (B14 rule 36 — found by the PO looking at four shipped screens, not by
any check.)

The handful worth holding in your head, because they are the ones that get broken —
**the rest are in B14 and B14 is the authority:**

* **One page header** — kicker, title, optional subtitle. Every screen, including
  task pages and workflows.
* **Two button sizes only**, default and small. No inline font sizes.
* **Button grammar:** `+ Noun` opens a creator · `Verb →` navigates · `Verb ✓`
  commits · `↑` imports.
* **Danger tier** on destructive commits — disconnect, retire, reverse, write-off.
* **Row actions are ICONS with tooltips, never text links.** Max 2 visible, then `…`.
* **Every list table** carries the toolbar, the pagination footer and an empty state.
* **A row of controls holds only things a person can PRESS.** A status, an age, the
  reason a control is disabled — those are FACTS and belong elsewhere.
* **Money displays to 2 decimals**, however many it is stored to.
* ⚠ **`Panel` IS THE INFORMATION GROUP ON A DETAIL SCREEN** — a box, 1px border on all
  four sides, surface fill, 16px padding, heading inside. **145 files already use it.**
  A detail screen that rules its groups off with a top border instead is the shape
  `R4` was raised against: the reading detail had `SECTION = "…border-t border-divider
  pt-3.5"` and imported no `Panel` at all. **Not every group is a Panel** — a notice or
  a banner is not an information group, so read the drawing for which is which.
* **`StateFrame` gives you loading · empty · failed · denied.** Every list AND every
  detail needs all four; a screen with only the happy path is half a screen.

---

## 9 · COPY — THE CAPS ARE HARD LIMITS

* **A description budget: one sentence per section.** A stated absence is a
  `<details>` **closed** by default. Said four times in twenty minutes: *"too much
  content - desctiption is too much for clark to read"*.
* ⚠ **ON-SCREEN TEXT IS CAPPED BY WHAT IT IS FOR — FIVE CAPS, NOT ONE.** This line
  read *"a refusal sentence caps at five or six words"* until 2026-09-14, which is the
  paraphrase `CLAUDE.md` itself flags as wrong in three ways: it names a kind **rule 33
  does not have**, gives ONE cap where there are FIVE, and drops the clause that bites
  hardest. The rule:
  * a **LABEL** or heading — **≤ 3 words**, no sentence
  * a **FACT** — **≤ 6 words**
  * an **INSTRUCTION** — **≤ 6 words PER SENTENCE**, and *two sentences of six beat one
    sentence of twelve*
  * a **CONSEQUENCE** before an irreversible act — ≤ 6 words per sentence, **at most
    two**, and **never cut below clarity**
  * **RATIONALE — why the product works this way, why a control is absent, why a rule
    did not fire — is ZERO WORDS ON SCREEN.** It belongs in the code and the register.
  ⚠ **RATIONALE IS REMOVED, NOT SHORTENED.** Cutting a *why* sentence to six words keeps
  the breach and makes it terser. **Read the rule in B14, never this summary.**
* ⚠ **AND THE WORKING TARGET IS TIGHTER — PO ruling 2026-09-14, verbatim: *"reduce the
  content to 5 to 6 meaningful words"*.** Said of three drawn warnings measured at 13, 19
  and 18 words on the running product. Worked, from that screen:
  *"The new value becomes current. This reading stays in the history."* (11) →
  **"New value becomes current. Old one kept."** ·
  *"The account is not served on a reading; open it through the unit."* (13) →
  **"Open the account through the unit."**
* **Nothing internal is ever visible** — not a database id, not a rule number, not a
  path, not an OQ or DEF id.
* **One pair of words for *held here* and *in the books*: `Recorded` and
  `In the books`.** Everywhere, in all eleven catalogues.

---

## 10 · EVERY STRING THROUGH THE CATALOGUE

No hardcoded user-visible text. Ever. And **a catalogue is written in its own
language, not translated from English** — PO, verbatim: *"it sound like local person
language and not mechanical translations of English"*.

After adding keys, confirm every one of the eleven files has them. A key present in
`en.json` and missing elsewhere is a blank space on a real screen. **And leave room:
the same sentence is longer in German than in English, which is why nothing that
holds text gets a fixed height.**

---

## 11 · WIRE IT, THEN PROVE THE DOOR OPENS

**Built is not wired.** A component with an optional prop nothing passes is dead UI:
it renders nothing and every test passes.

**And the mirror costs more, and no gate can see it:** a *live* screen behind a
*dead* control. On 2026-09-05 the customer portal's front page had **two working
doors out of eight** — five cards, the sign-in bar and three of four nav words were
all still refusing over holds whose screens had shipped days earlier. All 42 test
files and 391 cases passed, because each wave tested its own screen at its own
address and *"has the door started pointing at it"* belonged to nobody.

* **Land the screen AND release the control that was holding it, in the same commit.**
* **When you write a hold, write the test that fires when the hold expires** — assert
  the destination by ADDRESS and by the screen id it opens.
* ⚠ **Mount routed components under the real path pattern.** A bare `MemoryRouter`
  with no `/:tenant/...` route leaves `useParams().tenant` undefined, so every URL the
  page builds comes out `//portal/…` — a protocol-relative URL to another host, which
  reads as a perfectly good string to `toContain`.

---

## 12 · NEVER HAND-TYPE A LIST

Services, statuses, steps, badges — derive them. The service list is typed by hand in
**two** places, so an eleventh service does not appear on screen on its own **and it
fails silently**: the row exists, the API serves it, `tsc` and every test pass, and
the sign-up screen simply never offers it.

Before adding a list to a screen, ask where else the same list is typed out.

---
---

# PART C — WHAT NOT TO DO, AND HOW TO CLOSE

## 13 · NEVER DO ANY OF THIS

**Styling**
* ❌ **Arbitrary values** — `mt-[13px]`, `w-[347px]`, `text-[15px]`. Use the scale.
* ❌ **Inline `style={{…}}`** to position or size anything.
* ❌ **A raw hex or rgb colour.** Tokens only.
* ❌ **`!important`**, in any form.
* ❌ **A new font size, radius, shadow or colour** invented for one screen.
* ❌ **A fixed pixel height on anything containing text.**
* ❌ **Absolute positioning to achieve a layout** that flex or grid should do.
* ❌ **Adding a class to a stylesheet** for new UI (B14 rule 21).

**Components**
* ❌ **A second table, dialog, dropdown or button variant** when the kit has one.
* ❌ **Copying the prototype's JavaScript.** Layout, copy, flows and states only.
* ❌ **A clickable `<div>` or `<span>`.** Use a `<button>` or an `<a>`.
* ❌ **An input without a bound `<label>`.**
* ❌ **Removing the focus outline** without a clearly visible replacement.

**Content**
* ❌ **A hardcoded user-visible string.**
* ❌ **A database id, rule id, path, enum code or internal reference on screen.**
* ❌ **Inventing a label** because the drawing did not have one — ask.
* ❌ **Adding a control the drawing does not show** because it seemed useful.
* ❌ **Filling an empty state with placeholder or sample data.**

**Getting to green**
* ❌ **`any`, `@ts-ignore`, or disabling a lint rule** to make something pass.
* ❌ **Editing a baseline, allow-list or carried set** to turn a check green.
* ❌ **Skipping, disabling or quarantining a test.**
* ❌ **Claiming a screen is done because the suite is green.** It is not the same
  statement, and this whole file exists because of the gap between them.
* ❌ **`git add -A`, `git add .`, `git commit -a`, `git stash`** — a shared tree, and
  each of those has eaten another lane's work here.

---

## 14 · HOW A RULE ACTUALLY GETS OBEYED

**Start with the honest number, because it decides everything else: B14 holds ~37
ratified rules and only a handful are machine-checked** — button sizes, native
selects and the chevron, table font sizes, and search placeholders. B14 says so about
itself: *"most are RATIFIED and UNENFORCED, because no gate in this repo reads
rendered output."*

**So "it adheres because the gates would have caught it" is false, and reasoning that
way is how a screen ships not matching its design.** Adherence is three tiers, and you
owe all three:

| Tier | What it covers | What you do |
|---|---|---|
| **1 · Machine-checked** | The handful above, plus the Tailwind class check | Run the gates. **Read the output — not the exit code** |
| **2 · Source-checkable** | A prop is passed · a placeholder key exists · a route is registered · a catalogue key is present in eleven files | Write the assertion. It cannot tell you the sentence is TRUE, only that it exists |
| **3 · Only a person can see it** | Layout, order, labels, alignment, spacing, hierarchy, colour, state — **nearly half of everything that goes wrong on a screen** | The walkthrough in §15. There is no substitute and there is no tool |

**And when you find a rule that is not being followed:**

* **File it.** A defect row, with what you saw.
* **Do not fix it silently** in a commit about something else — the record is how the
  next lane knows.
* **Never widen a baseline, allow-list or carried set to go green.** That converts a
  true finding into a permanently invisible one, and it is the single most damaging
  move available to you in this repository.

---

## 15 · CLOSE IT OUT

### How much close-out — PO ruling, 2026-09-10

**A one-word label fix and a new screen do NOT get the same close-out.** A copy fix
that needs a ceremony is a rule people go around, first for small things and then for
medium ones.

| What you changed | What closes it |
|---|---|
| A new screen · a new row, column, tile or tab · anything that moves layout · a new control | **The full close-out below.** No exceptions |
| **Copy only** — a label, a sentence, a placeholder, a translation, with no layout moved | **The short check:** the string renders where it should, **in all eleven catalogues**, at **both widths**. That is all |

**If you are not sure which it is, it is a layout change.** The expensive defects all
arrived looking like copy.

### The full close-out

**This is the only check in the repository that reads rendered output, and it is a
person.** Hard-won law 6 — *"diff the running app against the prototype: nine defects
were found this way and by nothing else"* — is the one law with no tool behind it.

A screen is done when:

- [ ] every **drawn label** is present, spelled exactly, **in the drawn order**
- [ ] the tiles are the drawn tiles; the columns are the drawn columns
- [ ] the §4 comparison was walked top to bottom: presence, order, labels, alignment,
      spacing, weight, colour and state
- [ ] it was walked in a **browser** against a booted stack — not a green suite
- [ ] walked at **1280 and 390**
- [ ] the **refusals** were exercised, not only the happy path
- [ ] the **empty, loading and error** states were seen, not assumed
- [ ] it was re-run **over its own leftovers**, not only a fresh seed
- [ ] the door that opens it works, from where a person would actually click
- [ ] a keyboard alone can reach and operate every control

Write it as a walkthrough — `10-scripts/*_walkthrough.mjs` has 34 worked examples — so
the next change re-runs it instead of re-remembering it.

**"The feature works" is not the statement. "It is the screen we agreed" is.**

---

## 16 · WHEN THE DRAWING AND THE SPEC DISAGREE

**r10 is right and the spec is stale.** A1–A17 were extracted from prototype r9,
which has been deleted, so the spec describes screens that can no longer be opened.

**File it, don't follow it, and don't fix it in passing.**

---

## 17 · BEFORE YOU PUSH

- [ ] my file is on `route-b-migrated.txt`, or I used no Tailwind utility
- [ ] no new component the kit already had; no new stylesheet class
- [ ] no arbitrary values, no inline styles, no raw colours
- [ ] every string in all eleven catalogues
- [ ] no database id, rule id or path visible on screen
- [ ] the route, the nav entry and the link that opens it all exist
- [ ] tests mount under the real path pattern
- [ ] walked in a browser at both widths, against the drawing, row by row
      (copy-only change → the short check instead)
- [ ] ⚠ **`npx tsc --noEmit` was capable of FAILING when I ran it.** In a worktree with
      no local `node_modules` it fetches a newer TypeScript, aborts on a config error, and
      **reports no type errors at all** — a clean run over an unchecked tree. Symlink or
      install first, then plant a deliberate type error, watch it fail, remove it. Six
      lanes were one message away from reporting a green that meant nothing.
- [ ] **every new guard proved RED before green, IN THE HARNESS THAT WILL RUN IT** — a red
      proof through a path nobody uses is no proof of the thing that matters, and
      `--dry-run` often cannot fail at all (it skips the write the bug lives in)
- [ ] **I read every red line in the suite and dated the ones I did not cause**
      (`git log -S "<the failing symbol>" -- <file>` answers it in one command — two
      lanes have reported a red as "pre-existing, not mine" when one of them had
      caused it forty minutes earlier)
