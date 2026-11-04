# CR-085 step 1 · lane 4 — HOME AND ACCOUNTS · **the drawing, quoted**

<!-- ── Trace ──────────────────────────────────────────────
     Change:  CR-085 step 1 lane 4 — IDENTIFY ONLY. No product code was
              changed by this lane.
     Source:  05-prototype/SMARTBillHub Customer Portal Blueprint.pdf,
              129 pages, section 04 "Your account, once you are in"
              (pages 47-55) and section 10 "You and your settings"
              (pages 99-105).
     Read at: 2026-09-11, worktree detached at b4063d1e6.
     Rules:   react-tailwind-css-ui-generator SKILL.md §1 — "QUOTE the
              drawing into your working notes — do not link it. The labels,
              in order, in front of you while you type. A link gets skimmed;
              a quote gets built."
     ⚠ The PDF text layer joins words with U+FFFE and U+00AD. Both were
       stripped before matching, per the lane brief, so an absence recorded
       here is a real absence and not an extraction artefact. Page 129 is
       truncated mid-table in the source; it is outside this lane's sections.
     ───────────────────────────────────────────────────── -->

## Which drawings this lane owns

Six routes under `/:tenant/portal/`, carrying **eight drawn screens**:

| Route | Drawn screen | Built screen id |
|---|---|---|
| `/` (and `/home`) | **25 · Home** | `CWP-022` at `/home`; `/` is `CWP-001`, see delta H-01 |
| `/home` | **26 · Home, at its second address** | `CWP-022` |
| `/accounts` | **27 · Your accounts** | `CWP-023` |
| `/account` | **28 · One account** | `CWP-065` |
| `/accounts/add` | **29 · Add an account** | `CWP-020` |
| `/my-details` | **57 · Your details** | `CWP-024` |
| `/my-details/preferences` | **58 · How we contact you** | `CWP-025` |
| `/my-details/preferences` | **59 · Your language · signed in** | (no separate screen — see delta P-09) |

Section 04's own opening sentence, verbatim:

> *Five screens. One property for most people; for a landlord or a small
> business, several — and everything else in the portal assumes one, which is
> what these make safe.*

Section 10's, verbatim:

> *Four screens. Who you are, how we reach you, in what language, and everything
> we have ever sent.*

The fourth screen of section 10 is **60 · Documents** at `/documents` — **not this
lane's**, and its own `HOW YOU GET HERE` row says *Bills. **Not My details.***

---

## 25 · Home — `/portal` and `/portal/home`

> **The question:** what do I owe, when is it due, and is anything wrong?
> Nothing else belongs above the fold.

### PHONE · 390 — every label, in the order drawn

```
Marcus Bell
Account 4417-0092
1841 Quarry Hill Ct, Silver Creek TX
Home   Bills   Usage   Help
🏠 1841 Quarry Hill Ct        3 accounts ▾
AMOUNT DUE
$191.00
Due Aug 22, 2026 · in 9 days
Pay $191.00 now
Set up autopay
YOUR ACCOUNT
  Account            4417-0092
  Name               Marcus Bell
  Service address    1841 Quarry Hill Ct
                     Silver Creek, TX 78611
  Services           ⚡ 💧 🚿 🗑
  Equipment          8841-C · W-2209 · F-0118
  Status             ACTIVE
  → All account details
YOUR BILL
  August ▾
  Electric · 800 kWh      $107.50
  Water · 8 kgal           $47.50
  Sewer                    $36.00
  → See the whole bill
USAGE
  ⚡ Electric ▾
  800 kWh
  5% less than July · 12% more than last August
Next meter read
  Sep 30 · in 22 days
```

⚠ **On the phone the account card sits BELOW the amount due.** The drawing says
so in its own words: *"on a phone it sits BELOW it — compact, four rows, with
'all account details' expanding the rest. On the width where space is scarce,
the money wins and the identity is one tap away."*

### DESKTOP · 1280 — every label, in the order drawn

