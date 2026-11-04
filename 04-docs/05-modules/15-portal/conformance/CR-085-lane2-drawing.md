# CR-085 · lane 2 · the drawing, quoted

**What this file is.** The Customer Portal Blueprint's own words for the eleven
drawings that cover lane 2's ten routes — every label, in the order the drawing
puts it, **quoted and not linked** (react-tailwind-css-ui-generator §1: *"A link
gets skimmed; a quote gets built."*). Nothing here is a judgment; the judgments
are in `CR-085-lane2-findings.md` beside it.

**Source.** `05-prototype/SMARTBillHub Customer Portal Blueprint.pdf`, 129 pages,
read with `10-scripts/pdf/pdf_text.py`. The masthead dates itself: *"Every
as-built statement here was true at version 2.232.0, commit d940f460, on 8
September 2026, and must be re-verified before it is trusted."* Section **02
Before you sign in** is pages 6–24; the route index that names each screen's
address is pages 121–123.

⚠ **THE TEXT LAYER JOINS WORDS WITH `￾`** (`How￾you-get-here`). Every quote below
is taken after stripping `￾` and `­`. A grep for a phrase WITHOUT stripping them
returns a false absence.

⚠ **TWO DRAWING SETS EXIST AND THEY ARE NOT THE SAME DRAWING.** This blueprint
(8 September) and `04-docs/05-modules/15-portal/wireframes/CWP-###.png` (*"rendered
from the blueprint 2026-09-03"*, per `08-screen-layouts.md`'s own first line) draw
the same routes differently. **The product is built to the September 3 pack**, and
`14-layout-audit.md` grades nine of my screens *"Matches"* against that pack. So
almost every difference in the findings file is *the product matching the older
drawing*, not the product being careless. Which of the two is the design is a
question for the PO; this lane records the delta.

---

## The ten routes, and the eleven drawings that cover them

| Route (as the router mounts it) | Blueprint screen | Title as drawn |
|---|---|---|
| `/:tenant/portal` | **01** | The landing page · signed out |
| `/:tenant/portal` (top-bar menu) | **02** | Choose your language · signed out |
| `/:tenant/portal/sign-in` | **03** | Sign in |
| `/:tenant/portal/enrol` | **04** | Create your sign-in |
| `/:tenant/portal/forgot-password` | **05** | Forgotten password |
| `/:tenant/portal/report` | **09** | Report a problem |
| `/:tenant/portal/track` | **10** | Track a report |
| `/:tenant/portal/help` | **11** | Help |
| `/:tenant/portal/help/:slug` | **12** | One help article |
| `/:tenant/portal/visit` | **13** | Where to find us |
| `/:tenant/portal/visit/:slug` | **14** | One service centre |

---

## 01 · The landing page · signed out — `/:tenant/portal`

State chip: **NEW BUILD** · **COMMITMENT CPB-24**

> **The question:** a stranger has typed the utility's address into their phone.
> Most of them want to pay a bill, one is standing next to a burst main, and a
> few want to sign in. The page has to serve all three without asking anyone to
> choose a category first.

### PHONE · 390 — in order

```
Silver Creek Water                       🌐 English ⌄
Emergency?  Burst main, no water, or a gas smell — call (281) 555-0164, 24 hours.
PAY YOUR BILL
  With the bill number from your bill. No sign-up needed.
  [ Pay a bill → ]
ALREADY HAVE A SIGN-IN?
  [ Sign in ]
  Create one · Forgot your password?
OR DO THIS WITHOUT SIGNING IN
  ⚠ Report a problem                ›
  ⌛ Track something you reported    ›
  🏠 Start service at a new address  ›
  💲 Prices and fees                 ›
  📍 Where to find us                ›
  ❓ Help                            ›
Silver Creek Water · Mon–Fri 8 AM – 5 PM · (281) 555-0164
```

### DESKTOP · 1280 — in order

```
Silver Creek Water · Pay a bill · Report a problem · Prices · Help · Visit us
                       🌐 English ⌄ · ☎ (281) 555-0164 · Sign in
Emergency?  A burst main, no water, or a gas smell — call us. Do not use a form.
            (281) 555-0164     24 hours, every day
Pay your bill
  The bill number from the bill in front of you, and your ZIP code. No sign-up.
  Bill number · BL-2608-000042
  ZIP code
  [ Find this bill ]
OR DO THIS WITHOUT SIGNING IN
  ⚠ Report a problem        A leak, no water, a manhole
  ⌛ Track a report          With your reference
  🏠 Start service           Moving in
  💲 Prices and fees         What we charge
  📍 Where to find us        Offices and hours
  ❓ Help                    Common questions
SIGN IN                                  (right rail)
  To see your bills, your usage, and set up autopay.
  Email
  Password
  [ Sign in ]
  Create a sign-in · Forgot your password?
LOW PRESSURE · QUARRY HILL AREA
  Crews on site since 9:40 AM. Expected back to normal by 4 PM today.
  → All current problems
STRUGGLING TO PAY?
  Grants and discounts exist and most people who qualify never claim them.
  → See help paying
```

### The notes the drawing attaches

* **FOR** — *"Everyone who arrives without being signed in. It is the busiest page
  in the portal and the only one a stranger, a customer and somebody in an
  emergency all land on together."*
* **HOW YOU GET HERE** — *"It **is** the door. Everything a signed-out visitor
  reaches starts here or from the guest bar."*
* **PRIMARY ACTION** — *"**Pay a bill.** One filled button, and it is not "Sign
  in" — most visits are a payment, and most of those people have no account and
  do not want one. Sign-in is the outlined second path."*
* **THE EMERGENCY BAND** — *"Above everything, on every width, in the danger tier,
  with a phone number and not a form. Somebody standing in water must not have to
  read a page."*
* **COGNITIVE LOAD** — *"Three routes, visually distinct, no menu to open first:
  pay · sign in · everything else. The "everything else" list is written as the
  things people do, not as site sections."*
* **LIVE OUTAGES** — *"Shown unprompted. It answers "is it just me?" and prevents
  a duplicate report, which is the commonest call during an incident."*
* **ASSISTANCE** — *"Reachable from the front page, not buried behind a sign-in.
  Somebody who cannot pay is often somebody who never enrolled."*

### STATES, verbatim

| State | The drawing's words |
|---|---|
| NOTHING WRONG | *"The outage panel is absent, not shown saying "no outages" — that trains people to ignore it."* |
| PORTAL OFF | *"The utility has not switched sign-in on: the pay and contact routes stay, sign-in says so."* |
| ALREADY SIGNED IN | *"Never rendered — the frame sends them to Home."* |
| BRANDING UNSET | *"Falls back to the utility's name in plain type. A missing logo must not take the page with it."* |

**COMPONENTS** `PublicFrame` · `Callout danger` · `QuickPayCard` · `SignInCard` ·
`TaskGrid` · `OutageBanner` · `PortalLanguage`

**RULES** *"Colour is never the only signal. Every icon carries its word. All copy
and branding are the utility's own, configured in settings."*

---

## 02 · Choose your language · signed out — `/:tenant/portal` (and `/sign-in`, `/pay-now`)

State chip: **EXISTS BEHIND** · **COMMITMENT CPB-23** · *"No door named."*

> **The question:** this page is not in a language I read. A picker that is itself
> only in English has already failed the person who needs it.

### PHONE · 390 · OPEN FROM THE TOP BAR

```
Silver Creek Water        🌐 English ▾
LANGUAGE · IDIOMA · NGÔN NGỮ
  English            ✓
  Español    Spanish      ›
  Tiếng Việt Vietnamese   ›
  中文        Chinese      ›
  Français   French       ›
Your choice is remembered on this device. Bills and letters keep the language
on your account until you change it there.
```

### DESKTOP · 1280 · THE MENU OPEN

```
LANGUAGE · IDIOMA · NGÔN NGỮ · 中文 · LANGUE
  English            CURRENT
  Español · Spanish        [ Choose ]
  Tiếng Việt · Vietnamese  [ Choose ]
  中文 · Chinese            [ Choose ]
  Français · French        [ Choose ]
Each language is written in that language, first. The English name is
underneath, for anyone helping somebody else set it.

WHAT IT CHANGES
  This site, on this device        NOW
  Your bills and letters           Set on your account
  A guest has no account, so the choice lives in this browser until they sign in.

IF WE HAVE NOT TRANSLATED SOMETHING
  A page we have not translated stays in English rather than showing a machine
  translation. It says so, in your language, at the top.
```

* **THE RULE THAT MAKES IT WORK** — *"**Every language is written in its own
  language, first.** "Español", not "Spanish". Somebody who reads no English
  cannot find "Spanish" in a list; they can find "Español" instantly."*
* **COGNITIVE LOAD** — *"No flags — a flag is a country, not a language… No
  auto-detection that cannot be overridden. The current choice is marked, so
  nobody wonders whether the tap worked."*

| State | The drawing's words |
|---|---|
| ONE LANGUAGE | *"No picker at all — a chooser with one option is furniture."* |
| PARTLY TRANSLATED | *"The language is offered, with a line saying which parts are English."* |
| CHOSEN | *"The page redraws immediately in that language, including this picker."* |
| STORAGE BLOCKED | *"The choice holds for the visit and says it will not be remembered."* |

**COMPONENTS** `PublicFrame` · `PortalLanguage` · `LanguageRow`

---

## 03 · Sign in — `/:tenant/portal/sign-in`

State chip: **NEW BUILD** · **COMMITMENT CPB-24**

> **The question:** how do I get to my bill? — and, for the third of visitors who
> are not signed up, **how do I pay without an account?**

### PHONE · 390 and DESKTOP · 1280 — the same list, in order

```
Sign in
to see your bills and pay online
Email        you@example.com
Password     ••••••••
[ Sign in ]
Forgot your password?
NO ACCOUNT?
  Pay a bill with its bill number — no sign-up needed.
  [ Pay a bill → ]
Emergency? Call (281) 555-0164 — 24 hours      (390)
Emergency? (281) 555-0164 · 24 hours           (1280)
```

* **HOW YOU GET HERE** — *"The landing page (its own sign-in form is embedded
  there) and the **Sign in** word in the guest top bar."*
* **PRIMARY ACTION** — *"One filled button: **Sign in**. Quick-pay is the outlined
  second path, never a third equal button."*
* **COGNITIVE LOAD** — *"Two fields. No "username or email" ambiguity — it is the
  email the bill was sent to, and the label says so on error."*
* **WORDS** — *""Sign in", not "Log on". "Forgot your password?" as a question, not
  "Password recovery"."*
* **LANGUAGE** — *"A guest picks from the top bar. A signed-in customer gets their
  own account's language without asking."*

| State | The drawing's words |
|---|---|
| LOADING | *"Button reads "Signing in…" and is disabled. The form stays visible."* |
| WRONG DETAILS | *"One message under the pair, never per field: "That email and password do not match.""* |
| LOCKED OUT | *"Says how long, and offers the reset — never a bare refusal."* |
| PORTAL OFF | *"The utility has not switched it on: says so, with the phone number."* |

**COMPONENTS** `PortalFrame` · `Field` · `Button` · `Button ghost` · `PortalLanguage`

**RULES** *"Emergency number on every unauthenticated screen. Colour never the only
signal. Icon never alone."*

⚠ The blueprint's standards block **E** names this screen as one of its nine
audited door findings: *"**No way to sign up, from the sign-in screen** — enrol is
reached from the landing page and from the guest payment receipt — not from
sign-in, which offers **Forgot your password?** and nothing else… It is the most
obvious place to look for it."*

---

## 04 · Create your sign-in — `/:tenant/portal/enrol`

State chip: **EXISTS BEHIND** · **NO COMMITMENT**

> **The question:** I get a paper bill — how do I get online? The one thing that
> stops people is being asked for a number they cannot find.

### PHONE · 390 — in order

```
← The landing page
Create your sign-in
You need your account number and last bill
Account number                          4417-0092
  🔍 Where to find it on your bill
ZIP code of the service address         78611
Your email                              you@example.com
Choose a password                       ••••••••
  At least 10 characters
[ Create my sign-in ]
```

### DESKTOP · 1280 — in order

```
← The landing page
Create your sign-in
Two things off your bill, and an email address.
Account number                          4417-0092
ZIP code of the service address         78611
Your email                              you@example.com
Choose a password                       ••••••••
  At least 10 characters. We will email you to confirm it is you.
[ Create my sign-in ]

WHERE THE ACCOUNT NUMBER IS                 (right rail)
  SILVER CREEK WATER
  Account       4417-0092
  Amount due    $191.00
  Top right of your paper bill, above the amount due.
NOT READY TO SIGN UP?
  You can pay a bill with just your account number.
  [ Pay without signing in → ]

Cannot find your account number? Call (281) 555-0164.
```

* **FOR** — *"Turning a paper-bill customer into an online one, in four fields."*
* **HOW YOU GET HERE** — *"The landing page — one of the three doors it carries
  beneath the sign-in form — and the guest payment receipt, offered after somebody
  has paid without an account. ⚠ **Not the sign-in screen.**"*
* **COGNITIVE LOAD** — *"The account number is the barrier, so the screen shows a
  picture of a bill with the number circled rather than describing where to look.
  The ZIP code is the second factor because it is the one thing everybody knows
  without hunting."*
* **THE ESCAPE HATCH** — *"Quick-pay is offered on the same screen. Someone who
  cannot complete this must not leave without having paid."*

| State | The drawing's words |
|---|---|
| NO MATCH | *"One message for the pair — never "that account exists but the ZIP is wrong", which confirms an account to a stranger."* |
| ALREADY ENROLLED | *""This account already has a sign-in." Offers the password reset, not a second account."* |
| EMAIL IN USE | *"Says so and offers to add this account to the existing sign-in."* |
| CONFIRM PENDING | *""Check your email" — and says the link lasts an hour, before they go looking."* |

**COMPONENTS** `PortalFrame` · `Field` · `BillLocator` · `Button`

---

## 05 · Forgotten password — `/:tenant/portal/forgot-password`

State chip: **EXISTS BEHIND** · **COMMITMENT CPB-23** · *"No door named."*

> **The question:** I cannot get in — what now? The screen must not tell an
> attacker whether an email is registered.

```
← Sign in
Reset your password
We will email you a link. It works once and lasts an hour.
Email                                   you@example.com
[ Send the link ]
Check your email. If that address is on an account, a link is on its way.
It may take a minute.                                            (390, after send)
No email? Call (281) 555-0164 and we will verify you another way.        (390)
No email on the account? Call (281) 555-0164 and we will verify you
another way.                                                            (1280)
```

* **COGNITIVE LOAD** — *"The link's lifetime is stated **before** they submit, so a
  link that has expired is not a surprise."*
* **WORDS** — *""Send the link", not "Submit". The confirmation says what to do
  next, not that a request was received."*

| State | The drawing's words |
|---|---|
| SENT | *"The same confirmation whether or not the email exists. Never "no such account"."* |
| LINK EXPIRED | *"Says it expired and offers a new one in one tap — a dead end here is a phone call."* |
| NO EMAIL ON FILE | *"Falls back to the phone number rather than stranding them."* |
| FAILED TO SEND | *"Says so plainly and keeps the typed address."* |

**COMPONENTS** `PortalFrame` · `Field` · `Button` · `Callout ok`

---

## 09 · Report a problem — `/:tenant/portal/report`

State chip: **EXISTS BEHIND** · **COMMITMENT CPB-23** · *"No door named."*

> **The question:** there is water coming out of the road — who do I tell, right
> now? This is the one screen a stranger may reach in an emergency.

### PHONE · 390 — in order

```
GAS SMELL, OR WATER FLOODING A ROAD?
(281) 555-0164
Call now — 24 hours. Do not use this form.
Report a problem
What is happening?        Choose one ⌄
   · Water leaking in the street
   · No water
   · Water looks or smells wrong
   · Low pressure
   · A manhole or cover
   · Streetlight out
   · Something else
Where                     📍 Use my location, or type an address
A photo helps             📷 Add a photo
Your phone, if we need to call     Optional
[ Report it ]
You do not need an account to report a problem.
```

### DESKTOP · 1280 — in order

```
Emergency?  Gas smell, water flooding a road, or a downed line — call us, do not
use this form.          (281) 555-0164      24 hours, every day
Report a problem
You do not need an account.
What is happening?   Water leaking in the street ⌄
How bad?             A steady trickle ⌄
Where                📍 Corner of Quarry Hill Ct and Lakeview Dr
Anything else        Been running since yesterday morning.
A photo helps        📷 Add a photo
Your phone, if we need to call     Optional
[ Report it ]

ALREADY KNOWN ABOUT                                   (right rail)
  ⚠ Low pressure · Quarry Hill area        Since 9:40 AM
  Crews are on site. Expected back to normal by 4 PM today.
  → See all current problems
WHAT HAPPENS AFTER YOU REPORT
  1 · You get a reference straight away
  2 · We assess it, usually within the hour
  3 · If you left a phone number we call before visiting
```

* **THE EMERGENCY BAND** — *"Above everything, on every width, in the danger tier.
  A form that quietly accepts a gas-smell report is the most dangerous screen in
  the product."*
* **COGNITIVE LOAD** — *"No sign-in. Location by one tap. A photo instead of a
  description. Someone reporting a burst main is standing in the street on a
  phone."*
* **KNOWN PROBLEMS** — *"Showing what is already reported nearby prevents
  duplicates and answers "have you been told?" without anyone having to ask."*

| State | The drawing's words |
|---|---|
| SENT | *"A reference on screen immediately, and by text if a number was given."* |
| ALREADY KNOWN | *"Offers to attach to the existing report rather than creating a duplicate."* |
| OUTSIDE OUR AREA | *"Says so and names who to call — never accepts a report it will not act on."* |
| PHOTO FAILED | *"The report still sends; the photo can be added afterwards."* |

**COMPONENTS** `PortalFrame` · `Callout danger` · `Select` · `LocationField` · `FileDrop`

**RULES** *"What a stranger typed is recorded as a report, not as a change to any
property record."*

---

## 10 · Track a report — `/:tenant/portal/track`

State chip: **EXISTS BEHIND** · **COMMITMENT CPB-23** · *"No door named."*

> **The question:** I reported a leak on Tuesday and I do not have an account —
> has anybody been?

### PHONE · 390 — in order

```
Track a report
No sign-in needed
Reference                      REP-8842
Or a phone number you gave us
[ Look it up ]
Lost it? A phone number finds everything reported from it in the last 90 days.
Water leaking in the street        CREW ON THE WAY
Corner of Quarry Hill Ct and Lakeview Dr
Reported          Sep 2, 9:14 AM
Expected fixed    Today, by 4 PM
WHAT HAS HAPPENED
  Sep 8, 8:02 AM   A crew is on the way.
  Sep 2, 10:30 AM  We inspected it and scheduled a repair.
  Sep 2, 9:14 AM   You reported it.
```

### DESKTOP · 1280 — in order

```
Track a report
No sign-in needed — the reference we gave you when you reported it.
Reference                      REP-8842
Or a phone number you gave us  (512) 555-0148
[ Look it up ]
Lost the reference? A phone number finds everything reported from it in the last
90 days. ☎ Or call (281) 555-0164.
Showing 1 report for REP-8842  ·  ↻ Look up another
Water leaking in the street
REP-8842 · corner of Quarry Hill Ct and Lakeview Dr · reported Sep 2, 2026
WHAT HAS HAPPENED
  Sep 8, 8:02 AM · Silver Creek Water   A crew is on the way. We expect the road
                                        to be back to normal by 4 PM today.
  Sep 2, 10:30 AM · Silver Creek Water  We inspected it. It is a service line,
                                        not a main, and a repair is scheduled.
  Sep 2, 9:20 AM · Silver Creek Water   Received. We will inspect within one
                                        working day.
  Sep 2, 9:14 AM · You                  Been running since yesterday morning.
                                        📷 leak.jpg
WHERE IT IS UP TO                                    (right rail)
  Crew on the way
  Expected fixed today, by 4 PM.
OTHERS REPORTED THIS TOO
  4 people have reported the same problem.
  You will all be told when it is fixed.
Anything to add? You can reply here without signing in.
  [ Type here… ]  [ Send ]
```

* **COGNITIVE LOAD** — *"The status has a time attached — "expected fixed today, by
  4 PM" — because "in progress" with no date is what makes somebody phone."*
* **THE LOOKUP** — *"Two ways in, on both widths: the **reference** we gave them, or
  a **phone number they left**, which returns everything reported from it in the
  last 90 days. A reference on a scrap of paper is the thing people lose… so the
  fallback is on the screen, not behind a link."*
* **NO SIGN-IN** — *"**Either key alone opens it**, because most reporters have no
  account. It therefore shows only what a passer-by may see: what was reported,
  where, and what is being done. No names, no customer addresses, no account
  details."*
* **OTHERS REPORTED IT** — *"Saying four other people reported the same thing
  answers "does anyone know?" — and stops a fifth duplicate report."*

| State | The drawing's words |
|---|---|
| NOT FOUND | *""We cannot find that reference." Offers the phone-number lookup and our number, and never confirms whether a reference exists."* |
| SEVERAL FOUND | *"A phone number with three reports lists them, newest first, each opening its own thread."* |
| FIXED | *"Green, with what was done and when — a report that ends silently reads as ignored."* |
| OVERDUE | *"Says the expected date has passed and gives a new one. Owning it beats silence."* |
| NOT OURS | *"Says which body is responsible — a streetlight may belong to the city."* |

**COMPONENTS** `PortalFrame` · `Field` · `Thread` · `StatusCard`

---

## 11 · Help — `/:tenant/portal/help` (and `/visit`)

State chip: **EXISTS BEHIND** · **COMMITMENT CPB-23** · *"No door named."*

> **The question:** the portal has not answered me — how do I reach a person, and
> when are they there?

### PHONE · 390 — in order

```
Help
TALK TO SOMEONE
(281) 555-0164
Mon–Fri, 8 AM – 5 PM · open now
Emergencies, 24 hours, same number
Search    🔍 What do you need help with?
COMMON QUESTIONS
  Why is my bill higher this month?   ›
  How do I read my meter?             ›
  What if I cannot pay?               ›
  How do I start or stop service?     ›
  What is budget billing?             ›
💡 Worth knowing · A running toilet can use 4,000 gallons a month.
COME AND SEE US
  Main office
  412 Water St, Burnet, TX 78611
  Mon–Fri 8 AM – 5 PM · cash, card, check
  → Directions
```

### DESKTOP · 1280 — in order

```
Help
🔍 What do you need help with?
COMMON QUESTIONS
  Why is my bill higher this month?              ›
  How do I read my meter?                        ›
  What if I cannot pay my bill?                  ›
  How do I start or stop service?                ›
  What is budget billing, and should I use it?   ›
  Why was my meter estimated?                    ›
  How do I report a leak?                        ›

TALK TO SOMEONE                                       (right rail)
  (281) 555-0164
  Mon–Fri, 8 AM – 5 PM Central · open now
  Emergencies      24 hours, same number
  Email            help@silvercreekwater.com
  We reply to email within 1 working day.
💡 Worth knowing · A running toilet can use 4,000 gallons a month.
COME AND SEE US
  Main office · 412 Water St, Burnet, TX 78611
  Mon–Fri 8 AM – 5 PM · cash, card and check accepted
  Payment drop box · 24 hours, outside the main office
  → Directions · → All locations
```

* **FOR** — *"Reaching a person, and answering the seven questions that make up
  most of the call volume before anyone dials."*
* **COGNITIVE LOAD** — *"The phone number is the loudest thing, with the hours and
  whether the office is open **right now**. A number without hours produces a call
  to a closed office and a second call tomorrow."*
* **QUESTIONS, NOT TOPICS** — *""Billing enquiries" is a filing category; "Why is
  my bill higher this month?" is what someone types."*
* **THE TIP** — *"One line, from the utility's own list, in a quiet band below the
  questions — never above them and never beside the phone number… **Exactly one
  tip renders per screen**."*
* **WHEN THERE IS NO TIP** — *"**No band at all** — not an empty box, not a
  placeholder."*

| State | The drawing's words |
|---|---|
| CLOSED NOW | *"Says when it opens next, and what to do in the meantime."* |
| NO ARTICLES | *"Falls back to the phone number and email — never an empty search box."* |
| TIP OUT OF SEASON | *"The band is absent entirely. Nothing says "no tip today"."* |
| NO RESULTS | *"Offers the three most-read articles plus the phone number."* |
| ONE OFFICE | *"No "all locations" link — a list of one is furniture."* |

**COMPONENTS** `PortalFrame` · `SearchField` · `ArticleRow` · `ContactCard` ·
`ServiceCentreCard`

---

## 12 · One help article — `/:tenant/portal/help/:slug`

State chip: **EXISTS BEHIND** · **COMMITMENT CPB-23** · *"No door named."*

> **The question:** the article title matched my problem — does the answer
> actually solve it, and what do I do next?

```
← Help
Why is my bill higher this month?
Updated Aug 2026 · 2 minutes to read             (390)
Updated August 2026 · about 2 minutes to read    (1280)

Four things change a bill from one month to the next, and usually only one of
them is at work.
1 · You used more. …
2 · The billing period was longer. …
3 · Prices changed. …
4 · A meter read was estimated. …

SEE IT FOR YOUR OWN BILL
  We can show which of these applies to yours, with the figures.
  [ Why my August bill costs this → ]
DID THIS HELP?   👍 Yes   👎 No           (390)
Did this answer your question?  👍 Yes  👎 No     (1280)
RELATED
  → Why was my meter estimated?
  → What is budget billing?
  → How do I read my meter?
Still not answered? Ask us a question — we reply within one working day.
```

* **THE PANEL THAT MATTERS** — *"A generic article about bill increases is worth far
  less than the customer's own attribution. Every article that has a live
  equivalent links straight to it — reading about a thing is second best to seeing
  it."*
* **COGNITIVE LOAD** — *"Reading time and the last-updated date are stated."*

| State | The drawing's words |
|---|---|
| NO SUCH ARTICLE | *"Offers the search and the three most-read, never a bare 404."* |
| NOT SIGNED IN | *"The "see it for your own bill" panel becomes a sign-in prompt, not a dead button."* |
| MARKED UNHELPFUL | *"Offers to ask a question, with the article's title pre-filled."* |
| OUT OF DATE | *"An article not reviewed in a year is flagged to staff, never silently trusted."* |

**COMPONENTS** `PortalFrame` · `Article` · `RelatedList` · `Feedback`

---

## 13 · Where to find us — `/:tenant/portal/visit`

State chip: **EXISTS BEHIND** · **COMMITMENT CPB-23** · *"No door named."*

> **The question:** which office is nearest, and which one can do the thing I
> need? A list of addresses answers only half of it.

### PHONE · 390 — in order

```
← Help
Where to find us
🔍 Town, ZIP code, or name
[ Nearest ] [ Takes cash ] [ Open now ] [ Open Saturday ]
14 places · showing the 3 nearest to 78611
Main office                             OPEN NOW
  412 Water St, Burnet · 4 miles
  Cash · card · check · start and stop service
  Mon–Fri 8 AM – 5 PM · → Directions
North counter                           CLOSED
  88 Lake Rd, Buchanan Dam · 11 miles
  Card and check only · no cash
  Tue and Thu 9 AM – 3 PM · → Directions
Payment drop box                        24 HOURS
  Outside the main office · 4 miles
  Check or money order only · never cash
[ Show 11 more ]
```

### DESKTOP · 1280 — in order

```
← Help
Where to find us
14 places · showing the 3 nearest to 78611
Find a place          🔍 Town, ZIP code, or the name of an office
What do you need to do?   Pay in cash ⌄
[ Search ]
[ Nearest first ] [ Open now ] [ Open Saturday ] [ Takes cash ]
[ Start or stop service ] [ Drop box ]
📍 Map · three pins around Burnet, TX
PLACE              WHERE                        WHAT YOU CAN DO              OPEN
Main office        412 Water St, Burnet · 4 mi  Cash, card, check · start &  OPEN NOW
                                                stop service · assistance
                                                paperwork
North counter      88 Lake Rd, Buchanan Dam     Card and check · no cash     OPENS TUE
                   · 11 mi
Payment drop box   Outside the main office      Check or money order ·       24 HOURS
                   · 4 mi                       never cash
Showing 3 of 14 · Show 11 more            Rows per page 25 ⌄

LOOKING TO PAY CASH?                                  (right rail)
  Only the main office takes cash. The drop box never does — never post cash and
  never leave it in the box.
DO YOU NEED TO COME IN AT ALL?
  Paying, starting service, stopping service and assistance applications can all
  be done here on the site.
  [ Pay online instead ]
```

* **SEARCH, BECAUSE THREE IS NOT THE NUMBER** — *"The drawing showed three places and
  a scroll, which is right for one utility and wrong for the next. A city system
  can have a dozen counters, drop boxes and partner payment agents… So: a search by
  **town, ZIP or name**, filters for what a place can actually do, and server-side
  paging — "showing 3 of 14", never the whole list at once and never a cap on how
  many a utility may have."*
* **FILTER BY THE ERRAND, NOT BY THE FEATURE** — *"takes cash · open now · open
  Saturday · start or stop service · drop box."*
* **THE CASH WARNING** — *"Called out separately, because posting cash or dropping it
  in a box is a real and unrecoverable loss."*

| State | The drawing's words |
|---|---|
| ONE LOCATION | *"Opens screen 42 directly — a list of one is furniture."* |
| NO LOCATION SHARED | *"Sorted alphabetically instead of by distance, with no error. Search still works."* |
| SEARCH FINDS NOTHING | *""No place matches 'Marble Falls'." Offers the full list and the phone number."* |
| TWO OR THREE PLACES | *"Search and filters are absent — a search box over three rows is furniture."* |
| ALL CLOSED | *"Says when the next one opens, and points at the drop box and the online routes."* |
| NONE CONFIGURED | *"Falls back to the phone number rather than an empty page."* |

**COMPONENTS** `PublicFrame` · `SearchField` · `FilterChips` · `Map` ·
`LocationRow` · `OpenNowBadge` · `Pagination`

**RULES** *"Server-side paging, and **no cap on how many service centres a utility
may have** — the same rule that governs every other list in the product."*

---

## 14 · One service centre — `/:tenant/portal/visit/:slug`

State chip: **EXISTS BEHIND** · **NO COMMITMENT**

⚠ The blueprint corrects itself on this screen, at the head of the spec:
> **WAS:** *Nothing in the portal links to an individual service centre*
> **NOW:** ANSWERED — **the door was built.** `CentresPage.tsx` now links each
> centre to `/:tenant/portal/visit/:slug`; the route-reachability guard names it.
> Fixed by the doors wave, `DEF-CWP-…`

…and then its own **HOW YOU GET HERE** row, further down the same spec, still
reads the superseded sentence: *"Nothing. Nothing in the portal links to an
individual service centre — `/:tenant/portal/visit/:slug` has no inbound link of
any kind, constructed or literal. Where to find us lists the places and does not
open one. Filed as a defect."*

> **The question:** I am going to come in and pay — where is it, when is it open,
> and can I pay cash?

### PHONE · 390 — in order

```
← Help
Main office
Open now · until 5:00 PM today
WHERE
  412 Water St
  Burnet, TX 78611
  → Directions · ☎ (281) 555-0164
OPENING HOURS
  Mon – Fri     8:00 AM – 5:00 PM
  Saturday      Closed
  Sunday        Closed
  Closed Nov 27 – 28 for Thanksgiving.
WHAT YOU CAN DO HERE
  · Pay by cash, card, check or money order
  · Start or stop service
  · Hand in assistance paperwork
  · Payment drop box, outside, 24 hours
  Parking            Free, at the rear
  Step-free access   Yes, from the car park
```

### DESKTOP · 1280 — in order

```
← Help
Main office · 412 Water St, Burnet
📍 Map · 412 Water St, Burnet, TX 78611
WHAT YOU CAN DO HERE
  Pay a bill                        Cash · card · check · money order
  Start or stop service             Bring photo ID
  Hand in assistance paperwork      Yes
  Payment drop box                  Outside, 24 hours
  Parking                           Free, at the rear
  Step-free access                  Yes, from the car park

OPEN NOW  until 5:00 PM                              (right rail)
Today is Monday, Sep 8.
OPENING HOURS
  Monday – Friday   8:00 AM – 5:00 PM
  Saturday          Closed
  Sunday            Closed
  Closed Nov 27 – 28 for Thanksgiving, and Dec 24 – 25.
→ Directions · ☎ (281) 555-0164 · → All our locations
```

* **COGNITIVE LOAD** — *"Open-or-closed **right now** is the headline, above the
  hours table. Holiday closures are listed rather than left to be discovered at the
  door."*
* **WHAT YOU CAN DO HERE** — *"Not every office does everything. Payment methods are
  named explicitly — cash is the reason a large share of these visits happen, and
  no other channel accepts it."*
* **ACCESSIBILITY** — *"Step-free access and parking are facts somebody needs before
  setting out, not afterwards."*

| State | The drawing's words |
|---|---|
| CLOSED NOW | *"Amber, says when it opens next, and points at the 24-hour drop box."* |
| CLOSED TODAY ONLY | *"A holiday closure says which holiday and the next open day."* |
| TEMPORARILY CLOSED | *"Says why and for how long, with the nearest alternative."* |
| NO MAP | *"The address and directions link still work — a map that fails must not take the address with it."* |

**COMPONENTS** `PortalFrame` · `OpenNowBadge` · `HoursTable` · `Map`

**RULES** *"The address is the utility's own service centre — one of the three
places in the product that legitimately holds an address of its own, because it is
not a property that takes service."*

---

## The standards these eleven screens are drawn to (blocks A–E), quoted

Block **A** — *"In the portal every icon carries its word."* · *"One glyph, one
meaning: ↓ download · ↗ opens elsewhere · ✎ change · 👁 view · ⚠ needs attention."*
· *"Colour is never the only signal. Overdue is red **and** says "Past due"."* ·
*"No emoji as a section marker. A utility bill is a financial document. Icons label
controls; they do not decorate headings."*

Block **B** — *"**The two numbers, everywhere.** Amount due and due date appear in
the same place on every screen."* · *"Never ask them to compute."* · *"**One primary
action.** One filled button per screen."* · *"Plain words over correct ones."* ·
*"Recognition over recall."* · *"**The bad news comes with the way out.** A past-due
notice never appears without the help beside it."* · *"Name, service address and
account number ride in the frame… on every signed-in screen."*

Block **C** — *"MONEY $1,247.31 — dollars, comma thousands, two decimals. Never four
on screen."* · *"DATES MM/DD/YYYY, and a written month where there is room."* ·
*"THE WORDS THEY KNOW Past due · Budget billing · Autopay · Paperless · Shut-off
notice · Payment arrangement · **ZIP code**."* · *"ASSISTANCE IS A FIRST-CLASS
PATH."* · *"USAGE IN THEIR OWN UNIT."* · *"PAPER STILL EXISTS."*

Block **D** — *"**GUEST — SCREENS 01 TO 16, AND ANY OF 11–14 REACHED SIGNED OUT**:
Silver Creek Water · Pay a bill · Report a problem · Prices · Help · Visit us ·
🌐 English ⌄ · ☎ (281) 555-0164 · Sign in."* (**lane 1's**, recorded here only
because it is the frame every one of my screens renders inside.)

Block **E** — *"**A route existing is not a door.** Every screen's spec now carries
a How you get here row naming its real inbound links, read from the source rather
than assumed."*
