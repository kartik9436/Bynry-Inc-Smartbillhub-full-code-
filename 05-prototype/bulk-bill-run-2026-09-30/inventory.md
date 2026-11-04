# Bulk bill run — screen inventory (D2, 2026-09-30)

The `react-tailwind-css-ui-generator` skill's §2.1–§2.5 inventory for **one product page with
four steps** (Scope · Check · Sign off · Send, with a Calculating panel between Check and Sign off),
read from the 72 PNGs in this folder (B14 rule 42: the images are the spec; `mockup.html` was used
only to check spelling). Change list: `04-docs/05-modules/07-billing/14-bulk-bill-run-changes.md`
rows 1–43. Build plan: `15-bulk-bill-run-build-plan.md` (F1–F19). Image index: `README.md`.

**How to read this file.**
- Strings in `code` are copied from the drawing. Where the drawing shows UPPERCASE (kickers, column
  heads, pills), the **source string is sentence case** and the capitals come from CSS — the
  catalogue key holds `Blocks the bill`, not `BLOCKS THE BILL`.
- Every figure, name, account number, address and date is **example data** (B14 rule 37).
- Spacing, sizes, type and tokens come from **our UI standard, not the drawing** (rule 44; rule 38
  for forms).
- "Kit" names a file in `07-frontend/src/components/`. **NEW** means nothing in the kit does it
  today and the plan's F-task adds it as a component (rule 43), never inline code in a page.
- Image numbers (`01`–`36`) refer to both widths; 1440 and 1280 draw the same layout (the mock-up
  caps content at 1180px), so no element appears at one width and not the other.

---

## 0 · Must NOT be built (mock-up chrome, capture faults, drawing faults)

| What | Where | Why |
|---|---|---|
| The dashed strip `Design mock-up · example data` with `Scope state:` `Continuous` `Gap` `Overlap` `Warnings` `Problems` and `Check state:` `Checking` `Results` `Module down` | Top of every image | A review control. The states it switches are reached by real data. |
| Side panels and scrim drawn only over the top 900px | `07`, `08`, `22`, `30` | A `position: fixed` panel in a full-page screenshot. In the product the panel and scrim cover the viewport. |
| Category list cut at the panel height | Most Check images | The list scrolls inside its column; the build does the same, but the cut is not a design. |
| Search hides **No reading** from the list while the pane still shows it | `18` | Mock-up fault. When a search hides the open tag, the pane opens the first tag still shown. |
| Toast `Opens Meter Reads, account filled in in a new tab.` | `14` | The mock-up's stand-in for "opens in a new tab". The build opens the screen; no toast. |
| `Warnings 3` on Send vs `4 warnings.` on Sign off; `1,104 e-mail` on Send vs `1,102 e-mail` on Sent | `31`/`32`, `35` | Illustration numbers (rule 37). The build counts; Sent shows what was actually sent. |
| **No run number series** drawn as a **refusal** | — | Not drawn as one in these images (`05` shows it as a warning, which is the ruling). Recorded because the design record once had it as a refusal: it is a **warning** (changes row 43, decision log 2026-09-30). |
| `Nobody to bill` as a per-ACCOUNT tag under Accounts & units in Check | `16`, `19`, `Also has` chips | A unit with nobody to bill has no account, so it cannot appear on an account row. It is counted and listed on Scope (`07`) and in Not in this run's **Nobody to bill** filter (`29`) — both unit lists. Build it there, not as an account tag. |

---

## 1 · The frame — identical on every step

### 1.1 Page header (chrome)

| # | Element | String | Kit |
|---|---|---|---|
| 1 | Breadcrumb | `Billing › Bill runs` | `PageHeader.tsx` |
| 2 | Title | `Bill run` | `PageHeader.tsx` (32px, rule 40) |
| 3 | Run line, right, muted (from step 2 on) | `Run BR-0232 · Cycle 3 · Sep 1 – Sep 30, 2026` | `PageHeader.tsx` actions slot |

No subtitle, no back arrow, no action buttons in the header.

### 1.2 Step rail (chrome)

