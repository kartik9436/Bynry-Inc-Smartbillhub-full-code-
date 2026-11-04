# CR-085 step 1 · lane 4 — HOME AND ACCOUNTS · **as built, and every difference**

<!-- ── Trace ──────────────────────────────────────────────
     Change:  CR-085 step 1 lane 4 — IDENTIFY ONLY. NOT ONE LINE OF PRODUCT
              CODE WAS CHANGED BY THIS LANE.
     Drawing: CR-085-lane4-01-drawing-quoted.md (this folder) — the labels,
              quoted, in order.
     Read in: SOURCE at worktree b4063d1e6, and in a BROWSER against the
              shared stack at http://127.0.0.1:8401, tenant `brazosbend`,
              at 1280 AND 390, on 2026-09-11.
     Rules:   hard-won law 6 (no gate in this repo reads rendered output) ·
              hard-won law 2's mirror (a live screen behind a dead control) ·
              B14 rule 21 · rule 31 · rule 32 · rule 35 · rule 39 ·
              SKILL.md §4 (presence · order · labels · alignment · spacing ·
              weight · colour · state)
     ───────────────────────────────────────────────────── -->

> ⚠ **AMENDED 2026-09-11 BY THE SAME LANE'S STEP 2 — READ
> `CR-085-lane4-05-step2-after.md` BESIDE THIS FILE.** Eleven of the deltas below
> are FIXED and one of them was WRONG. `H-01`, `H-07`, `H-08`, `H-16`, `H-17`,
> `A-02`, `A-04`, `A-07`, `O-02`, `P-09` and `X-01` are built; **`H-02` was an
> over-generalisation** — the blueprint's screen 25 gives Home no page title at
> either width and `pageHeadCensus.test.ts` records `CWP-022` as correctly
> headless, so *"every drawn screen opens with its name"* was read off
> `DEF-CWP-4000`'s census rather than off the drawing. What was genuinely absent
> on Home is the `data-screen` mark on its failed and loading branches, and that
> is what step 2 added. **`P-09` and `P-03` are no longer open questions:** the
> PO ruled both on 2026-09-11 (`BR-CWP-107`, `BR-CWP-108`). Every other delta
> here stands, and the step-2 file says which and why.

## How this was read, and what the reading can and cannot prove

**The stack had no customer to sign in as.** `portal_credential` held **0 rows**
for `brazosbend`, so every signed-in address answered the grey failure panel.
The login used below was created **through the product's own enrolment flow** —
`POST enrol/find-account` → `verify-code` → `set-password`, the same three calls
the `/enrol` screen makes — and is left in place for the sibling lanes:

> **`elena@example.test` / `Brazos-Bend-2026!`**, tenant `brazosbend`.

⚠ **WHAT THE FIXTURE CANNOT SHOW, STATED UP FRONT RATHER THAN DISCOVERED BY THE
NEXT READER.** `brazosbend` holds **one** account (`AC-2026-00001`), **one**
customer (Elena Rivera), **zero** invoices and **zero** payments. So this lane
walked every screen in its **one-account, nothing-owed, no-bill** state and
**could not exercise**: the past-due treatment, the month chooser, the account
switcher, the multi-account table, the usage tile, the paying-together action,
or any state that needs a balance. Every delta below is marked
**MEASURED** (seen in the browser) or **SOURCE** (read out of the component, the
state being unreachable on this fixture). A SOURCE delta is a claim about the
code and is as checkable as a MEASURED one; it is simply not a claim about a
picture.

No JavaScript error and no 4xx was raised on any of the six routes at either
width.

---

# HOME — `CWP-022` at `/portal/home` · drawn as screen 25

## What it renders (1280, measured)

```
[frame: bar · nav · account line]          ← lane 1
YOUR ACCOUNT                       ACTIVE
  Name on the account       Elena Rivera
  Plan                Residential Standard
  Billed                          Monthly
  Equipment              M-7001 · W-7001
  Mobile                    ••• ••• 0100
  Email               e•••@example.com
  Paperless                          Post
BALANCE
$0.00
We cannot yet show how a payment was split across a bill.
                         [rail] Paying by instalments?
                                We can spread what you owe over several
                                months and hold the arrears while you pay.
                                [Ask for a plan] [Where things stand]
```

At **390** the same content, with `BALANCE` **above** `YOUR ACCOUNT` — the
`max-md:order-1/2` swap works and matches the drawing's *"on a phone it sits
BELOW it"*. Nothing scrolls sideways (`scrollWidth 390 = clientWidth 390`).

## Deltas