```
Silver Creek Water
Home  Bills  Usage  Payments  Requests  Help  My details   🌐 English   ·  Sign out
Marcus Bell  ·  1841 Quarry Hill Ct, Silver Creek, TX 78611  ·  Account 4417-0092
$191.00 due Aug 22

YOUR ACCOUNT
  4417-0092 · Marcus Bell
  🏠 1841 Quarry Hill Ct ▾  · 3 accounts
  Service address   1841 Quarry Hill Ct
                    Silver Creek, TX 78611
  Service area      Quarry Hill · Route 4 · Cycle 2
  Services          ⚡ Electric · 💧 Water
                    🚿 Sewer · 🗑 Trash
  Plan              Residential Standard
  Status            ACTIVE since Jun 2, 2026
  Equipment         8841-C · W-2209 · F-0118
                    → See equipment
  How we reach you  (•••) •••-0148
                    m•••••@example.com
  ID on file        Driving licence ••••4417
                    → Show · → Change
  Autopay on  ·  Paperless off  ·  Budget billing off  ·  No deposit held  ·
  Nothing past due  ·  → Everything about this account

AMOUNT DUE
  $191.00
  Due Aug 22, 2026 · in 9 days
  Pay $191.00 now
  Set up autopay

YOUR BILL
  August 2026 · $191.00 ▾
  BL-2608-000077 · Jul 1 – Jul 31 · due Aug 22
  Electric · 800 kWh        $107.50
  Water · 8 kgal             $47.50
  Sewer · 7.2 kgal           $36.00
  State & local tax           $8.30
  → See the whole bill     ↓ Download PDF     → Why it costs this

USAGE
  ⚡ Electric ▾
  800 kWh — 5% less than July
  → See all your usage

NEXT METER READ
  Sep 30
  in 22 days

SERVICE
  1841 Quarry Hill Ct
  ACTIVE
  Electric · Water · Sewer · Trash
```

### The paragraphs that decide the screen, verbatim

**FOR** — *Answering the whole visit in one glance for the majority who came to
check or pay.*

**PRIMARY ACTION** — ***Pay $191.00 now** — the button carries the amount, so the
decision is made before the tap.*

**COGNITIVE LOAD** — *Amount and date in the largest type on the page, in the
accent-bordered card that appears in the same position on every screen. Usage is
a comparison, not a raw figure.*

**THE ACCOUNT CARD** — *A wide card under the bars carrying everything that
identifies the account:* ***account number · name · service address · service
area, route and cycle · which services · the plan · the equipment installed ·
phone · email · the ID on file***. *It is the answer to "am I in the right place,
and does this look like me" — the question a landlord with three properties, and
anybody about to phone, asks first.*

**EQUIPMENT AS REFERENCES** — *The serials alone — **8841-C · W-2209 · F-0118** —
not "Electric meter 8841-C · 5/8 inch". … the room that frees carries the
**account status**, which is the fact people actually check.*

**STATUS, ON THE CARD** — ***Active since Jun 2, 2026**, as a chip and a date.
Below it the settings that change what happens next month — autopay, paperless,
budget billing, deposit held, and whether anything is past due.*

**THE MONTH CHOOSER** — *The bill panel carries a **chooser for the last six
months**, showing the month and its total — "August 2026 · $191.00".*

**WHAT IS MASKED, AND WHY** — *Phone, email and the government ID are **masked by
default and revealed on request** … Only the last four of an ID is ever shown …
The account number is **not** masked.*

**THE ACCOUNT SWITCHER** — *Top right of the card and, on a phone, above the
amount due: **the current property with a count of the rest** … it is **absent
entirely for a customer with one account**.*

**WHICH SERVICE** — *The usage tile carries a **service picker**, built from the
services this customer actually has … a customer with only one service gets no
picker at all, because a chooser with one option is furniture.*

**WORDS** — *"Amount due", "Due Aug 22", "in 9 days". Never "Outstanding balance"
or "Net position".*

**COMPONENTS** — `PortalFrame` · `AmountDueCard` · `ServiceLines` · `UsageSpark` ·
`Button`

**RULES** — *No internal id on screen — the bill number is the customer's, the
database id is not. One filled button.*

### The drawn STATES, verbatim — all eight

| State | The drawing's own words |
|---|---|
| LOADING | *Skeleton cards of the right height. Never dashes — a dash means "genuinely none".* |
| NOTHING DUE | *"You are all paid up." with the next bill date. Not an empty card.* |
| PAST DUE | *The card turns red, reads **PAST DUE**, and the help link sits inside it, not elsewhere.* |
| FAILED TO LOAD | *Says the bill could not be loaded and offers the phone number. Never a page of dashes.* |
| ONE ACCOUNT | *The switcher is absent — a chooser with one option is furniture.* |
| FEWER THAN SIX BILLS | *The chooser lists what exists. A first bill means no chooser at all.* |
| AN OLDER MONTH CHOSEN | *Paid bills show "Paid Jul 19" where the due date was; the Pay button does not appear.* |
| NO ID ON FILE | *That row is absent rather than shown empty; a prompt appears only where one is required.* |

