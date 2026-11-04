# CR-085 lane 3 — starting and stopping service, drawing against build

**Scope.** Blueprint section **03**, screens **15–24**, on four routes under
`/:tenant/portal`: `/start-service`, `/start-service/:draft`, `/stop-or-restart`,
`/final-bill`. **Identify only — not one line of product code was changed.**

**Read at.** Branch `claude/hi-0jmv62`, tip `b4063d1e6`. Walked against the shared stack
at `http://127.0.0.1:8401`, tenant **brazosbend**, bundle `index-N9cg-E6T.js`, on
**2026-09-11**, at **1280 and 390**, both, on every screen that could be opened.

The drawing is quoted verbatim in `CR-085-lane3-drawing.md` beside this file.

---

## 0 · WHAT WAS WALKED, AND THE ONE HALF THAT COULD NOT BE — SAY IT FIRST

| Screens | Walked in a browser | At |
|---|---|---|
| **15 · 16 · 17 · 18 · 19** — the whole start-service wizard and the draft resume | **YES**, end to end, including a real submit | 1280 and 390 |
| **20 · 21 · 22 · 23** — the stop wizard | **NO — signed out only.** Source-read in full | 1280 and 390 (signed-out state) |
| **24** — your final bill | **NO — signed out only.** Source-read in full | 1280 and 390 (signed-out state) |

⚠ **THE PORTAL WAS SWITCHED OFF ON THIS STACK AND EVERY PORTAL ROUTE ANSWERED A HOLDING
PAGE.** `GET /settings/portal` read `is_live: false`, so `/brazosbend/portal/start-service`
rendered *"We are not open online yet. Your bills and letters reach you as before; ring the
office for anything else."* and nothing else — `GuestPage.tsx` reads the switch on every
route by design. **It was switched on through the product's own staff control** (Settings →
Customer portal → the LIVE panel's toggle, signed in as `dana@brazosbendutilities.com`),
which is a tenant setting rather than code or data. `data-portal-live` went `off` → `live`.
**It is left ON**, because every other portal lane needs it; say so to the PO before the
stack is handed back.

⚠ **AND THE SIGNED-IN HALF COULD NOT BE OPENED, WHICH IS A GAP IN THIS AUDIT AND IS
STATED RATHER THAN PAPERED OVER.** The one account on this tenant — `AC-2026-00001`, Elena
Rivera, 1408 Bluestem Ln · Unit A — **already holds a portal credential**: `/enrol` refuses
it with `reason: use_reset` (*"Try resetting your password instead."*), which is the answer
for an account that is already enrolled. **That password is recorded nowhere in the repo**;
`10-scripts/` documents only `pine-hill`'s `ana@example.test`, and this stack has exactly
one tenant and it is not pine-hill. The enrolment code is a six-digit value stored as a
digest and queued to a notification the staff app has no screen for, so there is no product
path to it either. **Nothing was guessed at, and no credential was created or reset on a
shared stack.** The parent lane should publish a portal login for `brazosbend`, or seed one;
until then s20–s24 have never been opened with data on this stack by anybody.