| # | | What the drawing says | What is built | How read |
|---|---|---|---|---|
| **H-01** | **WRONG SCREEN AT AN ADDRESS THE DRAWING NAMES** | Screen 26: *"The portal serves the home page at both `/{tenant}/portal` and `/{tenant}/portal/home`. Both render screen 03 … so a link written by a person, an email template or another system does not 404."* | `portalRoutes.tsx:63` maps `/` to `<FrontPage />` — the **guest** front page, `CWP-001` — and `FrontPage` contains no redirect and no session read. A **signed-in** customer opening `/{tenant}/portal` gets the *"What do you need?"* errand grid with a **Sign in** bar on it. | MEASURED at both widths, signed in |
| **H-02** | **NO HEADING OF ANY KIND** | Every drawn screen opens with its name. | `Home.tsx` composes **no `PageHeader` and no `<h1>`** — the only one of the six. It opens straight into a `Card`. | MEASURED · this is `DEF-CWP-4000` still open for `CWP-022`; the other five are now fixed |
| **H-03** | **THE PRIMARY ACTION IS ABSENT** | **PRIMARY ACTION:** ***Pay $191.00 now** — the button carries the amount, so the decision is made before the tap.* And beneath it, **Set up autopay**. | The lead tile is a **read-only figure**. `Pay {{amount}}` exists only inside the `attention` list, which the server populates; **`autopay` appears nowhere in `Home.tsx`** (grep count 0), so **Set up autopay has no door from Home in any state**. | SOURCE (no balance on this fixture) |
| **H-04** | **"AMOUNT DUE" IS CALLED "BALANCE"** | **WORDS:** *"Amount due", "Due Aug 22", "in 9 days". Never "Outstanding balance" or "Net position".* | The lead tile reads **`BALANCE`** (`portal.home.balance`, `defaultValue: "Balance"`). The screen's own other heading, `portal.home.whatYouOwe` = *What you owe*, is the drawn vocabulary and is used on `/account` instead. | MEASURED |
| **H-05** | **THE ACCOUNT CARD IS MISSING FIVE OF ITS ELEVEN FACTS** | *account number · name · service address · service area, route and cycle · which services · the plan · the equipment installed · phone · email · the ID on file*, plus *Status **ACTIVE since Jun 2, 2026***. | Built rows: Name on the account · Plan · **Billed** · Equipment · Mobile · Email · **Paperless**. **Absent: service area/route/cycle · Services · ID on file · the status DATE** (the chip says `ACTIVE`, never *since*). *Account number* and *service address* are on the frame line, which the drawing itself allows. **Extra, not drawn: Billed, Paperless.** ⚠ `Services` IS coded (`identity.services`) and rendered nothing here because the row drops when the list is empty — so on a richer fixture this row may appear. | MEASURED + SOURCE |
| **H-06** | **THE SETTINGS LINE IS ABSENT** | *Autopay on · Paperless off · Budget billing off · No deposit held · Nothing past due · → **Everything about this account***. | Nothing of this line is built. Only `Paperless` survives, as a `KVList` row. | MEASURED |
| **H-07** | **NO DOOR FROM HOME TO "ONE ACCOUNT"** | The card ends with *→ All account details* (phone) / *→ Everything about this account* (desktop). | `/account` (`CWP-065`) is linked from **exactly one place in the whole portal** — `MyDetails.tsx:289`. Home links to it from nowhere, in any state. | MEASURED (link list) + SOURCE (`grep '"/account"'` returns the route row and one caller) |
| **H-08** | **THE DRAWN "NOTHING DUE" STATE IS NOT BUILT** | *NOTHING DUE: "You are all paid up." with the next bill date. **Not an empty card.*** | With `$0.00` owing the tile prints **`$0.00`** and no sub-line at all. The string *paid up* exists in **no catalogue** (`grep 'paid up'` over `en.json` → 0 hits). | MEASURED — this is the exact state the fixture is in |
| **H-09** | **"NEXT METER READ" IS ABSENT** | A drawn region of its own, both widths: *Next meter read · Sep 30 · in 22 days*. | `Home.tsx` contains no `next read` of any spelling (grep count 0). | SOURCE |
| **H-10** | **THE BILL PANEL'S MONTH CHOOSER IS DRAWN FOR SIX MONTHS AND BUILT OVER `recent_bills`** | *a **chooser for the last six months**, showing the month and its total*. | `YourBill` builds its options from `data.recent_bills`, whatever the server sends; nothing in the client asks for six. The drawn *FEWER THAN SIX BILLS* and *A FIRST BILL MEANS NO CHOOSER AT ALL* rules **are** honoured (`bills.length > 1`). | SOURCE |
| **H-11** | **AN OLDER MONTH CHOSEN — THE DRAWN BEHAVIOUR IS NOT BUILT** | *Paid bills show "Paid Jul 19" where the due date was; the Pay button does not appear.* | `YourBill`'s `due` row always renders `bill.due_on`; there is no paid-date substitution. | SOURCE |
| **H-12** | **THE BILL PANEL SHOWS ONE TOTAL, NOT THE SERVICE LINES** | *Electric · 800 kWh `$107.50` / Water · 8 kgal `$47.50` / Sewer · 7.2 kgal `$36.00` / State & local tax `$8.30`*. | `YourBill` draws a `KVList` of **Bill · Period · Due · Usage · Amount** — the bill's identity, not its lines. The drawn `ServiceLines` component is not composed here. | SOURCE |
| **H-13** | **THE BILL PANEL'S THREE DRAWN ACTIONS ARE TWO ICONS** | *→ See the whole bill · ↓ Download PDF · → Why it costs this*. | Two bare icon links (`EyeIcon`, `PrinterIcon`) with `aria-label`s and **no visible word**. ⚠ **That is the portal's own standard A reversed** — *"In the portal every icon carries its word … Never an icon alone. On a customer's phone there is no hover, so a tooltip is invisible."* | SOURCE (no bill on this fixture) |
| **H-14** | **THE GAP SENTENCE IS NOT A DRAWN ELEMENT** | Nothing of the kind is drawn. | *"We cannot yet show how a payment was split across a bill."* renders on Home **and** on `/accounts`, in body grey, between the tiles and the two-column body. It is `NamedGaps`, and it is honest — but it is an **un-drawn sentence in the most-read position on the page**, and at `$0.00` owing it is the only sentence under the balance. | MEASURED at both widths |
| **H-15** | **A LONE TILE IN A FOUR-COLUMN GRID** | The drawn `AmountDueCard` is a full-width accent-bordered card carrying *the largest type on the page*. | `KpiRow` is `grid-cols-4` unconditionally at ≥768px. With one tile the measured columns are **`253px 253px 253px 253px`** — the balance sits in the **left quarter of a 1,060px row** with three empty columns beside it. A single-account customer with one service is the T7 majority case. | MEASURED, 1280 |
| **H-16** | **THREE STATES, ONE PICTURE** | Appendix **R-22**: *Three states — loading, empty, failed — can never render as the same picture.* And the drawing: *LOADING: skeleton cards of the right height.* | `HomeView` draws the **same bare `Card` with one grey sentence** for failed (*We could not read your balance.*), for loading (*Reading your balance…*) and — one level down — for empty (*Add an account and your balance appears here.*). No skeleton exists. The words differ; the picture does not. | SOURCE + MEASURED (loading seen as a flash) |
| **H-17** | **FAILED TO LOAD DOES NOT OFFER THE PHONE NUMBER** | *Says the bill could not be loaded and **offers the phone number**. Never a page of dashes.* | *We could not read your balance.* and nothing else. | SOURCE |

