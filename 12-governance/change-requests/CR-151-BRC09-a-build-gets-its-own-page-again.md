# CR-151-BRC09 — A build gets its own page again, and the two rules that killed the last one still hold

**Raised:** 2026-09-28, by the Product Owner, reviewing a redrawn Accounts › New connects list and
being shown three ways to give a clerk the whole build in one place. **They chose the third.**
**Branch:** `claude/brave-dijkstra-xgfsgz` (`BRC09`). Block `CR-150`–`CR-154`, recorded in
`12-governance/14-id-reservations.md` before `CR-150-BRC09` was written; **this is the second number
out of that block.**
**Version:** none yet, deliberately — see §7. `CR-150-BRC09`'s RECORD lane owns `2.390.0` and two
lanes bumping is `DEF-GOV-3756`.
**Classification:** ⚠ **CHANGE, and a reversal of a signed decision.** A clerk can open a build
today — the address resolves and lands them on the premises or the account — so the Product Owner's
own test (*can a user do this task in the product today?*) answers **yes**, and the maintenance
track applies to the screens. But the thing that moves is a **ruling**, not a bug: on 2026-09-04 the
Product Owner said a build must NOT have its own screen, and on 2026-09-28 they say it must. Nothing
was broken. `13-change-process.md` §1 calls that a **reversal of a signed decision → change**.
**Screen-shaped:** yes. **Screen:** the build detail page, at `/{tenant}/connections/{id}`, plus the
`NCT-01` list above it. **Drawings:** `05-prototype/new-connect-detail-2026-09-28/` — **eleven PNGs,
and they are the specification** (B14 rules 42 and 44).
**Owner of this file:** the REVERSAL lane. The page and its tabs are the DETAIL PAGE lane's; the
list is the LIST lane's.

---

## 0 · What arrived, in the requester's words

Three options were put to the Product Owner in plain English, with what each one costs, after they
asked to see everything about a build without hopping between two hosts:

* **(A)** leave it as it is — the build's facts stay spread across the premises and the account;
* **(B)** a summary panel on the New connects list, opening under the row;
* **(C)** a full detail page per build, with tabs.

**They chose (C)**, and settled the shape in the same conversation:

> *"since we have given link for them in overview"* — said when the two header buttons
> *Open premises* and *Open account* were shown, and they took them out.

> *"you need to use 1 or 2 action words - dont use 3 words"*

> *"all these option will anyway will be in filter - so we dont need them outside"* — said of the
> saved-view chips drawn above the New connects list.

And the standing instruction that governs how it is built, repeated the same day:

> *"ensure you use images to build screens and not text/content"*

**THE SHAPE, AS RULED AND AS DRAWN** (`01-overview.png`, and one PNG per tab):

* the product's own **shared `PageHeader`** — back link (*← New connects*), kicker
  (`B-2026-00042 · SR-2026-00311`), 32px title (the premise name), a roll-up line
  (address · unit count · who raised it and when · service badges · state pill), and the actions on
  the right (*More ▾* and one primary);
* **then the tab bar**, then the tab's content — the same frame the account and template detail
  pages already use;
* **seven tabs: Overview · Units · Work · Charges · Documents · Messages · Audit.**