Four equal cells: `Scope` · `Check` · `Sign off` · `Send`. Current = accent number box + accent
underline; done = black box with `✓`; future = outlined grey number, disabled. After Send all four
show `✓` (`35`, `36`). **Four steps, not six** (Billing blueprint p35). Kit: the existing
`RunWizardShell` stepper (F2) — one screen, not two.

### 1.3 Body

Scope, Sign off and Send: main column + summary aside on the right. **Check is full width — no
aside** (changes row 36). Calculating (`24`) sits in the Check body, full width.

### 1.4 Summary aside (data; kit: **NEW** `RunSummaryCard`, F6, from `Panel.tsx`)

| Block | Rows | Steps |
|---|---|---|
| Kicker | `Run to start` (Scope) · `Run BR-0232` (later) | all |
| Run facts | `Run name` · `Cycle` · `Period` (with `· 30 days`) · `Bill date` · `Days to pay` · `Due` · `Template` — `—` when not yet valid (`05`) | all |
| Counts | `To fix` (red pill, or green `0`) · `Warnings` (amber pill) | Scope |
| Services | heading `Services`, then one chip per utility service (colour square + name), seed order — `ServiceChips.tsx` | Scope |
| Covers | `Units` · `Accounts` · `Regular · master` (`1,394 · 12`) · `Meters` · `Routes` | Scope |
| Last run | `Last run` (`BR-0231 · Aug 1 – Aug 31`) · `Last run total` · `Follows on` pill `Continuous` / `Gap` / `Overlap` | Scope |
| Check result | `Ready` (green) · `Need a decision` (amber) · `Blocked` (red) | from Check |
| Drafts | big total `$214,386.52` · `1,371 draft bills` | Sign off, Send |

### 1.5 Footer actions (chrome)

Left `Back` (secondary) from step 2 on; right the step's primary. A refusal reason sits left of a
disabled primary (`Fix 5 things first.`) and a consequence left of an enabled one
(`19 blocked stay out of this run.`).

---

## 2 · Step 1 — Scope (`01`–`08`)

### 2.1 Problems at the top (kit: `StateFrame.tsx` `FormErrorSummary`; changes row 35)

Above What to bill, main column only. Two boxes, each only when it has lines:

| Box | Title | Line shape |
|---|---|---|
| Red, `role="alert"` | `Fix <n> things to start.` (`Fix 1 thing to start.`) | **field name as a link** that jumps to and focuses the field, ` — `, message |
| Amber | `<n> warnings. You can still start.` | field name as a link (or bold, for a count with no field), ` — `, message, optional link |

Every refusal and warning also shows **under its field** (red / amber) — `05`, `04`, `02`, `03`.

Drawn lines (copy, rule 33):

| Kind | Field | Message | Image |
|---|---|---|---|
| Refusal | Run name | `Enter a run name.` | `05` |
| Refusal | Period end | `Ends before it starts.` | `05` |
| Refusal | Bill date | `Cycle has no bill day. Enter one.` | `05` |
| Refusal | Days to pay | `Enter whole days, zero or more.` | `05` |
| Refusal | Bill template | `Not published. Publish it first.` | `05` |
| Refusal | Period start | `Sep 15 – Sep 30 already billed.` + link `Open BR-0231` | `03` |
| Warning | Run number | `No number series yet. Numbered when set up.` | `05` |
| Warning | Period start | `Oct 1 – Oct 9 not billed by any run.` | `02` |
| Warning | Period | `45 days. Cycle is monthly. Ends after today.` | `04` |
| Warning | Bill date | `Not the cycle's bill day (1st).` | `04` |
| Warning | Days to pay | `Changed from the cycle's 21.` | `04` |
| Warning | Bill template | `Not the cycle's usual template.` | `04` |
| Warning | Units | `7 units have nobody to bill.` + link `See units` (opens §2.6) | all |
| Warning | Meters | `9 services have no meter. Not billed.` + link `See services` (opens §2.7) | all |