---

# YOUR ACCOUNTS — `CWP-023` at `/portal/accounts` · drawn as screen 27

## What it renders (1280, measured)

```
YOUR ACCOUNTS
All my accounts                        [Add another account]
Each account is billed on its own — nothing here is combined.
[Search accounts…]
ADDRESS ⇅   SERVICES   NEXT DUE ⇅   BALANCE ⇅   STATUS
1408 Bluestem Ln · Unit A
AC-2026-00001 · Tenant billed   Electric · Water   —   $0.00   CLEAR
1–1 of 1   Page 1 of 1   Rows per page [50]  ‹ ›
We cannot yet show how a payment was split across a bill.
[Add another account]
```

## Deltas

| # | | What the drawing says | What is built | How read |
|---|---|---|---|---|
| **A-01** | **THE DRAWN "ONE ACCOUNT" STATE IS NOT BUILT, AND IT IS THE STATE THIS FIXTURE IS IN** | *ONE ACCOUNT: **This screen is skipped entirely** — a list of one is furniture, and Home opens instead.* | The screen renders a **one-row table with a search box, a sort control on four columns, a rows-per-page chooser offering 50/100/200/500/1000, and two pagination arrows** over a single row. Nothing redirects. | MEASURED at both widths |
| **A-02** | **AT 390 THE TWO FACTS THE SCREEN EXISTS FOR ARE OFF SCREEN** | The phone drawing is **stacked blocks**, address first, then *`$247.30` · PAST DUE · Pay $247.30* — the money and the status are the largest things on it. | The table stays a table: measured **492px wide inside a 350px container**, scrolling sideways within its own box. The **BALANCE** and **STATUS** columns are past the right edge on first paint. The page itself does not scroll sideways, so every page-level check passes. | MEASURED, 390 |
| **A-03** | **COLUMN NAMES AND COUNT** | `SERVICE ADDRESS` · `ACCOUNT` · `SERVICES` · `OWED` · `STATUS` | `ADDRESS` · `SERVICES` · `NEXT DUE` · `BALANCE` · `STATUS`. `ACCOUNT` is folded into the address cell as a sub-line; `OWED` is renamed `BALANCE` (see **H-04** — the same vocabulary drift); `NEXT DUE` is added. | MEASURED |
| **A-04** | **THE PER-ROW ACTION IS AN ICON WITH NO WORD, AND IT GOES SOMEWHERE ELSE** | `Pay` on the two owing rows, `→ Open` on the paid-up one — *Open* being this property's own page. | `portal.accounts.openAccount` / `portal.accounts.payAccount` are used **only as `aria-label` and `title`** on two icon links (`EyeIcon`, `DollarIcon`). Standard A again: *never an icon alone*, and a `title` tooltip is exactly the thing the portal's own standard says is invisible on a phone. ⚠ **And the eye goes to `/bills`, not to `/account`** — so the drawn *→ Open* has no built counterpart at all and `CWP-065` keeps its single door (**H-07**). | SOURCE |
| **A-05** | **"PAY ALL THREE · $438.30" IS NOT BUILT** | **PAYING TOGETHER:** *A single payment across accounts is offered, because a landlord with eleven properties will not make eleven payments. It allocates per account and each gets its own receipt line.* | No such control exists on the screen or in the catalogue. | SOURCE |
| **A-06** | **THE SORT IS NOT THE DRAWN SORT** | *Sorted by urgency, not alphabetically — **past due first, then due soonest**.* | Four sortable columns with a reader-chosen order; nothing states or applies an urgency default. | SOURCE |
| **A-07** | **"+ ADD AN ACCOUNT" IS DRAWN ONCE AND BUILT TWICE** | One `+ Add an account`, under the list. | Rendered in the page-header action row **and** again below the table — the same label, twice on one screen. | MEASURED |
| **A-08** | **THE TOTAL BAND'S WORDS** | *TOTAL OWED · `$438.30` · across 3 accounts · 1 past due* (phone) / *3 accounts · $438.30 owed in total · 1 past due* (desktop). | `portal.accounts.totalOwing` = *Total owing*, a bold line with a rule under it; no account count and no past-due count beside it. Hidden here because the server's `show_total` is false for one account at zero. | SOURCE |
| **A-09** | **THE DRAWN "ACCESS REMOVED" AND "A CLOSED ACCOUNT" STATES** | *Stays listed, marked Closed, with its final balance if any.* / *Disappears from the list, **and says so once** rather than silently.* | Neither sentence exists in any catalogue; the row's `state` map covers `clear` / `overdue` / `due` only. | SOURCE |

