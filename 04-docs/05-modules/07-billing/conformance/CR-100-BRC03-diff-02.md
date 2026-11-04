# Billing §02 — THE TWO-WAY DIFF. Every drawn element against the running screen, in both directions

`CR-100-BRC03` step 1 · diffed 2026-09-14 · product version **`v2.261.4`** ·
branch `claude/eager-johnson-r0k88b`

**Step 1 measures and classifies. Nothing here was fixed.** No `.tsx` and no `.py` was edited
by this lane. What it wrote: three defect rows and this file.

---

## What this file is, and the two things it puts side by side

Everything measured in this pass so far has sat on **one side** of a comparison nobody had
made:

| The DRAWN side | The BUILT side |
|---|---|
| `blueprint/01-screens-in-journey-order.md` — §02, p005–p028, **7 entries, 8 drawings, all REDESIGN** | `conformance/CR-100-BRC03-walk.md` — **15 of 15 screens** walked at 1280 and 1440, 8 with real rows |
| *"Nothing here was measured against running code and no screen was walked for this file."* | *"It is not a diff against the drawings — **no drawing was opened by this lane**."* |

This file is the join. It covers §02's seven screens only: **01 All bills · 02 Bill detail ·
02.1 Document · 02.2 Charges · 02.3 Corrections · 02.4 Audit · 02.5 Sent.**

---

## ⛔ THE FRAMING DECIDES WHAT EVERY DIFFERENCE MEANS, SO IT IS FIRST

**All 8 of §02's drawings carry the caption `REDESIGN … NEVER BUILT`.** Every one:

> *"REDESIGN drawn 2026-09-11, still unbuilt at Version 35 (2026-09-13), drawn to B14 31 · B14
> 37 · the Product Owner's 2026-09-11 ruling removing the embedded viewer. **NEVER BUILT.**
> Today the product ships the as-built bills list and bill detail directly below this drawing."*

**So a difference here is NOT drift. It is the redesign not yet built**, and filing it as a
drift defect would convert our own unfinished work into a product fault. Nothing below is
filed as drift. Each difference is routed to exactly one of:

| | |
|---|---|
| **build** | the redesign proposes it and the product lacks it — the expected case, and the bulk of this file |
| **defect** | the product is wrong **on its own terms**, independent of any drawing — it throws, a refusal outlived its screen, or an internal code reaches a clerk. **Three filed, five re-verified** |
| **question** | the drawing contradicts a SIGNED rule, or would move a ❄️ FROZEN B4/B5 figure. **Zero** — see *Questions* at the foot, including the one that looked like one and is already ruled |

---

## ⚠ ONE SIDE OF THE COMPARISON DOES NOT EXIST, AND IT IS A PROPERTY OF THE FILE

Five of §02's seven entries are captioned `TWO REVISIONS` — *"This entry holds **both**: an
AS-BUILT drawing of 2026-09-11 and a REDESIGN that has never been built"*. **The as-built half
is inside a collapsed `<details>` and the PDF renders it closed**, so p009, p017, p019, p023
and p026 each carry the line

    ▶ As built today — kept because the findings below point at it. Do not build this.

and **what follows is a table, never a frame**. Across §02's 24 pages there are eight rendered
wireframes and every one is the REDESIGN.

**Consequence for this file, stated rather than worked around: the BUILT column below is the
running product at `v2.261.4`, measured in Chromium — never the as-built drawing, because there
is no as-built drawing in §02 to measure against.** Where the document's own as-built TABLES
make a claim about today (the six alignment findings on p020, the three audit fixes on p025),
that claim is quoted and **re-checked live**, and the result is marked `RE-VERIFIED` or
`STALE`. Nothing is inferred about what the five hidden frames showed.

---

## How this was measured

* **Every drawing opened AS AN IMAGE** (B14 rule 42) — p007, p008, p014, p015, p016, p018,
  p019, p020, p021, p022, p024, p025, p027, p028 — plus 3 crops rendered from the PDF at 5×–9×
  for the tab strip, the TOTAL column and the EVERY-CHARGE header row, where alignment had to be
  decided in pixels rather than by eye.
* **Every screen opened in Chromium 1194** at 1440×1100 against the running stack, signed in as
  `dana@brazosbendutilities.com`, tenant `brazosbend`, with **92 invoices · 732 invoice lines ·
  3 bill runs · 72 accounts** behind it.
* Per screen the DOM was captured structurally rather than by eye: `h1` and its computed size
  and weight, every tab label and its selected state, every table's column headers **with their
  computed `text-align` and their measured left/right gaps**, the first data row cell by cell,
  every input with its placeholder and label, every button and link with its disabled state and
  title, every `h2/h3/h4` with size and weight, every `<details>` with its open state, and the
  full rendered body text.
* Scripts and raw captures in SCRATCH: `billing-diff-02.mjs`, `billing-diff-geom.mjs`,
  `billing-diff-charges.mjs`, `billing-diff-fixdoor.mjs`, `audit-probe.mjs`, `audit-probe2.mjs`;
  results in `diff02/capture.json`, `diff02/geom.json`, `diff02/charges-chain-audit.json`,
  `diff02/fixdoor.json`, and 10 screenshots in `diff02/`.

⚠ **THE STACK WAS DOWN WHEN THIS LANE STARTED AND THE NEXT LANE WILL HIT IT.** The container had
restarted: PostgreSQL was `down`, nothing served `:8000` or `:8080`. The **data survived** —
`pg_ctlcluster 16 main start`, then the counts above read back intact once `app.tenant_id` was
set (without it every table reads 0, which is the trap the walk lane names). The backend was
restarted with `DATABASE_URL=...` + `DJANGO_SETTINGS_MODULE=config.settings.local`, the SPA with
`API_PROXY_TARGET=http://127.0.0.1:8000`. **A walk begun before that would have recorded seven
dead screens and every finding would have been false.**

### The ordering rule this file obeys

**Per element, stop at the first difference, in this order: presence → order → labels
character-for-character → alignment → spacing → weight/size → colour and state.** A spacing
difference is not reported on an element whose label is already wrong. Where the drawing cannot
decide a question (two strings of identical rendered width, say), the element is marked
**NOT JUDGED** with the reason, never guessed.

### What is deliberately excluded, and why

The drawing's **app shell is a wireframe abstraction** — a light rail with grey placeholder
glyphs, `Demo Water & Light / demoutility`, a plain `Search` box. The product's is a dark nav
with real icons and the live tenant. **Those are not diffed**: the frame is drawn as a stand-in
for the shell, not as a specification of it, and reporting 13 nav rows as "wrong colour" would
bury 166 real comparisons. The nav's **contents** were checked and match: 13 items, same words,
same order.

---

## The counts

