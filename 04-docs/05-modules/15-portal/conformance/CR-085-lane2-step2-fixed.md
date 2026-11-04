# CR-085 step 2 · lane 2 · **THE GUEST ENTRANCE, FIXED** — what changed, measured before and after at 390 and 1280

**Written 2026-09-11** by the CR-085 step-2 guest lane, from `56ddf02fa`.
This is the AFTER of **`CR-085-lane2-findings.md`** beside it, which is the same
lane's step-1 measurement and is the specification this work was built to. Read
that one first; this one is what moved.

**Ten routes, all under `/:tenant/portal/`:** the landing page · `/sign-in` ·
`/enrol` · `/forgot-password` · `/track` · `/report` · `/visit` · `/visit/:slug`
· `/help` · `/help/:slug`.

---

## 0 · How this was measured, and the one thing step 1 could not do

**Every figure below was read off a browser** — Chromium via `playwright-core`,
at **390 and 1280, both, every route**, against a bundle built from this lane's
own tree and served by a second copy of `07-frontend/server.mjs` on `:8412`,
proxying `/api` to the same backend the shared stack uses. The shared stack on
`:8401` was not restarted, rebuilt or re-seeded.

⚠ **TWO TENANTS, ON PURPOSE, AND STEP 1 HAD ONLY ONE.** `pine-hill` has help
answers, service centres, an emergency number and office hours all published;
`brazosbend` has **none of them**. Every empty state in this lane can only be
seen on the second, and step 1 reported three screens as *source only* because
it looked for them on the first. Both were walked end to end this time.

**The walk is a file, not a memory:**
`10-scripts/cr085_lane2_guest_walkthrough.mjs`. It re-runs, it fails loudly, and
it carries the two checks nothing else in the repo can make — *how many
emergency bands does this page have* and *does this screen respect the portal's
on/off switch*.

⚠ **IT WAS RUN BOTH WAYS, WHICH IS THE ONLY REASON ANY FIGURE HERE IS WORTH
READING (hard-won law 7).** The walk ran in full **BEFORE** these fixes and
every check in it was seen RED on the code as it stood — the off-switch table in
§2, the two-band count in §3, the staff panel in §4, the empty-vs-no-match
collapse in §5, the *Postcode* strings in §6, the 12 and 16 in §7 and the live
*Continue* in §9. It then ran again after, on a bundle built from this tree, and
reports **235 checks green**. The BEFORE and AFTER columns below are those two
runs.

⚠ **AND TWO REDS IN THE FIRST AFTER PASS WERE THE HARNESS, NOT THE PRODUCT — SAID
OUT LOUD RATHER THAN QUIETLY RE-RUN.** `/track` at 390 reported *exactly one h1 —
saw 0* and *exactly one emergency band — saw 0*, with **no `[data-screen]` in the
document at all**, while the identical route at 1280 passed and the same route on
the other tenant passed at both widths. `waitUntil: "networkidle"` is not *the
page is drawn*: on an SPA the last request can finish a frame before React
paints. The walk now waits for the mark every portal screen carries before it
reads, because a red that means *the harness was early* is worse than no check —
the next reader cannot tell it from a real one.

⚠ **THE OFF SWITCH IS EXERCISED BY REWRITING THE RESPONSE, NOT BY SWITCHING A
TENANT OFF.** `is_live` lives in one row of `portal_settings` on a stack six
lanes share; turning it off would take the portal down for all of them. The
gate under test is the CLIENT's, so the walk intercepts `public/front` and
hands the client the payload a switched-off utility actually sends. **What that
cannot prove is the server half — see §2.**

---

## 1 · The eight rows, and where each one stands