**Door:** *No door named. This screen carries no **How you get here** row, though
the document's own rule E says every screen does. It is one of 37. See CPB-23.*

---

## 26 · Home, at its second address — `/portal/home`

> ***Not a separate screen.** The portal serves the home page at both
> `/{tenant}/portal` and `/{tenant}/portal/home`. Both render screen 03; the
> second exists so a link written by a person, an email template or another
> system does not 404.*

**WHY BOTH EXIST** — *`/{tenant}/portal` is what the frame links to and what a
signed-in customer lands on. `/{tenant}/portal/home` is the spelling a human
writes and the one that turns up in emails and bookmarks.*

**WHAT MUST BE TRUE** — *They must render the **same screen**, not two that
drift. One route table entry pointing at one component — never a second copy
that gets a fix the other does not.*

**LISTED HERE** — *So that all fifty routes are accounted for and nobody later
finds an address nothing describes.*

---

## 27 · Your accounts — `/portal/accounts`

> **The question:** which of my properties owes what, and which one needs me
> today?

### PHONE · 390

```
Accounts   Bills   Payments   Help
Your accounts
TOTAL OWED
$438.30
across 3 accounts · 1 past due
  12 Quarry Hill Ct      4417-0114   $247.30   PAST DUE   Pay $247.30
  1841 Quarry Hill Ct    4417-0092   $191.00   Due Aug 22
  220 Lakeview Dr        4417-0155   $0.00     PAID UP
+ Add an account
```

### DESKTOP · 1280

```
Your accounts
3 accounts · $438.30 owed in total · 1 past due

SERVICE ADDRESS        ACCOUNT      SERVICES                     OWED      STATUS
12 Quarry Hill Ct      4417-0114    Water · Sewer                $247.30   PAST DUE     Pay
1841 Quarry Hill Ct    4417-0092    Electric · Water ·           $191.00   Due Aug 22   Pay
                                    Sewer · Trash
220 Lakeview Dr        4417-0155    Water                        $0.00     PAID UP      → Open

+ Add an account
Pay all three · $438.30
```

**FOR** — *Landlords and small businesses. One glance says which property needs
attention today.*

**COGNITIVE LOAD** — *Sorted by urgency, not alphabetically — past due first,
then due soonest. The address is the heading because that is how an owner thinks
of a property; the account number is underneath for when they phone.*

**PAYING TOGETHER** — *A single payment across accounts is offered, because a
landlord with eleven properties will not make eleven payments. It allocates per
account and each gets its own receipt line.*

### The drawn STATES, verbatim

| State | The drawing's own words |
|---|---|
| ONE ACCOUNT | *This screen is skipped entirely — a list of one is furniture, and Home opens instead.* |
| MANY ACCOUNTS | *Paged with a search by address. Never a full unpaged list, at any number.* |
| A CLOSED ACCOUNT | *Stays listed, marked Closed, with its final balance if any.* |
| ACCESS REMOVED | *Disappears from the list, and says so once rather than silently.* |

**COMPONENTS** — `PortalFrame` · `AccountRow` · `StatusChip` · `Button` ·
`Pagination`

**RULES** — *Server-side paging, no cap on how many accounts one person may hold
— a property company is a real customer.*

---

## 28 · One account — `/portal/account`

> **The question:** everything about this one property, on one page — what it
> costs, what is installed, who it is in the name of.

### PHONE · 390

```
← Accounts
1841 Quarry Hill Ct
Account 4417-0092 · open since Jun 2, 2026
AMOUNT DUE
$191.00
Due Aug 22, 2026
Pay $191.00 now
THIS ACCOUNT
  In the name of   Marcus Bell
  Services         Electric · Water · Sewer · Trash
  Plan             Residential Standard
  Autopay          On · bank ····4417
  Paperless        Off
  Deposit held     $0.00
GO TO
  → Bills        3
  → Usage        4 services
  → Equipment    3 items
  → Requests     1 open
```