---

# ONE ACCOUNT — `CWP-065` at `/portal/account` · drawn as screen 28

## What it renders (1280, measured)

```
MY DETAILS
Your account
WHAT YOU OWE
$0.00
HOW YOU ARE BILLED
Residential Standard, since Aug 1, 2026
[Your final bill] [Stop or restart service]
                    [rail] Things you can do here
                           Bills · Usage · Equipment · Requests · Documents and letters
                    [rail] This account
                           Opened    Aug 15, 2026
```

## Deltas

| # | | What the drawing says | What is built | How read |
|---|---|---|---|---|
| **O-01** | **THE HEADING IS THE WRONG THING** | The heading is the **address** — *1841 Quarry Hill Ct, Silver Creek, TX 78611* — with *Account 4417-0092 · open since Jun 2, 2026 · in the name of Marcus Bell* under it. *"The address is the heading because that is how an owner thinks of a property."* | Kicker **`MY DETAILS`**, title **`Your account`**. The address appears nowhere on the screen; the account number and the opened date are elsewhere (frame line, and a rail panel). | MEASURED |
| **O-02** | **NO BACK-LINK** | *← Accounts*, at both widths, under the bar. Appendix **R-15**: *a back-link sits under the bar, never inside it.* | No back-link. `/accounts/add` and `/my-details/preferences` both have one; this screen does not. | MEASURED |
| **O-03** | **"THIS ACCOUNT" IS EIGHT DRAWN ROWS AND ONE BUILT ROW** | *Services · Plan · Billed · Autopay · Budget billing · Paperless · Discounts · Deposit held* — each **with its consequence**: *"Paperless — Off, a paper bill costs $2.00 a month"*, *"Budget billing — Off, you would pay $171.40 a month"*. **COGNITIVE LOAD:** *A bare Off is a fact; the consequence is a decision.* | `HOW YOU ARE BILLED` → one sentence, *Residential Standard, since Aug 1, 2026*. **Absent: Services · Billed · Autopay · Budget billing · Paperless · Discounts.** `Deposit held` and `Your services` are coded and drop when the server sends nothing. **Not one consequence sentence is built.** | MEASURED + SOURCE |
| **O-04** | **"RECENT" IS NOT BUILT** | *August bill issued · Aug 5, $191.00 / Payment cleared · Jul 19, $176.20 / Meter read · Jul 31, 800 kWh* | No such block in the component or the catalogue. | SOURCE |
| **O-05** | **THE "GO TO" LIST IS RIGHT AND ITS COUNTS ARE NOT** | *→ Bills · **3** / → Usage · **4 services** / → Equipment · **3 items** / → Requests · **1 open** / → Documents · **6*** | Five doors, correct and in the drawn order, **each with no count**. The counts are half of what the drawn list is for. | MEASURED |
| **O-06** | **THE PRIMARY ACTION IS ABSENT, AGAIN** | *AMOUNT DUE · $191.00 · Due Aug 22, 2026 · in 9 days · **Pay $191.00 now*** | `WHAT YOU OWE` is a read-only `KpiTile`; no pay control. Same shape as **H-03**. | MEASURED |
| **O-07** | **TWO SCREENS, TWO NAMES FOR ONE FIGURE** | One card, one word, *"in the same position on every screen"* (appendix **R-05**). | Home calls it **BALANCE**; this screen calls it **WHAT YOU OWE**. Both are `KpiTile lead`, so the shape agrees and the **word does not**. | MEASURED |
| **O-08** | **EXTRA, NOT DRAWN** | — | `Tax exempt` panel (`Exempt` · `Runs out` · `Certificate` · *We will remind you a month before it runs out.* · `Send a new certificate`), and the two errand buttons `Your final bill` / `Stop or restart service`. | SOURCE + MEASURED |

⚠ **O-02 is worth more than its size.** `/stop-or-restart` is one of the two
flows the blueprint calls **unreachable** — *"`stop-or-restart` has no inbound
link anywhere … Moving out is one of the commonest reasons to open a utility
portal."* It now has **two** doors, both found in this walk: from `/account` and
from `/my-details`. That part of rule E's finding is closed; recorded here so
nobody re-files it.

---

# ADD AN ACCOUNT — `CWP-020` at `/portal/accounts/add` · drawn as screen 29

## What it renders (1280, measured)

```
← All my accounts
YOUR ACCOUNTS
Add another account
Both are printed on that account's bill.
Account number *          Postcode *
WHAT HAPPENS WHEN YOU ADD IT
  This account joins your list.
  A code goes to that account's own contact, not to you.
  Nothing is combined — bills stay separate.
[Find this account]   (disabled: "Both fields are needed")
Already on this login
  1   1408 Bluestem Ln · Unit A   $0.00
                    [rail] Taking over an account?
                           If the account is in somebody else's name, we have to
                           change that for you — this form does not.
                           [Visit us]
```

