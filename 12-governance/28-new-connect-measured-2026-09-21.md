# 28 · New Connect, measured — 2026-09-21

**Written so the next session starts from a measurement rather than a suspicion**, and
because the PO asked for it: *"i want you to do similar excercise for new connect - we
have updated drawring in blueprint for new conenct. do the mapping and start tasks for
Create new Connect + Actions, list view, detaisl view + actions"*.

⚠ **SNAPSHOT.** True at `be42a12fd`, version `2.319.5`. **The registers and the decision
log outrank this file the moment they disagree.** This covers the LIST, the DETAIL and
the ACTIONS; the create wizard was measured by a sibling lane.

⚠ **METHOD.** Blueprint pages **p99–p107** were RENDERED AS IMAGES and read that way
(`B14` rule 42) — the PDF's text layer prints every digit as `&`, so the drawn figures
are legible only as pictures. Every drawn number is an ILLUSTRATION (rule 37) and none
is treated as a requirement. The server's own read functions were run against the live
database. **No browser was opened**, so every *Built* below means built IN THE CODE,
which is not the same claim as *a clerk sees it*.

---

## 0 · THE TWO THINGS THAT DECIDE HOW TO READ THE REST

**(1) THESE PAGES ARE A REDESIGN AND SAY SO THEMSELVES.** Every frame carries a banner:
p99–p100 *"REDESIGN — PUBLISHED 2026-09-12 … NEVER BUILT"*, p100–p104 and p107
*"PUBLISHED 2026-09-17 … NEVER BUILT"*. So the **list** is a real screen with one drawn
addition; the **record and its three actions are drawn for a page that has never
existed.** Building "to the drawing" means building intent, not documenting a screen.

**(2) THE DETAIL SCREEN WAS DELETED ON PURPOSE, AND THIS IS NOT THE DISCONNECTS
SITUATION.** A New Connect detail screen existed for about three weeks. **PO ruling
2026-09-04, verbatim:** *"you are duplicating this — there is nothing called as
connections; Connection = Account only — you cannot have two different screen — this is
an integration problem."* Today a build opens the **property's Build tab** or the
**account's Work tab**; the old address forwards. Measured: **all nine builds in the
demo tenant resolve.** The blueprint drawn thirteen days later draws a six-tab page
anyway. **That collision was `OQ-MET-12520`.** ⚠ **IT IS NOW CLOSED — PO ruling
2026-09-21, AND THE ANSWER IS NEITHER OF THE TWO READINGS THIS PARAGRAPH OFFERS.**
The PO chose option C, verbatim: *"Your ruling's words were 'you cannot have two
different screen' — that's about duplication, not about the content. The drawing
isn't asking for a duplicate; it's asking for completeness we don't have."* **So:
⛔ NO SECOND SCREEN AT ITS OWN `/connections/…` ADDRESS — the 2026-09-04 ruling
STANDS and is not superseded — and the property's Build tab gains what the six
drawn tabs carry, AS SECTIONS.** Pages 100–107 are stamped ONE DESTINATION rather
than wrong: they remain the **content** contract, and only their ADDRESS and their
TAB STRIP are superseded. A lane building from them takes what each tab shows and
**not where it lives**. ⚠ **AND IT STILL DOES NOT UNBLOCK BUILDING** — §2's four
measured stoppers are untouched by it. The register row and `02-decision-log.md`
§1 of 2026-09-21 are the authority; this line is only the snapshot.

---

## 1 · THE LIST — a real screen, and better than its sibling

**Route** `/:tenant/accounts?tab=new-connects`, drawn p99–p100.

Ten tabs in the drawn order · five KPI tiles all built · nine drawn columns all built,
**including `WAITING ON`, which the blueprint calls "the addition" and which is already
here** · server-applied filter · server pagination.

⚠ **TWO OF THE THREE FAULTS FOUND ON THE DISCONNECTS TAB ARE ABSENT HERE, AND SAYING SO
IS THE POINT — a conformance pass that only reports faults teaches the wrong lesson.**

* **The search prompt is TRUE.** It offers *"Connection #, premise, address, applicant,
  or request #…"* and the server searches connection number, premise number, premise
  name, address line, request number and applicant name — five promises, six legs. On
  Disconnects the prompt offered a case number the query never searched.