| Row | What it was | **Now** |
|---|---|---|
| `DEF-CWP-4851` | nine of ten routes ignored the portal's on/off switch | **FIXED** — §2 |
| `DEF-CWP-4852` | no emergency band on the landing page or `/sign-in` | **FIXED, AND NOT BY THIS LANE** — §3 |
| `DEF-CWP-4853` | a staff error panel with *Download error report* on three public screens | **FIXED** — §4 |
| `DEF-CWP-4854` | *"Nothing here matches what you typed"* said to somebody who typed nothing | **FIXED** — §5 |
| `DEF-CWP-4855` | the portal asks a North American for their *Postcode* | **PARTIALLY FIXED** — four guest keys moved, three screens are other lanes' — §6 |
| `DEF-CWP-4856` | B14 rule 39's field anatomy | **FIXED for this lane's five forms** — §7 |
| `DEF-CWP-4857` | `CPB-24` would print a catalogue key to customers | **FIXED BY NARROWING THE SPEC** — §8 |
| `DEF-CWP-4858` | `/enrol`'s Continue live over three empty required fields | **FIXED** — §9 |

**And two rows this lane FILED rather than fixed**, because each belongs to a
layer this lane does not own:

| Row | Why it is not fixed here |
|---|---|
| `DEF-CWP-4937` | two identical emergency bands, stacked, on `/report` — half of it is fixed here and the residue is a `GuestFrame` decision (§3) |
| `DEF-CWP-4938` | the SERVER still answers six guest endpoints at a switched-off utility (§2) |

---

## 2 · `DEF-CWP-4851` — the off switch, and the copy of one file with one line missing

### What it was, measured

With `is_live:false` on the wire, at **390 and at 1280**, one route at a time:

| Route | Before | After |
|---|---|---|
| `/` | ✓ the holding page | ✓ |
| `/sign-in` | ✗ **a live sign-in box** | ✓ the holding page |
| `/enrol` | ✗ **the whole three-step enrolment wizard** | ✓ |
| `/forgot-password` | ✗ **a live password-reset mailer** | ✓ |
| `/track` | ✗ the full lookup form | ✓ |
| `/report` | ✗ the full report form | ✓ |
| `/visit` | ✗ the full list of counters | ✓ |
| `/visit/:slug` | ✗ one counter in full | ✓ |
| `/help` | ✗ the full answers screen | ✓ |
| `/help/:slug` | ✗ one answer in full | ✓ |

### The cause, which is the part worth writing down

`guest/GuestPage.tsx` has read the switch since wave C and says so in its own
docstring — *"A utility that switched the portal off and still served
`/pine-hill/portal/start-service` would have turned nothing off."*
`signin/SignInPages.tsx` held a private `GuestPageFrame` that was **that
component byte for byte minus the `is_live` line**, and five other pages
composed `GuestFrame` directly.

⚠ **THE DUPLICATE READ AS DILIGENCE.** It is short, it is correct about
everything it does do, and the missing line is invisible unless you diff it
against the file it was copied from. **So the fix is a deletion** — the copy is
gone and all nine screens compose `GuestPage` (B14 rule 36).

### The half that is about the WIRE rather than the SCREEN

The four content reads — `help`, `help/:slug`, `service-centres`,
`service-centres/:slug` — now carry `enabled: live`. A switched-off portal draws
the holding notice **and asks the server for nothing**. Those are two different
statements and only the first is about what a visitor sees; without the second,
a page would hide its own screen and still pull the utility's help articles over
the wire. It matters most on `/help/:slug`, where opening an answer is an EVENT
the back office counts (`CP-34`) — a switched-off portal would have been logging
*read this month* against a utility whose customers cannot reach the page.

### ⚠ AND THE SERVER HALF IS NOT FIXED AND IS NOT IMPLIED FIXED

`apps/portal/guest_api.py` reads `is_live` in **exactly two places** —
`_quick_pay_is_on` and `_requests_are_on`. Six guest endpoints answer normally
on a switched-off tenant: `reports`, `track`, `help`, `help/{slug}`,
`service-centres`, `service-centres/{slug}`. `CR-068` R8 as this module's own
execution plan states it is *"off means unreachable **and** refused"*, and only
the first half is true of those six. **Filed as `DEF-CWP-4938`**, and the new
test file says so in its own header rather than letting a passing client suite
imply the server is covered.

