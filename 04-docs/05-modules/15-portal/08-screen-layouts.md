# 15 · Customer Web Portal — screen layouts

**One entry per screen, written while looking at its wireframe** (`wireframes/CWP-###.png`,
rendered from the blueprint 2026-09-03). Each entry names the **frame**, the **template**,
the **regions top-to-bottom** and the **components** from `09-component-inventory.md` — and
nothing that is not in that inventory.

**Where a drawing and B14 disagree, B14 wins, and the entry says so** — the blueprint's
own §26 lists seventeen places it corrected itself, and the stories carry the corrections.

**Phone layouts (`CWP-076`–`079`) are deferred** — PO instruction 2026-09-03.

## Templates

| Code | Shape | Used by |
|---|---|---|
| **T1** | `GuestFrame` → `PageHead` → `CardGrid3` → `InfoBar` | guest hubs |
| **T2** | frame → `Stepper` → `TwoCol` [main `Card` \| rail `Panel`s] | every multi-step flow |
| **T3** | `PortalShell` → `PageHead` → `TwoCol` [main \| rail] | most signed-in pages |
| **T4** | frame → `PageHead` → `TwoEqual` | two equal panels |
| **T5** | frame → `PageHead`(+actions) → `DataTable` (toolbar · rows · footer) → optional `InfoBar` | list pages |
| **T6** | frame → `PageHead`(detail: back link) → body | detail pages |
| **T7** | frame → single `Card` ≈ 70% wide, no rail | focused tasks |
| **T8** | `BackOfficeFrame` → `PageHead` → body | staff screens |

`TwoCol` is `grid-cols-12` with `col-span-8` / `col-span-4`; drawn at ≈ 62/35.

---

## Guest surface — `CWP-001` … `CWP-014`

### CWP-001 · G1 · The public front page — T1
`GuestFrame` (Sign in as an outlined header button) → `PageHead` kicker **PINE HILL WATER &
POWER** · title *What do you need?* · subtitle → `CardGrid3` × 2 rows: six `ErrandCard`s
(*Pay a bill · Report a problem · Check my area · Start service · What things cost · Help &
answers*), each `Button(outline, sm)` *Start →* → `InfoBar` (`i` · *Already have a login?
**Signing in shows…*** · `Button(outline)` *Sign in*).
States ⚠ **REWRITTEN 2026-09-05 — THE PO REVERSED ALL THREE OF THEM.** Verbatim: *"Yoi ahev
these cards - may be disable them, but for completess have them on screen"*. **All six cards
are always drawn.** A card the tenant cannot offer is DISABLED — the card recedes to the page
ground, its words drop to the muted step, `aria-disabled` is set — and its `Start →` is a
`HeldButton` carrying one sentence of six words or fewer:
· switch off → *Not offered online at the moment.*
· *Check my area* (`R9`) → *No status page here yet.*
· *Help & answers*, nothing published → *Nothing published here yet.*
*What things cost* is OFFERED and merely has no screen, so it keeps `R3`'s own hold —
*Opens with the next release.* — which is a different state and must not be collapsed into
the three above. **The nav words are unchanged: *Help* and *Visit us* still appear only when
something is published.** No rail.

### CWP-002 · G2 · Quick pay · find the bill — T2
`GuestFrame` → `Stepper` 3 (**1** current · 2 · 3) → main `Card` [kicker **PAY A BILL** ·
section title *Find your bill* · grey line · `FormField` *Bill number\** · `FormField`
*ZIP code of the service address\** · `Button` *Continue →* **held**] · rail [`Panel`
**WHERE TO FIND IT** · `Panel.Warning` (five wrong tries…)].
<!-- ⚠ *ZIP code* CORRECTED FROM *Postcode* 2026-09-11 (`DEF-CWP-4855`). The
     blueprint's conventions block C names the vocabulary a North American
     utility customer expects and this word is in the list; the extraction wrote
     the British one and the product followed it onto three live screens. Only
     `en.json` moved — the other ten catalogues already carry their own
     language's right word (B14 rule 35). -->

### CWP-003 · G3 · Quick pay · check and pay — T2
`Stepper` (✓ · **2** · 3) → main `Card` [`KVList` Bill / Service address / **Billed to
`M. A••••••`** / Due → `TotalRow` *Owing $142.18* · section title **HOW YOU ARE PAYING** ·
`FormField` card number · `TwoUp` Expires\* \| Security code\* · `FormField` Email
(optional) + helper · `ConsequenceBox` (3 bullets) · `ButtonRow` *Pay $142.18 ✓* **held**]
· rail [`Panel` **WHY SO LITTLE IS SHOWN** · `Panel.Warning` nothing can charge a card].
⚠ The name is masked **server-side** (`US-CWP-004`).

### CWP-004 · G4 · Quick pay · done — T2 (two cards ≈ 55/45)
`Stepper` (✓ · ✓ · **3**) → left `Card` [kicker **PAID** · title *$142.18 received, thank
you* (two lines, 28px) · `KVList` Reference / Paid / Against / Method · `ButtonRow`
`Button(outline)` *↓ Receipt* · *✉ Email it to me*] · right `Card` with `border-l-4
border-l-[var(--brand)]` [title *Want this to be easier next time?* · grey two lines ·
`KVList` We already know / You would add · `Button` *Set up a login →* **held**].

### CWP-005 · G5 · Check my area — **DEFERRED, do not build** (`R9`)
Drawn for the record only: T5 with a toolbar (search · two toggle chips *Happening now* \|
*Planned* · *Updated 9:40am* right), a `DataTable` What(bold + grey sub)/Where/Since/Back
on/Status(`StatusChip` danger CREW ON SITE · warning LOOKING INTO IT · neutral PLANNED),
a rail `Panel` **YOUR STREET IS NOT LISTED?** + `Button(outline)` *Report a problem*, and a
`Panel.Warning`.

### CWP-006 · G6 · Report a problem — T3 shape under `GuestFrame`
`PageHead` kicker **REPORT A PROBLEM** · title *Tell us what is wrong* · subtitle →
`TwoCol`: main `Card` [section title **WHAT IS HAPPENING?** · `RadioList` × 6 with inline
grey hints (*· We treat this as urgent*) · `FormField` *Where\** + helper · textarea
*Anything else* · `PhotoPicker` · `TwoUp` Your name\* \| Phone\* · `ConsequenceBox` ·
*Send this report ✓* **held**] · rail [`Panel.Emergency` *Is anyone in danger?* (brand
left rule, phone number bold) · `Panel.Info` already reported].
⚠ *Smell of gas* returns a phone number and creates nothing (`US-CWP-007`).

### CWP-007 · G7 · Report sent — T3 shape under `GuestFrame`
main `Card` [kicker **SENT** · title *Thank you — that is with us* · grey line · `KVList`
Reference / Reported / Where / What · `ButtonRow` *✉ Text me the reference* · *Check my
area*] · rail [`Panel` **WHAT HAPPENS NOW** = `ChecklistTimeline` × 4 (1 done, **2
current**, 3–4 future) + a closing sentence under a rule].

### CWP-008 · G8 · Can I get service here? — T3 shape under `GuestFrame`
`PageHead` kicker **START SERVICE** · title → main `Card` [`FormField` *Address\** ·
`Button` *Check →* **held** · rule · section title **WE SERVE THIS ADDRESS** · `MiniTable`
Service / Available (`StatusChip` success YES · neutral NOT HERE) / To connect / Deposit,
the *Electric* row greyed · `ConsequenceBox` headed **IF YOU APPLY** · *Apply for service →*
**held**] · rail [`Panel` **ALREADY SERVED?** · `Panel.Info` an unknown address is not a
refusal].

### CWP-009 · G9 · Apply for a connection · check and send — T2
`Stepper` 4 (✓ ✓ ✓ **4**) → main `Card` [`KVList` Address / Applicant / Services / Start on
/ To pay before we start / On your first bill · section title **WE WILL NEED THESE FROM
YOU** · two rows *document · `StatusChip` warning AFTER YOU APPLY* · `FormField` checkbox
*How we send your bills\** (boxed) + helper *We print them as well…* · `ConsequenceBox` (4
bullets) · `ButtonRow` *Send my application ✓* **held** · `Button(outline)` *Back*] · rail
[`Panel` **SAVED AS YOU GO** · `Panel.Info` documents come after].