### DESKTOP · 1280

```
← Accounts
1841 Quarry Hill Ct, Silver Creek, TX 78611
Account 4417-0092 · open since Jun 2, 2026 · in the name of Marcus Bell

THIS ACCOUNT
  Services         Electric · Water · Sewer · Trash
  Plan             Residential Standard
  Billed           Monthly, around the 5th
  Autopay          On — full bill, on the due date, from bank ····4417
  Budget billing   Off — you would pay $171.40 a month
  Paperless        Off — a paper bill costs $2.00 a month
  Discounts        None applied
  Deposit held     $0.00

RECENT
  August bill issued    Aug 5, $191.00
  Payment cleared       Jul 19, $176.20
  Meter read            Jul 31, 800 kWh

AMOUNT DUE
  $191.00
  Due Aug 22, 2026 · in 9 days
  Pay $191.00 now

GO TO
  → Bills · 3
  → Usage · 4 services
  → Equipment · 3 items
  → Requests · 1 open
  → Documents · 6
```

**FOR** — *The whole picture of one property, for somebody who holds several and
needs to answer a question about this one.*

**COGNITIVE LOAD** — *Settings are shown with their consequence, not just their
state: "Paperless — Off, a paper bill costs $2.00 a month", "Budget billing —
Off, you would pay $171.40 a month". A bare Off is a fact; the consequence is a
decision.*

### The drawn STATES, verbatim

| State | The drawing's own words |
|---|---|
| CLOSED | *Header says closed and when; the due card becomes the final balance or a credit.* |
| PENDING START | *Says service begins Sep 14 and no bill exists yet.* |
| NOT IN YOUR NAME | *A tenant on a landlord's account sees the services and their own bills, not the owner's details.* |
| PAST DUE | *The due card takes the past-due treatment, with the three ways out.* |

**COMPONENTS** — `PortalFrame` · `AmountDueCard` · `DetailRow` · `JumpList`

**RULES** — *The account number is the customer's reference and is shown; the
database id is not. The address is derived from the property record.*

---

## 29 · Add an account — `/portal/accounts/add`

> **The question:** I have another property with you — how do I see it here too,
> without a second sign-in?

### PHONE · 390

```
← Accounts
Add an account
Another property you hold with us
Account number                      4417-0155
→ Where to find it on the bill
ZIP code of that service address    78611
Add it
220 Lakeview Dr added. It is on your accounts list now.
The account must already be in your name. To take over someone else's, call us.
```

### DESKTOP · 1280

```
← Accounts
Add an account
Another property you already hold with us — one sign-in covers all of them.
Account number                      4417-0155
ZIP code of that service address    78611
Add it

WHAT THIS DOES
Adds the account to your list here. It does not change whose name it is in, and
it does not move any balance.

TAKING OVER AN ACCOUNT?
If the account is in someone else's name — you have bought the property, or a
tenant has left — this is not the way. Call us on (281) 555-0164.
```

**FOR** — *One sign-in covering every property a person holds.*

**THE DISTINCTION THAT MATTERS** — *Adding an account to a view is not taking one
over. The screen says so and routes a transfer to the phone, because a change of
responsible party has legal and deposit consequences a form cannot settle.*

### The drawn STATES, verbatim

| State | The drawing's own words |
|---|---|
| NO MATCH | *One message for the pair, rate-limited — the same guessable pair as quick-pay.* |
| ALREADY ADDED | *"That account is already on your list." Links to it.* |
| DIFFERENT NAME | *Refused with the reason and the phone number, never a silent failure.* |
| ADDED | *Confirmation names the address, not the number — that is how the owner recognises it.* |

**COMPONENTS** — `PortalFrame` · `Field` · `Callout ok` · `Callout warn`

---

## 57 · Your details — `/portal/my-details`

> **The question:** is my phone number right, is my bill going to the right
> place, and how do you contact me?

### PHONE · 390

```
Home   Bills   Usage   You
Your details
YOU
  Name    Marcus Bell
  Email   m.bell@example.com
  Phone   (512) 555-0148
  → Change
ADDRESSES
  Where you get service   1841 Quarry Hill Ct
                          Silver Creek, TX 78611
  Where the bill goes     Same
  → Send my bill somewhere else
HOW WE CONTACT YOU
  Your bill            Email + paper
  Payment reminders    Text
  Outages nearby       Text
  Language             English
```