### Why nothing caught it

**71 test files and 960 cases were green** on the morning this was measured.
Every one of the ten screens was tested — at its own address, against a fixture
whose `is_live` is true, because that is the state a screen is interesting in.
The question *does this screen respect the switch* belonged to no suite at all.
That is `DEF-CWP-3925`'s shape one layer down. The cure is the same:
**`src/portal/guest/guestOffSwitch.test.tsx` walks the WHOLE SET**, so a route
added later either appears in that table or is visibly missing from it — and it
carries the mirror case, because every assertion in it also passes on a guest
surface that renders nothing at all.

---

## 3 · `DEF-CWP-4852` — the emergency band was fixed by lane 1, and this lane found the duplicate it left

⚠ **THIS ROW IS CLOSED AND THIS LANE DID NOT CLOSE IT.** Step 1 measured the
landing page on `brazosbend` and reported *"no band, no phone number and no
danger tier anywhere"*. That was true and the reason was not the one recorded:
**`brazosbend` has published no emergency number at all**, and `BR-CWP-093`'s
*no phone, no band* is the correct answer to that. Lane 1 landed
`GuestFrame.EmergencyBand` in the same CR, above the children on every
signed-out screen.

Measured on `pine-hill` at 390 and 1280: **every one of the ten guest routes
carries exactly one emergency band**, the landing page and `/sign-in` included.

⚠ **AND FIXING IT CREATED A SECOND DEFECT ON THE ONE SCREEN THAT ALREADY HAD A
BAND.** `/report` drew its own above the page head from the 2026-09-08 safety
fix, so a tenant with a number published got **two identical red panels,
stacked**, on the most dangerous screen in the product. The screen's band is now
the **fallback** for the one case the frame deliberately leaves empty — no
phone, no band — where *ring the number on your bill* and *Do not use this form*
are the half only this screen can say.

**What that costs, stated rather than left to be found:** on a tenant WITH a
number the sentence *"Do not use this form."* no longer reaches `/report` at
all. The frame's band ends at `portal.emergency.anyHour`, correctly, because
that tail is wrong on `/sign-in` where *this form* is the sign-in box. Restoring
it everywhere is a frame decision. **`DEF-CWP-4937`**, open.

---

## 4 · `DEF-CWP-4853` — a 404 is an EMPTY, and three public screens read it as a failure

`GET portal/public/service-centres` answers **404 on purpose** when the utility
shows no counter (`BR-CWP-093`, `US-CWP-074` TC-5): the server refuses the page
rather than serving a heading with nothing under it. Correct on the wire. Three
screens handed it to `FailedWithRetry`, the STAFF panel, and what a member of
the public in `brazosbend` saw at both widths was:

```
Failed
We could not open this page.
We could not find that. It may have been removed, or the address may be wrong.
[ Retry ]  [ Download error report ]  Cancel
```

— **outside the `GuestFrame` entirely**, so with no utility name, no phone
number, no nav and no door out.

**Three things were wrong at once and all three are fixed:**

1. **The tier.** A 404 is now told apart from every other status by
   `isApiError(error) && error.status === 404`. **Empty** says what is absent;
   **failed** says the read did not work and offers the retry an empty state
   must not. Both are `PortalState`, the same card, different sentences — R-22
   as the PO ruled it.
2. **The frame.** All three screens render inside `GuestPage`, so the utility's
   name, its nav, its emergency band and its footer survive a refused read.
   `PortalScreen` puts the page head — and the `data-screen` mark, and the
   `← Where you can walk in` back link — on **every** branch.
3. **The way out, beside the message (R-10).** `/visit` with no counters now
   draws the utility's own phone as a `tel:` link inside the state card — which
   is the drawing's `NONE CONFIGURED` state in one sentence: *"Falls back to the
   phone number rather than an empty page."* `/visit/:slug` and `/help/:slug`
   each offer the list they belong to.