**The seventh is called Audit and not History**, because the account detail page and the template
detail page already call that tab Audit, and one product may not have two words for one thing
(B14 rule 34's reasoning, one vocabulary out).

---

## 1 · Classification — and why this is a change rather than a defect

| Part | What it is | Why |
|---|---|---|
| **A full detail page per build** | **CHANGE — a reversal of a signed decision** | Nothing was wrong with the redirect. It was built to a Product Owner ruling of 2026-09-04, it works, and every bookmark still lands. The Product Owner has used the product and now wants a different shape. `13-change-process.md` §1: *"Reversal of a signed decision → change"* |
| **The header's two *Open* buttons** | **CHANGE (scope removal)** | Drawn, then removed by the Product Owner in the same review |
| **One- or two-word action labels** | **CHANGE (UI/copy)** | *"Still real work: eleven catalogues and a re-verified screen"* |
| **No saved-view chips on the list** | **CHANGE (scope removal)** | The tiles set the filter; the chips would be a second control saying the same thing differently |

⚠ **THE AMBIGUOUS CASE WOULD HAVE BEEN A DEFECT AND THIS IS NOT AMBIGUOUS.** `13-change-process.md`
§1 is deliberately harsh on us — *"filing our misunderstanding as a change quietly converts our
error into the customer's new requirement"*. Here the 2026-09-04 ruling is written down verbatim in
`12-governance/02-decision-log.md`, it was implemented exactly, and the Product Owner is reversing
their own words. Recording that as *"the product did not do what was expected"* would be false.

---

## 2 · What signed statement is being reversed — quoted, with the supersedes chain

**THE STATEMENT BEING REVERSED**, `12-governance/02-decision-log.md`, row dated **2026-09-04**, in
full where it matters:

> **`CR-070` WAVE O IS BUILT AND SHIPS AS `2.141.0` — A BUILD HAS ONE DESTINATION, AND IT IS THE
> PREMISES AND THE ACCOUNT.** `/connections/<uuid>` stops being a place a person navigates to:
> `features/customers/ConnectionDetailPage.tsx` (1,464 lines) and its two test files are DELETED,
> its panels live once in `features/work/buildViews.tsx`, and the premises detail and the account
> detail compose them. **The route is KEPT** and answers a redirect — every bookmark and every
> *Open this connection* link the New Connect wizard has handed out for three weeks still opens, and
> lands in the same place. **Five links repointed** (the *New connects* eye, the wizard's completion,
> the Orders tab's `CONNECTION` cell, the approval queue's cell and its eye), one path helper DELETED
> so the compiler answers, and **`G93` added so the destination cannot come back.**

and the Product Owner's own words that row transcribes, from `CR-070` §W.10 / §W.11:

> *"youa re duplcaiting this - there is nothing called as conenctions; Connection = Account only -
> you cannot have two differnt screen - this is an integration problem"*

scoped the same day:

> *"One screen too many. The objection is the duplicate destination — a person should reach the
> build's progress, its units, its work orders and its charges from the account, not from a parallel
> screen."*

### THE SUPERSEDES CHAIN, STATED RATHER THAN ASSUMED

| # | Date | Statement | Status after this CR |
|---|---|---|---|
| 1 | 2026-09-04 | `CR-070` §W.10 / §W.11 — **a build has one destination; `/connections/<id>` is a doorway, not a screen** | **SUPERSEDED IN PART** — the first clause only |
| 2 | 2026-09-04 | wave-O judgment **(2)** — *"money and its trail are facts about a PAYER … Building a second copy inside a Build tab is the duplicate destination the ruling is about, one level down"* | ⚠ **NOT SUPERSEDED. IT HOLDS, AND IT IS PART OF THIS RULING.** |
| 3 | 2026-09-04 | the panels live **once**, in `features/work/buildViews.tsx`, and hosts **compose** them | ⚠ **NOT SUPERSEDED. IT HOLDS, AND IT IS PART OF THIS RULING** — and B14 rule 43 (2026-09-20) has since ratified it as a product-wide rule |
| 4 | 2026-09-04 | `G93` exists so the destination *"cannot come back"* | **AMENDED, NOT DELETED** — §6 task R2 |
| 5 | 2026-09-04 | the route is KEPT so no bookmark breaks | **UNCHANGED, AND IT IS WHY THE FLIP IS ORDERED THE WAY IT IS** — §6 task R3 |

⚠ **EXACTLY ONE CLAUSE MOVES.** *A build may not have its own screen* becomes *a build has its own
screen.* **The objection underneath it — duplication — does not move at all**, and the Product Owner
restated it themselves in the same review by taking the two *Open* buttons off the header: the
Overview table already links the premises and the account, so a second door to each in the header is
the same fault this whole chain is about, one size smaller.

**No ❄️ FROZEN B4/B5 figure is touched.** No money math, no rounding, no golden test. §2's STOP
condition does not fire.

### THE TWO RULES THAT KILLED THE OLD PAGE, RESTATED AS BUILD LAW

1. **MONEY FACTS LINK; THEY ARE NOT RE-IMPLEMENTED.** The Charges tab shows what **this build**
   created and what it costs, and every bill, payment, adjustment and journal line is reached by a
   **link to the account**. The drawing agrees: Overview's last row reads
   `One-time charges · $1,035.00 · INV-2026-00318 · $535.00 due 28 Oct`, where the invoice number is
   a link and the money beside it is a fact, and *What happens next* points at **Account › Bills**.
   Re-hosting the account's own Bills tab inside a Charges tab is the same breach as re-implementing
   it — that is wave-O judgment (2) in its own words.
2. **NO PANEL IS COPIED.** The page **composes `features/work/buildViews.tsx`** and its
   `buildRecord/` kit — the same panels the premises detail and the account detail compose. B14 rule
   43: *a piece of UI is built as a COMPONENT; standalone code inside a page is not reuse.* A
   1,464-line page is exactly what rule 43 was ratified against.

---

## 3 · Impact

| Surface | What moves |
|---|---|
| **Screens** | ONE new page with seven tabs; the `NCT-01` list loses its saved-view chips; every action label capped at two words |
| **Routes** | `/{tenant}/connections/:connectionId` stops being a doorway and becomes a page. **The address does not change**, so no bookmark and no handed-out link breaks — which is the whole reason wave O kept it |
| **Screen ids** | `NCT-02` was RETIRED by wave O (`07-frontend/src/routing/screenIds.ts`, `10-scripts/gates/g29_allocated_badges.txt`). A page needs a badge again — the DETAIL PAGE lane re-allocates it, and the route test asserts the address **by screen id** |
| **Components** | none copied. `buildViews.tsx` + `buildRecord/*` are composed. New tab content that has no shared panel (Documents, Messages) is built as components under the same kit, not inline (rule 43) |
| **Gates** | `G93` is amended in place, keeping its id — §6 task R2 |
| **Backend** | nothing in this CR. `GET /work/builds/{id}/home` and the `/connections/{id}` API family are unchanged; §W.10 is explicit that the table survives as plumbing |
| **Locales** | eleven catalogues, for the tab words and the action labels — the TEXT lane's file, not this one's |
| **Open questions** | **in both directions:** none is closed by this CR, and none is opened. `OQ-CUS-12770` (which quantities were 1, 2 and 15) is `CR-150-BRC09`'s and still blocks any Qty column, including one on this page's Charges tab |
| **Demo fixture** | unchanged — the page reads what the premises and account pages already read |
| **Decision log** | the reversal is appended, with this chain — `12-governance/02-decision-log.md`, 2026-09-28 |
| **Rollback** | §8 |

---

## 4 · What is already built and is now wrong

### Code shipped on the old rule

| File | What it is | What happens to it |
|---|---|---|
| `07-frontend/src/features/work/BuildRedirect.tsx` | the doorway wave O put at the address | **DELETED when the page lands**, and not before — §6 task R3 |
| `07-frontend/src/features/work/BuildRedirect.dom.test.tsx` | proves a bookmarked `/connections/<id>` lands somewhere real | deleted with it; its assertion is REPLACED by one that the address renders the page **by screen id** |
| `07-frontend/src/App.tsx:1111–1112` | mounts `BuildRedirect`, `// no screen id: NCT-02 is retired` | the element and the comment both move |
| `10-scripts/gates/g93_one_build_destination.py` | *"nothing navigates to `/connections/<id>`"* | **amended, id kept** — §6 task R2 |
| `07-frontend/src/routing/screenIds.ts:1244` | the note explaining that this address has no screen id | rewritten when the badge returns |

### The five links wave O repointed, so the DETAIL PAGE lane can find them

Every one of them goes through `buildHomePath()` today — Work's single function for *where a build
lives* — and every one of them will need to point at the page instead. **They are listed here
because wave O's own row named them in prose and a lane had to go and find them again.**

⚠ **EACH ROW LEADS WITH THE SYMBOL AND GIVES THE LINE SECOND, AND THAT IS NOT TIDINESS — THE LINE
NUMBERS WENT STALE WHILE THIS FILE WAS BEING WRITTEN.** They were measured on `a8fa8ffbb`; the LIST
lane pushed `40db81e67` in the same hour and `NewConnectsTab.tsx`'s `rowDoor()` moved from line 345
to line **408**, its number cell from 901 to **1097**, and its eye from 984 to **1230**. A symbol
survives a sibling's commit and a line number does not, which is this repo's own lesson about
pointers in a different family. **Lines below are as at `40db81e67`; grep the symbol.**

| # | Link | Symbol → file : line at `40db81e67` |
|---|---|---|
| 1 | the **New connects eye** (row action) | `RowActionLink` fed by `rowDoor()` — `07-frontend/src/features/customers/NewConnectsTab.tsx:1230`, its door computed at `:1215`, `rowDoor()` itself at `:408` |
| 1b | *and the same row's NUMBER cell*, a SECOND door added 2026-09-21 (`DEF-CUS-6132`) reading the SAME `rowDoor()` | `07-frontend/src/features/customers/NewConnectsTab.tsx:1097` |
| 2 | the **wizard's completion** — *Open this connection* | `onOpen={(home) => navigate(tenantPath(buildHomePath(home)))}` — `07-frontend/src/features/customers/NewConnectWizard.tsx:682`; the button it feeds is `props.onOpen` at `NewConnectDone.tsx:109` |
| 3 | the **Orders tab's `CONNECTION` cell** | `<ConnectionCell>` — `07-frontend/src/features/work/OrdersPage.tsx:524` → defined at `07-frontend/src/features/work/buildViews.tsx:2188`, its `<Link>` at `:2200` |
| 4 | the **approval queue's cell** | the same `<ConnectionCell>` — `07-frontend/src/features/work/AwaitingApprovalPage.tsx:237` |
| 5 | the **approval queue's eye** | `buildOrderPath(row.connection.home, row.id)` — `07-frontend/src/features/work/AwaitingApprovalPage.tsx:276`, the `RowActionLink` at `:273` |

⚠ **THE COUNT IS SIX SITES, NOT FIVE, AND THE SIXTH IS NOT A WAVE-O MISS.** `1b` did not exist on
2026-09-04; the number cell became a door on 2026-09-21 (`DEF-CUS-6132`) and was deliberately wired
to the SAME `rowDoor()` so the two doors on one row cannot disagree. **So there is one function to
change for both** — which is what that decision bought, and it is worth saying out loud before
somebody changes one of them.

⚠ **AND THREE OF THE SIX ARE ONE FUNCTION, NOT THREE EDITS.** `ConnectionCell` is written once in
`buildViews.tsx` and mounted by the Orders tab and the approval queue. Repointing it repoints both.
**That is rule 43 paying for itself, and it is the reason this CR refuses a copied panel.**

⚠ **`buildHomePath()` MUST NOT SIMPLY BE REPOINTED.** It answers *where a build LIVES*, and the
premises and the account both still host build panels — the dispatcher's drawer, the premises Build
tab and the account Work tab all read it. A lane that changes `buildHomePath()` to return the new
page changes all of those at once. **The new page needs its own path helper**; `buildHomePath()`
keeps its job.

### Lanes building right now

Five lanes are live on `claude/brave-dijkstra-xgfsgz`: RECORD (`CR-150-BRC09` and the registers),
COMPONENTS (`07-frontend/src/components`), TEXT (`NewConnect*.tsx` and the locales), DETAIL PAGE
(the page and its tabs) and LIST. **None is asked to stop.** This lane touches none of their files:
it owns this CR, its index row, the decision-log entry, `g93_one_build_destination.py`, the
route wiring and the review-ledger row.

### Which checks are now wrong — named before any code is written

| Check | Why it is wrong now | What happens |
|---|---|---|
| `G93` — *"nothing navigates to `/connections/<id>`"* | the address is a page again, so every link to it becomes lawful and the gate would refuse the correct build | **rewritten to check the rule that did NOT move** — §6 task R2 |
| `BuildRedirect.dom.test.tsx` | asserts a bookmark lands *elsewhere* | replaced by the route test, at the flip |
| `06-backend/tests/test_us_wrk_002_one_destination.py` | named for the reversed clause | ⚠ **READ IT BEFORE TOUCHING IT.** Its subject is the backend's `connection_home()` resolver, which is UNCHANGED. A test whose NAME cites a reversed ruling and whose ASSERTIONS are still true is amended in its docstring, never deleted |

---

## 5 · Sized and confirmed — in plain English, with the figure

**What was put to the Product Owner**, in their own terms and with the number that decides it:

> Today, opening build `B-2026-00042` from the New connects list sends you to the property page. Its
> units are on one tab there, the work orders on another, and the money is on the customer's account
> — **three places, two screens**. We can give you one page with seven tabs instead, at the address
> the link already uses, so nothing you have bookmarked breaks.
>
> **It costs us the screen we deleted three weeks ago.** That screen was 1,464 lines and we removed
> it because you told us a connection and an account must not be two different screens. We can build
> this one without repeating that mistake — **the panels stay written once and this page shows the
> same ones**, and **the money stays on the account with a link to it**, which is nine of the rows on
> the Overview tab.

**They chose (C).** They then removed the two *Open* buttons from the header themselves, which is
the same principle applied by the person who set it.

**The size, honestly:** one page, seven tabs, one route flip, one gate rewritten, one screen id
re-allocated, and six link sites that reduce to **three edits** because three of them are one shared
cell. **It is not a fast path** — §5's fast path is for changes touching no rule, no money and no
data, and this one reverses a rule.

---

## 6 · Execute — the tasks this lane owns

| # | Task | State |
|---|---|---|
| **R1** | This file, its index row, the reservations update, and the decision-log entry with the supersedes chain | **DONE** |
| **R2** | `G93` amended: it stops asking *"does anything link to `/connections/<id>`"* and starts asking *"is a build panel defined outside its home"* and *"does the build page re-implement the account's money"*. Id kept, Trace block carries the new ruling and its date, proved RED **through `run_gates.py`** — not through `__main__` (`DEF-GOV-3733`) | **DONE** |
| **R3** | The route. **Ordered so no link breaks:** the redirect stays mounted until the DETAIL PAGE lane's page is on the branch; then one commit flips the element, deletes `BuildRedirect.tsx` and its test, and lands a route test asserting the address renders the page **BY SCREEN ID** | **PREPARED, NOT FLIPPED** — see §6a and §6b |
| **D1–D7** | The page and its seven tabs, from the eleven PNGs read AS IMAGES | **DETAIL PAGE lane** |
| **L1** | The list: no saved-view chips, the tiles set the filter | **LIST lane** |
| **T1** | Eleven catalogues: the tab words and the one- or two-word action labels | **TEXT lane** |

### 6a · Why the route flip is a SEPARATE commit, and what happens if it is not

**A route flipped before the page exists is a live address behind a screen that is not there** —
hard-won law 2's mirror, and the customer portal's front page had two working doors out of eight for
exactly this reason on 2026-09-05. **A page built before the route is flipped is dead UI** — law 2
itself.

So: **the redirect keeps answering until the page is on the branch.** The flip is one commit that
moves the element, deletes the doorway and its test, and adds the assertion. ⚠ **AND THE ASSERTION IS
BY SCREEN ID, NOT BY COMPONENT NAME.** Law 7's *looking at the wrong thing*: a hold-expiry test once
asserted a screen was REGISTERED at an address while the router mounted it somewhere else, both
screens opened onto *"not built yet"*, and every check passed. An assertion that the route table
contains a component named `BuildDetailPage` proves nothing about what a reader gets.

⚠ **AND MOUNT IT UNDER THE REAL PATH PATTERN.** The portal front page's test mounted its component
bare in a `MemoryRouter` with no `/:tenant/portal` route, so `useParams().tenant` was undefined and
every address it built came out `//portal/…` — a protocol-relative URL to another host, which reads
as a perfectly good string to `toContain`. `BuildRedirect.dom.test.tsx:49` already mounts under
`/:tenant/connections/:connectionId`; **the replacement keeps that.**

### 6b · WHAT ACTUALLY LANDED FOR R3, AND WHAT DID NOT

**THE ROUTE IS NOT FLIPPED. `App.tsx` still mounts `BuildRedirect` and `BuildRedirect.tsx` is still
there**, because the DETAIL PAGE lane's page is not on the branch — flipping now would put a live
address in front of a screen that does not exist.

**What landed instead is the thing law 2's mirror asks for in the same commit as the hold:**
`07-frontend/src/features/work/buildAddress.route.test.tsx`, which

* asserts `/:tenant/connections/:connectionId` **is mounted in `APP_ROUTES` with an element** — the
  bookmark guarantee, and it goes red if the flip DELETES the route instead of swapping its element;
* asserts the router and `SCREEN_ROUTES` tell **one story**, and **fires the day the hold expires**:
  the moment the element stops being the doorway, it demands the screen id back, names
  `screenIds.ts` and `g29_allocated_badges.txt` in its failure message, and says to delete
  `BuildRedirect.tsx` and its test in that same commit;
* asserts **by SCREEN ID and never by component name**. The component name is read once, as the
  discriminator between the two arms, and the file says so at the top with the law-7 defect it
  would otherwise repeat — *a hold-expiry test once asserted a screen was REGISTERED at an address
  while the router mounted it somewhere else, and every check passed.*

**Proved RED before it was trusted green, twice, in vitest — the harness that runs it:** once by
pointing the doorway name at something nothing mounts (the flip simulated — the release arm fired
with its full instruction), once by pointing the address at a pattern the router does not serve (the
bookmark guarantee fired). Green as authored, with the doorway in place.

⚠ **SO THE DETAIL PAGE LANE INHERITS A CHECKLIST RATHER THAN A PARAGRAPH.** It does not need to
remember any of this: the suite will tell it, in order, on the commit that flips the route.

---

### 6c · ⛔ THE PAGE LANDED WHILE THIS FILE WAS BEING WRITTEN, AND `G93` WENT RED ON IT — `DEF-CUS-7618`

**The DETAIL PAGE lane pushed its page at `78900cac7`'s parent**, as
`07-frontend/src/features/customers/BuildDetail{Page,Tabs,Shared,Dialogs,Draft}.tsx` plus a
fixture — **4,422 lines.** The amended `G93` went red on it within the minute, naming six panels:

| Panel | Where |
|---|---|
| `BuildPrimaryAction` | `BuildDetailShared.tsx:596` |
| `BuildOverviewTab` · `BuildUnitsTab` · `BuildWorkTab` · `BuildChargesTab` · `BuildDocumentsTab` | `BuildDetailTabs.tsx:160 · :528 · :660 · :788 · :947` |

⚠ **IT IS A TRUE FINDING AND NOT A NAMING ARTEFACT — CHECKED BY READING BOTH SIDES.**
`BuildDetailTabs.tsx` imports exactly **two things** from `features/work/buildViews`:
`ORDER_STATE_LABELS` and `buildStateTone`. **Two label helpers and not one panel.** And
`BuildWorkTab` is a hand-rolled `PlainTable` with its own `<thead>`, its own tiles and its own
empty state, where `buildViews.WorkOrdersTab` is the shared `DataTable` — search, filter chip,
column chooser, pagination — that the premises and the account pages already compose. **That is
§2's rule (2) breached and B14 rule 43 breached**, and the figure that makes it plain is the one
the Product Owner already ruled on: **4,422 lines against the 1,464 they deleted for exactly
this.**

✅ **THE MONEY HALF IS RESPECTED, AND IT IS WORTH SAYING SO.** The only import from
`features/billing|ledger|payments` anywhere in the new files is
`paymentsShared.methodOptions` — a `*Shared` module, which is the LINK-helper exemption. The
Charges tab shows the build's own invoice number and links; it reads no ledger row and re-hosts no
account tab. §2's rule (1) holds.

### ⛔ SO THE ROUTE IS DELIBERATELY NOT FLIPPED, AND THESE ARE THE REASONS

1. **Flipping publishes the breach.** The address would open a page that breaks the ruling this CR
   exists to record, on a clerk's screen.
2. **`G93` checks 2 and 3 CANNOT SEE THE PAGE UNTIL IT IS FLIPPED** — they are derived from what
   `App.tsx` mounts, and that is still the doorway. So the page has never been asked *do you
   compose the home* or *do you reach for the account's money* by the gate; only check 1, which
   reads the whole front end, could see it. **Fix `DEF-CUS-7618` first, then flip, then read all
   three.**
3. **The screen id is not back.** `NCT-02` is retired, `g29_allocated_badges.txt` has no row and
   `G29`'s baseline is one lower. The hold-expiry test goes red the instant the element changes and
   names all three — which is what it is for.

**The flip is one commit and it is ready:** swap the element, delete `BuildRedirect.tsx` and
`BuildRedirect.dom.test.tsx`, restore the badge, raise `G29`'s baseline by one. Nothing else.

### 6d · ✅ `DEF-CUS-7618` IS FIXED — AND THE COUNT ABOVE WAS SIX WHERE THE GATE SAID TEN

**Amended 2026-09-28 by the `DEF-CUS-7618` lane.** §6c says `G93` went red *"naming six panels"*.
**It named TEN.** The FAIL line prints three findings and `(+7 more)`, and the six written down
are the six in the two files this CR was looking at. The other four were
`BuildMessagesTab`, `BuildAuditTab` and `BuildStatePill` — the same lane's, in the same file —
and **`BuildTiles` in `features/customers/newConnectListViews.tsx`, which is the LIST lane's and
predates this CR** (`40db81e67`). That last one is now `DEF-CUS-7622`. **Read a gate's whole scan
and not its first line**, which is law 7's third habit: a check's output must distinguish pass
from fail to a READER.

**What landed, tab by tab:**

| Tab | What it does now |
|---|---|
| **Work** | **COMPOSES `buildViews.WorkOrdersTab`** on a third host, `build`. It reads the SHARED `GET /premises/{id}/work-orders` and narrows it by `onlyOrderIds` from the build's own read, because there is no `GET /connections/{id}/work-orders` and `_scoped_row` publishes no build id. The tab gains search, a filter chip, the column chooser, pagination, the `TARGET` column, the row action and `WorkOrderPanel`'s drawer — and **CREW and TECHNICIAN each say what the one served holder actually is** instead of being two permanent dashes |
| **Overview · Units · Charges · Documents · Messages · Audit** | no shared panel draws any of them, and §3 already said where that content goes — *"built as components under the same kit"*. Each is now a file in `features/work/buildRecord/`, with the reason the shared one cannot serve it written at the top of it: `BuildTab` is the RECORD and not this drawing; `BuildRecordTiles` is a fixed five-tile vocabulary; the account's Bills tab is the money panel and re-hosting it is what check 3 refuses; the two Audit tabs read their own entity's trail |
| `BuildStatePill` · `BuildPrimaryAction` | moved into the kit unchanged, for the same rule |

`features/customers/BuildDetailTabs.tsx` is **deleted**; the page composes the kit. `G93` is
**PASS through `run_gates.py`** — 23 build panels, all in the home — with check 2 still SKIPPED,
by its own pass line, because the route has not been flipped.

---

## 7 · Version

**None allocated by this lane, and that is deliberate.** `CR-150-BRC09` owns `2.390.0`, `G35` holds
four literals in lockstep, and two lanes bumping is `DEF-GOV-3756` — three lanes each computed *the
next free number* correctly and got the same answer. `10-scripts/allocate.py version` answers
**`2.391.0`** at the time of writing; **the lane that lands the page allocates it, re-verifying at
push time**, because a version allocated now and pushed in an hour is the stale read law 11 is about.

⚠ **A CR MARKED DONE WITH NO VERSION IS REFUSED BY A GATE.** This CR is **IN PROGRESS** and may not
be marked done until the page is on screen and the version is written in all three files.

---

## 8 · Close — and the rollback, stated before shipping

### ⛔ This CR is NOT closed

**It closes when a clerk opens `B-2026-00042` from the New connects list, lands on a page with seven
tabs, reads the one-time charge figure on Overview, follows its invoice link to the account, and
comes back.** Nobody has done that. At the time of writing the page does not exist, the route still
answers a redirect, and what has landed is the record, the gate and the route's preparation.

**And the reporter is told which build to look in** — `22-product-maintenance-process.md`'s close
step. A tester who reports three things and hears nothing stops reporting.

### The rollback

**One commit, and it is cheap because of the order in §6a.**

* **Before the flip** — nothing to roll back. The redirect is untouched and every link works exactly
  as it did on `2.390.0`.
* **After the flip** — restore `BuildRedirect.tsx` and its test from git, put the element back in
  `App.tsx`, and retire the screen-id badge again. **No data moved and no migration ran**, in either
  direction: this CR changes no table and no endpoint. The address is the same address before and
  after, so **no bookmark and no handed-out link breaks in either direction** — which is the property
  wave O bought when it kept the route, and this CR spends it a second time.
* **`G93`** — its amendment is independent of the flip and is rolled back on its own if needed; the
  old body is in git history at `d58a21729`.

---

## Trace

* **Supersedes in part:** `12-governance/02-decision-log.md` 2026-09-04, *"`CR-070` WAVE O IS BUILT
  AND SHIPS AS `2.141.0` — A BUILD HAS ONE DESTINATION"* · `CR-070` §W.10 / §W.11
* **Does NOT supersede:** wave-O judgments (2) and (3) · B14 rule 43 · `BR-WRK-026`
* **Drawings:** `05-prototype/new-connect-detail-2026-09-28/` (eleven PNGs + `00-all-screens.html`,
  which is an index and never the specification — B14 rule 42)
* **Sibling:** `CR-150-BRC09` (the wizard). Same branch, same block, different screens.
