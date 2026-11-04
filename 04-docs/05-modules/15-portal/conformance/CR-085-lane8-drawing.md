# CR-085 lane 8 — the drawing, quoted

**Scope.** Seven routes under `/:tenant/portal/` — `/usage`, `/readings`,
`/equipment`, `/requests`, `/requests/:reference`, `/ask`, `/ask-a-question`.
**Drawing:** `05-prototype/SMARTBillHub Customer Portal Blueprint.pdf`
sections **08 "What you used"** (pp. 87–93) and **09 "Asking us something"**
(pp. 93–99), read 2026-09-11 with `10-scripts/pdf/pdf_text.py`
(`\xa0` normalised to a space before matching — the text layer joins words with
it, and a naive grep returns FALSE ABSENCES).

**⚠ EVERY ONE OF THESE SEVEN SCREENS HAS TWO DRAWINGS AND THEY DISAGREE.** The
captured pack (`04-docs/05-modules/15-portal/wireframes/CWP-0NN.png`) is the
older one that the build was made from; the blueprint above is the newer one and
is what this lane was pointed at. **B14 rule 37 decides what to do about it:**
a figure drawn in a wireframe is an ILLUSTRATION, so where the two frames draw
the same fact differently the shape they AGREE on is the specification and both
sets of figures are ignored. Every place they disagree is marked `⚖` below and
carried into `CR-085-lane8-conformance.md` as a divergence rather than a defect.

Quoted verbatim, in order. Nothing is paraphrased and nothing is re-sorted.

---

## Section 08 — "What you used"

> **08 · What you used**
> Three screens. The evidence behind the bill, and the only place several
> services must share one page without confusing each other.

### Screen 50 · Usage — `/{tenant}/portal/usage` — `NEW BUILD`

Commitments named on the screen: `CPB-06` · `CPB-07` · `CPB-08` · `CPB-23`.
Marked **"No door named."** — one of the 37 screens carrying no
*How you get here* row (`CPB-23`).

> The question: am I using more than I used to, and is that why the bill went
> up? One service at a time — a customer cannot read four units on one axis.

**PHONE · 390, in order**

```
Home   Bills   Usage   Help
What you used
⚡ Electric ▾
LAST MONTH
800 kWh
5% less than July · 12% more than August last year
Lowest    412 kWh
Average   664 kWh
Highest   948 kWh
AGAINST LAST YEAR
Aug 2026     800 kWh
Aug 2025     714 kWh
Difference   +86 kWh
Summer is your heaviest season — it has been in each of the last two years.
```

**DESKTOP · 1280, in order**

```
Silver Creek Water | Home Bills Usage Payments Requests Help My details
🌐 English  ·  Sign out
Marcus Bell · 1841 Quarry Hill Ct, Silver Creek, TX 78611 · Account 4417-0092
$191.00 due Aug 22

What you used
⚡ Electric    💧 Water    🚿 Sewer
ELECTRIC · THE LAST 12 MONTHS
This month        800 kWh
Lowest · Feb      412 kWh
Average           664 kWh
Highest · Jul 2025  948 kWh
LAST MONTH
800 kWh
Against July 2026     −42 kWh
Against August 2025   +86 kWh
WHAT THIS COST YOU
800 kWh at $0.1150
$92.00
→ See the whole bill →
```

**The notes under the drawing, verbatim**

* **FOR** — "Letting a customer see their own consumption pattern and connect it
  to the bill."
* **ONE SERVICE AT A TIME** — "A picker on phone, tabs on desktop. kWh, thousand
  gallons and therms cannot share an axis, and a chart that mixes them is
  unreadable. The picker is built from the services this customer actually has —
  never a fixed list."
* **THE FAILURE TO AVOID** — "Every figure on this screen must belong to the
  selected service. Showing \"Average water month 15 kgal\" while Electric is
  selected is the defect that reached a live screen this week; the fix is that no
  summary is rendered outside the block that owns its data."
* **COGNITIVE LOAD** — "Comparisons are computed: \"5% less than July\", \"+86 kWh
  against last August\". The customer never subtracts two figures the screen has
  already shown them."
* **UNITS** — "Every number carries its unit, at the number, in the customer's
  own unit. Never converted, never assumed."