⚠ **`Download error report` appears on none of the ten routes at either width
on either tenant** — counted in the browser, once per route per width, and
asserted absent four more times in `GuestEmptyStates.dom.test.tsx`. The component
that drew it, `@/components/StateFrame`'s `FailedWithRetry`, is no longer
imported by either screen file.

---

## 5 · `DEF-CWP-4854` — three facts, three sentences, and a rail that names a person

The blueprint's `NO ARTICLES` state is one sentence — *"Falls back to the phone
number and email — **never an empty search box**"* — and all three of its
clauses were broken. On `brazosbend`, where `GET portal/public/help` answers
`{"answers":[],"topics":[]}`, a customer got an empty search box, a chooser with
one option (`All`), and **"Nothing here matches what you typed."**

**What the screen says now, and it is a three-way split rather than a two-way
one:**

| State | Sentence | Furniture |
|---|---|---|
| still reading | *Finding the answers…* | — |
| the utility has published none | **No answers are published here yet.** | no search box, no chips — neither can undo it |
| the visitor narrowed it | **Nothing here matches what you typed.** | box and chips stay, plus **Show every answer** |
| the read failed | *We could not load the answers.* | **Try again** |

`narrowed` is the honest test — a typed word or a chosen chip is the visitor
having asked for less. Without one, an empty list is the **utility's** absence
and no control on the screen could undo it, so the controls that can only ever
answer *nothing matches* do not render at all.

**And the rail.** `Still stuck?` said *"Call us or come in and someone will go
through it with you."* and named nothing to call or come in to on a tenant that
had published neither a number nor hours. The sentence now follows the facts:
with a number, the call is offered, the number is bold under it and **the hours
are under that** — the drawing's own reason being that *"a number without hours
produces a call to a closed office and a second call tomorrow"*. With none, it
says where the number actually is: on the paper bill. One panel, composed by
both help screens, so the two cannot drift into two spellings of *ring us*.

⚠ **THE EMAIL ADDRESS THE DRAWING ALSO ASKS FOR IS STILL ABSENT, DELIBERATELY.**
No endpoint serves one — `public/front` carries a phone and an hours string and
nothing else — so a line naming an inbox would be a sentence stating a fact the
product does not hold.

---

## 6 · `DEF-CWP-4855` — the word a North American reads, and the narrowing that keeps B14 rule 35

**Changed, in `en.json` only:**

| Key | Before | After |
|---|---|---|
| `portal.enrol.postcode` | Postcode of the service address | **ZIP code of the service address** |
| `portal.postcodeHelper` | Just the postcode, not the whole address. | **Just the ZIP code, not the whole address.** |
| `portal.track.secondFact` | Postcode, or the phone number you gave us | **ZIP code, or the phone number you gave us** |
| `portal.quickPay.postcode` | Postcode of the service address | **ZIP code of the service address** |

⚠ **THE OTHER TEN CATALOGUES WERE NOT TOUCHED, AND THAT IS THE RULING RATHER
THAN AN OMISSION.** They already carry their own language's right word —
*Postleitzahl*, *código postal*, *CAP*, *CEP*, *पिन कोड*, *郵便番号* — and B14
rule 35 says a catalogue is written in its own language, not translated from
English. Pushing an English acronym into ten of them would break a ratified rule
to fix a defect that exists in one. **This is `CPB-24`'s shape in the other
direction: a change stated as *"everywhere"* that is only correct in one place.**

⚠ **`portal.quickPay.postcode` IS `/pay`, WHICH IS ANOTHER LANE'S SCREEN, AND IT
WAS CHANGED ON PURPOSE.** `portal.postcodeHelper` is shared between `/enrol`
and `/pay`; moving it alone would have left `/pay` reading *"Postcode of the
service address"* over the helper *"Just the ZIP code…"* — one screen
contradicting itself, which is worse than the defect. The two moved together.
It is copy only, no layout moved, and no source file of that lane's was touched.