| | |
|---|---|
| **Drawn elements compared** | **166** |
| — matching (no difference found) | **80** |
| — **present, with a difference** | **36** |
| — **DRAWN AND NOT ON THE SCREEN** | **49** |
| — could not judge | **1** |
| **ON THE SCREEN AND NOT DRAWN** | **23** |
| **Routed to `build`** | **81** |
| **Routed to `defect`** | **4 elements across 8 defect rows** (3 filed by this lane, 5 re-verified) |
| **Routed to `question`** | **0** |

`49 + 36 = 85` differences in the drawn→built direction; **4** of them are the product wrong on
its own terms and route to `defect`, leaving **81** to `build`. The 23 present-not-drawn are
counted separately and are folded into the same build items — they are the other half of the
same changes (a column that moves under a description is one element gone and one arriving).

---

# Entry 01 · All bills — `/:tenant/billing` · `S30` · `BIL-01` · drawing p007

`BUILD THIS` · `New build` · *"All bills — eight changes, drawn"* · CLOSES `BIL-S13 · BIL-S14 ·
BIL-S15 · BIL-S16 · BIL-S3`

**40 drawn elements: 28 match · 6 differ · 5 absent · 1 not judged.** 5 present-not-drawn.

## DRAWN AND NOT ON THE SCREEN — 5

| # | Drawn | Measured | Route |
|---|---|---|---|
| 1 | **Tab `Print bills`** — the strip is drawn with SEVEN tabs (verified on a 6× crop: `All bills · Run bills · One-time bill · Budget Bills · Fix a bill · Past billing runs · Print bills`) | `billingShared.tsx:106` lists **six**; there is no `print` tab. The screen exists at `/billing/print` and is reached only from the header button | **build** ⚠ **backed by a dated PO ruling** — decision log 2026-09-12, ruling #10 of the fifteen: *"We will need Print bills as tab at Billing level"*. Not a drawing preference |
| 2 | Filter chip **`Cycle 09-A ×`** | absent. Legend 2: all four params *"already filtered in SQL at `selectors.py:905-920`"* — front end only | **build** |
| 3 | Filter chip **`Issued 09/01–09/30 ×`** (date range) | absent, same legend item | **build** |
| 4 | Column **`PRINTED`**, drawn with **three** distinct values — `—` for a draft, `Not yet` for an issued bill that has not printed, a date (green) for one that has | absent. Legend 5 calls it *"the largest of the eight: BR-BIL-016's outbound queue has no table"* ⚠ **that reason is stale** — `outbound_messages` exists and the bill detail already renders two rows from it | **build** |
| 5 | **Third row action** — a `…` overflow carrying *Fix this bill* | the cell holds exactly two: `Open this bill` (eye) and `Print bill` (printer), both `RowAction`s. No overflow component exists | **build** · UI-RULES 15 is *"Max 2 visible + `…` overflow"*, so the product is lawful today and the drawing adds the third |

## PRESENT, WITH A DIFFERENCE — 6

| # | Drawn | Measured | First difference | Route |
|---|---|---|---|---|
| 6 | Roll-up `Out this cycle **$342,180.00**` | `Out this cycle **Not counted yet**` | value | **defect — `DEF-BIL-5236`**, filed by this lane. See below |
| 7 | Roll-up `Unresolved from the last run **3 →**`, an accent LINK to the pending queue | `Unresolved from the last run 0` — plain text, no anchor | presence (of the link) | **build** · legend 3: the figure is already computed and the screen already exists |
| 8 | Download glyph, **enabled** | `DownloadButton` renders **disabled**, wrapped in a `title` reading *"Bills cannot be downloaded yet. No export is built for this list."* | state | **build** · legend 6 `CHANGED`; the code's own reason is still true — there is no `apps/billing/exports.py` |
| 9 | `STATUS` header carries an **ⓘ** | no ⓘ on the header or in any cell | presence (of the marker) | **build** · legend 1's other half |
| 10 | `TOTAL` header **right-aligned over the money** — measured on a 9× crop, header right edge and `$71.50`'s right edge within **2 px at 9×** (≈0.2 px at 1×) | header content sits LEFT: `headerRightGap 47` against `cellRightGap 12` — a **35 px** offset between the word and the figures under it | alignment | **build** |
| 11 | The past-due explainer as a **collapsed `<details>` BELOW the table**, summary *"Why no bill is marked past due"* | the same sentence renders as **open prose ABOVE the table**, 55 words | presence of the disclosure / position | **build** · legend 1 `MOVED`, B14 rule 32 (*a stated absence is CLOSED by default*) |

## COULD NOT JUDGE — 1

| # | Drawn | Why not |
|---|---|---|
| 12 | *"A draft sorts to the top, and that is correct… `_apply_order` puts **nulls first on descending**"* | **This tenant has no draft bill.** `invoices` holds 91 `issued` + 1 `corrected` and zero `draft`, so the null-issue-date branch never rendered. An empty branch is not a branch that matched. **A step-2 lane must create one draft before calling this conforming** |

## ON THE SCREEN AND NOT DRAWN — 5

All five are weight, colour or treatment; none is structural.

| # | On the screen | Drawn instead |
|---|---|---|
| 13 | `Start a billing run →` is a **filled accent primary** | drawn as plain text — the LOWEST-emphasis of the three header actions |
| 14 | The `All` status segment is a **filled black button** | drawn as plain small text beside the search box |
| 15 | `Issued` renders as a **bordered grey chip** in every status cell | drawn as bold plain text |
| 16 | The two row-action glyphs render in **accent red** | drawn in dark grey |
| 17 | The column chooser also offers **`Subtotal`** and **`Tax`** as hideable columns | the carry-over names only `Bill type` and `Template version` as the hidden pair |

## ALREADY BUILT — one drawn change the drawing does not know has landed

**Legend 8, *"Column choices remembered · `table.S30.columns` · UI-RULES 14 · CHANGED"*, IS
BUILT.** `DataTable.tsx:252` calls `columnPreferenceKey(config)`, `tableTypes.ts:360` forms
`table.<screenId>.columns`, the bills table's `screenId` is `"S30"`, and the hook reads through
`getUserPreference` on mount and writes through `putUserPreference` on every toggle.

⚠ **And the file's own header still says the opposite** — `BillsListPage.tsx:42`: *"**No column
chooser persistence, no CSV export.** … IS-5's per-user column preference needs US-SHL-013's
preference service, **which is not wired**."* The preference service is wired
(`config/urls.py` includes `apps.tenancy.preferences_api`) and the chooser uses it. **Hard-won
law 1** — recorded here rather than filed, because the comment is wrong and the behaviour is
right, so nothing a clerk can see is affected. A step-2 lane touching this file should correct
the sentence in the same commit.

---

# Entry 02 · Bill detail (the parent) — `/:tenant/billing/bills/:invoiceId` · `BIL-05`

