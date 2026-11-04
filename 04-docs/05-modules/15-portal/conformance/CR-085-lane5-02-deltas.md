# CR-085 lane 5 · EVERY DIFFERENCE — bills and documents, measured

**Measured 2026-09-11**, tip `b4063d1e6`, product version **2.235.0**, in a real Chromium
at **390 and 1280**, both widths, on every screen and in every state below. Six screens:
`/bills` · `/bills/:number` · `/bills/:number/comparison` · `/bills/:number/dispute` ·
`/bills/:number/document` · `/documents`.

## How this was measured, and the one thing it does not prove

⚠ **THE SHARED STACK HAS NO CUSTOMER TO SIGN IN AS.** `http://127.0.0.1:8401` serves the
single tenant `brazosbend`; `GET /api/brazosbend/portal/public/front` answers
`"is_live": false` with `cards: []`, and `portal_credential` holds **0 rows**. No portal
customer exists, so no signed-in portal screen can be populated from it, and the walk was
run with `page.route()` returning fixture JSON shaped to the exported TypeScript types.
Creating a database was refused (`permission denied to create database`) and re-seeding the
shared stack was out of scope.

**What that proves and what it does not.** The bundle, the stylesheet, the components, the
eleven catalogues and the router are the SHIPPED ones — `dist/index-N9cg-E6T.js`, the hash
the running server is actually serving, built from the checkout whose only difference from
the tip is a docs-only commit. So every label, every column, every state, every computed
padding and every overflow figure below is the product's. **What it does not prove** is the
server's own shapes — `DEF-CWP-4206` (empty year-on-year panel) and `DEF-CWP-4209` (both
bars labelled *Aug*) are server-side and are re-verified by reading, not by this walk.

Evidence: `walk.log`, `measure.log`, `measure2.log` and twelve full-page screenshots.

---

# 1 · `/bills` — `CWP-027`, blueprint screen 30

**Verdict: the closest of the six to its drawing.** It uses the shared table, it has search,
filter chips, sorting, row icons and a pager, and at 390 it becomes a card list. The
2026-09-05 audits' agreed root cause *"no list on the shared table"* is **FIXED here.**

