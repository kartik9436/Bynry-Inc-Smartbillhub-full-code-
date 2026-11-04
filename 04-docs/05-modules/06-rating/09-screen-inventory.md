# Plans & Rates — THE screen inventory (PO, 2026-08-20)

**Status: CONFIRMED against r10 source + against six browser screenshots the PO
supplied on 2026-08-20.** This file is the ticket vocabulary for CR-013. Nothing
in the repo held a screen list for this module before it — `08-cr013-design.md`
is a resolution argument, `07-r10-plans-rates-readout.md` reads out the drawing,
and A1's `S9` still describes the **r9** landing with **four** tabs and no
Discounts. A lane asking "how many screens is Plans & Rates" had no answer.

## The count, in the PO's words (verbatim, 2026-08-20)

> there are these many screen from r10 - 13 screens in Plans & Rates. Counted
> from the actual view states in the file.
> So: 1 landing (5 tabs) + 3 details + 5 wizards + 1 adjacent = 10 routes / 13
> distinct views.

**Verified. The arithmetic and every step count are right.** Evidence per row below.

## 1 · Landing — one route, five tabs

`planRatesTab ∈ plans | rates | charges | discounts | taxes` (10356-10363,
10473-10475). One route, tab-switched, as the PO says.

| View | Tab | Emitted ID | Primary button | Evidence |
|---|---|---|---|---|
| PLN-01 | Plans (default) | `PLN-01` | `+ New plan` | 8873, 9211, screenshot |
| — | Rate schedules | **`RAT-01`** | `+ New rate schedule` | 9211, screenshot |
| — | Charge codes | `PLN-01.charges` | `+ New charge code` | 9211, screenshot |
| — | Discounts | `PLN-01.discounts` | `+ New discount` | 9211, screenshot |
<!-- BUILT 2026-08-21 (CR-013 part 3, §18 row 10). The tab renders in this exact
     position, the `+ New discount` button is drawn DISABLED with its reason
     because DIS-02 (row 12) does not exist, and the route resolves to
     `PLN-01.discounts` through `screenIds.ts`'s existing `subIdFrom` rule with
     no new baseline entry. -->
| — | Taxes & fees | `PLN-01.taxes` | `+ New tax or fee` | 9211, screenshot |

⚠ **The ID scheme is inconsistent and that is r10's, not ours**: four tabs are
`PLN-01.<tab>` and the fifth is a top-level `RAT-01`. All five badges were read
off the running canvas, so this is behaviour, not a mapping we can quietly fix.

The counts strip under the H1 (`6 plans · 7 rate schedules · 13 charge codes ·
5 discounts · 6 taxes & fees · effective Aug 1, 2026`) is **identical on all five
tabs** — it summarises the module, not the tab.

## 2 · Detail pages — 3 screens, and the third serves three object types

| View | Route state | **Emitted ID** | Tabs | Evidence |
|---|---|---|---|---|
| PLN-02 plan detail | `prView: 'plan'` | **`PLN-plan`** | 8 | 10372, screenshot |
| RAT-02 rate detail | `prView: 'rate'` | **`PLN-rate`** | 5 | 10370-10371, screenshot |
| CHG-03 definition detail | `prView: 'cd'` + `cdKind` | **`CHG-01`** | 5 / 5 / 6 | 10477, 10515-10516, 10561 |

**The emitted IDs are not the specified IDs for the first two.** r10's mapping
expects `prView === 'pl'` → `PLN-02` and `prView === 'rd'` → `RAT-02`; the
handlers set `'plan'` and `'rate'`, so the badge reads `PLN-plan` and `PLN-rate`.
Predicted from source in `07-r10-plans-rates-readout.md` §2 and **now confirmed
visually** — both screenshots show the wrong badge. A walkthrough cannot be
evidenced by screen ID on these two; use route + `<h1>` text.

**The shared shell is real.** `openChargeDetail`, `openTaxDetail` and
`openDiscDetail` all set `prView:'cd'` and differ only by `cdKind`
(`charge|disc|tax`); the body reads `const d = CD[s.cdKind] || CD.charge` (10561).
All three screenshots — Water base service, Senior discount, Bexar County local
tax — carry the badge **`CHG-01`**. One screen, three kinds.

### The detail shell, in eight parts (identical across all five details)

1. `← Plans & Rates` back link, accent, bold.
2. Uppercase accent eyebrow, `·`-separated, ending in the version:
   `PLAN · RES-STD · V2` · `RATE SCHEDULE · WATER · TIERED · V3` ·
   `CHARGE CODE · BASE-W · RECURRING · V2` · `DISCOUNT · SENIOR · PERCENT OVERLAY · V2` ·
   `TAX · LOCAL · BEXAR COUNTY · V1`.
3. `<h1>` object name.
4. Muted sub-line: effective range, GL, and the policy note.
5. Right cluster: status pill, then **`Duplicate` · `<middle>` · `Retire`**.
   **The plan is the exception** — its middle button is `Edit as new version`
   with **no pencil glyph**; the other four are `✏ Edit` (`✏ Edit rates` on the
   rate schedule). The plan's sub-line explains it: *"composition edits run
   through Edit as new version"*.
6. **Exactly four KPI tiles**, hairline-divided. Tile 1 is always the reach
   ("who uses this"); tile 4 is the object's defining characteristic and is
   **text, not a number**, on three of the five:

   | | 1 | 2 | 3 | 4 |
   |---|---|---|---|---|
   | Plan | ACCOUNTS 842 · *781 inside · 61 outside ×1.5* | JULY REVENUE $68,420 | SERVICES 3 · *E · W · S* | EXCEPTIONS 2 · *1 waiver · 1 tax exemption* |
   | Rate | ACCOUNTS 914 | PLANS 2 | SIZES 5 | JULY REVENUE $127,240 |
   | Charge | PLANS CARRYING IT 4 | BILLS LAST MONTH 915 | MONTHLY REVENUE $11,948 | BASIS **Per size** |
   | Discount | PLANS USING IT 1 | ENROLLED ACCOUNTS 72 | PROGRAM COST / MO $930 | TYPE **% of subtotal** |
   | Tax | PLANS IT TOUCHES 5 | TAXABLE BASE / MO $294,600 | COLLECTED / MO $5,892 | RATE 2.00% |

   Only the plan's tiles carry the small caption line.
7. Underlined tabs — **8 · 5 · 5 · 5 · 6**, exactly as `07-...-readout.md` §3
   recorded from source:
   * Plan: Overview · Rate schedules · Base rates · Charges · Taxes · Discounts · Eligibility · Versions
   * Rate: Overview · Rate matrix · Billing rules · Plans · Versions & filings
   * Charge: Overview · Amounts · Applicability · Plans · Versions
   * Discount: Overview · Value & rules · Applicability · Plans · Versions
   * Tax: Overview · Rate & basis · Applicability · Plans · Remittance & filings · Versions
8. Overview body: grey panels, each headed by an uppercase accent label.
   Plan → `WHAT THIS PLAN IS` then `SAMPLE BILL · …`. Rate → `STRUCTURE` (with a
   **three-bar tier chart**, value above each bar, band caption below) then
   `SAMPLE BILL · …`. Charge / discount / tax → **`WHAT THIS IS` and nothing
   else** — those three Overviews are one panel deep.

## 3 · Wizards — 5 screens

| View | Steps | State var | Evidence |
|---|---|---|---|
| PLN-03 New/Edit Plan | **8** | `planWizStep`, `Math.min(8)` | 10682-10701; markup 2658 *"Eight steps"* |
| RAT-03 New/Edit Rate schedule | **5** | `rateWizStep`, `Math.min(5)` | 10604-10656; markup 2446 *"Five steps"* |
| CHG-02 New/Edit Charge code | **3** | `chargeWizStep`, `Math.min(3)` | 10836-10843; markup 2957 *"Three steps"* |
| DIS-02 New/Edit Discount | **5** | ⚠ generic `wz1..wz5` | markup 1210-1220 *"Five steps"* |
| TAX-02 New/Edit Tax or fee | **4** | `taxWizStep` | markup 3057 *"Four steps"*, chips 1-4 |

All five step counts match the PO's list. Two traps:

⚠ **DIS-02 has no state of its own and no ID.** It binds the generic wizard
handles `wz1..wz5`/`wzNext` that other modules also use, and `sid()` mints
nothing for it. It cannot be evidenced by screen ID *or* isolated by state.

⚠ **TAX-02's step count is drawn twice and the two disagree** — 10859-10868
defines four steps (`Math.min(4)`), 11399-11406 defines three (`Math.min(3)`).
The markup binds the FIRST copy, so **4 is correct**. Do not port the second.

## 4 · Adjacent — 1 screen, owned by Accounts

| View | Steps | Evidence |
|---|---|---|
| PLN-04 Change an account's plan | **3** | `changePlanStep`, `Math.min(3)` 11061-11069; markup 1283 *"Three steps · with proration preview before you confirm."* |

Breadcrumb is `Accounts › A-#### › Change plan` (9005) and entry is from the
account detail (3779) and a row action (1446) — it **lives in Accounts** and is
governed by plan rules, exactly as the PO scoped it. `sid()` mints **no ID** for
`module: 'changePlan'`.

## 5 · How "which services" is drawn — FOUR different ways

The PO asked how services are shown. r10 draws the same fact four ways:

| Surface | Rendering | Source |
|---|---|---|
| Plans tab · `Services included` | `.svc-tag` chips, one per service | 747-752 |
| Rate schedules tab · `Svc` | one `.svc-tag` chip | screenshot |
| Charge codes tab · `Svc` | one `.svc-tag` chip, **or the literal word `Any`** | screenshot |
| Taxes & fees tab · `Services` | **plain text** — `All`, `Electric`, `Electric, Gas`, `Water` | screenshot |
| Plan detail · SERVICES tile | **plain text** — `E · W · S` | screenshot |

`.svc-tag` is a **20×20 filled square**, service colour as background, page
background as the letter, 10px heading font at weight 800, 2px gap between
consecutive chips (173-174). Colours (213): `E #ec3013` · `W #1e6b8f` ·
`G #c47a1d` · `S #5a5555` · `T #3a6b3d` · `B #6b3d8a`. `.svc-dot` (127-128) is a
**different** component — a padded surface-filled pill with an 8px colour square
before the label, used for the tenant's services in the top bar (`■ ELEC`,
`■ WATER`, 559-560). Two components, one vocabulary; do not merge them.

⚠ **Six colours for ten services.** Storm water, Solar, Thermal/Heat and Battery
have no `--dot` in r10 and fall back to `var(--color-text)` — identical grey.
2.29.7 already assigned the missing four (Storm water dark blue as a **ring**,
Solar olive, Thermal magenta, Battery teal); that ruling governs, not r10.

## 6 · The column chooser

Opened by the icon button at the right of every table toolbar —
`btn btn-icon-sm`, an 18×18 rect split by two vertical rules, tooltip
**`Choose columns · ↑↓ to reorder`** (743). There are **32** such buttons.

From the PO's screenshot, the popover is anchored below-right of the button and
overlays the table:

* Header: `COLUMNS · show / hide · ↑↓ reorder` — small, uppercase, muted.
* One row per column, **in current table order**: a checked checkbox, the column
  label in **sentence case** (`Plan`, `Services included`, `Rate schedules`,
  `Base charges`, `Accounts`, `Effective`, `Status` — the seven plan columns,
  matching 745 exactly), then two icon buttons `↑` `↓` at the right.
* Footer: a full-width secondary **`Reset table`** button.

⚠ **THE POPOVER IS NOT IN OUR COPY OF r10.** `05-prototype/r10-2026-08-16/
SMARTBillHub.dc.html` contains the button and its tooltip but **no popover
markup** — `COLUMNS`, `show / hide`, `Reset table` and `reorder` return zero
hits. The same copy has **no sort glyph** on any `<th>` (745 is a bare
`<th>Plan</th>`, and there is no `th::after` rule), yet every header in every
screenshot carries `⇅`. **Our reference file is behind the PO's canvas.** The
screenshots are the authority for both of these; the tooltip in our copy already
states the same behaviour, so the intent is not in doubt — only the markup is
missing. Filed as DEF-354.

## 7 · What this inventory contradicts

* **A1 `S9`** — "Plans & Rates (tabbed) · Plans, Rates, Charge Codes, Taxes &
  Fees" — **four** tabs, no Discounts, and no detail pages at all. r9-era and
  stale. r10 wins (CLAUDE.md); file, do not follow.
* **CR-013 parts 2, 3 and 4** each specify a detail page for their object, which
  reads as three screens. r10 draws **one shared shell**. The PO raised this
  themselves; it is DEF-353 and needs a ruling, because CR-013 is an upgrade and
  may intend the split.
* **The ID `CHG-03`** used in the PO's list is not in the repo or the drawing —
  r10 emits `CHG-01` for the shared shell. OQ-281.

## 8 · The wizard shell — FULL PAGE, NEVER A MODAL (PO, 2026-08-20)

> **"Wizards for each type - no modal;"**

Confirmed in all five screenshots: each wizard is its own route with its own
top-bar breadcrumb (`Plans & Rates › New plan`), the sidebar still present, and
the page scrolling normally. **No dialog, no overlay, no focus trap.** Anything
built as a modal is wrong.

⚠ **THIS PARAGRAPH IS WRONG ABOUT r10 AND IS CORRECTED IN PLACE — DEF-406
(amended 2026-08-21 by the DIS-02 lane, after G29 refused the badge it implies).**
It read: *"ALL FIVE WIZARDS EMIT THE SAME BADGE: `NEW-01`. Worse than the
`CHG-01` collision — the screen ID cannot distinguish a new plan from a new tax."*