**Still open on the row:** `portal.addAccount.postcode` and
`portal.myDetails.postcode` (signed-in screens, no key shared with this lane) and
`settings.portal.switch.quick_pay.sub` (the staff side). `08-screen-layouts.md`
was corrected on all three of its drawn lines.

---

## 7 · `DEF-CWP-4856` — the third figure of rule 39's field anatomy, on the five guest forms

Lane 1 closed the two figures a shared component can own — **label → input 5**
and **input → helper 6** — and said in its own close-out that *field → field* is
20 only where the kit's `TwoUp` is the container, naming five screens that stack
their fields in a container of their own. **Three of those five are this lane's.**

Measured with `getComputedStyle` on the running app, at **390 and 1280**,
before and after:

| Screen | field | before | after | anchor |
|---|---|---|---|---|
| `/sign-in` `CWP-015` | `portal-email` → `portal-password` | **12** | **20** | 20 |
| `/enrol` `CWP-016` | `enrol-account` → `enrol-postcode` | **12** | **20** | 20 |
| `/enrol` `CWP-016` | `enrol-postcode` → `enrol-lastname` | **12** | **20** | 20 |
| `/track` `CWP-012` | `cwp012-reference` → `cwp012-second-fact` | **16** | **20** | 20 |
| `/report` `CWP-006` | `cwp006-where` → `notes` → `photo` → `TwoUp` | **16** | **20** | 20 |

⚠ **`Card` WAS NOT MOVED, AND THAT IS THE POINT.** `/report` and `/track` read
16 because their fields are direct children of the kit's `Card`, whose gap is
the scale's BLOCK step — correct for blocks, and the container of every guest
screen's main column. Changing it would move panels, consequence boxes and
button rows on screens four other lanes own. The field stack gets a wrapper of
its own at the field figure, which is what `TwoUp` already is one level down.

The three `gap-3` containers on `/sign-in` and `/enrol` were the scale's
*inside a block* step (12) against a 6px helper — a ratio of 1 : 1.2 : 2.4 where
the rule asks for **1 : 1 : 4**.

---

## 8 · `DEF-CWP-4857` — `CPB-24`, narrowed before it was executed

The specification says of **both** `portal.held.card` and
`portal.held.signIn` that they *"sit in all eleven catalogues and are rendered
by **no source file at all**"*, and that done looks like *"the two keys are gone
from all eleven catalogues and no screen changes, because nothing rendered
them."*

**Checked, at the tip:**

* `portal.held.signIn` — **true.** Eleven catalogues, no call site anywhere in
  `07-frontend` or `06-backend`. **Retired**, through
  `10-scripts/i18n_fanin.py retire`, which is the tool that owns those files.
* `portal.held.card` — **false.** `FrontPageView.tsx:237` draws it under
  *What things cost*, whose `CR-068` R3 hold is still correct because the public
  prices screen is genuinely unbuilt. The live landing page reads *"Opens with
  the next release."* under that card right now.

`t()` answers a missing key **with the key**. Executing the spec as written
would have printed `portal.held.card` to customers **in eleven languages** — the
exact defect `G27` exists for. **One key retired; the other stays until its
screen lands.**

---

## 9 · `DEF-CWP-4858` — the one guest form that let an empty submission spend a try

`/enrol` step 1 matches on three facts, all printed on the paper bill
(`BR-CWP-030`), and `BR-CWP-036` gives it three attempts before a
fifteen-minute lock — which the screen's own rail states two inches away.
*Continue →* was a bare `WorkingButton` with **no guard at all**: measured at
both widths, pressable with every box blank.

It is `CommitButton` now, with `ready` and a reason, which is what `/report` and
`/track` already compose — so the refusal reads the same words as the other two
forms rather than being a fourth opinion. New key
`portal.enrol.notReady` = *"Fill in all three boxes."*, eleven languages.

⚠ **`/sign-in` AND `/forgot-password` ARE STILL UNGATED AND CORRECTLY SO.** Each
answers one sentence either way and spends nothing. The cost of pressing is what
decides, not the presence of a required field.

---

## 10 · What this lane did NOT do, said plainly