* **The row action OPENS.** It is an eye glyph rather than the drawn `↗ Open` button,
  which is `B14` rule 15 winning over the drawing on how a control is BUILT (rule 38),
  and it resolves for every build.

**Absent:** `⇩ Export` (nothing on the server can export connections — not drawn dead,
which is correct) · the four one-click chips, folded into the filter panel a level down
· the sub-line's `N open` fragment · the two grey explanatory paragraphs, which are
RATIONALE and are zero words on screen by rule 33.

---

## 2 · THE FOUR THINGS THAT MAKE THE DRAWN RECORD MOOT UNTIL THEY ARE FIXED

⚠ **EACH IS MEASURED, NOT INFERRED. Everything pages 100–107 draw is a picture of what a
completed build leaves behind — and no build has ever completed here.**

### 2.1 · NOTHING CAN BE ACTIVATED, AT ALL
`connections.transition_service` is the **only** code in the product that can set a
service to *activated*, and **nothing in the front end calls it.** Searched three ways:
for a control by name, for the word in any form, for the request shape. Every
`transitionService` hit belongs to *service requests*, a different thing.

A build's state is COMPUTED from its services, so **a build can never reach "Activated"
or "Partly activated" through the product.** The four builds in the database showing
those states are **seeded sample rows**; the only real build anyone has made is a draft.

### 2.2 · THE COMPLETION PATH HAS NEVER RUN
Counted from `audit_log`: **nine `connection created`, eight `submitted`, ZERO
`committed`.** All nine connections carry no quote total and no owner account; all 39
work orders record no source, so none was raised by a build.

⚠ **AND THE REASON IS A CHECK-THAT-DOES-NOT-CHECK, WHICH IS WHY IT MATTERS BEYOND THIS
MODULE:** the wizard's commit door answered *not found* from the day the wizard shipped
until 2026-09-16, and **both test suites stayed green the whole time, because each one
tested its own side of the gap.** Hard-won law 7's fifth shape — a check reporting
truthfully over a scope it silently excludes.

**So §4's manifest is written, reviewed and real, and it has never executed here.**
Prove it end to end against a real build before anything is drawn on top of it.

### 2.3 · THE GATE THE ACTIVATE DIALOG IS BUILT AROUND IS READ BY NOTHING
Blueprint p105 is titled *"Activate units — and the gate that stops it"* and refuses
every unit with *"gate not passed"* or *"no meter"*. `work_orders.is_gate` is **written,
stored and printed — and read by nothing that refuses anything.** No check, no guard, no
refusal message. Hard-won law 1: a label is not the guarantee it names.

### 2.4 · AN EXECUTIVE IS SHOWN EIGHT BUTTONS THEY ARE REFUSED ON
The server allows System Admin and Billing Clerk every build action and gives Executive
**read-only**. The Build tab does **no role check at all** — no access-cell lookup
anywhere in `buildViews.tsx`. So an Executive sees eight live, pressable controls and is
refused on every one.
⚠ **THE CONTRAST IS WHAT MAKES IT A DEFECT RATHER THAN A GAP:** the list's own
`+ New connect` **is** role-aware and greys out with its reason. One page family, both
behaviours.

---

## 3 · THE ACTIONS — the drawing wants three, the product has eight, and they disagree

| Drawn | Built |
|---|---|
| **Activate units** (p105) — the terminal act | ⛔ **no control anywhere.** §2.1 |
| **Edit details** (p107) — one live field, four locked | ⛔ **no endpoint exists.** Nothing edits a committed build anywhere in the product; the drawing's own banner says so. Its one drawn-live field, *Waiting on*, IS live — just not in a dialog |
| **Add a work order** (p106) — a dialog with type, scope, due, method, and a gate tick | **Partial and misleading** — the Build tab's button asks nothing and posts a hard-coded `Meter set` / `water` order. The real wizard is on the Work orders tab |
| — | Hold · Release · Cancel · Waiting-on · Mark outstanding work · Close an item · Accept a finished job — **all live, none drawn** |
| — | **Add service** — posts a hard-coded `water`, no picker |