`BUILD THIS` · `New build` · *"Nothing on the bill detail is lost"* · **no `CLOSES` printed** ·
**no drawing of its own** — the header and tab strip below are read off the frames of 02.1–02.5,
which draw them identically on every page.

**19 drawn elements: 8 match · 3 differ · 8 absent.** 5 present-not-drawn.

## DRAWN AND NOT ON THE SCREEN — 8

| # | Drawn | Measured | Route |
|---|---|---|---|
| 18 | **Copy-the-bill-number glyph** (⧉) beside the title | absent | **build** · legend 8: *"it gets read aloud and pasted into Fix-a-bill all day"* |
| 19 | **Who this is** — the customer's name, bold, in the header | absent from the header. ⚠ **`customer_name: "Kaya Kowalski"` IS already served** on `GET /invoices/{id}` — measured live | **build**, and cheaper than drawn: the chip says `New read`, the name is **Exists behind** |
| 20 | **The service address**, linked, beside the name | absent, and **not** on the invoice payload — it is derived by walking to `premises` (hard rule 8) | **build** — genuinely a new read |
| 21 | The money line **`$251.45 due 08/22/2026`** in the header | absent — the total appears only inside the Amount panel | **build** · legend 2 `MOVED` |
| 22 | **`billed 08/02/2026`** — the issue date in the header | absent. `issued_at` is served | **build** · legend 3: *"three dates matter and only two were shown"* |
| 23 | **The cycle by name** — `Silver Creek — monthly` | absent. `cycle_label` is served as **`CY-007`**, a code. The utility's own words (`Silver Creek — monthly`) do appear — on the printed PDF, not on the screen | **build** · legend 4, *"the clerk's word for which run was this"* |
| 24 | A **`…` overflow** holding `Print bill` and `Cancel this bill`, *"Cancel keeping its reason"* | absent. Four header controls render at equal weight | **build** · legend 6, UI-RULES 4–6 |
| 25 | Tab **`Sent ₂`**, third of five | absent. `?tab=sent` falls back to Document (`aria-selected="true"` on Document) — `billingTabFrom`'s documented fallback, working correctly | **build** — this is entry 02.5, *entirely new* |

## PRESENT, WITH A DIFFERENCE — 3

| # | Drawn | Measured | First difference | Route |
|---|---|---|---|---|
| 26 | `View the bill as sent` as the **filled primary**, `Fix this bill` secondary | `View the bill as sent` is the **third** of four equal bordered controls; nothing on the screen is primary | weight | **build** |
| 27 | The account number bare in the who-line: `Clara Castillo · 105 Cedar Ridge Way… · AC-2026-00003` | rendered as a **labelled pair**, `Account AC-2026-00011` | labels | **build** |
| 28 | Tab `Corrections ₀` — a **count** so *"a clerk never clicks to find nothing"* | `Corrections`, no count | labels | **build** · legend 7 |

## ON THE SCREEN AND NOT DRAWN — 5

| # | On the screen | Drawn instead |
|---|---|---|
| 29 | A second heading pill, **`Past-due unknown`**, beside `Issued` | legend 5: *"One pill, not two"* — the fact lives once, under `Dates` |
| 30 | **`Print bill`** as a top-level header control | inside the `…` overflow |
| 31 | **`Cancel this bill`** as a top-level header control, disabled | inside the `…` overflow, *"keeping its reason"* |
| 32 | `Service period 07/01/2026 – 07/31/2026` in the sub-line | under the `Dates` group, with `· 31 days` |
| 33 | `Due date 08/22/2026` in the sub-line | in the money line, as `$251.45 **due** 08/22/2026` |

⚠ **`Cancel this bill`'s `title` carries 60 words of rationale** (*"Before a bill is cancelled
you must be shown, in plain words, what it will do: which entries reverse, how the balance
changes…"*). B14 rule 33 puts **rationale at zero words on screen**. **Not filed and not routed**:
the drawing explicitly keeps this control's reason (legend 6, *"Cancel keeping its reason"*), and
a refusal REASON is a consequence rather than rationale. Recorded so a step-2 lane rules on it
against the drawing instead of re-deriving it.

## ⚠ ONE AS-BUILT CLAIM IN THE DRAWING IS STALE — RE-MEASURED AND REFUTED

p014's header-control table says of `Fix this bill`:

> *"⚠ **And this is the door that creates the rule-31 breach.** It arrives on the Fix-a-bill
> screen having put the invoice **UUID into a visible text box labelled *Bill***. The door is
> right; what it lands on is not."*

**Walked through the door as a clerk does** — opened the bill, clicked `Fix this bill`, landed on
`/brazosbend/billing/fix?bill=01a09e8d-…`:

* **UUIDs matching `[0-9a-f]{8}-…` in the whole rendered page: 0.**
* The `Bill` field reads **`BL-2608-000058`** with a `Choose another bill` control beside it.
* The only visible inputs are the global search box and a `What went wrong` select.

**The rule-31 breach on this door is fixed.** The blueprint was read at `v2.235.0` on 11
September; we are at `v2.261.4`. ⚠ **A step-2 lane must not "fix" it again** — and this is
exactly the shape `CLAUDE.md` law 13 exists for.

⚠ **But the screen it lands on has a different fault, and it is already filed:** the `What went
wrong` select renders **thirteen raw snake_case codes** — `charge_billed_in_error`,
`customer_name`, `goodwill`, `meter_number_or_read_dates`, `missed_charge`,
`premises_or_unit_label`, `service_or_mailing_address`, `template_or_language`, `theft_restated`,
`wrong_period_or_service`, `wrong_rate_plan`, `wrong_read`, `wrong_tax`. **`DEF-BIL-5233`**,
filed by a sibling lane today. Not re-filed. It is the source of the `wrong_read` that reaches
entry 02.3's REASON column.

---

# Entry 02.1 · Bill detail · Document — `…?tab=document` · drawing p015–p016

`BUILD THIS` · `New read` · *"the new heading, and the overview grouped"* · CLOSES `BIL-S17 ·
BIL-S18 · BIL-S19 · BIL-S20`

**26 drawn body elements: 7 match · 8 differ · 11 absent.** 4 present-not-drawn.

The drawing's own summary of the target: **"Seven groups, one word each, in the order a clerk
asks them: Amount → Breakdown → Usage → Dates → the document itself → Origin → Record."**
The product has six panels in a different order and only two of the seven words.

## DRAWN AND NOT ON THE SCREEN — 11

