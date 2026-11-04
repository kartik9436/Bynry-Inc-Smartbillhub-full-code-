# One-time bill — screen inventory (D2, 2026-09-30)

The `react-tailwind-css-ui-generator` skill's §2.1–§2.5 inventory for **one product
page with four steps** (Account · Services · Review · Send), read from the PNGs in
this folder (B14 rule 42: the images are the spec). `mockup.html` was used only to
check spelling. Design record: `04-docs/05-modules/07-billing/11-one-time-bill-redesign.md`.
Build plan: `12-one-time-bill-build-plan.md` (F1–F18).

**How to read this file.**
- Strings in `code` are copied character for character from the drawing. Where the
  drawing shows UPPERCASE (kickers, column heads, pills), the **source string is in
  sentence case** and the capitals come from CSS — so the catalogue key holds
  `Billed · 2 meters`, not `BILLED · 2 METERS`.
- Every figure, name, meter number and date is **example data** (B14 rule 37). The
  shape is what gets built, not the numbers.
- Spacing, sizes, type and tokens come from **our UI standard, not the drawing**
  (B14 rule 44; rule 38 for forms). §2.4 below records the drawn rhythm only so a
  builder knows which kit spacing it corresponds to.
- "Kit" names a file in `07-frontend/src/components/`. **NEW** means nothing in the
  kit does it today and the build plan (F3–F14) adds it as a component (B14 rule 43),
  never as inline code in a page.

---

## 0 · Must NOT be built (mock-up chrome and mock-up faults)

| What | Where in the images | Why |
|---|---|---|
| The dashed strip `Design mock-up · example data` with `View:` `Walk through` `Compare kinds` and `State:` `Normal` `Problems on step 1` `Already billed` | Top of every PNG | A review control for the mock-up. The three states it switches are real product states reached by real data, not by buttons. |
| The **Compare kinds** view (`One-time bill · compare kinds`, the `Step 2 · what changes by kind` matrix, and six stacked step-2 blocks, each headed with the kind name and `Step 2 · Services · <need>`) | `*-37-compare-kinds.png` | A review aid for the PO, not a product screen. Its matrix is transcribed into §5 below as build knowledge only. (It also shows the kind cards and rail still drawn above it — a mock-up fault: `.kinds{display:grid}` beats `[hidden]`. Irrelevant, as the view is not built.) |
| **The Rates table's Amount column clipped** by its horizontal scroll box — the head reads `AMOUN`, the cells `$29.2`, `$21.9`, `$165.1` | Every step-2 Rates panel, at **both 1440 and 1280** (the mock-up caps its content at 1180px, so both widths draw the same clip) | A drawing flaw (README). **The build shows Amount in full.** |
| **The Readings table's Check column clipped** on First bill (`ACCEPTED` cut at the right edge) and meter numbers wrapping to `W-` / `10442` | `*-10-First-bill-2-services.png` (the extra `Move-in reading` input widens the table) | Same flaw, same fix: every column fully visible; meter numbers do not break. |
| `First bill bill · draft` in the Review bill header (kicker = kind name + ` bill`) | `*-12-First-bill-3-review.png` | A string-assembly fault in the mock-up. The build must not double the word. The kicker per kind is decided in the catalogue (e.g. `First bill · draft`). |
| The summary aside floating half-way down on Review | `*-05`, `*-12`, `*-17`, `*-22`, `*-27` | A sticky element captured mid-scroll in a full-page screenshot. The aside sits at the top of its column like every other step. |
| The `Draft saved · BL-2609-000318` replacement label on the Save draft button | mock-up script only, not drawn | Not drawn; the saved-draft confirmation is the kit's own toast/notice, not a relabelled button. |

---

## 1 · The frame — identical on all four steps and all six kinds

### 1.1 Page header (chrome)

| # | Element | String | Kit |
|---|---|---|---|
| 1 | Breadcrumb | `Billing › Bills` | `PageHeader.tsx` (crumb) |
| 2 | Title | `One-time bill` | `PageHeader.tsx` (32px, B14 rule 40) |
| 3 | Action, right, small, secondary | `Start over` | `Button.tsx` size `sm` in `PageHeader` actions |

No kicker above the title, no subtitle, no back arrow — see §6.

### 1.2 Kind cards (chrome; the choice is state)

Six equal cards in one row, each a button: **name** bold, **use** muted below.
The chosen one has the accent top rule and accent border.

| Order | Name | Use line |
|---|---|---|
| 1 | `Interim` | `Mid-cycle bill` |
| 2 | `First bill` | `Missed at move-in` |
| 3 | `Final` | `Move-out` |
| 4 | `Catch-up` | `Missed periods` |
| 5 | `Penalty / theft` | `Tamper or theft` |
| 6 | `Fee` | `One charge code` |

Kit: **NEW** `KindCards` (F3). Closest existing: `workflow/SourceCards.tsx`
(selectable cards) — reuse its pattern or generalise it; do not copy it.
Choosing a kind resets to step 1.

### 1.3 Step rail (chrome)