* **The server half of the off switch is open** (`DEF-CWP-4938`) and named in
  the new test's own header.
* **`Do not use this form.` no longer reaches `/report` on a tenant with a
  published number** (`DEF-CWP-4937`); the frame is not this lane's to change.
* **Three `Postcode` strings remain** — two signed-in portal screens and one
  staff screen. `DEF-CWP-4855` stays **partially-fixed**.
* **`BillLocator`, `LocationField`, `Thread` and `Map` are still unbuilt**
  (`DEF-CWP-3986`), so `/enrol`'s picture of a bill, `/report`'s *use my
  location*, `/track`'s thread and both `visit` maps are still absent. Those are
  new components with their own drawings, not fixes.
* **`/visit` still reads the whole list in one request and renders every row.**
  That is `NFR-3` on a guest-facing list — the fifth breach beside `CLAUDE.md`'s
  four, and the only one on a page a member of the public can open. Recorded in
  step 1; a server-paging change is not a screen fix.
* **`/sign-in`'s *Pay with a bill number →* still goes to the LANDING PAGE**
  (`FrontDoor.tsx`, `data-door="quick_pay"` → `path("/")`) while the SAME LABEL
  on `/enrol` goes to `/pay`. Two destinations for one word, and the one-line
  fix is obvious — which is exactly why it is not in this commit. It is not one
  of the eight rows this lane was dispatched with, and a silent fix inside a
  commit about something else is how the record stops being able to tell the
  next lane what happened. Recorded in step 1 §2 screen 03 and carried forward
  here.
* **`/forgot-password` still stacks its one field and its button on the 12px
  step** while `/sign-in` and `/enrol` are now on 20. Rule 39's anchors cover
  field → field and say nothing about field → button, so there is no figure to
  build to; left alone rather than guessed at.
* **Nothing was built to an unratified rule.** `R-10` and `R-22` are law as of
  2026-09-11 and are cited. The blueprint's other proposals are not cited by id
  anywhere in this lane's source — including in the two places where the
  reasoning happens to agree with one, which say so in as many words.

---

## 11 · The AFTER pass, in figures

**283 checks green, 0 red** — `════════ ALL CHECKS PASS ════════` — at **390
and 1280**, on both tenants.

⚠ **THE FIRST AFTER-PASS WAS 281 GREEN AND 2 RED, AND THE TWO REDS WERE THIS
HARNESS RATHER THAN THE PRODUCT. BOTH NUMBERS ARE KEPT HERE ON PURPOSE.**
`/track` at **390 on `pine-hill`** reported *exactly one h1 — saw 0* and *exactly
one emergency band — saw 0*, with **no `[data-screen]` in the document at all** —
while the same route at 1280 passed, the same route on `brazosbend` passed at
both widths, and every other route passed everywhere. Two things settled it, and
the second is the one that counts: opening `/pine-hill/portal/track` on its own
renders `CWP-012`, the heading *Look something up*, the guest frame and the
emergency band at both widths, with a single `200` from `public/front` and no
page error; and then **the walk was given a proper wait and re-run, and came back
283 green**. `waitUntil: "networkidle"` is not *the page is drawn* — on an SPA
the last request can finish a frame before React paints — and the wait that
followed it was swallowing its own timeout on a box running six lanes.

**The fix was not to re-run until it went away.** The harness waits for the mark
every portal screen carries, and when it gives up it now prints `⚠ HARNESS:` and
names the address, because a red that means *I gave up waiting* is
indistinguishable from a real one and is the more common of the two on a shared
machine. **The record keeps the 281/2 as well as the 283/0**, because a walk that
only ever shows its good pass is a walk nobody can calibrate.