**Not drawn, built from changes row 43 in the same boxes:** not allowed to run bills; cycle
missing or not this utility's; period missing or not a date; same cycle and period already run
(who, when, link); **bill date before the period ends** (new refusal, decision log 2026-09-30);
cycle has no units; cycle has no accounts to bill; Meter Reads or Customers not answering (names
which, form kept); warnings *first run for this cycle*. **A gap is a warning with no tick** — there
is no "Continue anyway" checkbox anywhere (row 35, superseding row 17's tick).

### 2.2 What to bill (not collapsible; kit: `Panel.tsx` + form kit, rule 38)

| Order | Label | Control | Help (when valid) |
|---|---|---|---|
| 1 | `Run name *` (wide) | text, e.g. `September 2026 · Riverside` | — |
| 2 | `Cycle *` | select `Cycle 3 · Riverside` | — |
| 3 | `Period start *` | date | — |
| 4 | `Period end *` | date | — |
| 5 | `Bill date *` | date | `Cycle bill day: 1st.` |
| 6 | `Days to pay *` | number | `From the cycle. Due Oct 22.` |
| 7 | `Bill template *` (wide) | select `Standard bill · v4` | — |

Below the fields, the continuity line: pill + fact — `Continuous` `Follows run BR-0231 (Aug 1 – Aug 31). 30 days.` ·
`Gap` `Oct 1 – Oct 9 not billed.` · `Overlap` `Sep 15 – Sep 30 billed by BR-0231.`

### 2.3 Cycle details (collapsible, open by default; kit: **NEW** `CollapsiblePanel` if none, F5)

Header: `Cycle details`, summary kicker `Monthly · bill day 1st`, link `Open cycle` (new tab, Settings › Cycles), chevron.
Facts grid: `Cycle` (wide) · `Run name` (wide, `—` when empty) · `Frequency` · `Reads start` `Day 1` with small `5 days to complete` · `Bill day` · `Days to pay` · `Routes` · `First run` · `Runs so far` · `Status` pill `Active`.

### 2.4 This run covers (collapsible, open by default)

Header kicker `1,406 accounts · 2,210 meters`. Eight fact cards in two rows:
`Units in cycle` · `Accounts to bill` (+ small `Last run 1,398`) · `Regular accounts` (+ `Last run 1,387`) · `Master accounts` (+ `Last run 11`) ·
`Meters` · `Sub-meters` · `Behind the meter` · `Missing meter`.
**Last-run figures only on the three account cards** (row 30).

### 2.5 Previous runs (collapsible, CLOSED by default; `03` opens it)

Header kicker `Last BR-0231 · Aug 1 – Aug 31`. Table (kit: `DataTable`): `Run` (run no. as link + run name below) · `Period` · `Bills` (right) · `Value` (right) · `Run by` · `Status` pill (`Sent`, `Cancelled`). Newest first. Link `All runs` below (Bill runs, filtered to the cycle).

### 2.6 Nobody to bill panel (`07`; kit: **NEW** `RunListPanel`, F19, from the kit's side panel)

Kicker `Units`, title `Nobody to bill` + count, note `Their usage is not billed until an account is added.`, close `✕`.
Columns: `Unit` · `Services connected` · `Last account` (`Moved out Aug 12` / `Never had one`) · `Action` button `Add account ↗` (Accounts › New account, unit filled in).

### 2.7 Missing meter panel (`08`)

Kicker `Services`, title `Missing meter`, note `Connected with no meter. Not billed.` Columns: `Unit` · `Service` · `Account` · `Action` `Fit a meter ↗` (Assets › Add meter, unit and service filled in).

### 2.8 Collapsed (`06`)

The three collapsible panels show header + summary kicker + `▼` only. What to bill never collapses.

### 2.9 Footer

`Start checking` (primary). Disabled with `Fix <n> things first.` while any refusal exists; warnings never disable it.

---

## 3 · Step 2 — Check (`09`–`23`)

### 3.1 Checking (`09`) and module down (`10`)

- Panel `Checking accounts`, kicker `633 of 1,406`, progress bar, note `Runs in the background. You can leave and come back.`
- Module down: red note, bold `Meter Reads isn't answering. No account was checked.` then `Try again in a few minutes. The run is saved. Ref C-8812.`; button `Try again`. (Row 24: names what; the support reference; run kept.)

### 3.2 Head and tiles

Panel title `Check`, kicker `Checked 1,406 accounts · saved`. Five tiles, each a button that filters:
`Problem types` `40` · `Blocked accounts` `19` (red) · `Need a decision` `62` (amber) · `Warnings` `73` (blue) · `Ready accounts` `1,318` (green). Pressed tile has the accent underline (`17`, `21`).

### 3.3 Left list (kit: **NEW** `ProblemTagList`, F8)

1. Search `Find a problem`; checkbox `Show 7 passed checks`.
2. **`Ready to bill` `1,318`** — first entry, above the categories (row 41).
3. Categories, each a collapsible header with its total (`Payments & balances 109 ▴`), then its tags: severity square (red blocks · amber decision · blue warning) + name + count. A passed tag shows `✓` in place of the count and only when `Show passed checks` is ticked (`19`). Selected tag = black row.

Categories and tags as drawn (severity · meaning shown in the pane):

| Category | Tags |
|---|---|
| Payments & balances | Paid after cut-off (D) · Unmatched payment (D) · Bounced payment (D) · Plan instalment due (D) · Level pay off track (D) · Credit covers bill (W) · Autopay card expiring (W) · Deposit not paid (W) · In collections (W) |
| Readings | No reading (D) · Estimated reading (D) · Usage too high (D) · Usage too low (D) · No usage (D) · Factor changed (D) · Meter replaced (D) · True-up due (D) · Disputed reading (B) |
| Meter history | Meter swapped (B) · Reading went down (B) · Time-of-use unmatched (B) · No multiplier (B) |
| Plans & rates | No plan (B) · Plan not published (B) · No price for service (B) · No price in force (B) · No charge for type (B) · Pricing refused (B) · Base charge $0.00 (W) |
| Accounts & units | No unit (B) · Standing charges only (D) · Partly disconnected (B) — *(Nobody to bill: see §0)* |
| Master accounts | Coverage unknown · Units on two plans · Service repeated · Unit state unknown (all B) |
| Assets & connections | No size (B) · No asset count (B) · No size class (B) · Missing meter (W) |
| Billing period | Gap or overlap (D) · Long or short period (D) |
| Setup | Currency not set (B) · City limits unknown (B) · No bill number series (W) · No services on file (W) |

Nine categories drawn (changes row 36 names eight; Payments & balances was added by row 38).

### 3.4 Tag pane (kit: **NEW** `ProblemTagPane`, F9)

Head: kicker = category, title = tag + severity pill (`Needs a decision` / `Blocks the bill` / `Warning` / `No problems`), line `<n> accounts · <meaning> Fixed in <screen>.`; right: `Find account` search.

Action bar by severity:
- **Decision** (`11`, `12`, `16`): `Answer for all 48:` + one segmented button per answer (e.g. `Estimate` `Hold` `Bill without it`; `Apply to this bill` `Next bill`), then — when rows are selected — `Apply to 3 selected`, then `Pre-selected from Billing settings.`
- **Blocking, fixable here** (`13`, `23`): `Fix here, row by row.` · `Re-check 4 accounts` · `Not fixed? It stays out of this run.`
- **Blocking, fixed elsewhere** (`14`, `17`): `Open Meter Reads ↗` · `Re-check 2 accounts` · same note.
- **Warning** (`15`): `Bills anyway. Nothing to decide.`

Table (kit: `DataTable`, one table type, rule 3): select box + select-all · `Account` (number as link opening Fix account, name below) · `Unit` · `Service` (e.g. `Water · W-10442`, `—` where none) · `Also has` (chips for the account's OTHER tags, coloured by severity, each opening that tag) · last column `Decision` / `Fix` / `More`.

Last-column cell:
- Decision: select with the tag's answers (row override); where a fact can be typed, `or enter it:` + input (`Reading` + unit `kgal`) + `Save`.
- Blocking inline: `Choose plan` / `Choose size` / `Count` / `Choose unit` / `Inside city?` + `Save`; after save the row turns green and reads `Fixed · re-checked` (`13`, `23`).
- Blocking elsewhere: link `Fix in Meter Reads ↗` (new tab, account filled in).
- Warning: link `See in <screen> ↗`.

Pager: `1–8 of 48`, `Previous` `Next` (server-paged; NFR-3).

### 3.5 Ready to bill (`20`, `21`; kit: **NEW** `ReadyToBillPane`, F12)

Kicker `Ready`, title `Ready to bill` + pill `No problems`, line `1,317 accounts · Nothing to fix. Priced in the next step.`, `Find account`.
Segments `All` · `Regular 1,306` · `Master 12`, note `Leave one out to bill it later.`, pill `1 left out` once any.
Columns: `Account` (number + name, `· master` suffix) · `Unit` · `Services` (service chips) · `Plan` · `Readings` pill `All read` · button `Leave out` / `Put back`. A left-out row is dimmed (`21`).

### 3.6 Fix account side panel (`22`; kit: **NEW** `FixAccountPanel`, F11)

Kicker `Fix account`, title account number, line `Sara Cohen · 1589 Pine Ct · Unit A`, close `✕`.
Kicker `3 problems on this account`, then one card per problem: severity square + name + severity pill, meaning, and the same fix control as the table cell. Footer: `Re-check runs this account again.` + primary `Re-check account`.

### 3.7 Footer

`Back` · `19 blocked stay out of this run.` · primary `Price 1,371 accounts`.

---

## 4 · Calculating (`24`)

Panel `Calculating bills`, kicker `754 of 1,371`, progress bar, note `Draft bills only. Nothing is sent. One failure doesn't stop the rest.` (Row 39: bills are calculated between step 2 and step 3.)

---

## 5 · Step 3 — Sign off (`25`–`31`)

### 5.1 Run summary (not collapsible)

Title `Run summary`, kicker `Drafts · nothing sent`. Four facts: `Bills` `1,371` (small `of 1,406 accounts`) · `This run's charges` · `Payments applied` (small `2,118 payments`) · `Amount due` (small `Due Oct 22`).

### 5.2 Who is billed (collapsible, open; `26`)

Two tables side by side, each `…` · `Count` · link column:

| Accounts | | Units | |
|---|---|---|---|
| **Accounts to bill** (step 1) | 1,406 | **Units in cycle** (step 1) | 1,482 |
| Billed | 1,371 | Billed | 1,440 |
| · Regular accounts | 1,359 | · On their own account | 1,359 |
| · Master accounts | 12 | · Through a master account | 81 |
| Not billed | 35 | Not billed | 42 |
| · Blocked `See` | 19 | · Account not billed `See` | 28 |
| · Held by a decision `See` | 9 | · Nothing to bill `See` | 7 |
| · Nothing to bill `See` | 7 | · Nobody to bill `See` | 7 |

Every line adds to the step 1 figure (row 37). **Every `See` goes to Not in this run with that filter pressed — no side panel** (row 42).

### 5.3 Usage and charges (collapsible, open; `27`)

Kicker `5 services · $214,386.52`. Columns `Service` (service chip) · `Bills` · `Usage` (with unit: `612,340 kWh`, `18,420 kgal`, `1,388 carts`, `1,371 ERU`) · `Usage charges` · `Base charges` · `Total`; `—` where none. Subtotal row `Services`. Then `Taxes` (`2 tax rates`) · `Late fees` (`on unpaid balances`) · `Reconnection fees` · `Credits and adjustments` (negative with `−`). Total row `This run's charges`. Note `Sewer is billed on water usage. 48 readings estimated.`

### 5.4 Payments and balances (collapsible, open; `28`)

Kicker `Amount due $219,679.29`. Left `Balance` · `Amount`: `Previous balance` · `Payments applied since last bill` (count muted) `−` · `Credits applied` `−` · `This run's charges` · total `Amount due`. Right `How it will be paid` · `Accounts` · `Amount`: `Autopay on Oct 22` · `Payment plan instalments` · `Level pay` · `Credit covers the bill` · `Pay by due date` — adds back to the amount due.

### 5.5 By customer type (collapsible, CLOSED by default; open in `25`)

Kicker `4 types`. `Customer type` · `Bills` · `Charges`; total row.

### 5.6 Not in this run (collapsible, open; after By customer type — row 40; kit: **NEW** `NotInRunList`, F14/F15/F19)

Kicker `35 accounts · 7 units` (accounts and units counted apart). Segments `All 42` · `Blocked 19` · `Held 9` · `Nothing to bill 7` · `Nobody to bill 7`. Action `Fix and re-check` (disabled until a selection; `Fix and re-check 3` with one) and note `When you send, these go to Pending billing. Bill them later in a catch-up run.`
Columns: select · `Account` (number + name; for a unit row `No account` + its services) · `Unit` · `Why not billed` (pill `Blocked` / `Held` / `Nothing to bill` / `Nobody to bill` + reason) · `Fix` (`Fix in Check` → the tag; unit row `Add account ↗`). Unit rows have no checkbox (`29`). Pager.

### 5.7 Warnings note

Amber, `4 warnings.` then one line each with a link: `14 bills: Electric base $0.00.` `See` (→ Check tag) · `3 bills: no services on file.` `See` · `4 autopay cards expire before Oct 22.` `See` · `2 bills failed to draft.` `See breaks` (→ §5.8).

### 5.8 Failed to draft panel (`30`)

Kicker `Bills`, title `Failed to draft 2`, note `The other bills are fine. Fix and retry these two.` Columns `Account` · `What failed` · `Fix in` (link to the named screen ↗) · `Action` `Retry` (→ pill `Drafted`).

### 5.9 Sign off confirmations (`31`)

Panel `Sign off`, five checkboxes: `Bills follow our rules and rates` · `E-mail customers have agreed to e-bills` · `SMS customers have agreed to texts` · `Autopay customers will be charged on the due date` · `I checked the totals`. Footer `Back` · primary `Sign off`, disabled until all five are ticked.

---

## 6 · Step 4 — Send and Sent (`32`–`36`)

### 6.1 Send card (`32`, `33`)

One panel with a heavy black top rule. Left: kicker `Run BR-0232 · Cycle 3`, title `Sep 1 – Sep 30, 2026`, `Signed off by J. Ortiz · Oct 1, 09:42`. Right: kicker `Total`, big `$214,386.52`, `1,371 bills · due Oct 22`.
Key-value table: `Delivery` `1,104 e-mail · 267 paper` · `Autopay` `388 accounts` · `Template` `Standard bill · v4` · `Warnings` pill `3`.
Red note `Final once sent.` `Changes need a credit note.` Checkbox `I checked the totals`. Footer `Back` · danger button `Send 1,371 bills`, disabled until ticked.

### 6.2 Sending (`34`)

Panel `Sending`, kicker `686 of 1,371`, bar, `Each bill is sent on its own. One failure doesn't stop the rest.`

### 6.3 Sent (`35`)

Green `✓` block, title `1,369 bills sent`, key-values `Total` · `Due` · `Delivery` `1,102 e-mail · 267 paper · queued` · `Meter reads` `Locked`. Red note `2 bills not sent.` naming each account and what failed, link `See breaks`. Buttons `View run` (primary) · `Print paper bills`.
Then **Not in this run** again, kicker `… · in Pending billing`, same segments, actions `Start catch-up run for N` (primary, disabled until a selection) · `Leave for next cycle` · link `Open Pending billing`; last column `Waiting / fix` shows days waiting (`0 days`).

### 6.4 Catch-up started (`36`)

Green note: `Catch-up run BR-0232-A started for 5 accounts.` `Same period, Sep 1 – Sep 30. It goes through Check, Sign off and Send like any run.` link `Open BR-0232-A`.

---

## 7 · States (skill §2.2)

| State | Images | What changes |
|---|---|---|
| Continuous / Gap / Overlap | `01` / `02` / `03` | Continuity pill + line; aside `Follows on`; gap = amber line, overlap = red line with link |
| Warnings only | `04` | amber box + amber field messages; Start enabled |
| Problems | `05` | red + amber boxes; red fields; aside facts `—`; Start disabled with reason |
| Collapsed | `06` | §2.8 |
| List panels | `07`, `08`, `30` | §2.6, §2.7, §5.8 |
| Checking / Module down / Calculating / Sending | `09` / `10` / `24` / `34` | progress panels; module down stop |
| Tag kinds | `11`, `13`, `14`, `15`, `16` | §3.4 action bar and last column |
| Rows selected | `12` | `Apply to 3 selected` appears |
| Fixed and re-checked | `13`, `23` | green row, `Fixed · re-checked` |
| Tile filter / search / passed | `17` / `18` / `19` | list narrows; passed tags with `✓` |
| Ready / left out | `20` / `21` | §3.5 |
| Fix account | `22` | §3.6 |
| Sign off sections | `25`–`29` | open/closed; filter pressed |
| Confirmations / ack ticked | `31` / `33` | primary enabled |
| Sent / catch-up | `35` / `36` | §6.3, §6.4 |

**Not drawn, and the build still owes them** (StateFrame kit, copy within rule 33): loading of each read (scope preview, findings, a tag's page, sign-off summary); an empty tag search (`No match.` is the drawn empty for the tag list only); a failed read with retry; permission denied (view-only role — also a Scope refusal); a Check resumed after leaving (row 25); a run with nothing left out (Not in this run hidden or empty); a server refusal on Start, Sign off and Send.

---

## 8 · Chrome vs data (skill §2.2)

Chrome (catalogue strings): header, rail labels, panel titles, column heads, field labels, severity pill words, button labels, notes. Data (from the API): every count, figure, run number, name, address, service list, tag list and its counts, answers offered per decision tag, last-run figures, continuity result, and the refusal/warning list with its field keys.

## 9 · Repetition — build once, use many (skill §2.3, rule 43)

| Component | Used by |
|---|---|
| Collapsible panel with summary kicker | Cycle details, This run covers, Previous runs, Who is billed, Usage and charges, Payments and balances, By customer type, Not in this run |
| Fact card grid | Cycle details, This run covers, Run summary |
| Severity pill + square (3 severities + ok) | tags, pane head, Also has chips, Fix account cards, Not in this run |
| Side list panel (kicker, title + count, note, table, close) | Nobody to bill, Missing meter, Failed to draft |
| Progress panel (title, `n of N`, bar, note) | Checking, Calculating, Sending |
| Segmented filter | Ready to bill, Not in this run, decision answers |
| `ServiceChips.tsx` | aside, Ready to bill, Usage and charges |
| Not in this run list | Sign off and Sent (two action sets) |
| Run summary card | all steps, growing per step |

## 10 · Rhythm (skill §2.4) — drawn, then mapped to our scale

The drawing uses a 4px scale, 20px between panels, 20px panel padding, 12–16px field gaps, square corners and a 1180px content cap — the same as our tokens; build with the kit's spacing (rule 44), not the drawing's pixel values. Page title 32px (rule 40).

## 11 · What is ABSENT (skill §2.5) — decisions, not gaps

| Absent | Why (source) |
|---|---|
| **No services filter on Scope** — no "which services" checkboxes anywhere | Removed; which services bill is decided per account at run time (decision log 2026-09-30; row 11; `BR-BIL-005` key without a services term) |
| **No standing answers on Scope** (no Defaults group, no estimate/hold/prorate choices) | Moved to Check, per tag, pre-selected from Billing settings (row 13; `BR-BIL-1040` amended 2026-09-30) |
| **No "billed to owner" card or line** anywhere — only Regular and Master | PO: *"there is no Billed to owner - we dont have this category"* (row 15) |
| **No "Continue anyway" tick on a gap** | Gap warns, Start stays enabled (row 35 supersedes row 17's tick) |
| No last-run figure under Units, Meters, Sub-meters, Behind the meter or Missing meter | Not provable from saved bills today (row 30) |
| No side panel behind any `See` on Who is billed | They filter Not in this run (row 42) |
| **No dead link** — every link opens a list, a tag, a panel, or a named screen in a new tab | Row 42; a test clicks every link on every step (plan T7) |
| No per-account problem on Scope | Scope checks the run, never an account (row 43) |
| No summary aside on Check | Step 2 is full width (row 36) |
| No run label separate from the run name | The clerk types the run name (row 14) |
| No sixth step, no separate "Review" or "Approve" step | Four steps (Billing blueprint p35) |

## 12 · Differences from the changes list, for the builder to carry (not fixed here)

- Row 36 names eight categories; the drawing has nine — **Payments & balances** is row 38's addition. Build nine.
- The drawing's Check has no tag for *reading without a unit* (row 23). It is a per-account blocking tag; put it under Readings.
- The drawing's Scope has no *bill date before the period ends* line; it is a refusal on the Bill date field (§2.1).
- Ten engine codes have no clerk label today (row 36); the drawn tag names are the source for their labels, chosen per code by the reads/engine lane.