Four equal cells, full width, below the kind cards.

| # | Label | States drawn |
|---|---|---|
| 1 | `Account` | current: accent square with the numeral, bold label, accent bottom rule · done: black square with `✓` · todo: outlined square, grey label |
| 2 | `Services` | same (**label stays `Services` on Fee**, whose step 2 shows only a Charge panel) |
| 3 | `Review` | same |
| 4 | `Send` | same |

After **Sent**, all four are done (`✓`) and greyed (not doors).
Kit: `WizardFrame.tsx` rail (F2). ⚠ The live `oneTimeWizardChrome.tsx` draws a
**three**-step rail — it is replaced, not widened.

### 1.4 Two-column body

Left: the step's panels, stacked. Right: the **summary aside** (320px drawn) on
every step. Below ~960px the aside drops under the main column (drawn in CSS only).

### 1.5 Summary aside (data; kit: **NEW** `OneTimeSummary`, F14, built from `Panel.tsx`)

| # | Element | String / value | Notes |
|---|---|---|---|
| 1 | Kicker | kind name — `Interim`, `First bill`, `Final`, `Catch-up`, `Penalty / theft`, `Fee` | uppercase by CSS |
| 2 | Big figure | total, e.g. `$168.49` | `MoneyCell.tsx`, 2 dp |
| 3 | Row | `Charges` · `$165.19` | |
| 4 | Row | `Tax` · `$3.30` | |
| 5 | Row | `Lines` · `10` | count of bill lines |
| — | Rule | | |
| 6 | Row | `Bill date` · `Sep 30, 2026` | `DateCell.tsx` |
| 7 | Row | `Due` · `Oct 21, 2026` — **`—` while step 1 has problems** | |
| — | Rule | **(this block and its rule are ABSENT on Fee)** | |
| 8 | Row + pill | `Billed` · `4 services` (success) | `StatusPill.tsx` |
| 9 | Row + pill | `Not in service` · `2 · no line` (muted) | |
| 10 | Row + pill | `Not taken` · `1` (muted) | |
| 11 | Row + pill | `Warnings` · `1` (warning) | |
| 12 | Footnote | `Nothing saved yet.` → after Send: `Sent.` | |

Figures per kind in the example: Interim `$168.49` (charges `$165.19`, tax `$3.30`,
lines `10`) · First bill `$429.23` (`$424.64`, `$4.59`, `12`) · Final `$152.17`
(`$149.19`, `$2.98`, `10`) · Catch-up `$432.18` (`$423.71`, `$8.47`, `28`) ·
Penalty `$682.18` (`$673.71`, `$8.47`, `29`) · Fee `$76.50` (`$75.00`, `$1.50`, `1`).

### 1.6 Footer actions (chrome)

A rule, then Back on the left, the rest on the right. Kit: `Button.tsx`.

| Step | Left | Right (in order) |
|---|---|---|
| 1 Account | *(nothing)* | `Continue` (primary) |
| 2 Services | `Back` | `Continue` (primary) |
| 3 Review | `Back` | `Save draft` (secondary) · `Continue` (primary) |
| 4 Send | `Back` | `Save draft` (secondary) · `Send $168.49 bill` (**danger**, disabled until ticked) — inside the send card |
| 4 Sent | — | `View bill` (primary) · `New one-time bill` (secondary) — inside the sent card |

---

## 2 · Step 1 — Account

Panels in order: **Account → Period** (`Charge` on Fee) **→ Dates**, then the footer.

### 2.1 Account panel

| # | Element | String | Kind of thing | Kit |
|---|---|---|---|---|
| 1 | Panel heading | `Account` | chrome | `Panel.tsx` |
| 2 | Label, required | `Find account` `*` | chrome | `FormModal.tsx` `FieldLabel` |
| 3 | Searchable dropdown, caret `▾` on the right; placeholder `Type to search` | value = the chosen name, e.g. `Maria Alvarez` | data | **NEW** `AccountCombobox` (F4). Build on `RemoteSearchSelectField.tsx` / `features/customers/accountFinder.tsx` (server search, min 2 chars) rather than beside them |
| 4 | Help | `Name, account no. or address.` | chrome | field help |
| 5 | Result card (grey fill, 4 × 2 grid of label over value) | see below | data | `FactBlock.tsx` variant `card` |

Result card, reading order (row 1 then row 2):

| Label | Example value | Notes |
|---|---|---|
| `Customer` | `Maria Alvarez` | |
| `Account` | `AC-2026-00042` | account **number**, never an id (B14 rule 31) |
| `Address` | `1408 Elm St · Unit A` | derived from premises + unit label (hard rule 8) |
| `Plan` | `Residential Standard` | |
| `Status` | pill `Active` (success) | `StatusPill.tsx` |
| `Balance` | `$142.18` | `MoneyCell.tsx` |
| `Cycle` | `Monthly · 21 days` | |
| `Last bill` | `Aug 31, 2026` | |