### CWP-010 · G10 · Ask for a quick service — T1
`PageHead` kicker **QUICK SERVICE** · title · subtitle → `CardGrid3` × 2: six `ErrandCard`s
with `Button(outline, sm)` *Ask →* → `InfoBar` (the boundary sentence, bold clause).
Cards read from the tenant's categories, never a fixed list.

### CWP-011 · G11 · Help and answers — T3 shape under `GuestFrame`
`PageHead` kicker **HELP** · title *Answers* → main `Card` [toolbar: search · chips *All*
(selected) \| Paying \| Readings \| Moving · list rows *question · `StatusChip` info TOPIC ·
→* with 1px rules] · rail [`Panel` **STILL STUCK?** · `Button(outline)` *Ask a question* ·
rule · office and emergency lines · `Panel.Warning`].
**Absent entirely** when nothing is published (`BR-CWP-093`).
<!-- ⚠ *ABSENT* IS THE NAV WORD AND THE FRONT-PAGE CARD, NOT THE ADDRESS
     (`DEF-CWP-4854`, 2026-09-11). The route stays registered, so a typed
     address or a stale bookmark still opens it — and what that person got was
     an empty search box, an `All` chip with nothing to filter, and *"Nothing
     here matches what you typed."* said to somebody who had typed nothing.
     The screen now draws the frame, its heading and ONE sentence that says
     what is absent, with the **STILL STUCK?** rail beside it; the search box
     and the chips do not render, because neither could undo the emptiness.
     ⚠ AND THE NO-MATCH STATE IS A DIFFERENT SENTENCE FROM THE EMPTY ONE —
     R-22, ratified 2026-09-11, PO verbatim *"differntiate it using text
     message"*. -->
<!-- ⚠ THE RAIL'S *Ask a question* IS STILL NOT BUILT on this screen. The
     route `/ask-a-question` exists and is SIGNED IN; nothing on the guest help
     screen points at it. Recorded in `conformance/CR-085-lane2-findings.md`,
     not fixed in passing. -->

### CWP-012 · G12 · Track anything — T3 shape under `GuestFrame`
main `Card` [kicker **TRACK** · title *Look something up* · grey line · `FormField`
*Reference\** + helper · `FormField` *ZIP code, or the phone number you gave us\** · *Look
it up →* **held**] · rail [`Panel` **WHAT YOU WOULD SEE** = `KVList` Reference / What /
Reported / Now + rule + grey note *no account details…*].

### CWP-013 · G13 · Where you can walk in — T3 shape under `GuestFrame`
`PageHead` kicker **VISIT US** · title · subtitle → main column of `CentreCard`s [`Panel`
header: name + brand link *See this centre →* · body: bold address + `StatusChip` (success
OPEN UNTIL 5:00PM / neutral CLOSED TODAY) right · phone · hours line · rule · kicker **YOU
CAN HERE** + a row of `Button(outline, sm)` chips · **Takes** bold + grey list · `ButtonRow`
*Opening hours* · *Get directions* · on the north counter: **Not here:** bold + grey] ·
rail [`Panel` **RATHER NOT TRAVEL?** + two buttons + rule + phones · `Panel.Info` ⓘ
holidays]. Hidden centres are **absent**; no centres → the page and its link are absent.
<!-- ⚠ *THE PAGE IS ABSENT* IS THE SERVER'S 404 AND THE MISSING NAV WORD, NOT
     A BLANK SCREEN (`DEF-CWP-4853`, 2026-09-11). A typed address or a stale
     bookmark still reaches this route, and what it drew was the STAFF failure
     panel — a red *Failed* chip, *"the address may be wrong"*, and a **Download
     error report** button — rendered OUTSIDE `GuestFrame`, so with no utility
     name, no phone number and no way back. A 404 from `service-centres` is now
     read as an EMPTY: the frame, the heading, one sentence saying no counter is
     listed, and the utility's own phone number as a `tel:` beside it. Anything
     that is NOT a 404 is still a FAILURE and says so in different words, with
     the retry an empty state must not offer (R-22 · R-10, both ratified
     2026-09-11). The same split governs `CWP-014` and `CWP-060`. -->

### CWP-014 · G14 · One service centre — T6 under `GuestFrame`
`PageHead`(detail) back **← WHERE YOU CAN WALK IN** · kicker **NORTH COUNTER** · title =
the address · grey status line · actions `Button(outline)` *Get directions* ·
`Button(danger-outline as drawn → use outline)` *Call (512) 555-0148* → `TwoCol`: main
[`Panel` **WHAT YOU CAN DO HERE** rows *action · ✓ or —* + footer note · `Panel` **TAKES
PAYMENT BY** chips + grey note] · rail [`Panel` **OPENING HOURS** 7 rows, today's row bold
with `StatusChip` neutral TODAY, footer *Closed 26 November — Thanksgiving* · `Panel.Info`
ⓘ holidays not typed]. ⚠ Four of five rows say **no** on purpose.

---

## Getting in — `CWP-015` … `CWP-019` (no guest nav; URL strip reads *step n of 3*)

### CWP-015 · P1 · Front door — split `Card` 50/50
Left (brand panel): utility name `text-xl font-bold` · grey strapline · a row of service
names as plain text · rule · office and emergency lines. Right: kicker **SIGN IN** · title
*Welcome back* · `FormField` Email\* · Password\* · small link *Forgotten it?* ·
`ButtonRow` *Sign in* + checkbox text *Keep me signed in* · rule · three lines **bold
question? brand link →** (*Set up your login → · Pay with a bill number → · Start service
→*). **Not the front page** — it sits behind G1's card.

### CWP-016 · P2 · Find my account — T2
`Stepper` 3 (**1**) → main `Card` [kicker **SET UP YOUR LOGIN** · title *Find your account*
· grey line · `FormField` Account number\* · ZIP code of the service address\* · Last name,
or company name\* · `ButtonRow` *Continue →* **held** · *Cancel*] · rail [`Panel` **NO BILL
TO HAND?** · `Panel.Warning` with a `!` glyph — three tries]. ⚠ Nothing about the account is
shown on this screen (`BR-CWP-032`).
<!-- ⚠ ***Continue →* IS HELD UNTIL ALL THREE ARE TYPED, AND IT WAS NOT UNTIL
     2026-09-11 (`DEF-CWP-4858`).** The word **held** has been on this line since
     the layout was extracted and the built button had no guard at all: measured
     at 390 and 1280, it was pressable with every box blank, so an empty
     submission spent one of the three attempts `BR-CWP-036` allows before the
     form locks for fifteen minutes. The refusal it now carries is
     *"Fill in all three boxes."* -->

### CWP-017 · P3 · Prove it is you — T7 (wide card, no rail)
`Stepper` (✓ · **2** · 3) → `Card` ≈ 75% [kicker **ACCOUNT FOUND** · title *We sent you a
code* · line with the masked number bold · `DialInput`-style *Six-digit code\** (narrow,
≈ 240px, spaced digits) · `ButtonRow` *Verify ✓* **held** · `Button(outline)` *Send it
again* · grey text *Wrong number? Ring the office.*] → full-width `WarningBar` under the
card.

### CWP-018 · P4 · Choose a password — T4 (50/50)
`Stepper` (✓ · ✓ · **3**) → left `Card` [`FormField` New password\* + helper · Type it
again\* · section title **HOW SHOULD WE SEND CODES?** · `RadioList` × 2 · *Create my login
✓* **held**] · right `Panel` **WHAT YOU ARE ABOUT TO GET ACCESS TO** [`KVList` Account /
Service address / Services / **Balance today** · nested `ConsequenceBox` headed **WHEN YOU
FINISH**]. ⚠ The consequence box lives in the **rail** here; the first screen in the flow
allowed to show a balance.