### DESKTOP · 1280

```
Your details
YOU
  Name                            Marcus Bell
  Email — where your bill is sent m.bell@example.com
  Phone                           (512) 555-0148
  Account                         4417-0092
  → Change your details
ADDRESSES
  Where you get service   1841 Quarry Hill Ct, Silver Creek, TX 78611
  Where your bill goes    The same address
  → Send my bill somewhere else · your service address cannot be changed here
HOW WE CONTACT YOU
  Your bill            Email and paper ▾
  Payment reminders    Text ▾
  Payment taken        Email ▾
  Outages near you     Text ▾
  Planned work         Email ▾
  Language             English ▾
  Save
GO PAPERLESS
  Stop the paper bill and save $2.00 a month.
  Switch to paperless
```

**FOR** — *Keeping contact details right — the single biggest cause of a customer
never receiving a shut-off notice.*

**COGNITIVE LOAD** — *Each contact row says what it is **for**, not just its name:
"Email — where your bill is sent". Grouped by purpose, not by channel.*

**THE HONEST REFUSAL** — *The service address cannot be changed here, and the
screen says so beside it rather than offering a field that fails. Where the bill
goes is genuinely separate and genuinely editable.*

**THE CHANNEL-OFF CASE** — *If the utility has switched a channel off entirely,
the row says so — "Text messages are not switched on at this utility" — instead
of offering a preference that silently does nothing.*

### The drawn STATES, verbatim

| State | The drawing's own words |
|---|---|
| EMAIL UNVERIFIED | *Says so and offers to resend, because bills sent there are bouncing.* |
| SAVED | *A confirmation naming what changed, not a generic tick.* |
| CHANNEL UNAVAILABLE | *The row is stated as unavailable with the reason, never left switchable.* |
| PAPERLESS ALREADY ON | *The offer disappears rather than repeating something done.* |

**COMPONENTS** — `PortalFrame` · `DetailRow` · `PreferenceRow` · `Select` ·
`Button`

**RULES** — *The account number is the customer's reference and is shown. No
database id appears. The address is derived from the property record.*

---

## 58 · How we contact you — `/portal/my-details/preferences`

> **The question:** which of these actually reach me, and can I stop the ones I
> do not want without losing the ones I need?

### PHONE · 390

```
← My details
How we contact you
YOUR BILL
  Email   On
  Paper   On · $2.00 a month
  One of these must stay on.
MONEY
  Bill is ready        Email ▾
  Payment reminder     Text ▾
  Payment taken        Email ▾
  Payment failed       Text + email
  A failed payment always reaches you both ways.
YOUR SERVICE
  Outages near you      Text ▾
  Planned work          Email ▾
  Meter reading visits  Off ▾
Text messages are not switched on at this utility. Anything set to text will
arrive by email instead.
Save
```

### DESKTOP · 1280

```
← My details
How we contact you
Grouped by what it is about, not by email or text.

YOUR BILL · ONE OF THESE MUST STAY ON
  By email — to m.bell@example.com                  On ▾
  On paper — posted to your service address         On · $2.00 a month ▾
  Turning paper off saves $24.00 a year.

MONEY
  Your bill is ready               Email ▾
  Reminder before it is due        Text · 3 days before ▾
  We took a payment                Email ▾
  A payment failed                 Text and email · always
  You are past due                 Text and email · always
  The last two cannot be switched off — a shut-off notice must reach you.

YOUR SERVICE
  Outages near you                 Text ▾
  Planned work in your street      Email ▾
  We are coming to read your meter Off ▾
  Save

TEXT MESSAGES ARE OFF AT THIS UTILITY
  Silver Creek Water has not switched text messaging on. Anything set to Text
  above will arrive by email instead — nothing is silently dropped.

LANGUAGE
  Everything we send you           English ▾
  Bills, notices and letters, in your language.

WHERE THESE GO
  Email   m.bell@example.com
  Phone   (512) 555-0148
  → Change these on My details
```

**FOR** — *Control over what arrives, without letting anyone switch off the
messages that must reach them.*

**GROUPED BY SUBJECT** — *By what it is about — your bill, money, your service —
**not by channel**. Nobody thinks "which of my emails do I want"; they think
"stop telling me about roadworks".*