* **STATES** — `NO HISTORY` "We need two reads before we can show a trend." Says
  when that will be. · `NO PRIOR YEAR` "The comparison block says so in a
  sentence — never a raw key, never a blank row." · `ESTIMATED MONTHS` "Marked on
  the chart with a legend, so the customer knows which bars are measured." ·
  `ONE SERVICE ONLY` "No picker at all — a chooser with one option is furniture."
* **COMPONENTS** — `PortalFrame` · `ServicePicker` · `UsageChart` ·
  `ComparisonRows`
* **RULES** — "Weight follows importance — the chart outranks the summary tiles
  above it, not the other way round."

⚖ **The captured pack draws this screen differently** (`wireframes/CWP-033.png`,
`P19`): kicker `USAGE`, title **"What you have used"**, a `12 months / 24 months`
segmented control and a **`↓ CSV`** button, **three** tiles
(`WATER · THIS PERIOD` / **`DAILY AVERAGE`** / `NEXT READING DUE`), a chart panel
headed `WATER · GALLONS PER MONTH` with `Sewer is billed on this figure` at its
right, and **three service cards below the chart** (`WATER` this-year/last-year,
`SEWER` billed-on, `TRASH` billed-on).

### Screen 51 · Readings — `/{tenant}/portal/readings` — `NEW BUILD`

Commitments: `CPB-04` · `CPB-09` · `CPB-23`. **"No door named."**

> The question: was my meter actually read, or was this bill a guess? A customer
> disputing a bill comes here first.

**PHONE · 390**

```
← Usage
Meter readings
⚡ Electric · meter 8841-C ▾
Jul 31, 2026   Read by us   41,208   800 kWh used
Jun 30, 2026   Read by us   40,408   842 kWh used
May 31, 2026   39,566
⚠ Estimated — meter not reachable   790 kWh est.
NEXT READ   Around Sep 30, 2026   in 22 days
Send us your own reading
READ IT YOURSELF
If a read was estimated, sending us your own corrects it on the next bill.
Send us a reading
ABOUT ESTIMATES
When we cannot reach a meter we estimate from your own history. The next real
read corrects the difference automatically — you are never charged twice.
```

**DESKTOP · 1280**

```
← Usage
Meter readings
⚡ Electric · 8841-C     💧 Water · W-2209
DATE            READING   USED      HOW
Jul 31, 2026    41,208    800 kWh   READ BY US
NEXT READ   Sep 30   in 22 days · you do not need to be home
Jun 30, 2026    40,408    842 kWh   READ BY US
May 31, 2026    39,566    790 kWh   ⚠ ESTIMATED
Apr 30, 2026    38,776    655 kWh   READ BY US
```

**Notes, verbatim**

* **FOR** — "Showing the evidence behind every bill, and distinguishing a
  measured read from an estimated one at a glance."
* **COGNITIVE LOAD** — "Both the dial reading and the amount used are shown,
  because customers check the dial against their own meter. The difference is
  computed for them."
* **ESTIMATES** — "Flagged with colour **and** the word \"Estimated\" **and** a
  row tint — three signals, because this is the fact most likely to be disputed.
  The self-correction is explained, since \"am I paying twice\" is the follow-up
  question."
* **STATES** — `NO READS YET` "Your first read is due around Sep 30." Not an
  empty table. · `CUSTOMER READ` A third kind of chip: "You sent this", with the
  date received. · `METER CHANGED` An explicit row: old meter final read, new
  meter start, so a reset number is never alarming. · `LONG RUN OF ESTIMATES` A
  banner offering a read appointment — three estimates in a row is a service
  failure.
* **WORDS** — "\"Read by us\", not \"Actual\". \"Estimated — meter not
  reachable\", not \"Estimated read, no access\"."
* **COMPONENTS** — `PortalFrame` · `ServicePicker` · `ReadingRow` · `StatusChip`
* **RULES** — "The meter's own serial is the customer's reference and is shown;
  the database id is not."