### CWP-019 · P5 · Forgotten password — T7
`Card` ≈ 70% [kicker **RESET** · title *Send me a reset link* · `FormField` Email\* · *Send
the link* **held** · `InfoBar` inside the card (same answer either way)].

---

## The shell, the account set, access — `CWP-020` … `CWP-026`, `CWP-065`

### CWP-020 · P6 · Add another account — T3 (drawn without tabs — a focused task)
`PageHead` kicker **YOUR ACCOUNTS** · title · subtitle → main `Card` [Account number\* ·
Postcode\* · `ConsequenceBox` (3 bullets, *Nothing is combined*) · *Add account ✓* **held**]
· rail [`Panel` **ALREADY ON THIS LOGIN** with a **brand count** right in the header ·
`KVList` address / money × 4].

### CWP-021 · P7 · Accept an invitation — T7
`Card` ≈ 75% [kicker **INVITATION** · title *M. Alvarez has asked you to help with an
account* · `KVList` Account / **You would be able to** / **You would not be able to** /
Access ends · `ButtonRow` *Accept ✓* **held** · *Decline*]. Both permission lists render
from one field.

### CWP-022 · P8 · Portal home — T3 with an account card, then a `KpiRow`
⚠ **AMENDED 2026-09-08 (`CR-085` task (c)) BY THREE PRODUCT OWNER RULINGS ON ONE DAY, AND
THE SIGNED WIREFRAME THAT FOLLOWED THEM.** What this entry described until then is kept
below the amendment because two of the changes REMOVE a piece, and a removal with no
record reads as a lane forgetting.

1. *"once I login as consumer - 03 Home ... we are not displaying account # of Customer
   nmae - ther eis no identifier"* — the page had no identity on it at all.
2. *"can you give big account identifier on home screen - name account #, service area,
   Utility services, assets, phone # and email ID, govt ID - last 4 digits etc - you can
   mask these detials - and also seletor for multiple account if he has"*.
3. The trim, which decides the shape: *"just show IDs not details - Equipment ... W-2209,
   8841-C, F-0118 - this is enough + account status ; - please give me drop down to select
   last 6 months - on this - August bill · BL-2608-000077"*.