**Dropdown open** (`*-02-Interim-1-account-dropdown-open.png`): the input takes the
accent focus ring, typed `Alv`; a list overlays the panels below. Each option:
name (bold) with the matched text in accent-ink bold, status pill on the right,
second line `<account no.> · <address>` muted. The keyboard-highlighted option has
the accent-soft fill. Drawn options:

| Name | Pill | Second line |
|---|---|---|
| `Maria Alvarez` | `Active` (success) | `AC-2026-00042 · 1408 Elm St · Unit A` |
| `Luis Alvarez` | `Active` | `AC-2026-00117 · 22 Birch Ct` |
| `Alvarez Hardware LLC` | `Active` | `AC-2026-00388 · 900 Main St · Suite 2` |
| `Maria Alvarez` | `Closed` (muted) | `AC-2025-01904 · 61 Oak Ave` |

Empty result (mock-up source, not drawn): `No account found.`
Two customers with the same name are told apart only by number and address — the
option must always show both.

### 2.2 Period panel — varies by kind

| Kind | Heading | Fields (in order) |
|---|---|---|
| Interim | `Period` | `From` `*` date · `To` `*` date (two of three columns; third empty) |
| First bill | `Period` | `Move-in date` `*` date, **read-only (grey)**, help `From the account.` · `To` `*` date |
| Final | `Period` | `From` `*` date · `Move-out date` `*` date |
| Catch-up | `Period` | periods list (below) · `Reason` `*` select |
| Penalty / theft | `Period` | periods list · `Reason` `*` select · `Charge code` select, help `Optional. Amount from the code.` (Reason and Charge code side by side) |
| Fee | `Charge` | `Charge code` `*` select (two columns wide), help `Amount comes from the code.` |

**Periods list** (Catch-up, Penalty): label `Missed periods` `*`, then one row per
period: `From` date · `To` date · `Remove` (small secondary). Drawn with three rows
(`06/01/2026`–`06/30/2026`, `07/01/2026`–`07/31/2026`, `08/01/2026`–`08/31/2026`).
Under the rows: `Add period` (small secondary), then help `3 months · limit 12`
(the count is live). Kit: **NEW** periods list inside F5; `TableArray.tsx` is the
closest existing add/remove-rows pattern — check it first.

Select option strings (mock-up source):
- Reason, Catch-up: `Choose a reason` · `Missed billing cycle` · `Meter fault found`
- Reason, Penalty: `Choose a reason` · `Theft of service` · `Meter tampering`
- Charge code, Fee: `Choose a charge` · `Reconnection fee · $75.00` · `Returned payment · $30.00` · `Meter test · $40.00` · `Tamper charge · $250.00`
- Charge code, Penalty: `Choose a charge` · `Tamper charge · $250.00`

All option lists come from Settings (reason codes, charge codes) — never typed in the
page (skill §12). Kit: `FormModal.tsx` `SelectField`, `DatePickerField`.

### 2.3 Dates panel — same on every kind

| # | Label | Control | Help |
|---|---|---|---|
| 1 | `Bill date` `*` | date | — |
| 2 | `Days to pay` `*` | number | `From the cycle. Change if needed.` |
| 3 | `Due date` | read-only (grey), e.g. `Oct 21, 2026`; `—` when it cannot be derived | — |

Kit: `DatePickerField`, `TextField`, a read-only field per `fieldErrorEmptyAndReadOnly`.

---

## 3 · Step 2 — Services

Section order is ruled (PO 2026-09-30): **Services → Rates → Move-in charges → Readings**,
then Periods / Settlement / Evidence / Charge as the kind needs. The first three
**collapse**; they are open by default. Collapsed state (`*-04`, `*-11`, `*-16`,
`*-21`, `*-26`): only the heading row shows — heading, right-hand summary, chevron
button (`▼` collapsed, `▲` open). Readings and later panels do not collapse.

### 3.1 Services panel (collapsible) — every kind except Fee

Header: heading `Services`; right: summary `4 billed · 2 not in service · 1 not taken`
(uppercase by CSS) + chevron.
Kit: `Disclosure.tsx` variant `section` (or `card`) holding a `Surfaces.tsx`
`PlainTable`; **NEW** `ServicesTable` (F6).

| Column (in order) | Align | Content |
|---|---|---|
| `Service` | left | colour square + service name (bold) |
| `Asset` | left | text |
| `Status` | left | pill |
| `On the bill` | left | text |

Rows drawn (same on all five kinds):

| Service | Asset | Status pill (tone) | On the bill | Row |
|---|---|---|---|---|
| `Water` | `2 meters · W-10442, W-10443` | `Billed · 2 meters` (success) | `2 lines · usage + base each` | normal |
| `Electric` | `Meter E-55120` | `Billed · base $0.00` (warning) | `Usage + $0.00 base` | normal |
| `Trash` | `1 cart · 96 gal` | `Billed · 1 cart` (success) | `Cart × rate + base per cart` | normal |
| `Sewer` | `No asset needed` | `Billed · follows water` (info) | `40% of water + base` | normal |
| `Gas` | `No meter` | `Not in service` (muted) | `No line · $0` | greyed |
| `Fire` | `No asset` | `Not in service` (muted) | `No line · $0` | greyed |
| `Broadband` | `Router R-2201` | `Not taken` (muted) | `No line` | greyed |