⚖ The captured pack (`CWP-034.png`, `P20`) titles it **"Readings on your water
meter"**, columns `TAKEN ⇅ · READING · USED SINCE · HOW IT WAS TAKEN · ON WHICH
BILL`, a `Send a reading` OUTLINE button top right, `Showing 1–4 of 26` with page
arrows, and the estimates note as an `i` callout at the foot.

### Screen 52 · Equipment — `/{tenant}/portal/equipment` — `NEW BUILD`

Commitment: `CPB-10`. This screen **does** name a door.

> The question: what is installed at my address, whose is it, and what am I
> paying for it?

**PHONE · 390**

```
← Usage
What is at your address
1841 Quarry Hill Ct, Silver Creek, TX 78611
⚡ Electric meter          8841-C · installed Jun 2, 2026   Ours   No charge
💧 Water meter · 5/8"     W-2209 · installed Jun 2, 2026   Ours   No charge
🔥 Fire line · 2"  Sprinkler supply                        Ours   $12.00 a month
If something looks damaged or is leaking, tell us — do not touch it yourself.
Report a problem
```

**DESKTOP · 1280**

```
← Usage
What is at your address
1841 Quarry Hill Ct, Silver Creek, TX 78611
EQUIPMENT                  REFERENCE  INSTALLED     WHOSE  MONTHLY
⚡ Electric meter           8841-C     Jun 2, 2026   Ours   No charge
💧 Water meter · 5/8 inch   W-2209     Jun 2, 2026   Ours   No charge
🔥 Fire line · 2 inch sprinkler supply  F-0118  Jun 2, 2026  Ours  $12.00
WHOSE IS WHAT
Equipment marked Ours is maintained by us at no cost to you. Anything marked
Yours is your responsibility to repair.
NEVER TOUCH A METER YOURSELF
If something is damaged, leaking or making a noise, tell us and we will come
out. There is no charge for a safety visit.
Report a problem
```

**Notes, verbatim**

* **FOR** — "Answering what is installed, who maintains it, and which items carry
  a monthly charge — the three facts behind most equipment questions."
* **HOW YOU GET HERE** — "Usage. *Not My details.*"
* **COGNITIVE LOAD** — "\"Ours\" and \"Yours\" in one column settles the
  repair-bill question without reading a policy. **Size is stated in inches, as
  the customer's plumber would.**"
* **SAFETY** — "The instruction not to touch a meter is on the screen that lists
  meters, not in a leaflet, and the visit is stated as free so nobody delays
  reporting a leak over cost."
* **STATES** — `NOTHING RECORDED` "We have not recorded your equipment yet." With
  a way to ask. · `BEING REPLACED` A row showing the swap in progress and the
  date. · `CHARGED ITEM` The monthly charge links to the bill line it produces. ·
  `MULTIPLE ADDRESSES` An address picker above the list, one property at a time.
* **COMPONENTS** — `PortalFrame` · `EquipmentRow` · `Callout warn`
* **RULES** — "The address is derived from the property record, never stored on
  the equipment — a map and an envelope cannot disagree."

⚖ The captured pack (`CWP-037.png`, `P23`) titles it **"What is installed at your
property"** and its columns are `EQUIPMENT · SERIAL · WHERE · FITTED · LAST READ ·
STATUS` — no `WHOSE`, no `MONTHLY`, and no size on the equipment name.

---

## Section 09 — "Asking us something"

> **09 · Asking us something**
> Four screens. A question, and then the thread it becomes. Silence after a
> request is the fastest route to a second phone call.

### Screen 53 · Ask a question — `/{tenant}/portal/ask` AND `/{tenant}/portal/ask-a-question` — `NEW BUILD`

Commitments: `CPB-16` · `CPB-17`.

> The question: I have something to ask that no page here answers, and I do not
> want to sit on hold.

**PHONE · 390**

```
← Prices and fees
Ask us a question
We reply within 1 working day
What is it about?   [ Choose one ▾ ]
Your question       [ I am moving my elderly mother in and wondered whether… ]
You may already have an answer: Help paying your bill covers assistance for
older customers.
Attach something, if it helps   📎 Add a file
Send my question
You will get a reference, and the reply appears in Your requests.
```

**DESKTOP · 1280**

```
← Prices and fees
Ask us a question
About account 4417-0092 · 1841 Quarry Hill Ct
What is it about?   [ My bill ▾ ]
Your question       [ I am moving my elderly mother in and wondered whether her
                      age would qualify us for anything. ]
