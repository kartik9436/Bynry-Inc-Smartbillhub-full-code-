# CR-085 · lane 2 · guest entrance & errands — what differs

**Written 2026-09-11** by the CR-085 step-1 guest lane, from `b4063d1e6`.
**IDENTIFY ONLY — not one line of product code was changed by this lane.**

Ten routes, all under `/:tenant/portal/`: the landing page · `/sign-in` ·
`/enrol` · `/forgot-password` · `/track` · `/report` · `/visit` ·
`/visit/:slug` · `/help` · `/help/:slug`.

The drawing is quoted verbatim in **`CR-085-lane2-drawing.md`** beside this file.
Read that one first; this one is the delta.

---

## 0 · How this was measured, and what it could not reach

**Source** — every screen read in full at `b4063d1e6`.

**Browser** — the shared stack at `http://127.0.0.1:8401`, tenant `brazosbend`,
Chromium via `playwright-core`, at **390 and 1280, both, every route**
(PO 2026-09-11: *"this is Consumer web portal - that means we have Mobile and
Desktop sizes"*).

⚠ **THE STACK CHANGED UNDER THIS LANE MID-MEASUREMENT, AND BOTH HALVES ARE
REPORTED.** At the first pass `portal_settings` held **zero rows** in the shared
database, so `is_live` answered **false** for every read and the portal was OFF.
A sibling lane switched it on partway through; the second pass reads
`is_live: true`. Every observation below says which pass it came from. The
portal-off pass is not wasted — it produced finding **G1**, which is the most
serious thing this lane found.

**What is still unverified, and why** — the demo content was never seeded on this
stack: `GET portal/public/service-centres` answers **404** and
`GET portal/public/help` answers `{"answers":[],"topics":[],"visit_link":false}`.
So **`/visit` (with centres), `/visit/:slug` and `/help/:slug` could not be opened
at all**, and `/help` could only be seen empty. Those three are read in SOURCE
here and marked `source only`. `seed_portal_demo` refuses on anything but
PostgreSQL — *"needs PostgreSQL — tenant context is a GUC and the portal's tables
are RLS-forced; nothing was written"* — and creating a private database was not
permitted to this lane, so a private stack was not an option either.

**One environment caveat that touches the numbers.** Every page requests
`https://fonts.googleapis.com/css2?family=Archivo…` and it fails
`net::ERR_CONNECTION_RESET` in this container, so all measurements were taken on
the fallback face. The rule-39 figures in §6 are margin- and gap-derived, not
line-box-derived, so they are unaffected; type sizes would need re-reading with
the real face.

⚠ **TWO DRAWINGS EXIST AND THE PRODUCT IS BUILT TO THE OLDER ONE.** The blueprint
PDF is dated **8 September**; `wireframes/CWP-###.png` is *"rendered from the
blueprint 2026-09-03"* (`08-screen-layouts.md`, first line). `14-layout-audit.md`
grades nine of my eleven drawings **"Matches"** against the September-3 pack.
**So most of §2 is the product matching the older drawing, not the product being
careless** — and **no gate compares any screen with the blueprint PDF**: `G105`
reads `08-screen-layouts.md` and nothing else. Which of the two is the design is a
PO question, not this lane's.

---

## 1 · The findings that are not about one drawing

Six, and all six are filed: `DEF-CWP-4851` · `4852` · `4853` · `4854` · `4855` ·
`4856` · `4857` · `4858` (eight rows — the two screen-copy ones are in §2).

### G1 · **NINE OF MY TEN ROUTES IGNORE THE PORTAL'S OWN ON/OFF SWITCH** — `DEF-CWP-4851` — measured in a browser, portal-off pass

Only `FrontPage.tsx` branches on `front.is_live`. Grep the whole portal front end
for `is_live` and outside tests you get exactly two files: `shell/GuestFrame.tsx`
(the frame — lane 1's) and `guest/FrontPage.tsx`.

At `is_live: false`, opened one at a time at 390 **and** 1280:

| Route | What a stranger got |
|---|---|
| `/` | ✓ *"We are not open online yet."* — the holding page, correct |
| `/sign-in` | ✗ the full sign-in form, email + password + Sign in |
| `/enrol` | ✗ the full three-step enrolment wizard |
| `/forgot-password` | ✗ the full reset form |
| `/track` | ✗ the full lookup form |
| `/report` | ✗ the full report form, emergency band and all |
| `/help` | ✗ the full answers screen |
| `/visit` | ✗ a raw failure panel (see G2) |

**The drawing rules on this explicitly**, in screen 01's own state table:
*"**PORTAL OFF** — The utility has not switched sign-in on: the pay and contact
routes stay, **sign-in says so**."* It does not say so. It signs you in.

**Hard-won law 3 is the general form** — *"Defaults fail closed. The unsafe option
must be the one you type."* `models.PortalSettings.is_live` defaults `False` with
a comment saying *"law 3: off until switched on"*, and the front page honours it;
eight screens behind it do not. A utility that has not switched its portal on
still has a live sign-in box, a live enrolment wizard and a live password-reset
mailer on the open internet.

**Why nothing caught it:** every one of those screens is tested at its own address
with a fixture whose `is_live` is true. The question *does this screen respect the
switch* belongs to no test — the exact shape of `DEF-CWP-3925`, one layer down.

### G2 · **`/visit` WITH NO CENTRES SHOWS A MEMBER OF THE PUBLIC A STAFF ERROR PANEL WITH A "DOWNLOAD ERROR REPORT" BUTTON** — `DEF-CWP-4853` — browser, both passes, both widths

`GET portal/public/service-centres` answers 404 when no centre is shown, and
`CentresPage` hands that to `FailedWithRetry`. What renders, outside the
`GuestFrame` entirely — no utility name, no header, no way back:

```
Failed
We could not open this page.
We could not find that. It may have been removed, or the address may be wrong.
[ Retry ]  [ Download error report ]  Cancel
```

The drawing's **NONE CONFIGURED** state is one sentence: *"Falls back to the phone
number rather than an empty page."*

Three things are wrong at once, and the first is the worst: **"Download error
report" is an internal control on a public page** (the blueprint's own copy rule:
*"Nothing internal is ever visible"*; B14 rule 31's spirit). Second, the page
loses the frame, so there is no phone number, no nav and no door out. Third, the
sentence *"the address may be wrong"* blames a visitor who typed nothing.

⚠ **This is `CPB-17`'s shape on the GUEST side, and `CPB-17` names only screens
53 and 54.** The spec says *"True of every signed-in screen, not just one"* — it is
true of a signed-out one too.

### G3 · **`CPB-24`, AS WRITTEN, WOULD PUT A RAW CATALOGUE KEY ON THE LIVE LANDING PAGE** — `DEF-CWP-4857`

`CPB-24` says: *"`portal.held.card` and `portal.held.signIn` sit in all eleven
catalogues and are rendered by **no source file at all**."*

Checked at `b4063d1e6`:

* **`portal.held.signIn`** — true. Eleven catalogues, no render site. Retire it.
* **`portal.held.card`** — **false.** `FrontPageView.tsx:237` renders it for
  `what_things_cost`, whose `CR-068` R3 hold is still correct because the
  blueprint's screen 08 (a public prices page) is genuinely unbuilt. I have the
  screenshot: the live landing page reads *"Opens with the next release."* under
  **What things cost** right now.

`t()` answers a missing key **with the key**, so doing what CPB-24 asks would
print `portal.held.card` to customers in eleven languages — the defect `G27` was
built for. **CPB-24 must be narrowed to one key before anybody executes it.**

⚠ There is a second trap next to it, worth one line: **`/:tenant/portal/fees` is
claimed by both drawings for different screens.** The blueprint's screen 08 is a
PUBLIC prices and fees list; the product mounts `CWP-050` *"Fees to pay"* — a
**signed-in** list of fees owed — at that exact address. Not my screen; flagged
because the landing page's *What things cost* card points at it.

---

## 2 · Screen by screen — every difference

Legend: **✗ missing** · **＋ extra** · **≠ different words / order / state** ·
**✓ matches**. `[live]` = seen in a browser on the portal-on pass; `[off]` = seen
on the portal-off pass; `[src]` = read in source only.

---

### 01 · The landing page — `/:tenant/portal` `[live, 390 + 1280]`

| | Difference |
|---|---|
| ✗ | **THE EMERGENCY BAND IS ABSENT — `DEF-CWP-4852`.** The drawing: *"Above everything, on every width, in the danger tier, with a phone number and not a form. Somebody standing in water must not have to read a page."* There is no band, no phone number and no danger tier anywhere on the built landing page. `/report` has one; the busiest page in the portal does not. **This is the most serious content delta in the lane.** |
| ✗ | **The quick-pay form.** The drawing puts *Bill number* + *ZIP code* + **[ Find this bill ]** on the landing page itself. Built: a `Pay a bill` card with a `Start →` to `/pay`. |
| ✗ | **The embedded sign-in form.** The drawing's right rail carries *Email* · *Password* · **[ Sign in ]**. Built: an `InfoBar` with a `Sign in` link. (Screen 03's own *HOW YOU GET HERE* row depends on this: *"The landing page (**its own sign-in form is embedded there**)"*.) |
| ✗ | **The outage panel** — *"LOW PRESSURE · QUARRY HILL AREA / Crews on site since 9:40 AM… → All current problems"*, drawn as *"Shown unprompted."* Built: no panel. `Check my area` is a **disabled card** saying *"No status page here yet."* — correct per `CR-068` R9, so this absence is ruled, not careless. |
| ✗ | **The assistance panel** — *"STRUGGLING TO PAY? … → See help paying"*. `/help-paying` is a live route. The drawing's own standards say *"Assistance is a first-class path, not a page behind a sign-in"* and *"The bad news comes with the way out"*. No door from the front page. |
| ✗ | **The footer** — *"Silver Creek Water · Mon–Fri 8 AM – 5 PM · (281) 555-0164"*. |
| ✗ | **Two of the six drawn errands have no card:** *Track a report* and *Where to find us*. (*Track* is in the nav; *Visit us* is not, because `links.visit` is false.) |
| ＋ | **`Check my area`** is a seventh errand the drawing does not have. |
| ≠ | **The errand set and its order.** Drawing: Report a problem · Track a report · Start service · Prices and fees · Where to find us · Help, under the heading *"OR DO THIS WITHOUT SIGNING IN"*, with *Pay your bill* as a form above them. Built: Pay a bill · Report a problem · Check my area · Start service · What things cost · Help & answers, with no heading over them. |
| ≠ | **No icons.** The drawing gives every errand one (⚠ ⌛ 🏠 💲 📍 ❓) and block A requires *"Every icon carries its word"*. Built cards carry words and no icons. Not a rule breach — the rule forbids an icon *alone* — but it is the drawing. |
| ✓ | **One filled button, and it is `Pay a bill`.** The drawing's own words: *"One filled button, and it is not "Sign in""*. Verified live: `pay_bill` is the only `primary`. |
| ✓ | Three disabled cards each carry a distinct six-word reason — *"No status page here yet."* · *"Opens with the next release."* · *"Nothing published here yet."* — which is `DEF-CWP-3953` holding. |
| ✓ | `Set up your login →` and `Forgot your password?` are both present beneath the sign-in bar, which is the drawing's *"Create one · Forgot your password?"*. |

---

### 02 · Choose your language — the top bar `[live, 390 + 1280]`

| | Difference |
|---|---|
| ≠ | **A native `<select>` in the bar, not a menu screen.** The drawing draws a list of rows, the current one marked `CURRENT`, each other with a **[ Choose ]** button. Built is a `<select>`. **B14 rule 8 requires a real `<select>`, and B14 rule 38 (a form's CONSTRUCTION is the UI rules') settles it in the product's favour** — this one is correctly overruled and should be recorded as such rather than fixed. |
| ✗ | **The `WHAT IT CHANGES` panel** — *"This site, on this device / NOW"* · *"Your bills and letters / Set on your account"* · *"A guest has no account, so the choice lives in this browser until they sign in."* Absent. That is CONTENT, which rule 38 leaves to the drawing. |
| ✗ | **The `IF WE HAVE NOT TRANSLATED SOMETHING` panel** — *"A page we have not translated stays in English… It says so, in your language, at the top."* Absent on the guest side. The equivalent exists on `/help/:slug` only (`portal.help.fallback`). |
| ≠ | Two languages offered (English, Español), not five. **Ruled, not a defect** — `DEF-CWP-4442`, PO 2026-09-07: *"currently in drop down show only 2 elnglish and spanish"*, and the list is the server's `PORTAL_LOCALES`. |
| ✓ | Each language is named in its own language (`languageName`), never as `es-MX` — the drawing's *"THE RULE THAT MAKES IT WORK"* and B14 rules 31 + 35. |
| ✓ | No flags. |

---

### 03 · Sign in — `/:tenant/portal/sign-in` `[live, 390 + 1280]`

| | Difference |
|---|---|
| ≠ | **`Forgot your password?` sits ABOVE the `Sign in` button.** The drawing puts it below. Measured at both widths. |
| ≠ | **Three doors where the drawing has one.** Drawing: *"NO ACCOUNT? / Pay a bill with its bill number — no sign-up needed. / [ Pay a bill → ]"*. Built: an `OR` rule then **Set up your login →** · **Pay with a bill number →** · **Start service →**, three bare links with no explaining sentence. |
| ✗ | **The sentence** *"Pay a bill with its bill number — no sign-up needed."* has no equivalent. |
| ✗ | **No emergency number on the screen at all — `DEF-CWP-4852`**, on a tenant that has not set one. The drawing's RULES for this screen: *"**Emergency number on every unauthenticated screen.**"* Built renders `front.emergency_phone` inside the brand card and draws **nothing** when it is null — where `/report` falls back to *"the number on your bill"*. So the rule holds only for tenants that filled the field in. |
| ✗ | **`PORTAL OFF` state.** See **G1** — the drawing says *"says so, with the phone number"*; the screen signs you in instead. |
| ＋ | **An empty brand card.** At 390 the card under the form renders the utility's name, a `<hr>`, and nothing else, because `strapline`, `services`, `office_hours_text` and `emergency_phone` are all null. The drawing has **no brand panel on the phone at all** — the file's own comment says so. A titled card with no body is the empty-state failure r10's own rules warn about. |
| ✓ | **The form comes first at 390.** The `max-md:order` fix holds — verified, the email box is the first thing under the bar. |
| ✓ | **One filled button: `Sign in`.** |
| ✓ | **WRONG DETAILS is one message under the pair, not per field** — exercised live with a bad password: `Those details do not match.` (drawing: *"That email and password do not match."* — same shape, five words, different wording). |
| ✓ | **`Set up your login →` IS on this screen.** ⚠ **The blueprint's standards block E is now STALE here.** It lists *"No way to sign up, from the sign-in screen"* among its nine audited door findings: *"enrol… not from sign-in, which offers Forgot your password? and nothing else"*. That door exists — `data-door="enrol"` → `/{tenant}/portal/enrol`, confirmed in the browser at both widths. Screen 04's *HOW YOU GET HERE* row carries the same stale claim (*"⚠ Not the sign-in screen."*) and needs the same correction. |
| ⚠ | `Pay with a bill number →` on this screen goes to **`/{tenant}/portal`** (the landing page); the *same label* on `/enrol` goes to **`/{tenant}/portal/pay`**. Two destinations for one label, and on a portal-off tenant the first one lands on *"We are not open online yet."* |

---

### 04 · Create your sign-in — `/:tenant/portal/enrol` `[live, 390 + 1280]`

The largest structural gap in the lane.

| | Difference |
|---|---|
| ≠ | **The drawing is ONE screen of four fields; the product is a THREE-STEP wizard with a one-time code.** Drawing: *Account number* · *ZIP code of the service address* · *Your email* · *Choose a password* → **[ Create my sign-in ]**, and *"Turning a paper-bill customer into an online one, **in four fields**."* Built: step 1 *Account number · Postcode · Last name* → step 2 *Six-digit code* → step 3 *Email · New password · Type it again · How should we send codes?*. **The wizard is the product's own signed law** (`BR-CWP-030`/`032`/`035`/`036`/`037`) and is almost certainly right; the drawing simply has not caught up. Recorded as a delta for the PO, not as a defect. |
| ＋ | **`Last name, or company name`** — a third matching factor the drawing does not have. |
| ✗ | **The `← The landing page` back link.** Both widths of the drawing carry it. There is no back link and no `WhereNext` out of step 1's main column. |
| ✗ | **`WHERE THE ACCOUNT NUMBER IS`** — the drawing's little picture of a bill with the number circled, captioned *"Top right of your paper bill, above the amount due."* The drawing is explicit that this is the point of the screen: *"the screen shows a picture of a bill with the number circled **rather than describing where to look**."* Built shows the opposite: a rail reading `NO BILL TO HAND?` / *"Ring the office and we will read it to you."* — which is describing where to look. The `BillLocator` component the drawing names is unbuilt. |
| ✗ | **`Cannot find your account number? Call (281) 555-0164.`** — no equivalent. |
| ≠ | **`ZIP code of the service address` is built as `Postcode of the service address`.** See **G4** / `DEF-CWP-4855`. |
| ≠ | **`Create my sign-in`** is built as **`Create my login ✓`**. |
| ≠ | **`At least 10 characters`** is built as `At least {{count}} characters.` reading the tenant's own `pw_min_length` — **better than the drawing**, and `BR-CWP-037`. Recorded so nobody "fixes" it back to a literal 10. |
| ✓ | **The escape hatch is on the screen** — `Pay with a bill number →` in the rail, which is the drawing's *"NOT READY TO SIGN UP? … [ Pay without signing in → ]"*. |
| ✓ | Password reveal present on both password fields (see §3, `DEF-CWP-4377`). |
| ✗ | **At 390 the stepper truncates its own labels** — *"Find your acco…"* and *"Choose a pass…"*. Two of three step names are unreadable on the design-target width. |

---

### 05 · Forgotten password — `/:tenant/portal/forgot-password` `[live, 390 + 1280]`

| | Difference |
|---|---|
| ≠ | **`Reset your password`** is built as **`Send me a reset link`**. |
| ≠ | **`We will email you a link. It works once and lasts an hour.`** is built as **`We will email you a link. It works once.`** ⚠ **This one is right and is already reasoned in the file**: the product's link lasts **seven days** (`RESET_TTL_DAYS = 7`), so the drawing's *an hour* is not this product's figure, and the lifetime is a server constant this screen cannot read. **B14 rule 37** settles it — *a figure drawn in a wireframe is an illustration, never a fact to build to*. Recorded so nobody copies the hour in. |
| ✗ | **The drawing states the lifetime BEFORE submit** and the built line states only *once*. The gap — *how long* — is real and unstated. The drawing's whole cognitive-load note is *"The link's lifetime is stated before they submit, so a link that has expired is not a surprise."* |
| ≠ | **`← Sign in` at the top** is built as a `WhereNext` **`Sign in`** at the foot. Deliberate (the kit's shape for *where you can go from here*) and recorded rather than filed. |
| ✗ | **`No email on the account? Call (281) 555-0164 and we will verify you another way.`** — absent. The drawing's `NO EMAIL ON FILE` state is *"Falls back to the phone number rather than stranding them"*; there is no phone number on this screen. |
| ✓ | **One answer either way.** `asked` is a boolean and the panel is a constant — `BR-CWP-038`, the drawing's `SENT` state exactly. |
| ✗ | `LINK EXPIRED` and `FAILED TO SEND` have no drawn state in the product — the screen has one branch. |

---

### 09 · Report a problem — `/:tenant/portal/report` `[live, 390 + 1280]`

| | Difference |
|---|---|
| ✓ | **THE EMERGENCY BAND IS ABOVE EVERYTHING, AT BOTH WIDTHS.** Measured: band top 171px, first field top 457px at 390. The `CR-085` 2026-09-08 fix holds. |
| ≠ | **The problem list is six radio options, not the drawing's seven in a select.** Drawing: *Water leaking in the street · No water · Water looks or smells wrong · Low pressure · A manhole or cover · Streetlight out · Something else*. Built: *No water at all · A leak or a burst · Low pressure · Smell of gas · A missed collection · A damaged meter or cover*. **Four of the drawing's seven have no equivalent** (*Water looks or smells wrong*, *A manhole or cover*, *Streetlight out*, *Something else*) and **two built options are not drawn** (*Smell of gas*, *A missed collection*). The drawing's own `NOT OURS` state on screen 10 — *"a streetlight may belong to the city"* — depends on *Streetlight out* existing. |
| ✗ | **`How bad?`** (drawing, 1280: *A steady trickle ⌄*) — no field. |
| ✗ | **`📍 Use my location`** — the drawing's *"Location by one tap. …Someone reporting a burst main is standing in the street on a phone."* Built is a plain text box with the helper *"An address, or the nearest one you can see."* The `LocationField` component the drawing names is unbuilt. |
| ✗ | **`ALREADY KNOWN ABOUT`** — the live nearby-incident row with *Since 9:40 AM* and **→ See all current problems**. Built has a static note: *"Already reported by someone on your street? **We will say so before you send.**"* — a promise instead of the answer. The drawing's reason: *"Showing what is already reported nearby prevents duplicates and answers "have you been told?" without anyone having to ask."* |
| ≠ | **`WHAT HAPPENS AFTER YOU REPORT` (1 · 2 · 3)** is built as a `ConsequenceBox` headed **`WHAT THIS WILL DO`** with three bullets — same three facts, different heading, unnumbered, and on the main column rather than the rail. |
| ≠ | **`Your phone, if we need to call` / `Optional`** is built as **`Phone`**, **required**. The drawing marks it optional in both drawings. |
| ＋ | **`Your name`, required.** The drawing has no name field at all. So the built form demands **two** facts the drawing does not ask for, on the one screen the drawing says a stranger may reach in an emergency. |
| ≠ | **`Report it`** is built as **`Send this report ✓`** (r10 rule 4, `Verb ✓` commits — the kit wins; recorded, not filed). |
| ≠ | **`A photo helps` / `📷 Add a photo`** is built as **`A photo`** with a held `PhotoPicker`: *"Photos open with a later release."* `CR-068` §2b — a signed deferral, correctly stated. |
| ✗ | The `PHOTO FAILED` state cannot exist while photos are held. |
| ⚠ | At 390 the radio hints render **beside** the label, not under it, so three of six labels wrap to two lines (*"No water at all"*, *"A leak or a burst"*, *"Smell of gas"*) against a hint on the right. Cramped on the design-target width. |

---

### 10 · Track a report — `/:tenant/portal/track` `[live, 390 + 1280]`

| | Difference |
|---|---|
| ≠ | **THE DRAWING SAYS EITHER KEY ALONE OPENS IT; THE PRODUCT REQUIRES BOTH.** Drawing: *"**Either key alone opens it**, because most reporters have no account"* — *Reference* **or** *Or a phone number you gave us*. Built: `Reference *` **and** `Postcode, or the phone number you gave us *`, and `ready = reference && secondFact` — verified live, the button is disabled with *"Fill in both boxes."* until both are typed. **This is `BR-CWP-025`** (*a second fact only the sender would know*), so the product has a signed rule and the drawing has a promise, and they contradict each other. **A PO question, not a fix.** |
| ✗ | **The phone-number-only lookup**, and with it the drawing's whole *"Lost the reference? A phone number finds everything reported from it in the last 90 days"* fallback, and the `SEVERAL FOUND` state built on it. |
| ✗ | **`WHAT HAS HAPPENED` — the thread.** The drawing's centre of gravity: four dated entries, each attributed (*Silver Creek Water* / *You*), with the reporter's own words and their photo. Built shows a `KVList` of *Reference · What · Reported · Now · Expected fixed · Fixed · Cleared*. The `Thread` component the drawing names is unbuilt. |
| ✗ | **The reply box** — *"Anything to add? You can reply here without signing in."* + **[ Send ]**. Absent. |
| ✗ | **`OTHERS REPORTED THIS TOO`** — *"4 people have reported the same problem. You will all be told when it is fixed."* Absent. |
| ✗ | **`Showing 1 report for REP-8842 · ↻ Look up another`** — absent. |
| ≠ | **`Track a report` / `No sign-in needed`** is built as **`Look something up`** / *"Any reference we have given you."* — deliberately wider (the screen takes reports, applications, requests and payments), and recorded rather than filed. |
| ✓ | **The three dates the drawing calls the point of the screen are drawn** — `Expected fixed`, `Fixed`, `Cleared` — each ABSENT rather than dashed when unknown. That was the `CR-085` 2026-09-08 fix and it holds. |
| ✓ | **`NOT FOUND` never confirms whether a reference exists** — exercised live: `We cannot find that reference.` |
| ✗ | `OVERDUE` and `NOT OURS` have no built state. |

---

### 11 · Help — `/:tenant/portal/help` `[live at 390 + 1280, but EMPTY — nothing published on this stack]`

| | Difference |
|---|---|
| ✗ | **`TALK TO SOMEONE` — the phone number, the hours and `open now` (`DEF-CWP-4854`).** The drawing makes this the loudest thing on the screen and says why: *"A number without hours produces a call to a closed office and a second call tomorrow."* Built has a `Still stuck?` rail reading *"Call us or come in and someone will go through it with you."* — **with no number, no hours and no open/closed state** unless the tenant filled `emergency_phone` in. On this tenant the rail names no way to reach anybody at all. |
| ✗ | **The email address** and *"We reply to email within 1 working day."* |
| ✗ | **`COME AND SEE US`** — the office, its address, its hours, what it takes, **→ Directions** and **→ All locations**. Built has a bare `Visit us →` link, and only when `visit_link` is true. |
| ✗ | **The tip band** — *"💡 Worth knowing · A running toilet can use 4,000 gallons a month."* The drawing specifies exactly one tip, below the questions, absent entirely when there is none. **Nothing on this screen renders a tip.** (Related: `DEF-CWP-4510`, a tip aimed at a screen that cannot receive one.) |
| ＋ | **A topic chip row** the drawing does not have. With nothing published it renders a single `All` chip — a chooser with one option, which the drawing's own reasoning calls *furniture*. |
| ✗ | **The `NO ARTICLES` state is wrong in all three of its clauses — `DEF-CWP-4854`.** Drawing: *"Falls back to the phone number and email — **never an empty search box**."* Built, screenshotted: an empty search box, a lone `All` chip, and **`Nothing here matches what you typed.`** — said to somebody who typed nothing. |
| ≠ | **`Help` / `COMMON QUESTIONS`** is built as **`Answers`** with kicker `HELP` and no section heading over the rows. |
| ⚠ | **The search filters rows already in the browser**, which the file itself flags: *"The day that endpoint learns to page, this has to become a server query."* Honest today; a `NFR-3` trip-wire to remember. |
| ✓ | Article rows are titled as questions, not topics — the drawing's *"QUESTIONS, NOT TOPICS"*. `[src]` |

---

### 12 · One help article — `/:tenant/portal/help/:slug` `[src only — nothing published to open]`

| | Difference |
|---|---|
| ✗ | **`about 2 minutes to read`.** Correctly absent and correctly reasoned in the file: no reading time is served, and *"a number this screen invented from the body's length would be a figure the product cannot stand behind"*. Recorded so it is not "fixed" by inventing one. |
| ✓ | **`Updated August 2026`** is drawn, from `updated_on`, in the tenant's own date format, and ABSENT when the server sends none. That was the `CR-085` 2026-09-08 fix. |
| ✗ | **`Still not answered? Ask us a question — we reply within one working day.`** The rail says *"Call us or come in"*; `/ask-a-question` exists as a route and this screen does not point at it. |
| ✗ | **The `NOT SIGNED IN` state** — *"The "see it for your own bill" panel becomes a sign-in prompt, not a dead button."* There is no *see it for your own bill* panel at all: `also_written_in` is drawn, the live-equivalent link is not. **That is `DEF-CWP-3945` on this screen** — *"A CLERK CAN PIN A HELP ANSWER TO A SCREEN AND THE CUSTOMER NEVER SEES IT"*. |
| ✗ | **The `NO SUCH ARTICLE` state** — drawing: *"Offers the search and the three most-read, never a bare 404."* Built: the generic `FailedWithRetry` panel, i.e. **G2** again. |
| ≠ | **`DID THIS HELP? 👍 Yes 👎 No`** is built as `Did this help?` with two plain `Button`s labelled `Yes` / `No` — no thumbs. Consistent with the drawing's own *"No emoji as a section marker"*, and these are controls rather than headings, so this is a straight delta. |
| ⚠ | Related answers and the `Visit us` link are plain `<a href>` relative links, not router `Link`s — a full page reload inside an SPA, and the exact fragility `AnswerHead`'s own comment warns about for `backTo`. |

---

### 13 · Where to find us — `/:tenant/portal/visit` `[src only — 404 on this stack; failure panel seen live, see G2]`

| | Difference |
|---|---|
| ✗ | **The search box** — *"🔍 Town, ZIP code, or the name of an office"*. Not built. |
| ✗ | **The `What do you need to do?` select** — *"Pay in cash ⌄"*. Not built. |
| ✗ | **The six filter chips** — *Nearest first · Open now · Open Saturday · Takes cash · Start or stop service · Drop box*. Not built. |
| ✗ | **The map.** Not built (`Map` is in the inventory and unbuilt — `DEF-CWP-3986`'s shape). |
| ✗ | **The table** — `PLACE · WHERE · WHAT YOU CAN DO · OPEN`. Built draws `CentreCard`s instead. |
| ✗ | **`14 places · showing the 3 nearest to 78611`**, **`Showing 3 of 14 · Show 11 more`**, **`Rows per page 25`** — no count, no paging, no distance, no sort. |
| ⚠ | **AND THIS IS THE ONE WITH A RULE BEHIND IT.** The drawing's RULES row for this screen: *"**Server-side paging, and no cap on how many service centres a utility may have** — the same rule that governs every other list in the product. A screen that assumes three is the shape that has to be rebuilt when a larger utility arrives."* `getPortalCentres` returns the whole list in one read and the page renders every row. **That is `NFR-3` (universal server pagination) on a guest-facing list — a fifth breach beside `CLAUDE.md`'s four**, and it is the only one on a page a member of the public can open. |
| ✗ | **`LOOKING TO PAY CASH?`** — *"Only the main office takes cash. The drop box never does — never post cash and never leave it in the box."* The drawing calls it out separately *"because posting cash or dropping it in a box is a real and unrecoverable loss."* Absent. |
| ≠ | **`DO YOU NEED TO COME IN AT ALL?` / [ Pay online instead ]** is built as `Rather not travel?` / *"Most things can be done from this page or over the phone."* — same job, no link. |
| ✗ | **Four of the six drawn states** have no built equivalent: `ONE LOCATION` (*"Opens screen 42 directly"*), `NO LOCATION SHARED`, `SEARCH FINDS NOTHING`, `TWO OR THREE PLACES`, `ALL CLOSED`. `NONE CONFIGURED` is built as **G2**. |
| ＋ | `<header className="hidden"></header>` — a stray empty element left in `CentresPage.tsx`. |

---

### 14 · One service centre — `/:tenant/portal/visit/:slug` `[src only — no centre to open]`

| | Difference |
|---|---|
| ✓ | **THE DOOR EXISTS. THE BLUEPRINT'S "no door anywhere" IS STALE AND THE BLUEPRINT ALREADY KNOWS.** The spec head carries the correction — *"**NOW:** ANSWERED — the door was built. `CentresPage.tsx` now links each centre to `/:tenant/portal/visit/:slug`"* — and the source agrees: `<CentreCard … href={path(\`/visit/${centre.slug}\`)} />`, an absolute portal path via `usePortalPath`, fixed under `DEF-CWP-4655` on 2026-09-08. **I could not click it** (no centres on this stack), so this is source-verified, not browser-verified. |
| ✗ | ⚠ **BUT THE SAME SPEC'S OWN `HOW YOU GET HERE` ROW STILL READS THE SUPERSEDED SENTENCE** — *"Nothing. Nothing in the portal links to an individual service centre… Filed as a defect."* One document, two answers, the stale one in the row a lane actually reads. **This is `CLAUDE.md`'s status-vs-body law in a blueprint instead of a register**, and the body is the half that rots. |
| ✗ | **The map.** Not built. |
| ✗ | **`Parking` / `Free, at the rear`** and **`Step-free access` / `Yes, from the car park`** — the drawing's `ACCESSIBILITY` note: *"facts somebody needs before setting out, not afterwards."* Built draws `directions_note` as one free-text line (the `CR-085` 2026-09-08 fix) and has **no structured parking or step-free rows**. |
| ✗ | **`→ All our locations`** in the foot — built has only the `← Where you can walk in` back link at the top. |
| ≠ | **`WHAT YOU CAN DO HERE` is a ✓/— list of action names**; the drawing gives each action a qualifying phrase (*Pay a bill → Cash · card · check · money order*; *Start or stop service → Bring photo ID*). Built splits payment methods into a separate `Takes payment by` panel. |
| ≠ | **`Call (281) 555-0164`** is a plain outline in the head's action row, where the drawing gives it the brand outline. **Deliberate and already recorded** — B14 rule 6 reserves the brand outline for destructive commits and overrules the drawing. |
| ✗ | `CLOSED TODAY ONLY`, `TEMPORARILY CLOSED` and `NO MAP` have no built state. |

---

### G5 · **One of my five forms lets you press its commit with every field empty** — `DEF-CWP-4858` `[live, both widths]`

Four of the five guard the commit and name the reason; the fifth does not.

| Screen | Commit, with nothing typed |
|---|---|
| `/report` | `Send this report ✓` — **disabled**, `title="Fill in the marked fields."` |
| `/track` | `Look it up →` — **disabled**, `title="Fill in both boxes."` |
| `/sign-in` | `Sign in` — enabled, but a failed attempt answers one sentence under the pair, which is the drawing |
| `/forgot-password` | `Send the link` — enabled, and correctly so: one answer either way |
| **`/enrol` step 1** | **`Continue →` — ENABLED.** Three required fields, all empty, and the button is live |

`Enrol.tsx` composes `WorkingButton` with no `ready` guard, where `ReportProblem`
and `TrackAnything` compose `CommitButton` with one. So the enrolment wizard —
the screen with the most fields in the lane, and a **three-wrong-tries lock**
(`BR-CWP-036`, and the screen says so: *"Three wrong tries locks this form for
fifteen minutes."*) — is the one that lets an empty submission spend a try.

### G6 · **No route in this lane scrolls sideways at either width** `[live + off passes]`

`document.documentElement.scrollWidth === window.innerWidth` on all eight
openable routes at **390** and at **1280**, on both passes. Recorded as a pass
because it is one of the two things the responsive rule actually promises.

### G4 · **"Postcode" reaches a North American customer on two of my screens** — `DEF-CWP-4855` `[live, both widths]`

The blueprint's standards block C lists the vocabulary a North American utility
customer expects and names it: *"THE WORDS THEY KNOW … **ZIP code**."* Every
drawing in my set writes *ZIP code of the service address*.

Built, and read off the running screens:

| Key | What a customer reads |
|---|---|
| `portal.enrol.postcode` | **Postcode** of the service address |
| `portal.postcodeHelper` | Just the **postcode**, not the whole address. |
| `portal.track.secondFact` | **Postcode**, or the phone number you gave us |

and four more on screens that are not mine — `portal.quickPay.postcode`,
`portal.addAccount.postcode`, `portal.myDetails.postcode`,
`settings.portal.switch.quick_pay.sub`. The staff side already says
*"ZIP / postal code"* (`metering.premises.field.postalCode`), so the product
contradicts itself as well as its customers. **Eleven catalogues, so this is a
copy change with a translation tail, not a rename.**

---

## 3 · My slice of the 82 open / partially-fixed `DEF-CWP` rows, re-verified

The two audits (`13-wireframe-delta.md`, `14-layout-audit.md`) are dated
2026-09-05 and say *"before citing a row here as current, open the screen."*
Opened.

| Row | Register says | **Verdict now** |
|---|---|---|
| `DEF-CWP-4377` password fields cannot be read back | **open / high** | **FIXED — close it.** `primitives.tsx` `TextInput` carries a `data-password-reveal` toggle in the shared primitive. Exercised live on `/sign-in`: `portal-password=Show pressed=false`. Being in the primitive, it reaches both enrolment password fields too. |
| `DEF-CWP-4440` the portal never applies a language | **open / high** | **FIXED — close it.** `PortalLanguage.tsx` and `GuestLanguage.tsx` landed 2026-09-07 and both call `changeLanguage`; the guest `<select>` renders live in the bar at both widths. |
| `DEF-CWP-4000` [D1] screens carry no heading | **partially-fixed / high** | **The guest half is DONE.** All eight openable routes emit exactly one `<h1>` at both widths — *We are not open online yet.* · *Welcome back* · *Find your account* · *Send me a reset link* · *Look something up* · *Tell us what is wrong* · *Answers* · (the landing's *What do you need?*). `14-layout-audit.md`'s *"CWP-012 — No title on the page at all"* is **out of date**. The signed-in half is other lanes'. |
| `DEF-CWP-3986` [D11] six named components never built | **partially-fixed / medium** | **STILL REAL, and its own text is now wrong in one place.** The row says *"DialInput … verified — Enrol.tsx renders the code as a plain TextInput"*; `Enrol.tsx` renders `<DialInput id="enrol-code" …>` today. Still unbuilt and still needed by MY screens: **`BillLocator`** (screen 04), **`LocationField`** (09), **`Thread`** (10), **`Map`** (13, 14). |
| `DEF-CWP-3943` 36 keys render to nobody | **partially-fixed / low** | **STILL REAL for `portal.held.signIn`** — eleven catalogues, no render site. ⚠ **But the row's companion `portal.held.card` IS rendered** — see **G3**. Removing them as a pair breaks the live landing page. |
| `DEF-CWP-3988` [D13] ten drawn screens have no address | **partially-fixed / medium** | **NOT MINE** — none of the ten is one of my routes. |
| `DEF-CWP-3945` a pinned help answer never reaches the customer | **partially-fixed / medium** | **STILL REAL on `/help/:slug`** — the *see it for your own bill* panel the drawing calls *"THE PANEL THAT MATTERS"* is absent. `[src]` |
| `DEF-CWP-4174` wave-E documents name an account the seed never produces | **open / medium** | **STILL REAL.** `portal.enrol.accountNumberExample` is `AC-2026-00027`, i.e. the series shape, not `ACC-10432-A`; the documents and `cr068-e-getting-in.mjs` still carry the old number. |
| `DEF-CWP-4136` / `4148` the chromium fallback cannot fire | **open / low** | **STILL REAL, and it bit this lane.** I hit exactly the described failure and had to copy `cr087_tax_tabs_walkthrough.mjs`'s `resolveChromium()`, which checks `existsSync` BEFORE the fallback. **The fix is already written in a sibling file and has not been carried to the render-checks.** |
| `DEF-CWP-4447` one language, two names | **open / low** | **NOT RE-VERIFIABLE HERE** — needs the staff Regional screen beside the portal picker. The portal half draws `languageName()`, as the row says. |
| `DEF-CWP-4491` the preference endpoint stores any string | **open / low** | **NOT MINE** (signed-in preferences), but it is the same subject as the guest picker; noting the adjacency only. |
| `DEF-CWP-4468` the guest header is two rows in English | **open / low** | **STILL REAL and it is LANE 1's** — I see it at 1280 and at 390, where the utility's name is also truncated to *"Brazo…"*. Recorded in one line and passed on. |
| `DEF-CWP-4187` / `DEF-CWP-4711` / `DEF-CWP-4205` gates red at the tip | **open** | **NOT RE-VERIFIED** — I did not run the gate suite (this lane changes no product code, and a shared-tree gate run would have told me nothing about my screens that the browser did not). Left as found, and said so rather than implied. |

**Nothing in my slice moved the other way** — no row I checked has become *more*
broken since it was filed.

---

## 4 · `CPB-01` … `CPB-24` — which touch my ten routes

Read off the register on blueprint pages 111–113, matching the **SCREENS** column
against my eleven drawings (01 · 02 · 03 · 04 · 05 · 09 · 10 · 11 · 12 · 13 · 14).

**Exactly two of the twenty-four touch my screens.** The other twenty-two name
screens 6, 7, 8, 32, 34, 35–37, 39, 40, 43, 44, 47, 48, 50–56 and 60, every one of
which belongs to another lane.

| Spec | Screens | Touches mine? | **State on my screens** |
|---|---|---|---|
| **CPB-23** · *Every screen carries its How-you-get-here row* | **all** | **yes — all eleven** | **NOT BUILT, and it is a document deliverable rather than a screen one.** Of my eleven drawings, **three carry the row** (01, 03, 04) and **eight do not** (02, 05, 09, 10, 11, 12, 13, and 14 — whose row exists but states the superseded answer, see §2). So my slice is **3 of 11**, against the spec's repo-wide *23 of 60*. |
| **CPB-24** · *The two dead hold sentences are retired* | **1 · 3** | **yes — landing page and sign-in** | **HALF-BUILT AND HALF-WRONG.** `portal.held.signIn` is dead and should go. `portal.held.card` is **live on the landing page** and removing it prints the key to customers. **See G3 — this spec needs narrowing before it is executed.** |

**Nothing else in my lane is under a commitment card**, which is itself the
finding the blueprint's own state chip makes: my screens 04 and 14 carry
**NO COMMITMENT**, and the blueprint says of that chip — *"A screen no
specification covers carries NO COMMITMENT — that absence is the finding, not an
oversight."* So every difference in §2 for those two screens is unowned work.

---

## 5 · The twelve unratified drawn rules — which my screens depend on

Appendix A, *"12 of 24 are stated only here"*. **They are proposals until the PO
rules them in, and nothing below treats one as binding.** My screens depend on
**nine of the twelve**; the three I do not need are `R-05`, `R-09` and `R-16`
(all about an amount due, which a signed-out screen never shows).

| | The rule as stated | Which of my screens needs it, and for what |
|---|---|---|
| **R-04** | *No emoji as a section marker.* | **01, 09, 11, 13.** The drawing itself puts emoji on errand rows (⚠ ⌛ 🏠 💲 📍 ❓), on the tip (💡) and on the map pin (📍). Without a ruling nobody can say whether the built cards' **absence** of icons is right or wrong. |
| **R-06** | *Never ask a customer to compute — show the difference, not two numbers.* | **10.** *"expected fixed today, by 4 PM"* rather than a date a reporter has to subtract today from. The built screen now draws `Expected fixed` as a date; whether it must carry the relative phrase turns on this rule. |
| **R-07** | *One filled button per screen.* | **01, 03, 04, 05, 09, 10.** This is the rule the built landing page is *already obeying* — `pay_bill` is the only `primary`, and `FrontPageView`'s own comment cites the drawing's note as its authority. **A live screen is built to an unratified rule today.** |
| **R-10** | *Bad news never appears without the way out beside it.* | **01, 03, 11, 13.** It is what makes the landing page's missing `STRUGGLING TO PAY?` panel a defect rather than a preference, and what makes `/help`'s numberless *Still stuck?* rail one. The appendix calls it *"the strongest rule on the page"*. **Nothing in the repo states it.** |
| **R-13** | *A route existing is not a door.* | **all ten.** It is the rule the whole CR-085 audit is being run under, it is `CPB-23`'s basis, and `G100` half-implements it. The repo states it in `12-governance/02-decision-log.md` and **nowhere as a rule**. |
| **R-15** | *Position, order and wording never move; a back-link sits under the bar, never inside it.* | **04, 12, 13, 14** — every screen of mine that draws a `← back`. It is also the rule that would settle whether `/forgot-password`'s `← Sign in` may legitimately become a `WhereNext` at the foot (§2, screen 05). |
| **R-18** | *Assistance is a first-class path, not a page behind a sign-in.* | **01, 11.** The missing `STRUGGLING TO PAY?` panel and the missing help-paying door. |
| **R-19** | *The portal is a second channel; every bill is printed regardless.* | **01, 04.** It is the reason the drawing's enrolment screen may say *"You need your account number and last bill"* without apologising for assuming paper. |
| **R-22** | *Three states — loading, empty, failed — can never render as the same picture.* | **01, 10, 11, 13, 14.** ⚠ **THIS IS THE ONE MY LANE MOST NEEDS RULED, AND IT IS ALREADY BREACHED TWICE:** `/visit` renders **failed** where **empty** was meant (**G2**), and `/help` renders **no-match** where **empty** was meant. Both are the picture-collapse this rule names, and there is no rule to cite for either. |
| **R-23** | *No sentence states a fact it does not derive.* | **05, 11, 12.** The reset screen's link lifetime, the article's reading time and the *"We will say so before you send"* promise on `/report` are all this rule's subject, and two of the three have already been decided correctly by a lane reasoning from first principles (§2). A rule would make that repeatable. |

⚠ **The honest summary: three of my screens are built to rules that do not exist.**
`R-07` is cited by name in live source, `R-13` is the premise of the audit
producing this file, and `R-22` is breached twice with nothing to cite.

---

## 6 · B14 rule 39, measured on my forms — `getComputedStyle`, both widths

**Filed as `DEF-CWP-4856`.**

Rule 39 was ratified **today**, 2026-09-11, and says of itself: *"No `--sp-N`
token exists in `tokens.css` today (94 custom properties, not one of them a
spacing scale), so this rule is entirely unbuilt at ratification."*

**Confirmed first:** `getPropertyValue("--sp-1")` … `--sp-7` all return the empty
string on every one of my screens at both widths. There is no scale to measure
against; what follows is what the forms compute instead.

### Field anatomy — ratified **5 / 6 / 20 ≈ 1 : 1 : 4**

Identical at **390 and 1280** on every form (this layout does not change with
width):

| Screen | field | label → input | input → helper | field → field |
|---|---|---|---|---|
| `/enrol` `CWP-016` | `enrol-account` | **4** | — | **12** |
| | `enrol-postcode` | **4** | **17** | **12** |
| | `enrol-lastname` | **4** | — | — |
| `/report` `CWP-006` | `cwp006-where` | **4** | **17** | **16** |
| | `cwp006-notes` | **4** | — | **16** |
| | `cwp006-name` | **4** | — | **16** |
| | `cwp006-phone` | **4** | — | — |
| `/track` `CWP-012` | `cwp012-reference` | **4** | **17** | **16** |
| | `cwp012-second-fact` | **4** | — | — |
| `/sign-in` `CWP-015` | `portal-email` | **4** | — | **12** |
| | `portal-password` | **4** | — | — |
| `/forgot-password` `CWP-019` | `reset-email` | **4** | — | — |

**Against the ruling:**

* **label → input = 4px** everywhere. Ratified **5px**. Off by one, consistently.
* **input → helper = 17px** on all three helpers in the lane. Ratified **6px**.
  **Nearly 3× the ratified figure**, and the single largest miss.
* **field → field = 12px** on `/enrol` and `/sign-in`, **16px** on `/report` and
  `/track`. Ratified **20px**. **Neither value is right, and the two forms in one
  lane do not agree with each other.**
* **Ratio:** ratified ≈ **1 : 1 : 4**. Measured **4 : 17 : 12** on `/enrol`
  (≈ 1 : 4.3 : 3) and **4 : 17 : 16** on `/report` and `/track` (≈ 1 : 4.3 : 4).

### Does the helper READ as attached to the input above it?

The ruling is explicit that DOM order alone is not enough. Measured properly —
helper bottom to the **next field's label top**:

| Screen | input → helper | helper → next label | attachment margin |
|---|---|---|---|
| `/enrol` `enrol-postcode` | 17 | **25** | 1.5× |
| `/report` `cwp006-where` | 17 | **29** | 1.7× |
| `/track` `cwp012-reference` | 17 | **29** | 1.7× |

**The attachment holds, but weakly.** The helper is nearer its input than the next
label, so the ordering half passes. The ruling's own figures give **6 vs 20**, a
**3.3×** margin; my forms deliver **1.5–1.7×**. *"Just the postcode, not the whole
address."* on `/enrol` is 17px under its own box and 25px above *Last name, or
company name* — visibly a helper, but the rhythm the PO asked for is not there.

### The mechanism, named, because it is one line and it moves the whole product

`FormField` is `<div className="flex flex-col gap-1">` — **one gap for all three
relationships**, so label→input and input→helper can never differ by design. The
container gap computes to **4px**.

The other **13px** is not styling at all. Probed in the running page: a bare
`<p class="text-base">` appended to `document.body` computes
`margin-top: 13px; margin-bottom: 13px`. **There is no `p { margin: 0 }` reset in
the portal's stylesheet**, `text-base` is 13px, and the UA default is `1em 0`. The
helper is a plain `<p>` with no `m-0`:

```tsx
{props.helper !== undefined ? (
  <p className="text-base text-neutral-600">{props.helper}</p>
) : null}
```

So **4 + 13 = 17** above, and the same 13 below pushes helper→next-label to
25/29. The codebase already knows about this margin — `ReportRouted.tsx` and
others write `m-0` on every `<p>` by hand — **and `FormField`, the one component
every portal form composes, does not.** The same 13px rides on the field ERROR
paragraph directly beneath it.

⚠ **`/enrol` and `/report` are the best evidence in the product for the
field-anatomy half of rule 39, and both fail it on figures while passing it on
order.** The fix is inside one shared component, which is also why no screen can
be fixed alone.

---

## 7 · Frame problems seen on my screens — **lane 1's**, one line each

Recorded and not pursued, as instructed.

* `DEF-CWP-4468` *"the guest header is two rows in English"* — **did NOT reproduce
  at 1280 on this tenant**: with five nav words (Home · Pay a bill · Report a
  problem · Ask us for something · Track) the bar is one row. It **does** break at
  **390**, where the nav wraps to three lines *and* the utility's own name
  truncates to **`Brazo…`**. The row is still real; its stated width is not.
* The `CWP-###` screen-id chip is `position: fixed` and **overlaps page content**
  — it sits on top of the `Where` helper on `/report` and the rail text on
  `/enrol` at 390. It is behind `VITE_SCREEN_ID_TAG`, so this is a dev-build
  observation, not a customer one.
* `GuestFrame` renders **no nav and no language control at all** when
  `is_live: false`, which is `US-CWP-001` TC-3 and correct — but it is also why
  **G1**'s eight screens have no way back to anything.