### The endpoint census — 25 mounted, 17 called, **8 with no door**
Searched twice for each: once for the wrapper by name, once for the raw address as a
hand-built string. The eight: **create a draft build · commit by id · transition a
service (the only way to activate anything) · submit · name the owner account · tag the
payer · set a unit's pricing characteristics · `GET /connections/{id}`.**

⚠ **THREE OF THOSE EIGHT ARE EXACTLY WHAT THE DRAWN DIALOGS ASK FOR** — name the payer,
set the pricing inputs, activate a service. **The work is done on the server and there
is no button.**

⚠ **AND `GET /connections/{id}` IS A FINISHED 26-BLOCK READ ANSWERING ALL SIX DRAWN
TABS, BUILT FOR THE SCREEN THAT WAS THEN DELETED.** Its wrapper exists and has zero
callers. **It also now tells a lie:** it still publishes *"The charges for this build are
held as a single quoted total. The lines behind it were never raised as bills"* — untrue
since 2026-09-16, when the quote began posting as a real bill. The commit path deleted
that sentence; the read kept it **and a test pins it in place.** Nobody sees it because
nothing calls the read — and the day somebody builds the drawn Plan & charges tab, it
draws **a false absence on a money screen.**

---

## 4 · WHAT A COMPLETED BUILD ACTUALLY DOES — one transaction, all or none

Address created or named · **units** created · **meters** created through the assets
seam · **plan assignments** written BEFORE the account, because an account on an
unpriced unit is refused · the owner's account opened (opt-in) · the owner's master
account at the address (opt-in, idempotent) · **work orders** raised from templates ·
**the quote priced and posted as a real bill**, its total written back · **balanced
ledger pairs written only by the ledger posting service** · **audit rows for the money
act** · three letters attempted · the build stamped submitted with a manifest audit row
· the state recomputed.

**Absent from it:** ⛔ **the deposit** — the PO ruled on 2026-09-16 how an owner pays
every unit's deposit, all or none, never a transfer, and **nothing is built**; the code
comment still calls that question OPEN while the register says CLOSED, which is this
repo's stale-body trap on a money path · sub-meter links, honestly reported as *"we
cannot make them from here"* rather than as zero · a first bill · **an account per unit
as each unit goes live**, which p99 promises and nothing does.

**No background jobs.** Searched the commit path and everything it calls: every step is
synchronous.

**Messages: 373 queued product-wide, ZERO connections among them, and not one message
of any kind has ever been sent.** `connection` is not one of the fourteen things a
message may be about, so all three letters are refused BY NAME and the commit reports
honestly that it queued none. That is `OQ-NOT-12521`, OPEN. **Queued is not sent, and
answering that question delivers nothing on its own** — there is no provider adapter for
any channel.

---

## 5 · WHAT TO PUT IN FRONT OF THE PO, IN ORDER

1. ~~**`OQ-MET-12520` — does the six-tab record get built at all?**~~ ✅ **ASKED AND
   ANSWERED 2026-09-21 — DO NOT PUT IT AGAIN (law 13).** The PO chose **one
   destination, made complete**: no second screen at a `/connections/…` address, and
   the property's Build tab gains the six drawn tabs AS SECTIONS. See §0(2).
2. **Nothing can be activated** — §2.1. A build cannot be finished through the product.
3. **An Executive is shown eight buttons they are refused** — §2.4. One access check.
4. **The completion path has never run** — §2.2. Prove it before drawing on top of it.
5. **The deposit ruled on 2026-09-16 is not built.**
6. **Eight finished endpoints with no door** — §3.
7. **The unused read carries a money sentence that stopped being true on 2026-09-16, and
   a test holds it there.**
8. **`OQ-NOT-12521` — may a connection letter be filed?**

## 6 · WHAT THIS MEASUREMENT DID NOT CHECK

**No browser was opened.** Neither the app nor the API was running, and starting them
would have collided with six live lanes. Every *Built* is built in the code. Where
something is reported ABSENT it was searched for under at least three names, and the
search terms are named above rather than left implied — a lane here once concluded
*"move-in has no runner"* because its filename pattern was wrong, and reported the shape
of its pattern as a fact about the product.

---