| What the walk asked | Answer |
|---|---|
| every guest route draws exactly one `<h1>` | **10 of 10**, both widths, both tenants |
| every guest route draws exactly one emergency band (`pine-hill`) | **10 of 10** — it was **2** on `/report` |
| *Download error report* anywhere on the ten | **0** — it was on `/visit`, `/visit/:slug` and `/help/:slug` at `brazosbend` |
| a raw `portal.*` key visible as text | **0** |
| the page scrolls sideways | **0**, both widths |
| checks green in the final pass | **283 of 283** |
| with `is_live:false`: the holding page and nothing behind it | **10 of 10** — it was **1** |
| with `is_live:false`: content reads issued to the server | **0** |
| `/help` empty vs `/help` no-match, as sentences | *"No answers are published here yet."* vs *"Nothing here matches what you typed."* — R-22 |
| `/enrol`'s commit with three empty required fields | `disabled: true`, `title: "Fill in all three boxes."` — it was `disabled: false`, no reason |
| *"Postcode"* on `/enrol` and `/track` | **absent**; *"ZIP code"* present on both |

**B14 rule 39, every field of all five guest forms, at 390:**

| form | label → input | input → helper | field → field |
|---|---|---|---|
| `/sign-in` | 5 | — | **20** (was 12) |
| `/enrol` | 5 | 6 | **20** (was 12) |
| `/forgot-password` | 5 | — | one field |
| `/track` | 5 | 6 | **20** (was 16) |
| `/report` | 5 | 6 | **20** (was 16) |

Ratified: **5 / 6 / 20**, a ratio of 1 : 1 : 4. Every figure on the anchor.

**`npm run lint`: 4 errors, none of them this lane's, each dated
(`git log -S`, law 7 habit 1):** `UnitDetailPage.tsx`'s `SearchSelectField`
since **2026-08-22** (`fa25a6017`), `RunbookSetupPage.test.tsx`'s `_options`
since **2026-09-06** (`c6fa557b9`), `LevelPayStanding.tsx`'s `ErrandLink` since
**2026-09-05** (`98c1c43ad`) and `YourPlan.tsx`'s `SectionTitle` since
**2026-09-11** (`0c85f58ce`, `CR-085` step 2 lane 7 — today, and the newest of
the four). All four are unused imports in files this lane did not touch.

⚠ **AND ONE RED IN THE WHOLE-PORTAL RUN THAT IS NOT THIS LANE'S, DATED RATHER
THAN DISMISSED (law 7 habit 1).** `vitest run src/portal` — all 73 files, not
just this lane's 18 — leaves **one** failure standing:
`portal/payments/Fees.dom.test.tsx:301`, *"R-10 — a failed read still offers the
question route, and really re-reads"*, which cannot find `SR-26-0061`.
`git log -S "SR-26-0061"` puts that string in **`0c85f58ce`, 2026-09-11 —
`CR-085` step 2 lane 7's own R-10 work**, and again in `c0157aa4c` the same day.
Neither is this lane's. **And the check that it is not ours is not the date, it
is the wiring:** none of the five catalogue keys this lane moved
(`portal.enrol.postcode`, `portal.postcodeHelper`, `portal.track.secondFact`,
`portal.quickPay.postcode`, the retired `portal.held.signIn`) is referenced
anywhere under `portal/payments` or `portal/plans` — grepped, not assumed,
because *"a red I did not cause"* has been said in good faith by the lane that
caused it. **Ten other failures in that same run had already been fixed by their
own lanes between the two runs**, which is what an active branch looks like.

**The suites:** `npx tsc --noEmit` green over the whole front end;
`vitest run src/portal/guest src/portal/signin` **18 files, 191 cases, all
green**.

⚠ **ONE OF THOSE 191 IS ANOTHER LANE'S AND THIS LANE BROKE IT BEFORE FIXING IT.**
`QuickPay.dom.test.tsx` looks its field up by the words a person reads —
`getByLabelText(/postcode/i)` — so moving `portal.quickPay.postcode` to *ZIP
code* took **eleven** of its cases red at once. That is the translation tail
`DEF-CWP-4855` names, arriving on a screen this lane does not own: the two
lookups now read `/zip code/i` and the field ids are untouched. **A copy change
is not a small change when a suite asserts on the copy.**