| # | Drawn | Measured | Route |
|---|---|---|---|
| 34 | `Owed today  **on this account →**` row in the Amount group, the live balance, linked | absent. ⚠ **`GET /accounts/{id}` serves `balance = 300.400000 USD`, `balance_basis = posting`, `balance_source = ledger`** — measured live | **build**; chipped `New read`, actually **Exists behind** |
| 35 | `BREAKDOWN` group label | absent from Document | **build** · legend 10 `MOVED` (the table stays on Charges) |
| 36 | The one-line breakdown `Water $132.02 · Sewer $94.50 · Trash $15.00 · …· Tax $4.93` | absent. `charges_by_service` **is served** on the invoice payload | **build** — Exists behind |
| 37 | `See every charge →` link into the Charges tab | absent | **build** |
| 38 | `USAGE` group label | absent | **build** |
| 39 | The USAGE table — `SERVICE · THIS PERIOD · AVERAGE · READ`, with the read linked | absent. ⚠ **`GET /accounts/{id}/usage` answers 200** with per-service monthly points, units and a 12/24-month window — probed live | **build**; chipped `New read`, actually **Exists behind**. Legend 11 called it *"mounted"* and it is |
| 40 | `DATES` group label | absent from Document (`When this is due` is on Charges) | **build** · legend 12 |
| 41 | `Billed  08/02/2026` row | absent | **build** |
| 42 | `↓ Download the bill as sent (PDF)` button | absent — there is a text link, `Open the bill as the customer received it`, to the standalone document screen | **build** · legend 14 |
| 43 | `Open it in a new tab ↗` button | absent | **build** |
| 44 | `Saved copy  **Kept — 2 pages**` row (green) | absent. `has_payload: true` is served | **build** |

## PRESENT, WITH A DIFFERENCE — 8

| # | Drawn | Measured | First difference | Route |
|---|---|---|---|---|
| 45 | Accent group label `AMOUNT` | panel heading `Amount due`, `h3` 16px/800 | labels | **build** |
| 46 | *"The four figures above are the ones saved on the bill the day it was issued. **Owed today** is the live balance on the account."* | *"These figures are the ones saved on the bill the day it was issued, not today's balance."* | labels | **build** — the drawn sentence names the row that does not exist yet |
| 47 | `Service period  07/01 – 07/31/2026 · **31 days**` as a DATES row | in the header sub-line, **without** the day count | presence (of the day count) | **build** |
| 48 | `Past due  Not checked on this deployment` as a DATES row | a heading pill reading `Past-due unknown` | presence (as a row) | **build** · legend 5 |
| 49 | `Fees on this bill  None` as a DATES row | present, on the **Charges** tab under `When this is due` | order (wrong tab) | **build** |
| 50 | Group label `THE BILL` | `Customer's bill` | labels | **build** |
| 51 | `▸ **Origin**` — collapsed, closed by default | `Where this bill came from` — an **open** panel with 5 rows and a 20-word note | presence (of the disclosure) | **build** · legend 13, B14 rule 32 |
| 52 | `▸ **Record**` — one collapsed disclosure merging *How this bill was produced* + *Record check* | **two** separate open panels, each with its own note | presence / order | **build** · legend 13 |

## ON THE SCREEN AND NOT DRAWN — 4

| # | On the screen | Note |
|---|---|---|
| 53 | ⛔ **THE EMBEDDED PDF VIEWER.** A full `document.pdf` frame — page thumbnails, page counter `1 / 2`, zoom `99%`, `−`/`+`, fit, rotate, draw, undo, redo — occupying the middle of the tab | **This is the one thing the PO ruled out.** Decision log 2026-09-11, ruling **#1** of the fifteen, verbatim: *"we dont what full view of the document - you give a link to download but full view of document is not requires - it does not add any value to user"*. It is the **only `REMOVED` row in the whole blueprint** (entry 02's carry-over) and every §02 drawing's caption names it. **Still rendering at `v2.261.4`** |
| 54 | The caption above it: *"This is the page the bill prints as. Print or save it from the viewer."* | copy that exists only to explain the viewer |
| 55 | The **`Delivery`** panel and its `CHANNEL · STATUS · QUEUED · CAME BACK · ACTION` table with two live rows and two `Mark returned` buttons | drawn as the new **`Sent`** tab — entry 02.5 |
| 56 | The Delivery note: *"Queued is the final state today. Nothing on this deployment sends bills — there is no dispatcher and no provider connection — so a queued row means the bill is ready to go out, not that a send failed."* | drawn on the Sent tab, with one extra sentence — *"**Printing is the channel every bill has.**"* |

⚠ **Element 53 is the single largest build item in §02 and it is a REMOVAL, not an addition.**
It routes to **build** and not to defect, because the redesign is the vehicle for the ruling —
but it is backed by a dated PO ruling now greppable in `12-governance/02-decision-log.md`, which
puts it ahead of every ordinary redesign item in this section.

⚠ **One documentation nit, recorded so nobody re-derives it:** the drawn frame carries a **⑭**
marker on `THE BILL` and the printed legend runs **1–13**, so marker 14 has no legend row. The
text for it is on p019, in the left margin beside the Charges frame, as a floating note. Nothing
is missing; it is on the wrong page.

---

# Entry 02.2 · Bill detail · Charges — `…?tab=lines` · drawing p018–p019

`BUILD THIS` · `Exists behind` · *"Rate version folded under the description"* · **no `CLOSES`
printed**

**23 drawn elements: 15 match · 7 differ · 1 absent.** 5 present-not-drawn.

The drawing's own summary: **"Two changes, and neither loses a field… Nothing is removed."**
① `Accounting code` and `Rate version` come out of their own columns and ride **under the
description**, taking the table from **seven columns to five** · ② the four panels get
**one-word group labels — Amount · By service · Every charge · Tax** — *"so the tab reads as
four questions rather than five headings."*

## DRAWN AND NOT ON THE SCREEN — 1

| # | Drawn | Measured | Route |
|---|---|---|---|
| 57 | A **sub-line under each description** carrying both folded values: `4110 — Water usage · Residential water (inclining tiers), from 08/01/2026` | absent — the two values are still two columns | **build** |

## PRESENT, WITH A DIFFERENCE — 7

| # | Drawn | Measured | First difference | Route |
|---|---|---|---|---|
| 58 | `AMOUNT` | `Amount due` | labels | **build** |
| 59 | `BY SERVICE` | `What each service cost` | labels | **build** |
| 60 | Tax row label `Tax — charged to the bill, not a service` | `Charged to the bill, not to a service` + `Tax` in one cell | labels | **build** |
| 61 | `EVERY CHARGE` | `Charges on this bill` | labels | **build** |
| 62 | `Total` row **bold** | `Total` renders at **weight 400 / 13.5px** while the header panel's `Total due` is **800 / 15px** | weight | **build** — and this is p020's alignment finding 4, **RE-VERIFIED LIVE** |
| 63 | `TAX` | `Tax on this bill, by authority` | labels | **build** |
| 64 | `Total tax` row | `Authority subtotal` | labels | **build** |

## ON THE SCREEN AND NOT DRAWN — 5