Attach something, if it helps   📎 Add a file — a photo, a letter, a document
Send my question
THIS MAY ALREADY BE ANSWERED
→ Help paying your bill — senior discount, 15% off every bill
→ What if I cannot pay my bill?
Reading one of these is faster than waiting for a reply.
IF IT IS URGENT
Call (281) 555-0164, Mon–Fri 8 AM – 5 PM.
A question sent here is answered within one working day.
```

**Notes, verbatim**

* **FOR** — "The catch-all. Everything the other twenty-nine screens do not cover
  ends up here rather than on the phone."
* **HOW YOU GET HERE** — "Prices and fees — the only door, which is a strange
  place for it and is worth a second one from Help."
* **COGNITIVE LOAD** — "The suggestions appear as they type, from what they have
  written — not a static list. A person who gets their answer in five seconds and
  closes the form is a success, not a lost submission."
* **CONTEXT** — "The account is attached automatically, so nobody has to state
  who they are. A signed-out visitor is asked for an email instead, and the
  screen says why."
* **STATES** — `SENT` "Becomes a tracked request with a reference, and the thread
  is where the reply appears." · `URGENT CHOSEN` "Shows the phone number
  prominently — some things should not wait a day." · `ATTACHMENT TOO LARGE`
  "Says the limit plainly and keeps everything typed." · `OUTSIDE HOURS` "Says
  when the office opens, and that the question is queued either way."
* **COMPONENTS** — `PortalFrame` · `Select` · `Field` · `FileDrop` ·
  `SuggestionCard`

⚖ The captured pack (`CWP-054.png`, `P40`) draws the same form at
`/pine-hill/portal/help/ask` with kicker **HELP**, title **"Ask us something"**,
fields **"What is it about? *"**, **"Which bill"** (`BL-2608-0141 · August ·
$142.18`), **"Tell us *"**, **"Attach a photo"** (`📷 Optional`), **`Send ✓`**,
and a rail of **MIGHT ANSWER IT NOW** (three links) + **OR RING** (two numbers).
**The blueprint has NO bill field and the captured pack does.**

### Screen 54 · Ask a question, at its second address — `/{tenant}/portal/ask` — `NEW BUILD`

Commitments: `CPB-17` · `CPB-23`. **"No door named."**

> **Not a separate screen.** The portal serves the question form at both
> `/{tenant}/portal/ask` and `/{tenant}/portal/ask-a-question`. **Both render
> screen 40.**
> **WHY BOTH EXIST** — "`/{tenant}/portal/ask` is the short form used inside the
> product; `/{tenant}/portal/ask-a-question` is the readable one that goes into
> help articles and emails."
> **WHAT MUST BE TRUE** — "One component behind both. A second copy is how one of
> them quietly stops carrying the account context while the other keeps it."

### Screen 55 · Your requests — `/{tenant}/portal/requests` — `NEW BUILD`

Commitments: `CPB-05` · `CPB-11` · `CPB-12` · `CPB-23`. **"No door named."**

> The question: I asked for something — is anyone doing it? Silence after a
> request is the fastest way to a second phone call.

**PHONE · 390**

```
Home  Bills  Requests  Help
Your requests
Bill looks wrong          REQ-4471 · raised Aug 13   BEING LOOKED AT  Reply by Aug 15
Meter re-read             REQ-4390 · raised Jul 28   DONE AUG 2
Paperless billing         REQ-4288 · raised Jun 15   DONE JUN 15
Ask for something else
```

**DESKTOP · 1280**

```
Your requests
1 open · 2 finished
WHAT YOU ASKED                 REFERENCE   RAISED         WHERE IT IS       NEXT
Bill looks wrong — water reading  REQ-4471  Aug 13, 2026  BEING LOOKED AT   We reply by Aug 15
Meter re-read                     REQ-4390  Jul 28, 2026  DONE              Finished Aug 2
Switch to paperless billing       REQ-4288  Jun 15, 2026  DONE              Finished Jun 15
Ask for something else
```

**Notes, verbatim**

* **FOR** — "Showing every open request in one place, with what happens next and
  when."
* **COGNITIVE LOAD** — "\"Next\" is a column. A status without a date is what
  makes people phone; \"We reply by Aug 15\" is what stops them."
* **NAMING** — "Requests are titled by what the customer asked for in their own
  words, not by an internal category."
* **STATES** — `NONE` "You have not asked us for anything yet." With the ways
  to. · `OVERDUE` Amber, and says so: "We said Aug 15 and have not replied."
  Owning it beats hiding it. · `NEEDS YOU` Top of the list, saying exactly what
  is needed from them. · `CLOSED WITH NO ACTION` Says why, never simply
  disappears.
* **COMPONENTS** — `PortalFrame` · `RequestRow` · `StatusChip` · `Pagination`
* **RULES** — "The reference is the customer's, shown so they can quote it on the
  phone. Server-side paging, no cap."

⚖ The captured pack (`CWP-046.png`, `P32`) draws this address as **"What do you
need?"** — a hub of six errand cards above an `OPEN REQUESTS` panel — not as a
list of everything asked for. **The product is built to the captured pack.**

### Screen 56 · One request — `/{tenant}/portal/requests/{reference}` — `BLOCKED`

Commitments: `CPB-11` · `CPB-13`.

> The question: what has actually happened on this, and is anything waiting on
> me?

**PHONE · 390**

```
← Your requests
Bill looks wrong
REQ-4471 · about your August bill
Being looked at   OPEN
We will reply by Aug 15.
WHAT HAS HAPPENED
Aug 14 · Us    We have asked for a re-read of your water meter.
Aug 13 · Us    Received. We will come back to you within 2 working days.
Aug 13 · You   The water reading looks about double what we normally use…
The disputed $47.50 is not due while this is open.
Add something   [ Type here… ]   Send
```

**DESKTOP · 1280**

```
← Your requests
Bill looks wrong — water reading
REQ-4471 · raised Aug 13, 2026 · about bill BL-2608-000042
WHAT HAS HAPPENED
Aug 14, 11:20 AM · Silver Creek Water   We have asked for a re-read of your water
  meter. A technician will visit within 3 working days; nobody needs to be home.