# PART TWO · THE CREATE WIZARD — measured the same day

⚠ **METHOD, AND ONE CORRECTION TO EVERY CITATION IN OUR OWN CODE.** The eight New
Connect screens are on blueprint pages **92–99**. **The eight step files cite pages
87–92** — about five pages early — so a person following our own citations opens the
wrong drawing. The screens were found by LOOKING at rendered images, not by trusting a
number. ⚠ **This is the blueprint page-shift compounding**: the 2026-09-21 update
inserted two pages at 69–70, so every citation at or above p69 was already off by two
before this was measured.

**These pages are a REDESIGN too** — *"PUBLISHED 2026-09-11 … NEVER BUILT"* — and they
say the product has NINE steps. **It has eight, and so does the drawing**: the merge
landed after publication, so on step COUNT the product has already caught up.

## THE STEPS MATCH — eight drawn, eight built, seven named identically

The one difference is **deliberate and ruled**: step 5 is drawn *Plans & work orders*
and built *Work orders*, because the PO ruled on 2026-09-16 that the plan is chosen
earlier. It moved to step 2 and the name moved with it. **The drawing still shows the
plan on step 5**, so a lane building from the drawing alone would move it back.

## 1 · THE THREE THAT WOULD STOP A REAL BUILD TODAY

### 1.1 · ⛔ NO BUILD MADE THROUGH THIS WIZARD CAN EVER RAISE A CHARGE — a money path
`newConnectDraft.ts:618` **always** sends the application reference EMPTY, and the
wizard has no door from an application. The server's first test when pricing the quote
is *does this build have an application?* — so it always answers no. **The payer choice,
the payment terms and the posting date that step 6 collects are read by NOTHING, ever.**
⚠ **THE MONEY PATH ITSELF IS SOUND AND WAS PROVED ON A REAL INVOICE** — it simply cannot
be reached from this screen. Measured: **not one of the nine connections has a quote
total, and not one has an owner account.**

### 1.2 · ⛔ UNTICK "INCLUDE A COMMON-AREA UNIT" AND THE BUILD CANNOT BE CREATED
The commit always opens the owner's account when a name was typed — and step 1 refuses
to continue WITHOUT a name. The account door refuses outright when the address has no
common-area unit: *"has no common area to bill the owner through. Add one, or bill the
unit."* **So a single house, or any build where the clerk unticks that box, is refused
AFTER ALL EIGHT STEPS.**

### 1.3 · ⛔ STEP 4 OFFERS ELEVEN SERVICES; THIS UTILITY SELLS TWO
The tick list is a HAND-TYPED list of all eleven platform services and the line above
reads *"N of 11 available at this address."* The demo utility has **electric and water
enabled and nine disabled**, so **nine of eleven tick boxes cannot commit** — refused at
the door with *"gas isn't one of the services this utility bills."*
⚠ **AND STEP 2 ASKS THE SAME QUESTION WITH A CONTROL THAT CORRECTLY OFFERS ONLY THE
TWO.** One field, two controls, two lists. This is `CLAUDE.md`'s hard-won law 2 in its
front-end form and `B14` rule 43's reason for existing.

## 2 · THE ONE THAT IS NOT NEW CONNECT'S — IT IS ALL FIVE WIZARDS

⛔ **`?step=8` OPENS THE REVIEW ON AN EMPTY DRAFT WITH `Create connection ✓` LIVE.**
The wizard hands the frame `{ step, reached: step }` on every render
(`NewConnectWizard.tsx:246`) and the step is read from the address bar, clamped only to
1–8. **A fence EXISTS — `clampStepToReached` — and this wizard never calls it.** A
whole-front-end search finds only the sign-up and tax wizards using it.
⚠ **ALL FIVE CUSTOMER-FLOW WIZARDS SHARE THE HOLE**, and the disconnect wizard's
`?step=5` finding is the same defect seen from the other end. **It is ONE fix in ONE
place, not five** — which is the only reason it is worth stating as a single line rather
than five register rows.

## 3 · WHERE NEW CONNECT IS GENUINELY BETTER, AND SAYING SO IS THE POINT