| # | On the screen | Note |
|---|---|---|
| 65 | Column **`ACCOUNTING CODE`** (224 px) | the folded pair — the mirror of element 57 |
| 66 | Column **`RATE VERSION`** (324 px, content 295 px — **the widest column in the table**) | the folded pair |
| 67 | Panel **`When this is due`** — Due date · Past due · Fees on this bill | drawn on the Document tab as `DATES` (legend 12) |
| 68 | The line *"These add up to the tax."* under the tax table | not drawn |
| 69 | A **second** total row, `Tax  $14.73`, directly beneath `Authority subtotal  $14.73` — the same figure twice | the drawing has one `Total tax` row |

## ⚠ THE DOCUMENT'S SIX ALIGNMENT FINDINGS, RE-CHECKED AGAINST A RUNNING BACKEND

p020 lists *"Is the content properly aligned? No — six things, and they are all the same kind."*
**Its author had no backend**, so every one was predicted from source. Measured here in Chromium
with 12 real charge rows:

| p020 | Claim | Result |
|---|---|---|
| 1 | *"Usage is left-aligned beside two right-aligned money columns"* | **RE-VERIFIED.** `USAGE` th/td `text-align: left`; `RATE` and `AMOUNT` both `right` |
| 2 | *"`Rate version` wraps mid-date… it is the widest column"* | **RE-VERIFIED as widest** — 324 px of 1,086. On this bill's shorter strings it does not wrap; the tax row is 2 lines |
| 3 | *"The accounting code wraps too"* | **NOT REPRODUCED ON THIS BILL.** `4100 — Electric usage` is 123 px in a 224 px column. The document's example was the tax row's longer string; this tenant's tax code is short |
| 4 | *"`Total` is not emphasised… while the header panel's `Total due` is bold"* | **RE-VERIFIED.** `Total` = `<td>` 400/13.5px · `Total due` = `<dt>` 800/15px |
| 5 | *"The em-dash placeholders sit on opposite sides"* | **RE-VERIFIED** — and see the finding below |
| 6 | *"Row heights are ragged"* | **RE-VERIFIED, measured:** group rows 36 px · `electric base charge` 38 px · every usage row 59 px · the tax row 61 px. Four heights in twelve rows |