**WHAT CANNOT BE SWITCHED OFF** — *A failed payment and a past-due notice always
go both ways, and the screen says why. A customer who silences a shut-off notice
has not exercised a preference; they have lost their service.*

**THE CHANNEL-OFF CASE** — *If the utility has not enabled a channel, the screen
says so and states what happens instead.*

### The drawn STATES, verbatim

| State | The drawing's own words |
|---|---|
| LAST BILL CHANNEL | *Turning off the second one is refused with the reason, not silently ignored.* |
| EMAIL UNVERIFIED | *Flagged here too — preferences pointing at a bouncing address are worthless.* |
| CHANNEL DISABLED | *The row stays visible, marked unavailable, with what happens instead.* |
| SAVED | *Names what changed, not a generic tick.* |

**COMPONENTS** — `PortalFrame` · `PreferenceRow` · `Select` · `Callout warn`

---

## 59 · Your language · signed in — `/portal/my-details/preferences`

> **The question:** I set the website to Spanish, but my bill still arrives in
> English. Which one is which, and how do I change the one that matters?

### PHONE · 390

```
← How we contact you
Your language
EVERYTHING WE SEND YOU
  English    → Change
  Bills, letters, texts and emails. Set on your account, so it follows you to
  any device.
THIS WEBSITE
  Español    → Change
  What you are reading now, on this device only.
These two are different right now. You are reading Spanish, and your bills
arrive in English.
Make my bills Spanish too
CHOOSE
  English            ›
  Español · Spanish  ›
  Tiếng Việt · Vietnamese  ›
  中文 · Chinese      ›
```

### DESKTOP · 1280

```
← How we contact you
Your language
There are two, and they can differ — which is usually not what anyone intends.

EVERYTHING WE SEND YOU — THE ONE THAT MATTERS
  Your bill, letters, notices, texts and emails     English ▾
  Set on your account. It follows you to any device, and it is what a shut-off
  notice arrives in.

THIS WEBSITE
  What you are reading now                          Español ▾
  Held in this browser. Signing in on another device does not carry it over.

THESE TWO DO NOT MATCH
  You are reading this site in Español, and your bills and notices arrive in
  English.
  Make everything Español
  Or leave them different on purpose — some people prefer the site in one and
  paperwork in another.

CHOOSE A LANGUAGE
  English            YOUR BILLS
  Español · Spanish  THIS WEBSITE
  Tiếng Việt · Vietnamese   Choose
  中文 · Chinese      Choose
  Français · French  Choose
  Each is written in its own language first, so it can be found by somebody who
  reads no English.

WHAT CHANGES, AND WHEN
  This site           Straight away
  Emails and texts    Next one sent
  Your printed bill   Next bill run
  A bill already printed does not change.
```

**THE WHOLE POINT** — ***There are two languages and they can disagree.** The one
on the account decides what a bill and a shut-off notice arrive in; the one in
the browser decides what this site looks like. A customer who sets the site to
Spanish reasonably assumes their bill follows. This screen names both, shows when
they differ, and offers one tap to align them.*

**WHICH ONE IS LOUDER** — *The account language, in the accent-bordered card,
because it is the one that carries a disconnection notice. The website language
is second.*

**NOT FORCED** — *Different on purpose is a legitimate choice … The mismatch is
flagged, never corrected automatically.*

### The drawn STATES, verbatim

| State | The drawing's own words |
|---|---|
| THEY MATCH | *The amber panel is absent entirely, not shown saying "these match".* |
| ONE LANGUAGE | *The whole screen is absent — nothing to choose.* |
| NOT TRANSLATED | *A language offered for bills but not for the site says which is which.* |
| CHANGED | *Confirms what changed and when each part takes effect.* |

**COMPONENTS** — `PortalFrame` · `LanguageRow` · `Callout warn` · `Select`

**RULES** — *Catalogues are authored in their own language, never
machine-translated. Languages offered are the utility's own setting.*

---

## What the frame draws, and is therefore NOT this lane's

Per the lane brief, and stated once so no reader mistakes an absence here for an
absence anywhere: **the heading bar, the menu words, the account line (name,
service address, account number, amount due) and the page-heading gap belong to
lane 1.** Every drawing above shows them and this lane records only what sits
*below* them. The one exception is noted at delta H-02, where the account CARD's
contents overlap the account LINE's and the drawing says which fact belongs
where.