Aug 13, 3:02 PM · Silver Creek Water    Received. We will come back to you within
  2 working days.
Aug 13, 2:58 PM · You   The water reading looks about double what we normally
  use, and nobody was home for two weeks. 📷 meter.jpg
Add something   [ Type here… ]   Send
BEING LOOKED AT
We will reply by Aug 15, 2026.
WHILE THIS IS OPEN
The disputed $47.50 is not due and carries no late fee. The remaining $143.50 is
still due on Aug 22.
NOTHING IS WAITING ON YOU
If we need anything, it will say so here and we will email you.
```

**Notes, verbatim**

* **FOR** — "One thread showing everything said and done, in order, with what is
  owed in the meantime."
* **HOW YOU GET HERE** — "Something looks wrong and Ask a question — both go
  straight to the thread they just created, by reference."
* **COGNITIVE LOAD** — "Newest first. Each entry says who and when. \"Nothing is
  waiting on you\" is stated explicitly, because uncertainty about whose turn it
  is drives the follow-up call."
* **MONEY** — "The disputed and undisputed amounts are split with real figures.
  \"Part of your bill is on hold\" is not enough to act on."
* **STATES** — `WAITING ON YOU` Amber banner naming exactly what is needed, at
  the top. · `RESOLVED` Green, with the outcome and any credit — and the thread
  stays readable. · `OVERDUE REPLY` Says the promised date passed. Owning it
  beats a silent thread. · `CLOSED` No reply box; offers to raise a new one
  referencing this.
* **COMPONENTS** — `PortalFrame` · `Thread` · `Callout warn` · `Callout ok` ·
  `Field`

⚖ The captured pack (`CWP-051.png`, `P37`) draws a **six-step PROGRESS ladder**
(`You sent it · We picked it up · We need something from you · We decide · Final
reading and bill · Account closes`) beside a **DETAILS** rail (`Reference · Last
day of service · Waiting on · Open for`) and `Add a note` / `Withdraw` buttons —
**no thread at all.** The blueprint draws a thread and **no ladder**. The product
draws **both**.

---

## What the blueprint says about `/ask` that the router does not

The blueprint's screen 54 states, as fact, that **"the portal serves the question
form at both `/{tenant}/portal/ask` and `/{tenant}/portal/ask-a-question`. Both
render screen 40."** It does not. `07-frontend/src/portal/routing/portalRoutes.tsx`
mounts `/ask` on `QuickServicePage` (`CWP-010`, *Ask us for something* — the six
errand cards) and only `/ask-a-question` on `AskAQuestionPage` (`CWP-054`).
Recorded here because it is the drawing that is wrong about the product, and
because the blueprint's own `WHAT MUST BE TRUE` — *"One component behind both"* —
is a requirement nobody can satisfy while the two addresses are two screens.