⚠ **AND THE REDESIGN DOES NOT FIX FINDINGS 1 AND 5, THOUGH ITS OWN TEXT SAYS IT WILL.** p020
concludes: *"All six trace to one decision: seven columns, two of them long text… Fold the two
text columns under the description and **the other four straighten out on their own.**"*
**Measured on the drawing itself, at 6×:** in the redesigned five-column table, `USAGE` is
**left-aligned** (`5 kgal` starts at x≈1145 and `10 kgal` at x≈1141 — same left edge; their right
edges differ by 21 px, which right-alignment cannot produce), while `RATE` and `AMOUNT` are
right-aligned (every value's right edge on 1500 and 1728 respectively). And the base-charge row's
two em-dashes sit **left under `USAGE` and right under `RATE`**, exactly as finding 5 describes.

**So a lane that builds this drawing and then closes findings 1 and 5 will have closed nothing.**
This is B14 rule 37 running in the direction people forget: a drawing's figures are
illustrations, and so is a drawing's *claim about itself*.

---

# Entry 02.3 · Bill detail · Corrections — `…?tab=chain` · drawings p021 (empty) + p022 (populated)

TWO `BUILD THIS` bands. State 1 `Exists behind` *"two groups, and a way out"* (no `CLOSES`) ·
State 2 `Exists behind` *"the populated state"* · CLOSES `BIL-S21`

**22 drawn elements across the two states: 2 match · 5 differ · 15 absent.** 4 present-not-drawn.

## ⛔ THE POPULATED STATE HAD NEVER BEEN SEEN BY ANYBODY. IT HAS NOW.

The blueprint says so in its own red rail (p023): *"`DEF-2901` records no database in this repo
has a draft bill, and this repo has no corrected bill either, **so the three standings, the
credit-note table and the replacement link have never been rendered together.** Every figure
above is an illustration and none is a served value."* The walk lane could not reach it either —
its UNJUDGED #3 says the bill it walked *"has no correction"*.

**There is a correction chain on this tenant and this lane walked it:**

```
BL-2607-000032   status corrected     ← the original
BL-2607-000047   status issued        corrects_invoice_id → BL-2607-000032
```

Both states were opened. **The drawn frame and the built screen agree on almost nothing.**

## STATE 1 · empty — 7 drawn elements: 1 match · 2 differ · 4 absent

| # | Drawn | Measured | Route |
|---|---|---|---|
| 70 | `STANDING` group label | absent — three stacked sentences, no groups | **build** |
| 71 | Green pill **`This is the current bill`** | absent — the words are inside a sentence instead | **build** |
| 72 | `HISTORY` group label | absent | **build** |
| 73 | **`Fix this bill`** button ON THE TAB | absent. *"today the only route is the header button"* — **re-verified: the tab's only controls are the four tab buttons and the disabled `Cancel this bill` in the header** | **build** |
| 74 | Standing sentence *"Nothing has replaced it, and no credit note or replacement bill is recorded against it."* | split in two: *"This is the current bill. Nothing has replaced it."* + *"No credit note or replacement bill is recorded against this bill."* | labels → **build** |
| 75 | `Nothing to report.` under HISTORY | absent as such (folded into 74's second sentence) | labels → **build** |
| 76 | *"Correcting a bill never changes it. The original stays exactly as the customer received it, and the correction is a credit note and, where one is needed, a replacement bill."* | **identical, word for word** | — **matches** |

## STATE 2 · populated — 15 drawn elements: 1 match · 3 differ · 11 absent

| # | Drawn | Measured on `BL-2607-000032` | Route |
|---|---|---|---|
| 77 | `STANDING` group label | absent | **build** |
| 78 | Pill **`Replaced`** | **present** — `Replaced` | **matches** |
| 79 | `Open BL-2609-000051, the bill that counts now →` | `Open BL-2607-000047, the bill that counts now` — the trailing `→` is absent | labels → **build** |
| 80 | Standing sentence *"This bill stays exactly as the customer received it. A replacement bill was issued on 09/03/2026 and it is the one that counts."* | absent | **build** |
| 81 | `WHAT HAPPENED` group label | absent | **build** |
| 82 | Column `WHEN` | absent — the table is `CREDIT NOTE · AMOUNT · REASON · ISSUED` | **build** |
| 83 | Column `WHAT` | absent | **build** |
| 84 | Column `REASON`, value **`Wrong reading used`** | present; the value is **`wrong_read`** | labels → **defect, already filed: `DEF-2448`** (open since 2026-08-30). Its own text: *"On the development fixture the cell reads `wrong_read`"* — **now re-verified on a real corrected invoice on a real tenant**. Not re-filed |
| 85 | Column `WHO` | absent | **build** |
| 86 | Column `EFFECT` | absent | **build** |
| 87 | Row: **the bill issued** (`BL-… issued / this bill`, effect `$251.45`) | absent | **build** |
| 88 | Row: **correction opened** (`case CC-0041`, reason, who) | absent | **build** |
| 89 | Row: **approved** (who + their role) | absent | **build** |
| 90 | Row: **credit note** (`CN-2609-000012 / cancels this bill`, effect `−$251.45`) | present in a different shape — one row, `CM-0001 · -$137.70 · wrong_read · 07/17/2026` | order/shape → **build** |
| 91 | Row: **replacement bill** (`BL-… / the bill that counts now`, effect `$198.30`) | absent from the table; the fact is carried by the link at the top | **build** |

## ON THE SCREEN AND NOT DRAWN — 4

| # | On the screen | Note |
|---|---|---|
| 92 | A `Replaces bill / Replaced by bill` definition pair, on both bills of the chain | not drawn in either state |
| 93 | Column `CREDIT NOTE` — the credit-note number `CM-0001` | not drawn as a column (the number is inside the drawn `WHAT` cell) |
| 94 | Column `ISSUED` — the credit note's date | not drawn as a column (the drawn `WHEN` carries it) |
| 95 | ⚠ **A THIRD STANDING THE DRAWING HAS NO STATE FOR.** On the replacement `BL-2607-000047` the screen reads *"This is the current bill. Nothing has replaced it."* **and** `Replaces bill  BL-2607-000032` below it | The drawing draws two standings — *current* and *replaced*. **A bill that IS a replacement is a third**, and nothing in §02 says how it should read. Recorded as a **gap in the drawing**, not a defect and not a question: the product's answer is truthful and nobody has ruled on it |

## ⚠ THE MONEY ARITHMETIC — the drawing agrees with hard rule 4, and the product agrees with both

p023's red rail states the correction arithmetic against hard rule 4: the original stays at
`$251.45` for ever, a credit note of `−$251.45` cancels it, a replacement of `$198.30` is issued,
the customer is `$53.15` better off — *"Three documents, not one edited one."*

**Checked against the live chain:** `BL-2607-000032` is still present, still `status=corrected`,
still carries its own total; `CM-0001` is a **separate row** at `-$137.70`; `BL-2607-000047` is a
**separate invoice** with its own number. **No row was updated and none was deleted.** Hard rule
4 is satisfied on the one real correction this tenant has. **No question arises.**

---

# Entry 02.4 · Bill detail · Audit — `…?tab=audit` · drawings p024 (state 1) + p025 (state 2)

TWO `BUILD THIS` bands, both `Blocked` on `BIL-S22`. State 1 *"newest first, dates in words,
nothing hidden"* (no `CLOSES`) · State 2 *"one row per field, not three parallel lists"* ·
CLOSES `BIL-S22`

**21 drawn elements across the two states: 13 match · 3 differ · 5 absent.** 0 present-not-drawn.
⚠ State 2 supersedes state 1's table shape, so the two states are listed separately and the
overlap is noted rather than counted twice.

## STATE 1 — 16 drawn elements: 13 match · 3 differ · 0 absent

Everything structural is already there. The toolbar (`Search this history…` · `All` ·
`+ Filter ▾` · column chooser), all five columns, the pager, `Open the audit log for this
record →` and `Showing the last 2 years` all render. **The three differences are the drawing's
own "three fixes", and all three are RE-VERIFIED LIVE:**

| # | Drawn | Measured | Route |
|---|---|---|---|
| 96 | `WHEN ▼` — **newest first** | **`WHEN ▲`** — `PremisesDetailPage.tsx:2707` sets `defaultSort { sort: "when", dir: "asc" }`. ⚠ **And the global audit log this tab links to renders `WHEN ▼` over the identical row** — two surfaces, one dataset, opposite defaults | **defect — `DEF-BIL-5240`**, filed by this lane |
| 97 | `08/02/2026 04:00` — the raw stamp put through the one date formatter (BR-SHL-034) | the `TO` cell prints **`2026-08-02T09:00:00+00:00`** while the `WHEN` cell in the SAME ROW prints `09/14/2026 01:14`. Two conventions, one row | **defect — `DEF-BIL-5240`** |
| 98 | `▸ 7 more fields` — *"expands in place"* | `+7 more`, twice. **Probed in Chromium: a bare `<span>`, no `role`, no `tabindex`, `cursor: auto`, no clickable ancestor; a click leaves `document.body.innerText` at exactly 751 characters — unchanged.** Seven of the ten changed fields cannot be seen on the tab. They ARE reachable one screen away, behind the global log's `Expand▾` | **defect — `DEF-BIL-5240`** |

## STATE 2 — 5 drawn elements: 0 match · 0 differ · 5 absent

| # | Drawn | Measured | Route |
|---|---|---|---|
| 99 | Column renamed `FIELD` | header still reads `WHAT CHANGED` | **build** |
| 100 | **One table ROW per changed field**, with `WHEN` and `WHO` spanning them | three newline-joined lists in three cells: `Status / Issued at / Template version / +7 more` against `draft / Not set / Not set` against `issued / 2026-08-02T09:00:00+00:00 / 1 / +7 more` | **build** — *"and this is the important one"* |
| 101 | The `WHO` cell carries the actor's **role** under the name (`Vijay Bikkad / System Admin`) | `Dana Whitfield` alone | **build** |
| 102 | `▸ Show the other 6 fields that changed` | absent | **build** |
| 103 | Footer `1–1 of 1 change · **10 fields**` | `1–1 of 1` | **build** |

## ⚠ WHY THIS ENTRY'S BUILD ITEMS BELONG TO ANOTHER MODULE

`BillDetailPage.tsx:87` — `import { AuditTab } from "@/features/metering/PremisesDetailPage"`.
**Every detail screen in the product mounts the same component.** The drawing says so and draws
the right conclusion:

> *"Fixing it here fixes it everywhere: the right outcome and the wrong blast radius to take on
> inside a billing change. **It needs its own change request.**"*

Both `BUILD THIS` bands are chipped `Blocked` for exactly this. **`DEF-BIL-5240` is filed with
`module = metering`** so it lands with the code rather than with the screen it was seen on;
`DEF-MET-4764` and `DEF-MET-4765` are already open against the same component.

## ⚠ AND ONE CONSTRAINT THIS ENTRY INHERITS, WITH THE CITATION CORRECTED

p026 names *whether an audit row recording a `payments` reference correction is exempt from
retention pruning* as OPEN, and forbids describing this tab as a permanent record. **The
constraint is right and binding. The id the drawing prints is not: p026 says `OQ-1330` and the
question is `OQ-1340`** — already filed as **`DEF-GOV-5229`** by the sibling lane that mapped
§02. Not re-filed. Repeated here only because a build lane reading p026 will take the wrong id
off the page, and `OQ-1330` is a real, different, open metering question.

---

# Entry 02.5 · Bill detail · Sent — `…?tab=sent` · drawing p027

`ENTIRELY NEW` · `BUILD THIS` · `New build` · *"a new tab, split out of Document"* · CLOSES
`BIL-S19`

**15 drawn elements: 7 match · 4 differ · 4 absent.** 0 present-not-drawn.
The tab itself is element 25 under entry 02 and is not counted twice.

**The table already exists — as the `Delivery` panel at the bottom of the Document tab.** So
this entry is mostly a MOVE plus one new group, and the walk lane's confirmation 2 is exactly
right: *"the bill detail carries four tabs and no fifth… this walk confirms it is unbuilt. That
is a build item correctly described, not drift."*

## DRAWN AND NOT ON THE SCREEN — 4

| # | Drawn | Measured | Route |
|---|---|---|---|
| 104 | `HOW THEY HEAR FROM US` group label | absent | **build** |
| 105 | `Paperless  Not elected` | absent. ⚠ **`paperless` IS served on `GET /accounts/{id}`**, alongside `sms_reminders` and `preferred_language` | **build**; p028 calls this group *"a proposal, not a redraw… **NEW** and needs a customers read"* — the read exists |
| 106 | `Email  clara.castillo@example.com` | absent. `contacts` is on the account payload | **build** |
| 107 | `Post  105 Cedar Ridge Way, Unit 1` | absent. `premise_address` + `unit_label` are on the account payload (derived by walking — hard rule 8) | **build** |

## PRESENT, WITH A DIFFERENCE — 4

| # | Drawn | Measured | First difference | Route |
|---|---|---|---|---|
| 108 | Accent group label `SENT`, on its own tab | panel heading `Delivery`, at the foot of the Document tab | labels / location | **build** |
| 109 | Channel **`Print`**, with the sub-line *"in print set PS-0014"* | **`pdf_print`**, no sub-line | labels | **defect — `DEF-BIL-5237`**, filed by this lane, for the code; the print-set sub-line is **build** |
| 110 | Channel **`Customer portal`** | **`portal`** | labels | **defect — `DEF-BIL-5237`** |
| 111 | The Queued note ending *"**Printing is the channel every bill has.**"* | present word for word **minus** that closing sentence | labels | **build** |

⚠ **THE DRAWING GIVES THE REASON FOR 109 AND 110 IN ITS OWN WORDS**, on p028: *"The channel
names become words — `pdf_print` → **Print**, `portal` → **Customer portal** — because a machine
code on a clerk's screen is **B14 rule 32**."* Measured: `billing.bill.channel.*` and
`billing.bill.delivery.*` hold **0 keys in all eleven locale files**, and
`BillDetailPage.tsx:1195-1196` falls back to the raw value. It is a product fault whether or not
this redesign is ever built, which is why it is a defect and not only a build item.

## `?tab=sent` TODAY — checked, and it behaves correctly

Opening `…?tab=sent` renders the **Document** tab with `aria-selected="true"` on it. That is
`billingTabFrom`'s documented fallback (*"BR-SHL-011's spirit: an unknown tab falls back to the
first, never errors"*), and it is the right behaviour for an address that does not exist yet.
**No defect.** It is also the cleanest available proof that the tab is unbuilt.

---

# The defects

## Filed by this lane — 3

### `DEF-BIL-5236` — the *Out this cycle* money KPI is refused on a reason the PO ruled away 34 days ago

**`not-built` · medium.** The header reads `Out this cycle  Not counted yet` over 92 real bills.
`invoices_rollup()` returns `billed_this_cycle=None` hardcoded, and its own docstring item 2
gives the reason:

> *"no signed document says what "this cycle" means for the S30 header… A money KPI computed on a
> guessed definition is a claim about money. Null, and REPORTED."*

`apps/billing/api.py`'s exception trailer repeats it: *"no signed document defines 'this cycle'
for the S30 header… REPORTED as an OQ candidate."*

**Both sentences are false.** `OQ-114` reads **CLOSED 2026-08-11 — PO ruling, option C**,
verbatim *"Option C"*, and `12-governance/02-decision-log.md` carries the worked example — main
run `$342,180`, catch-up `+$12,400`, one correction net `−$12.81`, a July back-bill `+$890`
excluded, answer **`$354,567.19`** — and names `InvoicesRollup.billed_this_cycle` and `S30` in
its own consequences column. The definition IS signed.

⚠ **The tooltip is worse than the cell.** `billing.rollup.thisCycleWhy` reads *"The amount billed
this cycle is served with the bills list, with its currency. **Nothing serves that list yet.**"*
`GET /invoices` serves 92 rows and `rollup.bills` renders 92 six pixels away. Its two siblings —
`billsWhy` and `unresolvedWhy` — carry the same stale clause; those two are inside
**`DEF-BIL-5231`**'s scope and are recorded here as further evidence for it rather than filed
again.

**Not `DEF-BIL-5231`.** That one is the roll-up query being disabled on five of six tabs. This is
the **All-bills** tab, where the query runs and the server answers null.

### `DEF-BIL-5237` — the Delivery panel prints the channel and the status as raw machine codes, in all eleven languages

**`copy-i18n` · medium.** `CHANNEL` reads `pdf_print` and `portal`; `STATUS` reads `queued`.
`BillDetailPage.tsx:1195-1196` resolves each through a template key with `defaultValue` set to
the raw value, and **`billing.bill.channel.*` and `billing.bill.delivery.*` hold 0 keys in every
one of `en, de, es, es-MX, fr-FR, hi, id-ID, it-IT, ja-JP, ko-KR, pt-BR`** — so the fallback is
not a fallback, it is the only path there has ever been. The words already exist one module
away: `customers.account.communication.channel.pdf_print = "Post"`, `.portal = "Portal"`.

Fourth sighting of one mechanism in this module after `DEF-518`, `DEF-2448` and `DEF-BIL-5233`.
**The pattern is the `defaultValue` fallback, not any one key.**

⚠ **This row's own title lost two key names to shell backtick expansion when it was filed.** The
sentence immediately after them names both prefixes and counts them as 0 in 11 locales, so
nothing is lost, and `file_defect.py` deliberately refuses to edit a row. It stands rather than
being hand-rewritten into a shared register (law 11).

### `DEF-BIL-5240` — the shared audit tab, against the audit log it links to

**`design-divergence` · medium · `module = metering`.** Three faults in one row, all three
predicted by the blueprint with no backend and all three re-measured here with one: an
**oldest-first** default sort where the global log the tab links to sorts newest-first; a **raw
ISO timestamp** in the `TO` cell beside a formatted one in `WHEN`; and **`+7 more` as an inert
`<span>`**, hiding seven of ten changed fields on the tab. Filed against metering because
`BillDetailPage.tsx:87` imports the component from there and six detail screens mount it.

## Re-verified live, NOT re-filed — 5

| id | status | What this lane added |
|---|---|---|
| `DEF-2448` | open since 2026-08-30 | Its evidence was *"on the development fixture"*. **Now seen on a real corrected invoice on a real tenant** — `BL-2607-000032`'s REASON cell reads `wrong_read` |
| `DEF-BIL-5233` | open, filed today by a sibling | Confirmed as the **source** of `DEF-2448`'s value: the same thirteen codes, on the control that writes the correction |
| `DEF-BIL-5230` | open | The `Past billing runs` tab still refuses over three served runs — unchanged |
| `DEF-BIL-5231` | open | Re-confirmed, and **widened with evidence**: the three `*Why` tooltips all still say *"Nothing serves that list yet"* |
| `DEF-BIL-5232` | open | The Budget Bills placeholder is unchanged |

## Already filed elsewhere, cited not re-filed — 1

`DEF-GOV-5229` — `CLAUDE.md` hard rule 4 cites `OQ-1330` where the question is `OQ-1340`, and
p026 of this blueprint took the wrong id from it.

---

# Questions — 0

**Nothing in §02's eight drawings contradicts a signed rule, and nothing in them would move a
❄️ FROZEN B4/B5 figure.** Checked deliberately, not assumed:

* **Hard rule 4 (no UPDATE/DELETE on an issued bill).** 02.3's drawn arithmetic is *"Three
  documents, not one edited one"* and the product's live chain is three separate rows. The
  drawing agrees with the rule.
* **Hard rule 2 (money 4 dp, percentages 6, both DISPLAY 2).** No drawn money figure shows other
  than two places.
* **Hard rule 3 (consumption always with a unit).** Every drawn usage value carries `kgal`,
  `kWh` or an explicit dash.
* **B4/B5 figures.** No drawn figure is a golden-test figure; B14 rule 37 makes every one an
  illustration and none is asserted anywhere in this file.

## ⚠ THE ONE THAT LOOKED LIKE A QUESTION AND IS ALREADY RULED — DO NOT RE-ASK IT

The walk lane recorded *"ONE OBSERVATION, DELIBERATELY NOT CALLED A DEFECT: the document prints
unit rates to 4 dp (`0.1100`, `4.2400`) while money displays to 2… a step-2 lane should confirm
the intended display precision against B4."*

**It is settled, and it was settled 18 days ago.** `OQ-620(a)`, **CLOSED 2026-08-27**, PO
verbatim:

> *"What does a tariff rate show? Four ($0.1420). A rate is not money and not a quantity - 4
> decimal places"*

Worked as put to them: `8.290000` per kgal → `$8.2900`; `0.142000` → `$0.1420`. **Hard rule 2 is
explicitly NOT changed** — money still displays 2, a quantity at most 2 trimmed. And it has
already been re-asked once: **`DEF-CWP-4153`** — *"RATES ARE DRAWN TO FOUR DECIMALS ON A
CUSTOMER'S BILL — `$0.1100 / kWh`, `$4.2400 / kgal`"* — is closed **`invalid`**.

**The drawing shows `$4.2400` and the product shows `$4.2400`, and both are correct.** Nothing to
route. Recorded at this length because hard-won law 13 says a re-ask is a bug in us, and this one
has now been raised twice.

---

# What I could not judge, and exactly why

**Three, each an absence of evidence rather than a pass.**

1. **The draft-sorts-to-top rule (entry 01, element 12).** This tenant holds 91 `issued` + 1
   `corrected` invoices and **zero drafts**, so `_apply_order`'s nulls-first-on-descending branch
   never rendered. A step-2 lane must create one draft first.
2. **The five collapsed as-built frames.** p009, p017, p019, p023 and p026 each carry the
   disclosure line and a table, never a frame. They are not in the PDF. **Nothing in this file
   claims anything about what they showed**, and no statement of the form *"the product has
   drifted from the as-built drawing"* can be sourced from this document for any §02 screen.
3. **Entry 02.2's alignment finding 3** (*the accounting code wraps*). Not reproduced on this
   tenant's bill, whose accounting codes are short. Neither confirmed nor refuted — it needs a
   bill carrying the long tax-payable string the document quotes.

**Also not attempted, and named so nobody reads silence as coverage:** the drawn Corrections
`WHAT HAPPENED` table's *correction opened* and *approved* rows imply a correction CASE with an
approver. Whether such a case exists behind `POST /billing/fix` was **not** probed — this lane
took no write on the money path, and the drawing's own chip for that state is `Exists behind`,
which is a claim a step-2 lane must check rather than inherit.

---

# For a step-2 lane, in order of what it buys

1. **Remove the embedded PDF viewer from the Document tab** (element 53). It is a deletion, it is
   backed by a dated PO ruling now in the decision log, and it is the only `REMOVED` row in the
   whole blueprint. Nothing else in §02 is both this cheap and this clearly ruled.
2. **Add the `Print bills` tab** (element 1). One entry in `BILLING_TABS`, one locale key, one
   route already mounted — and PO ruling #10 of 2026-09-12 behind it.
3. **`DEF-BIL-5236`** — the `Out this cycle` KPI. The definition has been signed since
   2026-08-11 with a worked figure; what is missing is the arithmetic and a corrected docstring.
4. **`DEF-BIL-5237`** — 22 catalogue keys (2 lookups × 11 locales) and the raw codes stop
   reaching clerks.
5. **Entry 02.1's four Exists-behind reads.** `customer_name`, `charges_by_service`,
   `GET /accounts/{id}/usage` and `accounts.balance` are **all already served** — the drawing
   chips three of them `New read` and it is wrong in the cheap direction. Four drawn groups
   (`Owed today`, `BREAKDOWN`, `USAGE`, and `HOW THEY HEAR FROM US` on 02.5) are front-end work
   only.
6. **Raise the change request for the shared `AuditTab`** rather than touching it from billing.
   `DEF-BIL-5240`, `DEF-MET-4764` and `DEF-MET-4765` should go in it together.
7. **Before building entry 02.2, read the finding above about its own alignment claims** — the
   drawing does not straighten `USAGE` or the em-dashes, and closing p020's findings 1 and 5
   against it would close nothing.

---

# What this file is not

It is not a specification and it is not permission to build. **No `.tsx` and no `.py` was
touched.** Where it disagrees with the blueprint it is because the blueprint was read at
`v2.235.0` with no backend and this was measured at `v2.261.4` against a live PostgreSQL with 92
bills on it; where it disagrees with `CR-100-BRC03-walk.md` it is because that lane opened no
drawing and this one opened fourteen pages of them as images.