## Deltas

| # | | What the drawing says | What is built | How read |
|---|---|---|---|---|
| **D-01** | **THE ZIP FIELD IS CALLED A POSTCODE** | *ZIP code of that service address* | `portal.addAccount.postcode` = **`Postcode`**. The whole portal catalogue is British here — `portal.enrol.postcode`, `portal.myDetails.postcode`, `portal.quickPay.postcode`, `portal.track.secondFact`, `portal.postcodeHelper` — over a product CLAUDE.md scopes to **North American utilities**. Mine are `/accounts/add` and `/my-details`; the other four belong to the enrol, quick-pay and track lanes and are named here so they are not missed. | MEASURED |
| **D-02** | **"WHERE TO FIND IT ON THE BILL" IS A SENTENCE, NOT A DOOR** | *→ Where to find it on the bill* — a link, on the phone drawing. | *Both are printed on that account's bill.* — a lead sentence, no link, no picture. | MEASURED |
| **D-03** | **A THIRD STEP THE DRAWING DOES NOT HAVE** | Two fields, one button, one outcome: *Add it*. | Three fields across two steps — `Account number` + `Postcode` → **Find this account** → a **six-digit code** sent to *that account's own contact* → **Add this account**. The security posture is defensible and it is **not the drawn flow**, and the drawing's own `ADDED` / `NO MATCH` / `DIFFERENT NAME` states were written for the two-field form. | MEASURED (step 1) + SOURCE (step 2) |
| **D-04** | **THE PHONE NUMBER IS NOT IN THE REFUSAL** | *TAKING OVER AN ACCOUNT? … **Call us on (281) 555-0164.*** | *If the account is in somebody else's name, we have to change that for you — this form does not.* + a `Visit us` door. **No telephone number.** The drawn `DIFFERENT NAME` state also says *refused with the reason **and the phone number***. | MEASURED |
| **D-05** | **"WHAT THIS DOES" IS RENAMED AND RE-WRITTEN** | *WHAT THIS DOES — Adds the account to your list here. It does not change whose name it is in, and it does not move any balance.* | `WHAT HAPPENS WHEN YOU ADD IT`, three bullets, one of which (*A code goes to that account's own contact, not to you*) describes **D-03**'s extra step and has no drawn counterpart. The drawn *"it does not move any balance"* is not said. | MEASURED |
| **D-06** | **EXTRA, NOT DRAWN** | — | An `Already on this login` panel listing the accounts already held, with a count and each balance. Useful; undrawn. | MEASURED |
| **D-07** | **THE BUTTON LABEL** | *Add it* | `Find this account` then `Add this account`. Follows from **D-03**. | MEASURED |

---

# MY DETAILS — `CWP-024` at `/portal/my-details` · drawn as screen 57

## What it renders (1280, measured)

```
MY DETAILS
My details
Changes here reach your account.
  Email [elena.rivera@example.com]   Mobile [+1 (281) 555-0100]
  This is where your bill is posted. Your service address is not changed here.
  Postal address [1408 Elm St]
  Town or city [Katy]                Postcode [ ]
  [Save changes ✓]   (disabled: "Nothing has changed yet")
  [How we contact you →] [All my accounts] [Your account] [Stop or restart service]
                    [rail] NOT CHANGED HERE
                           Name on the account   Elena Rivera
                           Account holder        Ask us to change this
                           We check these at the counter, so a request comes to us first.
                    [rail] YOUR SIGN-IN
                           Password changed   Sep 11, 2026
                           Codes go to        Your mobile
                           Devices signed in  2
```

## Deltas

| # | | What the drawing says | What is built | How read |
|---|---|---|---|---|
| **M-01** | **THE "HOW WE CONTACT YOU" BLOCK IS NOT ON THIS SCREEN** | Six drawn rows **on screen 57 itself**: *Your bill · Payment reminders · Payment taken · Outages near you · Planned work · Language*, with a `Save`. | A single door, `How we contact you →`, to `CWP-025`. The whole block lives one screen away. | MEASURED |
| **M-02** | **"GO PAPERLESS" IS ABSENT** | *GO PAPERLESS — Stop the paper bill and save $2.00 a month. **[Switch to paperless]*** | Nothing. The paperless consent control is on `CWP-025` and states *You have not been asked about paperless billing*; the drawn money sentence exists nowhere. | MEASURED |
| **M-03** | **"WHERE YOU GET SERVICE" IS ABSENT** | *ADDRESSES — Where you get service `1841 Quarry Hill Ct, Silver Creek, TX 78611` / Where your bill goes `The same address`* | Only the postal address is drawn, under a sentence. `MyDetails.tsx` records the reasoning — the service address is on the frame line and hard rule 8 forbids a second copy — so this is **a deliberate divergence with a stated reason**, not an oversight. It is still a difference and the drawing still shows two rows where the product shows one. | MEASURED + SOURCE |
| **M-04** | **"WHERE YOUR BILL GOES: THE SAME ADDRESS" IS NOT SAID** | A row that reads *The same address* when they match. | The postal fields simply hold whatever is on file (here `1408 Elm St`, which is **not** the service address `1408 Bluestem Ln`), and nothing says whether the two agree. | MEASURED |
| **M-05** | **THE REFUSAL IS A SENTENCE ABOVE, NOT BESIDE** | **THE HONEST REFUSAL:** *"the screen says so **beside it** rather than offering a field that fails"* — drawn as a tail on the link: *· your service address cannot be changed here*. | *This is where your bill is posted. Your service address is not changed here.* sits **above** the Postal address field. Said, correctly; not where it is drawn. | MEASURED |
| **M-06** | **`Account 4417-0092` IS A DRAWN ROW OF THIS CARD** | *Account `4417-0092`* is the fourth row of `YOU` on the desktop drawing. | Frame line only. Same allowance as **M-03**. | MEASURED |
| **M-07** | **THE DRAWN `Change` / `Change your details` CONTROL** | *→ Change* (phone) / *→ Change your details* (desktop) — the drawing's `YOU` block is **read-only with one Change door**. | The fields are **directly editable in place** with a `Save changes ✓`. This is a better product and a different drawing; recorded so the two are known to differ rather than assumed to agree. | MEASURED |
| **M-08** | **NO `Change password` AND NO `Sign out everywhere`** | Not drawn on screen 57 — but recorded here because **two live documents already claim it is an open defect and cite the wrong id** (see `DEF-CWP-4362`). | The `YOUR SIGN-IN` panel states three facts — *Password changed*, *Codes go to*, *Devices signed in* — and offers **no control at all**, including none for the *2 devices signed in* it names. **A row of facts with no way to act on them.** | MEASURED |
| **M-09** | **EXTRA, NOT DRAWN** | — | The whole right rail: `NOT CHANGED HERE` and `YOUR SIGN-IN`. And the four errand buttons under Save. | MEASURED |
| **M-10** | **THE DRAWN `EMAIL UNVERIFIED` STATE** | *Says so and offers to resend, because bills sent there are bouncing.* | No such state in the component or the catalogue. (`returned post` is built, for the postal address, and is the drawing's neighbour rather than this state.) | SOURCE |

---

# HOW WE CONTACT YOU — `CWP-025` at `/portal/my-details/preferences` · drawn as screens 58 **and** 59

## What it renders (1280, measured)

```
← My details
MY DETAILS
How we contact you
One choice, used for everything we send you, on your account.
  EMAIL AS WELL [On|Off]    TEXT AS WELL [On|Off]
  WHAT WE SEND                    POST     EMAIL  TEXT  IN THE PORTAL
  Confirmations                   ALWAYS   Off    Off   ALWAYS
  Your bill                       ALWAYS   Off    Off   ALWAYS
  Moving in and out               ALWAYS   Off    Off   ALWAYS
  Notices about your account      ALWAYS   Off    Off   ALWAYS
  Payment received                ALWAYS   Off    Off   ALWAYS
  Payment plan letters            ALWAYS   Off    Off   ALWAYS
  ⓘ Turning these off stops the email or the text, never the letter.
    We post everything, always.
  PAPER                              LANGUAGE
  You have not been asked about       Write to me in [Not chosen yet ▾]
  paperless billing. We post          2 languages available.
  everything to you.                  [Save language ✓]
                                      This website: English
                                      Your bills and letters use the language
                                      above; this site follows it.
```

## Deltas

| # | | What the drawing says | What is built | How read |
|---|---|---|---|---|
| **P-01** | **GROUPED BY CHANNEL, WHICH IS THE ONE THING THE DRAWING FORBIDS** | **GROUPED BY SUBJECT:** *By what it is about — your bill, money, your service — **not by channel**. Nobody thinks "which of my emails do I want"; they think "stop telling me about roadworks".* Three drawn headings: `YOUR BILL` · `MONEY` · `YOUR SERVICE`. | A **matrix**: rows are message kinds, **columns are POST / EMAIL / TEXT / IN THE PORTAL**. There are no subject groups. This is the single largest divergence in this lane. | MEASURED at both widths |
| **P-02** | **THE ROW NAMES ARE THE PRODUCT'S, NOT THE CUSTOMER'S** | *Your bill is ready · Reminder before it is due · We took a payment · A payment failed · You are past due · Outages near you · Planned work in your street · We are coming to read your meter* | *Confirmations · Your bill · Moving in and out · Notices about your account · Payment received · Payment plan letters.* Six internal message families where the drawing names eight things that happen to a customer. **Absent entirely: a payment failed · you are past due · outages near you · planned work · meter reading visits.** | MEASURED |
| **P-03** | **"ONE OF THESE MUST STAY ON" IS NOT BUILT** | *YOUR BILL · **ONE OF THESE MUST STAY ON*** and the `LAST BILL CHANNEL` state: *Turning off the second one is refused with the reason, not silently ignored.* | Not built, and **it cannot be**: the product's rule is the print floor — *We post everything, always* — so paper can never be turned off. The two rules are incompatible and the built one is the one the business has. **This is a drawing that needs re-ruling, not a defect to fix.** | MEASURED |
| **P-04** | **THE TWO UNSWITCHABLE ROWS ARE NOT NAMED** | *A payment failed · Text and email · always* / *You are past due · Text and email · always* / *The last two cannot be switched off — a shut-off notice must reach you.* | `ALWAYS` chips appear on **POST and IN THE PORTAL for all six rows**; EMAIL and TEXT are switchable everywhere. The drawn promise — a shut-off notice always reaches you by text and email — is not made. | MEASURED |
| **P-05** | **THE CHANNEL-OFF CALLOUT IS ABSENT** | *TEXT MESSAGES ARE OFF AT THIS UTILITY — Silver Creek Water has not switched text messaging on. Anything set to **Text** above will arrive by email instead — nothing is silently dropped.* Drawn on 57 **and** 58; the drawing calls it *"the failure this panel exists to prevent — somebody waiting for a text that can never be sent."* | The screen offers a `TEXT AS WELL` toggle and says nothing about whether this utility can send a text. | MEASURED |
| **P-06** | **"WHERE THESE GO" IS ABSENT** | *WHERE THESE GO — Email `m.bell@example.com` / Phone `(512) 555-0148` / → Change these on My details* | Not built. The back-link `← My details` is the only route back. | MEASURED |
| **P-07** | **THE PAPERLESS SAVING IS NOT STATED** | *On paper — posted to your service address · On · **$2.00 a month*** and *Turning paper off saves **$24.00 a year**.* | *You have not been asked about paperless billing. We post everything to you.* No figure, monthly or annual. | MEASURED |
| **P-08** | **THE SEGMENTED `On|Off` PAIR IS NOT A DRAWN CONTROL** | Every drawn preference is a **`▾` select** carrying its current value as a word (*Email and paper*, *Text · 3 days before*). | Two segmented `On|Off` button pairs at the top (`EMAIL AS WELL`, `TEXT AS WELL`) plus per-cell `Off` text in the matrix. A control shape the drawing does not use anywhere. | MEASURED |
| **P-09** | **SCREEN 59 IS NOT BUILT, AND THE PRODUCT SAYS THE OPPOSITE OF WHAT IT DRAWS** | ***There are two languages and they can disagree.*** *… This screen names both, shows when they differ, and offers one tap to align them* — with `THESE TWO DO NOT MATCH`, `Make everything Español`, the language list *written in its own language first*, and the `WHAT CHANGES, AND WHEN` table. | One line: *This website: English*, and under it *"**Your bills and letters use the language above; this site follows it.**"* — i.e. the product asserts the two **cannot** differ. `Preferences.tsx` records why (`BR-CWP-105`, PO 2026-09-07: the account preference is re-applied on every render, so a website picker would revert under the customer's hand) and says in as many words that the drawn banner *"needs the two to be allowed to differ, which is a ruling nobody has made."* ⚠ **This is a live product statement and a signed drawing contradicting each other and it needs a PO ruling, not a lane's choice.** | MEASURED + SOURCE |
| **P-10** | **`CHOOSE A LANGUAGE` LISTS TWO** | Five, each *written in its own language first* (B14 rule 35, appendix R-20). | *2 languages available.* — the tenant's own setting, which the drawing's own RULES line allows (*Languages offered are the utility's own setting*). **Not a delta; recorded so it is not mistaken for one.** | MEASURED |

---

# Cross-cutting, all six screens

| # | | Finding | How read |
|---|---|---|---|
| **X-01** | **THIRTY USER-VISIBLE STRINGS HAVE NO CATALOGUE KEY IN ANY OF THE ELEVEN LANGUAGES** | Every one is a `t("…", { defaultValue: "English words" })` whose key is absent from **all eleven** locale files, so **the English `defaultValue` renders for a reader in German, Japanese, Korean, Hindi, Portuguese and the rest**. `tsc`, eslint, every DOM test and every gate pass, because the string genuinely renders. **26 of the 30 are on Home**, including the lead tile's own label. Full list below. | SOURCE (checked against all 11 `locales/*.json`) + MEASURED (they render) |
| **X-02** | **THE ICON-ONLY ROW ACTIONS** | `CWP-022`'s two bill icons and `CWP-023`'s row icons carry `aria-label`s and no word, against the portal's own **standard A** — *"In the portal every icon carries its word … Never an icon alone … one of those glyphs sends a disconnection notice."* This reverses the staff rule deliberately and the portal has not followed its own reversal. | SOURCE + MEASURED |
| **X-03** | **THE SCREEN-ID CHIP IS ON** | `CWP-001` … `CWP-065` render as a dark chip bottom-right of every screen. **This is deliberate** — `PortalScreenIdTag.tsx`, PO 2026-09-03 *"We need unique screen ID - on every screen"*, behind `VITE_SCREEN_ID_TAG`. **Not a defect.** Recorded because it trips every *"no internal id on screen"* check a reader will run, and because its own classes are `px-[9px] py-[3px]` — **ad-hoc 9 and 3**, the two numbers B14 rule 39 bans by name. That part belongs to whoever owns the tag. | MEASURED |
| **X-04** | **NO PAGE-LEVEL SIDEWAYS SCROLL AT 390** | All six routes measured `scrollWidth == clientWidth == 390`. The only over-wide element is `CWP-023`'s 492px table, correctly inside its own scroller — which is allowed, and which is nevertheless **A-02**. | MEASURED |
| **X-05** | **NOTHING EXISTS ONLY WHEN WIDE** | The visible text at 390 and at 1280 is the same set on all six screens. | MEASURED (both walks diffed) |
| **X-06** | **CPB-17 IS REAL AND IT IS ALL SIX OF MINE** | Signed out, every one of the six answers: *"**Failed** — We could not open this page. You're signed out. Sign in again to continue. [Retry] [Download error report] [Cancel]"*. `CPB-17`'s `SCREENS` column names 53 · 54; its own text says *"True of every signed-in screen, not just one."* It is. | MEASURED, signed out, both widths |

## X-01 — the thirty keys, in full

`Home.tsx` (26): `portal.home.balance` · `acrossAccounts` · `usageThisMonth` ·
`viewAll` · `dueSoon` · `paySentenceDated` · `paySentence` · `allBills` ·
`instalments` · `instalmentsBody` · `askForPlan` · `colBill` · `colPeriod` ·
`period` · `colUsage` · `colAmount` · `openBill` · `printedBill` · `chartTitle` ·
`usageDoor` · `service.varies` · `service.plan` · `service.billed` ·
`service.paperless` · `service.paperlessOn` · `service.paperlessOff`

`MyAccounts.tsx` (2): `portal.accounts.openAccount` · `portal.accounts.payAccount`

`AddAccount.tsx` (2): `portal.addAccount.takingOverTitle` ·
`portal.addAccount.takingOver`

`YourAccount.tsx`, `MyDetails.tsx`, `Preferences.tsx`: **none** — all three are
fully catalogued.

⚠ **`portal.home.acrossAccounts` carries a second, sharper version of the same
bug.** Its own comment says *"The catalogues carry `_one` and `_other`"*. They
carry neither — no `acrossAccounts`, no `acrossAccounts_one`, no
`acrossAccounts_other`, in any of the eleven files. That is hard-won law 1 inside
a comment written to justify the code beneath it.

---

# What was filed, and what deliberately was not

**Twelve rows went to `12-governance/10-defect-log.csv`.** Every one names the
delta above that it records, so a reader can go from either direction.

| Row | Delta | Category | Sev |
|---|---|---|---|
| `DEF-CWP-4899` | **X-01** — thirty user-visible strings with no catalogue key in any of eleven languages, 26 of them on Home | `copy-i18n` | medium |
| `DEF-CWP-4900` | **H-01** — a signed-in customer at `/{tenant}/portal` gets the guest front page with a *Sign in* bar on it | `wrong-logic` | medium |
| `DEF-CWP-4901` | **H-07 · A-04** — `CWP-065` has one inbound link in the whole portal and it is not the drawn one | `built-not-wired` | medium |
| `DEF-CWP-4902` | **rule 39 field anatomy** — the helper sits 17px below its input where 6px is ratified; the shared `FormField` never zeroed the paragraph's browser margin | `design-divergence` | medium |
| `DEF-CWP-4903` | **rule 39 KPI anchor** — tile side padding 16 where 20 is ratified, row gap 16 where 24 is | `design-divergence` | low |
| `DEF-CWP-4904` | **H-15** — a lone 253px balance tile in a four-column grid | `design-divergence` | medium |
| `DEF-CWP-4905` | **A-02 · A-07** — at 390 the accounts table puts BALANCE and STATUS off screen; *Add another account* renders twice | `design-divergence` | medium |
| `DEF-CWP-4906` | **H-08 · H-16 · H-17** — the drawn NOTHING DUE, FAILED TO LOAD and LOADING states | `not-built` | medium |
| `DEF-CWP-4907` | **P-01 … P-06** — `CWP-025` grouped by channel, which its drawing forbids by name | `design-divergence` | medium |
| `DEF-CWP-4908` | **D-01** — the portal asks a North American customer for their *Postcode* | `copy-i18n` | low |
| `DEF-CWP-4909` | **M-08** — `YOUR SIGN-IN` states three facts and offers no control; also the correct home for what `DEF-CWP-4362` mis-cites | `not-built` | medium |
| `DEF-CWP-4910` | **O-01 … O-05** — `CWP-065` shows one of eight drawn rows and no consequence sentence | `not-built` | medium |

## What was NOT filed, and why

* **`H-02`, Home has no heading** — it is `DEF-CWP-4000`, still open, and this
  lane re-verified it rather than re-filing it.
* **`P-09`, the two languages** — the product asserts *"this site follows it"*
  and blueprint screen 59 says *"there are two and they can differ"*. Both are
  deliberate, both are written down, and `Preferences.tsx` already records that
  the drawn banner *"needs the two to be allowed to differ, which is a ruling
  nobody has made."* **That is a question for the PO, not a defect**, and a lane
  that files it as a defect converts a product decision into our error — which
  is the thing `13-change-process.md` step 1 exists to stop happening in the
  other direction.
* **`P-03`, "one of these must stay on"** — same shape: it is incompatible with
  the print floor the business actually has (`R-19`). The drawing needs
  re-ruling; there is nothing to fix.
* **`M-03`, `M-06`, `M-07`, `D-03`, `D-05`, `O-08` and the other "extra, not
  drawn" rows** — each is a deliberate, reasoned departure recorded in the
  component's own docstring (hard rule 8 for the service address, the
  send-a-code step for account-takeover safety). They are listed above because
  the drawing and the product differ and somebody should know; they are not
  defects.
* **`X-03`, the screen-id chip** — ruled by the PO on 2026-09-03 and gated
  behind `VITE_SCREEN_ID_TAG`. Its `px-[9px] py-[3px]` is a genuine rule-39
  breach and belongs to whoever owns the tag, not to this lane's six screens.