`PortalShell` (Home active) → `Card` **YOUR ACCOUNT** + `StatusChip` (coloured from the
account status lookup's own `behavior_class`, never from its name): `KVList` Name on the
account / Services / Plan / Billed / Equipment *(bare references — `8841-C · W-2209`,
never descriptions)* / Mobile *(masked)* / Email *(masked)* / Paperless → `KpiRow` × 4:
**`KpiTile.lead` BALANCE $142.18** *Due 14 Sep · in 12 days* · LAST BILL · LAST PAYMENT ·
WATER THIS MONTH *4,820 gal* → `TwoCol`: main [`Panel` **NEEDS YOUR ATTENTION** (+ *View
all*): rows `StatusChip` danger DUE SOON · sentence with bold refs · `Button(outline)`
*Pay $142.18*; `StatusChip` neutral READING · sentence · *Send a reading* · `Panel`
**YOUR BILL** (+ *All bills →*): month chooser over the last six bills, then ONE bill —
heading *Aug 2026 · $177.60* + `StatusChip`, `KVList` Bill / Period / Due / Usage /
Amount, icons 👁 🖨] · rail [`ChartPanel` **TWELVE MONTHS OF WATER** (+ *Usage →*) ·
`Panel` **PAYING BY INSTALMENTS?** + `Button(outline)` *Ask for a plan*].
`TipBar` slot between the tab strip and the tiles — **absent today** (`BR-CWP-095`). The
attention panel is **absent** when empty.

**The account card sits ABOVE the tiles on a wide screen and BELOW them on a phone**
(`max-md:order-*`, never the min-width form). This screen's own question is still *what do
I owe*; where space is scarce the money wins and the identity is one scroll away.

**Three pieces of the drawing are NOT served and are drawn as nothing rather than guessed**
— the government ID (`customers.Contact.gov_id_last4` exists; no portal read returns it and
whether the portal MAY has never been put to anybody), the service area / route / cycle,
and the account number and service address, which the frame's own account bar already
carries one line above.

**SUPERSEDED, kept for the record (the shape before 2026-09-08):** no account card; the
bill panel was `Panel` **RECENT BILLS** (+ *All bills →*) drawing the kit's one table type
over Bill / Period / Usage / Amount / Status with row icons, three rows and no chooser —
⚠ **the component is deliberately NOT named in this paragraph, because `G105` reads these
entries for the pieces a screen must compose and would ask for a table this screen no
longer draws**; and the rail
carried a third panel, **YOUR SERVICE** `KVList` Address / Plan / Billed / Paperless,
whose four rows are now rows of the account card. Nothing was deleted — Address is the
one fact that went, because the account bar states it.

### CWP-023 · P9 · All my accounts — T5
`PageHead` kicker **YOUR ACCOUNTS** · title *Four accounts on this login* · actions
`Button(outline)` *+ Add an account* · *Pay several →* → `DataTable`: toolbar search · chips
*All \| Owing \| On a plan* · right-aligned **Total owing $872.82** · columns Service
address (bold + grey *Tenant billed* / *Billed to you as owner*) / Services / Next due /
Balance / Status (`StatusChip` danger DUE · success CLEAR · danger OVERDUE 19 DAYS) · icons
👁 💳 · footer *Showing 1–4 of 4 · Rows per page 50*. No rail.

### CWP-024 · P10 · My details — T4
`PageHead` kicker **MY DETAILS** · title · subtitle → `TwoEqual`: `Panel` **CONTACT**
[`FormField.ReadOnly` Name + helper *To change a name we need a document. Raise a request.*
· Email\* · Mobile · Postal address + helper · *Save changes ✓* **held**] · `Panel`
**SIGN-IN** [`KVList` Password / Codes go to / Signed in on · rule · `ButtonRow` *Change
password* · *Sign out everywhere*] with a `Panel.Warning` beneath it (name and ownership
are not a form here).

### CWP-025 · P11 · How we contact you — `PreferenceGrid` then T4
⚠ **THE GRID IS THE DRAWING AND NOT THE STORE — `DEF-CWP-3860`, `OQ-CWP-1660` (OPEN),
STAMPED 2026-09-05.** This layout draws a cell per event per channel — six rows × four
columns, **forty-eight cells**. This product holds **three facts**: `accounts.paperless`
(adds email), `accounts.sms_reminders` (adds text) and
`notifications.CHANNEL_FLOOR_BY_SOURCE` (print, on every kind, always). `US-CWP-028` §5
pointed the per-event cell at the *notification rule catalogue*, which is
`notification_rules` — **one row per event per TENANT by unique constraint**, so a
customer saving there would change what every other customer of that utility receives.
**What shipped draws the rows and puts ONE switch per movable channel above them**, with
a line saying the choice covers everything we send. ⚠ **THIS STAMP RECORDS THE GAP AND
DOES NOT CLOSE IT:** narrowing this drawing to one row of switches is `OQ-CWP-1660`
option (c) and is the Product Owner's to pick, not a lane's.

⚠ **AND IT IS SIX FLOOR CLASSES, NOT FOUR** (PO 2026-08-30, verbatim: *"don't switch of
print for any document it is awayls on"*) — `invoice`, `payment`, `notice`, `plan`,
`account` and `move`. The screen reads `CHANNEL_FLOOR_BY_SOURCE` rather than a list of
its own, so the next widening reaches the grid without anybody editing a screen.

`PageHead` → full-width `PreferenceGrid`: WHAT WE SEND (bold + grey sub) / POST / EMAIL /
TEXT / IN THE PORTAL — POST = `StatusChip` neutral **ALWAYS** on the six floor classes,
`—` elsewhere; other cells *On* / *Off* → `TwoEqual`: `Panel` **PAPER** [`KVList` Paperless
billing / You agreed · grey paragraph · `Button(outline)` *Go back to paper*] · `Panel`
**LANGUAGE** [`FormField.Select` + helper *N languages available.*, where N is the number of options actually drawn]. ⚠ **AMENDED 2026-09-07 — THIS READ *Eleven languages available.* (`DEF-CWP-4442`, `BR-CWP-106`).** The Product Owner ruled the portal offers TWO: *"currently in drop down show only 2 elnglish and spanish"*. The helper is the catalogue's own `{{count}}` string and was never written out, so no copy changed; what changed is that the count is the RENDERED list rather than the server's offer, because a customer already reading German is shown three and a caption saying *2* under three options contradicts the control beneath it.

### CWP-026 · P12 · People with access — T5
`PageHead` + action *+ Invite someone* **held** → `DataTable` Person (bold + grey email /
*You*) / Accounts / Can / Access ends / Status (`StatusChip` success HOLDER · success ACTIVE
· warning INVITED) · icons ✎ − · footer → `InfoBar` (*recorded under **their** name*).

### CWP-065 · P51 · Your account — T3
`PortalShell` (My details active) → `PageHead` kicker **MY DETAILS** · title *Your account*
· subtitle → main [`Panel` **THE DEPOSIT WE HOLD** `KVList` Held / Taken / Interest so far +
grey paragraph · `Panel` **YOUR SERVICES** `MiniTable` Service / On since / Billed on ·
`Panel` **HOW YOU ARE BILLED** `KVList` Plan / On this plan since / Before that] · rail
[`Panel` **TAX** `StatusChip` neutral EXEMPT · `KVList` From / Runs out · grey paragraph ·
`Button(outline)` *Send a new certificate* · `Panel` **THIS ACCOUNT** `KVList` Opened /
Transferred from]. The deposit panel is **absent** when none is held.

---

## Bills and documents — `CWP-027` … `CWP-032`, `CWP-068`

### CWP-027 · P13 · Bills — T5
`PortalShell` (Bills) → `PageHead` kicker **BILLS** · title *Your bills* · actions *↓
Download all* · *Pay $142.18* → `DataTable`: toolbar search · *All \| Unpaid \| This year*
· *+ Filter ▾* … *▦ Columns* · columns Bill ⇅ (bold) / Period ⇅ / Issued / Due / Usage
(with unit) / Amount / **Owing** / Status (`StatusChip` danger DUE IN 12 DAYS · neutral
PAID · neutral CORRECTED) · icons 👁 🖨 · footer with the full pager. **Corrected row**:
greyed, with a brand small caption *Replaced by BL-2606-0147* under the number.

### CWP-028 · P14 · One bill, line by line — T6 + `TwoCol`
`PageHead`(detail) back **← BILLS** · title = bill number · grey subtitle *1–31 August ·
issued 30 August · due 14 September* · actions *↓ PDF* · *Query this bill* · *Pay $142.18*
→ main `Panel` **WHAT YOU WERE CHARGED**: `MiniTable` LINE / QUANTITY / RATE / AMOUNT with
**group rows** in kicker type (WATER · SEWER · TRASH · TAXES AND FEES) spanning; footer rows
*Charges before tax* · *Tax* (grey label, bold right) · `TotalRow` *Total for August* ·
rail [`Panel` **YOUR ACCOUNT** `KVList` + `TotalRow` Owing · `Panel` **READINGS THIS BILL**
`MiniTable` Meter / Taken / Reading + grey note · `Panel` **SOMETHING WRONG?** +
`Button(outline)` *Query this bill*]. The `AttachedAnswerCard` slot (`CWP-061`) sits
**directly under the charges panel**.

### CWP-029 · P15 · The bill as it was printed — T6
back **← BL-2608-0141** · title *The bill we sent you* · subtitle · actions *↓ Download* ·
*🖨 Print* → `DocumentPreview` (the issued PDF, centred, letter aspect). No rail.

### CWP-030 · P16 · Why is this bill different? — T6 + `TwoEqual`
back **← BL-2608-0141** · title *Why August cost $3.74 more* → `Panel` **AGAINST LAST
MONTH** [`KVList` with **signed money** — positives in brand red · `TotalRow` *Difference
+$3.74*] · `Panel` **AGAINST LAST AUGUST** [tiny two-bar chart with mono labels · `KVList`
Water used *4,090 → 4,820 gal* / Rate per gallon *unchanged* · grey paragraph · `ButtonRow`
*Send a reading* · *Query this bill*].

### CWP-031 · P17 · Documents and letters — T5
`PageHead` kicker **DOCUMENTS** · title · action *↓ Download a year* → `DataTable` toolbar
search · *All \| Bills \| Receipts \| Letters* … *▦ Columns* · Document / Kind / Sent /
How · icons 👁 🖨 · footer *Showing 1–5 of 41 · Page 1 of 9*.

### CWP-032 · P18 · Your final bill — T4
`PageHead` kicker **MOVING OUT** · title · subtitle · actions *↓ PDF* · *Pay $63.40* →
`Panel` **SETTLING UP** [`KVList` Service to 17 September / Deposit held / Interest on your
deposit · `TotalRow` **We owe you $89.80** · nested `ConsequenceBox` headed **WHAT HAPPENS
NEXT**] · `Panel` **CLOSING READING** [`KVList` × 3 · grey paragraph · `Button(outline)`
*Query this reading*].

### CWP-068 · P54 · Everything we sent you, and what came back — T3 with a `DataTable` main
`PageHead` kicker **DOCUMENTS** · title · subtitle *And the ones that did not arrive.* ·
action *↓ Download a year* → main `DataTable` toolbar search · *All \| Bills \| Receipts \|
Notices \| Did not arrive* (wraps) · What (bold + grey reason on failures) / Kind / Sent /
How / What happened (`StatusChip` success DELIVERED · danger CAME BACK · neutral NOT SENT ·
success-outline DUE TO GO) · icon 👁 · footer · rail [`Panel.Warning` *Two letters came back
from this address* + `Button(outline)` *Check my address* · `Panel` **WHY SOMETHING WAS NOT
SENT**].

---

## Usage and readings — `CWP-033` … `CWP-037`, `CWP-062`

### CWP-033 · P19 · Usage — T3 variant: `ServicePicker`, `KpiRow`, then full-width panels
**AMENDED 2026-09-08 · `CR-085` s50 — ONE SERVICE AT A TIME.** Product Owner, verbatim:
*"on this screen usage you will ahve to give drop down for utility services"*, and the
signed-off wireframe's own reason: *"kWh, thousand gallons and therms cannot share an axis,
and a chart that mixes them is unreadable"* (CLAUDE.md hard rule 3). ⚠ **THE ROW OF PER-SERVICE
CARDS LEAVES THIS ENTRY** (it is written without its component name on purpose: G105 reads
every kit name this file puts in backticks, so naming the piece here would go on requiring
it). It drew one card per service under the charts, so a WATER total stood on a
page whose picker could perfectly well say ELECTRIC — the wireframe's own named *failure to
avoid*, with a grid round it. Its two served year totals are the comparison block now.

`PortalShell` (Usage) → `PageHead` kicker **USAGE** · title *What you have used* · controls:
segmented `Button(outline)` pair *12 months* (selected) \| *24 months* + *↓ CSV* → [`TipBar`
slot — `CWP-062`] → `ServicePicker` (a dropdown on a phone, tabs on a desktop, built from the
account's OWN services and absent entirely where there is one) → `KpiRow` (ELECTRIC · THIS
PERIOD *800 kWh* · LOWEST · FEB *412 kWh* · MONTHLY AVERAGE *664 kWh* · HIGHEST · JUL 2025
*948 kWh*, plus NEXT READING DUE when a window is open) → `ChartPanel` **ELECTRIC · kWh PER
MONTH** with a brand right note *Sewer is billed on this figure*, 12 bars, mono axis, legend
→ `Card` **AGAINST LAST YEAR** (`KVList` This year / Last year, or one sentence where there
is no prior year) → the answer a clerk pinned to this screen, at the FOOT and absent when
nothing is pinned. A service the customer has that produces no reading is a TAB like any
other and draws *Billed on · Water used* / *Not separately metered* instead.
**No chart for an unmeasured service.**

⚠ **AMENDED 2026-09-11 · `CR-085` step 2 — THE HEAD ABOVE WAS DRAWN AND NOT BUILT, WHICH IS
WHY IT IS WORTH SAYING TWICE.** Until today this screen composed no page head at all: the
kicker and the title did not exist, an eleven-pixel section title inside the first card stood
where the `<h1>` belongs, and the two controls sat beside it in the card body rather than in
the head's action row. On a failed read the whole lot went away with the data
(`DEF-CWP-4846`). It is the shared page head on **every** branch now.

⚠ **AND THE KPI ROW CHOOSES ITS OWN COLUMNS (`DEF-CWP-4847`).** `NEXT READING DUE` makes five
tiles the ordinary case, and five into four columns leaves one alone on a second row with
three quarters of it empty. The rule is *no row ends in one orphan*: four columns unless the
remainder would be one, three otherwise.

⚠ **THE FOOT SLOT IS `CWP-060`'s SECOND PLACEMENT (`DEF-CWP-3945`).** A clerk ticks *also
show this on the Usage screen* on Settings → Help; `ALSO_SHOW_SCREENS` has named `usage`
since the feature shipped and nothing on this screen read it, so the tick published into
nothing for six days. It is at the FOOT because this screen's own rule is *"weight follows
importance — the chart outranks the summary tiles above it"*.

### CWP-034 · P20 · Every reading — T6 + T5
**AMENDED 2026-09-08 · `CR-085` s51.** The drawing scopes this screen to ONE meter —
`⚡ Electric · meter 8841-C ▾` on a phone, two tabs on a desktop — which reverses the
2026-09-05 decision to answer `DEF-CWP-3990` with a meter COLUMN. The column is not deleted:
it returns whenever the chosen service answers from more than one meter, which is the one
case a tab cannot state. The phone frame is a stack of cards, not a table that scrolls
sideways.

back **← USAGE** · title *Readings on your meters* · action *Send a reading* **held**
→ `ServicePicker` (`⚡ Electric · 8841-C` \| `💧 Water · W-2209`) → `DataTable` Taken ⇅ /
Reading / Used since (unit) / How it was taken (text, or `StatusChip` warning ESTIMATED +
*then corrected*) / On which bill · icons 👁 · footer → `InfoBar` (the estimated sentence).

### CWP-035 · P21 · Send your own reading — T3
`PageHead` kicker **READINGS** · title · subtitle (*window open until 6 September*) → main
`Card` [`FormField.Select` *Which meter* (by serial) · `FormField.Date` *Date you read it\**
· **`DialInput`** *The number on the dial\** — **flagged** state: brand border + brand
helper *That is 5,900 gallons in two days — about nineteen times your usual…* ·
`PhotoPicker` · `ButtonRow` *Send it ✓* **held** · *Cancel*] · rail [`Panel` **LAST
READING** `KVList` Taken / Expected now · `Panel` **WHAT HAPPENS TO IT** = `ChecklistTimeline`
× 3].

### CWP-036 · P22 · Your usage looks high — T4 (**blocked**)
`PageHead` kicker **ALERT** · title · subtitle → `ChartPanel` **DAILY USE, LAST FOURTEEN
DAYS** + caption · `Panel` **WHAT IT USUALLY IS** [4 rows *bold lead + grey rest* with rules
· `ButtonRow` *Send a reading* · *Ask for a visit*] → full-width `WarningBar`.

### CWP-037 · P23 · Meters and equipment — T6 + `DataTable`
**AMENDED 2026-09-08 · `CR-085` s52 — BARE REFERENCE NUMBERS, NOT A DETAIL RECORD.** Product
Owner, verbatim: *"just show IDs not details - Equipment ... W-2209, 8841-C, F-0118 - this is
enough + account status"*, and the signed-off wireframe's table is `Equipment · Reference ·
Installed · Whose · Monthly` with no location cell and no last-read cell in it. ⚠ **`Where`
and `Last read` LEAVE THIS ENTRY.** Where a meter physically sits is the utility's own
record; a reading belongs on `CWP-034` one door away.

⚠ **THIS ENTRY SAID `Whose` AND `Monthly` WERE *"drawn but NOT built"* UNTIL 2026-09-11 AND
BOTH HAVE BEEN BUILT SINCE `CPB-10`** — `GET /portal/accounts/{id}/equipment` serves
`maintained_by`, `charge_basis`, `monthly_charge` and `monthly_charge_bill`, and the screen
keeps the two absences apart (*No charge* is a FACT, *Not on your last bill* is a GAP).

⚠ **AND THE EQUIPMENT CELL CARRIES ITS SIZE, AMENDED 2026-09-11 (`DEF-CWP-4848`).** The
signed-off wireframe writes it into that cell on both widths — *Water meter · 5/8 inch*,
*Fire line · 2 inch sprinkler supply* — and its own note says why: *"Size is stated in
inches, as the customer's plumber would."* It matters most on **fire**, where the size class
PICKS THE PRICE and the count multiplies it, so the one row with a monthly charge on it was
the one row whose charge could not be checked. The wire carries the ratified NAME
(`size_class_name`); the bare CODE never reaches the glass (B14 rule 32). The phone frame is
a stack of cards.

back **← USAGE** · title → `DataTable` Equipment (name · size) / Reference / Installed /
Whose / Monthly / Status (`StatusChip` success IN SERVICE · warning TEST DUE NOV), no
footer → `InfoBar` with an embedded `Button(outline)` *Report a problem*. **The empty state
carries that same door** (`DEF-CWP-4849`): the drawing's `NOTHING RECORDED` is a sentence
*with a way to ask*, and the callout used to live inside the non-empty branch only.

### CWP-062 · P48 · A tip where it lands — `CWP-033` with the `TipBar` filled
`TipBar` under the page head: brand left rule · kicker **TIP** in brand · *Watering before
10am loses less to evaporation.* · `×`. **When no tip is live, the bar is absent.**

---

## Paying — `CWP-038` … `CWP-041`, `CWP-045`, `CWP-050`

### CWP-038 · P24 · Pay now — T2 (no guest nav; URL *step 2 of 3*)
`Stepper` 3 (✓ How much · **2** How you are paying · 3 Confirm) → main `Card` [section
title **AMOUNT** · `RadioList` × 3 with bold money inline · section title **HOW YOU ARE
PAYING** · `RadioList` × 3, first row with `StatusChip` success VERIFIED at the right ·
`ConsequenceBox` · `ButtonRow` *Pay $142.18 ✓* (**held** until rails) · *Back*] · rail
[`Panel` **WHERE IT WILL GO** `MiniTable` Bill / Owing / Paying + footer *Payments settle
the oldest bill first.* · `Panel.Warning`].

### CWP-039 · P25 · Your payment methods — T5
`PageHead` kicker **PAYMENTS** · title *Cards and bank accounts* · action *+ Add a method*
**held** → `DataTable` Method (bold *Chase ••••4021* + grey *Bank account* / *Card ·
expires 11/27*) / Added / Used for / Status (`StatusChip` success VERIFIED · success
ACTIVE) · icons ✎ − · no footer → `InfoBar` (never hold your full card number).

### CWP-040 · P26 · Autopay — T4
`PageHead` kicker **PAYMENTS** · title → left `Card` [`FormField.Select` *Take it from* ·
`FormField.Select` *How much* + helper · **`FormField.ReadOnly`** *When* = *On the due date*
+ helper *Always the due date. It cannot be changed.* · `ConsequenceBox` · *Turn autopay
on*] · right [`Panel` **NEXT FEW** `MiniTable` Date / Expected / Status (`StatusChip` warning
SCHEDULED · neutral NOT BILLED YET) · `Panel.Warning`].
⚠ **B14 over the drawing:** the blueprint drew *Turn autopay on* live; it is **held**
(`CR-068` `R3`, `US-CWP-047`).

### CWP-041 · P27 · Payments and receipts — T5
`PageHead` kicker **PAYMENTS** · title *What you have paid* · action *↓ CSV* → `DataTable`
toolbar search · *All \| This year* … *▦ Columns* · Date ⇅ / How / Reference / Applied to /
Amount / Status (`StatusChip` success CLEARED · danger BOUNCED · neutral REVERSED) · icons
👁 🖨 (🖨 absent on the bounce and the reversal) · footer. **Bounced row** = danger row
(every cell brand red), *Applied to* reads *Returned by the bank*, amount *−$129.02*.

### CWP-045 · P31 · Credits and refunds — T4
`PageHead` kicker **PAYMENTS** · title *Money coming back to you* → `Panel` **A REFUND ON
ITS WAY** = `ChecklistTimeline` × 4 (Raised · Approved · **Sent** current · Cleared) · `Panel`
**CREDITS ON THE ACCOUNT** [`MiniTable` What / When / Amount / Used × 2 · footer sentence *A
credit comes off your next bill. A refund is money sent back.*].

### CWP-050 · P36 · Fees to pay — T6 + `TwoCol`
`PageHead`(detail) kicker = **SR-26-0061** · title *What starting service will cost* · action
*Pay $335.00* (**held** until rails) → main `Panel`-less `MiniTable` Fee / When / Amount × 4
(the waived row: *Waived* + amount **struck through, grey**) · `TotalRow`s *To pay now
$335.00* · *On your first bill $150.00* · rail [`Panel.Info` · `Panel.Warning`].

---

## Plans, level pay, arrears — `CWP-042` … `CWP-044`, `CWP-056`, `CWP-057`, `CWP-063`, `CWP-064`, `CWP-066`

### CWP-042 · P28 · Ask for a payment plan — T2
`Stepper` 3 (✓ What you owe · **2** Choose the instalments · 3 Agree) → main `Card`
[`FormField.Select` *Spread it over* + helper · `FormField.Date` *First payment on* ·
`FormField` money *Something up front?* + helper · `ConsequenceBox` (**five** payments…) ·
`ButtonRow` *Ask for this plan ✓* **held** · *Back*] · rail [`Panel` **THE INSTALMENTS**
`MiniTable` Due / Amount × 6 · `TotalRow` *Total $132.20* · grey note *The last instalment
carries the rounding.*].

### CWP-043 · P29 · Your payment plan — T3
`PageHead` kicker **PAYMENTS** · title *Your plan is on track* · subtitle · actions *↓
Agreement* · *Pay the next one* → main `MiniTable` Instalment / Due / Amount / Status
(`StatusChip` success PAID ON TIME · warning PAID LATE · danger DUE IN 9 DAYS · neutral TO
COME) · rail [`Panel` **WHILE THE PLAN HOLDS** 3 rows *bold lead + grey* · `Panel.Warning`
missing two].

### CWP-044 · P30 · Level pay — T4
`PageHead` kicker **PAYMENTS** · title · subtitle → left `Card` [`KVList` Your last twelve
months / Monthly average / Rounded to · `TotalRow` *You would pay each month $125.00* ·
`ConsequenceBox` · *Join level pay ✓* **held**] · right `ChartPanel` **THIS MONTH, EITHER
WAY** (bars + the level line, caption).

### CWP-056 · P42 · Help paying — `CardGrid3` then `InfoBar`
`PageHead` kicker **HELP** · title *Struggling to pay?* · subtitle → `CardGrid3`: three
`ErrandCard`-shaped cards with a paragraph body (bold clause) and a button each — *Ask for
a plan* **held** · `Button(outline)` *Send a certificate* · *Look at level pay* → `InfoBar`
(moratorium, bold dates, **no button**).

### CWP-057 · P43 · What happens if this is not paid — T3
`PageHead` kicker **OVERDUE** · title *$412.60 is overdue by 19 days* · actions *Ask for a
plan* · *Pay $412.60* → main `Panel` **WHERE THINGS STAND** = `ChecklistTimeline` × 6 (Due ·
Reminder sent · Late fee added · **First notice sent** current · Final notice · Supply
disconnected) · rail [`Panel` **WHAT IT WOULD COST** `KVList` Owed now / Reconnection fee /
New deposit · `TotalRow` *If it goes that far $657.60* · `Panel.Warning` *A plan stops this
today*]. ⚠ An unmapped tier renders as an **absence** in the timeline (`BR-CWP-092`).

### CWP-063 · P49 · A plan the utility has offered you — T3
`PortalShell` (Payments) → `PageHead` kicker **PAYMENTS** · title *Pine Hill has offered you
a plan* · subtitle · action *↓ Agreement* → main [`Panel` **THE PLAN** `KVList` What it
covers / Paid up front / Spread over / First payment + grey footer · `ConsequenceBox` headed
**WHAT ACCEPTING THIS DOES** (4 bullets) · `ButtonRow` **three, in this order:** *Accept
this plan ✓* **held** · `Button(outline)` *Ask for different terms* · *Decline*] · rail
[`Panel` **THE INSTALMENTS** `MiniTable` × 6 + `TotalRow` · `Panel.Info` ⓘ *Nothing happens
until you accept…*].

### CWP-064 · P50 · What is protecting your supply — T3, three `ProtectionCard`s
`PageHead` kicker **HELP** · title · subtitle → main: two stacked `ProtectionCard`s [`Panel`
header = the protection's name · row `StatusChip` success HOLDING NOW + grey *Since…* ·
`KVList` **Ends on** (a date — or the sentence *no date — see below*) · body sentence with
a bold clause · `Button(outline)`] · rail [`ProtectionCard` **WINTER MORATORIUM**:
`StatusChip` info STARTS 1 DECEMBER · `KVList` From / Until · sentence · **no button** ·
`Panel.Warning` *A hold stops a disconnection. It does not stop the debt.*].

### CWP-066 · P52 · Where your level pay stands — T3 with a `KpiRow`
`PageHead` kicker **PAYMENTS** · title · subtitle · action *↓ CSV* → `KpiRow` × 3
(**`KpiTile.lead` YOU PAY EACH MONTH $125.00** · YOU ARE AHEAD BY $47.30 · SETTLES UP IN
June) → `TwoCol`: main [`ChartPanel` **WHAT YOU PAID AGAINST WHAT YOU USED** · `Panel`
**WHEN THE LEVEL CHANGED** `MiniTable` When / What happened / New level / Balance after] ·
rail [`ConsequenceBox` headed **WHAT HAPPENS IN JUNE** (4 bullets) · `Panel` **IF YOU LEFT
TODAY** `KVList` + grey sentence + `Button(outline)` *Leave level pay*].

---

## Requests, disputes, messages — `CWP-046` … `CWP-049`, `CWP-051` … `CWP-055`, `CWP-067`

### CWP-046 · P32 · What do you need? — T1 shape inside `PortalShell`
`PageHead` kicker **REQUESTS** · title → `CardGrid3` × 2 `ErrandCard`s (*Start →*) →
`Panel` **OPEN REQUESTS** (+ *All requests →*) `MiniTable` Reference (bold) / What / Raised
/ Status (`StatusChip` warning WE NEED TWO DOCUMENTS) + icon 👁.

### CWP-047 · P33 · Start service — about you — T2 under `GuestFrame` (URL *not signed in · step 2 of 4*)
`Stepper` 4 (✓ · **2** · 3 · 4) → main `Card` [kicker **ABOUT YOU** · `TwoUp` First name\*
\| Last name\* · `FormField.Select` *Are you a person or a business?\** · `TwoUp` Email\* \|
Mobile\* · `FormField.Date` Date of birth\* + helper · `FormField.Date` *When do you want
service to start?\** + helper · `ButtonRow` *Continue →* **held** · `Button(outline)` *Save
and finish later*] · rail [`Panel` **THE ADDRESS** `KVList` Service address / Unit /
Services here · `Panel.Info` nothing is promised yet].

### CWP-048 · P34 · Moving out or moving on — T2
`Stepper` 3 (✓ When · ✓ Where to send the last bill · **3** Check and send) → main `Card`
[`KVList` Leaving / Last day of service / Final bill goes to / Deposit held ·
`ConsequenceBox` (third bullet *The account closes. You cannot undo this.*) · `ButtonRow`
**`Button(danger)` *Send this request ✓*** · *Back*] · rail [`Panel` **NOT THE SAME THING** 2
rows bold lead · `Panel.Info` a transfer keeps your history]. **Rule 6: the one place the
danger tier is the commit.**

### CWP-049 · P35 · Documents we need from you — T6
`PageHead`(detail) kicker = **SR-26-0056** · title *Two things still to send* · subtitle →
full-width `DataTable`-typed table Document (bold) / Why / Status (`StatusChip` neutral
RECEIVED 2 SEP · warning NEEDED) · icon 👁 on received, ↑ on needed → **as drawn:** an *Add
a file* block with a dashed drop zone. **B14 and the story over the drawing: the drop zone
is NOT built** — a sentence saying documents come to the office replaces it
(`US-CWP-064`). Then a `WarningBar`.

### CWP-051 · P37 · Track your request — T6 + `TwoCol`
`PageHead`(detail) kicker = **SR-26-0056** · title *Move out · 1408 Elm St · A* · subtitle ·
actions `Button(outline)` *Add a note* · *Withdraw* → main `Panel` **PROGRESS** =
`ChecklistTimeline` × 6 (2 done · **current** · 3 future; bold step · date, grey
actor/detail) · rail [`Panel` **DETAILS** `KVList` Reference / Last day of service / Waiting
on / Open for · plain `Card` *Changed your mind? Withdrawing stops the request…*].

### CWP-052 · P38 · Stop or restart service — T4
`PageHead` kicker **REQUESTS** · title → left `Card` [`FormField.Date` Stop from\* · Start
again\* · `FormField.Select` Why · `ConsequenceBox` (*The account stays open* · *Standing
charges keep running — about $18.50 a month*) · `ButtonRow` **`Button(danger)` *Request
this ✓*** · *Cancel*] · right `Panel` **WOULD MOVING OUT BE CHEAPER?** [two sentences with
bold money · rule · the computed verdict line]. Second danger-tier commit.

### CWP-053 · P39 · Messages — T5
`PageHead` kicker **MESSAGES** · title *From Pine Hill* · action `Button(outline)` *Mark all
read* → `DataTable` (no toolbar) Message (**unread rows bold**) / About / When · icon 👁 ·
footer *Showing 1–5 of 22 · Page 1 of 5*.

### CWP-054 · P40 · Ask a question — T3
main `Card` [kicker **HELP** · title *Ask us something* · `FormField.Select` *What is it
about?\** · `FormField.Select` *Which bill* · textarea *Tell us\** · `PhotoPicker` · *Send
✓* **held**] · rail [`Panel` **MIGHT ANSWER IT NOW** 3 brand-link rows *Question →* with
rules — **absent when nothing is published** · `Panel` **OR RING** two grey lines].

### CWP-055 · P41 · Dispute a bill or a reading — T2 (2-cell stepper)
`Stepper` 2 (✓ What is wrong · **2** Check and send) → main `Card` [`KVList` Bill / What you
are questioning / Your reason / Your own reading today · `ConsequenceBox` · `ButtonRow`
*Send the query ✓* **held** · *Back*] · rail [`Panel` **WHILE A BILL IS QUERIED** two
paragraphs with a rule · `Panel.Info`].

### CWP-067 · P53 · A visit is booked — T3 (**blocked**)
`PortalShell` (Requests) → `PageHead` kicker **REQUESTS** · title · subtitle → main [`Panel`
**WHAT IS HAPPENING** `KVList` Job / Where / Which meter / When + a bold-lead sentence
*Nobody needs to be in.* · `Panel` **PROGRESS** `ChecklistTimeline` × 4] · rail [`Panel`
**NOT CONVENIENT?** sentence + two **stacked** `Button(outline)` · `Panel.Warning`].

---

## Help on the portal, notices — `CWP-058` … `CWP-061`

### CWP-058 · P44 · Outages and planned work — T5 (**blocked**, `OQ-249`)
`PageHead` kicker **NOTICES** · title *Work near you* → full-width table What (bold + grey
sub) / Where / When / Status (`StatusChip` danger PLANNED · neutral SCHEDULED) →
`WarningBar`. Absent when there is no work.

### CWP-059 · P45 · Help and answers — signed in — T3
`PortalShell` (no tab active — Help is a header link) → `PageHead` kicker **HELP** · title
*Answers* · subtitle → main `Card` [toolbar search · chips *All \| Billing \| Paying \|
Readings \| Water \| Moving* (wraps) · list rows *question · TOPIC chip · →* · footer row
*Six answers* left · *Read in English ▾* right] · rail [`Panel` **STILL STUCK?** sentence ·
`ButtonRow` *Ask a question* · *Call us* · rule · *Or come in — **Main office**, open until
5:00pm.* · brand link *Where you can walk in →* · `Panel.Info` ⓘ].

### CWP-060 · P46 · One answer — T6 + `TwoCol`
`PageHead`(detail) back **← HELP AND ANSWERS** · kicker = the topic **BILLING** · title =
the question · grey *Updated 2 September.* → main [plain `Card` body paragraph + `ButtonRow`
of **in-text actions** *See my bill* · *Compare in Usage* · a feedback `Card` *Did this
help?* `Button(outline, sm)` *Yes* · *No* · `Panel` **RELATED** 2 rows *question · →*] · rail
[`Panel` **STILL STUCK?** *Three ways…* + **three full-width stacked** `Button(outline)` ·
`Panel` **ALSO WRITTEN IN** · `Panel.Info` ⓘ].

### CWP-061 · P47 · An answer where the question is asked — `CWP-028` + one block
The bill screen with an `AttachedAnswerCard` **directly under the charges panel**. On this
variant the rail reads `Panel` **THIS BILL** (`KVList` Due / Used / Last month) +
`Panel.Info` ⓘ *the answer is here because somebody put it here*.

---

## Back office — `CWP-069` … `CWP-075` (**staff app**, T8)

### CWP-069 · B1 · Portal settings · Overview — T8 + `TwoCol`
`PageHead` kicker **SETTINGS · CONFIGURE · CUSTOMER PORTAL** · title *Overview* · subtitle ·
actions `Button(outline)` *↗ Open the portal* · *Save* (disabled until dirty) → main
[`Panel` **YOUR PORTAL ADDRESS**: a `font-mono` address in a bordered box with inline
`Button(outline, sm)` *Copy* · *↗ Open* · grey sentence · `ButtonRow` *↓ QR code for your
bills* · *Add it to the bill template* · `Panel` **WHAT CUSTOMERS CAN DO** 5 rows *bold name
+ grey sub · On/Off switch right*] · rail [`Panel` **THE PORTAL IS** big *Live* + grey
sentence · `Panel` **WHO IS USING IT** `KVList` × 4 + grey note (*Readings are off, so
nothing is counted*)].

### CWP-070 · B2 · Portal settings · Branding — T8 + `TwoCol`
title *Branding* · actions *Reset to defaults* · *Save* → main [`Panel` **SHARED WITH YOUR
BILLS AND LETTERS** (+ brand link *Edit in Company*): `TwoUp` `FormField.ReadOnly` Logo \|
Trading name · `TwoUp` Brand colour \| Accent colour · grey paragraph · `Panel` **PORTAL
ONLY**: textarea *The sentence under your name* · multi-select *Services shown on the front
page* + helper · `TwoUp` textarea *Office hours shown* \| *Emergency number*] · rail
[`Panel` **WHAT YOUR CUSTOMERS WILL SEE** = a **live miniature of `CWP-001`** in a bordered
box + grey caption *Updates as you type.*].

### CWP-071 · B3 · Help and answers — T8 + T5
title *Help and answers* · subtitle · actions *↗ See it on the portal* · *+ New answer*
**held** → `DataTable`: toolbar search · *All \| Published \| Draft \| Needs translating* ·
grey right *Drag to reorder* · leading **drag handle** column ⋮⋮ · Question (bold, wraps) /
Topic chip / Status (`StatusChip` success PUBLISHED · warning DRAFT · neutral NOT SHOWN) /
Languages / Read this month (right; `—` when none) · icon ✎ · footer *Showing 1–8 of 8* ·
*The order here is the order on the portal* → `InfoBar`.

### CWP-072 · B4 · Edit an answer — T8 + T6 + `TwoCol`
back **← HELP AND ANSWERS** · title = the question · grey *Published · last changed 2
September by Sarah Miller* · actions *Preview* · *History* · *Publish* **held** → main
[`Card` form: `FormField` Question\* · `TwoUp` `Select` Topic \| `Select` Also show on +
helper · textarea Answer\* + helper · `Panel` **LANGUAGES** (+ brand link *Copy English into
all*) `MiniTable` Language (bold) / Status (`StatusChip` success PUBLISHED · warning NEEDS
TRANSLATING) / Last changed · icon ✎] · rail [`Panel` **WHERE IT APPEARS** `KVList` × 4 ·
`Panel.Warning` publishing is immediate].

### CWP-073 · B5 · Tips — T8 + T5, then `TwoEqual`
title *Tips* · subtitle · action *+ New tip* **⚠ NO LONGER HELD — AMENDED 2026-09-05,
`DEF-CWP-3820`** → `DataTable`: toolbar search · *All \|
Showing now \| Seasonal* · grey right *One tip per screen at a time* · ⋮⋮ / Tip (bold,
wraps) / Where it shows (`StatusChip` info, the screen name) / When / Status (`StatusChip`
success ON · neutral OFF) · icons ✎ 👁 − · footer *Showing 1–6 of 6* · *Top of the list wins
where two match* → `TwoEqual` `Panel` **A TIP IS NOT AN ANSWER** · `Panel` **SEASONAL TIPS**.

⚠ **THE WORD *held* WAS A NOTE ABOUT THE DAY THIS WAS DRAWN, AND IT STOPPED BEING TRUE
INSIDE ONE WAVE.** `create_tip`, `update_tip` and `delete_tip` landed with wave D
(`2.138.0`) — routed, audited and tested — and the screen kept a disabled button over
them for a day, which is hard-won law 2 with the label on. **`+ New tip` is LIVE and the
editor behind ✎ is built** (`DEF-CWP-3820`).

**The editor is NOT DRAWN ANYWHERE**, so it is modelled on `CWP-075` next door, which is
what B14 rule 36 asks when a pack has no page for a screen: back link · title · `Button`
**Remove** in the danger tier · *Save*; main [`Panel` **THE TIP** textarea + the
fifteen-word flag · `Panel` **WHERE IT SHOWS** `Select` over the SERVER's six ·
`Panel` **WHEN** switch + two month `Select`s] · rail [`Panel` **STATUS** switch ·
`Panel` **WHAT THE CUSTOMER SEES**].

⚠ **THE ROW'S 👁 IS FOLDED INTO THAT LAST PANEL RATHER THAN SHIPPED AS A THIRD ICON.**
It renders the customer's own `TipBar`, live, as the clerk types — the posture `CWP-070`
already sets for branding — so the preview cannot drift from the real thing by being
maintained twice, and a third icon onto the same destination as ✎ would be noise. Stated
here rather than silently dropped.

### CWP-074 · B6 · Service centres — T8 (breadcrumb) + T5
Breadcrumb *Reference data › Service centres* · title *Service centres* · subtitle · actions
on their own row *↗ See it on the portal* · *+ New centre* **⚠ NO LONGER HELD — AMENDED
2026-09-05, `DEF-CWP-3821`** → `DataTable` Centre
(bold + grey address; **hidden row greyed**) / Open / Takes / You can / Status (`StatusChip`
success ON THE PORTAL · neutral HIDDEN) · icons ✎ 👁 − · footer → `WarningBar` (hidden is a
state) · `InfoBar` (holiday calendar).

### CWP-075 · B7 · Edit a service centre — T8 + T6 + `TwoCol`
back **← SERVICE CENTRES** · title *Main office* · grey *Shown on the portal · last changed
14 August* · actions *Preview* · **`Button(danger)` *Remove*** · *Save* → main [`Panel`
**WHERE IT IS** `FormField` Name\* · Address\* · `TwoUp` Phone \| textarea *Getting there* ·
`Panel` **WHAT A CUSTOMER CAN DO HERE** five checkboxes (brand-outlined when ticked) + grey
sentence] · rail [`Panel` **OPENING HOURS** 7 rows *day bold · `StatusChip` OPEN/CLOSED ·
two time fields* + footer *Public holidays close it automatically.* · `Panel` **TAKES
PAYMENT BY** `ToggleChips` Cash · Cheque · Card · Money order · `Panel` **ON THE PORTAL**
rows *Shown to customers* (switch) · *Position* (number)].

---

## Where the drawings and B14 disagree — the four places, and B14 wins

| Screen | The drawing | B14 / the ruling | Built as |
|---|---|---|---|
| `CWP-040` | *Turn autopay on* drawn live | `R3` — held, disabled, carrying its reason | held |
| `CWP-001` five `Start →` and the sign-in bar; the frame's *Help* · *Visit us* · *Pay a bill* · *Sign in* | drawn live | `R3` — held until the screen lands | ⚠ **LIVE SINCE `2.164.1`, AND THE HOLD OUTLIVED THE RULE BY A WEEK (`DEF-CWP-3925`).** `CWP-002`, `CWP-008`, `CWP-011`, `CWP-013` and `CWP-015` landed in waves B–E and P; the door was never told, so a visitor read *Opens with the next release* over five live screens and pressed three `<span>`s that were not links at all. The drawings were right and R3's clock was the thing nobody was watching |
| `CWP-001` *What things cost* | drawn live | `R3`, and it still applies — §9 allocates no screen and `DEF-CWP-3704` records the endpoint as deliberately not built | held |
| `CWP-001` *Check my area* · *Help & answers* | drawn live **since 2026-09-05** | PO ruling: all six cards are shown, disabled where unavailable. Each carries the reason the SERVER sends — `status_page_not_offered` (`R9`) or `nothing_published_yet` (`BR-CWP-093`) — never `R3`'s release note, because neither is waiting on a screen we have not built | **disabled, with a reason.** `FrontPage.test.tsx` refuses a `CWP-005` row in `PORTAL_SCREENS`, so the day the status page lands the suite goes red and names the card |
| `CWP-049` | a dashed upload drop zone | consumer upload is a signed deferral | a sentence; no file input |
| every `Pay` control before release 5 | drawn as a normal outlined button | `R3` | held |
| `CWP-014` *Call* action | brand-outlined | rule 6 reserves the brand outline for **destructive** commits | plain outline |
| `CWP-073` *+ New tip* | **held** | ⚠ the endpoint has accepted a tip since `2.138.0`, and a disabled control over a working write is hard-won law 2 (`DEF-CWP-3820`, amended 2026-09-05) | live, and the editor behind ✎ is built |
| `CWP-074` *+ New centre* | **held** | ⚠ same, and worse: a tenant with no centres has no visit page at all (`BR-CWP-093`) and the empty state was its only door (`DEF-CWP-3821`) | live |
| `CWP-073` row icon 👁 | a third row icon | one live preview inside the editor beats a second destination onto the same screen — and it is the CUSTOMER's own `TipBar`, so it cannot drift | folded into the editor |
| `CWP-074` *↗ See it on the portal* | a header action | ⚠ **NOT BUILT AND NOT CLAIMED.** Stated so its absence is a plan and not a gap somebody rediscovers | absent |
| `CWP-075` *Preview* | a header action | ⚠ **NOT BUILT.** Same reason as the row above — the public centre page is `CWP-014`, and a link to it is a wave of its own | absent |