Status vocabulary (five shapes): `Billed · <n> meters` / `Billed · <n> cart` (count) ·
`Billed · base $0.00` · `Billed · follows water` · `Not in service` · `Not taken`.
Under the table, when any warning: a warning note — bold `1 warning.` then
`No base charge for Electric. Billed $0.00.` Kit: `WarningBox.tsx` tone `soon`, or
`TextBits.tsx` `Note` — check which the kit uses for a non-blocking amber note.

Service colour squares come from the service's own token (Water blue, Electric red,
Trash green, Sewer grey, Gas amber, Fire dark red) — the map is
`serviceBadge(code).token` (`--color-service-*` tokens), as `ServiceChips.tsx` uses it;
do not hand-type a second one (CLAUDE.md, eleven services).

### 3.2 Rates panel (collapsible) — every kind except Fee

Header: `Rates`; right: `<Plan> · <before-tax>` e.g. `Residential Standard · $165.19`;
Catch-up and Penalty: `Residential Standard · per period · $423.71`. Chevron.
Kit: `Disclosure` + `PlainTable`; **NEW** `RatesTable` (F7).

| Column (in order) | Align |
|---|---|
| `Service / meter` | left (colour square + bold) |
| `Rate type` | left |
| `Usage rate` | left |
| `Base charge` | left |
| `Minimum` | left |
| `Price version` | left |
| `Amount` | **right** — ⚠ clipped in the drawing, **must show in full** |

| Service / meter | Rate type | Usage rate | Base charge | Minimum | Price version |
|---|---|---|---|---|---|
| `Water · W-10442` | `Tiered` | `$3.25 / kgal to 5 kgal` / `$4.50 / kgal above` (two lines) | `$8.00 · BASE-W` | `None` | `Water v4` |
| `Water · W-10443` | `Tiered` | same | `$8.00 · BASE-W` | `None` | `Water v4` |
| `Electric · E-55120` | `Flat` | `$0.1245 / kWh` | pill `Not set · $0.00` (warning) | `None` | `Electric v7` |
| `Trash · 1 cart` | `Per asset` | `$15.00 / cart` | `$3.00 per cart · BASE-T` | `None` | `Trash v2` |
| `Sewer` | `% of service` | `40% of water usage` | `$6.00 · BASE-S` | `$10.00` | `Sewer v3` |
| `Gas · no meter` (greyed) | `No rate used` spanning five columns | | | | amount `$0.00` |
| `Fire · no asset` (greyed) | `No rate used` | | | | `$0.00` |
| Total row (grey): `Before tax` | | | | | amount right |