**The string `NEW-01` appears NOWHERE in `SMARTBillHub.dc.html`.** What r10's own
`sid` function does (9196 onward) is give **four** of the five wizards their own
badge — `PLN-03.<step>` · `RAT-03.<step>` · `CHG-02.<step>`, plus the details —
and give the **DISCOUNT wizard no branch at all**, so opening it falls through to
`PLN-01.discounts`, the LANDING TAB's badge. That is consistent with the two other
⚠ marks this section already carries against the discount wizard (empty
breadcrumb, no `Save draft & exit`): **r10's discount wizard is the one that was
never finished**, and its missing branch is a third symptom of the same thing.

**The conclusion the old paragraph reached still holds, for a different reason:**
route + kicker are the only usable evidence for a walkthrough — on the four
because a step suffix is not a screen id, and on DIS-02 because there is no badge.
This was found because the badge could not be claimed in code: `screenIds.ts` was
written with `r10: "DIS-02"` and G29 refused it — *"that is not a badge r10
draws"*. The map now carries `null` for both authorities with its reason, and
`DIS-02` stays the TICKET vocabulary of §18 row 12 rather than becoming a badge
claim nobody can look up.

Shell, top to bottom:

1. Breadcrumb in the top bar: `Plans & Rates › New plan | New rate schedule |
   New charge code | New tax / fee`. ⚠ **The discount wizard's breadcrumb is
   empty** — it renders `Silver Creek Water /` and stops, because `crumbs` (9005)
   has no key for its module.
2. `← Plans & Rates` back link. ⚠ **Absent on the rate-schedule wizard**; present
   on the other four.
3. Uppercase accent kicker: `NEW PLAN` · `NEW RATE SCHEDULE` · `NEW CHARGE CODE`
   · `NEW DISCOUNT` · `NEW TAX OR FEE`.
4. `<h1>`, a sentence ending in a full stop — *"Bundle rates into a customer
   offering."* · *"Build a pricing formula."* · *"Add a fee, deposit, or
   adjustment."* · *"Define an overlay."* · *"Add a tax, franchise fee, or
   surcharge."*
5. Muted sub-line: the step count **in words** plus a time estimate — *"Eight
   steps · takes about 5 minutes."*
6. Top-right `Save draft & exit`, secondary. ⚠ **Absent on the discount wizard**
   — and **BUILT ABSENT 2026-08-21, because on this one screen r10 is right for a
   reason it does not give**: `create_discount` lands the discount **and** its
   version 1 as DRAFTS, so DIS-02's ordinary commit *is* the save-draft and a
   second button would suggest the primary one did something else. The page says
   that in a sentence rather than leaving an absence to be interpreted. Note this
   is the OPPOSITE call from CHG-02's the day before, and the difference is real:
   a charge code has no draft state at all (DEF-375), so its button is drawn
   present-and-disabled with that reason.
7. **Step rail** — full width, equal-width segments split by vertical rules, each
   a numbered square + label. Active = filled accent square, white numeral,
   accent bold label; inactive = pale square, dark numeral, muted label. Labels
   wrap to two lines (`Rate schedules`, `Discounts & billing`, `Review &
   activate`). Every step is clickable (`goWz*` / `go<Kind>Step*`).
8. `STEP 1 OF 8` — small uppercase accent.
9. Step heading, again a sentence with a full stop: *"Name and describe this
   plan."* · *"Name it and pick its services."* · *"Name the charge and pick its
   type."* · *"Name and jurisdiction."*
10. Muted helper paragraph.
11. Hairline rule, then a pale form panel.
12. Footer: `Cancel` (ghost, accent text) left · `Continue →` (primary) right.

Step labels, verbatim:

* **PLN-03** Basics · Services · Rate schedules · Charges · Taxes · Discounts & billing · Eligibility · Review & activate
* **RAT-03** Basics · Base rates · Pricing formula · Effective & approval · Review & activate
* **CHG-02** Basics · Amount & behavior · Review & save
* **DIS-02** Basics & type · Value · Eligibility & verification · Effective & approval · Review
* **TAX-02** Jurisdiction · Rate & base · Remittance · Review & save

Field idioms: label above control, required marked with a red `*`, grey
placeholders, `<select>` with chevron, and a **segmented pick-one** — adjacent
bordered cells, selected cell filled accent with white text.

### ✅ BUILT ONCE, FOR TAX-02 — and what diverged (2026-08-21)

`07-frontend/src/features/rating/TaxWizard.tsx` is the first screen drawn to
this shell. Three notes for the next four wizards, so they are not rediscovered:

* **Part 1, the breadcrumb leaf, is the SHELL's and it does not say "New tax /
  fee".** `AppShell.breadcrumbFor` derives crumbs from `SHELL_NAV`, so the route
  reads `Plans & Rates › Taxes & fees`. r10's leaf needs the shell to learn the
  route, not the screen to draw its own crumb. Reported, not forged.
* **Part 12's `Continue →` LOSES ITS GLYPH.** B14 (PO 2026-08-20, no glyph on a
  button) beats r10 where they disagree, so the footer reads `Continue`.
* **The rail is NOT `WizardFrame`'s.** `.br-steps` is bespoke CSS and B14 rule
  21 says new UI adds no class to a stylesheet, so the rail, the `STEP n OF 4`
  kicker and the footer are Tailwind utilities in the screen — while
  `WizardFrame`'s **pure nav functions** (`clampStepToReached`, `jumpBackTo`,
  `backOne`, `continueFrom`) are imported unchanged, so BR-SHL-018's fence is
  the same one rule for every wizard rather than a second copy.
* **An EDIT starts with every step reached; a NEW tax earns them one at a time.**
  The record already exists, so no step is unvisited — which is what makes
  `?step=3` resolve on an edit and clamp to 1 on a new one.

### ✅ PLN-03 DRAWN TO r10, STEPS 1–8 (2026-08-21) — and the six things that diverge

The Product Owner walked **all eight steps side by side with r10** and reported a
divergence on every one (`DEF-462`, with their words per step). PLN-03 is now
drawn to the reference. What follows is only what a later lane would otherwise
re-litigate: **where the built screen deliberately does NOT match r10**, each
with the rule that outranks the drawing.

**Three PO rulings landed mid-build and are implemented, not deferred.** The one
sentence behind all three, verbatim: ***"plan all steps are bascailly binding
everything together"*** — **a plan is a BINDING screen**, and every step binds an
object that already exists.

| Step | r10 draws | What is built | Why |
|---|---|---|---|
| 2 | ten services, seven greyed with *"Not switched on for this utility"* | ⚠ **AMENDED 2026-09-08 (`CR-087` D1): ALL ELEVEN, the switched-off ones greyed, unselectable, and each carrying WHERE to switch it on** — a 3-column tile grid + a count with its denominator | ⚠ **`BR-RAT-100` AMENDED 2026-09-08 and this row has now been ruled both ways.** It read *"only the tenant-enabled ones"* from 2026-08-21 (PO: *"hide services that are not use"*), and the 2026-09-08 ruling reverses that: the missing half in August was not the greyed row but the sentence saying what to DO about it. The list is `SERVICE_CODES`'s ELEVEN, never the tenant's own rows — a tenant provisioned before `fire` existed has ten, and rendering those would hide the eleventh silently (hard-won law 2). **Scope is still the wizard only.** |
| 3 | an editable `BASE CHARGE` money input | the base **read-only and attributed** (`$12.00 · from BASE-W`) | `BR-RAT-088` moved the base to the charge code and `DEF-422` removed this very input. §A3 prices the double-base failure at **`$23,069.50`/month across 1,247 connections**. r10 predates the ruling — `DEF-456` |
| 3 | `+ Add alternate schedule for a service…` | **not built**, and the absence is stated on screen | `BR-RAT-025` **D1**: one schedule per service per plan. A second binding is a second price for one service, and the engine has no rule for choosing — `DEF-456` |
| 4 / 6 | a per-plan amount/value box, *"recorded as a plan exception"* | the **charge code's own** amount, read-only | `BR-RAT-094` gates `amount_override` to `<= 0`. `CONN` is `$85.00`; a plan may write `−$10.00` and bill `$75.00`, and may **not** write `$95.00` — refused with `rating.above_maximum, maximum: 0` |
| 5 | `+ Apply` / `Mark exempt` / a per-plan rate box | **`+ Add` binds an AUTHORITY**; no rate box, no exempt control | `BR-RAT-096` — PO: *"in step 5 of the plan we have to bind it; that wahy it is search and select"*. **Two gates, not one**: CR-013 part 4's attachment-by-jurisdiction is NOT reversed, so a bound tax still has to scope to the premises and class (`DEF-273`'s two columns). `rate_override` stays refused. The exempt control has nowhere to store its answer — `DEF-451` |
| 7 | *"Accounts outside the bounds cannot be moved onto the plan"* + a live MATCH count | the **builder** (`Attribute · Operator · Value`), advisory copy, **no count** | `BR-RAT-097` settles **authoring only** and says nothing about enforcement. `BR-RAT-043` STANDS (advisory) and the conflict is **`OQ-304`**, open. Nothing evaluates a rule (`DEF-404`) and nothing counts accounts against one (`DEF-457`), so no figure is drawn |
| 8 | no `Reason for this change` | the reason textarea **stays** | `BR-RAT-037`: a published plan is a new version with a REQUIRED reason and the server refuses without one. r10 predates the rule — a divergence in **our** favour |

**Four more things r10 draws that nothing can serve**, each a stated absence
rather than a figure: the step-4 `Recurring fixed charges $38.50/mo at 5/8"`
total (no default connection size, no per-size amount, and a browser-side sum is
forbidden — `OQ-301`); the step-7 `1,014 accounts` MATCH (`DEF-457`); the step-8
`EXCEPTIONS ON THIS PLAN` chip (`DEF-451`); and the step-8 **sample bill**
(`BR-BIL-026` puts the render on the server, so assembling one here would be a
second bill renderer with invented figures).

**Two substitutions, because the served data is not the drawn data:**

* Step 4's left pane groups by **`charge_type`**, not by r10's `BASE SERVICE` /
  `CAPACITY & STANDBY` **category** — `charges` has no category column at all,
  and a hand-written code→category map would be a second taxonomy no rule can
  read back.
* Step 7 offers the attributes the product can actually read off an account —
  **customer class and service**. r10 draws six; `BR-RAT-097` says they come
  from *"a served list"* and **no endpoint serves one** (`DEF-454`). `DEF-255`
  is the sharpest case: utility service size classes are seeded into every tenant with no
  column anywhere able to hold one, so `Meter size ≤ 1"` would be a rule that
  can never be true.

**Three parts of the shell above are now answered for PLN-03:**