* **THE COMMIT IS ONE TRANSACTION.** `connections.py:4210` opens a single
  `transaction.atomic()` around both halves; nested services become save points. **No
  `try/except` anywhere on the path, deliberately** — catching a database error and
  carrying on loses the work on PostgreSQL anyway and passes green on our SQLite suite
  (hard-won law 14). A test proves a refused build leaves no address behind. **The
  disconnect flow's two-writes-with-no-transaction problem does not exist here.**
* **REFUSALS REACH THE CLERK.** `connections.py` raises **38** distinct refusals and
  **36 carry an English sentence** the clerk reads, with every answer still on screen —
  *"500 Main St offers electric, water, not gas. Add it on the premises first."*
  **The disconnect wizard collapses all twelve of its refusals into the same eleven
  generic words**, so this is the same product doing the same job two ways.
  ⚠ **THE TWO WITHOUT A SENTENCE ARE BOTH MONEY-PATH** — the quote's posting-date format
  check and its price-drift refusal — and both are **missing from all eleven language
  files**, so a clerk sees a raw internal code on a money screen.

## 4 · FIVE MORE, EACH MEASURED

* ⛔ **A REAL ROW IS STRANDED.** Approving a new-connect application creates a Draft
  build. **`CON-26-0129` at 500 Main St exists right now — real, not sample, created
  today, no units, no services, no work orders.** The tab's link opens the account or
  the premises, never the wizard. **No screen in the product can finish it.**
* ⛔ **FIVE CONTROLS ON THE UNITS GRID DO NOT TRAVEL** — occupancy, asset type, size,
  install date and work order per row. All render, all default, all changeable, **none
  is in the payload**, which carries only the unit label, the service and a blank
  serial. **The PO asked for these on 2026-09-16.** The whole-build occupancy on step 8
  IS sent and the server reads it nowhere.
* ⛔ **THE SUCCESS SCREEN PRINTS THE SERVER'S ENGINEERING NOTES VERBATIM** — three
  paragraphs, **126 words**, one ending *"a tolerated key with no consumer is
  DEF-MET-4715."* **A defect number on a clerk's screen**, against `B14` rule 32 and
  against the PO's own August ruling that server detail text may not reach a screen.
* ⛔ **A PICKED ADDRESS SILENTLY LOSES ITS SERVICE LIST.** Choosing an address already on
  file copies street, town, state and ZIP and **not** the premise type, parcel, route,
  building name or **what services that address offers** — and the whole address block
  is dropped before it reaches the server. **So on a picked address the clerk's service
  ticks are a local fiction**, and every meter is refused at commit.
* **31% OF THIS WIZARD CANNOT BE TRANSLATED** — **73 of 238 text keys are absent from
  all eleven language files, English included**, so they render from English written
  into the code. **The commit button itself, the failure title, and every heading on
  steps 3, 4 and 8** are among them.

## 5 · VALIDATION THAT LIVES ONLY ON THE SCREEN — four, and one is a rule

* **A build with no units** — the screen blocks it, the server accepts it and writes
  nothing.
* ⚠ **SEWER WITHOUT WATER** — the screen refuses it and **there is NO SUCH RULE ON THE
  SERVER**; the whole backend was searched for it. An integration posting directly gets
  a sewer connection with no water. **That is a business rule living in a browser.**
* **Scope must be chosen** — screen only; the server ignores the field entirely,
  because `connections` has no scope column at all.
* **The owner's identity** — genuinely enforced on both sides.

⚠ **AND THE MIRROR IS HERE TOO:** the front-end tests assert the screen's own constants
back to themselves. **Nothing anywhere compares a front-end list to the server's.** That
is exactly `DEF-CUS-6023`'s escape reason, in a second module — so it is a repo-wide
shape and not a disconnect quirk.

## 6 · FOR THE PO, NOT FOR US

**Step 8 reads *"Units energise one at a time."*** The PO asked in August for
**activated**. The drawing says **energise**. Our own ruling says **activated**. A lane
may not settle a word the PO has already ruled on — it goes back to them.

## 7 · WHAT PART TWO DID NOT CHECK

**No browser.** Everything about layout and what a clerk sees is read from the drawing
and the code. The test suite was not run — it writes under the backend directory and six
lanes hold those files. Search terms are named above rather than implied.