By kind:
- **Final:** base charges read `$8.00 · BASE-W · prorated 18/30`, `$6.00 · BASE-S · prorated 18/30` (trash's base is not marked prorated in this table but is prorated on the bill).
- **Catch-up / Penalty:** Water price version reads `Water v3 →` / `Water v4` plus info pill `Split Aug 15`.

One row per **meter** for metered services and one per **service** otherwise (PO 2026-09-30, two meters = two lines).

### 3.3 Move-in charges panel (collapsible) — First bill only

Header: `Move-in charges`; right: `Deposit + fees · $195.00`; chevron.

- Three fact tiles in a row: `Move-in date` `Sep 12, 2026` · `Deposit asked` `$150.00` · `Already paid` `$0.00`. Kit: `FactBlock.tsx` (card).
- Table (`PlainTable`): `Charge` · `Type` · `Basis` · `Amount` (right).

| Charge | Type | Basis | Amount |
|---|---|---|---|
| `Security deposit` | `Deposit` | `$150.00 asked − $0.00 paid` | `$150.00` |
| `Connection charge` | `Fee` | `Code CONN` | `$45.00` |
| **`Move-in total`** (grey total row) | | | `$195.00` |

Kit: **NEW** `MoveInChargesPanel` (F8).

### 3.4 Readings panel — every kind except Fee (not collapsible)

Header: `Readings`; right: a pill naming what is needed:

| Kind | Pill (tone) |
|---|---|
| Interim | `Needed · every meter` (info) |
| First bill | `Needed · move-in + new` (info) |
| Final | `Needed · final reading` (info) |
| Catch-up | `Needed · last period only` (info) |
| Penalty / theft | `Not needed` (muted) |

**Single-window form (Interim, First bill, Final)** — one table, one row per meter.
Kit: `EditableTable.tsx` or `TableArray.tsx` (inputs in cells); **NEW** `ReadingsTable` (F9).

| Column | Interim | First bill | Final | Align |
|---|---|---|---|---|
| 1 | `Meter` | `Meter` | `Meter` | left — colour square, meter no. bold, unit (`kgal`, `kWh`) muted below |
| 2 | `Previous` | `Move-in reading` | `Last billed` | right |
| 3 | `Read on` | `Read on` | `Read on` | left (date) |
| 4 | `New read date` (date input) | `New read date` (date input) | `Move-out date` (**fixed text**, e.g. `Sep 18, 2026`) | left |
| 5 | `New reading` `*` (input) | `New reading` `*` (input) | `Final reading` `*` (input) | left |
| 6 | `Usage` | `Usage` | `Usage` | right, value + unit, e.g. `6.1 kgal` |
| 7 | `Check` | `Check` | `Check` | pill |

First bill, meter with no move-in reading on file (`W-10443`): the Move-in reading
cell is an **input** (`128.9`) with warning pill `None on file` under it.
First bill `Read on` = the move-in date (`Sep 12, 2026`).

Check pill values: `Accepted` (success) · `Below last reading` (danger; the reading
input turns red, Usage shows `—`) · `Waiting` (muted, no reading yet). Only
`Accepted` is drawn; the other two are in the mock-up source.

Under the table: `Saved to Meter Reads. Multi-register meter?` then link
`Use full readings screen` (kit: `Surfaces.tsx` `InlineLinkTo`).

**Per-period form (Catch-up, Penalty)** — one block per missed period, each with a
sub-heading `Jun 1, 2026 – Jun 30, 2026` and its own table. Catch-up's **last**
period sub-heading carries info pill `Enter reading`.

| Column | Align | Catch-up | Penalty |
|---|---|---|---|
| `Meter` | left | colour square + meter no. | same |
| `Start reading` | right | figure | figure |
| `Start date` | left | date | date |
| `End reading` | right | figure; `—` where estimated; **input on the last period** | figure |
| `End date` | left | date; **date input on the last period** | date |
| `Usage` | right | e.g. `3.1 kgal` | same |
| `Reading` | left | pill `Actual` (success) / `Estimated` (warning) | pill `Assessed` (warning) on every row |

Footnote: Catch-up `Saved to Meter Reads. Earlier gaps are estimated.` · Penalty
`Assessed reads come from Meter Reads.` Penalty has no inputs at all.

### 3.5 Periods panel — Catch-up and Penalty

Header: `Periods`; right kicker `3 periods`. Kit: `Panel` + `PlainTable`; F10.

| Column | Align | Example |
|---|---|---|
| `Period` | left | `Jun 1, 2026 – Jun 30, 2026` |
| `Days` | right | `30` |
| `Price version` | left | `Water v3 · Elec v7`; split period `Water v3 → v4 · Elec v7` |
| `Reading` | left | pill `Actual` / `Estimated` (Catch-up) · `Assessed` (Penalty) |
| `Note` | left | `—`, or info pill `Split Aug 15 · price change` |

### 3.6 Settlement panel — Final only

Header: `Settlement`; right kicker `Deposit applied first`. Kit: `RecapBox.tsx`
(label→value `<dl>` with a bold outcome row) — or `PlainTable`; F10.

| Row | Example |
|---|---|
| `This final bill` | `$152.17` |
| `Balance brought forward` | `$142.18` |
| `Deposit held` | `−$100.00` |
| `Deposit interest` | `−$1.24` |
| **`Left to pay`** (grey total; reads **`Refund due`** when negative) | `$193.11` |

Then a radio group, legend `How to settle` (kicker style): `Collect` (default) ·
`Payment plan` · `Move to landlord account`. Kit: `SegmentedField` or a radio group
from `FormModal.tsx` — check which is the kit's single-choice control (rule 38).

### 3.7 Evidence panel — Penalty only

Header: `Evidence`. Two fields side by side:
- `What was found` — textarea (example `Bypass fitted at meter E-55120. Photos taken Aug 29.`)
- `Photos or report` — file picker, help `Optional.` (kit: `FileField.tsx` / `FileDropField.tsx`)

Then an info note `Needs approval before it is sent.` (kit: `TextBits.tsx` `Note` / `Panel` tone `info`).

### 3.8 Charge panel — Penalty (last) and Fee (only content)

Header: `Charge`; right kicker `Optional` (Penalty) · `No usage` (Fee).
Table: `Code` · `Charge` · `Amount` (right) · `Tax`.

| Kind | Code | Charge | Amount | Tax |
|---|---|---|---|---|
| Penalty | `TAMPER` | `Tamper charge` | `$250.00` | `None` |
| Fee | `RECON` | `Reconnection fee` | `$75.00` | `Taxable · 2.00%` |

Fee only: field `Note on the bill` (text input, example
`Reconnected Sep 30 after non-payment cut`).

---

## 4 · Step 3 — Review

Panels: **The bill → Delivery**, then the footer (`Back` · `Save draft` · `Continue`).

### 4.1 The bill panel

Header: `The bill`; right kicker `As it will print`.
Inside, a bordered bill block. Kit: **NEW** `BillPreview` (F11) using `PlainTable`.

Bill head (thick rule under it):

| Left | Right (label · value pairs) |
|---|---|
| kicker `<Kind> bill · draft` (e.g. `Interim bill · draft`) | `Bill date` · `Sep 30, 2026` |
| customer name, large bold `Maria Alvarez` | `Due date` · **`Oct 21, 2026`** (bold) |
| `AC-2026-00042 · 1408 Elm St · Unit A` (muted) | `Period` · `Sep 1, 2026 – Sep 30, 2026` — **absent on Fee** |

Table columns:

| Column | Align |
|---|---|
| `Service` | left — colour square + service name (regular weight), or the charge name for non-service lines |
| `Meter / asset` | left — meter no., `1 cart`, or `—` |
| `Charge` | left — `Usage` · `Base` · `Per cart` · `Base · per cart` · `40% of water` · `Deposit` · `Fee · CONN` · `Fee · RECON` · `Fee · TAMPER`; Final adds ` · prorated 18/30` to base lines |
| `Quantity` | right — `6.1 kgal`, `610 kWh`, `1 cart`, `1`, a money base for sewer (`$35.18`), `—` |
| `Rate` | right — `Tiered`, `$8.00`, `$0.1245`, `40%`, `Not set` |
| `Amount` | right |

Rows are **grouped**; each group has a grey group-heading row (name left, uppercase
by CSS; group subtotal right). Pills inline in `Charge`: `No base set` (warning) on
the $0 electric base line; `Est.` (warning) on an estimated usage line (Catch-up).

| Kind | Groups, in order |
|---|---|
| Interim | `Sep 1 – Sep 30` (all 10 lines, the $0 electric base last) |
| First bill | `Sep 12 – Sep 30` · `Move-in charges` (`Security deposit` · `Deposit`; `Connection charge` · `Fee · CONN`) |
| Final | `Sep 1 – Sep 18` |
| Catch-up | `Jun 2026` · `Jul 2026` · `Aug 2026` · `Standing` (the $0 electric base) |
| Penalty / theft | `Jun 2026` · `Jul 2026` · `Aug 2026` · `Standing` · `Other charges` (`Tamper charge` · `Fee · TAMPER`) |
| Fee | `Charges` (`Reconnection fee` · `—` · `Fee · RECON` · `1` · `$75.00` · `$75.00`) |

Foot rows (muted): `Subtotal` · amount; `Utility tax · 2.00% of taxable charges` ·
amount; then grey bold total row `Total due` · amount. (The 2.00% is example data —
the rate comes from the tenant's tax setting.)

Under the bill block, when any warning: the same warning note as §3.1 — `1 warning.`
`No base charge for Electric. Billed $0.00.` (absent on Fee).

### 4.2 Delivery panel

Heading `Delivery`; one field `Send by` — select, options
`Email · m.alvarez@example.com` (drawn truncated `Email · m.alvarez@example.c`) ·
`Paper` · `Email and paper`. Kit: `SelectField`. ⚠ The drawn select truncates the
address; the build must fit it or wrap it, never cut it.

---

## 5 · Step 4 — Send, and Sent

### 5.1 Send card (one panel with a heavy black top rule)

| # | Element | String / value | Kit |
|---|---|---|---|
| 1 | Kicker, left | `<Kind> bill · <account no.>` e.g. `Interim bill · AC-2026-00042` | `TextBits` `Kicker` |
| 2 | Name | `Maria Alvarez` | |
| 3 | Address | `1408 Elm St · Unit A` (muted) | |
| 4 | Right, kicker | `Total due` | |
| 5 | Right, big figure | `$168.49` | `MoneyCell` |
| 6 | Right, muted | `Due Oct 21, 2026` | |
| 7 | Facts table (label left, value right) | `Bill date` `Sep 30, 2026` · `Days to pay` `21` · `Lines` `10` · `Send by` `Email` · `Warnings` pill `1 · Electric base $0.00` (warning) — or pill `None` (success) on Fee | `RecapBox.tsx` |
| 8 | Penalty only: info note | `Approved by R. Chen · Sep 30` | `Note` / info panel |
| 9 | Danger note | bold `Final once sent.` then `Changes need a credit note.` | `ConsequenceBox.tsx` (check tone) or `OutcomeCard` `danger` — B14 rule 33 consequence, ≤ 6 words per sentence, already met |
| 10 | Checkbox | `I checked the amounts` | `FormModal.tsx` `CheckboxField` |
| 11 | Footer, inside the card | `Back` · `Save draft` · `Send $168.49 bill` | `Button` — **danger tier**, disabled (faded) until ticked (`*-06`), live when ticked (`*-07`) |

### 5.2 Sent (`*-08-Interim-4-sent.png`)

Rail: all four `✓`, greyed. The card:

| # | Element | String |
|---|---|---|
| 1 | Green square with white `✓` | — |
| 2 | Heading | `Bill BL-2609-000318 sent` (bill **number**, never an id) |
| 3 | Rows | `Total` `$168.49` · `Due` `Oct 21, 2026` · `Delivery` `Email · queued` · `Meter reads` `Locked` |
| 4 | Actions | `View bill` (primary) · `New one-time bill` (secondary) |

Aside footnote becomes `Sent.` Kit: `OutcomeCard.tsx` tone `success` + `RecapBox`.

---

## 6 · States

| State | Image | What changes |
|---|---|---|
| Dropdown open | `*-02` | §2.1 |
| Sections collapsed | `*-04`, `*-11`, `*-16`, `*-21`, `*-26` | §3 — Services, Rates, Move-in charges show header only; chevron `▼` |
| Send unticked / ticked | `*-06` / `*-07` | Send button disabled / live |
| Sent | `*-08` | §5.2 |
| **Problems on step 1** | `*-33` Interim · `*-34` Catch-up · `*-35` Fee | A red summary box **above the Account panel** (main column only): bold `Fix <n> things to continue.` then a bullet list. Each problem is **also on its field**: the input turns red-tinted with a red message under it. Due date shows `—` in the field and in the aside. |
| **Already billed** | `*-36` | A red banner **full width, between the rail and the two columns**: bold `Already billed for this period.` then `BL-2609-000211 · Sep 18, 2026 · by J. Ortiz.` then link `Open that bill`. Drawn on step 2; the rest of the page is unchanged. |

Problem sets drawn (list text · field message):

| Kind | Summary list | Field messages |
|---|---|---|
| Interim (and First / Final) | `The period ends before it starts.` · `Enter days to pay.` | To: `Ends before it starts.` · Days to pay: `Enter days to pay.` |
| Catch-up (and Penalty) | `Period 2 ends before it starts.` · `Choose a reason.` · `Enter days to pay.` | period-2 To: `Ends before it starts.` · Reason (shows `Choose a reason`): `Choose a reason.` · Days to pay |
| Fee | `Choose a charge code.` · `Enter days to pay.` | Charge code (shows `Choose a charge`): `Choose a charge code.` · Days to pay |

Kit: `StateFrame.tsx` `FormErrorSummary` + `FieldError` (+ `INVALID_INPUT_CLASS`);
`Surfaces.tsx` `RefusalStrip` for the already-billed banner. Help text stays visible
above the error message (`From the cycle. Change if needed.` then `Enter days to pay.`).

**Not drawn, and the build still owes them (skill §2.2, §8 `StateFrame`):** loading
(account search, step 2's services/rates/readings, the bill preview), a failed load
with retry, a server refusal on Save draft / Send, permission denied, an account
with **no** billable services, and the empty combobox. Use the `StateFrame` kit;
do not invent copy beyond rule 33's caps.

---

## 7 · Which sections appear per kind (built sections only)

| Section | Interim | First bill | Final | Catch-up | Penalty / theft | Fee |
|---|---|---|---|---|---|---|
| **Step 1** Account panel | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Period: From / To | ✔ | Move-in (read-only) / To | From / Move-out | — | — | — |
| Period: missed periods list | — | — | — | ✔ | ✔ | — |
| Reason | — | — | — | ✔ | ✔ | — |
| Charge code (step 1) | — | — | — | — | optional | required (panel titled `Charge`) |
| Dates panel | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| **Step 2** Services (collapsible) | ✔ | ✔ | ✔ | ✔ | ✔ | — |
| Rates (collapsible) | ✔ | ✔ | ✔ prorated base | ✔ per period, split | ✔ per period, split | — |
| Move-in charges (collapsible) | — | ✔ | — | — | — | — |
| Readings | per meter | per meter, move-in + new | per meter, final | per period, last entered | per period, read-only, Assessed | — |
| Periods | — | — | — | ✔ | ✔ | — |
| Settlement | — | — | ✔ | — | — | — |
| Evidence | — | — | — | — | ✔ | — |
| Charge (step 2) | — | — | — | — | ✔ optional | ✔ only content |
| **Step 3** bill groups | 1 period | period + Move-in charges | 1 period, prorated | per month + Standing | per month + Standing + Other charges | Charges |
| Bill head `Period` row | ✔ | ✔ | ✔ | ✔ | ✔ | — |
| Warning note | ✔ | ✔ | ✔ | ✔ | ✔ | — |
| **Step 4** approval note | — | — | — | — | ✔ | — |
| Warnings pill | `1 · Electric base $0.00` | same | same | same | same | `None` |
| Aside services block | ✔ | ✔ | ✔ | ✔ | ✔ | — |

Previous-reading source and read-date rule by kind (from the compare matrix, for the
builder): Interim *Last on file*, clerk date · First *Move-in (typed if none)*, clerk
date · Final *Last billed*, move-out date fixed · Catch-up *Period start*, last period
only · Penalty *Period start*, no date entered.

---

## 8 · Chrome vs data (skill §2.2)

| Element | Chrome / data | Empty · long · failed |
|---|---|---|
| Header, kind cards, rail, panel headings, column heads, button labels, help lines | chrome | — |
| Kind card use lines | chrome (catalogue) | — |
| Account options / result card | data | no match → `No account found.`; long name/address wraps (never truncates the number); search failure → `StateFrame` failed |
| Services rows | data | an account with 11 services draws 11 rows; none billable → a stated state, not an empty table |
| Rates rows | data | one row per meter; many meters → many rows; Amount always visible |
| Readings rows / period blocks | data | Catch-up **limit 12** periods → up to 12 blocks × meters |
| Bill lines | data | 29 lines on Penalty's example; grows with periods × meters — no pagination inside a bill preview, but the page must not clip it |
| Summary figures, pills, counts | data | `—` where not derivable (Due with problems) |
| Warning note text | data (count + per-service sentence) | absent when 0 warnings; plural when >1 |
| Delivery options | data (customer's email) | no email on file → options without email |
| Bill number on Sent | data | server-issued |

---

## 9 · Repetition (skill §2.3) — build once, use many

| Repeated thing | Appears in | Component |
|---|---|---|
| Panel with heading + right-hand kicker/pill | every panel | `Panel.tsx` (`title`, `trailing`) |
| Collapsible panel with summary + chevron | Services, Rates, Move-in charges | `Disclosure.tsx` |
| Small in-panel table with grey header, grey total row | Services, Rates, Move-in, Readings, Periods, Settlement, Charge, bill | `Surfaces.tsx` `PlainTable` |
| Colour square + service name | Services, Rates, Readings, bill | `serviceBadge(code).token` swatch, as in `ServiceChips.tsx` |
| Status pill (success / warning / info / muted / danger) | everywhere | `StatusPill.tsx` |
| Warning note `1 warning.` … | Services, Review | one note component |
| Label → value rows | aside, Send facts, Sent, Settlement | `RecapBox.tsx` |
| Field (label, `*`, control, help, error) | step 1, Evidence, Delivery, Fee note | `FormModal.tsx` fields |
| Period sub-block with its own table | Readings (Catch-up, Penalty) | one `PeriodReadings` inside F9 |
| `Back` / `Continue` footer | every step | `WizardFrame.tsx` footer |
| Kind name → kicker/label | aside kicker, bill kicker, send kicker | one kind→label map, catalogue-backed |

---

## 10 · Rhythm (skill §2.4) — drawn, then mapped to our scale

The drawing already uses a 4px scale (its own header says so). Build with the kit's
tokens (rule 44); these are recorded only to show there is no odd value to chase.

| Where | Drawn |
|---|---|
| Page column gap (header → cards → rail → body) | 20px |
| Main column panel gap / main-to-aside gap | 20px |
| Panel padding / gap inside a panel | 20px / 16px |
| Kind-card gap | 8px; card padding 12px |
| Field grid | 3 columns, 16px gap; label → control 4px |
| Table cells | 8×12 header, 10×12 body |
| Rail cell | 12×16, numeral box 24px |
| Buttons | default 40px high; small 30px |
| Type | title 32 · panel heading 20 · card/rail label 14 · body 13–15 · kicker/pill/column head 11 uppercase |
| Aside width | 320px |

---

## 11 · What is ABSENT (skill §2.5) — decisions, not gaps

- No page-level kicker, subtitle or back arrow in the header; `Start over` is the only header action.
- No `Cancel` in the wizard footer; leaving is `Start over` or the app's own navigation.
- No step-1 `Back` (left slot empty).
- No row actions, no toolbar, no search, no pagination, no export on any table — they are in-panel figure tables, not list tables.
- No editing of rates, prices, base charges or services on this page — Rates is read-only; a missing base is a warning, not a field.
- No per-row delete/skip of a service; not-in-service and not-taken rows are shown, never hidden, and never billed.
- No reading inputs for Gas, Fire, Trash, Sewer or Broadband — only meters get rows.
- No reading inputs at all on Penalty; on Catch-up only the last period is editable.
- No settlement write-off option drawn (the design record lists *write-off*; the drawing offers `Collect` · `Payment plan` · `Move to landlord account` only) — **say so to the builder; do not add it.**
- No `Period` row on a Fee bill; no Services / Rates / Readings / aside-services block on Fee.
- No approval control on this page — Penalty shows who approved (`Approved by R. Chen · Sep 30`) and Evidence says it `Needs approval before it is sent.`; the approval act lives elsewhere.
- No tax editing; the tax line is computed.
- No print/PDF button on Review (`As it will print` is a label); `View bill` exists only after Sent.
- No explanation of why sections exist (rule 33: rationale is zero words).

---

## 12 · Differences from the design record, for the builder to carry (not fix here)

| Drawing | `11-one-time-bill-redesign.md` | Note |
|---|---|---|
| Tax `2.00%`; Fee `Taxable · 2.00%` | Fee tax answered at 8.25% example | Rule 37 — both are illustrations; the rate is the tenant's. |
| Settlement: Collect · Payment plan · Move to landlord account | … refund / left to pay / **write-off** | Write-off not drawn (§11). |
| Rail label `Services` on Fee | Step 2 = Services | Drawn this way; keep one word per step. |
| Trash base in Final's Rates not marked prorated; bill line is | — | Mock-up inconsistency; the bill line is the truth. |