### Present and right
h1 `Your bills` · kicker `BILLS` · `Every bill since you started, Jun 2026 · 3 bills` (the
drawing's own sentence, verbatim) · the month as the row's heading with the number under it
· `Pay` only where something is owed (empty list and all-paid list both draw none) · phone
cards · `body.scrollWidth === 390`, no sideways page scroll at either width.

### Differences

| # | what the drawing says | what is on the screen | where |
|---|---|---|---|
| 1.1 | `COVERS` | `PERIOD` | column header |
| 1.2 | four columns | **nine** — `BILL · PERIOD · ISSUED · DUE · USAGE · AMOUNT · OWING · STATUS · ACTIONS` | see `01-drawing.md` §8; the pack draws eight, so this follows the pack |
| 1.3 | `PAID JUL 19` · `DUE AUG 22` — *"Paid Jul 19, not Settled or Closed"* | `PAID` (no date) · `DUE IN 9 DAYS` (a countdown, no date) | status chip. The countdown is `DEF-CWP-3980`'s deliberate choice; **the drawing's dates are gone in both directions** |
| 1.4 | `Pay $191.00 now` on the unpaid ROW | `Pay` in the page head, **no amount**, outline not filled | Bills.tsx states why: `GET /portal/bills` serves no `total_owing`, so an amount would be browser arithmetic. **Owed: a served total.** This is CR-085's own recorded finding *"the bill that never said what to pay"* |
| 1.5 | `↓ Download all as a spreadsheet` | absent | footer |
| 1.6 | `Bills are kept for seven years` | absent | footer |
| 1.7 | *Paged at 12* | `Rows per page 50 / 100 / 200 / 500 / 1000`, default 50 | a staff control on a consumer screen; the pack draws `Rows per page 50` too, neither draws the selector |
| 1.8 | ` View · ↓ PDF` | two 32×32 icon anchors with **no visible word** (`aria-label` and `title` only) | blueprint standard A: *"In the portal every icon carries its word … a phone has no hover"* — and the 2026-09-05 audit's D4 |
| 1.9 | phone frame carries the download | at 390 the table is `display:none`, so **the printed-bill door does not exist on a phone** | **`DEF-CWP-4864`** |

### States, all four opened

| state | drawn | rendered |
|---|---|---|
| LOADING | three grey rows of the right height, *so the page does not jump* | one card, one sentence, `Reading your bills…` — **no skeleton, and the page jumps** |
| NO BILLS YET | *"Your first bill will arrive after your first meter read, around Sep 30."* | `Your first bill will appear here.` — **says where, never when** |
| FAILED | *"We could not load your bills." **Retry, plus the phone number.*** | `We could not read your bills.` — **no retry, no phone number, nothing to press** |
| MANY BILLS | paged at 12, never unpaged | paged, server-side absent (client slice), default 50 |

⚠ **The three states render the SAME PICTURE** — one `Card`, one grey sentence — which is
the blueprint's unratified **R-22** (*"three states … can never render as the same picture"*)
exactly, and the FAILED row is unratified **R-10** (*"bad news never appears without the way
out beside it"*).

---

# 2 · `/bills/:number` — `CWP-028`, blueprint screen 31

**Verdict: the charge lines are right and the rail is a different screen from either drawing.**

### Present and right
Every charge line carries **quantity · unit · unit price · amount** — the four facts the
drawing says stop the call. `800 kWh` `$0.1150 / kWh` `$92.00`. Group subtotals, `Charges
before tax`, `Tax`, `Total for this period`. Nothing is summed in the browser. Readings
panel with `read_method` honesty (*"Both taken by a reader. Neither was estimated."*). At
390 the `Amount due` card sits above the lines, as drawn.

### Differences

| # | drawn | on screen |
|---|---|---|
| 2.1 | `Bill BL-2608-000042 · covers Jul 1 – Jul 31, 2026 · issued Aug 5` **under the title** | the identity line is **inside the charges card**, under `WHAT YOU WERE CHARGED`; the head carries title and kicker only |
| 2.2 | `Due Aug 22, 2026 · **in 9 days**` | `Due 08/22/2026` — **the countdown that `CWP-027` computes is absent on the screen that needs it most** |
| 2.3 | `Pay $191.00 now` | `Pay` |
| 2.4 | rail `THIS BILL`: `Why does it cost this?` · `↓ Download the printed bill` · `Something looks wrong` · `How your water is priced` | `Why is this different? →` in the head; `See the bill we sent →` in a body section; `Query this bill →` and `Ask us about it →` in a `Something not right?` panel; **`How your water is priced` has no equivalent anywhere** |
| 2.5 | `Total for August` | `Total for this period` |
| 2.6 | — | **EXTRA**: a `Your account` panel (`Brought forward` / `This bill` / `Paid since` / `Owing`) and a `Readings this bill` table. Both come from the module pack, neither is in the blueprint |
| 2.7 | module pack: *"Tell us before the due date and **we will hold the account while we look**"* | `Tell us and somebody will look at this bill.` — **the promise is gone** (and it is the same promise `CPB-13` is about) |
| 2.8 | PAID: *"the due card becomes 'Paid in full on Aug 19' and the button disappears entirely"* | the card shows **`$0.00` in 40px type** with `Paid in full.` under it and **no date**. The button does go |
| 2.9 | ESTIMATED READ: a band above the lines | no band. The readings panel says *"One of these readings was estimated, not taken."* **below** the charges |
| 2.10 | FAILED / LOADING | **the entire head disappears** — no h1, no kicker, no back link, one grey sentence on an empty page. **`DEF-CWP-4859`** |

### Money, and a contradiction inside the blueprint itself
Rates render at **four decimals** — `$0.1150 / kWh`, `$4.2400 / kgal`, `$6.8900 / kgal`,
`$5.0000 / kgal`. Section 05's own MONEY note asks for exactly that (*"four on unit prices …
rounding it to $4.24 makes the line stop adding up"*). The blueprint's **appendix rule R-16**
says the opposite — *"Money: dollars, comma thousands, two decimals — **never four on
screen**"* — and cites CLAUDE.md hard rule 2 as its home. **One document, two answers, on
my screen.** Totals are 2 dp everywhere, which both agree on. Reported, not resolved.

### Width
At 390 the three charge tables scroll **inside their own container** (`overflow-x: auto`),
`scrollWidth 336` inside `clientWidth 316` on the Electric block — permitted by the rule, but
it means the `AMOUNT` column is off-screen until the customer discovers a sideways scroll on
the one screen whose whole job is *"so the customer can check the arithmetic themselves"*.
The page body never scrolls sideways at either width.

---

# 3 · `/bills/:number/comparison` — `CWP-030`, blueprint screen 32

**Verdict: the screen the drawing calls *"the one the portal can answer alone"* cannot
answer it.**

| # | drawn | on screen |
|---|---|---|
| 3.1 | heading **is the answer** — `Why August costs $14.80 more than July` | `Why is this bill different?` — the generic question. **`DEF-CWP-4211`, OPEN, re-verified** |
| 3.2 | `WHERE THE DIFFERENCE CAME FROM` — four lines that sum exactly to the headline | `We are still working out how to show you the reasons line by line.` `components_available: false`, `components_blocked_by: OQ-CWP-1563`. **`CPB-08`; `DEF-CWP-4207`, OPEN, re-verified** |
| 3.3 | `Your prices did not change between these two bills.` | absent. **`DEF-CWP-4212`, OPEN, re-verified** |
| 3.4 | `YOUR LAST 12 BILLS` — `Lowest $142.10` `Average $171.40` `Highest $228.75` | absent; `BillHistoryBars` was never built. Part of **`DEF-CWP-3986`** |
| 3.5 | *"The customer is never asked to subtract"* (unratified **R-06**) | the difference IS given (`+$14.80`) **and** both numbers are given above it as `Last month (BL-2607-000041) $176.20` / `This bill (BL-2608-000042) $191.00` — two bill NUMBERS where the drawing uses two MONTHS |
| 3.6 | `PRICES DID CHANGE` state — *"Water prices rose on Oct 1 · +$7.40"* | no such state exists |
| 3.7 | no action drawn; the plan's are `Send a reading` / `Query this bill` | neither. **`DEF-CWP-4213`, OPEN, re-verified** — the screen explains a bill and offers no way to act on it |
| 3.8 | back-link ` August 2026` | `← Back to BL-2608-000042` |
| 3.9 | NO PREVIOUS BILL — one sentence | the heading renders **twice** — h1 and section title. **`DEF-CWP-4862`** |

`DEF-CWP-4209` (both bars labelled *Aug*) and `DEF-CWP-4206` (empty year-on-year panel) are
**server-side**: given correct `this_year_label` / `last_year_label` the component drew
`Aug 2025` and `Aug 2026` correctly in this walk, so the client is not the fault and those
two rows stay against `billing_seam.bill_comparison_for`.

---

# 4 · `/bills/:number/document` — `CWP-029`, blueprint screen 33

⚠ **READ THE CORRECTION BEFORE THE TABLE.** The first pass of this walk read the page with
`innerText` and reported *"the preview is absent — the whole screen is three lines"*. **That
was wrong.** `innerText` cannot see inside an `<object>`, and the preview is there:
`<object data="/api/brazosbend/portal/bills/BL-2608-000042/document.pdf?view=1"
type="application/pdf" aria-label="The bill we sent you">` inside
`[data-document-preview]`, **605 × 783 px** at 1280. It was built under `DEF-CWP-3983`, it
is wired to the server's `?view=1` branch, and `DEF-CWP-3986`'s `DocumentPreview` line is
**CLOSED for this screen**. The finding was an instrument that could not distinguish a
missing element from an unreadable one — law 7's *"looking at the wrong thing"* — and it is
recorded rather than quietly deleted.

**What is actually wrong**, measured with `getBoundingClientRect`:

| drawn | on screen |
|---|---|
| *"the real document at real proportions"* | **at 390 the page renders at 165 × 213 px** inside a 316 px column. `DocumentPreview` hardcodes `w-[62%]` with no responsive step: 62% of 1026 is a readable 605, 62% of 316 is a thumbnail. **`DEF-CWP-4865`** |
| `🖨 Print` — *"Print is second because most people asking for this need a file, not paper"* | **absent.** The only `<button>` on the page is `Sign out` |
| `— page 1 of 1 —`, *"the page count is stated on screen"* | **absent** |
| rail `NEED IT ELSEWHERE?`: `↓ Download as a spreadsheet`, ` Email a copy to yourself` | **absent** |
| MULTI-PAGE: *"page navigation appears only when there is more than one page"* | **absent** |
| GENERATING: *"Preparing your bill…" with the download disabled* | **absent** |
| BLOCKED: *"a viewer that cannot start downloads gets a plain link"* | **present** — the `<object>`'s own fallback child is the download anchor, which is exactly the drawn behaviour |
| NOT AVAILABLE | **present and good** — `We do not have that file.` + `Ask us for a copy →`, and a second sentence for *what we have is not what you received* |
| `Exactly as it was printed and posted on 08/05/2026.` | present, through `asDate` |

`DocumentPreview` also carries three arbitrary Tailwind values the skill forbids by name —
`w-[62%]`, `aspect-[8.5/11]`, `bg-[white]`.

**`DEF-CWP-4657` (this route answering 500 when the kept file is gone) reads OPEN in the
register and the code says otherwise**: `bill_document_pdf` now raises a named `BizError`
on both absences — `portal.billDocument.notKept` under `BR-CWP-045`, and
`portal.document.notTrusted` under `BR-NOT-027` for bytes that no longer hash to the record
— and cites `DEF-CWP-4699` for the second. The row should be re-read by its owner.

**The blueprint marks this screen `EXISTS BEHIND` / `NO COMMITMENT`** — nothing undertakes to
build the print button, the page count, the email copy or the multi-page navigation. That is
the finding to take to the register, not a defect against a lane.

# 5 · `/bills/:number/dispute` — `CWP-055`, blueprint screen 34

**Verdict: built as a two-step wizard where the drawing draws one page, and the panel the
drawing calls `THE CRITICAL PANEL` says the opposite of what the drawing says.**

| # | drawn | on screen |
|---|---|---|
| 5.1 | `Something looks wrong` — *and the WORDS note says explicitly not "Raise a dispute" or "Billing enquiry", because "customers do not think of themselves as disputing"* | `Something is wrong with this bill`, and the body says `querying` / `Send the query ✓` / `Track this query →` / `While a bill is queried` |
| 5.2 | `About your August bill, $191.00` / `About bill BL-2608-000042 · August 2026 · $191.00` | `You are querying bill BL-2608-000042, $191.00.` — **no month, no period, no services**. `DEF-CWP-4202`, OPEN, **partly true still**: the amount IS shown now, the rest is not |
| 5.3 | **`WHILE WE LOOK INTO IT` — *"The disputed amount is not due and no late fee is added to it. The rest of the bill is still due on Aug 22."*** | **`WHILE A BILL IS QUERIED` — *"The bill stands and its due date keeps running, so tell us if that worries you."*** — the opposite answer to the question the drawing says is *"the question behind the question"*. This is **`CPB-13`** and the build is honestly saying what it can do; **the drawing is describing work nobody has undertaken** |
| 5.4 | `WHAT HAPPENS NEXT` — four numbered steps | `WHAT THIS MEANS` — four unnumbered consequence sentences, different content |
| 5.5 | `Which service?` select | **absent** |
| 5.6 | `A photo, if it helps` · `📷 Add a photo of your meter` (`FileDrop` is in the drawn component list) | **absent**. In its place: `Your own reading today` — a field the drawing does not have |
| 5.7 | *"We reply within **2 working days**"* | *"We answer within **five** working days."* (rule 37 makes the drawn 2 an illustration; the built 5 is the promise a customer will hold us to) |
| 5.8 | PRIMARY ACTION `Send it` — *"One button"* | a two-step stepper: `1 What is wrong` / `2 Check and send`, primary `Check it` |
| 5.9 | ALREADY DISPUTED / TOO LATE / PHOTO TOO LARGE states | `A query is already open.` exists; no *too late* window; no photo |
| 5.10 | — | the three helpers are **not bound to their inputs** (`aria-describedby` null). **`DEF-CWP-4863`** |

The five reason options are **verbatim correct and in the drawn order** — the one part of
this screen that matches character for character.

---

# 6 · `/documents` — `CWP-031`, blueprint screen 60

| # | drawn | on screen |
|---|---|---|
| 6.1 | `Your documents` (blueprint) / `Everything we have sent you` (pack) | h1 `Documents and letters`; `Everything we have sent you` is the table CAPTION |
| 6.2 | `6 documents · **kept for seven years**` | **no count, no retention sentence**. `CPB-15` half one |
| 6.3 | `↓ Download a spreadsheet of everything` | **absent**. `CPB-15` half two |
| 6.4 | rail `ASK FOR A LETTER` / `Ask for one` / *Usually ready the same day* | **absent entirely**. `CPB-14` — *"the one document people phone for and that is never in a list"* |
| 6.5 | four columns `DOCUMENT · KIND · SENT · HOW` | **six** — adds `WHAT WE KNOW` and `ACTIONS` |
| 6.6 | `↓ Download a year of bills as one file` | `Download a year ↓` present, and **not held** — so `CPB-03`'s *"Downloads are not ready yet"* hold is already released on this screen |
| 6.7 | — | banner *"We cannot confirm that anything arrived — post and email remain the record of delivery."* — `CPB-20`, a live refusal, **33 words over three sentences** against B14 rule 32's one-sentence budget |
| 6.8 | phone: a **card list** | at 390 it is still the six-column table, `scrollWidth 507` inside `clientWidth 316` — **it scrolls sideways inside its container**, so `HOW`, `WHAT WE KNOW` and both row actions are off-screen until a customer finds a scroll nobody told them about. The page body does not move (390 = 390). **`CWP-027` solved this with cards; `CWP-031` did not** |
| 6.9 | NONE YET *"With the first bill's expected date"* | `Nothing has been sent to you yet. Your bills, receipts and letters will appear here as soon as we send the first one.` — no date, and two sentences |
| 6.10 | — | every row reads `Came back to us on .` — a bounce claim with an empty date, and a raw ISO date when there is one. **`DEF-CWP-4860`** |
| 6.11 | — | `Rows per page 50/100/200/500/1000` again |

The door is right: `Bills` links to `/documents` through `WhereNext`, and `My details` does
not — exactly as the drawing asks.

---

# 7 · Both widths, on all six — the responsive verdict

| screen | 1280 | 390 |
|---|---|---|
| `/bills` | no page overflow | **no page overflow**; table → cards; loses search, chips, pager, both row actions |
| `/bills/:number` | no page overflow | no page overflow; four tables scroll inside their containers (336 in 316) |
| `/bills/:number/comparison` | no page overflow | no page overflow; identical content |
| `/bills/:number/dispute` | no page overflow | no page overflow; identical content, fields stack |
| `/bills/:number/document` | no page overflow; preview 605x783 | no page overflow; **preview shrinks to 165x213 — unreadable** (`DEF-CWP-4865`) |
| `/documents` | no page overflow | **no page overflow**, but the table does **not** become cards: 507 in 316 |

**`document.body.scrollWidth === window.innerWidth` on all twelve measurements.** Nothing
scrolls the page sideways. The two remaining width problems are (a) `/documents` keeping a
six-column table on a phone where its sibling list became cards, and (b) `/bills` dropping
two row controls when it becomes cards.

---

# 8 · Signed out at all six addresses — `CPB-17`, confirmed live

Opened each of the six without a session against the running server (no stub): every one
answers `401` on `GET /portal/session` and renders, identically:

> **Failed** · *We could not open this page.* · *You're signed out. Sign in again to
> continue.* · `Retry` · `Download error report` · `Cancel`

**No sign-in link.** *"Sign in again to continue"* with nothing to press, and a
`Download error report` button offered to a utility customer. `CPB-17` describes exactly
this and is `UNVERIFIED`; it is **live on all six of this lane's screens**, and it matters
most on `/bills/:number/document`, which the drawing says exists so a customer can send the
bill to a landlord or an accountant — i.e. a link somebody follows cold.