* **Part 6, `Save draft & exit`, is LIVE** (unlike CHG-02's disabled one and
  DIS-02's absent one): `BR-RAT-030` gives a plan a real draft state and a
  create always lands as a draft.
* **Part 7's rail is `WizardFrame`'s, and PLN-03 drives it CONTROLLED** — step 8
  needed `Edit` links that jump back, which is the whole point of its own
  subtitle (*"the edit links jump straight back"*) and was entirely missing.
  `BR-SHL-018` allows backwards-to-completed only, which every step is by then.
* **Part 12's `Cancel` sits in the HEADER**, as on RAT-03 and CHG-02, because
  `WizardFrame` right-aligns its action row for ten wizards.

⚠ **AND TWO THINGS ON THIS SCREEN ARE UNREACHABLE ON THE LIVE TENANT FOR
REASONS THAT ARE NOT THIS SCREEN'S.** Step 4's base panel is a stated absence
for water, sewer and trash because **the seeder writes no `is_base` charge
codes** (`DEF-455`), and step 5 lists nothing because **the tenant has zero tax
jurisdictions** (`DEF-459`). Both are correct refusals sitting over inputs that
never arrive. A third: every seeded plan has **no customer class** (`DEF-452`),
which is why step 8 reads *"Not set"* and the foreign-class gate can never fire.

## 9 · REFERENCE DATA FROM SETTINGS — the linkage (PO, 2026-08-20)

> **"there is reference data coming from settings ; so we need to ensure that is
> linked"**

Confirmed as a requirement, and r10 states it itself at 7610: *"Authorities are
created under Configure → Reference data → Tax jurisdictions."* r10's own
pickers are hard-coded and inconsistent — the rate wizard offers **Electric ·
Water · Gas · Sewer · Trash** (5) and the charge wizard offers **Any · Electric ·
Water · Gas · Sewer · Trash · Broadband** (6+Any). **Neither is the ten-service
platform seed.** Do not port either list; bind both to Settings.

Every Plans & Rates control that offers a choice, and where it must read from:

| Surface | Must bind to | Home |
|---|---|---|
| RAT-03 s1 "Service this schedule prices · pick one" | tenant services, `enabled` only | SET-03 |
| CHG-02 s1 "Applies to service" (+ `Any`) | tenant services | SET-03 |
| PLN-03 s2 Services | tenant services | SET-03 |
| `.svc-tag` chips + the ten service colours | tenant services | SET-03 |
| RAT-03 s1 Unit of measure | **`uoms`**, service-scoped per BR-TEN-078 | SET-04.uoms |
| RAT-03 s2 Base rates · the per-size matrix · `5 sizes` / `Per size · 6 rows` | **`service_size_classes`** (`meter_size_classes` until BR-TEN-170, 2026-08-27) | SET-04.sizes · S76 |
| TAX-02 s1 Jurisdiction · the Taxes tab JURISDICTION column | **`tax_jurisdictions`** | SET-04 · r10 7610 |
| Customer class on PLN-03, RAT-03, CHG-02 and two landing columns | `account_types` / `account_subtypes` | customers module |
| GL on the charge and tax details (`GL 4200`, `GL 2301`) and the Taxes tab GL column | chart of accounts | SET-11.coa |
| The reason on every new version (BR-RAT-037) | `reason_codes` | SET-04 |
| PLN-03 s6 "Discounts & billing" | `billing_defaults` · `budget_billing` | SET-04 |

### What is already right, and what is not — audited 2026-08-20

✅ **No production file in `07-frontend/src/features/rating/` hard-codes a
service name.** `PlanWizard`, `RateScheduleWizard`, `ChargeCodesTab`,
`PlansTab`, `RateSchedulesTab` and `TaxesFeesTab` all read `getTenantServices`;
`RateScheduleWizard` filters `.enabled` (444-456). The only literals are in
`*.test.tsx` fixtures, which is correct. **The r10 hard-coded lists were already
not ported.** Customer class already keys on `account_types` (718).

✅ **FIXED 2026-08-21 (CR-013 P1 · RAT-03).** It is a `SelectField` over
`/lookups/uoms` now, scoped through `activeUomOptions` — the same expression of
`selectors.uom_scope_filter` the SET-03 picker uses, imported rather than
copied, so the screen and the write cannot drift. A water schedule is offered
`kgal` and `month` and is not offered `therm`; a unit a version already stores
that has since been scoped away renders **disabled with its reason** instead of
vanishing, so a save cannot silently rewrite the unit a bill was priced in. What
follows is the state it was found in.

❌ ~~**Unit of measure is a free-text `TextField`**~~ (`RateScheduleWizard.tsx`
709-717), not a select over `uoms`. The server checks it against the service's
billed unit (BR-RAT-038) and returns a non-blocking **notice**, so an operator
can type `kwh`, `KWH` or `kilowatt-hours` and still save. Hard rule 3 says
consumption always carries an explicit unit; a free-text unit is that rule
enforced only after the fact. **DEF-355.**

⚠ **PARTLY FIXED 2026-08-21 (CR-013 P1 · RAT-03).** RAT-03 reads it: the wizard
gained **step 2**, whose rows are `/lookups/service_size_classes` (active only,
BR-TEN-029; **unscoped**, because BR-TEN-078 ruled that list unscoped twice and
specifically because r10's card text reads like the strongest candidate for
scoping). The backend accepts and serves the schedule's half of the axis —
`RateSizeRow` per-size minimum bill, through `version_row.size_rows`.

⚠ **AND THE WIZARD HAD FOUR STEPS, NOT THE FIVE THIS DOCUMENT SAID.** §18 row 6
and §8's rail both recorded RAT-03 as five steps; the file's `steps` array was
`basics · structure · effective · review`. `Base rates` was never a step, which
is *why* the per-size matrix had nowhere to live. The rail is now built from
`RATE_WIZARD_STEPS` so the count is one fact a test reads.

**Still not read anywhere else** — PLN-02's Base rates tab and the charge code's
`Per size · N rows` basis are unchanged. ✅ **RAT-02's matrix IS updated
(DEF-430 CLOSED, 2026-08-21):** it drew ONE row and printed *"this schedule has
no per-connection-size rows"* unconditionally, which was a true statement about
every schedule in the database and became a statement about the CODE the moment
`version_row` started serving `size_rows` — hard-won law 1 in its quietest form.
`matrixRows()` now draws one row per size over the UNION of the two axes (a size
with its own minimum bill, and a size with its own tier ladder), falls back to
the single every-size row when both are empty, and says which sizes are showing
the fallback ladder rather than their own. What follows is the state it was found
in.

❌ ~~**`service_size_classes` is referenced NOWHERE in the rating feature**~~ — zero
hits across every file. Per-size base rates are the spine of RAT-02's matrix,
PLN-02's Base rates tab, and the `Per size · N rows` basis on charge codes, and
none of it reads the size-class list. **DEF-356**, and it collides with the
per-size base-rate ruling CR-013 is already waiting on.

⚠ **`charge_codes` exists as a Settings reference-data card AND as a Plans &
Rates tab with its own 3-step wizard and detail page.** Two homes for one object,
and nothing says which owns creation, validation and versioning. **OQ-282** —
this needs a ruling before CHG-02 is built, not after.

## 10 · THE VERSIONS TAB IS THE OBJECT'S OWN RECORD — NOT A VIEW ON `audit_log` (PO, 2026-08-20)

> **"also look at version screens - they are showing details directly here and not
> routing them to audit log"**

**Confirmed in all five details, and this is a build instruction, not an
observation.** The Versions tab renders the object's **version table** inline —
what changed, in a sentence a utility clerk wrote — and it never links out to
audit. A lane that implements Versions as a filtered `audit_log` query has built
the wrong screen, and it will look plausible: both are append-only histories of
the same object.

They are different records with different owners:

| | **Versions tab** | **`audit_log`** |
|---|---|---|
| Answers | *what the price WAS, and from when* | *who touched it, and when* |
| Row is | a priced state that bills can still resolve to | an actor + action + timestamp |
| `CHANGE` text | **authored by the person filing it** | derived from the mutation |
| Read by | the resolution chain, every bill run | compliance, incident review |
| Lives in | `tariff_versions` and its siblings | `audit_log` (hard rule 7) |

A version row is **billing input**: R1 and R2 select one. An audit row is never
read by the engine. Writing one does not excuse writing the other — a new version
still writes `audit_log` under hard rule 7.

### Columns, as drawn

Four of the five share one shape; **the rate schedule is deliberately richer**,
because it is the only one filed with a regulator:

* Plan · Charge code · Discount · Tax — `VERSION · EFFECTIVE · CHANGE · STATUS`
* **Rate schedule** — `VERSION · EFFECTIVE · SUPERSEDED · FILED AS · CHANGE · BY · STATUS`

`FILED AS` carries the docket (`PUC #W-2025-1184`, or `2027 filing (pending)`
for a draft) and `BY` names the submitter (`Alex Reed`, `M. Torres`). Do not
normalise the other four up to seven columns — a discount has no docket.

Statuses drawn in these tables: `Active` · `Draft` · `Superseded`. A **draft
future version is listed above the current one** (rate v4 · Jan 1 2027 sits above
v3 · current), so the table is ordered by effective date descending, not by status.

### The `DATED` exception banner closes every one of the five

An accent-ruled banner with the literal label `DATED`, verbatim:

* **Plan** — *"Composition changes save as a new plan version via the builder — accounts re-price from its effective date."*
* **Rate schedule** — *"Bills always price usage with the version in force on the read date — a January bill for December usage uses v3 even after v4 activates."*
* **Charge code · Discount · Tax** — *"Bills always use the version in force on the usage date."*

The rate schedule's wording is the strongest statement of the propagation rule in
the whole product and should be treated as the canonical sentence for it.

⚠ **`CHANGE` is authored, not derived** — *"Adds 4th conservation tier"*,
*"+6% across tiers, 2″ override added"*, *"Raised from −10% to −15%"*. It is the
reason captured at version creation (`reason_codes`, §9).

✅ **CLOSED 2026-08-21 (DEF-280), and the finding is that the sentence was ALWAYS
AUTHORED.** BR-RAT-037 has refused a new version without a reason since the rule
was written; `create_rate_schedule_version` took it and wrote it to
`rate_change_log` — the cross-object history — and to nowhere a filings table can
read. So this column was empty for want of a JOIN, not for want of an author.
`tariff_versions.change_reason` carries the same words now (migration 0017); the
log row is untouched, because it carries plan changes too. A FIRST version reads
`null` and the column states that absence: there was no change to describe.

⚠ **AND THE SEPARATE `{...}` DEFECT IS FIXED BY DESCENDING, not by prettifying.**
DEF-280's own prevention names it — *"descend into the structure and diff
component by component … naming the component that moved"* — so
`RateChangesTab.diffFields` walks both stored payloads and reports
`structure.tiers[0].unit_price 3.200000 → 3.450000` where it used to report
`structure — → {…}`. Arrays compare BY POSITION, which is right for these
payloads and worth stating: a tier's identity is its place in the ladder, a
season's is its place in the year, a window's is its start time, and the server
orders all three deterministically before serving them.

## 11 · WHAT THIS DOES TO SEED DATA (PO, 2026-08-20)

> **"this change might lead to change in seed data"**

Right, and the biggest consequence is not a count — it is that **the seed writes
exactly one version per object**, so the Versions tab §10 just ruled on cannot be
walked, demonstrated or tested from seeded data at all.

`seed_demo.py:246` states it: *"the first version is written ACTIVE
(create_rate_schedule)"*, and the live tenant carries **6 rate schedules and 6
schedule versions** — one apiece. r10 draws **v1 · v2 · v3 · v4** on the rate
schedule, with a superseded date, a docket per version and two different
submitters. Against our seed, every one of the five Versions tabs renders a single
row, `SUPERSEDED` is always `—`, and the `DATED` banner makes a claim about
behaviour nothing in the fixture can exhibit. **DEF-357.**

### The counts, live vs the drawing

Already reconciled in `11-change-requests.md` (CR-013 item 0, counted with
`select count(*)` rather than read off a document) and unchanged by today:

| | r10 draws | live tenant | at HEAD |
|---|---|---|---|
| Plans | 6 | **5** | 5 |
| Rate schedules | 7 | **6** | 6 |
| Charge codes | 13 | **23** | 23 |
| Discounts | 5 | **0** | 0 |
| Tax rates | 6 | **2** | 5 |
| Tax jurisdictions | — | 5 | 7 |

**Two of those rows change what CR-013 can demonstrate**, and both are already
known rather than new:

* **Discounts are zero and there is no discounts table.** EP-RAT-12 builds DIS-01,
  DIS-02 and the discount half of the shared detail shell — against an empty
  fixture there is nothing to click, and R6 resolves to *unmodelled*.
* **The live tenant has 2 tax rates where a tenant provisioned at HEAD gets 5**,
  because the post-migrate sweep passes `structural_only=True` until
  `tenants.reference_defaults_opted_in` exists (OQ-088 residue, OQ-216). A
  walkthrough on the live tenant and one on a fresh tenant see different screens.

### What today's findings add to the fixture

* **Version history — the new one.** At least one object needs the full r10 shape:
  a superseded version, a current version, and a **dated draft above it**, each
  with its own authored `CHANGE` sentence, and the rate schedule additionally with
  `FILED AS` and two different values in `BY`. Without it §10's distinction is
  untestable and DEF-280 has no fixture to be proved RED against.
* **Services.** The seeded tenant runs **Electric + Water**; the platform seeds
  **ten**. Eight service colours — including the four assigned in 2.29.7 — are
  never rendered by any walkthrough. A fixture premises on Gas, Trash or Storm
  water is what makes §5's chips real.
* **The six §B4 accounts** already named in the design and still unbuilt: an
  out-of-county premises, a commercial 2″ meter, an industrial demand account, a
  fire-line premises, an account with two stacked discounts, and an expired
  exemption certificate. Each exists to make one selector of the Tier-1 matrix
  reachable.
* **Reference data is NOT the gap.** `uoms` holds 26 rows and
  `service_size_classes` holds **40** — both fully seeded. (**9 until 2026-08-27**;
  BR-TEN-171 ratified the bands for eight services and renamed the list, so the
  matrix this section is about now has forty candidate rows rather than nine.)
  DEF-355 and DEF-356 are therefore *unwired*, not *unseeded*, and no seed change
  fixes either.

## 12 · SEARCH · FILTER · EXPORT · COLUMNS — the four toolbar capabilities (PO, 2026-08-20)

> **"I want you to confirm on search, filter, export, colume section panel UI and
> finctioalities also as part of design"**

These are **not** Plans & Rates decisions. B9 (`04-docs/02-decisions/09-interaction-standards.md`)
defines all four ONCE, cross-cutting, and each screen declares conformance through
a capability-matrix row in its epic file. Stories never restate them. Quoted:

| | Standard | The binding behaviour |
|---|---|---|
| Search | **IS-3** | server-side · debounced **300 ms** · **min 2 chars** · searches only the fields the capability matrix declares · clears via ✕ |
| Filters | **IS-4** | declared per screen · **AND**-combined · active filters shown as chips with clear-all · **state persisted in the URL**, so a filtered list is shareable |
| Table + paging | **IS-2** | server-side · page sizes **50 / 100 / 200 / 500 / 1000, default 50** (PO ruling 2026-08-09; `per` clamps to this set) · click-header single-column sort with direction toggle · **stable secondary sort by id** · sorted column indicated |
| Columns | **IS-5** | **UNIVERSAL** requirement, PO-confirmed · show/hide **+ reorder** · **server-persisted per user** (BR-SHL-027) · **identity column always visible** (BR-SHL-013) · **export follows the visible set** |
| Export | **IS-9** | CSV honours **current filters + visible columns** · money 2dp · UTF-8 · filename `<screen>-<tenant>-<YYYYMMDD>.csv` · server-streamed, **>50,000 rows rejected** · money exports write an audit row (BR-SHL-016) |

**IS-5's stated rationale is why it is universal**, and it is worth quoting because
it decides arguments later: *"every data table gives the user control of displayed
columns so per-tenant column requests never require code changes."*

### ⚠ THE COLUMN PANEL IS BUILT, TESTED, AND REACHABLE BY NOBODY — DEF-358

The logic is real. `07-frontend/src/components/DataTable.tsx` exports
`toggleColumnVisible`, keeps the visible set as an **ordered array of column keys**,
refuses to hide the identity column (BR-SHL-013), carries reorder helpers, and
names its persistence key `table.<screen>.columns`.

**And `toggleColumnVisible` is called by exactly two files: `DataTable.tsx` itself
and `DataTable.test.tsx`.** No feature screen calls it. No component renders a
chooser — `columnChooser`, `ColumnChooser`, `availableColumns` and `hiddenColumns`
return **zero hits across the whole of `src/`**. `ChargeCodesTab.tsx:181` even
declares *"the two additional available columns (IS-5 chooser)"* for a chooser
that does not exist.

That is hard-won law 2 exactly — built is not wired — and it is the **DEF-135
pattern** (*"thirteen ruled rules have no door"*) with a fourteenth instance. It
also silently breaks IS-9: *"export follows the visible set"* cannot mean anything
while the visible set can never be changed.

### What r10 draws, and what it settles

r10's toolbar, identical on all **33** table surfaces (743):

```
[ Search plans… ]                    [ All ] [ + Filter ▾ ] [ ▥ ]
```

* the **`▥` button** carries `title="Choose columns · ↑↓ to reorder"`
* the panel it opens (from the PO's screenshot — §6, and **not present in our copy
  of r10**, DEF-354) is: header `COLUMNS · show / hide · ↑↓ reorder` · one row per
  column in current table order, each a checked box + sentence-case label + `↑` `↓`
  · a full-width secondary **`Reset table`** footer.

**This closes OQ-013.** B9's own header says *"IS-5 pattern pending design
ratification (OQ-013)"* and IS-5 offers only an *"interim spec: ⋮ menu top-right of
table header"*. r10 draws a **columns icon and a full panel with explicit ↑↓
controls and a reset**, not a ⋮ menu — so the interim spec is superseded by the
drawing and the pattern is now ratifiable. `Reset table` is new and appears in no
standard; it needs to be added to IS-5 when OQ-013 closes.

⚠ **Two gaps r10 leaves open, which the standards already answer** — do not port
the drawing's silence:

* ~~**The `All` chip is a stub.** All 33 toolbars carry exactly one `fchip`
  reading `All` and no others; `+ Filter ▾` opens nothing. IS-4 requires **active
  filters as chips with clear-all, persisted in the URL**. Build IS-4, not the
  drawing.~~
  ⚠ **SUPERSEDED 2026-08-21 (DEF-442) — THE CHIP AND THE BUTTON ARE NOT STUBS,
  AND READING THEM AS STUBS IS WHAT PRODUCED THE DEFECT.** This bullet was
  written from the STATIC `.dc.html`, where `+ Filter ▾` has no markup behind it.
  **r10 ships the behaviour in `table-tools.js`**, which the page loads: the
  button opens a panel headed `FILTER BY` with one checkbox group per filterable
  column (lines 149-176), every applied value is inserted into the toolbar as a
  removable chip reading `Column: value ×` (lines 119-137), and the `All` chip
  goes `.active` exactly when nothing is applied and clears filters + search when
  clicked (line 239). One r10 toolbar even draws the applied chips statically —
  line 7265, `Area: South ×` and `Not on any route ×`. **So r10 and IS-4 never
  disagreed**; the drawing was read as silent when it was only unopened. The
  Product Owner reported the consequence directly: _"also look at Filter in Proto
  - it is panel and when you select somethibg it shows selection on screen ; look
  at filters you build"_. **Both are built now**, shared, in
  `07-frontend/src/components/FilterBar.tsx` — see the amendment below.
* **There is no export control on any Plans & Rates toolbar.** r10 draws Export on
  Finance and Reports surfaces only. IS-9 and the epic capability rows still apply
  — **EP-RAT-03's row declares CSV for charge codes and it is wired** to
  `POST /exports` (a money table, so the server writes the BR-SHL-016 audit row);
  `PlansTab` and `ChargeCodesTab` both compose a `downloadSlot`. A missing button
  in the drawing is not a decision to drop the capability.

### ~~One ratified divergence, correctly recorded~~ — ❌ **WRONG, AND IT IS WHAT CAUSED DEF-441 (corrected 2026-08-21)**

> ~~**RAT-01 is a CARD GRID, not an IS-2 table**, and EP-RAT-02's capability row
> marks the IS-5 chooser **N/A** for it. … It does mean **RAT-01 has no column
> control by ratified design**, which is a stated exception to IS-5's
> universality rather than a gap.~~

**RAT-01 IS A TABLE. r10 draws it as one, and this section said otherwise for
five days.**

**The source, quoted, not summarised.** `05-prototype/r10-2026-08-16/SMARTBillHub.dc.html`
**line 764**:

```html
<table class="table lt">
<thead><tr><th>Schedule</th><th>Svc</th><th>Structure</th><th>Sizes</th><th>Seasons</th><th>Plans</th><th style="text-align:right">Accounts</th><th>Effective</th><th>Status</th></tr></thead>
```

Nine columns. The line above it draws the toolbar — a search box, an `All` chip,
`+ Filter ▾`, and **the column-chooser glyph with the tooltip "Choose columns ·
↑↓ to reorder"**. So the IS-5 chooser is not N/A for this surface; r10 draws it
explicitly.

**What the error cost.** The Product Owner found it by putting the two screens
side by side (2026-08-21): *"rate schedule is in table format in Proto - you
ahve done card format"*. The lane that built the card grid did nothing wrong —
it read this row, saw it contradict its own build packet ("the shared DataTable
on every list"), followed the document marked **ratified**, and reported the
divergence in `RateSchedulesTab.tsx`. **A false statement carrying the word
"ratified" is worse than no statement**, because it converts a lane's correct
instinct into the wrong build and leaves a written reason not to look again.

**And the layout error hid five DATA gaps.** A card has no columns, so nothing
noticed that `Sizes`, `Seasons` and `Effective` had no field behind them at all,
and that `Plans` and `Accounts` were served but rendered as a prose sentence in
a card footer — *"Used by 1 plans · applied to 2 accounts"* — which cannot be
sorted, scanned or exported. All five are served by `selectors.schedule_card`
as of 2026-08-21.

**IS-5 now APPLIES to this tab**, along with every other table capability it was
excused from: search, filters, the column chooser, the pager, and **CSV export**
(`apps/rating/exports.py` registers `rate-schedules`; a money-bearing list, so
the server writes the BR-SHL-016 audit row).

**EP-RAT-02's capability row is the remaining stale document** — it still says
"not an IS-2 table" with the chooser N/A. It is superseded by r10 line 764 on the
authority of the PO ruling of 2026-08-16; re-extraction into the epic has not
happened and is reported here rather than done silently.

### ⚠ AMENDMENT 2026-08-21 — THE FILTER CONTROL IS A PANEL AND A CHIP ROW (DEF-442)

Everything above describing filters as a **dropdown per dimension** is
**superseded**. It described the product as it was: `FilterBar` rendered one
labelled `<select>` per declared dimension — on RAT-01 that was **Service ·
Structure · Status**, three controls permanently occupying the toolbar — and the
applied state was visible only inside each closed select.

**What is built now**, once, in the shared `07-frontend/src/components/FilterBar.tsx`,
so all five Plans & Rates tabs and the ~10 other list screens changed together:

```
[ Search rate schedules… ]      [All] [Svc: Water ×] [Status: Active ×] [ + Filter ▾ ] [ ▥ ]
                                                                              │
                                                            ┌─────────────────┴───────┐
                                                            │ FILTER BY               │
                                                            │  Svc                    │
                                                            │   ☐ Electric  ☑ Water   │
                                                            │  Structure              │
                                                            │   ☐ Flat  ☐ Tiered  …   │
                                                            │  Status                 │
                                                            │   ☑ Active  ☐ Draft  …  │
                                                            └─────────────────────────┘
```

* **`+ Filter ▾`** is `btn-secondary btn-sm`, matching r10 line 763, and its
  tooltip names the dimensions before you open it — *"Filter by: Service,
  Structure, Status"*, which is r10's own `title` on that button.
* **The panel** is a `<details>`/`<summary>` disclosure, the same one the column
  chooser beside it uses, so it is keyboard-operable with no script. Each
  dimension is a `<fieldset>` with a `<legend>`, so a checkbox reading *"Water"*
  is announced as *"Svc, Water"* rather than on its own.
* **Every applied filter is a chip in the toolbar**, between the `All` chip and
  the button — exactly where r10 inserts it. The `×` is a real button carrying
  *"Remove the {dimension} filter"*; the chip itself is inert, because r10's
  whole-chip click with a bare `×` names nothing to a screen reader.
* **The `All` chip is the clear-all.** Inverted while nothing is applied
  (r10's `.fchip.active`); the moment something is, it carries the accessible
  name *"Clear all"* and clears every filter. IS-4 wants a clear-all only when
  there is something to clear, so it names nothing when there is not.
* **A screen that declares NO filters renders none of this** — BR-SHL-010, an
  undeclared capability is never drawn.

**IS-4's behaviour is unchanged and that is the point.** Same declared
dimensions, same **AND** combination on the server, same `f.<name>` URL
round-trip. Of the four tests over this component, the three that assert the
RULES passed through the redraw untouched; the only one that broke counted
`<select>` elements, which is the shape.

**Two things r10 has that this does not, both filed rather than faked:**

| Divergence | Why | Filed as |
|---|---|---|
| r10's checkboxes **multi-select** within a dimension (`table-tools.js` line 168 pushes onto an array); ours **replace** — ticking `Svc: Gas` after `Svc: Water` leaves Gas alone | `TableRequestState.filters` is one value per dimension and **BR-SHL-011 serialises one `f.<name>=<value>`**, both signed and both applied server-side. Widening is an API change, not a drawing change, and the prime directive forbids choosing it here | **OQ-304** |
| r10's footer reads `Showing 1–1 of 1 **(filtered from 7)**` (`table-tools.js` line 106); ours stops at `of 1` | **No list endpoint serves an unfiltered count.** Faking it would print a figure nobody computed, and an optional prop nothing can pass is dead UI (hard-won law 2, G13) | **DEF-458** (and **DEF-459** for `Showing` + `Page N of M` + first/last) |

**No CSS was added** (PO: _"do everything using tailwind and not custom CSS"_) —
`components/FilterBar.css` was **deleted**, five rules with it, and G31's
declared-class ceiling was lowered **897 → 892** to hold the shrink.

## 13 · WHERE `service_size_classes` BELONGS — BOTH, FOR DIFFERENT COLUMNS (PO question, 2026-08-20)

> ⚠ **The list was called `meter_size_classes` when this section was written.**
> BR-TEN-170 renamed it to `service_size_classes` on 2026-08-27 — PO verbatim,
> *"it is utility service size class"* — and BR-TEN-171 took it 9 → 40 rows
> across eight services. **Nothing in this section's ANSWER changes**: where the
> list belongs, and which column is editable on which object, are untouched. The
> quoted question below is left in the PO's own words, old name included.

> **"meter_size_classes SET-04.sizes → the base-rate rows — is this required on
> rate schedule or charge code - please evaluate and reconfirm"**

**Answer: both objects need it, as a shared ROW AXIS — and they write different
COLUMNS of that row. Today neither object has a size dimension at all.**
`09-screen-inventory.md` §9 and the design artifact both attributed the
*base-rate rows* to the rate schedule. That follows CR-013 part 1's wording and
**contradicts §A3**, which is later and explicitly settles it. Corrected here.

### The evidence: r10's own rate matrix has three per-size columns, not one

`07-r10-plans-rates-readout.md` §4 records RAT-02's matrix as
**`size · base · min · t1 · t2 · t3 · accounts`**:

```
Water    5/8"   12.00 / 18.00 / 3.20 / 4.80 / 7.20
         3/4"   14.50 / 21.00 / 3.20 / 4.80 / 7.20
         1"     22.00 / 30.00 / 3.20 / 4.80 / 7.20
         1.5"   42.00 / 52.00 / 3.20 / 4.80 / 7.20
         2"     64.00 / 78.00 / 3.45 / 5.10 / 7.70   ← the tiers CHANGE here
Electric 1φ100A 18.50 /   —   / 0.11 / 0.14 / 0.19   ← no minimum bill at all
```

Three separate things vary by size, and **the 2″ row is the one that settles the
question**: its tier prices differ from every other size. A per-size tier rate
cannot be derived from a base, from a multiplier, or from anything else — it can
only come from a per-size row **on the schedule**. So the schedule genuinely needs
the size axis for its own reasons, independently of the base.

### The split, per §A3

| Column | Written by | Read by | Why |
|---|---|---|---|
| **base** | **CHARGE CODE** | schedule shows it **read-only, attributed** (`$12.00 · from BASE-W`) | §A3: *"the charge code owns the base amount. One source of truth."* |
| **minimum bill** per size | **RATE SCHEDULE** | — | §A3 lists minimum bill as usage math |
| **tier / period rates** per size | **RATE SCHEDULE** | — | the 2″ row |

So the correct wording, replacing §9's row for both objects:

* **Charge code** → `service_size_classes` gives it the rows of its **per-size amount
  table**, including the base. This is the editable source.
* **Rate schedule** → `service_size_classes` gives it the rows of its **rate matrix**,
  whose editable columns are minimum bill and the tier/period rates. The base
  column on that matrix is a **display of the charge code's value**, and the
  schedule's edit mode does not include it.

The resolution chain already splits the two refusals correctly — R3 refuses when
the **schedule** has no size row, R4 refuses when the **charge code** has no amount
at that size — so the engine's control flow is right even where its data model is
not.

### ⚠ WHAT IS ACTUALLY BUILT: no size dimension exists anywhere

Read off the models, not the spec:

| | Today | Needed |
|---|---|---|
| `TariffVersion.base_charge` | **scalar**, nullable (DEF-277) | retire — the base moves to the charge code |
| `TariffVersion.minimum_bill` | **scalar**, nullable | per size |
| `RateTier` | tenant · tariff_version · season · seq · from_qty · to_qty · unit_price — **no size FK** | per size |
| `Charge.amount` | **scalar** | per size (`charge_code_amounts`, §B3, **not built**) |

One tariff version therefore carries **one** base, **one** minimum bill and **one**
set of tiers. The five-row water matrix above collapses to a single row, and the
2″ row is inexpressible.

⚠ **The engine models per-size and assigns it to the wrong owner.**
`apps/rating/resolution.py` defines `ScheduleVersion.size_rows: dict[str, Decimal |
None]` documented as *"maps a connection size to its BASE amount"*, and
`resolve_size_row()` returns that base into `ServiceResolution.base_charge` (760-766).
That is **part 1's model, not §A3's**, in a module written the same day §A3 was
ruled — and there is no reference to §A3 anywhere in the file and no guard against
a base charge code being resolved alongside it. **DEF-359.**

⚠ **§B3's schema plan is incomplete.** It adds `charge_code_amounts` (per-size rows)
and `tariff_versions (+minimum bill per size)` — and says nothing about per-size
**tier rates**. Nothing in the plan adds a size dimension to `RateTier`, so building
§B3 exactly as written still cannot express the 2″ row. **DEF-360.**

### ⚠ WHAT CHANGED ON 2026-08-21 (CR-013 P1 · RAT-03) — HALF THE AXIS IS LIVE

The table above said *"no size dimension exists anywhere"*. Read off the code
now:

| | Then | Now |
|---|---|---|
| `TariffVersion.base_charge` | scalar, nullable | **unchanged, and no longer editable from RAT-03** — the wizard carries and re-posts it so no tenant loses a live base, and offers no control. BR-RAT-088's *"its edit mode does not include it"*, built |
| per-size **minimum bill** | nowhere | **`RateSizeRow`, written and served** — `POST/PATCH … size_rows`, `version_row.size_rows`, edited on RAT-03 step 2 |
| per-size **tier rates** | nowhere | ✅ **WRITTEN AND SERVED, 2026-08-21 (DEF-433 CLOSED).** `RateTier.size_class` is accepted on a tier, validated PER GROUP (BR-RAT-032 amended), stored and served on `version_structure.tiers[].size_class`. RAT-03 step 3 states an override beside the ladder it differs from; RAT-02's matrix draws one row per size. ⚠ **`pricing_inputs` takes a `size_class` and a BILL DOES NOT PASS ONE YET — DEF-484** |
| per-size **base** | nowhere | ✅ **SERVED, 2026-08-21 (DEF-431 CLOSED for the READ).** `charge_row.size_amounts` publishes `charge_code_amounts` beside the scalar; `features/rating/baseCharge.ts` resolves one size's base for BOTH screens, so RAT-02 and RAT-03 cannot disagree. An empty list means *"this code does not vary by size"* and the scalar answers, which is what every charge code says today. ⚠ **The EDITOR is still CHG-02's** — nothing in Plans & Rates writes a per-size amount |

**So the schedule's own reason for needing the axis is now met — with the wiring
to a bill named.** §13's argument is that the 2″ row settles the question — a
per-size tier cannot be derived from a base or a multiplier — and that row is
expressible from 2026-08-21: `3.45 / 5.10 / 7.70` against every other size's
`3.20 / 4.80 / 7.20`, entered on RAT-03 step 3 and drawn on RAT-02's matrix.
**What is NOT done is the last hop into money**: `apps/billing/gather.py` calls
`selectors.pricing_inputs` without a connection size, so the selector falls back
to the NULL *"every size"* ladder and a 2″ connection bills `3.20 / 4.80 / 7.20`.
That is **DEF-484**, and it is stated on the screen at the moment the override is
typed rather than left in a docstring — on 10/20/5 units it is **$220.00 billed
against the $232.00 the utility typed**, twelve dollars a month with every line
individually correct.

**Neither is a blocker for the PO to rule on** — §A3 already ruled ownership and
this is the implementation catching up. What the PO *does* still owe a ruling on is
the per-size base-rate question already open (two dated rulings conflict), and these
two defects sharpen what that ruling has to cover.

## 14 · THE GL BELONGS ON THE RATE SCHEDULE AS A DISPLAY, AND IT IS ALREADY MAPPED (PO, 2026-08-20)

> **"you will have to display GL code here also; they will be mapped"**

Correct, and the mapping exists — the rate schedule reads it rather than owning it.
**BR-BIL-010** maps *"service → revenue GL with an optional usage/base split"*, and
**BR-BIL-067** (PO ruling 2026-08-11) makes the seeded account a **default the
tenant may override**: `ledger/chart.py` states it plainly — *"`SERVICE_REVENUE_ACCOUNTS`
is where a service's revenue account STARTS; the live answer is
`tenant_services.revenue_account`, which a tenant may override."*

So for the rate schedule the boundary has a third shape, and it is worth naming
because it is neither of the other two:

* Settings owns the **list** (services, sizes, jurisdictions).
* Rating owns the **money** against each entry.
* **The ledger owns the ACCOUNT, Settings maps service → account, and the rate
  schedule DISPLAYS the mapped code.** It stores no GL of its own —
  `TariffVersion` has no `gl_account_id` and must not gain one.

⚠ **BR-BIL-010's *"optional usage/base split"* is the same seam as §A3.** Usage
revenue and base revenue may point at different accounts — which is precisely why
the base belongs to the charge code (which carries its own mandatory
`gl_account_id`) and the usage math belongs to the schedule (which reads the
service's revenue account). The GL model and the ownership model agree; §9's row
for the rate schedule now names the GL as a **read-only mapped display**.

Two facts a builder needs: a tenant is seeded **only the accounts for services it
sells** (Silver Creek Water gets 4110 · 4115 · 4120 and not the other six), and
`invoice_lines[].gl_account_code` is **served null** today until `ledger_accounts`
lands in W5 — so the display has a source but the bill line does not yet carry it.

## 15 · R6 AND `tariff_version_id` — BOTH CLAIMS IN THIS DOCUMENT WERE STALE

> **"you will have to model this"**

Checked against the code rather than the design, and **both had already moved**:

* **`tariff_version_id` is populated. DEF-276 is FIXED.** `backbill.py:246-252`
  records it: *"DEF-276 put `version_id` on `TariffConfig`, the engine stamps it on
  every priced line, and stage 6 writes it."* The re-pricing guarantee is a
  guarantee now, not a comment. Corrected in the design artifact.
* **The discount MODEL exists.** Migration `0009_cr013_discounts.py` and ~2,800
  lines across four modules define **six tables** — `discounts` ·
  `discount_versions` · `plan_discount_rules` · `discount_enrolments` ·
  `discount_enrolment_documents` · `discount_grants` — with all five part-3 types
  and all five statuses including `suspended_funding_exhausted`. §A2's *"there is
  no discounts table in this product"* is **out of date**.

⚠ **But the ENGINE is not wired to it, and its refusal now states something false.**
`resolution.py:655` still returns `modelled=False` with the message *"this product
has no discounts table — not 'none seeded': the table does not exist"*. **The table
does exist.** The module docstring above it already describes the wired behaviour
(*"`resolve_discounts` reads it and returns `modelled=True` with the enrolments it
found — including `applied=()` for an account enrolled in nothing"*) — so the
design is written, the tables are built, and the eight lines that join them are
missing. **DEF-361.**

The order rule stays exactly as the docstring states it, and it carries the worked
figure: **discounts apply BEFORE taxes**, so a discount reduces the taxable base —
removing the $1.00 PAPERLESS discount moves Bexar County from $3.78 to $3.80, which
is why §A4 S1's reachable total is **$196.37 and not $194.60**.

## 16 · RATE SCHEDULE vs CHARGE CODE — FOUR OVERLAPS, AND ONLY ONE IS RESOLVED

> **"My only confusion is between Rate schedule and Charge code - I still see there
> is overlap; can you evaluate them we need to keep them separate and no overlap"**

The confusion is well founded. **Four distinct amounts can be expressed by both
objects.** One is settled, one is already on the PO's agenda, and **two have never
been raised.**

| # | The amount | Rate schedule expresses it as | Charge code expresses it as | Same figure? | Status |
|---|---|---|---|---|---|
| 1 | **Base service charge** | `TariffVersion.base_charge` · matrix `base` = **$12.00** | `BASE-W · Water base service · $12.00 · per size` | **yes** | **RESOLVED** by §A3 — charge code owns it. Not yet implemented (DEF-359) |
| 2 | **Minimum bill** | `TariffVersion.minimum_bill` · matrix `min` = **$18.00** | `MIN-W · Minimum bill · water · $18.00 · per size` | **yes** | ⚠ **UNRESOLVED — never raised. DEF-362** |
| 3 | **Capacity charge** | `CapacityRate` model (`unit_label` + `rate_per_unit`, BR-RAT-018/019/022, **GT-15**) and EP-RAT-06 | `CAP-W · Capacity charge · water · $22.00 · per size` | — | ⚠ **UNRESOLVED — never raised. DEF-363** |
| 4 | **Fire line standby** | a rate schedule: *Fire line standby · Flat · 4 sizes · **Standby*** | `FIRE · Private fire line standby · $14.00 · per size` | — | **ON THE AGENDA** — design §A5, *"plan, parallel path, or charge code?"* |

**Overlaps 1 and 2 are the dangerous kind: the same figure stored twice.** §A3
worked the cost of exactly this for the base — $18.50 charged twice is
**$23,069.50 a month across 1,247 connections**, *"and no test catches it, because
both rows are individually correct and only the rule makes the total wrong."* The
minimum bill is the same trap at $18.00 and nobody has looked at it.

**Overlap 3 is the delicate one**, because `CapacityRate` is consumed by **GT-15**
— a golden test, and B5 is ❄️ FROZEN. Moving capacity to the charge code changes a
frozen billing-math path and needs a finance re-sign via HUMAN-GUIDE §6, not a
lane's decision.

### What is NOT an overlap — two pairs of homonyms, keep both

Worth stating so a cleanup does not delete a real field:

* **`TariffVersion.minimum_bill` vs `Charge.min_amount`** — different things.
  The first is a floor on the whole service line (if usage + base < min, bill the
  min). The second is the floor on a **percentage** charge code — `LATE` is
  *"1.5% · $5 min"*. Same word, unrelated rules.
* **The schedule's *optional cap* vs `Charge.max_amount`** — same distinction, one
  caps a usage calculation and one caps a percentage fee.

### The separation rule to build to

**One sentence per object, and every amount must fall on exactly one side:**

> **The rate schedule prices a QUANTITY. The charge code prices a THING.**

If the amount is multiplied by something the meter measured, it belongs to the
schedule. If it is charged because a connection, an account or an event exists —
regardless of consumption — it belongs to the charge code. Tested against all
four: base = a thing (charge code ✓, §A3 agrees) · minimum bill = **neither, it is
a floor on the schedule's own result** and therefore the schedule's ✓ · capacity =
a thing, priced per reserved unit not per consumed unit (charge code) · fire line
standby = a thing (charge code). **That reading resolves 2, 3 and 4 the same way
§A3 resolved 1 — but 3 crosses a frozen figure, so it is put to the PO rather than
applied.**

## 17 · THE INVENTORY — screens, endpoints, tables, seed, E2E (PO, 2026-08-20)

> **"you need to confirm how many screens and how many endpoints - including their
> build status, and table names and their status ; do you think there will be
> changes in seed data and e2E cases"**

Counted from the repo on 2026-08-20 at build **2.29.29**, not from any document.

### Screens — 13 views / 10 routes

Per §§1–4. Frontend files present in `07-frontend/src/features/rating/`:
`PlansRatesPage` · `PlansTab` · `RateSchedulesTab` · `ChargeCodesTab` ·
`TaxesFeesTab` · `RateChangesTab` · `PlanWizard` · `RateScheduleWizard` ·
`ratingShared` (+ 5 test files).

**Added since this census was taken:** `RateScheduleDetail` (RAT-02, row 5) ·
`DefinitionDetailPage` + `definitionDetail` (rows 8 · 11 · 14) ·
**`ChargeCodeWizard`** (CHG-02, row 9, 2026-08-21 — the modal it replaced left
`ChargeCodesTab` in the same commit) · **`PlanDetail`** (PLN-02, row 2,
2026-08-21 — the last of the five details; `…/plans/{id}` opened the PLN-03
builder before it and the builder moved to `…/plans/{id}/edit`).

| Surface | Built | Gap |
|---|---|---|
| PLN-01 landing, 5 tabs | ✅ 4 of 5 tabs | **no Discounts tab** — the model landed, the tab did not |
| PLN-02 plan detail (8 tabs) | ✅ **BUILT 2026-08-21** | `PlanDetail.tsx` — eight tabs over five reads (`GET /plans/{id}` plus one clamped page each of `/rate-schedules`, `/charges`, `/taxes` and the tenant services). What it CANNOT serve is stated on screen with its reason rather than shown as a zero: the plan's version history (DEF-410), which discounts it offers (DEF-412), revenue by plan (DEF-413), the accounts inside/outside split and the exceptions count |
| RAT-02 rate detail (5 tabs) | ✅ **BUILT 2026-08-20** | `RateScheduleDetail.tsx`. ⚠ **This row read `❌ no file` until 2026-08-21** and the paragraph directly above it had named the file since the day it landed — the table was stale against its own prose. Corrected by the PLN-02 lane, which read this census before building from it |
| CHG-01/03 definition detail (charge · discount · tax) | ✅ **BUILT 2026-08-20 · WIRED for all three kinds 2026-08-21** | `DefinitionDetailPage.tsx` + `definitionDetail.tsx`, three routes over one component (BR-RAT-084 settled DEF-353 — one shell, three ids). ⚠ **Stale the same way and corrected the same day** |
| PLN-03 plan wizard (8 steps) | ✅ `PlanWizard.tsx` | earlier form; CR-013 upgrades it |
| RAT-03 rate wizard (5 steps) | ✅ `RateScheduleWizard.tsx` | UoM free-text (DEF-355); no per-size matrix (DEF-356) |
| **CHG-02** | ✅ **BUILT 2026-08-21** | `ChargeCodeWizard.tsx` — the full-page 3-step wizard, §8's shell, both doors wired from the tab. The modal is deleted; `ChargeCodesTab`'s E2 exception is CLOSED. Gaps it exposed: DEF-372 (fixed — `is_base` was unsettable), DEF-373 (eight part-2 fields have no column), DEF-374 (no breadcrumb leaf), DEF-375 (no draft state), OQ-286 (four stored types against CR-013's five) |
| DIS-02 · TAX-02 wizards | ❌ | TAX-02 is still a `FormModal` inside `TaxesFeesTab`; DIS-02 does not exist. Both share CHG-02's chassis (§18 "Shared shells") — `WizardFrame` + `PageHeader`, as `ChargeCodeWizard.tsx` now demonstrates |
| **TAX-02 tax wizard (4 steps)** | ✅ `TaxWizard.tsx` (2026-08-21) | full-page route, `?step=` in the URL; six part-4 capabilities have no column or no endpoint and are named on screen (DEF-380…DEF-387) |
| CHG-02 · DIS-02 wizards | ❌ | CHG-02 exists only as a modal form inside `ChargeCodesTab` (a recorded E2 exception) |
| PLN-01 landing, 5 tabs | ✅ **5 of 5 (2026-08-21)** | was *"4 of 5 tabs — **no Discounts tab**, the model landed and the tab did not"*. `DiscountsTab.tsx` closed it, and with DIS-02 its three write doors are live too. What remains on this row is §18's own **OQ-286**: the strip draws r10's five and Rate changes is a sixth surface reached by a top-right button |
| PLN-02 plan detail (8 tabs) | ❌ | no file |
| RAT-02 rate detail (5 tabs) | ❌ | no file |
| CHG-01/03 definition detail (charge · discount · tax) | ❌ | no file; and §DEF-353 asks whether it is one screen or three |
| PLN-03 plan wizard (8 steps) | ✅ `PlanWizard.tsx` | earlier form; CR-013 upgrades it |
| RAT-03 rate wizard (5 steps) | ✅ `RateScheduleWizard.tsx` | UoM free-text (DEF-355); no per-size matrix (DEF-356) |
| **CHG-02** | ✅ **BUILT 2026-08-21** | `ChargeCodeWizard.tsx` — the full-page 3-step wizard, §8's shell, both doors wired from the tab. The modal is deleted; `ChargeCodesTab`'s E2 exception is CLOSED. Gaps it exposed: DEF-372 (fixed — `is_base` was unsettable), DEF-373 (eight part-2 fields have no column), DEF-374 (no breadcrumb leaf), DEF-375 (no draft state), OQ-286 (four stored types against CR-013's five) |
| **DIS-02** | ✅ **BUILT 2026-08-21** | `DiscountWizard.tsx` — the full-page 5-step wizard, §8's shell, all three doors wired from the tab plus the definition detail's `Edit`. The write half of the API landed with it (`POST /discounts` · `POST /discounts/{id}/versions`), both pure delegation to the 🔒 services. Gaps it exposed: DEF-400 (submit/approve/activate are built and mounted on no route, so a draft can never go live), DEF-401 (no `update_discount` — the bill line label is unchangeable), DEF-402 (nothing computes the mandatory impact analysis, which is also BR-RAT-091's missing input), DEF-403 (no before/after preview), DEF-404 (no eligibility rule builder, and nothing evaluates a rule), DEF-405 (backdating and the enrolment window have no column), DEF-406 (r10 draws no badge for this wizard at all), **OQ-290** (two signed second-approval rules, $500/mo projected vs a $10,000 budget cap), OQ-291 (a usage allowance has no unit), OQ-292 (a rate override has no target) |
| TAX-02 wizard | ❌ | TAX-02 is still a `FormModal` inside `TaxesFeesTab`. Both share CHG-02's chassis (§18 "Shared shells") — `WizardFrame` + `PageHeader`, as `ChargeCodeWizard.tsx` now demonstrates |
| PLN-04 change an account's plan | ❌ | Accounts module |

**AMENDED 2026-08-21: 8 of 13 views exist in some form** — was *"roughly 5 of 13 …
the three detail pages are the largest single hole"*. The Discounts tab, the shared
definition detail, CHG-02 and DIS-02 all landed on 2026-08-21. **The largest single
hole is now the two remaining wizards' siblings and the plan/rate details** (PLN-02,
RAT-02, TAX-02, PLN-04), and the Versions tab (§10) still has no read on any kind —
no definition VERSION LIST is served, which is why every Versions tab states what it
waits for rather than rendering an empty table.

### Endpoints — 22 handlers on `apps/rating/api.py`

⚠ **AMENDED TWICE ON 2026-08-21: 18 → 20 → 22.** The DIS-02 lane added `POST
/discounts` and `POST /discounts/{id}/versions` — the write half, mounted only once
its screen existed, and both pure delegation to services that already existed. There
is deliberately **no `PATCH /discounts/{id}`**: BR-RAT-078 makes an edit a NEW DATED
VERSION, so a PATCH route would invite the in-place overwrite the rule forbids. The
read-API lane's own note, which the write half fulfils, follows.

⚠ **AMENDED 2026-08-21 (CR-013 discounts read-API lane): 18 → 20.** `GET
/discounts` and `GET /discounts/{id}` are the two new ones, and they close the
row this section's own last sentence named — *"nothing serves … a definition
detail"* is now true only of the VERSION LIST and the impact analysis. Both are
GET; the DIS-02 wizard (row 12) has no write route and that is deliberate, so
the verb counts move by two GETs and nothing else.

Verbs across the module: **8** × GET · 8 × POST · 5 × PATCH · 4 × DELETE (plus
the `/lookups/{list}` handlers rating owns for `charge_codes` and
`tax_jurisdictions`, served through tenancy's framework per BR-TEN-031). **Still
not served**: a plan detail, a version list for any object, and an impact
analysis. The **definition detail** is served for all three kinds now — charge
and tax through `charge_item`/`tax_item`, which answered GET since W1, and the
discount through `discount_item`.

### Tables — 26 exist, 5 more planned

**Live** (`db_table`, from `models.py` + `discounts.py`):

`rate_plans` · `tariffs` · `tariff_versions` · `rate_seasons` · `rate_tiers` ·
`time_of_use_windows` · `capacity_rates` · `demand_rate_config` · `charges` ·
`tax_jurisdictions` · `taxes` · `plan_services` · `plan_rate_schedules` ·
`plan_charge_rules` · `plan_deposit_rules` · `plan_penalty_rules` ·
`plan_tax_rules` · `plan_discount_rules` · `rate_change_batches` ·
`rate_change_log` · `unit_plan_assignments` · **`discounts`** ·
**`discount_versions`** · **`discount_enrolments`** ·
**`discount_enrolment_documents`** · **`discount_grants`**

The six bold ones arrived with `0009_cr013_discounts.py` and are the reason §A2's
"no discounts table" line is stale (§15).

**Planned by §B3 and NOT built:** `charge_code_amounts` (per-size rows) ·
`tax_exemption_certificates` · `tax_premises_scopes` · `approval_requests` ·
`rate_calendar_entries`. **And §B3 is itself incomplete** — it omits the per-size
dimension on `rate_tiers` and on `minimum_bill` (DEF-360).

**Column-level status that changes what can be built:** `tariff_versions.base_charge`
and `.minimum_bill` are **scalars** · `rate_tiers` has **no size FK** ·
`charges.amount` is a **scalar** · `charges.gl_account_id` and
`taxes.liability_gl_account_id` are **deferred FKs** (`UUIDField`, no constraint)
until `ledger_accounts` lands in W5 · `tax_jurisdictions` has **no `code` and no
active column** (both flagged as candidate schema additions in `lookups.py`).

### Seed data — yes, it changes. Four ways.

Beyond §11's version-history gap (DEF-357), all still true:

1. **Version history** — one version per object today, so no Versions tab is walkable.
2. **Discounts** — six tables exist and the seeded tenant has **zero rows**. DIS-01,
   DIS-02 and the discount detail have nothing to render.
3. **Per-size rows** — nothing to seed until `charge_code_amounts` and the schedule's
   size dimension exist. r10's five-row water matrix is the obvious fixture.
4. **The six §B4 accounts** — out-of-county premises, commercial 2″ meter, industrial
   demand, fire-line premises, two stacked discounts, expired exemption certificate.

**Not a seed problem:** `uoms` (26 rows) and `service_size_classes` (**40 rows** since
BR-TEN-171, 9 before it) are fully seeded. DEF-355 and DEF-356 are wiring, not data.

### E2E — the closure bar is unmet

**`07-frontend/e2e/` contains no `CR-013-*.spec.ts`.** The PO's standing bar is
*"everything should be passed only when web walkthrough is confirmed"*, and §B4
Tier 4 sizes it at 16 screens each walked. Two constraints on writing them:

* **Evidence by route + heading text, never by screen ID** (§2) — the IDs collide
  (`PLN-plan`, `PLN-rate`, `CHG-01` ×3, `NEW-01` ×5).
* **Several journeys cannot be walked until the seed changes** — a Versions tab with
  one row, a Discounts tab with no rows, and a rate matrix with no sizes are not
  walkthroughs, they are empty states.

**Existing specs that will need updating rather than replacing:**
`CR-016-screen-ids.spec.ts` (the ID collisions are its subject),
`CR-018-rate-schedules-visual.spec.ts`, `CR-016-ui-conformance.spec.ts`, and
`CR-010-seed-completeness.spec.ts` (its pinned counts move when the seed does).

## 18 · EVERY SURFACE, ENUMERATED — 16 of them, NEW or UPGRADE (PO, 2026-08-20)

> **"Many screens are missing … Landing page, Wizard, Detail view for every items -
> many screens are not mentioned in your list - please list down everything - what
> is new and what is upgrade"**

§17's table was wrong to collapse them. **Five objects × three surfaces = 15, plus
PLN-04 = 16** — which is exactly §B1's *"16 screens"* and §B4 Tier 4's *"16
screens, each walked"*. Here they are one per row.

> **PO disposition, same session:** *"you can build them; engineer them to reduce
> the screens and code; Im okay with that; from product management point of view,
> i need to know you are considering everything."* **Reduction by shared shell is
> AUTHORISED** — what is not authorised is an enumeration that hides a surface.
> Every row below is listed whether or not it gets its own file.

| # | Object | Surface | ID | Today | **NEW / UPGRADE** | The delta |
|---|---|---|---|---|---|---|
| 1 | Plans | Landing tab | `PLN-01` | `PlansTab.tsx` | **UPGRADE** | + Base charges column · 4 statuses (+ Closed to new enrolment) |
| 2 | Plans | Detail | `PLN-02` → emits `PLN-plan` | ✅ **BUILT 2026-08-21** — `PlanDetail.tsx`, route `…/plans/{id}`, screen ids **S10 · PLN-02** | ~~NEW~~ **DONE (with four gaps named)** | 8 tabs · pending-component surfacing · Versions — all three built. The plan's NAME opens the record and the PLN-03 builder moves to `…/plans/{id}/edit`, the same move RAT-02 made. **The pending-component surface is REAL, not stated-absent:** `schedule_card.scheduled_change` is the effective date of the earliest ACTIVATED version whose window opens after today, which is exactly "a version that will price this plan and is not pricing it yet" — drawn as a banner above the tabs AND as its own column. What it cannot show is stated on the tab: an active schedule's saved DRAFT is suppressed by `schedule_card` and so never reaches it. Gaps it exposed: **DEF-410** (no plan version history — `rate_plans.version` is a scalar, so the Versions tab holds one row), **DEF-411** (`plan_charge_rules.amount_override` and `plan_tax_rules.rate_override` let a plan PRICE, which part 5 forbids — marked on screen, not removed, because BR-RAT-043 gives one of them a ratified use), **DEF-412** (`plan_discount_rules` is read by no endpoint, so the Discounts tab has no source), **DEF-413** (no revenue-by-plan read for the second KPI), **OQ-295** (four plan statuses in the CR, three stored) |
| 3 | Plans | Wizard | `PLN-03` (⚠ **NOT** `NEW-01` — that string appears nowhere in r10; DEF-406) | ✅ **`PlanWizard.tsx`, 8 steps, DRAWN TO r10 2026-08-21** | ~~UPGRADE~~ **DONE (with seven divergences stamped and eight defects named)** | was *"**6 → 8**: the built `rules` step splits into **Charges · Taxes · Discounts & billing**"*, and the split landed — but the STEPS were built from CR-013 part 5's prose, which says what each must ANSWER and never what it must LOOK like, so every one of the eight diverged from the drawing and the PO reported all eight (`DEF-462`). Now: step 1 is r10's field order with `code | customer class` in one two-column row and r10's customer-facing copy (ours claimed the opposite — that the NAME is what staff pick from a list); step 2 a **3-column tile grid of enabled services only** (`BR-RAT-095`); step 3 r10's four-column table `SERVICE | RATE SCHEDULE | BASE CHARGE | GL`; steps 4, 5 and 6 the **two-pane search-and-add** the PO asked for by name; step 7 the **`Attribute · Operator · Value` builder** (`BR-RAT-097`); step 8 the **`Edit` jump-back links**, which are the point of its own subtitle and were entirely missing, plus r10's Save-it panel. **Three PO rulings implemented, one sentence behind all three: *"plan all steps are bascailly binding everything together"*.** ⚠ **SEVEN PLACES DO NOT MATCH r10 AND EACH IS A RULE OUTRANKING THE DRAWING — the table is in §8** (`DEF-456` carries the four money controls r10 draws that ratified rules forbid, chiefly the step-3 base input at **`$23,069.50`/month**). ⚠ **A LIVE MONEY FIX RODE WITH IT:** step 6 rendered a hard-coded **`$500`** second-approval bar that `BR-RAT-077` had made a tenant setting and the PO had raised to **`$50,000`** hours earlier; it reads the setting now, and names **no figure at all** when the role cannot read it (`/settings/finance-controls` is AdminOrExecutive; a Billing Clerk has View on Plans & Rates). ⚠ **Unreachable on the live tenant for reasons that are not this screen's:** no `is_base` charge codes seeded (`DEF-455`), no tax jurisdictions (`DEF-459`), no customer class on any seeded plan (`DEF-452`). Also named: `DEF-457` (no account MATCH count), `DEF-451` (no plan-level tax exemption), `DEF-453` (BR-RAT-096 says *codes*, the column holds a *jurisdiction*), `DEF-454` (no served eligibility-attribute list), `OQ-300`, `OQ-301`, **`OQ-304`** (does an eligibility rule BLOCK? `BR-RAT-043` says advisory and stands) |
| 4 | Rate schedules | Landing tab | `RAT-01` | `RateSchedulesTab.tsx` | **UPGRADE** | ✅ DONE 2026-08-21 (DEF-441) — **r10's NINE-COLUMN TABLE** (r10 line 764: Schedule · Svc · Structure · Sizes · Seasons · Plans · Accounts · Effective · Status), all nine sortable, **IS-5 APPLIES**, + CSV export. ⚠ This cell read *"stays a CARD GRID (EP-RAT-02, IS-5 N/A — ratified)"* until 2026-08-21 and **that was false** — see §12. |
| 5 | Rate schedules | Detail | `RAT-02` → emits `PLN-rate` | — | **NEW** | 5 tabs · the per-size matrix · Versions & filings (7 columns) |
| 6 | Rate schedules | Wizard | `RAT-03` → emits `NEW-01` | ✅ **UPGRADED 2026-08-21** — `RateScheduleWizard.tsx`, now genuinely **5 steps** | **UPGRADE — LANDED, with four gaps named** | UoM → select over `uoms` ✅ (DEF-355 CLOSED) · per-size matrix ✅ (DEF-356 CLOSED; step 2 is NEW — the file had **four** steps, not the five this row claimed) · `Base only` drawn DISABLED with its reason ⚠ (DEF-297 stays OPEN — nothing prices it) · mandatory impact analysis ✅ **all four figures SERVED as of 2026-08-21 (DEF-434 CLOSED)** — `GET /rate-schedules/{id}/impact` prices every affected account twice through `engine.price_period`; step 4 draws accounts affected + the BY-PLAN breakdown, worst-case and average bill change, the annualised revenue change, and how many of the affected accounts could be priced at all · BR-RAT-091's `10%` bar ✅ **enforced server-side (DEF-435 CLOSED)** — `services._guard_rate_change_second_approval` refuses a filing above it and the screen prints the verdict with the measured percentage; on our own numbers a **+6%** water filing (`$59.00 → $62.54`) flows and a **10.5%** repricing is refused ⚠ **and the refusal itself is `OQ-318`**, because BR-RAT-031 as-modified left nowhere for a second approval to land · BR-RAT-082's filing capture ✅ (authority · submitted · approved · approver, four new columns) · remaining: DEF-431 (one scalar base for every size) · DEF-432 ("increase all by %") · DEF-433 (per-size tier rates — the 2″ row) · DEF-436 (worked example at low/typical/high usage) · the **per-CUSTOMER-CLASS** cut part 1 asks for is still unserved and is named on the screen rather than answered with the by-plan one (`OQ-319`) |
| 7 | Charge codes | Landing tab | `PLN-01.charges` | `ChargeCodesTab.tsx` | **UPGRADE** | + 5 types · Outside city + GL **hidden by default** |
| 8 | Charge codes | Detail | `CHG-01` | — | **NEW** | 5 tabs · per-size Amounts with computed outside-city |
| 9 | Charge codes | Wizard | `CHG-02` → emits `NEW-01` | **a `FormModal` inside the tab** | **UPGRADE → NEW shape** | modal → **3-step full page**. A recorded E2 exception becomes the spec |
| 10 | Discounts | Landing tab | `PLN-01.discounts` | **`DiscountsTab.tsx` — BUILT 2026-08-21** | ~~NEW~~ **DONE** | was *"the tab does not exist; the 6 tables do"*. Nine columns over `GET /discounts`. Was *"read-only: `+ New discount` is drawn disabled with its reason until row 12 exists"* — **row 12 exists (2026-08-21), so all three doors are open**: the header button, the empty-state CTA and a new row-actions column with a single `✏` opening `…/{id}/edit`, all three routed through `definitionWizardPath`. Only the RBAC guard remains, and the catalogue key that carried the wizard-is-not-built sentence is DELETED in all eleven locales rather than left to be read as a decision (hard-won law 1). Duplicate and Retire are still not drawn — neither has a route on any definition kind |
| 11 | Discounts | Detail | `CHG-01.discount` | **the shared shell, WIRED 2026-08-21** | ~~NEW~~ **DONE (with one gap named)** | the shell shipped with CR-013 P2 and had no read; `GET /discounts/{id}` serves it now. Its 5 tabs are `overview · value · applicability · plans · versions` — **Enrolled accounts and Budget & usage are NOT separate tabs**: BR-RAT-084 fixes the count at five, so the budget, the three caps, the floor and the precedence render inside `Value & rules`, and enrolment appears as a COUNT only (BR-RAT-079 — no account, no document) |
| 9 | Charge codes | Wizard | `CHG-02` → emits `NEW-01` | ✅ **BUILT 2026-08-21** — `ChargeCodeWizard.tsx`, routes `…/charge-codes/new` and `…/{id}/edit`, screen ids **S12 · CHG-02** | **UPGRADE → NEW shape** | modal → **3-step full page**, done. The E2 exception became the spec and is CLOSED. **Ten of §8's twelve parts are drawn**; part 1's breadcrumb leaf (DEF-374) and part 12's left-hand `Cancel` (the shared `WizardFrame` right-aligns its row for ten wizards) are reported, and Cancel sits in the header as it does on RAT-03 and PLN-03 |
| 10 | Discounts | Landing tab | `PLN-01.discounts` | **nothing** | **NEW** | the tab does not exist; the 6 tables do |
| 11 | Discounts | Detail | `CHG-01` (`cdKind=disc`) | — | **NEW** | 5 tabs incl. Enrolled accounts · Budget & usage |
| 12 | Discounts | Wizard | `DIS-02` → **emits NOTHING** (r10 has no branch for it — DEF-406) | ✅ **BUILT 2026-08-21** — `DiscountWizard.tsx`, routes `…/discounts/new` and `…/{id}/edit` | ~~NEW~~ **DONE (with three questions and seven defects named)** | was *"5 steps · the eligibility rule builder"*, and it was **the only one of the sixteen that existed in no form at all** — no modal, no form, no route. Five steps, CR-013 part 3's own labels, §8's shell. The write half of the API landed with it (`POST /discounts` · `POST /discounts/{id}/versions`), both pure delegation to the 🔒 services this lane did not edit. **Ten of §8's twelve parts are drawn**; part 1's breadcrumb leaf (DEF-374, shared with CHG-02) and part 12's left-hand `Cancel` (the shared `WizardFrame` right-aligns its row for ten wizards) are reported, and Cancel sits in the header as it does on CHG-02, RAT-03 and PLN-03. Part 6 is absent on purpose — see §8. **The eligibility rule builder is NOT built and is named on the control (DEF-404):** `eligibility_rule` is stored as authored and nothing evaluates one, so the step offers the plain-language summary DIS-01's Eligibility column actually renders. Also named rather than omitted: the lifecycle (DEF-400), the unchangeable identity (DEF-401), the mandatory impact analysis (DEF-402), the before/after example (DEF-403), backdating and the enrolment window (DEF-405), and the `named_codes` scope (DEF-388, the write lane's). **OQ-290** is the one with money on it — two signed rules give the second-approval test two quantities and two figures |
| 13 | Taxes & fees | Landing tab | `PLN-01.taxes` | `TaxesFeesTab.tsx` | **UPGRADE** | + rate-calendar strip · 4 statuses · **no status column today** |
| 14 | Taxes & fees | Detail | `CHG-01` (`cdKind=tax`) | — | **NEW** | 6 tabs incl. Rate history · Remittance · Exemptions |
| 15 | Taxes & fees | Wizard | `TAX-02` → emits `NEW-01` | ✅ **`TaxWizard.tsx`, built 2026-08-21** | **DONE (was UPGRADE → NEW shape)** | modal → **4-step full page** ✅ · premises scope + customer classes ✅ (closes DEF-292) · matched premise count ❌ no endpoint (DEF-380) · compounding ❌ no column, and it contradicts BR-RAT-036 (DEF-381) |
| 16 | Accounts | Change an account's plan | `PLN-04` | — | **NEW** | 3 steps · proration + **deposit differential** |

**Tally: 9 NEW · 7 UPGRADE**, of which **rows 2, 10 and 11 are DONE as of
2026-08-21** — 6 NEW remain (rows 8, 12, 14, 16, and the two upgrades below that
are new work). ⚠ **Row 2 is DONE as a SURFACE and four of its facts are absent
by defect** (DEF-410 · DEF-412 · DEF-413, plus the accounts split and the
exceptions count) — each is stated on the screen with its reason, so "done"
here means the screen exists and tells the truth, not that every figure r10
draws is served. Two of the seven upgrades (#9, #15) are upgrades only
**Tally: 9 NEW · 7 UPGRADE**, of which **rows 10, 11 and 12 are DONE as of 2026-08-21** (and row 9 of the seven upgrades) — **6 NEW remain**: the plan detail (2), the rate-schedule detail (5), the charge-code detail (8), the tax detail (14), the tax wizard (15) and PLN-04 (16). Two of the seven upgrades (#9, #15) are upgrades only
in the sense that a form exists — the shape changes from modal to full-page wizard,
so budget them as new work.

### ⚠ A SIXTH TAB IS BUILT THAT r10 DOES NOT DRAW — now **OQ-286**

⚠ **AMENDED 2026-08-21.** Discounts is BUILT (row 10), so half of this section is
history and the other half is a live question. What was written here:

```
built (until 2026-08-21):  Plans · Rate schedules · Charge codes · Taxes & fees · RATE CHANGES
r10:                       Plans · Rate schedules · Charge codes · DISCOUNTS   · Taxes & fees
built (now):               Plans · Rate schedules · Charge codes · DISCOUNTS   · Taxes & fees   + Rate changes
```

**And the shape of the divergence is smaller than "six tabs", which matters to the
answer.** `RATING_TAB_STRIP` draws **five** — r10's five, with Discounts in r10's
own position between Charge codes and Taxes & fees. Rate changes has never been in
the strip: it is a top-right `History` button, because *"History is a DESTINATION,
not another view of these records"*. So a user sees **five tabs and one button**
against r10's five tabs and no button.

`RateChangesTab.tsx` exists, is wired, has no counterpart in the drawing, and is
also not in BR-SHL-001's ratified four-child sidebar list. r10's rate detail
carries a **Versions & filings** tab which may be where rate changes belong —
though that tab is ONE schedule's filings and Rate changes is every change across
every object including the bulk batches, so a move is a re-scope, not a
relocation.

**Neither the addition nor the removal is decided, and the Discounts build did not
decide it: `OQ-286` is now open with three costed options, and
`PlansRatesPage.test.tsx` asserts Rate changes is still present so a later lane
cannot resolve it by deletion.**

### Shared shells the reduction can legitimately use

Named so the count above stays honest while the file count falls:

* **Rows 8 · 11 · 14** are r10's one `CHG-01` shell switched by `cdKind` — **three
  surfaces, one file** (DEF-353 asks whether the specs should say so; the PO's
  disposition above authorises the reduction).
* **Rows 9 · 12 · 15** share a wizard chassis — step rail, `STEP n OF m`, footer,
  draft/activate — differing only in step content: 3 · 5 · 4.
* **Rows 1 · 7 · 10 · 13** are one config-driven `DataTable` (IS-5) with different
  column configs. ~~**Row 4 is deliberately not** — it is a card grid.~~ ❌ Corrected
  2026-08-21 (DEF-441): **row 4 IS a column config** — r10 line 764's nine columns,
  all sortable, with the IS-5 chooser r10 draws in its own toolbar.

## 19 · THE BLOCKING RULINGS — worked examples and options (PO, 2026-08-20)

> **"please give examples and options for all blocking items"**

Seven. Each with the figure and the choices; **none may be resolved by a lane.**

### B1 · Where does the base charge live? — **THREE claimants, not two**

**The conflict, dated.** `BR-RAT-012` and `BR-RAT-027` (both **CONFIRMED**) say the
base *"is defined **per service within a plan**"*. `tariff_versions.base_charge` is
a column on the **rate schedule** and is what the product actually read until
2026-08-16. Design **§A3** (2026-08-19) rules the **charge code** owns it. `OQ-238`
raised the first pair; §A3 answered a question nobody had asked in those terms.

**Worked:** a 5/8″ residential water account. Plan says base `$12.00`; schedule's
matrix says `$12.00`; charge code `BASE-W` says `$12.00`. Charge two of the three
and the bill is **`$24.00`** — §A3's own arithmetic, **`$23,069.50` per month
across 1,247 connections**, and every row individually correct.

* **(A) Charge code owns it** — §A3 as written; schedule + plan display it
  read-only and attributed (`$12.00 · from BASE-W`). Consistent with BR-RAT-080.
  Costs: `charge_code_amounts` built, `tariff_versions.base_charge` retired, and
  BR-RAT-012/027 **superseded with a dated note** (they are CONFIRMED, so this is
  a supersession, not a correction).
* **(B) Plan owns it** — honours the two signed rules unchanged; but a plan that
  prices contradicts part 5's *"a plan composes; it does not price"*, the
  load-bearing sentence of all five parts.
* **(C) Schedule owns it** — matches what the code does today and r10's matrix;
  contradicts both §A3 and the two signed rules.

**Recommendation (A)**, and it is the only one consistent with a rule already
ratified. **What it costs is a supersession of two CONFIRMED rules, which is the
PO's call.**

### B2 · Approval workflow — a signed ruling removed it and r10 draws it

**Decision log 2026-08-08:** *"R5 sweep CLOSED: **board approval out-of-system
(workflow removed)**"*, flipping BR-RAT-030..040. **And r10 draws approval
everywhere**: RAT-03 step 4 is *Effective & approval*, with a *"Requires regulator
approval"* checkbox and the toast *"Filed for approval · activates when the
regulator signs off"*; the Versions & filings tab carries **`BY`** and a docket;
CR-013 parts 1/3/4 all specify *Submit for approval*; **EP-RAT-16 exists as an
epic with 6 stories and 22 test cases**.

**The reconciliation nobody has offered:** the 2026-08-08 ruling says **BOARD**
approval is out-of-system. That is not the same act as an **internal** submit →
approve, which part 1 states plainly — *"Owner/Admin activate, Billing drafts."*

* **(A) Both, and they are different acts.** The board/regulator signs **outside**
  the product; the product records the **filing reference** (`PUC #W-2025-1184`)
  and runs its own **internal** two-role gate. Nothing signed is reversed —
  BR-RAT-030..040 removed the board workflow, not the internal one.
* **(B) Internal only** — drop the docket fields; r10's *"filed for approval"*
  toast becomes wrong copy.
* **(C) Neither** — honour 2026-08-08 literally, delete EP-RAT-16, and Billing
  staff activate their own filings. Cheapest, and it removes the only control over
  who may change 1,247 accounts' prices.

**Recommendation (A).** **Worked:** Billing drafts v4 at +6% → submits → Owner
approves → status `Draft` until Jan 1 2027 → activates. The regulator's sign-off
is a **date and a docket number typed in**, not a workflow step.

### B3 · Role permissions

Part 1 gives one split — *"Owner/Admin activate, Billing drafts"* — and nothing
covers the other four objects, PLN-04, or waivers.

**Worked:** a Billing clerk waives a `$30.00` NSF fee. Part 2 says the waiver
policy governs *"whether front-line staff can waive it and whether a supervisor
and reason code are needed"* — per charge code. So the answer is per-object, not
one matrix.

* **(A) Two acts, all five objects** — anyone with the module may **draft**;
  Owner/Admin **activate**. One rule, five objects, matches part 1.
* **(B) Per-object matrix** — finer, five times the surface, and every new object
  needs a ruling.
* **(C) (A) plus money-threshold exceptions** — e.g. a discount above a subsidy
  threshold needs a second approval (part 3 already asks for this and **the
  threshold figure is not given and must not be guessed**).

**Recommendation (A) now, (C) when the threshold is ruled.**

### B4 · Definition detail — one shell or three screens? (DEF-353)

r10 emits **`CHG-01`** for all three; the specs describe three detail pages.
**The PO's disposition this session authorises the reduction**, so this is now a
documentation choice rather than a build choice — but it still needs stating,
because the tab counts differ: charge **5**, discount **5**, tax **6**.

* **(A) One shell, three configs** — one file, `cdKind` switches title, KPI tiles
  and tab set. Cheapest, matches the drawing.
* **(B) Three routes over one shared shell component** — same code, three URLs, so
  a walkthrough can evidence each and deep links work.

**Recommendation (B)** — it costs nothing over (A) and restores per-object
evidence for the closure bar.

### B5 · Who owns the charge code — Settings or Plans & Rates? (OQ-282)

`lookups.py` already draws the line: the reference card *"mints and renames the
CODE, while the money-bearing fields … belong to rating's own endpoints. A
reference card that could set an amount would be a back door into B4-governed
money configuration."*

* **(A) Keep both, as built** — Settings mints/renames the code, Plans & Rates
  owns amounts, GL, versions. Already implemented and already documented.
* **(B) Settings card becomes a `kind: "link"`** — navigation only, precedent
  BR-TEN-033 (templates). One home, one less way to be confused.
* **(C) Retire the card.**

**Recommendation (A) with (B)'s label made explicit on the card**, so an operator
reading Settings knows amounts live elsewhere.

### B6 · Capacity charge — the one that crosses a frozen figure (DEF-363)

`CapacityRate` (a **GT-15** consumer) and charge code `CAP-W $22.00` both express
it. BR-RAT-080 reads it as a **thing** → charge code, but **B5 is ❄️ FROZEN**.

* **(A) Move to the charge code** — consistent with the ratified rule; **requires
  a finance re-sign via HUMAN-GUIDE §6.**
* **(B) Keep on the schedule and retire `CAP-W`** — changes no frozen figure.
  `CAP-W` is **not in the live tenant's 23 charge codes**, so nothing is lost.
* **(C) Split** — the reserved per-unit rate on the schedule, a one-time
  connection capacity fee as a charge code. Two objects, two meanings, no overlap.

**Recommendation (B) now** — it removes the duplication at zero cost to a frozen
path — **with (A) revisited if a tenant needs capacity on a bill without a
schedule.**

### B7 · "Amounts 2 decimals, percentages 4" vs ❄️ FROZEN B4

Part 2 states it. B4 is frozen at `NUMERIC(18,6)`, rounding only at finalisation.

**Worked:** `1.5%` of `$100.58` is `$1.5087`. Stored at 2dp it is `$1.51` and the
sixth decimal is gone forever; stored at 6dp and displayed at 2dp the bill reads
`$1.51` and the stored value stays `1.508700`.

* **(A) Display-only** — a restatement of B4, no re-sign, nothing changes.
* **(B) Storage** — a change to a finance-signed figure. **The change process says
  STOP and re-sign via HUMAN-GUIDE §6.**

**Recommendation (A)** — it is what B4 already requires and what the code does.
**But only the PO can say which was meant**, which is exactly why this is here and
not in a lane.

## 20 · THE IMPLEMENTATION PLAN (PO, 2026-08-20)

> **"please add implementation plan to document and show me"**

Written after the six rulings of 2026-08-20, so it plans the product as decided
rather than as proposed. **Every phase follows engineering-plan Addendum r11** —
packet · build (backend · **frontend** · tests+data · prove it) · self-verify ·
close the record · human review · merge — and **step 2b is why no phase below
ships a backend without its screen.**

### What gates what

```
P0 ─ unblock ──► P1 ─ engine ──► P2 ─ charge codes ──► P3 ─ schedules ─┐
                                                        P4 ─ taxes ────┼─► P6 ─ plans ─► P7 ─ PLN-04
                                                        P5 ─ discounts ┘
```

`P3 · P4 · P5` are independent of each other and can run in parallel. **`P6`
composes all four and cannot start early.**

### P0 · Unblock — nothing here is a screen

Small, and everything after it is cheaper. **Ship as one release.**

| # | Work | Why first | Ref |
|---|---|---|---|
| 1 | **Server-formatted money + percent strings**; percent renders `1.50%`, money `$1.51` | BR-RAT-087's display half, ratified. **Do not scale in the component** — that is the client-side money arithmetic the code correctly refuses | DEF-364 · DEF-291 · BR-SHL-034 |
| 2 | **Wire `resolve_discounts`** to the six tables that already exist | Its refusal states something false today; ~8 lines | DEF-361 |
| 3 | **`metered` on `tenant_services`**, R3b branches on it ⚠ **`tenant_services.metered` IS NOW `tenant_services.billing_basis` AND CARRIES THREE VALUES — `BR-TEN-1180`, PO ruling 2026-09-02, closing `DEF-2409`** (`metered` · `share` · `capacity`). This rule is unchanged in substance: `capacity` is precisely what the old `metered=False` meant, and `TenantService.metered` survives as a read-only property, so every reader and every signed figure stands. The value it must NOT be read as is `share` — sewer is a percentage of the water usage charge (`BR-RAT-015`) and has no assets to count. | Unblocks **every** unmetered service, not just trash | BR-RAT-081 · DEF-161 |
| 4 | **Version history in the seed** — one object with superseded · current · dated draft | Without it no Versions tab is walkable and DEF-280 has no fixture | DEF-357 |
| 5 | **The IS-5 column panel** — wire the existing `toggleColumnVisible` | The logic is built and tested; it needs a door | DEF-358 |

⚠ **P0 cannot start item 3's sibling — the cart COUNT — until `OQ-283` is ruled.**
The declaration lands; where the number comes from does not.

### P1 · The resolution engine · EP-RAT-15

Before any screen, per §B5 — *"the engine is what makes every screen mean
something."*

* **The size axis, both objects** — `charge_code_amounts` (per-size, the base
  lives here) and a size dimension on `rate_tiers` + `minimum_bill`. **§B3 omits
  the tier half; correct §B3 in the same commit.** (DEF-356 · DEF-360)
* **Move the base to the charge code** — retire `TariffVersion.base_charge`,
  `ScheduleVersion.size_rows` stops carrying it. **Blocked on B1**, the one
  ruling still open. (DEF-359)
* Keep R3/R4's two refusals exactly as they are — the control flow is already right.
* **Unmetered quantities** in R3b once OQ-283 lands.

### P2 · Charge codes · EP-RAT-11

Second, because *"base-charge ownership is settled and every other object
references it."*

* **Row 7** landing — 5 types, outside-city + GL **hidden by default**.
* **Row 8** detail — the first use of the **shared definition shell** (BR-RAT-084).
* **Row 9** wizard — `FormModal` → **3-step full page**. Budget as new.
* The Settings card gets its label: mints the code, **not** the amount (BR-RAT-085).

### P3 · Rate schedules · EP-RAT-10 — parallel

* **Row 5** detail — the per-size matrix, base column **read-only and attributed**.
* **Row 6** wizard — UoM becomes a select over `uoms` (DEF-355); the per-size
  matrix; the mandatory four-figure impact analysis; `Base only` registered
  (DEF-297).
* ~~**Row 4** landing stays a **card grid** — ratified, IS-5 N/A.~~ ❌ **FALSE — corrected
  2026-08-21 (DEF-441).** r10 line 764 draws a nine-column `<table class="table lt">`
  and its toolbar carries the column-chooser glyph. Row 4 is a table and **IS-5
  applies**; the word "ratified" on a wrong statement is what sent a lane to build
  the card grid. See §12.
* **Approval per BR-RAT-082**: internal submit → approve, plus docket/authority/
  dates **captured and kept**.

### P4 · Taxes & fees · EP-RAT-13 — parallel

`tax_premises_scopes` + `tax_exemption_certificates` — **these are DEF-273 and
DEF-292's fix**, and the three withheld Texas rates can seed once they exist.
Rows 13 · 14 · 15; row 15 is `FormModal` → **4-step page**.

### P5 · Discounts · EP-RAT-12 — parallel

⚠ **AMENDED 2026-08-21: rows 10 and 11 are DONE.** The Discounts landing tab
(`DiscountsTab.tsx`) and the discount half of the shared definition detail are
built over `GET /discounts` and `GET /discounts/{id}` — two new handlers on
`apps/rating/api.py`, both GET. **Row 12 (the DIS-02 five-step wizard) is still
NEW**, and until it exists both surfaces are read-only with `+ New discount`,
Duplicate, Edit and Retire all drawn DISABLED with their reason rather than
hidden.

⚠ **`RateChangesTab` was NOT ruled on before this shipped**, which this line asked
for. It is now `OQ-286`, open with three costed options; nothing was removed or
moved, and a test asserts as much.

### P6 · Plans · EP-RAT-14

Composes all four.

* **Row 3** wizard **6 → 8 steps** — the built `rules` step splits into **Charges ·
  Taxes · Discounts & billing**.
* **Row 2** detail, 8 tabs, and it must surface a **pending component version** —
  the subtlest rule in the CR: a schedule can change the plan's pricing while the
  plan itself has not changed.
  ⚠ **BUILT 2026-08-21, ahead of this phase order and deliberately so.** P6 says
  the plan *"composes all four and cannot start early"*, and that is right about
  the WIZARD (row 3) and about anything that WRITES. It is not true of a
  read-only detail: PLN-02 reads what the four objects already serve, and every
  fact they do not serve is drawn as a stated absence rather than waited for. The
  phase order stands for rows 3 and 16.
  **The pending-component surface is real** — `schedule_card.scheduled_change`,
  drawn as a banner above the tabs and as its own column. The absence it cannot
  cover is stated on the tab: an active schedule's saved DRAFT is suppressed by
  `schedule_card` and never reaches the plan.
* Step 5 stays **read-only by design** — built as the Taxes tab, which renders
  each authority the plan touches and the active taxes it brings, with no
  control of any kind on the tab.

### P7 · PLN-04 · row 16

Three steps, proration **and the deposit differential**. Lives in Accounts.

### Threaded through every phase

* **EP-RAT-16 approval** — its state machine lands with **P1** so all five objects
  inherit one implementation (§B5.6). Second-approval thresholds wait on OQ-284;
  the two-act base rule does not.
* **E2E** — a `CR-013-*.spec.ts` per phase, **evidence by route + heading text**,
  never by screen ID (§2). The closure bar is 16 screens walked.
* **Seed** — grows per phase; §B4's six fixture accounts arrive with the phase
  that needs each.
* **Version** — `<release>.<change>.<fix>` bumped per change-process §7, and
  **the gate refuses a CR marked done with no version.**

### What is still blocking, by phase

| Blocks | Item | Phase |
|---|---|---|
| **P1** | **B1 — where the base lives.** Three claimants, two of them CONFIRMED rules | the engine's data model |
| P0/P1 | `OQ-283` — where an unmetered quantity comes from | CR-019 entirely |
| P1/P2 | `OQ-285` — did *store 4* mean the column or the input? | **decides the column type before `charge_code_amounts` is written** |
| P2/P3 | `OQ-284` — the three threshold figures | second-approval stories only |
| P3 | `BR-RAT-086` — the capacity re-sign | queued behind HUMAN-GUIDE §6 |
| P5 | `RateChangesTab` — keep, move, or retire | the sixth tab |

**Five of the six are one-sentence answers.** B1 is the one that changes the
schema, and it is the only one that should hold up P1.