**What the signed-out state actually renders, measured at 1280 and 390 — and it is a
finding:** `/stop-or-restart`, `/final-bill` and `/account` all draw the SAME grey failure
panel: *"Failed · We could not open this page. · You're signed out. Sign in again to
continue."* with **Retry · Download error report · Cancel**. That is the blueprint's
**CPB-17** exactly (*"a grey failure panel reading We could not open this page… Download
error report. True of every signed-in screen, not just one"*), and it reaches my screens
even though CPB-17's own Screens column lists only 53 and 54. **`Download error report` is
an engineer's control on a customer's screen**, and the panel offers no way to sign in.

---

## 1 · SCREEN 15 · Start service · 1 Address — `CWP-008`, `/start-service`

**Walked at 1280 and 390. No horizontal overflow at either width** (`scrollWidth 390`,
`innerWidth 390`, zero elements past the right edge).

### What matches
The step bar is there and says **Step 1 of 4** in substance — four named steps, the first
current. The availability answer is priced. The unmatched address is **not** a refusal —
*"We do not hold that address yet, so a person will look at it. You can still apply."* with
the Continue control still live, which is the drawing's **ADDRESS NOT RECOGNISED** state
answered in the product's own words. `Check →` is disabled with its reason on `title`
(*"Type an address first."*, four words, inside B14 rule 33's cap).

### What differs

| # | Kind | Drawn | Built |
|---|---|---|---|
| 15.1 | STRUCTURE | **Four address fields** — `Street address` / `Town` / `ZIP code` / `Is there a unit or apartment number?` | **Two** — one free-text `Address *` and the unit box. The town and the ZIP are not asked |
| 15.2 | CONTROL | **`📍 Use my location`** beside `Check this address` | Absent |
| 15.3 | COPY | Button reads **`Check this address`** | **`Check →`** |
| 15.4 | STRUCTURE | The answer is a **service list with words** — `💧 Water · Required`, `🚿 Sewer · Required with water`, `Trash · Optional · $18.00 a month` | A four-column **table** — `SERVICE · AVAILABLE · TO CONNECT · DEPOSIT` — with `YES`/`NOT HERE` chips. Nothing says which services are REQUIRED, which are OPTIONAL, or what a service costs per month |
| 15.5 | COPY | **`Electric at this address is supplied by Pedernales Electric, not by us. You will need to contact them separately.`** — the drawing's caption calls this out as *"saves a second search and a call"* | Absent. A service we do not carry renders as a greyed row saying `NOT HERE` and names nobody |
| 15.6 | STRUCTURE | Rail reads **`ALREADY A CUSTOMER?` — *"If you are moving within our area, signing in first carries your details and your payment method across."* with a `Sign in` link** | Rail reads **`ALREADY SERVED?`** — a different question (*is somebody living there now*) — and **carries no sign-in link at all.** The drawing's point is that signing in first pre-fills the form; the built rail never offers it |
| 15.7 | COPY | Sub-line **`Step 1 of 4 · about 5 minutes · nothing is saved until step 4`** | **`Check before you fill anything in.`** No time estimate, no "nothing is saved yet" |
| 15.8 | COPY | Step names **`1 Address · 2 When · 3 About you · 4 Check`** | **`The address · When · About you · Check and send`** |
| 15.9 | ⛔ DEFECT | The **NO ESTIMATE AVAILABLE** state is drawn as *"The panel is absent, not shown with a dash"* | **`IF YOU APPLY`** renders **`— deposit on your first bill.`** — a sentence that begins with an em dash. Filed |
| 15.10 | RULE | Unratified **R-07**, *one filled button per screen* | After a successful check there are **two** `variant="primary"` buttons on screen at once: `Check →` and `Continue →` |

### The four drawn states

| Drawn state | Built |
|---|---|
| **NOT OUR AREA** — *"says so immediately and names who does serve it"* | The unmatched sentence is drawn; **nobody is named** |
| **ADDRESS NOT RECOGNISED** — *"offers the nearest matches rather than refusing"* | Sentence only; **no nearest matches** |
| **ALREADY HAS SERVICE** — *"somebody else holds it, or you do. Routes to sign-in or the phone"* | Not drawn. The server sends `job: "move_in"`; the screen never says so and never routes |
| **UNIT NEEDED** — *"a multi-unit building asks which unit"* | The unit box is **always** shown and never required; the building's unit count is not read |

---

## 2 · SCREEN 16 · Start service · 2 When — `CWP-047`, `/start-service/:draft`

| # | Kind | Drawn | Built |
|---|---|---|---|
| 16.1 | ⛔ STRUCTURE | Title **`When would you like it on?`** with sub-line **`1841 Quarry Hill Ct, Silver Creek, TX 78611 · step 2 of 4`** | **No heading of any kind.** Measured in a browser: `h1` count **0**, `.page-header` nodes **0**. The page goes navigation → step bar → `WHEN WOULD YOU LIKE IT ON?` as an 11px section title. Filed |
| 16.2 | COPY | **`Earliest is 09/10/2026 — we need three working days`** — a real date, before they type | **`At least three working days from today.`** — the rule, not the date. The drawing's caption argues for the date specifically: *"one sentence that prevents a rejected form"* |
| 16.3 | COPY | **`Is it a home or a business?`** | **`Are you a person or a business?`** |
| 16.4 | CONTROL | **`WHICH SERVICES?`** — tickable, required ones ticked and locked WITH the reason (*Required at this address*, *Required with water · charged on 90% of your water*), the optional one priced (*Trash · weekly collection, Tuesdays · Optional · $18.00 a month*) | **`WHICH SERVICES`** — *"These are the services this address takes, and there is nothing to choose."* and two rows reading `Included`. No required/optional distinction, no reason, no monthly price, no collection day |
| 16.5 | ⛔ COPY | **`WHAT IT COSTS TO START`** — `Connection fee $45.00`, `Deposit  Decided at step 3`, `On your first bill  $45.00 + any deposit` | Three bullets: `$90.00 before we start.` / **`— deposit on your first bill.`** / `About 3 working days.` The middle one is the em-dash sentence again. Filed |
| 16.6 | STRUCTURE | **`ON THE DAY`** panel — *"Nobody needs to be home unless the water is shut off at the street. If it is, we will call to arrange a time."* | Absent |
| 16.7 | STRUCTURE | **`A TYPICAL MONTHLY BILL HERE — about $96`** — the drawing calls it *"the question behind the question"* | Absent |
| 16.8 | CONTROL | — | **`Save and finish later`** is a **held button** whose reason is *"Already saved as you type."* — a control that can never be pressed, over a promise that is already kept. The drawing's s19 draws **`Save and come back later`** as a real control. Hard-won law 2's mirror: a dead control on a live screen |
| 16.9 | ⛔ CONTROL | The start date is the step's whole question | `When do you want service to start?` is marked **`*` required** and **`Continue →` is enabled with it empty** (measured: `disabled=false`, no `title`). Filed |

### The four drawn states
**DATE TOO SOON** — not built; no earliest date is stated or enforced on the screen.
**BUSINESS CHOSEN** — the kind selector exists; the service list and fees do **not** change and the screen does not say they did.
**NO OPTIONAL SERVICES** — effectively the only state built: the list is shown as facts. This one matches.
**NO ESTIMATE AVAILABLE** — *"the panel is absent, not shown with a dash"*; built shows the dash (15.9/16.5).

---

## 3 · SCREEN 17 · Start service · 3 About you — `CWP-047`

| # | Kind | Drawn | Built |
|---|---|---|---|
| 17.1 | ⛔ STRUCTURE | Title **`About you`**, sub-line **`Step 3 of 4 · this is the only step that needs a document`** | **No heading.** `h1` count **0** |
| 17.2 | COPY | **`Email — where your bill will be sent`** · **`Phone`** | **`Email`** · **`Mobile`** |
| 17.3 | STRUCTURE | **`Mailing address, if different`** with *Same as the service address* | Absent entirely. The drawing's *WHY WE ASK FOR EACH OF THESE* names it first — *"Name and address · Whose account it is"* |
| 17.4 | STRUCTURE | **`WHY WE ASK FOR EACH OF THESE`** — a five-row panel (Name and address · Email · Phone · Date of birth · Photo ID), each with its reason. The drawing's caption: *"the difference between suspicion and cooperation"* | Absent. One helper survives, under the date of birth — and it says something different: *"We use this to check whether you have held an account with us before."* where the drawing says *"the credit check, which decides the deposit"* |
| 17.5 | CONTROL | **The document drop** — drag-and-drop, `Choose a file`, `📷 Take a photo`, formats and the 10 MB limit stated BEFORE the attempt, an added file listed with its size and a way to remove it | A `PhotoPicker` **held** with *"Documents come to the counter."* — no file input at all. This is a signed deferral (PO 2026-08-08, DF-4) and is correctly a stated absence, **but the drawing's whole argument for this step is the document**, so the step that the drawing calls *"the one people abandon"* no longer has the thing they abandon it over |
| 17.6 | CONTROL | **`Send it later instead` / `Send my ID later`** — *"the escape hatch, offered as a real option rather than a failure"* | Not applicable while 17.5 is held — recorded so the next lane does not read its absence as an oversight |
| 17.7 | STRUCTURE | **`YOUR DOCUMENTS ARE PRIVATE`** rail — *"An ID is used to verify you and is deleted once service starts."* | Absent |
| 17.8 | ⛔ CONTROL | — | **Five fields marked `*` required** — First name, Last name, Email, Mobile, Date of birth — and **`Continue →` is enabled with all five empty** (measured `disabled=false`). Filed |

### The four drawn states
**FILE TOO LARGE** / **WRONG FORMAT** — unreachable while the picker is held.
**DEPOSIT REQUIRED** — *"shown at step 4 with the reason and what would remove it"*; built shows an em dash and no reason (§4).
**SIGNED IN** — *"Name, email, phone and mailing address arrive pre-filled from the account"*; **not built** — the guest wizard never reads a session, and there is no sign-in door on step 1 either (15.6).

---

## 4 · SCREEN 18 · Start service · 4 Check — `CWP-009`, `/start-service/:draft`

| # | Kind | Drawn | Built |
|---|---|---|---|
| 18.1 | ⛔ STRUCTURE | Title **`Check this, then send it`**, sub-line **`Step 4 of 4 · nothing has been submitted yet`** | **No heading.** `h1` count **0** |
| 18.2 | STRUCTURE | Read-back in two blocks — **`SERVICE ✎ CHANGE`** and **`YOU ✎ CHANGE`** — each row naming the plan or the basis (*Water · Residential Standard · tiered*, *Sewer · 90% of the water you use*, *Trash · Weekly, Tuesdays · $18.00 a month*) | Two blocks, right shape, right change links. The service rows read **`Electric, Water`** on one line — no plan, no basis, no price |
| 18.3 | DATA | **`Starting  Monday, Sep 14, 2026`** — the weekday, because it is a move | **`Start on  09/23/2026`** — the tenant's own format, correctly (`usePortalDate`), and no weekday |
| 18.4 | ⛔ DATA | **`WHAT YOU WILL BE CHARGED`** — `Connection fee $45.00`, `Deposit $0.00`, `On your first bill $45.00`, and **the verdict with its reason**: *"No deposit is needed — the credit check passed. Nothing is taken today; both appear on your first bill, around Oct 5."* | **`WHAT YOU WILL PAY`** — `To pay before we start $90.00`, `On your first bill —`. **No deposit verdict and no reason.** The drawing's caption: *"THE DEPOSIT VERDICT, HERE. With its reason… closes the question this whole flow raises at step 3, at the moment somebody is deciding whether to press"* |
| 18.5 | STRUCTURE | **`WHAT HAPPENS NEXT`** — four **dated** steps: *1 · We confirm by email within one working day · 2 · We turn the water on, on Sep 14 · 3 · Your first bill arrives around Oct 5 · 4 · You can create a sign-in as soon as we confirm* | **`WHAT THIS WILL DO`** — four **undated** sentences: *Sends your application to us. · Records how you want your bills sent. · Nothing is charged today. · We answer within two working days.* Nothing says when service starts, when the first bill comes, or that a sign-in follows |
| 18.6 | CONTROL | Consent is **`I agree to the terms of service`**, and **`Send is disabled until the box is ticked`** | Consent is **`How we send your bills — Send my bills and letters by email`** (paperless, `BR-CWP-087`), ticked by default, and **Send is never disabled**. These are two different consents; the terms-of-service one does not exist |
| 18.7 | ⛔ REFUSAL | — | Pressing **`Send my application ✓`** on an empty form returns **`422 VAL-001 portal.application.stepIncomplete params={"step":"name"}`** and the screen renders **`Finish an earlier step first.`** — five words that name **no step and no field**, over a read-back that is visibly showing `Applicant —`, `Email —`, `Mobile —`. **The server sends the step; the catalogue string has no `{{step}}` placeholder, so it is dropped.** `services.py:480` carries the comment *"⚠ THE DRAFT IS KEPT (US-CWP-013 TC-5). The refusal names the step."* — hard-won law 1 exactly: a comment claiming a guarantee that is not there. Filed |
| 18.8 | RULE | Unratified **R-15**, *a back-link sits under the bar, never inside it* | At 390 the drawing puts **`← Final bill`**-style back-links under the bar on s20–s24; the built wizard's only back is a footer `← Back` button. This is r10 rule 1 followed deliberately (the code says so) and R-15 unmet — **a conflict between a ratified convention and an unratified drawn rule**, recorded, not resolved |

### The four drawn states
**DEPOSIT REQUIRED** — not built (18.4). **ID NOT ATTACHED** — not applicable (17.5).
**ADDRESS TAKEN MEANWHILE** — *"refused with the reason and the phone number; nothing typed is lost"*; the draft IS kept, but no such refusal exists.
**SENT** — built and correct: `Your application is with us`, `Your reference`, `WHAT HAPPENS NOW`.

---

## 5 · SCREEN 19 · Finish starting service — `/start-service/:draft`

The resumed head **is** built and is drawn only when the draft was already there —
*`START SERVICE` / `Picked up where you left off` / `You started this for 1408 Bluestem Ln,
Katy, TX 77494.`* — which is the drawing's own first line. Confirmed in a browser.

| # | Kind | Drawn | Built |
|---|---|---|---|
| 19.1 | DATA | **`started Sep 6`** and **`Held until Oct 6`** and **`We keep an unfinished request for 30 days — this one until Oct 6.`** | **Absent, deliberately and correctly.** `GET portal/public/applications/{token}` serves neither a created date nor an expiry and no retention rule for a draft exists anywhere; the code says so in as many words. The drawing's caption calls the expiry *"the point"* — **so the gap is in the SERVER and the drawing is a specification for it**, not a screen fault |
| 19.2 | DATA | **`Two things left · About 3 minutes`** | Absent — same root as 19.1 |
| 19.3 | STRUCTURE | **`ALREADY DONE · NOTHING TO REDO`** rail with three ticked rows and change links | Built as **`ALREADY DONE`** with up to **two** rows (address, start date) and a change link on the second. The drawing's third row — *Services · Water · Sewer · Trash* — is not in the rail |
| 19.4 | CONTROL | **`📷 Take a photo`** — *"the last is the one that matters on a phone, because the ID is in the person's hand"* | Held (17.5) |
| 19.5 | DETAIL | **Still-needed fields carry an accented border and one line underneath** — *"still needed, for the credit check"* | Not built; every field looks the same whether it is answered or not |
| 19.6 | BEHAVIOUR | *"IT OPENS ON THE FIELDS, NOT ON A CHECKLIST"* | **Correct** — `firstUnfinishedStep()` opens the first step that is not complete. Walked: a complete draft reopened on step 4, an incomplete one on the step it stopped at |
| 19.7 | STRUCTURE | One rail | **The service address is printed TWICE, in two stacked rail panels.** Measured on a resumed draft: `ALREADY DONE · Address · 1408 Bluestem Ln, Katy, TX 77494` sits directly above `THE ADDRESS · Service address · 1408 Bluestem Ln, Katy, TX 77494 · Services here · Electric, Water`. The drawing has one `ALREADY DONE` panel |

### The four drawn states
**EXPIRED** / **DATE NOW PAST** — not built (no expiry exists; 19.1).
**ADDRESS TAKEN MEANWHILE** — not built.
**NOTHING LEFT BUT THE ID** — not reachable while the picker is held.

---

## 6 · SCREENS 20–23 · Stop service — `CWP-052`, `/stop-or-restart` — SOURCE READ ONLY

⚠ **THE BUILT FLOW IS THREE STEPS AND THE DRAWING IS FOUR.** Built:
`What you need · When · Check`. Drawn: `1 Which property · 2 When · 3 Final bill · 4 Check`.

| # | Kind | Drawn | Built |
|---|---|---|---|
| 20.1 | STRUCTURE | Step 1 is **`Which property`** only, and **is skipped for a one-property customer** — *"the flow opens on When and says step 1 of 3"* | Step 1 is **`What you need`** — it holds the property chooser (only when the customer has more than one) **and** *are you coming back*. It is never skipped. **The code states the divergence and its reason**, which is the right way to differ from a drawing |
| 20.2 | ⛔ CONTROL | **Three choices, in the customer's own words** — `Stop all services — the account closes and a final bill is sent` · `Stop trash only — water and sewer stay on, the account stays open` · `Pause for a season — $25.00, the account stays open, nothing is billed for usage`, with a rail naming the three situations (*Moving out · Away for the winter · Do not want the trash service*) and the two prices ($45.00 to reconnect vs $25.00 to pause) | **Two choices, and neither is any of the three**: `Yes, and I know the date` / `Not yet, I have no date`. **There is no way to stop ONE service, no way to close the account, and no seasonal pause product.** The whole of the drawing's step-1 guidance panel — the part that routes a customer without making them price it themselves — has no counterpart |
| 21.1 | COPY | **`PICK YOUR MOVING DAY, NOT THE DAY BEFORE` — *"You are billed up to and including Sep 30, and the water stays on all that day. People commonly choose the 29th and then have no water while they load the van."*** The drawing's caption says this sentence is the point of the screen | Helper reads **`The supply stays on all of this day.`** — one clause of it. The consequence (*"no water while loading the van"*) and the heading are absent |
| 21.2 | COPY | **`Earliest is 09/11 — we need three working days`** | Absent. No earliest date is stated or enforced |
| 21.3 | STRUCTURE | **`ON THE DAY`** — *We read your meter Sep 30* · *Does anyone need to be home? No* · *Is the water turned off at the street? Only if the property will be empty* | Absent |
| 21.4 | STRUCTURE | **`IF YOU ARE COMING BACK`** rail, offering the pause again with `Go back and pause instead` | The rail is the **cost comparison** (`Would moving out be cheaper?`), which answers a related question and is arguably better — it composes the kit where the drawing writes prose, and its verdict varies (`For this long, closing the account is cheaper`). **Noted, not filed** |
| 21.5 | CONTROL | **`Why, if you would like to say`** is a **`<select>`** reading *Moving out* | A free-text `TextInput`. **Already filed as `DEF-CWP-4203` and still true** |
| 22.1 | ⛔ STRUCTURE | **A WHOLE STEP** — *Where should the final bill go?* · `Send it to this address` / `Send it to a new address` with street, town, state+ZIP and email · **`YOUR DEPOSIT COMES BACK $150.00`** · *"less anything owed, within 30 days of it being issued — which is the rule, not our choice"* · **`Send the refund to  Bank account ····4417`** · *"WHY WE ASK TWICE"* | **Absent.** `POST accounts/{id}/stop-or-restart/ask` accepts a stop date, a restart date, a reason and a contact — no address, no refund destination, no deposit — and `GET stop-or-restart` serves no deposit figure either. **The absence is the honest answer** and the code says so. ⚠ **But it is recorded ONLY in a code comment**, which is hard-won law 1 and is `DEF-CWP-4203`'s own escape reason (*"A DEFERRAL WRITTEN AS A CODE COMMENT IS NOT TRACKED BY ANYTHING"*). Filed as a record defect |
| 23.1 | COPY | **`Check this, then confirm`** · sub-line *Step 4 of 4 · nothing is stopped until you press the button* | `CHECK THIS, THEN CONFIRM` as a section title, and *Nothing stops until you press the button below.* Substance present; it is a section title, not a page heading |
| 23.2 | ⛔ STRUCTURE | **`WHAT HAPPENS NEXT` — four dated steps**: *We read your meter Sep 30 · Your final bill is sent around Oct 5 · It is due around Oct 20 · Your deposit is returned by Nov 4* | Absent. Nothing on the wire carries those dates. Same root as 22.1 and recorded in the same comment |
| 23.3 | STRUCTURE | **`WHAT YOU WILL OWE`** — `Service to Sep 30 · estimated $86.20`, `Move-out final read $20.00`, `Deposit held −$150.00`, `Expected back to you $43.80`, *"An estimate — the final read decides it."* | Absent |
| 23.4 | STRUCTURE | **`AUTOPAY IS ON`** amber panel — *"Your final bill will be taken automatically on its due date, from bank ····4417. If that account is closing with your move, change it now."* with `Change autopay`. The drawing calls it *"the one nobody thinks of"* | Absent |
| 23.5 | COPY | **`You can cancel this any time up to Sep 29.`** | Absent |
| 23.6 | COPY | Consequence heading | **`What this would mean`**; every other consequence box in the portal says **`WHAT THIS WILL DO`**. **Already filed as `DEF-CWP-4203` and still true** |
| 23.7 | COPY | Commit reads **`Stop service on Sep 30`** | **`Request this ✓`** — held with *"Give us a stop date first"* / *"We need a phone number"* |
| 23.8 | — | — | **`HOW WE REACH YOU`** (name · phone · email) is not in the drawing and must stay: it is the fix for *"every stop request was being refused"* (`1a95f31c`). **Verified present in source**; the phone is required and the commit is held with its reason when it is empty. **Not verified end to end in a browser** — see §0 |

---

## 7 · SCREEN 24 · Your final bill — `CWP-032`, `/final-bill` — SOURCE READ ONLY

| # | Kind | Drawn | Built |
|---|---|---|---|
| 24.1 | STRUCTURE | Heading `Your final bill`, sub-line *1408 … · account closed Sep 30, 2026* | Heading **now present on every branch** (`DEF-CWP-4190` fixed in code — see §9). The sub-line naming the address and the closing date is **not** built |
| 24.2 | STRUCTURE | **The refund is the headline** — `COMING BACK TO YOU $63.80 · to bank ····4417, by Oct 30` | Built as a lead `KpiTile` reading `COMING BACK TO YOU` / `STILL TO PAY`. **The destination and the date are not on the tile** |
| 24.3 | DATA | **The bill is itemised per service** — *Electric · 412 kWh $62.88*, *Water · 3 kgal $18.35*, *Sewer · 2.7 kgal $13.50*, *Move-out final read $20.00*, **`Trash · stopped Sep 30, 20 of 30 days −$28.53`** — the drawing's caption says the proration is itemised *"since a part-month charge is the commonest final-bill dispute"* | **One line**: `Service to <date>` and a total. No services, no quantities, **no proration line at all** |
| 24.4 | STRUCTURE | **`WHERE WE SENT IT` — 220 Lakeview Dr… the forwarding address you gave when you stopped service**, with **`That is wrong — change it`** | Absent — and it cannot exist while 22.1 is absent, which is the same gap seen from the other end |
| 24.5 | CONTROL | **`↓ Download the final bill`** | Built (`ErrandLink` to `/bills/{number}/document`), present only when the bill carries a number |
| 24.6 | COPY | *"This account is closed and no further bills will be sent."* | Absent |
| 24.7 | DATA | Deposit block — `Deposit held since Jun 2, 2026 −$150.00`, `Coming back to you $63.80`, and the 30-day rule *"as the rules require"* | Built, including `Interest on your deposit`. The **30-day rule sentence** is replaced by *"Allow ten working days."* — a different promise |

### The four drawn states
**YOU OWE US** — built (`STILL TO PAY` / `You owe us`, with a due date).
**REFUND SENT** — not distinguished; one refund sentence covers both.
**NO DEPOSIT** — built correctly: the deposit rows are absent, not `$0.00`.
**ESTIMATED FINAL READ** — not built; no sentence says the figure may change once the meter is read.

---

## 8 · B14 RULE 39 — MEASURED, NOT EYEBALLED

`getComputedStyle` + `getBoundingClientRect` in Chromium on the running bundle, **identical
at 1280 and at 390**. The scale is `--sp-1 4 · --sp-2 8 · --sp-3 12 · --sp-4 16 · --sp-5 20
· --sp-6 24 · --sp-7 32`.

### The wizard anchors — both miss

| Anchor | Rule 39 | Measured | Where it comes from |
|---|---|---|---|
| **wizard step** | **16 × 20** | **padding `8px` on every side**; step box `259 × 41` at 1280, `171 × 41` at 390 | `primitives.tsx` `Stepper` → `<li className="… p-2 …">` |
| **wizard step gap** | **12** | **`8px`**, row and column (`gap-2`) | `<ol className="mb-4 grid grid-cols-4 gap-2 max-md:grid-cols-2">` |
| **rail margin-bottom** | **24** | **`16px`** (`mb-4`) — and the rail's own column also carries `gap-4`, so two rail panels sit **32px** apart while one sits 16px from the bottom | `Panel` + `TwoCol`'s `flex flex-col gap-4` |

### The field anatomy — all three miss, and the helper is the one that matters

| Gap | Rule 39 | Measured | Ratio |
|---|---|---|---|
| label → input | **5** | **4** | — |
| input → helper | **6** | **17** | — |
| field → field | **20** | **16** | — |
| | rule's shape ≈ **1 : 1 : 4** | built ≈ **1 : 4.25 : 4** | the helper is pushed four times too far from its input |

**Why 17 and not 4.** `FormField` is `flex flex-col gap-1` — 4px between every child, so the
label, the input, the helper and the error all sit at one distance. The extra 13px is
`global.css:78`, **`p { margin-block: 1em }`**, which at the helper's 13px font size is
exactly 13px. **13 is not on the scale at all**, and it is applied to every `<p>` in the
product, so no per-screen change can reach it.

**The attachment test, measured on the one field that has a helper and a neighbour**
(`requested_start` on step 2): the helper sits **17px below its own input** and **29px above
the next field's label**. Rule 39 asks for 6 above and 20 below — a 1:3.3 attachment; built
is **1:1.7**. It still reads upward, but only just, and the label is glued four times tighter
to its input than the helper is, which inverts the shape the rule describes.

**One off-scale value found in the wizard subtree and it is not mine:** `px-[9px] py-[3px]`
on the screen-id badge (`PortalScreenIdTag.tsx`). Frame; noted for lane 1 only.

---

## 9 · RE-VERIFYING MY SLICE OF THE OPEN `DEF-CWP` ROWS

The two audits are dated 2026-09-05/06 and say *"before citing a row here as current, open
the screen."* Nine rows in the register touch these ten screens. **Two of them are fixed in
the code and still read `open`.**

| Row | Register says | What the code says today | Verdict |
|---|---|---|---|
| **`DEF-CWP-4190`** — CWP-032 draws no heading on the branch that has a final bill | `open` | `FinalBill.tsx:145` now renders `{head}` in the success return, with a comment naming this defect. `13-wireframe-delta.md` row 32.1 reads **✅ FIXED 2026-09-06** | **FIXED — the register row is stale.** Close it |
| **`DEF-CWP-4193`** — CWP-032 prints four raw machine dates | `open` | All four go through `usePortalDate` (`showDate`). Delta row 32.9 reads **✅ FIXED 2026-09-06** | **FIXED — the register row is stale.** Close it |
| **`DEF-CWP-4191`** — the settling-up column does not add up when the account owed something | `open` | `FinalBill.tsx` still reads **`bill.service_charges` only**; `charges` is served and unread; no line names the arrears | **STILL OPEN, exactly as filed** |
| **`DEF-CWP-4192`** — *Query this reading* can never draw on a refund bill | `open` | The branch is still gated on `query_reading_open`, which is `not settled`, and a refund settles on sight | **STILL OPEN, exactly as filed** |
| **`DEF-CWP-4199`** — no account can produce the stop comparison | `open` | Unchanged in `sample_data.py`/`rating/seams.py`. ⚠ **And it is now worse on this stack than the row says**: brazosbend holds **one** account and **no portal credential anyone can use**, so `CWP-052` cannot be opened at all here | **STILL OPEN, and widened** |
| **`DEF-CWP-4203`** — the Why box, and the consequence heading | `open` | `StopOrRestart.tsx` still uses a `TextInput` for the reason; `portal.stopRestart.consequenceHeading` is still *"What this would mean"* | **STILL OPEN, both halves** |
| **`DEF-CWP-4204`** — wave I prints raw machine dates | `open` | **`StopOrRestart.tsx`'s half is fixed** — it imports `usePortalDate` and the trace names this defect. The other four wave-I files are not mine | **PARTLY FIXED — my half is done** |
| **`DEF-CWP-3986`** — six drawn components never built | `partially-fixed` | **`KpiRow` and `KpiTile` now exist** in `primitives.tsx` and `FinalBill.tsx` composes `KpiTile`. `DialInput` exists. `FileDrop`/`CameraCapture` (s17, s19) still do not, and cannot while the upload deferral stands | Still `partially-fixed`, correctly |
| **`DEF-CWP-4654`** — stop service unreachable | `fixed` | **Confirmed still fixed:** two doors, `YourAccount.tsx:271` and `MyDetails.tsx:299`. `/final-bill` has one (`YourAccount.tsx:270`); `/start-service` has two, and the landing-page card was confirmed **live, not held**, in a browser at 1280 and 390 | **Stays fixed** |

**`1a95f31c`'s finding — *every stop request was being refused* — is still fixed in source:**
step 3 sends name, phone and email, the phone is required, and the commit is held with
*"We need a phone number"* when it is empty. **Not re-proved end to end** (§0).

---

## 10 · THE 24 SPECIFICATIONS — WHICH TOUCH THESE TEN SCREENS

Read out of the blueprint's own register (section 12, pages 111–113). Every row's `SCREENS`
column was checked against 15–24.

| Spec | Touches my screens? | State |
|---|---|---|
| **CPB-23** — *Every screen carries its How-you-get-here row* | **YES — `all`.** Nine of my ten cards carry the `COMMITMENT CPB-23` chip; screen 20 carries `NO COMMITMENT` | **PART-BUILT, and the missing half is the DOCUMENT rather than the product.** All four of my routes have real inbound links read out of the source (§9). What is missing is the row in the blueprint, on 9 of my 10 screens |
| **CPB-17** — *A signed-out visitor at a signed-in address is offered a sign-in* | **YES in substance**, though its Screens column lists only 53 · 54 — the row itself says *"True of every signed-in screen, not just one"* | **NOT BUILT.** Measured: `/stop-or-restart`, `/final-bill` and `/account` all draw *Failed · We could not open this page · Download error report* at both widths |
| **CPB-01 … CPB-16, CPB-18 … CPB-22, CPB-24** | **NO.** Their Screens columns are 1, 3, 6, 7, 8, 32, 34, 35, 36, 37, 40, 43, 44, 47, 48, 50, 51, 52, 53, 54, 55, 56, 60 — none of 15–24 | — |

**So: one specification is mine outright (CPB-23), one reaches me through its own escape
clause (CPB-17), and twenty-two do not touch these screens at all.** Section 03's commitment
block says `None.`, which contradicts the nine chips inside it (see the drawing file).

---

## 11 · THE 12 UNRATIFIED DRAWN RULES — WHICH THESE SCREENS DEPEND ON

The blueprint's appendix A marks **12 of its 24 rules `NO HOME — stated only here`**:
**R-04, R-05, R-06, R-07, R-09, R-10, R-13, R-15, R-18, R-19, R-22, R-23.** They are
proposals. **Eight of the twelve are load-bearing for these ten screens:**

| Rule | Stated as | How these screens depend on it | Met today? |
|---|---|---|---|
| **R-05** | *Amount due and due date appear in the same place on every screen* | s20–s24 inherit it from the account bar; s15–s19 have no account, so it cannot apply to the guest wizard — **which is itself a gap in the rule** | Frame (lane 1) |
| **R-06** | *Never ask a customer to compute — show the difference, not two numbers* | s16's *typical monthly bill*, s23's *what you will owe*, s24's proration line. **`DEF-CWP-4191` is precisely an R-06 breach** | **NO** — 16.7, 23.3, 24.3 |
| **R-07** | *One filled button per screen* | s15 shows **two** primary buttons at once once an address is checked | **NO** — 15.10 |
| **R-10** | *Bad news never appears without the way out beside it* | s24's *you owe us*; s18's refusal; s21's *date already billed* | Partly — s24 offers a due date and a document, not a way to pay |
| **R-13** | *A route existing is not a door* | The whole door question for my four routes | **YES** — all four have real doors |
| **R-15** | *Position, order and wording never move; a back-link sits under the bar, never inside it* | The drawing puts `← My details`, `← When`, `← Final bill`, `← Home` under the bar at 390 on s20–s24 | **NO, and deliberately** — r10 rule 1 says a footer `← Back` inside a stepper means *previous step*. A ratified convention and an unratified drawn rule disagree; **the PO should settle it, not a lane** |
| **R-22** | *Three states — loading, empty, failed — can never render as the same picture* | s24 has three distinct sentences; s15 distinguishes checked/served/unmatched | **YES** on s24; s16–s18 have no loading or failed state of their own |
| **R-23** | *No sentence states a fact it does not derive* | 19.1's absent expiry, 22.1's absent forwarding address, 23.2's absent four dates are **all R-23 being obeyed** — the product declines to print a date it cannot derive | **YES**, and it is the reason several of §6's gaps exist |

**R-04, R-09, R-18, R-19** do not bear on these screens.

⚠ **None of the eight is law.** Where a build differs from one of them — 15.10, 16.7, 23.3,
24.3, and the R-15 conflict — **that is a proposal unmet, not a defect**, and it is written
here so nobody "fixes" a screen to an unratified rule and nobody closes the gap by silently
adopting one.

---

## 12 · WHAT WAS FILED

| Id | Severity | One line | Where |
|---|---|---|---|
| **`DEF-CWP-4875`** | medium | The first two screens of the move-in journey print **`— deposit on your first bill.`** — a sentence beginning with an em dash — because a `kind: "none"` money cell is interpolated into a sentence instead of the panel being absent | 15.9 · 16.5 |
| **`DEF-CWP-4876`** | medium | **Steps 2, 3 and 4 of Start service carry no heading at all** — `h1` count 0 and `.page-header` 0, measured at 1280 and 390 — and the two branches that DO have one are the two an applicant reaches least | 16.1 · 17.1 · 18.1 |
| **`DEF-CWP-4877`** | high | **Six fields marked required gate nothing**, the applicant reaches the commit with an empty form, and the refusal — *Finish an earlier step first.* — **drops the step the server sends in `params`** | 16.9 · 17.8 · 18.7 |
| **`DEF-CWP-4878`** | low | **The two wizards miss every one of B14 rule 39's anchors**, and the helper sits 17px from its input where the rule asks 6 | §8 |
| **`DEF-CWP-4874`** | medium | **The stop flow's missing third step and its four-date timeline are recorded only in a code comment** — no question, no defect row, no plan entry | 22.1 · 23.2 |

**Two rows the parent lane should CLOSE, not re-verify:** `DEF-CWP-4190` and `DEF-CWP-4193`
are both fixed in the code and both still read `open` (§9).

**Not filed, deliberately:** the screen-id badge (frame, and `13-wireframe-delta.md` 32.12
already rules it not a defect); the heading bar, the menu, the account line and the universal
spacing scale (lane 1); every difference in §11 that exists only against an unratified rule.

⚠ **FOUR OF THESE FIVE IDS WERE RENUMBERED BEFORE THEY WERE PUSHED, AND IT IS WORTH ONE
LINE.** `file_defect.py` allocated `4859`, `4866`, `4867`, `4868` against the remote and
every allocation was correct at the moment it was made; by the time this lane came to push,
**a sibling lane had taken all four** — `4859` by the bills lane and the other three by
`CR-085 step 1 lane 6 (paying)`. `allocate.py defect --verify` at push time is what found
it, which is exactly the moment CLAUDE.md law 11 says to run it, and the register was
rebuilt from the pinned tip with the four rows renumbered to `4875`–`4878` rather than
pushed on top. **The prefix was proved byte-identical to the tip before the push.**
